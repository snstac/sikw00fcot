#!/usr/bin/env python3
"""Fake drone telemetry transmitter for end-to-end SiKW00F testing.

Feeds a slowly-circling MAVLink track into a SiK radio's serial port (the radio
then transmits it over the air). Pair with `sikw00f --eavesdrop` on the far end.

Usage: python3 fake_drone.py [/dev/ttyUSB0] [baud]
"""
import math
import sys
import time

from pymavlink import mavutil

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 57600

# Center of the orbit + ~200 m radius.
LAT0, LON0, R = 32.7157, -117.1611, 0.0018
ALT_MM = 120000  # 120 m

m = mavutil.mavlink_connection(PORT, baud=BAUD, source_system=7,
                               dialect="ardupilotmega")
print(f"TX MAVLink drone (sysid 7) on {PORT}@{BAUD} — Ctrl+C to stop")

i = 0
while True:
    ang = math.radians(i % 360)
    lat = LAT0 + R * math.cos(ang)
    lon = LON0 + R * math.sin(ang)
    cog = int((math.degrees(ang) + 90) % 360 * 100)  # heading along the circle
    m.mav.heartbeat_send(2, 3, 217, 5, 4)
    m.mav.gps_raw_int_send(int(time.time() * 1e6), 3, int(lat * 1e7),
                           int(lon * 1e7), ALT_MM, 100, 100, 1400, cog, 11)
    m.mav.global_position_int_send(1000, int(lat * 1e7), int(lon * 1e7),
                                   ALT_MM, 100000, 0, 0, 0, cog)
    m.mav.vfr_hud_send(14.0, 14.5, int(cog / 100), 55, 120.0, 0.5)
    if i % 20 == 0:
        print(f"  t={i}s pos=({lat:.5f},{lon:.5f}) hdg={cog//100}")
    time.sleep(1)
    i += 5
