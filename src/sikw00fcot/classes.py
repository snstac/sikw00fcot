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
"""sikw00fcot worker classes."""

import asyncio

from pymavlink import mavutil

import pytak

from .functions import mav_to_cot

__author__ = "gba@snstac.com"
__license__ = "Apache License, Version 2.0"


# MAVLink message types we accumulate into a per-vehicle state view.
# NB: must be a list — pymavlink's recv_match only special-cases `list`; a
# tuple gets wrapped as [tuple] and silently matches nothing.
TRACKED = [
    "HEARTBEAT",
    "GLOBAL_POSITION_INT",
    "GPS_RAW_INT",
    "VFR_HUD",
    "ATTITUDE",
    "BATTERY_STATUS",
    "SYSTEM_TIME",
]


class MAVWorker(pytak.QueueWorker):
    """Reads MAVLink (from SiKW00F's UDP fan-out) and emits CoT.

    SiKW00F holds the serial port; it mirrors every received MAVLink frame to a
    local UDP socket. We connect to that socket as a passive listener so both
    the SiKW00F TUI and this gateway run at the same time.
    """

    def __init__(self, queue, config):
        super().__init__(queue, config)
        # Per-system-id accumulated state. Each drone (MAVLink sysid) gets its
        # own merged message view so multiple links produce distinct CoT UIDs.
        self._state: dict = {}
        self._conn = None

    def _connect(self):
        url = self.config.get("MAV_URL", "udpin:127.0.0.1:14550")
        self._logger.info("Listening for MAVLink on %s", url)
        # input=True => we are a passive sink; never transmit onto the link.
        self._conn = mavutil.mavlink_connection(
            url, dialect="ardupilotmega", input=True, autoreconnect=True
        )

    def _vehicle_state(self, sysid: int) -> dict:
        st = self._state.get(sysid)
        if st is None:
            st = {"_sysid": sysid, "_netid": self.config.get("SIK_NETID")}
            self._state[sysid] = st
        return st

    async def handle_data(self, data) -> None:
        await self.put_queue(data)

    async def close(self) -> None:
        """Release the MAVLink UDP socket so a restart can rebind it cleanly."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
            self._conn = None

    async def run(self, _=-1) -> None:
        self._connect()
        poll = float(self.config.get("POLL_INTERVAL", "0.2"))
        cot_interval = float(self.config.get("COT_INTERVAL", "2.0"))
        loop = asyncio.get_event_loop()
        last_emit = 0.0

        while True:
            # recv_match is blocking C code; run it off the event loop thread.
            msg = await loop.run_in_executor(
                None,
                lambda: self._conn.recv_match(type=TRACKED, blocking=True, timeout=1),
            )
            if msg is not None:
                sysid = msg.get_srcSystem() if hasattr(msg, "get_srcSystem") else 1
                st = self._vehicle_state(sysid)
                st[msg.get_type()] = msg.to_dict()

            now = loop.time()
            if now - last_emit >= cot_interval:
                last_emit = now
                for st in self._state.values():
                    event = mav_to_cot(st, self.config)
                    if event:
                        await self.handle_data(event)

            await asyncio.sleep(poll)
