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
- **`grounding.py`** — whole-word matching for grounding, what kind of
  private a fact is (health, money, children, the home's safety, other
  people's confidences), and every name an audience may go by for the
  owner's rules.
- **`provenance.py`** — who said what (the owner, his own typed words, or
  an AI, unconfirmed), and who will read a result.

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
2. **Actions**: paste the schema that `python connector/jefferey_http.py
   --schema` prints on this Mac (the server never shows its routes to the
   internet: `/docs` and `/openapi.json` are off).
3. **Authentication**: API Key → Bearer → the token the server printed
   (pin it with `JEFFEREY_HTTP_TOKEN`; make one with
   `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` — a short
   or repetitive token stops the server at start-up). Wrong tokens are
   written down and slowed with "too many"; the right one always works.

Same `conscience.json` as the Claude connector and the standalone chat.
Override GPT-Jefferey on Monday, and Claude-Jefferey already knows why on
Tuesday. **One conscience, many engines.**

## Operational AI (build priority 04)

Jefferey doesn't just advise — he acts, inside hard walls **enforced in
code, not vibes**:

- **Observe → Recommend → Act.** Every action category defaults to
  *recommend*. `authorize_action` is the gate before anything touches the
  real world, and only the caretaker key may ask it. It default-denies;
  needs the full price for anything that costs money; holds each spending
  limit to a total per day, week or month, in one currency; needs a lowest
  price for selling; and never approves moving money, gift cards, crypto,
  phone calls or the doors. Only the owner raises a level, typing `/permit`
  himself in `jefferey_chat.py` — it is not a tool on any surface. JEFFEREY
  can never widen his own authority.
- **No silent actions, no forged ones.** Every approval (with a single-use
  `authorization_id`), denial, act and permission change lands in the audit
  log inside the owner's conscience file (`action_log`), saying who wrote it
  and through which door; an act that cites no approval is marked so.

## An AI never changes what is his

These follow **who wrote something** — an engine key, or the owner at his own
console — never what the words mean:

- **His rules.** From an engine, a *no* (`set_rule` with `allow=false`) holds at
  once, labelled *noted by the AI, not yet confirmed by him*. Anything that
  widens what goes out — a yes, `remove_rule`, any other kind of rule — is a
  proposal that changes nothing until he confirms it (`/pending`, `/confirm`,
  or `python connector/conscience.py confirm`); no code completes it for an
  engine. `list_rules`, `check_disclosure`, `guidance_for` and `remove_rule`
  never hand an engine a rule's own sentence when the rule holds for that
  engine, or when its words are about something his rules keep from it — and
  `remove_rule` from an engine matches only what it may read (id, topic,
  audience). `/pending` and `conscience.py confirm` show each rule's yes or
  no, subject and audience first, then its words in full.
- **His profile.** An engine's `set_profile_field` waits beside his own value;
  `fill_form` and `fill_pdf` use only what he confirmed.
- **His people and goals.** An engine's person or goal waits, labelled; its
  change to someone he recorded is a proposal. Triage and every trust decision
  count only the people he recorded or confirmed; triage names someone an AI
  noted down as just that, and asks him.
- **Forgetting what is his** — anything he stored or confirmed — needs his own
  approval, whatever the count; an engine's code only forgets its own notes.
- **Learned values.** An engine's note never passes 0.6, and an engine's
  correction never wears down a value he stated or confirmed, or one kept
  before JEFFEREY knew who said what.
- **log_action** is `approved` only when what was done is what was approved,
  and says nothing beyond it (no word, and no more money, than the approval).
- **His home itself** (home, house, keys, security, guests, cameras, garage,
  la maison, chez moi…, in any letters, anywhere in the category) is never
  `act`; an errand under it is brought to him.
- **Money.** A bill through a payment processor (`PAYPAL *…`, `SQ *…`) or a
  name glued to a fee word is never by itself his membership: it asks him, and
  never makes the real bill a duplicate, until he says the line is his.
- **A no for someone nobody knows** holds for everyone but his own JEFFEREY.
- **A no for himself is a no for everyone** (round 9). A no whose audience is
  'me', 'myself', 'just me', 'moi' — in any case or letters — or that names
  no one at all holds for everyone and every AI but his own JEFFEREY; a
  disclosure no left without an audience is stored for 'anyone', and
  `set_rule` says so plainly. A yes for himself widens nothing.
- **No search is an oracle** (round 9). `forget`, `forget_life`, `remove_rule`,
  `close_goal`, `explain_basis`, `priorities_for` and `tell_story` match an
  engine's words only against what release would show it, list only what it
  may read (its `also_mentioned` and counts too), and count what is held back
  only by the kind of thing the subject names. Twenty searches by one key
  that find nothing within ten minutes pause that key's searches for an hour
  (`conscience.searches.json` beside the memories holds only times); he is
  told in his notices. His own console is never paused.
- **A sender is someone he recorded only by a whole match** (round 9): the
  whole address (case, spaces and look-alike letters aside) or the whole
  number (a leading 1 aside) noted for them. A name alone, or a display name
  with another address, never is; an address in another alphabet's letters
  is nobody's. Drafts and yes rules read a recipient the same way.
- **His own private facts in a draft** (round 9): a fact written in the first
  person is about him. `check_draft` to someone his rules do not let hear it
  answers `ask_owner` when the draft carries a word of that fact or of its
  kind (health, money, legal, family confidences), whoever it names.
- **Invisible characters are nothing** (round 9): every default-ignorable code
  point and every combining mark is dropped wherever words are read.

Round 9 repair (what the round-9 skeptics found):

- **Him, and only him.** `check_disclosure` and `guidance_for` answer 'the
  owner may always hear about themself' only when every part of the audience
  is him: 'me and Karen Novak', 'moi et ChatGPT' and 'me and the man on the
  phone' are asked about as that audience (silence is still a no).
- **Read both ways.** A character that shows as nothing or as a blank (the
  default-ignorables, and now U+2800, U+FFFC and U+1D159) is read as nothing
  and, again, as a space by every reader that decides something — the door,
  what kind of private a text is, a rule's topic, a draft, the secrets, a
  message's scam signs — and what either reading finds counts. In a merchant
  name it is a disguise, like a look-alike letter: he is asked.
- **What his rules close is no guess.** A question about a kind of thing his
  rules keep from that key (his health under 'Never tell my health to any AI')
  is answered the same whatever he keeps, so it never counts toward the pause.
- **No answer names what is held back.** `story_gaps` and `add_person` treat
  someone his rules keep from that AI as nobody; `record_correction` about a
  held value says only that it was noted; a rule's topic that is itself the
  secret ('hiv') is shown and asked by its kind ('health'); `forget` by an id
  it may not read answers as for an unknown id, and engine ids count as
  searches.
- **The sender is the address in `<…>`.** Another address in the From line
  makes it nobody he recorded, and is a warning sign.
- **No audience is anyone.** `check_draft` and `draft_guidance` with the
  audience left out check it as for anyone; 'myself' is him, as 'me' is.
- **The local model's system prompt fits** in 39,000 characters, however long
  the facts, values and goals: what does not fit is left out, and it says so.

Round 9, second repair (what the confirm check of the repair found):

- **A 'no' in the audience is never him.** 'not me', 'pas moi', 'never me',
  'everyone but me' — any not, never, no, pas, jamais, ni, sauf, except, but,
  other than or besides in it — are asked about as that audience, and a draft
  to them is checked.
- **A name is read both ways.** A character that shows as nothing or as a
  blank inside a name ('Karen⠀Novak') is read as nothing and as a space in
  every check of who a rule is for: a no holds if either reading meets it, a
  yes only if both do. `do_not_mention` meets an audience as `check_disclosure`
  does (any word of the name, the person it names).
- **Only a question in its kind's own words is no guess.** 'my health and my
  boat number 4800' counts toward the pause like any other question; 'my
  diabetes', 'ma santé' and 'my credit card' still do not, when his rules close
  them.
- **A value an AI states about what his rules hold back** (`set_priority`) is
  answered 'noted' the same whatever he holds; his question still reaches him.
- **The sender is the sent-from address, exactly.** It must be an ordinary
  address JEFFEREY can read (no IP literal, 'localhost', quoted name or domain
  in another script) and match his recorded one as written, accents and marks
  kept. Anything else is a stranger, with a warning sign.
- **An audience that shows as nothing is no audience:** checked as for anyone,
  and it says so.
- **Hidden is whatever the fold reads as nothing** — one list, so they cannot
  drift (U+16FE4 between words hid the door words and a password).
- **A mark his own name does not have is a disguise.** 'NÉTFLIX.COM',
  'NET̲FLIX.COM', 'NETFLİX.COM', 'NETFLıX.COM' ask him; CAA-QUÉBEC's own accent
  still matches. When he says such a name is his (`add_alias`), it is.

Round 9, last fixes (what the confirm check of the second repair found):

- **A question about what his rules close is no guess unless it carries a
  number.** The second repair counted 'what medication does he take' and 'how
  often does he see his doctor' as guesses, and paused his own JEFFEREY. Now
  only a number — digits of any script, or number words — makes such a question
  count (`grounding.guess_shaped`): 'my health and my boat number 4800' still
  pauses at the twenty-first.
- **Marks are checked place by place.** A statement name may drop his accents
  ('CAA QUEBEC' for 'CAA-Québec') but not add one, move one ('CAA-QUEBÉC'), or
  write a letter another way (a circled Ⓝ, a Roman numeral Ⅰ, full-width,
  dotless ı): `guardian._marked_unlike` lines the name up with his own names
  for the plan and asks him about anything that differs.
- **His relationship to someone is one relationship however it is joined:**
  'my ex‑wife' with a non-breaking hyphen, 'my ex wife', 'my exwife' and 'my
  ex⠀wife' all meet a no for his ex-wife (`grounding.same_relationship`; a
  no only).

**Confirmation needs a person.** The owner's own command-line confirmations —
`conscience.py confirm` and `restore`, `forgetting.py approve`, `erase` and
`bring-back`, `guardian.py review`, `egress.py open` and `keep` — refuse unless
stdin and stdout are terminals; `--yes` is ignored; the answer is read from the
terminal itself (`/dev/tty`) and must hold a short number printed on the
screen at that moment. `conscience.py edit` and `dismiss`, and `confirm` called
from Python, want him there too. **What this cannot stop:** a program with a
shell alone can change the memory file directly — it is a plain file, and
JEFFEREY adopts what it finds (keeping the copy from before) — and one that also
has a pseudo-terminal can read the number off its own screen and type it back.
Until confirmation moves to Touch ID (I-43), never give an AI agent a shell on
the Mac that holds his memories.

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

- `triage_message` — reads anything that wants money, time, or a decision,
  in English or French, with the sender. Returns a verdict (`safety` /
  `likely_scam` / `suspicious` / `check_first` / `money_watch` /
  `needs_decision` / `routine`), whether to interrupt, the predatory tactics
  **named in plain words** (a grandchild's "new number", gift cards, a code
  "sent by mistake", overpayment, a courier "agent", "don't tell anyone",
  remote access, look-alike links and addresses), what it touches, amounts
  and deadlines found, and the user's own priorities that apply. Money,
  cards, codes, secrecy, urgency or a family claim never come back
  `routine`; someone asking when he is home alone is `safety`. Disguised
  words (look-alike letters, invisible characters, `g1ft c@rd`) are read
  through, and are a sign in themselves. Built for the people who get
  targeted.
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
  agreed to, and what they've cancelled. From an AI, an addition waits for the
  owner (`charge_changes_waiting` lists it, `decline_charge_change` withdraws
  it, `name_for_charge` asks to treat a statement name as a known company);
  only the owner confirms, at his keyboard (`/charges`, `Check my
  charges.command`). No engine is offered a way to confirm.
- `check_charge` / `review_statement` — every charge held against it.
  Eleven verdicts (see `guardian.py`): quiet ones (`expected`,
  `amount_decreased`, `refund`), the informational `unexpected_merchant`, and
  the alarms (`amount_increased`, `duplicate`, `unauthorized_renewal`,
  `charged_after_cancel`, `possible_card_testing`, `possible_scam`,
  `needs_date`). Statement names are normalized, so
  `GODADDY.COM 480-505-8855` and `GoDaddy Inc` are the same company.
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
- `forget_life` — never argued with, never on a guess: two steps (shown, then
  removed with a one-time code), like every removal — see `forgetting.py`.

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
