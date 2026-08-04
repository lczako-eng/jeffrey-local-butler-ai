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

mcp = _Server("jefferey")
conscience = Conscience()

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


if __name__ == "__main__":
    mcp.run()
