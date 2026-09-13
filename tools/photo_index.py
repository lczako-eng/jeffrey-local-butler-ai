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

Install (once, with a network; after that it never needs one)
    pip install open_clip_torch torch pillow numpy
    # or:  pip install transformers torch pillow numpy
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp",
                  ".bmp", ".tif", ".tiff", ".gif"}

# Small, open, and good enough. ~150 MB of weights, 512-dim embeddings.
DEFAULT_MODEL = "ViT-B-32"
DEFAULT_PRETRAINED = "laion2b_s34b_b79k"


# --------------------------------------------------------------- the index
class PhotoIndex:
    """A content-addressed vector index that lives in one directory.

    Keyed by SHA-256, so it shares its identity model with the dedup work
    that already ran: the same photo found on three drives is one row, and
    moving or renaming a file never orphans its vector.
    """

    def __init__(self, root: Path):
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "index.sqlite"
        self.manifest_path = self.root / "manifest.json"
        self.model_dir = self.root / "models"
        self.db = sqlite3.connect(self.db_path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS photos (
                sha256 TEXT PRIMARY KEY, path TEXT, bytes INTEGER,
                mtime REAL, seen_at TEXT);
            CREATE TABLE IF NOT EXISTS vectors (
                sha256 TEXT PRIMARY KEY, dim INTEGER, vec BLOB);
            CREATE TABLE IF NOT EXISTS failures (
                path TEXT PRIMARY KEY, reason TEXT, at TEXT);
            CREATE INDEX IF NOT EXISTS photos_path ON photos(path);
        """)
        self.db.commit()

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

    def add(self, sha: str, path: Path, vec) -> None:
        st = path.stat()
        self.db.execute(
            "INSERT OR REPLACE INTO photos VALUES (?,?,?,?,?)",
            (sha, str(path), st.st_size, st.st_mtime,
             time.strftime("%Y-%m-%dT%H:%M:%S")))
        self.db.execute("INSERT OR REPLACE INTO vectors VALUES (?,?,?)",
                        (sha, len(vec), vec.astype("float16").tobytes()))

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
        q = ",".join("?" * len(shas))
        return dict(self.db.execute(
            f"SELECT sha256, path FROM photos WHERE sha256 IN ({q})", shas))


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


def walk(root: Path):
    for p in sorted(Path(root).expanduser().rglob("*")):
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES:
            yield p


def open_image(path: Path):
    from PIL import Image
    try:                                   # iPhone libraries are full of HEIC
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    return Image.open(path).convert("RGB")


# --------------------------------------------------------------- commands
def cmd_build(a) -> int:
    idx = PhotoIndex(a.index)
    emb = Embedder(idx, a.model, a.pretrained, offline=a.offline)
    idx.claim(emb.name, emb.pretrained, emb.dim)
    print(f"  model    {emb.name}/{emb.pretrained} ({emb.dim}-dim, {emb.backend})")
    print(f"  weights  {idx.model_dir}")
    print(f"  index    {idx.db_path}")

    known = idx.have()
    files = list(walk(a.source))
    print(f"  found    {len(files)} images under {a.source}")

    batch_imgs, batch_meta, done, skipped, failed = [], [], 0, 0, 0
    t0 = time.time()

    def flush():
        nonlocal done
        if not batch_imgs:
            return
        vecs = emb.embed_images(batch_imgs)
        for (sha, path), vec in zip(batch_meta, vecs):
            idx.add(sha, path, vec)
        idx.db.commit()
        done += len(batch_meta)
        batch_imgs.clear()
        batch_meta.clear()

    for n, path in enumerate(files, 1):
        if a.limit and done + skipped >= a.limit:
            break
        try:
            sha = sha256(path)
            if sha in known:
                skipped += 1
                continue
            batch_imgs.append(open_image(path))
            batch_meta.append((sha, path))
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
    secs = time.time() - t0
    print(f"\r  embedded {done}  already had {skipped}  failed {failed}  "
          f"in {secs:.1f}s".ljust(72)
          + (f"  ({done / secs:.1f}/s)" if done and secs else ""))
    print(f"\n  Done. Search it with no network at all:\n"
          f"    python {Path(__file__).name} search \"kids at the lake\" "
          f"--index {a.index}")
    return 0


def cmd_search(a) -> int:
    import numpy as np
    idx = PhotoIndex(a.index)
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
    idx = PhotoIndex(a.index)
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


def cmd_stats(a) -> int:
    idx = PhotoIndex(a.index)
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
    ap.add_argument("--index", default="~/.selfcloud/photo-index",
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

    t = sub.add_parser("selftest", help="prove the pipeline, no download needed")
    t.set_defaults(fn=cmd_selftest)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
