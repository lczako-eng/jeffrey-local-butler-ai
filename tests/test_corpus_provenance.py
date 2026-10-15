"""
Frozen corpus — his own words, and who may turn his values round (R9),
repair round 6.

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
"""

from __future__ import annotations

import unittest

from test_life import LifeTest

C, S = ("cost", "safety"), ("safety", "cost")
FC, FS = ("coût", "sécurité"), ("sécurité", "coût")

# (what he typed, (higher, lower), does it back that ranking as his words?)
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
]

# (what he typed, what an AI wrote down, is it his own words?)
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
]


class HisWordsFrozenCorpus(LifeTest):

    def test_which_rankings_are_his(self):
        r = self.py("""
            import provenance
            res = []
            for typed, (hi, lo), _ in %r:
                provenance.reset(); provenance.owner_typed(typed)
                res.append(provenance.ranked_by_owner(hi, lo))
            out(res)
        """ % (RANKINGS,))
        bad = [(t, r_, want) for (t, r_, want), got in zip(RANKINGS, r) if got != want]
        self.assertEqual(bad, [], "\n" + "\n".join(map(str, bad)))

    def test_which_words_are_his(self):
        r = self.py("""
            import provenance
            res = []
            for typed, said, _ in %r:
                provenance.reset(); provenance.owner_typed(typed)
                res.append(provenance.verbatim(said))
            out(res)
        """ % (WORDS,))
        bad = [(t, s, want) for (t, s, want), got in zip(WORDS, r) if got != want]
        self.assertEqual(bad, [], "\n" + "\n".join(map(str, bad)))


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
        r = self.py("""
            import jefferey_chat as jc, provenance
            d = jc.dispatch_tool
            res = []
            for i, msg in enumerate(%r):
                ctx = f"the car {i}"
                provenance.owner_typed(f"For {ctx}, safety matters more than cost.")
                a = d("set_priority", {"context": ctx, "higher": "safety", "lower": "cost"})
                provenance.owner_typed(msg.replace("the car", ctx))
                b = d("set_priority", {"context": ctx, "higher": "cost", "lower": "safety"})
                row = [p for p in store()["priorities"] if p["context"] == ctx][0]
                res.append({"a": a.get("unconfirmed"), "changed": b.get("changed"),
                            "now": [row["higher"], row["lower"]],
                            "proposed": (row.get("proposed") or {}).get("higher")})
            out(res)
        """ % (self.REVERSAL_MESSAGES,))
        for msg, x in zip(self.REVERSAL_MESSAGES, r):
            self.assertFalse(x["a"], ("his own statement is his", msg))
            self.assertIs(x["changed"], False, (msg, x))
            self.assertEqual(x["now"], ["safety", "cost"], (msg, x))
            self.assertEqual(x["proposed"], "cost", (msg, x))

    def test_a_change_of_mind_about_the_car_never_reaches_moms_care(self):
        # round 5 verify-b HIGH (p/r9e.py)
        r = self.py("""
            import jefferey_chat as jc, provenance
            d = jc.dispatch_tool
            provenance.owner_typed("For Mom's care, safety matters more than cost.")
            d("set_priority", {"context": "Mom's care", "higher": "safety", "lower": "cost"})
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
            d("set_priority", {"context": "the car", "higher": "safety", "lower": "cost"})
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
        for fact in ("I have early dementia", "I want to give my daughter power of attorney",
                     "I have dementia", "you drink too much", "Mike froze under fire"):
            self.assertEqual(r[fact], ["pending", "engine"], fact)
        self.assertEqual(r["I keep the heat at 22"], ["confirmed", "owner_words"])

    def test_his_stories_are_his_words(self):
        r = self.py("""
            import jefferey_chat as jc, provenance
            res = []
            for s in ('My father always said "work hard and be kind", and I have lived by it.',
                      "Mom said we would never go hungry, and we never did, even in 1956.",
                      "The doctor told me I was lucky to survive the heart attack in 1999."):
                provenance.owner_typed(s)
                res.append(jc.life.add_memory(s))
            out(res)
        """)
        for m in r:
            self.assertTrue(m["verbatim"], m)
            self.assertNotEqual(m.get("status"), "pending", m)


if __name__ == "__main__":
    unittest.main()
