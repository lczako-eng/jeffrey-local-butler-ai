#!/bin/bash
# Double-click this to see the payments an AI asked to add to your list of
# agreed payments, and say yes or no to each one.
#
# JEFFEREY stays quiet about a charge only when it is on that list, so an AI
# can never add to it by itself: it asks, and it waits for you. Type yes to
# add one, no to leave it out. Then your whole list is shown. Nothing here
# goes anywhere, and no AI can do this — only you, here.
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

echo
"$PY" connector/guardian.py review
echo
echo "  Your list of agreed payments:"
"$PY" connector/guardian.py list

echo
echo "Press return to close this window."
read -r _
