#!/bin/bash
# Double-click this to record your own voice, into your own machine.
#
# It records; it does not clone or play anything as you. That is a separate
# decision for later. Nothing here leaves this Mac.
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

# The one piece that needs installing, once: the microphone library.
if ! "$PY" -c "import sounddevice, numpy" >/dev/null 2>&1; then
    echo "  Installing the microphone library (once)…"
    "$PY" -m pip install --quiet sounddevice numpy
fi

# A name is required, typed by the person who will speak. It is never taken
# from this Mac's account: on a shared account that would put someone else's
# voice in the owner's recordings.
echo
WHO=""
for _ in 1 2 3; do
    read -r -p "  Whose voice is this? Type your own name: " WHO
    WHO="$(printf '%s' "$WHO" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [ -n "$WHO" ] && break
    echo "  Please type your name: the name of the person who will be speaking."
done
if [ -z "$WHO" ]; then
    echo
    echo "  No name was typed, so nothing was recorded."
    echo
    echo "Press return to close this window."
    read -r _
    exit 1
fi

"$PY" tools/voice_enrol.py --who "$WHO" start "$@"
STATUS=$?

echo
echo "Press return to close this window."
read -r _
exit $STATUS
