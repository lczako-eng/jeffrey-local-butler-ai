"""
home.py — where the life lives: on the drive, if there is one.
==============================================================

"Plug it in anywhere" is only true if the DATA is on the drive. So every
tool asks this module where things go, and the answer depends on whether a
Self-Cloud drive is present:

    a drive is present   →  <drive>/.selfcloud/jefferey/…      (the product)
    no drive             →  ~/.jefferey  and  ~/.selfcloud    (laptop-only, as before)

A drive is "present" when SELFCLOUD_ROOT points at it, or exactly one mounted
volume carries the marker `.selfcloud/selfcloud.json` written by
tools/provision_drive.py. Two marked drives at once is ambiguous and is
refused rather than guessed — pick one with SELFCLOUD_ROOT.

Why `.selfcloud/jefferey/` and not `.selfcloud/` itself: the Self-Cloud
connector owns the top of that folder (node.json, catalog.db, audit.jsonl,
index.lock — see Self-Cloud-Workspace/HANDOVER.md). Namespacing under
`jefferey/` means the two halves cannot collide on a shared drive, and
either can be removed without touching the other.

Explicit environment variables always win:
    JEFFEREY_CONSCIENCE_PATH   the conscience file
    SELFCLOUD_INDEX            the photo index directory
    SELFCLOUD_VOICE            voice recordings
    SELFCLOUD_DISCS            archived discs
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

MARKER = Path(".selfcloud") / "selfcloud.json"
NAMESPACE = Path(".selfcloud") / "jefferey"

_ROOT: Path | None | bool = False        # False = not yet looked
_ANNOUNCED = False


def _mounts() -> list[Path]:
    """Where removable drives appear, per platform."""
    cands: list[Path] = []
    for base in ("/Volumes", "/media", "/mnt", "/run/media"):
        b = Path(base)
        if b.is_dir():
            try:
                cands += [p for p in b.iterdir() if p.is_dir()]
            except OSError:
                pass
            # /media/<user>/<drive> and /run/media/<user>/<drive>
            for sub in list(cands):
                try:
                    cands += [p for p in sub.iterdir() if p.is_dir()]
                except OSError:
                    pass
    return cands


def root() -> Path | None:
    """The Self-Cloud drive, or None. Decided once per process."""
    global _ROOT
    if _ROOT is not False:
        return _ROOT
    env = os.environ.get("SELFCLOUD_ROOT")
    if env:
        p = Path(env).expanduser()
        _ROOT = p if p.exists() else None
        if _ROOT is None:
            print(f"  ⚠  SELFCLOUD_ROOT={env} is not mounted. Using this machine's "
                  f"home folder instead.", file=sys.stderr)
        return _ROOT
    marked = [m for m in _mounts() if (m / MARKER).is_file()]
    if len(marked) > 1:
        print("  ⚠  More than one Self-Cloud drive is plugged in:\n" +
              "".join(f"       {m}\n" for m in marked) +
              "     Say which with SELFCLOUD_ROOT=/Volumes/…  Using neither.",
              file=sys.stderr)
        _ROOT = None
    else:
        _ROOT = marked[0] if marked else None
    return _ROOT


def marker() -> dict:
    r = root()
    if not r:
        return {}
    try:
        return json.loads((r / MARKER).read_text())
    except Exception:
        return {}


def data() -> Path | None:
    """JEFFEREY's namespace on the drive, or None if there is no drive."""
    r = root()
    return (r / NAMESPACE) if r else None


def _pick(env: str, on_drive: str, at_home: str) -> Path:
    if os.environ.get(env):
        return Path(os.environ[env]).expanduser()
    d = data()
    return (d / on_drive) if d else Path(at_home).expanduser()


def conscience_path() -> Path:
    return _pick("JEFFEREY_CONSCIENCE_PATH", "conscience.json", "~/.jefferey/conscience.json")


def index_path() -> Path:
    return _pick("SELFCLOUD_INDEX", "photo-index", "~/.selfcloud/photo-index")


def voice_path() -> Path:
    return _pick("SELFCLOUD_VOICE", "voice", "~/.selfcloud/voice")


def discs_path() -> Path:
    return _pick("SELFCLOUD_DISCS", "discs", "~/.selfcloud/discs")


def describe() -> str:
    r = root()
    if r:
        m = marker()
        name = m.get("name") or r.name
        return f"on the Self-Cloud drive '{name}' ({r})"
    return "on this machine (no Self-Cloud drive plugged in)"


def announce() -> None:
    """Say once, to stderr, where the life is being kept. Never silent about it."""
    global _ANNOUNCED
    if _ANNOUNCED:
        return
    _ANNOUNCED = True
    print(f"  Life lives {describe()}.", file=sys.stderr)


def reset_for_tests() -> None:
    global _ROOT, _ANNOUNCED
    _ROOT, _ANNOUNCED = False, False
