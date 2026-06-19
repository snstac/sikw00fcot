#!/usr/bin/env bash
# Quick simulated-track suite: capture what the sentinel emits to TAK and score it.
set -uo pipefail
F=/tmp/track.txt
sudo PYTAK_TLS_DONT_CHECK_HOSTNAME=1 timeout "${1:-55}" /opt/sikw00fcot/venv/bin/pytak \
  tls://takserver.snstak.com:8089 --rx-only \
  --tls-cert /etc/sikw00fcot/sikw00fcot.pem \
  --tls-key /etc/sikw00fcot/sikw00fcot-key.pem \
  --tls-ca /etc/sikw00fcot/sikw00fcot-ca.pem --no-verify 2>/dev/null > "$F" || true
sed -i 's#</event>#</event>\n#g' "$F"

det=$(grep -c 'uid="sikw00f-scan-200"' "$F")
trk=$(grep -c 'uid="sikw00f-200"' "$F")
pos=$(grep 'uid="sikw00f-200"' "$F" | grep -oE 'lat="[-0-9.]*" lon="[-0-9.]*"' | sort -u | wc -l)
sta=$(grep -c 'uid="sikw00f-sentinel' "$F")

echo "########## SIMULATED TRACK SUITE ##########"
printf "detection alerts (sikw00f-scan-200): %s\n" "$det"
printf "telemetry tracks (sikw00f-200):      %s\n" "$trk"
printf "distinct positions (moving track):   %s\n" "$pos"
printf "status-marker frames:                %s\n" "$sta"
echo "modes seen:"; grep -oE 'callsign="SIKW00F:[^"]*"' "$F" | sort -u | sed 's/^/  /'
echo "sample moving positions:"; grep 'uid="sikw00f-200"' "$F" | grep -oE 'lat="[-0-9.]*" lon="[-0-9.]*"' | sort -u | head -6 | sed 's/^/  /'
echo "precision check (lat/lon <=4 dp):"
grep -oE '(lat|lon)="(-?[0-9]+\.[0-9]+)"' "$F" | sed -E 's/.*"(-?[0-9.]+)"/\1/' | awk -F. '{print (length($2)>4)?"BAD "$0:""}' | grep . | head -3 || echo "  all <=4 decimals OK"

echo "=== PASS/FAIL ==="
[ "$det" -ge 1 ] && echo "  PASS detection alert reached TAK" || echo "  FAIL detection alert"
[ "$trk" -ge 1 ] && echo "  PASS telemetry track reached TAK" || echo "  FAIL telemetry track"
[ "$pos" -ge 2 ] && echo "  PASS track is moving ($pos positions)" || echo "  FAIL track not moving ($pos)"
[ "$sta" -ge 1 ] && echo "  PASS status/mode marker reached TAK" || echo "  FAIL status marker"
rm -f "$F"
