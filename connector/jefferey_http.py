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
    python connector/jefferey_http.py --schema   # the schema, for GPT Actions

    JEFFEREY_HTTP_TOKEN=...   bearer token (auto-generated + printed if unset)
    JEFFEREY_HTTP_TOKENS=...  one token per key, e.g.
        jefferey:<43 random characters>,gpt-raw:<43 others>
        Make each one with:
        python3 -c "import secrets; print(secrets.token_urlsafe(32))"
    JEFFEREY_PUBLIC_URL=...   the public https address, if this is reachable
                              from outside this Mac
    JEFFEREY_HTTP_PORT=8377   port override

Keys (October 2026, I-59): a token shorter than 32 characters, or the same
token given to two keys, stops the server at start-up with a plain message.
A token with fewer than ten different characters is refused the same way.
A wrong token is written down with where it came from; after five wrong ones
from one address in ten minutes, wrong ones get "too many" — but the right
token is always checked first and always works (behind a tunnel every caller
shares one address). A token whose key the owner switched off gets nothing at
all. The /docs, /redoc and /openapi.json pages are switched off — they told
any passer-by every route there is; `--schema` prints the schema on this Mac.

Wire up a custom GPT (chatgpt.com → Create a GPT):
    1. Instructions: paste connector/directives.md, plus one line —
       "Call GET /directives and GET /conscience at the start of every chat."
    2. Actions → paste the schema that `--schema` prints (with
       JEFFEREY_PUBLIC_URL set, so it names the right address).
    3. Authentication: API Key → Bearer → the token for that key.
    4. Talk to it. Override a recommendation. Watch it learn you —
       into the SAME conscience.json JEFFEREY uses on Claude.
"""

from __future__ import annotations

import functools
import json
import os
import secrets
import sys
import time
from pathlib import Path

# Everything this process creates is readable by the owner's account only.
os.umask(0o077)

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
import access
# This server serves engines, never the owner's own hands (I-43).
access.refuse_owner_console_env("ChatGPT (HTTP)")
from conscience import Conscience, StoreProblem
from representative import Representative
from guardian import Guardian
from life import Life
from selfcloud import SelfCloud
from interview import Interview
from rules import ConscienceRules
from reminisce import Reminisce
import egress
from access import AccessDenied, OwnerOnly, gate
from egress import EgressRefused

# A damaged store does not stop the server: every route explains instead.
conscience = Conscience.for_surface()


def door(register):
    """The egress door around a route, re-reading the conscience first: this
    server stays up while the owner talks to other engines too."""
    def wrap(fn):
        @functools.wraps(fn)
        def fresh(*args, **kwargs):
            try:
                conscience.refresh()
            except StoreProblem:
                if fn.__name__ != "get_directives":    # needs no store
                    raise
            return fn(*args, **kwargs)
        return egress.door(register)(fresh)
    return wrap


rep = Representative(conscience)
guard = Guardian(conscience)
life = Life(conscience)
cloud = SelfCloud(conscience)
interview = Interview(conscience, life)
rules = ConscienceRules(conscience)
album = Reminisce(conscience, life)
DIRECTIVES = (Path(__file__).parent / "directives.md").read_text()

TOKEN = os.environ.get("JEFFEREY_HTTP_TOKEN") or secrets.token_urlsafe(32)
PUBLIC_URL = os.environ.get("JEFFEREY_PUBLIC_URL", "").rstrip("/")
PORT = int(os.environ.get("JEFFEREY_HTTP_PORT", "8377"))
MIN_TOKEN = 32                 # characters; a one-letter token fell in 11 tries
MIN_KINDS = 10                 # different characters: 'AAAA…' is not a key
DOCS = (os.environ.get("JEFFEREY_HTTP_DOCS", "").strip() == "1" and not PUBLIC_URL)
FAIL_LIMIT, FAIL_WINDOW = 5, 600   # wrong tokens per address, per ten minutes


def _token_map() -> dict[str, str]:
    """token -> client. One process here legitimately serves several engines
    (a Custom GPT, a Claude session, a family member's app), so the token is
    not just a password — it says WHICH KEY the caller holds.

        JEFFEREY_HTTP_TOKENS="jefferey:<token_urlsafe(32)>,gpt-raw:<another>"

    With nothing set, the single JEFFEREY_HTTP_TOKEN maps to JEFFEREY_CLIENT
    (default `claude-raw` — the narrow key, per access.py).

    A token shorter than MIN_TOKEN characters, or one token given to two
    keys (the last one used to win, so the family app got the caretaker's
    key), refuses the start with a plain message (I-59)."""
    raw = os.environ.get("JEFFEREY_HTTP_TOKENS", "").strip()
    problems: list[str] = []
    out: dict[str, str] = {}
    if not raw:
        out[TOKEN] = os.environ.get("JEFFEREY_CLIENT", access.DEFAULT_CLIENT).strip().lower()
        if len(TOKEN) < MIN_TOKEN:
            problems.append(f"the key in JEFFEREY_HTTP_TOKEN is only {len(TOKEN)} "
                            f"characters long; it must be at least {MIN_TOKEN}")
        elif len(set(TOKEN)) < MIN_KINDS:
            problems.append("the key in JEFFEREY_HTTP_TOKEN repeats the same few "
                            "characters; it must be made at random")
    else:
        for pair in raw.split(","):
            pair = pair.strip()
            if not pair:
                continue
            client, sep, tok = pair.partition(":")
            client, tok = client.strip().lower(), tok.strip()
            if not sep or not client or not tok:
                problems.append("one entry does not look like name:token")   # never echoed: it may be a token
                continue
            if len(tok) < MIN_TOKEN:
                problems.append(f"the token for '{client}' is only {len(tok)} characters "
                                f"long; it must be at least {MIN_TOKEN}")
            elif len(set(tok)) < MIN_KINDS:
                problems.append(f"the token for '{client}' repeats the same few "
                                f"characters; it must be made at random")
            if access.reserved(client):
                problems.append(f"'{client}' is a name only the owner himself goes by; "
                                f"a key may not be called that")
            if tok in out:
                problems.append(f"'{out[tok]}' and '{client}' were given the same token; "
                                f"every key needs its own")
            out[tok] = client
    if problems:
        raise SystemExit(
            "JEFFEREY will not start the ChatGPT connection, because "
            + "; ".join(problems) + ".\nNothing was changed. Make a strong token for "
            "each key with:\n"
            "    python3 -c \"import secrets; print(secrets.token_urlsafe(32))\"\n"
            "then put it in JEFFEREY_HTTP_TOKENS, and paste the same token into the "
            "GPT's settings (Actions → Authentication → API Key → Bearer).")
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
import home
home.announce()


_FAILS: dict[str, list[float]] = {}


def _bad_token(where: str, why: str) -> None:
    """Written down in the owner's access log, with where it came from."""
    try:
        cloud._log("unknown", "bad_token", f"{why}, from {where}", False, actor="unknown")
    except Exception:
        pass


def _wrong_key(where: str, tok: str) -> None:
    """A wrong or missing key: counted for its address, written down (the
    first few in each ten minutes, so a flood cannot fill the log), and
    refused. After FAIL_LIMIT in ten minutes the refusal says to slow down.

    Only WRONG keys are ever refused here. The right key is checked first
    and always works: behind the tunnel the owner sets up, every caller
    arrives from one address, and ChatGPT's GPTs share OpenAI's addresses —
    so locking out an address locked out the owner's own GPT, the family app
    and the caretaker whenever a stranger sent five bad keys (engines-25,
    money-64). With 43-character keys, guessing is hopeless anyway."""
    now = time.time()
    if len(_FAILS) > 10_000:                   # many addresses: forget the old
        for k in [k for k, v in _FAILS.items() if not v or now - v[-1] >= FAIL_WINDOW]:
            _FAILS.pop(k, None)
    recent = [t for t in _FAILS.get(where, []) if now - t < FAIL_WINDOW]
    recent.append(now)
    _FAILS[where] = recent[-(FAIL_LIMIT * 20):]
    if len(recent) <= FAIL_LIMIT:
        _bad_token(where, "a missing or wrong key" if tok else "no key")
    elif len(recent) == FAIL_LIMIT + 1:
        _bad_token(where, f"more than {FAIL_LIMIT} wrong keys in ten minutes; the "
                          "rest from this address are counted, not each written down")
    if len(recent) > FAIL_LIMIT:
        raise HTTPException(status_code=429, detail=(
            "Too many wrong keys from this address. A wrong key is refused; the "
            "right key still works."))
    raise HTTPException(status_code=401, detail="missing or invalid bearer token")


async def require_owner(request: Request) -> None:
    """Every byte in the store is personal. No token, no access — and the
    token decides which key you hold for the rest of this request. A token
    whose key the owner switched off gets nothing (I-09: a revoked key still
    read the key list and revoked others)."""
    where = request.client.host if request.client else "an unknown address"
    scheme, _, tok = request.headers.get("authorization", "").strip().partition(" ")
    tok = tok.strip()
    client = None
    if scheme.lower() == "bearer" and tok:
        for known, who in TOKENS.items():
            if secrets.compare_digest(tok.encode(), known.encode()):
                client = who
    if client is None:
        _wrong_key(where, tok)
    access.use_client(client)          # per-request identity, not per-call
    # The door shut: nothing is done, and no key is issued on first use
    # either (I-12: a shut door still wrote two new keys into the store).
    why = egress.shut_reason()
    if why:
        raise egress._refused_before(request.url.path, None, why)
    try:
        access.require_live()
    except AccessDenied as e:
        raise HTTPException(status_code=403, detail=str(e))


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
    # No open pages listing every route, whether or not the owner told it
    # its public address (a tunnel set up without JEFFEREY_PUBLIC_URL still
    # exposed them — verify I-59). The schema for GPT Actions comes from
    # `--schema`, on this Mac. A developer on this Mac alone may switch the
    # pages on with JEFFEREY_HTTP_DOCS=1.
    docs_url="/docs" if DOCS else None,
    redoc_url="/redoc" if DOCS else None,
    openapi_url="/openapi.json" if DOCS else None,
)


@app.exception_handler(RequestValidationError)
async def _invalid(request: Request, exc: RequestValidationError):
    """What was sent does not fit. Said in words, WITHOUT echoing the values
    back (FastAPI's own answer repeated them — and could not even be written
    when one was NaN, so the caller got a crash instead of a 422)."""
    parts = []
    for e in exc.errors():
        where = ".".join(str(x) for x in e.get("loc", ()) if x not in ("body", "query"))
        parts.append(f"'{where or 'the request'}': {e.get('msg', 'not valid')}")
    return JSONResponse(status_code=422, content={
        "detail": "Some of what was sent is not valid — " + "; ".join(parts) + "."})


@app.exception_handler(AccessDenied)
async def _denied(request: Request, exc: AccessDenied):
    """A refusal is an answer, not an error to route around."""
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(OwnerOnly)
async def _owner_only(request: Request, exc: OwnerOnly):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(StoreProblem)
async def _store(request: Request, exc: StoreProblem):
    """The memory file is damaged, was changed elsewhere a moment ago, or the
    drive refused the save. Plain words, never a bare 500 — and never a
    file path."""
    return JSONResponse(status_code=503, content={
        "detail": exc.plain, "tell_the_user": exc.tell_the_user})


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
def get_conscience(limit: int = 100, offset: int = 0) -> dict:
    """Read the conscience: the priority hierarchy (with confidence and the
    evidence for and against), remembered facts, the most recent page
    first (offset for older ones), active goals. Private facts are counted, not
    sent; anything marked unconfirmed was written by an AI and not yet
    confirmed by him. The user owns every byte."""
    return conscience.snapshot(limit, offset)


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
    higher='direct flights', lower='saving money'). The context must name a
    subject. You may claim at most 0.6 confidence; he confirms it higher
    himself. Reversing something he stated himself is never applied, even
    when he says he changed his mind: it becomes a question for him, and only
    his own /confirm makes it so. Use record_correction instead when learning
    from an override rather than an explicit statement."""
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
def forget(contains: str = "", ids: str = "", confirm: str = "") -> dict:
    """Forget remembered facts — by id, or by whole words in them (at least
    three letters). Two steps, never a guess: without `confirm` nothing is removed — the
    answer lists exactly what would go (with ids) and a one-time code. Read
    it to the owner; only if he says yes, call again with confirm=<code>.
    Anything big can only be approved by the owner himself — the answer says
    how. `ids` is a comma-separated list. Never argue with a forget."""
    return conscience.forget_fact(contains, ids, confirm)


# ---------------------------------------------------------------- representing
@door(app.get("/basis", operation_id="explain_basis"))
@gate("priorities.read")
def explain_basis(topic: str, limit: int = 10, offset: int = 0) -> dict:
    """Before recommending anything, fetch the user's OWN priorities and
    facts relevant to this topic (whole words, each with why it matched,
    most relevant first). Ground the recommendation and its explanation
    strictly in what this returns — never hidden incentives. If it returns
    nothing relevant, say you don't yet know their values here, and ask."""
    return conscience.explain_basis(topic, limit, offset)


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
def close_goal(contains: str = "", ids: str = "", confirm: str = "") -> dict:
    """Mark active goals done/retired — by id or whole words. Two steps, never a guess: without `confirm` nothing is removed — the
    answer lists exactly what would go (with ids) and a one-time code. Read
    it to the owner; only if he says yes, call again with confirm=<code>.
    Anything big can only be approved by the owner himself — the answer says
    how. `ids` is a comma-separated list."""
    return conscience.close_goal(contains, ids, confirm)


# ---------------------------------------------------------------- operational AI
# Raising a permission is not a route. The owner types it himself (/permit in
# 'Talk to JEFFEREY on this Mac'); JEFFEREY never widens JEFFEREY.
class ActionAskIn(BaseModel):
    category: str
    description: str
    amount: float | None = Field(default=None, allow_inf_nan=False,
                                 description="the FULL price, as a plain number")
    currency: str = "CAD"
    recurring: bool = Field(default=False, description="true if it repeats or has "
                                                       "a minimum term")


@door(app.post("/actions/authorize", operation_id="authorize_action"))
@gate("act.request")
def authorize_action(a: ActionAskIn) -> dict:
    """THE gate. Call before doing anything in the real world on the owner's
    behalf, with the full price whenever money is involved. A yes carries a
    single-use authorization_id, good for 30 minutes; cite it in log_action.
    A no is final: recommend instead — only the owner can raise the level.
    Moving money, gift cards, crypto, phone calls and the doors are never
    approved."""
    return conscience.authorize_action(a.category, a.description, a.amount,
                                       a.currency, a.recurring)


class ActionLogIn(BaseModel):
    category: str
    description: str
    outcome: str
    amount: float | None = Field(default=None, allow_inf_nan=False)
    authorization_id: str = ""


@door(app.post("/actions", operation_id="log_action"))
@gate("facts.write")
def log_action(a: ActionLogIn) -> dict:
    """Write down an act just performed on the owner's behalf, citing the
    authorization_id. No silent actions, ever; an act with no valid approval
    is kept but marked 'not approved'."""
    return conscience.log_action(a.category, a.description, a.outcome, a.amount,
                                 a.authorization_id)


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
@gate("goals.write")
def record_opportunity(o: OpportunityIn) -> dict:
    """Score a way to make the user's life better against THEIR priorities,
    and keep it for the brief, with who saved it. Returns the score and
    whether it earns an interrupt (>=0.75), waits for the daily brief
    (>=0.40), or holds. Only interrupt when it says to."""
    return conscience.record_opportunity(
        o.what, o.value_estimate, o.aligns_with, o.advances_goal,
        o.reduces_risk, o.urgency,
    )


@door(app.post("/opportunities/score", operation_id="score_opportunity"))
@gate("goals.read")
def score_opportunity(o: OpportunityIn) -> dict:
    """The same score, saved nowhere."""
    return conscience.score_opportunity(
        o.what, o.value_estimate, o.aligns_with, o.advances_goal,
        o.reduces_risk, o.urgency,
    )


@door(app.delete("/opportunities", operation_id="resolve_opportunity"))
@gate("goals.write")
def resolve_opportunity(contains: str = "", outcome: str = "done", ids: str = "",
                        confirm: str = "") -> dict:
    """Close pending opportunities — by id or whole words. Two steps, never a guess: without `confirm` nothing is removed — the
    answer lists exactly what would go (with ids) and a one-time code. Read
    it to the owner; only if he says yes, call again with confirm=<code>.
    Anything big can only be approved by the owner himself — the answer says
    how. `ids` is a comma-separated list."""
    return conscience.resolve_opportunity(contains, outcome, ids, confirm)


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
    """Read an incoming message (a text, an email, a call he typed in,
    English or French) the way a good friend would: what does it want, does
    it matter by THIS person's priorities, and is anyone trying to take
    advantage of them? Pass the sender exactly as shown (the number, the
    address, or the name with any '~' or 'Maybe:' the app puts before it).
    Returns a verdict —
    safety (someone asking when he is home alone: tell him at once) /
    likely_scam / suspicious / check_first (it touches money, cards, codes,
    secrecy, urgency or a family claim: tell him, and he checks by calling
    back on a number he already has) / money_watch / needs_decision /
    routine — whether to interrupt him now, the tactics spotted in plain
    words, what it touches, amounts and deadlines, and his relevant values.
    Relay the advice. Never reply, click, pay, or unsubscribe on their
    behalf without authorize_action."""
    return rep.triage_message(t.sender, t.subject, t.body)


class DraftIn(BaseModel):
    purpose: str
    recipient: str = ""


@door(app.post("/draft-guidance", operation_id="draft_guidance"))
@gate("priorities.read")
def draft_guidance(d: DraftIn) -> dict:
    """Call BEFORE writing anything in the user's name, with the recipient as
    it will appear. Returns their voice, the priorities and facts that
    apply, who to sign as, the hard limits, and what his own rules keep from
    this recipient (do_not_mention). Run check_draft before showing it.
    Sending requires authorize_action on 'correspondence'."""
    return rep.draft_guidance(d.purpose, d.recipient)


class DraftCheckIn(BaseModel):
    text: str
    audience: str = ""


@door(app.post("/draft-check", operation_id="check_draft"))
@gate("priorities.read")
def check_draft(d: DraftCheckIn) -> dict:
    """Check a draft BEFORE showing or sending it: his rules for this person,
    his private facts, and his safety (never when he is home, alone or away,
    or how to get in). Fix every problem it lists."""
    return rep.check_draft(d.text, d.audience)


class FormIn(BaseModel):
    fields: list[str]
    owner_is: str = ""


@door(app.post("/forms/fill", operation_id="fill_form"))
@gate("facts.read")
def fill_form(f: FormIn) -> dict:
    """Given a form's field labels, return what Jefferey can fill from the
    user's own profile and exactly what he cannot. He never guesses, never
    fills a box about someone else with the owner's details, and never fills
    sensitive identifiers — those go back to the user. When he is selling
    or buying something himself, say which side he is on: owner_is='seller'
    or 'buyer'; with nothing said, every seller's, buyer's, vendor's or
    shop's box is left for him, and a shop's, dealer's or supplier's box is
    never his."""
    return rep.fill_form(f.fields, f.owner_is)


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
    confirm: str = ""


@door(app.post("/profile", operation_id="set_profile_field"))
@gate("facts.write")
def set_profile_field(p: ProfileIn) -> dict:
    """Store one of the OWNER's own details Jefferey may reuse on forms.
    Sensitive identifiers (SIN/SSN, cards, PINs) and anything about someone
    else are refused. A change to who he is (his name or date of birth)
    waits for his own yes: tell him, and he types /approve and the code
    himself in 'Talk to JEFFEREY on this Mac'."""
    return rep.set_profile_field(p.field, p.value, p.confirm)


@door(app.get("/profile", operation_id="get_profile"))
@gate("facts.read")
def get_profile() -> dict:
    """Everything Jefferey can put on a form for this user. They own all of it."""
    return rep.get_profile()


@door(app.delete("/profile", operation_id="forget_profile_field"))
@gate("facts.write")
def forget_profile_field(field: str, confirm: str = "") -> dict:
    """Delete one profile detail, by its exact name. Two steps, never a guess: without `confirm` nothing is removed — the
    answer lists exactly what would go (with ids) and a one-time code. Read
    it to the owner; only if he says yes, call again with confirm=<code>.
    Anything big can only be approved by the owner himself — the answer says
    how."""
    return rep.forget_profile_field(field, confirm)


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
    """Ask to add a charge the user has actually agreed to. From you it WAITS
    for the owner (status 'waiting_for_owner'): say it is waiting, never that
    it is registered, unless the note says 'is in your register'."""
    return guard.expect_charge(e.merchant, e.amount, e.cadence,
                               e.authorized_recurring, e.note)


class CancelIn(BaseModel):
    merchant: str
    on: str = ""


@door(app.post("/charges/cancelled", operation_id="mark_cancelled"))
@gate("money.write")
def mark_cancelled(c: CancelIn) -> dict:
    """Record that the user cancelled something, with the date (ISO) — any
    charge dated after it is flagged. If marked_cancelled is 0, NOTHING is
    being watched: ask what the note asks and send it again."""
    return guard.mark_cancelled(c.merchant, c.on)


class ChargeIn(BaseModel):
    merchant: str
    # '$18.63' or '1 234,56 $' as printed is read by the guardian, line by
    # line, instead of refusing the whole statement
    amount: float | str
    date: str = Field(default="", description="as printed on the statement, ISO if you can")
    ref: str = Field(default="", description="the statement line's reference, if any")


@door(app.post("/charges/check", operation_id="check_charge"))
@gate("money.read")
def check_charge(c: ChargeIn) -> dict:
    """Hold one charge up against what the user agreed to. Checking the same
    charge again never adds a duplicate. Quiet: expected, amount_decreased,
    refund. unexpected_merchant is informational (offer a dispute only if
    they say it is not theirs); needs_date: ask for the date;
    possible_card_testing / possible_scam: the next step is the bank, on the
    number on the card. The rest: say it plainly and offer a dispute_pack."""
    return guard.check_charge(c.merchant, c.amount, c.date, ref=c.ref)


class StatementIn(BaseModel):
    charges: list[ChargeIn]


@door(app.post("/charges/review", operation_id="review_statement"))
@gate("money.read")
def review_statement(s: StatementIn) -> dict:
    """Run a whole statement through at once and report the summary and the
    total at stake. If some lines could not be read, nothing was kept."""
    return guard.review_statement([c.model_dump() for c in s.charges])


@door(app.get("/charges/expected", operation_id="expected_charges"))
@gate("money.read")
def expected_charges() -> list:
    """What the user has agreed to pay, and what they've cancelled. Entries
    with status 'waiting_for_owner' are not in force yet."""
    return guard.expected_charges()


@door(app.get("/charges/waiting", operation_id="charge_changes_waiting"))
@gate("money.read")
def charge_changes_waiting() -> list:
    """Additions an AI asked for that wait for the owner. Only he confirms
    them, at his own keyboard; you can only tell him they are waiting."""
    return guard.pending_changes()


@door(app.delete("/charges/waiting/{proposal_id}", operation_id="decline_charge_change"))
@gate("money.write")
def decline_charge_change(proposal_id: str) -> dict:
    """Withdraw a waiting addition — when the user says it was a mistake."""
    return guard.decline_change(proposal_id)


class AliasIn(BaseModel):
    descriptor: str = Field(description="the name as printed on the statement")
    merchant: str = Field(description="the agreed payment it belongs to")


@door(app.post("/charges/names", operation_id="name_for_charge"))
@gate("money.write")
def name_for_charge(a: AliasIn) -> dict:
    """A statement name is one of their agreed payments. From you it waits
    for the owner to confirm, like any addition."""
    return guard.add_alias(a.descriptor, a.merchant)


@door(app.get("/charges/dispute", operation_id="dispute_pack"))
@gate("money.read")
def dispute_pack(merchant: str, not_mine: bool = False) -> dict:
    """Everything needed to get money back from one merchant. not_mine=true
    when the user says charges from a place not in their register are not
    theirs."""
    return guard.dispute_pack(merchant, not_mine)


# ---------------------------------------------------------------- life layer
class PersonIn(BaseModel):
    name: str
    relationship: str
    notes: str = ""
    important_dates: str = ""


@door(app.post("/life/people", operation_id="add_person"))
@gate("life.write")
def add_person(p: PersonIn) -> dict:
    """Record someone who matters to the user. Only when they offer it. The
    same name with a different relationship is a separate person; the same
    person gets new notes added, never replaced."""
    return life.add_person(p.name, p.relationship, p.notes, p.important_dates)


class PersonUpdateIn(BaseModel):
    person_id: str
    name: str = ""
    relationship: str = ""
    notes: str = ""
    important_dates: str = ""


@door(app.post("/life/people/update", operation_id="update_person"))
@gate("life.write")
def update_person(p: PersonUpdateIn) -> dict:
    """Change one person, by id. Notes and dates are added, dated; a changed
    name or relationship keeps what it was."""
    return life.update_person(p.person_id, p.name, p.relationship, p.notes,
                              p.important_dates)


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
    one; only record what they actually said. Kept private whatever
    visibility is sent: only he shares it."""
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
def who_am_i(limit: int = 50, offset: int = 0) -> dict:
    """What Jefferey understands about this person as a human being, the
    most recent moments first, a page at a time. How much of it you see is decided by
    the key your token carries and by his own rules — there is no parameter
    to widen it."""
    return life.who_am_i(access.ceiling(), limit, offset)


@door(app.get("/life/story", operation_id="tell_story"))
def tell_story(theme: str = "", limit: int = 50, offset: int = 0) -> dict:
    """Gather what's needed to tell a piece of their story. Which moments are
    in reach is decided by the key your token carries — private, family or
    legacy. You cannot ask for a wider audience."""
    return life.tell_story(access.ceiling(), theme, limit, offset)


@door(app.get("/life/gaps", operation_id="story_gaps"))
@gate("life.read")
def story_gaps() -> dict:
    """What's missing from their story. Ask for at most one at a time."""
    return life.story_gaps()


@door(app.delete("/life", operation_id="forget_life"))
@gate("life.write")
def forget_life(contains: str = "", ids: str = "", confirm: str = "") -> dict:
    """Forget a person by EXACT name or id (with the moments and pictures
    about them alone), or moments and pictures by id or whole words. Two steps, never a guess: without `confirm` nothing is removed — the
    answer lists exactly what would go (with ids) and a one-time code. Read
    it to the owner; only if he says yes, call again with confirm=<code>.
    Anything big can only be approved by the owner himself — the answer says
    how. `ids` is a comma-separated list."""
    return life.forget_life(contains, ids, confirm)


class VisibilityIn(BaseModel):
    ids: list[str]
    visibility: str = Field(description="private | engines (facts only) | family | legacy")


@door(app.post("/life/visibility", operation_id="set_visibility"))
@gate("life.write")
def set_visibility(v: VisibilityIn) -> dict:
    """Who may see something, by id. More private: done at once. Less
    private: only the owner, typing /share himself — the answer says how."""
    return life.set_visibility(v.ids, v.visibility)


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
    most once per conversation; state only the facts it returns. 'Not yet'
    means don't mention the album. Follow its 'rule' exactly. 'Not now' →
    skip_story; 'rather not' → decline_story."""
    return album.next_prompt()


@door(app.post("/album/story", operation_id="record_story"))
@gate("life.write")
def record_story(s: StoryIn) -> dict:
    """Keep what they said, verbatim, pinned to those photographs."""
    return album.record(s.moment_id, s.text, s.people, s.when, s.visibility)


@door(app.delete("/album/{moment_id}", operation_id="decline_story"))
@gate("life.write")
def decline_story(moment_id: str) -> dict:
    """They'd rather not. Final for you; only the owner can reopen it."""
    return album.decline(moment_id)


@door(app.post("/album/{moment_id}/skip", operation_id="skip_story"))
@gate("life.write")
def skip_story(moment_id: str) -> dict:
    """Not now — the moment goes to the back of the album; nothing is decided."""
    return album.skip(moment_id)


@door(app.get("/album/progress", operation_id="story_progress"))
@gate("life.read")
def story_progress() -> dict:
    return album.progress()


# ---------------------------------------------------------------- self-cloud
# Giving out or widening a key is not a route: the owner types /grant or
# /scope add himself. A key may give up its OWN access here; changing any
# other key is the owner's. (A switched-off key never gets this far.)
@door(app.get("/selfcloud", operation_id="selfcloud_status"))
def selfcloud_status() -> dict:
    """Who holds a key to this person's Self-Cloud, what's revoked, recent
    refusals and recent changes to the important keys. A key other than the
    caretaker's sees only itself."""
    return cloud.status()


@door(app.get("/selfcloud/grants", operation_id="selfcloud_grants"))
def selfcloud_grants() -> dict:
    """Every key in full, plus every scope that exists. A key other than the
    caretaker's sees only itself."""
    return cloud.grants()


class ScopeIn(BaseModel):
    client: str
    scope: str


@door(app.post("/selfcloud/scopes/remove", operation_id="selfcloud_remove_scope"))
def selfcloud_remove_scope(s: ScopeIn) -> dict:
    """Give up one scope of the key this token holds."""
    return cloud.remove_scope(s.client, s.scope)


@door(app.delete("/selfcloud/grants", operation_id="selfcloud_revoke"))
def selfcloud_revoke(client: str) -> dict:
    """Switch off the key this token holds. Never argue with a revocation."""
    return cloud.revoke(client)


@door(app.get("/selfcloud/check", operation_id="selfcloud_check_access"))
def selfcloud_check_access(client: str, scope: str) -> dict:
    """Would this client be allowed this scope? Deny by default. Only the
    caretaker key may ask about keys other than its own."""
    return cloud.ask_access(client, scope)


@door(app.get("/selfcloud/log", operation_id="selfcloud_access_log"))
def selfcloud_access_log(limit: int = 30) -> list:
    """Who asked for what, and what happened (1 to 200 entries); a key other
    than the caretaker's sees only its own lines."""
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
    """Keep what they said, privately (only he shares it). If they
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
def conscience_exclude(contains: str = "", ids: str = "", confirm: str = "") -> dict:
    """Take something back out of the conscience; it stays on Self-Cloud.
    Two steps, never a guess: without `confirm` nothing is removed — the
    answer lists exactly what would go (with ids) and a one-time code. Read
    it to the owner; only if he says yes, call again with confirm=<code>.
    Anything big can only be approved by the owner himself — the answer says
    how. `ids` is a comma-separated list."""
    return rules.exclude(contains, ids, confirm)


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
def remove_rule(rule_id_or_text: str = "", confirm: str = "") -> dict:
    """Delete a rule by its id, or by whole words of it. Two steps, never a guess: without `confirm` nothing is removed — the
    answer lists exactly what would go (with ids) and a one-time code. Read
    it to the owner; only if he says yes, call again with confirm=<code>.
    Anything big can only be approved by the owner himself — the answer says
    how."""
    return rules.remove_rule(rule_id_or_text, confirm)


@door(app.get("/rules", operation_id="list_rules"))
@gate("rules.read")
def list_rules(kind: str = "") -> list:
    """Every standing rule the owner has written."""
    return rules.listed(kind)


@door(app.get("/rules/check", operation_id="check_disclosure"))
@gate("rules.read")
def check_disclosure(audience: str, tags: str) -> dict:
    """Before saying anything about the owner to anyone else. Silence is a no."""
    return rules.check_disclosure(audience, tags)


@door(app.get("/rules/guidance", operation_id="guidance_for"))
@gate("rules.read")
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


def schema() -> dict:
    """The routes, for pasting into GPT Actions — printed on this Mac, never
    served to the internet."""
    return app.openapi()


if __name__ == "__main__":
    if "--schema" in sys.argv[1:]:
        print(json.dumps(schema(), indent=2))
        sys.exit(0)
    import uvicorn

    print("JEFFEREY HTTP connector — one conscience, many engines")
    print(f"  store : {conscience.path}")
    print(f"  local : http://127.0.0.1:{PORT}   (no open /docs or /openapi.json pages; "
          f"use --schema)")
    if PUBLIC_URL:
        print(f"  public: {PUBLIC_URL}")
    else:
        print("  public: set JEFFEREY_PUBLIC_URL before importing into GPT Actions")
    if "JEFFEREY_HTTP_TOKEN" not in os.environ and not os.environ.get("JEFFEREY_HTTP_TOKENS"):
        print(f"  token : {TOKEN}   (generated — set JEFFEREY_HTTP_TOKEN to pin it)")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
