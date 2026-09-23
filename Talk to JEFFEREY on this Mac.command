#!/bin/bash
# Double-click this to talk to JEFFEREY using an AI that runs ON THIS MAC.
#
# Same memory as in the Claude app — same conscience, same drive — but the
# thinking happens here, on your own machine. Nothing you say to him, and
# nothing he reads about you, leaves the house.
#
# The first time, it downloads the AI (Hermes, about 5 GB). After that it
# works with the internet off.
cd "$(dirname "$0")" || exit 1
MODEL="${JEFFEREY_LOCAL_MODEL:-hermes3}"

pause() { echo; echo "Press return to close this window."; read -r _; }

VENV="$HOME/.jefferey/venv"
if [ -x "$VENV/bin/python" ]; then
    PY="$VENV/bin/python"
else
    echo "  JEFFEREY isn't installed yet. Double-click 'Install JEFFEREY.command' first."
    pause; exit 1
fi

# 1. The engine: Ollama runs local AIs. Install it once, from its own site.
if ! command -v ollama >/dev/null 2>&1 && [ ! -d "/Applications/Ollama.app" ]; then
    echo
    echo "  One thing to install first: Ollama, the program that runs AI on your Mac."
    echo "    1. Go to  https://ollama.com/download  and download it for Mac."
    echo "    2. Open the download and drag Ollama into Applications."
    echo "    3. Open Ollama once, then double-click this again."
    open "https://ollama.com/download" 2>/dev/null
    pause; exit 1
fi
command -v ollama >/dev/null 2>&1 || export PATH="/Applications/Ollama.app/Contents/Resources:$PATH"

# 2. Make sure it is running (it listens only on this Mac).
if ! curl -s --noproxy '*' -m 2 http://127.0.0.1:11434/api/tags >/dev/null; then
    echo "  Starting the local AI…"
    open -a Ollama 2>/dev/null || (ollama serve >/dev/null 2>&1 &)
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
        curl -s --noproxy '*' -m 2 http://127.0.0.1:11434/api/tags >/dev/null && break
        sleep 1
    done
fi

# 3. Make sure the model is here. The one download, then never again.
if ! ollama list 2>/dev/null | awk '{print $1}' | grep -q "^${MODEL}\(:\|$\)"; then
    echo
    echo "  Downloading ${MODEL} — once, about 5 GB. After this it works offline."
    ollama pull "$MODEL" || { echo "  The download didn't finish. Double-click this again to resume."; pause; exit 1; }
fi

# 4. Talk. Same conscience, same drive, same two doors.
echo
JEFFEREY_LOCAL_MODEL="$MODEL" "$PY" connector/jefferey_chat.py --engine local
pause
