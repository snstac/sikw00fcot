#!/usr/bin/env bash
# sikw00f radio test suite (v2) — robust timing: journal is the detection oracle,
# TAK round-trip captured only AFTER events are confirmed flowing.
set -uo pipefail

PY=/tmp/dronevenv/bin/python
FAKE=/home/gba/Claude/sikw00fcot/scripts/fake_drone.py
SETNID=/tmp/sik_setnetid.py
RX_CERTS='--tls-cert /etc/sikw00fcot/sikw00fcot.pem --tls-key /etc/sikw00fcot/sikw00fcot-key.pem --tls-ca /etc/sikw00fcot/sikw00fcot-ca.pem --no-verify'
RX="sudo PYTAK_TLS_DONT_CHECK_HOSTNAME=1 timeout 22 /opt/sikw00fcot/venv/bin/pytak tls://takserver.snstak.com:8089 --rx-only $RX_CERTS"
PASS=0; FAIL=0
ok(){ if [ "$1" = 1 ]; then echo "  ✅ PASS: $2"; PASS=$((PASS+1)); else echo "  ❌ FAIL: $2"; FAIL=$((FAIL+1)); fi; }
stop_drone(){ sudo kill $(sudo lsof -t /dev/ttyUSB0 2>/dev/null) 2>/dev/null; sleep 1; }
start_drone(){ sudo $PY $FAKE /dev/ttyUSB0 57600 >/dev/null 2>&1 & sleep 2; }
set_netid(){ stop_drone; sudo python3 $SETNID "$1" >/dev/null 2>&1; sleep 2; }
now_ts(){ ssh nebra 'date "+%Y-%m-%d %H:%M:%S"'; }
# Poll the scanner journal up to ~44s for "ALERT NetID <n>"; echo HIT/MISS
detect_wait(){ ssh nebra "for i in \$(seq 1 22); do sudo journalctl -u sikw00fscan --since '$2' --no-pager | grep -aq 'ALERT NetID $1' && { echo HIT; exit; }; sleep 2; done; echo MISS"; }
capture(){ ssh nebra "$RX > /tmp/suite_rx.txt 2>/dev/null || true"; }
grab(){ ssh nebra 'cat /tmp/suite_rx.txt 2>/dev/null'; }
prec(){ ssh nebra '/opt/sikw00fcot/venv/bin/python - <<PY
import re
t=open("/tmp/suite_rx.txt").read()
v=[x for x in re.findall(r"(?:lat|lon)=\"(-?\d+\.\d+)\"", t) if x not in ("0.0",)]
bad=[x for x in v if len(x.split(".")[1])>4]
print("GOOD" if (v and not bad) else ("NODATA" if not v else "BAD"), "samples=",v[:4],"bad=",bad[:3])
PY'; }

echo "########## sikw00f RADIO TEST SUITE v2 ##########"
echo "===== PHASE 1: SCAN / DETECTION ====="
ssh nebra 'sudo systemctl restart sikw00fscan; sleep 4'   # one clean start

echo "[T1] Drone TX NetID 111 -> scanner detects (journal oracle)"
set_netid 111; start_drone; T=$(now_ts)
[ "$(detect_wait 111 "$T")" = HIT ] && ok 1 "NetID 111 detected" || ok 0 "NetID 111 detected"
echo "[T2] ...and that detection round-trips through TAK"
capture; RX1="$(grab)"
echo "$RX1" | grep -q 'uid="sikw00f-scan-111"' && ok 1 "sikw00f-scan-111 redistributed by TAK" || ok 0 "sikw00f-scan-111 via TAK"
echo "[T3] Own sensor NetID 25 never alerted (journal, whole run)"
ssh nebra 'sudo journalctl -u sikw00fscan --since "6 min ago" --no-pager | grep -aq "ALERT NetID 25"' && ok 0 "own NetID 25 wrongly alerted" || ok 1 "own NetID 25 excluded"
echo "[T4] lat/lon precision <=4 decimals on a real detection CoT"
P="$(prec)"; echo "      $P"; echo "$P" | grep -q '^GOOD' && ok 1 "lat/lon <=4 decimals" || ok 0 "precision ($P)"

echo "[T5] Re-tune radio NetID 222 -> detection follows"
ssh nebra 'sudo systemctl restart sikw00fscan; sleep 4'   # clear stale 111
set_netid 222; start_drone; T=$(now_ts)
[ "$(detect_wait 222 "$T")" = HIT ] && ok 1 "NetID 222 detected after re-tune" || ok 0 "NetID 222 after re-tune"

echo "[T6] Radio idle (no TX) -> no detection"
stop_drone; ssh nebra 'sudo systemctl restart sikw00fscan; sleep 4'
T=$(now_ts); sleep 22
ssh nebra "sudo journalctl -u sikw00fscan --since '$T' --no-pager | grep -aq 'ALERT'" && ok 0 "idle radio produced alert" || ok 1 "no false detection when idle"

echo "===== PHASE 2: EAVESDROP / TELEMETRY ====="
echo "[T7] Eavesdrop telemetry -> moving track to TAK"
stop_drone; ssh nebra 'sudo systemctl stop sikw00fscan'
set_netid 25
ssh nebra 'cd /home/gba/work/SNS/sikw00f && timeout 35 .venv/bin/python sikw00f.py --disable-promiscuous-mode >/dev/null 2>&1; tmux kill-session -t eav 2>/dev/null; : > sikw00f.log; tmux new-session -d -s eav ".venv/bin/python sikw00f.py --eavesdrop"'
start_drone
# wait until eavesdrop actually decodes position before capturing
EAV=MISS; for i in $(seq 1 20); do ssh nebra 'grep -aq GLOBAL_POSITION_INT /home/gba/work/SNS/sikw00f/sikw00f.log' && { EAV=HIT; break; }; sleep 2; done
[ "$EAV" = HIT ] && ok 1 "eavesdrop decoded telemetry over RF" || ok 0 "eavesdrop decoded telemetry"
capture; RX2="$(grab)"
echo "$RX2" | grep -q 'uid="sikw00f-25"' && ok 1 "telemetry track sikw00f-25 reached TAK" || ok 0 "track sikw00f-25 via TAK"
NL=$(echo "$RX2" | grep -o 'uid="sikw00f-25"[^>]*lat="[-0-9.]*"' | grep -o 'lat="[-0-9.]*"' | sort -u | wc -l)
[ "$NL" -ge 2 ] && ok 1 "track is moving ($NL distinct lats)" || ok 0 "track moving ($NL lats)"
P2="$(prec)"; echo "      $P2"; echo "$P2" | grep -q '^GOOD' && ok 1 "track lat/lon <=4 decimals" || ok 0 "track precision ($P2)"

echo "===== RESTORE PRODUCTION ====="
stop_drone; ssh nebra 'tmux kill-session -t eav 2>/dev/null; rm -f /tmp/suite_rx.txt'
set_netid 200; ssh nebra 'sudo systemctl start sikw00fscan; sleep 4'
ssh nebra 'for s in sikw00fscan sikw00fcot; do printf "  %s: %s\n" "$s" "$(systemctl is-active $s)"; done'
echo "########## RESULTS: $PASS passed, $FAIL failed ##########"
