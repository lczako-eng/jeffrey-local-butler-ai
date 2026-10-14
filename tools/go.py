#!/usr/bin/env python3
"""
go.py — put your life on the screen. One step.
==============================================

Behind `Show me my life.command`. It does everything needed and explains
itself as it goes:

  1. makes sure the pieces are installed (once — the first time is slow)
  2. asks which folder your photographs are in, and remembers
  3. reads them — dates, places, and what they look like — and notices the
     ones that have been deleted, so they are not shown
  4. opens the wall on this machine; the phone and the TV only if you say so

Safe to run again any time. The reading is resumable: it picks up where it
stopped and skips everything it has already seen, so a second run on 80,000
photographs takes seconds, not hours.

Nothing here talks to the internet except the one-time install, and after
that it never needs to again.

    Show me my life.command           this Mac only (it asks about the TV)
    Show me my life.command --lan     the phone and the TV too, without asking
"""

from __future__ import annotations

import json
import os
import shlex
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
ASK_LIMIT = 5                   # wrong folders in a row before it stops asking

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


def unescape(typed: str) -> str:
    """What the owner typed or dragged in, as a plain path.

    Dragging a folder from Finder into Terminal types it with backslashes
    before spaces, brackets and apostrophes — "Family\\ Photos" — and a
    space after it. Some apps put quotes around it instead. Undo both."""
    t = typed.strip()
    if not t:
        return ""
    if "\\" in t or t[0] in "'\"":
        try:
            parts = shlex.split(t)
        except ValueError:                  # an unbalanced quote: keep it simple
            parts = [t.strip("'\"")]
        if len(parts) == 1:
            return parts[0]
        return " ".join(parts)
    return t


def photos_libraries(folder: Path) -> list[Path]:
    """Apple Photos libraries in or at this folder. They hold every picture
    several times over and are read only by exporting the originals."""
    from photo_index import walk
    found: list = []
    for _ in walk(folder, found):
        pass
    return [p for p in found if p.name.lower().endswith((".photoslibrary",
                                                         ".photolibrary"))]


def explain_photos_library(libs: list[Path]) -> None:
    warn("This folder holds an Apple Photos library:")
    for lib in libs[:3]:
        say(f"     {lib.name}")
    say(f"  {D}A Photos library keeps every picture several times over (small"
        f"\n   copies, previews, faces), so it is skipped. To include those"
        f"\n   photographs: open Photos, select them, choose File → Export →"
        f"\n   Export Unmodified Originals, save them into a folder, and choose"
        f"\n   that folder here.{O}")


def _drive_name() -> str | None:
    r = home.root()
    if not r:
        return None
    return home.marker().get("name") or r.name


def _remembered() -> dict:
    if not CONF.exists():
        return {}
    try:
        conf = json.loads(CONF.read_text())
        return conf if isinstance(conf, dict) else {}
    except Exception:
        return {}


def _remembered_folder(conf: dict) -> Path | None:
    """The remembered folder, followed onto the drive if the drive was
    renamed since ('Self Cloud' → 'Self-Cloud')."""
    r = home.root()
    if conf.get("photos_on_drive") is not None and r:
        p = r / conf["photos_on_drive"]
        if p.is_dir():
            return p
    if conf.get("photos") and Path(conf["photos"]).is_dir():
        return Path(conf["photos"])
    return None


def ask_folder() -> Path:
    conf = _remembered()
    folder = _remembered_folder(conf)
    if folder:
        return folder

    default = Path.home() / "Pictures"
    say(f"\n  Where are your photographs?")
    say(f"  {D}Drag the folder into this window and press return — or just press"
        f"\n   return for {default}.{O}\n")
    for attempt in range(ASK_LIMIT):
        try:
            typed = input("  folder: ")
        except (EOFError, KeyboardInterrupt):
            say("")
            bad("No folder chosen. Nothing was read. Double-click again when ready.")
            sys.exit(1)
        plain = unescape(typed)
        folder = Path(plain).expanduser() if plain else default
        if folder.name.lower().endswith((".photoslibrary", ".photolibrary")):
            explain_photos_library([folder])
            say(f"\n  {D}Drag a folder of exported photographs in, then press return.{O}\n")
            continue
        if not folder.is_dir():
            bad(f"I can't find a folder at {folder}.")
            say(f"  {D}Try again: drag the folder itself into this window, then"
                f" press return.{O}\n")
            continue
        libs = photos_libraries(folder)
        if libs:
            explain_photos_library(libs)
        break
    else:
        bad("That still isn't a folder I can find. Nothing was read.")
        say(f"  {D}Double-click 'Show me my life' again when you're ready.{O}")
        sys.exit(1)
    r = home.root()
    saved = {"photos": str(folder)}
    if r:
        try:                                 # remembered relative to the drive,
            saved["photos_on_drive"] = folder.resolve().relative_to(r.resolve()).as_posix()
        except ValueError:                   # so a renamed drive still finds it
            pass
        saved["drive"] = _drive_name()
    CONF.parent.mkdir(parents=True, exist_ok=True)
    CONF.write_text(json.dumps(saved, indent=2))
    ok(f"Remembered. Change it later by deleting {CONF}")
    return folder


def drive_missing() -> str | None:
    """The drive the photographs were read onto, if it is not plugged in now.
    Reading them again into this Mac's home folder would split the life in
    two, so say so instead."""
    conf = _remembered()
    if conf.get("drive") and not home.root() and not os.environ.get("SELFCLOUD_INDEX"):
        return conf["drive"]
    return None


def want_lan(argv: list[str]) -> bool:
    """The phone and the TV only when the owner says so. Off by default: on
    hotel or café wifi, 'everyone on the network' is strangers."""
    if "--lan" in argv:
        return True
    say(f"\n  Would you also like to see this on a phone, tablet or TV in this house?")
    say(f"  {D}Type yes and press return, or just press return for this Mac only.{O}")
    try:
        answer = input("  phone/TV? ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    return answer in ("y", "yes", "yes please", "ok", "sure")


def count_indexed() -> int:
    try:
        from photo_index import PhotoIndex
        return next(PhotoIndex(INDEX, create=False).db.execute(
            "SELECT COUNT(*) FROM vectors"))[0]
    except Exception:
        return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    say(f"\n{B}Your life, on the screen{O}")
    say(f"{D}Everything below happens on this machine. Nothing is uploaded.{O}")
    say(f"  {D}Life lives {home.describe()}.{O}")
    gone = drive_missing()
    if gone:
        bad(f"Your photographs were read onto the Self-Cloud drive '{gone}', "
            f"and it isn't plugged in.")
        say(f"  {D}Plug it in, then double-click 'Show me my life' again. Nothing"
            f" was read\n   onto this Mac.{O}")
        return 1

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
    lan = want_lan(argv)
    import wall
    srv = wall.serve(str(INDEX), 8378, lan=lan)
    local = wall.link()
    say(f"\n  {B}On this Mac{O}        {local}")
    if lan:
        say(f"  {B}Phone / TV / iPad{O}  {wall.link(wall.lan_ip())}")
        say(f"\n  {D}Each screen needs this link — being on the wifi is not the same"
            f" as being\n   allowed. It's new every time you start this.{O}")
    else:
        say(f"  {D}This Mac only. To see it on the TV, double-click again and"
            f" answer yes.{O}")
    say(f"\n  {B}Try typing:{O}  vacation ten years ago in Cuba")
    say(f"  {D}The Hide button (or Escape) clears the screen. Ctrl-C here stops"
        f" everything.{O}\n")
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
