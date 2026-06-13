#!/usr/bin/env bash
# CT Cannabis Political Check — macOS / Linux launcher
set -e
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
python3 CTCannabisPoliticalCheck.py "$@"
