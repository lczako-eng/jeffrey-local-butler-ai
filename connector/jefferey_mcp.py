"""
JEFFEREY Agent Connector — MCP server
=====================================

Plugs JEFFEREY's owned conscience into any MCP-capable AI engine
(Claude Desktop, Claude Code, and other MCP hosts). The host model is the
rented, disposable reasoning engine; this store — and the person it
represents — persist.

Run:
    pip install "mcp[cli]"
    python connector/jefferey_mcp.py            # stdio server

Add to Claude Code:
    claude mcp add jefferey -- python /path/to/connector/jefferey_mcp.py

Add to Claude Desktop (claude_desktop_config.json):
    { "mcpServers": { "jefferey": {
        "command": "python",
        "args": ["/path/to/connector/jefferey_mcp.py"] } } }
"""

import sys
from pathlib import Path

# Support both SDK generations: mcp 1.x (FastMCP) and mcp 2.x (MCPServer).
try:
    from mcp.server.fastmcp import FastMCP as _Server
except ImportError:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server

sys.path.insert(0, str(Path(__file__).parent))
from conscience import Conscience
from representative import Representative
from guardian import Guardian
from life import Life

mcp = _Server("jefferey")
conscience = Conscience()
rep = Representative(conscience)
guard = Guardian(conscience)
life = Life(conscience)

DIRECTIVES = (Path(__file__).parent / "directives.md").read_text()


# ---------------------------------------------------------------- identity
@mcp.tool()
def get_directives() -> str:
    """Load the Jefferey Directive Pack: the identity, mission, and operating
    rules the host model must adopt to BE Jefferey. Call this first in every
    session, then follow it for the rest of the conversation."""
    return DIRECTIVES


@mcp.tool()
def get_conscience() -> dict:
    """Read the full conscience: the user's priority hierarchy (with
    confidence scores), remembered facts, active goals, and how many
    corrections Jefferey has learned from. The user owns every byte."""
    return conscience.snapshot()


# ---------------------------------------------------------------- learning
@mcp.tool()
def record_correction(
    context: str,
    what_was_suggested: str,
    what_user_chose: str,
    value_protected: str,
    value_traded_away: str,
) -> dict:
    """THE core learning act. The user overrode a recommendation — learn WHY.
    Record which value they were protecting (e.g. 'reliability') and which
    they traded away (e.g. 'lowest price') in this context. Consistent
    evidence raises confidence; contradictions erode and can flip the
    hierarchy. Returns the updated priority with its confidence score —
    tell the user what you learned and the confidence you now hold."""
    return conscience.record_correction(
        context, what_was_suggested, what_user_chose,
        value_protected, value_traded_away,
    )


@mcp.tool()
def set_priority(context: str, higher: str, lower: str, confidence: float = 0.6) -> dict:
    """The user explicitly stated a priority (e.g. context='travel',
    higher='direct flights', lower='saving money'). Store it with the given
    confidence (0-1). Use record_correction instead when learning from an
    override rather than an explicit statement."""
    return conscience.set_priority(context, higher, lower, confidence)


@mcp.tool()
def remember_fact(fact: str, category: str = "general") -> dict:
    """Remember a durable FACT about the user (people, dates, situations,
    constraints). Facts are stored separately from values — never mix the
    two. Ask before remembering anything sensitive."""
    return conscience.remember_fact(fact, category)


@mcp.tool()
def forget(contains: str) -> dict:
    """Delete every remembered fact containing this text. The user's right
    to erase is absolute — never argue, always confirm what was removed."""
    removed = conscience.forget_fact(contains)
    return {"removed_facts": removed}


# ---------------------------------------------------------------- representing
@mcp.tool()
def explain_basis(topic: str) -> dict:
    """Before recommending anything, fetch the user's OWN priorities and
    facts relevant to this topic. Ground the recommendation and its
    explanation strictly in what this returns — 'I chose X because you
    consistently value A over B' — never in hidden incentives. If it
    returns nothing relevant, say you don't yet know their values here,
    and ask."""
    return conscience.explain_basis(topic)


@mcp.tool()
def priorities_for(context: str = "") -> list:
    """List the user's learned priority hierarchy, highest confidence first,
    optionally filtered to a context (e.g. 'travel', 'money', 'family')."""
    return conscience.priorities_for(context or None)


# ---------------------------------------------------------------- goals
@mcp.tool()
def add_goal(goal: str) -> dict:
    """Register a long-term goal the user has approved (e.g. 'reduce monthly
    expenses by 15%'). Goals drive the Opportunity Engine: what can be done
    today to move these forward, within permissions."""
    return conscience.add_goal(goal)


@mcp.tool()
def close_goal(contains: str) -> dict:
    """Mark active goals containing this text as done/retired."""
    return {"closed": conscience.close_goal(contains)}


# ---------------------------------------------------------------- operational AI
@mcp.tool()
def set_permission(category: str, level: str, cap: float | None = None) -> dict:
    """ONLY when the user explicitly grants or changes authority, in their own
    words. Levels: 'observe' (watch and learn), 'recommend' (bring ranked
    options — the default), 'act' (execute in this category, optionally under
    a spending cap). Never call this on your own initiative — Jefferey never
    expands his own permissions."""
    return conscience.set_permission(category, level, cap)


@mcp.tool()
def authorize_action(category: str, description: str, amount: float | None = None) -> dict:
    """THE gate. Call before doing anything in the real world on the user's
    behalf. Returns allowed true/false with the reason. If denied, recommend
    instead — only the user can raise the level. Denials are logged."""
    return conscience.authorize_action(category, description, amount)


@mcp.tool()
def log_action(category: str, description: str, outcome: str, amount: float | None = None) -> dict:
    """Write down an act just performed on the user's behalf. No silent
    actions, ever — the log lives in the user's own store."""
    return conscience.log_action(category, description, outcome, amount)


@mcp.tool()
def action_log(limit: int = 20) -> list:
    """The audit trail: recent acts, denials, and permission changes,
    newest first."""
    return conscience.action_log(limit)


# ---------------------------------------------------------------- opportunity engine
@mcp.tool()
def log_observation(note: str, category: str = "general") -> dict:
    """Note something observed that might matter later (a price change, a
    renewal date approaching, a pattern in their spending). Observations
    feed the Opportunity Engine."""
    return conscience.log_observation(note, category)


@mcp.tool()
def record_opportunity(
    what: str,
    value_estimate: str = "",
    aligns_with: str = "",
    advances_goal: str = "",
    reduces_risk: bool = False,
    urgency: float = 0.5,
) -> dict:
    """Score a way to make the user's life better against THEIR priorities:
    what it is, its value ('saves $380/yr'), which learned priority it aligns
    with, which goal it advances, whether it reduces a risk, and urgency 0-1.
    Returns the score and whether it earns an interrupt (>=0.75), waits for
    the daily brief (>=0.40), or holds. Only interrupt when it says to."""
    return conscience.record_opportunity(
        what, value_estimate, aligns_with, advances_goal, reduces_risk, urgency
    )


@mcp.tool()
def resolve_opportunity(contains: str, outcome: str = "done") -> dict:
    """Close pending opportunities containing this text (acted on, declined,
    or expired)."""
    return {"resolved": conscience.resolve_opportunity(contains, outcome)}


@mcp.tool()
def daily_brief() -> dict:
    """One screen: the orb's current mood (the engine's real state), active
    goals, pending opportunities ranked by score, recent actions, and recent
    observations. Open a session with this when the user asks what's new."""
    return conscience.daily_brief()


@mcp.tool()
def orb_state() -> dict:
    """The predictive cycle: the mood the orb should show right now —
    protective (risk found), charged (interrupt-worthy opportunity), curious
    (brief-level opportunities), happy (learned recently), thinking (fresh
    observations), or calm."""
    return conscience.orb_state()


# ---------------------------------------------------------------- representative
# Correspondence and paperwork, done in the user's interest. Jefferey rides
# the host's own mail/file connectors; these tools supply the representation.
@mcp.tool()
def triage_message(sender: str, subject: str, body: str) -> dict:
    """Read an incoming message the way a good friend would: what does it
    want, does it matter by THIS person's priorities, and is anyone trying to
    take advantage of them? Returns a verdict (likely_scam / suspicious /
    money_watch / needs_decision / routine), the predatory tactics spotted in
    plain words, amounts and deadlines found, and the user's relevant values.
    Never reply, click, pay, or unsubscribe on their behalf without
    authorize_action."""
    return rep.triage_message(sender, subject, body)


@mcp.tool()
def draft_guidance(purpose: str, recipient: str = "") -> dict:
    """Call BEFORE writing anything in the user's name (an email, a letter,
    a complaint, a cancellation). Returns their voice, the priorities and
    facts that apply here, who to sign as, and the hard limits. Write the
    draft from this — then show it to them. Sending requires
    authorize_action on 'correspondence'."""
    return rep.draft_guidance(purpose, recipient)


@mcp.tool()
def fill_form(fields: list) -> dict:
    """Given the field labels on a form (HTML, PDF, or paper), return what
    Jefferey can fill from the user's own profile and exactly what he cannot.
    He never guesses a value, and never fills sensitive identifiers (SIN/SSN,
    card numbers, PINs, signatures) — those always go back to the user."""
    return rep.fill_form([str(f) for f in fields])


@mcp.tool()
def pdf_form_fields(pdf_path: str) -> dict:
    """List the fillable field names in a PDF form. Feed them to fill_form."""
    return rep.pdf_form_fields(pdf_path)


@mcp.tool()
def fill_pdf(pdf_path: str, values: dict, out_path: str = "") -> dict:
    """Write values into a PDF form, saving a NEW file — the user's original
    is never modified. Show them the filled copy for review; submitting or
    signing requires authorize_action on 'paperwork'."""
    return rep.fill_pdf(pdf_path, {str(k): str(v) for k, v in values.items()}, out_path)


@mcp.tool()
def vault_status() -> dict:
    """Where the user's secrets live (their platform keychain — Apple
    Keychain, Windows Credential Manager, etc.) and WHICH secrets exist, by
    name only. You never see a value and must never ask for one. To use a
    secret on a form, pass the token 'vault:<name>' — local code on the
    user's machine resolves it at write time. If a secret they need isn't
    stored yet, tell them to run: python connector/vault.py set <name>"""
    return rep.vault_status()


@mcp.tool()
def set_profile_field(field: str, value: str) -> dict:
    """Store one identity detail Jefferey may reuse on forms (name, address,
    phone, email, date of birth, employer...). Sensitive identifiers are
    refused by design. Ask before storing anything the user hasn't offered."""
    return rep.set_profile_field(field, value)


@mcp.tool()
def get_profile() -> dict:
    """Everything Jefferey can put on a form for this user. They own all of it."""
    return rep.get_profile()


@mcp.tool()
def forget_profile_field(field: str) -> dict:
    """Delete one profile detail. The right to erase is absolute."""
    return rep.forget_profile_field(field)


# ---------------------------------------------------------------- guardian
# Money that leaves without asking. Jefferey never moves money — he catches
# what moved, proves it, and helps the user get it back.
@mcp.tool()
def expect_charge(merchant: str, amount: float, cadence: str = "monthly",
                  authorized_recurring: bool = True, note: str = "") -> dict:
    """Register a charge the user has ACTUALLY agreed to (merchant, amount,
    cadence, and whether they ever authorized recurring billing). Anything
    not in this register becomes a question later, so build it up whenever
    a subscription or bill comes up in conversation."""
    return guard.expect_charge(merchant, amount, cadence, authorized_recurring, note)


@mcp.tool()
def mark_cancelled(merchant: str, on: str = "") -> dict:
    """The user cancelled something. Record it — any charge after this date
    is unauthorized, and that is the kind that goes unnoticed for years."""
    return guard.mark_cancelled(merchant, on)


@mcp.tool()
def check_charge(merchant: str, amount: float, date: str = "") -> dict:
    """Hold one charge up against what the user agreed to. Returns a verdict:
    expected / amount_increased / unexpected_merchant / charged_after_cancel /
    duplicate, in plain words, with the dollars at stake. Anything that isn't
    'expected' should be scored with record_opportunity (reduces_risk=True)
    and said out loud."""
    return guard.check_charge(merchant, amount, date)


@mcp.tool()
def review_statement(charges: list) -> dict:
    """Run a whole statement or transaction list through at once — each entry
    {merchant, amount, date}. This is where people find the money that has
    been quietly leaking for years. Report the total at stake."""
    return guard.review_statement([dict(c) for c in charges])


@mcp.tool()
def expected_charges() -> list:
    """What the user has agreed to pay, and what they've cancelled."""
    return guard.expected_charges()


@mcp.tool()
def dispute_pack(merchant: str) -> dict:
    """Assemble everything needed to get money back from one merchant: what
    was authorized, every disputed charge, and how to write the demand. The
    user should never be the one digging through statements at 11pm."""
    return guard.dispute_pack(merchant)


# ---------------------------------------------------------------- the life layer
# The Digital Conscience proper: who this person IS, so Jefferey can
# represent them now and tell their story later.
@mcp.tool()
def add_person(name: str, relationship: str, notes: str = "",
               important_dates: str = "") -> dict:
    """Record someone who matters to the user (family, friends, the people
    they'd want remembered). Only when they offer it — never interrogate."""
    return life.add_person(name, relationship, notes, important_dates)


@mcp.tool()
def add_memory(text: str, when: str = "", people: str = "", tags: str = "",
               visibility: str = "private") -> dict:
    """Record a snippet of the user's life in their own words — a moment, a
    turning point, a lesson, a joke only their family gets. visibility:
    'private' (Jefferey only), 'family' (may be shared with named people),
    'legacy' (meant to outlive them). Never invent one; only record what
    they actually said."""
    return life.add_memory(text, when, people, tags, visibility)


@mcp.tool()
def add_media(path: str, caption: str = "", when: str = "", people: str = "",
              visibility: str = "private") -> dict:
    """Reference a photo or recording WHERE IT ALREADY LIVES — on the user's
    own Self-Cloud drive. Jefferey stores the path and caption, never a copy
    and never an upload. If the drive is off, it simply reads unreachable."""
    return life.add_media(path, caption, when, people, visibility)


@mcp.tool()
def who_am_i(include: str = "private") -> dict:
    """What Jefferey understands about this person as a human being: the
    people who matter, the moments recorded, the pictures, and what they
    value. Speak from this — never invent a memory or a feeling."""
    return life.who_am_i(include)


@mcp.tool()
def tell_story(theme: str = "", audience: str = "family") -> dict:
    """Gather what's needed to tell a piece of this person's story — for them
    now, or for the people they named, later. audience: 'self', 'family', or
    'legacy' (each sees only what the user permitted). Tell it in their
    voice, in order, using only what is here."""
    return life.tell_story(theme, audience)


@mcp.tool()
def story_gaps() -> dict:
    """What's missing from their story, so you can gently ask for it while
    there is still time. Ask for at most ONE at a time, at the right moment.
    Never pressure them."""
    return life.story_gaps()


@mcp.tool()
def forget_life(contains: str) -> dict:
    """Erase anything in the life layer matching this text — people, moments,
    media references. Never argued with."""
    return life.forget_life(contains)


if __name__ == "__main__":
    mcp.run()
