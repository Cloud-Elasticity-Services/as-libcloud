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
from libcloud.common.softlayer import SoftLayerConnection

from libcloud.monitor.base import AutoScaleAlarm, MonitorDriver
from libcloud.monitor.types import AutoScaleOperator, AutoScaleMetric
from libcloud.monitor.types import Provider

from libcloud.utils.misc import reverse_dict


class SoftLayerMonitorDriver(MonitorDriver):

    _VALUE_TO_SCALE_OPERATOR_TYPE_MAP = {
        '>': AutoScaleOperator.GT,
        '<': AutoScaleOperator.LT
    }

    _SCALE_OPERATOR_TYPE_TO_VALUE_MAP = reverse_dict(
        _VALUE_TO_SCALE_OPERATOR_TYPE_MAP)

    _VALUE_TO_METRIC_MAP = {
        'host.cpu.percent': AutoScaleMetric.CPU_UTIL
    }

    _METRIC_TO_VALUE_MAP = reverse_dict(
        _VALUE_TO_METRIC_MAP)

    connectionCls = SoftLayerConnection
    name = 'SoftLayer'
    website = 'http://www.softlayer.com/'
    type = Provider.SOFTLAYER

    def __init__(self, *args, **kwargs):
        super(SoftLayerMonitorDriver, self).__init__(*args, **kwargs)

    def create_auto_scale_alarm(self, name, action_ids, metric_name, operator,
                                threshold, period, **kwargs):
        data = {}
        # 'RESOURCE_USE'
        data['typeId'] = 3
        data['scalePolicyId'] = action_ids[0]

        trigger_watch = {}
        trigger_watch['algorithm'] = 'EWMA'
        trigger_watch['metric'] = self._metric_to_value(metric_name)

        trigger_watch['operator'] = \
            self._operator_type_to_value(operator)

        trigger_watch['value'] = threshold
        trigger_watch['period'] = period

        data['watches'] = [trigger_watch]

        res = self.connection.\
            request('SoftLayer_Scale_Policy_Trigger_ResourceUse',
                    'createObject', data).object

        mask = {
            'watches': ''
        }

        res = self.connection.\
            request('SoftLayer_Scale_Policy_Trigger_ResourceUse',
                    'getObject', id=res['id'], object_mask=mask).object
        alarm = self._to_autoscale_alarm(res)

        return alarm

    def list_auto_scale_alarms(self, action_ids):
        mask = {
            'resourceUseTriggers': {
                'watches': ''
            }
        }

        res = self.connection.request('SoftLayer_Scale_Policy',
                                      'getResourceUseTriggers',
                                      object_mask=mask,
                                      id=action_ids[0]).object
        return [self._to_autoscale_alarm(r) for r in res]

    def delete_auto_scale_alarm(self, alarm):
        self.connection.request('SoftLayer_Scale_Policy_Trigger_ResourceUse',
                                'deleteObject', id=alarm.id).object
        return True

    def _to_autoscale_alarm(self, alrm):

        alrm_id = alrm['id']

        metric = None
        operator = None
        period = None
        threshold = None

        if alrm.get('watches', []):

            metric = self._value_to_metric(alrm['watches'][0]['metric'])
            op = alrm['watches'][0]['operator']
            operator = self._value_to_operator_type(op)
            period = alrm['watches'][0]['period']
            threshold = alrm['watches'][0]['value']

        return AutoScaleAlarm(id=alrm_id, name='N/A', metric_name=metric,
                              operator=operator, period=period,
                              threshold=int(threshold),
                              driver=self.connection.driver)
