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

## Operational AI (build priority 04)

Jefferey doesn't just advise — he acts, inside hard walls **enforced in
code, not vibes**:

- **Observe → Recommend → Act.** Every action category defaults to
  *recommend*. `authorize_action` is the gate before anything touches the
  real world; it default-denies, enforces per-category spending caps, and
  logs every denial. Only `set_permission` — at the user's explicit word —
  raises a level. Jefferey can never widen his own authority.
- **No silent actions.** Every act, denial, and permission change lands in
  the audit log inside the user's own conscience file (`action_log`).

## The Opportunity Engine + the predictive orb

The daily question from the spec: *"What can I do today to make this
person's life better?"*

- `log_observation` — things noticed (price changes, renewals, patterns).
- `record_opportunity` — scores each idea against THEIR priorities: value,
  alignment, goal advancement, risk reduction, urgency. **The score gates
  the right to interrupt**: ≥ 0.75 interrupts, ≥ 0.40 waits for the brief,
  below holds. Proactivity without noise.
- `daily_brief` — one screen: what he noticed, suggests, and did.
- `orb_state` — **the predictive cycle**: the orb's mood is the engine's
  real state — *protective* (risk found), *charged* (interrupt-worthy),
  *curious* (brief-level finds), *happy* (learned recently), *thinking*
  (fresh observations), *calm*. The face and the mind are the same thing.

## The Representative — correspondence & paperwork

The part that earns his keep on day one. Jefferey carries **no mail account
of his own** — he rides the Gmail/Outlook connector the host engine already
has. What he adds is representation:

- `triage_message` — reads anything that wants money, time, or a decision.
  Returns a verdict (`likely_scam` / `suspicious` / `money_watch` /
  `needs_decision` / `routine`), the predatory tactics **named in plain
  words** (gift cards, manufactured urgency, "don't tell anyone", remote
  access, impersonated institutions), amounts and deadlines found, and the
  user's own priorities that apply. Built for the people who get targeted.
- `draft_guidance` → write in their voice, from their values, signed as
  them. Sending requires `authorize_action` on `correspondence`.
- `fill_form` / `pdf_form_fields` / `fill_pdf` — completes HTML and PDF
  forms from the user's profile, saves a **new** file (never overwrites the
  original), and hands back every field it doesn't know. **It never guesses
  a value onto a form.**
- `set_profile_field` / `get_profile` / `forget_profile_field` — the identity
  details he may reuse, in the user's own store. **Sensitive identifiers
  (SIN/SSN, card numbers, PINs, signatures) are refused by design** — even
  if the user asks. Those fields always come back to them.

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

- The phone app: the orb live on your home screen (driven by `orb_state`),
  the conscience stored on YOUR phone — Self-Cloud v0 — permission dials,
  and the daily brief.
- Pro: hosted always-on sync, the Opportunity Engine running 24/7.
- Self-Cloud™ hardware: the conscience comes home to drives you physically
  own, with an on/off switch.
