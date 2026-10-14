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


def _ask(prompt: str, input_fn) -> str | None:
    try:
        return input_fn(prompt)
    except (EOFError, KeyboardInterrupt):
        return None                      # the window was closed: no answer


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
