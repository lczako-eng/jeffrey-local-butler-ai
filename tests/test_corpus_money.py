"""
Frozen corpus — the money watch and memberships (R5), repair round 6.

Round 4 took any charge within 85-120% of a membership fee for the fee and
waved everything else through as shopping (real price rises and double
bills were lost). Round 5 took any statement name with a fee word in it for
the fee, whatever the amount ('AMAZON PRIME NOW' $129 and 'CAA SERVICE FEE'
$150 were claimed in full), and once one charge said 'membership', the same
fee billed under the plain name was 'shopping' ('CAA SOUTH CENTRAL ONT' then
'CAA MEMBERSHIP RENEWAL' — a real double bill — was quiet). This file
freezes every statement the round-4 and round-5 skeptics reported, with the
outcome the structural rule gives.

The structural rule, for a registered membership (a name with 'membership',
'member', 'Prime', 'adhésion' or 'cotisation' in it):

  * A charge is the fee only when its statement name matches the registered
    merchant AND its amount is within 20% of the fee, or of the fee with a
    Canadian sales tax on it. A fee word in the statement name ('fee',
    'annual', 'renewal', 'Prime', 'member') never makes a charge the fee by
    itself.
  * Two such charges inside one cadence window are a duplicate, whatever the
    two statement names. JEFFEREY never claims more than the registered fee
    for one duplicate, and when the amount is not the fee itself it asks him
    first ('if this was shopping there, nothing is wrong').
  * Everything else at that merchant is shopping: never claimed, never a
    price rise. A large amount is still called large, a tiny one is still a
    card test, and a name that speaks of a membership, a fee or a renewal at
    another price is pointed out for him to look at ('Prime' in an Amazon
    Prime name is the merchant's own name, not a fee word).

A plain plan (no membership word: 'Costco' $65 yearly, Norton, Netflix)
keeps the I-38 rule: a second charge inside a long period is a second bill,
whatever the amount — and when the amount is not the agreed one, he is asked
first.
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
ASK, LARGE, LOOK = "ask", "large", "look"

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
        ("COSTCO WHSE #0545", 120.31, "2026-09-03", "unexpected_merchant", 0.0, ""),
        ("COSTCO WHSE #0545", 64.20, "2026-09-10", "amount_decreased", 0.0, ""),
        ("COSTCO.CA", 89.99, "2026-09-20", "unexpected_merchant", 0.0, "")], 0.0),
    ("costco shopping after the fee, then the fee again", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO WHSE #0545", 120.31, "2026-09-03", "unexpected_merchant", 0.0, ""),
        ("COSTCO WHSE #0545", 64.20, "2026-09-10", "duplicate", 64.20, ASK),
        ("COSTCO.CA", 89.99, "2026-09-20", "unexpected_merchant", 0.0, ""),
        ("COSTCO MEMBERSHIP", 65.00, "2026-09-25", "duplicate", 65.00, "")], 129.20),
    # round 4 verify-b (k/r5a.py)
    ("near-fee purchases after the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO.CA", 71.18, "2026-09-03", "duplicate", 65.00, ASK),
        ("COSTCO", 60.40, "2026-09-10", "duplicate", 60.40, ASK),
        ("COSTCO GAS #123", 70.10, "2026-09-12", "duplicate", 65.00, ASK),
        ("COSTCO WHOLESALE", 68.00, "2026-09-14", "duplicate", 65.00, ASK)], None),
    ("Amazon Prime and Amazon shopping", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01", "expected", 0.0, ""),
        ("AMAZON.CA", 45.67, "2026-09-03", NOCLAIM, 0.0, ""),
        ("AMAZON.CA", 104.50, "2026-09-10", NOCLAIM, 0.0, ""),
        ("AMZN MKTP CA", 89.99, "2026-09-12", NOCLAIM, 0.0, ""),
        ("AMAZON PRIME", 99.00, "2026-09-20", "duplicate", 99.00, "")], 99.00),
    ("a 'renewal' and an 'executive membership' far from the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-03", "unexpected_merchant", 0.0, LOOK),
        ("COSTCO EXECUTIVE MEMBERSHIP", 130.00, "2026-09-10", "unexpected_merchant", 0.0, LOOK)],
     0.0),
    ("French registration", [("Adhésion Costco", 65.00, "annuel")], [
        ("COSTCO ENTREPOT", 120.31, "2026-09-03", NOCLAIM, 0.0, ""),
        ("COSTCO.CA", 89.99, "2026-09-20", NOCLAIM, 0.0, ""),
        ("COSTCO", 64.20, "2026-09-25", NOCLAIM, 0.0, "")], None),
    ("CAA shopping and a near-fee charge", [CAA], [
        ("CAA MEMBERSHIP", 120.00, "2026-08-01", "expected", 0.0, ""),
        ("CAA STORE", 45.00, "2026-09-03", "unexpected_merchant", 0.0, ""),
        ("CAA TRAVEL", 1200.00, "2026-09-10", "unexpected_merchant", 0.0, LARGE),
        ("CAA", 110.00, "2026-09-12", "duplicate", 110.00, ASK)], 110.00),
    ("gym billed twice, then a small extra", [GYM], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-02", "duplicate", 54.99, ""),
        ("GOODLIFE FITNESS", 25.00, "2026-09-05", "unexpected_merchant", 0.0, "")], 54.99),
    # round 4 verify-b: a plain registration (no membership word) keeps the
    # plain-plan rule, and asks first when the amount is not the agreed one
    ("plain 'Costco' yearly plan", [("Costco", 65.00, "yearly")], [
        ("COSTCO", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO.CA", 89.99, "2026-09-20", "duplicate", 89.99, ASK),
        ("COSTCO", 120.31, "2026-09-03", "duplicate", 120.31, ASK),
        ("COSTCO GAS", 70.10, "2026-09-12", "unexpected_merchant", 0.0, "")], None),
    # round 4 verify-c (skep/gu.py): real rises and double bills of the fee
    ("Prime 79 -> 99 a year later", [("Amazon Prime membership", 79.00, "yearly")], [
        ("AMAZON PRIME", 79.00, "2025-10-01", "expected", 0.0, ""),
        ("AMAZON PRIME", 99.00, "2026-10-01", "amount_increased", 20.00, ASK)], 20.00),
    ("Prime (no member word) 79 -> 99", [("Amazon Prime", 79.00, "yearly")], [
        ("AMAZON PRIME", 79.00, "2025-10-01", "expected", 0.0, ""),
        ("AMAZON PRIME", 99.00, "2026-10-01", "amount_increased", 20.00, ASK)], 20.00),
    ("gym 54.99 -> 69.99", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-08-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 69.99, "2026-10-01", "amount_increased", 15.00, ASK)], 15.00),
    ("gym double bill", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-02", "duplicate", 54.99, "")], 54.99),
    ("gym charge of twice the fee", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 109.98, "2026-10-01", "unexpected_merchant", 0.0, "")], 0.0),
    ("one-dollar card tests under the membership's name", [COSTCO], [
        ("COSTCO MEMBERSHIP", 1.00, "2026-09-01", "possible_card_testing", 1.00, ""),
        ("COSTCO MEMBERSHIP", 1.00, "2026-09-02", "possible_card_testing", 1.00, "")], None),
    ("costco 65 -> 130 'membership'", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2025-10-01", "expected", 0.0, ""),
        ("COSTCO MEMBERSHIP", 130.00, "2026-10-01", "unexpected_merchant", 0.0, LOOK)], 0.0),
    ("CAA 120 then 180 inside the year", [("CAA membership", 120.00, "yearly")], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-03-01", "expected", 0.0, ""),
        ("CAA SOUTH CENTRAL ONT", 180.00, "2026-09-01", "unexpected_merchant", 0.0, "")], 0.0),
    ("netflix rise (a plain plan)", [("Netflix", 18.63, "monthly")], [
        ("NETFLIX.COM", 18.63, "2026-08-01", "expected", 0.0, ""),
        ("NETFLIX.COM", 18.63, "2026-09-01", "expected", 0.0, ""),
        ("NETFLIX.COM", 24.99, "2026-10-01", "amount_increased", 6.36, "")], 6.36),
    ("the fee billed at the warehouse, then a grocery run", [COSTCO], [
        ("COSTCO WHOLESALE W539", 65.00, "2026-09-01", "expected", 0.0, ""),
        ("COSTCO WHSE #0545", 120.31, "2026-09-03", "unexpected_merchant", 0.0, "")], 0.0),
    ("Sun Life 150 -> 200", [("Sun Life member health plan", 150.00, "monthly")], [
        ("SUN LIFE", 150.00, "2026-08-01", "expected", 0.0, ""),
        ("SUN LIFE", 150.00, "2026-09-01", "expected", 0.0, ""),
        ("SUN LIFE", 200.00, "2026-10-01", NOCLAIM, 0.0, "")], None),
    # round 5 verify-b (p/r5.py, p/r5b.py)
    ("Prime Video and Prime Now", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01", "expected", 0.0, ""),
        ("AMAZON PRIME VIDEO", 5.99, "2026-09-03", "unexpected_merchant", 0.0, ""),
        ("PRIME VIDEO CHANNELS", 8.99, "2026-09-05", NOCLAIM, 0.0, ""),
        ("AMAZON PRIME NOW", 85.40, "2026-09-10", "duplicate", 85.40, ASK)], 85.40),
    ("CAA insurance named 'annual' and 'renewal'", [CAA], [
        ("CAA MEMBERSHIP", 120.00, "2026-08-01", "expected", 0.0, ""),
        ("CAA TRAVEL INSURANCE ANNUAL PLAN", 300.00, "2026-09-03", "unexpected_merchant", 0.0,
         LOOK),
        ("CAA INSURANCE RENEWAL", 1100.00, "2026-09-10", "unexpected_merchant", 0.0, LARGE)], 0.0),
    ("the fee with tax at the warehouse, then a rise", [COSTCO], [
        ("COSTCO WHOLESALE W539", 73.45, "2025-10-01", "expected", 0.0, ""),
        ("COSTCO WHOLESALE W539", 79.10, "2026-10-01", "amount_increased", 5.65, ASK)], 5.65),
    ("a first warehouse charge above the fee, then again the next day", [COSTCO], [
        ("COSTCO WHOLESALE W539", 79.10, "2026-10-01", "amount_increased", 14.10, ASK),
        ("COSTCO WHOLESALE W539", 79.10, "2026-10-02", "duplicate", 65.00, ASK)], None),
    ("the fee with tax checked twice is one charge", [COSTCO], [
        ("COSTCO WHOLESALE W539", 73.45, "2026-10-01", "expected", 0.0, ""),
        ("COSTCO WHOLESALE W539", 73.45, "2026-10-01", "expected", 0.0, "")], 0.0),
    ("French membership at double the fee", [("Adhésion Costco", 65.00, "annuel")], [
        ("COSTCO ADHESION", 65.00, "2025-10-01", NOCLAIM, 0.0, ""),
        ("COSTCO ADHESION", 130.00, "2026-10-01", NOCLAIM, 0.0, ""),
        ("COSTCO ENTREPOT", 120.31, "2026-10-03", NOCLAIM, 0.0, "")], None),
    ("costco shopping under fee words", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO MEMBER SERVICES", 45.00, "2026-09-03", "unexpected_merchant", 0.0, LOOK),
        ("COSTCO ANNUAL SALE", 180.00, "2026-09-12", "unexpected_merchant", 0.0, LOOK),
        ("COSTCO.CA SUBSCRIPTION BOX", 49.99, "2026-09-20", "unexpected_merchant", 0.0, LOOK)],
     0.0),
    ("gym personal training", [GYM], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 100.00, "2026-09-05", "unexpected_merchant", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-10-01", "expected", 0.0, "")], 0.0),
    ("costco shopping under fee words, again", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01", "expected", 0.0, ""),
        ("COSTCO.CA SUBSCRIPTION BOX", 89.99, "2026-09-20", "unexpected_merchant", 0.0, LOOK),
        ("COSTCO MEMBER SERVICES", 110.00, "2026-09-22", "unexpected_merchant", 0.0, LOOK)], 0.0),
    ("Prime Now near the fee, Prime Day deal far from it", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01", "expected", 0.0, ""),
        ("AMAZON PRIME NOW", 129.00, "2026-09-10", "duplicate", 99.00, ASK),
        ("AMAZON.CA PRIME DAY DEAL", 150.00, "2026-09-12", "unexpected_merchant", 0.0, "")],
     99.00),
    ("a Prime name at exactly the fee", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01", "expected", 0.0, ""),
        ("AMZN PRIME VIDEO RENTAL", 99.00, "2026-09-10", "duplicate", 99.00, "")], 99.00),
    ("CAA member store and member travel", [CAA], [
        ("CAA MEMBERSHIP", 120.00, "2026-08-01", "expected", 0.0, ""),
        ("CAA MEMBER STORE", 180.00, "2026-09-10", "unexpected_merchant", 0.0, LOOK),
        ("CAA MEMBER SAVINGS TRAVEL", 120.00, "2026-09-12", "duplicate", 120.00, "")], 120.00),
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
        ("AMAZON PRIME*2K3LX", 64.99, "2026-09-05", "unexpected_merchant", 0.0, "")], 0.0),
    ("gym extra the same month", [("GoodLife Fitness membership", 54.99, "monthly")], [
        ("GOODLIFE FITNESS", 54.99, "2026-08-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-09-01", "expected", 0.0, ""),
        ("GOODLIFE FITNESS", 80.00, "2026-09-12", "unexpected_merchant", 0.0, ""),
        ("GOODLIFE FITNESS", 54.99, "2026-10-01", "expected", 0.0, "")], 0.0),
    ("CAA store, then the fee again by another name", [("CAA membership", 120.00, "yearly")], [
        ("CAA SOUTH CENTRAL ONT", 120.00, "2026-03-01", "expected", 0.0, ""),
        ("CAA SOUTH CENTRAL ONT", 25.00, "2026-09-01", "unexpected_merchant", 0.0, ""),
        ("CAA ANNUAL FEE", 120.00, "2026-09-02", "duplicate", 120.00, "")], 120.00),
    ("Costco 'annual sale' near the fee, and a member price TV", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01", "expected", 0.0, ""),
        ("COSTCO ANNUAL SALE EVENT", 79.99, "2026-09-03", "duplicate", 65.00, ASK),
        ("COSTCO MEMBER PRICE", 899.00, "2026-09-04", "unexpected_merchant", 0.0, LARGE)], 65.00),
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
        ("COSTCO WHOLESALE W551", 65.00, "2026-09-02", "duplicate", 65.00, "")], 65.00),
    ("Costco billed again at the warehouse with tax", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-03-01", "expected", 0.0, ""),
        ("COSTCO WHOLESALE W551", 73.45, "2026-09-02", "duplicate", 65.00, "")], 65.00),
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
          ("AMAZON PRIME VIDEO", 3.99, "unexpected_merchant", 0.0, ""),
          ("AMAZON.CA ANNUAL KINDLE", 109.00, NOCLAIM, 0.0, ""),
          ("AMZN MKTP CA", 89.99, NOCLAIM, 0.0, ""),
          ("AMAZON.CA", 99.00, "duplicate", 99.00, ""),
          ("AMAZON.CA MEMBER DEAL", 45.00, NOCLAIM, 0.0, ""),
          ("AMAZON PRIME DAY", 129.99, "duplicate", 99.00, ASK)]],
    *[(f"Costco, then {m} {a}", [("Costco membership", 65.00, "yearly")], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-02-01", "expected", 0.0, ""),
        (m, a, "2026-09-03", v, rec, fl)], None)
      for m, a, v, rec, fl in [
          ("COSTCO WHOLESALE W551", 65.00, "duplicate", 65.00, ""),
          ("COSTCO GAS W551", 72.15, "duplicate", 65.00, ""),
          ("COSTCO.CA", 130.00, "unexpected_merchant", 0.0, ""),
          ("COSTCO MBR SVCS", 65.00, "duplicate", 65.00, "")]],
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
     [("COSTCO WHSE #0545", 120.31, "2026-09-03", "unexpected_merchant", 0.0),
      ("COSTCO WHSE #0545", 64.20, "2026-09-10", "duplicate", 64.20),
      ("COSTCO.CA", 89.99, "2026-09-20", "unexpected_merchant", 0.0)], 64.20),
    ("three shopping lines and no fee", [COSTCO], [
        ("COSTCO WHSE #0545", 120.31, "2026-09-03"), ("COSTCO WHSE #0545", 64.20, "2026-09-10"),
        ("COSTCO.CA", 89.99, "2026-09-20")],
     [("COSTCO WHSE #0545", 120.31, "2026-09-03", "unexpected_merchant", 0.0),
      ("COSTCO.CA", 89.99, "2026-09-20", "unexpected_merchant", 0.0)], 0.0),
    ("near-fee shopping after the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01"), ("COSTCO.CA", 66.10, "2026-09-03"),
        ("COSTCO", 70.00, "2026-09-10"), ("COSTCO.CA", 58.20, "2026-09-20")],
     [("COSTCO.CA", 66.10, "2026-09-03", "duplicate", 65.00),
      ("COSTCO", 70.00, "2026-09-10", "duplicate", 65.00),
      ("COSTCO.CA", 58.20, "2026-09-20", "duplicate", 58.20)], 188.20),
    ("a large Amazon order beside Prime", [PRIME], [
        ("AMAZON PRIME", 99.00, "2026-08-01"), ("AMAZON.CA", 1499.99, "2026-09-03")],
     [("AMAZON.CA", 1499.99, "2026-09-03", "unexpected_merchant", 0.0)], 0.0),
    ("a large Amazon order, nothing registered", [], [("AMAZON.CA", 1499.99, "2026-09-03")],
     [("AMAZON.CA", 1499.99, "2026-09-03", "unexpected_merchant", 0.0)], 0.0),
    ("a 'renewal' far from the fee", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01"),
        ("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-03")],
     [("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-03", "unexpected_merchant", 0.0)], 0.0),
    ("CAA travel", [CAA], [("CAA TRAVEL", 1200.00, "2026-09-10")],
     [("CAA TRAVEL", 1200.00, "2026-09-10", "unexpected_merchant", 0.0)], 0.0),
    # round 4 verify-b (k/r5c.py): three memberships on one statement
    ("three memberships, one statement", [COSTCO, PRIME, CAA], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-08-01"), ("COSTCO.CA", 66.10, "2026-09-03"),
        ("COSTCO", 70.00, "2026-09-10"), ("COSTCO.CA", 58.20, "2026-09-20"),
        ("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-25"), ("AMAZON PRIME", 99.00, "2026-08-01"),
        ("AMAZON.CA", 1499.99, "2026-09-03"), ("CAA TRAVEL", 1200.00, "2026-09-10")],
     [("COSTCO.CA", 66.10, "2026-09-03", "duplicate", 65.00),
      ("COSTCO", 70.00, "2026-09-10", "duplicate", 65.00),
      ("COSTCO.CA", 58.20, "2026-09-20", "duplicate", 58.20),
      ("COSTCO MEMBERSHIP RENEWAL", 199.99, "2026-09-25", "unexpected_merchant", 0.0),
      ("AMAZON.CA", 1499.99, "2026-09-03", "unexpected_merchant", 0.0),
      ("CAA TRAVEL", 1200.00, "2026-09-10", "unexpected_merchant", 0.0)], 188.20),
    # round 5 verify-b (p/r5.py, p/r5c.py, p/r5d.py)
    ("the fee with tax twice at the warehouse, and a grocery run", [COSTCO], [
        ("COSTCO WHOLESALE W539", 73.45, "2026-10-01"), ("COSTCO WHOLESALE W539", 73.45, "2026-10-01"),
        ("COSTCO WHOLESALE W539", 120.31, "2026-10-03")],
     [("COSTCO WHOLESALE W539", 73.45, "2026-10-01", "duplicate", 65.00),
      ("COSTCO WHOLESALE W539", 120.31, "2026-10-03", "unexpected_merchant", 0.0)], 65.00),
    ("Prime, the gym and CAA, with fee words in other lines", [PRIME, GYM, CAA], [
        ("AMAZON PRIME", 99.00, "2026-08-01"), ("AMAZON PRIME NOW", 129.00, "2026-09-10"),
        ("AMAZON PRIME NOW", 64.10, "2026-09-17"), ("GOODLIFE FITNESS", 54.99, "2026-09-01"),
        ("GOODLIFE FITNESS ANNUAL FEE", 49.99, "2026-09-15"), ("GOODLIFE FITNESS", 54.99, "2026-10-01"),
        ("CAA MEMBERSHIP", 120.00, "2026-08-01"), ("CAA SERVICE FEE", 150.00, "2026-09-03")],
     [("AMAZON PRIME NOW", 129.00, "2026-09-10", "duplicate", 99.00),
      ("AMAZON PRIME NOW", 64.10, "2026-09-17", "unexpected_merchant", 0.0),
      ("GOODLIFE FITNESS ANNUAL FEE", 49.99, "2026-09-15", "duplicate", 49.99),
      ("CAA SERVICE FEE", 150.00, "2026-09-03", "duplicate", 120.00)], 268.99),
    ("the gym billed twice, an annual-fee line and a rise", [GYM], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01"), ("GOODLIFE FITNESS", 54.99, "2026-09-01"),
        ("GOODLIFE FITNESS ANNUAL FEE", 49.99, "2026-09-15"), ("GOODLIFE FITNESS", 69.99, "2026-10-01")],
     [("GOODLIFE FITNESS", 54.99, "2026-09-01", "duplicate", 54.99),
      ("GOODLIFE FITNESS ANNUAL FEE", 49.99, "2026-09-15", "duplicate", 49.99),
      ("GOODLIFE FITNESS", 69.99, "2026-10-01", "amount_increased", 15.00)], 119.98),
    ("the gym billed twice and a rise", [GYM], [
        ("GOODLIFE FITNESS", 54.99, "2026-09-01"), ("GOODLIFE FITNESS", 54.99, "2026-09-01"),
        ("GOODLIFE FITNESS", 69.99, "2026-10-01")],
     [("GOODLIFE FITNESS", 54.99, "2026-09-01", "duplicate", 54.99),
      ("GOODLIFE FITNESS", 69.99, "2026-10-01", "amount_increased", 15.00)], 69.99),
    ("the fee named as such, then billed twice at the warehouse", [COSTCO], [
        ("COSTCO MEMBERSHIP FEE", 65.00, "2025-10-01"), ("COSTCO WHOLESALE #539", 73.45, "2026-10-01"),
        ("COSTCO WHOLESALE #539", 73.45, "2026-10-01")],
     [("COSTCO WHOLESALE #539", 73.45, "2026-10-01", "duplicate", 65.00)], 65.00),
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
    ("Costco under two names on one statement", [COSTCO], [
        ("COSTCO MEMBERSHIP", 65.00, "2026-09-01"), ("COSTCO WHOLESALE W551", 73.45, "2026-09-20")],
     [("COSTCO WHOLESALE W551", 73.45, "2026-09-20", "duplicate", 65.00)], 65.00),
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
                if flag == LOOK and "not counted as the fee" not in said:
                    problems.append("does not point out the fee words")
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

    def test_the_dispute_pack_asks_him_about_charges_that_may_be_shopping(self):
        g = self.guard([COSTCO])
        g.check_charge("COSTCO MEMBERSHIP", 65.00, "2026-08-01")
        g.check_charge("COSTCO.CA", 66.10, "2026-09-03")
        p = g.dispute_pack("Costco Membership")
        self.assertEqual(p["amount_in_dispute"], 65.00, p)
        self.assertIn("shopping", p["how_to_use"])
        self.assertIn("ask", p["how_to_use"].lower())


if __name__ == "__main__":
    unittest.main()
