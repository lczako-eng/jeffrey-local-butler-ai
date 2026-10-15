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
# word, an AI word) holds for everyone AND every AI, his own JEFFEREY too
# (grounding.unknown_parts). 'my lawyer', 'Bob', 'Le Monde' and 'the press'
# used to bind only a reader of that very name — in practice nobody. Once he
# records who they are at his own console, the no binds only them; a person
# an AI wrote down never makes a no narrower. A yes never widens past what
# is written.
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


def _no_aud(r: dict, data: dict | None = None) -> str:
    """Who a rule that says NO is for: its own audience, or everyone when it
    says so with an anyone-word ('members of the public', 'nobody but my
    doctor', 'les gens', 'le monde') — or when nobody knows who it is (F1,
    round 8: 'Bob', 'my GP' and 'Le Monde' are each only themselves once he
    has recorded who they are)."""
    if grounding.is_anyone(_written(r)) or unknown(r, data):
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
    """Does this NO hold for every AI: it names one, or nobody knows who its
    audience is (F1)?"""
    return names_ai(r) or bool(unknown(r, data))


def describe(r: dict, data: dict | None = None) -> tuple[str, str]:
    """(whom a rule that says NO holds for, the note that says so in plain
    words) — the same on every surface."""
    said = _written(r)
    nobody = unknown(r, data)
    everyone, ai = _no_aud(r, data) == ANYONE, every_ai(r, data)
    if nobody:
        who = (" and ".join(f"'{x}'" for x in nobody))
        are = "is" if len(nobody) == 1 else "are"
        return ("everyone and every AI",
                f"I don't know who {who} {are}, so this no holds for everyone and every AI. "
                f"Add them to your people to make it narrower. Only you, reading at your own "
                f"keyboard, still see it.")
    if ai:
        return ("everyone and every AI" if everyone else "every AI",
                f"'{said}' names an AI, so this no holds for every AI that reads your "
                "memories — Claude, ChatGPT, a model on this Mac, and your own JEFFEREY too"
                + (", and for every person as well" if everyone else "")
                + ". Only you, reading at your own keyboard, still see it.")
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
    the family (D1)."""
    a = _aud(r)
    if a in names:
        return True
    if "family" in names and grounding.names_family(_written(r)):
        return True
    return bool(grounding.rule_names(r.get("audience", ""), people) & set(names))


def _ai_no(data: dict, hit) -> dict | None:
    """The first rule that says NO to every AI — it names one, or nobody
    knows its audience (F1) — about whatever `hit` reaches."""
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
        yes = [r for r in disc if r.get("allow") and _aud(r) in names_yes]
        if yes:
            return True, yes[0], []
        say = [r for r in reps if _aud(r) in names_yes]
        if say:
            return True, say[0], [r.get("instruction", "") for r in say]
    return None, None, []


# The far end of a connection — the engine's maker — is one reader; the key
# holder (the family, the executor, a named key) is another. Every key that
# reaches an engine carries grounding.AI_READER in its audiences (D1): then
# every no that names an AI holds for it.
VENDOR_NAMES = frozenset({"ai", "an ai", "any ai", "engines", "engine", "ais", "anthropic",
                          "claude", "openai", "chatgpt", "gpt", grounding.AI_READER})


def held_back(data: dict, audiences, text: str = "", tags=()) -> dict | None:
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
    reaches one, his caretaker key too, whatever yes there is."""
    aud = frozenset(grounding.norm_audience(a) for a in audiences or () if a)
    if not aud:
        return None
    hit = lambda r: grounding.tag_hits(r.get("tags") or [], text, tags)  # noqa: E731
    if aud & VENDOR_NAMES:
        rule = _ai_no(data, hit)
        if rule:
            return rule
    people = aud - VENDOR_NAMES
    if people:
        ok, rule, _ = verdict(data, people, people, hit)
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
    names = frozenset(grounding.norm_audience(a) for a in aud) - VENDOR_NAMES
    if not r.get("allow") and _no_aud(r, data) == ANYONE:
        return True
    return _aud(r) in names or (not r.get("allow") and _says_no_to(
        r, names, (data or {}).get("people") or []))


def held_for_reader(r: dict, rd: dict | None = None, data: dict | None = None) -> dict:
    """A rule as a reader it binds may see it: what it is about, whom it is
    for, yes or no — never his sentence (S1)."""
    v = {k: r[k] for k in ("id", "kind", "tags", "audience", "allow", "added") if k in r}
    if r.get("kind") == "disclosure" and not r.get("allow"):
        v["holds_for"] = describe(r, data)[0]
    v["instruction_held_back"] = True
    v["note"] = ("His own words for this rule are not given to an AI it holds for — only "
                 "what it is about, whom it is for, and whether it is a yes or a no. Obey "
                 "it; never ask him to read it to you.")
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
                 audience: str = SELF, allow: bool = True) -> dict:
        """Write one rule in the owner's own words.

        kind       'disclosure' | 'reaction' | 'representation'
        tags       what it's about: 'health', 'father', 'money', 'karen' ...
        audience   who it concerns: 'me' (the owner), 'anyone', or a named
                   person/group ('karen', 'family', 'my doctor')
        allow      for disclosure rules only: True = may share with this
                   audience, False = must not
        instruction  the rule itself, verbatim — this is what Jefferey obeys
        """
        kind = kind.strip().lower()
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        written = " ".join(str(audience or "").split())
        rule = {
            "id": f"r{int(time.time() * 1000) % 10_000_000}",
            "kind": kind,
            "tags": _tags(tags),
            "audience": written.lower() or SELF,
            "allow": bool(allow),
            "instruction": instruction.strip(),
            "added": _now(),
        }
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
        plan = forgetting.plan_rules(self.c, rule_id_or_text)
        if isinstance(plan, str):
            return forgetting.refusal("remove_rule", plan)
        if not plan.changes:
            return {"step": "nothing", "count": 0, "removed": 0,
                    "note": "Nothing matched, so nothing was asked for. Words match whole "
                            "words; a rule can also be named by its id (list_rules)."}
        src = provenance.source(text=str(rule_id_or_text or ""))
        props = self.c.data.setdefault("rule_proposals", [])
        ids, rows = [], []
        rd = provenance.reader()
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
            seen = held_for_reader(r, rd, self.c.data) if binds(r, rd, self.c.data) else r
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
        To an engine a rule holds for, never his sentence (S1, round 8); an
        AI's note is labelled, and what an AI proposed is listed apart."""
        rd = provenance.reader()
        out = []
        for r in self.rules(kind):
            v = (held_for_reader(r, rd, self.c.data) if binds(r, rd, self.c.data)
                 else self._as_read(r))
            v = {k: x for k, x in v.items() if k not in ("source", "status")}
            if provenance.pending(r):
                v.update(status="pending", noted_by=provenance.NOTED_BY_AI)
            out.append(v)
        for p in self.c.data.get("rule_proposals") or []:
            if not isinstance(p, dict):
                continue
            r = p.get("rule") if isinstance(p.get("rule"), dict) else {}
            if kind and r.get("kind") != kind.lower():
                continue
            out.append({"id": p.get("id"), "kind": r.get("kind"), "tags": r.get("tags"),
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
        if grounding.norm_audience(aud) == SELF:
            return {"allowed": True, "audience": aud, "reason": "the owner may always hear about themself"}
        # 'Karen Novak <k@example.com>' meets a rule for 'karen' (I-24: only
        # the exact string used to match, so a 'never tell Karen' rule let
        # her full name through to an 'anyone' allow).
        broad, strict = self._aliases(aud)
        text = " ".join(sorted(want))

        def on_topic(r):
            return grounding.tag_hits(r.get("tags") or [], text, want)

        if grounding.names_ai(audience):
            # a no that names any AI holds for every AI (D1)
            no = _ai_no(self.c.data, on_topic)
            if no:
                out = {"allowed": False, "audience": aud, "tags": sorted(want),
                       "reason": "the owner forbade it", "rule": no.get("instruction", "")}
                if not _caller_holds_private() or binds(no, None, self.c.data):
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
            # owner's permission to say exactly that much — and no more.
            out["limited_to"] = limited
        if not _caller_holds_private() or binds(rule, None, self.c.data):
            # The words of his rule are themselves the secret ('Never tell
            # Karen about Lisa'). Only his caretaker key reads them; others
            # get the answer and the reason (family#6) — and never an AI
            # the rule holds for (S1, round 8).
            out.pop("rule", None)
        return out

    def guidance_for(self, tags: str | list, audience: str = SELF) -> dict:
        """The standing instructions that apply right now — reaction rules
        when speaking WITH the owner, representation rules when speaking
        ABOUT them to someone else. Returned verbatim: Jefferey follows the
        owner's words, not a paraphrase."""
        aud = audience.strip().lower()
        want = set(_tags(tags))

        def hits(kind):
            return [r["instruction"] for r in self.rules(kind)
                    if (not r["tags"] or want & set(r["tags"]))
                    and r["audience"] in (aud, ANYONE, SELF if kind == "reaction" else aud)]

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
        return [r["instruction"] for r in self.rules("representation")
                if _aud(r) in names
                and grounding.tag_hits(r.get("tags") or [], text or " ".join(sorted(want)), want)]

    def denied_subjects(self, audience: str) -> list[str]:
        """The subjects a rule of his keeps from this audience — their names
        only, never his words (for draft_guidance's do_not_mention)."""
        broad, strict = self._aliases(audience)
        ai = grounding.names_ai(audience)
        out = []
        for r in self.rules("disclosure"):
            if r.get("allow") or not r.get("tags"):
                continue
            if ai and every_ai(r, self.c.data):
                out += r["tags"]
            elif _no_aud(r, self.c.data) != ANYONE and (
                    _aud(r) in broad or "family" in broad and grounding.names_family(_written(r))):
                out += r["tags"]
            elif unknown(r, self.c.data) and _aud(r) in broad:
                out += r["tags"]                 # a no nobody knows names this very one
            elif _no_aud(r, self.c.data) == ANYONE:
                # a yes for exactly this audience opens it again
                if not any(x.get("allow") and _aud(x) in strict
                           and set(x.get("tags") or []) & set(r["tags"])
                           for x in self.rules("disclosure")):
                    out += r["tags"]
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
