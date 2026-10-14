"""
version.py — which JEFFEREY this is.
====================================

One number, the date of the release it was cut from. It is written into
every line of the record of what left the house, shown by the installer and
by 'What left the house', and stamped into the memory file: a copy of
JEFFEREY older than the newest one that ever wrote the owner's memories
refuses to touch them and says "update" (I-21). Before October 2026 there
was no number at all, and an old copy on the drive could store a card
number with none of the newer protections.

Bump it with every change that reaches the owner (tools/update.py moves
every copy to the same one).
"""

from __future__ import annotations

import re

__version__ = "2026.10.14"


def parse(v) -> tuple[int, ...]:
    """'2026.10.14' → (2026, 10, 14); anything unreadable sorts first."""
    return tuple(int(x) for x in re.findall(r"\d+", str(v or ""))[:4]) or (0,)


def newer(a, b) -> bool:
    """Is version `a` newer than `b`?"""
    return parse(a) > parse(b)


if __name__ == "__main__":
    print(__version__)
