Auto Scaling enabled libCloud 
=============================

An extension to [Libcloud][libcloud] enabling native cloud providers Auto 
Scaling capabilities.

### Features

**Supported providers:**

- Amazon EC2
- Softlayer

**Auto Scale Groups:**

- List groups
- Create group
- Delete group (and all of its resources)
- List group members

**Auto Scale Policies:**

- List policies for a given group
- Create policy for a given group
- Delete policy

**Auto Scale Alarms:**

- List alarms for a given policy
- Create alarm for a given policy
- Delete alarm

#### Installation

    $ git clone https://github.com/Cloud-Elasticity-Services/as-libcloud.git
    $ cd as-libcloud
    $ python setup.py install


#### Usage Examples

    $ python

    >>> from libcloud.compute.types import Provider
    >>> from libcloud.compute.providers import get_driver
    >>> cls = get_driver(Provider.SOFTLAYER)

    # Use account username and api key
    >>> username = "Your SOFTLAYER user name"
    >>> api_key = "Your SOFTLAYER api key"
    >>> driver = cls(username, api_key)

    # Create an auto scale group
    >>> group = driver.create_auto_scale_group(name="test",min_size=1,
                   max_size=5, cooldown=300,
                   image=driver.list_images()[0])

    # List auto scale groups
    >>> driver.list_auto_scale_groups()

    # Create policy that when triggered, increments group membership 
    # by one
    >>> policy=driver.create_auto_scale_policy(group,
           name='test-policy',
           adjustment_type='CHANGE_IN_CAPACITY',
           scaling_adjustment=1)

    # Add an alarm to policy.
    # Alarm triggers the policy when cpu utilization 
    # of group members is beyond 80%
    >>> alarm = driver.create_auto_scale_alarm(name='my_alarm',
           policy=policy, metric_name='CPU_UTIL', operator='GT',
           threshold=80, period=120)

    # List alarms for this policy
    >>> driver.list_auto_scale_alarms(policy)

    # List policies for this group
    >>> driver.list_auto_scale_policies(group)

    # Delete alarm
    >>> driver.delete_auto_scale_alarm(alarm)
    

[libcloud]: https://libcloud.readthedocs.org/
