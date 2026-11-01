#!/bin/bash
# Installs thermal-guard.sh as a service that starts at boot. Run it as root on the machine that runs hot
# (for a Proxmox setup: on the Proxmox host, not inside the container).
set -e
[ "$(id -u)" = 0 ] || { echo "Run this as root (sudo)."; exit 1; }
here="$(cd "$(dirname "$0")" && pwd)"
install -m 755 "$here/thermal-guard.sh" /usr/local/sbin/thermal-guard.sh
# a quick look first, so a machine with no sensor is told so now and not silently later
ONCE=1 /usr/local/sbin/thermal-guard.sh >/dev/null 2>/tmp/thermal-guard-check || { cat /tmp/thermal-guard-check; exit 1; }
cat > /etc/systemd/system/thermal-guard.service <<UNIT
[Unit]
Description=Thermal guard: lowers CPU power and speed when the CPU runs hot

[Service]
ExecStart=/usr/local/sbin/thermal-guard.sh
Restart=always
RestartSec=5
# when the service stops, the guard puts the normal power and speed back itself

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now thermal-guard.service
echo "Thermal guard is running. Watch it with: journalctl -u thermal-guard -f"
