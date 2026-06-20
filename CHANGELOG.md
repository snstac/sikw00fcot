# SIKW00FCOT Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0]

Initial release.

### Added

- `sikw00fcot`: MAVLink (UDP) to CoT gateway. Consumes drone MAVLink
  eavesdropped and fanned out by SiKW00F and forwards position/track CoT to TAK.
- `sikw00fscan`: promiscuous SiK NetID scanner that emits a CoT detection alert
  when a drone telemetry link is detected near the sensor.
- `sikw00fsentinel`: autonomous SCAN <-> INSPECT state machine on a single SiK
  radio. Scans in promiscuous mode, squawks a detection on a new NetID, switches
  to INSPECT to decode MAVLink, and reverts to SCAN on timeout. Emits a status
  CoT marker showing the current mode.
- 4-decimal lat/lon truncation via `pytak.truncate_float`.
- Clean fatal-restart behavior: a lost or unreachable TAK connection exits
  non-zero with a single log line so systemd restarts the daemon.
- `wss://` (TAK Protocol websocket) delivery support via the optional
  `takproto` extra.
- Debian/RPM packaging (snstac house style), systemd units, and Docker image.
- SiKW00F MAVLink fan-out patch (`patches/apply_fanout.py`).
