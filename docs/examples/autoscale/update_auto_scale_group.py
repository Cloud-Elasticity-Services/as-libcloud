from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.utoscale.types import Provider as as_provider

USER_NAME = 'your user name'
PASSWORD = 'your password'
TENANT_NAME = 'your tenant name'
AUTH_URL = 'http://1.2.3.4:5000'

as_driver = as_get_driver(as_provider.OPENSTACK)(
    USER_NAME, PASSWORD, ex_tenant_name=TENANT_NAME,
    ex_force_auth_url=AUTH_URL,
    ex_force_auth_version='2.0_password')

group = as_driver.list_auto_scale_groups()[0]
print ('Group before update %s' % group)

# Note: update is a syncronious operation, be patient
group = as_driver.update_auto_scale_group(group, min_size=2, max_size=4)
print ('Group after update %s' % group)
