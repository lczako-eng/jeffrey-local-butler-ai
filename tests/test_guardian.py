"""
Regression tests for the money watch (October 2026 stress test: I-36, I-37,
I-38, I-39, I-47). The cases are the stress test's own money scenarios
(money-02 … money-71); each one failed on the old guardian.

Standard-library unittest. Every test uses its own temporary folder and
never the real home folder. Anything that binds at import time (the three
surfaces) runs in a child process with its own HOME, which must still be
empty afterwards.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "connector"))

from conscience import Conscience        # noqa: E402
import guardian                          # noqa: E402
from guardian import Guardian            # noqa: E402

PY = sys.executable
TODAY = dt.date(2026, 10, 14)


# ---------------------------------------------------------------- helpers
def child_env(tmp: Path, **extra) -> dict:
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ)
    for k in ("SELFCLOUD_ROOT", "JEFFEREY_OWNER_CONSOLE", "JEFFEREY_CLIENT",
              "JEFFEREY_OFFLINE", "JEFFEREY_HTTP_TOKEN", "JEFFEREY_HTTP_TOKENS"):
        env.pop(k, None)
    env.update(HOME=str(home), JEFFEREY_CONSCIENCE_PATH=str(tmp / "conscience.json"),
               JEFFEREY_EGRESS=str(tmp / "egress.jsonl"),
               JEFFEREY_DOOR=str(tmp / "door-shut"),
               SELFCLOUD_INDEX=str(tmp / "photo-index"), SELFCLOUD_VOICE=str(tmp / "voice"),
               SELFCLOUD_DISCS=str(tmp / "discs"), PYTHONDONTWRITEBYTECODE="1")
    for k, v in extra.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


PRELUDE = """
import asyncio, json, os, sys
sys.path.insert(0, %r)
def out(**kw):
    print("RESULT " + json.dumps(kw, default=str))
def unpack(r):
    content = getattr(r, "content", None)
    if content is None:
        content = r[0] if isinstance(r, tuple) else r
    if isinstance(content, tuple):
        content = content[0]
    items = [json.loads(c.text) for c in content]
    return items[0] if len(items) == 1 else items
""" % str(REPO / "connector")


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-money-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def guard(self, owner: bool = True, name: str = "conscience.json") -> Guardian:
        c = Conscience(self.tmp / name)
        return Guardian(c, owner_present=lambda: owner, today=lambda: TODAY)

    def child(self, code: str, **env) -> dict:
        p = subprocess.run([PY, "-c", PRELUDE + textwrap.dedent(code)], cwd=REPO,
                           env=child_env(self.tmp, **env), capture_output=True,
                           text=True, timeout=180)
        left = sorted(str(x) for x in (self.tmp / "home").rglob("*"))
        self.assertEqual(left, [], "a surface wrote into the home folder")
        for line in reversed(p.stdout.splitlines()):
            if line.startswith("RESULT "):
                return json.loads(line[7:])
        raise AssertionError(f"no RESULT\nstdout:{p.stdout[-3000:]}\nstderr:{p.stderr[-3000:]}")


def big_statement(n=220, seed=7, month="2026-09"):
    """The stress test's realistic statement: 8 subscriptions, the rest
    ordinary purchases written the way card statements write them."""
    rnd = random.Random(seed)
    oneoffs = [
        "LOBLAWS #1234 TORONTO ON", "METRO 512 OTTAWA ON", "TIM HORTONS #0456 KANATA ON",
        "SQ *JOES COFFEE TORONTO ON", "SQ *FARMERS MARKET STALL 12", "PETRO-CANADA 12345 OTTAWA ON",
        "SHELL C12345 NEPEAN ON", "SHOPPERS DRUG MART #1022", "DOLLARAMA #612 OTTAWA",
        "LCBO/RAO #0213 OTTAWA ON", "CANADIAN TIRE #087 OTTAWA", "HOME DEPOT #7011",
        "COSTCO WHOLESALE W539 OTTAWA ON", "UBER *TRIP HELP.UBER.COM", "UBER* EATS PENDING",
        "DOORDASH*SUBWAY", "PAYPAL *EBAY CA", "PAYPAL *ETSY.COM", "AMZN Mktp CA*{id}",
        "AMAZON.CA*{id}", "STARBUCKS 800-782-7282", "WAL-MART SUPERCENTER#3121", "PRESTO AUTOLOAD",
        "OC TRANSPO PARKING", "CINEPLEX #9101", "INDIGO #233", "BEST BUY #940", "IKEA OTTAWA",
        "MCDONALD'S #40123", "SOBEYS #842", "PHARMAPRIX #0123 MONTRÉAL QC", "GOOGLE *YOUTUBE PREMIUM",
        "APPLE.COM/BILL 866-712-7753 ON", "STEAMGAMES.COM 4259522", "WINNERS #213", "SAQ 23045",
    ]
    subs = [("NETFLIX.COM 866-579-7172 ON", 18.63), ("SPOTIFY P2A5C1D3E9 STOCKHOLM", 12.42),
            ("ROGERS ******1234", 95.00), ("DISNEY PLUS 888-905-7888 CA", 13.55),
            ("Amazon.ca Prime Member amazon.ca/pm", 11.29), ("GOODLIFE FITNESS 1234", 59.99),
            ("APPLE.COM/BILL 866-712-7753 ON", 3.99), ("THE GLOBE AND MAIL", 25.00)]
    rows = [{"merchant": m, "amount": a, "date": f"{month}-{rnd.randint(1, 28):02d}"}
            for m, a in subs]
    while len(rows) < n:
        m = rnd.choice(oneoffs).replace(
            "{id}", "".join(rnd.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(9)))
        rows.append({"merchant": m, "amount": round(rnd.uniform(2, 180), 2),
                     "date": f"{month}-{rnd.randint(1, 28):02d}"})
    return rows


def register_subs(g: Guardian):
    for m, a in [("Netflix", 18.63), ("Spotify", 12.42), ("Rogers", 95.00), ("Disney Plus", 13.55),
                 ("Amazon Prime", 11.29), ("GoodLife Fitness", 59.99), ("Apple iCloud", 3.99),
                 ("The Globe and Mail", 25.00)]:
        g.expect_charge(m, a)


# ======================================================================
# I-36  merchant matching: real statements, cancellations that arm
# ======================================================================
class I36Matching(Temp):
    def test_real_descriptors_match_the_registered_merchant(self):
        # money-02, -03, -04, -06: these were all 'unexpected_merchant'
        g = self.guard()
        g.expect_charge("Netflix", 18.63)
        g.expect_charge("Spotify", 12.42)
        g.expect_charge("Disney Plus", 13.55)
        g.expect_charge("Amazon Prime", 11.29)
        cases = [("NETFLIX.COM 866-579-7172 CA", 18.63, "Netflix"),
                 ("NETFLIX.COM LOS GATOS CA", 18.63, "Netflix"),
                 ("Netflix.com Toronto ON", 18.63, "Netflix"),
                 ("SPOTIFY P2A5C1D3E9 STOCKHOLM SE", 12.42, "Spotify"),
                 ("Spotify Toronto ON", 12.42, "Spotify"),
                 ("PAYPAL *SPOTIFY", 12.42, "Spotify"),
                 ("PAYPAL *SPOTIFYAB 4029357733", 12.42, "Spotify"),
                 ("PAYPAL *DISNEYPLUS", 13.55, "Disney Plus"),
                 ("Amazon.ca Prime Member amazon.ca/pm", 11.29, "Amazon Prime"),
                 ("AMAZON.CA PRIME MEMBER", 11.29, "Amazon Prime")]
        for desc, amt, name in cases:
            r = g.check_charge(desc, amt, "2026-10-03", record=False)
            self.assertEqual((r["verdict"], r["matched_to"]), ("expected", name), desc)

    def test_marketplace_orders_are_one_merchant_and_not_prime(self):
        # money-06: every order id got its own key, and none was Prime
        g = self.guard()
        g.expect_charge("Amazon Prime", 11.29)
        self.assertEqual(guardian._norm("AMZN Mktp CA*2K4L71Z30"),
                         guardian._norm("AMZN Mktp CA*9B3TQ02X1"))
        r = g.check_charge("AMZN Mktp CA*2K4L71Z30", 11.29, "2026-10-07", record=False)
        self.assertIsNone(r["matched_to"])

    def test_a_real_statement_is_not_a_wall_of_alarms(self):
        # money-35: '217 of 220 charges need your attention ($19759.27 at stake)'
        g = self.guard()
        register_subs(g)
        st = g.review_statement(big_statement())
        subs = ("NETFLIX", "SPOTIFY", "ROGERS", "DISNEY", "PRIME", "GOODLIFE", "GLOBE")
        loud = [f for f in st["flagged"]
                if any(s in f["merchant"].upper() for s in subs)
                and f["verdict"] != "unexpected_merchant"]
        self.assertEqual(loud, [], "a registered subscription was flagged")
        quiet_subs = [f for f in st["flagged"] if any(s in f["merchant"].upper() for s in subs)]
        self.assertEqual(quiet_subs, [], "a registered subscription was not matched")
        self.assertLess(st["recoverable_total"], 50, st["summary"])
        self.assertNotIn("217 of 220", st["summary"])
        self.assertLessEqual(st["attention"], 10, st["summary"])

    def test_a_one_off_purchase_is_informational(self):
        # money-05: a coffee was 0.85 severity, 'at stake', with a dispute offered
        g = self.guard()
        r = g.check_charge("SQ *JOES COFFEE TORONTO ON", 4.75, "2026-10-06")
        self.assertEqual(r["verdict"], "unexpected_merchant")
        self.assertEqual(r["recoverable"], 0.0)
        self.assertLess(r["severity"], 0.5)
        self.assertNotIn("dispute_pack", r["action"])
        st = g.review_statement([{"merchant": "SQ *JOES COFFEE TORONTO ON",
                                  "amount": 4.75, "date": "2026-10-06"}])
        self.assertEqual(st["recoverable_total"], 0.0)
        self.assertNotIn("need your attention", st["summary"])

    def test_cancellation_under_a_slightly_different_name_arms_the_entry(self):
        # money-67: a new inactive entry was created; Netflix stayed active
        g = self.guard()
        g.expect_charge("Netflix", 18.63)
        m = g.mark_cancelled("Netflix subscription", "2026-08-01")
        self.assertEqual(m["marked_cancelled"], 1)
        self.assertEqual(len(g.expected_charges()), 1)
        r = g.check_charge("Netflix", 18.63, "2026-09-03")
        self.assertEqual(r["verdict"], "charged_after_cancel")

    def test_near_miss_cancellation_asks_and_records_nothing(self):
        g = self.guard()
        g.expect_charge("Netflix", 18.63)
        before = json.dumps(g.expected_charges())
        m = g.mark_cancelled("Netflx", "2026-08-01")
        self.assertEqual(m["marked_cancelled"], 0)
        self.assertIn("Did you mean Netflix", m["note"])
        self.assertEqual(json.dumps(g.expected_charges()), before)

    def test_cancellation_that_could_be_two_things_asks(self):
        g = self.guard()
        g.expect_charge("Apple iCloud", 3.99)
        g.expect_charge("Apple Music", 10.99)
        m = g.mark_cancelled("Apple", "2026-08-01")
        self.assertEqual(m["marked_cancelled"], 0)
        self.assertTrue(all(e["active"] for e in g.expected_charges()))

    def test_non_latin_digit_only_and_empty_names_never_collide(self):
        # money-40: all of these had the key '' and matched each other
        g = self.guard()
        g.expect_charge("淘宝", 20.0)
        self.assertEqual(g.check_charge("Яндекс Такси", 20.0, "2026-10-01")["verdict"],
                         "unexpected_merchant")
        self.assertEqual(g.check_charge("淘宝", 20.0, "2026-10-01")["verdict"], "expected")
        self.assertEqual(g.check_charge("1234567", 20.0, "2026-10-02")["verdict"],
                         "unexpected_merchant")
        empty = g.check_charge("", 20.0, "2026-10-03")
        self.assertEqual(empty["verdict"], "could_not_check")
        self.assertIn("error", g.expect_charge("", 5.0))
        self.assertEqual(g.mark_cancelled("", "2026-10-01")["marked_cancelled"], 0)

    def test_dispute_pack_found_by_name_or_by_descriptor(self):
        # money-53: by name $0; by descriptor 'nothing on file' and the cancel lost
        g = self.guard()
        g.expect_charge("Crave", 22.59)
        g.mark_cancelled("Crave", "2026-08-01")
        g.check_charge("CRAVE TORONTO ON 8669", 22.59, "2026-09-12")
        g.check_charge("CRAVE TORONTO ON 8669", 22.59, "2026-10-12")
        for name in ("Crave", "CRAVE TORONTO ON 8669"):
            p = g.dispute_pack(name)
            self.assertEqual(p["amount_in_dispute"], 45.18, name)
            self.assertEqual(p["what_was_authorized"]["cancelled_on"], "2026-08-01")
            self.assertEqual({c["verdict"] for c in p["charges_in_dispute"]},
                             {"charged_after_cancel"})

    def test_lookalike_domain_is_not_the_real_merchant(self):
        g = self.guard()
        g.expect_charge("Netflix", 18.63)
        r = g.check_charge("NETFLIX-SUPPORT.NET", 18.63, "2026-10-03")
        self.assertIsNone(r["matched_to"])

    def test_the_owner_can_confirm_a_name_for_a_merchant(self):
        g = self.guard(owner=False)
        g.expect_charge("Hydro Ottawa", 140.0)            # a caretaker's proposal
        owner = Guardian(g.c, owner_present=lambda: True, today=lambda: TODAY)
        owner.confirm_change(owner.pending_changes()[0]["id"])
        r = g.add_alias("HOL ELECTRIC 6135550100", "Hydro Ottawa")
        self.assertEqual(r["status"], "waiting_for_owner")
        self.assertIsNone(g.check_charge("HOL ELECTRIC 6135550100", 140.0, "2026-10-01",
                                         record=False)["matched_to"])
        owner.confirm_change(owner.pending_changes()[0]["id"])
        self.assertEqual(g.check_charge("HOL ELECTRIC 6135550100", 140.0, "2026-10-01",
                                        record=False)["matched_to"], "Hydro Ottawa")


# ======================================================================
# I-37  one charge is one charge
# ======================================================================
class I37Idempotent(Temp):
    def test_the_same_statement_reviewed_twice_says_the_same(self):
        # money-16: the second review said '3 of 3 ... duplicate'
        g = self.guard()
        for m, a in [("Netflix", 18.63), ("Spotify", 12.42), ("Rogers", 95.0)]:
            g.expect_charge(m, a)
        stmt = [{"merchant": "Netflix", "amount": 18.63, "date": "2026-09-03"},
                {"merchant": "Spotify", "amount": 12.42, "date": "2026-09-04"},
                {"merchant": "Rogers", "amount": 95.0, "date": "2026-09-15"}]
        a = g.review_statement(stmt)
        b = g.review_statement(stmt)
        self.assertEqual(a["flagged"], [])
        self.assertEqual(b["flagged"], [])
        self.assertEqual(b["already_on_file"], 3)
        self.assertEqual(len(g.c.data["charges_seen"]), 3)

    def test_asking_six_times_does_not_build_a_dispute(self):
        # money-54: six checks -> dispute pack demanded $93.15
        g = self.guard()
        g.expect_charge("Netflix", 18.63)
        verdicts = {g.check_charge("Netflix", 18.63, "2026-10-03")["verdict"] for _ in range(6)}
        self.assertEqual(verdicts, {"expected"})
        self.assertEqual(g.dispute_pack("Netflix")["amount_in_dispute"], 0.0)
        self.assertEqual(len(g.c.data["charges_seen"]), 1)

    def test_a_bad_line_keeps_nothing_and_the_retry_is_clean(self):
        # money-31: line 1 was kept, the retry called it a duplicate
        g = self.guard()
        g.expect_charge("Netflix", 18.63)
        g.expect_charge("Spotify", 11.99)
        bad = g.review_statement([{"merchant": "Netflix", "amount": 18.63, "date": "2026-10-03"},
                                  {"merchant": "Spotify", "amount": "11,9x", "date": "2026-10-04"}])
        self.assertEqual(len(g.c.data["charges_seen"]), 0)
        self.assertEqual(bad["errors"][0]["line"], 2)
        self.assertIn("line 2", bad["summary"])
        good = g.review_statement([{"merchant": "Netflix", "amount": 18.63, "date": "2026-10-03"},
                                   {"merchant": "Spotify", "amount": "11,99", "date": "2026-10-04"}])
        self.assertEqual(good["flagged"], [])
        self.assertEqual(good["recorded"], 2)

    def test_amounts_written_the_way_statements_write_them(self):
        # money-27/-28/-29: ValueError; money-33: NaN/Infinity reached the store
        for said, want in [("1,234.56", 1234.56), ("$18.63", 18.63), ("1 234,56 $", 1234.56),
                           ("11,99", 11.99), ("(22.59)", -22.59), ("22.59 CR", -22.59),
                           ("-$22.59", -22.59), ("CA$20", 20.0), (95, 95.0)]:
            self.assertEqual(guardian._parse_amount(said), (want, None), said)
        g = self.guard()
        g.expect_charge("Netflix", 18.63)
        for said in ("nan", "inf", float("nan"), float("inf"), True, 1e15, "20 or 25", None):
            r = g.check_charge("Netflix", said, "2026-10-01")
            self.assertEqual(r["verdict"], "could_not_check", said)
        st = g.review_statement([{"merchant": "NETFLIX"}, {"amount": 12.0}, {}, "NETFLIX 18.63"])
        self.assertEqual(len(st["errors"]), 4)
        self.assertEqual(g.c.data["charges_seen"], [])
        raw = (self.tmp / "conscience.json").read_text()
        self.assertNotIn("NaN", raw)
        self.assertNotIn("Infinity", raw)

    def test_a_real_double_bill_in_one_statement_is_found_once(self):
        g = self.guard()
        g.expect_charge("GoodLife Fitness", 59.99)
        stmt = [{"merchant": "GoodLife Fitness", "amount": 59.99, "date": "2026-10-01"},
                {"merchant": "GoodLife Fitness", "amount": 59.99, "date": "2026-10-01"}]
        for _ in range(2):
            st = g.review_statement(stmt)
            self.assertEqual([f["verdict"] for f in st["flagged"]], ["duplicate"])
        self.assertEqual(g.dispute_pack("GoodLife Fitness")["amount_in_dispute"], 59.99)

    def test_cadence_windows_not_calendar_months(self):
        # money-15: Sep 30 / Oct 1 missed; money-17: weekly called duplicate
        g = self.guard()
        g.expect_charge("GoodLife Fitness", 59.99)
        self.assertEqual(g.check_charge("GoodLife Fitness", 59.99, "2026-09-30")["verdict"],
                         "expected")
        self.assertEqual(g.check_charge("GoodLife Fitness", 59.99, "2026-10-01")["verdict"],
                         "duplicate")
        g.expect_charge("Meals on Wheels", 42.00, "weekly")
        self.assertEqual({g.check_charge("Meals on Wheels", 42.0, d)["verdict"]
                          for d in ("2026-10-01", "2026-10-08", "2026-10-15", "2026-10-22")},
                         {"expected"})

    def test_a_double_bill_found_when_reviewed_out_of_order(self):
        g = self.guard()
        g.expect_charge("GoodLife Fitness", 59.99)
        g.check_charge("GoodLife Fitness", 59.99, "2026-10-01")
        g.check_charge("GoodLife Fitness", 59.99, "2026-09-30")
        p = g.dispute_pack("GoodLife Fitness")
        self.assertEqual([(c["date"], c["verdict"]) for c in p["charges_in_dispute"]],
                         [("2026-10-01", "duplicate")])

    def test_dates_a_year_apart_are_different_charges(self):
        # money-39: '10/01/2025' after '10/01/2026' was a duplicate
        g = self.guard()
        g.expect_charge("GoodLife Fitness", 59.99)
        got = [g.check_charge("GoodLife Fitness", 59.99, d)["verdict"]
               for d in ("10/01/2026", "10/01/2025", "Sep 1, 2026", "Sep 1, 2025")]
        self.assertEqual(got, ["expected"] * 4)
        self.assertEqual(guardian._parse_date("Sep 1, 2025", TODAY)[0], "2025-09-01")
        self.assertEqual(guardian._parse_date("1er octobre 2026", TODAY)[0], "2026-10-01")

    def test_dateless_lines_are_checked_but_never_pile_up(self):
        g = self.guard()
        g.expect_charge("Tim Hortons", 2.15)
        a = g.check_charge("Tim Hortons", 2.15)
        b = g.check_charge("Tim Hortons", 2.15)
        self.assertEqual((a["verdict"], b["verdict"]), ("expected", "expected"))
        self.assertEqual(g.c.data["charges_seen"], [])

    def test_one_save_for_a_whole_statement(self):
        # money-38: one save (and one snapshot) per line wiped the history
        g = self.guard()
        register_subs(g)
        rev = g.c.data["_rev"]
        g.review_statement(big_statement(25, seed=9))
        self.assertEqual(g.c.data["_rev"], rev + 1)

    def test_door_shut_review_keeps_nothing_terminal(self):
        # money-45, on the terminal surface as the stress test ran it
        # Integration: on the terminal the model is not the owner's hands (I-04),
        # so its expect_charge waits for him; he confirms it at his keyboard.
        r = self.child("""
            import jefferey_chat as jc, egress, access
            T = jc.dispatch_tool
            asked = T("expect_charge", {"merchant": "Netflix", "amount": 18.63})
            with access.owner_console():
                jc.guard.confirm_change(asked["proposal"])
            egress.shut()
            T("review_statement", {"charges": [{"merchant": "Netflix", "amount": 18.63, "date": "2026-10-03"}]})
            seen = len(jc.guard.c.data["charges_seen"])
            egress.open_()
            r2 = T("review_statement", {"charges": [{"merchant": "Netflix", "amount": 18.63, "date": "2026-10-03"}]})
            r3 = T("review_statement", {"charges": [{"merchant": "Netflix", "amount": 18.63, "date": "2026-10-03"}]})
            out(seen_while_shut=seen, after=[f["verdict"] for f in r2["flagged"]],
                again=[f["verdict"] for f in r3["flagged"]])
        """)
        self.assertEqual(r, {"seen_while_shut": 0, "after": [], "again": []})

    def test_bad_line_then_retry_over_mcp(self):
        # money-31 as reproduced over MCP with the caretaker key
        r = self.child("""
            os.environ["JEFFEREY_CLIENT"] = "jefferey"
            import jefferey_mcp as m
            async def go():
                c = lambda n, a: m.mcp.call_tool(n, a)
                bad = unpack(await c("review_statement", {"charges": [
                    {"merchant": "Netflix", "amount": 18.63, "date": "2026-10-03"},
                    {"merchant": "Spotify", "amount": -1e300, "date": "2026-10-04"}]}))
                good = unpack(await c("review_statement", {"charges": [
                    {"merchant": "Netflix", "amount": 18.63, "date": "2026-10-03"}]}))
                again = unpack(await c("review_statement", {"charges": [
                    {"merchant": "Netflix", "amount": 18.63, "date": "2026-10-03"}]}))
                return bad, good, again
            bad, good, again = asyncio.run(go())
            out(bad=bad["summary"], good=[f["verdict"] for f in good["flagged"]],
                again=[f["verdict"] for f in again["flagged"]], again_summary=again["summary"])
        """)
        self.assertIn("Nothing from this statement has been kept", r["bad"])
        self.assertEqual(r["good"], r["again"])
        self.assertNotIn("duplicate", r["again"])
        self.assertIn("already on file", r["again_summary"])


# ======================================================================
# I-38  cadence and 'did not authorize recurring' are enforced
# ======================================================================
class I38Cadence(Temp):
    def test_a_one_time_purchase_that_renews_is_flagged(self):
        # money-19: the GoDaddy renewal was 'as agreed. Quiet.'
        g = self.guard()
        g.expect_charge("GoDaddy", 21.99, cadence="once", authorized_recurring=False)
        got = [g.check_charge("GODADDY.COM 480-505-8855", 21.99, d)["verdict"]
               for d in ("2025-10-10", "2026-10-10", "2026-11-10")]
        self.assertEqual(got, ["expected", "unauthorized_renewal", "unauthorized_renewal"])
        p = g.dispute_pack("GoDaddy")
        self.assertEqual(p["amount_in_dispute"], 43.98)
        self.assertIn("never agreed to automatic renewal", p["how_to_use"])

    def test_a_yearly_plan_billed_every_month_is_flagged(self):
        # money-18
        g = self.guard()
        g.expect_charge("Norton 360", 119.99, "yearly")
        got = [g.check_charge("Norton 360", 119.99, d)["verdict"]
               for d in ("2026-08-14", "2026-09-14", "2026-10-14")]
        self.assertEqual(got, ["expected", "duplicate", "duplicate"])
        self.assertEqual(g.check_charge("Norton 360", 119.99, "2027-08-10")["verdict"],
                         "expected")

    def test_cadence_words_are_understood(self):
        # money-11: 'Monthly' understated the yearly cost twelvefold
        g = self.guard()
        g.expect_charge("Netflix", 16.49, cadence="Monthly")
        r = g.check_charge("Netflix", 18.99, "2026-10-03")
        self.assertIn("$30.00 a year", r["what_happened"])
        g.expect_charge("Crave", 9.99, cadence="month")
        st = g.review_statement([{"merchant": "Netflix", "amount": 18.99, "date": "2026-11-03"},
                                 {"merchant": "Crave", "amount": 12.99, "date": "2026-11-03"}])
        self.assertEqual(st["annualized_estimate"], 66.0)
        self.assertEqual(g.expected_charges()[0]["cadence"], "monthly")

    def test_false_as_text_means_false_on_every_surface(self):
        # money-71: 'false' from a local model was stored as True
        r = self.child("""
            import jefferey_chat as jc
            e = jc.dispatch_tool("expect_charge", {"merchant": "GoDaddy", "amount": 21.99,
                                                   "cadence": "once", "authorized_recurring": "false"})
            out(stored=e.get("authorized_recurring"))
        """)
        self.assertIs(r["stored"], False)
        g = self.guard()
        self.assertFalse(g.expect_charge("X Co", 5, "monthly", "no")["authorized_recurring"])
        self.assertFalse(g.expect_charge("Y Co", 5, "monthly", "maybe?")["authorized_recurring"])


# ======================================================================
# I-39  dates decide; disputes claim only what is owed
# ======================================================================
class I39DatesAndDisputes(Temp):
    def test_a_charge_from_before_the_cancellation_is_legitimate(self):
        # money-20
        g = self.guard()
        g.expect_charge("Crave", 22.59)
        g.mark_cancelled("Crave", "2026-10-12")
        r = g.check_charge("Crave", 22.59, "2026-09-12")
        self.assertEqual(r["verdict"], "expected")
        self.assertEqual(g.dispute_pack("Crave")["amount_in_dispute"], 0.0)

    def test_end_of_period_cancellation(self):
        # money-21
        g = self.guard()
        g.expect_charge("SiriusXM", 14.69)
        g.mark_cancelled("SiriusXM", "2026-10-31")
        self.assertEqual(g.check_charge("SiriusXM", 14.69, "2026-10-15")["verdict"], "expected")
        self.assertEqual(g.check_charge("SiriusXM", 14.69, "2026-11-15")["verdict"],
                         "charged_after_cancel")

    def test_free_text_cancellation_dates(self):
        # money-66: 'end of the month' was stored and quoted as a date
        g = self.guard()
        g.expect_charge("Crave", 22.59)
        m = g.mark_cancelled("Crave", "end of the month")
        self.assertEqual(m["cancelled_on"], "2026-10-31")
        self.assertEqual(g.check_charge("Crave", 22.59, "2026-10-03")["verdict"], "expected")
        g.expect_charge("Hydro", 95.0)
        for said in ("sometime soon", "03/04/2026"):
            m = g.mark_cancelled("Hydro", said)
            self.assertEqual(m["marked_cancelled"], 0, said)
            self.assertIn("NOT RECORDED", m["note"])
        self.assertTrue(next(e for e in g.expected_charges() if e["merchant"] == "Hydro")["active"])

    def test_a_genuine_charge_after_cancelling(self):
        # money-22 still works
        g = self.guard()
        g.expect_charge("Crave", 22.59)
        g.mark_cancelled("Crave", "2026-08-01")
        r = g.check_charge("Crave", 22.59, "2026-09-12")
        self.assertEqual((r["verdict"], r["recoverable"]), ("charged_after_cancel", 22.59))
        self.assertIn("2026-08-01", g.dispute_pack("Crave")["how_to_use"])

    def test_refunds_are_refunds(self):
        # money-24: 'they charged $-22.59 anyway'; money-25: refunds as alarms
        g = self.guard()
        g.expect_charge("Crave", 22.59)
        g.mark_cancelled("Crave", "2026-08-01")
        g.check_charge("Crave", 22.59, "2026-09-12")
        r = g.check_charge("Crave", -22.59, "2026-09-20")
        self.assertEqual(r["verdict"], "refund")
        p = g.dispute_pack("Crave")
        self.assertEqual((p["amount_in_dispute"], p["refunds_received"]), (0.0, 22.59))
        st = g.review_statement([
            {"merchant": "WALMART #3121 OTTAWA ON", "amount": 84.20, "date": "2026-10-01"},
            {"merchant": "WALMART #3121 OTTAWA ON", "amount": -84.20, "date": "2026-10-03"},
            {"merchant": "CANADIAN TIRE #087", "amount": -30.00, "date": "2026-10-04"}])
        self.assertEqual(st["recoverable_total"], 0.0)
        self.assertTrue(all(f["verdict"] != "refund" for f in st["flagged"]))
        self.assertIn("2 refunds came back ($114.20)", st["summary"])

    def test_a_price_increase_claims_the_increase_and_never_says_unauthorized(self):
        # money-52: $37.98 claimed and 'say plainly ... not authorized'
        g = self.guard()
        g.expect_charge("Netflix", 16.49)
        g.check_charge("Netflix", 16.49, "2026-08-03")
        g.check_charge("Netflix", 18.99, "2026-09-03")
        g.check_charge("Netflix", 18.99, "2026-10-03")
        p = g.dispute_pack("Netflix")
        self.assertEqual(p["amount_in_dispute"], 5.0)
        self.assertNotIn("recurring billing was not authorized", p["how_to_use"])
        self.assertIn("do NOT say it was unauthorized", p["how_to_use"])
        self.assertIn("2026-09-03", p["how_to_use"])

    def test_a_double_bill_that_was_refunded_nets_to_nothing(self):
        # money-26: the pack still demanded $95
        g = self.guard()
        g.expect_charge("Rogers", 95.0)
        g.review_statement([{"merchant": "Rogers", "amount": 95.0, "date": "2026-10-15"},
                            {"merchant": "Rogers", "amount": 95.0, "date": "2026-10-15"},
                            {"merchant": "Rogers", "amount": -95.0, "date": "2026-10-20"}])
        p = g.dispute_pack("Rogers")
        self.assertEqual(p["amount_in_dispute"], 0.0)
        self.assertIn("already refunded", p["how_to_use"])

    def test_the_pack_has_a_deadline_estimate_and_the_right_template(self):
        g = self.guard()
        g.expect_charge("GoodLife Fitness", 59.99)
        g.review_statement([{"merchant": "GoodLife Fitness", "amount": 59.99, "date": "2026-10-01"},
                            {"merchant": "GoodLife Fitness", "amount": 59.99, "date": "2026-10-01"}])
        p = g.dispute_pack("GoodLife Fitness")
        self.assertEqual(p["chargeback_deadline_estimate"], "2027-01-29")
        self.assertIn("2027-01-29", p["how_to_use"])
        self.assertIn("extra charge back", p["how_to_use"])
        self.assertNotIn("not authorized", p["how_to_use"])

    def test_card_testing_goes_to_the_bank_not_into_the_letter(self):
        g = self.guard()
        g.expect_charge("Rogers", 95.0)
        g.check_charge("Rogers", 95.0, "2026-09-15")
        g.check_charge("Rogers", 105.0, "2026-10-15")
        g.check_charge("Rogers", 1.00, "2026-10-20")
        p = g.dispute_pack("Rogers")
        self.assertEqual(p["amount_in_dispute"], 11.0)
        self.assertIn("Ask Rogers for $10.00 back in total", p["how_to_use"])
        self.assertIn("call the bank", p["how_to_use"])

    def test_the_selftest_godaddy_case_keeps_its_full_claim_honestly(self):
        # authorized_recurring=False: the only agreement was $21.99 once, so a
        # $89.97 charge is wholly in question — and the pack says why.
        g = self.guard()
        g.expect_charge("GoDaddy", 21.99, "yearly", authorized_recurring=False)
        r = g.check_charge("GODADDY.COM 480-505-8855", 89.97, "2026-09-02")
        self.assertEqual((r["verdict"], r["recoverable"], r["authorized_on_file"]),
                         ("amount_increased", 89.97, False))
        p = g.dispute_pack("GoDaddy")
        self.assertEqual(p["amount_in_dispute"], 89.97)
        self.assertIn("never agreed to automatic renewal", p["how_to_use"])


# ======================================================================
# I-47  the register is the owner's; tiny charges are not 'fine'
# ======================================================================
class I47Register(Temp):
    def test_a_caretaker_registration_waits_for_the_owner(self):
        g = self.guard(owner=False)
        r = g.expect_charge("PAYPAL *TECHSUPPORT PRO", 499, "yearly")
        self.assertEqual(r["status"], "waiting_for_owner")
        self.assertIn("Not in force yet", r["note"])
        self.assertNotIn("techsupport pro", [e["key"] for e in g.c.data["expected_charges"]])
        c = g.check_charge("PAYPAL *TECHSUPPORT PRO", 499.0, "2026-10-12")
        self.assertNotIn(c["verdict"], ("expected", "amount_decreased"))
        self.assertIn("waiting for the owner", c["what_happened"])
        acts = [a for a in g.c.data["actions"] if a["category"] == "money register"]
        self.assertEqual(len(acts), 1)
        self.assertIn("asked to add PAYPAL *TECHSUPPORT PRO", acts[0]["description"])

    def test_a_caretaker_cannot_silence_a_price_rise(self):
        # money-46: expect_charge('Netflix', 99.99) silenced the rise
        owner = self.guard(owner=True)
        owner.expect_charge("Netflix", 16.49)
        g = Guardian(owner.c, owner_present=lambda: False, today=lambda: TODAY)
        g.expect_charge("Netflix", 99.99)
        self.assertEqual(g.check_charge("Netflix", 99.99, "2026-10-12")["verdict"],
                         "amount_increased")
        self.assertEqual(g.confirm_change(g.pending_changes()[0]["id"]).get("refused"), True)
        self.assertEqual(owner.expected_charges()[0]["amount"], 16.49)

    def test_the_owner_confirms_or_declines(self):
        g = self.guard(owner=False)
        g.expect_charge("Netflix", 16.49)
        g.expect_charge("Spotify", 12.42)
        owner = Guardian(g.c, owner_present=lambda: True, today=lambda: TODAY)
        waiting = owner.pending_changes()
        self.assertEqual(len(waiting), 2)
        self.assertEqual(owner.confirm_change(waiting[0]["id"])["status"], "confirmed")
        self.assertEqual(g.decline_change(waiting[1]["id"])["status"], "declined")
        self.assertEqual([e["merchant"] for e in owner.expected_charges()], ["Netflix"])
        self.assertEqual(owner.pending_changes(), [])
        self.assertEqual(g.check_charge("Netflix", 16.49, "2026-10-03")["verdict"], "expected")

    def test_a_registration_far_above_history_is_questioned_even_for_the_owner(self):
        # money-68: a model's typo registered Rogers at $9,500
        g = self.guard(owner=True)
        g.expect_charge("Rogers", 145.0)
        g.check_charge("Rogers", 145.0, "2026-09-15")
        r = g.expect_charge("Rogers", 9500)
        self.assertEqual(r["status"], "waiting_for_owner")
        self.assertIn("more than ten times", r["note"])
        self.assertEqual(g.expected_charges()[0]["amount"], 145.0)
        self.assertIn("error", g.expect_charge("Netflix", -16.49))

    def test_a_typo_registration_does_not_hide_later_charges(self):
        g = self.guard(owner=True)
        g.expect_charge("Rogers", 9500)                    # no history yet
        got = [g.check_charge("Rogers", a, f"2026-{m:02d}-15")["verdict"]
               for m, a in [(8, 95.0), (9, 145.0), (10, 640.0)]]
        self.assertNotIn("amount_decreased", got)

    def test_card_testing_charges_are_flagged(self):
        # money-09: $1.00 and $0.50 on a $95 bill were 'Nothing to do.'
        g = self.guard()
        g.expect_charge("Rogers", 95.0)
        for amt, d in ((1.00, "2026-10-09"), (0.50, "2026-10-10")):
            r = g.check_charge("ROGERS", amt, d)
            self.assertEqual(r["verdict"], "possible_card_testing")
            self.assertIn("card thieves", r["what_happened"])
            self.assertIn("bank", r["action"])
        self.assertEqual(g.check_charge("Rogers", 90.0, "2026-11-09")["verdict"],
                         "amount_decreased")
        self.assertEqual(g.check_charge("SOME SHOP ONLINE", 0.99, "2026-10-09")["verdict"],
                         "possible_card_testing")

    def test_over_mcp_with_the_caretaker_key(self):
        # money-46 as the stress test ran it: Claude Desktop, key 'jefferey'
        r = self.child("""
            os.environ["JEFFEREY_CLIENT"] = "jefferey"
            import jefferey_mcp as m
            async def go():
                c = lambda n, a: m.mcp.call_tool(n, a)
                e = unpack(await c("expect_charge", {"merchant": "PAYPAL *TECHSUPPORT PRO",
                                                     "amount": 499, "cadence": "yearly"}))
                chk = unpack(await c("check_charge", {"merchant": "PAYPAL *TECHSUPPORT PRO",
                                                      "amount": 499, "date": "2026-10-12"}))
                acts = unpack(await c("action_log", {}))
                return e, chk, acts
            e, chk, acts = asyncio.run(go())
            acts = acts if isinstance(acts, list) else [acts]
            out(note=e.get("note"), verdict=chk["verdict"],
                logged=[a["description"] for a in acts if "TECHSUPPORT" in a.get("description", "")])
        """)
        self.assertIn("Not in force yet", r["note"])
        self.assertNotIn(r["verdict"], ("expected", "amount_decreased"))
        self.assertTrue(any("jefferey asked to add" in d for d in r["logged"]), r)

    def test_over_http_a_request_is_never_the_owner(self):
        # Integration: the owner-console variable no longer exists as a way in
        # (I-04, I-43) — HTTP refuses to start at all when it is set.
        p = subprocess.run([PY, "-c", PRELUDE + "import jefferey_http"], cwd=REPO,
                           env=child_env(self.tmp, JEFFEREY_OWNER_CONSOLE="1",
                                         JEFFEREY_HTTP_TOKENS="jefferey:" + "t" * 40),
                           capture_output=True, text=True, timeout=120)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("will not start", p.stderr)
        r = self.child("""
            os.environ["JEFFEREY_HTTP_TOKENS"] = "jefferey:" + "t" * 40
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            H = {"Authorization": "Bearer " + "t" * 40}
            e = c.post("/charges/expected", json={"merchant": "Netflix", "amount": 99.99}, headers=H).json()
            reg = c.get("/charges/expected", headers=H).json()
            out(note=e.get("note"), active=[x for x in reg if x.get("active")])
        """)
        self.assertIn("Not in force yet", r["note"])
        self.assertEqual(r["active"], [])

    def test_the_review_command_needs_the_owner_at_the_keyboard(self):
        g = self.guard(owner=False)
        g.expect_charge("Netflix", 16.49)
        p = subprocess.run([PY, str(REPO / "connector" / "guardian.py"), "review"], cwd=REPO,
                           env=child_env(self.tmp), input="y\n", capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        c = Conscience(self.tmp / "conscience.json")
        self.assertEqual([x["status"] for x in c.data["charge_proposals"]], ["waiting"])
        # (an empty section is not written to disk — the storage package)
        self.assertEqual(c.data.get("expected_charges", []), [])
        listing = subprocess.run([PY, str(REPO / "connector" / "guardian.py"), "list"], cwd=REPO,
                                 env=child_env(self.tmp), capture_output=True, text=True,
                                 timeout=60)
        self.assertIn("waiting for you to confirm", listing.stdout)


# ======================================================================
# an owner's existing conscience.json keeps working
# ======================================================================
class OldStores(Temp):
    OLD = {
        "_rev": 7, "owner": "Laszlo", "facts": [], "priorities": [], "goals": [],
        "corrections": [], "permissions": {}, "actions": [], "observations": [],
        "opportunities": [],
        "expected_charges": [
            {"key": "netflix ca", "merchant": "NETFLIX.COM 1-800-555-0100 CA", "amount": 18.63,
             "cadence": "Monthly", "authorized_recurring": True, "note": "", "active": True,
             "cancelled_on": None, "updated": "2026-09-01T10:00:00+0000"},
            {"key": "crave", "merchant": "Crave", "amount": 22.59, "cadence": "monthly",
             "authorized_recurring": True, "note": "", "active": False,
             "cancelled_on": "end of the month", "updated": "2026-09-01T10:00:00+0000"},
            {"key": "old gym", "merchant": "Old Gym", "amount": 0.0, "cadence": "unknown",
             "authorized_recurring": False, "note": "cancelled by the user", "active": False,
             "cancelled_on": "2026-06-01", "updated": "2026-06-01T10:00:00+0000"},
        ],
        "charges_seen": (
            [{"key": "netflix", "merchant": "Netflix", "amount": 18.63, "date": "2026-10-03",
              "verdict": "expected" if i == 0 else "duplicate"} for i in range(6)]
            + [{"key": "goodlife fitness", "merchant": "GoodLife Fitness", "amount": 59.99,
                "date": "10/01/2025", "verdict": "expected"}]),
    }

    def write_old(self) -> Path:
        p = self.tmp / "conscience.json"
        p.write_text(json.dumps(self.OLD, indent=2))
        return p

    def test_an_old_store_is_read_upgraded_and_nothing_is_lost(self):
        p = self.write_old()
        before = p.read_bytes()
        g = Guardian(Conscience(p), owner_present=lambda: True, today=lambda: TODAY)
        self.assertEqual(p.read_bytes(), before, "starting must not write")
        reg = g.expected_charges()
        self.assertEqual(len(reg), 3)
        self.assertEqual(reg[0]["key"], "netflix")
        self.assertEqual(reg[0]["key_v1"], "netflix ca")
        self.assertEqual(reg[0]["cadence"], "monthly")
        self.assertEqual(reg[0]["cadence_said"], "Monthly")
        # the old free-text cancellation is kept, and asks instead of accusing
        self.assertIsNone(reg[1]["cancelled_on"])
        self.assertEqual(reg[1]["cancelled_on_said"], "end of the month")
        r = g.check_charge("Crave", 22.59, "2026-10-12")
        self.assertEqual(r["verdict"], "needs_date")
        self.assertEqual(r["recoverable"], 0.0)
        # six saved re-checks of one charge are one charge
        self.assertEqual(g.dispute_pack("Netflix")["amount_in_dispute"], 0.0)
        self.assertEqual(g.check_charge("NETFLIX.COM 866-579-7172 CA", 18.63, "2026-11-03")
                         ["verdict"], "expected")
        # nothing dropped; the old date is kept beside the new one
        seen = g.c.data["charges_seen"]
        self.assertEqual(len(seen), 7 + 2)            # the old seven, plus the two above
        self.assertEqual([r["merchant"] for r in seen[:7]],
                         [r["merchant"] for r in self.OLD["charges_seen"]])
        gym = next(r for r in seen if r["merchant"] == "GoodLife Fitness")
        self.assertEqual((gym["date"], gym["date_said"]), ("2025-10-01", "10/01/2025"))
        # the old code's 'duplicate' verdicts are corrected, and kept beside the new one
        self.assertEqual([r["verdict"] for r in seen[:6]], ["expected"] * 6)
        self.assertEqual([r.get("verdict_before") for r in seen[:6]],
                         ["expected"] + ["duplicate"] * 5)
        # and a later save writes the upgraded shape
        disk = json.loads(p.read_text())
        self.assertTrue(all(e.get("v") == 2 for e in disk["expected_charges"]))
        self.assertEqual(disk["owner"], "Laszlo")

    def test_an_old_unknown_amount_cancellation_stays_armed(self):
        g = Guardian(Conscience(self.write_old()), owner_present=lambda: True,
                     today=lambda: TODAY)
        self.assertEqual(g.check_charge("OLD GYM 4411", 40.0, "2026-05-15")["verdict"],
                         "expected")
        self.assertEqual(g.check_charge("OLD GYM 4411", 40.0, "2026-07-15")["verdict"],
                         "charged_after_cancel")

    def test_ids_never_look_like_a_card_or_insurance_number(self):
        # the egress door withholds a whole result when it sees nine digits in a row
        for i in range(500):
            ident = guardian._ident("c-", str(i))
            self.assertFalse(any(ch.isdigit() for ch in ident[2:]), ident)


if __name__ == "__main__":
    unittest.main()
