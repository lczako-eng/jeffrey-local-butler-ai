"""
SELF-CLOUD — the vault, and who gets a key
==========================================

Self-Cloud is its own product. It is not "where Jefferey keeps his stuff" —
it is the person's own storage and compute, and **Jefferey is one caretaker
among several**, holding a key the owner granted and can take back.

Different AI clients get different keys:

    claude-raw   a plain Claude session. Useful, not intimate. Read the
                 facts and priorities it needs to be helpful — nothing of
                 the person's life, no media, no legacy.
    gpt-raw      the same, for a plain ChatGPT session.
    jefferey     the wrapped connector: the personable one, the friend.
                 The caretaker. Reads and writes the conscience, holds the
                 life layer, guards the money, and is trusted with legacy.
    family       a person the owner names — reads what was marked `family`,
                 writes nothing.
    executor     after death or incapacity: reads `legacy` only. Nothing
                 else, ever.

Three properties make this a vault rather than a promise:

1. **Deny by default.** An unknown client gets nothing. A known client gets
   exactly its granted scopes and not one scope more.
2. **Every decision is logged**, allow or deny, in the owner's own store.
   The audit belongs to them, not to us.
3. **Revocation is instant and total** — `revoke('gpt-raw')` and that key
   is dead, with the record of it having existed left intact.

The physical switch is still the final word: when the drive is off, none of
this is reachable by anyone, which is the point of owning it.
"""

from __future__ import annotations

import time

# The scopes a key can carry. Deliberately small and readable — a person
# should be able to look at their own grants and understand them.
SCOPES = {
    "facts.read":      "durable facts about the owner (dates, constraints, situations)",
    "priorities.read": "the learned value hierarchy, with confidence",
    "priorities.write": "may learn new priorities from corrections",
    "goals.read":      "active long-term goals",
    "life.read":       "the people who matter and recorded moments (private + family)",
    "life.write":      "may record new people and moments",
    "media.read":      "references to photos and recordings on the drive",
    "family.read":     "moments the owner marked shareable with family",
    "legacy.read":     "what the owner meant to outlive them",
    "money.read":      "the charge register and what was flagged",
    "money.write":     "may register charges and flag unauthorized ones",
    "vault.names":     "may learn WHICH secrets exist, never their values",
}

# What each kind of client gets when the owner adds it. Starting points,
# not fixed law — every scope can be added or removed one at a time.
PRESETS: dict[str, dict] = {
    "claude-raw": {
        "label": "Claude (plain session)",
        "scopes": ["facts.read", "priorities.read", "goals.read"],
        "why": "Helpful, not intimate. It can serve the owner well without "
               "being handed their life.",
    },
    "gpt-raw": {
        "label": "ChatGPT (plain session)",
        "scopes": ["facts.read", "priorities.read", "goals.read"],
        "why": "Same as any other rented engine: useful, kept at arm's length.",
    },
    "jefferey": {
        "label": "Jefferey (the wrapped connector — the caretaker)",
        "scopes": [
            "facts.read", "priorities.read", "priorities.write", "goals.read",
            "life.read", "life.write", "media.read", "family.read", "legacy.read",
            "money.read", "money.write", "vault.names",
        ],
        "why": "The one who represents the owner. Trusted with the life layer "
               "and the money — never with the secrets themselves.",
    },
    "family": {
        "label": "A family member the owner named",
        "scopes": ["family.read", "media.read"],
        "why": "Sees what was deliberately marked shareable. Writes nothing.",
    },
    "executor": {
        "label": "Executor / inheritor",
        "scopes": ["legacy.read"],
        "why": "For after. Only what the owner meant to outlive them — "
               "nothing private, nothing operational.",
    },
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class SelfCloud:
    """The owner's access control over their own storage."""

    def __init__(self, conscience):
        self.c = conscience
        self.c.data.setdefault("selfcloud_grants", {})
        self.c.data.setdefault("selfcloud_access_log", [])

    # ---------------------------------------------------------------- grants
    def grant(self, client: str, scopes: list[str] | None = None,
              label: str = "", note: str = "") -> dict:
        """Give a client a key. With no scopes given, use the preset for that
        kind of client — a sane starting point the owner can then narrow."""
        client = client.strip().lower()
        preset = PRESETS.get(client, {})
        chosen = list(scopes) if scopes else list(preset.get("scopes", []))
        unknown = [s for s in chosen if s not in SCOPES]
        if unknown:
            return {"granted": False, "unknown_scopes": unknown,
                    "valid_scopes": sorted(SCOPES)}
        entry = {
            "client": client,
            "label": label or preset.get("label", client),
            "scopes": sorted(set(chosen)),
            "note": note or preset.get("why", ""),
            "active": True, "granted_on": _now(), "revoked_on": None,
        }
        self.c.data["selfcloud_grants"][client] = entry
        self._log(client, "grant", ", ".join(entry["scopes"]), True)
        return entry

    def add_scope(self, client: str, scope: str) -> dict:
        """Widen one key by exactly one scope — the owner's decision, never
        the client's. No client may ever call this about itself."""
        client = client.strip().lower()
        g = self.c.data["selfcloud_grants"].get(client)
        if not g:
            return {"error": f"'{client}' has no key. Grant one first."}
        if scope not in SCOPES:
            return {"error": f"unknown scope '{scope}'", "valid_scopes": sorted(SCOPES)}
        g["scopes"] = sorted(set(g["scopes"] + [scope]))
        self._log(client, "add_scope", scope, True)
        return g

    def remove_scope(self, client: str, scope: str) -> dict:
        client = client.strip().lower()
        g = self.c.data["selfcloud_grants"].get(client)
        if not g:
            return {"error": f"'{client}' has no key."}
        g["scopes"] = [s for s in g["scopes"] if s != scope]
        self._log(client, "remove_scope", scope, True)
        return g

    def revoke(self, client: str) -> dict:
        """Kill a key. Instant, total, and the record that it existed stays."""
        client = client.strip().lower()
        g = self.c.data["selfcloud_grants"].get(client)
        if not g:
            return {"revoked": False, "reason": f"'{client}' has no key."}
        g["active"] = False
        g["revoked_on"] = _now()
        self._log(client, "revoke", "all scopes", True)
        return {"revoked": True, "client": client, "on": g["revoked_on"],
                "note": "That key is dead. The record of it stays."}

    def grants(self) -> dict:
        """Every key to this Self-Cloud, live and revoked. The owner should be
        able to read this and understand it without help."""
        gs = self.c.data.get("selfcloud_grants", {})
        return {
            "keys": list(gs.values()),
            "active": [g["client"] for g in gs.values() if g["active"]],
            "revoked": [g["client"] for g in gs.values() if not g["active"]],
            "available_scopes": SCOPES,
            "presets": {k: v["label"] for k, v in PRESETS.items()},
        }

    # ---------------------------------------------------------------- checks
    def check_access(self, client: str, scope: str, log: bool = True) -> dict:
        """The gate. Deny by default; a known client gets exactly what it was
        granted. Every decision — allowed or refused — is written down."""
        client = client.strip().lower()
        g = self.c.data.get("selfcloud_grants", {}).get(client)
        if g is None:
            verdict = {"allowed": False, "client": client, "scope": scope,
                       "reason": "no key: this client has never been granted access"}
        elif not g["active"]:
            verdict = {"allowed": False, "client": client, "scope": scope,
                       "reason": f"key revoked on {g['revoked_on']}"}
        elif scope not in g["scopes"]:
            verdict = {"allowed": False, "client": client, "scope": scope,
                       "reason": f"'{scope}' is not in this key ({', '.join(g['scopes']) or 'no scopes'})",
                       "owner_can": f"add it with add_scope('{client}', '{scope}')"}
        else:
            verdict = {"allowed": True, "client": client, "scope": scope,
                       "reason": "granted by the owner"}
        if log:
            self._log(client, "check", scope, verdict["allowed"])
        return verdict

    def access_log(self, limit: int = 30) -> list[dict]:
        """Who asked for what, and what happened. The owner's record."""
        return self.c.data.get("selfcloud_access_log", [])[-limit:][::-1]

    def _log(self, client: str, action: str, detail: str, allowed: bool) -> None:
        self.c.data.setdefault("selfcloud_access_log", []).append({
            "client": client, "action": action, "detail": detail,
            "allowed": bool(allowed), "at": _now(),
        })
        self.c._save()

    # ---------------------------------------------------------------- status
    def status(self) -> dict:
        gs = self.c.data.get("selfcloud_grants", {})
        denials = [a for a in self.c.data.get("selfcloud_access_log", [])
                   if a["action"] == "check" and not a["allowed"]]
        return {
            "keys_issued": len(gs),
            "active_keys": [g["client"] for g in gs.values() if g["active"]],
            "revoked_keys": [g["client"] for g in gs.values() if not g["active"]],
            "recent_denials": denials[-5:][::-1],
            "principle": (
                "Self-Cloud belongs to the owner. Jefferey is a caretaker with a "
                "key, not the owner of the vault. Unknown clients get nothing, "
                "every decision is logged, revocation is instant — and when the "
                "drive is switched off, none of it is reachable by anyone."
            ),
        }
