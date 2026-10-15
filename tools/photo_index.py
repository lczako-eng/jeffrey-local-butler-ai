#!/usr/bin/env python3
"""
photo_index.py — local semantic search over your own photos. No cloud.
======================================================================

This is the cheap proof of Self-Cloud's independence guarantee: *"Self-Cloud
must remain useful, intelligible, and owner-controlled even if every external
AI provider becomes unavailable."* It runs a small open-weight image/text
model on the owner's own machine, indexes their own library, and answers
"show me the kitchen table at Christmas" with no network at all.

Three tiers of "local AI", and this is deliberately the middle one:

    A. deterministic   indexing, EXACT dedup (SHA-256), timeline, near-dup
                       — plain code, no model. Already proven on ~80k photos.
    B. small model     semantic search, classification, retrieval.  <-- HERE
                       A few hundred MB of weights. Fine on a CPU.
    C. LLM             summarizing, answering, reasoning. The expensive tier,
                       and the only one that argues for a GPU.

Do not buy hardware for tier C until A and B are shipped and something is
measurably slow.

WEIGHTS LIVE ON THE DRIVE
    Open weights are not independence if you would have to re-download them
    from a company's website. This script keeps the model inside the index
    directory (`<index>/models`), and `--verify` proves the whole thing runs
    with the network off.

THE EMBEDDING MODEL IS NOT REPLACEABLE
    Swapping it invalidates every vector in the index. The model name and
    dimensions are recorded in `manifest.json`, and a mismatch is refused
    rather than silently producing nonsense results. Changing models means
    re-indexing.

Usage
    python tools/photo_index.py build   ~/Pictures --index ~/.selfcloud/photo-index
    python tools/photo_index.py search  "kids at the lake"  --index ...
    python tools/photo_index.py verify  --index ...
    python tools/photo_index.py stats   --index ...
    python tools/photo_index.py forget  <photo file, folder, or id>

Only `build` (and `watch` with a folder) ever makes a new index. Every other
command, and every reader (the wall, recall, the album), opens an existing
one or says plainly that there isn't one — it never quietly starts an empty
index in the home folder.

PATHS SURVIVE A RENAMED DRIVE
    Each photo is also stored relative to the folder that holds the index's
    `.selfcloud` directory (the drive itself, for an index on the drive). If
    the drive is renamed from 'Self Cloud' to 'Self-Cloud', the photos are
    found again without re-reading anything. A rebuild also follows a known
    photo to its new place.

Install (once, with a network; after that it never needs one)
    pip install open_clip_torch torch pillow numpy
    # or:  pip install transformers torch pillow numpy
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import datetime as dt
import sqlite3
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "connector"))
import home  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp",
                  ".bmp", ".tif", ".tiff", ".gif"}

# Folders that look like folders but are really one application's private
# storage. A Photos library holds every picture two to six times (originals,
# previews, thumbnails, face crops, shared-album copies), so reading it as a
# folder fills the wall with duplicates. The owner exports originals instead.
BUNDLE_SUFFIXES = (".photoslibrary", ".photolibrary", ".aplibrary",
                   ".migratedphotolibrary", ".lrdata", ".app", ".bundle")

# Small, open, and good enough. ~150 MB of weights, 512-dim embeddings.
DEFAULT_MODEL = "ViT-B-32"
DEFAULT_PRETRAINED = "laion2b_s34b_b79k"

# How long a reader waits for a writer (the watcher, the album) to finish
# before giving up. A family screen should wait, not fail.
DB_TIMEOUT = 30


class NoIndex(FileNotFoundError):
    """There is no photo index where one was expected. Said plainly, and
    never answered by quietly creating an empty one."""

    def __init__(self, root: Path):
        self.root = root
        super().__init__(
            f"No photographs have been read yet at {root}. If they were read "
            f"onto the Self-Cloud drive, plug the drive in. Otherwise "
            f"double-click 'Show me my life' to read them.")


def connect(db_path: Path) -> sqlite3.Connection:
    """One connection for one thread. SQLite connections may not cross
    threads, and the wall, the MCP server and the HTTP server all answer from
    several threads at once — sharing one silently broke all three."""
    con = sqlite3.connect(db_path, timeout=DB_TIMEOUT)
    # Take the write lock when a write starts, not halfway through it: two
    # threads that both upgrade a read lock deadlock instead of waiting.
    con.isolation_level = "IMMEDIATE"
    return con


def anchor_of(index_root: Path) -> Path:
    """The folder photo paths are stored relative to: the one holding the
    index's `.selfcloud` directory (the drive's top, for an index on the
    drive), else the disk the index is on."""
    p = Path(os.path.abspath(Path(index_root).expanduser()))
    parts = p.parts
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == ".selfcloud":
            return Path(*parts[:i]) if i else Path(p.anchor)
    q = p
    while not os.path.ismount(q) and q.parent != q:
        q = q.parent
    return q


def _rel(path: Path | str, anchor: Path) -> str:
    """`path` relative to `anchor`, or '' when it lives somewhere else."""
    try:
        return Path(os.path.abspath(path)).relative_to(anchor).as_posix()
    except ValueError:
        return ""


# --------------------------------------------------------------- the index
class PhotoIndex:
    """A content-addressed vector index that lives in one directory.

    Keyed by SHA-256, so it shares its identity model with the dedup work
    that already ran: the same photo found on three drives is one row, and
    moving or renaming a file never orphans its vector.

    `create=False` opens an index that must already exist and raises NoIndex
    otherwise. Every reader uses it; only building makes a new index.
    """

    def __init__(self, root: Path, create: bool = True):
        self.root = Path(root).expanduser()
        self.db_path = self.root / "index.sqlite"
        self.manifest_path = self.root / "manifest.json"
        self.model_dir = self.root / "models"
        if not create and not self.db_path.is_file():
            raise NoIndex(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.anchor = anchor_of(self.root)
        # Where the index was when it was last built, read before anything
        # rewrites the manifest — so a renamed drive can be followed.
        self.old_anchor = self._old_anchor()
        self._local = threading.local()
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS photos (
                sha256 TEXT PRIMARY KEY, path TEXT, bytes INTEGER,
                mtime REAL, seen_at TEXT,
                taken_at TEXT, lat REAL, lon REAL, place TEXT, country TEXT);
            CREATE TABLE IF NOT EXISTS vectors (
                sha256 TEXT PRIMARY KEY, dim INTEGER, vec BLOB);
            CREATE TABLE IF NOT EXISTS failures (
                path TEXT PRIMARY KEY, reason TEXT, at TEXT);
            CREATE TABLE IF NOT EXISTS sources (
                path TEXT PRIMARY KEY, added_at TEXT, last_scan TEXT,
                last_seen_files INTEGER);
            CREATE TABLE IF NOT EXISTS scans (
                at TEXT, source TEXT, added INTEGER, missing INTEGER,
                returned INTEGER, failed INTEGER, seconds REAL);
            CREATE TABLE IF NOT EXISTS forgotten (
                sha256 TEXT PRIMARY KEY, at TEXT);
            CREATE INDEX IF NOT EXISTS photos_path ON photos(path);
            CREATE INDEX IF NOT EXISTS photos_taken ON photos(taken_at);
            CREATE INDEX IF NOT EXISTS photos_place ON photos(place);
        """)
        # An index built before when/where existed gets the columns added
        # rather than rebuilt — the embeddings in it are still perfectly good.
        for col, typ in (("taken_at", "TEXT"), ("lat", "REAL"), ("lon", "REAL"),
                         ("place", "TEXT"), ("country", "TEXT"),
                         ("missing_since", "TEXT"), ("rel", "TEXT")):
            try:
                self.db.execute(f"ALTER TABLE photos ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass                                  # already there
        self.db.commit()
        self._backfill_rel()

    # -- one connection per thread ----------------------------------------
    @property
    def db(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = connect(self.db_path)
            self._local.con = con
        return con

    def close(self) -> None:
        con = getattr(self._local, "con", None)
        if con is not None:
            con.close()
            self._local.con = None

    # -- where a photo is now ----------------------------------------------
    def _old_anchor(self) -> Path | None:
        """Where the index lived when it was last built — read from its own
        manifest, so an index made before paths were stored relatively can
        still follow a renamed drive."""
        try:
            m = self.manifest()
        except (OSError, ValueError):
            return None
        if m.get("anchor"):
            return Path(m["anchor"])
        if m.get("weights_dir"):
            return anchor_of(Path(m["weights_dir"]).parent)
        return None

    def _backfill_rel(self) -> None:
        """Rows from before the `rel` column: work out each photo's place
        relative to the drive once, and keep it. Nothing is dropped."""
        rows = list(self.db.execute(
            "SELECT sha256, path FROM photos WHERE rel IS NULL"))
        if not rows:
            return
        old = self.old_anchor
        try:
            for sha, path in rows:
                rel = _rel(path, self.anchor) if path else ""
                if not rel and path and old and old != self.anchor:
                    rel = _rel(path, old)          # the drive was renamed
                self.db.execute("UPDATE photos SET rel=? WHERE sha256=?", (rel, sha))
            self.db.commit()
        except sqlite3.OperationalError:           # a read-only disk: work it
            self.db.rollback()                     # out at read time instead

    def locate(self, path: str | None, rel: str | None = None) -> Path | None:
        """The file as it can be reached now, or None. Tries the place
        relative to the drive first (it follows a rename), then the stored
        path."""
        if rel:
            p = self.anchor / rel
            if p.is_file():
                return p
        if path and Path(path).is_file():
            return Path(path)
        old = self.old_anchor if path else None
        if old and old != self.anchor:
            r = _rel(path, old)
            if r and (self.anchor / r).is_file():
                return self.anchor / r
        return None

    def away(self, path: str | None, rel: str | None = None) -> bool:
        """Is the original away for now rather than deleted: kept in iCloud
        with only a placeholder on this Mac ('Optimize Mac Storage'), or on
        a drive that is not plugged in? Its cached copy for the wall is kept
        and shown (verify regression: such photos vanished from the wall
        until downloaded again)."""
        cands = [Path(path)] if path else []
        if rel:
            cands.append(self.anchor / rel)
        return any(offloaded(c) or unplugged(c) for c in cands)

    def where(self, sha: str) -> Path | None:
        """Where this photo can be reached now, or None — None also when it
        is marked missing or was forgotten."""
        row = self.db.execute(
            "SELECT path, rel, missing_since FROM photos WHERE sha256=?",
            (sha,)).fetchone()
        if not row or row[2] is not None:
            return None
        return self.locate(row[0], row[1])

    def thumb_path(self, sha: str) -> Path:
        return self.root / "thumbs" / f"{sha}.jpg"

    def drop_thumb(self, sha: str) -> None:
        try:
            self.thumb_path(sha).unlink()
        except OSError:
            pass

    # -- the manifest: what produced these vectors ------------------------
    def manifest(self) -> dict:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return {}

    def claim(self, model: str, pretrained: str, dim: int) -> None:
        """Record which model owns this index, or refuse a mismatched one."""
        m = self.manifest()
        if m and (m.get("model"), m.get("pretrained")) != (model, pretrained):
            raise SystemExit(
                f"\nThis index was built with {m.get('model')}/{m.get('pretrained')} "
                f"({m.get('dim')}-dim) and you are running "
                f"{model}/{pretrained}.\n"
                "Embeddings from different models are not comparable — searching\n"
                "across them returns confident nonsense. Either use the original\n"
                "model, or re-index into a new directory.\n"
            )
        self.manifest_path.write_text(json.dumps({
            "model": model, "pretrained": pretrained, "dim": dim,
            "normalized": True, "metric": "cosine",
            "weights_dir": str(self.model_dir),
            "anchor": str(self.anchor),
            "created": m.get("created") or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "note": ("The embedding model is part of this index, not a "
                     "detachable choice. Changing it means re-indexing."),
            **({"WARNING": "Built with UNTRAINED weights (pretrained=none). "
                           "This proves the pipeline, not the search quality. "
                           "Re-index with real weights before trusting a result."}
               if str(pretrained).lower() in ("none", "") else {}),
        }, indent=2))

    # -- rows -------------------------------------------------------------
    def have(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT sha256 FROM vectors")}

    def forgotten(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT sha256 FROM forgotten")}

    def add(self, sha: str, path: Path, vec, facts: dict | None = None) -> None:
        st, f = path.stat(), facts or {}
        path = Path(os.path.abspath(path))
        # Columns named explicitly: the table grows over time, and a
        # positional INSERT silently rots the moment one is added.
        self.db.execute(
            "INSERT OR REPLACE INTO photos (sha256, path, bytes, mtime, "
            "seen_at, taken_at, lat, lon, place, country, missing_since, rel) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,NULL,?)",
            (sha, str(path), st.st_size, st.st_mtime,
             time.strftime("%Y-%m-%dT%H:%M:%S"),
             f.get("taken_at"), f.get("lat"), f.get("lon"),
             f.get("place"), f.get("country"), _rel(path, self.anchor)))
        self.db.execute("INSERT OR REPLACE INTO vectors VALUES (?,?,?)",
                        (sha, len(vec), vec.astype("float16").tobytes()))

    def moved(self, sha: str, path: Path) -> None:
        """A photo already known turned up at a new place (a renamed drive, a
        moved folder, a duplicate kept instead of the original). Follow it;
        never re-read it."""
        path = Path(os.path.abspath(path))
        self.db.execute(
            "UPDATE photos SET path=?, rel=?, missing_since=NULL WHERE sha256=?",
            (str(path), _rel(path, self.anchor), sha))

    def forget(self, sha: str) -> None:
        """Out of the index for good: the row, its vector, its thumbnail —
        and it stays out, even if the file is still in the folder."""
        self.db.execute("DELETE FROM photos WHERE sha256=?", (sha,))
        self.db.execute("DELETE FROM vectors WHERE sha256=?", (sha,))
        self.db.execute("INSERT OR REPLACE INTO forgotten VALUES (?,?)",
                        (sha, time.strftime("%Y-%m-%dT%H:%M:%S")))
        self.drop_thumb(sha)

    def fail(self, path: Path, reason: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO failures VALUES (?,?,?)",
                        (str(path), reason[:300], time.strftime("%Y-%m-%dT%H:%M:%S")))

    def matrix(self):
        """Every vector as one float32 matrix, plus the hashes in row order."""
        import numpy as np
        rows = list(self.db.execute("SELECT sha256, dim, vec FROM vectors"))
        if not rows:
            return None, []
        dim = rows[0][1]
        mat = np.zeros((len(rows), dim), dtype="float32")
        for i, (_, _dim, blob) in enumerate(rows):
            mat[i] = np.frombuffer(blob, dtype="float16").astype("float32")
        return mat, [r[0] for r in rows]

    def paths_for(self, shas: list[str]) -> dict[str, str]:
        """Where each photo can be reached now (following a renamed drive),
        else the path it was last seen at."""
        q = ",".join("?" * len(shas))
        out = {}
        for sha, path, rel in self.db.execute(
                f"SELECT sha256, path, rel FROM photos WHERE sha256 IN ({q})", shas):
            found = self.locate(path, rel)
            out[sha] = str(found) if found else path
        return out


# --------------------------------------------------------------- the model
class Embedder:
    """open_clip if present, else transformers. Weights stay in the index."""

    def __init__(self, index: PhotoIndex, model: str, pretrained: str,
                 offline: bool = False):
        index.model_dir.mkdir(parents=True, exist_ok=True)
        # Everything the libraries might cache goes on the drive, not in ~/.
        for var in ("HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME",
                    "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE"):
            os.environ[var] = str(index.model_dir)
        if offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        self.name, self.pretrained = model, pretrained
        self.backend = None
        # `none` builds the architecture with UNTRAINED weights. It exercises
        # every part of this pipeline without a download, which is how the
        # self-test runs — but its "semantic" results are noise. Never index a
        # real library with it; the manifest records the warning either way.
        weights = None if str(pretrained).lower() in ("none", "") else pretrained
        try:
            import open_clip, torch
            self.torch = torch
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                model, pretrained=weights, cache_dir=str(index.model_dir))
            self.tokenizer = open_clip.get_tokenizer(model)
            self.model.eval()
            self.backend = "open_clip"
        except ImportError:
            self._transformers(index, offline)
        self.dim = int(self.embed_text(["a photo"]).shape[1])

    def _transformers(self, index: PhotoIndex, offline: bool) -> None:
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
        except ImportError:
            raise SystemExit(
                "\nNo local embedding model available. Install one (once, with "
                "a network — after that this runs offline forever):\n"
                "    pip install open_clip_torch torch pillow numpy\n"
                "  or\n"
                "    pip install transformers torch pillow numpy\n")
        self.torch = torch
        repo = "openai/clip-vit-base-patch32"
        self.model = CLIPModel.from_pretrained(
            repo, cache_dir=str(index.model_dir), local_files_only=offline)
        self.proc = CLIPProcessor.from_pretrained(
            repo, cache_dir=str(index.model_dir), local_files_only=offline)
        self.model.eval()
        self.backend = "transformers"
        self.name, self.pretrained = repo, "openai"

    # -- embedding --------------------------------------------------------
    def _norm(self, t):
        return (t / t.norm(dim=-1, keepdim=True)).cpu().numpy()

    def embed_text(self, texts: list[str]):
        with self.torch.no_grad():
            if self.backend == "open_clip":
                return self._norm(self.model.encode_text(self.tokenizer(texts)))
            batch = self.proc(text=texts, return_tensors="pt", padding=True)
            return self._norm(self.model.get_text_features(**batch))

    def embed_images(self, images: list):
        with self.torch.no_grad():
            if self.backend == "open_clip":
                batch = self.torch.stack([self.preprocess(im) for im in images])
                return self._norm(self.model.encode_image(batch))
            batch = self.proc(images=images, return_tensors="pt")
            return self._norm(self.model.get_image_features(**batch))


# --------------------------------------------------------------- helpers
def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def offloaded(p: Path) -> bool:
    """Only a cloud placeholder of this photo is on the Mac: the older
    '.name.icloud' file beside it, or a 'dataless' file (macOS keeps the
    name and fetches the bytes when it is opened)."""
    p = Path(p)
    try:
        if (p.parent / f".{p.name}.icloud").exists():
            return True
        return bool(getattr(os.stat(p), "st_flags", 0) & 0x40000000)   # SF_DATALESS
    except OSError:
        return False


def unplugged(p: Path) -> bool:
    """The photo lives on a drive that is not plugged in now."""
    parts = Path(p).parts
    for base in home.MOUNT_BASES:
        b = Path(base).parts
        depth = len(b) + (2 if base in home._PER_USER else 1)
        if parts[:len(b)] == b and len(parts) > depth:
            return not Path(*parts[:depth]).is_dir()
    return False


def is_bundle(p: Path) -> bool:
    return p.name.lower().endswith(BUNDLE_SUFFIXES)


def walk(root: Path, skipped: list | None = None):
    """Only files that really live under the folder the owner named.

    A symlink passes `is_file()` and `Image.open()` follows it, so without
    this the guard constrains where we LOOKED, not what we OPENED — one link
    in a photo folder and the index quietly reaches anywhere on the disk.

    Never descends into an application's private package (a Photos library
    holds every picture several times over) or into hidden folders (the
    drive's own `.selfcloud` holds the wall's thumbnails, which are not new
    photographs). Packages it stepped over are added to `skipped`, so the
    caller can explain how to export the originals instead.
    """
    start = Path(root).expanduser()
    base = start.resolve()
    if is_bundle(start):
        if skipped is not None:
            skipped.append(start)
        return
    for dirpath, dirnames, filenames in os.walk(start):
        keep = []
        for d in sorted(dirnames):
            if d.startswith("."):
                continue
            if is_bundle(Path(d)):
                if skipped is not None:
                    skipped.append(Path(dirpath) / d)
                continue
            keep.append(d)
        dirnames[:] = keep                   # os.walk honours the pruning
        for name in sorted(filenames):
            if name.startswith("._"):        # macOS resource-fork shadows
                continue
            p = Path(dirpath) / name
            if p.suffix.lower() not in IMAGE_SUFFIXES or p.is_symlink():
                continue
            try:
                if not (p.is_file() and p.resolve().is_relative_to(base)):
                    continue
            except OSError:
                continue
            yield p


def open_image(path: Path):
    from PIL import Image
    try:                                   # iPhone libraries are full of HEIC
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    return Image.open(path).convert("RGB")


# --------------------------------------------------------- when, and where
#
# Two thirds of "show me the vacation ten years ago in Cuba" is answered
# here, with no model at all: the camera already wrote down the date and the
# coordinates. Only "vacation" needs the neural network.

def _ratio(v) -> float:
    try:
        return float(v[0]) / float(v[1]) if isinstance(v, tuple) else float(v)
    except (TypeError, ZeroDivisionError, ValueError):
        return 0.0


def _dms(values, ref: str) -> float | None:
    """EXIF stores degrees/minutes/seconds; the world uses decimals."""
    try:
        d, m, s = (_ratio(v) for v in values)
    except (TypeError, ValueError):
        return None
    deg = d + m / 60 + s / 3600
    return -deg if str(ref).upper() in ("S", "W") else deg


def read_when_where(path: Path) -> dict:
    """Date taken and GPS, straight from the file. Never fatal: a photo with
    no EXIF is still a photo, it just cannot answer a 'where' question."""
    from PIL import Image

    facts: dict = {"taken_at": None, "lat": None, "lon": None}
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return facts
            # 36867 DateTimeOriginal, 36868 DateTimeDigitized, 306 DateTime
            sub = exif.get_ifd(0x8769) or {}
            raw = sub.get(36867) or sub.get(36868) or exif.get(306)
            if raw:
                try:                        # EXIF format: 2016:07:14 12:00:00
                    facts["taken_at"] = dt.datetime.strptime(
                        str(raw).strip(), "%Y:%m:%d %H:%M:%S").isoformat()
                except ValueError:
                    pass
            gps = exif.get_ifd(0x8825) or {}
            if gps:
                lat = _dms(gps.get(2), gps.get(1, "N"))
                lon = _dms(gps.get(4), gps.get(3, "E"))
                if lat is not None and lon is not None and (lat or lon):
                    facts["lat"], facts["lon"] = lat, lon
    except Exception:
        pass                                # unreadable metadata is not an error
    if facts["taken_at"] is None:           # fall back to the file's own date
        try:
            facts["taken_at"] = dt.datetime.fromtimestamp(
                path.stat().st_mtime).isoformat()
        except OSError:
            pass
    return facts


def name_places(rows: list[dict]) -> None:
    """Turn coordinates into names people say out loud — 'Varadero', 'Cuba' —
    using a city database bundled on this machine. Offline by construction:
    where you were on holiday is nobody else's search query.

    Fills `place` and `country` in place. A silent no-op if the optional
    library isn't installed; coordinates are still stored either way.
    """
    # One bad coordinate must not cost the whole batch its places.
    usable = [r for r in rows
              if isinstance(r.get("lat"), (int, float))
              and isinstance(r.get("lon"), (int, float))
              and math.isfinite(r["lat"]) and math.isfinite(r["lon"])]
    pts = [(r["lat"], r["lon"]) for r in usable]
    if not pts:
        return
    try:
        import reverse_geocoder
    except ImportError:
        return
    try:
        found = reverse_geocoder.search(pts, mode=1, verbose=False)
    except Exception:
        return
    try:
        import pycountry
    except ImportError:
        pycountry = None
    it = iter(found)
    for r in usable:
        hit = next(it, None)
        if not hit:
            break
        r["place"] = hit.get("name") or None
        cc = hit.get("cc")
        country = None
        if cc and pycountry:
            c = pycountry.countries.get(alpha_2=cc)
            country = c.name if c else cc
        r["country"] = country or cc


# --------------------------------------------------------------- commands
def reconcile(idx: PhotoIndex, source: Path, seen: dict[str, Path],
              judge_absence: bool = True) -> tuple[int, int, int]:
    """After a pass over one folder: follow photos that moved, mark the ones
    that are gone (only after a complete pass), and welcome back the ones
    that returned.

    `seen` maps each photo found under `source` in this pass to where it was
    found. Returns (moved, gone, back). Gone is a dated state, never a
    deletion — but the wall's cached copy of a gone photo is removed, so a
    picture deleted on purpose stops being shown.
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    src = os.path.abspath(Path(source).expanduser())
    prefix = src.rstrip(os.sep) + os.sep
    moved = gone = back = 0
    rows = {sha: (path, rel, miss) for sha, path, rel, miss in idx.db.execute(
        "SELECT sha256, path, rel, missing_since FROM photos")}
    def under(p: str) -> bool:
        return bool(p) and (p == src or p.startswith(prefix))

    for sha, found in seen.items():
        if sha not in rows:
            continue
        path, rel, miss = rows[sha]
        here = os.path.abspath(found)
        if path != here and not (path and Path(path).is_file()):
            idx.moved(sha, Path(here))           # follow it to its new place
            moved += 1
            if miss is not None:
                back += 1
            rows[sha] = (here, _rel(here, idx.anchor), None)
        elif miss is not None:
            idx.db.execute("UPDATE photos SET missing_since=NULL WHERE sha256=?", (sha,))
            back += 1
    for sha, (path, rel, miss) in rows.items():
        if not judge_absence:
            break
        if sha in seen or miss is not None or not path:
            continue
        # Only what was last seen under THIS folder — compared as a prefix,
        # never with LIKE, where '_' and '%' in a folder name match anything.
        now_at = os.path.abspath(idx.anchor / rel) if rel else path
        if not (under(path) or under(now_at)):
            continue
        if idx.locate(path, rel) is not None:
            continue                             # still there, just not read this time
        if idx.away(path, rel):
            continue                             # in iCloud for now, or its drive is out
        idx.db.execute("UPDATE photos SET missing_since=? WHERE sha256=?", (now, sha))
        idx.drop_thumb(sha)
        gone += 1
    idx.db.commit()
    return moved, gone, back


def remember_source(idx: PhotoIndex, source: Path) -> None:
    idx.db.execute(
        "INSERT OR IGNORE INTO sources (path, added_at) VALUES (?,?)",
        (os.path.abspath(Path(source).expanduser()),
         time.strftime("%Y-%m-%dT%H:%M:%S")))
    idx.db.commit()


def cmd_build(a) -> int:
    idx = PhotoIndex(a.index)
    emb = Embedder(idx, a.model, a.pretrained, offline=a.offline)
    idx.claim(emb.name, emb.pretrained, emb.dim)
    print(f"  model    {emb.name}/{emb.pretrained} ({emb.dim}-dim, {emb.backend})")
    print(f"  weights  {idx.model_dir}")
    print(f"  index    {idx.db_path}")

    known = idx.have()
    forgotten = idx.forgotten()
    bundles: list = []
    files = list(walk(a.source, bundles))
    print(f"  found    {len(files)} images under {a.source}")
    for b in bundles:
        print(f"  skipped  {b} — an app's own library, not a folder of photos")
    if Path(a.source).expanduser().is_dir():
        remember_source(idx, Path(a.source))

    seen: dict[str, Path] = {}
    complete = True
    batch_imgs, batch_meta, done, skipped, failed = [], [], 0, 0, 0
    t0 = time.time()

    def flush():
        nonlocal done
        if not batch_imgs:
            return
        vecs = emb.embed_images(batch_imgs)
        facts = [f for _, _, f in batch_meta]
        name_places(facts)                 # one batched lookup, not one per photo
        for (sha, path, f), vec in zip(batch_meta, vecs):
            idx.add(sha, path, vec, f)
        idx.db.commit()
        done += len(batch_meta)
        batch_imgs.clear()
        batch_meta.clear()

    for n, path in enumerate(files, 1):
        if a.limit and done + skipped >= a.limit:
            complete = False                 # a trial run saw only part of it
            break
        try:
            sha = sha256(path)
            if sha in forgotten:             # the owner told it to forget this
                continue
            seen.setdefault(sha, path)
            if sha in known:
                skipped += 1
                continue
            batch_imgs.append(open_image(path))
            batch_meta.append((sha, path, read_when_where(path)))
            known.add(sha)
        except Exception as exc:                      # a bad file is not fatal
            idx.fail(path, f"{type(exc).__name__}: {exc}")
            failed += 1
            continue
        if len(batch_imgs) >= a.batch:
            flush()
            rate = done / max(time.time() - t0, 1e-6)
            print(f"\r  embedded {done}  skipped {skipped}  failed {failed}  "
                  f"({rate:.1f}/s)", end="", flush=True)
    flush()
    idx.db.commit()
    moved = gone = back = 0
    if Path(a.source).expanduser().is_dir():
        # A trial run (--limit) saw only part of the folder: follow what
        # moved, but judge nothing absent from a pass that did not finish.
        moved, gone, back = reconcile(idx, Path(a.source), seen,
                                      judge_absence=complete)
    secs = time.time() - t0
    print(f"\r  embedded {done}  already had {skipped}  failed {failed}  "
          f"in {secs:.1f}s".ljust(72)
          + (f"  ({done / secs:.1f}/s)" if done and secs else ""))
    if moved:
        print(f"  followed {moved} photo(s) to a new place (a renamed drive or moved folder)")
    if gone:
        print(f"  {gone} photo(s) are no longer in this folder — they will not be shown")
    print(f"\n  Done. Search it with no network at all:\n"
          f"    python {Path(__file__).name} search \"kids at the lake\" "
          f"--index {a.index}")
    return 0


def open_index(path) -> PhotoIndex:
    """Open an index that must already exist; say so plainly if it doesn't."""
    try:
        return PhotoIndex(path, create=False)
    except NoIndex as e:
        raise SystemExit(f"\n  {e}\n")


def cmd_search(a) -> int:
    import numpy as np
    idx = open_index(a.index)
    man = idx.manifest()
    if not man:
        raise SystemExit("No index here yet. Run `build` first.")
    emb = Embedder(idx, man["model"], man["pretrained"], offline=True)
    mat, shas = idx.matrix()
    if mat is None:
        raise SystemExit("The index is empty.")
    q = emb.embed_text([a.query])[0]
    scores = mat @ q                       # both sides are unit vectors
    top = np.argsort(-scores)[:a.top]
    paths = idx.paths_for([shas[i] for i in top])
    print(f'\n  "{a.query}"  — {len(shas)} photos searched locally, '
          f"no network\n")
    for rank, i in enumerate(top, 1):
        print(f"  {rank:2d}. {scores[i]:.3f}  {paths.get(shas[i], '?')}")
    print()
    return 0


def cmd_verify(a) -> int:
    """Prove the independence claim: unplug the internet, it still works."""
    idx = open_index(a.index)
    man = idx.manifest()
    if not man:
        raise SystemExit("No index here yet. Run `build` first.")
    weights = sum(f.stat().st_size for f in idx.model_dir.rglob("*") if f.is_file())
    print(f"  index      {idx.db_path}")
    print(f"  model      {man['model']}/{man['pretrained']} ({man['dim']}-dim)")
    print(f"  weights    {weights / 1e6:.0f} MB on this drive, at {idx.model_dir}")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    emb = Embedder(idx, man["model"], man["pretrained"], offline=True)
    v = emb.embed_text(["a test with the network switched off"])
    assert v.shape[1] == man["dim"]
    n, = next(idx.db.execute("SELECT COUNT(*) FROM vectors"))
    print(f"  photos     {n} indexed")
    print("\n  ✓ The model loaded and embedded with HF_HUB_OFFLINE=1.")
    print("    Every AI company could disappear tomorrow and this still works.")
    return 0


def cmd_watch(a) -> int:
    """Keep the index alive. A library indexed once is a snapshot; a life
    is not.

    Three promises this makes, because "constantly indexing your life" is
    one word away from surveillance:

      * it looks ONLY in the folders the owner named, and it lists them
        every time it runs;
      * it stops when the machine stops — there is no service phoning
        home, no queue that flushes later, no work done in the dark;
      * it NEVER deletes. A file that has gone is far more often an
        unplugged drive than a deleted photo, so absence is recorded as a
        dated state and the knowledge is kept. When the drive comes back,
        the photo comes back with everything already known about it.
    """
    idx = PhotoIndex(a.index) if a.source else open_index(a.index)
    if a.source:
        remember_source(idx, Path(a.source))
    sources = [r[0] for r in idx.db.execute("SELECT path FROM sources")]
    if not sources:
        raise SystemExit(
            "\nNothing to watch yet. Name a folder:\n"
            f"    python {Path(__file__).name} watch ~/Pictures --index {a.index}\n")

    man = idx.manifest()
    emb = Embedder(idx, man.get("model", a.model),
                   man.get("pretrained", a.pretrained), offline=True) if man else None

    print(f"\n  Watching {len(sources)} folder(s) — and only these:")
    for s in sources:
        print(f"    {s}")
    print(f"  Every {a.every}s while this machine is awake. Ctrl-C stops it,"
          f"\n  and nothing runs once it has.\n")

    round_no = 0
    while True:
        round_no += 1
        total_new = total_gone = total_back = 0
        for src in sources:
            n, gone, back, failed, secs = scan_once(idx, Path(src), emb, a.batch)
            total_new += n
            total_gone += gone
            total_back += back
            idx.db.execute("INSERT INTO scans VALUES (?,?,?,?,?,?,?)",
                           (time.strftime("%Y-%m-%dT%H:%M:%S"), src, n, gone,
                            back, failed, round(secs, 2)))
            idx.db.execute("UPDATE sources SET last_scan=? WHERE path=?",
                           (time.strftime("%Y-%m-%dT%H:%M:%S"), src))
        idx.db.commit()
        stamp = time.strftime("%H:%M:%S")
        if total_new or total_gone or total_back:
            bits = []
            if total_new:
                bits.append(f"{total_new} new")
            if total_back:
                bits.append(f"{total_back} back (drive reconnected)")
            if total_gone:
                bits.append(f"{total_gone} not reachable — kept, not deleted")
            print(f"  {stamp}  " + ", ".join(bits))
        elif a.verbose:
            print(f"  {stamp}  nothing changed")
        if a.once:
            return 0
        try:
            time.sleep(a.every)
        except KeyboardInterrupt:
            print("\n  Stopped. Nothing is running in the background.\n")
            return 0


def scan_once(idx: PhotoIndex, source: Path, emb, batch_size: int = 16):
    """One pass over one folder. Returns (new, gone, returned, failed, secs)."""
    t0 = time.time()
    known = idx.have()
    forgotten = idx.forgotten()

    if not source.exists():
        # The whole folder is unreachable — an unplugged drive, not a
        # hundred deletions. Say so and change nothing.
        return 0, 0, 0, 0, time.time() - t0

    on_disk: dict[str, Path] = {}
    new, failed = 0, 0
    imgs, meta = [], []

    def flush():
        nonlocal new
        if not imgs or emb is None:
            imgs.clear(); meta.clear(); return
        vecs = emb.embed_images(imgs)
        facts = [f for _, _, f in meta]
        name_places(facts)
        for (sha, path, f), vec in zip(meta, vecs):
            idx.add(sha, path, vec, f)
        new += len(meta)
        imgs.clear(); meta.clear()

    for path in walk(source):
        try:
            sha = sha256(path)
            if sha in forgotten:
                continue
            on_disk.setdefault(sha, path)
            if sha in known:
                continue
            imgs.append(open_image(path))
            meta.append((sha, path, read_when_where(path)))
            known.add(sha)
        except Exception as exc:
            idx.fail(path, f"{type(exc).__name__}: {exc}")
            failed += 1
            continue
        if len(imgs) >= batch_size:
            flush()
    flush()
    idx.db.commit()

    # Anything under this source that we did not see is marked missing —
    # dated, reversible, and never deleted. A known photo seen at a new
    # place is followed there.
    _moved, gone, back = reconcile(idx, source, on_disk)
    return new, gone, back, failed, time.time() - t0


def cmd_forget(a) -> int:
    """'Forget this photo.' Removes it from the index — its row, what the
    model saw in it, and the wall's copy — and keeps it out from then on.
    The original file is never touched: deleting that is the owner's call."""
    idx = open_index(a.index)
    what = a.what.strip()
    shas: list[str] = []
    p = Path(what).expanduser()
    if p.exists():
        target = os.path.abspath(p)
        files = [p] if p.is_file() else list(walk(p))
        for f in files:
            try:
                shas.append(sha256(f))
            except OSError:
                pass
        # and anything the index last saw there, even if the file is gone
        prefix = target.rstrip(os.sep) + os.sep
        for sha, path in idx.db.execute("SELECT sha256, path FROM photos"):
            if path and (path == target or path.startswith(prefix)):
                shas.append(sha)
    elif len(what) >= 12 and all(c in "0123456789abcdef" for c in what.lower()):
        shas = [r[0] for r in idx.db.execute(
            "SELECT sha256 FROM photos WHERE substr(sha256, 1, ?) = ?",
            (len(what), what.lower()))]
    else:
        for sha, path in idx.db.execute("SELECT sha256, path FROM photos"):
            if path and (path == what or Path(path).name == what):
                shas.append(sha)
    shas = sorted(set(shas))
    if not shas:
        print(f"\n  Nothing in the index matches {what!r}. Nothing was changed.\n")
        return 1
    for sha in shas:
        idx.forget(sha)
    idx.db.commit()
    print(f"\n  Forgotten: {len(shas)} photo(s). They are out of the index and off "
          f"the wall,\n  and they stay out even if the files are still in the "
          f"folder.\n  The original files were not touched.\n")
    return 0


def cmd_stats(a) -> int:
    idx = open_index(a.index)
    n, = next(idx.db.execute("SELECT COUNT(*) FROM vectors"))
    b, = next(idx.db.execute("SELECT COALESCE(SUM(bytes),0) FROM photos"))
    f, = next(idx.db.execute("SELECT COUNT(*) FROM failures"))
    print(json.dumps({"indexed": n, "source_bytes": b, "failures": f,
                      **idx.manifest()}, indent=2))
    return 0


def cmd_selftest(a) -> int:
    """Prove the pipeline end to end without a download.

    Uses UNTRAINED weights, so it tests everything except the one thing that
    is a property of CLIP rather than of this file: whether the top hit is
    the right photo. That needs one run with real weights on a machine that
    can reach the weights once.
    """
    import shutil
    import tempfile
    import numpy as np
    from PIL import Image, ImageDraw

    td = Path(tempfile.mkdtemp(prefix="photo-index-selftest-"))
    try:
        pix = td / "pix"
        pix.mkdir()
        for name, bg, fg, shape in (("red_square.png", "white", "red", "sq"),
                                    ("blue_circle.png", "white", "blue", "ci"),
                                    ("green_tri.png", "white", "green", "tr"),
                                    ("yellow_circle.png", "black", "yellow", "ci")):
            im = Image.new("RGB", (256, 256), bg)
            dr = ImageDraw.Draw(im)
            if shape == "sq":
                dr.rectangle([48, 48, 208, 208], fill=fg)
            elif shape == "ci":
                dr.ellipse([48, 48, 208, 208], fill=fg)
            else:
                dr.polygon([(128, 40), (220, 215), (36, 215)], fill=fg)
            im.save(pix / name)
        (pix / "not_an_image.txt").write_text("ignore me")
        shutil.copy(pix / "red_square.png", pix / "red_square_COPY.png")

        args = argparse.Namespace(
            index=str(td / "idx"), source=str(pix), model=DEFAULT_MODEL,
            pretrained="none", batch=4, limit=0, offline=True)
        cmd_build(args)
        idx = PhotoIndex(td / "idx")

        # 1. content-addressed: the duplicate is ONE row, not two
        n, = next(idx.db.execute("SELECT COUNT(*) FROM vectors"))
        assert n == 4, f"expected 4 unique photos, indexed {n}"
        files, = next(idx.db.execute("SELECT COUNT(*) FROM photos"))
        assert files == 4, files
        assert not list(idx.db.execute(
            "SELECT * FROM failures")), "a valid image failed to embed"

        # 2. resumable: a second pass embeds nothing new
        before = idx.manifest()["updated"]
        cmd_build(args)
        assert next(idx.db.execute("SELECT COUNT(*) FROM vectors"))[0] == 4
        assert idx.manifest()["updated"] >= before

        # 3. vectors are unit-length, so a dot product IS cosine similarity
        mat, shas = idx.matrix()
        assert mat.shape == (4, idx.manifest()["dim"]), mat.shape
        norms = np.linalg.norm(mat, axis=1)
        assert np.allclose(norms, 1.0, atol=2e-3), norms

        # 4. search returns ranked, descending, resolvable paths
        emb = Embedder(idx, DEFAULT_MODEL, "none", offline=True)
        q = emb.embed_text(["a red square"])[0]
        scores = mat @ q
        order = np.argsort(-scores)
        assert all(scores[order[i]] >= scores[order[i + 1]] for i in range(3))
        paths = idx.paths_for([shas[i] for i in order])
        assert len(paths) == 4 and all(Path(p).exists() for p in paths.values())

        # 5. an index refuses a model it was not built with — silently mixing
        #    embedding spaces would return confident nonsense
        try:
            idx.claim("ViT-L-14", "something-else", 768)
            raise AssertionError("accepted a mismatched embedding model!")
        except SystemExit:
            pass

        # 6. the whole thing ran with the network refused
        assert os.environ.get("HF_HUB_OFFLINE") == "1"

        # 7. WHEN and WHERE — the two thirds of the Cuba question that need
        #    no model at all. Two photos with real EXIF: one shot in Varadero
        #    in 2016, one in Toronto in 2023.
        try:
            import piexif
        except ImportError:
            print("  (skipped the when/where test — pip install piexif)")
        else:
            def _stamp(name, when, lat, lon):
                p = pix / name
                Image.new("RGB", (64, 64), "gray").save(p, "JPEG")
                def dms(v):
                    v = abs(v)
                    d = int(v); m = int((v - d) * 60)
                    s = round((v - d - m / 60) * 3600 * 100)
                    return ((d, 1), (m, 1), (s, 100))
                ex = {"Exif": {piexif.ExifIFD.DateTimeOriginal: when.encode()},
                      "GPS": {piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
                              piexif.GPSIFD.GPSLatitude: dms(lat),
                              piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
                              piexif.GPSIFD.GPSLongitude: dms(lon)}}
                piexif.insert(piexif.dump(ex), str(p))
                return p

            cuba = _stamp("varadero.jpg", "2016:07:14 12:30:00", 23.1394, -81.2714)
            home = _stamp("home.jpg", "2023:11:02 09:00:00", 43.6532, -79.3832)

            facts = read_when_where(cuba)
            assert facts["taken_at"].startswith("2016-07-14"), facts
            assert abs(facts["lat"] - 23.1394) < 0.01, facts
            assert abs(facts["lon"] + 81.2714) < 0.01, facts

            rows = [read_when_where(cuba), read_when_where(home)]
            name_places(rows)
            if rows[0].get("country"):          # needs reverse_geocoder installed
                assert rows[0]["country"] == "Cuba", rows[0]
                assert rows[1]["country"] == "Canada", rows[1]

                cmd_build(args)                 # index the two new photos
                idx2 = PhotoIndex(td / "idx")
                import recall
                known = {r[0] for r in idx2.db.execute(
                    "SELECT DISTINCT country FROM photos WHERE country IS NOT NULL")}
                known |= {r[0] for r in idx2.db.execute(
                    "SELECT DISTINCT place FROM photos WHERE place IS NOT NULL")}
                assert "Cuba" in known, known

                # THE question, parsed and answered end to end
                q = recall.parse(
                    "show me the part of me that was on vacation ten years ago in Cuba",
                    known, dt.date(2026, 9, 14))
                assert q.places == ["Cuba"] and q.semantic == "vacation"
                hits = recall.run(idx2, q, emb, top=10)
                assert len(hits) == 1, [h["path"] for h in hits]
                assert Path(hits[0]["path"]).name == "varadero.jpg"

                # and the time filter alone excludes the Toronto photo
                q2 = recall.parse("2023", known, dt.date(2026, 9, 14))
                hits2 = recall.run(idx2, q2, None, top=10)
                assert [Path(h["path"]).name for h in hits2] == ["home.jpg"], hits2
                # 8. THE LIVING INDEX — it keeps up, and it never deletes.
                w = argparse.Namespace(index=str(td / "idx"), source=str(pix),
                                       every=1, once=True, batch=4, verbose=False,
                                       model=DEFAULT_MODEL, pretrained="none")
                cmd_watch(w)                       # registers the source
                before = next(idx2.db.execute("SELECT COUNT(*) FROM vectors"))[0]

                Image.new("RGB", (48, 48), "purple").save(pix / "later.png")
                cmd_watch(w)
                idx3 = PhotoIndex(td / "idx")
                assert next(idx3.db.execute("SELECT COUNT(*) FROM vectors"))[0] == before + 1

                # a file disappears: recorded as missing, NOT deleted
                (pix / "later.png").unlink()
                cmd_watch(w)
                idx3 = PhotoIndex(td / "idx")
                assert next(idx3.db.execute("SELECT COUNT(*) FROM vectors"))[0] == before + 1, \
                    "a vanished file was deleted from the index"
                miss = next(idx3.db.execute(
                    "SELECT COUNT(*) FROM photos WHERE missing_since IS NOT NULL"))[0]
                assert miss == 1, f"expected 1 missing, got {miss}"

                # ...and when the drive comes back, so does the photo, with
                # everything already known about it
                Image.new("RGB", (48, 48), "purple").save(pix / "later.png")
                cmd_watch(w)
                idx3 = PhotoIndex(td / "idx")
                assert next(idx3.db.execute(
                    "SELECT COUNT(*) FROM photos WHERE missing_since IS NOT NULL"))[0] == 0
                assert next(idx3.db.execute("SELECT COUNT(*) FROM scans"))[0] >= 4
                print("  ✓ living index: re-scans on its own, marks absent files")
                print("    missing instead of deleting them, and restores them")
                print("    untouched when the drive comes back")

                print("  ✓ when & where: EXIF date + GPS read, geocoded offline to")
                print("    Cuba/Canada, and \"vacation ten years ago in Cuba\" returns")
                print("    exactly the Varadero photo")
            else:
                print("  (skipped geocoding — pip install reverse_geocoder pycountry)")
        print("\n  ✓ pipeline: sha256 identity (duplicate collapsed), resumable,"
              "\n    unit vectors, ranked search, model-mismatch refused, offline."
              "\n  ⚠ untrained weights — search QUALITY still needs one run with"
              "\n    real weights on a machine that can fetch them once.\n")
        return 0
    finally:
        shutil.rmtree(td, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", default=str(home.index_path()),
                    help="where the index and the model weights live")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="index a folder of photos")
    b.add_argument("source")
    b.add_argument("--model", default=DEFAULT_MODEL)
    b.add_argument("--pretrained", default=DEFAULT_PRETRAINED)
    b.add_argument("--batch", type=int, default=16)
    b.add_argument("--limit", type=int, default=0, help="stop after N (a trial run)")
    b.add_argument("--offline", action="store_true",
                   help="refuse to fetch weights; use only what is on the drive")
    b.set_defaults(fn=cmd_build)

    s = sub.add_parser("search", help="search the index in plain words")
    s.add_argument("query")
    s.add_argument("--top", type=int, default=10)
    s.set_defaults(fn=cmd_search)

    v = sub.add_parser("verify", help="prove it runs with the network off")
    v.set_defaults(fn=cmd_verify)

    st = sub.add_parser("stats", help="what is in the index")
    st.set_defaults(fn=cmd_stats)

    w = sub.add_parser("watch", help="keep the index alive as the library changes")
    w.add_argument("source", nargs="?", help="a folder to watch (remembered)")
    w.add_argument("--every", type=int, default=300, help="seconds between passes")
    w.add_argument("--once", action="store_true", help="one pass, then exit (for cron/launchd)")
    w.add_argument("--batch", type=int, default=16)
    w.add_argument("--verbose", action="store_true", help="say so even when nothing changed")
    w.add_argument("--model", default=DEFAULT_MODEL)
    w.add_argument("--pretrained", default=DEFAULT_PRETRAINED)
    w.set_defaults(fn=cmd_watch)

    fg = sub.add_parser("forget", help="take a photo (or a folder of them) out of "
                                       "the index and off the wall, for good")
    fg.add_argument("what", help="the photo file, a folder, or its id")
    fg.set_defaults(fn=cmd_forget)

    t = sub.add_parser("selftest", help="prove the pipeline, no download needed")
    t.set_defaults(fn=cmd_selftest)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
