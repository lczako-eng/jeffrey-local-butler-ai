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

3. **Who is listening (I-24).** 'karen', 'Karen Czako' and
   'Karen Czako <karen@example.com>' are the same person to the owner's
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


@functools.lru_cache(maxsize=1 << 16)
def _normalise(t: str) -> str:
    t = unicodedata.normalize("NFKC", t).translate(_QUOTES).casefold()
    return re.sub(r"\s+", " ", t).strip()


def normalise(text) -> str:
    """One spelling for the same words: compatible characters folded,
    straight quotes, case folded, runs of space made one."""
    return _normalise(str(text or ""))


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


@functools.lru_cache(maxsize=1 << 16)
def _content(t: str, names: bool = False) -> frozenset:
    n = unicodedata.normalize("NFKC", t).translate(_QUOTES)
    long = re.findall(r"[^\W\d_]{3,}", n)
    shouting = bool(long) and sum(w.isupper() for w in long) >= 0.6 * len(long)
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
            if _short_keeps(w, low, shouting, names):
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
    ws = _words(t)
    st = {stem(w) for w in ws}
    joined = f" {' '.join(ws)} "
    cat = {stem(w) for w in _words(category)}
    found = set()
    for cls in CLASSES:
        if st & _SENSE_WORDS.get(cls, frozenset()):
            found.add(cls)
        elif any(p in joined for p in _PHRASE_FORMS.get(cls, ())):
            found.add(cls)
        elif any(rx.search(t) for rx in _SENSE_PATTERNS.get(cls, ())):
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
    so). An empty list means nothing sensitive was recognised."""
    return list(_sensitivity(str(text or ""), str(category or "")))


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
    tset = {normalise(t) for t in tags if normalise(t)}
    classes = {CLASS_ALIASES.get(t, t) for t in tset} & set(CLASSES)
    have = {stem(w) for w in _words(str(text or ""))} | {stem(w) for t in tset
                                                          for w in _words(t)}
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
# Titles that are not a name ('Mrs. Czako' is Czako).
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
# written ('Karen Czako' is also 'Karen' and 'my ex-wife'), and no one else —
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
    n = normalise(text)
    n = "".join(c for c in unicodedata.normalize("NFKD", n) if not unicodedata.combining(c))
    return re.sub(r"[^\w'\- ,;/&+|]", " ", n)


def is_anyone(audience) -> bool:
    """Does this audience, as a rule that says NO names it, mean everyone
    (other than the owner's own keys)? Only an explicit anyone-word does
    ('the public or the press', 'nobody but my doctor', 'les gens'); 'Le
    Monde', 'Mr. Nobody', 'my GP' and 'Bob' each name only themselves."""
    raw = _plain_words(audience)
    if not raw.strip():
        return False
    if norm_audience(audience) == "anyone":
        return True
    for part in _PART_BREAK.split(raw):
        ws = [w for w in part.split() if w]
        while ws and (ws[0] in _DETERMINERS or ws[0].rstrip("'") in ("l", "d")):
            ws = ws[1:]
        if not ws:
            continue
        if ws[0] in _TITLES:
            continue                                  # Mr. Nobody, Mrs. World
        phrase = " ".join(ws)
        if phrase in _ANYONE_PHRASES or ws[0] in _ANYONE_HEADS:
            return True
        if len(ws) >= 2 and (ws[0], ws[1]) in {("no", "one"), ("any", "one"), ("every", "one")}:
            return True
        if ws[0] in _QUANTIFIERS and len(ws) >= 2 and ws[1] in _GENERIC_PERSON:
            return True
    return False


def norm_audience(s) -> str:
    """'My Sister' and 'sister' are one audience; 'the family' is 'family';
    'everyone', 'everybody', 'the public' and 'the world' are 'anyone'."""
    n = normalise(s).strip(" .,:;!\"'")
    if n in _ANYONE_ALL or _ANY_DETERMINER.sub("", n) in _ANYONE_ALL:
        return "anyone"
    n = _DETERMINER.sub("", n).strip(" .,:;!\"'")
    return "anyone" if n in _ANYONE_ALL else n


def _emails_in(text) -> set[str]:
    return {e.strip(".,;:()<>").lower() for e in _EMAIL.findall(str(text or ""))}


def rule_names(audience, people=()) -> frozenset:
    """Every way a rule that says NO to this audience reaches someone
    (verify I-24): the audience as written, each word of its name, and — when
    it names someone recorded in his life story — that person, their
    relationship to him, and the addresses noted for them. A no for 'Karen
    Czako' then meets 'Karen', 'Mrs. Czako', 'my ex-wife' and her address."""
    n = norm_audience(audience)
    if not n or n in (SELF, "anyone"):
        return frozenset({n} if n else ())
    out = {n} | {w for w in words(n) if len(w) >= 2 and w not in STOP and w not in _TITLES}
    nw = {w for w in words(n) if w not in _TITLES}
    for p in people or ():
        if not isinstance(p, dict):
            continue
        pn = norm_audience(p.get("name", ""))
        rel = norm_audience(p.get("relationship", ""))
        pw = {w for w in words(pn) if w not in _TITLES}
        if not pn:
            continue
        if n == pn or (nw and pw and (nw <= pw or pw <= nw)) or (rel and n == rel):
            out |= {pn} | ({rel} if rel else set())
            out |= _emails_in(p.get("notes", ""))
    out.discard("")
    out.discard(SELF)
    return frozenset(out)


_ADDRESSED = re.compile(r"^(.*?)<\s*([^<>\s]+@[^<>\s]+)\s*>\s*$")
_EMAIL = re.compile(r"[^\s@<>]+@[^\s@<>]+")


def audience_aliases(audience, people=()) -> tuple[frozenset, frozenset]:
    """Every name this audience may be known by to the owner's rules:
    (broad, strict). A rule that says NO is matched against `broad` — each
    word of a display name, an e-mail address's name part, and the person
    and relationship recorded in his life story ('Karen' → his ex-wife →
    family). A rule that says YES is matched against `strict` only — the
    whole name or address as written, or the recorded person it exactly is."""
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
        local = email.split("@", 1)[0]
        strict |= {email, local}
        broad |= {p for p in re.split(r"[._+\-0-9]+", local) if len(p) >= 2}
    if name:
        n = norm_audience(name)
        strict |= {name, n}
        broad |= {w for w in words(n) if w not in STOP and w not in _TITLES}
    for p in people or ():
        if not isinstance(p, dict):
            continue
        pn = norm_audience(p.get("name", ""))
        if not pn:
            continue
        pw = set(words(pn))
        rel = norm_audience(p.get("relationship", ""))
        noted = _emails_in(p.get("notes", ""))
        exact = pn in strict or bool(email and email.lower() in noted)
        # 'my ex-wife' is the person recorded as his ex-wife; 'kczako@…'
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
