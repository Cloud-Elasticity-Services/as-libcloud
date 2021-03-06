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
import base64
import time

from libcloud.utils.py3 import b

from libcloud.utils.misc import get_new_obj, reverse_dict
from libcloud.utils.xml import fixxpath, findtext, findall
from libcloud.common.aws import AWSGenericResponse,\
    AWSObjectDoesntExist
from libcloud.common.aws import DEFAULT_SIGNATURE_VERSION
from libcloud.common.types import LibcloudError
from libcloud.autoscale.providers import Provider
from libcloud.autoscale.base import AutoScaleDriver, AutoScaleGroup,\
    AutoScalePolicy
from libcloud.compute.drivers.ec2 import EC2NodeDriver, EC2Connection
from libcloud.autoscale.types import AutoScaleAdjustmentType, \
    AutoScaleTerminationPolicy

AUTOSCALE_API_VERSION = '2011-01-01'
AUTOSCALE_NAMESPACE = 'http://autoscaling.amazonaws.com/doc/%s/' % \
    (AUTOSCALE_API_VERSION)

AUTOSCALE_REGION_DETAILS = {
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
    },
    # EU (Frankfurt)
    'eu-central-1': {
        'endpoint': 'autoscaling.eu-central-1.amazonaws.com',
        'api_name': 'autoscaling_eu_central',
        'country': 'Germany'
    },
    # Asia Pacific (Singapore)
    'ap-southeast-1': {
        'endpoint': 'autoscaling.ap-southeast-1.amazonaws.com',
        'api_name': 'autoscaling_ap_southeast',
        'country': 'Singapore'
    },
    # Asia Pacific (Sydney)
    'ap-southeast-2': {
        'endpoint': 'autoscaling.ap-southeast-2.amazonaws.com',
        'api_name': 'autoscaling_ap_southeast_2',
        'country': 'Australia'
    },
    # Asia Pacific (Tokyo)
    'ap-northeast-1': {
        'endpoint': 'autoscaling.ap-northeast-1.amazonaws.com',
        'api_name': 'autoscaling_ap_northeast',
        'country': 'Japan'
    },
    # South America (Sao Paulo)
    'sa-east-1': {
        'endpoint': 'autoscaling.sa-east-1.amazonaws.com',
        'api_name': 'autoscaling_sa_east',
        'country': 'Brazil'
    }
}


VALID_AUTOSCALE_REGIONS = AUTOSCALE_REGION_DETAILS.keys()


class AutoScaleResponse(AWSGenericResponse):

    namespace = AUTOSCALE_NAMESPACE
    xpath = 'Error'
#     exceptions = {
#         'AlreadyExists': ResourceExistsError
#     }


class AutoScaleConnection(EC2Connection):
    """
    Represents a single connection to the AutoScaling Endpoint.
    """

    version = AUTOSCALE_API_VERSION
    host = AUTOSCALE_REGION_DETAILS['us-east-1']['endpoint']

    responseCls = AutoScaleResponse


class AWSAutoScaleDriver(AutoScaleDriver):

    connectionCls = AutoScaleConnection

    type = Provider.AWS_AUTOSCALE
    name = 'Amazon EC2'
    website = 'http://aws.amazon.com/ec2/'
    path = '/'
    signature_version = DEFAULT_SIGNATURE_VERSION

    _VALUE_TO_SCALE_ADJUSTMENT_TYPE_MAP = {
        'ChangeInCapacity': AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
        'ExactCapacity': AutoScaleAdjustmentType.EXACT_CAPACITY,
        'PercentChangeInCapacity': AutoScaleAdjustmentType.
        PERCENT_CHANGE_IN_CAPACITY
    }

    _SCALE_ADJUSTMENT_TYPE_TO_VALUE_MAP = reverse_dict(
        _VALUE_TO_SCALE_ADJUSTMENT_TYPE_MAP)

    _VALUE_TO_TERMINATION_POLICY_MAP = {
        'OldestInstance': AutoScaleTerminationPolicy.OLDEST_INSTANCE,
        'NewestInstance': AutoScaleTerminationPolicy.NEWEST_INSTANCE,
        'ClosestToNextInstanceHour': AutoScaleTerminationPolicy.
        CLOSEST_TO_NEXT_CHARGE,
        'Default': AutoScaleTerminationPolicy.DEFAULT
    }

    _TERMINATION_POLICY_TO_VALUE_MAP = reverse_dict(
        _VALUE_TO_TERMINATION_POLICY_MAP)

    def __init__(self, key, secret=None, secure=True, host=None, port=None,
                 region='us-east-1', **kwargs):
        if hasattr(self, '_region'):
            region = self._region

        if region not in VALID_AUTOSCALE_REGIONS:
            raise ValueError('Invalid region: %s' % (region))

        details = AUTOSCALE_REGION_DETAILS[region]
        self.region_name = region
        self.api_name = details['api_name']
        self.country = details['country']

        host = host or details['endpoint']

        self.signature_version = details.pop('signature_version',
                                             DEFAULT_SIGNATURE_VERSION)

        if kwargs.get('ec2_driver'):
            self.ec2 = kwargs['ec2_driver']
        else:
            self.ec2 = EC2NodeDriver(key, secret=secret, region=region,
                                     **kwargs)

        super(AWSAutoScaleDriver, self).__init__(key=key, secret=secret,
                                                 secure=secure, host=host,
                                                 port=port, **kwargs)

    def create_auto_scale_group(
            self, group_name, min_size, max_size, cooldown,
            termination_policies, balancer=None, ex_availability_zones=None,
            **kwargs):
        """
        Create a new auto scale group.

        @inherits: :class:`AutoScaleDriver.create_auto_scale_group`

        :keyword    ex_availability_zones: The availability zones of the group.
        :type       ex_availability_zones: ``list`` of ``str``

        :keyword    ex_launch_configuration_name: Launch configuration name.
        :type       ex_launch_configuration_name: ``str``

        :keyword    ex_keyname: The name of the key pair
        :type       ex_keyname: ``str``

        :keyword    ex_iamprofile: Name or ARN of IAM profile
        :type       ex_iamprofile: ``str``

        :keyword    ex_userdata: User data to be injected to group members.
        :type       ex_userdata: ``str``

        :return: The newly created scale group.
        :rtype: :class:`.AutoScaleGroup`
        """
        template = self._to_virtual_guest_template(**kwargs)

        data = {}
        data['AutoScalingGroupName'] = group_name
        data['LaunchConfigurationName'] = template['LaunchConfigurationName']
        data['MinSize'] = min_size
        data['MaxSize'] = max_size

        data['DefaultCooldown'] = cooldown

        if ex_availability_zones is None:
            ex_availability_zones = ['a']

        for i, z in enumerate(ex_availability_zones):
            zone = ''.join((self.region_name, z))
            data['AvailabilityZones.member.%d' % (i + 1)] = zone

        if 'name' in kwargs:
            data['Tags.member.1.Key'] = 'Name'
            data['Tags.member.1.Value'] = kwargs['name']
            data['Tags.member.1.PropagateAtLaunch'] = 'true'

        if termination_policies:
            for p in range(len(termination_policies)):
                data['TerminationPolicies.member.%d' % (p + 1,)] =\
                    self._termination_policy_to_value(termination_policies[p])
        if balancer:
            data['LoadBalancerNames.member.1'] = balancer.name

        template.update({'Action': 'CreateLaunchConfiguration'})
        self.connection.request(self.path, params=template).object
        # If we are here then status=200 which is OK
        try:
            data.update({'Action': 'CreateAutoScalingGroup'})
            self.connection.request(self.path, params=data).object
        except Exception as e:
            d = {}
            d['Action'] = 'DeleteLaunchConfiguration'
            d['LaunchConfigurationName'] = data['LaunchConfigurationName']
            try:
                self.connection.request(self.path, params=d)
            except:
                pass
            raise e

        data = {}
        data['Action'] = 'DescribeAutoScalingGroups'
        data['AutoScalingGroupNames.member.1'] = group_name

        res = self.connection.request(self.path, params=data).object
        groups = self._to_autoscale_groups(res,
                                           'DescribeAutoScalingGroupsResult'
                                           '/AutoScalingGroups/member')
        return groups[0]

    def update_auto_scale_group(self, group, min_size=None, max_size=None):
        data = {}

        data['Action'] = 'UpdateAutoScalingGroup'
        data['AutoScalingGroupName'] = group.name
        if min_size:
            data['MinSize'] = min_size
        if max_size:
            data['MaxSize'] = max_size
        # per AWS documentation, group is set with new settings after call
        # completes
        self.connection.request(self.path, params=data)
        updated_group = get_new_obj(obj=group, klass=AutoScaleGroup,
                                    attributes={'min_size': min_size,
                                                'max_size': max_size})
        return updated_group

    def list_auto_scale_groups(self):

        data = {}
        data['Action'] = 'DescribeAutoScalingGroups'

        res = self.connection.request(self.path, params=data).object
        return self._to_autoscale_groups(res,
                                         'DescribeAutoScalingGroupsResult/'
                                         'AutoScalingGroups/member')

    def list_auto_scale_group_members(self, group):
        return self.ec2.list_nodes(
            ex_filters={'tag:aws:autoscaling:groupName': group.name})

    def create_auto_scale_policy(self, group, name, adjustment_type,
                                 scaling_adjustment):
        """
        Create an auto scale policy for the given group.

        @inherits: :class:`NodeDriver.create_auto_scale_policy`

        :param group: Group object.
        :type group: :class:`.AutoScaleGroup`

        :param name: Policy name.
        :type name: ``str``

        :param adjustment_type: The adjustment type.
        :type adjustment_type: value within :class:`AutoScaleAdjustmentType`

        :param scaling_adjustment: The number of instances by which to scale.
        :type scaling_adjustment: ``int``

        :return: The newly created policy.
        :rtype: :class:`.AutoScalePolicy`
        """

        data = {}
        data['AutoScalingGroupName'] = group.name
        data['PolicyName'] = name
        data['AdjustmentType'] = \
            self._scale_adjustment_to_value(adjustment_type)

        data['ScalingAdjustment'] = scaling_adjustment
        data.update({'Action': 'PutScalingPolicy'})

        self.connection.request(self.path, params=data).object
        # If we are here then status=200 which is OK

        data = {}
        data['Action'] = 'DescribePolicies'
        data['AutoScalingGroupName'] = group.name
        data['PolicyNames.member.1'] = name
        res = self.connection.request(self.path, params=data).object
        policies = self._to_autoscale_policies(res, 'DescribePoliciesResult'
                                               '/ScalingPolicies/member')

        return policies[0]

    def list_auto_scale_policies(self, group):
        data = {}
        data['Action'] = 'DescribePolicies'
        data['AutoScalingGroupName'] = group.name
        res = self.connection.request(self.path, params=data).object
        return self._to_autoscale_policies(res, 'DescribePoliciesResult'
                                           '/ScalingPolicies/member')

    def delete_auto_scale_policy(self, policy):
        data = {}
        data['Action'] = 'DeletePolicy'
        # policy ARN.
        data['PolicyName'] = policy.id
        self.connection.request(self.path, params=data)
        return True

    def delete_auto_scale_group(self, group):
        DEFAULT_TIMEOUT = 1200

        def _wait_for_deletion(group_name):
            # 5 seconds
            POLL_INTERVAL = 5

            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                try:
                    self._get_auto_scale_group(group_name)
                    time.sleep(POLL_INTERVAL)
                except AWSObjectDoesntExist:
                    # did not find group
                    completed = True
            if not completed:
                raise LibcloudError('Operation did not complete in %s seconds'
                                    % (DEFAULT_TIMEOUT))

        # we need to manually remove launch_configuration as well.
        group = self._get_auto_scale_group(group.name)
        lc_name = group.extra['launch_configuration_name']

        data = {}
        data['AutoScalingGroupName'] = group.name
        data.update({'Action': 'DeleteAutoScalingGroup',
                     'ForceDelete': 'true'})
        self.connection.request(self.path, params=data).object

        _wait_for_deletion(group.name)

        data = {}
        data['LaunchConfigurationName'] = lc_name
        data.update({'Action': 'DeleteLaunchConfiguration'})
        self.connection.request(self.path, params=data).object

        return True

    def _get_auto_scale_group(self, group_name):
        data = {}
        data['Action'] = 'DescribeAutoScalingGroups'
        data['AutoScalingGroupNames.member.1'] = group_name

        try:
            res = self.connection.request(self.path, params=data).object
            groups = self._to_autoscale_groups(
                res, 'DescribeAutoScalingGroupsResult'
                '/AutoScalingGroups/member')

            return groups[0]
        except IndexError:
            raise AWSObjectDoesntExist(value='Group: %s not found' %
                                       group_name, driver=self)

    def _to_autoscale_groups(self, res, xpath):
        return [self._to_autoscale_group(el)
                for el in res.findall(fixxpath(xpath=xpath,
                                               namespace=AUTOSCALE_NAMESPACE))]

    def _to_autoscale_group(self, element):

        group_id = findtext(element=element, xpath='AutoScalingGroupARN',
                            namespace=AUTOSCALE_NAMESPACE)
        name = findtext(element=element, xpath='AutoScalingGroupName',
                        namespace=AUTOSCALE_NAMESPACE)
        cooldown = findtext(element=element, xpath='DefaultCooldown',
                            namespace=AUTOSCALE_NAMESPACE)
        min_size = findtext(element=element, xpath='MinSize',
                            namespace=AUTOSCALE_NAMESPACE)
        max_size = findtext(element=element, xpath='MaxSize',
                            namespace=AUTOSCALE_NAMESPACE)
        region = self.region_name
        termination_policies = self._get_termination_policies(element)
        availability_zones = self._get_availability_zones(element)

        extra = {}
        extra['balancer_names'] = self._get_balancer_names(element)
        extra['availability_zones'] = availability_zones
        extra['launch_configuration_name'] =\
            findtext(element=element, xpath='LaunchConfigurationName',
                     namespace=AUTOSCALE_NAMESPACE)

        return AutoScaleGroup(id=group_id, name=name, cooldown=int(cooldown),
                              min_size=int(min_size), max_size=int(max_size),
                              region=region,
                              termination_policies=termination_policies,
                              driver=self.connection.driver, extra=extra)

    def _to_autoscale_policies(self, res, xpath):
        return [self._to_autoscale_policy(el)
                for el in res.findall(fixxpath(xpath=xpath,
                                               namespace=AUTOSCALE_NAMESPACE))]

    def _to_autoscale_policy(self, element):

        policy_id = findtext(element=element, xpath='PolicyARN',
                             namespace=AUTOSCALE_NAMESPACE)
        name = findtext(element=element, xpath='PolicyName',
                        namespace=AUTOSCALE_NAMESPACE)
        adj_type = findtext(element=element, xpath='AdjustmentType',
                            namespace=AUTOSCALE_NAMESPACE)
        adjustment_type = self._value_to_scale_adjustment(adj_type)

        scaling_adjustment = findtext(element=element,
                                      xpath='ScalingAdjustment',
                                      namespace=AUTOSCALE_NAMESPACE)

        return AutoScalePolicy(id=policy_id, name=name,
                               adjustment_type=adjustment_type,
                               scaling_adjustment=int(scaling_adjustment),
                               driver=self.connection.driver)

    def _get_termination_policies(self, element):
        """
        Parse termination policies from the provided element and return a
        list of these.

        :rtype: ``list`` of ``str``
        """
        termination_policies = []
        for item in findall(element=element, xpath='TerminationPolicies',
                            namespace=AUTOSCALE_NAMESPACE):

            t_p = findtext(element=item, xpath='member',
                           namespace=AUTOSCALE_NAMESPACE)
            if t_p is not None:
                termination_policies.append(
                    self._value_to_termination_policy(t_p))

        return termination_policies

    def _get_balancer_names(self, element):
        """
        Parse load balancer names from the provided element and return a
        list of therse.

        :rtype: ``list`` of ``str``
        """
        balancer_names = []
        for item in findall(element=element, xpath='LoadBalancerNames',
                            namespace=AUTOSCALE_NAMESPACE):
            b_n = findtext(element=item, xpath='member',
                           namespace=AUTOSCALE_NAMESPACE)
            if b_n is not None:
                balancer_names.append(b_n)

        return balancer_names

    def _get_availability_zones(self, element):
        """
        Parse availability zones from the provided element and return a
        list of these.

        :rtype: ``list`` of ``str``
        """
        availability_zones = []
        for item in findall(element=element, xpath='AvailabilityZones/member',
                            namespace=AUTOSCALE_NAMESPACE):
            if item.text is not None:
                availability_zones.append(item.text)

        return availability_zones

    def _to_virtual_guest_template(self, **attrs):
        """
        Return launch configuration template based on supplied
        attributes.
        """
        template = {}

        image = attrs['image']
        size = attrs['size']
        name = attrs['name']

        template['ImageId'] = image.id
        template['InstanceType'] = size.id

        if 'ex_launch_configuration_name' in attrs:
            template['LaunchConfigurationName'] = \
                attrs['ex_launch_configuration_name']
        else:
            template['LaunchConfigurationName'] = name

        if 'ex_keyname' in attrs:
            template['KeyName'] = attrs['ex_keyname']

        if 'ex_iamprofile' in attrs:
            template['IamInstanceProfile'] = attrs['ex_iamprofile']

        if 'ex_userdata' in attrs:
            template['UserData'] = base64.b64encode(b(attrs['ex_userdata']))\
                .decode('utf-8')

        return template
