#!/usr/bin/env bash
# Sets up the wall calendar on a Raspberry Pi so it starts at boot and paints
# the picture straight onto the HDMI screen. Run it from the repository folder:
#
#     bash pi/install.sh
#
# It asks for your password (sudo) to install packages and the boot service.
# Safe to run again after `git pull`.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$HOME/.config/wallcal/config.toml"
USER_NAME="$(id -un)"

echo "==> Installing system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pil

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
    echo "Python 3.9 or newer is needed. Update Raspberry Pi OS first." >&2
    exit 1
fi

echo "==> Installing the calendar software"
# --system-site-packages reuses the Pi's own Pillow, so nothing has to compile.
python3 -m venv --system-site-packages "$REPO/.venv"
"$REPO/.venv/bin/pip" install -q -r "$REPO/requirements.txt"

if [ ! -f "$CONFIG" ]; then
    mkdir -p "$(dirname "$CONFIG")"
    cp "$REPO/config.example.toml" "$CONFIG"
    chmod 600 "$CONFIG"
    echo
    echo "A settings file was created at $CONFIG"
    echo "Edit it (nano $CONFIG): add your calendar links and remove the # marks"
    echo "from the [screen] lines. Then run this script again."
    exit 0
fi
chmod 600 "$CONFIG"

echo "==> Testing the calendar links"
"$REPO/.venv/bin/python" -m wallcal check || {
    echo "Fix the links in $CONFIG, then run this script again." >&2
    exit 1
}

echo "==> Letting $USER_NAME draw on the screen"
sudo usermod -aG video,tty "$USER_NAME"

echo "==> Installing the boot service"
sudo tee /etc/systemd/system/wallcal.service >/dev/null <<UNIT
[Unit]
Description=Wall calendar hub
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
SupplementaryGroups=video tty
WorkingDirectory=$REPO
# Hide the blinking text cursor and stop the screen from blanking.
ExecStartPre=+/bin/sh -c 'printf "\\\\033[?25l\\\\033[9;0]" > /dev/tty1 || true'
ExecStart=$REPO/.venv/bin/python -m wallcal run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

# The login prompt on the screen would draw over the calendar. SSH still works.
sudo systemctl disable --now getty@tty1.service >/dev/null 2>&1 || true
sudo systemctl daemon-reload
sudo systemctl enable wallcal.service >/dev/null
sudo systemctl restart wallcal.service

echo
echo "Done. The calendar should be on the screen within a minute."
echo "  See what it is doing:  journalctl -u wallcal -f"
echo "  Stop it:               sudo systemctl stop wallcal"
echo "  Undo the screen login: sudo systemctl enable --now getty@tty1"
