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
import time
from pathlib import Path
from typing import Any

DEFAULT_STORE = Path(
    os.environ.get("JEFFEREY_CONSCIENCE_PATH", "~/.jefferey/conscience.json")
).expanduser()

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
        }
        self._load()

    # ------------------------------------------------------------ storage
    def _load(self) -> None:
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except Exception:
                pass  # a corrupt store must never crash the conscience

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))

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
