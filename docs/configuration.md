# Configuration

Each daemon reads configuration from its systemd `EnvironmentFile`
(`/etc/default/<daemon>`) or an `.ini` section. Fully-commented examples for all
three live in
[`config/`](https://github.com/snstac/sikw00fcot/tree/main/config).

All [PyTAK](https://pytak.rtfd.io/) settings apply — most importantly `COT_URL`
and the `PYTAK_TLS_*` client-certificate keys.

## CoT destination

```ini
# Recommended: TLS streaming
COT_URL=tls://takserver.example.com:8089
PYTAK_TLS_CLIENT_CERT=/etc/sikw00fcot/sikw00fcot.pem
PYTAK_TLS_CLIENT_KEY=/etc/sikw00fcot/sikw00fcot-key.pem
PYTAK_TLS_CLIENT_CAFILE=/etc/sikw00fcot/sikw00fcot-ca.pem
PYTAK_TLS_DONT_CHECK_HOSTNAME=1
```

## Common keys

| Key | Default | Daemons | Meaning |
|-----|---------|---------|---------|
| `COT_URL` | — | all | TAK destination URL |
| `COT_TYPE` | `a-u-A-M-H-Q` | all | Drone marker type |
| `COT_STALE` | `120` | all | CoT stale ("timeout") seconds |
| `COT_INTERVAL` | `5` | all | Seconds between CoT emissions |
| `DEVICE` | `/dev/ttyUSB0` | scan, sentinel | SiK radio serial device |
| `BAUD` | `57600` | scan, sentinel | SiK radio baud rate |
| `SENSOR_LAT` / `SENSOR_LON` | `0` | scan, sentinel | Sensor location |
| `SENSOR_NETID` | — | sentinel | Sensor radio's own NetID (excluded from detections) |
| `IGNORE_NETIDS` | — | scan, sentinel | NetIDs to never detect (comma/space separated) |
| `DETECT_MIN_HITS` | `4` | scan, sentinel | `NetID:` hits before confirming a detection |
| `INSPECT_TIMEOUT` | `30` | sentinel | Seconds with no MAVLink before INSPECT → SCAN |
| `INSPECT_COOLDOWN` | `30` | sentinel | Don't re-INSPECT a failed NetID for this long |
| `MAV_URL` | `udpin:127.0.0.1:14550` | sikw00fcot | Where to read the SiKW00F UDP fan-out |

## wss:// delivery

`wss://takserver.example.com:8443/takproto/1` works with enrolled PEM certs, but:

- it needs the `takproto` extra installed (otherwise pytak sends raw XML to the
  protobuf endpoint and TAK silently drops it);
- use the **direct** `wss://` URL, not a `tak://...enroll` URL (pytak's
  enrollment path reuses a 30 s timeout session that drops the websocket);
- pytak's `403` handler **deletes** the cert file it used — keep a backup.

See
[`config/sikw00fsentinel.config.example`](https://github.com/snstac/sikw00fcot/blob/main/config/sikw00fsentinel.config.example)
for the details.
