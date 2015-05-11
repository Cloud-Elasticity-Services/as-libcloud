from pprint import pprint

from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider
from libcloud.autoscale.types import AutoScaleTerminationPolicy, \
    AutoScaleAdjustmentType

from libcloud.compute.providers import get_driver as compute_get_driver
from libcloud.compute.types import Provider as compute_provider

from libcloud.monitor.providers import get_driver as monitor_get_driver
from libcloud.monitor.types import Provider as monitor_provider
from libcloud.monitor.types import AutoScaleMetric, AutoScaleOperator

ACCESS_ID = 'your access id'
SECRET_KEY = 'your secret key'

IMAGE_ID = 'ami-1ecae776'
SIZE_ID = 't2.small'

# Initialize the drivers
driver = compute_get_driver(compute_provider.EC2)(ACCESS_ID, SECRET_KEY)
as_driver = as_get_driver(as_provider.AWS_AUTOSCALE)(ACCESS_ID, SECRET_KEY)
mon_driver = monitor_get_driver(monitor_provider.AWS_CLOUDWATCH)(
    ACCESS_ID, SECRET_KEY)

# Here we select image
images = driver.list_images()
image = [i for i in images if i.id == IMAGE_ID][0]

sizes = driver.list_sizes()
size = [s for s in sizes if s.id == SIZE_ID][0]

location = driver.list_locations()[0]
group = as_driver.create_auto_scale_group(
    group_name='libcloud-group', min_size=2, max_size=5, cooldown=300,
    termination_policies=[AutoScaleTerminationPolicy.CLOSEST_TO_NEXT_CHARGE],
    name='test-node', image=image, size=size, location=location)

pprint(group)

policy = as_driver.create_auto_scale_policy(
    group=group, name='libcloud-policy',
    adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
    scaling_adjustment=1)

pprint(policy)

alarm = mon_driver.create_auto_scale_alarm(
    name='libcloud-alarm',
    action_ids=[policy.id], metric_name=AutoScaleMetric.CPU_UTIL,
    operator=AutoScaleOperator.GT, threshold=80,
    period=120)

pprint(alarm)

import time
time.sleep(60)

nodes = as_driver.list_auto_scale_group_members(group=group)
pprint(nodes)

as_driver.delete_auto_scale_group(group=group)
