#!/usr/bin/env bash
# One-line installer for Linux and Mac (also an LXC or any server).
#   curl -fsSL https://raw.githubusercontent.com/Hikki-dev/media-server-setup/main/install.sh | bash
# It checks Docker, downloads this project into ~/media-server-setup, and starts the setup page.
# Nothing outside that folder is changed, and no media is touched.
set -u
REPO="Hikki-dev/media-server-setup"; BRANCH="${ARR_BRANCH:-main}"; DEST="${ARR_DIR:-$HOME/media-server-setup}"
if [ -t 1 ]; then B=$'\033[1m'; D=$'\033[2m'; C=$'\033[36m'; G=$'\033[32m'; R=$'\033[31m'; N=$'\033[0m'; else B=; D=; C=; G=; R=; N=; fi
say() { printf '  %s\n' "$*"; }
die() { printf '\n  %s%s%s\n\n' "$R" "$*" "$N" >&2; exit 1; }

printf '\n  %sMedia Server Setup%s  %s(one-line installer)%s\n\n' "$B$C" "$N" "$D" "$N"
case "$(uname -s)" in Darwin) OS=mac ;; Linux) OS=linux ;; *) die "This installer is for Linux and Mac. On Windows, download the project and double click 'Start on Windows.bat'." ;; esac

command -v docker >/dev/null 2>&1 || die "Docker is not installed yet.
  Mac:   install Docker Desktop from https://www.docker.com/products/docker-desktop/
  Linux: install Docker Engine from https://docs.docker.com/engine/install/
  Then run this command again."
command -v curl >/dev/null 2>&1 || die "curl is missing. Install it first (for example: sudo apt install curl)."
command -v tar >/dev/null 2>&1 || die "tar is missing. Install it first."

say "Downloading the setup into $DEST"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" -o "$TMP/p.tar.gz" || die "Could not download the project. Check your internet connection."
mkdir -p "$DEST" && tar -xzf "$TMP/p.tar.gz" -C "$DEST" --strip-components=1 || die "Could not unpack the project into $DEST."
say "${G}Done.${N} Starting it now."
# bash reads this script from the pipe, so give the launcher the real keyboard when there is one
if [ -r /dev/tty ]; then exec bash "$DEST/tools/start.sh" "$OS" "$@" </dev/tty; else exec bash "$DEST/tools/start.sh" "$OS" "$@"; fi
