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
                    "my health and the code IV", "my money and the code xiv")],
                 "no": [g.guess_shaped(q) for q in (
                    "is his type 2 diabetes under control", "did he get his COVID-19 booster",
                    "is he still on 500 mg of metformin", "did he see the doctor on the 3rd",
                    "does he take one pill", "a-t-il un nouveau m\u00e9decin",
                    "est-ce que son m\u00e9decin est neuf")],
                 "health": [g.sensitivity(q) for q in (
                    "how is his heart", "comment va son coeur", "did he see the dentist")]})
        """)
        self.assertEqual(r["yes"], [True] * 6, r["yes"])
        self.assertEqual(r["no"], [False] * 7, r["no"])
        self.assertEqual(r["health"], [["health"]] * 3, r["health"])


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


if __name__ == "__main__":
    unittest.main()
