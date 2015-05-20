from pprint import pprint

from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider

USER_NAME = 'your user name'
PASSWORD = 'your password'
TENANT_NAME = 'your tenant name'

as_driver = as_get_driver(as_provider.OPENSTACK)(
    USER_NAME, PASSWORD, ex_tenant_name=TENANT_NAME,
    ex_force_auth_url='http://1.2.3.4:5000',
    ex_force_auth_version='2.0_password')

groups = as_driver.list_auto_scale_groups()

policies = as_driver.list_auto_scale_policies(groups[0])
pprint(policies)
