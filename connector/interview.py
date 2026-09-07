"""
How the Digital Conscience gets built — the quiet interview
===========================================================

You cannot hand someone a form and get a person out of it. Nobody fills in
"who are you" on a Tuesday. A conscience that genuinely understands someone
has to be **drawn out** — by the AI, in conversation, one question at a time,
over months, at moments that don't feel like an interview at all.

That is what this module is: a ladder of questions Jefferey earns the right
to ask.

**Depth is earned, not given.** Every question has a depth:

    1  warm      easy, pleasant, answerable in one line
    2  shape     the outline of a life: work, place, routine, people
    3  values    turning points, regrets, what they'd defend
    4  legacy    mortality, meaning, what should outlive them

Jefferey starts at depth 1 with a stranger. Depth rises only as the
relationship earns it — measured by what the person has actually chosen to
share and correct, never by how many days have passed. You do not ask
somebody what they want said at their funeral in week one.

**The rules that keep it human:**

- One question at a time. Never a battery.
- Never twice. An asked question is retired whether or not it was answered.
- Never pressure. "Rather not" is a complete answer, recorded as such, and
  Jefferey moves on without a second attempt.
- Woven into conversation, not announced. The question is a thing a friend
  would say, not a field to complete.
- Everything the person says goes into THEIR store, under the visibility
  they choose, erasable forever after.
"""

from __future__ import annotations

import time

# The ladder. Each: (id, depth, domain, question, what it teaches Jefferey)
QUESTIONS: list[dict] = [
    # ---- depth 1: warm ------------------------------------------------
    dict(id="call_first", depth=1, domain="people",
         q="Who's the first person you'd call with good news?",
         learns="the closest relationship, without asking anything heavy"),
    dict(id="good_day", depth=1, domain="daily",
         q="What does a genuinely good day look like for you?",
         learns="what they actually optimize for, in their own words"),
    dict(id="pet_peeve", depth=1, domain="values",
         q="What's something small that drives you up the wall?",
         learns="friction to avoid on their behalf"),
    dict(id="hands_busy", depth=1, domain="joy",
         q="What do you do when you want to stop thinking for a while?",
         learns="how they rest — worth protecting in a calendar"),
    dict(id="how_address", depth=1, domain="voice",
         q="What should I call you?",
         learns="their name and the register of the relationship"),

    # ---- depth 2: the shape of a life ---------------------------------
    dict(id="household", depth=2, domain="people",
         q="Who's in your day-to-day life — who's around?",
         learns="the household, the people to notice and remember"),
    dict(id="work_life", depth=2, domain="work",
         q="What do you do, and is it what you meant to do?",
         learns="work, and whether it's a burden or an identity"),
    dict(id="place", depth=2, domain="daily",
         q="Where do you live, and is it home?",
         learns="place, and whether they're rooted or drifting"),
    dict(id="money_shape", depth=2, domain="money",
         q="Is money something you count carefully, or something you'd rather not think about?",
         learns="how to talk about cost — and how loudly to flag a charge"),
    dict(id="health_watch", depth=2, domain="health",
         q="Anything about your health I should keep an eye on for you?",
         learns="what to watch; ask permission before storing any of it"),
    dict(id="dates_matter", depth=2, domain="people",
         q="Any dates in the year that matter to you — ones you'd hate to miss?",
         learns="birthdays, anniversaries, the day someone died"),

    # ---- depth 3: values and turning points ---------------------------
    dict(id="turning_point", depth=3, domain="origins",
         q="What's a moment that changed the direction of your life?",
         learns="the story's spine — where they turned"),
    dict(id="proud_of", depth=3, domain="values",
         q="What are you proudest of that almost nobody knows about?",
         learns="what they value when nobody's watching"),
    dict(id="would_redo", depth=3, domain="values",
         q="Is there a decision you'd make differently now?",
         learns="a value learned the hard way — usually the strongest one"),
    dict(id="who_shaped", depth=3, domain="origins",
         q="Who shaped you most — and what did they teach you?",
         learns="inherited values, and a person who belongs in the story"),
    dict(id="worry_at_night", depth=3, domain="worry",
         q="What do you worry about, when it's quiet?",
         learns="what protection actually means for this person"),
    dict(id="defend", depth=3, domain="values",
         q="What would you defend even if it cost you?",
         learns="the top of the hierarchy — the value that outranks the rest"),

    # ---- depth 4: legacy ----------------------------------------------
    dict(id="said_about_you", depth=4, domain="legacy",
         q="If someone told your story in one sentence, what would you want it to say?",
         learns="the thesis of a life — the frame every other memory hangs on"),
    dict(id="who_should_know", depth=4, domain="legacy",
         q="Who should hear your story one day, and who shouldn't?",
         learns="the audience for `legacy` — inheritance, made explicit"),
    dict(id="unsaid", depth=4, domain="legacy",
         q="Is there anything you've never said out loud that you'd want written down?",
         learns="the thing people take with them by accident"),
    dict(id="care_later", depth=4, domain="worry",
         q="Have you thought about who looks out for you when you're older?",
         learns="the founder's own question — and the reason this exists"),
]

BY_ID = {q["id"]: q for q in QUESTIONS}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Interview:
    """Jefferey coming to understand a person, at the pace of a friendship."""

    def __init__(self, conscience, life=None):
        self.c = conscience
        self.life = life
        self.c.data.setdefault("asked", {})

    # ----------------------------------------------------------- readiness
    def trust(self) -> dict:
        """How much of themselves this person has chosen to share. Depth is
        gated on this — not on elapsed time, which earns nothing."""
        d = self.c.data
        answered = sum(1 for a in d.get("asked", {}).values() if a.get("answered"))
        signals = {
            "answers_given": answered,
            "moments_recorded": len(d.get("memories", [])),
            "people_recorded": len(d.get("people", [])),
            "corrections": len(d.get("corrections", [])),
            "facts": len(d.get("facts", [])),
        }
        score = (signals["answers_given"] * 2 + signals["moments_recorded"] * 2
                 + signals["people_recorded"] + signals["corrections"]
                 + signals["facts"])
        depth = 1 if score < 4 else 2 if score < 10 else 3 if score < 20 else 4
        return {
            "score": score, "signals": signals, "max_depth": depth,
            "meaning": {
                1: "You've just met. Keep it warm and light.",
                2: "They're sharing. You may ask about the shape of their life.",
                3: "There is a relationship here. Values and turning points are open.",
                4: "They trust you. You may ask what should outlive them — gently.",
            }[depth],
        }

    # ------------------------------------------------------------ the ask
    def next_question(self, domain: str = "") -> dict:
        """ONE question — the right one, right now. Never a list.

        Prefers a domain Jefferey is thin on, stays at or below the depth the
        relationship has earned, and never repeats one already asked.
        """
        asked = self.c.data.get("asked", {})
        t = self.trust()
        pool = [q for q in QUESTIONS
                if q["id"] not in asked and q["depth"] <= t["max_depth"]
                and (not domain or q["domain"] == domain.lower())]
        if not pool:
            deeper = [q for q in QUESTIONS if q["id"] not in asked]
            return {
                "question": None,
                "why": ("Nothing to ask at this depth yet — they haven't shared "
                        "enough for it to be earned." if deeper else
                        "You've asked everything on the ladder. From here, listen "
                        "and record what they offer unprompted."),
                "trust": t,
            }
        # thinnest domain first, then shallowest question
        counts: dict[str, int] = {}
        for a in asked.values():
            counts[a.get("domain", "")] = counts.get(a.get("domain", ""), 0) + 1
        pool.sort(key=lambda q: (counts.get(q["domain"], 0), q["depth"]))
        q = pool[0]
        return {
            "question": q["q"],
            "id": q["id"],
            "depth": q["depth"],
            "domain": q["domain"],
            "what_it_teaches_you": q["learns"],
            "trust": t,
            "how_to_ask": (
                "Ask this ONCE, woven into what you're already talking about — "
                "never announced as a question from a list, never alongside "
                "another. If they answer, call record_answer and thank them "
                "plainly. If they deflect or say they'd rather not, record it "
                "as declined and never raise it again. Their 'no' is a complete "
                "answer and costs them nothing."
            ),
        }

    def record_answer(self, question_id: str, answer: str = "",
                      declined: bool = False, visibility: str = "private") -> dict:
        """Keep what they said — in their store, under their visibility — and
        retire the question either way."""
        q = BY_ID.get(question_id)
        if not q:
            return {"error": f"unknown question '{question_id}'",
                    "known": sorted(BY_ID)[:10]}
        self.c.data.setdefault("asked", {})[question_id] = {
            "domain": q["domain"], "depth": q["depth"],
            "answered": bool(answer and not declined),
            "declined": bool(declined), "at": _now(),
        }
        self.c._save()
        if declined or not answer.strip():
            return {"recorded": "declined", "question": q["q"],
                    "rule": "Never ask this again. Don't circle back to it later."}
        stored = None
        if self.life is not None:
            stored = self.life.add_memory(
                answer.strip(), people="", tags=f"{q['domain']},interview",
                visibility=visibility if visibility in ("private", "family", "legacy")
                else "private")
        return {
            "recorded": "answered",
            "question": q["q"],
            "kept_as": stored,
            "next": (
                "Thank them in one line — no gushing. If their answer named a "
                "person, offer to remember them (add_person). If it revealed a "
                "value ranking, set_priority with modest confidence and say what "
                "you took from it, so they can correct you. Then let it go: one "
                "question, one moment."
            ),
        }

    # ----------------------------------------------------------- overview
    def progress(self) -> dict:
        """What Jefferey knows, what he's still missing, and what he has
        earned the right to ask."""
        asked = self.c.data.get("asked", {})
        answered = [k for k, v in asked.items() if v.get("answered")]
        declined = [k for k, v in asked.items() if v.get("declined")]
        t = self.trust()
        by_domain: dict[str, dict] = {}
        for q in QUESTIONS:
            d = by_domain.setdefault(q["domain"], {"asked": 0, "total": 0})
            d["total"] += 1
            if q["id"] in asked:
                d["asked"] += 1
        return {
            "answered": len(answered),
            "declined": len(declined),
            "remaining_at_this_depth": sum(
                1 for q in QUESTIONS
                if q["id"] not in asked and q["depth"] <= t["max_depth"]),
            "locked_deeper": sum(
                1 for q in QUESTIONS
                if q["id"] not in asked and q["depth"] > t["max_depth"]),
            "by_domain": by_domain,
            "trust": t,
            "rule": (
                "This is a friendship being built, not a dataset being filled. "
                "A person who answers nothing for a month is not a failure — "
                "be useful to them anyway, and the door opens on its own."
            ),
        }
