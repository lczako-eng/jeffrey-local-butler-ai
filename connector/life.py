"""
JEFFEREY — the life layer of the Digital Conscience
===================================================

The founder's term, and the point of the whole system: a **Digital
Conscience** doesn't just learn how you decide — it learns *who you are*.

Priorities tell Jefferey how to represent you in a decision. This layer tells
him who he is representing: the people you love, the moments that made you,
the photographs sitting in your Self-Cloud, the things you'd want said about
you one day. It is what makes him a companion rather than a calculator, and
it is what lets him **tell your story down the road** — priority 07, Digital
Inheritance, starting to grow now instead of after it's too late.

Design rules — these are the sensitive ones, so they are strict:

- **Snippets, not surveillance.** Nothing enters here unless the person
  deliberately adds it. Jefferey never scrapes a life together on his own.
- **Photos stay where they live.** Media is stored as a *path* into the
  user's own Self-Cloud drive — a caption and a reference, never a copy,
  never an upload. If the drive is switched off, the pictures simply aren't
  there, which is exactly the point.
- **Private by default.** Every entry has a visibility: `private` (Jefferey
  only, ever), `family` (may be shared with named people), or `legacy`
  (intended to outlive the user and be told to those they name).
- **Erasable, always.** One call removes anything, and it is never argued
  with.
"""

from __future__ import annotations

import time
from pathlib import Path

VISIBILITY = ("private", "family", "legacy")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Life:
    """Who this person is — added by them, held for them."""

    def __init__(self, conscience):
        self.c = conscience
        self.c.data.setdefault("people", [])
        self.c.data.setdefault("memories", [])
        self.c.data.setdefault("media", [])

    # --------------------------------------------------------------- people
    def add_person(self, name: str, relationship: str, notes: str = "",
                   important_dates: str = "") -> dict:
        """Someone who matters. Jefferey should know their name before he
        needs it — not learn it from an obituary."""
        existing = next(
            (p for p in self.c.data["people"] if p["name"].lower() == name.strip().lower()),
            None)
        if existing:
            existing.update(relationship=relationship or existing["relationship"],
                            notes=notes or existing.get("notes", ""),
                            important_dates=important_dates or existing.get("important_dates", ""),
                            updated=_now())
            self.c._save()
            return existing
        entry = {
            "name": name.strip(), "relationship": relationship.strip(),
            "notes": notes.strip(), "important_dates": important_dates.strip(),
            "added": _now(), "updated": _now(),
        }
        self.c.data["people"].append(entry)
        self.c._save()
        return entry

    def people(self) -> list[dict]:
        return list(self.c.data.get("people", []))

    # -------------------------------------------------------------- moments
    def add_memory(self, text: str, when: str = "", people: str = "",
                   tags: str = "", visibility: str = "private") -> dict:
        """A snippet of a life: a moment, a turning point, a lesson, a joke
        only this family gets. This is what a story is made of."""
        if visibility not in VISIBILITY:
            raise ValueError(f"visibility must be one of {VISIBILITY}")
        entry = {
            "text": text.strip(), "when": when.strip(),
            "people": [p.strip() for p in people.split(",") if p.strip()],
            "tags": [t.strip().lower() for t in tags.split(",") if t.strip()],
            "visibility": visibility, "added": _now(),
        }
        self.c.data["memories"].append(entry)
        self.c._save()
        return entry

    def add_media(self, path: str, caption: str = "", when: str = "",
                  people: str = "", visibility: str = "private") -> dict:
        """Reference a photo or recording **where it already lives** — on the
        user's Self-Cloud drive. Jefferey stores the path and the caption. He
        never copies the file, never uploads it, and if the drive is off he
        simply reports that it isn't reachable."""
        if visibility not in VISIBILITY:
            raise ValueError(f"visibility must be one of {VISIBILITY}")
        p = Path(path).expanduser()
        entry = {
            "path": str(p), "caption": caption.strip(), "when": when.strip(),
            "people": [x.strip() for x in people.split(",") if x.strip()],
            "visibility": visibility, "reachable": p.exists(), "added": _now(),
        }
        self.c.data["media"].append(entry)
        self.c._save()
        return {
            **entry,
            "note": ("The file stays where it is — Jefferey holds a reference, not a "
                     "copy. If your Self-Cloud is switched off, this simply reads as "
                     "unreachable until you switch it back on."),
        }

    def forget_life(self, contains: str) -> dict:
        """Erase anything in the life layer matching this text. Never argued
        with, never questioned."""
        c = contains.lower()
        before = (len(self.c.data["memories"]), len(self.c.data["media"]),
                  len(self.c.data["people"]))
        self.c.data["memories"] = [m for m in self.c.data["memories"] if c not in m["text"].lower()]
        self.c.data["media"] = [m for m in self.c.data["media"]
                                if c not in (m["caption"] + " " + m["path"]).lower()]
        self.c.data["people"] = [p for p in self.c.data["people"] if c not in p["name"].lower()]
        self.c._save()
        after = (len(self.c.data["memories"]), len(self.c.data["media"]),
                 len(self.c.data["people"]))
        return {"memories_removed": before[0] - after[0],
                "media_removed": before[1] - after[1],
                "people_removed": before[2] - after[2]}

    # ------------------------------------------------------------ the story
    def who_am_i(self, include: str = "private") -> dict:
        """What Jefferey understands about this person as a human being —
        not as a set of preferences."""
        allowed = {"private": VISIBILITY, "family": ("family", "legacy"),
                   "legacy": ("legacy",)}.get(include, ("legacy",))
        mems = [m for m in self.c.data["memories"] if m["visibility"] in allowed]
        media = [m for m in self.c.data["media"] if m["visibility"] in allowed]
        prios = sorted(self.c.data.get("priorities", []),
                       key=lambda p: -p.get("confidence", 0))[:8]
        return {
            "people_who_matter": self.c.data.get("people", []),
            "moments": mems,
            "pictures_and_recordings": media,
            "what_they_value": [
                f"{p['higher']} over {p['lower']} ({p['context']}, "
                f"{int(p['confidence'] * 100)}% confident)" for p in prios
            ],
            "facts": self.c.data.get("facts", []),
            "depth": {
                "people": len(self.c.data.get("people", [])),
                "moments": len(self.c.data.get("memories", [])),
                "media": len(self.c.data.get("media", [])),
                "values_learned": len(self.c.data.get("priorities", [])),
            },
            "rule": (
                "This is a person, not a profile. Speak about them the way a "
                "close friend would — specifically, warmly, and only from what "
                "is actually here. Never invent a memory, a relationship, or a "
                "feeling they did not record."
            ),
        }

    def tell_story(self, theme: str = "", audience: str = "family") -> dict:
        """Gather what's relevant to tell a piece of this person's story —
        for them now, or for the people they name, later."""
        allowed = {"self": VISIBILITY, "family": ("family", "legacy"),
                   "legacy": ("legacy",)}.get(audience, ("legacy",))
        t = theme.lower().strip()
        mems = [m for m in self.c.data["memories"] if m["visibility"] in allowed]
        media = [m for m in self.c.data["media"] if m["visibility"] in allowed]
        if t:
            def hit(m):
                return (t in m.get("text", "").lower()
                        or t in " ".join(m.get("tags", []))
                        or any(t in p.lower() for p in m.get("people", [])))
            mems = [m for m in mems if hit(m)] or mems
            media = [m for m in media
                     if t in m.get("caption", "").lower()
                     or any(t in p.lower() for p in m.get("people", []))] or media
        mems = sorted(mems, key=lambda m: m.get("when", ""))
        return {
            "theme": theme or "their life",
            "audience": audience,
            "moments": mems,
            "pictures": media,
            "people": self.c.data.get("people", []),
            "how_to_tell_it": (
                "Tell it in their voice, in order, using only what is here. Name "
                "the people by name. Where a picture belongs, say which one and "
                "why. If the record is thin, say so honestly and ask them to add "
                "more while they can — that is the whole reason this exists."
            ),
        }

    def story_gaps(self) -> dict:
        """What's missing — so Jefferey can gently ask for it while there's
        still time to ask."""
        people = self.c.data.get("people", [])
        mems = self.c.data.get("memories", [])
        gaps = []
        if not people:
            gaps.append("Nobody is recorded yet. Who are the people that matter most?")
        if not mems:
            gaps.append("No moments recorded. What's a day you'd want remembered?")
        named = {p["name"].lower() for p in people}
        mentioned = {n.lower() for m in mems for n in m.get("people", [])}
        for n in sorted(mentioned - named):
            gaps.append(f"'{n}' appears in a memory but isn't recorded as a person — who are they?")
        for p in people:
            if not any(p["name"].lower() in {x.lower() for x in m.get("people", [])} for m in mems):
                gaps.append(f"Nothing recorded yet about {p['name']} ({p['relationship']}).")
        if not any(m["visibility"] == "legacy" for m in mems):
            gaps.append("Nothing marked 'legacy' yet — what should outlive you?")
        return {
            "gaps": gaps[:10],
            "rule": (
                "Ask for at most one of these at a time, and only when the moment "
                "is right. This is a life being written down, not a form being "
                "completed. Never pressure them."
            ),
        }
