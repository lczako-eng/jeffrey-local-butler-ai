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
            "permissions": {},  # {category: {level, cap, updated}} — Operational AI
            "actions": [],      # [{category, description, amount, outcome, added, ts}]
            "observations": [],   # [{note, category, added, ts}] — Opportunity Engine
            "opportunities": [],  # [{what, ..., score, status, added, ts}]
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
