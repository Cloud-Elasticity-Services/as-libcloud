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

from libcloud.common.types import LibcloudError
from libcloud.common.softlayer import SoftLayerException, \
    SoftLayerObjectDoesntExist, SoftLayerConnection

from libcloud.autoscale.base import AutoScaleDriver, AutoScalePolicy, \
    AutoScaleGroup
from libcloud.autoscale.types import AutoScaleTerminationPolicy, \
    AutoScaleAdjustmentType
from libcloud.autoscale.types import Provider
from libcloud.utils.misc import find, reverse_dict
from libcloud.compute.drivers.softlayer import SoftLayerNodeDriver


class SoftLayerAutoScaleDriver(AutoScaleDriver):

    _VALUE_TO_SCALE_ADJUSTMENT_TYPE_MAP = {
        'RELATIVE': AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
        'ABSOLUTE': AutoScaleAdjustmentType.EXACT_CAPACITY,
        'PERCENT': AutoScaleAdjustmentType.PERCENT_CHANGE_IN_CAPACITY
    }

    _SCALE_ADJUSTMENT_TYPE_TO_VALUE_MAP = reverse_dict(
        _VALUE_TO_SCALE_ADJUSTMENT_TYPE_MAP)

    _VALUE_TO_TERMINATION_POLICY_MAP = {
        'OLDEST': AutoScaleTerminationPolicy.OLDEST_INSTANCE,
        'NEWEST': AutoScaleTerminationPolicy.NEWEST_INSTANCE,
        'CLOSEST_TO_NEXT_CHARGE': AutoScaleTerminationPolicy.
        CLOSEST_TO_NEXT_CHARGE
    }

    _TERMINATION_POLICY_TO_VALUE_MAP = reverse_dict(
        _VALUE_TO_TERMINATION_POLICY_MAP)

    connectionCls = SoftLayerConnection
    name = 'SoftLayer'
    website = 'http://www.softlayer.com/'
    type = Provider.SOFTLAYER

    def __init__(self, *args, **kwargs):

        if kwargs.get('softlayer'):
            self.softlayer = kwargs['softlayer']
        else:
            self.softlayer = SoftLayerNodeDriver(*args, **kwargs)

        super(SoftLayerAutoScaleDriver, self).__init__(*args, **kwargs)

    def list_auto_scale_groups(self):

        mask = {
            'scaleGroups': {
                'terminationPolicy': ''
            }
        }

        res = self.connection.request('SoftLayer_Account',
                                      'getScaleGroups', object_mask=mask).\
            object
        return self._to_autoscale_groups(res)

    def create_auto_scale_group(
            self, group_name, min_size, max_size, cooldown,
            termination_policies, balancer=None, ex_region='na-usa-east-1',
            **kwargs):
        """
        Create a new auto scale group.

        @inherits: :class:`AutoScaleDriver.create_auto_scale_group`

        :param ex_region: The region the group will be created
        in. e.g. 'na-usa-east-1' (required)
        :type  ex_region: ``str``

        :keyword    ex_service_port: Service port to be used by the group
                                     members.
        :type       ex_service_port: ``int``

        :return: The newly created scale group.
        :rtype: :class:`.AutoScaleGroup`
        """
        DEFAULT_TIMEOUT = 12000
        template = self.softlayer._to_virtual_guest_template(**kwargs)

        # Customize template per property 'virtualGuestMemberTemplate' at:
        # http://sldn.softlayer.com/reference/datatypes/SoftLayer_Scale_Group
        if 'datacenter' not in template:
            template['datacenter'] = {'name': 'FIRST_AVAILABLE'}
        template['hourlyBillingFlag'] = 'true'

        def _wait_for_creation(group_id):
            # 5 seconds
            POLL_INTERVAL = 5

            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                status_name = self._get_group_status(group_id)
                if status_name != 'ACTIVE':
                    time.sleep(POLL_INTERVAL)
                else:
                    completed = True

            if not completed:
                raise LibcloudError('Group creation did not complete in %s'
                                    ' seconds' % (DEFAULT_TIMEOUT))

        # retrieve internal region id
        res = self.connection.request(
            'SoftLayer_Location_Group_Regional',
            'getAllObjects').object
        r = find(res, lambda r: r['name'] == ex_region)
        if not r:
            raise SoftLayerException('Unable to find region id for region: %s'
                                     % ex_region)
        rgn_grp_id = r['id']

        data = {}
        data['name'] = group_name
        data['minimumMemberCount'] = min_size
        data['maximumMemberCount'] = max_size
        data['cooldown'] = cooldown

        data['regionalGroupId'] = rgn_grp_id
        data['suspendedFlag'] = False

        if termination_policies:
            termination_policy = termination_policies[0] if \
                isinstance(termination_policies, list) else \
                termination_policies
            data['terminationPolicy'] = {
                'keyName':
                    self._termination_policy_to_value(termination_policy)
            }

        data['virtualGuestMemberTemplate'] = template

        if balancer:
            # if not datacenter:
            # raise ValueError('location must be supplied when supplying '
            # 'loadbalancer')

            ex_service_port = kwargs.get('ex_service_port', 80)
            data['loadBalancers'] = [
                self._generate_balancer_template(balancer, ex_service_port)]

        res = self.connection.request('SoftLayer_Scale_Group',
                                      'createObject', data).object

        _wait_for_creation(res['id'])
        mask = {
            'terminationPolicy': ''
        }

        res = self.connection.request('SoftLayer_Scale_Group', 'getObject',
                                      object_mask=mask, id=res['id']).object
        group = self._to_autoscale_group(res)

        return group

    def list_auto_scale_group_members(self, group):
        mask = {
            'virtualGuest': {
                'billingItem': '',
                'powerState': '',
                'operatingSystem': {'passwords': ''},
                'provisionDate': ''
            }
        }

        res = self.connection.request('SoftLayer_Scale_Group',
                                      'getVirtualGuestMembers',
                                      id=group.id).object

        nodes = []
        for r in res:
            # NOTE: r[id]  is ID of virtual guest member
            # (not instance itself)
            res_node = self.connection.request('SoftLayer_Scale_Member_'
                                               'Virtual_Guest',
                                               'getVirtualGuest', id=r['id'],
                                               object_mask=mask).object
            if res_node:
                nodes.append(self.softlayer._to_node(res_node))

        return nodes

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
        data['name'] = name
        data['scaleGroupId'] = int(group.id)

        policy_action = {}
        # 'SCALE'
        policy_action['typeId'] = 1
        policy_action['scaleType'] = \
            self._scale_adjustment_to_value(adjustment_type)
        policy_action['amount'] = scaling_adjustment

        data['scaleActions'] = [policy_action]

        res = self.connection.request('SoftLayer_Scale_Policy',
                                      'createObject', data).object
        mask = {
            'scaleActions': ''
        }

        res = self.connection.request('SoftLayer_Scale_Policy',
                                      'getObject', id=res['id'],
                                      object_mask=mask).object
        policy = self._to_autoscale_policy(res)

        return policy

    def list_auto_scale_policies(self, group):
        mask = {
            'policies': {
                'scaleActions': ''
            }
        }

        res = self.connection.request('SoftLayer_Scale_Group', 'getPolicies',
                                      id=group.id, object_mask=mask).object
        return [self._to_autoscale_policy(r) for r in res]

    def delete_auto_scale_policy(self, policy):
        self.connection.request('SoftLayer_Scale_Policy',
                                'deleteObject', id=policy.id).object
        return True

    def delete_auto_scale_group(self, group):
        DEFAULT_TIMEOUT = 12000

        def _wait_for_deletion(group_name):
            # 5 seconds
            POLL_INTERVAL = 5

            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                try:
                    self._get_auto_scale_group(group_name)
                    time.sleep(POLL_INTERVAL)
                except SoftLayerObjectDoesntExist:
                    # for now treat this as not found
                    completed = True
            if not completed:
                raise LibcloudError('Operation did not complete in %s seconds'
                                    % (DEFAULT_TIMEOUT))

        self.connection.request(
            'SoftLayer_Scale_Group', 'forceDeleteObject', id=group.id).object

        _wait_for_deletion(group.name)

        return True

    def ex_attach_balancer_to_auto_scale_group(self, group, balancer,
                                               ex_service_port=80):
        """
        Attach loadbalancer to auto scale group.

        :param group: Group object.
        :type group: :class:`.AutoScaleGroup`

        :param balancer: The loadbalancer object.
        :type balancer: :class:`.LoadBalancer`

        :param ex_service_port: Service port to be used by the group members.
        :type  ex_service_port: ``int``

        :return: ``True`` if attach_balancer_to_auto_scale_group was
        successful.
        :rtype: ``bool``
        """
        def _get_group_model(group_id):

            mask = {
                'loadBalancers': ''
            }

            return self.connection.request('SoftLayer_Scale_Group',
                                           'getObject', object_mask=mask,
                                           id=group_id).object

        res = _get_group_model(group.id)
        res['loadBalancers'].append(
            self._generate_balancer_template(balancer, ex_service_port))

        self.connection.request('SoftLayer_Scale_Group', 'editObject', res,
                                id=group.id)
        return True

    def ex_detach_balancer_from_auto_scale_group(self, group, balancer):
        """
        Detach loadbalancer from auto scale group.

        :param group: Group object.
        :type group: :class:`.AutoScaleGroup`

        :param balancer: The loadbalancer object.
        :type balancer: :class:`.LoadBalancer`

        :return: ``True`` if detach_balancer_from_auto_scale_group was
        successful.
        :rtype: ``bool``
        """

        def _get_group_model(group_id):

            mask = {
                'loadBalancers': ''
            }

            return self.connection.request('SoftLayer_Scale_Group',
                                           'getObject', object_mask=mask,
                                           id=group_id).object

        def _get_balancer_model(balancer_id):

            lb_service = 'SoftLayer_Network_Application_Delivery_Controller_'\
                'LoadBalancer_VirtualIpAddress'

            lb_mask = {
                'virtualServers': {
                    'serviceGroups': {
                        'services': ''
                    },
                    'scaleLoadBalancers': {
                    }
                }
            }

            lb_res = self.connection.request(lb_service, 'getObject',
                                             object_mask=lb_mask,
                                             id=balancer_id).object
            return lb_res

        def _locate_vs(lb, port):

            vs = None
            if port < 0:
                vs = lb['virtualServers'][0] if lb['virtualServers']\
                    else None
            else:
                for v in lb['virtualServers']:
                    if v['port'] == port:
                        vs = v

            return vs

        res = _get_group_model(group.id)
        lb_res = _get_balancer_model(balancer.id)
        vs = _locate_vs(lb_res, balancer.port)
        if not vs:
            raise LibcloudError(value='No service_group found for port: %s' %
                                balancer.port, driver=self)
        lbs_to_remove = [lb['id'] for lb in res['loadBalancers'] if
                         lb['virtualServerId'] == vs['id']]
        for lb in lbs_to_remove:
            self.connection.request('SoftLayer_Scale_LoadBalancer',
                                    'deleteObject', id=lb)
        return True

    def _get_auto_scale_group(self, group_name):

        groups = self.list_auto_scale_groups()
        group = find(groups, lambda g: g.name == group_name)
        if not group:
            raise SoftLayerObjectDoesntExist('Group name: %s does not exist'
                                             % group_name)
        return group

    def _get_group_status(self, group_id):
        res = self.connection.request('SoftLayer_Scale_Group',
                                      'getStatus', id=group_id).object
        return res['keyName']

    def _to_autoscale_policy(self, plc):

        plc_id = plc['id']
        name = plc['name']

        adj_type = None
        adjustment_type = None
        scaling_adjustment = None

        if plc.get('scaleActions', []):

            adj_type = plc['scaleActions'][0]['scaleType']
            adjustment_type = self._value_to_scale_adjustment(adj_type)
            scaling_adjustment = plc['scaleActions'][0]['amount']

        return AutoScalePolicy(id=plc_id, name=name,
                               adjustment_type=adjustment_type,
                               scaling_adjustment=scaling_adjustment,
                               driver=self.connection.driver)

    def _to_autoscale_groups(self, res):
        groups = [self._to_autoscale_group(grp) for grp in res]
        return groups

    def _to_autoscale_group(self, grp):

        grp_id = grp['id']
        name = grp['name']
        cooldown = grp['cooldown']
        min_size = grp['minimumMemberCount']
        max_size = grp['maximumMemberCount']

        sl_tp = self._value_to_termination_policy(
            grp['terminationPolicy']['keyName'])
        termination_policies = [sl_tp]

        extra = {}
        extra['id'] = grp_id
        extra['state'] = grp['status']['keyName']
        # TODO: set with region name
        extra['region'] = 'softlayer'
        extra['regionalGroupId'] = grp['regionalGroupId']
        extra['suspendedFlag'] = grp['suspendedFlag']
        extra['terminationPolicyId'] = grp['terminationPolicyId']

        return AutoScaleGroup(id=grp_id, name=name, cooldown=cooldown,
                              min_size=min_size, max_size=max_size,
                              termination_policies=termination_policies,
                              driver=self.connection.driver,
                              extra=extra)

    def _generate_balancer_template(self, balancer, ex_service_port):

        lb_service = 'SoftLayer_Network_Application_Delivery_Controller_'\
            'LoadBalancer_VirtualIpAddress'

        lb_mask = {
            'virtualServers': {
                'serviceGroups': {
                },
                'scaleLoadBalancers': {
                }
            }
        }

        # get the loadbalancer
        lb_res = self.connection.request(
            lb_service, 'getObject', object_mask=lb_mask,
            id=balancer.id).object

        # find the vs with matching balancer port
        # we need vs id for the scale template to 'connect' it
        vss = lb_res.get('virtualServers', [])
        vs = find(vss, lambda vs: vs['port'] == balancer.port)
        if not vs:
            raise LibcloudError(value='No virtualServers found for'
                                ' Softlayer loadbalancer with port: %s' %
                                balancer.port, driver=self)

        scale_lb_template = {
            # connect it to the matched vs
            'virtualServerId': vs['id'],
            'port': ex_service_port,
            # DEFAULT health check
            'healthCheck': {
                'healthCheckTypeId': 21
            }
        }
        return scale_lb_template
