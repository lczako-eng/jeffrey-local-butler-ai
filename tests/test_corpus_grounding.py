"""
Frozen corpus — two-letter words in grounding (R11), repair round 6.

Round 4 let two-letter words count only from a short list of abbreviations,
so names and abbreviations missing from it ('Ed', 'Jo', 'Dr Wu', 'VW', 'GM')
found nothing, 'Li has HIV' was no longer caught in a draft, and a value for
"Ed's care" reached "Mom's care". Round 5 let every two-letter word count
except a list of grammar words, so units, streets and name suffixes ('kg',
'Rd', 'Jr', 'où') grounded unrelated facts, and capitals typed for emphasis
('Is it OK to GO UP there?', 'Is it ON?') grounded again. This file freezes
every case the round-4 and round-5 skeptics reported.

The structural rule: a word of two letters or fewer grounds only when it is
written capitalised — as a name ('Ed', 'Jo', 'Li', 'Wu') or an abbreviation
in capitals ('RA', 'GM', 'AA', 'ER', 'MS') — in BOTH the subject asked and
the fact, and never when it is a unit, a street or a title ('kg', 'km',
'Rd', 'St', 'Jr', 'Dr', 'Mr') or the grammar of a sentence ('go', 'up',
'ok', 'on', 'is', 'là', 'va', 'Do', 'An'), in capitals or not. A message
typed all in capitals says nothing by its capitals. check_draft still
catches a private fact about someone with a short name, even one that is
also a little word ('Do', 'An'), because a draft repeating it repeats the
name and the fact together.
"""

from __future__ import annotations

import json
import unittest

from test_life import LifeTest

# grounding.content(text): the words of two letters or fewer it keeps
# (p/r11.py, sk5/s_gr.py and the round-4 and round-5 tests)
SHORT: list[tuple[str, set[str]]] = [
    ("is it ok to go up there", set()), ("Is it OK to GO UP there?", set()),
    ("I want to GO HOME", set()), ("Can we GO now?", set()), ("Ça va bien?", set()),
    ("Ça va", set()), ("Où es-tu?", set()), ("Tu es là?", set()),
    ("Je ne sais pas si je dois y aller", set()), ("On y va, Ed", {"ed"}),
    ("Er, what about Mom?", set()), ("Um, er, hm", set()), ("Mm-hm, ok", set()),
    ("Oui, ça me va", set()), ("Qu'en dis-tu?", set()), ("Il y a un an", set()),
    ("Et toi?", set()), ("Dis-le moi", set()), ("C'est ça", set()), ("Ah ça non", set()),
    ("Vas-y", set()), ("Mets-le là", set()), ("Nous y sommes", set()), ("OK", set()),
    ("Ok so what do I do", set()), ("Hey yo", set()), ("Ya know", set()), ("Uh oh", set()),
    ("Hi Jo", {"jo"}), ("Dr Wu said", {"wu"}), ("Mom has RA", {"ra"}), ("Ed's care", {"ed"}),
    ("AA meeting", {"aa"}), ("GM pension", {"gm"}), ("I am at the ER", {"er"}),
    ("We go to the UK in May", {"uk"}), ("Help me Al", {"al"}), ("So, er, ok", set()),
    ("Is it ON?", set()), ("Turn it OFF", set()), ("Je vais au lit", set()),
    ("Mes pieds me font mal", set()), ("Ni oui ni non", set()), ("Ou bien", set()),
    ("Ce soir", set()), ("Ma fille", set()), ("Ta soeur", set()), ("Sa voiture", set()),
    ("Un peu", set()), ("Au revoir", set()), ("Nu", set()), ("Té", set()),
    ("Né en 1950", set()), ("Yes, do it", set()), ("Go ahead", set()), ("OH NO", set()),
    ("Oh no!", set()), ("Aw, ok", set()), ("No, he is ok", set()), ("I'm in", set()),
    ("Me too", set()), ("Up to you", set()), ("Ex-wife Karen", set()),
    ("où as-tu mis mes lunettes?", set()), ("Mike Jr is coming for dinner", set()),
    ("buy 2 kg of apples", set()), ("the house on Maple Rd is for sale", set()),
    ("Dad takes 10 mg of melatonin", set()), ("PS call me later", set()),
    ("u ok? ur late", set()), ("Ca va? Oui ça va bien", set()), ("Je suis né à Paris", set()),
    ("ON est rendu où?", set()), ("Il a 2 ans", set()), ("Les gens de mon âge", set()),
    ("Rendez-vous à 9 h", set()), ("Can we go at 9 AM?", set()), ("I'm going to the ER", {"er"}),
    ("Ok so what about Ed", {"ed"}), ("Bob Smith Jr fixed the roof", set()),
    ("We live at 12 Elm Rd", set()), ("I weigh 80 kg", set()), ("Mom takes 5 mg of warfarin", set()),
    ("We live on Elm St", set()), ("Le chalet est là où la rivière rejoint le lac", set()),
    ("Our cat is named Oz", set()), ("Karen has MS", {"ms"}), ("Ms Patel called", set()),
    ("Mr. Do is in rehab", set()), ("Ho has HIV", {"ho"}), ("Su has cancer", {"su"}),
    ("Lu", {"lu"}), ("the tv is on", set()), ("We bought a new TV in May", {"tv"}),
    ("ed's birthday", set()), ("IS HE AT HOME TODAY", set()), ("HO HAS HIV", set()),
]

# explain_basis on the terminal: (facts, [(subject, facts it finds — all of
# them, and only them)]) — each set in a store of its own. A fact that is
# private (his health, his money) is found only by a subject that names that
# kind of thing (I-11, I-28): 'TD' alone does not find 'Our bank is TD', 'Dr
# Wu' finds 'Dr Wu is my heart doctor' and 'Wu' alone does not.
LOOKUPS: list[tuple[list[str], list[tuple[str, list[str]]]]] = [
    # round 4 verify-b (k/r11a.py)
    (["Our bank is TD", "Karen has MS", "The fridge is an LG", "Dad worked at GM for 30 years",
      "He drives a VW Golf", "The printer is an HP", "Mom sees the GI specialist",
      "He goes to AA on Tuesdays", "Karen has RA in her hands", "We go to the cottage every July",
      "Mike will go to the dentist on Friday", "We bought a new TV in May",
      "He is up at 5 every day", "We said no to the offer", "Mom was in the OR for three hours",
      "Le chat va au vétérinaire le lundi", "Il va à la messe le dimanche",
      "Nous sommes allés au Québec"],
     [("TD", []), ("what about TD?", []), ("my TD account", ["Our bank is TD"]),
      ("MS", ["Karen has MS"]), ("LG fridge", ["The fridge is an LG"]),
      ("GM pension", ["Dad worked at GM for 30 years"]), ("VW", ["He drives a VW Golf"]),
      ("HP printer", ["The printer is an HP"]), ("GI", []),
      ("GI specialist", ["Mom sees the GI specialist"]),
      ("AA meeting", ["He goes to AA on Tuesdays"]), ("RA", ["Karen has RA in her hands"]),
      ("is it ok to go up there", []), ("go", []), ("up", []), ("no", []), ("OR", []),
      ("on y va", []), ("va", []), ("is he up?", []), ("ok", []), ("so", []),
      ("oh no", []), ("Is it ok?", []), ("Can we go?", []), ("au", [])]),
    # round 4 verify-c (skep/gr.py)
    (["Ed's birthday is May 3", "Al from next door borrowed the ladder",
      "Dr Wu is my heart doctor", "Dr Li prescribed the new pills",
      "My TD account is for the pension", "The HP printer needs ink",
      "The LG fridge is under warranty until 2027", "I was diagnosed with MS in 2019",
      "My RA flares up in the cold", "I worked at CN for 30 years", "Jo is my granddaughter",
      "We bought a new TV in May", "I have AF and take blood thinners",
      "The NP at the clinic is very kind"],
     [("Ed", ["Ed's birthday is May 3"]), ("when is Ed's birthday", ["Ed's birthday is May 3"]),
      ("Al", ["Al from next door borrowed the ladder"]), ("Dr Wu", ["Dr Wu is my heart doctor"]),
      ("Wu", []), ("Dr Li", ["Dr Li prescribed the new pills"]), ("TD", []),
      ("my TD account", ["My TD account is for the pension"]),
      ("HP", ["The HP printer needs ink"]), ("LG", ["The LG fridge is under warranty until 2027"]),
      ("LG fridge", ["The LG fridge is under warranty until 2027"]),
      ("MS", []), ("MS diagnosis", ["I was diagnosed with MS in 2019"]),
      ("RA", ["My RA flares up in the cold"]),
      ("CN", ["I worked at CN for 30 years"]), ("Jo", ["Jo is my granddaughter"]),
      ("TV", ["We bought a new TV in May"]), ("AF", []),
      ("AF medication", ["I have AF and take blood thinners"]), ("NP", []),
      ("the NP at the clinic", ["The NP at the clinic is very kind"])]),
    # round 5 verify-c (sk5/s_gr2.py)
    (["The doctor said it is OK to drive again", "We go to the cottage every July",
      "Le chalet est là où la rivière rejoint le lac", "I weigh 80 kg", "We live at 12 Elm Rd",
      "Bob Smith Jr fixed the roof"],
     [("Is it OK to go up there?", []), ("Où est la pharmacie?", []),
      ("buy 2 kg of apples", []), ("Is the house on Maple Rd nice?", []),
      ("Mike Jr is coming for dinner", [])]),
    # round 5 verify-b (p/r11b.py)
    (["Anna picks me up on Tuesdays", "We go to the cottage in July",
      "OK Tire did the winter tires", "The basement light is ON a timer",
      "Oh, and the furnace filter is in the garage"],
     [("is it ok to go up there", []), ("Is it OK to GO UP there?", []), ("OH NO", []),
      ("Is it ON?", [])]),
    # the round-4 and round-5 tests
    (["We go to the cottage every July", "Mike will go to the dentist on Friday",
      "We bought a new TV in May", "Mom was in the ER in March",
      "Le chat va au vétérinaire le lundi", "Il va à la messe le dimanche"],
     [("is it ok to go up there", []), ("TV", ["We bought a new TV in May"]),
      ("the ER", ["Mom was in the ER in March"]), ("on y va", []), ("va", []),
      ("Can we go?", [])]),
]

# check_draft to 'the neighbours' with these private health facts kept
# (skep/cd.py, p/cd2.py): (draft, caught?)
PRIVATE = ["Ed has MS and uses a cane", "Jo is in AA", "Al takes pills for his BP",
           "Mom has RA in her hands", "Li has HIV", "Ho has HIV", "Mr. Do is in rehab",
           "An is pregnant again", "Su has cancer"]
DRAFTS: list[tuple[str, bool]] = [
    ("Ed has MS, so he can't come", True), ("Jo is in AA now", True), ("Mom has RA", True),
    ("Li has HIV", True), ("Al takes pills for his BP", True), ("Ho has HIV", True),
    ("Do is in rehab", True), ("An is pregnant again", True), ("Su has cancer", True),
    ("Do you want to come for dinner on Sunday?", False),
    ("An apple pie for the bake sale", False), ("Hi Jo, see you Sunday", False),
    ("Ed and Al will bring chairs", False),
]


class ShortWordsGroundOnlyAsNamesOnBothSides(LifeTest):

    def test_which_short_words_count(self):
        r = self.py("""
            import grounding as g
            out({t: sorted(w for w in g.content(t) if len(w) <= 2 and w.isalpha()
                           and w.isascii()) for t, _ in %r})
        """ % (SHORT,))
        wrong = [(t, r[t], sorted(want)) for t, want in SHORT if set(r[t]) != want]
        self.assertEqual(wrong, [], f"{len(wrong)} of {len(SHORT)}:\n"
                         + "\n".join(map(repr, wrong)))

    def _lookups(self, facts, asks, surface="terminal", store="c.json"):
        return self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            for f in %r:
                d("remember_fact", {"fact": f, "category": "general"})
            if %r == "mcp":
                import jefferey_mcp as m
                m.conscience.refresh()
                ask = lambda q: [x.get("fact") for x in mcp_call(m, "explain_basis",
                                                                {"topic": q}).get("facts", [])]
            else:
                ask = lambda q: [x.get("fact") for x in d("explain_basis", {"topic": q})
                                 .get("facts", [])]
            out({q: ask(q) for q, _ in %r})
        """ % (facts, surface, asks), JEFFEREY_CLIENT="jefferey",
            JEFFEREY_CONSCIENCE_PATH=str(self.tmp / store))

    def test_every_lookup_the_skeptics_named(self):
        wrong = []
        for i, (facts, asks) in enumerate(LOOKUPS):
            r = self._lookups(facts, asks, "mcp" if i == 3 else "terminal", f"c{i}.json")
            for q, want in asks:
                if sorted(r[q]) != sorted(want):
                    wrong.append((q, r[q], want))
        n = sum(len(a) for _, a in LOOKUPS)
        self.assertEqual(wrong, [], f"{len(wrong)} of {n} lookups:\n"
                         + "\n".join(map(repr, wrong)))

    def test_a_value_for_one_persons_matter_never_reaches_anothers(self):
        r = self.py("""
            import jefferey_chat as jc, provenance as p
            D = jc.dispatch_tool
            p.owner_typed("For Ed's care, staying at home matters more than cost.")
            D("set_priority", {"context": "Ed's care", "higher": "staying at home", "lower": "cost"})
            p.owner_typed("For Jo's wedding, family matters more than money.")
            D("set_priority", {"context": "Jo's wedding", "higher": "family", "lower": "money"})
            out({q: [x.get("context") for x in D("explain_basis", {"topic": q})
                     .get("priorities", [])]
                 for q in ("Mom's care", "Anna's wedding", "Ed's care", "Jo's wedding")})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertNotIn("Ed's care", r["Mom's care"])
        self.assertNotIn("Jo's wedding", r["Anna's wedding"])
        self.assertIn("Ed's care", r["Ed's care"])
        self.assertIn("Jo's wedding", r["Jo's wedding"])

    def test_a_draft_repeating_a_short_named_private_fact_is_caught(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            for t in %r:
                d("remember_fact", {"fact": t, "category": "health"})
            out([d("check_draft", {"text": t, "audience": "the neighbours"}) for t, _ in %r])
        """ % (PRIVATE, DRAFTS), JEFFEREY_CLIENT="jefferey")
        wrong = [(t, x["ok"], x.get("problems")) for (t, caught), x in zip(DRAFTS, r)
                 if x["ok"] == caught]
        self.assertEqual(wrong, [], "\n".join(map(repr, wrong)))


if __name__ == "__main__":
    unittest.main()
