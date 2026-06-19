#!/usr/bin/env python3
"""sikw00fscan CLI entry point — PyTAK CLITool + ScanWorker."""

import asyncio
import os

from configparser import ConfigParser

import pytak

from .runner import run_daemon
from .scan import ScanWorker

__author__ = "gba@snstac.com"
__license__ = "Apache License, Version 2.0"

_ENV_KEYS = (
    "COT_URL", "COT_TYPE", "COT_STALE", "COT_INTERVAL", "COT_CALLSIGN",
    "DEVICE", "BAUD", "SENSOR_LAT", "SENSOR_LON", "SENSOR_CE", "DETECT_TTL",
    "DETECT_MIN_HITS", "IGNORE_NETIDS",
    "PYTAK_TLS_CLIENT_CERT", "PYTAK_TLS_CLIENT_KEY", "PYTAK_TLS_CLIENT_CAFILE",
    "PYTAK_TLS_DONT_CHECK_HOSTNAME",
)


async def main() -> None:
    config = ConfigParser()
    config["sikw00fscan"] = {}
    section = config["sikw00fscan"]

    config_path = os.getenv("SIKW00FSCAN_CONFIG", "/etc/sikw00fscan/config.ini")
    if os.path.exists(config_path):
        config.read(config_path)
        section = config["sikw00fscan"]

    for key in _ENV_KEYS:
        if os.getenv(key) is not None:
            section[key] = os.getenv(key)

    clitool = pytak.CLITool(section)
    await clitool.setup()
    clitool.add_tasks({ScanWorker(clitool.tx_queue, section)})
    await clitool.run()


def cli() -> None:
    run_daemon(main, "sikw00fscan")


if __name__ == "__main__":
    cli()
