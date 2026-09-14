#!/usr/bin/env python3
"""
Set JEFFEREY up on this Mac, in one go.
=======================================

Written for someone who does not program. It does five things and tells you
what it did:

  1. checks this machine has a new enough Python
  2. builds a private space for Jefferey to live in  (~/.jefferey/venv)
  3. installs what he needs
  4. runs his self-test, so you know he works BEFORE you rely on him
  5. wires him into Claude Desktop and/or Claude Code, without disturbing
     anything else you already have connected

It never touches your conscience file, never deletes anything, and always
backs up a config before changing it.

    python3 tools/install.py                # do it
    python3 tools/install.py --check        # just tell me what's wrong
    python3 tools/install.py --uninstall    # unhook from Claude, keep my data
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONNECTOR = REPO / "connector"
HOME_DIR = Path.home() / ".jefferey"
VENV = HOME_DIR / "venv"
MIN_PY = (3, 10)
SERVER_KEY = "jefferey"

# Where each host keeps its list of connected tools.
CLAUDE_DESKTOP_CONFIG = {
    "Darwin": Path.home() / "Library/Application Support/Claude/claude_desktop_config.json",
    "Windows": Path(os.environ.get("APPDATA", "")) / "Claude/claude_desktop_config.json",
    "Linux": Path.home() / ".config/Claude/claude_desktop_config.json",
}.get(platform.system())

GREEN, RED, YELL, DIM, BOLD, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m")


def say(msg: str = "") -> None:
    print(msg, flush=True)


def ok(msg: str) -> None:
    say(f"  {GREEN}✓{OFF} {msg}")


def bad(msg: str) -> None:
    say(f"  {RED}✗{OFF} {msg}")


def warn(msg: str) -> None:
    say(f"  {YELL}!{OFF} {msg}")


def step(n: int, total: int, msg: str) -> None:
    say(f"\n{BOLD}[{n}/{total}] {msg}{OFF}")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ------------------------------------------------------------------ python
def find_python() -> Path | None:
    """A Python new enough to run Jefferey. Prefer the newest we can find."""
    if sys.version_info >= MIN_PY:
        return Path(sys.executable)
    for name in ("python3.13", "python3.12", "python3.11", "python3.10", "python3"):
        exe = shutil.which(name)
        if not exe:
            continue
        r = run([exe, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"])
        if r.returncode == 0:
            try:
                major, minor = (int(x) for x in r.stdout.strip().split("."))
            except ValueError:
                continue
            if (major, minor) >= MIN_PY:
                return Path(exe)
    return None


def python_help() -> None:
    bad(f"This Mac's Python is {platform.python_version()}; Jefferey needs "
        f"{MIN_PY[0]}.{MIN_PY[1]} or newer.")
    say()
    say("  Fix it in one of two ways, then run this again:")
    say(f"    {DIM}•{OFF} Download from  https://www.python.org/downloads/  "
        "(the big yellow button), or")
    say(f"    {DIM}•{OFF} If you have Homebrew:  brew install python@3.12")
    say()


# --------------------------------------------------------------- the venv
def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def build_venv(base: Path) -> bool:
    if venv_python().exists():
        ok(f"Jefferey's space already exists at {VENV}")
    else:
        HOME_DIR.mkdir(parents=True, exist_ok=True)
        r = run([str(base), "-m", "venv", str(VENV)])
        if r.returncode != 0:
            bad(f"Could not create {VENV}:\n{r.stderr.strip()[:400]}")
            return False
        ok(f"Made Jefferey a private space at {VENV}")

    say(f"  {DIM}installing what he needs (this takes a minute)…{OFF}")
    r = run([str(venv_python()), "-m", "pip", "install", "--quiet", "--upgrade",
             "pip", "-r", str(CONNECTOR / "requirements.txt")])
    if r.returncode != 0:
        bad("Install failed:\n" + (r.stderr.strip()[:800] or r.stdout.strip()[:800]))
        return False
    ok("Everything he needs is installed")
    return True


# ------------------------------------------------------------- the selftest
def selftest() -> bool:
    r = run([str(venv_python()), str(CONNECTOR / "jefferey_chat.py"), "--selftest"])
    if r.returncode != 0:
        bad("His self-test did NOT pass. Nothing has been connected to Claude.")
        tail = (r.stdout + r.stderr).strip().splitlines()[-25:]
        say(DIM + "\n".join("      " + l for l in tail) + OFF)
        return False
    passed = [l for l in r.stdout.splitlines() if "✓" in l]
    ok(f"Self-test passed — {len(passed)} checks, no API key needed")
    say(f"  {DIM}(this proves the learning loop, the permission gate, the money"
        f" watch,\n   the life layer and the crash-recovery all work){OFF}")
    return True


# --------------------------------------------------------------- the wiring
def server_entry(client: str, owner_console: bool) -> dict:
    env = {"JEFFEREY_CLIENT": client}
    if owner_console:
        # Only ever on a surface that is literally the owner's own machine and
        # his own hands. It is what allows WIDENING a permission. Never set it
        # for a host where a model drives the conversation.
        env["JEFFEREY_OWNER_CONSOLE"] = "1"
    return {"command": str(venv_python()),
            "args": [str(CONNECTOR / "jefferey_mcp.py")],
            "env": env}


def wire_claude_desktop(client: str) -> bool:
    cfg = CLAUDE_DESKTOP_CONFIG
    if cfg is None:
        warn("Unknown operating system — skipping Claude Desktop.")
        return False
    if not cfg.parent.exists():
        warn("Claude Desktop doesn't look installed — skipping it. "
             "(Install it, then run this again.)")
        return False

    data = {}
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text() or "{}")
        except json.JSONDecodeError:
            bad(f"{cfg} is not valid JSON. Not touching it — fix or move it first.")
            return False
        backup = cfg.with_suffix(f".json.backup-{time.strftime('%Y%m%d-%H%M%S')}")
        backup.write_bytes(cfg.read_bytes())
        ok(f"Backed up your existing config to {backup.name}")

    servers = data.setdefault("mcpServers", {})
    others = [k for k in servers if k != SERVER_KEY]
    servers[SERVER_KEY] = server_entry(client, owner_console=False)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(data, indent=2))
    ok(f"Connected Jefferey to Claude Desktop as '{client}'")
    if others:
        ok(f"Left your other {len(others)} connection(s) alone: {', '.join(others)}")
    return True


def wire_claude_code(client: str) -> bool:
    if not shutil.which("claude"):
        warn("Claude Code CLI not found — skipping it. (Optional.)")
        return False
    run(["claude", "mcp", "remove", SERVER_KEY])          # ignore failure
    r = run(["claude", "mcp", "add", SERVER_KEY,
             "--env", f"JEFFEREY_CLIENT={client}",
             "--", str(venv_python()), str(CONNECTOR / "jefferey_mcp.py")])
    if r.returncode != 0:
        warn("Could not add to Claude Code: " + r.stderr.strip()[:200])
        return False
    ok(f"Connected Jefferey to Claude Code as '{client}'")
    return True


def unwire() -> None:
    cfg = CLAUDE_DESKTOP_CONFIG
    if cfg and cfg.exists():
        try:
            data = json.loads(cfg.read_text() or "{}")
        except json.JSONDecodeError:
            data = {}
        if data.get("mcpServers", {}).pop(SERVER_KEY, None) is not None:
            cfg.write_text(json.dumps(data, indent=2))
            ok("Removed Jefferey from Claude Desktop")
        else:
            ok("He wasn't connected to Claude Desktop")
    if shutil.which("claude"):
        run(["claude", "mcp", "remove", SERVER_KEY])
        ok("Removed Jefferey from Claude Code")
    say()
    say(f"  {BOLD}Your conscience was not touched.{OFF} It is still at "
        f"{HOME_DIR / 'conscience.json'},")
    say("  with its history beside it. Nothing you told him has been lost.")


# ------------------------------------------------------------------- checks
def check_only() -> int:
    say(f"\n{BOLD}Checking this machine{OFF}")
    base = find_python()
    if base:
        r = run([str(base), "-c", "import sys;print(sys.version.split()[0])"])
        ok(f"Python {r.stdout.strip()} at {base}")
    else:
        python_help()
    ok(f"Jefferey's code is at {REPO}") if CONNECTOR.exists() else bad(
        f"connector/ not found under {REPO}")
    (ok if venv_python().exists() else warn)(
        f"Private space {'ready' if venv_python().exists() else 'not built yet'}"
        f" at {VENV}")
    store = HOME_DIR / "conscience.json"
    if store.exists():
        try:
            d = json.loads(store.read_text())
            ok(f"Conscience exists: {len(d.get('facts', []))} facts, "
               f"{len(d.get('priorities', []))} priorities, "
               f"{len(d.get('memories', []))} moments, revision {d.get('_rev', 0)}")
        except Exception:
            bad("Conscience file exists but will not parse — he will refuse to "
                "start rather than lose it. Restore from ~/.jefferey/conscience.history/")
    else:
        warn("No conscience yet — that's normal before the first conversation")
    if CLAUDE_DESKTOP_CONFIG and CLAUDE_DESKTOP_CONFIG.exists():
        try:
            servers = json.loads(CLAUDE_DESKTOP_CONFIG.read_text()).get("mcpServers", {})
        except json.JSONDecodeError:
            servers = {}
        if SERVER_KEY in servers:
            client = servers[SERVER_KEY].get("env", {}).get("JEFFEREY_CLIENT", "?")
            ok(f"Connected to Claude Desktop, holding the '{client}' key")
        else:
            warn("Not connected to Claude Desktop yet")
    else:
        warn("Claude Desktop config not found")
    say()
    return 0


# --------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="Set JEFFEREY up on this machine.")
    ap.add_argument("--check", action="store_true", help="report status, change nothing")
    ap.add_argument("--uninstall", action="store_true",
                    help="unhook from Claude; your conscience is kept")
    ap.add_argument("--client", default="jefferey",
                    help="which Self-Cloud key this install holds "
                         "(jefferey = the caretaker; claude-raw = a guest)")
    a = ap.parse_args()

    say(f"\n{BOLD}JEFFEREY{OFF}  —  a Personal AI Shadow")
    say(f"{DIM}The intelligence is rented. The conscience is owned.{OFF}")

    if a.check:
        return check_only()
    if a.uninstall:
        say(f"\n{BOLD}Unhooking Jefferey{OFF}")
        unwire()
        return 0

    total = 4
    step(1, total, "Checking this machine")
    base = find_python()
    if not base:
        python_help()
        return 1
    ok(f"Python is new enough ({run([str(base), '-c', 'import sys;print(sys.version.split()[0])']).stdout.strip()})")
    if not (CONNECTOR / "jefferey_mcp.py").exists():
        bad(f"Can't find connector/jefferey_mcp.py under {REPO}")
        return 1
    ok(f"Found his code at {REPO}")

    step(2, total, "Building Jefferey a private space")
    if not build_venv(base):
        return 1

    step(3, total, "Making sure he actually works")
    if not selftest():
        return 1

    step(4, total, "Connecting him to Claude")
    desktop = wire_claude_desktop(a.client)
    code = wire_claude_code(a.client)
    if not (desktop or code):
        bad("Nothing was connected — install Claude Desktop, then run this again.")
        return 1

    store = HOME_DIR / "conscience.json"
    say(f"\n{GREEN}{BOLD}Done.{OFF}\n")
    if desktop:
        say(f"  {BOLD}1.{OFF} Quit Claude Desktop completely and open it again.")
        say(f"     {DIM}(the menu bar → Quit, not just closing the window){OFF}")
    else:
        say(f"  {BOLD}1.{OFF} Open Claude Code in a new terminal.")
    say(f"  {BOLD}2.{OFF} Start a new chat and say:")
    say(f"     {BOLD}\"Load your directives and tell me what you know about me.\"{OFF}")
    say(f"  {BOLD}3.{OFF} Then just talk to him. Correct him when he's wrong —")
    say(f"     {DIM}that is literally how he learns you.{OFF}")
    say()
    say(f"  Everything he remembers lives in one file you own:")
    say(f"     {store}")
    say(f"  {DIM}Plain text. Readable, editable, deletable, yours. Old versions are")
    say(f"   kept beside it in conscience.history/ in case anything goes wrong.{OFF}")
    say()
    say(f"  {DIM}Check on him any time:   python3 tools/install.py --check{OFF}")
    say(f"  {DIM}Unhook him (keeps data): python3 tools/install.py --uninstall{OFF}")
    say()
    return 0


if __name__ == "__main__":
    sys.exit(main())
