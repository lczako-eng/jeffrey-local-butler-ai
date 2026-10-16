"""
Grounding — whole words, what kind of private, and who is listening
====================================================================

Three small things JEFFEREY needs everywhere, kept in one place so every
surface answers the same way (the October 2026 stress test):

1. **Whole words (I-28).** Grounding used to match fragments of words: 'car'
   grounded a caregiver choice, 'art' grounded heart surgery, 'rent' pulled a
   PTSD medication into a letter to a landlord (from cuRRENT), an empty
   context grounded everything, and 'booking a flight to Calgary' found
   nothing. Now text is split into whole words, lower-cased and lightly
   stemmed (flights → flight, booking → book, Mom's → mom), the little words
   ('the', 'my', 'write', 'letter') are ignored, and a subject that names
   nothing is refused instead of matched against everything.

2. **What kind of private (I-11).** A fact about health, money, children,
   the safety of the home, or someone else's confidence is private by
   default: only the owner's own caretaker key sees it, and only when the
   subject names it.

3. **Who is listening (I-24).** 'karen', 'Karen Novak' and
   'Karen Novak <karen@example.com>' are the same person to the owner's
   rules. A rule that says NO matches every way she can be written; a rule
   that says YES must match her exactly. When in doubt, the answer is no.
"""

from __future__ import annotations

import functools
import re
import unicodedata

# ------------------------------------------------------------------ words
_QUOTES = str.maketrans({"‘": "'", "’": "'", "ʼ": "'", "`": "'",
                         "´": "'", "“": '"', "”": '"'})
# Scripts written without spaces between words: Chinese, Japanese kana,
# Thai, Lao, Khmer, Myanmar. A sentence there is one long run of letters, so
# it is read as overlapping pairs of characters ('我女儿住在多伦多' → 我女,
# 女儿, 儿住 …): most Chinese words are two characters, and a pair on both
# sides of a comparison finds them (learning-30: every Chinese and Japanese
# lookup used to find nothing).
_SPACELESS = ("฀-໿က-႟ក-៿々぀-ヿ"
              "ㇰ-ㇿ㐀-䶿一-鿿豈-﫿"
              "\U00020000-\U0002ffff")
_TOKEN = re.compile(r"(?P<run>[" + _SPACELESS + r"]+)"
                    r"|(?P<w>[^\W_" + _SPACELESS + r"]+(?:'[^\W_" + _SPACELESS + r"]+)*)"
                    r"|(?P<sym>[^\w\s])")
_RUN = re.compile("[" + _SPACELESS + "]")

# Little words that never decide what something is about — in English and
# the French a Canadian owner may write in — and the words of the task
# itself ('write a letter to…'), which say what to do, not what about.
STOP = frozenset("""
a an the and or but nor of to in on at for with without about above below from by
as into onto over under up down out off than then so if is are was were be been
being am do does did done doing have has had having it its this that these those
there here what which who whom whose when where why how all any each every both
few more most other some such no not only own same too very can could will would
shall should may might must just also again further once ever still even yet
i me my mine myself we us our ours you your yours he him his she her hers they
them their theirs one ones thing things something anything everything nothing
someone anyone everyone get got gets getting make makes made let lets please
need needs want wants like likes write writes writing written wrote letter
letters email emails message messages reply replies draft drafts note notes
send sending sent ask asking asked tell telling told say saying said help helping
le la les un une des du de et ou en au aux mon ma mes ton ta tes son sa ses est
sont je tu il elle nous vous ils elles ce cet cette ces qui que quoi pour par avec
sans sur dans pas plus
oh uh eh ok hi yo ah ha ya mr mrs ms dr st pm vs eg ie re ne se te si ni ça là
el lo es da im um zu az
""".split())


def _is_symbol(tok: str) -> bool:
    """A picture-word: an emoji or a symbol like ♥ (not punctuation)."""
    return len(tok) == 1 and unicodedata.category(tok) == "So"


# Round 9 (G5): the code points Unicode calls default-ignorable — invisible,
# never a letter, never a space — read as nothing by every reader of words.
# Round 8's fold dropped only the 'format' characters, so a variation
# selector (U+FE0F), the combining grapheme joiner (U+034F) or a Hangul
# filler inside a word hid it from every reader: 'I take Ozem️pic',
# 'Pass️word: Tulip7392', 'Jo is on che️mo', 'Let the plumber
# i️n', 'Turn off the al͏arm'.
#
# Round 9 repair (G5): three more that are not default-ignorable but show as
# nothing or as a blank — U+2800 (the braille blank), U+FFFC (the object
# replacement character) and U+1D159 (the musical null notehead): 'Let the
# plumber i⠀n' was allowed, 'I take Ozem⠀pic' reached every AI past his
# no, and an engine handed in 'My PIN is 7⠀7⠀3⠀1'.
IGNORABLE_RANGES = ((0x00AD, 0x00AD), (0x034F, 0x034F), (0x061C, 0x061C), (0x115F, 0x1160),
                    (0x17B4, 0x17B5), (0x180B, 0x180F), (0x200B, 0x200F), (0x202A, 0x202E),
                    (0x2060, 0x206F), (0x2800, 0x2800), (0x3164, 0x3164), (0xFE00, 0xFE0F),
                    (0xFEFF, 0xFEFF), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8), (0xFFFC, 0xFFFC),
                    (0x1BCA0, 0x1BCA3), (0x1D159, 0x1D159), (0x1D173, 0x1D17A),
                    (0xE0000, 0xE0FFF))
IGNORABLE_CLASS = "".join(f"\\U{a:08x}" if a == b else f"\\U{a:08x}-\\U{b:08x}"
                          for a, b in IGNORABLE_RANGES)
_IGNORABLE = re.compile("[" + IGNORABLE_CLASS + "]")


def is_ignorable(ch: str) -> bool:
    """Is this one character one that shows as nothing (G5)?"""
    cp = ord(ch)
    return any(a <= cp <= b for a, b in IGNORABLE_RANGES)


def visible(text) -> str:
    """The text with every code point that shows as nothing taken out (G5)."""
    t = str(text or "")
    return t if t.isascii() else _IGNORABLE.sub("", t)


# ---------------------------------------- read both ways (round 9 repair, G5)
# A character that shows as nothing may stand inside a word ('i⠀n',
# 'Ozem​pic') or between two words, where it shows as their space
# ('Unlock​the​front​door', 'MyㅤPINㅤisㅤ7731'). Read only as
# nothing, the second glues the words together and hides them — the door
# allowed 'Unlock​the​front​door'; read only as a space, the first
# splits the word. So every reader that decides something (the door, what
# kind of private a text is, a rule's topic, a draft, the secrets) reads a
# text that holds one both ways, and finds what either reading finds.
#
# Round 9, second repair: WHAT IS HIDDEN IS WHAT THE FOLD READS AS NOTHING.
# Two lists drifted: the fold read U+16FE4 (a Khitan filler, a combining
# mark that shows as nothing) as nothing, but has_hidden did not count it,
# so 'Unlock<16FE4>the<16FE4>front<16FE4>door' was never also read with
# spaces and the door allowed it. Now a character is hidden exactly when the
# shared fold reads it as nothing (a format character, a filler, a variation
# selector, a combining mark standing on its own), so the two cannot differ.
def _hidden(ch: str) -> bool:
    return not ch.isascii() and _fold_char(ch, False) == ""


def has_hidden(text) -> bool:
    """Does this text hold a character that shows as nothing (G5) — any
    character the shared fold reads as nothing?"""
    t = str(text or "")
    return not t.isascii() and any(_hidden(ch) for ch in t if not ch.isascii())


def spaced(text) -> str:
    """The text with every character that shows as nothing read as a space —
    one for one, so every place in it stays where it was."""
    t = str(text or "")
    return t if t.isascii() else "".join(" " if not ch.isascii() and _hidden(ch) else ch
                                         for ch in t)


def readings(text) -> tuple[str, ...]:
    """The ways a reader that decides something reads this text: as written
    — or, when it holds a character that shows as nothing, with each of them
    read as nothing, and again with each read as a space."""
    t = str(text or "")
    if not has_hidden(t):
        return (t,)
    return ("".join(ch for ch in t if ch.isascii() or not _hidden(ch)), spaced(t))


@functools.lru_cache(maxsize=1 << 16)
def _normalise(t: str) -> str:
    t = unicodedata.normalize("NFKC", visible(t)).translate(_QUOTES).casefold()
    return re.sub(r"\s+", " ", t).strip()


def normalise(text) -> str:
    """One spelling for the same words: compatible characters folded,
    straight quotes, case folded, runs of space made one."""
    return _normalise(str(text or ""))


# ------------------------------------------------------------------- fold
# Round 8 (engineer 2): ONE reader for letters that look like Latin ones,
# shared by every reader that still reads words — who a 'no' is for (F1),
# the health words (F2), the words that announce a secret (F3, egress), the
# names on a card statement (F4, guardian), a draft (F5) and the door words
# (F6, conscience). Each round before, every reader kept its own table and a
# skeptic found the letter it missed: 'Сlaude' with a Cyrillic С, 'Unlօck
# the dօօr' in Armenian, 'Ꮮet him in' in Cherokee, 'ʟet the plumber ɪn' in
# small capitals, 'Cl4ude', 'p@ssword', 'Iet him in', '|et the man |n', 'P I
# N', 'le t him in'.
#
# What is read, letter by letter: compatible forms (NFKC: full-width and
# mathematical letters, ligatures), Cyrillic, Greek, Armenian and Cherokee
# letters that look like Latin ones, every LATIN LETTER SMALL CAPITAL, digits
# of every script, dashes and quotes; zero-width characters are dropped and,
# unless asked to keep them, accents.
#
# What is read word by word — and ONLY when the result is a word the reader
# knows, so 'Hunter22', 'gpt4o', 'A1C' and 'If' stay themselves: digits and
# @ $ | ! written for letters, a capital I written for l, letters spaced out
# or dotted ('C l a u d e', 'A.I.'), a word split by a space ('le t'), and a
# hyphenated name ('Chat-GPT').
def _pairs(src: str, dst: str) -> dict:
    assert len(src) == len(dst), (src, dst)
    return dict(zip(src, dst))


_LOOK = {
    # Cyrillic
    **_pairs("АВЕКМНОРСТХУІЈЅаеорсухіјѕԁһӏԛԝвкмнтүӀԜҮЅԌ",
             "ABEKMHOPCTXYIJSaeopcyxijsdhlqwbkmhtylWYSG"),
    # Greek
    **_pairs("ΑΒΕΖΗΙΚΜΝΟΡΤΥΧαβεικνορτυχγϲϳ", "ABEZHIKMNOPTYXabeikvoptuxycj"),
    # Armenian
    **_pairs("օսհոցզռյգաՕՍՏԼ", "ouhngqnjqwOUSL"),
}
# Cherokee capitals that look like Latin ones, and their small forms
_CHEROKEE = {chr(cp): v for cp, v in (
    (0x13A0, "D"), (0x13A1, "R"), (0x13A2, "T"), (0x13A5, "i"), (0x13A9, "Y"), (0x13AA, "A"),
    (0x13AB, "J"), (0x13AC, "E"), (0x13B3, "W"), (0x13B7, "M"), (0x13BB, "H"), (0x13C0, "G"),
    (0x13C2, "h"), (0x13C3, "Z"), (0x13CF, "b"), (0x13D2, "R"), (0x13D4, "W"), (0x13D5, "S"),
    (0x13D9, "V"), (0x13DA, "S"), (0x13DE, "L"), (0x13DF, "C"), (0x13E2, "P"), (0x13E6, "K"),
    (0x13F3, "G"), (0x13F4, "B"))}
_LOOK.update(_CHEROKEE)
_LOOK.update({chr(0xAB70 + ord(c) - 0x13A0): v.lower() for c, v in _CHEROKEE.items()
              if 0x13A0 <= ord(c) < 0x13F0})
_LOOK.update({chr(0x13F8 + ord(c) - 0x13F0): v.lower() for c, v in _CHEROKEE.items()
              if 0x13F0 <= ord(c) <= 0x13F5})
_DASH_CHARS = frozenset("‐‑‒–—―−﹘﹣－")
_QUOTE_CHARS = frozenset("‘’‚‛′ʼ`´")
_SPECIAL = {"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O", "ß": "ss",
            "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ı": "i", "ȷ": "j"}
_SMALL_CAP = "LATIN LETTER SMALL CAPITAL "


def _mark(c: str) -> bool:
    """A combining mark of any kind — nonspacing, spacing or enclosing (G5:
    'chë̱mo', 'e⃝'). Some of them have no combining class, so
    the class alone missed them."""
    return unicodedata.category(c).startswith("M")


@functools.lru_cache(maxsize=1 << 14)
def _fold_char(ch: str, accents: bool) -> str:
    if unicodedata.category(ch) == "Cf" or is_ignorable(ch):
        return ""          # zero-width spaces, soft hyphens, variation selectors, fillers (G5)
    if ch.isspace():
        return " "         # a line or paragraph separator is a space too (G5 repair: 'i n')
    if ch in _LOOK:
        return _LOOK[ch]
    if ch.isdecimal():
        try:
            return str(unicodedata.decimal(ch))
        except ValueError:
            pass
    out = []
    for c in unicodedata.normalize("NFKC", ch):
        if c.isascii():
            out.append(c)
        elif c in _LOOK:
            out.append(_LOOK[c])
        elif c in _DASH_CHARS:
            out.append("-")
        elif c in _QUOTE_CHARS:
            out.append("'")
        elif c in _SPECIAL:
            out.append(_SPECIAL[c])
        elif unicodedata.name(c, "").startswith(_SMALL_CAP) and \
                len(unicodedata.name(c)) == len(_SMALL_CAP) + 1:
            out.append(unicodedata.name(c)[-1].lower())
        elif _mark(c) or is_ignorable(c):
            continue                              # a combining mark on its own (G5)
        elif not accents:
            # every combining mark after decomposition (G5): 'é' is 'e'
            base = "".join(x for x in unicodedata.normalize("NFKD", c)
                           if not _mark(x) and not is_ignorable(x))
            out.append("".join(_LOOK.get(x, x) for x in base) or c)
        else:
            out.append(c)
    return "".join(out)


_LEET = {"0": "o", "1": "li", "2": "z", "3": "e", "4": "a", "5": "s", "6": "gb", "7": "t",
         "8": "b", "9": "g", "@": "a", "$": "s", "|": "li", "!": "il", "I": "l"}
_LEET_TOKEN = re.compile(r"(?:[^\W_]|[@$|!])+")
_LEET_CHARS = frozenset(_LEET)
_HYPHENED = re.compile(r"(?<![^\W_])[^\W_]+(?:-[^\W_]+)+(?![^\W_])")
_SPACED_RUN = re.compile(r"(?<![^\W_])[^\W\d_](?:(?:\. |[ .\-·])[^\W\d_]){1,15}\.?(?![^\W_])")
_LONE = frozenset("a i y o e u à á è é ô".split())
_SPLIT = re.compile(r"(?<!\S)([^\W\d_]{1,12}) ([^\W\d_])(?=[\s.,;:!?]|$)"
                    r"|(?<!\S)([^\W\d_]) ([^\W\d_]{1,12})(?=[\s.,;:!?]|$)")


def _knows(known, w: str) -> bool:
    return (w in known) if isinstance(known, frozenset) else bool(known(w))


def _deleet(tok: str, known) -> str | None:
    """The word a token with digits or symbols for letters spells, if the
    reader knows it — same length, letter for letter — or None."""
    if not any(c.isalpha() for c in tok) or _knows(known, tok.lower()):
        return None
    at = [i for i, c in enumerate(tok) if c in _LEET]
    if not at or len(at) > 8:
        return None
    options = [(_LEET[tok[i]] + ("i" if tok[i] == "I" else "")) for i in at]
    best = None

    def walk(k: int, cur: list[str]) -> bool:
        nonlocal best
        if k == len(at):
            w = "".join(cur).lower()
            if _knows(known, w):
                best = "".join(cur)
                return True
            return False
        for o in options[k]:
            cur[at[k]] = o
            if walk(k + 1, cur):
                return True
        cur[at[k]] = tok[at[k]]
        return False

    walk(0, list(tok))
    return best


def _edit(t: str, src: list[int] | None, repl: dict[int, str], drop: set[int]
          ) -> tuple[str, list[int] | None]:
    if not repl and not drop:
        return t, src
    if src is None:
        src = list(range(len(t)))
    out, where = [], []
    for i, ch in enumerate(t):
        if i in drop:
            continue
        out.append(repl.get(i, ch))
        where.append(src[i])
    return "".join(out), where


def fold_map(text: str, known=None, accents: bool = False) -> tuple[str, list[int]]:
    """`text` read as Latin letters (see above), case kept, and where each
    character of the result came from in `text`. `known` (a frozenset of
    lower-case words, or a function of one) says which words this reader
    knows; without it only letters are folded, never words."""
    text = str(text or "")
    src: list[int] | None
    if text.isascii():
        t, src = text, None                       # built only if a word is changed
    else:
        chars: list[str] = []
        src = []
        for i, ch in enumerate(text):
            f = ch if ch.isascii() else _fold_char(ch, accents)
            chars.append(f)
            src.extend([i] * len(f))
        t = "".join(chars)
    if known is None:
        return t, (src if src is not None else list(range(len(t))))
    # 'Chat-GPT' is ChatGPT, 'in-laws' in-laws, when the reader knows the word
    drop = set()
    for m in _HYPHENED.finditer(t) if "-" in t else ():
        if _knows(known, m.group().replace("-", "").lower()):
            drop |= {m.start() + k for k, c in enumerate(m.group()) if c == "-"}
    t, src = _edit(t, src, {}, drop)
    # digits and symbols for letters, a capital I for l
    repl = {}
    for m in _LEET_TOKEN.finditer(t) if not _LEET_CHARS.isdisjoint(t) else ():
        tok = m.group()
        if not _LEET_CHARS.isdisjoint(tok):
            w = _deleet(tok, known)
            if w:
                repl.update({m.start() + k: b for k, (a, b) in enumerate(zip(tok, w)) if a != b})
    t, src = _edit(t, src, repl, set())
    # letters spaced out or dotted: 'C l a u d e', 'A.I.', 'P I N'
    drop = set()
    for m in _SPACED_RUN.finditer(t):
        letters = [k for k, c in enumerate(m.group()) if c.isalpha()]
        if _knows(known, "".join(m.group()[k] for k in letters).lower()):
            drop |= {m.start() + k for k in range(len(m.group())) if k not in letters}
    t, src = _edit(t, src, {}, drop)
    # a word split by a space: 'le t him in'
    drop = set()
    for m in _SPLIT.finditer(t):
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        lone = b if m.group(1) else a
        if lone.lower() in _LONE or _knows(known, a.lower()) and _knows(known, b.lower()):
            continue
        if _knows(known, (a + b).lower()):
            drop.add(m.start() + len(a))
    t, src = _edit(t, src, {}, drop)
    return t, (src if src is not None else list(range(len(t))))


@functools.lru_cache(maxsize=1 << 16)
def _fold(text: str, known) -> str:
    t, _ = fold_map(text, known)
    return re.sub(r"\s+", " ", t.translate(_QUOTES).lower()).strip()


def fold(text, known=None) -> str:
    """The text in one spelling for every reader (round 8): look-alike
    letters read as Latin, accents and zero-width characters off, lower
    case, one space; digits or symbols for letters, a capital I for l,
    spaced-out, dotted, split and hyphenated words read back as the word
    they spell when it is one of `known` (by default FOLD_WORDS: the words
    of an audience, of his health and money, of a secret and of the door)."""
    return _fold(str(text or ""), FOLD_WORDS if known is None else known)


@functools.lru_cache(maxsize=1 << 17)
def _words(t: str) -> tuple[str, ...]:
    out = []
    for m in _TOKEN.finditer(_normalise(t)):
        run, w, sym = m.group("run"), m.group("w"), m.group("sym")
        if run:
            if len(run) == 1:
                out.append(run)
            else:
                out.extend(run[i:i + 2] for i in range(len(run) - 1))
            continue
        if sym:
            if _is_symbol(sym):
                out.append(sym)
            continue
        if "'" in w:
            head, _, tail = w.partition("'")
            if len(head) == 1 or head == "qu":          # l'alarme, d'abord, qu'il
                w = tail.replace("'", "")
            elif tail == "s":                          # possessive
                w = head
            else:
                w = w.replace("'", "")
        if w:
            out.append(w)
    return tuple(out)


def words(text) -> list[str]:
    """The whole words, in order. "Mom's" is 'mom'; French "l'alarme" is
    'alarme'; "don't" is 'dont'; Chinese and Japanese are read in pairs of
    characters; an emoji is a word of its own."""
    return list(_words(str(text or "")))


def _joined(text) -> str:
    return " ".join(_words(str(text or "")))


@functools.lru_cache(maxsize=1 << 16)
def stem(w: str) -> str:
    """Light stemming, the same on both sides of every comparison: flights →
    flight, booking → book, rented → rent, families → family. Never so
    deep that two different words meet ('caring' stays 'caring', not
    'car')."""
    if len(w) <= 3 or w.isdigit():
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("sses"):
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    for suf in ("ing", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            base = w[:-len(suf)]
            if base[-1] == base[-2] and base[-1] not in "lsz":     # shopping → shop
                base = base[:-1]
            return base
    return w


# Words of two letters or fewer (R11, round 6). Round 4 let them count only
# from a short list of abbreviations ('Ed', 'Jo', 'Dr Wu', 'VW' found nothing);
# round 5 let every one count but a list of grammar words, and units, streets
# and suffixes ('kg', 'Rd', 'Jr', 'où') and capitals typed for emphasis ('Is
# it OK to GO UP there?') grounded unrelated facts. Now a short word counts
# only when it is WRITTEN CAPITALISED — as a name ('Ed', 'Jo', 'Li', 'Wu') or
# an abbreviation in capitals ('RA', 'GM', 'AA', 'ER', 'MS') — and the same
# rule on both sides means it grounds only when the subject and the fact both
# write it so. Never the grammar of a sentence, however written ('Do',
# 'An', 'OK', 'ON', 'là', 'va'), never a unit, a street or a suffix ('kg',
# 'km', 'Rd', 'St', 'Jr'), and never in a message typed all in capitals,
# where capitals say nothing.
SHORT_GRAMMAR = frozenset("""
go va vu eu ai pu dû du mû ah aw hm mm uh um oh ok eh ha hi yo ya ye ow oy lo ta an as at by
he me my of on or so to up us we be do is it if in no am ça ca là la où ou es tu il je le ma mi
ne ni nu té te né ne se si sa ce un et en de au aux ex ps vs eg ie re cc ad
""".split())
_UNITS = frozenset("kg km mg cm mm ml lb oz ft mi hr gb mb kb tb hz kw am pm rd st ln av "
                   "jr sr mt pl ct hw bd".split())
# titles and a hesitation: never as 'Dr', 'Ms', 'Mr', 'Er' — but 'MS', 'ER' are
_TITLES_SHORT = frozenset("dr mr ms er".split())
# ...and the few grammar words that are also people's names ('Mr. Do', 'An'):
# a draft that repeats one with a private fact about them is still caught
# (check_draft reads names this way; grounding never does)
_NAMES_TOO = frozenset("do an ma ha vu vo ly".split())
_ALPHA2 = re.compile(r"^[^\W\d_]{1,2}$")
# D6, round 7: a closed list of abbreviations that count in small letters
# too ('my bp', 'is the pc ok'), and 'ER' even in a message typed all in
# capitals ('GO TO THE ER NOW'). 'or', 'ms' and 'er' are also a little word,
# a title and a hesitation, so in small letters they count only beside a
# medical word ('the or nurse', 'an ms flare', 'the er doctor'); 'OR' in
# capitals is the operating room.
_ABBR_ALWAYS = frozenset("bp pc".split())
_ABBR_MEDICAL = frozenset("or ms er".split())
_ABBR_SKIP = frozenset("the a an my his her their our your le la les l un une mon ma son sa"
                       .split())


def _short_keeps(w: str, low: str, shouting: bool, names: bool) -> bool:
    """Does a word of two letters or fewer, written `w`, say what something
    is about? Only capitalised, and never grammar, a unit or a title."""
    if len(low) != 2 or not w[:1].isupper():
        return False
    caps = w.isupper()
    if low in _UNITS or (low in _TITLES_SHORT and not caps):
        return False
    if names:
        return low not in SHORT_GRAMMAR or low in _NAMES_TOO
    return not shouting and low not in SHORT_GRAMMAR


def _keeps(s: str) -> bool:
    """Is this (stemmed) word of three letters or more, a number, letters
    with a number ('5G'), a Chinese or Japanese pair (or a single character
    standing alone) or an emoji enough to say what something is about? The
    little words are already gone (STOP)."""
    if _RUN.match(s) or _is_symbol(s) or s.isdigit():
        return True
    if any(c.isdigit() for c in s):
        return True
    return len(s) >= 3


def _medical(w: str) -> bool:
    """Is this word (as written, any case) a medical one?"""
    low = _normalise(w)
    return stem(low) in _SENSE_WORDS["health"] or low in _MEDICAL_TOO


def _abbreviation(w: str, low: str, shouting: bool, toks: list[str], i: int) -> bool:
    """Is this short word one of the closed list of abbreviations, here (D6)?"""
    if low in _ABBR_ALWAYS:
        return True
    if low not in _ABBR_MEDICAL:
        return False
    if w.isupper() and ((low == "or" and not shouting) or low == "er"):
        return True                        # 'Mom was in the OR', 'GO TO THE ER NOW'
    for step in (-1, 1):                   # beside a medical word
        j = i + step
        while 0 <= j < len(toks) and _normalise(toks[j]) in _ABBR_SKIP:
            j += step
        if 0 <= j < len(toks) and _medical(toks[j]):
            return True
    return False


@functools.lru_cache(maxsize=1 << 16)
def _content(t: str, names: bool = False) -> frozenset:
    n = unicodedata.normalize("NFKC", visible(t)).translate(_QUOTES)
    long = re.findall(r"[^\W\d_]{3,}", n)
    shouting = bool(long) and sum(w.isupper() for w in long) >= 0.6 * len(long)
    toks = [m.group("w") for m in _TOKEN.finditer(n) if m.group("w")]
    k = -1
    out = set()
    for m in _TOKEN.finditer(n):
        run, w = m.group("run"), m.group("w")
        if run:
            low = _normalise(run)
            out.update([low] if len(low) == 1 else (low[i:i + 2] for i in range(len(low) - 1)))
            continue
        if not w:
            sym = m.group("sym")
            if sym and _is_symbol(sym):
                out.add(sym)
            continue
        k += 1
        if "'" in w:
            head, _, tail = w.partition("'")
            if len(head) == 1 or head.casefold() == "qu":   # l'alarme, d'abord, qu'il
                w = tail.replace("'", "")
            elif tail.casefold() == "s":                    # possessive
                w = head
            else:
                w = w.replace("'", "")
        if not w:
            continue
        low = _normalise(w)
        if _ALPHA2.match(low):
            if _short_keeps(w, low, shouting, names) or _abbreviation(w, low, shouting, toks, k):
                out.add(low)
            continue
        if low in STOP:
            continue
        st = stem(low)
        if st in STOP:
            continue
        if _keeps(st):
            out.add(st)
    return frozenset(out)


def content(text) -> set[str]:
    """The words that say what something is about: whole, stemmed, without
    the little words; a word of two letters or fewer only when written
    capitalised as a name or an abbreviation (see _short_keeps)."""
    return set(_content(str(text or "")))


def name_words(text) -> set[str]:
    """content(), and also the short names that are grammar words too ('Mr.
    Do', 'An'): how check_draft reads a private fact and a draft (R11)."""
    return set(_content(str(text or ""), True))


# --- check_draft reads short names in any case (D6, round 7) ---------------
# Round 6 let a short name count only written capitalised, so 'li has hiv',
# 'wu is bipolar' and 'ed has ms so he can't come' went to the neighbours.
# A draft is read in any case: a name of the person a private fact is about,
# as a whole word, with any word of that fact's sensitive content, is the
# fact repeated.
_DOTTED = re.compile(r"(?<![^\W\d_])(?:[^\W\d_]\.){2,}(?![^\W\d_])")
_CALENDAR = frozenset("""january february march april may june july august september october
    november december monday tuesday wednesday thursday friday saturday sunday janvier fevrier
    février mars avril mai juin juillet aout août septembre octobre novembre decembre décembre
    lundi mardi mercredi jeudi vendredi samedi dimanche""".split())
_TITLES = frozenset("mr mrs ms dr mme mlle mx sir madam".split())
_MEDICAL_TOO = frozenset("""surgery surgeon operating operation emergency ambulance sclerosis
    flare triage scan nurse doctor hospital""".split())


def _undotted(text: str) -> str:
    """'M.S.' is 'MS', 'H.I.V.' is 'HIV'."""
    return _DOTTED.sub(lambda m: m.group().replace(".", "") + " ", text)


@functools.lru_cache(maxsize=1 << 15)
def _any_case(t: str) -> frozenset:
    out = set()
    for w in _words(_undotted(t)):
        if _ALPHA2.match(w):
            if (((w in SHORT_GRAMMAR or w in STOP) and w not in _NAMES_TOO and w != "ms")
                    or w in _UNITS or (len(w) == 1 and w.isascii())):
                continue
            out.add(w)
            continue
        if w in STOP:
            continue
        st = stem(w)
        if st not in STOP and _keeps(st):
            out.add(st)
    return frozenset(out)


def any_case_words(text) -> set[str]:
    """Every word that says something, in any case — short ones too ('li',
    'ms', 'aa'), never the grammar of a sentence (D6)."""
    return set(_any_case(str(text or "")))


@functools.lru_cache(maxsize=1 << 15)
def _subject_names(t: str) -> frozenset:
    n = unicodedata.normalize("NFKC", _undotted(visible(t))).translate(_QUOTES)
    sens = set().union(*_SENSE_WORDS.values())
    out = set()
    for m in re.finditer(r"[^\W\d_]+(?:'[^\W\d_]+)?", n):
        w = m.group()
        head, _, tail = w.partition("'")
        if tail.casefold() == "s":
            w = head                                   # Ed's
        elif tail and len(head) == 1:
            w = tail                                   # l'Anna
        if not w[:1].isupper() or (len(w) > 1 and not w[1:].islower()):
            continue                                   # a name, not 'HIV'
        low = _normalise(w)
        if low in _TITLES or low in _CALENDAR:
            continue
        if len(low) <= 2:
            if _short_keeps(w, low, False, True):
                out.add(low)
            continue
        st = stem(low)
        if low in STOP or st in STOP or st in sens:
            continue
        out.add(st)
    return frozenset(out)


def subject_names(text) -> set[str]:
    """The names a fact is about: words written as a name — a capital, then
    small letters — that are not grammar, a title, a month or a day, or a
    sensitive word ('Li has HIV' is about Li; D6)."""
    return set(_subject_names(str(text or "")))


@functools.lru_cache(maxsize=1 << 15)
def _sensitive_content(t: str) -> frozenset:
    words = _any_case(t) - _subject_names(t)
    n = unicodedata.normalize("NFKC", _undotted(visible(t)))
    long = re.findall(r"[^\W\d_]{3,}", n)
    shouting = bool(long) and sum(w.isupper() for w in long) >= 0.6 * len(long)
    sens = set().union(*_SENSE_WORDS.values())
    picked = {w for w in words if w in sens}
    joined = f" {_joined(t)} "
    for cls, forms in _PHRASE_FORMS.items():
        for p in forms:
            if p in joined:
                picked |= {stem(x) for x in p.split()} & words
    if not shouting:                                   # 'MS', 'AIDS', 'RA', 'AA'
        picked |= {_normalise(x) for x in re.findall(r"\b[^\W\d_a-z]{2,5}\b", n)
                   if x.isupper()} & words
    return frozenset(picked or words)


def sensitive_content(text) -> set[str]:
    """The words that make a private fact private: its medical, money,
    family-secret words and the abbreviations it writes in capitals ('MS',
    'HIV') — or, when it has none of those, every word but its names (D6)."""
    return set(_sensitive_content(str(text or "")))


# --- a draft names the person in any case (F5, round 8) --------------------
# Round 7 read the DRAFT in any case but still needed the FACT to spell its
# person's name with a capital, so 'jo is on chemo for her breast cancer …'
# and 'ED HAS MS …', typed as an elderly owner often types, let 'Jo is on
# chemo' and 'Ed has MS' go to the neighbours; and 'Ed has M S', 'Ed has
# multiple sclerosis', 'jo is having chemotherapy', 'li is poz' and 'Lі has
# HІV' (Cyrillic і) did not repeat 'Ed has MS', 'Jo is on chemo' or 'Li has
# HIV'. Now the person of a fact is found in any case: the names of people
# he recorded, its capitalised words, and — for a fact written all in small
# letters or all in capitals — its first word and every word that is not a
# common word. Abbreviations are read however they are dotted or spaced
# (m.s, M. S., M S, M-S are ms; h.i.v is hiv), a short list of synonyms is
# read as one word, and a draft that names the person with a word of what
# makes the fact private — or any word of his health or his money — is the
# fact repeated. Friction is accepted.
_COMMON = frozenset("""
    about above across after again against ago all almost alone along already also always
    among another any anything around asked away back bad be became because become been
    before began behind being believe best better between big bit both bought bring brought
    but buy call called came can cannot car care case cause certain change check child city
    close come comes coming could couple course cut day days did different do does doing done
    door down during each early either else end enough even evening ever every everything
    face fact family far feel felt few find fine first five found four friday friend friends
    from front full gave general get gets getting give given go goes going gone good got great
    group had half hand hard has have having head hear heard help her here high him his home
    hope hospital hour hours house how idea important into its just keep kept kind knew know
    known large last late later least left less let life like likely line little live lives
    long look looked looking lot lots love made make makes making man many may maybe mean
    means meet met might mind minute minutes miss moment monday month months more morning
    most mother move much must name near need needs never new news next nice night nine
    nobody none nor now number off often old once one only open other out over own part past
    pay people perhaps person place plan play point pretty probably put quite rather read
    ready real really right room round said same saturday saw say says second see seem seemed
    seems seen sent set seven several she should show side since six small so some someone
    something sometimes soon sorry start started still stop story sunday sure take taken
    talk tell ten than thank thanks that the their them then there these they thing things
    think this those though thought three through thursday time times today together told
    tomorrow too took town tried try trying tuesday turn two under until upon use used uses
    using usual very visit wait want wanted wants was watch water way week weekend weeks
    well went were what wednesday when where whether which while who whole why will wish
    with within without woman word words work worked would year years yes yesterday yet
    young your
    went back went relapse again good bad worse better fine okay ok
    avec avoir bien bon bonne cela chez comme dans depuis deux dire elle encore entre est
    etait etre fait faire fois hier ici jamais jour jours leur lui mais meme mois moins
    nous peu peut plus pour quand rien semaine sans sera sont sous suis tous tout tres trop
    une vers vient voir vous
""".split()) | STOP
# Abbreviations a draft may write dotted or spaced, read as one word
_DRAFT_ABBR = frozenset("""ms hiv aids copd ra aa bp ptsd adhd ocd als ibs uti dvt chf ckd tb
    std sti mri icu er""".split())
# A few words that mean the same thing, read as one on both sides
_DRAFT_SAME = {"chemotherapy": "chemo", "poz": "hiv", "rehabilitation": "rehab",
               "leukemia": "cancer", "leukaemia": "cancer", "lymphoma": "cancer",
               "melanoma": "cancer", "carcinoma": "cancer", "sarcoma": "cancer",
               "myeloma": "cancer", "tumour": "cancer", "tumor": "cancer",
               "oncology": "cancer", "oncologist": "cancer", "cancers": "cancer",
               "mastectomy": "cancer", "radiotherapy": "radiation",
               # round 9 (G4): French, and the words the skeptics used
               "chimio": "chemo", "chimiotherapie": "chemo", "vih": "hiv",
               "seropositif": "hiv", "seropositive": "hiv", "undetectable": "hiv",
               "faillite": "bankrupt", "bankruptcy": "bankrupt", "enceinte": "pregnant",
               "pregnancy": "pregnant", "grossesse": "pregnant"}
_DRAFT_PHRASES = (("multiple sclerosis", "ms"), ("sclerose en plaques", "ms"),
                  ("hiv positive", "hiv"), ("hiv+", "hiv"),
                  # round 9 (G4)
                  ("the big c", "cancer"), ("le gros c", "cancer"), ("viral load", "hiv"),
                  ("charge virale", "hiv"), ("having a baby", "pregnant"),
                  ("expecting a baby", "pregnant"), ("attend un bebe", "pregnant"),
                  ("a fait faillite", "bankrupt"),
                  # round 9 repair (unsafe_r9 G4): the drafts the skeptics wrote
                  ("mind is going", "dementia"), ("perd la memoire", "dementia"),
                  ("maxed out", "debt"), ("drank too much", "alcoholic"),
                  ("drinks too much", "alcoholic"), ("drinking too much", "alcoholic"),
                  ("treatment centre", "rehab"), ("treatment center", "rehab"))
_DRAFT_PHRASE_RX = tuple((re.compile(r"(?<![^\W_])" + re.escape(p) + r"(?![^\W_])"), w)
                         for p, w in _DRAFT_PHRASES) + (
    # 'Laszlo has AIDS' — not hearing, visual or teaching aids, nor first aid
    (re.compile(r"(?<![^\W_])(?<!hearing )(?<!visual )(?<!teaching )(?<!learning )"
                r"(?<!mobility )(?<!walking )aids(?![^\W_])"), "hiv"),)
# 'Anna is expecting', 'expecting in May' — not 'expecting a parcel' or rain
_EXPECTING = re.compile(r"(?<![^\W_])expecting(?=\s*(?:[.!?,;:]|$)|\s+(?:in|this|next|again|"
                        r"another|twins|a\s+(?:boy|girl)|her|their|our|his)(?![^\W_]))")
# SEP is 'sclérose en plaques' in capitals, or after 'la', 'une', 'sa' …;
# 'Sep 12' is September
_SEP = re.compile(r"(?<![^\W_])SEP(?![^\W_])|(?i:(?<![^\W_])(la|une|sa|ma|de|d'une|avec)\s+sep"
                  r"(?![^\W_]))")
_DRAFT_LEX_EXTRA = frozenset("""ms hiv aids copd ra aa ptsd adhd ocd als ibs uti chemo cancer
    rehab lupus crohn colitis celiac epilepsy seizure seizures shingles hepatitis cirrhosis
    kidney liver transplant angina pacemaker glaucoma cataract cataracts macular osteoporosis
    gout fibromyalgia migraine migraines ulcer hernia thyroid autism psychosis overdose
    radiation surgery operation stroke heart sick ill illness disease diagnosed
    sclerosis bipolar alcoholic relapse sober
    virus prostate""".split())


def _draft_prepared(text: str) -> str:
    t = fold_map(text)[0]                             # look-alike letters, case kept
    t = _SEP.sub(lambda m: f"{m.group(1) or ''} MS", t)
    return re.sub(r"(?<![^\W_])Ms\.?(?=\s+[A-Z])", " ", t)   # 'Ms Wu' is a title


@functools.lru_cache(maxsize=1 << 14)
def _draft_words(text: str, known: frozenset = frozenset()) -> frozenset:
    """`known`: more words the fold may read back ('J0', 'J o' are 'Jo' when
    the fact compared is about Jo — round 9, G4)."""
    t = fold(_draft_prepared(text), _DRAFT_ABBR | FOLD_WORDS | known)
    for rx, w in _DRAFT_PHRASE_RX:
        t = rx.sub(f" {w} ", t)
    t = _EXPECTING.sub(" pregnant ", t)
    out = set()
    for w in _any_case(t):
        out.add(_DRAFT_SAME.get(w, w))
    return frozenset(out)


def draft_words(text) -> set[str]:
    """The words of a draft or a fact as check_draft compares them (F5):
    any case, look-alike letters read as Latin, abbreviations however they
    are dotted or spaced, a few synonyms as one word."""
    return set(_draft_words(str(text or "")))


@functools.lru_cache(maxsize=1 << 12)
def _fact_people(fact: str, people: tuple) -> frozenset:
    words_ = _draft_words(fact)
    out = {_DRAFT_SAME.get(w, w) for w in _subject_names(_draft_prepared(fact))}
    for name in people:                               # the people he recorded
        nw = {stem(w) for w in _words(fold(name)) if len(w) >= 2 and w not in _TITLES}
        if nw & words_:
            out |= nw
    letters = [c for c in fact if c.isalpha()]
    if letters and (all(c.islower() for c in letters) or all(c.isupper() for c in letters)):
        first = next(iter(_words(fold(fact))), "")
        if first and first not in _COMMON:
            out.add(stem(first) if len(first) > 2 else first)
        out |= {w for w in words_ if w not in _COMMON and stem(w) not in _COMMON
                and not w.isdigit()}
    return frozenset(out)


def _known_for(fact: str, people: tuple) -> frozenset:
    """The words a draft's fold may read back when it is compared with this
    fact: the fact's own words and the names of the people he recorded."""
    out = {w for w in _words(fold(fact)) if len(w) >= 2}
    for name in people:
        out |= {w for w in _words(fold(name)) if len(w) >= 2}
    return frozenset(out)


# --- his own private facts in a draft (G4, round 9) ------------------------
# Round 8 looked for the PERSON a private fact is about, and a first-person
# fact names nobody: with 'I have HIV' kept, 'I have HIV', 'Dad has HIV',
# 'Laszlo has HIV' and 'He has HIV' to the neighbours were all 'nothing in it
# goes against his rules'. A fact in the first person — I, my, me, I'm, I've,
# je, j', mon, ma, mes, moi — is about him. A draft to an audience that may
# not hear it, carrying any sensitive word of that fact or of its kind (his
# health, his money, legal matters, family confidences), is brought to him,
# whoever the draft names. Friction is accepted.
_FIRST_PERSON = re.compile(r"(?<![\w'])(?:i|i'm|im|i've|ive|i'd|i'll|my|me|mine|myself|je|mon|ma"
                           r"|mes|moi)(?![\w'])|(?<![\w'])j'(?=\w)")
OWN_CLASSES = ("health", "money", "private", "third_party")


def first_person(text) -> bool:
    """Is this fact written in the first person — about him (G4)? Read both
    ways (round 9, second repair: 'I\u200btake\u200bOzempic' glued to
    'itakeozempic' was nobody's, and a draft that carried it was not asked)."""
    return any(_FIRST_PERSON.search(fold(r, frozenset())) for r in readings(str(text or "")))


@functools.lru_cache(maxsize=1 << 12)
def _carries_kind(draft: str, kinds: tuple, known: frozenset) -> bool:
    dw = _draft_words(draft, known)
    t = fold(_draft_prepared(draft), _DRAFT_ABBR | FOLD_WORDS | known)
    for rx, w in _DRAFT_PHRASE_RX:
        t = rx.sub(f" {w} ", t)
    joined = f" {' '.join(_words(t))} "
    for cls in kinds:
        lex = _SENSE_WORDS.get(cls, frozenset()) | (_DRAFT_LEX_EXTRA if cls == "health"
                                                    else frozenset())
        if dw & lex or {stem(w) for w in dw} & lex:
            return True
        if any(p in joined for p in _PHRASE_FORMS.get(cls, ())):
            return True
        if any(rx.search(t) for rx in _SENSE_PATTERNS.get(cls, ())):
            return True
    return False


def draft_carries(fact, classes, draft, people=()) -> bool:
    """Does this draft carry a sensitive word of this private fact, or any
    word of its kind — his health, his money, a legal matter, a family
    confidence (G4)? Read in any case, through the fold, with the synonyms."""
    fact, draft = str(fact or ""), str(draft or "")
    known = _known_for(fact, tuple(people))
    dw = _draft_words(draft, known)
    fw = _draft_words(fact)
    # its sensitive words are the words of a kind of private thing it holds —
    # never a name ('my friend dana reyes has lupus' is not about 'Dana')
    lex = set().union(*_SENSE_WORDS.values()) | _DRAFT_LEX_EXTRA
    names = {w for p in people for w in _words(fold(p))}
    sens = {w for w in fw if w in lex or stem(w) in lex} - names - _COMMON
    if sens & dw:
        return True
    kinds = tuple(c for c in OWN_CLASSES if c in set(classes or ()))
    return bool(kinds) and _carries_kind(draft, kinds, known)


def draft_repeats(fact, draft, people=()) -> bool:
    """Does this draft repeat this private fact (F5)? It names the fact's
    person — in any case — together with a word of what makes the fact
    private, or any word of his health or his money; or it repeats two of
    the fact's words and at least half of them."""
    fact, draft = str(fact or ""), str(draft or "")
    fw = _draft_words(fact)
    dw = _draft_words(draft, _known_for(fact, tuple(people)))
    shared = fw & dw
    if len(fw) >= 2 and len(shared) >= max(2, -(-len(fw) // 2)):
        return True
    who = _fact_people(fact, tuple(people))
    about = who & dw
    if not about:
        return False
    names_only = {w for w in who if w not in _DRAFT_LEX_EXTRA
                  and w not in _SENSE_WORDS["health"] and w not in _SENSE_WORDS["money"]}
    sens = ({_DRAFT_SAME.get(w, w) for w in _sensitive_content(fold_map(fact)[0])}
            | (fw & _DRAFT_LEX_EXTRA)) - names_only
    if not sens:
        sens = fw - names_only - _COMMON
    lex = _DRAFT_LEX_EXTRA | _SENSE_WORDS["health"] | _SENSE_WORDS["money"]
    return bool(sens & dw) or bool((dw - about) & lex) or bool(about & lex & sens)


# A few everyday words that mean the same subject, so 'booking a flight'
# reaches a value about travel and 'a caregiver for Mom' reaches one about
# Mom's care. Only ever added to what was ASKED, never to what is stored.
_ALSO = {
    "caregiver": ("care",), "carer": ("care",), "caretaker": ("care",),
    "caring": ("care",), "nurse": ("care",),
    "flight": ("travel", "fly"), "fly": ("travel", "flight"), "plane": ("travel", "flight"),
    "airline": ("travel", "flight"), "trip": ("travel",), "hotel": ("travel",),
    "vacation": ("travel",), "holiday": ("travel",), "travel": ("trip",),
    "med": ("medication",), "medicine": ("medication",), "pill": ("medication",),
    "prescription": ("medication",), "medication": ("med",),
    "mum": ("mom",), "mother": ("mom",), "mama": ("mom",), "mommy": ("mom",),
    "mom": ("mother",), "father": ("dad",), "papa": ("dad",), "daddy": ("dad",),
    "dad": ("father",), "physician": ("doctor",),
}


def expand(ws: set[str]) -> set[str]:
    return set(ws) | {a for w in ws for a in _ALSO.get(w, ())}


def phrase_in(phrase: str, text: str) -> bool:
    """Is this phrase in the text as whole words ('lives alone' in 'He lives
    alone now', never 'art' in 'heart')?"""
    p = _joined(phrase)
    return bool(p) and f" {p} " in f" {_joined(text)} "


def topic_problem(topic) -> str | None:
    """Why a subject cannot be looked up — or None when it names something."""
    if not content(str(topic or "").strip()):
        return ("Name the subject in a word or two that mean something (for example "
                "'travel', 'Mom's care' or 'the phone bill'); nothing was looked up.")
    return None


# Contexts that apply to everything. The owner may hold such a value; an AI
# may not write one, because it is cited for every decision (I-25).
CATCH_ALL = frozenset({"any", "all", "general", "everything", "always", "anything",
                       "every", "overall", "in general", "all things", "life"})
# Words that, alone, name no subject (verify I-25: 'all decisions', 'every
# decision' and 'decisions' were cited for a grandson's bail). 'Family' does
# name one ('in family matters, presence beats work'), so it stays.
_BROAD = frozenset(stem(w) for w in """decision decisions choice choices thing things matter
    matters situation situations case cases stuff everything anything something all any
    every each whatever overall general generally default usual usually life
    people everyone anyone time times way ways day days""".split())


def context_problem(context, engine: bool) -> str | None:
    """Why a priority's context cannot be stored, in plain words — or None."""
    n = normalise(context)
    if n in CATCH_ALL:
        if engine:
            return ("A value that applies to everything can only be set by the owner "
                    "himself. Name the subject it is about (for example 'Mom's care' "
                    "or 'travel'); nothing was stored.")
        return None
    if not content(context):
        return ("Name the subject this value is about in a word or two (for example "
                "'travel' or 'Mom's care'); nothing was stored.")
    if engine and not {stem(w) for w in words(n)} - _BROAD:
        return ("That is about nearly everything, so only the owner himself can set it. "
                "Name the subject it is about (for example 'Mom's care' or 'family "
                "visits'); nothing was stored.")
    return None


def context_match(context, topic_words: set[str]) -> tuple[str, str] | None:
    """Does a value held about `context` apply to a subject with these words?
    ('about', reason) when every word of the context is in the subject;
    ('general', reason) for a value about everything; else None."""
    n = normalise(context)
    if n in CATCH_ALL:
        return ("general", "a value he holds about everything")
    c = content(context)             # as written: "Ed's care" keeps 'Ed' (R11)
    if not c:
        return None
    if c <= topic_words:
        return ("about", "it is about " + " and ".join(sorted(c)))
    return None


# ------------------------------------------------------- what kind of private
CLASSES = ("health", "money", "minors", "home_security", "third_party", "private")
CLASS_WORDS_PLAIN = {
    "health": "his health",
    "money": "his money",
    "minors": "children",
    "home_security": "the safety of his home",
    "third_party": "someone else's confidence",
    "private": "something private",
}


def _stems(text: str) -> frozenset:
    return frozenset(stem(w) for w in text.split())


_SENSE_WORDS = {
    "health": _stems("""health medical medication medications meds medicine prescription
        prescribed pharmacy pharmacist doctor physician psychiatrist psychologist therapist
        therapy counselling counseling diagnosis diagnosed ptsd alzheimer alzheimers
        dementia cancer tumour tumor biopsy chemo chemotherapy diabetes diabetic insulin
        warfarin sertraline donepezil metformin statin statins stroke surgery hospital
        hospitalised hospitalized rehab addiction alcoholic alcoholism sober sobriety
        depression depressed anxiety bipolar schizophrenia pregnant pregnancy miscarriage
        hiv suicide suicidal disability wheelchair allergy allergic illness symptoms
        parkinson parkinsons copd asthma arthritis cholesterol pills pill dialysis
        santé médecin médicament médicaments maladie enceinte
        dr doctors clinic nurse specialist cardiologist neurologist oncologist
        geriatrician urologist gynecologist physio physiotherapy shrink counsellor
        counselor coumadin eliquis xarelto lipitor aricept memantine lorazepam ativan
        xanax prozac zoloft lithium seroquel oxycodone morphine methadone opioid
        drinking drunk alcohol booze relapse hangover rehab detox forgetful
        forgetfulness incontinence catheter mri ultrasound biopsy
        colonoscopy mammogram prognosis palliative hospice"""),
    "money": _stems("""bank banking savings debt debts owe owes owed owing loan loans
        mortgage bankrupt bankruptcy overdraft salary income pension inheritance invest
        investment investments rrsp tfsa rrif brokerage credit banque dette dettes prêt
        hypothèque épargne"""),
    # Age, not relationship: a grandson may be forty. What marks a child is
    # an age, a school, a baby.
    "minors": _stems("""toddler toddlers baby babies infant infants newborn teen teens
        teenager teenagers teenage kindergarten daycare preschool bébé"""),
    "home_security": _stems("""alarm alarms alarme lockbox keypad deadbolt"""),
    "third_party": _stems("""secret secrets secretly affair confided hush"""),
    # matters people keep to themselves even when nobody marked them so
    "private": _stems("""divorce divorcing separated separation custody lawyer lawsuit
        estranged bankruptcy arrest arrested probation parole"""),
}
_SENSE_PHRASES = {
    "health": ("blood pressure", "mental health", "memory clinic", "heart attack",
               "heart condition", "heart surgery", "blood thinner", "blood thinners",
               "losing my memory", "losing his memory", "losing her memory", "memory loss",
               "memory problems", "memory is going", "a test for", "test results",
               "blood test", "cat scan"),
    "money": ("net worth", "credit card", "savings account", "bank account"),
    "minors": ("high school", "middle school", "elementary school", "grade school",
               "junior high", "école primaire"),
    "home_security": ("spare key", "hidden key", "key under", "key is under", "key is in",
                      "door code", "gate code", "garage code", "garage door code",
                      "safe combination", "lives alone", "live alone", "living alone",
                      "home alone", "alone at home", "by myself at home", "home most",
                      "usually home", "away from home", "out of town", "on vacation",
                      "while we are away", "while we're away", "while i am away",
                      "while i'm away", "house is empty", "empty house", "nobody home",
                      "no one home", "seul à la maison", "vit seul", "code de porte",
                      "restraining order", "peace bond", "no contact order",
                      "house sits empty", "house is empty", "the house empty",
                      "away for the winter", "spend the winter", "away until",
                      "we're away", "we are away", "i'm away", "i am away"),
    "third_party": ("hasn't told", "has not told", "hasnt told", "haven't told",
                    "doesn't know", "does not know", "doesnt know", "don't tell",
                    "do not tell", "not to tell", "never told", "nobody knows",
                    "no one knows", "in confidence", "keep it quiet", "between us",
                    "behind her back", "behind his back", "keep it hush", "hush hush",
                    "hasn't told anyone", "not told anyone", "keep this quiet",
                    "don't say anything", "not a word"),
}
_SENSE_PATTERNS = {
    "health": (re.compile(r"\b\d+(?:\.\d+)?\s?mg\b"),
               # 'Emma is expecting in May' — not 'expecting a parcel'
               re.compile(r"\b(?:is|she'?s|are|we'?re) expecting\b(?! (?:a|an|the|my|his|her|"
                          r"your|some) (?:call|parcel|package|delivery|letter|cheque|check|"
                          r"visit|visitor|email|reply|answer|refund|bill))")),
    "money": (re.compile(r"[$€£]\s?\d{1,3}(?:,\d{3})+"), re.compile(r"[$€£]\s?\d{4,}"),
              re.compile(r"\$?\b\d{2,}k\b")),
    "minors": (re.compile(r"\b(?:[1-9]|1[0-7])\s*(?:years?|yrs?)[\s-]*old\b"),
               re.compile(r"\b(?:aged?)\s*(?:[1-9]|1[0-7])\b"),
               re.compile(r"\bgrade\s*(?:[1-9]|1[0-2])\b"),
               # 'Grandson Leo is 9 and goes to Riverside Elementary'
               re.compile(r"\b(?:is|turns?|turned|just turned) (?:[1-9]|1[0-7])\b(?! ?(?:%|"
                          r"percent|dollars|am|pm|o'clock|:|\.\d|minutes|hours|days|weeks|"
                          r"months|km|kg|lbs))"),
               re.compile(r"\b(?:elementary|primary|junior|middle|public|catholic) school\b"
                          r"|\belementary\b")),
}
# F2, round 8: his health is also his lab results and measures, and the
# medicines most prescribed in Canada, by their generic and brand names and
# in French ('My A1C was 8.2 at the last checkup' and 'I take Ozempic every
# Sunday' went to every AI past 'Never tell my health to any AI'). Written
# without accents: a fact is read through the fold, accents off, as well.
_HEALTH_LEX = """
    a1c hba1c inr ldl hdl cholesterol cholesterol triglyceride triglycerides glucose
    glycemie insulin insuline egfr psa bp bmi imc creatinine hemoglobin haemoglobin
    ferritin tsh potassium inr warfarin
    metformin metformine glucophage ozempic wegovy rybelsus semaglutide victoza saxenda
    liraglutide trulicity dulaglutide mounjaro tirzepatide jardiance empagliflozin
    empagliflozine forxiga farxiga dapagliflozin dapagliflozine invokana canagliflozin
    januvia janumet sitagliptin sitagliptine trajenta linagliptin synjardy xigduo
    gliclazide diamicron glyburide glimepiride pioglitazone lantus basaglar toujeo
    tresiba levemir humalog novorapid fiasp glargine degludec
    atorvastatin atorvastatine lipitor rosuvastatin rosuvastatine crestor simvastatin
    simvastatine zocor pravastatin ezetimibe ezetrol fenofibrate lipidil repatha
    evolocumab levothyroxine synthroid eltroxin
    ramipril altace perindopril coversyl lisinopril zestril enalapril vasotec candesartan
    atacand losartan cozaar valsartan diovan irbesartan avapro telmisartan micardis
    olmesartan olmetec amlodipine norvasc nifedipine adalat diltiazem cardizem tiazac
    verapamil hydrochlorothiazide chlorthalidone indapamide furosemide furosemide lasix
    spironolactone aldactone metoprolol lopressor betaloc bisoprolol monocor atenolol
    tenormin carvedilol coreg propranolol inderal nebivolol digoxin digoxine lanoxin
    amiodarone cordarone nitroglycerin isosorbide
    apixaban rivaroxaban dabigatran pradaxa edoxaban lixiana clopidogrel plavix
    ticagrelor brilinta warfarine coumadin eliquis xarelto
    pantoprazole pantoloc tecta omeprazole losec esomeprazole nexium rabeprazole pariet
    lansoprazole dexlansoprazole dexilant famotidine ranitidine
    sertraline zoloft citalopram celexa escitalopram cipralex lexapro fluoxetine prozac
    paroxetine paxil venlafaxine effexor desvenlafaxine pristiq duloxetine cymbalta
    bupropion wellbutrin zyban mirtazapine remeron trazodone desyrel amitriptyline elavil
    nortriptyline quetiapine seroquel olanzapine zyprexa risperidone risperdal
    aripiprazole abilify lamotrigine lamictal valproate divalproex epival depakote
    carbamazepine tegretol gabapentin gabapentine neurontin pregabalin pregabaline lyrica
    topiramate topamax levetiracetam keppra phenytoin dilantin lorazepam ativan clonazepam
    rivotril alprazolam xanax diazepam valium oxazepam temazepam zopiclone imovane
    zolpidem ambien sublinox
    salbutamol ventolin albuterol fluticasone flovent advair symbicort budesonide
    pulmicort formoterol salmeterol tiotropium spiriva breo trelegy montelukast singulair
    prednisone prednisolone methylprednisolone hydrocortisone
    allopurinol zyloprim colchicine febuxostat methotrexate hydroxychloroquine plaquenil
    sulfasalazine adalimumab humira etanercept enbrel infliximab remicade
    tamsulosin tamsulosine flomax finasteride proscar dutasteride avodart oxybutynin
    solifenacin vesicare mirabegron myrbetriq tolterodine detrol sildenafil viagra
    tadalafil cialis alendronate fosamax risedronate actonel denosumab prolia zoledronic
    aclasta donepezil aricept memantine ebixa rivastigmine exelon galantamine reminyl
    levodopa carbidopa sinemet pramipexole mirapex ropinirole requip
    amoxicillin amoxicilline amoxil clavulin azithromycin azithromycine zithromax
    clarithromycin biaxin cephalexin keflex ciprofloxacin ciprofloxacine cipro
    levofloxacin levaquin doxycycline nitrofurantoin macrobid trimethoprim
    sulfamethoxazole septra metronidazole flagyl clindamycin dalacin valacyclovir
    valtrex acyclovir oseltamivir tamiflu
    tramadol tramacet ultram codeine hydromorphone dilaudid oxycontin percocet fentanyl
    buprenorphine suboxone naloxone celecoxib celebrex naproxen aleve ibuprofen advil
    motrin diclofenac voltaren meloxicam mobicox acetaminophen acetaminophene tylenol
    estradiol estrace progesterone prometrium medroxyprogesterone provera levonorgestrel
    mirena norethindrone testosterone androgel tamoxifen nolvadex letrozole femara
    anastrozole arimidex exemestane aromasin bicalutamide casodex enzalutamide xtandi
    ondansetron zofran domperidone metoclopramide cyclobenzaprine flexeril baclofen
    lioresal methylphenidate ritalin concerta lisdexamfetamine vyvanse varenicline
    champix oxycodone morphine methadone lithium
    sante medecin medicament medicaments maladie
"""
_HEALTH_LEX_PHRASES = ("blood sugar", "sugar level", "sugar levels", "my sugars",
                       "blood work", "bloodwork", "lab results", "taux de sucre",
                       "tension arterielle", "pression arterielle", "prise de sang")
# Round 9 (G9): the words the round-8 skeptics found his health in — HIV
# medicines and prevention, a CPAP, AA, NA and twelve-step meetings,
# incontinence, a personal support worker who bathes him, a joint replaced,
# hearing aids, 'my sugar', 'ma pression', 'mes pilules', an ostomy, a puffer
# or an inhaler, 'the big C', 'my waterworks', a worry about 'my memory' —
# and his money: borrowed, lent, 'five grand'. Exactly these; the list is
# bounded (round 9 says what it knows remains).
_HEALTH_LEX += """
    biktarvy truvada descovy genvoya triumeq dovato odefsey stribild complera juluca
    cpap bipap colostomy ostomy ileostomy urostomy stoma puffer puffers inhaler inhalers
    pilule pilules waterworks psw incontinent
"""
_HEALTH_LEX_PHRASES += ("my sugar", "his sugar", "her sugar", "ma pression", "sa pression",
                        "the big c", "le gros c", "hearing aid", "hearing aids",
                        "hip replacement", "knee replacement", "joint replacement",
                        "shoulder replacement", "replacement hip", "replacement knee",
                        "incontinence pads", "incontinence pad", "adult diapers",
                        "personal support worker", "personal care worker", "bathe me",
                        "bathes me", "bathing me", "help me bathe", "helps me bathe",
                        "help me shower", "helps me shower", "helping me shower",
                        "help me in the shower", "twelve step", "12 step",
                        "alcoholics anonymous", "narcotics anonymous", "aa meeting",
                        "aa meetings", "na meeting", "na meetings", "sleep apnea",
                        "sleep apnoea")
# Round 9 repair: HIV and dementia in French, as the skeptics asked a rule's
# topic ('VIH', 'démence')
_HEALTH_LEX += """
    vih demence
"""
_SENSE_WORDS["health"] = _SENSE_WORDS["health"] | _stems(_HEALTH_LEX)
_SENSE_PHRASES["health"] = _SENSE_PHRASES["health"] + _HEALTH_LEX_PHRASES
_SENSE_PATTERNS["health"] = _SENSE_PATTERNS["health"] + (
    # 'I go to AA on Thursdays' — not 'AA batteries' or an AA flight
    re.compile(r"\b(?:go|goes|going|went|attend|attends|attended|attending|at|in|to|from|"
               r"join|joined|my|his|her)\s+(?:aa|na)\b(?!\s*(?:batter|cells?|flight|size|\d))"),
    # 'I wear Depends at night' — not 'it depends'
    re.compile(r"\b(?:wear|wears|wearing|wore|buy|buys|bought|need|needs|pack of|box of|"
               r"my|his|her)\s+depends\b|\bdepends\s+(?:at night|pads?|underwear|"
               r"undergarments|briefs|diapers)\b"),
    # PrEP, the pill that prevents HIV — not meal prep
    re.compile(r"\b(?:on|take|takes|taking|took|started|start|my|his|her|daily|hiv)\s+prep\b"
               r"|\bprep\s+(?:pills?|daily|every|for\s+hiv)\b"),
    # a worry about 'my memory' — not 'in my memory the lake was bigger'
    re.compile(r"(?<!in )\b(?:my|his|her)\s+memory\b(?!\s+(?:of|from|for|card|stick|foam|"
               r"box|book|lane)\b)"),
)
_SENSE_WORDS["money"] = _SENSE_WORDS["money"] | _stems("faillite")
_GRAND = (r"(?:\d+(?:[.,]\d+)?|a few|a couple of|one|two|three|four|five|six|seven|eight|"
          r"nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|"
          r"ninety|hundred)\s*(?:grand|gs)\b")
_SENSE_PATTERNS["money"] = _SENSE_PATTERNS["money"] + (
    # 'five grand', '5 grand', 'forty grand' — thousands, not a piano
    re.compile(r"\b" + _GRAND),
    # borrowed, lent, a loan — of money: 'Mike borrowed 5 grand', 'I lent
    # Mike $500' (not 'Al borrowed the ladder', nor 'chocolate for Lent')
    re.compile(r"\b(?:borrow|borrows|borrowed|borrowing|lent|lend|lends|lending|loaned)\b"
               r"[^.!?\n]{0,60}?(?:[$€£]\s?\d|\b\d[\d,.]*\s*(?:\$|dollars?|bucks|k)\b"
               r"|\b(?:money|cash|cheque|check for)\b|\b" + _GRAND + r")"),
)
# PrEP written as it is spelt (G9)
_PREP_RAW = re.compile(r"(?<![^\W_])PrEP(?![^\W_])")

# A category the owner (or an AI) gave a fact that already says what it is.
_CATEGORY = {
    "health": _stems("health medical medication medications medicine"),
    "money": _stems("money finance finances financial bank banking debt debts"),
    "minors": _stems("kids children grandchildren grandkids minors"),
    "home_security": _stems("security safety"),
    "private": _stems("private secret secrets confidential confidence"),
}


# Each phrase as whole words, worked out once (sensitivity() runs for every
# fact and moment on every call that shows them: re-reading ~80 phrases from
# text each time made 'who am I' take eight seconds on a long life — scale-21).
_PHRASE_FORMS = {cls: tuple(f" {_joined(p)} " for p in ps)
                 for cls, ps in _SENSE_PHRASES.items()}


@functools.lru_cache(maxsize=1 << 16)
def _sensitivity(text: str, category: str) -> tuple[str, ...]:
    t = _normalise(text)
    ft = fold(text)
    ws = _words(t)
    # ...and read through the fold (round 8): 'Оzempic' with a Cyrillic О,
    # 'glycémie' without its accent, '0zempic'
    fws = _words(fold(text))
    st = {stem(w) for w in ws} | {stem(w) for w in fws}
    joined = f" {' '.join(ws)} {' '.join(fws)} "
    cat = {stem(w) for w in _words(category)}
    found = set()
    for cls in CLASSES:
        if st & _SENSE_WORDS.get(cls, frozenset()):
            found.add(cls)
        elif any(p in joined for p in _PHRASE_FORMS.get(cls, ())):
            found.add(cls)
        elif any(rx.search(t) or (ft != t and rx.search(ft))
                 for rx in _SENSE_PATTERNS.get(cls, ())):
            found.add(cls)
        elif cls == "health" and _PREP_RAW.search(str(text)):
            found.add(cls)
        if cat & _CATEGORY.get(cls, frozenset()):
            found.add(cls)
    c = _normalise(category)
    if "never share" in c or "do not share" in c or "don't share" in c:
        found.add("private")
    return tuple(c for c in CLASSES if c in found)


def sensitivity(text, category="") -> list[str]:
    """What kind of private this is, if any: health, money, minors (children),
    home_security, third_party (someone else's confidence) or private (marked
    so). An empty list means nothing sensitive was recognised. A text that
    holds a character that shows as nothing is read both ways (G5 repair)."""
    t, cat = str(text or ""), str(category or "")
    if not has_hidden(t):
        return list(_sensitivity(t, cat))
    found = {k for r in readings(t) for k in _sensitivity(r, cat)}
    return [k for k in CLASSES if k in found]


# What a subject has to say to NAME a kind of private ("my medications"
# names his health; "rent" names nothing private).
CLASS_WORDS = {
    "health": _stems("health medical medication medicine med pill doctor diagnosis "
                     "illness hospital prescription pharmacy condition treatment"),
    "money": _stems("money finance financial bank banking debt saving account loan "
                    "mortgage budget investment pension tax"),
    "minors": _stems("kid child children grandchild grandchildren grandkid grandson "
                     "granddaughter school minor"),
    "home_security": _stems("home house security safety alarm key lock away schedule "
                            "alone address"),
    "third_party": _stems("secret confidence"),
    "private": _stems("private secret"),
}
# How an owner may name a kind in a rule ('medical', 'my finances', 'kids').
CLASS_ALIASES = {
    "health": "health", "medical": "health", "medication": "health",
    "medications": "health", "meds": "health", "mental health": "health",
    "diagnosis": "health", "money": "money", "finances": "money", "financial": "money",
    "finance": "money", "debt": "money", "debts": "money", "bank": "money",
    "kids": "minors", "children": "minors", "grandchildren": "minors",
    "grandkids": "minors", "minors": "minors", "home security": "home_security",
    "security": "home_security", "safety": "home_security",
    "schedule": "home_security", "lives alone": "home_security",
    "secrets": "third_party", "secret": "third_party", "confidences": "third_party",
    "private": "private",
}


# ------------------------------------ a question in a kind's own words (r9 fix 2)
# A question about a kind his rules close to a reader ('my diabetes', 'ma
# santé', 'my credit card') is answered by the rule, so it is no guess. But
# only when it says nothing else: round 9's repair left out of the guess count
# every question that NAMED a closed kind, so 'my health and my boat number
# 4800' … '4824' never counted, and the twenty-guess limit was gone. A
# question is the kind's own only when every word of it that says what it is
# about is a word of that kind — of what makes a thing his health or money,
# a phrase of it ('blood pressure', 'credit card'), or the kind's own name. A
# number, a code, a name or any other word, and it is a question like any
# other.
def _kind_vocab(kinds) -> frozenset:
    out: set[str] = set()
    for k in kinds:
        out |= _SENSE_WORDS.get(k, frozenset()) | CLASS_WORDS.get(k, frozenset())
        out |= _CATEGORY.get(k, frozenset()) | {stem(w) for w in k.split("_")}
        out |= {stem(w) for a, c in CLASS_ALIASES.items() if c == k for w in a.split()}
    return frozenset(out)


def kind_words_only(text, kinds) -> bool:
    """Is every word of this question that says what it is about a word of
    one of these kinds' own vocabulary (see above), in every reading of it?"""
    kinds = tuple(k for k in kinds or () if k in CLASSES)
    t = str(text or "")
    if not kinds or not t.strip():
        return False
    vocab = _kind_vocab(kinds)
    for r in readings(t):
        ws = content(r)
        if not ws:
            return False
        joined = f" {_joined(_normalise(r))} {_joined(fold(r))} "
        covered: set[str] = set()
        for k in kinds:
            for p, form in zip(_SENSE_PHRASES.get(k, ()), _PHRASE_FORMS.get(k, ())):
                if form in joined:
                    covered |= content(p) | {stem(w) for w in _words(fold(p))}
        for w in ws:
            fw = fold(w, frozenset())
            if not ({w, stem(w), fw, stem(fw)} & (vocab | covered)):
                return False
    return True


def fact_match(text, category, classes, topic_words: set[str],
               topic: str | None = None) -> tuple[int, str] | None:
    """Does a fact belong to a subject with these words? (score, reason) —
    the words they share, or the kind of thing the subject names — or None.

    With `topic` (the subject as asked), a private fact — his health, money,
    children, home, someone's confidence — belongs only to a subject that
    names that kind of thing (verify I-28: 'a letter to the landlord about
    Mom's apartment' shared only 'Mom' with 'Mom takes warfarin 5mg', and
    'invite Emma's in-laws' only 'Emma' with 'Emma is pregnant')."""
    f = content(text)
    shared = topic_words & f
    cat = (content(category) - {"general"}) & topic_words
    named = [c for c in classes or () if CLASS_WORDS.get(c, frozenset()) & topic_words]
    if not shared and not cat and not named:
        return None
    if topic is not None and classes:
        if not named and not cat and not set(_sensitivity(str(topic), "")) & set(classes):
            return None
        # 'Mom's medication' is about Mom: another person's private fact
        # ('Emma is pregnant') does not belong to it; 'my medications' is
        # about nothing but the kind, so every such fact does
        kind_words = set().union(*(CLASS_WORDS.get(c, frozenset()) for c in CLASSES))
        sens = set().union(*(_SENSE_WORDS.get(c, frozenset()) for c in CLASSES))
        rest = {w for w in topic_words if stem(w) not in kind_words | sens
                and w not in kind_words | sens}
        if rest and not rest & f:
            return None
    reasons = []
    if shared:
        reasons.append("it mentions " + ", ".join(sorted(shared)))
    if cat:
        reasons.append("it is filed under " + ", ".join(sorted(cat)))
    if named:
        reasons.append("you asked about " + " and ".join(CLASS_WORDS_PLAIN[c] for c in named))
    return 2 * len(shared) + len(cat) + len(named), "; ".join(reasons)


def tag_hits(rule_tags, text: str = "", tags=()) -> bool:
    """Does a rule about these subjects reach something with this text and
    these tags? A rule with no subject reaches everything. 'health' reaches
    a fact recognised as health even if the word is not in it; a phrase
    ('lives alone') must be there as whole words."""
    rts = [normalise(t) for t in (rule_tags or []) if normalise(t)]
    if not rts:
        return True
    if text and has_hidden(text):
        # read both ways (G5 repair): 'I​take​Ozempic' is about Ozempic
        return any(tag_hits(rule_tags, r, tags) for r in readings(text))   # neither has one
    tset = {normalise(t) for t in tags if normalise(t)}
    classes = {CLASS_ALIASES.get(t, t) for t in tset} & set(CLASSES)
    # ...read as written and through the fold (round 9, G5: a combining mark
    # or a look-alike letter inside a word hid it from the rule)
    have = {stem(w) for w in _words(str(text or ""))} | {stem(w) for t in tset
                                                          for w in _words(t)}
    if text and not str(text).isascii():
        have |= {stem(w) for w in _words(fold(text))}
    text = text if not text or str(text).isascii() else f"{text} \n {fold(text)}"
    for rt in rts:
        if rt in tset:
            return True
        cls = CLASS_ALIASES.get(rt, rt if rt in CLASSES else None)
        if cls and cls in classes:
            return True
        ws = words(rt)
        if len(ws) == 1:
            if stem(ws[0]) in have:
                return True
        elif ws and (phrase_in(rt, text) or any(phrase_in(rt, t) for t in tset)):
            return True
    return False


# --------------------------------------------------------- who is listening
SELF = "me"
FAMILY_WORDS = _stems("""wife husband spouse partner son daughter child mother father
    mom dad mum parent brother sister sibling grandson granddaughter grandchild
    grandmother grandfather grandma grandpa aunt uncle niece nephew cousin stepson
    stepdaughter stepmother stepfather family""")


# Ways of saying 'anyone' (verify I-10: a rule for 'everyone' was stored as
# written and never applied).
_ANYONE = frozenset({"anyone", "everyone", "everybody", "anybody", "all", "any one",
                     "every one", "the world", "the public", "others", "other people",
                     "everyone else", "anyone else", "anybody else", "everybody else",
                     "all others", "all other people", "people", "strangers", "tout le monde",
                     "n'importe qui", "les autres", "tous"})
# Titles that are not a name ('Mrs. Novak' is Novak).
_TITLES = frozenset({"mr", "mrs", "ms", "miss", "dr", "mme", "mlle", "m", "sir", "madam"})


_DETERMINER = re.compile(r"^(?:my|the|our|ma|mon|mes)\s+")
_ANY_DETERMINER = re.compile(r"^(?:my|the|our|ma|mon|mes|le|la|les|tout\s+le|all\s+the)\s+")
# Each way of saying 'anyone' with and without its first little word, so 'the
# public', 'public', 'the world' and 'world' are all 'anyone' (R2: 'the ' was
# taken off before the list was read, so 'the public' and 'the world' never
# matched, and a no for them let the family key read his health).
_ANYONE_ALL = (_ANYONE | frozenset(_ANY_DETERMINER.sub("", a) for a in _ANYONE)
               | frozenset({"general public", "public at large", "whole world",
                            "the whole world", "the general public", "le public",
                            "le grand public", "grand public"})) - {"monde", "le monde"}
# Not 'le monde' or 'monde': that is also a newspaper, or a person's name, and
# a yes for it must not open a subject to everyone.


# The kinds of people and groups someone can be ('My sister: …' is his
# sister speaking — provenance reads this).
SOMEONE_WORDS = FAMILY_WORDS | _stems("""
    ex exwife exhusband fiance fiancee girlfriend boyfriend widow widower inlaws
    stepchild stepson stepdaughter kid children grandkid grandchildren relative relatives
    friend neighbour neighbor roommate tenant landlord landlady caretaker executor
    trustee guardian doctor physician nurse psw caregiver carer pharmacist dentist
    therapist psychologist psychiatrist specialist surgeon physio chiropractor
    optometrist counsellor counselor hospital clinic pharmacy bank banker lawyer
    notary accountant advisor adviser planner broker insurer insurance realtor agent
    attorney priest pastor minister rabbi imam church parish congregation choir club
    colleague coworker boss employer employee manager government police officer court
    judge school teacher press newspaper reporter journalist media plumber
    electrician contractor mechanic visitor guest buyer seller salesman saleswoman
    voisin voisine voisins voisines ami amie amis amies médecin medecin docteur
    infirmier infirmière infirmiere pharmacien dentiste banque banquier avocat
    notaire comptable conseiller assureur propriétaire proprietaire locataire sœur
    soeur frère frere fils fille femme mari mère mere père pere maman papa oncle
    tante neveu nièce niece cousine épouse epouse époux epoux conjoint conjointe
    enfant enfants famille prêtre pretre pasteur église eglise patron collègue
    collegue gouvernement école ecole journaliste
    """)


# --------------------------------------------------- who a 'no' is for (R2)
# A rule that says NO names exactly its audience — every way that audience is
# written ('Karen Novak' is also 'Karen' and 'my ex-wife'), and no one else —
# except that an explicit anyone-word means every audience other than the
# owner's own keys: 'anyone', 'everyone', 'the public', 'members of the
# public', 'the world', 'nobody', 'people', 'les gens', 'tout le monde',
# 'quiconque', 'n'importe qui' … with or without its first little word, alone
# or beside other names ('the public or the press', 'nobody but my doctor',
# 'le public et la banque'). A name that merely holds such a word is a name:
# 'Le Monde' is a newspaper, 'Mr. Nobody' a man. (Round 4 kept a list of
# ways to say anyone; round 5 made every 'no' it did not recognise a no for
# everyone, and blinded his own caretaker; both are gone.)
_ANYONE_PHRASES = frozenset("""
    anyone|anybody|any one|everyone|everybody|every one|all|all people|all others|
    all other people|others|other people|everyone else|anyone else|anybody else|
    everybody else|nobody else|no one else|noone else|no-one else|people|persons|folks|
    strangers|stranger|outsiders|outsider|public|general public|public at large|
    members of the public|member of the public|world|whole world|entire world|
    world at large|wide world|whole wide world|internet|social media|society|
    tout le monde|monde entier|les autres|autres|gens|n'importe qui|nimporte qui|
    quiconque|tous|toutes|chacun|chacune|personne|personne d'autre|aucun|aucune|nul|
    grand public|reseaux sociaux|nobody|no one|no-one|noone|none|whoever|whomever
    """.replace("\n", " ").split("|")) - {""}
_ANYONE_PHRASES = frozenset(" ".join(p.split()) for p in _ANYONE_PHRASES)
# A part of an audience that STARTS with one of these is everyone, whatever
# follows ('anyone who asks', 'everyone in the world', 'no-one at all').
_ANYONE_HEADS = frozenset("""anyone anybody everyone everybody nobody noone no-one whoever
    whomever quiconque chacun chacune""".split())
# 'any', 'all', 'every' … of a person in general ('every person', 'any
# stranger', 'toute personne'); 'all the family' is still the family.
_QUANTIFIERS = frozenset("any all every each no tout toute tous toutes aucun aucune "
                         "n'importe nimporte".split())
_GENERIC_PERSON = frozenset("""person persons people one body folks human humans individual
    individuals stranger strangers outsider outsiders citizen citizens personne personnes
    gens monde qui""".split())
_DETERMINERS = frozenset("the a an my our his her their le la les l' un une des du de "
                         "d'".split())
_PART_BREAK = re.compile(r"\s*(?:[,;/&+|]|\b(?:and|or|but|except(?: for)?|other than|apart "
                         r"from|aside from|besides|nor|et|ou|mais|sauf|hormis|excepte|a part"
                         r"|ni)\b)\s*")


def _plain_words(text: str) -> str:
    """An audience in one spelling, read through the fold (round 8: 'Сlaude'
    with a Cyrillic С, 'C l a u d e', 'Cl4ude', 'ma sœur', 'my sister' with a
    zero-width space), accents off, lower case."""
    n = fold(text)
    return re.sub(r"[^\w'\- ,;/&+|]", " ", n)


# Round 7: more ways of saying 'anyone' the convergence skeptics wrote ('not
# a soul', 'absolutely anyone', 'qui que ce soit', 'the masses', 'les gens du
# village', 'outside people'). Words that only make 'anyone' stronger are
# read past ('absolutely anyone' is anyone).
_ANYONE_PHRASES = _ANYONE_PHRASES | frozenset("""
    soul|a soul|souls|a living soul|living soul|single soul|a single soul|masses|the masses|
    population|general population|the population|qui que ce soit|tout un chacun|un chacun|
    etranger|etrangers|etrangere|etrangeres|n'importe lequel|n'importe laquelle|
    n'importe lesquels|n'importe lesquelles|nimporte lequel|nimporte laquelle|
    all and sundry|tom dick and harry|every tom dick and harry|third parties|third party|
    tiers|public en general|gens de l'exterieur|le grand public|grand monde
    """.replace("\n", " ").split("|")) - {""}
_ANYONE_PHRASES = frozenset(" ".join(p.split()) for p in _ANYONE_PHRASES)
_ANYONE_HEADS = _ANYONE_HEADS | frozenset("n'importe nimporte quiconque".split())
_STRONGER = frozenset("""absolutely literally just simply really truly totally quite
    basically virtually practically almost nearly not never even strictly
    vraiment absolument strictement surtout pas meme""".split())
# A part that starts with, or ends in, one of these — with no name in it —
# is people in general ('les gens du village', 'outside people', 'people in
# town', 'random folks').
_PEOPLE_PLURAL = frozenset("""people persons folks gens personnes humans individuals
    strangers outsiders etrangers inconnus""".split())


def _anyone_part(ws: list[str], raw_part: str) -> bool:
    phrase = " ".join(ws)
    if phrase in _ANYONE_PHRASES or ws[0] in _ANYONE_HEADS:
        return True
    if len(ws) >= 2 and (ws[0], ws[1]) in {("no", "one"), ("any", "one"), ("every", "one")}:
        return True
    if ws[0] in _QUANTIFIERS and len(ws) >= 2 and ws[1] in _GENERIC_PERSON:
        return True
    later = raw_part.strip().split()[1:]
    named = any(re.match(r"[A-Z][a-z]", w) for w in later) or {stem(w) for w in ws} & SOMEONE_WORDS
    if not named and (ws[0] in _PEOPLE_PLURAL or ws[-1] in _PEOPLE_PLURAL):
        return True
    return False


# 'le monde' in lower case is everyone ('ne le dis pas à le monde', 'tout le
# monde'); 'Le Monde' with its capital M, as a newspaper is written, is the
# newspaper (D1, round 7: round 6 made every 'le monde' the newspaper).
_LE_MONDE_ANY = re.compile(r"(?<![^\W_])(?:le|la|du)\s+monde(?![^\W_])", re.I)
_LE_MONDE_BRAND = re.compile(r"(?<![^\W_])[Ll]e\s+Monde(?![^\W_])")
# ('LE MONDE' in capitals could be either: for a 'no', everyone.)


def is_anyone(audience) -> bool:
    """Does this audience, as a rule that says NO names it, mean everyone
    (other than the owner's own keys)? Only an explicit anyone-word does
    ('the public or the press', 'nobody but my doctor', 'les gens', 'not a
    soul', 'le monde'); 'Le Monde', 'Mr. Nobody', 'my GP' and 'Bob' each
    name only themselves. Read both ways (round 9, second repair): it is
    everyone when either reading is."""
    return any(_is_anyone_one(r) for r in audience_readings(audience))


def _is_anyone_one(audience) -> bool:
    text = str(audience or "")
    raw = _plain_words(text)
    if not raw.strip():
        return False
    if norm_audience(text) == "anyone":
        return True
    if _LE_MONDE_ANY.search(text) and not _LE_MONDE_BRAND.search(text):
        return True
    raws = _PART_BREAK.split(text)
    for k, part in enumerate(_PART_BREAK.split(raw)):
        ws = [w for w in part.split() if w]
        while ws and (ws[0] in _DETERMINERS or ws[0].rstrip("'") in ("l", "d")
                      or ws[0] in _STRONGER and len(ws) > 1):
            ws = ws[1:]
        if not ws:
            continue
        if ws[0] in _TITLES:
            continue                                  # Mr. Nobody, Mrs. World
        if _anyone_part(ws, raws[k] if len(raws) > k else part):
            return True
    return False


# --------------------------------------------- a 'no' that names an AI (D1)
# Round 7 decision: a rule that says NO to an AI, an engine or the company
# behind one binds EVERY key that reaches an engine — Claude, ChatGPT, a
# model on this Mac, and his own caretaker key 'jefferey' too. Only the owner
# himself, reading at his own keyboard, is not an AI. Written with or without
# a little word before it ('the AI', 'any AI', "l'IA", 'my assistant').
AI_READER = "any ai"          # in every audience list of a key that reaches an engine
_AI_WORDS = frozenset("""ai ais a.i a.i. ia ias chatbot chatbots chatbot's bot bots robot
    robots chatgpt gpt gpts gpt4 gpt-4 gpt-4o gpt4o gpt-5 gpt5 openai claude anthropic gemini
    bard copilot llama llamas hermes llm llms grok mistral deepseek perplexity
    engine engines moteur moteurs google microsoft meta
    jefferey jeffrey jeffery butler ollama model models modele modeles computer computers
    ordinateur ordinateurs machine machines alexa siri cortana mixtral qwen gemma phi""".split())
_AI_PHRASES = frozenset(" ".join(p.split()) for p in """
    artificial intelligence|intelligence artificielle|intelligences artificielles|the cloud|
    cloud|le cloud|the assistant|assistant|assistants|ai assistant|virtual assistant|
    assistant virtuel|google|microsoft|meta|open ai|chat gpt|language model|language models|
    large language model|machine learning|siri|alexa|cortana|le chat|local model|
    the local model""".split("|") if p.strip())
# A word that starts with an engine's name is that engine ('gpt4o', 'llama3',
# 'claude-raw' read as 'claude raw', 'hermes3').
_AI_STEM = re.compile(r"^(?:gpt|chatgpt|claude|llama|gemini|mistral|mixtral|hermes|qwen|gemma"
                      r"|deepseek|ollama|copilot|grok|openai|anthropic)[a-z0-9.]*$")


def _audience_words(part: str) -> list[str]:
    """The words of one part of an audience, its little words off the front:
    hyphens as spaces ('AI-powered', 'claude-raw'), possessives as the word
    ("AI's"), "l'IA" as 'ia'."""
    ws = []
    for w in part.replace("-", " ").split():
        w = w.strip(".'")
        if w.endswith("'s"):
            w = w[:-2]
        if w.startswith(("l'", "d'")):
            w = w[2:]
        if w:
            ws.append(w)
    while ws and (ws[0] in _DETERMINERS or ws[0] in _QUANTIFIERS or ws[0] in _STRONGER
                  or ws[0] in ("other", "others", "autre", "autres")):
        ws = ws[1:]
    return ws


def names_ai(audience, extra=()) -> bool:
    """Does this audience name an AI, an engine or a company that makes one
    ('ChatGPT', 'any AI', "l'IA", 'chatbots', 'artificial intelligence',
    'Google', 'the cloud', 'the public and ChatGPT', 'JEFFEREY', 'the local
    model', 'my computer', 'Сlaude', "AI's", 'claude-raw')? `extra`: the
    names of the engines reading right now. Read both ways: it names one
    when either reading does."""
    return any(_names_ai_one(r, extra) for r in audience_readings(audience))


def _names_ai_one(audience, extra=()) -> bool:
    raw = _plain_words(re.sub(r"(?i)(?<![^\W_])a\.\s?i(?![^\W_])\.?", "ai", str(audience or "")))
    if not raw.strip():
        return False
    more = {str(x).lower() for x in extra or () if x}
    for part in _PART_BREAK.split(raw):
        ws = _audience_words(part)
        if not ws:
            continue
        if set(ws) & (_AI_WORDS | more) or " ".join(ws) in _AI_PHRASES \
                or any(_AI_STEM.match(w) for w in ws):
            return True
        whole = part.replace("-", " ").split()            # 'Le Chat', with its 'le'
        if any(" ".join(x[i:i + n]) in _AI_PHRASES for x in (ws, whole) for n in (2, 3)
               for i in range(len(x) - n + 1)):
            return True
    return False


# ------------------------------------- a 'no' that names his family (D1)
# Round 7 decision: a rule that says NO to his family, or to the people who
# read through his family's key — his children, grandchildren and relatives
# — binds the family key, in English and in French ('ma famille', 'mes
# enfants', 'my kids', 'my daughter', 'ma fille', 'mon fils'). Round 8 (F1):
# every kinship word, in English and French — wife, husband, partner,
# spouse, sister, brother, nephew, niece, cousin, aunt, uncle, mother,
# father, mom, mum, dad, parents, any in-law, step-, grand-, great-; femme,
# mari, conjoint, sœur, frère, neveu, nièce, cousin(e), tante, oncle, mère,
# père, belle-, beau-, demi-, petit(e)- … A part of an audience is the
# family when, past its little words, it is kinship words only, with perhaps
# a name after them ('my brother Mike'). A possessive or a 'de' is someone
# else ("my son's teacher", 'la femme de ménage', 'le mari de Karen').
_KIN = frozenset("""family families relatives relative kin kinfolk wife wives husband husbands
    spouse spouses partner partners son sons daughter daughters child children childrens kid
    kids baby babies mother mothers father fathers mom moms mum mums mommy mummy mama dad
    dads daddy papa parent parents brother brothers sister sisters sibling siblings nephew
    nephews niece nieces cousin cousins aunt aunts auntie aunty uncle uncles grandson
    grandsons granddaughter granddaughters grandchild grandchildren grandkid grandkids
    grandmother grandmothers grandfather grandfathers grandma grandmas grandpa grandpas
    granny grannies nana grandparent grandparents stepson stepsons stepdaughter
    stepdaughters stepchild stepchildren stepmother stepfather stepbrother stepbrothers
    stepsister stepsisters stepmom stepdad inlaw inlaws fiance fiancee twin twins godson
    goddaughter godchild godmother godfather descendants
    famille familles proches parente parents parent femme epouse epoux mari maris conjoint
    conjointe conjoints fils fille filles enfant enfants bebe mere meres pere peres maman
    frere freres soeur soeurs neveu neveux niece cousine cousines tante tantes oncle oncles
    mamie mamy papi papy pepere memere""".split())
_KIN_MODIFIERS = frozenset("""in law laws step great grand half ex late older younger elder
    eldest oldest youngest little big own dear beloved whole entire extended immediate close
    grands grande grandes belle belles beau beaux demi petit petite petits petites arriere
    aine ainee cadet cadette cher chere chers cheres all toute tout tous toutes member members
    membres""".split())
_FAMILY_MEMBERS = _KIN          # (round 7's name for the list)


_FAM_DET = frozenset("""the a an my our his her their your le la les un une des du de ma mon
    mes ta ton tes sa son ses notre nos votre vos leur leurs""".split())


def _family_part(part: str, raw_part: str = "") -> bool:
    """Is this one part of an audience his family (see above)?"""
    if re.search(r"\w's\b", part):
        return False                       # 'my son's teacher' is the teacher
    ws = []
    for w in part.replace("-", " ").split():
        if w.startswith(("l'", "d'")) and len(w) > 2:
            if ws:
                return False               # 'le fils d'Anna' is Anna's son
            w = w[2:]
        ws.append(w.strip("'."))
    ws = [w for w in ws if w]
    while len(ws) > 1 and ws[0] in _FAM_DET:
        ws = ws[1:]                        # 'son médecin' is 'his doctor'
    names = {fold(w) for w in raw_part.replace("-", " ").split() if re.match(r"[A-Z][a-z]", w)}
    kin = False
    for w in ws:
        if w in _KIN:
            kin = True
        elif w in _KIN_MODIFIERS or w in _FAM_DET and w not in ("de", "du", "des"):
            continue                       # 'all the family', 'my own sister'
        elif kin and w in names:
            continue                       # 'my brother Mike'
        else:
            return False                   # 'la femme de ménage', 'my business partner'
    return kin


def names_family(audience) -> bool:
    """Does this audience name his family, or the people who use the family
    key ('ma famille', 'my kids', 'the grandchildren', 'my daughter', 'my
    sister', 'the in-laws', 'ma belle-fille', 'my brother Mike')? Read both
    ways: it does when either reading does."""
    return any(_names_family_one(r) for r in audience_readings(audience))


def _names_family_one(audience) -> bool:
    raw = _plain_words(audience)
    raws = _PART_BREAK.split(str(audience or ""))
    for k, part in enumerate(_PART_BREAK.split(raw)):
        if _family_part(part.strip(), raws[k] if len(raws) > k else ""):
            return True
    return False


def norm_audience(s) -> str:
    """'My Sister' and 'sister' are one audience; 'the family' is 'family';
    'everyone', 'everybody', 'the public' and 'the world' are 'anyone'.
    One reading — a character that shows as nothing read as nothing; every
    check of who a rule is for reads both (norm_audiences)."""
    n = normalise(s).strip(" .,:;!\"'")
    if n in _ANYONE_ALL or _ANY_DETERMINER.sub("", n) in _ANYONE_ALL:
        return "anyone"
    n = _DETERMINER.sub("", n).strip(" .,:;!\"'")
    return "anyone" if n in _ANYONE_ALL else n


# ------------------------------------ a name read both ways (round 9, fix 2)
# A character that shows as nothing or as a blank inside a person's name —
# 'Karen⠀Novak', 'KarenㅤNovak', 'Karen​Novak' — was read only
# as nothing ('karennovak'), so she was nobody: 'Never tell Karen when I
# travel' did not meet her, and 'Anyone may know when I travel' let her
# hear it. Every check of who a rule is for now reads an audience both
# ways, as nothing and as a space: a NO holds when either reading meets it,
# a YES only when both readings do. Accents written as separate marks are
# put on their letters first ('Renée' is 'Renée'), so a name typed that
# way is one name.
def audience_readings(audience) -> tuple[str, ...]:
    """The ways an audience is read: as written, or — when it holds a
    character that shows as nothing — with each read as nothing and again
    as a space. Runs of space are one."""
    t = unicodedata.normalize("NFC", str(audience or ""))
    out: list[str] = []
    for r in readings(t):
        r = " ".join(r.split())
        if r not in out:
            out.append(r)
    return tuple(out)


def norm_audiences(s) -> frozenset:
    """norm_audience of every reading of this audience (one, unless it holds
    a character that shows as nothing)."""
    return frozenset(norm_audience(r) for r in audience_readings(s))


def is_blank(audience) -> bool:
    """Is this audience nothing at all once what shows as nothing is read as
    nothing — empty, spaces, '​', 'ㅤ', ' ﻿ '?"""
    return not any(r.strip() for r in audience_readings(audience))


def _emails_in(text) -> set[str]:
    return emails_of(text)


def rule_names(audience, people=()) -> frozenset:
    """Every way a rule that says NO to this audience reaches someone
    (verify I-24): the audience as written, each word of its name, and — when
    it names someone recorded in his life story — that person, their
    relationship to him, and the addresses noted for them. A no for 'Karen
    Novak' then meets 'Karen', 'Mrs. Novak', 'my ex-wife' and her address.
    A no meets every reading of its audience and of each person's name (round
    9, second repair: 'Never tell Karen\u2800Novak' is a no for Karen Novak)."""
    out: set[str] = set()
    for r in audience_readings(audience):
        out |= _rule_names_one(r, people)
    return frozenset(out)


def _rule_names_one(audience, people=()) -> set[str]:
    n = norm_audience(audience)
    if not n or n in (SELF, "anyone"):
        return {n} if n else set()
    out = {n} | {w for w in words(n) if len(w) >= 2 and w not in STOP and w not in _TITLES}
    nw = {w for w in words(n) if w not in _TITLES}
    for p in people or ():
        if not isinstance(p, dict):
            continue
        for pn in norm_audiences(p.get("name", "")):
            for rel in norm_audiences(p.get("relationship", "")):
                pw = {w for w in words(pn) if w not in _TITLES}
                if not pn:
                    continue
                if n == pn or (nw and pw and (nw <= pw or pw <= nw)) or (rel and n == rel):
                    out |= {pn} | ({rel} if rel else set())
                    out |= _emails_in(p.get("notes", ""))
    out.discard("")
    out.discard(SELF)
    return out


# ------------------------------- an audience no one knows is everyone (F1)
# Round 8: a 'no' whose audience — or any part of it before 'but', 'except'
# or 'other than', which say who MAY hear it — is not a person he recorded
# himself, not the name of one of his keys, and not a group JEFFEREY knows
# (an anyone-word, a family word, an AI word) holds for everyone and every
# AI. Round 7 let a no for 'my lawyer', 'Bob' or 'the press' bind only a
# reader of that very name, which in practice was nobody.
_EXCEPT = re.compile(r"(?<![^\W_])(?:but|except(?:\s+for)?|other\s+than|apart\s+from|aside\s+from"
                     r"|besides|mais|sauf|hormis|excepte|a\s+part|à\s+part)(?![^\W_])", re.I)
_SELF_WORDS = frozenset("me myself moi i".split())


# ---------------------------------------- a 'no' for himself (G1, round 9)
# Round 8 read 'me', 'myself', 'just me' and 'moi' as the owner — and a no
# for the owner bound nobody, so 'Keep my health to myself' (audience
# 'myself', or no audience at all, which every surface stored as 'me') let
# the family key read his diabetes. Now a no whose audience — or any part of
# it before 'but' or 'except' — is himself holds as a no for someone nobody
# knows does: for everyone and every AI but his own JEFFEREY.
_SELF_ALONE = frozenset("me myself moi i meme moimeme".split())
_SELF_ONLY = frozenset("just only juste seulement rien que simply solely uniquement "
                       "that's thats c'est".split())
_SELF_FOLD = _SELF_ALONE | _SELF_ONLY | frozenset({"moi-meme"})


def names_self(audience) -> bool:
    """Does this audience — the part before 'but' or 'except' — name the
    owner himself ('me', 'Me', 'ME', 'myself', 'just me', 'only me', 'I',
    'moi', 'moi-même', 'juste moi', 'mе' with a Cyrillic е, 'my​self')?
    Read both ways: it does when either reading does (a no for him holds for
    everyone, so reading more of them as him only widens a no)."""
    return any(_names_self_one(r) for r in audience_readings(audience))


def _names_self_one(audience) -> bool:
    text = " ".join(str(audience or "").split())
    if not text:
        return False
    m = _EXCEPT.search(text)
    if m:
        text = text[:m.start()]
    n = fold(text, _SELF_FOLD)
    n = re.sub(r"[^\w' ,;/&+|\-]", " ", n)
    for part in _PART_BREAK.split(n):
        ws = [w.strip("'.-") for w in part.replace("-", " ").split()]
        ws = [w for w in ws if w and w not in _SELF_ONLY and w not in _STRONGER]
        if ws and all(w in _SELF_ALONE for w in ws):
            return True
    return False


def only_self(audience) -> bool:
    """Is this audience the owner himself and nobody else — EVERY part of it,
    after 'and', 'but' or a comma too ('me', 'myself', 'just me', 'moi-même',
    'me and myself')? Round 9 repair: names_self is true when ANY part is him
    (right for a no, which then holds for everyone), and check_disclosure's
    'the owner may always hear about himself' used it, so 'me and Karen
    Novak', 'moi et ChatGPT' and 'me and the man on the phone' were a silent
    yes. An audience with anyone else in it is asked about as that audience.

    Round 9, second repair: a word that says no — not, never, no, pas,
    jamais, ni, sauf, except, but, other than, besides … — anywhere in it
    means it is not only him ('not me', 'pas moi', 'never me', 'not even me'
    were read as 'me' made stronger, and were a silent yes); and an audience
    that holds a character that shows as nothing is only him when BOTH its
    readings are ('m\u200be' is also 'm e')."""
    rs = audience_readings(audience)
    return bool(rs) and all(_only_self_one(r) for r in rs)


# The words that say no, or leave someone out, in an audience (round 9,
# second repair): with one of them anywhere, it is never only him.
_NEGATION = re.compile(
    r"(?<![^\W_])(?:not|never|no|none|nobody|noone|nor|neither|pas|jamais|ni|non|sauf"
    r"|aucun|aucune|personne|except|excepting|excepted|exception|excluding|exclude|without"
    r"|but|besides|other\s+than|rather\s+than|instead\s+of|apart\s+from|aside\s+from"
    r"|hormis|excepte|exceptee|a\s+part|plutot\s+que|au\s+lieu\s+de|sans)(?![^\W_])")


def _only_self_one(audience) -> bool:
    text = " ".join(str(audience or "").split())
    if not text:
        return False
    if _NEGATION.search(fold(text, frozenset())) or _NEGATION.search(normalise(text)):
        return False                     # 'not me', 'pas moi', 'everyone but me'
    if norm_audience(text) == SELF:
        return True                      # 'me', 'Me.', 'ME!'
    n = fold(text, _SELF_FOLD)
    if _NEGATION.search(n):
        return False
    if re.search(r"[^\w' ,;/&+|\-]", n):
        return False                     # an address, a bracket, a sign: someone else
    parts = [p for p in _PART_BREAK.split(n) if p and p.strip(" ,;/&+|-")]
    if not parts:
        return False
    for part in parts:
        ws = [w.strip("'.-") for w in part.replace("-", " ").split()]
        ws = [w for w in ws if w and w not in _SELF_ONLY and w not in _STRONGER]
        if not ws or not all(w in _SELF_ALONE for w in ws):
            return False
    return True


def person_key(name, relationship="") -> tuple[str, str]:
    """A person he recorded, the way an audience is compared with them. A
    name whose two readings differ ('Karen\u2800Novak') is no name a rule's
    audience is known by (round 9, second repair): a no for her then holds
    for everyone, as a no for someone nobody knows does."""
    def one(x) -> str:
        ks = {norm_audience(fold(r)) for r in audience_readings(x)} or {""}
        return ks.pop() if len(ks) == 1 else ""
    return (one(name), one(relationship))


@functools.lru_cache(maxsize=1 << 12)
def _unknown_parts(audience: str, people: tuple, keys: frozenset) -> tuple[str, ...]:
    text = " ".join(audience.split())
    whole = _plain_words(text).strip(" .,;:!")
    if whole in _ANYONE_PHRASES or norm_audience(text) == "anyone":
        return ()                               # 'all and sundry', 'tom dick and harry'
    m = _EXCEPT.search(text)
    if m:
        text = text[:m.start()]                 # 'nobody but my doctor': the doctor may
    raws = [p for p in _PART_BREAK.split(text) if p and p.strip(" ,;/&+|")]
    out = []
    for rp in raws:
        ws = _audience_words(_plain_words(rp))
        if not ws:
            continue
        if is_anyone(rp) or names_ai(rp) or names_family(rp):
            continue                            # a group JEFFEREY knows
        joined = " ".join(ws)
        if joined in _SELF_WORDS:
            continue
        n = norm_audience(fold(rp))
        if n in keys or joined in keys or joined.replace(" ", "-") in keys:
            continue                            # one of his keys
        nw = set(ws) - _TITLES
        if any(n and (n == pn or n == rel) or joined == pn or (rel and joined == rel)
               or (nw and nw <= (set(pn.replace(".", " ").split()) - _TITLES))
               for pn, rel in people if pn):
            continue                            # a person he recorded
        out.append(rp.strip(" ,;/&+|"))
    return tuple(out)


def unknown_parts(audience, people=(), keys=()) -> tuple[str, ...]:
    """The parts of a 'no''s audience nobody knows (F1): not a person he
    recorded (`people`: person_key tuples of the people HE recorded), not
    one of his keys' names, not an anyone-, family- or AI-word. Empty when
    every part is known. Read both ways: a part nobody knows in either
    reading is one nobody knows (its no then holds for everyone)."""
    out: list[str] = []
    ks = frozenset(norm_audience(k) for k in keys)
    for r in audience_readings(audience):
        out += [x for x in _unknown_parts(r, tuple(people), ks) if x not in out]
    return tuple(out)


_ADDRESSED = re.compile(r"^(.*?)<\s*([^<>\s]+@[^<>\s]+)\s*>\s*$")
_EMAIL = re.compile(r"[^\s@<>]+@[^\s@<>]+")


# ------------------------------------- someone, by a whole match (G3, round 9)
# Round 8's triage asked `addr in notes`, so any address that was the END of
# a recorded person's ('5@example.com', 'novak1985@example.com') was that
# person, and a scam from it scored 0.0. An address is someone's only when it
# is the whole address (case-folded, trimmed, read through the fold); a phone
# number only when it is the whole number (digits only, a leading 1 for North
# America set aside). A display name alone never makes anyone someone he
# recorded.
_PHONE_IN_TEXT = re.compile(r"(?<![\w+])\+?\d[\d \t().\-]{5,}\d(?!\w)")


def email_key(text) -> str:
    """One address in one spelling: trimmed, case-folded, through the fold
    (no word is read back), without a 'mailto:' or the brackets around it."""
    t = fold(str(text or ""), frozenset()).strip().strip(".,;:()<>\"'[]")
    if t.startswith("mailto:"):
        t = t[7:]
    return t


def emails_of(text) -> set[str]:
    """Every whole e-mail address written in this text, as email_key."""
    return {email_key(e) for e in _EMAIL.findall(visible(text))} - {""}


def phone_key(text) -> str:
    """A phone number as its digits, a leading 1 for North America set aside
    ('+1 (613) 555-0142' and '6135550142' are one number)."""
    d = re.sub(r"\D", "", fold(str(text or ""), frozenset()))
    return d[1:] if len(d) == 11 and d.startswith("1") else d


def phones_of(text) -> set[str]:
    """Every whole phone number written in this text (seven digits or
    more), as phone_key."""
    return {k for k in (phone_key(m.group()) for m in _PHONE_IN_TEXT.finditer(visible(text)))
            if len(k) >= 7}


def audience_aliases(audience, people=()) -> tuple[frozenset, frozenset]:
    """Every name this audience may be known by to the owner's rules:
    (broad, strict). A rule that says NO is matched against `broad` — each
    word of a display name, an e-mail address's name part, and the person
    and relationship recorded in his life story ('Karen' → his ex-wife →
    family). A rule that says YES is matched against `strict` only — the
    whole name or address as written, or the recorded person it exactly is.

    Read both ways (round 9, second repair): an audience that holds a
    character that shows as nothing ('Karen\u2800Novak') is every name either
    reading is known by for a no (broad), and only the names both readings
    are known by for a yes (strict)."""
    rs = audience_readings(audience)
    if len(rs) <= 1:
        return _audience_aliases_one(rs[0] if rs else "", people)
    pairs = [_audience_aliases_one(r, people) for r in rs]
    return (frozenset().union(*(b for b, _ in pairs)),
            frozenset.intersection(*(st for _, st in pairs)))


def _audience_aliases_one(audience, people=()) -> tuple[frozenset, frozenset]:
    raw = normalise(audience)
    if not raw or norm_audience(raw) == SELF:
        return frozenset(), frozenset()
    m = _ADDRESSED.match(raw)
    if m:
        name, email = m.group(1).strip(" \"'"), m.group(2)
    elif _EMAIL.fullmatch(raw):
        name, email = "", raw
    else:
        name, email = raw, ""
    strict: set[str] = set()
    broad: set[str] = set()
    if email:
        email = email_key(email)
        local = email.split("@", 1)[0]
        # with an address, a yes meets only that whole address (G3, round 9:
        # 'Anna <stranger@example.net>' was Anna for a yes by her display
        # name, and the part before the @ was a name of its own)
        strict |= {email}
        broad |= {local} | {p for p in re.split(r"[._+\-0-9]+", local) if len(p) >= 2}
    if name:
        n = norm_audience(name)
        (broad if email else strict).update({name, n})
        broad |= {w for w in words(n) if w not in STOP and w not in _TITLES}
    for p, pn, rel, agree in _person_readings(people):
        pw = set(words(pn))
        noted = emails_of(p.get("notes", ""))
        # a person is this audience exactly by a whole address noted for them,
        # or — with no address given — by their whole recorded name (G3); a
        # name whose two readings differ is never exactly anyone, for a yes
        exact = agree and (bool(email and email in noted) or bool(not email and pn in strict))
        # 'my ex-wife' is the person recorded as his ex-wife; 'knovak@…'
        # holds her surname (verify I-24) — for a NO, never for a yes
        if rel and norm_audience(raw) == rel:
            broad |= {pn, rel}
        if email:
            local = email.split("@", 1)[0]
            for w in pw:
                if len(w) >= 4 and w in local:
                    broad.add(w)
        if exact or (pw and pw <= broad):
            broad |= {pn} | ({rel} if rel else set()) | set(words(rel))
            if exact:
                strict |= {pn} | ({rel} if rel else set())
            if {stem(w) for w in words(rel)} & FAMILY_WORDS:
                broad.add("family")
    broad |= strict
    for s in (broad, strict):
        s.discard("")
        s.discard(SELF)
    return frozenset(broad), frozenset(strict)


def _person_readings(people):
    """(person, name, relationship, whether every reading agrees) for each
    reading of each recorded person's name and relationship."""
    for p in people or ():
        if not isinstance(p, dict):
            continue
        pns = [x for x in norm_audiences(p.get("name", "")) if x]
        rels = sorted(norm_audiences(p.get("relationship", ""))) or [""]
        agree = len(pns) == 1 and len(rels) == 1
        for pn in pns:
            for rel in rels:
                yield p, pn, rel, agree


# ----------------------------------------------------- the fold's own words
# The words the shared fold may read back from digits, symbols, spaced-out
# or split letters (see fold): those of an audience, of his health and
# money, of a secret and of the door. A reader may pass its own.
FOLD_WORDS = frozenset(
    {w for w in _AI_WORDS if w.isalpha()}
    | {w for p in _AI_PHRASES for w in p.split()} | {p.replace(" ", "") for p in _AI_PHRASES}
    | _KIN | {"inlaws", "inlaw", "stepson", "stepdaughter", "grandson", "granddaughter",
              "grandchildren", "grandkids", "noone", "nobody", "everyone", "anyone"}
    | {w for p in _ANYONE_PHRASES for w in p.split() if w.isalpha()}
    | set(_HEALTH_LEX.split()) | set().union(*_SENSE_WORDS.values())
    | set("""password passwords passwd passcode passcodes passphrase pin pins nip code codes
          digicode combination combinaison combo mdp pwd unlock opener secret
          let lets in inside into up open opens door doors lock locks locked unlock unlocked
          unlocking key keys gate garage alarm alarms enter entry porte portes cle cles
          serrure entrer rentrer ouvre ouvrir""".split()))
