#!/usr/bin/env python3
"""sikw00fsentinel: autonomous SCAN -> INSPECT -> SCAN state machine on one SiK radio.

COA:
  * Boot in SCAN (promiscuous): detect drone SiK NetIDs.
  * On a confirmed detection: squawk a detection CoT, then switch to INSPECT.
  * INSPECT: tune the radio to that NetID (same-band assumption), decode MAVLink,
    emit telemetry track CoT.
  * If no telemetry is decoded for INSPECT_TIMEOUT, revert to SCAN.
  * Always emit a status CoT showing the current mode (SCAN / INSPECT-<netid>).

This OWNS the radio and replaces the standalone scan/eavesdrop services.
"""

import asyncio
import re
import time

import serial

from pymavlink import mavutil

import pytak

from .functions import detection_to_cot, mav_to_cot, status_to_cot

__author__ = "gba@snstac.com"
__license__ = "Apache License, Version 2.0"

NETID_RE = re.compile(r"NetID:\s*(\d+)", re.IGNORECASE)
CHAN_RE = re.compile(r"Channel:\s*(\d+)", re.IGNORECASE)
S3_RE = re.compile(r"S3:NETID=(\d+)", re.IGNORECASE)

# MAVLink messages we accumulate while inspecting.
MAV_TYPES = [
    "HEARTBEAT", "GLOBAL_POSITION_INT", "GPS_RAW_INT", "VFR_HUD",
    "ATTITUDE", "BATTERY_STATUS", "SYSTEM_TIME",
]
# Messages that count as a usable telemetry decode (keep INSPECT alive).
MAV_LIVE = {"GLOBAL_POSITION_INT", "GPS_RAW_INT", "HEARTBEAT", "VFR_HUD", "ATTITUDE"}

SCAN = "SCAN"
INSPECT = "INSPECT"


class SentinelWorker(pytak.QueueWorker):
    """SCAN/INSPECT state machine; emits detection, track and status CoT."""

    def __init__(self, queue, config):
        super().__init__(queue, config)
        self._dev = config.get("DEVICE", "/dev/ttyUSB0")
        self._baud = int(config.get("BAUD", "57600"))
        self._min_hits = int(config.get("DETECT_MIN_HITS", "4"))
        self._inspect_timeout = float(config.get("INSPECT_TIMEOUT", "30"))
        self._cot_interval = float(config.get("COT_INTERVAL", "5"))
        self._status_interval = float(config.get("STATUS_INTERVAL", "30"))
        self._cooldown = float(config.get("INSPECT_COOLDOWN", str(self._inspect_timeout)))

        self._ser = None     # pyserial handle (SCAN mode)
        self._mav = None     # mavutil handle (INSPECT mode)
        self._buf = ""
        self._state = SCAN
        self._target = None
        self._own_netid = None
        self._ignore = set()
        self._drones = {}        # netid -> {hits, chan, last, ...}
        self._cooldowns = {}     # netid -> wall time until which not to re-inspect
        self._mavstate = {}
        self._last_decode = 0.0

    # ---------- serial / AT helpers ----------
    def _read_lines(self):
        n = self._ser.in_waiting
        if n:
            self._buf += self._ser.read(n).decode(errors="replace")
        if len(self._buf) > 4096:
            self._buf = ""
        out = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if line:
                out.append(line)
        return out

    def _at(self, cmd, wait=0.3):
        self._ser.write(cmd + b"\r\n")
        time.sleep(wait)

    # ---------- state entry (blocking; run in executor) ----------
    def _enter_scan(self):
        """(Re)configure the radio for promiscuous scanning."""
        if self._mav is not None:
            try:
                self._mav.close()
            except Exception:
                pass
            self._mav = None
        if self._ser is None:
            self._ser = serial.Serial(self._dev, self._baud, timeout=0.05)
        s = self._ser
        time.sleep(1)
        s.reset_output_buffer(); s.reset_input_buffer(); self._buf = ""
        s.write(b"\r\n"); time.sleep(0.5)
        s.write(b"ATO\r\n"); time.sleep(1)
        s.write(b"+++"); time.sleep(2)
        self._at(b"ATS16=1")                       # promiscuous on
        if self._own_netid is None:                # determine own NetID once
            cfg_nid = self.config.get("SENSOR_NETID")
            if cfg_nid is not None and str(cfg_nid).isdigit():
                # Authoritative sensor NetID — set the radio to it so detection
                # exclusion is deterministic and immune to leftover S3 state.
                self._own_netid = int(cfg_nid)
            else:
                self._at(b"ATI5", 0.5)             # else read whatever's on the radio
                for line in self._read_lines():
                    m = S3_RE.match(line)
                    if m:
                        self._own_netid = int(m.group(1))
            self._ignore = set()
            for raw in str(self.config.get("IGNORE_NETIDS", "")).replace(",", " ").split():
                if raw.isdigit():
                    self._ignore.add(int(raw))
        # Always (re)assert the sensor NetID — also restores it after INSPECT
        # retuned S3 to a target.
        if self._own_netid is not None:
            self._at(f"ATS3={self._own_netid}".encode())
        self._read_lines()
        self._state = SCAN
        self._target = None
        self._drones = {}
        self._logger.info("STATE=SCAN (own NetID=%s, ignore=%s)",
                          self._own_netid, sorted(self._ignore))

    def _enter_inspect(self, netid):
        """Tune the radio to `netid` (same band) and open MAVLink decode."""
        s = self._ser
        self._at(b"ATS16=0")                       # promiscuous off (transparent link)
        self._at(f"ATS3={netid}".encode())         # tune to the drone's NetID
        self._read_lines()
        s.write(b"ATO\r\n"); time.sleep(0.5)       # back to data mode
        try:
            s.close()
        except Exception:
            pass
        self._ser = None
        self._mav = mavutil.mavlink_connection(
            self._dev, baud=self._baud, dialect="ardupilotmega")
        self._state = INSPECT
        self._target = netid
        self._mavstate = {"_sysid": None, "_netid": netid}
        self._last_decode = time.time()
        self._good = 0
        self._bad = 0
        self._logger.info("STATE=INSPECT target NetID=%s", netid)

    # ---------- per-cycle polls (blocking; run in executor) ----------
    def _scan_poll(self):
        self._ser.write(b"RTI5\r\n")
        time.sleep(0.05)
        for line in self._read_lines():
            nm = NETID_RE.search(line)
            if nm:
                nid = int(nm.group(1))
                if nid == self._own_netid or nid in self._ignore:
                    continue
                d = self._drones.get(nid)
                if d is None:
                    self._drones[nid] = {"netid": nid, "first": time.time(),
                                         "last": time.time(), "chan": None,
                                         "pkts": 0, "hits": 1, "params": {}}
                else:
                    d["hits"] += 1
                    d["last"] = time.time()
                continue
            cm = CHAN_RE.search(line)
            if cm and self._drones:
                d = self._drones[next(reversed(self._drones))]
                d["chan"] = int(cm.group(1)); d["pkts"] += 1; d["last"] = time.time()

    def _pick_detection(self):
        """Return a confirmed NetID worth inspecting (past hits + cooldown)."""
        now = time.time()
        for nid, d in self._drones.items():
            if d["hits"] < self._min_hits:
                continue
            if now < self._cooldowns.get(nid, 0):
                continue
            return nid
        return None

    def _inspect_poll(self):
        """Read one MAVLink frame; return its type or None."""
        msg = self._mav.recv_match(blocking=True, timeout=1)
        if msg is None:
            return None
        mtype = msg.get_type()
        if mtype == "BAD_DATA":
            self._bad += 1
            return None
        if mtype in MAV_TYPES:
            self._mavstate[mtype] = msg.to_dict()
            if hasattr(msg, "get_srcSystem"):
                self._mavstate["_sysid"] = msg.get_srcSystem()
            if mtype in MAV_LIVE:
                self._last_decode = time.time()
            self._good += 1
        return mtype

    # ---------- CoT emit ----------
    async def _emit(self, payload):
        if payload:
            await self.put_queue(payload)

    async def _emit_status(self):
        await self._emit(status_to_cot(self._state, self._target, self.config))
        self._logger.info("status: mode=%s target=%s", self._state, self._target)

    async def handle_data(self, data) -> None:
        await self.put_queue(data)

    async def close(self) -> None:
        for h in (self._mav, self._ser):
            try:
                if h is not None:
                    h.close()
            except Exception:
                pass
        self._mav = None
        self._ser = None

    # ---------- main loop ----------
    async def run(self, _=-1) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._enter_scan)
        await self._emit_status()
        last_status = loop.time()
        last_track = 0.0

        while True:
            if self._state == SCAN:
                await loop.run_in_executor(None, self._scan_poll)
                nid = self._pick_detection()
                if nid is not None:
                    info = self._drones[nid]
                    await self._emit(detection_to_cot(info, self.config))
                    self._logger.info("DETECTED NetID %s (hits=%s) -> INSPECT",
                                      nid, info["hits"])
                    await loop.run_in_executor(None, lambda: self._enter_inspect(nid))
                    await self._emit_status()
                    last_track = 0.0
            else:  # INSPECT
                await loop.run_in_executor(None, self._inspect_poll)
                now = loop.time()
                if now - last_track >= self._cot_interval:
                    last_track = now
                    self._logger.info("INSPECT NetID %s: good=%d bad=%d",
                                      self._target, self._good, self._bad)
                    await self._emit(mav_to_cot(self._mavstate, self.config))
                if time.time() - self._last_decode > self._inspect_timeout:
                    self._logger.info(
                        "INSPECT idle %.0fs on NetID %s (good=%d bad=%d) -> SCAN",
                        self._inspect_timeout, self._target, self._good, self._bad)
                    self._cooldowns[self._target] = time.time() + self._cooldown
                    await loop.run_in_executor(None, self._enter_scan)
                    await self._emit_status()

            if loop.time() - last_status > self._status_interval:
                last_status = loop.time()
                await self._emit_status()
            await asyncio.sleep(0.02)
