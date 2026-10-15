"""
answers.py — what a person typed, read the way they meant it.
=============================================================

Every question JEFFEREY asks at the owner's own keyboard goes through here,
so the same words mean the same thing everywhere, in English and in French.
Before October 2026 each prompt matched one letter: typing "shut" in 'What
left the house' paged the log and left the door open, and "no" renamed a
drive (I-60). Now:

  * an answer is read in lower case, without accents, by its first word
    ("Shut the door" is "shut", "Non merci" is "non");
  * a yes is only ever a yes the person typed — never a default, never an
    empty line, never a closed window;
  * anything not understood is asked again, with the words that work.

Only the standard library: the installer and the drive launchers use this
before JEFFEREY's own Python space exists.
"""

from __future__ import annotations

import os
import re
import secrets
import sys
import unicodedata

YES = frozenset({"y", "yes", "yeah", "yep", "ok", "okay", "sure",
                 "oui", "ouais", "d'accord", "daccord"})
NO = frozenset({"n", "no", "nope", "nah", "non"})

# The door menu in 'What left the house'. "close" and "stop" mean the door:
# that is what someone who types them is afraid of.
DOOR = {
    "shut": frozenset({"s", "shut", "stop", "close", "ferme", "fermer", "fermez",
                       "arrete", "arreter", "arretez"}),
    "open": frozenset({"o", "open", "ouvre", "ouvrir", "ouvrez"}),
    "see": frozenset({"", "see", "show", "words", "voir", "montre"}),
    "all": frozenset({"a", "all", "everything", "tout"}),
    "keep": frozenset({"k", "keep", "garde", "garder"}),
    "quit": frozenset({"q", "quit", "exit", "leave", "quitter", "sortir", "fin"}),
}

_WORD = re.compile(r"[a-z0-9']+")


def norm(text: str | None) -> str:
    """The first word, lower case, accents and punctuation gone."""
    s = unicodedata.normalize("NFKD", str(text or "")).casefold()
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("’", "'")
    m = _WORD.search(s)
    return m.group(0).strip("'") if m else ""


def yes_no(text: str | None) -> bool | None:
    """True for a yes, False for a no, None for anything else (ask again)."""
    w = norm(text)
    if w in YES:
        return True
    if w in NO:
        return False
    return None


def choice(text: str | None, table: dict) -> str | None:
    """Which entry of `table` (name -> words) the answer is, or None."""
    w = norm(text)
    for name, words in table.items():
        if w in words:
            return name
    return None


def flush_typeahead(stream=None) -> None:
    """Throw away whatever was typed or pasted BEFORE the question was asked,
    so only an answer typed after it counts (verify I-04: one pasted scam
    e-mail held a command and the 'yes' after it, and the yes was read as
    the owner's own). Does nothing when not at a real keyboard."""
    try:
        import termios
        fd = (stream or sys.stdin).fileno()
        if os.isatty(fd):
            termios.tcflush(fd, termios.TCIFLUSH)
    except Exception:
        pass


def fresh_code() -> str:
    """Three digits to type back, different each time: nothing pasted or
    written beforehand can hold them."""
    while True:
        c = "".join(secrets.choice("123456789") for _ in range(3))
        if len(set(c)) > 1:
            return c


def typed_code(answer: str | None, code: str) -> bool:
    """Did the person type these digits back ('482', '4 8 2', '4-8-2')?"""
    return re.sub(r"\D", "", str(answer or "")) == code


# ---------------------------------------------------------- a person, here
# S6 (round 8): a confirmation that only the owner gives — 'confirm' and
# 'restore' in conscience.py, 'approve', 'erase' and 'bring-back' in
# forgetting.py, 'review' in guardian.py, opening the door or letting the
# record of what left go in egress.py — needs a person at this keyboard:
# stdin and stdout are terminals, --yes is ignored, and the answer is read
# from the terminal itself (/dev/tty) and must hold a short number printed
# on the screen at that moment. (Before, `conscience.py confirm all --yes`
# with stdin from /dev/null confirmed an AI's notes as his own words.)
#
# What this cannot tell apart: an agent that has a shell AND a
# pseudo-terminal can still do what he can, until Touch ID (I-43).
NOT_AT_KEYBOARD = ("This can only be done by you, typing at the keyboard of this "
                   "computer. Nothing was changed.")
YES_IGNORED = ("(--yes is not accepted any more: JEFFEREY asks you here, at the "
               "keyboard, every time.)")


def person_at_keyboard() -> bool:
    """Are both stdin and stdout a terminal? A pipe, /dev/null, a file or
    another program on either end is not a person."""
    try:
        return os.isatty(sys.stdin.fileno()) and os.isatty(sys.stdout.fileno())
    except (AttributeError, ValueError, OSError):
        return False


def read_tty(prompt: str) -> str | None:
    """One line typed at this terminal, read from the terminal itself
    (/dev/tty), never from whatever stdin was pointed at. Whatever was typed
    or pasted before the question is thrown away first. None when nothing
    was typed (a closed window). With no controlling terminal at all, stdin
    is used — it has been checked to be a terminal."""
    try:
        fd = os.open("/dev/tty", os.O_RDWR | getattr(os, "O_NOCTTY", 0))
    except OSError:
        fd = None
    if fd is None:
        if not person_at_keyboard():
            return None
        flush_typeahead()
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            return None
    try:
        try:
            import termios
            termios.tcflush(fd, termios.TCIFLUSH)        # nothing typed beforehand
        except Exception:
            pass
        os.write(fd, prompt.encode("utf-8", "replace"))
        got = b""
        while not got.endswith(b"\n") and len(got) < 4096:
            chunk = os.read(fd, 1024)
            if not chunk:
                break
            got += chunk
        return got.decode("utf-8", "replace") if got else None
    except (OSError, KeyboardInterrupt):
        return None
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def confirm_by_code(out=print, input_fn=None, tty: bool | None = None,
                    what: str = "") -> bool:
    """The owner's own yes (S6): only at a terminal (stdin and stdout), and
    only when he types back the three digits shown now. `input_fn` is for a
    caller that already reads the owner's keyboard itself (the terminal
    chat, a test); otherwise the answer comes from /dev/tty."""
    if tty is None:
        tty = person_at_keyboard()
    if not tty:
        out("  " + NOT_AT_KEYBOARD)
        return False
    code = fresh_code()
    prompt = (f"  {what + ' ' if what else ''}To make sure it is really you at the keyboard, "
              f"type the number {' '.join(code)} and press return: ")
    if input_fn is None:
        said = read_tty(prompt)
    else:
        flush_typeahead()
        try:
            said = input_fn(prompt)
        except (EOFError, KeyboardInterrupt):
            said = None
    if not typed_code(said, code):
        out("  That was not the number shown, so nothing was changed.")
        return False
    return True


def _ask(prompt: str, input_fn) -> str | None:
    try:
        return input_fn(prompt)
    except (EOFError, KeyboardInterrupt):
        return None                      # the window was closed: no answer


def ask_code_or_no(head: str, input_fn=None, out=print, tries: int = 5) -> bool | None:
    """S6 (round 8): a yes here is the number shown now, typed back; a no is
    a no; anything else is asked again. No answer at all is None — nothing is
    decided, it stays as it was. Read from the terminal itself unless the
    caller reads the owner's keyboard (`input_fn`)."""
    code = fresh_code()
    prompt = (f"{head} To say yes, type the number {' '.join(code)} and press return "
              f"(or type no): ")
    for _ in range(tries):
        if input_fn is None:
            said = read_tty(prompt)
        else:
            flush_typeahead()
            said = _ask(prompt, input_fn)
        if said is None:
            out("")
            return None
        if typed_code(said, code):
            return True
        if yes_no(said) is False:
            return False
        out("  That was not the number shown. Type the number to say yes, or no.")
    out("  No answer, so nothing was changed.")
    return None


def ask_yes_no(prompt: str, input_fn=input, out=print, tries: int = 5) -> bool:
    """Ask until there is a yes or a no. No answer at all is a no."""
    for _ in range(tries):
        a = _ask(prompt, input_fn)
        if a is None:
            out("")
            return False
        v = yes_no(a)
        if v is not None:
            return v
        out("  Please type yes or no (oui ou non), then press return.")
    out("  No answer, so nothing was changed.")
    return False


def ask_yes_no_or_none(prompt: str, input_fn=input, out=print, tries: int = 5) -> bool | None:
    """Like ask_yes_no, but no answer at all — a closed window, or five
    answers it did not understand — is None, never a 'no' to act on (verify
    I-08, I-60: the installer read silence as 'no drive' and chose this Mac)."""
    for _ in range(tries):
        a = _ask(prompt, input_fn)
        if a is None:
            out("")
            out("  No answer, so nothing was changed.")
            return None
        v = yes_no(a)
        if v is not None:
            return v
        out("  Please type yes or no (oui ou non), then press return.")
    out("  No answer, so nothing was changed.")
    return None


def ask_choice(prompt: str, table: dict, input_fn=input, out=print,
               hint: str = "", tries: int = 5) -> str | None:
    """Ask until the answer is one of `table`. None if there is no answer."""
    for _ in range(tries):
        a = _ask(prompt, input_fn)
        if a is None:
            out("")
            return None
        c = choice(a, table)
        if c is not None:
            return c
        out(f"  I did not understand '{a.strip()[:40]}'." + (f" {hint}" if hint else ""))
    return None


if __name__ == "__main__":                       # for shell launchers
    # python answers.py yesno "<answer>"  → exit 0 yes, 1 no, 2 not understood
    if len(sys.argv) == 3 and sys.argv[1] == "yesno":
        v = yes_no(sys.argv[2])
        sys.exit(0 if v is True else 1 if v is False else 2)
    sys.exit(2)
