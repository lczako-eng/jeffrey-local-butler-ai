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
   On top of the allowlist a hard scan refuses the send outright if anything
   shaped like a secret is in it — a card number, a SIN, a password, an API
   key. Refused means the *whole* result stays home and the model is told
   only the field name, never the value.

3. **Nothing leaves unlogged.** Every send is written, word for word, to an
   append-only log beside the conscience — on the drive when there is one —
   *before* it goes. If the log cannot be written, the send does not happen.
   `python connector/egress.py` reads it back in plain words: who got what.

The owner can also shut the door: `python connector/egress.py shut` (or a
file named `door-shut` beside the conscience, or JEFFEREY_OFFLINE=1). Shut
means every release is refused until they open it again. This is JEFFEREY's
own switch; Self-Cloud's offline switch is theirs and stays theirs.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import home

# --------------------------------------------------------------- the allowlist
# Per tool: the top-level fields that may leave. For a tool that returns a
# list, these are the fields of each item. Anything not named is withheld.
TEXT = "*text*"      # the tool returns a bare string that may leave whole
ANY = "*any*"        # keys are the owner's own field names (get_profile) —
                     # no top-level filter, the secret scan still runs

# Shapes JEFFEREY itself produces — guidance strings and refusals, never owner
# data — allowed on every tool so a refusal can be reported as a result.
COMMON = frozenset({"error", "note", "rule", "reason", "refused", "tool",
                    "tell_the_user"})

RELEASE: dict[str, frozenset[str]] = {
    # identity
    "get_directives": frozenset({TEXT, "directives"}),
    # store_path is deliberately absent: the layout of the owner's drive is
    # not the engine's business.
    "get_conscience": frozenset({"owner", "priorities", "facts", "active_goals",
                                 "corrections_learned_from"}),
    # values and how they are learned
    "record_correction": frozenset({"context", "higher", "lower", "confidence",
                                    "evidence", "updated"}),
    "set_priority": frozenset({"context", "higher", "lower", "confidence",
                               "evidence", "updated"}),
    "explain_basis": frozenset({"topic", "priorities", "facts"}),
    "priorities_for": frozenset({"context", "higher", "lower", "confidence",
                                 "evidence", "updated"}),
    "draft_guidance": frozenset({"purpose", "recipient", "write_as",
                                 "their_priorities_here", "their_facts_here",
                                 "voice", "rules"}),
    # facts, profile, rules, the daily brief
    "remember_fact": frozenset({"fact", "category", "added"}),
    "forget": frozenset({"removed_facts"}),
    "get_profile": frozenset({ANY}),
    "set_profile_field": frozenset({"stored", "field", "value"}),
    "forget_profile_field": frozenset({"removed"}),
    "fill_form": frozenset({"filled", "needs_you", "coverage", "vault_available"}),
    # fill_pdf: the filled copy's location, never the values written into it
    "fill_pdf": frozenset({"written", "fields_set", "filled_from_vault",
                           "original_untouched", "fields", "references",
                           "available"}),
    "pdf_form_fields": frozenset({"path", "fields", "count"}),
    "action_log": frozenset({"category", "description", "amount", "outcome",
                             "added", "ts"}),
    "conscience_include": frozenset({"ref", "added"}),
    "conscience_exclude": frozenset({"excluded"}),
    "set_rule": frozenset({"id", "kind", "tags", "audience", "allow",
                           "instruction", "added"}),
    "remove_rule": frozenset({"removed"}),
    "list_rules": frozenset({"id", "kind", "tags", "audience", "allow",
                             "instruction", "added"}),
    "daily_brief": frozenset({"orb", "active_goals", "opportunities",
                              "recent_actions", "recent_observations",
                              "corrections_learned_from"}),
    "orb_state": frozenset({"mood"}),
    # goals and the opportunity engine
    "add_goal": frozenset({"goal", "added", "active"}),
    "close_goal": frozenset({"closed"}),
    "log_observation": frozenset({"note", "category", "added", "ts"}),
    "record_opportunity": frozenset({"what", "value_estimate", "aligns_with",
                                     "advances_goal", "reduces_risk", "urgency",
                                     "score", "status", "resolved", "added", "ts"}),
    "resolve_opportunity": frozenset({"resolved"}),
    # acting on their behalf
    "set_permission": frozenset({"category", "level", "cap", "updated"}),
    "authorize_action": frozenset({"allowed", "level", "cap", "updated"}),
    "log_action": frozenset({"category", "description", "amount", "outcome",
                             "added", "ts"}),
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
    "add_person": frozenset({"name", "relationship", "notes", "important_dates",
                             "added", "updated"}),
    "add_memory": frozenset({"text", "when", "people", "tags", "visibility",
                             "added", "photos"}),
    "add_media": frozenset({"path", "caption", "when", "people", "visibility",
                            "reachable", "added"}),
    "who_am_i": frozenset({"people_who_matter", "moments",
                           "pictures_and_recordings", "what_they_value", "facts",
                           "depth"}),
    "tell_story": frozenset({"theme", "visible_at", "moments", "pictures",
                             "people", "how_to_tell_it"}),
    "story_gaps": frozenset({"gaps"}),
    "forget_life": frozenset({"memories_removed", "media_removed",
                              "people_removed"}),
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
    # the keys to Self-Cloud (about keys — never about the data behind them)
    "selfcloud_status": frozenset({"keys_issued", "active_keys", "revoked_keys",
                                   "recent_denials", "principle"}),
    "selfcloud_grants": frozenset({"keys", "active", "revoked",
                                   "available_scopes", "presets"}),
    "selfcloud_grant": frozenset({"client", "label", "scopes", "active",
                                  "granted_on", "revoked_on"}),
    "selfcloud_add_scope": frozenset({"client", "label", "scopes", "active",
                                      "granted_on", "revoked_on"}),
    "selfcloud_remove_scope": frozenset({"client", "label", "scopes", "active",
                                         "granted_on", "revoked_on"}),
    "selfcloud_revoke": frozenset({"revoked", "client", "on"}),
    "selfcloud_check_access": frozenset({"allowed", "client", "scope"}),
    "selfcloud_access_log": frozenset({"client", "action", "detail", "allowed", "at"}),
    # secrets: names only
    "vault_status": frozenset({"available", "secrets"}),
    # this door's own report — counts and destinations, never the bodies
    "what_left_the_house": frozenset({"since", "sends", "refused",
                                      "by_destination", "door", "log_lives",
                                      "to_see_everything"}),
}


# ------------------------------------------------------------ the hard scan
# Shapes that are a secret wherever they appear. A hit refuses the whole
# result: the allowlist decides what *kind* of thing may leave; this decides
# that a secret is not a kind of thing.
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


_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")       # 13–19 digits
_SIN = re.compile(r"(?<!\d)\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)")    # Canadian SIN
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")           # US SSN
_PASSWORD = re.compile(
    r"(?i)\b(?:password|passcode|passphrase|pin|cvv|cvc|security code)\b\s*(?:is|[:=])\s*\S+")
_APIKEY = re.compile(
    r"\b(?:sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
    r"|ghp_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,})")


def looks_secret(text: str) -> str | None:
    """Why this string must not leave, or None."""
    if not isinstance(text, str) or len(text) < 6:
        return None
    if _APIKEY.search(text):
        return "an API key"
    if _PASSWORD.search(text):
        return "a password or PIN"
    if _SSN.search(text):
        return "a social security number"
    for m in _CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return "a card number"
    for m in _SIN.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if _luhn(digits):
            return "a social insurance number"
    return None


def _scan(obj, where: str = "") -> tuple[str, str] | None:
    """Walk the whole value. Returns (field, what) for the first secret."""
    if isinstance(obj, str):
        why = looks_secret(obj)
        return (where or "text", why) if why else None
    if isinstance(obj, dict):
        for k, v in obj.items():
            why = looks_secret(str(k))
            if why:
                return (where or "a field name", why)
            hit = _scan(v, f"{where}.{k}" if where else str(k))
            if hit:
                return hit
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            hit = _scan(v, f"{where}[{i}]")
            if hit:
                return hit
    return None


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


def is_shut() -> bool:
    return os.environ.get("JEFFEREY_OFFLINE") == "1" or switch_path().exists()


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


def _describe(asked) -> str:
    """The arguments, for the log's 'why' — capped, and never a secret's
    home: if what the engine sent looks like a secret, the log says so and
    keeps the value out."""
    if asked is None:
        return ""
    asked = _plain(asked)
    hit = _scan(asked)
    if hit:
        return (f"[not written down: '{hit[0]}' in what the engine sent "
                f"contained what looks like {hit[1]}]")
    try:
        s = _dumps(asked)
    except Exception:
        s = str(asked)
    return s if len(s) <= ASKED_CAP else s[:ASKED_CAP] + "…"


# ------------------------------------------------------------------- the log
def log_path() -> Path:
    return home.egress_path()


def _write(entry: dict) -> None:
    """Append one line, fsynced, before anything leaves. A log that cannot be
    written is a door that cannot be opened."""
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    line = (_dumps(entry) + "\n").encode()
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(p, flags, 0o600)
    try:
        os.write(fd, line)
        os.fsync(fd)
    finally:
        os.close(fd)


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
    _write(_entry(kind, tool=tool, sent=None, asked=_describe(asked),
                  withheld=[], refused=reason))
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
    stored value would poison every aggregate result afterwards (who_am_i,
    get_conscience, the daily brief) — each refused whole at the door until
    the owner found and forgot the fact. So the scan runs on the arguments
    *before* the tool runs and nothing is written. Secrets go in the vault,
    from the owner's own terminal, never through an engine."""
    if asked is None:
        return
    hit = _scan(_plain(asked))
    if hit:
        field, what = hit
        _write(_entry("tool_call", tool=tool, sent=None, asked=_describe(asked),
                      withheld=[], refused=f"the engine handed in what looks like "
                                          f"{what} in '{field}'; not taken"))
        raise EgressRefused(
            f"refused at the door: '{field}' in what you sent contains what looks "
            f"like {what}. JEFFEREY does not take secrets into the conscience from "
            f"an engine — nothing was stored. If the owner needs it kept, they "
            f"store it in the vault from their own terminal "
            f"(python connector/vault.py set <name>) and you use 'vault:<name>'.")


def release(tool: str, out, asked=None):
    """A tool result is about to go to the engine. Return what may go.

    Order matters: shut? → known tool? → allowlist → secret scan → log → go.
    Every refusal is logged too, with the reason and never the value."""
    if _SURFACE is None:
        raise _refuse("tool_result", tool, asked,
                      "no surface is bound to this process, so nothing leaves it")
    if is_shut():
        raise _refuse("tool_result", tool, asked,
                      "the owner has shut the door (JEFFEREY is offline)")
    if tool not in RELEASE:
        raise _refuse("tool_result", tool, asked,
                      f"'{tool}' has no entry in the release list — nothing "
                      f"from it may leave until the owner's code names what may")
    try:
        kept, withheld = _filter(tool, out)
    except ValueError as e:
        raise _refuse("tool_result", tool, asked, str(e))
    hit = _scan(kept)
    if hit:
        field, what = hit
        raise _refuse("tool_result", tool, asked,
                      f"'{field}' contains what looks like {what}")
    _write(_entry("tool_result", tool=tool, sent=_dumps(kept),
                  asked=_describe(asked), withheld=withheld, refused=None))
    return kept


def release_text(kind: str, text: str, why: str = "") -> str:
    """Text the owner's own terminal is about to send: the system prompt, or
    what they typed. Same door, same scan, same log."""
    if _SURFACE is None:
        raise _refuse(kind, None, why, "no surface is bound to this process")
    if is_shut():
        raise _refuse(kind, None, why, "the owner has shut the door (JEFFEREY is offline)")
    what = looks_secret(text)
    if what:
        raise _refuse(kind, None, why, f"it contains what looks like {what}")
    _write(_entry(kind, tool=None, sent=text, asked=why, withheld=[], refused=None))
    return text


def request(payload: dict, model: str) -> dict:
    """The owner's terminal is about to make one call to the engine. Every
    part of the payload has already been released piece by piece (system
    prompt, what they typed, each tool result); this writes the receipt for
    the call itself — its exact size and hash — and is the last thing that
    runs before the bytes go."""
    if _SURFACE is None:
        raise _refuse("request", None, model, "no surface is bound to this process")
    if is_shut():
        raise _refuse("request", None, model, "the owner has shut the door (JEFFEREY is offline)")
    raw = _dumps(payload).encode()
    _write({
        "t": _now(), "surface": _SURFACE, "to": _client(),
        "engine": _ENGINE or model, "kind": "request", "tool": None,
        "asked": f"model={model} messages={len(payload.get('messages', []))}",
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "sent": None, "truncated": False, "withheld": [], "refused": None,
    })
    return payload


def system_prompt_once(text: str) -> str:
    """The system prompt is logged whenever it changes, not every turn."""
    global _ANNOUNCED_SYSTEM
    h = hashlib.sha256(text.encode()).hexdigest()
    if h != _ANNOUNCED_SYSTEM:
        release_text("system_prompt", text, why="the directives plus the live conscience")
        _ANNOUNCED_SYSTEM = h
    return text


def refusal_result(tool: str, e: EgressRefused) -> dict:
    """A refusal as a RESULT the model must report — for surfaces whose SDK
    would otherwise swallow the reason (the MCP SDK reduces any exception to
    'Error executing tool <name>')."""
    return {"refused": True, "tool": tool, "reason": str(e),
            "tell_the_user": "Say plainly that the egress door kept this in the "
                             "house, and stop. Do not ask the owner to read it "
                             "to you another way."}


def through(fn, name: str | None = None, as_result: bool = False):
    """Wrap a tool function so what goes in is admitted and what comes out is
    released. `as_result=True` turns a refusal into a result dict instead of
    an exception (see refusal_result)."""
    tool = name or fn.__name__

    @functools.wraps(fn)
    def inner(*args, **kwargs):
        asked = kwargs if kwargs else (args[0] if len(args) == 1 else list(args))
        try:
            admit(tool, asked)
            out = fn(*args, **kwargs)
            return release(tool, out, asked=asked)
        except EgressRefused as e:
            if as_result:
                return refusal_result(tool, e)
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
            try:
                e = json.loads(line)
            except ValueError:
                continue          # a torn last line from a power cut
            if since and e.get("t", "") < since.strftime("%Y-%m-%dT%H:%M:%SZ"):
                continue
            out.append(e)
    return out


def _kb(n: int) -> str:
    return f"{n/1024:.1f} KB" if n >= 1024 else f"{n} B"


def summary(days: int = 7) -> dict:
    """Counts and destinations — safe to hand to the engine itself."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    es = entries(since)
    by: dict[tuple[str, str, str], dict] = {}
    refused = 0
    for e in es:
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

    # 6. The hard scan: a secret anywhere refuses the WHOLE result and the
    #    value is in neither the exception nor the log.
    card = "4111 1111 1111 1111"
    msg = refused(release, "remember_fact",
                  {"fact": f"my visa is {card}", "category": "money", "added": "x"})
    assert "card number" in msg and card not in msg and "4111" not in msg
    assert card not in log_path().read_text() and "4111" not in log_path().read_text()
    assert "insurance" in refused(release, "remember_fact",
                                  {"fact": "SIN 046 454 286", "category": "x", "added": ""})
    assert "password" in refused(release, "add_memory",
                                 {"text": "the wifi password is hunter22", "when": "",
                                  "people": [], "tags": [], "visibility": "private", "added": ""})
    assert "API key" in refused(release, "log_observation",
                                {"note": "key sk-ant-api03-abcdefghijklmnop", "category": "x",
                                 "added": "", "ts": 0})
    # nested, inside a list inside a dict
    assert "card number" in refused(release, "who_am_i",
                                    {"moments": [{"text": "card 5500 0000 0000 0004"}]})
    # and ordinary numbers are not secrets
    release("remember_fact", {"fact": "call 416 555 0199 before June 12 2026",
                              "category": "x", "added": ""})
    release("expect_charge", {"merchant": "Hydro", "amount": 1234.56, "cadence": "monthly"})
    print("  ✓ a card, a SIN, a password or an API key refuses the whole result;")
    print("    the value is in neither the message nor the log; phone numbers pass")

    # 7. get_profile keeps the owner's own field names but is still scanned.
    assert release("get_profile", {"first_name": "L", "email": "l@x.ca"})["email"] == "l@x.ca"
    assert "card" in refused(release, "get_profile", {"card": "4111111111111111"})
    print("  ✓ the profile passes by field name, and is still scanned")

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
    assert "not written down" in tail["asked"]
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
    assert s["sends"] >= 8 and s["refused"] >= 10 and s["door"] == "open"
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
    print("  ✓ a torn last line is skipped, not fatal")

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
                    choices=["report", "shut", "open", "status", "selftest"])
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
    if a.what == "status":
        print(f"  door: {'SHUT' if is_shut() else 'open'} · log: {log_path()}")
        return 0
    print(report(None if a.all else a.days, full=a.full))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
