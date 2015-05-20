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
from libcloud.common.base import ConnectionKey, BaseDriver, LibcloudError

__all__ = [
    'MonitorDriver',
    'AutoScaleAlarm'
]


class AutoScaleAlarm(object):
    """Base class for alarm triggering
    """

    def __init__(self, id, name, metric_name, period, operator, threshold,
                 driver, extra=None):
        """
        :param name: Descriptive name of the alarm.
        :type name: ``str``

        :param metric_name: The metric to watch.
        :type metric_name: ``str``

        :param period: The number of seconds the values are aggregated for when
                       compared to value.
        :type period: ``int``

        :param operator: The operator to use for comparison.
        :type operator: value within :class:`AutoScaleOperator`

        :param threshold: The value against which the specified statistic is
                          compared
        :type threshold: ``int``
        """
        self.id = str(id) if id else None
        self.name = name
        self.metric_name = metric_name
        self.period = period
        self.operator = operator
        self.threshold = threshold
        self.statistic = 'AVG'

        self.driver = driver
        self.extra = extra or {}

    def __repr__(self):
        return (
            ('<AutoScaleAlarm: id=%s, metric_name=%s, period=%s, '
             'operator=%s, threshold=%s, statistic=%s, '
             'provider=%s>') % (self.id, self.metric_name, self.period,
                                self.operator, self.threshold,
                                self.statistic, self.driver.name))


class MonitorDriver(BaseDriver):
    """
    A base MonitorDriver class to derive from.

    This class is always subclassed by a specific driver.

    """
    connectionCls = ConnectionKey

    name = None
    type = None
    port = None

    _SCALE_OPERATOR_TYPE_TO_VALUE_MAP = {}
    _VALUE_TO_SCALE_OPERATOR_TYPE_MAP = {}

    _METRIC_TO_VALUE_MAP = {}
    _VALUE_TO_METRIC_MAP = {}

    def __init__(self, key, secret=None, secure=True, host=None,
                 port=None, api_version=None, **kwargs):
        super(MonitorDriver, self).__init__(
            key=key, secret=secret, secure=secure, host=host,
            port=port, api_version=api_version, **kwargs)

    def create_auto_scale_alarm(self, name, policy, metric_name, operator,
                                threshold, period, **kwargs):
        """
        Create an auto scale alarm for the given policy.

        :param name: Descriptive name of the alarm.
        :type name: ``str``

        :param policy: Policy object.
        :type policy: :class:`.AutoScalePolicy`

        :param metric_name: The metric to watch.
        :type metric_name: value within :class:`AutoScaleMetric`

        :param operator: The operator to use for comparison.
        :type operator: value within :class:`AutoScaleOperator`

        :param threshold: The value against which the specified statistic is
                          compared
        :type threshold: ``int``

        :param period: The number of seconds the values are aggregated for when
                       compared to threshold.
        :type period: ``int``

        :return: The created alarm.
        :rtype: :class:`.AutoScaleAlarm`
        """

        raise NotImplementedError(
            'create_auto_scale_alarm not implemented for this driver')

    def list_auto_scale_alarms(self, policy):
        """
        List alarms associated with the given auto scale policy.

        :param policy: Policy object.
        :type policy: :class:`.AutoScalePolicy`

        :rtype: ``list`` of ``AutoScaleAlarm``
        """
        raise NotImplementedError(
            'list_auto_scale_alarms not implemented for this driver')

    def delete_auto_scale_alarm(self, alarm):
        """
        Delete auto scale alarm.

        :param alarm: Alarm object.
        :type alarm: :class:`.AutoScaleAlarm`

        :return: ``True`` if delete_auto_scale_alarm was successful,
        ``False`` otherwise.
        :rtype: ``bool``

        """
        raise NotImplementedError(
            'delete_auto_scale_alarm not implemented for this driver')

    def list_supported_operator_types(self):
        """
        Return operator types supported by this driver.

        :rtype: ``list`` of ``str``
        """
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
