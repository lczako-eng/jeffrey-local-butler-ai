#!/usr/bin/env python3
"""
Update JEFFEREY — every copy to the same release, then check it works.
=====================================================================

    python3 tools/update.py            # what 'Update JEFFEREY.command' runs
    python3 tools/update.py --check    # say what would change, change nothing

Before October 2026 there was no update button and no version number: a
copy on the Mac and a copy on the drive ran different code, an old copy
could store a card number with none of the newer protections, and updating
meant a 'git pull' on a branch that could vanish (I-21). This:

  1. finds every copy: this one (in your home folder) and the one on your
     Self-Cloud drive, if it is plugged in;
  2. refuses, plainly, if a copy has changes made by hand — nothing is
     overwritten, ever;
  3. moves this copy forward to the newest release (the newest 'v…' tag, or
     else the newest version of the branch it follows) — forward only;
  4. brings the drive's copy to exactly the same version, from this one;
  5. runs the installer again (it keeps the key Claude held before, installs
     the pinned versions, and runs the self-test, which really starts the
     servers Claude and ChatGPT use);
  6. prints the version every copy now has.

Nothing here touches your memories. The installer refuses to wire Claude to
the drive's copy; the drive's copy is for 'Start Self-Cloud' on other Macs.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "connector"))
import home  # noqa: E402


def say(m: str = "") -> None:
    print(m, flush=True)


class UpdateRefused(Exception):
    """Nothing was changed, for a reason in plain words."""


def git(repo: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        detail = ((r.stderr or r.stdout).strip().splitlines() or [""])[-1][:160]
        raise UpdateRefused(f"the update could not be done in {repo} ({detail}); nothing "
                            f"more was changed")
    return r.stdout.strip()


def version_of(repo: Path) -> str:
    try:
        m = re.search(r'__version__\s*=\s*"([^"]+)"',
                      (repo / "connector" / "version.py").read_text())
        return m.group(1) if m else "unknown (older than 2026.10.14)"
    except OSError:
        return "unknown (older than 2026.10.14)"


def is_copy(repo: Path) -> bool:
    return (repo / ".git").exists() and (repo / "connector").is_dir()


def clean(repo: Path) -> None:
    """A copy with changes made by hand is never overwritten."""
    changed = git(repo, "status", "--porcelain", "--untracked-files=no")
    if changed:
        files = ", ".join(line[3:] for line in changed.splitlines()[:5])
        raise UpdateRefused(f"the copy at {repo} has changes made by hand ({files}), so "
                            f"nothing was updated. Ask the person who made them to save them first.")


def target(repo: Path) -> tuple[str, str]:
    """(commit, what it is called): the newest release tag if there is one,
    else the newest version of the branch this copy follows."""
    tags = [t for t in git(repo, "tag", "--list", "v*", "--sort=-v:refname").splitlines() if t]
    if tags:
        return git(repo, "rev-list", "-n", "1", tags[0]), f"release {tags[0]}"
    up = git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
    if not up or "@{u}" in up:
        raise UpdateRefused(f"the copy at {repo} does not know where its updates come from, "
                            f"so nothing was updated.")
    return git(repo, "rev-parse", up), f"the newest version of {up}"


def forward(repo: Path, commit: str) -> bool:
    """Move `repo` to `commit`, forward only. False if it was already there."""
    head = git(repo, "rev-parse", "HEAD")
    if head == commit:
        return False
    r = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", head, commit])
    if r.returncode != 0:
        raise UpdateRefused(f"the copy at {repo} has its own changes that the update would "
                            f"undo, so nothing was updated.")
    git(repo, "merge", "--ff-only", "--quiet", commit)
    return True


def drive_copies() -> list[Path]:
    """The software on each of the owner's drives that is plugged in."""
    out = []
    try:
        ids = home.pinned_ids()
    except home.PairingDamaged:
        ids = set()
    for p, mk in home.marked_drives():
        app = p / "Self-Cloud" / "app"
        if mk["id"] in ids and is_copy(app):
            out.append(app)
    return out


def update(repo: Path = REPO, copies: list[Path] | None = None, fetch: bool = True,
           check_only: bool = False) -> dict:
    """Bring `repo` and every copy in `copies` to the same version."""
    repo = Path(repo)
    if not is_copy(repo):
        raise UpdateRefused(f"{repo} is not a copy of JEFFEREY that can be updated.")
    copies = drive_copies() if copies is None else copies
    for c in [repo] + copies:
        clean(c)
    if fetch:
        r = subprocess.run(["git", "-C", str(repo), "fetch", "--tags", "--quiet"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise UpdateRefused("JEFFEREY could not reach the internet to fetch the update, "
                                "so nothing was changed. Try again when the Mac is online.")
    commit, called = target(repo)
    if check_only:
        return {"target": commit, "called": called, "changed": []}
    changed = []
    if forward(repo, commit):
        changed.append(str(repo))
    for c in copies:
        git(c, "fetch", "--quiet", "--tags", str(repo), "HEAD")
        if forward(c, git(c, "rev-parse", "FETCH_HEAD")):
            changed.append(str(c))
    return {"target": commit, "called": called, "changed": changed,
            "versions": {str(c): version_of(c) for c in [repo] + copies}}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Update every copy of JEFFEREY to the same release.")
    ap.add_argument("--check", action="store_true", help="say what would change, change nothing")
    a = ap.parse_args(argv)
    say("\n  Updating JEFFEREY. Your memories are not touched.\n")
    try:
        res = update(check_only=a.check)
    except UpdateRefused as e:
        say(f"  ! {e}\n")
        return 1
    if a.check:
        say(f"  This copy is at version {version_of(REPO)}; the update is {res['called']}.\n")
        return 0
    say(f"  ✓ every copy is now at {res['called']}"
        + ("" if res["changed"] else " (they already were)"))
    say("\n  Installing it, and checking it works:")
    r = subprocess.run([sys.executable, str(REPO / "tools" / "install.py")])
    for where, v in res["versions"].items():
        say(f"  JEFFEREY {v}  —  {where}")
    if r.returncode != 0:
        say("\n  ! The update arrived, but the installer did not finish (see above). Claude "
            "is still connected the way it was.\n")
        return 1
    say("\n  Quit Claude Desktop completely and open it again, so it uses the new version.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
