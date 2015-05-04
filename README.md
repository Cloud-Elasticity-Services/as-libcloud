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

    >>> from libcloud.autoscale.types import AutoScaleTerminationPolicy, AutoScaleMetric, AutoScaleAdjustmentType, AutoScaleOperator
    >>> from libcloud.autoscale.types import Provider as autoscale_Provider
    >>> from libcloud.autoscale.providers import get_driver as autoscale_get_driver

    >>> from libcloud.compute.types import Provider
    >>> from libcloud.compute.providers import get_driver

    # Use account username and api key
    >>> username = "Your SOFTLAYER user name"
    >>> api_key = "Your SOFTLAYER api key"

    >>> driver = get_driver(Provider.SOFTLAYER)(username, api_key)
    >>> as_driver = autoscale_get_driver(autoscale_Provider.SOFTLAYER)(username, api_key)

    # Create an auto scale group 
    # (note: create is a long syncronious operation, be patient)
    >>> group = as_driver.create_auto_scale_group(group_name='test', min_size=1,
            max_size=5, cooldown=300, image=driver.list_images()[0],
            termination_policies=[AutoScaleTerminationPolicy.OLDEST_INSTANCE],
            location=driver.list_locations()[0], name='inst-test', ex_region='na-usa-east-1')

    # List auto scale groups
    >>> as_driver.list_auto_scale_groups()

    # Create policy that when triggered, increments group membership 
    # by one
    >>> policy=as_driver.create_auto_scale_policy(group, name='policy-scale-up',
            adjustment_type=AutoScaleAdjustmentType.CHANGE_IN_CAPACITY,
            scaling_adjustment=1)

    # Add an alarm to policy.
    # Alarm triggers the policy when cpu utilization 
    # of group members is beyond 80%
    >>> alarm = as_driver.create_auto_scale_alarm(name='cpu-high',
            policy=policy, metric_name=AutoScaleMetric.CPU_UTIL,
            operator=AutoScaleOperator.GT, threshold=80, period=120)

    # List alarms for this policy
    >>> as_driver.list_auto_scale_alarms(policy)

    # List policies for this group
    >>> as_driver.list_auto_scale_policies(group)

    # Delete alarm
    >>> as_driver.delete_auto_scale_alarm(alarm)
    
Additional autoscale/loadbalancer examples available at [autoscale][autoscale] and [loadbalancer][loadbalancer] directories.

### Native APIs

Following is a list of native API services that the extension uses
for the below operations supported by the cloud providers.

List groups

- Amazon: DescribeAutoScalingGroups
- Softlayer: SoftLayer_Account::getScaleGroups

Create group

- Amazon: CreateAutoScalingGroup
- Softlayer: SoftLayer_Scale_Group::createObject

Delete group

- Amazon: DeleteAutoScalingGroup
- Softlayer: SoftLayer_Scale_Group::forceDeleteObject

List group members

- Amazon: DescribeInstances (with a filter of 'tag:aws:autoscaling:groupName')
- Softlayer: SoftLayer_Scale_Group::getVirtualGuestMembers

List policies

- Amazon: DescribePolicies
- Softlayer: SoftLayer_Scale_Group::getPolicies

Create policy

- Amazon: PutScalingPolicy
- Softlayer: SoftLayer_Scale_Policy::createObject

Delete policy

- Amazon: DeletePolicy
- Softlayer: SoftLayer_Scale_Policy::deleteObject

List alarms

- Amazon: DescribeAlarms
- Softlayer: SoftLayer_Scale_Policy::getResourceUseTriggers

Create alarm

- Amazon: PutMetricAlarm
- Softlayer: SoftLayer_Scale_Policy_Trigger_ResourceUse::createObject

Delete alarm

- Amazon: DeleteAlarms
- Softlayer: SoftLayer_Scale_Policy_Trigger_ResourceUse::deleteObject

[autoscale]: https://github.com/Cloud-Elasticity-Services/as-libcloud/tree/trunk/docs/examples/autoscale
[libcloud]: https://libcloud.readthedocs.org/
[loadbalancer]: https://github.com/Cloud-Elasticity-Services/as-libcloud/tree/trunk/docs/examples/loadbalancer/softlayer
