"""
Crash-proof storage — regression tests for the October 2026 stress test.

    I-05  reads wrote the whole store and a backup copy; history lasted ~20 calls
    I-19  hand edits were silently undone, and a deleted fact re-sent
    I-20  no restore; a later recovery brought back the abandoned version
    I-49  a tear inside an accented letter crashed every launch
    I-50  JEFFEREY_ALLOW_RESET=1 destroyed the damaged original
    I-51  no full flush on macOS; backup copies not written atomically
    I-52  a failed save stayed in memory and was later written anyway
    I-62  the memory file and its copies were readable by every account
    I-68  a damaged memory looked like a broken program / a dead connection

Each test makes its own temporary folder and environment. Nothing here
touches the real home folder: HOME is pointed at a throwaway folder before
anything from connector/ is imported, and checked empty at the end.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
CONNECTOR = ROOT / "connector"
PY = sys.executable

# --- isolate BEFORE importing anything from connector/ (modules bind at import)
_MOD_TMP = Path(tempfile.mkdtemp(prefix="jf-storage-"))
(_MOD_TMP / "home").mkdir()
for _k in list(os.environ):
    if _k.startswith(("JEFFEREY_", "SELFCLOUD_")):
        del os.environ[_k]
os.environ.update(
    HOME=str(_MOD_TMP / "home"),
    JEFFEREY_CONSCIENCE_PATH=str(_MOD_TMP / "unused" / "conscience.json"),
    JEFFEREY_EGRESS=str(_MOD_TMP / "unused" / "egress.jsonl"),
    JEFFEREY_DOOR=str(_MOD_TMP / "unused" / "door-shut"),
)
sys.path.insert(0, str(CONNECTOR))

import conscience as cmod                                      # noqa: E402
from conscience import (Conscience, ConscienceConflict,         # noqa: E402
                        ConscienceCorrupt, ConscienceNeedsFixing,
                        ConscienceSaveFailed)
from selfcloud import SelfCloud                                 # noqa: E402


def tearDownModule():
    left = list((_MOD_TMP / "home").rglob("*"))
    shutil.rmtree(_MOD_TMP, ignore_errors=True)
    assert not left, f"a test wrote into the home folder: {left}"


PRELUDE = f"""
import sys, os, json, asyncio
sys.path.insert(0, {str(CONNECTOR)!r})
def mcp_call(m, name, args=None):
    r = asyncio.run(m.mcp.call_tool(name, args or {{}}))
    items = [json.loads(c.text) for c in r.content]
    return items[0] if len(items) == 1 else items
def out(obj):
    print("RESULT " + json.dumps(obj, default=str))
"""


class StoreTest(unittest.TestCase):
    """A fresh folder per test, and helpers to run a surface in a subprocess
    the way an engine would reach it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-st-"))
        (self.tmp / "home").mkdir()
        self.store = self.tmp / "conscience.json"

    def tearDown(self):
        left = list((self.tmp / "home").rglob("*"))
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.assertEqual(left, [], "a surface wrote into the home folder")

    def env(self, **extra) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("JEFFEREY_", "SELFCLOUD_"))}
        env.update(HOME=str(self.tmp / "home"),
                   JEFFEREY_CONSCIENCE_PATH=str(self.store),
                   JEFFEREY_EGRESS=str(self.tmp / "egress.jsonl"),
                   JEFFEREY_DOOR=str(self.tmp / "door-shut"),
                   SELFCLOUD_INDEX=str(self.tmp / "photo-index"),
                   SELFCLOUD_VOICE=str(self.tmp / "voice"),
                   SELFCLOUD_DISCS=str(self.tmp / "discs"),
                   PYTHONDONTWRITEBYTECODE="1")
        env.update({k: str(v) for k, v in extra.items()})
        return env

    def py(self, code: str, check: bool = True, **extra):
        p = subprocess.run([PY, "-c", PRELUDE + textwrap.dedent(code)],
                           env=self.env(**extra), cwd=self.tmp,
                           capture_output=True, text=True, timeout=300)
        if check and p.returncode != 0:
            raise AssertionError(f"subprocess failed:\n{p.stdout}\n{p.stderr}")
        results = [l[7:] for l in p.stdout.splitlines() if l.startswith("RESULT ")]
        return json.loads(results[-1]) if results else None

    # helpers on the files themselves
    def copies_holding(self, text: str) -> int:
        n = 0
        hist = self.store.parent / (self.store.stem + ".history")
        for p in list(hist.glob("*.json")) + list((hist / "pinned").glob("*.json")):
            if text in p.read_text(encoding="utf-8", errors="replace"):
                n += 1
        return n

    def tear(self, keep: int) -> None:
        """Cut the store as a power cut would. A torn file carries the time of
        JEFFEREY's last write, a moment before its copy in history — not the
        time a test got round to cutting it."""
        self.store.write_bytes(self.store.read_bytes()[:keep])
        newest = max(self.snapshot_files(), key=lambda p: p.stat().st_mtime)
        t = newest.stat().st_mtime
        os.utime(self.store, (t, t))

    def snapshot_files(self) -> list[Path]:
        hist = self.store.parent / (self.store.stem + ".history")
        return sorted(hist.glob("*.json"))


# ======================================================================= I-05
class ReadsDoNotWrite(StoreTest):
    """I-05: every read wrote the whole store and a snapshot."""

    def test_reads_on_the_terminal_never_rewrite_the_store(self):
        r = self.py("""
            import jefferey_chat as jc
            for i in range(5):
                jc.dispatch_tool("remember_fact", {"fact": f"fact {i} metformin"})
            p = jc.conscience.path
            before = (p.read_bytes(), os.stat(p).st_ino, len(jc.conscience.snapshots()))
            bad = []
            for _ in range(10):
                for t, a in [("explain_basis", {"topic": "metformin"}), ("priorities_for", {}),
                             ("daily_brief", {}), ("who_am_i", {}), ("story_gaps", {}),
                             ("list_rules", {}), ("action_log", {}), ("selfcloud_status", {})]:
                    r = jc.dispatch_tool(t, a)
                    if isinstance(r, dict) and r.get("refused"):
                        bad.append((t, r))
            after = (p.read_bytes(), os.stat(p).st_ino, len(jc.conscience.snapshots()))
            out({"bad": bad, "same_bytes": before[0] == after[0],
                 "same_inode": before[1] == after[1], "snaps": [before[2], after[2]],
                 "logged": len(jc.cloud.access_log(1000)),
                 "in_store": "selfcloud_access_log" in json.loads(p.read_text())})
        """)
        self.assertEqual(r["bad"], [])
        self.assertTrue(r["same_bytes"] and r["same_inode"], "a read rewrote the store")
        self.assertEqual(r["snaps"][0], r["snaps"][1], "a read used up a backup copy")
        self.assertGreaterEqual(r["logged"], 70, "reads must still be in the access log")
        self.assertFalse(r["in_store"], "the access log is back inside the store")
        log = self.tmp / "conscience.access.jsonl"
        self.assertTrue(log.exists())

    def test_a_forgotten_fact_survives_forty_reads_in_history(self):
        # The original repro (durability#0 / ops#0): a forget, then ordinary
        # reads, and no copy anywhere held the fact after ~20 calls.
        r = self.py("""
            import jefferey_mcp as m
            for i in range(14):
                mcp_call(m, "remember_fact", {"fact": f"ordinary fact {i}"})
            mcp_call(m, "remember_fact", {"fact": "Served in Kandahar in 2011"})
            gone = mcp_call(m, "forget", {"contains": "Kandahar"})
            for _ in range(20):
                mcp_call(m, "get_conscience")
                mcp_call(m, "explain_basis", {"topic": "weather"})
            out({"gone": gone, "rev": json.loads(m.conscience.path.read_text())["_rev"],
                 "pinned": [h["pinned"] for h in m.conscience.history(None) if h["pinned"]]})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r["gone"].get("removed_facts"), 1, r)
        self.assertGreaterEqual(self.copies_holding("Kandahar"), 1,
                                "no copy holds the forgotten fact any more")
        self.assertIn("before forget", r["pinned"])
        self.assertNotIn("Kandahar", self.store.read_text())

    def test_refused_calls_from_a_guest_key_change_nothing(self):
        self.py("""
            import jefferey_chat as jc
            jc.dispatch_tool("remember_fact", {"fact": "something real"})
        """)
        r = self.py("""
            import jefferey_chat as jc
            assert jc.access.current_client() == "claude-raw"
            jc.dispatch_tool("explain_basis", {"topic": "x"})   # first use: its key is issued
            p = jc.conscience.path
            before = (p.read_bytes(), len(jc.conscience.snapshots()))
            refused = sum(1 for _ in range(30)
                          if jc.dispatch_tool("remember_fact", {"fact": "spam"}).get("refused"))
            after = (p.read_bytes(), len(jc.conscience.snapshots()))
            out({"refused": refused, "same": before[0] == after[0],
                 "snaps": [before[1], after[1]]})
        """, JEFFEREY_CLIENT="claude-raw")
        self.assertEqual(r["refused"], 30)
        self.assertTrue(r["same"], "refused calls rewrote the store")
        self.assertEqual(r["snaps"][0], r["snaps"][1], "refused calls rotated history")

    def test_family_and_denied_http_calls_do_not_write(self):
        r = self.py("""
            from fastapi.testclient import TestClient
            import jefferey_http as h
            c = TestClient(h.app)
            A = {"Authorization": "Bearer tok-owner-aaaaaaaa"}
            F = {"Authorization": "Bearer tok-family-bbbbbbb"}
            G = {"Authorization": "Bearer tok-gpt-ccccccccc"}
            assert c.post("/facts", json={"fact": "Born in Szeged"}, headers=A).status_code == 200
            c.get("/life", headers=F); c.get("/life/gaps", headers=G)   # keys issued
            p = h.conscience.path
            before = (p.read_bytes(), len(h.conscience.snapshots()))
            fam = [c.get("/life", headers=F).status_code for _ in range(25)]
            gpt = [c.get("/life/gaps", headers=G).status_code for _ in range(20)]
            after = (p.read_bytes(), len(h.conscience.snapshots()))
            out({"fam": sorted(set(fam)), "gpt": sorted(set(gpt)),
                 "same": before[0] == after[0], "snaps": [before[1], after[1]]})
        """, JEFFEREY_HTTP_TOKENS="jefferey:tok-owner-aaaaaaaa,family:tok-family-bbbbbbb,"
                                  "gpt-raw:tok-gpt-ccccccccc")
        self.assertEqual(r["fam"], [200])
        self.assertEqual(r["gpt"], [403])
        self.assertTrue(r["same"], "a family read or a refused call rewrote the store")
        self.assertEqual(r["snaps"][0], r["snaps"][1])

    def test_an_old_store_access_log_is_moved_out_once(self):
        old = {
            "owner": None, "facts": [{"fact": "keep me", "category": "general",
                                      "added": "2026-09-01T10:00:00+0000"}],
            "priorities": [], "goals": [], "corrections": [], "permissions": {},
            "actions": [], "observations": [], "opportunities": [], "_rev": 7,
            "selfcloud_grants": {"jefferey": {"client": "jefferey", "scopes": ["facts.read"],
                                              "active": True, "label": "J", "note": "",
                                              "granted_on": "x", "revoked_on": None}},
            "selfcloud_access_log": [
                {"client": "jefferey", "action": "check", "detail": "facts.read",
                 "allowed": True, "at": f"2026-09-01T10:00:0{i}+0000"} for i in range(3)],
        }
        self.store.write_text(json.dumps(old, indent=2))
        raw = self.store.read_bytes()
        c = Conscience(self.store)
        cloud = SelfCloud(c)
        log = cloud.access_log(10)
        self.assertEqual([e["at"][-7:] for e in log], ["02+0000", "01+0000", "00+0000"])
        self.assertEqual(self.store.read_bytes(), raw, "starting must not rewrite the store")
        Conscience(self.store)                          # read again: no duplicates
        lines = (self.tmp / "conscience.access.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 3)
        c.remember_fact("a real change")
        disk = json.loads(self.store.read_text())
        self.assertNotIn("selfcloud_access_log", disk)
        self.assertEqual([f["fact"] for f in disk["facts"]], ["keep me", "a real change"])
        self.assertIn("jefferey", disk["selfcloud_grants"])
        self.assertEqual(len(SelfCloud(Conscience(self.store)).access_log(10)), 3)

    def test_a_read_still_works_when_the_access_log_cannot_be_written(self):
        c = Conscience(self.store)
        cloud = SelfCloud(c)
        cloud.grant("claude-raw")
        with mock.patch.object(cmod.AppendLog, "_append_locked",
                               side_effect=OSError(30, "Read-only file system")):
            self.assertTrue(cloud.check_access("claude-raw", "facts.read")["allowed"])
        self.assertTrue(any("access log" in n["what"] for n in c.notices()))

    def test_changes_that_change_nothing_write_nothing(self):
        c = Conscience(self.store)
        c.remember_fact("one")
        raw, n = self.store.read_bytes(), len(self.snapshot_files())
        self.assertEqual(c.forget_fact("zzz-nothing"), 0)
        self.assertEqual(c.close_goal("zzz-nothing"), 0)
        self.assertEqual(c.resolve_opportunity("zzz-nothing"), 0)
        SelfCloud(c).remove_scope("nobody", "facts.read")
        self.assertEqual(self.store.read_bytes(), raw)
        self.assertEqual(len(self.snapshot_files()), n)

    def test_history_is_kept_by_time_not_by_count(self):
        c = Conscience(self.store)
        c.remember_fact("seed")
        hist = c.history_dir
        for p in hist.glob("*.json"):
            p.unlink()
        now = 2_000_000_000.0
        made = []

        def make(age_s, rev, pinned=False):
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now - age_s))
            d = c.pinned_dir if pinned else hist
            d.mkdir(parents=True, exist_ok=True)
            name = (f"conscience-before_forget-{stamp}-{rev:06d}.json" if pinned
                    else f"conscience-{stamp}-{rev:06d}.json")
            (d / name).write_text("{}")
            made.append((age_s, d / name))

        rev = 10_000
        for age in range(120 * 86400, 0, -3 * 3600):        # every 3 h for 120 days
            make(age, rev)
            rev += 1
        for age in range(86000, 0, -240):                    # every 4 min, last day
            make(age, rev)
            rev += 1
        make(10 * 86400, 5, pinned=True)
        make(100 * 86400, 4, pinned=True)
        c._prune_locked(now=now)
        kept = {p for _, p in made if p.exists()}
        ages = sorted(a for a, p in made if p in kept and p.parent == hist)
        day = 86400
        last_day = [a for a in ages if a <= day]
        self.assertGreaterEqual(len(last_day), cmod.HISTORY_RECENT_MAX)
        week = [a for a in ages if day < a <= 7 * day]
        self.assertGreater(len(week), 40, "the hourly tier for the week was pruned")
        old = [a for a in ages if 7 * day < a <= 90 * day]
        self.assertGreaterEqual(len(old), 80, "one copy a day for three months")
        self.assertLessEqual(len(old), 84)
        self.assertEqual([a for a in ages if a > 90 * day], [])
        pins = {a for a, p in made if p in kept and p.parent == c.pinned_dir}
        self.assertEqual(pins, {10 * day})

    def test_a_pinned_copy_outlives_a_flood_of_writes(self):
        with mock.patch.object(cmod, "HISTORY_KEEP", 5), \
                mock.patch.object(cmod, "HISTORY_RECENT_MAX", 10):
            c = Conscience(self.store)
            c.remember_fact("Adam is allergic to penicillin")
            self.assertEqual(c.forget_fact("penicillin"), 1)
            for i in range(60):
                c.remember_fact(f"chatter {i}")
            self.assertEqual(sum("penicillin" in p.read_text()
                                 for p in self.snapshot_files()), 0)
            self.assertEqual(self.copies_holding("penicillin"), 1)
            pinned = [h for h in c.history(None) if h["pinned"] == "before forget"]
            self.assertEqual(len(pinned), 1)
            c.restore(pinned[0]["number"])
        self.assertIn("penicillin", self.store.read_text())

    def test_pin_snapshot_helper(self):
        c = Conscience(self.store)
        self.assertIsNone(c.pin_snapshot("before forget"), "nothing written yet")
        c.remember_fact("x")
        p1 = c.pin_snapshot("before erase")
        p2 = c.pin_snapshot("before erase")
        self.assertEqual(p1, p2, "the same state is pinned once")
        self.assertEqual(p1.read_bytes(), self.store.read_bytes())
        c.remember_fact("y")
        with mock.patch.object(cmod, "_write_atomic", side_effect=OSError(28, "No space")):
            with self.assertRaises(ConscienceSaveFailed):
                c.pin_snapshot("before erase")

    def test_parallel_reader_and_writer_do_not_collide(self):
        self.py("""
            import jefferey_chat as jc
            jc.dispatch_tool("remember_fact", {"fact": "seed"})
            jc.access.Gate(jc.cloud, "claude-raw", announce=False).check("facts.read")
        """)
        # Both processes import, say they are ready, and start together; the
        # writer keeps writing until the reader has finished, so they overlap.
        sync = """
            import time
            from pathlib import Path
            def ready_and_wait(me):
                Path(me).touch()
                while not Path("go").exists():
                    time.sleep(0.01)
        """
        writer = PRELUDE + textwrap.dedent(sync) + textwrap.dedent("""
            import jefferey_chat as jc
            ready_and_wait("ready-writer")
            bad = n = 0
            while not Path("reader-done").exists() and n < 3000:
                bad += bool(jc.dispatch_tool("remember_fact", {"fact": f"w{n}"}).get("refused"))
                n += 1
            out({"bad": bad, "n": n})
        """)
        reader = PRELUDE + textwrap.dedent(sync) + textwrap.dedent("""
            import jefferey_mcp as m
            ready_and_wait("ready-reader")
            bad = 0
            for i in range(150):
                try:
                    r = mcp_call(m, "get_conscience")
                    bad += bool(isinstance(r, dict) and r.get("refused"))
                except Exception:
                    bad += 1
            Path("reader-done").touch()
            out({"bad": bad})
        """)
        pw = subprocess.Popen([PY, "-c", writer], env=self.env(), cwd=self.tmp,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        pr = subprocess.Popen([PY, "-c", reader], env=self.env(JEFFEREY_CLIENT="claude-raw"),
                              cwd=self.tmp, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True)
        deadline = time.time() + 120
        while not ((self.tmp / "ready-writer").exists() and (self.tmp / "ready-reader").exists()):
            if time.time() > deadline or pw.poll() is not None or pr.poll() is not None:
                break
            time.sleep(0.02)
        (self.tmp / "go").touch()
        ow, ew = pw.communicate(timeout=300)
        orr, er = pr.communicate(timeout=300)
        res = lambda o: json.loads([l for l in o.splitlines() if l.startswith("RESULT ")][-1][7:])  # noqa: E731
        self.assertEqual(res(orr)["bad"], 0, er[-2000:])
        w = res(ow)
        self.assertGreater(w["n"], 10, "the writer never overlapped the reader")
        self.assertEqual(w["bad"], 0, ew[-2000:])

    def test_first_use_key_is_retried_after_a_conflict(self):
        import access
        a = Conscience(self.store)
        a.remember_fact("from this surface")
        b = Conscience(self.store)
        b.remember_fact("from another engine")          # `a` is now stale
        gate = access.Gate(SelfCloud(a), "claude-raw", announce=False)
        self.assertTrue(gate.check("facts.read")["allowed"])
        self.assertIn("claude-raw", json.loads(self.store.read_text())["selfcloud_grants"])
        self.assertTrue(gate.check("facts.read")["allowed"])


# ======================================================================= I-19
class HandEdits(StoreTest):

    def test_a_hand_edit_with_the_same_revision_is_adopted_not_undone(self):
        r = self.py("""
            import jefferey_mcp as m
            mcp_call(m, "remember_fact", {"fact": "I had an affair in 2009"})
            mcp_call(m, "remember_fact", {"fact": "My doctor is Dr Old"})
            p = m.conscience.path
            d = json.loads(p.read_text())
            d["facts"] = [{"fact": "My doctor is Dr New", "category": "general", "added": "x"}]
            p.write_text(json.dumps(d, indent=2))              # same _rev, by hand
            g = mcp_call(m, "get_conscience")
            sent = [json.loads(l) for l in open(os.environ["JEFFEREY_EGRESS"])
                    if '"get_conscience"' in l][-1]["sent"]
            out({"served": [f["fact"] for f in g["facts"]], "notices": g.get("notices"),
                 "disk": [f["fact"] for f in json.loads(p.read_text())["facts"]],
                 "sent_affair": "affair" in sent})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r["served"], ["My doctor is Dr New"])
        self.assertEqual(r["disk"], ["My doctor is Dr New"])
        self.assertFalse(r["sent_affair"], "the deleted fact was re-sent to the engine")
        self.assertTrue(any("changed outside JEFFEREY" in n["what"] for n in r["notices"]))
        self.assertGreaterEqual(self.copies_holding("affair"), 1, "the pre-edit version is kept")

    def test_a_save_is_refused_when_the_file_changed_underneath(self):
        c = Conscience(self.store)
        c.remember_fact("PIN hint: dog name")
        c.remember_fact("likes jazz")
        d = json.loads(self.store.read_text())
        d["facts"] = [f for f in d["facts"] if "PIN" not in f["fact"]]
        self.store.write_text(json.dumps(d, indent=2))
        with self.assertRaises(ConscienceConflict):
            c.remember_fact("something new")
        self.assertNotIn("PIN hint", self.store.read_text())
        self.assertNotIn("something new", json.dumps(c.data), "a refused save stayed in memory")
        self.assertTrue(c.refresh())
        self.assertNotIn("PIN hint", json.dumps(c.snapshot()))
        c.remember_fact("something new")
        self.assertNotIn("PIN hint", self.store.read_text())

    def test_a_mistake_in_the_file_is_a_plain_result_and_nothing_is_undone(self):
        r = self.py("""
            import jefferey_mcp as m
            mcp_call(m, "remember_fact", {"fact": "first"})
            p = m.conscience.path
            broken = p.read_text().replace('"facts": [', '"facts": [,', 1)
            p.write_text(broken)
            g = mcp_call(m, "get_conscience")
            w = mcp_call(m, "remember_fact", {"fact": "second"})
            unchanged = p.read_text() == broken
            p.write_text(broken.replace('"facts": [,', '"facts": [', 1))
            after = mcp_call(m, "get_conscience")
            out({"g": g, "w": w, "unchanged": unchanged,
                 "after": [f["fact"] for f in after["facts"]]})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertTrue(r["g"]["refused"])
        self.assertIn("mistake on line", r["g"]["reason"])
        self.assertNotIn(str(self.tmp), r["g"]["reason"], "a file path reached the engine")
        self.assertTrue(r["w"]["refused"])
        self.assertTrue(r["unchanged"], "the owner's file was changed")
        self.assertEqual(r["after"], ["first"], "the fixed file was not picked up")

    def test_at_start_a_mistake_is_not_recovered_over(self):
        c = Conscience(self.store)
        for f in ("Dr Smith is my doctor", "I had an affair in 2009", "likes tea"):
            c.remember_fact(f)
        d = json.loads(self.store.read_text())
        d["facts"] = [f for f in d["facts"] if "affair" not in f["fact"]]
        broken = json.dumps(d, indent=2).replace('"likes tea"', '"likes tea",', 1)
        self.store.write_text(broken)
        with self.assertRaises(ConscienceNeedsFixing) as cm:
            Conscience(self.store)
        self.assertIn("line", str(cm.exception))
        self.assertEqual(self.store.read_text(), broken)
        self.assertEqual(list(self.tmp.glob("conscience.json.corrupt*")), [])

    def test_a_truncated_hand_edit_newer_than_every_copy_is_not_recovered_over(self):
        c = Conscience(self.store)
        c.remember_fact("one")
        c.remember_fact("two")
        cut = self.store.read_bytes()[:-1]                 # the closing brace deleted
        self.store.write_bytes(cut)
        later = time.time() + 120
        os.utime(self.store, (later, later))
        with self.assertRaises(ConscienceNeedsFixing):
            Conscience(self.store)
        self.assertEqual(self.store.read_bytes(), cut)

    def test_the_owner_edit_command_checks_before_it_saves(self):
        c = Conscience(self.store)
        c.remember_fact("My doctor is Dr Old")
        c.remember_fact("I had an affair in 2009")
        good = self.tmp / "good_editor.py"
        good.write_text("import sys, json\np = sys.argv[1]\nd = json.load(open(p))\n"
                        "d['facts'] = [f for f in d['facts'] if 'affair' not in f['fact']]\n"
                        "open(p, 'w').write(json.dumps(d))\n")
        bad = self.tmp / "bad_editor.py"
        bad.write_text("import sys\nopen(sys.argv[1], 'w').write('{\"facts\": [,]}')\n")
        before = self.store.read_bytes()
        self.assertEqual(cmod.edit(Conscience(self.store), [PY, str(bad)]), 1)
        self.assertEqual(self.store.read_bytes(), before, "a bad edit changed the file")
        self.assertEqual(len(list(self.tmp.glob(".memories-edit-*.json"))), 1,
                         "the owner's edited copy must be kept to fix")
        self.assertEqual(cmod.edit(Conscience(self.store), [PY, str(good)]), 0)
        c2 = Conscience(self.store)
        self.assertEqual([f["fact"] for f in c2.data["facts"]], ["My doctor is Dr Old"])
        self.assertTrue(any("by hand" in n["what"] for n in c2.notices()))
        self.assertTrue(any(r["pinned"] == "before an edit" for r in c2.history(None)))
        self.assertGreaterEqual(self.copies_holding("affair"), 1)

    def test_shapes_that_are_not_a_life_are_refused_not_adopted(self):
        c = Conscience(self.store)
        c.remember_fact("one")
        d = json.loads(self.store.read_text())
        d["facts"] = None
        self.store.write_text(json.dumps(d))
        with self.assertRaises(ConscienceNeedsFixing):
            c.refresh()
        self.assertEqual([f["fact"] for f in c.data["facts"]], ["one"])
        for junk in ('{"_rev": 3}', '{"_rev": "7", "facts": []}', '{"facts": ["x"], "_rev": 1}'):
            p = self.tmp / f"j{abs(hash(junk))}.json"
            p.write_text(junk)
            with self.assertRaises(ConscienceCorrupt):
                Conscience(p)


# ======================================================================= I-20
class Restore(StoreTest):

    def test_a_restore_by_hand_survives_a_later_tear(self):
        # ops#3: 30 writes; forget everything; copy an old snapshot back by
        # hand; 6 new facts; tear the file. Recovery used to bring back the
        # wiped timeline (rev 31, 0 facts).
        c = Conscience(self.store)
        for i in range(30):
            c.remember_fact(f"fact {i}")
        c.forget_fact("")
        old = [p for p in self.snapshot_files() if p.name.endswith("-000012.json")][0]
        shutil.copy(old, self.store)
        c2 = Conscience(self.store)
        self.assertEqual(len(c2.data["facts"]), 12)
        for i in range(6):
            c2.remember_fact(f"after restore {i}")
        self.store.write_text(self.store.read_text()[:40])
        c3 = Conscience(self.store)
        facts = [f["fact"] for f in c3.data["facts"]]
        self.assertEqual(len(facts), 18, facts)
        self.assertIn("after restore 5", facts)

    def test_eighty_writes_restore_rev_ten_then_ten_more(self):
        # durability#6: post-restore copies were pruned at once (they sorted
        # below the old revisions) and a tear restored the abandoned 80.
        c = Conscience(self.store)
        saved = None
        for i in range(80):
            c.remember_fact(f"old {i}")
            if i == 9:
                saved = self.store.read_bytes()
        self.store.write_bytes(saved)
        c2 = Conscience(self.store)
        for i in range(10):
            c2.remember_fact(f"new {i}")
        newest = c2.snapshots()[0]
        self.assertIn("new 9", Path(newest["file"]).read_text())
        self.store.write_text('{"facts": [')
        facts = [f["fact"] for f in Conscience(self.store).data["facts"]]
        self.assertEqual(len(facts), 20)
        self.assertIn("new 9", facts)
        self.assertNotIn("old 79", facts)

    def test_restore_command_is_timeline_aware_and_undoable(self):
        c = Conscience(self.store)
        for i in range(5):
            c.remember_fact(f"fact {i}")
        c.forget_fact("fact")
        rows = c.history(None)
        target = next(r for r in rows if r["facts"] == 5 and not r["pinned"])
        p = subprocess.run([PY, str(CONNECTOR / "conscience.py"), "restore",
                            str(target["number"]), "--yes", "--path", str(self.store)],
                           env=self.env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Done", p.stdout)
        c2 = Conscience(self.store)
        self.assertEqual(len(c2.data["facts"]), 5)
        self.assertTrue(any("put back" in n["what"] for n in c2.notices()))
        self.assertTrue(any(r["pinned"] == "before restore" for r in c2.history(None)))
        self.assertGreater(c2.data["_rev"], max(r["revision"] for r in rows))
        self.tear(30)                                                 # a power cut
        self.assertEqual(len(Conscience(self.store).data["facts"]), 5)

    def test_history_and_restore_at_the_owner_terminal(self):
        r = self.py("""
            import jefferey_chat as jc
            jc.dispatch_tool("remember_fact", {"fact": "Mira is my niece"})
            jc.dispatch_tool("forget", {"contains": "Mira"})
            n = [h for h in jc.conscience.history(None) if h["pinned"] == "before forget"][0]
            res = jc.owner_restore(f"/restore {n['number']}", answer=lambda _: "yes")
            no = jc.owner_restore("/restore 1", answer=lambda _: "no")
            out({"res": res, "no": no, "facts": [f["fact"] for f in jc.conscience.data["facts"]],
                 "tools": [t["name"] for t in jc.TOOLS]})
        """)
        self.assertEqual(r["facts"], ["Mira is my niece"])
        self.assertIsNone(r["no"])
        self.assertFalse([t for t in r["tools"] if "restore" in t or "snapshot" in t],
                         "restoring must never be a tool an engine can call")

    def test_a_recovery_is_told_to_the_engine_and_the_owner(self):
        c = Conscience(self.store)
        c.remember_fact("Zoë is my granddaughter")
        c.remember_fact("I live in Montréal")
        self.store.write_text(self.store.read_text()[:-20])
        r = self.py("""
            import jefferey_mcp as m
            g = mcp_call(m, "get_conscience")
            b = mcp_call(m, "daily_brief")
            out({"g": g, "b": b})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(len(r["g"]["facts"]), 2)
        self.assertTrue(any("could not be read" in n["what"] for n in r["g"]["notices"]))
        self.assertTrue(any("could not be read" in n["what"] for n in r["b"]["notices"]))
        self.assertNotIn("store_path", r["g"])
        p = subprocess.run([PY, str(CONNECTOR / "conscience.py"), "check",
                            "--path", str(self.store)], env=self.env(),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 2)
        self.assertIn("could not be read", p.stdout)


# ======================================================================= I-49
class Utf8Tear(StoreTest):

    def test_a_tear_inside_an_accented_letter_recovers(self):
        c = Conscience(self.store)
        for f in ("Laszlo Czakó", "Zoë", "Montréal"):
            c.remember_fact(f)
        raw = self.store.read_bytes()
        i = raw.index("ó".encode())
        self.store.write_bytes(raw[:i + 1])                 # one byte into 'ó'
        c2 = Conscience(self.store)
        self.assertEqual([f["fact"] for f in c2.data["facts"]],
                         ["Laszlo Czakó", "Zoë", "Montréal"])
        kept = list(self.tmp.glob("conscience.json.corrupt-*"))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_bytes(), raw[:i + 1])

    def test_every_surface_still_starts(self):
        c = Conscience(self.store)
        c.remember_fact("Laszlo Czakó")
        c.remember_fact("Montréal")
        raw = self.store.read_bytes()
        self.store.write_bytes(raw[:raw.index("é".encode()) + 1])
        r = self.py("""
            import jefferey_mcp as m
            out([f["fact"] for f in mcp_call(m, "get_conscience")["facts"]])
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r, ["Laszlo Czakó", "Montréal"])


# ======================================================================= I-50
class AllowReset(StoreTest):

    def test_reset_sets_the_damaged_original_aside(self):
        c = Conscience(self.store)
        for i in range(50):
            c.remember_fact(f"precious memory {i}")
        shutil.rmtree(c.history_dir)
        original = self.store.read_bytes()[:-3]
        self.store.write_bytes(original)
        with mock.patch.dict(os.environ, {"JEFFEREY_ALLOW_RESET": "1"}):
            c2 = Conscience(self.store)
            self.assertEqual(c2.data["facts"], [])
            kept = list(self.tmp.glob("conscience.json.corrupt-*"))
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0].read_bytes(), original)
            self.assertTrue(any("kept beside it" in n["what"] for n in c2.notices()))
            # a second damaged reset never overwrites the first kept copy
            shutil.rmtree(c2.history_dir)
            self.store.write_bytes(b'{"facts": [{"fact": "second')
            Conscience(self.store)
        kept = sorted(self.tmp.glob("conscience.json.corrupt-*"))
        self.assertEqual(len(kept), 2)
        self.assertIn(original, [k.read_bytes() for k in kept])

    def test_a_flag_left_set_never_empties_a_life_over_a_typo(self):
        c = Conscience(self.store)
        c.remember_fact("precious")
        broken = self.store.read_text().replace('"precious"', '"precious",', 1)
        self.store.write_text(broken)
        with mock.patch.dict(os.environ, {"JEFFEREY_ALLOW_RESET": "1"}):
            with self.assertRaises(ConscienceNeedsFixing):
                Conscience(self.store)
        self.assertEqual(self.store.read_text(), broken)

    def test_without_the_flag_it_refuses_and_changes_nothing(self):
        self.store.write_text('{"facts": [{"fact": "trunca')
        with self.assertRaises(ConscienceCorrupt) as cm:
            Conscience(self.store)
        self.assertIn("no good copy", str(cm.exception))
        self.assertNotIn(str(self.tmp), str(cm.exception))
        self.assertEqual(self.store.read_text(), '{"facts": [{"fact": "trunca')


# ======================================================================= I-51
class PowerCuts(StoreTest):

    def fake_fcntl(self, fail: bool = False):
        import fcntl as real
        calls = []

        def fcntl_(fd, flag, *a):
            if flag == 51:
                calls.append(fd)
                if fail:
                    raise OSError(22, "not supported")
                return 0
            return real.fcntl(fd, flag, *a)
        fake = types.SimpleNamespace(F_FULLFSYNC=51, fcntl=fcntl_, flock=real.flock,
                                     LOCK_EX=real.LOCK_EX, LOCK_UN=real.LOCK_UN)
        return fake, calls

    def test_full_fsync_is_used_for_the_store_and_its_copies(self):
        fake, calls = self.fake_fcntl()
        with mock.patch.object(cmod, "fcntl", fake), \
                mock.patch.object(cmod.os, "fsync", wraps=os.fsync) as plain:
            c = Conscience(self.store)
            c.remember_fact("one")
            self.assertGreaterEqual(len(calls), 4)       # temp+folder, copy+folder
            self.assertEqual(plain.call_count, 0)
        fake, calls = self.fake_fcntl(fail=True)          # a drive that refuses it
        with mock.patch.object(cmod, "fcntl", fake), \
                mock.patch.object(cmod.os, "fsync", wraps=os.fsync) as plain:
            c.remember_fact("two")
            self.assertGreaterEqual(plain.call_count, 2)

    def test_copies_are_written_atomically_and_a_failure_is_not_silent(self):
        c = Conscience(self.store)
        c.remember_fact("one")
        real = cmod._write_atomic

        def copies_fail(path, payload):
            if path.parent == c.history_dir:
                raise OSError(28, "No space left on device")
            return real(path, payload)
        before = set(self.snapshot_files())
        with mock.patch.object(cmod, "_write_atomic", side_effect=copies_fail):
            c.remember_fact("two")
        self.assertIn("two", self.store.read_text())
        self.assertEqual(set(self.snapshot_files()), before, "a partial copy was left")
        self.assertEqual(list(c.history_dir.glob(".*.tmp")), [])
        self.assertTrue(any("safety copy" in n["what"] for n in c.notices()))
        c.remember_fact("three")
        self.assertFalse(any("safety copy" in n["what"] for n in c.notices()))
        with mock.patch.object(cmod.os, "replace", wraps=os.replace) as rep:
            c.remember_fact("four")
        dests = [Path(a[1]) for a, _ in rep.call_args_list]
        self.assertTrue(any(d.parent == c.history_dir for d in dests),
                        "copies must be renamed into place, not written in place")


# ======================================================================= I-52
class FailedSave(StoreTest):

    def test_a_save_that_fails_leaves_nothing_in_memory(self):
        # The original repro: RLIMIT_FSIZE makes the write fail with 'File too
        # large'; the phantom stayed in memory and a retry wrote it twice.
        r = self.py(f"""
            import resource, signal
            from conscience import Conscience, ConscienceSaveFailed
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            c = Conscience({str(self.store)!r})
            c.remember_fact("real fact one")
            size = c.path.stat().st_size
            resource.setrlimit(resource.RLIMIT_FSIZE, (size + 20, resource.RLIM_INFINITY))
            try:
                c.remember_fact("PHANTOM medication change: stop warfarin")
                failed = None
            except ConscienceSaveFailed as e:
                failed = str(e)
            in_memory = "PHANTOM" in json.dumps(c.snapshot())
            refreshed = c.refresh()
            resource.setrlimit(resource.RLIMIT_FSIZE,
                               (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
            c.remember_fact("after the drive was freed")
            disk = json.loads(c.path.read_text())["facts"]
            out({{"failed": failed, "in_memory": in_memory, "refreshed": refreshed,
                  "disk": [f["fact"] for f in disk]}})
        """)
        self.assertIn("could not save", r["failed"])
        self.assertFalse(r["in_memory"], "a failed write is served as remembered")
        self.assertEqual(r["disk"], ["real fact one", "after the drive was freed"])

    def test_on_mcp_the_failure_is_plain_and_the_phantom_never_served(self):
        r = self.py("""
            import errno
            import jefferey_mcp as m, conscience
            mcp_call(m, "remember_fact", {"fact": "real"})
            real = conscience._write_atomic
            def full(path, payload):
                raise OSError(errno.ENOSPC, "No space left on device")
            conscience._write_atomic = full
            w = mcp_call(m, "remember_fact", {"fact": "PHANTOM stop warfarin"})
            g = mcp_call(m, "get_conscience")
            conscience._write_atomic = real
            g2 = mcp_call(m, "get_conscience")
            mcp_call(m, "remember_fact", {"fact": "later"})
            out({"w": w, "g": [f["fact"] for f in g["facts"]],
                 "g2": [f["fact"] for f in g2["facts"]],
                 "disk": m.conscience.path.read_text()})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertTrue(r["w"]["refused"])
        self.assertIn("could not save", r["w"]["reason"])
        self.assertEqual(r["g"], ["real"])
        self.assertEqual(r["g2"], ["real"])
        self.assertNotIn("PHANTOM", r["disk"])


# ======================================================================= I-62
class Modes(StoreTest):

    def mode(self, p: Path) -> int:
        return p.stat().st_mode & 0o777

    def test_new_files_and_folders_are_the_owners_alone(self):
        old = os.umask(0o022)
        try:
            store = self.tmp / ".jefferey" / "conscience.json"
            c = Conscience(store)
            SelfCloud(c).check_access("someone", "facts.read")
            c.remember_fact("private")
            c.remember_fact("more")
            c.forget_fact("more")
        finally:
            os.umask(old)
        self.assertEqual(self.mode(store.parent), 0o700)
        self.assertEqual(self.mode(store), 0o600)
        self.assertEqual(self.mode(c.history_dir), 0o700)
        self.assertEqual(self.mode(c.pinned_dir), 0o700)
        for p in list(c.history_dir.glob("*.json")) + list(c.pinned_dir.glob("*.json")):
            self.assertEqual(self.mode(p), 0o600, p)
        self.assertEqual(self.mode(c.access_log.path), 0o600)

    def test_files_from_before_are_tightened_on_start(self):
        store = self.tmp / ".jefferey" / "conscience.json"
        c = Conscience(store)
        c.remember_fact("private")
        for p in [store, *c.history_dir.glob("*.json")]:
            os.chmod(p, 0o644)
        os.chmod(c.history_dir, 0o755)
        os.chmod(store.parent, 0o755)
        Conscience(store)
        self.assertEqual(self.mode(store), 0o600)
        self.assertEqual(self.mode(store.parent), 0o700)
        self.assertEqual(self.mode(c.history_dir), 0o700)
        for p in c.history_dir.glob("*.json"):
            self.assertEqual(self.mode(p), 0o600)

    def test_every_surface_sets_a_private_umask(self):
        r = self.py("""
            res = {}
            for mod in ("jefferey_mcp", "jefferey_http", "jefferey_chat"):
                os.umask(0o022)
                __import__(mod)
                res[mod] = oct(os.umask(0o022))
            out(res)
        """)
        self.assertEqual(set(r.values()), {"0o77"}, r)


# ======================================================================= I-68
class DamagedStoreIsNotACrash(StoreTest):

    def damage(self):
        self.store.write_text('{"facts": [{"fact": "trunca')

    def test_mcp_starts_and_every_tool_explains(self):
        self.damage()
        r = self.py("""
            import jefferey_mcp as m
            d = asyncio.run(m.mcp.call_tool("get_directives", {})).content[0].text
            g = mcp_call(m, "get_conscience")
            w = mcp_call(m, "remember_fact", {"fact": "x"})
            p = m.conscience.path
            p.write_text(json.dumps({"facts": [{"fact": "put back by hand"}],
                                     "priorities": [], "goals": [], "_rev": 1}))
            fixed = mcp_call(m, "get_conscience")
            out({"g": g, "w": w, "fixed": [f["fact"] for f in fixed["facts"]],
                 "directives": "memory file" in d})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertTrue(r["directives"], "the directives must load on a damaged store")
        self.assertTrue(r["g"]["refused"] and r["w"]["refused"])
        self.assertIn("no good copy", r["g"]["reason"])
        self.assertNotIn(str(self.tmp), json.dumps(r["g"]))
        self.assertEqual(r["fixed"], ["put back by hand"], "a fixed file needs no restart")

    def test_http_answers_in_plain_words(self):
        self.damage()
        r = self.py("""
            from fastapi.testclient import TestClient
            import jefferey_http as h
            res = TestClient(h.app).get("/conscience",
                                        headers={"Authorization": "Bearer tok-owner-aaaaaaaa"})
            out({"status": res.status_code, "body": res.json()})
        """, JEFFEREY_HTTP_TOKENS="jefferey:tok-owner-aaaaaaaa")
        self.assertEqual(r["status"], 503)
        self.assertIn("cannot be read", r["body"]["detail"])
        self.assertNotIn(str(self.tmp), r["body"]["detail"])

    def test_terminal_tools_return_a_refusal(self):
        self.damage()
        r = self.py("""
            import jefferey_chat as jc
            out([jc.dispatch_tool("remember_fact", {"fact": "x"}),
                 jc.dispatch_tool("daily_brief", {}), "cannot be read" in jc.system_prompt()])
        """)
        self.assertTrue(r[0]["refused"] and r[1]["refused"])
        self.assertTrue(r[2])

    def test_the_installer_self_test_runs_on_a_throwaway_store(self):
        self.damage()
        r = self.py(f"""
            import contextlib, io
            from pathlib import Path
            sys.path.insert(0, {str(ROOT / "tools")!r})
            import install
            install.venv_python = lambda: Path(sys.executable)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                passed = install.selftest()
            out({{"passed": passed, "text": buf.getvalue()}})
        """)
        self.assertTrue(r["passed"], r["text"][-3000:])
        self.assertIn("Your memories need attention", r["text"])
        self.assertEqual(self.store.read_text(), '{"facts": [{"fact": "trunca')

    def test_the_memories_line_is_read_only_and_plain(self):
        check = lambda: subprocess.run(  # noqa: E731
            [PY, str(CONNECTOR / "conscience.py"), "check", "--path", str(self.store)],
            env=self.env(), capture_output=True, text=True, timeout=60)
        p = check()
        self.assertEqual((p.returncode, "none yet" in p.stdout), (0, True), p.stdout)
        c = Conscience(self.store)
        c.remember_fact("one")
        p = check()
        self.assertEqual(p.returncode, 0)
        self.assertIn("OK", p.stdout)
        self.tear(25)
        listing = sorted(x.name for x in self.tmp.rglob("*"))
        p = check()
        self.assertEqual(p.returncode, 2, p.stdout)
        self.assertIn("will go back", p.stdout)
        self.assertEqual(sorted(x.name for x in self.tmp.rglob("*")), listing,
                         "a check changed something")
        self.store.write_text('{"facts": [], "_rev": 3,, "goals": []}')
        p = check()
        self.assertEqual(p.returncode, 1)
        self.assertIn("need attention", p.stdout)


if __name__ == "__main__":
    unittest.main()
