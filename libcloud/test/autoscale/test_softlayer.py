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

import unittest
import sys

try:
    import Crypto
    Crypto
    crypto = True
except ImportError:
    crypto = False

from libcloud.utils.py3 import httplib
from libcloud.utils.py3 import xmlrpclib

from libcloud.autoscale.base import AutoScalePolicy, \
    AutoScaleGroup
from libcloud.autoscale.drivers.softlayer import SoftLayerAutoScaleDriver as \
    asSoftlayer
from libcloud.autoscale.types import AutoScaleAdjustmentType

from libcloud.compute.drivers.softlayer import SoftLayerNodeDriver as SoftLayer

from libcloud.monitor.base import AutoScaleAlarm
from libcloud.monitor.drivers.softlayer import SoftLayerMonitorDriver as \
    monSoftlayer
from libcloud.monitor.types import AutoScaleMetric, AutoScaleOperator

from libcloud.test import MockHttp               # pylint: disable-msg=E0611
from libcloud.test.file_fixtures import ComputeFileFixtures
from libcloud.test.secrets import SOFTLAYER_PARAMS

null_fingerprint = '00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:' + \
                   '00:00:00:00:00'
DELETE_GROUP_CALLS = 0


class SoftLayerTests(unittest.TestCase):

    def setUp(self):
        SoftLayer.connectionCls.conn_classes = (
            SoftLayerMockHttp, SoftLayerMockHttp)
        SoftLayerMockHttp.type = None
        SoftLayerMockHttp.test = self
        self.driver = SoftLayer(*SOFTLAYER_PARAMS)

        asSoftlayer.connectionCls.conn_classes = (
            SoftLayerMockHttp, SoftLayerMockHttp)
        self.as_driver = asSoftlayer(*SOFTLAYER_PARAMS)

        monSoftlayer.connectionCls.conn_classes = (
            SoftLayerMockHttp, SoftLayerMockHttp)
        self.mon_driver = monSoftlayer(*SOFTLAYER_PARAMS)

    def test_create_auto_scale_group(self):

        group = self.as_driver.create_auto_scale_group(
            group_name="libcloud-testing", min_size=1, max_size=5,
            cooldown=300, name='inst-test', size=self.driver.list_sizes()[0],
            image=self.driver.list_images()[0],
            termination_policies=[2])

        self.assertEqual(group.name, 'libcloud-testing')
        self.assertEqual(group.cooldown, 300)
        self.assertEqual(group.min_size, 1)
        self.assertEqual(group.max_size, 5)
        self.assertEqual(group.termination_policies, [2])

    def test_create_auto_scale_group_size(self):

        group = self.as_driver.create_auto_scale_group(
            group_name="libcloud-testing", min_size=1, max_size=5,
            cooldown=300, name='inst-test', image=self.driver.list_images()[0],
            size=self.driver.list_sizes()[0], termination_policies=2)

        self.assertEqual(group.name, 'libcloud-testing')
        self.assertEqual(group.cooldown, 300)
        self.assertEqual(group.min_size, 1)
        self.assertEqual(group.max_size, 5)
        self.assertEqual(group.termination_policies, [2])

    def test_list_auto_scale_groups(self):

        groups = self.as_driver.list_auto_scale_groups()
        self.assertEqual(len(groups), 3)

    def test_create_auto_scale_policy(self):

        group = AutoScaleGroup(145955, 'libcloud-testing', None, None, None, 0,
                               self.driver)

        policy = self.as_driver.create_auto_scale_policy(
            group=group, name='libcloud-testing-policy',
            adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
            scaling_adjustment=1)

        self.assertEqual(policy.name, 'libcloud-testing-policy')
        self.assertEqual(policy.adjustment_type,
                         AutoScaleAdjustmentType.CHANGE_IN_CAPACITY)
        self.assertEqual(policy.scaling_adjustment, 1)

    def test_list_auto_scale_policies(self):

        group = AutoScaleGroup(167555, 'libcloud-testing', None, None, None, 0,
                               self.driver)
        policies = self.as_driver.list_auto_scale_policies(group=group)
        self.assertEqual(len(policies), 1)

    def test_create_auto_scale_alarm(self):

        policy = AutoScalePolicy(45955, None, None, None,
                                 self.driver)

        alarm = self.mon_driver.create_auto_scale_alarm(
            name='libcloud-testing-alarm', policy=policy,
            metric_name=AutoScaleMetric.CPU_UTIL,
            operator=AutoScaleOperator.GT, threshold=80, period=120)

        self.assertEqual(alarm.metric_name, AutoScaleMetric.CPU_UTIL)
        self.assertEqual(alarm.operator, AutoScaleOperator.GT)
        self.assertEqual(alarm.threshold, 80)
        self.assertEqual(alarm.period, 120)

    def test_list_auto_scale_alarms(self):

        policy = AutoScalePolicy(50055, None, None, None,
                                 self.driver)
        alarms = self.mon_driver.list_auto_scale_alarms(policy)
        self.assertEqual(len(alarms), 1)

    def test_delete_alarm(self):

        alarm = AutoScaleAlarm(37903, None, None, None, None, None,
                               self.driver)
        self.mon_driver.delete_auto_scale_alarm(alarm)

    def test_delete_policy(self):

        policy = AutoScalePolicy(45955, None, None, None, self.driver)
        self.as_driver.delete_auto_scale_policy(policy)

    def test_delete_group(self):

        group = AutoScaleGroup(145955, 'libcloud-testing', None, None, None, 0,
                               self.driver)
        SoftLayerMockHttp.type = 'DELETE'
        global DELETE_GROUP_CALLS
        DELETE_GROUP_CALLS = 0
        self.as_driver.delete_auto_scale_group(group)


class SoftLayerMockHttp(MockHttp):
    fixtures = ComputeFileFixtures('softlayer')

    def _get_method_name(self, type, use_param, qs, path):
        return "_xmlrpc"

    def _xmlrpc(self, method, url, body, headers):
        params, meth_name = xmlrpclib.loads(body)
        url = url.replace("/", "_")
        meth_name = "%s_%s" % (url, meth_name)
        return getattr(self, meth_name)(method, url, body, headers)

    def _xmlrpc_v3_SoftLayer_Account_getVirtualGuests(
            self, method, url, body, headers):
        body = self.fixtures.load('v3_SoftLayer_Account_getVirtualGuests.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Location_Datacenter_getDatacenters(
            self, method, url, body, headers):
        body = self.fixtures.load(
            'v3_SoftLayer_Location_Datacenter_getDatacenters.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Location_Group_Regional_getAllObjects(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Location_Group_Regional_getAllObjects.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Group_createObject(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Group_createObject.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Group_getObject(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Group_getObject.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Group_getStatus(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Group_getStatus.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Group_getPolicies(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Group_getPolicies.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Group_forceDeleteObject(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Group_forceDeleteObject.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Account_getScaleGroups(
            self, method, url, body, headers):

        global DELETE_GROUP_CALLS
        if self.type == 'DELETE':
            if DELETE_GROUP_CALLS > 3:
                fixture = 'v3__SoftLayer_Account_getScaleGroups_emtpy.xml'
            else:
                DELETE_GROUP_CALLS = DELETE_GROUP_CALLS + 1
                fixture = 'v3__SoftLayer_Account_getScaleGroups.xml'
        else:
            fixture = 'v3__SoftLayer_Account_getScaleGroups.xml'

        body = self.fixtures.load(fixture)
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Policy_createObject(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Policy_createObject.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Policy_getObject(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Policy_getObject.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Policy_getResourceUseTriggers(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Policy_getResourceUseTriggers.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Policy_deleteObject(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Policy_deleteObject.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Policy_Trigger_ResourceUse_createObject(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Policy_Trigger_ResourceUse_createObject.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Policy_Trigger_ResourceUse_getObject(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Policy_Trigger_ResourceUse_getObject.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

    def _xmlrpc_v3_SoftLayer_Scale_Policy_Trigger_ResourceUse_deleteObject(
            self, method, url, body, headers):
        body = self.fixtures.load('v3__SoftLayer_Scale_Policy_Trigger_ResourceUse_deleteObject.xml')
        return (httplib.OK, body, {}, httplib.responses[httplib.OK])

if __name__ == '__main__':
    sys.exit(unittest.main())
