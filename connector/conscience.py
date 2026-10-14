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
import functools
import hashlib
import json
import os
import re
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
DEFAULT_STORE = home.conscience_path()   # on the drive if one is plugged in

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


class _Unreadable(ValueError):
    """Why bytes are not a usable store, in plain words, and whether that
    looks like a power-cut tear (`torn`) or certainly is one (`certain`)."""

    def __init__(self, plain: str, torn: bool = False, certain: bool = False):
        super().__init__(plain)
        self.plain, self.torn, self.certain = plain, torn, certain


# Confidence learning rates
_REINFORCE = 0.15   # consistent correction: conf += (1 - conf) * RATE
_CONTRADICT = 0.30  # contradicting correction: conf -= conf * RATE
_FLIP_BELOW = 0.25  # below this, the hierarchy flips and confidence resets


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
    """A folder only the owner's account can open (0700)."""
    if d.is_dir():
        return
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


# --------------------------------------------------------------- the store
class Conscience:
    _SHAPE = ("facts", "priorities", "goals", "corrections", "permissions",
              "actions", "observations", "opportunities")
    _LISTS = ("facts", "priorities", "goals", "corrections", "actions",
              "observations", "opportunities", "_notices")
    _CORE = ("owner", "_rev") + _SHAPE
    # A section that used to live in the store and now lives beside it.
    _LEGACY_ACCESS = "selfcloud_access_log"

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
        new = dict(obj)
        self._absorb_legacy(new)
        self.data.clear()
        self.data.update(new)
        for k, v in sections.items():
            self.data.setdefault(k, v)
        self._rev_seen = self._rev_of(new)

    def _adopt(self, raw: bytes, obj: dict, st: os.stat_result | None = None) -> None:
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
    def remember_fact(self, fact: str, category: str = "general") -> dict:
        entry = {"fact": fact.strip(), "category": category, "added": _now()}
        self.data["facts"].append(entry)
        self._save()
        return entry

    def forget_fact(self, contains: str) -> int:
        keep = [f for f in self.data["facts"]
                if contains.lower() not in f["fact"].lower()]
        removed = len(self.data["facts"]) - len(keep)
        if removed:
            # Pinned first, so a mistaken or injected forget can be undone
            # with 'Restore my memories' — however much is said afterwards.
            self.pin_snapshot("before forget")
            self.data["facts"] = keep
            self._save()
        return removed

    # ------------------------------------------------------------ priorities
    def _find_priority(self, context: str, a: str, b: str) -> dict | None:
        for p in self.data["priorities"]:
            if p["context"].lower() == context.lower() and {
                p["higher"].lower(),
                p["lower"].lower(),
            } == {a.lower(), b.lower()}:
                return p
        return None

    def set_priority(
        self, context: str, higher: str, lower: str, confidence: float = 0.6
    ) -> dict:
        """Explicitly declare a priority: in <context>, <higher> beats <lower>."""
        p = self._find_priority(context, higher, lower)
        if p:
            p.update(
                higher=higher, lower=lower,
                confidence=round(max(0.05, min(0.99, confidence)), 2),
                updated=_now(),
            )
        else:
            p = {
                "context": context, "higher": higher, "lower": lower,
                "confidence": round(max(0.05, min(0.99, confidence)), 2),
                "evidence": 1, "updated": _now(),
            }
            self.data["priorities"].append(p)
        self._save()
        return p

    def record_correction(
        self, context: str, suggested: str, chosen: str,
        inferred_higher: str, inferred_lower: str,
    ) -> dict:
        """The heart of the conscience: the user overrode a recommendation.

        Learn WHY — which value they were protecting — and update the
        hierarchy's confidence accordingly.
        """
        self.data["corrections"].append({
            "context": context, "suggested": suggested, "chosen": chosen,
            "inferred": f"{inferred_higher} > {inferred_lower}", "added": _now(),
            "ts": time.time(),
        })

        p = self._find_priority(context, inferred_higher, inferred_lower)
        if p is None:
            p = self.set_priority(context, inferred_higher, inferred_lower, 0.55)
            p["evidence"] = 1
        elif p["higher"].lower() == inferred_higher.lower():
            # consistent evidence → reinforce
            p["confidence"] = round(p["confidence"] + (1 - p["confidence"]) * _REINFORCE, 2)
            p["evidence"] += 1
            p["updated"] = _now()
        else:
            # contradiction → erode; flip if it collapses
            p["confidence"] = round(p["confidence"] * (1 - _CONTRADICT), 2)
            p["evidence"] += 1
            p["updated"] = _now()
            if p["confidence"] < _FLIP_BELOW:
                p["higher"], p["lower"] = inferred_higher, inferred_lower
                p["confidence"] = 0.5
        self._save()
        return p

    def priorities_for(self, context: str | None = None) -> list[dict]:
        ps = self.data["priorities"]
        if context:
            ps = [
                p for p in ps
                if context.lower() in p["context"].lower()
                or p["context"].lower() in ("any", "all", "general")
            ]
        return sorted(ps, key=lambda p: -p["confidence"])

    # ------------------------------------------------------------ goals
    def add_goal(self, goal: str) -> dict:
        entry = {"goal": goal.strip(), "added": _now(), "active": True}
        self.data["goals"].append(entry)
        self._save()
        return entry

    def close_goal(self, contains: str) -> int:
        n = 0
        for g in self.data["goals"]:
            if g["active"] and contains.lower() in g["goal"].lower():
                g["active"] = False
                n += 1
        self._save()
        return n

    # ------------------------------------------------------------ operational AI
    # The Act tier, enforced in code. Jefferey can never widen his own
    # authority: permissions change only here, at the user's explicit word,
    # and every grant, denial, and act lands in the owned log.

    LEVELS = ("observe", "recommend", "act")

    def set_permission(self, category: str, level: str, cap: float | None = None) -> dict:
        """User-granted authority for a category of action. 'act' may carry a
        spending cap; anything above it is denied regardless of level."""
        if level not in self.LEVELS:
            raise ValueError(f"level must be one of {self.LEVELS}")
        entry = {"level": level, "cap": cap, "updated": _now()}
        self.data["permissions"][category.lower().strip()] = entry
        self.data["actions"].append({
            "category": category.lower().strip(),
            "description": f"permission set to '{level}'"
                           + (f" with cap {cap}" if cap is not None else ""),
            "amount": None, "outcome": "permission_change",
            "added": _now(), "ts": time.time(),
        })
        self._save()
        return {"category": category.lower().strip(), **entry}

    def permission_for(self, category: str) -> dict:
        """Default is 'recommend': watch, learn, bring options — never act."""
        return self.data["permissions"].get(
            category.lower().strip(), {"level": "recommend", "cap": None}
        )

    def authorize_action(self, category: str, description: str,
                         amount: float | None = None) -> dict:
        """THE gate. Called before any real-world act. Denials are logged too —
        an auditable trail of what Jefferey wanted to do but wasn't allowed."""
        perm = self.permission_for(category)
        if perm["level"] != "act":
            verdict = {
                "allowed": False,
                "reason": (
                    f"'{category}' is at level '{perm['level']}' — recommend it "
                    "to the user instead; only they can raise the level."
                ),
                **perm,
            }
        elif amount is not None and perm.get("cap") is not None and amount > perm["cap"]:
            verdict = {
                "allowed": False,
                "reason": f"amount {amount} exceeds the user's cap of {perm['cap']} "
                          f"for '{category}' — ask them first.",
                **perm,
            }
        else:
            verdict = {"allowed": True, "reason": "within granted authority", **perm}
        if not verdict["allowed"]:
            self.data["actions"].append({
                "category": category.lower().strip(), "description": description,
                "amount": amount, "outcome": f"denied: {verdict['reason']}",
                "added": _now(), "ts": time.time(),
            })
            self._save()
        return verdict

    def log_action(self, category: str, description: str, outcome: str,
                   amount: float | None = None) -> dict:
        """Every executed act is written down. No silent actions, ever."""
        entry = {
            "category": category.lower().strip(), "description": description,
            "amount": amount, "outcome": outcome, "added": _now(), "ts": time.time(),
        }
        self.data["actions"].append(entry)
        self._save()
        return entry

    def action_log(self, limit: int = 20) -> list[dict]:
        return self.data["actions"][-limit:][::-1]

    # ------------------------------------------------------------ opportunity engine
    # "What can I do today to make this person's life better?" — observations
    # come in, opportunities get scored against THEIR priorities, and only
    # what clears the bar earns the right to interrupt.

    def log_observation(self, note: str, category: str = "general") -> dict:
        entry = {"note": note.strip(), "category": category,
                 "added": _now(), "ts": time.time()}
        self.data["observations"].append(entry)
        self._save()
        return entry

    def record_opportunity(self, what: str, value_estimate: str = "",
                           aligns_with: str = "", advances_goal: str = "",
                           reduces_risk: bool = False, urgency: float = 0.5) -> dict:
        """Score an opportunity by the spec's questions: does it align with
        their priorities, advance a goal, reduce a risk, and is it urgent?
        >= 0.75 earns an interrupt; >= 0.40 waits for the daily brief;
        below that it holds."""
        urgency = max(0.0, min(1.0, urgency))
        score = round(
            0.20
            + (0.25 if aligns_with.strip() else 0)
            + (0.20 if advances_goal.strip() else 0)
            + (0.15 if reduces_risk else 0)
            + 0.20 * urgency,
            2,
        )
        status = "interrupt" if score >= 0.75 else "brief" if score >= 0.40 else "hold"
        entry = {
            "what": what.strip(), "value_estimate": value_estimate,
            "aligns_with": aligns_with, "advances_goal": advances_goal,
            "reduces_risk": reduces_risk, "urgency": urgency,
            "score": score, "status": status, "resolved": False,
            "added": _now(), "ts": time.time(),
        }
        self.data["opportunities"].append(entry)
        self._save()
        return entry

    def pending_opportunities(self) -> list[dict]:
        return sorted(
            [o for o in self.data["opportunities"] if not o["resolved"]],
            key=lambda o: -o["score"],
        )

    def resolve_opportunity(self, contains: str, outcome: str = "done") -> int:
        n = 0
        for o in self.data["opportunities"]:
            if not o["resolved"] and contains.lower() in o["what"].lower():
                o["resolved"] = True
                o["outcome"] = outcome
                n += 1
        self._save()
        return n

    def orb_state(self) -> dict:
        """The predictive cycle: the orb's mood is the engine's real state,
        so the user reads Jefferey like a face."""
        now = time.time()
        pending = self.pending_opportunities()
        recent_corr = any(
            c.get("ts", 0) > now - 48 * 3600 for c in self.data["corrections"]
        )
        if any(o["reduces_risk"] and o["status"] == "interrupt" for o in pending):
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
        """One screen: what he noticed, what he suggests, what he did."""
        return {
            "orb": self.orb_state(),
            "active_goals": [g["goal"] for g in self.data["goals"] if g["active"]],
            "opportunities": self.pending_opportunities()[:10],
            "recent_actions": self.action_log(10),
            "recent_observations": self.data["observations"][-5:][::-1],
            "corrections_learned_from": len(self.data["corrections"]),
            # a recovery, a restore, a change made by hand: the owner is told
            "notices": self.notices(),
        }

    # ------------------------------------------------------------ views
    def snapshot(self) -> dict:
        """Everything the reasoning engine may see. The user owns all of it."""
        return {
            "owner": self.data.get("owner"),
            "priorities": sorted(self.data["priorities"], key=lambda p: -p["confidence"]),
            "facts": self.data["facts"],
            "active_goals": [g for g in self.data["goals"] if g["active"]],
            "corrections_learned_from": len(self.data["corrections"]),
            "notices": self.notices(),
            "store_path": str(self.path),
        }

    def explain_basis(self, topic: str) -> dict:
        """The grounding for a recommendation: which of the USER'S OWN values
        apply to this topic. Every recommendation must be explainable in
        these terms — never hidden incentives."""
        relevant_p = [
            p for p in self.data["priorities"]
            if topic.lower() in p["context"].lower()
            or p["context"].lower() in topic.lower()
            or p["context"].lower() in ("any", "all", "general")
        ]
        relevant_f = [
            f for f in self.data["facts"] if topic.lower() in f["fact"].lower()
        ]
        return {
            "topic": topic,
            "priorities": sorted(relevant_p, key=lambda p: -p["confidence"]),
            "facts": relevant_f,
            "rule": (
                "Explain the recommendation strictly in terms of these priorities "
                "and facts. If confidence is low, say so and ask. If nothing is "
                "relevant, say you don't know this person's values here yet."
            ),
        }


# ------------------------------------------------------------ the owner's view
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

    if a.cmd in (None, "check"):
        h = health(path)
        print("  " + h["plain"])
        return {"needs_restoring": 1, "will_recover": 2, "recovered": 2}.get(h["status"], 0)

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
        if answer.strip().lower() not in ("y", "yes"):
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
