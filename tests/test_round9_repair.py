"""
Round 9 repair — what the round-9 skeptics found (skep9: regress_r9.py,
unsafe_r9.py, g1*.py … g5*.py, sp*.py).

Structural, each from its repro:

    1  an audience is the owner himself only when EVERY part of it is him:
       'me and Karen Novak', 'moi et ChatGPT', 'me and the man on the phone'
       were a silent yes from check_disclosure and guidance_for
    2  a merchant name with a character that shows as nothing inside it is a
       disguise, as a look-alike letter is: it asks him (the Hangul filler in
       'NET\\u3164FLIX.COM' passed as his plan and made the real bill a
       duplicate)
    3  a question about a subject his own rules close to this reader is
       answered by the rule, the same whatever he has recorded — so it is
       never counted as a guess (his own JEFFEREY asking about his own
       rule-held health was paused for an hour)
    5  the local model's system prompt stays under 40,000 characters however
       long his facts, values and goals are
    7  no answer about what his rules hold back tells a reader what it is:
       story_gaps, add_person by name, record_correction, a rule's topic
       when the topic is itself the secret, and forget by ids
    8  the sender of an e-mail is the address it was sent from; another
       address written in the From line makes it nobody he recorded
    9  a draft with no audience may be read by anyone; 'myself' is him
   10  a character that shows as nothing or as a blank is read both ways — as
       nothing, and as a space — by every reader that decides something

Invented people only: his daughter Anna, his ex-wife Karen Novak, a
neighbour Ed Lam, Dr Okafor, a friend Jo. Every address is on an example
domain.
"""

from __future__ import annotations

import json
import textwrap
import unittest

from test_his_own import HisOwnTest

RESET = """
import pathlib
def clear_watch():
    p = pathlib.Path(os.environ['JEFFEREY_CONSCIENCE_PATH'])
    for x in p.parent.glob(p.stem + '.searches.json*'):
        x.unlink()
def reset(sections=("rules", "facts", "memories", "rule_proposals", "priorities", "goals",
                    "people", "_notices", "expected_charges", "charges_seen", "corrections")):
    fresh()
    with access.owner_console():
        m.conscience.save_fresh(lambda d: [d.__setitem__(k, []) for k in sections])
        m.conscience.refresh()
    clear_watch()
"""

SURFACES = """
import jefferey_mcp as m, jefferey_chat as jc
h, c = http()
def three(tool, path, args, method="get"):
    fresh(); h.conscience.refresh()
    if method == "get":
        hx = c.get(path, params=args, headers=H(TA)).json()
    else:
        hx = c.post(path, json=args, headers=H(TA)).json()
    return [mcp_as(m, "jefferey", tool, args), hx, term(tool, args)]
"""


# ========================================================================== 1
class R1AnAudienceIsHimOnlyWhenAllOfItIsHim(HisOwnTest):
    """regress_r9 row 1, g1.py, g1b.py, g1d.py: check_disclosure's shortcut
    `or grounding.names_self(audience)` was true when ANY part of an audience
    was the owner, so 'me and Karen Novak' under 'Never tell Karen about my
    health' was allowed:true, 'the owner may always hear about themself', on
    MCP, HTTP GET /rules/check and the terminal — and with no rule at all."""

    def test_an_audience_with_someone_else_in_it_is_asked_about_everyone(self):
        r = self.py(pre=SURFACES + RESET, code="""
            reset()
            with access.owner_console():
                m.life.add_person("Karen Novak", "ex-wife", notes="karen.novak@example.com")
                m.rules.set_rule("disclosure", "health", "Never tell Karen about my health",
                                 audience="Karen Novak", allow=False)
                m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                 audience="any AI", allow=False)
                m.rules.set_rule("disclosure", "money", "Never tell anyone about my money",
                                 audience="anyone", allow=False)
            res = {}
            for aud, tag in (("me and Karen Novak", "health"), ("moi et Karen Novak", "health"),
                             ("me & karen.novak@example.com", "health"),
                             ("me, Karen Novak", "health"), ("I, Karen Novak", "health"),
                             ("Karen Novak and me", "health"), ("me but also Karen", "health"),
                             ("me and ChatGPT", "health"), ("moi et ChatGPT", "health"),
                             ("me, Replika", "health"), ("me and the neighbours", "money"),
                             # no rule at all on travel: silence is a no
                             ("me and the man on the phone", "travel"),
                             ("the bank and me", "travel"), ("me, Microsoft support", "travel"),
                             ("moi et le monsieur de la banque", "travel")):
                res[aud] = three("check_disclosure", "/rules/check",
                                 {"audience": aud, "tags": tag})
            for aud in ("me and Karen Novak", "moi et ChatGPT"):
                res["guidance " + aud] = [
                    mcp_as(m, "jefferey", "guidance_for", {"tags": "health", "audience": aud}),
                    c.get("/rules/guidance", params={"tags": "health", "audience": aud},
                          headers=H(TA)).json()]
            # he himself, however he writes it, still always hears about himself
            for aud in ("me", "Me", "myself", "just me", "moi", "moi-même", "me and myself"):
                res["self " + aud] = three("check_disclosure", "/rules/check",
                                           {"audience": aud, "tags": "health"})
            out(res)
        """)
        for aud, xs in r.items():
            if aud.startswith("guidance "):
                for g in xs:
                    self.assertFalse(g["disclosure"]["allowed"], (aud, g))
                    self.assertNotIn("always hear", json.dumps(g), aud)
                continue
            for x in xs:
                if aud.startswith("self "):
                    self.assertTrue(x["allowed"], (aud, x))
                    self.assertIn("always hear about themself", x["reason"], aud)
                else:
                    self.assertFalse(x["allowed"], (aud, x))
                    self.assertNotIn("always hear", x["reason"], aud)


# ========================================================================== 2
class R2AHiddenCharacterInAMerchantNameAsksHim(HisOwnTest):
    """regress_r9 row 2, g5b.py, g5.py: 'NET\\u3164FLIX.COM' at his Netflix
    price passed as 'expected' (quiet); the real NETFLIX.COM two days later
    was then a 'duplicate', $18.99 recoverable, and dispute_pack('Netflix')
    asked for $18.99. U+115F, U+1160, U+FFA0 and (already on e362c8d) U+200B
    did the same; a Cyrillic 'NЕTFLIX.COM' asked him."""

    def test_the_disguised_line_asks_him_and_the_real_bill_is_his_plan(self):
        r = self.py(pre=SURFACES + RESET, code="""
            from guardian import Guardian
            from conscience import Conscience
            import datetime as dt
            reset()
            with access.owner_console():
                m.guard.expect_charge("Netflix", 18.99, "monthly")
            fresh(); h.conscience.refresh()
            res = {"mcp": mcp_as(m, "jefferey", "check_charge", {
                       "merchant": "NET\\u3164FLIX.COM", "amount": 18.99, "date": "2026-09-01"}),
                   "http": c.post("/charges/check", json={
                       "merchant": "NETFLIX.COM", "amount": 18.99, "date": "2026-09-03"},
                       headers=H(TA)).json(),
                   "pack": mcp_as(m, "jefferey", "dispute_pack", {"merchant": "Netflix"})}
            for cp in (0x3164, 0x115F, 0x1160, 0xFFA0, 0x200B, 0xFE0F, 0x2800, 0xFFFC,
                       0x1D159, 0x0410):
                g = Guardian(Conscience(os.path.join(os.environ["HOME"], "..", f"g{cp}",
                                                     "c.json")),
                             owner_present=lambda: True, today=lambda: dt.date(2026, 10, 15))
                g.expect_charge("Netflix", 18.99, "monthly")
                name = "NET" + chr(cp) + "FLIX.COM" if cp != 0x0410 else "NЕTFLIX.COM"
                a = g.check_charge(name, 18.99, "2026-09-01")
                b = g.check_charge("NETFLIX.COM", 18.99, "2026-09-03")
                res[hex(cp)] = [a["verdict"], b["verdict"], b.get("recoverable")]
            out(res)
        """)
        self.assertEqual(r["mcp"]["verdict"], "ask_owner", r["mcp"])
        self.assertEqual(r["http"]["verdict"], "expected", r["http"])
        self.assertEqual(r["http"]["recoverable"], 0.0)
        self.assertEqual(r["pack"].get("amount_in_dispute") or 0, 0, r["pack"])
        for cp in ("0x3164", "0x115f", "0x1160", "0xffa0", "0x200b", "0xfe0f", "0x2800",
                   "0xfffc", "0x1d159", "0x410"):
            self.assertEqual(r[cp], ["ask_owner", "expected", 0.0], cp)


# ========================================================================== 3
class R3ASubjectHisRulesCloseIsNotAGuess(HisOwnTest):
    """regress_r9 row 3, g2i.py: with 'Never tell my health to any AI',
    twenty terminal explain_basis calls on 'my diabetes', 'my sugar', 'my
    medication', 'my doctor' and 'my health' counted as twenty searches that
    found nothing, and paused his own JEFFEREY for an hour on every surface:
    explain_basis('flights') and draft_guidance were refused, and he was told
    it searched 'the way someone guesses a PIN'."""

    def test_asking_about_what_his_rules_hold_back_never_pauses_his_jefferey(self):
        r = self.py(pre=SURFACES + RESET, code="""
            reset()
            with access.owner_console():
                m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                 audience="any AI", allow=False)
                m.conscience.remember_fact("I have type 2 diabetes and take metformin", "health")
                m.conscience.remember_fact("Likes an aisle seat on long flights", "travel")
            res = {"asked": []}
            qs = ["my diabetes", "my sugar", "my medication", "my doctor", "my health"]
            for i in range(25):
                x = term("explain_basis", {"topic": qs[i % 5]})
                res["asked"].append("refused" if x.get("refused") else
                                    ("metformin" in json.dumps(x)))
            for i in range(5):
                mcp_as(m, "jefferey", "priorities_for", {"context": qs[i]})
            res["flights"] = term("explain_basis", {"topic": "flights"})
            res["draft"] = mcp_as(m, "jefferey", "draft_guidance",
                                  {"purpose": "book flights for May", "recipient": "Anna"})
            m.conscience.refresh()
            res["notices"] = [n for n in store().get("_notices") or []
                              if n.get("kind") == "searches"]
            # the count still works for subjects that are not closed to it
            clear_watch()
            res["guesses"] = []
            for i in range(21):
                x = term("explain_basis", {"topic": f"my boat number {4800 + i}"})
                res["guesses"].append(bool(x.get("refused")))
            out(res)
        """)
        self.assertEqual(r["asked"], [False] * 25, r["asked"])   # never paused, never shown
        self.assertIn("aisle", json.dumps(r["flights"]))
        self.assertNotIn("refused", r["draft"])
        self.assertEqual(r["notices"], [])
        self.assertEqual(r["guesses"], [False] * 20 + [True], r["guesses"])


# ========================================================================== 5
class R5TheLocalModelsPromptFitsWhateverHeKeeps(HisOwnTest):
    """sk9v/mine/sp.py, sp2.py, sp3.py: the budget capped how many facts,
    values and goals went in, not how long they were: 200 goals of 300
    characters plus 30 facts and 15 values of about 300 characters each made
    a 61,052-character system prompt, and an ordinary large memory 51,178."""

    def test_the_system_prompt_stays_under_forty_thousand_characters(self):
        r = self.py(pre=SURFACES, code="""
            res = {}
            fresh()
            with access.owner_console():
                for i in range(200):
                    jc.conscience.add_goal(f"goal number {i}: " + "x" * 300)
            res["goals"] = jc.system_prompt()
            fresh()
            with access.owner_console():
                for i in range(30):
                    jc.conscience.remember_fact(f"fact {i}: " + "y" * 300, "general")
                for i in range(15):
                    jc.conscience.set_priority(context=f"ctx {i} " + "z" * 100,
                                               higher="h" * 100, lower="l" * 100)
            res["long"] = jc.system_prompt()
            fresh()
            with access.owner_console():
                for i in range(300):
                    m.conscience.remember_fact(f"Fact number {i}: I like walking by the river "
                                               f"on Tuesday mornings with Anna and the dog, "
                                               f"item {i}", "general")
                for i in range(80):
                    m.conscience.set_priority(context=f"context {i} about travel and errands",
                                              higher=f"quiet option {i}",
                                              lower=f"cheap option {i}")
                for i in range(40):
                    m.rules.set_rule("disclosure", "money", f"Never tell person {i} about my "
                                     f"money or my house or my car, rule {i}",
                                     audience="anyone", allow=False)
                for i in range(60):
                    m.life.add_person(f"Person{i} Example", "friend", notes="met at the "
                                      "community centre in 1990 and we play cards " * 3)
                    m.life.add_memory(f"Moment {i}: a long memory about the cottage and the "
                                      "lake and the dog " * 3, visibility="family")
            fresh()
            res["large"] = jc.system_prompt()
            out({k: [len(v), "shortened" in v, "explain_basis" in v] for k, v in res.items()})
        """)
        for k, (n, shortened, how) in r.items():
            self.assertLess(n, 40_000, k)
            self.assertTrue(how, k)
        self.assertTrue(r["long"][1], "it says it was shortened to fit")
        self.assertTrue(r["large"][1])


# ========================================================================== 7
class R7NoAnswerTellsWhatHisRulesHoldBack(HisOwnTest):
    """unsafe_r9.py G2, g2c.py, g2d.py, g2f.py, g2g.py — with 'Never tell my
    health to any AI', which binds his JEFFEREY too:
    (1) story_gaps listed 'Nothing recorded yet about Dr Okafor (HIV
        specialist)' while who_am_i held him back;
    (2) add_person('Dr Okafor', 'dentist') answered 'There is already a Dr
        Okafor (HIV specialist)' with his id, and ('Dr Okafor', 'HIV
        specialist') gave back his notes;
    (3) record_correction(context 'my HIV meds', protected 'cost', traded
        'brand name') answered 'He said that for my HIV meds, brand name
        matters more than cost', confirming a guessed value word for word;
    (4) a rule tagged 'hiv' was listed with its tag, and draft_guidance said
        do_not_mention ['hiv'];
    (5) check_disclosure(Ed, 'hiv') said 'the owner forbade it' and 'diabetes'
        'silence' — guidance_for and remove_rule by topic the same, unlimited;
    (6) forget(ids=[…]) told whether a held fact exists, and was never
        counted."""

    SETUP = SURFACES + RESET + """
def setup():
    reset()
    with access.owner_console():
        m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                         audience="any AI", allow=False)
        m.life.add_person("Dr Okafor", "HIV specialist", notes="sees me every March")
        m.life.add_person("Ed Lam", "neighbour", notes="lives at number 12")
        m.conscience.set_priority(context="my HIV meds", higher="brand name", lower="cost")
        m.rules.set_rule("disclosure", "hiv", "Never tell Ed about it", audience="Ed Lam",
                         allow=False)
        m.rules.set_rule("disclosure", "dementia", "Keep it from the neighbours",
                         audience="the neighbours", allow=False)
        m.conscience.remember_fact("I am on Biktarvy for HIV since 2019", "health")
        m.conscience.remember_fact("Likes an aisle seat on long flights", "travel")
    fresh(); h.conscience.refresh()
"""

    def test_story_gaps_and_add_person_never_name_a_held_person(self):
        r = self.py(pre=self.SETUP, code="""
            setup()
            res = {"gaps": [mcp_as(m, "jefferey", "story_gaps"), term("story_gaps", {}),
                            c.get("/life/gaps", headers=H(TA)).json()]}
            with access.owner_console():
                res["owner_gaps"] = m.life.story_gaps()
            for name, rel in (("Dr Okafor", "dentist"), ("Dr Okafor", "HIV specialist"),
                              ("Dr Okonkwo", "dentist")):
                setup()
                res[f"{name}|{rel}"] = [
                    mcp_as(m, "jefferey", "add_person", {"name": name, "relationship": rel}),
                    c.post("/life/people", json={"name": name, "relationship": rel},
                           headers=H(TA)).json(),
                    term("add_person", {"name": name, "relationship": rel})]
                res[f"{name}|{rel}|his"] = [p for p in store()["people"]
                                            if p.get("relationship") == "HIV specialist"
                                            and p.get("notes")]
            out(res)
        """)
        for g in r["gaps"]:
            s = json.dumps(g)
            self.assertNotIn("Okafor", s)
            self.assertNotIn("HIV", s)
            self.assertIn("Ed Lam", s)
        self.assertIn("Okafor", json.dumps(r["owner_gaps"]))
        fresh_keys = [sorted(x.keys()) for x in r["Dr Okonkwo|dentist"]]
        for k in ("Dr Okafor|dentist", "Dr Okafor|HIV specialist"):
            for i, x in enumerate(r[k]):
                s = json.dumps(x)
                self.assertNotIn("sees me every March", s, k)
                self.assertNotIn("possible_duplicate_of", x, k)
                self.assertNotIn("There is already", s, k)
                self.assertFalse(x.get("matched_existing"), k)
                self.assertEqual(sorted(x.keys()), fresh_keys[i], (k, x))
                if k.endswith("dentist"):
                    self.assertNotIn("HIV", s, k)
            # his own record is as he left it, with no change proposed on it
            his = r[k + "|his"]
            self.assertEqual(len(his), 1, his)
            self.assertEqual(his[0]["notes"], "sees me every March")
            self.assertNotIn("proposed", his[0])

    def test_a_correction_never_confirms_a_held_value(self):
        r = self.py(pre=self.SETUP, code="""
            setup()
            args = {"context": "my HIV meds", "what_was_suggested": "the brand",
                    "what_user_chose": "the generic", "value_protected": "cost",
                    "value_traded_away": "brand name"}
            other = dict(args, value_traded_away="convenience")
            res = {"held": three("record_correction", "/corrections", args, "post")}
            setup()
            res["guess"] = three("record_correction", "/corrections", other, "post")
            res["his"] = [p for p in store()["priorities"] if p.get("higher") == "brand name"]
            out(res)
        """)
        for k in ("held", "guess"):
            for x in r[k]:
                s = json.dumps(x)
                self.assertNotIn("brand name matters more", s, k)
                self.assertNotIn("question_for_owner", x, k)
                self.assertNotIn('"higher": "brand name"', s, k)
        # a right guess and a wrong one are answered alike
        strip = lambda x: {k: v for k, v in x.items()                       # noqa: E731
                           if k not in ("already_counted", "note")}
        self.assertEqual(sorted(strip(r["held"][0])), sorted(strip(r["guess"][0])))
        # his stated value is as he left it
        self.assertEqual(len(r["his"]), 1)
        self.assertEqual((r["his"][0]["lower"], r["his"][0].get("against", 0)), ("cost", 0))

    def test_a_rules_topic_is_never_the_secret(self):
        r = self.py(pre=self.SETUP, code="""
            setup()
            res = {"list": [mcp_as(m, "jefferey", "list_rules"),
                            c.get("/rules", headers=H(TA)).json(), term("list_rules", {})],
                   "guide": mcp_as(m, "jefferey", "draft_guidance",
                                   {"purpose": "thank Ed for the shovelling",
                                    "recipient": "Ed Lam"})}
            with access.owner_console():
                res["owner"] = m.rules.listed()
            for t in ("hiv", "diabetes", "cancer", "VIH", "dementia", "démence"):
                clear_watch()
                res["check " + t] = [mcp_as(m, "jefferey", "check_disclosure",
                                            {"audience": a, "tags": t})
                                     for a in ("Ed Lam", "the neighbours")]
                res["guidance " + t] = mcp_as(m, "jefferey", "guidance_for",
                                              {"tags": t, "audience": "Ed Lam"})
                res["remove " + t] = mcp_as(m, "jefferey", "remove_rule", {"rule_id_or_text": t})
            out(res)
        """)
        for x in r["list"]:
            s = json.dumps(x).lower()
            self.assertNotIn("hiv", s)
            self.assertNotIn("dementia", s)
        dis = json.dumps(r["guide"].get("disclosure")).lower()
        self.assertNotIn("hiv", dis)
        self.assertNotIn("dementia", dis)
        self.assertIn("health", dis)
        self.assertIn("hiv", json.dumps(r["owner"]).lower())        # he reads his own
        ts = ("hiv", "diabetes", "cancer", "VIH", "dementia", "démence")
        norm = lambda x, t: json.dumps(x, ensure_ascii=False).replace(    # noqa: E731
            json.dumps(t.lower(), ensure_ascii=False), '"T"')
        for kind in ("check", "guidance", "remove"):
            seen = {norm(r[f"{kind} {t}"], t) for t in ts}
            self.assertEqual(len(seen), 1, (kind, seen))
        for t in ts:
            for x in r["check " + t]:
                self.assertFalse(x["allowed"], t)
            self.assertEqual(r["remove " + t].get("step"), "nothing", t)

    def test_forgetting_by_an_id_it_may_not_read_is_answered_as_an_unknown_id(self):
        r = self.py(pre=self.SETUP, code="""
            setup()
            fid = [f for f in store()["facts"] if "Biktarvy" in f["fact"]][0]["id"]
            res = {"held": mcp_as(m, "jefferey", "forget", {"ids": [fid]}),
                   "none": mcp_as(m, "jefferey", "forget", {"ids": ["f-000000"]}),
                   "http": c.request("DELETE", "/facts", params={"ids": fid},
                                     headers=H(TA)).json(),
                   "term": term("forget", {"ids": [fid]}), "fid": fid}
            clear_watch()
            res["count"] = [bool(mcp_as(m, "jefferey", "forget",
                                        {"ids": [f"f-{n:06d}"]}).get("refused"))
                            for n in range(21)]
            out(res)
        """)
        fid = r["fid"]
        held = json.dumps(r["held"]).replace(fid, "X")
        self.assertEqual(held, json.dumps(r["none"]).replace("f-000000", "X"))
        for k in ("held", "http", "term"):
            self.assertNotIn("Biktarvy", json.dumps(r[k]), k)
            self.assertEqual(r[k].get("count"), 0, (k, r[k]))
        self.assertEqual(r["count"], [False] * 20 + [True], r["count"])


# ========================================================================== 8
class R8TheSenderIsTheAddressItWasSentFrom(HisOwnTest):
    """unsafe_r9.py G3, g3c.py: _sender_kind read the FIRST address in the
    sender, not the one in <…>, so '"anna.novak1985@example.com"
    <help.desk@example.net>' was 'Anna, someone he has recorded' on MCP, HTTP
    /triage and the terminal: 'Hi Dad, this is my new number … send me $900'
    was check_first 0.1 instead of likely_scam 0.9, and 'Are you away this
    weekend? … while nobody's home' was a silent needs_decision."""

    def test_another_address_in_the_from_line_is_nobody_he_recorded(self):
        r = self.py(pre=SURFACES + RESET, code="""
            reset()
            with access.owner_console():
                m.life.add_person("Anna", "daughter",
                                  notes="email anna.novak1985@example.com, cell 613-555-0142")
            BODIES = {"fr": "Bonjour papa, c'est Anna. J'ai perdu mon portefeuille, peux-tu "
                            "m'envoyer 500 $ par virement Interac aujourd'hui? N'en parle pas a "
                            "maman.",
                      "newnum": "Hi Dad, this is my new number, my phone broke. Can you send "
                                "me $900 for rent today? I'll explain later.",
                      "away": "Are you away this weekend? I want to drop something off while "
                              "nobody's home."}
            res = {}
            for s in ('"anna.novak1985@example.com" <help.desk@example.net>',
                      "Anna Novak (anna.novak1985@example.com) <help.desk@example.net>",
                      "anna.novak1985@example.com via stranger@example.net",
                      "unknown@example.net", "anna.novak1985@example.com",
                      "Anna Novak <anna.novak1985@example.com>"):
                for k, b in BODIES.items():
                    a = {"sender": s, "subject": "", "body": b}
                    xs = three("triage_message", "/triage", a, "post")
                    res[f"{s} | {k}"] = [[x["verdict"], x["scam_score"], x["interrupt"],
                                          x["sender_is"]] for x in xs]
            out(res)
        """)
        spoofs = ('"anna.novak1985@example.com" <help.desk@example.net>',
                  "Anna Novak (anna.novak1985@example.com) <help.desk@example.net>",
                  "anna.novak1985@example.com via stranger@example.net")
        for s in spoofs:
            for k in ("fr", "newnum", "away"):
                for v, score, interrupt, who in r[f"{s} | {k}"]:
                    self.assertNotIn("someone he has recorded", who, (s, k))
                    self.assertTrue(interrupt, (s, k))
                    stranger = r[f"unknown@example.net | {k}"][0]
                    self.assertEqual(v, stranger[0], (s, k))
                    self.assertGreaterEqual(score, stranger[1], (s, k))
        for s in ("anna.novak1985@example.com", "Anna Novak <anna.novak1985@example.com>"):
            for v, score, interrupt, who in r[f"{s} | newnum"]:
                self.assertIn("Anna, someone he has recorded", who, s)


# ========================================================================== 9
class R9ADraftWithNoAudienceMayBeReadByAnyone(HisOwnTest):
    """unsafe_r9.py G4, g4.py, g1d.py: check_draft('Dad has HIV') with the
    audience left out, empty or only spaces was ok:true — 'Nothing in it goes
    against his rules or his safety' — on the terminal, MCP and HTTP
    /draft-check, while the same text to 'the neighbours' asked him; and
    draft_guidance with no recipient handed over 'I have HIV' and 'I owe
    $40,000 on my Visa' with no disclosure block. Eight more drafts were ok
    to the neighbours. 'myself' asked where 'me' did not."""

    def test_no_audience_is_checked_as_anyone_on_every_surface(self):
        r = self.py(pre=SURFACES + RESET, code="""
            reset()
            with access.owner_console():
                m.conscience.remember_fact("I have HIV", "health")
                m.conscience.remember_fact("I owe $40,000 on my Visa", "money")
                m.conscience.remember_fact("I was in rehab in 2019", "health")
                m.conscience.remember_fact("I have early dementia", "health")
                m.conscience.remember_fact("J'ai un cancer de la prostate", "health")
            fresh(); h.conscience.refresh()
            res = {}
            for a in (None, "", "   "):
                args = {"text": "Dad has HIV"} if a is None else {"text": "Dad has HIV",
                                                                  "audience": a}
                res[repr(a)] = three("check_draft", "/draft-check", args, "post")
                g = {"purpose": "a letter about my HIV and my debts"}
                if a is not None:
                    g["recipient"] = a
                res["guide " + repr(a)] = mcp_as(m, "jefferey", "draft_guidance", g)
            for d in ("He's got the virus", "Laszlo has AIDS", "Dad's mind is going",
                      "Papa perd la mémoire", "Dad maxed out his Visa",
                      "Dad drank too much back then", "Dad was in a treatment centre",
                      "Dad's prostate is acting up again"):
                res["word " + d] = three("check_draft", "/draft-check",
                                         {"text": d, "audience": "the neighbours"}, "post")
            for a in ("me", "myself", "just me", "moi"):
                res["self " + a] = mcp_as(m, "jefferey", "check_draft",
                                          {"text": "Dad has HIV", "audience": a})
            res["bbq"] = mcp_as(m, "jefferey", "check_draft",
                                {"text": "Lovely day for a barbecue on Sunday."})
            out(res)
        """)
        for k, x in r.items():
            if k.startswith("guide "):
                self.assertIn("disclosure", x, k)
                facts = [f["fact"] for f in x.get("their_facts_here", [])]
                self.assertEqual(facts, [], (k, facts))
            elif k.startswith("self "):
                self.assertTrue(x["ok"], (k, x))
            elif k == "bbq":
                self.assertTrue(x["ok"], x)
            else:
                for y in x:
                    self.assertFalse(y["ok"], (k, y))
                    self.assertTrue(y.get("ask_owner"), (k, y))


# ========================================================================= 10
class R10ABlankIsReadAsNothingAndAsASpace(HisOwnTest):
    """unsafe_r9.py G5, g5.py: U+2800 (braille blank), U+1D159 (musical null
    notehead) and U+FFFC show as nothing or as a blank but are not
    default-ignorable: 'Let the plumber i\\u2800n' was allowed under errands
    on the terminal, MCP and HTTP; 'I take Ozem\\u2800pic' reached claude-raw
    under 'Never tell my health to any AI'; 'Jo is on che\\u2800mo' was ok;
    an engine's 'My PIN is 7\\u28007\\u28003\\u28001' was stored. Read only as
    nothing, a blank between words would glue them ('Unlock\\u200bthe
    \\u200bfront\\u200bdoor' was already allowed), so every reader that
    decides reads both ways."""

    def test_every_reader_reads_a_blank_both_ways(self):
        r = self.py(pre=SURFACES + RESET, code="""
            res = {}
            for cp in (0x2800, 0x1D159, 0xFFFC):
                ch = chr(cp)
                reset()
                with access.owner_console():
                    m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                     audience="any AI", allow=False)
                    m.conscience.remember_fact(f"I take Ozem{ch}pic on Sundays", "general")
                    m.conscience.remember_fact(f"I{ch}take{ch}Wegovy{ch}on{ch}Mondays", "general")
                    m.life.add_person("Jo", "friend")
                    m.conscience.remember_fact("Jo is on chemo", "health")
                    m.conscience.set_permission("errands", "act")
                fresh(); h.conscience.refresh()
                row = {"out": json.dumps(mcp_as(m, "claude-raw", "get_conscience"),
                                         ensure_ascii=False)}
                for d in (f"Let the plumber i{ch}n", f"Let{ch}the{ch}plumber{ch}in",
                          f"Unlock{ch}the{ch}front{ch}door"):
                    row[d] = three("authorize_action", "/actions/authorize",
                                   {"category": "errands", "description": d}, "post")
                row["draft"] = mcp_as(m, "jefferey", "check_draft",
                                      {"text": f"Jo is on che{ch}mo", "audience": "the neighbours"})
                row["pin"] = mcp_as(m, "jefferey", "remember_fact",
                                    {"fact": f"My PIN is 7{ch}7{ch}3{ch}1", "category": "general"})
                row["pin2"] = mcp_as(m, "jefferey", "remember_fact",
                                     {"fact": f"My{ch}PIN{ch}is{ch}7731", "category": "general"})
                row["pw"] = mcp_as(m, "jefferey", "remember_fact",
                                   {"fact": f"Pass{ch}word: Sunflower88", "category": "general"})
                res[hex(cp)] = row
            # zero-width and filler characters used as spaces
            reset()
            with access.owner_console():
                m.conscience.set_permission("errands", "act")
            fresh()
            for ch in ("\\u200b", "\\u3164", "\\u2060"):
                d = f"Unlock{ch}the{ch}front{ch}door"
                res["gap " + d] = three("authorize_action", "/actions/authorize",
                                        {"category": "errands", "description": d}, "post")
                res["gap pin " + d] = mcp_as(m, "jefferey", "remember_fact",
                                             {"fact": f"My{ch}PIN{ch}is{ch}7731",
                                              "category": "general"})
            res["plain"] = mcp_as(m, "jefferey", "authorize_action",
                                  {"category": "errands", "description": "Pick up the groceries"})
            out(res)
        """)
        plain = r.pop("plain")
        self.assertTrue(plain["allowed"], plain)
        for k, row in r.items():
            if k.startswith("gap pin "):
                self.assertTrue(row.get("refused"), (k, row))
                continue
            if k.startswith("gap "):
                for x in row:
                    self.assertFalse(x["allowed"], (k, x))
                continue
            self.assertNotIn("Ozem", row.pop("out"), k)
            for d, xs in row.items():
                if d == "draft":
                    self.assertFalse(xs["ok"], (k, xs))
                elif d in ("pin", "pin2", "pw"):
                    self.assertTrue(xs.get("refused"), (k, d, xs))
                else:
                    for x in xs:
                        self.assertFalse(x["allowed"], (k, d, x))

    def test_a_message_with_blanks_for_spaces_is_read_both_ways(self):
        # the neighbour of reading a blank as nothing: put between the words, it
        # glued 'send $3000 bail in gift cards' together and hid the scam
        # (likely_scam 0.6 became suspicious 0.3), and 'are you away … while
        # nobody's home' was routine and silent
        r = self.py(pre=SURFACES + RESET, code="""
            msgs = {"bail": "Grandpa it's me, I'm in jail, please send $3000 bail in gift cards "
                            "and don't tell mom",
                    "bank": "Your bank account is locked. Verify your password now at the link",
                    "away": "Are you away this weekend? I want to drop something off while "
                            "nobody's home."}
            res = {}
            for name, ch in (("space", " "), ("2800", "\\u2800"), ("200b", "\\u200b"),
                             ("3164", "\\u3164")):
                for k, b in msgs.items():
                    a = {"sender": "unknown@example.net", "subject": "",
                         "body": b.replace(" ", ch)}
                    res[f"{name} {k}"] = [[x["verdict"], x["scam_score"], x["interrupt"]]
                                          for x in three("triage_message", "/triage", a, "post")]
            out(res)
        """)
        for name in ("2800", "200b", "3164"):
            for k in ("bail", "bank", "away"):
                plain = r[f"space {k}"][0]
                for v, score, interrupt in r[f"{name} {k}"]:
                    self.assertTrue(interrupt, (name, k))
                    self.assertEqual(v, plain[0], (name, k))
                    self.assertGreaterEqual(score, plain[1], (name, k))

    def test_wegovy_between_blanks_is_his_health_too(self):
        r = self.py("""
            import grounding, egress, conscience
            # a line separator shows as a blank: it is a space, and the door
            # reads 'i n' back as 'in' as it does for a plain space
            sep = [conscience.entry_words("Let the plumber i" + ch + "n")
                   for ch in ("\u2028", "\u2029", "\u0085", " ")]
            res = {}
            for cp in (0x2800, 0x1D159, 0xFFFC, 0x200B, 0x3164):
                ch = chr(cp)
                res[hex(cp)] = [grounding.sensitivity(f"I{ch}take{ch}Wegovy"),
                                grounding.sensitivity(f"I take Weg{ch}ovy"),
                                grounding.fold(f"Ozem{ch}pic"),
                                egress.looks_secret(f"Netflix{ch}password:{ch}Bluebird77")]
            out({"sep": sep, "res": res})
        """)
        self.assertTrue(all(r["sep"]), r["sep"])
        for k, (a, b, f, s) in r["res"].items():
            self.assertIn("health", a, k)
            self.assertIn("health", b, k)
            self.assertEqual(f, "ozempic", k)
            self.assertTrue(s, k)


if __name__ == "__main__":
    unittest.main()
