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

import time

KINDS = ("disclosure", "reaction", "representation")

# Audiences a rule can name. Anything else is treated as a named person or
# group (e.g. "karen", "family", "my sister") and matched by exact word.
SELF = "me"
ANYONE = "anyone"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _tags(s: str | list) -> list[str]:
    if isinstance(s, list):
        return [str(t).strip().lower() for t in s if str(t).strip()]
    return [t.strip().lower() for t in str(s).split(",") if t.strip()]


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

    def exclude(self, contains: str) -> dict:
        """Take something back out of the conscience. It stays on Self-Cloud;
        Jefferey simply no longer holds it as part of who they are."""
        c = contains.lower()
        before = len(self.c.data["conscience_included"])
        self.c.data["conscience_included"] = [
            e for e in self.c.data["conscience_included"] if c not in e["ref"].lower()]
        self.c._save()
        return {"excluded": before - len(self.c.data["conscience_included"])}

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
        rule = {
            "id": f"r{int(time.time() * 1000) % 10_000_000}",
            "kind": kind,
            "tags": _tags(tags),
            "audience": audience.strip().lower() or SELF,
            "allow": bool(allow),
            "instruction": instruction.strip(),
            "added": _now(),
        }
        self.c.data["rules"].append(rule)
        self.c._save()
        return rule

    def remove_rule(self, rule_id_or_text: str) -> dict:
        """Delete a rule by id or by any text it contains. Never argued with."""
        key = rule_id_or_text.strip().lower()
        before = len(self.c.data["rules"])
        self.c.data["rules"] = [
            r for r in self.c.data["rules"]
            if r["id"] != key and key not in r["instruction"].lower()
            and key not in " ".join(r["tags"])]
        self.c._save()
        return {"removed": before - len(self.c.data["rules"])}

    def rules(self, kind: str = "") -> list[dict]:
        rs = self.c.data.get("rules", [])
        return [r for r in rs if not kind or r["kind"] == kind.lower()]

    # ------------------------------------------------------------ enforcement
    def check_disclosure(self, audience: str, tags: str | list) -> dict:
        """May this be said to this audience? Called BEFORE speaking about the
        person to anyone who is not them.

        Logic: the owner themself may always hear anything. For everyone
        else: a matching DENY rule wins outright; otherwise an explicit ALLOW
        for this audience (or for 'anyone') is required; otherwise refuse.
        Silence is a 'no'.
        """
        aud = audience.strip().lower()
        want = set(_tags(tags))
        if aud == SELF:
            return {"allowed": True, "audience": aud, "reason": "the owner may always hear about themself"}

        def on_topic(r):
            return not r["tags"] or want & set(r["tags"])

        # Precedence: a rule naming THIS audience beats a rule for "anyone".
        # Within the same level, deny beats allow.
        for level in (aud, ANYONE):
            here = [r for r in self.rules("disclosure") if on_topic(r) and r["audience"] == level]
            denies = [r for r in here if not r["allow"]]
            allows = [r for r in here if r["allow"]]
            if denies:
                return {"allowed": False, "audience": aud, "tags": sorted(want),
                        "reason": "the owner forbade it", "rule": denies[0]["instruction"]}
            if allows:
                return {"allowed": True, "audience": aud, "tags": sorted(want),
                        "reason": "the owner permitted it", "rule": allows[0]["instruction"]}
            # A representation rule ("to others, say I'm retired") IS the
            # owner's permission to say exactly that much — and no more.
            reps = [r for r in self.rules("representation") if on_topic(r) and r["audience"] == level]
            if reps:
                return {"allowed": True, "audience": aud, "tags": sorted(want),
                        "reason": "the owner told you what to say — say only that",
                        "rule": reps[0]["instruction"], "limited_to": [r["instruction"] for r in reps]}

        return {"allowed": False, "audience": aud, "tags": sorted(want),
                "reason": ("no rule opens this to this audience — silence is a no. "
                           "Say nothing about it, and if pressed, say it isn't yours to share.")}

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
            out["speak_of_them_this_way"] = [
                r["instruction"] for r in self.rules("representation")
                if (not r["tags"] or want & set(r["tags"])) and r["audience"] in (aud, ANYONE)]
            out["rule"] = ("Before saying anything about the owner to this audience, obey "
                           "'disclosure'. If allowed, say it only in the way "
                           "'speak_of_them_this_way' prescribes. If nothing prescribes, say "
                           "less rather than more.")
        return out

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
