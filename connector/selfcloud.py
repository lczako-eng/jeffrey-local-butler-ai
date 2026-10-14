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
2. **Every decision is logged**, allow or deny, in the owner's own access
   log — an append-only file beside the store (conscience.access.jsonl), on
   the drive when there is one. The audit belongs to them, not to us. It is
   deliberately NOT inside the store: there, every question any engine asked
   rewrote the whole life and pushed a backup copy out of history.
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
    "facts.write":     "may record and erase facts, profile fields and rules",
    "priorities.read": "the learned value hierarchy, with confidence",
    "priorities.write": "may learn new priorities from corrections",
    "goals.read":      "active long-term goals",
    "goals.write":     "may open and close goals, and log observations",
    "life.read":       "the people who matter and recorded moments (private + family)",
    "life.write":      "may record new people and moments",
    "media.read":      "references to photos and recordings on the drive",
    "family.read":     "moments the owner marked shareable with family",
    "legacy.read":     "what the owner meant to outlive them",
    "money.read":      "the charge register and what was flagged",
    "money.write":     "may register charges and flag unauthorized ones",
    "vault.names":     "may learn WHICH secrets exist, never their values",
    # October 2026 (I-06, I-09): two abilities every key used to have, now
    # only the caretaker's.
    "act.request":     "may ask whether an act in the world is allowed (the caretaker)",
    "keys.read":       "may see every key and the record of who asked for what",
    # October 2026 (I-02): reading a PDF form on this computer and saving a
    # filled copy in the 'Filled forms' folder. It was 'facts.read', so every
    # plain guest session could write files anywhere.
    "paperwork.write": "may read PDF forms and save filled copies in the 'Filled forms' folder",
}

# The caretaker preset as it was before act.request and keys.read existed.
# A stored 'jefferey' key that still holds all of it is the untouched default,
# so it is given the two new scopes when it is read (once — see
# migrate_grants). A key the owner had narrowed is left as he made it.
_CARETAKER_V1 = frozenset({
    "facts.read", "facts.write", "priorities.read", "priorities.write",
    "goals.read", "goals.write", "life.read", "life.write", "media.read",
    "family.read", "legacy.read", "money.read", "money.write", "vault.names"})
# ...and as it was before paperwork.write existed (forms were filled under
# facts.read, which the guests held too — I-02).
_CARETAKER_V2 = _CARETAKER_V1 | {"act.request", "keys.read"}
GRANTS_VERSION = 3

# Keys whose every change the owner is told about, in the brief and status.
WATCHED_KEYS = ("jefferey", "family", "executor")
KEY_CHANGES = ("grant", "add_scope", "remove_scope", "revoke")

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
            "facts.read", "facts.write", "priorities.read", "priorities.write",
            "goals.read", "goals.write",
            "life.read", "life.write", "media.read", "family.read", "legacy.read",
            "money.read", "money.write", "vault.names",
            "act.request", "keys.read", "paperwork.write",
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


def migrate_grants(data: dict) -> bool:
    """Keep reading old stores (October 2026). The caretaker preset gained
    act.request and keys.read (v2), then paperwork.write (v3: filling forms
    left facts.read, so the caretaker keeps what it could already do and the
    guests lose it). A stored 'jefferey' key that still holds the whole old
    preset is the untouched default, so it gets them too — once, marked with
    the version, so a scope the owner later removes is never put back. A key
    the owner had narrowed is left exactly as he made it. Changes memory
    only; the next real save keeps it (reading never writes). Returns True
    when something changed."""
    gs = data.get("selfcloud_grants")
    if not isinstance(gs, dict):
        return False
    g = gs.get("jefferey")
    if not isinstance(g, dict) or not isinstance(g.get("scopes"), list):
        return False
    try:
        v = int(g.get("v") or 1)
    except (TypeError, ValueError):
        v = 1
    if v >= GRANTS_VERSION:
        return False
    if v < 2 and _CARETAKER_V1 <= set(g["scopes"]):
        g["scopes"] = sorted(set(g["scopes"]) | {"act.request", "keys.read"})
    if v < 3 and _CARETAKER_V2 <= set(g["scopes"]):
        g["scopes"] = sorted(set(g["scopes"]) | {"paperwork.write"})
    g["v"] = GRANTS_VERSION
    return True


def _access():
    import access            # late: access imports this module lazily too
    return access


class SelfCloud:
    """The owner's access control over their own storage."""

    def __init__(self, conscience):
        self.c = conscience
        self.c.data.setdefault("selfcloud_grants", {})
        migrate_grants(self.c.data)
        # The access log is the conscience's append-only file beside the
        # store (conscience.access_log); entries an older version kept inside
        # the store were moved there when it was read.

    # ------------------------------------------------------------- who asks
    @staticmethod
    def _sees_every_key() -> bool:
        """The owner, his own tools, and a key holding keys.read (only the
        caretaker preset does) see every key and the whole access log. Any
        other key sees only itself (I-09: the family app read every key's
        label — 'for questions about my cancer treatment')."""
        return _access().may("keys.read")

    @staticmethod
    def _me() -> str:
        a = _access()
        return a.who() if a.owners_hands() else a.current_client()

    _DOORS = {"mcp": "through Claude", "http": "through the ChatGPT connection",
              "chat": "in 'Talk to JEFFEREY on this Mac'"}

    def _changed(self, client: str, what: str) -> None:
        """A change to the caretaker, family or executor key is told to the
        owner in the brief and in selfcloud_status, with who made it."""
        if client in WATCHED_KEYS:
            a = _access()
            who = a.who()
            by = ("the owner himself, at his own keyboard" if who == "owner"
                  else "the owner's own tools on this Mac" if who == "local"
                  else f"the AI holding the '{who}' key "
                       f"{self._DOORS.get(a.surface(), '')}".rstrip())
            self.c._note("key_change", f"The '{client}' key was changed: {what}. "
                                       f"Done by {by}.")

    # ---------------------------------------------------------------- grants
    def grant(self, client: str, scopes: list[str] | None = None,
              label: str = "", note: str = "", auto: bool = False) -> dict:
        """Give a client a key. With no scopes given, use the preset for that
        kind of client — a sane starting point the owner can then narrow.
        Only the owner's own hands may do this (`auto` is the gate issuing a
        preset exactly as written, on its first use)."""
        if not auto or scopes:
            _access().require_owners_hands("give out a key")
        client = (client or "").strip().lower()
        if not client:
            return {"granted": False, "error": "a key needs a name"}
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
            "v": GRANTS_VERSION,
        }
        self.c.data["selfcloud_grants"][client] = entry
        if not auto:
            self._changed(client, "it was given out, holding "
                          + (", ".join(entry["scopes"]) or "nothing"))
        self.c._save()
        self._log(client, "grant", ", ".join(entry["scopes"]), True)
        return entry

    def add_scope(self, client: str, scope: str) -> dict:
        """Widen one key by exactly one scope — the owner's decision, never
        the client's. No client may ever call this about itself."""
        _access().require_owners_hands("widen a key")
        client = (client or "").strip().lower()
        g = self.c.data["selfcloud_grants"].get(client)
        if not g:
            return {"error": f"'{client}' has no key. Grant one first."}
        if scope not in SCOPES:
            return {"error": f"unknown scope '{scope}'", "valid_scopes": sorted(SCOPES)}
        if scope in g["scopes"]:
            return g
        g["scopes"] = sorted(set(g["scopes"] + [scope]))
        self._changed(client, f"it was given one more kind of access ({scope}: {SCOPES[scope]})")
        self.c._save()
        self._log(client, "add_scope", scope, True)
        return g

    def remove_scope(self, client: str, scope: str) -> dict:
        """Narrow a key by one scope. A key may narrow itself from anywhere;
        narrowing any OTHER key is the owner's decision (I-09)."""
        client = (client or "").strip().lower()
        _access().require_self_or_owner(client, "selfcloud_remove_scope")
        g = self.c.data["selfcloud_grants"].get(client)
        if not g:
            return {"error": f"'{client}' has no key."}
        if scope not in g["scopes"]:
            return g                       # nothing to change, nothing written
        g["scopes"] = [s for s in g["scopes"] if s != scope]
        self._changed(client, f"one kind of access was taken away ({scope}: "
                              f"{SCOPES.get(scope, 'unknown')})")
        self.c._save()
        self._log(client, "remove_scope", scope, True)
        return g

    def revoke(self, client: str) -> dict:
        """Kill a key. Instant, total, and the record that it existed stays.
        A key may switch itself off from anywhere; switching off any OTHER
        key is the owner's decision (I-09)."""
        client = (client or "").strip().lower()
        _access().require_self_or_owner(client, "selfcloud_revoke")
        g = self.c.data["selfcloud_grants"].get(client)
        if not g:
            return {"revoked": False, "reason": f"'{client}' has no key."}
        g["active"] = False
        g["revoked_on"] = _now()
        self._changed(client, "it was switched off")
        self.c._save()
        self._log(client, "revoke", "all scopes", True)
        return {"revoked": True, "client": client, "on": g["revoked_on"],
                "note": "That key is dead. The record of it stays."}

    def grants(self) -> dict:
        """Every key to this Self-Cloud, live and revoked. The owner should be
        able to read this and understand it without help. A key without
        keys.read sees only its own entry."""
        gs = self.c.data.get("selfcloud_grants", {})
        keys = list(gs.values())
        note = None
        if not self._sees_every_key():
            me = self._me()
            keys = [g for g in keys if g.get("client") == me]
            note = ("This shows only the key this connection holds. Only the "
                    "owner, and his caretaker key, see every key.")
        out = {
            "keys": keys,
            "active": [g["client"] for g in keys if g.get("active")],
            "revoked": [g["client"] for g in keys if not g.get("active")],
            "available_scopes": SCOPES,
            "presets": {k: v["label"] for k, v in PRESETS.items()},
        }
        if note:
            out["note"] = note
        return out

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
                       "owner_can": f"type /scope add {client} {scope} in 'Talk to "
                                    f"JEFFEREY on this Mac'"}
        else:
            verdict = {"allowed": True, "client": client, "scope": scope,
                       "reason": "granted by the owner"}
        if log:
            self._log(client, "check", scope, verdict["allowed"])
        return verdict

    def ask_access(self, client: str, scope: str) -> dict:
        """The tool's question: 'would this client be allowed this scope?'
        Answered for the caller's own key, or — for the owner and the
        caretaker key — for any key. Written down under who ASKED, with the
        key asked about as the detail: it used to be written as if the other
        key had tried, so the log blamed the wrong one (I-09)."""
        client = (client or "").strip().lower()
        me = self._me()
        if client != me and not self._sees_every_key():
            self._log(me, "asked_about", f"{client}: {scope}", False, actor=me)
            return {"allowed": None, "client": client, "scope": scope,
                    "reason": "This connection may only ask about its own key "
                              f"('{me}'). Only the owner sees the other keys."}
        verdict = self.check_access(client, scope, log=False)
        self._log(me, "asked_about", f"{client}: {scope}", True, actor=me)
        return verdict

    def access_log(self, limit: int = 30) -> list[dict]:
        """Who asked for what, and what happened. The owner's record. Between
        1 and 200 entries (0 or a negative number used to return all of
        them); a key without keys.read sees only its own lines."""
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 30
        limit = max(1, min(200, limit))
        if self._sees_every_key():
            return self.c.access_log.tail(limit)
        me = self._me()
        mine = [e for e in self.c.access_log.tail(2000)
                if e.get("client") == me or e.get("actor") == me]
        return mine[:limit]

    def _log(self, client: str, action: str, detail: str, allowed: bool,
             actor: str | None = None) -> None:
        """One line appended to the access log. Never a write of the store:
        a question — allowed or refused — must not rewrite the owner's life
        or use up a backup copy. `client` is the key the line is ABOUT;
        `actor` is who did it (I-09: a revocation used to be written down
        under the victim's name, not the culprit's)."""
        try:
            a = _access()
            actor = actor or a.who()
            where = a.surface()
        except Exception:
            actor, where = actor or "unknown", "unknown"
        self.c.access_log.append({
            "client": client, "actor": actor, "surface": where, "action": action,
            "detail": detail, "allowed": bool(allowed), "at": _now(),
        })

    # ---------------------------------------------------------------- status
    def key_changes(self) -> list[dict]:
        """Recent changes to the caretaker, family and executor keys."""
        return [n for n in self.c.notices() if "' key was changed:" in str(n.get("what"))]

    def status(self) -> dict:
        gs = self.c.data.get("selfcloud_grants", {})
        principle = (
            "Self-Cloud belongs to the owner. JEFFEREY is a caretaker with a "
            "key, not the owner of the vault. Unknown clients get nothing, "
            "every decision is logged, revocation is instant — and when the "
            "drive is switched off, none of it is reachable by anyone.")
        if not self._sees_every_key():
            me = self._me()
            g = gs.get(me)
            return {
                "your_key": ({k: g.get(k) for k in ("client", "label", "scopes", "active",
                                                     "granted_on", "revoked_on")}
                             if isinstance(g, dict) else {"client": me, "active": False}),
                "principle": principle,
                "note": ("This shows only the key this connection holds. Only the "
                         "owner, and his caretaker key, see every key."),
            }
        denials = [a for a in self.c.access_log.tail(500)
                   if a.get("action") == "check" and not a.get("allowed")]
        return {
            "keys_issued": len(gs),
            "active_keys": [g["client"] for g in gs.values() if g["active"]],
            "revoked_keys": [g["client"] for g in gs.values() if not g["active"]],
            "recent_denials": denials[:5],          # newest first
            "key_changes": self.key_changes(),
            "principle": principle,
        }
