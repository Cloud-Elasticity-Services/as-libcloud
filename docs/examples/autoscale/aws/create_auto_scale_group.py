from pprint import pprint

from libcloud.autoscale.providers import get_driver as as_get_driver
from libcloud.autoscale.types import Provider as as_provider
from libcloud.autoscale.types import AutoScaleTerminationPolicy

from libcloud.compute.providers import get_driver as compute_get_driver
from libcloud.compute.types import Provider as compute_provider

ACCESS_ID = 'your access id'
SECRET_KEY = 'your secret key'

SIZE_ID = 't2.small'

# Initialize the drivers
driver = compute_get_driver(compute_provider.EC2)(ACCESS_ID, SECRET_KEY)
as_driver = as_get_driver(as_provider.AWS_AUTOSCALE)(ACCESS_ID, SECRET_KEY)

# Get image and size for autoscale member template
image = driver.list_images(ex_image_ids=['ami-1ecae776'])[0]

sizes = driver.list_sizes()
size = [s for s in sizes if s.id == SIZE_ID][0]

location = driver.list_locations()[0]
group = as_driver.create_auto_scale_group(
    group_name='libcloud-group', min_size=2, max_size=5,
    cooldown=300,
    termination_policies=[AutoScaleTerminationPolicy.CLOSEST_TO_NEXT_CHARGE],
    name='inst-name', image=image, size=size, location=location)

pprint(group)
