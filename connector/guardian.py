"""
JEFFEREY the Guardian — money that leaves without asking
========================================================

The GoDaddy problem: a card gets charged, nobody asked you, and finding out
takes forever — by which time it's "policy" and you're on hold. Multiply that
by every auto-renewal, silent price hike, zombie subscription and duplicate
billing on earth and you are looking at an enormous amount of money quietly
leaving ordinary people who never agreed to it.

This module is JEFFEREY standing in front of that.

He keeps a register of what SHOULD be charged — merchant, amount, cadence,
and whether the user ever authorized recurring billing at all. Then every
charge gets checked against it:

  expected              → quiet. Don't interrupt.
  amount_decreased      → a little less than usual. Quiet.
  refund                → money came back. Quiet; it comes off any dispute.
  amount_increased      → they raised the price. Here is the delta, in dollars.
  duplicate             → billed again sooner than the cadence allows.
  unauthorized_renewal  → you agreed to pay once; they charged again.
  charged_after_cancel  → a charge dated AFTER the day you cancelled.
  possible_card_testing → a tiny charge, the way card thieves test a card.
  possible_scam         → gift cards, bitcoin machines, wire services.
  needs_date            → the answer depends on a date nobody has given yet.
  unexpected_merchant   → a place that isn't in the register. Informational:
                          most are ordinary purchases, so nothing is "at stake".

What the October 2026 stress test changed, and why:

* Card statements are shouty and abbreviated. 'NETFLIX.COM 866-579-7172 CA',
  'PAYPAL *SPOTIFYAB' and 'AMZN Mktp CA*2K4L71Z30' are matched through their
  processor prefixes, phone and reference numbers, region codes and company
  suffixes — and a weak resemblance only counts when the amount agrees too.
  When nothing matches well enough, JEFFEREY asks instead of guessing.
* A charge is one charge however often it is checked. Re-reading the same
  statement, or asking about the same charge six times, never invents a
  duplicate or inflates a dispute. A statement is read whole before anything
  is kept, so one bad line cannot leave half a statement behind.
* Dates decide. A charge from before the day you cancelled is not theft, and
  a cancellation without a date is not an accusation waiting to happen.
* A dispute claims only what is recoverable (the increase, not the whole
  bill), takes refunds off, and never tells the merchant a subscription was
  unauthorized when the owner authorized it.
* Nothing irreversible happens because an AI asked. The register decides
  which charges stay quiet, so an AI session can only PROPOSE an addition;
  the owner confirms it with his own hands — /charges in 'Talk to JEFFEREY
  on this Mac', 'Check my charges.command', or:

      python connector/guardian.py review

  Engines may list what waits (charge_changes_waiting) and withdraw it
  (decline_charge_change); confirming is offered to no engine.

  A cancellation makes JEFFEREY more watchful, never less, so it is recorded
  at once — and written in the action log with who asked for it.

He never moves money. Cancelling or disputing is an Act — gated, capped,
and logged like everything else.
"""

from __future__ import annotations

import copy
import datetime as _dt
import difflib
import functools
import hashlib
import math
import os
import re
import statistics
import sys
import time
import unicodedata
from typing import Any, Callable

# ===================================================================== words
QUIET = frozenset({"expected", "amount_decreased", "refund"})
INFORMATIONAL = frozenset({"unexpected_merchant"})
RECOVERABLE = frozenset({"charged_after_cancel", "duplicate", "amount_increased",
                         "unauthorized_renewal", "possible_card_testing"})
# a place not in the register: claimed only when the user says it is not his
NOT_RECOGNISED = frozenset({"unexpected_merchant", "possible_card_testing", "possible_scam"})

# Canonical cadence -> (days in one period, a repeat at the same amount sooner
# than this many days is a second bill for the same period).
CADENCES = {
    "weekly": (7, 4), "biweekly": (14, 9), "semimonthly": (15, 9), "fourweekly": (28, 18),
    "monthly": (30, 20), "every_two_months": (61, 45),
    "quarterly": (91, 70), "semiannual": (182, 150), "yearly": (365, 335),
}
PER_YEAR = {"weekly": 52, "biweekly": 26, "semimonthly": 24, "fourweekly": 13,
            "monthly": 12, "every_two_months": 6, "quarterly": 4, "semiannual": 2,
            "yearly": 1}
_CADENCE_SAID = {
    "weekly": "every week", "biweekly": "every two weeks", "semimonthly": "twice a month",
    "fourweekly": "every four weeks", "monthly": "monthly",
    "every_two_months": "every two months", "quarterly": "every three months",
    "semiannual": "twice a year", "yearly": "once a year",
}
# Words that mean two different things, so JEFFEREY asks instead of guessing
# (verify I-38: 'bi-monthly' is every two months to some, twice a month to others).
_CADENCE_TWO_WAYS = {"bimonthly", "bi monthly", "bimensuel", "bimensuelle"}
_CADENCE_WORDS = {
    "weekly": {"weekly", "week", "every week", "per week", "a week", "wk",
               "hebdomadaire", "par semaine"},
    "biweekly": {"biweekly", "bi weekly", "every two weeks", "every 2 weeks",
                 "fortnightly", "fortnight", "every other week", "aux deux semaines",
                 "toutes les deux semaines"},
    "semimonthly": {"semimonthly", "semi monthly", "twice a month", "twice monthly",
                    "two times a month", "deux fois par mois"},
    "fourweekly": {"every 4 weeks", "every four weeks", "4 weekly", "four weekly",
                   "every 28 days", "toutes les quatre semaines", "aux quatre semaines"},
    "monthly": {"monthly", "month", "per month", "a month", "every month", "mo",
                "mthly", "mensuel", "mensuelle", "par mois"},
    "every_two_months": {"every two months", "every 2 months", "every other month",
                         "bimestriel", "bimestrielle", "aux deux mois",
                         "tous les deux mois"},
    "quarterly": {"quarterly", "quarter", "every quarter", "every 3 months",
                  "every three months", "trimestriel", "trimestrielle"},
    "semiannual": {"semiannual", "semi annual", "semiannually", "semi annually",
                   "twice a year", "every 6 months", "every six months",
                   "half yearly", "biannual", "biannually"},
    "yearly": {"yearly", "year", "annual", "annually", "per year", "a year",
               "every year", "yr", "annuel", "annuelle", "par an", "per annum", "annum",
               "every 12 months", "every twelve months", "par annee"},
    "once": {"once", "one time", "onetime", "one off", "oneoff", "single",
             "just once", "one", "unique", "une fois"},
    "unknown": {"unknown"},
}

# Pure payment processors: the real merchant is what follows the '*'.
_PROCESSORS = {"paypal", "pp", "ppl", "sq", "tst", "sp", "iz", "izettle", "zettle",
               "ztl", "cko", "fs", "paddle", "2co", "wpy", "bt", "clv", "py", "ls",
               "pos", "stripe", "sumup", "moneris", "helcim"}
# Platforms that bill for others: the merchant may be either side of the '*'.
_PLATFORMS = {"google", "goog", "apple", "amazon", "amzn", "doordash", "uber", "lyft",
              "skip", "skipthedishes", "microsoft", "msft", "xbox", "steam",
              "steamgames", "shopify", "etsy", "ebay", "openai", "facebook", "fb",
              "meta", "instacart", "grubhub", "ubereats"}
_SYNONYMS = {"amzn": "amazon", "mktp": "marketplace", "mktplace": "marketplace"}
_FILLER = {"subscription", "subscriptions", "subscr", "membership", "member",
           "monthly", "annual", "annually", "yearly", "plan", "bill", "billing",
           "payment", "pymt", "pmt", "recurring", "autopay", "renewal", "renew",
           "pending", "purchase", "preauthorized", "preauth"}
_COMPANY = {"inc", "llc", "ltd", "corp", "co", "limited", "gmbh", "plc", "ulc", "lp",
            "llp", "ag", "sa", "sarl", "bv", "nv", "pty", "ab", "incorporated"}
_REGIONS = {
    # provinces and territories
    "on", "qc", "bc", "ab", "mb", "sk", "ns", "nb", "nl", "pe", "pei", "yt", "nt", "nu",
    # countries a card statement names
    "ca", "can", "us", "usa", "uk", "gb", "se", "ie", "nl", "de", "fr", "lu", "au",
    "nz", "mx", "jp", "hk", "sg", "ch", "dk", "fi", "es", "pl", "cn",
    # US states (common English words left out)
    "al", "ak", "az", "ar", "ct", "fl", "ga", "ia", "il", "ks", "ky", "la", "ma",
    "md", "mi", "mn", "mo", "ms", "mt", "nc", "nd", "ne", "nh", "nj", "nm", "nv", "ny",
    "pa", "ri", "sc", "sd", "tn", "tx", "ut", "va", "vt", "wa", "wi", "wv", "wy", "dc",
}
# What may follow a registered name glued onto it: 'SPOTIFYAB', 'NETFLIXINC'.
_GLUED_OK = {"ab", "inc", "llc", "ltd", "co", "corp", "ca", "us", "usa", "canada", "com"}
_SCAM = re.compile(
    r"\b(bitcoin|btc|crypto|coinbase|bitbuy|kraken|gift ?cards?|giftcards?|"
    r"google play card|itunes card|steam card|western union|moneygram|"
    r"ria money|remitly|wire transfer|tech ?support|computer support|"
    r"virus removal|pc repair online)\b")

STRONG, WEAK = 0.9, 0.75
HINT = 0.7                      # only ever a 'did you mean'

# A statement name that only STARTS with a registered name ('COSTCO WHOLESALE'
# for 'Costco Membership', 'ROGERS CENTRE' for 'Rogers', 'APPLE STORE' for
# 'APPLE.COM/BILL') is the same agreement only when what follows is not
# another line of business, and the amount is near the agreed one (verify
# I-36: grocery runs became price rises, card tests and duplicates, and a
# $308 dispute pack). Otherwise it is a 'did you mean', never a match.
_OTHER_BUSINESS = frozenset("""
wholesale store stores shop shoppe boutique outlet depot mart market marche
supermarket grocery groceries epicerie centre center arena stadium field park
theatre theater cinema cineplex ticket tickets concession concessions cafe coffee
restaurant resto bar grill pub kitchen bakery deli pizza sushi pharmacy pharmacie
drug drugs gas fuel station essence carwash wash parking hotel inn motel resort
travel tours airport duty bank insurance financial rewards gift gifts golf ski
sports optical dental clinic salon spa food foods liquor beer wine catering
""".split())
_PRICE_BAND = (0.5, 2.0)        # a new price, not a different purchase


def _extra(q: tuple[str, ...], r: tuple[str, ...]) -> tuple[str, ...]:
    """The words a statement name adds after a registered name it starts with."""
    if len(r) < len(q) and q[:len(r)] == r:
        return q[len(r):]
    return ()

_MONTHS = {
    "jan": 1, "january": 1, "janvier": 1, "janv": 1,
    "feb": 2, "february": 2, "fevrier": 2, "fev": 2, "fevr": 2,
    "mar": 3, "march": 3, "mars": 3,
    "apr": 4, "april": 4, "avril": 4, "avr": 4,
    "may": 5, "mai": 5,
    "jun": 6, "june": 6, "juin": 6,
    "jul": 7, "july": 7, "juillet": 7, "juil": 7,
    "aug": 8, "august": 8, "aout": 8,
    "sep": 9, "sept": 9, "september": 9, "septembre": 9,
    "oct": 10, "october": 10, "octobre": 10,
    "nov": 11, "november": 11, "novembre": 11,
    "dec": 12, "december": 12, "decembre": 12,
}
_DATE_NOISE = {"st", "nd", "rd", "th", "er", "le", "the", "of", "de", "on",
               "mon", "monday", "tue", "tues", "tuesday", "wed", "wednesday",
               "thu", "thur", "thurs", "thursday", "fri", "friday", "sat",
               "saturday", "sun", "sunday", "lundi", "mardi", "mercredi", "jeudi",
               "vendredi", "samedi", "dimanche"}

_MAX_AMOUNT = 10_000_000.0


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _ident(prefix: str, seed: str) -> str:
    """A short id made of letters only: a run of digits in an id could look
    like a social insurance number to the egress door and get a whole result
    withheld."""
    h = hashlib.sha1(seed.encode()).hexdigest()[:10]
    return prefix + "".join(chr(ord("a") + int(ch, 16)) for ch in h)


def _m(x: float) -> str:
    return f"${x:,.2f}"


# ===================================================================== names
def _fold(s: Any) -> str:
    """Lower-case with accents off; every script is kept, so a Chinese or
    Cyrillic name stays itself instead of collapsing to nothing."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.casefold()


_URL = re.compile(r"^(?:[a-z0-9-]+\.)*([a-z0-9-]+)\.(?:com|ca|net|org|co|io|tv|us|uk|"
                  r"ie|se|de|fr|nl|lu|app|ai|me|info|biz)(?:\.[a-z]{2})?(?:/\S*)?$")


def _segment_tokens(seg: str) -> list[str]:
    words = []
    for i, w in enumerate(seg.split()):
        m = _URL.match(w.strip("#,;:()[]"))
        if m:
            if i == 0 and not words:
                words.append(m.group(1))      # 'NETFLIX.COM' is Netflix
            continue                          # 'help.uber.com', 'amazon.ca/pm': noise
        words.append(w)
    s = " ".join(words)
    s = re.sub(r"(?<=\w)['’`](?=\w)", "", s)     # JOE'S -> joes
    s = re.sub(r"(?<=\w)-(?=\w)", "", s)              # CO-OP, WAL-MART, 866-579-7172
    return re.findall(r"[^\W_]+", s)


def _clean(tokens: list[str]) -> list[str]:
    raw = [_SYNONYMS.get(t, t) for t in tokens]
    out: list[str] = []
    for i, t in enumerate(raw):
        has_digit = any(ch.isdigit() for ch in t)
        if t.isdigit():
            continue                                   # phone numbers, store ids
        if has_digit and any(ch.isalpha() for ch in t) and i > 0:
            continue                                   # reference codes: P2A5C1D3E9
        if t in _FILLER:
            continue
        out.append(t)
    if out and out[0] == "the" and len(out) > 1:
        out = out[1:]
    while len(out) > 1 and (out[-1] in _REGIONS or out[-1] in _COMPANY):
        out.pop()
    if not out:
        out = [t for t in raw if t]                    # '1234567' stays itself
    return out


def _forms(merchant: Any) -> tuple[tuple[str, ...], ...]:
    """The ways one statement line can name a merchant, most likely first."""
    return _forms_of("" if merchant is None else str(merchant))


@functools.lru_cache(maxsize=16384)
def _forms_of(merchant: str) -> tuple[tuple[str, ...], ...]:
    s = _fold(merchant)
    s = s.replace("+", " plus ").replace("&", " and ")
    s = re.sub(r"[*x•]{2,}\d*", " ", s)            # masked cards: ******1234
    head, star, tail = s.partition("*")
    head_t = _segment_tokens(head)
    tail_t = _segment_tokens(tail) if star else []
    forms: list[list[str]] = []
    first = head_t[0] if head_t else ""
    if star and tail_t and first in _PROCESSORS:
        forms.append(_clean(tail_t))
    elif star and tail_t and first in _PLATFORMS:
        forms.append(_clean(head_t + tail_t))
        tail = _clean(tail_t)
        if any(not any(ch.isdigit() for ch in t) for t in tail):
            forms.append(tail)                         # not when it is only an order id
    else:
        forms.append(_clean(head_t + tail_t))
    return tuple(tuple(f) for f in forms if f)


def _norm(merchant: Any) -> str:
    """The key a merchant is filed under. Empty means 'no name I can use'."""
    forms = _forms(merchant)
    return " ".join(forms[0]) if forms else ""


def _score(q: tuple[str, ...], r: tuple[str, ...]) -> float:
    """How surely statement name `q` is registered name `r`."""
    if not q or not r:
        return 0.0
    if q == r:
        return 1.0
    cq, cr = "".join(q), "".join(r)
    if cq == cr:
        return 0.97                                   # DISNEYPLUS = Disney Plus
    if len(r) < len(q) and q[:len(r)] == r:
        return min(0.95 + 0.001 * len(r), 0.969)      # NETFLIX LOS GATOS = Netflix
    if len(cr) >= 4 and cq.startswith(cr) and cq[len(cr):] in _GLUED_OK:
        return 0.92                                   # SPOTIFYAB = Spotify
    # weak: only ever trusted when the amount agrees too
    if len(q) < len(r) and r[:len(q)] == q and len(cq) >= 3:
        return 0.8                                    # APPLE = Apple iCloud
    if min(len(cq), len(cr)) >= 5:
        sm = difflib.SequenceMatcher(None, cq, cr)
        if sm.real_quick_ratio() >= 0.85 and sm.quick_ratio() >= 0.85:
            ratio = sm.ratio()
            if ratio >= 0.85:
                return 0.6 + 0.2 * ratio              # a typo: Spotfy
    return 0.0


# ===================================================================== values
def _parse_amount(value: Any) -> tuple[float | None, str | None]:
    """'$18.63', '1,234.56', '1 234,56 $', '(22.59)', '22.59 CR' — or a plain
    reason it is not an amount. NaN, infinity, True and absurd sizes are not."""
    if isinstance(value, bool):
        return None, f"'{value}' is not an amount of money"
    if value is None:
        return None, "there is no amount"
    if isinstance(value, (int, float)):
        x = float(value)
    else:
        s = str(value).strip().replace("−", "-")
        s = s.replace(" ", " ").replace(" ", " ")
        if not s:
            return None, "the amount is empty"
        neg = False
        if s.startswith("(") and s.endswith(")"):
            neg, s = True, s[1:-1].strip()
        m = re.search(r"\s*\b(cr|credit)\.?$", s, re.I)
        if m:
            neg, s = True, s[:m.start()]
        s = re.sub(r"\b(?:cad|usd|eur|gbp|chf|aud)\b|(?:\b(?:c|ca|us|au))?\$|[€£¥]",
                   " ", s, flags=re.I).strip()
        if s.startswith(("-", "+")):
            neg, s = neg or s[0] == "-", s[1:].strip()
        if s.endswith("-"):
            neg, s = True, s[:-1].strip()
        if not s or re.search(r"[^\d\s,.]", s) or not re.search(r"\d", s):
            return None, f"I can't read '{value}' as an amount of money"
        if " " in s:
            if not re.fullmatch(r"\d{1,3}(?: \d{3})+(?:[.,]\d{1,2})?", s):
                return None, f"I can't read '{value}' as an amount of money"
            s = s.replace(" ", "")
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")     # 1.234,56
            else:
                s = s.replace(",", "")                       # 1,234.56
        elif "," in s:
            if re.fullmatch(r"\d{1,3}(?:,\d{3})+", s):
                s = s.replace(",", "")                       # 1,234
            elif re.fullmatch(r"\d+,\d{1,2}", s):
                s = s.replace(",", ".")                      # 11,99
            else:
                return None, f"I can't read '{value}' as an amount of money"
        elif s.count(".") > 1:
            if not re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
                return None, f"I can't read '{value}' as an amount of money"
            s = s.replace(".", "")
        try:
            x = float(s)
        except ValueError:
            return None, f"I can't read '{value}' as an amount of money"
        if neg:
            x = -x
    if not math.isfinite(x):
        return None, f"'{value}' is not an amount of money"
    if abs(x) > _MAX_AMOUNT:
        return None, f"{value} is far too large to be a real charge"
    return round(x, 2), None


def _parse_date(value: Any, today: _dt.date,
                relative_ok: bool = True) -> tuple[str | None, str | None, bool]:
    """(ISO date, reason it can't be read, ambiguous?). '2026-10-03',
    '10/01/2026' (month first, as North American statements print it),
    'Sep 1, 2025', '1er octobre 2026', 'SEP 01', 'today', 'end of the month'.
    With relative_ok=False (text saved long ago) 'today', 'end of the month'
    and dates without a year are not guessed: nobody knows when they were said."""
    if value is None:
        return None, None, False
    if isinstance(value, _dt.datetime):
        return value.date().isoformat(), None, False
    if isinstance(value, _dt.date):
        return value.isoformat(), None, False
    said = str(value).strip()
    s = _fold(said).strip().rstrip(".")
    if not s:
        return None, None, False

    def ok(y: int, mo: int, d: int, ambiguous: bool = False):
        try:
            return _dt.date(y, mo, d).isoformat(), None, ambiguous
        except ValueError:
            return None, f"'{said}' is not a real date", False

    def month_end(d: _dt.date, ahead: int = 0) -> str:
        y, mo = d.year + (d.month - 1 + ahead) // 12, (d.month - 1 + ahead) % 12 + 1
        nxt = _dt.date(y + (mo == 12), mo % 12 + 1, 1)
        return (nxt - _dt.timedelta(days=1)).isoformat()

    relative = (s in ("today", "now", "aujourd'hui", "aujourdhui", "yesterday", "hier",
                      "tomorrow", "demain") or "end of" in s)
    if relative and not relative_ok:
        return None, f"'{said}' does not say which day it was", False
    if s in ("today", "now", "aujourd'hui", "aujourdhui"):
        return today.isoformat(), None, False
    if s in ("yesterday", "hier"):
        return (today - _dt.timedelta(days=1)).isoformat(), None, False
    if s in ("tomorrow", "demain"):
        return (today + _dt.timedelta(days=1)).isoformat(), None, False
    if re.fullmatch(r"(?:at )?(?:the )?end of (?:the |this )?month", s):
        return month_end(today), None, False
    if re.fullmatch(r"(?:at )?(?:the )?end of next month", s):
        return month_end(today, 1), None, False

    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[t ].*)?", s)
    if m:
        return ok(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})", s)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        if y < 100:
            y += 2000 if y <= (today.year % 100) + 1 else 1900
        if a > 12 and b <= 12:
            return ok(y, b, a)
        if a <= 12:
            return ok(y, a, b, ambiguous=(b <= 12 and a != b))
        return None, f"'{said}' is not a real date", False

    toks = re.findall(r"[^\W\d_]+|\d+", s)
    month = next((_MONTHS[t] for t in toks if t in _MONTHS), None)
    if month is None or any(not t.isdigit() and t not in _MONTHS and t not in _DATE_NOISE
                            for t in toks):
        return None, (f"I can't read '{said}' as a date; please give it like "
                      f"2026-10-12"), False
    nums = [int(t) for t in toks if t.isdigit()]
    years = [n for n in nums if n >= 1000]
    days = [n for n in nums if 1 <= n <= 31]
    if not days:
        return None, f"'{said}' has no day of the month", False
    day = days[0]
    if years:
        return ok(years[0], month, day)
    if not relative_ok and len(days) < 2:
        return None, f"'{said}' has no year", False
    if len(days) > 1 and days[1] >= 10 and len(nums) > 1:
        # 'Sep 1, 25': a two-digit year after the day
        y = 2000 + days[1] if days[1] <= (today.year % 100) + 1 else 1900 + days[1]
        return ok(y, month, day)
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            d = _dt.date(y, month, day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    if best is None:
        return None, f"'{said}' is not a real date", False
    return best.isoformat(), None, False


def _other_reading(value: Any) -> str | None:
    """The day-first reading of a date like '11/10/2026' (month-first is
    the one _parse_date gives), or None."""
    m = re.fullmatch(r"\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*", str(value or ""))
    if not m:
        return None
    try:
        return _dt.date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    except ValueError:
        return None


def _ref(value: Any) -> str:
    """A statement line's reference, written one way: 'A1', 'a1 ' and
    'A-1' are one reference (verify I-37)."""
    return re.sub(r"[\s\-_.#/]+", "", _fold(value or "")).strip()


def _norm_cadence(value: Any) -> tuple[str, bool]:
    s = re.sub(r"[^a-z0-9 ]+", " ", _fold(value)).strip()
    s = re.sub(r"\s+", " ", s)
    if not s:
        return "monthly", True                     # the documented default
    for canon, words in _CADENCE_WORDS.items():
        if s in words:
            return canon, True
    return "unknown", False


def _parse_bool(value: Any) -> tuple[bool, bool]:
    """(value, understood). 'false' from a local model means False — the old
    bool('false') made it True and weakened the owner's own dispute."""
    if isinstance(value, bool):
        return value, True
    if value is None:
        return True, True
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value), True
    s = _fold(value).strip()
    if s in ("", "true", "yes", "y", "1", "on", "authorized", "authorised"):
        return True, True
    if s in ("false", "no", "n", "0", "off", "none", "never", "not authorized",
             "not authorised"):
        return False, True
    return False, False                            # unclear: stay watchful


def _same_amount(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.01, 0.01 * max(abs(a), abs(b)))


def _amounts_agree(registered: float, charged: float) -> bool:
    return abs(registered - charged) <= max(0.05, 0.02 * abs(registered))


def _days(a: str, b: str) -> int:
    return (_dt.date.fromisoformat(a) - _dt.date.fromisoformat(b)).days


_MONTH_NAMES = ("January February March April May June July August September October "
                "November December").split()


def _spoken(iso: str) -> str:
    """'2026-10-11' as people say it: '11 October 2026'."""
    try:
        d = _dt.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return str(iso)
    return f"{d.day} {_MONTH_NAMES[d.month - 1]} {d.year}"


# A one-time agreement is charged when it is made: a first charge seen more
# than this many days later is, almost always, a renewal (verify I-38).
_ONCE_DAYS = 25

# A charge kept by the first version, whose date may be the day it was asked
# about (verify I-37): it never decides an accusation on its own.
_OLD_DATE = ("This {amt} from {name} rests on a charge an older version of JEFFEREY kept "
             "with the date {d}; that version wrote down the day it was asked when no "
             "date was given, so I can't be sure it {what}. What date is printed on the "
             "statement?")


def _agreed_on(entry: dict) -> str | None:
    """The day he agreed to an entry: when it was registered (or, for one
    made before this was kept, when it was last changed)."""
    for v in (entry.get("agreed_on"), str(entry.get("updated") or "")[:10]):
        try:
            return _dt.date.fromisoformat(v).isoformat()
        except (TypeError, ValueError):
            continue
    return None


# ===================================================================== who
def _owner_hands() -> bool:
    """True only when the owner's own hands are on this call: a command he
    typed and confirmed at his keyboard (access.owner_console — the /charges
    command, or `python connector/guardian.py review`). Never an environment
    variable, which any process a model drives could inherit (I-04), and
    never an HTTP request."""
    try:
        import access
        return bool(access.owner_present())
    except Exception:
        return False


def _client() -> str:
    try:
        import access
        if access.GATE is not None:
            return access.current_client()
    except Exception:
        pass
    return "this computer"


def _door_shut() -> bool:
    try:
        import egress
        return bool(egress.is_shut())
    except Exception:
        return False


_ACTIONS = {
    "quiet": "Nothing to do.",
    "unexpected_merchant": (
        "Mention it calmly as a purchase from a place that is not in the register "
        "and ask whether they recognize it. Do not call it fraud and do not offer "
        "a dispute unless they say it is not theirs; then call dispute_pack with "
        "not_mine=true."),
    "needs_date": "Ask the user for the date, then check the charge again with it.",
    "alarm": (
        "Tell the user plainly and gently. If they do not recognize it, the next "
        "step is to call the bank using the number on the back of the card — not "
        "the merchant. Score it with record_opportunity (reduces_risk=True)."),
    "dispute": (
        "Tell the user in plain words, offer to build a dispute_pack, and score it "
        "with record_opportunity (reduces_risk=True). Contacting the merchant or "
        "the bank is an Act: authorize_action first — with no amount, since a "
        "letter or a call costs nothing — then log_action."),
}


def _action_for(verdict: str) -> str:
    if verdict in QUIET:
        return _ACTIONS["quiet"]
    if verdict in ("unexpected_merchant", "needs_date"):
        return _ACTIONS[verdict]
    if verdict in ("possible_card_testing", "possible_scam"):
        return _ACTIONS["alarm"]
    return _ACTIONS["dispute"]


# ===================================================================== guardian
class Guardian:
    """Watches what leaves the user's accounts. Holds no card numbers — only
    what was charged, by whom, and whether it was ever agreed to."""

    def __init__(self, conscience, owner_present: Callable[[], bool] | None = None,
                 today: Callable[[], _dt.date] | None = None):
        self.c = conscience
        # In memory only: starting JEFFEREY must never write the conscience.
        self.c.data.setdefault("expected_charges", [])
        self.c.data.setdefault("charges_seen", [])
        self.owner_present = owner_present or _owner_hands
        self._today = today or _dt.date.today

    # ---------------------------------------------------------- old shapes
    def _entries(self) -> list[dict]:
        """The register, upgraded in place (in memory) from any older shape.
        Nothing is dropped: replaced values are kept beside the new ones."""
        reg = self.c.data.setdefault("expected_charges", [])
        today = self._today()
        old = [e for e in reg if e.get("v") != 2]
        for i, e in enumerate(reg):
            if e.get("v") != 2:
                self._upgrade_entry(e, i, today)
        if old:
            self._settle_old_cancellations(reg, old)
        return reg

    @staticmethod
    def _settle_old_cancellations(reg: list[dict], old: list[dict]) -> None:
        """The old code filed a cancellation under a name nothing else had
        ('Netflix subscription'), next to the agreed 'Netflix'. Read the way
        names are read now, both are Netflix, and the agreed one won, so a
        charge after the cancellation was 'as agreed. Quiet.' (verify I-36).
        Such a cancellation now belongs to its entry: if it was said after
        the entry was last agreed (or nobody knows when), the entry is
        cancelled from that date; if he agreed again later, it is kept as
        history. The old entry stays in the file, marked as merged."""
        for s in old:
            if (s.get("active", True) or s.get("amount_known", True)
                    or s.get("merged_into")):
                continue
            twins = [e for e in reg if e is not s and e.get("key") == s.get("key")
                     and e.get("active", True) and not e.get("merged_into")]
            if len(twins) != 1:
                continue
            e = twins[0]
            said = {"cancelled_on": s.get("cancelled_on"),
                    "said": s.get("cancelled_on_said"), "from_entry": s.get("id")}
            if str(s.get("updated") or "") >= str(e.get("updated") or ""):
                e["active"] = False
                e["cancelled_on"] = s.get("cancelled_on")
                if s.get("cancelled_on_said"):
                    e["cancelled_on_said"] = s["cancelled_on_said"]
                e["cancellation_from"] = s.get("id")
            else:
                e.setdefault("past_cancellations", []).append(said)
            s["merged_into"] = e["id"]

    @staticmethod
    def _upgrade_entry(e: dict, i: int, today: _dt.date) -> None:
        e.setdefault("merchant", e.get("key", ""))
        key = _norm(e["merchant"])
        if e.get("key") not in (None, key):
            e.setdefault("key_v1", e.get("key"))
        e["key"] = key
        e.setdefault("id", _ident("c-", f"{i}|{e['merchant']}|{e.get('updated', '')}"))
        try:
            amt = float(e.get("amount", 0.0))
            good = math.isfinite(amt) and amt >= 0
        except (TypeError, ValueError):
            good = False
        if not good:
            e.setdefault("amount_said", e.get("amount"))
            e["amount"], e["amount_known"] = 0.0, False
        else:
            e["amount"] = round(amt, 2)
        cad, _ = _norm_cadence(e.get("cadence"))
        if cad != e.get("cadence"):
            e.setdefault("cadence_said", e.get("cadence"))
        e["cadence"] = cad
        e["authorized_recurring"], _ = _parse_bool(e.get("authorized_recurring", True))
        e.setdefault("active", True)
        said = e.get("cancelled_on")
        if said:
            iso, err, _amb = _parse_date(said, today, relative_ok=False)
            if iso != said:
                e.setdefault("cancelled_on_said", said)
            e["cancelled_on"] = iso if not err else None
        else:
            e["cancelled_on"] = None
        if e["active"] and e.get("cancelled_on"):
            # re-subscribed under the old code: the cancellation is history
            e.setdefault("past_cancellations", []).append(
                {"cancelled_on": e["cancelled_on"], "said": e.get("cancelled_on_said")})
            e["cancelled_on"] = None
        e.setdefault("amount_known", not (
            e["amount"] == 0 and e["cadence"] == "unknown"
            and e.get("note") == "cancelled by the user"))
        e.setdefault("aliases", [])
        e["v"] = 2

    def _charges(self) -> list[dict]:
        seen = self.c.data.setdefault("charges_seen", [])
        today = self._today()
        for r in seen:
            if r.get("v") != 2:
                self._upgrade_charge(r, today)
        return seen

    @staticmethod
    def _upgrade_charge(r: dict, today: _dt.date) -> None:
        merchant = str(r.get("merchant", r.get("key", "")))
        key = _norm(merchant)
        if r.get("key") not in (None, key):
            r.setdefault("key_v1", r.get("key"))
        r["key"] = key
        said = r.get("date")
        iso, err, _amb = (_parse_date(said, today, relative_ok=False) if said
                          else (None, None, False))
        if said and iso != said:
            r.setdefault("date_said", said)
        r["date"] = iso if not err else None
        if r["date"] and "seen" not in r:
            # The first version wrote the day it was ASKED when no date was
            # given, and did not say so: this date may not be the day of the
            # charge, so it never decides an accusation alone (verify I-37).
            r["date_uncertain"] = True
        try:
            amt = float(r.get("amount"))
            if not math.isfinite(amt):
                raise ValueError
            r["amount"] = round(amt, 2)
        except (TypeError, ValueError):
            r["unreadable"] = True
        # Under the old code every check was saved again; identical old lines
        # are one charge (seq 1 each), so they can no longer pose as duplicates.
        r.setdefault("seq", 1)
        r["v"] = 2

    # ---------------------------------------------------------- matching
    def _entry_forms(self, e: dict) -> tuple[tuple[str, ...], ...]:
        return _forms(e.get("merchant", "")) + tuple(
            tuple(a.split()) for a in e.get("aliases", []) if a)

    def _ranked(self, merchant: Any, amount: float | None = None) -> list[tuple[float, dict]]:
        """Register entries this name may be, with how surely. A name that
        only starts with an entry's name, then names another business or a
        far-off amount, or that names a gift card or 'tech support' when the
        entry does not, counts as a 'did you mean' only (verify I-36)."""
        q = _forms(merchant)
        scam = bool(_SCAM.search(_fold(merchant)))
        out = []
        for e in self._entries():
            if e.get("merged_into"):
                continue
            best, extra = 0.0, ()
            for qf in q:
                for rf in self._entry_forms(e):
                    s = _score(qf, rf)
                    x = _extra(qf, rf) if s >= STRONG else ()
                    if s > best or (s == best and extra and not x):
                        best, extra = s, x
            if best < WEAK:
                continue
            if self._only_a_likeness(e, extra, amount, scam):
                best = HINT          # a 'did you mean', never matched, whatever the amount
            out.append((best, e))
        return out

    @staticmethod
    def _only_a_likeness(e: dict, extra: tuple[str, ...], amount: float | None,
                         scam: bool) -> bool:
        if scam and not _SCAM.search(_fold(e.get("merchant", ""))):
            return True                  # 'NETFLIX GIFT CARD', 'NETFLIX TECH SUPPORT'
        if not extra:
            return False
        if set(extra) & _OTHER_BUSINESS:
            return True                  # 'COSTCO WHOLESALE', 'ROGERS CENTRE'
        reg = e.get("amount") or 0.0
        if amount is None or not e.get("amount_known", True) or reg <= 0:
            return False
        ratio = abs(amount) / reg
        return not (_PRICE_BAND[0] <= ratio <= _PRICE_BAND[1])

    def _match(self, merchant: Any, amount: float | None) -> tuple[dict | None, dict | None]:
        """(the register entry this line is, a 'did you mean' hint)."""
        ranked = self._ranked(merchant, amount)
        strong = [(s, e) for s, e in ranked if s >= STRONG]

        def gap(e):
            if amount is None or not e.get("amount_known", True):
                return 0.0
            return abs(e["amount"] - abs(amount))

        if strong:
            top = max(s for s, _ in strong)
            tied = [e for s, e in strong if s >= top - 0.015]
            return min(tied, key=lambda e: (gap(e), not e.get("active", True))), None
        weak = sorted(((s, e) for s, e in ranked if s < STRONG), key=lambda x: -x[0])
        if weak and amount is not None:
            agree = [e for s, e in weak
                     if s >= WEAK and e.get("amount_known", True)
                     and _amounts_agree(e["amount"], abs(amount))]
            if agree:
                return min(agree, key=gap), None
        return None, (weak[0][1] if weak else None)

    def _registration_target(self, key: str) -> dict | None:
        compact = key.replace(" ", "")
        for e in self._entries():
            if e.get("merged_into"):
                continue
            if e["key"] == key or e["key"].replace(" ", "") == compact or key in e.get("aliases", []):
                return e
        return None

    # ---------------------------------------------------------- saving
    _SECTIONS = ("expected_charges", "charges_seen", "charge_proposals", "actions")

    def _transaction(self, fn: Callable[[], dict | list]) -> dict | list:
        """Run one operation and save it once. If another JEFFEREY saved at the
        same moment, undo, re-read and try once more; never half a change."""
        for attempt in (1, 2):
            snap = {k: copy.deepcopy(self.c.data[k]) for k in self._SECTIONS if k in self.c.data}
            try:
                return fn()
            except Exception as exc:
                for k in self._SECTIONS:
                    if k in snap:
                        self.c.data[k] = snap[k]
                    else:
                        self.c.data.pop(k, None)
                if type(exc).__name__ != "ConscienceConflict":
                    raise
                if attempt == 1 and getattr(self.c, "refresh", None) and self.c.refresh():
                    continue
                return {"error": "Nothing was kept: another JEFFEREY window saved at the "
                                 "same moment. Please ask again.",
                        "tell_the_user": "Say that nothing was saved and that asking "
                                         "again will work."}
        raise AssertionError("unreachable")

    def _log(self, description: str, outcome: str, amount: float | None = None,
             client: str | None = None) -> None:
        """Every register change goes in the action log, with who asked."""
        self.c.data.setdefault("actions", []).append({
            "category": "money register", "description": description,
            "amount": amount, "outcome": outcome, "client": client or _client(),
            "added": _stamp(), "ts": time.time(),
        })

    # ---------------------------------------------------------- register
    def expect_charge(self, merchant: str, amount: Any, cadence: Any = "monthly",
                      authorized_recurring: Any = True, note: str = "") -> dict:
        """Register a charge the user has actually agreed to. Anything not in
        this register is, by default, a question. From anyone but the owner's
        own hands this is a proposal the owner confirms; nothing goes quiet
        because an AI asked."""
        key = _norm(merchant)
        if not key:
            return {"merchant": merchant, "error": "There is no merchant name I can use.",
                    "tell_the_user": "Ask for the name of the company as it appears "
                                     "on the statement."}
        amt, err = _parse_amount(amount)
        if err is None and amt is not None and amt < 0:
            err = "an agreed charge cannot be a negative amount"
        if err:
            return {"merchant": merchant, "error": f"Not registered: {err}.",
                    "tell_the_user": "Ask for the amount they agreed to pay, in dollars "
                                     "and cents."}
        cad, cad_ok = _norm_cadence(cadence)
        auth, auth_ok = _parse_bool(authorized_recurring)
        warnings = []
        two_ways = re.sub(r"[^a-z ]+", " ", _fold(cadence)).split()
        if not cad_ok and " ".join(two_ways) in _CADENCE_TWO_WAYS:
            warnings.append(f"'{cadence}' can mean every two months or twice a month, so I "
                            f"did not guess and will not check how often it is charged. "
                            f"Ask which, then add it again as 'every two months' or "
                            f"'twice a month'.")
        elif not cad_ok:
            warnings.append(f"I did not understand how often ('{cadence}'), so I will not "
                            f"check how often it is charged.")
        if not auth_ok:
            warnings.append(f"I did not understand whether automatic renewal was agreed "
                            f"('{authorized_recurring}'), so I have treated it as not agreed.")
        if cad == "once" and auth:
            auth = False                     # one payment is not a subscription
        change = {"merchant": str(merchant), "amount": amt, "cadence": cad,
                  "authorized_recurring": auth, "note": str(note or "")}

        def run() -> dict:
            target = self._registration_target(key)
            if (target and target.get("active", True) and target.get("amount_known", True)
                    and abs(target["amount"] - amt) < 0.005 and target["cadence"] == cad
                    and target["authorized_recurring"] == auth):
                out = dict(target)
                out["note"] = "Already in your register exactly like this. Nothing changed."
                return out
            far = self._far_above(target, key, amt)
            if self.owner_present() and not far:
                entry = self._apply_expect(change, target, by="the owner")
                self.c._save()
                out = dict(entry)
                out["status"] = "registered"
                out["note"] = (f"{entry['merchant']} {_m(entry['amount'])} "
                               f"{_CADENCE_SAID.get(cad, cad)} is in your register."
                               + (" " + " ".join(warnings) if warnings else ""))
                return out
            p = self._propose("expect", change, target, warnings + ([far] if far else []))
            self.c._save()
            return self._proposal_result(p, far)

        return self._transaction(run)

    def _far_above(self, target: dict | None, key: str, amt: float) -> str | None:
        """A registration far above what this merchant has ever charged is
        probably a typo (or someone hiding a scam) — ask first."""
        group = ("e:" + target["id"]) if target else ("m:" + key)
        cache: dict[tuple, str] = {}
        hist = []
        for r in self._charges():
            # a card test, a scam payment or a second bill is not what this
            # place 'usually charges' (verify I-47: a $1 test made $145 look
            # like a typo, ten times the usual)
            if (r.get("unreadable") or r["amount"] < 2.00
                    or r.get("verdict") in ("possible_card_testing", "possible_scam",
                                            "duplicate")):
                continue
            k = (r["merchant"], r["amount"])
            if k not in cache:
                cache[k] = self._group(r["merchant"], r["amount"])[0]
            if cache[k] == group:
                hist.append(r["amount"])
        ref = statistics.median(hist) if hist else None
        if ref is None and target and target.get("amount_known", True) and target["amount"] > 0:
            ref = target["amount"]
        if ref and amt > 10 * ref:
            name = target["merchant"] if target else key
            return (f"{_m(amt)} is more than ten times what {name} usually charges "
                    f"({_m(ref)}), so I have not changed the register.")
        return None

    def _apply_expect(self, change: dict, target: dict | None, by: str,
                      log: bool = True) -> dict:
        now = _stamp()
        if target is None:
            target = self._registration_target(_norm(change["merchant"]))
        if target is not None:
            if not target.get("active", True):
                target.setdefault("past_cancellations", []).append({
                    "cancelled_on": target.get("cancelled_on"),
                    "said": target.get("cancelled_on_said"),
                    "resumed": now})
                target["cancelled_on"] = None
                target.pop("cancelled_on_said", None)
            target.update(merchant=change["merchant"], key=_norm(change["merchant"]),
                          amount=change["amount"], cadence=change["cadence"],
                          authorized_recurring=change["authorized_recurring"],
                          note=change["note"] or target.get("note", ""), active=True,
                          amount_known=True, updated=now,
                          agreed_on=self._today().isoformat())
            entry = target
        else:
            entry = {
                "id": _ident("c-", f"{change['merchant']}|{now}|{time.time_ns()}"),
                "key": _norm(change["merchant"]), "merchant": change["merchant"],
                "amount": change["amount"], "cadence": change["cadence"],
                "authorized_recurring": change["authorized_recurring"],
                "note": change["note"], "active": True, "cancelled_on": None,
                "amount_known": True, "aliases": [], "updated": now, "v": 2,
                # the day he said it: a one-time agreement's charge comes then,
                # so one long after is a renewal (verify I-38)
                "agreed_on": self._today().isoformat(),
            }
            self.c.data["expected_charges"].append(entry)
        if not log:
            return entry
        self._log(f"Charge register: {entry['merchant']} {_m(entry['amount'])} "
                  f"{_CADENCE_SAID.get(entry['cadence'], entry['cadence'])}"
                  f"{'' if entry['authorized_recurring'] else ', no automatic renewal'}"
                  f" (by {by})", "registered", entry["amount"],
                  client="the owner" if by == "the owner" else None)
        return entry

    def mark_cancelled(self, merchant: str, on: Any = "") -> dict:
        """The user cancelled. From that date, any further charge is theft of
        a kind that usually goes unnoticed. If JEFFEREY cannot tell which
        register entry is meant, or when, NOTHING is recorded and the reply
        says so — a cancellation must never look armed when it is not."""
        key = _norm(merchant)
        if not key:
            return {"merchant": merchant, "marked_cancelled": 0, "cancelled_on": None,
                    "note": "NOT RECORDED: there is no merchant name I can use.",
                    "tell_the_user": "Ask which company they cancelled."}
        iso, err, ambiguous = _parse_date(on if str(on or "").strip() else "today",
                                          self._today())
        if err or ambiguous:
            why = err or (f"'{on}' could be read two ways (day/month or month/day)")
            return {"merchant": merchant, "marked_cancelled": 0, "cancelled_on": None,
                    "note": f"NOT RECORDED YET: {why}. Nothing is being watched for "
                            f"{merchant} until I have the date.",
                    "tell_the_user": "Ask for the date they cancelled, like 2026-10-12, "
                                     "then record it again."}

        def run() -> dict:
            ranked = self._ranked(merchant)
            strong = [(s, e) for s, e in ranked if s >= STRONG]
            entry = None
            if strong:
                top = max(s for s, _ in strong)
                tied = [e for s, e in strong if s >= top - 0.015]
                if len({e["id"] for e in tied}) > 1:
                    names = " or ".join(f"{e['merchant']} ({_m(e['amount'])})" for e in tied)
                    return {"merchant": merchant, "marked_cancelled": 0, "cancelled_on": None,
                            "note": f"NOT RECORDED YET: '{merchant}' could be {names}.",
                            "tell_the_user": f"Ask which one they cancelled: {names}."}
                entry = tied[0]
            elif ranked:
                best = max(ranked, key=lambda x: x[0])[1]
                return {"merchant": merchant, "marked_cancelled": 0, "cancelled_on": None,
                        "possible_match": best["merchant"],
                        "note": f"NOT RECORDED YET: nothing in the register is called "
                                f"'{merchant}'. Did you mean {best['merchant']}?",
                        "tell_the_user": f"Ask: did you mean {best['merchant']}? Then "
                                         f"record the cancellation under that name."}
            was = entry.get("cancelled_on") if entry is not None else None
            if (was and not entry.get("active", True) and iso > was
                    and not self.owner_present()):
                # A later date would make the charges in between look normal:
                # quieter because an AI asked (verify I-47: 2026-08-01 moved
                # to 2027-12-31 dropped a $45.18 dispute to $0). It waits.
                p = self._propose("cancel", {"merchant": entry["merchant"],
                                             "cancelled_on": iso, "was": was,
                                             "said": str(on or "").strip()}, entry, [])
                self.c._save()
                out = self._proposal_result(p, None)
                out.update(marked_cancelled=0, cancelled_on=was,
                           matched_to=entry["merchant"])
                out["note"] = (f"{entry['merchant']} is already on file as cancelled on "
                               f"{was}. A later date would make JEFFEREY quieter about the "
                               f"charges in between, so it waits for the owner to confirm "
                               f"it on his own Mac. Until then, any charge after {was} is "
                               f"still flagged.")
                return out
            if entry is None:
                # Never registered, but the user says they cancelled it — keep it
                # anyway, so a charge that shows up later is caught. Asked for
                # by an AI, it never makes earlier charges look agreed: nothing
                # becomes quieter because an AI asked (verify, I-47).
                entry = {
                    "id": _ident("c-", f"{merchant}|{_stamp()}|{time.time_ns()}"),
                    "key": key, "merchant": str(merchant), "amount": 0.0,
                    "cadence": "unknown", "authorized_recurring": False,
                    "note": "cancelled by the user", "active": True,
                    "cancelled_on": None, "amount_known": False, "aliases": [],
                    "updated": _stamp(), "v": 2,
                }
                if not self.owner_present():
                    entry["asked_by_ai"] = _client()
                self.c.data["expected_charges"].append(entry)
            entry["active"] = False
            entry["cancelled_on"] = iso
            if str(on or "").strip() and str(on).strip() != iso:
                entry["cancelled_on_said"] = str(on).strip()
            else:
                entry.pop("cancelled_on_said", None)
            entry["updated"] = _stamp()
            self._log(f"Charge register: {entry['merchant']} cancelled from {iso}",
                      "cancellation on file")
            self.c._save()
            earlier = ("Earlier charges are checked like any place not in the register."
                       if entry.get("asked_by_ai") and not entry.get("amount_known", True)
                       else "Charges on or before that date are treated as normal.")
            return {"merchant": entry["merchant"], "marked_cancelled": 1,
                    "cancelled_on": iso, "matched_to": entry["merchant"],
                    "note": f"Any charge from {entry['merchant']} dated after {iso} will "
                            f"be flagged. {earlier}"}

        return self._transaction(run)

    def add_alias(self, descriptor: str, merchant: str) -> dict:
        """'This is my Netflix': a statement name the owner confirms belongs to
        a register entry. From anyone but the owner it is a proposal."""
        alias = _norm(descriptor)
        entry, _hint = self._match(merchant, None)
        if not alias or entry is None:
            return {"merchant": merchant, "error": "I could not find that register entry, "
                                                   "or the statement name is empty."}

        def run() -> dict:
            if alias in entry.get("aliases", []) or alias == entry["key"]:
                return {"merchant": entry["merchant"], "note": "Already known by that name."}
            change = {"descriptor": str(descriptor), "alias": alias, "entry": entry["id"],
                      "merchant": entry["merchant"]}
            if self.owner_present():
                self._apply_alias(change)
                self.c._save()
                return {"merchant": entry["merchant"], "status": "registered",
                        "note": f"'{descriptor}' now counts as {entry['merchant']}."}
            p = self._propose("alias", change, entry, [])
            self.c._save()
            return self._proposal_result(p, None)

        return self._transaction(run)

    def _apply_alias(self, change: dict, log: bool = True) -> None:
        entry = next((e for e in self._entries() if e["id"] == change["entry"]), None)
        if entry is None:
            return
        entry.setdefault("aliases", []).append(change["alias"])
        if log:
            self._log(f"Charge register: '{change['descriptor']}' counts as {entry['merchant']}",
                  "name added")

    # ---------------------------------------------------------- proposals
    def _propose(self, kind: str, change: dict, target: dict | None,
                 why: list[str]) -> dict:
        props = self.c.data.setdefault("charge_proposals", [])
        for p in props:
            if p.get("status") == "waiting" and p["kind"] == kind and p["change"] == change:
                return p
        who = _client()
        p = {"id": _ident("p-", f"{kind}|{change}|{time.time_ns()}"),
             "kind": kind, "change": change, "target": target["id"] if target else None,
             "asked_by": who, "asked_on": _stamp(), "asked_day": self._today().isoformat(),
             "status": "waiting", "why": why}
        props.append(p)
        self._log(f"Charge register: {who} asked to {self._describe(p)}",
                  "proposed, waiting for the owner", change.get("amount"), client=who)
        return p

    @staticmethod
    def _describe(p: dict) -> str:
        ch = p["change"]
        if p["kind"] == "alias":
            return f"treat '{ch['descriptor']}' as {ch['merchant']}"
        if p["kind"] == "cancel":
            return (f"move the day {ch['merchant']} was cancelled from {ch['was']} to "
                    f"{ch['cancelled_on']}")
        return (f"add {ch['merchant']} at {_m(ch['amount'])} "
                f"{_CADENCE_SAID.get(ch['cadence'], ch['cadence'])}"
                f"{'' if ch['authorized_recurring'] else ', with no automatic renewal'}")

    def _proposal_result(self, p: dict, far: str | None) -> dict:
        ch = p["change"]
        out = {k: ch[k] for k in ("merchant", "amount", "cadence", "authorized_recurring")
               if k in ch}
        out.update(status="waiting_for_owner", proposal=p["id"])
        reason = (far + " ") if far else ""
        out["note"] = (f"{reason}Not in force yet: this waits for the owner to confirm it "
                       f"on their own Mac. Until then, charges from {ch['merchant']} are "
                       f"still mentioned, never kept quiet.")
        out["tell_the_user"] = (f"Say plainly that '{self._describe(p)}' is waiting for "
                                f"them to confirm, and that nothing has been kept quiet. "
                                f"To confirm it, they double-click 'Check my charges' on "
                                f"their Mac (or type /charges in 'Talk to JEFFEREY on this "
                                f"Mac'). Do not say it is registered.")
        return out

    def pending_changes(self) -> list[dict]:
        """Register changes an AI asked for, waiting for the owner."""
        def first_up(s: str) -> str:          # 'add PAYPAL *X …' keeps its capitals
            return s[:1].upper() + s[1:]
        return [{"id": p["id"], "what": first_up(self._describe(p)) + ".",
                 "kind": p["kind"], "asked_by": p["asked_by"], "asked_on": p["asked_on"][:10],
                 "why": list(p.get("why", []))}
                for p in self.c.data.get("charge_proposals", [])
                if p.get("status") == "waiting"]

    def confirm_change(self, proposal_id: str) -> dict:
        """Only the owner's own hands may make the register quieter."""
        if not self.owner_present():
            return {"refused": True,
                    "reason": "Only the owner, on their own Mac, can confirm a change to "
                              "the charge register.",
                    "tell_the_user": "Say it is waiting for them, and stop."}

        def run() -> dict:
            p = next((x for x in self.c.data.get("charge_proposals", [])
                      if x["id"] == proposal_id and x.get("status") == "waiting"), None)
            if p is None:
                return {"error": "That change is not waiting any more."}
            target = next((e for e in self._entries() if e["id"] == p.get("target")), None)
            if p["kind"] == "alias":
                self._apply_alias(p["change"], log=False)
                note = f"'{p['change']['descriptor']}' now counts as {p['change']['merchant']}."
            elif p["kind"] == "cancel":
                if target is None:
                    return {"error": "That entry is no longer in the register."}
                target.update(active=False, cancelled_on=p["change"]["cancelled_on"],
                              updated=_stamp())
                if p["change"].get("said") and p["change"]["said"] != p["change"]["cancelled_on"]:
                    target["cancelled_on_said"] = p["change"]["said"]
                else:
                    target.pop("cancelled_on_said", None)
                note = (f"{target['merchant']} is on file as cancelled on "
                        f"{target['cancelled_on']}.")
            else:
                entry = self._apply_expect(p["change"], target, by="the owner", log=False)
                # the agreement dates from when he said it, not from today
                asked = p.get("asked_day")
                if asked and asked < entry.get("agreed_on", asked):
                    entry["agreed_on"] = asked
                note = (f"{entry['merchant']} {_m(entry['amount'])} "
                        f"{_CADENCE_SAID.get(entry['cadence'], entry['cadence'])} "
                        f"is in your register.")
            p.update(status="confirmed", decided_on=_stamp())
            self._log(f"Charge register: the owner confirmed: {self._describe(p)}",
                      "confirmed", p["change"].get("amount"), client="the owner")
            self.c._save()
            return {"merchant": p["change"]["merchant"], "status": "confirmed", "note": note}

        return self._transaction(run)

    def decline_change(self, proposal_id: str) -> dict:
        """Declining keeps JEFFEREY watchful, so anyone may do it."""
        def run() -> dict:
            p = next((x for x in self.c.data.get("charge_proposals", [])
                      if x["id"] == proposal_id and x.get("status") == "waiting"), None)
            if p is None:
                return {"error": "That change is not waiting any more."}
            p.update(status="declined", decided_on=_stamp())
            self._log(f"Charge register: declined: {self._describe(p)}", "declined",
                      p["change"].get("amount"))
            self.c._save()
            return {"merchant": p["change"]["merchant"], "status": "declined",
                    "note": "Left out. The register is unchanged."}

        return self._transaction(run)

    def expected_charges(self) -> list[dict]:
        out = [dict(e) for e in self._entries()]
        for p in self.c.data.get("charge_proposals", []):
            if p.get("status") == "waiting" and p["kind"] == "expect":
                ch = p["change"]
                out.append({"merchant": ch["merchant"], "amount": ch["amount"],
                            "cadence": ch["cadence"],
                            "authorized_recurring": ch["authorized_recurring"],
                            "status": "waiting_for_owner", "proposal": p["id"],
                            "note": f"Not in force yet: {p['asked_by']} asked for this on "
                                    f"{p['asked_on'][:10]}; it waits for the owner."})
        return out

    # ---------------------------------------------------------- checking
    def _group(self, merchant: Any, amount: float) -> tuple[str, dict | None, dict | None]:
        entry, hint = self._match(merchant, amount)
        return (("e:" + entry["id"]) if entry else ("m:" + _norm(merchant))), entry, hint

    def check_charge(self, merchant: str, amount: Any, date: Any = "",
                     record: bool = True, ref: str = "") -> dict:
        """Hold one charge up against what the user actually agreed to. The
        same charge checked again is the same charge: it is counted once."""
        run = self._check([{"merchant": merchant, "amount": amount, "date": date,
                            "ref": ref}], record)
        if isinstance(run, dict) and "results" not in run:
            return run                                   # could not be saved
        if run["errors"]:
            return {"merchant": merchant, "amount": None, "date": str(date or ""),
                    "cadence": "unknown", "verdict": "could_not_check", "severity": 0.0,
                    "what_happened": "I could not check this charge: "
                                     + run["errors"][0]["problem"] + ".",
                    "recoverable": 0.0, "authorized_on_file": False,
                    "error": run["errors"][0]["problem"],
                    "action": "Ask the user for the missing or unclear detail, then check "
                              "it again. Nothing was kept."}
        return run["results"][0]

    def review_statement(self, charges: Any) -> dict:
        """Run a whole statement through at once. Every line is read first;
        if any line cannot be read, nothing is kept and the reply says which."""
        if not isinstance(charges, (list, tuple)):
            return {"checked": 0, "flagged": [], "quiet": 0, "recoverable_total": 0.0,
                    "annualized_estimate": 0.0,
                    "summary": "That was not a list of charges, so nothing was checked.",
                    "error": "charges must be a list of {merchant, amount, date}"}
        run = self._check(list(charges), True)
        if isinstance(run, dict) and "results" not in run:
            return run
        results, errors = run["results"], run["errors"]
        flagged = [r for r in results if r["verdict"] not in QUIET]
        attention = [r for r in flagged if r["verdict"] not in INFORMATIONAL]
        info = [r for r in flagged if r["verdict"] in INFORMATIONAL]
        refunds = [r for r in results if r["verdict"] == "refund"]
        # What is at stake, less what the same merchant already refunded on
        # this statement (verify I-39: '$95.00 at stake' beside its $95 refund)
        claim: dict[str, float] = {}
        back: dict[str, float] = {}
        for r, g in zip(results, run.get("groups") or [None] * len(results)):
            if r["verdict"] == "refund":
                back[g] = back.get(g, 0.0) - r["amount"]
            elif r["verdict"] not in QUIET:
                claim[g] = claim.get(g, 0.0) + r["recoverable"]
        gross = round(sum(claim.values()), 2)
        total = round(sum(max(0.0, c - back.get(g, 0.0)) for g, c in claim.items()), 2)
        netted = round(gross - total, 2)
        flagged.sort(key=lambda r: r["verdict"] in INFORMATIONAL)   # alarms first
        annual = round(sum(
            r["recoverable"] * (PER_YEAR.get(r["cadence"], 1)
                                if r["verdict"] == "amount_increased" and r["authorized_on_file"]
                                else 1)
            for r in flagged), 2)
        n = len(results)
        parts = []
        if errors:
            listed = "; ".join(f"line {e['line']}: {e['problem']}" for e in errors[:5])
            parts.append(f"I could not read {len(errors)} of {len(charges)} lines ({listed}). "
                         f"Nothing from this statement has been kept yet: fix "
                         f"{'that line' if len(errors) == 1 else 'those lines'} and send "
                         f"the whole statement again.")
        lead = "Of the lines I could read: " if errors and n else ""
        if not n and not errors:
            parts.append("There were no charges in that statement.")
        elif attention:
            if netted and not total:
                stake = (f"the same place already refunded {_m(netted)}, so nothing is left "
                         f"at stake")
            elif netted:
                stake = (f"{_m(total)} at stake, after {_m(netted)} the same places already "
                         f"refunded")
            else:
                stake = f"{_m(total)} at stake"
            parts.append(f"{lead}{len(attention)} of {n} charges need your attention "
                         f"({stake}).")
        elif n:
            parts.append(lead + ("everything matches what you agreed to." if lead else
                                 "Everything on this statement matches what you agreed to.")
                         if not info else lead + ("nothing needs your attention." if lead else
                                                  "Nothing on this statement needs your "
                                                  "attention."))
        if info:
            parts.append(f"{len(info)} {'is' if len(info) == 1 else 'are'} from "
                         f"{'a place' if len(info) == 1 else 'places'} not in your register "
                         f"— most likely ordinary purchases. Have a look in case one isn't "
                         f"yours.")
        if refunds:
            parts.append(f"{len(refunds)} refund{'' if len(refunds) == 1 else 's'} came back "
                         f"({_m(sum(-r['amount'] for r in refunds))}).")
        again = sum(1 for r in results if r.get("already_on_file"))
        if again:
            parts.append(f"{again} of these {'was' if again == 1 else 'were'} already on file "
                         f"from an earlier check, so nothing was counted twice.")
        undated = sum(1 for r in results if not r["date"])
        if undated:
            parts.append(f"{undated} had no date, so I checked "
                         f"{'it' if undated == 1 else 'them'} but did not keep "
                         f"{'it' if undated == 1 else 'them'} on file.")
        out = {
            "checked": n, "flagged": flagged, "quiet": n - len(flagged),
            "recoverable_total": total, "annualized_estimate": annual,
            "summary": " ".join(parts),
            "attention": len(attention), "new_merchants": len(info),
            "refunds": refunds, "already_on_file": again, "recorded": run["recorded"],
        }
        if errors:
            out["errors"] = errors
            out["note"] = out["summary"]
        return out

    def _read_line(self, raw: Any, i: int, today: _dt.date) -> tuple[dict | None, str | None]:
        if not isinstance(raw, dict):
            return None, ("this is not a charge; each line needs a merchant, an amount and "
                          "a date")
        merchant = raw.get("merchant")
        if not _norm(merchant or ""):
            return None, "there is no merchant name"
        amt, err = _parse_amount(raw.get("amount"))
        if err:
            return None, f"{merchant}: {err}"
        said = raw.get("date")
        alt = None
        if said is None or not str(said).strip():
            iso = None
        else:
            iso, derr, amb = _parse_date(said, today)
            if derr:
                return None, f"{merchant}: {derr}"
            # '11/10/2026' is 10 November to some and 11 October to others
            # (verify I-39). A statement lists charges already made, so a
            # reading in the future is not the one; when both are past, the
            # other is kept, and a verdict that depends on which is a question.
            alt = _other_reading(said) if amb else None
            soon = (today + _dt.timedelta(days=2)).isoformat()
            if iso > soon and alt and alt <= soon:
                iso, alt = alt, None
            elif iso > soon:
                return None, (f"{merchant}: '{str(said).strip()}' is a date in the future, and "
                              f"a statement only lists charges already made; please check "
                              f"the date")
            elif alt and alt > soon:
                alt = None
        return {"merchant": str(merchant), "amount": amt, "date": iso, "date_alt": alt,
                "date_said": str(said).strip() if said is not None else "",
                "ref": _ref(raw.get("ref") or raw.get("reference") or raw.get("line_id")),
                "cents": int(round(amt * 100)), "uncertain": False}, None

    def _check(self, lines: list, record: bool) -> dict:
        today = self._today()
        parsed, errors = [], []
        for i, raw in enumerate(lines, 1):
            line, problem = self._read_line(raw, i, today)
            if problem:
                errors.append({"line": i, "problem": problem})
            else:
                parsed.append(line)
        keep = record and not errors and not _door_shut()

        def run() -> dict:
            groups: dict[tuple, tuple] = {}

            def group(merchant, amount):
                k = (merchant, amount)
                if k not in groups:
                    groups[k] = self._group(merchant, amount)
                return groups[k]

            counts: dict[tuple, int] = {}
            for line in parsed:
                g, entry, hint = group(line["merchant"], line["amount"])
                line.update(group=g, entry=entry, hint=hint)
                n = counts[(g, line["cents"], line["date"])] = \
                    counts.get((g, line["cents"], line["date"]), 0) + 1
                line["seq"] = n
            touched = {line["group"] for line in parsed}
            stored = self._charges()
            members: dict[str, list] = {g: [] for g in touched}
            given = {(line["group"], line["cents"], line["date"]) for line in parsed
                     if line["date"] is not None}
            confirmed = False
            for idx, rec in enumerate(stored):
                if rec.get("unreadable"):
                    continue
                g = group(rec["merchant"], rec["amount"])[0]
                if g in members:
                    cents = int(round(rec["amount"] * 100))
                    if (keep and rec.get("date_uncertain")
                            and (g, cents, rec.get("date")) in given):
                        # the date has now been given for this very charge
                        rec.pop("date_uncertain", None)
                        rec["date_confirmed"] = _stamp()
                        confirmed = True
                    members[g].append(self._item(rec, idx))
            base = len(stored)
            for j, line in enumerate(parsed):
                line["order"] = base + j
                members[line["group"]].append(line)
            verdicts: dict[int, dict] = {}
            twin_of: dict[int, dict] = {}
            for g, items in members.items():
                entry = next((x["entry"] for x in parsed if x["group"] == g), None)
                v, tw = self._evaluate(entry, items)
                verdicts.update(v)
                twin_of.update(tw)
            waiting = {_norm(p["change"].get("merchant", ""))
                       for p in self.c.data.get("charge_proposals", [])
                       if p.get("status") == "waiting" and p.get("kind") == "expect"}
            changed = False
            results = []
            for line in parsed:
                line["waiting"] = line["entry"] is None and _norm(line["merchant"]) in waiting
                v = verdicts[id(line)]
                twin = twin_of.get(id(line))
                already = twin is not None and "rec" in twin
                kept = False
                if keep and not already and line["date"] is not None and twin is None:
                    rec = {"key": _norm(line["merchant"]), "merchant": line["merchant"],
                           "amount": line["amount"], "date": line["date"],
                           "seq": line["seq"], "verdict": v["verdict"],
                           "recoverable": round(v["recover"], 2), "seen": _stamp(),
                           "client": _client(), "v": 2}
                    if line["ref"]:
                        rec["ref"] = line["ref"]
                    if line["date_said"] and line["date_said"] != line["date"]:
                        rec["date_said"] = line["date_said"]
                    if line.get("date_alt"):
                        rec["date_alt"] = line["date_alt"]
                    stored.append(rec)
                    kept = changed = True
                results.append(self._result(line, v, already, kept))
            if keep:
                # bring the stored verdicts of every touched merchant up to date
                for items in members.values():
                    for it in items:
                        if "rec" in it:
                            v = verdicts[id(it)]
                            if (it["rec"].get("verdict") != v["verdict"]
                                    or it["rec"].get("recoverable") != round(v["recover"], 2)):
                                if "seen" not in it["rec"]:      # written by the old code
                                    it["rec"].setdefault("verdict_before",
                                                         it["rec"].get("verdict"))
                                it["rec"]["verdict"] = v["verdict"]
                                it["rec"]["recoverable"] = round(v["recover"], 2)
                                changed = True
                if changed or confirmed:
                    self.c._save()
            return {"results": results, "errors": errors,
                    "groups": [line["group"] for line in parsed],
                    "recorded": sum(1 for r in results if r.get("kept"))}

        return self._transaction(run)

    @staticmethod
    def _item(rec: dict, idx: int) -> dict:
        """A stored charge, the way it is judged beside new ones."""
        return {"rec": rec, "merchant": rec["merchant"], "amount": rec["amount"],
                "date": rec.get("date"), "seq": rec.get("seq", 1), "ref": _ref(rec.get("ref")),
                "cents": int(round(rec["amount"] * 100)), "order": idx,
                "date_alt": rec.get("date_alt"), "date_said": rec.get("date_said", ""),
                "uncertain": bool(rec.get("date_uncertain"))}

    def _evaluate(self, entry: dict | None, items: list[dict]) -> tuple[dict, dict]:
        """Judge every charge of one merchant in date order. A charge seen
        again (same amount, date and line) is the same charge: it gets its
        twin's verdict and never counts twice."""
        # Within one amount and day, the charges are told apart by reference
        # when they have one and by place in the statement when they do not;
        # the same charge seen once with its reference and once without is
        # still one charge (verify I-37: it became a 'duplicate' and an
        # $18.63 claim). A line without a reference is the n-th charge of
        # that day; a reference never seen before is the first charge of the
        # day that has none yet.
        buckets: dict[tuple, list[dict]] = {}
        twin_of: dict[int, dict] = {}
        uniq = []
        for it in sorted(items, key=lambda x: x["order"]):
            charges = buckets.setdefault((it["cents"], it["date"]), [])
            ref = _ref(it.get("ref"))
            twin = None
            if ref:
                # ...an earlier check's charge, never another line of this statement
                twin = next((c for c in charges if ref in c["_refs"]), None) or \
                    next((c for c in charges if not c["_refs"] and "rec" in c), None)
                if twin is not None:
                    twin["_refs"].add(ref)
            elif len(charges) >= it["seq"]:
                twin = charges[it["seq"] - 1]
            if twin is not None:
                twin_of[id(it)] = twin
                continue
            it["_refs"] = {ref} if ref else set()
            charges.append(it)
            uniq.append(it)
        timeline = sorted(uniq, key=lambda x: (x["date"] is None, x["date"] or "",
                                               x["seq"], x["order"]))
        prior: list[dict] = []
        verdicts: dict[int, dict] = {}
        for it in timeline:
            v = verdicts[id(it)] = self._judge(entry, it, prior)
            if it["amount"] > 0 and it["date"] is not None:
                it["_verdict"] = v["verdict"]
                prior.append(it)
        for tid, twin in twin_of.items():
            verdicts[tid] = verdicts[id(twin)]
        return verdicts, twin_of

    @staticmethod
    def _judge(entry: dict | None, it: dict, prior: list[dict]) -> dict:
        def V(verdict, severity, recover, detail, authorized):
            return {"verdict": verdict, "severity": severity, "recover": recover,
                    "detail": detail, "authorized": authorized}

        amt, d = it["amount"], it["date"]
        name = entry["merchant"] if entry else it["merchant"]
        when = f" on {d}" if d else ""
        if amt < 0:
            return V("refund", 0.0, 0.0,
                     f"A refund of {_m(-amt)} from {name}{when}. Nothing to do: it comes "
                     f"off anything being disputed with {name}.", bool(entry))
        if entry is None:
            if _SCAM.search(_fold(it["merchant"])):
                return V("possible_scam", 0.95, 0.0,
                         f"{_m(amt)} to '{it['merchant']}'{when}. Gift cards, bitcoin "
                         f"machines and money-wiring services are how scammers ask to be "
                         f"paid. Ask gently whether someone asked for the money this way.",
                         False)
            if amt <= 1.00:
                return V("possible_card_testing", 0.8, amt,
                         f"Only {_m(amt)} to '{it['merchant']}'{when}, a place not in your "
                         f"register. Tiny charges like this are how card thieves test a "
                         f"stolen card. Do you recognize it?", False)
            if amt >= 500:
                return V("unexpected_merchant", 0.6, 0.0,
                         f"{_m(amt)} at '{it['merchant']}'{when}. This place isn't in your "
                         f"register, and it is a large amount, so please make sure you "
                         f"recognize it.", False)
            return V("unexpected_merchant", 0.3, 0.0,
                     f"{_m(amt)} at '{it['merchant']}'{when}. This place isn't in your "
                     f"register — most likely an ordinary purchase. Nothing to do unless "
                     f"you don't recognize it.", False)

        reg, cad = entry["amount"], entry["cadence"]
        before = ""
        if not entry.get("active", True):
            c_on = entry.get("cancelled_on")
            if not c_on:
                said = entry.get("cancelled_on_said")
                return V("needs_date", 0.5, 0.0,
                         f"You told me {name} was cancelled"
                         f"{f' ({said!r})' if said else ''}, but I don't have the date it "
                         f"was cancelled, so I can't tell whether this {_m(amt)}{when} came "
                         f"before or after.", False)
            if d is None:
                return V("needs_date", 0.5, 0.0,
                         f"{name} was cancelled on {c_on}. This {_m(amt)} has no date, so I "
                         f"can't tell whether it came before or after.", False)
            alt = it.get("date_alt")
            if alt and min(d, alt) <= c_on < max(d, alt):
                return V("needs_date", 0.5, 0.0,
                         f"'{it.get('date_said') or d}' could be {_spoken(d)} or "
                         f"{_spoken(alt)}. You cancelled {name} on {_spoken(c_on)}, so "
                         f"which one it is decides whether this {_m(amt)} came after. "
                         f"Which day is it?", False)
            if d > c_on and it.get("uncertain"):
                return V("needs_date", 0.5, 0.0, _OLD_DATE.format(
                    name=name, amt=_m(amt), d=d, what=f"came after {c_on}, the day you "
                                                      f"cancelled"), False)
            if d > c_on:
                return V("charged_after_cancel", 1.0, amt,
                         f"You cancelled {name} on {c_on} and they charged {_m(amt)} anyway "
                         f"on {d}.", False)
            if not entry.get("amount_known", True):
                if entry.get("asked_by_ai"):
                    # Only an AI said this place was ever theirs: before the
                    # cancellation it is judged like any place not in the
                    # register, never 'agreed'.
                    return Guardian._judge(None, it, prior)
                return V("expected", 0.0, 0.0,
                         f"{name} {_m(amt)} on {d}, on or before the cancellation date "
                         f"({c_on}). Nothing to do.", True)
            before = f" (This is dated on or before the cancellation date, {c_on}.)"

        if not entry.get("amount_known", True):
            return V("unexpected_merchant", 0.3, 0.0,
                     f"{_m(amt)} from {name}{when}. {name} is on file, but not the amount "
                     f"you agreed to pay, so I can't tell whether this is right.", False)
        once = cad == "once" or not entry.get("authorized_recurring", True)
        if once and prior:
            if d is None:
                return V("needs_date", 0.5, 0.0,
                         f"You agreed to pay {name} only once. I need the date of this "
                         f"{_m(amt)} to tell whether it is that one charge or a renewal "
                         f"you never agreed to.", False)
            last = prior[-1]
            if it.get("uncertain") or last.get("uncertain"):
                return V("needs_date", 0.5, 0.0, _OLD_DATE.format(
                    name=name, amt=_m(amt), d=last["date"] if last.get("uncertain") else d,
                    what="is a second charge after the one you agreed to"), False)
            return V("unauthorized_renewal", 1.0, amt,
                     f"You agreed to pay {name} once ({_m(reg)}) and did not agree to "
                     f"automatic renewal. This {_m(amt)} on {d} is another charge after "
                     f"the one on {last['date']} — a renewal you never authorized.", False)
        agreed = _agreed_on(entry)
        if once and not prior and d is not None and agreed and _days(d, agreed) > _ONCE_DAYS:
            # The first charge JEFFEREY sees came long after he agreed to pay
            # once: almost always the renewal (verify I-38: a same-price
            # renewal a year later was 'as agreed. Quiet.'). He is asked first,
            # in case this is the one payment, charged late.
            v = V("unauthorized_renewal", 1.0, amt,
                  f"You agreed on {agreed} to pay {name} once ({_m(reg)}) and did not agree "
                  f"to automatic renewal. This {_m(amt)} on {d} came {_days(d, agreed)} days "
                  f"later, and no earlier charge from {name} is on file. If you already paid "
                  f"when you agreed, this is a renewal you never authorized.", False)
            v["ask_first"] = agreed
            return v
        if d is not None and prior and (cad in CADENCES or cad == "unknown"):
            min_gap = CADENCES[cad][1] if cad in CADENCES else 1
            # A plan billed every three months or longer is billed once in its
            # period, whatever the amount: a second charge inside it is a
            # second bill, not a price change (verify I-38: $59.99 against a
            # yearly $119.99 was 'less than expected. Nothing to do').
            long = cad in CADENCES and CADENCES[cad][0] >= 91
            # measured from the last charge that was itself accepted: an extra
            # bill must not push the next real renewal into looking early
            same = [p for p in prior if (long or _same_amount(p["amount"], amt))
                    and p.get("_verdict") not in ("duplicate", "possible_card_testing")]
            if same:
                p = same[-1]
                gap = _days(d, p["date"])
                if gap < min_gap:
                    if it.get("uncertain") or p.get("uncertain"):
                        return V("needs_date", 0.5, 0.0, _OLD_DATE.format(
                            name=name, amt=_m(amt), d=p["date"] if p.get("uncertain") else d,
                            what="is a second bill for the same period"), False)
                    alike = _same_amount(p["amount"], amt)
                    if gap == 0 and alike:
                        text = f"{name} charged {_m(amt)} twice on {d}."
                    elif gap == 0:
                        text = (f"{name} charged {_m(p['amount'])} and {_m(amt)} on the same "
                                f"day, {d}, but it is billed {_CADENCE_SAID.get(cad, cad)}.")
                    else:
                        text = (f"{name} is billed {_CADENCE_SAID.get(cad, cad)}, but it "
                                f"charged {_m(amt)} on {d}, only {gap} day"
                                f"{'' if gap == 1 else 's'} after the {_m(p['amount'])} on "
                                f"{p['date']}." + ("" if alike else
                                                   " That is a second bill inside the same "
                                                   "period."))
                    return V("duplicate", 0.9, amt, text + before, True)
        if amt > reg + 0.01:
            delta = amt - reg
            if once:
                return V("amount_increased", 1.0, amt,
                         f"{name} charged {_m(amt)}{when}. You agreed to pay {_m(reg)} once "
                         f"and never agreed to automatic renewal, so the whole {_m(amt)} is "
                         f"in question." + before, False)
            if reg <= 0:
                text = f"{name} was registered as free and charged {_m(amt)}{when}."
            else:
                text = (f"{name} went from {_m(reg)} to {_m(amt)} — up {_m(delta)} "
                        f"({delta / reg * 100:.0f}%).")
            if cad in PER_YEAR:
                text += (f" Billed {_CADENCE_SAID[cad]}, that's {_m(delta * PER_YEAR[cad])} "
                         f"a year.")
            return V("amount_increased", min(1.0, 0.4 + delta / max(reg, 1)), delta,
                     text + before, True)
        if amt < reg - 0.01:
            if (amt < 2.00 and reg >= 5.00) or amt < 0.25 * reg:
                return V("possible_card_testing", 0.85, amt,
                         f"Only {_m(amt)} from {name}{when}, when you expect {_m(reg)}. "
                         f"Very small charges like this are how card thieves test a stolen "
                         f"card. Do you recognize it?", False)
            return V("amount_decreased", 0.1, 0.0,
                     f"{name} charged less than expected ({_m(amt)} instead of {_m(reg)}). "
                     f"Nothing to do." + before, True)
        return V("expected", 0.0, 0.0, f"{name} {_m(amt)} — as agreed. Quiet." + before, True)

    @staticmethod
    def _result(line: dict, v: dict, already: bool, kept: bool) -> dict:
        entry, hint = line["entry"], line["hint"]
        detail = v["detail"]
        if hint is not None and entry is None and v["verdict"] == "unexpected_merchant":
            if hint.get("amount_known", True):
                detail += (f" It looks a little like {hint['merchant']} "
                           f"({_m(hint['amount'])}), but the amount is different.")
            else:
                detail += f" It looks a little like {hint['merchant']}."
        if line.get("waiting"):
            detail += (" A request to add it to your register is waiting for the owner to "
                       "confirm.")
        if already:
            detail += (" This charge was already on file from an earlier check, so it is "
                       "counted once.")
        if line["date"] is None and v["verdict"] not in QUIET | {"needs_date"}:
            detail += " There is no date, so I have not kept it on file."
        out = {
            "merchant": line["merchant"], "amount": line["amount"],
            "date": line["date"] or "",
            "cadence": entry["cadence"] if entry else "unknown",
            "verdict": v["verdict"], "severity": round(v["severity"], 2),
            "what_happened": detail, "recoverable": round(v["recover"], 2),
            "authorized_on_file": bool(v["authorized"]),
            "action": _action_for(v["verdict"]),
            "matched_to": entry["merchant"] if entry else None,
            "already_on_file": already, "kept": kept,
        }
        if hint is not None and entry is None:
            out["possible_match"] = hint["merchant"]
            out["action"] += (f" If they say it is their {hint['merchant']}, call "
                              f"name_for_charge with this name and '{hint['merchant']}': it "
                              f"waits for the owner to confirm, then this name counts as "
                              f"{hint['merchant']}.")
        return out

    # -------------------------------------------------------------- dispute
    def dispute_pack(self, merchant: str, not_mine: Any = False) -> dict:
        """Everything needed to get the money back, assembled — so the user
        isn't the one digging through statements at 11pm. It claims only what
        is recoverable, takes refunds off, and words the demand by what
        actually happened. `not_mine`: the user says charges from a place
        that is not in his register are not his (verify regression: such a
        charge could no longer get a pack); they are claimed in full, and the
        way back is the bank, never a letter to that place."""
        not_mine, _ok = _parse_bool(not_mine) if not isinstance(not_mine, bool) else (not_mine, True)
        key = _norm(merchant)
        empty = {"merchant": merchant, "what_was_authorized": None, "charges_in_dispute": [],
                 "amount_in_dispute": 0.0, "full_history": []}
        if not key:
            return dict(empty, error="There is no merchant name I can use.",
                        how_to_use="Ask which company this is about.")
        entry, hint = self._match(merchant, None)
        target = ("e:" + entry["id"]) if entry else ("m:" + key)
        cache: dict[tuple, str] = {}
        items = []
        for idx, rec in enumerate(self._charges()):
            if rec.get("unreadable"):
                continue
            k = (rec["merchant"], rec["amount"])
            if k not in cache:
                cache[k] = self._group(rec["merchant"], rec["amount"])[0]
            if cache[k] == target:
                items.append(self._item(rec, idx))
        if not items and entry is None and hint is not None:
            return dict(empty, what_was_authorized="nothing on file — no agreement recorded",
                        how_to_use=f"Nothing is on file under '{merchant}'. Ask whether they "
                                   f"mean {hint['merchant']}, and build the pack under that "
                                   f"name.")
        verdicts, twin_of = self._evaluate(entry, items)
        history, disputed, refunds = [], [], []
        for it in sorted(items, key=lambda x: (x["date"] or "", x["order"])):
            v = verdicts[id(it)]
            row = {"merchant": it["merchant"], "amount": it["amount"], "date": it["date"],
                   "verdict": v["verdict"], "recoverable": round(v["recover"], 2)}
            if id(it) in twin_of:
                row["counted_once"] = "the same charge was checked more than once"
                history.append(row)
                continue
            history.append(row)
            if it["amount"] < 0:
                refunds.append(row)
            elif v["verdict"] in RECOVERABLE and v["recover"] > 0:
                disputed.append(dict(row, what_happened=v["detail"],
                                     authorized_on_file=v["authorized"],
                                     **({"ask_first": v["ask_first"]} if v.get("ask_first")
                                        else {})))
            elif (not_mine and entry is None and v["verdict"] in NOT_RECOGNISED
                  and it["amount"] > 0):
                row["recoverable"] = it["amount"]
                disputed.append(dict(row, verdict="not_recognised",
                                     what_happened=(f"{_m(it['amount'])} at '{it['merchant']}'"
                                                    f"{' on ' + it['date'] if it['date'] else ''}"
                                                    f", which the user says is not theirs."),
                                     authorized_on_file=False))
        claimed = sum(r["recoverable"] for r in disputed)
        refunded = round(sum(-r["amount"] for r in refunds), 2)
        amount = round(max(0.0, claimed - refunded), 2)
        dated = sorted(r["date"] for r in disputed if r["date"])
        deadline = None
        if dated:
            deadline = (_dt.date.fromisoformat(dated[0]) + _dt.timedelta(days=120)).isoformat()
        name = entry["merchant"] if entry else merchant
        return {
            "merchant": name,
            "what_was_authorized": (self._agreement(entry) if entry else
                                    "nothing on file — no agreement recorded"),
            "charges_in_dispute": disputed,
            "amount_in_dispute": amount,
            "refunds_received": refunded,
            "chargeback_deadline_estimate": deadline,
            "full_history": history,
            "how_to_use": self._how_to_use(name, entry, disputed, refunded, amount, deadline),
        }

    @staticmethod
    def _agreement(e: dict) -> dict:
        out = {"merchant": e["merchant"],
               "amount": e["amount"] if e.get("amount_known", True) else None,
               "cadence": e["cadence"], "authorized_recurring": e["authorized_recurring"],
               "active": e.get("active", True), "cancelled_on": e.get("cancelled_on"),
               "note": e.get("note", ""), "updated": e.get("updated")}
        if e.get("cancelled_on_said"):
            out["cancelled_on_said"] = e["cancelled_on_said"]
        return out

    @staticmethod
    def _how_to_use(name: str, entry: dict | None, disputed: list[dict], refunded: float,
                    amount: float, deadline: str | None) -> str:
        if not disputed:
            text = (f"Nothing from {name} is in dispute: every charge on file is as agreed, "
                    f"or is waiting for an answer from the user. There is no letter to write.")
            if entry is None:
                text += (f" If the user says a charge from {name} is not theirs, call "
                         f"dispute_pack again with not_mine=true.")
            if refunded:
                text += f" {name} has refunded {_m(refunded)}."
            return text
        if amount <= 0:
            return (f"{name} has already refunded {_m(refunded)}, which covers everything "
                    f"that was in question. There is nothing left to ask for; tell the user "
                    f"so.")
        by: dict[str, list[dict]] = {}
        for r in disputed:
            by.setdefault(r["verdict"], []).append(r)

        def dates(rows):
            return ", ".join(r["date"] or "no date" for r in rows)

        parts = []
        bank = ("possible_card_testing", "not_recognised")
        letter = [v for v in by if v not in bank]
        ask = round(max(0.0, sum(r["recoverable"] for r in disputed
                                 if r["verdict"] not in bank) - refunded), 2)
        if "not_recognised" in by:
            parts.append(f"The user says the charges from {name} "
                         f"({dates(by['not_recognised'])}, "
                         f"{_m(sum(r['recoverable'] for r in by['not_recognised']))} in all) are "
                         f"not theirs. Do not write to {name}: the next step is to call the "
                         f"bank using the number on the back of the card, say these charges "
                         f"are not theirs, and ask for them back and for a new card. Calling "
                         f"is an Act: authorize_action first, with no amount, then log_action.")
        first = sorted({r["ask_first"] for r in disputed if r.get("ask_first")})
        if first:
            parts.append(f"Before writing anything, ask the user whether they already paid "
                         f"{name} once when they agreed (on {first[0]}). If this charge was "
                         f"that one payment, there is nothing to dispute.")
        if "possible_card_testing" in by:
            parts.append(f"The tiny charges ({dates(by['possible_card_testing'])}) look like "
                         f"card fraud, not a billing mistake. Do not write to {name} about "
                         f"them: the user should call the bank using the number on the back "
                         f"of the card and ask for the card to be replaced.")
        if letter:
            parts.append(f"Call draft_guidance('dispute a charge', '{name}') and write the "
                         f"letter in the user's voice. Ask {name} for {_m(ask)} back in "
                         f"total — no more.")
        if "charged_after_cancel" in by:
            c_on = entry.get("cancelled_on") if entry else None
            parts.append(f"Say they cancelled on {c_on or 'the date they cancelled'} and were "
                         f"charged after that ({dates(by['charged_after_cancel'])}). Ask for "
                         f"those charges back and for written confirmation that billing has "
                         f"stopped; attach the cancellation confirmation if they have it.")
        if "duplicate" in by:
            parts.append(f"Say they were billed again for the same period "
                         f"({dates(by['duplicate'])}). Ask for the extra charge back — not "
                         f"the one they agreed to.")
        inc = by.get("amount_increased", [])
        agreed_inc = [r for r in inc if r["authorized_on_file"]]
        never_inc = [r for r in inc if not r["authorized_on_file"]]
        if agreed_inc:
            reg = _m(entry["amount"]) if entry else "the agreed price"
            parts.append(f"The subscription itself was agreed to at {reg}, so do NOT say it "
                         f"was unauthorized. Say the price went up ({dates(agreed_inc)}), ask "
                         f"whether notice of the increase was sent, and ask for the "
                         f"difference back "
                         f"({_m(sum(r['recoverable'] for r in agreed_inc))}).")
        renewals = by.get("unauthorized_renewal", []) + never_inc
        if renewals:
            parts.append(f"Say plainly that they agreed to pay once and never agreed to "
                         f"automatic renewal or recurring billing ({dates(renewals)}). Ask for "
                         f"a full refund of those charges and for automatic renewal to be "
                         f"turned off.")
        if refunded:
            parts.append(f"{name} has already refunded {_m(refunded)}; that is already taken "
                         f"off the amount above. Mention it.")
        if letter:
            parts.append("Show the draft to the user. Sending is an Act — authorize_action on "
                         "'correspondence' (no amount: a letter costs nothing), then "
                         "log_action.")
        if deadline and letter:
            parts.append(f"If {name} refuses, the next step is the card issuer's chargeback "
                         f"process. Card issuers often allow about 120 days from the charge: "
                         f"counting from the earliest charge, that is roughly {deadline}. This "
                         f"is an estimate — the card agreement has the real limit, so tell "
                         f"the user before it passes. Have the card's last four digits and the "
                         f"statement at hand when calling.")
        return " ".join(parts)


# ===================================================================== the owner's console
def main(argv: list[str] | None = None) -> int:
    """The owner's own hands on the charge register.

        python connector/guardian.py list      what you agreed to, and what waits
        python connector/guardian.py review    confirm or decline, one by one
    """
    import argparse

    ap = argparse.ArgumentParser(
        prog="guardian.py",
        description="Your charge register: what you agreed to pay, and the changes "
                    "an AI asked for that wait for you.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="show your charge register and anything waiting for you")
    sub.add_parser("review", help="confirm or decline the changes an AI asked for")
    args = ap.parse_args(argv)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import home
    why = home.problem()
    if why:
        print(why[0].upper() + why[1:] + ".")
        return 2
    from conscience import Conscience, StoreProblem
    try:
        g = Guardian(Conscience())
    except StoreProblem as e:
        print(e.for_owner())
        return 2
    if args.cmd == "review":
        if not sys.stdin.isatty():
            print("This needs you at the keyboard: open Terminal and run it yourself.")
            return 2
        return review_at_the_keyboard(g)
    entries = g.expected_charges()
    if not entries:
        print("Your charge register is empty.")
        return 0
    for e in entries:
        if e.get("status") == "waiting_for_owner":
            state = "waiting for you to confirm"
        elif e.get("active", True):
            state = "agreed"
        else:
            state = f"cancelled {e.get('cancelled_on') or '(date unknown)'}"
        amount = _m(e["amount"]) if e.get("amount_known", True) else "amount unknown"
        print(f"  {e['merchant']}: {amount} {_CADENCE_SAID.get(e['cadence'], e['cadence'])}"
              f" — {state}")
    return 0


def review_at_the_keyboard(g: "Guardian", input_fn=input, out=print) -> int:
    """The owner, at his own keyboard, goes through what an AI asked to add
    to his list of agreed payments: yes adds it, no leaves it out. Used by
    `python connector/guardian.py review` and by /charges in 'Talk to
    JEFFEREY on this Mac'. Only here is a change confirmed — inside
    access.owner_console(), after a yes he typed (answers.py: 'oui' is a yes,
    a closed window or an empty answer never is)."""
    import access
    import answers
    waiting = g.pending_changes()
    if not waiting:
        out("  Nothing is waiting for you. Your list of agreed payments is as you "
            "left it.")
        return 0
    out(f"  {len(waiting)} change{'' if len(waiting) == 1 else 's'} to your list of "
        f"agreed payments {'is' if len(waiting) == 1 else 'are'} waiting for you.")
    for p in waiting:
        out("")
        out("  " + p["what"])
        out(f"     asked by {p['asked_by']} on {p['asked_on']}")
        for w in p["why"]:
            out("     Please check: " + w)
        q = ("  Add this to your list?" if p.get("kind") == "expect"
             else "  Make this change?")
        if answers.ask_yes_no(q + " Type yes or no, then press return: ",
                              input_fn=input_fn, out=out):
            with access.owner_console():          # his own hands, this one change
                r = g.confirm_change(p["id"])
            out("     Done. " + str(r.get("note") or r.get("error") or ""))
        else:
            g.decline_change(p["id"])
            out("     Left out. Nothing changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
