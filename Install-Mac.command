#!/bin/sh
# Shark Support installer launcher (Mac) - WORK IN PROGRESS
# Copyright Matthew Armstrong. PolyForm Noncommercial 1.0.0. No warranty.
# First run: right-click > Open (the file is not signed).
cd "$(dirname "$0")" || exit 1
PY=""
for c in python3 /usr/local/bin/python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  osascript -e 'display dialog "Shark Support needs Python 3. Install it from python.org (it includes the window toolkit), then double-click this file again." buttons {"OK"}' >/dev/null 2>&1
  echo "Python 3 not found. Install it from https://www.python.org/downloads/"
  exit 1
fi
if ! "$PY" -c 'import tkinter' 2>/dev/null; then
  echo "This Python has no tkinter. The python.org installer includes it. Running the text installer instead..."
  "$PY" install.py --cli
  printf "Press Enter to close. "; read -r _
  exit 0
fi
exec "$PY" install.py "$@"
