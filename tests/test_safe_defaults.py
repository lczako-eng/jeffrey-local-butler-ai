"""
Safe defaults where words are still read — round 8, engineer 2 (F1 to F6).

Round 7 replaced word detection with "ask the owner" decisions; its two
skeptics showed where words are still read, and read too narrowly: a no for
'JEFFEREY', 'Сlaude' (a Cyrillic С) or 'my lawyer' held back from nobody;
'sugar-free over taste' for his diabetes diet went to every AI past 'Never
tell my health to any AI'; 'Garage door opener: 4821' and 'Security question
answer: Fluffy' went out in clear, and explain_basis(topic='Bluebird77')
confirmed a guessed password; a charge after a cancelled membership was no
longer claimed; 'jo is on chemo …' typed in small letters let 'Jo is on
chemo' go to the neighbours; 'Open the front for the plumber' and 'Have the
plumber in at 10' were allowed. Every repro is in roundD_verdicts.json (v1
D1 cases 2-5, v1 D3, v1 new_regressions, v2 D4, D5, D6 and new_regressions).

The decisions:

    fold  one reader for look-alike letters, shared by every reader below
          (grounding.fold): NFKC, Cyrillic, Greek, Armenian, Cherokee, small
          capitals, full-width and mathematical letters, digits and @$| for
          letters, a capital I for l, spaced-out or dotted letters, a split
          word, zero-width characters, hyphens and possessives — each read
          back only when that makes a word the reader knows
    F1    an audience no one knows is everyone: a no whose audience is not a
          person he recorded, one of his keys, or a group (anyone, family,
          AI) holds for everyone and every AI, and set_rule says so
    F2    a no on a topic reaches his values and his health (lab results,
          measures, the most-prescribed medicines in Canada)
    F3    codes and secret answers; a topic search matches only what would
          be shown; JEFFEREY's own codes are never hidden as a note
    F4    money after a cancellation and look-alike bills
          (tests/test_corpus_money.py)
    F5    a draft names a person in any case
    F6    the door words (tests/test_corpus_door.py)

Invented people only: his daughter Anna, his ex-wife Karen Novak, friends
with short names (Ed, Jo, Li, Ty, Wu), a lawyer Dana Reyes; every address is
on an example domain.
"""

from __future__ import annotations

import json
import textwrap
import unittest

from test_his_own import HisOwnTest
from test_life import LifeTest

EVERY = "everyone and every AI"


# ======================================================================= fold
FOLDS: list[tuple[str, str]] = [
    # look-alike letters (v1 D1 case 3, v2 D4)
    ("СhatGPT", "chatgpt"), ("Сlaude", "claude"), ("АI", "ai"),
    ("ΑΙ", "ai"), ("Unlօck the dօօr", "unlock the door"),
    ("Ꮮet him in", "let him in"), ("ʟet the plumber ɪn", "let the plumber in"),
    ("ＣＬＡＵＤＥ", "claude"),
    ("\U0001d402\U0001d425\U0001d41a\U0001d42e\U0001d41d\U0001d41e", "claude"),
    ("Clau​de", "claude"),
    # digits and @$| for letters, a capital I for l
    ("Cl4ude", "claude"), ("p@ssword", "password"), ("pa$$word", "password"),
    ("passw0rd", "password"), ("Iet him in", "let him in"),
    ("UnIock it for the courier", "unlock it for the courier"),
    ("|et the man |n", "let the man in"), ("unl0ck the d00r", "unlock the door"),
    # spaced-out, dotted and split words, hyphens
    ("C l a u d e", "claude"), ("A I", "ai"), ("A.I.", "ai"), ("P I N 4821", "pin 4821"),
    ("le t him in", "let him in"), ("Chat-GPT", "chatgpt"),
    # ...and nothing else changes
    ("Hunter22", "hunter22"), ("gpt4o", "gpt4o"), ("My A1C was 8.2", "my a1c was 8.2"),
    ("I am fine", "i am fine"), ("If it rains", "if it rains"), ("Route 66", "route 66"),
    ("le chat", "le chat"), ("Anna", "anna"), ("4821", "4821"),
]


class TheFoldReadsLookAlikeLettersAsLatin(LifeTest):

    def test_every_look_alike_the_skeptics_wrote(self):
        r = self.py("""
            import grounding as g
            out([g.fold(t) for t, _ in %r])
        """ % (FOLDS,))
        wrong = [(t, got, want) for (t, want), got in zip(FOLDS, r) if got != want]
        self.assertEqual(wrong, [], "\n".join(map(repr, wrong)))

    def test_the_readers_of_an_audience_read_through_it(self):
        # v1 new_regressions D1 [MEDIUM]: "AI's", 'AI-powered apps' and
        # 'claude-raw' were not an AI; v1 D1 case 3: look-alikes and spellings
        r = self.py("""
            import grounding as g
            ai = ["AI's", "AI-powered apps", "claude-raw", "\\u0421hatGPT", "\\u0421laude",
                  "\\u0410I", "\\u0391\\u0399", "Chat-GPT", "A I", "C l a u d e", "Cl4ude",
                  "gpt4o", "Le Chat", "les intelligences artificielles", "JEFFEREY",
                  "Jefferey", "Jeffrey", "the butler", "the local model", "my local model",
                  "the model", "Ollama", "the computer", "computers", "my computer",
                  "l'ordinateur", "les machines", "Alexa", "Siri", "Mistral", "gpt-raw"]
            fam = ["my wife", "my sister", "ma soeur", "ma s\\u0153ur", "my brother",
                   "my nephew", "the in-laws", "my daughter-in-law", "ma belle-fille",
                   "my stepson", "my husband", "my partner", "my spouse", "my niece",
                   "my cousin", "my aunt", "my uncle", "my mother", "my father", "my mom",
                   "my mum", "my dad", "my parents", "my step-daughter", "my grandmother",
                   "my great-grandson", "ma femme", "mon mari", "mon conjoint",
                   "mon fr\\u00e8re", "mon neveu", "ma ni\\u00e8ce", "ma cousine", "ma tante",
                   "mon oncle", "ma m\\u00e8re", "mon p\\u00e8re", "mes parents",
                   "ma belle-m\\u00e8re", "mon beau-p\\u00e8re", "mon demi-fr\\u00e8re",
                   "ma petite-fille", "my brother Mike", "my \\u0455ister"]
            not_fam = ["my son's teacher", "la femme de m\\u00e9nage", "Karen's husband",
                       "my lawyer", "the neighbours"]
            out({"ai": {a: g.names_ai(a) for a in ai},
                 "fam": {a: g.names_family(a) for a in fam},
                 "not_fam": {a: g.names_family(a) for a in not_fam}})
        """)
        self.assertEqual([a for a, v in r["ai"].items() if not v], [])
        self.assertEqual([a for a, v in r["fam"].items() if not v], [])
        self.assertEqual([a for a, v in r["not_fam"].items() if v], [])


# ========================================================================= F1
class F1AnAudienceNoOneKnowsIsEveryone(HisOwnTest):
    """v1 D1: 'Le Monde', 'Bob', 'my lawyer' and 'Joe Everyone' bound only
    themselves, and every look-alike or spelling of an AI bound nobody."""

    SETUP = """
        import jefferey_mcp as m
        h, c = http()
        with access.owner_console():
            m.life.add_memory("Diagnosed with type 2 diabetes in June.", visibility="family")
            m.life.add_memory("The orb made her laugh.", visibility="family")
            m.conscience.remember_fact("I have type 2 diabetes and take metformin", "health")
        def no(aud, tags="health"):
            with access.owner_console():
                m.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                m.conscience.refresh()
                return m.rules.set_rule("disclosure", tags, "Never tell my health to " + aud,
                                        audience=aud, allow=False)
        def reads():
            m.conscience.refresh(); h.conscience.refresh()
            # (claude-raw never holds his private health: only the two keys
            # that may read it are asked)
            return {"family": "diabetes" in c.get("/life", headers=H(TF)).text,
                    "jefferey": "metformin" in json.dumps(
                        mcp_as(m, "jefferey", "explain_basis", {"topic": "diabetes"}))}
    """

    def test_set_rule_says_in_plain_words_whom_it_does_not_know(self):
        r = self.py(pre=textwrap.dedent(self.SETUP), code="""
            res = {}
            for a in ("my lawyer", "Bob", "Le Monde", "the public or the press"):
                said = no(a)
                res[a] = [said.get("holds_for"), said.get("note"), reads()]
            out(res)
        """)
        for a, (holds, note, seen) in r.items():
            self.assertEqual(holds, EVERY, a)
            self.assertEqual(seen, {"family": False, "jefferey": False}, a)
        self.assertIn("I don't know who 'my lawyer' is, so this no holds for everyone and "
                      "every AI. Add them to your people to make it narrower.", r["my lawyer"][1])
        self.assertIn("I don't know who 'Bob' is", r["Bob"][1])
        self.assertIn("I don't know who 'the press' is", r["the public or the press"][1])

    def test_a_person_he_recorded_makes_it_narrow_and_an_ais_person_does_not(self):
        r = self.py(pre=textwrap.dedent(self.SETUP), code="""
            res = {}
            # an AI writes down 'my lawyer': that never narrows his no (S3)
            mcp_as(m, "jefferey", "add_person", {"name": "Dana Reyes", "relationship": "lawyer"})
            res["ai_person"] = [no("my lawyer").get("holds_for"), reads()]
            with access.owner_console():
                m.conscience.refresh()
                m.life.add_person("Bob", "friend")
                m.life.add_person("Dr. Amira Haddad", "GP")
                m.life.add_person("Karen Novak", "ex-wife")
                m.life.add_person("Le Monde", "newspaper")
                m.life.add_person("Mrs. Patel", "neighbour")
            for a in ("Bob", "my GP", "Karen", "Karen Novak", "Le Monde", "Mrs. Patel"):
                res[a] = [no(a).get("holds_for"), reads()]
            # 'Bob Smith' is not the Bob he recorded: nobody knows him
            res["Bob Smith"] = [no("Bob Smith").get("holds_for"), reads()]
            out(res)
        """)
        self.assertEqual(r["ai_person"], [EVERY, {"family": False, "jefferey": False}])
        for a in ("Bob", "my GP", "Karen", "Karen Novak", "Le Monde", "Mrs. Patel"):
            self.assertNotEqual(r[a][0], EVERY, a)
            self.assertEqual(r[a][1], {"family": True, "jefferey": True}, a)
        self.assertEqual(r["Bob Smith"][0], EVERY)

    def test_a_family_word_binds_the_family_key_and_the_person_he_recorded(self):
        # v1 D1 case 5: 'my wife', 'my sister', 'ma soeur', 'my brother', 'my
        # nephew', 'the in-laws', 'my daughter-in-law', 'ma belle-fille', 'my
        # stepson' were not the family; with a yes for anyone plus a no for
        # 'my sister', check_disclosure('family', 'health') was True
        r = self.py(pre=textwrap.dedent(self.SETUP), code="""
            res = {}
            for a in ("my wife", "my sister", "ma soeur", "my brother", "my nephew",
                      "the in-laws", "my daughter-in-law", "ma belle-fille", "my stepson"):
                res[a] = [no(a).get("holds_for"), reads()]
            with access.owner_console():
                m.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                m.conscience.refresh()
                m.life.add_person("Lena", "sister")
                m.rules.set_rule("disclosure", "health", "Anyone may know", audience="anyone",
                                 allow=True)
                m.rules.set_rule("disclosure", "health", "Not my sister", audience="my sister",
                                 allow=False)
            res["check"] = {a: m.rules.check_disclosure(a, "health")["allowed"]
                            for a in ("family", "Lena", "a neighbour")}
            out(res)
        """)
        check = r.pop("check")
        for a, (holds, seen) in r.items():
            self.assertNotEqual(holds, EVERY, a)
            self.assertEqual(seen, {"family": False, "jefferey": True}, a)
        self.assertEqual(check, {"family": False, "Lena": False, "a neighbour": True})

    def test_a_no_for_jefferey_or_the_machine_holds_for_a_model_in_the_house(self):
        # v1 D1 case 2 (d1d.py): with 'JEFFEREY', 'the local model' or 'my
        # computer' as the audience and a model on this Mac, the system
        # prompt, explain_basis and who_am_i all carried metformin
        r = self.py("""
            import jefferey_chat as jc
            with access.owner_console():
                jc.life.add_memory("Diagnosed with type 2 diabetes in June.", visibility="family")
                jc.conscience.remember_fact("I have type 2 diabetes and take metformin", "health")
            egress.bind("chat", engine="llama3 on this machine (local \\u2014 stays in the house)")
            res = {"in_house": egress.in_the_house()}
            for aud in ("JEFFEREY", "the local model", "my computer", "the butler", "Ollama"):
                with access.owner_console():
                    jc.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                    jc.rules.set_rule("disclosure", "health", "Never tell my health to " + aud,
                                      audience=aud, allow=False)
                jc.conscience.refresh()
                res[aud] = ["metformin" in jc.system_prompt(),
                            "metformin" in json.dumps(jc.dispatch_tool("explain_basis",
                                                                       {"topic": "diabetes"})),
                            "diabetes" in json.dumps(jc.dispatch_tool("who_am_i", {}))]
            out(res)
        """, JEFFEREY_CLIENT="jefferey")
        self.assertTrue(r.pop("in_house"))
        for aud, seen in r.items():
            self.assertEqual(seen, [False, False, False], aud)


# ========================================================================= F2
class F2ANoOnATopicReachesHisValuesAndHisHealth(HisOwnTest):
    """v1 D1 case 4 (d1b.py): under 'Never tell my health to any AI', his
    value 'sugar-free over taste' for 'my diabetes diet' reached claude-raw
    (get_conscience, priorities_for) and jefferey (who_am_i), and 'My A1C
    was 8.2 at the last checkup' and 'I take Ozempic every Sunday' reached
    every AI, because they were not recognised as health."""

    def test_his_values_and_lab_results_stay_home_on_every_surface(self):
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc, re
            h, c = http()
            with access.owner_console():
                m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                 audience="any AI", allow=False)
                m.conscience.set_priority(context="my diabetes diet", higher="sugar-free",
                                          lower="taste")
                m.conscience.set_priority(context="travel", higher="direct flights",
                                          lower="price")
                m.conscience.remember_fact("My A1C was 8.2 at the last checkup", "general")
                m.conscience.remember_fact("I take Ozempic every Sunday", "general")
                m.conscience.remember_fact("My LDL is down and my eGFR is fine", "general")
                m.conscience.log_observation("Blood sugar was 14 this morning", "general")
                m.conscience.remember_fact("Anna calls on Sundays", "general")
            MARK = re.compile(r"diabet|sugar|A1C|Ozempic|LDL|eGFR", re.I)
            seen = {}
            for cl in ("jefferey", "claude-raw"):
                for name, args in (("get_conscience", {}), ("priorities_for", {}),
                                   ("priorities_for", {"context": "my diabetes diet"}),
                                   ("explain_basis", {"topic": "my diabetes diet"}),
                                   ("explain_basis", {"topic": "Ozempic"}),
                                   ("explain_basis", {"topic": "A1C"}), ("who_am_i", {}),
                                   ("daily_brief", {})):
                    s = json.dumps(mcp_as(m, cl, name, args))
                    seen[f"mcp {cl} {name} {args}"] = sorted(set(x.lower() for x in
                        MARK.findall(re.sub(r'"topic": "[^"]*"', "", s))))
            for path in ("/conscience", "/priorities"):
                seen["http gpt-raw " + path] = sorted(set(x.lower() for x in MARK.findall(
                    c.get(path, headers=H(TG)).text)))
            term("list_rules", {})                  # the terminal's own key and door
            seen["terminal"] = sorted(set(x.lower() for x in MARK.findall(jc.system_prompt())))
            travel = mcp_as(m, "claude-raw", "priorities_for", {"context": "travel"})
            travel = [travel] if isinstance(travel, dict) else travel
            out({"seen": seen, "travel": travel,
                 "anna": "Anna calls" in json.dumps(mcp_as(m, "claude-raw", "get_conscience"))})
        """)
        self.assertEqual({k: v for k, v in r["seen"].items() if v}, {})
        self.assertEqual([p["higher"] for p in r["travel"]], ["direct flights"])
        self.assertTrue(r["anna"])

    def test_the_health_lexicon_knows_lab_results_measures_and_medicines(self):
        names = ("A1C HbA1c INR LDL HDL cholesterol glucose insulin eGFR PSA BP BMI "
                 "metformin Ozempic semaglutide atorvastatin rosuvastatin levothyroxine "
                 "Synthroid ramipril amlodipine Jardiance empagliflozin Januvia sitagliptin "
                 "Lipitor Crestor Eliquis apixaban Xarelto rivaroxaban warfarin Coumadin "
                 "pantoprazole Pantoloc omeprazole Losec Nexium esomeprazole hydrochlorothiazide "
                 "metoprolol bisoprolol candesartan Atacand losartan Cozaar valsartan Diovan "
                 "perindopril Coversyl furosemide Lasix spironolactone clopidogrel Plavix "
                 "salbutamol Ventolin fluticasone Flovent Advair Symbicort budesonide tiotropium "
                 "Spiriva montelukast Singulair prednisone allopurinol gabapentin Neurontin "
                 "pregabalin Lyrica sertraline Zoloft citalopram escitalopram Cipralex "
                 "venlafaxine Effexor duloxetine Cymbalta bupropion Wellbutrin mirtazapine "
                 "trazodone quetiapine Seroquel lorazepam Ativan clonazepam zopiclone tamsulosin "
                 "Flomax finasteride alendronate Fosamax donepezil Aricept memantine "
                 "amoxicillin azithromycin ciprofloxacin cephalexin nitrofurantoin "
                 "hydromorphone oxycodone tramadol acetaminophen Tylenol celecoxib Celebrex "
                 "naproxen estradiol levonorgestrel tamoxifen letrozole Trulicity dulaglutide "
                 "Rybelsus Wegovy Mounjaro tirzepatide Forxiga dapagliflozin gliclazide "
                 "Diamicron Lantus Tresiba Humalog NovoRapid Eltroxin Altace Norvasc "
                 "metformine atorvastatine rosuvastatine lévothyroxine insuline warfarine "
                 "sémaglutide gabapentine prégabaline lorazépam acétaminophène "
                 "amoxicilline").split()
        phrases = ["My blood pressure is up", "Blood sugar was 14 this morning",
                   "Mon taux de glycémie est bas", "The A1C came back at 8.2"]
        r = self.py("""
            import grounding as g
            out({"words": {w: g.sensitivity("I take " + w + " now") for w in %r},
                 "phrases": {p: g.sensitivity(p) for p in %r},
                 "plain": [g.sensitivity(t) for t in ("I take the bus now",
                                                      "I like my coffee black")]})
        """ % (names, phrases))
        self.assertGreaterEqual(len(names), 140)
        self.assertEqual([w for w, k in r["words"].items() if "health" not in k], [])
        self.assertEqual([p for p, k in r["phrases"].items() if "health" not in k], [])
        self.assertEqual(r["plain"], [[], []])


# ========================================================================= F3
class F3ASearchMatchesOnlyWhatWouldBeShown(HisOwnTest):
    """v1 D3: with 'Netflix password: Bluebird77' kept by the owner,
    explain_basis(topic='Bluebird77') from claude-raw returned the hidden
    fact with match_reason 'it mentions bluebird77' — a guessed password,
    confirmed. A topic search matches only the text release would show."""

    def test_a_guessed_password_finds_nothing_on_any_surface(self):
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            h, c = http()
            with access.owner_console():
                m.conscience.remember_fact("Netflix password: Bluebird77", "general")
                m.conscience.remember_fact("The garage code is 4821", "general")
                m.life.add_memory("We set the Netflix password to Bluebird77 that night",
                                  visibility="family")
            m.conscience.refresh()
            res = {}
            for topic in ("Bluebird77", "bluebird77", "Bluebird", "4821", "Bluebird78"):
                for cl in ("claude-raw", "jefferey"):
                    e = mcp_as(m, cl, "explain_basis", {"topic": topic})
                    res[f"mcp {cl} {topic}"] = [len(e.get("facts", [])), e.get("held_back")]
                res[f"http {topic}"] = len(c.get("/basis", params={"topic": topic},
                                                 headers=H(TA)).json().get("facts", []))
                res[f"terminal {topic}"] = len(term("explain_basis", {"topic": topic})
                                               .get("facts", []))
                res[f"story {topic}"] = len(mcp_as(m, "jefferey", "tell_story",
                                                   {"theme": topic}).get("moments", []))
            e = mcp_as(m, "claude-raw", "explain_basis", {"topic": "the Netflix password"})
            res["netflix"] = [f["fact"] for f in e.get("facts", [])]
            out(res)
        """)
        netflix = r.pop("netflix")
        self.assertEqual({k: v for k, v in r.items() if v not in (0, [0, None])}, {})
        self.assertEqual(len(netflix), 1)
        self.assertNotIn("Bluebird77", netflix[0])
        self.assertIn("Netflix password", netflix[0])

    def test_forgetting_by_a_guessed_password_finds_nothing_either(self):
        # the same oracle through forget(contains=…): an engine's words match
        # only what would leave the house
        r = self.py("""
            import jefferey_mcp as m
            with access.owner_console():
                m.conscience.remember_fact("Netflix password: Bluebird77", "general")
            m.conscience.refresh()
            out([mcp_as(m, "jefferey", "forget", {"contains": w}).get("count", 0)
                 for w in ("Bluebird77", "Netflix")])
        """)
        self.assertEqual(r, [0, 1])

    def test_jefferey_never_hides_its_own_code_as_a_note(self):
        # v1 new_regressions D3 [LOW]: forget's how_to_finish hid its own code
        # ('types the code [hidden: a number in a note that mentions a code]')
        # in 4 runs of 6, whenever the code mixed letters and digits
        r = self.py("""
            import jefferey_mcp as m
            with access.owner_console():
                for i in range(5):
                    m.conscience.remember_fact(f"Anna likes tulips number {i}", "general")
            m.conscience.refresh()
            runs = []
            for k in range(12):
                x = mcp_as(m, "jefferey", "forget", {"contains": "tulips"})
                runs.append([x.get("confirm"), x.get("how_to_finish", "")])
            out(runs)
        """)
        for code, how in r:
            self.assertTrue(code and "hidden" not in code, (code, how))
            self.assertIn(f"/approve {code}", how)
            self.assertNotIn("[hidden", how)


# ========================================================================= F5
F5_FACTS = [
    "jo is on chemo for her breast cancer, started last week at the general",
    "ED HAS MS AND USES A CANE SINCE 2019 WHEN HE WAS DIAGNOSED",
    "TY WENT BACK TO REHAB AFTER HIS RELAPSE LAST MONTH",
    "Bo has MS", "Al is on chemo", "Li has HIV", "wu is bipolar",
    "my friend dana reyes has lupus",
]
# (draft to 'the neighbours', caught?)
F5_DRAFTS: list[tuple[str, bool]] = [
    # v2 D6 unsafe_cases: the fact typed in small letters or all capitals
    ("Jo is on chemo", True), ("jo has cancer", True), ("Jo has breast cancer", True),
    ("Ed has MS", True), ("ed has ms", True), ("Ty is in rehab", True),
    # ...the abbreviation written another way
    ("bo has m.s", True), ("Bo has M.S", True), ("Bo has M. S.", True), ("Bo has M S", True),
    ("Bo has M-S", True), ("Bo has multiple sclerosis", True),
    # ...the full word, slang and look-alike letters
    ("al is having chemotherapy", True), ("Al started chemotherapy", True),
    ("li is poz", True), ("Lі has HІV", True),
    # a name he recorded, with a word of the fact or of the health lexicon
    ("Dana has lupus", True), ("Dana Reyes had surgery", True),
    # ordinary drafts still pass
    ("Al dente pasta for Bo tonight", False), ("See you Sunday, Li", False),
    ("Ms Wu called about the church sale", False), ("Thanks for the casserole, Jo", False),
    ("Ed fixed the fence", False), ("Is Ty coming to the game?", False),
    ("Dana, the roses look lovely", False),
]


class F5ADraftNamesThePersonInAnyCase(HisOwnTest):

    def test_every_draft_the_skeptic_wrote(self):
        r = self.py("""
            import jefferey_chat as jc
            with access.owner_console():
                jc.life.add_person("Dana Reyes", "friend")
                for f in %r:
                    jc.conscience.remember_fact(f, "health")
            jc.conscience.refresh()
            out([term("check_draft", {"text": t, "audience": "the neighbours"})
                 for t, _ in %r])
        """ % (F5_FACTS, F5_DRAFTS))
        wrong = [(t, x["ok"], x.get("problems")) for (t, caught), x in zip(F5_DRAFTS, r)
                 if x["ok"] == caught]
        self.assertEqual(wrong, [], "\n".join(map(repr, wrong)))

    def test_mcp_and_http_read_a_draft_the_same_way(self):
        r = self.py("""
            import jefferey_mcp as m
            h, c = http()
            with access.owner_console():
                m.conscience.remember_fact(%r, "health")
            m.conscience.refresh()
            out([mcp_as(m, "jefferey", "check_draft", {"text": "Jo has breast cancer",
                                                       "audience": "the neighbours"})["ok"],
                 c.post("/draft-check", json={"text": "jo has cancer",
                                               "audience": "the neighbours"},
                        headers=H(TA)).json().get("ok")])
        """ % (F5_FACTS[0],))
        self.assertEqual(r, [False, False])


if __name__ == "__main__":
    unittest.main()
