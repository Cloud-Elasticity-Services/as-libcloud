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

from libcloud.monitor.base import MonitorDriver, AutoScaleAlarm
from libcloud.monitor.types import Provider, AutoScaleMetric, \
    AutoScaleOperator
from libcloud.common.types import LibcloudError

from libcloud.common.openstack_heat import OpenStackHeatConnection, \
    OpenStackHeatResponse
from libcloud.common.openstack import OpenStackDriverMixin

from libcloud.utils.misc import find, iso_to_datetime, reverse_dict

__all__ = [
    'MonitorResponse',
    'MonitorConnection',
    'OpenStackAutoScaleMonitorDriver',
]

DEFAULT_API_VERSION = '1.0'


class MonitorResponse(OpenStackHeatResponse):
    def __init__(self, *args, **kwargs):
        # done because of a circular reference from
        # NodeDriver -> Connection -> Response
        self.node_driver = OpenStackAutoScaleMonitorDriver
        super(MonitorResponse, self).__init__(*args, **kwargs)


class MonitorConnection(OpenStackHeatConnection):
    responseCls = MonitorResponse


class OpenStackAutoScaleMonitorDriver(MonitorDriver, OpenStackDriverMixin):
    """
    OpenStack driver for auto-scale related monitoring such as:
    auto-scale alarms.

    Auto scale monitoring support (autoscale alarms) done through heat.
    API based on v1.0 (current):
    http://developer.openstack.org/api-ref-orchestration-v1.html
    """
    api_name = 'openstack'
    name = 'OpenStack'
    website = 'http://openstack.org/'
    connectionCls = MonitorConnection
    type = Provider.OPENSTACK

    def __init__(self, key, secret=None, secure=True, host=None, port=None,
                 api_version=DEFAULT_API_VERSION, **kwargs):
        if api_version != '1.0':
            raise NotImplementedError(
                "No OpenStackAutoScaleDriver found for API version %s" %
                (api_version))

        OpenStackDriverMixin.__init__(self, **kwargs)
        super(OpenStackAutoScaleMonitorDriver, self).__init__(
            key=key, secret=secret, secure=secure, host=host,
            port=port, api_version=api_version,
            **kwargs)

    _VALUE_TO_SCALE_OPERATOR_TYPE_MAP = {
        'ge': AutoScaleOperator.GE,
        'gt': AutoScaleOperator.GT,
        'le': AutoScaleOperator.LE,
        'lt': AutoScaleOperator.LT,
    }

    _SCALE_OPERATOR_TYPE_TO_VALUE_MAP = reverse_dict(
        _VALUE_TO_SCALE_OPERATOR_TYPE_MAP)

    _VALUE_TO_METRIC_MAP = {
        'cpu_util': AutoScaleMetric.CPU_UTIL
    }

    _METRIC_TO_VALUE_MAP = reverse_dict(_VALUE_TO_METRIC_MAP)

    def create_auto_scale_alarm(self, name, policy, metric_name, operator,
                                threshold, period, **kwargs):
        stack_name = policy.extra['stack_name']
        stack_id = policy.extra['stack_id']

        def _wait_for_update(stack_name, stack_id, pre_update_ts):
            DEFAULT_TIMEOUT = 600
            POLL_INTERVAL = 5

            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                stack = self.connection.get_stack(stack_name, stack_id)
                stack_status = stack['stack_status']
                ts_completed = iso_to_datetime(
                    stack.get('updated_time')) > pre_update_ts
                if (stack_status == 'UPDATE_COMPLETE' and ts_completed) or \
                        stack_status == 'UPDATE_FAILED':
                    completed = True
                else:
                    time.sleep(POLL_INTERVAL)

            if not completed:
                raise LibcloudError('Policy creation did not complete in %s'
                                    ' seconds' % (DEFAULT_TIMEOUT))

        template_res = self.connection.get_stack_template(stack_name, stack_id)
        template = {
            name: {
                'type': 'OS::Ceilometer::Alarm',
                'properties': {
                    'meter_name': self._metric_to_value(metric_name),
                    'statistic': 'avg',
                    'period': period,
                    'evaluation_periods': 1,
                    'threshold': threshold,
                    'comparison_operator': self._operator_type_to_value(
                        operator),
                    'alarm_actions': [
                        {'get_attr': [policy.name, 'alarm_url']},
                    ]
                }
            }
        }

        template_res['resources'].update(template)

        pre_update_ts = self.connection.stack_update(stack_name, stack_id,
                                                     template_res)
        _wait_for_update(stack_name, stack_id, pre_update_ts)
        alarams = self.list_auto_scale_alarms(policy)
        return [a for a in alarams if a.name == name][0]

    def list_auto_scale_alarms(self, policy):
        stack_name = policy.extra['stack_name']
        stack_id = policy.extra['stack_id']
        template = self.connection.get_stack_template(stack_name, stack_id)
        return [self._get_auto_scale_alarm(k, stack_name, stack_id)
                for k in template['resources'] if
                template['resources'][k]['type'] == 'OS::Ceilometer::Alarm']

    def delete_auto_scale_alarm(self, alarm):
        def _wait_for_update(stack_name, stack_id, pre_update_ts):
            DEFAULT_TIMEOUT = 600
            POLL_INTERVAL = 5

            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                stack = self.connection.get_stack(stack_name, stack_id)
                stack_status = stack['stack_status']
                ts_completed = iso_to_datetime(
                    stack.get('updated_time')) > pre_update_ts
                if (stack_status == 'UPDATE_COMPLETE' and ts_completed) or \
                        stack_status == 'UPDATE_FAILED':
                    completed = True
                else:
                    time.sleep(POLL_INTERVAL)

            if not completed:
                raise LibcloudError('Update operation did not complete in %s'
                                    ' seconds' % (DEFAULT_TIMEOUT))

        stack_name = alarm.extra['stack_name']
        stack_id = alarm.extra['stack_id']

        template = self.connection.get_stack_template(stack_name, stack_id)

        if alarm.name in template['resources']:
            template['resources'].pop(alarm.name)
            pre_update_ts = self.connection.stack_update(stack_name, stack_id,
                                                         template)
            _wait_for_update(stack_name, stack_id, pre_update_ts)

        return True

    def _get_auto_scale_alarm(self, name, stack_name, stack_id):
        template = self.connection.get_stack_template(stack_name, stack_id)
        # resources is an array of dictionaries
        resources = self.connection.get_stack_resources(stack_name, stack_id)
        resource = find(resources['resources'],
                        lambda r: r['resource_type'] ==
                        'OS::Ceilometer::Alarm' and
                        r['resource_name'] == name)
        if not (name in template['resources'] and resource):
            raise LibcloudError(value='Alarm: %s not found' % name,
                                driver=self.connection.driver)

        extra = dict(stack_name=stack_name, stack_id=stack_id)
        return self._to_autoscale_alarm(name=name,
                                        template=template['resources'][name],
                                        resource=resource, extra=extra)

    def _to_autoscale_alarm(self, name, template, resource, extra=None):
        alarm_id = resource['logical_resource_id']
        metric_name = template['properties']['meter_name']
        op = template['properties']['comparison_operator']
        period = template['properties']['period']
        threshold = template['properties']['threshold']

        metric = self._value_to_metric(metric_name)
        operator = self._value_to_operator_type(op)

        return AutoScaleAlarm(id=alarm_id, name=name, metric_name=metric,
                              operator=operator, period=int(period),
                              threshold=int(float(threshold)),
                              driver=self.connection.driver, extra=extra)

    def list_supported_operator_types(self):
        return list(self._SCALE_OPERATOR_TYPE_TO_VALUE_MAP.keys())

    def _value_to_operator_type(self, value):

        try:
            return self._VALUE_TO_SCALE_OPERATOR_TYPE_MAP[value]
        except KeyError:
            raise LibcloudError(value='Invalid value: %s' % (value),
                                driver=self)

    def _operator_type_to_value(self, operator_type):
        """
        Return string value for the provided operator.

        :param value: AutoScaleOperator enum.
        :type  value: :class:`AutoScaleOperator`

        :rtype: ``str``
        """
        try:
            return self._SCALE_OPERATOR_TYPE_TO_VALUE_MAP[operator_type]
        except KeyError:
            raise LibcloudError(value='Invalid operator type: %s'
                                % (operator_type), driver=self)

    def _value_to_metric(self, value):

        try:
            return self._VALUE_TO_METRIC_MAP[value]
        except KeyError:
            raise LibcloudError(value='Invalid value: %s' % (value),
                                driver=self)

    def _metric_to_value(self, metric):
        """
        Return string value for the provided metric.

        :param value: AutoScaleMetric enum.
        :type  value: :class:`AutoScaleMetric`

        :rtype: ``str``
        """
        try:
            return self._METRIC_TO_VALUE_MAP[metric]
        except KeyError:
            raise LibcloudError(value='Invalid metric: %s'
                                % (metric), driver=self)

    def _ex_connection_class_kwargs(self):
        return self.openstack_connection_kwargs()
