from pprint import pprint

from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider

from libcloud.monitor.providers import get_driver as monitor_get_driver
from libcloud.monitor.types import Provider as monitor_provider
from libcloud.monitor.types import AutoScaleMetric, AutoScaleOperator

ACCESS_ID = 'your access id'
SECRET_KEY = 'your secret key'

# Initialize the drivers
as_driver = as_get_driver(as_provider.AWS_AUTOSCALE)(ACCESS_ID, SECRET_KEY)
mon_driver = monitor_get_driver(monitor_provider.AWS_CLOUDWATCH)(
    ACCESS_ID, SECRET_KEY)

group = as_driver.list_auto_scale_groups()[0]

policy = as_driver.list_auto_scale_policies(group)[0]

alarm = mon_driver.create_auto_scale_alarm(
    name='my-alarm', policy=policy,
    metric_name=AutoScaleMetric.CPU_UTIL,
    operator=AutoScaleOperator.GT, threshold=80,
    period=120)

pprint(alarm)
