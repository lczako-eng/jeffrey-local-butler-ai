"""
Nothing irreversible because an AI asked — regression tests for the October
2026 stress test.

    I-01  one empty or short word in a 'forget' call wiped the whole life,
          with no preview, confirmation, undo or audit entry
    I-16  'forget' was not complete: the words stayed in the record of what
          was sent, in the safety copies and in other sections, and a
          forgotten person came back as a question

Every test makes its own temporary folder and environment, and reaches
JEFFEREY the way an engine does — the terminal's dispatch_tool, the MCP
server's call_tool, or the HTTP routes — in a subprocess, so nothing here
touches the real home folder (HOME is a throwaway folder, checked empty).
"""

from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONNECTOR = ROOT / "connector"
PY = sys.executable

PRELUDE = f"""
import sys, os, json, asyncio
sys.path.insert(0, {str(CONNECTOR)!r})
def mcp_call(m, name, args=None):
    r = asyncio.run(m.mcp.call_tool(name, args or {{}}))
    items = [json.loads(c.text) for c in r.content]
    return items[0] if len(items) == 1 else items
def out(obj):
    print("RESULT " + json.dumps(obj, default=str))
def store():
    return json.loads(open(os.environ["JEFFEREY_CONSCIENCE_PATH"], encoding="utf-8").read())
"""

# A life with the names the testers used: a daughter Anna, a granddaughter
# Joanna, a Legion friend Ann, an ex-wife Karen.
SEED_LIFE = """
def seed_life(call):
    for n, rel in [("Anna", "daughter"), ("Joanna", "granddaughter"),
                   ("Ann", "Legion friend"), ("Karen", "ex-wife")]:
        call("add_person", {"name": n, "relationship": rel})
    call("add_memory", {"text": "Every anniversary we went back to the lake."})
    call("add_memory", {"text": "Letter to Anna, to be read after I am gone.",
                        "visibility": "legacy"})
    call("add_memory", {"text": "The day she left, I sat in the truck for an hour.",
                        "people": "Karen"})
    call("add_memory", {"text": "Joanna's graduation, all of us there.",
                        "people": "Karen, Joanna"})
    call("add_media", {"path": "/Users/laszlo/Pictures/lake.jpg", "caption": "the lake"})
    call("add_media", {"path": "/Users/laszlo/Pictures/truck.jpg", "caption": "the old truck"})
    call("remember_fact", {"fact": "Karen (ex-wife) lives in Barrie; there is a restraining order."})
"""

DESTRUCTIVE = {
    "forget": "contains", "close_goal": "contains", "resolve_opportunity": "contains",
    "conscience_exclude": "contains", "forget_life": "contains",
    "remove_rule": "rule_id_or_text", "forget_profile_field": "field",
}


class DeletionTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-del-"))
        (self.tmp / "home").mkdir()
        self.store = self.tmp / "conscience.json"
        self.egress = self.tmp / "egress.jsonl"

    def tearDown(self):
        left = list((self.tmp / "home").rglob("*"))
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.assertEqual(left, [], "something wrote into the home folder")

    def env(self, **extra) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("JEFFEREY_", "SELFCLOUD_"))}
        env.update(HOME=str(self.tmp / "home"),
                   JEFFEREY_CONSCIENCE_PATH=str(self.store),
                   JEFFEREY_EGRESS=str(self.egress),
                   JEFFEREY_DOOR=str(self.tmp / "door-shut"),
                   SELFCLOUD_INDEX=str(self.tmp / "photo-index"),
                   SELFCLOUD_VOICE=str(self.tmp / "voice"),
                   SELFCLOUD_DISCS=str(self.tmp / "discs"),
                   PYTHONDONTWRITEBYTECODE="1")
        env.update({k: str(v) for k, v in extra.items()})
        return env

    def py(self, code: str, check: bool = True, **extra):
        p = subprocess.run([PY, "-c", PRELUDE + SEED_LIFE + textwrap.dedent(code)],
                           env=self.env(**extra), cwd=self.tmp,
                           capture_output=True, text=True, timeout=300)
        if check and p.returncode != 0:
            raise AssertionError(f"subprocess failed:\n{p.stdout}\n{p.stderr}")
        results = [l[7:] for l in p.stdout.splitlines() if l.startswith("RESULT ")]
        return json.loads(results[-1]) if results else None

    def owner(self, *args, input_text: str = "") -> subprocess.CompletedProcess:
        """The owner's own console: connector/forgetting.py."""
        return subprocess.run([PY, str(CONNECTOR / "forgetting.py"), *args],
                              env=self.env(), cwd=self.tmp, input=input_text,
                              capture_output=True, text=True, timeout=120)

    def every_copy(self) -> list[Path]:
        hist = self.store.parent / (self.store.stem + ".history")
        trash = self.store.parent / (self.store.stem + ".trash")
        return (list(hist.glob("*.json")) + list((hist / "pinned").glob("*.json"))
                + list(trash.glob("*.json")))

    def holding(self, word: str) -> list[str]:
        """Every file JEFFEREY keeps that still holds `word`."""
        found = []
        for p in [self.store, self.egress] + self.every_copy():
            if p.exists() and word.lower() in p.read_text(
                    encoding="utf-8", errors="replace").lower():
                found.append(p.name)
        return found


# ======================================================================= I-01
class NoWildcards(DeletionTest):
    """I-01 (adversarial#1, learning#0, family#0, life#0, privacy#3): '' and
    ' ' and one letter matched everything."""

    def test_empty_blank_and_short_matches_are_refused_by_every_destructive_tool(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            seed_life(d)
            for f in ["Mom's insulin: 10 units Lantus at bedtime", "Emergency contact: brother Peter"]:
                d("remember_fact", {"fact": f})
            d("add_goal", {"goal": "cut monthly expenses 15%"})
            d("record_opportunity", {"what": "switch streaming plan"})
            d("conscience_include", {"ref": "/library/2025/kitchen-table/"})
            d("set_rule", {"kind": "disclosure", "tags": "health", "instruction": "My health is mine.",
                           "audience": "anyone", "allow": False})
            d("set_profile_field", {"field": "phone", "value": "416 555 0199"})
            before = open(os.environ["JEFFEREY_CONSCIENCE_PATH"], "rb").read()
            res = {}
            for tool, key in DESTRUCTIVE.items():
                for bad in ["", " ", "   ", "a", " e ", "*", "ab"]:
                    res[f"{tool}:{bad!r}"] = d(tool, {key: bad})
            after = open(os.environ["JEFFEREY_CONSCIENCE_PATH"], "rb").read()
            out({"res": res, "same": before == after})
        """.replace("DESTRUCTIVE", repr(DESTRUCTIVE)))
        self.assertTrue(r["same"], "an empty or short match changed the memory file")
        for k, v in r["res"].items():
            self.assertTrue(v.get("refused"), (k, v))
            self.assertIn("nothing was removed", v["reason"].lower(), k)

    def test_mcp_caretaker_key_cannot_wipe_the_life_with_an_empty_string(self):
        # The original repro, on the installer's default Claude Desktop key.
        r = self.py("""
            import jefferey_mcp as m
            call = lambda n, a=None: mcp_call(m, n, a)
            seed_life(call)
            call("set_rule", {"kind": "reaction", "tags": "father", "instruction": "Just listen."})
            call("add_goal", {"goal": "visit the lake"})
            got = [call("forget_life", {"contains": ""}), call("forget", {"contains": " "}),
                   call("remove_rule", {"rule_id_or_text": ""}), call("close_goal", {"contains": ""}),
                   call("conscience_exclude", {"contains": ""})]
            s = store()
            out({"got": got, "people": len(s["people"]), "memories": len(s["memories"]),
                 "media": len(s["media"]), "facts": len(s["facts"]), "rules": len(s["rules"]),
                 "goals": [g["active"] for g in s["goals"]]})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertTrue(all(g.get("refused") for g in r["got"]), r["got"])
        self.assertEqual((r["people"], r["memories"], r["media"], r["facts"], r["rules"]),
                         (4, 4, 2, 1, 1))
        self.assertEqual(r["goals"], [True])

    def test_http_delete_facts_with_an_empty_match_removes_nothing(self):
        # learning-45: DELETE /facts?contains= with the caretaker token → 200,
        # every fact gone.
        r = self.py("""
            os.environ["JEFFEREY_HTTP_TOKENS"] = "jefferey:tokA"
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            A = {"Authorization": "Bearer tokA"}
            for f in ["one fact", "two facts", "three facts"]:
                c.post("/facts", json={"fact": f}, headers=A)
            r1 = c.delete("/facts", params={"contains": ""}, headers=A)
            r2 = c.delete("/life", params={"contains": ""}, headers=A)
            out({"r1": r1.json(), "r2": r2.json(), "facts": len(store()["facts"])})
        """)
        self.assertTrue(r["r1"]["refused"] and r["r2"]["refused"], r)
        self.assertEqual(r["facts"], 3)

    def test_a_local_model_sending_forget_life_empty_wipes_nothing(self):
        # life-22: one local Hermes turn issuing forget_life {contains: ''}
        # wiped the life and replied "Done. I've let it go."
        calls = []

        class Fake(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append(req)
                if not any(m.get("role") == "tool" for m in req["messages"]):
                    msg = {"role": "assistant", "content": "", "tool_calls": [{
                        "id": "c1", "type": "function", "function": {
                            "name": "forget_life", "arguments": json.dumps({"contains": ""})}}]}
                else:
                    msg = {"role": "assistant", "content": "Done. I've let it go."}
                body = json.dumps({"choices": [{"message": msg}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        srv = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            r = self.py(f"""
                import jefferey_chat as jc
                seed_life(jc.dispatch_tool)
                h = [{{"role": "user", "content": "forget her"}}]
                jc.run_turn_local(h, model="hermes3",
                                  url="http://127.0.0.1:{srv.server_address[1]}/v1")
                tool_msg = [m for m in h if m.get("role") == "tool"][0]
                s = store()
                out({{"tool": json.loads(tool_msg["content"]), "people": len(s["people"]),
                     "memories": len(s["memories"])}})
            """)
        finally:
            srv.shutdown()
        self.assertTrue(r["tool"]["refused"], r)
        self.assertEqual((r["people"], r["memories"]), (4, 4))


class ExactMatching(DeletionTest):
    """I-01: a person by exact name or id; words as whole words; a picture
    never by its folder."""

    def test_ann_does_not_take_anna_joanna_the_anniversary_or_the_legacy_letter(self):
        # family#0 / life-15: forget_life('Ann') removed Anna, Joanna, the
        # anniversary memory and the 'Letter to Anna'.
        r = self.py("""
            import jefferey_mcp as m
            call = lambda n, a=None: mcp_call(m, n, a)
            seed_life(call)
            shown = call("forget_life", {"contains": "Ann"})
            done = call("forget_life", {"confirm": shown["confirm"]})
            s = store()
            out({"shown": shown, "done": done, "people": [p["name"] for p in s["people"]],
                 "memories": [x["text"] for x in s["memories"]]})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual([x["what"] for x in r["shown"]["would_remove"]],
                         ["Ann (Legion friend)"])
        self.assertEqual(r["done"]["people_removed"], 1)
        self.assertEqual(r["people"], ["Anna", "Joanna", "Karen"])
        self.assertIn("Every anniversary we went back to the lake.", r["memories"])
        self.assertIn("Letter to Anna, to be read after I am gone.", r["memories"])

    def test_a_short_word_matches_whole_words_and_the_engine_sees_what_would_go(self):
        # learning-12: forget('mom') took the insulin dose, 'Momentum…' and
        # 'Treasured moments…', and the engine was told only a count.
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            for f in ["Mom's insulin: 10 units Lantus at bedtime — never skip",
                      "Mom's old address was 12 Elm St", "Momentum matters at work",
                      "Treasured moments with Peter"]:
                d("remember_fact", {"fact": f})
            shown = d("forget", {"contains": "mom"})
            facts = {f["fact"]: f["id"] for f in store()["facts"]}
            only = d("forget", {"ids": [facts["Mom's old address was 12 Elm St"]]})
            done = d("forget", {"confirm": only["confirm"]})
            out({"shown": shown, "done": done, "left": [f["fact"] for f in store()["facts"]]})
        """)
        self.assertEqual(r["shown"]["step"], "preview")
        self.assertEqual(r["shown"]["removed_facts"], 0, "a preview removed something")
        self.assertEqual(sorted(x["what"] for x in r["shown"]["would_remove"]),
                         ["Mom's insulin: 10 units Lantus at bedtime — never skip",
                          "Mom's old address was 12 Elm St"])
        self.assertEqual([x["what"] for x in r["done"]["removed_items"]],
                         ["Mom's old address was 12 Elm St"])
        self.assertIn("Mom's insulin: 10 units Lantus at bedtime — never skip", r["left"])
        self.assertIn("Momentum matters at work", r["left"])
        self.assertIn("Treasured moments with Peter", r["left"])

    def test_a_picture_is_never_matched_by_the_folder_it_sits_in(self):
        # life-16: forget_life('laszlo') removed every media reference by path.
        r = self.py("""
            import jefferey_chat as jc
            seed_life(jc.dispatch_tool)
            out({"r": jc.dispatch_tool("forget_life", {"contains": "laszlo"}),
                 "media": len(store()["media"])})
        """)
        self.assertEqual(r["r"]["step"], "nothing", r)
        self.assertEqual(r["media"], 2)

    def test_forgetting_a_person_reaches_the_moments_that_name_them(self):
        # privacy#3 / family-43 / life-17: forget_life('Sarah') removed only
        # the person record; memories and media listing her stayed.
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            d("add_person", {"name": "Sarah", "relationship": "ex-wife", "notes": "restraining order"})
            d("add_person", {"name": "Joanna", "relationship": "granddaughter"})
            d("add_memory", {"text": "My ex and I split in 2019.", "people": "Sarah"})
            d("add_memory", {"text": "Joanna's first steps.", "people": "Sarah, Joanna"})
            d("add_media", {"path": "/Users/l/beach.jpg", "caption": "beach day", "people": "Sarah"})
            d("remember_fact", {"fact": "Sarah lives in Barrie."})
            shown = d("forget_life", {"contains": "sarah"})
            ai_try = d("forget_life", {"confirm": shown["confirm"]})
            out({"shown": shown, "ai_try": ai_try, "people": len(store()["people"])})
        """)
        shown = r["shown"]
        removed = sorted((x["kind"], x["what"]) for x in shown["would_remove"])
        self.assertEqual(removed, [("moment", "My ex and I split in 2019."),
                                   ("person", "Sarah (ex-wife)"),
                                   ("picture or recording", "beach day")])
        self.assertEqual([x["what"] for x in shown["would_change"]], ["Joanna's first steps."])
        self.assertIn("Sarah's name taken off", shown["would_change"][0]["change"])
        self.assertEqual([x["what"] for x in shown["also_mentioned"]], ["Sarah lives in Barrie."])
        # A person with their moments is more than one kind: the owner's alone.
        self.assertTrue(shown["needs_owner"])
        self.assertTrue(r["ai_try"]["refused"])
        self.assertIn("Forget or bring back", r["ai_try"]["tell_the_user"])
        self.assertEqual(r["people"], 2, "an AI confirmed what needs the owner")
        p = self.owner("approve", shown["confirm"])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        s = json.loads(self.store.read_text())
        self.assertEqual([x["name"] for x in s["people"]], ["Joanna"])
        self.assertEqual([(m["text"], m["people"]) for m in s["memories"]],
                         [("Joanna's first steps.", ["Joanna"])])
        self.assertEqual(s.get("media", []), [])

    def test_remove_rule_by_id_exact_tag_or_whole_words_never_a_fragment(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            a = d("set_rule", {"kind": "disclosure", "tags": "health", "audience": "anyone",
                               "allow": False, "instruction": "My health is mine."})
            d("set_rule", {"kind": "reaction", "tags": "father", "instruction": "Don't fix it. Just listen."})
            frag = d("remove_rule", {"rule_id_or_text": "hea"})
            byid = d("remove_rule", {"rule_id_or_text": a["id"]})
            out({"frag": frag, "byid": byid, "rules": len(store()["rules"])})
        """)
        self.assertEqual(r["frag"]["step"], "nothing")
        self.assertEqual([x["what"] for x in r["byid"]["would_remove"]],
                         ["My health is mine. (about health)"])
        self.assertEqual(r["rules"], 2)


class TwoSteps(DeletionTest):
    """I-01: the first call removes nothing and returns ids and a one-time
    code; only the code removes, exactly what was shown."""

    def test_the_code_works_once_for_the_same_tool_and_key_only(self):
        r = self.py("""
            os.environ["JEFFEREY_HTTP_TOKENS"] = "jefferey:tokA,helper:tokC"
            import jefferey_http as h
            from fastapi.testclient import TestClient
            h.cloud.grant("helper", ["facts.read", "facts.write", "goals.read", "goals.write"])
            c = TestClient(h.app)
            A, C = {"Authorization": "Bearer tokA"}, {"Authorization": "Bearer tokC"}
            c.post("/facts", json={"fact": "The recital is June 12"}, headers=A)
            c.post("/goals", json={"goal": "The recital costume"}, headers=A)
            shown = c.delete("/facts", params={"contains": "recital"}, headers=A).json()
            other_tool = c.delete("/goals", params={"confirm": shown["confirm"]}, headers=A).json()
            other_key = c.delete("/facts", params={"confirm": shown["confirm"]}, headers=C).json()
            first = c.delete("/facts", params={"confirm": shown["confirm"]}, headers=A).json()
            again = c.delete("/facts", params={"confirm": shown["confirm"]}, headers=A).json()
            out({"shown": shown, "tool": other_tool, "key": other_key, "first": first,
                 "again": again, "facts": len(store()["facts"]),
                 "goals": [g["active"] for g in store()["goals"]]})
        """)
        self.assertEqual(r["shown"]["step"], "preview")
        self.assertTrue(r["tool"]["refused"] and "different request" in r["tool"]["reason"])
        self.assertTrue(r["key"]["refused"] and "different key" in r["key"]["reason"])
        self.assertEqual(r["first"]["removed_facts"], 1)
        self.assertTrue(r["again"]["refused"], "a code worked twice")
        self.assertEqual(r["facts"], 0)
        self.assertEqual(r["goals"], [True])

    def test_something_changed_since_it_was_shown_is_not_removed(self):
        r = self.py("""
            import jefferey_chat as jc, subprocess
            d = jc.dispatch_tool
            d("remember_fact", {"fact": "The boat is moored at Wiarton"})
            shown = d("forget", {"contains": "Wiarton"})
            # another engine (another process) rewords the fact meanwhile
            subprocess.run([sys.executable, "-c",
                "import sys, os; sys.path.insert(0, sys.argv[1]); from conscience import Conscience;"
                "c = Conscience(os.environ['JEFFEREY_CONSCIENCE_PATH']);"
                "c.data['facts'][0]['fact'] = 'The boat is moored at Wiarton, slip 12'; c._save()",
                sys.path[0]], check=True)
            r = d("forget", {"confirm": shown["confirm"]})
            out({"r": r, "facts": [f["fact"] for f in store()["facts"]]})
        """)
        self.assertTrue(r["r"]["refused"], r)
        self.assertIn("changed after it was shown", r["r"]["reason"])
        self.assertEqual(r["facts"], ["The boat is moored at Wiarton, slip 12"])

    def test_more_than_three_things_or_more_than_ten_a_day_needs_the_owner(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            for i in range(16):
                d("remember_fact", {"fact": f"note {i} about the garden"})
            big = d("forget", {"contains": "garden"})
            big_try = d("forget", {"confirm": big["confirm"]})
            ids = [f["id"] for f in store()["facts"]]
            done = []
            for k in range(3):                       # 9 removed, three at a time
                s = d("forget", {"ids": ids[3 * k: 3 * k + 3]})
                done.append(d("forget", {"confirm": s["confirm"]}).get("removed_facts"))
            budget = d("forget", {"ids": ids[9:11]})
            out({"big": big, "big_try": big_try, "done": done, "budget": budget,
                 "left": len(store()["facts"])})
        """)
        self.assertTrue(r["big"]["needs_owner"])
        self.assertEqual(r["big"]["count"], 16)
        self.assertTrue(r["big_try"]["refused"])
        self.assertEqual(r["done"], [3, 3, 3])
        self.assertTrue(r["budget"]["needs_owner"], r["budget"])
        self.assertIn("in the last day", r["budget"]["how_to_finish"])
        self.assertEqual(r["left"], 7)

    def test_close_goal_and_resolve_opportunity_take_two_steps_too(self):
        r = self.py("""
            import jefferey_mcp as m
            call = lambda n, a=None: mcp_call(m, n, a)
            call("add_goal", {"goal": "cut monthly expenses 15%"})
            call("record_opportunity", {"what": "switch streaming plan"})
            g = call("close_goal", {"contains": "expenses"})
            o = call("resolve_opportunity", {"contains": "streaming", "outcome": "declined"})
            mid = store()
            g2 = call("close_goal", {"confirm": g["confirm"]})
            o2 = call("resolve_opportunity", {"confirm": o["confirm"]})
            s = store()
            out({"g": g, "o": o, "mid": [mid["goals"][0]["active"], mid["opportunities"][0]["resolved"]],
                 "g2": g2, "o2": o2, "end": [s["goals"][0]["active"], s["opportunities"][0]["resolved"],
                                              s["opportunities"][0]["outcome"]]})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual((r["g"]["closed"], r["o"]["resolved"]), (0, 0))
        self.assertEqual(r["mid"], [True, False])
        self.assertEqual((r["g2"]["closed"], r["o2"]["resolved"]), (1, 1))
        self.assertEqual(r["end"], [False, True, "declined"])

    def test_forget_profile_field_takes_two_steps(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            d("set_profile_field", {"field": "phone", "value": "416 555 0199"})
            s1 = d("forget_profile_field", {"field": "phone"})
            mid = dict(store().get("profile", {}))
            s2 = d("forget_profile_field", {"field": "phone", "confirm": s1["confirm"]})
            out({"s1": s1, "mid": mid, "s2": s2, "end": store().get("profile", {})})
        """)
        self.assertEqual(r["s1"]["removed"], None)
        self.assertIn("phone", r["mid"])
        self.assertEqual(r["s2"]["removed"], "phone")
        self.assertNotIn("phone", r["end"])


class UndoAndAudit(DeletionTest):
    """I-01: a pinned copy first, a dated removed list outside the rotating
    copies, the owner's own 'bring back', and every removal in the action
    log — by id, never by its words."""

    def test_what_went_is_kept_logged_and_can_be_put_back_by_the_owner(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            seed_life(d)
            shown = d("forget_life", {"contains": "Ann"})
            done = d("forget_life", {"confirm": shown["confirm"]})
            acts = d("action_log", {})
            pins = [h["pinned"] for h in jc.conscience.history(None) if h["pinned"]]
            out({"done": done, "acts": acts, "pins": pins})
        """)
        self.assertEqual(r["done"]["step"], "done")
        self.assertIn("put_back", r["done"])
        self.assertIn("What left the house", r["done"]["still_held"])
        self.assertIn("before forget life", r["pins"])
        act = r["acts"][0]
        self.assertEqual(act["category"], "memory")
        self.assertIn("removed 1 person", act["description"])
        self.assertIn(r["done"]["removed_items"][0]["id"], act["description"])
        self.assertNotIn("Legion", json.dumps(r["acts"]), "the action log repeats the words")
        trash = list((self.tmp / "conscience.trash").glob("*.json"))
        self.assertEqual(len(trash), 1, "nothing in the removed list")
        self.assertNotIn(".history", str(trash[0]))
        self.assertEqual(trash[0].stat().st_mode & 0o777, 0o600)
        # the owner looks, and puts it back
        p = self.owner("removed")
        self.assertIn("Ann (Legion friend)", p.stdout)
        p = self.owner("bring-back", "1")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Put back", p.stdout)
        s = json.loads(self.store.read_text())
        self.assertIn("Ann", [x["name"] for x in s["people"]])
        self.assertEqual(s.get("forgotten_names", []), [], "putting back did not unforget")
        self.assertIn("put back", s["actions"][-1]["description"])

    def test_putting_back_a_forgotten_person_restores_their_name_on_shared_moments(self):
        r = self.py("""
            import jefferey_chat as jc, forgetting
            d = jc.dispatch_tool
            seed_life(d)
            shown = d("forget_life", {"contains": "Karen"})
            forgetting.approve(jc.conscience, shown["confirm"])
            mid = store()
            forgetting.bring_back(jc.conscience, "1")
            s = store()
            out({"mid": [m["people"] for m in mid["memories"]],
                 "end": sorted(tuple(m["people"]) for m in s["memories"]),
                 "people": sorted(p["name"] for p in s["people"])})
        """)
        self.assertNotIn(["Karen"], r["mid"])
        self.assertIn(["Joanna"], r["mid"])
        self.assertIn(["Karen"], r["end"])
        self.assertIn(["Karen", "Joanna"], r["end"])
        self.assertIn("Karen", r["people"])

    def test_the_owner_menu_approves_by_number_and_the_terminal_by_slash_command(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            for i in range(5):
                d("remember_fact", {"fact": f"old phone number {i}"})
            a = d("forget", {"contains": "phone"})
            out({"a": a})
        """)
        self.assertTrue(r["a"]["needs_owner"])
        p = self.owner(input_text="ok 1\n")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Waiting for your OK", p.stdout)
        self.assertIn("Done: 5", p.stdout)
        self.assertEqual(json.loads(self.store.read_text())["facts"], [])
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            for i in range(4):
                d("remember_fact", {"fact": f"spare key {i}"})
            a = d("forget", {"contains": "spare key"})
            res = jc.owner_forgetting(f"/approve {a['confirm']}")
            back = jc.owner_forgetting("/bringback 1")
            out({"res": res, "back": back, "facts": len(store()["facts"]),
                 "tools": [t["name"] for t in jc.TOOLS]})
        """)
        self.assertEqual(r["res"]["removed_facts"], 4)
        self.assertEqual(r["back"]["put_back"], 4)
        self.assertEqual(r["facts"], 4)
        for t in r["tools"]:
            self.assertFalse(any(w in t for w in ("approve", "erase", "bring", "restore")),
                             f"{t}: the owner's own acts must never be a tool")


class OldStores(DeletionTest):
    """Existing data keeps working: ids are worked out as an old file is read,
    the file is not rewritten by reading, and they stay the same once saved."""

    def test_an_old_store_without_ids_gets_stable_ids_without_a_write(self):
        old = {"owner": "Laszlo", "_rev": 3,
               "facts": [{"fact": "Takes metformin 500mg with breakfast", "category": "health",
                          "added": "2026-01-01"},
                         {"fact": "Takes metformin 500mg with breakfast", "category": "health",
                          "added": "2026-01-01"}],
               "priorities": [], "goals": [{"goal": "walk daily", "added": "x", "active": True}],
               "corrections": [], "permissions": {}, "actions": [], "observations": [],
               "opportunities": [],
               "people": [{"name": "Karen", "relationship": "wife", "notes": "",
                           "important_dates": "", "added": "x", "updated": "x"}],
               "memories": [{"text": "The ferry to Tobermory.", "when": "", "people": ["Karen"],
                             "tags": [], "visibility": "private", "added": "x"}],
               "rules": [{"id": "r1234567", "kind": "reaction", "tags": ["father"],
                          "audience": "me", "allow": True, "instruction": "Listen.", "added": "x"}],
               # the key this Mac's terminal holds, issued long ago
               "selfcloud_grants": {"jefferey": {
                   "client": "jefferey", "label": "Jefferey", "note": "", "active": True,
                   "granted_on": "x", "revoked_on": None, "scopes": [
                       "facts.read", "facts.write", "priorities.read", "priorities.write",
                       "goals.read", "goals.write", "life.read", "life.write", "media.read",
                       "family.read", "legacy.read", "money.read", "money.write",
                       "vault.names"]}}}
        self.store.write_text(json.dumps(old, indent=2))
        raw = self.store.read_bytes()
        code = """
            import jefferey_chat as jc
            jc.dispatch_tool("explain_basis", {"topic": "metformin"})   # an ordinary read
            c = jc.conscience
            out({"ids": {k: [x.get("id") for x in c.data[k]] for k in
                         ("facts", "goals", "people", "memories", "rules")}})
        """
        a, b = self.py(code), self.py(code)
        self.assertEqual(self.store.read_bytes(), raw, "reading an old store rewrote it")
        self.assertEqual(a, b, "two processes worked out different ids")
        ids = a["ids"]
        self.assertEqual(ids["rules"], ["r1234567"], "an existing id was changed")
        self.assertEqual(len(set(ids["facts"])), 2, "two identical facts share an id")
        self.assertTrue(all(i and i.startswith("f-") for i in ids["facts"]))
        # forgetting by an id worked out on read, then the ids are on disk, unchanged
        r = self.py(f"""
            import jefferey_chat as jc
            s = jc.dispatch_tool("forget", {{"ids": [{ids['facts'][1]!r}]}})
            d = jc.dispatch_tool("forget", {{"confirm": s["confirm"]}})
            out({{"d": d, "disk": store()}})
        """)
        self.assertEqual(r["d"]["removed_facts"], 1)
        disk = r["disk"]
        self.assertEqual([f["id"] for f in disk["facts"]], [ids["facts"][0]])
        self.assertEqual([p["id"] for p in disk["people"]], ids["people"])
        self.assertEqual(disk["memories"][0]["text"], "The ferry to Tobermory.")
        self.assertEqual(disk["owner"], "Laszlo")


# ======================================================================= I-16
class RealErasure(DeletionTest):
    """I-16 (egress#1, privacy#2, life#1): the words stayed in the record of
    what was sent, the copies and other sections; a forgotten person came
    back as a question."""

    def test_what_an_engine_asks_to_forget_is_never_written_down(self):
        # privacy-32: forget('affair with Maria'), with nothing matching, wrote
        # 'affair with Maria' into the egress log word for word.
        self.py("""
            import jefferey_chat as jc
            jc.dispatch_tool("forget", {"contains": "affair with Maria"})
            jc.dispatch_tool("forget_life", {"contains": "Maria Kovacs"})
            jc.dispatch_tool("remove_rule", {"rule_id_or_text": "affair with Maria"})
        """)
        log = self.egress.read_text()
        self.assertNotIn("Maria", log)
        self.assertIn("sha256:", log)

    def test_erase_takes_the_words_out_of_every_section(self):
        # privacy-05: forget('bankruptcy') removed one fact; the word stayed in
        # priorities, goals, corrections, actions, observations, opportunities
        # and memories.
        self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            d("remember_fact", {"fact": "Filed for bankruptcy in 2009"})
            d("set_priority", {"context": "bankruptcy", "higher": "honesty", "lower": "pride"})
            d("record_correction", {"context": "money", "what_was_suggested": "hide the bankruptcy",
                                    "what_user_chose": "tell the bank", "value_protected": "honesty",
                                    "value_traded_away": "privacy"})
            d("add_goal", {"goal": "Rebuild credit after the bankruptcy"})
            d("log_observation", {"note": "Credit report still shows the bankruptcy"})
            d("record_opportunity", {"what": "Ask to remove the old bankruptcy note"})
            d("log_action", {"category": "paperwork", "description": "Sent the bankruptcy letter",
                             "outcome": "done"})
            d("add_memory", {"text": "The year of the bankruptcy was hard."})
            d("set_rule", {"kind": "disclosure", "tags": "bankruptcy", "audience": "anyone",
                           "allow": False, "instruction": "Never mention it."})
            d("set_profile_field", {"field": "note", "value": "discharged bankruptcy 2012"})
            d("remember_fact", {"fact": "Likes the lake"})
            jc.egress.system_prompt_once(jc.system_prompt())   # the whole conscience, logged
        """)
        self.assertIn("bankruptcy", self.store.read_text())
        p = self.owner("erase", "bankruptcy", "--yes")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Erased, for good", p.stdout)
        s = json.loads(self.store.read_text())
        self.assertNotIn("bankruptcy", json.dumps(s).lower())
        self.assertEqual([f["fact"] for f in s["facts"]], ["Likes the lake"])
        for k in ("corrections", "goals", "observations", "opportunities",
                  "memories", "rules"):
            self.assertEqual(s.get(k, []), [], k)
        # the priority about it went; the one learned in the same correction,
        # which never names it, stays
        self.assertEqual([(p["context"], p["higher"]) for p in s["priorities"]],
                         [("money", "honesty")])
        # the action log keeps its entry, with the words taken out
        sent = [a for a in s["actions"] if a.get("category") == "paperwork"]
        self.assertEqual(len(sent), 1)
        self.assertIn("[erased on", sent[0]["description"])
        self.assertIn("erased everywhere", s["actions"][-1]["description"])
        self.assertEqual(self.holding("bankruptcy"), [], "a copy still holds the words")

    def test_erase_rewrites_the_record_of_what_was_sent_as_tombstones(self):
        # egress#1: after forget('Alzheimer'), egress.jsonl still held it 7
        # times, and 'What left the house' [a] printed it.
        r = self.py("""
            import jefferey_mcp as m, egress
            call = lambda n, a=None: mcp_call(m, n, a)
            call("remember_fact", {"fact": "Diagnosed with Alzheimer's in March; not told the kids yet"})
            call("add_memory", {"text": "Kandahar, 2011: the night the convoy was hit."})
            call("get_conscience"); call("who_am_i"); call("get_conscience")
            out({"n": len(egress.entries())})
        """, JEFFEREY_CLIENT="jefferey")
        before = [json.loads(l) for l in self.egress.read_text().splitlines()]
        self.assertGreaterEqual(sum("Alzheimer" in json.dumps(e) for e in before), 3)
        p = self.owner("erase", "Alzheimer", "--yes")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        after = [json.loads(l) for l in self.egress.read_text().splitlines()]
        self.assertEqual(len(after), len(before), "erasing dropped log entries")
        self.assertNotIn("alzheimer", self.egress.read_text().lower())
        tomb = [e for e in after if e.get("erased")]
        self.assertTrue(tomb)
        for e, b in zip(after, before):
            if e.get("erased"):
                self.assertEqual(e["sha256"], b["sha256"], "the fingerprint was not kept")
                self.assertEqual((e["t"], e["tool"], e["bytes"]), (b["t"], b["tool"], b["bytes"]))
        self.assertIn("Kandahar", self.egress.read_text(), "erased more than was asked")
        rep = subprocess.run([PY, str(CONNECTOR / "egress.py"), "report", "--all", "--full"],
                             env=self.env(), capture_output=True, text=True, timeout=60).stdout
        self.assertNotIn("Alzheimer", rep)
        self.assertIn("erased by the owner", rep)
        # the receipt says where the words went, and what JEFFEREY cannot reach
        self.assertIn("going to: the engine JEFFEREY is riding", p.stdout)
        self.assertIn("cannot reach what an AI company keeps", p.stdout)

    def test_erase_reaches_every_copy_and_the_removed_list_and_reports_it(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            d("remember_fact", {"fact": "I was diagnosed with PTSD after Kandahar"})
            d("remember_fact", {"fact": "Likes the lake"})
            for i in range(4):
                d("remember_fact", {"fact": f"chatter {i}"})
            s = d("forget", {"contains": "PTSD"})
            d("forget", {"confirm": s["confirm"]})
        """)
        self.assertTrue(len([p for p in self.every_copy() if "PTSD" in p.read_text()]) >= 3,
                        "the test did not reach the copies it means to check")
        p = self.owner("erase", "PTSD", "--yes")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("safety copies:", p.stdout)
        self.assertIn("rewritten", p.stdout)
        self.assertEqual(self.holding("PTSD"), [])
        # the copies are still good copies: putting one back works, and brings
        # back the other things in it — never the erased words
        res = subprocess.run([PY, str(CONNECTOR / "conscience.py"), "restore", "3", "--yes",
                              "--path", str(self.store)], env=self.env(),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertNotIn("PTSD", self.store.read_text())
        self.assertIn("Likes the lake", self.store.read_text())

    def test_a_forgotten_person_is_never_asked_about_again(self):
        # life-17: after forget_life('Karen'), story_gaps asked "'karen'
        # appears in a memory but isn't recorded as a person — who are they?"
        r = self.py("""
            import jefferey_chat as jc, forgetting
            d = jc.dispatch_tool
            seed_life(d)
            shown = d("forget_life", {"contains": "Karen"})
            forgetting.approve(jc.conscience, shown["confirm"])
            # later an AI keeps a story that names her again
            d("add_memory", {"text": "We fixed the dock that summer.", "people": "karen"})
            gaps = d("story_gaps", {})
            out({"gaps": gaps["gaps"], "forgotten": store().get("forgotten_names")})
        """)
        self.assertFalse([g for g in r["gaps"] if "karen" in g.lower()], r["gaps"])
        self.assertEqual(len(r["forgotten"]), 1)
        self.assertNotIn("karen", json.dumps(r["forgotten"]).lower(),
                         "the forgotten-names list holds the name itself")
        # saying the name again, on purpose, takes it off the list — and says so
        r = self.py("""
            import jefferey_chat as jc
            p = jc.dispatch_tool("add_person", {"name": "Karen", "relationship": "neighbour"})
            out({"p": p, "forgotten": store().get("forgotten_names", [])})
        """)
        self.assertIn("forget", r["p"]["note"])
        self.assertEqual(r["forgotten"], [])

    def test_the_owner_can_choose_how_long_every_word_is_kept(self):
        # privacy-19 / egress-46: the log was a word-for-word diary kept
        # forever, with no retention at all.
        self.py("""
            import jefferey_chat as jc
            jc.dispatch_tool("remember_fact", {"fact": "The new knee is booked for March"})
        """)
        old = {"t": "2025-01-02T10:00:00Z", "surface": "mcp", "to": "jefferey",
               "engine": "Anthropic (Claude)", "kind": "tool_result", "tool": "remember_fact",
               "asked": '{"fact": "the old hip surgery"}', "bytes": 40, "sha256": "ab" * 32,
               "sent": '{"fact": "the old hip surgery"}', "truncated": False,
               "withheld": [], "refused": None}
        lines = self.egress.read_text().splitlines()
        self.egress.write_text("\n".join([json.dumps(old)] + lines) + "\n")
        p = subprocess.run([PY, str(CONNECTOR / "egress.py"), "keep", "90"], env=self.env(),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("kept word for word for 90 days", p.stdout)
        after = [json.loads(l) for l in self.egress.read_text().splitlines()]
        self.assertEqual(len(after), len(lines) + 1)
        self.assertNotIn("hip surgery", self.egress.read_text())
        self.assertIn("let go after 90 days", after[0]["sent"])
        self.assertEqual(after[0]["sha256"], "ab" * 32)
        self.assertIn("knee", self.egress.read_text(), "a recent send was let go")
        # ...and it keeps applying: a surface starting later lets go of what aged
        self.assertEqual((self.tmp / "egress.jsonl.keep").read_text().strip(), "90")
        old2 = dict(old, sent='{"fact": "the old shoulder"}', asked="")
        with self.egress.open("a") as f:
            f.write(json.dumps(old2) + "\n")
        self.py("import jefferey_mcp")
        self.assertNotIn("shoulder", self.egress.read_text())
        p = subprocess.run([PY, str(CONNECTOR / "egress.py"), "keep", "always"],
                           env=self.env(), capture_output=True, text=True, timeout=60)
        self.assertFalse((self.tmp / "egress.jsonl.keep").exists())

    def test_erase_is_the_owners_alone(self):
        r = self.py("""
            import jefferey_chat as jc, jefferey_mcp as m, access, egress
            os.environ["JEFFEREY_HTTP_TOKENS"] = "jefferey:tokA"
            import jefferey_http as h
            names = [t["name"] for t in jc.TOOLS]
            mcp = [t.name for t in asyncio.run(m.mcp.list_tools())]
            routes = [getattr(r, "operation_id", None) or getattr(r, "name", "") for r in h.app.routes]
            everything = names + mcp + routes + list(egress.RELEASE) + list(access.TOOL_SCOPES)
            out({"hits": [t for t in everything if "erase" in str(t) or "approve" in str(t)
                          or "bring" in str(t)]})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r["hits"], [])

    def test_erase_from_the_terminal_asks_first_and_nothing_matching_writes_nothing(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            d("remember_fact", {"fact": "The garage code is in the vault"})
            raw = open(os.environ["JEFFEREY_CONSCIENCE_PATH"], "rb").read()
            no = jc.owner_forgetting("/erase garage", answer=lambda _: "no")
            same_after_no = open(os.environ["JEFFEREY_CONSCIENCE_PATH"], "rb").read() == raw
            nothing = jc.owner_forgetting("/erase zanzibar", answer=lambda _: "yes")
            same_after_nothing = open(os.environ["JEFFEREY_CONSCIENCE_PATH"], "rb").read() == raw
            yes = jc.owner_forgetting("/erase garage", answer=lambda _: "yes")
            out({"no": no, "nothing": nothing, "a": same_after_no, "b": same_after_nothing,
                 "yes": yes, "facts": store()["facts"]})
        """)
        self.assertIsNone(r["no"])
        self.assertTrue(r["a"], "saying no still erased")
        self.assertIsNone(r["nothing"])
        self.assertTrue(r["b"], "erasing words nothing holds wrote the file")
        self.assertEqual(r["yes"]["step"], "done")
        self.assertEqual(r["facts"], [])
        self.assertIn("cannot reach what an AI company keeps", r["yes"]["still_held_elsewhere"])


if __name__ == "__main__":
    unittest.main()
