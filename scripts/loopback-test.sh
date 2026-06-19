#!/usr/bin/env bash
# Localhost end-to-end test: synthetic MAVLink -> sikw00fcot -> CoT (udp sink).
# Nothing leaves the host. Run on nebra: bash loopback-test.sh
set -uo pipefail
VENV=/opt/sikw00fcot/venv
OUT=/tmp/sikw00fcot_cot_out.txt
GWLOG=/tmp/sikw00fcot_gw.log
: > "$OUT"; : > "$GWLOG"

# 1) CoT sink: TCP server on 18999 (pytak connects as client) -> append to $OUT
"$VENV/bin/python" - "$OUT" <<'PY' &
import socket, sys
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 18999)); srv.listen(1)
conn, _ = srv.accept()
with open(sys.argv[1], "a") as f:
    while True:
        d = conn.recv(65535)
        if not d: break
        f.write(d.decode("utf-8", "replace") + "\n"); f.flush()
PY
SINK=$!

# 2) Gateway: read fan-out udp/14550, emit CoT to the TCP sink.
MAV_URL=udpin:127.0.0.1:14550 COT_URL=tcp://127.0.0.1:18999 \
  COT_INTERVAL=1 COT_STALE=60 SIK_NETID=TEST1 \
  "$VENV/bin/sikw00fcot" >"$GWLOG" 2>&1 &
GW=$!
sleep 4

# 3) Inject synthetic drone MAVLink (sysid 7) to the fan-out port.
"$VENV/bin/python" - <<'PY'
from pymavlink import mavutil
import time
m = mavutil.mavlink_connection("udpout:127.0.0.1:14550", source_system=7)
for _ in range(10):
    m.mav.heartbeat_send(2, 3, 217, 5, 4)
    m.mav.gps_raw_int_send(int(time.time()*1e6), 3, 327157000, -1171611000, 120000, 100, 100, 0, 0, 11)
    m.mav.global_position_int_send(1000, 327157000, -1171611000, 120000, 100000, 0, 0, 0, 27000)
    time.sleep(0.4)
print("sent synthetic MAVLink")
PY
sleep 3

kill "$GW" "$SINK" 2>/dev/null
wait 2>/dev/null

echo "==================== GATEWAY LOG ===================="
tail -n 15 "$GWLOG"
echo "==================== CoT RECEIVED ===================="
echo "total frames: $(grep -c '<event' "$OUT" 2>/dev/null || echo 0)"
echo "drone (sikw00f-*) frames: $(grep -c 'uid=\"sikw00f-' "$OUT" 2>/dev/null || echo 0)"
echo "---- first drone CoT ----"
grep -o '<event[^>]*uid="sikw00f-[^>]*>.*</event>' "$OUT" | head -n 1 || echo "NONE FOUND"
echo "---- raw tail ----"; tail -c 1200 "$OUT"