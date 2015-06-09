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
Common / shared code for interacting against OpenStack orchestration service
(Heat).
"""

from libcloud.common.openstack import OpenStackResponse, \
    OpenStackBaseConnection
from libcloud.utils.misc import iso_to_datetime

try:
    import simplejson as json
except ImportError:
    import json

DEFAULT_API_VERSION = '1.0'

__all__ = [
    'OpenStackHeatResponse',
    'OpenStackHeatConnection',
]


class OpenStackHeatResponse(OpenStackResponse):
    pass


class OpenStackHeatConnection(OpenStackBaseConnection):
    service_type = 'orchestration'
    service_name = 'heat'
    service_region = 'RegionOne'

    responseCls = OpenStackHeatResponse
    accept_format = 'application/json'
    default_content_type = 'application/json; charset=UTF-8'

    def encode_data(self, data):
        return json.dumps(data)

    def get_stack(self, stack_name, stack_id):
        res = self.request(
            '/stacks/%(stack_name)s/%(stack_id)s' %
            {'stack_name': stack_name, 'stack_id': stack_id}).object

        return res['stack']

    def get_stack_template(self, stack_name, stack_id):
        return self.request(
            '/stacks/%(stack_name)s/%(stack_id)s/template' %
            {'stack_name': stack_name, 'stack_id': stack_id}).object

    def get_stack_resources(self, stack_name, stack_id):
        return self.request(
            '/stacks/%(stack_name)s/%(stack_id)s/resources' %
            {'stack_name': stack_name, 'stack_id': stack_id}).object

    def stack_update(self, stack_name, stack_id, template):
        DEFAULT_TIMEOUT = 600
        data = {
            'timeout_mins': str(DEFAULT_TIMEOUT),
            'files': {},
            'environment': {},
            'template': template
        }

        pre_update_ts = iso_to_datetime(
            self.get_stack(stack_name, stack_id).get('updated_time'))

        self.request(
            '/stacks/%(stack_name)s/%(stack_id)s' %
            {'stack_name': stack_name, 'stack_id': stack_id},
            data=data, method='PUT')
        return pre_update_ts
