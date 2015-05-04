from pprint import pprint

from libcloud.compute.types import Provider as compute_provider
from libcloud.compute.providers import get_driver \
    as compute_get_driver

from libcloud.autoscale.types import Provider, AutoScaleAdjustmentType,\
    AutoScaleMetric, AutoScaleOperator, AutoScaleTerminationPolicy
from libcloud.autoscale.providers import get_driver

USER_NAME = 'your user name'
SECRET_KEY = 'your secret key'

driver = compute_get_driver(compute_provider.SOFTLAYER)(
    USER_NAME, SECRET_KEY)

as_driver = get_driver(Provider.SOFTLAYER)(USER_NAME, SECRET_KEY)

image = driver.list_images()[0]
size = driver.list_sizes()[0]

# Dallas 5 datacenter
location = driver.list_locations()[4]

# create an auto scale group
# (note: create is a long syncronious operation, be patient)
group = as_driver.create_auto_scale_group(
    group_name='libcloud-group', min_size=2, max_size=5,
    cooldown=300,
    termination_policies=[AutoScaleTerminationPolicy.CLOSEST_TO_NEXT_CHARGE],
    name='inst-test', image=image, size=size, location=location,
    ex_region='na-usa-central-1')

pprint(group)

# create scale up policy that when triggered, increments group membership
# by one
policy_scale_up = as_driver.create_auto_scale_policy(
    group=group, name='policy-scale-up',
    adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
    scaling_adjustment=1)

pprint(policy_scale_up)

# add an alarm to policy which triggers the policy when cpu utilization
# of group members is greater than 80%
alarm_high_cpu = as_driver.create_auto_scale_alarm(
    name='cpu-high', policy=policy_scale_up,
    metric_name=AutoScaleMetric.CPU_UTIL,
    operator=AutoScaleOperator.GT, threshold=80,
    period=120)

pprint(alarm_high_cpu)

# create scale down policy that when triggered, decreases group membership
# by one
policy_scale_down = as_driver.create_auto_scale_policy(
    group=group, name='policy-scale-down',
    adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
    scaling_adjustment=-1)

pprint(policy_scale_down)

# add an alarm to policy which triggers the policy when cpu utilization
# of group members is less than 30%
alarm_low_cpu = as_driver.create_auto_scale_alarm(
    name='cpu-low', policy=policy_scale_down,
    metric_name=AutoScaleMetric.CPU_UTIL,
    operator=AutoScaleOperator.LT, threshold=30,
    period=120)

pprint(alarm_low_cpu)

import time
time.sleep(60)

# list group members
nodes = as_driver.list_auto_scale_group_members(group=group)
pprint(nodes)

# delete group completely with all of its resources
# (members, policies, alarms)
as_driver.delete_auto_scale_group(group=group)
