# JEFFEREY stress test: the honest report

*For Laszlo first, then for the engineering agents. Run 2026-10-12 to 2026-10-13. Data: `docs/stress-test-2026-10/`.*

## 1. The honest answer

JEFFEREY is not ready for your family. It is not ready for a stranger who pays. You can use it yourself, carefully, but not yet the way the product promises.

The base works. Guest keys are refused when they try to write or widen. Power cuts are survived. Ordinary card numbers are caught. Nothing in JEFFEREY can pay, send or sign by itself.

Around that base, too much trusts whatever the AI says. One short or empty word in a "forget" call wipes your whole life. The form tool will save over any file on your Mac. At your own terminal, the AI can raise its own authority until a $9,500 wire comes back "approved", and it can give ChatGPT a key to your private memories. JEFFEREY itself still cannot send money, but anything that trusts its approval would.

Private things also reach the wrong people. Your health facts go to plain guest AIs even when you wrote a rule against it. The family key reads your private notes about other people. Many secrets are missed when they are written in French or in ordinary phrasing.

The single most important thing: **nothing irreversible should happen because an AI asked.** Deleting, overwriting, widening a key and approving a spend all need your own confirmation, outside the AI, plus a real undo. Alongside that, and starting this week, make a second verified copy of the drive. JEFFEREY's memory exists only on the drive, and its 20 backups sit on the same drive.

## 2. The numbers

**How the test ran.** We covered 26 areas. Testers wrote 1,521 scenarios and ran 1,425 of them against the real code. Your usage limit interrupted the run twice, so it finished in three parts, but every area was completed. The 96 scenarios not executed needed a real Mac, a real person, or a feature that does not exist. Independent skeptics then tried to reproduce findings, in batches per area:

- In onboarding and drive, every finding rated medium or higher.
- In durability, the first 8 findings.
- Everywhere else, every critical and high finding.

Critical findings also got an impact check. **Medium and low findings outside those areas were not checked by a skeptic.** Section 5 lists them separately as tester-reported.

### Overall

| | Count |
|---|---|
| Scenarios written | 1,521 |
| Executed (code actually run) | 1,425 |
| PASS | 360 |
| FAIL | 539 |
| GAP (needed thing does not exist) | 137 |
| RISK (works as coded, harmful in that situation) | 485 |

### Skeptic results

| | This pass | Earlier pass (onboarding, drive, durability first 8) | Total |
|---|---|---|---|
| Findings checked | 143 | 32 | 175 |
| Kept (reproduced) | 142 | 32 | 174 |
| Refuted | 1 | 0 | 1 |
| Contested (kept, severity disputed) | (see I-43, I-66) | 1 | |
| Could not be checked | 0 | 0 | 0 |
| Kept, by severity | critical 4, high 97, medium 40, low 1 | high 8, medium 18, low 6 | |
| Medium findings never checked by a skeptic | | | 127 |

- **Refuted:** voice#5, "Anyone can delete with no presence check and nothing is recorded".
- **Critical impact check:** durability#0 was confirmed. In the final triage it is merged into I-05 and rated high.
- **After merging:** the triage folds the kept findings into 69 issues: 3 critical, 39 high, 23 medium and 4 low.

### Per area

| Area | Title | Total | Executed | PASS | FAIL | GAP | RISK | Mediums not checked |
|---|---|---|---|---|---|---|---|---|
| access | Keys and permissions | 58 | 57 | 16 | 14 | 1 | 27 | 3 |
| accessibility | Elderly, confused and non-technical users | 61 | 56 | 7 | 31 | 9 | 14 | 8 |
| adversarial | Attacks and abuse | 50 | 50 | 15 | 16 | 2 | 17 | 3 |
| album | Interview, album and dementia care | 63 | 63 | 21 | 22 | 4 | 16 | 6 |
| business | Selling this to other people | 60 | 49 | 9 | 16 | 16 | 19 | 5 |
| buying | Buying things | 59 | 56 | 15 | 23 | 5 | 16 | 6 |
| drive | The Self-Cloud drive | 64 | 64 | 15 | 17 | 3 | 29 | 0 |
| durability | Crash-proof memory | 58 | 56 | 22 | 20 | 1 | 15 | 8 |
| egress | The egress door: what leaves the house | 51 | 51 | 16 | 18 | 1 | 16 | 3 |
| email | Email and correspondence | 48 | 48 | 12 | 4 | 1 | 31 | 3 |
| engines | Every AI engine | 46 | 44 | 28 | 6 | 1 | 11 | 3 |
| family | Family, guests and the household | 56 | 54 | 8 | 20 | 6 | 22 | 2 |
| house | The house | 56 | 54 | 11 | 20 | 8 | 17 | 5 |
| learning | Learning who the owner is | 64 | 64 | 13 | 29 | 5 | 17 | 4 |
| life | Life story, people and legacy | 63 | 63 | 10 | 28 | 6 | 19 | 10 |
| money | Money watch and fraud | 75 | 74 | 14 | 39 | 7 | 15 | 7 |
| onboarding | Sign-up, install and first run | 74 | 62 | 21 | 28 | 11 | 14 | 0 |
| ops | Running it day to day | 52 | 49 | 8 | 15 | 4 | 25 | 5 |
| paperwork | Forms, PDFs and secrets | 50 | 50 | 13 | 17 | 2 | 18 | 2 |
| photos | Photos, recall and the wall | 64 | 62 | 16 | 25 | 7 | 16 | 13 |
| privacy | Privacy, law and rights | 56 | 44 | 8 | 13 | 5 | 30 | 5 |
| scale | Scale and performance | 47 | 46 | 19 | 10 | 0 | 18 | 6 |
| seam | Self-Cloud and JEFFEREY together | 45 | 28 | 0 | 18 | 7 | 20 | 2 |
| selling | Selling things | 81 | 68 | 11 | 46 | 11 | 13 | 7 |
| texting | Texting and messaging | 64 | 62 | 19 | 32 | 6 | 7 | 4 |
| voice | Voice | 56 | 51 | 13 | 12 | 8 | 23 | 7 |

Two things stand out. The seam between Self-Cloud and JEFFEREY has no passing scenario: 0 of 45, with only 28 executed. Engines (28 of 46 PASS) and durability (22 of 58) are the strongest areas.

## 3. What works

Every item below was executed, and the output was observed.

**Guest keys hold their line**
- A plain Claude session gets the narrow claude-raw key by default, with 3 read scopes (access-01).
- Guest Claude and ChatGPT cannot write facts, forget, write rules, widen their own permissions or grant themselves the life layer (access-04, adversarial-04/11/12/13/14, engines-02/04/05, learning-26/27). Off the owner console the reply is "403 owner-console required" (adversarial-13).
- The family key sees family and legacy moments only: private moments False, facts 0, values 0 (access-23).
- The executor key sees only legacy, with no people, facts or values (access-26, family-35/36, life-07, privacy-24).
- The 2026-09-15 fixes hold: the life layer is still denied to claude-raw (adversarial-03), the wall lockout holds on the LAN (house-17), and the symlink walker is fixed (photos-04).
- The HTTP surface returns 401 with no token or a bad token (egress-31, house-16).

**JEFFEREY cannot move money, sign or call**
- None of the 64 MCP tools pays, transfers, sends, signs, submits or buys (business-39).
- Asked to place a call in your voice, Claude finds no voice tool on any surface, with any key (voice-14/15/16).
- With no permission set, "unlock the door" is denied (house-07), and so are selling (selling-21), buying (buying-01) and texting (texting-02). The denials are logged.
- When the amount is a normal number, caps work: $150 against a $100 cap is denied (buying-03), and an amount exactly at the cap behaves correctly (buying-04).

**It survives power cuts**
- When a power cut tears the store at a plain-text byte, 46 of 49 tear points recovered all 30 facts and kept a .corrupt copy (durability-01).
- A kill in the middle of a write loop reopened at rev 327 with 327 facts and no temp file left (ops-44).
- Empty, deleted and multiply-torn stores recover correctly from history (durability-02 to -07).

**Standard secrets are caught**
- Luhn-valid cards with spaces or dashes are refused in both directions, on every surface (egress-01/15/28).
- A refused card's digits never reach the log (privacy-30). A card typed into the terminal chat is caught (privacy-31).
- Forms with a vault reference fill correctly, the original stays untouched and the secret stays off every logged path (paperwork-10). Canonical SIN, card, CVV and signature labels are refused (paperwork-02).

**It works without the internet and does not phone home**
- With the internet down, local Hermes works, and the log says "stays in the house" (house-28).
- The only outbound network code is the engine you chose (business-57).
- A customer can use the local model only, with no subscription (business-54).

**It holds up under load**
- A store of 10,000 facts and 5,000 memories loads in 93.5 ms (scale-01).
- Eight concurrent HTTP clients wrote 200 of 200 facts and 200 of 200 memories. gpt-raw was refused all 200 times, and 0 of 240 log entries were misattributed (scale-19).

**Photos and album basics**
- Real EXIF photos cluster into trips such as Kabul, Kandahar, Budapest and Varadero (album-01).
- Stories are kept word for word, including Hungarian and emoji (album-04).
- GPS 0,0 is not turned into Ghana (album-22).
- The photo pipeline survives broken files, decompression bombs and 2,000 tiny files (photos-01/02/05/06).

**Install and drive setup**
- Install backs up the Claude config, keeps your other connections and passes 85 self-test checks (onboarding-09).
- Reinstall and offline reinstall work (onboarding-11/12).
- Provisioning a used SSD leaves the existing photos byte-identical (drive-01).

**Money and scam basics**
- Exact registered charges are quiet (money-01).
- Real price increases and same-month double billing are caught (money-10/14).
- A 1,000-line statement processes without trouble (money-37).
- The classic CRA gift-card and arrest scam comes back as likely_scam, score 1.0 (email-01), and so does a CRA arrest text (texting-11).

## 4. What is broken

All 69 issues come from the triage, most severe first. Each line gives who fixes it and the effort. "JEFFEREY" means the engineering agents on this repo. "Both" means JEFFEREY plus the Self-Cloud laptop agent. Two issues are marked contested.

### Critical

- **I-01 · JEFFEREY · days**: One empty or short word in a "forget" call wipes the whole life, with no preview, confirmation or undo.
  - In plain words: forget "" or "Ann" deletes every fact, memory, person and rule containing those letters. In the test that took Anna, Joanna, an anniversary memory and a legacy letter. The reply is only a count.
  - Fix: reject empty and short (<3 chars) match strings. Match people and memories by id. Make deletion two steps: preview with ids, then delete by id. Require your confirmation when many items would go. Keep a dated trash and add a restore command. Log every forget.

- **I-02 · JEFFEREY · days**: fill_pdf writes to any path the AI names. Read-only guest keys can reach it, and it can put vault secrets into any field.
  - In plain words: the form tool can save over a war photo, your will, Claude's settings, JEFFEREY's memory or the log of what left the house. Guests can put your SIN into any box and save it to iCloud.
  - Fix: move it behind a write scope guests lack. Confine output to a fixed .pdf outbox, and refuse symlinks, cloud folders and the store, log and switch paths. Resolve vault:X only into a matching field. Log each secret used.

- **I-03 · JEFFEREY · hours**: The album and the photo wall share one SQLite connection across threads.
  - In plain words: stories told through Claude or ChatGPT often fail to save. The TV wall shows "Nothing matched" or blank tiles.
  - Fix: one connection per thread or per call. Add tests that make concurrent calls. Show a plain error instead of "Nothing matched".

### High

- **I-04 · JEFFEREY · days**: At your terminal, the AI can raise its own authority (payments, key grants), and the change carries over to every surface.
  - Fix: remove set_permission, selfcloud_grant and selfcloud_add_scope from what the engine is given. Make widening a slash command you type, confirmed with y/N (or Touch ID). Never allow "act" on money without a cap.
- **I-05 · JEFFEREY · days**: Every read writes the whole store plus a snapshot. The 20-step undo history lasts about 20 tool calls, and parallel readers collide.
  - Fix: move the access log to its own append-only file. Snapshot only on content change. Keep time-tiered snapshots and pin one before any destructive call.
- **I-06 · JEFFEREY · days**: authorize_action is not a gate. Any key, even a revoked or unknown one, gets an answer, and a missing, negative or NaN amount skips the cap.
  - Fix: deny unless the amount is a finite number > 0 when a cap is set. Validate caps. Gate the tool and refuse revoked keys. Log allowed verdicts with a single-use id.
- **I-07 · JEFFEREY · days**: The secret scan misses French and natural phrasings, separated digits and house codes ("mon NIP est 4321", "garage code 4821", dotted cards).
  - Fix: normalise first. Add bilingual and house-code keywords plus API-key, IBAN, bank and health-card shapes. Scan profile values too. Offer "move to vault".
- **I-08 · Both · days**: Where the life lives is decided once per process, with a silent fallback to the laptop. The result is split brain, a shut switch that doesn't shut and revocations that reset.
  - Fix: record the drive id at provisioning. Refuse with "your drive is not plugged in" instead of falling back. Keep grants and the door switch in one owner-level policy. Report from every log.
- **I-09 · JEFFEREY · days**: Any key, including guest, family, revoked or unknown ones, can revoke other keys and read and pollute the key list and access log.
  - Fix: without the owner console, a key may narrow only itself. Refuse revoked keys. Make the key list and access log owner-only. Log actor and subject separately.
- **I-10 · JEFFEREY · days**: Family and legacy views ignore your disclosure rules, return everyone's private notes and open "after I'm gone" material now.
  - Fix: add person visibility, default private. Apply deny rules in who_am_i and tell_story. Separate legacy from family behind a release event. Enforce media.read.
- **I-11 · JEFFEREY · weeks**: Facts have no sensitivity class. Health, minors' and third-party facts go to every guest AI.
  - Fix: add a visibility field with private defaults for health, money, minors, home security and third parties. Apply rules to what engines read. Add category scopes and a caregiver preset. Make rule tools owner-only.
- **I-12 · JEFFEREY · hours**: Shutting the door does not stop writes, and the log still says "refused".
  - Fix: check the door before the tool runs. Write the log entry before the side effect. Treat an unreachable switch as shut.
- **I-13 · JEFFEREY · days**: Scam triage misses most elder scams (grandchild, "new number", gift cards plural, French, seller scams) and tells the AI not to bother you. 14 of 16 realistic Canadian scam texts were not flagged.
  - Fix: normalise text. Add the missing signal sets. Never say "routine" or "Do not interrupt" when money, cards, codes, secrecy or a family claim appears. Keep an EN/FR regression corpus.
- **I-14 · JEFFEREY · days**: The inbound secret scan blocks scam checks on exactly the messages that quote a card, SIN, code or password, and tells the AI to stop.
  - Fix: hard-refuse only on tools that store text. For analysis tools, mask secret-shaped spans, still return the verdict and treat the secret as a scam signal.
- **I-15 · JEFFEREY · hours**: About 1 in 60 photo IDs (sha256) looks like a SIN or card number. That jams the album and permanently blocks "who am I" and "tell my story".
  - Fix: use letter-aware boundaries in the scan, stop sending raw sha lists to engines, and report a story as kept when it was kept.
- **I-16 · JEFFEREY · days**: Forget is not complete. The text stays in the egress log, in snapshots and in other sections, and a forgotten person comes back as a question.
  - Fix: one erase operation across every section, the log (keeping a tombstone) and snapshots, with a receipt and a forgotten-names list.
- **I-17 · Both · days**: Any volume with the marker file becomes your conscience: planted sticks, second-hand drives, a relative's drive.
  - Fix: require a valid marker. Pair the Mac to drive ids at provisioning and refuse unknown drives. Never trust permissions on an unpaired drive. Add a resale wipe.
- **I-18 · Both · days**: Other connectors in the same Claude (the filesystem server, R-evolv) sit outside JEFFEREY's door and log, and the installer says nothing.
  - Fix: warn loudly about any connector that covers HOME or the drive. Load JEFFEREY's rules as server instructions. Rename R-evolv's "Self Cloud" memory. State the limit in START_HERE.
- **I-19 · JEFFEREY · days**: Hand edits to the memory file are silently undone, and a deleted private fact is sent again.
  - Fix: track a content hash. Adopt valid external edits and refuse stale saves. Explain parse errors plainly.
- **I-20 · JEFFEREY · days**: Restoring a backup is unsafe and invisible. There is no restore tool, and a later recovery brings back the abandoned timeline.
  - Fix: handle timelines on load and ship a restore command. Show recovery notices in the brief and in --check.
- **I-21 · JEFFEREY · days**: There is no version or update mechanism. Two copies, unpinned dependencies and a session branch mean stale code runs silently, and a reinstall re-widens the key.
  - Fix: add a version, a minimum version recorded in the store, a pinned lock file and "Update JEFFEREY.command". Keep the existing --client. Never wire Claude to /Volumes.
- **I-22 · Owner · hours**: The GitHub default branch ships the pre-audit connector, with no egress door, keys or secret scan.
  - Fix: merge the product branch into main or make it the default, archive the old stub, point the README at START_HERE and tag a release.
- **I-23 · JEFFEREY · hours**: explain_basis and draft_guidance return every fact to keys that hold only priorities.read.
  - Fix: require facts.read to return facts, refuse empty topics and add a selftest.
- **I-24 · JEFFEREY · days**: Drafts for buyers and contacts are never checked against your disclosure rules, and "when are you home alone?" is treated as routine.
  - Fix: normalise audiences, apply rules in draft_guidance, add check_draft and a "safety" verdict that always interrupts.
- **I-25 · JEFFEREY · days**: Nothing records who said a fact or memory. AI paraphrases are stored as "his words", and injected values become yours.
  - Fix: record the source on every write. Mark text verbatim only when it matches what you typed. Hold engine-inferred writes as pending and cap their confidence.
- **I-26 · JEFFEREY · days**: The AI chooses who can see each memory, and visibility can never be narrowed later.
  - Fix: store engine writes as private, widen only by the owner, and add set_visibility.
- **I-27 · JEFFEREY · days**: Adding a person with the same name overwrites a different person. In the test, a son named after his grandfather inherited the grandfather's "died 2003".
  - Fix: give people stable ids, flag possible duplicates and append notes rather than replace them.
- **I-28 · JEFFEREY · days**: Grounding uses raw substring matching. "car" grounds caregiver choices, and "rent" pulls a PTSD medication into a landlord letter.
  - Fix: whole-word matching with stemming, refusal of tiny topics, match reasons, and no health or third-party facts unless named.
- **I-29 · JEFFEREY · days**: Form filling puts your SIN and PIN into the wrong boxes ("sin" inside "business", "pin" inside "shipping").
  - Fix: whole-word alias tables. Resolve a vault secret only into its own fields, refuse other people's fields and show where each secret will go.
- **I-30 · JEFFEREY · hours**: Profile matching fills buyers', spouses' and doctors' boxes with your identity and can overwrite your own name.
  - Fix: drop loose matching, mark party-qualified labels needs_you and confirm before changing full_name.
- **I-31 · JEFFEREY · hours**: Filled PDFs keep the form's hidden actions, and field names written by an attacker reach the AI as if they were instructions.
  - Fix: strip /AA, /OpenAction, JavaScript and Submit actions, and mark field names as untrusted.
- **I-32 · JEFFEREY · days**: A "rather not" on a painful photo moment is not durable. A re-index or one new photo asks about it again.
  - Fix: keep declines in the conscience with the moment's sha set, and give moments stable ids.
- **I-33 · JEFFEREY · days**: The album ignores your rules, the people you described and how much trust has been built. It opens on the funeral photos and offers Kabul next.
  - Fix: check guidance_for in next_prompt, keep the album closed until trust ≥ 2, start small and allow skip.
- **I-34 · JEFFEREY · hours**: Photos you deleted keep appearing on the wall.
  - Fix: filter missing photos, check before serving cached thumbnails and add a forget command.
- **I-35 · JEFFEREY · days**: The wall's microphone sends speech to Google or Apple while the page says "Nothing was sent anywhere". It also has public caching and the passcode sits in the URL.
  - Fix: hide the mic unless recognition is on-device, make the page text truthful, add no-store, use a cookie passcode and default to lan=False.
- **I-36 · JEFFEREY · days**: Charge checks match merchant names exactly, so real statements become false alarms and a cancellation can silently fail to arm.
  - Fix: strip processor and region tokens, use fuzzy matching with aliases and ask when nothing matches.
- **I-37 · JEFFEREY · days**: Re-checking a statement invents duplicate charges and inflates dispute claims.
  - Fix: idempotent recording, validate the whole statement before writing and use cadence-based duplicate windows.
- **I-38 · JEFFEREY · hours**: Cadence and "did not authorize recurring" are stored but never checked, so unauthorized renewals pass.
  - Fix: flag unauthorized renewals, enforce cadence windows, parse booleans strictly and fix the yearly wording.
- **I-39 · JEFFEREY · days**: Charge-after-cancel ignores dates, and dispute packs overclaim. The AI accuses merchants with false statements.
  - Fix: store ISO cancel dates, sum only the recoverable amount, choose the template by verdict and treat negative amounts as refunds.
- **I-40 · JEFFEREY · hours**: The least-trusted guest key can plant a fake fraud alert at the top of your daily brief.
  - Fix: gate record_opportunity as a write, record and show its source, and allow "interrupt" only for caretaker or owner entries.
- **I-41 · JEFFEREY · days**: Whole-memory payloads have no size limit and outgrow any AI's context window (about 92k tokens at 2,000 facts).
  - Fix: send a small system prompt, page the big reads, set a byte budget per tool and set the context length for local engines.
- **I-42 · JEFFEREY · days**: Drive encryption assurance can be false or missing. A rename collision checks the wrong drive, and a failed check is silent.
  - Fix: find the drive by device id, refuse colliding names, say "could NOT verify" and re-check at runtime.

### Medium

- **I-43 · JEFFEREY · weeks · contested**: Identity and owner presence are just names in environment variables and plain JSON. Anyone at the Mac, or anyone who can edit the drive, is the owner. *(Kept by skeptics. drive#5 within it was contested and rated low.)*
  - Fix: refuse to start MCP or HTTP with the console flag set, require Touch ID for owner-only actions, HMAC grants, use one conscience per person and record the owner in the marker.
- **I-44 · JEFFEREY · weeks**: The authority model is too coarse. Caps are per purchase only, the AI picks the category, money-moving categories can be enabled, and a sale cap has no floor.
  - Fix: hard-deny transfers, gift cards, crypto, voice calls and intercom. Add period totals, currency, merchant and recurrence, and floor prices for sales.
- **I-45 · JEFFEREY · hours**: The action log can be forged and is incomplete. Approvals are not logged, and entries don't say who wrote them.
  - Fix: log approvals with an id, stamp each entry with client and surface, and reserve internal outcomes.
- **I-46 · Owner · hours**: Public claims don't match the code ("patent pending", "encrypted", "nothing leaves unlogged", "never sends without authorize_action").
  - Fix: make the tracked site edits and describe authorize_action honestly.
- **I-47 · JEFFEREY · days**: Any caretaker session can rewrite the expected-charges register, and charges below the expected amount pass silently, so card testing goes unnoticed.
  - Fix: make register changes proposals you confirm, and flag tiny or unusually low charges.
- **I-48 · JEFFEREY · days**: Priorities flip cheaply and silently.
  - Fix: count for and against separately, lock priorities you stated, log reversals and deduplicate corrections.
- **I-49 · JEFFEREY · hours**: A damaged file with a split accented character (Czakó, Montréal) crashes every launch, and recovery never runs.
  - Fix: decode inside the try block with explicit UTF-8.
- **I-50 · JEFFEREY · hours**: JEFFEREY_ALLOW_RESET=1 permanently destroys the damaged original.
  - Fix: rename it to .corrupt-<timestamp> first.
- **I-51 · JEFFEREY · hours**: On macOS a power cut can tear both the memory and its backups. This is a code trace only and was not run here.
  - Fix: use F_FULLFSYNC and atomic snapshot writes.
- **I-52 · JEFFEREY · hours**: A failed write stays in memory, is served as remembered and is sometimes written twice.
  - Fix: mutate a copy and swap it in only after a successful save.
- **I-53 · JEFFEREY · days**: The wall ignores "rather not" and your rules. Declined war photos open by themselves on the shared TV, and hiding them needs the Escape key.
  - Fix: open on a neutral screen, exclude declined moments, add an on-screen hide button and an idle hide.
- **I-54 · JEFFEREY · days**: Voice enrolment doesn't prove who is speaking or consenting, and the files are world-readable.
  - Fix: verify the consent file, refuse silent takes, add a challenge phrase, require a name, encrypt the takes and set 0700/0600 modes.
- **I-55 · JEFFEREY · days**: Planted symbolic links make setup, the store and voice deletion write over files outside the drive.
  - Fix: lstat, use O_NOFOLLOW/O_EXCL temp files and never open or chmod through a link.
- **I-56 · JEFFEREY · hours**: Deleting a voice says "Gone" while copies remain on the laptop and in the tail of long takes.
  - Fix: search every root, overwrite to full size, state the SSD limits and use per-person keys.
- **I-57 · JEFFEREY · hours**: Signature and attestation boxes are filled without authorize_action or an action-log entry.
  - Fix: detect signature fields and require authorization at the "act" level before writing them, then log the act.
- **I-58 · JEFFEREY · hours**: Driver's licence and passport numbers are stored and released to plain guest sessions.
  - Fix: add them to the sensitive patterns, which makes them vault-only.
- **I-59 · JEFFEREY · hours**: The ChatGPT server accepts weak and duplicate tokens, has no lockout and no failure log, and leaves its docs open.
  - Fix: refuse tokens shorter than 32 characters and duplicates, log 401s with backoff and disable the docs when exposed.
- **I-60 · JEFFEREY · hours**: Prompts accept only single letters. Typing "shut" doesn't shut the door, and "no" renames the drive or keeps a recording.
  - Fix: normalise answers in EN/FR, re-ask on anything unrecognised and always print the door state.
- **I-61 · JEFFEREY · hours**: Folders dragged in from Finder aren't un-escaped, so "Show me my life" exits on any folder name with a space.
  - Fix: use shlex, keep asking until the folder exists and skip .photoslibrary bundles.
- **I-62 · JEFFEREY · hours**: The memory file and its backups are readable by every account on the Mac.
  - Fix: umask 077 and 0600/0700 modes.
- **I-63 · JEFFEREY · hours**: Renaming the drive breaks every indexed photo path.
  - Fix: re-root known shas, or store paths relative to the drive.
- **I-64 · JEFFEREY · hours**: Access refusals reach Claude as a bare "Error executing tool", so key mistakes look like crashes.
  - Fix: return plain refusal results and validate --client.
- **I-65 · JEFFEREY · hours**: The make-drive launcher throws tracebacks on unwritable drives, loops on closed input, renames with no answer and offers installer disk images.
  - Fix: catch OSError, check writability, exclude read-only and installer volumes and require a yes before renaming.

### Low

- **I-66 · JEFFEREY · hours · contested**: Variant SIN labels (NAS, S.I.N.) are not recognised as sensitive. *(The impact check refuted most of the harm, because admit() still refuses literal SINs.)*
  - Fix: normalise labels, add NAS and the French label, and strip non-digits before the checks.
- **I-67 · JEFFEREY · hours**: Short writes to the egress log count as success, so data leaves while its log entry is torn.
  - Fix: loop the write and refuse the send on a short write.
- **I-68 · JEFFEREY · hours**: A damaged memory shows up as a failed self-test at install and as a silent disconnect in Claude.
  - Fix: run the selftest on a temp store, add a "Your memories: OK" line and start a degraded server that explains the restore.
- **I-69 · JEFFEREY · hours**: Claude Code wiring is local-scope only.
  - Fix: pass `--scope user`.

## 5. Reported but not checked by a skeptic

These 127 medium findings were reported by testers in areas where skeptics checked only critical and high findings. **No skeptic reproduced them.** Many overlap with the issues above. Treat them as leads, not proven facts.

**access**
- Widening attempts are never logged, and on MCP every key refusal reaches the model as an opaque crash
- Preset auto-issue surprises: a pre-emptive revoke does nothing, the executor key is live at once, an empty scope list means the full preset
- The guest presets' facts.read exposes sensitive facts, the owner's disclosure rules and the engine map

**accessibility**
- The egress report isn't in plain English, and its default action traps the person in `less`
- The wall isn't usable by touch, low vision or screen readers, and is English-only
- The wall passcode changes at every start, there's no QR code, and the lockout blocks the correct link with the same message
- The wall misreads how older people and French speakers describe time and place
- The album breaks in the situations it exists for: false dates, a permanent "no", an unguarded first topic, lost stories
- Access refusals on Claude Desktop reach the model as "Error executing tool X"
- Start-up collisions give tracebacks or "set an environment variable"
- The default ~/Pictures folder reads inside the Apple Photos library

**adversarial**
- The owner's private standing rules leak to plain rented engines (gated one tier too low)
- Owner-console content injection escalates authority and mints keys; self-widening is blocked only by the directive, not by code
- Unbounded store and audit-log growth, and audit entries forgeable by low-privilege callers

**album**
- Absent photos are still offered: unplugged sources aren't marked missing and stale moment rows are never re-checked
- Wrong or useless "facts" in prompts: dead-clock dates, undated scans invisible, a whole life as one moment
- Erasure is incomplete and blunt
- A terminal sitting stores refusals as stories and then asks follow-ups
- Dementia and caregiver use is unsupported: retellings inflate trust, no speaker field, no caregiver key, anyone at the Mac reads private stories
- The inbound secret scan refuses ordinary war stories

**business**
- The ChatGPT surface is not sellable as documented
- Guardian turns ordinary spending into "recoverable" disputes
- Cost per user and local-model fit are unmanaged
- The trademark is used inconsistently, filings miss the goods sold, and "Self Cloud" is also a hosted product name
- Onboarding is too hard and too risky for the intended elderly users

**buying**
- authorize_action is ungated on MCP and HTTP: guest, family, executor and no-key clients can read the owner's authority table and write into his action log
- The brake doesn't work from chat: narrowing is refused, self-widening attempts leave no trace, and refusal reasons are swallowed on MCP
- Shutting the door does not stop writes: authorize_action and log_action still change the conscience while "offline"
- A raw edit of conscience.json (for example by a filesystem connector) changes permissions silently, with no integrity check and no log entry
- Plain Claude and ChatGPT sessions can read the full purchase log, including purchases that reveal health
- Recurring purchases and Guardian are disconnected, and an engine can whitelist a scam charge

**durability** (findings after the first 8)
- Half an emoji poisons a surface until restart
- Concurrent engines get unexplained failures and hangs, partly because every read writes
- Startup recovery runs unlocked with a shared temp name
- Snapshot failures are silent
- A torn egress line hides the next real send from the owner's report
- Store files are world-readable, and a symlinked temp file overwrites other files
- Recovery and data loss are never shown to the user or the model
- Forgotten facts survive in history and permanently in the egress log

**egress**
- The field allowlist controls field shape, not sensitivity: free-text fields and the whole private life layer leave word for word to rented engines
- Stored text that is an instruction is acted on by an obedient or compromised engine to move private content into wider-audience fields; the door logs this but cannot stop it
- "Every send, word for word" is not true for sends over 64 KB: the log keeps only the first 64 KB

**email**
- The authorize_action gate for sending is advisory, caller-labelled, cap-skippable, cross-surface and unlogged on approval
- The egress log keeps every triaged email body word for word and forever, and forget() cannot remove it
- Scam detection is defeated by obfuscation, non-English text and sender spoofing, and mislabels real legal and debt mail

**engines**
- Tool exceptions bypass the egress door entirely: they are unscanned and unlogged, and they leak the store path
- The Self-Cloud key map and access log are ungated: any engine enumerates who holds keys and who accessed what
- The conscience stores whatever an engine writes: fabricated memories and forged "actions"

**family**
- Disclosure rules match audience and tags as exact strings: aliases bypass a deny, "Nobody" loses to a general allow, and interview intent never becomes a rule
- The egress log is a second word-for-word copy of the private life, readable at the Mac and untouched by erasure

**house**
- Narrowing is ungated across clients: any key, or no key, can revoke the caretaker; keyless clients write into the owner's store
- The "offline" switch also kills the local engine that works without internet
- A power-cut tear in the egress log swallows the next send's record
- Doorbell and parcel smishing passes as "Real and actionable"
- Endpoints to the outside and across the LAN are weak: any token length, no lockout, a plaintext LAN engine that honours proxies, mislabelled destinations, and house connectors running side by side that bypass both doors

**learning**
- Erasure is not erasure: forgotten text survives in corrections, snapshots and the egress log; a full wipe leaves priorities and corrections
- Two engines writing at once: about 65% of corrections, and reads too, fail with ConscienceConflict, with no retry
- Unbounded growth: about 98k tokens of facts at 2,000 facts, and about 9.6k tokens of directives and tools for Hermes before any facts
- Interview "trust" depth is earned by fact counts, so an engine writing 20 trivial facts unlocks end-of-life questions

**life**
- The media.read scope is never enforced
- add_media takes any absolute path: folder names leak, and it works as a file-existence probe
- The password scanner flags ordinary "pin" memories: the veteran cannot record his medal pin, and one such memory locks the whole legacy
- Rule precedence and inputs: a specific allow beats a general deny; the engine chooses tags and audience; remove_rule erases deny rules by substring
- story_gaps does not know about grief or a "rather not", and cannot be snoozed
- Visibility is chosen by the engine on write, and no tool can change or correct a memory
- who_am_i sends the entire private life on every call, and the log keeps only 64 KB of it
- Nothing checks who is typing: anyone at the owner's unlocked Mac gets the private ceiling
- The egress report says family and executor reads went to "a person"; they went through that person's AI vendor
- A used drive brings the previous owner's whole life into a stranger's Claude

**money**
- Amount parsing and validation break whole statements and poison the store
- The secret scan rejects ordinary statement reference numbers
- No tolerance, currency or trial concepts: tax, exchange rates and trials create recurring false alarms
- Multiple subscriptions under one billing merchant overwrite each other
- Money details reach keys denied money.read, and the family key can write into the owner's action log
- Concurrent engines abort statement reviews partway
- Each statement line is a full save plus snapshot, which wipes the recovery history

**ops**
- Installer check, uninstall and post-install messages ignore the drive
- Concurrent engines collide: the Claude surface failed 71% of calls under parallel use
- Borrowed and new Macs: someone else's photos indexed onto the drive, traces left behind, vault secrets don't travel
- Filled forms with resolved secrets are written beside the original, world-readable
- Unbounded growth: the egress log grows about 2.2 GB a year with no rotation, and there are no size caps on text engines write

**paperwork**
- fill_form discloses the set of vault secret names to keys that are denied vault_status
- The null keyring backend silently accepts secrets that never persist

**photos**
- The index keeps one path per photo and never updates it, so moving or deduping breaks thumbnails and missing-detection
- Missing-detection uses an unescaped LIKE on unresolved paths
- The time parser misreads common speech, returns confident wrong windows and crashes on absurd numbers
- Place matching filters out people and matches the wrong countries
- Wrong photos presented as matches: no similarity floor, and a silent fallback when the model is missing
- Dates are made up from the file's modification time, and undated scans cannot be dated
- `watch` on an index that was never built silently indexes nothing
- A macOS Photos library package is indexed twice (originals plus derivatives)
- Index location is fragile: the recall CLI ignores the drive, and a missing drive silently starts a laptop index
- Index and thumbnails are readable by every account on the Mac
- Localhost mode has no passcode and no Host check
- The wall ignores the kill switch and logs nothing it serves
- HEIC support is optional, so an iPhone library can silently go mostly unindexed

**privacy**
- The photo index never forgets and records precise location without opt-in
- Voice biometrics: world-readable files, a weak consent model, overstated deletion
- Conscience and history files are created world-readable
- Third parties' data (emails, friends' diagnoses, minors) has no consent, minimisation or retention handling
- Public and onboarding claims overstate protection

**scale**
- A busy writer starves other surfaces: even read-only calls fail with ConscienceConflict
- Write amplification: a statement review saves the whole store once per charge
- The egress log is not word for word past 64 KB, but the report says it is
- Photo resume and the watcher re-hash the entire library every time
- Album moments don't scale: home life merges into one multi-year moment, and each story stores every hash
- Recall resolves occasions, seasons and months without a year to the current year, even when that date is in the future

**seam**
- Guest keys can revoke or narrow other clients' keys, and the audit trail is ungated
- Hard links in JEFFEREY's drive namespace redirect its writes

**selling**
- Audit trail gaps: approvals not logged, log_action takes unverified claims, and a shut door lets writes happen
- Triage flags honest e-transfer buyers and never looks at the sender
- From Claude Desktop the owner cannot narrow a permission ("stop selling"), and the reason is lost
- Any key, including revoked and family keys, can flood the action log and push every recovery snapshot out
- The owner's selling priorities and item facts are not found for natural requests
- The scanner blocks harmless tracking numbers but lets one-time codes through
- Listing photos can carry the home's GPS location

**texting**
- authorize_action and log_action are a gate the engine can talk its way around
- One-time codes reach the model and are kept in the egress log; blocking depends on wording
- The family safe word against voice-clone calls has no safe home
- Real, time-sensitive messages are suppressed, and family messages are flagged as scams

**voice**
- A different person can join an existing enrolment without consent
- The terminal check does not prove a person is present
- Recordings are plain, world-readable files
- With the drive unplugged, recordings silently land on the laptop and status misleads
- play has no presence check and no log
- The manifest is unsigned and writable
- The wall mic is not offline

## 6. What is not built

The gap auditor confirmed each of these as absent from the code.

**Now**
- Backup verifier and second copy: nothing copies or verifies the conscience, index, voice or originals. "Never cancel iCloud before two verified copies" exists only as prose. (Both)
- Provisioning a drive leaves the laptop conscience behind, so the next session on the drive knows nothing. There is no migration. (JEFFEREY)
- Failures and access denials are invisible on Claude, and there is no health or status tool covering store, drive, free space, backup, recovery, door and version. (JEFFEREY)
- No way to correct learned items: no edit or supersede for facts, no delete or merge for priorities, no way to read corrections back, and contradictory stories are not flagged. (JEFFEREY)
- The iCloud dedup-and-separation pipeline exists in no repo. It lives only on the laptop. (Both)
- Seam decisions are waiting on you: B1, B6, the marker (selfcloud.json or node.json), and who owns the backup verifier. The laptop agent has been silent since 2026-09-14. (Owner)
- Photos cannot be kept off the wall. "On this day" shows screenshots, IDs and war photos to anyone with the passcode. (JEFFEREY)

**Before anyone else uses it**
- Keys govern only JEFFEREY's tools. The wall, recall and the photo index check no key, and wall traffic is not in the egress log. (Both)
- Forget is not real deletion, and there is no export of everything held. (JEFFEREY)
- No per-memory audience, for example "for Emma only". (JEFFEREY)
- No caregiver role. (JEFFEREY)
- No reminders, and no warning that JEFFEREY must not be relied on for medication or safety reminders. (JEFFEREY)
- Grants never expire, and there is no co-signer, merchant allowlist or spend summary. (JEFFEREY)
- Disclosure rules don't reach family engines, and interview answers never become rules. (JEFFEREY)
- No age or content gating of stories for children on a family key. (JEFFEREY)
- No "don't ask" or "deceased" marker on people. (JEFFEREY)
- The secret scan misses bank account numbers and IBANs. (JEFFEREY)
- The model is never given the voice, phone or texting rules. (JEFFEREY)
- The drive does not carry its software, and every launcher points at a personal AI-session branch. (JEFFEREY)
- The "no Terminal" promise breaks for storing a secret, changing the photo folder, opening the album and showing a moment on the wall. There is no QR code. (JEFFEREY)
- No version, update channel or pinned dependencies. (JEFFEREY)
- The encryption runbook sits in the separate Self-Cloud repo, not beside the drive tools, with no guidance for non-Mac, Time Machine or exFAT drives. (Both)
- The photo index stores absolute paths, does not exclude the drive's own folders and duplicates Self-Cloud's catalog. (Both)
- No restore of a snapshot from any surface. (JEFFEREY)
- Elder-scam charge patterns are not recognised in Guardian, and no trusted contact can be alerted. (JEFFEREY)
- Money records cannot be erased or edited, and an executor cannot see subscriptions. (JEFFEREY)
- In voice enrolment, a blank name silently becomes the Mac account name. (JEFFEREY)

**Before selling**
- No consent or capacity record when someone sets JEFFEREY up for a person with dementia. (JEFFEREY)
- No representative or power-of-attorney role. (JEFFEREY)
- No commercial layer: payment, customer EULA, warranty disclaimer, pricing, support or insurance. The current LICENSE forbids commercial use. (Owner)
- No privacy policy or cross-border notice (PIPEDA, Quebec Law 25), in English or French. (Owner)
- A stranger cannot obtain and start the product: no signed download, a git-and-Terminal install, and users with only ChatGPT or no API key get stuck. (JEFFEREY)
- No Windows or Linux path. Say "Mac only" or build one. (JEFFEREY)
- No third-party licence notices. (JEFFEREY)
- Marketing claims run ahead of the code: "every major AI" and "the house keeps working when the box is off". (Owner)
- No French, and no handling of Canadian forms (XFA, tooltips, scanned forms). (JEFFEREY)
- On a new Mac, vault secrets don't travel, the first run needs network and about 2 GB, and model weights are not on the drive. (JEFFEREY)
- No uninstall-and-erase path for when a Mac or drive is sold. (JEFFEREY)
- Album and photos extras: dating scanned prints, snooze, told_by, merging repeated stories. (JEFFEREY)

**Later**
- An inheritance flow: heirs, a release condition, a preservation mode and the drive-key handover. (Both)
- Voice playback and its safeguards in code. (JEFFEREY)
- Texting and calling integration. (JEFFEREY)
- Triage that considers who sent a message. (JEFFEREY)
- Sending email. The host's mail connector acts outside JEFFEREY's gate. (JEFFEREY)
- A signed, single-use authorization token that a purchase tool could verify. (JEFFEREY)
- Home automation. (Both)
- Money extras: trial expiry, card reference and deadline in disputes, CSV/OFX import. (JEFFEREY)
- The seller side: incoming payments, sale records, regulated items, a double-sale lock. A cheap directive can come sooner. (JEFFEREY)
- Photo search extras: faces, relative times, Canadian occasions, videos and RAW. (JEFFEREY)
- .metadata_never_index on the drive. (JEFFEREY)
- Card numbers spelled out in words. (JEFFEREY)

**Never**
- Customer accounts and sign-in. Use an offline licence file if licensing is ever needed.
- A native phone app. Make the wall an installable web app instead.

**Gap claims the auditor disproved or could not confirm**
- "Engine refusal stop_reason not handled": **disproved.** The handling exists at jefferey_chat.py:1252. It just could not be run live.
- "Self-Cloud connector behaviour" (node id after erase, erasure across catalog.db and audit.jsonl, one shared id): **unverifiable, not proven absent.** The code is private. The Self-Cloud side should confirm it.
- "No per-person family keys": **partly wrong.** Named per-person keys and independent revocation already work. Only per-memory audience is missing.

## 7. What we need, in order

### This week (stop the harm)

1. **Owner:** make the product branch the GitHub default, or merge it to main, and tag a release (I-22).
2. **Owner, with the Self-Cloud laptop agent:** make a second, verified copy of the Self-Cloud drive by hand, today. Do not cancel iCloud. Do not give anyone else a key yet.
3. **JEFFEREY:** guard every destructive tool against empty and short match strings. This is the hours-sized first half of I-01; two-step delete and trash follow.
4. **JEFFEREY:** move fill_pdf and pdf_form_fields behind a write scope and confine their output path (I-02). Strip hidden PDF actions (I-31). Require authorization for signature boxes (I-57).
5. **JEFFEREY:** remove the three widening tools from what the engine sees at the terminal, and add a typed, confirmed /permit command (I-04).
6. **JEFFEREY:** check the door before any tool runs (I-12).
7. **JEFFEREY:** give each thread its own SQLite connection in the album and the wall (I-03).
8. **JEFFEREY**, quick fixes that are hours each:
   - validate amounts and caps and gate authorize_action (I-06, first part)
   - stop sha256 IDs from tripping the scan (I-15)
   - make explain_basis require facts.read (I-23)
   - gate record_opportunity (I-40)
   - fix the profile matcher (I-30)
   - stop deleted photos showing (I-34)
   - fix renewals and cadence (I-38)
   - fix UTF-8 recovery (I-49), the reset that destroys the original (I-50) and phantom writes (I-52)
   - set file modes (I-62)
   - return readable refusals on Claude (I-64)
   - add licence and passport to the sensitive patterns (I-58)
   - make prompts understand words (I-60), and handle Finder paths (I-61)
9. **JEFFEREY:** add a status tool and stop failures being invisible (gap, now).
10. **Owner:** record decisions B1, B6 and the marker in CANON, and assign the backup verifier to one side.

### Before your family uses it

11. **JEFFEREY:** move the access log out of the store, snapshot only on change, keep tiered history and add a restore command (I-05, I-20, the restore gap).
12. **Both:** pair the Mac to its drive. Refuse instead of falling back to the laptop. Keep one policy file for grants, revocations and the door. Migrate the laptop store at provisioning (I-08, I-17, the migration gap).
13. **JEFFEREY:** a key may only narrow itself, and the key list is owner-only (I-09).
14. **JEFFEREY:** add sensitivity classes for facts and people, apply disclosure rules to everything engines read, separate legacy from family, add per-memory audience and child gating, and add a caregiver preset (I-10, I-11, I-26, related gaps).
15. **JEFFEREY:** finish delete: two-step, trash, full erase across the log and snapshots, and an export (I-01, I-16, gap).
16. **JEFFEREY:** a bilingual secret scan plus IBAN and bank shapes (I-07, gap). Rebuild scam triage with an EN/FR test corpus that never says "don't interrupt" on money or family claims (I-13). Let scam checks run on messages that quote secrets (I-14).
17. **JEFFEREY:** album and wall respect your rules: durable declines, trust before opening, no auto-shown declined photos, a touch hide button, truthful mic text, private caching, LAN off by default (I-32, I-33, I-35, I-53, photos-off-wall gap).
18. **JEFFEREY:** record the source on every write, hold engine-inferred writes as pending, use stable people ids and fix grounding (I-25, I-27, I-28, I-48, the corrections gap).
19. **JEFFEREY:** fix forms, whole-word aliases and vault-to-matching-field only (I-29). Check drafts against rules and add a safety verdict for home-casing questions (I-24).
20. **JEFFEREY:** fix Guardian merchant matching, idempotent statements, dated cancels, honest dispute packs, and register changes you confirm (I-36, I-37, I-39, I-47, the elder-charge-pattern gap).
21. **JEFFEREY:** hard-deny money-moving and voice categories, add period caps, an honest action log and approval ids (I-44, I-45, I-06 second part).
22. **JEFFEREY:** make hand edits safe (I-19), size budgets (I-41), macOS full fsync (I-51), a correct encryption check (I-42) and symlink safety (I-55).
23. **Both:** installer warnings about other connectors covering HOME or the drive. Rename R-evolv's "Self Cloud" memory so it is not confused with the drive (I-18).
24. **JEFFEREY:** a version number, a pinned lock and an "Update JEFFEREY" launcher. The drive carries its software (I-21, gaps).
25. **JEFFEREY:** voice consent and deletion done properly (I-54, I-56, blank-name gap). Directives for phone, texting and voice. A plain warning not to rely on JEFFEREY for medication reminders.
26. **Both:** build and run the backup verifier (gap, now) and recover the iCloud dedup pipeline into a repo.
27. **JEFFEREY:** require Touch ID for owner-only actions and HMAC grants (I-43).
28. **Testers:** run the untested areas in section 8, starting with crisis and emergency handling.

### Before a stranger pays

29. **Owner:** fix public claims (I-46, the marketing gap). Decide pricing. Write a customer EULA with warranty limits, a privacy notice in English and French, and a support process. Arrange insurance.
30. **JEFFEREY:** a signed installer, a "Connect ChatGPT" launcher, hardened HTTP tokens (I-59), and a clear "Mac only" or a Windows path.
31. **JEFFEREY:** a consent and capacity record and a representative/POA role, for families setting it up for someone with dementia.
32. **JEFFEREY:** French UI and Canadian forms. An uninstall-and-erase path for resale. Third-party notices. New-Mac guidance.
33. **JEFFEREY:** the remaining medium and low issues: I-63, I-65 to I-69, and the 127 unchecked medium findings, after a skeptic confirms them.
34. **Self-Cloud laptop agent:** confirm the connector behaviour JEFFEREY cannot see: re-keying after an erase, erasure across catalog and audit, and one shared drive id.

## 8. Not yet tested

A critic read all 1,521 titles and found five real-world areas with little or no coverage. Nothing was run for these.

1. **Health emergencies, mental-health crisis and break-glass access.** The code, directives and docs have nothing on crisis, 911 or 988, falls or wandering. Nobody tested what happens when the veteran says something dark mid-album, when a person with dementia says "help, I fell" at the wall, or when a paramedic needs the medication list while you are unconscious. "Deny by default" has no emergency override.
2. **Disaster recovery and long-term preservation.** Nobody tested losing the drive itself to death, theft or fire and restoring onto a new one: same id, keys, declines and voice consent. Nobody tested a forgotten APFS passphrase or the recovery key. disc_archive verify after bit rot was not tested either.
3. **The daily routine.** add_goal is never called in any scenario. Nobody checked that the daily brief is correct, timely and readable. Reminders don't exist. Nobody checked what happens on the anniversary of a death.
4. **Dealing with institutions and professionals.** Legitimate, end-to-end dealings with CRA, VAC, CPP/OAS, a doctor, a lawyer or an accountant were not tested. That includes a narrow, time-limited key for one professional.
5. **Abuse by the trusted insider.** Nobody tested coercive control, elder financial abuse by a caregiving family member, or the egress log used as a surveillance diary of the victim.

## 9. What this test could not prove

- **No real Mac.** Everything ran on Linux. macOS-only behaviour was simulated or traced in code: APFS encryption checks, rename collisions, F_FULLFSYNC and power cuts, Keychain, Finder drag-and-drop and launchers. Treat those findings as likely, not observed.
- **No real Claude, ChatGPT or Ollama model.** We made the exact calls an engine makes, and we used a fake local-model server. That proves what JEFFEREY does when asked. It does not prove what a real model would actually ask, refuse or obey, for example whether Claude would follow an injected instruction or call get_directives. Ollama's context truncation was not run.
- **No pretrained CLIP weights.** Photo search quality could not be judged. Only the pipeline with untrained weights ran.
- **Self-Cloud code is private and unseen.** Only its docs were read. Every Self-Cloud behaviour is unverifiable here. That is part of why the seam area has no passing scenario.
- **No real users.** No elderly person, family member or stranger touched it. The accessibility and onboarding findings come from testers imagining those people, not from watching them.
- **Only part of the findings were checked.** 96 scenarios could not be executed here (they need a real Mac, a real person, or a missing feature). To stay inside the owner's usage limit, 127 medium findings were never checked by a skeptic. One finding (voice#5) was refuted, and two issues (I-43, I-66) are contested.