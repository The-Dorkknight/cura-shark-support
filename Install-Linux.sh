#!/bin/sh
# Shark Support installer launcher (Linux) - WORK IN PROGRESS
# Copyright Matthew Armstrong. PolyForm Noncommercial 1.0.0. No warranty.
cd "$(dirname "$0")" || exit 1
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  MSG="Shark Support needs Python 3.8 or newer. On Linux Mint / Ubuntu: sudo apt install python3 python3-tk"
  if command -v zenity >/dev/null 2>&1; then zenity --error --text="$MSG"; else echo "$MSG"; printf "Press Enter to close. "; read -r _; fi
  exit 1
fi
if ! "$PY" -c 'import tkinter' 2>/dev/null; then
  echo "The installer window needs tkinter: sudo apt install python3-tk"
  echo "Running the text installer instead..."
  "$PY" install.py --cli
  printf "Press Enter to close. "; read -r _
  exit 0
fi
exec "$PY" install.py "$@"
