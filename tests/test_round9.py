"""
Round 9 — what the round-8 skeptics still found (round8.json: v2, confirm).

Structural first — each of these follows who reads and what release would
show them, never the meaning of the words:

    G1  a no for himself ('me', 'myself', 'just me', 'moi', or left at its
        default) is a no for everyone and every AI but his own JEFFEREY; a
        yes for him widens nothing
    G2  no search is an oracle: every engine-facing match over his life
        matches only what release would show that engine, lists only what it
        may read, and twenty searches that find nothing in ten minutes pause
        that key's searches for an hour — and he is told
    G3  a sender is someone he recorded only by a whole address or a whole
        number, never a part of one, never a display name alone
    G4  his own private facts in a draft: a first-person fact is about him,
        and a draft that carries a word of it or of its kind, to someone who
        may not hear it, is brought to him — whoever it names
    G5  invisible characters and combining marks are read as nothing,
        everywhere words are read
    G6  his own details are his in any spacing (K1A0B1 is K1A 0B1)

Then the listed vocabulary, bounded — exactly these:

    G8  secrets: family code words, recovery phrases, logins, security Q&A,
        an account's password after its name, a PIN in words
    G9  health and money words: HIV medicines, CPAP, AA, incontinence,
        personal care, hearing aids, ostomy, 'the big C'; borrowed, lent,
        'grand' as thousands
    G10 the door: telling a PIN, the run of the house, walking someone
        through it, 'say yes' at the front, home mode, pressing a digit for a
        caller, holding the front, the chain, the snib, smart-lock apps,
        French, Spanish and Italian

(G7 is test hygiene in tests/test_round8_repair.py.)

Invented people only: his daughter Anna, his ex-wife Karen Novak, a
neighbour Ed Lam, friends Jo, Li, Bo and Ty, a 'grandson' Mike an AI made
up. Every address is on an example domain.
"""

from __future__ import annotations

import json
import textwrap
import unittest

from test_his_own import HisOwnTest
from test_paperwork import PaperworkTest

# The owner's memories, reset between rows, for G1 and G9.
RESET = """
def reset(sections=("rules", "facts", "memories", "rule_proposals", "priorities", "goals",
                    "people", "_notices")):
    fresh()
    with access.owner_console():
        m.conscience.save_fresh(lambda d: [d.__setitem__(k, []) for k in sections])
        m.conscience.refresh()
"""


# ========================================================================= G1
class G1ANoForHimselfIsANoForEveryone(HisOwnTest):
    """v2 F1 case 1 (f1.py, f1eng.py) and the confirm info line: 'Keep my
    health to myself' for 'myself', 'just me', 'moi', 'me', 'Me' or 'ME' —
    or with no audience at all, which every surface stored as 'me' — held
    for nobody: holds_for 'me', and the family key read his diabetes."""

    SETUP = RESET + """
import jefferey_mcp as m, jefferey_chat as jc
h, c = http()
def setup():
    reset()
    with access.owner_console():
        m.life.add_memory("Diagnosed with type 2 diabetes in June.", visibility="family",
                          tags="health")
        m.life.add_memory("Flew to Calgary in May for the graduation.", visibility="family",
                          tags="travel")
        m.conscience.remember_fact("I have type 2 diabetes and take metformin", "health")
        m.conscience.remember_fact("Likes an aisle seat on long flights", "travel")
def peek():
    fresh(); h.conscience.refresh()
    fam = c.get("/life", headers=H(TF)).text
    return {"family_diabetes": "diabetes" in fam,
            "family_calgary": "Calgary" in fam,
            "claude_aisle": "aisle" in json.dumps(
                mcp_as(m, "claude-raw", "explain_basis", {"topic": "flights"})),
            "gpt_aisle": "aisle" in c.get("/basis", params={"topic": "flights"},
                                          headers=H(TG)).text,
            "jefferey_metformin": "metformin" in json.dumps(
                mcp_as(m, "jefferey", "explain_basis", {"topic": "diabetes"})),
            "jefferey_aisle": "aisle" in json.dumps(
                mcp_as(m, "jefferey", "explain_basis", {"topic": "flights"}))}
"""
    SELF_WORDS = ("myself", "just me", "moi", "me", "Me", "ME", "only me", "I", "moi-même",
                  "juste moi", "MYSELF", "Moi-Meme", "my​self", "mе" ,
                  "myѕelf", "just  me", "me myself")

    def test_a_no_for_himself_holds_for_everyone_but_his_own_jefferey(self):
        r = self.py(pre=textwrap.dedent(self.SETUP), code="""
            setup()
            res = {"before": peek()}
            for aud in %r:
                setup()
                with access.owner_console():
                    s1 = m.rules.set_rule("disclosure", "health", "Keep my health to myself",
                                          audience=aud, allow=False)
                    s2 = m.rules.set_rule("disclosure", "travel", "My trips are mine",
                                          audience=aud, allow=False)
                res[aud] = {**peek(), "holds_for": [s1.get("holds_for"), s2.get("holds_for")],
                            "note": s1.get("note", "")}
            out(res)
        """ % (self.SELF_WORDS,))
        before = r.pop("before")
        self.assertTrue(all(before.values()), before)          # with no rule, all read it
        for aud, x in r.items():
            self.assertEqual(x["holds_for"], ["everyone", "everyone"], aud)
            self.assertFalse(x["family_diabetes"], aud)
            self.assertFalse(x["family_calgary"], aud)
            self.assertFalse(x["claude_aisle"], aud)
            self.assertFalse(x["gpt_aisle"], aud)
            # his own JEFFEREY, which looks after him, still reads his life
            self.assertTrue(x["jefferey_metformin"], aud)
            self.assertTrue(x["jefferey_aisle"], aud)
            self.assertIn("everyone", x["note"], aud)
            self.assertIn("except your own JEFFEREY", x["note"], aud)

    def test_a_no_left_at_its_default_holds_for_everyone_on_every_surface(self):
        r = self.py(pre=textwrap.dedent(self.SETUP), code="""
            res = {}
            setup()
            with access.owner_console():
                res["owner"] = m.rules.set_rule("disclosure", "travel",
                                                "Never tell anyone about my trips", allow=False)
            res["owner_peek"] = peek()
            setup()
            res["mcp"] = mcp_as(m, "jefferey", "set_rule", {"kind": "disclosure", "tags": "travel",
                                "instruction": "Never tell anyone about his trips", "allow": False})
            res["mcp_peek"] = peek()
            setup()
            p = c.post("/rules", json={"kind": "disclosure", "tags": "travel", "allow": False,
                                       "instruction": "Never tell anyone about his trips"},
                       headers=H(TA))
            res["http"] = p.json()
            res["http_peek"] = peek()
            setup()
            res["term"] = term("set_rule", {"kind": "disclosure", "tags": "travel", "allow": False,
                                            "instruction": "Never tell anyone about his trips"})
            res["term_peek"] = peek()
            # a rule for how to react to HIM is still for him, by default
            setup()
            with access.owner_console():
                res["reaction"] = m.rules.set_rule("reaction", "father",
                                                   "When I talk about my father, just listen")
            res["listen"] = mcp_as(m, "jefferey", "guidance_for", {"tags": "father"})
            out(res)
        """)
        for k in ("owner", "mcp", "http", "term"):
            self.assertEqual(r[k]["holds_for"], "everyone", (k, r[k]))
            self.assertIn("did not say who", r[k]["note"], k)
            self.assertIn("everyone", r[k]["note"], k)
            p = r[k + "_peek"]
            self.assertFalse(p["family_calgary"], k)
            self.assertFalse(p["claude_aisle"], k)
            self.assertFalse(p["gpt_aisle"], k)
            self.assertTrue(p["jefferey_aisle"], k)
        self.assertEqual(r["reaction"]["audience"], "me")
        self.assertEqual(r["listen"]["react_this_way"], ["When I talk about my father, just listen"])

    def test_a_yes_for_himself_widens_nothing(self):
        r = self.py(pre=textwrap.dedent(self.SETUP), code="""
            res = {}
            for aud in ("me", "myself", "moi", ""):
                setup()
                with access.owner_console():
                    m.rules.set_rule("disclosure", "travel", "Nobody hears about my trips",
                                     audience="anyone", allow=False)
                    kw = {"audience": aud} if aud else {}
                    m.rules.set_rule("disclosure", "travel", "I may hear about my trips",
                                     allow=True, **kw)
                m.conscience.refresh()
                res[aud or "(default)"] = {**peek(),
                    "family_may": m.rules.check_disclosure("family", "travel")["allowed"],
                    "anyone_may": m.rules.check_disclosure("the neighbours", "travel")["allowed"]}
            out(res)
        """)
        for aud, x in r.items():
            for k in ("family_calgary", "claude_aisle", "gpt_aisle", "family_may", "anyone_may"):
                self.assertFalse(x[k], (aud, k))


# ========================================================================= G2
class G2NoSearchIsAnOracle(HisOwnTest):
    """v2 F3 case 1 (f3brute.py): forget_life('4821') answered with
    also_mentioned 'My bank PIN is [hidden…]' and forget_life('4822') with
    nothing, on MCP, HTTP DELETE /life and the terminal — a brute force of four
    digits took 40 seconds. v1 S5 (s5o.py): forget('Biktarvy') counted a fact
    his rule keeps from every AI; forget_life('canal') and close_goal('viral')
    found what was held back."""

    def _clear_watch(self):
        return ("import pathlib\n"
                "def clear_watch():\n"
                "    p = pathlib.Path(os.environ['JEFFEREY_CONSCIENCE_PATH'])\n"
                "    for x in p.parent.glob(p.stem + '.searches.json*'):\n"
                "        x.unlink()\n")

    def test_forget_life_answers_a_right_guess_as_it_answers_a_wrong_one(self):
        r = self.py(pre=self._clear_watch(), code="""
            import jefferey_mcp as m, jefferey_chat as jc
            h, c = http()
            with access.owner_console():
                m.conscience.remember_fact("My bank PIN is 4821", "general")
                m.conscience.remember_fact("Netflix password: Bluebird77", "general")
                m.life.add_memory("Garage code 7731, Anna knows it", visibility="family")
                m.life.add_person("Ed Lam", "neighbour", notes="his alarm code is 2468")
            def plain(x):
                return {k: v for k, v in x.items() if k not in ("confirm", "expires")}
            res = {}
            for right, wrong in (("4821", "4822"), ("Bluebird77", "Bluebird78"),
                                 ("7731", "7732"), ("2468", "2469")):
                clear_watch()
                for g in (right, wrong):
                    res[g] = [plain(mcp_as(m, "jefferey", "forget_life", {"contains": g})),
                              plain(c.delete("/life", params={"contains": g}, headers=H(TA)).json()),
                              plain(term("forget_life", {"contains": g})),
                              plain(mcp_as(m, "jefferey", "forget", {"contains": g}))]
            out(res)
        """)
        for right, wrong in (("4821", "4822"), ("Bluebird77", "Bluebird78"),
                             ("7731", "7732"), ("2468", "2469")):
            self.assertEqual(json.dumps(r[right]).replace(right, "X"),
                             json.dumps(r[wrong]).replace(wrong, "X"), right)
            for x in r[right]:
                self.assertNotIn("also_mentioned", x, (right, x))
                self.assertEqual(x.get("count"), 0, (right, x))

    def test_what_his_rules_keep_from_the_reader_is_never_matched_or_counted(self):
        r = self.py(pre=self._clear_watch(), code="""
            import jefferey_mcp as m
            h, c = http()
            with access.owner_console():
                m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                 audience="any AI", allow=False)
                m.conscience.remember_fact("I am on Biktarvy for HIV since 2019", "health")
                m.life.add_memory("The day Dr Patel told me I was HIV positive, I walked along "
                                  "the canal for hours.", visibility="private")
                m.conscience.add_goal("Keep my HIV viral load undetectable")
                m.life.add_person("Karen Novak", "ex-wife")
                m.rules.set_rule("disclosure", "health", "Never tell Karen Novak that I have HIV",
                                 audience="Karen Novak", allow=False)
                m.life.add_person("Ed Lam", "neighbour")
                m.conscience.remember_fact("Ed Lam has HIV and told only me", "health")
                m.conscience.remember_fact("Ed Lam fixed the fence in May", "general")
            res = {}
            for w in ("Biktarvy", "HIV", "canal", "viral", "cancer", "undetectable"):
                clear_watch()
                res[w] = {t: mcp_as(m, "jefferey", t, a) for t, a in (
                    ("forget", {"contains": w}), ("forget_life", {"contains": w}),
                    ("close_goal", {"contains": w}), ("remove_rule", {"rule_id_or_text": w}))}
                res[w]["basis"] = mcp_as(m, "jefferey", "explain_basis", {"topic": w})
                res[w]["http_basis"] = c.get("/basis", params={"topic": w}, headers=H(TA)).json()
            clear_watch()
            res["ed"] = mcp_as(m, "jefferey", "forget_life", {"contains": "Ed Lam"})
            out(res)
        """)
        for w in ("Biktarvy", "HIV", "canal", "viral", "cancer", "undetectable"):
            for t in ("forget", "forget_life", "close_goal", "remove_rule"):
                x = r[w][t]
                self.assertEqual(x.get("step"), "nothing", (w, t, x))
                self.assertEqual(x.get("count"), 0, (w, t, x))
                self.assertNotIn("also_mentioned", x, (w, t))
            for t in ("basis", "http_basis"):
                self.assertEqual(r[w][t]["facts"], [], (w, t))
                self.assertNotIn("held_back", r[w][t], (w, t, r[w][t]))
        # the person he can see is named; what mentions them that he keeps from
        # every AI is not on the list, nor counted
        ed = r["ed"]
        self.assertEqual(ed["step"], "preview")
        also = json.dumps(ed.get("also_mentioned", []))
        self.assertIn("fixed the fence", also)
        self.assertEqual(len(ed.get("also_mentioned", [])), 1, ed)
        self.assertNotIn("HIV", json.dumps(ed))

    def test_twenty_searches_that_find_nothing_pause_that_key_for_an_hour(self):
        r = self.py(pre=self._clear_watch(), code="""
            import jefferey_mcp as m, jefferey_chat as jc, conscience as cs, time
            h, c = http()
            with access.owner_console():
                m.conscience.remember_fact("Likes an aisle seat on long flights", "travel")
                m.conscience.remember_fact("My bank PIN is 4821", "general")
            clear_watch()
            res = {"tries": []}
            for n in range(4800, 4820):                       # twenty that find nothing
                x = mcp_as(m, "jefferey", "forget_life", {"contains": str(n)})
                res["tries"].append(x.get("step") or x.get("refused"))
            # the twenty-first: refused on every surface, even what would match
            res["mcp"] = mcp_as(m, "jefferey", "explain_basis", {"topic": "flights"})
            res["http"] = c.delete("/life", params={"contains": "4821"}, headers=H(TA)).json()
            res["term"] = term("priorities_for", {"context": "flights"})
            res["story"] = mcp_as(m, "jefferey", "tell_story", {"theme": "flights"})
            res["rule"] = mcp_as(m, "jefferey", "remove_rule", {"rule_id_or_text": "flights"})
            # reading without a search still works
            res["brief"] = mcp_as(m, "jefferey", "daily_brief")
            # another key is not paused
            res["other"] = mcp_as(m, "claude-raw", "explain_basis", {"topic": "flights"})
            # he is told, in his notices
            m.conscience.refresh()
            res["notices"] = m.conscience.notices()
            # the owner himself is never paused
            with access.owner_console():
                res["owner"] = m.conscience.explain_basis("flights")
            # an hour later the key may search again
            later = time.time() + 3601
            cs._search_clock = lambda: later
            res["later"] = mcp_as(m, "jefferey", "explain_basis", {"topic": "flights"})
            out(res)
        """)
        self.assertEqual(r["tries"], ["nothing"] * 20, r["tries"])
        for k in ("mcp", "http", "term", "story", "rule"):
            x = r[k]
            if isinstance(x, list):              # priorities_for answers with a list
                self.assertEqual(len(x), 1, x)
                x = x[0]
            self.assertTrue(x.get("refused"), (k, x))
            self.assertIn("an hour", x["reason"], k)
            self.assertIn("20", x["reason"], k)
            self.assertNotIn("aisle", json.dumps(x), k)
        self.assertNotIn("refused", r["brief"])
        self.assertIn("aisle", json.dumps(r["other"]))
        self.assertIn("aisle", json.dumps(r["owner"]))
        self.assertIn("aisle", json.dumps(r["later"]))
        said = " ".join(n["what"] for n in r["notices"])
        self.assertIn("jefferey", said)
        self.assertIn("20", said)
        self.assertIn("an hour", said)

    def test_searches_that_find_something_do_not_count(self):
        r = self.py(pre=self._clear_watch(), code="""
            import jefferey_mcp as m
            with access.owner_console():
                m.conscience.remember_fact("Likes an aisle seat on long flights", "travel")
            clear_watch()
            res = [bool(mcp_as(m, "jefferey", "explain_basis", {"topic": "flights"}).get("facts"))
                   for _ in range(30)]
            out(res)
        """)
        self.assertEqual(r, [True] * 30)


# ========================================================================= G3
class G3ASenderIsSomeoneOnlyByAWholeMatch(HisOwnTest):
    """confirm (n1b.py): triage tested `addr in notes`, so '5@example.com'
    and 'novak1985@example.com' were 'Anna, someone he has recorded' (scam
    score 0.0 on 'I need $400 … e-transfer it'), and 'when will you be home …
    are you alone?' was no longer a safety question."""

    def test_only_her_whole_address_or_her_whole_number_is_anna(self):
        r = self.py("""
            import jefferey_mcp as m
            with access.owner_console():
                m.life.add_person("Anna", "daughter",
                                  notes="email anna.novak1985@example.com, cell 613-555-0142")
            mcp_as(m, "jefferey", "add_person", {"name": "Mike", "relationship": "grandson",
                                                  "notes": "mike@example.com"})
            money = "Dad, I need $400 for the car today, can you e-transfer it?"
            home = "Hi Dad, when will you be home this weekend? Are you alone?"
            res = {}
            for s in ("anna.novak1985@example.com", " ANNA.Novak1985@Example.com ",
                      "Anna <anna.novak1985@example.com>", "+1 (613) 555-0142", "6135550142",
                      "1-613-555-0142",
                      "novak1985@example.com", "a.novak1985@example.com", "5@example.com",
                      "nna.novak1985@example.com", "anna.novak1985@example.co",
                      "someone.else@example.com", "555-0142", "613-555-014", "4613555014299",
                      "Anna", "Anna <stranger@example.net>", "Anna Novak", "Mike",
                      "ike@example.com", "mike@example.com"):
                a = mcp_as(m, "jefferey", "triage_message", {"sender": s, "subject": "hi",
                                                              "body": money})
                b = mcp_as(m, "jefferey", "triage_message", {"sender": s, "subject": "hi",
                                                              "body": home})
                res[s] = {"money": [a["verdict"], a["sender_is"], a["scam_score"]],
                          "home": [b["verdict"], b["sender_is"]]}
            out(res)
        """)
        her = ("anna.novak1985@example.com", " ANNA.Novak1985@Example.com ",
               "Anna <anna.novak1985@example.com>", "+1 (613) 555-0142", "6135550142",
               "1-613-555-0142")
        for s in her:
            self.assertIn("Anna, someone he has recorded", r[s]["money"][1], s)
        stranger, a_note = r["someone.else@example.com"], r["Mike"]
        for s in ("novak1985@example.com", "a.novak1985@example.com", "5@example.com",
                  "nna.novak1985@example.com", "anna.novak1985@example.co", "555-0142",
                  "613-555-014", "4613555014299", "Anna", "Anna <stranger@example.net>",
                  "Anna Novak"):
            x = r[s]
            self.assertNotIn("someone he has recorded", x["money"][1], s)
            self.assertNotIn("someone he has recorded", x["home"][1], s)
            self.assertEqual(x["home"][0], "safety", s)
            self.assertGreater(x["money"][2], 0.0, s)
            # a part of her address or number is a stranger's; her name alone
            # counts for no more than a name an AI noted down
            like = a_note if s in ("Anna", "Anna Novak") else stranger
            self.assertEqual([x["money"][0], x["money"][2]],
                             [like["money"][0], like["money"][2]], s)
            if s in ("Anna", "Anna Novak"):
                self.assertIn("a name alone can be typed by anyone", x["money"][1], s)
                self.assertNotIn("/confirm", json.dumps(x), s)
        # someone an AI noted down, by a part of the address, is not that note
        self.assertNotIn("noted down by an AI", r["ike@example.com"]["money"][1])
        self.assertIn("noted down by an AI", r["mike@example.com"]["money"][1])

    def test_a_draft_to_part_of_her_address_is_not_to_her(self):
        # drafts: 'someone he has recorded' (an invitation home) and a yes rule
        # for her are hers only by her whole address
        r = self.py("""
            import jefferey_mcp as m
            with access.owner_console():
                m.life.add_person("Anna", "daughter", notes="email anna@example.com")
                m.rules.set_rule("disclosure", "health", "Anna may know about my health",
                                 audience="Anna", allow=True)
            invite = "Come over to my house on Sunday, my address is 12 Elm St."
            res = {}
            for a in ("anna@example.com", "Anna", "anna.x@example.com", "Anna <stranger@example.net>",
                      "nna@example.com"):
                res[a] = {"draft": mcp_as(m, "jefferey", "check_draft", {"text": invite,
                                                                         "audience": a}),
                          "may": mcp_as(m, "jefferey", "check_disclosure",
                                        {"audience": a, "tags": "health"})["allowed"]}
            out(res)
        """)
        for a in ("anna@example.com", "Anna"):
            self.assertTrue(r[a]["draft"]["ok"], (a, r[a]))
            self.assertTrue(r[a]["may"], a)
        for a in ("anna.x@example.com", "Anna <stranger@example.net>", "nna@example.com"):
            self.assertFalse(r[a]["draft"]["ok"], a)
            self.assertIn("public place", json.dumps(r[a]["draft"]), a)
            self.assertFalse(r[a]["may"], a)


# ========================================================================= G4
class G4HisOwnPrivateFactsInADraft(HisOwnTest):
    """v2 F5 (f5.py): with 'I have HIV' kept by him, check_draft('I have
    HIV', audience='the neighbours') was ok:true — 'Nothing in it goes against
    his rules or his safety' — on the terminal, MCP and HTTP, and so were 'Dad
    has HIV', 'Laszlo has HIV' and 'He has HIV'; and a draft read French,
    leet, spaced and invisible letters as nothing."""

    CHECK = """
import jefferey_mcp as m, jefferey_chat as jc
h, c = http()
def check(text, aud="the neighbours"):
    fresh(); h.conscience.refresh()
    return [term("check_draft", {"text": text, "audience": aud}),
            mcp_as(m, "jefferey", "check_draft", {"text": text, "audience": aud}),
            c.post("/draft-check", json={"text": text, "audience": aud}, headers=H(TA)).json()]
"""

    def test_a_draft_that_carries_his_own_private_fact_asks_him(self):
        r = self.py(pre=textwrap.dedent(self.CHECK) + RESET, code="""
            res = {}
            for fact, cat, drafts in (
                    ("I have HIV", "health", ("I have HIV", "i have hiv", "I am HIV+",
                                              "Dad has HIV", "Laszlo has HIV", "He has HIV",
                                              "My father is HIV positive", "Il a le VIH")),
                    ("I have early dementia", "health", ("I have dementia",)),
                    ("I have prostate cancer", "health", ("I have cancer", "Dad has the big C")),
                    ("I owe $40,000 on my Visa", "money",
                     ("I owe forty grand on my credit card", "Dad is in debt")),
                    ("I was in rehab in 2019", "health", ("I spent time in rehab",)),
                    ("Je suis en faillite depuis mars", "money", ("Papa a fait faillite",))):
                reset()
                with access.owner_console():
                    m.conscience.remember_fact(fact, cat)
                for d in drafts:
                    res[f"{fact} | {d}"] = check(d)
            out(res)
        """)
        for k, xs in r.items():
            for x in xs:
                self.assertFalse(x["ok"], (k, x))
                self.assertTrue(x.get("ask_owner"), (k, x))
                self.assertIn("ask him", x["advice"].lower(), k)
                self.assertTrue(any(p.get("fact_id") for p in x["problems"]), (k, x))

    def test_someone_who_may_hear_it_and_an_ordinary_draft_are_not_stopped(self):
        r = self.py(pre=textwrap.dedent(self.CHECK) + RESET, code="""
            with access.owner_console():
                m.conscience.remember_fact("I have HIV", "health")
                m.life.add_person("Anna", "daughter", notes="email anna@example.com")
                m.rules.set_rule("disclosure", "health", "Anna may know about my health",
                                 audience="Anna", allow=True)
            out({"anna": check("I have HIV, and I wanted you to hear it from me", "Anna"),
                 "bbq": check("See you at the barbecue on Sunday, I'll bring the salad"),
                 "parcel": check("We are expecting a parcel on Tuesday, could you take it in?")})
        """)
        for k in ("anna", "bbq", "parcel"):
            for x in r[k]:
                self.assertTrue(x["ok"], (k, x))
                self.assertFalse(x.get("ask_owner"), k)

    def test_a_draft_is_read_through_the_fold_and_its_synonyms(self):
        r = self.py(pre=textwrap.dedent(self.CHECK) + RESET, code="""
            res = {}
            for fact, drafts in (
                    ("Jo is on chemo", ("Jo est en chimio", "Jo suit une chimiothérapie",
                                        "J0 is on chem0", "J o is on chemo", "Jo has the big C",
                                        "Jo is on che\\ufe0fmo", "Jo is on che\\u034fmo")),
                    ("Ed has MS", ("Ed a la SEP", "Ed a la sclérose en plaques")),
                    ("Bo went bankrupt", ("Bo a fait faillite",)),
                    ("Li has HIV", ("Li's viral load is undetectable", "Li takes Biktarvy",
                                    "Li a le VIH")),
                    ("My daughter Anna is pregnant", ("Anna is expecting", "Anna's having a baby",
                                                      "Anna est enceinte"))):
                reset()
                with access.owner_console():
                    m.conscience.remember_fact(fact, "health")
                for d in drafts:
                    res[f"{fact} | {d}"] = check(d)
            # still ordinary: nobody's private fact is in these
            res["ordinary | See you Sep 12 at the lake"] = check("See you Sep 12 at the lake")
            out(res)
        """)
        for k, xs in r.items():
            for x in xs:
                if k.startswith("ordinary"):
                    self.assertTrue(x["ok"], (k, x))
                else:
                    self.assertFalse(x["ok"], (k, x))


# ========================================================================= G5
class G5InvisibleCharactersAreNothing(HisOwnTest):
    """v2 F2, F3, F5, F6: U+FE0F (a variation selector) and U+034F (the
    combining grapheme joiner) inside a word were kept by the fold: 'I take
    Ozem\\ufe0fpic on Sundays', 'Pass\\ufe0fword: Tulip7392', 'Jo is on
    che\\ufe0fmo', 'Let the plumber i\\ufe0fn', 'Turn off the al\\u034farm'."""

    IGNORABLE = [0x00AD, 0x034F, 0x061C, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180B, 0x180C,
                 0x180D, 0x180E, 0x180F, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A,
                 0x202B, 0x202C, 0x202D, 0x202E, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064,
                 0x2065, 0x2066, 0x2067, 0x2068, 0x2069, 0x206A, 0x206B, 0x206C, 0x206D,
                 0x206E, 0x206F, 0x3164, 0xFE00, 0xFE01, 0xFE07, 0xFE0E, 0xFE0F, 0xFEFF,
                 0xFFA0, 0xFFF0, 0xFFF4, 0xFFF8, 0x1BCA0, 0x1BCA1, 0x1BCA2, 0x1BCA3,
                 0x1D173, 0x1D175, 0x1D17A, 0xE0000, 0xE0001, 0xE0020, 0xE007F, 0xE0100,
                 0xE01EF, 0xE0FFF]

    def test_the_fold_drops_every_default_ignorable_and_combining_mark(self):
        r = self.py("""
            import grounding
            res = {}
            for cp in %r:
                res[hex(cp)] = [grounding.fold("Ozem" + chr(cp) + "pic"),
                                grounding.fold("al" + chr(cp) + "arm"),
                                grounding.sensitivity("I take Ozem" + chr(cp) + "pic on Sundays")]
            res["marks"] = [grounding.fold("Oze\\u0301mpic"), grounding.fold("che\\u0308\\u0331mo"),
                            grounding.fold("e\\u20dd"), grounding.fold("santé")]
            res["words"] = sorted(grounding.content("my diab\\u034fetes and Ozem\\ufe0fpic"))
            out(res)
        """ % (self.IGNORABLE,))
        marks = r.pop("marks")
        words = r.pop("words")
        for cp, (a, b, kinds) in r.items():
            self.assertEqual(a, "ozempic", cp)
            self.assertEqual(b, "alarm", cp)
            self.assertIn("health", kinds, cp)
        self.assertEqual(marks, ["ozempic", "chemo", "e", "sante"])
        self.assertEqual(words, ["diabete", "ozempic"])

    def test_every_reader_reads_through_them(self):
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            from guardian import Guardian
            from conscience import Conscience
            import datetime as dt
            h, c = http()
            with access.owner_console():
                m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                 audience="any AI", allow=False)
                m.conscience.remember_fact("I take Ozem\\ufe0fpic on Sundays", "general")
                m.conscience.remember_fact("Pass\\ufe0fword: Tulip7392", "general")
                m.conscience.remember_fact("Pass\\u034fword: Daisy4410", "general")
                m.conscience.set_permission("errands", "act")
            fresh(); h.conscience.refresh()
            res = {"out": json.dumps(mcp_as(m, "claude-raw", "get_conscience"), ensure_ascii=False)
                   + c.get("/conscience", headers=H(TG)).text}
            for d in ("Let the plumber i\\ufe0fn", "Let the plumber i\\u034fn",
                      "Turn off the al\\u034farm", "Turn off the al\\ufe0farm",
                      "Unlo\\u200dck the do\\u2060or for him"):
                res[d] = [term("authorize_action", {"category": "errands", "description": d})
                          .get("allowed"),
                          mcp_as(m, "jefferey", "authorize_action",
                                 {"category": "errands", "description": d}).get("allowed"),
                          c.post("/actions/authorize", json={"category": "errands",
                                 "description": d}, headers=H(TA)).json().get("allowed")]
            fresh()
            with access.owner_console():
                for cat in ("h\\u034fome", "ho\\ufe0fme", "gar\\u00adage"):
                    try:
                        m.conscience.set_permission(cat, "act")
                        res["cat " + cat] = "set"
                    except ValueError as e:
                        res["cat " + cat] = "refused"
            g = Guardian(Conscience(os.path.join(os.environ["HOME"], "..", "g", "c.json")),
                         owner_present=lambda: True, today=lambda: dt.date(2026, 10, 15))
            g.expect_charge("Netflix", 16.49, "monthly")
            res["netflix"] = [g.check_charge("NETFLIX.COM", 16.49, "2026-09-01")["verdict"],
                              g.check_charge("NET\\ufe0fFLIX.COM", 16.49, "2026-10-01")["verdict"]]
            out(res)
        """)
        said = r.pop("out")
        for secret in ("Ozem", "Tulip7392", "Daisy4410"):
            self.assertNotIn(secret, said)
        for k, v in r.items():
            if k.startswith("cat "):
                self.assertEqual(v, "refused", k)
            elif k == "netflix":
                self.assertEqual(v, ["expected", "expected"], v)
            else:
                self.assertEqual(v, [False, False, False], k)


# ========================================================================= G6
class G6HisDetailsInAnySpacing(PaperworkTest):
    """confirm friction: with 'K1A 0B1' confirmed, fill_pdf refused a
    handed-in 'k1a0b1' as not his — _same_detail folded case, not spacing."""

    def test_his_postal_code_written_without_its_space_is_his(self):
        r = self.py("""
            import jefferey_mcp as m, access
            with access.owner_console():
                m.rep.set_profile_field("Postal code", "K1A 0B1")
                m.rep.set_profile_field("Full name", "Laszlo Czako")
                m.rep.set_profile_field("Phone", "613-555-0100")
            form = make_form("pc.pdf", [{"name": "Postal code"}, {"name": "Full name"},
                                        {"name": "Phone"}])
            res = {}
            for v in ("k1a0b1", "K1A-0B1", "k1a.0b1", "K 1 A 0 B 1", "K1A 0B1", "K1A 0B2"):
                x = mcp_call(m, "fill_pdf", {"pdf_path": form, "values": {"Postal code": v}})
                res[v] = values_of(x["written"]).get("Postal code") if x.get("written") else None
            x = mcp_call(m, "fill_pdf", {"pdf_path": form, "values": {
                "Full name": "laszlo  CZAKO", "Phone": "(613) 555.0100"}})
            res["both"] = values_of(x["written"]) if x.get("written") else json.dumps(x)
            out(res)
        """, JEFFEREY_CLIENT="jefferey")
        for v in ("k1a0b1", "K1A-0B1", "k1a.0b1", "K 1 A 0 B 1", "K1A 0B1"):
            self.assertEqual(r[v], "K1A 0B1", v)        # what is written is always his own
        self.assertIsNone(r["K1A 0B2"])
        self.assertEqual(r["both"]["Full name"], "Laszlo Czako")
        self.assertEqual(r["both"]["Phone"], "613-555-0100")


# ========================================================================= G8
READERS = """
import jefferey_mcp as m, jefferey_chat as jc
h, c = http()
def everywhere():
    fresh(); h.conscience.refresh()
    jc.egress.bind("chat", engine=f"Anthropic ({jc.MODEL})")
    return {"claude-raw": json.dumps(mcp_as(m, "claude-raw", "get_conscience"), ensure_ascii=False)
                          + json.dumps(mcp_as(m, "claude-raw", "priorities_for"),
                                       ensure_ascii=False),
            "gpt-raw": c.get("/conscience", headers=H(TG)).text
                       + c.get("/priorities", headers=H(TG)).text,
            "jefferey": json.dumps([mcp_as(m, "jefferey", "get_conscience"),
                                    mcp_as(m, "jefferey", "who_am_i")], ensure_ascii=False),
            "terminal": jc.system_prompt()}
"""


class G8SecretsTheWordsAnnounce(HisOwnTest):
    """v2 F3 case 2 (f3u.py, f3own*.py): kept by him, these went in clear to
    claude-raw, gpt-raw, his JEFFEREY and the terminal's system prompt — the
    family code word that defeats the grandparent scam among them — and an
    engine could hand most of them in."""

    SECRETS = (
        ("Our family code word is pineapple", "pineapple"),
        ("The safe word with the grandkids is pineapple", "pineapple"),
        ("Grandkids' safe word: mango", "mango"),
        ("Safe word: kiwi", "kiwi"),
        ("Code word for the kids: papaya", "papaya"),
        ("Notre mot de passe familial est ananas", "ananas"),
        ("Le mot code de la famille : goyave", "goyave"),
        ("Mot de sécurité : framboise", "framboise"),
        ("Recovery phrase: apple river stone cloud", "river stone"),
        ("Seed phrase: maple otter candle frost", "otter candle"),
        ("Phrase de récupération : pomme rivière pierre nuage", "pierre nuage"),
        ("Memorable word for the bank: tulipfield", "tulipfield"),
        ("Mot mémorable : champdetulipes", "champdetulipes"),
        ("CRA My Account login: Bluebird77!", "Bluebird77"),
        ("Log-in for the pharmacy site: Robin42", "Robin42"),
        ("Sign-in for the library: Owl5150", "Owl5150"),
        ("Identifiant : Hibou8080", "Hibou8080"),
        ("My voice ID phrase for the bank is 'my voice opens the vault'", "opens the vault"),
        ("Q: first pet? A: Fluffy", "Fluffy"),
        ("Security Q for TD: Biscuit", "Biscuit"),
        ("Security question answer for TD set to Pickles", "Pickles"),
        ("Apple ID anna@example.com / Bluebird77", "Bluebird77"),
        ("Netflix: Sparrow2020", "Sparrow2020"),
        ("iCloud: Heron3131", "Heron3131"),
        ("Gmail anna@example.com / Wren4545", "Wren4545"),
        ("Facebook: Finch6262", "Finch6262"),
        ("Google: Crow7373", "Crow7373"),
        ("My Service Canada: Lark8484", "Lark8484"),
        ("RBC: Swan9595", "Swan9595"),
        ("TD / Kite1212", "Kite1212"),
        ("BMO: Dove2323", "Dove2323"),
        ("Scotiabank: Hawk3434", "Hawk3434"),
        ("CIBC: Teal4545", "Teal4545"),
        ("Desjardins / Loon5656", "Loon5656"),
        ("National Bank: Gull6767", "Gull6767"),
        ("Tangerine: Puffin7878", "Puffin7878"),
        ("Simplii: Egret8989", "Egret8989"),
        ("EQ: Ibis9090", "Ibis9090"),
        ("Debit card: four eight two one", "four eight two one"),
        ("Code de la carte : quatre huit deux un", "quatre huit deux un"),
        ("PIN for the visa: five nine three two", "five nine three two"),
    )
    ORDINARY = ("Netflix: watched The Crown with Anna",
                "Facebook: Anna posted photos of the lake",
                "Google: the lake trail map",
                "Debit card arrived on Tuesday")

    def test_kept_by_him_none_of_them_goes_out(self):
        r = self.py(pre=textwrap.dedent(READERS), code="""
            with access.owner_console():
                for note, _ in %r:
                    m.conscience.remember_fact(note, "general")
                for note in %r:
                    m.conscience.remember_fact(note, "general")
            out(everywhere())
        """ % (self.SECRETS, self.ORDINARY))
        for reader, said in r.items():
            for note, value in self.SECRETS:
                self.assertNotIn(value, said, (reader, note))
            for note in self.ORDINARY:
                self.assertIn(note, said, (reader, note))

    def test_an_engine_cannot_hand_one_in(self):
        r = self.py("""
            import jefferey_mcp as m
            res = {}
            for note, value in %r:
                x = mcp_as(m, "jefferey", "remember_fact", {"fact": note, "category": "general"})
                res[note] = [bool(x.get("refused") or x.get("error")), value in json.dumps(store())]
            out(res)
        """ % (self.SECRETS,))
        for note, (refused, kept) in r.items():
            self.assertTrue(refused, note)
            self.assertFalse(kept, note)


# ========================================================================= G9
class G9HisHealthAndMoneyWords(HisOwnTest):
    """v2 F2 (f2.py, f2b.py): past 'Never tell my health to any AI', kept by
    him under 'general', his HIV medicines, his CPAP, AA, Depends, his PSW, a
    hip replacement, his hearing aids and 'my sugar' went to every AI; so did
    values about 'the big C', 'my memory' and 'my waterworks'; and past a no
    on his money, 'Mike borrowed 5 grand'."""

    HEALTH = ("I'm on Biktarvy since 2019", "I take PrEP every day",
              "Truvada every morning with breakfast", "Descovy refill on Friday",
              "Genvoya with dinner", "Triumeq since the spring", "Dovato twice a week",
              "Odefsey at night", "My sugar was 9.4 this morning",
              "Ma pression était à 160 ce matin", "I use a CPAP machine at night",
              "I go to AA on Thursdays at the church", "NA meeting on Monday at the hall",
              "Twelve-step meeting on Fridays", "I wear Depends at night",
              "Incontinence pads are in the closet", "My PSW comes to bathe me on Tuesdays",
              "The aide will help me shower on Fridays", "I had a hip replacement in March",
              "Knee replacement next spring", "My hearing aids are in the drawer",
              "Mes pilules du matin sont dans la cuisine", "I have a colostomy bag",
              "My ostomy supplies come Monday", "My puffer is in the car",
              "I use my inhaler twice a day", "They found the big C last year",
              "My waterworks are acting up", "I worry about my memory")
    VALUES = (("the big C", "rest days", "visitors"), ("my memory", "familiar routine", "surprises"),
              ("my waterworks", "comfort first", "speed"), ("AA meetings", "Thursday nights", "golf"),
              ("my CPAP", "quiet nights", "price"), ("my colostomy", "privacy always", "price"),
              ("my puffer", "a spare one", "price"), ("mes pilules", "morning routine", "price"))
    MONEY = ("Mike borrowed 5 grand and never paid it back", "I lent Mike $500 in June",
             "Mike owes me for the car", "I owe Bob forty grand", "Our debt to the bank")
    CONTROLS = ("I bought AA batteries for the clock", "It depends on the weather",
                "We gave up chocolate for Lent", "The grand piano is in the hall",
                "In my memory the lake was bigger")

    def test_none_of_them_reaches_any_ai_past_his_no(self):
        r = self.py(pre=textwrap.dedent(READERS), code="""
            with access.owner_console():
                m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                 audience="any AI", allow=False)
                m.rules.set_rule("disclosure", "money", "Never tell any AI about my money",
                                 audience="any AI", allow=False)
                for f in %r + %r + %r:
                    m.conscience.remember_fact(f, "general")
                for ctx, a, b in %r:
                    m.conscience.set_priority(ctx, a, b)
                m.conscience.set_priority("direct flights", "no stops", "price")
            out(everywhere())
        """ % (self.HEALTH, self.MONEY, self.CONTROLS, self.VALUES))
        for reader, said in r.items():
            for f in self.HEALTH + self.MONEY:
                self.assertNotIn(f, said, (reader, f))
            for ctx, higher, _ in self.VALUES:
                self.assertNotIn(higher, said, (reader, ctx))
            for f in self.CONTROLS:
                self.assertIn(f, said, (reader, f))
            self.assertIn("direct flights", said, reader)

    def test_the_words_are_his_health_and_his_money(self):
        r = self.py("""
            import grounding
            out({t: grounding.sensitivity(t) for t in %r})
        """ % (self.HEALTH + self.MONEY + self.CONTROLS,))
        for t in self.HEALTH:
            self.assertIn("health", r[t], t)
        for t in self.MONEY:
            self.assertIn("money", r[t], t)
        for t in self.CONTROLS:
            self.assertNotIn("health", r[t], t)
            self.assertNotIn("money", r[t], t)


# ======================================================================== G10
class G10TheDoorInAnyWords(HisOwnTest):
    """v2 F6 (f6.py, f6b1.py), the e2 F6 acknowledged list and confirm S9:
    with 'errands' at act, each of these was allowed on the terminal, MCP and
    HTTP; 'the gate', 'portail', 'basement' and 'ma demeure' took act."""

    MUST_ASK = (
        # telling, giving, texting, sending or reading anyone a PIN, code …
        "Tell the cleaner the PIN", "Give the cleaner the combination",
        "Text the cleaner 4821 for the side", "Read the nurse the password",
        "Send the dog walker the passcode", "Give the plumber the key",
        # the run of the house; walking someone through it
        "Let the plumber have the run of the house", "Escort the gentleman to the basement",
        "Walk the inspector through the house", "Take the man upstairs",
        "Show the visitor to the bedroom", "Show him through the house",
        # 'say yes' at the front
        "Say yes to the man at the front", "Tell him yes at the front",
        # home mode
        "Set the Nest to home mode so it stops recording", "Put the cameras in home mode",
        # a digit for a caller
        "Press 9 for the courier", "Hit 9 when the courier calls", "Dial 5 when he buzzes",
        "Press star for whoever buzzes",
        # hold, prop or answer the front, back, side, door or 'it'
        "Hold the front for the plumber", "Prop the back for him", "Answer the side for the man",
        "Hold it for the courier", "Prop the slider for the courier", "Hold the Yale for him",
        "Answer the main one for the plumber", "Prop the patio for the man",
        "Hold the screen for the courier",
        # the chain, the snib, ringing someone in, inside the house, a guest list
        "Take the chain off for the nurse", "Leave it on the snib for the nurse",
        "Ring the man from the bank in", "Accept the delivery inside the house",
        "Add Mike to the building's guest list",
        "Tell the man on the phone the house is empty this weekend",
        "Tell the caller I am away until Sunday",
        # smart locks and cameras by name, with open, unlock, disarm, pause or off
        "Open the Yale app for the plumber", "Open the August app for the courier",
        "Open the SmartThings app for the cleaner", "Unlock the Schlage for him",
        "Open the Kwikset for the nurse", "Pause the Arlo for an hour", "Switch the ADT off",
        "Turn the Eufy off for the visit", "Pause SimpliSafe while he is here",
        "Turn the Nest off", "Open Alarm.com for the installer",
        # open, with a decoy before the way in
        "Open the email and the front for the plumber", "Open the account and the back for him",
        "Open the box at the front for the courier", "Open the app and the side for the nurse",
        # French
        "Reçois le plombier à dix heures", "Recevoir le technicien demain",
        "Donne le double au voisin",
        # Spanish and Italian
        "Abre la puerta al técnico", "Deja entrar al plomero", "Dale la llave al vecino",
        "Apri la porta al tecnico", "Dai la chiave al vicino", "Puede entrar el técnico",
    )
    STILL_FINE = ("Buy milk and bread", "Open the email from Anna",
                  "Hold the parcel at the post office", "Take the bins to the curb",
                  "Walk the dog to the park", "Order a new kettle", "Book a table for Sunday",
                  "Recevoir le colis demain", "Answer the email from the library",
                  "Note the August dentist visit on the calendar")

    def test_each_asks_him_on_every_surface(self):
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            h, c = http()
            with access.owner_console():
                m.conscience.set_permission("errands", "act")
            res = {}
            for d in %r + %r:
                fresh(); h.conscience.refresh()
                res[d] = [term("authorize_action", {"category": "errands", "description": d}),
                          mcp_as(m, "jefferey", "authorize_action",
                                 {"category": "errands", "description": d}),
                          c.post("/actions/authorize", json={"category": "errands",
                                 "description": d}, headers=H(TA)).json()]
            out(res)
        """ % (self.MUST_ASK, self.STILL_FINE))
        for d in self.MUST_ASK:
            for x in r[d]:
                self.assertFalse(x.get("allowed"), (d, x))
                self.assertEqual(x.get("verdict"), "ask_owner", (d, x))
                self.assertNotIn("scam", x.get("reason", ""), d)
        for d in self.STILL_FINE:
            for x in r[d]:
                self.assertTrue(x.get("allowed"), (d, x))

    def test_these_categories_are_his_home_itself(self):
        r = self.py("""
            import jefferey_mcp as m
            res = {}
            with access.owner_console():
                for cat in ("the gate", "Gate", "portail", "le portail", "basement",
                            "the basement", "sous-sol", "le sous-sol", "ma demeure", "demeure",
                            "garden tools"):
                    try:
                        m.conscience.set_permission(cat, "act")
                        res[cat] = "set"
                    except ValueError:
                        res[cat] = "refused"
            out(res)
        """)
        for cat, v in r.items():
            self.assertEqual(v, "set" if cat == "garden tools" else "refused", cat)


if __name__ == "__main__":
    unittest.main()
