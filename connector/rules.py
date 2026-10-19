"""
The Conscience Rules — how Jefferey is allowed to carry you
===========================================================

Self-Cloud holds everything. The Digital Conscience holds only what the
person deliberately lets in. And over that curated self, the person writes
**rules** — standing instructions on how Jefferey handles it:

    "Share my health only with me."
    "When I bring up my father, don't try to fix it. Just listen."
    "To anyone else, say I'm retired and leave it there."
    "Speak of Karen warmly, always. Never as a complaint."
    "If I mention drinking, be direct with me."

Three kinds of rule, each answering a different question:

    disclosure       WHO may hear WHAT.       "share X only with Y"
    reaction         HOW to respond to ME.    "when I raise X, do Y"
    representation   HOW to speak of me to    "to others, about X, say Y"
                     OTHERS.

Plus the intake gate: nothing enters the conscience from the wider Self-Cloud
without the person choosing it. Storage is total; the conscience is curated.

Enforcement, not etiquette:
- `check_disclosure(audience, tags)` is called before anything about the
  person is said to anyone. Deny wins over allow. Unknown audience → nothing
  but what was explicitly opened to "anyone".
- `guidance_for(tags, audience)` returns the reaction and representation
  rules that apply, verbatim in the owner's words — so Jefferey speaks *their*
  instruction, not his paraphrase of it.
- The owner can read every rule in plain language, and delete any of them
  without argument.
"""

from __future__ import annotations

import copy
import re
import secrets
import time

import forgetting
import grounding
import provenance

KINDS = ("disclosure", "reaction", "representation")

# Audiences a rule can name. Anything else is a named person or group
# ("karen", "family", "my sister"). Since October 2026 (I-24) a rule meets
# its audience however it is written: 'Karen Novak <k@example.com>' is the
# 'karen' a rule names, and his ex-wife Karen is 'family' too. A rule that
# says NO matches every way the audience can be written; a rule that says
# YES must match it exactly.
#
# Who a NO is for (R2, round 6; D1, round 7): exactly its audience — except
# that
#   * an explicit anyone-word ('the public', 'nobody but my doctor', 'les
#     gens', 'not a soul'; grounding.is_anyone) makes it a no for everyone
#     but his own JEFFEREY;
#   * a no that names an AI, an engine or the company behind one ('ChatGPT',
#     'any AI', "l'IA", 'Google', 'the cloud'; grounding.names_ai) holds for
#     EVERY key that reaches an engine — his own caretaker key 'jefferey'
#     too. Only the owner himself, at his own keyboard, is not an AI;
#   * a no that names his family or the people who read through the family
#     key ('ma famille', 'my kids', 'the grandchildren', 'my daughter';
#     grounding.names_family) holds for the family key.
# A no that names people never applies to his caretaker key: his own agent
# always sees his life so it can look after him; his rules about people
# govern everyone else.
#
# AN AUDIENCE NO ONE KNOWS IS EVERYONE (F1, round 8). A no whose audience —
# read through the shared fold — is not a person he recorded himself, not
# the name of one of his keys, and not a group (an anyone-word, a family
# word, an AI word) holds for everyone (grounding.unknown_parts): every
# person, the family key and every AI — but not his own JEFFEREY, exactly as
# a no for 'anyone' does (round 8 repair: holding it from his own JEFFEREY
# too blinded the caretaker that looks after him, and an engine's untagged
# no for a name nobody knows hid his whole life from it). 'my lawyer', 'Bob',
# 'Le Monde' and 'the press' used to bind only a reader of that very name —
# in practice nobody. Once he records who they are at his own console, the
# no binds only them; a person an AI wrote down never makes a no narrower. A
# yes never widens past what is written.
#
# A NO FOR HIMSELF IS A NO FOR EVERYONE (G1, round 9). A no whose audience is
# the owner himself — 'me', 'myself', 'just me', 'only me', 'I', 'moi',
# 'moi-même', 'juste moi', in any case or letters (grounding.names_self) — or
# that was left at its default holds as a no for someone nobody knows does:
# for everyone and every AI but his own JEFFEREY. Round 8 stored such a no
# as 'me' and it bound nobody: 'Keep my health to myself' let the family key
# read his diabetes. The default audience of a disclosure no is everyone, on
# every surface; set_rule says so plainly. A YES for himself widens nothing:
# he always hears about himself, and no one else is named.
SELF = "me"
ANYONE = "anyone"
# The keys a no may name: the presets, and every key he has given out.
KEY_NAMES = ("claude-raw", "gpt-raw", "jefferey", "family", "executor")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _tags(s: str | list) -> list[str]:
    if isinstance(s, list):
        return [str(t).strip().lower() for t in s if str(t).strip()]
    return [t.strip().lower() for t in str(s).split(",") if t.strip()]


def _aud(r: dict) -> str:
    return grounding.norm_audience(r.get("audience", "")) or SELF


def _written(r: dict) -> str:
    """The audience as he wrote it, capitals and all ('Le Monde' is the
    newspaper, 'le monde' is everyone). Rules kept before round 7 have only
    the lower-case form."""
    return str(r.get("audience_written") or r.get("audience") or "")


# A RULE'S AUDIENCE IS READ BOTH WAYS (round 9, second repair). A character
# that shows as nothing or as a blank in it ('Karen\u2800Novak') is read as
# nothing and as a space: a NO is for everyone either reading names, a YES
# only for whom both readings name.
def _auds(r: dict) -> frozenset:
    """Every reading of this rule's audience, as norm_audience reads it."""
    out = {a for a in grounding.norm_audiences(_written(r)) if a}
    return frozenset(out | {_aud(r)})


def _yes_to(r: dict, names) -> bool:
    """Does this rule name an audience known by these names, in every
    reading (what a YES needs)?"""
    return _auds(r) <= set(names)


def unknown(r: dict, data: dict | None = None) -> tuple[str, ...]:
    """The parts of a NO's audience nobody knows (F1, round 8): not a person
    he recorded himself, not one of his keys, not an anyone-, family- or
    AI-word. Empty for a yes, and when every part is known."""
    if not isinstance(r, dict) or r.get("kind") != "disclosure" or r.get("allow"):
        return ()
    if _aud(r) == SELF:
        return ()
    data = data or {}
    people = tuple(grounding.person_key(p.get("name", ""), p.get("relationship", ""))
                   for p in provenance.his_people(data))
    keys = set(KEY_NAMES) | set((data.get("selfcloud_grants") or {}).keys())
    return grounding.unknown_parts(_written(r), people, keys)


def for_himself(r: dict) -> bool:
    """Is this rule's audience the owner himself, or was it left at its
    default (G1, round 9)?"""
    if not isinstance(r, dict):
        return False
    return (bool(r.get("audience_default")) or SELF in _auds(r)
            or grounding.names_self(_written(r)))


def _no_aud(r: dict, data: dict | None = None) -> str:
    """Who a rule that says NO is for: its own audience, or everyone when it
    says so with an anyone-word ('members of the public', 'nobody but my
    doctor', 'les gens', 'le monde') — or when nobody knows who it is (F1,
    round 8: 'Bob', 'my GP' and 'Le Monde' are each only themselves once he
    has recorded who they are) — or when it is for himself, or was left at
    its default (G1, round 9)."""
    if grounding.is_anyone(_written(r)) or unknown(r, data):
        return ANYONE
    if r.get("kind") == "disclosure" and not r.get("allow") and for_himself(r):
        return ANYONE
    return _aud(r)


def _engine_names() -> tuple[str, ...]:
    """The names of the engines reading right now ('hermes3', 'claude')."""
    try:
        label = provenance._engine_label().lower()
    except Exception:
        label = ""
    # a model's own name carries its version ('hermes3', 'granite3', 'phi4');
    # the rest of a label is plain words ('a person holding the family key')
    return tuple(w for w in label.replace(":", " ").split()
                 if re.fullmatch(r"[a-z][a-z\-]*\d[\w.\-]*", w))


def names_ai(r: dict) -> bool:
    """Does this rule name an AI, an engine or the company behind one (D1)
    — the engines reading right now among them (F1)?"""
    return grounding.names_ai(_written(r), _engine_names())


def every_ai(r: dict, data: dict | None = None) -> bool:
    """Does this NO hold for every AI, his own JEFFEREY too? Only when it
    names an AI (D1). A no for someone nobody knows holds for everyone but
    his own JEFFEREY, as a no for 'anyone' does (F1, round 8 repair)."""
    return names_ai(r)


def describe(r: dict, data: dict | None = None) -> tuple[str, str]:
    """(whom a rule that says NO holds for, the note that says so in plain
    words) — the same on every surface."""
    said = _written(r)
    nobody = unknown(r, data)
    everyone, ai = _no_aud(r, data) == ANYONE, every_ai(r, data)
    who = " and ".join(f"'{x}'" for x in nobody)
    are = "is" if len(nobody) == 1 else "are"
    jeff = ("except your own JEFFEREY, which always sees your life so it can look after "
            "you. To keep it from your JEFFEREY too, add a no for 'any AI'.")
    if r.get("audience_default") and not ai:
        return ("everyone",
                "You did not say who this no is for, so it holds for everyone and every AI "
                + jeff + " To let someone hear it after all, add a yes that names them.")
    if not ai and for_himself(r):
        return ("everyone",
                f"A no for '{said or SELF}' — for you yourself — holds for everyone and every AI "
                + jeff + " You yourself always see it. To let someone hear it after all, add "
                "a yes that names them.")
    if ai:
        return ("everyone and every AI" if everyone else "every AI",
                f"'{said}' names an AI, so this no holds for every AI that reads your "
                "memories — Claude, ChatGPT, a model on this Mac, and your own JEFFEREY too"
                + (", and for every person as well" if everyone else "")
                + "." + (f" I don't know who {who} {are}: add them to your people to make it "
                         f"narrower." if nobody else "")
                + " Only you, reading at your own keyboard, still see it.")
    if nobody:
        return ("everyone",
                f"I don't know who {who} {are}, so this no holds for everyone and every AI "
                f"except your own JEFFEREY, which always sees your life so it can look after "
                f"you, and never tells it to {who if len(nobody) == 1 else 'them'}. "
                f"Add them to your people to make it narrower. To keep it from your JEFFEREY "
                f"too, add a no for 'any AI'.")
    if everyone:
        return ("everyone",
                f"'{said}' means everyone, so this no holds for everyone except your own "
                "JEFFEREY, which always sees your life so it can look after you. To keep it "
                "from your JEFFEREY too, add a no for 'any AI'. To let someone hear it after "
                "all, add a yes that names them.")
    family = grounding.names_family(said)
    return (_aud(r),
            f"This no is only for '{said}'"
            + (", and so for your family's key too" if family else "")
            + ". Your own JEFFEREY still sees it; nobody else is kept from it by this rule.")


def _says_no_to(r: dict, names, people) -> bool:
    """Does this NO rule reach an audience known by these names? Its own
    audience, each word of it, or the recorded person it names (verify I-24:
    a no for 'Karen Novak' let 'Karen' and 'my ex-wife' through) — and, for
    a no that names his family or his children ('ma famille', 'my kids'),
    the family (D1). Any reading of its audience (round 9, second repair)."""
    if _auds(r) & set(names):
        return True
    if "family" in names and grounding.names_family(_written(r)):
        return True
    return bool(grounding.rule_names(_written(r), people) & set(names))


def _ai_no(data: dict, hit) -> dict | None:
    """The first rule that says NO to every AI — it names one (D1) — about
    whatever `hit` reaches."""
    for r in data.get("rules") or []:
        if isinstance(r, dict) and r.get("kind") == "disclosure" and not r.get("allow") \
                and hit(r) and every_ai(r, data):
            return r
    return None


def verdict(data: dict, broad, strict, hit) -> tuple[bool | None, dict | None, list]:
    """The owner's rules for an audience known by these names, about
    whatever `hit(rule)` says a rule reaches. (False, rule, []) when a rule
    keeps it from them; (True, rule, limited_to) when one opens it; (None,
    None, []) when no rule speaks. A rule naming this audience beats a rule
    for 'anyone'; at the same level, no beats yes."""
    rs = [r for r in data.get("rules") or [] if isinstance(r, dict)]
    people = data.get("people") or []
    disc = [r for r in rs if r.get("kind") == "disclosure" and hit(r)]
    reps = [r for r in rs if r.get("kind") == "representation" and hit(r)]
    for level, (names_no, names_yes) in enumerate(((broad, strict), ({ANYONE}, {ANYONE}))):
        # a no for someone nobody knows (F1) holds for everyone — and, like
        # any no, first of all for the very audience it names
        no = [r for r in disc if not r.get("allow") and (
            _no_aud(r, data) in names_no if level else
            (_no_aud(r, data) != ANYONE or unknown(r, data))
            and _says_no_to(r, names_no, people))]
        if no:
            return False, no[0], []
        # a yes for himself widens nothing (G1, round 9)
        yes = [r for r in disc if r.get("allow") and _yes_to(r, names_yes)
               and not for_himself(r)]
        if yes:
            return True, yes[0], []
        say = [r for r in reps if _yes_to(r, names_yes)]
        if say:
            return True, say[0], [r.get("instruction", "") for r in say]
    return None, None, []


# The far end of a connection — the engine's maker — is one reader; the key
# holder (the family, the executor, a named key) is another. Every key that
# reaches an engine carries grounding.AI_READER in its audiences (D1): then
# every no that names an AI holds for it.
VENDOR_NAMES = frozenset({"ai", "an ai", "any ai", "engines", "engine", "ais", "anthropic",
                          "claude", "openai", "chatgpt", "gpt", grounding.AI_READER})


def held_back(data: dict, audiences, text: str = "", tags=(), yes_to=None) -> dict | None:
    """Does one of the owner's rules keep this (a fact, a moment, a person,
    a picture) from whoever is reading? The rule that does, or None. Only a
    rule that says no holds anything back here: what reaches a reader at all
    was already decided by its visibility — this is the owner's rules on top
    (I-10, I-11: the life layer and the facts never consulted them).

    Everyone who will read it is asked on their own, and a no for any of them
    holds it back (verify I-10: a yes for 'claude' let the family key read
    his diabetes over Claude despite 'never share my health with anyone',
    while the same key over ChatGPT was refused). An engine is always one of
    the readers (D1): a no that names any AI holds for every key that
    reaches one, his caretaker key too, whatever yes there is.

    `yes_to`, when given, is the only set of names a YES may meet: the
    readers as they are, and the people HE recorded whose names they are
    exactly. `audiences` may be wider — a relationship, a word of a name, a
    person an AI wrote down — but that width is for a NO only (final checks:
    a family key whose aliases took in an AI-recorded 'Karen Novak, family'
    read past 'Never tell anyone when I travel' through his 'Karen may
    know')."""
    # every reading of each reader's name meets a no; only the names whose
    # readings agree meet a yes (round 9, second repair)
    readings = [grounding.norm_audiences(a) for a in audiences or () if a]
    aud = frozenset().union(*readings) - {""} if readings else frozenset()
    if not aud:
        return None
    hit = lambda r: grounding.tag_hits(r.get("tags") or [], text, tags)  # noqa: E731
    if aud & VENDOR_NAMES:
        rule = _ai_no(data, hit)
        if rule:
            return rule
    people = aud - VENDOR_NAMES
    if yes_to is not None:
        readings = [grounding.norm_audiences(a) for a in yes_to or () if a]
    sure = frozenset(x for rs in readings if len(rs) == 1 for x in rs) - VENDOR_NAMES
    if people:
        ok, rule, _ = verdict(data, people, sure, hit)
        if ok is False:
            return rule
    return None


def binds(r: dict, rd: dict | None = None, data: dict | None = None) -> bool:
    """Does this rule hold for whoever reads (S1, round 8)? Then its words —
    his own sentence, which is often the very secret ('Never tell any AI that
    I have HIV') — are never handed to that reader: only what it is about,
    whom it is for, and yes or no. Only disclosure rules bind a reader; a rule
    for how to react or how to speak of him is an instruction to follow."""
    if not isinstance(r, dict) or r.get("kind") != "disclosure":
        return False
    rd = rd if rd is not None else provenance.reader()
    aud = rd.get("audiences") or frozenset()
    if not aud:
        return False                     # the owner himself, at his keyboard
    if not r.get("allow") and every_ai(r, data):
        return True                      # every reader that reaches an engine is an AI
    if not rd.get("people_rules"):
        return False                     # his rules about people never hold for his own key
    names = frozenset(x for a in aud for x in grounding.norm_audiences(a)) - VENDOR_NAMES
    if not r.get("allow") and _no_aud(r, data) == ANYONE:
        return True
    return bool(_auds(r) & names) or (not r.get("allow") and _says_no_to(
        r, names, (data or {}).get("people") or []))


def words_held(r: dict, rd: dict | None = None, data: dict | None = None) -> bool:
    """Are this rule's own words kept from whoever reads (S1, round 8
    repair)? When the rule holds for that reader (binds) — and when its words
    are about something one of his rules keeps from that reader, or are
    private and the reader does not hold his private life. 'Never tell Karen
    Novak that I have HIV' does not hold for his own JEFFEREY, but its words
    are about his health, which 'Never tell my health to any AI' keeps from
    every AI: the words of one rule never carry what another keeps back.
    Who may read a rule's words follows the same rules as everything else."""
    if not isinstance(r, dict):
        return False
    rd = rd if rd is not None else provenance.reader()
    aud = rd.get("audiences") or frozenset()
    if not aud:
        return False                     # the owner himself, at his keyboard
    if binds(r, rd, data):
        return True
    text = str(r.get("instruction") or "")
    tags = [str(t) for t in r.get("tags") or [] if str(t).strip()]
    kinds: list[str] = []
    for t in tags or [""]:
        kinds += [k for k in grounding.sensitivity(text, t) if k not in kinds]
    if kinds and not rd.get("caretaker") and not rd.get("owner"):
        return True
    return held_back(data or {}, aud, text, tags + kinds) is not None


# A RULE'S TOPIC IS ONE OF ITS WORDS (round 9 repair). 'Never tell Ed about
# it', tagged 'hiv', was listed to every AI with its tag, draft_guidance said
# do_not_mention ['hiv'], and check_disclosure(Ed, 'hiv') said 'the owner
# forbade it' where 'diabetes' said 'silence' — an unlimited oracle on the
# word his rule is about. A topic word that is itself private ('hiv',
# 'dementia', 'diabetes' — not a kind, like 'health' or 'money') goes to a
# reader only as his rules let that reader hear it: otherwise the reader sees
# its kind ('health'), every question by such a word is asked by its kind, a
# no about it holds for its whole kind for that reader, and a yes about it
# opens nothing to that reader.
def _private_word(tag) -> list[str]:
    t = grounding.normalise(tag)
    if not t or t in grounding.CLASSES or t in grounding.CLASS_ALIASES:
        return []
    return grounding.sensitivity(t)


def tag_held(tag, rd: dict | None = None, data: dict | None = None) -> list[str]:
    """The kinds a rule's topic word stands for when that word is kept from
    whoever reads — or [] when the reader may see the word itself."""
    rd = rd if rd is not None else provenance.reader()
    aud = rd.get("audiences") or frozenset()
    if not aud:
        return []                        # the owner himself, at his keyboard
    kinds = _private_word(tag)
    if not kinds:
        return []
    if not rd.get("caretaker") and not rd.get("owner"):
        return kinds                     # a reader who does not hold his private life
    return kinds if held_back(data or {}, aud, str(tag), [str(tag)] + kinds) else []


def shown_tags(r: dict, rd: dict | None = None, data: dict | None = None) -> list[str]:
    """A rule's topics as this reader may see them (see above)."""
    out: list[str] = []
    for t in (r.get("tags") or []) if isinstance(r, dict) else []:
        for x in tag_held(t, rd, data) or [t]:
            if x not in out:
                out.append(x)
    return out


def asked_as(tags, rd: dict | None = None, data: dict | None = None) -> set[str]:
    """The topics a reader asks about, as it may ask them: a private word
    kept from it is asked by its kind."""
    out: set[str] = set()
    for t in tags:
        out |= set(tag_held(t, rd, data) or [t])
    return out


def held_for_reader(r: dict, rd: dict | None = None, data: dict | None = None) -> dict:
    """A rule as a reader whose rules keep its words from it may see it: what
    it is about, whom it is for, yes or no — never his sentence (S1)."""
    v = {k: r[k] for k in ("id", "kind", "tags", "audience", "allow", "added") if k in r}
    if "tags" in v:
        v["tags"] = shown_tags(r, rd, data)
    if r.get("kind") == "disclosure" and not r.get("allow"):
        v["holds_for"] = describe(r, data)[0]
    v["instruction_held_back"] = True
    v["note"] = ("His own words for this rule are not given to this AI — it holds for you, "
                 "or its words are about something his rules keep from you. Only what it is "
                 "about, whom it is for, and whether it is a yes or a no. Obey it; never ask "
                 "him to read it to you.")
    return v


def _engine() -> bool:
    return provenance.engine_writes()


def _caller_holds_private() -> bool:
    try:
        import access
        return access.may("life.read")
    except Exception:
        return False


class ConscienceRules:
    """The owner's standing instructions over their own conscience."""

    def __init__(self, conscience):
        self.c = conscience
        self.c.data.setdefault("rules", [])
        self.c.data.setdefault("conscience_included", [])   # intake gate

    # ---------------------------------------------------------------- intake
    def include(self, ref: str, note: str = "") -> dict:
        """The person chose to let something from Self-Cloud INTO the
        conscience — a photo, an album, a document. Nothing enters otherwise."""
        entry = {"ref": ref.strip(), "note": note.strip(), "added": _now()}
        self.c.data["conscience_included"].append(entry)
        self.c._save()
        return {**entry, "rule": "Included by the owner's choice. Storage is total; the conscience is curated."}

    def exclude(self, contains: str = "", ids=None, confirm: str = "") -> dict:
        """Take something back out of the conscience. It stays on Self-Cloud;
        Jefferey simply no longer holds it as part of who they are. Two
        steps, by id or whole words, never a wildcard (forgetting.py)."""
        return forgetting.exclude(self.c, contains, ids, confirm)

    def included(self) -> list[dict]:
        return list(self.c.data.get("conscience_included", []))

    # ----------------------------------------------------------------- rules
    def set_rule(self, kind: str, tags: str, instruction: str,
                 audience: str | None = None, allow: bool = True) -> dict:
        """Write one rule in the owner's own words.

        kind       'disclosure' | 'reaction' | 'representation'
        tags       what it's about: 'health', 'father', 'money', 'karen' ...
        audience   who it concerns: 'anyone', or a named person/group
                   ('karen', 'family', 'my doctor'). Left out, a NO is for
                   everyone (but his own JEFFEREY) and any other rule is for
                   him ('me'). A no for himself is a no for everyone too (G1).
        allow      for disclosure rules only: True = may share with this
                   audience, False = must not
        instruction  the rule itself, verbatim — this is what Jefferey obeys
        """
        kind = kind.strip().lower()
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        written = " ".join(str(audience or "").split())
        defaulted = not written
        no = kind == "disclosure" and not allow
        rule = {
            "id": f"r{int(time.time() * 1000) % 10_000_000}",
            "kind": kind,
            "tags": _tags(tags),
            "audience": written.lower() or (ANYONE if no else SELF),
            "allow": bool(allow),
            "instruction": instruction.strip(),
            "added": _now(),
        }
        if defaulted and no:
            rule["audience_default"] = True          # said so plainly (G1, round 9)
        if written and written != written.lower():
            rule["audience_written"] = written       # 'Le Monde', not 'le monde' (D1)
        if _engine():
            return self._from_an_engine(rule)
        rule["source"] = provenance.source(text=rule["instruction"])
        rule["status"] = provenance.status_for(rule["source"])
        self.c.data["rules"].append(rule)
        self.c._save()
        return self._as_read(rule)

    def _from_an_engine(self, rule: dict) -> dict:
        """S1 (round 8): an AI never changes what is his. A NO from an engine
        narrows what goes out, so it holds at once — labelled as the AI's
        note, not yet confirmed by him. Anything else — a yes, a rule for how
        to react or how to speak of him — is a proposal that changes nothing
        until he confirms it with his own hands. (Before, an engine's yes from
        MCP or POST /rules opened his health to anyone.)"""
        src = provenance.source(text=rule["instruction"])
        if rule["kind"] == "disclosure" and not rule["allow"]:
            rule.update(source=src, status="pending")
            self.c.data["rules"].append(rule)
            self.c._save()
            out = self._as_read(rule)
            out = {k: v for k, v in out.items() if k != "source"}
            out.update(status="pending", noted_by=provenance.NOTED_BY_AI)
            out["note"] = (out.get("note", "") + " This no holds at once — a no only "
                           "narrows what goes out — and it is noted by the AI, not yet "
                           "confirmed by him: he confirms it himself (/pending, then "
                           "/confirm, in 'Talk to JEFFEREY on this Mac').").strip()
            return out
        prop = {"id": "rp-" + secrets.token_hex(3), "action": "add", "rule": rule,
                "source": src, "status": "pending", "added": _now()}
        self.c.data.setdefault("rule_proposals", []).append(prop)
        self.c._save()
        return {"proposed": True, "id": prop["id"], "kind": rule["kind"],
                "tags": rule["tags"], "audience": rule["audience"], "allow": rule["allow"],
                "status": "waiting_for_owner", "changed": False,
                "note": ("Proposed, not made: this changes nothing until he confirms it "
                         "himself. A yes, or a rule for how to react to him or speak of him, "
                         "is his to make — an AI never changes his rules for him."),
                "tell_the_user": ("Tell him plainly what you proposed and that it waits for "
                                  "him: he types /pending and /confirm in 'Talk to JEFFEREY on "
                                  "this Mac' (or runs python connector/conscience.py confirm). "
                                  "Until then, act as if it was never written.")}

    def _as_read(self, rule: dict) -> dict:
        """The rule, and — for a no — whom it holds for, said so he knows."""
        if rule.get("kind") != "disclosure" or rule.get("allow"):
            return rule
        holds, note = describe(rule, self.c.data)
        return {**rule, "holds_for": holds, "note": note}

    def remove_rule(self, rule_id_or_text: str = "", confirm: str = "") -> dict:
        """Delete a rule by its id, or by whole words of it, an exact tag or
        its audience. Never argued with, never done on a guess: the first
        call shows which rules would go and gives a one-time code; only the
        second, with the code, removes them (forgetting.py).

        From an engine (S1, round 8) taking a rule away widens what goes out,
        so it is a proposal: nothing is removed until he confirms it with his
        own hands, and no code completes it for an AI. (Before, the code the
        engine was handed itself lifted his 'never tell any AI'.)"""
        if not _engine():
            return forgetting.remove_rules(self.c, rule_id_or_text, confirm)
        if isinstance(confirm, str) and confirm.strip():
            return forgetting.refusal(
                "remove_rule",
                "A code never removes one of his rules for an AI: taking a rule away lets "
                "more go out, so only he does it, with his own hands. Nothing was removed.",
                "Tell him what you asked to remove, and that it waits for him: /pending and "
                "/confirm in 'Talk to JEFFEREY on this Mac'. Do not try again yourself.")
        rd = provenance.reader()
        # a search by words: a key paused for searching that finds nothing is
        # refused, and one that finds nothing is counted (G2, round 9)
        paused = self.c.search_paused("remove_rule")
        if paused:
            return paused
        # Only by what this engine may read of a rule: its id, its topic, its
        # audience — and its words only when they are not kept from it (round
        # 8 repair: 'HIV' said 'proposed', 'cancer' said 'nothing', a yes/no
        # test of the very sentence it may not read).
        plan = forgetting.plan_rules(
            self.c, rule_id_or_text,
            readable=lambda r: not words_held(r, rd, self.c.data),
            tags_of=lambda r: shown_tags(r, rd, self.c.data))
        if isinstance(plan, str):
            return forgetting.refusal("remove_rule", plan)
        self.c.search_found(bool(plan.changes))
        if not plan.changes:
            return {"step": "nothing", "count": 0, "removed": 0,
                    "note": "Nothing matched, so nothing was asked for. Words match whole "
                            "words; a rule can also be named by its id (list_rules)."}
        src = provenance.source(text=str(rule_id_or_text or ""))
        props = self.c.data.setdefault("rule_proposals", [])
        ids, rows = [], []
        for ch in plan.changes:
            r = ch["before"]
            old = next((x for x in props if isinstance(x, dict) and x.get("action") == "remove"
                        and x.get("rule_id") == r.get("id")), None)
            if old is None:
                old = {"id": "rp-" + secrets.token_hex(3), "action": "remove",
                       "rule_id": r.get("id"), "rule": copy.deepcopy(r), "source": src,
                       "status": "pending", "added": _now()}
                props.append(old)
            ids.append(old["id"])
            seen = held_for_reader(r, rd, self.c.data) if words_held(r, rd, self.c.data) else r
            rows.append({"id": r.get("id"), "kind": "rule",
                         "what": (f"a {'yes' if seen.get('allow') else 'no'} about "
                                  f"{', '.join(seen.get('tags') or []) or 'anything'} for "
                                  f"{seen.get('audience')}") if seen is not r else
                                 forgetting._what("rules", r)})
        self.c._save()
        return {"step": "proposed", "count": len(rows), "would_remove": rows,
                "needs_owner": True, "removed": 0, "proposal_ids": ids,
                "how_to_finish": (
                    "Nothing has been removed. Taking one of his rules away lets more go "
                    "out, so it is never done because an AI asked: it waits for him. Read "
                    "him the list. If he wants it, he does it himself — /pending, then "
                    "/confirm, in 'Talk to JEFFEREY on this Mac' (or python "
                    "connector/conscience.py confirm). Do not call remove_rule again for it."),
                "tell_the_user": forgetting.ASK_FIRST}

    def rules(self, kind: str = "") -> list[dict]:
        rs = self.c.data.get("rules", [])
        return [r for r in rs if isinstance(r, dict) and (not kind or r["kind"] == kind.lower())]

    def listed(self, kind: str = "") -> list[dict]:
        """The rules as he reads them: each no that holds for everyone says so.
        To an engine a rule holds for, never his sentence (S1, round 8), nor
        the sentence of any rule whose words are about what his rules keep
        from it (words_held); an AI's note is labelled, and what an AI
        proposed is listed apart."""
        rd = provenance.reader()
        out = []
        for r in self.rules(kind):
            v = (held_for_reader(r, rd, self.c.data) if words_held(r, rd, self.c.data)
                 else self._as_read(r))
            v = {k: x for k, x in v.items() if k not in ("source", "status")}
            if "tags" in v:
                v["tags"] = shown_tags(r, rd, self.c.data)
            if provenance.pending(r):
                v.update(status="pending", noted_by=provenance.NOTED_BY_AI)
            out.append(v)
        for p in self.c.data.get("rule_proposals") or []:
            if not isinstance(p, dict):
                continue
            r = p.get("rule") if isinstance(p.get("rule"), dict) else {}
            if kind and r.get("kind") != kind.lower():
                continue
            out.append({"id": p.get("id"), "kind": r.get("kind"),
                        "tags": shown_tags(r, rd, self.c.data),
                        "audience": r.get("audience"), "allow": r.get("allow"),
                        "proposed": "to remove" if p.get("action") == "remove" else "to add",
                        "status": "waiting_for_owner",
                        "note": "An AI proposed this; it changes nothing until he confirms it."})
        return out

    # ------------------------------------------------------------ enforcement
    def check_disclosure(self, audience: str, tags: str | list) -> dict:
        """May this be said to this audience? Called BEFORE speaking about the
        person to anyone who is not them.

        Logic: the owner themself may always hear anything. For everyone
        else: a matching DENY rule wins outright; otherwise an explicit ALLOW
        for this audience (or for 'anyone') is required; otherwise refuse.
        Silence is a 'no'.
        """
        aud = str(audience or "").strip().lower()
        want = set(_tags(tags))
        # only when the whole audience is him (round 9 repair: 'me and Karen
        # Novak' was a silent yes, because any part of it was him), in both
        # readings, with no 'not' in it (second repair: 'not me')
        if grounding.only_self(audience):
            return {"allowed": True, "audience": aud, "reason": "the owner may always hear about themself"}
        # 'Karen Novak <k@example.com>' meets a rule for 'karen' (I-24: only
        # the exact string used to match, so a 'never tell Karen' rule let
        # her full name through to an 'anyone' allow).
        broad, strict = self._aliases(aud)
        rd = provenance.reader()
        # asked as this reader may ask it (a private word kept from it by its
        # kind); a no about a word kept from it holds for the whole kind, and
        # a yes about one opens nothing to it (round 9 repair)
        seen = asked_as(want, rd, self.c.data)
        text = " ".join(sorted(seen))

        def on_topic(r):
            tags = r.get("tags") or []
            if r.get("allow") or r.get("kind") != "disclosure":
                if any(tag_held(t, rd, self.c.data) for t in tags):
                    return False
                if seen != want:
                    return False
                return grounding.tag_hits(tags, text, want)
            return grounding.tag_hits(shown_tags(r, rd, self.c.data), text, seen)

        if grounding.names_ai(audience):
            # a no that names any AI holds for every AI (D1)
            no = _ai_no(self.c.data, on_topic)
            if no:
                out = {"allowed": False, "audience": aud, "tags": sorted(want),
                       "reason": "the owner forbade it", "rule": no.get("instruction", "")}
                if not _caller_holds_private() or words_held(no, None, self.c.data):
                    out.pop("rule", None)
                return out
        ok, rule, limited = verdict(self.c.data, broad, strict, on_topic)
        if ok is None:
            return {"allowed": False, "audience": aud, "tags": sorted(want),
                    "reason": ("no rule opens this to this audience — silence is a no. "
                               "Say nothing about it, and if pressed, say it isn't yours "
                               "to share.")}
        out = {"allowed": ok, "audience": aud, "tags": sorted(want),
               "reason": ("the owner forbade it" if not ok else
                          "the owner told you what to say — say only that" if limited else
                          "the owner permitted it"),
               "rule": rule.get("instruction", "")}
        if limited:
            # A representation rule ("to others, say I'm retired") IS the
            # owner's permission to say exactly that much — and no more. Its
            # words go only to a reader they keep nothing from (round 8 repair).
            rd = provenance.reader()
            kept = {r.get("instruction", "") for r in self.rules("representation")
                    if words_held(r, rd, self.c.data)}
            out["limited_to"] = [x for x in limited if x not in kept]
        if not _caller_holds_private() or words_held(rule, None, self.c.data):
            # The words of his rule are themselves the secret ('Never tell
            # Karen about Lisa'). Only his caretaker key reads them; others
            # get the answer and the reason (family#6) — and never an AI
            # the rule holds for (S1, round 8), nor one whose words carry what
            # another of his rules keeps from it (round 8 repair).
            out.pop("rule", None)
        return out

    def guidance_for(self, tags: str | list, audience: str = SELF) -> dict:
        """The standing instructions that apply right now — reaction rules
        when speaking WITH the owner, representation rules when speaking
        ABOUT them to someone else. Returned verbatim: Jefferey follows the
        owner's words, not a paraphrase."""
        aud = audience.strip().lower()
        want = set(_tags(tags))
        rd = provenance.reader()
        held = [0]
        seen = asked_as(want, rd, self.c.data)          # round 9 repair

        def hits(kind):
            got = []
            for r in self.rules(kind):
                rt = shown_tags(r, rd, self.c.data)
                if not ((not rt or seen & set(rt))
                        and r["audience"] in (aud, ANYONE, SELF if kind == "reaction" else aud)):
                    continue
                if words_held(r, rd, self.c.data):
                    held[0] += 1         # its words carry what his rules keep from you
                    continue
                got.append(r["instruction"])
            return got

        out = {"tags": sorted(want), "audience": aud}
        if aud == SELF:
            out["react_this_way"] = hits("reaction")
            out["rule"] = ("These are the owner's own instructions for how to be with them on "
                           "this subject. Follow them exactly, even if you'd have chosen "
                           "differently. If none apply, default to the Directive Pack's voice.")
        else:
            out["disclosure"] = self.check_disclosure(aud, list(want))
            out["speak_of_them_this_way"] = self.representation_for(aud, list(want))
            out["rule"] = ("Before saying anything about the owner to this audience, obey "
                           "'disclosure'. If allowed, say it only in the way "
                           "'speak_of_them_this_way' prescribes. If nothing prescribes, say "
                           "less rather than more.")
        if held[0]:
            out["held_back"] = {"count": held[0], "why": (
                "Some of his instructions on this subject are about something his own rules "
                "keep from you, so their words are not given. Do not guess at them.")}
        return out

    def _aliases(self, audience: str) -> tuple[frozenset, frozenset]:
        """(broad, strict) names for this audience. A NO meets every person
        written down (broad); a YES only the people HE recorded or confirmed
        (strict) — a person an AI wrote down never makes a yes reach anyone
        (S3, round 8)."""
        broad, _ = grounding.audience_aliases(audience, self.c.data.get("people") or [])
        mine, strict = grounding.audience_aliases(audience, provenance.his_people(self.c.data))
        n = grounding.norm_audience
        return (frozenset(n(a) for a in broad) | frozenset(n(a) for a in mine),
                frozenset(n(a) for a in strict))

    def representation_for(self, audience: str, tags=(), text: str = "") -> list[str]:
        """How he told JEFFEREY to speak of him to this audience (or to
        anyone), on these subjects — in his own words."""
        _, strict = self._aliases(audience)
        names = set(strict) | {ANYONE}
        want = set(_tags(list(tags)))
        rd = provenance.reader()
        return [r["instruction"] for r in self.rules("representation")
                if _yes_to(r, names)
                and grounding.tag_hits(r.get("tags") or [], text or " ".join(sorted(want)), want)
                and not words_held(r, rd, self.c.data)]

    def denied_subjects(self, audience: str) -> list[str]:
        """The subjects a rule of his keeps from this audience — their names
        only, never his words (for draft_guidance's do_not_mention)."""
        broad, strict = self._aliases(audience)
        ai = grounding.names_ai(audience)
        rd = provenance.reader()
        people = self.c.data.get("people") or []
        out = []
        for r in self.rules("disclosure"):
            if r.get("allow") or not r.get("tags"):
                continue
            # a topic word his rules keep from this reader is named by its kind
            tags = shown_tags(r, rd, self.c.data)        # (round 9 repair)
            # a no meets this audience as verdict reads it — any reading of
            # its own audience, each word of it, and the person it names
            # (round 9, second repair: 'Karen' and 'Karen\u2800Novak' met
            # check_disclosure's no but not do_not_mention)
            if ai and every_ai(r, self.c.data):
                out += tags
            elif _no_aud(r, self.c.data) != ANYONE and _says_no_to(r, broad, people):
                out += tags
            elif unknown(r, self.c.data) and _says_no_to(r, broad, people):
                out += tags                      # a no nobody knows names this very one
            elif _no_aud(r, self.c.data) == ANYONE:
                # a yes for exactly this audience opens it again
                if not any(x.get("allow") and _yes_to(x, strict)
                           and set(x.get("tags") or []) & set(r["tags"])
                           for x in self.rules("disclosure")):
                    out += tags
        return sorted(set(out))

    def summary(self) -> dict:
        rs = self.c.data.get("rules", [])
        return {
            "rules": len(rs),
            "by_kind": {k: sum(1 for r in rs if r["kind"] == k) for k in KINDS},
            "included_in_conscience": len(self.c.data.get("conscience_included", [])),
            "principle": (
                "Storage is total; the conscience is curated. Over the curated self, "
                "the owner writes the rules: who may hear what, how to react to them, "
                "how to speak of them to others. Silence is a no."
            ),
        }
