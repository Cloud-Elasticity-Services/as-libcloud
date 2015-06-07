Auto Scale
==========

.. note::

    Auto Scale API is available in Libcloud 0.17.1 and higher.

Auto Scale API allows you to manage elasticity (autoscale) groups that
automatically add or remove compute resources depending upon actual usage and
demand. Auto Scale services are supported by various cloud providers such as
Amazon (through AutoScaling and CloudWatch services), OpenStack (through
Heat/Ceilometer services), SoftLayer (through Scale_Group/Scale_Policy_Trigger
services) and more.

Terminology
-----------

* :class:`~libcloud.autoscale.base.AutoScaleGroup` - Represents an autoscale
  group.
* :class:`~libcloud.autoscale.base.AutoScalePolicy` - Represents an autoscale
  policy that defines how the group will scale. Each policy belongs to an auto
  scale group.
* :class:`~libcloud.monitor.base.AutoScaleAlarm` - Represents an autoscale
  alarm. An alarm is essentially a monitor of a statistic (such as CPU utilization) that
  get triggered when a threshold condition is breached which in turn triggers the policy
  of the auto scale group to scale the group as needed. Each alarm belongs to an autoscale
  policy.

Supported Providers
-------------------

For a list of supported providers see :doc:`supported providers page
</autoscale/supported_providers>`.

Examples
--------

We have :doc:`end to end example of a common autoscale pattern </autoscale/examples>`.

API Reference
-------------

For a full reference of all the classes and methods exposed by the Auto Scale
API, see :doc:`this page </autoscale/api>`.
