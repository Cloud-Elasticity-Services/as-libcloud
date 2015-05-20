from pprint import pprint

from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider
from libcloud.autoscale.types import AutoScaleTerminationPolicy, \
    AutoScaleAdjustmentType

from libcloud.compute.providers import get_driver \
    as compute_get_driver
from libcloud.compute.types import Provider as compute_provider

from libcloud.monitor.providers import get_driver as monitor_get_driver
from libcloud.monitor.types import Provider as monitor_provider
from libcloud.monitor.types import AutoScaleMetric, AutoScaleOperator

USER_NAME = 'your user name'
SECRET_KEY = 'your secret key'

# Initialize the drivers
driver = compute_get_driver(compute_provider.SOFTLAYER)(
    USER_NAME, SECRET_KEY)

as_driver = as_get_driver(Provider.SOFTLAYER)(USER_NAME, SECRET_KEY,
                                              region='na-usa-central-1')
mon_driver = monitor_get_driver(monitor_provider.SOFTLAYER)(
    USER_NAME, SECRET_KEY)

image = driver.list_images()[0]
size = driver.list_sizes()[0]

# Dallas 5 datacenter
location = driver.list_locations()[4]

group = as_driver.create_auto_scale_group(
    group_name='libcloud-group', min_size=1, max_size=5, cooldown=300,
    termination_policies=AutoScaleTerminationPolicy.CLOSEST_TO_NEXT_CHARGE,
    name='inst-test', size=size, location=location)
pprint(group)

policy = as_driver.create_auto_scale_policy(
    group=group, name='libcloud-policy',
    adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
    scaling_adjustment=1)

pprint(policy)

alarm = mon_driver.create_auto_scale_alarm(
    name='libcloud-alarm',
    policy=policy,
    metric_name=AutoScaleMetric.CPU_UTIL,
    operator=AutoScaleOperator.GT,
    threshold=80, period=120)

pprint(alarm)

import time
time.sleep(60)

nodes = as_driver.list_auto_scale_group_members(group=group)
pprint(nodes)

as_driver.delete_auto_scale_group(group=group)
