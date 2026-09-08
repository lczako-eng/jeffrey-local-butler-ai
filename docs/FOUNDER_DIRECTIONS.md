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

## 2. Things already decided in this session, so they aren't relitigated

- **JEFFEREY**, never "Jeff". No "butler" anywhere.
- Jefferey is a **wrapper** over rented engines, not a model of our own.
- **Self-Cloud is its own product**; Jefferey is a caretaker with a key.
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
