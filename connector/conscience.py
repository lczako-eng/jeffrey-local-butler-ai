"""
JEFFEREY Conscience Store
=========================

The persistent, user-owned core of JEFFEREY: priorities (not preferences),
facts, goals, and the correction log that teaches him why you decide.

Design rules (from the "To Be Built" specification v1.1):
- Values are stored separately from facts.
- Every learned priority carries a confidence score the user can see.
- Priorities are contextual (business travel != family health).
- Corrections are the curriculum: consistent evidence raises confidence,
  contradictions lower it and can flip the hierarchy.
- The store is a plain local JSON file: inspectable, editable, deletable,
  portable between AI engines. The intelligence is rented; this is owned.

Storage rules (the October 2026 stress test), because the product's headline
feature is a switch that cuts power, and its owners include people who will
never read a traceback:
- Reading never writes. The per-call access log lives in its own append-only
  file beside the store (conscience.access.jsonl), never inside it.
- Every write is atomic, locked, flushed all the way onto the drive, private
  to the owner's account, and copied into history — only when something
  actually changed.
- History is kept by time, not by count: every copy from the last day, the
  newest of each hour for a week and of each day for three months, and a
  copy pinned before anything destructive.
- A change made outside JEFFEREY (an edit by hand, an older copy put back)
  is noticed by its content, adopted and versioned — never silently undone.
- A file torn by a power cut recovers from history. A file with a mistake in
  it (usually a hand edit) is never replaced behind the owner's back: he is
  told, in plain words, which line.
- A failed save changes nothing, in memory either.

Owner commands (the owner's own terminal; no AI can run these):
    python connector/conscience.py check            how are my memories?
    python connector/conscience.py history          the copies kept
    python connector/conscience.py restore <n>      put copy <n> back
    python connector/conscience.py edit             change it by hand, checked
    python connector/conscience.py dismiss          I have read the notices
"""

from __future__ import annotations

import argparse
import calendar
import copy
import functools
import hashlib
import json
import math
import os
import re
import secrets
import stat as _stat
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import fcntl  # POSIX only; Windows falls back to no cross-process lock
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

import home
import grounding
import provenance
from version import __version__, newer as _newer
DEFAULT_STORE = home.conscience_path()   # on the drive if one is plugged in
# The newest JEFFEREY that ever saved this life. A copy older than that
# refuses to touch it (I-21): an old copy once stored a card number with
# none of the newer protections.
VERSION_KEY = "_jefferey_version"

# ------------------------------------------------------------------ history
# Copies of the store kept beside it, so a mistake or a power cut can be
# undone. An earlier version kept "the last twenty writes" and every read
# wrote, so twenty copies lasted about twenty questions: one bad forget was
# permanent within minutes. Now they are kept by time.
HISTORY_KEEP = 20            # the newest twenty, however old
HISTORY_RECENT_HOURS = 24    # every copy from the last day…
HISTORY_RECENT_MAX = 200     # …up to this many
HISTORY_HOURLY_DAYS = 7      # then the newest of each hour for a week
HISTORY_DAILY_DAYS = 90      # and the newest of each day for three months
PIN_KEEP_DAYS = 90           # a copy pinned before a destructive change
PIN_MAX = 500
NOTICE_DAYS = 14             # how long a notice keeps being shown
# A file torn by a power cut was written by JEFFEREY, which copies every
# write into history a moment later. A damaged file newer than its newest
# copy by more than this was changed by someone else — usually by hand.
TEAR_WINDOW_S = 2.0

_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)

_SAVE_FAILED = ("JEFFEREY could not save to the drive just now — it may be full, "
                "unplugged or read-only. Nothing was changed, and nothing is "
                "remembered that is not on the drive.")


# --------------------------------------------------------------- problems
class StoreProblem(RuntimeError):
    """Something is wrong with the memory file or the drive it lives on.

    `str(e)` is plain English an owner can act on, and never contains a file
    path, because it may be handed to a rented engine as a tool result. The
    path, for the owner's own screen only, is `e.where`."""

    tell_the_user = ("Tell the owner plainly, in a sentence or two, what this "
                     "says. Never say anything was saved or read when it was "
                     "not, and do not try to get round it another way.")

    def __init__(self, plain: str, where: Path | str | None = None):
        super().__init__(plain)
        self.plain = plain
        self.where = str(where) if where else None

    def for_owner(self) -> str:
        return self.plain + (f"\n     (the file: {self.where})" if self.where else "")

    def as_result(self, tool: str) -> dict:
        """The problem as a RESULT the model must report — never a crash."""
        return {"refused": True, "tool": tool, "reason": self.plain,
                "tell_the_user": self.tell_the_user}


class ConscienceCorrupt(StoreProblem):
    """The store on disk is unreadable and could not be safely replaced.

    Raised instead of silently starting from an empty conscience — losing a
    life quietly is worse than refusing to start loudly.
    """


class ConscienceNeedsFixing(ConscienceCorrupt):
    """The file is complete but has a mistake in it — usually an edit by
    hand. JEFFEREY does not swap it for an older copy (that would silently
    undo the owner's edit, and re-send whatever he had deleted); he says
    where the mistake is."""


class ConscienceConflict(StoreProblem):
    """The file changed since this process read it — another engine wrote
    it, or the owner edited it.

    Refusing the write is the point: two surfaces each holding the whole
    store in memory would otherwise overwrite each other's changes, and a
    surface holding an old copy would undo the owner's edit.
    """


class ConscienceSaveFailed(StoreProblem):
    """The drive refused the write (full, unplugged, read-only). Nothing
    changed — in memory either, so nothing is served as remembered that is
    not on the drive."""


class DriveNotHere(StoreProblem):
    """The owner's Self-Cloud drive is expected but is not here (or is not
    his). Nothing is read from, or written to, anywhere else — and what this
    process held in memory of the life is let go (I-08)."""


class ConscienceTooNew(ConscienceCorrupt):
    """The memories were last saved by a newer JEFFEREY than this copy."""


class _Unreadable(ValueError):
    """Why bytes are not a usable store, in plain words, and whether that
    looks like a power-cut tear (`torn`) or certainly is one (`certain`)."""

    def __init__(self, plain: str, torn: bool = False, certain: bool = False):
        super().__init__(plain)
        self.plain, self.torn, self.certain = plain, torn, certain


# How values are learned (October 2026, I-48). For and against are counted
# separately, and confidence comes from the counts: (for + 1) / (for +
# against + 2) for a value learned from his choices. A value he STATED
# counts like four observations at the confidence he stated, and is never
# reversed by inference: a choice that contradicts it raises a question for
# him instead. A learned value turns round only when the evidence against
# outweighs the evidence for. One correction repeated in one conversation
# (an AI in a loop) counts once.
_STATED_WEIGHT = 4
ENGINE_CONFIDENCE_CAP = 0.6   # the most an AI may say it is sure of (I-25)
UNCONFIRMED_CAP = 0.8         # the most evidence alone may reach; above it, only
                              # what the owner set or confirmed himself
DEDUP_SECONDS = 600           # the same correction within ten minutes: once
FACT_VISIBILITY = ("private", "engines", "family", "legacy")
LIFE_VISIBILITY = ("private", "family", "legacy")
FACTS_PAGE, FACTS_MAX = 100, 500       # get_conscience
BASIS_FACTS, BASIS_MAX, BASIS_PRIORITIES = 10, 25, 10   # explain_basis


def _page(limit, offset, default: int, most: int) -> tuple[int, int]:
    """A page of a long answer: (limit, offset), whatever was sent."""
    try:
        lim = int(limit) if limit is not None else default
    except (TypeError, ValueError):
        lim = default
    try:
        off = int(offset or 0)
    except (TypeError, ValueError):
        off = 0
    return max(1, min(most, lim)), max(0, off)


def _refusal(tool: str, reason: str) -> dict:
    return {"refused": True, "tool": tool, "reason": reason,
            "tell_the_user": "Nothing was stored. Say plainly what was missing."}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@functools.lru_cache(maxsize=8192)
def _stamp_seconds(stamp: str) -> float | None:
    """'20261014T101500Z' → seconds since 1970 (UTC), or None."""
    try:
        return float(calendar.timegm(time.strptime(stamp, "%Y%m%dT%H%M%SZ")))
    except ValueError:
        return None


def _when(ts: float) -> str:
    """A moment, the way a person says it: 'on 14 October 2026 at 10:15'."""
    t = time.localtime(ts)
    return f"on {t.tm_mday} {time.strftime('%B %Y at %H:%M', t)}"


# ------------------------------------------------------- durable, private IO
def _full_fsync(fd: int) -> None:
    """Make what was written survive a power cut. On a Mac, fsync() only hands
    the data to the drive, which may still hold it in its cache; F_FULLFSYNC
    asks the drive to put it on the platter or flash. Elsewhere fsync is it."""
    flag = getattr(fcntl, "F_FULLFSYNC", None) if fcntl is not None else None
    if flag is not None:
        try:
            fcntl.fcntl(fd, flag)
            return
        except OSError:
            pass                              # some drives refuse it: fall back
    os.fsync(fd)


def _sync_dir(d: Path) -> None:
    """Make a rename in this folder durable too."""
    try:
        fd = os.open(d, os.O_RDONLY)
    except OSError:
        return                                # not every platform allows this
    try:
        _full_fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _make_dir(d: Path) -> None:
    """A folder only the owner's account can open (0700). Never on a drive
    that is not there: re-making a pulled drive's folders on the Mac's own
    disk is how an empty second life used to begin (I-08)."""
    if d.is_dir():
        return
    home.guard(d)
    d.parent.mkdir(parents=True, exist_ok=True)
    try:
        d.mkdir(mode=0o700)
    except FileExistsError:
        pass


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        view = view[n:]


def _write_atomic(path: Path, payload: bytes) -> None:
    """One atomic, durable, private write: a fresh temp file with a unique
    name (created 0600, never through a symlink), full fsync, rename, fsync
    the folder. Readers see the old file or the new one, never half."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.",
                               suffix=".tmp")
    try:
        try:
            _write_all(fd, payload)
            _full_fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _sync_dir(path.parent)


class _FileLock:
    """Exclusive cross-process lock on a small file beside what it guards.
    Never nested within one process (flock would wait on itself). On a drive
    that cannot be written nothing can be saved anyway, so reading goes ahead
    without the lock rather than failing."""

    def __init__(self, path: Path):
        self.path, self.fd = path, None

    def __enter__(self):
        if fcntl is None:
            return self
        try:
            # O_NOFOLLOW so a symlink here cannot aim the lock at one of the
            # owner's files, and no O_TRUNC so opening never empties anything.
            self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | _O_NOFOLLOW,
                              0o600)
        except OSError:
            self.fd = None
            return self
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None
        return False


# --------------------------------------------------------- append-only logs
class AppendLog:
    """An append-only JSON-lines file with its own lock: one line per event,
    never rewritten, rotated when it grows (conscience.access.jsonl, then
    .1.jsonl, .2.jsonl … oldest dropped after KEEP files).

    The Self-Cloud access log lives here. It used to live inside the store,
    so every question any engine asked — even a refused one — rewrote the
    whole life and pushed a backup copy out of history."""

    MAX_BYTES = 5 * 1024 * 1024
    KEEP = 20

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.failures = 0
        self._warned = False

    @property
    def _lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".lock")

    def _rotated(self, i: int) -> Path:
        return self.path.with_name(f"{self.path.stem}.{i}{self.path.suffix}")

    def files(self) -> list[Path]:
        """The active file, then the rotated ones, newest first."""
        return [self.path] + [self._rotated(i) for i in range(1, self.KEEP + 1)]

    def _rotate_locked(self) -> None:
        try:
            if self.path.stat().st_size < self.MAX_BYTES:
                return
        except FileNotFoundError:
            return
        self._rotated(self.KEEP).unlink(missing_ok=True)
        for i in range(self.KEEP - 1, 0, -1):
            if self._rotated(i).exists():
                os.replace(self._rotated(i), self._rotated(i + 1))
        os.replace(self.path, self._rotated(1))

    def _append_locked(self, lines: list[bytes]) -> None:
        fd = os.open(self.path, os.O_RDWR | os.O_APPEND | os.O_CREAT | _O_NOFOLLOW,
                     0o600)
        try:
            blob = b"".join(lines)
            size = os.fstat(fd).st_size
            # A line torn by a power cut must not swallow the next one.
            if size and hasattr(os, "pread") and os.pread(fd, 1, size - 1) != b"\n":
                blob = b"\n" + blob
            _write_all(fd, blob)
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _line(entry) -> bytes:
        return (json.dumps(entry, sort_keys=True) + "\n").encode("ascii")

    def append(self, entry: dict) -> bool:
        """Write one event. A log that cannot be written does not stop the
        call it records (the egress door still logs every send); it is
        counted, said once on the console, and shown as a notice."""
        try:
            _make_dir(self.path.parent)
            with _FileLock(self._lock_path):
                self._rotate_locked()
                self._append_locked([self._line(entry)])
            return True
        except OSError as exc:
            self.failures += 1
            if not self._warned:
                self._warned = True
                print(f"  ⚠  Could not write the access log {self.path} "
                      f"({exc.strerror or exc}). The request went ahead; it is "
                      f"not in that log.", file=sys.stderr)
            return False

    @staticmethod
    def _read(p: Path) -> list[dict]:
        try:
            raw = p.read_bytes()
        except OSError:
            return []
        out = []
        for line in raw.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue                       # a torn line from a power cut
            if isinstance(e, dict):
                out.append(e)
        return out

    def tail(self, limit: int = 30) -> list[dict]:
        """The newest `limit` events, newest first."""
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 30
        out: list[dict] = []
        for p in self.files():
            if len(out) >= limit:
                break
            if not p.exists():
                continue
            for e in reversed(self._read(p)):
                out.append({k: v for k, v in e.items() if k != "from_store"})
                if len(out) >= limit:
                    break
        return out

    def import_legacy(self, entries: list) -> bool:
        """Move events that used to be kept inside the store into this file,
        once: an event already imported is not imported twice, however often
        the old store is read. True when every one of them is safely here."""
        def key(e) -> str:
            if isinstance(e, dict):
                e = {k: v for k, v in e.items() if k != "from_store"}
            return json.dumps(e, sort_keys=True)
        try:
            _make_dir(self.path.parent)
            with _FileLock(self._lock_path):
                seen: Counter = Counter()
                for p in reversed(self.files()):
                    for e in self._read(p):
                        if e.get("from_store"):
                            seen[key(e)] += 1
                new = []
                for e in entries:
                    k = key(e)
                    if seen[k] > 0:
                        seen[k] -= 1
                        continue
                    row = dict(e) if isinstance(e, dict) else {"entry": e}
                    row["from_store"] = True
                    new.append(self._line(row))
                if new:
                    self._append_locked(new)
            return True
        except OSError:
            return False


# --------------------------------------------------------------- authority
# What an AI may do in the world for the owner (the Act tier), and what it
# may never do whatever anyone sets. October 2026 (I-04, I-06, I-44, I-45):
# the old gate trusted one self-reported amount, skipped the cap when the
# amount was missing, negative or NaN, let ten $99 orders through a $100
# cap, could be set to 'act' on wires and gift cards, and wrote approvals
# nowhere. Nothing irreversible happens because an AI asked.
PERIODS = {"day": 86400, "week": 7 * 86400, "month": 30 * 86400}
PERIOD_WORDS = {"day": "any 24 hours", "week": "any 7 days", "month": "any 30 days"}
LEGACY_PERIOD = "month"        # a limit saved before limits had a period
DEFAULT_CURRENCY = "CAD"
AUTH_MINUTES = 30              # an approval is used once, within this long

# Never 'act', at any level, whatever anyone sets: JEFFEREY never moves
# money, never speaks in the owner's voice, never lets anyone into the house.
_NEVER = (
    (re.compile(r"\b(?:e ?transfers?|transfers?|wires?|wiring|interac|remittances?"
                r"|western ?union|money ?grams?|money ?orders?)\b"),
     "moving money from one account to another"),
    (re.compile(r"\b(?:gift ?cards?|prepaid ?cards?|itunes|google ?play|steam ?cards?"
                r"|vouchers?)\b"), "buying gift cards"),
    (re.compile(r"\b(?:crypto\w*|bitcoins?|btc|ethereum|usdt|tether)\b"),
     "crypto-currency"),
    (re.compile(r"\b(?:phone ?calls?|calls?|calling|voice(?! ?mail)\w*|intercoms?|doorbells?)\b"),
     "speaking for the owner on the phone, in his voice or at the door"),
    (re.compile(r"\b(?:unlock\w*|locks?|alarms?|garage ?doors?|garage ?openers?|doors?)\b"),
     "letting anyone into the house"),
)
# Inside a description, under any category, only the unmistakable ones.
_NEVER_IN_TEXT = (
    (re.compile(r"\b(?:e-?\s?transfer\w*|wire\s+(?:transfer|\$|money|funds|it|the)\w*"
                r"|interac|western\s?union|money\s?gram|money\s?order)"),
     "moving money from one account to another"),
    (re.compile(r"\bgift\s?cards?\b"), "buying gift cards"),
    (re.compile(r"\b(?:bitcoin|crypto\w*|btc|ethereum|usdt)\b"), "crypto-currency"),
    (re.compile(r"\b(?:unlock\w*|disarm\w*|open\s+the\s+(?:front|back|side|garage)\s+door)"),
     "letting anyone into the house"),
    (re.compile(r"\b(?:phone\s?call|place\s+a\s+call|in\s+(?:my|his|her)\s+voice)"),
     "speaking for the owner on the phone or in his voice"),
)
# A category about money: 'act' there needs a limit.
_MONEYISH = re.compile(
    r"buy|purchas|pay|bill|shop|grocer|subscri|order|spend|money|fund|donat|gift"
    r"|charit|rent|fee|invest|bank|card|travel|book|ticket|insur|tax|loan|mortgage"
    r"|deliver|food|meal|restaurant|household|suppl|pharm|store|amazon|cash|dollar"
    r"|price|cost")
# A category about selling: 'act' there needs a lowest price, not a limit.
_SALEISH = re.compile(r"sell|\bsale|auction|marketplace|listing")
# A commitment that repeats or has a minimum term is the owner's to make.
_RECURRING = re.compile(
    r"/\s?(?:mo|month|yr|year|wk|week)\b|\bper\s+(?:month|year|week|annum)\b"
    r"|\b(?:a|each|every)\s+(?:month|year|week)\b|\bsubscri\w*|\bauto-?\s?renew\w*"
    r"|\b(?:monthly|yearly|annual|annually|weekly)\s+(?:plan|fee|payment|charge|bill\w*"
    r"|subscription|membership|contract|instal\w*|donation)"
    r"|\bbilled\s+(?:monthly|yearly|annually|weekly)|\brecurring\b|\bminimum\s+term\b"
    r"|\binstal(?:l)?ments?\b"
    r"|\b\d+[- ]?(?:month|year)s?\s+(?:minimum|contract|term|commitment)")
_CURRENCY_TEXT = (("GBP", re.compile(r"£|\bgbp\b|\bpounds?\s+sterling\b")),
                  ("EUR", re.compile(r"€|\beur\b|\beuros?\b")),
                  ("USD", re.compile(r"\bus\s?\$|\busd\b|\bu\.s\.\s?dollars?\b"
                                     r"|\bamerican\s+dollars?\b")),
                  ("JPY", re.compile(r"¥|\bjpy\b|\byen\b")),
                  ("CAD", re.compile(r"\bcad\b|\bc\$|\bcanadian\s+dollars?\b")))
_MONEY_TEXT = re.compile(r"[$£€¥]\s?\d|\d\s?(?:\$|dollars?\b|bucks\b|cad\b|usd\b|eur\b|gbp\b)")
# What an engine may not write as an act's outcome: these are JEFFEREY's own
# words, and a forged 'approved by owner' looked exactly like a real one.
_RESERVED_OUTCOME = re.compile(
    r"permission|\ballowed\b|\bdenied\b|\bapprov\w*|\bauthori[sz]\w*|\bowner\b"
    r"|\bput\s+back\b|\berased?\b|\bremoved\s+list\b|\brefused\b", re.I)
# Signs that an 'opportunity' is a scam someone wants put in front of him.
_SCAM_SIGNS = (
    (re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"),
     "a phone number to call"),
    (re.compile(r"\bgift\s?cards?\b"), "gift cards"),
    (re.compile(r"\b(?:card\s+number|pin\b|cvv|security\s+code|password|one[- ]time\s+code"
                r"|verification\s+code)"), "asks for card details, a PIN or a code"),
    (re.compile(r"\b(?:read|give|tell)\s+(?:them|him|her|us)\s+(?:the|your)\b"),
     "asks him to read something out to someone"),
    (re.compile(r"\b(?:wire|e-?transfer|bitcoin|crypto)\w*"), "asks to move money"),
)


def _real_number(x) -> float | None:
    """A finite number, or None. True/False, text, NaN and infinity are not
    prices — NaN > cap is False, which is how NaN used to pass the cap."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def _money(x: float, cur: str = DEFAULT_CURRENCY) -> str:
    return (f"${x:,.2f} {cur}" if cur in ("CAD", "USD", "AUD", "NZD")
            else f"{x:,.2f} {cur}")


def _currency_named(text: str) -> str | None:
    t = (text or "").lower()
    for code, rx in _CURRENCY_TEXT:
        if rx.search(t):
            return code
    return None


def _who() -> tuple[str, str]:
    """(who is acting, through which door) — for every line of the record."""
    try:
        import access
        return access.who(), access.surface()
    except Exception:
        return "unknown", "unknown"


# --------------------------------------------------------------- the store
class Conscience:
    _SHAPE = ("facts", "priorities", "goals", "corrections", "permissions",
              "actions", "observations", "opportunities")
    _LISTS = ("facts", "priorities", "goals", "corrections", "actions",
              "observations", "opportunities", "_notices")
    _CORE = ("owner", "_rev") + _SHAPE
    # A section that used to live in the store and now lives beside it.
    _LEGACY_ACCESS = "selfcloud_access_log"
    # Every item in these sections carries a stable id, so a thing can be
    # named exactly ("forget f-3a9c1e") instead of by a few letters of its
    # text — a few letters once took a whole life with them. Files written
    # before ids existed get them in memory as they are read, worked out from
    # each item's own content (so every surface works out the same id), and
    # keep them from the next real save on. Reading never writes.
    ID_PREFIX = {"facts": "f", "priorities": "pr", "goals": "g",
                 "corrections": "c", "observations": "ob", "opportunities": "op",
                 "memories": "m", "media": "md", "people": "p", "rules": "r",
                 "conscience_included": "in"}

    def __init__(self, path: Path | str = DEFAULT_STORE):
        self._init_fields(path)
        self._tighten_modes()
        self._load()

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "owner": None,
            "facts": [],        # [{fact, category, added}]
            "priorities": [],   # [{context, higher, lower, confidence, evidence, updated}]
            "goals": [],        # [{goal, added, active}]
            "corrections": [],  # [{context, suggested, chosen, inferred, added}]
            "permissions": {},  # {category: {level, cap, updated}} — Operational AI
            "actions": [],      # [{category, description, amount, outcome, added, ts}]
            "observations": [],   # [{note, category, added, ts}] — Opportunity Engine
            "opportunities": [],  # [{what, ..., score, status, added, ts}]
            "_rev": 0,          # bumped on every write; orders history
        }

    def _init_fields(self, path: Path | str) -> None:
        self.path = Path(path).expanduser()
        self.data: dict[str, Any] = self._defaults()
        self._rev_seen = 0
        self._stat: tuple[int, int, int] | None = None
        # sha256 of the bytes this process last read from or wrote to disk:
        # how a change made anywhere else — another engine, a hand edit — is
        # recognised, whatever its revision number says.
        self._disk_sha: str | None = None
        # Those contents as JEFFEREY writes them: the point a failed save
        # rolls back to, and the yardstick for "did anything change?".
        self._clean: bytes = self._canon(self.data)
        self._unavailable: ConscienceCorrupt | None = None
        self._runtime_notices: dict[str, str] = {}
        self.access_log = AppendLog(self.path.with_name(self.path.stem + ".access.jsonl"))
        # A store opened where home.py says the life lives follows it: when
        # the drive goes, memory is let go; when it comes back — under any
        # name — the store is opened there again (I-08).
        self._follows_home = (self.path == Path(DEFAULT_STORE).expanduser()
                              and not os.environ.get("JEFFEREY_CONSCIENCE_PATH"))
        self._left = False
        if self._follows_home:
            home.watch(self._drive_left)

    # ------------------------------------------------------ the drive comes and goes
    def _forget_in_memory(self) -> None:
        """Hold nothing of the life in this process (the same dict object, so
        every module holding it sees the empty one)."""
        self._replace_data(self._defaults())
        self._clean = self._canon(self.data)
        self._disk_sha, self._stat, self._rev_seen = None, None, 0

    def _drive_left(self) -> None:
        self._forget_in_memory()
        self._left = True

    def _relocate(self, path: Path) -> None:
        """The life is somewhere else now (the drive came back under another
        name, or was plugged in after this process started): open it there."""
        self._forget_in_memory()
        self.path = Path(path)
        self.access_log = AppendLog(self.path.with_name(self.path.stem + ".access.jsonl"))
        self._unavailable, self._runtime_notices, self._left = None, {}, False
        self._tighten_modes()
        try:
            self._load()
        except ConscienceCorrupt as exc:
            self._unavailable = exc
            raise

    def _follow_home(self) -> bool:
        """Before every call: is the life where this store is? Raises
        DriveNotHere, in the owner's words, when it is nowhere."""
        why = home.problem()
        if why:
            if not self._left:
                self._drive_left()
            raise DriveNotHere(why[0].upper() + why[1:] + ".")
        want = home.conscience_path()
        if want != self.path:
            self._relocate(want)
            return True
        if self._left:
            self._left = False
            try:
                self._load()
            except ConscienceCorrupt as exc:
                self._unavailable = exc
                raise
            return True
        return False

    @classmethod
    def for_surface(cls, path: Path | str | None = None) -> "Conscience":
        """Open the store for a surface (MCP, HTTP, the terminal). A damaged
        store must not look like a crash — Claude would only show a dead
        connection. So the surface still starts, every tool answers with the
        plain explanation, and once the owner fixes or restores the file the
        next call picks it up without a restart."""
        path = DEFAULT_STORE if path is None else path
        try:
            return cls(path)
        except ConscienceCorrupt as exc:
            c = cls.__new__(cls)
            c._init_fields(path)
            c._unavailable = exc
            print(f"\n  ⚠  {exc.for_owner()}\n", file=sys.stderr)
            return c

    # ------------------------------------------------------ many engines, one life
    #
    # The owner runs more than one engine at once: Claude Desktop keeps its
    # JEFFEREY process alive for as long as the app is open, while he talks to
    # Hermes on the same Mac, or a Custom GPT calls in. Each is a separate
    # process holding the conscience in memory. Every surface calls refresh()
    # before each tool call, so a surface picks up what the others wrote —
    # and what the owner changed by hand.

    @staticmethod
    def _key(st: os.stat_result) -> tuple[int, int, int]:
        return (st.st_ino, st.st_mtime_ns, st.st_size)

    def _mark(self) -> None:
        try:
            self._stat = self._key(self.path.stat())
        except OSError:
            self._stat = None

    def refresh(self) -> bool:
        """Re-read the store if anything changed it since this process last
        looked. Cheap when nothing did (one stat). Returns True if memory now
        holds something new.

        Raises a StoreProblem — which every surface turns into a plain
        result — when the file has become unreadable: serving the old copy
        from memory would undo, and re-send, whatever the owner just deleted
        by hand."""
        if self._follows_home and self._follow_home():
            return True
        if self._unavailable is not None:
            try:
                with self._lock():
                    self._open_locked()
            except ConscienceCorrupt as exc:
                self._unavailable = exc
                raise
            self._unavailable = None
            return True
        try:
            st = self.path.stat()
        except OSError:
            return False
        # Every save is a fresh file renamed into place, so the inode changes
        # on each write — this stays right on disks that keep 1-second times.
        if self._stat == self._key(st):
            return False
        try:
            raw = self.path.read_bytes()
        except OSError:
            return False
        if self._disk_sha is not None and _sha(raw) == self._disk_sha:
            self._stat = self._key(st)
            return False
        with self._lock():
            return self._open_locked()

    # ------------------------------------------------------------ storage
    @property
    def history_dir(self) -> Path:
        return self.path.parent / (self.path.stem + ".history")

    @property
    def pinned_dir(self) -> Path:
        return self.history_dir / "pinned"

    @property
    def _lock_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".lock")

    def _lock(self) -> _FileLock:
        """Exclusive cross-process lock, as a context manager."""
        return _FileLock(self._lock_path)

    @staticmethod
    def _snap_rev(p: Path) -> int:
        """The revision baked into a copy's name. Ordering by the TIME in the
        name would let a clock change make recovery pick an older life."""
        try:
            return int(p.stem.rsplit("-", 1)[-1])
        except ValueError:
            return -1

    @staticmethod
    def _snap_time(p: Path) -> float:
        """When a copy was made: the UTC stamp in its name (copying a file
        changes its mtime, not its name)."""
        parts = p.stem.rsplit("-", 2)
        t = _stamp_seconds(parts[1]) if len(parts) == 3 else None
        if t is not None:
            return t
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    def _pin_label(self, p: Path) -> str:
        prefix = p.stem.rsplit("-", 2)[0]
        stem = self.path.stem + "-"
        return (prefix[len(stem):] if prefix.startswith(stem) else prefix).replace("_", " ")

    @staticmethod
    def _files_in(d: Path) -> list[Path]:
        try:
            return [p for p in d.glob("*.json") if p.is_file()]
        except OSError:
            return []

    def _snapshot_files(self) -> list[Path]:
        """The ordinary copies, newest revision first."""
        return sorted(self._files_in(self.history_dir),
                      key=lambda p: (self._snap_rev(p), self._snap_time(p)),
                      reverse=True)

    def _pinned_files(self) -> list[Path]:
        """Copies pinned before something destructive, newest first."""
        return sorted(self._files_in(self.pinned_dir), key=self._snap_time,
                      reverse=True)

    def _history_files(self) -> list[Path]:
        """Every copy, ordinary and pinned, newest revision first."""
        return sorted(self._files_in(self.history_dir) + self._files_in(self.pinned_dir),
                      key=lambda p: (self._snap_rev(p), self._snap_time(p)),
                      reverse=True)

    _snapshots = _history_files

    def _damaged_copies(self) -> list[Path]:
        try:
            return sorted(p for p in self.path.parent.iterdir()
                          if p.name.startswith(self.path.name + ".corrupt"))
        except OSError:
            return []

    # -------------------------------------------------------- what is a life
    @classmethod
    def _validate(cls, obj) -> dict:
        """`[]`, `{}` and `{"_rev": 3}` all parse as JSON and none of them is
        a life; neither is a file whose facts are `null`. Anything that is
        not recognisably a conscience is unreadable, so it never quietly
        replaces one. The reasons are written for the owner."""
        if not isinstance(obj, dict):
            raise ValueError("it does not hold memories (its outermost part "
                             f"is a {type(obj).__name__}, not {{ … }})")
        if "_rev" in obj:
            rev = obj["_rev"]
            if not isinstance(rev, int) or isinstance(rev, bool) or rev < 0:
                raise ValueError("its revision number ('_rev') is not a whole number")
            if not any(k in obj for k in cls._SHAPE):
                raise ValueError("it has none of the usual sections (facts, "
                                 "priorities, goals …)")
        elif sum(1 for k in cls._SHAPE if k in obj) < 3:
            raise ValueError("it does not look like a memory file (too few of "
                             "the usual sections)")
        for k in cls._LISTS:
            if k in obj and not isinstance(obj[k], list):
                raise ValueError(f"the '{k}' section should be a list, in "
                                 "square brackets [ ]")
        if "permissions" in obj and not isinstance(obj["permissions"], dict):
            raise ValueError("the 'permissions' section should be in curly "
                             "brackets { }")
        for i, f in enumerate(obj.get("facts") or []):
            if not isinstance(f, dict) or not isinstance(f.get("fact"), str):
                raise ValueError(f"fact number {i + 1} should look like "
                                 '{"fact": "…"}')
        return obj

    @classmethod
    def _parse(cls, raw: bytes) -> dict:
        """Bytes → a validated store, or _Unreadable saying why in plain words.
        The bytes are decoded INSIDE this check: a file cut in the middle of
        'ó' (Czakó, Montréal) is a torn file to recover, not a crash."""
        if not raw.strip():
            raise _Unreadable("the file is empty", torn=True, certain=True)
        if b"\x00" in raw:
            line = raw[:raw.index(b"\x00")].count(b"\n") + 1
            raise _Unreadable(f"it is damaged from line {line} on, the way a "
                              "power cut can leave a file", torn=True, certain=True)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            if e.end >= len(raw):
                raise _Unreadable("it stops in the middle of a letter, the way "
                                  "a power cut can leave a file",
                                  torn=True, certain=True) from None
            line = raw[:e.start].count(b"\n") + 1
            raise _Unreadable(f"line {line} holds a character JEFFEREY cannot "
                              "read (the file may have been saved in the wrong "
                              "text format)") from None
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            if e.msg.startswith("Unterminated string") or e.pos >= len(text.rstrip()):
                raise _Unreadable("it stops part-way through, the way a power "
                                  "cut can leave a file", torn=True) from None
            raise _Unreadable(f"there is a mistake on line {e.lineno}, near "
                              f"character {e.colno} ({e.msg})") from None
        try:
            return cls._validate(obj)
        except ValueError as e:
            raise _Unreadable(str(e)) from None

    @staticmethod
    def _rev_of(obj: dict) -> int:
        r = obj.get("_rev", 0)
        return r if isinstance(r, int) and not isinstance(r, bool) else 0

    @classmethod
    def _canon(cls, data: dict) -> bytes:
        """The store exactly as JEFFEREY writes it. Empty sections that other
        modules create on start-up are left out, so starting never makes a
        file look changed."""
        body = {k: v for k, v in data.items()
                if k in cls._CORE or not (isinstance(v, (list, dict)) and not v)}
        try:
            return json.dumps(body, indent=2, ensure_ascii=False).encode("utf-8")
        except UnicodeEncodeError:
            # Half of an emoji (a lone surrogate) cannot be written as UTF-8.
            # Escaped, it round-trips exactly and poisons nothing.
            return json.dumps(body, indent=2).encode("ascii")

    # ------------------------------------------------- memory ⇄ disk, safely
    def _replace_data(self, obj: dict) -> None:
        """Make memory hold `obj`. Sections another module created in memory
        (people, rules, grants…) that `obj` lacks must still exist, empty, or
        the next call into that module fails on a missing key."""
        sections = {k: type(v)() for k, v in self.data.items()
                    if isinstance(v, (list, dict))}
        # A copy all the way down: ids are added below, and the parsed file
        # the caller holds must stay exactly what is on disk.
        new = copy.deepcopy(obj)
        self._absorb_legacy(new)
        self.data.clear()
        self.data.update(new)
        for k, v in sections.items():
            self.data.setdefault(k, v)
        self._ensure_ids()
        self._migrate()
        self._rev_seen = self._rev_of(new)

    def _migrate(self) -> None:
        """Older shapes, brought up to date in memory as they are read (the
        next real save keeps them; reading never writes). October 2026: the
        caretaker key gains the two scopes that every key used to have
        implicitly (selfcloud.migrate_grants)."""
        try:
            import selfcloud
            selfcloud.migrate_grants(self.data)
        except Exception:
            pass
        self._migrate_who_said_what()

    def _migrate_who_said_what(self) -> None:
        """October 2026 (I-10, I-11, I-25, I-48): facts learn what kind of
        private they are and who may see them; values count for and against
        separately; people get a visibility (private, like everything else
        that was never marked). Whatever an older file holds is kept and
        still read; what it lacks is worked out here, in memory — the next
        real save keeps it. Nothing is dropped."""
        for f in self.data.get("facts") or []:
            if not isinstance(f, dict):
                continue
            if not isinstance(f.get("sensitivity"), list):
                f["sensitivity"] = grounding.sensitivity(f.get("fact", ""),
                                                         f.get("category", ""))
            if f.get("visibility") not in FACT_VISIBILITY:
                f["visibility"] = "private" if f["sensitivity"] else "engines"
            if not isinstance(f.get("source"), dict):
                f["source"] = dict(provenance.UNKNOWN_SOURCE)
            if f.get("status") not in ("confirmed", "pending"):
                f["status"] = "confirmed"
        for p in self.data.get("priorities") or []:
            if not isinstance(p, dict):
                continue
            if not isinstance(p.get("for"), int):
                try:
                    p["for"] = max(1, int(p.get("evidence") or 1))
                except (TypeError, ValueError):
                    p["for"] = 1
            if not isinstance(p.get("against"), int):
                p["against"] = 0
            p.setdefault("stated", False)
            if not isinstance(p.get("source"), dict):
                p["source"] = dict(provenance.UNKNOWN_SOURCE)
            if p.get("status") not in ("confirmed", "pending"):
                p["status"] = "confirmed"
        for section in ("people", "memories", "media"):
            for it in self.data.get(section) or []:
                if isinstance(it, dict) and it.get("visibility") not in LIFE_VISIBILITY:
                    it["visibility"] = "private"

    def _ensure_ids(self) -> None:
        """Give every item in ID_PREFIX's sections a stable, unique id (see
        there). An id already present is kept; a missing or repeated one is
        worked out from the item's content, so two processes reading the same
        file agree on it. Changes memory only; the next save keeps them."""
        for section, prefix in self.ID_PREFIX.items():
            items = self.data.get(section)
            if not isinstance(items, list) or not items:
                continue
            used: set[str] = set()
            need = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                i = it.get("id")
                if isinstance(i, str) and i.strip() and i not in used:
                    used.add(i)
                else:
                    need.append(it)
            seen: Counter = Counter()
            for it in need:
                body = json.dumps({k: v for k, v in it.items() if k != "id"},
                                  sort_keys=True, ensure_ascii=False, default=str)
                base = _sha(f"{section}\0{body}".encode("utf-8"))
                n = seen[base]
                seen[base] += 1
                while True:
                    h = base if n == 0 else _sha(f"{base}\0{n}".encode())
                    cand = f"{prefix}-{h[:6]}"
                    if cand not in used:
                        break
                    n += 1
                used.add(cand)
                it["id"] = cand

    def _adopt(self, raw: bytes, obj: dict, st: os.stat_result | None = None) -> None:
        _check_version(obj, self.path)
        self._replace_data(obj)
        self._disk_sha = _sha(raw)
        self._clean = self._canon(self.data)
        if st is not None:
            self._stat = self._key(st)
        else:
            self._mark()

    def _rollback(self) -> None:
        """A save failed: memory goes back to exactly what is on disk, so a
        change the engine was told had failed is never served, and never
        written later by some unrelated save."""
        self._replace_data(json.loads(self._clean.decode("utf-8")))

    def _absorb_legacy(self, obj: dict) -> None:
        """The access log used to live inside the store. Move it beside the
        store (once — nothing is imported twice), and keep it in the store
        if it cannot be moved: no record is ever dropped."""
        entries = obj.get(self._LEGACY_ACCESS)
        if entries is None:
            return
        if isinstance(entries, list) and (not entries
                                          or self.access_log.import_legacy(entries)):
            obj.pop(self._LEGACY_ACCESS, None)

    def _load(self) -> None:
        if not self.path.exists() and not (self._history_files()
                                           or self._damaged_copies()):
            return          # the very first run: nothing to read, nothing written
        # A missing store is normal on the very first run — and a catastrophe
        # if there is evidence a life was here; _open_locked recovers it.
        with self._lock():
            self._open_locked()

    def _open_locked(self) -> bool:
        """Read the store and make memory match it, under the lock (so two
        surfaces starting together after a power cut cannot both recover).
        Returns True if memory changed."""
        try:
            st = self.path.stat()
            raw = self.path.read_bytes()
        except FileNotFoundError:
            if self._history_files() or self._damaged_copies():
                self._recover_locked(None, "the file is missing")
                return True
            return False
        except OSError as exc:
            raise ConscienceCorrupt(
                "JEFFEREY cannot open your memory file right now "
                f"({exc.strerror or exc}). Nothing has been changed. If the "
                "drive was just plugged in, try again in a moment.",
                self.path) from exc
        if self._disk_sha is not None and _sha(raw) == self._disk_sha:
            self._stat = self._key(st)
            return False
        try:
            obj = self._parse(raw)
        except _Unreadable as u:
            if u.torn and (u.certain or self._could_be_tear(st)):
                self._recover_locked(raw, u.plain)
                return True
            # "Start over" is for a store nothing can bring back. A typo in a
            # hand edit, with good copies beside it, is never a reason to
            # empty a life — even if the flag was left set.
            if os.environ.get("JEFFEREY_ALLOW_RESET") == "1" and not self._good_copy():
                self._reset_locked(raw, u.plain)
                return True
            raise ConscienceNeedsFixing(self._fix_text(u), self.path) from None
        self._adopt(raw, obj, st)
        self._ensure_versioned(raw, obj)
        return True

    def _good_copy(self) -> Path | None:
        """The newest copy in history that can actually be read."""
        for f in self._history_files():
            try:
                self._parse(f.read_bytes())
                return f
            except (OSError, _Unreadable):
                continue
        return None

    def _could_be_tear(self, st: os.stat_result) -> bool:
        snaps = self._snapshot_files()
        if not snaps:
            return True
        try:
            return st.st_mtime <= snaps[0].stat().st_mtime + TEAR_WINDOW_S
        except OSError:
            return True

    @staticmethod
    def _fix_text(u: _Unreadable) -> str:
        if u.torn:
            core = (f"Your memory file cannot be read: {u.plain}. It was changed "
                    "after JEFFEREY's last saved copy, so he has not swapped it "
                    "for an older one")
        else:
            core = (f"Your memory file cannot be read: {u.plain}. This usually "
                    "happens after an edit by hand. JEFFEREY has not changed the "
                    "file")
        return (core + ". Fix that in the file and ask again, or put back an "
                "earlier copy by double-clicking 'Restore my memories'.")

    def _keep_damaged(self, raw: bytes) -> Path | None:
        """Set a damaged file's bytes aside as <name>.corrupt-<UTC time>,
        never over an earlier one, before anything replaces it."""
        base = f"{self.path.name}.corrupt-{_utc_stamp()}"
        for i in range(1, 1000):
            cand = self.path.with_name(base if i == 1 else f"{base}-{i}")
            try:
                fd = os.open(cand, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
                             0o600)
            except FileExistsError:
                continue
            except OSError:
                return None
            try:
                _write_all(fd, raw)
                _full_fsync(fd)
            except OSError:
                os.close(fd)
                try:
                    cand.unlink()
                except OSError:
                    pass
                return None
            os.close(fd)
            _sync_dir(cand.parent)
            return cand
        return None

    def _recover_locked(self, raw: bytes | None, reason: str) -> None:
        """The live store is unreadable or gone. Go back to the newest good
        copy; if there isn't one, stop — never start from an empty life."""
        for snap in self._history_files():
            try:
                obj = self._parse(snap.read_bytes())
            except (OSError, _Unreadable):
                continue
            saved = _when(self._snap_time(snap))
            kept = self._keep_damaged(raw) if raw is not None else None
            self._replace_data(obj)
            if raw is not None and kept is None:
                # The damaged file could not be set aside (a full drive?), so
                # it is NOT written over. Work from the copy, in memory only.
                self._disk_sha, self._clean = _sha(raw), self._canon(self.data)
                self._mark()
                self._runtime_notices["recovery"] = (
                    f"Your memory file could not be read ({reason}). JEFFEREY "
                    f"is working from the copy saved {saved}, but could not "
                    "repair the file on the drive. Please free some space or "
                    "check the drive.")
                return
            self._note("recovered",
                       f"Your memory file could not be read ({reason}). JEFFEREY "
                       f"went back to the copy saved {saved}. Anything said "
                       "after that may be missing, so please check."
                       + (f" The damaged file was kept beside it as {kept.name}."
                          if kept else ""))
            try:
                self._commit_locked(check_disk=False)
            except OSError:
                self._disk_sha = _sha(raw) if raw is not None else None
                self._clean = self._canon(self.data)
                self._runtime_notices["recovery"] = (
                    f"Your memory file could not be read ({reason}). JEFFEREY "
                    f"is working from the copy saved {saved}, but could not "
                    "write it back to the drive (it may be full or read-only).")
            print(f"\n  ⚠  {self.path} could not be read ({reason}).\n"
                  f"     Recovered from the copy saved {saved} ({snap.name})."
                  + (f"\n     The damaged file is kept at {kept}." if kept else "")
                  + "\n     Check what you may have said since then.\n",
                  file=sys.stderr)
            return
        if os.environ.get("JEFFEREY_ALLOW_RESET") == "1":
            self._reset_locked(raw, reason)
            return
        raise ConscienceCorrupt(
            f"Your memory file cannot be read ({reason}), and there is no good "
            "copy to go back to. JEFFEREY will not start from an empty memory — "
            "that would silently erase everything you have told him. Nothing "
            "has been changed. Put the file back from a backup; or, if you truly "
            "mean to start over, start JEFFEREY once with JEFFEREY_ALLOW_RESET=1 "
            "(the damaged file is kept, never deleted).", self.path)

    def _reset_locked(self, raw: bytes | None, reason: str) -> None:
        """JEFFEREY_ALLOW_RESET=1: start empty — but the damaged original is
        set aside first, never destroyed. If it cannot be, nothing happens."""
        kept = self._keep_damaged(raw) if raw is not None else None
        if raw is not None and kept is None:
            raise ConscienceCorrupt(
                f"Your memory file cannot be read ({reason}). JEFFEREY could not "
                "set the damaged file aside, so he left it exactly as it is and "
                "did not start over.", self.path)
        self._replace_data(self._defaults())
        self._note("reset", "JEFFEREY started with an empty memory, as asked."
                   + (f" The damaged file was kept beside it as {kept.name}; "
                      "nothing was deleted." if kept else ""))
        try:
            self._commit_locked(check_disk=False)
        except OSError as exc:
            raise ConscienceCorrupt(
                "JEFFEREY could not write a fresh memory file (the drive may be "
                "full or read-only). Nothing else was changed.", self.path) from exc
        print(f"\n  ⚠  {self.path} could not be read ({reason}); "
              f"JEFFEREY_ALLOW_RESET=1 — starting empty."
              + (f"\n     The damaged file is kept at {kept}." if kept else "")
              + "\n", file=sys.stderr)

    def _ensure_versioned(self, raw: bytes, obj: dict) -> None:
        """Whatever is on disk must also be in history, in the right order.

        Normally it already is: JEFFEREY copies every write it makes. If it
        is not, someone changed the file outside JEFFEREY — an edit by hand,
        or an older copy put back. That change is the owner's: it is adopted
        as the newest revision (above every copy, so a later recovery cannot
        bring back the abandoned version) and the owner is told."""
        files = self._history_files()
        if not files:
            return
        top = files[0]
        top_rev, disk_rev = self._snap_rev(top), self._rev_of(obj)
        if disk_rev > top_rev:
            self._archive(raw, disk_rev)          # written, never copied
            return
        if disk_rev == top_rev:
            try:
                top_raw = top.read_bytes()
            except OSError:
                top_raw = None
            if top_raw == raw:
                return
            if top_raw is not None:
                try:
                    if self._parse(top_raw) == obj:
                        return
                except _Unreadable:
                    self._archive(raw, disk_rev)  # the newest copy is damaged
                    return
        try:
            before = self._pin_locked(top.read_bytes(), top_rev,
                                      "before an outside change")
        except OSError:
            before = None
        try:
            when = _when(self.path.stat().st_mtime)
        except OSError:
            when = "recently"
        self._note("changed_outside",
                   "Your memory file was changed outside JEFFEREY (an edit by "
                   f"hand, or an older copy put back) {when}. JEFFEREY is now "
                   "using the file exactly as it is."
                   + (" The version from before is kept as a copy, in case that "
                      "was a mistake." if before else ""))
        try:
            self._commit_locked(check_disk=False)
        except OSError:
            self._rollback()
            self._runtime_notices["outside"] = (
                "Your memory file was changed outside JEFFEREY. He is using it "
                "as it is, but could not record that change in his copies (the "
                "drive may be full or read-only).")

    def _check_disk_unchanged(self) -> None:
        """The anti-clobber guard, by CONTENT: the bytes on disk must be the
        ones this process last read or wrote. Comparing revision numbers was
        not enough — a hand edit keeps the number, and the next save (even a
        read's) silently put the deleted text back."""
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            if self._disk_sha is None and not self._history_files():
                return                        # the very first write: nothing lost
            raise ConscienceConflict(
                "Your memory file has disappeared since JEFFEREY last read it "
                "(perhaps the drive was unplugged). Nothing was saved, so "
                "nothing was written over whatever happened. Plug the drive "
                "back in, or restart JEFFEREY so he can put the file back.",
                self.path)
        if _sha(raw) != self._disk_sha:
            raise ConscienceConflict(
                "Your memories were changed somewhere else a moment ago — by "
                "another app using JEFFEREY, or by hand — so nothing was saved "
                "and nothing was lost. Ask again and JEFFEREY will use the "
                "newest version.", self.path)

    def _next_rev(self) -> int:
        """One above everything: the file, and every copy in history. After an
        older copy is put back, new writes still sort above the abandoned
        version, so recovery can never pick it."""
        top = max((self._snap_rev(p) for p in self._history_files()), default=0)
        return max(self._rev_seen, top) + 1

    def _commit_locked(self, check_disk: bool = True) -> None:
        """Write memory as the next revision, then copy it into history.
        The caller holds the lock. May raise OSError; callers roll back."""
        if check_disk:
            self._check_disk_unchanged()
        rev = self._next_rev()
        self.data["_rev"] = rev
        need = self.data.get(VERSION_KEY)
        if not isinstance(need, str) or _newer(__version__, need):
            self.data[VERSION_KEY] = __version__
        payload = self._canon(self.data)
        _make_dir(self.path.parent)
        _write_atomic(self.path, payload)
        self._rev_seen = rev
        self._clean = payload
        self._disk_sha = _sha(payload)
        self._mark()
        self._archive(payload, rev)

    def _save(self) -> None:
        """Persist what the caller just changed — or, if the save fails, undo
        it in memory too, and say why in plain words."""
        if self._unavailable is not None:
            raise self._unavailable
        if self._follows_home:
            why = home.problem()
            if why:
                self._rollback()
                raise DriveNotHere(why[0].upper() + why[1:] + ".")
        self._ensure_ids()          # whatever was just added gets its id now
        if self._canon(self.data) == self._clean:
            return                  # nothing changed: no write, no copy, no rev
        try:
            _make_dir(self.path.parent)
            with self._lock():
                self._commit_locked()
        except StoreProblem:
            self._rollback()
            raise
        except OSError as exc:
            self._rollback()
            raise ConscienceSaveFailed(_SAVE_FAILED, self.path) from exc
        except BaseException:
            self._rollback()
            raise

    # ------------------------------------------------------------ history
    def _archive(self, payload: bytes, rev: int) -> None:
        """Copy a revision into history — atomically, privately, fully
        flushed — then prune by age. Taken *after* the store is written: a
        copy that lagged one write behind would lose the newest change in
        exactly the case it exists for. A copy that cannot be written is not
        silent: it becomes a notice until it works again."""
        try:
            _make_dir(self.history_dir)
            dest = self.history_dir / f"{self.path.stem}-{_utc_stamp()}-{rev:06d}.json"
            _write_atomic(dest, payload)
            self._prune_locked()
            self._runtime_notices.pop("history", None)
        except OSError:
            self._runtime_notices["history"] = (
                "JEFFEREY could not save a safety copy of your memories just now "
                "(the drive may be full or read-only). Your memories themselves "
                "were saved, but no new safety copies are being kept until this "
                "is fixed.")

    def _prune_locked(self, now: float | None = None) -> None:
        """Keep: the newest HISTORY_KEEP; every copy from the last day (up to
        HISTORY_RECENT_MAX); the newest copy of each hour for a week and of
        each day for three months. Pinned copies keep for PIN_KEEP_DAYS."""
        now = time.time() if now is None else now
        snaps = self._snapshot_files()
        keep = set(snaps[:HISTORY_KEEP])
        recent = [p for p in snaps
                  if now - self._snap_time(p) <= HISTORY_RECENT_HOURS * 3600]
        keep.update(recent[:HISTORY_RECENT_MAX])
        hours: set[int] = set()
        days: set[int] = set()
        for p in snaps:
            t = self._snap_time(p)
            if now - t <= HISTORY_HOURLY_DAYS * 86400 and int(t // 3600) not in hours:
                hours.add(int(t // 3600))
                keep.add(p)
            if now - t <= HISTORY_DAILY_DAYS * 86400 and int(t // 86400) not in days:
                days.add(int(t // 86400))
                keep.add(p)
        for p in snaps:
            if p not in keep:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass
        for i, p in enumerate(self._pinned_files()):
            if i >= PIN_MAX or now - self._snap_time(p) > PIN_KEEP_DAYS * 86400:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass

    def _pin_locked(self, raw: bytes, rev: int, label: str) -> Path:
        pins = self._pinned_files()
        if pins:
            try:
                if pins[0].read_bytes() == raw:
                    return pins[0]            # this exact state is already pinned
            except OSError:
                pass
        _make_dir(self.history_dir)
        _make_dir(self.pinned_dir)
        slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:40] or "pinned"
        dest = self.pinned_dir / f"{self.path.stem}-{slug}-{_utc_stamp()}-{rev:06d}.json"
        _write_atomic(dest, raw)
        self._prune_locked()
        return dest

    def pin_snapshot(self, reason: str = "before a change that removes things") -> Path | None:
        """Keep the store exactly as it is on disk now, for PIN_KEEP_DAYS,
        whatever happens after. Call it BEFORE anything destructive (forget,
        erase, a bulk change); if it raises, do not go ahead — nothing
        irreversible happens because an AI asked. Returns the copy, or None
        when nothing has been written yet (so nothing can be lost)."""
        if self._unavailable is not None:
            raise self._unavailable
        try:
            with self._lock():
                try:
                    raw = self.path.read_bytes()
                except FileNotFoundError:
                    return None
                try:
                    rev = self._rev_of(self._parse(raw))
                except _Unreadable:
                    rev = self._rev_seen
                return self._pin_locked(raw, rev, reason)
        except OSError as exc:
            raise ConscienceSaveFailed(
                "JEFFEREY could not keep a safety copy first (the drive may be "
                "full or read-only), so nothing was removed.", self.path) from exc

    def snapshots(self) -> list[dict]:
        """What versions of this conscience are recoverable, newest first."""
        return [{"file": str(p), "revision": self._snap_rev(p),
                 "pinned": p.parent == self.pinned_dir,
                 "saved": time.strftime("%Y-%m-%dT%H:%M:%S",
                                        time.localtime(self._snap_time(p)))}
                for p in self._history_files()]

    def history(self, limit: int | None = 30) -> list[dict]:
        """The copies kept, numbered, newest first, in the owner's words."""
        out = []
        for i, p in enumerate(self._history_files()):
            if limit is not None and i >= limit:
                break
            entry: dict[str, Any] = {
                "number": i + 1, "file": p.name, "revision": self._snap_rev(p),
                "saved": _when(self._snap_time(p)),
                "pinned": self._pin_label(p) if p.parent == self.pinned_dir else None,
            }
            try:
                obj = self._parse(p.read_bytes())
                count = lambda k: len(obj[k]) if isinstance(obj.get(k), list) else 0  # noqa: E731
                entry.update(readable=True, facts=count("facts"),
                             moments=count("memories"), people=count("people"))
            except (OSError, _Unreadable):
                entry["readable"] = False
            out.append(entry)
        return out

    def _resolve_copy(self, which) -> Path:
        files = self._history_files()
        s = str(which).strip()
        if s.isdigit():
            n = int(s)
            if 1 <= n <= len(files):
                return files[n - 1]
        else:
            for p in files:
                if s in (p.name, str(p)):
                    return p
        raise StoreProblem(f"There is no copy '{s}'. Look at the list of copies "
                           "and choose one of its numbers.")

    def restore(self, which) -> dict:
        """OWNER ONLY — the owner's own terminal, never a tool an engine can
        call (putting an old copy back would re-surface whatever he deleted).

        Puts copy `which` (its number in history(), or its file name) back as
        the current memory. Timeline-aware: what is there now is pinned first,
        so the restore can itself be undone, and the restored version becomes
        the newest revision — above every copy — so no later recovery can
        bring back the abandoned one. The restore is recorded as a notice."""
        snap = self._resolve_copy(which)
        try:
            obj = self._parse(snap.read_bytes())
        except (OSError, _Unreadable) as exc:
            raise StoreProblem("That copy cannot be read either "
                               f"({getattr(exc, 'plain', exc)}). Choose another.")
        saved = _when(self._snap_time(snap))
        _make_dir(self.path.parent)
        try:
            with self._lock():
                try:
                    cur = self.path.read_bytes()
                except FileNotFoundError:
                    cur = None
                kept = None
                if cur is not None:
                    try:
                        kept = self._pin_locked(cur, self._rev_of(self._parse(cur)),
                                                "before restore")
                    except _Unreadable:
                        kept = self._keep_damaged(cur)
                        if kept is None:
                            raise StoreProblem(
                                "JEFFEREY could not set the current file aside, "
                                "so nothing was put back.")
                self._replace_data(obj)
                self._note("restored",
                           f"Your memories were put back to the copy saved {saved}. "
                           "What was there just before is kept as a copy, so this "
                           "can be undone.")
                self._commit_locked(check_disk=False)
        except StoreProblem:
            self._rollback()
            raise
        except OSError as exc:
            self._rollback()
            raise ConscienceSaveFailed(
                "JEFFEREY could not put that copy back (the drive may be full or "
                "read-only). Nothing was changed.", self.path) from exc
        self._unavailable = None
        return {"restored": snap.name, "saved": saved,
                "facts": len(self.data.get("facts", [])),
                "kept_before_restore": kept.name if kept else None,
                "revision": self._rev_seen}

    # ------------------------------------------------------------ notices
    def _note(self, kind: str, message: str) -> None:
        ns = self.data.get("_notices")
        if not isinstance(ns, list):
            ns = self.data["_notices"] = []
        ns.append({"at": _now(), "ts": time.time(), "kind": kind,
                   "message": message})
        del ns[:-20]

    def notices(self) -> list[dict]:
        """What the owner must be told — a recovery, a restore, a change made
        outside JEFFEREY, safety copies failing. Shown in get_conscience and
        the daily brief for NOTICE_DAYS, or until he dismisses them."""
        out = []
        now = time.time()
        for n in self.data.get("_notices") or []:
            if not isinstance(n, dict) or n.get("dismissed"):
                continue
            try:
                if now - float(n.get("ts", 0)) > NOTICE_DAYS * 86400:
                    continue
            except (TypeError, ValueError):
                continue
            out.append({"when": n.get("at"), "what": n.get("message")})
        out += [{"when": "now", "what": m} for m in self._runtime_notices.values()]
        if self.access_log.failures:
            out.append({"when": "now", "what": (
                "JEFFEREY could not write down some recent requests in the access "
                "log (the drive may be full or read-only).")})
        return out

    def dismiss_notices(self) -> int:
        """The owner has read them. They stay in the file, marked as read."""
        n = 0
        for x in self.data.get("_notices") or []:
            if isinstance(x, dict) and not x.get("dismissed"):
                x["dismissed"] = _now()
                n += 1
        self._runtime_notices.clear()
        self._save()
        return n

    # ------------------------------------------------------------ hygiene
    def _tighten_modes(self) -> None:
        """Files made by earlier versions were readable by every account on
        the Mac (0644). Make them the owner's alone: files 0600, folders 0700.
        The folder holding the store is changed only when it is JEFFEREY's
        own (~/.jefferey or the drive's .selfcloud/jefferey)."""
        def fix(p: Path, mode: int) -> None:
            try:
                st = os.lstat(p)
                if _stat.S_ISLNK(st.st_mode):
                    return
                if st.st_mode & 0o077:
                    os.chmod(p, mode)
            except OSError:
                pass
        parent = self.path.parent
        if parent.name in (".jefferey", "jefferey"):
            fix(parent, 0o700)
        fix(self.path, 0o600)
        fix(self._lock_path, 0o600)
        for p in self._damaged_copies():
            fix(p, 0o600)
        for p in self.access_log.files():
            if p.exists():
                fix(p, 0o600)
        for d in (self.history_dir, self.pinned_dir):
            if d.is_dir():
                fix(d, 0o700)
                for p in self._files_in(d):
                    fix(p, 0o600)

    # ------------------------------------------------------------ facts
    # October 2026 (I-11, I-25). A fact records what kind of private it is
    # and who said it. Health, money, children, the safety of the home and
    # other people's confidences are 'private' by default: only the owner's
    # own caretaker key sees them — in bulk only on a model on this Mac, and
    # on a rented engine only when a question names them. Anything else is
    # 'engines': any key that may read facts. His own disclosure rules apply
    # on top, to every engine. Anyone who may write may narrow; only the
    # owner widens (/share). What an AI wrote down in its own words waits as
    # 'pending' until he confirms it (/pending).
    def remember_fact(self, fact: str, category: str = "general") -> dict:
        text = str(fact or "").strip()
        if not text:
            return _refusal("remember_fact", "There is nothing to remember: the fact is empty.")
        category = str(category or "general").strip() or "general"
        kinds = grounding.sensitivity(text, category)
        src = provenance.source(text=text)
        entry = {"fact": text, "category": category, "added": _now(),
                 "visibility": "private" if kinds else "engines",
                 "sensitivity": kinds, "source": src,
                 "status": provenance.status_for(src)}
        self.data["facts"].append(entry)
        self._save()
        out = dict(entry)
        notes = []
        if kinds:
            notes.append(
                "Kept private, because it is about "
                + " and ".join(grounding.CLASS_WORDS_PLAIN[k] for k in kinds)
                + ". Only his own caretaker key sees it, and only when a question names "
                  "it. Only he can let other AIs see it, typing /share "
                + f"{entry['id']} engines himself.")
        if entry["status"] == "pending":
            notes.append("It is marked 'not yet confirmed by him', because an AI wrote "
                         "it down in its own words; he confirms it with /pending in "
                         "'Talk to JEFFEREY on this Mac'.")
        if notes:
            out["note"] = " ".join(notes)
        return out

    def forget_fact(self, contains: str = "", ids=None, confirm: str = "") -> dict:
        """Two steps, never a wildcard (forgetting.py): without `confirm`,
        returns the facts that would go — matched by id, or by whole words —
        and a one-time code; with the code, removes exactly those, pins a
        copy first, keeps them in the removed list and logs it."""
        import forgetting
        return forgetting.forget_facts(self, contains, ids, confirm)

    @staticmethod
    def _fact_tags(f: dict) -> list[str]:
        return [str(f.get("category") or "")] + list(f.get("sensitivity") or [])

    def visible_facts(self, rd: dict | None = None, bulk: bool = True
                      ) -> tuple[list[dict], list[tuple[dict, str]]]:
        """The facts whoever reads this result may see — and the ones held
        back, each with why ('private' or 'rules'). `bulk`: a whole-memory
        read (get_conscience, the system prompt, who_am_i), where private
        facts go only to the owner's own caretaker on this Mac. A question
        that names a subject (explain_basis) may reach his private facts
        through his caretaker key on any engine."""
        import rules as _rules
        rd = rd or provenance.reader()
        seen, held = [], []
        for f in self.data.get("facts") or []:
            if not isinstance(f, dict):
                continue
            if not rd["owner"]:
                if f.get("visibility", "engines") != "engines" and (bulk or not rd["caretaker"]):
                    held.append((f, "private"))
                    continue
                if _rules.held_back(self.data, rd["audiences"], f.get("fact", ""),
                                    self._fact_tags(f)):
                    held.append((f, "rules"))
                    continue
            seen.append(f)
        return seen, held

    @staticmethod
    def _fact_view(f: dict, reason: str | None = None) -> dict:
        """A fact as an engine reads it: what it says, and how far to trust it."""
        v = {k: f[k] for k in ("id", "fact", "category", "added", "visibility") if k in f}
        kinds = [k for k in f.get("sensitivity") or [] if k in grounding.CLASS_WORDS_PLAIN]
        if kinds:
            v["private_because"] = [grounding.CLASS_WORDS_PLAIN[k] for k in kinds]
        if provenance.pending(f):
            v["unconfirmed"] = True
        if reason:
            v["match_reason"] = reason
        return v

    # ------------------------------------------------------------ priorities
    def _find_priority(self, context: str, a: str, b: str) -> dict | None:
        n = grounding.normalise
        for p in self.data["priorities"]:
            if not isinstance(p, dict):
                continue
            if n(p.get("context")) == n(context) and {
                n(p.get("higher")), n(p.get("lower"))} == {n(a), n(b)}:
                return p
        return None

    @staticmethod
    def _confidence(p: dict) -> float:
        """From the evidence, never from a number an AI chose: (for + 1) /
        (for + against + 2) for a learned value; a stated one counts like four
        observations at the confidence it was stated with. Above 0.8 only
        for what the owner set or confirmed himself."""
        f = max(0, int(p.get("for") or 0))
        a = max(0, int(p.get("against") or 0))
        if p.get("stated"):
            s = _real_number(p.get("stated_confidence"))
            s = 0.6 if s is None else s
            c = (s * _STATED_WEIGHT + f) / (_STATED_WEIGHT + f + a)
        else:
            c = (f + 1) / (f + a + 2)
        cap = 0.99 if provenance.owner_backed(p) else UNCONFIRMED_CAP
        return round(max(0.05, min(cap, c)), 2)

    @staticmethod
    def _prio_view(p: dict, reason: str | None = None) -> dict:
        """A value as an engine reads it, with the evidence for and against."""
        v = {k: p[k] for k in ("id", "context", "higher", "lower", "confidence", "for",
                               "against", "evidence", "updated") if k in p}
        if p.get("stated"):
            v["stated"] = True
            v["locked"] = True       # never reversed by inference; a question instead
        if provenance.pending(p):
            v["unconfirmed"] = True
        if p.get("question"):
            v["question_for_owner"] = p["question"]
        if isinstance(p.get("proposed"), dict):
            v["proposed_change"] = {k: p["proposed"].get(k) for k in ("higher", "lower")}
        if reason:
            v["match_reason"] = reason
        return v

    def _log_change(self, kind: str, context: str, was: str, now: str, src: dict,
                    **extra) -> None:
        """A change to a value goes in the correction log, with what it was
        and who changed it (I-48: a reversal used to leave no trace)."""
        self.data["corrections"].append({
            "context": context, "kind": kind, "was": was, "inferred": now,
            "source": src, "added": _now(), "ts": time.time(), **extra})

    @staticmethod
    def _rank(src: dict) -> int:
        return {provenance.OWNER: 3, provenance.IMPORTED: 3, provenance.OWNER_WORDS: 2,
                provenance.ENGINE: 1}.get((src or {}).get("stated_by"), 0)

    def set_priority(
        self, context: str, higher: str, lower: str, confidence: float = 0.6
    ) -> dict:
        """He STATED a priority: in <context>, <higher> beats <lower>.

        October 2026 (I-25, I-48): an AI may not write a value about
        everything ('general', 'any'), may not claim more than 0.6
        confidence for him, and a statement is locked against inference. A
        statement that reverses one he made himself is not applied: it waits
        for his own yes (/pending). Every reversal is logged with what it
        was and who changed it."""
        import access
        context, higher, lower = (" ".join(str(x or "").split()) for x in (context, higher, lower))
        engine = not access.owners_hands()
        problem = grounding.context_problem(context, engine)
        if problem:
            return _refusal("set_priority", problem)
        if not higher or not lower or grounding.normalise(higher) == grounding.normalise(lower):
            return _refusal("set_priority", "A value needs two different things: what "
                                            "matters more, and what it matters more than.")
        c = _real_number(confidence)
        c = max(0.05, min(0.99, 0.6 if c is None else c))
        if engine:
            c = min(c, ENGINE_CONFIDENCE_CAP)
        src = provenance.source(values=(higher, lower))
        status = provenance.status_for(src)
        p = self._find_priority(context, higher, lower)
        extra: dict = {}
        if p is None:
            p = {"context": context, "higher": higher, "lower": lower, "stated": True,
                 "stated_confidence": c, "for": 0, "against": 0, "evidence": 1,
                 "source": src, "status": status, "updated": _now()}
            self.data["priorities"].append(p)
        elif grounding.normalise(p.get("higher")) == grounding.normalise(higher):
            # Said again. It is a statement now; never less trusted than it was.
            if self._rank(src) > self._rank(p.get("source")) and (
                    status == "confirmed" or provenance.pending(p)):
                p["source"], p["status"] = src, status
            old = _real_number(p.get("stated_confidence")) if p.get("stated") else None
            p["stated_confidence"] = c if old is None else max(old, c)
            p["stated"] = True
            p.pop("question", None)
            p["updated"] = _now()
        else:
            was = f"{p.get('higher')} > {p.get('lower')}"
            now = f"{higher} > {lower}"
            locked = bool(p.get("stated")) and not provenance.pending(p)
            if locked and engine and status != "confirmed":
                p["proposed"] = {"higher": higher, "lower": lower, "confidence": c,
                                 "source": src, "at": _now()}
                self._log_change("reversal_asked", context, was, now, src, applied=False)
                q = (f"An AI says that for {context}, {higher} now matters more to you than "
                     f"{lower}. You had said the opposite, so nothing was changed.")
                self._note("priority_question",
                           q + " If it is right, type /pending in 'Talk to JEFFEREY on this "
                               "Mac' and confirm it.")
                self._save()
                return {**self._prio_view(p), "changed": False,
                        "question_for_owner": q,
                        "note": ("He stated the opposite himself, so it was not reversed. "
                                 "Ask him plainly whether it has changed. Only his own yes "
                                 "(/pending in 'Talk to JEFFEREY on this Mac', or saying so "
                                 "himself there) changes it.")}
            self._log_change("reversal", context, was, now, src, applied=True,
                             confidence_was=p.get("confidence"))
            for k in ("proposed", "question", "confirmed_by_owner"):
                p.pop(k, None)
            p.update(higher=higher, lower=lower, stated=True, stated_confidence=c,
                     source=src, status=status, updated=_now())
            p["for"], p["against"] = 0, 0
            extra["reversed"] = {"was": was, "logged": True}
        p["evidence"] = int(p.get("for") or 0) + int(p.get("against") or 0) or 1
        p["confidence"] = self._confidence(p)
        self._save()
        out = {**self._prio_view(p), **extra}
        if engine and _real_number(confidence) is not None and _real_number(confidence) > c:
            out["note"] = (f"Kept at {c:.0%} sure: an AI may not say it is surer than that "
                           "for him. Only he can confirm it higher (/pending).")
        return out

    def _same_correction(self, context: str, hi: str, lo: str) -> bool:
        """Was this exact correction already counted in this conversation?
        (One override, repeated by an AI in a loop, used to count twelve
        times.) On the terminal a conversation step is the owner's turn;
        elsewhere, the same correction within ten minutes."""
        n = grounding.normalise
        key = (n(context), n(hi), n(lo))
        turn, now = provenance.turn(), time.time()
        for c in reversed(self.data.get("corrections", [])[-200:]):
            if not isinstance(c, dict) or c.get("kind") not in (None, "correction"):
                continue
            h, l = c.get("higher"), c.get("lower")
            if h is None:
                h, _, l = str(c.get("inferred", "")).partition(" > ")
            if (n(c.get("context")), n(h), n(l)) != key:
                continue
            if turn is not None:
                return c.get("turn") == turn
            try:
                return now - float(c.get("ts") or 0) < DEDUP_SECONDS
            except (TypeError, ValueError):
                return False
        return False

    def record_correction(
        self, context: str, suggested: str, chosen: str,
        inferred_higher: str, inferred_lower: str,
    ) -> dict:
        """The heart of the conscience: the user overrode a recommendation.

        Learn WHY — which value they were protecting. For and against are
        counted separately; a learned value turns round only when the
        evidence against outweighs the evidence for; a value he STATED is
        never reversed by inference — a contradiction becomes a question for
        him. The same correction twice in one conversation counts once."""
        import access
        context, hi, lo = (" ".join(str(x or "").split())
                           for x in (context, inferred_higher, inferred_lower))
        engine = not access.owners_hands()
        problem = grounding.context_problem(context, engine)
        if problem:
            return _refusal("record_correction", problem)
        if not hi or not lo or grounding.normalise(hi) == grounding.normalise(lo):
            return _refusal("record_correction", "Say which value he protected and which "
                                                 "he gave up; they must be different.")
        if self._same_correction(context, hi, lo):
            p = self._find_priority(context, hi, lo)
            out = self._prio_view(p) if p else {"context": context}
            out.update(already_counted=True,
                       note="This same correction was already counted in this "
                            "conversation; one correction counts once.")
            return out
        src = provenance.source()
        entry = {"context": context, "suggested": suggested, "chosen": chosen,
                 "inferred": f"{hi} > {lo}", "higher": hi, "lower": lo,
                 "added": _now(), "ts": time.time(), "turn": provenance.turn(),
                 "source": src}
        self.data["corrections"].append(entry)
        extra: dict = {}
        p = self._find_priority(context, hi, lo)
        if p is None:
            p = {"context": context, "higher": hi, "lower": lo, "stated": False,
                 "for": 1, "against": 0, "source": src,
                 "status": provenance.status_for(src), "updated": _now()}
            self.data["priorities"].append(p)
        elif grounding.normalise(p.get("higher")) == grounding.normalise(hi):
            p["for"] = int(p.get("for") or 0) + 1
        else:
            p["against"] = int(p.get("against") or 0) + 1
            if p.get("stated"):
                q = (f"He said that for {p['context']}, {p['higher']} matters more than "
                     f"{p['lower']}. This time he chose {hi} over {lo}. Ask him, once "
                     f"and plainly, whether that has changed; nothing was reversed.")
                if not p.get("question"):
                    self._note("priority_question",
                               f"You once said that for {p['context']}, {p['higher']} "
                               f"matters more than {p['lower']}. Recently {hi} was chosen "
                               f"over {lo}. Has that changed? Nothing was changed; tell "
                               f"JEFFEREY in your own words if it has.")
                p["question"] = q
                extra["question_for_owner"] = q
            elif p["against"] > p["for"]:
                was = f"{p['higher']} > {p['lower']}"
                p["higher"], p["lower"] = hi, lo
                p["for"], p["against"] = p["against"], p["for"]
                entry["flipped_from"] = was
                extra["flipped"] = {"was": was,
                                    "why": "the choices against it now outweigh the ones for it"}
        p["evidence"] = int(p.get("for") or 0) + int(p.get("against") or 0)
        p["updated"] = _now()
        p["confidence"] = self._confidence(p)
        self._save()
        return {**self._prio_view(p), **extra}

    def priorities_for(self, context: str | None = None) -> list[dict]:
        """His values, most certain first — about a subject (whole words:
        'car' is not 'caregiver'), or all of them. A value he holds about
        everything is listed last."""
        ps = [p for p in self.data["priorities"] if isinstance(p, dict)]
        if context:
            q = grounding.expand(grounding.content(context))
            if not q:
                return []
            ps = [p for p in ps
                  if grounding.content(p.get("context", "")) & q
                  or grounding.normalise(p.get("context")) in grounding.CATCH_ALL]
        general = lambda p: grounding.normalise(p.get("context")) in grounding.CATCH_ALL  # noqa: E731
        return [self._prio_view(p) for p in
                sorted(ps, key=lambda p: (general(p), -float(p.get("confidence") or 0)))]

    # ------------------------------------------------------------ goals
    def add_goal(self, goal: str) -> dict:
        entry = {"goal": goal.strip(), "added": _now(), "active": True}
        self.data["goals"].append(entry)
        self._save()
        return entry

    def close_goal(self, contains: str = "", ids=None, confirm: str = "") -> dict:
        """Two steps, like every change that takes something away
        (forgetting.py)."""
        import forgetting
        return forgetting.close_goals(self, contains, ids, confirm)

    # ------------------------------------------------------------ operational AI
    # The Act tier, enforced in code. JEFFEREY can never widen his own
    # authority: a permission changes only at the owner's own keyboard
    # (/permit in 'Talk to JEFFEREY on this Mac'), and every change, approval
    # and refusal lands in the owned log, saying who and through which door.

    LEVELS = ("observe", "recommend", "act")

    @staticmethod
    def _cat(category) -> str:
        return re.sub(r"\s+", " ", str(category or "")).strip().lower()

    @staticmethod
    def _never(category: str, description: str = "") -> str | None:
        """Why this can never be approved, whatever is set — or None."""
        words = re.sub(r"[^a-z0-9]+", " ", (category or "").lower())
        for rx, why in _NEVER:
            if rx.search(words):
                return why
        text = (description or "").lower()
        for rx, why in _NEVER_IN_TEXT:
            if rx.search(text):
                return why
        return None

    @staticmethod
    def _stamp(entry: dict, source: str) -> dict:
        """Every line of the action log says who wrote it and through which
        door; `source` says whether JEFFEREY wrote it ('jefferey') or an
        engine reported it ('engine') — I-45."""
        entry["by"], entry["surface"] = _who()
        entry["source"] = source
        return entry

    @staticmethod
    def describe_permission(category: str, p: dict) -> str:
        """One permission, in the owner's words."""
        lvl = p.get("level", "recommend")
        if lvl == "observe":
            return f"'{category}': JEFFEREY only watches and learns"
        if lvl != "act":
            return f"'{category}': JEFFEREY brings you options; you decide"
        cur = p.get("currency") or DEFAULT_CURRENCY
        if p.get("floor") is not None:
            return (f"'{category}': JEFFEREY may accept a price for you of no less than "
                    f"{_money(p['floor'], cur)}")
        if p.get("cap") is not None:
            return (f"'{category}': JEFFEREY may act for you, spending at most "
                    f"{_money(p['cap'], cur)} in {PERIOD_WORDS.get(p.get('period'), PERIOD_WORDS[LEGACY_PERIOD])}"
                    f" (and never more than that on one thing)")
        return f"'{category}': JEFFEREY may act for you, but never on anything that costs money"

    def set_permission(self, category: str, level: str, cap: float | None = None,
                       period: str | None = None, currency: str | None = None,
                       floor: float | None = None) -> dict:
        """The owner's own decision about a kind of act — never an AI's. It
        runs only at the owner's keyboard (/permit), or in his own tools.

        'act' on anything that costs money needs a limit (cap) and a period:
        the limit is the most for one thing AND the most in any day, week or
        month together (I-44: ten $99 orders passed a $100 limit). Selling
        needs a lowest price (floor) instead. Moving money, gift cards,
        crypto, phone calls, the owner's voice and the doors are never
        'act', for anyone."""
        import access
        access.require_owners_hands("change what JEFFEREY may do for him")
        cat, entry = self.check_permission(category, level, cap, period, currency, floor)
        entry["updated"] = _now()
        self._stamp(entry, "owner")
        self.data["permissions"][cat] = entry
        self.data["actions"].append(self._stamp({
            "category": cat,
            "description": "permission set: " + self.describe_permission(cat, entry),
            "amount": None, "outcome": "permission_change",
            "added": _now(), "ts": time.time(),
        }, "jefferey"))
        self._save()
        return {"category": cat, **entry}

    def check_permission(self, category: str, level: str, cap: float | None = None,
                         period: str | None = None, currency: str | None = None,
                         floor: float | None = None) -> tuple[str, dict]:
        """The permission exactly as it would be saved, or ValueError in
        plain words — so the owner is read back only a change that can be
        made. Saves nothing."""
        cat = self._cat(category)
        if not cat or len(cat) > 60:
            raise ValueError("Name the kind of thing in a few words, for example 'groceries'.")
        lvl = str(level or "").strip().lower()
        if lvl not in self.LEVELS:
            raise ValueError("The level must be one of: observe, recommend or act.")
        cur = str(currency or DEFAULT_CURRENCY).strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", cur):
            raise ValueError("The currency must be three letters, for example CAD.")
        entry: dict[str, Any] = {"level": lvl, "cap": None}
        if lvl == "act":
            never = self._never(cat)
            if never:
                raise ValueError(
                    f"JEFFEREY never acts on '{cat}' ({never}) — not for anyone, at any "
                    f"level. He can only bring it to you.")
            if _SALEISH.search(cat):
                fl = _real_number(floor)
                if fl is None or fl <= 0:
                    raise ValueError(
                        f"Selling needs the lowest price you would accept, for example: "
                        f"/permit {cat} act at least 500")
                entry.update(floor=round(fl, 2), currency=cur)
            elif cap is not None or _MONEYISH.search(cat):
                c = _real_number(cap)
                if c is None or c < 0:
                    raise ValueError(
                        f"Anything that costs money needs a limit, for example: "
                        f"/permit {cat} act 100 per week")
                per = str(period or LEGACY_PERIOD).strip().lower()
                if per not in PERIODS:
                    raise ValueError("The limit must be per day, per week or per month.")
                entry.update(cap=round(c, 2), period=per, currency=cur)
        return cat, entry

    def permission_for(self, category: str) -> dict:
        """Default is 'recommend': watch, learn, bring options — never act.
        Older stores are read as they are: a limit saved before limits had a
        period counts per month, in Canadian dollars; a limit that is not a
        number is unreadable, and nothing is approved under it."""
        raw = self.data["permissions"].get(self._cat(category))
        if not isinstance(raw, dict):
            return {"level": "recommend", "cap": None}
        p = dict(raw)
        lvl = str(p.get("level") or "").strip().lower()
        p["level"] = lvl if lvl in self.LEVELS else "recommend"
        for k in ("cap", "floor"):
            if p.get(k) is None:
                continue
            v = p[k]
            if isinstance(v, str):
                try:
                    v = float(v.replace("$", "").replace(",", "").strip())
                except ValueError:
                    v = None
            v = _real_number(v)
            if v is None or v < 0:
                p[k] = None
                p["unreadable_limit"] = True
            else:
                p[k] = v
        if p.get("cap") is not None and p.get("period") not in PERIODS:
            p["period"] = LEGACY_PERIOD
        if p.get("cap") is not None or p.get("floor") is not None:
            p["currency"] = str(p.get("currency") or DEFAULT_CURRENCY).upper()
        return p

    def _spent(self, category: str, period: str, currency: str, now: float) -> float:
        """What has been approved in this category within the period."""
        since = now - PERIODS.get(period, PERIODS[LEGACY_PERIOD])
        total = 0.0
        for a in self.data.get("actions") or []:
            if (isinstance(a, dict) and a.get("outcome") == "allowed"
                    and a.get("category") == category
                    and str(a.get("currency") or DEFAULT_CURRENCY).upper() == currency):
                try:
                    ts = float(a.get("ts") or 0)
                except (TypeError, ValueError):
                    continue
                amt = _real_number(a.get("amount"))
                if ts >= since and amt:
                    total += amt
        return round(total, 2)

    def _judge(self, cat: str, desc: str, amount, cur: str, recurring: bool,
               perm: dict, now: float) -> dict:
        shown = {k: perm.get(k) for k in ("level", "cap", "period", "currency", "floor")
                 if perm.get(k) is not None}
        shown.setdefault("cap", None)

        def no(reason: str, **kw) -> dict:
            return {"allowed": False, "reason": reason, **shown, **kw}

        never = self._never(cat, desc)
        if never:
            return no(f"JEFFEREY never does this ({never}), whatever anyone has set. "
                      f"Only the owner can, himself. Tell him plainly what was asked "
                      f"— it may be a scam.")
        if perm["level"] != "act":
            return no(f"'{cat}' is at '{perm['level']}': bring it to the owner as a "
                      f"suggestion instead. Only he can raise the level, himself.")
        if recurring or _RECURRING.search(desc.lower()):
            return no("This repeats or has a minimum term, so it is a commitment, not "
                      "one purchase. Only the owner can agree to that — ask him.")
        amt = None if amount is None else _real_number(amount)
        if amount is not None and amt is None:
            return no("The amount given is not a real price. State the full price as "
                      "a plain number; nothing is approved without it.")
        if amt is not None and amt < 0:
            return no("The amount cannot be below zero. State the full price as a plain "
                      "number; nothing is approved without it.")
        if perm.get("unreadable_limit"):
            return no(f"The limit saved for '{cat}' is not a number JEFFEREY can read, so "
                      f"nothing is approved under it. The owner can set it again himself.")
        pcur = perm.get("currency") or DEFAULT_CURRENCY
        named = _currency_named(desc)
        if (perm.get("cap") is not None or perm.get("floor") is not None) and (
                cur != pcur or (named and named != pcur)):
            return no(f"The owner's limit is in {pcur}, and this is in {named or cur}. "
                      f"JEFFEREY does not convert money — ask the owner.")
        if perm.get("floor") is not None:
            if amt is None or amt <= 0:
                return no("Say the full sale price as a plain number (for example 450); "
                          "nothing is approved without it.")
            if amt < perm["floor"]:
                return no(f"{_money(amt, pcur)} is below the lowest price the owner set for "
                          f"'{cat}' ({_money(perm['floor'], pcur)}). Bring the offer to him.")
            return {"allowed": True, "reason": "at or above the lowest price the owner set",
                    **shown}
        cap = perm.get("cap")
        if cap is not None:
            if amt is None or amt <= 0:
                return no("State the full price as a plain number (for example 42.50); "
                          "nothing that costs money is approved without it.")
            if amt > cap:
                return no(f"{_money(amt, pcur)} is more than the owner's limit of "
                          f"{_money(cap, pcur)} for '{cat}'. Ask him first.")
            spent = self._spent(cat, perm["period"], pcur, now)
            words = PERIOD_WORDS[perm["period"]]
            if spent + amt > cap + 0.005:
                return no(f"{_money(spent, pcur)} has already been approved for '{cat}' in "
                          f"{words}; {_money(amt, pcur)} more would pass the owner's limit "
                          f"of {_money(cap, pcur)}. Ask him first.",
                          spent_this_period=spent,
                          left_this_period=round(max(0.0, cap - spent), 2))
            return {"allowed": True, "reason": "within the limit the owner set", **shown,
                    "spent_this_period": round(spent + amt, 2),
                    "left_this_period": round(max(0.0, cap - spent - amt), 2)}
        if _MONEYISH.search(cat):
            return no(f"No spending limit is set for '{cat}', so nothing that costs money "
                      f"can be approved there. Only the owner can set one, himself.")
        if (amt is not None and amt != 0) or _MONEY_TEXT.search(desc.lower()):
            return no(f"The owner allowed '{cat}' only for things that cost nothing and "
                      f"move no money; this one involves money. Bring it to him.")
        return {"allowed": True, "reason": "within the authority the owner gave "
                                          "(nothing that costs money)", **shown}

    def authorize_action(self, category: str, description: str,
                         amount: float | None = None, currency: str | None = None,
                         recurring: bool = False) -> dict:
        """THE gate. Called before any real-world act. Silence is a no: with
        no permission, no amount, or an amount that is not a real price, the
        answer is no. Every answer is written down, with who asked and
        through which door; a yes carries a single-use authorization id,
        good for AUTH_MINUTES, that log_action must cite."""
        now = time.time()
        cat = self._cat(category)
        desc = str(description or "").strip()
        perm = self.permission_for(cat)
        cur = str(currency or perm.get("currency") or DEFAULT_CURRENCY).strip().upper()
        verdict = self._judge(cat, desc, amount, cur, bool(recurring), perm, now)
        amt = None if amount is None else _real_number(amount)
        entry: dict[str, Any] = {
            "category": cat, "description": desc[:300], "amount": amt, "currency": cur,
            "added": _now(), "ts": now,
        }
        if amount is not None and amt is None:
            entry["amount_given"] = str(amount)[:40]
        if verdict["allowed"]:
            aid = "au-" + secrets.token_hex(5)
            until = now + AUTH_MINUTES * 60
            entry.update(outcome="allowed", authorization_id=aid, expires_ts=until,
                         expires=time.strftime("%H:%M", time.localtime(until)))
            verdict.update(authorization_id=aid, expires=entry["expires"],
                           note=f"Use this approval once, for exactly this, within "
                                f"{AUTH_MINUTES} minutes. Afterwards call log_action with "
                                f"authorization_id='{aid}'.")
        else:
            entry["outcome"] = "denied: " + verdict["reason"]
        self.data["actions"].append(self._stamp(entry, "jefferey"))
        self._save()
        return verdict

    def _approval_problem(self, aid: str, cat: str, amt: float | None) -> tuple[str | None, dict | None]:
        who, _ = _who()
        for a in reversed(self.data.get("actions") or []):
            if isinstance(a, dict) and a.get("authorization_id") == aid \
                    and a.get("outcome") == "allowed":
                break
        else:
            return "JEFFEREY never gave that approval", None
        if a.get("by") != who:
            return "that approval was given to another connection", None
        if a.get("used"):
            return "that approval was already used", None
        try:
            if float(a.get("expires_ts") or 0) < time.time():
                return f"that approval ran out (each lasts {AUTH_MINUTES} minutes)", None
        except (TypeError, ValueError):
            return "that approval cannot be read", None
        if a.get("category") != cat:
            return f"that approval was for '{a.get('category')}', not '{cat}'", None
        approved = _real_number(a.get("amount"))
        if approved is not None:
            if amt is None:
                return "the amount spent was not stated", None
            if amt > approved + 0.005:
                return (f"{_money(amt, a.get('currency') or DEFAULT_CURRENCY)} is more than "
                        f"the {_money(approved, a.get('currency') or DEFAULT_CURRENCY)} "
                        f"that was approved"), None
        return None, a

    def log_action(self, category: str, description: str, outcome: str,
                   amount: float | None = None, authorization_id: str = "") -> dict:
        """Every executed act is written down. No silent actions, ever — and
        no forged ones: an outcome JEFFEREY writes itself (a permission
        change, an approval) cannot be written by an engine, every line says
        who wrote it, and an act that cites no valid approval is kept but
        marked as not approved, where the owner sees it."""
        cat = self._cat(category)
        out = str(outcome or "").strip()
        if not out:
            return {"refused": True, "reason": "Say what happened in a word or two, "
                                               "for example 'done' or 'sent'."}
        if _RESERVED_OUTCOME.search(out):
            return {"refused": True,
                    "reason": "That outcome is one JEFFEREY writes itself (a permission "
                              "change, an approval or a refusal), so it cannot be written "
                              "by an AI. Say what you did in your own words, for example "
                              "'done' or 'sent'.",
                    "tell_the_user": "Nothing was written. Describe the act plainly."}
        amt = None if amount is None else _real_number(amount)
        if amount is not None and amt is None:
            return {"refused": True, "reason": "The amount is not a real number. Give the "
                                               "amount spent as a plain number."}
        entry: dict[str, Any] = {
            "category": cat, "description": str(description or "").strip()[:300],
            "amount": amt, "outcome": out[:120], "added": _now(), "ts": time.time(),
        }
        aid = str(authorization_id or "").strip()
        problem, auth = (self._approval_problem(aid, cat, amt) if aid
                         else ("no approval was cited", None))
        if auth is not None:
            entry.update(authorization_id=aid, approved=True)
            auth["used"] = _now()
        else:
            entry.update(authorization_id=aid or None, approved=False,
                         note=f"Not an approved act: {problem}. The owner sees this "
                              f"line marked that way.")
        self.data["actions"].append(self._stamp(entry, "engine"))
        self._save()
        return entry

    def action_log(self, limit: int = 20) -> list[dict]:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(200, limit))
        return self.data["actions"][-limit:][::-1]

    # ------------------------------------------------------------ opportunity engine
    # "What can I do today to make this person's life better?" — observations
    # come in, opportunities get scored against THEIR priorities, and only
    # what clears the bar earns the right to interrupt — and only when it
    # came from his caretaker or himself (I-40: a plain guest session planted
    # a fake RBC fraud alert at the top of his brief).

    def log_observation(self, note: str, category: str = "general") -> dict:
        entry = {"note": note.strip(), "category": category,
                 "added": _now(), "ts": time.time()}
        self.data["observations"].append(entry)
        self._save()
        return entry

    @staticmethod
    def _score(what: str, value_estimate: str = "", aligns_with: str = "",
               advances_goal: str = "", reduces_risk=False, urgency=0.5) -> dict:
        """Score by the spec's questions: does it align with their
        priorities, advance a goal, reduce a risk, and is it urgent?
        >= 0.75 earns an interrupt; >= 0.40 waits for the brief; else holds."""
        u = _real_number(urgency)
        u = 0.5 if u is None else max(0.0, min(1.0, u))
        if not isinstance(reduces_risk, bool):
            reduces_risk = str(reduces_risk).strip().lower() in ("true", "1", "yes")
        score = round(
            0.20
            + (0.25 if str(aligns_with or "").strip() else 0)
            + (0.20 if str(advances_goal or "").strip() else 0)
            + (0.15 if reduces_risk else 0)
            + 0.20 * u,
            2,
        )
        status = "interrupt" if score >= 0.75 else "brief" if score >= 0.40 else "hold"
        text = f"{what} {value_estimate}".lower()
        signs = [why for rx, why in _SCAM_SIGNS if rx.search(text)]
        return {"what": str(what or "").strip(), "value_estimate": value_estimate,
                "aligns_with": aligns_with, "advances_goal": advances_goal,
                "reduces_risk": reduces_risk, "urgency": u, "score": score,
                "status": status, "scam_signals": signs}

    def score_opportunity(self, what: str, value_estimate: str = "", aligns_with: str = "",
                          advances_goal: str = "", reduces_risk=False, urgency=0.5) -> dict:
        """The same score, saved nowhere: for keys that may read goals but
        not write to the owner's brief."""
        s = self._score(what, value_estimate, aligns_with, advances_goal,
                        reduces_risk, urgency)
        if not s["scam_signals"]:
            s.pop("scam_signals")
        s["note"] = "Scored only; nothing was saved."
        return s

    def record_opportunity(self, what: str, value_estimate: str = "",
                           aligns_with: str = "", advances_goal: str = "",
                           reduces_risk=False, urgency=0.5) -> dict:
        """Score it and keep it for the brief. It records who saved it; only
        the owner or a caretaker key (one holding act.request) can make it
        interrupt, and anything with the marks of a scam — a number to call,
        gift cards, a card or PIN to read out — never interrupts, and is
        shown with a warning."""
        import access
        entry = self._score(what, value_estimate, aligns_with, advances_goal,
                            reduces_risk, urgency)
        who, where = _who()
        caretaker = access.is_caretaker(who)
        signs = entry.pop("scam_signals")
        entry["source"], entry["surface"] = who, where
        entry["may_interrupt"] = bool(caretaker and not signs)
        if entry["status"] == "interrupt" and not entry["may_interrupt"]:
            entry["status"] = "brief"
            entry["note"] = ("Kept for the daily brief, not as an interruption: "
                             + ("it has the marks of a scam." if signs else
                                "only the owner's caretaker key, or the owner, can "
                                "raise an interruption."))
        if signs:
            entry["scam_signals"] = signs
            entry["warning"] = ("This has the marks of a scam (" + ", ".join(signs) + "). "
                                "Do not call a number in it or read anything out to "
                                "anyone; check through a number the owner already has.")
        entry.update(resolved=False, added=_now(), ts=time.time())
        self.data["opportunities"].append(entry)
        self._save()
        return entry

    def pending_opportunities(self) -> list[dict]:
        return sorted(
            [o for o in self.data["opportunities"] if not o["resolved"]],
            key=lambda o: -o["score"],
        )

    @staticmethod
    def _as_shown(o: dict) -> dict:
        """An opportunity as the brief and the orb treat it. One saved before
        October 2026 records no source, so it cannot interrupt either."""
        o = dict(o)
        if o.get("status") == "interrupt" and not o.get("may_interrupt"):
            o["status"] = "brief"
        o.setdefault("source", "not recorded (saved before October 2026)")
        return o

    def _shown_opportunities(self) -> list[dict]:
        rank = {"interrupt": 0, "brief": 1, "hold": 2}
        return sorted((self._as_shown(o) for o in self.pending_opportunities()),
                      key=lambda o: (rank.get(o.get("status"), 3),
                                     bool(o.get("scam_signals")), -o.get("score", 0)))

    def resolve_opportunity(self, contains: str = "", outcome: str = "done",
                            ids=None, confirm: str = "") -> dict:
        """Two steps, like every change that takes something away
        (forgetting.py)."""
        import forgetting
        return forgetting.resolve_opportunities(self, contains, outcome, ids, confirm)

    def orb_state(self) -> dict:
        """The predictive cycle: the orb's mood is the engine's real state,
        so the user reads Jefferey like a face."""
        now = time.time()
        pending = self._shown_opportunities()
        recent_corr = any(
            c.get("ts", 0) > now - 48 * 3600 for c in self.data["corrections"]
        )
        if any(o.get("reduces_risk") and o["status"] == "interrupt" for o in pending):
            return {"mood": "protective",
                    "reason": "a risk to the user needs attention"}
        if any(o["status"] == "interrupt" for o in pending):
            return {"mood": "charged",
                    "reason": "found something worth interrupting for"}
        if any(o["status"] == "brief" for o in pending):
            return {"mood": "curious",
                    "reason": "opportunities waiting in the daily brief"}
        if recent_corr:
            return {"mood": "happy", "reason": "learned something new recently"}
        if any(ob.get("ts", 0) > now - 24 * 3600 for ob in self.data["observations"]):
            return {"mood": "thinking", "reason": "digesting new observations"}
        return {"mood": "calm", "reason": "all quiet, watching"}

    def daily_brief(self) -> dict:
        """One screen: what he noticed, what he suggests, what he did — and
        who wrote each line. A key that does not hold his private life sees
        no line about his health, money, children, home or someone else's
        confidence, and every engine is kept from what his own rules forbid
        (I-11: a plain guest session read 'booked VAC mental-health intake')."""
        import rules as _rules
        rd = provenance.reader()
        obs = self.data["observations"][-5:][::-1]
        acts = self.action_log(10)
        held = 0
        if not rd["owner"]:
            def ok(text, cat):
                kinds = grounding.sensitivity(text, cat)
                if kinds and not rd["caretaker"]:
                    return False
                return not _rules.held_back(self.data, rd["audiences"], text,
                                            [str(cat or "")] + kinds)
            keep_obs = [o for o in obs if ok(o.get("note", ""), o.get("category", ""))]
            keep_acts = [a for a in acts if ok(a.get("description", ""), a.get("category", ""))]
            held = len(obs) - len(keep_obs) + len(acts) - len(keep_acts)
            obs, acts = keep_obs, keep_acts
        out = {
            "orb": self.orb_state(),
            "active_goals": [g["goal"] for g in self.data["goals"] if g["active"]],
            "opportunities": self._shown_opportunities()[:10],
            "recent_actions": acts,
            "recent_observations": obs,
            "corrections_learned_from": len(self.data["corrections"]),
            # a recovery, a restore, a change made by hand, a change to the
            # caretaker, family or executor key: the owner is told
            "notices": self.notices(),
        }
        if held:
            out["held_back"] = {"count": held, "why": (
                "Some recent lines are private, or kept from this connection by his "
                "own rules. Do not guess at them.")}
        if rd["owner"] or rd["caretaker"]:
            waiting = len(self.pending_items())
            if waiting:
                out["waiting_for_owner"] = {"count": waiting, "how": (
                    "Things an AI wrote down that he has not confirmed, or asked to "
                    "share. He sees them with /pending in 'Talk to JEFFEREY on this Mac'.")}
        return out

    # ------------------------------------------------------------ views
    def snapshot(self, limit=None, offset=0, top: int = 50) -> dict:
        """What the reasoning engine may see of the whole conscience — never
        all of it at once (I-41: 5,000 facts were 900,000 characters, past any
        engine's reading), and never what is private to an engine that may
        not hold it (I-11). The most recent facts first, a page at a time; the values
        he holds most surely first. What is held back is counted, not shown."""
        rd = provenance.reader()
        facts, held = self.visible_facts(rd, bulk=True)
        lim, off = _page(limit, offset, FACTS_PAGE, FACTS_MAX)
        # the newest page first (offset reaches further back), each page in
        # the order he told them
        end = max(0, len(facts) - off)
        page = facts[max(0, end - lim):end]
        prios = sorted((p for p in self.data["priorities"] if isinstance(p, dict)),
                       key=lambda p: -float(p.get("confidence") or 0))
        out = {
            "owner": self.data.get("owner"),
            "priorities": [self._prio_view(p) for p in prios[:top]],
            "facts": [self._fact_view(f) for f in page],
            "active_goals": [g for g in self.data["goals"] if g.get("active")],
            "corrections_learned_from": len(self.data["corrections"]),
            "notices": self.notices(),
        }
        if len(prios) > top:
            out["more_priorities"] = len(prios) - top
        if len(facts) > off + lim:
            out["more_facts"] = len(facts) - off - lim
            out["how_to_see_more"] = (f"Older facts: call again with offset={off + lim}, "
                                      f"or ask explain_basis about the subject you need.")
        private = sum(1 for _, why in held if why == "private")
        ruled = sum(1 for _, why in held if why == "rules")
        if private or ruled:
            out["held_back"] = {
                "private": private, "by_his_rules": ruled,
                "why": ("Private facts (his health, money, children, the safety of his "
                        "home, other people's confidences) are not sent all at once. "
                        + ("Ask explain_basis about the subject and the ones that matter "
                           "come back. " if rd["caretaker"] else "")
                        + "Never guess at what is held back.")}
        if rd["owner"] or rd["caretaker"]:
            waiting = len(self.pending_items())
            if waiting:
                out["waiting_for_owner"] = waiting
        return out

    def owner_view(self) -> dict:
        """Everything, for the owner's own screen (/conscience) — never sent
        anywhere."""
        return {
            "store_path": str(self.path),
            "owner": self.data.get("owner"),
            "priorities": sorted((p for p in self.data["priorities"] if isinstance(p, dict)),
                                 key=lambda p: -float(p.get("confidence") or 0)),
            "facts": self.data["facts"],
            "active_goals": [g for g in self.data["goals"] if g.get("active")],
            "corrections_learned_from": len(self.data["corrections"]),
            "notices": self.notices(),
            "waiting_for_you": self.pending_items(),
        }

    def explain_basis(self, topic: str, limit=None, offset=0) -> dict:
        """The grounding for a recommendation: which of the USER'S OWN values
        and facts apply to this topic. Every recommendation must be
        explainable in these terms — never hidden incentives.

        Whole words, never fragments (I-28: 'car' grounded a caregiver
        choice, 'rent' pulled a PTSD medication into a landlord letter): a
        value applies when every word of its context is in the subject; a
        fact when it shares a word with the subject, or the subject names
        its kind ('my medications' names his health). A subject that names
        nothing is refused. Most relevant first, at most ten values and a
        page of facts, each with the reason it matched. Facts come back only
        to a key that may read facts (I-23), private ones only to his
        caretaker key, and nothing his rules keep from this engine."""
        t = str(topic or "").strip()
        problem = grounding.topic_problem(t)
        if problem:
            return {"topic": t, "priorities": [], "facts": [], "note": problem}
        tw = grounding.expand(grounding.content(t))
        rows = []
        for p in self.data["priorities"]:
            if not isinstance(p, dict):
                continue
            m = grounding.context_match(p.get("context", ""), tw)
            if m:
                rows.append(((0 if m[0] == "about" else 1, provenance.pending(p),
                              -float(p.get("confidence") or 0)), self._prio_view(p, m[1])))
        rows.sort(key=lambda r: r[0])
        out = {
            "topic": t,
            "priorities": [v for _, v in rows[:BASIS_PRIORITIES]],
            "facts": [],
            "rule": (
                "Explain the recommendation strictly in terms of these priorities "
                "and facts. If confidence is low, say so and ask. Anything marked "
                "unconfirmed was written down by an AI and not yet confirmed by him: "
                "say so if you rely on it. If nothing is relevant, say you don't know "
                "this person's values here yet."
            ),
        }
        import access
        if not access.may("facts.read"):
            out["note"] = ("The key this connection holds may not read the owner's "
                           "facts, so none are included.")
            return out
        rd = provenance.reader()
        seen, held = self.visible_facts(rd, bulk=False)
        scored = []
        for f in seen:
            m = grounding.fact_match(f.get("fact", ""), f.get("category", ""),
                                     f.get("sensitivity") or [], tw)
            if m:
                scored.append(((-m[0], provenance.pending(f)), f, m[1]))
        scored.sort(key=lambda r: r[0])
        lim, off = _page(limit, offset, BASIS_FACTS, BASIS_MAX)
        out["facts"] = [self._fact_view(f, why) for _, f, why in scored[off:off + lim]]
        if len(scored) > off + lim:
            out["more_facts"] = len(scored) - off - lim
            out["how_to_see_more"] = f"Call again with offset={off + lim}."
        kept = sum(1 for f, _ in held
                   if grounding.fact_match(f.get("fact", ""), f.get("category", ""),
                                           f.get("sensitivity") or [], tw))
        if kept:
            out["held_back"] = {"count": kept, "why": (
                "Some facts on this subject are private, or kept from this connection "
                "by his own rules. Do not guess at them.")}
        return out

    # ------------------------------------------------------- waiting for him
    _CONFIRMABLE = ("facts", "priorities", "memories", "media")

    def pending_items(self) -> list[dict]:
        """What waits for the owner's own yes: things an AI wrote down in its
        own words, values it says changed, and requests to share something
        more widely. Shown with /pending in 'Talk to JEFFEREY on this Mac'."""
        out = []
        for f in self.data.get("facts") or []:
            if isinstance(f, dict) and provenance.pending(f):
                out.append({"id": f.get("id"), "kind": "fact", "what": f.get("fact", ""),
                            "why": "an AI wrote it down; you have not confirmed it"})
        for p in self.data.get("priorities") or []:
            if not isinstance(p, dict):
                continue
            what = f"for {p.get('context')}: {p.get('higher')} over {p.get('lower')}"
            if isinstance(p.get("proposed"), dict):
                out.append({"id": p.get("id"), "kind": "change of a value",
                            "what": (f"for {p.get('context')}: {p['proposed'].get('higher')} "
                                     f"over {p['proposed'].get('lower')} — you had said "
                                     f"{p.get('higher')} over {p.get('lower')}"),
                            "why": "an AI says this changed; confirming changes it"})
            elif p.get("question"):
                out.append({"id": p.get("id"), "kind": "question about a value", "what": what,
                            "why": "a recent choice went the other way; confirming keeps it"})
            elif provenance.pending(p):
                out.append({"id": p.get("id"), "kind": "value", "what": what,
                            "why": "an AI wrote it down; you have not confirmed it"})
        for sec, kind in (("memories", "moment"), ("media", "picture or recording")):
            for m in self.data.get(sec) or []:
                if not isinstance(m, dict):
                    continue
                what = (m.get("text") or m.get("caption") or m.get("path") or "")[:160]
                if provenance.pending(m):
                    out.append({"id": m.get("id"), "kind": kind, "what": what,
                                "why": "kept in an AI's words, not yours; confirming says it is right"})
                ask = m.get("requested_visibility")
                if ask and ask != m.get("visibility"):
                    out.append({"id": m.get("id"), "kind": "request to share", "what": what,
                                "why": f"an AI asked to make it '{ask}'; type /share "
                                       f"{m.get('id')} {ask} if you want that"})
        for f in self.data.get("facts") or []:
            ask = f.get("requested_visibility") if isinstance(f, dict) else None
            if ask and ask != f.get("visibility"):
                out.append({"id": f.get("id"), "kind": "request to share",
                            "what": f.get("fact", ""),
                            "why": f"an AI asked to make it '{ask}'; type /share "
                                   f"{f.get('id')} {ask} if you want that"})
        return out

    def _find_item(self, item_id: str, sections=None) -> tuple[str | None, dict | None]:
        i = str(item_id or "").strip()
        for sec in sections or ("facts", "priorities", "memories", "media", "people"):
            for it in self.data.get(sec) or []:
                if isinstance(it, dict) and it.get("id") == i:
                    return sec, it
        return None, None

    def confirm(self, ids) -> dict:
        """The owner says: yes, that is right. Only his own hands (/confirm,
        typed at his terminal). A value an AI said had changed is changed
        now, and the change is logged as his."""
        import access
        access.require_owners_hands("confirm what an AI wrote down")
        want = [str(x).strip() for x in (ids if isinstance(ids, (list, tuple))
                                         else str(ids or "").replace(",", " ").split())
                if str(x).strip()]
        if want == ["all"]:
            want = [x["id"] for x in self.pending_items() if x["kind"] != "request to share"]
        done, unknown = [], []
        src = provenance.source()
        for i in want:
            sec, it = self._find_item(i, self._CONFIRMABLE)
            if it is None:
                unknown.append(i)
                continue
            if sec == "priorities" and isinstance(it.get("proposed"), dict):
                pr = it.pop("proposed")
                was = f"{it.get('higher')} > {it.get('lower')}"
                self._log_change("reversal", it.get("context", ""), was,
                                 f"{pr.get('higher')} > {pr.get('lower')}", src, applied=True)
                it.update(higher=pr.get("higher"), lower=pr.get("lower"), stated=True,
                          stated_confidence=_real_number(pr.get("confidence")) or 0.6)
                it["for"], it["against"] = 0, 0
            it.pop("question", None)
            it["status"] = "confirmed"
            it["confirmed_by_owner"] = _now()
            if sec == "priorities":
                it["evidence"] = int(it.get("for") or 0) + int(it.get("against") or 0) or 1
                it["confidence"] = self._confidence(it)
            done.append(i)
        if done:
            self._save()
        return {"confirmed": done, "unknown_ids": unknown}

    def set_visibility(self, ids, visibility: str) -> dict:
        """Who may see something: a fact ('private', 'engines', 'family',
        'legacy'), or a moment, picture or person ('private', 'family',
        'legacy'). Making something MORE private is free to any key that
        may write; letting more people see it is the owner's own act (/share,
        typed himself) — an AI that asks gets a plain answer, and the
        request waits in /pending (I-26)."""
        import access
        want = grounding.normalise(visibility)
        id_list = [str(x).strip() for x in (ids if isinstance(ids, (list, tuple))
                                            else str(ids or "").replace(",", " ").split())
                   if str(x).strip()]
        if not id_list:
            return _refusal("set_visibility", "Name what to change by its id (from "
                                              "who_am_i or get_conscience).")
        changed, not_changed, need_owner = [], [], []
        for i in id_list:
            sec, it = self._find_item(i, ("facts", "memories", "media", "people"))
            if it is None:
                not_changed.append({"id": i, "why": "nothing has that id"})
                continue
            allowed = FACT_VISIBILITY if sec == "facts" else LIFE_VISIBILITY
            if want not in allowed:
                not_changed.append({"id": i, "why": "it can be one of: " + ", ".join(allowed)})
                continue
            if sec == "facts" and not access.may("facts.write"):
                not_changed.append({"id": i, "why": "this key may not change facts"})
                continue
            cur = it.get("visibility") or ("engines" if sec == "facts" else "private")
            if cur == want:
                not_changed.append({"id": i, "why": f"it is already '{want}'"})
                continue
            if want != "private" and not access.owners_hands():
                it["requested_visibility"] = want
                need_owner.append(i)
                continue
            it["visibility"] = want
            it.pop("requested_visibility", None)
            it["visibility_changed"] = {"from": cur, "to": want, "by": access.who(),
                                        "at": _now()}
            changed.append({"id": i, "from": cur, "to": want})
        if changed or need_owner:
            self._save()
        out: dict = {"changed": changed}
        if not_changed:
            out["not_changed"] = not_changed
        if need_owner:
            out["needs_owner"] = need_owner
            out["tell_the_user"] = (
                "Only he can let more people see something. If he wants it, he types "
                f"/share {' '.join(need_owner)} {want} himself in 'Talk to JEFFEREY on "
                "this Mac'. Nothing was widened.")
        return out


# ------------------------------------------------------------ the owner's view
def _too_new_text(need: str) -> str:
    return (f"Your memories were last saved by a newer JEFFEREY (version {need}) "
            f"than this copy (version {__version__}), so this copy will not touch "
            "them: it may not know how to keep them safe. Double-click 'Update "
            "JEFFEREY.command', then try again. Nothing was changed.")


def _check_version(obj: dict, where=None) -> None:
    need = obj.get(VERSION_KEY) if isinstance(obj, dict) else None
    if isinstance(need, str) and _newer(need, __version__):
        raise ConscienceTooNew(_too_new_text(need), where)


def health(path: Path | str | None = None) -> dict:
    """How the owner's memories are, in one plain line — for the installer and
    'install --check'. Reads only: it never recovers, writes or moves anything.

    status: new | ok | recovered | will_recover | needs_restoring"""
    p = Path(path or DEFAULT_STORE).expanduser()
    c = Conscience.__new__(Conscience)
    c._init_fields(p)

    newest_good = c._good_copy

    if not p.exists():
        good = newest_good()
        if good:
            return {"status": "will_recover", "plain": (
                "Your memories: the file is missing, but a copy saved "
                f"{_when(c._snap_time(good))} exists. JEFFEREY will put it back "
                "when he next starts.")}
        return {"status": "new", "plain": "Your memories: none yet. That is "
                "normal before the first conversation."}
    try:
        st = p.stat()
        raw = p.read_bytes()
    except OSError as exc:
        return {"status": "needs_restoring", "plain": (
            f"Your memories: JEFFEREY cannot open the file ({exc.strerror or exc}).")}
    try:
        obj = Conscience._parse(raw)
    except _Unreadable as u:
        good = newest_good()
        if u.torn and (u.certain or c._could_be_tear(st)) and good:
            return {"status": "will_recover", "plain": (
                f"Your memories: the file is damaged ({u.plain}). JEFFEREY will "
                f"go back to the copy saved {_when(c._snap_time(good))} when he "
                "next starts; check what was said after that.")}
        if not good:
            return {"status": "needs_restoring", "plain": (
                f"Your memories need attention: the file cannot be read ({u.plain}) "
                "and there is no good copy to go back to. Put the file back from "
                "a backup.")}
        return {"status": "needs_restoring",
                "plain": "Your memories need attention. " + Conscience._fix_text(u)}
    try:
        _check_version(obj)
    except ConscienceTooNew as e:
        return {"status": "needs_update", "plain": "Your memories: " + e.plain}
    c.data = obj
    count = lambda k: len(obj[k]) if isinstance(obj.get(k), list) else 0  # noqa: E731
    line = (f"Your memories: OK — {count('facts')} facts, {count('memories')} "
            f"moments, {count('people')} people, revision {c._rev_of(obj)}.")
    ns = c.notices()
    if ns:
        return {"status": "recovered", "notices": ns,
                "plain": line + " Recently: " + " ".join(n["what"] for n in ns)}
    return {"status": "ok", "plain": line}


def _print_history(c: Conscience, limit: int | None) -> None:
    rows = c.history(limit)
    if not rows:
        print("  No copies are kept yet. They start with the first thing "
              "JEFFEREY remembers.")
        return
    print("  Copies of your memories, newest first:\n")
    for r in rows:
        what = (f"{r['facts']} facts, {r['moments']} moments, {r['people']} people"
                if r.get("readable") else "damaged — cannot be used")
        pin = f"   (kept {r['pinned']})" if r.get("pinned") else ""
        print(f"  {r['number']:>4}.  {r['saved'][3:]:<32} {what}{pin}")
    print("\n  To put one back:  restore <number>")


def edit(c: Conscience, editor: list[str] | None = None) -> int:
    """The owner's validated hand edit. A private copy of the memory file
    opens in a text editor; when it is saved and closed it is checked. A
    mistake is named by line and nothing changes (the edited copy is kept
    to fix); a good edit becomes the newest revision, with the version from
    before pinned so it can be undone. Editing the file directly also works
    — JEFFEREY notices and adopts it — this is the safe way."""
    import shlex
    import shutil
    import subprocess
    try:
        c.refresh()
    except StoreProblem:
        pass                                   # editing is how it gets fixed
    try:
        raw = c.path.read_bytes()
    except FileNotFoundError:
        print("  There are no memories to edit yet.")
        return 1
    fd, tmp = tempfile.mkstemp(prefix=".memories-edit-", suffix=".json",
                               dir=c.path.parent)
    with os.fdopen(fd, "wb") as fh:
        fh.write(raw)
    if editor is None:
        chosen = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if chosen:
            editor = shlex.split(chosen)
        elif sys.platform == "darwin":
            editor = ["open", "-W", "-t"]      # TextEdit; waits until it is closed
        else:
            editor = [shutil.which("nano") or "vi"]
    print("  Your memories are open in a text editor. Save, then close it.")
    subprocess.run(editor + [tmp])
    new = Path(tmp).read_bytes()
    if new == raw:
        os.unlink(tmp)
        print("  Nothing was changed.")
        return 0
    try:
        obj = Conscience._parse(new)
    except _Unreadable as u:
        print(f"  Not saved: {u.plain}. Your memories are exactly as they were.\n"
              f"  Your edited copy is kept at {tmp} — fix it and run this again.")
        return 1
    try:
        with c._lock():
            cur = c.path.read_bytes()
            if cur != raw:
                print("  Not saved: your memories changed while you were editing "
                      "(another app was using JEFFEREY). Nothing was lost.\n"
                      f"  Your edited copy is kept at {tmp}.")
                return 1
            try:
                rev = c._rev_of(c._parse(cur))
            except _Unreadable:
                rev = c._rev_seen
            c._pin_locked(cur, rev, "before an edit")
            c._replace_data(obj)
            c._note("edited", f"You changed your memories by hand {_when(time.time())}. "
                    "The version from before is kept as a copy.")
            c._commit_locked(check_disk=False)
    except OSError as exc:
        c._rollback()
        print(f"  Not saved: {_SAVE_FAILED} ({exc.strerror or exc})\n"
              f"  Your edited copy is kept at {tmp}.")
        return 1
    c._unavailable = None
    os.unlink(tmp)
    print("  Saved. The version from before is kept as a copy, if you change "
          "your mind ('Restore my memories').")
    return 0


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--path", default=None,
                        help="the memory file (default: where JEFFEREY keeps it)")
    ap = argparse.ArgumentParser(
        description="Your memories: check them, see the copies kept, put one back.",
        parents=[common])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("check", parents=[common], help="how are my memories?")
    h = sub.add_parser("history", parents=[common], help="the copies kept")
    h.add_argument("--all", action="store_true")
    r = sub.add_parser("restore", parents=[common], help="put a copy back")
    r.add_argument("which", help="the copy's number in 'history', or its file name")
    r.add_argument("--yes", action="store_true", help="do not ask first")
    sub.add_parser("dismiss", parents=[common], help="I have read the notices")
    sub.add_parser("edit", parents=[common], help="change them by hand, checked")
    a = ap.parse_args(argv)
    path = Path(a.path).expanduser() if a.path else DEFAULT_STORE

    away = None if a.path else home.problem()
    if away:
        # Never "none yet" when the drive that holds them is simply away.
        print("  Your memories: " + away + ".")
        return 1
    if a.cmd in (None, "check"):
        h = health(path)
        print("  " + h["plain"])
        return {"needs_restoring": 1, "will_recover": 2, "recovered": 2,
                "needs_update": 1}.get(h["status"], 0)

    c = Conscience.for_surface(path)
    if a.cmd == "history":
        _print_history(c, None if a.all else 30)
        return 0
    if a.cmd == "edit":
        return edit(c)
    if a.cmd == "dismiss":
        try:
            c.refresh()
            n = c.dismiss_notices()
        except StoreProblem as e:
            print("  " + e.for_owner())
            return 1
        print(f"  Marked {n} notice(s) as read.")
        return 0
    # restore
    try:
        snap = c._resolve_copy(a.which)
    except StoreProblem as e:
        print("  " + e.plain)
        _print_history(c, 30)
        return 1
    row = next((x for x in c.history(None) if x["file"] == snap.name), {})
    print(f"\n  The copy saved {row.get('saved', '?')[3:]}"
          + (f": {row['facts']} facts, {row['moments']} moments, {row['people']} people."
             if row.get("readable") else "."))
    print("  Your memories as they are now are kept as a copy first, so this can "
          "be undone.")
    if not a.yes:
        try:
            answer = input("  Put this copy back? Type yes and press return: ")
        except EOFError:
            answer = ""
        import answers
        if answers.yes_no(answer) is not True:
            print("  Nothing was changed.")
            return 1
    try:
        res = c.restore(snap.name)
    except StoreProblem as e:
        print("  " + e.for_owner())
        return 1
    print(f"  Done. Your memories are back to the copy saved {res['saved'][3:]} "
          f"({res['facts']} facts).")
    if res.get("kept_before_restore"):
        print("  What was there just before is kept: it is the copy marked "
              "'kept before restore' in the list, if you change your mind.")
    print("  If Claude or another app is open, it picks this up on its next "
          "question; there is no need to restart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
