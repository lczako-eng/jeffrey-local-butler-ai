#!/usr/bin/env python3
"""
voice_enrol.py — record your own voice, for your own Self-Cloud.
================================================================

This is the ENROLMENT half of "the conscience speaks in your voice": you,
present, reading phrases aloud into your own machine. It records; it does not
clone, synthesise or play anything as you. That half comes later and is a
separate decision.

The safeguards from FOUNDER_DIRECTIONS §1 are in the code, not just the docs:

  1. The recordings live ONLY under ~/.selfcloud/voice/. Nothing here imports
     anything that can talk to a network. Nothing is uploaded, ever.
  2. THE PERSON MUST BE PRESENT. This refuses to run without an interactive
     terminal — a script, a cron job or a model cannot drive it.
  3. CONSENT IS THE FIRST TAKE, IN THE PERSON'S OWN VOICE: "I am ___, it is
     ___, and I am recording my own voice for my own Self-Cloud, to be used
     only as I direct." That recording is kept with the rest, so the consent
     is not a checkbox somewhere — it is audible.
  4. Every take is checksummed, logged and made read-only. The manifest is
     the audit.
  5. `delete` is one action and it is REAL deletion: each file is overwritten
     before it is unlinked, and the manifest goes with it.

    python tools/voice_enrol.py start              # record (resumable)
    python tools/voice_enrol.py status
    python tools/voice_enrol.py play 7             # hear a take back
    python tools/voice_enrol.py delete             # gone, for real

Install on the Mac (once):   pip install sounddevice numpy

About ten minutes of clean speech is plenty for the models that exist today;
the phrase sheet is ~55 short lines and you can stop whenever you like and
carry on tomorrow. Read naturally. It's you it's learning, not an announcer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "connector"))
import home  # noqa: E402

VOICE_ROOT = home.voice_path()          # on the drive, if one is plugged in
RATE = 48000          # capture high; anything downstream can resample
MIN_SECONDS = 0.6     # shorter than this is a mis-press, not a phrase

# ---------------------------------------------------------------- phrases
#
# Short, natural, and phonetically varied — numbers, names, questions, a bit
# of feeling. The first is not on the list: it is the consent sentence, built
# from the person's own name and today's date.
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


# ---------------------------------------------------------------- helpers
def person_dir(who: str) -> Path:
    slug = "".join(c if c.isalnum() else "-" for c in who.strip().lower()).strip("-")
    if not slug:
        raise SystemExit("Who is this? Give --who a name.")
    d = VOICE_ROOT / slug
    # Belt and braces: never let a name walk out of the voice folder.
    if not d.resolve().is_relative_to(VOICE_ROOT.resolve()):
        raise SystemExit("That name is not allowed.")
    return d


def load_manifest(d: Path) -> dict:
    m = d / "manifest.json"
    return json.loads(m.read_text()) if m.exists() else {}


def save_manifest(d: Path, man: dict) -> None:
    (d / "manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def write_wav(path: Path, samples, rate: int) -> None:
    """16-bit mono PCM via the standard library. No codec, no dependency."""
    import numpy as np
    pcm = np.clip(np.asarray(samples, dtype="float32"), -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def level(samples) -> tuple[float, float]:
    """RMS and peak, both 0..1 — enough to say 'too quiet' or 'clipping'."""
    import numpy as np
    a = np.asarray(samples, dtype="float32")
    if a.size == 0:
        return 0.0, 0.0
    return float(np.sqrt(np.mean(a * a))), float(np.max(np.abs(a)))


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


# ---------------------------------------------------------------- session
def start(who: str, limit: int, recorder=record_until_enter, quiet: bool = False) -> int:
    if not sys.stdin.isatty() and recorder is record_until_enter:
        # Structural, not polite: a person must be here. A script, a cron job
        # or a model cannot enrol a voice.
        print("\n  Voice enrolment needs a person at a keyboard. Refusing.\n",
              file=sys.stderr)
        return 2

    d = person_dir(who)
    d.mkdir(parents=True, exist_ok=True)
    man = load_manifest(d)
    fresh = not man
    if fresh:
        man = {
            "person": who.strip(),
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "machine": platform.node(),
            "rate": RATE,
            "consent": None,
            "takes": [],
            "rule": ("Recordings of a living person, made by that person, present "
                     "and consenting. They live only here. Nothing plays or "
                     "synthesises this voice yet — that is a separate decision "
                     "the owner makes later, with the safeguards in "
                     "FOUNDER_DIRECTIONS §1."),
        }

    say = (lambda *a, **k: None) if quiet else print
    say(f"\n  Recording {who}'s voice into {d}")
    say("  Nothing here leaves this machine. Read naturally. Press return to")
    say("  start each one and return again to stop. Type q at any prompt to quit.\n")

    done_phrases = {t["phrase"] for t in man["takes"]}
    n = len(man["takes"])

    def take(text: str, tag: str) -> str:
        """Record one phrase; return 'kept', 'skipped' or 'quit'."""
        nonlocal n
        while True:
            say(f"\n  ┌ {tag}")
            for line in text.split("\n"):
                say(f"  │  {line}")
            say("  └ return = start recording · s = skip · q = quit")
            if recorder is record_until_enter:
                ans = input("  > ").strip().lower()
                if ans == "q":
                    return "quit"
                if ans == "s":
                    return "skipped"
                say("  ● recording — press return when you've finished")
            samples = recorder(RATE)
            secs = len(samples) / RATE
            rms, peak = level(samples)
            if secs < MIN_SECONDS:
                say(f"  that was {secs:.1f}s — too short to be a phrase; try again")
                continue
            note = ""
            if rms < 0.01:
                note = "  (very quiet — closer to the mic, or check the input)"
            elif peak > 0.99:
                note = "  (clipping — a little further from the mic)"
            say(f"  {secs:.1f}s, level {rms:.3f}{note}")
            if recorder is record_until_enter:
                ans = input("  return = keep · r = redo · s = skip · q = quit > ").strip().lower()
                if ans == "r":
                    continue
                if ans == "s":
                    return "skipped"
                if ans == "q":
                    return "quit"
            n += 1
            fname = f"take-{n:03d}.wav"
            path = d / fname
            write_wav(path, samples, RATE)
            entry = {"n": n, "tag": tag, "phrase": text, "file": fname,
                     "seconds": round(secs, 2), "rms": round(rms, 4),
                     "sha256": sha256(path),
                     "recorded_at": dt.datetime.now().isoformat(timespec="seconds")}
            man["takes"].append(entry)
            try:
                path.chmod(0o444)          # an original: read-only from now on
            except OSError:
                pass
            save_manifest(d, man)          # after EVERY take: quitting loses nothing
            return "kept"

    # 1. Consent, first and always, in the person's own voice.
    if not man.get("consent"):
        today = dt.date.today().strftime("%B %-d, %Y")
        consent = (f"I am {who.strip()}. It is {today}. I am recording my own "
                   f"voice, for my own Self-Cloud, to be used only as I direct.")
        r = take(consent, "CONSENT — read this exactly")
        if r != "kept":
            say("\n  No consent recording, so nothing else is recorded. "
                "Nothing has been kept.\n")
            if fresh:
                shutil.rmtree(d, ignore_errors=True)
            return 1
        man["consent"] = man["takes"][-1]["file"]
        save_manifest(d, man)

    # 2. The phrases, resumable.
    todo = [p for p in PHRASES if p not in done_phrases][:max(0, limit)]
    for i, phrase in enumerate(todo, 1):
        r = take(phrase, f"{len(done_phrases) + i} of {len(PHRASES)}")
        if r == "quit":
            break
    else:
        # 3. In their own words — only once the sheet is done.
        for prompt in OPEN:
            if prompt in done_phrases:
                continue
            if take(prompt, "IN YOUR OWN WORDS") == "quit":
                break

    total = sum(t["seconds"] for t in man["takes"])
    say(f"\n  {len(man['takes'])} takes, {total / 60:.1f} minutes of your voice, "
        f"in {d}")
    say("  Run this again any time to carry on. `status` shows where you are.\n")
    return 0


def status(who: str) -> int:
    d = person_dir(who)
    man = load_manifest(d)
    if not man:
        print(f"\n  Nothing recorded yet for {who}. Run `start`.\n")
        return 0
    total = sum(t["seconds"] for t in man["takes"])
    phrases_done = sum(1 for t in man["takes"] if t["phrase"] in PHRASES)
    own = sum(1 for t in man["takes"] if t["phrase"] in OPEN)
    ok = sum(1 for t in man["takes"] if (d / t["file"]).exists()
             and sha256(d / t["file"]) == t["sha256"])
    print(f"\n  {man['person']} — {len(man['takes'])} takes, {total / 60:.1f} min")
    print(f"  consent    {'recorded (' + man['consent'] + ')' if man.get('consent') else 'MISSING'}")
    print(f"  phrases    {phrases_done} of {len(PHRASES)}")
    print(f"  own words  {own} of {len(OPEN)}")
    print(f"  integrity  {ok} of {len(man['takes'])} files match their checksum")
    print(f"  where      {d}")
    print(f"\n  {man['rule']}\n")
    return 0


def delete(who: str, force: bool = False) -> int:
    """Real deletion. Overwrite, then unlink, then remove the folder."""
    d = person_dir(who)
    if not d.exists():
        print(f"\n  There is nothing recorded for {who}.\n")
        return 0
    if not force:
        if not sys.stdin.isatty():
            print("  Deleting a voice needs a person to confirm. Refusing.",
                  file=sys.stderr)
            return 2
        ans = input(f"\n  Delete every recording of {who}'s voice, permanently? "
                    f"Type the name to confirm: ").strip()
        if ans.lower() != who.strip().lower():
            print("  Not deleted.\n")
            return 1
    for p in sorted(d.rglob("*")):
        if p.is_file():
            try:
                p.chmod(0o600)
                size = p.stat().st_size
                with open(p, "r+b") as fh:
                    fh.write(os.urandom(min(size, 1 << 26)))
                    fh.flush()
                    os.fsync(fh.fileno())
            except OSError:
                pass
            p.unlink(missing_ok=True)
    shutil.rmtree(d, ignore_errors=True)
    print(f"\n  Gone. Every file overwritten and removed, manifest included.\n")
    return 0


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    """Everything except the microphone, which is swapped for a tone."""
    import tempfile
    import numpy as np
    global VOICE_ROOT
    td = Path(tempfile.mkdtemp(prefix="voice-selftest-"))
    saved = VOICE_ROOT
    VOICE_ROOT = td / "voice"
    try:
        calls = {"n": 0}

        def fake(rate):
            calls["n"] += 1
            t = np.arange(int(rate * 1.2)) / rate
            return (0.3 * np.sin(2 * np.pi * 220 * t)).astype("float32")

        # a short session: consent + 3 phrases + the 5 open prompts
        rc = start("Test Person", limit=3, recorder=fake, quiet=True)
        assert rc == 0, rc
        d = person_dir("Test Person")
        man = load_manifest(d)
        assert man["consent"] == "take-001.wav", man["consent"]
        assert "I am Test Person" in man["takes"][0]["phrase"]
        assert len(man["takes"]) == 1 + 3 + len(OPEN), len(man["takes"])
        for t in man["takes"]:
            f = d / t["file"]
            assert f.exists() and sha256(f) == t["sha256"], t["file"]
            assert not (f.stat().st_mode & 0o222), "a take is writable"
            with wave.open(str(f)) as w:
                assert w.getnchannels() == 1 and w.getframerate() == RATE
                assert w.getsampwidth() == 2

        # resumable: a second run records only what is missing
        before = len(man["takes"])
        rc = start("Test Person", limit=2, recorder=fake, quiet=True)
        man = load_manifest(d)
        assert len(man["takes"]) == before + 2, len(man["takes"])
        assert man["consent"] == "take-001.wav", "consent was re-recorded"
        assert len({t["phrase"] for t in man["takes"]}) == len(man["takes"]), "a phrase repeated"

        # everything lives under the voice root and nowhere else
        assert d.resolve().is_relative_to(VOICE_ROOT.resolve())
        # a hostile name is either refused outright or lands INSIDE the folder
        for hostile in ("../../etc", "/etc/passwd", "..", "a/b/../../../c", "   "):
            try:
                hd = person_dir(hostile)
            except SystemExit:
                continue                      # refused: fine
            assert hd.resolve().is_relative_to(VOICE_ROOT.resolve()), hostile
            assert hd.parent.resolve() == VOICE_ROOT.resolve(), hostile

        # too short is refused and retried, not kept
        def short_first():
            yield np.zeros(int(RATE * 0.2), dtype="float32")   # a mis-press
            while True:
                yield fake(RATE)
        feed = short_first()
        rc = start("Second Person", limit=0, recorder=lambda r: next(feed),
                   quiet=True)
        m2 = load_manifest(person_dir("Second Person"))
        assert m2["takes"], "nothing kept"
        assert all(t["seconds"] >= MIN_SECONDS for t in m2["takes"]), \
            "a too-short take was kept"
        # limit=0 means no sheet phrases this sitting; consent + own words only
        assert m2["consent"] and len(m2["takes"]) == 1 + len(OPEN), len(m2["takes"])

        # real deletion: files gone, folder gone
        files = [d / t["file"] for t in man["takes"]]
        assert delete("Test Person", force=True) == 0
        assert not d.exists() and not any(f.exists() for f in files)

        # nothing here can reach a network
        import ast
        src = Path(__file__).read_text()
        names = {n.names[0].name.split(".")[0] for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Import)}
        names |= {n.module.split(".")[0] for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.ImportFrom) and n.module}
        for bad in ("socket", "urllib", "http", "requests", "ssl"):
            assert bad not in names, f"{bad} imported"

        print("\n  ✓ voice enrolment: consent recorded first and kept, takes are")
        print("    checksummed WAVs made read-only, resumable without repeating,")
        print("    names cannot escape the voice folder, too-short takes are")
        print("    retried, deletion is real, and nothing here can reach a network.\n")
        return 0
    finally:
        VOICE_ROOT = saved
        for p in td.rglob("*"):
            if p.is_file():
                try:
                    p.chmod(0o644)
                except OSError:
                    pass
        shutil.rmtree(td, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--who", default=getpass.getuser(),
                    help="whose voice (a name; default: your login name)")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("start", help="record, or carry on recording")
    s.add_argument("--phrases", type=int, default=len(PHRASES),
                   help="how many phrases this sitting (default: all remaining)")
    sub.add_parser("status", help="how much is recorded, and is it intact")
    p = sub.add_parser("play", help="hear a take back")
    p.add_argument("take", type=int)
    dl = sub.add_parser("delete", help="remove every recording, for real")
    dl.add_argument("--yes", action="store_true", help="skip the confirmation")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if a.cmd == "start":
        return start(a.who, a.phrases)
    if a.cmd == "status":
        return status(a.who)
    if a.cmd == "play":
        d = person_dir(a.who)
        f = d / f"take-{a.take:03d}.wav"
        if not f.exists():
            print(f"  No take {a.take}.")
            return 1
        play(f)
        return 0
    if a.cmd == "delete":
        return delete(a.who, force=a.yes)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
