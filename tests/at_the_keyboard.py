"""
A person at the keyboard, for the tests (S6, round 8).

The owner's own command-line confirmations (conscience.py confirm and
restore, forgetting.py approve, erase and bring-back, guardian.py review,
egress.py open and keep) refuse unless stdin and stdout are terminals,
ignore --yes, and want a short number that is printed on the screen at that
moment, read back from the terminal itself (/dev/tty). A test can only be
that person through a pseudo-terminal: this runs a command with a new
pseudo-terminal as its controlling terminal, watches the screen, and types
the number shown — or a wrong one, or nothing.

That is exactly what an agent with a shell and a pseudo-terminal can still
do; the docs say so, until Touch ID (I-43).
"""

from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import subprocess
import termios
import time

CODE = re.compile(rb"type the number ((?:\d ){2}\d)")


def _controlling_terminal() -> None:          # runs in the child, after setsid
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def run(cmd: list[str], env: dict, cwd, answer: str = "code",
        more: tuple[bytes, ...] = (), timeout: float = 120) -> tuple[int, str]:
    """Run `cmd` at a pseudo-terminal. Each time the screen asks for the
    number, type it (answer='code'), a wrong one ('wrong') or nothing
    ('nothing'). `more` is typed, one line each, whenever the screen asks
    for anything else ('Type yes', 'Which are right?'). Returns (exit
    status, what the screen showed)."""
    master, slave = pty.openpty()
    p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, env=env, cwd=cwd,
                         close_fds=True, start_new_session=True,
                         preexec_fn=_controlling_terminal)
    os.close(slave)
    buf, seen = b"", 0
    extra = list(more)
    deadline = time.time() + timeout
    while time.time() < deadline:
        rd, _, _ = select.select([master], [], [], 0.5)
        if rd:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
        fresh = buf[seen:]
        m = CODE.search(fresh)
        if m and b"press return" in fresh[m.end():]:
            typed = m.group(1).replace(b" ", b"")
            if answer == "wrong":
                typed = b"".join(str((int(ch) % 9) + 1).encode() for ch in typed.decode())
            elif answer == "nothing":
                typed = b""
            os.write(master, typed + b"\n")
            seen = len(buf)
        elif extra and (fresh.rstrip().endswith(b":") or fresh.rstrip().endswith(b">")):
            os.write(master, extra.pop(0) + b"\n")
            seen = len(buf)
        if p.poll() is not None and not rd:
            break
    try:
        rc = p.wait(timeout=30)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = -9
    try:
        while True:
            rd, _, _ = select.select([master], [], [], 0.2)
            if not rd:
                break
            chunk = os.read(master, 4096)
            if not chunk:
                break
            buf += chunk
    except OSError:
        pass
    os.close(master)
    return rc, buf.decode("utf-8", "replace")
