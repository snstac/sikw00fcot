#!/usr/bin/env python3
"""Idempotently add a MAVLink UDP fan-out to SiKW00F's core/eavesdrop.py.

SiKW00F holds the serial port; this teaches its eavesdrop loop to mirror every
received MAVLink frame to a local UDP socket so the sikw00fcot CoT gateway can
consume telemetry concurrently. Safe to run more than once.

Usage:
    python3 apply_fanout.py /path/to/sikw00f/core/eavesdrop.py
"""

import sys
from pathlib import Path

MARKER = "# --- sikw00fcot fan-out ---"

# 1) Create the fan-out connection right after `master = mavutil...` block.
ANCHOR_CONN = "        autoreconnect=True\n    )\n"
INJECT_CONN = (
    ANCHOR_CONN
    + "\n"
    + "    " + MARKER + "\n"
    "    import os as _os\n"
    "    _fanout = None\n"
    "    if _os.getenv('SIKW00F_FANOUT', '1') == '1':\n"
    "        _fanout_url = _os.getenv('SIKW00F_FANOUT_URL', 'udpout:127.0.0.1:14550')\n"
    "        _fanout = mavutil.mavlink_connection(_fanout_url, input=False)\n"
    "        logger.info('[EAVSDROP] MAVLink fan-out -> %s', _fanout_url)\n"
    "    globals()['_SIKW00F_FANOUT'] = _fanout\n"
)

# 2) Forward each frame inside the read loop, next to the existing log call.
ANCHOR_LOOP = '                logger.info("MAVLINK: %s", msg)\n'
INJECT_LOOP = (
    ANCHOR_LOOP
    + "                _fo = globals().get('_SIKW00F_FANOUT')\n"
    "                if _fo is not None:\n"
    "                    try:\n"
    "                        _fo.write(msg.get_msgbuf())\n"
    "                    except Exception:\n"
    "                        pass\n"
)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    src = path.read_text()

    if MARKER in src:
        print(f"Already patched: {path}")
        return 0

    for anchor, inject, label in (
        (ANCHOR_CONN, INJECT_CONN, "fan-out connection"),
        (ANCHOR_LOOP, INJECT_LOOP, "loop forwarder"),
    ):
        if anchor not in src:
            print(f"ERROR: anchor for {label} not found; SiKW00F may have changed.")
            return 1
        src = src.replace(anchor, inject, 1)

    backup = path.with_suffix(path.suffix + ".bak")
    backup.write_text(path.read_text())
    path.write_text(src)
    print(f"Patched {path} (backup at {backup})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
