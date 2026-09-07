"""
JEFFEREY the Guardian — money that leaves without asking
========================================================

The GoDaddy problem: a card gets charged, nobody asked you, and finding out
takes forever — by which time it's "policy" and you're on hold. Multiply that
by every auto-renewal, silent price hike, zombie subscription and duplicate
billing on earth and you are looking at an enormous amount of money quietly
leaving ordinary people who never agreed to it.

This module is Jefferey standing in front of that.

He keeps a register of what SHOULD be charged — merchant, amount, cadence,
and whether the user ever authorized recurring billing at all. Then every
charge gets checked against it:

  expected            → quiet. Don't interrupt.
  amount_increased    → they raised the price. Here is the delta, in dollars.
  unexpected_merchant → nobody registered this. Why is it on your card?
  charged_after_cancel→ you cancelled. They took the money anyway.
  duplicate           → billed twice in the same window.

Anything that isn't `expected` becomes a scored opportunity (risk-reducing,
so it earns the right to interrupt) and turns the orb protective. Jefferey
can then assemble a dispute pack: what was taken, when, what was authorized,
and a demand written in the user's own voice.

He never moves money. Cancelling or disputing is an Act — gated, capped,
and logged like everything else.
"""

from __future__ import annotations

import re
import time
from typing import Any


def _norm(merchant: str) -> str:
    """Card statements are shouty and abbreviated: 'GODADDY.COM 480-505-8855'
    and 'GoDaddy Inc' are the same company."""
    s = str(merchant).lower()
    s = re.sub(r"\b(?:inc|llc|ltd|corp|co|com|net|org)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b\d{3,}\b", " ", s)          # phone numbers, store ids
    return re.sub(r"\s+", " ", s).strip()


class Guardian:
    """Watches what leaves the user's accounts. Holds no card numbers — only
    what was charged, by whom, and whether it was ever agreed to."""

    def __init__(self, conscience):
        self.c = conscience
        self.c.data.setdefault("expected_charges", [])
        self.c.data.setdefault("charges_seen", [])

    # ------------------------------------------------------------- register
    def expect_charge(
        self,
        merchant: str,
        amount: float,
        cadence: str = "monthly",
        authorized_recurring: bool = True,
        note: str = "",
    ) -> dict:
        """Register a charge the user has actually agreed to. Anything not in
        this register is, by default, a question."""
        key = _norm(merchant)
        for e in self.c.data["expected_charges"]:
            if e["key"] == key:
                e.update(merchant=merchant, amount=float(amount), cadence=cadence,
                         authorized_recurring=bool(authorized_recurring),
                         note=note or e.get("note", ""), active=True,
                         updated=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
                self.c._save()
                return e
        entry = {
            "key": key, "merchant": merchant, "amount": float(amount),
            "cadence": cadence, "authorized_recurring": bool(authorized_recurring),
            "note": note, "active": True, "cancelled_on": None,
            "updated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        self.c.data["expected_charges"].append(entry)
        self.c._save()
        return entry

    def mark_cancelled(self, merchant: str, on: str = "") -> dict:
        """The user cancelled. From here, any further charge is theft of a
        kind that usually goes unnoticed."""
        key = _norm(merchant)
        when = on or time.strftime("%Y-%m-%d")
        hits = 0
        for e in self.c.data["expected_charges"]:
            if e["key"] == key:
                e["active"] = False
                e["cancelled_on"] = when
                hits += 1
        if not hits:
            # Never registered, but the user says they cancelled it — record it
            # anyway, so a charge that shows up later is caught as theft rather
            # than shrugged off as merely unfamiliar.
            self.c.data["expected_charges"].append({
                "key": key, "merchant": merchant, "amount": 0.0,
                "cadence": "unknown", "authorized_recurring": False,
                "note": "cancelled by the user", "active": False,
                "cancelled_on": when, "updated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            })
            hits = 1
        self.c._save()
        return {"merchant": merchant, "marked_cancelled": hits, "cancelled_on": when,
                "note": "Any charge after this date is unauthorized. Watch for it."}

    def expected_charges(self) -> list[dict]:
        return list(self.c.data.get("expected_charges", []))

    # ---------------------------------------------------------------- check
    def check_charge(self, merchant: str, amount: float, date: str = "",
                     record: bool = True) -> dict:
        """Hold one charge up against what the user actually agreed to."""
        key = _norm(merchant)
        amount = float(amount)
        date = date or time.strftime("%Y-%m-%d")
        match = next((e for e in self.c.data["expected_charges"] if e["key"] == key), None)

        recent_same = [
            c for c in self.c.data.get("charges_seen", [])
            if c["key"] == key and abs(c["amount"] - amount) < 0.01
            and c.get("date", "")[:7] == date[:7]
        ]

        if match and not match["active"]:
            verdict, severity = "charged_after_cancel", 1.0
            detail = (f"You cancelled {match['merchant']} on "
                      f"{match.get('cancelled_on') or 'an earlier date'} and they charged "
                      f"${amount:.2f} anyway on {date}.")
            recover = amount
        elif match is None:
            verdict, severity = "unexpected_merchant", 0.85
            detail = (f"${amount:.2f} to '{merchant}' on {date}, and nothing in your "
                      "register says you agreed to this. Do you recognize it?")
            recover = amount
        elif recent_same:
            verdict, severity = "duplicate", 0.9
            detail = (f"{match['merchant']} charged ${amount:.2f} more than once in "
                      f"{date[:7]}. The cadence on file is {match['cadence']}.")
            recover = amount
        elif amount > match["amount"] + 0.01:
            delta = amount - match["amount"]
            verdict, severity = "amount_increased", min(1.0, 0.4 + delta / max(match["amount"], 1) )
            detail = (f"{match['merchant']} went from ${match['amount']:.2f} to "
                      f"${amount:.2f} — up ${delta:.2f} "
                      f"({delta / max(match['amount'], 0.01) * 100:.0f}%), {match['cadence']}. "
                      f"That's ${delta * {'monthly': 12, 'weekly': 52, 'quarterly': 4}.get(match['cadence'], 1):.2f} a year.")
            recover = delta
        elif amount < match["amount"] - 0.01:
            verdict, severity, recover = "amount_decreased", 0.1, 0.0
            detail = f"{match['merchant']} charged less than expected. Nothing to do."
        else:
            verdict, severity, recover = "expected", 0.0, 0.0
            detail = f"{match['merchant']} ${amount:.2f} — as agreed. Quiet."

        if record:
            self.c.data.setdefault("charges_seen", []).append({
                "key": key, "merchant": merchant, "amount": amount,
                "date": date, "verdict": verdict,
            })
            self.c._save()

        return {
            "merchant": merchant, "amount": amount, "date": date,
            "cadence": (match or {}).get("cadence", "unknown"),
            "verdict": verdict, "severity": round(severity, 2),
            "what_happened": detail,
            "recoverable": round(recover, 2),
            "authorized_on_file": bool(match and match["active"]),
            "action": (
                "Nothing to do." if verdict in ("expected", "amount_decreased") else
                "Tell the user in plain words, offer to build a dispute_pack, and "
                "score it with record_opportunity (reduces_risk=True). Contacting "
                "the merchant or the bank is an Act: authorize_action first."
            ),
        }

    def review_statement(self, charges: list[dict]) -> dict:
        """Run a whole statement through at once. This is the moment people
        find the money that's been leaking for years."""
        results = [
            self.check_charge(
                c.get("merchant", ""), float(c.get("amount", 0)), c.get("date", ""))
            for c in charges
        ]
        flagged = [r for r in results if r["verdict"] not in ("expected", "amount_decreased")]
        total = round(sum(r["recoverable"] for r in flagged), 2)
        per_year = {"monthly": 12, "weekly": 52, "quarterly": 4, "yearly": 1, "annual": 1}
        return {
            "checked": len(results),
            "flagged": flagged,
            "quiet": len(results) - len(flagged),
            "recoverable_total": total,
            "annualized_estimate": round(
                sum(r["recoverable"] * (per_year.get(r.get("cadence", ""), 1)
                                        if r["verdict"] == "amount_increased" else 1)
                    for r in flagged), 2),
            "summary": (
                f"{len(flagged)} of {len(results)} charges need your attention "
                f"(${total:.2f} at stake)." if flagged else
                "Everything on this statement matches what you agreed to."
            ),
        }

    # -------------------------------------------------------------- dispute
    def dispute_pack(self, merchant: str) -> dict:
        """Everything needed to get the money back, assembled — so the user
        isn't the one digging through statements at 11pm."""
        key = _norm(merchant)
        agreed = next((e for e in self.c.data["expected_charges"] if e["key"] == key), None)
        history = [c for c in self.c.data.get("charges_seen", []) if c["key"] == key]
        disputed = [c for c in history
                    if c["verdict"] not in ("expected", "amount_decreased")]
        total = round(sum(c["amount"] for c in disputed), 2)
        return {
            "merchant": merchant,
            "what_was_authorized": agreed or "nothing on file — no agreement recorded",
            "charges_in_dispute": disputed,
            "amount_in_dispute": total,
            "full_history": history,
            "how_to_use": (
                "Call draft_guidance('dispute an unauthorized charge', merchant) and "
                "write the demand in the user's voice: state the amount and date, say "
                "plainly that recurring billing was not authorized (or was cancelled "
                "on the date shown), request a full refund and written confirmation "
                "that billing has stopped, and give a deadline. Show it to the user. "
                "Sending is an Act — authorize_action on 'correspondence', then "
                "log_action. If the merchant refuses, the next step is the card "
                "issuer's chargeback process, which has its own time limit — tell "
                "them that before it expires."
            ),
        }
