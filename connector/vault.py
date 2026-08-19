"""
JEFFEREY Vault — secrets the provider holds, not Jefferey
=========================================================

The answer to "he's supposed to look out for me but can't hold anything":
he doesn't have to hold it. **The operating system already does.**

Secrets live in the platform's own credential store — macOS Keychain
(Secure Enclave-backed), Windows Credential Manager, Linux Secret Service /
GNOME Keyring, and on phones iOS Keychain / Android Keystore with Face ID or
fingerprint. Jefferey never stores them, and — this is the part that matters
— **never sees them**.

Two rules make that true, and they are enforced here, not promised:

1. **Secrets never enter the AI's context.** You never type a secret into the
   chat. You store it out of band, from your own terminal:

       python connector/vault.py set sin

   which prompts privately (no echo, no history) and hands it straight to the
   OS store. The model is not in that path.

2. **Jefferey uses secrets by REFERENCE, never by value.** He writes the
   token `vault:sin` into a form field. Local code on your machine resolves
   that token at the moment of writing. The value goes from the OS keychain
   into your PDF — it never travels to Anthropic, OpenAI, or us.

So Jefferey can complete the whole government form, every year, including
the box he isn't allowed to know. He orchestrates; the platform custodies;
the secret never leaves your hardware.

CLI (all local, none of it visible to the model):
    python connector/vault.py set <name>       store a secret (prompts privately)
    python connector/vault.py list             names only
    python connector/vault.py get <name>       show it to YOURSELF
    python connector/vault.py delete <name>    remove it
    python connector/vault.py status           which platform store is in use
"""

from __future__ import annotations

import re
import sys

SERVICE = "jefferey-vault"          # namespace inside the platform store
INDEX_KEY = "__index__"             # names we've stored (names only, no values)
REF = re.compile(r"^vault:([a-z0-9_.-]{1,64})$", re.I)


class VaultUnavailable(RuntimeError):
    """No platform credential store on this machine."""


def _kr():
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring
    except ImportError:
        raise VaultUnavailable(
            "the keyring library is missing — run: pip install keyring"
        )
    backend = keyring.get_keyring()
    if isinstance(backend, FailKeyring):
        raise VaultUnavailable(
            "no platform credential store found on this machine. macOS and "
            "Windows have one built in; on Linux install gnome-keyring or "
            "KWallet. Jefferey will never fall back to writing secrets to a "
            "plain file."
        )
    return keyring


def backend_name() -> str:
    kr = _kr()
    b = kr.get_keyring()
    friendly = {
        "macOS": "Apple Keychain (macOS)",
        "Windows": "Windows Credential Manager",
        "SecretService": "Secret Service (GNOME Keyring / KWallet)",
        "kwallet": "KDE KWallet",
        "chainer": "platform keychain",
    }
    mod = b.__class__.__module__.rsplit(".", 1)[-1]
    return friendly.get(mod, f"{b.__class__.__module__}.{b.__class__.__name__}")


# ------------------------------------------------------------------ index
# The platform store holds the values. We keep only the NAMES, so Jefferey
# can say "your SIN is in the vault" without ever holding what it is.
def _index() -> list[str]:
    kr = _kr()
    raw = kr.get_password(SERVICE, INDEX_KEY) or ""
    return [n for n in raw.split("\x1f") if n]


def _write_index(names: list[str]) -> None:
    _kr().set_password(SERVICE, INDEX_KEY, "\x1f".join(sorted(set(names))))


# ------------------------------------------------------------------ api
def store(name: str, value: str) -> dict:
    """Put a secret in the platform store. Called ONLY from the local CLI —
    never from a tool the model can reach, so the value has no path into an
    AI context."""
    name = name.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{1,64}", name):
        raise ValueError("name must be letters, digits, dot, dash, underscore")
    kr = _kr()
    kr.set_password(SERVICE, name, value)
    _write_index(_index() + [name])
    return {"stored": name, "where": backend_name()}


def names() -> list[str]:
    """What Jefferey is allowed to know: that these secrets exist."""
    try:
        return _index()
    except VaultUnavailable:
        return []


def has(name: str) -> bool:
    return name.strip().lower() in names()


def resolve(value: str) -> str | None:
    """Turn `vault:sin` into the actual secret — on this machine only, at the
    moment of writing. Returns None if it isn't a reference token."""
    m = REF.match(str(value).strip())
    if not m:
        return None
    return _kr().get_password(SERVICE, m.group(1).lower())


def is_reference(value: str) -> bool:
    return bool(REF.match(str(value).strip()))


def delete(name: str) -> dict:
    kr = _kr()
    name = name.strip().lower()
    try:
        kr.delete_password(SERVICE, name)
    except Exception:
        pass
    _write_index([n for n in _index() if n != name])
    return {"deleted": name}


def status() -> dict:
    """Safe to show the model: where secrets live and which names exist —
    never a value."""
    try:
        return {
            "available": True,
            "store": backend_name(),
            "secrets": names(),
            "how_jefferey_uses_them": (
                "By reference only. He writes `vault:<name>` into a field; "
                "local code on this machine resolves it at write time. The "
                "value never enters an AI context or crosses the network."
            ),
            "how_to_add": "The user runs: python connector/vault.py set <name>",
        }
    except VaultUnavailable as e:
        return {"available": False, "reason": str(e), "secrets": []}


# ------------------------------------------------------------------ cli
def _main(argv: list[str]) -> int:
    import getpass

    cmd = argv[1] if len(argv) > 1 else "status"
    try:
        if cmd == "set":
            if len(argv) < 3:
                print("usage: vault.py set <name>")
                return 2
            name = argv[2]
            v1 = getpass.getpass(f"Value for '{name}' (hidden): ")
            if not v1:
                print("empty — nothing stored.")
                return 1
            v2 = getpass.getpass("Again to confirm: ")
            if v1 != v2:
                print("they don't match — nothing stored.")
                return 1
            r = store(name, v1)
            print(f"Stored '{r['stored']}' in {r['where']}.")
            print(f"Jefferey can now use it as: vault:{r['stored']}")
            print("He can see the name. He can never see the value.")
        elif cmd == "list":
            ns = names()
            print("\n".join(ns) if ns else "(vault empty)")
        elif cmd == "get":
            if len(argv) < 3:
                print("usage: vault.py get <name>")
                return 2
            v = _kr().get_password(SERVICE, argv[2].strip().lower())
            print(v if v is not None else "(not found)")
        elif cmd == "delete":
            print(delete(argv[2])["deleted"] + " deleted.")
        else:
            s = status()
            if s["available"]:
                print(f"Vault: {s['store']}")
                print(f"Secrets stored: {', '.join(s['secrets']) or '(none)'}")
            else:
                print("Vault unavailable — " + s["reason"])
                return 1
    except VaultUnavailable as e:
        print("Vault unavailable — " + str(e))
        return 1
    except Exception as e:
        print(f"error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
