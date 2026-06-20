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

"""SIKW00FCOT Constants.

Documented defaults shared by the three daemons (sikw00fcot, sikw00fscan,
sikw00fsentinel). These mirror the per-worker fallbacks so config files and
docs have a single source of truth.
"""

import socket as _socket

# --- CoT shaping ---
# Detected drone marker: unknown air, multirotor UAS.
DEFAULT_COT_TYPE: str = "a-u-A-M-H-Q"
# Marker stale ("timeout") period, in seconds.
DEFAULT_COT_STALE: str = "120"
# Seconds between CoT emissions for a tracked/detected contact.
DEFAULT_COT_INTERVAL: str = "5"

# --- SiK radio (serial) ---
DEFAULT_DEVICE: str = "/dev/ttyUSB0"
DEFAULT_BAUD: int = 57600

# --- MAVLink ingest (sikw00fcot) ---
DEFAULT_MAV_URL: str = "udpin:127.0.0.1:14550"

# --- Detection gate (sikw00fscan / sikw00fsentinel) ---
# "NetID: X" hits required before a detection is confirmed (filters fragments).
DEFAULT_DETECT_MIN_HITS: int = 4

# --- INSPECT state machine (sikw00fsentinel) ---
# Seconds with NO decoded MAVLink before reverting INSPECT -> SCAN.
DEFAULT_INSPECT_TIMEOUT: str = "30"
# After a failed inspect, don't re-inspect that NetID for this long (anti-thrash).
DEFAULT_INSPECT_COOLDOWN: str = "30"

# --- Status / mode marker ---
# a-f-G-E-S = friendly ground sensor.
DEFAULT_STATUS_COT_TYPE: str = "a-f-G-E-S"
# Seconds between sensor status/mode markers.
DEFAULT_STATUS_INTERVAL: str = "30"

DEFAULT_SENSOR_NAME: str = f"sikw00f_{_socket.gethostname()}"
