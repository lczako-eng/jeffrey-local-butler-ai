"""
Regression tests for voice consent and deletion (October 2026 stress test:
I-54, I-56, and the voice half of I-55). Each test is one of the stress
test's own reproductions (voice#0, voice#3, voice#4, family#11, house#9) and
failed on the old tools/voice_enrol.py or the old launcher.

Standard-library unittest. Every test works in its own temporary folder;
tests that need a drive and a home folder at once run in a child process
whose HOME is a temporary folder too. Nothing here touches the real home.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "connector"))
sys.path.insert(0, str(REPO / "tools"))

import numpy as np                     # noqa: E402
import voice_enrol as ve               # noqa: E402

PY = sys.executable
RATE = ve.RATE


# ---------------------------------------------------------------- helpers
def speech(hz: float = 220.0, seconds: float = 4.5):
    """A stand-in for a person speaking: a voice-pitched tone in syllables."""
    t = np.arange(int(RATE * seconds)) / RATE
    syll = ((t % 0.35) < 0.25) & (t > 0.3)
    return (0.3 * np.sin(2 * np.pi * hz * t) * syll).astype("float32")


def mic(hz: float = 220.0):
    return lambda rate: speech(hz)


def answers(**by_word):
    """Scripted answers: the reply for the first keyword found in the prompt."""
    def ask(prompt):
        for word, reply in by_word.items():
            if word.replace("_", " ") in prompt:
                return reply
        return ""
    return ask


YES = answers(yourself="yes")


@contextlib.contextmanager
def captured():
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def text_of(buffers) -> str:
    """What was printed, with line wrapping undone, so a phrase can be found
    wherever the lines happened to break."""
    return " ".join("".join(b.getvalue() for b in buffers).split())


def mode(p: Path) -> int:
    return os.lstat(p).st_mode & 0o777


def child_env(tmp: Path, **extra) -> dict:
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ)
    for k in ("SELFCLOUD_ROOT", "SELFCLOUD_VOICE", "JEFFEREY_OWNER_CONSOLE",
              "JEFFEREY_CLIENT"):
        env.pop(k, None)
    env.update(HOME=str(home), JEFFEREY_CONSCIENCE_PATH=str(tmp / "conscience.json"),
               JEFFEREY_EGRESS=str(tmp / "egress.jsonl"),
               JEFFEREY_DOOR=str(tmp / "door-shut"),
               SELFCLOUD_INDEX=str(tmp / "photo-index"),
               SELFCLOUD_DISCS=str(tmp / "discs"), PYTHONDONTWRITEBYTECODE="1")
    for k, v in extra.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


# A child process that records or deletes the way the stress test did. It
# only uses what the old module had too, so it ran (and failed) against it.
CHILD = textwrap.dedent("""
    import sys
    sys.path.insert(0, %r)
    import numpy as np
    import voice_enrol as ve
    ve._SELFTEST = True
    def speech(rate):
        t = np.arange(int(rate * 4.5)) / rate
        syll = ((t %% 0.35) < 0.25) & (t > 0.3)
        return (0.3 * np.sin(2 * np.pi * 220 * t) * syll).astype("float32")
    if sys.argv[1] == "record":
        rc = ve.start("Erin", 2, recorder=speech, quiet=True)
    else:
        rc = ve.delete("Erin", force=True)
    print("RC", rc)
    print("ROOT", ve.VOICE_ROOT)
""") % str(REPO / "tools")


class VoiceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-voice-"))
        self.root = self.tmp / "voice"
        self._mode = ve.selftest_mode(self.root, roots=[self.root])
        self._mode.__enter__()

    def tearDown(self):
        self._mode.__exit__(None, None, None)
        for p in self.tmp.rglob("*"):
            with contextlib.suppress(OSError):
                if p.is_symlink():
                    continue
                p.chmod(0o700 if p.is_dir() else 0o600)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def enrol(self, who="Laszlo", limit=2, recorder=None, **kw):
        with captured() as bufs:
            rc = ve.start(who, limit, recorder=recorder or mic(), quiet=True, **kw)
        self.last = text_of(bufs)
        return rc

    def manifest(self, who="Laszlo") -> dict:
        return json.loads((ve.person_dir(who) / "manifest.json").read_text())

    def wavs(self, who="Laszlo") -> list[Path]:
        return sorted(ve.person_dir(who).glob("take-*.wav"))

    def delete(self, who="Laszlo", force=True):
        with captured() as bufs:
            rc = ve.delete(who, force=force)
        self.last = text_of(bufs)
        return rc

    def status(self, who="Laszlo"):
        with captured() as bufs:
            rc = ve.status(who)
        self.last = text_of(bufs)
        return rc


# ---------------------------------------------------------- I-54: consent
class ConsentIsReal(VoiceCase):
    def test_silent_consent_is_refused_and_nothing_is_kept(self):
        # voice#0 / voice-10: one second of silence was kept as the consent.
        rc = self.enrol(recorder=lambda r: np.zeros(RATE, dtype="float32"))
        self.assertNotEqual(rc, 0)
        self.assertFalse(ve.person_dir("Laszlo").exists())

    def test_a_steady_tone_is_not_someone_agreeing(self):
        t = np.arange(RATE * 6) / RATE
        steady = (0.3 * np.sin(2 * np.pi * 220 * t)).astype("float32")
        self.assertNotEqual(self.enrol(recorder=lambda r: steady), 0)
        self.assertFalse(ve.person_dir("Laszlo").exists())

    def test_silent_phrase_takes_are_not_kept(self):
        feed = iter([speech()] + [np.zeros(RATE * 2, dtype="float32")] * 50)
        self.enrol(recorder=lambda r: next(feed))
        man = self.manifest()
        self.assertEqual(len(man["takes"]), 1, "a silent take was kept")
        self.assertTrue(all(t["rms"] > 0.01 for t in man["takes"]))

    def test_every_sitting_has_its_own_spoken_words(self):
        self.assertEqual(self.enrol(), 0)
        self.assertEqual(self.enrol(ask=YES), 0)
        man = self.manifest()
        self.assertEqual(len(man["consents"]), 2)
        chal = [c["challenge"] for c in man["consents"]]
        self.assertNotEqual(chal[0], chal[1])
        by_file = {t["file"]: t for t in man["takes"]}
        for c in man["consents"]:
            words = c["challenge"].split()
            self.assertEqual(len(words), 3)
            sentence = by_file[c["file"]]["phrase"]
            self.assertTrue(sentence.startswith("I am Laszlo. It is "))
            for w in words:
                self.assertIn(w, sentence)
        # the second sitting's phrases were recorded under the second consent
        second = man["consents"][1]["file"]
        after = man["takes"][[t["file"] for t in man["takes"]].index(second) + 1:]
        self.assertTrue(after and all(t.get("consent") == second for t in after))

    def test_missing_consent_shows_missing_and_must_be_said_again(self):
        # voice#0 / voice-39: take-001 deleted, recording carried on and
        # status still said "consent recorded (take-001.wav)".
        self.assertEqual(self.enrol(), 0)
        d = ve.person_dir("Laszlo")
        os.unlink(d / "take-001.wav")
        self.status()
        self.assertIn("MISSING", self.last)
        self.assertNotIn("recorded on", self.last)
        before = len(self.manifest()["takes"])
        self.assertEqual(self.enrol(ask=YES), 0)
        man = self.manifest()
        first_new = man["takes"][before]
        self.assertEqual(first_new.get("kind"), "consent",
                         "recording resumed without a new consent")
        self.assertEqual(man["consent"], "take-001.wav", "history was rewritten")
        self.status()
        self.assertIn("recorded on", self.last)

    def test_a_changed_consent_recording_no_longer_counts(self):
        self.assertEqual(self.enrol(), 0)
        f = ve.person_dir("Laszlo") / "take-001.wav"
        os.chmod(f, 0o600)
        with open(f, "r+b") as fh:
            fh.seek(100)
            fh.write(b"\x7f" * 64)
        self.status()
        self.assertIn("has been changed", self.last)
        self.assertNotIn("recorded on", self.last)


# ------------------------------------------------------------ I-54: names
class ANameIsRequired(VoiceCase):
    def test_a_blank_name_is_refused(self):
        for blank in ("", "   "):
            self.assertEqual(self.enrol(who=blank), 2, repr(blank))
        self.assertFalse(self.root.exists() and any(self.root.iterdir()))

    def test_the_consent_sentence_takes_only_a_name(self):
        # voice#0 / voice-42: --who text went word for word into the consent.
        for bad in ("Bob. I do not consent to any of this", "Laszlo123",
                    "Laszlo; rm -rf"):
            self.assertEqual(self.enrol(who=bad), 2, bad)
        self.assertFalse(self.root.exists() and any(self.root.iterdir()))
        self.assertEqual(self.enrol(who="László Czakó"), 0)
        first = self.manifest("László Czakó")["takes"][0]["phrase"]
        self.assertTrue(first.startswith("I am László Czakó. It is "))

    def test_the_launcher_never_uses_the_mac_account_name(self):
        # family#11: `[ -z "$WHO" ] && WHO=$(id -un)` put whoever pressed
        # return into the account owner's recordings.
        home = self.tmp / "home"
        venv = home / ".jefferey" / "venv" / "bin"
        venv.mkdir(parents=True)
        log = self.tmp / "calls.txt"
        fake = venv / "python"
        fake.write_text('#!/bin/bash\nif [ "$1" = "-c" ]; then exit 0; fi\n'
                        'printf "%s|" "$@" >> "$CALLS"; echo >> "$CALLS"\n')
        fake.chmod(0o755)
        env = child_env(self.tmp, CALLS=str(log))

        def run(typed: str):
            return subprocess.run(["bash", str(REPO / "Record my voice.command")],
                                  input=typed, env=env, capture_output=True,
                                  text=True, timeout=60)

        p = run("\n  \n\n\n\n")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("No name was typed", p.stdout)
        self.assertFalse(log.exists() and "start" in log.read_text(),
                         "the launcher started a recording with no name typed")
        p = run("  Laszlo Czako \n\n")
        self.assertIn("tools/voice_enrol.py|--who|Laszlo Czako|start|", log.read_text())


# --------------------------------------------------------- I-54: identity
class OnePersonPerFolder(VoiceCase):
    def test_a_second_voice_cannot_carry_on_by_pressing_return(self):
        # family#11: start('laszlo', 110 Hz) then start('Laszlo', 330 Hz):
        # same folder, no new consent, takes 8 -> 10.
        self.assertEqual(self.enrol("laszlo", recorder=mic(110)), 0)
        before = self.manifest("laszlo")
        rc = self.enrol("Laszlo", recorder=mic(330))
        self.assertNotEqual(rc, 0)
        after = self.manifest("laszlo")
        self.assertEqual(after["takes"], before["takes"])
        self.assertEqual(len(self.wavs("laszlo")), len(before["takes"]))

    def test_a_different_sounding_voice_must_say_it_is_them(self):
        self.assertEqual(self.enrol("laszlo", recorder=mic(110)), 0)
        n = len(self.manifest("laszlo")["takes"])
        # says "yes, I am Laszlo" but the voice is clearly different: stopped,
        # and the new recording is not left behind
        self.assertEqual(self.enrol("Laszlo", recorder=mic(330), ask=YES), 1)
        self.assertEqual(len(self.manifest("laszlo")["takes"]), n)
        self.assertEqual(len(self.wavs("laszlo")), n)
        # if they insist it is them, it is kept and written down
        ask = answers(yourself="yes", it_is_me="it is me")
        self.assertEqual(self.enrol("Laszlo", recorder=mic(330), ask=ask), 0)
        last = self.manifest("laszlo")["consents"][-1]
        self.assertTrue(last["voice_differs"])
        self.status("laszlo")
        self.assertIn("sounded different", self.last)
        # the same voice as before carries on without that question
        self.assertEqual(self.enrol("Laszlo", recorder=mic(110), ask=YES), 0)
        self.assertFalse(self.manifest("laszlo")["consents"][-1]["voice_differs"])

    def test_look_alike_names_never_share_a_folder(self):
        # voice-08: Mary-Ann and Mary Ann landed in one folder.
        self.assertEqual(self.enrol("Mary-Ann", recorder=mic(200)), 0)
        before = self.manifest("Mary-Ann")
        self.assertNotEqual(self.enrol("Mary Ann", recorder=mic(300), ask=YES), 0)
        after = self.manifest("Mary-Ann")
        self.assertEqual(after, before)
        self.assertIn("Mary-Ann", self.last)

    def test_a_fake_microphone_is_refused_outside_the_selftest(self):
        # house#9: any caller could pass pre-recorded audio as "present".
        ve._SELFTEST = False
        try:
            self.assertEqual(self.enrol(), 2)
        finally:
            ve._SELFTEST = True
        self.assertFalse(self.root.exists())
        outside = REPO / ".voice-never-created"
        try:
            with ve.selftest_mode(outside, roots=[outside]):
                self.assertEqual(self.enrol(), 2)
            self.assertFalse(outside.exists())
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_two_windows_at_once_do_not_collide(self):
        self.assertEqual(self.enrol(), 0)
        d = ve.person_dir("Laszlo")
        n = len(self.manifest()["takes"])
        with ve._lock(d) as got:
            self.assertTrue(got)
            self.assertEqual(self.enrol(ask=YES), 1)
        self.assertIn("Another window", self.last)
        self.assertEqual(len(self.manifest()["takes"]), n)


# ------------------------------------------------- I-54: modes, old data
class OwnerOnlyAndOldDataKept(VoiceCase):
    def test_recordings_are_readable_by_their_owner_only(self):
        # house#9 / voice-26: voice/ 0755, manifest 0644, takes 0444.
        self.assertEqual(self.enrol(), 0)
        d = ve.person_dir("Laszlo")
        self.assertEqual(mode(self.root), 0o700)
        self.assertEqual(mode(d), 0o700)
        self.assertEqual(mode(d / "manifest.json"), 0o600)
        for w in self.wavs():
            self.assertEqual(mode(w), 0o400, w.name)

    def _old_enrolment(self, consent_audio):
        """An enrolment exactly as the first version left it."""
        d = self.root / "laszlo"
        d.mkdir(parents=True)
        os.chmod(self.root, 0o755)
        os.chmod(d, 0o755)
        takes = []
        for i, (text, audio) in enumerate(
                [("I am laszlo. It is September 16, 2026. I am recording my own "
                  "voice, for my own Self-Cloud, to be used only as I direct.",
                  consent_audio)] + [(p, speech()) for p in ve.PHRASES[:2]], 1):
            f = d / f"take-{i:03d}.wav"
            with wave.open(str(f), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
            f.chmod(0o444)
            takes.append({"n": i, "tag": "x", "phrase": text, "file": f.name,
                          "seconds": round(len(audio) / RATE, 2), "rms": 0.2,
                          "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                          "recorded_at": "2026-09-16T10:00:00"})
        man = {"person": "laszlo", "created": "2026-09-16T10:00:00",
               "machine": "old-mac", "rate": RATE, "consent": "take-001.wav",
               "takes": takes, "rule": "the old rule"}
        (d / "manifest.json").write_text(json.dumps(man, indent=2))
        os.chmod(d / "manifest.json", 0o644)
        return d, man

    def test_an_old_enrolment_keeps_working_and_is_brought_up_to_date(self):
        d, old = self._old_enrolment(speech())
        before = {n: mode(d / n) for n in ("take-001.wav", "manifest.json")}
        self.assertEqual(self.status("laszlo"), 0)
        self.assertIn("recorded on September 16, 2026 (take-001.wav)", self.last)
        # Integration: 'status' only reads — it changed modes before, even of
        # a hard-linked file that was not a recording (verify, voice). The
        # next sitting brings the folder up to owner-only modes instead.
        self.assertEqual({n: mode(d / n) for n in before}, before)
        self.assertEqual(self.enrol("laszlo", ask=YES), 0)
        self.assertEqual(mode(d), 0o700)
        self.assertEqual(mode(d / "take-001.wav"), 0o400)
        self.assertEqual(mode(d / "manifest.json"), 0o600)
        man = self.manifest("laszlo")
        self.assertEqual(man["takes"][:3], [dict(t, **extra) for t, extra in zip(
            old["takes"], [{"kind": "consent"}, {"consent": "take-001.wav"},
                           {"consent": "take-001.wav"}])])
        self.assertEqual(man["consent"], "take-001.wav")
        self.assertEqual(man["consents"][0]["file"], "take-001.wav")
        self.assertEqual(len(man["consents"]), 2)
        self.assertEqual(man["rule"], "the old rule")
        self.assertEqual(man["version"], 2)

    def test_an_old_silent_consent_is_called_out(self):
        self._old_enrolment(np.zeros(RATE, dtype="float32"))
        self.status("laszlo")
        self.assertIn("SILENT", self.last)

    def test_a_damaged_list_is_never_overwritten(self):
        d = self.root / "laszlo"
        d.mkdir(parents=True)
        (d / "take-001.wav").write_bytes(b"RIFF....")
        (d / "manifest.json").write_text("{not json")
        self.assertEqual(self.enrol("laszlo"), 2)
        self.assertEqual((d / "manifest.json").read_text(), "{not json")
        self.assertIn("damaged", self.last)


# ------------------------------------------- I-55 (voice): never follow links
class NeverThroughAShortcut(VoiceCase):
    def outside(self, name="tax_return_2025.pdf", body=b"%PDF the owner's tax return"):
        o = self.tmp / "outside"
        o.mkdir(exist_ok=True)
        f = o / name
        f.write_bytes(body)
        f.chmod(0o444)
        return f, body

    def test_delete_does_not_follow_a_link_inside_the_folder(self):
        # voice#3 / voice-31: a link take-099.wav -> tax_return_2025.pdf was
        # overwritten with random bytes and set to 0600.
        self.assertEqual(self.enrol("Carol"), 0)
        target, body = self.outside()
        d = ve.person_dir("Carol")
        os.symlink(target, d / "take-099.wav")
        # Changed by verify I-56: this said 'Gone.' with rc 0, although what
        # the shortcut pointed to may be a copy of the voice and was left.
        self.assertEqual(self.delete("Carol"), 1)
        self.assertEqual(target.read_bytes(), body)
        self.assertEqual(mode(target), 0o444)
        self.assertFalse(os.path.lexists(d))
        self.assertIn("without being followed", self.last)
        self.assertIn("it is still there", self.last)
        self.assertNotIn("Gone.", self.last)

    def test_delete_does_not_follow_a_linked_person_folder(self):
        o = self.tmp / "elsewhere"
        o.mkdir()
        (o / "letter.txt").write_text("to the kids")
        self.root.mkdir()
        os.symlink(o, self.root / "carol")
        self.assertEqual(self.delete("Carol"), 1)
        self.assertEqual((o / "letter.txt").read_text(), "to the kids")
        self.assertIn("shortcut", self.last)
        self.assertNotIn("Gone.", self.last)

    def test_recording_never_writes_through_a_link_at_the_next_take_name(self):
        # voice#3 / voice-32: a link at the next take name was overwritten
        # with WAV data and made 0444.
        target, body = self.outside("letter_to_kids.txt", b"Dear kids,")
        d = ve.person_dir("Carol")
        d.mkdir(parents=True)
        os.symlink(target, d / "take-002.wav")
        self.assertEqual(self.enrol("Carol"), 0)
        self.assertEqual(target.read_bytes(), body)
        self.assertEqual(mode(target), 0o444)
        self.assertTrue(os.path.islink(d / "take-002.wav"))
        man = self.manifest("Carol")
        self.assertNotIn("take-002.wav", [t["file"] for t in man["takes"]])
        for t in man["takes"]:
            self.assertTrue(stat.S_ISREG(os.lstat(d / t["file"]).st_mode))

    def test_the_list_of_recordings_is_never_written_through_a_link(self):
        target, body = self.outside("will.txt", b"my will")
        d = ve.person_dir("Carol")
        d.mkdir(parents=True)
        os.symlink(target, d / "manifest.json")
        self.assertEqual(self.enrol("Carol"), 2)
        self.assertEqual(target.read_bytes(), body)
        os.unlink(d / "manifest.json")
        os.symlink(target, d / "manifest.json.tmp")
        self.assertEqual(self.enrol("Carol"), 0)
        self.assertEqual(target.read_bytes(), body)
        self.assertTrue(stat.S_ISREG(os.lstat(d / "manifest.json").st_mode))

    def test_a_hard_linked_outside_file_is_not_scrambled(self):
        self.assertEqual(self.enrol("Carol"), 0)
        target = self.tmp / "notes.txt"
        target.write_text("the owner's notes")
        os.link(target, ve.person_dir("Carol") / "notes.txt")
        self.assertEqual(self.delete("Carol"), 1)
        self.assertEqual(target.read_text(), "the owner's notes")
        self.assertIn("another name", self.last)
        self.assertFalse(ve.person_dir("Carol").exists())


# ----------------------------------------------- I-56: deletion is complete
class DeletionIsComplete(VoiceCase):
    def test_a_long_take_is_overwritten_to_its_full_size(self):
        # voice#4 / voice-33: only the first 64 MiB were overwritten.
        self.assertEqual(self.enrol(), 0)
        d = ve.person_dir("Laszlo")
        size = (64 << 20) + (3 << 20)
        big = d / "take-050.wav"
        big.write_bytes(b"\x5a" * size)
        man = json.loads((d / "manifest.json").read_text())
        man["takes"].append({"n": 50, "tag": "long", "phrase": "a long story",
                             "file": big.name, "seconds": 730, "rms": 0.1,
                             "sha256": hashlib.sha256(big.read_bytes()).hexdigest(),
                             "recorded_at": "2026-10-14T10:00:00"})
        (d / "manifest.json").write_text(json.dumps(man))
        side = self.tmp / "side-copy.wav"
        os.link(big, side)                 # to see what happened to the bytes
        self.assertEqual(self.delete(), 0)
        data = side.read_bytes()
        self.assertEqual(len(data), size)
        block = b"\x5a" * 4096
        left = sum(1 for i in range(0, size, 4096) if data[i:i + 4096] == block)
        self.assertEqual(left, 0, f"{left} blocks of the original survived")

    def test_delete_says_plainly_what_overwriting_cannot_reach(self):
        self.assertEqual(self.enrol(), 0)
        self.assertEqual(self.delete(), 0)
        self.assertIn("Gone.", self.last)
        self.assertIn("flash storage", self.last)
        self.assertIn("Time Machine", self.last)
        self.assertIn("not plugged in now", self.last)

    def test_delete_with_yes_and_no_person_is_refused(self):
        # family#11 / voice-36: `delete --yes </dev/null` -> 'Gone.' rc 0.
        self.assertEqual(self.enrol(), 0)
        d = ve.person_dir("Laszlo")
        env = child_env(self.tmp, SELFCLOUD_VOICE=str(self.root))
        p = subprocess.run([PY, str(REPO / "tools" / "voice_enrol.py"), "--who",
                            "Laszlo", "delete", "--yes"], stdin=subprocess.DEVNULL,
                           env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertTrue((d / "manifest.json").exists())
        self.assertEqual(len(self.wavs()), len(self.manifest()["takes"]))

    def test_forced_delete_is_refused_outside_the_selftest(self):
        self.assertEqual(self.enrol(), 0)
        ve._SELFTEST = False
        try:
            self.assertEqual(self.delete(), 2)
        finally:
            ve._SELFTEST = True
        self.assertTrue((ve.person_dir("Laszlo") / "manifest.json").exists())


class DeletionSearchesEveryPlace(unittest.TestCase):
    """voice#4 / voice-30: recorded once without the drive and once with it;
    delete with the drive in said 'Gone' and left the laptop copy."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-voice-roots-"))
        self.drive = self.tmp / "drive"
        # a real Self-Cloud marker: since I-17 nothing else counts as a drive
        (self.drive / ".selfcloud").mkdir(parents=True)
        (self.drive / ".selfcloud" / "selfcloud.json").write_text(json.dumps(
            {"kind": "self-cloud-drive", "id": "0123456789abcdef", "name": "Self-Cloud"}))
        script = self.tmp / "child.py"
        script.write_text(CHILD)
        self.script = script
        self.laptop = self.tmp / "home" / ".selfcloud" / "voice" / "erin"
        self.on_drive = self.drive / ".selfcloud" / "jefferey" / "voice" / "erin"
        self.run_child("record", SELFCLOUD_ROOT=None)
        self.run_child("record", SELFCLOUD_ROOT=str(self.drive))
        self.assertTrue((self.laptop / "manifest.json").exists())
        self.assertTrue((self.on_drive / "manifest.json").exists())

    def tearDown(self):
        for p in self.tmp.rglob("*"):
            with contextlib.suppress(OSError):
                if not p.is_symlink():
                    p.chmod(0o700 if p.is_dir() else 0o600)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_child(self, what: str, **env):
        p = subprocess.run([PY, str(self.script), what], env=child_env(self.tmp, **env),
                           capture_output=True, text=True, timeout=120)
        self.assertIn("RC 0", p.stdout, p.stdout + p.stderr)
        return " ".join((p.stdout + p.stderr).split())

    def test_delete_with_the_drive_in_also_removes_the_laptop_copy(self):
        out = self.run_child("delete", SELFCLOUD_ROOT=str(self.drive))
        self.assertFalse(self.laptop.exists(), "the laptop copy was left behind")
        self.assertFalse(self.on_drive.exists())
        self.assertIn(str(self.laptop), out)
        self.assertIn(str(self.on_drive), out)
        self.assertIn("Gone.", out)

    def test_the_person_types_the_name_at_a_terminal(self):
        """The real command, at a real (pseudo) terminal, as the owner uses it."""
        import pty  # noqa: F401  (Linux and macOS)
        master, slave = os.openpty()
        env = child_env(self.tmp, SELFCLOUD_ROOT=str(self.drive))
        p = subprocess.Popen([PY, str(REPO / "tools" / "voice_enrol.py"), "--who",
                              "Erin", "delete"], stdin=slave, stdout=slave,
                             stderr=slave, env=env, close_fds=True)
        os.close(slave)
        out = b""
        sent = False
        deadline = time.time() + 60
        try:
            while time.time() < deadline:
                r, _, _ = select.select([master], [], [], 1)
                if r:
                    try:
                        chunk = os.read(master, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    out += chunk
                if not sent and b"Type the name to confirm" in out:
                    os.write(master, b"Erin\n")
                    sent = True
                if p.poll() is not None and not r:
                    break
            p.wait(timeout=30)
        finally:
            os.close(master)
            if p.poll() is None:
                p.kill()
        text = " ".join(out.decode("utf-8", "replace").split())
        self.assertTrue(sent, text)
        self.assertEqual(p.returncode, 0, text)
        self.assertFalse(self.laptop.exists(), "the laptop copy was left behind")
        self.assertFalse(self.on_drive.exists())
        self.assertIn("Gone.", text)
        self.assertIn("flash storage", text)


# ----------------------------------------------------- after the fixes
# The skeptics' and regression hunters' reproductions against the first
# round of fixes (verify I-54, I-55, I-56 and the regressions).
CHILD2 = textwrap.dedent("""
    import os, sys
    sys.path.insert(0, %r)
    import numpy as np
    import voice_enrol as ve
    ve._SELFTEST = True
    def speech(rate):
        t = np.arange(int(rate * 4.5)) / rate
        syll = ((t %% 0.35) < 0.25) & (t > 0.3)
        return (0.3 * np.sin(2 * np.pi * 220 * t) * syll).astype("float32")
    who = os.environ.get("VE_WHO", "Erin")
    if sys.argv[1] == "record":
        rc = ve.start(who, 2, recorder=speech, quiet=True)
    else:
        rc = ve.delete(who, force=True)
    print("RC", rc)
""") % str(REPO / "tools")


def steady_after_silence(hz: float = 110.0, gap: bool = False):
    t = np.arange(RATE * 6) / RATE
    a = (0.3 * np.sin(2 * np.pi * hz * t)).astype("float32")
    a[:RATE] = 0                       # a second of silence first
    if gap:
        a[int(RATE * 3):int(RATE * 4)] = 0
    return a


class AfterTheFixes(VoiceCase):

    def child(self, what: str, **env) -> str:
        script = self.tmp / "child2.py"
        script.write_text(CHILD2)
        p = subprocess.run([PY, str(script), what], env=child_env(self.tmp, **env),
                           capture_output=True, text=True, timeout=120)
        return " ".join((p.stdout + p.stderr).split())

    # ------------------------------------------------------- verify I-54
    def test_a_sentence_never_passes_as_a_name(self):
        for bad in ("Bob. I do not consent", "Nobody. I refuse", "Bob. Not me. Refuse",
                    "Bob I do not consent", "Bob.I refuse", "Je ne consens pas"):
            self.assertEqual(self.enrol(who=bad), 2, bad)
        self.assertFalse(self.root.exists() and any(self.root.iterdir()))
        for good in ("J. R. Smith", "Dr. Ana Silva", "Jean-Luc St.-Pierre",
                     "Mary O'Brien", "László Czakó", "Anh Do"):
            self.assertEqual(ve.clean_name(good), good)

    def test_one_steady_sound_after_a_pause_is_not_someone_agreeing(self):
        for gap in (False, True):
            self.assertNotEqual(self.enrol(recorder=lambda r: steady_after_silence(gap=gap)),
                                0, gap)
            self.assertFalse(ve.person_dir("Laszlo").exists())
        self.assertEqual(self.enrol(), 0)        # syllables still pass

    def test_the_list_never_claims_the_words_were_heard(self):
        self.assertEqual(self.enrol(), 0)
        man = self.manifest()
        self.assertIs(man["consents"][0]["words_checked"], False)
        self.assertIs(man["takes"][0]["words_checked"], False)

    def test_a_voice_a_little_different_must_still_say_it_is_them(self):
        # 150 Hz against 110 Hz (1.36) joined the set on a typed yes
        self.assertEqual(self.enrol("Laszlo", recorder=mic(110)), 0)
        n = len(self.manifest()["takes"])
        self.assertEqual(self.enrol("Laszlo", recorder=mic(150), ask=YES), 1)
        self.assertEqual(len(self.manifest()["takes"]), n)

    def test_the_selftest_gate_does_not_depend_on_where_the_code_is(self):
        # regression: with the checkout under /tmp, a folder inside it counted
        # as 'temporary' and a fake microphone was accepted there
        saved = ve._CODE
        ve._CODE = self.tmp                       # as if JEFFEREY lived here
        try:
            self.assertEqual(self.enrol(), 2)
            self.assertFalse(ve.person_dir("Laszlo").exists())
        finally:
            ve._CODE = saved
        self.assertEqual(self.enrol(), 0)

    # ------------------------------------------------------- verify I-55
    def test_a_shortcut_above_the_voice_folder_is_never_followed(self):
        cloud = self.tmp / "home" / "Library" / "Mobile Documents" / "stash"
        cloud.mkdir(parents=True)
        drive = self.tmp / "drive"
        drive.mkdir()
        os.symlink(cloud, drive / ".selfcloud")
        root = drive / ".selfcloud" / "jefferey" / "voice"
        with ve.selftest_mode(root, roots=[root]):
            self.assertEqual(self.enrol(), 2)
        self.assertIn("shortcut", self.last)
        self.assertEqual(list(cloud.rglob("*")), [], "the voice went into the cloud folder")

    def test_a_shortcut_at_the_macs_own_voice_folder_is_never_followed(self):
        home = self.tmp / "home"
        cloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "stash"
        cloud.mkdir(parents=True)
        os.symlink(cloud, home / ".selfcloud")
        out = self.child("record")
        self.assertIn("RC 2", out)
        self.assertIn("shortcut", out)
        self.assertEqual(list(cloud.rglob("*")), [], "the voice went into iCloud")

    def test_deletion_walks_the_open_folder_not_its_path(self):
        # verify I-55 (4): the folder swapped for a shortcut between the look
        # and the listing sent the deletion to an outside will.txt
        self.assertEqual(self.enrol("Carol"), 0)
        d = ve.person_dir("Carol")
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "will.txt").write_text("my will")
        real_scandir, real_listdir = os.scandir, os.listdir
        swapped = []

        def swap(arg):
            if not swapped and (arg == d or arg == str(d) or isinstance(arg, int)):
                swapped.append(1)
                os.rename(d, self.tmp / "moved")
                os.symlink(outside, d)

        def scandir(arg=".", *a):
            swap(arg)
            return real_scandir(arg, *a)

        def listdir(arg=".", *a):
            swap(arg)
            return real_listdir(arg, *a)
        os.scandir, os.listdir = scandir, listdir
        try:
            self.delete("Carol")
        finally:
            os.scandir, os.listdir = real_scandir, real_listdir
        self.assertTrue(swapped)
        self.assertEqual((outside / "will.txt").read_text(), "my will")

    # ------------------------------------------------------- verify I-56
    def test_a_look_alike_name_never_deletes_someone_elses_set(self):
        self.assertEqual(self.enrol("Mary-Ann", recorder=mic(200)), 0)
        self.assertEqual(self.delete("Mary Ann"), 1)
        self.assertTrue((ve.person_dir("Mary-Ann") / "manifest.json").exists())
        self.assertIn("belong to Mary-Ann", self.last)
        self.assertIn("NOT deleted", self.last)
        self.assertEqual(self.delete("Mary-Ann"), 0)
        self.assertFalse(ve.person_dir("Mary-Ann").exists())

    def test_an_older_set_under_another_name_is_named_after_gone(self):
        # the old launcher recorded under the Mac's account name ('laszlo')
        self.assertEqual(self.enrol("laszlo"), 0)
        self.assertEqual(self.enrol("Laszlo Czako"), 0)
        self.assertEqual(self.delete("Laszlo Czako"), 0)
        self.assertIn("Still kept here", self.last)
        self.assertIn("laszlo — ", self.last)
        self.assertIn("this may be yours too", self.last)
        self.assertTrue(ve.person_dir("laszlo").exists())

    def test_an_old_set_under_the_macs_account_name_can_be_carried_on(self):
        # regression: start refused 'laszlo2', so the voice split in two
        d = self.root / "laszlo2"
        d.mkdir(parents=True)
        take = d / "take-001.wav"
        with wave.open(str(take), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(RATE)
            w.writeframes((speech() * 32767).astype("<i2").tobytes())
        digest = hashlib.sha256(take.read_bytes()).hexdigest()
        (d / "manifest.json").write_text(json.dumps({
            "person": "laszlo2", "consent": "take-001.wav", "rate": RATE,
            "takes": [{"n": 1, "file": "take-001.wav", "phrase": "I consent",
                       "sha256": digest, "seconds": 4.5, "rms": 0.2}]}))
        self.assertEqual(self.enrol("laszlo2", ask=YES), 0, self.last)
        man = json.loads((d / "manifest.json").read_text())
        self.assertEqual(len(man["consents"]), 2)
        self.assertTrue(man["takes"][1]["phrase"].startswith("I am laszlo2. It is "))
        # ...but no NEW set gets a name like that
        self.assertEqual(self.enrol("laszlo3"), 2)

    def test_a_folder_chosen_by_hand_is_remembered_and_deleted_later(self):
        custom = self.tmp / "custom-voice"
        out = self.child("record", SELFCLOUD_VOICE=str(custom))
        self.assertIn("RC 0", out)
        self.assertTrue(list((custom / "erin").glob("take-*.wav")))
        out = self.child("delete", SELFCLOUD_VOICE=None)
        self.assertIn("RC 0", out)
        self.assertFalse((custom / "erin").exists(), "the hand-chosen folder was left")
        self.assertIn(str(custom / "erin"), out)

    def test_a_deletion_is_recorded_without_keeping_the_name(self):
        # R6: the record kept the folder's name ('laszlo', 'erin-kowalski')
        # and a plain sha256 of the name, which anyone can recompute from a
        # guess — after the voice was deleted at the person's request
        self.assertEqual(self.enrol(), 0)
        self.assertEqual(self.delete(), 0)
        text = (self.root / "deletions.jsonl").read_text()
        rec = json.loads(text.splitlines()[-1])
        self.assertEqual(sorted(rec), ["complete", "deleted_on", "deletion",
                                       "files_overwritten"])
        self.assertTrue(rec["complete"])
        self.assertGreater(rec["files_overwritten"], 0)
        self.assertEqual(rec["deleted_on"], dt.date.today().isoformat())
        self.assertNotIn("aszlo", text.lower())
        for name in ("laszlo", "Laszlo"):
            self.assertNotIn(hashlib.sha256(name.encode()).hexdigest(), text)
        self.assertEqual(mode(self.root / "deletions.jsonl"), 0o600)
        # two deletions are two different records, never linked by a name
        self.assertEqual(self.enrol("Erin Kowalski"), 0, self.last)
        self.assertEqual(self.delete("Erin Kowalski"), 0, self.last)
        lines = (self.root / "deletions.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertNotEqual(json.loads(lines[0])["deletion"], json.loads(lines[1])["deletion"])
        self.assertNotIn("erin", "\n".join(lines).lower())
        self.assertNotIn("kowalski", "\n".join(lines).lower())

    def test_an_older_record_that_kept_a_name_is_cleaned(self):
        # R6: what the earlier version wrote is cleaned the next time a voice
        # is deleted or looked at — the deletion is still recorded
        self.root.mkdir(parents=True, exist_ok=True)
        old = self.root / "deletions.jsonl"
        old.write_text(json.dumps({
            "deleted_at": "2026-10-12T09:14:03", "folder": "erin-kowalski",
            "name_fingerprint": hashlib.sha256(b"erin kowalski").hexdigest(),
            "files_overwritten": 9, "complete": True}) + "\n" + "{torn line erin\n")
        os.chmod(old, 0o600)
        self.status("Nobody")
        text = old.read_text()
        self.assertNotIn("erin", text.lower())
        self.assertNotIn(hashlib.sha256(b"erin kowalski").hexdigest(), text)
        rec = json.loads(text.splitlines()[0])
        self.assertEqual(rec["deleted_on"], "2026-10-12")
        self.assertEqual((rec["files_overwritten"], rec["complete"]), (9, True))
        self.assertEqual(len(text.splitlines()), 1)
        self.assertEqual(mode(old), 0o600)


if __name__ == "__main__":
    unittest.main()
