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
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    import fcntl  # POSIX only; Windows falls back to no cross-process lock
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

DEFAULT_STORE = Path(
    os.environ.get("JEFFEREY_CONSCIENCE_PATH", "~/.jefferey/conscience.json")
).expanduser()

# How many previous versions of the store to keep beside it. Twenty is a few
# hundred kilobytes and buys back weeks of accidents.
HISTORY_KEEP = 20


class ConscienceCorrupt(RuntimeError):
    """The store on disk is unreadable and no snapshot could replace it.

    Raised instead of silently starting from an empty conscience — losing a
    life quietly is worse than refusing to start loudly.
    """


class ConscienceConflict(RuntimeError):
    """Another process wrote to this conscience since we loaded it.

    Refusing the write is the point: two surfaces each holding the whole
    store in memory would otherwise overwrite each other's changes.
    """

# Confidence learning rates
_REINFORCE = 0.15   # consistent correction: conf += (1 - conf) * RATE
_CONTRADICT = 0.30  # contradicting correction: conf -= conf * RATE
_FLIP_BELOW = 0.25  # below this, the hierarchy flips and confidence resets


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Conscience:
    def __init__(self, path: Path | str = DEFAULT_STORE):
        self.path = Path(path).expanduser()
        self.data: dict[str, Any] = {
            "owner": None,
            "facts": [],        # [{fact, category, added}]
            "priorities": [],   # [{context, higher, lower, confidence, evidence, updated}]
            "goals": [],        # [{goal, added, active}]
            "corrections": [],  # [{context, suggested, chosen, inferred, added}]
            "permissions": {},  # {category: {level, cap, updated}} — Operational AI
            "actions": [],      # [{category, description, amount, outcome, added, ts}]
            "observations": [],   # [{note, category, added, ts}] — Opportunity Engine
            "opportunities": [],  # [{what, ..., score, status, added, ts}]
            "_rev": 0,          # bumped on every write; guards against clobber
        }
        self._rev_seen = 0
        self._load()

    # ------------------------------------------------------------ storage
    #
    # Durability rules, because the product's headline feature is a switch
    # that cuts power:
    #   * every write is atomic  — temp file, fsync, os.replace, fsync dir;
    #   * every write is locked  — one writer at a time across processes;
    #   * every write is versioned — the previous copy lands in history/;
    #   * a corrupt store recovers from history, or REFUSES TO START.
    # A truncated file must never quietly become an empty conscience.

    @property
    def history_dir(self) -> Path:
        return self.path.parent / (self.path.stem + ".history")

    @property
    def _lock_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".lock")

    def _lock(self):
        """Exclusive cross-process lock, as a context manager."""
        class _Lock:
            def __init__(self, path):
                self.path, self.fh = path, None

            def __enter__(self):
                if fcntl is None:
                    return self
                self.path.parent.mkdir(parents=True, exist_ok=True)
                # O_NOFOLLOW so a symlink here cannot aim the lock at one of
                # the owner's files, and no O_TRUNC so opening never empties
                # whatever is there.
                fd = os.open(self.path,
                             os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
                self.fh = os.fdopen(fd, "r+")
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX)
                return self

            def __exit__(self, *exc):
                if self.fh is not None:
                    fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
                    self.fh.close()
                return False

        return _Lock(self._lock_path)

    @staticmethod
    def _snap_rev(p: Path) -> int:
        """The revision baked into a snapshot's name. Ordering by FILENAME
        would order by local clock, so a timezone change or the hour that
        repeats every autumn could make recovery restore an older life and
        pruning delete the newest one."""
        try:
            return int(p.stem.rsplit("-", 1)[-1])
        except ValueError:
            return -1

    def _snapshots(self) -> list[Path]:
        if not self.history_dir.exists():
            return []
        return sorted(self.history_dir.glob("*.json"),
                      key=lambda p: (self._snap_rev(p), p.stat().st_mtime),
                      reverse=True)

    _SHAPE = ("facts", "priorities", "goals", "corrections", "permissions",
              "actions", "observations", "opportunities")

    @classmethod
    def _validate(cls, obj) -> dict:
        """`[]`, `{}` and `{"facts": []}` all parse as JSON and none of them is
        a life. Anything that is not recognisably a conscience is treated as
        unreadable, so it routes to recovery instead of quietly replacing one."""
        if not isinstance(obj, dict):
            raise ValueError(f"not a conscience: top level is {type(obj).__name__}")
        if isinstance(obj.get("_rev"), int):
            return obj
        if sum(1 for k in cls._SHAPE if k in obj) >= 3:
            return obj                       # a store from before _rev existed
        raise ValueError("not a conscience: no _rev and too few known fields")

    def _load(self) -> None:
        corrupt_marker = self.path.with_suffix(self.path.suffix + ".corrupt")
        if not self.path.exists():
            # A missing store is normal on the very first run — and is a
            # catastrophe if there is evidence a life was here. Do not guess.
            if self._snapshots() or corrupt_marker.exists():
                parsed = self._recover(reason="the store is gone")
                self.data.update(parsed)
                self._rev_seen = int(self.data.get("_rev", 0))
                self._write(self.data)       # put it back before anything else
            return
        raw = self.path.read_text()
        recovered = False
        try:
            parsed = json.loads(raw) if raw.strip() else None
            if parsed is None:
                raise ValueError("store is empty")
            self._validate(parsed)
        except Exception as exc:
            parsed = self._recover(reason=str(exc))
            recovered = True
        self.data.update(parsed)
        self._rev_seen = int(self.data.get("_rev", 0))
        if recovered:
            # Without this the recovery lives only in memory: close the app
            # and the NEXT launch finds the same broken file, or nothing at
            # all, and starts an empty life with no warning.
            self._write(self.data)

    def _recover(self, reason: str) -> dict:
        """The live store is unreadable. Try the newest good snapshot; if there
        isn't one, stop — do not start from an empty conscience."""
        for snap in self._snapshots():
            try:
                parsed = json.loads(snap.read_text())
            except Exception:
                continue
            broken = self.path.with_suffix(self.path.suffix + ".corrupt")
            try:
                self.path.replace(broken)
            except OSError:
                broken = None
            print(
                f"\n  ⚠  {self.path} was unreadable ({reason}).\n"
                f"     Recovered from snapshot {snap.name}."
                + (f"\n     The damaged file is kept at {broken}." if broken else "")
                + "\n     Check what you may have said since that snapshot.\n",
                file=sys.stderr,
            )
            return parsed
        if os.environ.get("JEFFEREY_ALLOW_RESET") == "1":
            print(f"\n  ⚠  {self.path} unreadable ({reason}); "
                  f"JEFFEREY_ALLOW_RESET=1 — starting empty.\n", file=sys.stderr)
            return {}
        raise ConscienceCorrupt(
            f"{self.path} is unreadable ({reason}) and no usable snapshot exists "
            f"in {self.history_dir}.\n"
            "Refusing to start from an empty conscience — that would silently "
            "erase everything this person told Jefferey.\n"
            "Restore the file from your backup, or, if you truly mean to start "
            "over, run again with JEFFEREY_ALLOW_RESET=1."
        )

    def _on_disk_rev(self) -> int:
        """The revision actually on disk.

        Returning our own revision when the file cannot be read would make the
        anti-clobber guard a no-op in precisely the state where it matters —
        the store replaced, truncated or deleted under us.
        """
        if not self.path.exists():
            if self._rev_seen == 0 and not self._snapshots():
                return 0                     # the very first write: nothing lost
            raise ConscienceConflict(
                f"{self.path} has disappeared since this session loaded it "
                f"(revision {self._rev_seen}). Refusing to write over whatever "
                f"replaced it. Restart so the store is re-read or recovered.")
        try:
            return int(self._validate(json.loads(self.path.read_text()))
                       .get("_rev", 0))
        except ConscienceConflict:
            raise
        except Exception as exc:
            raise ConscienceConflict(
                f"{self.path} is no longer readable ({exc}). Nothing was "
                f"written. Restart so it can be recovered from history.")

    def _archive(self) -> None:
        """Snapshot the store as it now stands on disk.

        Taken *after* the atomic replace, not before: a snapshot that lagged
        one write behind would lose the newest change in exactly the case it
        exists for — recovering a file torn by a power cut.
        """
        if not self.path.exists():
            return
        self.history_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        dest = self.history_dir / f"{self.path.stem}-{stamp}-{self._rev_seen:06d}.json"
        try:
            dest.write_bytes(self.path.read_bytes())
        except OSError:
            return
        for old in self._snapshots()[HISTORY_KEEP:]:
            old.unlink(missing_ok=True)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock():
            disk_rev = self._on_disk_rev()
            if disk_rev != self._rev_seen:
                raise ConscienceConflict(
                    f"{self.path} was written by another Jefferey "
                    f"(disk revision {disk_rev}, this session loaded {self._rev_seen}). "
                    "Nothing was written, so neither set of changes is lost. "
                    "Restart this surface so it reloads the conscience."
                )
            self.data["_rev"] = self._rev_seen + 1
            self._write(self.data)
            self._rev_seen = self.data["_rev"]
            self._archive()

    def _write(self, payload: dict) -> None:
        """One atomic, durable write. Temp file, fsync, rename, fsync dir."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2, ensure_ascii=False))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)              # readers see old or new, never half
        try:                                     # make the rename itself durable
            dir_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except (OSError, AttributeError):
            pass                                 # not all platforms allow this

    # ------------------------------------------------------------ recovery
    def snapshots(self) -> list[dict]:
        """What versions of this conscience are recoverable, newest first."""
        return [{"file": str(p), "saved": time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))}
            for p in self._snapshots()]

    # ------------------------------------------------------------ facts
    def remember_fact(self, fact: str, category: str = "general") -> dict:
        entry = {"fact": fact.strip(), "category": category, "added": _now()}
        self.data["facts"].append(entry)
        self._save()
        return entry

    def forget_fact(self, contains: str) -> int:
        before = len(self.data["facts"])
        self.data["facts"] = [
            f for f in self.data["facts"] if contains.lower() not in f["fact"].lower()
        ]
        self._save()
        return before - len(self.data["facts"])

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
