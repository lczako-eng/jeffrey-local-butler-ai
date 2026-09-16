"""
JEFFEREY — reminiscence: the album, opened by him
=================================================

    "I wanted to collect all my memories and have it ask me questions —
     'these pictures from Afghanistan, tell me some stories' — so it
     remembers permanently."                          — the owner, 2026-09-16

The photo index knows WHEN and WHERE every picture was taken. Nobody remembers
everything, but almost everybody remembers when shown. So this is the loop:

    1. FIND a moment nobody has been asked about — a trip, a season, a place:
       "143 photographs, Afghanistan, October 2011."
    2. ASK, once, the way a friend flipping through an album would:
       "Tell me about that — whatever comes to mind."
    3. KEEP what he says, verbatim, in the life layer, pinned to those exact
       photographs. Permanently. In his words.

Rules, because this is the most intimate thing the system does:

  * ONE question at a time. Never a list, never announced as an interview.
  * The prompt states only FACTS the index holds — a count, a place, dates.
    Never "this looks like a wedding": that is a guess, and a guess offered
    as a memory is how a false memory starts. The story comes from him.
  * His words are kept exactly. Nothing summarised, nothing embellished.
  * "Rather not" is final. A declined moment is never offered again.
  * Private by default. He decides what family sees, later, if ever.
  * Absence is not deletion: a moment whose photos are on an unplugged drive
    still exists; it is simply not offered until the drive is back.

This reads the photo index built by tools/photo_index.py and writes to the
conscience through life.py. It runs by itself from a terminal, and through
three tools on every JEFFEREY surface: next_story_prompt / record_story /
decline_story.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import home
DEFAULT_INDEX = home.index_path()
MERGE_GAP_DAYS = 14   # same country, photos within two weeks = one trip
MIN_PHOTOS = 3        # fewer than this is not a moment worth an interruption
SHOW = 12             # how many photo ids a prompt carries for display

# A gentle second question, chosen by what the first answer left out. One
# only; the model may ask it or let it go.
FOLLOW_UPS = {
    "people": "Who was with you?",
    "sense": "What do you remember most — a sound, a smell, the light?",
    "feeling": "How did it feel at the time, and how does it feel now?",
    "detail": "Is there one small thing from then you'd hate to lose?",
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "somewhere"


def _label(country: str, start: str, end: str, places: list[str]) -> str:
    s, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if (s.year, s.month) == (e.year, e.month):
        when = s.strftime("%B %Y")
    elif s.year == e.year:
        when = f"{s.strftime('%b')}–{e.strftime('%b %Y')}"
    else:
        when = f"{s.strftime('%b %Y')}–{e.strftime('%b %Y')}"
    where = country
    detail = [p for p in places if p and p != country][:3]
    if detail:
        where += f" ({', '.join(detail)})"
    return f"{where} · {when}"


class Reminisce:
    """Finds untold moments in the photographs and keeps what he says."""

    def __init__(self, conscience, life, index_path: Path | str = DEFAULT_INDEX):
        self.c = conscience
        self.life = life
        self.index_path = Path(index_path).expanduser()
        self._db: sqlite3.Connection | None = None

    # ------------------------------------------------------------ storage
    @property
    def available(self) -> bool:
        return (self.index_path / "index.sqlite").exists()

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            p = self.index_path / "index.sqlite"
            if not p.exists():
                raise FileNotFoundError(
                    f"No photo index at {self.index_path}. Run "
                    f"tools/photo_index.py build first (or Show me my life.command).")
            self._db = sqlite3.connect(p)
            # Moment state lives beside the photos it describes, not in the
            # conscience: it is ABOUT the pictures. The stories are about him
            # and go to the life layer.
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS moments (
                    id TEXT PRIMARY KEY, label TEXT, country TEXT, places TEXT,
                    start TEXT, end TEXT, count INTEGER,
                    status TEXT NOT NULL DEFAULT 'untold',
                    asked_at TEXT, told_at TEXT, stories INTEGER DEFAULT 0,
                    shas TEXT);
                CREATE INDEX IF NOT EXISTS moments_status ON moments(status);
            """)
            self._db.commit()
        return self._db

    # ---------------------------------------------------------- clustering
    def refresh(self) -> int:
        """Group dated photographs into moments. Idempotent: a moment that has
        been told or declined keeps its status; counts and ranges update."""
        rows = self.db.execute(
            "SELECT sha256, taken_at, country, place FROM photos "
            "WHERE taken_at IS NOT NULL AND missing_since IS NULL "
            "ORDER BY taken_at").fetchall()
        by_key: dict[str, list] = {}
        for sha, taken, country, place in rows:
            by_key.setdefault(country or place or "somewhere", []).append(
                (taken[:19], sha, place))

        clusters = []
        for key, items in by_key.items():
            items.sort()
            cur = [items[0]]
            for it in items[1:]:
                prev = dt.datetime.fromisoformat(cur[-1][0])
                this = dt.datetime.fromisoformat(it[0])
                if (this - prev).days > MERGE_GAP_DAYS:
                    clusters.append((key, cur))
                    cur = []
                cur.append(it)
            clusters.append((key, cur))

        n = 0
        for key, items in clusters:
            if len(items) < MIN_PHOTOS:
                continue
            start, end = items[0][0][:10], items[-1][0][:10]
            places = sorted({p for _, _, p in items if p})
            shas = [s for _, s, _ in items]
            mid = f"{_slug(key)}-{start.replace('-', '')}"
            self.db.execute(
                "INSERT INTO moments (id, label, country, places, start, end, "
                "count, shas) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET label=excluded.label, "
                "places=excluded.places, end=excluded.end, count=excluded.count, "
                "shas=excluded.shas",
                (mid, _label(key, start, end, places), key, json.dumps(places),
                 start, end, len(shas), json.dumps(shas)))
            n += 1
        self.db.commit()
        return n

    def moments(self, status: str | None = None) -> list[dict]:
        q = "SELECT id, label, country, start, end, count, status, stories FROM moments"
        args: tuple = ()
        if status:
            q += " WHERE status = ?"
            args = (status,)
        q += " ORDER BY count DESC, start ASC"
        return [dict(zip(("id", "label", "country", "from", "to", "photos",
                          "status", "stories"), r))
                for r in self.db.execute(q, args)]

    # ---------------------------------------------------------------- ask
    def next_prompt(self) -> dict:
        """ONE untold moment — the biggest, then the oldest — phrased the way
        a friend would ask. States only what the index knows for a fact."""
        if not self.available:
            return {"moment_id": None,
                    "note": "No photographs are indexed yet, so there is nothing "
                            "to ask about. Once the library is read, this fills."}
        self.refresh()
        row = self.db.execute(
            "SELECT id, label, country, start, end, count, shas FROM moments "
            "WHERE status = 'untold' ORDER BY count DESC, start ASC LIMIT 1"
        ).fetchone()
        if not row:
            told = self.db.execute(
                "SELECT COUNT(*) FROM moments WHERE status='told'").fetchone()[0]
            return {"moment_id": None,
                    "note": f"Every moment in the photographs has been asked about "
                            f"({told} told). New ones appear as photos are added."}
        mid, label, country, start, end, count, shas = row
        shas = json.loads(shas)
        year = start[:4]
        self.db.execute("UPDATE moments SET asked_at=? WHERE id=?", (_now(), mid))
        self.db.commit()
        return {
            "moment_id": mid,
            "label": label,
            "photos": count,
            "from": start, "to": end,
            "show_on_the_wall": f"{country} {year}",       # a recall.py sentence
            "photo_ids": shas[:SHOW],
            "ask": (f"There are {count} photographs from {label}. "
                    f"Tell me about that — whatever comes to mind."),
            "rule": ("One question, asked the way a friend would while looking at "
                     "the pictures. Keep his words exactly. 'Rather not' is final — "
                     "call decline_story and never raise it again."),
        }

    # --------------------------------------------------------------- keep
    def record(self, moment_id: str, text: str, people: str = "",
               when: str = "", visibility: str = "private") -> dict:
        """Keep what he said, verbatim, pinned to the photographs."""
        if not self.available:
            return {"error": "no photographs are indexed yet, so there is no "
                             "moment to pin this to"}
        row = self.db.execute(
            "SELECT label, country, start, shas, status FROM moments WHERE id=?",
            (moment_id,)).fetchone()
        if not row:
            return {"error": f"no such moment: {moment_id}"}
        label, country, start, shas, status = row
        if status == "declined":
            return {"error": "he said he'd rather not talk about this one; "
                             "that stands"}
        if not text or not text.strip():
            return {"error": "nothing to keep — the story is empty"}
        tags = f"{country},{start[:4]},moment:{moment_id}"
        memory = self.life.add_memory(
            text, when=when or start[:7], people=people, tags=tags,
            visibility=visibility, photos=json.loads(shas))
        self.db.execute(
            "UPDATE moments SET status='told', told_at=?, stories=stories+1 "
            "WHERE id=?", (_now(), moment_id))
        self.db.commit()
        # One gentle follow-up, chosen by what the story left out.
        if not memory["people"]:
            follow = FOLLOW_UPS["people"]
        elif not re.search(r"\b(smell|sound|light|cold|hot|warm|taste|dust|noise)\w*",
                           text, re.I):
            follow = FOLLOW_UPS["sense"]
        else:
            follow = FOLLOW_UPS["feeling"]
        return {"kept": True, "moment": label, "memory": memory,
                "pinned_to_photos": len(memory.get("photos", [])),
                "one_follow_up": follow,
                "note": "Kept in his words, privately, pinned to those pictures. "
                        "Ask the follow-up only if the moment is right; never two."}

    def decline(self, moment_id: str) -> dict:
        """'Rather not.' Final. Never offered again."""
        if not self.available:
            return {"error": "no photographs are indexed yet"}
        cur = self.db.execute(
            "UPDATE moments SET status='declined' WHERE id=?", (moment_id,))
        self.db.commit()
        if cur.rowcount == 0:
            return {"error": f"no such moment: {moment_id}"}
        return {"declined": True, "moment_id": moment_id,
                "note": "Never raised again. Do not circle back or rephrase it."}

    def progress(self) -> dict:
        if not self.available:
            return {"indexed": False}
        self.refresh()
        counts = dict(self.db.execute(
            "SELECT status, COUNT(*) FROM moments GROUP BY status"))
        stories = self.db.execute(
            "SELECT COALESCE(SUM(stories),0) FROM moments").fetchone()[0]
        return {"indexed": True, "untold": counts.get("untold", 0),
                "told": counts.get("told", 0), "declined": counts.get("declined", 0),
                "stories": stories}


# ------------------------------------------------------------------ CLI
def _interactive(rem: Reminisce) -> int:
    """Sit down with the album. One moment, one story, saved."""
    p = rem.next_prompt()
    if not p.get("moment_id"):
        print(f"\n  {p['note']}\n")
        return 0
    print(f"\n  {p['label']} — {p['photos']} photographs, {p['from']} to {p['to']}")
    print(f"  (on the wall, type:  {p['show_on_the_wall']})\n")
    print(f"  {p['ask']}")
    print("  Type your story. Blank line to finish. 'no' if you'd rather not.\n")
    lines = []
    while True:
        try:
            line = input("  > ")
        except EOFError:
            break
        if not line.strip():
            break
        if not lines and line.strip().lower() in ("no", "rather not", "skip"):
            rem.decline(p["moment_id"])
            print("\n  Understood. I won't ask about that one again.\n")
            return 0
        lines.append(line)
    if not lines:
        print("\n  Nothing kept. It'll still be here next time.\n")
        return 0
    people = input("  Who was there? (names, comma-separated, or blank) > ").strip()
    r = rem.record(p["moment_id"], "\n".join(lines), people=people)
    print(f"\n  Kept — pinned to {r['pinned_to_photos']} photographs, privately.")
    print(f"  {r['one_follow_up']}\n")
    return 0


def selftest() -> int:
    import tempfile
    import argparse
    from PIL import Image
    try:
        import piexif
    except ImportError:
        print("  (reminisce selftest needs piexif)")
        return 0
    sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
    from photo_index import PhotoIndex, cmd_build, DEFAULT_MODEL
    from conscience import Conscience
    from life import Life

    td = Path(tempfile.mkdtemp(prefix="reminisce-"))
    pix = td / "pix"
    pix.mkdir()

    def stamp(name, when, lat, lon):
        p = pix / name
        Image.new("RGB", (64, 64), "olive").save(p, "JPEG")
        def dms(v):
            v = abs(v); d = int(v); m = int((v - d) * 60)
            return ((d, 1), (m, 1), (round((v - d - m / 60) * 360000), 100))
        piexif.insert(piexif.dump({
            "Exif": {piexif.ExifIFD.DateTimeOriginal: when.encode()},
            "GPS": {piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
                    piexif.GPSIFD.GPSLatitude: dms(lat),
                    piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
                    piexif.GPSIFD.GPSLongitude: dms(lon)}}), str(p))

    KABUL, TORONTO = (34.5553, 69.2075), (43.6532, -79.3832)
    for i, day in enumerate((3, 4, 6, 8)):                 # one trip
        stamp(f"afg{i}.jpg", f"2011:10:{day:02d} 10:00:00", *KABUL)
    for i in range(2):                                     # too small to count
        stamp(f"afg-later{i}.jpg", f"2012:03:1{i} 10:00:00", *KABUL)
    for i in range(3):
        stamp(f"tor{i}.jpg", f"2023:11:0{i+1} 09:00:00", *TORONTO)
    Image.new("RGB", (64, 64), "gray").save(pix / "undated.png")   # excluded

    cmd_build(argparse.Namespace(index=str(td / "idx"), source=str(pix),
                                 model=DEFAULT_MODEL, pretrained="none",
                                 batch=8, limit=0, offline=True))
    idx = PhotoIndex(td / "idx")
    countries = {r[0] for r in idx.db.execute(
        "SELECT DISTINCT country FROM photos WHERE country IS NOT NULL")}
    if "Afghanistan" not in countries:
        print("  (skipped: offline geocoder not installed)")
        return 0

    c = Conscience(td / "conscience.json")
    rem = Reminisce(c, Life(c), td / "idx")

    # clustering: Afghanistan Oct 2011 (4), Toronto Nov 2023 (3); the March
    # 2012 pair is below MIN_PHOTOS and the undated one never enters
    n = rem.refresh()
    ms = rem.moments()
    assert n == 2 and len(ms) == 2, ms
    assert ms[0]["country"] == "Afghanistan" and ms[0]["photos"] == 4, ms[0]
    assert "October 2011" in ms[0]["label"], ms[0]["label"]
    assert ms[1]["country"] == "Canada" and ms[1]["photos"] == 3, ms[1]

    # the first prompt is the biggest untold moment, phrased from facts only
    p = rem.next_prompt()
    assert p["moment_id"] == ms[0]["id"], p
    assert "4 photographs" in p["ask"] and "Afghanistan" in p["ask"], p["ask"]
    assert p["show_on_the_wall"] == "Afghanistan 2011"
    assert len(p["photo_ids"]) == 4
    for bad in ("looks like", "wedding", "probably"):
        assert bad not in p["ask"], "the prompt guessed"

    # his words are kept verbatim, pinned to the four photos, private
    story = "We were up at Bagram most of that month. Dust in everything.\nMike drove."
    r = rem.record(p["moment_id"], story, people="Mike")
    assert r["kept"] and r["pinned_to_photos"] == 4, r
    mem = c.data["memories"][-1]
    assert mem["text"] == story, "the story was altered"
    assert mem["visibility"] == "private" and mem["people"] == ["Mike"]
    assert f"moment:{p['moment_id']}" in mem["tags"] and "afghanistan" in mem["tags"]
    assert len(mem["photos"]) == 4 and set(mem["photos"]) == set(p["photo_ids"])
    assert r["one_follow_up"] == FOLLOW_UPS["feeling"], r["one_follow_up"]  # people + a sense word given
    assert rem.moments("told")[0]["id"] == p["moment_id"]

    # the story's people were omitted -> the follow-up asks who was there
    r2 = rem.record(p["moment_id"], "Second story, no names.")
    assert r2["one_follow_up"] == FOLLOW_UPS["people"]
    assert rem.moments("told")[0]["stories"] == 2

    # next: Toronto. Decline it. Final.
    p2 = rem.next_prompt()
    assert p2["moment_id"] == ms[1]["id"], p2
    assert rem.decline(p2["moment_id"])["declined"]
    assert "rather not" in rem.record(p2["moment_id"], "anyway")["error"]

    # nothing left; refresh does not resurrect anything
    p3 = rem.next_prompt()
    assert p3["moment_id"] is None and "1 told" in p3["note"], p3
    rem.refresh()
    assert rem.progress() == {"indexed": True, "untold": 0, "told": 1,
                              "declined": 1, "stories": 2}, rem.progress()

    # no index at all -> a graceful answer, not a crash
    rem0 = Reminisce(c, Life(c), td / "nope")
    assert rem0.next_prompt()["moment_id"] is None
    assert rem0.progress() == {"indexed": False}

    import shutil
    shutil.rmtree(td, ignore_errors=True)
    print("\n  ✓ reminisce: trips clustered from dated+placed photos, the biggest")
    print("    untold one asked first from facts alone, the story kept verbatim")
    print("    and pinned to its photos, one follow-up chosen by what was left")
    print("    out, 'rather not' final, nothing resurrected, no index handled.\n")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from conscience import Conscience
    from life import Life
    import access
    from selfcloud import SelfCloud
    _c = Conscience()
    access.bind(SelfCloud(_c), "jefferey", announce=False)
    sys.exit(_interactive(Reminisce(_c, Life(_c))))
