import time

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

"""
End to end example for creating auto-scale group that scales out
due to cpu utilization increase of its members (nodes).

Finally, this group and all of its resources get deleted.

OpenStack or devstack must be installed with heat and ceilometer
services for this example to properly work.
"""

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
mon_driver = monitor_get_driver(monitor_provider.OPENSTACK)(
    USER_NAME, PASSWORD, ex_tenant_name=TENANT_NAME,
    ex_force_auth_url=AUTH_URL,
    ex_force_auth_version='2.0_password')

# script to load cpu
ex_userdata = \
    "#!/bin/sh\ntouch userdata.txt\nnohup dd if=/dev/zero of=/dev/null &"

image = driver.list_images()[0]
location = driver.list_locations()[0]
size = driver.list_sizes()[0]

# create an auto scale group
group = as_driver.create_auto_scale_group(
    group_name='libcloud-group-1', min_size=1, max_size=4,
    cooldown=60,
    termination_policies=[AutoScaleTerminationPolicy.DEFAULT],
    name='inst-test', image=image, size=size, location=location,
    ex_userdata=ex_userdata, ex_userdata_format='RAW')
pprint(group)

policy_scale_up = as_driver.create_auto_scale_policy(
    group=group, name='policy-scale-up',
    adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
    scaling_adjustment=1)
pprint(policy_scale_up)

# associate it with cpu>60 alarm
alarm_high_cpu = mon_driver.create_auto_scale_alarm(
    name='cpu-high', policy=policy_scale_up,
    metric_name=AutoScaleMetric.CPU_UTIL,
    operator=AutoScaleOperator.GT, threshold=60,
    period=60)
pprint(alarm_high_cpu)

# create scale down policy
policy_scale_down = as_driver.create_auto_scale_policy(
    group=group, name='policy-scale-down',
    adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
    scaling_adjustment=-1)
pprint(policy_scale_down)

# associate policy with a cpu<30 alarm
alarm_low_cpu = mon_driver.create_auto_scale_alarm(
    name='cpu-low', policy=policy_scale_down,
    metric_name=AutoScaleMetric.CPU_UTIL,
    operator=AutoScaleOperator.LT, threshold=30,
    period=60)
pprint(alarm_low_cpu)

groups = as_driver.list_auto_scale_groups()
pprint(groups)
print "Allow time for the group to scale out ..."
time.sleep(300)

print "Terminating the group and all of its resources ..."
as_driver.delete_auto_scale_group(groups[0])
