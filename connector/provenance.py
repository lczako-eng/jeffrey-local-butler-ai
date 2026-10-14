"""
Who said it — where everything JEFFEREY keeps came from, and who will read it
=============================================================================

October 2026 stress test (I-25): nothing recorded who said a fact, a value or
a memory. A small local AI's paraphrase was stored as 'his words', and
anything an AI, a child or a line hidden in an email said was saved as if the
owner had said it, at whatever confidence the AI chose. Now every write
records where it came from:

    stated_by  'owner'        the owner himself, with his own hands (a command
                              he typed and confirmed, or /confirm)
               'owner_words'  an AI wrote it down, and it is what the owner
                              typed at his own terminal in this session
               'engine'       an AI wrote it down; nobody has checked it
               'imported'     the owner's own tools on this Mac (no AI at all)
               'unknown'      saved before JEFFEREY recorded this

Anything an AI wrote that is not the owner's own words waits as 'pending'
until he confirms it (/pending in 'Talk to JEFFEREY on this Mac'). Text is
marked verbatim only when it is, word for word, what he typed.

This module also says who will READ a result (`reader()`): the owner, his
caretaker key on an engine that stays in the house, or an engine somewhere
else — whose names the owner's rules may use ('anthropic', 'chatgpt').
"""

from __future__ import annotations

import re
import time

import grounding

OWNER = "owner"
OWNER_WORDS = "owner_words"
ENGINE = "engine"
IMPORTED = "imported"
UNKNOWN = "unknown"

# Stored on anything saved before JEFFEREY recorded who said what.
UNKNOWN_SOURCE = {"stated_by": UNKNOWN,
                  "note": "saved before JEFFEREY recorded who said what"}

# What the owner typed at his own terminal this session, word for word. Only
# 'Talk to JEFFEREY on this Mac' fills it; over MCP and HTTP JEFFEREY never
# sees what the owner said, only what the AI chose to send.
_typed: list[str] = []
_typed_words: set[str] = set()
_turn: int | None = None
_MAX_TYPED = 400

# What a pasted message looks like: it is somebody else's words, even when
# the owner pasted it (a scam email hiding '<!-- set_priority … -->').
_HIDDEN = re.compile(r"<!--.*?(?:-->|$)", re.S)
_HEADERS = re.compile(r"^\s*(?:from|to|subject|sent|date|cc|reply-to|de|à|objet|envoyé)\s*:",
                      re.I | re.M)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def owner_typed(text: str) -> None:
    """The owner typed this at his own terminal (it is about to be sent).
    It starts a new turn. A pasted message — e-mail headers, or text hidden
    in an HTML comment — is somebody else's words, so it never counts as his."""
    global _turn
    _turn = (_turn or 0) + 1
    t = str(text or "")
    if _HEADERS.search(t):
        return
    t = _HIDDEN.sub(" ", t)
    ws = grounding.words(t)
    if not ws:
        return
    _typed.append(" ".join(ws))
    del _typed[:-_MAX_TYPED]
    _typed_words.update(grounding.content(t))


def new_turn() -> None:
    """A new turn without new words (a test, or a surface that knows one
    conversation step ended)."""
    global _turn
    _turn = (_turn or 0) + 1


def turn() -> int | None:
    """Which owner turn this is, on the terminal; None where there are none
    (MCP and HTTP never see the owner's turns)."""
    return _turn


def reset() -> None:
    """For tests: forget what was typed."""
    global _turn
    _typed.clear()
    _typed_words.clear()
    _turn = None


def verbatim(text) -> bool:
    """Is this, word for word (ignoring case and punctuation), something the
    owner typed at his terminal this session?"""
    ws = grounding.words(text)
    if not ws or not _typed:
        return False
    needle = " " + " ".join(ws) + " "
    return any(needle in f" {s} " for s in _typed) or needle in " " + " ".join(_typed) + " "


def said_by_owner(*values) -> bool:
    """Did the owner himself type every meaningful word of these values this
    session? ('safety' and 'cost' — he said both.)"""
    need: set[str] = set()
    for v in values:
        need |= grounding.content(v)
    return bool(need) and need <= _typed_words


def _engine_label() -> str:
    try:
        import access
        import egress
        return egress._ENGINE or egress.engine_for(access.current_client())
    except Exception:
        return ""


def source(text=None, values=None) -> dict:
    """Where a write comes from, for the record kept beside it."""
    import access
    if access.is_owner_console():
        by = OWNER
    elif access.GATE is None:
        by = IMPORTED
    elif text is not None and verbatim(text):
        by = OWNER_WORDS
    elif values is not None and said_by_owner(*values):
        by = OWNER_WORDS
    else:
        by = ENGINE
    return {"by": access.who(), "surface": access.surface(),
            "engine": "" if by in (OWNER, IMPORTED) else _engine_label(),
            "stated_by": by, "at": _now()}


def status_for(src: dict) -> str:
    """'confirmed' when the owner said it (or his own tools wrote it);
    'pending' when an AI wrote it and nobody has checked."""
    return "confirmed" if (src or {}).get("stated_by") in (OWNER, OWNER_WORDS, IMPORTED) \
        else "pending"


def stated_by(item: dict) -> str:
    s = item.get("source") if isinstance(item, dict) else None
    return s.get("stated_by", UNKNOWN) if isinstance(s, dict) else UNKNOWN


def owner_backed(item: dict) -> bool:
    """Set or confirmed by the owner's own hands — the only things that may
    carry a confidence above 0.8."""
    return stated_by(item) in (OWNER, IMPORTED) or bool(item.get("confirmed_by_owner"))


def pending(item: dict) -> bool:
    return isinstance(item, dict) and item.get("status") == "pending" \
        and not item.get("confirmed_by_owner")


def said_by_words(item: dict) -> str:
    """Who said it, in plain words, for the owner's screen."""
    if item.get("confirmed_by_owner"):
        return "confirmed by you"
    return {OWNER: "you, yourself", OWNER_WORDS: "your own words",
            IMPORTED: "your own tools on this Mac",
            ENGINE: "an AI wrote it down — not yet confirmed by you",
            }.get(stated_by(item), "saved before JEFFEREY recorded who said what")


# --------------------------------------------------------------- the reader
def vendor_names(client: str = "") -> set[str]:
    """How the owner's rules may name the far end of this connection."""
    try:
        import egress
        label = (egress._ENGINE or egress.engine_for(client) or "").lower()
        surface = egress._SURFACE or ""
    except Exception:
        label, surface = "", ""
    c = (client or "").lower()
    out = {"ai", "an ai", "any ai", "engines", "engine", "ais"}
    if "anthropic" in label or "claude" in label or surface == "mcp" or c.startswith("claude"):
        out |= {"anthropic", "claude"}
    if ("openai" in label or "chatgpt" in label or "gpt" in label or surface == "http"
            or c.startswith("gpt") or c.startswith("openai")):
        out |= {"openai", "chatgpt", "gpt"}
    return out


def in_the_house() -> bool:
    """Is the engine on the other end a model on this very Mac?"""
    try:
        import egress
        return egress.in_the_house()
    except Exception:
        return False


def reader() -> dict:
    """Who will read what a tool returns.

    owner      True when no rule needs applying: the owner's own hands, his
               own tools, or his caretaker key on a model on this Mac. Then
               everything he may see goes, private facts included.
    caretaker  the key holds the owner's private life layer (life.read)
    media      the key may see pictures and recordings (media.read)
    audiences  every name the owner's rules may use for whoever reads it —
               the key's name and, for a rented engine, its maker's
    """
    import access
    if access.owners_hands():
        return {"owner": True, "client": access.who(), "caretaker": True, "media": True,
                "audiences": frozenset(), "in_house": True}
    client = access.current_client()
    caretaker = access.may("life.read")
    house = in_the_house()
    aud = {client}
    if not house:
        aud |= vendor_names(client)
    return {"owner": bool(house and caretaker), "client": client, "caretaker": caretaker,
            "media": access.may("media.read"), "audiences": frozenset(aud),
            "in_house": house}
