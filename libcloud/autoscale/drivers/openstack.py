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
from datetime import datetime
import time

from libcloud.autoscale.base import AutoScaleDriver, AutoScaleGroup, \
    AutoScalePolicy
from libcloud.autoscale.types import Provider, AutoScaleAdjustmentType
from libcloud.common.types import LibcloudError

from libcloud.utils.misc import find, reverse_dict
from libcloud.utils.py3 import b

"""
OpenStack driver.
Autoscale support done through heat. API based on v1.0 (current):
http://developer.openstack.org/api-ref-orchestration-v1.html
"""
try:
    import simplejson as json
except ImportError:
    import json

from libcloud.common.openstack import OpenStackBaseConnection
from libcloud.common.openstack import OpenStackDriverMixin
from libcloud.common.openstack import OpenStackResponse

__all__ = [
    'OpenStack_Response',
    'OpenStackHeatConnection',
    'OpenStackAutoScaleDriver',
]

DEFAULT_API_VERSION = '1.0'

# use to tag stacks as auto-scale groups
SCALE_GROUP_RESOURCE_NAME = 'auto_scale_group'


class OpenStack_Response(OpenStackResponse):
    def __init__(self, *args, **kwargs):
        # done because of a circular reference from
        # NodeDriver -> Connection -> Response
        self.node_driver = OpenStackAutoScaleDriver
        super(OpenStack_Response, self).__init__(*args, **kwargs)


class OpenStackHeatConnection(OpenStackBaseConnection):
    # default config for http://devstack.org/
    service_type = 'orchestration'
    service_name = 'heat'
    service_region = 'RegionOne'

    responseCls = OpenStack_Response
    accept_format = 'application/json'
    default_content_type = 'application/json; charset=UTF-8'

    def encode_data(self, data):
        return json.dumps(data)


class OpenStackAutoScaleDriver(AutoScaleDriver, OpenStackDriverMixin):
    """
    Base OpenStack autoscale driver.
    """
    api_name = 'openstack'
    name = 'OpenStack'
    website = 'http://openstack.org/'
    connectionCls = OpenStackHeatConnection
    type = Provider.OPENSTACK

    _VALUE_TO_SCALE_ADJUSTMENT_TYPE_MAP = {
        'change_in_capacity': AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
        'exact_capacity': AutoScaleAdjustmentType.EXACT_CAPACITY,
        'percent_change_in_capacity': AutoScaleAdjustmentType.
        PERCENT_CHANGE_IN_CAPACITY
    }

    _SCALE_ADJUSTMENT_TYPE_TO_VALUE_MAP = reverse_dict(
        _VALUE_TO_SCALE_ADJUSTMENT_TYPE_MAP)

    def __init__(self, key, secret=None, secure=True, host=None, port=None,
                 api_version=DEFAULT_API_VERSION, **kwargs):
        if api_version != '1.0':
            raise NotImplementedError(
                "No OpenStackAutoScaleDriver found for API version %s" %
                (api_version))

        OpenStackDriverMixin.__init__(self, **kwargs)
        super(OpenStackAutoScaleDriver, self).__init__(
            key=key, secret=secret, secure=secure, host=host,
            port=port, api_version=api_version,
            **kwargs)

    def create_auto_scale_group(
            self, group_name, min_size, max_size, cooldown,
            termination_policies, balancer=None, **kwargs):
        """
        Create a new auto scale group.
        @inherits: :class:`AutoScaleDriver.create_auto_scale_group`

        The following keyword parameters are documented below:
        http://docs.openstack.org/hot-reference/content/OS__Nova__Server.html

        :keyword    ex_availability_zone: Nova availability zone for the group
                                          members.
        :type       ex_availability_zone: ``str``

        :keyword    ex_keyname: The name of the key pair.
        :type       ex_keyname: ``str``

        :keyword    ex_userdata: User data to be injected to group members.
        :type       ex_userdata: ``str``

        :keyword    ex_userdata: String containing user data.
        :type       ex_userdata: ``str``

        :keyword    ex_userdata_format: How the user_data should be formatted
                                        for the server.
        :type       ex_userdata_format: ``str``. Allowed values:
                                        HEAT_CFNTOOLS, RAW, SOFTWARE_CONFIG

        :keyword    ex_security_groups: List of security groups to assign to
                                        the members.
        :type       ex_security_groups: ``list`` of
                                        :class:`OpenStackSecurityGroup`

        :keyword    ex_metadata: Key/Value metadata to associate with the group
                                 members.
        :type       ex_metadata: ``dict``

        :keyword    ex_admin_pass: The root password for the group members.
        :type       ex_admin_pass: ``str``

        :keyword    ex_config_drive: If True enables metadata injection in a
                                     server through a configuration drive.
        :type       ex_config_drive: ``bool``

        :return: The newly created scale group.
        :rtype: :class:`.AutoScaleGroup`
        """
        # TODO: make this more general so that it waits on desired states.
        def _wait_for_creation(stack_name, stack_id):
            DEFAULT_TIMEOUT = 12000
            # 5 seconds
            POLL_INTERVAL = 5

            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                stack = self._get_stack(stack_name, stack_id)
                stack_status = stack['stack_status']
                if stack_status not in ['CREATE_COMPLETE', 'CREATE_FAILED']:
                    time.sleep(POLL_INTERVAL)
                else:
                    completed = True

            if not completed:
                raise LibcloudError('Group creation did not complete in %s'
                                    ' seconds' % (DEFAULT_TIMEOUT))

        server_params = self._to_virtual_guest_template(**kwargs)
        server_params['metadata']['metering.stack'] = \
            {'get_param': 'OS::stack_id'}
        # TODO: Add support for all parameters
        template = {
            'heat_template_version': '2013-05-23',
            # TODO: see if stacks can be tagged
            'description': SCALE_GROUP_RESOURCE_NAME,
            'resources': {
                group_name: {
                    'type': 'OS::Heat::AutoScalingGroup',
                    'properties': {
                        'min_size': min_size,
                        'max_size': max_size,
                        'resource': {
                            'type': 'OS::Nova::Server',
                            'properties': server_params,
                        },
                    },
                },
            },
            'outputs': {
                'policy_cooldown': {
                    'value': cooldown
                }
            }
        }
        data = {
            'stack_name': group_name,
            'template': template,
        }
        res = self.connection.request('/stacks', data=data,
                                      method='POST').object
        stack_id = res['stack']['id']
        _wait_for_creation(group_name, stack_id)
        return self._get_auto_scale_group(group_name, stack_id)

    def list_auto_scale_groups(self):
        res = self.connection.request('/stacks').object
        groups = []
        # filter auto-scale stacks
        for s in [s for s in res['stacks'] if s['description'] ==
                  SCALE_GROUP_RESOURCE_NAME]:
            groups.append(self._get_auto_scale_group(
                s['stack_name'], s['id']))
        return groups

    def list_auto_scale_group_members(self, group):
        # TODO: impl
        pass

    def create_auto_scale_policy(self, group, name, adjustment_type,
                                 scaling_adjustment):
        stack_name = group.name
        stack_id = group.id

        def _wait_for_update(stack_name, stack_id, pre_update_ts):
            DEFAULT_TIMEOUT = 600
            POLL_INTERVAL = 5

            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                stack = self._get_stack(stack_name, stack_id)
                stack_status = stack['stack_status']
                ts_completed = self._iso_to_datetime(
                    stack.get('updated_time')) > pre_update_ts
                if (stack_status == 'UPDATE_COMPLETE' and ts_completed) or \
                        stack_status == 'UPDATE_FAILED':
                    completed = True
                else:
                    time.sleep(POLL_INTERVAL)

            if not completed:
                raise LibcloudError('Policy creation did not complete in %s'
                                    ' seconds' % (DEFAULT_TIMEOUT))

        template_res = self._get_stack_template(stack_name, stack_id)
        template = {
            name: {
                'type': 'OS::Heat::ScalingPolicy',
                'properties': {
                    'cooldown': group.cooldown,
                    'adjustment_type': self._scale_adjustment_to_value(
                        adjustment_type),
                    'scaling_adjustment': scaling_adjustment,
                    'auto_scaling_group_id': {'get_resource': group.name},
                }
            }
        }

        template_res['resources'].update(template)

        pre_update_ts = self._stack_update(stack_name, stack_id, template_res)
        _wait_for_update(stack_name, stack_id, pre_update_ts)
        policies = self.list_auto_scale_policies(group)
        return [p for p in policies if p.name == name][0]

    def list_auto_scale_policies(self, group):
        template = self._get_stack_template(group.name, group.id)
        stack_name = group.name
        stack_id = group.id
        return [self._get_auto_scale_policy(k, stack_name, stack_id)
                for k in template['resources'] if
                template['resources'][k]['type'] == 'OS::Heat::ScalingPolicy']

    def delete_auto_scale_policy(self, policy):
        def _wait_for_update(stack_name, stack_id, pre_update_ts):
            DEFAULT_TIMEOUT = 600
            POLL_INTERVAL = 5

            end = time.time() + DEFAULT_TIMEOUT
            completed = False
            while time.time() < end and not completed:
                stack = self._get_stack(stack_name, stack_id)
                stack_status = stack['stack_status']
                ts_completed = self._iso_to_datetime(
                    stack.get('updated_time')) > pre_update_ts
                if (stack_status == 'UPDATE_COMPLETE' and ts_completed) or \
                        stack_status == 'UPDATE_FAILED':
                    completed = True
                else:
                    time.sleep(POLL_INTERVAL)

            if not completed:
                raise LibcloudError('Policy creation did not complete in %s'
                                    ' seconds' % (DEFAULT_TIMEOUT))
        stack_name = policy.extra['stack_name']
        stack_id = policy.extra['stack_id']
        template = self._get_stack_template(stack_name, stack_id)

        if policy.name in template['resources']:
            template['resources'].pop(policy.name)
            pre_update_ts = self._stack_update(stack_name, stack_id, template)
            _wait_for_update(stack_name, stack_id, pre_update_ts)

        return True

    def delete_auto_scale_group(self, group):
        stack_name = group.name
        stack_id = group.id
        return self.connection.request(
            '/stacks/%(stack_name)s/%(stack_id)s' %
            {'stack_name': stack_name, 'stack_id': stack_id},
            method='DELETE').success()

    def _get_auto_scale_group(self, stack_name, stack_id):
        template = self._get_stack_template(stack_name, stack_id)
        # resources is an array of resource dictionaries
        resources = self._get_stack_resources(stack_name, stack_id)
        # exactly one resource with this type
        key = find(
            template['resources'],
            lambda k: template['resources'][k]['type'] ==
            'OS::Heat::AutoScalingGroup')
        resource = find(
            resources['resources'],
            lambda r: r['resource_type'] == 'OS::Heat::AutoScalingGroup')
        if not (key and resource):
            raise LibcloudError(value='Group: %s not found' % stack_name,
                                driver=self.connection.driver)
        template['resources'][key]['properties']['cooldown'] = \
            int(template['outputs']['policy_cooldown']['value'])
        return self._to_autoscale_group(group_id=stack_id, group_name=key,
                                        template=template['resources'][key],
                                        resource=resource)

    def _to_autoscale_group(self, group_id, group_name, template,
                            resource):
        cooldown = template['properties']['cooldown']
        min_size = template['properties']['min_size']
        max_size = template['properties']['max_size']

        extra = {}
        extra['state'] = resource['resource_status']
        extra['resource_id'] = resource['logical_resource_id']
        extra['region'] = self.connection.service_region

        return AutoScaleGroup(id=group_id, name=group_name, cooldown=cooldown,
                              min_size=min_size, max_size=max_size,
                              termination_policies=[],
                              driver=self.connection.driver,
                              extra=extra)

    def _get_auto_scale_policy(self, name, stack_name, stack_id):
        template = self._get_stack_template(stack_name, stack_id)
        # resources is an array of dictionaries
        resources = self._get_stack_resources(stack_name, stack_id)
        resource = find(resources['resources'],
                        lambda r: r['resource_type'] ==
                        'OS::Heat::ScalingPolicy' and
                        r['resource_name'] == name)
        if not (name in template['resources'] and resource):
            raise LibcloudError(value='Policy: %s not found' % name,
                                driver=self.connection.driver)

        extra = dict(stack_name=stack_name, stack_id=stack_id)
        return self._to_autoscale_policy(name=name,
                                         template=template['resources'][name],
                                         resource=resource, extra=extra)

    def _to_autoscale_policy(self, name, template, resource,
                             extra=None):
        policy_id = resource['logical_resource_id']
        adj_type = template['properties']['adjustment_type']
        adjustment_type = self._value_to_scale_adjustment(adj_type)
        scaling_adjustment = template['properties']['scaling_adjustment']

        return AutoScalePolicy(id=policy_id, name=name,
                               adjustment_type=adjustment_type,
                               scaling_adjustment=int(scaling_adjustment),
                               driver=self.connection.driver, extra=extra)

    def _get_stack(self, stack_name, stack_id):
        res = self.connection.request(
            '/stacks/%(stack_name)s/%(stack_id)s' %
            {'stack_name': stack_name, 'stack_id': stack_id}).object

        return res['stack']

    def _get_stack_template(self, stack_name, stack_id):
        return self.connection.request(
            '/stacks/%(stack_name)s/%(stack_id)s/template' %
            {'stack_name': stack_name, 'stack_id': stack_id}).object

    def _get_stack_resources(self, stack_name, stack_id):
        return self.connection.request(
            '/stacks/%(stack_name)s/%(stack_id)s/resources' %
            {'stack_name': stack_name, 'stack_id': stack_id}).object

    def _stack_update(self, stack_name, stack_id, template):
        DEFAULT_TIMEOUT = 600
        data = {
            'timeout_mins': str(DEFAULT_TIMEOUT),
            'files': {},
            'environment': {},
            'template': template
        }

        pre_update_ts = self._iso_to_datetime(
            self._get_stack(stack_name, stack_id).get('updated_time'))

        self.connection.request(
            '/stacks/%(stack_name)s/%(stack_id)s' %
            {'stack_name': stack_name, 'stack_id': stack_id},
            data=data, method='PUT')
        return pre_update_ts

    def _to_virtual_guest_template(self, **attrs):
        """
        Return heat nova server resource based on supplied attributes.
        """
        server_params = {
            'metadata': attrs.get('ex_metadata', {}),
            'image': attrs['image'].name,
            'flavor': attrs['size'].id,
        }
        if 'name' in attrs:
            server_params['name'] = attrs['name']

        if 'ex_availability_zone' in attrs:
            server_params['availability_zone'] = attrs['ex_availability_zone']

        if 'ex_keyname' in attrs:
            server_params['key_name'] = attrs['ex_keyname']

        if 'ex_userdata' in attrs:
            server_params['user_data'] = base64.b64encode(
                b(attrs['ex_userdata'])).decode('ascii')

        if 'ex_userdata_format' in attrs:
            server_params['user_data_format'] = attrs['ex_userdata_format']

        if 'ex_admin_pass' in attrs:
            server_params['admin_pass'] = attrs['ex_admin_pass']

        if 'ex_config_drive' in attrs:
            server_params['config_drive'] = str(attrs['ex_config_drive'])

        if 'ex_security_groups' in attrs:
            server_params['security_groups'] = []
            for security_group in attrs['ex_security_groups']:
                name = security_group.name
                server_params['security_groups'].append({'name': name})

        return server_params

    def _iso_to_datetime(self, isodate):
        date_formats = ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z')
        _isodate = isodate or '1970-01-01T00:00:01Z'
        date = None

        for date_format in date_formats:
            try:
                date = datetime.strptime(_isodate, date_format)
            except ValueError:
                pass

            if date:
                break

        return date

    def _ex_connection_class_kwargs(self):
        return self.openstack_connection_kwargs()
