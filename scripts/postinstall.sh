#!/bin/sh
set -e

# Service account + state dir (writable HOME for PyTAK cert cache).
if ! id sikw00fcot >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/sikw00fcot --create-home \
        --shell /usr/sbin/nologin sikw00fcot || true
fi
install -d -o sikw00fcot -g sikw00fcot -m 0750 /var/lib/sikw00fcot
# Cert dir: group-owned by sikw00fcot so the service user can read 640 certs.
install -d -o root -g sikw00fcot -m 0750 /etc/sikw00fcot

# Install the package payload from PyPI/local wheel into the system python.
pip3 install --quiet --upgrade sikw00fcot || \
    echo "NOTE: install the sikw00fcot wheel manually (pip3 install ./dist/*.whl)"

chmod 600 /etc/default/sikw00fcot || true

systemctl daemon-reload || true
echo "sikw00fcot installed. Edit /etc/default/sikw00fcot, drop TAK certs in"
echo "/etc/sikw00fcot, then: systemctl enable --now sikw00fcot"
