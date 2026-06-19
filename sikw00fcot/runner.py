#!/usr/bin/env python3
"""Shared daemon entry-point runner for sikw00fcot / sikw00fscan.

Policy: a lost or unreachable TAK connection is FATAL by design. We exit
non-zero with a single clean log line (no traceback spam) so systemd restarts
the daemon. The unit files use Restart=always + StartLimitIntervalSec=0 so the
restart loop never gives up while TAK is down.
"""

import asyncio
import logging
import sys

__author__ = "gba@snstac.com"
__license__ = "Apache License, Version 2.0"


def run_daemon(main_coro_factory, name: str) -> None:
    """Run an async main(); treat connection/IO loss as a clean fatal restart."""
    log = logging.getLogger(name)
    try:
        asyncio.run(main_coro_factory())
    except KeyboardInterrupt:
        sys.exit(0)
    except OSError as exc:
        # OSError covers ConnectionRefused/Reset, BrokenPipe, ssl.SSLError,
        # TimeoutError and serial I/O errors — all fatal; restart cleanly.
        log.error("Fatal connection/IO error (%s); exiting for clean restart.", exc)
        sys.exit(1)
    except Exception as exc:  # pylint: disable=broad-except
        log.error("Fatal error (%s); exiting for clean restart.", exc)
        sys.exit(1)
