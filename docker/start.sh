#!/bin/bash
# Run the SiKW00F to TAK gateway. Override the command (e.g. sikw00fsentinel)
# and pass --device /dev/ttyUSB0 to the container to run a radio daemon instead.
set -a
[ -f /etc/default/sikw00fcot ] && . /etc/default/sikw00fcot
set +a
exec /usr/local/bin/sikw00fcot
