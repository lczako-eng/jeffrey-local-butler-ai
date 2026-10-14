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
                    "tell_the_user", "kept_home"})

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
    "pdf_form_fields", "tell_story", "selfcloud_check_access",
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
    "close_goal": ("contains",), "resolve_opportunity": ("contains",),
    "conscience_exclude": ("contains",), "remove_rule": ("rule_id_or_text",),
    "forget_profile_field": ("field",),
}

RELEASE: dict[str, frozenset[str]] = {
    # identity
    "get_directives": frozenset({TEXT, "directives"}),
    # store_path is deliberately absent: the layout of the owner's drive is
    # not the engine's business.
    # notices: JEFFEREY's own plain words about the store (a recovery, a
    # restore, an edit by hand) — the owner must hear them, so they go out.
    "get_conscience": frozenset({"owner", "priorities", "facts", "active_goals",
                                 "corrections_learned_from", "notices"}),
    # values and how they are learned
    "record_correction": frozenset({"id", "context", "higher", "lower",
                                    "confidence", "evidence", "updated"}),
    "set_priority": frozenset({"id", "context", "higher", "lower", "confidence",
                               "evidence", "updated"}),
    # facts only reach a key that may read facts (conscience.explain_basis)
    "explain_basis": frozenset({"topic", "priorities", "facts"}),
    "priorities_for": frozenset({"id", "context", "higher", "lower", "confidence",
                                 "evidence", "updated"}),
    "draft_guidance": frozenset({"purpose", "recipient", "write_as",
                                 "their_priorities_here", "their_facts_here",
                                 "voice", "rules"}),
    # facts, profile, rules, the daily brief
    "remember_fact": frozenset({"id", "fact", "category", "added"}),
    "forget": FORGET | {"removed_facts"},
    "get_profile": frozenset({ANY}),
    # a change to who the owner is comes back as a question first (I-30)
    "set_profile_field": frozenset({"stored", "field", "value", "step", "would_change",
                                    "confirm", "expires", "how_to_finish"}),
    "forget_profile_field": FORGET | {"removed"},
    # from_your_vault: "your SIN will go into box X", read to the owner first
    "fill_form": frozenset({"filled", "needs_you", "coverage", "vault_available",
                            "from_your_vault"}),
    # fill_pdf: the filled copy's location, never the values written into it;
    # which secret went into which box by NAME (I-02), what was taken out of
    # the copy (I-31) and which boxes were signed under an approval (I-57)
    "fill_pdf": frozenset({"written", "saved_in", "fields_set", "filled_from_vault",
                           "original_untouched", "fields", "references", "available",
                           "secrets_used", "not_on_this_form", "removed_from_copy",
                           "signed", "wrong_boxes"}),
    # field names are the PDF author's words: data, never instructions (I-31)
    "pdf_form_fields": frozenset({"path", "fields", "count", "field_names_are",
                                  "described", "sensitive", "for_someone_else",
                                  "signing", "suspicious", "warning"}),
    # who wrote each line and through which door (I-45); an approval's id is
    # given only to the connection that asked for it, never in the log view
    "action_log": frozenset({"category", "description", "amount", "currency",
                             "outcome", "added", "ts", "by", "surface", "source",
                             "approved"}),
    "conscience_include": frozenset({"id", "ref", "added"}),
    "conscience_exclude": FORGET | {"excluded"},
    "set_rule": frozenset({"id", "kind", "tags", "audience", "allow",
                           "instruction", "added"}),
    "remove_rule": FORGET | {"removed"},
    "list_rules": frozenset({"id", "kind", "tags", "audience", "allow",
                             "instruction", "added"}),
    "daily_brief": frozenset({"orb", "active_goals", "opportunities",
                              "recent_actions", "recent_observations",
                              "corrections_learned_from", "notices"}),
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
                             "surface", "source"}),
    # money
    "expect_charge": frozenset({"key", "merchant", "amount", "cadence",
                                "authorized_recurring", "active",
                                "cancelled_on", "updated"}),
    "mark_cancelled": frozenset({"merchant", "marked_cancelled", "cancelled_on"}),
    "check_charge": frozenset({"merchant", "amount", "date", "cadence", "verdict",
                               "severity", "what_happened", "recoverable",
                               "authorized_on_file", "action"}),
    "review_statement": frozenset({"checked", "flagged", "quiet",
                                   "recoverable_total", "annualized_estimate",
                                   "summary"}),
    "expected_charges": frozenset({"key", "merchant", "amount", "cadence",
                                   "authorized_recurring", "active",
                                   "cancelled_on", "updated"}),
    "dispute_pack": frozenset({"merchant", "what_was_authorized",
                               "charges_in_dispute", "amount_in_dispute",
                               "full_history", "how_to_use"}),
    # the representative reading their mail
    "triage_message": frozenset({"sender", "subject", "verdict", "scam_score",
                                 "scam_flags", "billing_score", "billing_flags",
                                 "money_mentioned", "deadlines",
                                 "relevant_priorities", "advice"}),
    # the life layer
    "add_person": frozenset({"id", "name", "relationship", "notes",
                             "important_dates", "added", "updated"}),
    "add_memory": frozenset({"id", "text", "when", "people", "tags", "visibility",
                             "added", "photos"}),
    "add_media": frozenset({"id", "path", "caption", "when", "people", "visibility",
                            "reachable", "added"}),
    "who_am_i": frozenset({"people_who_matter", "moments",
                           "pictures_and_recordings", "what_they_value", "facts",
                           "depth"}),
    "tell_story": frozenset({"theme", "visible_at", "moments", "pictures",
                             "people", "how_to_tell_it"}),
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
    "next_story_prompt": frozenset({"moment_id", "label", "photos", "from", "to",
                                    "show_on_the_wall", "photo_ids", "ask"}),
    "record_story": frozenset({"kept", "moment", "memory", "pinned_to_photos",
                               "one_follow_up"}),
    "decline_story": frozenset({"declined", "moment_id"}),
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
                                      "secrets_used_on_forms", "to_see_everything"}),
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
         **dict.fromkeys(map(ord, "\u2018\u2019\u201a\u201b\u2032\u02bc`\u00b4"), "'")}


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
    r"wi[\s\-]?fi" + _S + r"(?:code|key|pin)")
# Words that only count when the value follows at once ("wifi: BlueHouse20").
_WEAK_WORDS = _rx(r"wi[\s\-]?fi", r"network" + _S + r"key",
                  r"cle" + _S + r"(?:wi[\s\-]?fi|reseau|de" + _S + r"securite)")
_KW = re.compile(r"(?<![^\W_])(?:(?P<pw>" + _PW_WORDS + r")|(?P<pin>" + _PIN_WORDS
                 + r")|(?P<weak>" + _WEAK_WORDS + r")|(?P<code>code))(?![^\W_])", re.I)

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
""".split())
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


def _ndigits(s: str) -> int:
    return sum(c.isdigit() for c in s)


def _is_value(fam: str, raw: str, conn: bool, gap: int, prev: str,
              says: bool = True) -> bool:
    """Is this token the secret that the word before announced?"""
    v = raw.lstrip(_LEAD + "-").rstrip(_TRAIL)
    if not v:
        return False
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


def _keyword_hits(n: str) -> list[tuple[int, int, str]]:
    out = []
    for m in _KW.finditer(n):
        fam = m.lastgroup
        what = PASSWORD if fam in ("pw", "weak") else CODE
        if fam == "code":
            before = re.findall(r"[a-z]+", n[max(0, m.start() - 20):m.start()].lower())
            if before and before[-1] in _NOT_A_SECRET_CODE:
                continue
        # the value after the word: "PIN 4821", "mot de passe Desjardins est Soleil24"
        conn, says, gap, prev, last = False, False, 0, "", m.end()
        for t in _TOK.finditer(n, m.end(), min(len(n), m.end() + 200)):
            between = n[last:t.start()]
            if "\n" in between and (gap or "\n\n" in between):
                break
            raw = t.group()
            low = raw.lower()
            if low in _CONNECT:
                conn, says, last = True, low in _SAYS, t.end()
                continue
            if _is_value(fam, raw, conn, gap, prev, says):
                end = t.end()
                if fam in ("pw", "weak") and raw[-1:] not in ".,;!?\"'":
                    # a passphrase can be several words: hide to the end of the clause
                    for k, u in enumerate(_TOK.finditer(n, end, min(len(n), end + 120))):
                        if k >= 5 or "\n" in n[end:u.start()]:
                            break
                        end = u.end()
                        if u.group()[-1:] in ".,;!?\"'":
                            break
                out.append((*_trim(n, t.start(), end), what))
                break
            gap += 1
            if gap > _MAX_GAP or raw[-1:] in ".!?;":
                break
            prev, last = low.strip(_LEAD + _TRAIL), t.end()
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
_SEPR = "(?:[ \\t]*[.\\-/_\u00b7\u2022][ \\t]*|\\s{1,3})"
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
                      r"|membership|serial|imei|iccid|barcode|upc|isbn|no|num|n°|nº)(?![^\W_])"
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
            elif w3 == [3, 3, 3] and len(set(seps[i:i + 2])) == 1 and (_luhn(sub) or sin_kw):
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


def _id_hits(n: str) -> list[tuple[int, int, str]]:
    out = []
    for what, rx in _ID_WORDS.items():
        for m in rx.finditer(n):
            gap, start, end, digits, chunk = 0, None, None, 0, ""
            for t in _TOK.finditer(n, m.end(), min(len(n), m.end() + 80)):
                raw = t.group()
                v = raw.lstrip(_LEAD).rstrip(_TRAIL)
                if start is None:
                    if v.lower() in _ID_FILLER or not v:
                        continue
                    if not any(c.isdigit() for c in v):
                        gap += 1
                        if gap > 3 or raw[-1:] in ".!?;" or v.lower() in _ID_BREAK:
                            break
                        continue
                    if ("$" in raw or "%" in raw or re.search(r"\d,\d{3}", v)
                            or _DATE_OR_PHONE.fullmatch(v)):
                        break                     # money, a date or a phone number
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


def find_secrets(text: str) -> list[tuple[int, int, str]]:
    """Every secret-shaped span in `text`: (start, end, what), in the
    original text's positions, overlapping spans merged, in order."""
    if not isinstance(text, str) or len(text) < 6 or _HEXID.fullmatch(text):
        return []                      # a sha256 or other long hex id: never a secret
    n, src = _normalise(text)
    hits = _key_hits(n) + _keyword_hits(n) + _number_hits(n) + _id_hits(n)
    if not hits:
        return []
    if src is not None:
        hits = [(src[s], src[e - 1] + 1, w) for s, e, w in hits]
    hits.sort(key=lambda h: (h[0], -h[1]))
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


def looks_secret(text: str) -> str | None:
    """Why this string must not leave, or None."""
    hits = find_secrets(text)
    if not hits:
        return None
    return min((w for _, _, w in hits), key=_ORDER.index)


def hidden_mark(what: str) -> str:
    return f"[hidden: looks like {what}]"


def mask_text(text: str) -> tuple[str, list[str]]:
    """The text with every secret-shaped span replaced by a plain mark, and
    what each was."""
    hits = find_secrets(text)
    if not hits:
        return text, []
    parts, last = [], 0
    for s, e, w in hits:
        parts.append(text[last:s])
        parts.append(hidden_mark(w))
        last = e
    parts.append(text[last:])
    return "".join(parts), [w for _, _, w in hits]


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
    out whole."""
    found: list[tuple[str, str]] = []

    def go(o, w):
        if isinstance(o, str):
            m, whats = mask_text(o)
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
                    why = looks_secret(str(v)) or _pair_secret(k, v)
                    if why:
                        rows.append({"path": path + (k,), "section": path[0] if path else k,
                                     "field": _label(k), "words": str(v), "looks_like": why})
                else:
                    walk(v, path + (k,))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                if isinstance(v, str) and looks_secret(v):
                    rows.append({"path": path + (i,), "section": path[0] if path else "",
                                 "field": "", "words": v, "looks_like": looks_secret(v)})
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
    if row.get("section") == "profile" or not find_secrets(old):
        new = f"vault:{name}"
    else:
        hits = find_secrets(old)
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
_ANNOUNCED_SYSTEM: str | None = None

SENT_CAP = 64 * 1024               # bytes of each send kept word for word
ASKED_CAP = 2 * 1024


def bind(surface: str, engine: str | None = None) -> None:
    """Say once, per process, which surface this is and who is on the far end."""
    global _SURFACE, _ENGINE
    _SURFACE = surface
    _ENGINE = engine or os.environ.get("JEFFEREY_ENGINE")
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
    process is a first run, not an unplugged drive."""
    if os.environ.get("JEFFEREY_OFFLINE") == "1":
        return SHUT
    p = switch_path()
    try:
        os.stat(p)
        return SHUT
    except FileNotFoundError:
        pass
    except OSError:
        return UNREACHABLE               # cannot tell: treat as shut
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
    """The Self-Cloud drive this process started on is no longer there."""
    try:
        r = home.root()
        return bool(r) and not os.path.isdir(r)
    except Exception:
        return False


def shut() -> Path:
    p = switch_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"shut by the owner {_now()}\n")
    return p


def open_() -> bool:
    p = switch_path()
    if p.exists():
        p.unlink()
        return True
    return False


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
    asked, _ = mask(asked)
    try:
        s = _dumps(asked)
    except Exception:
        s = str(asked)
    return s if len(s) <= ASKED_CAP else s[:ASKED_CAP] + "…"


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
    p.parent.mkdir(parents=True, exist_ok=True)
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


def _text_hits(s, match) -> bool:
    if not isinstance(s, str) or not s:
        return False
    try:
        obj = json.loads(s)
    except ValueError:
        return bool(match(s))
    return any(match(x) for x in _strings(obj))


def _hits(e: dict, match) -> tuple[bool, bool]:
    return _text_hits(e.get("sent"), match), _text_hits(e.get("asked"), match)


def matching(match) -> dict:
    """How many entries hold what `match` finds, and where they went.
    Reads only."""
    out = {"entries": 0, "engines": Counter(), "first": None, "last": None}
    for e in entries():
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
    """Rewrite the log under its lock, atomically: `change(entry)` returns
    True if it changed the entry in place. A torn line `change` is asked
    about as {"torn": text}; True drops it. Returns how many."""
    p = log_path()
    out = {"entries": 0, "torn_lines_dropped": 0}
    if not p.exists():
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
    hit = _scan(_plain(asked))
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
def entries(since: datetime | None = None) -> list[dict]:
    p = log_path()
    if not p.exists():
        return []
    out = []
    with p.open("rb") as f:
        for line in f:
            e = _parse_line(line)
            if e is None:
                continue          # a torn line from a power cut or a full drive
            if since and e.get("t", "") < since.strftime("%Y-%m-%dT%H:%M:%SZ"):
                continue
            out.append(e)
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
    es = entries(since)
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
        "log_lives": home.describe(),
        "to_see_everything": "double-click 'What left the house.command' — the "
                             "owner reads every send word for word, there",
    }


def report(days: int | None = 7, full: bool = False) -> str:
    """The owner's readable answer to 'what left the house?'"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)) if days else None
    es = entries(since)
    span = f"the last {days} days" if days else "all time"
    lines = [f"WHAT LEFT THE HOUSE — {span}",
             f"  the door is {'SHUT' if is_shut() else 'open'} · "
             f"the log lives {home.describe()}", ""]
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
            head = (f"{e['t']}  {e.get('kind')}  {e.get('tool') or ''}  → {e.get('engine')} "
                    f"({_kb(int(e.get('bytes') or 0))})")
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


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="What left the house — JEFFEREY's egress log, in plain words.")
    ap.add_argument("what", nargs="?", default="report",
                    choices=["report", "shut", "open", "status", "selftest", "keep"])
    ap.add_argument("days_to_keep", nargs="?", default=None,
                    help="with 'keep': how many days to keep each send word for "
                         "word, or 'always'")
    ap.add_argument("--all", action="store_true", help="all time, not the last 7 days")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--full", action="store_true", help="every send, word for word")
    a = ap.parse_args(argv)
    if a.what == "selftest":
        return selftest()
    if a.what == "shut":
        p = shut()
        print(f"  The door is SHUT. Nothing leaves JEFFEREY until you open it.\n  ({p})")
        return 0
    if a.what == "open":
        was = open_()
        print("  The door is open." + ("" if was else "  (it already was)"))
        return 0
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
        return 0
    print(report(None if a.all else a.days, full=a.full))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
