# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__all__ = [
    "Provider",
    "AutoScaleOperator",
    "AutoScaleMetric"
]


class Provider(object):
    """
    Defines for each of the supported providers

    :cvar: AWS_CLOUDWATCH: Amazon CloudWatch
    :cvar SOFTLAYER: Softlayer
    """
    AWS_CLOUDWATCH = 'aws_cloudwatch'
    SOFTLAYER = 'softlayer'


class AutoScaleOperator(object):
    """
    The arithmetic operation to use when comparing the statistic
    and threshold.

    :cvar LT: Less than.
    :cvar LE: Less equals.
    :cvar GT: Greater than.
    :cvar GE: Great equals.

    """

    LT = 'LT'
    LE = 'LE'
    GT = 'GT'
    GE = 'GE'


class AutoScaleMetric(object):
    """
    :cvar CPU_UTIL: The percent CPU a guest is using.
    """
    CPU_UTIL = 'CPU_UTIL'
