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
- **Private by default — people too.** Every moment, picture and person has
  a visibility: `private` (Jefferey only, ever), `family` (may be shared with
  the family's keys), or `legacy` (meant to outlive him, and sealed until he
  releases it to the keys he names). Only the OWNER makes anything less
  private: an AI that writes a memory stores it private, whatever it asks
  for, and the owner shares it himself (/share). Anyone may make something
  more private (set_visibility).
- **His rules are enforced here, not suggested (I-10).** A family or
  executor key never sees what one of his disclosure rules keeps from it,
  nor his private notes about anyone; it is told how many things were held
  back, never what.
- **Who said it is kept (I-25).** A moment records where it came from. What
  an AI keeps is noted by the AI, not yet confirmed — never his own words by
  itself (D2, round 7): it is his words once he confirms it with his own
  hands (/confirm), or when he keeps it himself.
- **Two people can share a name (I-27).** A second Laszlo is a second
  person, never an overwrite of the first; notes are added to, never
  replaced.
- **Erasable, always — and never by accident.** Forgetting is never argued
  with, and never done on a guess: the first call shows exactly what would
  go, the second removes it, anything big waits for the owner's own hands,
  and what went can be put back for three months. Erasing words for good,
  everywhere, is the owner's own act (forgetting.py). A forgotten person is
  never asked about again.
"""

from __future__ import annotations

import time
from pathlib import Path

import forgetting
import grounding
import provenance

VISIBILITY = ("private", "family", "legacy")
PAGE, MOST = 50, 200          # moments and pictures per answer (I-41)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _key(s) -> str:
    return " ".join(grounding.words(s))


def _access():
    import access
    return access


# ------------------------------------------------- an AI never changes his people
# S3 (round 8). A person an AI writes down waits for him: kept, labelled
# 'noted by the AI, not yet confirmed by him', and never 'someone he has
# recorded' when JEFFEREY decides whom to trust. A change an AI asks for to
# someone HE recorded — a name, a relationship, notes, dates — is a proposal
# beside the person, and the person stays exactly as he left them until he
# confirms it (/pending and /confirm). Before, an AI added a 'grandson' with
# power of attorney and turned his daughter into a 'stranger'.
def describe_change(ch: dict) -> str:
    """A proposed change to a person, in plain words."""
    parts = []
    for f in ("name", "relationship"):
        if ch.get(f):
            parts.append(f"{f} to '{ch[f]}'")
    if ch.get("notes"):
        parts.append("add the notes '" + "; ".join(ch["notes"])[:160] + "'")
    if ch.get("important_dates"):
        parts.append("add the dates '" + "; ".join(ch["important_dates"])[:80] + "'")
    return "change " + ", ".join(parts) if parts else "no change"


def apply_change(p: dict, ch: dict) -> list[str]:
    """Make a change to one person: new notes and dates added, dated; a new
    name or relationship recorded with what it was, so nothing is lost."""
    changed = Life._add_to(p, "\n".join(ch.get("notes") or []),
                           "; ".join(ch.get("important_dates") or []))
    for field in ("name", "relationship"):
        new = " ".join(str(ch.get(field) or "").split())
        if new and _key(new) != _key(p.get(field)):
            was = p.get(field) or ""
            p[field] = new
            line = f"{_today()}: {field} was '{was}', now '{new}'"
            p["notes"] = (str(p.get("notes") or "") + "\n" + line).strip()
            changed.append(f"{field} ('{was}' → '{new}', kept in the notes)")
    return changed


class Life:
    """Who this person is — added by them, held for them."""

    def __init__(self, conscience):
        self.c = conscience
        self.c.data.setdefault("people", [])
        self.c.data.setdefault("memories", [])
        self.c.data.setdefault("media", [])

    # --------------------------------------------------------------- people
    @staticmethod
    def _person_out(p: dict) -> dict:
        o = {k: v for k, v in p.items() if k not in ("source", "proposed", "status")}
        if provenance.pending(p):
            o["unconfirmed"] = True
            o["noted_by"] = provenance.NOTED_BY_AI
        if isinstance(p.get("proposed"), dict):
            o["proposed_change"] = {k: v for k, v in p["proposed"].items()
                                    if k in ("name", "relationship", "notes", "important_dates")}
        return o

    def _propose(self, p: dict, name: str = "", relationship: str = "", notes: str = "",
                 dates: str = "") -> dict:
        """An AI's change to someone he recorded, kept beside them (S3)."""
        ch = p.get("proposed") if isinstance(p.get("proposed"), dict) else {}
        for field, new in (("name", name), ("relationship", relationship)):
            new = " ".join(str(new or "").split())
            if new and _key(new) != _key(p.get(field)):
                ch[field] = new
        for field, new in (("notes", notes), ("important_dates", dates)):
            new = str(new or "").strip()
            if new and _key(new) not in _key(p.get(field)) and new not in (ch.get(field) or []):
                ch.setdefault(field, []).append(new)
        if any(ch.get(f) for f in ("name", "relationship", "notes", "important_dates")):
            ch.update(source=provenance.source(text=" ".join(
                [str(name), str(relationship), str(notes), str(dates)])), at=_now())
            p["proposed"] = ch
            self.c._save()
        return {**self._person_out(p), "changed": [],
                "note": ("Nothing was changed: this is someone he recorded himself, so an AI's "
                         "change waits beside them until he confirms it (/pending, then "
                         "/confirm, in 'Talk to JEFFEREY on this Mac'). Tell him plainly what "
                         "you asked; never say it was changed.")}

    def add_person(self, name: str, relationship: str, notes: str = "",
                   important_dates: str = "") -> dict:
        """Someone who matters. Jefferey should know their name before he
        needs it — not learn it from an obituary.

        Two people may share a name (a father and a son, both Laszlo): the
        same name with a different relationship is a NEW person, reported as
        a possible duplicate, and neither is changed. The same name and
        relationship is the same person: new notes and dates are ADDED,
        dated, and nothing is replaced. The answer always says which."""
        nm = " ".join(str(name or "").split())
        rel = " ".join(str(relationship or "").split())
        notes = str(notes or "").strip()
        dates = str(important_dates or "").strip()
        if not nm:
            return {"refused": True, "tool": "add_person",
                    "reason": "A person needs a name.",
                    "tell_the_user": "Nothing was stored. Ask him for the name."}
        # He asked to forget someone by this name; saying it again on purpose
        # takes it off that list. The engine is told, so it can check.
        again = forgetting.unforget(self.c.data, nm)
        people = self.c.data["people"]
        same_name = [p for p in people if isinstance(p, dict) and _key(p.get("name")) == _key(nm)]
        same = [p for p in same_name
                if not rel or _key(p.get("relationship")) == _key(rel)]
        if len(same) > 1 and not rel:
            return {"matched_existing": False, "changed": [],
                    "possible_duplicate_of": [self._who(p) for p in same],
                    "note": (f"There is more than one {nm}. Nothing was changed. Ask him "
                             f"which one he means, then use update_person with that id.")}
        if same:
            p = same[0]
            if provenance.engine_writes() and provenance.his(p):
                out = self._propose(p, notes=notes, dates=dates)
                out["matched_existing"] = True
                return out
            changed = self._add_to(p, notes, dates)
            if changed:
                p["updated"] = _now()
                self.c._save()
            return {**self._person_out(p), "matched_existing": True,
                    "changed": changed or ["nothing — this was already known"],
                    "note": ("This is someone already known, so what was new was added "
                             "to them; nothing was replaced.")}
        src = provenance.source(text=nm)
        entry = {
            "name": nm, "relationship": rel, "notes": notes, "important_dates": dates,
            "visibility": "private", "source": src, "status": provenance.status_for(src),
            "added": _now(), "updated": _now(),
        }
        people.append(entry)
        self.c._save()
        out = {**self._person_out(entry), "matched_existing": False}
        if entry["status"] == "pending":
            out["note"] = ("Noted by the AI, not yet confirmed by him: JEFFEREY does not "
                           "count this person as someone he knows until he confirms them "
                           "himself (/pending, then /confirm, in 'Talk to JEFFEREY on this "
                           "Mac'). Tell him so.")
        if same_name:
            out["possible_duplicate_of"] = [self._who(p) for p in same_name]
            out["note"] = (
                f"There is already {self._names(same_name)}. This was kept as a separate "
                f"person, and nobody was changed. If they are in fact the same person, "
                f"ask him, and use update_person with the right id. "
                + out.get("note", "")).strip()
        if again:
            out["note"] = (out.get("note", "") + " He once asked JEFFEREY to forget someone "
                           "by this name. Make sure this is what he wants now; if not, "
                           "forget_life undoes it.").strip()
        return out

    @staticmethod
    def _who(p: dict) -> dict:
        return {"id": p.get("id"), "name": p.get("name"),
                "relationship": p.get("relationship")}

    @staticmethod
    def _names(ps: list[dict]) -> str:
        return " and ".join(f"a {p.get('name')} ({p.get('relationship') or 'no relationship given'})"
                            for p in ps)

    @staticmethod
    def _add_to(p: dict, notes: str, dates: str) -> list[str]:
        """Add new notes and dates to a person — dated, never replacing."""
        changed = []
        old = str(p.get("notes") or "")
        if notes and _key(notes) not in _key(old):
            p["notes"] = (old + "\n" if old else "") + (f"{_today()}: {notes}" if old else notes)
            changed.append("notes (added to; nothing replaced)")
        oldd = str(p.get("important_dates") or "")
        if dates and _key(dates) not in _key(oldd):
            p["important_dates"] = (oldd + "; " if oldd else "") + dates
            changed.append("important dates (added to; nothing replaced)")
        return changed

    def update_person(self, person_id: str, name: str = "", relationship: str = "",
                      notes: str = "", important_dates: str = "") -> dict:
        """Change one person, by their id. New notes and dates are added,
        dated; a new name or relationship is recorded with what it was, so
        nothing is lost."""
        pid = str(person_id or "").strip()
        p = next((x for x in self.c.data["people"]
                  if isinstance(x, dict) and x.get("id") == pid), None)
        if p is None:
            return {"refused": True, "tool": "update_person",
                    "reason": f"Nobody is recorded with the id '{pid}'.",
                    "tell_the_user": "Nothing was changed. Use an id from who_am_i."}
        if provenance.engine_writes() and provenance.his(p):
            # someone he recorded: the record stays as it is (S3)
            return self._propose(p, name, relationship, notes, important_dates)
        ch = {"name": name, "relationship": relationship,
              "notes": [str(notes).strip()] if str(notes or "").strip() else [],
              "important_dates": ([str(important_dates).strip()]
                                  if str(important_dates or "").strip() else [])}
        changed = apply_change(p, ch)
        if changed:
            p["updated"] = _now()
            self.c._save()
        return {**self._person_out(p), "changed": changed or ["nothing — this was already known"]}

    def people(self) -> list[dict]:
        return list(self.c.data.get("people", []))

    # -------------------------------------------------------------- moments
    @staticmethod
    def _kept_privately(entry: dict, asked: str) -> dict:
        """What the engine is told about a write: who may see it, whose words
        these are."""
        out = {k: v for k, v in entry.items() if k != "source"}
        notes = []
        if asked != entry["visibility"]:
            out["requested_visibility"] = asked
            notes.append(
                f"Kept private. An AI does not decide who else sees his memories: if he "
                f"wants it '{asked}', he types /share {entry.get('id')} {asked} himself in "
                f"'Talk to JEFFEREY on this Mac'.")
        if "verbatim" in entry and not entry["verbatim"]:
            notes.append("It is noted by the AI, not yet confirmed by him: an AI never "
                         "makes something his own words. Tell him plainly, and that he can "
                         "confirm it himself with /confirm in 'Talk to JEFFEREY on this Mac'.")
        if notes:
            out["note"] = " ".join(notes)
        return out

    def _engine_wrote(self) -> bool:
        return not _access().owners_hands()

    def add_memory(self, text: str, when: str = "", people: str = "",
                   tags: str = "", visibility: str = "private",
                   photos: list[str] | None = None) -> dict:
        """A snippet of a life: a moment, a turning point, a lesson, a joke
        only this family gets. This is what a story is made of.

        `photos` is a list of content hashes from the photo index — the
        pictures this story was told about. References, never copies.

        Written by an AI, it is stored private whatever visibility was asked
        (I-26), and noted by the AI, not yet confirmed — never his words until
        he confirms it with his own hands (D2, round 7)."""
        asked = str(visibility or "private").strip().lower()
        if asked not in VISIBILITY:
            raise ValueError(f"visibility must be one of {VISIBILITY}")
        body = str(text or "").strip()
        if not body:
            raise ValueError("There is nothing to keep: the moment is empty.")
        src = provenance.source(text=body)
        vis = "private" if (asked != "private" and self._engine_wrote()) else asked
        entry = {
            "text": body, "when": str(when or "").strip(),
            "people": [p.strip() for p in str(people or "").split(",") if p.strip()],
            "tags": [t.strip().lower() for t in str(tags or "").split(",") if t.strip()],
            "visibility": vis, "added": _now(), "source": src,
            # his own words only from his own hands, or his own tools on this
            # Mac with no AI in between — never because an AI says so (D2)
            "verbatim": src["stated_by"] != provenance.ENGINE,
            "status": provenance.status_for(src),
        }
        if photos:
            entry["photos"] = [str(s) for s in photos]
        if asked != vis:
            entry["requested_visibility"] = asked
        self.c.data["memories"].append(entry)
        self.c._save()
        return self._kept_privately(entry, asked)

    def add_media(self, path: str, caption: str = "", when: str = "",
                  people: str = "", visibility: str = "private") -> dict:
        """Reference a photo or recording **where it already lives** — on the
        user's Self-Cloud drive. Jefferey stores the path and the caption. He
        never copies the file, never uploads it, and if the drive is off he
        simply reports that it isn't reachable. Written by an AI, it is
        private whatever was asked (I-26)."""
        asked = str(visibility or "private").strip().lower()
        if asked not in VISIBILITY:
            raise ValueError(f"visibility must be one of {VISIBILITY}")
        p = Path(path).expanduser()
        vis = "private" if (asked != "private" and self._engine_wrote()) else asked
        entry = {
            "path": str(p), "caption": str(caption or "").strip(),
            "when": str(when or "").strip(),
            "people": [x.strip() for x in str(people or "").split(",") if x.strip()],
            "visibility": vis, "reachable": p.exists(), "added": _now(),
            "source": provenance.source(),
        }
        if asked != vis:
            entry["requested_visibility"] = asked
        self.c.data["media"].append(entry)
        self.c._save()
        out = self._kept_privately(entry, asked)
        out["note"] = ((out.get("note", "") + " ") if out.get("note") else "") + (
            "The file stays where it is — Jefferey holds a reference, not a "
            "copy. If your Self-Cloud is switched off, this simply reads as "
            "unreachable until you switch it back on.")
        return out

    def set_visibility(self, ids, visibility: str) -> dict:
        """Who may see a moment, a picture, a person or a fact. More private:
        any key that may write. Less private: the owner's own hands only
        (conscience.set_visibility)."""
        return self.c.set_visibility(ids, visibility)

    def forget_life(self, contains: str = "", ids=None, confirm: str = "") -> dict:
        """Forget a person (by exact name or id, with the moments and
        pictures that are about them alone; their name comes off the ones
        shared with others), or moments and pictures (by id, or by whole
        words in what was said about them — never by the folder a picture
        sits in). Never argued with, and never done on a guess: the first
        call shows exactly what would go and gives a one-time code; only the
        second, with the code, removes. A forgotten person is never asked
        about again. See forgetting.py."""
        return forgetting.forget_life(self.c, contains, ids, confirm)

    # ------------------------------------------------- what is for after
    def legacy_state(self) -> dict:
        d = self.c.data.get("legacy_release")
        d = d if isinstance(d, dict) else {}
        return {"released": bool(d.get("released")),
                "to": [str(x) for x in d.get("to") or []],
                "on": d.get("on"), "by": d.get("by")}

    def release_legacy(self, to) -> dict:
        """What he meant for after is opened — to the keys he names
        ('executor', 'family', 'anna'), and only by his own hands (I-10: it
        used to be readable by the family and executor keys while he was
        alive)."""
        _access().require_owners_hands("open what he meant for after")
        names = [str(x).strip().lower() for x in (to if isinstance(to, (list, tuple))
                                                  else str(to or "").replace(",", " ").split())
                 if str(x).strip()]
        if not names:
            return {"released": False, "reason": "Name who may read it (for example: executor)."}
        self.c.data["legacy_release"] = {"released": True, "to": sorted(set(names)),
                                         "on": _now(), "by": _access().who()}
        self.c._note("legacy", "What you meant for after was opened to: "
                     + ", ".join(sorted(set(names))) + ".")
        self.c._save()
        return self.legacy_state()

    def seal_legacy(self) -> dict:
        """Close it again. His own hands."""
        _access().require_owners_hands("seal what he meant for after")
        self.c.data["legacy_release"] = {"released": False, "to": [], "on": _now(),
                                         "by": _access().who()}
        self.c._note("legacy", "What you meant for after is sealed again.")
        self.c._save()
        return self.legacy_state()

    def _legacy_open_to(self, client: str, ceiling: str) -> bool:
        st = self.legacy_state()
        if not st["released"]:
            return False
        to = set(st["to"])
        return bool({"all", "everyone", client} & to) or (ceiling == "family" and "family" in to) \
            or (ceiling == "legacy" and "executor" in to and client == "executor")

    # ------------------------------------------------------------ the view
    def _view(self, ceiling: str) -> dict:
        """Who is reading, and what their key and his rules let them see."""
        rd = provenance.reader()
        client = rd["client"]
        if ceiling in ("private", "self"):
            levels = set(VISIBILITY)
        elif ceiling == "family":
            levels = {"family"} | ({"legacy"} if self._legacy_open_to(client, "family") else set())
        else:                                        # 'legacy' and anything unknown
            levels = {"legacy"} if self._legacy_open_to(client, "legacy") else set()
        # a no for any AI holds for every engine reader (D1); his rules about
        # people govern every key but his own
        aud: set = set(rd["audiences"])
        if rd.get("people_rules"):
            broad, _ = grounding.audience_aliases(client, self.c.data.get("people") or [])
            aud |= set(broad)
            if ceiling == "family":
                aud.add("family")
            if ceiling == "legacy":
                aud.add("executor")
        return {"rd": rd, "levels": levels, "audiences": aud, "ceiling": ceiling,
                "full": ceiling in ("private", "self")}

    def _rule(self, v: dict, text: str, tags) -> bool:
        if not v["audiences"]:
            return False
        import rules
        tags = list(tags) + grounding.sensitivity(text)
        return rules.held_back(self.c.data, v["audiences"], text, tags) is not None

    def _moments(self, v: dict) -> tuple[list[dict], int]:
        out, held = [], 0
        for m in self.c.data.get("memories") or []:
            if not isinstance(m, dict) or m.get("visibility", "private") not in v["levels"]:
                continue
            if self._rule(v, m.get("text", ""), list(m.get("tags") or []) + list(m.get("people") or [])):
                held += 1
                continue
            out.append(self._moment_out(m))
        return out, held

    @staticmethod
    def _moment_out(m: dict) -> dict:
        o = {k: x for k, x in m.items()
             if k not in ("source", "requested_visibility", "visibility_changed", "status")}
        if isinstance(o.get("photos"), list):
            # The photographs' fingerprints are no use to an engine and look
            # like numbers to the door (I-15): a count goes out instead. An
            # older store keeps its list on disk until the album moves it.
            o["photos"] = len(o["photos"])
        if provenance.pending(m):
            o["unconfirmed"] = True
        if "verbatim" in m and not m["verbatim"]:
            o["told_by"] = provenance.NOTED_BY_AI
        return o

    def _pictures(self, v: dict) -> tuple[list[dict], int, bool]:
        if not v["rd"]["media"]:
            return [], 0, False
        out, held = [], 0
        for m in self.c.data.get("media") or []:
            if not isinstance(m, dict) or m.get("visibility", "private") not in v["levels"]:
                continue
            if self._rule(v, m.get("caption", ""), list(m.get("people") or [])):
                held += 1
                continue
            out.append({k: x for k, x in m.items()
                        if k not in ("source", "requested_visibility", "visibility_changed")})
        return out, held, True

    def _people(self, v: dict) -> tuple[list[dict], int]:
        """Everyone, with his notes, for his own caretaker; for the family,
        only those he marked family — a name and a relationship, never his
        notes; for what is meant for after, nobody (I-10)."""
        out, held = [], 0
        if v["ceiling"] not in ("private", "self", "family"):
            return out, held
        for p in self.c.data.get("people") or []:
            if not isinstance(p, dict):
                continue
            who = f"{p.get('name', '')} {p.get('relationship', '')}"
            tags = [p.get("name", ""), p.get("relationship", "")]
            if v["full"]:
                if self._rule(v, who, tags):
                    held += 1
                    continue
                o = self._person_out(p)
                if (p.get("notes") or p.get("important_dates")) and self._rule(
                        v, f"{p.get('notes', '')} {p.get('important_dates', '')}", tags):
                    o.pop("notes", None)
                    o.pop("important_dates", None)
                    o["notes_held_back"] = True
                    held += 1
                out.append(o)
            elif p.get("visibility") == "family":
                if self._rule(v, who, tags):
                    held += 1
                    continue
                o = {"id": p.get("id"), "name": p.get("name"),
                     "relationship": p.get("relationship")}
                if provenance.pending(p):                # S3: labelled in every view
                    o.update(unconfirmed=True, noted_by=provenance.NOTED_BY_AI)
                out.append(o)
        return out, held

    def _facts(self, v: dict) -> tuple[list[dict], int]:
        if v["full"]:
            seen, held = self.c.visible_facts(v["rd"], bulk=True)
            return [self.c._fact_view(f) for f in seen], len(held)
        out, held = [], 0
        for f in self.c.data.get("facts") or []:
            if not isinstance(f, dict) or f.get("visibility") not in v["levels"]:
                continue
            if self._rule(v, f.get("fact", ""), self.c._fact_tags(f)):
                held += 1
                continue
            out.append(self.c._fact_view(f))
        return out, held

    @staticmethod
    def _paged(items: list, limit, offset, newest: bool = False) -> tuple[list, int, int]:
        """One page. `newest`: offset 0 is the most recent page (offset
        reaches further back); each page keeps the order things were told."""
        try:
            lim = int(limit) if limit is not None else PAGE
        except (TypeError, ValueError):
            lim = PAGE
        try:
            off = int(offset or 0)
        except (TypeError, ValueError):
            off = 0
        lim, off = max(1, min(MOST, lim)), max(0, off)
        if newest:
            end = max(0, len(items) - off)
            page = items[max(0, end - lim):end]
        else:
            page = items[off:off + lim]
        return page, max(0, len(items) - off - lim), off + lim

    def _sealed_note(self, v: dict) -> str | None:
        if v["full"] or "legacy" in v["levels"]:
            return None
        return ("What he meant for after is sealed until he opens it himself, to the "
                "people he names. Do not guess at it.")

    def who_am_i(self, ceiling: str, limit=None, offset=0) -> dict:
        """What Jefferey understands about this person as a human being —
        not as a set of preferences.

        `ceiling` has no default on purpose: it comes from the bound client's
        key (`access.ceiling()`), never from a caller's choice. An unknown
        value falls to `legacy` — the narrowest, not the widest. His own
        disclosure rules apply on top, to every reader but himself; what
        they hold back is counted, never shown. The most recent moments first, a page
        at a time (I-41)."""
        v = self._view(ceiling)
        mems, h1 = self._moments(v)
        pics, h2, media_ok = self._pictures(v)
        people, h3 = self._people(v)
        facts, h4 = self._facts(v)
        # his values, past his own rules (F2, round 8)
        shown, h5 = self.c.visible_priorities(v["rd"])
        prios = sorted(shown, key=lambda p: -float(p.get("confidence") or 0))[:8]
        mems_page, more_m, next_m = self._paged(mems, limit, offset, newest=True)
        pics_page, more_p, _ = self._paged(pics, limit, offset, newest=True)
        facts_page, more_f, _ = self._paged(facts, limit, offset, newest=True)
        out = {
            "people_who_matter": people,
            "moments": mems_page,
            "pictures_and_recordings": pics_page,
            "what_they_value": [
                f"{p.get('higher')} over {p.get('lower')} ({p.get('context')}, "
                f"{int(float(p.get('confidence') or 0) * 100)}% confident)" for p in prios
            ] if v["full"] else [],
            "facts": facts_page,
            # counted within what this key may see (privacy#4)
            "depth": {
                "people": len(people),
                "moments": len(mems),
                "media": len(pics),
                "values_learned": len(self.c.data.get("priorities", [])) if v["full"] else 0,
            },
            "rule": (
                "This is a person, not a profile. Speak about them the way a "
                "close friend would — specifically, warmly, and only from what "
                "is actually here. Never invent a memory, a relationship, or a "
                "feeling they did not record. A moment marked as told in an AI's "
                "words is not his own wording."
            ),
        }
        self._finish(out, v, h1 + h2 + h3 + h4 + (h5 if v["full"] else 0), media_ok,
                     more=more_m + more_p + more_f, next_offset=next_m)
        return out

    def _finish(self, out: dict, v: dict, held: int, media_ok: bool, more: int,
                next_offset: int) -> None:
        notes = []
        if held:
            out["held_back"] = {"count": held, "why": (
                "Some things are kept from this connection by his own rules, or are "
                "private. Do not guess at them, and do not ask him to read them to you.")}
        if not media_ok:
            notes.append("This key may not see his pictures and recordings.")
        sealed = self._sealed_note(v)
        if sealed:
            out["legacy"] = sealed
        if more:
            out["more"] = more
            out["how_to_see_more"] = f"Call again with offset={next_offset}."
        if notes:
            out["note"] = " ".join(notes)

    def tell_story(self, ceiling: str, theme: str = "", limit=None, offset=0) -> dict:
        """Gather what's relevant to tell a piece of this person's story —
        for them now, or for the people they name, later.

        `ceiling` comes from the bound client's key, never from an argument
        the model picks. Unknown values fall to `legacy`. A theme is matched
        by whole words ('art' is not 'heart'); a theme nothing matches says
        so instead of returning everything. A theme is a search (G2, round
        9): it reads only what would leave the house, and a key paused for
        searching that finds nothing is refused."""
        t = str(theme or "").strip()
        if t:
            paused = self.c.search_paused("tell_story")
            if paused:
                return paused
        v = self._view(ceiling)
        mems, h1 = self._moments(v)
        pics, h2, media_ok = self._pictures(v)
        people, h3 = self._people(v)
        nothing = None
        if t:
            tw = grounding.expand(grounding.content(t))
            tkey = _key(t)

            def hit(text, tags, names):
                if tkey and any(_key(n) == tkey for n in names):
                    return True
                # only what would leave the house is searched (F3, round 8)
                have = grounding.content(self.c.searched(text, v["rd"])) | {
                    grounding.stem(x) for g in tags
                                                  for x in grounding.words(g)}
                have |= {grounding.stem(x) for n in names for x in grounding.words(n)}
                return bool(tw & have)

            mems = [m for m in mems if hit(m.get("text", ""), m.get("tags", []),
                                           m.get("people", []))]
            pics = [m for m in pics if hit(m.get("caption", ""), [], m.get("people", []))]
            self.c.search_found(bool(mems or pics))
            if not mems and not pics:
                nothing = (f"Nothing recorded yet matches '{t}'. Say so honestly, and "
                           "ask him if he would like to tell it.")
        mems = sorted(mems, key=lambda m: str(m.get("when", "")))
        mems_page, more_m, next_m = self._paged(mems, limit, offset)
        pics_page, more_p, _ = self._paged(pics, limit, offset)
        out = {
            "theme": t or "their life",
            "visible_at": ceiling,
            "moments": mems_page,
            "pictures": pics_page,
            "people": people,
            "how_to_tell_it": (
                "Tell it in their voice, in order, using only what is here. Name "
                "the people by name. Where a picture belongs, say which one and "
                "why. If the record is thin, say so honestly and ask them to add "
                "more while they can — that is the whole reason this exists."
            ),
        }
        self._finish(out, v, h1 + h2 + h3, media_ok, more=more_m + more_p,
                     next_offset=next_m)
        if nothing:
            out["note"] = (out.get("note", "") + " " + nothing).strip()
        return out

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
        # Someone he asked to forget is never asked about again.
        gone = forgetting.forgotten(self.c.data)
        named = {p["name"].lower() for p in people}
        mentioned = {n.lower() for m in mems for n in m.get("people", [])}
        for n in sorted(mentioned - named):
            if forgetting.name_key(n) in gone:
                continue
            gaps.append(f"'{n}' appears in a memory but isn't recorded as a person — who are they?")
        for p in people:
            if forgetting.name_key(p["name"]) in gone:
                continue
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
