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
"""sikw00fcot CLI entry point — PyTAK CLITool wiring."""

import asyncio
import os

from configparser import ConfigParser

import pytak

from .classes import MAVWorker
from .runner import run_daemon

__author__ = "gba@snstac.com"
__license__ = "Apache License, Version 2.0"


async def main() -> None:
    """Read config, set up PyTAK, attach the MAVLink worker, run forever."""
    config = ConfigParser()
    # Section name PyTAK reads. Env vars (COT_URL, PYTAK_TLS_*) are merged in.
    config["sikw00fcot"] = {}
    section = config["sikw00fcot"]

    config_path = os.getenv("SIKW00FCOT_CONFIG", "/etc/sikw00fcot/config.ini")
    if os.path.exists(config_path):
        config.read(config_path)
        section = config["sikw00fcot"]

    # Environment overrides file (systemd EnvironmentFile friendly).
    for key in (
        "COT_URL",
        "COT_TYPE",
        "COT_STALE",
        "COT_INTERVAL",
        "COT_CALLSIGN",
        "MAV_URL",
        "SIK_NETID",
        "PYTAK_TLS_CLIENT_CERT",
        "PYTAK_TLS_CLIENT_KEY",
        "PYTAK_TLS_CLIENT_CAFILE",
        "PYTAK_TLS_DONT_CHECK_HOSTNAME",
    ):
        if os.getenv(key) is not None:
            section[key] = os.getenv(key)

    clitool = pytak.CLITool(section)
    await clitool.setup()
    clitool.add_tasks({MAVWorker(clitool.tx_queue, section)})
    await clitool.run()


def cli() -> None:
    """Console-script entry point."""
    run_daemon(main, "sikw00fcot")


if __name__ == "__main__":
    cli()
