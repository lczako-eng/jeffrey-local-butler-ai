#!/usr/bin/env python3
"""
disc_archive.py — get the family DVDs off the discs before the discs go.
========================================================================

Home-burned DVDs are not the archival medium people assume. A pressed
commercial disc is stamped metal; a DVD-R burned on a home machine is a
photosensitive *dye* that fades — faster if it was a cheap disc, faster still
in a warm or humid house. Discs burned in the 2000s are already failing, and
the failure is quiet: the disc still looks fine, plays for eleven minutes, and
then stops.

The good news, compared to tape: **ripping is not real-time**, it needs no
capture hardware beyond a $25 USB drive, and the video on the disc is already
a file. Copying `VIDEO_TS` verbatim is a perfect, lossless preservation of
what is on that disc — no re-encoding, no quality lost, nothing decided now
that can't be decided later.

What this does:

  * copies the disc **verbatim** — the archived copy IS the original, in the
    `/originals` sense: read-only, checksummed, never re-encoded in place;
  * **survives a damaged disc.** One unreadable sector must not cost you the
    whole evening. It reads chunk by chunk, records exactly which byte ranges
    could not be read, fills them and carries on — so a scratched disc gives
    you 98% of your mother's birthday instead of an error message;
  * writes a manifest naming every file, its SHA-256, and its damage, so
    `verify` can tell you years later whether the copy still reads true;
  * never touches the disc. Read-only, always.

    python tools/disc_archive.py rip  /Volumes/MUM_1994 --label "Mum's birthday 1994"
    python tools/disc_archive.py list
    python tools/disc_archive.py verify
    python tools/disc_archive.py audio <disc-id>      # needs ffmpeg

Then the audio goes to local transcription and into the index, and "what did
mum say about the house" becomes a question with an answer — played back in
her own voice. The transcript is a convenience. The recording is the truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

CHUNK = 1 << 16                      # 64 KiB: small enough to lose little
DEFAULT_LIBRARY = "~/.selfcloud/discs"
VIDEO_EXT = {".vob", ".ifo", ".bup", ".mpg", ".mpeg", ".m2v", ".avi", ".mp4", ".mov"}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "disc"


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ----------------------------------------------------------------- copying
def copy_recovering(src: Path, dst: Path, opener=None) -> dict:
    """Copy one file, surviving unreadable sectors.

    A normal copy aborts on the first bad read and you lose everything after
    it. This records the byte range it could not read, writes zeros in its
    place so the file stays the right length and still plays, and keeps
    going. What you get back says exactly how much is real.
    """
    opener = opener or (lambda p: open(p, "rb"))
    size = src.stat().st_size
    h = hashlib.sha256()
    bad: list[list[int]] = []
    read_ok = 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    with opener(src) as fin, open(dst, "wb") as fout:
        pos = 0
        while pos < size:
            want = min(CHUNK, size - pos)
            try:
                fin.seek(pos)
                block = fin.read(want)
                if len(block) < want:            # short read at a bad spot
                    block = block + b"\0" * (want - len(block))
                    bad.append([pos + len(block), pos + want])
                else:
                    read_ok += want
            except OSError:
                block = b"\0" * want             # the sector is gone
                if bad and bad[-1][1] == pos:
                    bad[-1][1] = pos + want      # merge adjacent damage
                else:
                    bad.append([pos, pos + want])
            fout.write(block)
            h.update(block)
            pos += want
    return {"bytes": size, "sha256": h.hexdigest(), "unreadable": bad,
            "recovered": round(read_ok / size, 6) if size else 1.0}


def rip(source: Path, library: Path, label: str = "", when: str = "") -> dict:
    """Copy a whole disc (or a folder shaped like one) into the library."""
    source = Path(source).expanduser()
    if not source.exists():
        raise SystemExit(f"\nNothing at {source}. Is the disc mounted?\n")
    library = Path(library).expanduser()
    disc_id = f"{time.strftime('%Y%m%d')}-{_slug(label or source.name)}"
    dest = library / disc_id
    if dest.exists():
        raise SystemExit(f"\n{dest} already exists — that disc looks archived.\n"
                         f"Give it a different --label, or delete that folder.\n")

    files = sorted(p for p in source.rglob("*") if p.is_file())
    if not files:
        raise SystemExit(f"\n{source} has no files in it.\n")

    print(f"\n  Disc     {label or source.name}")
    print(f"  From     {source}")
    print(f"  Into     {dest}")
    print(f"  Files    {len(files)}\n")

    entries, damaged, total = [], 0, 0
    for i, p in enumerate(files, 1):
        rel = p.relative_to(source)
        try:
            info = copy_recovering(p, dest / rel)
        except OSError as exc:
            print(f"  ! could not open {rel}: {exc}")
            entries.append({"path": str(rel), "error": str(exc)})
            damaged += 1
            continue
        info["path"] = str(rel)
        entries.append(info)
        total += info["bytes"]
        if info["unreadable"]:
            damaged += 1
            pct = info["recovered"] * 100
            print(f"  ! {rel}  —  {pct:.2f}% recovered, "
                  f"{len(info['unreadable'])} damaged range(s)")
        else:
            print(f"  ✓ {rel}  ({_human(info['bytes'])})")

    manifest = {
        "disc_id": disc_id,
        "label": label or source.name,
        "recorded": when or "",
        "ripped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": str(source),
        "files": entries,
        "bytes": total,
        "damaged_files": damaged,
        "visibility": "legacy",
        "rule": ("This is an original. Read-only, never re-encoded in place. "
                 "Everything downstream works on copies. The recording is the "
                 "truth; a transcript is only a convenience."),
    }
    (dest / "disc.json").write_text(json.dumps(manifest, indent=2))

    # Make the copy read-only, so a later tool cannot casually overwrite it.
    for p in dest.rglob("*"):
        if p.is_file() and p.name != "disc.json":
            try:
                p.chmod(0o444)
            except OSError:
                pass

    print(f"\n  {_human(total)} archived as {disc_id}")
    if damaged:
        print(f"  {damaged} file(s) had unreadable sectors — the rest is intact "
              f"and still plays.")
        print(f"  If this disc matters, try it again in another drive: different "
              f"lasers\n  read different discs, and a second attempt often "
              f"recovers more.")
    else:
        print("  Every sector read cleanly.")
    print(f"\n  Keep the disc. This copy does not replace it — it outlives it.\n")
    return manifest


# ------------------------------------------------------------------ verify
def verify(library: Path) -> int:
    library = Path(library).expanduser()
    discs = sorted(library.glob("*/disc.json"))
    if not discs:
        print(f"\n  Nothing archived in {library} yet.\n")
        return 0
    bad_total = 0
    for m in discs:
        man = json.loads(m.read_text())
        root = m.parent
        changed, missing = [], []
        for e in man["files"]:
            if "sha256" not in e:
                continue
            f = root / e["path"]
            if not f.exists():
                missing.append(e["path"])
                continue
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                while block := fh.read(1 << 20):
                    h.update(block)
            if h.hexdigest() != e["sha256"]:
                changed.append(e["path"])
        mark = "✓" if not (changed or missing) else "✗"
        print(f"  {mark} {man['disc_id']}  {man['label']}  "
              f"({len(man['files'])} files, {_human(man['bytes'])})")
        for p in missing:
            print(f"      missing: {p}")
        for p in changed:
            print(f"      CHANGED since it was archived: {p}")
        bad_total += len(changed) + len(missing)
    print()
    return 1 if bad_total else 0


def listing(library: Path) -> int:
    library = Path(library).expanduser()
    discs = sorted(library.glob("*/disc.json"))
    if not discs:
        print(f"\n  Nothing archived in {library} yet. Rip one:\n"
              f"    python {Path(__file__).name} rip /Volumes/YOUR_DISC "
              f'--label "Mum\'s birthday 1994"\n')
        return 0
    print()
    for m in discs:
        man = json.loads(m.read_text())
        dmg = f"  ⚠ {man['damaged_files']} damaged" if man.get("damaged_files") else ""
        print(f"  {man['disc_id']:28s} {man['label'][:34]:36s} "
              f"{_human(man['bytes']):>9s}{dmg}")
    print()
    return 0


# ------------------------------------------------------------------- audio
def extract_audio(library: Path, disc_id: str) -> int:
    """Pull the sound off, losslessly, into one file per video title.

    Her voice is the point. The video is a bonus.
    """
    if not shutil.which("ffmpeg"):
        print("\n  ffmpeg isn't installed. On a Mac:\n"
              "      brew install ffmpeg\n"
              "  (or download it from https://ffmpeg.org/download.html)\n")
        return 1
    root = Path(library).expanduser() / disc_id
    man_path = root / "disc.json"
    if not man_path.exists():
        print(f"\n  No disc called {disc_id}. Run `list` to see what's archived.\n")
        return 1
    # Beside the disc, never inside the verbatim copy — otherwise a hostile
    # disc carrying audio/VTS_01_1.flac pre-occupies the destination and its
    # file silently becomes "her voice".
    out = root.parent / f"{disc_id}.audio"
    out.mkdir(exist_ok=True)
    sources = [root / e["path"] for e in json.loads(man_path.read_text())["files"]
               if Path(e["path"]).suffix.lower() in VIDEO_EXT
               and Path(e["path"]).suffix.lower() not in (".ifo", ".bup")]
    if not sources:
        print("\n  No video files on this disc.\n")
        return 1
    print(f"\n  Extracting sound from {len(sources)} file(s)…\n")
    made = 0
    for src in sources:
        dst = out / (src.stem + ".flac")
        if dst.exists():
            print(f"  · {dst.name} already there — skipping (delete it to redo)")
            continue
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(src), "-vn", "-c:a", "flac", str(dst)],
            capture_output=True, text=True)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size:
            print(f"  ✓ {dst.name}  ({_human(dst.stat().st_size)})")
            made += 1
        else:
            print(f"  ! {src.name}: {r.stderr.strip()[:120]}")
    print(f"\n  {made} audio file(s) in {out}")
    print("  FLAC — lossless, so nothing is thrown away before transcription.\n")
    return 0


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    """Uses a folder shaped like a DVD, and a reader that fails on purpose."""
    import tempfile

    td = Path(tempfile.mkdtemp(prefix="disc-selftest-"))
    try:
        disc = td / "MUM_1994" / "VIDEO_TS"
        disc.mkdir(parents=True)
        (disc / "VIDEO_TS.IFO").write_bytes(b"IFO" * 100)
        (disc / "VTS_01_1.VOB").write_bytes(bytes(range(256)) * 900)   # 230400 B
        lib = td / "library"

        man = rip(disc.parent, lib, label="Mum's birthday 1994")
        assert man["damaged_files"] == 0, man
        assert len(man["files"]) == 2
        got = lib / man["disc_id"] / "VIDEO_TS" / "VTS_01_1.VOB"
        assert got.read_bytes() == (disc / "VTS_01_1.VOB").read_bytes(), "not verbatim"
        assert verify(lib) == 0

        # the archived copy is read-only — a later tool can't casually clobber it
        assert not (got.stat().st_mode & 0o222), "the original is writable"

        # a scratched disc: a reader that throws on one 64K chunk
        class Scratched:
            def __init__(self, p):
                self.f = open(p, "rb")
            def seek(self, n):
                self.pos = n
                return self.f.seek(n)
            def read(self, n):
                if self.pos == CHUNK:            # the second chunk is gone
                    raise OSError(5, "Input/output error")
                return self.f.read(n)
            def __enter__(self):
                return self
            def __exit__(self, *a):
                self.f.close()

        src = disc / "VTS_01_1.VOB"
        out = td / "recovered.VOB"
        info = copy_recovering(src, out, opener=Scratched)
        assert out.stat().st_size == src.stat().st_size, "length changed"
        assert info["unreadable"] == [[CHUNK, CHUNK * 2]], info["unreadable"]
        assert 0.70 < info["recovered"] < 0.73, info["recovered"]
        original = src.read_bytes()
        rescued = out.read_bytes()
        assert rescued[:CHUNK] == original[:CHUNK], "good data before the scratch lost"
        assert rescued[CHUNK * 2:] == original[CHUNK * 2:], "data AFTER the scratch lost"
        assert rescued[CHUNK:CHUNK * 2] == b"\0" * CHUNK

        # tampering is caught years later
        got.chmod(0o644)
        got.write_bytes(b"different")
        assert verify(lib) == 1, "a changed file was not detected"

        print("  ✓ disc archive: verbatim copy, manifest + checksums, originals")
        print("    made read-only, tampering detected, and a scratched disc still")
        print("    yields everything on both sides of the damage\n")
        return 0
    finally:
        for p in td.rglob("*"):
            if p.is_file():
                try:
                    p.chmod(0o644)
                except OSError:
                    pass
        shutil.rmtree(td, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--library", default=DEFAULT_LIBRARY)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("rip", help="copy a disc into the library, verbatim")
    r.add_argument("source", help="the mounted disc, e.g. /Volumes/MUM_1994")
    r.add_argument("--label", default="", help='e.g. "Mum\'s birthday 1994"')
    r.add_argument("--when", default="", help="when it was RECORDED, if known")

    sub.add_parser("list", help="what has been archived")
    sub.add_parser("verify", help="does every archived copy still read true")

    a_ = sub.add_parser("audio", help="extract the sound, losslessly")
    a_.add_argument("disc_id")

    sub.add_parser("selftest", help="prove it works, no disc needed")

    a = ap.parse_args()
    if a.cmd == "rip":
        rip(Path(a.source), Path(a.library), a.label, a.when)
        return 0
    if a.cmd == "list":
        return listing(Path(a.library))
    if a.cmd == "verify":
        return verify(Path(a.library))
    if a.cmd == "audio":
        return extract_audio(Path(a.library), a.disc_id)
    return selftest()


if __name__ == "__main__":
    sys.exit(main())
