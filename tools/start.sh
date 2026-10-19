#!/usr/bin/env bash
# Shared start script for Mac and Linux. Builds and starts the setup, then opens the browser.
OS="${1:-linux}"
say() { printf '\n\033[1;36m%s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m%s\033[0m\n' "$*"; read -r -p "Press Enter to close..." _; exit 1; }

say "Media Server Setup is starting."
command -v docker >/dev/null 2>&1 || {
  [ "$OS" = mac ] && open "https://www.docker.com/products/docker-desktop/" 2>/dev/null
  die "Docker is not installed. Install Docker Desktop on a Mac, or Docker Engine on Linux (https://docs.docker.com/engine/install/), start it, then open this file again."; }
if ! docker info >/dev/null 2>&1; then
  [ "$OS" = mac ] && { say "Starting Docker Desktop."; open -a Docker; }
  for _ in $(seq 1 45); do docker info >/dev/null 2>&1 && break; sleep 4; done
  docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker Desktop, then open this file again."
fi
docker compose version >/dev/null 2>&1 || die "Docker Compose is missing. Update Docker Desktop, or install the Docker Compose plugin."

STACK="${ARR_STACK_DIR:-$HOME/ArrStack}"
MEDIA="${ARR_MEDIA_DIR:-$HOME/ArrMedia}"
mkdir -p "$STACK" || die "Could not create $STACK"

say "Getting the setup ready. The first time it downloads about 100 MB."
docker build -q -t arr-wizard -f wizard/Dockerfile . >/dev/null || die "Could not get the setup ready. Check your internet."
docker rm -f arr-wizard >/dev/null 2>&1

ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')
# when Tailscale runs on this computer, let the setup reach it so it can make private HTTPS addresses for the apps
TS=""; [ -S /var/run/tailscale/tailscaled.sock ] && TS="-v /var/run/tailscale:/var/run/tailscale -e HOST_TAILSCALE=1"
docker run -d --name arr-wizard --restart unless-stopped -p 7979:7979 \
  -v /var/run/docker.sock:/var/run/docker.sock -v "$STACK":/stack \
  --add-host host.docker.internal:host-gateway $TS \
  -e HOST_STACK_DIR="$STACK" -e HOST_OS="$OS" -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  -e HOST_DEFAULT_MEDIA="$MEDIA" -e HOST_HOME="$HOME" -e HOST_ADDRESS="${ADDR:-localhost}" \
  arr-wizard >/dev/null || die "Could not start the setup. Is another program using port 7979?"

say "Ready. Opening http://localhost:7979"
sleep 2
( command -v open >/dev/null && open http://localhost:7979 ) || ( command -v xdg-open >/dev/null && xdg-open http://localhost:7979 ) || true
echo "If the page did not open, go to http://localhost:7979 yourself. You can close this window."
