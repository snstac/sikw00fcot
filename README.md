# sikw00fcot

SiKW00F drone MAVLink telemetry → Cursor-on-Target (CoT) gateway, built on
[PyTAK](https://github.com/snstac/pytak). Same house pattern as `aiscot` /
`adsbcot`.

## How it fits together

```
drone SiK link ──RF──> SiK radio ──serial──> SiKW00F eavesdrop (curses TUI, owns /dev/ttyUSB0)
                                                    │  MAVLink fan-out (patch)
                                                    ▼
                                        udp:127.0.0.1:14550
                                                    ▼
                                  sikw00fcot (PyTAK) ──CoT/TLS──> takserver.snstak.com:8089
```

SiKW00F has **no DB/API** — telemetry only exists as the live MAVLink stream and
a curses TUI. A serial port has one reader, so we don't fight SiKW00F for it:
`patches/apply_fanout.py` teaches SiKW00F's eavesdrop loop to mirror every
MAVLink frame to a local UDP socket. `sikw00fcot` listens on that socket as a
passive sink and emits CoT.

## Install on nebra.local

1. Patch SiKW00F for UDP fan-out (idempotent, makes a `.bak`):
   ```
   python3 patches/apply_fanout.py /path/to/sikw00f/core/eavesdrop.py
   ```
2. Install the gateway: `pip3 install .` (or build a deb with `nfpm package -p deb`).
3. Drop TAK certs in `/etc/sikw00fcot/` and configure `/etc/default/sikw00fcot`
   (see `config/sikw00fcot.config.example`).
4. `systemctl enable --now sikw00fcot`
5. Run SiKW00F eavesdrop as usual — fan-out is on by default
   (`SIKW00F_FANOUT=1`).

## Config (env / `/etc/default/sikw00fcot`)

| Key | Default | Meaning |
|-----|---------|---------|
| `COT_URL` | — | TAK dest, e.g. `tls://takserver.snstak.com:8089` |
| `PYTAK_TLS_CLIENT_CERT/KEY/CAFILE` | — | client cert pattern (enroll once, then direct tls) |
| `MAV_URL` | `udpin:127.0.0.1:14550` | where to read the fan-out |
| `COT_TYPE` | `a-u-A-M-H-Q` | air / unknown / multirotor UAS |
| `COT_STALE` | `120` | CoT stale seconds |
| `COT_INTERVAL` | `2.0` | seconds between CoT emits per drone |
| `SIK_NETID` | — | NetID label for UID/callsign |

Position is taken from `GLOBAL_POSITION_INT` (fallback `GPS_RAW_INT`); a fix
below 2D is suppressed. Each MAVLink sysid becomes a distinct CoT track.
