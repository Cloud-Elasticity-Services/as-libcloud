from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider

USER_NAME = 'your user name'
SECRET_KEY = 'your secret key'

as_driver = as_get_driver(as_provider.SOFTLAYER)(USER_NAME, SECRET_KEY)

group = as_driver.list_auto_scale_groups()[0]

# delete group completely with all of its resources
# (members, policies, alarms)
as_driver.delete_auto_scale_group(group)
