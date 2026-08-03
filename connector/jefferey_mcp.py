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


if __name__ == "__main__":
    mcp.run()
