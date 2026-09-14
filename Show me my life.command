#!/bin/bash
# Double-click this.
#
# It puts your photographs on the screen — this Mac, your phone, your TV.
# Everything happens on this machine. Nothing is uploaded anywhere.
#
# Safe to run as many times as you like. It picks up where it left off.
cd "$(dirname "$0")" || exit 1

VENV="$HOME/.jefferey/venv"

# Use Jefferey's own space if the installer already made one; otherwise find
# any Python new enough and make one, so this works on its own.
if [ -x "$VENV/bin/python" ]; then
    PY="$VENV/bin/python"
else
    BASE=""
    for c in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$c" >/dev/null 2>&1; then
            if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
                BASE="$c"; break
            fi
        fi
    done
    if [ -z "$BASE" ]; then
        echo
        echo "  This Mac needs a newer Python."
        echo
        echo "  Get it from  https://www.python.org/downloads/  (the big yellow"
        echo "  button), install it, then double-click this again."
        echo
        echo "Press return to close."
        read -r _
        exit 1
    fi
    echo "  Making a private space for this…"
    "$BASE" -m venv "$VENV" || exit 1
    PY="$VENV/bin/python"
    "$PY" -m pip install --quiet --upgrade pip
fi

"$PY" tools/go.py "$@"
STATUS=$?

echo
echo "Press return to close this window."
read -r _
exit $STATUS
