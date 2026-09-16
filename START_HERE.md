# Start here — the owner's steps, in order

**For:** Laszlo, on the Mac, with the drive. Nothing here needs a terminal
except one copy-paste in step 0. Everything else is a double-click.
**Updated:** 2026-09-16.

Two products, two repos. **Self-Cloud** is the drive and the box — storage,
the catalog, the kill switch — built by the laptop agent in `lczako-eng/Self-Cloud`.
**JEFFEREY** is this repo: the shadow that rides a rented engine and gives it
a conscience you own. These steps prepare the drive and put JEFFEREY on it.

---

## 0. Get the code onto the Mac (once, with a network)

Open Terminal (⌘-space, type `Terminal`), paste this, press return:

```sh
git clone https://github.com/lczako-eng/jeffrey-local-butler-ai ~/JEFFEREY
cd ~/JEFFEREY && git checkout claude/substantiation-discussion-8dmu3c
open ~/JEFFEREY
```

A Finder window opens with the buttons. If the Mac asks to install
"command line developer tools", say yes and run the three lines again after.

If a `.command` file refuses to open ("cannot be opened because it is from
an unidentified developer"): right-click it → **Open**, once. Or:
System Settings → Privacy & Security → **Open Anyway**.

---

## 1. Prepare the hard drive

Plug the drive in. Double-click **`Make this drive a Self-Cloud.command`**.
Drag the drive from Finder into the window, press return, say **Y** to the
rename.

What it does — and it **creates only**; it never moves, renames or deletes a
file already on the drive:

| It makes | Which is |
|---|---|
| `Self-Cloud/` | the folder you see: `Start Self-Cloud.command`, a README |
| `originals/` | your originals. Read-only, checksummed, never re-encoded |
| `library/` | the working copy the tools read and show |
| `.selfcloud/` | hidden. The machine side, shared with the Self-Cloud connector: its catalog at the top, JEFFEREY under `.selfcloud/jefferey/` — conscience, photo index, voice, **the egress log** |
| `.selfcloud/selfcloud.json` | the marker that makes every JEFFEREY tool find this drive on any Mac |
| the cloud icon | the Self-Cloud logo as the drive's Finder icon (eject and re-plug if it doesn't show) |

**Then encrypt it.** The drive holds the family's photographs in plain text
until you do. The runbook is `Self-Cloud/docs/ENCRYPT_THE_DRIVE.md` in the
other repo; the short version, if the drive is already APFS: Finder →
right-click the drive → **Encrypt "Self-Cloud"…**, choose a passphrase, write
the passphrase on paper and put the paper somewhere that is not the drive.
**Do not begin until a second copy of the photographs exists** (iCloud and the
Mac both count). Do not cancel iCloud until two copies exist and a restore has
been tested.

---

## 2. Put the software on the drive (once, with a network)

So the drive works on *any* Mac, the code lives on it too. In Terminal:

```sh
git clone https://github.com/lczako-eng/jeffrey-local-butler-ai "/Volumes/Self-Cloud/Self-Cloud/app"
cd "/Volumes/Self-Cloud/Self-Cloud/app" && git checkout claude/substantiation-discussion-8dmu3c
```

From now on, on any Mac: plug in the drive, open `Self-Cloud/`, double-click
**`Start Self-Cloud.command`**. The Mac lends a screen and a Python; it keeps
nothing.

---

## 3. Install JEFFEREY on this Mac

Double-click **`Install JEFFEREY.command`** (in `~/JEFFEREY`, or in
`Self-Cloud/app` on the drive — same thing). It:

1. makes JEFFEREY a private Python space (`~/.jefferey/venv`);
2. runs the whole self-test — **if anything fails it refuses to connect**;
3. backs up and edits Claude Desktop's config so Claude can see JEFFEREY's
   tools, with the narrow `claude-raw` key.

Restart Claude Desktop. Say *"call get_directives and be JEFFEREY."* With the
drive plugged in, everything he learns lands on the drive.

---

## 4. Your photographs

Copy them into `library/` on the drive (or leave them where they are and point
at that folder when asked). Double-click **`Show me my life.command`** — or
`Start Self-Cloud.command` on the drive. The first run installs the seeing
parts (once, ~2 GB), then reads the photographs: dates, places, and what they
look like. The first pass stops at 3,000 so you see it working in minutes; run
it again for the rest. It always picks up where it left off.

The wall opens in the browser: big pictures, one box to type or speak into.
*"the vacation ten years ago in Cuba"* works, offline.

---

## 5. Your voice

Double-click **`Record my voice.command`**. About twenty minutes of reading
sentences aloud, in your own room. The first thing it records is you saying
you agree. Recordings go on the drive, read-only, checksummed; deleting them
is real deletion. Nothing is cloned or played back as you yet — that is a
separate decision, made later, with the local model, and never on a phone or
a door intercom.

---

## 6. See what left the house

After your first conversation, double-click **`What left the house.command`**.

Every byte JEFFEREY has ever handed to a rented engine passed through one
door and was written down first — to whom, when, which tool, and word for
word. This button reads it back to you in plain words. From the same window
you can **shut the door** (nothing leaves until you open it) and open it again.

The door also refuses. If Claude ever tells you *"the door kept that in the
house"*, something looked like a secret — a card number, your SIN, a
password — or the door is shut. That is the system working. **Never read a
secret to an AI.** Secrets go in the vault, from your own terminal:

```sh
~/.jefferey/venv/bin/python ~/JEFFEREY/connector/vault.py set sin
```

and JEFFEREY uses them by *name* (`vault:sin`) on forms, never by value.

---

## Every button

| Double-click | What happens | Leaves the Mac? |
|---|---|---|
| `Make this drive a Self-Cloud.command` | folders, marker, cloud icon, Start button on the drive | no |
| `Install JEFFEREY.command` | private Python, self-test, wires Claude Desktop | one `pip install` |
| `Show me my life.command` | index the photographs, open the wall | one-time model download |
| `Record my voice.command` | enrol your voice onto the drive | no |
| `What left the house.command` | the egress log, in plain words; shut / open the door | no |
| on the drive: `Self-Cloud/Start Self-Cloud.command` | the same as *Show me my life*, bound to that drive, on any Mac | no |

## Where things live

With the drive in: `<drive>/.selfcloud/jefferey/` — `conscience.json` (+
history), `photo-index/`, `voice/`, `egress.jsonl`, `door-shut` (exists only
while the door is shut). Without the drive: `~/.jefferey/` and `~/.selfcloud/`.
The drive always wins when it is plugged in; unplugged means gone.

## If something goes wrong

- *"This Mac needs a newer Python"* → https://www.python.org/downloads/, the
  big yellow button, then double-click again.
- The self-test fails → nothing was connected. Run
  `~/.jefferey/venv/bin/python ~/JEFFEREY/connector/jefferey_chat.py --selftest`
  in Terminal and send the last twenty lines to whoever is helping you.
- Two Self-Cloud drives plugged in at once → every tool refuses to guess and
  says so. Unplug one.
- The icon didn't change → eject, re-plug.
- You want everything to stop → unplug the drive. That is the whole security
  model, and it is not a metaphor.
