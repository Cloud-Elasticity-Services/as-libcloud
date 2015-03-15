# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
try:
    from lxml import etree as ET
except ImportError:
    from xml.etree import ElementTree as ET

from libcloud.utils.misc import find
from libcloud.utils.xml import fixxpath, findtext
from libcloud.common.aws import SignedAWSConnection, AWSGenericResponse
from libcloud.common.types import LibcloudError, ResourceNotFoundError, ResourceExistsError
from libcloud.compute.providers import Provider
from libcloud.compute.base import NodeDriver, AutoScalingGroup, ScalingPolicy, Alarm
from libcloud.compute.drivers.ec2 import EC2Connection, EC2Response
from libcloud.compute.types import ScalingPolicyType, ScalingPolicyOperator

__all__ = [
    'API_VERSION',
    'NAMESPACE',
    'INSTANCE_TYPES',
    'OUTSCALE_INSTANCE_TYPES',
    'OUTSCALE_SAS_REGION_DETAILS',
    'OUTSCALE_INC_REGION_DETAILS',
    'DEFAULT_EUCA_API_VERSION',
    'EUCA_NAMESPACE',

    'EC2NodeDriver',
    'BaseEC2NodeDriver',

    'NimbusNodeDriver',
    'EucNodeDriver',

    'OutscaleSASNodeDriver',
    'OutscaleINCNodeDriver',

    'EC2NodeLocation',
    'EC2ReservedNode',
    'EC2SecurityGroup',
    'EC2Network',
    'EC2NetworkSubnet',
    'EC2NetworkInterface',
    'EC2RouteTable',
    'EC2Route',
    'EC2SubnetAssociation',
    'ExEC2AvailabilityZone',

    'IdempotentParamError'
]

API_VERSION = '2011-01-01'
NAMESPACE = 'http://autoscaling.amazonaws.com/doc/%s/' % (API_VERSION)

REGION_DETAILS = {
    # US East (Northern Virginia) Region
    'us-east-1': {
        'endpoint': 'autoscaling.us-east-1.amazonaws.com',
        'api_name': 'autoscaling_us_east',
        'country': 'USA'
    },
    # US West (Northern California) Region
    'us-west-1': {
        'endpoint': 'autoscaling.us-west-1.amazonaws.com',
        'api_name': 'autoscaling_us_west',
        'country': 'USA'
    },
    # US West (Oregon) Region
    'us-west-2': {
        'endpoint': 'autoscaling.us-west-2.amazonaws.com',
        'api_name': 'autoscaling_us_west_oregon',
        'country': 'USA'
    },
    'eu-west-1': {
        'endpoint': 'autoscaling.eu-west-1.amazonaws.com',
        'api_name': 'autoscaling_eu_west',
        'country': 'Ireland'
    }
}
  

CW_API_VERSION = '2010-08-01'
CW_NAMESPACE = 'http://monitoring.amazonaws.com/doc/%s/' % (CW_API_VERSION)

CW_REGION_DETAILS = {
    # US East (Northern Virginia) Region
    'us-east-1': {
        'endpoint': 'monitoring.us-east-1.amazonaws.com',
        'api_name': 'cloudwatch_us_east',
        'country': 'USA'
    },
    # US West (Northern California) Region
    'us-west-1': {
        'endpoint': 'monitoring.us-west-1.amazonaws.com',
        'api_name': 'cloudwatch_us_west',
        'country': 'USA'
    },
    # US West (Oregon) Region
    'us-west-2': {
        'endpoint': 'monitoring.us-west-2.amazonaws.com',
        'api_name': 'cloudwatch_us_west_oregon',
        'country': 'USA'
    },
    'eu-west-1': {
        'endpoint': 'monitoring.eu-west-1.amazonaws.com',
        'api_name': 'cloudwatch_eu_west',
        'country': 'Ireland'
    }
}

VALID_AUTOSCALE_REGIONS = REGION_DETAILS.keys()
VALID_CW_AUTOSCALE_REGIONS = CW_REGION_DETAILS.keys()

DEFAULT_TIMEOUT = 1200

class CloudWatchConnection(SignedAWSConnection):
    """
    Represents a single connection to the CloudWatch Endpoint.
    """

    version = CW_API_VERSION
    host = CW_REGION_DETAILS['us-east-1']['endpoint']
    responseCls = EC2Response

class CloudWatchDriver(NodeDriver):

    operator_mapping = {ScalingPolicyOperator.GE: 'GreaterThanOrEqualToThreshold',
                 ScalingPolicyOperator.GT: 'GreaterThanThreshold',
                 ScalingPolicyOperator.LE: 'LessThanOrEqualToThreshold',
                 ScalingPolicyOperator.LT: 'LessThanThreshold'}


    connectionCls = CloudWatchConnection

    type = Provider.AWS_CW_AUTOSCALE
    name = 'Amazon EC2'
    website = 'http://aws.amazon.com/ec2/'
    path = '/'

    def __init__(self, key, secret=None, secure=True, host=None, port=None,
                 region='us-east-1', **kwargs):
        if hasattr(self, '_region'):
            region = self._region

        if region not in VALID_CW_AUTOSCALE_REGIONS:
            raise ValueError('Invalid region: %s' % (region))

        details = CW_REGION_DETAILS[region]
        self.region_name = region
        self.api_name = details['api_name']
        self.country = details['country']

        host = host or details['endpoint']

        super(CloudWatchDriver, self).__init__(key=key, secret=secret,
                                            secure=secure, host=host,
                                            port=port, **kwargs)

    def _to_alarms(self, res, xpath):
        return [self._to_alarm(el)
                for el in res.findall(fixxpath(xpath=xpath,
                                                  namespace=CW_NAMESPACE))]

    def _to_alarm(self, element):

        print 'Turn alarm=%s' % element

        extra = {}

        extra['name'] = findtext(element=element, xpath='AlarmName',
                             namespace=CW_NAMESPACE)
        extra['Namespace'] = findtext(element=element, xpath='Namespace',
                             namespace=CW_NAMESPACE)
        
        metric_name = findtext(element=element, xpath='MetricName',
                             namespace=NAMESPACE)
        op = findtext(element=element, xpath='ComparisonOperator',
                             namespace=CW_NAMESPACE)
        operator = find(self.operator_mapping,
                        lambda e: self.operator_mapping[e] == op)
        if not operator:
            raise Exception('Illegal operator value [op=%(op)s]' \
                            % {'op': op})

        period = findtext(element=element, xpath='Period',
                             namespace=CW_NAMESPACE)
        threshold = findtext(element=element, xpath='Threshold',
                             namespace=CW_NAMESPACE)

        return Alarm(id=None, metric_name=metric_name, operator=operator,
                                period=period, threshold=threshold,
                                driver=self.connection.driver, extra=extra)

    def create_alarm(self, policy_id, **kwargs):

        data = {}
        data['AlarmActions.member.1'] = policy_id
        data['AlarmName'] = kwargs['ex_name']
        data['Namespace'] = kwargs['ex_namespace']
        data['Statistic'] = 'Average'
        data['MetricName'] = kwargs['metric_name']
        data['ComparisonOperator'] = \
                           self.operator_mapping[kwargs['operator']]
        data['EvaluationPeriods'] = 1
        data['Period'] = kwargs['period']
        data['Threshold'] = kwargs['threshold']
        data.update({'Action': 'PutMetricAlarm'})

        print 'Creating alarm %(alarm)s ...' % {'alarm': data}
        self.connection.request(self.path, params=data).object
        print 'Successfully created alarm'

        data = {}
        data['Action'] = 'DescribeAlarms'
        data['AlarmNames.member.1'] = kwargs['ex_name']
        res = self.connection.request(self.path, params=data).object
        alarms = self._to_alarms(res, 'DescribeAlarmsResult/MetricAlarms/member')

        return alarms[0]

class AutoScaleResponse(AWSGenericResponse):

    namespace = NAMESPACE
    xpath = 'Error'
    exceptions = {
        'AlreadyExists': ResourceExistsError
    }

class AutoScaleConnection(EC2Connection):
    """
    Represents a single connection to the EC2 Endpoint.
    """
 
    version = API_VERSION
    host = REGION_DETAILS['us-east-1']['endpoint']
    #responseCls = EC2Response
    responseCls = AutoScaleResponse


class AutoScaleDriver(NodeDriver):

    connectionCls = AutoScaleConnection

    type = Provider.AWS_AUTOSCALE
    name = 'Amazon EC2'
    website = 'http://aws.amazon.com/ec2/'
    path = '/'
    
    scaleType_mapping = {ScalingPolicyType.CHANGE_IN_CAPACITY: 'ChangeInCapacity',
                         ScalingPolicyType.EXACT_CAPACITY: 'ExactCapacity',
                         ScalingPolicyType.PERCENT_CHANGE_IN_CAPACITY: 'PercentChangeInCapacity'}


    def __init__(self, key, secret=None, secure=True, host=None, port=None,
                 region='us-east-1', **kwargs):
        if hasattr(self, '_region'):
            region = self._region

        if region not in VALID_AUTOSCALE_REGIONS:
            raise ValueError('Invalid region: %s' % (region))

        details = REGION_DETAILS[region]
        self.region_name = region
        self.api_name = details['api_name']
        self.country = details['country']

        host = host or details['endpoint']

        super(AutoScaleDriver, self).__init__(key=key, secret=secret,
                                            secure=secure, host=host,
                                            port=port, **kwargs)


    def _to_scaling_groups(self, res, xpath):
        return [self._to_scaling_group(el)
                for el in res.findall(fixxpath(xpath=xpath,
                                                  namespace=NAMESPACE))]


    def _to_scaling_group(self, element):

        print 'Turn group=%s' % element

        group_id = findtext(element=element, xpath='AutoScalingGroupARN',
                               namespace=NAMESPACE)
        name = findtext(element=element, xpath='AutoScalingGroupName',
                             namespace=NAMESPACE)
        cooldown = findtext(element=element, xpath='DefaultCooldown',
                             namespace=NAMESPACE)
        min_size = findtext(element=element, xpath='MinSize',
                             namespace=NAMESPACE)
        max_size = findtext(element=element, xpath='MaxSize',
                             namespace=NAMESPACE)
        
        extra = {}
        extra['id'] = name
        print 'REGION: %s' % self.region_name
        extra['region'] = self.region_name

        extra['launch_configuration_name'] =\
                             findtext(element=element, xpath='LaunchConfigurationName',
                             namespace=NAMESPACE)
        
        return AutoScalingGroup(id=group_id, name=name, cooldown=cooldown,
                                min_size=min_size, max_size=max_size,
                                driver=self.connection.driver, extra=extra)

    def get_auto_scale_group(self, group_name):
        
        data = {}
        data['Action'] = 'DescribeAutoScalingGroups'
        data['AutoScalingGroupNames.member.1'] = group_name
        
        try:
            res = self.connection.request(self.path, params=data).object
            groups = self._to_scaling_groups(res, 'DescribeAutoScalingGroupsResult/AutoScalingGroups/member')

            return groups[0]
        except IndexError:
            raise ResourceNotFoundError(value='Group: %s not found' % \
                                        group_name, driver=self)

    def list_auto_scale_groups(self):

        data = {}
        data['Action'] = 'DescribeAutoScalingGroups'

        res = self.connection.request(self.path, params=data).object
        return self._to_scaling_groups(res, 'DescribeAutoScalingGroupsResult/AutoScalingGroups/member')

    def create_auto_scale_group(self, **kwargs):

        import base64

        template = {
        'LaunchConfigurationName': kwargs['ex_launch_configuration_name'],
        'InstanceType': kwargs['ex_flavor'],
        'ImageId': kwargs['image'].id,
        #'KeyName': kwargs['key_name'],
        'UserData': base64.b64encode(kwargs['ex_user_data'])
        }
  
        data = {}
        data['AutoScalingGroupName'] = kwargs['name']
        data['LaunchConfigurationName'] = template['LaunchConfigurationName']
        data['MaxSize'] = kwargs['max_size']
        data['MinSize'] = kwargs['min_size']
        data['DefaultCooldown'] = kwargs['cooldown']
        data['AvailabilityZones.member.1'] = kwargs['ex_avail_zone']

        # Have instance names to be based on group name
        data['Tags.member.1.Key'] = 'Name'
        data['Tags.member.1.Value'] = kwargs['ex_instance_name']
        data['Tags.member.1.PropagateAtLaunch'] = 'true'
        
         
        configuration = template
        configuration.update({'Action': 'CreateLaunchConfiguration'})
        self.connection.request(self.path, params=configuration).object
        # If we are here then status=200 which is OK
        print 'Successfully created launch configuration'
        
        data.update({'Action': 'CreateAutoScalingGroup'})
        self.connection.request(self.path, params=data).object
        print 'Successfully created auto scaling group'
        
        data = {}
        data['Action'] = 'DescribeAutoScalingGroups'
        data['AutoScalingGroupNames.member.1'] = kwargs['name']
        
        res = self.connection.request(self.path, params=data).object
        groups = self._to_scaling_groups(res, 'DescribeAutoScalingGroupsResult/AutoScalingGroups/member')

        return groups[0]

    def _to_scaling_policies(self, res, xpath):
        return [self._to_scaling_policy(el)
                for el in res.findall(fixxpath(xpath=xpath,
                                                  namespace=NAMESPACE))]

    def _to_scaling_policy(self, element):

        print 'Turn policy=%s' % element

        policy_id = findtext(element=element, xpath='PolicyARN',
                               namespace=NAMESPACE)
        name = findtext(element=element, xpath='PolicyName',
                             namespace=NAMESPACE)
        adj_type = findtext(element=element, xpath='AdjustmentType',
                             namespace=NAMESPACE)
        adjustment_type = find(self.scaleType_mapping,
                            lambda e: self.scaleType_mapping[e] == adj_type)
        if not adjustment_type:
            raise Exception('Illegal adjustment_type value [adj_type=%(adj_type)s]' \
                            % {'adj_type': adj_type})

        scaling_adjustment = findtext(element=element, xpath='ScalingAdjustment',
                             namespace=NAMESPACE)
        
        return ScalingPolicy(id=policy_id, name=name, adjustment_type=adjustment_type,
                                scaling_adjustment=scaling_adjustment,
                                driver=self.connection.driver)


    def create_policy(self, group_name, **kwargs):

        data = {}        
        data['AutoScalingGroupName'] = group_name
        data['PolicyName'] = kwargs['name']
        data['AdjustmentType'] = \
                           self.scaleType_mapping[kwargs['adjustment_type']]
        data['ScalingAdjustment'] = kwargs['scaling_adjustment']
        data.update({'Action': 'PutScalingPolicy'})

        print 'Creating policy with an action %(policy)s ...' % {'policy': data}
        self.connection.request(self.path, params=data).object
        # If we are here then status=200 which is OK
        print 'Successfully created policy'

        data = {}
        data['Action'] = 'DescribePolicies'
        data['AutoScalingGroupName'] = group_name
        data['PolicyNames.member.1'] = kwargs['name']
        res = self.connection.request(self.path, params=data).object
        policies = self._to_scaling_policies(res, 'DescribePoliciesResult/ScalingPolicies/member')
        
        return policies[0]

    def delete_auto_scale_group(self, group):
        """Delete group completely  with all of its resources"""

        def _wait_for_deletion(group_id):
            # 5 seconds
            POLL_INTERVAL = 5
        
            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                try:
                    self.get_auto_scale_group(group_id)
                    print 'Group exists. Waiting....'
                    time.sleep(POLL_INTERVAL)
                except ResourceNotFoundError:
                    # did not find group
                    completed = True
            if not completed:
                raise LibcloudError('Operation did not complete in %s seconds' %
                                    (DEFAULT_TIMEOUT))
        
        data = {}
        data['AutoScalingGroupName'] = group.name
        data.update({'Action': 'DeleteAutoScalingGroup',
                     'ForceDelete': 'true'})
        self.connection.request(self.path, params=data).object

        _wait_for_deletion(group.name)        
        
        data = {}
        data['LaunchConfigurationName'] = \
                      group.extra['launch_configuration_name']
        data.update({'Action': 'DeleteLaunchConfiguration'})
        self.connection.request(self.path, params=data).object
        
        return True


class AutoScaleUSWestDriver(AutoScaleDriver):
    """
    Driver class for AutoScale in the Western US Region
    """
    name = 'Amazon AutoScale (us-west-1)'
    _region = 'us-west-1'

class AutoScaleUSWestOregonDriver(AutoScaleDriver):
    """
    Driver class for AutoScale in the US West Oregon region.
    """
    name = 'Amazon AutoScale (us-west-2)'
    _region = 'us-west-2'

class AutoScaleEuropeDriver(AutoScaleDriver):
    """
    Driver class for AutoScale in the Europe Region
    """
    name = 'Amazon AutoScale (eu-central-1)'
    _region = 'eu-west-1'


class CloudWatchUSWestDriver(CloudWatchDriver):
    """
    Driver class for AutoScale in the Western US Region
    """
    name = 'Amazon CloudWatch (us-west-1)'
    _region = 'us-west-1'

class CloudWatchUSWestOregonDriver(CloudWatchDriver):
    """
    Driver class for AutoScale in the US West Oregon region.
    """
    name = 'Amazon CloudWatch (us-west-2)'
    _region = 'us-west-2'

class CloudWatchEuropeDriver(CloudWatchDriver):
    """
    Driver class for AutoScale in the Europe Region
    """
    name = 'Amazon CloudWatch (eu-central-1)'
    _region = 'eu-west-1'


if __name__ == '__main__':

    import libcloud
    from libcloud.compute.providers import get_driver
    libcloud.security.VERIFY_SSL_CERT = False

    cls = get_driver(Provider.AWS_AUTOSCALE_US_WEST_OREGON)
    driver = cls('AKIAIGF5OEY25FMKT55A', 'sqIzwlNlQ0CNQKLjHvQ735RZcgNKkLxU7ex6r+5H')

    cw_cls = get_driver(Provider.AWS_CW_AUTOSCALE_US_WEST_OREGON)
    cw_driver = cw_cls('AKIAIGF5OEY25FMKT55A', 'sqIzwlNlQ0CNQKLjHvQ735RZcgNKkLxU7ex6r+5H')
    driver.get_auto_scale_group('foo')
