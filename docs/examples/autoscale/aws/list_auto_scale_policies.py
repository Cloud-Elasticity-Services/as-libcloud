from pprint import pprint

from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider

ACCESS_ID = 'your access id'
SECRET_KEY = 'your secret key'

as_driver = as_get_driver(as_provider.AWS_AUTOSCALE)(ACCESS_ID, SECRET_KEY)

group = as_driver.list_auto_scale_groups()[0]
policies = as_driver.list_auto_scale_policies(group)

pprint(policies)
