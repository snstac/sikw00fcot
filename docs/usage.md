# Usage

## sikw00fsentinel (recommended)

The autonomous detect-and-track daemon. Plug a SiK radio into the sensor, point
`DEVICE` at it, set `SENSOR_NETID` to a NetID your targets won't use, and start
it:

```sh
sudo systemctl enable --now sikw00fsentinel
sudo journalctl -fu sikw00fsentinel
```

State machine:

1. **SCAN** — the radio runs promiscuously, listening for any SiK link. A status
   marker (`SIKW00F:SCAN`) shows on the TAK map.
2. On a new NetID (≥ `DETECT_MIN_HITS` hits), it squawks a **detection alert** at
   the sensor location and transitions to **INSPECT**.
3. **INSPECT** — the radio tunes to that NetID and decodes MAVLink into a live
   drone **track** (`SIKW00F:INSPECT-<netid>`).
4. After `INSPECT_TIMEOUT` seconds with no decoded MAVLink, it reverts to SCAN
   (and won't re-INSPECT that NetID for `INSPECT_COOLDOWN` seconds).

## sikw00fscan

Detection-only: emits a CoT alert whenever a drone link is detected, without
tuning in to decode it. Useful as a pure tripwire.

```sh
sudo systemctl enable --now sikw00fscan
```

## sikw00fcot

Passive MAVLink → CoT sink, fed by SiKW00F's eavesdrop TUI.

1. Patch SiKW00F for UDP fan-out (idempotent, writes a `.bak`):

   ```sh
   python3 patches/apply_fanout.py /path/to/sikw00f/core/eavesdrop.py
   ```

2. Configure `/etc/default/sikw00fcot` and start the service:

   ```sh
   sudo systemctl enable --now sikw00fcot
   ```

3. Run SiKW00F eavesdrop as usual — fan-out is on by default
   (`SIKW00F_FANOUT=1`). Each MAVLink `sysid` becomes a distinct CoT track;
   position comes from `GLOBAL_POSITION_INT` (fallback `GPS_RAW_INT`), with
   below-2D fixes suppressed.

> The two radio daemons own the serial port exclusively — do **not** run
> `sikw00fscan`, `sikw00fsentinel`, or SiKW00F eavesdrop against the same radio
> at once.
