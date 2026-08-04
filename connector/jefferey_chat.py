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

MODEL = "claude-opus-5"
MAX_TOKENS = 4096

DIRECTIVES = (Path(__file__).parent / "directives.md").read_text()

conscience = Conscience()


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

        # 5. The system prompt carries directives + live store.
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
