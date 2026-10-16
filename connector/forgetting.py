"""
Forgetting — nothing irreversible happens because an AI asked
==============================================================

The October 2026 stress test found that one empty or short word in a
'forget' call could wipe a whole life: forget('') matched every fact,
forget_life('Ann') took Anna, Joanna, an anniversary and a legacy letter,
and the engine was told only a count. And what WAS forgotten was not gone:
the words stayed in the record of what was sent, in the safety copies and in
other sections, and a forgotten person came back as a question.

Every tool that removes or closes anything now goes through this module, and
it keeps five rules:

1. **No wildcards.** An empty, blank or very short match (fewer than three
   letters or digits) is refused. Words match whole words ('Ann' is not
   'Anna'); a person is matched by their exact name or id, never by part of
   a name; a picture is never matched by the folder it sits in.
2. **Two steps.** The first call removes nothing: it returns exactly what
   would go, with ids, and a one-time code. Only a second call with that
   code removes — exactly what was shown, and nothing that changed since.
3. **The owner's own hands for anything big.** More than three things, more
   than one kind of thing, or more than ten in a day is never removed
   because an AI asked: the code then works only at the owner's console
   ('Forget or bring back', or /approve in JEFFEREY's own terminal).
4. **Nothing is lost by mistake.** A copy of the memory file is pinned
   first; what went is kept in a dated removed list beside the memory file
   (not in the rotating copies) for three months, and the owner can put it
   back. Every removal is written in the action log — by id, never by its
   words.
5. **Erasing for good is the owner's alone.** `erase()` takes words out of
   everything: every section, the record of what was sent (each entry kept
   as a dated tombstone with its sha256 fingerprint), the safety copies and
   the removed list — and returns a receipt, including what the AI companies
   may still hold. A forgotten name goes on a list (as a fingerprint, not the
   name) so JEFFEREY never asks about that person again.

What is HIS — anything he stored or confirmed himself — is never forgotten
because an AI asked, whatever the count (S5, round 8): an AI's own code only
forgets its own notes that still wait for him.

Owner commands (his own terminal; no AI can run these). Each one that
changes something wants him at the keyboard (S6, round 8): stdin and stdout
terminals, the number shown on the screen typed back, --yes ignored. An
agent with a shell and a pseudo-terminal can still do what he can, until
Touch ID (I-43):
    python connector/forgetting.py                  the 'Forget or bring back' menu
    python connector/forgetting.py waiting          what an AI asked to remove
    python connector/forgetting.py approve <code>   remove it (it can still be put back)
    python connector/forgetting.py removed          what was removed, newest first
    python connector/forgetting.py bring-back <n>   put number n back
    python connector/forgetting.py erase "<words>"  erase these words everywhere, for good
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import secrets
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Callable

import conscience as _cs
from conscience import Conscience, StoreProblem

MIN_CHARS = 3            # letters or digits a match must have
AI_MAX_ITEMS = 3         # more than this, in one request, needs the owner
AI_DAILY_MAX = 10        # more than this in a day, because an AI asked, too
# Marking a goal done or an offer declined removes nothing (it can be undone
# from 'Forget or bring back'), so it is counted on its own, more generous
# daily line — routine triage of offers must not use up the removals' ten
# (verify: the 11th declined coupon of the day needed the owner, and he was
# told "10 things have already been removed" when nothing had been).
STATUS_TOOLS = frozenset({"close_goal", "resolve_opportunity"})
# Who the owner is on every form and letter: changing or removing one of
# these, because an AI asked, always waits for his own yes (verify I-30).
IDENTITY_KEYS = frozenset({"full_name", "first_name", "last_name", "date_of_birth"})
AI_DAILY_STATUS_MAX = 40
AI_CODE_MINUTES = 30     # how long a code an AI may use stays good
OWNER_CODE_DAYS = 7      # how long a request waits for the owner
TRASH_KEEP_DAYS = 90     # how long the removed list keeps a thing
SHOW_MAX = 25            # items listed in one answer

KINDS = {
    "facts": ("fact", "facts"),
    "goals": ("goal", "goals"),
    "opportunities": ("opportunity", "opportunities"),
    "observations": ("observation", "observations"),
    "priorities": ("priority", "priorities"),
    "corrections": ("correction", "corrections"),
    "conscience_included": ("thing let into the conscience",
                            "things let into the conscience"),
    "rules": ("rule", "rules"),
    "profile": ("profile detail", "profile details"),
    "people": ("person", "people"),
    "memories": ("moment", "moments"),
    "media": ("picture or recording", "pictures and recordings"),
    "actions": ("action-log entry", "action-log entries"),
    "_notices": ("notice", "notices"),
    "expected_charges": ("expected charge", "expected charges"),
    "charges_seen": ("charge seen", "charges seen"),
    "profile_notes": ("profile detail an AI noted", "profile details an AI noted"),
    "rule_proposals": ("rule an AI asked for", "rules an AI asked for"),
}

# S5 (round 8): what is HIS — anything he stored or confirmed himself, or
# kept before JEFFEREY recorded who said what — is never forgotten because
# an AI asked, whatever the count: the code then works only at his own
# keyboard. An AI's two-step code completes only the forgetting of its own
# notes that still wait for him. (Before, forget('resuscitated') gave
# needs_owner false, and the AI's own code removed his confirmed words.)
HIS_SECTIONS = frozenset({"facts", "memories", "media", "people", "rules", "goals",
                          "profile"})
HIS_OWN = ("it is his own — he stored or confirmed it himself — so only he can let it "
           "go")

# Which key may read each kind of thing: a preview never shows words to a
# key that could not read them anyway.
READ_SCOPE = {"facts": "facts.read", "rules": "facts.read", "profile": "facts.read",
              "profile_notes": "facts.read",
              "conscience_included": "facts.read", "goals": "goals.read",
              "opportunities": "goals.read", "observations": "goals.read",
              "priorities": "priorities.read", "corrections": "priorities.read",
              "people": "life.read", "memories": "life.read", "media": "life.read"}

LIFE = ("people", "memories", "media")
# Searched for "still mentioned" after a forget: what else names it.
MENTION_SECTIONS = ("facts", "rules", "profile", "goals", "opportunities",
                    "observations", "people", "memories", "media")
# Kept, with the words taken out: the audit trail says something happened.
AUDIT_SECTIONS = ("actions", "_notices")
# Security records erase does not rewrite; it says so on the receipt.
NOT_TOUCHED = ("owner", "_rev", "selfcloud_grants", "permissions", "asked",
               "forgotten_names")
# Never the owner's words.
_SKIP_KEYS = frozenset({"id", "added", "updated", "ts", "at", "closed",
                        "resolved_on"})

STILL_HELD = (
    "Gone from what JEFFEREY knows and tells any AI. Until it is erased for "
    "good, a copy stays in the removed list (so it can be put back), in older "
    "safety copies of the memory file, and in the record of what was sent "
    "('What left the house'). To erase it everywhere, the owner double-clicks "
    "'Forget or bring back' and chooses erase. Anything already sent to an AI "
    "company may still be held by that company.")

STATUS_HELD = (
    "Nothing was removed: it is only marked, and JEFFEREY still knows it. The "
    "owner can undo this himself from 'Forget or bring back'.")

ASK_FIRST = ("Read the owner the list of what would go, in plain words, and ask "
             "him. Never say anything was removed until a later result says it "
             "was.")


# ------------------------------------------------------------------- words
def _norm(s) -> str:
    s = unicodedata.normalize("NFKC", str(s))
    return s.replace("’", "'").replace("‘", "'").casefold()


_SPACELESS = re.compile("[\u0e00-\u0eff\u1000-\u109f\u1780-\u17ff\u3005\u3040-\u30ff"
                        "\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
                        "\U00020000-\U0002ffff]")


def _squash(s) -> str:
    return " ".join(_norm(s).split())


class Words:
    """A whole-word, case-blind phrase: 'Ann' finds "Ann" and "Ann's", never
    "Anna", "Joanna" or "anniversary"; 'mom' never finds "moments"."""

    def __init__(self, words: str):
        parts = _norm(words).split()
        self.text = " ".join(parts)
        # Chinese and Japanese are written without spaces, so a word there
        # has no "edge" to find: it is matched where it stands ('凯伦' in
        # '我和凯伦分居了'); everything else, as whole words.
        head = "" if parts and _SPACELESS.match(parts[0][:1]) else r"(?<!\w)"
        tail = "" if parts and _SPACELESS.match(parts[-1][-1:]) else r"(?!\w)"
        self.rx = re.compile(head + r"\s+".join(map(re.escape, parts)) + tail)

    def __call__(self, s) -> bool:
        return isinstance(s, str) and bool(self.rx.search(_norm(s)))


def too_vague(text) -> str | None:
    """Why this match is not safe to remove by, or None."""
    s = text.strip() if isinstance(text, str) else ""
    if not s:
        return ("Nothing was given to match, so nothing was removed. JEFFEREY "
                "never takes an empty match to mean everything.")
    # A Chinese or Japanese character says as much as a short word: two of
    # them are a word ('女儿', daughter).
    if sum(2 if _SPACELESS.match(ch) else 1 for ch in s if ch.isalnum()) < MIN_CHARS:
        return (f"'{s}' is too short to match safely — it would catch things "
                "nobody meant. Nothing was removed.")
    return None


def name_key(name: str) -> str:
    """A forgotten name is kept as this fingerprint, never as the name."""
    return hashlib.sha256(_squash(name).encode("utf-8")).hexdigest()


def forgotten(data: dict) -> set[str]:
    return {x.get("sha256") for x in data.get("forgotten_names") or []
            if isinstance(x, dict)}


def is_forgotten(data: dict, name: str) -> bool:
    return bool(name and name.strip()) and name_key(name) in forgotten(data)


def _add_forgotten(data: dict, keys) -> None:
    lst = data.get("forgotten_names")
    if not isinstance(lst, list):
        lst = data["forgotten_names"] = []
    have = forgotten(data)
    for k in keys:
        if k and k not in have:
            lst.append({"sha256": k, "on": _day(time.time())})
            have.add(k)


def unforget(data: dict, name: str) -> bool:
    """The owner said this name again on purpose: take it off the list."""
    k = name_key(name)
    lst = data.get("forgotten_names")
    if not isinstance(lst, list):
        return False
    keep = [x for x in lst if not (isinstance(x, dict) and x.get("sha256") == k)]
    if len(keep) == len(lst):
        return False
    data["forgotten_names"] = keep
    return True


# ------------------------------------------------------------------- items
def _day(ts: float) -> str:
    t = time.localtime(ts)
    return f"{t.tm_mday} {time.strftime('%B %Y', t)}"


def _kind(section: str, n: int = 1) -> str:
    one, many = KINDS.get(section, (section, section))
    return one if n == 1 else many


def _count_words(counts: dict) -> str:
    parts = [f"{n} {_kind(s, n)}" for s, n in counts.items() if n]
    if not parts:
        return "nothing"
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _strs(v) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str)]
    return []


def _leaves(obj, path=()):
    """Every string inside, with where it sits. Item bookkeeping (ids,
    timestamps) is never the owner's words."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if not path and k in _SKIP_KEYS:
                continue
            yield from _leaves(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _leaves(v, path + (i,))


def _set(obj, path, value) -> None:
    for p in path[:-1]:
        obj = obj[p]
    obj[path[-1]] = value


def _sha_item(item) -> str:
    return hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def _items(data: dict, section: str) -> list[dict]:
    if section == "profile":
        prof = data.get("profile")
        return ([{"field": k, "value": v} for k, v in prof.items()]
                if isinstance(prof, dict) else [])
    return [x for x in (data.get(section) or []) if isinstance(x, dict)]


def _id(section: str, item: dict):
    return item.get("field") if section == "profile" else item.get("id")


def _find(data: dict, section: str, id_) -> dict | None:
    if not isinstance(id_, str) or not id_:
        return None
    if section == "profile":
        prof = data.get("profile")
        if isinstance(prof, dict) and id_ in prof:
            return {"field": id_, "value": prof[id_]}
        return None
    for it in data.get(section) or []:
        if isinstance(it, dict) and it.get("id") == id_:
            return it
    return None


def _ids(ids) -> list[str]:
    if ids is None:
        return []
    if isinstance(ids, str):
        ids = re.split(r"[,\s]+", ids)
    return [str(i).strip() for i in ids if str(i).strip()]


def _what(section: str, item: dict) -> str:
    g = item.get
    if section == "facts":
        t = g("fact", "")
    elif section == "goals":
        t = g("goal", "")
    elif section == "opportunities":
        t = g("what", "")
    elif section == "observations":
        t = g("note", "")
    elif section == "conscience_included":
        t = g("ref", "")
    elif section == "rules":
        tags = ", ".join(_strs(g("tags")))
        t = g("instruction", "") + (f" (about {tags})" if tags else "")
    elif section in ("profile", "profile_notes"):
        t = f"{g('label') or g('field')}: {g('value')}"
    elif section == "people":
        t = g("name", "") + (f" ({g('relationship')})" if g("relationship") else "")
    elif section == "memories":
        t = g("text", "")
    elif section == "media":
        t = g("caption") or Path(str(g("path", ""))).name or "a picture"
    elif section == "priorities":
        t = f"{g('higher')} over {g('lower')} ({g('context')})"
    elif section == "corrections":
        t = f"chose {g('chosen')} over {g('suggested')} ({g('context')})"
    elif section == "actions":
        t = g("description", "")
    else:
        t = json.dumps(item, ensure_ascii=False, default=str)
    t = str(t)
    return t if len(t) <= 200 else t[:197] + "…"


def _client() -> str:
    try:
        import access
        return access.current_client()
    except Exception:
        return "unknown"


def _can_read(section: str) -> bool:
    scope = READ_SCOPE.get(section)
    try:
        import access
        g = access.GATE
        if g is None or scope is None:
            return True
        return bool(g.cloud.check_access(g.current_client(), scope, log=False)["allowed"])
    except Exception:
        return False


def _kept_from_reader(c, section: str, item: dict) -> str | None:
    """Why this connection may not read this item's words, or None. A
    preview of what would be forgotten is held to the same rules as every
    other read (verify I-11: forget(contains='night') showed a rented engine
    'Takes donepezil 10mg at night' word for word, while explain_basis held
    it back under his rule)."""
    if c is not None and section == "rules":
        # his rules are read only by a key that may read them (rules.read);
        # and the words of a rule that holds for whoever reads — or whose
        # words carry what another of his rules keeps from it — are never
        # handed to it (S1, round 8; G2, round 9: rules.words_held)
        try:
            import provenance
            import rules as _rules
            return ("his own words for a rule whose words are kept from this connection"
                    if _rules.words_held(item, provenance.reader(), c.data) else None)
        except Exception:
            return "private"
    if c is None or section in ("rules", "priorities", "corrections"):
        return None
    try:
        import provenance
        rd = provenance.reader()
        if not rd.get("audiences"):
            return None                  # the owner himself, at his keyboard
        text = _what(section, item)
        cat = str(item.get("category") or "")
        if section in ("facts", "memories", "people", "media") and item.get(
                "visibility", "engines" if section == "facts" else "private") not in (
                "engines", "family", "legacy") and not rd.get("caretaker"):
            return "private"
        if not c.reader_may_see(rd, text, cat):
            return "private, or kept from this connection by his own rules"
    except Exception:
        return "private"
    return None


def _row(section: str, item: dict, change: str | None = None, c=None) -> dict:
    r = {"id": _id(section, item), "kind": _kind(section)}
    why = _kept_from_reader(c, section, item) if _can_read(section) else None
    r["what"] = (("(not shown here: " + why + " — he sees its words himself in "
                  "'Forget or bring back')") if why else
                 _what(section, item) if _can_read(section)
                 else "(not shown: your key cannot read this)")
    if change:
        r["change"] = change
    return r


def _readable(c, section: str, item: dict) -> bool:
    """May whoever asks read this item's words (G2, round 9)? An engine's
    words match only what it may read — through what release would show it
    (_shown) — so no search over his life tells it what it may not see. The
    owner at his own keyboard reads everything."""
    if not _engine() or c is None:
        return True
    return _can_read(section) and _kept_from_reader(c, section, item) is None


def refusal(tool: str, reason: str, tell: str | None = None) -> dict:
    """A refusal is a RESULT the model must report, never a crash."""
    return {"refused": True, "tool": tool, "reason": reason, "tell_the_user": tell or (
        "Tell the owner plainly that nothing was removed, and why. Ask him "
        "exactly which thing he means — or use its id, which get_conscience, "
        "who_am_i and list_rules show.")}


# -------------------------------------------------------------------- plans
class Plan:
    """What a destructive request would do. Nothing in here has happened."""

    def __init__(self):
        self.changes: list[dict] = []
        self.also: list[tuple[str, dict]] = []
        self.unknown: list[str] = []
        self.names: list[str] = []        # people being forgotten, by name
        self._keys: set = set()

    def remove(self, section: str, item: dict) -> None:
        self._add(section, item, "remove", None, None)

    def update(self, section: str, item: dict, after: dict, change: str) -> None:
        self._add(section, item, "update", after, change)

    def _add(self, section, item, action, after, change) -> None:
        key = (section, _id(section, item))
        if key in self._keys:
            return
        self._keys.add(key)
        self.changes.append({"section": section, "id": key[1], "action": action,
                             "before": item, "after": after, "change": change})

    def removing(self, section: str, item: dict) -> bool:
        return any(c["section"] == section and c["id"] == _id(section, item)
                   and c["action"] == "remove" for c in self.changes)

    def mention(self, section: str, item: dict) -> None:
        if self.removing(section, item):
            return
        if any(s == section and _id(s, i) == _id(section, item) for s, i in self.also):
            return
        self.also.append((section, item))


def _plan(data: dict, section: str, contains, ids, fields, *,
          eligible: Callable | None = None,
          update: Callable | None = None, c=None) -> Plan | str:
    """By ids, or by an exact id given as the words, or by whole words in the
    item's own text fields — for an engine, only in what it may read, as
    release would show it (G2, round 9)."""
    plan = Plan()
    ids = _ids(ids)
    s = contains.strip() if isinstance(contains, str) else ""
    if not ids and s and _find(data, section, s) is not None:
        ids = [s]

    def add(it):
        if update is None:
            plan.remove(section, it)
        else:
            after, change = update(it)
            plan.update(section, it, after, change)

    if ids:
        for i in ids:
            it = _find(data, section, i)
            if it is None or (eligible and not eligible(it)):
                plan.unknown.append(i)
            else:
                add(it)
        return plan
    bad = too_vague(s)
    if bad:
        return bad
    w = Words(s)
    for it in _items(data, section):
        if eligible and not eligible(it):
            continue
        if not _readable(c, section, it):
            continue
        if any(w(_shown(x)) for f in fields for x in _strs(it.get(f))):
            add(it)
    return plan


def _shown(text: str) -> str:
    """What an engine's words may match (F3, round 8): only what would leave
    the house, never the part the door hides — forget(contains='Bluebird77')
    must not tell an engine that a note holds that password."""
    if not _engine() or not isinstance(text, str):
        return text
    import egress
    return egress.shown_text(text)


def _mentions(data: dict, plan: Plan, terms: list[str], c=None) -> None:
    """What else still names it, so the owner hears it — never removed here.
    For an engine, only what it may read, as release would show it (G2,
    round 9: forget_life('4821') named 'My bank PIN is [hidden…]' here, and
    forget_life('4822') nothing — a PIN confirmed)."""
    ws = [Words(t) for t in terms if t and not too_vague(t)]
    if not ws:
        return
    changed = {(ch["section"], ch["id"]): ch for ch in plan.changes}
    for sec in MENTION_SECTIONS:
        for it in _items(data, sec):
            ch = changed.get((sec, _id(sec, it)))
            if ch and ch["action"] == "remove":
                continue
            if not _readable(c, sec, it):
                continue
            look = ch["after"] if ch else it
            if any(w(_shown(s)) for w in ws for p, s in _leaves(look) if p[:1] != ("path",)):
                plan.mention(sec, it)


def plan_life(data: dict, contains, ids, c=None) -> Plan | str:
    """forget_life: a person by exact name or id (with the moments and
    pictures that are about them), or moments and pictures by id or by whole
    words in what was said about them. Never a person by part of a name, and
    never a picture by the folder it sits in. For an engine, only what it may
    read, as release would show it (G2, round 9)."""
    plan = Plan()
    ids = _ids(ids)
    s = contains.strip() if isinstance(contains, str) else ""
    if not ids and s and any(_find(data, sec, s) is not None for sec in LIFE):
        ids = [s]
    names: list[str] = []
    if ids:
        for i in ids:
            p = _find(data, "people", i)
            if p is not None:
                plan.remove("people", p)
                if p.get("name"):
                    names.append(p["name"])
                continue
            for sec in ("memories", "media"):
                it = _find(data, sec, i)
                if it is not None:
                    plan.remove(sec, it)
                    break
            else:
                plan.unknown.append(i)
    else:
        bad = too_vague(s)
        if bad:
            return bad
        key = _squash(s)
        persons = [p for p in _items(data, "people") if _squash(p.get("name", "")) == key
                   and _readable(c, "people", p)]
        listed = any(_squash(n) == key for sec in ("memories", "media")
                     for it in _items(data, sec) if _readable(c, sec, it)
                     for n in _strs(it.get("people")))
        if persons or listed:
            for p in persons:
                plan.remove("people", p)
            names.append(persons[0]["name"] if persons else s)
        else:
            w = Words(s)
            for sec, fields in (("memories", ("text", "when", "tags")),
                                ("media", ("caption", "when", "tags"))):
                for it in _items(data, sec):
                    if _readable(c, sec, it) and any(
                            w(_shown(x)) for f in fields for x in _strs(it.get(f))):
                        plan.remove(sec, it)
    for name in names:
        _cascade(data, plan, name, c)
    plan.names = names
    _mentions(data, plan, names + ([s] if s and not names else []), c)
    return plan


def _cascade(data: dict, plan: Plan, name: str, c=None) -> None:
    """A forgotten person's moments and pictures. One that is about them
    alone goes with them; one shared with other people stays, with their
    name taken off it — and if its words still name them, the owner is told.
    For an engine, only those it may read (G2, round 9): what it may not
    read stays, for him to forget himself."""
    key, w = _squash(name), Words(name)
    for sec, fields in (("memories", ("text", "tags")), ("media", ("caption", "tags"))):
        for it in _items(data, sec):
            if not _readable(c, sec, it):
                continue
            people = _strs(it.get("people"))
            in_people = any(_squash(n) == key for n in people)
            in_words = any(w(x) for f in fields for x in _strs(it.get(f)))
            if not (in_people or in_words):
                continue
            others = [n for n in people if _squash(n) != key]
            if not others:
                plan.remove(sec, it)
            elif in_people:
                after = {**it, "people": others}
                plan.update(sec, it, after, f"{name}'s name taken off; the "
                                            f"{_kind(sec)} itself stays")


# ------------------------------------------------------------ pending codes
_ALPHABET = "ACDEFGHJKMNPQRTUVWXY34679"     # nothing that reads as another


def _clean_code(s) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


class _Pending:
    """Requests that have been shown but not carried out, beside the memory
    file (several surfaces and the owner's console share them). They hold
    ids and fingerprints, not the owner's words."""

    def __init__(self, c: Conscience):
        self.path = c.path.with_name(c.path.stem + ".pending.json")

    def _lock(self):
        return _cs._FileLock(self.path.with_name(self.path.name + ".lock"))

    def _load(self) -> dict:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(d, dict):
            return {}
        now = time.time()
        return {k: v for k, v in d.items()
                if isinstance(v, dict) and float(v.get("expires_ts", 0)) > now}

    def _store(self, d: dict) -> None:
        try:
            if not d:
                try:
                    self.path.unlink()
                except FileNotFoundError:
                    pass
                return
            _cs._make_dir(self.path.parent)
            _cs._write_atomic(self.path, json.dumps(d, indent=1, ensure_ascii=False)
                              .encode("utf-8"))
        except OSError as exc:
            raise _cs.ConscienceSaveFailed(
                "JEFFEREY could not write down this request (the drive may be full "
                "or read-only), so nothing was removed.", self.path) from exc

    def add(self, entry: dict) -> str:
        with self._lock():
            d = self._load()
            code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
            while code in d:
                code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
            entry["code"] = code
            d[code] = entry
            self._store(d)
        return code

    def get(self, code: str) -> dict | None:
        with self._lock():
            return self._load().get(_clean_code(code))

    def take(self, code: str) -> dict | None:
        """One use: the request is gone from the list as it is taken."""
        with self._lock():
            d = self._load()
            e = d.pop(_clean_code(code), None)
            if e is not None:
                self._store(d)
            return e

    def put_back(self, entry: dict) -> None:
        with self._lock():
            d = self._load()
            d[entry["code"]] = entry
            self._store(d)

    def all(self) -> list[dict]:
        with self._lock():
            return sorted(self._load().values(), key=lambda e: e.get("ts", 0))

    def drop_matching(self, match: Callable) -> int:
        with self._lock():
            d = self._load()
            keep = {k: v for k, v in d.items()
                    if not any(match(s) for _, s in _leaves(v.get("changes")))}
            if len(keep) != len(d):
                self._store(keep)
            return len(d) - len(keep)


# ------------------------------------------------------------- removed list
class _Trash:
    """What was removed, dated, one file each, beside the memory file and
    outside the rotating copies. Kept TRASH_KEEP_DAYS, then let go."""

    def __init__(self, c: Conscience):
        self.dir = c.path.parent / (c.path.stem + ".trash")

    def put(self, entry: dict) -> Path:
        _cs._make_dir(self.dir)
        base = f"{_cs._utc_stamp()}-{entry['code']}"
        p = self.dir / f"{base}.json"
        n = 1
        while p.exists():
            n += 1
            p = self.dir / f"{base}-{n}.json"
        _cs._write_atomic(p, json.dumps(entry, indent=1, ensure_ascii=False)
                          .encode("utf-8"))
        self.prune()
        return p

    def _files(self) -> list[Path]:
        try:
            return sorted((p for p in self.dir.glob("*.json") if p.is_file()),
                          reverse=True)
        except OSError:
            return []

    def prune(self) -> None:
        now = time.time()
        for p, e in self._read_all():
            if float(e.get("keep_until_ts", 0)) < now:
                try:
                    p.unlink()
                except OSError:
                    pass

    def _read_all(self) -> list[tuple[Path, dict]]:
        out = []
        for p in self._files():
            try:
                e = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(e, dict) and isinstance(e.get("changes"), list):
                out.append((p, e))
        # Newest first by the moment it happened (two in one second must not
        # be ordered by their codes).
        out.sort(key=lambda pe: (float(pe[1].get("ts", 0) or 0), pe[0].name), reverse=True)
        return out

    def entries(self) -> list[tuple[Path, dict]]:
        """Newest first, only what is still kept."""
        now = time.time()
        return [(p, e) for p, e in self._read_all()
                if float(e.get("keep_until_ts", 0)) >= now]

    def removed_by_ai_since(self, since: float, status: bool = False) -> int:
        """How many things an AI's requests took away (or, with status=True,
        only marked done or declined) since then."""
        return sum(len(e["changes"]) for _, e in self._read_all()
                   if e.get("by") == "ai" and float(e.get("ts", 0)) >= since
                   and (e.get("tool") in STATUS_TOOLS) == status)


# ---------------------------------------------------------- the two steps
def _legacy(tool: str, changes: list[dict], done: bool) -> dict:
    """The counts each tool always returned, so nothing that read them breaks
    (0 until something is actually done)."""
    def n(section=None, action=None):
        return sum(1 for c in changes if done
                   and (section is None or c["section"] == section)
                   and (action is None or c["action"] == action))
    if tool == "forget":
        return {"removed_facts": n()}
    if tool == "close_goal":
        return {"closed": n()}
    if tool == "resolve_opportunity":
        return {"resolved": n()}
    if tool == "conscience_exclude":
        return {"excluded": n()}
    if tool == "remove_rule":
        return {"removed": n()}
    if tool == "forget_profile_field":
        if not (done and changes):
            return {"removed": None}
        ch = changes[0]
        # an AI's note for a detail is named by the detail it is for (S2)
        return {"removed": (ch.get("before") or {}).get("field")
                if ch["section"] == "profile_notes" else ch["id"]}
    if tool == "forget_life":
        return {"memories_removed": n("memories", "remove"),
                "media_removed": n("media", "remove"),
                "people_removed": n("people", "remove"),
                "names_taken_off": n(action="update")}
    return {}


def run(c: Conscience, tool: str, make_plan: Callable[[], Plan | str],
        confirm: str = "", searched: bool = False) -> dict:
    """The one way a destructive tool runs: a code carries out what was
    shown; anything else only shows. `searched`: the request names what to
    forget by words, not ids — a search (G2, round 9): a key paused for
    searching that finds nothing is refused, and one that finds nothing is
    counted."""
    if isinstance(confirm, str) and confirm.strip():
        return confirm_code(c, tool, confirm)
    if searched:
        paused = c.search_paused(tool)
        if paused:
            return paused
    plan = make_plan()
    if isinstance(plan, str):
        return refusal(tool, plan)
    if searched:
        c.search_found(bool(plan.changes))
    return ask(c, tool, plan)


def _by_words(contains, ids) -> bool:
    return bool(isinstance(contains, str) and contains.strip()) and not _ids(ids)


def _engine() -> bool:
    """An engine key is asking (not the owner's own hands, nor his own tools)."""
    try:
        import access
        return not access.owners_hands()
    except Exception:
        return True


def _his(section: str, item) -> bool:
    """Is this his own (S5)? Everything in his profile is (an AI's value waits
    beside it, in profile_notes); elsewhere, anything that is not an AI's
    note still waiting for him."""
    if section not in HIS_SECTIONS or not isinstance(item, dict):
        return False
    if section == "profile":
        return True
    import provenance
    return provenance.his(item)


def ask(c: Conscience, tool: str, plan: Plan) -> dict:
    """Step one: exactly what would go, and a one-time code. Nothing changes."""
    also = [_row(s, i, c=c) for s, i in plan.also[:SHOW_MAX]]
    if not plan.changes:
        res = {"step": "nothing", "count": 0,
               "note": "Nothing matched, so nothing was removed. Words match whole "
                       "words, and a person only by their exact name.",
               **_legacy(tool, [], False)}
        if plan.unknown:
            res["unknown_ids"] = plan.unknown
        if also:
            res["also_mentioned"] = also
        return res
    count = len(plan.changes)
    sections = list(dict.fromkeys(ch["section"] for ch in plan.changes))
    why = None
    if tool == "set_profile_field" or any(
            ch["section"] == "profile" and ch["id"] in IDENTITY_KEYS for ch in plan.changes):
        why = "it changes who he is on every form and letter"
    elif _engine() and any(_his(ch["section"], ch["before"]) for ch in plan.changes):
        why = HIS_OWN
    elif count > AI_MAX_ITEMS:
        why = f"it is {count} things"
    elif len(sections) > 1:
        why = "it is more than one kind of thing"
    else:
        why = _over_the_day(c, tool, count)
    now = time.time()
    entry = {
        "tool": tool, "client": _client(), "ts": now, "at": _cs._now(),
        "needs_owner": bool(why), "why_owner": why,
        "expires_ts": now + (OWNER_CODE_DAYS * 86400 if why else AI_CODE_MINUTES * 60),
        "changes": [{"section": ch["section"], "id": ch["id"], "action": ch["action"],
                     "sha": _sha_item(ch["before"]), "after": ch["after"],
                     "change": ch["change"]} for ch in plan.changes],
        "also": [[s, _id(s, i)] for s, i in plan.also[:SHOW_MAX]],
        "names": [name_key(n) for n in plan.names],
    }
    code = _Pending(c).add(entry)
    counts = Counter(ch["section"] for ch in plan.changes)
    res = {
        "step": "preview",
        "would_remove": [_row(ch["section"], ch["before"], c=c) for ch in plan.changes
                         if ch["action"] == "remove"][:SHOW_MAX],
        "would_change": [_row(ch["section"], ch["before"], ch["change"], c=c)
                         for ch in plan.changes if ch["action"] == "update"][:SHOW_MAX],
        "count": count, "kinds": _count_words(counts),
        "confirm": code, "needs_owner": bool(why),
        **_legacy(tool, plan.changes, False),
    }
    if why:
        res["expires"] = f"it waits for the owner until {_day(entry['expires_ts'])}"
        res["how_to_finish"] = (
            f"Nothing has been removed. This is {res['kinds']} — {why}, so it is "
            f"never removed because an AI asked. Read the list to the owner. If he "
            f"wants it, he does it himself: he double-clicks 'Forget or bring back' "
            f"on his Mac and types the code {code} (in JEFFEREY's own terminal: "
            f"/approve {code}). Do not call {tool} with this code; it will not work "
            f"for you.")
    else:
        res["expires"] = f"the code works once, for {AI_CODE_MINUTES} minutes"
        res["how_to_finish"] = (
            f"Nothing has been removed. Read the list to the owner. Only if he says "
            f"yes to exactly this, call {tool} again with confirm='{code}'. If he "
            f"wants only some of it, ask again with ids=[...] instead.")
    if also:
        res["also_mentioned"] = also
        res["note"] = ("Other things still mention it (also_mentioned). They are "
                       "not on this list; tell the owner, so he can decide.")
    if plan.unknown:
        res["unknown_ids"] = plan.unknown
    res["tell_the_user"] = ASK_FIRST
    return res


def _waiting_for_ai(c: Conscience, status: bool, but: str | None = None) -> int:
    """Things in requests an AI may still confirm itself, today."""
    now = time.time()
    return sum(len(e.get("changes") or []) for e in _Pending(c).all()
               if not e.get("needs_owner") and e.get("code") != but
               and float(e.get("expires_ts", 0)) > now
               and (e.get("tool") in STATUS_TOOLS) == status)


def _over_the_day(c: Conscience, tool: str, count: int, but: str | None = None,
                  waiting: bool = True) -> str | None:
    """Why this many more would be too many for one day because an AI asked —
    counting what was done today AND what is waiting to be confirmed, so ten
    small requests cannot add up to a whole life (verify I-01: the daily
    limit was looked at only when the list was shown, never when the code
    was used) — or None."""
    status = tool in STATUS_TOOLS
    limit = AI_DAILY_STATUS_MAX if status else AI_DAILY_MAX
    done = _Trash(c).removed_by_ai_since(time.time() - 86400, status=status)
    pend = _waiting_for_ai(c, status, but) if waiting else 0
    if done + pend + count <= limit:
        return None
    if status:
        return (f"{done + pend} goals or offers have already been marked done or "
                f"declined today because an AI asked (or are waiting to be), and more "
                f"than {limit} in a day is his own decision")
    return (f"{done + pend} things have already been removed today because an AI "
            f"asked (or are waiting to be), and more than {limit} in a day is his "
            f"own decision")


def confirm_code(c: Conscience, tool: str, code: str) -> dict:
    """Step two, from an AI: only a small request it was shown, by the same
    key, on the same tool — never one that needs the owner."""
    e = _Pending(c).get(code)
    if e is None:
        return refusal(tool, "That code is not waiting any more — it was already "
                             "used, it expired, or it was never given. Nothing was "
                             "removed.",
                       "Tell the owner nothing was removed. If he still wants it, "
                       "ask again: a fresh list comes with a fresh code.")
    if e.get("tool") != tool:
        return refusal(tool, f"That code belongs to a different request "
                             f"({e.get('tool')}). Nothing was removed.")
    if e.get("client") != _client():
        return refusal(tool, "That code was given to a different key. Nothing was "
                             "removed.")
    if not e.get("needs_owner"):
        # What became his since the list was shown (he confirmed it) is his
        # now (S5); and the day's limit again, now: what was done since the
        # list was shown counts (verify I-01). Either way the same code then
        # waits for the owner.
        mine = _engine() and any(_his(ch["section"], _find(c.data, ch["section"], ch["id"]))
                                 for ch in e.get("changes") or [])
        why = HIS_OWN if mine else _over_the_day(c, tool, len(e.get("changes") or []),
                                                 but=e["code"], waiting=False)
        if why:
            pend = _Pending(c)
            taken = pend.take(e["code"])
            if taken is not None:
                taken.update(needs_owner=True, why_owner=why,
                             expires_ts=time.time() + OWNER_CODE_DAYS * 86400)
                pend.put_back(taken)
                e = taken
    if e.get("needs_owner"):
        code = e["code"]
        return refusal(tool, f"This needs the owner's own OK, because "
                             f"{e.get('why_owner')}. Nothing was removed.",
                       f"Tell the owner: if he wants it, he double-clicks 'Forget or "
                       f"bring back' on his Mac and types {code} (in JEFFEREY's own "
                       f"terminal: /approve {code}). Do not try again yourself.")
    r = _execute(c, e["code"], by_owner=False)
    return r if r is not None else refusal(
        tool, "That code is not waiting any more. Nothing was removed.")


def approve(c: Conscience, code: str) -> dict:
    """OWNER ONLY — his console, never a tool. Carries out a request that is
    waiting, big or small."""
    r = _execute(c, code, by_owner=True)
    if r is None:
        return refusal("approve", "There is no request waiting with that code (it "
                                  "may have been done already, or it expired). "
                                  "Nothing was removed.")
    return r


def _execute(c: Conscience, code: str, *, by_owner: bool) -> dict | None:
    pend = _Pending(c)
    entry = pend.take(code)
    if entry is None:
        return None
    try:
        return _carry_out(c, entry, by_owner)
    except BaseException:
        try:
            pend.put_back(entry)      # nothing was removed: the code still works
        except StoreProblem:
            pass
        raise


def _carry_out(c: Conscience, entry: dict, by_owner: bool) -> dict:
    tool = entry["tool"]
    c.refresh()
    changes, gone = [], 0
    for ch in entry["changes"]:
        cur = _find(c.data, ch["section"], ch["id"])
        if cur is None and ch["section"] == "profile" and ch["action"] == "update":
            cur = {"field": ch["id"], "value": ""}      # a detail not set yet
        if cur is None:
            gone += 1
            continue
        if _sha_item(cur) != ch["sha"]:
            return refusal(tool, "Something on that list changed after it was shown, "
                                 "so nothing was removed. Ask again for a fresh list.")
        changes.append({**ch, "before": copy.deepcopy(cur)})
    if not changes:
        return {"step": "nothing", "count": 0,
                "note": "Everything on that list had already gone. Nothing else "
                        "was removed.", **_legacy(tool, [], False)}

    # A copy pinned first, so even this can be undone from 'Restore my
    # memories'. If it cannot be kept, nothing is removed.
    c.pin_snapshot(f"before {tool}")
    now = time.time()
    keep_until = now + TRASH_KEEP_DAYS * 86400
    trash_entry = {
        "code": entry["code"], "at": _cs._now(), "ts": now, "tool": tool,
        "asked_by": entry.get("client"), "by": "owner" if by_owner else "ai",
        "changes": [{k: ch[k] for k in ("section", "id", "action", "change", "before")}
                    for ch in changes],
        "names": entry.get("names", []), "keep_until_ts": keep_until,
    }
    try:
        tpath = _Trash(c).put(trash_entry)
    except OSError as exc:
        raise _cs.ConscienceSaveFailed(
            "JEFFEREY could not keep a copy of what would be removed (the drive "
            "may be full or read-only), so nothing was removed.", c.path) from exc

    counts = Counter(ch["section"] for ch in changes if ch["action"] == "remove")
    updates = Counter(ch["section"] for ch in changes if ch["action"] == "update")
    ids = [str(ch["id"]) for ch in changes]
    what = []
    if counts:
        what.append("removed " + _count_words(counts))
    if updates:
        verb = {"close_goal": "marked done", "resolve_opportunity": "marked resolved",
                "forget_life": "took a name off",
                "set_profile_field": "changed"}.get(tool, "changed")
        what.append(f"{verb} " + _count_words(updates))
    who = ("approved by the owner at his own console" if by_owner
           else "confirmed by the AI after it showed him the list")
    try:
        _apply(c.data, changes)
        if entry.get("names"):
            _add_forgotten(c.data, entry["names"])
        _log(c.data, f"{' and '.join(what)} (ids {', '.join(ids[:12])}"
                     f"{'…' if len(ids) > 12 else ''}). Asked for through '{tool}' by "
                     f"'{entry.get('client')}'; {who}.",
             f"kept in the removed list until {_day(keep_until)}; the owner can put "
             f"it back with 'Forget or bring back'")
        c._save()
    except BaseException:
        c._rollback()
        try:
            tpath.unlink()
        except OSError:
            pass
        raise

    status_only = tool in STATUS_TOOLS and not counts
    also = []
    for sec, i in entry.get("also") or []:
        it = _find(c.data, sec, i)
        if it is not None:
            also.append(_row(sec, it, c=c))
    res = {
        "step": "done", "count": len(changes),
        "removed_items": [_row(ch["section"], ch["before"], c=c) for ch in changes
                          if ch["action"] == "remove"][:SHOW_MAX],
        "changed_items": [_row(ch["section"], ch["before"], ch["change"], c=c)
                          for ch in changes if ch["action"] == "update"][:SHOW_MAX],
        "kept_until": _day(keep_until),
        "put_back": (f"Until {_day(keep_until)} the owner can put this back himself: "
                     "double-click 'Forget or bring back' (in JEFFEREY's own "
                     "terminal: /removed)."),
        "still_held": STATUS_HELD if status_only else STILL_HELD,
        "tell_the_user": (f"Tell the owner exactly what changed, from this list, and "
                          f"that he can undo it until {_day(keep_until)}." if status_only
                          else f"Tell the owner exactly what went, from this list, and "
                          f"that he can put it back until {_day(keep_until)}. Do not "
                          f"say it is gone everywhere — see still_held."),
        **_legacy(tool, changes, True),
    }
    if also:
        res["also_mentioned"] = also
    if gone:
        res["note"] = f"{gone} thing(s) on the list had already gone."
    return res


def remove_now(c: Conscience, section: str, items: list[dict], tool: str,
               asked_by: str) -> None:
    """The owner's own yes, given at his keyboard to something an AI asked
    for (S1: taking one of his rules away): done now, as an approved removal
    is — a copy pinned first, the removed list (he can put it back), the
    action log by id — with no code. Changes memory; the caller saves."""
    changes = [{"section": section, "id": _id(section, it), "action": "remove",
                "change": None, "after": None, "before": copy.deepcopy(it)} for it in items]
    if not changes:
        return
    c.pin_snapshot(f"before {tool}")
    now = time.time()
    keep_until = now + TRASH_KEEP_DAYS * 86400
    code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
    _Trash(c).put({"code": code, "at": _cs._now(), "ts": now, "tool": tool,
                   "asked_by": asked_by, "by": "owner",
                   "changes": [{k: ch[k] for k in ("section", "id", "action", "change",
                                                   "before")} for ch in changes],
                   "names": [], "keep_until_ts": keep_until})
    _apply(c.data, changes)
    ids = [str(ch["id"]) for ch in changes]
    _log(c.data, f"removed {_count_words(Counter(ch['section'] for ch in changes))} (ids "
                 f"{', '.join(ids[:12])}). Asked for through '{tool}' by '{asked_by}'; "
                 f"confirmed by the owner at his own keyboard.",
         f"kept in the removed list until {_day(keep_until)}; the owner can put it back "
         f"with 'Forget or bring back'")


def _apply(data: dict, changes: list[dict]) -> None:
    for ch in changes:
        sec = ch["section"]
        if sec == "profile":
            prof = data.get("profile")
            if not isinstance(prof, dict):
                prof = data["profile"] = {}
            if ch["action"] == "remove":
                prof.pop(ch["id"], None)
            elif isinstance(ch.get("after"), dict):
                prof[ch["id"]] = ch["after"].get("value", "")
            continue
        lst = data.get(sec) or []
        for i, it in enumerate(lst):
            if isinstance(it, dict) and it.get("id") == ch["id"]:
                if ch["action"] == "remove":
                    del lst[i]
                else:
                    lst[i] = copy.deepcopy(ch["after"])
                break


def _unapply(data: dict, changes: list[dict]) -> None:
    for ch in changes:
        sec, before = ch["section"], ch["before"]
        if sec == "profile":
            prof = data.get("profile")
            if not isinstance(prof, dict):
                prof = data["profile"] = {}
            prof[before["field"]] = before["value"]
            continue
        lst = data.get(sec)
        if not isinstance(lst, list):
            lst = data[sec] = []
        for i, it in enumerate(lst):
            if isinstance(it, dict) and it.get("id") == ch["id"]:
                lst[i] = copy.deepcopy(before)
                break
        else:
            lst.append(copy.deepcopy(before))


def _log(data: dict, description: str, outcome: str) -> None:
    """Into the action log, by id and count — never by the words removed."""
    acts = data.get("actions")
    if not isinstance(acts, list):
        acts = data["actions"] = []
    by, where = _cs._who()          # who and through which door (I-45)
    acts.append({"category": "memory", "description": description, "amount": None,
                 "outcome": outcome, "added": _cs._now(), "ts": time.time(),
                 "by": by, "surface": where, "source": "jefferey"})


# ------------------------------------------------------------ the tools
def forget_facts(c: Conscience, contains: str = "", ids=None, confirm: str = "") -> dict:
    return run(c, "forget", lambda: _plan(c.data, "facts", contains, ids, ("fact",), c=c),
               confirm, searched=_by_words(contains, ids))


def close_goals(c: Conscience, contains: str = "", ids=None, confirm: str = "") -> dict:
    def done(g):
        return {**g, "active": False, "closed": _cs._now()}, "marked done"
    return run(c, "close_goal", lambda: _plan(
        c.data, "goals", contains, ids, ("goal",),
        eligible=lambda g: g.get("active"), update=done, c=c), confirm,
        searched=_by_words(contains, ids))


def resolve_opportunities(c: Conscience, contains: str = "", outcome: str = "done",
                          ids=None, confirm: str = "") -> dict:
    outcome = (outcome or "done").strip() or "done"

    def done(o):
        return ({**o, "resolved": True, "outcome": outcome, "resolved_on": _cs._now()},
                f"marked {outcome}")
    return run(c, "resolve_opportunity", lambda: _plan(
        c.data, "opportunities", contains, ids, ("what",),
        eligible=lambda o: not o.get("resolved"), update=done, c=c), confirm,
        searched=_by_words(contains, ids))


def exclude(c: Conscience, contains: str = "", ids=None, confirm: str = "") -> dict:
    return run(c, "conscience_exclude", lambda: _plan(
        c.data, "conscience_included", contains, ids, ("ref", "note"), c=c), confirm,
        searched=_by_words(contains, ids))


def plan_rules(c: Conscience, rule_id_or_text: str = "", readable=None) -> Plan | str:
    """Which rules a remove_rule would take: by id, or by whole words of the
    rule, an exact tag or its audience. `readable(rule)`: may whoever asks
    read this rule's words? If not, its words are never matched — only its
    id, its tags and its audience (round 8 repair, S1: a match on words the
    engine may not read told it what they were)."""
    s = rule_id_or_text.strip() if isinstance(rule_id_or_text, str) else ""
    plan = Plan()
    exact = [r for r in _items(c.data, "rules") if s and str(r.get("id", "")).casefold() == s.casefold()]
    if exact:
        for r in exact:
            plan.remove("rules", r)
        return plan
    bad = too_vague(s)
    if bad:
        return bad
    w, key = Words(s), _squash(s)
    for r in _items(c.data, "rules"):
        words = w(r.get("instruction")) if readable is None or readable(r) else False
        if (words or any(_squash(t) == key for t in _strs(r.get("tags")))
                or _squash(r.get("audience", "")) == key):
            plan.remove("rules", r)
    return plan


def remove_rules(c: Conscience, rule_id_or_text: str = "", confirm: str = "") -> dict:
    """The owner's own two steps. From an engine, a removal is a proposal
    instead (rules.remove_rule, S1)."""
    return run(c, "remove_rule", lambda: plan_rules(c, rule_id_or_text), confirm)


def forget_profile(c: Conscience, field: str, key: str, confirm: str = "") -> dict:
    def make():
        bad = too_vague(field)
        if bad:
            return bad
        plan = Plan()
        it = _find(c.data, "profile", key)
        if it is not None:
            plan.remove("profile", it)
        else:
            # only what an AI noted for this detail, waiting beside his (S2)
            for n in _items(c.data, "profile_notes"):
                if n.get("field") == key:
                    plan.remove("profile_notes", n)
        return plan
    return run(c, "forget_profile_field", make, confirm)


def forget_life(c: Conscience, contains: str = "", ids=None, confirm: str = "") -> dict:
    return run(c, "forget_life", lambda: plan_life(c.data, contains, ids, c), confirm,
               searched=_by_words(contains, ids))


# --------------------------------------------------------- the owner's view
def waiting(c: Conscience) -> list[dict]:
    """What an AI asked to remove, waiting — oldest first, numbered."""
    out = []
    for n, e in enumerate(_Pending(c).all(), 1):
        items = []
        for ch in e.get("changes", []):
            it = _find(c.data, ch["section"], ch["id"])
            if it is not None:
                items.append((ch["section"], _what(ch["section"], it), ch.get("change")))
        out.append({"number": n, "code": e["code"], "tool": e.get("tool"),
                    "asked_by": e.get("client"), "when": _cs._when(float(e.get("ts", 0))),
                    "needs_owner": bool(e.get("needs_owner")),
                    "until": _day(float(e.get("expires_ts", 0))), "items": items})
    return out


def removed(c: Conscience) -> list[dict]:
    """What was removed and can be put back, newest first, numbered."""
    out = []
    for n, (p, e) in enumerate(_Trash(c).entries(), 1):
        items = [(ch["section"], _what(ch["section"], ch["before"]), ch.get("change"))
                 for ch in e["changes"]]
        out.append({"number": n, "file": p.name, "code": e.get("code"),
                    "tool": e.get("tool"), "when": _cs._when(float(e.get("ts", 0))),
                    "by": e.get("by"), "asked_by": e.get("asked_by"),
                    "until": _day(float(e.get("keep_until_ts", 0))), "items": items})
    return out


def bring_back(c: Conscience, which) -> dict:
    """OWNER ONLY — put a removed thing back (its number in removed(), its
    code, or its file name)."""
    entries = _Trash(c).entries()
    s = str(which).strip()
    pick = None
    if s.isdigit() and 1 <= int(s) <= len(entries):
        pick = entries[int(s) - 1]
    else:
        for p, e in entries:
            if s and (s == p.name or _clean_code(s) == e.get("code")):
                pick = (p, e)
                break
    if pick is None:
        return refusal("bring_back", f"There is nothing numbered '{s}' in the removed "
                                     "list. Look at the list and choose one of its "
                                     "numbers.")
    p, e = pick
    c.refresh()
    _unapply(c.data, e["changes"])
    for k in e.get("names") or []:
        lst = c.data.get("forgotten_names")
        if isinstance(lst, list):
            c.data["forgotten_names"] = [x for x in lst if not (
                isinstance(x, dict) and x.get("sha256") == k)]
    counts = Counter(ch["section"] for ch in e["changes"])
    ids = [str(ch["id"]) for ch in e["changes"]]
    try:
        _log(c.data, f"put back {_count_words(counts)} by the owner at his own console "
                     f"(ids {', '.join(ids[:12])}{'…' if len(ids) > 12 else ''}).",
             "put back")
        c._save()
    except BaseException:
        c._rollback()
        raise
    try:
        p.unlink()
    except OSError:
        pass
    return {"put_back": len(e["changes"]), "what": _count_words(counts),
            "items": [_what(ch["section"], ch["before"]) for ch in e["changes"]]}


# ----------------------------------------------------------------- erasure
def _erase_data(data: dict, w: Callable, stamp: str) -> dict:
    """Take the words out of one store (the live one, a safety copy). A thing
    that says them goes. The action log and notices keep their entries with
    the words replaced, so the record that something happened stays. A
    moment or picture whose only mention is a name among other people stays,
    with that name taken off. Security records are reported, not rewritten.
    Mutates `data`; returns what it did."""
    out = {"removed": Counter(), "unnamed": 0, "redacted": 0, "untouched": []}
    for sec in list(data):
        val = data[sec]
        if sec in NOT_TOUCHED:
            if any(w(s) for _, s in _leaves(val)):
                out["untouched"].append(sec)
            continue
        if sec == "profile" and isinstance(val, dict):
            for k in [k for k, v in val.items()
                      if w(k) or any(w(s) for _, s in _leaves(v))]:
                del val[k]
                out["removed"]["profile"] += 1
            continue
        if isinstance(val, list):
            keep = []
            for it in val:
                if isinstance(it, str):
                    if w(it):
                        out["removed"][sec] += 1
                    else:
                        keep.append(it)
                    continue
                if not isinstance(it, dict):
                    keep.append(it)
                    continue
                hits = [p for p, s in _leaves(it) if w(s)]
                if not hits:
                    keep.append(it)
                    continue
                if sec in AUDIT_SECTIONS:
                    it = copy.deepcopy(it)
                    for p in hits:
                        _set(it, p, f"[erased on {stamp}]")
                    keep.append(it)
                    out["redacted"] += 1
                    continue
                if (sec in ("memories", "media")
                        and all(len(p) == 2 and p[0] in ("people", "tags") for p in hits)):
                    others = [n for n in _strs(it.get("people")) if not w(n)]
                    if others:
                        it = {**it, "people": others}
                        if isinstance(it.get("tags"), list):
                            it["tags"] = [t for t in it["tags"] if not w(t)]
                        keep.append(it)
                        out["unnamed"] += 1
                        continue
                out["removed"][sec] += 1
            data[sec] = keep
        elif isinstance(val, dict):
            if any(w(s) for _, s in _leaves(val)):
                out["untouched"].append(sec)
    return out


def _names_hit(data: dict, w: Callable, words: str) -> list[str]:
    """Fingerprints of every person's name the words reach."""
    names = {p.get("name", "") for p in _items(data, "people")}
    names |= {n for sec in ("memories", "media") for it in _items(data, sec)
              for n in _strs(it.get("people"))}
    hit = [n for n in names if n and w(n)]
    keys = [name_key(n) for n in hit]
    if hit:
        keys.append(name_key(words))
    return list(dict.fromkeys(keys))


def _copy_files(c: Conscience) -> list[Path]:
    """Every copy of the memory file JEFFEREY keeps: the safety copies, the
    pinned ones, damaged files set aside, an unfinished hand edit."""
    files = list(c._history_files()) + list(c._damaged_copies())
    try:
        files += [p for p in c.path.parent.glob(".memories-edit-*.json") if p.is_file()]
    except OSError:
        pass
    return files


def _other_lives(c: Conscience) -> list[Conscience]:
    """The memory files that are not the one in use — the Mac's own, left
    from before the drive, or another of his drives — opened only to be
    rewritten, never to be read into this process."""
    try:
        import home
        found = home.conscience_files()
    except Exception:
        return []
    try:
        mine = c.path.resolve()
    except OSError:
        mine = c.path
    out = []
    for p in found:
        try:
            if p.resolve() == mine or not p.is_file():
                continue
        except OSError:
            continue
        o = Conscience.__new__(Conscience)
        o._init_fields(p)
        out.append(o)
    return out


def _temps_holding(c: Conscience, w: Callable) -> list[Path]:
    out = []
    for p in c._temp_files():
        try:
            if w(p.read_bytes().decode("utf-8", "replace")):
                out.append(p)
        except OSError:
            continue
    return out


def erase(c: Conscience, words: str, *, dry_run: bool = False) -> dict:
    """OWNER ONLY — his console, never a tool an AI can call: this cannot be
    undone, and nothing irreversible happens because an AI asked.

    Takes `words` (whole words, any case) out of every section of the memory
    file, the record of what was sent (entries kept as dated tombstones with
    their fingerprint), every safety copy, the removed list and the waiting
    list; puts a matching name on the forgotten-names list; writes the erasure
    in the action log by fingerprint only; and returns a receipt. With
    dry_run, says what it would do and changes nothing."""
    import egress
    bad = too_vague(words)
    if bad:
        return refusal("erase", bad.replace("removed", "erased"),
                       "Type the words again — at least three letters.")
    w = Words(words)
    stamp = _day(time.time())
    fingerprint = hashlib.sha256(w.text.encode("utf-8")).hexdigest()
    c.refresh()

    probe = copy.deepcopy(c.data)
    store = _erase_data(probe, w, stamp)
    names = _names_hit(c.data, w, words)
    log_hits = egress.matching(w)
    # This life's copies, then every other memory file and its copies: the
    # live file of another life is rewritten the same way as a copy.
    lives = [c] + _other_lives(c)
    groups = []
    for life in lives:
        files = ([] if life is c else [life.path]) + _copy_files(life)
        groups.append((life, [p for p in files if _file_mentions(p, w)]))
    copies = [p for _, fs in groups for p in fs]
    trash = [p for life in lives for p, e in _Trash(life)._read_all()
             if any(w(s) for _, s in _leaves(e.get("changes")))]
    temps = [p for life in lives for p in _temps_holding(life, w)]
    receipt = {
        "step": "preview" if dry_run else "done",
        "when": stamp, "words_sha256": fingerprint,
        "from_memory": _count_words(store["removed"]),
        "names_taken_off": store["unnamed"],
        "action_log_entries_reworded": store["redacted"],
        "sent_records_erased": log_hits["entries"],
        "copies": len(copies) + len(temps),
        "removed_list_entries": len(trash),
        "not_erased": [_untouched_words(s) for s in store["untouched"]],
        "still_held_elsewhere": _elsewhere(log_hits),
    }
    if not (sum(store["removed"].values()) or store["unnamed"] or store["redacted"]
            or log_hits["entries"] or copies or trash or temps):
        receipt.update(step="nothing", plain="  Nothing JEFFEREY keeps holds those "
                       "words (whole words, any case). Nothing was erased.")
        return receipt
    if dry_run:
        receipt["items"] = _erase_items(c.data, w)
        receipt["plain"] = _receipt_words(receipt, done=False)
        return receipt

    # 1. The memory file itself — the one step that must succeed first.
    done = _erase_data(c.data, w, stamp)
    if names:
        _add_forgotten(c.data, names)
    _log(c.data, f"erased everywhere at the owner's own console: "
                 f"{_count_words(done['removed'])} removed, {done['unnamed']} with a "
                 f"name taken off, {done['redacted']} action-log entries reworded, "
                 f"{log_hits['entries']} records of what was sent. The words are not "
                 f"written down.",
         "erased for good")
    try:
        c._save()
    except BaseException:
        c._rollback()
        raise
    problems: list[str] = []

    # 2. Every copy, and every other memory file (each under its own store's
    # lock, so none is rotated meanwhile) — and the half-written temporary
    # copies a cut-off save left behind (durability-34).
    rewritten = deleted = 0
    for life, files in groups:
        try:
            with life._lock():
                for p in files:
                    try:
                        raw = p.read_bytes()
                        try:
                            obj = Conscience._parse(raw)
                        except _cs._Unreadable:
                            p.unlink()
                            deleted += 1
                            continue
                        _erase_data(obj, w, stamp)
                        _cs._write_atomic(p, Conscience._canon(obj))
                        rewritten += 1
                    except OSError:
                        problems.append(f"a copy could not be rewritten ({p.name})")
                deleted += life._sweep_temps_locked()
        except OSError:
            problems.append(f"the copies beside {life.path.name} could not be reached")
        left = _temps_holding(life, w)
        if left:
            problems.append(f"{len(left)} half-written copy file(s) still hold the words")

    # 3. The removed list, and anything waiting for an OK.
    purged = 0
    for life in lives:
        for p, e in _Trash(life)._read_all():
            keep = [ch for ch in e["changes"]
                    if not any(w(s) for _, s in _leaves(ch))]
            if len(keep) == len(e["changes"]):
                continue
            try:
                if keep:
                    e["changes"] = keep
                    _cs._write_atomic(p, json.dumps(e, indent=1, ensure_ascii=False)
                                      .encode("utf-8"))
                else:
                    p.unlink()
                purged += 1
            except OSError:
                problems.append(f"an entry in the removed list could not be erased ({p.name})")
        try:
            _Pending(life).drop_matching(w)
        except StoreProblem:
            problems.append("a request waiting for the owner could not be erased")

    # 4. The record of what was sent: each entry stays, as a dated tombstone.
    try:
        red = egress.redact(w, stamp)
    except OSError as exc:
        red = {"entries": 0}
        problems.append(f"the record of what was sent could not be rewritten "
                        f"({exc.strerror or exc})")

    receipt.update(copies_rewritten=rewritten, copies_deleted=deleted,
                   removed_list_entries=purged, sent_records_erased=red["entries"],
                   from_memory=_count_words(done["removed"]),
                   names_taken_off=done["unnamed"],
                   action_log_entries_reworded=done["redacted"],
                   name_forgotten=bool(names), could_not=problems)
    receipt.pop("copies", None)
    receipt["plain"] = _receipt_words(receipt, done=True)
    return receipt


def _file_mentions(p: Path, w: Callable) -> bool:
    try:
        raw = p.read_bytes()
    except OSError:
        return False
    try:
        obj = Conscience._parse(raw)
    except _cs._Unreadable:
        return w(raw.decode("utf-8", "replace"))
    return any(w(s) for _, s in _leaves(obj))


def _erase_items(data: dict, w: Callable) -> list[tuple[str, str]]:
    out = []
    for sec in KINDS:
        if sec in AUDIT_SECTIONS:
            continue
        for it in _items(data, sec):
            if any(w(s) for _, s in _leaves(it)):
                out.append((_kind(sec), _what(sec, it)))
    return out


def _untouched_words(sec: str) -> str:
    return {
        "selfcloud_grants": "your list of keys (a key's name or note uses these words "
                            "— revoke or rename it yourself if you want it gone)",
        "permissions": "a permission you set (its category uses these words)",
        "owner": "your own name as the owner",
        "asked": "the list of which interview questions were asked (topics only)",
    }.get(sec, f"the '{sec}' section")


def _elsewhere(hits: dict) -> str:
    if not hits["entries"]:
        return ("Nothing JEFFEREY sent to an AI held these words, as far as his "
                "record of sends shows.")
    eng = ", ".join(f"{k} ({n})" for k, n in hits["engines"].most_common())
    span = (f" between {hits['first'][:10]} and {hits['last'][:10]}"
            if hits.get("first") else "")
    return (f"{hits['entries']} records of what was sent held these words{span}, "
            f"going to: {eng}. JEFFEREY erases his own record of them, but he cannot "
            f"reach what an AI company keeps. To have it deleted there, delete those "
            f"conversations in the Claude or ChatGPT app, or ask the company. "
            f"Anything marked 'on this machine' never left the house.")


def _receipt_words(r: dict, done: bool) -> str:
    head = "Erased, for good" if done else "This would erase, for good"
    lines = [f"  {head}, on {r['when']}:",
             f"    from your memories: {r['from_memory']}"]
    if r.get("names_taken_off"):
        lines.append(f"    a name taken off {r['names_taken_off']} moment(s) shared "
                     "with other people (the moments stay)")
    if r.get("action_log_entries_reworded"):
        lines.append(f"    the words taken out of {r['action_log_entries_reworded']} "
                     "action-log entr(ies) (the entries stay)")
    lines.append(f"    records of what was sent: {r['sent_records_erased']} "
                 "(each stays as a dated line with its fingerprint)")
    if done:
        lines.append(f"    safety copies: {r.get('copies_rewritten', 0)} rewritten"
                     + (f", {r['copies_deleted']} damaged or half-written one(s) deleted"
                        if r.get("copies_deleted") else ""))
    else:
        lines.append(f"    safety copies holding them: {r.get('copies', 0)}")
    lines.append(f"    the removed list: {r['removed_list_entries']}")
    if done and r.get("name_forgotten"):
        lines.append("    the name is on the forgotten list: JEFFEREY will not ask "
                     "about that person again")
    for n in r.get("not_erased") or []:
        lines.append(f"    NOT changed: {n}")
    for n in r.get("could_not") or []:
        lines.append(f"    could not: {n}")
    lines.append("  " + r["still_held_elsewhere"])
    return "\n".join(lines)


# ------------------------------------------------------- the owner's console
def _print_waiting(c: Conscience) -> list[dict]:
    rows = waiting(c)
    if not rows:
        print("  Nothing is waiting for your OK.")
        return rows
    print("  Waiting for your OK — an AI asked to remove these; nothing has gone yet:\n")
    for r in rows:
        print(f"  {r['number']:>3}.  code {r['code']}, asked {r['when'][3:]} "
              f"(waits until {r['until']}):")
        for sec, what, change in r["items"][:SHOW_MAX]:
            print(f"         {_kind(sec)}: {what}" + (f"  — {change}" if change else ""))
    return rows


def _print_removed(c: Conscience) -> list[dict]:
    rows = removed(c)
    if not rows:
        print("  Nothing has been removed in the last three months.")
        return rows
    print("  Removed, and can be put back:\n")
    for r in rows:
        print(f"  {r['number']:>3}.  {r['when'][3:]} (kept until {r['until']}):")
        for sec, what, change in r["items"][:SHOW_MAX]:
            print(f"         {_kind(sec)}: {what}" + (f"  — {change}" if change else ""))
    return rows


def _say(res: dict) -> None:
    if res.get("refused"):
        print("  " + res["reason"])
        return
    if res.get("step") == "nothing":
        print("  " + res.get("note", "Nothing was removed."))
        return
    if "put_back" in res and isinstance(res["put_back"], int):
        print(f"  Put back: {res['what']}.")
        return
    gone = res.get("removed_items", []) + res.get("changed_items", [])
    print(f"  Done: {len(gone)} thing(s).")
    for g in gone:
        print(f"    {g['kind']}: {g['what']}" + (f"  — {g['change']}" if g.get("change") else ""))
    print(f"  You can put this back until {res.get('kept_until')}, here.")


def _at_keyboard(answer, tty, yes: bool = False, what: str = "") -> bool:
    """S6 (round 8): his yes only at a terminal, with the number shown now —
    never --yes, never a script with stdin from somewhere else."""
    import answers as _answers
    if yes:
        print("  " + _answers.YES_IGNORED)
    return _answers.confirm_by_code(print, answer, tty, what)


def console_approve(c: Conscience, which: str, answer=None, yes: bool = False,
                    tty: bool | None = None) -> dict | None:
    """The owner approves a waiting request at his own keyboard — after he
    has seen exactly what it removes. A code read out to him by an AI is
    never carried out unseen (verify I-01: '/approve CODE' removed at once,
    without showing the list), and never by a script (S6: --yes is ignored;
    he types back the number shown)."""
    rows = waiting(c)
    s = str(which or "").strip()
    row = next((r for r in rows if str(r["number"]) == s or r["code"] == _clean_code(s)), None)
    if row is None:
        res = refusal("approve", "There is no request waiting with that code (it may "
                                 "have been done already, or it expired). Nothing was "
                                 "removed.")
        _say(res)
        return res
    print(f"  Code {row['code']}, asked for by '{row['asked_by']}' {row['when'][3:]}. "
          f"It would remove or change:")
    for sec, what, change in row["items"][:SHOW_MAX]:
        print(f"         {_kind(sec)}: {what}" + (f"  — {change}" if change else ""))
    if not row["items"]:
        print("         (nothing on it is still there)")
    if not _at_keyboard(answer, tty, yes, "Do this? It can still be put back."):
        print("  Nothing was removed.")
        return None
    res = approve(c, row["code"])
    _say(res)
    return res


def console_erase(c: Conscience, words: str, answer=None, yes: bool = False,
                  tty: bool | None = None) -> dict | None:
    pre = erase(c, words, dry_run=True)
    if pre.get("refused"):
        print("  " + pre["reason"])
        return None
    print(pre["plain"])
    if pre["step"] == "nothing":
        return None
    for kind, what in pre.get("items", [])[:SHOW_MAX]:
        print(f"      {kind}: {what}")
    print("\n  This cannot be undone — not from the removed list, not from a copy.")
    if not _at_keyboard(answer, tty, yes, "Erase it everywhere, for good?"):
        print("  Nothing was erased.")
        return None
    try:
        r = erase(c, words)
    except StoreProblem as e:
        print("  " + e.for_owner())
        return None
    print(r["plain"])
    return r


def console_bring_back(c: Conscience, which, answer=None, tty: bool | None = None) -> dict | None:
    """Put a removed thing back — he sees what, and says so himself (S6)."""
    entries = removed(c)
    s = str(which).strip()
    row = next((r for r in entries if str(r["number"]) == s or r["file"] == s
                or (s and _clean_code(s) == r.get("code"))), None)
    if row is not None:
        print(f"  This puts back what went {row['when'][3:]}:")
        for sec, what, change in row["items"][:SHOW_MAX]:
            print(f"         {_kind(sec)}: {what}" + (f"  — {change}" if change else ""))
        if not _at_keyboard(answer, tty, False, "Put it back?"):
            print("  Nothing was put back.")
            return None
    res = bring_back(c, which)
    _say(res)
    return res


def menu(c: Conscience, answer=None) -> int:
    """'Forget or bring back' — the owner's own window."""
    import answers as _answers
    if not _answers.person_at_keyboard() and answer is None:
        print("  " + _answers.NOT_AT_KEYBOARD)
        return 1
    ask = answer or (lambda p: _answers.read_tty(p) or "")
    print("\n  FORGET OR BRING BACK\n")
    w = _print_waiting(c)
    print()
    _print_removed(c)
    print("\n  Type:  ok <number>     remove what is waiting (or just type its code;"
          "\n                         it can still be put back)"
          "\n         back <number>   put something back"
          "\n         erase           erase words everywhere, for good"
          "\n         just return     change nothing\n")
    try:
        choice = ask("  > ").strip()
    except EOFError:
        choice = ""
    verb, _, rest = choice.partition(" ")
    verb, rest = verb.lower(), rest.strip()
    if _clean_code(choice) in {x["code"] for x in w}:      # just the code he was told
        verb, rest = "ok", choice
    try:
        if verb in ("ok", "approve") and rest:
            console_approve(c, rest, answer)
        elif verb in ("back", "bring") and rest:
            console_bring_back(c, rest.replace("back", "").strip() or rest, answer)
        elif verb == "erase":
            words = rest or ask("  Which words? (for example a name): ")
            console_erase(c, words, answer)
        else:
            print("  Nothing was changed.")
    except StoreProblem as e:
        print("  " + e.for_owner())
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--path", default=None, help="the memory file")
    ap = argparse.ArgumentParser(description="Forget or bring back — the owner's own.",
                                 parents=[common])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("waiting", parents=[common])
    a = sub.add_parser("approve", parents=[common])
    a.add_argument("code")
    a.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)   # ignored (S6)
    sub.add_parser("removed", parents=[common])
    b = sub.add_parser("bring-back", parents=[common])
    b.add_argument("which")
    e = sub.add_parser("erase", parents=[common])
    e.add_argument("words", nargs="+")
    e.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)   # ignored (S6)
    args = ap.parse_args(argv)
    c = Conscience.for_surface(Path(args.path).expanduser() if args.path else None)
    try:
        c.refresh()
    except StoreProblem as exc:
        print("  " + exc.for_owner())
        return 1
    try:
        if args.cmd is None:
            return menu(c)
        if args.cmd == "waiting":
            _print_waiting(c)
        elif args.cmd == "removed":
            _print_removed(c)
        elif args.cmd == "approve":
            res = console_approve(c, args.code, yes=args.yes)
            return 1 if res is None or res.get("refused") else 0
        elif args.cmd == "bring-back":
            res = console_bring_back(c, args.which)
            return 1 if res is None or res.get("refused") else 0
        elif args.cmd == "erase":
            return 0 if console_erase(c, " ".join(args.words), yes=args.yes) else 1
    except StoreProblem as exc:
        print("  " + exc.for_owner())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
