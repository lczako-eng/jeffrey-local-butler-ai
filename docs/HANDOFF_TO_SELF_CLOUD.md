# HANDOFF — to the Claude Code session building Self-Cloud on the laptop

*Written by the Claude Code session that built Jefferey (this repo). You are
the session building Self-Cloud. We cannot talk to each other; this document
is how we share one picture. Read it fully before building anything that
touches Jefferey, and write the counterpart (`SELF_CLOUD_CONTRACT.md` in your
repo) for me to read.*

**Owner:** Laszlo Czako. **Date:** 2026-09-08.

---

## 1. Who is who

| Product | Repo | What it is | Owned by |
|---|---|---|---|
| **Self-Cloud** | *(yours — push it to GitHub under lczako-eng so this session can read it)* | The platform. The owner's personal cloud on a drive they physically own: photos, files, backups, dedup, a network that goes up and down. Replaces iCloud — no monthly fee for life. Regulated by AI. | You |
| **Jefferey** | `lczako-eng/jeffrey-local-butler-ai` (this repo) | An AI *wrapper* — a connector that rides Claude / GPT and gives the rented engine a persistent, owned identity: the user's representative, secretary, protector, and the keeper of their Digital Conscience. **Jefferey is one accessor of Self-Cloud, not its owner.** | Me |
| Website | `lczako-eng/Jeffrey-AI-Butler` | jeffereyai.com — the public face and the public build spec. | Me |

The founder's framing, which both of us build to: *Self-Cloud is the vault.
Jefferey is a caretaker with a key.* Different AI clients get different keys
(a plain Claude session, a plain GPT session, the Jefferey wrapper, a family
member, an executor). The owner grants and revokes; the switch is final.

## 2. What Jefferey already has (so you don't rebuild it)

All in `connector/`, all tested offline (`python connector/jefferey_chat.py --selftest`, 15 sections):

- `conscience.py` — the owned store: priorities with confidence, corrections,
  facts, goals, **permission gate** for real-world acts (Observe/Recommend/
  Act, per-category caps, audit log), Opportunity Engine, `orb_state()`.
- `directives.md` — the identity pack any engine loads to *be* Jefferey.
- `jefferey_mcp.py` / `jefferey_http.py` / `jefferey_chat.py` — the three
  surfaces (Claude via MCP, GPT via HTTP Actions, standalone). 52 tools.
- `representative.py` — mail triage with scam/predatory-billing detection,
  drafting in the user's voice, HTML/PDF form filling.
- `vault.py` — secrets live in the **OS keychain**, used by *reference*
  (`vault:<name>`), resolved locally at write time; the AI never sees a value.
- `guardian.py` — unauthorized-charge detection (the GoDaddy problem),
  dispute packs.
- `life.py` — the Digital Conscience's life layer: people, moments, media
  **by path reference only**, per-item visibility (`private`/`family`/`legacy`).
- `interview.py` — how the conscience is drawn out: one earned question at a
  time, depth gated on trust, declines final.
- `selfcloud.py` — per-client access grants with scopes, deny by default,
  audit, revocation. **This is on the wrong side of the line — see §4.**

Today everything persists to one JSON file: `~/.jefferey/conscience.json`
(override: `JEFFEREY_CONSCIENCE_PATH`). Moving it onto the Self-Cloud drive is
a path change and nothing else. Preserve that property.

## 3. The boundary

**Self-Cloud owns:** the drive; the file system; the photo library and its
index (dates, faces, places, captions, duplicates); backup; encryption at
rest; **the access-grant service** (who holds which key, what scopes, the
audit log); the network state (up/down) and the physical switch; the
canonical location of the conscience file and the life-layer data.

**Jefferey owns:** the identity and directives; the reasoning about the
person (priorities, corrections, opportunities, triage, drafting, the
interview, story-telling); the orb's emotional state; his own key — and
nothing about *granting* keys.

**Rule:** Jefferey never reaches around Self-Cloud. Every read or write of
photos, files, or the life layer goes through Self-Cloud's API under the
`jefferey` key. If the drive is off, Jefferey reports "unreachable" and stops.
He does not cache a shadow copy to "help."

## 4. What moves from my side to yours

Take `connector/selfcloud.py` as a **reference implementation** of the grant
model — its scopes, presets, deny-by-default, audit and revocation are the
behaviour the owner asked for — and **re-home it in Self-Cloud**. Once your
grant service exists, I will reduce Jefferey's copy to a thin client that
calls yours. Until then, treat mine as a spec, not a source of truth.

The scopes as currently named (rename freely, but keep them readable by a
human owner):

```
facts.read  priorities.read  priorities.write  goals.read
life.read   life.write       media.read        family.read   legacy.read
money.read  money.write      vault.names
```

Presets: `claude-raw` / `gpt-raw` → facts, priorities, goals only.
`jefferey` → all of the above except secret values (which live in the OS
keychain, never on the drive). `family` → family.read, media.read.
`executor` → legacy.read only.

## 5. The seam — what Self-Cloud should expose to Jefferey

A local API on the drive's host (HTTP on localhost, or a Python module if
we're in one process — your call; say which in your contract). Minimum:

| Capability | Why Jefferey needs it |
|---|---|
| `check_access(client, scope)` → allowed/denied + reason | He asks before every read/write; deny by default |
| `network_state()` → up / down / degraded | So he says "the drive is off" instead of guessing |
| `files.list/read/write(path)` under his scopes | Conscience file, life-layer data, documents to fill |
| `photos.query(date range, people, place, text)` → items with ids, paths, captions | The diary, "on this day", story-telling |
| `photos.caption(id, text, people)` | The photo-intake question ("who's this?") writes back |
| `photos.duplicates()` (read) | He can tell the owner what your dedup found |
| `conscience_path()` | Where his file lives on the drive |
| `audit(entry)` | Every access he makes lands in *your* log, not only his |

Everything above is *pull* from Jefferey's side. Self-Cloud never needs to
call into Jefferey.

## 6. Security requirements (non-negotiable — this is the thesis)

1. **Encryption at rest** on the drive. A stolen drive must be a brick.
2. **No secrets on the drive.** Passwords, card numbers, SIN/SSN live in the
   OS keychain (`vault.py` pattern). The drive holds who you are, not the keys.
3. **Deny by default.** Unknown client → nothing. Known client → exactly its
   scopes.
4. **Audit everything**, allow and deny, in the owner's own store.
5. **Revocation is instant and total**, record preserved. Including Jefferey's.
6. **The switch is final.** Network down means nothing is reachable by anyone,
   Jefferey included — no cache, no queue that flushes later without consent.
7. **Least authority for the builder, too.** Your session has full authority
   over the laptop for development. The *product* must never assume that.

## 7. The backup rule — before iCloud is cancelled

**Do not let the owner cancel iCloud until two independent copies exist.**
A single drive is a single point of failure; drives fail without warning.
Minimum: the Self-Cloud drive **plus** one more copy on different media,
ideally kept elsewhere (a second drive off-site, or an encrypted archive).
Dedup first, then back up, then verify the second copy restores, *then*
cancel. Please put this check into Self-Cloud itself — "yours, and safe" is
the pitch; "yours" alone is just a hard drive.

## 7b. Originals are sacred — the on-drive layout

The founder's rule: **always keep an untouched copy of the originals on the
same drive**, separate from the working library. Same-drive originals guard
against *mistakes* (an over-aggressive dedup, a bad rename, a Self-Cloud bug,
an accidental edit); the second drive in §7 guards against *physics* (the
drive dying). Both are required — they defend against different things.

```
/originals    exactly as downloaded from iCloud. Read-only, immutable,
              a checksum stored per file so an original can be PROVEN
              unchanged years later. Nothing writes here — not the
              organizer, not the dedup, not Jefferey. No key has write
              scope to this path, ever.
/library      the organized, de-duplicated, captioned working copy.
/conscience   Jefferey's store and the life layer.
```

Consequence to check now, before the layout is locked: originals + library
means the photos occupy roughly **double** their size on the drive. Measure
the iCloud library and decide whether 1 TB is enough or the drive must be
larger, *before* the structure is committed.

## 7c. What the Digital Conscience is, in the founder's words

**The Digital Conscience is the person's journal** — a daily and family
journal, kept *for* them by Jefferey and stored *on* Self-Cloud: what
happened, who was there, the photo from that day, in their own words, added
a little at a time over years. It is not a database about the person. The
priorities, the story-telling, the protection all grow out of the journal,
because the journal is the raw material of knowing someone.

Consequences for the seam: the journal's entries live in Self-Cloud's
storage (under `/conscience`), its photos are references into `/library`,
and Jefferey is the one who writes to it (under his key) and reads it back —
"on this day", the weekly note, the story. Self-Cloud keeps it; Jefferey
keeps it *alive*.

## 7d. Two permission layers, not one

The owner's words: *"You give permission of what you want in that Digital
Conscience, and there's rules to the Digital Conscience as well — share with
me only these, react this way only to these, react to others about me in
this sense."*

So there are **two layers**, owned by different sides:

| Layer | Question it answers | Owned by |
|---|---|---|
| **Self-Cloud keys** (§4) | *Which client may touch which storage?* | Self-Cloud |
| **Conscience rules** (`connector/rules.py`) | *Of what Jefferey holds, who may hear what, how does he react to the owner, how does he speak of them to others?* | Jefferey |

Plus the **intake gate**: the conscience is a curated subset — items enter
only when the owner includes them (`conscience_include`), and can be taken
back out. Storage is total; the conscience is curated. Your API only needs to
let Jefferey *reference* an item; the choice to include it is his layer.

## 7e. The box is the hub; everything feeds it

Founder's direction (2026-09-08): the Self-Cloud unit — drive **plus a small
always-on computer** — is the hub. It runs the connector, talks to the rented
engines, and syncs to the phone and other devices, which are windows onto
it. Design Self-Cloud as the source of truth with devices holding working
copies; secrets never sync (keychain per device).

And it ingests the life the person already generates: Apple Health exports,
wearable APIs (e.g. Oura), bank/Revolv transaction exports, calendar. Plan an
**ingestion layer** in Self-Cloud (start with stable file exports: Apple
Health XML, bank CSV; add live APIs where offered). Jefferey then reads
those streams under his key and the owner's conscience rules — health
defaults to *owner only*. The Guardian's charge register should be fed from
real transactions once that stream exists, replacing hand entry.

## 8. Naming the founder's IP correctly

Use these exactly: **JEFFEREY** (never "Jeff"), **Self-Cloud**, **Personal AI
Shadow**, **Digital Conscience**. The founder coined *Digital Conscience*
years ago; treat it as a product name. No "butler" anywhere.

## 9. How we coordinate from here

1. You push Self-Cloud to GitHub under `lczako-eng` and write
   `SELF_CLOUD_CONTRACT.md` answering §5 (what you expose, how, where).
2. The owner adds your repo to my session; I read it and adjust Jefferey to
   call your API — thinning `selfcloud.py` and re-pointing `life.py`'s media
   references to your photo index.
3. Any change to the seam goes into the contract document **first**, code
   second. Neither of us changes the other's side.

If anything here contradicts what you've already built, the owner decides —
write the disagreement into your contract and he'll settle it.
