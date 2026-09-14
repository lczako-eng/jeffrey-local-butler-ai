#!/usr/bin/env python3
"""
recall.py — "show me the part of me that was on vacation ten years ago in Cuba"
==============================================================================

The question in that sentence has three separate parts, and only one of them
needs a neural network:

    "ten years ago"   a date       -> EXIF DateTimeOriginal      (plain code)
    "in Cuba"         a place      -> EXIF GPS + offline lookup  (plain code)
    "on vacation"     a feeling    -> CLIP embedding             (small model)

So this module is mostly arithmetic. It parses a spoken sentence into a
`Recall` — a time window, a set of places, and whatever words are left over —
then hands the leftovers to the photo index's semantic search and intersects
the results.

Everything is local. The place lookup uses a bundled offline city database
(`reverse_geocoder`); nothing here ever touches the network, which is the
whole point: your holiday in Cuba is not a search query anybody else gets to
see.

    python tools/recall.py "vacation ten years ago in Cuba"
    python tools/recall.py "christmas at the kitchen table" --top 30
    python tools/recall.py --explain "summer 2015 in Toronto with mum"

Use it as a library from the connector:

    from recall import parse, run
    hits = run(index, parse("that trip to Cuba"), embedder)
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------- vocabulary
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})

# Northern-hemisphere seasons. The owner is in Canada; if this ever ships
# south of the equator it needs to flip, so it is one table, not scattered.
SEASONS = {
    "winter": (12, 2), "spring": (3, 5), "summer": (6, 8),
    "fall": (9, 11), "autumn": (9, 11),
}

# Dates people say out loud that aren't dates.
OCCASIONS = {
    "christmas": (12, 20, 12, 27), "xmas": (12, 20, 12, 27),
    "new year": (12, 30, 1, 2), "new years": (12, 30, 1, 2),
    "halloween": (10, 28, 11, 1),
    "thanksgiving": (10, 5, 10, 15),      # Canadian
}

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "a": 1,
}

# Words that carry no meaning for a photo search. Stripped before the
# semantic pass so "show me the part of me that was on vacation" becomes
# "vacation".
NOISE = {
    "show", "me", "the", "part", "of", "that", "was", "were", "is", "are",
    "a", "an", "my", "our", "we", "i", "in", "on", "at", "to", "from",
    "find", "get", "pull", "up", "bring", "when", "where", "what", "hey",
    "jefferey", "jeffery", "please", "some", "any", "all", "photos",
    "photo", "pictures", "picture", "pics", "images", "back", "again",
    "remember", "recall", "with", "and", "it", "its", "there", "those",
    "these", "this", "time", "trip", "look", "see", "let", "us",
}


@dataclass
class Recall:
    """A spoken sentence, taken apart."""
    said: str
    since: dt.date | None = None
    until: dt.date | None = None
    places: list[str] = field(default_factory=list)
    semantic: str = ""
    notes: list[str] = field(default_factory=list)

    def describe(self) -> str:
        bits = []
        if self.since or self.until:
            bits.append(f"between {self.since} and {self.until}")
        if self.places:
            bits.append("in " + " or ".join(self.places))
        if self.semantic:
            bits.append(f'that look like "{self.semantic}"')
        return "photos " + (", ".join(bits) if bits else "(everything)")


# -------------------------------------------------------------------- time
def _year_window(year: int) -> tuple[dt.date, dt.date]:
    return dt.date(year, 1, 1), dt.date(year, 12, 31)


def _month_window(year: int, m1: int, m2: int) -> tuple[dt.date, dt.date]:
    """A month range, handling the winter case that wraps the new year."""
    if m1 <= m2:
        return dt.date(year, m1, 1), dt.date(year, m2, calendar.monthrange(year, m2)[1])
    return dt.date(year - 1, m1, 1), dt.date(year, m2, calendar.monthrange(year, m2)[1])


def parse_time(text: str, today: dt.date) -> tuple[dt.date | None, dt.date | None, str]:
    """Pull a date range out of the sentence and return it with the words
    that were consumed removed. Deliberately generous: "ten years ago" means
    that whole year, not that day — nobody remembers a date, they remember
    a summer."""
    t = f" {text.lower()} "
    since = until = None
    year = None

    # "in 2015", "2015"
    m = re.search(r"\b(19\d{2}|20\d{2})\b", t)
    if m:
        year = int(m.group(1))
        t = t.replace(m.group(0), " ", 1)

    # "ten years ago", "3 yrs ago", "a year ago"
    m = re.search(r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\s+(?:years?|yrs?)\s+ago\b", t)
    if m and year is None:
        n = m.group(1)
        n = int(n) if n.isdigit() else NUMBER_WORDS[n]
        year = today.year - n
        t = t[:m.start()] + " " + t[m.end():]

    # "last year", "this year"
    if year is None and " last year " in t:
        year = today.year - 1
        t = t.replace(" last year ", " ")
    if year is None and " this year " in t:
        year = today.year
        t = t.replace(" this year ", " ")

    # an occasion — christmas, new year
    for word, (m1, d1, m2, d2) in OCCASIONS.items():
        if f" {word} " in t:
            y = year or today.year
            since = dt.date(y if m1 <= m2 else y - 1, m1, d1)
            until = dt.date(y, m2, d2)
            t = t.replace(f" {word} ", " ")
            return since, until, t.strip()

    # a season — "summer 2015", "last summer"
    for word, (m1, m2) in SEASONS.items():
        if f" {word} " in t:
            y = year or today.year
            if year is None and f" last {word} " in t:
                y = today.year - 1
            since, until = _month_window(y, m1, m2)
            t = re.sub(rf"\b(last\s+)?{word}\b", " ", t)
            return since, until, t.strip()

    # a named month — "june 2015", "in june"
    for word, num in MONTHS.items():
        if re.search(rf"\b{word}\b", t):
            y = year or today.year
            since = dt.date(y, num, 1)
            until = dt.date(y, num, calendar.monthrange(y, num)[1])
            t = re.sub(rf"\b{word}\b", " ", t, count=1)
            return since, until, t.strip()

    if year is not None:
        since, until = _year_window(year)
    return since, until, t.strip()


# ------------------------------------------------------------------- place
def parse_place(text: str, known: set[str]) -> tuple[list[str], str]:
    """Match place words against the places this person ACTUALLY has photos
    of. That is the trick: no gazetteer of the whole world, no ambiguity
    about which Springfield — just the handful of places in their own life.
    Longest match first, so 'New York' beats 'York'."""
    found, t = [], text.lower()
    for place in sorted(known, key=len, reverse=True):
        p = place.lower()
        if len(p) < 3:
            continue
        if re.search(rf"\b{re.escape(p)}\b", t):
            found.append(place)
            t = re.sub(rf"\b{re.escape(p)}\b", " ", t)
    return found, t.strip()


# ------------------------------------------------------------------- parse
def parse(said: str, known_places: set[str] | None = None,
          today: dt.date | None = None) -> Recall:
    today = today or dt.date.today()
    since, until, rest = parse_time(said, today)
    places, rest = parse_place(rest, known_places or set())
    words = [w for w in re.findall(r"[a-z']+", rest.lower()) if w not in NOISE]
    r = Recall(said=said, since=since, until=until, places=places,
               semantic=" ".join(words))
    if not (since or places or r.semantic):
        r.notes.append("Nothing to search on — say a time, a place, or what it looked like.")
    return r


# ------------------------------------------------------------------ search
def run(index, recall: Recall, embedder=None, top: int = 24) -> list[dict]:
    """Filter by the hard facts first (fast, exact, no model), then rank
    what survives by meaning. Doing it in this order means the model only
    ever sees the handful of photos that were actually in Cuba."""
    import numpy as np

    where, args = [], []
    if recall.since:
        where.append("taken_at >= ?")
        args.append(recall.since.isoformat())
    if recall.until:
        where.append("taken_at <= ?")
        args.append(recall.until.isoformat() + "T23:59:59")
    if recall.places:
        ors = " OR ".join(["place LIKE ? OR country LIKE ?"] * len(recall.places))
        where.append(f"({ors})")
        for p in recall.places:
            args += [f"%{p}%", f"%{p}%"]
    sql = "SELECT sha256, path, taken_at, place, country FROM photos"
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = list(index.db.execute(sql, args))
    if not rows:
        return []

    # No words left over — it was a pure time/place question. Answer it
    # chronologically and never load the model at all.
    if not recall.semantic or embedder is None:
        rows.sort(key=lambda r: r[2] or "")
        return [{"sha256": r[0], "path": r[1], "taken_at": r[2],
                 "place": r[3], "country": r[4], "score": None} for r in rows[:top]]

    keep = {r[0]: r for r in rows}
    mat, shas = index.matrix()
    if mat is None:
        return []
    mask = [i for i, s in enumerate(shas) if s in keep]
    if not mask:
        return []
    q = embedder.embed_text([recall.semantic])[0]
    scores = mat[mask] @ q
    order = np.argsort(-scores)[:top]
    out = []
    for j in order:
        r = keep[shas[mask[j]]]
        out.append({"sha256": r[0], "path": r[1], "taken_at": r[2],
                    "place": r[3], "country": r[4], "score": float(scores[j])})
    return out


# --------------------------------------------------------------------- cli
def main() -> int:
    from photo_index import Embedder, PhotoIndex

    ap = argparse.ArgumentParser(description="Ask your own photos a question.")
    ap.add_argument("question", nargs="?", default="")
    ap.add_argument("--index", default="~/.selfcloud/photo-index")
    ap.add_argument("--top", type=int, default=24)
    ap.add_argument("--explain", action="store_true",
                    help="show how the sentence was taken apart, then stop")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if not a.question:
        ap.error("ask something, e.g. \"vacation ten years ago in Cuba\"")

    idx = PhotoIndex(a.index)
    known = {r[0] for r in idx.db.execute(
        "SELECT DISTINCT place FROM photos WHERE place IS NOT NULL")}
    known |= {r[0] for r in idx.db.execute(
        "SELECT DISTINCT country FROM photos WHERE country IS NOT NULL")}
    r = parse(a.question, known)

    print(f'\n  You said:  "{r.said}"')
    print(f"  I'll find: {r.describe()}")
    for n in r.notes:
        print(f"  note: {n}")
    if a.explain:
        print()
        return 0

    emb = None
    if r.semantic:
        man = idx.manifest()
        if man:
            emb = Embedder(idx, man["model"], man["pretrained"], offline=True)
    hits = run(idx, r, emb, a.top)
    print(f"\n  {len(hits)} photo(s), searched entirely on this machine:\n")
    for i, h in enumerate(hits, 1):
        when = (h["taken_at"] or "")[:10] or "date unknown"
        where = h["place"] or h["country"] or ""
        score = f"  {h['score']:.3f}" if h["score"] is not None else ""
        print(f"  {i:3d}. {when}  {where:22s}{score}  {h['path']}")
    print()
    return 0


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    """Every assertion here is a sentence someone might actually say."""
    today = dt.date(2026, 9, 14)
    known = {"Cuba", "Toronto", "Varadero", "Canada", "New York"}

    r = parse("show me the part of me that was on vacation ten years ago in Cuba",
              known, today)
    assert r.since == dt.date(2016, 1, 1) and r.until == dt.date(2016, 12, 31), r
    assert r.places == ["Cuba"], r.places
    assert r.semantic == "vacation", repr(r.semantic)

    r = parse("summer 2015 in Toronto with mum", known, today)
    assert (r.since, r.until) == (dt.date(2015, 6, 1), dt.date(2015, 8, 31)), r
    assert r.places == ["Toronto"] and "mum" in r.semantic

    r = parse("christmas at the kitchen table", known, today)
    assert r.since == dt.date(2026, 12, 20) and r.until == dt.date(2026, 12, 27)
    assert "kitchen" in r.semantic and "table" in r.semantic

    r = parse("last year in New York", known, today)
    assert r.since == dt.date(2025, 1, 1) and r.places == ["New York"]

    r = parse("june 2019", known, today)
    assert (r.since, r.until) == (dt.date(2019, 6, 1), dt.date(2019, 6, 30))

    # winter wraps the year boundary
    r = parse("winter 2020", known, today)
    assert r.since == dt.date(2019, 12, 1) and r.until == dt.date(2020, 2, 29), r

    # longest place name wins, and a place inside another is not double-matched
    r = parse("that trip to Varadero Cuba", known, today)
    assert set(r.places) == {"Varadero", "Cuba"}, r.places

    # a bare question with nothing to go on says so instead of returning
    # the whole library
    r = parse("show me the photos", known, today)
    assert r.notes and not r.semantic

    # a place the person has no photos of is not invented — it falls through
    # to the semantic pass rather than silently filtering to nothing
    r = parse("vacation in Portugal", known, today)
    assert r.places == [] and "portugal" in r.semantic

    print("\n  ✓ recall: dates, seasons, occasions, year-wrap, places from the")
    print("    owner's own library, noise stripped, nothing invented.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
