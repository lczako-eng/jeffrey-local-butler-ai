"""
Frozen corpus — who a 'no' is for (R2), repair round 6, and the round-7
decisions (D1).

Round 4 grew a list of ways to say 'anyone'; round 5 made every 'no' whose
audience it did not recognise a no for everyone — and that blinded his own
caretaker AI and overrode his own yes. This file freezes every audience the
round-4 and round-5 skeptics reported, with the outcome the product's
principles ask for.

The structural rules it holds his rules to:

  * A 'no' NEVER applies to the owner's own keys — his own console and his
    caretaker key 'jefferey'. His own agent always sees his life; his rules
    about who may hear what govern everyone else.
  * A 'no' names exactly its audience (every way that audience is written:
    'Karen Novak' is also 'Karen' and 'my ex-wife'), except that an explicit
    anyone-word — anyone, everyone, the public, members of the public, the
    world, nobody, people, les gens, tout le monde, quiconque, n'importe qui
    … with or without 'the', alone or beside other names — means every
    audience other than his own keys. A name that merely contains such a
    word ('Le Monde', 'Mr. Nobody') is a name.

Round 7 (D1) — rules that name an AI bind every engine key:

  * A 'no' whose audience names an AI, an engine or the company behind one
    (AI, any AI, artificial intelligence, a chatbot, the assistant, ChatGPT,
    GPT, OpenAI, Claude, Anthropic, Gemini, Google, Bard, Copilot,
    Microsoft, Llama, Meta, Hermes, the cloud, IA, l'IA …) holds for EVERY
    key that reaches an engine — his own caretaker key 'jefferey' too. Only
    the owner himself, at his own keyboard, still sees it. Round 6 let his
    caretaker read what he had said no AI may hear (the convergence
    skeptics' HIGH regression), and kept a 'no for Gemini' or 'Google' from
    nobody but a key of that name: both are AIs, so both now hold for every
    engine key.
  * A 'no' that names people ('anyone', 'the public', 'Bob') still never
    binds his caretaker: his own agent sees his life so it can look after
    him. To keep something from it too, he says no to 'any AI'.
  * A 'no' for his family or for the people who read through the family key
    (my family, ma famille, la famille, my kids, my children, mes enfants,
    the grandchildren, my relatives, my daughter, my son, ma fille, mon
    fils) holds for the family key.
  * Lower-case 'le monde' is everyone; 'Le Monde', with its capital M, is the
    newspaper.

Round 8 (F1) — an audience no one knows is everyone. Round 7 still let a
'no' for an audience it did not recognise ('Le Monde', 'Bob', 'my lawyer',
'Joe Everyone', 'the press') bind only a reader of that very name, and a no
for 'JEFFEREY', 'the local model', 'Сlaude' (a Cyrillic С), 'AI's' or
'claude-raw' bound nobody at all (roundD_verdicts.json v1 D1 cases 2, 3, 5
and new_regressions). Now:

  * Every audience is read through the shared fold (grounding.fold):
    look-alike letters, digits for letters, spaced-out letters, hyphens and
    possessives are read as the word they spell.
  * A 'no' whose audience — or any part of it before 'but', 'except' or
    'other than' — is not a person he recorded himself, not one of his keys'
    names, and not a group (an anyone-word, a family word, an AI word) holds
    for EVERYONE AND EVERY AI, his own JEFFEREY too, and set_rule says so:
    "I don't know who 'my lawyer' is, so this no holds for everyone and every
    AI. Add them to your people to make it narrower." Rows that round 7 read
    as EXACT ('Le Monde', 'Bob', 'my lawyer', 'the neighbours' …) are UNKNOWN
    now, and an anyone-word beside a name nobody knows ('the public or the
    press') holds for every AI too (AI_ALL). With the person recorded at his
    own console, the same audiences bind only that person (RECORDED below).
    A person an AI wrote down never makes a no narrower.
  * AI words also cover JEFFEREY, Jefferey, Jeffrey, the butler, the
    (local) model, Ollama, the computer, l'ordinateur, les machines, Alexa,
    Siri, Mistral, Le Chat and the readers' own engine names.
  * Family words are every kinship word in English and French, with in-law,
    step-, grand-, great-, belle-, beau-, demi- and petit(e)-; a no for one
    binds the family key, and the person he recorded with that relationship.
    A possessive or a 'de' ('my son's teacher', 'la femme de ménage') is
    someone else, nobody he knows.
  * A YES still never widens past what is written.

Outcomes, for a 'no' about his health with this audience:
  EVERYONE  the family key no longer reads his diabetes; set_rule says it
            holds for everyone
  EXACT     the family key still reads it (the no is for someone else)
  FAMILY    the family key no longer reads it (the no names the family)
  AI        neither the family key nor his caretaker key reads it; set_rule
            says it holds for every AI
  AI_ALL    both: an anyone-word and an AI ('the public and ChatGPT'), or an
            anyone-word and a name nobody knows ('the public or the press')
  UNKNOWN   nobody knows who it is: everyone and every AI (round 8, F1)
His caretaker key 'jefferey' still reads it, except for AI, AI_ALL and
UNKNOWN.
"""

from __future__ import annotations

import json
import unittest

from test_life import LifeTest, TA, TF

EVERYONE, EXACT, FAMILY, AI, AI_ALL = "everyone", "exact", "family", "ai", "ai+everyone"
UNKNOWN = "nobody knows them"
HOLDS_FOR = {EVERYONE: "everyone", AI: "every AI", AI_ALL: "everyone and every AI",
             UNKNOWN: "everyone and every AI"}

AUDIENCES: list[tuple[str, str]] = [
    # round 4, verify-b/c: the ways of saying 'anyone' (ANoForThePublicIsANoForEveryone)
    ("anyone", EVERYONE), ("everyone", EVERYONE), ("everybody", EVERYONE), ("anybody", EVERYONE),
    ("all", EVERYONE), ("the world", EVERYONE), ("world", EVERYONE), ("the public", EVERYONE),
    ("public", EVERYONE), ("The Public", EVERYONE), ("the World.", EVERYONE),
    ("others", EVERYONE), ("the others", EVERYONE), ("other people", EVERYONE),
    ("everyone else", EVERYONE), ("people", EVERYONE), ("the people", EVERYONE),
    ("strangers", EVERYONE), ("tout le monde", EVERYONE), ("les autres", EVERYONE),
    ("n'importe qui", EVERYONE), ("tous", EVERYONE), ("general public", EVERYONE),
    ("the general public", EVERYONE), ("le grand public", EVERYONE),
    # round 4 verify-b: wordings that named nobody
    ("members of the public", EVERYONE), ("the entire world", EVERYONE),
    ("anyone at all", EVERYONE), ("all people", EVERYONE), ("every person", EVERYONE),
    ("everyone in the world", EVERYONE), ("the world at large", EVERYONE),
    ("anyone who asks", EVERYONE), ("les gens", EVERYONE), ("quiconque", EVERYONE),
    ("le monde entier", EVERYONE), ("tout le monde sauf moi", EVERYONE),
    # round 5 verify-b: an anyone-word beside other names (round 8, F1: a
    # name nobody knows beside it makes it a no for every AI as well)
    ("the public or the press", AI_ALL), ("the public and the media", AI_ALL),
    ("le grand public et les journalistes", AI_ALL), ("the neighbours and the public", AI_ALL),
    ("le public et la banque", AI_ALL), ("the general public, the bank", AI_ALL),
    ("outsiders, the bank and the press", AI_ALL), ("nobody but my doctor", EVERYONE),
    ("people other than my doctor", EVERYONE), ("social media", EVERYONE),
    # ...and the rest of that skeptic's list (p/r2.py)
    ("strangers and the newspapers", AI_ALL), ("the world and his doctor", AI_ALL),
    ("no one", EVERYONE), ("nobody", EVERYONE), ("personne", EVERYONE), ("aucun", EVERYONE),
    ("no-one at all", EVERYONE), ("the internet", EVERYONE),
    ("the church and everybody", AI_ALL), ("any stranger", EVERYONE), ("folks", EVERYONE),
    ("everyone except the family", EVERYONE), ("all but Anna", EVERYONE),
    ("mon voisin et le public", AI_ALL), ("le public, les voisins", AI_ALL),
    # a name that holds such a word is a name (round 4 verify-c: 'Le Monde'),
    # and a name nobody knows is everyone and every AI (round 8, F1)
    ("Le Monde", UNKNOWN), ("Monde", UNKNOWN), ("Mr. Nobody", UNKNOWN), ("Mrs. World", UNKNOWN),
    ("Joe Public", UNKNOWN), ("Facebook", UNKNOWN),
    # round 5 verify-c: plain audiences that round 5 made 'everyone'
    # (round 7, D1: 'Gemini' and 'Google' name an AI, so a no for them holds
    # for every engine key, his own too — round 6 held them only from a key
    # of that name)
    ("Bob", UNKNOWN), ("my GP", UNKNOWN), ("my cardiologist", UNKNOWN), ("my oncologist", UNKNOWN),
    ("Gemini", AI), ("Google", AI), ("the VA", UNKNOWN), ("the CRA", UNKNOWN),
    ("Revenue Canada", UNKNOWN), ("the mailman", UNKNOWN), ("my hairdresser", UNKNOWN),
    ("Karen", UNKNOWN), ("Bob Smith", UNKNOWN), ("my brother Mike", FAMILY),
    # round 5 ANoForNobodyPlainIsANoForEveryone: plain ones stay plain —
    # until round 8 (F1): unrecorded, they are nobody he knows; 'my sister' is
    # a family word
    ("the neighbours", UNKNOWN), ("my sister", FAMILY), ("the bank", UNKNOWN), ("Mrs. Patel", UNKNOWN),
    # a no that names the family is a no for the family key
    ("family", FAMILY), ("the family", FAMILY), ("my family", FAMILY),
    # ---------------------------------------------------------- round 7 (D1)
    # convergence skeptic vb R2 [HIGH]: a no that names the engine no longer
    # held for his own key (sk7/r2.py, r2c.py); vc R2: the same for 'AI
    # engines' (sk6/s_r2b.py)
    ("ChatGPT", AI), ("OpenAI", AI), ("any AI", AI), ("AI", AI), ("claude", AI),
    ("Claude", AI), ("the AI", AI), ("anthropic", AI), ("Anthropic", AI), ("AI engines", AI),
    # vb R2 remaining: not taken as a no to the AI on any snapshot
    ("chatbots", AI), ("l'IA", AI), ("robots", AI), ("artificial intelligence", AI),
    # the rest of the decision's list, with and without little words
    ("a chatbot", AI), ("the assistant", AI), ("GPT", AI), ("Bard", AI), ("Copilot", AI),
    ("Microsoft", AI), ("Llama", AI), ("Meta", AI), ("Hermes", AI), ("the cloud", AI),
    ("IA", AI), ("l'intelligence artificielle", AI), ("any chatbot", AI),
    ("the public and ChatGPT", AI_ALL), ("anyone, AI included", AI_ALL),
    # vb R2 [MEDIUM] regression: lower-case 'le monde' named only itself
    ("le monde", EVERYONE), ("Le monde", EVERYONE),
    # vb R2 [MEDIUM, against r5]: holds_for was the literal text and the
    # family key read his diabetes
    ("absolutely anyone", EVERYONE), ("literally anyone", EVERYONE), ("a soul", EVERYONE),
    ("not a soul", EVERYONE), ("qui que ce soit", EVERYONE), ("les étrangers", EVERYONE),
    ("the general population", EVERYONE), ("tout un chacun", EVERYONE),
    ("n'importe lequel", EVERYONE), ("the masses", EVERYONE), ("outside people", EVERYONE),
    ("les gens du village", EVERYONE),
    # vb R2 remaining: a no for the family in French, or for the people who
    # use the family key, never reached it
    ("ma famille", FAMILY), ("la famille", FAMILY), ("my kids", FAMILY), ("the kids", FAMILY),
    ("my children", FAMILY), ("the grandchildren", FAMILY), ("my grandkids", FAMILY),
    ("my relatives", FAMILY), ("relatives", FAMILY), ("mes enfants", FAMILY),
    ("my daughter", FAMILY), ("my son", FAMILY), ("ma fille", FAMILY), ("mon fils", FAMILY),
    ("grandchildren", FAMILY),
    # ...and 'his son's teacher' is the teacher (nobody he knows, round 8)
    ("my son's teacher", UNKNOWN),
    # convergence vb/vc R2 evidence: fixed in round 6, kept fixed
    ("any person", EVERYONE), ("noone", EVERYONE), ("personne d'autre", EVERYONE),
    ("everyone on Facebook", EVERYONE), ("all and sundry", EVERYONE),
    ("anyone but Anna", EVERYONE), ("the press and anyone else", AI_ALL),
    ("whoever asks", EVERYONE), ("Nobody.", EVERYONE), ("toute personne", EVERYONE),
    ("my lawyer", UNKNOWN), ("Joe Everyone", UNKNOWN), ("Dr Wu", UNKNOWN),
    # ---------------------------------------------------------- round 8 (F1)
    # v1 D1 case 2: a no that names JEFFEREY or the machine held back from no AI
    ("Jefferey", AI), ("JEFFEREY", AI), ("Jeffrey", AI), ("the butler", AI),
    ("the local model", AI), ("my local model", AI), ("the model", AI), ("Ollama", AI),
    ("the computer", AI), ("computers", AI), ("my computer", AI), ("l'ordinateur", AI),
    ("les machines", AI), ("Alexa", AI), ("Siri", AI), ("Mistral", AI),
    # v1 D1 case 3: look-alike and variant spellings bound nobody
    ("\u0421hatGPT", AI), ("\u0421laude", AI), ("\u0410I", AI), ("\u0391\u0399", AI),
    ("Chat-GPT", AI), ("A I", AI), ("C l a u d e", AI), ("Cl4ude", AI), ("gpt4o", AI),
    ("Le Chat", AI), ("les intelligences artificielles", AI),
    ("\uff23\uff2c\uff21\uff35\uff24\uff25", AI), ("\u1d04\u029f\u1d00\u1d1c\u1d05\u1d07", AI),
    # v1 new_regressions D1 [MEDIUM]: held back on 6bdad7f, not on round 7
    ("AI's", AI), ("AI-powered apps", AI), ("claude-raw", AI),
    # v1 D1 case 5: family members outside round 7's list
    ("my wife", FAMILY), ("ma soeur", FAMILY), ("ma s\u0153ur", FAMILY), ("my brother", FAMILY),
    ("my nephew", FAMILY), ("the in-laws", FAMILY), ("my daughter-in-law", FAMILY),
    ("ma belle-fille", FAMILY), ("my stepson", FAMILY), ("my husband", FAMILY),
    ("my mother", FAMILY), ("mon fr\u00e8re", FAMILY), ("mon beau-p\u00e8re", FAMILY),
    ("ma petite-fille", FAMILY), ("my great-grandson", FAMILY), ("mes parents", FAMILY),
    # ...and a possessive or a 'de' is someone else: nobody he knows
    ("la femme de m\u00e9nage", UNKNOWN), ("Karen's husband", UNKNOWN),
]

# Round 8 (F1): the same audiences, once he has recorded who they are at his
# own console, bind only that person — his rules about people never bind his
# own JEFFEREY, so his caretaker and the family key still read his diabetes.
RECORDED_PEOPLE = [("Bob", "friend"), ("Dr. Amira Haddad", "GP"), ("Dana Reyes", "lawyer"),
                   ("Karen Novak", "ex-wife"), ("Mrs. Patel", "neighbour"),
                   ("Le Monde", "newspaper"), ("Joe Everyone", "friend"), ("Dr Wu", "doctor")]
RECORDED: list[str] = ["Bob", "my GP", "my lawyer", "Karen", "Karen Novak",
                       "Mrs. Patel", "Le Monde", "Joe Everyone", "Dr Wu"]

LOOP = """
import access
auds = %r
h, c = http()
import jefferey_mcp as m
seen = {}
for a in auds:
    with access.owner_console():
        h.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
        said = h.rules.set_rule("disclosure", "health", "Never tell my health to " + a,
                                audience=a, allow=False)
    m.conscience.refresh()
    seen[a] = {"said": said.get("holds_for"),
               "http": [x["text"] for x in c.get("/life", headers=H(%s)).json()["moments"]],
               "mcp": [x["text"] for x in mcp_call(m, "who_am_i")["moments"]]}
out(seen)
"""

SETUP = """
import access, jefferey_chat as jc
with access.owner_console():
    jc.life.add_memory("Diagnosed with type 2 diabetes in June.", visibility="family")
    jc.life.add_memory("The orb made her laugh.", visibility="family")
    jc.life.add_memory("We drove to the lake every July.", visibility="family")
    jc.conscience.remember_fact("Anna calls on Sundays")
out(1)
"""

DIABETES = "Diagnosed with type 2 diabetes in June."


class WhoANoIsFor(LifeTest):

    def test_every_audience_the_skeptics_named(self):
        self.py(SETUP)
        auds = [a for a, _ in AUDIENCES]
        fam = self.py(LOOP % (auds, "TF"), JEFFEREY_CLIENT="family")
        own = self.py(LOOP % (auds, "TA"), JEFFEREY_CLIENT="jefferey")
        bad = []
        for a, want in AUDIENCES:
            f, o = fam[a], own[a]
            why = []
            for where in ("http", "mcp"):
                own_held = DIABETES not in o[where]
                if own_held != (want in (AI, AI_ALL, UNKNOWN)):
                    why.append(f"his own key ({where}) {'held' if own_held else 'reads it'}")
                if "The orb made her laugh." not in f[where]:
                    why.append(f"the family key ({where}) lost an unrelated moment")
                if "The orb made her laugh." not in o[where]:
                    why.append(f"his own key ({where}) lost an unrelated moment")
                held = DIABETES not in f[where]
                if held != (want != EXACT):
                    why.append(f"family key ({where}) {'held' if held else 'reads it'}")
            if f["said"] != HOLDS_FOR.get(want, f["said"]) or (
                    want not in HOLDS_FOR and f["said"] in HOLDS_FOR.values()):
                why.append(f"set_rule said holds_for={f['said']!r}")
            if why:
                bad.append((a, want, why))
        self.assertEqual(bad, [], "\n" + "\n".join(map(str, bad)))

    def test_a_no_for_bob_blinds_nobody_else(self):
        # round 5 verify-c, repro A: an untagged 'Never tell Bob anything'
        # blanked every moment and fact for his own Claude and the family key.
        # Round 8 (F1): that holds once he has recorded who Bob is (and who his
        # GP is) at his own console; before that, nobody knows who Bob is, so
        # the no holds for everyone and every AI, and set_rule says so.
        self.py(SETUP)
        res = {}
        for recorded in (True, False):
            for a in ("Bob", "my GP"):
                r = self.py("""
                    import access
                    h, c = http()
                    with access.owner_console():
                        h.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                        h.conscience.save_fresh(lambda d: d.__setitem__("people", []))
                        h.conscience.refresh()
                        if %r:
                            h.life.add_person("Bob", "friend")
                            h.life.add_person("Dr. Amira Haddad", "GP")
                        said = h.rules.set_rule("disclosure", "", "Never tell %s anything",
                                                audience=%r, allow=False)
                    import jefferey_mcp as m
                    m.conscience.refresh()
                    who = mcp_call(m, "who_am_i")
                    con = mcp_call(m, "get_conscience")
                    out({"moments": len(who["moments"]), "facts": len(con.get("facts", [])),
                         "family": len(c.get("/life", headers=H(TF)).json()["moments"]),
                         "own_http": len(c.get("/life", headers=H(TA)).json()["moments"]),
                         "holds_for": said.get("holds_for"), "note": said.get("note")})
                """ % (recorded, a, a), JEFFEREY_CLIENT="jefferey")
                res[(recorded, a)] = r
        for (recorded, a), r in res.items():
            got = {k: r[k] for k in ("moments", "facts", "family", "own_http")}
            if recorded:
                self.assertEqual(got, {"moments": 3, "facts": 1, "family": 3, "own_http": 3}, a)
                self.assertNotEqual(r["holds_for"], "everyone and every AI", a)
            else:
                self.assertEqual(got, {"moments": 0, "facts": 0, "family": 0, "own_http": 0}, a)
                self.assertEqual(r["holds_for"], "everyone and every AI", a)
                self.assertIn(f"I don't know who '{a}' is", r["note"])

    def test_a_no_for_someone_he_recorded_binds_only_them(self):
        # round 8 (F1): with the person recorded at his own console, a no that
        # round 8 reads as UNKNOWN binds only that person again
        self.py(SETUP)
        self.py("""
            import access, jefferey_chat as jc
            with access.owner_console():
                for name, rel in %r:
                    jc.life.add_person(name, rel)
            out(1)
        """ % (RECORDED_PEOPLE,))
        fam = self.py(LOOP % (RECORDED, "TF"), JEFFEREY_CLIENT="family")
        own = self.py(LOOP % (RECORDED, "TA"), JEFFEREY_CLIENT="jefferey")
        bad = [(a, fam[a]["said"]) for a in RECORDED
               if fam[a]["said"] in HOLDS_FOR.values()
               or any(DIABETES not in x[w] for x in (fam[a], own[a]) for w in ("http", "mcp"))]
        self.assertEqual(bad, [])

    def test_a_no_for_bob_never_overrides_his_yes_for_anyone_else(self):
        # round 5 verify-c, repro C — with Bob recorded (round 8, F1); before
        # he is, nobody knows who Bob is, and the no holds for everyone: a yes
        # for anyone never widens past it
        r = self.py("""
            import access, jefferey_chat as jc
            res = {}
            for recorded in (True, False):
                with access.owner_console():
                    jc.conscience.save_fresh(lambda d: d.update(rules=[], people=[]))
                    jc.conscience.refresh()
                    if recorded:
                        jc.life.add_person("Bob", "friend")
                    jc.rules.set_rule("disclosure", "army", "Anyone can hear my army stories",
                                      audience="anyone", allow=True)
                    jc.rules.set_rule("disclosure", "army", "Don't tell Bob my army stories",
                                      audience="Bob", allow=False)
                res[str(recorded)] = {a: jc.rules.check_disclosure(a, "army")["allowed"]
                                      for a in ("a neighbour", "my daughter", "family",
                                                "claude", "Bob")}
            out(res)
        """)
        self.assertEqual(r["True"], {"a neighbour": True, "my daughter": True, "family": True,
                                     "claude": True, "Bob": False})
        self.assertEqual(set(r["False"].values()), {False}, r["False"])

    def test_a_no_for_any_ai_holds_for_his_own_key_too(self):
        # round 7, D1 (convergence vb/vc R2, HIGH): round 6 kept his no for
        # an AI from every key but the AI he named — his caretaker. Now it
        # holds for every key that reaches an engine; only he, at his own
        # keyboard, still sees it.
        self.py(SETUP)
        auds = ["claude", "any AI", "anthropic", "ChatGPT", "OpenAI", "AI", "the AI"]
        fam = self.py(LOOP % (auds, "TF"), JEFFEREY_CLIENT="family")
        own = self.py(LOOP % (auds, "TA"), JEFFEREY_CLIENT="jefferey")
        for a in auds:
            for where in ("mcp", "http"):
                self.assertNotIn(DIABETES, own[a][where], (a, where))
                self.assertNotIn(DIABETES, fam[a][where], (a, where))
                self.assertIn("The orb made her laugh.", own[a][where], (a, where))
            self.assertEqual(own[a]["said"], "every AI", a)

    def test_a_no_for_any_ai_holds_on_the_terminal_and_for_a_model_in_the_house(self):
        # D1: every key that reaches an engine — the terminal's caretaker on a
        # rented engine and on a model on this Mac — and every tool that
        # reads his facts; the owner at his own keyboard still sees it all
        r = self.py("""
            import access, jefferey_chat as jc
            with access.owner_console():
                jc.conscience.remember_fact("I have type 2 diabetes", "health")
                jc.conscience.remember_fact("Anna calls on Sundays")
                jc.rules.set_rule("disclosure", "health", "Never tell any AI about my health",
                                  audience="any AI", allow=False)
            rented = {"basis": jc.dispatch_tool("explain_basis", {"topic": "my diabetes"}),
                      "facts": jc.conscience.snapshot(30, 0, 15)}
            jc.egress.bind("chat", engine=jc.local_engine_label("hermes3",
                                                                "http://127.0.0.1:9/v1"))
            house = {"basis": jc.dispatch_tool("explain_basis", {"topic": "my diabetes"}),
                     "facts": jc.conscience.snapshot(30, 0, 15),
                     "in_house": jc.egress.in_the_house()}
            with access.owner_console():
                mine = jc.conscience.owner_view()
            out({"rented": rented, "house": house,
                 "mine": [f["fact"] for f in mine["facts"]]})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertTrue(r["house"]["in_house"])
        for where in ("rented", "house"):
            sent = json.dumps(r[where])
            self.assertNotIn("diabetes", sent.replace("my diabetes", ""), where)
            self.assertIn("Anna calls on Sundays", json.dumps(r[where]["facts"]), where)
        self.assertIn("I have type 2 diabetes", r["mine"])

    def test_check_disclosure_reads_the_family_and_the_ai_the_same_way(self):
        # vb R2 remaining: with a yes for anyone plus a no for 'ma famille',
        # 'la famille' or 'my grandchildren', check_disclosure('family') was
        # True; and a no for any AI must hold when asked about any AI
        r = self.py("""
            import access, jefferey_chat as jc
            res = {}
            for no in ("ma famille", "la famille", "my grandchildren", "mes enfants",
                       "any AI", "ChatGPT"):
                with access.owner_console():
                    jc.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                    jc.conscience.refresh()
                    jc.rules.set_rule("disclosure", "health", "Anyone may know",
                                      audience="anyone", allow=True)
                    jc.rules.set_rule("disclosure", "health", "But not " + no,
                                      audience=no, allow=False)
                res[no] = {a: jc.rules.check_disclosure(a, "health")["allowed"]
                           for a in ("family", "claude", "chatgpt", "a neighbour")}
            out(res)
        """)
        for no in ("ma famille", "la famille", "my grandchildren", "mes enfants"):
            self.assertEqual(r[no], {"family": False, "claude": True, "chatgpt": True,
                                     "a neighbour": True}, no)
        for no in ("any AI", "ChatGPT"):
            self.assertEqual(r[no], {"family": True, "claude": False, "chatgpt": False,
                                     "a neighbour": True}, no)

    def test_le_monde_is_the_newspaper_only_with_its_capital(self):
        # D1: lower-case 'le monde' is everyone, 'Le Monde' the newspaper —
        # however he types it into whichever surface. Round 8 (F1): a
        # newspaper he has not recorded is nobody he knows, so 'Le Monde'
        # holds for everyone and every AI until he records it.
        r = self.py("""
            import access, jefferey_chat as jc
            res = {}
            for recorded in (False, True):
                with access.owner_console():
                    if recorded:
                        jc.life.add_person("Le Monde", "newspaper")
                    for a in ("le monde", "Le Monde", "LE MONDE", "tout le monde"):
                        res[f"{a} {recorded}"] = jc.rules.set_rule(
                            "disclosure", "health", "Never tell " + a, audience=a,
                            allow=False)["holds_for"]
            out(res)
        """)
        self.assertEqual(r, {"le monde False": "everyone", "Le Monde False": "everyone and every AI",
                             "LE MONDE False": "everyone", "tout le monde False": "everyone",
                             "le monde True": "everyone", "Le Monde True": "le monde",
                             "LE MONDE True": "everyone", "tout le monde True": "everyone"})

    def test_a_yes_that_names_someone_opens_nothing_to_anyone_else(self):
        # convergence vb R2 evidence: on the yes side nothing opened wrongly
        r = self.py("""
            import access, jefferey_chat as jc
            res = {}
            for a in ("anyone except Karen", "the public library", "Le Monde", "nobody",
                      "le monde"):
                with access.owner_console():
                    jc.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                    jc.conscience.refresh()
                    jc.rules.set_rule("disclosure", "recipes", "Yes for " + a, audience=a,
                                      allow=True)
                res[a] = jc.rules.check_disclosure("my sister", "recipes")["allowed"]
            out(res)
        """)
        self.assertEqual(set(r.values()), {False}, r)

    def test_a_yes_for_le_monde_opens_nothing_to_anyone_else(self):
        r = self.py("""
            import access, jefferey_chat as jc
            with access.owner_console():
                jc.rules.set_rule("disclosure", "recipes", "Le Monde may print my recipes",
                                  audience="Le Monde", allow=True)
            out({"other": jc.rules.check_disclosure("my sister", "recipes")["allowed"],
                 "them": jc.rules.check_disclosure("le monde", "recipes")["allowed"]})
        """)
        self.assertEqual(r, {"other": False, "them": True})

    def test_holds_for_reads_the_same_on_every_surface(self):
        auds = ("the public or the press", "Bob", "nobody but my doctor")
        said = {}
        for surface in ("terminal", "mcp", "http"):
            said[surface] = self.py("""
                import access
                surface, res = %r, {}
                for a in %r:
                    rule = {"kind": "disclosure", "tags": "health", "instruction": "never " + a,
                            "audience": a, "allow": False}
                    if surface == "terminal":
                        import jefferey_chat as jc
                        with access.owner_console():
                            jc.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                        jc.conscience.refresh()
                        set_ = jc.dispatch_tool("set_rule", rule)
                        listed = jc.dispatch_tool("list_rules", {})
                    elif surface == "mcp":
                        import jefferey_mcp as m
                        with access.owner_console():
                            m.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                        m.conscience.refresh()
                        set_ = mcp_call(m, "set_rule", rule)
                        m.conscience.refresh()
                        listed = mcp_call(m, "list_rules")
                    else:
                        h, c = http()
                        with access.owner_console():
                            h.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                        h.conscience.refresh()
                        set_ = c.post("/rules", json=rule, headers=H(TA)).json()
                        listed = c.get("/rules", headers=H(TA)).json()
                    if isinstance(listed, dict):     # one rule comes back on its own
                        listed = [listed] if "kind" in listed else listed.get("rules", [])
                    res[a] = [set_.get("holds_for"), [x.get("holds_for") for x in listed]]
                out(res)
            """ % (surface, auds), JEFFEREY_CLIENT="jefferey")
        # round 8 (F1): nobody knows who 'the press' or 'Bob' is, so those
        # hold for everyone and every AI ('but my doctor' is who may hear it)
        for surface, res in said.items():
            self.assertEqual(res["the public or the press"],
                             ["everyone and every AI", ["everyone and every AI"]], surface)
            self.assertEqual(res["nobody but my doctor"], ["everyone", ["everyone"]], surface)
            self.assertEqual(res["Bob"], ["everyone and every AI", ["everyone and every AI"]],
                             surface)


if __name__ == "__main__":
    unittest.main()
