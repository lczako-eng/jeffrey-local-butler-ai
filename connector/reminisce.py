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
    3. KEEP what he says, verbatim, in the life layer, pinned to that moment.
       Permanently. In his words.

Rules, because this is the most intimate thing the system does:

  * ONE question at a time. Never a list, never announced as an interview.
  * The prompt states only FACTS the index holds — a count, a place, dates.
    Never "this looks like a wedding": that is a guess, and a guess offered
    as a memory is how a false memory starts. The story comes from him.
  * His words are kept exactly. Nothing summarised, nothing embellished.
  * "Rather not" is final. A declined moment is never offered again — and
    that answer lives in HIS conscience, with the photographs it covers, not
    in the rebuildable photo index. Re-reading the library, building a new
    index, or adding one more photo from that week does not undo it: any
    moment that shares a photograph with a declined one is declined too.
  * "Not now" is not "rather not": a skipped moment goes to the back of the
    album and comes round again much later.
  * His own rules come first. A moment his rules say not to raise ("never
    bring up Afghanistan unless I raise it first") is never offered.
  * Trust before depth. The album stays closed until he has shared a little
    in conversation, opens on small, recent, ordinary moments, and never
    opens on a war or a loss. Those come later, if ever, gently, with no
    "how does it feel now".
  * Private by default. He decides what family sees, later, if ever.
  * Absence is not deletion: a moment whose photos are on an unplugged drive
    still exists; it is simply not offered until the drive is back.
  * No photo fingerprints leave the house. Engines get a count, a place and
    dates — never the list of content hashes, which are no use to them.

This reads the photo index built by tools/photo_index.py and writes to the
conscience through life.py. It runs by itself from a terminal, and through
tools on every JEFFEREY surface: next_story_prompt / record_story /
decline_story / skip_story / story_progress. 'Not now' (skip_story) sends a
moment to the back; a moment offered and never answered rests a week.

The owner's own terminal can also keep subjects out of the album and off the
wall, and — only there, by his own hands — open a declined moment again:

    python connector/reminisce.py                       # sit down with the album
    python connector/reminisce.py never-ask Afghanistan
    python connector/reminisce.py keep-off-wall Kandahar
    python connector/reminisce.py list
    python connector/reminisce.py reopen afghanistan-20111003
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import sys
import threading
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import home
# Where the photo index was when this module was imported. Kept for older
# callers; a Reminisce made without a path asks home.py every time instead,
# so a running album follows a drive plugged in (or renamed) after it started.
DEFAULT_INDEX = home.index_path()
MERGE_GAP_DAYS = 14   # same country, photos within two weeks = one trip
MIN_PHOTOS = 3        # fewer than this is not a moment worth an interruption
DB_TIMEOUT = 30       # seconds a reader waits for a writer, rather than failing

# Interview trust (interview.py) needed before the album opens at all, and
# before a moment that may be painful is offered.
OPEN_AT_DEPTH = 2
HARD_AT_DEPTH = 3
# A moment offered but not answered ('not now', or the engine never got to
# it) rests this long before it is offered again.
REST_DAYS = 7

# A gentle second question, chosen by what the first answer left out. One
# only; the model may ask it or let it go.
FOLLOW_UPS = {
    "people": "Who was with you?",
    "sense": "What do you remember most — a sound, a smell, the light?",
    "feeling": "How did it feel at the time, and how does it feel now?",
    "detail": "Is there one small thing from then you'd hate to lose?",
}

# Where a soldier's or a peacekeeper's photographs come from. Used ONLY to
# keep these moments from being the first thing the album asks about and to
# make the follow-up gentle — never said to anyone, never a guess about what
# a picture shows.
CONFLICT_COUNTRIES = {
    "afghanistan", "iraq", "syria", "syrian arab republic", "somalia",
    "bosnia and herzegovina", "kosovo", "xk", "rwanda", "libya", "yemen",
    "sudan", "south sudan", "mali", "ukraine",
}

_DEATH = re.compile(
    r"\b(died|dies|passed away|passed on|passing|funeral|death|deceased|"
    r"buried|memorial|killed|lost (him|her|them)|late (wife|husband|mother|"
    r"father|mum|mom|dad|son|daughter|brother|sister|partner|friend))\b", re.I)
_PROHIBIT = re.compile(
    r"\b(never|don'?t|do not|not to|avoid|stop|unless i|no questions?)\b", re.I)
_MONTHS = {m.lower(): i for i, m in enumerate(
    ("January February March April May June July August September October "
     "November December").split(), 1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})


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


def _losses(people: list[dict]) -> list[tuple[str, int, int | None]]:
    """(name, year, month or None) for each loss the owner recorded about a
    person: 'died February 2019, funeral in Budapest'."""
    out = []
    for p in people or []:
        text = " ".join(str(p.get(k, "")) for k in
                        ("notes", "important_dates", "relationship"))
        if not _DEATH.search(text):
            continue
        found = False
        for m in re.finditer(r"\b([A-Za-z]{3,9})\.?\s+(19\d\d|20\d\d)\b", text):
            mon = _MONTHS.get(m.group(1).lower())
            if mon:
                out.append((p.get("name", ""), int(m.group(2)), mon))
                found = True
        for m in re.finditer(r"\b(19\d\d|20\d\d)-(\d\d)\b", text):
            out.append((p.get("name", ""), int(m.group(1)), int(m.group(2))))
            found = True
        if not found:
            for y in re.findall(r"\b(19\d\d|20\d\d)\b", text):
                out.append((p.get("name", ""), int(y), None))
    return out


def _covers(start: str, end: str, year: int, month: int | None) -> bool:
    s, e = start[:7], end[:7]
    if month is None:
        return int(start[:4]) <= year <= int(end[:4])
    ym = f"{year:04d}-{month:02d}"
    return s <= ym <= e


def _asked_within(asked_at: str | None, now: dt.datetime, days: int) -> bool:
    if not asked_at:
        return False
    try:
        when = dt.datetime.strptime(asked_at, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        try:
            when = dt.datetime.fromisoformat(asked_at)
        except ValueError:
            return False
    if when.tzinfo is None:
        when = when.astimezone()
    return now - when < dt.timedelta(days=days)


class _DataOnly:
    """A conscience that can be read and never written — for the wall, which
    must honour the owner's decisions but has no business changing them."""

    def __init__(self, data: dict | None):
        self.data = data if isinstance(data, dict) else {}

    def _save(self) -> None:
        raise PermissionError("read-only view of the conscience")


class Reminisce:
    """Finds untold moments in the photographs and keeps what he says."""

    def __init__(self, conscience, life, index_path: Path | str | None = None):
        self.c = conscience
        self.life = life
        # None: wherever home.py says the photographs are, asked on every
        # call — the drive may be plugged in after JEFFEREY started.
        self._fixed = Path(index_path).expanduser() if index_path is not None else None
        # One SQLite connection per thread: every surface answers from more
        # than one thread, and a connection shared between them broke
        # record_story and decline_story after any two calls overlapped.
        self._local = threading.local()
        self._lock = threading.RLock()
        self._schema_ready: set[str] = set()

    @property
    def index_path(self) -> Path:
        return self._fixed if self._fixed is not None else home.index_path()

    @index_path.setter
    def index_path(self, value) -> None:
        self._fixed = Path(value).expanduser()

    # ------------------------------------------------------------ storage
    @property
    def available(self) -> bool:
        return (self.index_path / "index.sqlite").is_file()

    @property
    def db(self) -> sqlite3.Connection:
        where = self.index_path
        con = getattr(self._local, "con", None)
        if con is not None and getattr(self._local, "where", None) == where:
            return con
        if con is not None:                 # the drive moved: let the old one go
            try:
                con.close()
            except Exception:
                pass
            self._local.con = None
        p = where / "index.sqlite"
        if not p.is_file():
            raise FileNotFoundError(
                f"No photographs have been read yet at {where}. "
                f"Double-click 'Show me my life' to read them (or plug in the "
                f"Self-Cloud drive, if they were read onto it).")
        con = sqlite3.connect(p, timeout=DB_TIMEOUT)
        con.isolation_level = "IMMEDIATE"   # take the write lock up front
        self._local.con, self._local.where = con, where
        with self._lock:
            if str(where) not in self._schema_ready:
                # The moments table is a CACHE of the clustering, beside the
                # photos it describes. What he decided — told, declined —
                # lives in his conscience (see _album), so a rebuilt index
                # cannot forget it.
                con.executescript("""
                    CREATE TABLE IF NOT EXISTS moments (
                        id TEXT PRIMARY KEY, label TEXT, country TEXT, places TEXT,
                        start TEXT, end TEXT, count INTEGER,
                        status TEXT NOT NULL DEFAULT 'untold',
                        asked_at TEXT, told_at TEXT, stories INTEGER DEFAULT 0,
                        shas TEXT);
                    CREATE INDEX IF NOT EXISTS moments_status ON moments(status);
                """)
                # present: in the current clustering. rev: NULL for a row an
                # older JEFFEREY wrote, whose status is carried into the
                # conscience once (_migrate) and never trusted again after.
                for col in ("present INTEGER DEFAULT 1", "rev INTEGER"):
                    try:
                        con.execute(f"ALTER TABLE moments ADD COLUMN {col}")
                    except sqlite3.OperationalError:
                        pass                      # already there
                con.commit()
                self._schema_ready.add(str(where))
        return con

    # -------------------------------------------------- his decisions, kept
    def _album(self) -> dict:
        """The album's state in the conscience: every moment he told or
        declined, with the photographs it covers, plus subjects he keeps out
        of the album or off the wall. Created on first use; older stores
        simply don't have it yet."""
        a = self.c.data.get("album")
        if not isinstance(a, dict):
            a = {}
            self.c.data["album"] = a
        if not isinstance(a.get("moments"), dict):
            a["moments"] = {}
        for k in ("never_ask", "never_on_the_wall"):
            if not isinstance(a.get(k), list):
                a[k] = []
        return a

    def _remember(self, mid: str, status: str, row: dict, story: bool = False) -> None:
        """Write one decision into the conscience (the caller saves)."""
        moments = self._album()["moments"]
        m = moments.get(mid) or {}
        shas = sorted(set(m.get("shas", [])) | set(row.get("shas", [])))
        m.update({
            # 'rather not' is final: nothing turns a declined moment back
            "status": "declined" if "declined" in (status, m.get("status")) else status,
            "label": row.get("label") or m.get("label", ""),
            "country": row.get("country") or m.get("country", ""),
            "places": row.get("places") or m.get("places", []),
            "from": row.get("from") or m.get("from", ""),
            "to": row.get("to") or m.get("to", ""),
            "shas": shas,
            "stories": int(m.get("stories", 0)) + (1 if story else 0),
            "at": _now(),
        })
        moments[mid] = m

    def _migrate(self) -> None:
        """Older stores kept 'told' and 'declined' only in the photo index,
        and pinned each story's photographs inside the memory itself (so
        who_am_i handed every fingerprint to the engine). Carry both into the
        album's state in the conscience, losing nothing: the photographs stay
        pinned to the moment, and the memory keeps the moment's id."""
        moments = self._album()["moments"]
        changed = False
        for mid, label, country, places, start, end, status, shas, stories in \
                self.db.execute("SELECT id, label, country, places, start, end, "
                                "status, shas, stories FROM moments "
                                "WHERE status IN ('told', 'declined') AND rev IS NULL"):
            m = moments.get(mid)
            if m and (m.get("status") == status or m.get("status") == "declined"):
                continue
            self._remember(mid, status, {
                "label": label, "country": country,
                "places": json.loads(places or "[]"), "from": start, "to": end,
                "shas": json.loads(shas or "[]")})
            moments[mid]["stories"] = max(int(moments[mid].get("stories", 0)),
                                          int(stories or 0))
            changed = True
        told_about: Counter = Counter()
        moved = set()
        for mem in self.c.data.get("memories", []):
            tag = next((t for t in mem.get("tags", []) if str(t).startswith("moment:")), None)
            if not tag:
                continue
            mid = tag.split(":", 1)[1]
            told_about[mid] += 1
            if isinstance(mem.get("photos"), list):
                self._remember(mid, "told", {"shas": mem["photos"]})
                del mem["photos"]                 # now kept with the moment
                moved.add(mid)
        for mid in moved:
            moments[mid]["stories"] = max(int(moments[mid].get("stories", 0)),
                                          told_about[mid])
            changed = True
        if changed:
            try:
                self.c._save()
            except PermissionError:
                pass                              # a read-only view (the wall)

    # ---------------------------------------------------------- clustering
    def _clusters(self) -> list[tuple[str, list]]:
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
                try:
                    prev = dt.datetime.fromisoformat(cur[-1][0])
                    this = dt.datetime.fromisoformat(it[0])
                    gap = (this - prev).days
                except ValueError:
                    gap = 0
                if gap > MERGE_GAP_DAYS:
                    clusters.append((key, cur))
                    cur = []
                cur.append(it)
            clusters.append((key, cur))
        return [(k, items) for k, items in clusters if len(items) >= MIN_PHOTOS]

    def _compute(self) -> list[dict]:
        """Group dated photographs into moments and give each a stable id
        and its status.

        A moment's id does not depend on its first date: a cluster that
        shares photographs with a moment already known keeps that moment's
        id. Status comes from his conscience, and any cluster that shares
        even one photograph with a declined moment is declined."""
        decided = {mid: (m.get("status"), set(m.get("shas", [])))
                   for mid, m in self._album()["moments"].items()}
        prior, legacy = {}, set()
        for mid, status, shas, rev in self.db.execute(
                "SELECT id, status, shas, rev FROM moments"):
            try:
                prior[mid] = (status, set(json.loads(shas or "[]")))
            except ValueError:
                prior[mid] = (status, set())
            if rev is None:
                legacy.add(mid)
        owners: dict[str, set] = {}
        for source in (decided, prior):
            for mid, (_st, shas) in source.items():
                for s in shas:
                    owners.setdefault(s, set()).add(mid)

        def status_of(mid: str) -> str:
            if mid in decided and decided[mid][0] in ("told", "declined"):
                return decided[mid][0]
            # An older JEFFEREY's decision, not yet carried into the conscience
            # (the wall reads without migrating). Never a status this code
            # derived itself: that is recomputed from the conscience each time.
            if mid in legacy and prior[mid][0] in ("told", "declined"):
                return prior[mid][0]
            return "untold"

        used: set[str] = set()
        out = []
        # Biggest first, so when a moment splits the bigger part keeps its id.
        for key, items in sorted(self._clusters(), key=lambda c: (-len(c[1]), c[1][0][0])):
            shas = [s for _, s, _ in items]
            overlap: Counter = Counter()
            for s in shas:
                for mid in owners.get(s, ()):
                    overlap[mid] += 1
            start, end = items[0][0][:10], items[-1][0][:10]
            cands = [m for m, _ in sorted(overlap.items(), key=lambda kv: (-kv[1], kv[0]))
                     if m not in used]
            if cands:
                mid = cands[0]
            else:
                mid = base = f"{_slug(key)}-{start.replace('-', '')}"
                n = 2
                while mid in used:
                    mid, n = f"{base}-{n}", n + 1
            used.add(mid)
            status = status_of(mid)
            if any(status_of(m) == "declined" for m in overlap):
                status = "declined"
            places = sorted({p for _, _, p in items if p})
            out.append({"id": mid, "key": key, "label": _label(key, start, end, places),
                        "country": key, "places": places, "from": start, "to": end,
                        "count": len(shas), "shas": shas, "status": status})
        return out

    def refresh(self) -> int:
        """Re-cluster and bring the cache up to date. Idempotent: what he
        decided is kept; counts and ranges update."""
        with self._lock:
            self._migrate()
            moments = self._compute()
            db = self.db
            db.execute("UPDATE moments SET present=0")
            for m in moments:
                db.execute(
                    "INSERT INTO moments (id, label, country, places, start, end, "
                    "count, shas, status, present, rev) VALUES (?,?,?,?,?,?,?,?,?,1,2) "
                    "ON CONFLICT(id) DO UPDATE SET label=excluded.label, "
                    "country=excluded.country, places=excluded.places, "
                    "start=excluded.start, end=excluded.end, count=excluded.count, "
                    "shas=excluded.shas, status=excluded.status, present=1, rev=2",
                    (m["id"], m["label"], m["country"], json.dumps(m["places"]),
                     m["from"], m["to"], m["count"], json.dumps(m["shas"]),
                     m["status"]))
            db.commit()
            return len(moments)

    def moments(self, status: str | None = None) -> list[dict]:
        q = ("SELECT id, label, country, start, end, count, status, stories "
             "FROM moments WHERE present=1")
        args: tuple = ()
        if status:
            q += " AND status = ?"
            args = (status,)
        q += " ORDER BY count DESC, start ASC"
        return [dict(zip(("id", "label", "country", "from", "to", "photos",
                          "status", "stories"), r))
                for r in self.db.execute(q, args)]

    # ---------------------------------------------------- his rules, first
    def tags_for(self, country: str | None, places, start: str, end: str | None = None
                 ) -> tuple[set[str], list[str]]:
        """The words his rules can name for a moment or a photo, and why it
        may be painful ('war', 'loss'). Facts only: the country, the places,
        the year — plus 'war' for a conflict country and the person's name
        for a loss he recorded at that time."""
        end = end or start
        tags = {str(t).strip().lower() for t in [country, *(places or [])] if t}
        tags |= {str(y) for y in range(int(start[:4]), int(end[:4]) + 1)}
        why = []
        if tags & CONFLICT_COUNTRIES:
            tags |= {"war", "military", "deployment"}
            why.append("war")
        for name, year, month in _losses(self.c.data.get("people", [])):
            if _covers(start, end, year, month):
                tags |= {"grief", "loss", "death", "funeral"}
                if name:
                    tags |= {name.strip().lower(), *name.strip().lower().split()}
                if "loss" not in why:
                    why.append("loss")
        return tags, why

    def _reaction_rules(self, tags: set[str]) -> tuple[list[str], list[str]]:
        """(rules that say not to raise this, his other words about it).
        Only rules that NAME something here count: a general rule with no
        subject ('be direct with me') does not close the album."""
        stop, say = [], []
        for r in self.c.data.get("rules", []):
            if r.get("kind") != "reaction":
                continue
            rt = {str(t).strip().lower() for t in r.get("tags", []) if str(t).strip()}
            if not rt or not (rt & tags):
                continue
            text = str(r.get("instruction", "")).strip()
            (stop if _PROHIBIT.search(text) else say).append(text)
        return stop, say

    def _kept_out(self, tags: set[str], key: str) -> bool:
        words = {str(w).strip().lower() for w in self._album().get(key, []) if str(w).strip()}
        return bool(words & tags)

    def _trust(self) -> dict:
        from interview import Interview
        return Interview(self.c).trust()

    # ---------------------------------------------------------------- ask
    def next_prompt(self, owner_opened: bool = False) -> dict:
        """ONE untold moment, phrased the way a friend would ask. States only
        what the index knows for a fact.

        Which one: never a moment his rules close or he declined; small,
        recent, ordinary moments first; a moment that may be painful (a war,
        a loss he recorded) only once trust is deep and the album has
        already been opened gently; and a moment asked before but not
        answered ('not now') goes to the back."""
        if not self.available:
            return {"moment_id": None,
                    "note": "No photographs are indexed yet, so there is nothing "
                            "to ask about. Once the library is read, this fills."}
        trust = None
        if not owner_opened:
            trust = self._trust()
            if trust["max_depth"] < OPEN_AT_DEPTH:
                return {"moment_id": None,
                        "note": "Not yet. The album opens once they have shared a "
                                "little with you in conversation. Don't mention "
                                "it; be useful to them, and it opens on its own."}
        self.refresh()
        album = self._album()
        told_any = any(m.get("status") == "told" for m in album["moments"].values())
        gentle, hard, closed, resting = [], [], 0, 0
        now = dt.datetime.now(dt.timezone.utc)
        for mid, label, country, places, start, end, count, asked_at in self.db.execute(
                "SELECT id, label, country, places, start, end, count, asked_at "
                "FROM moments WHERE status='untold' AND present=1"):
            places = json.loads(places or "[]")
            tags, why = self.tags_for(country, places, start, end)
            stop, say = self._reaction_rules(tags)
            if stop or self._kept_out(tags, "never_ask"):
                closed += 1
                continue
            if _asked_within(asked_at, now, REST_DAYS):
                resting += 1
                continue
            item = {"id": mid, "label": label, "country": country, "start": start,
                    "end": end, "count": count, "asked_at": asked_at,
                    "why": why, "say": say}
            (hard if why else gentle).append(item)

        def order(m):
            # not-yet-asked first, then the longest ago; then the most recent,
            # then the smallest
            return (m["asked_at"] is not None, m["asked_at"] or "",
                    -dt.date.fromisoformat(m["end"]).toordinal(), m["count"])

        pick = min(gentle, key=order) if gentle else None
        if pick is None and hard:
            deep = owner_opened or (trust or self._trust())["max_depth"] >= HARD_AT_DEPTH
            if owner_opened or (deep and told_any):
                pick = min(hard, key=order)
        if pick is None:
            told = sum(1 for m in album["moments"].values() if m.get("status") == "told")
            if resting and not hard:
                note = ("Nothing more to ask about right now — the rest was "
                        "offered recently. It comes round again in a few days.")
            elif hard:
                note = ("The moments left in the photographs may be painful ones — "
                        "a war, or a loss. The album does not open on those. If "
                        "they bring one up themselves, listen.")
            elif closed:
                note = (f"Nothing to ask about now ({told} told). The rest is "
                        f"closed by their own rules or their 'rather not'.")
            else:
                note = (f"Every moment in the photographs has been asked about "
                        f"({told} told). New ones appear as photos are added.")
            return {"moment_id": None, "note": note}

        mid = pick["id"]
        with self._lock:
            self.db.execute("UPDATE moments SET asked_at=? WHERE id=?", (_now(), mid))
            self.db.commit()
        rule = ("One question, asked the way a friend would while looking at the "
                "pictures. Keep their words exactly. 'Not now' is fine — call "
                "skip_story or just let it go; it comes round again much later. "
                "'Rather not' is final — call decline_story and never raise it again.")
        if pick["why"]:
            rule += (" This may be a painful one. Ask only if they seem ready, "
                     "make 'not now' easy, and ask nothing about how it feels.")
        if pick["say"]:
            rule += " Their own words on this: " + " / ".join(
                f"“{s}”" for s in pick["say"])
        return {
            "moment_id": mid,
            "label": pick["label"],
            "photos": pick["count"],
            "from": pick["start"], "to": pick["end"],
            "show_on_the_wall": f"{pick['country']} {pick['start'][:4]}",  # a recall.py sentence
            "ask": (f"There are {pick['count']} photographs from {pick['label']}. "
                    f"Tell me about that — whatever comes to mind."),
            "rule": rule,
        }

    # --------------------------------------------------------------- keep
    def _row(self, moment_id: str) -> dict | None:
        r = self.db.execute(
            "SELECT label, country, places, start, end, shas, status FROM moments "
            "WHERE id=?", (moment_id,)).fetchone()
        if not r:
            return None
        return {"label": r[0], "country": r[1], "places": json.loads(r[2] or "[]"),
                "from": r[3], "to": r[4], "shas": json.loads(r[5] or "[]"),
                "status": r[6]}

    def _elsewhere(self, row: dict, text: str) -> list[str]:
        """Places the story names that the photographs know about, when it
        names none of this moment's own: a Kabul story offered for the
        Budapest pictures (stress test album#5) is about somewhere else."""
        def named(word: str) -> bool:
            return bool(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, re.I))
        own = {str(x).strip().lower() for x in [row.get("country"), *(row.get("places") or [])]
               if str(x or "").strip()}
        if any(named(w) for w in own):
            return []
        known: set[str] = set()
        for country, places in self.db.execute(
                "SELECT country, places FROM moments WHERE present=1"):
            for w in [country, *json.loads(places or "[]")]:
                if str(w or "").strip():
                    known.add(str(w).strip().lower())
        return sorted(w for w in known - own if len(w) >= 3 and named(w))

    @staticmethod
    def _kept_note(memory: dict, where_pinned: str) -> str:
        """What really happened, said plainly (I-25, I-26)."""
        how = ("Kept in their words" if memory.get("verbatim", True) else
               "Kept as a summary in the AI's words, not his; he can check it with /pending")
        who = ("privately" if memory.get("visibility", "private") == "private"
               else f"for {memory.get('visibility')}")
        note = f"{how}, {who}, {where_pinned}."
        if memory.get("requested_visibility") and memory.get("note"):
            note += " " + str(memory["note"])
        return note

    def record(self, moment_id: str, text: str, people: str = "",
               when: str = "", visibility: str = "private") -> dict:
        """Keep what he said, verbatim, pinned to that moment — unless what he
        said is plainly about somewhere else: then it is kept, unpinned, and
        the moment is left for another day."""
        if not self.available:
            return {"error": "no photographs are indexed yet, so there is no "
                             "moment to pin this to"}
        from life import VISIBILITY
        with self._lock:
            row = self._row(moment_id)
            if not row:
                return {"error": f"no such moment: {moment_id}"}
            decided = self._album()["moments"].get(moment_id, {})
            if row["status"] == "declined" or decided.get("status") == "declined":
                return {"error": "he said he'd rather not talk about this one; "
                                 "that stands"}
            if not text or not text.strip():
                return {"error": "nothing to keep — the story is empty"}
            if visibility not in VISIBILITY:
                return {"error": f"visibility must be one of: {', '.join(VISIBILITY)}"}
            elsewhere = self._elsewhere(row, text)
            if elsewhere:
                # His words are kept (nothing he said is lost), but not pinned
                # to pictures they are not about, and the moment stays untold.
                memory = self.life.add_memory(text, when=when, people=people,
                                              tags=",".join(elsewhere),
                                              visibility=visibility)
                shown = {k: v for k, v in memory.items() if k != "photos"}
                return {"kept": True, "moment": row["label"], "memory": shown,
                        "pinned_to_photos": 0, "one_follow_up": "",
                        "note": self._kept_note(
                            memory, f"but NOT pinned to the pictures from {row['label']}: "
                                    f"it speaks of {', '.join(w.title() for w in elsewhere)}")
                                + " Ask him, gently, which pictures it belongs to; the "
                                  "album will ask about these ones another time."}
            _tags, why = self.tags_for(row["country"], row["places"], row["from"], row["to"])
            # The moment, with every photograph it covers, is kept in the
            # album's state; the memory carries the moment's id. The memory
            # itself holds no list of photo fingerprints, so who_am_i and
            # tell_story never hand hundreds of them to an engine.
            self._remember(moment_id, "told", row, story=True)
            tags = f"{row['country']},{row['from'][:4]},moment:{moment_id}"
            memory = self.life.add_memory(            # saves the conscience
                text, when=when or row["from"][:7], people=people, tags=tags,
                visibility=visibility)
            self.db.execute(
                "UPDATE moments SET status='told', told_at=?, stories=stories+1 "
                "WHERE id=?", (_now(), moment_id))
            self.db.commit()
        # One gentle follow-up, chosen by what the story left out — and none
        # at all about feelings when the moment may be painful.
        if why:
            follow = "" if memory["people"] else FOLLOW_UPS["detail"]
        elif not memory["people"]:
            follow = FOLLOW_UPS["people"]
        elif not re.search(r"\b(smell|sound|light|cold|hot|warm|taste|dust|noise)\w*",
                           text, re.I):
            follow = FOLLOW_UPS["sense"]
        else:
            follow = FOLLOW_UPS["feeling"]
        shown = {k: v for k, v in memory.items() if k != "photos"}
        return {"kept": True, "moment": row["label"], "memory": shown,
                "pinned_to_photos": len(row["shas"]),
                "one_follow_up": follow,
                "note": self._kept_note(memory, "pinned to those pictures")
                        + " Ask the follow-up only if the moment is right; never two."}

    def decline(self, moment_id: str) -> dict:
        """'Rather not.' Final. Never offered again — kept in his conscience
        with every photograph the moment covers."""
        if not self.available:
            return {"error": "no photographs are indexed yet"}
        with self._lock:
            row = self._row(moment_id)
            known = self._album()["moments"].get(moment_id)
            if not row and not known:
                return {"error": f"no such moment: {moment_id}"}
            self._remember(moment_id, "declined", row or {})
            self.c._save()
            if row:
                self.db.execute("UPDATE moments SET status='declined' WHERE id=?",
                                (moment_id,))
                self.db.commit()
        return {"declined": True, "moment_id": moment_id,
                "note": "Never raised again. Do not circle back or rephrase it."}

    def skip(self, moment_id: str) -> dict:
        """'Not now.' Nothing is decided: the moment goes to the back of the
        album and comes round again much later."""
        if not self.available:
            return {"error": "no photographs are indexed yet"}
        with self._lock:
            cur = self.db.execute("UPDATE moments SET asked_at=? WHERE id=?",
                                  (_now(), moment_id))
            self.db.commit()
        if cur.rowcount == 0:
            return {"error": f"no such moment: {moment_id}"}
        return {"skipped": True, "moment_id": moment_id,
                "note": "Not now is fine. It goes to the back of the album."}

    def progress(self) -> dict:
        if not self.available:
            return {"indexed": False}
        self.refresh()
        counts = dict(self.db.execute(
            "SELECT status, COUNT(*) FROM moments WHERE present=1 GROUP BY status"))
        stories = sum(int(m.get("stories", 0))
                      for m in self._album()["moments"].values())
        return {"indexed": True, "untold": counts.get("untold", 0),
                "told": counts.get("told", 0), "declined": counts.get("declined", 0),
                "stories": stories}

    def reopen(self, moment_id: str) -> dict:
        """The owner's terminal only: lift a 'rather not'. An engine can
        decline a moment, and never undo it; only he can. Nothing is
        removed — the moment and its photographs are kept, marked reopened."""
        m = self._album()["moments"].get(moment_id)
        if not m or m.get("status") != "declined":
            return {"error": f"no declined moment called {moment_id}"}
        m["status"] = "untold"
        m["reopened_at"] = _now()
        self.c._save()
        if self.available:
            with self._lock:
                self.db.execute("UPDATE moments SET status='untold', rev=2 WHERE id=?",
                                (moment_id,))
                self.db.commit()
        return {"reopened": moment_id}

    # ------------------------------------------------- the owner's own lists
    def keep_out(self, which: str, words: str) -> dict:
        """The owner's terminal only: keep a place, a country or a year out of
        the album ('never_ask') or off the wall ('never_on_the_wall')."""
        if which not in ("never_ask", "never_on_the_wall"):
            raise ValueError(which)
        lst = self._album()[which]
        added = [w.strip() for w in words.split(",")
                 if w.strip() and w.strip().lower() not in {x.lower() for x in lst}]
        lst.extend(added)
        if added:
            self.c._save()
        return {which: list(lst), "added": added}

    # -------------------------------------------------- what the wall hides
    def hidden(self) -> dict:
        """What the wall must not show, from his own decisions alone:
        every photograph in a declined moment (including one that joined it
        later), and the words on his 'never on the wall' list. Also the words
        his rules say not to raise unprompted, which keep 'on this day' from
        surfacing them by itself. Never writes anything."""
        shas: set[str] = set()
        album = self._album()
        for m in album["moments"].values():
            if m.get("status") == "declined":
                shas |= set(m.get("shas", []))
        if self.available:
            for m in self._compute():
                if m["status"] == "declined":
                    shas |= set(m["shas"])
        unprompted = set()
        for r in self.c.data.get("rules", []):
            if r.get("kind") == "reaction" and _PROHIBIT.search(str(r.get("instruction", ""))):
                unprompted |= {str(t).strip().lower() for t in r.get("tags", []) if str(t).strip()}
        return {"shas": shas,
                "off_wall": {str(w).strip().lower() for w in album["never_on_the_wall"]
                             if str(w).strip()},
                "unprompted": unprompted,
                "never_ask": {str(w).strip().lower() for w in album["never_ask"]
                              if str(w).strip()}}


def wall_rules(index_path: Path | str, conscience_data: dict | None) -> tuple[dict, Reminisce]:
    """The wall's view: what to hide, and a Reminisce to ask for a photo's
    tags. The conscience is only read, never written; in the index, at most
    the album's empty cache table is created."""
    rem = Reminisce(_DataOnly(conscience_data), None, index_path)
    return rem.hidden(), rem


# ------------------------------------------------------------------ CLI
def _interactive(rem: Reminisce) -> int:
    """Sit down with the album. One moment, one story, saved. The owner
    opened it himself, so it does not wait for trust to be built."""
    p = rem.next_prompt(owner_opened=True)
    if not p.get("moment_id"):
        print(f"\n  {p['note']}\n")
        return 0
    print(f"\n  {p['label']} — {p['photos']} photographs, {p['from']} to {p['to']}")
    print(f"  (on the wall, type:  {p['show_on_the_wall']})\n")
    print(f"  {p['ask']}")
    print("  Type your story. Blank line to finish.")
    print("  Type 'skip' for not now, or 'no' if you'd rather never talk about it.\n")
    lines = []
    while True:
        try:
            line = input("  > ")
        except EOFError:
            break
        if not line.strip():
            break
        word = line.strip().lower()
        if not lines and word in ("skip", "not now", "later", "pass"):
            rem.skip(p["moment_id"])
            print("\n  That's fine. It'll come round again another time.\n")
            return 0
        if not lines and word in ("no", "rather not", "never"):
            rem.decline(p["moment_id"])
            print("\n  Understood. I won't ask about that one again.\n")
            return 0
        lines.append(line)
    if not lines:
        print("\n  Nothing kept. It'll still be here next time.\n")
        return 0
    people = input("  Who was there? (names, comma-separated, or blank) > ").strip()
    r = rem.record(p["moment_id"], "\n".join(lines), people=people)
    if not r.get("kept"):
        print(f"\n  Not kept: {r.get('error')}\n")
        return 1
    print(f"\n  Kept — pinned to {r['pinned_to_photos']} photographs, privately.")
    if r["one_follow_up"]:
        print(f"  {r['one_follow_up']}")
    print()
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
    life = Life(c)
    rem = Reminisce(c, life, td / "idx")

    # clustering: Afghanistan Oct 2011 (4), Toronto Nov 2023 (3); the March
    # 2012 pair is below MIN_PHOTOS and the undated one never enters
    n = rem.refresh()
    ms = rem.moments()
    assert n == 2 and len(ms) == 2, ms
    assert ms[0]["country"] == "Afghanistan" and ms[0]["photos"] == 4, ms[0]
    assert "October 2011" in ms[0]["label"], ms[0]["label"]
    assert ms[1]["country"] == "Canada" and ms[1]["photos"] == 3, ms[1]

    # before anything has been shared, the album stays closed
    p0 = rem.next_prompt()
    assert p0["moment_id"] is None and "Not yet" in p0["note"], p0

    # a little shared in conversation: the album opens — on the ordinary,
    # recent moment, never on the war
    life.add_memory("I grew up in Pécs.")
    life.add_memory("I met Anna at a dance in 1972.")
    p = rem.next_prompt()
    assert p["moment_id"] == ms[1]["id"], p
    assert "3 photographs" in p["ask"] and "Canada" in p["ask"], p["ask"]
    assert p["show_on_the_wall"] == "Canada 2023"
    assert "photo_ids" not in p, "photo fingerprints offered to an engine"
    for bad in ("looks like", "wedding", "probably"):
        assert bad not in p["ask"], "the prompt guessed"

    # his words are kept verbatim, pinned to the moment, private
    story = "Cold that week, the light off the lake.\nAnna drove."
    r = rem.record(p["moment_id"], story, people="Anna")
    assert r["kept"] and r["pinned_to_photos"] == 3, r
    assert "photos" not in r["memory"]
    mem = c.data["memories"][-1]
    assert mem["text"] == story, "the story was altered"
    assert mem["visibility"] == "private" and mem["people"] == ["Anna"]
    assert f"moment:{p['moment_id']}" in mem["tags"] and "canada" in mem["tags"]
    assert len(c.data["album"]["moments"][p["moment_id"]]["shas"]) == 3
    assert r["one_follow_up"] == FOLLOW_UPS["feeling"], r["one_follow_up"]  # people + a sense word given
    assert rem.moments("told")[0]["id"] == p["moment_id"]

    # the story's people were omitted -> the follow-up asks who was there
    r2 = rem.record(p["moment_id"], "Second story, no names.")
    assert r2["one_follow_up"] == FOLLOW_UPS["people"]
    assert rem.moments("told")[0]["stories"] == 2

    # the war comes later, gently: trust deep enough and a story already told
    p1 = rem.next_prompt()
    assert p1["moment_id"] is None and "painful" in p1["note"], p1  # trust not deep yet
    life.add_person("Anna", "wife")
    life.add_person("Mike", "friend from the army")
    p2 = rem.next_prompt()
    assert p2["moment_id"] == ms[0]["id"], p2
    assert "painful" in p2["rule"], p2["rule"]
    assert rem.decline(p2["moment_id"])["declined"]
    assert "rather not" in rem.record(p2["moment_id"], "anyway")["error"]
    assert c.data["album"]["moments"][p2["moment_id"]]["status"] == "declined"

    # nothing left; refresh does not resurrect anything
    p3 = rem.next_prompt()
    assert p3["moment_id"] is None, p3
    rem.refresh()
    assert rem.progress() == {"indexed": True, "untold": 0, "told": 1,
                              "declined": 1, "stories": 2}, rem.progress()

    # no index at all -> a graceful answer, not a crash
    rem0 = Reminisce(c, Life(c), td / "nope")
    assert rem0.next_prompt()["moment_id"] is None
    assert rem0.progress() == {"indexed": False}

    import shutil
    shutil.rmtree(td, ignore_errors=True)
    print("\n  ✓ reminisce: trips clustered from dated+placed photos; the album")
    print("    stays closed until something is shared, opens on an ordinary")
    print("    moment, asks about the war only later and gently; the story is")
    print("    kept verbatim and pinned to its moment, one follow-up, 'rather")
    print("    not' kept in the conscience, nothing resurrected, no index handled.\n")
    return 0


def _owner_cli(argv: list[str]) -> int:
    from conscience import Conscience, StoreProblem
    from life import Life
    import access
    from selfcloud import SelfCloud
    why = home.problem()
    if why:                        # the drive is away: say so, change nothing
        print(f"\n  {why[0].upper() + why[1:]}.\n")
        return 1
    try:
        _c = Conscience()
    except StoreProblem as e:
        print(f"\n  {e.for_owner()}\n")
        return 1
    access.bind(SelfCloud(_c), "jefferey", announce=False)
    rem = Reminisce(_c, Life(_c))
    if argv and argv[0] in ("never-ask", "keep-off-wall"):
        words = " ".join(argv[1:]).strip()
        if not words:
            print("\n  Say what, for example:  never-ask Afghanistan\n")
            return 1
        key = "never_ask" if argv[0] == "never-ask" else "never_on_the_wall"
        r = rem.keep_out(key, words)
        what = "asked about in the album" if key == "never_ask" else "shown on the wall"
        print(f"\n  Done. These will not be {what}: {', '.join(r[key])}\n")
        return 0
    if argv and argv[0] == "reopen" and len(argv) > 1:
        r = rem.reopen(argv[1])
        print(f"\n  {r['error'] if 'error' in r else 'Opened again: ' + argv[1]}\n")
        return 0 if "reopened" in r else 1
    if argv and argv[0] == "list":
        a = rem._album()
        declined = [f"{m.get('label') or k} ({k})" for k, m in a["moments"].items()
                    if m.get("status") == "declined"]
        print("\n  Never asked about:  " + (", ".join(a["never_ask"]) or "nothing"))
        print("  Never on the wall:  " + (", ".join(a["never_on_the_wall"]) or "nothing"))
        print("  'Rather not':       " + (", ".join(declined) or "nothing") + "\n")
        return 0
    return _interactive(rem)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(_owner_cli(sys.argv[1:]))
