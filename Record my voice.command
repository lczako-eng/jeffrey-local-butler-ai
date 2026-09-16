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

echo
read -r -p "  Whose voice is this? Your name: " WHO
[ -z "$WHO" ] && WHO="$(id -un)"

"$PY" tools/voice_enrol.py --who "$WHO" start "$@"
STATUS=$?

echo
echo "Press return to close this window."
read -r _
exit $STATUS
