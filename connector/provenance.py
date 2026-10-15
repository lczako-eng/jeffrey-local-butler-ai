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
# sees what the owner said, only what the AI chose to send. Each message is
# kept as the sentences that are his own voice: words in quotation marks, and
# a sentence that reports what someone else says ('My sister says cost
# matters more than safety'), are somebody else's words even when he typed
# them (R9: that sentence, followed by 'Ridiculous.', made an AI's cost >
# safety 'his words' and reversed his own safety > cost).
_messages: list[dict] = []
_turn: int | None = None
_MAX_TYPED = 400

# What a pasted message looks like: it is somebody else's words, even when
# the owner pasted it (a scam email hiding '<!-- set_priority … -->').
_HIDDEN = re.compile(r"<!--.*?(?:-->|$)", re.S)
_HEADERS = re.compile(r"^\s*(?:from|to|subject|sent|date|cc|reply-to|de|à|objet|envoyé)\s*:",
                      re.I | re.M)
# Words in quotation marks — and in single quotes used as quotation marks,
# never an apostrophe ("Mom's").
_QUOTED = re.compile(r"[\"“”«»„‟][^\"“”«»„‟]*[\"“”«»„‟]?"
                     r"|(?:(?<=\s)|^)['‘][^'‘’\n]{2,}?['’](?=[\s.,!?;:)]|$)")
_SENTENCES = re.compile(r"[.!?;\n]+|\s[-–—]+\s|:\s")
# Someone else's opinion, reported: 'my sister says', 'the doctor thinks',
# 'she has always said', 'according to Karen', 'ma soeur dit'. His own ('I
# think', "I've always said", 'I really believe') is his.
_REPORTED_ANY = re.compile(r"\b(?:according to|selon|d'?apr[eè]s|apparently|supposedly"
                           r"|allegedly)\b", re.I)
_REPORTER = re.compile(
    r"\b(?P<who>[^\W\d_]+)(?:'s|'ve|'d|'ll|'m)?\s+"
    r"(?:(?:has|have|had|always|often|keeps|keep|kept|also|really|still|just|once|would"
    r"|will|did|does|do|honestly|truly|personally|a|ne|n'a|toujours)\s+)*"
    r"(?:says|said|say|saying|thinks|think|thought|believes|believe|believed|claims|claim"
    r"|claimed|insists|insist|insisted|reckons|reckon|feels|felt|tells me|told me|tell me"
    r"|wants me to|dit|disait|pense|pensait|croit|croyait|trouve|affirme|pretend)\b", re.I)
_HIS_OWN = frozenset("i we je j nous moi".split())


def _reported(piece: str) -> bool:
    n = grounding.normalise(piece)
    if _REPORTED_ANY.search(n):
        return True
    return any(m.group("who") not in _HIS_OWN for m in _REPORTER.finditer(n))


def _own_voice(text: str) -> list[list[str]]:
    """The owner's own sentences in what he typed, as runs: sentences next to
    each other stay together, a quoted or reported one breaks the run."""
    t = _QUOTED.sub(" | ", text)
    runs: list[list[str]] = [[]]
    for part in _SENTENCES.split(t):
        pieces = part.split("|")
        for k, piece in enumerate(pieces):
            if k:
                runs.append([])               # a quotation broke the sentence
            if not piece.strip():
                continue
            if _reported(piece):
                runs.append([])
                continue
            runs[-1].append(piece)
    return [r for r in runs if r]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def owner_typed(text: str) -> None:
    """The owner typed this at his own terminal (it is about to be sent).
    It starts a new turn. A pasted message — e-mail headers, or text hidden
    in an HTML comment — is somebody else's words, so it never counts as his;
    nor do the words he quotes, or what he reports someone else saying."""
    global _turn
    _turn = (_turn or 0) + 1
    t = str(text or "")
    if _HEADERS.search(t):
        return
    t = _HIDDEN.sub(" ", t)
    runs = _own_voice(t)
    sentences = [(" ".join(grounding.words(x)), frozenset(grounding.content(x)))
                 for run in runs for x in run]
    sentences = [(w, b) for w, b in sentences if w]
    if not sentences:
        return
    _messages.append({
        "runs": [" ".join(w for x in run for w in grounding.words(x)) for run in runs],
        "sentences": sentences,
        "bag": frozenset().union(*(b for _, b in sentences)),
    })
    del _messages[:-_MAX_TYPED]


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
    _messages.clear()
    _turn = None


# Words around a quote that turn it round: 'I never said Mike froze under
# fire, that is a lie' holds 'Mike froze under fire' but says the opposite
# (verify I-25).
_DENIED_BEFORE = re.compile(
    r"\b(?:never said|never told|didn'?t say|did not say|didnt say|not true|isn'?t true|"
    r"is not true|no one said|nobody said|never|not|no|it'?s a lie|that'?s a lie|a lie that|"
    r"false that|wrong that|deny|denied|denies|don'?t believe|do not believe|untrue|"
    r"rumou?r|they say|people say|claims?|claimed|accused|accuses|jamais|pas vrai|faux)"
    r"(?: \w+){0,3}\s*$")
_DENIED_AFTER = re.compile(
    r"^\s*(?:\w+ ){0,2}(?:is|was|that'?s|that is|which is|it'?s|its)? ?(?:a lie|a lie|not true|"
    r"false|untrue|wrong|nonsense|rubbish|a rumou?r|made up|never happened|faux|pas vrai)\b")
# A message that turns a ranking round: 'not', 'less', 'no longer'.
_REVERSING = frozenset("""not never no less longer don't dont doesn't doesnt isn't isnt
    wasn't wasnt didn't didnt rather_not instead ne pas plus moins jamais""".split())


def verbatim(text) -> bool:
    """Is this, word for word (ignoring case and punctuation), something the
    owner typed at his terminal this session — in ONE message (two messages
    are never stitched together), and not inside words that deny it ('I
    never said …', '… that is a lie')?"""
    ws = grounding.words(text)
    if not ws or not _messages:
        return False
    needle = " " + " ".join(ws) + " "
    for said in (run for m in _messages for run in m["runs"]):
        hay = f" {said} "
        i = hay.find(needle)
        while i >= 0:
            before, after = hay[:i + 1].strip(), hay[i + len(needle) - 1:]
            if not _DENIED_BEFORE.search(before) and not _DENIED_AFTER.match(after):
                return True
            i = hay.find(needle, i + 1)
    return False


def said_by_owner(*values) -> bool:
    """Did the owner himself type every meaningful word of these values, in
    ONE message this session? ('safety' and 'cost' — he said both, together.)
    Words gathered from different messages never count (verify I-25)."""
    need: set[str] = set()
    for v in values:
        need |= grounding.content(v)
    return bool(need) and any(need <= m["bag"] for m in _messages)


def ranked_by_owner(higher, lower) -> bool:
    """Did the owner himself put HIGHER before LOWER, in one sentence of his
    own, with no word that turns it round? 'safety matters more than cost'
    backs safety > cost — never cost > safety (verify I-25, I-48: the owner's
    own words were used to unlock their reversal) — and 'My sister says cost
    matters more than safety. Ridiculous.' backs nothing: it is his sister's
    ranking, which he rejects (R9). When in doubt, it is not his: the value
    waits for his yes."""
    hi, lo = grounding.content(higher), grounding.content(lower)
    if not hi or not lo:
        return False
    for said, bag in (x for m in _messages for x in m["sentences"]):
        if not (hi | lo) <= bag:
            continue
        ws = said.split()
        if set(ws) & _REVERSING:
            continue
        stems = [grounding.stem(w) for w in ws]

        def first(group):
            want = {grounding.stem(w) for w in group}
            return min((i for i, w in enumerate(stems) if w in want), default=None)
        a, b = first(hi), first(lo)
        if a is not None and b is not None and a < b:
            return True
    return False


def _engine_label() -> str:
    try:
        import access
        import egress
        return egress._ENGINE or egress.engine_for(access.current_client())
    except Exception:
        return ""


def source(text=None, values=None) -> dict:
    """Where a write comes from, for the record kept beside it. `values` is
    a ranking (higher, lower): it is his only if he put them in that order."""
    import access
    if access.is_owner_console():
        by = OWNER
    elif access.GATE is None:
        by = IMPORTED
    elif text is not None and verbatim(text):
        by = OWNER_WORDS
    elif values is not None and (ranked_by_owner(*values) if len(values) == 2
                                 else said_by_owner(*values)):
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
