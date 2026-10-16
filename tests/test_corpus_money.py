"""
Frozen corpus — the money watch and memberships (R5), repair rounds 6 and 7.

Round 4 took any charge within 85-120% of a membership fee for the fee and
waved everything else through as shopping (real price rises and double
bills were lost). Round 5 took any statement name with a fee word in it for
the fee, whatever the amount. Round 6 took a matching name within 20% of the
fee — and the convergence skeptics found shopping claimed as a double bill
again (four COSTCO GAS fill-ups, '$249.50 at stake'), real rises and double
bills of the fee called 'ordinary shopping' ('COSTCO MEMBERSHIP' $65 then
$130, GoodLife $54.99 then $79.99), the French CAA-QUÉBEC never matched, and
look-alike names (C0STCO, COSTCO-MEMBERSHIP-RENEW.COM, PRIME-RENEWAL-CA.NET)
called 'most likely an ordinary purchase'. This file freezes every
statement the round-4, round-5 and convergence skeptics reported.

The decision (D5, round 7), for a registered membership (a name with
'membership', 'member', 'Prime', 'adhésion' or 'cotisation' in it):

  * A charge is the membership only when its statement name clearly matches
    the registered merchant (accents and punctuation aside: CAA-QUÉBEC is
    CAA QUEBEC; a name that adds another line of business — GAS, WHOLESALE,
    WHSE, TRAVEL, STORE — is not a clear match) AND its amount is the fee,
    or the fee with a Canadian sales tax. A second such charge inside the
    cadence window is a duplicate, claimed at the fee.
  * Any other charge at that merchant whose name carries a membership word
    (member, membership, renewal, annual, Prime, executive, adhésion,
    cotisation, fee …) or whose amount is from 15% below the fee to double
    it is 'ask_owner': nothing claimed, a plain question ('Is this your
    membership going up, or something you bought?'). Round 6 claimed some of
    these as duplicates or rises with 'ask him first', and called others
    shopping; rows marked QUESTION changed their expected outcome for that
    reason, and so did the dispute packs that held them.
  * The rest at that place is shopping: never claimed. A large amount is
    still called large, and a tiny one is still a card test.
  * A name made to look like one he pays is 'ask_owner' with a phishing
    warning (PHISH).

Round 8 (F4) — money after a cancellation, and look-alike bills
(roundD_verdicts.json v2 D5 unsafe_cases and new_regressions):

  * After mark_cancelled, a charge at that membership's place that names the
    membership or sits in the fee band (15% below to double the fee) is
    charged_after_cancel and claimed in full, as before round 7; any other
    charge there after the cancellation asks him (CANCELLED below). Round 7
    asked 'Is this your membership going up?' and claimed nothing.
  * A duplicate claim — a second charge inside the cadence — needs a
    membership word in its name or the very same amount as the first;
    otherwise it is his question. Rows that claimed the fee with tax on top
    of the fee ('CAA SOUTH CENTRAL ONT' $120 then $135.60) ask now.
  * Once a charge of a membership is on file, the agreed amount is the
    amount last charged: a different one asks, even when it is the fee with
    some tax ('AMAZON PRIME' $99, then $111.87 a year later).
  * French lines of business (assurance, voyages, essence, carburant,
    pharmacie, optique, pneus, épicerie, station) are another business, like
    insurance, travel and gas.
  * Statement names are read through the shared fold (a Cyrillic 'CОSTCO' is
    made to look like Costco: a phishing question) and lose a payment
    processor's prefix (PAYPAL *, PP*, SQ *, SP *, TST*, STRIPE*) before they
    are matched — but such a line, or a name glued to a fee word
    ('COSTCOMEMBER'), is never by itself the membership: it asks him, and it
    is never the first bill (round 8 repair), until he says the line is his
    (name_for_charge, confirmed at his keyboard). A variant of a registered name (the same first word:
    'GOODLIFE CLUBS' for 'GOODLIFE FITNESS') at the fee inside the cadence
    asks 'Is this a second bill?'.

A plain plan (no membership word: 'Costco' $65 yearly, Norton, Netflix)
keeps the I-38 rule: a second charge inside a long period is a second bill —
claimed when it is at the first one's amount or names a membership word,
and otherwise his question (round 8, F4; round 7 claimed it with 'ask him
first'). Its bill under a shorter form of its name at another price ('ROGERS'
for 'Rogers internet', 29% more) is 'ask_owner' too.
"""

from __future__ import annotations

import datetime as dt
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "connector"))

from conscience import Conscience        # noqa: E402
from guardian import Guardian, QUIET, RECOVERABLE     # noqa: E402

TODAY = dt.date(2026, 10, 15)
NOCLAIM = "no claim"      # any verdict that claims nothing (shopping, quiet, a 'did you mean')
ASK, LARGE, QUESTION, PHISH = "ask", "large", "question", "phish"

COSTCO = ("Costco Membership", 65.00, "yearly")
PRIME = ("Amazon Prime", 99.00, "yearly")
CAA = ("CAA Membership", 120.00, "yearly")
GYM = ("GoodLife Membership", 54.99, "monthly")

# (what it is, registrations, lines checked one by one with check_charge:
#  (statement name, amount, date, verdict, recoverable, flag), dispute pack
#  for the first registration or None)
CHECKS: list[tuple] = [
    # round 4, the original report and ShoppingIsNotTheMembership
    ("costco shopping, no fee billed yet", [COSTCO], [
        ("COSTCO WHSE #0545", 120.31, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHSE #0545", 64.20, "2026-09-10", "ask_owner", 0.0, QUESTION),
        ("COSTCO.CA", 89.99, "2026-09-20", "ask_owner", 0.0, QUESTION)], 0.0),
    ("costco shopping after the fee, then the fee again", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO WHSE #0545", 120.31, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHSE #0545", 64.20, "2026-09-10", "ask_owner", 0.0, QUESTION),
        ("COSTCO.CA", 89.99, "2026-09-20", "ask_owner", 0.0, QUESTION),
        ("COSTCO MEMBERSHIP", 65.00, "2026-09-25", "duplicate", 65.00, "")], 65.00),
    # round 4 verify-b (k/r5a.py)
    ("near-fee purchases after the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO.CA", 71.18, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("COSTCO", 60.40, "2026-09-10", "ask_owner", 0.0, QUESTION),
        ("COSTCO GAS #123", 70.10, "2026-09-12", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHOLESALE", 68.00, "2026-09-14", "ask_owner", 0.0, QUESTION)], None),
    ("Amazon Prime and Amazon shopping", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01", "expected", 0.0, ""),
        ("AMAZON.CA", 45.67, "2026-09-03", NOCLAIM, 0.0, ""),
        ("AMAZON.CA", 104.50, "2026-09-10", NOCLAIM, 0.0, ""),
        ("AMZN MKTP CA", 89.99, "2026-09-12", NOCLAIM, 0.0, ""),
        ("AMAZON PRIME", 99.00, "2026-09-20", "duplicate", 99.00, "")], 99.00),
    ("a 'renewal' and an 'executive membership' far from the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("COSTCO EXECUTIVE MEMBERSHIP", 130.00, "2026-09-10", "ask_owner", 0.0, QUESTION)],
     0.0),
    ("French registration", [("Adhésion Costco", 65.00, "annuel")], [
        ("COSTCO ENTREPOT", 120.31, "2026-09-03", NOCLAIM, 0.0, ""),
        ("COSTCO.CA", 89.99, "2026-09-20", NOCLAIM, 0.0, ""),
        ("COSTCO", 64.20, "2026-09-25", NOCLAIM, 0.0, "")], None),
    ("CAA shopping and a near-fee charge", [CAA], [
        ("CAA MEMBERSHIP", 120.00, "2026-08-01", "expected", 0.0, ""),
        ("CAA STORE", 45.00, "2026-09-03", "unexpected_merchant", 0.0, ""),
        ("CAA TRAVEL", 1200.00, "2026-09-10", "unexpected_merchant", 0.0, LARGE),
        ("CAA", 110.00, "2026-09-12", "ask_owner", 0.0, QUESTION)], 0.00),
    ("gym billed twice, then a small extra", [GYM], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-02", "duplicate", 54.99, ""),
        ("GOODLIFE FITNESS", 25.00, "2026-09-05", "unexpected_merchant", 0.0, "")], 54.99),
    # round 4 verify-b: a plain registration (no membership word) keeps the
    # plain-plan rule, and asks first when the amount is not the agreed one
    # (round 8, F4: a second charge inside the year with no membership word and
    # not at the first one's amount is his question, not a claim)
    ("plain 'Costco' yearly plan", [("Costco", 65.00, "yearly")], [
        ("COSTCO", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO.CA", 89.99, "2026-09-20", "ask_owner", 0.0, QUESTION),
        ("COSTCO", 120.31, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("COSTCO GAS", 70.10, "2026-09-12", "unexpected_merchant", 0.0, "")], None),
    # round 4 verify-c (skep/gu.py): real rises and double bills of the fee
    ("Prime 79 -> 99 a year later", [("Amazon Prime membership", 79.00, "yearly")], [
        ("AMAZON PRIME", 79.00, "2025-10-01", "expected", 0.0, ""),
        ("AMAZON PRIME", 99.00, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.00),
    ("Prime (no member word) 79 -> 99", [("Amazon Prime", 79.00, "yearly")], [
        ("AMAZON PRIME", 79.00, "2025-10-01", "expected", 0.0, ""),
        ("AMAZON PRIME", 99.00, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.00),
    ("gym 54.99 -> 69.99", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-08-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 69.99, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.00),
    ("gym double bill", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-02", "duplicate", 54.99, "")], 54.99),
    ("gym charge of twice the fee", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 109.98, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("one-dollar card tests under the membership's name", [COSTCO], [
        ("COSTCO MEMBERSHIP", 1.00, "2026-09-01", "possible_card_testing", 1.00, ""),
        ("COSTCO MEMBERSHIP", 1.00, "2026-09-02", "possible_card_testing", 1.00, "")], None),
    ("costco 65 -> 130 'membership'", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2025-10-01", "expected", 0.0, ""),
        ("COSTCO MEMBERSHIP", 130.00, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("CAA 120 then 180 inside the year", [("CAA membership", 120.00, "yearly")], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-03-01", "expected", 0.0, ""),
        ("CAA SOUTH CENTRAL ONT", 180.00, "2026-09-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("netflix rise (a plain plan)", [("Netflix", 18.63, "monthly")], [
        ("NETFLIX.COM", 18.63, "2026-08-01", "expected", 0.0, ""),
        ("NETFLIX.COM", 18.63, "2026-09-01", "expected", 0.0, ""),
        ("NETFLIX.COM", 24.99, "2026-10-01", "amount_increased", 6.36, "")], 6.36),
    ("the fee billed at the warehouse, then a grocery run", [COSTCO], [
        ("COSTCO WHOLESALE W539", 65.00, "2026-09-01", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHSE #0545", 120.31, "2026-09-03", "ask_owner", 0.0, QUESTION)], 0.0),
    ("Sun Life 150 -> 200", [("Sun Life member health plan", 150.00, "monthly")], [
        ("SUN LIFE", 150.00, "2026-08-01", "expected", 0.0, ""),
        ("SUN LIFE", 150.00, "2026-09-01", "expected", 0.0, ""),
        ("SUN LIFE", 200.00, "2026-10-01", NOCLAIM, 0.0, "")], None),
    # round 5 verify-b (p/r5.py, p/r5b.py)
    ("Prime Video and Prime Now", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01", "expected", 0.0, ""),
        ("AMAZON PRIME VIDEO", 5.99, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("PRIME VIDEO CHANNELS", 8.99, "2026-09-05", NOCLAIM, 0.0, ""),
        ("AMAZON PRIME NOW", 85.40, "2026-09-10", "ask_owner", 0.0, QUESTION)], 0.00),
    ("CAA insurance named 'annual' and 'renewal'", [CAA], [
        ("CAA MEMBERSHIP", 120.00, "2026-08-01", "expected", 0.0, ""),
        ("CAA TRAVEL INSURANCE ANNUAL PLAN", 300.00, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("CAA INSURANCE RENEWAL", 1100.00, "2026-09-10", "ask_owner", 0.0, LARGE)], 0.0),
    ("the fee with tax at the warehouse, then a rise", [COSTCO], [
        ("COSTCO WHOLESALE W539", 73.45, "2025-10-01", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHOLESALE W539", 79.10, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.00),
    ("a first warehouse charge above the fee, then again the next day", [COSTCO], [
        ("COSTCO WHOLESALE W539", 79.10, "2026-10-01", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHOLESALE W539", 79.10, "2026-10-02", "ask_owner", 0.0, QUESTION)], None),
    ("the fee with tax checked twice is one charge", [COSTCO], [
        ("COSTCO WHOLESALE W539", 73.45, "2026-10-01", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHOLESALE W539", 73.45, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("French membership at double the fee", [("Adhésion Costco", 65.00, "annuel")], [
        ("COSTCO ADHESION", 65.00, "2025-10-01", NOCLAIM, 0.0, ""),
        ("COSTCO ADHESION", 130.00, "2026-10-01", NOCLAIM, 0.0, ""),
        ("COSTCO ENTREPOT", 120.31, "2026-10-03", NOCLAIM, 0.0, "")], None),
    ("costco shopping under fee words", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO MEMBER SERVICES", 45.00, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("COSTCO ANNUAL SALE", 180.00, "2026-09-12", "ask_owner", 0.0, QUESTION),
        ("COSTCO.CA SUBSCRIPTION BOX", 49.99, "2026-09-20", "ask_owner", 0.0, QUESTION)],
     0.0),
    ("gym personal training", [GYM], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 100.00, "2026-09-05", "ask_owner", 0.0, QUESTION),
        ("GOODLIFE FITNESS", 54.99, "2026-10-01", "expected", 0.0, "")], 0.0),
    ("costco shopping under fee words, again", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO.CA SUBSCRIPTION BOX", 89.99, "2026-09-20", "ask_owner", 0.0, QUESTION),
        ("COSTCO MEMBER SERVICES", 110.00, "2026-09-22", "ask_owner", 0.0, QUESTION)], 0.0),
    ("Prime Now near the fee, Prime Day deal far from it", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01", "expected", 0.0, ""),
        ("AMAZON PRIME NOW", 129.00, "2026-09-10", "ask_owner", 0.0, QUESTION),
        ("AMAZON.CA PRIME DAY DEAL", 150.00, "2026-09-12", "ask_owner", 0.0, QUESTION)],
     0.00),
    ("a Prime name at exactly the fee", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01", "expected", 0.0, ""),
        ("AMZN PRIME VIDEO RENTAL", 99.00, "2026-09-10", "duplicate", 99.00, "")], 99.00),
    ("CAA member store and member travel", [CAA], [
        ("CAA MEMBERSHIP", 120.00, "2026-08-01", "expected", 0.0, ""),
        ("CAA MEMBER STORE", 180.00, "2026-09-10", "ask_owner", 0.0, QUESTION),
        ("CAA MEMBER SAVINGS TRAVEL", 120.00, "2026-09-12", "ask_owner", 0.0, QUESTION)], 0.00),
    ("the membership billed twice", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO MEMBERSHIP", 65.00, "2026-09-01", "duplicate", 65.00, "")], 65.00),
    # round 5 verify-c (sk5/s_money.py)
    # 'Costco Executive' is not how 'COSTCO WHOLESALE' starts: a place not in
    # his register (he can name it with name_for_charge), and nothing claimed
    ("Executive membership at the warehouse, then groceries",
     [("Costco Executive Membership", 130.00, "yearly")], [
        ("COSTCO WHOLESALE W551", 146.90, "2026-01-10", NOCLAIM, 0.0, ""),
        ("COSTCO WHOLESALE W551", 212.45, "2026-06-01", "unexpected_merchant", 0.0, ""),
        ("COSTCO WHOLESALE W551", 98.30, "2026-07-01", "unexpected_merchant", 0.0, "")], 0.0),
    ("Prime Video channel and a Prime order", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-02-01", "expected", 0.0, ""),
        ("PRIME VIDEO CHANNELS", 5.99, "2026-09-03", NOCLAIM, 0.0, ""),
        ("AMAZON PRIME*2K3LX", 64.99, "2026-09-05", "ask_owner", 0.0, QUESTION)], 0.0),
    ("gym extra the same month", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-08-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 80.00, "2026-09-12", "ask_owner", 0.0, QUESTION),
        ("GOODLIFE FITNESS", 54.99, "2026-10-01", "expected", 0.0, "")], 0.0),
    ("CAA store, then the fee again by another name", [("CAA membership", 120.00, "yearly")], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-03-01", "expected", 0.0, ""),
        ("CAA SOUTH CENTRAL ONT", 25.00, "2026-09-01", "unexpected_merchant", 0.0, ""),
        ("CAA ANNUAL FEE", 120.00, "2026-09-02", "duplicate", 120.00, "")], 120.00),
    ("Costco 'annual sale' near the fee, and a member price TV", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01", "expected", 0.0, ""),
        ("COSTCO ANNUAL SALE EVENT", 79.99, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("COSTCO MEMBER PRICE", 899.00, "2026-09-04", "ask_owner", 0.0, LARGE)], 0.00),
    ("netflix rise, again", [("Netflix", 16.49, "monthly")], [
        ("NETFLIX.COM", 16.49, "2026-08-10", "expected", 0.0, ""),
        ("NETFLIX.COM", 16.49, "2026-09-10", "expected", 0.0, ""),
        ("NETFLIX.COM", 20.99, "2026-10-10", "amount_increased", 4.50, "")], 4.50),
    # round 5 verify-c (sk5/s_money2.py): the fee billed under two names
    ("CAA billed again as a renewal", [("CAA membership", 120.00, "yearly")], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-03-01", "expected", 0.0, ""),
        ("CAA MEMBERSHIP RENEWAL", 120.00, "2026-09-02", "duplicate", 120.00, "")], 120.00),
    ("CAA billed again as an annual fee with tax", [("CAA membership", 120.00, "yearly")], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-03-01", "expected", 0.0, ""),
        ("CAA ANNUAL FEE", 135.60, "2026-09-02", "duplicate", 120.00, "")], 120.00),
    ("Costco billed again at the warehouse", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-03-01", "expected", 0.0, ""),
        ("COSTCO WHOLESALE W551", 65.00, "2026-09-02", "ask_owner", 0.0, QUESTION)], 0.00),
    ("Costco billed again at the warehouse with tax", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-03-01", "expected", 0.0, ""),
        ("COSTCO WHOLESALE W551", 73.45, "2026-09-02", "ask_owner", 0.0, QUESTION)], 0.00),
    ("gym billed again as its membership", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-03-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS MEMBERSHIP", 54.99, "2026-03-20", "duplicate", 54.99, "")], 54.99),
    ("Prime billed twice", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-03-01", "expected", 0.0, ""),
        ("AMAZON PRIME", 99.00, "2026-09-02", "duplicate", 99.00, "")], 99.00),
    ("CAA billed twice under its plain name", [("CAA membership", 120.00, "yearly")], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-03-01", "expected", 0.0, ""),
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-09-02", "duplicate", 120.00, "")], 120.00),
    # round 5 verify-c (sk5/s_money3.py)
    *[(f"Prime, then {m} {a}", [PRIME], [
        ("Amazon.ca Prime Member amazon.ca/pm", 99.00, "2026-02-01", "expected", 0.0, ""),
        (m, a, "2026-09-03", v, rec, fl)], None)
      for m, a, v, rec, fl in [
          ("AMAZON.CA SUBSCRIPTION", 11.99, NOCLAIM, 0.0, ""),
          ("Amazon.ca Prime Member amazon.ca/pm", 99.00, "duplicate", 99.00, ""),
          ("AMAZON PRIME VIDEO", 3.99, "ask_owner", 0.0, QUESTION),
          ("AMAZON.CA ANNUAL KINDLE", 109.00, NOCLAIM, 0.0, ""),
          ("AMZN MKTP CA", 89.99, NOCLAIM, 0.0, ""),
          ("AMAZON.CA", 99.00, "ask_owner", 0.0, QUESTION),
          ("AMAZON.CA MEMBER DEAL", 45.00, NOCLAIM, 0.0, ""),
          ("AMAZON PRIME DAY", 129.99, "ask_owner", 0.0, QUESTION)]],
    *[(f"Costco, then {m} {a}", [("Costco membership", 65.00, "yearly")], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01", "expected", 0.0, ""),
        (m, a, "2026-09-03", v, rec, fl)], None)
      for m, a, v, rec, fl in [
          ("COSTCO WHOLESALE W551", 65.00, "ask_owner", 0.0, QUESTION),
          ("COSTCO GAS W551", 72.15, "ask_owner", 0.0, QUESTION),
          ("COSTCO.CA", 130.00, "ask_owner", 0.0, QUESTION),
          ("COSTCO MBR SVCS", 65.00, "duplicate", 65.00, "")]],
    # round 7, the convergence skeptics (converge.json vb/vc R5)
    ("gym 54.99 -> 79.99 on its billing day", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-08-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 79.99, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("gym two months billed at once", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 109.98, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("a grocery run near the fee at the warehouse", [COSTCO], [
        ("COSTCO WHOLESALE W551", 65.00, "2026-02-01", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHOLESALE W551", 60.12, "2026-06-01", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHOLESALE W551", 78.00, "2026-06-02", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHOLESALE W551", 72.00, "2026-09-04", "ask_owner", 0.0, QUESTION),
        ("COSTCO WHOLESALE W551", 212.45, "2026-09-10", "unexpected_merchant", 0.0, "")], 0.0),
    ("Prime 99 -> 143.55 a year later", [PRIME], [
        ("AMAZON PRIME", 99.00, "2025-10-01", "expected", 0.0, ""),
        ("AMAZON PRIME", 143.55, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("Prime 99 -> 129 a year later", [PRIME], [
        ("AMAZON PRIME", 99.00, "2025-10-01", "expected", 0.0, ""),
        ("AMAZON PRIME", 129.00, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    # (round 8, F4: once $99 is on file, $99 is the agreed amount — the fee
    # with tax a year later is his to say about)
    ("Prime with sales tax a year after the fee", [PRIME], [
        ("AMAZON PRIME", 99.00, "2025-10-01", "expected", 0.0, ""),
        ("AMAZON PRIME", 111.87, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("Prime with Quebec tax, first bill", [PRIME], [
        ("AMAZON PRIME", 113.83, "2026-10-01", "expected", 0.0, "")], 0.0),
    ("CAA-Québec billed twice, in French", [("CAA-Québec adhésion", 95.00, "yearly")], [
        ("CAA-QUEBEC", 95.00, "2026-03-01", "expected", 0.0, ""),
        ("CAA QUEBEC COTISATION", 95.00, "2026-09-01", "duplicate", 95.00, "")], 95.00),
    ("CAA-Québec under its accents", [("CAA-Québec adhésion", 95.00, "yearly")], [
        ("CAA-QUÉBEC", 95.00, "2026-03-01", "expected", 0.0, ""),
        ("C.A.A. QUEBEC", 95.00, "2026-03-20", "duplicate", 95.00, "")], 95.00),
    ("a first CAA bill above the fee", [CAA], [
        ("CAA SOUTH CENTRAL ONT", 150.00, "2026-09-15", "ask_owner", 0.0, QUESTION)], 0.0),
    ("CAA renewal twice in two weeks", [CAA], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-09-01", "expected", 0.0, ""),
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-09-15", "duplicate", 120.00, "")], 120.00),
    # (round 8, F4: no membership word and not the same amount as the first:
    # his question, not a claim)
    ("CAA again with tax", [CAA], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-03-01", "expected", 0.0, ""),
        ("CAA SOUTH CENTRAL ONT", 135.60, "2026-09-15", "ask_owner", 0.0, QUESTION)], 0.0),
    ("gym billed again ten days later, with tax", [("GoodLife Fitness membership", 54.99,
                                                    "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 62.14, "2026-09-11", "ask_owner", 0.0, QUESTION)], 0.0),
    ("a card test and a year paid ahead at the gym",
     [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 1.00, "2026-10-02", "possible_card_testing", 1.00, ""),
        ("GOODLIFE FITNESS", 549.99, "2026-10-03", "unexpected_merchant", 0.0, LARGE),
        ("PLANET FITNESS", 54.99, "2026-10-04", "unexpected_merchant", 0.0, ""),
        ("GOODLIFE FITNESS", -54.99, "2026-10-05", "refund", 0.0, "")], None),
    ("a plan's bill under a shorter name, 29% more", [("Rogers internet", 85.00, "monthly")], [
        ("ROGERS", 85.00, "2026-08-05", "expected", 0.0, ""),
        ("ROGERS", 85.00, "2026-09-05", "expected", 0.0, ""),
        ("ROGERS", 110.00, "2026-10-05", "ask_owner", 0.0, QUESTION)], 0.0),
    # ...look-alike names at the fee: asked, with a phishing warning
    *[(f"Costco, then the look-alike {m} {a}", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01", "expected", 0.0, ""),
        (m, a, "2026-09-03", v, 0.0, fl)], 0.0)
      for m, a, v, fl in [
          ("COSTCO-MEMBERSHIP-RENEW.COM", 65.00, "ask_owner", PHISH),
          ("C0STCO MEMBERSHIP", 65.00, "ask_owner", PHISH),
          ("COSTCO.NET", 65.00, "ask_owner", PHISH),
          ("C0STC0 WH0LESALE", 120.00, "ask_owner", PHISH),
          ("COSTCO-RENEWAL-CENTER.COM", 12.00, "ask_owner", PHISH),
          ("COSTCO.CA", 89.99, "ask_owner", QUESTION),
          ("COSTCO.CA", 25.00, "unexpected_merchant", "")]],
    *[(f"Prime, then the look-alike {m} {a}", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-02-01", "expected", 0.0, ""),
        (m, a, "2026-09-03", v, 0.0, fl)], 0.0)
      for m, a, v, fl in [
          ("PRIME-RENEWAL-CA.NET", 99.00, "ask_owner", PHISH),
          ("AMAZONPRIME-HELP.COM", 99.00, "ask_owner", PHISH),
          ("AMAZ0N PRIME", 99.00, "ask_owner", PHISH),
          ("AMAZON.CA", 45.67, "unexpected_merchant", "")]],
    ("a look-alike gym", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("G00DLIFE FITNESS", 54.99, "2026-09-03", "ask_owner", 0.0, PHISH)], 0.0),
    # ---------------------------------------------------------- round 8 (F4)
    # v2 D5 unsafe_cases: the fee with 11% or 13% tax after the fee, with no
    # membership word, was a $65 duplicate claimed without asking
    ("the fee with tax after the fee, under shopping names", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO.CA", 72.15, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("COSTCO", 73.45, "2026-09-10", "ask_owner", 0.0, QUESTION)], 0.0),
    # ...French insurance at the fee was a $95 duplicate (v2 new_regressions)
    ("CAA-Québec, then its insurance at the fee", [("CAA-Québec adhésion", 95.00, "yearly")], [
        ("CAA-QUEBEC", 95.00, "2026-01-05", "expected", 0.0, ""),
        ("CAA-QUEBEC ASSURANCE", 95.00, "2026-03-01", "ask_owner", 0.0, QUESTION)], 0.0),
    *[(f"CAA, then {m} at the fee", [CAA], [
        ("CAA MEMBERSHIP", 120.00, "2026-02-01", "expected", 0.0, ""),
        (m, 120.00, "2026-09-03", "ask_owner", 0.0, QUESTION)], 0.0)
      for m in ("CAA VOYAGES", "CAA ASSURANCES", "CAA STATION")],
    *[(f"Costco, then {m} at the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01", "expected", 0.0, ""),
        (m, 65.00, "2026-09-03", "ask_owner", 0.0, QUESTION)], 0.0)
      for m in ("COSTCO ESSENCE", "COSTCO CARBURANT", "COSTCO PHARMACIE", "COSTCO OPTIQUE",
                "COSTCO PNEUS", "COSTCO EPICERIE")],
    # ...a rise that lands on the fee with tax read 'as agreed. Quiet.'
    ("gym 54.99 -> 63.24, the fee with 15% tax", [("GoodLife Fitness membership", 54.99,
                                                   "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-08-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 63.24, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("Prime registered with its tax, then more", [("Amazon Prime", 111.87, "yearly")], [
        ("AMAZON PRIME", 111.87, "2025-10-01", "expected", 0.0, ""),
        ("AMAZON PRIME", 128.65, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    ("the gym's fee with tax, every month", [("GoodLife Fitness membership", 54.99,
                                              "monthly")], [
        ("GOODLIFE FITNESS", 62.14, "2026-08-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 62.14, "2026-09-01", "expected", 0.0, "")], 0.0),
    # ...look-alikes the decision promised to catch
    ("a Cyrillic Costco at the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01", "expected", 0.0, ""),
        ("C\u041eSTCO MEMBERSHIP", 65.00, "2026-09-03", "ask_owner", 0.0, PHISH)], 0.0),
    # Round 8 repair (F4): a line billed through a payment processor, or a name
    # read only by splitting a word glued to a fee word, is never by itself
    # his membership — anyone can call a PayPal or Square account
    # 'COSTCOMEMBER' — so it is his question, and nothing is claimed from the
    # membership for it (round 8 claimed $65 and $54.99 here, and a pack that
    # asked Costco to refund what PayPal's account holder had charged)
    ("the membership through PayPal", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01", "expected", 0.0, ""),
        ("PAYPAL *COSTCOMEMBER", 65.00, "2026-09-03", "ask_owner", 0.0, QUESTION)], 0.0),
    ("the gym through Square and Stripe", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("SQ *GOODLIFE FITNESS", 54.99, "2026-09-03", "ask_owner", 0.0, QUESTION),
        ("STRIPE*GOODLIFE FITNESS", 54.99, "2026-10-01", "ask_owner", 0.0, QUESTION)], 0.0),
    # ...the skeptic's P2: the processor's line first, then the real bill,
    # which stays as agreed (round 8 called it a $65 duplicate)
    ("PayPal first, then the real membership", [COSTCO], [
        ("PAYPAL *COSTCOMEMBER", 65.00, "2026-02-01", "ask_owner", 0.0, QUESTION),
        ("COSTCO MEMBERSHIP", 65.00, "2026-03-01", "expected", 0.0, "")], 0.0),
    ("a second bill under a variant name", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE CLUBS", 54.99, "2026-09-06", "ask_owner", 0.0, QUESTION)], 0.0),
    ("a variant name a month on is a place not in his register",
     [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-08-01", "expected", 0.0, ""),
        ("GOODLIFE CLUBS", 54.99, "2026-09-06", "unexpected_merchant", 0.0, "")], None),
    # the large-amount warning stays on (round 4 verify-b)
    ("large charges where he holds memberships", [PRIME, CAA], [
        ("AMAZON.CA", 1499.99, "2026-09-03", "unexpected_merchant", 0.0, LARGE),
        ("CAA TRAVEL", 1200.00, "2026-09-03", "unexpected_merchant", 0.0, LARGE)], None),
]

# (what it is, registrations, statement lines, the lines flagged:
#  (name, amount, date, verdict, recoverable), recoverable_total)
STATEMENTS: list[tuple] = [
    # round 4 verify-b (k/r5b.py)
    ("the original statement", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01"), ("COSTCO WHSE #0545", 120.31, "2026-09-03"),
        ("COSTCO WHSE #0545", 64.20, "2026-09-10"), ("COSTCO.CA", 89.99, "2026-09-20")],
     [("COSTCO WHSE #0545", 120.31, "2026-09-03", "ask_owner", 0.00),
      ("COSTCO WHSE #0545", 64.20, "2026-09-10", "ask_owner", 0.00),
      ("COSTCO.CA", 89.99, "2026-09-20", "ask_owner", 0.00)], 0.00),
    ("three shopping lines and no fee", [COSTCO], [
        ("COSTCO WHSE #0545", 120.31, "2026-09-03"), ("COSTCO WHSE #0545", 64.20, "2026-09-10"),
        ("COSTCO.CA", 89.99, "2026-09-20")],
     [("COSTCO WHSE #0545", 120.31, "2026-09-03", "ask_owner", 0.00),
      ("COSTCO WHSE #0545", 64.20, "2026-09-10", "ask_owner", 0.00),
      ("COSTCO.CA", 89.99, "2026-09-20", "ask_owner", 0.00)], 0.00),
    ("near-fee shopping after the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01"), ("COSTCO.CA", 66.10, "2026-09-03"),
        ("COSTCO", 70.00, "2026-09-10"), ("COSTCO.CA", 58.20, "2026-09-20")],
     [("COSTCO.CA", 66.10, "2026-09-03", "ask_owner", 0.00),
      ("COSTCO", 70.00, "2026-09-10", "ask_owner", 0.00),
      ("COSTCO.CA", 58.20, "2026-09-20", "ask_owner", 0.00)], 0.00),
    ("a large Amazon order beside Prime", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01"), ("AMAZON.CA", 1499.99, "2026-09-03")],
     [("AMAZON.CA", 1499.99, "2026-09-03", "unexpected_merchant", 0.0)], 0.0),
    ("a large Amazon order, nothing registered", [], [("AMAZON.CA", 1499.99, "2026-09-03")],
     [("AMAZON.CA", 1499.99, "2026-09-03", "unexpected_merchant", 0.0)], 0.0),
    ("a 'renewal' far from the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01"),
        ("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-03")],
     [("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-03", "ask_owner", 0.00)], 0.00),
    ("CAA travel", [CAA], [("CAA TRAVEL", 1200.00, "2026-09-10")],
     [("CAA TRAVEL", 1200.00, "2026-09-10", "unexpected_merchant", 0.0)], 0.0),
    # round 4 verify-b (k/r5c.py): three memberships on one statement
    ("three memberships, one statement", [COSTCO, PRIME, CAA], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01"), ("COSTCO.CA", 66.10, "2026-09-03"),
        ("COSTCO", 70.00, "2026-09-10"), ("COSTCO.CA", 58.20, "2026-09-20"),
        ("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-25"), ("AMAZON PRIME", 99.00, "2026-08-01"),
        ("AMAZON.CA", 1499.99, "2026-09-03"), ("CAA TRAVEL", 1200.00, "2026-09-10")],
     [("COSTCO.CA", 66.10, "2026-09-03", "ask_owner", 0.00),
      ("COSTCO", 70.00, "2026-09-10", "ask_owner", 0.00),
      ("COSTCO.CA", 58.20, "2026-09-20", "ask_owner", 0.00),
      ("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-25", "ask_owner", 0.00),
      ("AMAZON.CA", 1499.99, "2026-09-03", "unexpected_merchant", 0.00),
      ("CAA TRAVEL", 1200.00, "2026-09-10", "unexpected_merchant", 0.00)], 0.00),
    # round 5 verify-b (p/r5.py, p/r5c.py, p/r5d.py)
    ("the fee with tax twice at the warehouse, and a grocery run", [COSTCO], [
        ("COSTCO WHOLESALE W539", 73.45, "2026-10-01"), ("COSTCO WHOLESALE W539", 73.45, "2026-10-01"),
        ("COSTCO WHOLESALE W539", 120.31, "2026-10-03")],
     [("COSTCO WHOLESALE W539", 73.45, "2026-10-01", "ask_owner", 0.00),
      ("COSTCO WHOLESALE W539", 73.45, "2026-10-01", "ask_owner", 0.00),
      ("COSTCO WHOLESALE W539", 120.31, "2026-10-03", "ask_owner", 0.00)], 0.00),
    ("Prime, the gym and CAA, with fee words in other lines", [PRIME, GYM, CAA], [
        ("AMAZON PRIME", 99.00, "2026-08-01"), ("AMAZON PRIME NOW", 129.00, "2026-09-10"),
        ("AMAZON PRIME NOW", 64.10, "2026-09-17"), ("GOODLIFE FITNESS", 54.99, "2026-09-01"),
        ("GOODLIFE FITNESS ANNUAL FEE", 49.99, "2026-09-15"), ("GOODLIFE FITNESS", 54.99, "2026-10-01"),
        ("CAA MEMBERSHIP", 120.00, "2026-08-01"), ("CAA SERVICE FEE", 150.00, "2026-09-03")],
     [("AMAZON PRIME NOW", 129.00, "2026-09-10", "ask_owner", 0.00),
      ("AMAZON PRIME NOW", 64.10, "2026-09-17", "ask_owner", 0.00),
      ("GOODLIFE FITNESS ANNUAL FEE", 49.99, "2026-09-15", "ask_owner", 0.00),
      ("CAA SERVICE FEE", 150.00, "2026-09-03", "ask_owner", 0.00)], 0.00),
    ("the gym billed twice, an annual-fee line and a rise", [GYM], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01"), ("GOODLIFE FITNESS", 54.99, "2026-09-01"),
        ("GOODLIFE FITNESS ANNUAL FEE", 49.99, "2026-09-15"), ("GOODLIFE FITNESS", 69.99, "2026-10-01")],
     [("GOODLIFE FITNESS", 54.99, "2026-09-01", "duplicate", 54.99),
      ("GOODLIFE FITNESS ANNUAL FEE", 49.99, "2026-09-15", "ask_owner", 0.00),
      ("GOODLIFE FITNESS", 69.99, "2026-10-01", "ask_owner", 0.00)], 54.99),
    ("the gym billed twice and a rise", [GYM], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01"), ("GOODLIFE FITNESS", 54.99, "2026-09-01"),
        ("GOODLIFE FITNESS", 69.99, "2026-10-01")],
     [("GOODLIFE FITNESS", 54.99, "2026-09-01", "duplicate", 54.99),
      ("GOODLIFE FITNESS", 69.99, "2026-10-01", "ask_owner", 0.00)], 54.99),
    ("the fee named as such, then billed twice at the warehouse", [COSTCO], [
        ("COSTCO MEMBERSHIP FEE", 65.00, "2025-10-01"), ("COSTCO WHOLESALE #539", 73.45, "2026-10-01"),
        ("COSTCO WHOLESALE #539", 73.45, "2026-10-01")],
     [("COSTCO WHOLESALE #539", 73.45, "2026-10-01", "ask_owner", 0.00),
      ("COSTCO WHOLESALE #539", 73.45, "2026-10-01", "ask_owner", 0.00)], 0.00),
    # round 5 verify-c (sk5/s_money.py, s_money2.py)
    ("Executive membership and groceries at the warehouse",
     [("Costco Executive Membership", 130.00, "yearly")], [
        ("COSTCO WHOLESALE W551", 146.90, "2026-09-02"), ("COSTCO WHOLESALE W551", 187.12, "2026-09-15"),
        ("COSTCO WHOLESALE W551", 76.40, "2026-09-28")],
     [("COSTCO WHOLESALE W551", 146.90, "2026-09-02", "unexpected_merchant", 0.0),
      ("COSTCO WHOLESALE W551", 187.12, "2026-09-15", "unexpected_merchant", 0.0),
      ("COSTCO WHOLESALE W551", 76.40, "2026-09-28", "unexpected_merchant", 0.0)], 0.0),
    ("CAA billed under two names on one statement", [("CAA membership", 120.00, "yearly")], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-09-01"), ("CAA MEMBERSHIP RENEWAL", 120.00, "2026-09-20")],
     [("CAA MEMBERSHIP RENEWAL", 120.00, "2026-09-20", "duplicate", 120.00)], 120.00),
    ("CAA under two names, the second with tax", [("CAA membership", 120.00, "yearly")], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-09-01"), ("CAA ANNUAL FEE", 135.60, "2026-09-20")],
     [("CAA ANNUAL FEE", 135.60, "2026-09-20", "duplicate", 120.00)], 120.00),
    ("the gym under two names on one statement",
     [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01"), ("GOODLIFE FITNESS MEMBERSHIP", 54.99, "2026-09-20")],
     [("GOODLIFE FITNESS MEMBERSHIP", 54.99, "2026-09-20", "duplicate", 54.99)], 54.99),
    # round 7, the convergence skeptics (converge.json vb R5, sk7/r5.py, r5b.py)
    ("four fill-ups at the warehouse gas bar", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01"), ("COSTCO GAS W551", 58.40, "2026-03-03"),
        ("COSTCO GAS W551", 61.10, "2026-03-17"), ("COSTCO GAS W551", 66.10, "2026-04-02"),
        ("COSTCO GAS W551", 70.25, "2026-04-20")],
     [("COSTCO GAS W551", 58.40, "2026-03-03", "ask_owner", 0.00),
      ("COSTCO GAS W551", 61.10, "2026-03-17", "ask_owner", 0.00),
      ("COSTCO GAS W551", 66.10, "2026-04-02", "ask_owner", 0.00),
      ("COSTCO GAS W551", 70.25, "2026-04-20", "ask_owner", 0.00)], 0.00),
    ("a month of Costco shopping", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01"), ("COSTCO WHOLESALE W551", 58.20, "2026-03-03"),
        ("COSTCO WHOLESALE W551", 71.45, "2026-03-17"), ("COSTCO WHOLESALE W551", 66.10, "2026-04-02"),
        ("COSTCO GAS W551", 62.00, "2026-04-09")],
     [("COSTCO WHOLESALE W551", 58.20, "2026-03-03", "ask_owner", 0.00),
      ("COSTCO WHOLESALE W551", 71.45, "2026-03-17", "ask_owner", 0.00),
      ("COSTCO WHOLESALE W551", 66.10, "2026-04-02", "ask_owner", 0.00),
      ("COSTCO GAS W551", 62.00, "2026-04-09", "ask_owner", 0.00)], 0.00),
    ("the gym billed twice, then a rise", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-08-01"), ("GOODLIFE FITNESS", 54.99, "2026-09-01"),
        ("GOODLIFE FITNESS", 54.99, "2026-09-01"), ("GOODLIFE FITNESS", 79.99, "2026-10-01")],
     [("GOODLIFE FITNESS", 54.99, "2026-09-01", "duplicate", 54.99),
      ("GOODLIFE FITNESS", 79.99, "2026-10-01", "ask_owner", 0.00)], 54.99),
    # (round 8, F4: 'AMZN MKTP CA' is a variant of the Amazon name, at the fee,
    # inside the year: 'Is this a second bill?')
    ("Prime and Amazon shopping", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-02-01"), ("AMAZON.CA", 104.50, "2026-03-03"),
        ("AMAZON.CA PRIME", 89.99, "2026-03-09"), ("AMZN MKTP CA", 99.00, "2026-04-02")],
     [("AMAZON.CA", 104.50, "2026-03-03", "ask_owner", 0.00),
      ("AMAZON.CA PRIME", 89.99, "2026-03-09", "ask_owner", 0.00),
      ("AMZN MKTP CA", 99.00, "2026-04-02", "ask_owner", 0.00)], 0.00),
    ("CAA under two names in one year", [CAA], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-02-01"), ("CAA ONTARIO MBR", 120.00, "2026-08-01")],
     [("CAA ONTARIO MBR", 120.00, "2026-08-01", "duplicate", 120.00)], 120.00),
    ("a look-alike renewal beside the real fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01"),
        ("COSTCO-MEMBERSHIP-RENEW.COM", 65.00, "2026-09-03")],
     [("COSTCO-MEMBERSHIP-RENEW.COM", 65.00, "2026-09-03", "ask_owner", 0.00)], 0.00),
    ("Costco under two names on one statement", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-09-01"), ("COSTCO WHOLESALE W551", 73.45, "2026-09-20")],
     [("COSTCO WHOLESALE W551", 73.45, "2026-09-20", "ask_owner", 0.00)], 0.00),
]


# Round 8 (F4): after mark_cancelled (v2 new_regressions D5 [MEDIUM]):
# (what it is, registration, the charge before, cancelled on, the charge
#  after, verdict, recoverable, dispute pack)
CANCELLED: list[tuple] = [
    ("the gym at a new price", ("GoodLife Fitness membership", 54.99, "monthly"),
     ("GOODLIFE FITNESS", 54.99, "2026-08-01"), "2026-09-01",
     ("GOODLIFE FITNESS", 59.99, "2026-10-01"), "charged_after_cancel", 59.99, 59.99),
    ("the gym's annual fee", ("GoodLife Fitness membership", 54.99, "monthly"),
     ("GOODLIFE FITNESS", 54.99, "2026-08-01"), "2026-09-01",
     ("GOODLIFE FITNESS ANNUAL FEE", 49.99, "2026-10-01"), "charged_after_cancel", 49.99, 49.99),
    ("the gym's fee itself", ("GoodLife Fitness membership", 54.99, "monthly"),
     ("GOODLIFE FITNESS", 54.99, "2026-08-01"), "2026-09-01",
     ("GOODLIFE FITNESS", 54.99, "2026-10-01"), "charged_after_cancel", 54.99, 54.99),
    ("Costco renewed at $70", ("Costco Membership", 65.00, "yearly"),
     ("COSTCO MEMBERSHIP", 65.00, "2025-10-01"), "2026-03-01",
     ("COSTCO MEMBERSHIP", 70.00, "2026-10-01"), "charged_after_cancel", 70.00, 70.00),
    ("Prime renewed at $129", ("Amazon Prime", 99.00, "yearly"),
     ("AMAZON PRIME", 99.00, "2025-10-01"), "2026-03-01",
     ("AMAZON PRIME", 129.00, "2026-10-01"), "charged_after_cancel", 129.00, 129.00),
    ("a plain plan, as before", ("Netflix", 16.49, "monthly"),
     ("NETFLIX.COM", 16.49, "2026-08-01"), "2026-09-01",
     ("NETFLIX.COM", 18.99, "2026-10-01"), "charged_after_cancel", 18.99, 18.99),
    ("a smoothie at the gym after it", ("GoodLife Fitness membership", 54.99, "monthly"),
     ("GOODLIFE FITNESS", 54.99, "2026-08-01"), "2026-09-01",
     ("GOODLIFE FITNESS", 12.50, "2026-10-01"), "ask_owner", 0.0, 0.0),
    ("groceries at the warehouse after it", ("Costco Membership", 65.00, "yearly"),
     ("COSTCO MEMBERSHIP", 65.00, "2025-10-01"), "2026-03-01",
     ("COSTCO WHOLESALE W551", 212.45, "2026-10-01"), "ask_owner", 0.0, 0.0),
]


class _Money(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-corpus-money-"))
        self.n = 0

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def guard(self, regs) -> Guardian:
        self.n += 1
        g = Guardian(Conscience(self.tmp / f"c{self.n}.json"), owner_present=lambda: True,
                     today=lambda: TODAY)
        for r in regs:
            g.expect_charge(*r)
        return g


class AMembershipIsMatchedByItsAmountAndItsName(_Money):

    def test_every_charge_the_skeptics_named(self):
        wrong = []
        for title, regs, lines, pack in CHECKS:
            g = self.guard(regs)
            for name, amt, date, verdict, rec, flag in lines:
                r = g.check_charge(name, amt, date)
                problems = []
                if verdict == NOCLAIM:
                    if r["verdict"] in RECOVERABLE or r["recoverable"] != 0.0:
                        problems.append("claims")
                elif (r["verdict"], r["recoverable"]) != (verdict, round(rec, 2)):
                    problems.append("verdict")
                said = r["what_happened"]
                if flag == ASK and not r["action"].startswith("Ask him first"):
                    problems.append("does not ask him first")
                if flag != ASK and r["action"].startswith("Ask him first"):
                    problems.append("asks first for no reason")
                if flag == LARGE and "large amount" not in said:
                    problems.append("lost the large-amount warning")
                if r["verdict"] == "ask_owner":
                    if not r.get("question") or r["question"] not in said:
                        problems.append("asks no plain question")
                    if not r["action"].startswith("Ask him"):
                        problems.append("the action does not say to ask him")
                    if "scam" in said.lower() or "fraud" in said.lower():
                        problems.append("accuses")
                if flag == PHISH and ("made to look like" not in said or "phishing" not in said):
                    problems.append("no phishing warning")
                if flag != PHISH and "phishing" in said:
                    problems.append("a phishing warning for no reason")
                if problems:
                    wrong.append((title, name, amt, date, problems, r["verdict"],
                                  r["recoverable"], said[:160], r["action"][:60]))
            if pack is not None:
                got = g.dispute_pack(regs[0][0])["amount_in_dispute"]
                if round(got, 2) != round(pack, 2):
                    wrong.append((title, "dispute pack", got, "want", pack))
        self.assertEqual(wrong, [], f"{len(wrong)} charges:\n" + "\n".join(map(repr, wrong)))

    def test_every_statement_the_skeptics_named(self):
        wrong = []
        for title, regs, lines, flagged, total in STATEMENTS:
            st = self.guard(regs).review_statement(
                [{"merchant": m, "amount": a, "date": d} for m, a, d in lines])
            got = Counter((f["merchant"], f["amount"], f["date"], f["verdict"], f["recoverable"])
                          for f in st["flagged"])
            want = Counter((m, a, d, v, round(r, 2)) for m, a, d, v, r in flagged)
            if got != want or round(st["recoverable_total"], 2) != round(total, 2):
                wrong.append((title, "got", sorted(got.elements()), st["recoverable_total"],
                              "want", sorted(want.elements()), total))
        self.assertEqual(wrong, [], f"{len(wrong)} statements:\n" + "\n".join(map(repr, wrong)))

    def test_a_duplicate_never_claims_more_than_the_fee(self):
        for title, regs, lines, _, _ in STATEMENTS:
            fees = {r[0]: r[1] for r in regs}
            st = self.guard(regs).review_statement(
                [{"merchant": m, "amount": a, "date": d} for m, a, d in lines])
            for f in st["flagged"]:
                if f["verdict"] == "duplicate" and f.get("matched_to") in fees:
                    self.assertLessEqual(f["recoverable"], fees[f["matched_to"]] + 0.001,
                                         (title, f))
            for f in st["flagged"]:
                if f["verdict"] == "unexpected_merchant":
                    self.assertEqual(f["recoverable"], 0.0, (title, f))

    def test_the_dispute_pack_claims_nothing_he_has_not_answered(self):
        # round 6 claimed this $66.10 at the fee with 'ask him first'; under
        # D5 it is his question, and the pack holds nothing for it
        g = self.guard([COSTCO])
        g.check_charge("COSTCO MEMBERSHIP", 65.00, "2026-08-01")
        g.check_charge("COSTCO.CA", 66.10, "2026-09-03")
        p = g.dispute_pack("Costco Membership")
        self.assertEqual(p["amount_in_dispute"], 0.0, p)
        self.assertIn("for his answer", p["how_to_use"])
        self.assertIn("something he bought", p["how_to_use"])
        # ...and when he says it is not his, it is claimed in full, by the bank
        p = g.dispute_pack("Costco Membership", not_mine=True)
        self.assertEqual(p["amount_in_dispute"], 66.10, p)
        self.assertIn("bank", p["how_to_use"])

    def test_a_statement_of_questions_says_so_and_puts_nothing_at_stake(self):
        st = self.guard([COSTCO]).review_statement([
            {"merchant": m, "amount": a, "date": d} for m, a, d in (
                ("COSTCO MEMBERSHIP", 65.00, "2026-02-01"), ("COSTCO GAS W551", 58.40, "2026-03-03"),
                ("COSTCO GAS W551", 61.10, "2026-03-17"), ("COSTCO GAS W551", 66.10, "2026-04-02"),
                ("COSTCO GAS W551", 70.25, "2026-04-20"))])
        self.assertEqual(st["recoverable_total"], 0.0, st)
        self.assertEqual(st["questions"], 4, st)
        self.assertNotIn("at stake", st["summary"])
        self.assertIn("Nothing is claimed until you say", st["summary"])
        rise = self.guard([("GoodLife Fitness membership", 54.99, "monthly")])
        rise.check_charge("GOODLIFE FITNESS", 54.99, "2026-09-01")
        r = rise.check_charge("GOODLIFE FITNESS", 79.99, "2026-10-01")
        self.assertEqual(r["question"], "Is this your membership going up, or something you bought?")
        fake = self.guard([COSTCO]).review_statement([
            {"merchant": "C0STCO MEMBERSHIP", "amount": 65.00, "date": "2026-09-03"}])
        self.assertIn("made to look like one you pay", fake["summary"])

    def test_a_charge_after_a_cancelled_membership_is_claimed_again(self):
        wrong = []
        for title, reg, before, on, after, verdict, rec, pack in CANCELLED:
            g = self.guard([reg])
            g.check_charge(*before)
            g.mark_cancelled(reg[0], on)
            r = g.check_charge(*after)
            got = (r["verdict"], r["recoverable"], g.dispute_pack(reg[0])["amount_in_dispute"])
            if got != (verdict, rec, pack):
                wrong.append((title, got, "want", (verdict, rec, pack), r["what_happened"][:160]))
            if verdict == "ask_owner" and not (r.get("question") and r["question"] in
                                               r["what_happened"]):
                wrong.append((title, "asks no plain question", r["what_happened"][:160]))
            st = self.guard([reg])
            st.check_charge(*before)
            st.mark_cancelled(reg[0], on)
            s = st.review_statement([{"merchant": after[0], "amount": after[1],
                                      "date": after[2]}])
            if round(s["recoverable_total"], 2) != round(rec, 2):
                wrong.append((title, "statement", s["recoverable_total"], s["summary"][:120]))
        self.assertEqual(wrong, [], "\n".join(map(repr, wrong)))

    def test_a_second_bill_under_a_variant_name_is_asked_about_plainly(self):
        g = self.guard([("GoodLife Fitness membership", 54.99, "monthly")])
        g.check_charge("GOODLIFE FITNESS", 54.99, "2026-09-01")
        r = g.check_charge("GOODLIFE CLUBS", 54.99, "2026-09-06")
        self.assertEqual(r["verdict"], "ask_owner", r)
        self.assertEqual(r["question"], "Is this a second bill?", r)
        self.assertIn("GoodLife Fitness membership", r["what_happened"])
        self.assertEqual(r["recoverable"], 0.0)

    def test_the_same_charge_checked_again_asks_whether_it_shows_twice(self):
        # money-14: one at a time, a second identical charge cannot be told
        # from the same charge checked again; he is asked, never told
        g = self.guard([("GoodLife Fitness membership", 54.99, "monthly")])
        g.check_charge("GOODLIFE FITNESS", 54.99, "2026-10-01")
        r = g.check_charge("GOODLIFE FITNESS", 54.99, "2026-10-01")
        self.assertTrue(r["already_on_file"], r)
        self.assertIn("ask him", r["what_happened"])
        self.assertIn("review_statement", r["what_happened"])
        st = self.guard([("GoodLife Fitness membership", 54.99, "monthly")]).review_statement([
            {"merchant": "GOODLIFE FITNESS", "amount": 54.99, "date": "2026-10-01"},
            {"merchant": "GOODLIFE FITNESS", "amount": 54.99, "date": "2026-10-01"}])
        self.assertEqual(st["recoverable_total"], 54.99, st)


if __name__ == "__main__":
    unittest.main()
