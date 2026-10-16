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
    python connector/conscience.py confirm          say yes to what an AI noted
    python connector/conscience.py edit             change it by hand, checked
    python connector/conscience.py dismiss          I have read the notices
'restore' and 'confirm' want him at the keyboard (S6, round 8): stdin and
stdout terminals, the number shown on the screen typed back, --yes ignored.
'edit' and 'dismiss' want him there too (round 8 repair). What no check here
can stop: the memory file is a plain file, so a program with a shell on this
Mac can change the memory file directly (JEFFEREY adopts what it finds), and
one with a pseudo-terminal can type the number shown, until Touch ID (I-43).
Never let an AI run commands on the Mac that holds his memories.
"""

from __future__ import annotations

import argparse
import calendar
import codecs
import copy
import functools
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import stat as _stat
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Callable

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
# Every copy is a whole copy of the life, so all of them together are kept
# within a budget, and never so many that the drive fills and saving stops
# (verify: 430 copies of a 24 MB life would be over 10 GB). Over it, the
# copies that add least go first — the extra ones of the last day, then
# hourly, then the oldest — never the newest few or the newest pinned one.
HISTORY_MAX_BYTES = 2 * 1024 ** 3
HISTORY_PROTECT = 3          # the newest copies, never let go for space
HISTORY_FREE_SAVES = 10      # leave room on the drive for this many saves…
HISTORY_FREE_MIN = 256 * 1024 ** 2   # …and never less than this
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
LEGACY_FLIP_BELOW = 0.4       # an older value turns round only below this
# ...and only once the rules it was saved under (before October 2026) would
# have turned it round too: there a contradiction took 30% off its
# confidence, a choice that agreed added 15% of what was left, and it turned
# round below 0.25. So a value saved then is never easier to turn round now
# (R8: an old 0.55, the old default for every inferred value, turned round
# after 2 contradictions instead of 3, and 0.41-0.49 after 1 instead of 2).
_OLD_CONTRADICT, _OLD_REINFORCE, _OLD_FLIP_BELOW = 0.30, 0.15, 0.25
DEDUP_SECONDS = 600           # the same correction within ten minutes: once
FACT_VISIBILITY = ("private", "engines", "family", "legacy")
LIFE_VISIBILITY = ("private", "family", "legacy")
FACTS_PAGE, FACTS_MAX = 100, 500       # get_conscience
BASIS_FACTS, BASIS_MAX, BASIS_PRIORITIES = 10, 25, 10   # explain_basis
GOALS_SHOWN, NOTICES_SHOWN = 20, 10   # the newest; the rest are counted (verify I-41)


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


# ------------------------------------------- searches that find nothing (G2)
# Round 9: no search is an oracle — every match an engine asks for reads only
# what release would show it. And on top, a key that searches his memories
# for words that are not there, again and again, is guessing: twenty
# searches that find nothing within ten minutes pause that key's searches
# (by words, a topic, a subject or a theme) for an hour, said plainly, and
# the owner is told. A brute force of a four-digit PIN took forty seconds
# through forget_life (round 8, v2 F3). The owner at his own keyboard is
# never paused; reading without a search (the brief, who am I) goes on.
SEARCH_MISSES = 20
SEARCH_WINDOW = 10 * 60
SEARCH_PAUSE = 60 * 60
_search_clock = time.time       # tests move the clock


class _SearchWatch:
    """How many of each key's searches found nothing lately, beside the
    memory file (several surfaces share one key). Times only — never the
    words that were searched for."""

    def __init__(self, path: Path):
        self.path = path.with_name(path.stem + ".searches.json")

    def _load(self) -> dict:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return d if isinstance(d, dict) else {}

    def _store(self, d: dict) -> None:
        try:
            _make_dir(self.path.parent)
            _write_atomic(self.path, json.dumps(d, indent=1).encode("utf-8"))
        except (OSError, StoreProblem):
            pass                     # a full drive must not stop a search being refused

    def paused_until(self, key: str) -> float | None:
        e = self._load().get(key)
        until = float(e.get("paused_until") or 0) if isinstance(e, dict) else 0.0
        return until if until > _search_clock() else None

    def found_nothing(self, key: str) -> float | None:
        """Count one search that found nothing. When it is the one that makes
        twenty in ten minutes, the time the pause ends; otherwise None."""
        now = _search_clock()
        with _FileLock(self.path.with_name(self.path.name + ".lock")):
            d = self._load()
            e = d.get(key) if isinstance(d.get(key), dict) else {}
            misses = [float(t) for t in e.get("misses") or []
                      if isinstance(t, (int, float)) and now - float(t) < SEARCH_WINDOW]
            misses.append(now)
            until = None
            if len(misses) >= SEARCH_MISSES and float(e.get("paused_until") or 0) <= now:
                until = now + SEARCH_PAUSE
                e["paused_until"] = until
                misses = []
            e["misses"] = misses[-SEARCH_MISSES:]
            d[key] = e
            d = {k: v for k, v in d.items() if isinstance(v, dict) and (
                v.get("misses") or float(v.get("paused_until") or 0) > now)}
            self._store(d)
        return until


def _clock_words(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))


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
# A category is matched by what it ENDS with, so 'phone calls', 'the doors'
# and 'home alarm' are never — and 'voice lessons', 'alarm clock' and 'door
# dash' are ordinary things one can buy (verify I-44).
_NEVER = (
    (re.compile(r"\b(?:e ?transfers?|transfers?|wires?|wiring|interac|remittances?"
                r"|western ?union|money ?grams?|money ?orders?|pay ?pal|venmo|zelle)\b"),
     "moving money from one account to another"),
    (re.compile(r"\b(?:gift ?cards?|prepaid ?cards?|itunes|google ?play|steam ?cards?"
                r"|vouchers?)\b"), "buying gift cards"),
    (re.compile(r"\b(?:crypto\w*|bitcoins?|btc|ethereum|usdt|usdc|tether|stablecoins?"
                r"|litecoin|dogecoin)\b"), "crypto-currency"),
    (re.compile(r"\b(?:phone ?calls?|calls?|calling|voice|voices|intercoms?|doorbells?)$"),
     "speaking for the owner on the phone, in his voice or at the door"),
    (re.compile(r"\b(?:unlock\w*|locks?|alarms?|garage ?doors?|garage ?openers?|doors?)$"),
     "letting anyone into the house"),
)
# S9 (round 8): his home itself — the house, its security, its keys, who
# comes in — in English and French. Round 8 read only a wording that ENDED
# with one of these, and not through the shared fold: Cyrillic 'hоme', Greek
# 'Hοme', 'h0me', 'home security system', 'garage', 'serrures', 'chez moi'
# and thirty more took 'act' (round 8 repair). Now the category is read
# through grounding.fold, and a word of the home anywhere in it — or a word
# that starts with home, house or maison ('homesecurity', 'housekeeping') —
# makes it his home itself. Only what one buys for it ('household supplies',
# 'home supplies') is not. A category about his home is never 'act'; an
# errand under one is brought to him, never called a scam.
_HOME_ITSELF = re.compile(
    r"\b(?:homes?|houses?|maisons?|condos?|condominiums?|apartments?|appartements?"
    r"|apparts?|propert(?:y|ies)|proprietes?|security|securite|visitors?|visiteurs?"
    r"|guests?|invites?|keys?|cles?|clefs?|entry|entries|entrees?|access|acces|portes?"
    r"|cameras?|smart ?homes?|domotique|alarms?(?! clocks?\b)|alarmes?|codes?|serrures?|garages?"
    r"|locks?|lockbox(?:es)?|locksmiths?|buzzers?|nest|surveillance|domiciles?"
    r"|logements?|residences?|foyers?|cottages?|chalets?|chez (?:moi|nous|soi|lui|elle)"
    r"|(?:my|our|his|the) (?:place|flat)"
    # round 9 (G10): the gate, the basement, his dwelling
    r"|gates?|portails?|basements?|sous ?sols?|demeures?)\b"
    r"|\b(?:home|house|maison)[a-z]{3,}")
_HOME_GOODS = re.compile(r"\bsuppl(?:y|ies)$")
_HOME_WHY = "his home itself: who comes in, its keys, doors and security"
# the words the fold may read back from look-alike letters and digits
_NEVER_WORDS = frozenset(w for rx, _ in _NEVER for w in re.findall(r"[a-z]{3,}", rx.pattern)) \
    | frozenset(re.findall(r"[a-z]{3,}", _HOME_ITSELF.pattern))
# Inside a description: never a 'never' (R10, round 6). The words of a
# description are an engine's, and reading them for 'never' refused ordinary
# errands as 'letting anyone into the house … it may be a scam' ('Let me
# know in an hour', 'Let it sit in the fridge'). What a description names
# that only the owner decides — moving money, gift cards, crypto, phoning
# as him — is 'ask the owner first': not allowed for the engine, said
# plainly, with no accusation.
_ASK_IN_TEXT = (
    (re.compile(r"\b(?:e-?\s?transfer\w*|wire\s+(?:transfer|\$|money|funds|it|the)\w*"
                r"|by\s+wire\b|interac|western\s?union|money\s?gram|money\s?order"
                r"|(?:bank|money|wire|fund)\s+transfers?\b"
                r"|transfer\s+(?:the\s+)?(?:money|funds|cash|\$|\d)|confirm\s+the\s+transfer"
                r"|pay\s?pal|venmo|zelle"
                r"|send(?:ing)?\s+(?:\w+\s+){0,3}(?:money|cash|funds)\b)"),
     "moving money from one account to another"),
    (re.compile(r"\b(?:gift[\s-]?cards?|google\s?play\s+cards?|itunes\s+cards?|apple\s+itunes"
                r"|steam\s+cards?|prepaid\s+(?:visa|cards?))\b"), "buying gift cards"),
    (re.compile(r"\b(?:bitcoin|crypto\w*|btc|ethereum|usdt|usdc|tether|stablecoins?)\b"),
     "crypto-currency"),
    (re.compile(r"\b(?:phone\s?call|place\s+a\s+call|in\s+(?:my|his|her)\s+voice"
                r"|call\s+(?:him|her|them|back|the\s+(?:bank|police|number|office)"
                r"|[a-z]+\s+and\s+(?:tell|say|ask))"
                r"|ring\s+(?:him|her|them|the\s+(?:bank|police|office)|up|back)"
                r"|phone\s+(?:him|her|them|the\s+(?:bank|police|office)|back|up))"),
     "speaking for the owner on the phone or in his voice"),
)

# --- what was done, beside what was approved (S8, round 8 repair) ------------
# A line of the action log is in the past tense; an approval is not. These
# are read as the same word, so 'Fed the cat at 6' is what 'Feed the cat at 6'
# approved (the regular ones, 'watered', 'phoned', are read alike: _act_stem).
_PAST = {"fed": "feed", "ate": "eat", "gave": "give", "given": "give", "told": "tell",
         "sent": "send", "bought": "buy", "brought": "bring", "took": "take",
         "taken": "take", "made": "make", "paid": "pay", "got": "get", "gotten": "get",
         "went": "go", "gone": "go", "left": "leave", "kept": "keep", "met": "meet",
         "ran": "run", "rang": "ring", "rung": "ring", "said": "say", "sold": "sell",
         "wrote": "write", "written": "write", "drove": "drive", "driven": "drive",
         "came": "come", "saw": "see", "seen": "see", "found": "find", "did": "do",
         "done": "do", "had": "have", "put": "put", "set": "set", "read": "read",
         "picked": "pick", "dropped": "drop", "swept": "sweep", "hung": "hang",
         "fetched": "fetch", "booked": "book", "called": "call", "cut": "cut",
         "spent": "spend", "shut": "shut", "won": "win", "lost": "lose"}


# Only grammar is set aside: articles, pronouns, prepositions. The words of a
# message or an act ('sent', 'told', 'letter', 'everything') count, though
# grounding's own STOP list leaves them out when it grounds a topic —
# 'Fed the cat at 6 and sent a letter' says more than 'Feed the cat at 6'.
_ACT_KEEP = frozenset("""send sends sending sent ask asks asking asked tell tells telling told
    say says saying said help helps helping get gets got getting make makes made let lets
    write writes writing written wrote letter letters email emails message messages reply
    replies draft drafts note notes need needs want wants like likes everything something
    anything nothing someone anyone everyone thing things please""".split())
_ACT_GRAMMAR = grounding.STOP - _ACT_KEEP


def _act_words(text: str) -> dict[str, str]:
    """The words of an act that mean something, one form for each tense
    (and the word as written); numbers and times aside (an amount is read
    on its own)."""
    out: dict[str, str] = {}
    for w in re.findall(r"[a-z]+", grounding.fold(str(text or "")).lower()):
        if w in _ACT_GRAMMAR or len(w) < 2:
            continue
        out.setdefault(_act_stem(w), w)
    return out


def _act_stem(w: str) -> str:
    """One form for 'phone', 'phoned', 'fix', 'fixed', 'tidy', 'tidied':
    the same on both sides is all that matters here."""
    w = _PAST.get(w, w)
    if w.endswith("ied") and len(w) > 4:
        w = w[:-3] + "y"
    s = grounding.stem(w)
    if s.endswith("ed") and len(s) > 3:
        s = s[:-1]                      # 'used' is 'use', 'phoned' is 'phone'
    if s.endswith("e") and len(s) > 2:
        s = s[:-1]
    return s


# Words that only say the approved thing was carried out ('Ordered the weekly
# shop', 'Placed the order', 'Done') — never an object of their own: what
# they did it TO must still be a word of the approval.
_CARRIED_OUT = frozenset(_act_words("order orders ordered place placed complete completed "
                                    "finish finished handle handled arrange arranged"))


def _beyond_approval(done: str, approved: str, approved_amount=None) -> list[str]:
    """What an act written down says beyond what was approved: its words that
    are not words of the approval, and an amount larger than any the
    approval named."""
    have = set(_act_words(approved)) | _CARRIED_OUT
    extra = [w for k, w in _act_words(done).items() if k not in have]
    amounts = lambda t: [float((a or b).replace(",", "")) for a, b in  # noqa: E731
                         _AMOUNT_IN_TEXT.findall(str(t).lower())
                         if (a or b).replace(",", "").replace(".", "", 1).isdigit()]
    said, allowed = amounts(done), amounts(approved)
    if _real_number(approved_amount) is not None:
        allowed.append(_real_number(approved_amount))
    if said and max(said) > (max(allowed) if allowed else 0.0) + 0.005:
        extra.append(f"${max(said):,.2f}")
    return extra


# --- getting into the home asks the owner (D4, round 7) ----------------------
# Rounds 4 to 6 read a description for WHO was being let in — a person, a
# pet, the air — and each round the skeptics found the neighbours of the
# cases it fixed: 'let him in to fix the furnace', 'Laisse rentrer le
# voisin', 'Turn off the alarm', 'Tell the cleaner the door code', 'Send
# the plumber up'. Nothing is read for meaning any more. A description that
# touches the way into his home or its security — under ANY category, at any
# level — asks the owner first: not allowed for the engine, verdict
# 'ask_owner', in plain words, with no accusation. It asks more often than it
# must ('Let the cat in' asks: it is his door), and that is the decision.
# Only the words are read, in English and French, in any form, with
# look-alike letters (Cyrillic, Greek, digits for letters, spaced-out
# letters) read as the letters they look like:
#   * a word of the door itself, any form: door, porte, gate, portail,
#     garage, key, clé, lock, unlock, serrure, alarm, alarme, code,
#     digicode, intercom, interphone, buzz, entry, entrée, access, accès,
#     enter, entrer, rentrer, monter, ouvrir, accueillir, admit, disarm;
#   * a verb that lets in, with a word that says in: let / allow / laisser
#     … in, into, inside, indoors, onto, upstairs, à l'intérieur, dedans,
#     up, through, past, passer; show / welcome / invite / usher / bring /
#     send / wave / have / ask … in, inside, up, through, over; come /
#     step / walk / pop / drop / move … in, inside, over, by, up;
#   * open up, open … the window, leave / keep / prop … open or ajar;
#   * disable, deactivate, unplug, bypass, turn / switch / shut / cut …
#     off … the alarm, the camera, the security, a sensor;
#   * someone staying the night, and showing the house.
# A category that is itself a door, a lock or an alarm stays 'never' above.
_ENTRY_FOLD = {
    **dict.fromkeys(map(ord, "‘’‚‛′ʼ`´"), "'"),
    **dict.fromkeys(map(ord, "‐‑‒–—―−﹘﹣－"),
                    "-"),
    ord("ł"): "l", ord("đ"): "d", ord("ø"): "o", ord("ß"): "ss", ord("æ"): "ae",
    ord("œ"): "oe", ord("ı"): "i",
    **{ord(a): b for a, b in zip("АВЕКМНОРСТХУІЈЅаеорсухіјѕԁһӏԛԝвкмнтү",
                                 "ABEKMHOPCTXYIJSaeopcyxijsdhlqwbkmhty")},
    **{ord(a): b for a, b in zip("ΑΒΕΖΗΙΚΜΝΟΡΤΥΧαβεικνορτυχγ",
                                 "ABEZHIKMNOPTYXabeikvoptuxy")},
}
_ENTRY_LEET = (str.maketrans("013457@$8", "oleastasb"), str.maketrans("013457@$8", "oieastasb"))


def _wordset(*groups: str) -> frozenset:
    out: set[str] = set()
    for g in groups:
        out.update(g.split())
    return frozenset(out)


# words that are themselves about the door (accents already off: clé is cle)
_ENTRY_WORDS = _wordset(
    "door doors doorbell doorbells doorway doorways doorstep doorsteps doorknob doorknobs",
    "doorman doormen doormat frontdoor backdoor sidedoor doorcode",
    "porte portes portail portails sonnette sonnettes",
    "gate gates gated gatecode garage garages",
    "key keys keyed keyless keypad keypads keycard keycards keyfob keyfobs keybox keysafe",
    "housekey housekeys fob fobs cle cles clef clefs",
    "lock locks locked locking lockbox lockboxes lockout unlock unlocks unlocked unlocking",
    "relock padlock padlocks deadbolt deadbolts smartlock locksmith locksmiths",
    "serrure serrures verrou verrous verrouille verrouiller verrouillez verrouillee",
    "deverrouille deverrouiller deverrouillez deverrouillee cadenas",
    "alarm alarms alarmed alarme alarmes disarm disarms disarmed disarming",
    "desarme desarmer desarmez desarmee",
    "code codes passcode passcodes digicode digicodes keycode keycodes",
    "intercom intercoms interphone interphones buzz buzzes buzzed buzzing buzzer buzzers",
    "entry entries entrance entrances entree entrees",
    "access accesses accessed accessing acces acceder accedez",
    "enter enters entered entering reenter",
    "entrer entrez entrons entrent entrera entrerai entreront entrait",
    "rentrer rentre rentrez rentrons rentrent rentrera rentrerai",
    "monter monte montez montons montent montera monterai",
    "ouvrir ouvre ouvres ouvrez ouvrons ouvrent ouvrira ouvrirai ouvrirez ouvert ouverte",
    "ouverts ouvertes ouverture",
    "accueille accueilles accueillir accueillez accueillons accueillent accueilli accueillie",
    "admit admits admitted admitting",
    # round 8 (F6): the latch and the bolt, Quebec French débarrer, the
    # security system's own words, French héberger and the imperative 'entre'
    "latch latches latched latching unlatch unlatches unlatched unlatching",
    "bolt bolts bolted bolting unbolt unbolts unbolted unbolting",
    "debarre debarrer debarrez debarres debarrons debarrent debarrera",
    "camera cameras cam cams footage detector detectors detecteur detecteurs",
    "heberge heberger hebergez heberges hebergeons hebergent hebergera",
    "entre",
    # round 9 (G10): the snib; the door, the key, open and come in, in Spanish
    # and Italian, at the least
    "snib snibs snibbed unchain unchains unchained unchaining",
    "puerta puertas porta portone entrar entra llave llaves chiave chiavi",
    "abre abrir abra apri aprire apra",
)
# 'alarm clock' rings in the morning; an 'unlocked iPhone' is a phone; 'Door
# Dash' brings dinner — the one word beside them says so, and nothing else
_NOT_THE_DOOR = {"alarm": frozenset({"clock", "clocks"}), "alarms": frozenset({"clock",
                                                                                "clocks"}),
                 "bolt": frozenset({"of"}),
                 "unlocked": frozenset({"iphone", "phone", "cellphone", "smartphone", "android",
                                        "pixel", "galaxy", "samsung", "cell", "mobile"}),
                 "door": frozenset({"dash"})}
_LET = _wordset("let lets letting allow allows allowed allowing",
                "laisse laisser laissez laisses laissons laissent laissera laisserai laissait",
                "fais faire faites fait faisons")
_LET_IN_FAR = _wordset("in into inside indoors onto upstairs interieur dedans")
_LET_IN_NEAR = _wordset("up through thru past passer")
_BRING = _wordset("show shows showed showing welcome welcomes welcomed welcoming",
                  "invite invites invited inviting usher ushers ushered ushering",
                  "bring brings brought bringing send sends sent sending wave waves waved",
                  "waving")
_BRING_IN = _wordset("in into inside indoors upstairs up through over interieur dedans")
_HAVE = _wordset("have has had having ask asks asked asking",        # 'have the kids over'
                 "get gets got getting")
_HAVE_IN = _wordset("in inside round around over up")              # (F6, round 8)
_COME = _wordset("come comes came coming step steps stepped walk walks walked",
                 "move moves moved moving")
_COME_IN = _wordset("in inside indoors into over by up upstairs round around")
_POP = _wordset("pop pops popped drop drops dropped stop stops")
_POP_IN = _wordset("in by over round around")
# 'open' asks unless, within three words, it opens something that is not a
# way in (F6, round 8: 'Open the front for the plumber' was allowed)
_OPENS_ELSE = _wordset("account accounts app apps application applications file files",
                       "email emails mail link links letter letters parcel parcels",
                       "package packages box boxes jar jars tab tabs browser browsers",
                       "document documents attachment attachments pdf pdfs statement",
                       "statements bottle bottles can cans envelope envelopes")
_SPARE = _wordset("spare spares")
_NOT_A_SPARE_KEY = _wordset("tire tires tyre tyres wheel change time room rooms bedroom bed",
                            "beds parts part battery batteries bulb bulbs cash money ribs",
                            "moment minute minutes cent cents dime pair blanket sheets towel",
                            "towels")
_STAY_WHEN = _wordset("night nights overnight tonight weekend weekends couch sofa",
                      "week nuit nuits soir semaine canape")
_PUT = _wordset("put puts putting")
_BATHROOM = _wordset("bathroom bathrooms washroom washrooms toilet toilets restroom loo",
                     "lavatory toilettes toilette wc")
_USE = _wordset("use uses used using")
_LOOK = _wordset("look looks looked looking")
_AROUND = _wordset("around round through")
_TOUR = _wordset("tour tours toured touring")
_OPEN = _wordset("open opens opened opening")
_LEAVE = _wordset("leave leaves leaving left keep keeps kept prop props propped")
_LEFT_OPEN = _wordset("open unlocked ajar")
_WINDOW = _wordset("window windows fenetre fenetres")
_DISABLE = _wordset("disable disables disabled disabling deactivate deactivates deactivated",
                    "unplug unplugs unplugged disconnect disconnects disconnected bypass",
                    "bypasses override overrides desactive desactiver desactivez debranche",
                    "debrancher debranchez eteins eteindre eteignez coupe couper coupez")
_OFF_VERB = _wordset("turn turns turned turning switch switches switched switching shut",
                     "shuts cut cuts power powers")
_SECURITY = _wordset("alarm alarms alarme alarmes camera cameras security surveillance",
                     "sensor sensors detecteur detecteurs monitoring")
_STAY = _wordset("stay stays stayed staying sleep sleeps slept sleeping crash dormir dort",
                 "dorment coucher couche")
_NIGHT = _wordset("night nights overnight over here nuit ici")
_SPEND = _wordset("spend spends spent spending passer passe passez")
_SHOW = _wordset("show shows showed showing visit visits visiter visite")
_HOUSE = _wordset("house home condo apartment place property unit maison appartement")
# --- round 9 (G10): the door, in the words the round-8 skeptics used --------
# telling, giving, texting, sending or reading anyone a PIN, a code, a
# combination, a password or a key
_TELL = _wordset("tell tells told telling give gives gave giving text texts texted texting",
                 "send sends sent sending read reads reading share shares shared sharing",
                 "email emails emailed message messages messaged say says said whatsapp",
                 "dis dire dites donne donner donnez donnes envoie envoyer envoyez texte texter")
_SECRET_THING = _wordset("pin pins nip combination combinations combinaison combinaisons combo",
                         "combos password passwords passcode passcodes mdp")
# the ways in a door is named by ('the front', 'the side', 'the slider')
_WAY_IN = _wordset("front back side main patio slider sliding screen porch basement cellar",
                   "door doors gate gates garage entrance window windows yale")
# escorting, walking, taking or showing someone through the house
_ESCORT = _wordset("escort escorts escorted escorting walk walks walked walking take takes",
                   "took taking taken show shows showed showing guide guides guided lead",
                   "leads led bring brings brought accompany accompanies accompanied")
_THROUGH = _wordset("through thru to into up down around round")
_ROOMS = _wordset("house home basement cellar attic upstairs downstairs bedroom bedrooms",
                  "room rooms kitchen hallway hall office study den garage loft")
_AT_DOOR = _wordset("front door doors gate porch doorstep step stoop intercom buzzer")
# pressing, hitting or dialing a digit for a caller
_PRESS = _wordset("press presses pressed pressing hit hits hitting dial dials dialed dialing",
                  "push pushes pushed punch punches punched")
_DIGIT_NAMES = _wordset("star pound hash zero one two three four five six seven eight nine")
_FOR_WHEN = _wordset("for when whenever if once")
# holding, propping or answering the front, the back, the side, a door or 'it'
_HOLD = _wordset("hold holds held holding prop props propped propping answer answers",
                 "answered answering")
# the chain; ringing someone in; accepting something inside; a guest list
_CHAIN_OFF = _wordset("take takes took taking undo undoes undid remove removes removed slip")
_RING = _wordset("ring rings rang ringing")
_ACCEPT = _wordset("accept accepts accepted accepting")
_INDOORS = _wordset("inside indoors into")
_BUILDING = _wordset("building buildings condo lobby concierge desk apartment tower residence",
                     "security doorman")
# telling anyone the house will be empty, or that he is away
_SAY = _wordset("tell tells told telling text texts texted email emails message messages",
                "inform informs informed say says said post posts mention mentions know")
_BE = _wordset("am is are be m re s was were been being")
_EMPTY = _wordset("empty vacant")
# a smart lock or a camera by its name, with open, unlock, disarm, pause or off
_BRANDS = _wordset("yale august smartthings schlage kwikset ring nest arlo eufy simplisafe adt",
                   "alarmcom")
_BRAND_VERB = _wordset("open opens opened opening unlock unlocks unlocked unlocking disarm",
                       "disarms disarmed disarming pause pauses paused pausing off snooze")
# French: receiving someone ('Reçois le plombier'), giving the spare ('le double')
_RECEVOIR = _wordset("recois recoit recevoir recevez recevons recoivent recevra recevrai")
_RECEIVED_THINGS = _wordset("colis paquet paquets lettre lettres courrier facture factures",
                            "appel appels message messages courriel courriels email emails",
                            "cheque cheques remboursement commande commandes livraison",
                            "livraisons nouvelles resultats")
_GIVE_FR = _wordset("donne donner donnez donnes laisse laisser laissez prete preter pretez",
                    "passe passer remets remettre confie confier")
_KNOWN = (_ENTRY_WORDS | _LET | _LET_IN_FAR | _LET_IN_NEAR | _BRING | _BRING_IN | _COME
          | _COME_IN | _POP | _OPEN | _LEAVE | _LEFT_OPEN | _WINDOW | _DISABLE | _OFF_VERB
          | _SECURITY | _STAY | _NIGHT | _SHOW | _HOUSE | _HAVE | _HAVE_IN | _SPARE | _STAY_WHEN
          | _PUT | _BATHROOM | _USE | _LOOK | _AROUND | _TOUR
          | _TELL | _SECRET_THING | _WAY_IN | _ESCORT | _THROUGH | _ROOMS | _AT_DOOR | _PRESS
          | _DIGIT_NAMES | _HOLD | _CHAIN_OFF | _RING | _ACCEPT | _INDOORS | _BUILDING | _SAY
          | _EMPTY | _BRANDS | _BRAND_VERB | _RECEVOIR | _GIVE_FR
          | frozenset("him her them me man in let ring yes chain run guest list mode recording "
                      "away double".split()))


def _entry_words_of(description: str) -> list[str]:
    """The words of a description in one spelling, read through the shared
    fold (grounding.fold, round 8): look-alike letters read as Latin
    (Cyrillic, Greek, Armenian, Cherokee, small capitals), accents off, lower
    case; digits or symbols written for letters ('d00r', 'a1arm', '1n', '|et'),
    a capital I for l ('Iet him in', 'UnIock'), a split word ('le t him in')
    and spaced-out letters ('u n l o c k', 'd.o.o.r') read back as the word
    they spell."""
    t = grounding.fold(str(description or ""), _KNOWN | grounding.FOLD_WORDS)
    t = t.translate(_ENTRY_FOLD)
    words: list[str] = []
    tight: list[bool] = []          # only one space or dot before this word
    end = 0
    for m in re.finditer(r"[a-z0-9@$]+", t):
        w = m.group()
        if any(c.isalpha() for c in w) and any(c.isdigit() or c in "@$" for c in w):
            v0, v1 = w.translate(_ENTRY_LEET[0]), w.translate(_ENTRY_LEET[1])
            w = v1 if v1 in _KNOWN and v0 not in _KNOWN else v0
        words.append(w.strip("@$") or w)
        tight.append(len(t[end:m.start()]) <= 1)
        end = m.end()
    runs: list[tuple[int, int]] = []
    i = 0
    while i < len(words):
        j = i + 1
        if len(words[i]) == 1 and words[i].isalpha():
            while (j < len(words) and len(words[j]) == 1 and words[j].isalpha()
                   and tight[j]):
                j += 1
        runs.append((i, j))
        i = j
    # 'u n l o c k', 'd.o.o.r'; once a description spells out words letter by
    # letter, a two-letter run is a word too ('L E T  H I M  I N')
    least = 2 if any(j - i >= 3 for i, j in runs) else 3
    out: list[str] = []
    for i, j in runs:
        if j - i >= least:
            out.append("".join(words[i:j]))
        else:
            out.extend(words[i:j])
    return out


def _the_door_g10(w: list[str], i: int, ahead) -> int | None:
    """Round 9 (G10): the descriptions the round-8 skeptics found allowed
    under any category, read as words, each asking the owner. Where the word
    that makes it the door stands, or None."""
    n, x = len(w), w[i]
    nxt = w[i + 1] if i + 1 < n else ""
    if x in _TELL:
        k = ahead(i, _SECRET_THING, 6)               # 'Tell the cleaner the PIN'
        if k is not None:
            return k
        for k in range(i + 1, min(n, i + 7)):         # 'Text the cleaner 4821 for the side'
            if w[k].isdigit() and 3 <= len(w[k]) <= 8 and any(y in _WAY_IN for y in w):
                return k
    if x == "run" and nxt == "of" and ahead(i, _ROOMS | _HOUSE, 3) is not None:
        return ahead(i, _ROOMS | _HOUSE, 3)           # 'the run of the house'
    if x in _ESCORT:                                  # 'Escort the gentleman to the basement'
        k = ahead(i, frozenset({"upstairs", "downstairs"}), 6)
        if k is not None:
            return k
        k = ahead(i, _THROUGH, 6)
        if k is not None and ahead(k, _ROOMS, 3) is not None:
            return ahead(k, _ROOMS, 3)
    if x == "yes" and any(y in _AT_DOOR for y in w):  # 'Say yes to the man at the front'
        return next(k for k in range(n) if w[k] in _AT_DOOR)
    if x in ("home", "away") and nxt == "mode":       # 'Set the Nest to home mode'
        return i + 1
    if x in ("stop", "stops", "stopped", "stopping") and nxt == "recording":
        return i + 1
    if x in _PRESS and (nxt.isdigit() and len(nxt) <= 2 or nxt in _DIGIT_NAMES) \
            and ahead(i + 1, _FOR_WHEN, 3) is not None:
        return i + 1                                  # 'Press 9 for the courier'
    if x in _HOLD:                                    # 'Hold the front for the plumber'
        for k in range(i + 1, min(n, i + 4)):
            if w[k] in _WAY_IN:
                return k
            if w[k] in ("it", "one") and ahead(k, frozenset({"for"}), 3) is not None:
                return k
    if x == "chain" and (ahead(i, frozenset({"off"}), 2) is not None
                         or any(w[k] in _CHAIN_OFF for k in range(max(0, i - 3), i))):
        return i                                      # 'Take the chain off'
    if x in _RING:                                    # 'Ring the man from the bank in'
        k = ahead(i, frozenset({"in"}), 7)
        if k is not None and (k == n - 1 or w[k + 1] in ("now", "please", "for", "so", "and",
                                                         "when", "then")):
            return k
    if x in _ACCEPT:                                  # 'Accept the delivery inside the house'
        k = ahead(i, _INDOORS, 6)
        if k is not None:
            return k
        k = ahead(i, frozenset({"in"}), 6)
        if k is not None and ahead(k, _ROOMS, 2) is not None:
            return k
    if x == "guest" and nxt == "list" and any(y in _BUILDING for y in w):
        return i + 1                                  # "the building's guest list"
    if x in _SAY:                                     # 'Tell him the house is empty'
        for k in range(i + 1, min(n, i + 12)):
            if w[k] in _EMPTY and any(w[j] in _HOUSE | _ROOMS for j in range(max(i, k - 3), k)):
                return k
            if w[k] == "away" and k and w[k - 1] in _BE:
                return k
            if w[k] in ("nobody", "noone") and k + 1 < n and w[k + 1] == "home":
                return k
    if x in _BRANDS:                                  # 'Open the Yale app for the plumber'
        for k in range(max(0, i - 4), min(n, i + 5)):
            if w[k] in _BRAND_VERB:
                return k
    if x in _RECEVOIR and ahead(i, _RECEIVED_THINGS, 3) is None:
        return i                                      # 'Reçois le plombier'
    if x in _GIVE_FR and ahead(i, frozenset({"double", "doubles"}), 3) is not None:
        return ahead(i, frozenset({"double", "doubles"}), 3)   # 'Donne le double au voisin'
    return None


def entry_words(description: str) -> str | None:
    """The words of a description that touch getting into the home or its
    security, or None (D4, round 7). Read by the words alone — never by who
    or what is let in. A description that holds a character that shows as
    nothing is read both ways — with it as nothing, and as a space (round 9
    repair, G5: 'Let the plumber i\\u2800n' and 'Unlock\\u200bthe\\u200bfront\\u200bdoor'
    were both allowed)."""
    for text in grounding.readings(str(description or "")):
        found = _entry_words_one(text)
        if found:
            return found
    return None


def _entry_words_one(description: str) -> str | None:
    w = _entry_words_of(description)
    n = len(w)
    # the Ring with its capital, as the doorbell camera is written ('Turn off
    # the Ring'); 'Sell the ring' is jewellery
    ring_device = bool(re.search(r"\b(?:the|my|our|his|her|that)\s+Ring\b",
                                 grounding.fold_map(str(description or ""))[0]))
    far: list[int | None] = [None] * (n + 1)          # the next 'in' after each word
    for k in range(n - 1, -1, -1):
        far[k] = k if w[k] in _LET_IN_FAR else far[k + 1]

    def said(i: int, j: int) -> str:
        return " ".join(w[i:j + 1]) if j - i < 8 else f"{w[i]} … {w[j]}"

    def ahead(i: int, words: frozenset, upto: int) -> int | None:
        for k in range(i + 1, min(n, i + 1 + upto)):
            if w[k] in words:
                return k
        return None

    for i, x in enumerate(w):
        nxt = w[i + 1] if i + 1 < n else ""
        prev = w[i - 1] if i else ""
        if x in _ENTRY_WORDS and nxt not in _NOT_THE_DOOR.get(x, ()):
            return x
        # round 8 (F6): the spare (a key), the Ring, the security system,
        # maintenance mode, using the bathroom
        if x in _SPARE and nxt not in _NOT_A_SPARE_KEY:
            return x
        if x == "ring" and (ring_device or nxt in ("camera", "cameras", "doorbell", "cam",
                                                  "cams", "alarm", "device", "system")):
            return "the ring"
        if x == "security" and nxt in ("system", "systems", "panel", "company"):
            return "security " + nxt
        if x == "maintenance" and nxt == "mode":
            return "maintenance mode"
        if x in _BATHROOM and any(w[k] in _USE for k in range(max(0, i - 3), i)):
            return said(max(0, i - 3), i)
        door = _the_door_g10(w, i, ahead)
        if door is not None:
            return said(min(i, door), max(i, door))
        found = None
        if x in _LET:
            found = far[i + 1] if far[i + 1] is not None else ahead(i, _LET_IN_NEAR, 6)
        elif x in _BRING:
            found = ahead(i, _BRING_IN, 6)
        elif x in _HAVE:
            found = ahead(i, _HAVE_IN, 4)
            if found is not None and w[found] == "in" and found + 1 < n \
                    and w[found + 1] in ("touch", "mind"):
                found = None                         # 'get in touch', 'keep in mind'
        elif x in _COME:
            found = ahead(i, _COME_IN, 2)
        elif x in _POP:
            found = ahead(i, _POP_IN, 1)
        elif x in _OPEN:
            # 'open' asks when ANY of what it opens is a way in — a decoy noun
            # first no longer exempts it (G10: 'Open the email and the front
            # for the plumber') — and otherwise unless, within three words, it
            # opens what is no way in
            found = ahead(i, _WAY_IN, 8)
            if found is None and ahead(i, _OPENS_ELSE, 3) is None:
                found = i
        elif x in _PUT:
            if ahead(i, frozenset({"up"}), 4) is not None:
                found = ahead(i, _STAY_WHEN, 8)
        elif x in _LOOK:
            if ahead(i, _AROUND, 1) is not None:
                found = ahead(i, _HOUSE, 4)
        elif x in _TOUR:
            found = ahead(i, _HOUSE, 4)
        elif x in _LEAVE:
            found = ahead(i, _LEFT_OPEN, 6)
        elif x in _DISABLE:
            found = ahead(i, _SECURITY, 6)
        elif x in _OFF_VERB:
            if ahead(i, frozenset({"off", "down"}), 5) is not None:
                found = ahead(i, _SECURITY, 7)
        if found is None and x in _STAY:
            found = ahead(i, _NIGHT | _STAY_WHEN, 3)
            if found is None and x in ("dormir", "dort", "dorment", "coucher", "couche"):
                found = ahead(i, frozenset({"chez", "ici"}), 1)
        if found is None and x in _SPEND:
            found = ahead(i, frozenset({"night", "nights", "nuit"}), 3)
        if found is None and x in _SHOW:
            found = ahead(i, _HOUSE, 3)
        if found is None and x in ("home", "house") and nxt in ("visit", "visits", "call",
                                                              "calls"):
            found = i + 1
        if found is not None:
            return said(i, found)
        if x in ("sleepover", "sleepovers"):
            return x
    return None


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
    r"/\s?(?:mo|mth|mon|month|yr|year|wk|week)\b|\bper\s+(?:month|year|week|annum)\b"
    r"|(?:[$£€]\s?\d[\d.,]*|\d[\d.,]*\s?(?:\$|dollars?))\s*(?:a\s+|per\s+|/\s*)?"
    r"(?:monthly|weekly|yearly|annually|fortnightly)\b"
    r"|\b(?:billed|charged|paid|renews?|payable)\s+(?:monthly|weekly|yearly|annually"
    r"|fortnightly)\b|\b(?:monthly|weekly|yearly|annually|fortnightly)\s*$"
    r"|\bevery\s+(?:\d+|two|three|four|six)\s+(?:days?|weeks?|months?|years?)\b"
    r"|\b(?:a|each|every)\s+(?:month|year|week)\b|\bsubscri\w*|\bauto-?\s?renew\w*"
    r"|\b(?:monthly|yearly|annual|annually|weekly)\s+(?:plan|fee|payment|charge|bill\w*"
    r"|subscription|membership|contract|instal\w*|donation)"
    r"|\bbilled\s+(?:monthly|yearly|annually|weekly)|\brecurring\b|\bminimum\s+term\b"
    r"|\binstal(?:l)?ments?\b"
    r"|\b\d+[- ]?(?:month|year)s?\s+(?:minimum|contract|term|commitment)")
_CURRENCY_TEXT = (("GBP", re.compile(r"£|\bgbp\b|\bpounds?\s+sterling\b|\bquid\b"
                                     r"|\b\d+(?:\.\d+)?\s*pounds?\b(?!\s+(?:of|weight|bag))")),
                  ("AUD", re.compile(r"\ba\$|\baud\b|\baustralian\s+dollars?\b")),
                  ("NZD", re.compile(r"\bnz\$|\bnzd\b")),
                  ("EUR", re.compile(r"€|\beur\b|\beuros?\b")),
                  ("USD", re.compile(r"\bus\s?\$|\busd\b|\bu\.s\.\s?dollars?\b"
                                     r"|\bamerican\s+dollars?\b")),
                  ("JPY", re.compile(r"¥|\bjpy\b|\byen\b")),
                  ("CAD", re.compile(r"\bcad\b|\bc\$|\bcanadian\s+dollars?\b")))
_MONEY_TEXT = re.compile(r"[$£€¥]\s?\d|\d\s?(?:\$|dollars?\b|bucks\b|cad\b|usd\b|eur\b|gbp\b)"
                         r"|\b(?:dollars?|bucks|cash|money|payment|deposit|cheque|check\s+for)\b")
# Amounts written in a description, to compare with the amount given.
_AMOUNT_IN_TEXT = re.compile(r"[$£€¥]\s?(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s?"
                             r"(?:\$|dollars?\b|bucks\b|cad\b|usd\b)")
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
                 "conscience_included": "in",
                 # what an AI asked to change in his rules and his profile, waiting
                 # for his own yes (S1, S2 — round 8)
                 "rule_proposals": "rp", "profile_notes": "pf"}

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
        self._stat: tuple[int, int, int, int] | None = None
        # sha256 of the bytes this process last read from or wrote to disk:
        # how a change made anywhere else — another engine, a hand edit — is
        # recognised, whatever its revision number says.
        self._disk_sha: str | None = None
        # Those contents as JEFFEREY writes them: the point a failed save
        # rolls back to, and the yardstick for "did anything change?".
        self._clean: bytes = self._snap(self.data)
        self._unavailable: ConscienceCorrupt | None = None
        self._runtime_notices: dict[str, str] = {}
        # sha256 of a damaged file that recovery could not set aside yet:
        # nothing is saved over it until it is (I-50).
        self._unkept: str | None = None
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
        self._clean = self._snap(self.data)
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
    def _key(st: os.stat_result) -> tuple[int, int, int, int]:
        # The change time too: an editor that writes in place and puts the
        # old modification time back (same inode, same size) still changes
        # it, and nothing can set it back (I-19).
        return (st.st_ino, st.st_mtime_ns, st.st_size, st.st_ctime_ns)

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

    @staticmethod
    def _decode(raw: bytes) -> tuple[str | None, str | None]:
        """(text, how) for a file some editor saved in another text format:
        with a byte-order mark, or as UTF-16 or UTF-32. JEFFEREY only ever
        writes UTF-8 without a mark, so such a file is always an edit by hand
        — never a power-cut tear to recover over (I-19: an owner's edit
        saved as UTF-16 was taken for a tear, and the fact he had deleted
        came back). (None, None) for an ordinary file."""
        boms = ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
                (codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"),
                (codecs.BOM_UTF16_BE, "utf-16"))
        for bom, enc in boms:
            if raw.startswith(bom):
                try:
                    return raw.decode(enc), enc
                except UnicodeDecodeError:
                    return None, enc
        # UTF-16 or UTF-32 without a mark: the file starts with '{' (or a
        # space) written that way, every letter of the first line padded
        # with NULs in the same places. A power cut leaves runs of NULs,
        # never that pattern.
        head = raw[:64]
        for enc, width, at in (("utf-32-le", 4, 0), ("utf-32-be", 4, 3),
                               ("utf-16-le", 2, 0), ("utf-16-be", 2, 1)):
            if len(raw) % width or len(head) < width * 2:
                continue
            units = [head[i:i + width] for i in range(0, len(head) - width + 1, width)]
            if units[0][at:at + 1] not in (b"{", b" ", b"\t", b"\r", b"\n"):
                continue
            if all(u[:at] + u[at + 1:] == b"\0" * (width - 1) for u in units
                   if u[at:at + 1].isascii() and u[at:at + 1] != b"\0"):
                if sum(1 for u in units if u[at:at + 1] != b"\0") < len(units) // 2:
                    continue
                try:
                    return raw.decode(enc), enc
                except UnicodeDecodeError:
                    return None, enc
        return None, None

    # Python's own words for a mistake in the file, as an owner would say it.
    _JSON_WORDS = (
        ("Expecting property name enclosed in double quotes",
         "a name in double quotes was expected (often a comma is left after "
         "the last item before a closing bracket)"),
        ("Expecting ',' delimiter", "a comma is missing between two items"),
        ("Expecting ':' delimiter", "a colon ( : ) is missing after a name"),
        ("Expecting value", "something is missing there, or there is one comma "
                            "too many"),
        ("Extra data", "there is something more after the end of the memories"),
        ("Invalid control character", "a line break or tab is inside quotes"),
        ("Invalid \\escape", "a backslash ( \\ ) needs to be written twice"),
        ("Invalid \\uXXXX escape", "a backslash ( \\ ) needs to be written twice"),
        ("Unterminated string", "a quote mark is opened and never closed"),
    )

    @classmethod
    def _json_words(cls, msg: str) -> str:
        for start, plain in cls._JSON_WORDS:
            if msg.startswith(start):
                return plain
        return "something there is not written the way JEFFEREY expects"

    @classmethod
    def _parse(cls, raw: bytes) -> dict:
        """Bytes → a validated store, or _Unreadable saying why in plain words.
        The bytes are decoded INSIDE this check: a file cut in the middle of
        'ó' (Czakó, Montréal) is a torn file to recover, not a crash."""
        if not raw.strip():
            raise _Unreadable("the file is empty", torn=True, certain=True)
        text, enc = cls._decode(raw)
        if enc is not None:
            # Saved by an editor in another format: the owner's edit, never a
            # tear. Read it if it can be read; otherwise say what to fix.
            if text is None:
                raise _Unreadable("it was saved in a text format JEFFEREY cannot "
                                  "read. Save it again as plain text (UTF-8)")
            return cls._parse_text(text, hand=True)
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
        return cls._parse_text(text)

    @classmethod
    def _parse_text(cls, text: str, hand: bool = False) -> dict:
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            if not hand and (e.msg.startswith("Unterminated string")
                             or e.pos >= len(text.rstrip())):
                raise _Unreadable("it stops part-way through, the way a power "
                                  "cut can leave a file", torn=True) from None
            raise _Unreadable(f"there is a mistake on line {e.lineno}, near "
                              f"character {e.colno}: {cls._json_words(e.msg)}") from None
        try:
            return cls._validate(obj)
        except ValueError as e:
            raise _Unreadable(str(e)) from None

    @staticmethod
    def _rev_of(obj: dict) -> int:
        r = obj.get("_rev", 0)
        return r if isinstance(r, int) and not isinstance(r, bool) else 0

    @classmethod
    def _body(cls, data: dict) -> dict:
        """What is written. Empty sections that other modules create on
        start-up are left out, so starting never makes a file look changed."""
        return {k: v for k, v in data.items()
                if k in cls._CORE or not (isinstance(v, (list, dict)) and not v)}

    @classmethod
    def _snap(cls, data: dict) -> bytes:
        """The same contents, compact: what "has anything changed?" and a
        rolled-back save compare against. Six times quicker to make than the
        file itself (scale-01: every load and every save made the indented
        file twice, which took seconds on a long life)."""
        return json.dumps(cls._body(data), ensure_ascii=True,
                          separators=(",", ":")).encode("ascii")

    @classmethod
    def _canon(cls, data: dict) -> bytes:
        """The store exactly as JEFFEREY writes it (indented, so the owner
        can read and edit it)."""
        body = cls._body(data)
        try:
            return json.dumps(body, indent=2, ensure_ascii=False).encode("utf-8")
        except UnicodeEncodeError:
            # Half of an emoji (a lone surrogate) cannot be written as UTF-8.
            # Escaped, it round-trips exactly and poisons nothing.
            return json.dumps(body, indent=2).encode("ascii")

    # ------------------------------------------------- memory ⇄ disk, safely
    def _replace_data(self, obj: dict, owned: bool = False) -> None:
        """Make memory hold `obj`. Sections another module created in memory
        (people, rules, grants…) that `obj` lacks must still exist, empty, or
        the next call into that module fails on a missing key. `owned`: the
        caller parsed `obj` for this alone and will not look at it again."""
        sections = {k: type(v)() for k, v in self.data.items()
                    if isinstance(v, (list, dict))}
        # A copy all the way down: ids are added below, and a parsed file
        # the caller still holds must stay exactly what is on disk.
        new = obj if owned else copy.deepcopy(obj)
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
            selfcloud.migrate_grants(self.data, removed=self._scope_removed_before)
        except Exception:
            pass
        self._migrate_who_said_what()
        self._migrate_album_photos()

    def _migrate_album_photos(self) -> None:
        """An older album pinned each story's photographs inside the memory
        itself — a list of fingerprints, read out by who_am_i and tell_story
        (I-15). They belong with the album's record of that moment, where
        reminisce.py keeps them. That move used to wait for an album tool to
        run with the photo index plugged in (verify I-15: without the index,
        it never happened); now it happens as the memory file is read.
        Nothing is lost: the fingerprints stay with the moment, the memory
        keeps the moment's id. A memory with photographs but no moment is
        left as it is (it goes out as a count)."""
        mems = [m for m in self.data.get("memories") or []
                if isinstance(m, dict) and isinstance(m.get("photos"), list)]
        if not mems:
            return
        album = self.data.get("album")
        if not isinstance(album, dict):
            album = self.data["album"] = {}
        moments = album.get("moments")
        if not isinstance(moments, dict):
            moments = album["moments"] = {}
        for k in ("never_ask", "never_on_the_wall"):
            if not isinstance(album.get(k), list):
                album[k] = []
        told: dict[str, int] = {}
        for mem in self.data.get("memories") or []:
            if isinstance(mem, dict):
                for t in mem.get("tags") or []:
                    if str(t).startswith("moment:"):
                        told[str(t).split(":", 1)[1]] = told.get(str(t).split(":", 1)[1], 0) + 1
        for mem in mems:
            tag = next((str(t) for t in mem.get("tags") or [] if str(t).startswith("moment:")),
                       None)
            if not tag:
                continue
            mid = tag.split(":", 1)[1]
            m = moments.get(mid) if isinstance(moments.get(mid), dict) else {}
            m["shas"] = sorted(set(m.get("shas") or []) | {str(s) for s in mem["photos"]})
            if m.get("status") != "declined":          # 'rather not' stays final
                m["status"] = "told"
            m["stories"] = max(int(m.get("stories") or 0), told.get(mid, 1))
            for k, empty in (("label", ""), ("country", ""), ("places", []), ("from", ""),
                             ("to", "")):
                m.setdefault(k, empty)
            m.setdefault("at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
            moments[mid] = m
            del mem["photos"]

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
            older = not isinstance(p.get("for"), int)
            if older:
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
            self._migrate_legacy_value(p, older)
        for section in ("people", "memories", "media"):
            for it in self.data.get(section) or []:
                if isinstance(it, dict) and it.get("visibility") not in LIFE_VISIBILITY:
                    it["visibility"] = "private"

    def _scope_removed_before(self, client: str, scope: str) -> bool:
        """Did anyone take this scope off this key before? (The access log,
        read only when a migration needs to know.)"""
        try:
            for f in self.access_log.files():
                for e in AppendLog._read(f):
                    if (e.get("client") == client and e.get("action") == "remove_scope"
                            and scope in str(e.get("detail") or "")):
                        return True
        except Exception:
            return True                 # cannot tell: never widen
        return False

    @staticmethod
    def _migrate_legacy_value(p: dict, older: bool) -> None:
        """A value saved before October 2026 keeps the weight it had (verify
        I-48: an owner's old 0.99 fell to 0.5 after one AI correction and
        turned round after two; the old code needed four, and capped values
        it never had). Its old confidence counts like a stated value's —
        four observations — and a value he held at 0.8 or more is locked:
        an AI's contradiction becomes a question for him, never a reversal.
        A store migrated by the first October release (for = evidence,
        against 0, nothing counted since) is recognised and treated the same."""
        if isinstance(p.get("legacy"), dict) or p.get("stated"):
            return
        if provenance.stated_by(p) != provenance.UNKNOWN:
            return
        try:
            ev = max(1, int(p.get("evidence") or 1))
        except (TypeError, ValueError):
            ev = 1
        untouched = older or (int(p.get("against") or 0) == 0 and int(p.get("for") or 0) == ev)
        old = _real_number(p.get("confidence"))
        if old is None or not untouched:
            return
        kept = round(max(0.05, min(0.99, old)), 2)
        p["legacy"] = {"confidence": kept, "evidence": ev, "old_rule": kept}
        p["for"], p["against"] = 0, 0
        p["confidence"] = Conscience._confidence(p)

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

    def _adopt(self, raw: bytes, obj: dict, st: os.stat_result | None = None,
               owned: bool = False) -> None:
        _check_version(obj, self.path)
        self._replace_data(obj, owned=owned)
        self._disk_sha = _sha(raw)
        self._clean = self._snap(self.data)
        if st is not None:
            self._stat = self._key(st)
        else:
            self._mark()

    def _rollback(self) -> None:
        """A save failed: memory goes back to exactly what is on disk, so a
        change the engine was told had failed is never served, and never
        written later by some unrelated save."""
        self._replace_data(json.loads(self._clean.decode("utf-8")), owned=True)

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
        rev = self._rev_of(obj)
        self._adopt(raw, obj, st, owned=True)
        self._ensure_versioned(raw, rev)
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
        never over an earlier one, before anything replaces it. First as a
        second name for the same file (a link), which needs no free space —
        a full drive is exactly when a damaged file turns up, and a copy
        that could not be written once let the next save destroy the only
        place a newer fact was (I-50). Only if that is not possible, a copy."""
        base = f"{self.path.name}.corrupt-{_utc_stamp()}"
        for i in range(1, 1000):
            cand = self.path.with_name(base if i == 1 else f"{base}-{i}")
            try:
                os.link(self.path, cand, follow_symlinks=False)
            except FileExistsError:
                continue
            except (OSError, NotImplementedError):
                break                         # no links here: copy instead
            try:
                if _sha(cand.read_bytes()) == _sha(raw):
                    _sync_dir(cand.parent)
                    return cand
            except OSError:
                pass
            try:                              # the file changed meanwhile
                cand.unlink()
            except OSError:
                pass
            break
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
                # it is NOT written over: work from the copy, in memory only,
                # and every save first tries again to set it aside — no save
                # happens until it is kept (I-50).
                self._disk_sha, self._clean = _sha(raw), self._snap(self.data)
                self._unkept = _sha(raw)
                self._mark()
                self._runtime_notices["recovery"] = (
                    f"Your memory file could not be read ({reason}). JEFFEREY "
                    f"is working from the copy saved {saved}, but could not "
                    "repair the file on the drive, and he will not save "
                    "anything until the damaged file is kept safe. Please free "
                    "some space on the drive.")
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
                self._clean = self._snap(self.data)
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

    def _ensure_versioned(self, raw: bytes, disk_rev: int) -> None:
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
        top_rev = self._snap_rev(top)
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
                    if self._parse(top_raw) == self._parse(raw):
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

    def _set_aside_if_needed(self) -> None:
        """Before a save, under the lock: a damaged file recovery could not
        keep is kept now, or the save does not happen."""
        if self._unkept is None:
            return
        try:
            raw = self.path.read_bytes()
        except OSError:
            raw = None
        if raw is None or _sha(raw) != self._unkept:
            self._unkept = None               # it is gone or changed: nothing to keep
            return
        kept = self._keep_damaged(raw)
        if kept is None:
            raise ConscienceSaveFailed(
                "Your memory file was damaged, and JEFFEREY has not been able to "
                "keep the damaged file safe yet (the drive may be full). So that "
                "nothing in it is lost, nothing was saved. Free some space on the "
                "drive and ask again.", self.path)
        self._unkept = None
        self._runtime_notices.pop("recovery", None)
        self._note("recovered", "Your memory file could not be read earlier. "
                   "JEFFEREY went back to his last copy, and the damaged file is "
                   f"now kept beside it as {kept.name}. Anything said in between "
                   "may be missing, so please check.")

    def _temp_files(self) -> list[Path]:
        """Half-written temporary files a save left behind when it was cut
        off (a crash, a kill, a power cut): '.c.json.XXXX.tmp' beside the
        store and the same in its copies' folders. Each is a whole or partial
        copy of the life, so they must not pile up — nor keep words the owner
        erased (durability-34)."""
        out = []
        for d, prefix in ((self.path.parent, f".{self.path.name}."),
                          (self.history_dir, f".{self.path.stem}-"),
                          (self.pinned_dir, f".{self.path.stem}-")):
            try:
                out += [p for p in d.iterdir()
                        if p.name.startswith(prefix) and p.name.endswith(".tmp")]
            except OSError:
                continue
        return out

    def _sweep_temps_locked(self) -> int:
        """Remove them. Only ever under the store's lock: every save that
        makes one holds that lock, so any such file seen now was left by a
        save that is no longer running."""
        n = 0
        for p in self._temp_files():
            try:
                if _stat.S_ISREG(os.lstat(p).st_mode):
                    p.unlink()
                    n += 1
            except OSError:
                pass
        return n

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
        self._sweep_temps_locked()
        _write_atomic(self.path, payload)
        self._rev_seen = rev
        self._clean = self._snap(self.data)
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
        if self._snap(self.data) == self._clean:
            return                  # nothing changed: no write, no copy, no rev
        try:
            _make_dir(self.path.parent)
            with self._lock():
                self._set_aside_if_needed()
                self._commit_locked()
        except StoreProblem as exc:
            self._rollback()
            if isinstance(exc, ConscienceConflict):
                # Read the file again by its content next time, whatever its
                # date says: "ask again" must actually work (I-19).
                self._stat = None
            raise
        except OSError as exc:
            self._rollback()
            raise ConscienceSaveFailed(_SAVE_FAILED, self.path) from exc
        except BaseException:
            self._rollback()
            raise

    def save_fresh(self, change: Callable[[dict], Any]) -> bool:
        """Make one small change to the NEWEST memories on disk and save it,
        all under the lock: what another engine wrote a moment ago is read
        first, so this save can never collide with it. For changes that are
        not the engine's own (a key issued on its first use): a reader must
        not be refused because a writer was busy (I-05). Returns True if
        anything was written. Unsaved changes in memory are not kept."""
        if self._unavailable is not None:
            raise self._unavailable
        if self._follows_home:
            why = home.problem()
            if why:
                raise DriveNotHere(why[0].upper() + why[1:] + ".")
        try:
            _make_dir(self.path.parent)
            with self._lock():
                self._open_locked()
                change(self.data)
                self._ensure_ids()
                if self._snap(self.data) == self._clean:
                    return False
                self._set_aside_if_needed()
                self._commit_locked()
                return True
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
        pins = []
        for i, p in enumerate(self._pinned_files()):
            if i >= PIN_MAX or now - self._snap_time(p) > PIN_KEEP_DAYS * 86400:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass
            else:
                pins.append(p)
        self._fit_budget_locked([p for p in snaps if p in keep], pins, now)

    def _fit_budget_locked(self, kept: list[Path], pins: list[Path], now: float) -> None:
        """Keep every copy together within HISTORY_MAX_BYTES, and leave room
        on the drive for the store itself to keep being saved."""
        sizes: dict[Path, int] = {}
        for p in kept + pins:
            try:
                sizes[p] = p.stat().st_size
            except OSError:
                sizes[p] = 0
        total = sum(sizes.values())
        try:
            store = self.path.stat().st_size
        except OSError:
            store = max(sizes.values(), default=0)
        reserve = max(HISTORY_FREE_MIN, HISTORY_FREE_SAVES * store)

        def free() -> int:
            try:
                return shutil.disk_usage(self.history_dir).free
            except OSError:
                return reserve
        if total <= HISTORY_MAX_BYTES and free() >= reserve:
            return
        # kept is newest first. What each ordinary copy is kept for:
        hours: set[int] = set()
        days: set[int] = set()
        rank: dict[Path, int] = {}
        for i, p in enumerate(kept):
            t = self._snap_time(p)
            h, d = int(t // 3600), int(t // 86400)
            daily = now - t <= HISTORY_DAILY_DAYS * 86400 and d not in days
            hourly = now - t <= HISTORY_HOURLY_DAYS * 86400 and h not in hours
            days.add(d)
            hours.add(h)
            if i < HISTORY_PROTECT:
                continue                      # never for space
            rank[p] = (3 if i < HISTORY_KEEP else 2 if daily else 1 if hourly else 0)
        for p in pins[1:]:
            rank[p] = 2
        order = sorted(rank, key=lambda p: (rank[p], self._snap_time(p)))
        for p in order:
            if total <= HISTORY_MAX_BYTES and free() >= reserve:
                break
            try:
                p.unlink(missing_ok=True)
                total -= sizes.get(p, 0)
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
        """The owner has read them. They stay in the file, marked as read.
        Only he says so, at his keyboard (S6, round 8 repair: 'conscience.py
        dismiss' from a script marked 'what was done is not what was
        approved' read)."""
        import access
        access.require_owner_console("mark his notices as read")
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
            out["noted_by"] = provenance.NOTED_BY_AI
            notes.append("Noted by the AI, not yet confirmed by him: an AI never makes "
                         "something his own words, whatever he typed. It is used, marked "
                         "unconfirmed, until he confirms it himself — /confirm in 'Talk to "
                         "JEFFEREY on this Mac'. If he wants it kept in his own words, he "
                         "types /remember and the words there.")
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
            if not rd["owner"] and f.get("visibility", "engines") != "engines" and (
                    bulk or not rd["caretaker"]):
                held.append((f, "private"))
                continue
            # a no for an AI holds for every engine reader, his own too (D1)
            if _rules.held_back(self.data, rd["audiences"], f.get("fact", ""),
                                self._fact_tags(f)):
                held.append((f, "rules"))
                continue
            seen.append(f)
        return seen, held

    @staticmethod
    def _prio_text(p: dict) -> str:
        return " ".join(str(p.get(k) or "") for k in ("context", "higher", "lower"))

    @staticmethod
    def searched(text, rd: dict | None = None) -> str:
        """The words a topic search may match (F3, round 8): for anyone but
        the owner at his keyboard, only what would leave the house — never
        the part the door hides ('Bluebird77' must not find 'Netflix
        password: Bluebird77')."""
        rd = rd or provenance.reader()
        if not rd.get("audiences"):
            return str(text or "")
        import egress
        return egress.shown_text(str(text or ""))

    # ------------------------------------------- searches that find nothing (G2)
    @staticmethod
    def _search_key() -> str | None:
        """The key a search is counted against — None for the owner himself."""
        try:
            import access
            if access.owners_hands():
                return None
            return access.current_client() or "unknown"
        except Exception:
            return "unknown"

    def search_paused(self, tool: str) -> dict | None:
        """A plain refusal when this key's searches are paused (G2), or None."""
        key = self._search_key()
        if key is None:
            return None
        until = _SearchWatch(self.path).paused_until(key)
        if until is None:
            return None
        return {"refused": True, "tool": tool, "reason": (
                    f"Searching his memories is paused for this connection for an hour, "
                    f"until {_clock_words(until)}: it searched {SEARCH_MISSES} times in ten "
                    f"minutes for words that are not there — the way someone guesses a PIN "
                    f"or a password. Nothing was searched. He has been told."),
                "tell_the_user": (
                    "Tell him plainly that searching his memories is paused for an hour "
                    "because many searches found nothing, and that it is in his notices. "
                    "Do not try other words.")}

    def search_found(self, found: bool) -> None:
        """Count a search by words, a topic or a theme that found nothing (G2).
        The twentieth in ten minutes pauses that key's searches for an hour,
        and he is told in his notices."""
        key = None if found else self._search_key()
        if key is None:
            return
        until = _SearchWatch(self.path).found_nothing(key)
        if until is None:
            return
        msg = (f"An AI using the key '{key}' searched your memories {SEARCH_MISSES} times in "
               f"ten minutes for words that are not there — the way someone guesses a PIN or "
               f"a password. Its searches are paused for an hour, until "
               f"{_clock_words(until)}. If you did not ask it to look for those things, "
               f"double-click 'What left the house' to see what it asked.")
        def tell(d: dict) -> None:
            ns = d["_notices"] if isinstance(d.get("_notices"), list) else []
            ns.append({"at": _now(), "ts": time.time(), "kind": "searches", "message": msg})
            d["_notices"] = ns[-20:]
        try:
            self.save_fresh(tell)
        except StoreProblem:
            self._runtime_notices["searches"] = msg

    def subject_closed(self, text: str, rd: dict | None = None) -> list[str]:
        """The kinds of private thing a subject names — his health, his money
        … — that one of his rules keeps from whoever reads (round 9 repair).
        Such a question is answered by his rule, the same whatever he has
        recorded, so it is never counted as a search that found nothing: his
        own JEFFEREY, asking twenty times about the health 'Never tell my
        health to any AI' keeps from it, was paused for an hour as if it were
        guessing a PIN. Read by the KIND only, never by a rule's own topic
        word, so the answer tells nothing about which words his rules name.

        Unless it carries a number (grounding.guess_shaped): 'my health and my
        boat number 4800' … '4824' named his health, so it was never counted,
        and twenty-five guesses brought no pause and no notice to him. Asking
        in plain words — 'what medication does he take' — is still no guess."""
        import rules as _rules
        rd = rd or provenance.reader()
        aud = rd.get("audiences") or frozenset()
        if not aud or not str(text or "").strip():
            return []
        tw = grounding.expand(grounding.content(text))
        kinds = set(grounding.sensitivity(text)) | {
            c for c in grounding.CLASSES if grounding.CLASS_WORDS.get(c, frozenset()) & tw}
        closed = [k for k in grounding.CLASSES
                  if k in kinds and _rules.held_back(self.data, aud, "", [k]) is not None]
        return closed if closed and not grounding.guess_shaped(text) else []

    def visible_priorities(self, rd: dict | None = None) -> tuple[list[dict], int]:
        """His values whoever reads this result may see, and how many his
        rules hold back (F2, round 8): a no on a subject — 'Never tell my
        health to any AI' — also holds back a value whose subject or words
        touch it ('sugar-free over taste' for 'my diabetes diet' went to
        every AI through get_conscience, priorities_for and who_am_i)."""
        import rules as _rules
        rd = rd or provenance.reader()
        ps = [p for p in self.data.get("priorities") or [] if isinstance(p, dict)]
        if not rd.get("audiences"):
            return ps, 0                 # the owner himself, at his keyboard
        seen, held = [], 0
        for p in ps:
            text = self._prio_text(p)
            if _rules.held_back(self.data, rd["audiences"], text,
                                ["values"] + grounding.sensitivity(text)):
                held += 1
                continue
            seen.append(p)
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
            v["noted_by"] = provenance.NOTED_BY_AI
        if reason:
            v["match_reason"] = reason
        return v

    # ------------------------------------------------------------ priorities
    def _find_priority(self, context: str, a: str, b: str) -> dict | None:
        """The value about this context and these two things. 'the car', 'The
        car!', 'car' and 'my car' are one context (the same words that matter;
        R9 convergence: 'the car.' made a second row beside his locked one)."""
        n = grounding.normalise
        same = [p for p in self.data["priorities"] if isinstance(p, dict)
                and {n(p.get("higher")), n(p.get("lower"))} == {n(a), n(b)}]
        for p in same:
            if n(p.get("context")) == n(context):
                return p
        words = grounding.content(context)
        for p in same:
            if words and grounding.content(p.get("context", "")) == words:
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
        legacy = p.get("legacy") if isinstance(p.get("legacy"), dict) else None
        if legacy and not p.get("stated"):
            # a value from before October 2026: its old confidence weighs like
            # a stated one, and it is never capped below what it was
            L = _real_number(legacy.get("confidence"))
            L = 0.55 if L is None else L
            c = (L * _STATED_WEIGHT + f) / (_STATED_WEIGHT + f + a)
            cap = max(UNCONFIRMED_CAP, min(0.99, L))
            return round(max(0.05, min(cap, c)), 2)
        if p.get("stated"):
            s = _real_number(p.get("stated_confidence"))
            s = 0.6 if s is None else s
            c = (s * _STATED_WEIGHT + f) / (_STATED_WEIGHT + f + a)
        else:
            c = (f + 1) / (f + a + 2)
        # S7 (round 8): an AI's note never says it is surer than 0.6 for him,
        # however many corrections or turns it counts (twelve of them reached
        # 0.8, and one MCP correction 0.67)
        cap = (0.99 if provenance.owner_backed(p) else
               ENGINE_CONFIDENCE_CAP if provenance.engine_note(p) else UNCONFIRMED_CAP)
        return round(max(0.05, min(cap, c)), 2)

    @staticmethod
    def _old_rule(p: dict) -> float:
        """Where a value saved before October 2026 stands by the rules it was
        saved under. A store migrated before this was kept has only counts:
        they are replayed contradictions first, the order that leaves it
        hardest to turn round."""
        legacy = p["legacy"]
        v = _real_number(legacy.get("old_rule"))
        if v is not None:
            return v
        v = _real_number(legacy.get("confidence"))
        v = 0.55 if v is None else v
        for _ in range(max(0, int(p.get("against") or 0))):
            v = round(v * (1 - _OLD_CONTRADICT), 2)
        for _ in range(max(0, int(p.get("for") or 0))):
            v = round(v + (1 - v) * _OLD_REINFORCE, 2)
        return v

    @classmethod
    def _legacy_seen(cls, p: dict, agrees: bool) -> None:
        """One more choice about a value saved before October 2026, counted
        the old way as well — called before the new count is added."""
        if not isinstance(p.get("legacy"), dict):
            return
        v = cls._old_rule(p)
        v = round(v + (1 - v) * _OLD_REINFORCE, 2) if agrees else round(v * (1 - _OLD_CONTRADICT), 2)
        p["legacy"]["old_rule"] = v

    @staticmethod
    def _prio_view(p: dict, reason: str | None = None) -> dict:
        """A value as an engine reads it, with the evidence for and against."""
        v = {k: p[k] for k in ("id", "context", "higher", "lower", "confidence", "for",
                               "against", "evidence", "updated") if k in p}
        if p.get("stated"):
            v["stated"] = True
            v["locked"] = True       # never reversed by inference; a question instead
        elif isinstance(p.get("legacy"), dict):
            v["held_since_before"] = True        # kept from before October 2026
            if (_real_number(p["legacy"].get("confidence")) or 0) >= 0.8:
                v["locked"] = True
        if provenance.pending(p):
            v["unconfirmed"] = True
            v["noted_by"] = provenance.NOTED_BY_AI
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
        src = provenance.source(values=(higher, lower), context=context)
        status = provenance.status_for(src)
        # A value about something his rules keep from this AI is noted and
        # answered the same whatever he holds about it (round 9, second
        # repair: 'He stated the opposite himself', with his value 'brand name
        # over cost' given back, confirmed a guessed value word for word, on
        # MCP, HTTP and the terminal, while priorities_for held it back). Read
        # by its own words, as record_correction is. His question still
        # reaches him.
        closed = engine and self._value_closed(context, higher, lower)
        p = self._find_priority(context, higher, lower)
        extra: dict = {}
        if p is None:
            p = {"context": context, "higher": higher, "lower": lower, "stated": True,
                 "stated_confidence": c, "for": 0, "against": 0, "evidence": 1,
                 "source": src, "status": status, "updated": _now()}
            self.data["priorities"].append(p)
        elif (grounding.normalise(p.get("higher")) == grounding.normalise(higher)
              and isinstance(p.get("legacy"), dict) and status != "confirmed"):
            # An AI repeating a value he has held since before October 2026:
            # one more observation for it, never a drop to an AI's cap.
            self._legacy_seen(p, True)
            p["for"] = int(p.get("for") or 0) + 1
            p.pop("question", None)
            p["updated"] = _now()
        elif grounding.normalise(p.get("higher")) == grounding.normalise(higher):
            # Said again. It is a statement now; never less trusted than it was.
            legacy = p.pop("legacy", None)
            if isinstance(legacy, dict) and not p.get("stated"):
                p["stated_confidence"] = _real_number(legacy.get("confidence"))
                p["stated"] = True
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
            legacy = p.get("legacy") if isinstance(p.get("legacy"), dict) else {}
            locked = (bool(p.get("stated")) and not provenance.pending(p)) or (
                (_real_number(legacy.get("confidence")) or 0) >= 0.8) or (
                # round 8 repair (S7): a value kept before JEFFEREY knew who
                # said what is his, like one he stated: never turned round by an AI
                provenance.stated_by(p) == provenance.UNKNOWN)
            # An AI never turns round or overrides a value he stated, or one
            # that is locked — whatever he typed: a question, 'I decided', 'I
            # changed my mind', words in quotation marks (R9, round 6; round 5
            # let his first-person change of mind through, and a question
            # with 'decided' in it, or a change of mind about the car,
            # turned round Mom's care at once). It is a proposal; only his own
            # /confirm at his keyboard changes it.
            if locked and engine:
                p["proposed"] = {"higher": higher, "lower": lower, "confidence": c,
                                 "source": src, "at": _now()}
                self._log_change("reversal_asked", context, was, now, src, applied=False)
                q = (f"An AI says that for {context}, {higher} now matters more to you than "
                     f"{lower}. You had said the opposite, so nothing was changed.")
                self._note("priority_question",
                           q + " If it is right, type /pending in 'Talk to JEFFEREY on this "
                               "Mac' to see it, and /confirm to make it so.")
                self._save()
                if closed:
                    return self._closed_correction(context, "value")
                return {**self._prio_view(p), "changed": False,
                        "question_for_owner": q,
                        "note": ("He stated the opposite himself, so it was not reversed — "
                                 "even if he has just said it changed. Ask him plainly. Only "
                                 "his own /confirm, typed at his keyboard in 'Talk to JEFFEREY "
                                 "on this Mac', changes it.")}
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
        if closed:
            return self._closed_correction(context, "value")
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
        # A correction about something his rules keep from this AI is noted
        # and answered the same whatever he holds about it (round 9 repair: 'He
        # said that for my HIV meds, brand name matters more than cost'
        # confirmed a guessed value word for word). Read by its own words.
        closed = engine and self._value_closed(context, hi, lo)
        if self._same_correction(context, hi, lo):
            p = self._find_priority(context, hi, lo)
            out = (self._closed_correction(context) if closed else
                   self._prio_view(p) if p else {"context": context})
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
            self._legacy_seen(p, True)
            p["for"] = int(p.get("for") or 0) + 1
        else:
            # S7 (round 8): an AI's correction never wears down a value that is
            # his — one he stated or confirmed himself (twelve of them took his
            # 'the car' from 0.6 to 0.15), and one kept before JEFFEREY knew who
            # said what (round 8 repair: forty turned 'doctor's advice > cost'
            # round, and wore a 0.9 down to 0.08). It is written down, and he
            # is asked; it does not count against him.
            mine = engine and provenance.his(p)
            if not mine:
                self._legacy_seen(p, False)
                p["against"] = int(p.get("against") or 0) + 1
            else:
                entry["not_counted"] = ("against a value he stated or confirmed himself"
                                        if provenance.owner_backed(p) else
                                        "against a value he held before JEFFEREY knew who "
                                        "said what")
            legacy = p.get("legacy") if isinstance(p.get("legacy"), dict) else None
            strong_old = bool(legacy) and (_real_number(legacy.get("confidence")) or 0) >= 0.8
            if p.get("stated") or strong_old or mine:
                said = ("said" if p.get("stated") else "confirmed"
                        if provenance.owner_backed(p) else "has long held")
                q = (f"He {said} that for {p['context']}, {p['higher']} matters more than "
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
            elif ((self._confidence(p) < LEGACY_FLIP_BELOW
                   and self._old_rule(p) < _OLD_FLIP_BELOW) if legacy else (
                    p["against"] > p["for"])):
                was = f"{p['higher']} > {p['lower']}"
                p["higher"], p["lower"] = hi, lo
                if legacy:
                    # turned round: from now on an ordinary learned value
                    p.pop("legacy", None)
                    p["for"], p["against"] = p["against"], max(1, p["for"])
                else:
                    p["for"], p["against"] = p["against"], p["for"]
                entry["flipped_from"] = was
                extra["flipped"] = {"was": was,
                                    "why": "the choices against it now outweigh the ones for it"}
        p["evidence"] = int(p.get("for") or 0) + int(p.get("against") or 0)
        p["updated"] = _now()
        p["confidence"] = self._confidence(p)
        self._save()
        if closed:
            return self._closed_correction(context)
        return {**self._prio_view(p), **extra}

    def _value_closed(self, context: str, hi: str, lo: str) -> bool:
        """Do his rules keep a value with these words from whoever reads?"""
        import rules as _rules
        rd = provenance.reader()
        if not rd.get("audiences"):
            return False
        text = f"{context} {hi} {lo}"
        return _rules.held_back(self.data, rd["audiences"], text,
                                ["values"] + grounding.sensitivity(text)) is not None

    @staticmethod
    def _closed_correction(context: str, what: str = "correction") -> dict:
        return {"context": context, "noted": True, "noted_by": provenance.NOTED_BY_AI,
                "held_back": {"why": (
                    "This is about something his own rules keep from you, so what he holds "
                    f"about it is not shown. Your {what} is noted for him to see; nothing "
                    "of his was changed.")},
                "tell_the_user": ("Tell him plainly that you noted his choice, and that his own "
                                  "rules keep this subject from you.")}

    def priorities_for(self, context: str | None = None) -> list[dict]:
        """His values, most certain first — about a subject (whole words:
        'car' is not 'caregiver'), or all of them. A value he holds about
        everything is listed last."""
        rd = provenance.reader()
        general = lambda p: grounding.normalise(p.get("context")) in grounding.CATCH_ALL  # noqa: E731
        if context:
            paused = self.search_paused("priorities_for")
            if paused:
                return [paused]                    # a list, as this tool always answers
        ps, _ = self.visible_priorities(rd)
        if context:
            q = grounding.expand(grounding.content(context))
            if not q:
                return []
            ps = [p for p in ps
                  if grounding.content(self.searched(p.get("context", ""), rd)) & q
                  or general(p)]
            self.search_found(any(not general(p) for p in ps)
                              or bool(self.subject_closed(context, rd)))
        return [self._prio_view(p) for p in
                sorted(ps, key=lambda p: (general(p), -float(p.get("confidence") or 0)))]

    # ------------------------------------------------------------ goals
    def add_goal(self, goal: str) -> dict:
        """One of his goals. Written by an AI it waits for him (S4, round 8):
        kept and shown, labelled 'noted by the AI, not yet confirmed by him'
        in the brief and the conscience, until he confirms it himself — an
        AI's 'Send $3,000 bail for my grandson' showed as his own goal."""
        text = str(goal or "").strip()
        if not text:
            return _refusal("add_goal", "There is no goal to keep: it is empty.")
        src = provenance.source(text=text)
        entry = {"goal": text, "added": _now(), "active": True, "source": src,
                 "status": provenance.status_for(src)}
        self.data["goals"].append(entry)
        self._save()
        out = {k: v for k, v in entry.items() if k != "source"}
        if entry["status"] == "pending":
            out["noted_by"] = provenance.NOTED_BY_AI
            out["note"] = ("Noted by the AI, not yet confirmed by him: it is shown as such in "
                           "his brief until he confirms it himself (/pending, then /confirm "
                           "in 'Talk to JEFFEREY on this Mac'). Never call it his goal before "
                           "he does.")
        return out

    @staticmethod
    def _goal_view(g: dict) -> dict:
        """A goal as an engine reads it, and whether it is his yet."""
        v = {k: g[k] for k in ("id", "goal", "added", "active") if k in g}
        if provenance.pending(g):
            v["unconfirmed"] = True
            v["noted_by"] = provenance.NOTED_BY_AI
        return v

    @staticmethod
    def _goal_line(g: dict) -> str:
        """A goal in one line of the brief, labelled when an AI wrote it."""
        text = str(g.get("goal") or "")
        return f"{text} ({provenance.NOTED_BY_AI})" if provenance.pending(g) else text

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
    def _category_words(category: str) -> str:
        """A category in one spelling, read through the shared fold (round 8
        repair): look-alike letters, digits for letters and accents read as
        the letters they stand for ('hоme', 'h0me', 'propriété')."""
        t = grounding.fold(str(category or ""), _NEVER_WORDS | grounding.FOLD_WORDS)
        return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()

    @classmethod
    def _never_outright(cls, category: str) -> str | None:
        """Why nothing at all is ever done under this category (moving money,
        gift cards, crypto, a call or the doors) — or None."""
        words = cls._category_words(category)
        for rx, why in _NEVER:
            if rx.search(words):
                return why
        return None

    @classmethod
    def _home_itself(cls, category: str) -> bool:
        """Is this category about his home itself (S9)?"""
        words = cls._category_words(category)
        return bool(_HOME_ITSELF.search(words)) and not _HOME_GOODS.search(words)

    @classmethod
    def _never(cls, category: str, description: str = "") -> str | None:
        """Why this can never be 'act', whatever is set — or None. Only the
        CATEGORY decides (R10, round 6): a description is an engine's words,
        and reading them for 'never' refused ordinary errands."""
        return cls._never_outright(category) or (_HOME_WHY if cls._home_itself(category)
                                                 else None)

    @staticmethod
    def _ask_first(description: str) -> str | None:
        """Why what a description names is the owner's to decide first, in
        his words — or None (R10, round 6; D4, round 7: anything about
        getting into his home, under any category)."""
        door = entry_words(description or "")
        if door:
            return (f"Ask the owner first: this is about getting into the house — its "
                    f"doors, keys, locks, codes or alarm, or letting someone in "
                    f"('{door}'). It is his home, so he decides this himself; JEFFEREY "
                    f"does not do it because an AI asked. Tell him plainly what was "
                    f"asked, and for whom.")
        text = (description or "").lower()
        for rx, why in _ASK_IN_TEXT:
            m = rx.search(text)
            if m:
                return (f"Ask the owner first: this means {why} ('{m.group().strip()}'). "
                        f"JEFFEREY does not do that because an AI asked. Tell him plainly "
                        f"what was asked; he decides himself.")
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
        if p["level"] == "act" and self._never(self._cat(category)):
            # 'act' saved where it can never be (his home itself, S9, or a
            # door, a transfer, a call) reads as what it always was: he decides
            p["level"] = "recommend"
            p["never_act"] = True
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

        def no(reason: str, verdict: str = "not_allowed", **kw) -> dict:
            return {"allowed": False, "verdict": verdict, "reason": reason, **shown, **kw}

        never = self._never_outright(cat)
        if never:
            return no(f"JEFFEREY never does this ({never}), whatever anyone has set. "
                      f"Only the owner can, himself. Tell him plainly what was asked "
                      f"— it may be a scam.", "never")
        first = self._ask_first(desc)
        if first:
            # at any level, under any category (D4): the owner's to decide
            return no(first, "ask_owner")
        if self._home_itself(cat):
            # his home itself is never 'act' (S9), and an errand under it is his
            # to decide — brought to him, never called a scam (round 8 repair:
            # a stored 'home' at act made 'Water the plants' 'never … a scam')
            return no(f"'{cat}' is about his home itself, so JEFFEREY never does anything "
                      f"there for him, at any level: bring it to him as a suggestion — he "
                      f"decides himself.")
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
        if _SALEISH.search(cat) and perm.get("floor") is None:
            # A limit saved for selling before floors existed is a ceiling,
            # and a ceiling on a sale protects nothing (verify I-44: 'sell
            # the ring, appraised $4,200, for $20' was approved three times).
            return no(f"The owner has not set the lowest price he would accept for "
                      f"'{cat}', so no sale is approved. Bring the offer to him; he can "
                      f"set one himself (/permit {cat} act at least …).")
        mentioned = [float((a or b).replace(",", "")) for a, b in _AMOUNT_IN_TEXT.findall(desc.lower())
                     if (a or b).replace(",", "").replace(".", "", 1).isdigit()]
        if mentioned and not _SALEISH.search(cat) and (amt is None
                                                        or max(mentioned) > amt + 0.005):
            return no(f"The description mentions {_money(max(mentioned), pcur)}, more than "
                      f"the amount given. State the full price as the amount; nothing is "
                      f"approved for less than it really costs.")
        if perm.get("floor") is not None:
            if amt is None or amt <= 0:
                return no("Say the full sale price as a plain number (for example 450); "
                          "nothing is approved without it.")
            if amt < perm["floor"]:
                return no(f"{_money(amt, pcur)} is below the lowest price the owner set for "
                          f"'{cat}' ({_money(perm['floor'], pcur)}). Bring the offer to him.")
            return {"allowed": True, "verdict": "allowed",
                    "reason": "at or above the lowest price the owner set", **shown}
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
            return {"allowed": True, "verdict": "allowed",
                    "reason": "within the limit the owner set", **shown,
                    "spent_this_period": round(spent + amt, 2),
                    "left_this_period": round(max(0.0, cap - spent - amt), 2)}
        if _MONEYISH.search(cat):
            return no(f"No spending limit is set for '{cat}', so nothing that costs money "
                      f"can be approved there. Only the owner can set one, himself.")
        if (amt is not None and amt != 0) or _MONEY_TEXT.search(desc.lower()):
            return no(f"The owner allowed '{cat}' only for things that cost nothing and "
                      f"move no money; this one involves money. Bring it to him.")
        return {"allowed": True, "verdict": "allowed",
                "reason": "within the authority the owner gave (nothing that costs money)",
                **shown}

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
        # The verdict is JEFFEREY's; the words of what was asked are the
        # engine's, and the line says so (verify I-45).
        entry["description_by"] = "engine"
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
        elif amt is not None and amt > 0.005:
            # An approval for something that costs nothing never covers a
            # purchase (verify I-45: 'turn on the porch light' was approved,
            # then logged as a $5,000 television, approved:true).
            return ("that approval was for something that costs nothing, and this "
                    f"cost {_money(amt, a.get('currency') or DEFAULT_CURRENCY)}"), None
        return None, a

    def _not_what_was_approved(self, done: str, approved: str,
                               approved_amount=None) -> str | None:
        """Why an act written down is not the act that was approved — or None
        (S8, round 8). What was done would itself have asked the owner first
        (his doors, keys, codes and alarm, letting someone in, money moved, a
        call as him) and what was approved would not; or — round 8 repair —
        it says anything beyond what was approved: a word that means
        something and is not a word of the approval (in the past tense or
        not), or more money than the approval named. 'Fed the cat at 6 and
        wired $2,000 to Mike' under 'Feed the cat at 6' was approved:true,
        and so were twelve others: a list of words cannot know every act
        that can be added; what was approved can."""
        if self._ask_first(done) and not self._ask_first(approved):
            return ("what was done is something only he decides, and what was approved "
                    "was not")
        beyond = _beyond_approval(done, approved, approved_amount)
        if beyond:
            return "it says more than what was approved: " + ", ".join(
                f"'{w}'" for w in beyond[:8])
        return None

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
        mismatch = None
        if auth is not None:
            # The approval is used either way: it never covers a second act.
            auth["used"] = _now()
            mismatch = self._not_what_was_approved(entry["description"],
                                                   str(auth.get("description") or ""),
                                                   auth.get("amount"))
        if auth is not None and mismatch:
            # S8 (round 8): an approval for 'Feed the cat at 6' covered a
            # logged 'Unlocked the front door and let the plumber in' as
            # approved:true. Only what was approved is approved.
            entry.update(authorization_id=aid, approved=False,
                         approved_for=str(auth.get("description") or "")[:300],
                         note=(f"Not an approved act: what was done is not what was approved "
                               f"({mismatch}). The owner sees this line marked that way."))
            approved_for = on_screen(str(auth.get("description") or ""))[:120]
            done_said = on_screen(entry["description"])[:160]
            only_his = mismatch.startswith("what was done is something only he decides")
            self._note("action_mismatch", (
                f"An AI wrote in your action log ('{cat}') something beyond what you "
                f"approved: you approved '{approved_for}', and it wrote '{done_said}' — what "
                f"was done is not what was approved, so it is marked 'not approved' there. "
                + ("That is something only you decide: ask JEFFEREY what happened."
                   if only_his else
                   "If that is all it did, nothing is wrong; if not, ask JEFFEREY what "
                   "happened.")))
        elif auth is not None:
            # What was approved stands beside what was done, so the owner
            # sees at a glance whether they are the same thing (verify I-45).
            entry.update(authorization_id=aid, approved=True,
                         approved_for=str(auth.get("description") or "")[:300])
        else:
            entry.update(authorization_id=aid or None, approved=False,
                         note=f"Not an approved act: {problem}. The owner sees this "
                              f"line marked that way.")
        self.data["actions"].append(self._stamp(entry, "engine"))
        self._save()
        return entry

    def action_log(self, limit: int = 20, filtered: bool = True) -> list[dict]:
        """What was done, newest first. A line about his health, money,
        children, home or someone's confidence reaches only a key that holds
        his private life, and never past his own rules: the others see that
        something was done, in that category, and not what (verify I-11: the
        action log gave every guest 'booked VAC mental-health intake' that the
        daily brief held back)."""
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(200, limit))
        acts = self.data["actions"][-limit:][::-1]
        if not filtered:
            return acts
        rd = provenance.reader()
        if not rd["audiences"]:
            return acts                  # the owner himself, at his keyboard
        out = []
        for a in acts:
            text = " ".join(str(a.get(k) or "") for k in ("description", "approved_for",
                                                           "outcome"))
            if self.reader_may_see(rd, text, a.get("category", "")):
                out.append(a)
            else:
                out.append({k: a[k] for k in ("category", "at", "added", "approved",
                                              "authorization_id", "id") if k in a}
                           | {"held_back": ("private, or kept from this connection by "
                                            "his own rules — do not guess at it")})
        return out

    def reader_may_see(self, rd: dict, text: str, category: str = "") -> bool:
        """May whoever reads this result see a line with this text? Private
        kinds only through his caretaker key, and never what his rules keep
        from this reader."""
        import rules as _rules
        if not rd.get("audiences"):
            return True                  # the owner himself, at his keyboard
        kinds = grounding.sensitivity(text, category)
        if kinds and not rd.get("caretaker") and not rd.get("owner"):
            return False
        return not _rules.held_back(self.data, rd["audiences"], text,
                                    [str(category or "")] + kinds)

    def _goals_for(self, rd: dict) -> tuple[list[dict], int, int]:
        """(the newest active goals this reader may see, how many were held
        back, how many more there are)."""
        goals = [g for g in self.data.get("goals") or []
                 if isinstance(g, dict) and g.get("active")]
        seen = [g for g in goals if self.reader_may_see(rd, str(g.get("goal") or ""))]
        held = len(goals) - len(seen)
        return seen[-GOALS_SHOWN:][::-1], held, max(0, len(seen) - GOALS_SHOWN)

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
        rd = provenance.reader()
        obs = self.data["observations"][-5:][::-1]
        acts = self.action_log(10, filtered=False)
        goals, held, more_goals = self._goals_for(rd)
        if rd["audiences"]:
            def ok(text, cat):
                return self.reader_may_see(rd, text, cat)
            keep_obs = [o for o in obs if ok(o.get("note", ""), o.get("category", ""))]
            keep_acts = [a for a in acts if ok(a.get("description", ""), a.get("category", ""))]
            held += len(obs) - len(keep_obs) + len(acts) - len(keep_acts)
            obs, acts = keep_obs, keep_acts
        notices = self.notices()
        out = {
            "orb": self.orb_state(),
            "active_goals": [self._goal_line(g) for g in goals],
            "opportunities": self._shown_opportunities()[:10],
            "recent_actions": acts,
            "recent_observations": obs,
            "corrections_learned_from": len(self.data["corrections"]),
            # a recovery, a restore, a change made by hand, a change to the
            # caretaker, family or executor key: the owner is told
            "notices": notices[-NOTICES_SHOWN:],
        }
        if more_goals:
            out["more_goals"] = more_goals
        if len(notices) > NOTICES_SHOWN:
            out["more_notices"] = len(notices) - NOTICES_SHOWN
        if held:
            out["held_back"] = {"count": held, "why": (
                "Some recent lines are private, or kept from this connection by his "
                "own rules. Do not guess at them.")}
        waiting = self.waiting_for_owner()
        if waiting:
            out["waiting_for_owner"] = waiting
        if rd["owner"] or rd["caretaker"]:
            # changes to his list of agreed payments an AI asked for (verify
            # I-47: nothing showed they waited, so they waited forever)
            charges = sum(1 for p in self.data.get("charge_proposals") or []
                          if isinstance(p, dict) and p.get("status") == "waiting")
            if charges:
                out["charges_waiting_for_owner"] = {"count": charges, "how": (
                    "Changes to his list of agreed payments that an AI asked for. Only "
                    "he says yes or no to each: he double-clicks 'Check my charges' on "
                    "his Mac, or types /charges in 'Talk to JEFFEREY on this Mac'. "
                    "Until then, those charges are still pointed out to him.")}
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
        shown, prios_held = self.visible_priorities(rd)
        prios = sorted(shown, key=lambda p: -float(p.get("confidence") or 0))
        goals, goals_held, more_goals = self._goals_for(rd)
        notices = self.notices()
        out = {
            "owner": self.data.get("owner"),
            "priorities": [self._prio_view(p) for p in prios[:top]],
            "facts": [self._fact_view(f) for f in page],
            # verify I-11, I-41: goals are his too ('Find a memory clinic for my
            # Alzheimer's'), and 200 of them made an 89 KB system prompt
            "active_goals": [self._goal_view(g) for g in goals],
            "corrections_learned_from": len(self.data["corrections"]),
            "notices": notices[-NOTICES_SHOWN:],
        }
        if more_goals:
            out["more_goals"] = more_goals
        if len(notices) > NOTICES_SHOWN:
            out["more_notices"] = len(notices) - NOTICES_SHOWN
        if len(prios) > top:
            out["more_priorities"] = len(prios) - top
        if len(facts) > off + lim:
            out["more_facts"] = len(facts) - off - lim
            out["how_to_see_more"] = (f"Older facts: call again with offset={off + lim}, "
                                      f"or ask explain_basis about the subject you need.")
        private = sum(1 for _, why in held if why == "private")
        ruled = sum(1 for _, why in held if why == "rules") + prios_held
        if private or ruled or goals_held:
            out["held_back"] = {
                "private": private, "by_his_rules": ruled,
                **({"goals": goals_held} if goals_held else {}),
                "why": ("Private facts (his health, money, children, the safety of his "
                        "home, other people's confidences) are not sent all at once. "
                        + ("Ask explain_basis about the subject and the ones that matter "
                           "come back. " if rd["caretaker"] else "")
                        + "Never guess at what is held back.")}
        waiting = self.waiting_for_owner()
        if waiting:
            out["waiting_for_owner"] = waiting
        return out

    def waiting_for_owner(self) -> dict | None:
        """How many notes an AI wrote down wait for his confirmation (D2,
        round 7) — a count, said to every reader, never what they say."""
        items = self.pending_items()
        notes = sum(1 for x in items if x["kind"] != "request to share")
        if not items:
            return None
        return {"count": len(items), "notes_to_confirm": notes, "how": (
            f"{notes} note(s) an AI wrote down wait for his confirmation"
            + (f", and {len(items) - notes} request(s) to share something" if
               len(items) > notes else "")
            + ". They are used, marked unconfirmed, but they are not his words until he "
              "confirms them himself: /pending and /confirm in 'Talk to JEFFEREY on this "
              "Mac', or 'python connector/conscience.py confirm'. Never call them his "
              "words before he does.")}

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

    def explain_basis(self, topic: str, limit=None, offset=0, watch: bool = True) -> dict:
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
        caretaker key, and nothing his rules keep from this engine.

        A search (G2, round 9): only what release would show this engine is
        matched, what is held back is counted only by the kind of thing the
        subject names, and a key paused for searching that finds nothing is
        refused. `watch=False` for JEFFEREY's own reading inside a tool that
        is not a search (triage)."""
        t = str(topic or "").strip()
        if watch:
            paused = self.search_paused("explain_basis")
            if paused:
                return paused
        problem = grounding.topic_problem(t)
        if problem:
            return {"topic": t, "priorities": [], "facts": [], "note": problem}
        tw = grounding.expand(grounding.content(t))
        rows = []
        rd = provenance.reader()
        prios, prios_held = self.visible_priorities(rd)
        for p in prios:
            ctx = p.get("context", "")
            m = grounding.context_match(ctx if grounding.normalise(ctx) in grounding.CATCH_ALL
                                        else self.searched(ctx, rd), tw)
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
        about = any(r[0][0] == 0 for r in rows)
        if not access.may("facts.read"):
            out["note"] = ("The key this connection holds may not read the owner's "
                           "facts, so none are included.")
            if watch:
                self.search_found(about or bool(self.subject_closed(t, rd)))
            return out
        seen, held = self.visible_facts(rd, bulk=False)
        # anyone but the owner's own house gets a private fact only for a
        # subject that names its kind (verify I-28)
        asked = None if rd["owner"] else t
        scored = []
        for f in seen:
            m = grounding.fact_match(self.searched(f.get("fact", ""), rd), f.get("category", ""),
                                     f.get("sensitivity") or [], tw, asked)
            if m:
                scored.append(((-m[0], provenance.pending(f)), f, m[1]))
        scored.sort(key=lambda r: r[0])
        lim, off = _page(limit, offset, BASIS_FACTS, BASIS_MAX)
        out["facts"] = [self._fact_view(f, why) for _, f, why in scored[off:off + lim]]
        if len(scored) > off + lim:
            out["more_facts"] = len(scored) - off - lim
            out["how_to_see_more"] = f"Call again with offset={off + lim}."
        # What is held back is never matched by its words (G2, round 9: the
        # count told an engine that 'Biktarvy' was in a fact it may not read):
        # only by the kind of private thing the subject itself names.
        named = {c for c in grounding.CLASSES if grounding.CLASS_WORDS.get(c, frozenset()) & tw}
        kept = sum(1 for f, _ in held if named & set(f.get("sensitivity") or []))
        if watch:
            # a subject his rules close to this reader is answered by the rule,
            # whatever he has recorded: never a guess (round 9 repair)
            self.search_found(about or bool(scored) or bool(self.subject_closed(t, rd)))
        if kept:
            out["held_back"] = {"count": kept, "why": (
                "Some facts on this subject are private, or kept from this connection "
                "by his own rules. Do not guess at them.")}
        return out

    # ------------------------------------------------------- waiting for him
    _CONFIRMABLE = ("facts", "priorities", "memories", "media", "goals", "people", "rules",
                    "rule_proposals", "profile_notes")

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
        out += self._his_own_waiting()
        return out

    def _his_own_waiting(self) -> list[dict]:
        """What an AI asked about what is HIS (round 8): his goals (S4), his
        people and changes to them (S3), his rules (S1) and his profile (S2).
        Nothing here has changed anything of his until he confirms it."""
        out = []
        for g in self.data.get("goals") or []:
            if isinstance(g, dict) and g.get("active") and provenance.pending(g):
                out.append({"id": g.get("id"), "kind": "goal", "what": g.get("goal", ""),
                            "why": "an AI wrote it down as your goal; you have not confirmed it"})
        for p in self.data.get("people") or []:
            if not isinstance(p, dict):
                continue
            who = p.get("name", "") + (f" ({p.get('relationship')})" if p.get("relationship")
                                       else "")
            if provenance.pending(p):
                notes = str(p.get("notes") or "").strip()
                out.append({"id": p.get("id"), "kind": "person",
                            "what": who + (f" — {notes[:100]}" if notes else ""),
                            "why": "an AI wrote this person down; you have not confirmed them, "
                                   "so JEFFEREY does not count them as someone you know"})
            pr = p.get("proposed")
            if isinstance(pr, dict):
                import life as _life
                out.append({"id": p.get("id"), "kind": "change to a person",
                            "what": f"{who}: {_life.describe_change(pr)}",
                            "why": "an AI asks to change someone you recorded; nothing was "
                                   "changed, and confirming changes it"})
        for r in self.data.get("rules") or []:
            if isinstance(r, dict) and provenance.pending(r):
                out.append({"id": r.get("id"), "kind": "rule",
                            "what": _rule_said(r, "the AI's words"),
                            "why": "an AI wrote down this no; it already holds, and confirming "
                                   "makes it your own rule",
                            "effect": "keeps"})
        for x in self.data.get("rule_proposals") or []:
            if not isinstance(x, dict):
                continue
            r = x.get("rule") if isinstance(x.get("rule"), dict) else {}
            if x.get("action") == "remove":
                out.append({"id": x.get("id"), "kind": "removing one of his rules",
                            "what": "TAKING AWAY " + _rule_said(r, "its words", taken=True),
                            "why": "an AI asked to take this rule away; it still holds, and "
                                   "confirming takes it away (you can put it back)",
                            "effect": "takes away"})
            else:
                out.append({"id": x.get("id"), "kind": "new rule",
                            "what": _rule_said(r, "the AI's words"),
                            "why": "an AI asked for this rule; it changes nothing until you "
                                   "confirm it — " + _rule_if_confirmed(r),
                            "effect": ("yes" if r.get("kind") == "disclosure" and r.get("allow")
                                       else "no" if r.get("kind") == "disclosure" else "how")})
        prof = self.data.get("profile") if isinstance(self.data.get("profile"), dict) else {}
        for n in self.data.get("profile_notes") or []:
            if not isinstance(n, dict):
                continue
            had = str(prof.get(n.get("field")) or "")
            out.append({"id": n.get("id"), "kind": "profile detail",
                        "what": f"{n.get('label') or n.get('field')}: {n.get('value')}"
                                + (f" — you have {had}" if had else ""),
                        "why": "an AI wrote it down for your forms; forms use only what you "
                               "confirmed, and confirming puts this on them"})
        return out

    @staticmethod
    def rule_changes(items) -> str:
        """What confirming these does to his rules, in one line — or ''
        (round 8 repair: '/confirm all' said only 'everything an AI noted
        down', while it also took his rules away and added yes rules)."""
        n = {k: sum(1 for it in items if it.get("effect") == k)
             for k in ("yes", "no", "how", "takes away")}
        bits = []
        if n["yes"]:
            bits.append(f"it adds {n['yes']} yes (letting someone hear about you)")
        if n["no"]:
            bits.append(f"it adds {n['no']} no")
        if n["how"]:
            bits.append(f"it adds {n['how']} rule{'s' if n['how'] > 1 else ''} for how to react "
                        f"to you or speak of you")
        if n["takes away"]:
            bits.append(f"it takes away {n['takes away']} of your rules")
        if not bits:
            return ""
        return ("This also changes your rules: " + (", ".join(bits[:-1]) + " and " + bits[-1]
                                                    if len(bits) > 1 else bits[0]) + ".")

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
        access.require_owner_console("confirm what an AI wrote down")
        want = [str(x).strip() for x in (ids if isinstance(ids, (list, tuple))
                                         else str(ids or "").replace(",", " ").split())
                if str(x).strip()]
        if want == ["all"]:
            want = [x["id"] for x in self.pending_items() if x["kind"] != "request to share"]
        want = list(dict.fromkeys(want))        # a person and a change to them share an id
        done, unknown = [], []
        src = provenance.source()
        for i in want:
            sec, it = self._find_item(i, self._CONFIRMABLE)
            if it is None:
                unknown.append(i)
                continue
            if sec in ("rule_proposals", "profile_notes"):
                # an AI's request about his rules or his profile: confirming
                # does what it asked, and the request itself is done with
                self._carry_out_request(sec, it, src)
                done.append(i)
                continue
            if sec == "people" and isinstance(it.get("proposed"), dict):
                import life as _life
                _life.apply_change(it, it.pop("proposed"))
                it["updated"] = _now()
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
            if sec == "memories" and "verbatim" in it:
                it["verbatim"] = True          # his words now: he said so himself (D2)
            if sec == "priorities":
                it["evidence"] = int(it.get("for") or 0) + int(it.get("against") or 0) or 1
                it["confidence"] = self._confidence(it)
            done.append(i)
        if done:
            self._save()
        return {"confirmed": done, "unknown_ids": unknown}

    def _carry_out_request(self, sec: str, it: dict, src: dict) -> None:
        """His yes to what an AI asked about his rules (S1) or his profile
        (S2). Changes memory only; confirm() saves."""
        lst = self.data.get(sec) or []
        if sec == "rule_proposals":
            rule = dict(it.get("rule") or {})
            if it.get("action") == "remove":
                cur = next((r for r in self.data.get("rules") or []
                            if isinstance(r, dict) and r.get("id") == it.get("rule_id")), None)
                if cur is not None:
                    import forgetting
                    forgetting.remove_now(self, "rules", [cur], "remove_rule",
                                          (it.get("source") or {}).get("by", "an AI"))
            elif rule:
                rule.update(status="confirmed", confirmed_by_owner=_now(),
                            source=it.get("source") or src)
                rule.pop("id", None)
                self.data.setdefault("rules", []).append(rule)
        else:
            prof = self.data.setdefault("profile", {})
            key, new = it.get("field"), it.get("value")
            old = str(prof.get(key) or "")
            if key:
                prof[key] = new
                if old and old != new:
                    self.data["actions"].append(self._stamp({
                        "category": "profile", "description": (
                            f"changed his {it.get('label') or key} on forms from '{old}' to "
                            f"'{new}', confirmed by the owner himself"),
                        "amount": None, "outcome": "changed", "added": _now(),
                        "ts": time.time()}, "jefferey"))
        self.data[sec] = [x for x in lst if x is not it]

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


# ---------------------------------------------- what he confirms, on his screen
# Round 8 repair (S1): what he confirms is an AI's own words, so what it DOES
# comes first — yes or no, about what, for whom — and the words follow in
# full, never cut, with every control character (a new line, a colour code)
# shown as a space: a rule cannot draw a line of its own on his screen.
_SCREEN_CONTROL = re.compile("[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e"
                             "\u2060-\u2069\ufeff]")


def on_screen(text) -> str:
    """Text as it may stand on his screen: one line, no control characters."""
    return " ".join(_SCREEN_CONTROL.sub(" ", str(text or "")).split())


def _rule_parts(r: dict) -> tuple[str, str]:
    topic = ", ".join(str(t) for t in r.get("tags") or []) or "anything"
    aud = str(r.get("audience_written") or r.get("audience") or "me")
    return on_screen(topic), on_screen(aud)


def _rule_said(r: dict, whose: str, taken: bool = False) -> str:
    """One rule, for his screen: what it does first, then its words in full."""
    topic, aud = _rule_parts(r)
    words = f" — {whose}: \"{on_screen(r.get('instruction', ''))}\""
    kind = r.get("kind")
    if kind == "reaction":
        head = f"HOW TO REACT to you about {topic}"
    elif kind == "representation":
        head = f"HOW TO SPEAK OF YOU to {aud} about {topic}"
    elif r.get("allow"):
        head = (f"your YES: {aud} may hear about {topic}" if taken
                else f"A YES: {aud} may hear about {topic}")
    else:
        head = (f"your NO: never tell {aud} about {topic}" if taken
                else f"A NO: never tell {aud} about {topic}")
    return head + words


def _rule_if_confirmed(r: dict) -> str:
    topic, aud = _rule_parts(r)
    about = "anything about you" if topic == "anything" else f"your {topic}"
    if r.get("kind") == "reaction":
        return "if you confirm it, JEFFEREY reacts to you this way"
    if r.get("kind") == "representation":
        return f"if you confirm it, JEFFEREY speaks of you this way to {aud}"
    if r.get("allow"):
        return f"if you confirm it, {aud} may hear about {about}"
    return f"if you confirm it, {aud} is never told about {about}"


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


def edit(c: Conscience, editor: list[str] | None = None, input_fn=None,
         tty: bool | None = None) -> int:
    """The owner's validated hand edit, at his keyboard (S6, round 8 repair:
    with an EDITOR script and stdin from /dev/null it made an AI's notes his
    and its 'Anyone may know my money' a confirmed yes). Only a person at
    this keyboard starts it; a private copy of the memory file opens in a
    text editor; when it is saved and closed it is checked, he is told what
    it changes of his own (notes made his, rules added or taken away), and
    he types the number shown. A mistake is named by line and nothing
    changes (the edited copy is kept to fix); a good edit becomes the newest
    revision, with the version from before pinned so it can be undone.

    The memory file is a plain file: whatever can write to it — the owner's
    own editor, or any program with a shell on this Mac — can change it
    directly, and JEFFEREY adopts what it finds (it keeps the copy from
    before). That is why no AI should ever run commands on this Mac."""
    import shlex
    import shutil
    import subprocess
    import answers
    if tty is None:
        tty = answers.person_at_keyboard()
    if not tty:
        print("  " + answers.NOT_AT_KEYBOARD)
        return 1
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
        old_obj = Conscience._parse(raw)
    except _Unreadable:
        old_obj = {}
    for line in _what_an_edit_makes_his(old_obj, obj):
        print("  " + line)
    if not answers.confirm_by_code(print, input_fn, True, "Save this edit?"):
        os.unlink(tmp)
        print("  Your memories are exactly as they were.")
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


def _what_an_edit_makes_his(old: dict, new: dict) -> list[str]:
    """What a hand edit changes of what is his, in plain words: an AI's notes
    it makes his, rules it adds or takes away (round 8 repair, S6)."""
    def made_his(sec: str) -> int:
        was = {x["id"]: x for x in old.get(sec) or [] if isinstance(x, dict) and x.get("id")}
        return sum(1 for x in new.get(sec) or [] if isinstance(x, dict)
                   and x.get("id") in was and provenance.pending(was[x["id"]])
                   and not provenance.pending(x))
    lines = []
    notes = sum(made_his(sec) for sec in ("facts", "memories", "media", "people", "goals",
                                          "priorities"))
    if notes:
        lines.append(f"This edit makes {notes} thing(s) an AI wrote down your own words.")
    key = lambda r: (r.get("kind"), str(r.get("instruction")), r.get("audience"),  # noqa: E731
                     bool(r.get("allow")))
    was = {key(r) for r in old.get("rules") or [] if isinstance(r, dict)}
    now = {key(r) for r in new.get("rules") or [] if isinstance(r, dict)}
    yes = sum(1 for k in now - was if k[0] == "disclosure" and k[3])
    if yes:
        lines.append(f"It adds {yes} yes rule(s): someone may hear about you.")
    if now - was and len(now - was) > yes:
        lines.append(f"It adds {len(now - was) - yes} other rule(s).")
    if was - now:
        lines.append(f"It takes away {len(was - now)} of your rules.")
    return lines or ["This edit changes no rule, and makes nothing an AI wrote your own."]


def confirm_at_keyboard(c: "Conscience", which=(), yes: bool = False, input_fn=None,
                        out=print, tty: bool | None = None) -> int:
    """What an AI noted down, in plain words, numbered; he says which are
    right — one, several or all — and those become his own words (D2,
    round 7). Only a person at this keyboard (S6, round 8): stdin and stdout
    must be terminals, --yes is ignored, and he types back a number shown on
    the screen at that moment, read from the terminal itself. (Before, 'confirm
    all --yes' with stdin from /dev/null confirmed an AI's notes as his.)"""
    import access
    import answers
    if yes:
        out("  " + answers.YES_IGNORED)
    if tty is None:
        tty = answers.person_at_keyboard()
    if not tty:
        out("  " + answers.NOT_AT_KEYBOARD)
        return 1
    ask = input_fn or answers.read_tty
    try:
        c.refresh()
    except StoreProblem as e:
        out("  " + e.for_owner())
        return 1
    items = [it for it in c.pending_items() if it["kind"] != "request to share"]
    if not items:
        out("  Nothing is waiting for you: everything kept is in your own words, or you "
            "have confirmed it.")
        return 0
    out(f"  {len(items)} thing(s) an AI noted down wait for your OK:")
    for k, it in enumerate(items, 1):
        out(f"    {k}. ({it['kind']}) {on_screen(it['what'])}")
        out(f"          — {on_screen(it['why'])}")
    chosen = [w for w in which or () if str(w).strip()]
    if not chosen:
        answers.flush_typeahead()
        try:
            said = ask("  Which are right? Type their numbers (for example 1 3), or "
                       "all, and press return. Press return alone to stop: ")
        except EOFError:
            said = ""
        chosen = str(said or "").replace(",", " ").split()
    if not chosen:
        out("  Nothing was changed.")
        return 0
    if any(str(w).lower() == "all" for w in chosen):
        picked = items
    else:
        picked = []
        for w in chosen:
            if not str(w).isdigit() or not 1 <= int(w) <= len(items):
                out(f"  There is no number {w} in the list. Nothing was changed.")
                return 1
            picked.append(items[int(w) - 1])
    out("  You are saying these are right — your own words from now on:")
    for it in picked:
        out(f"    · {on_screen(it['what'])}")
    changes = c.rule_changes(picked)
    if changes:
        out("  " + changes)
    if not answers.confirm_by_code(out, input_fn, True, "Is that right?"):
        return 1
    try:
        with access.owner_console():
            res = c.confirm([it["id"] for it in picked])
    except (StoreProblem, PermissionError) as e:
        out("  Not done: " + (e.for_owner() if isinstance(e, StoreProblem) else str(e)))
        return 1
    out(f"  Done. Confirmed {len(res['confirmed'])}: they are your own words now.")
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
    r.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)   # ignored (S6)
    sub.add_parser("dismiss", parents=[common], help="I have read the notices")
    sub.add_parser("edit", parents=[common], help="change them by hand, checked")
    cf = sub.add_parser("confirm", parents=[common],
                        help="say yes to what an AI noted down, so it is your own words")
    cf.add_argument("which", nargs="*", help="their numbers in the list, or all")
    cf.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)   # ignored (S6)
    a = ap.parse_args(argv)
    path = Path(a.path).expanduser() if a.path else DEFAULT_STORE

    away = None if a.path else home.problem()
    if away:
        # Never "none yet" when the drive that holds them is simply away —
        # and never 'needs restoring' either (verify regression: the
        # installer then told him to restore an earlier copy): exit 3.
        print("  Your memories: " + away + ".")
        return 3
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
    if a.cmd == "confirm":
        return confirm_at_keyboard(c, a.which, a.yes)
    if a.cmd == "dismiss":
        # only a person at this keyboard (S6, round 8 repair)
        import answers
        if not answers.person_at_keyboard():
            print("  " + answers.NOT_AT_KEYBOARD)
            return 1
        try:
            c.refresh()
            waiting = c.notices()
        except StoreProblem as e:
            print("  " + e.for_owner())
            return 1
        if not waiting:
            print("  There are no notices to mark as read.")
            return 0
        print(f"  {len(waiting)} notice(s):")
        for x in waiting:
            print(f"    · {on_screen(x.get('what'))}")
        if not answers.confirm_by_code(print, None, True, "Mark them as read?"):
            return 1
        try:
            import access
            with access.owner_console():
                n = c.dismiss_notices()
        except StoreProblem as e:
            print("  " + e.for_owner())
            return 1
        print(f"  Marked {n} notice(s) as read.")
        return 0
    # restore — only a person at this keyboard (S6)
    import answers
    if a.yes:
        print("  " + answers.YES_IGNORED)
    if not answers.person_at_keyboard():
        print("  " + answers.NOT_AT_KEYBOARD)
        return 1
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
    if not answers.confirm_by_code(print, None, True, "Put this copy back?"):
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
