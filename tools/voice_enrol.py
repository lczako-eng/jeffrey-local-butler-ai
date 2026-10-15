#!/usr/bin/env python3
"""
voice_enrol.py — record your own voice, for your own Self-Cloud.
================================================================

This is the ENROLMENT half of "the conscience speaks in your voice": you,
present, reading phrases aloud into your own machine. It records; it does not
clone, synthesise or play anything as you. That half comes later and is a
separate decision.

The safeguards from FOUNDER_DIRECTIONS §1 are in the code, not just the docs:

  1. The recordings live ONLY in the voice folder (on the Self-Cloud drive if
     one is plugged in, otherwise ~/.selfcloud/voice/). Nothing here imports
     anything that can talk to a network. Nothing is uploaded, ever.
  2. THE PERSON MUST BE PRESENT. This refuses to run without an interactive
     terminal, and recordings only ever come from the microphone: a script,
     a cron job or a model cannot feed it audio. (A fake microphone is
     accepted only by the self-test, inside a temporary folder.)
  3. A NAME IS REQUIRED, and it must look like a name. It is never guessed
     from the computer's account.
  4. EVERY SITTING BEGINS WITH CONSENT, IN THE PERSON'S OWN VOICE: "I am ___,
     it is ___, and I am recording my own voice for my own Self-Cloud, to be
     used only as I direct. Today's words are ___." The three words are new
     every time, so an old recording (a voicemail, a video) does not have
     them. JEFFEREY cannot yet hear WHICH words were said (there is no speech
     recognition on the machine), so the manifest says the words were shown,
     never that they were checked. A silent take, or one steady sound (even
     after a pause), is refused. Consent counts only while its recording is
     there and matches its checksum.
  5. ONE FOLDER, ONE PERSON. Carrying on an existing set shows whose it is and
     when they agreed, and asks "are you that person?" (pressing return is
     not yes). A voice that sounds clearly different from the one already
     recorded must say "it is me" before anything is kept, and that is
     written down. A similar-looking name never merges into someone else's.
  6. Every take is checksummed, logged and made read-only by its owner alone
     (takes 0400, the list 0600, folders 0700). The manifest is the audit.
  7. `delete` is REAL deletion, done by the person at the keyboard typing the
     name: every place a voice may be (the drive, this computer's home
     folder) is searched, each file is overwritten to its full size before it
     is unlinked, and shortcuts (symbolic links) are removed without ever
     being followed. It says plainly what overwriting cannot reach: flash
     storage and backups may still hold old copies.

    python tools/voice_enrol.py --who "Your Name" start    # record (resumable)
    python tools/voice_enrol.py --who "Your Name" status
    python tools/voice_enrol.py status                     # everyone recorded
    python tools/voice_enrol.py --who "Your Name" play 7   # hear a take back
    python tools/voice_enrol.py --who "Your Name" delete   # gone, for real

Install on the Mac (once):   pip install sounddevice numpy

About ten minutes of clean speech is plenty for the models that exist today;
the phrase sheet is ~55 short lines and you can stop whenever you like and
carry on tomorrow. Read naturally. It's you it's learning, not an announcer.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import errno
import hashlib
import json
import os
import platform
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unicodedata
import wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "connector"))
import answers  # noqa: E402
import home  # noqa: E402

VOICE_ROOT = home.voice_path()          # on the drive, if one is plugged in
RATE = 48000          # capture high; anything downstream can resample
MIN_SECONDS = 0.6     # shorter than this is a mis-press, not a phrase

# What counts as someone speaking. Measured in 30 ms slices of the take.
FRAME_SECONDS = 0.03
SOUND_RMS = 0.005          # a slice louder than this has something in it
MIN_SOUND_SECONDS = 0.3    # any take: at least this much sound, or it was silence
MIN_CONSENT_SECONDS = 4.0  # the consent sentence cannot be read faster than this
MIN_CONSENT_SPEECH = 2.0   # ...and at least this much of it must be speech
MIN_CONSENT_BURSTS = 6     # ...in at least this many separate rises: speech comes in
                           # syllables, a held tone (even after a pause) does not
MAX_TRIES = 5              # unusable takes in a row before giving up for now
# Pitch ratio beyond which a voice "sounds different" and the speaker must
# say "it is me". A tripwire, not proof of who is speaking: two people of
# similar pitch are not told apart (verify I-54: 150 Hz against 110 Hz, 1.36,
# passed at 1.5; one person's pitch moves far less than that between days).
VOICE_DIFFERS = 1.3

NAME_MAX_CHARS = 60
NAME_MAX_WORDS = 6

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)

# The self-test (and tests/test_voice.py) may swap the microphone for a fake,
# and confirm a deletion without typing, but only inside a temporary folder.
_SELFTEST = False
_ROOTS: list[Path] | None = None        # override of all_roots(), tests only

# ---------------------------------------------------------------- phrases
#
# Short, natural, and phonetically varied — numbers, names, questions, a bit
# of feeling. The first is not on the list: it is the consent sentence, built
# from the person's own name, today's date and three fresh words.
PHRASES = [
    "Good morning. It's going to be a long day, so let's make it a good one.",
    "The kitchen table is where everything important ever got decided.",
    "Remind me to call the bank before noon on Thursday.",
    "She laughed so hard she had to sit down on the porch steps.",
    "Seven, twelve, forty-three, ninety-nine, and one thousand and one.",
    "Where did we put the photographs from the trip to Cuba?",
    "It rained the whole week, and honestly it was the best holiday we ever had.",
    "Turn the lights off in the hallway, please, and lock the back door.",
    "I never thought I'd say this, but I miss the sound of that old car.",
    "The doctor's appointment is on the fourteenth at half past two.",
    "Don't worry about it. We'll figure it out in the morning, like always.",
    "Play the song we danced to at the wedding. You know the one.",
    "My grandmother kept her recipes in a blue tin above the stove.",
    "How much did we pay for the roof? Something like eight thousand?",
    "That's the house on Westhill. We lived there for eleven years.",
    "Careful — the top step is loose. It's been loose since 2009.",
    "Yes. No. Maybe. Ask me again after I've had my coffee.",
    "The dog's name was Biscuit, and he was afraid of the vacuum cleaner.",
    "Is it Tuesday? It feels like Tuesday. It's probably Wednesday.",
    "Thank you for looking after her. I don't know what we'd have done.",
    "Winter came early that year. The lake froze in the first week of November.",
    "Read me the message from Karen, then delete the one from the bank.",
    "Three eggs, a cup of flour, a pinch of salt, and don't over-mix it.",
    "I'm proud of you. I should say that more often than I do.",
    "What was the name of the restaurant by the harbour, the one with the blue chairs?",
    "Set an alarm for six. No — six thirty. Six thirty is fine.",
    "We drove all night to get there, and the sunrise made it worth it.",
    "This is important, so listen: the spare key is under the third flowerpot.",
    "Happy birthday. You don't look a day over the last time I said that.",
    "The invoice is wrong. They've charged us twice for the same month.",
    "Put on your coat. It's colder out there than it looks from in here.",
    "I remember the smell of the garage — oil, sawdust, and my father's radio.",
    "Fourteen Elm Street, apartment two, buzzer doesn't work, just knock.",
    "Hello? Yes, this is him. No, I'm not interested, thank you. Goodbye.",
    "Sometimes the quiet ones are the ones who were paying the most attention.",
    "Show me the pictures from the summer we painted the fence green.",
    "Two coffees, one black, one with milk, and whatever pastry looks freshest.",
    "I was wrong about that, and I'm sorry. You were right the whole time.",
    "The train leaves at nine forty-five from platform four. Don't be late.",
    "Grandpa used to say: measure twice, cut once, and never rush the glue.",
    "It's been a hard week. Can we just watch something and not talk about it?",
    "October the third, nineteen eighty-seven. That's the date on the back.",
    "Tell them I said hello, and that the offer still stands.",
    "The garden did well this year — tomatoes, beans, and far too much zucchini.",
    "Wait, wait, wait. Say that again, slowly. Who called?",
    "There's a photo of us on the ferry, both squinting, both happy.",
    "Turn it up a little. No, that's too loud. There — perfect.",
    "I'd like to remember this exactly as it is right now.",
    "Nobody remembers everything. That's what the pictures are for.",
    "This is my voice, in my house, on my own machine. Nobody else's.",
]

# Five in the person's own words — these matter more than the fifty above.
OPEN = [
    "Say your full name, and where you were born.",
    "Describe the room you're sitting in right now, the way you'd describe it to a friend on the phone.",
    "Tell a short story about someone you love — a minute, no more.",
    "Say something you would want to hear in your own voice on a bad day.",
    "Say whatever you like. This one is yours.",
]

# Today's words: plain, easy to read aloud, easy to tell apart when heard.
# Three are drawn fresh for every consent, so no earlier recording has them.
CHALLENGE_WORDS = [
    "apple", "river", "candle", "garden", "yellow", "window", "pepper",
    "violin", "harbour", "blanket", "orange", "pencil", "sunset", "teapot",
    "mountain", "button", "ladder", "rabbit", "lemon", "anchor", "basket",
    "bridge", "cherry", "forest", "kettle", "meadow", "parrot", "pillow",
    "rocket", "saddle", "tiger", "tulip", "wagon", "walnut", "zebra",
    "copper", "silver", "maple", "island", "lantern",
]

RULE = ("Recordings of a living person, made by that person, present and "
        "consenting. They live only here. Nothing plays or synthesises this "
        "voice yet — that is a separate decision the owner makes later, with "
        "the safeguards in FOUNDER_DIRECTIONS §1.")

LIMITS_NOTE = (
    "  What 'gone' cannot promise: the drive and this {computer} keep data on\n"
    "  flash storage (an SSD), which can hold old copies where no program can\n"
    "  reach them, and backups such as Time Machine may still have copies made\n"
    "  while these recordings existed. Overwriting cannot reach those. To be\n"
    "  certain, delete those backups too, or erase the drive.")


class Refused(Exception):
    """Something was not done, and why, in words the person can read."""


# ---------------------------------------------------------------- helpers
def _computer() -> str:
    return "Mac" if sys.platform == "darwin" else "computer"


def _wrap(msg: str, indent: str = "  ") -> str:
    """Short lines, easy to read in a Terminal window."""
    return "\n".join(textwrap.fill(part, 72, initial_indent=indent,
                                   subsequent_indent=indent) if part else ""
                     for part in msg.split("\n"))


def _row(label: str, text: str) -> str:
    """One line of `status`: a label, then text wrapped under itself."""
    return textwrap.fill(text, 74, initial_indent=f"  {label:<10} ",
                         subsequent_indent=" " * 13)


def _tell(msg: str) -> None:
    """A refusal or a warning: always shown, even in quiet mode."""
    print(f"\n{_wrap(msg)}\n", file=sys.stderr)


def _norm(name: str) -> str:
    """For comparing two spellings of one name: same letters, any case."""
    return " ".join(unicodedata.normalize("NFC", name or "").split()).casefold()


def clean_name(who: str) -> str:
    """The person's name, tidied, or Refused with a plain reason.

    A name is required (never the computer's account name), and it must be a
    name: it goes word for word into the consent sentence the person reads.
    """
    name = " ".join(unicodedata.normalize("NFC", who or "").split())
    if not name:
        raise Refused("Please type a name: the name of the person whose voice "
                      "this is. Nothing was recorded.")
    if len(name) > NAME_MAX_CHARS or len(name.split()) > NAME_MAX_WORDS:
        raise Refused("That is longer than a name. Please type just the name of "
                      "the person who will be speaking. Nothing was recorded.")
    ok_marks = set(" -'’.")
    if not unicodedata.category(name[0]).startswith("L") or not all(
            unicodedata.category(c)[0] in "LM" or c in ok_marks for c in name):
        raise Refused("A name can only have letters, spaces, hyphens (-), "
                      "apostrophes (') and dots (.). Please type just the name. "
                      "Nothing was recorded.")
    if _reads_like_a_sentence(name):
        raise Refused("That reads like a sentence, not a name. Please type just the "
                      "name of the person who will be speaking. Nothing was recorded.")
    return name


# A dot belongs after an initial ('J. R. Smith') or a short title ('Dr.',
# 'Jr.'), never at the end of a sentence (verify I-54: 'Bob. I do not
# consent' and 'Nobody. I refuse' went into the consent sentence).
_TITLES = frozenset("dr mr mrs ms mme mlle m jr sr st ste rev fr sgt col capt lt".split())
# Words no name is made of, that turn the consent into something else:
# 'I', 'me', 'not', 'refuse', 'consent', in English and French.
_NOT_NAME = frozenset("""i me my myself not never nobody noone refuse refuses refused
    refusing consent consents consenting agree agrees disagree withdraw dont don't
    doesnt doesn't cannot can't won't without unless nor je moi pas jamais personne
    refuse refuser refusé consens accepte""".split())


def _reads_like_a_sentence(name: str) -> bool:
    for w in name.split():
        if w.strip(".").replace("’", "'").casefold() in _NOT_NAME:
            return True
        # every piece a dot ends is an initial or a title: 'J.', 'J.R.',
        # 'Dr.', 'St.-Jean' — never 'Bob.' or 'Bob.I'
        for piece in w.split(".")[:-1]:
            p = piece.strip("-'’").casefold()
            if len(p) > 1 and p not in _TITLES:
                return True
    return False


def slug(who: str) -> str:
    """The folder name for a person. Unchanged from the first version, so
    every existing enrolment is found where it was made."""
    return "".join(c if c.isalnum() else "-" for c in who.strip().lower()).strip("-")


def _slugs(who: str) -> list[str]:
    """Folder names a person's recordings may be under (old and new tidying)."""
    tidy = " ".join(unicodedata.normalize("NFC", who or "").split())
    out = []
    for s in (slug(tidy), slug(who or "")):
        if s and s not in out:
            out.append(s)
    return out


def person_dir(who: str) -> Path:
    s = slug(" ".join(unicodedata.normalize("NFC", who or "").split()))
    if not s:
        raise Refused("Who is this? Please give a name.")
    return VOICE_ROOT / s          # letters, digits and '-' only: cannot leave


def _is_link(p: Path) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(p).st_mode)
    except OSError:
        return False


def _link_target(p: Path) -> str:
    try:
        return os.readlink(p)
    except OSError:
        return "somewhere else"


def _secure_dir(p: Path, create: bool) -> None:
    """A real folder, never a shortcut, readable by its owner only (0700)."""
    if create:
        try:
            os.mkdir(p, 0o700)
        except FileExistsError:
            pass
    st = os.lstat(p)
    if stat.S_ISLNK(st.st_mode):
        raise Refused(f"The folder {p} is a shortcut to {_link_target(p)}, so "
                      "JEFFEREY will not use it. Nothing was recorded or changed. "
                      "Please ask someone you trust to look at it.")
    if not stat.S_ISDIR(st.st_mode):
        raise Refused(f"{p} should be a folder but is not. Nothing was changed.")
    fd = os.open(p, os.O_RDONLY | _DIRECTORY | _NOFOLLOW)
    try:
        os.fchmod(fd, 0o700)
    except OSError:
        pass                         # some drive formats cannot hold modes
    finally:
        os.close(fd)


def _tighten(d: Path) -> None:
    """Bring an older enrolment to owner-only modes, without following links:
    takes 0400 (read-only originals), everything else 0600, the folder 0700.
    A file with another name elsewhere (a hard link) is left alone: its mode
    is that other file's too, and it is not ours to change."""
    try:
        _secure_dir(d, create=False)
        with os.scandir(d) as it:
            names = [e.name for e in it]
    except (OSError, Refused):
        return
    for nm in names:
        p = d / nm
        try:
            fd = os.open(p, os.O_RDONLY | _NOFOLLOW | _NONBLOCK)
        except OSError:
            continue                  # a shortcut, or unreadable: leave it be
        try:
            st = os.fstat(fd)
            if stat.S_ISREG(st.st_mode) and st.st_nlink == 1:
                take = nm.startswith("take-") and nm.endswith(".wav")
                os.fchmod(fd, 0o400 if take else 0o600)
        except OSError:
            pass
        finally:
            os.close(fd)


@contextlib.contextmanager
def _lock(d: Path):
    """One window at a time per person, so two sittings never collide."""
    try:
        import fcntl
    except ImportError:               # not a Mac or Linux: carry on unlocked
        yield True
        return
    try:
        fd = os.open(d / ".lock", os.O_RDWR | os.O_CREAT | _NOFOLLOW, 0o600)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):
            raise Refused(f"Something odd is in {d} (a shortcut where JEFFEREY "
                          "keeps its lock), so nothing was recorded. Please ask "
                          "someone you trust to look at it.")
        raise
    locked = True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        locked = False
    except OSError:
        pass                          # a drive that cannot lock: carry on
    try:
        yield locked
    finally:
        os.close(fd)


def load_manifest(d: Path) -> dict:
    """The list of recordings, read without following a shortcut. {} if there
    is none yet; Refused if it is a shortcut or damaged (never overwritten)."""
    m = d / "manifest.json"
    try:
        st = os.lstat(m)
    except FileNotFoundError:
        return {}
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise Refused(f"The list of recordings in {d} is a shortcut to somewhere "
                      "else, so JEFFEREY will not trust it. Nothing was changed. "
                      "Please ask someone you trust to look at it.")
    try:
        fd = os.open(m, os.O_RDONLY | _NOFOLLOW)
        with os.fdopen(fd, "rb") as fh:
            man = json.loads(fh.read().decode("utf-8"))
        if not isinstance(man, dict) or not isinstance(man.get("takes"), list):
            raise ValueError("not a list of recordings")
    except (OSError, ValueError, UnicodeDecodeError):
        raise Refused(f"The list of recordings in {d} is damaged, so nothing was "
                      "changed. The recordings themselves are still there. Please "
                      "ask someone you trust to look at it.")
    return _migrate(man)


def _migrate(man: dict) -> dict:
    """Read the first version's shape and bring it up to date, in memory.

    Version 1 had one `consent` file name and nothing else. Version 2 keeps
    that field (the first consent ever) and adds `consents`, one entry per
    sitting with its checksum and today's words, and on each take the consent
    it was recorded under. Nothing is dropped.
    """
    takes = man.setdefault("takes", [])
    if not isinstance(man.get("consents"), list):
        c = man.get("consent")
        first = next((t for t in takes if t.get("file") == c), None) if c else None
        man["consents"] = []
        if c:
            man["consents"].append({
                "file": c,
                "sha256": first.get("sha256") if first else None,
                "at": (first or {}).get("recorded_at") or man.get("created"),
                "challenge": None,
            })
        for t in takes:
            if first is not None and t is first:
                t.setdefault("kind", "consent")
            elif c:
                t.setdefault("consent", c)
    man["version"] = max(2, int(man.get("version") or 1))
    return man


def save_manifest(d: Path, man: dict) -> None:
    """Write the list beside itself, then swap it in. The temporary file is
    created fresh (a stale one, or a planted shortcut, is removed first and
    never written through) and the list is readable by its owner only."""
    data = json.dumps(man, indent=2, ensure_ascii=False).encode("utf-8")
    tmp = d / "manifest.json.tmp"
    try:
        os.unlink(tmp)
    except FileNotFoundError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, d / "manifest.json")


def _hash_fd(fd: int) -> str:
    h = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while block := os.read(fd, 1 << 20):
        h.update(block)
    return h.hexdigest()


def sha256(path: Path) -> str:
    """Checksum of a real file. A shortcut is refused (OSError), not followed."""
    fd = os.open(path, os.O_RDONLY | _NOFOLLOW | _NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.EINVAL, "not a file")
        return _hash_fd(fd)
    finally:
        os.close(fd)


def _file_ok(d: Path, name: str | None, digest: str | None) -> str:
    """'ok', 'missing', 'changed' or 'shortcut' for one recording."""
    if not name:
        return "missing"
    p = d / name
    try:
        st = os.lstat(p)
    except OSError:
        return "missing"
    if stat.S_ISLNK(st.st_mode):
        return "shortcut"
    try:
        return "ok" if digest and sha256(p) == digest else "changed"
    except OSError:
        return "changed"


def write_wav(fh, samples, rate: int) -> None:
    """16-bit mono PCM via the standard library, into an open binary file."""
    import numpy as np
    pcm = np.clip(np.asarray(samples, dtype="float32"), -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(fh, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def read_wav(path: Path):
    """(samples, rate) from a take, without following a shortcut; None if not."""
    try:
        import numpy as np
        fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
        with os.fdopen(fd, "rb") as fh, wave.open(fh, "rb") as w:
            if w.getsampwidth() != 2:
                return None
            ch, rate = w.getnchannels(), w.getframerate()
            raw = w.readframes(w.getnframes())
    except (ImportError, OSError, EOFError, wave.Error):
        return None
    a = np.frombuffer(raw, dtype="<i2").astype("float32") / 32767
    if ch > 1:
        a = a[: (a.size // ch) * ch].reshape(-1, ch)[:, 0]
    return a, rate


def _write_take(d: Path, n: int, samples) -> tuple[int, str]:
    """Save a take as a brand-new file: never over an existing name, never
    through a shortcut (O_EXCL refuses both), read-only to its owner after."""
    while True:
        fname = f"take-{n:03d}.wav"
        try:
            fd = os.open(d / fname, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                         0o600)
            break
        except FileExistsError:
            n += 1                    # taken already (or a planted link): next
    try:
        with os.fdopen(fd, "wb") as fh:
            write_wav(fh, samples, RATE)
            fh.flush()
            os.fsync(fh.fileno())
            os.fchmod(fh.fileno(), 0o400)    # an original: read-only from now on
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(d / fname)
        raise
    return n, fname


def level(samples) -> tuple[float, float]:
    """RMS and peak, both 0..1 — enough to say 'too quiet' or 'clipping'."""
    import numpy as np
    a = np.asarray(samples, dtype="float32")
    if a.size == 0:
        return 0.0, 0.0
    return float(np.sqrt(np.mean(a * a))), float(np.max(np.abs(a)))


def _frame_levels(samples, rate: int):
    import numpy as np
    a = np.asarray(samples, dtype="float64")
    n = max(1, int(FRAME_SECONDS * rate))
    k = a.size // n
    if k == 0:
        return np.zeros(0)
    f = a[: k * n].reshape(k, n)
    return np.sqrt((f * f).mean(axis=1))


def sound_seconds(samples, rate: int = RATE) -> float:
    """How much of the take has any sound in it at all."""
    lv = _frame_levels(samples, rate)
    return float((lv > SOUND_RMS).sum() * FRAME_SECONDS)


def speech_seconds(samples, rate: int = RATE) -> float:
    """How much of the take rises clearly above the room: speech comes and goes
    between words, a hum or a held tone does not."""
    import numpy as np
    lv = _frame_levels(samples, rate)
    if lv.size == 0:
        return 0.0
    floor = float(np.percentile(lv, 10))
    return float((lv > max(SOUND_RMS, 2 * floor)).sum() * FRAME_SECONDS)


def bursts(samples, rate: int = RATE) -> int:
    """How many times the sound rises clearly after dipping: one per syllable
    or word for someone speaking, one for a held tone or a hum — however much
    silence comes before it (verify I-54: a second of silence first made a
    steady tone count as speech)."""
    import numpy as np
    lv = _frame_levels(samples, rate)
    snd = lv[lv > SOUND_RMS]
    if snd.size == 0:
        return 0
    top = float(np.percentile(snd, 90))
    hi, lo = 0.5 * top, 0.25 * top
    n, low = 0, True
    for x in lv:
        if low and x > hi:
            n += 1
            low = False
        elif x < lo:
            low = True
    return n


def take_problem(samples, rate: int = RATE, consent: bool = False) -> str | None:
    """None if the take can be kept; otherwise the plain reason it cannot."""
    secs = len(samples) / rate
    if secs < MIN_SECONDS:
        return f"That was {secs:.1f} seconds, too short to be a phrase. Please try again."
    if sound_seconds(samples, rate) < MIN_SOUND_SECONDS:
        return ("That was silence, or too quiet to hear anyone, so it was not kept. "
                "Please speak a little closer to the microphone and try again.")
    if consent:
        if secs < MIN_CONSENT_SECONDS:
            return ("That was too short to be the whole sentence. Please read all "
                    "of it aloud, including today's words.")
        if (speech_seconds(samples, rate) < MIN_CONSENT_SPEECH
                or bursts(samples, rate) < MIN_CONSENT_BURSTS):
            return ("That did not sound like someone speaking (it was one steady "
                    "sound), so it was not kept. Please read the sentence aloud "
                    "yourself.")
    return None


def voice_pitch(samples, rate: int = RATE) -> float | None:
    """The typical pitch of the voice in Hz, or None if it cannot be told.

    A rough measure (autocorrelation over the spoken parts), good enough to
    notice a clearly different voice, such as a man's and a woman's. It is
    not proof of who is speaking."""
    import numpy as np
    a = np.asarray(samples, dtype="float64")[: rate * 20]
    n = int(0.04 * rate)
    k = a.size // n
    if k < 5:
        return None
    frames = a[: k * n].reshape(k, n)
    lv = np.sqrt((frames * frames).mean(axis=1))
    loud = frames[lv > max(SOUND_RMS, 2 * float(np.percentile(lv, 10)))]
    if loud.shape[0] < 5:
        return None
    loud = loud - loud.mean(axis=1, keepdims=True)
    spec = np.fft.rfft(loud, 2 * n, axis=1)
    ac = np.fft.irfft(np.abs(spec) ** 2, axis=1)[:, :n]
    lo, hi = int(rate / 400), int(rate / 70)          # speaking voices: 70–400 Hz
    seg = ac[:, lo:hi]
    lag = seg.argmax(axis=1) + lo
    strength = seg.max(axis=1) / np.maximum(ac[:, 0], 1e-12)
    keep = strength > 0.3
    if keep.sum() < 5:
        return None
    return float(np.median(rate / lag[keep]))


def challenge_words(k: int = 3) -> list[str]:
    return secrets.SystemRandom().sample(CHALLENGE_WORDS, k)


def consent_sentence(name: str, words: list[str], today: dt.date | None = None) -> str:
    day = (today or dt.date.today()).strftime("%B %-d, %Y")
    return (f"I am {name}. It is {day}. I am recording my own voice, for my own "
            f"Self-Cloud, to be used only as I direct. "
            f"Today's words are {', '.join(words)}.")


def _when(iso: str | None) -> str:
    try:
        return dt.datetime.fromisoformat(iso).strftime("%B %-d, %Y")
    except (TypeError, ValueError):
        return "an earlier day"


def _consent_states(d: Path, man: dict) -> list[tuple[dict, str]]:
    return [(c, _file_ok(d, c.get("file"), c.get("sha256"))) for c in man.get("consents", [])]


def _reference_pitch(d: Path, man: dict) -> tuple[float | None, str | None]:
    """The voice already recorded here: the first intact consent take, or
    failing that the first intact take of any kind."""
    by_file = {t.get("file"): t for t in man.get("takes", [])}
    cands = [c.get("file") for c in man.get("consents", [])]
    cands += [t.get("file") for t in man.get("takes", [])]
    seen = set()
    for f in cands:
        if not f or f in seen:
            continue
        seen.add(f)
        t = by_file.get(f) or {}
        if _file_ok(d, f, t.get("sha256")) != "ok":
            continue
        hz = t.get("voice_hz")
        if hz is None:
            got = read_wav(d / f)
            hz = voice_pitch(*got) if got else None
        if hz:
            return float(hz), f
    return None, None


def _place(root: Path) -> str:
    """Plain words for where a voice folder is."""
    here = os.path.abspath(root)
    with contextlib.suppress(RuntimeError, KeyError):
        if here == os.path.abspath(Path.home() / ".selfcloud" / "voice"):
            return f"on this {_computer()}"
    if Path(here).parts[-3:] == (".selfcloud", "jefferey", "voice"):
        return "on the Self-Cloud drive"
    return "in the voice folder"


def _usual_roots() -> list[Path]:
    """The folder in use now, the one set by SELFCLOUD_VOICE, every Self-Cloud
    drive plugged in, and this computer's own home folder."""
    out = [VOICE_ROOT]
    if os.environ.get("SELFCLOUD_VOICE"):
        out.append(Path(os.environ["SELFCLOUD_VOICE"]).expanduser())
    with contextlib.suppress(Exception):
        out += [dr / home.NAMESPACE / "voice" for dr in home.all_drives(any_marker=True)]
    with contextlib.suppress(RuntimeError, KeyError):
        out.append(Path.home() / ".selfcloud" / "voice")
    return out


def all_roots() -> list[Path]:
    """Every place a voice may have been recorded: the usual places, and
    every folder chosen by hand that this Mac remembers."""
    if _ROOTS is not None:
        return [Path(r) for r in _ROOTS]
    out: list[Path] = []
    seen: set[str] = set()
    for p in _usual_roots() + _remembered_places():
        keys = {os.path.abspath(p), os.path.realpath(p)}
        if keys & seen:
            continue
        seen.update(keys)
        out.append(Path(p))
    return out


def _inside(path, folder) -> bool:
    rp, top = os.path.realpath(path), os.path.realpath(folder)
    return rp == top or rp.startswith(top.rstrip(os.sep) + os.sep)


_CODE = Path(__file__).resolve().parent.parent      # JEFFEREY's own folder


def _test_place(*paths: Path) -> bool:
    """True only for the self-test, only inside the temporary folder, and
    never inside JEFFEREY's own folder — wherever that folder happens to be
    (verify regression: a copy of JEFFEREY kept under /tmp made its own
    folder count as 'temporary')."""
    if not _SELFTEST:
        return False
    tmp = tempfile.gettempdir()
    return all(_inside(p, tmp) and not _inside(p, _CODE) for p in paths or (VOICE_ROOT,))


# Folders a cloud service copies off the machine. A voice is never recorded
# into one, whatever shortcut leads there (verify I-55).
_SYNCED = ("Library/Mobile Documents", "Library/CloudStorage", "iCloud Drive",
           "Dropbox", "Google Drive", "OneDrive", "Box", "pCloud Drive")


def _anchor(root: Path) -> Path | None:
    """The real place a voice folder hangs from: the Self-Cloud drive it is
    on, or the home folder; None for a folder chosen by hand elsewhere."""
    here = os.path.abspath(root)
    places: list[Path] = []
    with contextlib.suppress(Exception):
        places += home.all_drives(any_marker=True)
    with contextlib.suppress(RuntimeError, KeyError):
        places.append(Path.home())
    for p in places:
        top = os.path.abspath(p)
        if here.startswith(top.rstrip(os.sep) + os.sep):
            return Path(top)
    return None


def check_place(root: Path) -> None:
    """Refused unless the voice folder really is where the screen will say
    it is (verify I-55: a shortcut at .selfcloud or .selfcloud/jefferey on a
    drive, or at ~/.selfcloud, sent every take into an iCloud folder while
    the screen said 'on the Self-Cloud drive ... nothing here leaves this
    machine'). No folder between the drive (or the home folder) and the
    voice folder may be a shortcut; for a folder chosen by hand, none below
    the system's own top-level folders; and never inside a folder a cloud
    service copies away."""
    here = Path(os.path.abspath(root))
    top = _anchor(here)
    if top is not None:
        steps = [top.joinpath(*here.parts[len(top.parts):i + 1])
                 for i in range(len(top.parts), len(here.parts))]
    else:
        # /tmp or /var on a Mac are the system's own shortcuts: allowed
        steps = [Path(*here.parts[:i + 1]) for i in range(2, len(here.parts))]
    for p in steps:
        try:
            st = os.lstat(p)
        except FileNotFoundError:
            break                     # not made yet: nothing to follow
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode):
            raise Refused(f"The folder {p} is a shortcut to {_link_target(p)}, so "
                          "JEFFEREY will not record a voice through it: the "
                          "recordings could end up somewhere else. Nothing was "
                          "recorded. Please ask someone you trust to look at it.")
    real = os.path.realpath(here)
    with contextlib.suppress(RuntimeError, KeyError):
        h = os.path.realpath(Path.home())
        for s in _SYNCED:
            if _inside(real, os.path.join(h, s)):
                raise Refused(f"{root} is inside a folder that a cloud service "
                              "copies off this computer, so JEFFEREY will not "
                              "record a voice there. Nothing was recorded.")


@contextlib.contextmanager
def selftest_mode(root: Path, roots: list[Path] | None = None):
    """Point the module at a temporary voice folder and allow a fake
    microphone there. Outside a temporary folder it still refuses."""
    global VOICE_ROOT, _SELFTEST, _ROOTS
    saved = VOICE_ROOT, _SELFTEST, _ROOTS
    VOICE_ROOT, _SELFTEST, _ROOTS = Path(root), True, roots
    try:
        yield
    finally:
        VOICE_ROOT, _SELFTEST, _ROOTS = saved


# --------------------------------------------------------------- recording
def record_until_enter(rate: int = RATE):
    """Open the microphone, record until the person presses return.

    Kept behind one function so the self-test can substitute a fake: the
    logic around it is what needs proving, not PortAudio.
    """
    try:
        import numpy as np
        import sounddevice as sd
    except (ImportError, OSError):
        raise SystemExit(
            "\n  The microphone library isn't installed. Once, on this Mac:\n"
            "      pip install sounddevice numpy\n"
            "  Then run this again. Nothing else is needed.\n")
    chunks: list = []

    def cb(indata, frames, t, status):
        chunks.append(indata[:, 0].copy())

    try:
        with sd.InputStream(samplerate=rate, channels=1, dtype="float32",
                            callback=cb):
            input()                       # return stops it
    except Exception as exc:
        raise SystemExit(f"\n  Couldn't open the microphone: {exc}\n"
                         "  On a Mac, check System Settings → Privacy & Security "
                         "→ Microphone,\n  and allow Terminal.\n")
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype="float32")


def play(path: Path) -> None:
    """Hear a take back. macOS ships afplay; elsewhere try a couple of players."""
    for cmd in (["afplay", str(path)], ["aplay", "-q", str(path)],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd)
            return
    print(f"  No player found. The file is at {path}")


def _reply(ask, prompt: str, eof: str = "") -> str:
    try:
        return (ask(prompt) or "").strip()
    except EOFError:
        return eof


# What a person types at each prompt, read by connector/answers.py: in lower
# case, by its first word, in English or French (I-60: 'skip' and 'quit'
# started the microphone, and 'no' kept a take as consent). Anything else is
# asked again; a closed window is 'quit'.
_SKIP = frozenset({"s", "skip", "pass", "next", "passer", "suivant"})
_QUIT = frozenset({"q", "quit", "exit", "stop", "leave", "quitter", "sortir", "fin",
                   "arrete", "arreter"})
_REDO = frozenset({"r", "redo", "again", "retry", "refaire", "encore", "recommencer"})
BEFORE = {"start": frozenset({"", "start", "record", "go", "yes", "y", "ok", "oui"}),
          "skip": _SKIP, "quit": _QUIT | answers.NO}
AFTER = {"keep": frozenset({"", "k", "keep", "garde", "garder"}) | answers.YES,
         "redo": _REDO | answers.NO, "skip": _SKIP, "quit": _QUIT}
# The agreement is kept only on a yes the person typed: never an empty line.
AFTER_CONSENT = {"keep": answers.YES, "redo": _REDO | answers.NO, "quit": _QUIT}


def _choose(ask, prompt: str, table: dict, say, hint: str) -> str:
    """One of `table`'s names, asked again until it is; 'quit' when the
    window is closed or nothing usable is typed."""
    got = answers.ask_choice(prompt, table, input_fn=ask, out=print, hint=hint)
    return got or "quit"


# ---------------------------------------------------------------- session
def start(who: str, limit: int = len(PHRASES), recorder=record_until_enter,
          quiet: bool = False, ask=None) -> int:
    """Record one sitting: a fresh consent first, then phrases, resumable.

    `recorder` and `ask` are for the self-test only (a fake microphone and
    scripted answers); anywhere but a temporary folder they are refused.
    """
    interactive = recorder is record_until_enter
    if interactive and not sys.stdin.isatty():
        # Structural, not polite: a person must be here. A script, a cron job
        # or a model cannot enrol a voice.
        _tell("Voice enrolment needs a person at a keyboard. Refusing.")
        return 2
    if not interactive and not _test_place():
        _tell("Recordings can only come from the microphone, with the person "
              "sitting here. Nothing was recorded.")
        return 2
    if ask is None or (interactive and not _test_place()):
        ask = input if interactive else (lambda prompt: "")
    try:
        return _start(who, limit, recorder, quiet, ask, interactive)
    except Refused as exc:
        _tell(str(exc))
        return 2
    except OSError as exc:
        _tell(f"JEFFEREY could not write to {exc.filename or VOICE_ROOT} "
              f"({exc.strerror or exc}). Is the drive plugged in and not full? "
              "Whatever was already recorded is safe.")
        return 2


def _legacy_name(who: str) -> str | None:
    """The name of a set already recorded under exactly this name by an
    older version — the Mac's account name the old launcher used ('laszlo2',
    'l_czako') — so its owner can carry on instead of starting a second set
    (verify regression: the set was kept but could not be continued). A new
    set never gets such a name."""
    tidy = " ".join(unicodedata.normalize("NFC", who or "").split())
    if (not tidy or len(tidy) > NAME_MAX_CHARS or len(tidy.split()) > NAME_MAX_WORDS
            or not tidy[0].isalnum() or _reads_like_a_sentence(tidy.replace(".", " "))
            or not all(c.isalnum() or c in " _-.'" for c in tidy)):
        return None
    for s in _slugs(tidy):
        p = VOICE_ROOT / s
        if _is_link(p) or not p.is_dir():
            continue
        try:
            man = load_manifest(p)
        except Refused:
            continue
        if man and _norm(man.get("person") or "") == _norm(tidy):
            return man["person"]
    return None


def places_path() -> Path:
    """Where this Mac remembers voice folders chosen by hand (SELFCLOUD_VOICE),
    so `delete` finds them later even when that setting is gone."""
    return home.owner_dir() / "voice-places.json"


def _remembered_places() -> list[Path]:
    try:
        fd = os.open(places_path(), os.O_RDONLY | _NOFOLLOW)
        with os.fdopen(fd, "rb") as fh:
            got = json.loads(fh.read(1 << 20).decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    return [Path(p) for p in (got.get("places") if isinstance(got, dict) else []) or []
            if isinstance(p, str) and os.path.isabs(p)]


def _remember_place(root: Path) -> None:
    """Note a voice folder that is not one of the usual places (verify I-56:
    a set recorded under a custom SELFCLOUD_VOICE was left behind by a later
    delete that said 'Gone.')."""
    if _ROOTS is not None:
        return                        # the self-test's folders are its own
    usual: set[str] = set()
    with contextlib.suppress(Exception):
        usual |= {os.path.abspath(dr / home.NAMESPACE / "voice")
                  for dr in home.all_drives(any_marker=True)}
    with contextlib.suppress(RuntimeError, KeyError):
        usual.add(os.path.abspath(Path.home() / ".selfcloud" / "voice"))
    here = os.path.abspath(root)
    known = [str(p) for p in _remembered_places()]
    if here in usual or here in known:
        return
    with contextlib.suppress(OSError):
        home._write_private(places_path(), json.dumps(
            {"places": known + [here]}, indent=1).encode("utf-8"))


def _start(who, limit, recorder, quiet, ask, interactive) -> int:
    say = (lambda *a, **k: None) if quiet else print
    try:
        name = clean_name(who)
    except Refused:
        name = _legacy_name(who)
        if not name:
            raise
    d = person_dir(name)
    check_place(VOICE_ROOT)
    VOICE_ROOT.parent.mkdir(parents=True, exist_ok=True)
    check_place(VOICE_ROOT)
    _secure_dir(VOICE_ROOT, create=True)
    _remember_place(VOICE_ROOT)
    created = not os.path.lexists(d)
    _secure_dir(d, create=True)

    with _lock(d) as locked:
        if not locked:
            _tell(f"Another window is already recording {name}'s voice. Please "
                  "finish there, or close it, then try again.")
            return 1
        _tighten(d)
        man = load_manifest(d)
        fresh = not man
        if fresh:
            man = _migrate({
                "person": name,
                "created": dt.datetime.now().isoformat(timespec="seconds"),
                "machine": platform.node(),
                "rate": RATE,
                "consent": None,
                "takes": [],
                "rule": RULE,
            })
        person = man.get("person") or name

        def give_up(msg: str, rc: int = 1) -> int:
            _tell(msg)
            if fresh and created:
                _shred(d, set(), _result())
            return rc

        # One folder, one person: a look-alike name never merges in.
        if _norm(person) != _norm(name):
            return give_up(
                f"The recordings in {d} belong to {person}, whose name looks the "
                f"same to the computer as {name}. So that two people's voices are "
                "never mixed, please use a name that tells you apart, for example "
                "with a surname or a middle name. Nothing was recorded.")

        here = _place(VOICE_ROOT)
        say(f"\n  Recording {person}'s voice {here}, in {d}")
        if here.startswith("on this"):
            say(_wrap("(No Self-Cloud drive is plugged in, so this stays on this "
                      f"{_computer()}. Plug the drive in first if you want it there.)"))
        say("  Nothing here leaves this machine. Read naturally. Press return to")
        say("  start each one and return again to stop. Type q at any prompt to quit.\n")

        states = _consent_states(d, man)
        if not fresh:
            first = man["consents"][0] if man["consents"] else {}
            say(_wrap(f"There are already {len(man['takes'])} recordings of {person}'s "
                      f"voice here. {person} first agreed on {_when(first.get('at'))}. "
                      f"Only {person} may add to them."))
            ans = _reply(ask, f"  Are you {person} yourself? Type yes to carry on: ")
            if answers.yes_no(ans) is not True:
                return give_up(
                    "Not carried on. If you are someone else, please run this again "
                    "with your own name, so your voice is kept separately. Nothing "
                    "was recorded.")
            if man["takes"] and not any(s == "ok" for _, s in states):
                lost = man["consents"][0].get("file") if man["consents"] else None
                say("\n" + _wrap(f"The recording of {person} agreeing"
                                 + (f" ({lost})" if lost else "")
                                 + " is missing or has been changed. It must be said "
                                 "again now; nothing else will be recorded until it is."))

        n = max((int(t.get("n") or 0) for t in man["takes"]), default=0)

        def capture(text: str, tag: str, consent: bool = False):
            """Record until a take is usable: ('kept', samples), or 'skipped'/'quit'."""
            tries = 0
            while True:
                say(f"\n  ┌ {tag}")
                for line in textwrap.wrap(text, 66) or [""]:
                    say(f"  │  {line}")
                say("  └ return = start recording · s = skip · q = quit")
                if interactive:
                    # 'skip' and 'quit' never start the microphone (I-60)
                    what = _choose(ask, "  > ", BEFORE, say,
                                   "Press return to start, or type skip or quit.")
                    if what == "quit":
                        return "quit", None
                    if what == "skip":
                        return "skipped", None
                    say("  ● recording — press return when you've finished")
                samples = recorder(RATE)
                problem = take_problem(samples, RATE, consent=consent)
                if problem:
                    tries += 1
                    say(_wrap(problem))
                    if tries >= MAX_TRIES:
                        _tell("The microphone does not seem to be hearing anyone, so "
                              "nothing more was recorded this time. On a Mac, check "
                              "System Settings → Privacy & Security → Microphone, "
                              "and allow Terminal.")
                        return "quit", None
                    continue
                secs = len(samples) / RATE
                rms, peak = level(samples)
                note = ""
                if rms < 0.01:
                    note = "  (very quiet — closer to the mic, or check the input)"
                elif peak > 0.99:
                    note = "  (clipping — a little further from the mic)"
                say(f"  {secs:.1f}s, level {rms:.3f}{note}")
                if interactive and consent:
                    # The agreement is kept only on a typed yes (I-60: 'no'
                    # kept it); an empty line asks again.
                    what = _choose(ask, "  Keep this as your agreement? Type yes, or r to "
                                        "record it again, or q to stop > ",
                                   AFTER_CONSENT, say,
                                   "Type yes to keep it, r to record it again, or q to stop.")
                elif interactive:
                    what = _choose(ask, "  return = keep · r = redo · s = skip · q = quit > ",
                                   AFTER, say,
                                   "Press return to keep it, or type redo, skip or quit.")
                else:
                    what = "keep"
                if what == "redo":
                    continue
                if what == "skip":
                    return "skipped", None
                if what == "quit":
                    return "quit", None
                return "kept", samples

        def commit(samples, text: str, tag: str, **extra) -> dict:
            nonlocal n
            n, fname = _write_take(d, n + 1, samples)
            rms, _ = level(samples)
            entry = {"n": n, "tag": tag, "phrase": text, "file": fname,
                     "seconds": round(len(samples) / RATE, 2), "rms": round(rms, 4),
                     "sha256": sha256(d / fname),
                     "recorded_at": dt.datetime.now().isoformat(timespec="seconds")}
            entry.update(extra)
            man["takes"].append(entry)
            return entry

        # 1. Consent, first and every sitting, in the person's own voice, with
        #    three words nobody could have recorded before today.
        words = challenge_words()
        text = consent_sentence(person, words)
        say("  First, in your own voice, say that you agree. The last three words")
        say("  are new every time, so an old recording does not have them.")
        got, samples = capture(text, "CONSENT — read this exactly, out loud", consent=True)
        if got != "kept":
            return give_up("No consent recording, so nothing else is recorded. "
                           "Nothing new has been kept.")
        hz = voice_pitch(samples)
        ref_hz, ref_file = (None, None) if fresh else _reference_pitch(d, man)
        differs = bool(hz and ref_hz and max(hz, ref_hz) / min(hz, ref_hz) > VOICE_DIFFERS)
        if differs:
            which = "higher" if hz > ref_hz else "lower"
            say("\n" + _wrap(f"This voice sounds quite different from the voice "
                             f"already recorded for {person} (it is {which}). These "
                             f"recordings must be only {person}'s own voice. If you "
                             f"are not {person}, please stop now."))
            ans = _reply(ask, f"  If it really is you, {person}, type: it is me  > ")
            if ans.strip(" .!").lower() != "it is me":
                return give_up("Stopped. The new recording was not kept. If you are "
                               "someone else, please run this again with your own "
                               "name, so your voice is kept separately.")
        # words_checked: the words were SHOWN; nothing on this machine can yet
        # hear which words were said, and the list never claims it did
        entry = commit(samples, text, "CONSENT", kind="consent",
                       challenge=" ".join(words), words_checked=False,
                       voice_hz=round(hz, 1) if hz else None,
                       compared_with=ref_file, voice_differs=differs)
        man["consents"].append({"file": entry["file"], "sha256": entry["sha256"],
                                "at": entry["recorded_at"], "challenge": entry["challenge"],
                                "words_checked": False,
                                "voice_hz": entry["voice_hz"], "voice_differs": differs})
        if not man.get("consent"):
            man["consent"] = entry["file"]
        save_manifest(d, man)
        this_consent = entry["file"]

        # 2. The phrases, resumable.
        done = {t["phrase"] for t in man["takes"] if t.get("kind") != "consent"}

        def phrase_take(text: str, tag: str) -> str:
            got, samples = capture(text, tag)
            if got == "kept":
                commit(samples, text, tag, consent=this_consent)
                save_manifest(d, man)      # after EVERY take: quitting loses nothing
            return got

        todo = [p for p in PHRASES if p not in done][:max(0, limit)]
        already = sum(1 for p in PHRASES if p in done)
        for i, phrase in enumerate(todo, 1):
            if phrase_take(phrase, f"{already + i} of {len(PHRASES)}") == "quit":
                break
        else:
            # 3. In their own words — only once the sheet is done.
            for prompt in OPEN:
                if prompt in done:
                    continue
                if phrase_take(prompt, "IN YOUR OWN WORDS") == "quit":
                    break

        total = sum(t["seconds"] for t in man["takes"])
        say(f"\n  {len(man['takes'])} takes, {total / 60:.1f} minutes of your voice, "
            f"in {d}")
        say("  Run this again any time to carry on. `status` shows where you are.\n")
        return 0


def _people_in(root: Path) -> list[tuple[Path, dict | None]]:
    out = []
    try:
        if _is_link(root) or not root.is_dir():
            return out
        with os.scandir(root) as it:
            entries = sorted(it, key=lambda e: e.name)
    except OSError:
        return out
    for e in entries:
        p = Path(e.path)
        if e.is_symlink() or not e.is_dir(follow_symlinks=False):
            continue
        try:
            out.append((p, load_manifest(p) or None))
        except Refused:
            out.append((p, None))
    return out


def status(who: str | None = None) -> int:
    for r in all_roots():
        _scrub_deletions(r)          # an older version kept a name there (R6)
    if not (who or "").strip():
        found = False
        for root in all_roots():
            for p, man in _people_in(root):
                found = True
                if man:
                    print(f"  {man.get('person', p.name)} — {len(man['takes'])} "
                          f"recordings, {_place(root)} ({p})")
                else:
                    print(f"  {p.name} — a folder without a readable list, "
                          f"{_place(root)} ({p})")
        if not found:
            print("\n  No voice has been recorded yet.\n")
        return 0
    try:
        return _status(who)
    except Refused as exc:
        _tell(str(exc))
        return 1
    except OSError as exc:
        _tell(f"JEFFEREY could not read {exc.filename or VOICE_ROOT} "
              f"({exc.strerror or exc}). Nothing was changed.")
        return 1


def _status(who: str) -> int:
    name = " ".join(who.split())
    d = person_dir(who)
    elsewhere = [p for p in _find(_slugs(who), all_roots())[0]
                 if os.path.abspath(p) != os.path.abspath(d)]
    if not os.path.lexists(d / "manifest.json"):
        if elsewhere:
            print(f"\n  Nothing recorded for {name} {_place(VOICE_ROOT)} ({d}).")
            print("  But recordings were found:")
            for p in elsewhere:
                print(f"    · {_place(p.parent)} ({p})")
            print()
        else:
            print(f"\n  Nothing recorded yet for {name}. Run `start`.\n")
        return 0
    if _is_link(d):
        raise Refused(f"The folder {d} is a shortcut to {_link_target(d)}, so "
                      "JEFFEREY will not read it.")
    man = load_manifest(d)          # status only reads: it changes nothing
    person = man.get("person") or name
    takes = man["takes"]
    total = sum(t.get("seconds", 0) for t in takes)
    phrases_done = sum(1 for t in takes if t.get("phrase") in PHRASES)
    own = sum(1 for t in takes if t.get("phrase") in OPEN)
    ok = sum(1 for t in takes if _file_ok(d, t.get("file"), t.get("sha256")) == "ok")
    states = _consent_states(d, man)
    print(f"\n  {person} — {len(takes)} takes, {total / 60:.1f} min")
    good = [c for c, s in states if s == "ok"]
    if not states:
        print(_row("consent", f"MISSING: there is no recording of {person} agreeing. "
                   "Nothing more is recorded until it is said, at the start of the "
                   "next sitting."))
    label = "consent"
    for c, s in states:
        f, when = c.get("file"), _when(c.get("at"))
        if s == "ok":
            silent = False
            got = read_wav(d / f)
            if got is not None:
                silent = sound_seconds(*got) < MIN_SOUND_SECONDS
            if silent:
                print(_row(label, f"SILENT: the recording of {when} ({f}) has no "
                           "voice in it, so it does not count as agreeing."))
                good.remove(c)
            else:
                print(_row(label, f"recorded on {when} ({f}), and checked"))
        else:
            why = {"missing": "is gone", "changed": "has been changed",
                   "shortcut": "has been replaced by a shortcut"}[s]
            print(_row(label, f"MISSING: the recording of {person} agreeing on "
                       f"{when} ({f}) {why}, so it no longer counts."))
        if c.get("voice_differs"):
            print(_row("", f"That day the voice sounded different from the first "
                       f"one, and the speaker said it was {person}."))
        label = ""
    if states and not good:
        print(_row("", f"Nothing more is recorded until {person} says it again, "
                   "at the start of the next sitting."))
    unconsented = [t for t in takes if t.get("kind") != "consent"
                   and t.get("consent") not in {c.get("file") for c in good}]
    if unconsented and good:
        print(_row("", f"{len(unconsented)} recordings were made under an "
                   "agreement that no longer counts."))
    print(f"  phrases    {phrases_done} of {len(PHRASES)}")
    print(f"  own words  {own} of {len(OPEN)}")
    print(f"  integrity  {ok} of {len(takes)} files match their checksum")
    print(f"  where      {d}")
    for p in elsewhere:
        print(f"  also       {_place(p.parent)} ({p})")
    print(f"\n{_wrap(man.get('rule', RULE))}\n")
    return 0


# ---------------------------------------------------------------- deletion
def _result() -> dict:
    return {"wiped": 0, "links": [], "shared": [], "unwiped": [], "failed": [],
            "blocked": None}


def _overwrite(fd: int, size: int) -> None:
    """Random bytes over every byte of the file, then to the disk."""
    os.lseek(fd, 0, os.SEEK_SET)
    left = size
    while left > 0:
        mv = memoryview(os.urandom(min(left, 1 << 20)))
        while mv:
            w = os.write(fd, mv)
            left -= w
            mv = mv[w:]
    os.fsync(fd)
    with contextlib.suppress(ImportError, OSError, AttributeError):
        import fcntl
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)       # macOS: past the drive's cache


# Inside a folder being deleted, every step goes through the open folder
# itself (a descriptor), never through its path again: swapping the folder
# for a shortcut half way through cannot send the deletion somewhere else
# (verify I-55: a path-based walk overwrote and removed an outside will.txt).
_AT = os.open in os.supports_dir_fd and os.unlink in os.supports_dir_fd


def _readlink_at(name: str, dfd: int) -> str:
    try:
        return os.readlink(name, dir_fd=dfd)
    except (OSError, NotImplementedError, TypeError):
        return "somewhere else"


def _shred_file(dfd: int, name: str, p: Path, known: set[str], res: dict) -> None:
    """One file, opened through its folder `dfd` without following a link."""
    try:
        fd = os.open(name, os.O_RDONLY | _NOFOLLOW | _NONBLOCK, dir_fd=dfd)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.EMLINK):   # became a shortcut
            res["links"].append((p, _readlink_at(name, dfd)))
        else:
            res["unwiped"].append(p)
        with contextlib.suppress(OSError):
            os.unlink(name, dir_fd=dfd)
        return
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            os.unlink(name, dir_fd=dfd)
            return
        if st.st_nlink > 1 and _hash_fd(fd) not in known:
            # Another name elsewhere points at these same bytes, and they are
            # not one of the recordings: overwriting would damage that other
            # file. Remove this name only, and say so.
            res["shared"].append(p)
            os.unlink(name, dir_fd=dfd)
            return
        with contextlib.suppress(OSError):
            os.fchmod(fd, 0o600)          # through the open file, never a path
        try:
            wfd = os.open(name, os.O_WRONLY | _NOFOLLOW | _NONBLOCK, dir_fd=dfd)
        except OSError:
            res["unwiped"].append(p)
            os.unlink(name, dir_fd=dfd)
            return
        try:
            wst = os.fstat(wfd)
            if (wst.st_dev, wst.st_ino) != (st.st_dev, st.st_ino):
                res["failed"].append((p, "it changed while being deleted"))
                return
            _overwrite(wfd, wst.st_size)
        finally:
            os.close(wfd)
        os.unlink(name, dir_fd=dfd)
        res["wiped"] += 1
    except OSError as exc:
        res["failed"].append((p, exc.strerror or "it could not be removed"))
    finally:
        os.close(fd)


def _shred_at(dfd: int, name: str, p: Path, known: set[str], res: dict) -> None:
    """Overwrite and remove the entry `name` of the open folder `dfd`."""
    try:
        st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError:
        res["failed"].append((p, "it could not be looked at"))
        return
    if stat.S_ISLNK(st.st_mode):
        res["links"].append((p, _readlink_at(name, dfd)))
        with contextlib.suppress(OSError):
            os.unlink(name, dir_fd=dfd)   # the shortcut itself, never what it points to
        return
    if stat.S_ISDIR(st.st_mode):
        try:
            sub = os.open(name, os.O_RDONLY | _DIRECTORY | _NOFOLLOW, dir_fd=dfd)
        except OSError:
            res["failed"].append((p, "the folder could not be opened"))
            return
        try:
            sst = os.fstat(sub)
            if (sst.st_dev, sst.st_ino) != (st.st_dev, st.st_ino):
                res["failed"].append((p, "it changed while being deleted"))
                return
            for nm in sorted(os.listdir(sub)):
                _shred_at(sub, nm, p / nm, known, res)
        except OSError:
            res["failed"].append((p, "the folder could not be opened"))
            return
        finally:
            os.close(sub)
        try:
            os.rmdir(name, dir_fd=dfd)
        except OSError:
            res["failed"].append((p, "the folder could not be removed"))
        return
    if stat.S_ISREG(st.st_mode):
        _shred_file(dfd, name, p, known, res)
        return
    with contextlib.suppress(OSError):
        os.unlink(name, dir_fd=dfd)   # a pipe or a device entry: no data in it


def _shred(path: Path, known: set[str], res: dict) -> None:
    """Overwrite and remove everything at `path`, following no shortcut."""
    path = Path(os.path.abspath(path))
    if not _AT:                       # no descriptor calls here: refuse, never guess
        res["failed"].append((path, "this computer cannot delete it safely"))
        return
    try:
        pfd = os.open(path.parent, os.O_RDONLY | _DIRECTORY)
    except FileNotFoundError:
        return
    except OSError:
        res["failed"].append((path, "its folder could not be opened"))
        return
    try:
        _shred_at(pfd, path.name, path, known, res)
    finally:
        os.close(pfd)


def _find(slugs: list[str], roots: list[Path]) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Each folder of this person's, in every place; and places that hold one
    behind a shortcut (which are reported, never followed)."""
    found: list[Path] = []
    blocked: list[tuple[Path, str]] = []
    for r in roots:
        try:
            st = os.lstat(r)
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode):
            if any(os.path.lexists(r / s) for s in slugs):   # a look, not a write
                blocked.append((r, _link_target(r)))
            continue
        if not stat.S_ISDIR(st.st_mode):
            continue
        for s in slugs:
            p = r / s
            if os.path.lexists(p) and p not in found:
                found.append(p)
    return found, blocked


def _whose(p: Path) -> str | None:
    """The name a set of recordings was made under, from its own list; None
    for a shortcut or a folder whose list cannot be read."""
    if _is_link(p):
        return None
    try:
        return (load_manifest(p) or {}).get("person") or None
    except (Refused, OSError):
        return None


def _count(p: Path) -> int:
    try:
        return len(load_manifest(p).get("takes", [])) if not _is_link(p) else 0
    except (Refused, OSError):
        return 0


def _record_deletion(root: Path, res: dict, complete: bool) -> None:
    """A line in the voice folder saying a voice was deleted, on which day,
    and how completely (voice-35: nothing recorded that it happened). It
    keeps no voice, no name and nothing that leads back to one (R6: the
    folder's name, 'erin-kowalski', stood in it beside a plain fingerprint of
    the name, after her voice was deleted at her request): only a random
    deletion number, the day, and how many files were overwritten."""
    _scrub_deletions(root)
    line = json.dumps({
        "deletion": secrets.token_hex(8),
        "deleted_on": dt.date.today().isoformat(),
        "files_overwritten": res["wiped"], "complete": complete,
    }) + "\n"
    with contextlib.suppress(OSError):
        if _is_link(root):
            return
        fd = os.open(root / "deletions.jsonl",
                     os.O_WRONLY | os.O_APPEND | os.O_CREAT | _NOFOLLOW, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)


_KEPT_IN_A_DELETION = ("deletion", "deleted_on", "files_overwritten", "complete")


def _scrub_deletions(root: Path) -> None:
    """Rewrite the record of deletions an older version wrote, keeping only
    what a deletion record may hold: no folder name, no fingerprint of the
    name, no time of day (R6). A line that cannot be read is dropped — it
    could hold anything. Nothing happens when there is nothing to clean."""
    f = root / "deletions.jsonl"
    with contextlib.suppress(OSError, ValueError):
        if _is_link(root) or _is_link(f) or not f.is_file():
            return
        fd = os.open(f, os.O_RDONLY | _NOFOLLOW)
        try:
            raw = b""
            while True:
                chunk = os.read(fd, 1 << 16)
                if not chunk:
                    break
                raw += chunk
        finally:
            os.close(fd)
        out, changed = [], False
        for text in raw.decode("utf-8", "replace").splitlines():
            if not text.strip():
                continue
            try:
                rec = json.loads(text)
            except ValueError:
                changed = True
                continue
            if not isinstance(rec, dict):
                changed = True
                continue
            clean = {k: rec[k] for k in _KEPT_IN_A_DELETION if k in rec}
            if "deleted_on" not in clean and isinstance(rec.get("deleted_at"), str):
                clean["deleted_on"] = rec["deleted_at"][:10]
            if "deletion" not in clean:
                clean = {"deletion": secrets.token_hex(8), **clean}
            if clean != rec:
                changed = True
            out.append(json.dumps(clean))
        if not changed:
            return
        tmp = root / f".deletions.{secrets.token_hex(4)}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600)
        try:
            os.write(fd, ("".join(x + "\n" for x in out)).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, f)


def _account_name() -> str:
    with contextlib.suppress(Exception):
        import getpass
        return slug(getpass.getuser())
    return ""


def _still_kept(roots: list[Path], raw: str) -> None:
    """Every other voice still kept, by name, and which of them may be this
    person's too (verify I-56: an older set under the Mac's account name,
    'laszlo', stayed while the screen said 'Gone.')."""
    left = [(r, p, man) for r in roots for p, man in _people_in(r)]
    if not left:
        return
    mine = set(_norm(raw).replace("-", " ").split())
    acct = _account_name()
    print("\n  Still kept here, under other names (not deleted):")
    maybe = []
    for r, p, man in left:
        person = (man or {}).get("person") or p.name
        n = len((man or {}).get("takes", []))
        words = set(_norm(person).replace("-", " ").replace("_", " ").split())
        flag = bool(words & mine) or (acct and p.name == acct)
        if flag:
            maybe.append(person)
        print(f"    · {person} — {n} recordings, {_place(r)} ({p})"
              + ("   <- this may be yours too" if flag else ""))
    if maybe:
        print(_wrap("A set marked 'this may be yours too' shares a name with yours, "
                    "or with this computer's account (older versions of JEFFEREY "
                    "named recordings that way). If it is your voice, delete it too, "
                    "by the name shown: run this again and type that name.", "  "))


def delete(who: str, force: bool = False) -> int:
    """Real deletion, in every place, by the person at the keyboard.

    `force` skips the typed confirmation; only the self-test may use it, and
    only inside a temporary folder. --yes on the command line is refused.
    A set made under a name that only looks the same to the computer
    ('Mary-Ann' for 'Mary Ann') is someone else's and is never deleted.
    """
    raw = " ".join((who or "").split())
    slugs = _slugs(who or "")
    if not slugs:
        _tell("Please say whose recordings to delete, by name. Nothing was deleted.")
        return 2
    roots = all_roots()
    for r in roots:
        _scrub_deletions(r)          # what an older version kept of a name (R6)
    if force and not _test_place(*roots):
        _tell("Deleting a voice cannot be done by a script, or with --yes. The "
              "person has to be at the keyboard and type the name. Nothing was "
              "deleted.")
        return 2
    everything, blocked = _find(slugs, roots)
    found, others = [], []
    for p in everything:
        person = _whose(p)
        if person is not None and _norm(person) != _norm(raw):
            others.append((p, person))          # a look-alike name: someone else's
        else:
            found.append(p)

    def tell_others() -> None:
        for p, person in others:
            print("\n" + _wrap(f"The recordings in {p} belong to {person}, whose name "
                               f"only looks the same to the computer as {raw}. They "
                               f"were NOT deleted. To delete them, type that name "
                               f"exactly as it is written: {person}"))

    if not found and not blocked:
        if others:
            tell_others()
            print()
            return 1
        print(f"\n  There is nothing recorded for {raw}. JEFFEREY looked:")
        for r in roots:
            print(f"    · {_place(r)} ({r})")
        print(_wrap("If a Self-Cloud drive that is not plugged in now was ever "
                    "used, plug it in and look again.") + "\n")
        return 0
    if not force:
        if not sys.stdin.isatty():
            _tell("Deleting a voice needs a person to confirm. Refusing.")
            return 2
        print(f"\n  Recordings of {raw}'s voice were found:")
        for p in found:
            person = _whose(p)
            who_line = (f"{person} — {_count(p)} recordings" if person else
                        "a folder whose list of recordings cannot be read")
            print(f"    · {who_line}, {_place(p.parent)} ({p})")
        for r, target in blocked:
            print(f"    · behind a shortcut at {r}, which points to {target}")
        tell_others()
        try:
            ans = input(f"\n  Delete every recording of {raw}'s voice, permanently? "
                        "This cannot be undone.\n  Type the name to confirm: ")
        except EOFError:
            ans = ""
        if _norm(ans) != _norm(raw):
            print("  Not deleted.\n")
            return 1
    elif others:
        tell_others()

    complete = True
    for p in found:
        known: set[str] = set()
        with contextlib.suppress(Refused, OSError):
            if not _is_link(p):
                known = {t.get("sha256") for t in load_manifest(p).get("takes", [])
                         if t.get("sha256")}
        res = _result()
        whole_link = _is_link(p)
        _shred(p, known, res)
        where = f"{_place(p.parent)} ({p})"
        if whole_link:
            complete = False
            print(f"\n  {where}:")
            print(_wrap(f"This was a shortcut to {_link_target_text(res)}. JEFFEREY "
                        "removed the shortcut but did not follow it, so anything there "
                        "is untouched. Please look there with someone you trust.", "    "))
            _record_deletion(p.parent, res, False)
            continue
        here_complete = True
        print(f"\n  {where}:")
        print(f"    {res['wiped']} files overwritten, then removed.")
        inner = res["links"]
        if inner:
            # What a shortcut pointed to may be a copy of the voice: it was
            # not touched, so this is not 'Gone' (verify I-56).
            here_complete = False
            print(_wrap(f"{len(inner)} shortcut{'s' if len(inner) > 1 else ''} removed "
                        "without being followed, so what they pointed to was not "
                        "touched. If that is a copy of the voice, it is still there. "
                        "Please look there with someone you trust:", "    "))
            for lp, t in inner:
                print(f"      {lp.name} → {t}")
        if res["shared"]:
            here_complete = False
            print(_wrap(f"{len(res['shared'])} file(s) also had another name elsewhere "
                        "on this drive and were not among the recordings, so they were "
                        "removed from here but not overwritten (the other copy was "
                        "left as it was):", "    "))
            for sp in res["shared"]:
                print(f"      {sp.name}")
        if res["unwiped"]:
            here_complete = False
            print(_wrap(f"{len(res['unwiped'])} file(s) could not be overwritten, "
                        "only removed: " + ", ".join(u.name for u in res["unwiped"]),
                        "    "))
        if res["failed"]:
            here_complete = False
            for fp, why in res["failed"]:
                print(f"    could not finish with {fp}: {why}")
        complete = complete and here_complete
        _record_deletion(p.parent, res, here_complete)
    for r, target in blocked:
        complete = False
        print("\n" + _wrap(f"The voice folder at {r} is a shortcut to {target}. "
                           "JEFFEREY did not follow it, so anything there is "
                           "untouched. Please look there with someone you trust."))

    if complete:
        print("\n" + _wrap(f"Gone. Every recording of {raw}'s voice that JEFFEREY "
                           "could find under that name was overwritten, then removed, "
                           "with its list of recordings."))
    else:
        print("\n" + _wrap("Not everything could be removed: see above. Everything "
                           "else is gone."))
    _still_kept(roots, raw)
    print("\n  Please note:\n" +
          _wrap(f"If {raw}'s voice was ever recorded onto a Self-Cloud drive that is "
                "not plugged in now, those recordings are still on it. Plug it in "
                "and run this again.") + "\n\n" +
          LIMITS_NOTE.format(computer=_computer()) + "\n")
    return 0 if complete else 1


def _link_target_text(res: dict) -> str:
    return res["links"][0][1] if res["links"] else "somewhere else"


# ---------------------------------------------------------------- selftest
def _fake_voice(hz: float = 220.0, seconds: float = 6.0, rate: int = RATE):
    """A stand-in for speech: a voice-like tone in syllables, with pauses."""
    import numpy as np
    t = np.arange(int(rate * seconds)) / rate
    syll = ((t % 0.35) < 0.25) & (t > 0.3)
    return (0.3 * np.sin(2 * np.pi * hz * t) * syll).astype("float32")


def selftest() -> int:
    """Everything except the microphone, which is swapped for a tone."""
    import numpy as np
    td = Path(tempfile.mkdtemp(prefix="voice-selftest-"))
    yes = (lambda prompt: "yes")
    try:
        with selftest_mode(td / "voice", roots=[td / "voice"]):
            fake = (lambda rate: _fake_voice())

            # a short session: consent + 3 phrases + the 5 open prompts
            rc = start("Test Person", limit=3, recorder=fake, quiet=True)
            assert rc == 0, rc
            d = person_dir("Test Person")
            man = load_manifest(d)
            assert man["consent"] == "take-001.wav", man["consent"]
            assert "I am Test Person" in man["takes"][0]["phrase"]
            words = man["consents"][0]["challenge"].split()
            assert len(words) == 3 and all(w in man["takes"][0]["phrase"] for w in words)
            assert len(man["takes"]) == 1 + 3 + len(OPEN), len(man["takes"])
            for t in man["takes"]:
                f = d / t["file"]
                assert f.exists() and sha256(f) == t["sha256"], t["file"]
                mode = f.stat().st_mode & 0o777
                assert mode == 0o400, f"a take is {oct(mode)}, not owner read-only"
                with wave.open(str(f)) as w:
                    assert w.getnchannels() == 1 and w.getframerate() == RATE
                    assert w.getsampwidth() == 2
            assert (d.stat().st_mode & 0o777) == 0o700
            assert ((d / "manifest.json").stat().st_mode & 0o777) == 0o600

            # resumable: a second sitting begins with a FRESH consent, then
            # records only what is missing. (The first version kept the old
            # consent and recorded none; the stress test showed that lets a
            # second person carry on under the first one's agreement.)
            before = len(man["takes"])
            rc = start("Test Person", limit=2, recorder=fake, quiet=True, ask=yes)
            assert rc == 0, rc
            man = load_manifest(d)
            assert len(man["takes"]) == before + 1 + 2, len(man["takes"])
            assert man["consent"] == "take-001.wav", "the first consent was lost"
            assert len(man["consents"]) == 2, man["consents"]
            spoken = [t["phrase"] for t in man["takes"] if t.get("kind") != "consent"]
            assert len(set(spoken)) == len(spoken), "a phrase repeated"

            # pressing return is not "yes, I am that person"
            rc = start("Test Person", limit=2, recorder=fake, quiet=True,
                       ask=lambda p: "")
            assert rc == 1 and len(load_manifest(d)["takes"]) == before + 3

            # everything lives under the voice root and nowhere else
            assert d.resolve().is_relative_to(VOICE_ROOT.resolve())
            # a hostile name is either refused outright or lands INSIDE the folder
            for hostile in ("../../etc", "/etc/passwd", "..", "a/b/../../../c", "   "):
                try:
                    hd = person_dir(hostile)
                except Refused:
                    continue                      # refused: fine
                assert hd.resolve().is_relative_to(VOICE_ROOT.resolve()), hostile
                assert hd.parent.resolve() == VOICE_ROOT.resolve(), hostile
                assert start(hostile, limit=0, recorder=fake, quiet=True) == 2, hostile

            # too short is refused and retried, not kept; silence likewise
            def awkward_first():
                yield np.zeros(int(RATE * 0.2), dtype="float32")   # a mis-press
                yield np.zeros(int(RATE * 6), dtype="float32")     # silence
                while True:
                    yield _fake_voice()
            feed = awkward_first()
            rc = start("Second Person", limit=0, recorder=lambda r: next(feed),
                       quiet=True)
            m2 = load_manifest(person_dir("Second Person"))
            assert m2["takes"], "nothing kept"
            assert all(t["seconds"] >= MIN_SECONDS and t["rms"] > 0.01
                       for t in m2["takes"]), "a too-short or silent take was kept"
            # limit=0 means no sheet phrases this sitting; consent + own words only
            assert m2["consent"] and len(m2["takes"]) == 1 + len(OPEN), len(m2["takes"])

            # a silent consent keeps nothing at all
            assert start("Third Person", limit=0, quiet=True,
                         recorder=lambda r: np.zeros(RATE * 6, dtype="float32")) == 1
            assert not person_dir("Third Person").exists()

            # real deletion: files gone, folder gone, and a shortcut planted in
            # the folder is removed without the file it points to being touched
            # — and, since that file may be a copy of the voice, it is not
            # called 'Gone' (rc 1; it was 0 before verify I-56)
            outside = td / "keep.txt"
            outside.write_text("the owner's own file")
            os.symlink(outside, d / "take-099.wav")
            files = [d / t["file"] for t in man["takes"]]
            with contextlib.redirect_stdout(open(os.devnull, "w")):
                assert delete("Test Person", force=True) == 1
            assert not d.exists() and not any(f.exists() for f in files)
            assert outside.read_text() == "the owner's own file"
            # a look-alike name never deletes someone else's set
            with contextlib.redirect_stdout(open(os.devnull, "w")):
                assert delete("Second-Person", force=True) == 1
            assert person_dir("Second Person").exists()

        # outside the self-test, a fake microphone and --yes are refused
        assert start("Test Person", limit=0, recorder=fake, quiet=True) == 2

        # nothing here can reach a network
        import ast
        src = Path(__file__).read_text()
        names = {n.names[0].name.split(".")[0] for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Import)}
        names |= {n.module.split(".")[0] for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.ImportFrom) and n.module}
        for bad in ("socket", "urllib", "http", "requests", "ssl"):
            assert bad not in names, f"{bad} imported"

        print("\n  ✓ voice enrolment: every sitting begins with a fresh spoken")
        print("    consent with today's words, silent takes are refused, takes are")
        print("    checksummed WAVs readable by their owner only, resumable without")
        print("    repeating, a second person cannot carry on by pressing return,")
        print("    names cannot escape the voice folder, deletion is real and never")
        print("    follows a shortcut, and nothing here can reach a network.\n")
        return 0
    finally:
        for p in td.rglob("*"):
            if p.is_file() and not p.is_symlink():
                with contextlib.suppress(OSError):
                    p.chmod(0o644)
        shutil.rmtree(td, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--who", default=None,
                    help="whose voice: the person's own name (required)")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("start", help="record, or carry on recording")
    s.add_argument("--phrases", type=int, default=len(PHRASES),
                   help="how many phrases this sitting (default: all remaining)")
    sub.add_parser("status", help="how much is recorded, and is it intact")
    p = sub.add_parser("play", help="hear a take back")
    p.add_argument("take", type=int)
    dl = sub.add_parser("delete", help="remove every recording, for real")
    dl.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    for r in all_roots():
        _scrub_deletions(r)          # an older version kept a name there (R6)
    why = home.problem()
    if why:
        # The drive is away (or not yet known): recordings must not go
        # anywhere else. Status and delete still look everywhere they can.
        _tell(why[0].upper() + why[1:] + ".")
        if a.cmd == "start":
            return 2
    need_name = ("Please say whose voice this is, by name: "
                 "--who \"Your Name\". Nothing was done.")
    if a.cmd == "start":
        if not (a.who or "").strip():
            _tell(need_name)
            return 2
        return start(a.who, a.phrases)
    if a.cmd == "status":
        return status(a.who)
    if a.cmd == "play":
        if not (a.who or "").strip():
            _tell(need_name)
            return 2
        try:
            d = person_dir(a.who)
        except Refused as exc:
            _tell(str(exc))
            return 2
        f = d / f"take-{a.take:03d}.wav"
        try:
            ok = stat.S_ISREG(os.lstat(f).st_mode) and not _is_link(d)
        except OSError:
            ok = False
        if not ok:
            print(f"  No take {a.take}.")
            return 1
        play(f)
        return 0
    if a.cmd == "delete":
        if a.yes:
            _tell("Deleting a voice always needs the person at the keyboard to type "
                  "the name; --yes is no longer accepted. Nothing was deleted.")
            return 2
        if not (a.who or "").strip():
            _tell(need_name)
            return 2
        return delete(a.who)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
