#!/usr/bin/env bash
# On Linux, open a terminal here and run: bash "Start on Linux.sh"
cd "$(dirname "$0")" || exit 1
exec bash ./tools/start.sh linux
