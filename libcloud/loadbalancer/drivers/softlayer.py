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

from libcloud.utils.misc import find, reverse_dict
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
        'SHORTEST_RESPONSE': Algorithm.SHORTEST_RESPONSE,
        'PERSISTENT_IP': Algorithm.PERSISTENT_IP
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
                'loadBalancerHardware': {
                    'datacenter': ''
                },
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


    def ex_add_service_group(self, balancer, port=80,
                          protocol='http', algorithm=DEFAULT_ALGORITHM,
                          ex_allocation=100):
        """
        Adds a new service group to the load balancer.

        :param balancer: The loadbalancer
        :type  balancer: :class:`LoadBalancer`

        :param port: Port of the service group, defaults to 80
        :type  port: ``int``

        :param protocol: Loadbalancer protocol, defaults to http.
        :type  protocol: ``str``

        :param algorithm: Load balancing algorithm, defaults to
                            Algorithm.ROUND_ROBIN
        :type  algorithm: :class:`Algorithm`

        :param ex_allocation: The percentage of the total connection 
                              allocations to allocate for this group.
        :type  ex_allocation: ``int``

        """
        _types = self._get_routing_types()
        _methods = self._get_routing_methods()

        rt = find(_types, lambda t: t['keyname'] == protocol.upper())
        if not rt:
            raise LibcloudError(value='Invalid protocol %s' % protocol,
                                driver=self)

        value = self._algorithm_to_value(algorithm)
        meth = find(_methods, lambda m: m['keyname'] == value)
        if not meth:
            raise LibcloudError(value='Invalid algorithm %s' % algorithm,
                                driver=self)

        mask = {
                'virtualServers': {
                    'serviceGroups': ''
#                     {
#                         'routingMethod': '',
#                         'routingType': '',
#                     }
                }
        }

        service_template = {
            'port': port,
            'allocation': ex_allocation,
            'serviceGroups': [
                {
                    'routingTypeId': rt['id'],
                    'routingMethodId': meth['id']

# NOTE: the following does not work..
#                     'routingType': {
#                         'keyname': protocol.upper()
#                     },
#                     'routingMethod': {
#                         'keyname': self._algorithm_to_value(algorithm)
#                     }
                }
            ]
        }

        # get balancer vip object
        res = self.connection.request(lb_service, 'getObject',
                                      object_mask=mask, id=balancer.id).object
        res['virtualServers'].append(service_template)
        self.connection.request(lb_service, 'editObject', res, id=balancer.id)
        return True

    def ex_delete_service_group(self, balancer, port):
        """
        Delete a service group from the load balancer

        :type  balancer: :class:`LoadBalancer`

        :param port: Port of the service group to be removed. 
        Note: In Softlayer, loadbalancer can not have two service groups with
        same port.
        :type  port: ``int``

        """
        def _locate_group_service(res, port):

            vs = None

            for vs in res['virtualServers']:
                if vs['port'] == port:
                    return vs

        mask = {
                'virtualServers': {
                    'serviceGroups': {
                    }
                }
        }
        
        # get balancer vip object
        res = self.connection.request(lb_service, 'getObject',
                                      object_mask=mask, id=balancer.id).object
        vs = _locate_group_service(res, port)
        if vs:
            vs_service = 'SoftLayer_Network_Application_Delivery_Controller_'\
            'LoadBalancer_VirtualServer'
            self.connection.request(vs_service, 'deleteObject', id=vs['id']).\
                                    object
        else:
            raise LibcloudError(value='No service_group found for port: %s' %\
                                port, driver=self)

        return True

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

        extra = {}
        extra['ssl_active'] = lb['sslActiveFlag']
        extra['ssl_enabled'] = lb['sslEnabledFlag']
        extra['ha'] = lb['highAvailabilityFlag']
        extra['datacenter'] = lb['loadBalancerHardware'][0]\
                              ['datacenter']['name']

        vs = lb['virtualServers'][0] if lb['virtualServers'] else None

        if vs:
            port = vs['port']
            if vs['serviceGroups']:
                srvgrp = vs['serviceGroups'][0]
                routing_method = srvgrp['routingMethod']['keyname']
                routing_type = srvgrp['routingType']['keyname']
                try:
                    extra['algorithm'] = self.\
                                        _value_to_algorithm(routing_method)
                except:
                    pass
                extra['protocol'] = routing_type.lower()

        if not vs:
            port = 0

        balancer = LoadBalancer(
            id=lb['id'],
            name='',
            state=State.UNKNOWN,
            ip=ipaddress,
            port=port,
            driver=self.connection.driver,
            extra=extra
        )

        # populate members
        if vs:
            if vs['scaleLoadBalancers']:
                scale_lb = vs['scaleLoadBalancers'][0]
                member_port = scale_lb['port']
                scale_grp_id = scale_lb['scaleGroupId']

                nodes = self.softlayer.list_auto_scale_group_members(\
                                       AutoScaleGroup(scale_grp_id,
                                       None, None, None, None, None))

                balancer._scale_members = [self._to_member_from_scale_lb(
                                           n, member_port, balancer)\
                                           for n in nodes]

            if vs['serviceGroups']:
                srvgrp = vs['serviceGroups'][0]
                balancer._members = [self._to_member(srv, balancer)\
                                     for srv in srvgrp['services']]

        return balancer

    def _to_member_from_scale_lb(self, n, port, balancer=None):
        ip = n.public_ips[0] if n.public_ips else None
        if not ip:
            ip = n.private_ips[0] if n.private_ips else '127.0.0.1'

        return Member(id=n.id, ip=ip, port=port, balancer=balancer)

    def _to_member(self, svc, balancer=None):

        svc_id = svc['id']
        ip = svc['ipAddress']['ipAddress']
        port = svc['port']
        
        extra = {}
        extra['status'] = svc['status']
        extra['enabled'] = svc['enabled']
        return Member(id=svc_id, ip=ip, port=port, balancer=balancer,
                      extra=extra)
