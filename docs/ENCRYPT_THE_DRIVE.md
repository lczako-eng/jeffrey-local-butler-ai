# Encrypt your Self-Cloud drive

Your drive holds your life: your memories, your photographs, your voice. Until it
is encrypted, anyone who picks it up — in a car, at a border, after a break-in —
can read all of it on any computer. Encrypting it takes an afternoon, needs no
programming (a few steps ask you to paste one line into Terminal), and is the
single most useful thing you can do for it.

JEFFEREY checks this for you. When `Make this drive a Self-Cloud.command` sets a
drive up, it says whether the drive is encrypted, or that it **could not verify** it
(run again on a drive that is already yours, it says nothing about encryption). Any
time, with the drive plugged in and in use on a Mac, `cd ~/JEFFEREY && python3
tools/install.py --check` says the same. If either says it is not encrypted, or could not verify it, come here.

> **Mac only, for now.** JEFFEREY runs on a Mac today. On Windows (BitLocker To
> Go) or Linux (LUKS) a drive can be encrypted, but JEFFEREY cannot check it
> there: the drive launcher will say "could not verify" when it sets the drive
> up, and `install.py --check` says nothing about encryption.

---

## 0. Before you touch anything: a second copy

**Do not start until everything on the drive also exists somewhere else.** That
means on the Mac, in iCloud, or on another drive, and you have **opened a few of
the photographs there** ("I moved them" is not a check). Encryption that goes
wrong on a drive that holds the only copy is exactly the loss this product
exists to prevent. Do not cancel iCloud until step 5 passes.

**Everything includes the hidden `.selfcloud` folder.** That is where JEFFEREY
keeps your memories, your voice and the record of what left the house. Finder
hides it: in the drive's window press **Cmd-Shift-.** (the full stop) to show it,
and copy it with the rest. Ask someone you trust if you are unsure.

## 1. Find out what kind of drive it is

Open **Terminal** and type (your drive's name may differ):

```sh
diskutil info /Volumes/Self-Cloud | grep -i "personality\|encrypted\|filevault"
```

If your drive's name has spaces, put the whole path in quotes, here and in every
command below: `diskutil info "/Volumes/My Passport"`.

| What it says | What you do |
|---|---|
| **APFS**, and `FileVault: Yes` | Already encrypted. Go to step 5 to check it properly. |
| **APFS**, no `FileVault: Yes` | Step 2a: encrypt in place, keeps every file. |
| **Mac OS Extended / HFS+** | Step 2a also works. If the drive is nearly empty, step 2c is better. |
| **exFAT** or **FAT32** | Step 2c: these cannot be encrypted in place, so the drive must be erased. The second copy is mandatory. |

If no `Encrypted:` or `FileVault:` line comes back at all, the drive is **not
encrypted**. Absence is the answer.

## 2a. Encrypt in place (APFS or HFS+)

In Finder, right-click the drive → **Encrypt "Self-Cloud"…**, choose a
passphrase and a hint (read step 3 first), and let it run. The drive stays
usable while it converts. Leave it plugged in until it finishes; a large drive
takes hours.

**No "Encrypt…" in the menu?** The drive is almost always a **Time Machine
backup disk**: look for a `Backups.backupdb` folder, or a *Back Up Now* item in
the same menu. macOS hides Finder encryption on a Time Machine disk. Either
encrypt it through Time Machine's own settings, or — better — give Time Machine
its own drive. Then use step 2c. One drive, one job: a drive that is both your
backup and your Self-Cloud is a single point of loss for both.

The Terminal equivalents are **not** the same for both formats:

```sh
# APFS:
diskutil apfs encryptVolume /Volumes/Self-Cloud -user disk
# HFS+ (asks for the passphrase):
diskutil coreStorage convert /Volumes/Self-Cloud -stdinpassphrase
```

Watch it finish rather than assume it did:

```sh
diskutil info /Volumes/Self-Cloud | grep -i "filevault\|encrypt\|conversion"
```

## 2c. Erase to APFS (Encrypted)

Use this for exFAT or FAT32, for a Time Machine disk you are releasing, or
whenever the drive is nearly empty and erasing is quicker than converting. It is
the best end state for the drive.

**Only when all three are true:** the second copy from step 0 exists and you have
opened files from it; nothing else on the drive is wanted (`ls -la
/Volumes/Self-Cloud` — read every line); and, if it was a Time Machine disk, it
has been released (System Settings → General → Time Machine → select the drive
→ **−**; then `tmutil destinationinfo` must no longer list it).

1. Open **Disk Utility**, then **View → Show All Devices**.
2. Select the **physical disk** (the top row, named after the maker) — not the
   volume indented under it.
3. **Erase**: Name `Self-Cloud`, Format **APFS (Encrypted)**, Scheme **GUID
   Partition Map**. Set the passphrase (step 3 first). Erase.
4. Double-click **`Make this drive a Self-Cloud.command`** again. The erase
   removed the drive's Self-Cloud folders and marker; this puts them back. **The
   drive gets a new id**, and the launcher pairs it with this Mac again.
5. **Before you open Claude or any JEFFEREY window, put your memories back.** In
   the drive's window press Cmd-Shift-. (the full stop) to show hidden folders,
   open `.selfcloud`, and drag in the `jefferey` folder from the second copy's
   `.selfcloud` folder. Finder says a `jefferey` folder is already there: choose
   **Replace** (not Keep Both). Then tell this Mac again that the re-made drive is
   yours, because the folder you copied carries the old drive's pairing: in
   Terminal, `cd ~/JEFFEREY && python3 connector/home.py pair /Volumes/Self-Cloud`,
   and type the number it shows. Without both steps, JEFFEREY starts with no
   memories, or stays off saying the drive is a copy. Ask someone you trust if you
   are unsure.
6. Copy your photographs back, and open a few from the drive before deleting
   anything anywhere else.

## 3. The passphrase — where people really lose everything

- Keep it in a password manager (Apple Passwords, 1Password, Bitwarden),
- **and on paper**, in a safe or a fireproof box.
- **Never only in the Mac's keychain.** An encrypted drive whose only key lived
  on a laptop that died is not a backup; it is a brick.
- If someone should be able to open it after you (a spouse, an executor), the
  paper copy is how. Decide that on purpose.

## 4. Encrypt the Mac too

The Mac holds copies of the same photographs and leaves the house more often
than the drive. **System Settings → Privacy & Security → FileVault**: turn it
on, and keep its recovery key the same way as the passphrase.

## 5. Check it, then you are done

1. Eject the drive, unplug it, plug it back in. The Mac must **ask for the
   passphrase**. If it opens silently, the key is saved in the keychain: that
   protects against losing the drive, not against losing the bag with the
   laptop in it. Untick "Remember this password in my keychain" if you want
   both.
2. `diskutil info /Volumes/Self-Cloud` says `FileVault: Yes`. On current macOS
   an APFS drive may print no `Encrypted:` line at all; that is normal.
3. In Terminal, `cd ~/JEFFEREY && python3 tools/install.py --check` says the
   drive is encrypted.
4. Open a handful of photographs from the drive and compare them with the
   second copy.

## What this does and does not protect

- **Does:** a lost or stolen drive is unreadable. A drive sold or recycled
  later carries nothing.
- **Does not:** protect anything while the drive is plugged in and unlocked on a
  running Mac. That is the job of JEFFEREY's access keys and its door (`What
  left the house.command`), and of keeping the Mac itself locked.
- **Does not** replace a second copy. Encryption protects against theft, not
  against a drive that dies. Keep a second encrypted copy somewhere else.
