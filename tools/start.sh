#!/usr/bin/env bash
# Shared start script for Mac and Linux. Builds and starts the setup, then opens the browser.
# Usage: start.sh [mac|linux] [--headless]
#   --headless (or ARR_HEADLESS=1): do not open a browser; print the address to open from another computer.
#   On Linux with no screen (an LXC, a VPS, a server) this is chosen for you.
#   Settings you can put in front of the command: ARR_STACK_DIR, ARR_MEDIA_DIR, ARR_UID, ARR_GID (who owns the files), ARR_ADDRESS, ARR_HOME.
OS="linux"; HEADLESS="${ARR_HEADLESS:-}"
for a in "$@"; do case "$a" in mac|linux) OS="$a" ;; --headless) HEADLESS=1 ;; esac; done
[ "$OS" = linux ] && [ -z "$HEADLESS" ] && [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && HEADLESS=1

# ---- look ------------------------------------------------------------------
if [ -t 1 ]; then B=$'\033[1m'; D=$'\033[2m'; C=$'\033[36m'; G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; N=$'\033[0m'; else B=; D=; C=; G=; R=; Y=; N=; fi
case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in *UTF-8*|*utf8*|*UTF8*) OK="✔"; BAD="✘"; SP=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏) ;; *) OK="+"; BAD="x"; SP=("-" "\\" "|" "/") ;; esac
TOTAL=5; NOW=0; LOG="$(mktemp -t arr-setup.XXXXXX)"
banner() {
  printf '\n  %s%s\n' "$B$C" "Media Server Setup$N"
  printf '  %s%s%s\n\n' "$D" "Movies, shows, anime, comics and manga, set up for you." "$N"
}
fail() {
  printf '\r\033[K  %s%s%s %s\n' "$R" "$BAD" "$N" "$1" >&2
  shift; for l in "$@"; do printf '      %s\n' "$l" >&2; done
  [ -s "$LOG" ] && { printf '\n  %sWhat the computer said:%s\n' "$D" "$N" >&2; tail -n 6 "$LOG" | sed 's/^/      /' >&2; }
  printf '\n' >&2
  [ -t 0 ] && read -r -p "  Press Enter to close..." _
  exit 1
}
# step "label" command...   Shows a spinner while the command runs, then a tick.
step() {
  NOW=$((NOW + 1)); local label="$1"; shift
  : > "$LOG"; "$@" >"$LOG" 2>&1 & local pid=$! i=0
  while kill -0 "$pid" 2>/dev/null; do
    [ -t 1 ] && printf '\r  %s[%d/%d]%s %s %s%s%s ' "$D" "$NOW" "$TOTAL" "$N" "$label" "$C" "${SP[i % ${#SP[@]}]}" "$N"
    i=$((i + 1)); sleep 0.15
  done
  wait "$pid"; local rc=$?; [ "$rc" -ne 0 ] && return "$rc"
  printf '\r\033[K  %s[%d/%d]%s %s %s%s%s\n' "$D" "$NOW" "$TOTAL" "$N" "$label" "$G" "$OK" "$N"
}

banner

# ---- 1. Docker -------------------------------------------------------------
check_docker() {
  command -v docker >/dev/null 2>&1 || return 2
  if ! docker info >/dev/null 2>&1; then
    [ "$OS" = mac ] && open -a Docker 2>/dev/null
    for _ in $(seq 1 45); do docker info >/dev/null 2>&1 && break; sleep 4; done
    docker info >/dev/null 2>&1 || return 3
  fi
  docker compose version >/dev/null 2>&1 || return 4
}
step "Checking Docker" check_docker; rc=$?
case $rc in
  0) ;;
  2) [ "$OS" = mac ] && open "https://www.docker.com/products/docker-desktop/" 2>/dev/null
     fail "Docker is not installed." "Mac: install Docker Desktop (the download page just opened), start it, then open this file again." \
          "Linux: install Docker Engine from https://docs.docker.com/engine/install/ then run this again." ;;
  3) fail "Docker is installed but not running." "Start Docker Desktop (or run: sudo systemctl start docker), wait until it says running, then open this file again." ;;
  *) fail "Docker Compose is missing." "Update Docker Desktop, or install the Docker Compose plugin." ;;
esac

STACK="${ARR_STACK_DIR:-$HOME/ArrStack}"
MEDIA="${ARR_MEDIA_DIR:-$HOME/ArrMedia}"
cd "$(dirname "$0")/.." || fail "Could not find the project folder."

# ---- 2. Build --------------------------------------------------------------
step "Preparing folders" mkdir -p "$STACK" || fail "Could not create $STACK" "Choose another place with: ARR_STACK_DIR=/some/folder bash start.sh"
step "Getting the setup ready (first time: about 100 MB)" docker build -q -t arr-wizard -f wizard/Dockerfile . \
  || fail "Could not get the setup ready." "Check your internet connection, then try again."

# ---- 3. Start --------------------------------------------------------------
ADDR="${ARR_ADDRESS:-}"      # set ARR_ADDRESS to show a different address (for example a fixed IP or a name)
[ -z "$ADDR" ] && ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$ADDR" ] && [ "$OS" = mac ] && ADDR=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
# when Tailscale runs on this computer, let the setup reach it so it can make private HTTPS addresses for the apps
TS=(); [ -S /var/run/tailscale/tailscaled.sock ] && TS=(-v /var/run/tailscale:/var/run/tailscale -e HOST_TAILSCALE=1)
start_wizard() {
  docker rm -f arr-wizard >/dev/null 2>&1
  docker run -d --name arr-wizard --restart unless-stopped -p 7979:7979 \
    -v /var/run/docker.sock:/var/run/docker.sock -v "$STACK":/stack \
    --add-host host.docker.internal:host-gateway "${TS[@]}" \
    -e HOST_STACK_DIR="$STACK" -e HOST_OS="$OS" -e HOST_UID="${ARR_UID:-$(id -u)}" -e HOST_GID="${ARR_GID:-$(id -g)}" \
    -e HOST_DEFAULT_MEDIA="$MEDIA" -e HOST_HOME="${ARR_HOME:-$HOME}" -e HOST_ADDRESS="${ADDR:-localhost}" \
    arr-wizard
}
step "Starting the setup" start_wizard \
  || fail "Could not start the setup." "Another program may be using port 7979. Close it and try again."

# ---- 4. Open ---------------------------------------------------------------
LOCAL="http://localhost:7979"; LAN="http://${ADDR:-this-computer}:7979"
if [ -n "$HEADLESS" ]; then
  NOW=$((NOW + 1)); printf '  %s[%d/%d]%s No screen found, so no browser is opened %s%s%s\n' "$D" "$NOW" "$TOTAL" "$N" "$G" "$OK" "$N"
else
  step "Opening your browser" bash -c "sleep 2; (command -v open >/dev/null && open $LOCAL) || (command -v xdg-open >/dev/null && xdg-open $LOCAL) || true"
fi

printf '\n  %sYour setup page is ready.%s\n\n' "$B$G" "$N"
if [ -n "$HEADLESS" ]; then
  printf '  Open this on any computer on your network:\n\n      %s%s%s\n\n' "$B$C" "$LAN" "$N"
  printf '  %sNo screen on this machine? That is fine. The page works from any browser.\n  Away from home, use: ssh -L 7979:localhost:7979 you@%s  and open %s%s\n' "$D" "${ADDR:-this-computer}" "$LOCAL" "$N"
else
  printf '  If your browser did not open, go to:\n\n      %s%s%s\n\n' "$B$C" "$LOCAL" "$N"
  [ -n "$ADDR" ] && printf '  %sFrom another computer on your network: %s%s\n' "$D" "$LAN" "$N"
fi
printf '\n  %sYou can close this window. The setup keeps running, and stopping it never touches your media.%s\n\n' "$D" "$N"
rm -f "$LOG"
