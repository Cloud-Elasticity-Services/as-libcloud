import time
from pprint import pprint

from libcloud.compute.types import Provider as compute_provider
from libcloud.compute.providers import get_driver \
    as compute_get_driver

from libcloud.autoscale.types import Provider, AutoScaleAdjustmentType,\
    AutoScaleMetric, AutoScaleOperator, AutoScaleTerminationPolicy
from libcloud.autoscale.providers import get_driver

ACCESS_ID = 'your access id'
SECRET_KEY = 'your secret key'

SIZE_ID = 't2.small'

cls = compute_get_driver(compute_provider.EC2)
driver = cls(ACCESS_ID, SECRET_KEY)

as_cls = get_driver(Provider.AWS_AUTOSCALE)
as_driver = as_cls(ACCESS_ID, SECRET_KEY)

cw_cls = get_driver(Provider.AWS_CLOUDWATCH)
cw_driver = cw_cls(ACCESS_ID, SECRET_KEY)

image = driver.list_images(ex_image_ids=['ami-1ecae776'])[0]

sizes = driver.list_sizes()
size = [s for s in sizes if s.id == SIZE_ID][0]

group = as_driver.create_auto_scale_group(
    group_name='libcloud-group-1', min_size=2, max_size=5, cooldown=300,
    termination_policies=[AutoScaleTerminationPolicy.CLOSEST_TO_NEXT_CHARGE],
    name='test-node', image=image, size=size, ex_availability_zones=['a', 'b'])

print('%s %s' % (group, group.extra))

policy = as_driver.create_auto_scale_policy(
    group=group, name='libcloud-policy',
    adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
    scaling_adjustment=1)

pprint(policy)

alarm = cw_driver.create_auto_scale_alarm(name='libcloud-alarm',
                                          policy=policy,
                                          metric_name=AutoScaleMetric.CPU_UTIL,
                                          operator=AutoScaleOperator.GT,
                                          threshold=80,
                                          period=120)
pprint(alarm)

time.sleep(60)

nodes = as_driver.list_auto_scale_group_members(group=group)
pprint(nodes)

as_driver.delete_auto_scale_group(group=group)
