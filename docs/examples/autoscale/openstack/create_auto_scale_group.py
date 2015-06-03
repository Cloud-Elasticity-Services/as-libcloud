from pprint import pprint

from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider
from libcloud.autoscale.types import AutoScaleTerminationPolicy

from libcloud.compute.providers import get_driver \
    as compute_get_driver
from libcloud.compute.types import Provider as compute_provider

USER_NAME = 'your user name'
PASSWORD = 'your password'
TENANT_NAME = 'your tenant name'
AUTH_URL = 'http://1.2.3.4:5000'

# Initialize the drivers
driver = compute_get_driver(compute_provider.OPENSTACK)(
    USER_NAME, PASSWORD, ex_tenant_name=TENANT_NAME,
    ex_force_auth_url=AUTH_URL,
    ex_force_auth_version='2.0_password')
as_driver = as_get_driver(as_provider.OPENSTACK)(
    USER_NAME, PASSWORD, ex_tenant_name=TENANT_NAME,
    ex_force_auth_url=AUTH_URL,
    ex_force_auth_version='2.0_password')

image = driver.list_images()[0]
location = driver.list_locations()[0]
size = driver.list_sizes()[0]

# create an auto scale group
group = as_driver.create_auto_scale_group(
    group_name='libcloud-group', min_size=1, max_size=5,
    cooldown=300,
    termination_policies=[AutoScaleTerminationPolicy.DEFAULT],
    name='inst-test', image=image, size=size, location=location)

pprint(group)
