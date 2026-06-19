#!/usr/bin/env python3
"""sikw00fsentinel CLI entry point — PyTAK CLITool + SentinelWorker."""

import os

from configparser import ConfigParser

import pytak

from .runner import run_daemon
from .sentinel import SentinelWorker

__author__ = "gba@snstac.com"
__license__ = "Apache License, Version 2.0"

_ENV_KEYS = (
    "COT_URL", "COT_TYPE", "COT_STALE", "COT_INTERVAL", "COT_CALLSIGN",
    "STATUS_COT_TYPE", "STATUS_INTERVAL", "STATUS_STALE", "SENSOR_NAME",
    "DEVICE", "BAUD", "SENSOR_LAT", "SENSOR_LON", "SENSOR_CE", "SENSOR_NETID",
    "DETECT_MIN_HITS", "IGNORE_NETIDS", "INSPECT_TIMEOUT", "INSPECT_COOLDOWN",
    "PYTAK_TLS_CLIENT_CERT", "PYTAK_TLS_CLIENT_KEY", "PYTAK_TLS_CLIENT_CAFILE",
    "PYTAK_TLS_DONT_CHECK_HOSTNAME",
)


async def main() -> None:
    config = ConfigParser()
    config["sikw00fsentinel"] = {}
    section = config["sikw00fsentinel"]

    config_path = os.getenv("SIKW00FSENTINEL_CONFIG", "/etc/sikw00fsentinel/config.ini")
    if os.path.exists(config_path):
        config.read(config_path)
        section = config["sikw00fsentinel"]

    for key in _ENV_KEYS:
        if os.getenv(key) is not None:
            section[key] = os.getenv(key)

    clitool = pytak.CLITool(section)
    await clitool.setup()
    clitool.add_tasks({SentinelWorker(clitool.tx_queue, section)})
    await clitool.run()


def cli() -> None:
    run_daemon(main, "sikw00fsentinel")


if __name__ == "__main__":
    cli()
