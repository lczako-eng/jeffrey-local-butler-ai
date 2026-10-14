#!/bin/bash
# Double-click this to put back an earlier copy of what JEFFEREY remembers —
# after a mistake, after a power cut, or if JEFFEREY says your memory file
# cannot be read.
#
# JEFFEREY keeps copies beside your memory file (on your Self-Cloud drive if
# one is plugged in): every copy from the last day, one an hour for a week,
# one a day for three months, and one kept from just before anything was
# deleted. Putting one back keeps what is there now as a copy too, so this
# can always be undone. Nothing here goes anywhere, and no AI can do this —
# only you, here.
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
"$PY" connector/conscience.py check
echo
"$PY" connector/conscience.py history
echo
echo "  Type the number of the copy to put back and press return."
echo "  Just press return to change nothing."
echo
read -r -p "  > " CHOICE
CHOICE="$(echo "$CHOICE" | tr -d '[:space:].')"
if [ -n "$CHOICE" ]; then
    "$PY" connector/conscience.py restore "$CHOICE"
else
    echo "  Nothing was changed."
fi

echo
echo "Press return to close this window."
read -r _
