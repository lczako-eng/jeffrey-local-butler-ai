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
# R9, round 6. What he typed never turns round a value he stated: only his
# own /confirm does (conscience.set_priority). What it decides is only whether
# an AI's new value or fact is HIS words (confirmed) or the AI's (a proposal
# he confirms). When in doubt, it is the AI's:
#
#   * a RANKING is his only when one of his sentences states it plainly — not
#     as a question ('Should cost matter more…?', 'I decided to ask you: does
#     …?', '… whether …', 'If cost mattered more…'), not as someone else's
#     words ('My sister says …', 'I read that …', 'Karen: …', words in
#     quotation marks), not doubted or turned round in that sentence ('I
#     doubt …', 'It is false that …', '… said no one ever'), and with no
#     sentence in the message that only rejects ('Never!', 'I don't buy it.',
#     'Hogwash.'). His everyday 'not', 'no more' or 'I don't want to skimp' in
#     another sentence is still his. A ranking said about one thing ('For the
#     car, …') is not his word about another ("Mom's care").
#   * a FACT is his words when it is what he typed, unless it is a claim he
#     reports from someone else ('The doctor thinks I have dementia, but I
#     don't believe it', 'My doctor says I am allergic to penicillin',
#     'Karen: "you drink too much"'), sits in a question or a message that
#     rejects it — a claim reported is his to confirm, never his confirmed
#     words. His whole story, as he typed it, is his ('Mom said we would never
#     go hungry, and we never did').
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
_SENTENCE_PARTS = re.compile(r"([^.!?;\n—–]*?(?:\s[-–—]+\s|[.!?;\n]+|$))")
# Someone else's opinion, reported: 'my sister says', 'the doctor thinks',
# 'she has always said', 'according to Karen', 'ma soeur dit', 'Karen's view
# is'. His own ('I think', "I've always said", 'according to me', "let's say")
# is his.
_REPORTED_ANY = re.compile(r"\b(?:according to(?! (?:me|us)\b)|selon(?! (?:moi|nous)\b)"
                           r"|d'?apr[eè]s(?! (?:moi|nous)\b)|apparently|supposedly|allegedly"
                           r"|reportedly|rumou?r has it|word is"
                           r"|in (?!my\b|our\b)[^\W\d_]+'s (?:view|opinion|eyes|mind|book)"
                           r"|i (?:have |'ve )?(?:read|heard|saw|was told)|we were told"
                           r"|i'?ve (?:read|heard)|on tv|on the news"
                           r"|j'?ai (?:lu|entendu)|on (?:m'a )?dit|il para[iî]t|à la t[ée]l[ée])\b",
                           re.I)
_REPORTER = re.compile(
    r"\b(?P<who>[^\W\d_]+)(?:'s|'ve|'d|'ll|'m)?\s+"
    r"(?:(?:used to|has|have|had|always|often|keeps|keep|kept|also|really|still|just|once"
    r"|would|will|did|does|do|honestly|truly|personally|a|ne|n'a|m'a|m'avait|toujours)\s+)*"
    r"(?P<verb>says|said|say|saying|thinks|think|thought|believes|believe|believed|claims"
    r"|claim|claimed|insists|insist|insisted|reckons|reckon|reckoned|feels|felt|feel|tells me"
    r"|told me|tell me|telling me|tells us|told us|telling us|telling|tells|told|wants me to"
    r"|swears|swore|argues|argued|maintains|suggests|suggested|wrote|writes|written|texted"
    r"|emailed|posted|goes on about|go on about|went on about|going on about|keeps saying"
    r"|dit|disait|disent|disaient|pense|pensait|pensent|croit|croyait|croient|trouve"
    r"|trouvent|affirme|affirment|pretend|prétend|prétendent|raconte|racontent|écrit|ecrit"
    r"|a écrit|a ecrit)\b", re.I)
_OPINION_OF = re.compile(r"\b(?P<who>[^\W\d_]+)'s\s+(?:view|opinion|take|position|belief"
                         r"|feeling|idea|thinking|advice|argument)\b", re.I)
_HIS_OWN = frozenset("i we je j nous moi let".split())
_PERSONS = frozenset("he she they someone everyone everybody people nobody".split())
_AGREEING = re.compile(r"\b(?:like|as) you (?:said|say)\b|\bcomme (?:tu|vous) (?:dis|dites)\b",
                       re.I)
_I_AGREE = re.compile(r"\b(?:i agree|and i agree|so do i|me too|i think so too"
                      r"|je suis d'?accord|moi aussi)\b", re.I)
# What dismisses someone else's view rather than reporting it ('…, never mind
# what Karen says').
_DISMISSED = re.compile(r"\b(?:never mind|regardless of|no matter|whatever|despite|peu importe)"
                        r"\s+(?:what|ce que)\s+[^\W\d_]+\s+(?:says|said|thinks|dit|pense)\b", re.I)
# Said to agree, not to reject ('no doubt about it', 'sans aucun doute').
_AFFIRMING = re.compile(r"\b(?:no doubt(?: about it)?|without (?:a|any) doubt|no question"
                        r"(?: about it)?|no questions asked|no way around it|no matter what"
                        r"|sans (?:aucun )?doute|pas de (?:discussion|doute)|no ifs or buts)\b",
                        re.I)
# A sentence that does nothing but reject ('Never!', 'I don't buy it.',
# 'Hogwash.', 'Me: no I don't.'): then nothing in the message is his ranking,
# and no claim in it is his word.
_REJECT_PHRASES = re.compile(
    r"\b(?:(?:i )?(?:don'?t|do not) (?:buy|believe|agree)(?: it| that| with (?:it|that))?"
    r"|not in a million years|over my dead body|said no (?:one|body) ever|hell no|no way"
    r"|not happening|not true|not at all|that'?s crazy|(?:are|you'?re|you must be) kidding"
    r"(?: me)?|give me a break|i (?:strongly )?disagree|i doubt (?:it|that)|i don'?t think so"
    r"|not me|not anymore|no longer|i won'?t|i don'?t|yeah,? right|and pigs fly"
    r"|when pigs fly|my foot|(?:je ne suis )?pas d'?accord|pas question|n'?importe quoi"
    r"|c'?est faux|pas du tout|jamais de la vie|mon (?:oe|œ)il|tu rigoles)\b", re.I)
_REJECT_WORDS = frozenset("""never no nope nah not ridiculous nonsense rubbish absurd wrong false
    baloney hogwash bull bullshit laughable crazy silly bogus garbage lies lie untrue jamais
    non ridicule faux absurde foutaise foutaises balivernes n'importe rej""".split())
_FILLER = frozenset("""i it its it's that that's thats this is so just absolutely totally
    completely utterly simply plain pure strongly really oh ah well yeah hell of course the a
    me you c c'est cest est ce du tout ca ça le la de mais and but frankly sir please haha lol
    what non merci""".split())
# Said in the sentence itself, it turns the ranking round.
_SARCASM = re.compile(r"\b(?:said no (?:one|body) ever|yeah,? right|over my dead body|pigs fly"
                      r"|my foot|in your dreams|dit personne|mon (?:oe|œ)il)\b|\bas if\b", re.I)
# Before the ranking, these make it a question, a doubt, a past belief or a
# supposition — never his plain statement.
_NOT_PLAIN_BEFORE = re.compile(
    r"\b(?:whether|if|unless|suppose|supposing|imagine|what if|si|est-ce que|doubt|doubts"
    r"|disagree|disagrees|false|untrue|used to|who says|nobody thinks|no one thinks|as if)\b",
    re.I)
_QUESTION_START = frozenset("""do does did should would could can is are shall why how what
    which whether""".split())
# A ranking word turned round: 'not', 'less', 'no longer', 'doubt'.
_REVERSING = frozenset("""not never no less longer don't dont doesn't doesnt isn't isnt
    wasn't wasnt didn't didnt rather_not instead ne pas moins jamais doubt doubts disagree
    false untrue""".split())


def _reported(piece: str) -> bool:
    """Does this piece of what he typed report someone else's view?"""
    n = grounding.normalise(_DISMISSED.sub(" ", piece))
    if _REPORTED_ANY.search(n) or any(m.group("who") not in _HIS_OWN
                                      for m in _OPINION_OF.finditer(n)):
        return True
    n = _AGREEING.sub(" ", n)
    for m in _REPORTER.finditer(n):
        who = m.group("who")
        if who in _HIS_OWN:
            continue
        if m.group("verb").startswith(("feel", "felt")):
            # 'my son feels cost matters more', never 'the house feels cold'
            if not ({grounding.stem(who)} & grounding.SOMEONE_WORDS or who in _PERSONS
                    or re.search(r"\b" + re.escape(who) + r"\b", piece, re.I)
                    and re.search(r"\b[A-Z]" + re.escape(who[1:]) + r"\s+(?:feels|felt)\b",
                                  piece)):
                continue
        return True
    return False


# 'My sister: cost matters more than safety' — someone named, then what they
# say. 'Safety: it matters more than cost', 'For the car: …' and 'Me: …' are his.
_SPEAKER = re.compile(r"^\s*(?P<label>[^:]{1,40}?)\s*:\s+(?P<rest>.+)$", re.S)


def _speaker(label: str) -> bool:
    ws = grounding.words(label)
    if not ws or len(ws) > 4 or set(ws) & {"i", "me", "moi", "je", "we", "nous"}:
        return False
    if {grounding.stem(w) for w in ws} & grounding.SOMEONE_WORDS:
        return True
    raw = label.strip().split()
    # 'Karen:' — a name standing alone
    return len(raw) == 1 and raw[0][:1].isupper() and raw[0][1:].islower()


def _sentences(t: str) -> list[dict]:
    """His message, sentence by sentence: the text, whether it asks, and
    where its words are among the message's words."""
    out, at = [], 0
    for part in _SENTENCE_PARTS.findall(t):
        if not part.strip():
            continue
        ws = grounding.words(part)
        body = part.rstrip()
        q = "?" in body[-3:] or (bool(ws) and ws[0] in _QUESTION_START)
        out.append({"text": part, "start": at, "end": at + len(ws), "question": q})
        at += len(ws)
    return out


def _pure_rejection(sentence: str) -> bool:
    """A sentence that only rejects: after the words that agree, only words
    of rejection and little words are left, and at least one rejects."""
    s = _AFFIRMING.sub(" ", grounding.normalise(sentence))
    s = _REJECT_PHRASES.sub(" rej ", s)
    m = _SPEAKER.match(s)
    if m and set(grounding.words(m.group("label"))) & {"me", "moi"}:
        s = m.group("rest")
    ws = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", s)
    return bool(ws) and all(w in _REJECT_WORDS or w in _FILLER for w in ws) \
        and any(w in _REJECT_WORDS for w in ws)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def owner_typed(text: str) -> None:
    """The owner typed this at his own terminal (it is about to be sent).
    It starts a new turn. A pasted message — e-mail headers, or text hidden
    in an HTML comment — is somebody else's words, so it never counts as his;
    nor do the words he puts in someone else's quotation marks."""
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
    # said "the cottage goes to Mike"', 'Karen: "you drink too much"'); his
    # own motto in quotes ('I always say "…"', 'My motto is "…"') is his
    quoted: list[bool] = []
    last = 0
    for m in _QUOTED.finditer(t):
        head = _SENTENCES.split(t[:m.start()])[-1]
        tail = _SENTENCES.split(t[m.end():])[0]
        sp = re.match(r"^\s*(?P<label>[^:]{1,40}?)\s*:\s*$", head)
        theirs = _reported(head + " " + tail) or bool(sp and _speaker(sp.group("label")))
        quoted += [False] * len(grounding.words(t[last:m.start()]))
        quoted += [theirs] * len(grounding.words(m.group()))
        last = m.end()
    quoted += [False] * len(grounding.words(t[last:]))
    if len(quoted) != len(ws):                 # never trust a count that does not add up
        quoted = [False] * len(ws)
    sents = _sentences(t)
    if not sents or sents[-1]["end"] != len(ws):
        sents = [{"text": t, "start": 0, "end": len(ws), "question": "?" in t.rstrip()[-3:]}]
    low = grounding.normalise(t)
    # where a sentence only rejects: it rejects what was said before it ('Cost
    # matters more than safety? Never!'), not what he says after it ('No.
    # Safety matters more than cost.' answers the question he was asked)
    rejected = [k for k, s in enumerate(sents) if _pure_rejection(s["text"])]
    _messages.append({
        "text": t, "words": ws, "quoted": quoted, "sentences": sents,
        "bag": frozenset(grounding.content(t)),
        "sarcasm": bool(_SARCASM.search(low)),
        "rejected_after": max(rejected) if rejected else -1,
        "agrees": bool(_I_AGREE.search(low)),
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
    r"false that|wrong that|deny|denied|denies|don'?t believe|do not believe|dont believe|"
    r"don'?t think|do not think|dont think|doubt|untrue|"
    r"rumou?r|they say|people say|claims?|claimed|accused|accuses|jamais|pas vrai|faux)"
    r"(?: \w+){0,3}\s*$")
_DENIED_AFTER = re.compile(
    r"^\s*(?:\w+ ){0,2}(?:is|was|that'?s|that is|which is|it'?s|its)? ?(?:a lie|a lie|not true|"
    r"false|untrue|wrong|nonsense|rubbish|a rumou?r|made up|never happened|faux|pas vrai)\b")


def _sentence_at(m: dict, i: int) -> dict:
    for s in m["sentences"]:
        if s["start"] <= i < s["end"]:
            return s
    return m["sentences"][-1]


def _framed(m: dict, s: dict, i: int) -> bool:
    """Is the claim that starts at word `i` someone else's, as he reports it?
    A reporting frame right before it in its sentence ('the doctor thinks',
    'Karen keeps telling me', 'according to the bank'), a speaker's label
    before speech ('Karen: you …'), or a question."""
    if s["question"]:
        return True
    frame = " ".join(m["words"][s["start"]:i])
    if _REPORTED_ANY.search(frame):
        return True
    for r in _REPORTER.finditer(frame):
        if r.group("who") in _HIS_OWN:
            continue
        if len(frame[r.end():].split()) <= 3 and _reported(frame[r.start():]):
            return True
    sp = _SPEAKER.match(s["text"])
    if sp and {grounding.stem(w) for w in grounding.words(sp.group("label"))} \
            & grounding.SOMEONE_WORDS:
        rest = grounding.words(sp.group("rest"))
        if rest[:1] and rest[0] in ("i", "you", "we", "je", "tu", "vous", "j"):
            return True                        # 'Karen: you drink too much'
    return False


def verbatim(text) -> bool:
    """Is this, word for word (ignoring case and punctuation), something the
    owner typed at his terminal this session, as his own words — in ONE
    message (two messages are never stitched together)? Not when it is only
    what someone else says in it (in their quotation marks, or reported:
    'the doctor thinks …'), sits in a question, or the message rejects it
    ('I never said …', '… Ridiculous.'). His whole message is always his."""
    ws = grounding.words(text)
    if not ws or not _messages:
        return False
    n = len(ws)
    for m in _messages:
        said, quoted = m["words"], m["quoted"]
        for i in range(len(said) - n + 1):
            if said[i:i + n] != ws:
                continue
            if i == 0 and n == len(said):
                return True                    # his whole message, as he typed it
            s = _sentence_at(m, i)
            if any(quoted[i:i + n]) or m["sarcasm"] or m["rejected_after"] > \
                    m["sentences"].index(s):
                continue
            if i > s["start"] and _framed(m, s, i) or i == s["start"] and s["question"]:
                continue
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


def _ranks(clauses: list[list[str]], hi: set, lo: set) -> bool:
    """HIGHER before LOWER, with no word that turns it round between the
    start of HIGHER's clause and LOWER ('Cost doesn't matter to me, safety
    matters more than cost' ranks safety over cost; 'I don't think safety
    matters more than cost' does not)."""
    flat = [(k, w) for k, c in enumerate(clauses) for w in c]
    stems = [grounding.stem(w) for _, w in flat]
    want_hi = {grounding.stem(w) for w in hi}
    want_lo = {grounding.stem(w) for w in lo}
    for i, s in enumerate(stems):
        if s not in want_hi:
            continue
        j = next((j for j in range(i + 1, len(stems)) if stems[j] in want_lo), None)
        if j is None:
            return False
        start = next(x for x in range(len(flat)) if flat[x][0] == flat[i][0])
        window = {w for _, w in flat[start:j + 1]}
        if not window & _REVERSING:
            return True
    return False


_FOR_SOMEONE = re.compile(r"^\s*(?:for|pour|to|à)\s+(?P<who>[^,]{1,30}?)\s*,", re.I)


def _plain_ranking(m: dict, s: dict, hi: set, lo: set) -> bool:
    """Does this sentence of his state HIGHER over LOWER plainly, as his own?"""
    if s["question"]:
        return False
    text = _QUOTED.sub(" ¦ ", s["text"])
    for piece in text.split("¦"):
        if not piece.strip():
            continue
        label = ""
        sp = _SPEAKER.match(piece)
        if sp:
            label, piece = sp.group("label"), sp.group("rest")
            lab = grounding.content(label)
            if _speaker(label) and not (lab & (hi | lo)):
                continue                       # 'My sister: …' — what she says
        low = grounding.normalise(piece)
        if _SARCASM.search(low):
            continue
        if not m["agrees"] and (_reported(piece) or (label and _reported(label))):
            continue
        fs = _FOR_SOMEONE.match(piece)
        if fs and "'" not in fs.group("who") and _speaker(fs.group("who")) and not (
                grounding.content(fs.group("who")) & (hi | lo)):
            continue                           # 'Pour Karen, le coût compte plus…'
        first_hi = min((i for i, w in enumerate(grounding.words(low))
                        if grounding.stem(w) in {grounding.stem(x) for x in hi}), default=None)
        if first_hi is not None:
            head = " ".join(grounding.words(low)[:first_hi])
            if _NOT_PLAIN_BEFORE.search(head):
                continue
        clauses = [grounding.words(c) for c in re.split(r"[,:]", (label + ", " if label else "")
                                                         + piece)]
        if (hi | lo) <= set().union(*map(grounding.content, map(" ".join, clauses))) \
                and _ranks(clauses, hi, lo):
            return True
    return False


def _backing(higher, lower, context=None) -> list[dict]:
    """The messages in which the owner himself plainly put HIGHER before
    LOWER — about this context, when he named one."""
    hi, lo = grounding.content(higher), grounding.content(lower)
    if not hi or not lo:
        return []
    ctx = grounding.content(context) - hi - lo if context else set()
    out = []
    for m in _messages:
        if m["sarcasm"]:
            continue                       # '… said no one ever', '… and pigs fly'
        if ctx and not ctx <= m["bag"]:
            continue                       # what he said about the car, not Mom's care
        # not one he rejects after saying it ('Never!', 'Ridiculous', 'I don't buy it')
        if any(_plain_ranking(m, s, hi, lo) for k, s in enumerate(m["sentences"])
               if k >= m["rejected_after"]):
            out.append(m)
    return out


def ranked_by_owner(higher, lower, context=None) -> bool:
    """Did the owner himself put HIGHER before LOWER, plainly, in one
    sentence of his own — not a question, not someone else's words, not
    rejected — and, when the value is about something, about that? 'safety
    matters more than cost' backs safety > cost — never cost > safety
    (verify I-25, I-48) — and 'My sister says cost matters more than safety.
    Ridiculous.' backs nothing (R9). When in doubt, it is not his: the value
    waits for his yes."""
    return bool(_backing(higher, lower, context))


def _engine_label() -> str:
    try:
        import access
        import egress
        return egress._ENGINE or egress.engine_for(access.current_client())
    except Exception:
        return ""


def source(text=None, values=None, context=None) -> dict:
    """Where a write comes from, for the record kept beside it. `values` is
    a ranking (higher, lower): it is his only if he put them in that order,
    plainly, about this `context`."""
    import access
    if access.is_owner_console():
        by = OWNER
    elif access.GATE is None:
        by = IMPORTED
    elif text is not None and verbatim(text):
        by = OWNER_WORDS
    elif values is not None and (ranked_by_owner(*values, context=context) if len(values) == 2
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


# The owner's own caretaker key: his own agent. No rule of his about who may
# hear what ever applies to it (R2, round 6) — those rules govern everyone
# else; what it may see at all is still its key's scopes.
OWNERS_KEY = "jefferey"


def reader() -> dict:
    """Who will read what a tool returns.

    owner      True when no rule needs applying: the owner's own hands, his
               own tools, or his caretaker key on a model on this Mac. Then
               everything he may see goes, private facts included.
    own_key    the owner's own console or his caretaker key: his rules about
               who may hear what never apply (audiences is empty)
    caretaker  the key holds the owner's private life layer (life.read)
    media      the key may see pictures and recordings (media.read)
    audiences  every name the owner's rules may use for whoever reads it —
               the key's name and, for a rented engine, its maker's
    """
    import access
    if access.owners_hands():
        return {"owner": True, "own_key": True, "client": access.who(), "caretaker": True,
                "media": True, "audiences": frozenset(), "in_house": True}
    client = access.current_client()
    caretaker = access.may("life.read")
    house = in_the_house()
    own = str(client or "").strip().lower() == OWNERS_KEY
    aud = set() if own else {client}
    if not house and not own:
        aud |= vendor_names(client)
    return {"owner": bool(house and caretaker), "own_key": own, "client": client,
            "caretaker": caretaker, "media": access.may("media.read"),
            "audiences": frozenset(aud), "in_house": house}
