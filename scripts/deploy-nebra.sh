#!/usr/bin/env bash
# Deploy sikw00fcot to nebra.local over the `nebra` ssh alias.
# Requires: passwordless ssh + passwordless sudo (see SSH SETUP).
# Installs into a dedicated venv (Debian 12 is PEP-668 externally-managed).
# Does NOT enable/start the service — that needs TAK certs first.
set -euo pipefail

HOST="${1:-nebra}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
SIKW00F_DIR="${SIKW00F_DIR:-/home/gba/work/SNS/sikw00f}"
VENV="/opt/sikw00fcot/venv"

echo ">> Copying project to ${HOST}:/tmp/sikw00fcot"
rsync -a --delete --exclude .git --exclude '__pycache__' "${SRC}/" "${HOST}:/tmp/sikw00fcot/"

echo ">> Patch SiKW00F fan-out + install gateway venv on ${HOST}"
ssh "${HOST}" SIKW00F_DIR="${SIKW00F_DIR}" VENV="${VENV}" bash -s <<'EOF'
set -euo pipefail

# 1) Patch SiKW00F eavesdrop for UDP fan-out (idempotent, makes .bak).
python3 /tmp/sikw00fcot/patches/apply_fanout.py "${SIKW00F_DIR}/core/eavesdrop.py"

# 2) Dedicated venv (keeps system python clean).
sudo install -d -m755 /opt/sikw00fcot
[ -x "${VENV}/bin/python" ] || sudo python3 -m venv "${VENV}"
sudo "${VENV}/bin/pip" install --quiet --upgrade pip
sudo "${VENV}/bin/pip" install --quiet /tmp/sikw00fcot

# 3) Service account + state dir (writable HOME for PyTAK cert cache).
id sikw00fcot >/dev/null 2>&1 || sudo useradd --system --home-dir /var/lib/sikw00fcot \
    --create-home --shell /usr/sbin/nologin sikw00fcot
sudo install -d -o sikw00fcot -g sikw00fcot -m750 /var/lib/sikw00fcot
# Dir must be group-owned by sikw00fcot so the service user can traverse it
# and read the 640 root:sikw00fcot cert files inside.
sudo install -d -o root -g sikw00fcot -m750 /etc/sikw00fcot

# 4) systemd units + configs (don't clobber existing configs).
sudo install -D -m644 /tmp/sikw00fcot/config/sikw00fcot.service /lib/systemd/system/sikw00fcot.service
sudo install -D -m644 /tmp/sikw00fcot/config/sikw00fscan.service /lib/systemd/system/sikw00fscan.service
if [ ! -f /etc/default/sikw00fcot ]; then
  sudo install -m600 /tmp/sikw00fcot/config/sikw00fcot.config.example /etc/default/sikw00fcot
  echo "Installed default config -> edit /etc/default/sikw00fcot, add TAK certs to /etc/sikw00fcot."
fi
sudo install -d -m750 /etc/sikw00fscan
if [ ! -f /etc/default/sikw00fscan ]; then
  sudo install -m600 /tmp/sikw00fcot/config/sikw00fscan.config.example /etc/default/sikw00fscan
  echo "Installed scan config -> edit /etc/default/sikw00fscan, SET SENSOR_LAT/LON."
fi
sudo systemctl daemon-reload

echo "OK. Gateway installed (service NOT enabled). Next: install TAK certs, then"
echo "  sudo systemctl enable --now sikw00fcot"
# Verify the package imports cleanly (does NOT start the gateway).
sudo "${VENV}/bin/python" -c "import sikw00fcot, pytak, pymavlink; print('import OK', sikw00fcot.__version__)"
EOF
echo ">> Deploy step complete."
