"""
home.py — where the life lives: on YOUR drive, on this Mac, or nowhere.
=======================================================================

"Plug it in anywhere" is only true if the DATA is on the drive. So every
tool asks this module where things go. The answer is worked out again on
every question (a folder listing and a few stats), never decided once for
the life of a process:

    your drive is plugged in   →  <drive>/.selfcloud/jefferey/…   (the product)
    you chose "this Mac"       →  ~/.jefferey  and  ~/.selfcloud   (laptop-only)
    your drive is NOT here     →  nowhere: JEFFEREY is off, and says so

The October 2026 stress test (I-08, I-17) found that whenever there was not
exactly one marked drive, JEFFEREY quietly started a second life on the
laptop — it kept remembering there, forgot the keys the owner had revoked
and reopened the door he had shut — and that ANY stick with a file called
selfcloud.json became the owner's conscience, planted "owner instructions"
and permissions included. So now:

  * A drive counts only if its marker is a real one (a dict, kind
    'self-cloud-drive', a 16-hex id) AND this Mac has been paired with that
    id — at provisioning, by the installer with the owner's yes, or with
    `python3 connector/home.py pair <drive>`. The pairing lives in
    ~/.jefferey/drives.json; the installer also writes the id into Claude's
    config (SELFCLOUD_DRIVE_ID), so the pin survives that file being lost.
  * Once a drive is paired, its absence never means "use the laptop". Every
    tool refuses, plainly: "your Self-Cloud drive is not plugged in".
    Laptop-only is a choice the owner makes (the installer asks; or he
    unpairs every drive with his own hands). A life already kept on the
    laptop from before keeps working; a NEW one is never begun there just
    because no drive is plugged in.
  * Two of your drives at once, a drive this Mac does not know, a copy of
    your drive (same id, different volume), or a JEFFEREY folder that is a
    shortcut to somewhere else: refused, never guessed.
  * Nothing is ever created under a drive that is not there.

Why `.selfcloud/jefferey/` and not `.selfcloud/` itself: the Self-Cloud
connector owns the top of that folder (node.json, catalog.db, audit.jsonl,
index.lock — see Self-Cloud-Workspace/HANDOVER.md). Namespacing under
`jefferey/` means the two halves cannot collide on a shared drive, and
either can be removed without touching the other.

Explicit environment variables always win (the caller chose the place):
    JEFFEREY_CONSCIENCE_PATH   the conscience file
    SELFCLOUD_INDEX            the photo index directory
    SELFCLOUD_VOICE            voice recordings
    SELFCLOUD_DISCS            archived discs
    JEFFEREY_EGRESS            the egress log (what left the house)
    JEFFEREY_DOOR              the door-shut switch file
    JEFFEREY_FORMS_OUTBOX      where filled forms are saved ('Filled forms')
    JEFFEREY_DRIVES            the list of drives paired with this Mac
    SELFCLOUD_ROOT             use exactly this drive (it must be a real one)
    SELFCLOUD_DRIVE_ID         the id(s) of the owner's drive(s), pinned

Owner commands (his own terminal; no AI can run these):
    python3 connector/home.py                    where does my life live?
    python3 connector/home.py pair <drive>       this drive is mine
    python3 connector/home.py unpair <id|name>   this Mac forgets a drive
    python3 connector/home.py this-mac           keep my life on this Mac, no drive
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import plistlib
import re
import secrets
import stat as _stat
import subprocess
import sys
import weakref
from pathlib import Path

MARKER = Path(".selfcloud") / "selfcloud.json"
NAMESPACE = Path(".selfcloud") / "jefferey"
MARKER_KIND = "self-cloud-drive"
MARKER_MAX = 64 * 1024
_ID = re.compile(r"[0-9a-f]{16}")

# Where removable drives appear. Tests point this at a folder of their own.
MOUNT_BASES = ["/Volumes", "/media", "/mnt", "/run/media"]
_PER_USER = ("/media", "/run/media")          # /media/<user>/<drive>

# Where the life "is" while the drive that holds it is away: a place that is
# never a real folder. Nothing is ever read from or written under it.
OFFLINE_ROOT = Path("/nonexistent/self-cloud-drive-is-not-plugged-in")

# Things inside JEFFEREY's folder on the drive that must be real files and
# folders, never shortcuts: a link there sends the life somewhere else (an
# iCloud folder, the owner's ~/.zshrc) — I-55.
_NO_LINKS = ("conscience.json", "conscience.history", "conscience.access.jsonl",
             "conscience.trash", "conscience.pending.json", "conscience.changes.json",
             "egress.jsonl", "door-shut", "photo-index", "voice", "discs")
_ONE_LINK_ONLY = ("conscience.json", "egress.jsonl")   # a hard link is a copy someone can read

_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_SEEN_ROOTS: set[str] = set()            # drives this process has used
_LAST: tuple[str, str | None] | None = None
_WATCHERS: list = []
_ANNOUNCED = False
_UUIDS: dict[tuple[str, int], str | None] = {}


# ------------------------------------------------------------------ markers
def valid_marker(obj) -> bool:
    return (isinstance(obj, dict) and obj.get("kind") == MARKER_KIND
            and isinstance(obj.get("id"), str) and bool(_ID.fullmatch(obj["id"]))
            and isinstance(obj.get("name", ""), str))


def _read_small(p: Path, cap: int = MARKER_MAX) -> bytes:
    """Read a small file without following a link to it."""
    st = os.lstat(p)
    if not _stat.S_ISREG(st.st_mode):
        raise OSError(f"{p.name} is not a plain file")
    if st.st_size > cap:
        raise OSError(f"{p.name} is too big to be what it says")
    fd = os.open(p, os.O_RDONLY | _O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        return f.read(cap + 1)


def read_marker(root: Path) -> dict | None:
    """The drive's marker if it is a real one, else None. A marker inside a
    folder that is a shortcut is not a real one."""
    try:
        sc = os.lstat(Path(root) / ".selfcloud")
        if _stat.S_ISLNK(sc.st_mode):
            return None
        obj = json.loads(_read_small(Path(root) / MARKER))
    except (OSError, ValueError):
        return None
    return obj if valid_marker(obj) else None


def safe_name(name, fallback: str = "Self-Cloud") -> str:
    """A drive's name as the owner may see it: printable, short."""
    s = "".join(ch for ch in str(name or "") if ch.isprintable() and ch not in "\r\n\t")
    s = s.strip()[:40]
    return s or fallback


# ------------------------------------------------------------------ pairing
class PairingDamaged(ValueError):
    pass


def owner_dir() -> Path:
    """The owner's own folder on this Mac (~/.jefferey)."""
    return Path("~").expanduser() / ".jefferey"


def pairing_path() -> Path:
    env = os.environ.get("JEFFEREY_DRIVES")
    return Path(env).expanduser() if env else owner_dir() / "drives.json"


def _pairing() -> dict | None:
    """The owner's choice on this Mac: {'drives': [...], 'this_mac': bool},
    or None if he has never been asked. Raises PairingDamaged if the file
    exists but cannot be trusted (then nothing is guessed)."""
    p = pairing_path()
    try:
        raw = _read_small(p, 1024 * 1024)
    except FileNotFoundError:
        return None
    except OSError as e:
        raise PairingDamaged(str(e)) from None
    try:
        obj = json.loads(raw)
    except ValueError:
        raise PairingDamaged("not readable") from None
    drives = obj.get("drives") if isinstance(obj, dict) else None
    if not isinstance(drives, list):
        raise PairingDamaged("no list of drives")
    return {"drives": [d for d in drives if isinstance(d, dict)
                       and isinstance(d.get("id"), str) and _ID.fullmatch(d["id"])],
            "this_mac": obj.get("this_mac") is True}


def paired() -> list[dict]:
    """The drives this Mac knows are the owner's. Raises PairingDamaged."""
    got = _pairing()
    return got["drives"] if got else []


def laptop_life() -> bool:
    """Is there a life JEFFEREY already kept on this Mac (from before)?"""
    d = owner_dir()
    return (d / "conscience.json").exists() or (d / "conscience.history").is_dir()


def _env_ids() -> set[str] | None:
    raw = os.environ.get("SELFCLOUD_DRIVE_ID")
    if raw is None or not raw.strip():
        return None
    return {t for t in re.split(r"[\s,;]+", raw.strip().lower()) if _ID.fullmatch(t)}


def pinned_ids() -> set[str]:
    """Every id the owner has said is his: paired here, or pinned in the
    config. Raises PairingDamaged."""
    ids = {d["id"] for d in paired()}
    env = _env_ids()
    if env is not None:
        ids |= env or {"-"}        # pinned to something unreadable: nothing matches
    return ids


def _write_private(path: Path, payload: bytes) -> None:
    """Write a small file of the owner's: a fresh temp file (O_EXCL, never
    through a link), flushed, renamed into place; folder 0700, file 0600."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink():
        raise OSError(f"{path.parent} is a shortcut; not writing through it")
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW, 0o600)
    try:
        try:
            view = memoryview(payload)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _save_pairing(drives: list[dict], this_mac: bool = False) -> Path:
    p = pairing_path()
    body = {"about": "The Self-Cloud drives this Mac knows are yours. JEFFEREY "
                     "uses only these. Change it with: python3 connector/home.py",
            "drives": drives,
            "this_mac": bool(this_mac and not drives)}
    _write_private(p, (json.dumps(body, indent=2, ensure_ascii=False) + "\n").encode())
    return p


def pair(root: Path, marker: dict | None = None, volume_uuid: str | None = None) -> dict:
    """OWNER ONLY (provisioning, the installer after his yes, or his own
    terminal). Remember that the drive at `root` is his."""
    root = Path(root)
    m = marker or read_marker(root)
    if not m:
        raise ValueError(f"{root} is not a Self-Cloud drive (no valid marker)")
    try:
        drives = paired()
    except PairingDamaged:
        drives = []                     # the owner is setting it again, by hand;
        _keep_damaged()                 # the damaged list is kept, not overwritten
    uuid = volume_uuid if volume_uuid is not None else _volume_uuid(root)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    rec = next((d for d in drives if d["id"] == m["id"]), None)
    if rec is None:
        rec = {"id": m["id"], "paired": now}
        drives.append(rec)
    rec.update(name=safe_name(m.get("name"), root.name), mount=str(root), seen=now)
    if uuid:
        rec["volume_uuid"] = uuid
    _save_pairing(drives)                 # a paired drive ends "this Mac only"
    return rec


def unpair(which: str) -> list[dict]:
    """OWNER ONLY. Forget the drive(s) whose id or name is `which`. With no
    drive left, his life is kept on this Mac — he said so by unpairing."""
    w = str(which or "").strip()
    drives = paired()
    gone = [d for d in drives if d["id"] == w.lower() or d.get("name") == w]
    if gone:
        left = [d for d in drives if d not in gone]
        _save_pairing(left, this_mac=not left)
    return gone


def _keep_damaged() -> None:
    p = pairing_path()
    try:
        if os.path.lexists(p):
            os.replace(p, p.with_name(p.name + ".damaged-"
                                      + _dt.datetime.now().strftime("%Y%m%d-%H%M%S")))
    except OSError:
        pass


def choose_this_mac() -> Path:
    """OWNER ONLY (the installer, after he said he has no drive; or his own
    terminal). Keep the life on this Mac, in ~/.jefferey. Laptop-only is a
    choice he makes, never what happens because a drive is missing."""
    try:
        drives = paired()
    except PairingDamaged:
        drives = []
        _keep_damaged()
    if drives:
        raise ValueError("a Self-Cloud drive is paired with this Mac; unpair it first")
    return _save_pairing([], this_mac=True)


# ------------------------------------------------------------------ mounts
def _mounts() -> list[Path]:
    """Where removable drives appear, per platform. A link in /Volumes is
    not a drive (the Mac's own disk shows there as one)."""
    out: list[Path] = []
    for base in MOUNT_BASES:
        b = Path(base)
        try:
            kids = sorted(b.iterdir())
        except OSError:
            continue
        for k in kids:
            try:
                if k.is_symlink() or not k.is_dir():
                    continue
            except OSError:
                continue
            out.append(k)
            if str(base) in _PER_USER:                      # /media/<user>/<drive>
                try:
                    out += sorted(q for q in k.iterdir()
                                  if q.is_dir() and not q.is_symlink())
                except OSError:
                    pass
    return out


def marked_drives() -> list[tuple[Path, dict]]:
    """Every mounted volume carrying a real Self-Cloud marker."""
    out = []
    for m in _mounts():
        mk = read_marker(m)
        if mk:
            out.append((m, mk))
    return out


def all_drives(any_marker: bool = False) -> list[Path]:
    """Every Self-Cloud drive plugged in, the one in use first — paired or
    not. For FINDING things (a voice to delete everywhere), never for
    choosing where to write. `any_marker` also counts a volume whose marker
    is not a real one (a drive made before October 2026)."""
    out: list[Path] = []
    try:
        r = root()
    except Exception:
        r = None
    if r is not None:
        out.append(r)
    explicit = os.environ.get("SELFCLOUD_ROOT")
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_dir() and (read_marker(p) or (any_marker and (p / MARKER).is_file())):
            out.append(p)
    for m in _mounts():
        if read_marker(m) or (any_marker and (m / MARKER).is_file()):
            out.append(m)
    seen, uniq = set(), []
    for p in out:
        if str(p) not in seen:
            seen.add(str(p))
            uniq.append(p)
    return uniq


def _volume_uuid(root: Path) -> str | None:
    """The volume's own UUID (macOS), once per mount. None where unknown."""
    if platform.system() != "Darwin":
        return None
    try:
        dev = os.stat(root).st_dev
    except OSError:
        return None
    key = (str(root), dev)
    if key not in _UUIDS:
        _UUIDS[key] = str(disk_info(root).get("VolumeUUID") or "") or None
    return _UUIDS[key]


def _namespace_ok(root: Path) -> bool:
    """JEFFEREY's folder on the drive, and what is in it, are real — not
    shortcuts out of the drive, not hard links someone else can read."""
    for rel in (Path(".selfcloud"), NAMESPACE):
        try:
            if _stat.S_ISLNK(os.lstat(root / rel).st_mode):
                return False
        except FileNotFoundError:
            return True                   # not made yet: nothing to follow
        except OSError:
            return False
    ns = root / NAMESPACE
    try:
        real = os.path.realpath(ns)
        if os.path.commonpath([real, os.path.realpath(root)]) != os.path.realpath(root):
            return False
    except (OSError, ValueError):
        return False
    for name in _NO_LINKS:
        try:
            st = os.lstat(ns / name)
        except FileNotFoundError:
            continue
        except OSError:
            return False
        if _stat.S_ISLNK(st.st_mode):
            return False
        if name in _ONE_LINK_ONLY and _stat.S_ISREG(st.st_mode) and st.st_nlink > 1:
            return False
    return True


# ------------------------------------------------------------------ where
class Where:
    """Where the life is right now. state: 'drive', 'laptop' or 'off'."""
    __slots__ = ("state", "root", "marker", "why", "names")

    def __init__(self, state, root=None, marker=None, why=None, names=()):
        self.state, self.root, self.marker = state, root, marker or {}
        self.why, self.names = why, tuple(names)

    @property
    def ok(self) -> bool:
        return self.state != "off"

    def reason(self) -> str | None:
        return REASONS.get(self.why) if self.state == "off" else None


_OFF = "nothing was read, remembered or sent"
REASONS = {
    "missing": ("your Self-Cloud drive is not plugged in (or not unlocked yet), so "
                f"JEFFEREY is switched off: {_OFF}. Plug the drive in, type its "
                "password if the Mac asks, and ask again"),
    "missing+stranger": ("your Self-Cloud drive is not plugged in, so JEFFEREY is "
                         f"switched off: {_OFF}. The drive that IS plugged in is not "
                         "yours, and JEFFEREY will not use it. Plug in your own drive "
                         "and ask again"),
    "two": ("two of your Self-Cloud drives are plugged in at once, so JEFFEREY "
            f"cannot tell which one holds your life and is switched off: {_OFF}. "
            "Unplug the one you are not using, then ask again"),
    "unpaired": ("a Self-Cloud drive is plugged in, but this Mac has not been told "
                 f"it is yours, so JEFFEREY will not use it and is switched off: {_OFF}. "
                 "If it is your own drive, double-click 'Install JEFFEREY.command' "
                 "and answer yes when it asks about the drive"),
    "not-a-drive": ("the Self-Cloud drive JEFFEREY was told to use is not plugged in "
                    f"(or is not a Self-Cloud drive), so JEFFEREY is switched off: {_OFF}. "
                    "Plug your Self-Cloud drive in and ask again"),
    "stranger": ("this is not your Self-Cloud drive, so JEFFEREY will not use it and "
                 f"is switched off: {_OFF}. Plug in your own drive and ask again"),
    "copy": ("the drive plugged in carries your Self-Cloud drive's name but is a copy "
             "of it, not the drive this Mac was paired with, so JEFFEREY will not "
             f"write to it and is switched off: {_OFF}. Plug in your own drive; if this "
             "copy is your drive now, double-click 'Install JEFFEREY.command' and "
             "answer yes when it asks about the drive"),
    "link": ("JEFFEREY's folder on your Self-Cloud drive points somewhere else (a "
             f"shortcut someone put there), so JEFFEREY will not use it: {_OFF}. Ask "
             "someone you trust to look at the drive"),
    "undecided": ("JEFFEREY does not know yet where to keep your memories, so it is "
                  f"switched off: {_OFF}. Double-click 'Install JEFFEREY.command': with "
                  "your Self-Cloud drive plugged in it will ask if the drive is yours; "
                  "without one, answer no when it asks about a drive, to keep them on "
                  "this Mac"),
    "pairing": ("the list of your own Self-Cloud drives on this Mac is damaged, so "
                f"JEFFEREY will not guess which drive is yours and is switched off: {_OFF}. "
                "Double-click 'Install JEFFEREY.command' to set it again"),
}


def _check_drive(root: Path, mk: dict, records: list[dict]) -> Where:
    if not _namespace_ok(root):
        return Where("off", root, mk, "link", [mk.get("name", "")])
    rec = next((d for d in records if d["id"] == mk["id"]), None)
    want = (rec or {}).get("volume_uuid")
    if want:
        have = _volume_uuid(root)
        if have and have.upper() != str(want).upper():
            return Where("off", root, mk, "copy", [mk.get("name", "")])
    return Where("drive", root, mk)


def _resolve() -> Where:
    try:
        choice = _pairing()
        records = choice["drives"] if choice else []
        ids = {d["id"] for d in records}
        env = _env_ids()
        if env is not None:
            ids |= env or {"-"}
    except PairingDamaged:
        return Where("off", why="pairing")

    explicit = os.environ.get("SELFCLOUD_ROOT")
    if explicit:
        p = Path(explicit).expanduser()
        mk = read_marker(p) if p.is_dir() else None
        if mk is None:
            return Where("off", why="not-a-drive")
        if ids and mk["id"] not in ids:
            return Where("off", p, mk, "stranger", [mk.get("name", "")])
        return _check_drive(p, mk, records)

    marked = marked_drives()
    if not ids:
        chose = bool(choice and choice["this_mac"])
        if marked and not chose:
            # Never asked, and a Self-Cloud drive is in: it may be his own,
            # made before pairing existed. Not adopted, and not ignored either
            # (that is how the life split in two): he is asked to pair it.
            return Where("off", why="unpaired", names=[m.get("name", "") for _, m in marked])
        # Laptop-only when he chose it (another drive plugged in is then
        # ignored, never adopted), or when a life is already kept here (an
        # owner from before October 2026 keeps working as he did). A NEW life
        # is never begun on the laptop just because no drive is in.
        if chose or laptop_life() or any(os.environ.get(k) for k in _CORE_ENV):
            return Where("laptop")
        return Where("off", why="undecided")
    mine = [(p, m) for p, m in marked if m["id"] in ids]
    if len(mine) == 1:
        return _check_drive(mine[0][0], mine[0][1], records)
    if len(mine) > 1:
        return Where("off", why="two", names=[m.get("name", "") for _, m in mine])
    others = [m.get("name", "") for p, m in marked]
    return Where("off", why="missing+stranger" if others else "missing", names=others)


def locate() -> Where:
    """Where the life is, worked out now. Watchers hear when a drive this
    process was using goes away (they drop what they hold in memory)."""
    global _LAST
    w = _resolve()
    if w.state == "drive":
        _SEEN_ROOTS.add(str(w.root))
    now = (w.state, str(w.root) if w.state == "drive" else None)
    if _LAST is not None and _LAST[0] == "drive" and now != _LAST:
        for ref in list(_WATCHERS):
            fn = ref()
            if fn is None:
                _WATCHERS.remove(ref)
                continue
            try:
                fn()
            except Exception:
                pass
    _LAST = now
    return w


def watch(method) -> None:
    """Call `method` (a bound method; held weakly) when the drive in use goes."""
    _WATCHERS.append(weakref.WeakMethod(method))


_CORE_ENV = ("JEFFEREY_CONSCIENCE_PATH", "JEFFEREY_EGRESS", "JEFFEREY_DOOR")


def problem() -> str | None:
    """Why JEFFEREY must not run right now, in plain words — or None. When
    every place the surfaces use was named explicitly, the caller chose."""
    if all(os.environ.get(k) for k in _CORE_ENV):
        return None
    return locate().reason()


def root() -> Path | None:
    """Your Self-Cloud drive, if it is here and usable; else None."""
    w = locate()
    return w.root if w.state == "drive" else None


def marker() -> dict:
    w = locate()
    return dict(w.marker) if w.state == "drive" else {}


def data() -> Path | None:
    """JEFFEREY's namespace on the drive, or None if there is no drive."""
    r = root()
    return (r / NAMESPACE) if r else None


def _pick(env: str, on_drive: str, at_home: str) -> Path:
    if os.environ.get(env):
        return Path(os.environ[env]).expanduser()
    w = locate()
    if w.state == "drive":
        return w.root / NAMESPACE / on_drive
    if w.state == "laptop":
        return Path(at_home).expanduser()
    return OFFLINE_ROOT / NAMESPACE / on_drive      # never the laptop


def conscience_path() -> Path:
    return _pick("JEFFEREY_CONSCIENCE_PATH", "conscience.json", "~/.jefferey/conscience.json")


def index_path() -> Path:
    return _pick("SELFCLOUD_INDEX", "photo-index", "~/.selfcloud/photo-index")


def voice_path() -> Path:
    return _pick("SELFCLOUD_VOICE", "voice", "~/.selfcloud/voice")


def discs_path() -> Path:
    return _pick("SELFCLOUD_DISCS", "discs", "~/.selfcloud/discs")


def egress_path() -> Path:
    """The egress log: everything that ever left for a rented engine, word
    for word. Beside the conscience, because it is exactly as private."""
    return _pick("JEFFEREY_EGRESS", "egress.jsonl", "~/.jefferey/egress.jsonl")


def door_switch_path() -> Path:
    """A file whose mere existence shuts the egress door. The owner can make
    it by hand on the drive if every other switch has failed them."""
    return _pick("JEFFEREY_DOOR", "door-shut", "~/.jefferey/door-shut")


def _known(env: str, name: str) -> list[Path]:
    """Every place a door switch or a log may be: the one in use, the
    owner's own folder on this Mac, and each of his drives plugged in."""
    if os.environ.get(env):
        return [Path(os.environ[env]).expanduser()]
    out: list[Path] = []
    w = locate()
    if w.state == "drive":
        out.append(w.root / NAMESPACE / name)
    out.append(owner_dir() / name)
    try:
        ids = pinned_ids()
    except PairingDamaged:
        ids = set()
    for p, mk in marked_drives():
        if mk["id"] in ids and _namespace_ok(p):
            out.append(p / NAMESPACE / name)
    seen, uniq = set(), []
    for p in out:
        if str(p) not in seen:
            seen.add(str(p))
            uniq.append(p)
    return uniq


def door_switches() -> list[Path]:
    """Every switch that shuts the door. Any one of them shuts it; shutting
    writes all of them, opening removes all of them (I-08)."""
    return _known("JEFFEREY_DOOR", "door-shut")


def egress_logs() -> list[Path]:
    """Every record of what left the house that exists, the one in use first."""
    return [p for p in _known("JEFFEREY_EGRESS", "egress.jsonl") if p.exists()]


def where_of(path: Path) -> str:
    """'drive' or 'mac', for one of those places — for the owner's report."""
    s = str(path)
    if s.startswith(str(owner_dir()) + os.sep):
        return "mac"
    return "drive" if str(NAMESPACE) in s else "mac"


FORMS_FOLDER = "Filled forms"


def forms_outbox_path() -> Path:
    """The ONE place a filled form is saved (October 2026, I-02): a folder
    the owner can see and open — at the top of the Self-Cloud drive, or in
    his home folder when there is no drive. Never chosen by an AI; the
    representative refuses anything outside it."""
    if os.environ.get("JEFFEREY_FORMS_OUTBOX"):
        return Path(os.environ["JEFFEREY_FORMS_OUTBOX"]).expanduser()
    w = locate()
    if w.state == "drive":
        return w.root / FORMS_FOLDER
    if w.state == "laptop":
        return Path("~").expanduser() / FORMS_FOLDER
    return OFFLINE_ROOT / FORMS_FOLDER


# ------------------------------------------------------------------ guards
class DriveAway(OSError):
    """A write was about to land where a drive is not."""


def _under(path: Path, top: Path) -> bool:
    try:
        Path(path).relative_to(top)
        return True
    except ValueError:
        return False


def guard(path: Path) -> None:
    """Refuse to create `path` (or its folders) when it lies on a drive that
    is not there. Without this, a save after the drive was pulled re-made
    the drive's folders on the Mac's own disk, and the next start began an
    empty life in them (I-08)."""
    p = Path(path)
    if _under(p, OFFLINE_ROOT):
        raise DriveAway(19, "the Self-Cloud drive is not plugged in")
    roots = set(_SEEN_ROOTS)
    if os.environ.get("SELFCLOUD_ROOT"):
        roots.add(os.environ["SELFCLOUD_ROOT"])
    for r in roots:
        r = Path(r).expanduser()
        if _under(p, r) and not (r / MARKER).is_file():
            raise DriveAway(19, "the Self-Cloud drive is not plugged in")
    for base in MOUNT_BASES:
        b = Path(base)
        if _under(p, b) and p != b:
            first = b / p.relative_to(b).parts[0]
            if not first.exists():
                raise DriveAway(19, "that drive is not plugged in")


# ------------------------------------------------------------------ encryption
_ENC: dict[tuple[str, int], bool | None] = {}


def disk_info(target: str | Path) -> dict:
    """`diskutil info -plist` for a mount point or a device id (macOS), or {}."""
    if platform.system() != "Darwin":
        return {}
    try:
        r = subprocess.run(["diskutil", "info", "-plist", str(target)],
                           capture_output=True, timeout=20)
        return plistlib.loads(r.stdout) if r.returncode == 0 and r.stdout else {}
    except Exception:
        return {}


def encrypted_from(info: dict) -> bool | None:
    """Is the volume `info` describes encrypted? None when it cannot be told.
    A conversion still under way is not encrypted yet."""
    if not info:
        return None
    for k, v in info.items():
        if ("Progress" in k or "Conversion" in k) and v not in (None, "", 0, 100, False):
            if not (isinstance(v, (int, float)) and v >= 100):
                return False
    keys = [k for k in ("FileVault", "Encryption", "Encrypted", "CoreStorageEncrypted")
            if k in info]
    if not keys:
        return None
    return any(info[k] is True or str(info[k]).lower().startswith("yes") for k in keys)


def encrypted(where: str | Path) -> bool | None:
    """Checked, not assumed, once per mount (macOS only; None elsewhere)."""
    if platform.system() != "Darwin":
        return None
    try:
        key = (str(where), os.stat(where).st_dev)
    except OSError:
        return None
    if key not in _ENC:
        _ENC[key] = encrypted_from(disk_info(where))
    return _ENC[key]


def encryption_line() -> str | None:
    """One line for the owner about the drive in use (I-42): never silent."""
    w = locate()
    if w.state != "drive" or platform.system() != "Darwin":
        return None
    e = encrypted(w.root)
    if e is True:
        return "✓ your Self-Cloud drive is encrypted"
    if e is False:
        return ("! your Self-Cloud drive is NOT encrypted: whoever holds it can read "
                "everything on it. Finder → right-click the drive → Encrypt.")
    return "! JEFFEREY could NOT verify that your Self-Cloud drive is encrypted."


# ------------------------------------------------------------------ words
def describe() -> str:
    """For the owner's own screen."""
    w = locate()
    if w.state == "drive":
        return f"on your Self-Cloud drive '{safe_name(w.marker.get('name'), w.root.name)}' ({w.root})"
    if w.state == "laptop":
        return "on this machine (no Self-Cloud drive plugged in)"
    return "nowhere right now: " + (w.reason() or "")


def describe_for_engine() -> str:
    """For a rented engine: never the drive's name, never a path (a name is
    whatever was typed when the drive was made — drive#8)."""
    w = locate()
    if w.state == "drive":
        return "on the owner's Self-Cloud drive"
    if w.state == "laptop":
        return "on the owner's own computer"
    return "nowhere right now (the owner's Self-Cloud drive is not available)"


def announce() -> None:
    """Say once, to stderr, where the life is being kept. Never silent about it."""
    global _ANNOUNCED
    if _ANNOUNCED:
        return
    _ANNOUNCED = True
    w = locate()
    if w.state == "off":
        print(f"  ⚠  JEFFEREY is off: {w.reason()}.", file=sys.stderr)
    else:
        print(f"  Life lives {describe()}.", file=sys.stderr)


def reset_for_tests() -> None:
    global _LAST, _ANNOUNCED
    _LAST, _ANNOUNCED = None, False
    _SEEN_ROOTS.clear()
    _UUIDS.clear()
    _ENC.clear()


# ------------------------------------------------------------------ owner CLI
def status_lines() -> list[str]:
    lines = [f"  Your life lives {describe()}."]
    try:
        recs = paired()
    except PairingDamaged:
        lines.append(f"  ! The list of your drives ({pairing_path()}) is damaged.")
        recs = []
    for d in recs:
        lines.append(f"  · paired: '{d.get('name', '?')}'  id {d['id']}"
                     + (f"  (last seen at {d['mount']})" if d.get("mount") else ""))
    env = _env_ids()
    if env:
        lines.append(f"  · pinned in Claude's settings: {', '.join(sorted(env))}")
    if not recs and not env:
        lines.append("  · no Self-Cloud drive is paired with this Mac")
        try:
            chosen = (_pairing() or {}).get("this_mac")
        except PairingDamaged:
            chosen = False
        if chosen:
            lines.append("  · you chose to keep your memories on this Mac")
    for p, mk in marked_drives():
        mine = mk["id"] in {d["id"] for d in recs} | (env or set())
        lines.append(f"  · plugged in: '{safe_name(mk.get('name'), p.name)}' at {p}  id {mk['id']}"
                     + ("" if mine else "  — NOT paired with this Mac"))
    return lines


def main(argv: list[str]) -> int:
    import answers
    if not argv or argv[0] == "status":
        print("\n" + "\n".join(status_lines()) + "\n")
        return 0
    if argv[0] == "pair" and len(argv) == 2:
        r = Path(argv[1].replace("\\ ", " ")).expanduser()
        mk = read_marker(r)
        if not mk:
            print(f"\n  {r} is not a Self-Cloud drive (no valid marker). Nothing changed.\n"
                  "  To make it one, double-click 'Make this drive a Self-Cloud.command'.\n")
            return 1
        print(f"\n  The drive '{safe_name(mk.get('name'), r.name)}' at {r}, id {mk['id']}.")
        print("  JEFFEREY will keep your life on it and use no other drive you have not said yes to.")
        if not answers.ask_yes_no("  Is this your own Self-Cloud drive? Type yes or no: "):
            print("  Nothing was changed.\n")
            return 1
        pair(r, mk)
        print(f"  ✓ This Mac now knows that drive is yours ({pairing_path()}).")
        print("    Quit Claude completely and open it again so it picks this up.\n")
        return 0
    if argv[0] == "this-mac" and len(argv) == 1:
        print("\n  JEFFEREY will keep your memories on this Mac, in ~/.jefferey, and use no drive.")
        if not answers.ask_yes_no("  Is that what you want? Type yes or no: "):
            print("  Nothing was changed.\n")
            return 1
        try:
            choose_this_mac()
        except ValueError as e:
            print(f"  Nothing was changed: {e}.\n")
            return 1
        print("  ✓ Done.\n")
        return 0
    if argv[0] == "unpair" and len(argv) == 2:
        try:
            recs = [d for d in paired() if d["id"] == argv[1].lower() or d.get("name") == argv[1]]
        except PairingDamaged:
            recs = []
        if not recs:
            print(f"\n  No paired drive is called {argv[1]!r}. Nothing changed.\n")
            return 1
        print(f"\n  This Mac will forget the drive '{recs[0].get('name')}' (id {recs[0]['id']}).")
        print("  Nothing on the drive is touched. If it was your only drive, JEFFEREY keeps")
        print("  your life on this Mac from now on.")
        if not answers.ask_yes_no("  Forget it? Type yes or no: "):
            print("  Nothing was changed.\n")
            return 1
        unpair(argv[1])
        print("  ✓ Done.\n")
        return 0
    print(__doc__.split("Owner commands")[1])
    return 2


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(main(sys.argv[1:]))
