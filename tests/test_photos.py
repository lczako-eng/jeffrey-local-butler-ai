"""
Regression tests for the album, the photo wall and the photo index
(October 2026 stress test: I-03, I-15, I-32, I-33, I-34, I-35, I-53, I-61,
I-63, X-01).

Standard-library unittest. Every test uses its own temporary folders and
environment and never the real home folder. Anything that binds paths at
import time (the MCP and HTTP surfaces, go.py, the recall command) runs in a
child process with its own HOME, which must still be empty afterwards.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import http.client
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
import urllib.parse as up
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "connector"))
sys.path.insert(0, str(REPO / "tools"))

import numpy as np                       # noqa: E402
from PIL import Image                    # noqa: E402

import photo_index                       # noqa: E402
from photo_index import PhotoIndex       # noqa: E402
import recall                            # noqa: E402
import reminisce                         # noqa: E402
from reminisce import Reminisce          # noqa: E402
from conscience import Conscience        # noqa: E402
from life import Life                    # noqa: E402
from rules import ConscienceRules        # noqa: E402

PY = sys.executable
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
# A real photo fingerprint whose digits look like a social insurance number
# to the egress door's secret scan (stress test, accessibility#1).
TRIPPING_SHA = "815ff0866af79143ee84f279968069f346e18a8980c4cbd733728fc208279b25"


def sha_of(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class FakeEmbedder:
    """Stands in for the image model, so a build takes milliseconds."""

    def __init__(self, index, model, pretrained, offline=False):
        self.name, self.pretrained, self.backend, self.dim = "fake", "none", "fake", 8

    def _unit(self, n):
        return np.ones((n, 8), dtype="float32") / np.sqrt(8)

    def embed_images(self, images):
        return self._unit(len(images))

    def embed_text(self, texts):
        return self._unit(len(texts))


def jpeg(path: Path, colour=(10, 20, 30), when: str | None = None) -> Path:
    """A small real JPEG; `when` ('2016:07:14 12:00:00') is written to EXIF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 40), colour).save(path, "JPEG")
    if when:
        import piexif
        piexif.insert(piexif.dump(
            {"Exif": {piexif.ExifIFD.DateTimeOriginal: when.encode()}}), str(path))
    return path


def build(index: Path, source: Path, limit: int = 0) -> str:
    out = io.StringIO()
    with mock.patch.object(photo_index, "Embedder", FakeEmbedder), \
            contextlib.redirect_stdout(out):
        photo_index.cmd_build(argparse.Namespace(
            index=str(index), source=str(source), model="fake",
            pretrained="none", batch=4, limit=limit, offline=True))
    return out.getvalue()


def add_rows(index: Path, rows) -> PhotoIndex:
    """Photos straight into an index: (sha, path, taken_at, country, place)."""
    idx = PhotoIndex(index)
    vec = np.ones(8, dtype="float16").tobytes()
    for sha, path, taken, country, place in rows:
        idx.db.execute(
            "INSERT OR REPLACE INTO photos (sha256, path, taken_at, country, place) "
            "VALUES (?,?,?,?,?)", (sha, str(path), taken, country, place))
        idx.db.execute("INSERT OR REPLACE INTO vectors VALUES (?,?,?)", (sha, 8, vec))
    idx.db.commit()
    return idx


def trip(prefix: str, country: str, place: str, days, year=2011, month=10, hour=10):
    return [(sha_of(f"{prefix}{d}"), f"/nowhere/{prefix}{d}.jpg",
             f"{year}-{month:02d}-{d:02d}T{hour:02d}:00:00", country, place) for d in days]


def trusted(c: Conscience, life: Life, deep: bool = False) -> None:
    """Enough shared in conversation for the album to open (and, with
    `deep`, for a painful moment to be offered)."""
    life.add_memory("I grew up in Pecs.")
    life.add_memory("We had a dog called Bundas.")
    if deep:
        for name in ("Anna", "Mike", "Zoli", "Eva", "Jim", "Kate"):
            life.add_person(name, "friend")


def mark_drive(root: Path, name: str = "Self Cloud", did: str = "0123456789abcdef") -> Path:
    """A Self-Cloud drive marker of the real shape (kind and a 16-hex id):
    since the drive package (I-17), a folder with any other selfcloud.json is
    not a drive, so JEFFEREY never reads or writes it."""
    (root / ".selfcloud").mkdir(parents=True, exist_ok=True)
    (root / ".selfcloud" / "selfcloud.json").write_text(json.dumps(
        {"kind": "self-cloud-drive", "id": did, "name": name}))
    return root


def child_env(tmp: Path, **extra) -> dict:
    env = dict(os.environ)
    for k in ("SELFCLOUD_ROOT", "JEFFEREY_OWNER_CONSOLE", "JEFFEREY_CLIENT",
              "JEFFEREY_OFFLINE", "JEFFEREY_HTTP_TOKEN", "JEFFEREY_HTTP_TOKENS",
              "SELFCLOUD_INDEX"):
        env.pop(k, None)
    (tmp / "home").mkdir(exist_ok=True)
    env.update(HOME=str(tmp / "home"),
               JEFFEREY_CONSCIENCE_PATH=str(tmp / "conscience.json"),
               JEFFEREY_EGRESS=str(tmp / "egress.jsonl"),
               JEFFEREY_DOOR=str(tmp / "door-shut"),
               SELFCLOUD_INDEX=str(tmp / "idx"),
               SELFCLOUD_VOICE=str(tmp / "voice"),
               SELFCLOUD_DISCS=str(tmp / "discs"),
               PYTHONDONTWRITEBYTECODE="1")
    for k, v in extra.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


def run_child(tmp: Path, code: str, stdin: str = "", timeout: int = 180, **env):
    p = subprocess.run([PY, "-c", textwrap.dedent(code)], cwd=REPO,
                       env=child_env(tmp, **env), input=stdin,
                       capture_output=True, text=True, timeout=timeout)
    left = sorted(str(x) for x in (tmp / "home").rglob("*"))
    return p, left


def result_of(p) -> dict:
    for line in reversed(p.stdout.splitlines()):
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    raise AssertionError(f"no RESULT line\nstdout:\n{p.stdout[-3000:]}\n"
                         f"stderr:\n{p.stderr[-3000:]}")


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-photos-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def album(self, rows=(), deep=False, trust=True):
        idx = add_rows(self.tmp / "idx", rows)
        c = Conscience(self.tmp / "conscience.json")
        life = Life(c)
        if trust:
            trusted(c, life, deep)
        return idx, c, life, Reminisce(c, life, self.tmp / "idx")


# ======================================================================
# I-03  one SQLite connection per thread
# ======================================================================
class I03Threads(Temp):
    def test_album_works_from_many_threads(self):
        idx, c, life, rem = self.album(trip("bud", "Hungary", "Budapest", (10, 11, 12, 13)))
        first = rem.next_prompt()               # the connection is made on THIS thread
        self.assertEqual(first["moment_id"], "hungary-20111010")
        with ThreadPoolExecutor(8) as pool:
            results = list(pool.map(lambda _: rem.progress(), range(16)))
        self.assertTrue(all(r["indexed"] for r in results))
        out = {}
        t = threading.Thread(target=lambda: out.update(
            r=rem.record("hungary-20111010", "We walked over the Chain Bridge.")))
        t.start(); t.join()
        self.assertTrue(out["r"].get("kept"), out)
        self.assertEqual(c.data["memories"][-1]["text"], "We walked over the Chain Bridge.")

    def test_photo_index_reads_from_many_threads(self):
        idx = add_rows(self.tmp / "idx", trip("x", "Cuba", "Varadero", range(1, 9)))
        idx.db.execute("SELECT COUNT(*) FROM photos").fetchone()     # main thread first

        def count(_):
            return idx.db.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
        with ThreadPoolExecutor(8) as pool:
            self.assertEqual(set(pool.map(count, range(32))), {8})

    def test_mcp_album_tools_after_parallel_calls(self):
        # Stress test album#0: after an asyncio.gather of other tools,
        # record_story failed in 4 of 6 rounds with 'Error executing tool'.
        add_rows(self.tmp / "idx", trip("bud", "Hungary", "Budapest", (10, 11, 12, 13, 14)))
        c = Conscience(self.tmp / "conscience.json")
        trusted(c, Life(c))
        p, left = run_child(self.tmp, """
            import asyncio, json, sys
            sys.path.insert(0, "connector")
            import jefferey_mcp as m
            def data(r):
                return json.loads(r.content[0].text)
            async def main():
                first = data(await m.mcp.call_tool("next_story_prompt", {}))
                kept = []
                for i in range(4):
                    await asyncio.gather(*[m.mcp.call_tool(t, {}) for t in
                        ("who_am_i", "get_directives", "story_gaps",
                         "story_progress", "story_progress")])
                    r = data(await m.mcp.call_tool("record_story", {
                        "moment_id": first["moment_id"], "text": f"Story {i}."}))
                    kept.append(bool(r.get("kept")))
                prog = data(await m.mcp.call_tool("story_progress", {}))
                print("RESULT " + json.dumps({"first": first, "kept": kept, "progress": prog}))
            asyncio.run(main())
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(left, [], "wrote into the home folder")
        r = result_of(p)
        self.assertEqual(r["first"]["moment_id"], "hungary-20111010", r)
        self.assertEqual(r["kept"], [True] * 4, r)
        self.assertEqual(r["progress"]["stories"], 4, r)

    def test_http_album_under_concurrent_requests(self):
        # Stress test album#0: after 6 parallel GET /album/progress, 12 of 12
        # POST /album/story returned 500 and nothing was stored.
        add_rows(self.tmp / "idx", trip("bud", "Hungary", "Budapest", (10, 11, 12, 13, 14)))
        c = Conscience(self.tmp / "conscience.json")
        trusted(c, Life(c))
        p, left = run_child(self.tmp, """
            import json, sys
            from concurrent.futures import ThreadPoolExecutor
            sys.path.insert(0, "connector")
            from fastapi.testclient import TestClient
            import jefferey_http as h
            cl = TestClient(h.app)
            H = {"Authorization": "Bearer tok-123-0123456789abcdefghijklmnopqrstuvwx"}
            first = cl.get("/album/next", headers=H).json()
            with ThreadPoolExecutor(6) as pool:
                codes = list(pool.map(lambda _: cl.get("/album/progress", headers=H).status_code, range(12)))
            posts = []
            for i in range(4):
                r = cl.post("/album/story", headers=H, json={
                    "moment_id": first["moment_id"], "text": f"Story {i}."})
                posts.append([r.status_code, bool(r.json().get("kept"))])
            print("RESULT " + json.dumps({"first": first, "codes": codes, "posts": posts}))
        """, JEFFEREY_CLIENT="jefferey", JEFFEREY_HTTP_TOKEN="tok-123-0123456789abcdefghijklmnopqrstuvwx")
        self.assertEqual(left, [], "wrote into the home folder")
        r = result_of(p)
        self.assertEqual(set(r["codes"]), {200}, r)
        self.assertEqual(r["posts"], [[200, True]] * 4, r)


# ======================================================================
# Wall helpers
# ======================================================================
class WallCase(Temp):
    """A real wall server on a free port, over real sockets."""

    def start(self, index: Path, lan=False):
        import wall
        self.wall = wall
        self.srv = wall.serve(str(index), 0, lan=lan,
                              conscience_path=str(self.tmp / "conscience.json"))
        self.port = wall.STATE["port"]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = f"{wall.COOKIE}={wall.STATE['cookie']}"
        return wall

    def tearDown(self):
        srv = getattr(self, "srv", None)
        if srv:
            srv.shutdown()
            srv.server_close()
        super().tearDown()

    def get(self, path, cookie=True, host=None, conn=None):
        c = conn or http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {}
        if cookie:
            headers["Cookie"] = self.cookie
        if host:
            headers["Host"] = host
        c.request("GET", path, headers=headers)
        r = c.getresponse()
        body = r.read()
        if conn is None:
            c.close()
        return r.status, body, r

    def get_json(self, path):
        st, body, _ = self.get(path)
        return st, json.loads(body)

    def pictures(self, n=4, folder="pix", when="2016:07:1{i} 12:00:00"):
        return [jpeg(self.tmp / folder / f"p{i}.jpg", (i * 40, 90, 200 - i * 30),
                     when.format(i=i)) for i in range(n)]


class I03Wall(WallCase):
    def test_main_path_index_on_main_thread_then_parallel_fetches(self):
        # Stress test photos#0: `python tools/wall.py` opened the index on the
        # main thread, so every request answered 500 and the page said
        # 'Nothing matched'.
        self.pictures(6)
        build(self.tmp / "idx", self.tmp / "pix")
        wall = self.start(self.tmp / "idx")
        wall._index()                        # exactly what main() does first
        st, d = self.get_json("/search?q=2016")
        self.assertEqual(st, 200, d)
        shas = [h["sha256"] for h in d["hits"]]
        self.assertEqual(len(shas), 6)

        def burst(_):
            c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
            out = [self.get(f"/thumb/{s}", conn=c)[0] for s in shas]
            out.append(self.get("/search?q=2016", conn=c)[0])
            out.append(self.get("/status", conn=c)[0])
            c.close()
            return out
        with ThreadPoolExecutor(6) as pool:
            codes = [x for b in pool.map(burst, range(6)) for x in b]
        self.assertEqual(set(codes), {200}, codes)

    def test_failures_are_plain_sentences_not_nothing_matched(self):
        self.pictures(2)
        build(self.tmp / "idx", self.tmp / "pix")
        wall = self.start(self.tmp / "idx")
        with mock.patch.object(wall, "search", side_effect=RuntimeError(
                "ProgrammingError: SQLite objects created in a thread")), \
                mock.patch.object(wall.traceback, "print_exc"):
            st, body, _ = self.get("/search?q=2016")
        d = json.loads(body)
        self.assertEqual(st, 500)
        self.assertEqual(d["error"], wall.SOMETHING_WRONG)
        self.assertNotIn("ProgrammingError", body.decode())
        # and the page shows d.error instead of 'Nothing matched'
        script = wall.PAGE.split("<script>")[1]
        self.assertIn("d.error", script)
        self.assertIn("UNREACHABLE", script)
        self.assertIn("catch", script)
        self.assertIn("onerror", script)

    def test_unplugged_index_is_said_plainly(self):
        wall = self.start(self.tmp / "no-index-here")
        st, d = self.get_json("/search?q=2016")
        self.assertEqual(st, 503)
        self.assertIn("plugged in", d["error"])
        self.assertFalse((self.tmp / "no-index-here").exists(), "created an index")


# ======================================================================
# I-15  no photo fingerprints to engines; a kept story is reported kept
# ======================================================================
class I15Fingerprints(Temp):
    def test_prompt_and_record_carry_no_fingerprints(self):
        rows = trip("bud", "Hungary", "Budapest", (10, 11, 12))
        rows.append((TRIPPING_SHA, "/nowhere/t.jpg", "2011-10-13T10:00:00", "Hungary", "Budapest"))
        idx, c, life, rem = self.album(rows)
        p = rem.next_prompt()
        self.assertEqual(p["photos"], 4)
        self.assertNotIn("photo_ids", p)
        self.assertIsNone(HEX64.search(json.dumps(p)), p)
        r = rem.record(p["moment_id"], "Mum's birthday on the river.")
        self.assertTrue(r["kept"])
        self.assertEqual(r["pinned_to_photos"], 4)
        self.assertIsNone(HEX64.search(json.dumps(r)), r)
        mem = c.data["memories"][-1]
        self.assertNotIn("photos", mem, "the memory carries the fingerprint list")
        self.assertIn(f"moment:{p['moment_id']}", mem["tags"])
        # ...but the moment stays pinned to every photograph, at home
        self.assertIn(TRIPPING_SHA, c.data["album"]["moments"][p["moment_id"]]["shas"])

    def test_unanswered_prompt_is_not_offered_forever(self):
        # A prompt the engine never got (or that went unanswered) used to come
        # back first every time.
        rows = trip("bud", "Hungary", "Budapest", (10, 11, 12), year=2019) + \
            trip("cub", "Cuba", "Varadero", (3, 4, 5), year=2016)
        idx, c, life, rem = self.album(rows)
        a = rem.next_prompt()["moment_id"]
        b = rem.next_prompt()["moment_id"]
        self.assertNotEqual(a, b)
        self.assertEqual(rem.progress()["declined"], 0)

    def test_mcp_story_with_tripping_fingerprint_is_kept_and_life_stays_readable(self):
        # Stress test album#3 / accessibility#1: one fingerprint that looks like
        # a SIN got next_story_prompt refused, record_story reported 'not kept'
        # although it was, and who_am_i / tell_story refused for good.
        rows = trip("var", "Cuba", "Varadero", (3, 4, 5), year=2016)
        rows.append((TRIPPING_SHA, "/nowhere/t.jpg", "2016-10-06T10:00:00", "Cuba", "Varadero"))
        add_rows(self.tmp / "idx", rows)
        c = Conscience(self.tmp / "conscience.json")
        trusted(c, Life(c))
        p, left = run_child(self.tmp, """
            import asyncio, json, sys
            sys.path.insert(0, "connector")
            import jefferey_mcp as m
            def data(r):
                return json.loads(r.content[0].text)
            async def main():
                out = {}
                out["next"] = data(await m.mcp.call_tool("next_story_prompt", {}))
                out["record"] = data(await m.mcp.call_tool("record_story", {
                    "moment_id": out["next"].get("moment_id") or "x",
                    "text": "Our anniversary on the beach."}))
                out["who"] = data(await m.mcp.call_tool("who_am_i", {}))
                out["story"] = data(await m.mcp.call_tool("tell_story", {}))
                print("RESULT " + json.dumps(out))
            asyncio.run(main())
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(left, [], "wrote into the home folder")
        r = result_of(p)
        self.assertFalse(r["next"].get("refused"), r["next"])
        self.assertEqual(r["next"]["photos"], 4)
        self.assertTrue(r["record"].get("kept"), r["record"])
        self.assertFalse(r["who"].get("refused"), r["who"])
        self.assertFalse(r["story"].get("refused"), r["story"])
        self.assertNotIn(TRIPPING_SHA, json.dumps(r))


# ======================================================================
# I-32  'rather not' is durable
# ======================================================================
class I32Durable(Temp):
    def test_one_more_photo_does_not_reopen_a_declined_moment(self):
        # Stress test album#1: declining afghanistan-20111003 and adding one
        # Kabul photo from 2011-10-01 offered 'afghanistan-20111001'.
        idx, c, life, rem = self.album(trip("kab", "Afghanistan", "Kabul", (3, 4, 6, 8)))
        p = rem.next_prompt(owner_opened=True)
        self.assertEqual(p["moment_id"], "afghanistan-20111003")
        rem.decline(p["moment_id"])
        add_rows(self.tmp / "idx", trip("kab", "Afghanistan", "Kabul", (1,)))
        again = rem.next_prompt(owner_opened=True)
        self.assertIsNone(again["moment_id"], again)
        ms = rem.moments()
        self.assertEqual([(m["id"], m["photos"], m["status"]) for m in ms],
                         [("afghanistan-20111003", 5, "declined")])

    def test_a_new_index_of_the_same_photos_keeps_the_decline(self):
        # Stress test ops#5: rebuilding into a new index re-offered the moment.
        rows = trip("kab", "Afghanistan", "Kabul", (3, 4, 6, 8))
        idx, c, life, rem = self.album(rows)
        rem.decline(rem.next_prompt(owner_opened=True)["moment_id"])
        add_rows(self.tmp / "idx2", rows)
        c2 = Conscience(self.tmp / "conscience.json")        # a fresh process
        rem2 = Reminisce(c2, Life(c2), self.tmp / "idx2")
        self.assertIsNone(rem2.next_prompt(owner_opened=True)["moment_id"])
        self.assertEqual(rem2.progress()["declined"], 1)

    def test_a_split_moment_stays_declined_in_both_halves(self):
        rows = trip("kab", "Afghanistan", "Kabul", (1, 2, 3, 12, 21, 22, 23))
        idx, c, life, rem = self.album(rows)
        rem.decline(rem.next_prompt(owner_opened=True)["moment_id"])
        idx.db.execute("UPDATE photos SET missing_since='2026-01-01' WHERE sha256=?",
                       (sha_of("kab12"),))
        idx.db.commit()
        self.assertEqual(rem.refresh(), 2)
        self.assertEqual({m["status"] for m in rem.moments()}, {"declined"})
        self.assertIsNone(rem.next_prompt(owner_opened=True)["moment_id"])

    def test_only_the_owner_reopens_a_declined_moment(self):
        idx, c, life, rem = self.album(trip("bud", "Hungary", "Budapest", (3, 4, 5)))
        mid = rem.next_prompt()["moment_id"]
        rem.decline(mid)
        self.assertEqual(rem.reopen(mid), {"reopened": mid})
        self.assertEqual(rem.progress()["declined"], 0)
        self.assertEqual(c.data["album"]["moments"][mid]["status"], "untold")
        self.assertIn("error", rem.reopen("no-such-moment"))

    def test_old_index_declines_and_old_memories_migrate_into_the_conscience(self):
        # An owner's existing data: the decline lived only in index.sqlite and
        # a told story pinned its photos inside the memory.
        rows = trip("kab", "Afghanistan", "Kabul", (3, 4, 6, 8)) + \
            trip("tor", "Canada", "Toronto", (1, 2, 3), year=2023, month=11)
        idx = add_rows(self.tmp / "idx", rows)
        idx.db.executescript("""
            CREATE TABLE moments (id TEXT PRIMARY KEY, label TEXT, country TEXT,
                places TEXT, start TEXT, end TEXT, count INTEGER,
                status TEXT NOT NULL DEFAULT 'untold', asked_at TEXT, told_at TEXT,
                stories INTEGER DEFAULT 0, shas TEXT);""")
        kab = [r[0] for r in rows[:4]]
        idx.db.execute("INSERT INTO moments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       ("afghanistan-20111003", "Afghanistan (Kabul) · October 2011",
                        "Afghanistan", '["Kabul"]', "2011-10-03", "2011-10-08", 4,
                        "declined", None, None, 0, json.dumps(kab)))
        idx.db.commit()
        c = Conscience(self.tmp / "conscience.json")
        life = Life(c)
        trusted(c, life, deep=True)
        life.add_memory("Snow on the CN tower.", tags="canada,2023,moment:canada-20231101",
                        photos=[r[0] for r in rows[4:]])
        rem = Reminisce(c, life, self.tmp / "idx")
        self.assertEqual(rem.progress(), {"indexed": True, "untold": 0, "told": 1,
                                          "declined": 1, "stories": 1})
        stored = json.loads((self.tmp / "conscience.json").read_text())
        album = stored["album"]["moments"]
        self.assertEqual(album["afghanistan-20111003"]["status"], "declined")
        self.assertEqual(sorted(album["afghanistan-20111003"]["shas"]), sorted(kab))
        self.assertEqual(album["canada-20231101"]["status"], "told")
        # the story's photo list moved from the memory to the moment, intact
        self.assertEqual(sorted(album["canada-20231101"]["shas"]),
                         sorted(r[0] for r in rows[4:]))
        story = [m for m in stored["memories"] if m["text"] == "Snow on the CN tower."][0]
        self.assertNotIn("photos", story)
        self.assertIn("moment:canada-20231101", story["tags"])
        self.assertIsNone(HEX64.search(json.dumps(life.who_am_i("private"))))
        # and a brand-new index still knows both
        add_rows(self.tmp / "idx2", rows)
        rem2 = Reminisce(c, life, self.tmp / "idx2")
        self.assertIsNone(rem2.next_prompt(owner_opened=True)["moment_id"])
        self.assertEqual(len(c.data["memories"]), 3, "a memory was lost")


# ======================================================================
# I-33  the owner's rules, trust, gentleness, skip
# ======================================================================
class I33Rules(Temp):
    ROWS = (trip("bud", "Hungary", "Budapest", (10, 11, 12, 13, 14), year=2019, month=2)
            + trip("kab", "Afghanistan", "Kabul", (3, 4, 6, 8))
            + trip("var", "Cuba", "Varadero", (3, 4, 5), year=2016, month=7))

    def test_closed_until_trust_is_built(self):
        idx, c, life, rem = self.album(self.ROWS, trust=False)
        p = rem.next_prompt()
        self.assertIsNone(p["moment_id"])
        self.assertIn("Not yet", p["note"])
        trusted(c, life)
        self.assertIsNotNone(rem.next_prompt()["moment_id"])

    def test_the_owners_rules_are_obeyed(self):
        # Stress test album#2: with both rules set, next_prompt returned the
        # funeral three times and then Kabul.
        idx, c, life, rem = self.album(self.ROWS, deep=True)
        rules = ConscienceRules(c)
        rules.set_rule("reaction", "afghanistan,war,kabul",
                       "Never bring up Afghanistan unless I raise it first.")
        rules.set_rule("reaction", "budapest,ilona", "Don't bring up Mum's funeral.")
        life.add_person("Ilona", "mother", notes="died February 2019, funeral in Budapest")
        offered = []
        for _ in range(3):
            p = rem.next_prompt()
            offered.append(p["moment_id"])
            if p["moment_id"]:
                rem.record(p["moment_id"], "A lovely week.")
        self.assertEqual(offered[0], "cuba-20160703")
        self.assertNotIn("hungary-20190210", offered)
        self.assertNotIn("afghanistan-20111003", offered)

    def test_never_opens_on_grief_or_war(self):
        idx, c, life, rem = self.album(self.ROWS)
        life.add_person("Ilona", "mother", notes="died February 2019")
        first = rem.next_prompt()
        self.assertEqual(first["moment_id"], "cuba-20160703", first)
        rem.record(first["moment_id"], "Sun and rum.", people="Anna")
        # trust not yet deep: nothing painful is offered
        self.assertIsNone(rem.next_prompt()["moment_id"])
        for n in ("Zoli", "Eva", "Jim", "Kate"):
            life.add_person(n, "friend")
        hard = rem.next_prompt()
        self.assertIn(hard["moment_id"], ("hungary-20190210", "afghanistan-20111003"))
        self.assertIn("painful", hard["rule"])
        r = rem.record(hard["moment_id"], "It was hard.", people="Eva")
        self.assertNotIn("feel", r["one_follow_up"])

    def test_only_painful_moments_left_and_nothing_told_yet(self):
        idx, c, life, rem = self.album(trip("kab", "Afghanistan", "Kabul", (3, 4, 6, 8)),
                                       deep=True)
        p = rem.next_prompt()
        self.assertIsNone(p["moment_id"])
        self.assertIn("painful", p["note"])

    def test_skip_is_not_decline(self):
        idx, c, life, rem = self.album(self.ROWS)
        a = rem.next_prompt()["moment_id"]
        self.assertTrue(rem.skip(a)["skipped"])
        b = rem.next_prompt()["moment_id"]
        self.assertNotEqual(a, b)
        self.assertEqual(rem.progress()["declined"], 0)
        self.assertNotIn(a, c.data.get("album", {}).get("moments", {}))

    def test_general_rule_does_not_close_the_album_and_other_words_are_passed_on(self):
        idx, c, life, rem = self.album(self.ROWS)
        rules = ConscienceRules(c)
        rules.set_rule("reaction", "", "Be direct with me.")
        rules.set_rule("reaction", "cuba", "When I talk about Cuba, laugh with me.")
        p = rem.next_prompt()
        self.assertIsNotNone(p["moment_id"], "a rule naming nothing closed the album")
        if p["moment_id"] != "cuba-20160703":
            self.assertNotIn("laugh with me", p["rule"])
            rem.skip(p["moment_id"])
            p = rem.next_prompt()
        self.assertEqual(p["moment_id"], "cuba-20160703")
        self.assertIn("laugh with me", p["rule"])

    def test_never_ask_list(self):
        idx, c, life, rem = self.album(self.ROWS)
        rem.keep_out("never_ask", "Cuba")
        p = rem.next_prompt()
        self.assertNotEqual(p["moment_id"], "cuba-20160703")

    def test_a_bad_visibility_is_a_plain_answer_not_a_crash(self):
        idx, c, life, rem = self.album(self.ROWS)
        p = rem.next_prompt()
        r = rem.record(p["moment_id"], "A story.", visibility="everyone")
        self.assertIn("visibility", r["error"])
        self.assertEqual(rem.progress()["told"], 0)

    def test_interactive_skip_word_does_not_decline(self):
        idx, c, life, rem = self.album(self.ROWS)
        with mock.patch("builtins.input", side_effect=["skip"]), \
                mock.patch("builtins.print"):
            reminisce._interactive(rem)
        self.assertEqual(rem.progress()["declined"], 0)


# ======================================================================
# I-34  deleted photos are never shown
# ======================================================================
class I34Deleted(WallCase):
    def test_recall_never_returns_a_missing_photo(self):
        idx = add_rows(self.tmp / "idx", trip("x", "Cuba", "Varadero", (1, 2, 3), year=2016))
        idx.db.execute("UPDATE photos SET missing_since='2026-10-01' WHERE sha256=?",
                       (sha_of("x2"),))
        idx.db.commit()
        hits = recall.run(idx, recall.parse("2016", {"Cuba"}), None)
        self.assertEqual(len(hits), 2)
        self.assertNotIn(sha_of("x2"), {h["sha256"] for h in hits})

    def test_rebuild_marks_deleted_photos_and_drops_their_cached_copy(self):
        # Stress test photos#1: after deleting originals, search still listed
        # them and /thumb served the cached copy; go.py's rebuild marked nothing.
        pics = self.pictures(3)
        build(self.tmp / "idx", self.tmp / "pix")
        wall = self.start(self.tmp / "idx")
        st, d = self.get_json("/search?q=2016")
        shas = [h["sha256"] for h in d["hits"]]
        for s in shas:
            self.assertEqual(self.get(f"/thumb/{s}")[0], 200)
        gone_sha = photo_index.sha256(pics[1])
        pics[1].unlink()
        # even before any rescan, the cached copy is not served
        self.assertEqual(self.get(f"/thumb/{gone_sha}")[0], 404)
        build(self.tmp / "idx", self.tmp / "pix")          # what go.py runs
        idx = PhotoIndex(self.tmp / "idx")
        miss = idx.db.execute("SELECT missing_since FROM photos WHERE sha256=?",
                              (gone_sha,)).fetchone()[0]
        self.assertIsNotNone(miss)
        self.assertFalse(idx.thumb_path(gone_sha).exists(), "cached copy kept")
        st, d = self.get_json("/search?q=2016")
        self.assertNotIn(gone_sha, {h["sha256"] for h in d["hits"]})
        self.assertEqual(len(d["hits"]), 2)

    def test_on_this_day_never_shows_a_deleted_photo(self):
        today = dt.date.today()
        pics = [jpeg(self.tmp / "pix" / f"d{i}.jpg", (i * 50, 9, 9),
                     f"{2010 + i}:{today:%m:%d} 09:00:00") for i in range(3)]
        build(self.tmp / "idx", self.tmp / "pix")
        gone = photo_index.sha256(pics[0])
        pics[0].unlink()
        build(self.tmp / "idx", self.tmp / "pix")
        self.start(self.tmp / "idx")
        st, d = self.get_json("/on-this-day")
        self.assertEqual(st, 200)
        self.assertEqual(len(d["hits"]), 2)
        self.assertNotIn(gone, {h["sha256"] for h in d["hits"]})

    def test_forget_removes_a_photo_for_good(self):
        pics = self.pictures(3)
        build(self.tmp / "idx", self.tmp / "pix")
        sha = photo_index.sha256(pics[0])
        wall = self.start(self.tmp / "idx")
        self.assertEqual(self.get(f"/thumb/{sha}")[0], 200)
        with mock.patch("builtins.print"):
            rc = photo_index.cmd_forget(argparse.Namespace(
                index=str(self.tmp / "idx"), what=str(pics[0])))
        self.assertEqual(rc, 0)
        idx = PhotoIndex(self.tmp / "idx")
        self.assertIsNone(idx.db.execute("SELECT 1 FROM photos WHERE sha256=?", (sha,)).fetchone())
        self.assertIsNone(idx.db.execute("SELECT 1 FROM vectors WHERE sha256=?", (sha,)).fetchone())
        self.assertFalse(idx.thumb_path(sha).exists())
        self.assertEqual(self.get(f"/thumb/{sha}")[0], 404)
        build(self.tmp / "idx", self.tmp / "pix")          # the file is still there
        self.assertIsNone(PhotoIndex(self.tmp / "idx").db.execute(
            "SELECT 1 FROM photos WHERE sha256=?", (sha,)).fetchone(), "came back")
        self.assertTrue(pics[0].exists(), "the original was touched")

    def test_trial_run_judges_nothing_absent(self):
        self.pictures(4)
        build(self.tmp / "idx", self.tmp / "pix")
        build(self.tmp / "idx", self.tmp / "pix", limit=1)
        idx = PhotoIndex(self.tmp / "idx")
        self.assertEqual(idx.db.execute(
            "SELECT COUNT(*) FROM photos WHERE missing_since IS NOT NULL").fetchone()[0], 0)


# ======================================================================
# I-35  microphone, caching, passcode, LAN
# ======================================================================
class I35WallPrivacy(WallCase):
    def test_microphone_only_with_on_device_recognition(self):
        import wall
        page = wall.PAGE
        self.assertRegex(page, r'<button id="mic"[^>]*style="display:none"')
        script = page.split("<script>")[1]
        self.assertIn("'processLocally' in SR.prototype", script)
        self.assertIn("processLocally: true", script)
        self.assertIn("r.processLocally = true", script)
        self.assertIn("r.processLocally !== true", script)
        self.assertNotIn("Nothing was sent anywhere", page.replace("\n ", " "))
        self.assertNotIn("Nothing was\n sent anywhere", page)

    def test_nothing_is_cached_and_the_passcode_moves_to_a_cookie(self):
        self.pictures(2)
        build(self.tmp / "idx", self.tmp / "pix")
        wall = self.start(self.tmp / "idx")
        code = wall.STATE["passcode"]
        # no cookie and no code: refused (on this machine too)
        self.assertEqual(self.get("/status", cookie=False)[0], 403)
        st, body, r = self.get(f"/?k={code}", cookie=False)
        self.assertEqual(st, 303)
        self.assertEqual(r.getheader("Location"), "/")
        sc = r.getheader("Set-Cookie")
        self.assertIn("HttpOnly", sc)
        self.assertIn("SameSite=Strict", sc)
        self.assertIn(wall.STATE["cookie"], sc)
        # the page itself never puts the passcode in a URL
        script = wall.PAGE.split("<script>")[1]
        self.assertNotIn("?k=", script)
        self.assertNotIn("location.search", script)
        st, d = self.get_json("/search?q=2016")
        self.assertEqual(st, 200)
        st, img, r = self.get(f"/thumb/{d['hits'][0]['sha256']}")
        self.assertEqual(st, 200)
        cc = r.getheader("Cache-Control")
        self.assertIn("no-store", cc)
        self.assertIn("private", cc)
        self.assertNotIn("public", cc)

    def test_localhost_mode_checks_the_host_name(self):
        self.pictures(1)
        build(self.tmp / "idx", self.tmp / "pix")
        self.start(self.tmp / "idx")
        self.assertEqual(self.get("/status", host="attacker.example:80")[0], 403)
        self.assertEqual(self.get("/status")[0], 200)

    def test_show_me_my_life_is_this_mac_only_unless_asked(self):
        # Stress test privacy#9: go.py started the wall on 0.0.0.0 by default.
        (self.tmp / "pix").mkdir()
        p, left = run_child(self.tmp, """
            import json, sys
            sys.path.insert(0, "tools")
            import go, wall
            from pathlib import Path
            go.missing = lambda pairs: []
            go.ask_folder = lambda: Path(sys.argv[0]).parent
            go.count_indexed = lambda: 5
            class Done(Exception): pass
            seen = {}
            def fake_serve(index, port, lan=False, **kw):
                seen["lan"] = lan
                raise Done()
            wall.serve = fake_serve
            import subprocess
            subprocess.run = lambda *a, **k: type("R", (), {"returncode": 0})()
            for argv in ([], ["--lan"]):
                try:
                    go.main(argv)
                except Done:
                    pass
                seen.setdefault("runs", []).append(seen["lan"])
            print("RESULT " + json.dumps(seen["runs"]))
        """, stdin="\n")
        self.assertEqual(left, [], "wrote into the home folder")
        self.assertEqual(result_of(p), [False, True])


# ======================================================================
# I-53  the wall honours 'rather not' and the rules; opens quietly; hides
# ======================================================================
class I53WallRespect(WallCase):
    def kabul_today(self):
        """Four Kabul photos and three Halifax photos, all taken on this day
        in other years."""
        today = dt.date.today()
        rows, files = [], []
        for i, (year, day_off) in enumerate(((2011, 0), (2011, 0), (2011, 0), (2011, 0))):
            f = jpeg(self.tmp / "pix" / f"kab{i}.jpg", (200, 10 * i, 10))
            s = sha_of(f"kab{i}")
            rows.append((s, f, f"{year}-{today:%m-%d}T0{i}:00:00", "Afghanistan", "Kabul"))
        for i in range(3):
            f = jpeg(self.tmp / "pix" / f"hal{i}.jpg", (10, 200, 10 * i))
            rows.append((sha_of(f"hal{i}"), f, f"2023-{today:%m-%d}T1{i}:00:00",
                         "Canada", "Halifax"))
        add_rows(self.tmp / "idx", rows)
        return [r[0] for r in rows[:4]], [r[0] for r in rows[4:]]

    def test_declined_moment_is_never_on_the_wall(self):
        # Stress test family#10: a declined Kabul moment appeared 'on this day'
        # and in search on the shared TV.
        kab, hal = self.kabul_today()
        c = Conscience(self.tmp / "conscience.json")
        life = Life(c)
        rem = Reminisce(c, life, self.tmp / "idx")
        p = rem.next_prompt(owner_opened=True)
        self.assertEqual(p["moment_id"][:6], "canada")       # the gentle one first
        rem.skip(p["moment_id"])
        p = rem.next_prompt(owner_opened=True)
        self.assertEqual(p["moment_id"][:11], "afghanistan")
        rem.decline(p["moment_id"])
        self.start(self.tmp / "idx", lan=True)
        st, d = self.get_json("/on-this-day")
        self.assertEqual(st, 200)
        shown = {h["sha256"] for h in d["hits"]}
        self.assertEqual(shown, set(hal))
        st, d = self.get_json("/search?q=Afghanistan")
        self.assertEqual(d["hits"], [])
        self.assertEqual(self.get(f"/thumb/{kab[0]}")[0], 404)
        # a photo added to that week later is hidden too
        today = dt.date.today()
        extra = jpeg(self.tmp / "pix" / "kab9.jpg", (1, 2, 3))
        add_rows(self.tmp / "idx", [(sha_of("kab9"), extra, f"2011-{today:%m-%d}T09:00:00",
                                     "Afghanistan", "Kabul")])
        self.wall.STATE.pop("hidden", None)
        st, d = self.get_json("/search?q=Afghanistan")
        self.assertEqual(d["hits"], [])

    def test_never_on_the_wall_and_raise_it_first_rules(self):
        kab, hal = self.kabul_today()
        c = Conscience(self.tmp / "conscience.json")
        rem = Reminisce(c, Life(c), self.tmp / "idx")
        rem.keep_out("never_on_the_wall", "Halifax")
        ConscienceRules(c).set_rule("reaction", "afghanistan,war",
                                    "Never bring up Afghanistan unless I raise it first.")
        self.start(self.tmp / "idx", lan=True)
        st, d = self.get_json("/on-this-day")
        self.assertEqual(d["hits"], [], "surfaced by itself")
        st, d = self.get_json("/search?q=Halifax")
        self.assertEqual(d["hits"], [])
        st, d = self.get_json("/search?q=Afghanistan")      # someone asked for it
        self.assertEqual({h["sha256"] for h in d["hits"]}, set(kab))

    def test_opens_on_a_neutral_screen_with_a_hide_button_and_idle_hide(self):
        import wall
        script = wall.PAGE.split("<script>")[1]
        top_level_calls = [ln for ln in script.splitlines() if ln.strip() == "today();"]
        self.assertEqual(top_level_calls, [], "opens on 'on this day' by itself")
        self.assertIn('<button id="hide">', wall.PAGE)
        self.assertIn("veil.addEventListener('click'", script)
        self.assertIn("setTimeout(hide, IDLE_MS)", script)
        self.assertIn("touchstart", script)

    def test_status_does_not_reveal_the_index_location(self):
        self.pictures(1)
        build(self.tmp / "idx", self.tmp / "pix")
        self.start(self.tmp / "idx")
        st, d = self.get_json("/status")
        self.assertEqual(set(d), {"photos", "model_loaded"})
        self.assertNotIn(str(self.tmp), json.dumps(d))


# ======================================================================
# I-61  Finder paths, Photos libraries
# ======================================================================
class I61Folders(Temp):
    def test_unescape_dragged_paths(self):
        sys.path.insert(0, str(REPO / "tools"))
        import go
        self.assertEqual(go.unescape("/Users/l/Family\\ Photos "), "/Users/l/Family Photos")
        self.assertEqual(go.unescape("/x/Photos\\ d\\'été "), "/x/Photos d'été")
        self.assertEqual(go.unescape("/x/Kandahar\\ \\(2011\\) "), "/x/Kandahar (2011)")
        self.assertEqual(go.unescape("'/x/Uncle Bill' "), "/x/Uncle Bill")
        self.assertEqual(go.unescape("/x/Petting Zoo"), "/x/Petting Zoo")
        self.assertEqual(go.unescape("   "), "")

    def test_ask_folder_unescapes_and_asks_again(self):
        # Stress test accessibility#4: a dragged '.../Family\\ Photos ' made
        # 'Show me my life' say there was nothing there, and quit.
        fam = self.tmp / "Family Photos"
        fam.mkdir()
        dragged = str(fam).replace(" ", "\\ ") + " "
        p, left = run_child(self.tmp, """
            import json, sys
            sys.path.insert(0, "tools")
            import go
            print("RESULT " + json.dumps(str(go.ask_folder())))
        """, stdin=f"/no/such/folder\n{dragged}\n")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(result_of(p), str(fam))
        self.assertIn("Try again", p.stdout)
        conf = json.loads((self.tmp / "home" / ".jefferey" / "wall.conf").read_text())
        self.assertEqual(conf["photos"], str(fam))

    def test_walk_skips_photos_libraries_hidden_folders_and_shadows(self):
        pix = self.tmp / "Pictures"
        jpeg(pix / "a.jpg")
        lib = pix / "Photos Library.photoslibrary"
        jpeg(lib / "originals" / "0" / "x.jpg", (1, 1, 1))
        jpeg(lib / "resources" / "derivatives" / "x.jpg", (2, 2, 2))
        jpeg(pix / ".selfcloud" / "thumbs" / "t.jpg", (3, 3, 3))
        (pix / "._a.jpg").write_bytes(b"\0\5\26\7")
        skipped = []
        found = [p.name for p in photo_index.walk(pix, skipped)]
        self.assertEqual(found, ["a.jpg"])
        self.assertEqual([p.name for p in skipped], [lib.name])

    def test_go_explains_a_photos_library(self):
        pix = self.tmp / "Pictures"
        jpeg(pix / "a.jpg")
        jpeg(pix / "Photos Library.photoslibrary" / "originals" / "x.jpg", (1, 1, 1))
        p, left = run_child(self.tmp, """
            import json, sys
            sys.path.insert(0, "tools")
            import go
            print("RESULT " + json.dumps(str(go.ask_folder())))
        """, stdin=f"{pix / 'Photos Library.photoslibrary'}\n{pix}\n")
        self.assertEqual(result_of(p), str(pix))
        self.assertIn("Export Unmodified Originals", p.stdout)


# ======================================================================
# I-63  a renamed drive
# ======================================================================
class I63Rename(WallCase):
    def test_renamed_drive_with_the_index_on_it(self):
        # Stress test drive#9: after renaming 'Self Cloud' to 'Self-Cloud' every
        # stored path was dead and wall.thumbnail returned None.
        old = self.tmp / "Volumes" / "Self Cloud"
        pics = [jpeg(old / "library" / f"IMG_{i}.jpg", (i * 60, 5, 5), "2016:07:14 12:00:00")
                for i in range(3)]
        shas = [photo_index.sha256(p) for p in pics]
        build(old / ".selfcloud" / "jefferey" / "photo-index", old / "library")
        new = self.tmp / "Volumes" / "Self-Cloud"
        os.rename(old, new)
        idx = PhotoIndex(new / ".selfcloud" / "jefferey" / "photo-index", create=False)
        for s in shas:
            self.assertIsNotNone(idx.where(s), "photo lost after the rename")
        hits = recall.run(idx, recall.parse("2016"), None)
        self.assertTrue(all(Path(h["path"]).is_file() for h in hits))
        self.start(new / ".selfcloud" / "jefferey" / "photo-index")
        self.assertEqual(self.get(f"/thumb/{shas[0]}")[0], 200)

    def test_rebuild_follows_photos_to_the_renamed_drive(self):
        old = self.tmp / "Volumes" / "Self Cloud"
        pics = [jpeg(old / "library" / f"IMG_{i}.jpg", (i * 60, 5, 5)) for i in range(3)]
        build(self.tmp / "idx", old / "library")
        new = self.tmp / "Volumes" / "Self-Cloud"
        os.rename(old, new)
        build(self.tmp / "idx", new / "library")
        idx = PhotoIndex(self.tmp / "idx")
        paths = [r[0] for r in idx.db.execute("SELECT path FROM photos")]
        self.assertTrue(paths and all(Path(p).is_file() for p in paths), paths)
        self.assertEqual(idx.db.execute(
            "SELECT COUNT(*) FROM photos WHERE missing_since IS NOT NULL").fetchone()[0], 0)

    def test_an_index_from_before_this_fix_follows_a_rename(self):
        old = self.tmp / "Volumes" / "Self Cloud"
        pic = jpeg(old / "library" / "IMG_0.jpg")
        root = old / ".selfcloud" / "jefferey" / "photo-index"
        root.mkdir(parents=True)
        db = sqlite3.connect(root / "index.sqlite")
        db.executescript("""
            CREATE TABLE photos (sha256 TEXT PRIMARY KEY, path TEXT, bytes INTEGER,
                mtime REAL, seen_at TEXT, taken_at TEXT, lat REAL, lon REAL,
                place TEXT, country TEXT);
            CREATE TABLE vectors (sha256 TEXT PRIMARY KEY, dim INTEGER, vec BLOB);""")
        db.execute("INSERT INTO photos (sha256, path, taken_at) VALUES (?,?,?)",
                   ("a" * 64, str(pic), "2016-07-14T12:00:00"))
        db.commit()
        db.close()
        (root / "manifest.json").write_text(json.dumps(
            {"model": "fake", "pretrained": "none", "dim": 8,
             "weights_dir": str(root / "models")}))
        new = self.tmp / "Volumes" / "Self-Cloud"
        os.rename(old, new)
        idx = PhotoIndex(new / ".selfcloud" / "jefferey" / "photo-index", create=False)
        self.assertEqual(idx.where("a" * 64), new / "library" / "IMG_0.jpg")

    def test_show_me_my_life_remembers_the_folder_across_a_rename(self):
        old = self.tmp / "Volumes" / "Self Cloud"
        mark_drive(old)
        (old / "library").mkdir()
        code = """
            import json, sys
            sys.path.insert(0, "tools")
            import go
            print("RESULT " + json.dumps(str(go.ask_folder())))
        """
        p, left = run_child(self.tmp, code, stdin=f"{old / 'library'}\n",
                            SELFCLOUD_ROOT=str(old), SELFCLOUD_INDEX=None)
        self.assertEqual(result_of(p), str(old / "library"))
        new = self.tmp / "Volumes" / "Self-Cloud"
        os.rename(old, new)
        p, left = run_child(self.tmp, code, stdin="", SELFCLOUD_ROOT=str(new),
                            SELFCLOUD_INDEX=None)
        self.assertEqual(result_of(p), str(new / "library"))


# ======================================================================
# X-01  recall finds the drive's index, and a question never makes one
# ======================================================================
class X01IndexLocation(Temp):
    def test_recall_command_uses_the_drive_index(self):
        # Stress test photos#12: with the index on the drive, recall.py '2016'
        # said '0 photo(s)' and created ~/.selfcloud/photo-index.
        drive = mark_drive(self.tmp / "drive")
        add_rows(drive / ".selfcloud" / "jefferey" / "photo-index",
                 trip("x", "Cuba", "Varadero", (1, 2), year=2016))
        p, left = run_child(self.tmp, """
            import sys
            sys.path.insert(0, "tools")
            import recall
            sys.exit(recall.main(["2016"]))
        """, SELFCLOUD_ROOT=str(drive), SELFCLOUD_INDEX=None)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("2 photo(s)", p.stdout)
        self.assertEqual(left, [], "created something in the home folder")

    def test_a_question_never_creates_an_index(self):
        p, left = run_child(self.tmp, """
            import sys
            sys.path.insert(0, "tools")
            import recall
            sys.exit(recall.main(["2016"]))
        """, SELFCLOUD_INDEX=None)
        self.assertEqual(p.returncode, 1)
        self.assertIn("No photographs have been read yet", p.stdout)
        self.assertEqual(left, [], "created an index in the home folder")

    def test_show_me_my_life_asks_for_the_drive_instead_of_a_laptop_index(self):
        # Stress test photos#12: with the drive unplugged, go.py started
        # reading the photographs again into the laptop's home folder.
        (self.tmp / "home" / ".jefferey").mkdir(parents=True)
        (self.tmp / "home" / ".jefferey" / "wall.conf").write_text(json.dumps(
            {"photos": "/Volumes/Self Cloud/library", "drive": "Self Cloud"}))
        p, left = run_child(self.tmp, """
            import sys
            sys.path.insert(0, "tools")
            import go
            sys.exit(go.main([]))
        """, SELFCLOUD_INDEX=None)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("isn't plugged in", p.stdout)
        self.assertEqual(left, [str(self.tmp / "home" / ".jefferey"),
                                str(self.tmp / "home" / ".jefferey" / "wall.conf")],
                         "read photographs into the home folder")

    def test_readers_never_create_an_index(self):
        where = self.tmp / "nothing-here"
        with self.assertRaises(photo_index.NoIndex):
            PhotoIndex(where, create=False)
        with self.assertRaises(SystemExit):
            photo_index.cmd_search(argparse.Namespace(index=str(where), query="x", top=3))
        import wall
        with mock.patch("builtins.print"):
            self.assertEqual(wall.main(["--index", str(where), "--port", "0"]), 1)
        self.assertFalse(where.exists())



# ======================================================================
# After the fixes: the skeptics' and regression hunters' reproductions
# against the first round (verify I-15, I-33, I-53, I-61, X-01 and the
# regressions). Each failed on 35e4e9b, unless marked as a guard.
# ======================================================================
class AfterTheFixes(WallCase):

    # ------------------------------------------------------- verify I-15
    def test_an_old_memorys_photos_move_to_its_moment_when_the_file_is_read(self):
        # no photo index at all: the move used to wait for an album tool
        old = {"_rev": 2, "facts": [], "priorities": [], "goals": [], "corrections": [],
               "permissions": {}, "actions": [], "observations": [], "opportunities": [],
               "memories": [{"text": "We walked over the Chain Bridge.",
                             "tags": ["Hungary", "2011", "moment:hungary-20111010"],
                             "photos": [TRIPPING_SHA, sha_of("b")], "visibility": "private"}]}
        f = self.tmp / "conscience.json"
        f.write_text(json.dumps(old))
        c = Conscience(f)
        self.assertNotIn("photos", c.data["memories"][0])
        m = c.data["album"]["moments"]["hungary-20111010"]
        self.assertEqual(set(m["shas"]), {TRIPPING_SHA, sha_of("b")})
        self.assertEqual(m["status"], "told")
        self.assertIn("photos", json.loads(f.read_text())["memories"][0],
                      "reading must not write")
        p, left = run_child(self.tmp, """
            import asyncio, json, sys
            sys.path.insert(0, "connector")
            import jefferey_mcp as m
            t = asyncio.run(m.mcp.call_tool("who_am_i", {})).content[0].text
            m.life.add_memory("A second story.")          # a real save
            print("RESULT " + json.dumps({"text": t}))
        """, JEFFEREY_CLIENT="jefferey", SELFCLOUD_INDEX=str(self.tmp / "no-index"))
        r = result_of(p)
        self.assertNotIn('"refused"', r["text"])
        self.assertNotIn(TRIPPING_SHA, r["text"])
        disk = json.loads(f.read_text())
        self.assertNotIn("photos", disk["memories"][0])
        self.assertIn(TRIPPING_SHA, disk["album"]["moments"]["hungary-20111010"]["shas"])

    # ------------------------------------------------------- verify I-33
    def test_a_rule_about_mum_closes_the_moment_of_her_funeral(self):
        idx, c, life, rem = self.album(
            trip("bud", "Hungary", "Budapest", (10, 11, 12), year=2019, month=2)
            + trip("cub", "Cuba", "Varadero", (1, 2, 3), year=2016, month=7), deep=True)
        life.add_person("Ilona", "mum", notes="died February 2019, funeral in Budapest")
        ConscienceRules(c).set_rule("reaction", "mother", "Don't bring up Mum's funeral.")
        first = rem.next_prompt()
        self.assertEqual(first["moment_id"], "cuba-20160701")
        rem.record(first["moment_id"], "We swam every day at Varadero.")
        self.assertIsNone(rem.next_prompt()["moment_id"])
        self.assertIsNone(rem.next_prompt(owner_opened=True)["moment_id"])

    def test_rather_not_and_only_if_i_bring_it_up_close_a_moment(self):
        for words in ("I'd rather not talk about Afghanistan. Only if I bring it up myself.",
                      "Je préfère ne pas en parler."):
            sub = self.tmp / f"r{len(words)}"
            sub.mkdir()
            add_rows(sub / "idx", trip("afg", "Afghanistan", "Kandahar", (3, 4, 5))
                     + trip("cub", "Cuba", "Varadero", (1, 2, 3), year=2016, month=7))
            c = Conscience(sub / "conscience.json")
            life = Life(c)
            trusted(c, life, deep=True)
            rem = Reminisce(c, life, sub / "idx")
            ConscienceRules(c).set_rule("reaction", "afghanistan", words)
            rem.record(rem.next_prompt()["moment_id"], "Varadero was lovely.")
            self.assertIsNone(rem.next_prompt()["moment_id"], words)

    # ------------------------------------------------------- regression
    def test_the_owners_own_sitting_is_never_told_to_wait_a_week(self):
        idx, c, life, rem = self.album(trip("cub", "Cuba", "Varadero", (1, 2, 3), year=2016))
        self.assertEqual(rem.next_prompt()["moment_id"], "cuba-20161001")   # an engine asked
        self.assertIsNone(rem.next_prompt()["moment_id"])                    # it rests for engines
        self.assertEqual(rem.next_prompt(owner_opened=True)["moment_id"], "cuba-20161001")

    # ------------------------------------------------------- verify I-53
    def test_two_word_entries_work_and_the_owner_is_told_the_truth(self):
        today = dt.date.today()
        rows = []
        for i in range(3):
            f = jpeg(self.tmp / "pix" / f"h{i}.jpg", (10, 200, 10 * i))
            rows.append((sha_of(f"h{i}"), f, f"2023-{today:%m-%d}T1{i}:00:00", "Canada",
                         "Halifax"))
        f = jpeg(self.tmp / "pix" / "ny.jpg", (200, 10, 10))
        rows.append((sha_of("ny"), f, f"2019-{today:%m-%d}T10:00:00", "United States",
                     "New York City"))
        add_rows(self.tmp / "idx", rows)
        c = Conscience(self.tmp / "conscience.json")
        rem = Reminisce(c, Life(c), self.tmp / "idx")
        r = rem.keep_out("never_on_the_wall", "Halifax 2023, New York, Nova Scotia")
        self.assertEqual(r["matching"], {"Halifax 2023": 3, "New York": 1, "Nova Scotia": 0})
        lines = " ".join(reminisce._kept_out_lines("never_on_the_wall",
                                                  "Halifax 2023, New York, Nova Scotia", r))
        self.assertIn("'Halifax 2023' (photographs that are both) — 3 photographs", lines)
        self.assertIn("nothing in the photographs matches it yet", lines)
        self.start(self.tmp / "idx")
        st, d = self.get_json("/on-this-day")
        self.assertEqual(d["hits"], [])
        for q in ("Halifax", "New York"):
            st, d = self.get_json("/search?q=" + up.quote(q))
            self.assertEqual(d["hits"], [], q)

    # ------------------------------------------------- verify I-61, X-01
    def test_on_another_mac_return_never_reads_that_macs_pictures(self):
        drive = mark_drive(self.tmp / "Volumes" / "Self Cloud")
        jpeg(self.tmp / "home" / "Pictures" / "not-his.jpg")
        code = """
            import json, sys
            sys.path.insert(0, "tools")
            import go
            print("RESULT " + json.dumps(str(go.ask_folder())))
        """
        p, left = run_child(self.tmp, code, stdin="\n" * 6, SELFCLOUD_ROOT=str(drive),
                            SELFCLOUD_INDEX=None)
        self.assertNotEqual(p.returncode, 0, "it took this Mac's Pictures")
        self.assertIn("No folder was given", p.stdout)
        (drive / "library").mkdir()
        p, left = run_child(self.tmp, code, stdin="\n", SELFCLOUD_ROOT=str(drive),
                            SELFCLOUD_INDEX=None)
        self.assertEqual(result_of(p), str(drive / "library"))
        self.assertTrue((drive / ".selfcloud" / "jefferey" / "wall.conf").is_file())
        self.assertEqual([x for x in left if "wall.conf" in x], [],
                         "the folder was remembered on the other Mac")

    def test_an_old_remembered_folder_on_an_unplugged_drive_is_the_drive(self):
        (self.tmp / "home" / ".jefferey").mkdir(parents=True)
        (self.tmp / "home" / ".jefferey" / "wall.conf").write_text(json.dumps(
            {"photos": "/Volumes/Self Cloud/library"}))           # no 'drive': older code
        jpeg(self.tmp / "home" / "Pictures" / "a.jpg")
        p, left = run_child(self.tmp, """
            import sys
            sys.path.insert(0, "tools")
            import go
            sys.exit(go.main([]))
        """, stdin="\n" * 6, SELFCLOUD_INDEX=None)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("'Self Cloud', and it isn't plugged in", p.stdout)
        self.assertFalse(any("photo-index" in x for x in left), "began a laptop index")

    def test_the_make_drive_window_undoes_every_escape(self):
        # guard: fixed by the drive package (provision_drive --interactive)
        import provision_drive as pd
        self.assertEqual(pd._clean_path("/Volumes/Laszlo\\'s\\ Drive\\ \\(2\\) "),
                         "/Volumes/Laszlo's Drive (2)")
        self.assertEqual(pd._clean_path("'/Volumes/Self Cloud'"), "/Volumes/Self Cloud")

    # ------------------------------------------------------- regressions
    def test_a_photo_kept_in_icloud_stays_on_the_wall(self):
        pics = self.pictures(4)
        build(self.tmp / "idx", self.tmp / "pix")
        self.start(self.tmp / "idx")
        idx = PhotoIndex(self.tmp / "idx", create=False)
        shas = [r[0] for r in idx.db.execute("SELECT sha256 FROM photos ORDER BY path")]
        for s in shas:
            self.assertEqual(self.get(f"/thumb/{s}")[0], 200)
        # 'Optimize Mac Storage': the first is only a placeholder now; the
        # second was deleted
        os.unlink(pics[0])
        (pics[0].parent / f".{pics[0].name}.icloud").write_bytes(b"bplist00")
        os.unlink(pics[1])
        build(self.tmp / "idx", self.tmp / "pix")
        self.wall.STATE.pop("hidden", None)
        miss = dict(idx.db.execute("SELECT path, missing_since FROM photos"))
        self.assertIsNone(miss[str(pics[0])], "a photo in iCloud was called deleted")
        self.assertIsNotNone(miss[str(pics[1])])
        by_path = dict(idx.db.execute("SELECT path, sha256 FROM photos"))
        self.assertEqual(self.get(f"/thumb/{by_path[str(pics[0])]}")[0], 200)
        self.assertEqual(self.get(f"/thumb/{by_path[str(pics[1])]}")[0], 404)
        st, d = self.get_json("/search?q=2016")
        shown = {h["sha256"] for h in d["hits"]}
        self.assertIn(by_path[str(pics[0])], shown)
        self.assertNotIn(by_path[str(pics[1])], shown)

    def test_a_drive_pulled_while_the_wall_is_up_is_said_plainly(self):
        # guard: fixed in 35e4e9b
        self.pictures(2)
        build(self.tmp / "idx", self.tmp / "pix")
        wall = self.start(self.tmp / "idx")
        os.rename(self.tmp / "idx", self.tmp / "idx-away")         # the drive went
        with mock.patch.object(wall, "search", side_effect=sqlite3.OperationalError(
                "disk I/O error")):
            st, d = self.get_json("/search?q=2016")
        self.assertEqual((st, d["error"]), (503, wall.UNREACHABLE))

    def test_the_owners_steps_and_the_rules_say_what_the_album_does_now(self):
        # guard: docs updated in 35e4e9b
        start = (REPO / "START_HERE.md").read_text()
        for w in ("keep-off-wall", "never-ask", "reopen", "phone or the TV",
                  "only where the browser understands speech"):
            self.assertIn(w, start, w)
        rules = (REPO / "connector" / "directives.md").read_text()
        for w in ("skip_story", "Not yet", "Rather not"):
            self.assertIn(w, rules, w)

if __name__ == "__main__":
    unittest.main()
