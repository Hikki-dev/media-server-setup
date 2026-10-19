#!/usr/bin/env bash
# Double click this file on a Mac. It opens the setup in your browser.
cd "$(dirname "$0")" || exit 1
exec bash ./tools/start.sh mac "$@"
