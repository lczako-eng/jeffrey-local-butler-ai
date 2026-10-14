#!/bin/bash
# Double-click this to see exactly what JEFFEREY has sent to a rented engine
# (Claude, ChatGPT): to whom, when, which tool, and — if you ask — every word.
#
# Nothing here goes anywhere. It reads a log that lives beside your
# conscience, on your Self-Cloud drive if one is plugged in.
cd "$(dirname "$0")" || exit 1

VENV="$HOME/.jefferey/venv"
if [ -x "$VENV/bin/python" ]; then
    PY="$VENV/bin/python"
else
    PY=""
    for c in python3.13 python3.12 python3.11 python3.10 python3; do
        command -v "$c" >/dev/null 2>&1 && PY="$c" && break
    done
    if [ -z "$PY" ]; then
        echo "  This Mac needs Python: https://www.python.org/downloads/"
        echo "Press return to close."; read -r _; exit 1
    fi
fi

# The report, the door's state, and the menu, in plain words. Words work in
# English or French ("shut", "fermer", "open", "ouvrir"); anything not
# understood is asked again, and the door's state is printed after every
# answer. (Typing "shut" used to open the log and leave the door open.)
echo
"$PY" connector/egress.py menu

echo
echo "Press return to close this window."
read -r _ || true
