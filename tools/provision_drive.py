#!/usr/bin/env python3
"""
provision_drive.py — turn a drive into a Self-Cloud drive.
==========================================================

The hard drive IS the product. Plug it into any Mac and it is your cloud:
your photographs, your conscience, your voice, and the software that runs
them, all on the drive — the Mac only lends its screen and its Python.

    python tools/provision_drive.py --interactive          # what the launcher runs
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
     the one, and where the life lives (see connector/home.py). Written
     whole or not at all.
  3. PAIRING — this Mac remembers the drive's id (~/.jefferey/drives.json):
     JEFFEREY uses only drives the owner has said are his, and with his
     drive away it is off — it never starts a second life on the laptop.
  4. ICON — the Self-Cloud cloud as the drive's icon in Finder.
  5. NAME — renames the volume only if the owner typed yes (macOS), and
     never to a name another plugged-in drive already has.
  6. LAUNCHER — Self-Cloud/Start Self-Cloud.command: double-click on ANY Mac
     and it points every tool at this drive and opens the wall.
  7. YOUR MEMORIES — if JEFFEREY already kept a life on this Mac, and the
     owner says yes, it is copied onto the drive, checked, and the Mac's
     copy put aside (never deleted).

It refuses to touch a drive that already holds a different Self-Cloud marker
unless you say --force (which keeps the id, even from a damaged marker), and
it never deletes or moves a single existing file. It writes nothing through
a shortcut (a symbolic link): a tampered drive cannot make it overwrite a
file somewhere else (I-55). Existing user folders are read-only to it,
always (the connector's rule 6.2, which is also ours).
"""

from __future__ import annotations

import argparse
import datetime as dt
import errno
import hashlib
import io
import json
import os
import platform
import re
import secrets
import shutil
import stat as _stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "connector"))
import answers  # noqa: E402
import home  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
LOGO_CANDIDATES = [
    REPO.parent / "self-cloud" / "Self cloud.PNG",
    REPO.parent / "Jeffrey-AI-Butler" / "assets" / "selfcloud.png",
    REPO / "docs" / "selfcloud-logo.png",
]
FOLDERS = ("Self-Cloud", "originals", "library", ".selfcloud", ".selfcloud/jefferey")
NAME = "Self-Cloud"
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
# Volumes that are never a drive someone means (macOS shows these in /Volumes).
SYSTEM_NAMES = {"Macintosh HD", "Macintosh HD - Data", "Recovery", "Preboot",
                "VM", "Update", "com.apple.TimeMachine.localsnapshots"}

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
    echo "  Then, on your Mac, double-click 'Update JEFFEREY.command': it brings"
    echo "  this copy to the same version as the one on the Mac."
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


class Refused(Exception):
    """Provisioning stopped, with a reason in plain words. Nothing on the
    drive was deleted; what was already made is listed above it."""


# ----------------------------------------------------------- safe writing
def _lstat(p: Path):
    try:
        return os.lstat(p)
    except (FileNotFoundError, NotADirectoryError):
        return None


def _write_new(path: Path, data: bytes, mode: int = 0o644) -> None:
    """Write a file of ours on the drive: never through a link, never half.
    A fresh temp file (O_CREAT|O_EXCL|O_NOFOLLOW) gets the bytes and its
    mode, is flushed, then renamed over the old one — a rename replaces a
    link itself, it never writes where the link points."""
    st = _lstat(path)
    if st is not None and (_stat.S_ISLNK(st.st_mode) or not _stat.S_ISREG(st.st_mode)):
        raise Refused(f"There is a shortcut or a folder where JEFFEREY's file "
                      f"'{path.name}' should be, so nothing was written there. Someone "
                      f"may have tampered with this drive; ask someone you trust to look.")
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW, 0o600)
    try:
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fchmod(fd, mode)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def writable(volume: Path) -> bool:
    """Can this drive be written to? (A Windows-formatted drive on a Mac, a
    software installer, a locked card: no.)"""
    try:
        if os.statvfs(volume).f_flag & getattr(os, "ST_RDONLY", 1):
            return False
    except (OSError, AttributeError):
        pass
    return os.access(volume, os.W_OK)


def _plain_oserror(e: OSError) -> str:
    if e.errno == errno.EROFS:
        return "the drive is read-only (it may be formatted for Windows, or locked)"
    if e.errno in (errno.EACCES, errno.EPERM):
        return "this Mac is not allowed to write to it"
    if e.errno == errno.ENOSPC:
        return "the drive is full"
    if e.errno in (errno.ENOTDIR, errno.EEXIST):
        return "a file is in the way where a folder should be"
    return e.strerror or str(e)


# ----------------------------------------------------------- the marker
def read_existing(volume: Path) -> tuple[str, dict, str | None]:
    """('none' | 'valid' | 'invalid' | 'link', marker, an id worth keeping)."""
    marker = Path(volume) / home.MARKER
    sc = _lstat(Path(volume) / ".selfcloud")
    if sc is not None and _stat.S_ISLNK(sc.st_mode):
        return "link", {}, None
    st = _lstat(marker)
    if st is None:
        return "none", {}, salvage_id(volume, b"")
    if _stat.S_ISLNK(st.st_mode):
        return "link", {}, None
    try:
        raw = home._read_small(marker)
    except OSError:
        return "invalid", {}, salvage_id(volume, b"")
    try:
        obj = json.loads(raw)
    except ValueError:
        return "invalid", {}, salvage_id(volume, raw)
    if home.valid_marker(obj):
        return "valid", obj, obj["id"]
    return "invalid", obj if isinstance(obj, dict) else {}, salvage_id(volume, raw)


def salvage_id(volume: Path, raw: bytes) -> str | None:
    """The drive's id from a damaged marker, or from the README beside it, so
    --force keeps it (records elsewhere are keyed to it)."""
    m = re.search(rb'"id"\s*:\s*"([0-9a-f]{16})"', raw or b"")
    if m:
        return m.group(1).decode()
    try:
        text = home._read_small(Path(volume) / "Self-Cloud" / "README.txt").decode("utf-8", "replace")
    except OSError:
        return None
    m = re.search(r"\bid ([0-9a-f]{16})\b", text)
    return m.group(1) if m else None


# ------------------------------------------------------------------- icon
def find_logo() -> Path | None:
    for p in LOGO_CANDIDATES:
        if p.exists():
            return p
    return None


def make_icns(logo: Path, out: Path | None = None, size: int = 1024) -> bytes:
    """The cloud, square, background keyed to transparent, as a Mac .icns.
    Returns the bytes (and writes them to `out`, safely, if given).

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
    buf = io.BytesIO()
    im.save(buf, format="ICNS")
    data = buf.getvalue()
    if out is not None:
        _write_new(Path(out), data)
    return data


def set_volume_icon(volume: Path, icns: bytes) -> bool:
    """Put .VolumeIcon.icns at the root and flip Finder's custom-icon bit."""
    dest = volume / ".VolumeIcon.icns"
    _write_new(dest, icns)
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
        subprocess.run(["chflags", "-h", "hidden", str(dest)], capture_output=True)
    except Exception:
        pass
    # Finder caches; a touch on the volume usually refreshes it.
    os.utime(volume, None)
    return True


# ----------------------------------------------------------- encryption
def is_encrypted(volume: Path, device: str | None = None) -> bool | None:
    """True / False on a Mac; None where we cannot tell. Checked, not assumed
    — and by the drive's DEVICE when it is known, so a second drive with the
    same name can never be checked in its place (I-42)."""
    if platform.system() != "Darwin":
        return None
    return home.encrypted_from(home.disk_info(device or volume))


def _mount_of(device: str) -> Path | None:
    mp = home.disk_info(device).get("MountPoint")
    return Path(mp) if mp else None


# --------------------------------------------------------- your memories
def home_life() -> list[Path]:
    """What JEFFEREY kept of the owner's life on this Mac (never the venv,
    the list of drives, or the door switch)."""
    d = home.owner_dir()
    try:
        kids = sorted(d.iterdir())
    except OSError:
        return []
    return [p for p in kids
            if (p.name.startswith("conscience") or p.name.startswith("egress.jsonl"))
            and not p.name.endswith(".lock") and not p.is_symlink()]


def _sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree(p: Path) -> list[Path]:
    if p.is_dir() and not p.is_symlink():
        return [q for q in sorted(p.rglob("*")) if q.is_file() and not q.is_symlink()]
    return [p] if p.is_file() and not p.is_symlink() else []


def move_home_life(drive_root: Path, out=say) -> dict:
    """Copy the life kept on this Mac onto the drive, check every byte, then
    put the Mac's copy aside in ~/.jefferey/moved-to-self-cloud-<date>/ —
    never delete it. Only when the drive has no life of its own yet: two
    lives are never merged by guessing."""
    src = home.owner_dir()
    dst = Path(drive_root) / home.NAMESPACE
    items = home_life()
    if not items or (not (src / "conscience.json").is_file()
                     and not (dst / "conscience.json").is_file()):
        return {"moved": 0}
    if (dst / "conscience.json").exists():
        state = mac_copy_state(items, dst)
        if state in ("same", "older"):
            # an earlier move put everything on the drive but could not put
            # the Mac's copy aside, or only part of it, and he may have used
            # JEFFEREY since (R7): that is finished now, nothing more
            try:
                aside, done = _put_aside(src, items)
            except _AsideFailed as e:
                _left_on_mac(out, 0, src, e)
                return {"moved": 0, "aside": None, "left_on_mac": str(src),
                        "problem": e.why}
            if state == "same":
                out("  ✓ your memories were already on the drive, every byte the same as the")
                out("    Mac's copy.")
            else:
                out("  ✓ your memories were already on the drive. What was left on this Mac is")
                out("    an older copy of the same life: the drive has all of it, and more.")
            out(f"    The Mac's old copy is now put aside in {aside}.")
            out("    JEFFEREY never reads it again.")
            return {"moved": 0, "aside": str(aside), "finished": len(done)}
        if not (src / "conscience.json").is_file():
            out(f"  ! Some files of a life are still on this Mac, in {src}, and they are not")
            out("    the drive's. Nothing was moved or mixed: JEFFEREY uses the drive's and")
            out("    never reads them. Ask someone you trust to look at them with you.")
            return {"moved": 0, "both": True, "left_on_mac": str(src)}
        out("  ! Your drive already holds memories, and this Mac holds some too. Nothing")
        out("    was moved or mixed: JEFFEREY will use the drive's. The Mac's copy stays")
        out(f"    where it is ({src}); ask someone you trust to help you bring the two together.")
        return {"moved": 0, "both": True}
    for f in FOLDERS[3:]:
        p = Path(drive_root) / f
        st = _lstat(p)
        if st is not None and _stat.S_ISLNK(st.st_mode):
            raise Refused("JEFFEREY's folder on the drive is a shortcut; nothing was moved.")
        if st is None:
            home.guard(p)
            p.mkdir(mode=0o700)
    for it in items:
        if os.path.lexists(dst / it.name):
            raise Refused(f"'{it.name}' is already on the drive; nothing was moved.")
    # Copied into a folder of its own first, checked byte for byte, and only
    # then put in place — the memory file last — so a drive that fills up or
    # a copy that does not match leaves nothing half-done on the drive.
    stage = dst / f".moving-{secrets.token_hex(4)}"
    home.guard(stage)
    stage.mkdir(mode=0o700)
    copied = []
    try:
        for it in items:
            target = stage / it.name
            if it.is_dir():
                shutil.copytree(it, target, symlinks=False,
                                ignore=lambda d, names: [n for n in names
                                                         if (Path(d) / n).is_symlink()])
            else:
                shutil.copy2(it, target)
            copied.append((it, target))
        for a, b in copied:               # every byte, before anything is put aside
            fa, fb = _tree(a), _tree(b)
            if len(fa) != len(fb) or any(_sha_file(x) != _sha_file(y) for x, y in zip(fa, fb)):
                raise Refused("The copy on the drive did not match the Mac's, so the Mac's "
                              "memories were left exactly where they are. Try again.")
        for a, b in sorted(copied, key=lambda ab: ab[0].name == "conscience.json"):
            os.rename(b, dst / a.name)
    except BaseException:
        for _, b in copied:
            if os.path.lexists(dst / b.name) and not os.path.lexists(b):
                # put in place before the failure: taken out again
                tgt = dst / b.name
                shutil.rmtree(tgt) if tgt.is_dir() and not tgt.is_symlink() else tgt.unlink()
        shutil.rmtree(stage, ignore_errors=True)
        raise
    shutil.rmtree(stage, ignore_errors=True)
    copied = [(a, dst / a.name) for a, _ in copied]
    # From here the drive holds the whole life, checked byte for byte, and
    # JEFFEREY uses it. Putting the Mac's copy aside can still fail; that is
    # said as it is, never as 'your memories were not moved' (R7).
    try:
        aside, _ = _put_aside(src, [a for a, _ in copied])
    except _AsideFailed as e:
        _left_on_mac(out, len(copied), src, e)
        return {"moved": len(copied), "aside": None, "left_on_mac": str(src),
                "problem": e.why}
    out(f"  ✓ moved your memories onto the drive ({len(copied)} item(s), every byte checked)")
    out(f"    The Mac's old copy is put aside in {aside}.")
    out("    JEFFEREY never reads it again. Delete that folder once you have checked")
    out("    the drive, if you want no copy of your life left on this Mac.")
    return {"moved": len(copied), "aside": str(aside)}


def _rev_of(p: Path) -> int | None:
    try:
        r = json.loads(p.read_text(encoding="utf-8")).get("_rev")
        return r if isinstance(r, int) else None
    except (OSError, ValueError, AttributeError):
        return None


def _ids_of(p: Path) -> set[str]:
    """The ids of the things a memory file holds (facts, memories, people …)."""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    out: set[str] = set()
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                out |= {str(x["id"]) for x in v if isinstance(x, dict) and x.get("id")}
    return out


def _snap_rev(p: Path) -> int | None:
    try:
        return int(p.stem.rsplit("-", 1)[-1])
    except ValueError:
        return None


def _is_prefix(a: Path, b: Path) -> bool:
    """Is file `a` the beginning of file `b` (a log that only grows)?"""
    try:
        n = a.stat().st_size
        if n > b.stat().st_size:
            return False
        h = hashlib.sha256()
        with open(b, "rb") as f:
            left = n
            while left:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    return False
                h.update(chunk)
                left -= len(chunk)
        return h.hexdigest() == _sha_file(a)
    except OSError:
        return False


def mac_copy_state(items: list[Path], dst: Path) -> str:
    """How what is left of his life on this Mac stands to the drive's life:
    'same' — byte for byte; 'older' — an earlier state of the drive's own
    life: every copy the Mac keeps in its history is on the drive too (or
    older than any the drive still keeps), its memory file is one of the
    drive's copies or older than the drive's, and its record of what left is
    the beginning of the drive's; 'different' — another life, never mixed;
    '' — nothing of a life is on this Mac (R7, round 5: after JEFFEREY was
    used once, the two copies were no longer the same, and the window said
    'Nothing to do' with his whole life left on the Mac)."""
    if not items:
        return ""
    if same_on_drive(items, dst):
        return "same"
    try:
        dh = dst / "conscience.history"
        drive_hist = _tree(dh) if dh.is_dir() else []
        shas = {_sha_file(f) for f in drive_hist}
        revs = [r for r in (_snap_rev(f) for f in drive_hist) if r is not None]
        oldest = min(revs) if revs else None
        shared = False                 # a copy of the same life on both: the same past
        for it in items:
            if it.is_dir():
                for f in _tree(it):
                    if _sha_file(f) in shas:
                        shared = True
                    elif not (oldest is not None and (_snap_rev(f) or 0) < oldest):
                        return "different"   # a copy the drive never had: its own past
        src = items[0].parent
        aside = any((a / "conscience.json").is_file() for a in src.glob("moved-to-self-cloud-*"))
        for it in items:
            there = dst / it.name
            if (it.name.startswith("egress.jsonl") and it.is_file() and there.is_file()
                    and it.stat().st_size and _is_prefix(it, there)):
                shared = True          # the record of what left only grows: the same past
            if it.name == "conscience.json" and there.is_file() and not shared:
                mine, theirs = _ids_of(it), _ids_of(there)
                if mine and mine <= theirs:
                    shared = True      # every thing the Mac's copy holds, the drive holds too
        for it in items:
            there = dst / it.name
            if it.is_dir():
                continue
            if it.name == "conscience.json":
                if _sha_file(it) in shas or (there.is_file() and _sha_file(it) == _sha_file(there)):
                    shared = True
                    continue
                mine, theirs = _rev_of(it), _rev_of(there)
                if shared and mine is not None and theirs is not None and mine < theirs:
                    continue
                return "different"
            if it.name.startswith("egress.jsonl"):
                # the record of what left only grows; one rewritten since (a
                # forget takes words out of it) is still the same life's
                if there.is_file() and (_is_prefix(it, there) or shared or aside):
                    continue
                return "different"
            # the small files beside the memory (changes waiting, keys) go
            # with the life they belong to
            if not (shared or aside):
                return "different"
        return "older" if (shared or aside) else "different"
    except (OSError, ValueError):
        return "different"


def same_on_drive(items: list[Path], dst: Path) -> bool:
    """Is every one of these Mac items on the drive too, byte for byte?"""
    if not items:
        return False
    try:
        for it in items:
            there = dst / it.name
            fa, fb = _tree(it), _tree(there)
            if (it.is_dir() != there.is_dir() or len(fa) != len(fb)
                    or any(x.relative_to(it) != y.relative_to(there) for x, y in zip(fa, fb))
                    or any(_sha_file(x) != _sha_file(y) for x, y in zip(fa, fb))):
                return False
    except (OSError, ValueError):
        return False
    return True


class _AsideFailed(Exception):
    def __init__(self, why: str, aside: Path | None, done: list[str]):
        super().__init__(why)
        self.why, self.aside, self.done = why, aside, done


def _put_aside(src: Path, items: list[Path]) -> tuple[Path, list[str]]:
    """Move the Mac's copy into ~/.jefferey/moved-to-self-cloud-<date>/,
    never deleting it. Raises _AsideFailed, saying how far it got."""
    aside = src / f"moved-to-self-cloud-{dt.date.today().isoformat()}"
    n = 1
    while os.path.lexists(aside):
        n += 1
        aside = src / f"moved-to-self-cloud-{dt.date.today().isoformat()}-{n}"
    done: list[str] = []
    try:
        aside.mkdir(mode=0o700)
    except OSError as e:
        raise _AsideFailed(_plain_oserror(e), None, done) from None
    for a in items:
        try:
            os.rename(a, aside / a.name)
        except OSError as e:
            if not done:
                try:
                    aside.rmdir()          # nothing went in: no empty folder left behind
                except OSError:
                    pass
            raise _AsideFailed(_plain_oserror(e), aside if done else None, done) from None
        done.append(a.name)
    return aside, done


def _left_on_mac(out, moved: int, src: Path, e: _AsideFailed) -> None:
    """The truth when the drive holds the life but the Mac's copy could not
    be put aside (R7: this was reported as 'Your memories were not moved …
    nothing of them was left on the drive. Make room on the drive')."""
    if moved:
        out(f"  ✓ moved your memories onto the drive ({moved} item(s), every byte checked).")
    out("    JEFFEREY uses the drive's copy from now on; nothing is lost.")
    out(f"  ! But the copy on this Mac could not be put aside ({e.why}), so it is still")
    out(f"    there, in {src}" + (f" (part of it is already in {e.aside})." if e.done else "."))
    out("    JEFFEREY does not read it. To finish, double-click 'Make this drive a")
    out("    Self-Cloud.command' again later and answer yes when it offers to put the Mac's")
    out("    copy aside — or ask someone you trust to move those files somewhere safe.")


# --------------------------------------------------------------- provision
def _precheck(volume: Path) -> None:
    """Before anything is made: every path this writes is either absent or
    the right kind of thing — never a shortcut. (A gift drive whose
    'Start Self-Cloud.command' pointed at ~/.zshrc used to get it
    overwritten, and a dangling marker link created a LaunchAgent.)"""
    for f in FOLDERS:
        st = _lstat(volume / f)
        if st is None:
            continue
        if _stat.S_ISLNK(st.st_mode):
            raise Refused(f"'{f}' on this drive is a shortcut to somewhere else, so "
                          f"nothing was written. Someone may have tampered with this "
                          f"drive; ask someone you trust to look at it.")
        if not _stat.S_ISDIR(st.st_mode):
            raise Refused(f"There is a file called '{f}' on this drive where a folder "
                          f"should be, so nothing was changed. Move that file somewhere "
                          f"else first.")
    for rel in (home.MARKER, Path("Self-Cloud/README.txt"),
                Path("Self-Cloud/Start Self-Cloud.command"), Path(".VolumeIcon.icns"),
                Path(".selfcloud/jefferey/icon.icns")):
        st = _lstat(volume / rel)
        if st is not None and (_stat.S_ISLNK(st.st_mode) or not _stat.S_ISREG(st.st_mode)):
            raise Refused(f"'{rel}' on this drive is a shortcut or a folder, so nothing "
                          f"was written. Someone may have tampered with this drive; ask "
                          f"someone you trust to look at it.")


def provision(volume: Path, name: str, rename: bool, force: bool,
              logo: Path | None, pair: bool = True, move_life: bool = False) -> dict:
    """Make the drive a Self-Cloud drive. Raises Refused, in plain words,
    when it cannot — a read-only or installer volume, a damaged marker
    without --force, a shortcut where a file should be, a write that fails."""
    volume = Path(volume).expanduser()
    if not volume.is_dir() or volume.is_symlink():
        raise Refused(f"Nothing is mounted at {volume}.")
    if not writable(volume):
        raise Refused(f"'{volume.name}' cannot be written to — it may be read-only, a "
                      f"software installer, or formatted for Windows — so nothing was "
                      f"changed. A Self-Cloud drive must be one this Mac can write to "
                      f"(formatted as APFS or Mac OS Extended in Disk Utility).")
    state, existing, keep_id = read_existing(volume)
    if state == "link":
        raise Refused("The Self-Cloud marker on this drive is a shortcut to somewhere "
                      "else, so nothing was written. Someone may have tampered with this "
                      "drive; ask someone you trust to look at it.")
    if state == "valid" and not force:
        say(f"\n  This drive is already a Self-Cloud drive "
            f"('{home.safe_name(existing.get('name'))}', id {existing['id']}).")
        say("  Nothing changed. Use --force to re-provision (keeps the id).\n")
        return existing
    if state == "invalid" and not force:
        raise Refused("This drive's Self-Cloud marker is damaged, so nothing was changed. "
                      + (f"Its id was {keep_id}; " if keep_id else "")
                      + "to repair it and keep the id, run this again with --force.")

    _precheck(volume)
    say(f"\n  Provisioning {volume} as '{name}'\n")
    try:
        info = _lay_out(volume, name, existing, keep_id, logo)
    except Refused:
        raise
    except OSError as e:
        raise Refused(f"Setting up the drive stopped: {_plain_oserror(e)}. Nothing on it "
                      f"was deleted; whatever was made before this is listed above. "
                      f"Fix that, then double-click this again.") from None

    # Name. A rename moves the mount point, so everything after it uses the
    # drive's NEW place, found by its device — never by guessing parent/name,
    # which with a second 'Self-Cloud' plugged in pointed at the other drive.
    here = volume
    disk = home.disk_info(volume)
    device = disk.get("DeviceIdentifier")
    if rename and platform.system() == "Darwin" and volume.name != name:
        taken = volume.parent / name
        if os.path.lexists(taken):
            warn(f"another drive is already called '{name}', so this one keeps its name "
                 f"'{volume.name}' — two drives with one name is how the wrong one gets "
                 f"checked.")
        else:
            r = subprocess.run(["diskutil", "rename", str(device or volume), name],
                               capture_output=True, text=True)
            if r.returncode == 0:
                found = _mount_of(device) if device else None
                if found is None:
                    cand = volume.parent / name
                    mk = home.read_marker(cand) if cand.is_dir() else None
                    found = cand if mk and mk.get("id") == info["id"] else None
                if found is None:
                    warn("renamed, but JEFFEREY could not find where the drive is now; "
                         "eject it and plug it back in")
                    here = None
                else:
                    here = found
                    ok(f"renamed the volume to '{name}' — it is now at {here}")
            else:
                warn(f"couldn't rename: {r.stderr.strip()[:120]}")
    elif rename and platform.system() != "Darwin":
        warn("renaming needs a Mac (diskutil)")

    if pair:
        try:
            home.pair(here or volume, info, disk.get("VolumeUUID"))
            ok("this Mac now knows the drive is yours: JEFFEREY will use it, and no "
               "drive you have not said yes to")
        except OSError as e:
            warn(f"this Mac could not remember the drive ({_plain_oserror(e)}); run "
                 f"python3 connector/home.py pair '{here or volume}'")
    if move_life and here is not None:
        try:
            move_home_life(here)
        except Refused:
            raise
        except OSError as e:
            # verify I-65: ENOSPC while copying ended in a traceback, with a
            # half-copied life on a paired drive
            raise Refused(f"Your memories were not moved: {_plain_oserror(e)}. They are "
                          f"exactly where they were, on this Mac, and nothing of them was "
                          f"left on the drive. Make room on the drive, then double-click "
                          f"this again.") from None

    if here is not None:
        say(f"\n  Done. Open {here}/Self-Cloud/ and double-click "
            f"Start Self-Cloud.command.\n")
    enc = is_encrypted(here or volume, device)
    if enc is True:
        ok("the drive is encrypted — unplugged, it reads as noise without "
           "your passphrase")
        say()
    elif enc is False:
        warn("this drive is NOT encrypted. Everything on it is readable by "
             "whoever holds it.")
        say("    Read docs/ENCRYPT_THE_DRIVE.md (in this JEFFEREY folder) before "
            "you put photographs on it.\n")
    else:
        warn("JEFFEREY could NOT verify that this drive is encrypted. Check it "
             "yourself with step 1 of docs/ENCRYPT_THE_DRIVE.md (in this JEFFEREY "
             "folder): it says what each kind of drive shows, and what to do.\n")
    return info


def _lay_out(volume: Path, name: str, existing: dict, keep_id: str | None,
             logo: Path | None) -> dict:
    # 1. layout — create only; never touch what is there
    for f in FOLDERS:
        p = volume / f
        if _lstat(p) is None:
            p.mkdir(mode=0o700 if f == ".selfcloud/jefferey" else 0o755)
            ok(f"created {f}/")
        else:
            ok(f"kept    {f}/ (already there)")

    # 2. marker, written whole or not at all
    now = dt.datetime.now().isoformat(timespec="seconds")
    info = {
        "kind": home.MARKER_KIND,
        "name": name,
        "id": keep_id or secrets.token_hex(8),
        "created": existing.get("created") if isinstance(existing.get("created"), str) else now,
        "provisioned": now,
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
    _write_new(volume / home.MARKER, (json.dumps(info, indent=2) + "\n").encode())
    ok("wrote .selfcloud/selfcloud.json" + (f" (kept the id {keep_id})" if keep_id else ""))

    # 3. owner-facing folder
    _write_new(volume / "Self-Cloud" / "README.txt",
               README.format(name=name, when=info["provisioned"][:10], id=info["id"]).encode())
    _write_new(volume / "Self-Cloud" / "Start Self-Cloud.command", LAUNCHER.encode(), 0o755)
    ok("wrote Self-Cloud/README.txt and Start Self-Cloud.command")

    # 4. icon
    logo = logo or find_logo()
    if not logo:
        warn("no logo found to make the icon from")
        return info
    try:
        icns = make_icns(logo, volume / ".selfcloud" / "jefferey" / "icon.icns")
    except ImportError:
        warn("the cloud icon needs the picture library (Pillow); the drive works without it")
        return info
    if set_volume_icon(volume, icns):
        ok(f"set the drive icon from {logo.name} — eject and re-mount to see it")
    else:
        ok(f"icon written from {logo.name} (flag needs a Mac)")
    return info


# ------------------------------------------------------------------ check
def check(volume: Path) -> int:
    volume = Path(volume).expanduser()
    state, info, keep_id = read_existing(volume)
    if state == "none":
        say(f"\n  {volume} is not a Self-Cloud drive (no marker).\n")
        return 1
    if state == "link":
        say(f"\n  {volume}: the Self-Cloud marker is a shortcut to somewhere else. "
            f"JEFFEREY will not use this drive.\n")
        return 1
    if state == "invalid":
        say(f"\n  {volume}: the Self-Cloud marker is damaged, so JEFFEREY will not use "
            f"this drive." + (f" Its id was {keep_id}." if keep_id else "")
            + "\n  To repair it and keep the id: python3 tools/provision_drive.py "
              f"'{volume}' --force\n")
        return 1
    say(f"\n  {home.safe_name(info.get('name'))}  ·  id {info.get('id')}  ·  "
        f"provisioned {str(info.get('provisioned', ''))[:10]}")
    try:
        mine = info["id"] in home.pinned_ids()
    except home.PairingDamaged:
        mine = False
    say(f"  {'✓' if mine else '·'} {'paired with this Mac' if mine else 'NOT paired with this Mac'}")
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
    enc = is_encrypted(volume)
    say("  " + {True: "✓ encrypted", False: "! NOT encrypted",
                None: "! could NOT verify encryption"}[enc])
    say()
    return 0


# ------------------------------------------------------- the launcher's questions
def _why_not(v: Path) -> str | None:
    """Why this volume is not offered as a drive to set up, or None."""
    try:
        if os.stat(v).st_dev == os.stat("/").st_dev:
            return "the Mac's own disk"
    except OSError:
        return "it cannot be read"
    info = home.disk_info(v)
    if info.get("BusProtocol") == "Disk Image" or info.get("VirtualOrPhysical") == "Virtual":
        return "a software installer (a disk image), not a drive"
    if info.get("WritableVolume") is False or not writable(v):
        return "it cannot be written to (read-only, or formatted for Windows)"
    return None


def list_drives(bases: list[str] | None = None) -> tuple[list[Path], list[tuple[Path, str]]]:
    """(drives someone could mean, [(volume, why it is not offered)])."""
    offer, skipped = [], []
    for base in bases or ["/Volumes"]:
        try:
            kids = sorted(Path(base).iterdir())
        except OSError:
            continue
        for v in kids:
            if v.is_symlink() or not v.is_dir() or v.name in SYSTEM_NAMES:
                continue
            why = _why_not(v)
            (skipped.append((v, why)) if why else offer.append(v))
    return offer, skipped


def _clean_path(raw: str) -> str:
    """What Finder puts in the window when a drive is dragged in."""
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        s = s[1:-1]
    return re.sub(r"\\(.)", r"\1", s)


def interactive(input_fn=input, out=say, bases: list[str] | None = None) -> int:
    """'Make this drive a Self-Cloud.command'. Asks, in plain words; a yes is
    only ever typed (I-60, I-65): a closed window chooses nothing, renames
    nothing, and moves nothing."""
    drives, skipped = list_drives(bases)
    out("")
    if not drives:
        out("  No drive that can be set up is plugged in. Plug it in and double-click this again.")
        for v, why in skipped:
            out(f"     (not offered: '{v.name}' — {why})")
        return 1
    out("  Which drive?")
    for i, v in enumerate(drives, 1):
        out(f"     {i}) {v.name}")
    for v, why in skipped:
        out(f"     (not offered: '{v.name}' — {why})")
    out("")
    one = len(drives) == 1
    out(f"  Press return for '{drives[0].name}' — or type a number, a name, or drag one in."
        if one else "  Type a number or a name, or drag a drive in from Finder, then press return.")
    vol = None
    for _ in range(8):
        try:
            raw = input_fn("  drive: ")
        except (EOFError, KeyboardInterrupt):
            out("\n  Nothing was changed.")
            return 1
        a = _clean_path(raw)
        if not a and one:
            vol = drives[0]
        elif a.isdigit() and 1 <= int(a) <= len(drives):
            vol = drives[int(a) - 1]
        elif a:
            p = Path(a) if a.startswith("/") else Path((bases or ["/Volumes"])[0]) / a
            if not p.is_dir():
                out(f"  Nothing is plugged in called '{a}' — try again.")
                continue
            why = _why_not(p)
            if why:
                out(f"  '{p.name}' cannot be used: {why}. Choose another.")
                continue
            vol = p
        else:
            out("  Type a number from the list, then press return.")
            continue
        break
    if vol is None:
        out("  Nothing was changed.")
        return 1
    out(f"  Using {vol}")

    state, existing, keep_id = read_existing(vol)
    force = False
    if state == "valid":
        out(f"\n  This drive is already a Self-Cloud drive "
            f"('{home.safe_name(existing.get('name'))}', id {existing['id']}).")
        try:
            mine = existing["id"] in home.pinned_ids()
        except home.PairingDamaged:
            mine = False
        if mine:
            out("  This Mac already knows it is yours.")
            left = home_life()
            state = (mac_copy_state(left, vol / home.NAMESPACE)
                     if left and (vol / home.NAMESPACE / "conscience.json").is_file() else "")
            if state in ("same", "older"):
                # an earlier move could not put the Mac's copy aside, or only
                # part of it, and he may have used JEFFEREY since (R7)
                out("  Your memories are on the drive. A copy is still on this Mac, in")
                out(f"  {home.owner_dir()}.")
                out("  It is " + ("the same, byte for byte" if state == "same" else
                              "an older copy of the same life: the drive has all of it, and more")
                    + ". JEFFEREY does not read it.")
                if answers.ask_yes_no_or_none(
                        "  Put the Mac's copy aside now (it is kept, not deleted)? Type yes or "
                        "no: ", input_fn, out):
                    res = move_home_life(vol, out)
                    return 0 if res.get("aside") else 1
                out(f"  Nothing was changed. The Mac's copy is still in {home.owner_dir()};")
                out("  double-click this again whenever you want it put aside.")
                return 0
            if state == "different":
                out("  ! Your drive holds your memories, and this Mac still holds a different")
                out(f"    copy of a life, in {home.owner_dir()}. Nothing was moved or mixed:")
                out("    JEFFEREY uses the drive's and never reads the Mac's. Ask someone you")
                out("    trust to help you bring the two together.")
                return 0
            if (home.owner_dir() / "conscience.json").is_file() and not os.path.lexists(
                    vol / home.NAMESPACE / "conscience.json"):
                move = answers.ask_yes_no_or_none(
                    "  Your memories are still on this Mac. Move them onto the drive? Type yes "
                    "or no: ", input_fn, out)
                if move:
                    try:
                        res = move_home_life(vol, out)
                    except Refused as e:
                        out(f"  ! {e}")
                        return 1
                    except OSError as e:
                        out(f"  ! Your memories were not moved: {_plain_oserror(e)}. They "
                            f"are exactly where they were, on this Mac.")
                        return 1
                    return 1 if res.get("left_on_mac") else 0
                out("  Nothing was changed. JEFFEREY stays off until they are moved: he will")
                out("  not start an empty life on the drive.")
                return 1
            if home_life():
                out(f"  Some files of a life are still on this Mac, in {home.owner_dir()}, but")
                out("  not its memory file. JEFFEREY does not read them; ask someone you trust")
                out("  to look at them with you.")
                return 0
            out("  Nothing to do.")
            return 0
        out("  If you bought it second-hand or it is someone else's, it may hold their life:")
        out("  answer no, and JEFFEREY will not use it.")
        if not answers.ask_yes_no_or_none("  Is this your own Self-Cloud drive? Type yes or "
                                          "no: ", input_fn, out):
            out("  Nothing was changed. JEFFEREY will not use this drive.")
            return 1
        try:
            home.pair(vol, existing)
        except OSError as e:
            out(f"  ! This Mac could not remember the drive ({_plain_oserror(e)}).")
            return 1
        out("  ✓ This Mac now knows the drive is yours. Quit Claude completely and open")
        out("    it again so it picks this up.")
        if (home.owner_dir() / "conscience.json").is_file():
            move = answers.ask_yes_no_or_none(
                "  Your memories are on this Mac. Move them onto the drive? Type yes or no: ",
                input_fn, out)
            if move:
                try:
                    res = move_home_life(vol, out)
                except Refused as e:
                    out(f"  ! {e}")
                    return 1
                except OSError as e:
                    out(f"  ! Your memories were not moved: {_plain_oserror(e)}. They are "
                        f"exactly where they were, on this Mac.")
                    return 1
                if res.get("left_on_mac"):
                    return 1
            else:
                out("  JEFFEREY stays off until they are moved: he will not start an empty life")
                out("  on the drive. Double-click this again and answer yes.")
        return 0
    if state == "link":
        out("  The Self-Cloud marker on this drive is a shortcut to somewhere else, so")
        out("  nothing was written. Someone may have tampered with it; ask someone you trust.")
        return 1
    if state == "invalid":
        out("  This drive's Self-Cloud marker is damaged"
            + (f" (its id was {keep_id})." if keep_id else "."))
        if not answers.ask_yes_no_or_none("  Repair it, keeping its id? Type yes or no: ",
                                          input_fn, out):
            out("  Nothing was changed.")
            return 1
        force = True

    # No answer stops here, with nothing done (verify I-65: after five
    # answers it did not understand, it said 'nothing was changed' and went
    # on to set the drive up).
    rename = False
    if vol.name != NAME:
        rename = answers.ask_yes_no_or_none(f"  Name it '{NAME}' in Finder too? Type yes or "
                                            f"no: ", input_fn, out)
        if rename is None:
            return 1
    move = False
    if (home.owner_dir() / "conscience.json").is_file():
        out("\n  JEFFEREY has been keeping your memories on this Mac. Moving them onto the")
        out("  drive means they live there from now on; the Mac's copy is put aside, not")
        out("  deleted, until you say so.")
        move = answers.ask_yes_no_or_none("  Move them onto the drive? Type yes or no: ",
                                          input_fn, out)
        if move is None:
            return 1
    try:
        provision(vol, NAME, rename, force, None, pair=True, move_life=move)
    except Refused as e:
        out(f"\n  ! {e}\n")
        return 1
    out("  If the icon hasn't changed yet: eject the drive and plug it back in.")
    out("  Then open the Self-Cloud folder on it and double-click Start Self-Cloud.")
    return 0


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    import tempfile
    from PIL import Image

    td = Path(tempfile.mkdtemp(prefix="drive-"))
    saved = {k: os.environ.get(k) for k in ("JEFFEREY_DRIVES", "SELFCLOUD_ROOT",
                                             "JEFFEREY_CONSCIENCE_PATH", "SELFCLOUD_INDEX",
                                             "SELFCLOUD_VOICE", "SELFCLOUD_DISCS",
                                             "JEFFEREY_EGRESS", "JEFFEREY_DOOR")}
    os.environ["JEFFEREY_DRIVES"] = str(td / "drives.json")     # never the real Mac's list
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
        assert info["id"] in home.pinned_ids(), "provisioning did not pair the drive"

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
        for k in ("JEFFEREY_CONSCIENCE_PATH", "SELFCLOUD_INDEX", "SELFCLOUD_VOICE",
                  "SELFCLOUD_DISCS", "JEFFEREY_EGRESS", "JEFFEREY_DOOR"):
            os.environ.pop(k, None)
        assert home.root() == vol
        assert home.conscience_path() == vol / ".selfcloud" / "jefferey" / "conscience.json"
        assert home.index_path() == vol / ".selfcloud" / "jefferey" / "photo-index"
        assert home.voice_path() == vol / ".selfcloud" / "jefferey" / "voice"
        assert "Renamed" in home.describe() and home.problem() is None
        # ...and an explicit env var still wins
        os.environ["SELFCLOUD_INDEX"] = "/tmp/elsewhere"
        assert home.index_path() == Path("/tmp/elsewhere")
        os.environ.pop("SELFCLOUD_INDEX")
        # ...and with the paired drive unplugged, the life is NOT moved to the
        # home folder: JEFFEREY is off and says so. (Until October 2026 this
        # test asserted the laptop fallback — the split brain of I-08.)
        home.reset_for_tests()
        os.environ["SELFCLOUD_ROOT"] = str(td / "unplugged")
        assert home.root() is None
        assert "not plugged in" in (home.problem() or "")
        assert not str(home.conscience_path()).startswith(str(Path.home()))
        os.environ.pop("SELFCLOUD_ROOT")
        home.reset_for_tests()

        print("\n  ✓ drive: layout created without touching user files, marker with a")
        print("    stable id, paired with this Mac, real .icns with the background keyed")
        print("    clear, executable launcher bound to its own drive, re-run is a no-op,")
        print("    --force keeps the id, and home.py routes the conscience/index/voice")
        print("    onto the drive when present — and refuses, never the home folder,")
        print("    when the paired drive is away.\n")
        return 0
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        home.reset_for_tests()
        shutil.rmtree(td, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("volume", nargs="?", help="the mounted drive, e.g. /Volumes/MyDisk")
    ap.add_argument("--name", default=NAME)
    ap.add_argument("--rename", action="store_true", help="rename the volume too (macOS)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--logo", type=Path, help="a PNG to make the icon from")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-pair", action="store_true",
                    help="do not tell this Mac the drive is yours")
    ap.add_argument("--move-my-life", action="store_true",
                    help="move the memories kept on this Mac onto the drive")
    ap.add_argument("--interactive", action="store_true",
                    help="ask which drive, in plain words (the launcher)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.interactive:
        return interactive()
    if not a.volume:
        ap.error("which drive? e.g. /Volumes/MyDisk")
    if a.check:
        return check(Path(a.volume))
    try:
        provision(Path(a.volume), a.name, a.rename, a.force, a.logo,
                  pair=not a.no_pair, move_life=a.move_my_life)
    except Refused as e:
        say(f"\n  ! {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
