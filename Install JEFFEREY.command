#!/bin/bash
# Double-click this file on a Mac.
#
# Finder runs it in a Terminal window, so you see what happens and nothing is
# hidden from you. It only calls tools/install.py, which does the actual work.
cd "$(dirname "$0")" || exit 1

PY=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done

if [ -z "$PY" ]; then
    echo
    echo "  This Mac has no Python installed."
    echo
    echo "  Download it from  https://www.python.org/downloads/  (the big"
    echo "  yellow button), install it, then double-click this file again."
    echo
    echo "Press return to close."
    read -r _
    exit 1
fi

"$PY" tools/install.py "$@"
STATUS=$?

echo
echo "Press return to close this window."
read -r _
exit $STATUS
