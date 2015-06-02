import time

from libcloud.autoscale.types import AutoScaleTerminationPolicy
from libcloud.autoscale.types import Provider as as_provider
from libcloud.autoscale.providers import get_driver as as_get_driver

from libcloud.compute.base import NodeLocation

from libcloud.loadbalancer.base import Algorithm

from libcloud.loadbalancer.types import Provider as lb_provider
from libcloud.loadbalancer.providers import get_driver as lb_get_driver

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

USER_NAME = 'your user name'
SECRET_KEY = 'your secret key'

# the datacenter of the loadbalancer
DATACENTER = 'par01'
# the region of the auto-scale group
REGION = 'eu-fra-north-1'

lb_driver = lb_get_driver(lb_provider.SOFTLAYER)(USER_NAME, SECRET_KEY)
as_driver = as_get_driver(as_provider.SOFTLAYER)(USER_NAME, SECRET_KEY,
                                                 region=REGION)
driver = get_driver(Provider.SOFTLAYER)(USER_NAME, SECRET_KEY)

image = driver.list_images()[0]

balancers = lb_driver.list_balancers()
balancer = [b for b in balancers if
            b.extra.get('datacenter') == DATACENTER][0]

print balancer

if balancer.port < 0:
    # no front-end port defined, configure it with such one
    balancer = lb_driver.ex_configure_load_balancer(
        balancer, port=80, protocol='http',
        algorithm=Algorithm.SHORTEST_RESPONSE)

# create scale group with balancer and backend port of 8080
# NOTE: scale group members must be in the same datacenter of balancer
group = as_driver.create_auto_scale_group(
    group_name='libcloud-group', min_size=1, max_size=5, cooldown=300,
    termination_policies=AutoScaleTerminationPolicy.CLOSEST_TO_NEXT_CHARGE,
    image=image, location=NodeLocation(DATACENTER,
                                       None, None, None),
    balancer=balancer, ex_service_port=8080)

print ('Created scale group: %s' % group)
time.sleep(60)

as_driver.ex_detach_balancer_from_auto_scale_group(group, balancer)
print ('Detached balancer: %s from scale group: %s' % (balancer, group))
time.sleep(30)

as_driver.ex_attach_balancer_to_auto_scale_group(
    group=group, balancer=balancer,
    ex_service_port=100)

print (
    'Attached balancer: %s to scale group: %s with backend port %s' %
    (balancer, group, 100))
time.sleep(30)

as_driver.delete_auto_scale_group(group=group)
print ('Deleted scale group: %s' % group)
