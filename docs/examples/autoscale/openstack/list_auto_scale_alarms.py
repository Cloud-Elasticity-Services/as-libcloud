from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider

from libcloud.monitor.providers import get_driver as monitor_get_driver
from libcloud.monitor.types import Provider as monitor_provider

USER_NAME = 'your user name'
PASSWORD = 'your password'
TENANT_NAME = 'your tenant name'
AUTH_URL = 'http://1.2.3.4:5000'

as_driver = as_get_driver(as_provider.OPENSTACK)(
    USER_NAME, PASSWORD, ex_tenant_name=TENANT_NAME,
    ex_force_auth_url=AUTH_URL,
    ex_force_auth_version='2.0_password')
mon_driver = monitor_get_driver(monitor_provider.OPENSTACK)(
    USER_NAME, PASSWORD, ex_tenant_name=TENANT_NAME,
    ex_force_auth_url=AUTH_URL,
    ex_force_auth_version='2.0_password')

group = as_driver.list_auto_scale_groups()[0]
policy = as_driver.list_auto_scale_policies(group)[0]
alarms = mon_driver.list_auto_scale_alarms(policy)
print alarms
