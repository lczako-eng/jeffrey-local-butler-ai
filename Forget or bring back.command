#!/bin/bash
# Double-click this to see what JEFFEREY has forgotten, and change it:
#
#   - things an AI asked to remove that need your own OK first (it will have
#     told you a code — type "ok" and the number, or the code);
#   - things removed in the last three months, which you can put back;
#   - erase words everywhere, for good: from your memories, from the copies,
#     and from the record of what was sent. That one cannot be undone.
#
# Nothing here goes anywhere, and no AI can do any of this — only you, here.
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

"$PY" connector/forgetting.py

echo
echo "Press return to close this window."
read -r _
