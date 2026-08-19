"""
JEFFEREY the Representative — correspondence & paperwork
=======================================================

Priority 04 in practice. This is the module that lets Jefferey act as the
user's representative on the two things that eat ordinary people alive:

  1. **Correspondence** — mail that wants money, time, or a decision.
     Jefferey triages it against the user's OWN priorities, flags the
     predatory patterns aimed at the elderly and overwhelmed, and drafts
     replies in the user's voice — never sending without the Act gate.
  2. **Paperwork** — HTML forms and PDF forms. Jefferey fills what he
     knows from the user's own profile, names exactly what he does NOT
     know, and refuses to guess.

Design rules, straight from the Directive Pack:
- The profile lives in the user's own conscience store. Nowhere else.
- Sensitive identifiers (SIN/SSN, card numbers, passwords) are NEVER
  auto-filled — they are named as "needs you", every time, by design.
- Nothing is sent, submitted, or signed without `authorize_action`.
- Jefferey never invents a value to make a form look complete.

Jefferey does not carry his own mail connection: he rides whatever the host
engine already has (Gmail/Outlook connectors in Claude or ChatGPT). The host
supplies the pipes; this module supplies the representation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import vault

# ------------------------------------------------------------------ profile
# Field aliases: the labels real forms actually use, mapped to our keys.
FIELD_ALIASES: dict[str, list[str]] = {
    "full_name":      ["full name", "name", "your name", "applicant name", "legal name"],
    "first_name":     ["first name", "given name", "forename", "first"],
    "last_name":      ["last name", "surname", "family name", "last"],
    "email":          ["email", "e-mail", "email address"],
    "phone":          ["phone", "telephone", "phone number", "mobile", "cell"],
    "address_line1":  ["address", "street address", "address line 1", "address 1"],
    "address_line2":  ["address line 2", "address 2", "apt", "unit", "suite"],
    "city":           ["city", "town", "municipality"],
    "province":       ["province", "state", "region", "county"],
    "postal_code":    ["postal code", "postcode", "zip", "zip code"],
    "country":        ["country", "nation"],
    "date_of_birth":  ["date of birth", "dob", "birth date", "birthdate"],
    "occupation":     ["occupation", "job title", "profession"],
    "employer":       ["employer", "company", "organization"],
    "website":        ["website", "url", "web site"],
}

# Never auto-filled. Not "ask nicely" — refused, every time.
SENSITIVE_PATTERNS = [
    "sin", "social insurance", "ssn", "social security", "tax id",
    "card number", "credit card", "cvv", "cvc", "security code",
    "account number", "routing", "iban", "sort code",
    "password", "passcode", "pin", "secret", "security answer",
    "signature", "sign here",
]

# ------------------------------------------------------------------ triage
# Patterns that prey on people. Each is (regex, weight, plain-words reason).
_SCAM_SIGNALS: list[tuple[str, float, str]] = [
    (r"\b(?:urgent|immediately|within 24 hours|final notice|act now|last warning)\b", 0.20,
     "manufactured urgency — real institutions give you time"),
    (r"\b(?:suspend|suspended|terminate|deactivat|locked|closed) (?:your )?account\b", 0.20,
     "threatens your account to rush you"),
    (r"\b(?:gift card|itunes card|google play card|steam card)\b", 0.35,
     "asks for gift cards — no legitimate business is ever paid this way"),
    (r"\b(?:wire transfer|western union|moneygram|bitcoin|crypto|e-?transfer)\b", 0.30,
     "asks for an irreversible payment method"),
    (r"\b(?:verify|confirm|update) (?:your )?(?:identity|account|password|payment|billing)\b", 0.25,
     "asks you to 'verify' details — the classic phishing move"),
    (r"\b(?:click|tap) (?:here|this link|below)\b", 0.10,
     "pushes you to a link instead of letting you navigate yourself"),
    (r"\b(?:warrant|arrest|legal action|lawsuit|police|deport)\b", 0.30,
     "threatens legal or police consequences — a fear tactic"),
    (r"\b(?:you have won|prize|lottery|inheritance|beneficiary|unclaimed funds)\b", 0.30,
     "promises unexpected money"),
    (r"\b(?:refund|overpayment|rebate) (?:is )?(?:pending|available|owed)\b", 0.20,
     "dangles a refund to get your banking details"),
    (r"\b(?:do not tell|keep this confidential|between us)\b", 0.30,
     "asks you to keep it secret — isolation is how people get taken"),
    (r"\b(?:remote access|anydesk|teamviewer|install (?:this|our) (?:app|software))\b", 0.35,
     "wants control of your device"),
    (r"\b(?:microsoft|apple|amazon|revenue agency|cra|irs|bank) (?:support|security|team)\b", 0.15,
     "impersonates a well-known institution"),
]

# Charges that quietly grow. Not fraud — just the stuff nobody reads.
_BILLING_SIGNALS: list[tuple[str, float, str]] = [
    (r"\b(?:auto-?renew|automatically renew|renews on|will be charged)\b", 0.25,
     "auto-renewal — money leaves without another decision from you"),
    (r"\b(?:price|rate|fee|subscription) (?:increase|change|adjustment|will (?:go up|rise))\b", 0.30,
     "a price increase buried in the message"),
    (r"\b(?:free trial|trial period) (?:ends|ending|expires)\b", 0.25,
     "trial converting to a paid plan"),
    (r"\b(?:cancel(?:lation)? fee|early termination|restocking fee)\b", 0.20,
     "a penalty clause"),
    (r"\b(?:promotional|introductory) (?:rate|price|period) (?:ends|expires)\b", 0.25,
     "an introductory rate about to end"),
]

_MONEY = re.compile(r"[$£€]\s?\d[\d,]*(?:\.\d{2})?|\b\d[\d,]*(?:\.\d{2})?\s?(?:dollars|usd|cad|eur|gbp)\b", re.I)
_DEADLINE = re.compile(
    r"\b(?:by|before|due|expires?|deadline)\s+(?:\w+\s+\d{1,2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{1,2}\s+\w+)", re.I)


class Representative:
    """Correspondence and paperwork, done in the user's interest.

    Holds no state of its own: the profile lives in the Conscience store,
    which the user owns.
    """

    def __init__(self, conscience):
        self.c = conscience
        self.c.data.setdefault("profile", {})

    # -------------------------------------------------------------- profile
    def set_profile_field(self, field: str, value: str) -> dict:
        """Store one identity detail Jefferey may use to fill forms."""
        key = self._normalize_field(field) or field.lower().strip().replace(" ", "_")
        if self._is_sensitive(field) or self._is_sensitive(key):
            return {
                "stored": False,
                "field": key,
                "reason": (
                    "Refused by design: identifiers like SIN/SSN, card numbers, "
                    "PINs and passwords are never stored or auto-filled. Jefferey "
                    "will always hand these fields back to you to enter yourself."
                ),
            }
        self.c.data["profile"][key] = value.strip()
        self.c._save()
        return {"stored": True, "field": key, "value": value.strip()}

    def get_profile(self) -> dict:
        """Everything Jefferey can put on a form for you. You own all of it."""
        return dict(self.c.data.get("profile", {}))

    def forget_profile_field(self, field: str) -> dict:
        key = self._normalize_field(field) or field.lower().strip().replace(" ", "_")
        removed = self.c.data.get("profile", {}).pop(key, None)
        self.c._save()
        return {"removed": key if removed is not None else None}

    # ---------------------------------------------------------------- forms
    def fill_form(self, fields: list[str]) -> dict:
        """Given the labels on a form (HTML, PDF, or paper), return what
        Jefferey can fill from the user's own profile — and, just as
        importantly, what he cannot.

        He never guesses. A field he doesn't know is named, not invented.
        """
        profile = self.c.data.get("profile", {})
        filled: dict[str, str] = {}
        needs_you: list[dict] = []
        vault_names = vault.names()
        for raw in fields:
            label = str(raw)
            if self._is_sensitive(label):
                slot = self._vault_slot(label, vault_names)
                if slot:
                    # He completes it WITHOUT seeing it: the token is resolved
                    # from the platform keychain at write time, locally.
                    filled[label] = f"vault:{slot}"
                else:
                    needs_you.append({
                        "field": label,
                        "why": "sensitive — you enter this yourself, always",
                        "or": (
                            "store it once in your platform keychain "
                            f"(python connector/vault.py set {self._suggest_slot(label)}) "
                            "and Jefferey can fill it by reference without ever seeing it"
                        ),
                    })
                continue
            key = self._normalize_field(label)
            if key and key in profile:
                filled[label] = profile[key]
            elif key == "full_name" and profile.get("first_name") and profile.get("last_name"):
                filled[label] = f"{profile['first_name']} {profile['last_name']}"
            else:
                needs_you.append({"field": label, "why": "not in your profile yet"})
        return {
            "filled": filled,
            "needs_you": needs_you,
            "coverage": f"{len(filled)}/{len(fields)}",
            "vault_available": vault_names,
            "rule": (
                "Present the filled values for review, ask the user only for "
                "'needs_you', and never submit without authorize_action on the "
                "'paperwork' category. Values shown as 'vault:<name>' are "
                "references — you do not know what they are and must never "
                "ask. Local code fills them at write time."
            ),
        }

    def pdf_form_fields(self, pdf_path: str) -> dict:
        """Read the fillable field names out of a PDF form."""
        try:
            import pypdf
        except ImportError:
            return {"error": "pypdf is not installed — run: pip install pypdf"}
        p = Path(pdf_path).expanduser()
        if not p.exists():
            return {"error": f"no such file: {p}"}
        try:
            reader = pypdf.PdfReader(str(p))
            fields = reader.get_fields() or {}
        except Exception as e:
            return {"error": f"could not read PDF: {e}"}
        return {
            "path": str(p),
            "fields": sorted(fields.keys()),
            "count": len(fields),
            "note": "Pass these labels to fill_form to see what Jefferey can complete.",
        }

    def fill_pdf(self, pdf_path: str, values: dict[str, str], out_path: str = "") -> dict:
        """Write values into a PDF form and save a NEW file. The original is
        never modified — Jefferey does not overwrite the user's documents."""
        try:
            import pypdf
        except ImportError:
            return {"error": "pypdf is not installed — run: pip install pypdf"}
        p = Path(pdf_path).expanduser()
        if not p.exists():
            return {"error": f"no such file: {p}"}
        # A sensitive field may be filled ONLY through a vault reference —
        # never with a literal value handed over by the model.
        blocked = [
            k for k, v in values.items()
            if self._is_sensitive(k) and not vault.is_reference(v)
        ]
        if blocked:
            return {
                "error": "refused",
                "fields": blocked,
                "reason": (
                    "Sensitive fields are never filled from a literal value. "
                    "Store the secret in the platform keychain once "
                    "(python connector/vault.py set <name>) and pass "
                    "'vault:<name>' instead — it is resolved locally and never "
                    "seen by the AI."
                ),
            }

        # Resolve references here, on the user's machine, at write time.
        resolved, from_vault, missing = {}, [], []
        for k, v in values.items():
            if vault.is_reference(v):
                try:
                    secret = vault.resolve(v)
                except vault.VaultUnavailable as e:
                    return {"error": "vault unavailable", "reason": str(e)}
                if secret is None:
                    missing.append(str(v))
                    continue
                resolved[k] = secret
                from_vault.append(k)
            else:
                resolved[k] = v
        if missing:
            return {
                "error": "unknown vault reference",
                "references": missing,
                "available": vault.names(),
            }
        values = resolved
        out = Path(out_path).expanduser() if out_path else p.with_name(p.stem + "_filled.pdf")
        try:
            reader = pypdf.PdfReader(str(p))
            writer = pypdf.PdfWriter()
            writer.append(reader)
            for page in writer.pages:
                writer.update_page_form_field_values(page, values)
            with open(out, "wb") as fh:
                writer.write(fh)
        except Exception as e:
            return {"error": f"could not write PDF: {e}"}
        return {
            "written": str(out),
            "fields_set": sorted(values.keys()),
            "filled_from_vault": sorted(from_vault),
            "original_untouched": str(p),
            "rule": (
                "Show the user the filled copy for review before anything is "
                "submitted or signed. Vault-filled fields were written by local "
                "code — you never saw those values and must not ask for them."
            ),
        }

    # -------------------------------------------------------------- triage
    def triage_message(self, sender: str, subject: str, body: str) -> dict:
        """Read a message the way a good friend would: what does it want,
        does it matter by THIS person's priorities, and is anyone trying
        to take advantage of them?
        """
        text = f"{subject}\n{body}"
        low = text.lower()

        scam_flags, scam_score = [], 0.0
        for pattern, weight, reason in _SCAM_SIGNALS:
            if re.search(pattern, low):
                scam_flags.append(reason)
                scam_score += weight
        billing_flags, billing_score = [], 0.0
        for pattern, weight, reason in _BILLING_SIGNALS:
            if re.search(pattern, low):
                billing_flags.append(reason)
                billing_score += weight

        scam_score = round(min(1.0, scam_score), 2)
        billing_score = round(min(1.0, billing_score), 2)
        money = _MONEY.findall(text)[:5]
        deadlines = _DEADLINE.findall(text)[:5]

        if scam_score >= 0.5:
            verdict = "likely_scam"
            advice = ("Treat as hostile. Do not click, call the number in the message, "
                      "or send anything. If it claims to be a company the user deals "
                      "with, reach them through a number the USER already has.")
        elif scam_score >= 0.25:
            verdict = "suspicious"
            advice = ("Warn the user plainly, name the tactics you spotted, and verify "
                      "through an independent channel before anything happens.")
        elif billing_score >= 0.25:
            verdict = "money_watch"
            advice = ("Not fraud, but it costs money. Show the amount and the date, and "
                      "offer to act before it charges — within permissions.")
        elif money or deadlines:
            verdict = "needs_decision"
            advice = "Real and actionable. Recommend, with the reasoning in their values."
        else:
            verdict = "routine"
            advice = "Handle quietly. Do not interrupt the user for this."

        # Does it touch anything they've told Jefferey matters?
        basis = self.c.explain_basis(subject or body[:80])
        return {
            "sender": sender,
            "subject": subject,
            "verdict": verdict,
            "scam_score": scam_score,
            "scam_flags": scam_flags,
            "billing_score": billing_score,
            "billing_flags": billing_flags,
            "money_mentioned": money,
            "deadlines": deadlines,
            "relevant_priorities": basis.get("priorities", []),
            "advice": advice,
            "rule": (
                "Never reply, click, pay, or unsubscribe on the user's behalf without "
                "authorize_action. Protecting them comes before being helpful."
            ),
        }

    def draft_guidance(self, purpose: str, recipient: str = "") -> dict:
        """What Jefferey must know before writing anything in the user's name:
        their voice, their values on this subject, and the hard limits."""
        basis = self.c.explain_basis(purpose)
        profile = self.c.data.get("profile", {})
        signer = profile.get("full_name") or (
            f"{profile.get('first_name','')} {profile.get('last_name','')}".strip() or None)
        return {
            "purpose": purpose,
            "recipient": recipient,
            "write_as": signer or "the user (no name in profile yet — ask before signing)",
            "their_priorities_here": basis.get("priorities", []),
            "their_facts_here": basis.get("facts", []),
            "voice": (
                "Calm, articulate, warm, plain-spoken. Their language, their rhythm. "
                "Short sentences. No corporate padding, no false apology, no threats."
            ),
            "rules": [
                "Write in the user's interest, never to please the recipient.",
                "State what they want clearly and early; ask for one specific thing.",
                "Never invent facts, amounts, dates, or commitments.",
                "Never disclose more personal information than the purpose requires.",
                "Show the draft to the user. Sending requires authorize_action on "
                "the 'correspondence' category — and it is logged.",
            ],
        }

    def vault_status(self) -> dict:
        """Where secrets live and which exist — names only, never values."""
        return vault.status()

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _suggest_slot(label: str) -> str:
        low = re.sub(r"[^a-z0-9]+", "_", str(label).lower()).strip("_")
        for short, pats in [
            ("sin", ("sin", "social_insurance")), ("ssn", ("ssn", "social_security")),
            ("card_number", ("card",)), ("pin", ("pin",)),
            ("password", ("password", "passcode")),
        ]:
            if any(p in low for p in pats):
                return short
        return low[:40] or "secret"

    @classmethod
    def _vault_slot(cls, label: str, available: list[str]) -> str | None:
        """Match a sensitive form field to a stored secret's NAME."""
        if not available:
            return None
        low = re.sub(r"[^a-z0-9]+", "_", str(label).lower()).strip("_")
        suggested = cls._suggest_slot(label)
        if suggested in available:
            return suggested
        for name in available:
            if name in low or low in name:
                return name
        return None

    @staticmethod
    def _is_sensitive(label: str) -> bool:
        low = str(label).lower()
        return any(pat in low for pat in SENSITIVE_PATTERNS)

    @staticmethod
    def _normalize_field(label: str) -> str | None:
        low = re.sub(r"[^a-z0-9 ]+", " ", str(label).lower()).strip()
        low = re.sub(r"\s+", " ", low)
        if low in FIELD_ALIASES:
            return low
        for key, aliases in FIELD_ALIASES.items():
            if low == key.replace("_", " ") or low in aliases:
                return key
        for key, aliases in FIELD_ALIASES.items():   # looser containment pass
            for alias in aliases:
                if alias in low:
                    return key
        return None
