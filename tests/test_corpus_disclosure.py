"""
Frozen corpus — who a 'no' is for (R2), repair round 6.

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
    'Karen Czako' is also 'Karen' and 'my ex-wife'), except that an explicit
    anyone-word — anyone, everyone, the public, members of the public, the
    world, nobody, people, les gens, tout le monde, quiconque, n'importe qui
    … with or without 'the', alone or beside other names — means every
    audience other than his own keys. A name that merely contains such a
    word ('Le Monde', 'Mr. Nobody') is a name.

Outcomes, for a 'no' about his health with this audience:
  EVERYONE  the family key no longer reads his diabetes; set_rule says it
            holds for everyone
  EXACT     the family key still reads it (the no is for someone else)
  FAMILY    the family key no longer reads it (the no names the family)
In every case his caretaker key 'jefferey' still reads it.
"""

from __future__ import annotations

import json
import unittest

from test_life import LifeTest, TA, TF

EVERYONE, EXACT, FAMILY = "everyone", "exact", "family"

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
    # round 5 verify-b: an anyone-word beside other names
    ("the public or the press", EVERYONE), ("the public and the media", EVERYONE),
    ("le grand public et les journalistes", EVERYONE), ("the neighbours and the public", EVERYONE),
    ("le public et la banque", EVERYONE), ("the general public, the bank", EVERYONE),
    ("outsiders, the bank and the press", EVERYONE), ("nobody but my doctor", EVERYONE),
    ("people other than my doctor", EVERYONE), ("social media", EVERYONE),
    # ...and the rest of that skeptic's list (p/r2.py)
    ("strangers and the newspapers", EVERYONE), ("the world and his doctor", EVERYONE),
    ("no one", EVERYONE), ("nobody", EVERYONE), ("personne", EVERYONE), ("aucun", EVERYONE),
    ("no-one at all", EVERYONE), ("the internet", EVERYONE),
    ("the church and everybody", EVERYONE), ("any stranger", EVERYONE), ("folks", EVERYONE),
    ("everyone except the family", EVERYONE), ("all but Anna", EVERYONE),
    ("mon voisin et le public", EVERYONE), ("le public, les voisins", EVERYONE),
    # a name that holds such a word is a name (round 4 verify-c: 'Le Monde')
    ("Le Monde", EXACT), ("Monde", EXACT), ("Mr. Nobody", EXACT), ("Mrs. World", EXACT),
    ("Joe Public", EXACT), ("Facebook", EXACT),
    # round 5 verify-c: plain audiences that round 5 made 'everyone'
    ("Bob", EXACT), ("my GP", EXACT), ("my cardiologist", EXACT), ("my oncologist", EXACT),
    ("Gemini", EXACT), ("Google", EXACT), ("the VA", EXACT), ("the CRA", EXACT),
    ("Revenue Canada", EXACT), ("the mailman", EXACT), ("my hairdresser", EXACT),
    ("Karen", EXACT), ("Bob Smith", EXACT), ("my brother Mike", EXACT),
    # round 5 ANoForNobodyPlainIsANoForEveryone: plain ones stay plain
    ("the neighbours", EXACT), ("my sister", EXACT), ("the bank", EXACT), ("Mrs. Patel", EXACT),
    # a no that names the family is a no for the family key
    ("family", FAMILY), ("the family", FAMILY), ("my family", FAMILY),
]

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
                if DIABETES not in o[where]:
                    why.append(f"his own key ({where}) no longer reads it")
                if "The orb made her laugh." not in f[where]:
                    why.append(f"the family key ({where}) lost an unrelated moment")
                held = DIABETES not in f[where]
                if held != (want in (EVERYONE, FAMILY)):
                    why.append(f"family key ({where}) {'held' if held else 'reads it'}")
            if (f["said"] == "everyone") != (want == EVERYONE):
                why.append(f"set_rule said holds_for={f['said']!r}")
            if why:
                bad.append((a, want, why))
        self.assertEqual(bad, [], "\n" + "\n".join(map(str, bad)))

    def test_a_no_for_bob_blinds_nobody_else(self):
        # round 5 verify-c, repro A: an untagged 'Never tell Bob anything'
        # blanked every moment and fact for his own Claude and the family key
        self.py(SETUP)
        res = {}
        for a in ("Bob", "my GP"):
            r = self.py("""
                import access
                h, c = http()
                with access.owner_console():
                    h.conscience.save_fresh(lambda d: d.__setitem__("rules", []))
                    h.rules.set_rule("disclosure", "", "Never tell %s anything", audience=%r,
                                     allow=False)
                import jefferey_mcp as m
                m.conscience.refresh()
                who = mcp_call(m, "who_am_i")
                con = mcp_call(m, "get_conscience")
                out({"moments": len(who["moments"]), "facts": len(con.get("facts", [])),
                     "family": len(c.get("/life", headers=H(TF)).json()["moments"]),
                     "own_http": len(c.get("/life", headers=H(TA)).json()["moments"])})
            """ % (a, a), JEFFEREY_CLIENT="jefferey")
            res[a] = r
        for a, r in res.items():
            self.assertEqual(r, {"moments": 3, "facts": 1, "family": 3, "own_http": 3}, a)

    def test_a_no_for_bob_never_overrides_his_yes_for_anyone_else(self):
        # round 5 verify-c, repro C
        r = self.py("""
            import access, jefferey_chat as jc
            with access.owner_console():
                jc.rules.set_rule("disclosure", "army", "Anyone can hear my army stories",
                                  audience="anyone", allow=True)
                jc.rules.set_rule("disclosure", "army", "Don't tell Bob my army stories",
                                  audience="Bob", allow=False)
            out({a: jc.rules.check_disclosure(a, "army")["allowed"]
                 for a in ("a neighbour", "my daughter", "family", "claude", "Bob")})
        """)
        self.assertEqual(r, {"a neighbour": True, "my daughter": True, "family": True,
                             "claude": True, "Bob": False})

    def test_a_no_for_any_ai_is_for_other_keys_not_his_own(self):
        # his own agent always sees his life; a no for the engine's maker
        # still holds for the family key that reads through it
        self.py(SETUP)
        auds = ["claude", "any AI", "anthropic"]
        fam = self.py(LOOP % (auds, "TF"), JEFFEREY_CLIENT="family")
        own = self.py(LOOP % (auds, "TA"), JEFFEREY_CLIENT="jefferey")
        for a in auds:
            self.assertIn(DIABETES, own[a]["mcp"], a)
            self.assertIn(DIABETES, own[a]["http"], a)
            self.assertNotIn(DIABETES, fam[a]["mcp"], a)

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
        for surface, res in said.items():
            self.assertEqual(res["the public or the press"], ["everyone", ["everyone"]], surface)
            self.assertEqual(res["nobody but my doctor"], ["everyone", ["everyone"]], surface)
            self.assertEqual(res["Bob"], ["bob", ["bob"]], surface)


if __name__ == "__main__":
    unittest.main()
