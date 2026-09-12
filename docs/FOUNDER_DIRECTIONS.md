# Founder's Directions — where this is going

*A running record of where Laszlo has said he wants this to go, in his words
where possible, so no future session — human or AI — has to rediscover it.
Not a backlog. A compass. Add to it; never delete from it.*

---

## 1. The conscience speaks in your own voice (recorded 2026-09-08)

> "Things like Google Home and other audio voice like Apple — if you can
> change the voice to kind of *your* voice, it could be like… it's almost
> like your conscience speaking. I'm not sure if we can pull this off, but I
> want it to be, and this is eventually the way I want to go."

**The idea.** The Digital Conscience, when it speaks aloud — through a
speaker in the house, the phone, eventually the Self-Cloud box — speaks in a
voice that is *yours*: not Jefferey doing an impression, but your own
conscience with your own voice, saying back to you what you told it. The
reminder in your own voice. The story told in your own voice. And one day,
to the people you leave it to, still your own voice.

**Feasibility (honest, as of 2026-09).** More possible than it sounds:

- **Voice cloning from a few minutes of speech is mature technology today.**
  Apple already ships it *on-device* for accessibility ("Personal Voice":
  read 150 phrases, the phone builds your voice, it never leaves the phone).
  That is exactly the shape we want — a voice model that lives on hardware
  the person owns.
- **The walled speakers are the hard part, not the voice.** Google Home and
  HomePod do not let third parties replace their voice. The realistic path is
  **our own playback surfaces**: the phone app, a speaker Self-Cloud drives
  directly, the Self-Cloud box itself. Where a platform opens up later, we
  plug in; we do not wait for it.
- **Sequence:** phone app speaks in the owner's cloned voice → Self-Cloud box
  gains a speaker → third-party speakers as they allow it.

**Non-negotiable safeguards — this is a fraud vector if done carelessly.**
A cloned voice of a person is precisely the tool used in "grandparent" phone
scams. Ours must be built so it cannot become one:

1. The voice model lives **on Self-Cloud only** — never uploaded, never in
   any cloud, never exportable as a file. Same rule as the photos.
2. It speaks **only to the owner** (and, with explicit `legacy` permission,
   to the people they named — after). Never to a third party, never on a
   phone call, never to a bank.
3. It says **only what is in the conscience** — the owner's own words and
   what they permitted. It never generates new speech "as" the owner to
   anyone else. Reaction and representation rules apply to the voice exactly
   as to text.
4. Creating the clone requires the owner present, consenting, and reading
   the enrolment phrases themselves. Revocable in one action; deletion is
   real deletion.
5. Anything spoken aloud is logged like any other act.

**Why it matters.** It is the emotional endpoint of the whole thesis: an AI
that doesn't *answer* you in a stranger's voice, but *reminds* you in your
own. And for the people left behind — the story, told the way they remember
it sounding.

---

## 2. What belongs in the Digital Conscience (recorded 2026-09-08)

> "The Digital Conscience is also gonna have your health stuff in there —
> health records. You could also share your locations. Also use your
> information off your pictures — metadata. It should have a daily review if
> it's attached to a GPT or something like that, in the morning. Also your
> tasks, and everything. Anything you need to really remember needs to be in
> there… I'm on the line with [locations]. Just remember what I'm telling
> you."

**The principle, in his words:** *anything you need to really remember needs
to be in there.* The conscience is the one place a life's remembering goes.

**Contents, and how each is handled:**

| What | Enters how | Default rule |
|---|---|---|
| **Health records** | Only by the owner's explicit inclusion, item by item | *disclosure: me only* — the strictest default in the system. A doctor or family member is opened up by a named rule, never by default. Health is where "silence is a no" matters most. |
| **Location** | **Opt-in, and the founder is undecided** ("on the line"). Design it as a switch the owner turns on per purpose — e.g. "remember where photos were taken" separately from "know where I am now" — never as an always-on trail. | *disclosure: me only*; never shared with any third party or engine beyond what a task strictly needs. If in doubt, off. |
| **Photo metadata** (dates, places, faces, camera) | Automatically *indexed* by Self-Cloud; *enters the conscience* only for photos the owner included. Metadata is how "on this day" and "where was this" work without asking. | Follows the photo's visibility. |
| **Tasks** | Goals and to-dos, stated or drawn out; the Opportunity Engine works them. | private |
| **The daily review — the morning brief** | When Jefferey is attached to an engine (GPT, Claude, the app), the day opens with one review: what's coming, what he noticed, what needs a decision, what he did. `daily_brief` already exists; this is its delivery, in the morning, by habit. Later, spoken — in the owner's own voice (§1). | — |
| **Everything else worth remembering** | "Remember this" — the one verb. | private unless marked otherwise |

**Two cautions to build to:**
- Health and location are the two categories where a leak does lasting harm.
  They get the strictest defaults, the loudest confirmation before any
  sharing, and full audit. Treat them like the secrets in the keychain: the
  fact that Jefferey *can* hold them is exactly why the walls must be real.
- "Anything you need to remember" must not become "everything, automatically."
  The intake gate stays: the owner includes; Jefferey never hoovers.

## 3. Everything feeds it — and the drive is the hub (recorded 2026-09-08)

> "My other apps should be able to tie into this — your workout schedules,
> your health from your ring and all that, your Apple Health, even your
> transactions from Revolv. This should know everything about you. But
> storage — why should your phone be charged? You can just plug it in
> anywhere and let that resonate. It might be best to have the hard drive
> connected to your intelligence, which pulls off the intelligence and brings
> information back and forth onto your phone or whatever other device."

**Two ideas, both recorded as direction:**

**(a) The integrations layer — everything you already generate feeds the
conscience.** Wearables (Oura ring, watch), Apple Health, workout apps,
transactions (Revolv, bank exports), calendar. The person already produces
this data every day; today it sits in a dozen silos owned by a dozen
companies. Pulled onto Self-Cloud it becomes one life, in one place, owned.

- **How it enters:** through each app's export or API (Apple Health exports
  its full record; Oura, most banks and calendars have APIs or CSV). Self-
  Cloud ingests into storage; the conscience takes only what the owner
  includes (the intake gate); each stream gets a default rule (health: *me
  only*). Nothing is scraped from a screen.
- **What it unlocks:** the Guardian watching *real* transactions instead of a
  hand-kept register; health patterns ("your sleep has been short for two
  weeks") noticed without being asked; the morning brief built from actual
  data. This is where "protect you more than anybody" becomes concrete.
- **Honesty about the work:** every integration is its own small project
  and every API changes under you. Start with exports (Apple Health, bank
  CSV) — they are stable and need no partnership — and add live APIs where a
  provider offers one.

**(b) The drive is the hub, not the phone.** The Self-Cloud unit is the
always-on node: it holds the storage, runs the connector, talks to the rented
intelligence (Claude, GPT), and syncs to the phone and any other device. The
phone becomes a *window* onto Self-Cloud, not the place the life lives — so
the phone isn't burdened, and losing or replacing a phone loses nothing.

- **One physical fact to design around:** a bare hard drive cannot run
  software. "Plug it in anywhere" means the unit is **a drive plus a small
  computer** (the size of a paperback — a Raspberry Pi / mini-PC class
  board, tens of dollars). That pairing *is* the Self-Cloud box. Plug it into
  power and the home network and it's the hub; unplug it and it's off the
  network — the switch, made physical.
- **This revises the staged path** in `SELF_CLOUD.md`: the phone-storage v0
  becomes a *bridge* for people who don't have the box yet, not the destination.
  The destination is the box at home, with the phone as its face.
- **Sync rule:** the box is the source of truth; devices hold a working copy
  of what they need and nothing more; secrets never sync anywhere (keychain
  only, per device).

## 4. The local model, the house, and the AI that is *you* (recorded 2026-09-12)

> "I want this thing eventually — let's bring the local Emma LLM, and then this
> product to your house. So a hard drive that runs your house. But I want it to
> be *you* as the AI — you have the option. It could be your voice, your accent,
> your memories. Unlike Google, which sucks — this could be *you* talking to
> you."

Three directions in one sentence, and they belong together. This is the
destination §1 and §3 were pointing at.

**(a) The local model lives on the box.** ("Emma LLM" is recorded as he said it;
read it as *a downloadable model that runs on the owner's own hardware* — the
name is a placeholder until he settles one.) This is now Self-Cloud's stated
independence guarantee (their 2026-09-12 handoff): the box must stay useful if
every AI company disappears. The honest engineering, so nobody buys a GPU too
early — **three tiers, and only the third needs an LLM**:

| Tier | Jobs | What it actually runs on |
|---|---|---|
| Deterministic | indexing, exact dedup, timeline, near-duplicate detection | plain code. Already proven — 15,636 redundant copies, ~55 GB, found with SHA-256, no AI at all |
| Small model | semantic search, photo/document classification, OCR, conscience retrieval | embeddings, 100–400 MB of weights, fine on a Pi-class CPU |
| LLM | summarizing, answering, reasoning, *speaking* | a real local model — Apple-silicon mini or a GPU/NPU mini-PC |

Build the first two before spending a dollar on the third. And note the one
thing that makes "open weights = independence" true rather than a slogan: **the
weights must be archived on the drive itself.** A model you'd have to re-download
from a company's website is still that company's model.

**(b) The hard drive runs your house.** The box already has to be plugged in,
always on, on the home network, and trusted with the life. That is exactly a
home hub. Home Assistant is the obvious substrate — open, local-only, runs on
the same class of hardware, speaks Matter/Zigbee/Z-Wave/Thread — so this is an
integration, not an invention. It also fixes the box's weakest commercial
problem: a drive that only holds photos is a purchase; a drive that runs the
lights, the locks, the thermostat *and* holds the life is a fixture.

- **One hard rule, or this breaks the kill switch:** the house must keep working
  when the box is off. Local devices keep their local control (a switch is still
  a switch); what stops is the *intelligence* — the routines, the voice, the
  automations. "The box is asleep" must never mean "the lights don't turn on."
  That degradation is the actual engineering, and nobody in this market ships it.

**(c) It's you — your voice, your accent, your memories.** §1 already carries the
voice and its five safeguards; this adds two things:
- **Accent comes free with the clone** — that's the point of cloning a person
  rather than picking a stock voice. It's what makes it sound like *home*.
- **"You have the option."** Not the default. Some people will find their own
  voice in the hallway unsettling, and some will find it the most comforting
  thing in the house. Ship a neutral voice by default and let the owner choose
  their own, with one switch, reversible.

**And two safeguards this specific direction adds** (on top of §1's five):
6. **A speaker is a room, not a person.** The house has guests in it. Anything
   the box says aloud in a shared space is a *disclosure* — the rules layer
   applies to speech exactly as to text, and the default in a room with someone
   unrecognised is silence.
7. **The voice never answers the phone, the door intercom, or anything a
   stranger can dial.** A cloned voice that a caller can reach is the exact
   instrument of the scam this product exists to stop.

**Why "unlike Google" is the right instinct.** Google Home and Alexa speak in a
stranger's voice, from a company's cloud, about a person the company owns a
profile on. This speaks in the owner's own voice, from a drive on the owner's
own shelf, about a life the owner curated — and it can be switched off at the
wall. Same box, opposite ownership. That is the whole pitch in one sentence, and
it is the one version of a "smart home" nobody is selling.

## 5. Things already decided in this session, so they aren't relitigated

- **JEFFEREY**, never "Jeff". No "butler" anywhere.
- Jefferey is a **wrapper** over rented engines, not a model of our own.
- **Self-Cloud is its own product**; Jefferey is a caretaker with a key. Its
  repo exists — `lczako-eng/Self-Cloud` (Jan 2026 whitepapers, no code yet);
  the laptop build pushes there. The January documents are canon.
- **Intelligence must not outlive consent** — Jefferey operates only while
  Self-Cloud is powered. Always-on is the owner's option, never a requirement.
- The **Digital Conscience is the person's journal** — daily and family —
  curated (only what they let in), with rules they write: who may hear what,
  how to react to them, how to speak of them to others. Silence is a no.
- **Originals are sacred**: read-only, checksummed copy on the same drive;
  a second drive elsewhere; verify a restore before iCloud is ever cancelled.
- **Secrets never leave the OS keychain**; Jefferey uses them by reference.
- **Free first.** The person pays for their engine, not for Jefferey. Pro
  and hardware come after dependence is real.
- **Mission over money**: built for the lonely, the sick, the elderly, the
  scam-targeted. Money is fuel for more good, not the destination.
- Build order from the public spec: 01 Conscience → 02 Priority Learning →
  03 Plug-in Layer → 04 Operational AI → 05 Orb → 06 Self-Cloud → 07 Digital
  Inheritance. 01–05 have working code.
