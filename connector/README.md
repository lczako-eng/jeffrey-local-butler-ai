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
- **`representative.py`** — correspondence triage (scam and predatory-billing
  detection), drafting in the user's voice, and HTML/PDF form filling.
- **`vault.py`** — secrets stored in the platform keychain, used by reference
  so the AI never sees them.

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

## The Vault — secrets the platform holds, not Jefferey

*"He's supposed to look out for me but can't hold my information?"* He
doesn't have to hold it. **The operating system already does.**

`vault.py` puts secrets in the platform's own credential store — **Apple
Keychain**, **Windows Credential Manager**, Linux Secret Service, and on
phones iOS Keychain / Android Keystore behind Face ID. No partnership or
special deal is required: these are public APIs any developer can use.

Two rules are enforced in code, not promised:

1. **Secrets never enter an AI context.** You store them from your own
   terminal, never by typing them into a chat:
   ```bash
   python connector/vault.py set sin      # prompts privately, no echo
   ```
2. **Jefferey uses them by reference, never by value.** He writes
   `vault:sin` into the form field; local code on your machine swaps in the
   real value at the moment of writing. It goes keychain → your PDF, never
   touching Anthropic, OpenAI, or us.

So he files the same government form every year — including the box he
isn't allowed to know. He knows the secret *exists*; he never learns what
it is. Handing him a literal secret is refused outright.

```
What the AI sees:      {"SIN": "vault:sin", "Full Name": "Laszlo Czako"}
What lands in the PDF: {"SIN": "999-888-777", "Full Name": "Laszlo Czako"}
```

## The Guardian — money that leaves without asking

The GoDaddy problem: a card gets charged, nobody asked, and finding out takes
forever. Multiply that across every auto-renewal, silent price hike, zombie
subscription and double-billing and it is an enormous amount of money quietly
leaving people who never agreed to it.

- `expect_charge` / `mark_cancelled` — the register of what the user actually
  agreed to, and what they've cancelled.
- `check_charge` / `review_statement` — every charge held against it.
  Verdicts: `expected` (stay quiet), `amount_increased` (with the delta and
  the annual cost), `unexpected_merchant`, `charged_after_cancel`,
  `duplicate`. Statement names are normalized, so `GODADDY.COM 480-505-8855`
  and `GoDaddy Inc` are the same company.
- `dispute_pack` — what was authorized, every disputed charge, and how to
  write the demand, so the user is never the one digging through statements
  at 11pm.

Jefferey holds **no card numbers** — only what was charged, by whom, and
whether it was ever agreed to. He never moves money: disputing or cancelling
is an Act, gated and logged.

## The life layer — the Digital Conscience proper

Priorities tell Jefferey *how* to represent you. This tells him **who he is
representing** — and lets him tell your story down the road (priority 07,
starting now instead of too late).

- `add_person` — the people who matter, before he needs to know them.
- `add_memory` — snippets of a life in your own words, each marked
  `private` / `family` / `legacy`.
- `add_media` — photographs referenced **where they already live** on your
  Self-Cloud. Never a copy, never an upload; if the drive is off, they read
  as unreachable.
- `who_am_i` / `tell_story(audience=…)` — what he understands, and what each
  audience is permitted to hear. The visibility walls are enforced, not
  suggested.
- `story_gaps` — what's missing, so he can gently ask for one thing at a
  time while there's still time to ask.
- `forget_life` — absolute, never argued with.

See [`docs/SELF_CLOUD.md`](../docs/SELF_CLOUD.md) for how this comes home to
hardware you physically own.

## Self-Cloud — the vault, and who gets a key

Self-Cloud is **its own product**. Jefferey is one caretaker holding a key
the owner granted and can take back — not the owner of the vault.
(`selfcloud.py`; architecture in [`docs/SELF_CLOUD.md`](../docs/SELF_CLOUD.md).)

| Key | Gets |
|---|---|
| `claude-raw` | facts, priorities, goals. Useful, not intimate. |
| `gpt-raw` | the same — a rented engine kept at arm's length. |
| `jefferey` | the caretaker: conscience, life layer, media, money, legacy. Never the secrets themselves. |
| `family` | only what was marked `family`. Writes nothing. |
| `executor` | `legacy` only. Nothing else, ever. |

Three properties, enforced not promised: **deny by default** (an unknown
client gets nothing), **every decision logged** in the owner's own store, and
**revocation instant and total**. The physical switch is still the final
word — drive off, nothing is reachable by anyone.

## The interview — how the conscience actually gets built

You can't hand someone a form and get a person out of it. `interview.py` is
a ladder of questions Jefferey **earns the right to ask**:

1. **warm** — *"Who's the first person you'd call with good news?"*
2. **shape** — *"What do you do, and is it what you meant to do?"*
3. **values** — *"Is there a decision you'd make differently now?"*
4. **legacy** — *"If someone told your story in one sentence, what would you
   want it to say?"*

Depth rises with what the person has actually chosen to share — never with
elapsed time. `next_question` returns **one** question to weave into
conversation, never a list, never announced. `record_answer` keeps it in
their words at the visibility they choose. A deflection is recorded as
declined and **never raised again**.

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
