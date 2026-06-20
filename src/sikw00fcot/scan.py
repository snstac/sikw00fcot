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
"""sikw00fscan: continuous promiscuous SiK scan -> CoT detection alerts.

Owns the SiK radio (serial), keeps it in promiscuous mode (S16=1), and runs the
same RTI5/NetID read loop as SiKW00F's deep-scan. Each detected NetID becomes a
CoT alert to TAK. NB: this OWNS the radio, so it is mutually exclusive with
`sikw00f --eavesdrop` (which needs S16=0).
"""

import asyncio
import re
import time

import serial

import pytak

from .functions import detection_to_cot

__author__ = "gba@snstac.com"
__license__ = "Apache License, Version 2.0"

# Parse patterns lifted from SiKW00F core/scan.py so behaviour matches.
NETID_RE = re.compile(r"NetID:\s*(\d+)", re.IGNORECASE)
CHAN_RE = re.compile(r"Channel:\s*(\d+)", re.IGNORECASE)
PARAM_RE = re.compile(r"S(\d+):([A-Z0-9_]+)=([^\r\n]+)", re.IGNORECASE)


class ScanWorker(pytak.QueueWorker):
    """Promiscuous scanner that emits a CoT alert per active NetID."""

    def __init__(self, queue, config):
        super().__init__(queue, config)
        self._drones: dict = {}
        self._ser = None
        self._buf = ""  # carry partial (un-terminated) serial lines between reads
        self._own_netid = None    # this radio's own NETID — never alert on it
        self._ignore: set = set()  # extra NetIDs to suppress (config)

    # --- radio plumbing (mirrors SiKW00F scan helpers) ---
    def _open(self):
        dev = self.config.get("DEVICE", "/dev/ttyUSB0")
        baud = int(self.config.get("BAUD", "57600"))
        self._logger.info("Opening SiK radio %s@%s for promiscuous scan", dev, baud)
        for raw in str(self.config.get("IGNORE_NETIDS", "")).replace(",", " ").split():
            if raw.strip().isdigit():
                self._ignore.add(int(raw))
        self._ser = serial.Serial(dev, baud, timeout=0.05)
        self._enable_scanning_mode()

    def _enable_scanning_mode(self):
        s = self._ser
        time.sleep(1)
        s.reset_output_buffer()
        s.reset_input_buffer()
        s.write(b"\r\n")
        time.sleep(0.5)
        s.write(b"ATO\r\n")  # exit any prior AT mode
        time.sleep(1)
        s.write(b"+++")      # enter AT command mode
        time.sleep(2)
        s.write(b"ATS16=1\r\n")  # promiscuous, ephemeral (no AT&W/ATZ)
        time.sleep(1)
        self._read_lines()
        # Learn this radio's OWN NetID so we never alert on it (the promiscuous
        # firmware/RTI probes otherwise self-report it as a phantom drone).
        s.write(b"ATI5\r\n")
        time.sleep(0.5)
        for line in self._read_lines():
            m = re.match(r"S3:NETID=(\d+)", line, re.IGNORECASE)
            if m:
                self._own_netid = int(m.group(1))
        self._buf = ""
        self._read_lines()
        self._logger.info(
            "Promiscuous mode (S16=1) enabled; own NetID=%s ignored=%s",
            self._own_netid, sorted(self._ignore))

    def _read_lines(self):
        # Read whatever is available and only yield COMPLETE newline-terminated
        # lines. Partial lines stay in self._buf so "NetID: 25" never gets split
        # into a bogus "NetID: 2" by a mid-token read timeout.
        n = self._ser.in_waiting
        if n:
            self._buf += self._ser.read(n).decode(errors="replace")
        if len(self._buf) > 4096:  # runaway guard on line-noise with no newline
            self._buf = ""
        lines = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if line:
                lines.append(line)
        return lines

    def _poll_once(self):
        """Prompt the promiscuous firmware with RTI5 and parse what it reports.

        RTI5 polling is what drives the firmware to emit "NetID:/Channel:" lines
        for over-the-air packets. We deliberately do NOT set S3 to detected
        NetIDs (that mutates our own NetID and self-seeds phantom detections);
        new NetIDs surface from promiscuous reporting without it.
        """
        self._ser.write(b"RTI5\r\n")
        time.sleep(0.05)
        for line in self._read_lines():
            nm = NETID_RE.search(line)
            if nm:
                nid = int(nm.group(1))
                # Never treat our own radio's NetID (or configured ignores) as a
                # detection — those are self-reported, not over-the-air drones.
                if nid == self._own_netid or nid in self._ignore:
                    continue
                if nid not in self._drones:
                    self._drones[nid] = {
                        "netid": nid, "first": time.time(), "last": time.time(),
                        "chan": None, "pkts": 0, "hits": 1, "alerted": False,
                    }
                else:
                    self._drones[nid]["hits"] += 1
                    self._drones[nid]["last"] = time.time()
                continue
            cm = CHAN_RE.search(line)
            if cm and self._drones:
                last = next(reversed(self._drones))
                d = self._drones[last]
                d["chan"] = int(cm.group(1))
                d["pkts"] += 1
                d["last"] = time.time()

    async def handle_data(self, data) -> None:
        await self.put_queue(data)

    async def close(self) -> None:
        """Release the serial radio so a restart can re-acquire it cleanly."""
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
            self._ser = None

    async def run(self, _=-1) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._open)
        emit_interval = float(self.config.get("COT_INTERVAL", "10"))
        ttl = float(self.config.get("DETECT_TTL", "120"))
        # Min times a "NetID: X" line must appear before we believe it. The real
        # link reports constantly; parse fragments appear only a handful of times.
        min_hits = int(self.config.get("DETECT_MIN_HITS", "4"))
        last_emit = 0.0
        while True:
            await loop.run_in_executor(None, self._poll_once)
            now = loop.time()
            if now - last_emit >= emit_interval:
                last_emit = now
                wall = time.time()
                for info in self._drones.values():
                    if wall - info["last"] > ttl:
                        continue  # gone: stop refreshing, let CoT stale out
                    if info["hits"] < min_hits:
                        continue  # too few sightings — likely a parse fragment
                    if not info["alerted"]:
                        self._logger.info(
                            "ALERT NetID %s (hits=%s chan=%s)",
                            info["netid"], info["hits"], info["chan"])
                        info["alerted"] = True
                    event = detection_to_cot(info, self.config)
                    if event:
                        await self.handle_data(event)
            await asyncio.sleep(0.1)
