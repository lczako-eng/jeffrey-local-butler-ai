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

3. **Widening needs the owner's own hands.** *Widening* a key or an
   authority — granting, adding a scope, raising a permission level — is
   never a tool any engine is offered, on any surface. The owner types it
   (/permit, /grant … in 'Talk to JEFFEREY on this Mac') and confirms it at
   the keyboard; only that code path holds the owner console, and it holds it
   IN THIS PROCESS (`owner_console()`), never in an environment variable a
   model's process could inherit. (Before the October 2026 stress test the
   console was `JEFFEREY_OWNER_CONSOLE=1`, which the terminal set for its
   whole life — so the model there could raise its own authority. MCP and
   HTTP now refuse to start when that variable is set at all.)
   A key may give up its OWN authority from anywhere (revoke itself, drop one
   of its own scopes); narrowing ANOTHER key is the owner's decision too.
   Jefferey can never widen Jefferey.

The visibility ceiling for the life layer is derived here too, from the
bound key's scopes, so `who_am_i` and `tell_story` no longer take an
audience parameter at all.
"""

from __future__ import annotations

import functools
import os
import sys
from contextlib import contextmanager
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

# The owner's own hands, in this process only: set by owner_console() around
# a command the owner typed and confirmed at his keyboard. Never read from
# the environment, so no process (and no model) can inherit it.
_owner_hands: ContextVar[bool] = ContextVar("jefferey_owner_hands", default=False)

# Who the owner is, in the logs, when he acts with his own hands.
OWNER = "owner"
# Who acts when no engine is bound to this process at all (the owner's own
# command-line tools, or a test): there is no AI on the other end.
LOCAL = "local"


# The canonical scope table: which key each tool needs. The MCP and HTTP
# surfaces carry `@gate(...)` decorators that mirror this; `selftest` asserts
# the two agree, so they cannot drift apart unnoticed.
TOOL_SCOPES: dict[str, str] = {
    # values and how they are learned
    "record_correction": "priorities.write", "set_priority": "priorities.write",
    "explain_basis": "priorities.read", "priorities_for": "priorities.read",
    "draft_guidance": "priorities.read",
    # reads a draft against his rules and his safety; keeps nothing (I-24)
    "check_draft": "priorities.read",
    # facts, profile, rules, the daily brief
    "get_conscience": "facts.read", "remember_fact": "facts.write",
    "forget": "facts.write", "get_profile": "facts.read",
    "set_profile_field": "facts.write", "forget_profile_field": "facts.write",
    "fill_form": "facts.read", "action_log": "facts.read",
    # PDF forms on this computer: reading one, and saving a filled copy in the
    # 'Filled forms' folder. A write to the owner's disk, so never under a
    # read scope (I-02: fill_pdf was 'facts.read' and pdf_form_fields had no
    # gate, so a plain guest session overwrote photos, the record of what
    # left the house and the memory file itself). Only the caretaker holds it.
    "fill_pdf": "paperwork.write", "pdf_form_fields": "paperwork.write",
    "conscience_include": "facts.write", "conscience_exclude": "facts.write",
    "set_rule": "facts.write", "remove_rule": "facts.write",
    "list_rules": "facts.read", "daily_brief": "facts.read",
    # goals and the opportunity engine. record_opportunity SAVES an item that
    # can open the owner's daily brief, so it is a write (it was goals.read,
    # and a plain guest session planted a fake fraud alert there — I-40).
    "add_goal": "goals.write", "close_goal": "goals.write",
    "log_observation": "goals.write", "record_opportunity": "goals.write",
    "resolve_opportunity": "goals.write",
    # ...and the read-only half: score an idea without saving it.
    "score_opportunity": "goals.read",
    # THE gate for acting in the world. Only the acting caretaker holds this
    # scope; a guest, family, executor, revoked or unknown key gets no answer
    # at all (it used to be ungated — I-06).
    "authorize_action": "act.request",
    # money
    "expect_charge": "money.write", "mark_cancelled": "money.write",
    "check_charge": "money.read", "review_statement": "money.read",
    "expected_charges": "money.read", "dispute_pack": "money.read",
    # the life layer (who_am_i and tell_story use ceiling() instead)
    "add_person": "life.write", "add_memory": "life.write", "add_media": "life.write",
    "story_gaps": "life.read", "forget_life": "life.write",
    # one person, by id: notes added to, never replaced (I-27)
    "update_person": "life.write",
    # who may see something: narrowing from any key that may write; widening
    # is the owner's own /share, whatever key asks (I-26)
    "set_visibility": "life.write",
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

# Actions that WIDEN what an AI may do. None of them is a tool on any surface
# any more: the owner types them at his own keyboard (/permit, /grant, /scope
# add in 'Talk to JEFFEREY on this Mac'). The names are kept so every surface
# can refuse them in plain words, and so a test can prove they stay absent.
OWNER_ONLY_TOOLS = frozenset({"set_permission", "selfcloud_grant",
                              "selfcloud_add_scope"})

# Narrowing tools: a key may narrow ITSELF from anywhere; narrowing another
# key needs the owner's own hands (I-09).
NARROWING_TOOLS = frozenset({"selfcloud_revoke", "selfcloud_remove_scope"})

# Tools that change something. The egress door writes its record of the call
# BEFORE one of these runs, so a log that cannot be written stops the change
# (I-12) instead of letting it land unrecorded.
WRITE_TOOLS = frozenset(
    {t for t, s in TOOL_SCOPES.items() if s.endswith(".write") or s == "act.request"}
    | NARROWING_TOOLS)


def owner_only_refusal(tool: str) -> dict:
    """What an engine is told when it asks for a widening action."""
    return {"refused": True, "tool": tool,
            "reason": ("Raising a permission or giving out a key is never done by "
                       "an AI. Only the owner can do it, typing it himself at his "
                       "own keyboard in 'Talk to JEFFEREY on this Mac' (for example "
                       "/permit groceries act 100 per week)."),
            "tell_the_user": ("Tell the owner, in plain words, what you would need "
                              "and why, and that only he can allow it by typing it "
                              "himself. Then stop; do not try another way.")}


class AccessDenied(PermissionError):
    """This client's key does not carry the scope this call needs."""


class OwnerOnly(PermissionError):
    """A widening action was attempted outside the owner's own console."""


def refusal(tool: str, exc: Exception) -> dict:
    """An access refusal as a RESULT the model must report — never a bare
    'Error executing tool' (the MCP SDK reduces any exception to that, so a
    key mistake looked like a crash — I-64)."""
    if isinstance(exc, OwnerOnly):
        tell = ("Tell the owner plainly that only he can allow this, typing it "
                "himself at his own keyboard, and what you would need and why. "
                "Then stop; do not try another way.")
    else:
        tell = ("Say plainly that the key this connection holds does not allow "
                "this, and do not attempt it another way. If the owner expected "
                "it to work, the key's name in this connection's settings may be "
                "misspelled, or the owner may need to widen it himself.")
    return {"refused": True, "tool": tool, "reason": str(exc), "tell_the_user": tell}


class Gate:
    """The door. One per process, holding the bound client identity."""

    def __init__(self, cloud, client: str, announce: bool = True):
        self.cloud = cloud
        self.client = (client or DEFAULT_CLIENT).strip().lower()
        # (store, client): a key issued in one store is not issued in another —
        # the life moves to the drive when it is plugged in (I-08).
        self._provisioned: set[tuple[str, str]] = set()
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

        from conscience import ConscienceConflict

        client = client or self.client
        done = (str(getattr(self.cloud.c, "path", "")), client)
        if done in self._provisioned:
            return
        grants = self.cloud.c.data.get("selfcloud_grants", {})
        if client in grants:
            self._provisioned.add(done)
            return
        if client not in PRESETS:
            self._provisioned.add(done)
            print(f"\n  ⚠  JEFFEREY_CLIENT={client!r} has no key and no preset.\n"
                  f"     Every scoped call will be refused until the owner types, in\n"
                  f"     'Talk to JEFFEREY on this Mac':  /grant {client} <scopes>\n",
                  file=sys.stderr)
            return
        # Marked provisioned only once the key is SAVED. An earlier version
        # marked it first, so a grant that lost a race with another engine's
        # write was never retried: every later call was refused as 'never
        # granted' until the app was restarted. One retry, after re-reading.
        # (`auto=True`: issuing a preset exactly as written is not widening,
        # so it does not need the owner's hands; nothing else may pass it.)
        try:
            self.cloud.grant(client, note="auto-issued from its preset on "
                                          "first use; the owner may narrow it",
                             auto=True)
        except ConscienceConflict:
            self.cloud.c.refresh()
            if client not in self.cloud.c.data.get("selfcloud_grants", {}):
                self.cloud.grant(client, note="auto-issued from its preset on "
                                              "first use; the owner may narrow it",
                                 auto=True)
        self._provisioned.add(done)

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
                f"The key this connection holds ('{verdict['client']}') does not "
                f"allow this: {verdict['reason']}. Only the owner can change a key, "
                f"at his own keyboard; JEFFEREY cannot, and will not ask you to "
                f"work around it."
            )

    def may(self, scope: str, client: str | None = None) -> bool:
        """Does this key hold `scope`? A question, not an access event: it
        decides what a result may contain, and writes nothing."""
        if client is None:
            client = self.current_client()
            self._provision(client)
        return bool(self.cloud.check_access(client, scope, log=False)["allowed"])

    def live(self, client: str | None = None) -> dict | None:
        """The caller's key if it exists and is switched on, else None."""
        client = client or self.current_client()
        self._provision(client)
        g = self.cloud.c.data.get("selfcloud_grants", {}).get(client)
        return g if isinstance(g, dict) and g.get("active") else None

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


# ------------------------------------------------------------ the owner's hands
@contextmanager
def owner_console():
    """The owner, at his own keyboard, has typed a command and confirmed it.
    Only code that read that confirmation from a person (jefferey_chat's
    /permit, /grant …) enters this block. It lives in this process alone."""
    tok = _owner_hands.set(True)
    try:
        yield
    finally:
        _owner_hands.reset(tok)


def is_owner_console() -> bool:
    return _owner_hands.get()


def who() -> str:
    """Who is acting, for the record: the owner with his own hands, the key
    bound to this call, or — with no engine bound to this process at all — a
    local tool of the owner's."""
    if is_owner_console():
        return OWNER
    if GATE is None:
        return LOCAL
    return GATE.current_client()


def may(scope: str) -> bool:
    """Does the caller's key hold `scope`? The owner and local tools (no
    engine bound) may see everything; writes nothing."""
    if owners_hands():
        return True
    try:
        return GATE.may(scope)
    except Exception:
        return False


def is_caretaker(client: str | None) -> bool:
    """The owner, a local tool, or a key the owner made a caretaker (one that
    holds act.request — the 'jefferey' preset does). Only these may raise an
    interrupt in the owner's brief."""
    c = (client or "").strip().lower()
    if c in (OWNER, LOCAL):
        return True
    if GATE is None or not c:
        return False
    try:
        return GATE.may("act.request", client=c)
    except Exception:
        return False


def owners_hands() -> bool:
    """True when no AI can be on the other end of this call: the owner typed
    and confirmed it (owner_console), or no engine is bound to this process
    at all (the owner's own command-line tools). Every surface an engine can
    reach binds a gate at start-up, so there this is only ever the console."""
    return is_owner_console() or GATE is None


def require_owners_hands(what: str) -> None:
    """Widening — a key, a scope, a permission — is never done because an AI
    asked (I-04). The surfaces no longer offer it at all; this is the same
    rule once more, where the change is actually made."""
    if not owners_hands():
        raise OwnerOnly(
            f"Only the owner can {what}, typing it himself at his own keyboard in "
            f"'Talk to JEFFEREY on this Mac'. Tell him what you would need and "
            f"why, then stop. JEFFEREY never widens JEFFEREY.")


def require_live() -> dict:
    """The caller's key must exist and be switched on. A revoked or unknown
    key is dead everywhere — it does not even get to read the key list or the
    access log (I-09: a revoked key still read both and revoked others)."""
    if owners_hands():
        return {}
    g = GATE.live()
    if g is None:
        me = GATE.current_client()
        stored = GATE.cloud.c.data.get("selfcloud_grants", {}).get(me)
        why = (f"it was switched off by the owner on {stored.get('revoked_on')}"
               if isinstance(stored, dict) else "the owner never gave out a key by that name")
        raise AccessDenied(
            f"The key this connection holds ('{me}') does not work: {why}. If the "
            f"owner expected it to work, the key's name in this connection's "
            f"settings may be misspelled.")
    return g


def require_self_or_owner(target: str, tool: str = "") -> None:
    """A key may give up its own authority from anywhere; narrowing ANOTHER
    key is the owner's decision (I-09: a guest revoked the caretaker, the
    family key and the executor's legacy key)."""
    if owners_hands():
        return
    me = current_client()
    if (target or "").strip().lower() != me:
        raise OwnerOnly(
            f"This connection holds the '{me}' key, and a key may only give up "
            f"its OWN access. Changing the '{(target or '').strip().lower()}' key "
            f"is the owner's decision: he does it himself, typing /revoke or "
            f"/scope at his own keyboard in 'Talk to JEFFEREY on this Mac'.")


def surface() -> str:
    """Which door this call came through, for the record."""
    if is_owner_console():
        return "owner's terminal"
    try:
        import egress
        return egress._SURFACE or "local"
    except Exception:
        return "local"


def owner_console_env_set() -> bool:
    return os.environ.get("JEFFEREY_OWNER_CONSOLE", "").strip() not in ("", "0")


def refuse_owner_console_env(surface: str) -> None:
    """MCP and HTTP serve engines, never the owner's own hands. A host config
    that sets the old owner-console variable is a mistake (or an attack) —
    refuse to start, loudly, rather than run with it (I-43)."""
    if owner_console_env_set():
        sys.exit(
            f"JEFFEREY will not start the {surface} connection: the setting "
            f"JEFFEREY_OWNER_CONSOLE is switched on for it. That setting would let "
            f"the AI on the other end change its own permissions. Remove it from "
            f"this connection's settings and start again. Raising a permission is "
            f"something the owner types himself, in 'Talk to JEFFEREY on this Mac'.")


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
    scope, raising a permission level. They run only inside owner_console(),
    which nothing but a command the owner typed and confirmed ever enters
    (or in a process with no engine bound at all — the owner's own tools).
    The environment is not consulted: a variable can be inherited by any
    process, including one a model drives."""
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        if not owners_hands():
            raise OwnerOnly(
                f"{fn.__name__} widens what an AI is allowed to do, so only the "
                "owner can do it, typing it himself at his own keyboard. Tell the "
                "owner what you would need and why — then stop. JEFFEREY never "
                "widens JEFFEREY."
            )
        return fn(*args, **kwargs)
    inner.__jefferey_owner_only__ = True
    return inner
