# The Master Build List

*Everything discussed, in one place. Updated 2026-09-14.*

**The reframe that matters:** the laptop plus the external SSD **is Self-Cloud
v0**. A box is a packaging decision, not a prerequisite. Almost everything below
runs on the machine already on the desk — so nothing waits on a purchase.

Four columns throughout: **BUILT** (working, tested), **BUILDABLE NOW** (on the
laptop, no hardware, no purchase), **NEEDS HARDWARE**, **OWNER ONLY** (nobody
else can do it).

---

## 0. What is done and working

Every item here has code in `connector/` or `tools/` and is covered by
`python connector/jefferey_chat.py --selftest` — 74 offline checks, no API key.

### The conscience — the owned core
| | |
|---|---|
| Conscience store | facts, priorities, goals, corrections, in one plain JSON file the owner can read, edit and delete |
| Priority learning | corrections reinforce (+15% of headroom) or erode (−30%); below 0.25 the hierarchy flips and confidence resets |
| Durability | atomic fsynced writes under an exclusive lock, 20 snapshots kept, stale writer refused, corrupt store recovers from history or refuses to start rather than silently emptying |
| Startup writes nothing | launching a surface no longer touches the file; the revision number means something happened |

### Representing the owner
| | |
|---|---|
| Operational AI | observe / recommend / act; `authorize_action` gate with spend caps; every act and every denial logged |
| Opportunity Engine | scores what's worth saying: ≥0.75 interrupt, ≥0.40 daily brief, else stay quiet |
| Representative | mail triage with weighted scam signals, draft guidance in the owner's voice, HTML form fill, PDF AcroForm fill |
| Guardian | charge register, merchant-name normalisation (`GODADDY.COM 480-505-8855` = `GoDaddy Inc`), five verdicts, dispute pack |
| Vault | secrets live in the OS keychain; the model uses `vault:<name>` references and never sees a value; refuses to run rather than fall back to plaintext |

### Knowing the person
| | |
|---|---|
| Life layer | people, moments, media references (never copies), visibility private/family/legacy |
| Rules | disclosure / reaction / representation, in the owner's own words; specific beats general, deny beats allow, **no rule = silence is a no** |
| Interview | 21 questions, 4 depths, depth earned by trust; "rather not" is final and never revisited |
| Story | `tell_story` respects the visibility walls; `story_gaps` shows what's missing while there's time |

### The doors
| | |
|---|---|
| Self-Cloud grants | per-client keys with presets, deny by default, full audit, instant revocation |
| Access gate | identity bound per process, `@gate(scope)` on every data tool, **no model-chosen visibility**, widening requires the owner's console, narrowing never does |
| MCP surface | 59 tools for Claude Desktop / Claude Code |
| HTTP surface | 57 operations for Custom GPT Actions, per-client bearer tokens |
| Chat surface | `jefferey_chat.py` — the owner's own terminal, streaming, tool-use loop |
| Installer | `Install JEFFEREY.command` — double-click; refuses to connect if the self-test fails; `--check`, `--uninstall` |

### Local AI
| | |
|---|---|
| `tools/photo_index.py` | content-addressed (SHA-256) semantic photo search, resumable, unit vectors in SQLite, weights archived on the drive, refuses a mismatched model, `verify` proves it runs with the network off |

### Proven on real data, but the code is NOT in any repo
| | |
|---|---|
| Exact dedup | ~80,000 photos → 14,500 sets, 15,636 redundant copies, ~55 GB, SHA-256 confirmed, nothing deleted, checksum-verified copy to the SSD. **This lives only on the laptop. Recovering it into the repo is item 2.3.** |

### Written down, not code
Website (live), the 24-rule directive pack, `FOUNDER_DIRECTIONS.md`,
`HANDOFF_TO_SELF_CLOUD.md`, `ORB_PRIOR_ART_LOG.md`, `SELF_CLOUD.md`, and on the
Self-Cloud side `CANON.md`, the conscience architecture, the constitution
template, the 09-12 review and `ENCRYPT_THE_DRIVE.md`.

---

## 1. Safety — build before more of the life goes in

Order matters here. These are the things that make it safe to keep going.

| # | What | Why it's first | Effort |
|---|---|---|---|
| 1.1 | **The egress door** — one function every outbound call passes through, field **allowlist** (fails closed; redaction fails open), full egress log | The two-trust-zone model has no code behind it. Right now nothing stands between the conscience and a cloud model | 1 day |
| 1.2 | **"Show me what left the house"** — a readable log of exactly what was sent, to whom, when, and why | The one report that makes the privacy claim checkable instead of promised | hours |
| 1.3 | **Split the Constitution** — `public-charter.md` (safe for any engine) vs `private-boundaries.md` (never leaves) | The list of what must never leave is currently injected into every session. It's the most sensitive file in the system and it goes out first | hours |
| 1.4 | **Conscience cleaner** — find and remove junk written by old self-tests | A live store already has three stray "Laszlo" memories and a revoked key from 2026-09-09 | hours |
| 1.5 | **Backup verifier** — enforce two copies + a verified restore in software; refuse to say "safe to cancel iCloud" until both pass | The owner's own standing rule, currently only prose | 1 day |
| 1.6 | **Site claim fixes** — remove "patent pending"; the conscience is described as "encrypted" and Self-Cloud as "encrypted with keys only you hold", neither of which is true yet | Nothing is for sale so there's no real exposure, but they must be true before there is | minutes |

---

## 2. The laptop as Self-Cloud v0

All of this runs on the machine that exists. No purchase.

| # | What | Notes | Effort |
|---|---|---|---|
| 2.1 | **Photo index with real weights** | Code is done; this container can't reach HuggingFace, the laptop can. 3 commands | owner, 30 min |
| 2.2 | **Photo viewer** — thumbnails in a local web page, not file paths | A list of paths is not a demo. This is what makes local search feel real | 1 day |
| 2.3 | **Land the dedup code in the repo** | The only proven capability lives on one machine. Package it, add a test, commit | 1 day |
| 2.4 | **Near-duplicate detection (pHash)** | Tier A — no model needed. Catches the burst-of-twelve-almost-identical-shots case that exact dedup misses | 1 day |
| 2.5 | **Timeline / "on this day"** | Deterministic, from EXIF. Feeds the morning brief and the story layer | 1 day |
| 2.6 | **Local web UI on the home wifi** | Opens on his phone. Makes the laptop reachable like a cloud account, and is the honest ancestor of the box | 2–3 days |
| 2.7 | **First-run onboarding** | The three tiers start empty; the only onboarding artifact today is a 13-question essay. Needs to be a conversation | 2 days |
| 2.8 | **Morning brief as a habit** | `daily_brief` exists; this is scheduling and delivery | hours |
| 2.9 | **The living index** — ✅ **BUILT 2026-09-14.** `photo_index.py watch` re-scans the named folders on its own, embeds what's new, and **never deletes**: a file that has gone is marked missing with a date, and comes back untouched when the drive is reconnected | Only the folders he named, listed on every run; stops when the machine stops; every pass logged to a `scans` table | done |
| 2.10 | **Run the watcher automatically** — a launchd job so it runs while the Mac is awake | `watch --once` is built for exactly this | hours |

---

## 3. The endpoint: local model, the voice, the house

| # | What | Depends on | Effort |
|---|---|---|---|
| 3.1 | **Voice enrolment — recording only, no playback** | nothing. **Do this early: it is the only item with a closing window.** Record him; record his mother if she is living and willing | 1 day to build |
| 3.2 | **Local LLM on the laptop** (Ollama/llama.cpp, weights archived on the drive) | 2.1 | 1–2 days |
| 3.3 | **Ask-your-life** — questions answered from the conscience by the local model, with the network off | 3.2, 1.1 | 2 days |
| 3.4 | **Voice playback** — the conscience speaks in his voice; "her words only" enforced in code, not policy | 3.1, 3.2 | 2–3 days |
| 3.5 | **Health / transactions / wearables ingestion** | start with stable file exports (Apple Health XML, bank CSV) — no partnership needed. Feeds the Guardian real data | 1 week |
| 3.6 | **Device enrolment + pairing** — keypair per device, code shown by the box, grants bound to a key not a name | 2.6 | 1 week |
| 3.7 | **Encryption at rest, in software** | after 4.1 | 3 days |

---

## 3b. Surfaces — in the room, not in a chat window

*Added 2026-09-14, from: "I want to be able to talk to it, and cast to TVs —
'show me the part of me that was on vacation ten years ago in Cuba' — and it
should be able to read all my data."*

**The insight that keeps this cheap: "show me on the TV" and "show me on my
phone" are the same build.** One page the box serves; a phone opens it, a TV
browser opens it, an old tablet on the kitchen counter opens it in kiosk mode
and *is* the clock. One page, many screens — never three products.

That sentence about Cuba decomposes into four parts, and only one needs a
neural network:

| Part of the sentence | What it really is | State |
|---|---|---|
| "ten years ago" | EXIF `DateTimeOriginal` | **built** (`read_when_where`) |
| "in Cuba" | EXIF GPS + offline city database | **built** (`name_places`) |
| "on vacation" | CLIP embedding | **built** (`photo_index`) |
| taking the sentence apart | a parser, not a model | **built** (`tools/recall.py`) |
| "show me" | a web page | 3b.1 |
| saying it out loud | local speech-to-text | 3b.2 |

| # | What | Notes | Effort |
|---|---|---|---|
| 3b.1 | **The wall** — one local page that shows results as photographs, big, with the date and place under each | Serves to laptop, phone, TV browser, old tablet. This is also item 2.2 and 2.6; they were always the same thing | 2 days |
| 3b.2 | **Listening** — wake word + whisper.cpp speech-to-text, entirely local | Never a cloud speech API: the whole point is that "our holiday in Cuba" is not somebody else's search query | 2 days |
| 3b.3 | **The clock** — an old phone or tablet in kiosk mode showing the wall, always on | v1 costs nothing and uses a device already in a drawer. Purpose-built hardware is a later packaging decision, not a prerequisite | hours |
| 3b.4 | **Casting** — AirPlay from the box to Apple TV, or just open the wall's URL in the TV's own browser | The browser route needs no code at all | hours |
| 3b.5 | **Answering out loud** — the reply spoken in his own voice | same build as 3.4 | — |
| 3b.6 | **"Read all my data"** — the same when/where/meaning index over documents, messages, health and transactions, not only photos | The index is already content-addressed and general; this is new *readers*, not a new index. Do it after 3.5 ingestion | 1 week |

**Rules this layer inherits, non-negotiably:** a speaker is a room, not a
person — anything said aloud in a shared space is a disclosure and the rules
layer governs it. A screen in a living room is the same. "Show me Cuba" on the
TV when there are guests is a disclosure decision, not a display decision.

---

## 3c. The tape archive — the new urgent item

*Added 2026-09-14. His mother has died. Her voice exists on old videotape.*

**This replaces voice enrolment as the thing that can become impossible.**

*Corrected 2026-09-14: the tapes were already transferred — it's on DVDs.*
Better news, still urgent. A home-burned DVD-R is a **photosensitive dye that
fades**, not stamped metal, and discs from the 2000s are already failing —
quietly, playing fine for eleven minutes and then stopping. But ripping is not
real-time, needs no deck, and the video is already a file, so copying it
verbatim loses nothing.

**Open question for the owner: do the original tapes still exist?** If so they
are the better master — the DVD transfer is compressed MPEG-2 and discarded
detail permanently. Discs first (fast, cheap, urgent); tapes afterwards, if
they survived.

The line that governs all of it, from `FOUNDER_DIRECTIONS.md` §4(e): **a dead
person's voice is an archive, not an instrument.** Recovering what she actually
said is the rule "her voice, her words" at its purest. Generating sentences she
never spoke is a separate decision, made deliberately, never drifted into.

| # | What | Who | Notes |
|---|---|---|---|
| 3c.1 | **Buy a USB DVD drive** (~$25) | owner | The only purchase. Most Macs no longer have an optical drive |
| 3c.2 | **Rip every disc, verbatim** — ✅ **BUILT: `tools/disc_archive.py`** | both | `rip /Volumes/DISC --label "Mum's birthday 1994"`. Copies byte for byte, checksums everything, makes the copy read-only, and **survives scratches**: records which byte ranges failed, fills them, keeps going — you get everything on both sides of the damage. A disc that reads badly is worth a second try in a different drive; different lasers read different discs |
| 3c.3 | **Archived copies are `/originals`** — ✅ built into the ripper | me | Read-only enforced, `verify` re-checks every checksum years later and reports anything that changed |
| 3c.4 | **Audio extraction (lossless FLAC)** — ✅ built, needs `brew install ffmpeg` | me | Nothing thrown away before transcription |
| 3c.5 | **Local transcription** (whisper.cpp) | me | On his machine. Not one second of her voice leaves the house |
| 3c.6 | **Index it like the photos** — when, where, meaning | me | So "what did mum say about the house" is a question with an answer, and the answer plays *in her voice* |
| 3c.7 | **`legacy` visibility by default** | me | This is precisely what that tier was built for |

**A hard rule for this material:** the transcript is a convenience, never a
substitute. What gets played back is **the recording**. A transcript can be
wrong; a recording cannot lie about what she said.

---

## 3d. Who this is really for

*Added 2026-09-14: "great for dementia and Alzheimer's patients as well."*

Reminiscence and life-story work are established non-pharmacological practice in
dementia care, and what they need is exactly what this system produces: a
person's own photographs, their own recordings, their own people, organised so
that a carer or a family member can bring the right thing to hand at the right
moment. Two consequences that change the build, not just the pitch:

- **It argues for the archive, not the synthesis.** Reminiscence work uses real
  material. A confused person, a synthesised voice, and a relative who has died
  is the worst combination this technology can produce. The line in 3c is what
  prevents it.
- **It argues for the surfaces (§3b), not the chat box.** Someone with memory
  loss does not type a search query. They look at a screen on the wall while
  someone who loves them says "look — that's Cuba, that's you." The wall, the
  clock and the TV *are* the interface for this.

---

## 4. Owner only — nobody else can do these

| # | What | Time |
|---|---|---|
| **4.1** | **Encrypt the external SSD.** `docs/ENCRYPT_THE_DRIVE.md` in the Self-Cloud repo. Check the format first — exFAT needs an erase, so the second copy comes first | an afternoon |
| 4.2 | **Turn on FileVault** on the Mac. Same photos, and the laptop leaves the house more than the drive does | 5 min |
| 4.3 | **Install and use JEFFEREY daily** — the conscience only fills if he talks to it | ongoing |
| 4.4 | **Merge `claude/canon-addenda`** in the Self-Cloud repo | 1 min |
| **4.1b** | **Get a USB capture stick and a working tape deck.** See §3c — the tapes are now the only thing here that can become impossible | this month |
| 4.5 | **iCloud library size** — needed to size the drive layout | 2 min |
| 4.6 | **Original Pages file date** for the orb whitepaper — the PDF export is dated 2025-12-01, so if summer 2025 is real the evidence is the source file | 10 min |
| 4.7 | Patents and filings | **his, out of scope for this list** |

---

## 5. Needs hardware — genuinely later

Deliberately last. None of it is required to have a working, useful,
owner-controlled system on the laptop.

| # | What | Rough cost |
|---|---|---|
| 5.1 | The box v0 — mini PC + drive, always on, running the connector and the index | $300–700 |
| 5.2 | The kill switch — relay or solenoid on the power/network rail | $20–60 |
| 5.3 | Second drive, off-site — the other half of the two-copy rule | $80–200 |
| 5.4 | Home layer — Home Assistant bridge, **with the hard rule that the house keeps working when the box is off** | $50 + devices |
| 5.5 | GPU/NPU tier — only if tiers A and B are shipped and something is measurably slow | $600–1,500 |
| 5.6 | Multi-node / recycled-drive federation — reuse restic/kopia/SnapRAID, do not invent a pooling filesystem | — |

---

## 6. Explicitly not building

- **A pooling filesystem.** SnapRAID, mergerfs, restic, kopia and ZFS already
  solve heterogeneous always-changing consumer disks. Reuse them.
- **Our own model.** JEFFEREY is a wrapper. The intelligence is rented.
- **A phone app**, until the local web UI (2.6) proves people want it.
- **Cloud accounts, telemetry, crash reporting.** The moment any of it exists,
  the privacy claim changes and so do the legal obligations.
- **Anything for strangers**, until it has worked for one other person (his
  wife) for a week without him being called.

---

## 7. The next three things

1. **4.1 — encrypt the drive.** Owner. Highest-probability harm in the whole
   portfolio and it is an afternoon with no code.
2. **4.1b — start the tapes.** Owner. Buy the capture stick, find a deck, begin
   with the oldest. This is now the only item on the list where waiting can make
   it impossible — tape sheds, and capture is real-time.
3. **1.1 + 1.2 — the egress door and the "what left the house" log.** Mine.
   The last structural hole; everything downstream sends more data, not less.

*(Voice enrolment for a living person, formerly item 3, is still built next for
his own voice — but the closing window moved to the tapes.)*
