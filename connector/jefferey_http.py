"""
JEFFEREY Agent Connector — HTTP server (the GPT side)
=====================================================

The same owned conscience the MCP connector serves to Claude, exposed over
HTTP for engines that speak Actions instead of MCP — most importantly
**custom GPTs**. One conscience file, many engines: this is the other half
of build priority 03.

Run:
    pip install fastapi uvicorn
    python connector/jefferey_http.py            # http://127.0.0.1:8377

    JEFFEREY_HTTP_TOKEN=...   bearer token (auto-generated + printed if unset)
    JEFFEREY_PUBLIC_URL=...   public https URL (needed for GPT Actions import)
    JEFFEREY_HTTP_PORT=8377   port override

Wire up a custom GPT (chatgpt.com → Create a GPT):
    1. Instructions: paste connector/directives.md, plus one line —
       "Call GET /directives and GET /conscience at the start of every chat."
    2. Actions → Import from URL: <JEFFEREY_PUBLIC_URL>/openapi.json
       (expose your machine with a tunnel, e.g. `cloudflared tunnel` or
       `ngrok http 8377`, or host this file on any small server)
    3. Authentication: API Key → Bearer → the token this server prints.
    4. Talk to it. Override a recommendation. Watch it learn you —
       into the SAME conscience.json Jefferey uses on Claude.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
from conscience import Conscience

conscience = Conscience()
DIRECTIVES = (Path(__file__).parent / "directives.md").read_text()

TOKEN = os.environ.get("JEFFEREY_HTTP_TOKEN") or secrets.token_urlsafe(24)
PUBLIC_URL = os.environ.get("JEFFEREY_PUBLIC_URL", "").rstrip("/")
PORT = int(os.environ.get("JEFFEREY_HTTP_PORT", "8377"))


async def require_owner(request: Request) -> None:
    """Every byte in the store is personal. No token, no access."""
    auth = request.headers.get("authorization", "")
    if not secrets.compare_digest(auth, f"Bearer {TOKEN}"):
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")


app = FastAPI(
    title="JEFFEREY Agent Connector",
    version="1.0",
    description=(
        "JEFFEREY's owned conscience over HTTP. The host model is the rented, "
        "disposable reasoning engine; this store — and the person it "
        "represents — persist. Call GET /directives first and BE Jefferey."
    ),
    servers=[{"url": PUBLIC_URL}] if PUBLIC_URL else None,
    dependencies=[Depends(require_owner)],
)


# ---------------------------------------------------------------- identity
@app.get("/directives", operation_id="get_directives")
def get_directives() -> dict:
    """Load the Jefferey Directive Pack: the identity, mission, and operating
    rules the host model must adopt to BE Jefferey. Call this first in every
    session, then follow it for the rest of the conversation."""
    return {"directives": DIRECTIVES}


@app.get("/conscience", operation_id="get_conscience")
def get_conscience() -> dict:
    """Read the full conscience: the user's priority hierarchy (with
    confidence scores), remembered facts, active goals, and how many
    corrections Jefferey has learned from. The user owns every byte."""
    return conscience.snapshot()


# ---------------------------------------------------------------- learning
class CorrectionIn(BaseModel):
    context: str = Field(description="e.g. 'travel', 'phone plan'")
    what_was_suggested: str
    what_user_chose: str
    value_protected: str = Field(description="e.g. 'reliability'")
    value_traded_away: str = Field(description="e.g. 'lowest price'")


@app.post("/corrections", operation_id="record_correction")
def record_correction(c: CorrectionIn) -> dict:
    """THE core learning act. The user overrode a recommendation — learn WHY.
    Record which value they were protecting and which they traded away in
    this context. Consistent evidence raises confidence; contradictions erode
    and can flip the hierarchy. Tell the user what you learned and the
    confidence you now hold."""
    return conscience.record_correction(
        c.context, c.what_was_suggested, c.what_user_chose,
        c.value_protected, c.value_traded_away,
    )


class PriorityIn(BaseModel):
    context: str
    higher: str
    lower: str
    confidence: float = 0.6


@app.post("/priorities", operation_id="set_priority")
def set_priority(p: PriorityIn) -> dict:
    """The user explicitly stated a priority (e.g. context='travel',
    higher='direct flights', lower='saving money'). Store it with the given
    confidence (0-1). Use record_correction instead when learning from an
    override rather than an explicit statement."""
    return conscience.set_priority(p.context, p.higher, p.lower, p.confidence)


class FactIn(BaseModel):
    fact: str
    category: str = "general"


@app.post("/facts", operation_id="remember_fact")
def remember_fact(f: FactIn) -> dict:
    """Remember a durable FACT about the user (people, dates, situations,
    constraints). Facts are stored separately from values — never mix the
    two. Ask before remembering anything sensitive."""
    return conscience.remember_fact(f.fact, f.category)


@app.delete("/facts", operation_id="forget")
def forget(contains: str) -> dict:
    """Delete every remembered fact containing this text. The user's right
    to erase is absolute — never argue, always confirm what was removed."""
    return {"removed_facts": conscience.forget_fact(contains)}


# ---------------------------------------------------------------- representing
@app.get("/basis", operation_id="explain_basis")
def explain_basis(topic: str) -> dict:
    """Before recommending anything, fetch the user's OWN priorities and
    facts relevant to this topic. Ground the recommendation and its
    explanation strictly in what this returns — never hidden incentives.
    If it returns nothing relevant, say you don't yet know their values
    here, and ask."""
    return conscience.explain_basis(topic)


@app.get("/priorities", operation_id="priorities_for")
def priorities_for(context: str = "") -> list:
    """List the user's learned priority hierarchy, highest confidence first,
    optionally filtered to a context (e.g. 'travel', 'money', 'family')."""
    return conscience.priorities_for(context or None)


# ---------------------------------------------------------------- goals
class GoalIn(BaseModel):
    goal: str


@app.post("/goals", operation_id="add_goal")
def add_goal(g: GoalIn) -> dict:
    """Register a long-term goal the user has approved. Goals drive the
    Opportunity Engine: what can be done today to move these forward,
    within permissions."""
    return conscience.add_goal(g.goal)


@app.delete("/goals", operation_id="close_goal")
def close_goal(contains: str) -> dict:
    """Mark active goals containing this text as done/retired."""
    return {"closed": conscience.close_goal(contains)}


# ---------------------------------------------------------------- operational AI
class PermissionIn(BaseModel):
    category: str
    level: str = Field(description="'observe', 'recommend' (default), or 'act'")
    cap: float | None = Field(default=None, description="spending cap for 'act'")


@app.post("/permissions", operation_id="set_permission")
def set_permission(p: PermissionIn) -> dict:
    """ONLY when the user explicitly grants or changes authority, in their
    own words. Jefferey never expands his own permissions."""
    try:
        return conscience.set_permission(p.category, p.level, p.cap)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class ActionAskIn(BaseModel):
    category: str
    description: str
    amount: float | None = None


@app.post("/actions/authorize", operation_id="authorize_action")
def authorize_action(a: ActionAskIn) -> dict:
    """THE gate. Call before doing anything in the real world on the user's
    behalf. If denied, recommend instead — only the user can raise the
    level. Denials are logged."""
    return conscience.authorize_action(a.category, a.description, a.amount)


class ActionLogIn(BaseModel):
    category: str
    description: str
    outcome: str
    amount: float | None = None


@app.post("/actions", operation_id="log_action")
def log_action(a: ActionLogIn) -> dict:
    """Write down an act just performed on the user's behalf. No silent
    actions, ever."""
    return conscience.log_action(a.category, a.description, a.outcome, a.amount)


@app.get("/actions", operation_id="action_log")
def action_log(limit: int = 20) -> list:
    """The audit trail: recent acts, denials, and permission changes,
    newest first."""
    return conscience.action_log(limit)


# ---------------------------------------------------------------- opportunity engine
class ObservationIn(BaseModel):
    note: str
    category: str = "general"


@app.post("/observations", operation_id="log_observation")
def log_observation(o: ObservationIn) -> dict:
    """Note something observed that might matter later. Observations feed
    the Opportunity Engine."""
    return conscience.log_observation(o.note, o.category)


class OpportunityIn(BaseModel):
    what: str
    value_estimate: str = ""
    aligns_with: str = Field(default="", description="which learned priority this serves")
    advances_goal: str = ""
    reduces_risk: bool = False
    urgency: float = 0.5


@app.post("/opportunities", operation_id="record_opportunity")
def record_opportunity(o: OpportunityIn) -> dict:
    """Score a way to make the user's life better against THEIR priorities.
    Returns the score and whether it earns an interrupt (>=0.75), waits for
    the daily brief (>=0.40), or holds. Only interrupt when it says to."""
    return conscience.record_opportunity(
        o.what, o.value_estimate, o.aligns_with, o.advances_goal,
        o.reduces_risk, o.urgency,
    )


@app.delete("/opportunities", operation_id="resolve_opportunity")
def resolve_opportunity(contains: str, outcome: str = "done") -> dict:
    """Close pending opportunities containing this text."""
    return {"resolved": conscience.resolve_opportunity(contains, outcome)}


@app.get("/brief", operation_id="daily_brief")
def daily_brief() -> dict:
    """One screen: orb mood, active goals, ranked opportunities, recent
    actions and observations."""
    return conscience.daily_brief()


@app.get("/orb", operation_id="orb_state")
def orb_state() -> dict:
    """The predictive cycle: the mood the orb should show right now, and why."""
    return conscience.orb_state()


if __name__ == "__main__":
    import uvicorn

    print("JEFFEREY HTTP connector — one conscience, many engines")
    print(f"  store : {conscience.path}")
    print(f"  local : http://127.0.0.1:{PORT}   (openapi: /openapi.json)")
    if PUBLIC_URL:
        print(f"  public: {PUBLIC_URL}")
    else:
        print("  public: set JEFFEREY_PUBLIC_URL before importing into GPT Actions")
    if "JEFFEREY_HTTP_TOKEN" not in os.environ:
        print(f"  token : {TOKEN}   (generated — set JEFFEREY_HTTP_TOKEN to pin it)")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
