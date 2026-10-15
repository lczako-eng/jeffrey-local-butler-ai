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
#
# Each message is kept whole: a fact or a memory he typed is his words, even
# when it tells what someone else said ('Mom said we would never go hungry',
# 'My doctor says I am allergic to penicillin') — only the words inside
# quotation marks are someone else's (R9, round 5: round 4 dropped every
# reported sentence, so his own life stories became 'an AI's words, not his
# own'). A RANKING is read more strictly: a sentence that reports what someone
# else thinks ('My sister says…', 'Karen's view is that…', 'My sister: …') is
# never his ranking, and any word of rejection anywhere in the message
# ('Never!', 'No way', 'I don't buy it', 'Ridiculous', 'said no one ever')
# means it is not his (R9: 'My sister says cost matters more than safety.
# Ridiculous.' made an AI's cost > safety his words).
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
_SENTENCES = re.compile(r"[.!?;\n]+|\s[-–—]+\s")
# Someone else's opinion, reported: 'my sister says', 'the doctor thinks',
# 'she has always said', 'according to Karen', 'ma soeur dit', 'Karen's view
# is'. His own ('I think', "I've always said", 'according to me', "let's say",
# 'like you said') is his.
_REPORTED_ANY = re.compile(r"\b(?:according to(?! (?:me|us)\b)|selon(?! (?:moi|nous)\b)"
                           r"|d'?apr[eè]s(?! (?:moi|nous)\b)|apparently|supposedly|allegedly"
                           r"|in (?!my\b|our\b)[^\W\d_]+'s (?:view|opinion|eyes|mind|book))\b",
                           re.I)
_REPORTER = re.compile(
    r"\b(?P<who>[^\W\d_]+)(?:'s|'ve|'d|'ll|'m)?\s+"
    r"(?:(?:has|have|had|always|often|keeps|keep|kept|also|really|still|just|once|would"
    r"|will|did|does|do|honestly|truly|personally|a|ne|n'a|m'a|m'avait|toujours)\s+)*"
    r"(?:says|said|say|saying|thinks|think|thought|believes|believe|believed|claims|claim"
    r"|claimed|insists|insist|insisted|reckons|reckon|reckoned|feels|felt|tells me|told me"
    r"|tell me|telling me|tells us|told us|telling us|telling|tells|wants me to|swears"
    r"|swore|argues|argued|maintains|suggests|suggested|wrote|writes|written|texted|emailed"
    r"|posted|goes on about|go on about|went on about|going on about|keeps saying"
    r"|dit|disait|pense|pensait|croit|croyait|trouve|affirme|pretend|prétend|écrit|ecrit"
    r"|a écrit|a ecrit)\b", re.I)
_OPINION_OF = re.compile(r"\b(?P<who>[^\W\d_]+)'s\s+(?:view|opinion|take|position|belief"
                         r"|feeling|idea|thinking|advice|argument)\b", re.I)
_HIS_OWN = frozenset("i we je j nous moi let my our".split())
_AGREEING = re.compile(r"\b(?:like|as) you (?:said|say)\b|\bcomme (?:tu|vous) (?:dis|dites)\b",
                       re.I)
_I_AGREE = re.compile(r"\b(?:i agree|and i agree|so do i|me too|i think so too"
                      r"|je suis d'?accord|moi aussi)\b", re.I)
# Any of these anywhere in the message: what it ranks is not his ranking.
_REJECTING = frozenset("""not never no nope less longer don't dont doesn't doesnt isn't isnt
    wasn't wasnt didn't didnt instead ne pas plus moins jamais non ridiculous ridicule
    nonsense rubbish absurd absurde wrong faux bull bullshit baloney hogwash laughable
    crazy silly yeah_right""".split())
# His own change of mind, in the first person: then a value he had stated
# himself is turned round at once, as he says (R9, round 5).
_CHANGED_MIND = re.compile(
    r"\b(?:i|i've|i have|i'?ve|we|we've)\s+(?:\w+\s+)?(?:changed my mind|changed our mind"
    r"|change my mind|reconsidered|rethought|decided)\b|\bon second thought\b"
    r"|\bmy mind (?:has )?changed\b|\bj'?ai chang[ée] d'?avis\b|\bje change d'?avis\b"
    r"|\bj'?ai (?:bien )?r[ée]fl[ée]chi\b|\bj'?ai d[ée]cid[ée]\b", re.I)


def _reported(piece: str) -> bool:
    n = grounding.normalise(piece)
    if _REPORTED_ANY.search(n) or any(m.group("who") not in _HIS_OWN
                                      for m in _OPINION_OF.finditer(n)):
        return True
    n = _AGREEING.sub(" ", n)
    return any(m.group("who") not in _HIS_OWN for m in _REPORTER.finditer(n))


# 'My sister: cost matters more than safety' — someone named, then what they
# say. 'Safety: it matters more than cost' and 'For the car: …' are his.
_SPEAKER = re.compile(r"^\s*(?P<label>[^:]{1,40}?)\s*:\s+(?P<rest>.+)$", re.S)


def _speaker(label: str) -> bool:
    ws = grounding.words(label)
    if not ws or len(ws) > 4:
        return False
    if {grounding.stem(w) for w in ws} & grounding.SOMEONE_WORDS:
        return True
    raw = label.strip().split()
    # 'Karen:' — a name standing alone
    return len(raw) == 1 and raw[0][:1].isupper() and raw[0][1:].islower()


def _rank_pieces(text: str) -> list[tuple[str, str]]:
    """His own sentences, for rankings: (label, sentence). A quoted or
    reported sentence is left out; a sentence 'X: …' keeps X as its label,
    so it can be read as the subject ('Safety: it matters…') or as the one
    speaking ('Karen: …')."""
    t = _QUOTED.sub(" | ", text)
    out: list[tuple[str, str]] = []
    for part in _SENTENCES.split(t):
        for piece in part.split("|"):
            if not piece.strip() or _reported(piece):
                continue
            m = _SPEAKER.match(piece)
            out.append((m.group("label"), m.group("rest")) if m else ("", piece))
    return out


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def owner_typed(text: str) -> None:
    """The owner typed this at his own terminal (it is about to be sent).
    It starts a new turn. A pasted message — e-mail headers, or text hidden
    in an HTML comment — is somebody else's words, so it never counts as his;
    nor do the words he puts in quotation marks."""
    global _turn
    _turn = (_turn or 0) + 1
    t = str(text or "")
    if _HEADERS.search(t):
        return
    t = _HIDDEN.sub(" ", t)
    ws = grounding.words(t)
    if not ws:
        return
    # which words are inside quotation marks that someone else said ('Karen
    # said "the cottage goes to Mike"'); his own motto in quotes is his
    quoted: list[bool] = []
    last = 0
    for m in _QUOTED.finditer(t):
        head = _SENTENCES.split(t[:m.start()])[-1]
        tail = _SENTENCES.split(t[m.end():])[0]
        theirs = _reported(head + " " + tail)
        quoted += [False] * len(grounding.words(t[last:m.start()]))
        quoted += [theirs] * len(grounding.words(m.group()))
        last = m.end()
    quoted += [False] * len(grounding.words(t[last:]))
    if len(quoted) != len(ws):                 # never trust a count that does not add up
        quoted = [False] * len(ws)
    low = grounding.normalise(t)
    own = set(grounding.words(low.replace("yeah right", "yeah_right")))
    pieces = [(lab, " ".join(grounding.words(x)), frozenset(grounding.content(x)),
               frozenset(grounding.content(lab)))
              for lab, x in _rank_pieces(t)]
    _messages.append({
        "words": ws, "quoted": quoted,
        "bag": frozenset(grounding.content(t)),
        "pieces": [p for p in pieces if p[1]],
        "rejects": bool(own & _REJECTING) or "said no one ever" in low
                   or "n'importe quoi" in low or "pas du tout" in low,
        "agrees": bool(_I_AGREE.search(low)),
        "changed_mind": bool(_CHANGED_MIND.search(low)),
        "reports": any(_reported(x) for x in _SENTENCES.split(_QUOTED.sub(" ", t)) if x.strip())
                   or bool(_QUOTED.search(t)),
        "all_pieces": [(lab, " ".join(grounding.words(x)), frozenset(grounding.content(x)),
                        frozenset(grounding.content(lab)))
                       for lab, x in ((m.group("label"), m.group("rest")) if m else ("", x)
                                      for x in _SENTENCES.split(_QUOTED.sub(" ", t))
                                      for m in [_SPEAKER.match(x)] if x.strip())],
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
# A sentence that turns a ranking round: 'not', 'less', 'no longer'.
_REVERSING = frozenset("""not never no less longer don't dont doesn't doesnt isn't isnt
    wasn't wasnt didn't didnt rather_not instead ne pas plus moins jamais""".split())


def verbatim(text) -> bool:
    """Is this, word for word (ignoring case and punctuation), something the
    owner typed at his terminal this session — in ONE message (two messages
    are never stitched together), not all of it inside quotation marks (what
    he quotes is someone else's), and not inside words that deny it ('I
    never said …', '… that is a lie')?"""
    ws = grounding.words(text)
    if not ws or not _messages:
        return False
    n = len(ws)
    for m in _messages:
        said, quoted = m["words"], m["quoted"]
        for i in range(len(said) - n + 1):
            if said[i:i + n] != ws:
                continue
            if all(quoted[i:i + n]):
                continue                       # only what he quotes: someone else's
            before = " ".join(said[:i])
            after = " ".join(said[i + n:])
            if not _DENIED_BEFORE.search(before) and not _DENIED_AFTER.match(after):
                return True
    return False


def said_by_owner(*values) -> bool:
    """Did the owner himself type every meaningful word of these values, in
    ONE message this session? ('safety' and 'cost' — he said both, together.)
    Words gathered from different messages never count (verify I-25)."""
    need: set[str] = set()
    for v in values:
        need |= grounding.content(v)
    return bool(need) and any(need <= m["bag"] for m in _messages)


def _ranks(said: str, hi: set, lo: set) -> bool:
    ws = said.split()
    if set(ws) & _REVERSING:
        return False
    stems = [grounding.stem(w) for w in ws]

    def first(group):
        want = {grounding.stem(w) for w in group}
        return min((i for i, w in enumerate(stems) if w in want), default=None)
    a, b = first(hi), first(lo)
    return a is not None and b is not None and a < b


def _backing(higher, lower) -> list[dict]:
    """The messages in which the owner himself put HIGHER before LOWER."""
    hi, lo = grounding.content(higher), grounding.content(lower)
    if not hi or not lo:
        return []
    out = []
    for m in _messages:
        if m["rejects"]:
            continue                       # 'Never!', 'Ridiculous', 'I don't buy it'
        pieces = m["all_pieces"] if m["agrees"] else m["pieces"]
        for label, said, bag, lab in pieces:
            if label and not (lab & (hi | lo)):
                if _speaker(label):
                    continue               # 'My sister: …' — what she says
            words = (" ".join(grounding.words(label)) + " " + said) if label else said
            if (hi | lo) <= (bag | lab) and _ranks(words.strip(), hi, lo):
                out.append(m)
                break
    return out


def ranked_by_owner(higher, lower) -> bool:
    """Did the owner himself put HIGHER before LOWER, in one sentence of his
    own, with no word that turns it round? 'safety matters more than cost'
    backs safety > cost — never cost > safety (verify I-25, I-48: the owner's
    own words were used to unlock their reversal) — and 'My sister says cost
    matters more than safety. Ridiculous.' backs nothing: it is his sister's
    ranking, which he rejects (R9). When in doubt, it is not his: the value
    waits for his yes."""
    return bool(_backing(higher, lower))


def changed_his_mind(higher, lower) -> bool:
    """Did the owner himself say he changed his mind, in the very message in
    which he put HIGHER before LOWER — first person, nothing quoted or
    reported in it ('I changed my mind. For the car, cost matters more than
    safety now')? Then turning round a value he had stated is his own doing."""
    return any(m["changed_mind"] and not m["reports"] for m in _backing(higher, lower))


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
