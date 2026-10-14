#!/usr/bin/env python3
"""
Run every JEFFEREY test, isolated from the real home folder.

    python tests/run_all.py          # everything except the slow photo-index suite
    python tests/run_all.py --all    # everything

Each suite runs in its own process with a throwaway HOME and explicit data
paths, so no test can touch the owner's conscience, drive, voice or photos.
After each suite the throwaway HOME must still be empty: a test that writes
into a home folder is a failing test, because on the owner's Mac that home
folder is real.

Exit status is non-zero if anything failed. Regression tests for the
October 2026 stress-test fixes live beside this file as tests/test_*.py
(standard-library unittest) and are discovered automatically.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

SUITES = [
    ("connector", ["connector/jefferey_chat.py", "--selftest"]),
    ("egress door", ["connector/egress.py", "selftest"]),
    ("album", ["connector/reminisce.py", "--selftest"]),
    ("drive", ["tools/provision_drive.py", "--selftest"]),
    ("recall", ["tools/recall.py", "--selftest"]),
    ("voice", ["tools/voice_enrol.py", "--selftest"]),
    ("wall", ["tools/wall.py", "--selftest"]),
    ("discs", ["tools/disc_archive.py", "selftest"]),
]
SLOW = [("photo index", ["tools/photo_index.py", "selftest"])]


def isolated_env(tmp: Path) -> tuple[dict, Path]:
    home = tmp / "home"
    home.mkdir()
    env = dict(os.environ)
    for k in ("SELFCLOUD_ROOT", "JEFFEREY_OWNER_CONSOLE", "JEFFEREY_CLIENT",
              "JEFFEREY_OFFLINE", "JEFFEREY_HTTP_TOKEN", "JEFFEREY_HTTP_TOKENS"):
        env.pop(k, None)
    env.update(
        HOME=str(home),
        JEFFEREY_CONSCIENCE_PATH=str(tmp / "conscience.json"),
        JEFFEREY_EGRESS=str(tmp / "egress.jsonl"),
        JEFFEREY_DOOR=str(tmp / "door-shut"),
        SELFCLOUD_INDEX=str(tmp / "photo-index"),
        SELFCLOUD_VOICE=str(tmp / "voice"),
        SELFCLOUD_DISCS=str(tmp / "discs"),
        JEFFEREY_FORMS_OUTBOX=str(tmp / "Filled forms"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    return env, home


def run(name: str, cmd: list[str], timeout: int = 900) -> tuple[bool, str, float]:
    tmp = Path(tempfile.mkdtemp(prefix="jf-test-"))
    try:
        env, home = isolated_env(tmp)
        t0 = time.time()
        try:
            p = subprocess.run([PY] + cmd, cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=timeout)
            ok, out = p.returncode == 0, (p.stdout + p.stderr)
        except subprocess.TimeoutExpired:
            ok, out = False, f"timed out after {timeout}s"
        left = sorted(str(x.relative_to(home)) for x in home.rglob("*"))
        if left:
            ok = False
            out += "\nWROTE INTO THE HOME FOLDER: " + ", ".join(left[:10])
        return ok, out, time.time() - t0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str]) -> int:
    suites = SUITES + (SLOW if "--all" in argv else [])
    unit = sorted((ROOT / "tests").glob("test_*.py"))
    if unit:
        suites.append(("regression tests",
                       ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]))
    failed = []
    for name, cmd in suites:
        ok, out, secs = run(name, cmd)
        print(f"  {'✓' if ok else '✗'} {name:18s} {secs:6.1f}s")
        if not ok:
            failed.append(name)
            tail = "\n".join(out.strip().splitlines()[-40:])
            print("      " + tail.replace("\n", "\n      "))
    if "--all" not in argv:
        print("  · photo index suite skipped (slow) — run with --all")
    print(f"\n{'ALL PASSED' if not failed else 'FAILED: ' + ', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
