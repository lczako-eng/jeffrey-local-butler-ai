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

Invented people only: his ex-wife Karen Novak. Every address is on an
example domain.
"""

from __future__ import annotations

import unittest

from test_his_own import HisOwnTest
from test_round9_fix import RESET, SURFACES


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


if __name__ == "__main__":
    unittest.main()
