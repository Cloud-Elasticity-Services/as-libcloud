import time

from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider
from libcloud.autoscale.types import AutoScaleTerminationPolicy

from libcloud.compute.base import NodeImage
from libcloud.compute.providers import get_driver \
    as compute_get_driver
from libcloud.compute.types import Provider as compute_provider

from libcloud.loadbalancer.base import Algorithm
from libcloud.loadbalancer.providers import get_driver as lb_get_driver
from libcloud.loadbalancer.types import Provider as lb_provider

ACCESS_ID = 'your access id'
SECRET_KEY = 'your secret key'

IMAGE_ID = 'ami-d114f295'
SIZE_ID = 't2.small'

REGION = 'us-west-1'

# Initialize the drivers
ec2_driver = compute_get_driver(
    compute_provider.EC2)(ACCESS_ID, SECRET_KEY, region=REGION)
as_driver = as_get_driver(
    as_provider.AWS_AUTOSCALE)(ACCESS_ID, SECRET_KEY, region=REGION)
lb_driver = lb_get_driver(lb_provider.ELB)(ACCESS_ID, SECRET_KEY, REGION)

# image for the auto scale members
image = NodeImage(IMAGE_ID, None, None)

sizes = ec2_driver.list_sizes()
size = [s for s in sizes if s.id == SIZE_ID][0]

# create a balancer
balancer = lb_driver.create_balancer(
    name='MyLB',
    algorithm=Algorithm.ROUND_ROBIN,
    port=80,
    protocol='http',
    members=[])

print(balancer)
time.sleep(60)

# create scale group with balancer (group and balancer are
# in same availability zone)
group = as_driver.create_auto_scale_group(
    group_name='libcloud-balancer-group', min_size=2, max_size=5,
    cooldown=300,
    termination_policies=[AutoScaleTerminationPolicy.CLOSEST_TO_NEXT_CHARGE],
    balancer=balancer, name='test-node', image=image, size=size)

print(group)

time.sleep(120)

nodes = as_driver.list_auto_scale_group_members(group=group)
print(nodes)

as_driver.delete_auto_scale_group(group=group)
balancer.destroy()
