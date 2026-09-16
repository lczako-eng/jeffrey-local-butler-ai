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

**Built (2026-09-16): the enrolment half.** `tools/voice_enrol.py` records the
owner reading ~55 phrases plus five in his own words, into `~/.selfcloud/voice/`
only. Safeguard 4 is code, not prose: it refuses to run without a person at a
keyboard, the **first take is the consent sentence in the owner's own voice**
and is kept with the rest, every take is a checksummed read-only file, and
`delete` overwrites before it unlinks. The test asserts the file imports
nothing that can reach a network. Playback — the voice *saying* anything — is
not built and is a separate decision.

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

**Built (2026-09-16) — the drive as the product.** *"We got the hard drive
ready."* `tools/provision_drive.py` turns any drive into a Self-Cloud drive:
the layout, a marker, the cloud logo as the Finder icon, and a launcher that
binds every tool to that drive on whatever Mac it is plugged into.
`connector/home.py` makes every tool keep the conscience, the index and the
voice **on the drive** when one is present. The Mac keeps nothing but a
Python. Unplug it and it is gone — which was always the point.

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

**(d) — added 2026-09-13 — "or your mom's voice."**

> "Wouldn't that be cool, to talk to your own voice, or your mom's voice, or
> whatever."

This is the emotional endpoint of the whole system, and every part needed to
reach it already exists somewhere in the build: `legacy` visibility in the life
layer, the 21 interview questions, answers stored in the person's own words. Add
a voice and it stops being a product feature — it is a grandmother telling her
own stories, in her own voice, to grandchildren who never met her. Nobody is
selling that. It is also the direction that can do the most harm if built
carelessly, so it carries one rule above all others:

> **Her voice, her words. The system never generates new sentences as a person
> who is not here to object.**

That single line is the difference between a memorial and a puppet. A memorial
*replays and reads what she actually said and permitted* — the conscience is the
script, exactly as safeguard 3 already requires. A griefbot *improvises as her*:
invents opinions she never held, comfort she never gave, answers to questions
she never heard. The first helps people; the second is consistently what the
reporting on grief technology finds to be damaging. When the speaker belongs to
someone who has died, safeguard 3 stops being a policy and becomes the product's
spine.

Consent does not weaken after death, it hardens. Safeguard 4 stands unchanged:
**the clone is created by that person, present, consenting, reading the
enrolment phrases themselves.** You cannot enrol a parent from their voicemails,
and the system must refuse to try. That sounds like a limitation and is actually
the product:

> **Record the people you love while they are still here.**

It is the most honest call to action this company could have, it is the one
thing that genuinely cannot be done later, and it is what sells the box to a
fifty-year-old with aging parents. It also means the enrolment flow is not an
afterthought in the legacy tier — it is the reason someone buys in year one.

**And a note on the name.** "Self-Cloud" used to mean *your cloud instead of
theirs*. With the house on it, it means **the cloud came home** — the thing that
used to live in someone else's data centre is now a box on a shelf that answers
when you walk in. Same word, larger claim. Worth using that framing publicly.

**(e) — 2026-09-14 — his mother has died, and her voice is on videotape.**

> "No, she doesn't [live] — so I'm not sure how we can get it off of old
> videotape and stuff like that, but it'd be super cool… that's one thing
> we're going to have to work on."

This changes §4(d)'s "record them while they're here" from a plan into a
regret, and it changes what the urgent item is. **The window did not close. It
moved.**

*Corrected 2026-09-14 — "it's on the DVDs".* The tapes were already
transferred, which is better news than tape and still urgent. A pressed
commercial DVD is stamped metal; a **home-burned DVD-R is a photosensitive dye
that fades**, faster on cheap discs and faster still in a warm or humid house.
Discs burned in the 2000s are already failing, and the failure is quiet — the
disc looks perfect, plays for eleven minutes, and stops. But unlike tape:
ripping is **not real-time**, needs no deck, and costs a $25 USB drive. The
video is already a file; copying it verbatim preserves it exactly, with nothing
decided now that cannot be decided later.

**One question still open for the owner: do the original tapes still exist?**
If they do, they are the better master — the DVD transfer is compressed MPEG-2
and threw detail away permanently. The DVDs are the urgent, easy win; the tapes,
if they survive, are the one worth doing properly afterwards.

**Two different things, and the difference is the whole ethic:**

| | What it is | Verdict |
|---|---|---|
| **The archive** | Digitize the tapes. Separate the audio. Clean it. Transcribe it locally. Index it so he can *find* the moment she said a thing, and hear **her actually saying it**. | **Build it.** This IS "her voice, her words" — the rule at its purest. No consent question arises: replaying what a person really said to the family they said it to is what a family photograph has always been. |
| **The synthesis** | A model trained on those tapes, generating sentences she never spoke. | **A separate decision, made deliberately, never drifted into.** Safeguard 4 (the person present, consenting, reading the phrases) cannot be satisfied by someone who has died. If he ever chooses this, it is his choice as her son to make with his eyes open — and it must still never produce a sentence she did not say to someone who might believe she did. |

Everything §4(c) and (d) said about the *owner's* voice stands unchanged. What
is added here is that **a dead person's voice is an archive, not an instrument**
— and an archive is worth building well, urgently, and with care.

**What the archive actually needs** (each piece is ordinary, none is research):

1. **Rip the discs, verbatim** — ✅ **BUILT: `tools/disc_archive.py`.** A $25
   USB DVD drive is the only purchase. It copies `VIDEO_TS` byte for byte (no
   re-encoding, nothing lost), and **survives a damaged disc**: one bad sector
   must not cost the whole evening, so it records which byte ranges failed,
   fills them, and keeps going — a scratched disc yields 98% of her birthday
   instead of an error.
2. **Never touch the master.** The archived copy is an original in the
   `/originals` sense: read-only (enforced), checksummed, never re-encoded in
   place. Everything downstream works on copies. And **keep the discs** — the
   copy does not replace them, it outlives them.
3. **Audio extraction** — pull the sound out losslessly (FLAC), so nothing is
   thrown away before transcription. Her voice is the point; the video is a
   bonus.
4. **Local transcription** — whisper.cpp, on his own machine. Her words become
   searchable text without a single second of her voice leaving the house.
5. **Index it like everything else** — same when/where/meaning index as the
   photos, so "what did mum say about the house on Westhill" is a question
   with an answer, and the answer plays in her voice.
6. **Visibility** — `legacy` by default, because this is exactly what the
   legacy tier was built for.

**A hard rule for this material:** the transcription is a convenience, never a
substitute. What gets played back is **the recording**. A transcript can be
wrong; a recording cannot lie about what she said.

**(f) — 2026-09-14 — it re-indexes itself, forever.**

> "This thing should be constantly re-indexing itself so it knows you very
> well… great for dementia and Alzheimer's patients as well. But this is
> Self-Cloud. This is you. This is your property. This is your own ecosystem."

**The living index.** A library that is indexed once is a snapshot; a life is
not. New photos arrive, documents are written, recordings are made, things are
corrected. The index must keep up on its own, without being asked — and without
becoming surveillance. The reconciliation with "intelligence must not outlive
consent" is already written in the review: *owner-initiated digestion of the
owner's own data on the owner's own hardware is consented work.* It runs while
his machine is on, it logs exactly what it touched, it stops when the machine
stops, and it never reaches beyond the folders he named.

**Never delete on absence.** A file that has gone missing is far more often an
unplugged drive than a deleted photo. Missing is a *state*, recorded with a
date — never a reason to drop what is known about something.

**Dementia and Alzheimer's — take this seriously, it is not a nice-to-have.**
Reminiscence and life-story work are established non-pharmacological practice
in dementia care, and what they need is precisely what this system produces: a
person's own photographs, their own recordings, their own people, organised so
a carer or family member can bring the right thing to hand at the right moment.
Two things follow:

- It argues for **the archive, not the synthesis.** Reminiscence work uses real
  material. A confused person, a synthesised voice, and a relative who has died
  is the worst combination this technology can produce, and the line in (e) is
  what prevents it.
- It argues for **the surfaces** (§3b of the build list). A person with memory
  loss does not type a search query. They look at a screen on the wall, and
  someone they love says "look — that's Cuba, that's you." The wall, the clock
  and the TV are the interface for this, not a chat box.

**And the framing he closed with, which is the thesis in four sentences:**
*This is Self-Cloud. This is you. This is your property. This is your own
ecosystem.* Every capability above — the archive, the living index, the wall,
the voice — is built on hardware he owns, from data he owns, and it stops when
he says stop. That is not a feature list. That is the product.

## 4½. The album, opened by him (recorded 2026-09-16)

> "I wanted to collect all my memories and ask me questions about it — like I
> wanted to prompt the AI to say *hey, these pictures from Afghanistan, tell me
> some stories* — so it remembers permanently."

**This inverts the interview.** The 21 questions ask about a life in the
abstract; this asks about *a specific afternoon*, with the pictures on the
screen. Nobody remembers everything, but almost everybody remembers when
shown — which is why reminiscence work in dementia care uses photographs and
not questionnaires.

**Built the same day: `connector/reminisce.py`**, on every JEFFEREY surface as
`next_story_prompt` / `record_story` / `decline_story` / `story_progress`, and
standalone from a terminal. It clusters the dated, placed photographs into
moments — a trip, a season, a place ("Afghanistan · October 2011, 143
photographs") — offers the biggest untold one first, keeps what he says
**verbatim**, pinned to those exact photographs, privately, permanently, and
returns one gentle follow-up chosen by what the story left out.

**Rules that are code, not intention:**
- **The prompt states only facts the index holds** — a count, a place, dates.
  Never "this looks like a wedding." A guess offered as a memory is how a
  false memory starts; the story comes from him, always.
- **His words are kept exactly.** The test asserts the stored text equals what
  was said.
- **"Rather not" is final.** A declined moment is never offered again, and a
  later attempt to record against it is refused.
- **One question at a time**, at most once per conversation, the way a friend
  flipping through an album would.
- **Absence is not deletion** — a moment on an unplugged drive is simply not
  offered until the drive is back.

**Why it matters more than it looks.** This is the mechanism by which the
Digital Conscience stops being a form he fills in and becomes a conversation
he has with his own photographs — and it is exactly the interface a person
with memory loss can still use: someone who loves them sits beside them and
says *"look — tell me about this one."*

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
