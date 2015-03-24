from pprint import pprint


from libcloud.loadbalancer.types import Provider as lb_provider
from libcloud.loadbalancer.providers import get_driver as lb_get_driver
lb_cls = lb_get_driver(lb_provider.SOFTLAYER)

from libcloud.compute.types import Provider as provider
from libcloud.compute.providers import get_driver

cls = get_driver(provider.SOFTLAYER)

USER_NAME = 'your user name'
SECRET_KEY = 'your secret key'

DATACENTER = 'fra02'
FRA02_REGION = 'eu-deu-west-1'

lb_driver = lb_cls(USER_NAME, SECRET_KEY)
driver = cls(USER_NAME, SECRET_KEY)

# locate loadbalancer for Frankfurt datacenter
balancers = lb_driver.list_balancers()
balancer = [b for b in balancers if b.extra.get('datacenter', '') == \
            DATACENTER][0]
pprint(balancer)

# get Frankfurt location object
locations = driver.list_locations()
location = [l for l in locations if l.id == DATACENTER][0]

group = driver.create_auto_scale_group(name='libcloud-group', min_size=1,
                             max_size=5, cooldown=300, location=location,
                             balancer=balancer, ex_instance_port=8080,
                             ex_region=FRA02_REGION)
pprint(group)

# List balancer auto scale members
#TODO: call base common method for listing members
balancers = lb_driver.list_balancers()
balancer = [b for b in balancers if b.extra.get('datacenter', '') == \
            DATACENTER][0]
pprint(balancer._scale_members)

import time
time.sleep(60)

driver.delete_auto_scale_group(group=group)
