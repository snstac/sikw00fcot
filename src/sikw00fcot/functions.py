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
"""sikw00fcot: MAVLink telemetry -> Cursor-on-Target.

Converts the MAVLink messages that SiKW00F eavesdrops from a drone's SiK
telemetry link into CoT events suitable for ATAK/WinTAK/TAK Server.
"""

import xml.etree.ElementTree as ET

from configparser import SectionProxy
from typing import Optional, Union

import pytak

__author__ = "gba@snstac.com"
__license__ = "Apache License, Version 2.0"


# Format lat/lon to max 4 decimals (~11 m), matching pytak's truncate_float.
# Prefer pytak's implementation when present; fall back to an identical copy
# for pytak releases that predate it.
try:  # pytak >= the release that added truncate_float
    from pytak import truncate_float  # type: ignore
except ImportError:  # older pytak (e.g. 7.3.11)
    from decimal import ROUND_DOWN, Decimal

    def truncate_float(value, precision: int = 4) -> str:
        """Return a numeric value truncated to no more than ``precision`` decimals."""
        if precision < 0:
            raise ValueError("precision must be greater than or equal to 0")
        original = value.decode() if isinstance(value, bytes) else str(value)
        decimal_value = Decimal(original)
        quant = Decimal(1).scaleb(-precision)
        truncated = decimal_value.quantize(quant, rounding=ROUND_DOWN)
        text = format(truncated, f".{precision}f")
        if precision:
            text = text.rstrip("0").rstrip(".")
            if "." not in text and any(m in original.lower() for m in (".", "e")):
                text += ".0"
        if text in ("-0", "-0.0"):
            return "0.0" if "." in text else "0"
        return text


# MAVLink GPS fix_type -> minimum usable fix (2D)
MIN_FIX_TYPE = 2

# MAVLink scales lat/lon as degrees * 1e7 and altitude as millimetres.
LATLON_SCALE = 1.0e7
MM_TO_M = 1.0e-3


def mav_to_cot_xml(  # noqa: C901
    state: dict,
    config: Union[SectionProxy, dict, None] = None,
) -> Optional[ET.Element]:
    """Build a CoT Event Element from an accumulated MAVLink state dict.

    `state` is the merged view of the most recent MAVLink messages keyed by
    message type (HEARTBEAT, GLOBAL_POSITION_INT, GPS_RAW_INT, VFR_HUD, ...),
    exactly as SiKW00F's eavesdrop loop accumulates them.
    """
    config = config or {}

    # Prefer GLOBAL_POSITION_INT (fused lat/lon + MSL/relative alt); fall back
    # to GPS_RAW_INT (raw GPS).  Both use the 1e7 / millimetre scaling.
    gpi = state.get("GLOBAL_POSITION_INT") or {}
    gri = state.get("GPS_RAW_INT") or {}

    if gri:
        fix = gri.get("fix_type", 0)
        if fix < MIN_FIX_TYPE:
            return None  # no usable position lock yet

    lat_i = gpi.get("lat", gri.get("lat"))
    lon_i = gpi.get("lon", gri.get("lon"))
    if lat_i in (None, 0) and lon_i in (None, 0):
        return None

    lat = float(lat_i) / LATLON_SCALE
    lon = float(lon_i) / LATLON_SCALE

    # Altitude (HAE metres). GLOBAL_POSITION_INT.alt is mm MSL; GPS_RAW_INT.alt
    # is mm MSL. We treat MSL as HAE here (close enough for situational tracks).
    alt_mm = gpi.get("alt", gri.get("alt"))
    hae = str(float(alt_mm) * MM_TO_M) if alt_mm not in (None, 0) else "9999999.0"

    # Identity: SiK NetID if SiKW00F injected it, else MAVLink system id.
    sysid = state.get("_sysid")
    netid = state.get("_netid")
    uid_tail = netid if netid is not None else (sysid if sysid is not None else "unknown")
    cot_uid = f"sikw00f-{uid_tail}"

    cot_type = config.get("COT_TYPE", "a-u-A-M-H-Q")  # unknown air, multirotor
    cot_stale = int(config.get("COT_STALE", pytak.DEFAULT_COT_STALE))

    # Course / speed from VFR_HUD when present.
    hud = state.get("VFR_HUD") or {}
    course = str(hud.get("heading", 9999999.0))
    speed = str(hud.get("groundspeed", 9999999.0))

    # Circular error: tighten when we have a 3D fix.
    fix_type = gri.get("fix_type", 0)
    ce = "10.0" if fix_type >= 3 else "45.0"

    point = ET.Element("point")
    point.set("lat", truncate_float(lat))
    point.set("lon", truncate_float(lon))
    point.set("hae", hae)
    point.set("ce", ce)
    point.set("le", "9999999.0")

    # --- detail ---
    detail = ET.Element("detail")

    contact = ET.SubElement(detail, "contact")
    callsign = config.get("COT_CALLSIGN") or f"SiK-{uid_tail}"
    contact.set("callsign", str(callsign))

    track = ET.SubElement(detail, "track")
    track.set("course", course)
    track.set("speed", speed)

    # Roll up the interesting telemetry into a remarks blob.
    hb = state.get("HEARTBEAT") or {}
    batt = state.get("BATTERY_STATUS") or {}
    sats = gri.get("satellites_visible", "?")
    remarks = ET.SubElement(detail, "remarks")
    remarks.text = (
        f"SiKW00F drone track. NetID={netid} SysID={sysid} "
        f"Fix={fix_type} Sats={sats} "
        f"BaseMode={hb.get('base_mode', '?')} "
        f"Batt%={batt.get('battery_remaining', '?')}"
    )

    ET.SubElement(detail, "_sikw00f_").set("source", "sik-mavlink")

    root = ET.Element("event")
    root.set("version", "2.0")
    root.set("type", cot_type)
    root.set("uid", cot_uid)
    root.set("how", "m-g")  # machine, GPS-derived
    root.set("time", pytak.cot_time())
    root.set("start", pytak.cot_time())
    root.set("stale", pytak.cot_time(cot_stale))
    root.append(point)
    root.append(detail)
    return root


def mav_to_cot(state: dict, config=None) -> Optional[bytes]:
    """Return a serialized CoT XML bytestring, or None if no usable fix."""
    event = mav_to_cot_xml(state, config)
    if event is None:
        return None
    return ET.tostring(event)


def detection_to_cot_xml(
    info: dict,
    config: Union[SectionProxy, dict, None] = None,
) -> Optional[ET.Element]:
    """Build a CoT *detection alert* from a scan hit.

    A promiscuous scan yields a NetID (+ channel and the target radio's SiK
    params) but NO drone position — so the alert is placed at the sensor's
    location with a large circular error (CE) to convey "a drone link was
    detected near here," not a precise track.
    """
    config = config or {}
    netid = info.get("netid")
    if netid is None:
        return None

    lat = config.get("SENSOR_LAT", "0")
    lon = config.get("SENSOR_LON", "0")
    ce = str(config.get("SENSOR_CE", "1000.0"))  # uncertainty radius (m)
    cot_type = config.get("COT_TYPE", "a-u-A")   # air, unknown affiliation
    stale = int(config.get("COT_STALE", config.get("DETECT_TTL", 120)))

    params = info.get("params", {}) or {}
    cot_uid = f"sikw00f-scan-{netid}"

    point = ET.Element("point")
    point.set("lat", truncate_float(lat))
    point.set("lon", truncate_float(lon))
    point.set("hae", "9999999.0")
    point.set("ce", ce)
    point.set("le", "9999999.0")

    detail = ET.Element("detail")
    contact = ET.SubElement(detail, "contact")
    callsign = config.get("COT_CALLSIGN") or f"DRONE-DETECT-{netid}"
    contact.set("callsign", str(callsign))

    remarks = ET.SubElement(detail, "remarks")
    remarks.text = (
        f"SiK drone link DETECTED near sensor. NetID={netid} "
        f"chan={info.get('chan', '?')} pkts={info.get('pkts', '?')} "
        f"TXPOWER={params.get('TXPOWER', '?')} AIR_SPEED={params.get('AIR_SPEED', '?')} "
        f"MAVLINK={params.get('MAVLINK', '?')} "
        f"freq={params.get('MIN_FREQ', '?')}-{params.get('MAX_FREQ', '?')}kHz"
    )
    ET.SubElement(detail, "_sikw00f_").set("source", "sik-scan")

    root = ET.Element("event")
    root.set("version", "2.0")
    root.set("type", cot_type)
    root.set("uid", cot_uid)
    root.set("how", "m-r")  # machine, radio-detected (no GPS)
    root.set("time", pytak.cot_time())
    root.set("start", pytak.cot_time())
    root.set("stale", pytak.cot_time(stale))
    root.append(point)
    root.append(detail)
    return root


def detection_to_cot(info: dict, config=None) -> Optional[bytes]:
    """Serialize a detection alert CoT, or None."""
    event = detection_to_cot_xml(info, config)
    return ET.tostring(event) if event is not None else None


def status_to_cot_xml(
    state: str,
    target=None,
    config: Union[SectionProxy, dict, None] = None,
) -> ET.Element:
    """Build the sentinel's self/status CoT showing its current mode.

    A single stable-UID marker at the sensor location whose callsign/remarks
    reflect the active state (SCAN / INSPECT-<netid>), so operators can see what
    the sensor is doing on the TAK map.
    """
    config = config or {}
    lat = config.get("SENSOR_LAT", "0")
    lon = config.get("SENSOR_LON", "0")
    name = config.get("SENSOR_NAME", "sikw00f")
    cot_type = config.get("STATUS_COT_TYPE", "a-f-G-E-S")  # friendly ground sensor
    interval = int(config.get("STATUS_INTERVAL", 30))
    stale = int(config.get("STATUS_STALE", interval * 3))

    label = f"{state}-{target}" if target is not None else state

    point = ET.Element("point")
    point.set("lat", truncate_float(lat))
    point.set("lon", truncate_float(lon))
    point.set("hae", "9999999.0")
    point.set("ce", str(config.get("SENSOR_CE", "1000.0")))
    point.set("le", "9999999.0")

    detail = ET.Element("detail")
    ET.SubElement(detail, "contact").set("callsign", f"SIKW00F:{label}")
    ET.SubElement(detail, "remarks").text = (
        f"SiKW00F sentinel '{name}' mode={state} target={target if target is not None else 'none'}"
    )
    st = ET.SubElement(detail, "_sikw00f_")
    st.set("source", "sik-sentinel")
    st.set("mode", str(state))
    st.set("target", str(target) if target is not None else "")

    root = ET.Element("event")
    root.set("version", "2.0")
    root.set("type", cot_type)
    root.set("uid", f"sikw00f-sentinel-{name}")
    root.set("how", "m-g")
    root.set("time", pytak.cot_time())
    root.set("start", pytak.cot_time())
    root.set("stale", pytak.cot_time(stale))
    root.append(point)
    root.append(detail)
    return root


def status_to_cot(state: str, target=None, config=None) -> bytes:
    """Serialize the sentinel status CoT."""
    return ET.tostring(status_to_cot_xml(state, target, config))
