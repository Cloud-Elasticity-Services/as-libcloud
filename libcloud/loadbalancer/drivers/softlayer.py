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
from libcloud.compute.base import AutoScaleGroup
from libcloud.common.types import LibcloudError

__all__ = [
    'SoftlayerLBDriver'
]

from libcloud.utils.misc import reverse_dict, find
from libcloud.loadbalancer.types import MemberCondition, State
from libcloud.loadbalancer.base import Algorithm, Driver, LoadBalancer,\
                                       DEFAULT_ALGORITHM, Member
from libcloud.common.softlayer import SoftLayerConnection
from libcloud.compute.drivers.softlayer import SoftLayerNodeDriver

lb_service = 'SoftLayer_Network_Application_Delivery_Controller_LoadBalancer_'\
'VirtualIpAddress'

class SoftlayerLBDriver(Driver):
    name = 'Softlayer Load Balancing'
    website = 'http://www.softlayer.com/'
    connectionCls = SoftLayerConnection

    _VALUE_TO_ALGORITHM_MAP = {
        'ROUND_ROBIN': Algorithm.ROUND_ROBIN,
        'LEAST_CONNECTIONS': Algorithm.LEAST_CONNECTIONS,
    }

    _ALGORITHM_TO_VALUE_MAP = reverse_dict(_VALUE_TO_ALGORITHM_MAP)

    LB_MEMBER_CONDITION_MAP = {
        'ENABLED': MemberCondition.ENABLED,
        'DISABLED': MemberCondition.DISABLED,
    }

    CONDITION_LB_MEMBER_MAP = reverse_dict(LB_MEMBER_CONDITION_MAP)

    def __init__(self, key, secrete, **kwargs):

        super(SoftlayerLBDriver, self).__init__(key, secrete)
        if kwargs.get('softlayer_driver'):
            self.softlayer = kwargs['softlayer_driver']
        else:
            self.softlayer = SoftLayerNodeDriver(key, secrete, **kwargs)

    def list_balancers(self):
        """
        List all loadbalancers

        :rtype: ``list`` of :class:`LoadBalancer`
        """

        mask = {
            'adcLoadBalancers': {
                'ipAddress': '',
                'virtualServers': {
                    'serviceGroups': {
                        'routingMethod': '',
                        'routingType': '',
                        'services': {
                            'ipAddress': ''
                        }
                    },
                    'scaleLoadBalancers': {
                        'healthCheck': '',
                        'routingMethod': '',
                        'routingType': ''
                    }
                }
            }
        }
        res = self.connection.request('SoftLayer_Account',
            'getAdcLoadBalancers', object_mask=mask).object
        return [self._to_balancer(lb) for lb in res]

    def list_protocols(self):
        """
        Return a list of supported protocols.

        :rtype: ``list`` of ``str``
        """
        return ['dns', 'ftp', 'http', 'https', 'tcp', 'udp']

    def ex_add_service_group(self, balancer, allocation=100, port=80,
                          protocol='http', algorithm=DEFAULT_ALGORITHM):
        """Adds a new service group to the load balancer."""

        _types = self._get_routing_types()
        _methods = self._get_routing_methods()

        rt = find(_types, lambda t: t['keyname'] == protocol.upper())
        if not rt:
            raise LibcloudError(value='Invalid protocol %s' % protocol,
                                driver=self)

        method = find(_methods, lambda m: m['keyname'] == \
                      self._algorithm_to_value(algorithm))
        if not method:
            raise LibcloudError(value='Invalid algorithm %s' % algorithm,
                                driver=self)

        mask = {
                'virtualServers': {
                    'serviceGroups': {
                    }
                }
        }

        service_template = {
            'port': port,
            'allocation': allocation,
            'serviceGroups': [
                {
                    'routingTypeId': rt['id'],
                    'routingMethodId': method['id']
                }
            ]
        }

        res = self.connection.request(lb_service, 'getObject',
                                      object_mask=mask, id=balancer.id).object

        res['virtualServers'].append(service_template)
        self.connection.request(lb_service, 'editObject', res,
                                id=balancer.id)
        # TODO: return something?

    def ex_add_scale_balancer(self, balancer, group, allocation=100,
                              lb_port=80, port=80, protocol='http',
                              algorithm=DEFAULT_ALGORITHM):
        """
        Adds a new scale balancer configuration for the given scale group
        Note: balancer should not be set with service groups. This call
        creates such one based on given parameters and ties it to a given
        scale group.
        """
        #TODO: doc that lb_port is balancer port
        # and port is service port
        _types = self._get_routing_types()
        _methods = self._get_routing_methods()
        _hc_types = self._get_health_checks_types()

        # TODO: make this configurable
        hc_type = _hc_types[0]

        rt = find(_types, lambda t: t['keyname'] == protocol.upper())
        if not rt:
            raise LibcloudError(value='Invalid protocol %s' % protocol,
                                driver=self)

        method = find(_methods, lambda m: m['keyname'] == \
                      self._algorithm_to_value(algorithm))
        if not method:
            raise LibcloudError(value='Invalid algorithm %s' % algorithm,
                                driver=self)
        lb_mask = {
                'virtualServers': {
                    'serviceGroups': {
                    },
                    'scaleLoadBalancers': {
                    }
                }
        }

        # get the loadbalancer
        lb_res = self.connection.request(lb_service, 'getObject',
                                         object_mask=lb_mask, id=balancer.id).\
                                         object
        print lb_res
        service_template = {
            'port': lb_port, # loadbalancer listening port
            'allocation': allocation,
            'serviceGroups': [
                {
                'routingTypeId': rt['id'],
                 'routingMethodId': method['id']
                 }
            ],
        }

        lb_res['virtualServers'].append(service_template)
        # add newly vs with the service group
        self.connection.request(lb_service, 'editObject', lb_res,
                                id=balancer.id)

        # get loadbalancer with the vs added
        lb_res = self.connection.request(lb_service, 'getObject',
                                         object_mask=lb_mask, id=balancer.id).\
                                         object

        grp_mask = {
                    'loadBalancers': {
                    }
                }

        # get the scale group
        res = self.connection.request('SoftLayer_Scale_Group', 'getObject',
                                      object_mask=grp_mask, id=group.id).object
        print res
        vs_id = lb_res['virtualServers'][0]['id']
        scale_lb_template = {
            'virtualServerId': vs_id, # id of newly added loadbalancer vs
            'port': port,
            'routingTypeId': rt['id'],
            'routingMethodId': method['id'],
            'healthCheck': {
                'healthCheckTypeId': hc_type['id']
            }
        }

        res['loadBalancers'].append(scale_lb_template)

        # add the newly scale loadbalancer to the group
        self.connection.request('SoftLayer_Scale_Group', 'editObject', res,
                                id=group.id)

        # TODO: return something?

    def ex_remove_scale_balancer(self, balancer, group):
        """Detach balancer from the scale group and remove the associated
        service group.
        """
        pass

    def ex_list_scale_balancers(self, group):
        mask = {
            'loadBalancers': {
                'virtualServer': {
                    'virtualIpAddress': {'ipAddress': ''},
                    'port': ''
                }
            }
        }
        res = self.connection.request('SoftLayer_Scale_Group',
                                      'getLoadBalancers',
                                      object_mask=mask, id=group.id).object        
        
    def _get_routing_types(self):

        svc_rtype = 'SoftLayer_Network_Application_Delivery_Controller_'\
        'LoadBalancer_Routing_Type'

        return self.connection.request(svc_rtype, 'getAllObjects').object

    def _get_routing_methods(self):

        svc_rmeth = 'SoftLayer_Network_Application_Delivery_Controller_'\
        'LoadBalancer_Routing_Method'

        return self.connection.request(svc_rmeth, 'getAllObjects').object

    def _get_health_checks_types(self):

        svc_hctype = 'SoftLayer_Network_Application_Delivery_Controller_'\
        'LoadBalancer_Health_Check_Type'
        
        return self.connection.request(svc_hctype, 'getAllObjects').object

    def _to_balancer(self, lb):
        ipaddress = lb['ipAddress']['ipAddress']

        # dealing with first vs
        vs = lb['virtualServers'][0] if lb['virtualServers'] else None

        port = vs['port'] if vs else 0

        extra = {}
        extra['ssl_active'] = lb['sslActiveFlag']
        extra['ssl_enabled'] = lb['sslEnabledFlag']
        extra['ha'] = lb['highAvailabilityFlag']
        balancer = LoadBalancer(
            id=lb['id'],
            name='',
            state=State.UNKNOWN,
            ip=ipaddress,
            port=port,
            driver=self.connection.driver,
            extra=extra
        )

        # dealing with first scale/group configuration
        if vs:
            if 'scaleLoadBalancers' in vs and vs['scaleLoadBalancers']:
                scale_lb = vs['scaleLoadBalancers'][0]
                member_port = scale_lb['port']
                scale_grp_id = scale_lb['scaleGroupId']

                nodes = self.softlayer.list_auto_scale_group_members(\
                                       AutoScaleGroup(scale_grp_id,
                                       None, None, None, None, None))

                balancer._scale_members = []
                balancer._scale_members = self._to_members_from_scale_lb(
                                        nodes=nodes,
                                        port=member_port, balancer=balancer)

            balancer._members = []
            if 'serviceGroups' in vs and vs['serviceGroups']:
                svc_grp = vs['serviceGroups'][0]
                balancer._members = self._to_members(svc_grp['services'],
                                                balancer)

        return balancer

    def _to_members_from_scale_lb(self, nodes, port, balancer=None):
        return [self._to_member_from_scale_lb(n, port, balancer)\
                                             for n in nodes]

    def _to_member_from_scale_lb(self, n, port, balancer=None):
        ip = n.public_ips[0] if n.public_ips else None
        if not ip:
            ip = n.private_ips[0] if n.private_ips else '127.0.0.1'

        return Member(id=n.id, ip=ip, port=port, balancer=balancer)

    def _to_members(self, services, balancer=None):
        return [self._to_member(svc, balancer) for svc in services]

    def _to_member(self, svc, balancer=None):

        svc_id = svc['id']
        ip = svc['ipAddress']['ipAddress']
        port = svc['port']
        
        extra = {}
        extra['status'] = svc['status']
        extra['enabled'] = svc['enabled']
        return Member(id=svc_id, ip=ip, port=port, balancer=balancer,
                      extra=extra)
