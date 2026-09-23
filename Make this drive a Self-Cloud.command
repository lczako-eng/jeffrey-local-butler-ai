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

# The drives someone could mean: everything in /Volumes except the Mac's own
# disk. If there is exactly one, pressing return picks it — a first run on
# the owner's Mac ended with "No drive given." because nobody told him that
# dragging was the only way to answer.
DRIVES=()
for v in /Volumes/*; do
    [ -d "$v" ] || continue
    [ "$v" = "/Volumes/Macintosh HD" ] && continue
    [ "$(stat -f %d "$v" 2>/dev/null)" = "$(stat -f %d / 2>/dev/null)" ] && continue
    DRIVES+=("$v")
done

echo
if [ ${#DRIVES[@]} -eq 0 ]; then
    echo "  No external drive is plugged in. Plug it in and double-click this again."
    read -r _; exit 1
fi
echo "  Which drive?"
i=1
for v in "${DRIVES[@]}"; do echo "     $i) $v"; i=$((i+1)); done
echo
if [ ${#DRIVES[@]} -eq 1 ]; then
    echo "  Press return for ${DRIVES[0]} — or type a number, a name, or drag one in."
else
    echo "  Type a number, a name, or drag a drive in from Finder, then press return."
fi
# Ask until there is an answer. Giving up after one empty line closed the
# window on the owner while he was still typing the path.
while true; do
    read -r -p "  drive: " VOL
    VOL="${VOL%"${VOL##*[! ]}"}"          # trim trailing space Finder adds
    VOL="${VOL//\\ / }"                     # un-escape spaces
    if [ -z "$VOL" ] && [ ${#DRIVES[@]} -eq 1 ]; then
        VOL="${DRIVES[0]}"
    elif [[ "$VOL" =~ ^[0-9]+$ ]] && [ "$VOL" -ge 1 ] && [ "$VOL" -le ${#DRIVES[@]} ]; then
        VOL="${DRIVES[$((VOL-1))]}"
    elif [ -n "$VOL" ] && [ "${VOL:0:1}" != "/" ]; then
        VOL="/Volumes/$VOL"                  # "Self-Cloud" means /Volumes/Self-Cloud
    fi
    if [ -z "$VOL" ]; then
        echo "  Type a number from the list, then press return."
    elif [ ! -d "$VOL" ]; then
        echo "  Nothing at $VOL — try again."
    else
        break
    fi
done
echo "  Using $VOL"

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
