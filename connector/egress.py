"""
THE EGRESS DOOR — the one way out of the house
==============================================

JEFFEREY is the only half of the system that ever talks to a rented engine.
Self-Cloud never leaves the house at all. So the *whole* privacy claim of the
product comes down to one question: what, exactly, did JEFFEREY hand to the
cloud, when, and why? Before this module the honest answer was "whatever the
tools returned." Now it is "read the log."

Three rules, and they are the whole of this file:

1. **One door.** Every byte that leaves this process for a rented engine
   passes through `release()` (a tool result) or `request()` (the owner's
   own terminal sending a turn). The MCP and HTTP surfaces do not call the
   tool functions directly; they call them *through* the door (`door(...)`),
   so a tool added tomorrow without an entry here releases **nothing**.

2. **Allowlist, never redaction.** `RELEASE` names, per tool, the fields
   that may go out. A field not named is withheld. A tool not named releases
   nothing. This fails *closed*: forgetting an entry costs a feature, never a
   secret. (Redaction fails open: forgetting a pattern costs a secret.)
   On top of the allowlist a hard scan looks for anything shaped like a
   secret — a card number, a SIN, a password or PIN, a house code, a bank,
   health-card, licence or passport number, an API key — in English or
   French, however it is written. Going out, such words are replaced by
   "[hidden: looks like …]" and the answer says plainly that part of it
   stayed home; coming in, a tool that would keep them refuses. The scan is
   a backstop: the control is the vault, where secrets are kept by name.

3. **Nothing leaves unlogged.** Every send is written, word for word, to an
   append-only log beside the conscience — on the drive when there is one —
   *before* it goes. If the log cannot be written, the send does not happen.
   `python connector/egress.py` reads it back in plain words: who got what.

The owner can also shut the door: `python connector/egress.py shut` (or a
file named `door-shut` beside the conscience, or JEFFEREY_OFFLINE=1). Shut
means no tool runs at all — nothing is read, written or released — until
they open it again; a switch that cannot be reached counts as shut. This is JEFFEREY's
own switch; Self-Cloud's offline switch is theirs and stays theirs.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import fcntl  # POSIX only
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

import home
from version import __version__

# --------------------------------------------------------------- the allowlist
# Per tool: the top-level fields that may leave. For a tool that returns a
# list, these are the fields of each item. Anything not named is withheld.
TEXT = "*text*"      # the tool returns a bare string that may leave whole
ANY = "*any*"        # keys are the owner's own field names (get_profile) —
                     # no top-level filter, the secret scan still runs

# Shapes JEFFEREY itself produces — guidance strings and refusals, never owner
# data — allowed on every tool so a refusal can be reported as a result.
# kept_home: the door's own plain note when part of an answer looked like a
# secret and was hidden (see kept_home_note).
COMMON = frozenset({"error", "note", "rule", "reason", "refused", "tool",
                    "tell_the_user", "kept_home", "trimmed"})

# Tools that only READ what the engine hands them: they analyse it, answer,
# and keep none of it (I-14). A secret-shaped string handed to one of these
# is not refused — a scam that quotes a card number or "your password is
# about to expire" is exactly what must still be checked — it is hidden in
# the log and in the answer instead. Every other tool keeps what it is given
# (or might), so a secret handed to it is refused before it runs: deny by
# default, so a tool added tomorrow refuses until it is named here.
READS_ONLY = frozenset({
    "triage_message", "draft_guidance", "score_opportunity", "explain_basis",
    "priorities_for", "check_disclosure", "guidance_for", "fill_form",
    "pdf_form_fields", "tell_story", "check_draft",
    # the first step of a removal keeps nothing of what was asked: the log
    # keeps only a fingerprint (FINGERPRINT_ARGS), the pending code only ids
    "forget", "forget_life", "close_goal", "conscience_exclude", "remove_rule",
    "forget_profile_field",
})

# What every tool that removes or closes something returns (forgetting.py):
# step one shows what would go and a one-time code; step two says what went,
# until when it can be put back, and what copies still exist.
FORGET = frozenset({"step", "would_remove", "would_change", "count", "kinds",
                    "confirm", "needs_owner", "expires", "how_to_finish",
                    "also_mentioned", "unknown_ids", "removed_items",
                    "changed_items", "kept_until", "put_back", "still_held"})

# What an engine asks to forget names the very thing being forgotten — even
# when nothing matches ("forget the affair with Maria"). The log keeps a
# sha256 fingerprint of these arguments, never the words.
FINGERPRINT_ARGS: dict[str, tuple[str, ...]] = {
    "forget": ("contains",), "forget_life": ("contains",),
    "close_goal": ("contains",), "resolve_opportunity": ("contains", "outcome"),
    "conscience_exclude": ("contains",), "remove_rule": ("rule_id_or_text",),
    "forget_profile_field": ("field",),
}

# What a value carries out (I-48): the evidence for and against, whether he
# stated it (locked against inference), whether an AI wrote it unconfirmed,
# and any question it raises for him.
_PRIORITY = frozenset({"id", "context", "higher", "lower", "confidence", "evidence",
                       "updated", "for", "against", "stated", "locked", "unconfirmed",
                       "question_for_owner", "proposed_change", "held_since_before"})

RELEASE: dict[str, frozenset[str]] = {
    # identity
    "get_directives": frozenset({TEXT, "directives"}),
    # store_path is deliberately absent: the layout of the owner's drive is
    # not the engine's business.
    # notices: JEFFEREY's own plain words about the store (a recovery, a
    # restore, an edit by hand) — the owner must hear them, so they go out.
    # A page at a time, private facts counted not shown (I-11, I-41).
    "get_conscience": frozenset({"owner", "priorities", "facts", "active_goals",
                                 "corrections_learned_from", "notices",
                                 "more_priorities", "more_facts", "how_to_see_more",
                                 "held_back", "waiting_for_owner", "more_goals",
                                 "more_notices"}),
    # values and how they are learned: for and against counted apart, a
    # stated value locked against inference, a reversal logged (I-48)
    "record_correction": frozenset(_PRIORITY | {"flipped", "already_counted"}),
    "set_priority": frozenset(_PRIORITY | {"reversed", "changed"}),
    # facts only reach a key that may read facts (conscience.explain_basis);
    # whole words, each with why it matched (I-28)
    "explain_basis": frozenset({"topic", "priorities", "facts", "more_facts",
                                "how_to_see_more", "held_back"}),
    "priorities_for": frozenset(_PRIORITY | {"match_reason"}),
    # what his rules let this recipient be told (I-24)
    "draft_guidance": frozenset({"purpose", "recipient", "write_as",
                                 "their_priorities_here", "their_facts_here",
                                 "voice", "voice_is", "rules", "disclosure",
                                 "speak_of_them_this_way", "meeting_safety"}),
    "check_draft": frozenset({"ok", "audience", "problems", "advice"}),
    # facts, profile, rules, the daily brief
    "remember_fact": frozenset({"id", "fact", "category", "added", "visibility",
                                "sensitivity", "status"}),
    "forget": FORGET | {"removed_facts"},
    "get_profile": frozenset({ANY}),
    # a change to who the owner is comes back as a question first (I-30)
    "set_profile_field": FORGET | {"stored", "field", "value"},
    "forget_profile_field": FORGET | {"removed"},
    # from_your_vault: "your SIN will go into box X", read to the owner first
    # owner_is / sides: which side of a sale he was taken to be (selling-30)
    "fill_form": frozenset({"filled", "needs_you", "coverage", "vault_available",
                            "from_your_vault", "owner_is", "sides", "owner_is_can_be"}),
    # fill_pdf: the filled copy's location, never the values written into it;
    # which secret went into which box by NAME (I-02), what was taken out of
    # the copy (I-31) and which boxes were signed under an approval (I-57)
    "fill_pdf": frozenset({"written", "saved_in", "fields_set", "filled_from_vault",
                           "original_untouched", "fields", "references", "available",
                           "secrets_used", "not_on_this_form", "removed_from_copy",
                           "signed", "wrong_boxes", "owner_is_can_be", "needs_you"}),
    # field names are the PDF author's words: data, never instructions (I-31)
    "pdf_form_fields": frozenset({"path", "fields", "count", "field_names_are",
                                  "described", "sensitive", "for_someone_else",
                                  "signing", "suspicious", "warning", "owner_is",
                                  "sides", "owner_is_can_be", "needs_you"}),
    # who wrote each line and through which door (I-45); an approval's id is
    # given only to the connection that asked for it, never in the log view
    "action_log": frozenset({"category", "description", "amount", "currency",
                             "outcome", "added", "ts", "by", "surface", "source",
                             "approved", "approved_for", "description_by", "note",
                             "id", "held_back"}),
    "conscience_include": frozenset({"id", "ref", "added"}),
    "conscience_exclude": FORGET | {"excluded"},
    "set_rule": frozenset({"id", "kind", "tags", "audience", "allow",
                           "instruction", "added", "holds_for"}),
    "remove_rule": FORGET | {"removed"},
    "list_rules": frozenset({"id", "kind", "tags", "audience", "allow",
                             "instruction", "added", "holds_for"}),
    "daily_brief": frozenset({"orb", "active_goals", "opportunities",
                              "recent_actions", "recent_observations",
                              "corrections_learned_from", "notices",
                              "held_back", "waiting_for_owner", "more_goals",
                              "more_notices", "charges_waiting_for_owner"}),
    "orb_state": frozenset({"mood"}),
    # goals and the opportunity engine
    "add_goal": frozenset({"id", "goal", "added", "active"}),
    "close_goal": FORGET | {"closed"},
    "log_observation": frozenset({"id", "note", "category", "added", "ts"}),
    # who saved it, whether it may interrupt, and any marks of a scam (I-40)
    "record_opportunity": frozenset({"id", "what", "value_estimate", "aligns_with",
                                     "advances_goal", "reduces_risk", "urgency",
                                     "score", "status", "resolved", "added", "ts",
                                     "source", "surface", "may_interrupt",
                                     "scam_signals", "warning"}),
    "score_opportunity": frozenset({"what", "value_estimate", "aligns_with",
                                    "advances_goal", "reduces_risk", "urgency",
                                    "score", "status", "scam_signals"}),
    "resolve_opportunity": FORGET | {"resolved"},
    # acting on their behalf. Raising a permission is not a tool on any
    # surface (the owner types /permit himself), so it releases nothing.
    "authorize_action": frozenset({"allowed", "level", "cap", "period", "currency",
                                   "floor", "spent_this_period", "left_this_period",
                                   "authorization_id", "expires"}),
    "log_action": frozenset({"category", "description", "amount", "outcome",
                             "added", "ts", "authorization_id", "approved", "by",
                             "surface", "source", "note", "approved_for"}),
    # money
    # From an AI an addition to the agreed list waits for the owner: 'status'
    # says so and 'proposal' names it (I-47). The matcher says which entry a
    # statement line is, or asks "did you mean …" (I-36); a charge seen again
    # is 'already_on_file', never a new one (I-37); refunds come off (I-39).
    "expect_charge": frozenset({"key", "merchant", "amount", "cadence",
                                "authorized_recurring", "active",
                                "cancelled_on", "updated", "status", "proposal"}),
    # a later date asked for by an AI waits for the owner (verify I-47)
    "mark_cancelled": frozenset({"merchant", "marked_cancelled", "cancelled_on",
                                 "matched_to", "possible_match", "status", "proposal"}),
    "check_charge": frozenset({"merchant", "amount", "date", "cadence", "verdict",
                               "severity", "what_happened", "recoverable",
                               "authorized_on_file", "action", "matched_to",
                               "possible_match", "already_on_file", "kept"}),
    "review_statement": frozenset({"checked", "flagged", "quiet",
                                   "recoverable_total", "annualized_estimate",
                                   "summary", "attention", "new_merchants", "refunds",
                                   "already_on_file", "recorded", "errors"}),
    "expected_charges": frozenset({"key", "merchant", "amount", "cadence",
                                   "authorized_recurring", "active",
                                   "cancelled_on", "updated", "status", "proposal",
                                   "cancelled_on_said", "amount_known"}),
    "dispute_pack": frozenset({"merchant", "what_was_authorized",
                               "charges_in_dispute", "amount_in_dispute",
                               "full_history", "how_to_use", "refunds_received",
                               "chargeback_deadline_estimate"}),
    # what waits for the owner, and withdrawing it; confirming is not a tool
    "charge_changes_waiting": frozenset({"id", "what", "kind", "asked_by", "asked_on",
                                         "why"}),
    "decline_charge_change": frozenset({"merchant", "status"}),
    "name_for_charge": frozenset({"merchant", "status", "proposal"}),
    # the representative reading their mail
    # what it touches and who sent it, in plain words (I-13)
    "triage_message": frozenset({"sender", "subject", "verdict", "interrupt",
                                 "safety_flags", "scam_score",
                                 "scam_flags", "touches", "sender_is",
                                 "billing_score", "billing_flags",
                                 "money_mentioned", "deadlines",
                                 "relevant_priorities", "advice"}),
    # the life layer
    # a person is never overwritten by another of the same name (I-27)
    "add_person": frozenset({"id", "name", "relationship", "notes",
                             "important_dates", "visibility", "added", "updated",
                             "matched_existing", "changed", "possible_duplicate_of"}),
    "update_person": frozenset({"id", "name", "relationship", "notes",
                                "important_dates", "visibility", "added", "updated",
                                "changed"}),
    # an AI's write is private, and verbatim only when it is his words (I-25, I-26)
    "add_memory": frozenset({"id", "text", "when", "people", "tags", "visibility",
                             "added", "photos", "verbatim", "status",
                             "requested_visibility"}),
    "add_media": frozenset({"id", "path", "caption", "when", "people", "visibility",
                            "reachable", "added", "requested_visibility"}),
    "set_visibility": frozenset({"changed", "not_changed", "needs_owner"}),
    # his rules applied, legacy sealed, a page at a time (I-10, I-41)
    "who_am_i": frozenset({"people_who_matter", "moments",
                           "pictures_and_recordings", "what_they_value", "facts",
                           "depth", "held_back", "legacy", "more", "how_to_see_more"}),
    "tell_story": frozenset({"theme", "visible_at", "moments", "pictures",
                             "people", "how_to_tell_it", "held_back", "legacy", "more",
                             "how_to_see_more"}),
    "story_gaps": frozenset({"gaps"}),
    "forget_life": FORGET | {"memories_removed", "media_removed",
                             "people_removed", "names_taken_off"},
    # the interview
    "next_question": frozenset({"question", "id", "depth", "domain",
                                "what_it_teaches_you", "trust", "how_to_ask"}),
    "record_answer": frozenset({"recorded", "question", "kept_as", "next"}),
    "interview_progress": frozenset({"answered", "declined",
                                     "remaining_at_this_depth", "locked_deeper",
                                     "by_domain", "trust"}),
    # the album
    # a count, a place and dates — never the photographs' fingerprints (I-15)
    "next_story_prompt": frozenset({"moment_id", "label", "photos", "from", "to",
                                    "show_on_the_wall", "ask"}),
    "record_story": frozenset({"kept", "moment", "memory", "pinned_to_photos",
                               "one_follow_up"}),
    "decline_story": frozenset({"declined", "moment_id"}),
    "skip_story": frozenset({"skipped", "moment_id"}),
    "story_progress": frozenset({"indexed", "untold", "told", "declined", "stories"}),
    # their own rules about who may hear what
    "check_disclosure": frozenset({"allowed", "audience", "tags"}),
    "guidance_for": frozenset({"tags", "audience", "react_this_way",
                               "disclosure", "speak_of_them_this_way"}),
    # the keys to Self-Cloud (about keys — never about the data behind them).
    # Giving out or widening a key is not a tool on any surface (the owner
    # types /grant or /scope add himself), so those release nothing.
    "selfcloud_status": frozenset({"keys_issued", "active_keys", "revoked_keys",
                                   "recent_denials", "key_changes", "your_key",
                                   "principle"}),
    "selfcloud_grants": frozenset({"keys", "active", "revoked",
                                   "available_scopes", "presets"}),
    "selfcloud_remove_scope": frozenset({"client", "label", "scopes", "active",
                                         "granted_on", "revoked_on"}),
    "selfcloud_revoke": frozenset({"revoked", "client", "on"}),
    "selfcloud_check_access": frozenset({"allowed", "client", "scope"}),
    "selfcloud_access_log": frozenset({"client", "actor", "surface", "action",
                                       "detail", "allowed", "at"}),
    # secrets: names only
    "vault_status": frozenset({"available", "secrets"}),
    # this door's own report — counts and destinations, never the bodies
    "what_left_the_house": frozenset({"since", "sends", "refused",
                                      "by_destination", "door", "log_lives",
                                      "secrets_used_on_forms", "to_see_everything",
                                      "version"}),
}


# ------------------------------------------------------------ the hard scan
# Shapes that are a secret wherever they appear. This scan is a BACKSTOP:
# the control is the vault (connector/vault.py), where a secret is kept by
# the owner's own hands and used by name, never by value. The scan catches
# what slips past anyway — in English or French, however it is written:
# digits with dots, spaces, dashes, slashes or line breaks between them,
# full-width or Arabic digits, invisible characters, or the word a few words
# before the value ("my password for Desjardins is …", "le code de l'alarme
# est 4821", "the lockbox combination 1234").
#
# What a hit does depends on the direction (I-07, I-14):
#   * handed IN to a tool that keeps what it is given  → refused, nothing kept;
#   * handed IN to a tool that only reads it (triage_message and the other
#     analysers, READS_ONLY below) → the tool still answers — a scam that
#     quotes a card number is exactly what must still be checked — and the
#     log keeps the words with the secret hidden;
#   * going OUT → the secret-shaped words become "[hidden: looks like …]",
#     the rest goes, and the answer says plainly what stayed home. The log
#     names where, never the value.
#
# Digits only count as a number when they stand on their own: a run of
# digits inside a word or a long code (a photo's sha256 fingerprint, a
# tracking code like 1Z999AA10123456784, a file name) is not a card or a
# SIN (I-15).

def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


# What each kind of hit is called, in the owner's words.
CARD = "a card number"
SIN = "a social insurance number"
SSN = "a social security number"
PASSWORD = "a password or PIN"
CODE = "a PIN or a door, alarm or lock code"
APIKEY = "an API key"
BANK = "a bank account number"
HEALTH = "a health card number"
LICENCE = "a driver's licence number"
PASSPORT = "a passport number"
# Most serious first: what looks_secret() names when several are present.
_ORDER = (APIKEY, PASSWORD, CODE, SSN, CARD, SIN, BANK, HEALTH, LICENCE, PASSPORT)

# ---- normalising: one spelling for what can be written many ways
_FOLD = {**dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
                                  "\ufe58\ufe63\uff0d"), "-"),
         **dict.fromkeys(map(ord, "\u2018\u2019\u201a\u201b\u2032\u02bc`\u00b4"), "'"),
         # letters NFKD does not take apart ('hasło' is Polish for password)
         ord("ł"): "l", ord("Ł"): "L", ord("đ"): "d", ord("Đ"): "D", ord("ø"): "o",
         ord("Ø"): "O", ord("ß"): "ss", ord("æ"): "ae", ord("Æ"): "AE", ord("œ"): "oe",
         ord("Œ"): "OE", ord("ı"): "i"}


def _fold_char(ch: str) -> str:
    if unicodedata.category(ch) == "Cf":      # zero-width spaces, soft hyphens
        return ""
    if ch.isdecimal():                        # Arabic, Devanagari, full-width …
        try:
            return str(unicodedata.decimal(ch))
        except ValueError:
            pass
    s = unicodedata.normalize("NFKC", ch).translate(_FOLD)   # NBSP → space
    s = "".join(c for c in unicodedata.normalize("NFKD", s)
                if not unicodedata.combining(c))             # é → e
    return "".join(str(unicodedata.decimal(c, 0)) if c.isdecimal() and not c.isascii()
                   else c for c in s)


def _normalise(text: str) -> tuple[str, list[int] | None]:
    """The text in one spelling, and where each character came from in the
    original (None when nothing changed), so a hit can be hidden in place."""
    if text.isascii():
        return text, None
    out: list[str] = []
    src: list[int] = []
    for i, ch in enumerate(text):
        f = ch if ch.isascii() else _fold_char(ch)
        out.append(f)
        src.extend([i] * len(f))
    return "".join(out), src


# ---- words that announce a secret, and what may follow them
def _rx(*alts: str) -> str:
    return "|".join(sorted(alts, key=len, reverse=True))


_S = r"[\s\-]+"       # between the words of one phrase
# Passwords: the value may be a word ("the password is couch").
_PW_WORDS = _rx(
    r"pass(?:word|wd|code|phrase)s?", r"pwd", r"pass" + _S + r"word",
    r"mots?" + _S + r"de" + _S + r"passe", r"motdepasse", r"mdp",
    r"contrasena", r"clave", r"passwort", r"kennwort", r"senha",
    r"jelsz(?:o|avam|ava|avak)", r"wachtwoord", r"haslo", r"heslo")
# PINs and the codes of a house: the value is a number ("PIN 4821").
_PIN_WORDS = _rx(
    r"pins?", r"pin" + r"[\s\-]*(?:code|number|no|#|kod)", r"nip",
    r"code" + _S + r"(?:nip|pin)", r"geheimzahl", r"cvv2?", r"cvc2?", r"cvn",
    r"numero" + _S + r"d'?\s*identification" + _S + r"personnel(?:le)?",
    r"personal" + _S + r"identification" + _S + r"number",
    r"security" + _S + r"code", r"code" + _S + r"de" + _S + r"securite",
    r"secret" + _S + r"code", r"code" + _S + r"(?:secret|confidentiel)",
    r"access" + _S + r"code", r"code" + _S + r"d'?\s*acces",
    r"entry" + _S + r"code", r"code" + _S + r"d'?\s*entree",
    r"(?:(?:front|back|side|garage|patio|main)" + _S + r")?door" + _S + r"(?:code|pin)",
    r"code" + _S + r"(?:de" + _S + r"(?:la" + _S + r")?|du" + _S + r")?"
    r"(?:porte|garage|barriere|portail|cadenas|coffre|boite" + _S + r"a" + _S + r"cles?)",
    r"code" + _S + r"(?:de" + _S + r"|d'\s*)(?:l'\s*)?alarme",
    r"code" + _S + r"du" + _S + r"systeme" + _S + r"d'\s*alarme",
    r"gate" + _S + r"code", r"garage" + _S + r"(?:code|pin)",
    r"alarm" + _S + r"(?:code|pin|number)",
    r"lock" + r"[\s\-]*box(?:" + _S + r"(?:code|combination|combo))?",
    r"key" + r"[\s\-]*(?:safe|box)(?:" + _S + r"code)?", r"keypad(?:" + _S + r"code)?",
    r"(?:safe|lock)" + _S + r"(?:code|combination|combo)",
    r"combination", r"combinaison", r"combo",
    r"(?:buzzer|intercom)" + _S + r"code",
    r"verification" + _S + r"code", r"code" + _S + r"de" + _S + r"verification",
    r"one" + r"[\s\-]*time" + _S + r"(?:code|pin|passcode)",
    r"code" + _S + r"a" + _S + r"usage" + _S + r"unique", r"otp", r"2fa" + _S + r"code",
    r"auth(?:entication|orization)?" + _S + r"code",
    r"wi[\s\-]?fi" + _S + r"(?:code|key|pin)",
    # 'the code for the front door', 'the code to the garage' (verify I-07)
    r"code" + _S + r"(?:for|to|of|on)" + _S + r"(?:(?:the|my|our|his|her)" + _S + r")?"
    r"(?:(?:front|back|side|main|new|old)" + _S + r")?(?:door|garage|gate|alarm|house"
    r"|building|lock" + r"[\s\-]*box|safe|apartment|condo|keypad|cottage)",
    r"(?:atm|bank|card|debit|visa|mastercard)" + _S + r"(?:code|pin)",
    r"code" + _S + r"(?:de|d')\s*(?:(?:ma|la|mon|sa|ta|notre)" + _S + r")?carte",
    r"code" + _S + r"(?:bancaire|guichet|de" + _S + r"guichet)")
# Words that only count when the value follows at once ("wifi: BlueHouse20").
_WEAK_WORDS = _rx(r"wi[\s\-]?fi", r"network" + _S + r"key",
                  r"cle" + _S + r"(?:wi[\s\-]?fi|reseau|de" + _S + r"securite)")
_KW = re.compile(r"(?<![^\W_])(?:(?P<pw>" + _PW_WORDS + r")|(?P<pin>" + _PIN_WORDS
                 + r")|(?P<weak>" + _WEAK_WORDS + r")|(?P<code>code)|(?P<codes>codes))(?![^\W_])",
                 re.I)

# Words before a bare "code" that make it something else (a postal code).
_NOT_A_SECRET_CODE = frozenset(
    "postal zip area promo promotional discount coupon country dress source morse "
    "bar qr tax product error status colour color dial region building fiscal "
    "civil penal criminal highway traffic".split())
_CONNECT = frozenset(["is", "was", "are", "were", "will", "be", "'s", ":", "=", "-",
                      "->", "=>", "est", "etait", "c'est", "sont", "sera", "ist",
                      "war", "es", "era"])
# Only these may stand between a password word and a plain word that is the
# password ("the password is couch" — but not "the passcode was guessable").
_SAYS = frozenset(["is", "'s", ":", "=", "est", "c'est", "ist", "es"])
_STOP = frozenset("""
a an the this that these those it its in on at to of for from by with without
about above below under behind inside into onto near next not no never still also
only just now then here there my your his her our their me you him them we they i
written saved stored kept lost forgotten forgot changed change changing wrong
incorrect required needed needs missing expired expiring expire expires
reset same different new old too very being been sent attached hidden safe secure
strong weak case sensitive protected verify confirm enter type update please
click tap following something anything nothing everything one ones vault keychain
manager same le la les un une des de du dans sur sous pas plus encore aussi ici
mon ma mes ton ta tes son sa ses notre votre nos vos leur leurs oublie perdu
change changer requis expire nouveau nouvelle ancien ancienne bon mauvais el los
las una unos en mi tu su der die das ein eine mein dein sein nicht
call called calling phone phoned ask asked see check contact dial dialed appeler
appele voir demander
""".split())
# No word that joins a sentence is left out after a password word: 'car' (French
# for 'because') is also a word, and 'The password is car' is a password
# (round 5 had added the conjunctions of four languages here, and lost it).
# A number right after one of these is that thing's number, not the secret.
_LABEL = frozenset(
    "unit apt apartment suite room floor building house page chapter version model "
    "item line ext extension step appartement chambre etage bureau local lot route "
    "highway exit bus flight vol".split())
_PIN_VALUE = re.compile(r"[#*]?\d{3,12}[#*]?|\d{1,4}(?:-\d{1,4}){1,3}")
_YEAR = re.compile(r"(?:19|20)\d\d")
_TOK = re.compile(r"'s\b|c'est\b|->|=>|[:=]|[^\s:=]+", re.I)
_LEAD, _TRAIL = "\"'([{<«", "\"')]}>».,;:!?"
_BEFORE = re.compile(
    r"(?:^|\s)(?P<v>[^\s]+)\s+(?:is|was|est|c'est|=|:)\s+(?:(?:my|the|our|his|her|your|mon|ma|"
    r"mes|le|la|notre|votre|son|sa|leur)\s+)?$", re.I)
_MAX_GAP = 5
# Words that say whose a password is ('the password FOR MY bank').
_WHOSE = frozenset("for of to at on my our his her de du des d' ma mon mes sa son la le".split())
_SPACED = re.compile(r"(\d{1,4})(?:[ \t](\d{1,4})){1,7}(?![\d])")


def _spaced_pin(n: str, at: int) -> int | None:
    """'PIN: 48 21', 'my PIN is 4 8 2 1': digits typed with spaces between.
    The end of the whole PIN, or None (one group alone is read as usual)."""
    m = _SPACED.match(n, at)
    if not m or " " not in m.group() and "\t" not in m.group():
        return None
    digits = re.sub(r"\D", "", m.group())
    if not 4 <= len(digits) <= 8 or _PHONE_AT.match(n, at):
        return None
    if _UNIT_AFTER.match(n, m.end()):
        return None
    return m.end()
_DATE_SHAPE = re.compile(r"(?:19|20)\d\d[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])"
                         r"|(?:0?[1-9]|[12]\d|3[01])[-/.](?:0?[1-9]|[12]\d|3[01])[-/.](?:19|20)\d\d")
# A number followed by one of these is a dose, a size, a price or a count —
# 'a combination pill, 250 mg' is medicine, not a safe's combination (verify).
_UNIT_AFTER = re.compile(r"\s?(?:mg|mcg|µg|ug|ml|cc|g|gr|kg|lbs?|oz|iu|units?|mmol|mm|cm|km"
                         r"|m|ft|in|%|\$|dollars?|cad|usd|eur|beds?|people|persons?|pills?"
                         r"|tablets?|capsules?|caps|doses?|times?|years?|ans|yrs?|days?|jours?"
                         r"|hours?|hrs?|h|minutes?|mins?|km/h|kph|mph|calories|kcal|sq)\b", re.I)
# A 'pin' that is a thing one wears or collects ('his Legion pin 1985').
_NOT_A_PIN_BEFORE = frozenset("lapel legion enamel hat badge collector collectible "
                              "collectors bowling safety hair push rolling sewing drawing "
                              "lucky souvenir olympic campaign flag novelty tie brooch "
                              "medal service veterans".split())


def _ndigits(s: str) -> int:
    return sum(c.isdigit() for c in s)


def _is_value(fam: str, raw: str, conn: bool, gap: int, prev: str,
              says: bool = True) -> bool:
    """Is this token the secret that the word before announced?"""
    v = raw.lstrip(_LEAD + "-").rstrip(_TRAIL)
    if not v:
        return False
    if _DATE_SHAPE.fullmatch(v):
        return False          # 'changed my password on 2026-10-14' is a day, not a code
    d = _ndigits(v)
    if fam in ("pin", "code"):
        if not _PIN_VALUE.fullmatch(v) or prev in _LABEL:
            return False
        if fam == "code" and not (conn and gap == 0 and 4 <= d <= 8):
            return False
        return not (gap and not conn and _YEAR.fullmatch(v))
    letters = any(c.isalpha() for c in v)
    if fam == "weak":
        return conn and gap == 0 and ((d and letters and len(v) >= 6)
                                      or bool(_PIN_VALUE.fullmatch(v) and d >= 4))
    # a password
    if _PIN_VALUE.fullmatch(v):
        return d >= 3 and prev not in _LABEL and not (gap and not conn and _YEAR.fullmatch(v))
    if d and letters and len(v) >= 4:
        return True                                   # hunter22, Tulipe2024!
    return (conn and says and gap == 0 and letters and len(v) >= 3
            and v.lower() not in _STOP
            and not raw.startswith(("[", "(", "<")))  # "the password is couch"


def _trim(n: str, s: int, e: int) -> tuple[int, int]:
    """A hit's span without the quotes, brackets and commas around it, so
    hiding it never eats the punctuation of the sentence (or of JSON)."""
    while e > s and n[e - 1] in "\"'),;]}>»\\":
        e -= 1
    while s < e and n[s] in "\"'([{<«\\":
        s += 1
    return s, e


# 'Alarm: 7731', 'Front door: 4821', 'the alarm is 4821', 'Buzzer 2580': a
# part of the house that says its number is saying its code (verify I-07).
_HOUSE_SAYS = re.compile(
    r"(?<![^\W_])(?:alarm|alarme|(?:front|back|side|garage|patio|main)[\s\-]+door|door"
    r"|garage|gate|lock[\s\-]*box|keypad|safe|portail|porte|cadenas)"
    r"\s*(?::|=|\s(?:is|was|est|c'est|:)|-)\s*(?P<v>[#*]?\d{3,8}[#*]?)(?![\d\w.,]\d)", re.I)
_HOUSE_BARE = re.compile(r"(?<![^\W_])(?:buzzer|intercom|interphone)\s*[:=]?\s*"
                         r"(?P<v>[#*]?\d{3,8}[#*]?)(?![\d])", re.I)
_STREET_AFTER = re.compile(r"\s+(?:[A-Z][a-z]+\s+)?(?:st|street|ave|avenue|rd|road|rue|blvd"
                           r"|boulevard|dr|drive|lane|ln|way|cres|crescent|crt|court|chemin"
                           r"|place|pl|terrace|hwy)\b", re.I)
# A login written with its password: 'bank login is laszlo / Hunter22!',
# 'user laszlo, pass Soleil2024'.
_CREDS = re.compile(
    r"(?<![^\W_])(?:log[\s\-]?in|user(?:[\s\-]?name)?|identifiant|usager|utilisateur)"
    r"\s*(?:is|:|=|est)?\s*[^\s,/;]+\s*(?:[,/;]|and|et)\s*(?:(?:pass(?:word)?|pw|pwd|mdp"
    r"|mot\s+de\s+passe)\s*(?:is|:|=|est)?\s*)?(?P<v>[^\s,;]{4,})", re.I)


def _house_hits(n: str) -> list[tuple[int, int, str]]:
    out = []
    for rx in (_HOUSE_SAYS, _HOUSE_BARE):
        for m in rx.finditer(n):
            v = m.group("v")
            if _YEAR.fullmatch(v) or _UNIT_AFTER.match(n, m.end("v")) \
                    or _STREET_AFTER.match(n, m.end("v")) or _PHONE_AT.match(n, m.start("v")):
                continue
            out.append((m.start("v"), m.end("v"), CODE))
    for m in _CREDS.finditer(n):
        v = m.group("v").rstrip(_TRAIL)
        if any(c.isdigit() for c in v) or any(c in "!@#$%^&*" for c in v) or (
                m.group(0).lower().find("pass") != -1 and len(v) >= 4):
            out.append((m.start("v"), m.start("v") + len(v), PASSWORD))
    return out


# ---- what a number after a word that announces a secret is
# After these the number is that thing's own number — a reference, a case, a
# ticket, an account — never the code. Only when such a word stands right
# after the code's own word ('My PIN ref 4821', 'Alarm code (dossier) 4821')
# and nothing further on is the code, is that number the code.
_REF_WORDS = frozenset("ref reference dossier file case ticket order invoice facture account "
                       "compte confirmation claim serial policy member membership client customer "
                       "receipt transaction tracking booking reservation incident request".split())
# After these a number is a phone number only when it is shaped like one
# ('PIN for my phone 4821', 'My PIN, tel 4824' are PINs).
_PHONE_WORDS = frozenset("tel phone telephone call called calling dial dialed phoned appeler "
                         "appelle appelez rappeler cell mobile fax".split())
# After these a number that reads as a time of day is a time ('at 1430',
# 'they close at 1700', 'open 0900', 'à 1430'); and so is one after 'to' or
# 'and' that follows a time ('open 0900 to 1700').
_TIME_WORDS = frozenset("at after before by until till til around from open opens opened "
                        "close closes closing a vers avant apres jusqu'a des".split())
_TIME_LINKS = frozenset("to and till until - a et".split())
# After these a year is a year — when something happened ('built in 1987',
# 'since 1998', 'born in 1948', 'March 3 1950', 'before 2027') — and not the
# code; anywhere else a number shaped like a year can be one ('changed to
# 1987', 'new number 1987', "maintenant c'est 1962").
_YEAR_BEFORE = frozenset("""in since from until till before after by of circa around during
    year years en depuis dans avant apres jusqu'en des vers annee annees ete hiver
    january february march april may june july august september october november december
    jan feb mar apr jun jul aug sep sept oct nov dec janvier fevrier mars avril mai juin
    juillet aout septembre octobre novembre decembre""".split())
# What a card's last digits are called ('the card ending 4821').
_ENDING = frozenset("ending ends last finissant".split())
_DIGIT_WORDS = frozenset("zero oh one two three four five six seven eight nine un une deux "
                         "trois quatre cinq sept huit neuf".split())
_HHMM = re.compile(r"(?:[01]?\d|2[0-3])[0-5]\d")
_CLOCK_AFTER = re.compile(r"\s?(?:am|pm|a\.m\.|p\.m\.|h|hrs?|o'clock)\b", re.I)
# How far after its word the code may stand ('Alarm code: call the company
# 613 555 0199 first, then 4821'); a password's own shape a little less far.
_REACH = 14
_REACH_PW = 10
# The end of a clause: of a sentence (a '.', '!' or '?' before a capital, a
# number or the end — 'Hunter22! and my daughter …' goes on), a line, or a
# semicolon.
_CLAUSE_END = re.compile(r"[.!?]+(?=\s*$|[ \t]+[\"'«(\[]?[A-Z\u00c0-\u00de0-9])|[;\n]")
_PHONE_AT = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)")
_PHONE_WRITTEN = re.compile(r"(?:\+?1[\s.\-])?(?:\(\d{3}\)\s?|\d{3}[\s.\-])\d{3}[\s.\-]\d{4}(?!\d)")


def _clause(n: str, start: int, read_on: bool) -> int:
    """Where the clause that begins at `start` ends. With `read_on`, a clause
    that holds nothing yet (the value written on the next line, 'PIN:\\n4821')
    goes on into the next one."""
    end = start
    for _ in range(4):
        m = _CLAUSE_END.search(n, end)
        stop = m.start() if m else len(n)
        said = [t.group().lower() for t in _TOK.finditer(n, start, stop)]
        if not read_on or not m or any(
                w not in _CONNECT and (re.search(r"[^\W_]|[#*]\d", w) or w == _PH)
                for w in said):
            return stop
        end = m.end()
    return stop


_CLOSES = {")": "(", "]": "[", "}": "{", ">": "<", "»": "«", '"': '"', "'": "'"}


def _tail(n: str, s: int, e: int) -> tuple[int, int]:
    """A password and the rest of its clause, without the spaces around it
    and without a closing bracket or quote whose opening one is not in it."""
    while s < e and (n[s].isspace() or n[s] in _LEAD):
        s += 1
    if e > s and not n[e - 1].isspace() and n[e:e + 1] in ("!", "?", ".") \
            and not n[e:].strip(".!? \t"):
        e = len(n.rstrip())                     # 'Tulipe2024!' at the end: '!' and all
    while e > s and n[e - 1].isspace():
        e -= 1
    while e > s and n[e - 1] in _CLOSES and _CLOSES[n[e - 1]] not in n[s:e - 1]:
        e -= 1
    return s, e


def _is_time(n: str, v: str, end: int) -> bool:
    return bool(_HHMM.fullmatch(v) and len(v) >= 3) or bool(
        v.isdigit() and len(v) <= 4 and _CLOCK_AFTER.match(n, end))


def _why_not_the_code(n: str, at: int, v: str, prev: str, pos: bool,
                      after_time: bool = False) -> str | None:
    """Why the number `v` (at `at`) is not the code a word before announced —
    a date, a phone number, an amount, a street, a unit's, a reference's or a
    card ending's own number, a time, a year — or None. `pos`: it stands
    where a value is said (right after the word, a ':' or 'is', or the code
    just before it); `after_time`: a time stood just before ('0900 to 1700')."""
    end = at + len(v)
    if _DATE_SHAPE.fullmatch(v):
        return "date"
    if _PHONE_AT.match(n, at) or _PHONE_WRITTEN.match(n, at):
        return "phone"
    if (_UNIT_AFTER.match(n, end) or _MONEY_AFTER.match(n, end)
            or _MONEY_BEFORE.search(n[max(0, at - 2):at])):
        return "amount"
    if _STREET_AFTER.match(n, end):
        return "street"
    if prev in _LABEL or prev in _ENDING:
        return "label"
    if prev in _REF_WORDS:
        return "ref"
    if prev in _PHONE_WORDS and _ndigits(v) >= 7:
        return "phone"
    if (prev in _TIME_WORDS or (after_time and prev in _TIME_LINKS)) and _is_time(n, v, end):
        return "time"
    if _YEAR.fullmatch(v) and not pos and (prev in _YEAR_BEFORE or prev.isdigit()):
        return "year"
    return None


def _digit_words(n: str, toks: list, i: int) -> int | None:
    """'four eight two one': a PIN said in words. The end of it, or None."""
    k = i
    while k < len(toks) and toks[k].group().lower().strip(_LEAD + _TRAIL) in _DIGIT_WORDS:
        if k > i and n[toks[k - 1].end():toks[k].start()].strip(" \t,-"):
            break
        k += 1
    return toks[k - 1].end() if k - i >= 4 else None


def _keyword_hits(n: str) -> list[tuple[int, int, str]]:
    """The secrets that words announce ('PIN 4821', 'the password is couch').

    For a password, once its value is found the rest of the clause goes with
    it (to the end of the sentence, the line or a semicolon), so a
    passphrase's tail never leaks ('Wifi password: Blue42 Sky House'). For a
    PIN or a code, the search reads the whole clause: a phone number, a
    reference, case or ticket number, a time, a year, a street number or an
    amount is stepped over and never ends it ('Alarm code: call the company
    613 555 0199 first, then 4821'); only an unexplained number is the code,
    and every other code in the same clause is hidden with it ('Garage code
    4821, gate 2580'). A note that names a code but holds none ('Called
    about my PIN reset, ref 5678') holds no secret.

    A '\\ue000' stands where a mark was (see find_secrets): the value's slot
    is taken. After a password word the rest of its clause is hidden; after
    a PIN or code word the search goes on for any other code."""
    out = _house_hits(n) if _PH not in n else []
    for m in _KW.finditer(n):
        fam = m.lastgroup
        what = PASSWORD if fam in ("pw", "weak") else CODE
        if fam in ("code", "codes"):
            before = re.findall(r"[a-z]+", n[max(0, m.start() - 20):m.start()].lower())
            if before and before[-1] in _NOT_A_SECRET_CODE:
                continue
        if fam == "pin" and m.group().lower() in ("pin", "pins"):
            before = re.findall(r"[a-z]+", n[max(0, m.start() - 24):m.start()].lower())
            if before and before[-1] in _NOT_A_PIN_BEFORE:
                continue
        end_c = _clause(n, m.end(), read_on=True)
        toks = list(_TOK.finditer(n, m.end(), end_c))
        if fam == "codes" and not (toks and toks[0].group().lower() in _CONNECT):
            continue                # 'codes' names a list only before ':' ('Codes: garage 4821')
        conn, says, just_said, linked = False, False, False, False
        gap, prev, skip_to = 0, "", -1
        found, candidate, after_value, last_time = False, None, False, -9
        for i, t in enumerate(toks):
            if t.start() < skip_to:
                continue
            raw = t.group()
            low = raw.lower()
            if raw == _PH:
                if fam in ("pw", "weak"):
                    if gap == 0 or just_said:
                        # the password's slot: what follows in the clause is its tail
                        rest = n[t.end():end_c]
                        if re.search(r"[^\W_]", rest.replace(_PH, " ")):
                            out.append((*_tail(n, t.end(), end_c), what))
                        found = True
                        break
                    prev, gap = "", gap + 1
                    continue
                found = after_value = True         # the code's slot: look on for others
                prev = ""
                continue
            if low in _CONNECT:
                conn, says, just_said, prev = True, low in _SAYS, low in _SAYS or low in ":=-", ""
                continue
            v = raw.lstrip(_LEAD + "-").rstrip(_TRAIL)
            at = t.start() + len(raw) - len(raw.lstrip(_LEAD + "-"))
            ph = _PHONE_WRITTEN.match(n, at)
            if ph:                                  # a phone number is stepped over
                skip_to, gap, prev, after_value = ph.end(), gap + 1, "phone", False
                continue
            pos = gap == 0 or just_said or after_value
            if fam in ("pin", "code", "codes"):
                spaced = _spaced_pin(n, t.start()) if fam == "pin" and (gap <= 2 or pos) else None
                words = _digit_words(n, toks, i) if fam == "pin" else None
                if spaced or words:
                    out.append((*_trim(n, t.start(), spaced or words), what))
                    found = after_value = True
                    skip_to = spaced or words
                    gap += 1
                    continue
                # a bare 'code' holds its first value only at once, after 'is' or ':'
                first_ok = fam != "code" or (conn and gap == 0 and 4 <= _ndigits(v) <= 8)
                if _PIN_VALUE.fullmatch(v) and (found or first_ok):
                    why = _why_not_the_code(n, at, v, prev, pos, gap - last_time <= 2)
                    if why == "time":
                        last_time = gap
                    if why == "ref" and not found and gap == 1 and candidate is None:
                        candidate = _trim(n, t.start(), t.end())   # 'My PIN ref 4821'
                    elif why is None and (found or gap <= _REACH or just_said):
                        out.append((*_trim(n, t.start(), t.end()), what))
                        found = after_value = True
                        prev, gap, just_said = low.strip(_LEAD + _TRAIL), gap + 1, False
                        continue
            else:                                   # a password
                plain_ok = fam == "pw" and just_said and linked and gap <= _MAX_GAP
                if not found and (gap <= _REACH_PW or just_said) and _is_value(
                        fam, raw, conn, 0 if plain_ok else gap, prev, says) and not (
                        _PIN_VALUE.fullmatch(v) and _why_not_the_code(n, at, v, prev, pos)):
                    out.append((*_tail(n, t.start(), end_c), what))
                    found = True
                    break
            gap += 1
            just_said = after_value = False
            if low.strip(_LEAD + _TRAIL) in _WHOSE:
                linked = True
            prev = low.strip(_LEAD + _TRAIL)
            if fam in ("weak", "code") and not found:
                break                               # these hold their value only at once
        if candidate and not found:
            out.append((*candidate, what))
        # ...or before it: "4821 is my PIN", "Soleil2024 est mon mot de passe"
        if fam in ("pw", "pin"):
            b = _BEFORE.search(n[max(0, m.start() - 80):m.start()])
            if b:
                v = b.group("v")
                core = v.lstrip(_LEAD + "-").rstrip(_TRAIL)
                if _ndigits(core) >= (3 if fam == "pin" else 1) and _is_value(fam, v, True, 0, ""):
                    s = max(0, m.start() - 80) + b.start("v")
                    out.append((*_trim(n, s, s + len(v)), what))
    return out


# ---- numbers that stand on their own
# a comma too (verify I-66: '046,454,286' and '4111,1111,1111,1111' went
# onto forms) — but a comma also groups thousands, so a number written with
# commas counts only in a card's 4-4-4-4 shape, or beside the word 'SIN'
_SEPR = "(?:[ \\t]*[.,\\-/_\u00b7\u2022][ \\t]*|\\s{1,3})"
_RUN = re.compile(r"(?<![^\W_])(?<![^\W_][\-./_])\d+(?:" + _SEPR + r"\d+)*"
                  r"(?![^\W_])(?![\-./_][^\W_])")
_DIGITS = re.compile(r"\d+")
_CARD_CTX = re.compile(r"(?<![^\W_])(?:cards?|cartes?|visa|master\s?card|amex|american express"
                       r"|discover|credit|debit|cc|cvv)(?![^\W_])", re.I)
_SIN_CTX = re.compile(r"(?<![^\W_])(?:s\.?\s?i\.?\s?n\.?|n\.?\s?a\.?\s?s\.?|social\s+insurance"
                      r"|assurance\s+sociale)(?![^\W_])", re.I)
_SSN_CTX = re.compile(r"(?<![^\W_])(?:s\.?\s?s\.?\s?n\.?|social\s+security)(?![^\W_])", re.I)
# A long number after one of these is an order or a parcel, not a card.
_REF_CTX = re.compile(r"(?:(?<![^\W_])(?:orders?|ref|reference|tracking|track|confirmation"
                      r"|invoice|transaction|receipt|parcel|package|shipment|colis|commande"
                      r"|suivi|facture|booking|reservation|ticket|case|claim|policy|member"
                      r"|membership|serial|imei|iccid|barcode|upc|isbn|no|num|n°|nº"
                      r"|aeroplan|airmiles|air\s+miles|points|rewards|loyalty|optimum|scene"
                      r"|petro|costco|library|patient|student|employee|customer|client)(?![^\W_])"
                      r"(?:\W{1,3}(?:number|no|num|n°|nº|#))?|#)\W{0,3}$", re.I)


_MONEY_BEFORE = re.compile(r"[$€£]\s?$")
_MONEY_AFTER = re.compile(r"\s?(?:[$€£%]|dollars?\b|cad\b|usd\b|eur\b)", re.I)


def _number_hits(n: str) -> list[tuple[int, int, str]]:
    out = []
    for m in _RUN.finditer(n):
        gs = [(m.start() + g.start(), m.start() + g.end()) for g in _DIGITS.finditer(m.group())]
        lens = [e - s for s, e in gs]
        digits = "".join(n[s:e] for s, e in gs)
        seps = [n[gs[i][1]:gs[i + 1][0]].strip() for i in range(len(gs) - 1)]
        if len(gs) == 4 and max(lens) <= 3 and all(s == "." for s in seps):
            continue                                     # an IP address
        ctx = n[max(0, m.start() - 40):m.start()]
        near = ctx[-25:]
        card_kw, sin_kw, ssn_kw = (_CARD_CTX.search(ctx), _SIN_CTX.search(near),
                                   _SSN_CTX.search(near))
        if not (card_kw or sin_kw or ssn_kw) and lens[:4] != [4, 4, 4, 4]:
            if (_MONEY_BEFORE.search(n[max(0, m.start() - 3):m.start()])
                    or _MONEY_AFTER.match(n, m.end())):
                continue                                 # "123 456 789 $": an amount
            if len(gs) > 1 and all(_YEAR.fullmatch(n[s:e]) for s, e in gs):
                continue                                 # "2019 2020 2021": years
        ref = _REF_CTX.search(ctx) and not card_kw and not sin_kw and not ssn_kw

        def hit(i, j, what):
            out.append((gs[i][0], gs[j][1], what))

        found = False
        for i in range(len(gs)):
            w3 = lens[i:i + 3]
            sub = "".join(n[s:e] for s, e in gs[i:i + 3])
            if w3 == [3, 2, 4] and len(set(seps[i:i + 2])) == 1 and (
                    seps[i] == "-" or (sub[:3] not in ("000", "666") and sub[0] != "9"
                                       and sub[3:5] != "00" and sub[5:] != "0000")):
                hit(i, i + 2, SSN); found = True
            elif w3 == [3, 3, 3] and len(set(seps[i:i + 2])) == 1 and (
                    sin_kw or (_luhn(sub) and seps[i] != ",")):
                hit(i, i + 2, SIN); found = True
            for shape in ([4, 4, 4, 4, 3], [4, 4, 4, 4], [4, 6, 5], [4, 6, 4]):
                k = len(shape)
                if lens[i:i + k] == shape:
                    sub = "".join(n[s:e] for s, e in gs[i:i + k])
                    if _luhn(sub):
                        hit(i, i + k - 1, CARD); found = True
                        break
        if found:
            continue
        nd, ng = len(digits), len(gs)
        if "," in seps and not (card_kw or sin_kw or ssn_kw):
            continue                                     # '1,234,567,890': a count
        if nd == 9 and (sin_kw or ssn_kw):
            hit(0, ng - 1, SSN if ssn_kw and not sin_kw else SIN)
        elif 13 <= nd <= 19 and _luhn(digits) and (card_kw or (ng != 2 and not ref)):
            hit(0, ng - 1, CARD)
        elif nd == 9 and ng == 1 and _luhn(digits) and not ref:
            hit(0, 0, SIN)
    return out


# ---- identifiers announced by their name: bank, health card, licence, passport
_ID_WORDS = {
    BANK: re.compile(r"(?<![^\W_])(?:transit|institution|inst|routing|aba|sort" + _S + r"code"
                     r"|bsb|folio|(?:numero|no)" + _S + r"de" + _S + r"(?:transit|compte)"
                     r"|(?:(?:bank|chequing|checking|savings|cheque|current|joint)" + _S
                     + r")?account|acct|a/c|compte(?:" + _S + r"(?:bancaire|cheques?|epargne"
                     r"|conjoint))?)(?:" + _S + r"(?:number|no|num|#))?(?![^\W_])", re.I),
    HEALTH: re.compile(r"(?<![^\W_])(?:ohip|ramq|health" + _S + r"(?:insurance" + _S
                       + r")?(?:card|number)|healthcard|carte" + _S + r"(?:sante|soleil|"
                       r"d'\s*assurance" + _S + r"maladie)|(?:numero" + _S + r")?d?'?\s*"
                       r"assurance" + _S + r"maladie|personal" + _S + r"health" + _S
                       + r"number|phn|care" + r"[\s\-]*card|medicare)(?:" + _S
                       + r"(?:number|no|num|#))?(?![^\W_])", re.I),
    LICENCE: re.compile(r"(?<![^\W_])(?:driver'?s?" + _S + r"licen[cs]e|driving" + _S
                        + r"licen[cs]e|licen[cs]e|permis(?:" + _S + r"de" + _S
                        + r"conduire)?|dl)(?:" + _S + r"(?:number|no|num|#))?(?![^\W_])", re.I),
    PASSPORT: re.compile(r"(?<![^\W_])(?:passport|passeport)(?:" + _S
                         + r"(?:number|no|num|#))?(?![^\W_])", re.I),
}
_ID_FILLER = frozenset(["number", "no", "num", "#", "is", "was", "est", "my", "the", "mon",
                        "ma", "le", "la", "de", "du", "of", "card", "carte", ":", "=", "-",
                        "'s", "c'est"])
# After these words the number that follows is something else (an amount, a date).
_ID_BREAK = frozenset("balance solde total amount montant since depuis until opened "
                      "closed ouvert ferme expires expiry expire line ligne phone "
                      "telephone call appeler".split())
_DATE_OR_PHONE = re.compile(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
                            r"|(?:\+?1[-.]?)?\(?\d{3}\)?[-.]\d{3}[-.]\d{4}")
_PASSPORT_VALUE = re.compile(r"[a-z]{1,2}\d{6,8}|\d{8,9}", re.I)
_SHAPES = [
    (HEALTH, re.compile(r"(?<![^\W_])\d{4}[ \-]?\d{3}[ \-]?\d{3}[ \-]?[A-Z]{2}(?![^\W_])")),
    (LICENCE, re.compile(r"(?<![^\W_])[A-Z]\d{4}[ \-]?\d{5}[ \-]?\d{5}(?![^\W_])")),   # Ontario
    (LICENCE, re.compile(r"(?<![^\W_])[A-Z]\d{4}[ \-]?\d{6}[ \-]?\d{2}(?![^\W_])")),   # Quebec
]
_RAMQ = re.compile(r"(?<![^\W_])[A-Z]{4} ?\d{2}(\d{2}) ?(\d{2})\d{2}(?![^\W_])")
_IBAN = re.compile(r"(?<![^\W_])[A-Z]{2}\d{2}(?:[ \-]?[A-Z0-9]{4}){2,7}(?:[ \-]?[A-Z0-9]{1,3})?"
                   r"(?![^\W_])", re.I)


def _iban_ok(s: str) -> bool:
    s = re.sub(r"[ \-]", "", s).upper()
    if not 15 <= len(s) <= 34:
        return False
    moved = s[4:] + s[:4]
    try:
        return int("".join(str(int(c, 36)) for c in moved)) % 97 == 1
    except ValueError:
        return False


_BANK_AT_ONCE = re.compile(r"(?i)(?:transit|institution|inst|folio)\b")
_NOT_A_BANK = frozenset("hydro bell rogers telus videotron fido koodo virgin freedom shaw "
                        "cogeco enbridge gas electric electricity water phone internet cable "
                        "aeroplan loyalty optimum scene airmiles miles costco member library "
                        "netflix amazon customer client utility utilities billing insurance "
                        "pharmacy rx hospital patient school student transit presto ttc "
                        "parking toll bill billing invoice".split())


def _id_hits(n: str) -> list[tuple[int, int, str]]:
    out = []
    for what, rx in _ID_WORDS.items():
        for m in rx.finditer(n):
            if what == BANK:
                before = re.findall(r"[a-z]+", n[max(0, m.start() - 30):m.start()].lower())
                if set(before[-3:]) & _NOT_A_BANK:
                    continue            # 'Hydro account 123456789' is a bill, not a bank
            at_once = what == BANK and bool(_BANK_AT_ONCE.match(m.group()))
            gap, start, end, digits, chunk = 0, None, None, 0, ""
            for t in _TOK.finditer(n, m.end(), min(len(n), m.end() + 80)):
                raw = t.group()
                v = raw.lstrip(_LEAD).rstrip(_TRAIL)
                if start is None:
                    if v.lower() in _ID_FILLER or not v:
                        continue
                    if not any(c.isdigit() for c in v):
                        gap += 1
                        if (gap > 3 or raw[-1:] in ".!?;" or v.lower() in _ID_BREAK
                                or at_once):
                            break       # 'transit pass costs 128' is a fare, not a transit no.
                        continue
                    if ("$" in raw or "%" in raw or re.search(r"\d,\d{3}", v)
                            or re.fullmatch(r"\d+\.\d{2}", v) or _UNIT_AFTER.match(n, t.end())
                            or _DATE_OR_PHONE.fullmatch(v)):
                        break                     # money, a date, a count or a phone number
                    start = t.start()
                elif not (v == raw and (re.fullmatch(r"[A-Za-z0-9\-]{0,5}\d[A-Za-z0-9\-]{0,5}", v)
                                        or (what == HEALTH and re.fullmatch(r"[A-Za-z]{2}", v)))):
                    break                                     # the number has ended
                end, chunk = t.end(), chunk + v
                digits = _ndigits(chunk)
            if start is None:
                continue
            compact = re.sub(r"[^A-Za-z0-9]", "", chunk)
            ok = {BANK: digits >= 3 and compact.isdigit()
                        and (digits >= 5 or not re.match(r"(?i)(?:.*account|acct|compte|a/c)",
                                                         m.group())),
                  HEALTH: digits >= 8,
                  LICENCE: digits >= 5 and (len(m.group()) > 4 or digits >= 7),
                  PASSPORT: bool(_PASSPORT_VALUE.fullmatch(compact))}[what]
            if ok:
                out.append((*_trim(n, start, end), what))
    for what, rx in _SHAPES:
        out.extend((m.start(), m.end(), what) for m in rx.finditer(n))
    for m in _RAMQ.finditer(n):
        mm, dd = int(m.group(1)), int(m.group(2))
        if (1 <= mm <= 12 or 51 <= mm <= 62) and 1 <= dd <= 31:
            out.append((m.start(), m.end(), HEALTH))
    out.extend((m.start(), m.end(), BANK) for m in _IBAN.finditer(n) if _iban_ok(m.group()))
    return out


# ---- keys for other services
_APIKEY = re.compile(
    r"(?<![A-Za-z0-9])(?:sk-ant-[A-Za-z0-9_\-]{4,}|sk-(?:proj|svcacct|admin|live|test)-"
    r"[A-Za-z0-9_\-]{12,}|sk-[A-Za-z0-9]{20,}|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}"
    r"|whsec_[A-Za-z0-9]{16,}|A(?:KIA|SIA)[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_\-]{30,}"
    r"|hf_[A-Za-z0-9]{30,}|glpat-[A-Za-z0-9_\-]{20,}|npm_[A-Za-z0-9]{30,}"
    r"|SG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}"
    r"|-----BEGIN[A-Z ]*PRIVATE KEY-----(?:[\s\S]*?-----END[A-Z ]*PRIVATE KEY-----|[\s\S]*))")
_KEY_WORDS = re.compile(
    r"(?<![^\W_])(?:api" + r"[\s_\-]?key|apikey|secret[\s_\-]?key|access[\s_\-]?key(?:[\s_\-]?id)?"
    r"|client[\s_\-]?secret|(?:auth|access|refresh|bearer)[\s_\-]?token|bearer|private[\s_\-]?key"
    r"|aws_secret_access_key|token)(?![^\W_])\W{0,4}(?P<v>[A-Za-z0-9_\-+/=.]{20,})", re.I)


def _key_hits(n: str) -> list[tuple[int, int, str]]:
    out = [(m.start(), m.end(), APIKEY) for m in _APIKEY.finditer(n)]
    for m in _KEY_WORDS.finditer(n):
        v = m.group("v")
        if any(c.isdigit() for c in v) and any(c.isalpha() for c in v):
            out.append((m.start("v"), m.end("v"), APIKEY))
    return out


_HEXID = re.compile(r"(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{20,}")


# A mark in place of something hidden: "[hidden: looks like a card number]".
# Only JEFFEREY makes one (mask_text). Its own words are never read — the mark
# says "a PIN or a door, alarm or lock code", and read as words it announced
# the next number, so one old note ('Garage code 4821, gate 2580') blacked out
# 'who am I' and 'tell my story' whole (verify I-07, I-14, I-15).
#
# What an engine HANDS IN with a mark in it is never kept (admit): the text
# already has something hidden in it, and JEFFEREY does not store text it hid.
# That is the whole rule (R1, round 6). Two rounds tried to read what follows a
# mark — 'My PIN [hidden] 4821', 'Bank PIN[hidden]4821', 'Garage code
# [hidden]\nnow 5932' — and each reading let a different secret in. A tool
# that only reads what it is given (a scam check) still answers, and takes the
# mark as a sign that a secret was there (secret_signals).
#
# On the way OUT a mark can still be met: in JEFFEREY's own answer hidden
# twice over (the system prompt), and in a note an older version kept. In
# JEFFEREY's own answer a mark stands where a value was — after a password
# word the rest of its clause, after a PIN or code word any other code, would
# have been hidden with it, so its answer is clean when read again. A note
# kept before is read harder (`legacy`, the first look at what the store
# holds): every mark is also read as if it were not there, taken out and as a
# space ('Hun[hidden]ter22!', 'Bank PIN[hidden]4821'), so what an engine
# slipped in behind a mark never goes out. For shapes that need no word (a
# card, a SIN, a key) every mark is read as not there at all.
# Any spelling counts on the way out too ('[Hidden]', '[HIDDEN]', '[hidden - a
# code]'): a note an older version kept is read as harshly as the door reads.
_MARK_CORE = r"\[[ \t]*hidden\b[^\[\]\n]{0,120}\]"
_MARK = re.compile(_MARK_CORE, re.I)
_MARK_SPACED = re.compile(r"[ \t]*" + _MARK_CORE + r"[ \t]*", re.I)
_MARK_IN_WORD = re.compile(r"(?<=[^\W_])" + _MARK_CORE + r"(?=[^\W_])", re.I)
_PH = ""   # a mark, for the words that announce a value (a private-use letter)
_SLOT = re.compile(_MARK_IN_WORD.pattern + "|" + _MARK_SPACED.pattern, re.I)
# Any way a mark can be written, for the door: '[hidden]', '[Hidden: …]',
# '[ HIDDEN', full-width brackets.
_ANY_MARK = re.compile(r"\[\s*hidden", re.I)
MARK_REFUSAL = ("this text already has something hidden in it; JEFFEREY does not store text "
                "it hid")


def has_mark(text) -> bool:
    """Does this text hold one of JEFFEREY's hidden-marks ('[hidden …]'),
    however it is written?"""
    if not isinstance(text, str) or "idden" not in text.lower() and text.isascii():
        return False
    n, _ = _normalise(text)
    return bool(_ANY_MARK.search(n))


def _without_marks(text: str, rx: re.Pattern, glue
                   ) -> tuple[str, list[int], dict[int, int]]:
    """`text` with every mark replaced by `glue` (a string, or a function of
    the match); where each character of the result came from in `text` (glue
    points at the start of its mark); and where each such mark ends."""
    out: list[str] = []
    src: list[int] = []
    ends: dict[int, int] = {}
    last = 0
    for m in rx.finditer(text):
        g = glue(m) if callable(glue) else glue
        out.append(text[last:m.start()])
        src.extend(range(last, m.start()))
        out.append(g)
        src.extend([m.start()] * len(g))
        ends[m.start()] = m.end()
        last = m.end()
    out.append(text[last:])
    src.extend(range(last, len(text)))
    return "".join(out), src, ends


def _slot(m: re.Match) -> str:
    """A mark inside a word goes; any other stands as the value's place."""
    s, e, t = m.start(), m.end(), m.string
    inside = (t[s:s + 1] == "[" and t[e - 1:e] == "]" and s > 0 and e < len(t)
              and _WORDCH.match(t, s - 1) and _WORDCH.match(t, e))
    return "" if inside else f" {_PH} "


_WORDCH = re.compile(r"[^\W_]")


def find_secrets(text: str, legacy: bool = False) -> list[tuple[int, int, str]]:
    """Every secret-shaped span in `text`: (start, end, what), in the
    original text's positions, overlapping spans merged, in order. A hidden
    mark is read for what it is (see _MARK above); `legacy` reads a note an
    older version kept, marks and all, as if each mark were not there too."""
    if not isinstance(text, str) or len(text) < 6 or _HEXID.fullmatch(text):
        return []                      # a sha256 or other long hex id: never a secret
    if _PH in text:
        text = text.replace(_PH, " ")  # one character for one: places are kept
    if not _MARK.search(text):
        return _find(text)
    hits: list[tuple[int, int, str]] = []
    passes = [(_SLOT, _slot, _words), (_MARK, "", _shapes), (_MARK_SPACED, " ", _shapes)]
    if legacy:
        passes += [(_MARK, "", _words), (_MARK_SPACED, " ", _words)]
    for rx, glue, scan in passes:
        plain, src, ends = _without_marks(text, rx, glue)
        if not plain.strip(" " + _PH):
            continue
        for s, e, w in _find(plain, scan):
            if not plain[s:e].strip(" " + _PH):
                continue                # the mark itself: hidden already
            last = src[e - 1]
            # a span that ends on a mark's glue covers that whole mark
            hits.append((src[s], ends[last] if last in ends and plain[e - 1] in " " + _PH
                         else last + 1, w))
    return _merge(hits)


def _words(n: str) -> list[tuple[int, int, str]]:
    return _keyword_hits(n)


def _shapes(n: str) -> list[tuple[int, int, str]]:
    return _key_hits(n) + _house_hits(n) + _number_hits(n) + _id_hits(n)


def _everything(n: str) -> list[tuple[int, int, str]]:
    return _key_hits(n) + _keyword_hits(n) + _number_hits(n) + _id_hits(n)


def _find(text: str, scan=_everything) -> list[tuple[int, int, str]]:
    if len(text) < 3:
        return []
    n, src = _normalise(text)
    hits = scan(n)
    if not hits:
        return []
    if src is not None:
        hits = [(src[s], src[e - 1] + 1, w) for s, e, w in hits]
    return _merge(hits)


def _merge(hits: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Overlapping spans as one, the most serious name kept, in order."""
    hits = sorted(hits, key=lambda h: (h[0], -h[1]))
    merged: list[list] = []
    for s, e, w in hits:
        if merged and s < merged[-1][1]:
            m = merged[-1]
            m[1] = max(m[1], e)
            if _ORDER.index(w) < _ORDER.index(m[2]):
                m[2] = w
        else:
            merged.append([s, e, w])
    return [(s, e, w) for s, e, w in merged]


def looks_secret(text: str, legacy: bool = False) -> str | None:
    """Why this string must not leave, or None."""
    hits = find_secrets(text, legacy)
    if not hits:
        return None
    return min((w for _, _, w in hits), key=_ORDER.index)


_MARK_NAMES = re.compile(r"\[\s*hidden(?P<rest>[^\]\n]{0,200})", re.I)


def secret_signals(text) -> list[str]:
    """What a text that is only being READ (a message to check for a scam)
    carries: the secrets in it, and — for each hidden-mark in it — the kind
    of secret the mark stands for. A mark means a secret was there."""
    kinds = {w for _, _, w in find_secrets(text)} if isinstance(text, str) else set()
    if has_mark(text):
        n, _ = _normalise(text)
        for m in _MARK_NAMES.finditer(n):
            rest = m.group("rest").lower()
            kinds.add(next((w for w in _ORDER if w.lower() in rest), CODE))
    return sorted(kinds, key=_ORDER.index)


def hidden_mark(what: str) -> str:
    return f"[hidden: looks like {what}]"


def mask_text(text: str, legacy: bool = False) -> tuple[str, list[str]]:
    """The text with every secret-shaped span replaced by a plain mark, and
    what each was; what it returns is clean when scanned again. `legacy`:
    the text is a note as the store holds it, so a mark an older version let
    in is read harder (see _MARK) — on the first look only, never on
    JEFFEREY's own marks."""
    whats: list[str] = []
    for i in range(32):
        hits = find_secrets(text, legacy and i == 0)
        if not hits:
            break
        parts, last = [], 0
        for s, e, w in hits:
            parts.append(text[last:s])
            parts.append(hidden_mark(w))
            last = e
        parts.append(text[last:])
        text = "".join(parts)
        whats += [w for _, _, w in hits]
    return text, whats


def _label(k) -> str:
    return str(k).replace("_", " ")


def _is_number(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


_KEY_LABEL = re.compile(r"(?<![^\W_])(?:api|key|secret|token|bearer|credential)s?(?![^\W_])",
                        re.I)


@functools.lru_cache(maxsize=4096)
def _announces(label: str) -> bool:
    """Can a field of this name hold a secret on its own ('alarm code',
    'passport', 'sin', 'api key')? Field names repeat, so this is remembered."""
    n, _ = _normalise(label)
    return bool(_KW.search(n) or _SIN_CTX.search(n) or _SSN_CTX.search(n)
                or _CARD_CTX.search(n) or _KEY_LABEL.search(n)
                or any(rx.search(n) for rx in _ID_WORDS.values()))


def _pair_secret(k, v, alone_checked: bool = False) -> str | None:
    """A value that is only a secret beside its name: {'alarm code': '4821'}."""
    if not (isinstance(v, str) or _is_number(v)) or not _announces(_label(k)):
        return None
    if not alone_checked and looks_secret(str(v)):
        return None                     # the value alone is found where it sits
    return looks_secret(f"{_label(k)}: {v}")


def _scan(obj, where: str = "") -> tuple[str, str] | None:
    """Walk the whole value. Returns (field, what) for the first secret.
    Text and whole numbers are scanned (a card number can arrive as a JSON
    number); a value is also scanned beside its field name."""
    if isinstance(obj, str) or _is_number(obj):
        why = looks_secret(str(obj))
        return (where or "text", why) if why else None
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{where}.{k}" if where else str(k)
            why = looks_secret(str(k))
            if why:
                return (where or "a field name", why)
            hit = _scan(v, here)
            if hit:
                return hit
            why = _pair_secret(k, v, alone_checked=True)
            if why:
                return (here, why)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            hit = _scan(v, f"{where}[{i}]")
            if hit:
                return hit
    return None


def mask(obj, where: str = "") -> tuple[object, list[tuple[str, str]]]:
    """A copy of `obj` with every secret-shaped part hidden in place, and
    (where, what) for each. A field whose NAME looks like a secret is left
    out whole. What it is given is what the store holds (a tool's answer, or
    what an engine sent, for the record), so a mark an older version let in
    is read harder (legacy, see _MARK)."""
    found: list[tuple[str, str]] = []

    def go(o, w):
        if isinstance(o, str):
            m, whats = mask_text(o, legacy=True)
            found.extend((w or "text", x) for x in whats)
            return m
        if _is_number(o):
            why = looks_secret(str(o))
            if why:
                found.append((w or "a number", why))
                return hidden_mark(why)
            return o
        if isinstance(o, dict):
            out = {}
            for k, v in o.items():
                here = f"{w}.{k}" if w else str(k)
                why = looks_secret(str(k))
                if why:
                    found.append((w or "a field name", why))
                    continue
                n_before = len(found)
                masked = go(v, here)
                if len(found) == n_before:            # nothing in the value alone
                    why = _pair_secret(k, v, alone_checked=True)
                    if why:
                        found.append((here, why))
                        masked = hidden_mark(why)
                out[k] = masked
            return out
        if isinstance(o, (list, tuple)):
            return [go(v, f"{w}[{i}]") for i, v in enumerate(o)]
        return o

    return go(obj, where), found


# Parts of the store that are JEFFEREY's own bookkeeping, not the owner's words.
_NOT_WORDS = frozenset({"selfcloud_grants", "permissions", "_rev", "conscience_included"})


def stored_secrets(data: dict) -> list[dict]:
    """What is ALREADY in the owner's memories that looks like a secret —
    written before the scan knew its shape, in another language, or by hand.
    None of it goes out (release() hides it); this is so the owner can see it
    and move it into his vault with his own hands (/secrets, at his own
    terminal). Each row: where it is (`path`, for put_in_vault), what it is
    called, the words, and what it looks like."""
    rows: list[dict] = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if not path and k in _NOT_WORDS:
                    continue
                if isinstance(v, str) or _is_number(v):
                    why = looks_secret(str(v), legacy=True) or _pair_secret(k, v)
                    if why:
                        rows.append({"path": path + (k,), "section": path[0] if path else k,
                                     "field": _label(k), "words": str(v), "looks_like": why})
                else:
                    walk(v, path + (k,))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                if isinstance(v, str) and looks_secret(v, legacy=True):
                    rows.append({"path": path + (i,), "section": path[0] if path else "",
                                 "field": "", "words": v,
                                 "looks_like": looks_secret(v, legacy=True)})
                else:
                    walk(v, path + (i,))

    walk(data, ())
    return rows


def vault_name_for(row: dict) -> str:
    """A short, plain name for the vault: 'alarm_code', 'card_number' …"""
    field = re.sub(r"[^a-z0-9]+", "_", _label(row.get("field", "")).lower()).strip("_")
    if row.get("section") == "profile" and field:
        return field[:40]
    base = {CARD: "card_number", SIN: "sin", SSN: "ssn", PASSWORD: "password",
            CODE: "code", APIKEY: "api_key", BANK: "bank_account", HEALTH: "health_card",
            LICENCE: "drivers_licence", PASSPORT: "passport"}.get(row.get("looks_like"), "secret")
    n, _ = _normalise(str(row.get("words", "")))
    for word, short in (("alarm", "alarm"), ("alarme", "alarm"), ("garage", "garage"),
                        ("door", "door"), ("porte", "door"), ("gate", "gate"),
                        ("portail", "gate"), ("lockbox", "lockbox"), ("cadenas", "lockbox"),
                        ("wifi", "wifi"), ("wi-fi", "wifi"), ("bank", "bank"),
                        ("banque", "bank"), ("visa", "visa"), ("desjardins", "desjardins"),
                        ("rbc", "rbc"), ("td", "td"), ("bmo", "bmo"), ("scotia", "scotia"),
                        ("cibc", "cibc")):
        if re.search(r"(?<![^\W_])" + re.escape(word) + r"(?![^\W_])", n, re.I):
            return "visa_card" if short == "visa" else f"{short}_{base}"
    return base


def put_in_vault(data: dict, row: dict, name: str) -> str:
    """Replace, in `data`, the secret-shaped words of `row` by a reference to
    the vault entry `name` (the caller has already stored them there). A
    profile value becomes 'vault:<name>', which forms fill without anyone
    seeing it; words in a note keep everything else and say where the
    secret went. Returns the new words."""
    o = data
    for k in row["path"][:-1]:
        o = o[k]
    last = row["path"][-1]
    old = str(o[last])
    if row.get("section") == "profile" or not find_secrets(old, legacy=True):
        new = f"vault:{name}"
    else:
        hits = find_secrets(old, legacy=True)
        parts, prev = [], 0
        for s, e, _ in hits:
            parts += [old[prev:s], f"[in the vault as '{name}']"]
            prev = e
        new = "".join(parts + [old[prev:]])
    o[last] = new
    return new


def kept_home_note(found: list[tuple[str, str]]) -> str:
    """What the model is told when part of an answer stayed in the house."""
    kinds = sorted({w for _, w in found}, key=_ORDER.index)
    n = len(found)
    return (f"{n} part{'s' if n != 1 else ''} of this answer looked like "
            f"{', or '.join(kinds)}, so {'they were' if n != 1 else 'it was'} hidden "
            f"and stayed in the house; the rest is complete. Never ask anyone to read "
            f"a hidden part to you. If it came from the owner's own memories, tell him "
            f"plainly: he can move it into his vault by typing /secrets in 'Talk to "
            f"JEFFEREY on this Mac'.")


# ------------------------------------------------------------------ the door
class EgressRefused(PermissionError):
    """This result stays in the house. The message names a field, never a value."""


_SURFACE: str | None = None        # 'mcp' | 'http' | 'chat' | 'test'
_ENGINE: str | None = None         # what the owner would call the far end
_ENGINE_FROM_ENV = False           # named by a setting, not by JEFFEREY's own terminal
_ANNOUNCED_SYSTEM: str | None = None

SENT_CAP = 64 * 1024               # bytes of each send kept word for word
ASKED_CAP = 2 * 1024


def bind(surface: str, engine: str | None = None) -> None:
    """Say once, per process, which surface this is and who is on the far end."""
    global _SURFACE, _ENGINE, _ENGINE_FROM_ENV
    _SURFACE = surface
    _ENGINE = engine or os.environ.get("JEFFEREY_ENGINE")
    _ENGINE_FROM_ENV = not engine and bool(_ENGINE)
    if surface != "test":
        try:
            let_go()             # the owner's retention, if he has set one
        except OSError:
            pass


def _client() -> str:
    try:
        import access
        return access.current_client()
    except Exception:
        return "unknown"


def engine_for(client: str) -> str:
    """The far end, in the owner's words, from the key the caller holds."""
    if _ENGINE:
        return _ENGINE
    c = (client or "").lower()
    if c.startswith("claude"):
        return "Anthropic (Claude)"
    if c.startswith("gpt") or c.startswith("openai"):
        return "OpenAI (ChatGPT)"
    if c == "jefferey":
        return "the engine JEFFEREY is riding"
    if c in ("family", "executor"):
        return f"a person holding the '{c}' key"
    return "an unknown host"


def in_the_house() -> bool:
    """Is the far end a model on this very machine? (The terminal names a
    local engine '… on this machine (local — stays in the house)'.) Only
    then may the caretaker key be handed the owner's private facts in bulk
    (I-11); anywhere else they go only when a question names them.

    Only the terminal's own words count: it names the engine after checking
    the address is this machine. A name put in a setting (JEFFEREY_ENGINE in
    Claude's config) or any MCP or web connection is never 'in the house'
    (verify I-11: that setting handed every private fact to rented Claude)."""
    return (_SURFACE == "chat" and not _ENGINE_FROM_ENV and bool(_ENGINE)
            and "stays in the house" in _ENGINE)


def switch_path() -> Path:
    return home.door_switch_path()


# Folders that held the switch earlier in this process. If one disappears
# (the drive was unplugged), the switch can no longer be read: shut.
_SWITCH_SEEN: set[str] = set()


SHUT = "the owner has shut the door (JEFFEREY is offline)"
UNREACHABLE = ("the door's switch cannot be reached (the drive may have been "
               "unplugged), so the door counts as shut")


def shut_reason() -> str | None:
    """Why the door is shut, or None when it is open. Shut by the owner — or
    unreachable, which counts as shut (I-12): a switch that cannot be read is
    never taken to mean 'open'. A folder that has never existed in this
    process is a first run, not an unplugged drive.

    Since October 2026 (I-08) the door does not depend on where the life
    happens to be: it is shut if ANY known switch says so — the drive's, the
    one in the owner's own folder on this Mac, any of his drives plugged in —
    and a Self-Cloud drive that is expected but not here is a shut door too,
    with the reason in plain words."""
    if os.environ.get("JEFFEREY_OFFLINE") == "1":
        return SHUT
    away = home.problem()
    if away:
        return away
    for s in home.door_switches():
        try:
            os.lstat(s)                  # a link there counts: it was put there
            return SHUT
        except FileNotFoundError:
            pass
        except OSError:
            return UNREACHABLE           # cannot tell: treat as shut
    p = switch_path()
    try:
        os.stat(p.parent)
    except FileNotFoundError:
        gone = str(p.parent) in _SWITCH_SEEN or _drive_gone()
        return UNREACHABLE if gone else None
    except OSError:
        return UNREACHABLE
    _SWITCH_SEEN.add(str(p.parent))
    return UNREACHABLE if _drive_gone() else None


def is_shut() -> bool:
    return shut_reason() is not None


def _drive_gone() -> bool:
    """A Self-Cloud drive this process was using is no longer there."""
    try:
        r = home.root()
        return bool(r) and not os.path.isdir(r)
    except Exception:
        return False


def shut_all() -> list[Path]:
    """Shut the door everywhere it can be shut: every known switch is
    written (never through a link), so the door stays shut whichever drive
    or folder the next JEFFEREY looks in. Raises OSError if none could be."""
    done: list[Path] = []
    last: OSError | None = None
    line = f"shut by the owner {_now()}\n".encode()
    for p in home.door_switches():
        try:
            home.guard(p)
            p.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
            done.append(p)
        except OSError as e:
            if os.path.lexists(p):       # a link put there still shuts it
                done.append(p)
            else:
                last = e
    if not done:
        raise last or OSError("no switch could be written")
    return done


def shut() -> Path:
    return shut_all()[0]


def open_() -> bool:
    """Open the door: every known switch is removed (a link is removed, never
    followed). True if any was there."""
    was = False
    for p in home.door_switches():
        try:
            os.unlink(p)
            was = True
        except FileNotFoundError:
            pass
    return was


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str, sort_keys=True)


def _plain(asked):
    """Arguments as plain data, all the way down: pydantic models become
    dicts wherever they sit, so the scan sees inside them. (An HTTP endpoint
    receives its body as a model inside the kwargs dict — a first version
    scanned only the outer dict and missed a card number in the body.)"""
    if hasattr(asked, "model_dump"):
        asked = asked.model_dump()
    if isinstance(asked, dict):
        return {k: _plain(v) for k, v in asked.items()}
    if isinstance(asked, (list, tuple)):
        return [_plain(a) for a in asked]
    return asked


def fingerprint(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _describe(asked, tool: str | None = None) -> str:
    """The arguments, for the log's 'why' — capped, and never a secret's
    home: anything in what the engine sent that looks like a secret is
    written down as "[hidden: looks like …]", never as itself. What it asked
    to forget is kept as a fingerprint."""
    if asked is None:
        return ""
    asked = _plain(asked)
    if tool in FINGERPRINT_ARGS and isinstance(asked, dict):
        asked = dict(asked)
        for k in FINGERPRINT_ARGS[tool]:
            if isinstance(asked.get(k), str) and asked[k]:
                asked[k] = f"[not written down; {fingerprint(asked[k])}]"
    if isinstance(asked, dict):
        asked = _hide_labelled(asked)
    asked, _ = mask(asked)
    try:
        s = _dumps(asked)
    except Exception:
        s = str(asked)
    return s if len(s) <= ASKED_CAP else s[:ASKED_CAP] + "…"


# Set by representative.py when it loads (it imports this module, so not the
# other way round): does a form's or the profile's label ask for a kind of
# detail that is never kept (a passport, a login, a maiden name)?
LABEL_IS_SENSITIVE = None


def _hide_labelled(asked: dict) -> dict:
    """A value handed in under a label of its own ({'field': 'passport',
    'value': 'AB123456'}) is judged beside that label, not beside the word
    'value' — so a value refused for its label is never written down in the
    record either (verify I-07, I-58: 'bank login' 'laszlo / Hunter22!',
    'alarm code' '4821' and 'passport' 'AB123456' were each refused, then
    written word for word in the record, twice)."""
    label = next((asked[k] for k in ("field", "label", "name", "box")
                  if isinstance(asked.get(k), str) and asked[k].strip()), None)
    if label is None or "value" not in asked:
        return asked
    v = asked["value"]
    if not (isinstance(v, str) or _is_number(v)) or not str(v).strip():
        return asked
    hidden = bool(_pair_secret(label, v) or looks_secret(f"{label}: {v}"))
    if not hidden and LABEL_IS_SENSITIVE is not None:
        try:
            hidden = bool(LABEL_IS_SENSITIVE(label))
        except Exception:
            hidden = False
    if hidden:
        asked = dict(asked)
        asked["value"] = f"[not written down: a kind of detail never kept; {fingerprint(str(v))}]"
    return asked


# ------------------------------------------------------------------- the log
def log_path() -> Path:
    return home.egress_path()


class _Locked:
    """The log's own lock, so the owner's erasure (which rewrites the file)
    never loses a line another engine appends at the same moment."""

    def __init__(self, p: Path):
        self.path, self.fd = p.with_name(p.name + ".lock"), None

    def __enter__(self):
        if fcntl is None:
            return self
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT
                              | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except OSError:
            self.fd = None
            return self
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None
        return False


class LogUnwritable(OSError):
    """The record of what left the house could not be written whole."""


def _write(entry: dict) -> None:
    """Append one line, fsynced, before anything leaves. A log that cannot be
    written is a door that cannot be opened.

    Written whole or not at all (I-67): os.write may take only part of the
    line on a full drive, so it is called until every byte is down; if the
    drive refuses the rest, the file is cut back to where it was and the send
    is refused. A file that does not end in a line break (a power cut tore
    its last line) gets one first, so a torn line never swallows this one."""
    p = log_path()
    if not os.environ.get("JEFFEREY_EGRESS") and home.problem():
        # The log lives on a drive that is away (or not the owner's): nothing
        # is written anywhere else — a refusal note on a stranger's stick, or
        # a shadow log on the laptop, is a copy of the owner's words (I-08).
        raise LogUnwritable(19, "the Self-Cloud drive is not available")
    home.guard(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    entry.setdefault("v", __version__)
    line = (_dumps(entry) + "\n").encode()
    flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    with _Locked(p):
        fd = os.open(p, flags, 0o600)
        try:
            size = os.fstat(fd).st_size
            if size and os.pread(fd, 1, size - 1) != b"\n":
                line = b"\n" + line
            try:
                view = memoryview(line)
                while view:
                    n = os.write(fd, view)
                    if n <= 0:
                        raise LogUnwritable(28, "the drive took no more")   # ENOSPC
                    view = view[n:]
                os.fsync(fd)
            except BaseException:
                try:
                    os.ftruncate(fd, size)
                    os.fsync(fd)
                except OSError:
                    pass
                raise
        finally:
            os.close(fd)


NOT_LOGGED = ("JEFFEREY could not write it down in the record of what left the "
              "house (the drive may be full, unplugged or read-only), so nothing "
              "was sent. Tell the owner plainly")


def _write_or_refuse(entry: dict) -> None:
    """The last step before a send: written whole, or the send is refused."""
    try:
        _write(entry)
    except OSError:
        raise EgressRefused(f"withheld by the egress door: {NOT_LOGGED}.") from None


# ------------------------------------------------------------- erasure
# The one exception to "append-only": the OWNER erasing words for good
# (forgetting.erase, from his own console — never an engine). Each entry that
# held them stays in the log as a dated tombstone: when, to whom, which tool,
# how many bytes and the sha256 of what was sent. Only the words go.
def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


_ESC = re.compile(r"\\(u[0-9a-fA-F]{4}|.)", re.S)
_ESC_CHAR = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}


def _unescape(s: str) -> str:
    """A record cut off at its size limit is no longer whole JSON, so it is
    read as text — with its escapes turned back into what they stand for.
    Read raw, a name at the start of a line sat right after the letter 'n' of
    '\\n' and was never found as a whole word (verify I-16: 'erase Karen'
    said done while 'Karen made coffee' stayed in the record)."""
    def one(m):
        x = m.group(1)
        if x.startswith("u") and len(x) == 5:
            try:
                return chr(int(x[1:], 16))
            except ValueError:
                return m.group(0)
        return _ESC_CHAR.get(x, x)
    return _ESC.sub(one, s)


def _text_hits(s, match) -> bool:
    if not isinstance(s, str) or not s:
        return False
    try:
        obj = json.loads(s)
    except ValueError:
        return bool(match(s)) or bool(match(_unescape(s)))
    return any(match(x) for x in _strings(obj))


def _hits(e: dict, match) -> tuple[bool, bool]:
    return _text_hits(e.get("sent"), match), _text_hits(e.get("asked"), match)


def matching(match) -> dict:
    """How many entries hold what `match` finds, and where they went.
    Reads only."""
    out = {"entries": 0, "engines": Counter(), "first": None, "last": None}
    for e in all_entries():
        hs, ha = _hits(e, match)
        if hs or ha:
            out["entries"] += 1
            out["engines"][e.get("engine") or "?"] += 1
            t = e.get("t")
            if t:
                out["first"] = min(out["first"] or t, t)
                out["last"] = max(out["last"] or t, t)
    return out


def _rewrite(change) -> dict:
    """Rewrite every known log (the drive's, and one left on this Mac from a
    time JEFFEREY ran without the drive — I-08), each under its lock and
    atomically. `change(entry)` returns True if it changed the entry in
    place. A torn line `change` is asked about as {"torn": text}; True drops
    it. Returns how many."""
    out = {"entries": 0, "torn_lines_dropped": 0}
    for p in home.egress_logs():
        one = _rewrite_one(p, change)
        out["entries"] += one["entries"]
        out["torn_lines_dropped"] += one["torn_lines_dropped"]
    return out


def _rewrite_one(p: Path, change) -> dict:
    out = {"entries": 0, "torn_lines_dropped": 0}
    if not p.exists() or os.path.islink(p):
        return out
    with _Locked(p):
        lines = []
        for line in p.read_bytes().splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except ValueError:
                if change({"torn": line.decode("utf-8", "replace")}):
                    out["torn_lines_dropped"] += 1
                    continue
                lines.append(line)
                continue
            if isinstance(e, dict) and change(e):
                out["entries"] += 1
                line = _dumps(e).encode("utf-8")
            lines.append(line)
        if not (out["entries"] or out["torn_lines_dropped"]):
            return out
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.", suffix=".tmp")
        try:
            try:
                view = memoryview(b"\n".join(lines) + (b"\n" if lines else b""))
                while view:
                    view = view[os.write(fd, view):]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp, p)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        try:
            dfd = os.open(p.parent, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
    return out


def _tombstone(e: dict, sent: bool, asked: bool, words: str, mark: str, when: str) -> None:
    if sent and e.get("sent") is not None:
        e["sent"] = f"[{words} — the sha256 of what was sent is kept]"
    if asked and e.get("asked"):
        e["asked_sha256"] = hashlib.sha256(str(e["asked"]).encode("utf-8")).hexdigest()
        e["asked"] = f"[{words}]"
    e[mark] = when


def redact(match, when: str) -> dict:
    """OWNER ONLY. Every entry whose 'sent' or 'asked' holds what `match`
    finds becomes a tombstone; a torn line that holds it is dropped."""
    def change(e):
        if "torn" in e:
            return bool(match(e["torn"]))
        hs, ha = _hits(e, match)
        if hs or ha:
            _tombstone(e, hs, ha, f"erased by the owner on {when}", "erased", when)
            return True
        return False
    return _rewrite(change)


# How long the word-for-word record is kept: the owner's choice, and off
# until he makes it (`python connector/egress.py keep 90`). Older entries
# keep their date, destination, tool, size and fingerprint; their words go.
def _keep_path() -> Path:
    p = log_path()
    return p.with_name(p.name + ".keep")


def keep_days() -> int | None:
    raw = os.environ.get("JEFFEREY_EGRESS_KEEP_DAYS")
    if raw is None:
        try:
            raw = _keep_path().read_text().strip()
        except OSError:
            return None
    try:
        n = int(str(raw).strip())
    except ValueError:
        return None
    return n if n > 0 else None


def set_keep(days: int | None) -> None:
    p = _keep_path()
    if not days:
        p.unlink(missing_ok=True)
        return
    home.guard(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
                 0o600)
    try:
        os.write(fd, f"{int(days)}\n".encode())
    finally:
        os.close(fd)


def let_go(days: int | None = None) -> dict:
    """Keep the words of each send for `days` (the owner's setting) and no
    longer. Each older entry stays as a dated line with its fingerprint."""
    days = days if days is not None else keep_days()
    if not days:
        return {"entries": 0, "torn_lines_dropped": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = datetime.now().strftime("%d %B %Y").lstrip("0")

    def change(e):
        if "torn" in e or e.get("let_go") or e.get("erased"):
            return False
        if str(e.get("t", "")) >= cutoff:
            return False
        if e.get("sent") is None and not e.get("asked"):
            return False
        _tombstone(e, True, True, f"let go after {days} days, on {today}", "let_go", today)
        return True
    return _rewrite(change)


def _entry(kind: str, *, tool: str | None, sent: str | None, asked: str,
           withheld: list[str], refused: str | None) -> dict:
    client = _client()
    raw = sent.encode() if sent is not None else b""
    e = {
        "t": _now(),
        "surface": _SURFACE or "unbound",
        "to": client,
        "engine": engine_for(client),
        "kind": kind,
        "tool": tool,
        "asked": asked,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest() if sent is not None else None,
        "sent": (sent if len(raw) <= SENT_CAP else sent[:SENT_CAP]) if sent is not None else None,
        "truncated": bool(sent is not None and len(raw) > SENT_CAP),
        "withheld": withheld,
        "refused": refused,
    }
    return e


def _refuse(kind: str, tool: str | None, asked, reason: str) -> EgressRefused:
    """A refusal: written down if the log can be written; refused either way."""
    try:
        _write(_entry(kind, tool=tool, sent=None, asked=_describe(asked, tool),
                      withheld=[], refused=reason))
    except OSError:
        pass
    return EgressRefused(
        f"withheld by the egress door: {reason}. Nothing from this result left "
        f"the house. Tell the owner plainly; do not ask them to read it to you "
        f"another way. They can see what and why in 'What left the house'.")


def _filter(tool: str, out):
    """Apply the allowlist. Returns (filtered, withheld_field_names)."""
    allowed = RELEASE[tool]
    if isinstance(out, str):
        if TEXT in allowed:
            return out, []
        raise ValueError("bare text is not on this tool's allowlist")
    if ANY in allowed:
        return out, []
    keep = allowed | COMMON

    def one(d: dict) -> tuple[dict, list[str]]:
        kept = {k: v for k, v in d.items() if k in keep}
        return kept, sorted(k for k in d if k not in keep)

    if isinstance(out, dict):
        return one(out)
    if isinstance(out, list):
        items, withheld = [], set()
        for it in out:
            if isinstance(it, dict):
                k, w = one(it)
                items.append(k)
                withheld.update(w)
            else:
                items.append(it)
        return items, sorted(withheld)
    # ints/bools/None: nothing in them to filter
    return out, []


# No single answer may be bigger than this (I-41): at 5,000 facts and 500
# memories who_am_i was a million characters, far past what any engine can
# read in one turn — and a local model quietly cuts off the start, which is
# where JEFFEREY's own rules are. The tools page their answers; this is the
# backstop for anything that still grows too long.
RESULT_BUDGET = 96 * 1024


def _size(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"))


def fit(out, budget: int = RESULT_BUDGET):
    """Make a result fit the budget by leaving off the END of its longest
    lists (most relevant first, so the end matters least), then shortening
    any very long text. Returns (result, [what was cut]). A result that fits
    is returned untouched."""
    if _size(out) <= budget:
        return out, []
    cut: dict[str, int] = {}
    if isinstance(out, list):
        items = list(out)
        while items and _size(items) > budget:
            drop = max(1, len(items) // 4)
            del items[-drop:]
            cut["the list"] = cut.get("the list", 0) + drop
        return items, [f"{n} items of {k}" for k, n in cut.items()]
    if not isinstance(out, dict):
        return out, []
    res = dict(out)
    for _ in range(200):
        if _size(res) <= budget:
            break
        lists = [(k, v) for k, v in res.items() if isinstance(v, list) and v]
        if lists:
            k, v = max(lists, key=lambda kv: _size(kv[1]))
            drop = max(1, len(v) // 4)
            res[k] = v[:-drop]
            cut[k] = cut.get(k, 0) + drop
            continue
        texts = [(k, v) for k, v in res.items() if isinstance(v, str) and len(v) > 2000]
        if not texts:
            break
        k, v = max(texts, key=lambda kv: len(kv[1]))
        res[k] = v[: max(2000, len(v) // 2)] + " …"
        cut[k] = cut.get(k, 0)
    res["trimmed"] = {
        "left_off": {k: n for k, n in cut.items() if n},
        "why": ("This answer was too long for one turn, so the end of it was left off. "
                "Ask again with a smaller limit or a later offset, or ask about one "
                "subject at a time."),
    }
    return res, [f"{n} items of {k}" if n else f"the end of {k}" for k, n in cut.items()]


def admit(tool: str, asked) -> None:
    """The other direction of the same door: what the engine HANDS IN.

    A rented engine may not put a secret into the conscience. If it did, the
    value would sit in the owner's memories and go out again to every engine
    that reads them. So for a tool that keeps what it is given, the scan runs
    on the arguments *before* the tool runs, and a hit means nothing is
    written. Secrets go in the vault, by the owner's own hands, never through
    an engine.

    A tool that only reads what it is given (READS_ONLY) is not refused: it
    answers, and the record of the call hides the secret-shaped words (I-14).
    Refusing there protected nothing — the engine already holds the text —
    and it switched off the scam check on exactly the messages that quote a
    card, a SIN, a code or a password."""
    if asked is None or tool in READS_ONLY:
        return
    plain = _plain(asked)
    marked = _marked(plain)
    if marked is not None:
        try:
            _write(_entry("tool_call", tool=tool, sent=None,
                          asked=_describe(_unmarked(plain), tool), withheld=[],
                          refused=f"the engine handed in text with a hidden-mark in it "
                                  f"('{marked}'); not taken"))
        except OSError:
            pass
        raise EgressRefused(
            f"refused at the door: '{marked}' in what you sent — {MARK_REFUSAL}, so "
            f"nothing was stored. A mark like '[hidden …]' is where JEFFEREY kept "
            f"something back; write it again in plain words with the hidden part left "
            f"out. Never ask the owner to read out what was hidden. If it is a password, "
            f"a PIN or a code he wants kept, he puts it in his vault himself, at his own "
            f"keyboard (python connector/vault.py set <name>).")
    hit = _scan(plain)
    if hit:
        field, what = hit
        try:
            _write(_entry("tool_call", tool=tool, sent=None, asked=_describe(asked, tool),
                          withheld=[], refused=f"the engine handed in what looks like "
                                              f"{what} in '{field}'; not taken"))
        except OSError:
            pass
        raise EgressRefused(
            f"refused at the door: '{field}' in what you sent looks like {what}. "
            f"JEFFEREY never keeps passwords, PINs, house codes, or card or ID numbers "
            f"in the owner's memories, so nothing was stored. If he wants it kept, it "
            f"belongs in his vault: he stores it himself, at his own keyboard "
            f"(python connector/vault.py set <name>), and you then use 'vault:<name>' "
            f"without ever seeing it.")


def _marked(obj, where: str = "") -> str | None:
    """The first field of what an engine sent that holds a hidden-mark, or
    None."""
    if isinstance(obj, str):
        return (where or "text") if has_mark(obj) else None
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{where}.{k}" if where else str(k)
            if has_mark(str(k)):
                return where or "a field name"
            hit = _marked(v, here)
            if hit:
                return hit
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            hit = _marked(v, f"{where}[{i}]")
            if hit:
                return hit
    return None


def _unmarked(obj):
    """What an engine sent, for the record, with every text that held a
    hidden-mark left out (kept only as a fingerprint)."""
    if isinstance(obj, str):
        return f"[not written down: it held a hidden-mark; {fingerprint(obj)}]" \
            if has_mark(obj) else obj
    if isinstance(obj, dict):
        return {("[a field name]" if has_mark(str(k)) else k): _unmarked(v)
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_unmarked(v) for v in obj]
    return obj


def _writes() -> frozenset:
    try:
        import access
        return access.WRITE_TOOLS
    except Exception:
        return frozenset()


def _refused_before(tool: str, asked, reason: str) -> EgressRefused:
    """A refusal BEFORE the tool ran: nothing was done. Written down if the
    log can be written; refused either way."""
    try:
        _write(_entry("tool_call", tool=tool, sent=None, asked=_describe(asked, tool),
                      withheld=[], refused=reason + "; nothing was done"))
    except OSError:
        pass
    return EgressRefused(
        f"refused at the door: {reason}. Nothing was done and nothing left the "
        f"house. Tell the owner plainly, and do not try another way.")


def check_open(tool: str, asked=None) -> None:
    """Is this process allowed to run anything at all? A bound surface and an
    open door — checked before a tool does anything (I-12: with the door
    shut, deletions, stories and revocations still happened while the engine
    and the log were told 'refused')."""
    if _SURFACE is None:
        raise _refused_before(tool, asked, "no surface is bound to this process")
    why = shut_reason()
    if why:
        raise _refused_before(tool, asked, why)


def before(tool: str, asked=None, check: bool = True) -> None:
    """Everything that must happen BEFORE a tool runs, in order: the door is
    open; what the engine hands in holds no secret; and, for a tool that
    changes something, a line in the log saying it was asked for — written
    first, so a log that cannot be written stops the change instead of
    letting it land unrecorded."""
    if check:
        check_open(tool, asked)
    admit(tool, asked)
    if tool in _writes():
        try:
            _write(_entry("intent", tool=tool, sent=None, asked=_describe(asked, tool),
                          withheld=[], refused=None))
        except OSError:
            raise EgressRefused(
                "JEFFEREY could not write down this request in the record of what "
                "left the house (the drive may be full, unplugged or read-only), so "
                "nothing was done. Tell the owner plainly.") from None


def release(tool: str, out, asked=None):
    """A tool result is about to go to the engine. Return what may go.

    Order matters: shut? → known tool? → allowlist → secret scan → log → go.
    Anything in the result that looks like a secret is hidden in place
    ("[hidden: looks like a card number]") and the answer says plainly that
    part of it stayed home — one secret-shaped line no longer blacks out
    'who am I' or the whole profile for good (I-15). Every refusal is logged
    too, with the reason and never the value."""
    if _SURFACE is None:
        raise _refuse("tool_result", tool, asked,
                      "no surface is bound to this process, so nothing leaves it")
    why = shut_reason()
    if why:
        raise _refuse("tool_result", tool, asked, why)
    if tool not in RELEASE:
        raise _refuse("tool_result", tool, asked,
                      f"'{tool}' has no entry in the release list — nothing "
                      f"from it may leave until the owner's code names what may")
    try:
        kept, withheld = _filter(tool, out)
    except ValueError as e:
        raise _refuse("tool_result", tool, asked, str(e))
    kept, found = mask(kept)
    if found:
        hit = _scan(kept)
        if hit:                       # hiding did not clear it: nothing goes
            raise _refuse("tool_result", tool, asked,
                          f"'{hit[0]}' contains what looks like {hit[1]}")
        if isinstance(kept, dict):
            kept["kept_home"] = kept_home_note(found)
        withheld = list(withheld) + [f"{where} (hidden: looked like {what})"
                                     for where, what in found]
    kept, cut = fit(kept)
    if cut:
        withheld = list(withheld) + [f"{where} (left off: too long for one answer)"
                                     for where in cut]
    _write_or_refuse(_entry("tool_result", tool=tool, sent=_dumps(kept),
                            asked=_describe(asked, tool), withheld=withheld,
                            refused=None))
    return kept


def release_text(kind: str, text: str, why: str = "", hide: bool = False) -> str:
    """Text the owner's own terminal is about to send: the system prompt, or
    what they typed. Same door, same scan, same log.

    What the owner TYPED with a secret in it stays home whole (he is told,
    on his own screen). Text JEFFEREY assembled — the system prompt, with
    the live conscience in it — is sent with any secret-shaped words hidden
    (`hide=True`), so one old note with a door code in it does not silence
    the whole conversation."""
    if _SURFACE is None:
        raise _refuse(kind, None, why, "no surface is bound to this process")
    shut_why = shut_reason()
    if shut_why:
        raise _refuse(kind, None, why, shut_why)
    withheld: list[str] = []
    if hide:
        text, whats = mask_text(text)
        withheld = [f"hidden: looked like {w}" for w in whats]
    what = looks_secret(text)
    if what:
        raise _refuse(kind, None, why, f"it contains what looks like {what}")
    _write_or_refuse(_entry(kind, tool=None, sent=text, asked=why, withheld=withheld,
                            refused=None))
    return text


def request(payload: dict, model: str) -> dict:
    """The owner's terminal is about to make one call to the engine. Every
    part of the payload has already been released piece by piece (system
    prompt, what they typed, each tool result); this writes the receipt for
    the call itself — its exact size and hash — and is the last thing that
    runs before the bytes go."""
    if _SURFACE is None:
        raise _refuse("request", None, model, "no surface is bound to this process")
    shut_why = shut_reason()
    if shut_why:
        raise _refuse("request", None, model, shut_why)
    raw = _dumps(payload).encode()
    _write_or_refuse({
        "t": _now(), "surface": _SURFACE, "to": _client(),
        "engine": _ENGINE or model, "kind": "request", "tool": None,
        "asked": f"model={model} messages={len(payload.get('messages', []))}",
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "sent": None, "truncated": False, "withheld": [], "refused": None,
    })
    return payload


_SYSTEM_SENT: str | None = None     # what went out for _ANNOUNCED_SYSTEM


def system_prompt_once(text: str) -> str:
    """The system prompt is logged whenever it changes, not every turn, and
    marked as logged only once the log has it whole (I-67). Returns what may
    be sent: the prompt with any secret-shaped words hidden."""
    global _ANNOUNCED_SYSTEM, _SYSTEM_SENT
    h = hashlib.sha256(text.encode()).hexdigest()
    if h != _ANNOUNCED_SYSTEM or _SYSTEM_SENT is None:
        sent = release_text("system_prompt", text, hide=True,
                            why="the directives plus the live conscience")
        _ANNOUNCED_SYSTEM, _SYSTEM_SENT = h, sent
    return _SYSTEM_SENT


def refusal_result(tool: str, e: EgressRefused) -> dict:
    """A refusal as a RESULT the model must report — for surfaces whose SDK
    would otherwise swallow the reason (the MCP SDK reduces any exception to
    'Error executing tool <name>')."""
    return {"refused": True, "tool": tool, "reason": str(e),
            "tell_the_user": "Tell the owner in a sentence, in plain words, what the "
                             "reason says. Never ask him to read a secret to you, "
                             "spell it or split it up, and do not try another way "
                             "around the door."}


def _access_errors() -> tuple:
    try:
        import access
        return (access.AccessDenied, access.OwnerOnly)
    except Exception:
        return ()


def note_refusal(tool: str, asked, reason: str) -> None:
    """A refusal JEFFEREY gave instead of running a tool, written down."""
    try:
        _write(_entry("tool_call", tool=tool, sent=None, asked=_describe(asked, tool),
                      withheld=[], refused=reason))
    except OSError:
        pass


def note_secret_use(tool: str, uses: list[dict], where: str) -> None:
    """A secret from the owner's vault is about to be written into a file
    on his own disk (fill_pdf). Nothing leaves the house — but every use is
    written down first, by the secret's NAME and the box it goes into, never
    its value, and the owner sees it in 'What left the house' (I-02). Raises
    OSError when the log cannot be written: then nothing is filled."""
    asked = "; ".join(f"vault:{u.get('secret')} into the box '{u.get('field')}'"
                      for u in uses)
    words, _ = mask_text(f"{asked} — in a filled copy of '{where}', saved in the "
                         f"'Filled forms' folder")
    _write(_entry("secret_used", tool=tool, sent=None, asked=words[:ASKED_CAP],
                  withheld=[], refused=None))


def access_refusal(tool: str, asked, e: Exception) -> dict:
    """The access gate said no. Written down, and — for a surface whose SDK
    would reduce it to 'Error executing tool' — turned into a result the
    model must report (I-64)."""
    note_refusal(tool, asked, f"the key does not allow it: {e}")
    try:
        import access
        return access.refusal(tool, e)
    except Exception:
        return {"refused": True, "tool": tool, "reason": str(e)}


def through(fn, name: str | None = None, as_result: bool = False):
    """Wrap a tool function so the door is checked and what goes in is
    admitted BEFORE it runs, and what comes out is released. `as_result=True`
    turns a refusal — the door's or the key's — into a result dict instead of
    an exception (see refusal_result)."""
    tool = name or fn.__name__

    @functools.wraps(fn)
    def inner(*args, **kwargs):
        asked = kwargs if kwargs else (args[0] if len(args) == 1 else list(args))
        try:
            before(tool, asked)
            out = fn(*args, **kwargs)
            return release(tool, out, asked=asked)
        except EgressRefused as e:
            if as_result:
                return refusal_result(tool, e)
            raise
        except Exception as e:
            denied = _access_errors()
            if denied and isinstance(e, denied):
                r = access_refusal(tool, asked, e)
                if as_result:
                    return r
            raise

    inner.__jefferey_egress__ = tool
    return inner


def door(register, as_result: bool = False):
    """Compose a surface's own registration with the door:

        @door(mcp.tool())                    @door(app.get("/life"))
        @gate("life.read")                   @gate("life.read")
        def who_am_i() -> dict: ...          def who_am_i() -> dict: ...

    The surface registers the *wrapped* function, so there is no path from a
    registered tool to the engine that skips `admit()` and `release()`."""
    def wrap(fn):
        return register(through(fn, as_result=as_result))
    return wrap


# ---------------------------------------------------------------- the report
def _read_log(p: Path, since: datetime | None = None) -> list[dict]:
    try:
        f = open(p, "rb")
    except OSError:
        return []
    out = []
    with f:
        for line in f:
            e = _parse_line(line)
            if e is None:
                continue          # a torn line from a power cut or a full drive
            if since and e.get("t", "") < since.strftime("%Y-%m-%dT%H:%M:%SZ"):
                continue
            out.append(e)
    return out


def entries(since: datetime | None = None) -> list[dict]:
    """The log in use right now."""
    p = log_path()
    if not p.exists():
        return []
    return _read_log(p, since)


def all_entries(since: datetime | None = None) -> list[dict]:
    """Every known log, oldest first, each entry marked with where its log
    lives ('_where': 'drive' or 'mac'). Before October 2026 the report read
    only the log of wherever the life was that moment, so sends written on
    the laptop while the drive was away never appeared (I-08)."""
    out = []
    for p in home.egress_logs():
        w = home.where_of(p)
        for e in _read_log(p, since):
            e["_where"] = w
            out.append(e)
    out.sort(key=lambda e: str(e.get("t", "")))
    return out


def _parse_line(line: bytes) -> dict | None:
    """One entry. A line that a torn write ran into the next one (a log
    written before every line was made to start fresh) still gives up the
    whole entry at its end, so one torn line never hides its neighbour."""
    try:
        e = json.loads(line)
        return e if isinstance(e, dict) else None
    except ValueError:
        pass
    i = line.find(b'{"', 1)
    while i != -1:
        try:
            e = json.loads(line[i:])
            return e if isinstance(e, dict) else None
        except ValueError:
            i = line.find(b'{"', i + 1)
    return None


def _kb(n: int) -> str:
    return f"{n/1024:.1f} KB" if n >= 1024 else f"{n} B"


def summary(days: int = 7) -> dict:
    """Counts and destinations — safe to hand to the engine itself."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    es = all_entries(since)
    by: dict[tuple[str, str, str], dict] = {}
    refused = 0
    secrets_used = 0
    for e in es:
        if e.get("kind") == "intent":
            continue          # written before a change ran; nothing was sent
        if e.get("kind") == "secret_used":
            secrets_used += 1  # into a file on this computer; nothing was sent
            continue
        if e.get("refused"):
            refused += 1
            continue
        k = (e.get("surface", "?"), e.get("to", "?"), e.get("engine", "?"))
        d = by.setdefault(k, {"surface": k[0], "key": k[1], "engine": k[2],
                              "sends": 0, "bytes": 0, "tools": {}})
        d["sends"] += 1
        d["bytes"] += int(e.get("bytes") or 0)
        t = e.get("tool") or e.get("kind")
        d["tools"][t] = d["tools"].get(t, 0) + 1
    dest = []
    for d in by.values():
        d["tools"] = dict(sorted(d["tools"].items(), key=lambda kv: -kv[1]))
        dest.append(d)
    return {
        "since": since.strftime("%Y-%m-%d"),
        "sends": sum(d["sends"] for d in dest),
        "refused": refused,
        "by_destination": dest,
        "secrets_used_on_forms": secrets_used,
        "door": "shut" if is_shut() else "open",
        "log_lives": home.describe_for_engine(),
        "version": __version__,
        "to_see_everything": "double-click 'What left the house.command' — the "
                             "owner reads every send word for word, there",
    }


def report(days: int | None = 7, full: bool = False) -> str:
    """The owner's readable answer to 'what left the house?'"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)) if days else None
    es = all_entries(since)
    span = f"the last {days} days" if days else "all time"
    why = shut_reason()
    here = home.locate().ok
    lines = [f"WHAT LEFT THE HOUSE — {span}   (JEFFEREY {__version__})",
             f"  the door is {'SHUT' if why else 'open'}"
             + (f" · the log lives {home.describe()}" if here else "")]
    if why and why not in (SHUT, UNREACHABLE):
        lines.append(f"  JEFFEREY is off right now: {why}.")
    if not here:
        lines.append("  The record of what left the house lives on your Self-Cloud drive. Plug "
                     "it in to see all of it; below is only what is kept on this Mac.")
    logs = home.egress_logs()
    if any(home.where_of(p) == "mac" for p in logs) and any(
            home.where_of(p) == "drive" for p in logs):
        mac = sum(1 for e in es if e.get("_where") == "mac")
        lines.append(f"  ! {mac} of these were written down on this Mac's own disk, not on your "
                     f"drive — from a time JEFFEREY ran without the drive. They are shown "
                     f"here too, marked 'on this Mac'.")
    enc = home.encryption_line()
    if enc:
        lines.append(f"  {enc}")
    lines.append("")
    if not es:
        lines.append("  Nothing. No send has been made through the door" +
                     (" in this period." if days else " yet."))
        return "\n".join(lines)
    s = summary(days or 36500)
    for d in s["by_destination"]:
        lines.append(f"  → {d['engine']}  (via {d['surface']}, key '{d['key']}'): "
                     f"{d['sends']} sends, {_kb(d['bytes'])}")
        for t, n in list(d["tools"].items())[:12]:
            lines.append(f"       {t} ×{n}")
    used = [e for e in es if e.get("kind") == "secret_used"]
    if used:
        lines.append("")
        lines.append(f"  🔑 secrets from your vault written onto forms on this computer: "
                     f"{len(used)} (none of them was sent anywhere):")
        for e in used:
            lines.append(f"       {e['t']}  {e.get('asked')}")
    if s["refused"]:
        lines.append("")
        lines.append(f"  ✋ refused: {s['refused']} — kept home, with the reason:")
        for e in es:
            if e.get("refused"):
                lines.append(f"       {e['t']}  {e.get('tool') or e.get('kind')}: {e['refused']}")
    lines.append("")
    lines.append(f"  {len(es)} entries. Each one is in the log word for word.")
    if full:
        lines.append("")
        lines.append("EVERY SEND, WORD FOR WORD")
        for e in es:
            if e.get("kind") in ("secret_used", "intent"):
                # written down here, sent nowhere (verify I-02: it read
                # '→ the engine JEFFEREY is riding (0 B)')
                where = ("a secret from your vault, written onto a form on this computer — "
                         "sent nowhere" if e.get("kind") == "secret_used" else
                         "written down before a change ran — sent nowhere")
                head = f"{e['t']}  {e.get('kind')}  {e.get('tool') or ''}  ({where})"
            else:
                head = (f"{e['t']}  {e.get('kind')}  {e.get('tool') or ''}  → {e.get('engine')} "
                        f"({_kb(int(e.get('bytes') or 0))})")
            head += ("   [on this Mac]" if e.get("_where") == "mac" and len(logs) > 1 else "")
            lines.append("")
            lines.append(head)
            if e.get("asked"):
                lines.append(f"  asked: {e['asked']}")
            if e.get("withheld"):
                lines.append(f"  withheld fields: {', '.join(e['withheld'])}")
            if e.get("refused"):
                lines.append(f"  REFUSED: {e['refused']}")
            elif e.get("sent") is not None:
                body = e["sent"]
                lines.append("  sent: " + body.replace("\n", "\n        ")
                             + ("  […truncated in the log]" if e.get("truncated") else ""))
    return "\n".join(lines)


# ------------------------------------------------------------------ selftest
def selftest() -> int:
    import tempfile
    td = Path(tempfile.mkdtemp(prefix="egress-"))
    os.environ["JEFFEREY_EGRESS"] = str(td / "egress.jsonl")
    os.environ["JEFFEREY_DOOR"] = str(td / "door-shut")
    os.environ.pop("JEFFEREY_OFFLINE", None)
    home.reset_for_tests()

    def refused(fn, *a, **k) -> str:
        try:
            fn(*a, **k)
        except EgressRefused as e:
            return str(e)
        raise AssertionError("was not refused: " + repr((fn.__name__, a, k)))

    # 1. Unbound process: nothing leaves, and the refusal is logged.
    global _SURFACE, _ENGINE, _ANNOUNCED_SYSTEM
    _SURFACE = _ENGINE = _ANNOUNCED_SYSTEM = None
    assert "no surface" in refused(release, "orb_state", {"mood": "calm"})
    assert entries()[-1]["refused"] and entries()[-1]["sent"] is None
    print("  ✓ an unbound process releases nothing")

    bind("test", engine="a test engine")

    # 2. Unknown tool: fails closed.
    msg = refused(release, "brand_new_tool", {"anything": 1})
    assert "no entry in the release list" in msg
    print("  ✓ a tool with no allowlist entry releases nothing")

    # 3. Allowlist: unlisted fields are withheld and named; values never appear.
    out = release("get_conscience", {"owner": "L", "facts": [], "priorities": [],
                                     "active_goals": [], "corrections_learned_from": 0,
                                     "store_path": "/Volumes/Self-Cloud/.selfcloud/x"})
    assert "store_path" not in out and out["owner"] == "L"
    last = entries()[-1]
    assert last["withheld"] == ["store_path"] and "/Volumes" not in last["sent"]
    print("  ✓ allowlist withholds unlisted fields and logs their names only")

    # 4. Lists filter per item.
    out = release("priorities_for", [{"context": "travel", "higher": "a", "lower": "b",
                                      "confidence": 0.7, "evidence": 1, "updated": "",
                                      "secret_note": "x"}])
    assert out == [{"context": "travel", "higher": "a", "lower": "b",
                    "confidence": 0.7, "evidence": 1, "updated": ""}]
    print("  ✓ list results filter every item")

    # 5. Bare text only where allowed.
    assert release("get_directives", "be kind") == "be kind"
    assert "bare text" in refused(release, "orb_state", "calm")
    print("  ✓ bare text leaves only for tools that return text")

    # 6. The hard scan: a secret anywhere in a result is hidden in place —
    #    the value is in neither the result nor the log, the rest goes, and
    #    the answer says plainly that part of it stayed home. (Until October
    #    2026 a hit refused the WHOLE result, so one secret-shaped line — or a
    #    photo fingerprint that happened to look like a SIN — blacked out
    #    'who am I' and the profile for good: I-15.)
    card = "4111 1111 1111 1111"
    out = release("remember_fact", {"fact": f"my visa is {card}", "category": "money",
                                    "added": "x"})
    assert out["fact"] == "my visa is [hidden: looks like a card number]", out
    assert out["category"] == "money" and "stayed in the house" in out["kept_home"]
    assert "4111" not in _dumps(out) and "4111" not in log_path().read_text()
    assert "fact (hidden: looked like a card number)" in entries()[-1]["withheld"]
    assert "insurance" in release("remember_fact", {"fact": "SIN 046 454 286",
                                                    "category": "x", "added": ""})["fact"]
    assert "password" in release("add_memory", {
        "text": "the wifi password is hunter22", "when": "", "people": [], "tags": [],
        "visibility": "private", "added": ""})["text"]
    assert "API key" in release("log_observation", {
        "note": "key sk-ant-api03-abcdefghijklmnop", "category": "x", "added": "",
        "ts": 0})["note"]
    # nested, inside a list inside a dict: only that part is hidden
    out = release("who_am_i", {"moments": [{"text": "card 5500 0000 0000 0004"},
                                           {"text": "the lake"}]})
    assert out["moments"][1]["text"] == "the lake" and "5500" not in _dumps(out)
    # bare text is hidden in place too
    assert "4111" not in release("get_directives", f"pay with {card}")
    # and ordinary numbers are not secrets
    release("remember_fact", {"fact": "call 416 555 0199 before June 12 2026",
                              "category": "x", "added": ""})
    release("expect_charge", {"merchant": "Hydro", "amount": 1234.56, "cadence": "monthly"})
    assert "kept_home" not in release("orb_state", {"mood": "calm"})
    print("  ✓ a card, a SIN, a password or an API key in a result is hidden in place;")
    print("    the value is in neither the result nor the log; phone numbers pass")

    # 7. get_profile keeps the owner's own field names but is still scanned —
    #    each value beside its name, so {'alarm code': '4821'} is caught too.
    assert release("get_profile", {"first_name": "L", "email": "l@x.ca"})["email"] == "l@x.ca"
    p = release("get_profile", {"card": "4111111111111111", "alarm_code": "4821",
                                "city": "Ottawa"})
    assert p["city"] == "Ottawa" and "4111" not in _dumps(p) and "4821" not in _dumps(p)
    print("  ✓ the profile passes by field name, and every value is still scanned")

    # 8. Shut door: nothing leaves, by file or by env.
    shut()
    assert is_shut() and "shut the door" in refused(release, "orb_state", {"mood": "calm"})
    assert "shut" in refused(release_text, "you_said", "hello")
    assert open_() and not is_shut()
    os.environ["JEFFEREY_OFFLINE"] = "1"
    assert is_shut()
    os.environ.pop("JEFFEREY_OFFLINE")
    release("orb_state", {"mood": "calm"})
    print("  ✓ a shut door refuses everything until the owner opens it")

    # 9. The owner's own words go through the same scan.
    assert release_text("you_said", "what did I spend on hydro?")
    assert "card" in refused(release_text, "you_said", "my card is 4012888888881881")
    sp = system_prompt_once("directives + conscience")
    n = len(entries())
    system_prompt_once("directives + conscience")          # unchanged: not re-logged
    assert len(entries()) == n
    system_prompt_once("directives + conscience v2")       # changed: logged
    assert len(entries()) == n + 1
    print("  ✓ what the owner types is scanned; the system prompt logs on change only")

    # 10. The receipt for a request: exact bytes and hash, no body duplicated.
    payload = {"model": "m", "system": "s", "messages": [{"role": "user", "content": "hi"}]}
    request(payload, "m")
    r = entries()[-1]
    assert r["kind"] == "request" and r["sent"] is None
    assert r["sha256"] == hashlib.sha256(_dumps(payload).encode()).hexdigest()
    print("  ✓ every engine call leaves a receipt with its exact size and hash")

    # 11. Nothing leaves unlogged: if the log cannot be written, the send fails.
    real = log_path()
    os.environ["JEFFEREY_EGRESS"] = str(td / "nope" / "egress.jsonl")
    home.reset_for_tests()
    (td / "nope").write_text("a file where the directory should be")
    try:
        release("orb_state", {"mood": "calm"})
        raise AssertionError("released without a log")
    except (OSError, EgressRefused):
        pass
    os.environ["JEFFEREY_EGRESS"] = str(real)
    home.reset_for_tests()
    print("  ✓ a log that cannot be written is a door that does not open")

    # 12. The wrapper is the door: a wrapped function's return is released,
    #     and a function wrapped for an unknown tool returns nothing at all.
    def orb_state() -> dict:
        return {"mood": "calm", "reason": "nothing happened", "hidden": "x"}
    w = through(orb_state)
    assert w() == {"mood": "calm", "reason": "nothing happened"}
    assert w.__name__ == "orb_state" and w.__jefferey_egress__ == "orb_state"
    def not_listed() -> dict:
        return {"x": 1}
    assert "no entry" in refused(through(not_listed))
    registered = []
    def fake_register(fn):
        registered.append(fn)
        return fn
    door(fake_register)(orb_state)
    assert registered and getattr(registered[0], "__jefferey_egress__", None) == "orb_state"
    print("  ✓ through() and door() register only the wrapped function")

    # 12b. The other direction: a secret handed IN by the engine is refused
    #      before the tool runs, so nothing is written — and the log keeps the
    #      reason, not the value.
    ran = []
    def remember_fact(fact: str, category: str = "general") -> dict:
        ran.append(fact)
        return {"fact": fact, "category": category, "added": "now"}
    w = through(remember_fact)
    msg = refused(w, fact="my visa is 4111 1111 1111 1111", category="money")
    assert "nothing was stored" in msg and "4111" not in msg and not ran
    tail = entries()[-1]
    assert tail["kind"] == "tool_call" and tail["refused"] and "4111" not in _dumps(tail)
    assert "[hidden: looks like a card number]" in tail["asked"]
    assert w(fact="recital June 12")["fact"] == "recital June 12" and ran == ["recital June 12"]
    # a vault REFERENCE is not a secret and passes in
    def fill_pdf(pdf_path: str, values: dict) -> dict:
        return {"written": "x_filled.pdf", "fields_set": sorted(values)}
    assert through(fill_pdf)(pdf_path="t.pdf", values={"SIN": "vault:sin"})["fields_set"] == ["SIN"]
    print("  ✓ a secret handed in by the engine is refused before anything is written;")
    print("    the log records the reason and not the value; vault references pass")

    # 12b'. ...including when the secret sits inside a model object inside the
    #       kwargs, which is exactly how an HTTP body arrives.
    class Body:
        def __init__(self, **kw):
            self.kw = kw
        def model_dump(self):
            return dict(self.kw)
    def remember_body(f) -> dict:
        ran.append(f.kw["fact"])
        return {"fact": f.kw["fact"], "category": "x", "added": "now"}
    n_ran = len(ran)
    msg = refused(through(remember_body, name="remember_fact"),
                  f=Body(fact="visa 4111 1111 1111 1111"))
    assert "card number" in msg and len(ran) == n_ran
    assert "4111" not in _dumps(entries()[-1])
    print("  ✓ a secret inside a request body object is seen and refused")

    # 12c. as_result: the refusal comes back as a result the model must report.
    r = through(remember_fact, as_result=True)(fact="card 5500 0000 0000 0004")
    assert r["refused"] is True and r["tool"] == "remember_fact" and "5500" not in _dumps(r)
    print("  ✓ a surface can take refusals as results instead of exceptions")

    # 13. The report reads back, names destinations, never leaks a refused value.
    s = summary(1)
    assert s["sends"] >= 8 and s["refused"] >= 8 and s["door"] == "open"
    rep = report(1, full=True)
    assert "a test engine" in rep and "REFUSED" in rep and "4111" not in rep
    assert "orb_state" in rep
    # the summary itself is releasable through the door
    release("what_left_the_house", s)
    print("  ✓ the report is readable and the summary can itself pass the door")

    # 14. A torn last line (power cut mid-write) does not poison the log.
    with log_path().open("ab") as f:
        f.write(b'{"t": "2026-')
    assert entries()
    n = len(entries())
    release("orb_state", {"mood": "after the cut"})     # starts on a fresh line
    assert len(entries()) == n + 1 and entries()[-1]["sent"] == '{"mood": "after the cut"}'
    print("  ✓ a torn last line is skipped, not fatal, and never swallows the next send")

    # 15. Every allowlist entry is a set of names; no entry allows everything by
    #     accident except the profile.
    for t, fields in RELEASE.items():
        assert isinstance(fields, frozenset) and fields, t
        assert ANY not in fields or t == "get_profile", t
    print(f"  ✓ {len(RELEASE)} tools have a release list")

    print("\nThe egress door holds.")
    return 0


# ------------------------------------------------------------ the owner's menu
def door_line() -> str:
    """The state of the door, in large plain words, after every action."""
    why = shut_reason()
    if not why:
        return "  The door is OPEN: JEFFEREY answers the AIs you use, and writes down every word."
    if why in (SHUT, UNREACHABLE):
        return "  The door is SHUT: nothing leaves JEFFEREY until you open it."
    return f"  JEFFEREY is off: {why}."


def _do_shut(out) -> int:
    try:
        done = shut_all()
    except OSError as e:
        out(f"  The door could NOT be shut ({e.strerror or e}). To stop everything now, "
            f"quit Claude and unplug the drive.")
        return 1
    out("")
    out("  ███  The door is SHUT. Nothing leaves JEFFEREY until you open it.  ███")
    if len(done) > 1:
        out(f"  (shut in {len(done)} places: on your drive and on this Mac, so it stays "
            f"shut whichever one JEFFEREY looks at)")
    return 0


def _do_open(out) -> int:
    was = open_()
    why = shut_reason()
    if why and why not in (SHUT, UNREACHABLE):
        out(f"  Your switch is open, but JEFFEREY is still off: {why}.")
        return 0
    out("  The door is open." + ("" if was else "  (it already was)"))
    return 0


def _page(text: str, out) -> None:
    import shutil
    import subprocess
    if sys.stdout.isatty() and shutil.which("less"):
        out("  (Press q to come back.)")
        try:
            subprocess.run(["less", "-R"], input=text, text=True)
            return
        except OSError:
            pass
    out(text)


MENU = """  What would you like to do? Type a word and press return:
    shut     SHUT the door — nothing leaves until you open it    (fermer)
    open     open the door again                                 (ouvrir)
    [return] see every send, word for word                       (voir)
    all      everything since the beginning                      (tout)
    keep     keep each send word for word only for some days     (garder)
    quit     close this window                                   (quitter)"""


def menu(input_fn=input, out=print) -> int:
    """'What left the house.command'. Words in English or French, read by
    their first word; anything else is asked again (I-60: 'shut' used to
    page the log and leave the door open). The door's state is printed
    after every answer."""
    import answers
    out(report(7))
    out("")
    out(door_line())
    out("")
    out(MENU)
    out("")
    pick = answers.ask_choice("  > ", answers.DOOR, input_fn, out,
                              hint="Type shut, open, all, keep or quit — or just press return.")
    rc = 0
    if pick == "shut":
        rc = _do_shut(out)
    elif pick == "open":
        rc = _do_open(out)
    elif pick == "see":
        _page(report(7, full=True), out)
    elif pick == "all":
        _page(report(None, full=True), out)
    elif pick == "keep":
        now = keep_days()
        out("  Each send is kept word for word "
            + (f"for {now} days." if now else "for as long as the log exists."))
        try:
            v = input_fn("  How many days? (a number, or 'always') ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            v = ""
        if v in ("always", "forever", "toujours"):
            set_keep(None)
            out("  Every send is kept word for word, for as long as the log exists.")
        elif v.isdigit() and int(v) > 0 and answers.ask_yes_no(
                f"  The words of every send older than {v} days are then let go for good "
                f"(the date, where it went and its fingerprint stay). Type yes or no: ",
                input_fn, out):
            set_keep(int(v))
            r = let_go(int(v))
            out(f"  Each send is now kept word for word for {v} days. "
                f"{r['entries']} older send(s) were let go just now.")
        else:
            out("  Nothing was changed.")
    else:
        out("  Nothing was changed.")
    out("")
    out(door_line())
    return rc


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="What left the house — JEFFEREY's egress log, in plain words.")
    ap.add_argument("what", nargs="?", default="report",
                    choices=["report", "shut", "open", "status", "selftest", "keep", "menu"])
    ap.add_argument("days_to_keep", nargs="?", default=None,
                    help="with 'keep': how many days to keep each send word for "
                         "word, or 'always'")
    ap.add_argument("--all", action="store_true", help="all time, not the last 7 days")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--full", action="store_true", help="every send, word for word")
    a = ap.parse_args(argv)
    if a.what == "selftest":
        return selftest()
    if a.what == "menu":
        return menu()
    if a.what == "shut":
        return _do_shut(print)
    if a.what == "open":
        return _do_open(print)
    if a.what == "keep":
        v = (a.days_to_keep or "").strip().lower()
        if v in ("always", "forever", "off", "0"):
            set_keep(None)
            print("  Every send is kept word for word, for as long as the log exists.")
            return 0
        try:
            n = int(v)
            assert n > 0
        except (ValueError, AssertionError):
            now = keep_days()
            print("  Each send is kept word for word "
                  + (f"for {now} days." if now else "for as long as the log exists.")
                  + "\n  To change it: keep <number of days>, or keep always.")
            return 0 if not v else 1
        set_keep(n)
        r = let_go(n)
        print(f"  Each send is now kept word for word for {n} days. After that only "
              f"its date, where it went and its fingerprint stay.\n"
              f"  {r['entries']} older send(s) were let go just now.")
        return 0
    if a.what == "status":
        print(f"  door: {'SHUT' if is_shut() else 'open'} · log: {log_path()}")
        for sw in home.door_switches():
            print(f"    switch {'SHUT' if os.path.lexists(sw) else 'open'}: {sw}")
        return 0
    print(report(None if a.all else a.days, full=a.full))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
