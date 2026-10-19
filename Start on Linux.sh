#!/usr/bin/env bash
# On Linux, open a terminal here and run: bash "Start on Linux.sh"
# On a server with no screen (an LXC, a VPS) it prints the address to open from another computer.
# Add --headless to force that.
cd "$(dirname "$0")" || exit 1
exec bash ./tools/start.sh linux "$@"
