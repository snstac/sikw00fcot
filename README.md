# SIKW00FCOT - Detect & Track Drones in TAK

`sikw00fcot` detects and tracks drones in the [Team Awareness Kit
(TAK)](https://tak.gov/) ecosystem — ATAK, WinTAK, iTAK & TAK Server — from
their [SiK radio](https://github.com/ArduPilot/SiK) telemetry links, building on
[SiKW00F](https://github.com/nicholasaleks/sikw00f) and
[PyTAK](https://github.com/snstac/pytak).

It ships three daemons, each a PyTAK gateway:

| Command | What it does |
|---|---|
| **`sikw00fsentinel`** | Autonomous **SCAN ⇄ INSPECT** state machine on one SiK radio. Scans promiscuously, squawks a CoT alert on a new drone link, switches to INSPECT to decode MAVLink into a live track, and reverts to SCAN on timeout. Emits a status marker showing its current mode. **The recommended, plug-in-a-radio daemon.** |
| **`sikw00fscan`** | Promiscuous SiK NetID scanner. Emits a CoT **detection alert** (no position) whenever a drone telemetry link is detected near the sensor. |
| **`sikw00fcot`** | MAVLink → CoT gateway. Consumes drone MAVLink eavesdropped and fanned-out by SiKW00F over UDP and forwards full position/track CoT. |

## How it fits together

`sikw00fsentinel` / `sikw00fscan` own the SiK radio directly over serial — no
SiKW00F process required:

```
drone SiK link ──RF──> SiK radio ──serial──> sikw00fsentinel ──CoT──> TAK Server
                                             (SCAN ⇄ INSPECT)
```

`sikw00fcot` is a passive sink for SiKW00F's eavesdrop TUI. A serial port has
one reader, so we don't fight SiKW00F for it: `patches/apply_fanout.py` teaches
SiKW00F's eavesdrop loop to mirror every MAVLink frame to a local UDP socket,
which `sikw00fcot` reads:

```
SiK radio ──serial──> SiKW00F eavesdrop ──UDP fan-out──> sikw00fcot ──CoT──> TAK Server
                      (owns the serial port)            (udp:127.0.0.1:14550)
```

## Installation

### Debian / Ubuntu / Raspberry Pi (.deb)

Grab the `.deb` from [Releases](https://github.com/snstac/sikw00fcot/releases):

```sh
sudo apt update
sudo apt install ./sikw00fcot_latest_all.deb
```

This installs all three commands and enables the `sikw00fcot` gateway service.
To run the autonomous `sikw00fsentinel` instead, install its unit + config from
[`config/`](config/) (the two radio daemons aren't auto-enabled — they conflict
over the serial port).

### pip

```sh
python3 -m pip install sikw00fcot
# For wss:// (TAK Protocol websocket) delivery:
python3 -m pip install 'sikw00fcot[with_takproto]'
```

## Configuration

Configuration is via an environment file (systemd `EnvironmentFile`) or an `.ini`
section. See [`config/`](config/) for fully-commented examples for each daemon.

Common keys (plus all [PyTAK](https://pytak.rtfd.io/) `COT_URL` / `PYTAK_TLS_*`
settings):

| Key | Default | Meaning |
|-----|---------|---------|
| `COT_URL` | — | TAK destination, e.g. `tls://takserver.example.com:8089` |
| `DEVICE` | `/dev/ttyUSB0` | SiK radio serial device (scan/sentinel) |
| `BAUD` | `57600` | SiK radio baud |
| `SENSOR_LAT` / `SENSOR_LON` | `0` | Sensor location; detections/status are placed here |
| `SENSOR_NETID` | — | This sensor radio's own NetID (always excluded from detections) |
| `IGNORE_NETIDS` | — | NetIDs to never detect (comma/space separated) |
| `DETECT_MIN_HITS` | `4` | `NetID:` hits before a detection is confirmed |
| `INSPECT_TIMEOUT` | `30` | Seconds with no decoded MAVLink before INSPECT → SCAN |
| `MAV_URL` | `udpin:127.0.0.1:14550` | Where `sikw00fcot` reads the fan-out |
| `COT_TYPE` | `a-u-A-M-H-Q` | Drone marker (air / unknown / multirotor UAS) |
| `COT_STALE` | `120` | CoT stale seconds |

Lat/lon are truncated to 4 decimals via `pytak.truncate_float`. A lost TAK
connection is treated as fatal: the daemon exits cleanly so systemd
(`Restart=always`) reconnects.

> **wss:// note:** `wss://...:8443/takproto/1` works with enrolled PEM certs but
> needs the `takproto` extra (without it pytak sends raw XML and TAK drops it),
> and pytak's enrollment/403 paths have footguns — see
> [`config/sikw00fsentinel.config.example`](config/sikw00fsentinel.config.example).

## Source / development

```sh
git clone https://github.com/snstac/sikw00fcot
cd sikw00fcot
make editable                    # pip install -e .
make install_test_requirements
make test                        # pytest
make package                     # build .deb (needs debian/install_pkg_build_deps.sh)
```

## License & Copyright

Copyright Sensors & Signals LLC <https://www.snstac.com>

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
