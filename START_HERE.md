# Start here — the owner's steps, in order

**For:** Laszlo, on the Mac, with the drive. Nothing here needs a terminal
except one copy-paste in step 0. Everything else is a double-click.
**Updated:** 2026-10-14.

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
From then on, to update, double-click **`Update JEFFEREY.command`** with the
Mac online: it brings this copy and the drive's copy to the same version,
checks it works, and tells you the version.

If a `.command` file refuses to open ("cannot be opened because it is from
an unidentified developer"): right-click it → **Open**, once. Or:
System Settings → Privacy & Security → **Open Anyway**.

---

## 1. Prepare the hard drive

Plug the drive in. Double-click **`Make this drive a Self-Cloud.command`**.
Type its number (or drag it in) and press return, and type **yes** to the
rename (anything else keeps the name). It also tells this Mac the drive is
yours: JEFFEREY then uses that drive and no other, and with it unplugged he
is off — he never starts a second life on the Mac. If he already kept
memories on this Mac, it offers to move them onto the drive (type yes).
Until they are moved, JEFFEREY stays off rather than start an empty life on
the drive; `Install JEFFEREY.command` asks the same question.

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

Double-click **`Install JEFFEREY.command`** in `~/JEFFEREY` (not the copy on
the drive — it refuses that one, because Claude would stop the moment the
drive is unplugged). It:

1. makes JEFFEREY a private Python space (`~/.jefferey/venv`);
2. runs the whole self-test — **if anything fails it refuses to connect**;
3. backs up and edits Claude Desktop's config so Claude can see JEFFEREY's
   tools, holding the **`jefferey` caretaker key** — your life layer, the
   album, money and rules — because this is *your* Claude on *your* Mac. It
   still cannot widen any key, its own included, or let any AI spend: only you
   can, by typing it yourself (see *What JEFFEREY may do for you*, below).
   Any other connections in Claude's config are left alone and listed —
   except that one which can read your home folder or the drive is named in
   a loud warning, with an offer to disconnect it (type yes; the backup
   keeps it). Reinstalling keeps the key Claude held before. If a Self-Cloud
   drive is plugged in that this Mac does not know, it asks if it is yours;
   with none, it asks whether you have one.
   (An earlier version of this page said `claude-raw`. It was wrong; the
   installer has always given your own Desktop the caretaker key. Install a
   narrower one with `python3 tools/install.py --client claude-raw`.)

**Quit Claude Desktop completely** (menu bar → Claude → Quit) and open it
again. In a new chat say *"Load your directives and tell me what you know
about me."* macOS will ask whether **Python** may access files on a
removable volume — Python, not Claude, because JEFFEREY runs as a small
Python program on your Mac. **Allow.** It reaches only the drive, and nothing
leaves the Mac by it; without it he cannot reach his own memory. If you
clicked Don't Allow: System Settings → Privacy & Security → Files and
Folders → Python → turn on Removable Volumes, then quit and reopen Claude.
With the drive plugged in, everything he learns lands on the drive.

**A note on other connections.** If Claude Desktop already has a
`filesystem` connection, whatever folders it names are readable by Claude
*directly* — not through JEFFEREY's gate, and not through the egress door, so
nothing it reads appears in *What left the house*. That is fine for folders
you meant to share. It should never name the Self-Cloud drive or your home
folder; the installer warns you if it does.

---

## 4. Your photographs

Copy them into `library/` on the drive (or leave them where they are and point
at that folder when asked). Double-click **`Show me my life.command`** — or
`Start Self-Cloud.command` on the drive. The first run installs the seeing
parts (once, ~2 GB), then reads the photographs: dates, places, and what they
look like. The first pass stops at 3,000 so you see it working in minutes; run
it again for the rest. It always picks up where it left off.

The wall opens in the browser on this Mac: big pictures, one box to type into.
*"the vacation ten years ago in Cuba"* works, offline. (A microphone button
appears only where the browser understands speech on the device itself.) To
see it on the phone or the TV, answer yes when it asks, then open the printed
link once on each screen. **Hide** clears the screen; it also hides itself
after ten minutes untouched.

Keeping things off it, from your own terminal (`~/.jefferey/venv/bin/python`
in front of each):

| Type | It means |
|---|---|
| `tools/photo_index.py forget <photo or folder>` | that photo never shows again |
| `connector/reminisce.py keep-off-wall Kandahar` | never on the wall (two words, like `Halifax 2023`, mean photos that are both; it tells you how many it hides) |
| `connector/reminisce.py never-ask Afghanistan` | the album never asks about it |
| `connector/reminisce.py list`, then `reopen <id>` | undo a "rather not" — only you can |

---

## 5. Your voice

Double-click **`Record my voice.command`**. About twenty minutes of reading
sentences aloud, in your own room. It asks for your name: type it, it is
never guessed. Each sitting starts with you reading one sentence saying you
agree, ending in three words that change every time; type yes to keep it.
When you carry on another day it asks "Are you …?" Type yes. Recordings go on
the drive, read-only, checksummed. To delete, run `tools/voice_enrol.py --who
"Your Name" delete` and type your name: it removes the copies on the drive and
on this Mac, and tells you plainly what overwriting cannot reach (flash
storage, Time Machine). If it lists recordings under another name marked
"this may be yours too" (older versions used the Mac's account name), delete
those the same way, with that name. Nothing is cloned or played back as you yet — that is a separate
decision, made later, with the local model, and never on a phone or a door
intercom.

---

## 6. See what left the house

After your first conversation, double-click **`What left the house.command`**.

Every byte JEFFEREY has ever handed to a rented engine passed through one
door and was written down first — to whom, when, which tool, and word for
word. This button reads it back to you in plain words. From the same window
you can **shut the door** (nothing leaves until you open it) and open it again,
and — if you would rather it did not keep every word forever — choose `k` to
keep each send word for word only for so many days (after that, only its date,
where it went and a fingerprint stay).

The door also refuses. If Claude ever tells you *"the door kept that in the
house"*, something looked like a secret — a card number, your SIN, a
password, a PIN or a door code, in English or French — or the door is shut. That is the system working. **Never read a
secret to an AI.** Secrets go in the vault, from your own terminal:

```sh
~/.jefferey/venv/bin/python ~/JEFFEREY/connector/vault.py set sin
```

and JEFFEREY uses them by *name* (`vault:sin`) on forms, never by value.

If something like that is already in your memories (an alarm code, a PIN, a
card number), no AI sees it — it reaches them as `[hidden]`. To move it into
your vault, type `/secrets` in **`Talk to JEFFEREY on this Mac`**.

### Forms

A form JEFFEREY fills is saved as a new copy in the **`Filled forms`** folder —
at the top of your Self-Cloud drive, or in your home folder if no drive is
plugged in — and nowhere else. Your original is never changed. A secret from
your vault goes only into the box that asks for it, and *What left the house*
lists every time one was used. Boxes that sign or say "I certify" are left for
you, unless you type `/permit paperwork act` yourself.

### Charges

JEFFEREY watches your card statements against your list of agreed payments.
When an AI asks to add something to that list, it waits for you: double-click
**`Check my charges.command`** (or type `/charges` in *Talk to JEFFEREY on
this Mac*) and type yes or no for each one.

### Forgetting, and bringing back

Ask any AI to forget something and JEFFEREY first shows it exactly what would
go; nothing goes until you say yes. A small thing (up to three, of one kind)
goes on your word in the chat. Anything bigger — or forgetting a person, with
their moments — needs your own hands: the AI tells you a short code;
double-click **`Forget or bring back.command`** and type `ok` and the number
(or the code); it shows you the list once more, and you type yes. The same
window lists everything removed in the last three
months — `back` and the number puts it back — and can **erase** words
everywhere, for good: from your memories, the copies, and the record of what
was sent. Erasing cannot be undone. What an AI company already received, it
may still hold; the receipt says where it went.

---

## 7. Talk to him with an AI that lives on your Mac

JEFFEREY is not Claude's. Claude is one engine he can ride; ChatGPT is another;
and he can ride an AI that runs **on your own Mac**, where nothing he reads
about you leaves the house.

Double-click **`Talk to JEFFEREY on this Mac.command`**. The first time it
asks you to install **Ollama** (the free program that runs AI on a Mac — it
opens the download page for you), then downloads **Hermes** once, about 5 GB.
After that it works with the internet off.

Same memory as in the Claude app: same conscience, same drive, same rules.
Tell him something here and Claude knows it tomorrow, and the other way round.
*What left the house* still logs every word — and marks these as having stayed
home.

A different local model: `JEFFEREY_LOCAL_MODEL=qwen3` before the command, or
any model name Ollama has.

### What JEFFEREY may do for you

No AI can raise this — not Claude, not ChatGPT, not the one on your Mac. You
type it yourself in this window, JEFFEREY reads it back in plain words, and
nothing changes until you answer. To give more (raise a permission, give or
widen a key, confirm or share), he shows three numbers — type them and press
return. Nothing pasted counts, so a message someone sends you can never say
yes for you:

| Type | It means |
|---|---|
| `/permissions` | what he may do now, kind by kind |
| `/permit groceries act 100 per week` | he may buy groceries, at most $100 in any 7 days |
| `/permit selling act at least 450` | he may accept an offer of $450 or more |
| `/permit correspondence act` | he may send letters for you — nothing that costs money |
| `/permit paperwork act` | he may fill the boxes on a form that sign or certify for you |
| `/permit groceries recommend` | back to bringing you options; you decide |
| `/charges` | payments an AI asked to add to your agreed list: yes or no |
| `/keys`, `/grant family`, `/scope remove family media.read`, `/revoke gpt-raw` | who holds a key, and changing it |
| `/approve CODE` | yes to a change an AI asked for that waits for you — a big removal, or a change to your name or date of birth on forms |
| `/scope add jefferey paperwork.write` | give your own JEFFEREY back the filling of forms, if you had taken it away |

Moving money, gift cards, crypto, phone calls in your voice and the doors are
never allowed, whatever you type. Anything that repeats (a subscription) he
always brings to you.

### Who may see what

Whatever an AI writes down is kept private, and marked "not yet confirmed"
unless it is word for word what you typed here. Your health, money,
children, the safety of your home and other people's secrets are never sent
to a plain Claude or ChatGPT. Only you let more people see something:

| Type | It means |
|---|---|
| `/pending` | what an AI wrote down, or asked to share, that waits for your OK |
| `/confirm f-1a2b3c` (or `/confirm all`) | yes, that is right |
| `/share m-1a2b3c family` | your family's key may read this moment (`private` takes it back) |
| `/legacy`, `/legacy open executor`, `/legacy seal` | what you meant for after: sealed until you open it, to the keys you name |
| `/grant mira family.read` | give one family member her own key, so your rules about Mira apply to her |

---

## Every button

| Double-click | What happens | Leaves the Mac? |
|---|---|---|
| `Make this drive a Self-Cloud.command` | folders, marker, cloud icon, Start button on the drive | no |
| `Install JEFFEREY.command` | private Python, self-test, wires Claude Desktop | one `pip install` |
| `Update JEFFEREY.command` | every copy to the same newest version, reinstall, self-test | one download |
| `Show me my life.command` | index the photographs, open the wall | one-time model download |
| `Record my voice.command` | enrol your voice onto the drive | no |
| `What left the house.command` | the egress log, in plain words; type `shut` (or `fermer`) / `open` | no |
| `Restore my memories.command` | see the copies of your memories JEFFEREY keeps, and put one back | no |
| `Forget or bring back.command` | OK a big forget an AI asked for, put back something removed, or erase words for good | no |
| `Check my charges.command` | yes or no to payments an AI asked to add to your agreed list | no |
| `Talk to JEFFEREY on this Mac.command` | JEFFEREY riding Hermes on your own Mac, same conscience | one-time download; then no |
| on the drive: `Self-Cloud/Start Self-Cloud.command` | the same as *Show me my life*, bound to that drive, on any Mac | no |

## Where things live

With the drive in: `<drive>/.selfcloud/jefferey/` — `conscience.json` (+
history, and `conscience.access.jsonl`: who asked for what), `photo-index/`,
`voice/`, `egress.jsonl`, `door-shut` (exists only while the door is shut).
Only if you chose to keep them on this Mac (or already did before October
2026): `~/.jefferey/` and `~/.selfcloud/`. Once your drive is paired,
unplugged means off: every tool says "your Self-Cloud drive is not plugged
in", and nothing is kept anywhere else.

## If something goes wrong

- *"This Mac needs a newer Python"* → https://www.python.org/downloads/, the
  big yellow button, then double-click again.
- The self-test fails → nothing was connected. Run
  `~/.jefferey/venv/bin/python ~/JEFFEREY/connector/jefferey_chat.py --selftest`
  in Terminal and send the last twenty lines to whoever is helping you.
- Something was forgotten by mistake → double-click **`Forget or bring
  back.command`**, type `back` and its number.
- JEFFEREY says your memories *cannot be read*, or that they were *put back
  to an earlier copy* → double-click **`Restore my memories.command`**. It
  lists the copies he keeps (every one from the last day, one an hour for a
  week, one a day for three months, and one from just before anything was
  deleted) and puts back the one you pick. What is there now is kept too, so
  it can be undone. You can edit the memory file by hand; if a typo makes it
  unreadable, he tells you which line instead of quietly using an old copy.
- JEFFEREY says your **drive is not plugged in** → plug it in, type its
  password if the Mac asks, and ask again. No restart needed.
- He says a drive **is not yours** or **not paired** → if it is yours,
  double-click `Install JEFFEREY.command` and type yes when it asks.
- Two Self-Cloud drives plugged in at once → every tool refuses to guess and
  says so. Unplug one.
- He says your memories were saved by a **newer JEFFEREY** → double-click
  `Update JEFFEREY.command`.
- The icon didn't change → eject, re-plug.
- You want everything to stop → unplug the drive. That is the whole security
  model, and it is not a metaphor.
