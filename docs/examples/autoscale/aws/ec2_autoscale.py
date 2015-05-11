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

SIZE_ID = 't2.small'

# Initialize the drivers
driver = compute_get_driver(compute_provider.EC2)(ACCESS_ID, SECRET_KEY)
as_driver = as_get_driver(as_provider.AWS_AUTOSCALE)(ACCESS_ID, SECRET_KEY)
mon_driver = monitor_get_driver(monitor_provider.AWS_CLOUDWATCH)(
    ACCESS_ID, SECRET_KEY)

# Get image and size for autoscale member template
image = ec2_driver.list_images(ex_image_ids=['ami-1ecae776'])[0]
sizes = ec2_driver.list_sizes()
size = [s for s in sizes if s.id == SIZE_ID][0]

group = as_driver.create_auto_scale_group(
    group_name='libcloud-group', min_size=2, max_size=5,
    cooldown=300,
    termination_policies=[AutoScaleTerminationPolicy.CLOSEST_TO_NEXT_CHARGE],
    name='inst-name', image=image, size=size)

print('%s %s' % (group, group.extra))
# create scale up policy
policy_scale_up = as_driver.create_auto_scale_policy(
    group=group, name='policy-scale-up',
    adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
    scaling_adjustment=1)

pprint(policy_scale_up)

# and associate it with cpu>80 alarm
alarm_high_cpu = mon_driver.create_auto_scale_alarm(
    name='cpu-high', action_ids=[policy_scale_up.id],
    metric_name=AutoScaleMetric.CPU_UTIL,
    operator=AutoScaleOperator.GT, threshold=80,
    period=120)

pprint(alarm_high_cpu)

# create scale down policy
policy_scale_down = as_driver.create_auto_scale_policy(
    group=group, name='policy-scale-down',
    adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
    scaling_adjustment=-1)

pprint(policy_scale_down)

# associate policy with a cpu<30 alarm
alarm_low_cpu = mon_driver.create_auto_scale_alarm(
    name='cpu-low', action_ids=[policy_scale_down.id],
    metric_name=AutoScaleMetric.CPU_UTIL,
    operator=AutoScaleOperator.LT, threshold=30,
    period=120)

pprint(alarm_low_cpu)

import time
time.sleep(60)

alarms = mon_driver.list_auto_scale_alarms(
    action_ids=[policy_scale_up.id])
pprint(alarms)

nodes = as_driver.list_auto_scale_group_members(group=group)
pprint(nodes)

# delete group completely with all of its resources
# (members, policies, alarms)
as_driver.delete_auto_scale_group(group=group)
