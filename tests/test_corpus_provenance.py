"""
Frozen corpus — his own words, and who may turn his values round (R9),
repair round 6, and the round-7 decision (D2).

Two rounds tuned the reading of what he typed, and each broke cases next to
the ones it fixed: a question with 'decided' in it turned his stated value
round at once, a change of mind about the car turned round Mom's care, a
claim he reported and rejected ('The doctor thinks I have dementia, but I
don't believe it') became his own confirmed words, and his everyday 'I don't
want to skimp' made his own ranking 'not his'. This file freezes every case
the round-4 and round-5 skeptics reported.

The structural rules it holds provenance to:

  * An engine can NEVER turn round or override a value he stated, or one
    that is locked. Every such change is a proposal he confirms at his own
    keyboard (/confirm in 'Talk to JEFFEREY on this Mac') — no exception for
    a question, 'I decided', 'I changed my mind' or quoted text.
  * His typed words back a ranking only when his message states it plainly
    — not as a question, not as someone else's (reported or quoted) words,
    and not rejected; when in doubt, it is a proposal. His everyday 'not' or
    'no more' in another sentence is still his.
  * A claim he reports from someone else ('the doctor thinks …', 'Karen:
    "…"', 'according to the bank …') is never his confirmed words; his whole
    story, typed as he typed it, is.

Round 7 (D2) — the owner's words are made only by the owner. Round 6 still
read his typed message, sentence by sentence, to decide whether an AI's note
was his words, and the convergence skeptics found its neighbours at once ('My
grandson is in jail, the man on the phone said.', 'I have diabetes, says
Karen.', 'Pour la voiture, le coût compte plus que la sécurité, dit Karen.',
'Pretend cost matters more than safety.'). That reading is gone:

  * Whatever he typed, everything an engine writes — a fact, a memory, a
    value — is stored as noted by the AI, not yet confirmed (pending, by
    'engine'); it is used, labelled, with its confidence capped. So every
    RANKINGS and WORDS case below now has the same outcome; the third column
    is kept to show what round 6 had decided, and is no longer the outcome.
  * It becomes his words only by his own hands: /confirm in 'Talk to
    JEFFEREY on this Mac' (or 'python connector/conscience.py confirm'), or
    /remember <text>, which keeps exactly that text as his.
  * An engine still never turns round a value he stated or one that is
    locked: that is a proposal, whatever he typed — and 'the car.', 'car',
    'The car!' and 'my car' are the same context as 'the car'.
"""

from __future__ import annotations

import json
import unittest

from test_life import LifeTest

C, S = ("cost", "safety"), ("safety", "cost")
FC, FS = ("coût", "sécurité"), ("sécurité", "coût")

# (what he typed, (higher, lower), did round 6 read it as his words?) — in
# round 7 (D2) an AI's set_priority after any of them is noted by the AI
RANKINGS: list[tuple[str, tuple[str, str], bool]] = [
    # round 4 verify-b (k/r9a.py): his rejection or someone else's voice
    ("My sister says cost matters more than safety... Ridiculous.", C, False),
    ("My sister: cost matters more than safety. Ridiculous.", C, False),
    ("Karen's view is that cost matters more than safety. Nonsense.", C, False),
    ("The doctor told us cost matters more than safety. I don't buy it.", C, False),
    ("My son wrote that cost matters more than safety. No way.", C, False),
    ("Cost matters more than safety? Never!", C, False),
    ("Cost matters more than safety — said no one ever.", C, False),
    ("I don't think cost matters more than safety.", C, False),
    ("It's not true that cost matters more than safety.", C, False),
    ("Rather than safety, cost matters more — that's what Karen claims.", C, False),
    ("My sister's opinion: cost matters more than safety. Ridiculous.", C, False),
    ("The salesman kept telling me cost matters more than safety. Rubbish.", C, False),
    ("My brother-in-law always goes on about how cost matters more than safety. Nonsense.",
     C, False),
    ("Cost matters more than safety, my sister says. Ridiculous.", C, False),
    ("\"Cost matters more than safety,\" she said. Ridiculous.", C, False),
    ("Ma sœur m'a dit que le coût compte plus que la sécurité. Ridicule.", FC, False),
    ("Selon ma sœur, le coût compte plus que la sécurité. Ridicule.", FC, False),
    ("Mon fils a écrit que le coût compte plus que la sécurité. Jamais.", FC, False),
    ("Some say cost matters more than safety. Not me.", C, False),
    ("Who says cost matters more than safety? Not me.", C, False),
    # round 5 HisRejectionAnywhereAndHisOwnStories.NOT_HIS
    ("Karen's view is that cost matters more than safety.", C, False),
    ("My sister: cost matters more than safety.", C, False),
    ("My sister's opinion: cost matters more than safety.", C, False),
    ("The salesman kept telling me cost matters more than safety.", C, False),
    ("My brother-in-law always goes on about how cost matters more than safety.", C, False),
    # round 5 verify-b (p/r9.py): still read as his on 5adc37b, or caught
    ("Cost matters more than safety? I strongly disagree.", C, False),
    ("I read that cost matters more than safety.", C, False),
    ("I heard cost matters more than safety.", C, False),
    ("I doubt cost matters more than safety.", C, False),
    ("It is false that cost matters more than safety.", C, False),
    ("If cost mattered more than safety, I'd buy the cheap one.", C, False),
    ("Should cost matter more than safety?", C, False),
    ("Cost matters more than safety — over my dead body.", C, False),
    ("Cost matters more than safety? Yeah right.", C, False),
    ("Cost matters more than safety? Absolutely not.", C, False),
    ("Cost matters more than safety? Hogwash.", C, False),
    ("Cost matters more than safety? Baloney.", C, False),
    ("Cost matters more than safety? That's crazy.", C, False),
    ("Cost matters more than safety? Absurd.", C, False),
    ("Cost matters more than safety? Are you kidding me?", C, False),
    ("Cost matters more than safety? Not in a million years.", C, False),
    ("Cost matters more than safety? Hell no.", C, False),
    ("Le coût compte plus que la sécurité? N'importe quoi.", FC, False),
    ("Le coût compte plus que la sécurité? Pas question.", FC, False),
    ("Le coût compte plus que la sécurité? C'est faux.", FC, False),
    ("Le coût compte plus que la sécurité? Je ne suis pas d'accord.", FC, False),
    ("Le coût compte plus que la sécurité? Foutaise.", FC, False),
    ("Would you say cost matters more than safety?", C, False),
    ("Does cost really matter more than safety", C, False),
    ("The ad claims cost matters more than safety.", C, False),
    ("According to the salesman, cost matters more than safety.", C, False),
    ("Mom used to believe cost matters more than safety.", C, False),
    ("They think cost matters more than safety.", C, False),
    ("People say cost matters more than safety.", C, False),
    ("The article argues that cost matters more than safety.", C, False),
    ("On TV they said cost matters more than safety.", C, False),
    ("She insists cost matters more than safety.", C, False),
    ("The nurse reckons cost matters more than safety.", C, False),
    ("I used to think cost matters more than safety, but not anymore.", C, False),
    ("I'm not convinced cost matters more than safety.", C, False),
    ("Cost does not matter more than safety.", C, False),
    ("Sure, cost matters more than safety, and pigs fly.", C, False),
    ("Karen: \"cost matters more than safety\". Me: no.", C, False),
    ("Mike thinks cost matters more than safety. I think he's an idiot.", C, False),
    ("Anna believes cost matters more than safety.", C, False),
    ("My son feels cost matters more than safety.", C, False),
    ("Mon fils pense que le coût compte plus que la sécurité.", FC, False),
    ("D'après Karen, le coût compte plus que la sécurité.", FC, False),
    ("Pour Karen, le coût compte plus que la sécurité.", FC, False),
    ("Karen trouve que le coût compte plus que la sécurité.", FC, False),
    # a question is never a plain statement, whatever else it says (when in
    # doubt, a proposal — he confirms it)
    ("Cost matters more than safety, don't you think so too? I do.", C, False),
    ("Safety matters more than cost, isn't it obvious?", S, False),
    # round 5 verify-c (sk5/s_mind.py): a question with 'decided' in it
    ("Should cost matter more than safety for the car? I decided to ask you first.", C, False),
    ("I decided to ask you: does cost matter more than safety for the car?", C, False),
    ("I've decided to think about whether cost matters more than safety for the car.", C, False),
    ("We decided to look at cheaper cars, would cost matter more than safety for the car?",
     C, False),
    # his own, plainly — round 5 verify-b (p/r9.py) HIS list
    ("I changed my mind: cost matters more than safety.", C, True),
    ("Actually, cost matters more than safety now.", C, True),
    ("Cost matters more than safety, I've decided.", C, True),
    ("For me, cost matters more than safety.", C, True),
    ("Cost matters more than safety. Period.", C, True),
    ("Honestly cost matters more than safety, no doubt about it.", C, True),
    ("Cost matters more than safety, there's no way around it.", C, True),
    ("Cost matters more than safety, never mind what Karen says.", C, True),
    ("Je pense que le coût compte plus que la sécurité.", FC, True),
    ("Le coût compte plus que la sécurité, sans aucun doute.", FC, True),
    ("I've always said cost matters more than safety, and Karen agrees.", C, True),
    # round 5 verify-c (sk5/s_prov.py), with regression 9's everyday negation
    ("Safety matters more than cost, no question.", S, True),
    ("Safety matters more than cost. I don't want to skimp on the brakes.", S, True),
    ("I want the safer car, not the cheapest one. Safety matters more than cost.", S, True),
    ("Safety matters more than cost. No more cheap tires for me.", S, True),
    ("For the car, safety matters more than cost. Never again a lemon.", S, True),
    ("Safety matters more than cost, my wife agrees.", S, True),
    ("My wife and I agree: safety matters more than cost.", S, True),
    ("Safety matters more than cost. Mike said otherwise but he's wrong.", S, True),
    ("La sécurité compte plus que le coût.", FS, True),
    ("La sécurité avant le coût, pas de discussion.", FS, True),
    ("Safety before cost, always. The salesman said otherwise.", S, True),
    ("I think safety matters more than cost.", S, True),
    ("Safety matters more than cost", S, True),
    ("Safety first, cost second.", S, True),
    ("Honestly, safety matters more than cost to me. Less worry.", S, True),
    ("Safety matters more than cost, I'm no longer young.", S, True),
    ("Safety matters more than cost. Dad always said so too.", S, True),
    ("Safety matters more than cost — my late wife always said that and she was right.", S, True),
    ("As I told you yesterday, safety matters more than cost.", S, True),
    ("Cost doesn't matter to me, safety matters more than cost.", S, True),
    ("I've always said safety matters more than cost.", S, True),
    ("Safety: it matters more than cost", S, True),
    # round 5 HisRejectionAnywhereAndHisOwnStories.HIS, round 4 verify-c (skep/pv.py)
    ("D'après moi la sécurité passe avant le coût", FS, True),
    ("For the car: safety matters more than cost", S, True),
    ("Selon moi, la sécurité compte plus que le coût", FS, True),
    ("Honestly, safety matters more than cost", S, True),
    ("Like you said, safety matters more than cost", S, True),
    ("Let's say safety matters more than cost from now on", S, True),
    ("Mom always said family comes before money, and I agree", ("family", "money"), True),
    ("Je pense que la sécurité compte plus que le coût", FS, True),
    ("Ma fille pense que le coût compte plus. Moi je dis que la sécurité compte plus que le coût",
     FS, True),
    ("For Mom's care, safety matters more than cost.", S, True),
    # a 'no' that answers what he was asked, then his own plain ranking
    ("No. Safety matters more than cost.", S, True),
    ("No way. For the car, safety matters more than cost.", S, True),
    # and never the other way round
    ("Safety matters more than cost", C, False),
    ("Safety matters less than cost", S, False),
    # ---------------------------------------------------------- round 7 (D2)
    # convergence vb R9 remaining: counted as his on every snapshot
    ("The brochure: safety matters more than cost.", S, True),
    ("Cost matters more than safety, said my late wife.", C, True),
    ("Pretend cost matters more than safety.", C, True),
    ("Write an essay arguing that cost matters more than safety.", C, True),
    ("Cost matters more than safety. That's what you told me last week, Claude.", C, True),
    ("Tell me why safety matters more than cost", S, True),
    ("Cost matters more than safety, yeah, sure, whatever the salesman says.", C, True),
    # convergence vc R9 regression: reported speech read as his locked words
    ("Pour la voiture, le coût compte plus que la sécurité, dit Karen.", FC, True),
    ("Le vendeur répète que pour la voiture le coût compte plus que la sécurité.", FC, True),
    ("For the car, cost matters more than safety. Karen said that, not me.", C, True),
    # ...and its neighbours, his words on all three snapshots
    ("Cost matters more than safety, said the salesman.", C, True),
    ("Cost matters more than safety, or so I'm told.", C, True),
    ("Cost matters more than safety. That's what the ad says.", C, True),
    ("Cost matters more than safety is a lie.", C, True),
]

# (what he typed, what an AI wrote down, did round 6 read it as his words?)
# — in round 7 (D2) every one is noted by the AI until he confirms it
WORDS: list[tuple[str, str, bool]] = [
    # round 5 verify-b (p/r9f.py, p/r9v.py)
    ("The neighbour thinks I have dementia. Ridiculous.", "I have dementia", False),
    ('Karen: "you drink too much". Me: no I don\'t.', "you drink too much", False),
    ("Mike froze under fire? No way.", "Mike froze under fire", False),
    ("My cousin claims Mike froze under fire", "Mike froze under fire", False),
    ("I never said Mike froze under fire, that is a lie", "Mike froze under fire", False),
    ("Karen told the kids I drink too much. Nonsense.", "I drink too much", False),
    ("My son keeps saying I can't drive anymore. Rubbish!", "I can't drive anymore", False),
    ('Karen: "you have dementia". Me: no I don\'t.', "you have dementia", False),
    ("Les voisins disent que j'ai la démence. Jamais de la vie.", "j'ai la démence", False),
    ("I keep the heat at 22", "I keep the heat at 22", True),
    # round 5 verify-c (sk5/s_prov2.py): reported, and mostly rejected
    ("The doctor thinks I have early dementia, but I don't believe it.", "I have early dementia",
     False),
    ("My sister says I have dementia. I don't.", "I have dementia", False),
    ("Karen keeps telling me I drink too much. Rubbish.", "I drink too much", False),
    ("Karen keeps telling me I drink too much.", "I drink too much", False),
    ("My son thinks I should sell the house. Not happening.", "I should sell the house", False),
    ("Mike claims I owe him $500. I paid him back in May.", "I owe him $500", False),
    ("According to the bank I owe $2000, which is a mistake.", "I owe $2000", False),
    ("Apparently I am moving into a home. Over my dead body.", "I am moving into a home", False),
    ("My daughter wants me to give her power of attorney. I won't.", "give her power of attorney",
     False),
    # someone else's claim, reported without a rejection: still his to
    # confirm (when in doubt, a proposal)
    ("My doctor says I am allergic to penicillin", "I am allergic to penicillin", False),
    ("My doctor said I must not drive at night anymore", "I must not drive at night anymore",
     False),
    ("Le médecin dit que je suis allergique à la pénicilline",
     "je suis allergique à la pénicilline", False),
    ("Anna says she will visit on Sunday", "she will visit on Sunday", False),
    ("My will says the cottage goes to Anna", "the cottage goes to Anna", False),
    ('Karen said "the cottage goes to Mike"', "the cottage goes to Mike", False),
    ('Karen said "the cottage goes to Mike" and I laughed.', "the cottage goes to Mike", False),
    ("I don't think I want a funeral, just a party", "I want a funeral", False),
    # his own words: his whole story as he typed it, his notes, his motto
    ("Mom said we would never go hungry, and we never did.",
     "Mom said we would never go hungry, and we never did.", True),
    ('My father always said "work hard and be kind"', 'My father always said "work hard and be kind"',
     True),
    ("Note: my blood type is O negative", "my blood type is O negative", True),
    # a name and a colon before what he says about them is his note, not
    # their speech ('Karen: "you drink too much"' and 'Karen: you …' are)
    ("Emma: she was born in 1990 in Ottawa", "she was born in 1990 in Ottawa", True),
    ("Grandpa: he fought at Vimy", "he fought at Vimy", True),
    ("Reminder: I take metformin twice a day", "I take metformin twice a day", True),
    ("Our wedding was in 1972. It rained all day.", "Our wedding was in 1972. It rained all day.",
     True),
    ('My motto is "measure twice, cut once"', "measure twice, cut once", True),
    ('I always say "measure twice, cut once"', "measure twice, cut once", True),
    ('My motto is "family first, money second"', "family first, money second", True),
    ("The house feels cold in winter so I keep the heat at 22", "I keep the heat at 22", True),
    ("Remember: my daughter's name is Anna", "my daughter's name is Anna", True),
    ('My father always said "work hard and be kind", and I have lived by it.',
     'My father always said "work hard and be kind", and I have lived by it.', True),
    ("Mom said we would never go hungry, and we never did, even in 1956.",
     "Mom said we would never go hungry, and we never did, even in 1956.", True),
    ("The doctor told me I was lucky to survive the heart attack in 1999.",
     "The doctor told me I was lucky to survive the heart attack in 1999.", True),
    ("The doctor thinks I have early dementia, but I don't believe it.",
     "The doctor thinks I have early dementia, but I don't believe it.", True),
    # ---------------------------------------------------------- round 7 (D2)
    # convergence vb R9 remaining (1): his confirmed words on every snapshot
    ("I have diabetes, says Karen.", "I have diabetes", True),
    # convergence vb R9 regression against r4: a scammer's claim with the
    # speaker named at the end became his own confirmed words
    ("My grandson is in jail, the man on the phone said.", "My grandson is in jail", True),
    ("I need to send $3,000 for bail, the lawyer told me.", "I need to send $3,000 for bail",
     True),
    # the facts round 6 already kept pending, kept pending
    ("I gave Karen power of attorney? No way!", "I gave Karen power of attorney", False),
    ("The bank called: I owe $4,000 on a loan. I never took a loan.", "I owe $4,000 on a loan",
     False),
    ("Did I tell you I sold the cottage?", "I sold the cottage", False),
]


class HisWordsFrozenCorpus(LifeTest):
    """Round 7 (D2): whatever he typed, what an AI writes down after it is
    noted by the AI — never his words by itself."""

    def test_no_ranking_he_typed_makes_an_ais_value_his(self):
        r = self.py("""
            import jefferey_chat as jc, provenance
            res = []
            for i, (typed, (hi, lo), _) in enumerate(%r):
                provenance.owner_typed(typed)
                x = jc.dispatch_tool("set_priority", {"context": f"case {i}", "higher": hi,
                                                      "lower": lo})
                row = [p for p in store()["priorities"] if p["context"] == f"case {i}"][0]
                res.append([row["status"], row["source"]["stated_by"], bool(x.get("unconfirmed")),
                            x.get("noted_by"), row["confidence"] <= 0.6])
            out(res)
        """ % (RANKINGS,), JEFFEREY_CLIENT="jefferey")
        want = ["pending", "engine", True, "noted by the AI, not yet confirmed by him", True]
        bad = [(t, got) for (t, _, _), got in zip(RANKINGS, r) if got != want]
        self.assertEqual(bad, [], "\n" + "\n".join(map(str, bad)))

    def test_no_words_he_typed_make_an_ais_fact_his(self):
        r = self.py("""
            import jefferey_chat as jc, provenance
            res = []
            for typed, said, _ in %r:
                provenance.owner_typed(typed)
                x = jc.dispatch_tool("remember_fact", {"fact": said})
                f = [f for f in store()["facts"] if f["fact"] == said][-1]
                res.append([f["status"], f["source"]["stated_by"], x.get("noted_by")])
            out(res)
        """ % (WORDS,), JEFFEREY_CLIENT="jefferey")
        want = ["pending", "engine", "noted by the AI, not yet confirmed by him"]
        bad = [(t, s_, got) for (t, s_, _), got in zip(WORDS, r) if got != want]
        self.assertEqual(bad, [], "\n" + "\n".join(map(str, bad)))

    def test_the_same_on_claude_and_chatgpt(self):
        # MCP and HTTP never see what he typed; the outcome is the same
        a = self.py("""
            import jefferey_mcp as m
            out({"a": mcp_call(m, "remember_fact", {"fact": "My grandson is in jail"}),
                 "p": mcp_call(m, "set_priority", {"context": "the car", "higher": "cost",
                                                   "lower": "safety"})})
        """, JEFFEREY_CLIENT="jefferey")
        b = self.py("""
            h, c = http()
            out(c.post("/facts", json={"fact": "I have diabetes"}, headers=H(TA)).json())
        """)
        rows = [[f["status"], f["source"]["stated_by"]]
                for f in json.loads(self.store.read_text())["facts"]]
        self.assertEqual(rows, [["pending", "engine"]] * 2)
        self.assertTrue(a["p"]["unconfirmed"], a["p"])
        for x in (a["a"], b):
            self.assertEqual(x["status"], "pending", x)


class NoAIEverTurnsHisValueRound(LifeTest):
    """Whatever he typed, an engine's reversal of a value he stated is a
    proposal; only his own /confirm turns it round."""

    REVERSAL_MESSAGES = [
        # round 5 verify-c (sk5/s_mind.py)
        "Should cost matter more than safety for the car? I decided to ask you first.",
        "I decided to ask you: does cost matter more than safety for the car?",
        "I've decided to think about whether cost matters more than safety for the car.",
        "We decided to look at cheaper cars, would cost matter more than safety for the car?",
        # round 5 verify-b (p/r9e.py): a change of mind about something else
        "I changed my mind about the groceries: cost matters more than safety.",
        "I changed my mind about the groceries. For groceries cost matters more than safety.",
        # round 5's own exception, and round 4's
        "I changed my mind. For the car, cost matters more than safety now, money is tight.",
        "Things changed: for the car cost matters more than safety now.",
        "My sister says cost matters more than safety... Ridiculous.",
        'Karen said "for the car, cost matters more than safety".',
        "Cost matters more than safety for the car.",
    ]

    def test_every_reversal_waits_for_his_own_yes(self):
        # round 7 (D2): what an AI wrote after his statement is noted by the
        # AI; it is his once he confirms it himself — then no AI turns it round
        r = self.py("""
            import jefferey_chat as jc, provenance
            d = jc.dispatch_tool
            res = []
            for i, msg in enumerate(%r):
                ctx = f"the car {i}"
                provenance.owner_typed(f"For {ctx}, safety matters more than cost.")
                a = d("set_priority", {"context": ctx, "higher": "safety", "lower": "cost"})
                row = [p for p in store()["priorities"] if p["context"] == ctx][0]
                jc.conscience.refresh()
                jc.owner_life("/confirm " + row["id"], answer=yes, tty=True)
                provenance.owner_typed(msg.replace("the car", ctx))
                b = d("set_priority", {"context": ctx, "higher": "cost", "lower": "safety"})
                row = [p for p in store()["priorities"] if p["context"] == ctx][0]
                res.append({"a": a.get("unconfirmed"), "changed": b.get("changed"),
                            "now": [row["higher"], row["lower"]],
                            "proposed": (row.get("proposed") or {}).get("higher")})
            out(res)
        """ % (self.REVERSAL_MESSAGES,))
        for msg, x in zip(self.REVERSAL_MESSAGES, r):
            self.assertTrue(x["a"], ("an AI's note waits for his yes", msg))
            self.assertIs(x["changed"], False, (msg, x))
            self.assertEqual(x["now"], ["safety", "cost"], (msg, x))
            self.assertEqual(x["proposed"], "cost", (msg, x))

    def test_a_change_of_mind_about_the_car_never_reaches_moms_care(self):
        # round 5 verify-b HIGH (p/r9e.py)
        r = self.py("""
            import jefferey_chat as jc, provenance
            d = jc.dispatch_tool
            provenance.owner_typed("For Mom's care, safety matters more than cost.")
            first = d("set_priority", {"context": "Mom's care", "higher": "safety", "lower": "cost"})
            jc.conscience.refresh()
            jc.owner_life("/confirm " + first["id"], answer=yes, tty=True)
            provenance.owner_typed("I changed my mind about the car: cost matters more than safety.")
            x = d("set_priority", {"context": "Mom's care", "higher": "cost", "lower": "safety"})
            new = d("set_priority", {"context": "the garden", "higher": "cost", "lower": "safety"})
            rows = {p["context"]: p for p in store()["priorities"]}
            out({"x": x, "care": rows["Mom's care"], "garden": rows["the garden"]})
        """)
        self.assertIs(r["x"].get("changed"), False, r["x"])
        self.assertEqual((r["care"]["higher"], r["care"]["lower"]), ("safety", "cost"))
        self.assertEqual(r["care"]["status"], "confirmed")
        # what he said about the car is not his word about the garden
        self.assertEqual(r["garden"]["source"]["stated_by"], "engine")
        self.assertEqual(r["garden"]["status"], "pending")

    def test_his_own_confirm_turns_it_round(self):
        r = self.py("""
            import jefferey_chat as jc, provenance
            d = jc.dispatch_tool
            provenance.owner_typed("For the car, safety matters more than cost.")
            first = d("set_priority", {"context": "the car", "higher": "safety", "lower": "cost"})
            jc.conscience.refresh()
            jc.owner_life("/confirm " + first["id"], answer=yes, tty=True)
            provenance.owner_typed("I changed my mind. For the car, cost matters more than "
                                   "safety now, money is tight.")
            b = d("set_priority", {"context": "the car", "higher": "cost", "lower": "safety"})
            row = [p for p in store()["priorities"] if p["context"] == "the car"][0]
            jc.conscience.refresh()
            jc.owner_life("/confirm " + row["id"], answer=yes, tty=True)
            row2 = [p for p in store()["priorities"] if p["context"] == "the car"][0]
            out({"b": b, "row": row, "row2": row2})
        """)
        self.assertIs(r["b"].get("changed"), False, r["b"])
        self.assertEqual((r["row"]["higher"], r["row"]["lower"]), ("safety", "cost"))
        self.assertEqual((r["row2"]["higher"], r["row2"]["lower"]), ("cost", "safety"))

    def test_a_near_identical_context_never_gets_round_the_lock(self):
        # convergence vb R9 remaining (3): 'the car.', 'car', 'The car!' or
        # 'my car' created a confirmed row beside his locked one, and
        # priorities_for('the car') returned both opposite values as his
        r = self.py("""
            import jefferey_chat as jc, provenance
            d = jc.dispatch_tool
            provenance.owner_typed("For the car, safety matters more than cost")
            first = d("set_priority", {"context": "the car", "higher": "safety", "lower": "cost"})
            jc.conscience.refresh()
            jc.owner_life("/confirm " + first["id"], answer=yes, tty=True)
            provenance.owner_typed("For the old car I'm selling to Mike, cost matters more "
                                   "than safety.")
            res = [d("set_priority", {"context": c, "higher": "cost", "lower": "safety"})
                   for c in ("the car.", "car", "The car!", "my car")]
            import jefferey_mcp as m
            m.conscience.refresh()
            res.append(mcp_call(m, "set_priority", {"context": "The Car", "higher": "cost",
                                                    "lower": "safety"}))
            jc.conscience.refresh()
            other = d("set_priority", {"context": "the old car I'm selling to Mike",
                                       "higher": "cost", "lower": "safety"})
            jc.conscience.refresh()
            out({"res": res, "rows": store()["priorities"],
                 "for": jc.dispatch_tool("priorities_for", {"context": "the car"})})
        """)
        for x in r["res"]:
            self.assertIs(x.get("changed"), False, x)
        rows = r["rows"]
        mine = [p for p in rows if p["status"] == "confirmed"]
        self.assertEqual([(p["context"], p["higher"], p["lower"]) for p in mine],
                         [("the car", "safety", "cost")])
        self.assertEqual(mine[0]["proposed"]["higher"], "cost")
        self.assertFalse(any(p["source"]["stated_by"] == "owner_words" for p in rows))
        for p in r["for"]:
            if (p["higher"], p["lower"]) == ("cost", "safety"):
                self.assertTrue(p.get("unconfirmed"), p)
                self.assertEqual(p.get("noted_by"), "noted by the AI, not yet confirmed by him")

    def test_what_he_did_not_state_an_ai_may_still_correct(self):
        # round 4 verify-b (k/r9b.py): his rejected ranking was the AI's, so
        # the AI's correction a turn later applies
        r = self.py("""
            import jefferey_chat as jc, provenance
            d = jc.dispatch_tool
            provenance.owner_typed("For groceries, cost matters more than safety? Never!")
            a = d("set_priority", {"context": "groceries", "higher": "cost", "lower": "safety"})
            provenance.owner_typed("Yes, I mean it: safety first.")
            b = d("set_priority", {"context": "groceries", "higher": "safety", "lower": "cost"})
            res = {"a": a, "b": b,
                   "row": [p for p in store()["priorities"] if p["context"] == "groceries"][0]}
            for i, msg in enumerate(["Cost matters more than safety? I strongly disagree.",
                                     "I read that cost matters more than safety.",
                                     "If cost mattered more than safety, I'd buy the cheap one."]):
                provenance.owner_typed(msg)
                d("set_priority", {"context": f"case {i}", "higher": "cost", "lower": "safety"})
            res["cases"] = [[p["source"]["stated_by"], p["status"]] for p in store()["priorities"]
                            if p["context"].startswith("case ")]
            out(res)
        """)
        self.assertTrue(r["a"].get("unconfirmed"), r["a"])
        self.assertIsNot(r["b"].get("changed"), False, r["b"])
        self.assertEqual((r["row"]["higher"], r["row"]["lower"]), ("safety", "cost"))
        self.assertEqual(r["cases"], [["engine", "pending"]] * 3)


class AClaimHeRejectsIsNeverHisWords(LifeTest):

    def test_a_reported_claim_waits_and_his_own_note_is_his(self):
        # round 5 verify-c (sk5/s_prov3.py), verify-b (p/r9f.py)
        r = self.py("""
            import jefferey_chat as jc, provenance
            d = jc.dispatch_tool
            for typed, fact in [
                    ("The doctor thinks I have early dementia, but I don't believe it.",
                     "I have early dementia"),
                    ("My daughter wants me to give her power of attorney. I won't.",
                     "I want to give my daughter power of attorney"),
                    ("The neighbour thinks I have dementia. Ridiculous.", "I have dementia"),
                    ('Karen: "you drink too much". Me: no I don\\'t.', "you drink too much"),
                    ("Mike froze under fire? No way.", "Mike froze under fire"),
                    ("The house feels cold in winter so I keep the heat at 22",
                     "I keep the heat at 22")]:
                provenance.owner_typed(typed)
                d("remember_fact", {"fact": fact, "category": "general"})
            out({f["fact"]: [f["status"], f["source"]["stated_by"]] for f in store()["facts"]})
        """)
        # round 7 (D2): even his own note, written down by an AI, waits for him
        for fact in ("I have early dementia", "I want to give my daughter power of attorney",
                     "I have dementia", "you drink too much", "Mike froze under fire",
                     "I keep the heat at 22"):
            self.assertEqual(r[fact], ["pending", "engine"], fact)

    def test_his_stories_are_his_words_once_he_says_so(self):
        # round 7 (D2): an AI's add_memory is noted by the AI, word for word or
        # not; his own /confirm makes it his words
        r = self.py("""
            import jefferey_chat as jc, provenance
            res = []
            for s in ('My father always said "work hard and be kind", and I have lived by it.',
                      "Mom said we would never go hungry, and we never did, even in 1956.",
                      "The doctor told me I was lucky to survive the heart attack in 1999."):
                provenance.owner_typed(s)
                res.append(jc.dispatch_tool("add_memory", {"text": s}))
            jc.conscience.refresh()
            jc.owner_life("/confirm all", answer=yes, tty=True)
            out({"before": res, "after": store()["memories"]})
        """)
        for m in r["before"]:
            self.assertFalse(m["verbatim"], m)
            self.assertEqual(m.get("status"), "pending", m)
        for m in r["after"]:
            self.assertTrue(m["verbatim"], m)
            self.assertEqual(m.get("status"), "confirmed", m)


class HisOwnHandsMakeHisWords(LifeTest):
    """Round 7 (D2): /remember keeps exactly what he typed as his words;
    /confirm (by number, several, or all) and 'conscience.py confirm' make
    what an AI noted his; the daily brief and get_conscience say how many
    notes wait."""

    def test_remember_keeps_exactly_his_words(self):
        r = self.py("""
            import jefferey_chat as jc
            a = jc.owner_life("/remember Anna calls on Sundays at six", answer=yes, tty=True)
            b = jc.owner_life("/remember I have type 2 diabetes", answer=yes, tty=True)
            no = jc.owner_life("/remember Anna is moving", answer=lambda p: "no", tty=True)
            piped = jc.owner_life("/remember Bob owes me $50", answer=yes, tty=False)
            out({"facts": [[f["fact"], f["status"], f["source"]["stated_by"], f["visibility"]]
                           for f in store()["facts"]]})
        """)
        self.assertEqual(r["facts"], [
            ["Anna calls on Sundays at six", "confirmed", "owner", "engines"],
            ["I have type 2 diabetes", "confirmed", "owner", "private"]])

    def test_confirm_by_number_several_or_all(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            for f in ("Anna calls on Sundays", "Mike lives in Ottawa", "The cat is called Oz",
                      "Bob plays chess"):
                d("remember_fact", {"fact": f})
            jc.conscience.refresh()
            listed = jc.owner_life("/pending", answer=yes, tty=True)
            one = jc.owner_life("/confirm 2", answer=yes, tty=True)
            jc.conscience.refresh()
            two = jc.owner_life("/confirm 1 2", answer=yes, tty=True)
            jc.conscience.refresh()
            rest = jc.owner_life("/confirm all", answer=yes, tty=True)
            out({"listed": [x["what"] for x in listed["pending"]],
                 "facts": {f["fact"]: f["status"] for f in store()["facts"]}})
        """)
        self.assertEqual(r["listed"], ["Anna calls on Sundays", "Mike lives in Ottawa",
                                       "The cat is called Oz", "Bob plays chess"])
        self.assertEqual(set(r["facts"].values()), {"confirmed"})

    def test_conscience_py_confirm_at_his_keyboard(self):
        self.py("""
            import jefferey_chat as jc
            for f in ("Anna calls on Sundays", "Mike lives in Ottawa", "Bob plays chess"):
                jc.dispatch_tool("remember_fact", {"fact": f})
            out(1)
        """, JEFFEREY_CLIENT="jefferey")
        import subprocess, sys
        from test_life import CONNECTOR
        p = subprocess.run([sys.executable, str(CONNECTOR / "conscience.py"), "confirm"],
                           input="1 3\nyes\n", env=self.env(), cwd=self.tmp,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("1. (fact) Anna calls on Sundays", p.stdout)
        self.assertIn("they are your own words now", p.stdout)
        facts = {f["fact"]: f["status"] for f in json.loads(self.store.read_text())["facts"]}
        self.assertEqual(facts, {"Anna calls on Sundays": "confirmed",
                                 "Mike lives in Ottawa": "pending",
                                 "Bob plays chess": "confirmed"})
        p = subprocess.run([sys.executable, str(CONNECTOR / "conscience.py"), "confirm"],
                           input="all\nno\n", env=self.env(), cwd=self.tmp,
                           capture_output=True, text=True, timeout=120)
        self.assertIn("Nothing was changed", p.stdout)

    def test_the_brief_and_get_conscience_say_how_many_wait(self):
        r = self.py("""
            import jefferey_mcp as m
            mcp_call(m, "remember_fact", {"fact": "Anna calls on Sundays"})
            mcp_call(m, "set_priority", {"context": "the car", "higher": "safety",
                                         "lower": "cost"})
            out({"brief": mcp_call(m, "daily_brief"), "con": mcp_call(m, "get_conscience")})
        """, JEFFEREY_CLIENT="jefferey")
        for where in ("brief", "con"):
            w = r[where]["waiting_for_owner"]
            self.assertEqual(w["notes_to_confirm"], 2, (where, w))
            self.assertIn("wait for his confirmation", w["how"])



if __name__ == "__main__":
    unittest.main()
