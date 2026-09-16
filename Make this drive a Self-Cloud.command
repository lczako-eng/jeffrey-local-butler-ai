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

echo
echo "  Which drive? Drag it from Finder into this window, then press return."
echo "  (Plugged-in drives right now:)"
ls -1 /Volumes 2>/dev/null | sed 's/^/     \/Volumes\//'
echo
read -r -p "  drive: " VOL
VOL="${VOL%"${VOL##*[! ]}"}"          # trim trailing space Finder adds
VOL="${VOL//\\ / }"                     # un-escape spaces
[ -z "$VOL" ] && { echo "  No drive given."; read -r _; exit 1; }
[ -d "$VOL" ] || { echo "  Nothing at $VOL"; read -r _; exit 1; }

echo
read -r -p "  Name it 'Self-Cloud' in Finder too? [Y/n] " REN
if [ "$REN" = "n" ] || [ "$REN" = "N" ]; then
    "$PY" tools/provision_drive.py "$VOL"
else
    "$PY" tools/provision_drive.py "$VOL" --rename
fi
STATUS=$?

echo
echo "  If the icon hasn't changed yet: eject the drive and plug it back in."
echo "  Then open the Self-Cloud folder on it and double-click Start Self-Cloud."
echo
echo "Press return to close this window."
read -r _
exit $STATUS
