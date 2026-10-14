"""
Regression tests for where the October 2026 fixes meet (the integration of
the album, money, voice, drive, keys and egress work). Each test is a case
that was broken once the separate fixes were put together, or a cross-lane
request one package left for another:

  money (I-47, I-36..I-39)  an AI's addition waits for the owner on every
                            surface; what waits can be listed and withdrawn,
                            never confirmed by an engine; 'false' is false
                            everywhere; statement lines of text are read, not
                            crashed on; an AI's cancellation never makes
                            earlier charges look agreed
  album (I-15, I-32, I-33)  'not now' is a tool; no fingerprints leave; a
                            summary is never called his words; a story about
                            somewhere else is not pinned to these pictures;
                            the album follows the drive; its state survives
                            another process's save; the wall fails closed
  voice (I-55, I-60)        'skip' and 'quit' never start the microphone, an
                            agreement is kept only on a typed yes; read-only
                            status changes nothing; hard links are left alone
  drive (I-08)              every photo and voice tool says plainly that the
                            drive is away instead of using the laptop
  keys (I-11)               only the caretaker reads the owner's rules

Standard-library unittest. Everything that binds at import time runs in a
child process with its own HOME, which must still be empty afterwards.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "connector"))
sys.path.insert(0, str(REPO / "tools"))

PY = sys.executable
TOKEN = "integration-token-" + "x" * 32
CORE = ("JEFFEREY_CONSCIENCE_PATH", "JEFFEREY_EGRESS", "JEFFEREY_DOOR")

PRELUDE = f"""
import asyncio, json, os, sys
sys.path.insert(0, {str(REPO / 'connector')!r})
sys.path.insert(0, {str(REPO / 'tools')!r})
import home
if os.environ.get("TEST_VOLUMES"):
    home.MOUNT_BASES = [os.environ["TEST_VOLUMES"]]
def out(x):
    print("RESULT " + json.dumps(x, default=str))
def mcp_call(m, name, args=None):
    r = asyncio.run(m.mcp.call_tool(name, args or {{}}))
    content = getattr(r, "content", None)
    if content is None:
        content = r[0] if isinstance(r, tuple) else r
    items = [json.loads(c.text) if c.text[:1] in "[{{" else c.text for c in content]
    return items[0] if len(items) == 1 else items
def mcp_tools(m):
    return sorted(t.name for t in asyncio.run(m.mcp.list_tools()))
"""


class Child(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-integ-"))
        (self.tmp / "home").mkdir()
        (self.tmp / "Volumes").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def env(self, drive_away: bool = False, **extra) -> dict:
        e = {k: v for k, v in os.environ.items()
             if not k.startswith(("JEFFEREY_", "SELFCLOUD_"))}
        e.update(HOME=str(self.tmp / "home"), PYTHONDONTWRITEBYTECODE="1",
                 TEST_VOLUMES=str(self.tmp / "Volumes"))
        if drive_away:
            # The owner's drive is paired (pinned) and not plugged in, and no
            # place was named by hand: exactly how his Mac is with the drive out.
            e["SELFCLOUD_DRIVE_ID"] = "0123456789abcdef"
        else:
            e.update(JEFFEREY_CONSCIENCE_PATH=str(self.tmp / "conscience.json"),
                     JEFFEREY_EGRESS=str(self.tmp / "egress.jsonl"),
                     JEFFEREY_DOOR=str(self.tmp / "door-shut"),
                     SELFCLOUD_INDEX=str(self.tmp / "idx"),
                     SELFCLOUD_VOICE=str(self.tmp / "voice"),
                     SELFCLOUD_DISCS=str(self.tmp / "discs"),
                     JEFFEREY_FORMS_OUTBOX=str(self.tmp / "Filled forms"))
        for k, v in extra.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = str(v)
        return e

    def run_py(self, code: str, stdin: str = "", **env):
        p = subprocess.run([PY, "-c", PRELUDE + textwrap.dedent(code)], cwd=self.tmp,
                           env=self.env(**env), input=stdin, capture_output=True,
                           text=True, timeout=240)
        left = sorted(str(x.relative_to(self.tmp / "home"))
                      for x in (self.tmp / "home").rglob("*"))
        self.assertEqual(left, [], "wrote into the home folder:\n" + p.stdout + p.stderr)
        return p

    def py(self, code: str, **env):
        p = self.run_py(code, **env)
        for line in reversed(p.stdout.splitlines()):
            if line.startswith("RESULT "):
                return json.loads(line[7:])
        raise AssertionError(f"no RESULT ({p.returncode})\n{p.stdout[-3000:]}\n"
                             f"{p.stderr[-3000:]}")


# ======================================================================
# money: the register is the owner's, on every surface
# ======================================================================
class TheRegisterIsTheOwners(Child):
    def test_an_inherited_owner_console_variable_is_not_the_owners_hands(self):
        # Before: guardian.py read JEFFEREY_OWNER_CONSOLE=1 as the owner, so a
        # model's process that inherited it could add to the register.
        r = self.py("""
            os.environ["JEFFEREY_OWNER_CONSOLE"] = "1"
            import access
            from conscience import Conscience
            from guardian import Guardian
            g = Guardian(Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"]))
            before = access.owner_present()
            e = g.expect_charge("PAYPAL *TECHSUPPORT PRO", 499, "yearly")
            with access.owner_console():
                inside = access.owner_present()
            out({"before": before, "inside": inside, "status": e.get("status"),
                 "registered": [x["merchant"] for x in g.expected_charges()
                                if x.get("status") != "waiting_for_owner"]})
        """)
        self.assertEqual(r, {"before": False, "inside": True,
                             "status": "waiting_for_owner", "registered": []})

    def test_what_waits_can_be_listed_and_withdrawn_on_every_surface_never_confirmed(self):
        r = self.py(f"""
            os.environ["JEFFEREY_CLIENT"] = "jefferey"
            os.environ["JEFFEREY_HTTP_TOKENS"] = "jefferey:{TOKEN}"
            import jefferey_chat as jc, jefferey_mcp as m, jefferey_http as h, access
            from fastapi.testclient import TestClient
            c = TestClient(h.app); H = {{"Authorization": "Bearer {TOKEN}"}}
            res = {{}}
            e = jc.dispatch_tool("expect_charge", {{"merchant": "Rogers", "amount": 95}})
            res["chat_status"] = e.get("status")
            res["chat_waiting"] = [w["id"] for w in jc.dispatch_tool("charge_changes_waiting", {{}})]
            res["proposal"] = e.get("proposal")
            with access.owner_console():                 # the owner says yes, himself
                jc.guard.confirm_change(e["proposal"])
            e2 = mcp_call(m, "expect_charge", {{"merchant": "Bell", "amount": 70}})
            w = mcp_call(m, "charge_changes_waiting", {{}}) or []
            res["mcp_waiting"] = len(w if isinstance(w, list) else [w])
            res["mcp_decline"] = mcp_call(m, "decline_charge_change", {{"proposal_id": e2["proposal"]}})
            e3 = c.post("/charges/expected", json={{"merchant": "Hydro", "amount": 120}}, headers=H).json()
            res["http_waiting"] = len(c.get("/charges/waiting", headers=H).json())
            res["http_decline"] = c.delete(f"/charges/waiting/{{e3['proposal']}}", headers=H).json()
            res["alias"] = mcp_call(m, "name_for_charge", {{"descriptor": "ROGERS WIRELESS 1234",
                                                          "merchant": "Rogers"}})
            res["tools"] = {{"chat": [t["name"] for t in jc.TOOLS], "mcp": mcp_tools(m),
                            "http": sorted(r.operation_id for r in h.app.routes
                                           if getattr(r, "operation_id", None))}}
            out(res)
        """)
        self.assertEqual(r["chat_status"], "waiting_for_owner")
        self.assertIn(r["proposal"], r["chat_waiting"])
        self.assertEqual(r["mcp_waiting"], 1)
        self.assertEqual(r["mcp_decline"]["status"], "declined")
        self.assertEqual(r["http_waiting"], 1)
        self.assertEqual(r["http_decline"]["status"], "declined")
        self.assertEqual(r["alias"]["status"], "waiting_for_owner", r["alias"])
        self.assertTrue(r["alias"]["proposal"])
        for surface, names in r["tools"].items():
            for t in ("charge_changes_waiting", "decline_charge_change", "name_for_charge"):
                self.assertIn(t, names, surface)
            self.assertFalse([n for n in names if "confirm" in n and "charge" in n],
                             f"{surface} offers an engine a way to confirm")

    def test_the_owner_confirms_at_his_keyboard_with_a_typed_yes(self):
        r = self.py("""
            import jefferey_chat as jc
            a = jc.dispatch_tool("expect_charge", {"merchant": "PAYPAL *SPOTIFYAB", "amount": 12.42})
            b = jc.dispatch_tool("expect_charge", {"merchant": "Crave", "amount": 22.59})
            no_tty = jc.owner_charges("/charges", answer=lambda p: "yes", tty=False)
            answers = iter(["", "oui", "non"])      # return asks again; oui; non
            jc.owner_charges("/charges", answer=lambda p: next(answers), tty=True)
            reg = {x["merchant"]: x.get("status", "agreed") for x in jc.guard.expected_charges()}
            out({"no_tty": no_tty, "reg": reg, "waiting": jc.guard.pending_changes()})
        """)
        self.assertIsNone(r["no_tty"])
        self.assertEqual(r["reg"], {"PAYPAL *SPOTIFYAB": "agreed"})
        self.assertEqual(r["waiting"], [])

    def test_merchant_names_keep_their_capitals_for_the_owner(self):
        from conscience import Conscience
        from guardian import Guardian
        g = Guardian(Conscience(self.tmp / "c.json"), owner_present=lambda: False)
        g.expect_charge("PAYPAL *TECHSUPPORT PRO", 499, "yearly")
        self.assertIn("PAYPAL *TECHSUPPORT PRO", g.pending_changes()[0]["what"])

    def test_false_and_numbers_as_text_mean_the_same_on_the_terminal_as_elsewhere(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            e = d("expect_charge", {"merchant": "GoDaddy", "amount": "21.99", "cadence": "once",
                                    "authorized_recurring": "false"})
            log = d("action_log", {"limit": "5"})
            nan = d("action_log", {"limit": float("nan")})
            words = d("action_log", {"limit": "five"})
            out({"auth": e.get("authorized_recurring"), "status": e.get("status"),
                 "log_refused": isinstance(log, dict) and log.get("refused"),
                 "nan": nan.get("refused"), "words": words.get("reason")})
        """)
        self.assertIs(r["auth"], False)
        self.assertEqual(r["status"], "waiting_for_owner")
        self.assertFalse(r["log_refused"])
        self.assertTrue(r["nan"])
        self.assertEqual(r["words"], "'limit' should be a whole number.")

    def test_a_statement_line_of_text_is_read_not_crashed_on(self):
        # Before: [dict(x) for x in charges] raised 'dictionary update sequence'.
        r = self.py(f"""
            os.environ["JEFFEREY_CLIENT"] = "jefferey"
            os.environ["JEFFEREY_HTTP_TOKENS"] = "jefferey:{TOKEN}"
            import jefferey_chat as jc, jefferey_mcp as m, jefferey_http as h
            from fastapi.testclient import TestClient
            lines = [{{"merchant": "Netflix", "amount": 18.63, "date": "2026-10-03"}},
                     "NETFLIX.COM 18.63 2026-10-03"]
            chat = jc.dispatch_tool("review_statement", {{"charges": lines}})
            mcp = mcp_call(m, "review_statement", {{"charges": lines}})
            c = TestClient(h.app); H = {{"Authorization": "Bearer {TOKEN}"}}
            http = c.post("/charges/review", headers=H, json={{"charges": [
                {{"merchant": "Netflix", "amount": "$18.63", "date": "2026-10-03", "ref": "A1"}}]}})
            one = c.post("/charges/check", headers=H, json={{
                "merchant": "Netflix", "amount": "$18.63", "date": "2026-10-03", "ref": "A1"}})
            out({{"chat": chat, "mcp": mcp, "http": [http.status_code, http.json()],
                 "one": one.json()}})
        """)
        for k in ("chat", "mcp"):
            self.assertEqual(r[k]["errors"][0]["line"], 2, r[k])
            self.assertIn("Nothing from this statement has been kept", r[k]["summary"])
        self.assertEqual(r["http"][0], 200, r["http"])
        self.assertEqual(r["http"][1]["checked"], 1)
        self.assertTrue(r["one"]["already_on_file"], r["one"])     # same ref: one charge

    def test_the_terminal_says_what_really_happened(self):
        r = self.py("""
            import jefferey_chat as jc
            out([jc._TRACE["expect_charge"]({"merchant": "Netflix", "amount": 250},
                                            {"status": "waiting_for_owner"}),
                 jc._TRACE["mark_cancelled"]({"merchant": "Netflx"},
                                             {"marked_cancelled": 0, "cancelled_on": None})])
        """)
        self.assertIn("waiting for you", r[0])
        self.assertNotIn("registered", r[0])
        self.assertIn("NOT recorded", r[1])

    def test_an_ais_cancellation_never_makes_earlier_charges_look_agreed(self):
        # verify, I-47: mark_cancelled(scam, on='2027-12-31') silenced a $499
        # tech-support charge, a $900 bitcoin machine and a $0.99 card test.
        from conscience import Conscience
        from guardian import Guardian
        import datetime as dt
        g = Guardian(Conscience(self.tmp / "c.json"), owner_present=lambda: False,
                     today=lambda: dt.date(2026, 10, 14))
        for m in ("QWX ONLINE SVCS", "BITCOIN DEPOT ATM", "SOME SHOP"):
            self.assertEqual(g.mark_cancelled(m, "2027-12-31")["marked_cancelled"], 1)
        got = [g.check_charge(m, a, "2026-10-12")["verdict"] for m, a in
               (("QWX ONLINE SVCS", 349), ("BITCOIN DEPOT ATM", 900), ("SOME SHOP", 0.99))]
        self.assertEqual(got, ["unexpected_merchant", "possible_scam", "possible_card_testing"])
        st = g.review_statement([{"merchant": "QWX ONLINE SVCS", "amount": 349,
                                  "date": "2026-10-13"}])
        self.assertNotIn("Everything on this statement matches", st["summary"])
        # the owner's own cancellation keeps the guardian package's rule
        owner = Guardian(g.c, owner_present=lambda: True, today=lambda: dt.date(2026, 10, 14))
        owner.mark_cancelled("Old Gym", "2026-06-01")
        self.assertEqual(owner.check_charge("OLD GYM", 40, "2026-05-15")["verdict"], "expected")


# ======================================================================
# the album
# ======================================================================
def _album_setup(code: str) -> str:
    setup = """
        import numpy as np
        from photo_index import PhotoIndex
        idx = PhotoIndex(os.environ["SELFCLOUD_INDEX"])
        vec = np.ones(8, dtype="float16").tobytes()
        import hashlib
        rows = []
        for prefix, country, place, month in (("bud", "Hungary", "Budapest", 2),
                                              ("kab", "Afghanistan", "Kabul", 10)):
            for d in (10, 11, 12, 13):
                sha = hashlib.sha256(f"{prefix}{d}".encode()).hexdigest()
                rows.append(sha)
                idx.db.execute("INSERT INTO photos (sha256, path, taken_at, country, place) "
                               "VALUES (?,?,?,?,?)", (sha, f"/nowhere/{prefix}{d}.jpg",
                               f"2019-{month:02d}-{d:02d}T10:00:00", country, place))
                idx.db.execute("INSERT INTO vectors VALUES (?,?,?)", (sha, 8, vec))
        idx.db.commit()
        from conscience import Conscience
        from life import Life
        _c = Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"])
        Life(_c).add_memory("I grew up in Pecs."); Life(_c).add_memory("We had a dog.")
    """
    return textwrap.dedent(setup) + textwrap.dedent(code)


class TheAlbum(Child):
    def test_not_now_is_a_tool_on_every_surface_and_no_fingerprints_leave(self):
        r = self.py(_album_setup(f"""
            os.environ["JEFFEREY_CLIENT"] = "jefferey"
            os.environ["JEFFEREY_HTTP_TOKENS"] = "jefferey:{TOKEN}"
            import jefferey_chat as jc, jefferey_mcp as m, jefferey_http as h, access, egress
            from fastapi.testclient import TestClient
            c = TestClient(h.app); H = {{"Authorization": "Bearer {TOKEN}"}}
            p = mcp_call(m, "next_story_prompt")
            out({{"prompt": p,
                 "mcp": mcp_call(m, "skip_story", {{"moment_id": p["moment_id"]}}),
                 "http": c.post(f"/album/{{p['moment_id']}}/skip", headers=H).json(),
                 "chat": jc.dispatch_tool("skip_story", {{"moment_id": p["moment_id"]}}),
                 "scope": access.TOOL_SCOPES.get("skip_story"),
                 "release": sorted(egress.RELEASE["next_story_prompt"])}})
        """))
        self.assertTrue(r["prompt"]["moment_id"], r["prompt"])
        for k in ("mcp", "http", "chat"):
            self.assertEqual(r[k], {"skipped": True, "moment_id": r["prompt"]["moment_id"],
                                    "note": r[k]["note"]}, k)
        self.assertEqual(r["scope"], "life.write")
        self.assertNotIn("photo_ids", r["release"])
        self.assertNotRegex(json.dumps(r["prompt"]), r"[0-9a-f]{64}")

    def test_a_summary_is_not_called_his_words_and_another_places_story_is_not_pinned(self):
        r = self.py(_album_setup("""
            os.environ["JEFFEREY_CLIENT"] = "jefferey"
            import jefferey_mcp as m
            m.album.refresh()
            bud = [x for x in m.album.moments() if x["country"] == "Hungary"][0]["id"]
            kabul_story = mcp_call(m, "record_story", {"moment_id": bud,
                "text": "The user served in Kabul in 2011 and recalls dusty convoys."})
            after = {x["id"]: x["status"] for x in m.album.moments()}
            told = mcp_call(m, "record_story", {"moment_id": bud,
                "text": "We walked over the Chain Bridge in Budapest."})
            out({"kabul": kabul_story, "status_after_kabul": after[bud], "told": told,
                 "bud": bud})
        """))
        k = r["kabul"]
        self.assertTrue(k["kept"])
        self.assertEqual(k["pinned_to_photos"], 0)
        self.assertIn("NOT pinned", k["note"])
        self.assertIn("Kabul", k["note"])
        self.assertEqual(r["status_after_kabul"], "untold")
        self.assertEqual(r["told"]["pinned_to_photos"], 4)
        # an engine wrote it, so it is not word for word his
        self.assertFalse(r["told"]["memory"]["verbatim"])
        self.assertIn("summary in the AI's words", r["told"]["note"])
        self.assertNotIn("Kept in their words", r["told"]["note"])

    def test_an_old_memorys_fingerprints_go_out_as_a_count(self):
        shas = ["%064x" % i for i in range(1, 6)]
        (self.tmp / "conscience.json").write_text(json.dumps({
            "_rev": 3, "facts": [], "priorities": [], "goals": [], "corrections": [],
            "actions": [], "observations": [], "opportunities": [], "permissions": {},
            "memories": [{"text": "Varadero with Anna", "tags": ["cuba", "moment:cuba-2016"],
                          "photos": shas, "visibility": "private", "added": "x"}]}))
        r = self.py("""
            import jefferey_mcp as m
            out({"who": mcp_call(m, "who_am_i"), "story": mcp_call(m, "tell_story"),
                 "disk": json.load(open(os.environ["JEFFEREY_CONSCIENCE_PATH"]))})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r["who"]["moments"][0]["photos"], 5)
        self.assertEqual(r["story"]["moments"][0]["photos"], 5)
        self.assertNotIn(shas[0], json.dumps([r["who"], r["story"]]))
        self.assertEqual(r["disk"]["memories"][0]["photos"], shas, "nothing dropped on disk")

    def test_the_album_follows_the_drive_plugged_in_after_it_started(self):
        r = self.py(_album_setup("""
            from reminisce import Reminisce
            from life import Life
            later = os.environ["SELFCLOUD_INDEX"]
            os.environ["SELFCLOUD_INDEX"] = os.path.join(os.path.dirname(later), "not-yet")
            rem = Reminisce(_c, Life(_c))           # started with no photographs reachable
            before = rem.available
            os.environ["SELFCLOUD_INDEX"] = later    # the drive is plugged in
            out({"before": before, "after": rem.available, "progress": rem.progress()})
        """))
        self.assertFalse(r["before"])
        self.assertTrue(r["after"])
        self.assertTrue(r["progress"]["indexed"])
        self.assertEqual(r["progress"]["untold"], 2)

    def test_album_decisions_survive_another_processes_save(self):
        r = self.py(_album_setup("""
            from reminisce import Reminisce
            from life import Life
            from conscience import Conscience
            a = Reminisce(_c, Life(_c), os.environ["SELFCLOUD_INDEX"])
            a.refresh()
            kab = [x for x in a.moments() if x["country"] == "Afghanistan"][0]["id"]
            a.decline(kab)
            b_c = Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"])    # another engine
            b_c.remember_fact("The garden gate sticks in winter.")
            _c.refresh()
            Life(_c).add_memory("Another morning.")                     # and this one saves
            disk = json.load(open(os.environ["JEFFEREY_CONSCIENCE_PATH"]))
            out({"status": disk["album"]["moments"][kab]["status"],
                 "facts": [f["fact"] for f in disk["facts"]]})
        """))
        self.assertEqual(r["status"], "declined")
        self.assertIn("The garden gate sticks in winter.", r["facts"])


class TheWallFailsClosed(Child):
    def _wall(self, conscience_text: str, history: dict | None = None):
        from test_photos import add_rows, jpeg, sha_of
        import threading
        import http.client
        import wall
        idx = self.tmp / "idx"
        rows = []
        for d in (1, 2, 3):                  # real files, so only hiding can empty it
            f = jpeg(self.tmp / "pix" / f"kabul{d}.jpg", (d * 40, 5, 5))
            rows.append((sha_of(f"kab{d}"), f, f"2011-10-{d:02d}T10:00:00",
                         "Afghanistan", "Kabul"))
        add_rows(idx, rows)
        cpath = self.tmp / "conscience.json"
        cpath.write_text(conscience_text)
        for name, data in (history or {}).items():
            h = self.tmp / "conscience.history"
            h.mkdir(exist_ok=True)
            (h / name).write_text(json.dumps(data))
        srv = wall.serve(str(idx), 0, conscience_path=str(cpath))
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            c = http.client.HTTPConnection("127.0.0.1", wall.STATE["port"], timeout=15)
            c.request("GET", "/search?q=Afghanistan", headers={
                "Cookie": f"{wall.COOKIE}={wall.STATE['cookie']}",
                "Host": f"127.0.0.1:{wall.STATE['port']}"})
            resp = c.getresponse()
            got = resp.status, json.loads(resp.read() or b"{}")
            c.close()
            return got
        finally:
            srv.shutdown()
            srv.server_close()

    def test_an_unreadable_memory_file_shows_nothing_and_says_why(self):
        with redirect_stdout(io.StringIO()):
            code, body = self._wall("{this is not json")
        self.assertEqual(code, 503)
        self.assertIn("could not be read", body["error"])

    def test_the_wall_shows_them_when_his_memory_file_is_readable(self):
        with redirect_stdout(io.StringIO()):
            code, body = self._wall(json.dumps({"_rev": 1, "facts": [], "priorities": [],
                                                "goals": []}))
        self.assertEqual(code, 200, body)
        self.assertEqual(len(body["hits"]), 3)

    def test_with_a_safety_copy_the_owners_never_on_the_wall_still_holds(self):
        copy = {"_rev": 2, "facts": [], "priorities": [], "goals": [],
                "album": {"moments": {}, "never_ask": [], "never_on_the_wall": ["kabul"]}}
        with redirect_stdout(io.StringIO()):
            code, body = self._wall("{torn", {"conscience-20261014T000000Z-000002.json": copy})
        self.assertEqual(code, 200, body)
        self.assertEqual(body["hits"], [])


# ======================================================================
# voice: answers read the way people write them
# ======================================================================
class VoiceAnswers(unittest.TestCase):
    def setUp(self):
        import voice_enrol as ve
        self.ve = ve
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-integ-voice-"))
        self.root = self.tmp / "voice"
        self._mode = ve.selftest_mode(self.root, roots=[self.root])
        self._mode.__enter__()

    def tearDown(self):
        self._mode.__exit__(None, None, None)
        for p in self.tmp.rglob("*"):
            if not p.is_symlink():
                try:
                    p.chmod(0o700 if p.is_dir() else 0o600)
                except OSError:
                    pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sitting(self, replies: list[str]):
        """One sitting at a (simulated) keyboard: `replies` answer every prompt
        in turn; the microphone is a counter."""
        import numpy as np
        heard = []

        def mic(rate):
            heard.append(1)
            t = np.arange(int(rate * 4.5)) / rate
            return (0.3 * np.sin(2 * np.pi * 220 * t) * (((t % 0.35) < 0.25) & (t > 0.3))
                    ).astype("float32")
        it = iter(replies)

        def ask(prompt):
            try:
                return next(it)
            except StopIteration:
                raise EOFError
        with redirect_stdout(io.StringIO()) as buf:
            rc = self.ve._start("Erin", 2, mic, True, ask, interactive=True)
        man = self.root / "erin" / "manifest.json"
        takes = json.loads(man.read_text())["takes"] if man.exists() else []
        return rc, len(heard), takes, buf.getvalue()

    def test_skip_and_quit_never_start_the_microphone(self):
        for word in ("skip", "quit", "Quit please", "passer", "non"):
            shutil.rmtree(self.root, ignore_errors=True)
            rc, heard, takes, _ = self.sitting([word])
            self.assertEqual(heard, 0, word)
            self.assertEqual(takes, [], word)

    def test_the_agreement_is_kept_only_on_a_typed_yes(self):
        # 'no' at the keep prompt used to keep the take as consent
        rc, heard, takes, _ = self.sitting(["", "no", "quit"])
        self.assertEqual((heard, takes), (1, []))
        shutil.rmtree(self.root, ignore_errors=True)
        rc, heard, takes, _ = self.sitting(["", "", "", "", "", ""])   # return is not yes
        self.assertEqual(takes, [])
        shutil.rmtree(self.root, ignore_errors=True)
        rc, heard, takes, _ = self.sitting(["", "oui", "skip", "quit"])
        self.assertEqual([t.get("kind") for t in takes], ["consent"])

    def test_status_only_reads_and_a_hard_linked_file_is_left_alone(self):
        rc, *_ = self.sitting(["", "yes", "quit"])
        d = self.root / "erin"
        other = self.tmp / "script.sh"
        other.write_text("#!/bin/sh\n")
        other.chmod(0o755)
        os.link(other, d / "take-050.wav")
        (d / "manifest.json").chmod(0o644)
        with redirect_stdout(io.StringIO()):
            self.ve.status("Erin")
        self.assertEqual((d / "manifest.json").stat().st_mode & 0o777, 0o644)
        self.ve._tighten(d)
        self.assertEqual(other.stat().st_mode & 0o777, 0o755, "chmod through a hard link")
        self.assertEqual((d / "manifest.json").stat().st_mode & 0o777, 0o600)


# ======================================================================
# the drive away: every photo and voice tool says so, plainly
# ======================================================================
class TheDriveIsAway(Child):
    def test_every_photo_and_voice_tool_says_the_drive_is_not_plugged_in(self):
        r = self.py("""
            import io, contextlib
            res = {}
            for name, call in (
                    ("go", lambda: __import__("go").main([])),
                    ("wall", lambda: __import__("wall").main([])),
                    ("recall", lambda: __import__("recall").main(["Cuba 2016"])),
                    ("album", lambda: __import__("reminisce")._owner_cli(["list"]))):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = call()
                res[name] = [rc, buf.getvalue()]
            import voice_enrol as ve
            sys.argv = ["voice_enrol.py", "--who", "Erin", "start"]
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                rc = ve.main()
            res["voice"] = [rc, buf.getvalue()]
            out(res)
        """, drive_away=True)
        self.assertEqual(sorted(r), ["album", "go", "recall", "voice", "wall"])
        for name, (rc, text) in r.items():
            self.assertNotEqual(rc, 0, name)
            self.assertIn("not plugged in", " ".join(text.split()), (name, text))
            self.assertNotIn("/nonexistent", text, name)

    def test_all_drives_finds_every_drive_plugged_in(self):
        import home
        vols = self.tmp / "Volumes"
        good = vols / "Self-Cloud"
        old = vols / "Old Cloud"
        for d, mk in ((good, {"kind": "self-cloud-drive", "id": "0123456789abcdef"}),
                      (old, {"name": "Self Cloud"})):
            (d / ".selfcloud").mkdir(parents=True)
            (d / ".selfcloud" / "selfcloud.json").write_text(json.dumps(mk))
        saved = list(home.MOUNT_BASES)
        home.MOUNT_BASES = [str(vols)]
        try:
            self.assertEqual(home.all_drives(), [good])
            self.assertEqual(sorted(home.all_drives(any_marker=True)), sorted([good, old]))
        finally:
            home.MOUNT_BASES = saved


# ======================================================================
# keys: only the caretaker reads the owner's rules (I-11)
# ======================================================================
class OnlyTheCaretakerReadsHisRules(Child):
    def test_a_guest_key_gets_no_rule_and_the_caretaker_keeps_them(self):
        code = """
            import jefferey_mcp as m
            out({t: mcp_call(m, t, a) for t, a in (
                ("list_rules", {}), ("check_disclosure", {"audience": "karen", "tags": "health"}),
                ("guidance_for", {"tags": "health"}))})
        """
        self.py("""
            import jefferey_mcp as m
            mcp_call(m, "set_rule", {"kind": "disclosure", "tags": "health", "audience": "karen",
                     "allow": False, "instruction": "Never tell Karen about my PTSD."})
            out(1)
        """, JEFFEREY_CLIENT="jefferey")
        guest = self.py(code, JEFFEREY_CLIENT="claude-raw")
        mine = self.py(code, JEFFEREY_CLIENT="jefferey")
        for t, v in guest.items():
            self.assertTrue(isinstance(v, dict) and v.get("refused"), (t, v))
        self.assertNotIn("PTSD", json.dumps(guest))
        self.assertIn("PTSD", json.dumps(mine["list_rules"]))

    def test_an_old_caretaker_key_keeps_reading_rules_however_it_was_narrowed(self):
        from selfcloud import migrate_grants, GRANTS_VERSION
        narrowed = ["facts.read", "facts.write", "life.read", "paperwork.write"]
        data = {"selfcloud_grants": {
            "jefferey": {"client": "jefferey", "scopes": list(narrowed), "v": 3},
            "claude-raw": {"client": "claude-raw", "scopes": ["facts.read"], "v": 3}}}
        self.assertTrue(migrate_grants(data))
        self.assertEqual(GRANTS_VERSION, 4)
        self.assertEqual(sorted(data["selfcloud_grants"]["jefferey"]["scopes"]),
                         sorted(narrowed + ["rules.read"]))
        self.assertEqual(data["selfcloud_grants"]["claude-raw"]["scopes"], ["facts.read"])
        # once only: a scope the owner later removes is never put back
        data["selfcloud_grants"]["jefferey"]["scopes"].remove("rules.read")
        self.assertFalse(migrate_grants(data))


if __name__ == "__main__":
    unittest.main()
