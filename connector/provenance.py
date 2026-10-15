"""
Who said it — where everything JEFFEREY keeps came from, and who will read it
=============================================================================

October 2026 stress test (I-25): nothing recorded who said a fact, a value or
a memory. A small local AI's paraphrase was stored as 'his words', and
anything an AI, a child or a line hidden in an email said was saved as if the
owner had said it, at whatever confidence the AI chose. Now every write
records where it came from:

    stated_by  'owner'        the owner himself, with his own hands (a command
                              he typed and confirmed, /remember, or /confirm)
               'engine'       an AI wrote it down: noted by the AI, not yet
                              confirmed by him
               'imported'     the owner's own tools on this Mac (no AI at all)
               'unknown'      saved before JEFFEREY recorded this
               'owner_words'  (before round 7 only) an AI wrote it down, and an
                              older version read it as what he typed

THE OWNER'S WORDS ARE MADE ONLY BY THE OWNER (D2, round 7). Rounds 4 to 6
read what he typed, sentence by sentence, to decide whether an AI's note was
his own words — and every round a skeptic found a neighbour it misread ('My
grandson is in jail, the man on the phone said', 'I have diabetes, says
Karen', 'Pretend cost matters more than safety'). That reading is gone. An AI
can never mark a fact, a memory or a value as his words by itself: whatever
an engine writes is stored as noted by the AI, not yet confirmed — still used,
labelled as such, with its confidence capped. It becomes his only when he
confirms it with his own hands: /confirm in 'Talk to JEFFEREY on this Mac',
or `python connector/conscience.py confirm`. What he types as /remember <text>
is kept as exactly that, in his words. And an AI never turns round a value he
stated or one that is locked: that is a proposal, whatever he typed.

This module also says who will READ a result (`reader()`): the owner, his
caretaker key on an engine that stays in the house, or an engine somewhere
else — whose names the owner's rules may use ('anthropic', 'chatgpt').
"""

from __future__ import annotations

import time

import grounding

OWNER = "owner"
OWNER_WORDS = "owner_words"          # kept only to read what older versions stored
ENGINE = "engine"
IMPORTED = "imported"
UNKNOWN = "unknown"

# Stored on anything saved before JEFFEREY recorded who said what.
UNKNOWN_SOURCE = {"stated_by": UNKNOWN,
                  "note": "saved before JEFFEREY recorded who said what"}

# What an AI's note is called, wherever it is shown.
NOTED_BY_AI = "noted by the AI, not yet confirmed by him"

# The owner's turns at his own terminal: one conversation step each, so the
# same correction an AI repeats in a loop counts once (conscience). Only
# 'Talk to JEFFEREY on this Mac' counts them; over MCP and HTTP JEFFEREY never
# sees what the owner said. What he typed decides nothing about whose words a
# note is (D2, round 7).
_turn: int | None = None


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def owner_typed(text: str) -> None:
    """The owner typed something at his own terminal (it is about to be sent):
    a new turn. It never makes an AI's note his words (D2)."""
    new_turn()


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
    """For tests: forget the turns."""
    global _turn
    _turn = None


def _engine_label() -> str:
    try:
        import access
        import egress
        return egress._ENGINE or egress.engine_for(access.current_client())
    except Exception:
        return ""


def source(text=None, values=None, context=None) -> dict:
    """Where a write comes from, for the record kept beside it: the owner's
    own hands, his own tools with no AI, or an AI — whatever the AI wrote and
    whatever he typed before it (D2). `text`, `values` and `context` are
    accepted for the callers' sake and decide nothing."""
    import access
    if access.is_owner_console():
        by = OWNER
    elif access.GATE is None:
        by = IMPORTED
    else:
        by = ENGINE
    return {"by": access.who(), "surface": access.surface(),
            "engine": "" if by in (OWNER, IMPORTED) else _engine_label(),
            "stated_by": by, "at": _now()}


def status_for(src: dict) -> str:
    """'confirmed' when the owner said it (or his own tools wrote it);
    'pending' when an AI wrote it and he has not confirmed it."""
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
    return {OWNER: "you, yourself", OWNER_WORDS: "your own words (as an older version read them)",
            IMPORTED: "your own tools on this Mac",
            ENGINE: "noted by the AI — not yet confirmed by you",
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


# The owner's own caretaker key: his own agent. No rule of his about which
# PEOPLE may hear what ever applies to it (R2, round 6) — those rules govern
# everyone else; what it may see at all is still its key's scopes. But it is
# an AI: a rule that says no to an AI holds for it as for every other key
# that reaches an engine (D1, round 7).
OWNERS_KEY = "jefferey"


def reader() -> dict:
    """Who will read what a tool returns.

    owner        True when private facts may go: the owner's own hands, his
                 own tools, or his caretaker key on a model on this Mac
    own_key      the owner's own console or his caretaker key
    people_rules his rules about which people may hear what apply to this
                 reader (never to his own keys)
    caretaker    the key holds the owner's private life layer (life.read)
    media        the key may see pictures and recordings (media.read)
    audiences    every name the owner's rules may use for whoever reads it:
                 for every key that reaches an engine, 'any AI'
                 (grounding.AI_READER); for a key that is not his own, the
                 key's name and, for a rented engine, its maker's. Empty only
                 when the owner himself reads, at his own keyboard.
    """
    import access
    if access.owners_hands():
        return {"owner": True, "own_key": True, "people_rules": False,
                "client": access.who(), "caretaker": True, "media": True,
                "audiences": frozenset(), "in_house": True}
    client = access.current_client()
    caretaker = access.may("life.read")
    house = in_the_house()
    own = str(client or "").strip().lower() == OWNERS_KEY
    people = not own and not (house and caretaker)
    aud = {grounding.AI_READER}
    if people:
        aud.add(client)
        if not house:
            aud |= vendor_names(client)
    return {"owner": bool(house and caretaker), "own_key": own, "people_rules": people,
            "client": client, "caretaker": caretaker, "media": access.may("media.read"),
            "audiences": frozenset(aud), "in_house": house}
