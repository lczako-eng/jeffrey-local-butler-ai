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

Since October 2026 it also: tells this Mac which Self-Cloud drive is yours
(only with your yes) and writes that drive's id into Claude's config, so
with the drive away JEFFEREY is off instead of starting a second life on
the laptop (I-08, I-17); warns loudly about any other connection in Claude
that can read your home folder or the drive (I-18); installs exactly the
versions it was tested with, keeps the key you chose before, and refuses
to wire Claude to a copy on a removable drive (I-21); and connects Claude
Code for every folder, not just this one (I-69).

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
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONNECTOR = REPO / "connector"
sys.path.insert(0, str(CONNECTOR))
import answers  # noqa: E402  (standard library only: runs before the venv exists)
import home  # noqa: E402
from version import __version__  # noqa: E402

HOME_DIR = Path.home() / ".jefferey"
VENV = HOME_DIR / "venv"
MIN_PY = (3, 11)          # the pinned libraries (requirements.lock) need 3.11
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
    # Exactly the versions the self-test passed with (requirements.lock), not
    # whatever is newest today: an unpinned install once moved the MCP library
    # to a release that hid every refusal's reason (I-21).
    lock = CONNECTOR / "requirements.lock"
    reqs = lock if lock.exists() else CONNECTOR / "requirements.txt"
    r = run([str(venv_python()), "-m", "pip", "install", "--quiet", "-r", str(reqs)])
    if r.returncode != 0:
        bad("Install failed:\n" + (r.stderr.strip()[:800] or r.stdout.strip()[:800]))
        return False
    ok("Everything he needs is installed")
    return True


# ------------------------------------------------------------- the selftest
def selftest_env(tmp: Path) -> dict:
    """The self-test proves the CODE works, so it runs entirely on a throwaway
    store. (It used to open the owner's real memory file on the way in, so a
    damaged memory showed up as 'his self-test did NOT pass', as if the
    program were broken.)"""
    env = dict(os.environ)
    for k in ("SELFCLOUD_ROOT", "SELFCLOUD_DRIVE_ID", "JEFFEREY_CLIENT",
              "JEFFEREY_OWNER_CONSOLE", "JEFFEREY_OFFLINE", "JEFFEREY_ALLOW_RESET"):
        env.pop(k, None)
    env.update(JEFFEREY_CONSCIENCE_PATH=str(tmp / "conscience.json"),
               JEFFEREY_EGRESS=str(tmp / "egress.jsonl"),
               JEFFEREY_DOOR=str(tmp / "door-shut"),
               SELFCLOUD_INDEX=str(tmp / "photo-index"),
               SELFCLOUD_VOICE=str(tmp / "voice"),
               SELFCLOUD_DISCS=str(tmp / "discs"),
               JEFFEREY_DRIVES=str(tmp / "drives.json"),
               JEFFEREY_FORMS_OUTBOX=str(tmp / "Filled forms"))
    return env


def memories_line(python: Path | None = None) -> int:
    """'Your memories: OK / will be recovered / need restoring' — a line of its
    own, read-only, separate from whether the program works."""
    # Not yet decided where they live (a new Mac, or step 3 of a first
    # install, before the drive question): nothing is wrong, and there is
    # nothing to restore (onboarding-08: a new owner was told, with a red
    # cross, to put back memories that never existed).
    try:
        where = home.locate() if home.problem() else None
    except Exception:
        where = None
    if where is not None and where.why == "undecided":
        say(f"  · Your memories: none yet. JEFFEREY keeps them where you choose — your "
            f"Self-Cloud drive or this Mac — and this installer asks you which.")
        return 0
    py = python or (venv_python() if venv_python().exists() else Path(sys.executable))
    r = run([str(py), str(CONNECTOR / "conscience.py"), "check"])
    out = r.stdout.strip().splitlines()
    text = out[0].strip() if out else "Your memories: could not be checked."
    away = where is not None or r.returncode == 3
    (ok if r.returncode == 0 else warn if r.returncode in (2, 3) or away else bad)(text)
    if r.returncode == 1 and not away and "no good copy" not in text:
        say(f"  {DIM}Double-click 'Restore my memories.command' to put back an "
            f"earlier copy. JEFFEREY still connects, and tells you the same "
            f"in Claude.{OFF}")
    return r.returncode


IMPORT_CHECK = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "import jefferey_mcp, jefferey_http; print('the servers start')")


def selftest() -> bool:
    with tempfile.TemporaryDirectory(prefix="jefferey-selftest-") as td:
        r = run([str(venv_python()), str(CONNECTOR / "jefferey_chat.py"), "--selftest"],
                env=selftest_env(Path(td)))
        if r.returncode == 0:
            # The servers Claude and ChatGPT start, really imported — the
            # self-test above only reads their source, and a library that
            # changed under them once passed it and left Claude a dead server.
            r2 = run([str(venv_python()), "-c", IMPORT_CHECK, str(CONNECTOR)],
                     env=selftest_env(Path(td)))
            if r2.returncode != 0:
                r = r2
    if r.returncode != 0:
        bad("His self-test did NOT pass. Nothing has been connected to Claude.")
        tail = (r.stdout + r.stderr).strip().splitlines()[-25:]
        say(DIM + "\n".join("      " + l for l in tail) + OFF)
        return False
    passed = [l for l in r.stdout.splitlines() if "✓" in l]
    ok(f"Self-test passed — {len(passed)} checks, no API key needed")
    say(f"  {DIM}(this proves the learning loop, the permission gate, the money"
        f" watch,\n   the life layer and the crash-recovery all work){OFF}")
    memories_line()
    return True


# --------------------------------------------------------------- the wiring
def server_entry(client: str, drive_ids: list[str] | None = None) -> dict:
    # Never JEFFEREY_OWNER_CONSOLE: a host where a model drives the
    # conversation must never be able to widen anything, and the server now
    # refuses to start if it is set (October 2026, I-43). Widening is the
    # owner's typed /permit or /grant in 'Talk to JEFFEREY on this Mac'.
    env = {"JEFFEREY_CLIENT": client}
    if drive_ids:
        # The owner's drive, pinned: with it away, JEFFEREY is off — it never
        # starts a second life on the laptop (I-08).
        env["SELFCLOUD_DRIVE_ID"] = ",".join(sorted(set(drive_ids)))
    return {"command": str(venv_python()),
            "args": [str(CONNECTOR / "jefferey_mcp.py")],
            "env": env}


def _desktop_servers() -> dict:
    cfg = CLAUDE_DESKTOP_CONFIG
    try:
        data = json.loads(cfg.read_text() or "{}") if cfg and cfg.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    return servers if isinstance(servers, dict) else {}


def existing_client() -> str | None:
    """The key Claude Desktop was given last time. A plain reinstall keeps
    it: it used to hand Claude the caretaker key again, silently (I-21)."""
    ent = _desktop_servers().get(SERVER_KEY)
    env = ent.get("env") if isinstance(ent, dict) else None
    c = env.get("JEFFEREY_CLIENT") if isinstance(env, dict) else None
    return c.strip().lower() if isinstance(c, str) and c.strip() else None


def existing_drive_ids() -> list[str]:
    ent = _desktop_servers().get(SERVER_KEY)
    env = ent.get("env") if isinstance(ent, dict) else None
    raw = env.get("SELFCLOUD_DRIVE_ID", "") if isinstance(env, dict) else ""
    import re
    return [t for t in re.split(r"[\s,;]+", str(raw).lower()) if re.fullmatch(r"[0-9a-f]{16}", t)]


# ------------------------------------------------------- the copy that runs
def on_removable_drive(path: Path | None = None) -> bool:
    """Is this copy of JEFFEREY on a drive that can be unplugged? Claude
    wired to it dies the moment the drive is pulled (I-21)."""
    p = Path(path or REPO).resolve()
    for b in set(home.MOUNT_BASES) | {"/Volumes", "/media", "/run/media", "/mnt"}:
        try:
            p.relative_to(b)
            return True
        except ValueError:
            pass
    return any((q / home.MARKER).exists() for q in [p] + list(p.parents))


# ------------------------------------------------ other connections in Claude
def _sensitive() -> list[tuple[Path, str]]:
    """Places no other connection should be able to read: where JEFFEREY's
    memories and the record of what left the house live."""
    out = []
    for p, mk in home.marked_drives():
        out.append((p, f"your Self-Cloud drive '{home.safe_name(mk.get('name'), p.name)}'"))
    try:
        for d in home.paired():
            if d.get("mount"):
                out.append((Path(d["mount"]), f"your Self-Cloud drive '{d.get('name', '')}'"))
    except home.PairingDamaged:
        pass
    out.append((Path("/Volumes/Self-Cloud"), "your Self-Cloud drive"))
    out.append((home.owner_dir(), "JEFFEREY's folder on this Mac (~/.jefferey)"))
    out.append((Path.home() / ".selfcloud", "Self-Cloud's folder on this Mac (~/.selfcloud)"))
    return out


def _path_words(entry) -> list[str]:
    """Every path a connection names — whole, after '--root=', or one of
    several joined by ':' or ',' (verify I-18: '--root=/Users/him' and
    'ALLOWED=/Users/him:/Volumes/Self-Cloud' were not seen)."""
    import re
    words = []
    if isinstance(entry, dict):
        for a in entry.get("args") or []:
            if isinstance(a, str):
                words.append(a)
        env = entry.get("env")
        if isinstance(env, dict):
            words += [v for v in env.values() if isinstance(v, str)]
    out = []
    for w in words:
        for part in re.split(r"[=:,;\s]+(?=[/~$])", w):
            part = part.strip().strip("\"'")
            if part.startswith(("/", "~", "$HOME", "${HOME}")):
                out.append(part)
    return out


def claude_code_servers() -> dict:
    """The connections Claude Code itself holds (~/.claude.json): for the
    whole user, and for each folder it was opened in. Read only."""
    p = Path.home() / ".claude.json"
    try:
        data = json.loads(p.read_text() or "{}") if p.is_file() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict = {}
    if isinstance(data, dict):
        top = data.get("mcpServers")
        if isinstance(top, dict):
            out.update({f"{k} (Claude Code)": v for k, v in top.items()})
        for folder, proj in (data.get("projects") or {}).items():
            servers = proj.get("mcpServers") if isinstance(proj, dict) else None
            if isinstance(servers, dict):
                out.update({f"{k} (Claude Code, in {folder})": v for k, v in servers.items()})
    return {k: v for k, v in out.items() if not k.startswith(SERVER_KEY + " ")}


def exposures(servers: dict) -> list[tuple[str, str, str]]:
    """(connection, the path it names, what that path holds) for every
    other connection whose folders equal or contain the home folder, the
    drive, or JEFFEREY's own folders — or sit inside them."""
    found = []
    targets = _sensitive()
    for name, entry in servers.items():
        if name == SERVER_KEY:
            continue
        for raw in _path_words(entry):
            p = Path(os.path.normpath(os.path.expandvars(os.path.expanduser(raw))))
            what = None
            if Path.home().is_relative_to(p):
                what = "your home folder, with JEFFEREY's folder in it"
            for t, label in targets if what is None else ():
                t = Path(os.path.normpath(t))
                if p == t or t.is_relative_to(p) or p.is_relative_to(t):
                    what = label
                    break
            if what:
                found.append((name, raw, what))
    return found


def warn_exposures(servers: dict, offer: bool, input_fn=input) -> list[str]:
    """Say it loudly. With the owner at the keyboard, offer to disconnect
    each one (the backup of the config keeps it). Returns the names removed."""
    gone = []
    by: dict[str, list[tuple[str, str]]] = {}
    for name, raw, what in exposures(servers):
        by.setdefault(name, []).append((raw, what))
    for name, rows in by.items():
        say(f"\n  {RED}{BOLD}✗ WARNING:{OFF} the connection '{name}' in Claude can read — and change —")
        for raw, what in rows:
            say(f"      {what}  (it names {raw})")
        say("    What it reads is NOT checked by JEFFEREY's door and NOT written down in")
        say("    'What left the house'. It could even open the door you shut, or change what")
        say("    JEFFEREY may do, by editing his files.")
        if offer:
            if answers.ask_yes_no(f"    Disconnect '{name}' from Claude? (The backup keeps it.) "
                                  "Type yes or no: ", input_fn):
                servers.pop(name, None)
                gone.append(name)
                ok(f"Disconnected '{name}'")
            else:
                say(f"    {DIM}Left as it is. You can remove it later in Claude → Settings → "
                    f"Developer.{OFF}")
        else:
            say(f"    {DIM}To disconnect it: run the installer again and answer yes, or remove it"
                f" in Claude → Settings → Developer.{OFF}")
    return gone


def owner_keys() -> list[str]:
    """Keys the owner made himself (/grant), read from his memory file —
    read only, never opened for writing. A key he made is as good a choice
    as a preset (verify: --client refused every key that was not a preset)."""
    try:
        if home.problem():
            return []
        raw = json.loads(home.conscience_path().read_text(encoding="utf-8-sig"))
        gs = raw.get("selfcloud_grants") if isinstance(raw, dict) else None
        return sorted(k for k, g in (gs or {}).items()
                      if isinstance(g, dict) and g.get("active") and isinstance(k, str))
    except Exception:
        return []


def known_clients() -> list[str]:
    """The keys JEFFEREY knows: the ones he can issue (selfcloud.PRESETS) and
    the ones the owner made himself."""
    sys.path.insert(0, str(CONNECTOR))
    try:
        from selfcloud import PRESETS
        presets = list(PRESETS)
    except Exception:
        presets = ["jefferey", "claude-raw", "gpt-raw", "family", "executor"]
    finally:
        sys.path.remove(str(CONNECTOR))
    return presets + [k for k in owner_keys() if k not in presets
                      and k not in ("owner", "local", "unknown")]


def wire_claude_desktop(client: str, drive_ids: list[str] | None = None,
                        offer: bool | None = None, input_fn=input) -> bool:
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
    servers[SERVER_KEY] = server_entry(client, drive_ids)
    gone = warn_exposures(servers, sys.stdin.isatty() if offer is None else offer, input_fn)
    others = [k for k in servers if k != SERVER_KEY]
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(data, indent=2))
    ok(f"Connected Jefferey to Claude Desktop as '{client}'"
       + (" — bound to your Self-Cloud drive" if drive_ids else ""))
    if others:
        ok(f"Left your other {len(others)} connection(s) alone: {', '.join(others)}")
    if gone:
        say(f"  {DIM}(the backup above still holds what was disconnected){OFF}")
    return True


def claude_code_add_argv(client: str, drive_ids: list[str] | None = None) -> list[str]:
    """`--scope user`: for every folder Claude Code opens in, not only the one
    the installer happened to run from (I-69)."""
    argv = ["claude", "mcp", "add", "--scope", "user", SERVER_KEY,
            "--env", f"JEFFEREY_CLIENT={client}"]
    if drive_ids:
        argv += ["--env", "SELFCLOUD_DRIVE_ID=" + ",".join(sorted(set(drive_ids)))]
    return argv + ["--", str(venv_python()), str(CONNECTOR / "jefferey_mcp.py")]


def _claude_code_remove() -> None:
    run(["claude", "mcp", "remove", "--scope", "user", SERVER_KEY])     # ignore failure
    # an earlier installer added it for this folder only
    run(["claude", "mcp", "remove", "--scope", "local", SERVER_KEY], cwd=str(REPO))


def wire_claude_code(client: str, drive_ids: list[str] | None = None) -> bool:
    if not shutil.which("claude"):
        warn("Claude Code CLI not found — skipping it. (Optional.)")
        return False
    _claude_code_remove()
    r = run(claude_code_add_argv(client, drive_ids))
    if r.returncode != 0:
        warn("Could not add to Claude Code: " + r.stderr.strip()[:200])
        return False
    ok(f"Connected Jefferey to Claude Code as '{client}'")
    warn_exposures(claude_code_servers(), offer=False)
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
        _claude_code_remove()
        ok("Removed Jefferey from Claude Code")
    say()
    say(f"  {BOLD}Your conscience was not touched.{OFF} It is still "
        f"{where_words()},")
    say("  with its history beside it. Nothing you told him has been lost.")


# ---------------------------------------------------------------- the drive
def where_words() -> str:
    """Where the memories are, for the owner — never a placeholder path."""
    w = home.locate()
    if w.ok:
        return home.describe()
    if w.why == "undecided":
        return "not anywhere yet (run this again to choose your drive or this Mac)"
    return "on your Self-Cloud drive (not plugged in right now)"


def move_life_step(drive: Path, offer: bool, input_fn=input) -> None:
    """His life is still on this Mac and his drive has none: offer to move
    it (verify I-08: the installer paired the drive and left the life behind,
    and JEFFEREY then showed an empty life). Until he says yes, JEFFEREY
    stays off — it never begins an empty life on the drive. When the drive
    already holds his life and a copy was left on the Mac (it could not be
    put aside, or only part of it), offer to put that copy aside (R7)."""
    if os.path.lexists(drive / home.NAMESPACE / "conscience.json"):
        sys.path.insert(0, str(REPO / "tools"))
        try:
            import provision_drive as pd
            left = pd.home_life()
            state = pd.mac_copy_state(left, drive / home.NAMESPACE) if left else ""
            if state in ("same", "older"):
                warn("A copy of your memories is still on this Mac "
                     f"({home.owner_dir()}); your drive has all of it"
                     + ("." if state == "same" else ", and what came since."))
                aside = (answers.ask_yes_no_or_none(
                    "    Put the Mac's copy aside now (it is kept, not deleted)? Type yes or "
                    "no: ", input_fn) if offer else None)
                if aside:
                    pd.move_home_life(drive, out=say)
                else:
                    say(f"    {DIM}JEFFEREY uses the drive's and never reads the Mac's copy. Run "
                        f"this again whenever you want it put aside.{OFF}")
            elif state == "different":
                warn(f"This Mac still holds a different copy of a life ({home.owner_dir()}). "
                     "JEFFEREY uses the drive's and never reads it; nothing was mixed.")
        except Exception as e:                 # never stops the install
            bad(f"The copy left on this Mac could not be looked at: {e}")
        finally:
            sys.path.remove(str(REPO / "tools"))
        return
    if not home.laptop_life():
        return
    warn("Your memories are on this Mac, and your drive has none yet.")
    move = (answers.ask_yes_no_or_none("    Move them onto the drive? (The Mac's copy is put "
                                       "aside, not deleted.) Type yes or no: ", input_fn)
            if offer else None)
    if move:
        sys.path.insert(0, str(REPO / "tools"))
        try:
            import provision_drive as pd
            pd.move_home_life(drive, out=say)
        except Exception as e:                 # Refused, or the drive filled up
            bad(f"They were not moved: {e}")
            say(f"    {DIM}Your memories are exactly where they were, on this Mac.{OFF}")
        finally:
            sys.path.remove(str(REPO / "tools"))
    else:
        warn("JEFFEREY stays off until they are moved — he will not start an empty life on "
             "the drive. Double-click this again and answer yes.")


def drive_step(offer: bool, input_fn=input) -> list[str]:
    """Which Self-Cloud drive is the owner's. Only his typed yes pairs one —
    a drive is never adopted because it carries a marker (I-17). Returns the
    ids to pin in Claude's config."""
    try:
        recs = home.paired()
    except home.PairingDamaged:
        warn(f"The list of your drives ({home.pairing_path()}) is damaged; it is set "
             "again below from the drives you say are yours.")
        recs = []
    ids = [d["id"] for d in recs] + [i for i in existing_drive_ids()
                                     if i not in {d["id"] for d in recs}]
    here = False
    for p, mk in home.marked_drives():
        name = home.safe_name(mk.get("name"), p.name)
        if mk["id"] in ids:
            ok(f"Your Self-Cloud drive '{name}' is plugged in, and this Mac knows it is yours")
            rec = next((d for d in recs if d["id"] == mk["id"]), None)
            if rec is not None and not rec.get("proof") and home._namespace_ok(p):
                try:
                    home.pair(p, mk)          # leaves the proof a copy cannot have
                except (OSError, ValueError):
                    pass
            here = True
            move_life_step(p, offer, input_fn)
            continue
        warn(f"A Self-Cloud drive is plugged in that this Mac does not know: '{name}' "
             f"(id {mk['id']}, at {p}).")
        mine = (answers.ask_yes_no_or_none("    Is it your own Self-Cloud drive? Type yes or "
                                           "no: ", input_fn) if offer else None)
        if mine:
            home.pair(p, mk)
            ids.append(mk["id"])
            here = True
            ok(f"This Mac now knows '{name}' is yours")
            move_life_step(p, offer, input_fn)
        else:
            say(f"    {DIM}JEFFEREY will not use it. If it is yours, run this again in Terminal "
                f"and answer yes, or:  cd '{REPO}' && python3 connector/home.py pair '{p}'{OFF}")
    if not ids:
        try:
            chosen = bool((home._pairing() or {}).get("this_mac"))
        except home.PairingDamaged:
            chosen = False
        if chosen or home.laptop_life():
            say(f"  {DIM}No Self-Cloud drive is paired with this Mac, so JEFFEREY keeps your "
                f"memories on this Mac (~/.jefferey){' as you chose' if chosen else ', as before'}."
                f"\n  If you have a Self-Cloud drive, plug it in and run this again.{OFF}")
        elif offer and not home.marked_drives():
            # Laptop-only is his choice, never what happens because a drive
            # was not plugged in when Claude started (I-08) — and never what
            # silence means (verify I-08, I-60: a closed window, or five
            # answers it did not understand, chose this Mac).
            has = answers.ask_yes_no_or_none("  Do you have a Self-Cloud drive for your "
                                             "memories? Type yes or no: ", input_fn)
            if has:
                warn("Plug it in, then double-click this again (a new drive: double-click "
                     "'Make this drive a Self-Cloud.command' first). Until then JEFFEREY "
                     "stays off.")
            elif has is False:
                home.choose_this_mac()
                ok("JEFFEREY will keep your memories on this Mac (~/.jefferey)")
            else:
                warn("JEFFEREY does not know yet where to keep your memories, so he stays off. "
                     "Double-click this again and answer the question about your drive.")
        else:
            warn("JEFFEREY does not know yet where to keep your memories, so he stays off. "
                 "Run this again in Terminal and answer the question about your drive.")
    elif not here:
        warn("Your Self-Cloud drive is not plugged in right now. JEFFEREY stays off until it "
             "is — he never starts a second life on this Mac.")
    return ids


# ------------------------------------------------------------------- checks
def check_only() -> int:
    say(f"\n{BOLD}Checking this machine{OFF}")
    base = find_python()
    if base:
        r = run([str(base), "-c", "import sys;print(sys.version.split()[0])"])
        ok(f"Python {r.stdout.strip()} at {base}")
    else:
        python_help()
    ok(f"Jefferey's code is at {REPO} (version {__version__})") if CONNECTOR.exists() else bad(
        f"connector/ not found under {REPO}")
    if on_removable_drive():
        warn("This copy is on a removable drive. Claude should run the copy in your home "
             "folder (~/JEFFEREY).")
    for line in home.status_lines():
        say(line)
    enc = home.encryption_line()
    if enc:
        say(f"  {enc}")
    (ok if venv_python().exists() else warn)(
        f"Private space {'ready' if venv_python().exists() else 'not built yet'}"
        f" at {VENV}")
    memories_line()
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
        warn_exposures(servers, offer=False)
    else:
        warn("Claude Desktop config not found")
    warn_exposures(claude_code_servers(), offer=False)
    say()
    return 0


# --------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="Set JEFFEREY up on this machine.")
    ap.add_argument("--check", action="store_true", help="report status, change nothing")
    ap.add_argument("--uninstall", action="store_true",
                    help="unhook from Claude; your conscience is kept")
    ap.add_argument("--client", default=None,
                    help="which Self-Cloud key this install holds "
                         "(jefferey = the caretaker; claude-raw = a guest). "
                         "Default: the one it held before, else jefferey")
    a = ap.parse_args()

    say(f"\n{BOLD}JEFFEREY{OFF} {__version__}  —  a Personal AI Shadow")
    say(f"{DIM}The intelligence is rented. The conscience is owned.{OFF}")

    if a.check:
        return check_only()
    if a.uninstall:
        say(f"\n{BOLD}Unhooking Jefferey{OFF}")
        unwire()
        return 0
    kept = existing_client()
    a.client = (a.client or kept or "jefferey").strip().lower()
    if on_removable_drive():
        bad("This copy of JEFFEREY is on a removable drive. Claude wired to it would stop "
            "the moment the drive is unplugged, and two copies drift apart.")
        say(f"  {DIM}Double-click 'Install JEFFEREY.command' in the copy in your home folder "
            f"(~/JEFFEREY) instead. 'Update JEFFEREY.command' keeps both copies the same.{OFF}")
        return 1
    # A misspelled key name ('claude_raw') used to be accepted, and every
    # call in Claude then failed as a bare "Error executing tool" (I-64).
    if a.client not in known_clients():
        bad(f"'{a.client}' is not a key JEFFEREY knows. Choose one of: "
            f"{', '.join(known_clients())}.")
        say(f"  {DIM}For example:  python3 tools/install.py --client claude-raw{OFF}")
        return 1

    total = 5
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

    step(4, total, "Your Self-Cloud drive")
    drive_ids = drive_step(sys.stdin.isatty())

    step(5, total, "Connecting him to Claude")
    if kept and kept == a.client:
        ok(f"Keeping the key Claude held before: '{a.client}'")
    desktop = wire_claude_desktop(a.client, drive_ids)
    code = wire_claude_code(a.client, drive_ids)
    if not (desktop or code):
        bad("Nothing was connected — install Claude Desktop, then run this again.")
        return 1

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
    say(f"  Everything he remembers lives in one file you own,")
    say(f"     {where_words()}")
    say(f"  {DIM}Plain text. Readable, editable, deletable, yours. Old versions are")
    say(f"   kept beside it in conscience.history/ in case anything goes wrong —")
    say(f"   double-click 'Restore my memories.command' to put one back.{OFF}")
    say(f"  {DIM}He never forgets on a guess: he shows what would go first, and")
    say(f"   anything big waits for you — 'Forget or bring back.command'.{OFF}")
    say()
    say(f"  {DIM}Check on him any time:   python3 tools/install.py --check{OFF}")
    say(f"  {DIM}Unhook him (keeps data): python3 tools/install.py --uninstall{OFF}")
    say()
    return 0


if __name__ == "__main__":
    sys.exit(main())
