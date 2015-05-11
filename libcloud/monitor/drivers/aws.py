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
from libcloud.common.aws import SignedAWSConnection
from libcloud.compute.drivers.ec2 import EC2Response

from libcloud.monitor.base import AutoScaleAlarm, MonitorDriver
from libcloud.monitor.providers import Provider
from libcloud.monitor.types import AutoScaleOperator, AutoScaleMetric

from libcloud.utils.misc import reverse_dict
from libcloud.utils.xml import fixxpath, findtext

CLOUDWATCH_API_VERSION = '2010-08-01'
CLOUDWATCH_NAMESPACE = 'http://monitoring.amazonaws.com/doc/%s/' %\
                       (CLOUDWATCH_API_VERSION)

CLOUDWATCH_REGION_DETAILS = {
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
    # EU (Ireland)
    'eu-west-1': {
        'endpoint': 'monitoring.eu-west-1.amazonaws.com',
        'api_name': 'cloudwatch_eu_west',
        'country': 'Ireland'
    },
    # EU (Frankfurt)
    'eu-central-1': {
        'endpoint': 'monitoring.eu-central-1.amazonaws.com',
        'api_name': 'cloudwatch_eu_central',
        'country': 'Germany'
    },
    # Asia Pacific (Singapore)
    'ap-southeast-1': {
        'endpoint': 'monitoring.ap-southeast-1.amazonaws.com',
        'api_name': 'cloudwatch_ap_southeast',
        'country': 'Singapore'
    },
    # Asia Pacific (Sydney)
    'ap-southeast-2': {
        'endpoint': 'monitoring.ap-southeast-2.amazonaws.com',
        'api_name': 'cloudwatch_ap_southeast_2',
        'country': 'Australia'
    },
    # Asia Pacific (Tokyo)
    'ap-northeast-1': {
        'endpoint': 'monitoring.ap-northeast-1.amazonaws.com',
        'api_name': 'cloudwatch_ap_northeast',
        'country': 'Japan'
    },
    # South America (Sao Paulo)
    'sa-east-1': {
        'endpoint': 'monitoring.sa-east-1.amazonaws.com',
        'api_name': 'cloudwatch_sa_east',
        'country': 'Japan'
    }
}

VALID_CLOUDWATCH_REGIONS = CLOUDWATCH_REGION_DETAILS.keys()


class CloudWatchConnection(SignedAWSConnection):
    """
    Represents a single connection to the CloudWatch Endpoint.
    """

    version = CLOUDWATCH_API_VERSION
    host = CLOUDWATCH_REGION_DETAILS['us-east-1']['endpoint']
    responseCls = EC2Response


class AWSCloudWatchDriver(MonitorDriver):

    _VALUE_TO_SCALE_OPERATOR_TYPE_MAP = {
        'GreaterThanOrEqualToThreshold': AutoScaleOperator.GE,
        'GreaterThanThreshold': AutoScaleOperator.GT,
        'LessThanOrEqualToThreshold': AutoScaleOperator.LE,
        'LessThanThreshold': AutoScaleOperator.LT,

    }

    _SCALE_OPERATOR_TYPE_TO_VALUE_MAP = reverse_dict(
        _VALUE_TO_SCALE_OPERATOR_TYPE_MAP)

    _VALUE_TO_METRIC_MAP = {
        'CPUUtilization': AutoScaleMetric.CPU_UTIL
    }

    _METRIC_TO_VALUE_MAP = reverse_dict(_VALUE_TO_METRIC_MAP)

    connectionCls = CloudWatchConnection

    type = Provider.AWS_CLOUDWATCH
    name = 'Amazon CloudWatch'
    website = 'http://aws.amazon.com/ec2/'
    path = '/'

    def __init__(self, key, secret=None, secure=True, host=None, port=None,
                 region='us-east-1', **kwargs):
        if hasattr(self, '_region'):
            region = self._region

        if region not in VALID_CLOUDWATCH_REGIONS:
            raise ValueError('Invalid region: %s' % (region))

        details = CLOUDWATCH_REGION_DETAILS[region]
        self.region_name = region
        self.api_name = details['api_name']
        self.country = details['country']

        host = host or details['endpoint']

        super(AWSCloudWatchDriver, self).__init__(key=key, secret=secret,
                                                  secure=secure, host=host,
                                                  port=port, **kwargs)

    def create_auto_scale_alarm(self, name, action_ids, metric_name, operator,
                                threshold, period, **kwargs):
        """
        @inherits: :class:`NodeDriver.create_auto_scale_alarm`

        :keyword    ex_namespace: The namespace for the alarm's associated
                                  metric.
        :type       ex_namespace: ``str``
        """
        data = {}
        data['AlarmActions.member.1'] = action_ids[0]
        data['AlarmName'] = name
        if 'ex_namespace' not in kwargs:
            kwargs['ex_namespace'] = 'AWS/EC2'
        data['Namespace'] = kwargs['ex_namespace']
        data['Statistic'] = 'Average'

        data['MetricName'] = self._metric_to_value(metric_name)

        data['ComparisonOperator'] = \
            self._operator_type_to_value(operator)

        data['EvaluationPeriods'] = 1
        data['Threshold'] = threshold
        data['Period'] = period
        data.update({'Action': 'PutMetricAlarm'})

        self.connection.request(self.path, params=data).object

        data = {}
        data['Action'] = 'DescribeAlarms'
        data['AlarmNames.member.1'] = name or 'example_alarm'
        res = self.connection.request(self.path, params=data).object
        alarms = self._to_autoscale_alarms(
            res, 'DescribeAlarmsResult/MetricAlarms/member')
        return alarms[0]

    def list_auto_scale_alarms(self, action_ids):
        data = {}
        data['Action'] = 'DescribeAlarms'
        res = self.connection.request(self.path, params=data).object
        alarms = self._to_autoscale_alarms(
            res, 'DescribeAlarmsResult/MetricAlarms/member')

        # return only alarms for this action id
        return [a for a in alarms if a.extra.get(
            'ex_action_ids')[0] == action_ids[0]]

    def delete_auto_scale_alarm(self, alarm):
        data = {}
        data['Action'] = 'DeleteAlarms'
        data['AlarmNames.member.1'] = alarm.name
        self.connection.request(self.path, params=data)
        return True

    def _to_autoscale_alarms(self, res, xpath):
        return [self._to_autoscale_alarm(el)
                for el in res.findall(fixxpath(xpath=xpath,
                                      namespace=CLOUDWATCH_NAMESPACE))]

    def _to_autoscale_alarm(self, element):

        extra = {}

        name = findtext(element=element, xpath='AlarmName',
                        namespace=CLOUDWATCH_NAMESPACE)

        alarm_id = findtext(element=element, xpath='AlarmArn',
                            namespace=CLOUDWATCH_NAMESPACE)

        extra['ex_namespace'] = findtext(element=element, xpath='Namespace',
                                         namespace=CLOUDWATCH_NAMESPACE)

        metric_name = findtext(element=element, xpath='MetricName',
                               namespace=CLOUDWATCH_NAMESPACE)
        op = findtext(element=element, xpath='ComparisonOperator',
                      namespace=CLOUDWATCH_NAMESPACE)
        metric = self._value_to_metric(metric_name)
        operator = self._value_to_operator_type(op)

        period = findtext(element=element, xpath='Period',
                          namespace=CLOUDWATCH_NAMESPACE)

        threshold = findtext(element=element, xpath='Threshold',
                             namespace=CLOUDWATCH_NAMESPACE)

        def _to_alarm_action(element):
            """Internal method to return action ARN for this alarm.
            It is assumed that alarm is associated with a single action
            ARN.
            """
            return findtext(element=element, xpath='AlarmActions/member',
                            namespace=CLOUDWATCH_NAMESPACE)

        actions_id = _to_alarm_action(element)
        extra['ex_action_ids'] = [actions_id]

        return AutoScaleAlarm(id=alarm_id, name=name, metric_name=metric,
                              operator=operator, period=int(period),
                              threshold=int(float(threshold)),
                              driver=self.connection.driver, extra=extra)
