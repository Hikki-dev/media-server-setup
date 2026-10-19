#!/usr/bin/env bash
# Shares folders and drives from this Linux computer to your home network (Windows, Mac, Linux, phones).
# Use this when the computer is not running the setup wizard, or when you prefer sharing without Docker.
#
# How to use it:
#   sudo bash "Share folders on this computer.sh" /mnt/Media /mnt/Backup
# Every folder you list becomes one share, named after the folder. You are asked to choose a share password.
# Add the word  --read-only  before the folders to make all of them read only.
# Run it again with a different list any time. Only the part this script wrote is replaced.
set -euo pipefail

BEGIN="# BEGIN media-server-setup"
END="# END media-server-setup"
CONF=/etc/samba/smb.conf
ALLOWED="127.0.0.1 ::1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 fe80::/10 fd00::/8"

say() { printf '\n%s\n' "$*"; }
stop() { printf '\nStopped: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || stop "Run this with sudo, like:  sudo bash \"$0\" /path/to/folder"
command -v apt-get >/dev/null 2>&1 || stop "This script supports Debian and Ubuntu. On other systems, follow docs/File sharing.md and write the same settings by hand."

RO=no; FOLDERS=()
for a in "$@"; do
  [ "$a" = "--read-only" ] && { RO=yes; continue; }
  [ -d "$a" ] || stop "$a is not a folder."
  FOLDERS+=("$(cd "$a" && pwd)")
done
[ ${#FOLDERS[@]} -gt 0 ] || stop "List at least one folder, like:  sudo bash \"$0\" /mnt/Media"

# the person who owns the files: every file made over the network belongs to them, so your other apps keep working
OWNER="${SHARE_OWNER:-${SUDO_USER:-}}"
[ -n "$OWNER" ] && id "$OWNER" >/dev/null 2>&1 || stop "Could not tell which user owns your files. Run again with:  SHARE_OWNER=yourname sudo -E bash \"$0\" ..."
LOGIN="${SHARE_USER:-media}"
[[ "$LOGIN" =~ ^[a-z_][a-z0-9_-]{0,30}$ ]] || stop "The share login name must be lowercase letters or numbers."

if [ -z "${SHARE_PASSWORD:-}" ]; then
  read -r -s -p "Choose a password for the share login \"$LOGIN\" (8 or more characters): " PW; echo
  read -r -s -p "Type it again: " PW2; echo
  [ "$PW" = "$PW2" ] || stop "The two passwords are different."
else PW="$SHARE_PASSWORD"; fi
[ ${#PW} -ge 8 ] || stop "The password needs 8 or more characters."

say "Installing Samba (the file sharing program) if it is missing."
export DEBIAN_FRONTEND=noninteractive
dpkg -s samba >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq samba >/dev/null; }

# the login: a locked system account that only exists to sign in to shares
id "$LOGIN" >/dev/null 2>&1 || useradd -M -s /usr/sbin/nologin "$LOGIN"
printf '%s\n%s\n' "$PW" "$PW" | smbpasswd -s -a "$LOGIN" >/dev/null
smbpasswd -e "$LOGIN" >/dev/null

# unique share names
declare -A used=(); BLOCK=""
for f in "${FOLDERS[@]}"; do
  n="$(basename "$f" | tr -cd 'A-Za-z0-9 _.-')"; [ -n "$n" ] || n=Share
  base="$n"; k=2; while [ -n "${used[${n,,}]:-}" ]; do n="$base $k"; k=$((k+1)); done; used[${n,,}]=1
  BLOCK+=$'\n'"[$n]
   path = $f
   browseable = yes
   read only = $RO
   guest ok = no
   valid users = $LOGIN
   force user = $OWNER
   create mask = 0664
   directory mask = 0775
   force create mode = 0664
   force directory mode = 0775
"
done

[ -f "$CONF" ] && cp -p "$CONF" "$CONF.bak-$(date +%Y%m%d-%H%M%S)"
# take out any block this script wrote before
if [ -f "$CONF" ] && grep -qF "$BEGIN" "$CONF"; then sed -i "/^$BEGIN\$/,/^$END\$/d" "$CONF"; fi
# shares of your own (anything except the standard global and printer parts)
OWN=$(grep -E '^\[' "$CONF" 2>/dev/null | grep -vEic '^\[(global|printers|print\$)\]' || true)

if [ "${OWN:-0}" = 0 ]; then
  # no shares of your own yet: write a clean file with the speed and safety settings
  cat > "$CONF" <<CONFIG
[global]
   workgroup = WORKGROUP
   server string = %h server
   server role = standalone server
   map to guest = never
   restrict anonymous = 2
   server min protocol = SMB2_10
   hosts allow = $ALLOWED
   hosts deny = 0.0.0.0/0
   ea support = no
   store dos attributes = no
   mangled names = no
   unix extensions = no
   use sendfile = yes
   aio read size = 16384
   aio write size = 16384
   socket options = TCP_NODELAY IPTOS_LOWDELAY
   deadtime = 30
   smb ports = 445
   disable netbios = yes
   load printers = no
   printing = bsd
   printcap name = /dev/null
   disable spoolss = yes

$BEGIN
$BLOCK
$END
CONFIG
else
  # you already share things yourself: keep every setting you have and only add these shares
  printf '\n%s\n%s\n%s\n' "$BEGIN" "$BLOCK" "$END" >> "$CONF"
  say "Your own file sharing settings were kept. For the speed and safety settings, see docs/File sharing.md."
fi

testparm -s "$CONF" >/dev/null 2>&1 || stop "The new settings were not accepted. Your old file is saved as $CONF.bak-*  (nothing was changed on the network)."
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  systemctl enable --now smbd >/dev/null 2>&1; systemctl restart smbd
fi

HOSTN=$(hostname); IP=$(hostname -I 2>/dev/null | awk '{print $1}'); TS=$(tailscale ip -4 2>/dev/null | head -1 || true)
say "Done. File sharing is on."
echo "Login: $LOGIN   (the password you just chose)"
for f in "${FOLDERS[@]}"; do n=$(basename "$f"); echo "  $n   Windows: \\\\$IP\\$n    Mac and Linux: smb://$IP/${n// /%20}"; done
[ -n "$TS" ] && echo "Away from home, with Tailscale on both devices, use $TS instead of $IP."
say "Your old settings are saved next to $CONF. Never open port 445 on your router."
