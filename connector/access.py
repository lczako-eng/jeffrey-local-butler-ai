"""
THE DOOR — bound client identity and a real gate
================================================

Before this module, Self-Cloud's scopes were a *calculator the model was
politely asked to consult*: `check_access` existed as a tool the host model
could call if it felt like it, no data function called it internally, and
`who_am_i(include="private")` took the trust level as an argument the model
itself supplied — defaulting to the most permissive value. A plain Claude
Desktop session could ask for everything and get it.

Three rules fix that, and they are the whole of this file:

1. **Identity is bound to the process, never chosen per call.**
   `JEFFEREY_CLIENT=claude-raw python connector/jefferey_mcp.py` and that
   server IS claude-raw for its whole life. The model cannot say otherwise,
   because there is no argument left for it to say it with.

2. **The gate is structural.** `@gate("life.read")` sits under the tool
   registration. A denial raises; it does not return a polite dict the model
   can narrate its way around.

3. **Widening needs the owner's own hands.** Narrowing a key (revoke, remove
   a scope) is always allowed. *Widening* one — granting, adding a scope,
   raising a permission level — requires `JEFFEREY_OWNER_CONSOLE=1`, which
   the owner's terminal sets and an MCP host config does not. Jefferey can
   never widen Jefferey.

The visibility ceiling for the life layer is derived here too, from the
bound key's scopes, so `who_am_i` and `tell_story` no longer take an
audience parameter at all.
"""

from __future__ import annotations

import functools
import os
import sys
from contextvars import ContextVar

# The identity used when nothing says otherwise, and it is deliberately the
# narrow one: anything a host model launches is a GUEST until the owner says
# otherwise. The owner's own terminal (jefferey_chat.py) binds 'jefferey'
# explicitly, and an MCP host that should hold the caretaker key says so:
#     "env": { "JEFFEREY_CLIENT": "jefferey" }
DEFAULT_CLIENT = "claude-raw"

# Scope needed to see each level of the life layer, widest first.
_CEILINGS = (("life.read", "private"), ("family.read", "family"),
             ("legacy.read", "legacy"))

# Set per-request by surfaces that serve more than one client (HTTP).
_request_client: ContextVar[str | None] = ContextVar("jefferey_client", default=None)


# The canonical scope table: which key each tool needs. The MCP and HTTP
# surfaces carry `@gate(...)` decorators that mirror this; `selftest` asserts
# the two agree, so they cannot drift apart unnoticed.
TOOL_SCOPES: dict[str, str] = {
    # values and how they are learned
    "record_correction": "priorities.write", "set_priority": "priorities.write",
    "explain_basis": "priorities.read", "priorities_for": "priorities.read",
    "draft_guidance": "priorities.read",
    # facts, profile, rules, the daily brief
    "get_conscience": "facts.read", "remember_fact": "facts.write",
    "forget": "facts.write", "get_profile": "facts.read",
    "set_profile_field": "facts.write", "forget_profile_field": "facts.write",
    "fill_form": "facts.read", "fill_pdf": "facts.read", "action_log": "facts.read",
    "conscience_include": "facts.write", "conscience_exclude": "facts.write",
    "set_rule": "facts.write", "remove_rule": "facts.write",
    "list_rules": "facts.read", "daily_brief": "facts.read",
    # goals and the opportunity engine
    "add_goal": "goals.write", "close_goal": "goals.write",
    "log_observation": "goals.write", "record_opportunity": "goals.read",
    "resolve_opportunity": "goals.write",
    # money
    "expect_charge": "money.write", "mark_cancelled": "money.write",
    "check_charge": "money.read", "review_statement": "money.read",
    "expected_charges": "money.read", "dispute_pack": "money.read",
    # the life layer (who_am_i and tell_story use ceiling() instead)
    "add_person": "life.write", "add_memory": "life.write", "add_media": "life.write",
    "story_gaps": "life.read", "forget_life": "life.write",
    "next_question": "life.read", "record_answer": "life.write",
    "interview_progress": "life.read",
    # The owner's own rules about who may hear what. A REFUSAL that quotes
    # the rule is itself the disclosure — these were ungated and returned the
    # most sensitive sentences in the system verbatim.
    "check_disclosure": "facts.read", "guidance_for": "facts.read",
    # Returns the owner's relevant priorities alongside the verdict, which is
    # the same payload the gated explain_basis refuses.
    "triage_message": "priorities.read",
    # A write into the owner's audit trail. An ungated write is a forgery.
    "log_action": "facts.write",
    # the album: asking about his photographs and keeping what he says
    "next_story_prompt": "life.read", "record_story": "life.write",
    "decline_story": "life.write", "story_progress": "life.read",
    # secrets: names only, never values
    "vault_status": "vault.names",
    # the egress door's own report: counts and destinations
    "what_left_the_house": "facts.read",
}

# Tools that WIDEN what an AI may do. Narrowing (revoke, remove_scope) never
# needs the owner's console; widening always does.
OWNER_ONLY_TOOLS = frozenset({"set_permission", "selfcloud_grant",
                              "selfcloud_add_scope"})


class AccessDenied(PermissionError):
    """This client's key does not carry the scope this call needs."""


class OwnerOnly(PermissionError):
    """A widening action was attempted outside the owner's own console."""


class Gate:
    """The door. One per process, holding the bound client identity."""

    def __init__(self, cloud, client: str, announce: bool = True):
        self.cloud = cloud
        self.client = (client or DEFAULT_CLIENT).strip().lower()
        self._provisioned: set[str] = set()
        if announce:
            self.announce()

    # -- setup ------------------------------------------------------------
    def _effective_scopes(self) -> list[str]:
        """What this client's key holds — stored grant if there is one, else
        the preset it WOULD get. Read-only: works out the answer without
        writing anything."""
        from selfcloud import PRESETS

        g = self.cloud.c.data.get("selfcloud_grants", {}).get(self.client)
        if g is not None:
            return list(g["scopes"]) if g.get("active") else []
        return list(PRESETS.get(self.client, {}).get("scopes", []))

    def _provision(self, client: str | None = None) -> None:
        """Issue a client its preset key, once, on FIRST REAL USE.

        Deliberately lazy. Starting a process must not write to the person's
        conscience — importing a module, running a self-test, or launching a
        server the user never speaks to should leave the file untouched, and
        its revision number should mean 'things actually happened'. The first
        scoped call is a real access event and is worth recording; a startup
        is not.

        The client is whichever identity is making THIS call: the process
        default, or the one an HTTP token bound for the request. (An earlier
        version only ever provisioned the process default, so on the HTTP
        surface every per-token key was denied as 'never granted'.)
        """
        from selfcloud import PRESETS

        client = client or self.client
        if client in self._provisioned:
            return
        self._provisioned.add(client)
        grants = self.cloud.c.data.get("selfcloud_grants", {})
        if client in grants:
            return
        if client not in PRESETS:
            print(f"\n  ⚠  JEFFEREY_CLIENT={client!r} has no key and no preset.\n"
                  f"     Every scoped call will be denied until the owner runs:\n"
                  f"       selfcloud_grant('{client}', [...])\n",
                  file=sys.stderr)
            return
        self.cloud.grant(client, note="auto-issued from its preset on "
                                      "first use; the owner may narrow it")

    def announce(self) -> None:
        scopes = self._effective_scopes()          # no write on startup
        print(f"  Jefferey is running as '{self.client}' "
              f"({len(scopes)} scope{'s' if len(scopes) != 1 else ''}: "
              f"{', '.join(scopes) or 'none'})."
              f"{'' if os.environ.get('JEFFEREY_CLIENT') else '  [default]'}",
              file=sys.stderr)

    # -- the gate ---------------------------------------------------------
    def current_client(self) -> str:
        return _request_client.get() or self.client

    def check(self, scope: str) -> dict:
        client = self.current_client()
        self._provision(client)
        return self.cloud.check_access(client, scope)

    def require(self, scope: str) -> None:
        verdict = self.check(scope)
        if not verdict["allowed"]:
            raise AccessDenied(
                f"'{verdict['client']}' may not do this: {verdict['reason']}. "
                f"The owner can widen this key from their own console; "
                f"Jefferey cannot, and will not ask you to work around it."
            )

    def ceiling(self) -> str:
        """How deep into the life layer this key may see: private > family >
        legacy. Derived from the key, never from an argument."""
        client = self.current_client()
        self._provision(client)
        for scope, level in _CEILINGS:
            if self.cloud.check_access(client, scope, log=False)["allowed"]:
                self.cloud._log(client, "check", f"life ceiling: {level}", True)
                return level
        self.cloud._log(client, "check", "life ceiling", False)
        raise AccessDenied(
            f"'{client}' holds no key to this person's life layer "
            f"(needs life.read, family.read or legacy.read)."
        )


# Module-level singleton, set once at startup by each surface.
GATE: Gate | None = None


def bind(cloud, client: str | None = None, announce: bool = True) -> Gate:
    """Bind this process to one client identity. Call once, at startup."""
    global GATE
    GATE = Gate(cloud, client or os.environ.get("JEFFEREY_CLIENT", DEFAULT_CLIENT),
                announce=announce)
    return GATE


def provision(cloud, clients) -> None:
    """Make sure each named client has its preset key, without changing which
    identity this process is bound to. For surfaces that serve several clients."""
    for c in clients:
        Gate(cloud, c, announce=False)


def use_client(client: str):
    """Bind an identity for the duration of one request (HTTP, where a single
    process legitimately serves several clients). Returns the ContextVar token."""
    return _request_client.set(client.strip().lower())


def reset_client(token) -> None:
    _request_client.reset(token)


def current_client() -> str:
    return GATE.current_client() if GATE else DEFAULT_CLIENT


def ceiling() -> str:
    if GATE is None:
        raise AccessDenied("no client identity is bound; refusing to guess one")
    return GATE.ceiling()


def gate(scope: str):
    """Decorator. Put it *under* the tool registration:

        @mcp.tool()
        @gate("life.read")
        def story_gaps() -> dict: ...
    """
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            if GATE is None:
                raise AccessDenied(
                    "no client identity is bound; refusing to serve owner data"
                )
            GATE.require(scope)
            return fn(*args, **kwargs)
        inner.__jefferey_scope__ = scope
        return inner
    return wrap


def owner_only(fn):
    """Decorator for actions that WIDEN authority — granting a key, adding a
    scope, raising a permission level. Narrowing never needs this."""
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        if os.environ.get("JEFFEREY_OWNER_CONSOLE") != "1":
            raise OwnerOnly(
                f"{fn.__name__} widens what an AI is allowed to do, so it runs "
                "only from the owner's own console (JEFFEREY_OWNER_CONSOLE=1). "
                "Tell the owner what you would need and why — then stop. "
                "Jefferey never widens Jefferey."
            )
        return fn(*args, **kwargs)
    inner.__jefferey_owner_only__ = True
    return inner
