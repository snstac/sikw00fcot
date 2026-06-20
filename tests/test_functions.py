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

"""SIKW00FCOT Function Tests."""

import xml.etree.ElementTree as ET

import sikw00fcot
from sikw00fcot import functions


def test_version():
    """Package exposes a version string read from the VERSION file."""
    assert isinstance(sikw00fcot.__version__, str)
    assert sikw00fcot.__version__.split(".")[0].isdigit()


def test_detection_to_cot():
    """A scan hit produces a valid CoT detection alert at the sensor."""
    config = {"SENSOR_LAT": "37.7601", "SENSOR_LON": "-122.4977"}
    cot = functions.detection_to_cot({"netid": 42, "chan": 3}, config)
    assert cot is not None
    event = ET.fromstring(cot)
    assert event.tag == "event"
    assert event.attrib["uid"] == "sikw00f-scan-42"
    point = event.find("point")
    # 4-decimal truncation per pytak.truncate_float.
    assert point.attrib["lat"] == "37.7601"
    assert point.attrib["lon"] == "-122.4977"


def test_detection_to_cot_no_netid():
    """No NetID -> no detection CoT."""
    assert functions.detection_to_cot({}, {}) is None


def test_status_to_cot_modes():
    """Status CoT reflects the active sentinel mode in callsign + detail."""
    config = {"SENSOR_NAME": "nebra", "SENSOR_LAT": "1.0", "SENSOR_LON": "2.0"}

    scan = ET.fromstring(functions.status_to_cot("SCAN", config=config))
    assert scan.attrib["uid"] == "sikw00f-sentinel-nebra"
    assert scan.find("detail/contact").attrib["callsign"] == "SIKW00F:SCAN"

    inspect = ET.fromstring(functions.status_to_cot("INSPECT", target=42, config=config))
    assert inspect.find("detail/contact").attrib["callsign"] == "SIKW00F:INSPECT-42"
    assert inspect.find("detail/_sikw00f_").attrib["mode"] == "INSPECT"
