"""
Round 9, the last fixes — what the confirm check of 7629103 found
(cc9/w/nn: n3b.py, n3d.py, n8.py, n2b.py).

    1  a question about a kind his rules close to the reader is no guess
       unless it carries a number. The second repair counted every question
       with one word outside the kind ('what medication does he take', 'how
       often does he see his doctor'), so his own JEFFEREY was paused for an
       hour for asking about his health in plain words. A number — digits
       of any script, or number words — still makes it count ('my health
       and my boat number 4800' … '4824').
    2  a statement name may drop his accents (banks often do) but not add
       one, move one, or write a letter another way (circled, Roman
       numeral, full-width, dotless): checked place by place against his own
       names for the plan ('CAA-QUEBÉC', 'CAA-QUÉBÉC' and a circled Ⓝ in
       NETFLIX.COM passed as his plan, and the real bill was then called a
       duplicate).
    3  his relationship to someone is one relationship however it is joined:
       'my ex‑wife' with a non-breaking hyphen, 'my ex wife', 'my exwife'
       and 'my ex⠀wife' all meet a no for his ex-wife.

And what the two final checks of 7d53c0d found:

    4  a YES meets a reader only by the reader's own name and the exact
       names of people HE recorded; a relationship, a word of a name, or a
       person an AI wrote down widens a NO only (an AI-recorded 'Karen
       Novak, family' — or 'fam-ily', or a key named 'exwife' — let his yes
       for Karen beat 'Never tell anyone when I travel' for the family key)
    5  the accents a bank adds in words of its own — a city, 'LTÉE' — or in a
       shortened word of his name ('ADHÉS') are not a disguise; a single
       accented letter of his ('à') explains nothing elsewhere; a mark with
       no letter under it is never his
    6  a number written as a teen, 'dozen', a French teen or a Roman numeral
       is a number; a dose, a stage, 'COVID-19' and 'the 3rd' are not
       guesses; 'one', 'un', 'sept' and 'neuf' count only beside another;
       his heart and his dentist are his health
    7  pairing a drive, choosing this Mac and forgetting a drive with
       connector/home.py want the number typed at the keyboard; a piped
       'yes' is refused

Invented people only: his ex-wife Karen Novak. Every address is on an
example domain.
"""

from __future__ import annotations

import unittest

from test_his_own import HisOwnTest
from test_life import TOKENS
from test_round9_fix import RESET, SURFACES

TX = "tokX-exwife-0123456789abcdefghijklmnopq"


class L1APlainQuestionIsNoGuessANumberIs(HisOwnTest):

    def test_plain_health_questions_never_pause_his_jefferey(self):
        r = self.py(pre=SURFACES + RESET, code="""
            def setup(facts=True):
                reset()
                with access.owner_console():
                    m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                     audience="any AI", allow=False)
                    m.conscience.remember_fact("Likes an aisle seat on long flights", "travel")
                    if facts:
                        m.conscience.remember_fact("I have type 2 diabetes and take metformin",
                                                   "health")
            Q = ["what medication does he take", "how often does he see his doctor",
                 "is his blood pressure under control lately", "did he get his flu shot",
                 "when was his last check-up", "does he still take his pills at night",
                 "what did the specialist tell him", "how much insulin does he use",
                 "my insulin dose", "does he still see the cardiologist",
                 "what was his cholesterol result", "when is his next blood test",
                 "quels médicaments prend-il", "est-ce qu'il voit encore son médecin",
                 "is his hearing aid working", "how is his memory these days",
                 "has his cough gone away", "is he eating well since the hospital",
                 "does his back still hurt in the morning", "what vaccine is he due for",
                 "is his knee getting better", "does he need new glasses",
                 "how is he sleeping since the surgery", "what does the nurse say about his feet",
                 "does he have any allergies to antibiotics"]
            res = {}
            for facts in (True, False):
                for how in ("term", "mcp"):
                    setup(facts)
                    seq = []
                    for q in Q:
                        x = (term("explain_basis", {"topic": q}) if how == "term" else
                             mcp_as(m, "jefferey", "explain_basis", {"topic": q}))
                        seq.append(bool(x.get("refused")))
                    res[f"{how} facts={facts}"] = seq
            setup()
            res["same x25"] = [bool(term("explain_basis", {"topic": "what medication does he take"})
                                    .get("refused")) for _ in range(25)]
            # a number makes it a guess again, in digits of any script or in words
            setup()
            res["digits"] = [bool(term("explain_basis", {"topic": f"my health and my boat number {4800 + i}"})
                                  .get("refused")) for i in range(25)]
            setup()
            W = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
            res["words"] = [bool(term("explain_basis", {
                "topic": f"my health and the code four eight {W[i % 9]} {W[(i // 9) % 9]}"})
                .get("refused")) for i in range(25)]
            setup()
            res["full-width"] = [bool(term("explain_basis", {
                "topic": "my health and " + "".join(chr(0xFF10 + int(d)) for d in str(4800 + i))})
                .get("refused")) for i in range(25)]
            out(res)
        """)
        for k in ("term facts=True", "term facts=False", "mcp facts=True", "mcp facts=False",
                  "same x25"):
            self.assertEqual(r[k], [False] * len(r[k]), (k, r[k]))
        for k in ("digits", "words", "full-width"):
            self.assertIn(True, r[k], (k, r[k]))
            self.assertEqual(r[k].index(True), 20, (k, r[k]))


class L2AStatementMayDropHisAccentsNotAddOrMoveThem(HisOwnTest):

    def test_marks_are_checked_place_by_place(self):
        r = self.py(pre=SURFACES + RESET, code="""
            def pair(fake, real, plan, amt):
                reset()
                with access.owner_console():
                    m.guard.expect_charge(plan, amt, "yearly")
                fresh(); h.conscience.refresh()
                a = mcp_as(m, "jefferey", "check_charge",
                           {"merchant": fake, "amount": amt, "date": "2026-09-01"})
                b = mcp_as(m, "jefferey", "check_charge",
                           {"merchant": real, "amount": amt, "date": "2026-09-03"})
                p = mcp_as(m, "jefferey", "dispute_pack", {"merchant": plan})
                return [a.get("verdict"), b.get("verdict"), b.get("recoverable"),
                        p.get("amount_in_dispute") or 0]
            CAA, HQ, NF = "CAA-Qu\\u00e9bec", "Hydro-Qu\\u00e9bec", "Netflix"
            res = {
                "accent moved": pair("CAA-QUEB\\u00c9C", "CAA QUEBEC", CAA, 95.0),
                "accent added": pair("CAA-QU\\u00c9B\\u00c9C", "CAA QUEBEC", CAA, 95.0),
                "accent moved, Hydro": pair("HYDRO-QUEB\\u00c9C", "HYDRO QUEBEC", HQ, 80.0),
                "circled N": pair("\\u24c3ETFLIX.COM", "NETFLIX.COM", NF, 18.99),
                "Roman numeral I": pair("NETFL\\u2160X.COM", "NETFLIX.COM", NF, 18.99),
                "squared N": pair("\\U0001f13dETFLIX.COM", "NETFLIX.COM", NF, 18.99),
                "ctl his accent": pair("CAA-QU\\u00c9BEC", "CAA QUEBEC", CAA, 95.0),
                "ctl his accent decomposed": pair("CAA-QUE\\u0301BEC", "CAA QUEBEC", CAA, 95.0),
                "ctl accents dropped": pair("CAA QUEBEC", "CAA-QU\\u00c9BEC", CAA, 95.0),
                "ctl plain": pair("NETFLIX.COM", "NETFLIX.COM", NF, 18.99),
            }
            out(res)
        """)
        for k, v in r.items():
            if k.startswith("ctl"):
                self.assertEqual(v[:2], ["expected", "duplicate"], (k, v))
                continue
            self.assertEqual(v[0], "ask_owner", (k, v))
            self.assertEqual(v[1:], ["expected", 0.0, 0], (k, v))


class L3HisRelationshipHoweverItIsJoined(HisOwnTest):

    def test_a_no_for_her_meets_his_ex_wife_written_any_way(self):
        r = self.py(pre=SURFACES + RESET, code="""
            reset()
            with access.owner_console():
                m.life.add_person("Karen Novak", "ex-wife", notes="karen.novak@example.com")
                m.rules.set_rule("disclosure", "travel", "Anyone may know when I travel",
                                 audience="anyone", allow=True)
                m.rules.set_rule("disclosure", "travel", "Never tell Karen when I travel",
                                 audience="Karen Novak", allow=False)
            res = {}
            for aud in ("my ex\\u2011wife", "my ex wife", "my exwife", "my ex\\u2800wife",
                        "my ex\\u200bwife", "my ex-wife", "mon ex-femme"):
                res[aud] = [x.get("allowed") for x in disclosure(aud, "travel")[:3]]
            res["ctl my wife"] = [x.get("allowed") for x in disclosure("my neighbour", "travel")[:3]]
            out(res)
        """)
        for k, v in r.items():
            if k.startswith("ctl") or k == "mon ex-femme":
                continue
            self.assertEqual(v, [False] * 3, (k, v))




class L4AYesMeetsOnlyTheExactPeopleHeRecorded(HisOwnTest):

    def test_an_ai_person_or_a_relationship_never_widens_a_yes(self):
        toks = TOKENS + f",exwife:{TX}"
        r = self.py(code=f"""
            import os
            os.environ["JEFFEREY_HTTP_TOKENS"] = {toks!r}
            import jefferey_http as h, jefferey_mcp as m, access
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            TX = {TX!r}
            def life(tok):
                fresh(); h.conscience.refresh()
                j = c.get("/life", headers=H(tok)).json()
                return [mm.get("text") for mm in j.get("moments", [])] if isinstance(j, dict) else j
            with access.owner_console():
                h.rules.set_rule("disclosure", "travel", "Never tell anyone when I travel",
                                 audience="anyone", allow=False)
                h.rules.set_rule("disclosure", "travel", "Karen may know when I travel",
                                 audience="Karen Novak", allow=True)
                h.life.add_memory("Flying to Lisbon on the third, back on the tenth.",
                                  tags="travel", visibility="family")
                h.cloud.grant("exwife", ["family.read"])
            res = {{"before": life(TF)}}
            mcp_as(m, "jefferey", "add_person", {{"name": "Karen Novak", "relationship": "family"}})
            res["ai family"] = life(TF)
            mcp_as(m, "jefferey", "add_person", {{"name": "Karen Novak", "relationship": "fam-ily"}})
            res["ai fam-ily"] = life(TF)
            with access.owner_console():
                h.life.add_person("Karen Novak", "ex-wife", notes="karen.novak@example.com")
            res["key exwife"] = life(TX)
            res["family after his Karen"] = life(TF)
            out(res)
        """)
        for k, v in r.items():
            self.assertEqual(v, [], (k, v))


class L5TheBanksOwnAccentsAreNotADisguise(HisOwnTest):

    def test_real_quebec_bills_and_the_remaining_disguises(self):
        r = self.py(pre=SURFACES + RESET, code="""
            def one(stmt, plan, amt):
                reset()
                with access.owner_console():
                    m.guard.expect_charge(plan, amt, "monthly")
                fresh(); h.conscience.refresh()
                return mcp_as(m, "jefferey", "check_charge",
                              {"merchant": stmt, "amount": amt, "date": "2026-09-01"}).get("verdict")
            HQ, VT = "Hydro-Qu\u00e9bec", "Vid\u00e9otron"
            CAA, LP = "CAA-Qu\u00e9bec adh\u00e9sion", "Abonnement \u00e0 La Presse"
            out({
                "real HQ city": one("HYDRO-QU\u00c9BEC MONTR\u00c9AL QC", HQ, 80.0),
                "real HQ plain, city": one("HYDRO-QUEBEC MONTR\u00c9AL QC", HQ, 80.0),
                "real VT city": one("VID\u00c9OTRON MONTR\u00c9AL QC", VT, 60.0),
                "real VT Levis": one("VIDEOTRON L\u00c9VIS QC", VT, 60.0),
                "real VT ltee": one("VID\u00c9OTRON LT\u00c9E", VT, 60.0),
                "real CAA short": one("CAA-QU\u00c9BEC ADH\u00c9S", CAA, 95.0),
                "fake LA moved": one("L\u00c0 PRESSE ABONNEMENT", LP, 30.0),
                "fake lead mark": one("\u0301NETFLIX.COM", "Netflix", 18.99),
                "fake accent moved": one("HYDRO-QUEB\u00c9C", HQ, 80.0),
                # the last check: a marked letter in a token of its own passed
                "fake split N": one("N \u00c9TFLIX", "Netflix", 18.99),
                "fake split LIX": one("NETF L\u00cfX", "Netflix", 18.99),
                "fake split CAA": one("CAA-QUEB \u00c9C", CAA, 95.0),
                "real LE DEVOIR LEVIS": one("LE DEVOIR L\u00c9VIS", "Le Devoir", 25.0),
                "real HQ preautorise": one("HYDRO-QU\u00c9BEC PR\u00c9AUTORIS\u00c9", HQ, 80.0),
                # the reader check: his own word written on its own ('Québec')
                # is his name, not the bank's; a mark on no letter is never his;
                # an accented word the bank adds is the bank's
                "fake CAA QUEBEC own word": one("CAA QUEB\u00c9C", "CAA-Qu\u00e9bec", 95.0),
                "fake HQ own word": one("HYDRO QU\u00c9B\u00c8C", HQ, 80.0),
                "fake orphan mark": one("V \u0301IDEOTRON", VT, 60.0),
                "real BELL MOBILITE": one("BELL MOBILIT\u00c9", "Bell", 70.0),
                "real COSTCO GASPE": one("COSTCO GASP\u00c9", "Costco", 65.0),
                "real CAA ADHESION": one("CAA-QU\u00c9BEC ADH\u00c9SION", "CAA-Qu\u00e9bec", 95.0),
            })
        """)
        for k, v in r.items():
            self.assertEqual(v, "expected" if k.startswith("real") else "ask_owner", (k, v))


class L6ANumberInAnyWordsIsANumber(HisOwnTest):

    def test_number_words_count_and_plain_health_words_do_not(self):
        r = self.py(code="""
            import grounding as g
            out({"yes": [g.guess_shaped(q) for q in (
                    "my health and the code thirteen fifteen", "my health and the code one one",
                    "ma sant\u00e9 et le code quinze seize", "my health and a dozen",
                    # the last check: a number dressed as a dose, a stage or a day
                    "my health and my boat number type 4800", "my health and 4800 mg",
                    "my health and 4800th", "my health and level 4800")],
                 "no": [g.guess_shaped(q) for q in (
                    "is his type 2 diabetes under control", "did he get his COVID-19 booster",
                    "is he still on 500 mg of metformin", "did he see the doctor on the 3rd",
                    "does he take one pill", "a-t-il un nouveau m\u00e9decin",
                    "est-ce que son m\u00e9decin est neuf",
                    # the last check: Roman numerals are medical, articles are words
                    "is his type II diabetes under control", "is he getting an IV at the hospital",
                    "a-t-il un m\u00e9decin de famille et une pharmacie",
                    "does he take one pill in the morning and one at night",
                    "did his back seize up")],
                 "health": [g.sensitivity(q) for q in (
                    "his cardiac rehab", "a-t-il une ordonnance pour un antibiotique",
                    "prend-il ses comprim\u00e9s le soir")],
                 "not health": [g.sensitivity(q) for q in (
                    "Visited the Sacr\u00e9-Coeur in Paris with Anna",
                    "She knows the poem by heart", "Lunch with my friend who is a dentist")]})
        """)
        self.assertEqual(r["yes"], [True] * 8, r["yes"])
        self.assertEqual(r["no"], [False] * 12, r["no"])
        self.assertEqual(r["health"], [["health"]] * 3, r["health"])
        self.assertEqual(r["not health"], [[]] * 3, r["not health"])


class L7PairingADriveWantsTheKeyboard(HisOwnTest):

    def test_a_piped_yes_never_pairs_a_drive(self):
        import json as _json
        import os
        import subprocess
        import sys
        from pathlib import Path
        import at_the_keyboard
        from test_life import CONNECTOR
        vol = Path(self.tmp) / "Volumes" / "Planted"
        (vol / ".selfcloud").mkdir(parents=True)
        (vol / ".selfcloud" / "selfcloud.json").write_text(_json.dumps(
            {"kind": "self-cloud-drive", "id": "0123456789abcdef", "name": "Planted"}))
        env = self.env()
        env["JEFFEREY_DRIVES"] = str(Path(self.tmp) / "drives.json")
        cmd = [sys.executable, str(CONNECTOR / "home.py"), "pair", str(vol)]
        p = subprocess.run(cmd, input="yes\n", env=env, cwd=self.tmp, capture_output=True,
                           text=True, timeout=120)
        self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("typing at the keyboard", p.stdout)
        self.assertFalse(os.path.exists(env["JEFFEREY_DRIVES"]))
        rc, screen = at_the_keyboard.run(cmd, env, self.tmp)
        self.assertEqual(rc, 0, screen)
        self.assertIn("0123456789abcdef", Path(env["JEFFEREY_DRIVES"]).read_text())


class L8ANoHoldsTheSameOnEverySurface(HisOwnTest):

    def test_a_no_by_name_or_relationship_holds_on_life_and_basis_alike(self):
        TB = "tokB-bobkey-0123456789abcdefghijklmnopq"
        TC2 = "tokK-claudekey-0123456789abcdefghijkl"
        toks = TOKENS + f",exwife:{TX},bob:{TB},claude:{TC2}"
        r = self.py(code=f"""
            import os
            os.environ["JEFFEREY_HTTP_TOKENS"] = {toks!r}
            import jefferey_http as h, access
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            TX, TB, TC2 = {TX!r}, {TB!r}, {TC2!r}
            def seen(tok):
                fresh(); h.conscience.refresh()
                life = c.get("/life", headers=H(tok)).json()
                basis = c.get("/basis", params={{"topic": "travel Lisbon"}}, headers=H(tok)).json()
                return {{"moments": [x.get("text") for x in life.get("moments", [])],
                         "life facts": [x.get("fact") for x in life.get("facts", [])],
                         "basis": [x.get("fact") for x in basis.get("facts", [])]}}
            with access.owner_console():
                h.life.add_person("Karen Novak", "ex-wife", notes="karen.novak@example.com")
                h.life.add_person("Bob Smith", "neighbour")
                h.life.add_person("Claude", "neighbour")
                h.rules.set_rule("disclosure", "travel", "Never tell Karen when I travel",
                                 audience="Karen Novak", allow=False)
                h.rules.set_rule("disclosure", "travel", "Never tell my neighbour when I travel",
                                 audience="my neighbour", allow=False)
                h.life.add_memory("Flying to Lisbon on the third.", tags="travel",
                                  visibility="family")
                h.conscience.remember_fact("I fly to Lisbon on the third", "travel")
                for k in ("exwife", "bob", "claude"):
                    h.cloud.grant(k, ["life.read", "facts.read", "priorities.read"])
                # the reader check: a key named like an AI (a neighbour called
            # Claude) is still met by a no through his record of the person
            out({{"exwife": seen(TX), "bob": seen(TB), "claude": seen(TC2)}})
        """)
        for k, v in r.items():
            self.assertEqual(v, {"moments": [], "life facts": [], "basis": []}, (k, v))


class L9TwoOfHisPeopleWithOneNameGetNoYesThroughEachOther(HisOwnTest):

    def test_an_ambiguous_key_name_opens_nothing(self):
        TK = "tokK-karenkey-0123456789abcdefghijklmn"
        toks = TOKENS + f",karen:{TK}"
        r = self.py(code=f"""
            import os
            os.environ["JEFFEREY_HTTP_TOKENS"] = {toks!r}
            import jefferey_http as h, access
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            TK = {TK!r}
            with access.owner_console():
                h.life.add_person("Karen", "ex-wife")
                h.life.add_person("Karen", "sister")
                h.rules.set_rule("disclosure", "travel", "Never tell anyone when I travel",
                                 audience="anyone", allow=False)
                h.rules.set_rule("disclosure", "travel", "My sister may know when I travel",
                                 audience="my sister", allow=True)
                h.conscience.remember_fact("I fly to Lisbon on the third", "travel")
                h.cloud.grant("karen", ["facts.read", "life.read"])
            fresh(); h.conscience.refresh()
            basis = c.get("/basis", params={{"topic": "travel Lisbon"}}, headers=H(TK)).json()
            conscience = c.get("/conscience", headers=H(TK)).json()
            out({{"basis": [x.get("fact") for x in basis.get("facts", [])],
                 "conscience": [x.get("fact") for x in conscience.get("facts", [])]}})
        """)
        self.assertEqual(r, {"basis": [], "conscience": []}, r)


if __name__ == "__main__":
    unittest.main()
