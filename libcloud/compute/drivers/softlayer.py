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
"""
Softlayer driver
"""

import time
try:
    from Crypto.PublicKey import RSA
    crypto = True
except ImportError:
    crypto = False

from libcloud.utils.misc import find
from libcloud.common.base import ConnectionUserAndKey
from libcloud.common.xmlrpc import XMLRPCResponse, XMLRPCConnection
from libcloud.common.types import InvalidCredsError, LibcloudError, ResourceNotFoundError
from libcloud.compute.types import Provider, NodeState, ScalingPolicyType,\
    ScalingPolicyOperator
from libcloud.compute.base import NodeDriver, Node, NodeLocation, NodeSize, \
    NodeImage, KeyPair, AutoScalingGroup, ScalingPolicy, Alarm
from libcloud.compute.types import KeyPairDoesNotExistError

DEFAULT_DOMAIN = 'example.com'
DEFAULT_CPU_SIZE = 1
DEFAULT_RAM_SIZE = 2048
DEFAULT_DISK_SIZE = 100
DEFAULT_TIMEOUT = 12000

DATACENTERS = {
    'hou02': {'country': 'US'},
    'sea01': {'country': 'US', 'name': 'Seattle - West Coast U.S.'},
    'wdc01': {'country': 'US', 'name': 'Washington, DC - East Coast U.S.'},
    'dal01': {'country': 'US'},
    'dal02': {'country': 'US'},
    'dal04': {'country': 'US'},
    'dal05': {'country': 'US', 'name': 'Dallas - Central U.S.'},
    'dal06': {'country': 'US'},
    'dal07': {'country': 'US'},
    'sjc01': {'country': 'US', 'name': 'San Jose - West Coast U.S.'},
    'sng01': {'country': 'SG', 'name': 'Singapore - Southeast Asia'},
    'ams01': {'country': 'NL', 'name': 'Amsterdam - Western Europe'},
}

NODE_STATE_MAP = {
    'RUNNING': NodeState.RUNNING,
    'HALTED': NodeState.UNKNOWN,
    'PAUSED': NodeState.UNKNOWN,
    'INITIATING': NodeState.PENDING
}

SL_BASE_TEMPLATES = [
    {
        'name': '1 CPU, 1GB ram, 25GB',
        'ram': 1024,
        'disk': 25,
        'cpus': 1,
    }, {
        'name': '1 CPU, 1GB ram, 100GB',
        'ram': 1024,
        'disk': 100,
        'cpus': 1,
    }, {
        'name': '1 CPU, 2GB ram, 100GB',
        'ram': 2 * 1024,
        'disk': 100,
        'cpus': 1,
    }, {
        'name': '1 CPU, 4GB ram, 100GB',
        'ram': 4 * 1024,
        'disk': 100,
        'cpus': 1,
    }, {
        'name': '2 CPU, 2GB ram, 100GB',
        'ram': 2 * 1024,
        'disk': 100,
        'cpus': 2,
    }, {
        'name': '2 CPU, 4GB ram, 100GB',
        'ram': 4 * 1024,
        'disk': 100,
        'cpus': 2,
    }, {
        'name': '2 CPU, 8GB ram, 100GB',
        'ram': 8 * 1024,
        'disk': 100,
        'cpus': 2,
    }, {
        'name': '4 CPU, 4GB ram, 100GB',
        'ram': 4 * 1024,
        'disk': 100,
        'cpus': 4,
    }, {
        'name': '4 CPU, 8GB ram, 100GB',
        'ram': 8 * 1024,
        'disk': 100,
        'cpus': 4,
    }, {
        'name': '6 CPU, 4GB ram, 100GB',
        'ram': 4 * 1024,
        'disk': 100,
        'cpus': 6,
    }, {
        'name': '6 CPU, 8GB ram, 100GB',
        'ram': 8 * 1024,
        'disk': 100,
        'cpus': 6,
    }, {
        'name': '8 CPU, 8GB ram, 100GB',
        'ram': 8 * 1024,
        'disk': 100,
        'cpus': 8,
    }, {
        'name': '8 CPU, 16GB ram, 100GB',
        'ram': 16 * 1024,
        'disk': 100,
        'cpus': 8,
    }]

SL_TEMPLATES = {}
for i, template in enumerate(SL_BASE_TEMPLATES):
    # Add local disk templates
    local = template.copy()
    local['local_disk'] = True
    SL_TEMPLATES[i] = local


class SoftLayerException(LibcloudError):
    """
    Exception class for SoftLayer driver
    """
    pass


class SoftLayerResponse(XMLRPCResponse):
    defaultExceptionCls = SoftLayerException
    exceptions = {
        'SoftLayer_Account': InvalidCredsError,
        'SoftLayer_Exception_ObjectNotFound': ResourceNotFoundError
    }


class SoftLayerConnection(XMLRPCConnection, ConnectionUserAndKey):
    responseCls = SoftLayerResponse
    host = 'api.softlayer.com'
    endpoint = '/xmlrpc/v3'

    def request(self, service, method, *args, **kwargs):
        headers = {}
        headers.update(self._get_auth_headers())
        headers.update(self._get_init_params(service, kwargs.get('id')))
        headers.update(
            self._get_object_mask(service, kwargs.get('object_mask')))
        headers.update(
            self._get_object_mask(service, kwargs.get('object_mask')))

        args = ({'headers': headers}, ) + args
        endpoint = '%s/%s' % (self.endpoint, service)
        return super(SoftLayerConnection, self).request(method, *args,
                                                        **{'endpoint':
                                                            endpoint})

    def _get_auth_headers(self):
        return {
            'authenticate': {
                'username': self.user_id,
                'apiKey': self.key
            }
        }

    def _get_init_params(self, service, id):
        if id is not None:
            return {
                '%sInitParameters' % service: {'id': id}
            }
        else:
            return {}

    def _get_object_mask(self, service, mask):
        if mask is not None:
            return {
                '%sObjectMask' % service: {'mask': mask}
            }
        else:
            return {}


class SoftLayerNodeDriver(NodeDriver):
    """
    SoftLayer node driver

    Extra node attributes:
        - password: root password
        - hourlyRecurringFee: hourly price (if applicable)
        - recurringFee      : flat rate    (if applicable)
        - recurringMonths   : The number of months in which the recurringFee
         will be incurred.
    """

    
    operator_mapping = {ScalingPolicyOperator.GE: '>', 
                     ScalingPolicyOperator.GT: '>',
                     ScalingPolicyOperator.LE: '<',
                     ScalingPolicyOperator.LT: '<'}

    scaleType_mapping = {ScalingPolicyType.CHANGE_IN_CAPACITY: 'RELATIVE', 
                         ScalingPolicyType.EXACT_CAPACITY: 'ABSOLUTE',
                         ScalingPolicyType.PERCENT_CHANGE_IN_CAPACITY: 'PERCENT'}

    connectionCls = SoftLayerConnection
    name = 'SoftLayer'
    website = 'http://www.softlayer.com/'
    type = Provider.SOFTLAYER

    features = {'create_node': ['generates_password', 'ssh_key']}

    def _to_node(self, host):
        try:
            password = \
                host['operatingSystem']['passwords'][0]['password']
        except (IndexError, KeyError):
            password = None

        hourlyRecurringFee = host.get('billingItem', {}).get(
            'hourlyRecurringFee', 0)
        recurringFee = host.get('billingItem', {}).get('recurringFee', 0)
        recurringMonths = host.get('billingItem', {}).get('recurringMonths', 0)
        createDate = host.get('createDate', None)
        provision = host.get('provisionDate', None)

        # When machine is launching it gets state halted
        # we change this to pending
        state = NODE_STATE_MAP.get(host['powerState']['keyName'],
                                   NodeState.UNKNOWN)

        if not password and state == NodeState.UNKNOWN:
            state = NODE_STATE_MAP['INITIATING']

        public_ips = []
        private_ips = []

        if 'primaryIpAddress' in host:
            public_ips.append(host['primaryIpAddress'])

        if 'primaryBackendIpAddress' in host:
            private_ips.append(host['primaryBackendIpAddress'])

        image = host.get('operatingSystem', {}).get('softwareLicense', {}) \
                    .get('softwareDescription', {}) \
                    .get('longDescription', None)

        return Node(
            id=host['id'],
            name=host['fullyQualifiedDomainName'],
            state=state,
            public_ips=public_ips,
            private_ips=private_ips,
            driver=self,
            extra={
                'hostname': host['hostname'],
                'fullyQualifiedDomainName': host['fullyQualifiedDomainName'],
                'password': password,
                'maxCpu': host.get('maxCpu', None),
                'datacenter': host.get('datacenter', {}).get('longName', None),
                'maxMemory': host.get('maxMemory', None),
                'image': image,
                'hourlyRecurringFee': hourlyRecurringFee,
                'recurringFee': recurringFee,
                'recurringMonths': recurringMonths,
                'created': createDate,
                'provision': provision
            }
        )

    def destroy_node(self, node):
        self.connection.request(
            'SoftLayer_Virtual_Guest', 'deleteObject', id=node.id
        )
        return True

    def reboot_node(self, node):
        self.connection.request(
            'SoftLayer_Virtual_Guest', 'rebootSoft', id=node.id
        )
        return True

    def ex_stop_node(self, node):
        self.connection.request(
            'SoftLayer_Virtual_Guest', 'powerOff', id=node.id
        )
        return True

    def ex_start_node(self, node):
        self.connection.request(
            'SoftLayer_Virtual_Guest', 'powerOn', id=node.id
        )
        return True

    def _get_order_information(self, node_id, timeout=1200, check_interval=5):
        mask = {
            'billingItem': '',
            'powerState': '',
            'operatingSystem': {'passwords': ''},
            'provisionDate': '',
        }

        for i in range(0, timeout, check_interval):
            res = self.connection.request(
                'SoftLayer_Virtual_Guest',
                'getObject',
                id=node_id,
                object_mask=mask
            ).object

            if res.get('provisionDate', None):
                return res

            time.sleep(check_interval)

        raise SoftLayerException('Timeout on getting node details')

    def create_node(self, **kwargs):
        """Create a new SoftLayer node

        @inherits: :class:`NodeDriver.create_node`

        :keyword    ex_domain: e.g. libcloud.org
        :type       ex_domain: ``str``
        :keyword    ex_cpus: e.g. 2
        :type       ex_cpus: ``int``
        :keyword    ex_disk: e.g. 100
        :type       ex_disk: ``int``
        :keyword    ex_ram: e.g. 2048
        :type       ex_ram: ``int``
        :keyword    ex_bandwidth: e.g. 100
        :type       ex_bandwidth: ``int``
        :keyword    ex_local_disk: e.g. True
        :type       ex_local_disk: ``bool``
        :keyword    ex_datacenter: e.g. Dal05
        :type       ex_datacenter: ``str``
        :keyword    ex_os: e.g. UBUNTU_LATEST
        :type       ex_os: ``str``
        :keyword    ex_keyname: The name of the key pair
        :type       ex_keyname: ``str``
        """
        name = kwargs['name']
        os = 'DEBIAN_LATEST'
        if 'ex_os' in kwargs:
            os = kwargs['ex_os']
        elif 'image' in kwargs:
            os = kwargs['image'].id

        size = kwargs.get('size', NodeSize(id=123, name='Custom', ram=None,
                                           disk=None, bandwidth=None,
                                           price=None,
                                           driver=self.connection.driver))
        ex_size_data = SL_TEMPLATES.get(int(size.id)) or {}
        # plan keys are ints
        cpu_count = kwargs.get('ex_cpus') or ex_size_data.get('cpus') or \
            DEFAULT_CPU_SIZE
        ram = kwargs.get('ex_ram') or ex_size_data.get('ram') or \
            DEFAULT_RAM_SIZE
        bandwidth = kwargs.get('ex_bandwidth') or size.bandwidth or 10
        hourly = 'true' if kwargs.get('ex_hourly', True) else 'false'

        local_disk = 'true'
        if ex_size_data.get('local_disk') is False:
            local_disk = 'false'

        if kwargs.get('ex_local_disk') is False:
            local_disk = 'false'

        disk_size = DEFAULT_DISK_SIZE
        if size.disk:
            disk_size = size.disk
        if kwargs.get('ex_disk'):
            disk_size = kwargs.get('ex_disk')

        datacenter = ''
        if 'ex_datacenter' in kwargs:
            datacenter = kwargs['ex_datacenter']
        elif 'location' in kwargs:
            datacenter = kwargs['location'].id

        domain = kwargs.get('ex_domain')
        if domain is None:
            if name.find('.') != -1:
                domain = name[name.find('.') + 1:]
        if domain is None:
            # TODO: domain is a required argument for the Sofylayer API, but it
            # it shouldn't be.
            domain = DEFAULT_DOMAIN

        newCCI = {
            'hostname': name,
            'domain': domain,
            'startCpus': cpu_count,
            'maxMemory': ram,
            'networkComponents': [{'maxSpeed': bandwidth}],
            'hourlyBillingFlag': hourly,
            'operatingSystemReferenceCode': os,
            'localDiskFlag': local_disk,
            'blockDevices': [
                {
                    'device': '0',
                    'diskImage': {
                        'capacity': disk_size,
                    }
                }
            ]

        }

        if datacenter:
            newCCI['datacenter'] = {'name': datacenter}

        if 'ex_keyname' in kwargs:
            newCCI['sshKeys'] = [self._key_name_to_id(kwargs['ex_keyname'])]

        res = self.connection.request(
            'SoftLayer_Virtual_Guest', 'createObject', newCCI
        ).object

        node_id = res['id']
        raw_node = self._get_order_information(node_id)

        return self._to_node(raw_node)

    def list_key_pairs(self):
        result = self.connection.request(
            'SoftLayer_Account', 'getSshKeys'
        ).object
        elems = [x for x in result]
        key_pairs = self._to_key_pairs(elems=elems)
        return key_pairs

    def get_key_pair(self, name):
        key_id = self._key_name_to_id(name=name)
        result = self.connection.request(
            'SoftLayer_Security_Ssh_Key', 'getObject', id=key_id
        ).object
        return self._to_key_pair(result)

    # TODO: Check this with the libcloud guys,
    # can we create new dependencies?
    def create_key_pair(self, name, ex_size=4096):
        if crypto is False:
            raise NotImplementedError('create_key_pair needs'
                                      'the pycrypto library')
        key = RSA.generate(ex_size)
        new_key = {
            'key': key.publickey().exportKey('OpenSSH'),
            'label': name,
            'notes': '',
        }
        result = self.connection.request(
            'SoftLayer_Security_Ssh_Key', 'createObject', new_key
        ).object
        result['private'] = key.exportKey('PEM')
        return self._to_key_pair(result)

    def import_key_pair_from_string(self, name, key_material):
        new_key = {
            'key': key_material,
            'label': name,
            'notes': '',
        }
        result = self.connection.request(
            'SoftLayer_Security_Ssh_Key', 'createObject', new_key
        ).object

        key_pair = self._to_key_pair(result)
        return key_pair

    def delete_key_pair(self, key_pair):
        key = self._key_name_to_id(key_pair)
        result = self.connection.request(
            'SoftLayer_Security_Ssh_Key', 'deleteObject', id=key
        ).object
        return result

    def _to_image(self, img):
        return NodeImage(
            id=img['template']['operatingSystemReferenceCode'],
            name=img['itemPrice']['item']['description'],
            driver=self.connection.driver
        )

    def list_images(self, location=None):
        result = self.connection.request(
            'SoftLayer_Virtual_Guest', 'getCreateObjectOptions'
        ).object
        return [self._to_image(i) for i in result['operatingSystems']]

    def _to_size(self, id, size):
        return NodeSize(
            id=id,
            name=size['name'],
            ram=size['ram'],
            disk=size['disk'],
            bandwidth=size.get('bandwidth'),
            price=None,
            driver=self.connection.driver,
        )

    def list_images_private(self, location=None):
        
        mask = { 'id': '',
            'accountId': '',
            'name': '',
            'globalIdentifier': '',
            'parentId': ''
            }
        
        result = self.connection.request(
            'SoftLayer_Account', 'getPrivateBlockDeviceTemplateGroups', object_mask=mask
        ).object
        print 'RESULT: %s' % result
        return result

    def list_sizes(self, location=None):
        return [self._to_size(id, s) for id, s in SL_TEMPLATES.items()]

    def _to_loc(self, loc):
        country = 'UNKNOWN'
        loc_id = loc['template']['datacenter']['name']
        name = loc_id

        if loc_id in DATACENTERS:
            country = DATACENTERS[loc_id]['country']
            name = DATACENTERS[loc_id].get('name', loc_id)
        return NodeLocation(id=loc_id, name=name,
                            country=country, driver=self)

    def list_locations(self):
        res = self.connection.request(
            'SoftLayer_Virtual_Guest', 'getCreateObjectOptions'
        ).object
        return [self._to_loc(l) for l in res['datacenters']]

    def list_nodes(self):
        mask = {
            'virtualGuests': {
                'powerState': '',
                'hostname': '',
                'maxMemory': '',
                'datacenter': '',
                'operatingSystem': {'passwords': ''},
                'billingItem': '',
            },
        }
        res = self.connection.request(
            'SoftLayer_Account',
            'getVirtualGuests',
            object_mask=mask
        ).object
        return [self._to_node(h) for h in res]

    def _to_key_pairs(self, elems):
        key_pairs = [self._to_key_pair(elem=elem) for elem in elems]
        return key_pairs

    def _to_key_pair(self, elem):
        key_pair = KeyPair(name=elem['label'],
                           public_key=elem['key'],
                           fingerprint=elem['fingerprint'],
                           private_key=elem.get('private', None),
                           driver=self,
                           extra={'id': elem['id']})
        return key_pair

    def _key_name_to_id(self, name):
        result = self.connection.request(
            'SoftLayer_Account', 'getSshKeys'
        ).object
        key_id = [x for x in result if x['label'] == name]
        if len(key_id) == 0:
            raise KeyPairDoesNotExistError(name, self)
        else:
            return int(key_id[0]['id'])


    def get_auto_scale_group_instances(self, group_id):
        mask = { 'virtualGuest': {
            'billingItem': '',
            'powerState': '',
            'operatingSystem': {'passwords': ''},
            'provisionDate': ''
            }
                }
        res = self.connection.request('SoftLayer_Scale_Group', 
                                      'getVirtualGuestMembers',
                                       id=group_id).object

        nodes = []
        for r in res:
            # NOTE: r[id]  is ID of virtual guest member
            #(not instance itself)
            res_node = self.connection.request(
                'SoftLayer_Scale_Member_Virtual_Guest',
                'getVirtualGuest', id=r['id'],
                object_mask=mask
            ).object

            if res_node:
                nodes.append(self._to_node(res_node))

        return nodes

    def get_auto_scale_group(self, group_id):
        res = self.connection.request('SoftLayer_Scale_Group', 
                                       'getObject', id=group_id).object
        group = self._to_scaling_group(res)

        return group

    def list_auto_scale_groups(self):
        res = self.connection.request('SoftLayer_Account', 
                                       'getScaleGroups').object
        return self._to_scaling_groups(res)

    def get_group_status(self, group_id):
        res = self.connection.request('SoftLayer_Scale_Group',
                                      'getStatus', id=group_id).object
        return res['name']

    def _to_scaling_groups(self, res):
        groups = [self._to_scaling_group(grp) for grp in res]
        return groups

    def _to_scaling_group(self, grp):
        print 'Turn group=%s' % grp
        
        grp_id  = grp['id']
        name = grp['name']
        cooldown = grp['cooldown']
        min_size = grp['minimumMemberCount']
        max_size = grp['maximumMemberCount']
        
        extra = {}
        extra['id'] = grp_id
        extra['region'] = 'softlayer' # getattr(self, 'region', '')
        extra['regionalGroupId'] = grp['regionalGroupId']
        extra['suspendedFlag'] = grp['suspendedFlag']
        extra['terminationPolicyId'] = grp['terminationPolicyId']
        
        return AutoScalingGroup(id=grp_id, name=name, cooldown=cooldown,
                                min_size=min_size, max_size=max_size,
                                driver=self.connection.driver,
                                extra=extra)

    def create_auto_scale_group(self, **kwargs):

        # retrieve all available regions to extract the
        # matched id
        ex_region_id = None
        res = self.connection.request(
            'SoftLayer_Location_Group_Regional',
            'getAllObjects').object
        print 'Location groups: %s' % res
        for r in res:
            if r['name'] == kwargs['ex_region']:
                ex_region_id = r['id']
        if not ex_region_id:
            raise SoftLayerException('Unable to find region id for region: %s' % \
                                     kwargs['ex_region'])
        
        template = {
        'hostname': kwargs['ex_instance_name'],
        'notes': kwargs['ex_instance_name'],
        'domain': 'softlayer.com',
        'startCpus': 1,
        'maxMemory': 2048,
        'networkComponents': [{'maxSpeed': 10}],
        'hourlyBillingFlag': 'false',
        'blockDeviceTemplateGroup': kwargs['image'].extra, # this is the entire template_group...
        'localDiskFlag': 'true',
        'datacenter': {'name': kwargs['ex_datacenter']},
        'userData': [{'value': kwargs['ex_user_data']}]
        }

        def _wait_for_creation(group_id):
            # 5 seconds
            POLL_INTERVAL = 5
        
            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                status_name = self.get_group_status(group_id)
                if status_name != 'Active':
                    print 'Group status not active [status=%(status)s]. Waiting....' % {'status': status_name}
                    time.sleep(POLL_INTERVAL)
                else:
                    completed = True
        
            if not completed:
                raise LibcloudError('Group creation did not complete in %s seconds' %
                                    (DEFAULT_TIMEOUT))
            
        data = {}
        data['name'] = kwargs['name']
        data['maximumMemberCount'] = kwargs['max_size']
        data['minimumMemberCount'] = kwargs['min_size']
        data['cooldown'] = kwargs['cooldown']

        data['regionalGroupId'] = ex_region_id
        data['suspendedFlag'] = False
        # 'OLDEST'
        data['terminationPolicyId'] = 3
        data['virtualGuestMemberTemplate'] = template

        res = self.connection.request('SoftLayer_Scale_Group', 
                                       'createObject',
                                       data).object
        print 'Successfully created group %(id)s' % {'id': res['id']}
        
        _wait_for_creation(res['id'])
        
        res = self.connection.request('SoftLayer_Scale_Group', 
                                       'getObject', id=res['id']).object
        group = self._to_scaling_group(res)

        return group


    def _to_scaling_policy(self, plc):
        print 'Turn policy=%s' % plc

        plc_id = plc['id']
        name = plc['name']

        adj_type = None
        adjustment_type = None
        scaling_adjustment = None

        if plc.get('scaleActions', []):
                    
            adj_type = plc['scaleActions'][0]['scaleType']
            adjustment_type= find(self.scaleType_mapping,
                            lambda e: self.scaleType_mapping[e] == adj_type)
            if not adjustment_type:
                raise Exception('Illegal adjustment_type value [adj_type=%(adj_type)s]' \
                                % {'adj_type': adj_type})
            scaling_adjustment = plc['scaleActions'][0]['amount']
        
        return ScalingPolicy(id=plc_id, name=name, adjustment_type=adjustment_type,
                                scaling_adjustment=scaling_adjustment,
                                driver=self.connection.driver)


    def create_policy(self, group_id, **kwargs):

        data = {}
        data['name'] = kwargs['name']
        data['scaleGroupId'] = int(group_id)
 
        policy_action = {}
        policy_action['typeId'] = 1 # 'SCALE'
        policy_action['scaleType'] = \
                           self.scaleType_mapping[kwargs['adjustment_type']]
        policy_action['amount'] = kwargs['scaling_adjustment']

        data['scaleActions'] = [policy_action]
        
        print 'Creating policy with an action %(policy)s ...' % {'policy': data}
        res = self.connection.request('SoftLayer_Scale_Policy',
                                       'createObject', data).object
        print 'Successfully created policy %(id)s' % {'id': res['id']}

        res = self.connection.request('SoftLayer_Scale_Policy',
                                       'getObject', id=res['id']).object
        policy = self._to_scaling_policy(res)

        return policy

    def _to_alarm(self, alrm):

        print 'Turn alarm=%s' % alrm
        
        alrm_id = alrm['id']

        metric_name = None
        operator = None
        period = None
        threshold =None

        if alrm.get('watches', []):
        
            metric_name = alrm['watches'][0]['metric'] 
            op = alrm['watches'][0]['operator']
            operator = find(self.operator_mapping,
                            lambda e: self.operator_mapping[e] == op)
            if not operator:
                raise Exception('Illegal operator value [op=%(op)s]' \
                                % {'op': op})
    
            period = alrm['watches'][0]['period']
            threshold = alrm['watches'][0]['value']

        return Alarm(id=alrm_id, metric_name=metric_name, operator=operator,
                                period=period, threshold=threshold,
                                driver=self.connection.driver)

    def create_alarm(self, policy_id, **kwargs):

        data = {}
        data['typeId'] = 3 # 'RESOURCE_USE'
        data['scalePolicyId'] = policy_id
         
        trigger_watch = {}
        trigger_watch['algorithm'] = 'EWMA'
        trigger_watch['metric'] = kwargs['metric_name']
        trigger_watch['operator'] = \
                           self.operator_mapping[kwargs['operator']]
        trigger_watch['period'] = kwargs['period']
        trigger_watch['value'] = kwargs['threshold']
 
        data['watches'] = [trigger_watch]

        print 'Creating trigger with a watch %(trigger)s ...' % {'trigger': data}
        res = self.connection.request('SoftLayer_Scale_Policy_Trigger_ResourceUse',
                                       'createObject', data).object
        print 'Successfully created trigger %(id)s' % {'id': res['id']}

        res = self.connection.request('SoftLayer_Scale_Policy_Trigger_ResourceUse',
                                       'getObject', id=res['id']).object
        alarm = self._to_alarm(res)

        return alarm

    def delete_auto_scale_group(self, group):
        
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
                    # for now treat this as not found
                    completed = True
            if not completed:
                raise LibcloudError('Operation did not complete in %s seconds' %
                                    (DEFAULT_TIMEOUT))

        self.connection.request(
            'SoftLayer_Scale_Group', 'forceDeleteObject', id=group.id).object

        _wait_for_deletion(group.id)
        
        return True

    def get_all_regional_groups(self):
        
        res = self.connection.request(
            'SoftLayer_Location_Group_Regional', 'getAllObjects').object
        print res

