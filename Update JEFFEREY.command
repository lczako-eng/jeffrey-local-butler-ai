#!/bin/bash
# Double-click this to update JEFFEREY, with the Mac online.
#
# It brings this copy, and the copy on your Self-Cloud drive if it is plugged
# in, to the same newest release; installs exactly the versions it was tested
# with; checks it works; and tells you the version. It never touches your
# memories, and it changes nothing if a copy has changes made by hand.
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3.13 python3.12 python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
    echo
    echo "  This Mac has no Python installed. Download it from"
    echo "  https://www.python.org/downloads/ (the big yellow button), then"
    echo "  double-click this again."
    echo
    echo "Press return to close."; read -r _; exit 1
fi

"$PY" tools/update.py "$@"
STATUS=$?

echo
echo "Press return to close this window."
read -r _ || true
exit $STATUS
