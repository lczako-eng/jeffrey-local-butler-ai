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

echo
"$PY" connector/egress.py report --days 7
echo
echo "  [return]  see every send, word for word"
echo "  [a]       everything since the beginning"
echo "  [s]       SHUT the door — nothing leaves until you open it"
echo "  [o]       open the door"
echo "  [q]       close this window"
echo
read -r -p "  > " CHOICE
case "$CHOICE" in
    a|A) "$PY" connector/egress.py report --all --full | less -R ;;
    s|S) "$PY" connector/egress.py shut ;;
    o|O) "$PY" connector/egress.py open ;;
    q|Q) exit 0 ;;
    *)   "$PY" connector/egress.py report --days 7 --full | less -R ;;
esac

echo
echo "Press return to close this window."
read -r _
