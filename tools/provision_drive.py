#!/usr/bin/env python3
"""
provision_drive.py — turn a drive into a Self-Cloud drive.
==========================================================

The hard drive IS the product. Plug it into any Mac and it is your cloud:
your photographs, your conscience, your voice, and the software that runs
them, all on the drive — the Mac only lends its screen and its Python.

    python tools/provision_drive.py /Volumes/MyDisk --name "Self-Cloud"
    python tools/provision_drive.py /Volumes/Self-Cloud --check

What it does, and nothing more:

  1. LAYOUT — creates, never overwrites:
        Self-Cloud/           what the owner sees: launchers and a README
        originals/            read-only, checksummed — the sacred copies
        library/              the working copy the tools index
        .selfcloud/           the machine-side folder, shared with the
                              Self-Cloud connector; JEFFEREY's data goes
                              under .selfcloud/jefferey/ and nowhere else
  2. MARKER — .selfcloud/selfcloud.json so every tool knows this drive is
     the one, and where the life lives (see connector/home.py).
  3. ICON — the Self-Cloud cloud as the drive's icon in Finder
     (.VolumeIcon.icns from the real logo, plus the Finder custom-icon bit).
  4. NAME — optionally renames the volume (macOS, via diskutil).
  5. LAUNCHER — Self-Cloud/Start Self-Cloud.command: double-click on ANY Mac
     and it points every tool at this drive and opens the wall.

It refuses to touch a drive that already holds a different Self-Cloud marker
unless you say --force, and it never deletes or moves a single existing file.
Existing user folders are read-only to it, always (the connector's rule 6.2,
which is also ours).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "connector"))
import home  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
LOGO_CANDIDATES = [
    REPO.parent / "self-cloud" / "Self cloud.PNG",
    REPO.parent / "Jeffrey-AI-Butler" / "assets" / "selfcloud.png",
    REPO / "docs" / "selfcloud-logo.png",
]
FOLDERS = ("Self-Cloud", "originals", "library", ".selfcloud", ".selfcloud/jefferey")

README = """SELF-CLOUD
==========

This drive is your cloud. Everything on it is yours, on hardware you own, and
nothing on it talks to the internet unless you ask it to.

  Self-Cloud/    the buttons — double-click "Start Self-Cloud.command"
  originals/     your originals. Read-only, checksummed, never re-encoded.
  library/       the working copy your tools read and show
  .selfcloud/    the machine side: catalog, index, conscience, voice, and
                 the log of everything that ever left for a rented engine.
                 Hidden on purpose. Don't edit by hand; nothing deletes it.

To use it on any Mac: plug it in, open Self-Cloud/, double-click
"Start Self-Cloud.command". The first time on a new Mac it installs the
pieces it needs (once, ~2 GB). After that it never needs a network.

To make it disappear: unplug it. That is the whole security model, and it
is not a metaphor.

Backup rule, in the owner's own words: two independent copies plus a
verified restore before iCloud is ever cancelled. Encrypt this drive
(Finder > right-click > Encrypt) and keep the passphrase on paper too.

{name} — provisioned {when} — id {id}
"""

LAUNCHER = r'''#!/bin/bash
# Start Self-Cloud from THIS drive, on whatever Mac it is plugged into.
# Everything — photographs, conscience, voice — stays on the drive.
DRIVE="$(cd "$(dirname "$0")/.." && pwd)"
export SELFCLOUD_ROOT="$DRIVE"

CODE="$DRIVE/Self-Cloud/app"
if [ ! -d "$CODE/tools" ]; then
    echo
    echo "  The software isn't on this drive yet. Once, with a network:"
    echo "    git clone https://github.com/lczako-eng/jeffrey-local-butler-ai \"$CODE\""
    echo "    (cd \"$CODE\" && git checkout claude/substantiation-discussion-8dmu3c)"
    echo
    echo "Press return to close."; read -r _; exit 1
fi

VENV="$HOME/.jefferey/venv"            # the Mac lends its Python; data stays here
if [ -x "$VENV/bin/python" ]; then PY="$VENV/bin/python"; else
    PY=""; for c in python3.13 python3.12 python3.11 python3.10 python3; do
        command -v "$c" >/dev/null 2>&1 && PY="$c" && break; done
    [ -z "$PY" ] && { echo "  Install Python: https://www.python.org/downloads/"; read -r _; exit 1; }
    "$PY" -m venv "$VENV" && PY="$VENV/bin/python" && "$PY" -m pip install --quiet --upgrade pip
fi

cd "$CODE" || exit 1
"$PY" tools/go.py "$@"
echo; echo "Press return to close this window."; read -r _
'''


def say(m=""): print(m, flush=True)
def ok(m): say(f"  ✓ {m}")
def warn(m): say(f"  ! {m}")


# ------------------------------------------------------------------- icon
def find_logo() -> Path | None:
    for p in LOGO_CANDIDATES:
        if p.exists():
            return p
    return None


def make_icns(logo: Path, out: Path, size: int = 1024) -> Path:
    """The cloud, square, background keyed to transparent, as a Mac .icns.

    Pillow writes ICNS natively, so this needs no Xcode and runs anywhere.
    """
    from PIL import Image

    im = Image.open(logo).convert("RGBA")
    w, h = im.size
    side = min(w, h)
    im = im.crop(((w - side) // 2, (h - side) // 2,
                  (w - side) // 2 + side, (h - side) // 2 + side))

    # If the four corners agree, that colour is a background: make it clear.
    px = im.load()
    corners = [px[0, 0], px[side - 1, 0], px[0, side - 1], px[side - 1, side - 1]]
    if all(sum(abs(a - b) for a, b in zip(c[:3], corners[0][:3])) < 40 for c in corners):
        bg = corners[0][:3]
        # Pillow renamed getdata -> get_flattened_data and removes the old name
        # in 14 (2027-10). This drive has to still work then, so ask for the
        # new one and fall back, rather than warning at the owner every run.
        data = (im.get_flattened_data() if hasattr(im, "get_flattened_data")
                else im.getdata())
        keyed = []
        for r, g, b, a in data:
            dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
            if dist < 60:
                keyed.append((r, g, b, 0))
            elif dist < 140:                       # soft edge
                keyed.append((r, g, b, int(a * (dist - 60) / 80)))
            else:
                keyed.append((r, g, b, a))
        putdata = getattr(im, "put_flattened_data", None) or im.putdata
        putdata(keyed)

    im = im.resize((size, size), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, format="ICNS")
    return out


def set_volume_icon(volume: Path, icns: Path) -> bool:
    """Put .VolumeIcon.icns at the root and flip Finder's custom-icon bit."""
    dest = volume / ".VolumeIcon.icns"
    shutil.copyfile(icns, dest)
    if platform.system() != "Darwin":
        warn("Icon file placed; the Finder flag can only be set on a Mac.")
        return False
    # FinderInfo: 32 bytes; byte 8 bit 0x04 = kHasCustomIcon.
    info = bytearray(32)
    info[8] = 0x04
    hexs = info.hex()
    r = subprocess.run(["xattr", "-wx", "com.apple.FinderInfo", hexs, str(volume)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        # Fallback: SetFile, if the Xcode tools are present.
        if shutil.which("SetFile"):
            subprocess.run(["SetFile", "-a", "C", str(volume)], capture_output=True)
        else:
            warn(f"Couldn't set the icon flag: {r.stderr.strip()[:120]}")
            return False
    try:                                          # hide the icon file itself
        subprocess.run(["chflags", "hidden", str(dest)], capture_output=True)
    except Exception:
        pass
    # Finder caches; a touch on the volume usually refreshes it.
    os.utime(volume, None)
    return True


# --------------------------------------------------------------- provision
def provision(volume: Path, name: str, rename: bool, force: bool,
              logo: Path | None) -> dict:
    volume = Path(volume).expanduser()
    if not volume.is_dir():
        raise SystemExit(f"\n  Nothing mounted at {volume}.\n")
    marker = volume / home.MARKER
    existing = {}
    if marker.exists():
        try:
            existing = json.loads(marker.read_text())
        except Exception:
            existing = {"corrupt": True}
        if existing and not force:
            say(f"\n  This drive is already a Self-Cloud drive "
                f"('{existing.get('name', '?')}', id {existing.get('id', '?')}).")
            say("  Nothing changed. Use --force to re-provision (keeps the id).\n")
            return existing

    say(f"\n  Provisioning {volume} as '{name}'\n")

    # 1. layout — create only; never touch what is there
    for f in FOLDERS:
        p = volume / f
        if not p.exists():
            p.mkdir(parents=True)
            ok(f"created {f}/")
        else:
            ok(f"kept    {f}/ (already there)")

    # 2. marker
    info = {
        "kind": "self-cloud-drive",
        "name": name,
        "id": existing.get("id") or secrets.token_hex(8),
        "created": existing.get("created") or dt.datetime.now().isoformat(timespec="seconds"),
        "provisioned": dt.datetime.now().isoformat(timespec="seconds"),
        "layout": {"owner_facing": "Self-Cloud/", "originals": "originals/",
                   "library": "library/", "machine": ".selfcloud/",
                   "jefferey": ".selfcloud/jefferey/"},
        "rules": [
            "originals/ is read-only and checksummed; nothing re-encodes in place",
            "nothing under this drive is deleted by software; absence is marked, never removed",
            ".selfcloud/ top level belongs to the Self-Cloud connector; JEFFEREY stays under .selfcloud/jefferey/",
            "unplugged means gone: no cache, no queue, no shadow copy elsewhere",
        ],
    }
    marker.write_text(json.dumps(info, indent=2))
    ok("wrote .selfcloud/selfcloud.json")

    # 3. owner-facing folder
    (volume / "Self-Cloud" / "README.txt").write_text(
        README.format(name=name, when=info["provisioned"][:10], id=info["id"]))
    launcher = volume / "Self-Cloud" / "Start Self-Cloud.command"
    launcher.write_text(LAUNCHER)
    launcher.chmod(0o755)
    ok("wrote Self-Cloud/README.txt and Start Self-Cloud.command")

    # 4. icon
    logo = logo or find_logo()
    if logo:
        icns = make_icns(logo, volume / ".selfcloud" / "jefferey" / "icon.icns")
        if set_volume_icon(volume, icns):
            ok(f"set the drive icon from {logo.name} — eject and re-mount to see it")
        else:
            ok(f"icon written from {logo.name} (flag needs a Mac)")
    else:
        warn("no logo found to make the icon from")

    # 5. name. A rename moves the mount point, so everything printed after it
    # must use the NEW path — telling the owner to open a folder that no
    # longer exists is how a working drive looks broken.
    here = volume
    if rename and platform.system() == "Darwin" and volume.name != name:
        r = subprocess.run(["diskutil", "rename", str(volume), name],
                           capture_output=True, text=True)
        if r.returncode == 0:
            moved = volume.parent / name
            here = moved if moved.is_dir() else volume
            ok(f"renamed the volume to '{name}' — it is now at {here}")
        else:
            warn(f"couldn't rename: {r.stderr.strip()[:120]}")
    elif rename and platform.system() != "Darwin":
        warn("renaming needs a Mac (diskutil)")

    say(f"\n  Done. Open {here}/Self-Cloud/ and double-click "
        f"Start Self-Cloud.command.\n")
    enc = is_encrypted(here)
    if enc is True:
        ok("the drive is encrypted — unplugged, it reads as noise without "
           "your passphrase")
        say()
    elif enc is False:
        warn("this drive is NOT encrypted. Everything on it is readable by "
             "whoever holds it.")
        say(f"    Read ENCRYPT_THE_DRIVE.md in the Self-Cloud repo before you "
            f"put photographs on it.\n")
    return info


def is_encrypted(volume: Path) -> bool | None:
    """True / False on a Mac; None where we cannot tell. Checked, not assumed:
    an earlier version told the owner to go and encrypt a drive he had
    encrypted the day before."""
    if platform.system() != "Darwin":
        return None
    try:
        r = subprocess.run(["diskutil", "info", str(volume)],
                           capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    for line in r.stdout.splitlines():
        key, _, val = line.strip().partition(":")
        if key.strip() in ("FileVault", "Encrypted"):
            if val.strip().lower().startswith("yes"):
                return True
    return False if r.returncode == 0 else None


def check(volume: Path) -> int:
    volume = Path(volume).expanduser()
    marker = volume / home.MARKER
    if not marker.exists():
        say(f"\n  {volume} is not a Self-Cloud drive (no marker).\n")
        return 1
    info = json.loads(marker.read_text())
    say(f"\n  {info.get('name')}  ·  id {info.get('id')}  ·  provisioned {info.get('provisioned', '')[:10]}")
    for f in FOLDERS:
        say(f"  {'✓' if (volume / f).is_dir() else '✗'} {f}/")
    say(f"  {'✓' if (volume / '.VolumeIcon.icns').exists() else '✗'} .VolumeIcon.icns")
    say(f"  {'✓' if (volume / 'Self-Cloud' / 'Start Self-Cloud.command').exists() else '✗'} Start Self-Cloud.command")
    app = volume / "Self-Cloud" / "app"
    say(f"  {'✓' if (app / 'tools').is_dir() else '·'} software on the drive "
        f"({'present' if (app / 'tools').is_dir() else 'not yet — the launcher explains'})")
    for label, p in (("conscience", volume / home.NAMESPACE / "conscience.json"),
                     ("photo index", volume / home.NAMESPACE / "photo-index" / "index.sqlite"),
                     ("voice", volume / home.NAMESPACE / "voice")):
        say(f"  {'✓' if p.exists() else '·'} {label}")
    say()
    return 0


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    import struct
    import tempfile
    from PIL import Image

    td = Path(tempfile.mkdtemp(prefix="drive-"))
    try:
        vol = td / "FAKEDISK"
        vol.mkdir()
        (vol / "Photos").mkdir()
        (vol / "Photos" / "keep.txt").write_text("precious")
        logo = td / "logo.png"
        im = Image.new("RGB", (300, 200), (250, 250, 250))
        for x in range(90, 210):
            for y in range(60, 140):
                im.putpixel((x, y), (40, 120, 220))
        im.save(logo)

        info = provision(vol, "Self-Cloud", rename=False, force=False, logo=logo)
        for f in FOLDERS:
            assert (vol / f).is_dir(), f
        assert (vol / "Photos" / "keep.txt").read_text() == "precious", "touched user data"
        m = json.loads((vol / home.MARKER).read_text())
        assert m["kind"] == "self-cloud-drive" and m["id"] == info["id"]
        assert m["layout"]["jefferey"] == ".selfcloud/jefferey/"

        # the icon is a real ICNS with transparency keyed from the background
        icns = vol / ".VolumeIcon.icns"
        assert icns.exists() and icns.read_bytes()[:4] == b"icns", "not an icns"
        back = Image.open(vol / ".selfcloud" / "jefferey" / "icon.icns")
        back.load()
        assert back.mode == "RGBA" and back.getpixel((2, 2))[3] == 0, "background not keyed"
        assert back.getpixel((back.width // 2, back.height // 2))[3] == 255, "cloud lost"

        # the launcher exists, is executable, and points at its own drive
        launcher = vol / "Self-Cloud" / "Start Self-Cloud.command"
        assert launcher.stat().st_mode & 0o111
        assert 'SELFCLOUD_ROOT="$DRIVE"' in launcher.read_text()

        # re-running does not re-provision and keeps the id
        again = provision(vol, "Other", rename=False, force=False, logo=logo)
        assert again["id"] == info["id"] and again["name"] == "Self-Cloud"
        forced = provision(vol, "Renamed", rename=False, force=True, logo=logo)
        assert forced["id"] == info["id"] and forced["name"] == "Renamed"
        assert check(vol) == 0

        # home.py finds the drive via SELFCLOUD_ROOT and puts the life on it
        home.reset_for_tests()
        os.environ["SELFCLOUD_ROOT"] = str(vol)
        for k in ("JEFFEREY_CONSCIENCE_PATH", "SELFCLOUD_INDEX", "SELFCLOUD_VOICE", "SELFCLOUD_DISCS"):
            os.environ.pop(k, None)
        assert home.root() == vol
        assert home.conscience_path() == vol / ".selfcloud" / "jefferey" / "conscience.json"
        assert home.index_path() == vol / ".selfcloud" / "jefferey" / "photo-index"
        assert home.voice_path() == vol / ".selfcloud" / "jefferey" / "voice"
        assert "Renamed" in home.describe()
        # ...and an explicit env var still wins
        os.environ["SELFCLOUD_INDEX"] = "/tmp/elsewhere"
        assert home.index_path() == Path("/tmp/elsewhere")
        os.environ.pop("SELFCLOUD_INDEX")
        # ...and with no drive, the old home-folder defaults hold
        home.reset_for_tests()
        os.environ["SELFCLOUD_ROOT"] = str(td / "unplugged")
        assert home.root() is None
        assert home.conscience_path() == Path("~/.jefferey/conscience.json").expanduser()
        os.environ.pop("SELFCLOUD_ROOT")
        home.reset_for_tests()

        print("\n  ✓ drive: layout created without touching user files, marker with a")
        print("    stable id, real .icns with the background keyed clear, executable")
        print("    launcher bound to its own drive, re-run is a no-op, --force keeps")
        print("    the id, and home.py routes the conscience/index/voice onto the drive")
        print("    when present and back to the home folder when not.\n")
        return 0
    finally:
        shutil.rmtree(td, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("volume", nargs="?", help="the mounted drive, e.g. /Volumes/MyDisk")
    ap.add_argument("--name", default="Self-Cloud")
    ap.add_argument("--rename", action="store_true", help="rename the volume too (macOS)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--logo", type=Path, help="a PNG to make the icon from")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.volume:
        ap.error("which drive? e.g. /Volumes/MyDisk")
    if a.check:
        return check(Path(a.volume))
    provision(Path(a.volume), a.name, a.rename, a.force, a.logo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
