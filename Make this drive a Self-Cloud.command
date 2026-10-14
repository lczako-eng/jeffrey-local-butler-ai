#!/bin/bash
# Double-click this. Then drag your drive into the window and press return.
#
# It turns that drive into a Self-Cloud drive: the folders, the cloud icon,
# and a "Start Self-Cloud" button on it that works on any Mac. It creates
# only — it never moves, renames or deletes a single file already there.
cd "$(dirname "$0")" || exit 1

PY=""
for c in "$HOME/.jefferey/venv/bin/python" python3.13 python3.12 python3.11 python3.10 python3; do
    if [ -x "$c" ] || command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -z "$PY" ] && { echo "  Install Python: https://www.python.org/downloads/"; read -r _; exit 1; }
"$PY" -c "import PIL" 2>/dev/null || "$PY" -m pip install --quiet pillow

# Everything after this is asked in plain words by provision_drive.py: which
# drive (never the Mac's own disk, a read-only drive or a software
# installer), whether to rename it (only if you type yes), and whether to
# move memories already on this Mac onto it (only if you type yes). A closed
# window chooses nothing and changes nothing.
"$PY" tools/provision_drive.py --interactive
STATUS=$?

echo
echo "Press return to close this window."
read -r _ || true
exit $STATUS
