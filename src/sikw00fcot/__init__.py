#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""SiKW00F drone MAVLink telemetry to Cursor-on-Target (CoT) Gateway."""

import os as _os

with open(
    _os.path.join(_os.path.dirname(__file__), "VERSION"), encoding="utf-8"
) as _vf:
    __version__ = _vf.read().strip()

from .constants import (  # NOQA
    DEFAULT_COT_TYPE,
    DEFAULT_COT_STALE,
    DEFAULT_COT_INTERVAL,
    DEFAULT_DEVICE,
    DEFAULT_BAUD,
    DEFAULT_MAV_URL,
    DEFAULT_DETECT_MIN_HITS,
    DEFAULT_INSPECT_TIMEOUT,
    DEFAULT_INSPECT_COOLDOWN,
    DEFAULT_STATUS_COT_TYPE,
    DEFAULT_STATUS_INTERVAL,
    DEFAULT_SENSOR_NAME,
)

from .functions import (  # NOQA
    detection_to_cot,
    detection_to_cot_xml,
    mav_to_cot,
    mav_to_cot_xml,
    status_to_cot,
    status_to_cot_xml,
)

from .commands import cli, main  # NOQA
from .scan_commands import cli as scan_cli  # NOQA
from .sentinel_commands import cli as sentinel_cli  # NOQA
