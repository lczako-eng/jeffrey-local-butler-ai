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
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
from conscience import Conscience
from representative import Representative
from guardian import Guardian
from life import Life
from selfcloud import SelfCloud
from interview import Interview
from rules import ConscienceRules
from reminisce import Reminisce
import access
import egress
from access import AccessDenied, OwnerOnly, gate, owner_only
from egress import EgressRefused, door

conscience = Conscience()
rep = Representative(conscience)
guard = Guardian(conscience)
life = Life(conscience)
cloud = SelfCloud(conscience)
interview = Interview(conscience, life)
rules = ConscienceRules(conscience)
album = Reminisce(conscience, life)
DIRECTIVES = (Path(__file__).parent / "directives.md").read_text()

TOKEN = os.environ.get("JEFFEREY_HTTP_TOKEN") or secrets.token_urlsafe(24)
PUBLIC_URL = os.environ.get("JEFFEREY_PUBLIC_URL", "").rstrip("/")
PORT = int(os.environ.get("JEFFEREY_HTTP_PORT", "8377"))


def _token_map() -> dict[str, str]:
    """token -> client. One process here legitimately serves several engines
    (a Custom GPT, a Claude session, a family member's app), so the token is
    not just a password — it says WHICH KEY the caller holds.

        JEFFEREY_HTTP_TOKENS="jefferey:s3cr3t,gpt-raw:other,family:third"

    With nothing set, the single JEFFEREY_HTTP_TOKEN maps to JEFFEREY_CLIENT
    (default `claude-raw` — the narrow key, per access.py)."""
    raw = os.environ.get("JEFFEREY_HTTP_TOKENS", "").strip()
    if not raw:
        return {TOKEN: os.environ.get("JEFFEREY_CLIENT", access.DEFAULT_CLIENT)}
    out: dict[str, str] = {}
    for pair in raw.split(","):
        if ":" not in pair:
            continue
        client, tok = pair.split(":", 1)
        if client.strip() and tok.strip():
            out[tok.strip()] = client.strip().lower()
    return out


TOKENS = _token_map()

# THE DOOR. A process-wide fallback identity; each authenticated request then
# rebinds to the client its own token names (require_owner, below). Nothing
# the model says can change either one.
access.bind(cloud)
access.provision(cloud, set(TOKENS.values()))

# THE EGRESS DOOR. Every route below is registered with `@door(app.…(…))`, so
# its result passes egress.release() — allowlisted, scanned, logged word for
# word — before it is serialised to the caller. There is no other path out.
egress.bind("http")


async def require_owner(request: Request) -> None:
    """Every byte in the store is personal. No token, no access — and the
    token decides which key you hold for the rest of this request."""
    auth = request.headers.get("authorization", "")
    for tok, client in TOKENS.items():
        if secrets.compare_digest(auth, f"Bearer {tok}"):
            access.use_client(client)   # per-request identity, not per-call
            return
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


@app.exception_handler(AccessDenied)
async def _denied(request: Request, exc: AccessDenied):
    """A refusal is an answer, not an error to route around."""
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(OwnerOnly)
async def _owner_only(request: Request, exc: OwnerOnly):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(EgressRefused)
async def _withheld(request: Request, exc: EgressRefused):
    """The door kept it — a secret handed in, or a result that may not leave.
    The detail names a field or a reason, never a value."""
    return JSONResponse(status_code=403, content={"detail": str(exc)})


# ---------------------------------------------------------------- identity
@door(app.get("/directives", operation_id="get_directives"))
def get_directives() -> dict:
    """Load the Jefferey Directive Pack: the identity, mission, and operating
    rules the host model must adopt to BE Jefferey. Call this first in every
    session, then follow it for the rest of the conversation."""
    return {"directives": DIRECTIVES}


@door(app.get("/conscience", operation_id="get_conscience"))
@gate("facts.read")
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


@door(app.post("/corrections", operation_id="record_correction"))
@gate("priorities.write")
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


@door(app.post("/priorities", operation_id="set_priority"))
@gate("priorities.write")
def set_priority(p: PriorityIn) -> dict:
    """The user explicitly stated a priority (e.g. context='travel',
    higher='direct flights', lower='saving money'). Store it with the given
    confidence (0-1). Use record_correction instead when learning from an
    override rather than an explicit statement."""
    return conscience.set_priority(p.context, p.higher, p.lower, p.confidence)


class FactIn(BaseModel):
    fact: str
    category: str = "general"


@door(app.post("/facts", operation_id="remember_fact"))
@gate("facts.write")
def remember_fact(f: FactIn) -> dict:
    """Remember a durable FACT about the user (people, dates, situations,
    constraints). Facts are stored separately from values — never mix the
    two. Ask before remembering anything sensitive."""
    return conscience.remember_fact(f.fact, f.category)


@door(app.delete("/facts", operation_id="forget"))
@gate("facts.write")
def forget(contains: str) -> dict:
    """Delete every remembered fact containing this text. The user's right
    to erase is absolute — never argue, always confirm what was removed."""
    return {"removed_facts": conscience.forget_fact(contains)}


# ---------------------------------------------------------------- representing
@door(app.get("/basis", operation_id="explain_basis"))
@gate("priorities.read")
def explain_basis(topic: str) -> dict:
    """Before recommending anything, fetch the user's OWN priorities and
    facts relevant to this topic. Ground the recommendation and its
    explanation strictly in what this returns — never hidden incentives.
    If it returns nothing relevant, say you don't yet know their values
    here, and ask."""
    return conscience.explain_basis(topic)


@door(app.get("/priorities", operation_id="priorities_for"))
@gate("priorities.read")
def priorities_for(context: str = "") -> list:
    """List the user's learned priority hierarchy, highest confidence first,
    optionally filtered to a context (e.g. 'travel', 'money', 'family')."""
    return conscience.priorities_for(context or None)


# ---------------------------------------------------------------- goals
class GoalIn(BaseModel):
    goal: str


@door(app.post("/goals", operation_id="add_goal"))
@gate("goals.write")
def add_goal(g: GoalIn) -> dict:
    """Register a long-term goal the user has approved. Goals drive the
    Opportunity Engine: what can be done today to move these forward,
    within permissions."""
    return conscience.add_goal(g.goal)


@door(app.delete("/goals", operation_id="close_goal"))
@gate("goals.write")
def close_goal(contains: str) -> dict:
    """Mark active goals containing this text as done/retired."""
    return {"closed": conscience.close_goal(contains)}


# ---------------------------------------------------------------- operational AI
class PermissionIn(BaseModel):
    category: str
    level: str = Field(description="'observe', 'recommend' (default), or 'act'")
    cap: float | None = Field(default=None, description="spending cap for 'act'")


@door(app.post("/permissions", operation_id="set_permission"))
@owner_only
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


@door(app.post("/actions/authorize", operation_id="authorize_action"))
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


@door(app.post("/actions", operation_id="log_action"))
@gate("facts.write")
def log_action(a: ActionLogIn) -> dict:
    """Write down an act just performed on the user's behalf. No silent
    actions, ever."""
    return conscience.log_action(a.category, a.description, a.outcome, a.amount)


@door(app.get("/actions", operation_id="action_log"))
@gate("facts.read")
def action_log(limit: int = 20) -> list:
    """The audit trail: recent acts, denials, and permission changes,
    newest first."""
    return conscience.action_log(limit)


# ---------------------------------------------------------------- opportunity engine
class ObservationIn(BaseModel):
    note: str
    category: str = "general"


@door(app.post("/observations", operation_id="log_observation"))
@gate("goals.write")
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


@door(app.post("/opportunities", operation_id="record_opportunity"))
@gate("goals.read")
def record_opportunity(o: OpportunityIn) -> dict:
    """Score a way to make the user's life better against THEIR priorities.
    Returns the score and whether it earns an interrupt (>=0.75), waits for
    the daily brief (>=0.40), or holds. Only interrupt when it says to."""
    return conscience.record_opportunity(
        o.what, o.value_estimate, o.aligns_with, o.advances_goal,
        o.reduces_risk, o.urgency,
    )


@door(app.delete("/opportunities", operation_id="resolve_opportunity"))
@gate("goals.write")
def resolve_opportunity(contains: str, outcome: str = "done") -> dict:
    """Close pending opportunities containing this text."""
    return {"resolved": conscience.resolve_opportunity(contains, outcome)}


@door(app.get("/brief", operation_id="daily_brief"))
@gate("facts.read")
def daily_brief() -> dict:
    """One screen: orb mood, active goals, ranked opportunities, recent
    actions and observations."""
    return conscience.daily_brief()


@door(app.get("/orb", operation_id="orb_state"))
def orb_state() -> dict:
    """The predictive cycle: the mood the orb should show right now, and why."""
    return conscience.orb_state()


# ---------------------------------------------------------------- representative
class TriageIn(BaseModel):
    sender: str = ""
    subject: str = ""
    body: str


@door(app.post("/triage", operation_id="triage_message"))
@gate("priorities.read")
def triage_message(t: TriageIn) -> dict:
    """Read an incoming message the way a good friend would: what does it
    want, does it matter by THIS person's priorities, and is anyone trying to
    take advantage of them? Returns a verdict, the predatory tactics spotted,
    amounts and deadlines, and the user's relevant values. Never reply, click,
    pay, or unsubscribe on their behalf without authorize_action."""
    return rep.triage_message(t.sender, t.subject, t.body)


class DraftIn(BaseModel):
    purpose: str
    recipient: str = ""


@door(app.post("/draft-guidance", operation_id="draft_guidance"))
@gate("priorities.read")
def draft_guidance(d: DraftIn) -> dict:
    """Call BEFORE writing anything in the user's name. Returns their voice,
    the priorities and facts that apply, who to sign as, and the hard limits.
    Sending requires authorize_action on 'correspondence'."""
    return rep.draft_guidance(d.purpose, d.recipient)


class FormIn(BaseModel):
    fields: list[str]


@door(app.post("/forms/fill", operation_id="fill_form"))
@gate("facts.read")
def fill_form(f: FormIn) -> dict:
    """Given a form's field labels, return what Jefferey can fill from the
    user's own profile and exactly what he cannot. He never guesses, and
    never fills sensitive identifiers — those go back to the user."""
    return rep.fill_form(f.fields)


@door(app.get("/vault", operation_id="vault_status"))
@gate("vault.names")
def vault_status() -> dict:
    """Where the user's secrets live (their platform keychain) and which
    exist, by NAME only. You never see a value and must never ask. Use a
    secret on a form with the token 'vault:<name>' — resolved locally."""
    return rep.vault_status()


class ProfileIn(BaseModel):
    field: str
    value: str


@door(app.post("/profile", operation_id="set_profile_field"))
@gate("facts.write")
def set_profile_field(p: ProfileIn) -> dict:
    """Store one identity detail Jefferey may reuse on forms. Sensitive
    identifiers (SIN/SSN, cards, PINs) are refused by design."""
    return rep.set_profile_field(p.field, p.value)


@door(app.get("/profile", operation_id="get_profile"))
@gate("facts.read")
def get_profile() -> dict:
    """Everything Jefferey can put on a form for this user. They own all of it."""
    return rep.get_profile()


@door(app.delete("/profile", operation_id="forget_profile_field"))
@gate("facts.write")
def forget_profile_field(field: str) -> dict:
    """Delete one profile detail. The right to erase is absolute."""
    return rep.forget_profile_field(field)


# ---------------------------------------------------------------- guardian
class ExpectIn(BaseModel):
    merchant: str
    amount: float
    cadence: str = "monthly"
    authorized_recurring: bool = True
    note: str = ""


@door(app.post("/charges/expected", operation_id="expect_charge"))
@gate("money.write")
def expect_charge(e: ExpectIn) -> dict:
    """Register a charge the user has actually agreed to. Anything not in
    this register becomes a question later."""
    return guard.expect_charge(e.merchant, e.amount, e.cadence,
                               e.authorized_recurring, e.note)


class CancelIn(BaseModel):
    merchant: str
    on: str = ""


@door(app.post("/charges/cancelled", operation_id="mark_cancelled"))
@gate("money.write")
def mark_cancelled(c: CancelIn) -> dict:
    """Record that the user cancelled something — any charge after this date
    is unauthorized."""
    return guard.mark_cancelled(c.merchant, c.on)


class ChargeIn(BaseModel):
    merchant: str
    amount: float
    date: str = ""


@door(app.post("/charges/check", operation_id="check_charge"))
@gate("money.read")
def check_charge(c: ChargeIn) -> dict:
    """Hold one charge up against what the user agreed to. Returns a verdict
    in plain words with the dollars at stake."""
    return guard.check_charge(c.merchant, c.amount, c.date)


class StatementIn(BaseModel):
    charges: list[ChargeIn]


@door(app.post("/charges/review", operation_id="review_statement"))
@gate("money.read")
def review_statement(s: StatementIn) -> dict:
    """Run a whole statement through at once and report the total at stake."""
    return guard.review_statement([c.model_dump() for c in s.charges])


@door(app.get("/charges/expected", operation_id="expected_charges"))
@gate("money.read")
def expected_charges() -> list:
    """What the user has agreed to pay, and what they've cancelled."""
    return guard.expected_charges()


@door(app.get("/charges/dispute", operation_id="dispute_pack"))
@gate("money.read")
def dispute_pack(merchant: str) -> dict:
    """Everything needed to get money back from one merchant."""
    return guard.dispute_pack(merchant)


# ---------------------------------------------------------------- life layer
class PersonIn(BaseModel):
    name: str
    relationship: str
    notes: str = ""
    important_dates: str = ""


@door(app.post("/life/people", operation_id="add_person"))
@gate("life.write")
def add_person(p: PersonIn) -> dict:
    """Record someone who matters to the user. Only when they offer it."""
    return life.add_person(p.name, p.relationship, p.notes, p.important_dates)


class MemoryIn(BaseModel):
    text: str
    when: str = ""
    people: str = ""
    tags: str = ""
    visibility: str = Field(default="private", description="private | family | legacy")


@door(app.post("/life/memories", operation_id="add_memory"))
@gate("life.write")
def add_memory(m: MemoryIn) -> dict:
    """Record a snippet of the user's life in their own words. Never invent
    one; only record what they actually said."""
    try:
        return life.add_memory(m.text, m.when, m.people, m.tags, m.visibility)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class MediaIn(BaseModel):
    path: str
    caption: str = ""
    when: str = ""
    people: str = ""
    visibility: str = "private"


@door(app.post("/life/media", operation_id="add_media"))
@gate("life.write")
def add_media(m: MediaIn) -> dict:
    """Reference a photo where it already lives on the user's Self-Cloud —
    never a copy, never an upload."""
    try:
        return life.add_media(m.path, m.caption, m.when, m.people, m.visibility)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@door(app.get("/life", operation_id="who_am_i"))
def who_am_i() -> dict:
    """What Jefferey understands about this person as a human being. How much
    of it you see is decided by the key your token carries — there is no
    parameter to widen it."""
    return life.who_am_i(access.ceiling())


@door(app.get("/life/story", operation_id="tell_story"))
def tell_story(theme: str = "") -> dict:
    """Gather what's needed to tell a piece of their story. Which moments are
    in reach is decided by the key your token carries — private, family or
    legacy. You cannot ask for a wider audience."""
    return life.tell_story(access.ceiling(), theme)


@door(app.get("/life/gaps", operation_id="story_gaps"))
@gate("life.read")
def story_gaps() -> dict:
    """What's missing from their story. Ask for at most one at a time."""
    return life.story_gaps()


@door(app.delete("/life", operation_id="forget_life"))
@gate("life.write")
def forget_life(contains: str) -> dict:
    """Erase anything in the life layer matching this text."""
    return life.forget_life(contains)


# ---------------------------------------------------------------- the album
class StoryIn(BaseModel):
    moment_id: str
    text: str
    people: str = ""
    when: str = ""
    visibility: str = "private"


@door(app.get("/album/next", operation_id="next_story_prompt"))
@gate("life.read")
def next_story_prompt() -> dict:
    """ONE moment from their photographs nobody has asked about. Offer it at
    most once per conversation; state only the facts it returns."""
    return album.next_prompt()


@door(app.post("/album/story", operation_id="record_story"))
@gate("life.write")
def record_story(s: StoryIn) -> dict:
    """Keep what they said, verbatim, pinned to those photographs."""
    return album.record(s.moment_id, s.text, s.people, s.when, s.visibility)


@door(app.delete("/album/{moment_id}", operation_id="decline_story"))
@gate("life.write")
def decline_story(moment_id: str) -> dict:
    """They'd rather not. Final."""
    return album.decline(moment_id)


@door(app.get("/album/progress", operation_id="story_progress"))
@gate("life.read")
def story_progress() -> dict:
    return album.progress()


# ---------------------------------------------------------------- self-cloud
@door(app.get("/selfcloud", operation_id="selfcloud_status"))
def selfcloud_status() -> dict:
    """Who holds a key to this person's Self-Cloud, what's revoked, and any
    recent refusals."""
    return cloud.status()


@door(app.get("/selfcloud/grants", operation_id="selfcloud_grants"))
def selfcloud_grants() -> dict:
    """Every key in full, plus every scope that exists."""
    return cloud.grants()


class GrantIn(BaseModel):
    client: str
    scopes: list[str] | None = None
    label: str = ""
    note: str = ""


@door(app.post("/selfcloud/grants", operation_id="selfcloud_grant"))
@owner_only
def selfcloud_grant(g: GrantIn) -> dict:
    """ONLY at the owner's explicit word. Never grant a key on your own
    initiative, and never widen your own."""
    return cloud.grant(g.client, g.scopes, g.label, g.note)


class ScopeIn(BaseModel):
    client: str
    scope: str


@door(app.post("/selfcloud/scopes/add", operation_id="selfcloud_add_scope"))
@owner_only
def selfcloud_add_scope(s: ScopeIn) -> dict:
    """Widen one key by exactly one scope, at the owner's word."""
    return cloud.add_scope(s.client, s.scope)


@door(app.post("/selfcloud/scopes/remove", operation_id="selfcloud_remove_scope"))
def selfcloud_remove_scope(s: ScopeIn) -> dict:
    """Narrow a key by one scope."""
    return cloud.remove_scope(s.client, s.scope)


@door(app.delete("/selfcloud/grants", operation_id="selfcloud_revoke"))
def selfcloud_revoke(client: str) -> dict:
    """Kill a key completely. Never argue with a revocation."""
    return cloud.revoke(client)


@door(app.get("/selfcloud/check", operation_id="selfcloud_check_access"))
def selfcloud_check_access(client: str, scope: str) -> dict:
    """Would this client be allowed this scope? Deny by default."""
    return cloud.check_access(client, scope)


@door(app.get("/selfcloud/log", operation_id="selfcloud_access_log"))
def selfcloud_access_log(limit: int = 30) -> list:
    """Who asked for what, and what happened."""
    return cloud.access_log(limit)


# ---------------------------------------------------------------- interview
@door(app.get("/interview/next", operation_id="next_question"))
@gate("life.read")
def next_question(domain: str = "") -> dict:
    """ONE question to weave into conversation — never a list, never
    announced. Only what the relationship has earned."""
    return interview.next_question(domain)


class AnswerIn(BaseModel):
    question_id: str
    answer: str = ""
    declined: bool = False
    visibility: str = "private"


@door(app.post("/interview/answer", operation_id="record_answer"))
@gate("life.write")
def record_answer(a: AnswerIn) -> dict:
    """Keep what they said under the visibility they chose. If they
    deflected, declined=True retires the question permanently."""
    return interview.record_answer(a.question_id, a.answer, a.declined, a.visibility)


@door(app.get("/interview/progress", operation_id="interview_progress"))
@gate("life.read")
def interview_progress() -> dict:
    """What you know, what's missing, and the depth you've earned."""
    return interview.progress()


# ---------------------------------------------------------------- conscience rules
class IncludeIn(BaseModel):
    ref: str
    note: str = ""


@door(app.post("/conscience/include", operation_id="conscience_include"))
@gate("facts.write")
def conscience_include(i: IncludeIn) -> dict:
    """The owner chose to let something from Self-Cloud into their conscience."""
    return rules.include(i.ref, i.note)


@door(app.delete("/conscience/include", operation_id="conscience_exclude"))
@gate("facts.write")
def conscience_exclude(contains: str) -> dict:
    """Take something back out of the conscience; it stays on Self-Cloud."""
    return rules.exclude(contains)


class RuleIn(BaseModel):
    kind: str = Field(description="disclosure | reaction | representation")
    tags: str
    instruction: str
    audience: str = "me"
    allow: bool = True


@door(app.post("/rules", operation_id="set_rule"))
@gate("facts.write")
def set_rule(r: RuleIn) -> dict:
    """Write one of the owner's standing rules, in their words. Only at their word."""
    try:
        return rules.set_rule(r.kind, r.tags, r.instruction, r.audience, r.allow)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@door(app.delete("/rules", operation_id="remove_rule"))
@gate("facts.write")
def remove_rule(rule_id_or_text: str) -> dict:
    """Delete a rule. Never argued with."""
    return rules.remove_rule(rule_id_or_text)


@door(app.get("/rules", operation_id="list_rules"))
@gate("facts.read")
def list_rules(kind: str = "") -> list:
    """Every standing rule the owner has written."""
    return rules.rules(kind)


@door(app.get("/rules/check", operation_id="check_disclosure"))
@gate("facts.read")
def check_disclosure(audience: str, tags: str) -> dict:
    """Before saying anything about the owner to anyone else. Silence is a no."""
    return rules.check_disclosure(audience, tags)


@door(app.get("/rules/guidance", operation_id="guidance_for"))
@gate("facts.read")
def guidance_for(tags: str, audience: str = "me") -> dict:
    """The owner's standing instructions that apply right now, verbatim."""
    return rules.guidance_for(tags, audience)


# ---------------------------------------------------------------- the egress door
@door(app.get("/egress", operation_id="what_left_the_house"))
@gate("facts.read")
def what_left_the_house(days: int = 7) -> dict:
    """What JEFFEREY has handed to rented engines: sends, destinations, tools,
    refusals, and whether the door is open. Counts only — the owner reads
    every send word for word on their own machine."""
    return egress.summary(days)


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
