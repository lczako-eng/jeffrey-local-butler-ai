# JEFFEREY Agent Connector

**The intelligence is rented. The conscience is owned.**

This is priority 03 of the [public build spec](https://github.com/lczako-eng/Jeffrey-AI-Butler/blob/main/docs/JEFFEREY_TO_BE_BUILT.md):
JEFFEREY rides the best AI engines as a plug-in agent. This connector is an
[MCP](https://modelcontextprotocol.io) server that gives any MCP-capable host
(Claude Desktop, Claude Code, and others) JEFFEREY's identity and his owned
conscience store.

- **`conscience.py`** — the user-owned store: contextual priority hierarchies
  with confidence scores, facts (kept separate from values), goals, and the
  correction log. A plain local JSON file: inspect it, edit it, delete it,
  move it between engines. Default location: `~/.jefferey/conscience.json`
  (override with `JEFFEREY_CONSCIENCE_PATH`).
- **`jefferey_mcp.py`** — the MCP server exposing the conscience as tools:
  `get_directives`, `get_conscience`, `record_correction`, `set_priority`,
  `remember_fact`, `forget`, `explain_basis`, `priorities_for`, `add_goal`,
  `close_goal`.
- **`directives.md`** — the Jefferey Directive Pack: the identity and
  operating rules the host model adopts to *be* Jefferey.
- **`jefferey_chat.py`** — **Jefferey himself, runnable.** A terminal chat
  that wears the Directive Pack on a rented Claude engine and wires every
  conscience tool live. Talk to him today.
- **`jefferey_http.py`** — the same conscience over HTTP, for engines that
  speak Actions instead of MCP — most importantly **custom GPTs**. The other
  half of build priority 03.

## Talk to Jefferey (standalone)

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...   # console.anthropic.com
python connector/jefferey_chat.py
```

- `/conscience` in-chat shows everything he knows — you own every byte.
- `--once "message"` for a single exchange; `--selftest` proves the whole
  learning loop offline (dispatch, reinforcement, contradiction → flip,
  remember/forget) with **no API key needed**.
- Quit and relaunch — same conscience, same Jefferey. Point the MCP
  connector below at the same store and he's the same person inside
  Claude Desktop or Claude Code too. One conscience, many engines.

## Install (MCP connector)

```bash
pip install "mcp[cli]"        # or: pip install -r connector/requirements.txt
```

### Claude Code

```bash
claude mcp add jefferey -- python /absolute/path/to/connector/jefferey_mcp.py
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jefferey": {
      "command": "python",
      "args": ["/absolute/path/to/connector/jefferey_mcp.py"]
    }
  }
}
```

Then start a conversation with: **"Call get_directives and be Jefferey."**

## Install (custom GPT — the GPT side)

```bash
pip install fastapi uvicorn
python connector/jefferey_http.py     # http://127.0.0.1:8377, prints a bearer token
```

Expose it over HTTPS (e.g. `ngrok http 8377` or `cloudflared tunnel`, or run
it on any small server), set `JEFFEREY_PUBLIC_URL` to that URL, then at
chatgpt.com → **Create a GPT**:

1. **Instructions**: paste `directives.md`, plus one line — *"Call
   get_directives and get_conscience at the start of every chat."*
2. **Actions → Import from URL**: `<JEFFEREY_PUBLIC_URL>/openapi.json`
3. **Authentication**: API Key → Bearer → the token the server printed
   (pin it with `JEFFEREY_HTTP_TOKEN`).

Same `conscience.json` as the Claude connector and the standalone chat.
Override GPT-Jefferey on Monday, and Claude-Jefferey already knows why on
Tuesday. **One conscience, many engines.**

## The demo that matters

1. Ask Jefferey for a recommendation (a phone plan, a flight).
2. Override him — pick something "worse."
3. Watch him call `record_correction` and tell you what he learned about you,
   with a confidence score.
4. Ask again next session — in this engine or any other pointed at the same
   `conscience.json`. He remembers *why* you decide.

One conscience, many engines. No platform can copy that: their memory is
locked to themselves.

## Roadmap

- The Opportunity Engine loop (goals × world changes × permissions).
- Self-Cloud™: the conscience comes home to hardware you physically own.
