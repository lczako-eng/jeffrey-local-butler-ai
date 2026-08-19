"""
JEFFEREY — the runnable Shadow
==============================

Talk to Jefferey. This is the whole thesis running in one terminal:
a rented reasoning engine (Claude, via the Anthropic API) wearing the
Jefferey Directive Pack, wired live into the OWNED conscience store
(~/.jefferey/conscience.json). Override him and he learns why. Quit,
come back, switch engines — he still knows you.

Run:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...     # or an already-authed environment
    python connector/jefferey_chat.py

    python connector/jefferey_chat.py --once "Who are you?"
    python connector/jefferey_chat.py --selftest   # offline: no API key needed

In-chat commands:
    /conscience   show everything Jefferey knows (you own every byte)
    /quit         leave (the conscience stays)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from conscience import Conscience
from representative import Representative

MODEL = "claude-opus-5"
MAX_TOKENS = 4096

DIRECTIVES = (Path(__file__).parent / "directives.md").read_text()

conscience = Conscience()
rep = Representative(conscience)


# --------------------------------------------------------------------- tools
# The same conscience surface the MCP connector exposes, as client-side
# tools. The engine reasons; every durable byte lands in the user's store.

TOOLS = [
    {
        "name": "record_correction",
        "description": (
            "THE core learning act. The user overrode a recommendation — learn "
            "WHY. Record which value they were protecting and which they traded "
            "away in this context. Consistent evidence raises confidence; "
            "contradictions erode and can flip the hierarchy. Tell the user "
            "what you learned and the confidence you now hold."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "context": {"type": "string", "description": "e.g. 'travel', 'phone plan'"},
                "what_was_suggested": {"type": "string"},
                "what_user_chose": {"type": "string"},
                "value_protected": {"type": "string", "description": "e.g. 'reliability'"},
                "value_traded_away": {"type": "string", "description": "e.g. 'lowest price'"},
            },
            "required": [
                "context", "what_was_suggested", "what_user_chose",
                "value_protected", "value_traded_away",
            ],
        },
    },
    {
        "name": "set_priority",
        "description": (
            "The user explicitly stated a priority (e.g. context='travel', "
            "higher='direct flights', lower='saving money'). Store it with the "
            "given confidence (0-1). Use record_correction instead when "
            "learning from an override."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "context": {"type": "string"},
                "higher": {"type": "string"},
                "lower": {"type": "string"},
                "confidence": {"type": "number", "default": 0.6},
            },
            "required": ["context", "higher", "lower"],
        },
    },
    {
        "name": "remember_fact",
        "description": (
            "Remember a durable FACT about the user (people, dates, situations, "
            "constraints). Facts are stored separately from values. Ask before "
            "remembering anything sensitive."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string"},
                "category": {"type": "string", "default": "general"},
            },
            "required": ["fact"],
        },
    },
    {
        "name": "forget",
        "description": (
            "Delete every remembered fact containing this text. The user's "
            "right to erase is absolute — never argue, always confirm what "
            "was removed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"contains": {"type": "string"}},
            "required": ["contains"],
        },
    },
    {
        "name": "explain_basis",
        "description": (
            "Before recommending anything, fetch the user's OWN priorities and "
            "facts relevant to this topic, and ground the recommendation "
            "strictly in what this returns. If it returns nothing relevant, "
            "say you don't yet know their values here, and ask."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    },
    {
        "name": "priorities_for",
        "description": (
            "List the user's learned priority hierarchy, highest confidence "
            "first, optionally filtered to a context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"context": {"type": "string", "default": ""}},
        },
    },
    {
        "name": "add_goal",
        "description": (
            "Register a long-term goal the user has approved. Goals drive the "
            "Opportunity Engine: what can be done today to move these forward, "
            "within permissions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"goal": {"type": "string"}},
            "required": ["goal"],
        },
    },
    {
        "name": "close_goal",
        "description": "Mark active goals containing this text as done/retired.",
        "input_schema": {
            "type": "object",
            "properties": {"contains": {"type": "string"}},
            "required": ["contains"],
        },
    },
    {
        "name": "set_permission",
        "description": (
            "ONLY when the user explicitly grants or changes authority, in "
            "their own words. Levels: 'observe' (watch and learn), 'recommend' "
            "(bring ranked options — the default), 'act' (execute in this "
            "category, optionally under a spending cap). Never call this on "
            "your own initiative — Jefferey never expands his own permissions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "level": {"type": "string", "enum": ["observe", "recommend", "act"]},
                "cap": {"type": "number"},
            },
            "required": ["category", "level"],
        },
    },
    {
        "name": "authorize_action",
        "description": (
            "THE gate. Call before doing anything in the real world on the "
            "user's behalf. Returns allowed true/false with the reason. If "
            "denied, recommend instead — only the user can raise the level. "
            "Denials are logged."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "description": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["category", "description"],
        },
    },
    {
        "name": "log_action",
        "description": (
            "Write down an act just performed on the user's behalf. No silent "
            "actions, ever — the log lives in the user's own store."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "description": {"type": "string"},
                "outcome": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["category", "description", "outcome"],
        },
    },
    {
        "name": "action_log",
        "description": "The audit trail: recent acts, denials, and permission changes, newest first.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 20}},
        },
    },
    {
        "name": "log_observation",
        "description": (
            "Note something observed that might matter later (a price change, "
            "a renewal approaching, a pattern). Observations feed the "
            "Opportunity Engine."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note": {"type": "string"},
                "category": {"type": "string", "default": "general"},
            },
            "required": ["note"],
        },
    },
    {
        "name": "record_opportunity",
        "description": (
            "Score a way to make the user's life better against THEIR "
            "priorities: value ('saves $380/yr'), which learned priority it "
            "aligns with, which goal it advances, whether it reduces risk, "
            "urgency 0-1. Returns the score: interrupt (>=0.75), daily brief "
            "(>=0.40), or hold. Only interrupt when it says to."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "what": {"type": "string"},
                "value_estimate": {"type": "string"},
                "aligns_with": {"type": "string"},
                "advances_goal": {"type": "string"},
                "reduces_risk": {"type": "boolean", "default": False},
                "urgency": {"type": "number", "default": 0.5},
            },
            "required": ["what"],
        },
    },
    {
        "name": "resolve_opportunity",
        "description": "Close pending opportunities containing this text (acted on, declined, or expired).",
        "input_schema": {
            "type": "object",
            "properties": {
                "contains": {"type": "string"},
                "outcome": {"type": "string", "default": "done"},
            },
            "required": ["contains"],
        },
    },
    {
        "name": "daily_brief",
        "description": (
            "One screen: orb mood (the engine's real state), active goals, "
            "pending opportunities ranked by score, recent actions and "
            "observations. Open with this when the user asks what's new."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "orb_state",
        "description": (
            "The predictive cycle: the mood the orb should show right now — "
            "protective, charged, curious, happy, thinking, or calm — and why."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "triage_message",
        "description": (
            "Read an incoming message the way a good friend would: what does "
            "it want, does it matter by THIS person's priorities, and is "
            "anyone trying to take advantage of them? Returns a verdict "
            "(likely_scam / suspicious / money_watch / needs_decision / "
            "routine), the predatory tactics spotted in plain words, amounts "
            "and deadlines, and their relevant values. Never reply, click, "
            "pay, or unsubscribe on their behalf without authorize_action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sender": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["body"],
        },
    },
    {
        "name": "draft_guidance",
        "description": (
            "Call BEFORE writing anything in the user's name (an email, a "
            "letter, a complaint, a cancellation). Returns their voice, the "
            "priorities and facts that apply here, who to sign as, and the "
            "hard limits. Write the draft from this, then show it to them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "purpose": {"type": "string"},
                "recipient": {"type": "string"},
            },
            "required": ["purpose"],
        },
    },
    {
        "name": "fill_form",
        "description": (
            "Given a form's field labels (HTML, PDF, or paper), return what "
            "can be filled from the user's own profile and exactly what "
            "cannot. Never guess a value; sensitive identifiers always go "
            "back to the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"fields": {"type": "array", "items": {"type": "string"}}},
            "required": ["fields"],
        },
    },
    {
        "name": "pdf_form_fields",
        "description": "List the fillable field names in a PDF form.",
        "input_schema": {
            "type": "object",
            "properties": {"pdf_path": {"type": "string"}},
            "required": ["pdf_path"],
        },
    },
    {
        "name": "fill_pdf",
        "description": (
            "Write values into a PDF form, saving a NEW file — the original "
            "is never modified. Show the user the filled copy; submitting or "
            "signing requires authorize_action on 'paperwork'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pdf_path": {"type": "string"},
                "values": {"type": "object", "additionalProperties": {"type": "string"}},
                "out_path": {"type": "string"},
            },
            "required": ["pdf_path", "values"],
        },
    },
    {
        "name": "set_profile_field",
        "description": (
            "Store one identity detail for filling forms (name, address, "
            "phone, email, date of birth, employer...). Sensitive identifiers "
            "are refused by design. Ask before storing anything not offered."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"field": {"type": "string"}, "value": {"type": "string"}},
            "required": ["field", "value"],
        },
    },
    {
        "name": "get_profile",
        "description": "Everything Jefferey can put on a form for this user.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "forget_profile_field",
        "description": "Delete one profile detail. The right to erase is absolute.",
        "input_schema": {
            "type": "object",
            "properties": {"field": {"type": "string"}},
            "required": ["field"],
        },
    },
]


def dispatch_tool(name: str, args: dict) -> dict | list:
    """Route a tool call from the engine into the owned store."""
    if name == "record_correction":
        return conscience.record_correction(
            args["context"], args["what_was_suggested"], args["what_user_chose"],
            args["value_protected"], args["value_traded_away"],
        )
    if name == "set_priority":
        return conscience.set_priority(
            args["context"], args["higher"], args["lower"],
            args.get("confidence", 0.6),
        )
    if name == "remember_fact":
        return conscience.remember_fact(args["fact"], args.get("category", "general"))
    if name == "forget":
        return {"removed_facts": conscience.forget_fact(args["contains"])}
    if name == "explain_basis":
        return conscience.explain_basis(args["topic"])
    if name == "priorities_for":
        return conscience.priorities_for(args.get("context") or None)
    if name == "add_goal":
        return conscience.add_goal(args["goal"])
    if name == "close_goal":
        return {"closed": conscience.close_goal(args["contains"])}
    if name == "set_permission":
        return conscience.set_permission(
            args["category"], args["level"], args.get("cap"))
    if name == "authorize_action":
        return conscience.authorize_action(
            args["category"], args["description"], args.get("amount"))
    if name == "log_action":
        return conscience.log_action(
            args["category"], args["description"], args["outcome"], args.get("amount"))
    if name == "action_log":
        return conscience.action_log(args.get("limit", 20))
    if name == "log_observation":
        return conscience.log_observation(args["note"], args.get("category", "general"))
    if name == "record_opportunity":
        return conscience.record_opportunity(
            args["what"], args.get("value_estimate", ""), args.get("aligns_with", ""),
            args.get("advances_goal", ""), args.get("reduces_risk", False),
            args.get("urgency", 0.5))
    if name == "resolve_opportunity":
        return {"resolved": conscience.resolve_opportunity(
            args["contains"], args.get("outcome", "done"))}
    if name == "daily_brief":
        return conscience.daily_brief()
    if name == "orb_state":
        return conscience.orb_state()
    if name == "triage_message":
        return rep.triage_message(
            args.get("sender", ""), args.get("subject", ""), args["body"])
    if name == "draft_guidance":
        return rep.draft_guidance(args["purpose"], args.get("recipient", ""))
    if name == "fill_form":
        return rep.fill_form([str(f) for f in args["fields"]])
    if name == "pdf_form_fields":
        return rep.pdf_form_fields(args["pdf_path"])
    if name == "fill_pdf":
        return rep.fill_pdf(
            args["pdf_path"], {str(k): str(v) for k, v in args["values"].items()},
            args.get("out_path", ""))
    if name == "set_profile_field":
        return rep.set_profile_field(args["field"], args["value"])
    if name == "get_profile":
        return rep.get_profile()
    if name == "forget_profile_field":
        return rep.forget_profile_field(args["field"])
    raise ValueError(f"unknown tool: {name}")


# A quiet one-line trace so the user SEES the conscience working.
_TRACE = {
    "record_correction": lambda a, r: (
        f"learned: {r.get('higher')} > {r.get('lower')} "
        f"[{a.get('context')}] · confidence {r.get('confidence')}"
    ),
    "set_priority": lambda a, r: (
        f"stored: {r.get('higher')} > {r.get('lower')} "
        f"[{a.get('context')}] · confidence {r.get('confidence')}"
    ),
    "remember_fact": lambda a, r: f"remembered: {a.get('fact')}",
    "forget": lambda a, r: f"forgot {r.get('removed_facts')} fact(s) matching '{a.get('contains')}'",
    "explain_basis": lambda a, r: f"checking your values on: {a.get('topic')}",
    "priorities_for": lambda a, r: "reading your hierarchy",
    "add_goal": lambda a, r: f"goal registered: {a.get('goal')}",
    "close_goal": lambda a, r: f"closed {r.get('closed')} goal(s)",
    "set_permission": lambda a, r: (
        f"authority: {a.get('category')} → {a.get('level')}"
        + (f" (cap {a.get('cap')})" if a.get('cap') is not None else "")
    ),
    "authorize_action": lambda a, r: (
        f"{'✓ authorized' if r.get('allowed') else '✗ denied'}: "
        f"{a.get('description')} [{a.get('category')}]"
    ),
    "log_action": lambda a, r: f"acted: {a.get('description')} → {a.get('outcome')}",
    "action_log": lambda a, r: "reading the action log",
    "log_observation": lambda a, r: f"noticed: {a.get('note')}",
    "record_opportunity": lambda a, r: (
        f"opportunity [{r.get('status')} @ {r.get('score')}]: {a.get('what')}"
    ),
    "resolve_opportunity": lambda a, r: f"resolved {r.get('resolved')} opportunity(ies)",
    "daily_brief": lambda a, r: "assembling your brief",
    "orb_state": lambda a, r: f"orb: {r.get('mood')} — {r.get('reason')}",
    "triage_message": lambda a, r: (
        f"triaged [{r.get('verdict')}]: {a.get('subject') or a.get('sender') or 'message'}"
        + (f" · scam signals {r.get('scam_score')}" if r.get('scam_score') else "")
    ),
    "draft_guidance": lambda a, r: f"drafting on your behalf: {a.get('purpose')}",
    "fill_form": lambda a, r: f"form filled {r.get('coverage')} from your profile",
    "pdf_form_fields": lambda a, r: f"read {r.get('count')} PDF fields",
    "fill_pdf": lambda a, r: (
        f"wrote {r.get('written')}" if r.get("written") else f"pdf refused: {r.get('reason', r.get('error'))}"
    ),
    "set_profile_field": lambda a, r: (
        f"profile: {r.get('field')} = {r.get('value')}" if r.get("stored")
        else f"profile refused ({r.get('field')}) — sensitive, you enter that yourself"
    ),
    "get_profile": lambda a, r: "reading your profile",
    "forget_profile_field": lambda a, r: f"forgot profile field: {r.get('removed')}",
}


def system_prompt() -> str:
    snap = conscience.snapshot()
    return (
        DIRECTIVES
        + "\n\n## Live conscience (loaded this session — the user owns every byte)\n\n"
        + "```json\n" + json.dumps(snap, indent=2, ensure_ascii=False) + "\n```\n\n"
        + "The conscience tools write to this same store. Use them: corrections "
        + "are the curriculum, and anything worth keeping must be written down — "
        + "the engine forgets, the conscience does not."
    )


# ---------------------------------------------------------------- engine loop
DIM = "\033[2m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_turn(client, history: list) -> None:
    """One user turn: stream Jefferey's reply, executing conscience tools
    until the engine ends its turn."""
    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt(),
            tools=TOOLS,
            messages=history,
        ) as stream:
            started = False
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    if not started:
                        sys.stdout.write(f"\n{BOLD}{CYAN}Jefferey{RESET} ")
                        started = True
                    sys.stdout.write(event.delta.text)
                    sys.stdout.flush()
            msg = stream.get_final_message()
        if started:
            print()

        if msg.stop_reason == "refusal":
            print(f"{DIM}(the engine declined to continue this turn){RESET}")
            history.append({"role": "assistant", "content": msg.content})
            return

        history.append({"role": "assistant", "content": msg.content})
        if msg.stop_reason != "tool_use":
            return

        results = []
        for block in msg.content:
            if block.type != "tool_use":
                continue
            try:
                out = dispatch_tool(block.name, block.input)
                trace = _TRACE.get(block.name)
                if trace:
                    print(f"{DIM}  · {trace(block.input, out if isinstance(out, dict) else {})}{RESET}")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(out, ensure_ascii=False),
                })
            except Exception as e:  # a bad call must never kill the session
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"error: {e}",
                    "is_error": True,
                })
        history.append({"role": "user", "content": results})


def make_client():
    try:
        import anthropic
    except ImportError:
        sys.exit("The engine SDK is missing. Run:  pip install anthropic")
    client = anthropic.Anthropic()  # picks up ANTHROPIC_API_KEY / authed env
    if client.api_key is None and getattr(client, "auth_token", None) is None:
        sys.exit(
            "No engine credentials found.\n"
            "Set ANTHROPIC_API_KEY (https://console.anthropic.com), or run "
            "inside an already-authenticated environment. The conscience "
            "store works without it — only the rented intelligence needs "
            "a key. Try:  python connector/jefferey_chat.py --selftest"
        )
    return client


def chat(once: str | None = None) -> None:
    client = make_client()
    history: list = []

    snap = conscience.snapshot()
    print(f"{BOLD}JEFFEREY{RESET} — Personal AI Shadow™")
    print(f"{DIM}engine: {MODEL} (rented) · conscience: {snap['store_path']} (owned)")
    print(
        f"{DIM}he knows: {len(snap['priorities'])} priorities · "
        f"{len(snap['facts'])} facts · {len(snap['active_goals'])} active goals · "
        f"learned from {snap['corrections_learned_from']} corrections{RESET}"
    )

    if once is not None:
        history.append({"role": "user", "content": once})
        run_turn(client, history)
        return

    print(f"{DIM}/conscience shows the store · /quit leaves (he keeps what he learned){RESET}\n")
    while True:
        try:
            user = input(f"{BOLD}You{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Jefferey stays. See you next session.{RESET}")
            return
        if not user:
            continue
        if user.lower() in ("/quit", "/exit", "quit", "exit"):
            print(f"{DIM}Jefferey stays. See you next session.{RESET}")
            return
        if user.lower() == "/conscience":
            print(json.dumps(conscience.snapshot(), indent=2, ensure_ascii=False))
            continue
        history.append({"role": "user", "content": user})
        try:
            run_turn(client, history)
        except Exception as e:
            # Never lose the session to a transient engine error.
            print(f"{DIM}(engine error: {e} — your conscience is untouched; try again){RESET}")
            if history and history[-1]["role"] == "user" and isinstance(history[-1]["content"], str):
                history.pop()
        print()


# ------------------------------------------------------------------ selftest
def selftest() -> None:
    """Offline proof that the whole learning loop works — no API key needed.

    Simulates the engine's tool calls against a throwaway store and asserts
    the conscience learns, reinforces, erodes, and flips exactly as designed.
    """
    import tempfile

    global conscience
    with tempfile.TemporaryDirectory() as td:
        conscience = Conscience(Path(td) / "conscience.json")

        # 1. Every declared tool dispatches.
        for tool in TOOLS:
            name = tool["name"]
            sample = {
                "record_correction": {
                    "context": "travel", "what_was_suggested": "cheapest flight, 1 stop",
                    "what_user_chose": "direct flight, $120 more",
                    "value_protected": "direct flights", "value_traded_away": "saving money",
                },
                "set_priority": {"context": "family", "higher": "presence", "lower": "work"},
                "remember_fact": {"fact": "Daughter's recital is June 12", "category": "family"},
                "forget": {"contains": "nothing-matches-this"},
                "explain_basis": {"topic": "travel"},
                "priorities_for": {},
                "add_goal": {"goal": "cut monthly expenses 15%"},
                "close_goal": {"contains": "expenses"},
                "set_permission": {"category": "subscriptions", "level": "act", "cap": 50},
                "authorize_action": {
                    "category": "subscriptions",
                    "description": "cancel unused gym app", "amount": 12.99,
                },
                "log_action": {
                    "category": "subscriptions",
                    "description": "cancelled unused gym app", "outcome": "done",
                    "amount": 12.99,
                },
                "action_log": {},
                "log_observation": {"note": "streaming price rose to $22.99"},
                "record_opportunity": {
                    "what": "switch streaming plan", "value_estimate": "saves $96/yr",
                    "aligns_with": "saving money", "urgency": 0.4,
                },
                "resolve_opportunity": {"contains": "streaming"},
                "daily_brief": {},
                "orb_state": {},
                "triage_message": {
                    "sender": "billing@example.com", "subject": "Notice",
                    "body": "Your account balance is $42.00, due June 3.",
                },
                "draft_guidance": {"purpose": "cancel a subscription"},
                "fill_form": {"fields": ["First name", "Email"]},
                "pdf_form_fields": {"pdf_path": "/nonexistent.pdf"},
                "fill_pdf": {"pdf_path": "/nonexistent.pdf", "values": {"a": "b"}},
                "set_profile_field": {"field": "First name", "value": "Laszlo"},
                "get_profile": {},
                "forget_profile_field": {"field": "nothing_here"},
            }[name]
            out = dispatch_tool(name, sample)
            assert out is not None, name
            print(f"  ✓ {name}")

        # 2. Reinforcement: same correction again raises confidence.
        before = conscience.priorities_for("travel")[0]["confidence"]
        p = conscience.record_correction(
            "travel", "1-stop", "direct", "direct flights", "saving money")
        assert p["confidence"] > before, "reinforce failed"
        print(f"  ✓ reinforcement: {before} → {p['confidence']}")

        # 3. Contradictions erode and eventually flip the hierarchy.
        flipped = False
        for _ in range(8):
            p = conscience.record_correction(
                "travel", "direct", "1-stop", "saving money", "direct flights")
            if p["higher"] == "saving money":
                flipped = True
                break
        assert flipped, "hierarchy never flipped"
        print(f"  ✓ contradiction → flip: now {p['higher']} > {p['lower']} @ {p['confidence']}")

        # 4. Facts and the absolute right to forget.
        assert conscience.explain_basis("recital")["facts"], "fact not stored"
        assert conscience.forget_fact("recital") == 1, "forget failed"
        print("  ✓ remember / forget")

        # 5. Operational AI: the gate holds.
        denied = conscience.authorize_action("travel", "book flight", 300)
        assert not denied["allowed"], "acted without permission!"
        conscience.set_permission("travel", "act", cap=500)
        assert conscience.authorize_action("travel", "book flight", 300)["allowed"]
        over = conscience.authorize_action("travel", "book flight", 900)
        assert not over["allowed"] and "cap" in over["reason"], "cap not enforced!"
        assert any("denied" in a["outcome"] for a in conscience.action_log()), \
            "denials not logged"
        print("  ✓ act gate: default-deny, grant, cap, audit trail")

        # 6. Opportunity engine: scoring gates the right to interrupt.
        low = conscience.record_opportunity("minor coupon")
        assert low["status"] == "hold", low
        hot = conscience.record_opportunity(
            "suspicious recurring charge found", value_estimate="stops $60/mo",
            aligns_with="protecting money", advances_goal="cut expenses",
            reduces_risk=True, urgency=1.0)
        assert hot["status"] == "interrupt", hot
        assert conscience.orb_state()["mood"] == "protective", conscience.orb_state()
        conscience.resolve_opportunity("suspicious")
        conscience.resolve_opportunity("coupon")
        brief = conscience.daily_brief()
        assert "orb" in brief and "opportunities" in brief
        print(f"  ✓ opportunity engine: hold {low['score']} / interrupt {hot['score']} "
              f"/ orb went protective / brief assembles")

        # 7. Representative: forms fill, sensitive fields are refused.
        rep.set_profile_field("first name", "Laszlo")
        rep.set_profile_field("last name", "Czako")
        rep.set_profile_field("email", "l@example.com")
        blocked = rep.set_profile_field("SIN", "123-456-789")
        assert not blocked["stored"], "stored a sensitive identifier!"
        form = rep.fill_form(["Full name", "Email address", "Postal code", "Card number"])
        assert form["filled"]["Full name"] == "Laszlo Czako", form
        assert form["filled"]["Email address"] == "l@example.com", form
        missing = {n["field"] for n in form["needs_you"]}
        assert "Postal code" in missing and "Card number" in missing, form
        print(f"  ✓ forms: {form['coverage']} filled, sensitive + unknown handed back")

        # 8. Triage catches what preys on people.
        scam = rep.triage_message(
            "support@paypa1-security.com", "URGENT: account suspended",
            "Verify your identity immediately or we will suspend your account. "
            "Click here and pay the $50 fee with a gift card. Do not tell anyone.")
        assert scam["verdict"] == "likely_scam", scam
        assert scam["scam_score"] >= 0.5 and len(scam["scam_flags"]) >= 4, scam
        bill = rep.triage_message(
            "billing@streamer.com", "Your plan",
            "Your subscription will automatically renew on July 1 and you will "
            "be charged $22.99. Your promotional rate ends June 30.")
        assert bill["verdict"] == "money_watch", bill
        quiet = rep.triage_message("friend@example.com", "lunch", "Free Thursday?")
        assert quiet["verdict"] == "routine", quiet
        print(f"  ✓ triage: scam {scam['scam_score']} / billing {bill['billing_score']} / routine quiet")

        # 9. Drafting is grounded in their values and never signs blind.
        g = rep.draft_guidance("cancel the gym membership", "GoodLife")
        assert "Laszlo Czako" in g["write_as"] and g["rules"], g
        print("  ✓ draft guidance carries voice, values, and limits")

        # 10. The system prompt carries directives + live store.
        sp = system_prompt()
        assert "JEFFEREY" in sp and "Live conscience" in sp and "priorities" in sp
        print("  ✓ system prompt assembly")

    print("\nAll offline checks passed. Add an API key and he talks.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Talk to Jefferey.")
    ap.add_argument("--once", metavar="MSG", help="single message, then exit")
    ap.add_argument("--selftest", action="store_true",
                    help="offline end-to-end check of the learning loop (no key)")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    else:
        chat(a.once)
