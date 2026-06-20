# Installation

`sikw00fcot` requires Python 3.9+ and runs on Linux (Raspberry Pi included).

## Debian / Ubuntu / Raspberry Pi (.deb)

Download the latest `.deb` from
[Releases](https://github.com/snstac/sikw00fcot/releases) and install it:

```sh
sudo apt update
sudo apt install ./sikw00fcot_latest_all.deb
```

The package:

- installs the three commands (`sikw00fcot`, `sikw00fscan`, `sikw00fsentinel`),
- creates a `sikw00fcot` system user (added to `dialout` for serial access),
- installs and **enables** the `sikw00fcot.service` gateway,
- installs the config example to `/etc/default/sikw00fcot`.

The two radio daemons (`sikw00fscan`, `sikw00fsentinel`) are **not** enabled by
default because they contend for the same serial port. To run one, copy its unit
and config from [`config/`](https://github.com/snstac/sikw00fcot/tree/main/config):

```sh
sudo cp config/sikw00fsentinel.service /etc/systemd/system/
sudo cp config/sikw00fsentinel.config.example /etc/default/sikw00fsentinel
sudo nano /etc/default/sikw00fsentinel
sudo systemctl enable --now sikw00fsentinel
```

## pip

```sh
python3 -m pip install sikw00fcot
```

For `wss://` (TAK Protocol websocket) delivery, install the extra:

```sh
python3 -m pip install 'sikw00fcot[with_takproto]'
```

## From source

```sh
git clone https://github.com/snstac/sikw00fcot
cd sikw00fcot
make editable
```

## Building packages

```sh
sudo bash debian/install_pkg_build_deps.sh
make clean install_test_requirements package   # -> deb_dist/*.deb
```
