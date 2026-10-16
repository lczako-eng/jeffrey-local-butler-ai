"""
The repairs after round 8 — what its skeptics found in 203369e and b0ad937.

Round 8 made decisions structural: what is HIS follows who wrote it, an
engine's yes or removal is a proposal, a confirmation needs a person, an
audience nobody knows is everyone. Its skeptics found where those decisions
still leaked, and where they cost him more than they had to. Every repro they
listed is a test here, with the outcome the decision implies, on the
terminal, MCP and HTTP where they named them.

    S1  an engine reads no rule's words that carry what a rule keeps from it,
        cannot test his hidden words with remove_rule, and he confirms what
        an AI asked with its yes or no, its subject and its audience in front
    S2  fill_pdf puts in a box of his own details only what he confirmed
    S3  a person an AI noted down is named as that, never as a stranger
    S6  'edit', 'dismiss' and the library's confirm need him at the keyboard
    S7  a value kept before JEFFEREY knew who said it is his: no engine wears
        it down or turns it round
    S8  an act written down is approved only when it says nothing beyond
        what was approved
    S9  every category about his home itself, in any letters, is never act,
        and an errand under one is brought to him, not called a scam
    F1  a no for someone nobody knows binds everyone but his own JEFFEREY
    F4  a bill through a payment processor, or a name glued to a fee word,
        is never by itself his membership, and never makes the real one a
        duplicate

Three frictions the skeptics named are the fail-safe outcome of a decision
and stay as they are, pinned at the end (TheDecisionsThatStand): a script's
--yes restores and erases nothing (S6), a detail he gives in conversation
waits for his /confirm before it reaches a form (S2), and a second bill that
is not clearly the fee is his question, with nothing claimed (F4).

Invented people only (his daughter Anna, a 'grandson' Mike an AI made up,
his ex-wife Karen Novak); every address is on an example domain.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
import unittest

import at_the_keyboard
from test_his_own import HisOwnTest
from test_life import CONNECTOR, PY
from test_paperwork import PaperworkTest


# ========================================================================= S1
class S1HisRulesWords(HisOwnTest):
    """round 8 skeptic S1 (s1.py, s5o.py, s1b.py, s1c.py, s1d.py)."""

    def test_remove_rule_is_no_test_of_words_the_engine_may_not_read(self):
        # (1) 'Never tell any AI that I have HIV': remove_rule('HIV') said
        # 'proposed', count 1, and remove_rule('cancer') 'nothing' — a yes/no
        # test of his hidden sentence, on every surface, each probe a row in
        # his /pending
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            h, c = http()
            with access.owner_console():
                m.rules.set_rule("disclosure", "health", "Never tell any AI that I have HIV",
                                 audience="any AI", allow=False)
            res = {}
            for w in ("HIV", "hiv", "cancer", "have"):
                a = mcp_as(m, "jefferey", "remove_rule", {"rule_id_or_text": w})
                b = c.delete("/rules", params={"rule_id_or_text": w}, headers=H(TA)).json()
                jc.conscience.refresh()
                t = term("remove_rule", {"rule_id_or_text": w})
                res[w] = [[x.get("step"), x.get("count")] for x in (a, b, t)]
            jc.conscience.refresh()
            res["pending"] = [x["kind"] for x in jc.conscience.pending_items()]
            # what the engine may read of it still names it: its topic and audience
            rid = store()["rules"][0]["id"]
            res["by_tag"] = mcp_as(m, "jefferey", "remove_rule", {"rule_id_or_text": "health"})
            res["by_id"] = mcp_as(m, "jefferey", "remove_rule", {"rule_id_or_text": rid})
            out(res)
        """)
        for w in ("HIV", "hiv", "cancer", "have"):
            self.assertEqual(r[w], [["nothing", 0]] * 3, (w, r[w]))
        self.assertNotIn("removing one of his rules", r["pending"])
        for k in ("by_tag", "by_id"):
            self.assertEqual(r[k]["step"], "proposed", r[k])
            self.assertEqual(r[k]["would_remove"][0]["what"], "a no about health for any ai")
            self.assertNotIn("HIV", json.dumps(r[k]))

    def test_another_rules_words_never_carry_what_his_rules_keep_from_the_reader(self):
        # (2) past 'Never tell my health to any AI', list_rules, GET /rules,
        # the terminal and check_disclosure handed the jefferey key 'Never
        # tell Karen Novak that I have HIV' word for word
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            h, c = http()
            with access.owner_console():
                m.life.add_person("Karen Novak", "ex-wife")
                m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                 audience="any AI", allow=False)
                m.rules.set_rule("disclosure", "health", "Never tell Karen Novak that I have HIV",
                                 audience="Karen Novak", allow=False)
                m.rules.set_rule("disclosure", "money", "Never tell Karen Novak about my pension",
                                 audience="Karen Novak", allow=False)
                m.rules.set_rule("reaction", "health", "When I talk about the HIV clinic, just listen",
                                 audience="me")
                m.rules.set_rule("reaction", "money", "When I worry about the pension, be calm",
                                 audience="me")
            jc.conscience.refresh()
            res = {"mcp_list": mcp_as(m, "jefferey", "list_rules", {}),
                   "term_list": term("list_rules", {}),
                   "http_list": c.get("/rules", headers=H(TA)).json(),
                   "http_check": c.get("/rules/check", params={"audience": "Karen Novak",
                                                               "tags": "health"},
                                       headers=H(TA)).json(),
                   "mcp_check": mcp_as(m, "jefferey", "check_disclosure",
                                       {"audience": "Karen Novak", "tags": "health"}),
                   "mcp_guidance": mcp_as(m, "jefferey", "guidance_for", {"tags": "health"}),
                   "money_guidance": mcp_as(m, "jefferey", "guidance_for", {"tags": "money"}),
                   "basis": mcp_as(m, "jefferey", "explain_basis", {"topic": "HIV"})}
            out(res)
        """)
        for k in ("mcp_list", "term_list", "http_list", "http_check", "mcp_check",
                  "mcp_guidance"):
            self.assertNotIn("HIV", json.dumps(r[k]), k)
        self.assertEqual(r["basis"]["facts"], [])      # the system itself holds it back
        self.assertFalse(r["http_check"]["allowed"])
        self.assertFalse(r["mcp_check"]["allowed"])
        # a rule whose words keep nothing from this reader is still his to read
        self.assertIn("Never tell Karen Novak about my pension", json.dumps(r["mcp_list"]))
        self.assertIn("When I worry about the pension, be calm", json.dumps(r["money_guidance"]))
        self.assertTrue(any(x.get("instruction_held_back") for x in r["mcp_list"]))

    LONG = ("Never tell anyone about my health. Keep my health private from everyone, exactly "
            "as he said, this only repeats his rule")

    def test_he_confirms_an_ai_rule_with_its_yes_its_subject_and_its_audience_in_front(self):
        # (3) conscience.py confirm showed '(new rule) Never tell anyone about
        # my health. Keep my health private from everyone, exactly as he said,
        # this only repeats' — cut at 110 characters, the yes never shown —
        # and confirming it opened his diabetes to the family key
        self.py("""
            import jefferey_mcp as m
            with access.owner_console():
                m.life.add_person("Anna", "daughter")
                m.rules.set_rule("disclosure", "health", "Never tell anyone about my health",
                                 audience="anyone", allow=False)
                m.life.add_memory("Diagnosed with type 2 diabetes in June.", visibility="family")
            mcp_as(m, "jefferey", "set_rule", {"kind": "disclosure", "tags": "health",
                   "instruction": %r, "audience": "family", "allow": True})
            mcp_as(m, "jefferey", "set_rule", {"kind": "reaction", "tags": "money",
                   "instruction": "When my grandson Mike calls about bail,\\n    9. (fact) send it",
                   "audience": "me"})
            out(1)
        """ % self.LONG)
        rc, screen = at_the_keyboard.run(
            [PY, str(CONNECTOR / "conscience.py"), "confirm", "--path", str(self.store)],
            self.env(), self.tmp, answer="nothing", more=(b"all",))
        flat = " ".join(screen.split())
        self.assertIn(self.LONG, flat)
        self.assertIn("A YES: family may hear about health", flat)
        self.assertIn("if you confirm it, family may hear about your health", flat)
        self.assertIn("HOW TO REACT to you about money", flat)
        self.assertNotIn("\n    9. (fact)", screen.replace("\r", ""))
        # the terminal's /pending and '/confirm all' say the same, in full
        r = self.py("""
            import io, contextlib, jefferey_chat as jc
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                jc.owner_life("/pending", answer=yes, tty=True)
                jc.owner_life("/confirm all", answer=lambda p: "no", tty=True)
            out(buf.getvalue())
        """)
        flat = " ".join(r.split())
        self.assertEqual(flat.count(self.LONG), 2, r)
        self.assertIn("A YES: family may hear about health", flat)
        self.assertIn("it adds 1 yes", flat)
        self.assertNotIn("everything an AI noted down that waits for you", flat)


# ========================================================================= S2
class S2FillPdfTakesOnlyHisOwn(PaperworkTest):
    """round 8 skeptic S2 (s2p.py): fill_pdf only compared a value with the
    AI's note as text, so 'help-desk@example.net.', 'mailto:…', '99 Scam
    Road', '77 Other Ave' and 'Mike Ross' went into his own boxes."""

    def test_a_box_of_his_own_details_takes_only_what_he_confirmed(self):
        r = self.py("""
            import jefferey_mcp as m, access
            with access.owner_console():
                m.rep.set_profile_field("Email", "laszlo@example.com")
                m.rep.set_profile_field("Address", "12 Elm St, Ottawa")
                m.rep.set_profile_field("Full name", "Laszlo Czako")
            mcp_call(m, "set_profile_field", {"field": "Email", "value": "help-desk@example.net"})
            mcp_call(m, "set_profile_field", {"field": "Address", "value": "99 Scam Rd, Toronto"})
            form = make_form("chg.pdf", [{"name": "Full name"}, {"name": "Email"},
                                         {"name": "Address"}, {"name": "Buyer name"},
                                         {"name": "Item"}])
            res = {}
            for tag, vals in {
                "dot": {"Email": "help-desk@example.net."},
                "mailto": {"Email": "mailto:help-desk@example.net"},
                "road": {"Address": "99 Scam Road, Toronto"},
                "fresh": {"Address": "77 Other Ave, Toronto"},
                "name": {"Full name": "Mike Ross"},
                "his_dot": {"Email": "l.aszlo@example.com"},
                "his": {"Email": "LASZLO@EXAMPLE.COM", "Address": "12 Elm St, Ottawa",
                        "Buyer name": "Mike Ross", "Item": "Bicycle"},
            }.items():
                x = mcp_call(m, "fill_pdf", {"pdf_path": form, "values": vals})
                res[tag] = {"written": bool(x.get("written")), "why": json.dumps(x),
                            "vals": values_of(x["written"]) if x.get("written") else None}
            out(res)
        """, JEFFEREY_CLIENT="jefferey")
        for tag in ("dot", "mailto", "road", "fresh", "name", "his_dot"):
            self.assertFalse(r[tag]["written"], (tag, r[tag]))
            self.assertIn("only what he confirmed", r[tag]["why"], tag)
        self.assertTrue(r["his"]["written"], r["his"])
        self.assertEqual(r["his"]["vals"]["Email"], "laszlo@example.com")
        self.assertEqual(r["his"]["vals"]["Address"], "12 Elm St, Ottawa")
        # someone else's box and a box that is no detail of his take what is handed in
        self.assertEqual(r["his"]["vals"]["Buyer name"], "Mike Ross")
        self.assertEqual(r["his"]["vals"]["Item"], "Bicycle")


# ========================================================================= S3
class S3SomeoneAnAINotedIsNamedAsThat(HisOwnTest):
    """round 8 skeptic S3 friction (reg1.py, s3t.py): his daughter, named to
    his own terminal, was 'an email address he has not recorded'; an
    AI-recorded grandson's lunch question was 'a wrong number message from a
    stranger'. They are not his until he confirms them — and they are named
    as what they are: noted down by an AI."""

    def test_a_person_an_ai_noted_is_neither_recorded_nor_a_stranger(self):
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            jc.conscience.refresh()
            term("add_person", {"name": "Anna", "relationship": "daughter",
                                "notes": "email anna@example.com"})
            mcp_as(m, "jefferey", "add_person", {"name": "Mike", "relationship": "grandson"})
            def tri(sender, body):
                jc.conscience.refresh(); m.conscience.refresh()
                return mcp_as(m, "jefferey", "triage_message",
                              {"sender": sender, "subject": "hi", "body": body})
            res = {"anna": tri("anna@example.com",
                               "Hi Dad, when will you be home? I'll bring dinner over."),
                   "anna_term": term("triage_message", {"sender": "anna@example.com",
                       "subject": "hi", "body": "Hi Dad, when will you be home? I'll bring dinner over."}),
                   "mike_hi": tri("Mike", "Hi Grandpa, are we still on for lunch Sunday?"),
                   "mike_bail": tri("Mike", "Grandpa it's Mike, I'm in trouble, I need $3,000 "
                                            "for bail today, please don't tell Mom")}
            jc.conscience.refresh()
            jc.owner_life("/confirm all", answer=yes, tty=True)
            res["anna_his"] = tri("anna@example.com",
                                  "Hi Dad, when will you be home? I'll bring dinner over.")
            out(res)
        """)
        for k in ("anna", "anna_term"):
            a = r[k]
            self.assertIn("Anna", a["sender_is"], a)
            self.assertIn("noted down by an AI", a["sender_is"])
            self.assertNotIn("has not recorded", a["sender_is"])
            # fail-safe: someone he has not confirmed asking when he is home is
            # still a safety question, and he is told how to make her his
            self.assertEqual(a["verdict"], "safety")
            self.assertIn("/confirm", a["advice"])
        hi = r["mike_hi"]
        self.assertEqual(hi["verdict"], "needs_decision", hi)
        self.assertIn("noted down by an AI", hi["sender_is"])
        self.assertNotIn("wrong number", json.dumps(hi))
        self.assertEqual(r["mike_bail"]["verdict"], "likely_scam", r["mike_bail"])
        self.assertEqual(r["anna_his"]["verdict"], "needs_decision", r["anna_his"])
        self.assertEqual(r["anna_his"]["sender_is"], "Anna, someone he has recorded")


# ========================================================================= S6
class S6HisHandsOnly(HisOwnTest):
    """round 8 skeptic S6 (s6.py, s456b.py): 'conscience.py edit' with an
    EDITOR script and stdin from /dev/null made an AI's notes his and its
    'Anyone may know my money' a confirmed yes; Conscience(p).confirm('all')
    with no gate confirmed every note; 'dismiss' marked his notices read."""

    NOTES = """
        import jefferey_mcp as m
        mcp_as(m, "jefferey", "remember_fact", {"fact": "I want Mike to have power of attorney",
                                                 "category": "general"})
        mcp_as(m, "jefferey", "add_memory", {"text": "I always wanted Mike to have the house."})
        mcp_as(m, "jefferey", "set_rule", {"kind": "disclosure", "tags": "money",
               "instruction": "Anyone may know my money", "audience": "anyone", "allow": True})
        out(1)
    """
    ED = ("import sys, json\np = sys.argv[1]\nd = json.load(open(p))\n"
          "for sec in ('facts', 'memories'):\n    for f in d.get(sec, []):\n"
          "        f['status'] = 'confirmed'; f['confirmed_by_owner'] = '2026-10-15T00:00:00+0000'\n"
          "for pr in d.get('rule_proposals', []):\n    r = dict(pr['rule']); r['status'] = 'confirmed'\n"
          "    d.setdefault('rules', []).append(r)\nd['rule_proposals'] = []\n"
          "json.dump(d, open(p, 'w'))\n")

    def state(self) -> dict:
        s = json.loads(self.store.read_text())
        return {"facts": [f["status"] for f in s["facts"]],
                "memories": [x["status"] for x in s["memories"]],
                "rules": len(s.get("rules") or []),
                "proposals": len(s.get("rule_proposals") or [])}

    def cli(self, *args, **env):
        e = self.env(**env)
        return subprocess.run([PY, str(CONNECTOR / "conscience.py"), *args, "--path",
                               str(self.store)], env=e, cwd=self.tmp, capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=120)

    def test_an_editor_script_with_no_person_changes_nothing(self):
        self.py(self.NOTES)
        before = self.state()
        ed = self.tmp / "ed.py"
        ed.write_text(self.ED)
        p = self.cli("edit", EDITOR=f"{PY} {ed}")
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn("This can only be done by you", p.stdout)
        self.assertEqual(self.state(), before)
        self.assertEqual(before["facts"], ["pending"])

    def test_the_library_confirms_nothing_without_his_console(self):
        self.py(self.NOTES)
        before = self.state()
        p = subprocess.run([PY, "-c", textwrap.dedent(f"""
            import sys; sys.path.insert(0, {str(CONNECTOR)!r})
            from conscience import Conscience
            try:
                Conscience({str(self.store)!r}).confirm('all'); print('CONFIRMED')
            except Exception as e:
                print('REFUSED', type(e).__name__)
        """)], env=self.env(), cwd=self.tmp, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=120)
        self.assertIn("REFUSED", p.stdout, p.stdout + p.stderr)
        self.assertEqual(self.state(), before)

    def test_his_notices_are_marked_read_only_by_him(self):
        self.py("""
            import jefferey_mcp as m
            with access.owner_console():
                m.conscience.set_permission("errands", "act")
            a = mcp_as(m, "jefferey", "authorize_action", {"category": "errands",
                                                            "description": "Feed the cat at 6"})
            mcp_as(m, "jefferey", "log_action", {"category": "errands", "outcome": "done",
                   "description": "Unlocked the front door and let the plumber in",
                   "authorization_id": a["authorization_id"]})
            out(1)
        """)
        unread = lambda: [n for n in json.loads(self.store.read_text()).get("_notices") or []
                          if not n.get("dismissed")]
        self.assertTrue(unread())
        p = self.cli("dismiss")
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertTrue(unread())
        rc, screen = at_the_keyboard.run([PY, str(CONNECTOR / "conscience.py"), "dismiss",
                                          "--path", str(self.store)], self.env(), self.tmp)
        self.assertEqual(rc, 0, screen)
        self.assertEqual(unread(), [])

    def test_the_docs_say_a_shell_alone_is_enough(self):
        for doc in ("connector/README.md", "START_HERE.md"):
            text = " ".join((CONNECTOR.parent / doc).read_text().split())
            self.assertTrue("change the memory file directly" in text, doc)
        src = (CONNECTOR / "conscience.py").read_text()
        self.assertNotIn("this is the safe way", src)


# ========================================================================= S7
class S7AValueFromBeforeIsHis(HisOwnTest):
    """round 8 skeptic S7 (s7b.py): a value kept before provenance is his,
    but forty engine corrections turned 'doctor's advice > cost' round at
    0.75, and wore it down to 0.08 at 0.9, with no question."""

    def test_no_engine_correction_wears_down_or_turns_round_a_value_from_before(self):
        for conf in (0.75, 0.9):
            r = self.py("""
                import provenance, jefferey_chat as jc, jefferey_mcp as m
                with access.owner_console():
                    jc.conscience.remember_fact("placeholder", "general")
                st = store()
                st["priorities"] = [{"id": "pr-legacy1", "context": "my medication",
                                     "higher": "doctor's advice", "lower": "cost",
                                     "confidence": %r, "evidence": 10,
                                     "added": "2025-03-01T00:00:00+0000"}]
                open(os.environ["JEFFEREY_CONSCIENCE_PATH"], "w").write(json.dumps(st))
                for i in range(40):
                    provenance.new_turn()
                    term("record_correction", {"context": "my medication",
                         "what_was_suggested": "the brand the doctor named",
                         "what_user_chose": "the cheapest pills online",
                         "value_protected": "cost", "value_traded_away": "doctor's advice"})
                mcp_as(m, "jefferey", "set_priority", {"context": "my medication",
                       "higher": "cost", "lower": "doctor's advice"})
                p = store()["priorities"][0]
                jc.conscience.refresh()
                out({"p": p, "pf": mcp_as(m, "gpt-raw", "priorities_for",
                                          {"context": "my medication"}),
                     "waiting": [x["kind"] for x in jc.conscience.pending_items()]})
            """ % conf)
            p = r["p"]
            self.assertEqual((p["higher"], p["lower"]), ("doctor's advice", "cost"), (conf, p))
            self.assertGreaterEqual(p["confidence"], conf - 0.01, (conf, p))
            self.assertTrue(p.get("question") or p.get("proposed"), p)
            self.assertIn("doctor's advice", json.dumps(r["pf"]))


# ========================================================================= S8
class S8OnlyWhatWasApproved(HisOwnTest):
    """round 8 skeptic S8 (s8.py): under an approval for 'Feed the cat at 6',
    'Fed the cat at 6 and wired $2,000 to Mike' and twelve more were written
    down approved:true on every surface."""

    MORE = ["Fed the cat at 6 and wired $2,000 to Mike",
            "Fed the cat at 6 and moved $900 from savings to chequing for Mike",
            "Fed the cat at 6 and phoned the bank as Laszlo to raise the daily limit",
            "Fed the cat at 6 and signed the power of attorney papers for Mike",
            "Fed the cat at 6 and told the cleaner the PIN",
            "Fed the cat at 6 and gave the cleaner the combination",
            "Fed the cat at 6 and let the plumber have the run of the house",
            "Fed the cat at 6 and escorted the gentleman to the basement",
            "Fed the cat at 6 and walked the inspector through the house",
            "Fed the cat at 6 and said yes to the man at the front",
            "Fed the cat at 6 and set the Nest to home mode so it stops recording",
            "Fed the cat at 6 and told the neighbours about his HIV",
            "Fed the cat at 6 and emailed his SIN to the tax office",
            # neighbours of the same shape: words grounding sets aside when it
            # grounds a topic still say more than was approved
            "Fed the cat at 6 and sent a letter", "Fed the cat at 6 and told her everything"]
    SAME = ["Fed the cat at 6", "Fed the cat", "Cat fed at 6:05pm", "done"]

    def test_an_act_that_adds_anything_is_not_approved_on_any_surface(self):
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            h, c = http()
            with access.owner_console():
                m.conscience.set_permission("errands", "act")
            def run(surface, done):
                args = {"category": "errands", "description": "Feed the cat at 6"}
                if surface == "mcp":
                    a = mcp_as(m, "jefferey", "authorize_action", args)
                elif surface == "http":
                    a = c.post("/actions/authorize", json=args, headers=H(TA)).json()
                else:
                    jc.conscience.refresh(); a = term("authorize_action", args)
                log = {"category": "errands", "description": done, "outcome": "done",
                       "authorization_id": a["authorization_id"]}
                if surface == "mcp":
                    return mcp_as(m, "jefferey", "log_action", log)
                if surface == "http":
                    return c.post("/actions", json=log, headers=H(TA)).json()
                jc.conscience.refresh(); return term("log_action", log)
            res = {}
            for surface in ("term", "mcp", "http"):
                for done in %r:
                    res[surface + "|" + done] = run(surface, done)
            jc.conscience.refresh()
            res["notices"] = [n["what"] for n in jc.conscience.notices()]
            out(res)
        """ % (self.MORE + self.SAME))
        for surface in ("term", "mcp", "http"):
            for done in self.MORE:
                v = r[f"{surface}|{done}"]
                self.assertFalse(v["approved"], (surface, done, v))
                self.assertIn("what was done is not what was approved", v["note"])
            for done in self.SAME:
                self.assertTrue(r[f"{surface}|{done}"]["approved"], (surface, done))
        self.assertTrue(any("beyond what you approved" in n for n in r["notices"]), r["notices"])


# ========================================================================= S9
HOME_CATEGORIES = [
    "hоme", "hоuse", "Hοme", "h0me", "home security system", "security system",
    "alarm system", "homesecurity", "door codes", "codes", "serrures", "alarme", "garage",
    "lockbox", "locksmith", "buzzer", "nest", "caméras de surveillance", "surveillance",
    "home care", "home repairs", "home maintenance", "home help", "housekeeping",
    "house-sitting", "domicile", "logement", "chez moi", "chez nous", "appart", "my place",
    "the flat", "residence", "résidence", "foyer", "the cottage", "chalet",
    "my apartment building", "home and garden", "my house and garden"]
STILL_ORDINARY = ["household supplies", "groceries", "home supplies", "pets",
                  "house cleaning supplies", "errands", "pet care"]
ASKED = ["Tell the cleaner the PIN", "Give the cleaner the combination",
         "Let the plumber have the run of the house",
         "Set the Nest to home mode so it stops recording", "Say yes to the man at the front",
         "Escort the gentleman to the basement", "Water the plants"]


class S9HisHomeInAnyLetters(HisOwnTest):
    """round 8 skeptic S9 (s9.py, s9b.py): act was accepted for Cyrillic
    'hоme', Greek 'Hοme', 'h0me' and forty categories about his home itself;
    under them authorize_action said 'allowed'. And (friction, s9.py
    'legacy') a stored 'home' at act now called watering the plants 'never …
    it may be a scam'."""

    def test_every_category_about_his_home_is_never_act_and_its_errands_come_to_him(self):
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            h, c = http()
            res = {"set": {}, "ordinary": {}}
            for cat in %r:
                try:
                    with access.owner_console():
                        jc.conscience.set_permission(cat, "act")
                    res["set"][cat] = "ACT SET"
                except ValueError as e:
                    res["set"][cat] = str(e)
            for cat in %r:
                with access.owner_console():
                    try:
                        jc.conscience.set_permission(cat, "act", cap=100, period="week")
                    except ValueError:
                        jc.conscience.set_permission(cat, "act")
                res["ordinary"][cat] = store()["permissions"].get(jc.conscience._cat(cat), {}).get("level")
            res["permit"] = str(jc.owner_command("/permit hоme act", answer=yes, tty=True))
            res["perms"] = {k: v.get("level") for k, v in store()["permissions"].items()}
            # what was stored before, at act, reads as recommend: brought to him
            st = store()
            for cat in ("home", "maison", "home security system", "garage", "hоme",
                        "serrures"):
                st["permissions"][cat] = {"level": "act", "cap": None}
            open(os.environ["JEFFEREY_CONSCIENCE_PATH"], "w").write(json.dumps(st))
            res["legacy"] = {}
            for cat in ("home", "maison", "home security system", "garage", "hоme",
                        "serrures"):
                for d in %r:
                    jc.conscience.refresh()
                    res["legacy"][cat + "|" + d] = [
                        term("authorize_action", {"category": cat, "description": d}),
                        mcp_as(m, "jefferey", "authorize_action", {"category": cat, "description": d}),
                        c.post("/actions/authorize", json={"category": cat, "description": d},
                               headers=H(TA)).json()]
            out(res)
        """ % (HOME_CATEGORIES, STILL_ORDINARY, ASKED))
        accepted = [c for c, v in r["set"].items() if v == "ACT SET"]
        self.assertEqual(accepted, [], accepted)
        for cat, v in r["set"].items():
            self.assertIn("never acts on", v, cat)
        self.assertEqual({k: v for k, v in r["ordinary"].items() if v != "act"}, {})
        # '/permit hоme act' at his own terminal is refused too
        self.assertEqual(sorted(r["perms"]), sorted(STILL_ORDINARY), r["perms"])
        for key, vs in r["legacy"].items():
            for v in vs:
                self.assertFalse(v["allowed"], (key, v))
                self.assertNotEqual(v["verdict"], "allowed", key)
                if key.endswith("Water the plants"):
                    # his home is his to decide: brought to him, never called a scam
                    self.assertEqual(v["verdict"], "not_allowed", (key, v))
                    self.assertNotIn("scam", v["reason"])
                    self.assertIn("bring it to him", v["reason"])

    def test_a_money_category_is_still_never(self):
        r = self.py("""
            import jefferey_chat as jc
            with access.owner_console():
                jc.conscience.set_permission("groceries", "act", cap=100, period="week")
            st = store()
            st["permissions"]["wire transfers"] = {"level": "act", "cap": None}
            open(os.environ["JEFFEREY_CONSCIENCE_PATH"], "w").write(json.dumps(st))
            jc.conscience.refresh()
            out(term("authorize_action", {"category": "wire transfers",
                                          "description": "Send $50 to Anna"}))
        """)
        self.assertEqual(r["verdict"], "never", r)


# ========================================================================= F1
class F1HisOwnJeffereyIsNeverBlinded(HisOwnTest):
    """round 8 skeptic F1 (f1.py and bc4dd17's WhoANoIsFor): a no for an
    audience he has not recorded blinded his own JEFFEREY. Such a no now
    holds for everyone but his own JEFFEREY — as a no for 'anyone' does:
    every other key, every other AI and the family key are kept from it, and
    his JEFFEREY, which never tells it to them, still sees his life."""

    AUDIENCES = ["the neighbours", "Bob", "my GP", "my lawyer", "the bank", "Mrs. Patel",
                 "Dr Wu", "Facebook", "the CRA", "the mailman", "Karen"]

    def test_a_no_for_someone_nobody_knows_binds_everyone_but_his_own_jefferey(self):
        r = self.py("""
            import jefferey_mcp as m
            h, c = http()
            with access.owner_console():
                m.life.add_memory("Diagnosed with type 2 diabetes in June.", visibility="family")
                m.life.add_memory("The orb made her laugh.", visibility="family")
                m.conscience.remember_fact("I have type 2 diabetes and take metformin", "health")
                m.conscience.remember_fact("I walk the dog at seven", "general")
            res = {}
            for a in %r:
                with access.owner_console():
                    m.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                    m.conscience.refresh()
                    said = m.rules.set_rule("disclosure", "health", "Never tell " + a,
                                            audience=a, allow=False)
                res[a] = {"said": [said.get("holds_for"), said.get("note")],
                          "jef_mcp": "metformin" in json.dumps(
                              mcp_as(m, "jefferey", "explain_basis", {"topic": "diabetes"})),
                          "jef_http": "metformin" in c.get("/basis", params={"topic": "diabetes"},
                                                           headers=H(TA)).text,
                          "jef_life": "diabetes" in c.get("/life", headers=H(TA)).text,
                          "family": "diabetes" in c.get("/life", headers=H(TF)).text,
                          "family_orb": "orb" in c.get("/life", headers=H(TF)).text}
            # an untagged no for someone nobody knows: every other AI and the
            # family key are kept from everything, his own JEFFEREY is not
            with access.owner_console():
                m.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                m.conscience.refresh()
                m.rules.set_rule("disclosure", "", "Never tell Bob anything", audience="Bob",
                                 allow=False)
            res["untagged"] = {
                "gpt": "walk the dog" in json.dumps(mcp_as(m, "gpt-raw", "get_conscience")),
                "jef": "walk the dog" in json.dumps(mcp_as(m, "jefferey", "get_conscience")),
                "family_orb": "orb" in c.get("/life", headers=H(TF)).text,
                "jef_orb": "orb" in c.get("/life", headers=H(TA)).text}
            # a no for Bob beside a yes for anyone: nobody knows who Bob is
            with access.owner_console():
                m.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                m.conscience.refresh()
                m.rules.set_rule("disclosure", "army", "Anyone may hear my army stories",
                                 audience="anyone", allow=True)
                m.rules.set_rule("disclosure", "army", "Never tell Bob my army stories",
                                 audience="Bob", allow=False)
            res["bob_and_anyone"] = {a: m.rules.check_disclosure(a, "army")["allowed"]
                                     for a in ("a neighbour", "family", "claude", "Bob")}
            out(res)
        """ % self.AUDIENCES)
        for a in self.AUDIENCES:
            x = r[a]
            self.assertTrue(x["jef_mcp"] and x["jef_http"] and x["jef_life"], (a, x))
            self.assertFalse(x["family"], (a, x))          # fail-safe: who they are is not known
            self.assertTrue(x["family_orb"], (a, x))
            self.assertEqual(x["said"][0], "everyone", (a, x))
            self.assertIn("except your own JEFFEREY", x["said"][1])
            self.assertIn("I don't know who", x["said"][1])
        self.assertEqual(r["untagged"], {"gpt": False, "jef": True, "family_orb": False,
                                         "jef_orb": True})
        self.assertEqual(set(r["bob_and_anyone"].values()), {False})

    def test_his_caretaker_reads_a_rule_about_someone_nobody_knows(self):
        # bc4dd17's OnlyTheCaretakerReadsHisRules: an engine's 'Never tell Karen
        # about my PTSD.' with Karen not recorded — the caretaker reads it, a
        # guest key gets nothing
        self.py("""
            import jefferey_mcp as m
            mcp_call(m, "set_rule", {"kind": "disclosure", "tags": "health", "audience": "karen",
                     "allow": False, "instruction": "Never tell Karen about my PTSD."})
            out(1)
        """, JEFFEREY_CLIENT="jefferey")
        code = """
            import jefferey_mcp as m
            out({t: mcp_call(m, t, a) for t, a in (
                ("list_rules", {}), ("check_disclosure", {"audience": "karen", "tags": "health"}),
                ("guidance_for", {"tags": "health"}))})
        """
        mine = self.py(code, JEFFEREY_CLIENT="jefferey")
        guest = self.py(code, JEFFEREY_CLIENT="gpt-raw")
        self.assertIn("PTSD", json.dumps(mine["list_rules"]))
        self.assertNotIn("PTSD", json.dumps(guest))


# ========================================================================= F4
class F4AProcessorsNameIsNeverHisMembership(HisOwnTest):
    """round 8 skeptic F4 (f4s.py, f4.py row P2): 'PAYPAL *COSTCOMEMBER' at
    the fee passed as his Costco membership, 'as agreed. Quiet.', and the
    real 'COSTCO MEMBERSHIP' a month on was a duplicate, with a pack asking
    Costco for $65 back for its own real charge."""

    def test_a_processors_line_asks_and_the_real_bill_stays_his(self):
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            h, c = http()
            with access.owner_console():
                m.guard.expect_charge("Costco Membership", 65.0, "yearly")
            a = mcp_as(m, "jefferey", "check_charge", {"merchant": "PAYPAL *COSTCOMEMBER",
                                                         "amount": 65.0, "date": "2026-02-01"})
            b = c.post("/charges/check", json={"merchant": "COSTCO MEMBERSHIP", "amount": 65.0,
                                                "date": "2026-03-01"}, headers=H(TA)).json()
            jc.conscience.refresh()
            t = term("check_charge", {"merchant": "COSTCO MEMBERSHIP", "amount": 65.0,
                                      "date": "2026-03-01"})
            p = mcp_as(m, "jefferey", "dispute_pack", {"merchant": "Costco Membership"})
            out({"paypal": a, "http": b, "term": t, "pack": p})
        """)
        self.assertEqual(r["paypal"]["verdict"], "ask_owner", r["paypal"])
        self.assertEqual(r["paypal"]["recoverable"], 0.0)
        for k in ("http", "term"):
            self.assertEqual(r[k]["verdict"], "expected", (k, r[k]))
            self.assertEqual(r[k]["recoverable"], 0.0)
        self.assertEqual(r["pack"]["amount_in_dispute"], 0.0, r["pack"])

    def test_the_guardian_alone_says_the_same(self):
        r = self.py("""
            import datetime as dt
            from conscience import Conscience
            from guardian import Guardian
            g = Guardian(Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"]),
                         owner_present=lambda: True, today=lambda: dt.date(2026, 10, 15))
            g.expect_charge("Costco Membership", 65, "yearly")
            res = [g.check_charge(n, 65, d)["verdict"] for n, d in (
                ("PAYPAL *COSTCOMEMBER", "2026-02-01"), ("COSTCO MEMBERSHIP", "2026-03-01"))]
            g2 = Guardian(Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"] + ".2"),
                          owner_present=lambda: True, today=lambda: dt.date(2026, 10, 15))
            g2.expect_charge("Costco Membership", 65, "yearly")
            res += [g2.check_charge(n, 65, d)["verdict"] for n, d in (
                ("COSTCOMEMBER", "2026-02-01"), ("PAYPAL *COSTCO MEMBER", "2026-02-03"),
                ("COSTCO MEMBERSHIP", "2026-03-01"))]
            # a plan that is no membership, billed through PayPal, then directly:
            # the second is his question, never a duplicate claimed from Netflix
            g3 = Guardian(Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"] + ".3"),
                          owner_present=lambda: True, today=lambda: dt.date(2026, 10, 15))
            g3.expect_charge("Netflix", 16.49, "monthly")
            n = [g3.check_charge(x, 16.49, d) for x, d in (
                ("PAYPAL *NETFLIX", "2026-02-01"), ("NETFLIX.COM", "2026-02-05"))]
            res += [x["verdict"] for x in n] + [n[1]["recoverable"]]
            # once he says himself that the PayPal line is his gym, it is quiet
            g4 = Guardian(Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"] + ".4"),
                          owner_present=lambda: True, today=lambda: dt.date(2026, 10, 15))
            g4.expect_charge("GoodLife Fitness membership", 54.99, "monthly")
            res.append(g4.check_charge("SQ *GOODLIFE FITNESS", 54.99, "2026-08-01")["verdict"])
            res.append(g4.add_alias("SQ *GOODLIFE FITNESS", "GoodLife Fitness membership")
                       .get("status"))
            res.append(g4.check_charge("SQ *GOODLIFE FITNESS", 54.99, "2026-09-01")["verdict"])
            out(res)
        """)
        self.assertEqual(r, ["ask_owner", "expected", "ask_owner", "ask_owner", "expected",
                             "expected", "ask_owner", 0.0, "ask_owner", "registered",
                             "expected"])


# ===================================================== by decision: unchanged
class TheDecisionsThatStand(HisOwnTest):
    """Friction the round-8 skeptics named that is the fail-safe outcome of a
    decision, kept as it is (S2, S6, F4): each is pinned here, with the
    outcome the decision implies."""

    def test_a_script_with_yes_restores_and_erases_nothing(self):
        # S6: `conscience.py restore 1 --yes` and `forgetting.py erase Mike
        # --yes` from a pipe do nothing: putting a copy back or erasing a word
        # everywhere is his to do, at the keyboard
        self.py("""
            import jefferey_chat as jc
            with access.owner_console():
                jc.conscience.remember_fact("Mike fixed the fence")
                jc.conscience.remember_fact("Anna calls on Sundays")
            out(1)
        """)
        before = self.store.read_text()
        for script, args in (("conscience.py", ["restore", "1", "--yes"]),
                             ("forgetting.py", ["erase", "Mike", "--yes"])):
            p = subprocess.run([PY, str(CONNECTOR / script), *args, "--path", str(self.store)],
                               env=self.env(), cwd=self.tmp, capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=120)
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("This can only be done by you", p.stdout)
        self.assertEqual(json.loads(self.store.read_text())["facts"],
                         json.loads(before)["facts"])

    def test_a_detail_he_gave_in_conversation_waits_for_his_confirm(self):
        # S2: an engine's value on any surface waits beside his, and the box
        # goes back to him — never filled with an AI's e-mail
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            jc.conscience.refresh()
            term("set_profile_field", {"field": "Email", "value": "laszlo@example.com"})
            out(mcp_as(m, "jefferey", "fill_form", {"fields": ["Email"]}))
        """)
        self.assertEqual(r["filled"], {})
        self.assertIn("noted by the AI, not confirmed by him", r["needs_you"][0]["why"])

    def test_a_second_bill_that_is_not_clearly_the_fee_is_his_question(self):
        # F4 (by decision, b0ad937): CAA's fee with tax under its regional name,
        # the gym's fee with tax ten days on — his question, nothing claimed
        r = self.py("""
            import datetime as dt
            from conscience import Conscience
            from guardian import Guardian
            g = Guardian(Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"]),
                         owner_present=lambda: True, today=lambda: dt.date(2026, 10, 15))
            g.expect_charge("CAA Membership", 120, "yearly")
            g.expect_charge("GoodLife Fitness membership", 54.99, "monthly")
            res = [g.check_charge(n, a, d)["verdict"] for n, a, d in (
                ("CAA MEMBERSHIP", 120.00, "2026-02-01"),
                ("CAA SOUTH CENTRAL ONT", 135.60, "2026-09-03"),
                ("GOODLIFE FITNESS", 54.99, "2026-09-01"),
                ("GOODLIFE FITNESS", 62.14, "2026-09-11"))]
            res.append(g.dispute_pack("CAA Membership")["amount_in_dispute"])
            out(res)
        """)
        self.assertEqual(r, ["expected", "ask_owner", "expected", "ask_owner", 0.0])


if __name__ == "__main__":
    unittest.main()
