#!/usr/bin/env python3
"""
go.py — put your life on the screen. One step.
==============================================

Behind `Show me my life.command`. It does everything needed and explains
itself as it goes:

  1. makes sure the pieces are installed (once — the first time is slow)
  2. asks which folder your photographs are in, and remembers
  3. reads them — dates, places, and what they look like
  4. opens the wall, on this machine and on your phone and TV

Safe to run again any time. The reading is resumable: it picks up where it
stopped and skips everything it has already seen, so a second run on 80,000
photographs takes seconds, not hours.

Nothing here talks to the internet except the one-time install, and after
that it never needs to again.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "connector"))
import home  # noqa: E402

HOME = Path.home() / ".jefferey"
CONF = HOME / "wall.conf"
INDEX = home.index_path()            # on the drive, if one is plugged in
FIRST_RUN_LIMIT = 3000          # see it working in minutes, not hours

# What the seeing part needs. The connector's own requirements are separate
# and much lighter; these are only for reading photographs.
NEEDS = [
    ("PIL", "pillow"),
    ("numpy", "numpy"),
    ("open_clip", "open_clip_torch"),
    ("torch", "torch"),
    ("reverse_geocoder", "reverse_geocoder"),
    ("pycountry", "pycountry"),
]
NICE = [("pillow_heif", "pillow-heif")]     # iPhone photos are HEIC

G, R, Y, D, B, O = ("\033[32m", "\033[31m", "\033[33m", "\033[2m",
                    "\033[1m", "\033[0m")


def say(m: str = "") -> None:
    print(m, flush=True)


def ok(m): say(f"  {G}✓{O} {m}")
def warn(m): say(f"  {Y}!{O} {m}")
def bad(m): say(f"  {R}✗{O} {m}")
def head(m): say(f"\n{B}{m}{O}")


def missing(pairs) -> list[str]:
    out = []
    for module, package in pairs:
        try:
            __import__(module)
        except ImportError:
            out.append(package)
    return out


def install(packages: list[str]) -> bool:
    say(f"  {D}Installing: {', '.join(packages)}{O}")
    say(f"  {D}The first time this can take 10–20 minutes and about 2 GB —"
        f" it is\n   downloading the part that understands pictures. "
        f"Only ever once.{O}\n")
    r = subprocess.run([sys.executable, "-m", "pip", "install", *packages])
    return r.returncode == 0


def ask_folder() -> Path:
    remembered = {}
    if CONF.exists():
        try:
            remembered = json.loads(CONF.read_text())
        except Exception:
            remembered = {}
    if remembered.get("photos") and Path(remembered["photos"]).exists():
        return Path(remembered["photos"])

    default = Path.home() / "Pictures"
    say(f"\n  Where are your photographs?")
    say(f"  {D}Press return for {default}, or drag the folder into this window"
        f"\n   and press return.{O}\n")
    try:
        typed = input("  folder: ").strip().strip("'\"")
    except (EOFError, KeyboardInterrupt):
        typed = ""
    folder = Path(typed).expanduser() if typed else default
    if not folder.exists():
        bad(f"There's nothing at {folder}.")
        sys.exit(1)
    CONF.parent.mkdir(parents=True, exist_ok=True)
    CONF.write_text(json.dumps({"photos": str(folder)}, indent=2))
    ok(f"Remembered. Change it later by deleting {CONF}")
    return folder


def count_indexed() -> int:
    try:
        from photo_index import PhotoIndex
        return next(PhotoIndex(INDEX).db.execute(
            "SELECT COUNT(*) FROM vectors"))[0]
    except Exception:
        return 0


def main() -> int:
    say(f"\n{B}Your life, on the screen{O}")
    say(f"{D}Everything below happens on this machine. Nothing is uploaded.{O}")
    say(f"  {D}Life lives {home.describe()}.{O}")

    head("[1/4] Checking the pieces")
    need = missing(NEEDS)
    if need:
        warn(f"{len(need)} piece(s) not installed yet.")
        if not install(need):
            bad("That install failed. Scroll up for the reason, or tell Claude.")
            return 1
        still = missing(NEEDS)
        if still:
            bad(f"Still missing: {', '.join(still)}")
            return 1
    ok("Everything needed is here")
    if nice := missing(NICE):
        install(nice)               # HEIC support; not fatal if it fails

    head("[2/4] Your photographs")
    folder = ask_folder()
    ok(f"Reading from {folder}")

    head("[3/4] Reading them")
    already = count_indexed()
    if already:
        ok(f"{already:,} already read — skipping those, looking for new ones")
    else:
        say(f"  {D}First time. Doing {FIRST_RUN_LIMIT:,} to start, so you see it"
            f" working\n   in minutes. Run this again to carry on through the "
            f"rest.{O}")
    t0 = time.time()
    cmd = [sys.executable, str(Path(__file__).parent / "photo_index.py"),
           "--index", str(INDEX), "build", str(folder)]
    if not already:
        cmd += ["--limit", str(FIRST_RUN_LIMIT)]
    if subprocess.run(cmd).returncode != 0:
        bad("Reading the photographs failed. Scroll up for why.")
        return 1
    now = count_indexed()
    ok(f"{now:,} photographs readable — {now - already:,} new, "
       f"in {time.time() - t0:.0f}s")

    head("[4/4] Opening the wall")
    import wall
    srv = wall.serve(str(INDEX), 8378, lan=True)
    code = wall.STATE["passcode"]
    local = f"http://127.0.0.1:8378/?k={code}"
    lan = f"http://{wall.lan_ip()}:8378/?k={code}"
    say(f"\n  {B}On this Mac{O}        {local}")
    say(f"  {B}Phone / TV / iPad{O}  {lan}")
    say(f"\n  {D}Passcode {code} — being on the wifi is not the same as being"
        f" allowed.\n   It's new every time you start this.{O}")
    say(f"\n  {B}Try typing:{O}  vacation ten years ago in Cuba")
    say(f"  {D}Escape clears the screen. Ctrl-C here stops everything.{O}\n")
    try:
        webbrowser.open(local)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        say(f"\n  Stopped. Nothing is left running.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
