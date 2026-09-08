# Self-Cloud — the architecture, recorded

**Status:** design of record. Not yet built. Written down now so the software
being built today lands correctly on the hardware built later.

Self-Cloud is a **separate product** from Jefferey, tied into him. Jefferey is
the representative; Self-Cloud is the ground he stands on — storage and
compute the person physically owns, with a switch.

## The shape of it

A **hard drive that is also a connector**. Plugged in at home, it becomes its
own small network:

- **On the network** — reachable by the person's devices and, through the
  connector, by whatever AI engine they are renting that day.
- **Off the network** — physically switched off. Not firewalled, not
  "private mode": *absent*. The strongest security posture is non-existence.
- **Theirs.** Not a subscription that ends, not an account that can be
  suspended, not a jurisdiction that can change its mind.

## What lives on it

1. **The conscience** (`conscience.json`) — priorities, corrections, facts,
   goals, permissions, the action log. Today this sits in `~/.jefferey/`;
   on Self-Cloud it comes home to owned hardware and the path simply
   changes (`JEFFEREY_CONSCIENCE_PATH`). Nothing else about Jefferey has to
   change. That portability is deliberate and must be preserved.
2. **The life layer** — the people, the moments, the story (`life.py`).
3. **The media** — photographs, recordings, documents, a life's worth. These
   are referenced by path and **never copied or uploaded** (`add_media`).
   When the drive is off, Jefferey reports them unreachable rather than
   holding a shadow copy. That is the correct behaviour; keep it.

## What must never live on it

Secrets stay in the platform keychain (`vault.py`), not in a file on a drive
that can be stolen. The drive holds who you are; the keychain holds the keys.

## The staged path (matches the build order)

| Phase | Where the conscience lives | What it costs |
|---|---|---|
| **Now** — connector | The user's own computer (`~/.jefferey/`) | Free. They already pay for the engine. |
| **v0 phone** | The user's own phone storage | Free. Self-Cloud in the pocket. |
| **Pro** | Hosted sync so every engine reaches it instantly | Paid — this is the business model arriving on schedule. |
| **Self-Cloud** | The drive at home, with the switch | Hardware purchase. The endgame. |
| **Later** | On-device models — nothing leaves at all | The architecture is already shaped for it. |

Each step is the same file finding a better home. Nothing is rewritten.

**Revision (2026-09-08):** the founder's preferred destination is the **box as
hub** — drive + small computer, always on at home, running the connector and
talking to the rented engines, with the phone and other devices as *windows*
onto it rather than the place the life lives. The phone-storage stage is a
bridge for people without the box, not the goal. See `FOUNDER_DIRECTIONS.md`
§3. Everything the person already generates — wearables, Apple Health,
transactions, calendar — feeds Self-Cloud through exports and APIs, and the
conscience takes what the owner includes.

## Hardware v1 — the box, concretely (recorded 2026-09-08)

A bare drive cannot run software, so the unit is **a drive plus a small
computer in one enclosure**. Not a workaround — every personal-cloud device
ever sold is this. The computer is tiny, cheap, silent, and invisible.

| Stage | What | Notes |
|---|---|---|
| **v0 — now** | The founder's laptop with the drive attached, running the Self-Cloud software | Already exists. Not always-on; not a product. |
| **v1 — the box** | Raspberry Pi 5 (or equivalent mini-PC board) + the drive, one case, power + Ethernet/Wi-Fi | ~$80–120 compute, ~$150–200 all-in above the drive. Runs Linux 24/7, nightlight-level power, no fan. Runs the storage stack, the connector, and talks to the rented engines. **Build toward this.** |
| **v2 — the product** | Own board + designed enclosure with the physical switch on the front | Same software. When users justify manufacturing. |

**Reaching it from outside the house:** the box sits behind the home router.
First answer: a **private encrypted tunnel** between the owner's devices and
the box (Tailscale-class: zero router configuration, end-to-end encrypted,
free for personal use, none of the owner's data touches any server of ours).
Later: the Pro sync. The tunnel keeps the promise; start there.

**The switch stays physical.** Pull the plug — or flip a switch on the box —
and it is gone from every network. No software "off mode" can promise that.

## The digital conscience, in the founder's terms

> *"I want to build that digital conscience about you so it has to understand
> you — so you can add snippets about your life into it, amongst your personal
> pictures, in the Self-Cloud. Give it permission to see who you are: your
> family, what you like. So it understands you, and can tell your story down
> the road."*

That is `life.py`, and it is built. Three rules hold it honest:

- **Snippets, not surveillance.** Only what the person deliberately adds.
  Jefferey never assembles a life behind someone's back.
- **Permission is per-item, not per-system.** Every entry is `private`
  (Jefferey alone), `family` (may be shared with the named people), or
  `legacy` (meant to outlive them and be told to those they choose).
- **Erasable, always** (`forget_life`), and never argued with.

`story_gaps()` is the quiet engine of it: Jefferey notices what's missing —
a person mentioned but never described, nothing yet marked legacy — and asks
for **one thing at a time, at the right moment**. A life gets written down
over years of small moments, which is exactly the window most people miss.

This is also the on-ramp to build priority 07, **Digital Inheritance**: by the
time it matters, the story is already there, in hardware the family holds.
