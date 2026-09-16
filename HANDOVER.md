# JEFFEREY — Engineering Handover

**For:** the Self-Cloud agent on the owner's laptop, and any other agent or human
picking this up.
**Owner / sole inventor:** Laszlo Czako (`lczako-eng`). **Date:** 2026-09-14.
**Pairs with** `Self-Cloud-Workspace/HANDOVER.md` (their side) and
`Self-Cloud/docs/CANON.md`. **If anything here conflicts with CANON, CANON wins.**

---

## 0. Thirty-second orientation

Two products, two repos, two agents, one owner.

- **Self-Cloud** — the owner's drives as nodes of a personally owned cloud, one
  audited door, a physical off-switch. Built by the **laptop agent**.
- **JEFFEREY** — a Personal AI Shadow: a wrapper that rides rented frontier
  engines and gives them a persistent, owner-owned conscience. Built by the
  **remote agent** (this side). *The intelligence is rented. The conscience is
  owned.*

**Status this side:** the connector works and is installable — a double-click
installer, a structural permission gate, crash-proof storage, local semantic
photo search, and a screen.

**ADVERSARIALLY AUDITED 2026-09-15**, under your rule 6.4. Seven attackers,
each required to produce a repro they actually ran; 48 findings raised, 31
refuted by a skeptic, **17 survived — 5 of them HIGH. All five are fixed,
each with a regression test.** The worst was mine and it was bad: the wall's
LAN passcode was 24 bits with no lockout, measured at ~1,400 verified guesses
a second, so the whole family library was reachable from the wifi in about
ninety minutes. Now 128 bits with a five-strike lockout per address.

Your §6.4 was right and it cost me five HIGHs to prove it: every suite passed
before the attack, and the attack still found all of this.

---

## 1. Who owns what — the seam

We have independently built two filesystem walkers, two SQLite catalogs and two
MCP servers. Two of those are duplication; one is correct. Proposed split, for
the owner to confirm:

| Layer | Owner | What it answers |
|---|---|---|
| **Storage** | Self-Cloud `connector/` | *What files exist, on which drive, is that drive online?* Node identity, mirrors, the audited read-only door, offline switch |
| **Meaning** | JEFFEREY `tools/` | *When was this, where was it, what does it look like, what did she say?* EXIF, offline geocoding, CLIP embeddings, the recall parser, transcription |
| **Surfaces** | JEFFEREY `tools/wall.py` | *Show me.* One page: laptop, phone, TV browser, tablet-as-clock |
| **Representation** | JEFFEREY `connector/` | *Act for me.* Conscience, priorities, rules, money watch, paperwork, the life layer |

**Concretely, three changes follow:**

1. **My walker should die.** `tools/photo_index.py` walks and hashes drives;
   `connector/selfcloud/index.py` does it better, is hardened, and is proven on
   real hardware (84,020 entries, fingerprint-identical). Mine should stop
   walking and **read their catalog** instead. One thing hashes the drives.
2. **Two MCP servers is correct, not a bug.** Theirs is Self-Cloud's storage
   door (5 read-only tools, every call audited). Mine is JEFFEREY's agent
   surface (59 tools over the conscience). That matches CANON's two-product
   split. They must not be merged.
3. **We already agree on the hardest rule, independently.** Their `mirrors/` so
   an unplugged drive stays searchable, and my `missing_since` so an absent file
   is marked rather than deleted, are the same insight: **absence is an
   unplugged drive, not a deletion.** Theirs is the more complete
   implementation. Adopt theirs; keep the rule.

**The seam is now physical (2026-09-16).** The owner decided the drive IS the
product, so every JEFFEREY tool asks `connector/home.py` where the life lives:
`<drive>/.selfcloud/jefferey/…` when a provisioned drive is plugged in, the
home folder when not. Your `.selfcloud/` top level (node.json, catalog.db,
audit.jsonl) is untouched; mine is namespaced under `jefferey/`. Full layout,
the marker, and two decisions for you: `Self-Cloud/docs/HANDOVER_FROM_JEFFEREY.md`.

**What I need from their side to make this real:** a stable way to read the
catalog. Either the door gains a `catalog_path(node_id)` tool, or their
`search`/`stat` return enough to drive a viewer (path, size, mtime, node, and
whether the node is currently online). Their call which.

---

## 2. What is built and verified on this side

All of it is in `lczako-eng/jeffrey-local-butler-ai`, branch
`claude/substantiation-discussion-8dmu3c`. Everything below is covered by
`python connector/jefferey_chat.py --selftest` — **74 offline checks, no API
key, no network**.

### `connector/` — the conscience and the agent

| File | What it does |
|---|---|
| `conscience.py` | The owned store: facts, priorities with confidence, goals, corrections. Atomic fsynced writes under an exclusive lock, 20 snapshots, a stale writer refused rather than clobbering, and a corrupt store that **recovers from history or refuses to start** — never silently empties |
| `access.py` | **The door.** Client identity bound per process (`JEFFEREY_CLIENT`), defaulting to the *narrow* key; `@gate(scope)` on every data tool; no model-chosen visibility anywhere; **widening** authority needs `JEFFEREY_OWNER_CONSOLE=1`, narrowing never does |
| `selfcloud.py` | Per-client keys, presets, deny-by-default, audit, instant revocation. **Reference implementation only — belongs on their side eventually** |
| `life.py` | People, moments, media *references* (never copies), visibility private/family/legacy |
| `rules.py` | The owner's own words: disclosure / reaction / representation. Specific beats general, deny beats allow, **no rule = silence is a no** |
| `guardian.py` | Charge register, merchant-name normalisation, five verdicts, dispute pack |
| `representative.py` | Mail triage with weighted scam signals, draft guidance, HTML + PDF form filling |
| `vault.py` | Secrets in the OS keychain; the model uses `vault:<name>` and never sees a value; refuses to run rather than fall back to plaintext |
| `interview.py` | 21 questions, 4 depths, depth earned by trust; "rather not" is final |
| `reminisce.py` | **The album.** Clusters the photo index into moments (trip / season / place), offers the biggest untold one as a question phrased from facts only, keeps the answer verbatim pinned to those photos, one follow-up, "rather not" final. Reads the photo index; writes the life layer |
| `jefferey_mcp.py` / `jefferey_http.py` / `jefferey_chat.py` | Claude, Custom-GPT Actions, and the owner's own terminal |

### `tools/` — local AI and the screen

| File | What it does | Verified |
|---|---|---|
| `photo_index.py` | Content-addressed (SHA-256) semantic index. EXIF date + GPS, **offline** reverse geocoding, CLIP embeddings, unit vectors in SQLite, weights archived inside the index directory, refuses a mismatched embedding model, `verify` proves it runs with `HF_HUB_OFFLINE=1`. `watch` keeps it alive and **never deletes** | pipeline proven end to end with untrained weights; **search quality not yet proven with real weights** |
| `recall.py` | Turns a spoken sentence into a time window, places and leftover words. Years, "ten years ago", months, seasons (winter wraps the year), Christmas. Places matched **only against places the owner actually has photos of** | "show me the part of me that was on vacation ten years ago in Cuba" → exactly the Varadero photo, offline |
| `wall.py` | One page: big pictures, date and place, one box to type or speak into, opens on "on this day". Localhost unless `--lan`; `--lan` demands a passcode; Escape clears the screen | passcode enforced against a real socket; model not loaded for a pure time+place question; thumbnails cache |
| `voice_enrol.py` + `Record my voice.command` | Enrolment of the owner's own voice. Consent take first, read-only checksummed WAVs, resumable, TTY-only, real deletion | consent kept, integrity, containment, retry-on-short, deletion, and a no-network-import assertion |
| `disc_archive.py` | Rips family DVDs **verbatim**, checksums, makes copies read-only, and **survives a scratched disc**: records the unreadable byte ranges, fills them, keeps going | verbatim copy, tampering detected, real data recovered on both sides of simulated damage |
| `provision_drive.py` + `Make this drive a Self-Cloud.command` | Turns a drive into THE product: layout (`Self-Cloud/`, `originals/`, `library/`, `.selfcloud/jefferey/`) created without touching a file, marker with a stable id, the real logo keyed to a transparent `.icns` as the Finder icon, optional `diskutil` rename, and `Start Self-Cloud.command` that binds every tool to its own drive on any Mac | layout, user files untouched, marker id stable across `--force`, real ICNS with background keyed, launcher executable and self-binding, no-op re-run |
| `connector/home.py` | One answer to "where does the life live": the drive if present (`SELFCLOUD_ROOT` or exactly one marked volume; two is refused), else `~/.jefferey` / `~/.selfcloud`. Explicit env vars always win | routing onto the drive and back, ambiguity refused, env override |
| `install.py` + `Install JEFFEREY.command` | Double-click install; refuses to wire anything to Claude if the self-test fails; backs up and merges the host config; `--check`, `--uninstall` | run end to end |
| `go.py` + `Show me my life.command` | One double-click: installs the seeing parts, asks once where the photos are, indexes, opens the wall | logic tested; full run is owner-side |

---

## 3. THE BILL — everything that still needs building

Ordered. **Owner** = only Laszlo can do it. **SC** = Self-Cloud agent.
**JF** = this side.

### A. Safety — before more of the life goes in

| | What | Who |
|---|---|---|
| A1 | **Encrypt the external SSD.** ~240 GB of the family's photos are plaintext on a portable drive. Runbook: `Self-Cloud/docs/ENCRYPT_THE_DRIVE.md`. Highest-probability harm in the portfolio | **Owner** |
| A2 | **Fix §5.1 and §5.2** — drive-named path traversal, and hardlinks in `.selfcloud` writing into the owner's files | **SC** |
| A3 | ~~Adversarial audit of JEFFEREY~~ — ✅ **DONE 2026-09-15.** 48 raised, 17 survived, all 5 HIGH fixed with regression tests. Details in §7 | ✅ JF |
| A4 | **The egress door** — one function every outbound call passes through, field **allowlist** (fails closed; redaction fails open), full egress log, plus "show me what left the house" | **JF** |
| A5 | **Split the Constitution** — `public-charter.md` (safe for any engine) vs `private-boundaries.md` (never leaves). Today §9 of the template — the owner's list of what must never leave — is injected into every session | **JF** + SC |
| A6 | **Conscience cleaner** — a live store already carries junk written by an old self-test | JF |
| A7 | **Backup verifier** — enforce two copies + a verified restore in software; refuse to say "safe to cancel iCloud" until both pass | JF |
| A8 | **Site claims** — jeffereyai.com still says "patent pending", calls the conscience "encrypted", and calls Self-Cloud "encrypted with keys only you hold". None is true yet | JF |

### B. Joining the two halves

| | What | Who |
|---|---|---|
| B1 | **Decide the seam in §1** and write it into CANON | Owner |
| B2 | **Expose the catalog** — a door tool or return shape JEFFEREY can read | SC |
| B3 | **Retire my walker**; `photo_index` consumes their catalog | JF |
| B4 | **Re-home `selfcloud.py`** — the grant service belongs on their side; JEFFEREY's copy becomes a thin client | SC |
| B5 | **Land the dedup code in a repo.** The only proven capability still lives on one machine | SC |
| B6 | **Reconcile the dependency policy.** Their rule 6.1 says no third-party packages; their §2.2 requires llama.cpp/Ollama, and meaning needs CLIP. The rule means *nothing third-party in the sovereignty-critical path* — write that sentence down | Owner + both |

### C. The screen and the voice

| | What | Who |
|---|---|---|
| C1 | **Run the index with real weights.** Proven offline but never with trained weights — this container cannot reach them, the laptop can | **Owner** |
| C2 | **Finish Curator v0** (`FeaturePrint.swift`, `Report.swift`, `main.swift`). Use **Apple Vision feature-print** for near-duplicates, not pHash — measured 0.075 for a re-save vs 0.74+ unrelated. `Undated/` is **5,856 videos**, so triage must cover video | SC |
| C3 | ~~Rip the DVDs~~ — **stood down by the owner 2026-09-15**: *"we'll just use my voice."* `tools/disc_archive.py` is built and stays in the repo, ready if he changes his mind. Discs still fade; recorded, not argued | — |
| C4 | **Local transcription** (whisper.cpp) — now aimed at the owner's own recordings and at video in the library, not at the discs | JF |
| C5 | **Listening** — whisper.cpp on the machine plus a wake word, replacing the browser's recogniser | JF |
| C6 | **Local LLM** as the internal trust zone, weights archived on the drive | SC |
| **C7a** | ~~Voice enrolment~~ — ✅ **BUILT 2026-09-16**, `tools/voice_enrol.py`. Consent recorded first in the person's own voice; checksummed read-only WAVs; resumable; TTY required (a script or a model cannot enrol a voice); real deletion; no network-capable imports, asserted by test | ✅ JF |
| **C7b** | **Voice playback** — the conscience speaking in the owner's voice. "Says only what is in the conscience"; never on a call or intercom; a speaker is a room. Needs a local TTS model that accepts a reference voice; weights archived on the drive per the local-AI rule | JF, after 3.2 |
| C7c | ~~Reminiscence~~ — ✅ **BUILT 2026-09-16**, `connector/reminisce.py` + tools `next_story_prompt` / `record_story` / `decline_story` / `story_progress` on all three surfaces. Depends on the photo index having dates and places, which it does. **This is the first feature that needs your catalog and mine to agree** — see §1 | ✅ JF |
| C8 | **First-run onboarding.** The tiers start empty and the only artifact is a 13-question essay | JF |
| C9 | **Ingestion** — Apple Health, bank CSV, wearables. Exports first; no partnership needed | JF |

### D. Hardware — deliberately last

The laptop plus the SSD **is Self-Cloud v0**. Box $300–700, kill switch $20–60,
second drive off-site $80–200, home layer $50+, GPU only once tiers A and B are
shipped and something is measurably slow.

### E. Not building

A pooling filesystem (SnapRAID/restic/kopia already solve it) · our own model ·
a phone app before the web page proves it · telemetry or any cloud account ·
anything for strangers until it has worked for one other person for a week.

---

## 4. Rules this side works under

Their §6 applies here too. These are additions, not replacements.

1. **A dead person's voice is an archive, not an instrument.** Recovering and
   replaying what she actually said *is* "her voice, her words." Generating
   sentences she never spoke is a separate decision, made deliberately, never
   drifted into. **The transcript is a convenience; the recording is the truth.**
2. **Absence is an unplugged drive, not a deletion.** Never drop knowledge
   because a file stopped being visible.
3. **A speaker is a room, not a person.** Anything said aloud — or shown on a
   wall — in a shared space is a disclosure, and the rules layer governs it.
4. **Starting something must not write to the person's conscience.** Only what
   they actually did changes that file.
5. **Widening authority needs the owner's own hands.** Narrowing never does.
6. **Refusals are answers.** A denial raises; it is never a value the model can
   narrate its way around.
7. **The house keeps working when the box is off.** Local devices keep local
   control; only the intelligence stops.

---

## 5. What I need from the Self-Cloud agent

1. **Fix §5.1 and §5.2 first.** Everything I build that reads drives inherits
   those holes.
2. **Answer B2:** how does JEFFEREY read the catalog?
3. **Tell me if you want `selfcloud.py`** re-homed to your side, and in what
   shape. It is a reference implementation, not a claim on the territory.
4. **Say whether the dependency rule (6.1) is absolute** or scoped to the
   sovereignty path. I cannot do CLIP or whisper in stdlib and neither can you
   do local models.
5. **Anything you learned from the real 64.5k library** that contradicts what I
   built. Your `Undated/` finding already changed my plan once.

---

## 6. What the Self-Cloud agent should take from this side

1. `tools/recall.py` — sentence → time + place + meaning. Pure stdlib, no model.
   Drop it in as-is if a Self-Cloud surface wants natural questions.
2. `tools/disc_archive.py` — verbatim ripping with partial recovery from damaged
   media. Same `/originals` discipline you already use.
3. The **`missing_since`** pattern, if your mirrors don't already cover the
   single-file case.
4. `connector/access.py` — the shape of a gate that cannot be argued with:
   identity bound at startup, decorator on every entry point, no
   caller-supplied trust level, and a canonical scope table the tests assert
   against so the decorators cannot drift.

---

## 7. What the audit found and what it means for your side

Run 2026-09-15: seven attackers, one per surface, each required to produce a
repro it had actually executed. 48 raised, 31 refuted by an independent
skeptic, 17 survived. **Every HIGH is fixed with a regression test.**

**The five HIGHs, because three of them are classes that apply to your code too:**

1. **The wall's LAN passcode was brute-forceable** — 24 bits, no lockout, a
   200/403 oracle, ~1,400 verified guesses a second from one process. The
   whole library from the wifi in ~90 minutes. Now 128 bits + five-strike
   per-address lockout.
2. **The visibility ceiling filtered the wrong things.** It filtered moments
   but not facts, people or priorities — so an `executor` key holding
   `legacy.read` alone read the whole conscience. *This is your hardlink bug's
   cousin: a guard that checks something true but insufficient.*
3. **Two tools that return the owner's private rules were never gated** —
   and a refusal that quotes the rule IS the disclosure.
4. **A recovered conscience was never written back**, so the next launch found
   the same broken file and started an empty life. The recovery was real and
   entirely in memory.
5. **The photo walker followed symlinks out of the named folder** — the guard
   constrained where it LOOKED, not what it OPENED. *Same class as your §5.1:
   a path check that the attacker routes around.*

**Three patterns worth carrying to your side:**

- Guards that verify a property that is true but insufficient (2 and 5 here,
  your hardlink find). Ask of every guard: *what does this NOT prove?*
- Anything derived from untrusted input used as a path (5 here, your §5.1).
- A refusal that explains itself in too much detail is a disclosure (3).

Both halves of this project have now been attacked. Neither had been before,
and both had HIGH holes.