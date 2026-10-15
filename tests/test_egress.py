"""
The egress door and the secret scan — regression tests for the October 2026
stress test.

    I-07  the scan missed French and natural phrasings, separated digits and
          house codes, so passwords, PINs, cards and alarm codes were stored
          and handed to every AI
    I-14  the inbound scan blocked the scam check on exactly the messages
          that quote a card, a SIN, a code or a password, and told the AI to
          stop
    I-15  photo fingerprints (sha256) looked like SIN or card numbers, which
          jammed the album and blocked 'who am I' and 'tell my story'
    I-58  driver's licence and passport numbers were stored in the profile
          and released to plain guest sessions
    I-67  a short write to the egress log counted as success: data left while
          its log entry was torn, and the next entry was lost with it

Every test makes its own temporary folder and environment and reaches
JEFFEREY the way an engine does — the terminal's dispatch_tool, the MCP
server's call_tool, or the HTTP routes — in a subprocess, so nothing here
touches the real home folder (HOME is a throwaway folder, checked empty).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONNECTOR = ROOT / "connector"
PY = sys.executable

TA = "tokA-jefferey-0123456789abcdefghijklmn"
TG = "tokG-gptraw-0123456789abcdefghijklmnop"
TC = "tokC-claude-0123456789abcdefghijklmnop"
TOKENS = f"jefferey:{TA},gpt-raw:{TG},claude-raw:{TC}"

PRELUDE = f"""
import sys, os, json, asyncio
sys.path.insert(0, {str(CONNECTOR)!r})
def mcp_call(m, name, args=None):
    r = asyncio.run(m.mcp.call_tool(name, args or {{}}))
    items = [json.loads(c.text) for c in r.content]
    return items[0] if len(items) == 1 else items
def out(obj):
    print("RESULT " + json.dumps(obj, default=str))
def H(tok):
    return {{"Authorization": "Bearer " + tok}}
def seed(conscience_path, facts=(), profile=None, memories=()):
    # What an owner's file can already hold: written before the scan knew
    # these shapes, or by hand. Straight into the store, not through a door.
    from conscience import Conscience
    from life import Life
    c = Conscience(conscience_path)
    for f in facts:
        c.remember_fact(f)
    for k, v in (profile or {{}}).items():
        c.data.setdefault("profile", {{}})[k] = v
    for text, photos in memories:
        Life(c).add_memory(text, photos=list(photos))
    c._save()
"""

# A test keychain: the vault needs one, and a test must never touch the real one.
TEST_KEYCHAIN = """
import keyring
from keyring.backend import KeyringBackend
class FileKeychain(KeyringBackend):
    priority = 1
    path = os.environ["TEST_KEYCHAIN"]
    def _all(self):
        return json.load(open(self.path)) if os.path.exists(self.path) else {}
    def get_password(self, service, user):
        return self._all().get(service + "/" + user)
    def set_password(self, service, user, value):
        d = self._all(); d[service + "/" + user] = value
        json.dump(d, open(self.path, "w"))
    def delete_password(self, service, user):
        d = self._all(); d.pop(service + "/" + user, None)
        json.dump(d, open(self.path, "w"))
keyring.set_keyring(FileKeychain())
"""


# ------------------------------------------------- the scan before October 2026
# Kept here only to prove that each regression case below failed on the old
# code: these are the old patterns, word for word.
def _old_luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


_OLD_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_OLD_SIN = re.compile(r"(?<!\d)\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)")
_OLD_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_OLD_PASSWORD = re.compile(
    r"(?i)\b(?:password|passcode|passphrase|pin|cvv|cvc|security code)\b\s*(?:is|[:=])\s*\S+")
_OLD_APIKEY = re.compile(
    r"\b(?:sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
    r"|ghp_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,})")


def old_looks_secret(text: str):
    if not isinstance(text, str) or len(text) < 6:
        return None
    if _OLD_APIKEY.search(text):
        return "an API key"
    if _OLD_PASSWORD.search(text):
        return "a password or PIN"
    if _OLD_SSN.search(text):
        return "a social security number"
    for m in _OLD_CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _old_luhn(digits):
            return "a card number"
    for m in _OLD_SIN.finditer(text):
        if _old_luhn(re.sub(r"\D", "", m.group())):
            return "a social insurance number"
    return None


def tripping_photo_ids(n: int = 6) -> list[str]:
    """Real sha256 fingerprints that the OLD scan took for a SIN or a card:
    the one from the stress test, and the first few of a fixed sequence."""
    out = ["815ff0866af79143ee84f279968069f346e18a8980c4cbd733728fc208279b25"]
    i = 0
    while len(out) < n:
        h = hashlib.sha256(f"photo-{i}".encode()).hexdigest()
        if old_looks_secret(h):
            out.append(h)
        i += 1
    return out


# Every phrasing the testers reproduced (I-07, I-58), and the shapes the
# report names. The old scan let each of these through.
LEAKED_BEFORE = [
    "Mon mot de passe Desjardins est Soleil2024",
    "mon NIP est 4321",
    "Mon NIP est 4821",
    "Le code de l'alarme est 4821",
    "Le code de l\u2019alarme est 4821",
    "mot de passe: Soleil2024",
    "mdp = Soleil2024",
    "code d'accès: 4821",
    "Mein Passwort ist Tulipe2024!",
    "Mi contraseña es Tulipe2024!",
    "A jelszavam Tulipe2024!",
    "My alarm code is 4821",
    "The door code is 7392",
    "My password's Hunter2024",
    "My PIN 4821",
    "my pin 4821",
    "PIN 4821",
    "my bank PIN 4821",
    "My password for Desjardins is Tulipe2024!",
    "online banking password hunter22",
    "my password hunter2xx",
    "the wifi password hunter22",
    "pwd=hunter22",
    "The garage door code is 4821",
    "Alarm code: 7731",
    "Lockbox combination 1234",
    "Keypad code for the front door 0937",
    "wifi: BlueHouse2020",
    "Gate code is #2580",
    "The lockbox code is 5512 for the nurse",
    "4821 is my PIN",
    "card 4111.1111.1111.1111",
    "4111.1111.1111.1111",
    "4111\n1111\n1111\n1111",
    "4111  1111  1111  1111",
    "4111/1111/1111/1111",
    "4111 - 1111 - 1111 - 1111",
    "4111\u00a01111\u00a01111\u00a01111",
    "4111\u200b1111\u200b1111\u200b1111",
    "\uff14\uff11\uff11\uff11 \uff11\uff11\uff11\uff11 \uff11\uff11\uff11\uff11 \uff11\uff11\uff11\uff11",
    "\u0664\u0661\u0661\u0661\u0661\u0661\u0661\u0661\u0661\u0661\u0661\u0661\u0661\u0661\u0661\u0661",
    "SIN 046.454.286",
    "my SIN is 046.454.286",
    "SIN is 046/454/286",
    "NAS: 046.454.286",
    "SSN 078 05 1120",
    "IBAN GB82 WEST 1234 5698 7654 32",
    "transit 00123 inst 004 acct 1234567",
    "OHIP 1234-567-890-AB",
    "health card 1234-567-890-AB",
    "passport number GA123456",
    "Passport number AB123456",
    "Driver's licence number C6101-40706-60905",
    "sk-ant-api03 abcdefghijklmnop",
    "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
    "sk_live_abcdefghijklmnop1234",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----",
]

# Ordinary words the door must not mistake for a secret — several of them
# the old scan did (I-14), and the photo fingerprints (I-15).
NOT_SECRETS = [
    "call 416 555 0199 before June 12 2026",
    "the pin is in the drawer",
    "Your password is about to expire. Click http://bit.ly/x",
    "Password: (type it here)",
    "Dad's Legion pin is gold",
    "He gave me his Legion pin in 1985",
    "The door code changed in 2019",
    "postal code is K1A 0B1",
    "area code is 613",
    "Your order #4532015112830366 has shipped",
    "Ref 4532015112830366",
    "tracking 4532015112830366",
    "1Z999AA10123456784",
    "My NAS is at 192.168.1.20",
    "IMG_4821.jpg",
    "Meet at 10:30 on 2026-10-14",
    "Pay $1,234,567.89 by Friday",
    "1791987326.2183764",
    "550e8400-e29b-41d4-a716-446655440000",
    "Password: vault:password",
    "PIN: vault:pin",
    "types the code K7Q3MT (in JEFFEREY's own terminal: /approve K7Q3MT)",
    "[hidden: looks like a card number]",
]

# Scam messages that quote a secret: the old door refused to check them.
SCAMS = {
    "sin": ("Service Canada", "Your SIN has been suspended",
            "URGENT: your SIN 046 454 286 was used in a crime. Call immediately or "
            "a warrant will be issued for your arrest."),
    "gift": ("Amazon Support", "Refund pending",
             "Your refund is pending. Buy two Google Play cards and send the codes. "
             "Ref 4532015112830366. Act now, do not tell your bank."),
    "otp": ("Interac", "Verification",
            "Interac: your security code is 551203. If you did not request it, call "
            "1-833-555-0100 immediately and read us the code."),
    "expire": ("IT desk", "Mailbox",
               "Your password is about to expire. Click here to verify your account "
               "within 24 hours."),
    "card": ("Visa Security", "Fraud alert",
             "We detected fraud on card 4111 1111 1111 1111. Verify your account "
             "immediately by replying with your PIN."),
}


class EgressTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jf-egress-"))
        (self.tmp / "home").mkdir()
        self.store = self.tmp / "conscience.json"
        self.egress = self.tmp / "egress.jsonl"

    def tearDown(self):
        left = list((self.tmp / "home").rglob("*"))
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.assertEqual(left, [], "something wrote into the home folder")

    def env(self, **extra) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("JEFFEREY_", "SELFCLOUD_"))}
        env.update(HOME=str(self.tmp / "home"),
                   JEFFEREY_CONSCIENCE_PATH=str(self.store),
                   JEFFEREY_EGRESS=str(self.egress),
                   JEFFEREY_DOOR=str(self.tmp / "door-shut"),
                   SELFCLOUD_INDEX=str(self.tmp / "photo-index"),
                   SELFCLOUD_VOICE=str(self.tmp / "voice"),
                   SELFCLOUD_DISCS=str(self.tmp / "discs"),
                   TEST_KEYCHAIN=str(self.tmp / "keychain.json"),
                   PYTHONDONTWRITEBYTECODE="1")
        env.update({k: str(v) for k, v in extra.items()})
        return env

    def py(self, code: str, **extra):
        p = subprocess.run([PY, "-c", PRELUDE + textwrap.dedent(code)],
                           env=self.env(**extra), cwd=self.tmp,
                           capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            raise AssertionError(f"subprocess failed:\n{p.stdout}\n{p.stderr}")
        results = [l[7:] for l in p.stdout.splitlines() if l.startswith("RESULT ")]
        return json.loads(results[-1]) if results else None

    def log_text(self) -> str:
        return self.egress.read_text(encoding="utf-8") if self.egress.exists() else ""

    def store_text(self) -> str:
        return self.store.read_text(encoding="utf-8") if self.store.exists() else ""


# ======================================================================= I-07
class TheScanKnowsHowPeopleWriteSecrets(EgressTest):
    """I-07 (accessibility#0, business#8, learning#6, adversarial#2, egress#2,
    privacy#7, house#2, paperwork#2)."""

    def test_every_reproduced_phrasing_is_caught_and_ordinary_words_are_not(self):
        r = self.py("""
            import egress
            out({"pos": {s: egress.looks_secret(s) for s in %r},
                 "neg": {s: egress.looks_secret(s) for s in %r},
                 "int": egress._scan({"card": 4111111111111111})})
        """ % (LEAKED_BEFORE, NOT_SECRETS))
        missed = [s for s, why in r["pos"].items() if not why]
        self.assertEqual(missed, [], "still let through")
        wrong = {s: why for s, why in r["neg"].items() if why}
        self.assertEqual(wrong, {}, "ordinary words taken for a secret")
        # a card number that arrives as a JSON number is scanned too
        self.assertEqual(r["int"], ["card", "a card number"])
        # ...and the old scan really did let these through (the regression)
        self.assertTrue(any(old_looks_secret(s) is None for s in LEAKED_BEFORE))
        self.assertIsNone(old_looks_secret("Mon mot de passe Desjardins est Soleil2024"))
        self.assertIsNone(old_looks_secret("4111.1111.1111.1111"))

    def test_a_french_password_is_refused_on_every_surface_and_never_stored(self):
        fr = "Mon mot de passe Desjardins est Soleil2024"
        r = self.py("""
            import jefferey_chat as jc
            chat = jc.dispatch_tool("remember_fact", {"fact": %r})
            import jefferey_mcp as m
            mcp = mcp_call(m, "remember_fact", {"fact": %r})
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            x = c.post("/facts", json={"fact": %r}, headers=H(%r))
            out({"chat": chat, "mcp": mcp, "http": [x.status_code, x.json()]})
        """ % (fr, fr, TOKENS, fr, TA), JEFFEREY_CLIENT="jefferey")
        self.assertTrue(r["chat"]["refused"] and "nothing was stored" in r["chat"]["reason"])
        self.assertTrue(r["mcp"]["refused"])
        self.assertEqual(r["http"][0], 403)
        self.assertIn("vault", r["chat"]["reason"])
        self.assertNotIn("stop", r["chat"]["tell_the_user"])
        self.assertNotIn("Soleil2024", self.store_text())
        self.assertNotIn("Soleil2024", self.log_text())

    def test_house_codes_and_dotted_numbers_are_refused_too(self):
        r = self.py("""
            import jefferey_chat as jc
            out({s: jc.dispatch_tool("remember_fact", {"fact": s}).get("refused", False)
                 for s in ["The garage door code is 4821", "Alarm code: 7731",
                           "Lockbox combination 1234", "Keypad code for the front door 0937",
                           "wifi: BlueHouse2020", "Visa card 4111.1111.1111.1111 exp 09/29",
                           "my SIN is 046.454.286", "Le code de l'alarme est 4821",
                           "My birthday is June 12 and Anna calls on Sundays"]})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertFalse(r.pop("My birthday is June 12 and Anna calls on Sundays"))
        self.assertEqual([s for s, refused in r.items() if not refused], [])
        for v in ("4821", "7731", "0937", "BlueHouse2020", "4111.1111", "046.454.286"):
            self.assertNotIn(v, self.store_text())
            self.assertNotIn(v, self.log_text())

    def test_the_owner_typing_a_french_pin_at_his_terminal_keeps_it_home(self):
        r = self.py("""
            import egress
            egress.bind("chat")
            res = {}
            for s in ["mon NIP est 4321", "mot de passe: Soleil2024", "my alarm code is 4821"]:
                try:
                    egress.release_text("you_said", s)
                    res[s] = "sent"
                except egress.EgressRefused:
                    res[s] = "kept"
            out(res)
        """)
        self.assertEqual(set(r.values()), {"kept"}, r)
        for v in ("4321", "Soleil2024", "4821"):
            self.assertNotIn(v, self.log_text())

    def test_profile_values_are_scanned_not_only_their_names(self):
        r = self.py("""
            import jefferey_chat as jc
            res = {f: jc.dispatch_tool("set_profile_field", {"field": f, "value": v})
                   for f, v in [("notes", "4111.1111.1111.1111"), ("alarm code", "4821"),
                                ("house code", "4821"), ("bank login", "laszlo / Hunter22!"),
                                ("misc", "046.454.286"), ("city", "Ottawa")]}
            out({"res": res, "profile": jc.dispatch_tool("get_profile", {})})
        """, JEFFEREY_CLIENT="jefferey")
        # round 8 (S2): from an AI an ordinary detail is kept, waiting beside his
        # own (pending); a secret-shaped one is not kept at all
        kept = {f: bool(x.get("stored") or x.get("pending")) for f, x in r["res"].items()}
        self.assertEqual(kept.pop("city"), True)
        self.assertEqual([f for f, ok in kept.items() if ok], [], r["res"])
        self.assertEqual(r["profile"], {"noted_by_ai_not_confirmed": {"city": {
            "value": "Ottawa", "noted_by": "noted by the AI, not yet confirmed by him"}}})
        for v in ("4111", "4821", "Hunter22", "046.454.286"):
            self.assertNotIn(v, self.store_text())
        self.assertIn("vault", r["res"]["house code"]["reason"])

    def test_a_secret_already_stored_never_leaves_and_does_not_black_out_the_rest(self):
        """An owner's existing file, written before the scan knew French or
        dotted numbers: every engine gets the rest, with the secret hidden in
        place and a plain note — and the file itself is not changed."""
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"],
                 facts=["Le code de l'alarme est 4821", "Anna visits on Sundays",
                        "Visa 4111.1111.1111.1111 exp 09/29"],
                 profile={"alarm_code": "4821", "city": "Ottawa",
                          "drivers_licence": "C6101-40706-60905"})
        """)
        before = json.loads(self.store_text())
        r = self.py("""
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            con = c.get("/conscience", headers=H(%r))
            pro = c.get("/profile", headers=H(%r))
            out({"conscience": [con.status_code, con.json()],
                 "profile": [pro.status_code, pro.json()]})
        """ % (TOKENS, TG, TG))
        self.assertEqual(r["conscience"][0], 200, r)
        facts = [f["fact"] for f in r["conscience"][1]["facts"]]
        self.assertIn("Anna visits on Sundays", facts)
        # (Life package, October 2026, I-11: a fact about the safety of his
        # home is private now, so a guest key is not sent it at all — this
        # used to expect it here with the code hidden. The card line still
        # goes, with the number hidden.)
        self.assertFalse(any("alarme" in f for f in facts), facts)
        self.assertEqual(r["conscience"][1]["held_back"]["private"], 1)
        self.assertTrue(any(f.startswith("Visa [hidden: looks like") for f in facts), facts)
        self.assertIn("/secrets", r["conscience"][1]["kept_home"])
        self.assertEqual(r["profile"][0], 200, r)
        self.assertEqual(r["profile"][1]["city"], "Ottawa")
        body = json.dumps(r)
        for v in ("4821", "4111", "C6101"):
            self.assertNotIn(v, body)
            self.assertNotIn(v, self.log_text())
        after = json.loads(self.store_text())          # nothing of his was dropped
        self.assertEqual(after["facts"], before["facts"])
        self.assertEqual(after["profile"], before["profile"])

    def test_the_terminal_system_prompt_goes_with_an_old_secret_hidden(self):
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"],
                 facts=["Mon NIP est 4821", "Anna visits on Sundays"])
        """)
        r = self.py("""
            import jefferey_chat as jc, egress
            sent = egress.system_prompt_once(jc.system_prompt())
            out({"has_pin": "4821" in sent, "has_anna": "Anna visits on Sundays" in sent,
                 "hidden": "[hidden: looks like" in sent})
        """)
        self.assertEqual(r, {"has_pin": False, "has_anna": True, "hidden": True})
        self.assertNotIn("4821", self.log_text())

    def test_the_owner_moves_a_stored_secret_into_his_vault(self):
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"],
                 facts=["Le code de l'alarme est 4821", "Anna visits on Sundays"],
                 profile={"garage_code": "7731"})
        """)
        r = self.py(TEST_KEYCHAIN + textwrap.dedent("""
            import jefferey_chat as jc, egress, vault
            listed = egress.stored_secrets(jc.conscience.data)
            first = jc.owner_secrets("/secrets move 1", answer=lambda _: "yes")
            second = jc.owner_secrets("/secrets move 1", answer=lambda _: "yes")
            left = egress.stored_secrets(jc.conscience.data)
            out({"listed": len(listed), "first": first, "second": second,
                 "left": len(left), "vault": {n: vault.resolve("vault:" + n)
                                              for n in vault.names()},
                 "brief": jc.dispatch_tool("get_profile", {}),
                 "facts": [f["fact"] for f in jc.conscience.data["facts"]]})
        """), JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r["listed"], 2)
        self.assertEqual(r["left"], 0)
        # nothing lost: the words are whole in the vault
        self.assertIn("Le code de l'alarme est 4821", r["vault"].values())
        self.assertIn("7731", r["vault"].values())
        self.assertIn("Anna visits on Sundays", r["facts"])
        self.assertTrue(any("[in the vault as 'alarm_code']" in f for f in r["facts"]), r)
        self.assertTrue(r["brief"]["garage_code"].startswith("vault:"), r)
        self.assertNotIn("kept_home", r["brief"])
        self.assertNotIn("4821", self.store_text())
        self.assertNotIn("7731", self.store_text())

    def test_moving_to_the_vault_needs_the_owners_yes_and_a_vault(self):
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"], facts=["My PIN 4821"])
        """)
        before = self.store_text()
        r = self.py("""
            import jefferey_chat as jc
            no = jc.owner_secrets("/secrets move 1", answer=lambda _: "no")
            novault = jc.owner_secrets("/secrets move 1", answer=lambda _: "yes")
            out([no, novault])
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r, [None, None])
        self.assertEqual(self.store_text(), before)


# ======================================================================= I-14
class TheScamCheckStillWorksOnMessagesThatQuoteASecret(EgressTest):
    """I-14 (email#1, adversarial#3, selling#6, texting#1)."""

    def test_triage_answers_on_every_surface_and_flags_the_secret(self):
        r = self.py("""
            scams = %r
            import jefferey_chat as jc
            chat = {k: jc.dispatch_tool("triage_message",
                                        {"sender": s, "subject": sub, "body": b})
                    for k, (s, sub, b) in scams.items()}
            import jefferey_mcp as m
            mcp = {k: mcp_call(m, "triage_message", {"sender": s, "subject": sub, "body": b})
                   for k, (s, sub, b) in scams.items()}
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            http = {}
            for k, (s, sub, b) in scams.items():
                x = c.post("/triage", json={"sender": s, "subject": sub, "body": b},
                           headers=H(%r))
                http[k] = [x.status_code, x.json()]
            out({"chat": chat, "mcp": mcp, "http": http})
        """ % (SCAMS, TOKENS, TA), JEFFEREY_CLIENT="jefferey")
        for surface in ("chat", "mcp"):
            for k, res in r[surface].items():
                self.assertFalse(res.get("refused"), (surface, k, res))
                self.assertIn(res["verdict"], ("likely_scam", "suspicious"), (surface, k, res))
        for k, (status, res) in r["http"].items():
            self.assertEqual(status, 200, (k, res))
            self.assertIn(res["verdict"], ("likely_scam", "suspicious"), (k, res))
        # the secret in the message is itself a warning sign
        for k in ("sin", "otp", "card"):
            self.assertTrue(any("never read it out" in f for f in r["chat"][k]["scam_flags"]),
                            r["chat"][k])
            self.assertEqual(r["chat"][k]["verdict"], "likely_scam", r["chat"][k])
        body = json.dumps(r) + self.log_text()
        for v in ("046 454 286", "551203", "4111 1111 1111 1111"):
            self.assertNotIn(v, body)
        # the old door refused every one of these that held a number
        self.assertTrue(old_looks_secret(SCAMS["sin"][2]) and old_looks_secret(SCAMS["otp"][2]))
        self.assertTrue(old_looks_secret(SCAMS["expire"][2]))

    def test_a_scammer_cannot_switch_off_the_check_with_a_fake_reference(self):
        base = ("You won a prize! Pay the release fee by wire transfer or gift card "
                "today. Do not tell anyone.")
        r = self.py("""
            import jefferey_chat as jc
            out([jc.dispatch_tool("triage_message", {"sender": "x", "subject": "Prize",
                                                     "body": b})
                 for b in (%r, %r)])
        """ % (base, base + " Ref 4111 1111 1111 1111"), JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r[0]["verdict"], "likely_scam")
        self.assertEqual(r[1]["verdict"], "likely_scam")
        self.assertFalse(r[1].get("refused"))

    def test_ordinary_order_and_tracking_numbers_are_not_cards_or_sins(self):
        import random
        rnd = random.Random(7)
        texts = ([f"Your order #{rnd.randrange(10**15, 10**16)} has shipped" for _ in range(300)]
                 + [f"Parcel {rnd.randrange(10**8, 10**9)} is on its way" for _ in range(300)]
                 + [f"Tracking number {rnd.randrange(10**15, 10**16)}" for _ in range(300)])
        r = self.py("""
            import egress
            out(sum(1 for t in %r if egress.looks_secret(t)))
        """ % texts)
        self.assertEqual(r, 0)
        self.assertGreater(sum(1 for t in texts if old_looks_secret(t)), 30)

    def test_draft_guidance_and_scoring_answer_too(self):
        r = self.py("""
            import jefferey_chat as jc
            out([jc.dispatch_tool("draft_guidance",
                                  {"purpose": "reply to 'your password is expired'"}),
                 jc.dispatch_tool("score_opportunity",
                                  {"what": "card 4111 1111 1111 1111 offered a refund"})])
        """, JEFFEREY_CLIENT="jefferey")
        self.assertFalse(r[0].get("refused"), r[0])
        self.assertFalse(r[1].get("refused"), r[1])
        self.assertNotIn("4111", json.dumps(r))

    def test_tools_that_keep_what_they_are_given_still_refuse(self):
        r = self.py("""
            import jefferey_chat as jc
            out([jc.dispatch_tool(t, a) for t, a in [
                ("remember_fact", {"fact": "my SIN 046 454 286"}),
                ("add_memory", {"text": "the alarm code is 4821"}),
                ("check_charge", {"merchant": "card 4111 1111 1111 1111", "amount": 5}),
                ("log_observation", {"note": "Interac verification code 551203"})]])
        """, JEFFEREY_CLIENT="jefferey")
        for res in r:
            self.assertTrue(res.get("refused"), res)
            self.assertNotIn("and stop", res["tell_the_user"])
        for v in ("046 454 286", "4821", "4111", "551203"):
            self.assertNotIn(v, self.store_text())

    def paste(self, text: str, **extra) -> subprocess.CompletedProcess:
        """The owner pastes `text` into 'Talk to JEFFEREY on this Mac'."""
        return subprocess.run([PY, "-c", PRELUDE + textwrap.dedent("""
            import jefferey_chat as jc
            jc.make_client = lambda: object()      # no engine is ever reached
            jc.chat(once=%r)
        """ % text)], env=self.env(JEFFEREY_CLIENT="jefferey", **extra), cwd=self.tmp,
            capture_output=True, text=True, timeout=300)

    def test_the_owner_pasting_a_scam_at_his_terminal_gets_a_warning_from_his_mac(self):
        p = self.paste(SCAMS["sin"][2])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("stayed on this Mac", p.stdout)
        self.assertIn("checked it here, on your Mac: this message is very likely a scam",
                      p.stdout)
        self.assertIn("call the number on your card", p.stdout)
        sent = [e for e in map(json.loads, self.log_text().splitlines())
                if e.get("kind") == "you_said" and not e.get("refused")]
        self.assertEqual(sent, [])
        self.assertNotIn("046 454 286", self.log_text())

    def test_the_owner_typing_his_own_pin_is_told_plainly_not_warned_of_a_scam(self):
        p = self.paste("Please remember that my bank PIN is 4821 for the card")
        self.assertIn("stayed on this Mac", p.stdout)
        self.assertIn("saw no other sign of a scam", p.stdout)
        self.assertNotIn("4821", self.log_text())

    def test_a_shut_door_is_still_reported_as_a_shut_door(self):
        (self.tmp / "door-shut").write_text("shut by the owner")
        p = self.paste("What did I spend on hydro last month?")
        self.assertIn("kept in the house", p.stdout)
        self.assertNotIn("stayed on this Mac", p.stdout)


# ======================================================================= I-15
class PhotoFingerprintsAreNotSecrets(EgressTest):
    """I-15 (accessibility#1, album#3, scale#1) — the scan side. What the
    album sends (counts, not lists of fingerprints) is the album's work."""

    def test_fingerprints_that_used_to_trip_the_scan_pass_whole(self):
        ids = tripping_photo_ids()
        for h in ids:
            self.assertTrue(old_looks_secret(h), h)
        r = self.py("""
            import egress, hashlib
            egress.bind("mcp")
            ids = %r
            rel = egress.release("who_am_i", {"moments": [{"text": "Varadero", "photos": ids}]})
            prompt = egress.release("next_story_prompt", {"moment_id": "m1", "photo_ids": ids})
            rnd = [hashlib.sha256(str(i).encode() + b"x").hexdigest() for i in range(5000)]
            out({"each": [egress.looks_secret(h) for h in ids],
                 "rel": rel, "prompt": prompt,
                 "random": sum(1 for h in rnd if egress.looks_secret(h))})
        """ % ids)
        self.assertEqual(r["each"], [None] * len(ids))
        self.assertEqual(r["rel"]["moments"][0]["photos"], ids)
        self.assertNotIn("kept_home", r["rel"])
        # Integration: the album no longer sends fingerprints at all (I-15,
        # album side), so next_story_prompt's allowlist no longer names them.
        self.assertNotIn("photo_ids", r["prompt"])
        self.assertEqual(r["random"], 0)

    def test_who_am_i_and_tell_story_work_with_a_story_pinned_to_those_photos(self):
        ids = tripping_photo_ids()
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"],
                 memories=[("Our anniversary trip to Varadero", %r)])
        """ % ids)
        r = self.py("""
            import jefferey_mcp as m
            out({"who": mcp_call(m, "who_am_i"), "story": mcp_call(m, "tell_story")})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertFalse(r["who"].get("refused"), r["who"])
        self.assertFalse(r["story"].get("refused"), r["story"])
        # Integration: an older memory's fingerprint list reaches the engine
        # as a count (I-15) — and stays whole on disk.
        self.assertEqual(r["who"]["moments"][0]["photos"], len(ids))
        self.assertNotIn(ids[0], json.dumps(r))
        self.assertNotIn("social insurance", json.dumps(r))


# ======================================================================= I-58
class LicenceAndPassportNumbersStayOutOfTheProfile(EgressTest):
    """I-58 (selling#8)."""

    def test_licence_passport_and_account_answers_are_refused(self):
        r = self.py("""
            import jefferey_chat as jc
            out({f: jc.dispatch_tool("set_profile_field", {"field": f, "value": v})
                 for f, v in [("Driver's licence number", "C6101-40706-60905"),
                              ("Passport number", "AB123456"),
                              ("Mother's maiden name", "Kovacs"),
                              ("Place of birth", "Szeged"),
                              ("Security question answer", "Rex"),
                              ("Health card", "1234-567-890-AB")]})
        """, JEFFEREY_CLIENT="jefferey")
        # refused at the door (the number alone has the shape) or by the
        # profile's own rule (the field's name) — never stored
        self.assertEqual([f for f, x in r.items() if x.get("stored") or not
                          (x.get("refused") or x.get("stored") is False)], [], r)
        for v in ("C6101", "AB123456", "Kovacs", "Szeged", "1234-567-890"):
            self.assertNotIn(v, self.store_text())

    def test_a_guest_session_never_gets_a_licence_or_passport_already_stored(self):
        """Stored before this rule existed: kept in the file, never handed out."""
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"],
                 profile={"drivers_licence_number": "C6101-40706-60905",
                          "passport_number": "AB123456", "mothers_maiden_name": "Kovacs",
                          "shipping_address": "12 Elm St", "city": "Ottawa"})
        """)
        r = self.py("""
            import jefferey_mcp as m
            out(mcp_call(m, "get_profile"))
        """, JEFFEREY_CLIENT="claude-raw")
        r2 = self.py("""
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            x = TestClient(h.app).get("/profile", headers=H(%r))
            out([x.status_code, x.json()])
        """ % (TOKENS, TC))
        self.assertFalse(r.get("refused"), r)
        self.assertEqual(r["city"], "Ottawa")
        self.assertEqual(r["shipping_address"], "12 Elm St")    # 'pin' in 'shipping' is not a PIN
        self.assertIn("/secrets", r["kept_home"])
        self.assertEqual(r2[0], 200, r2)
        for v in ("C6101", "AB123456", "Kovacs"):
            self.assertNotIn(v, json.dumps(r))
            self.assertNotIn(v, json.dumps(r2))
            self.assertNotIn(v, self.log_text())
            self.assertIn(v, self.store_text())               # nothing was dropped

    def test_the_owner_can_move_them_into_his_vault(self):
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"],
                 profile={"mothers_maiden_name": "Kovacs", "city": "Ottawa"})
        """)
        r = self.py(TEST_KEYCHAIN + textwrap.dedent("""
            import jefferey_chat as jc, vault
            moved = jc.owner_secrets("/secrets move 1", answer=lambda _: "yes")
            out({"moved": moved, "vault": vault.resolve("vault:" + moved["moved"]),
                 "profile": jc.dispatch_tool("get_profile", {})})
        """), JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r["moved"]["moved"], "mothers_maiden_name")
        self.assertEqual(r["vault"], "Kovacs")
        self.assertEqual(r["profile"], {"mothers_maiden_name": "vault:mothers_maiden_name",
                                        "city": "Ottawa"})


# ======================================================================= I-67
class TheLogIsWrittenWholeOrNotAtAll(EgressTest):
    """I-67 (drive#1)."""

    def test_a_short_write_refuses_the_send_and_leaves_no_torn_line(self):
        r = self.py("""
            import resource, signal, egress
            egress.bind("mcp")
            egress.release("orb_state", {"mood": "calm"})
            p = os.environ["JEFFEREY_EGRESS"]
            size = os.path.getsize(p)
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
            resource.setrlimit(resource.RLIMIT_FSIZE, (size + 120, hard))  # the drive is full
            try:
                egress.release("get_directives", "Kandahar " * 700)
                full = "RELEASED"
            except egress.EgressRefused as e:
                full = str(e)
            after_full = os.path.getsize(p)
            resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))       # space again
            egress.release("orb_state", {"mood": "after"})
            lines = open(p, "rb").read().splitlines()
            out({"full": full, "size": size, "after_full": after_full,
                 "entries": [e.get("sent") for e in egress.entries()],
                 "bad_lines": sum(1 for l in lines if not l.startswith(b"{") or not l.endswith(b"}"))})
        """)
        self.assertNotEqual(r["full"], "RELEASED", "data left while its log line was torn")
        self.assertIn("nothing was sent", r["full"])
        self.assertEqual(r["after_full"], r["size"], "the torn bytes were left in the log")
        self.assertEqual(r["entries"], ['{"mood": "calm"}', '{"mood": "after"}'])
        self.assertEqual(r["bad_lines"], 0)

    def test_a_torn_line_from_a_power_cut_never_swallows_the_next_send(self):
        r = self.py("""
            import egress
            egress.bind("mcp")
            egress.release("orb_state", {"mood": "calm"})
            with open(os.environ["JEFFEREY_EGRESS"], "ab") as f:
                f.write(b'{"t": "2026-10-1')                 # the power went
            egress.release("remember_fact", {"fact": "Anna visits on Sundays"})
            out([e.get("tool") for e in egress.entries()])
        """)
        self.assertEqual(r, ["orb_state", "remember_fact"])

    def test_a_line_torn_before_this_fix_still_gives_up_the_send_after_it(self):
        r = self.py("""
            import egress
            egress.bind("mcp")
            egress.release("orb_state", {"mood": "calm"})
            good = open(os.environ["JEFFEREY_EGRESS"], "rb").read()
            # the old door appended the next entry straight onto a torn line
            with open(os.environ["JEFFEREY_EGRESS"], "wb") as f:
                f.write(b'{"t": "2026-10-1' + good)
            out([e.get("tool") for e in egress.entries()])
        """)
        self.assertEqual(r, ["orb_state"])

    def test_the_system_prompt_is_not_marked_logged_when_the_log_failed(self):
        r = self.py("""
            import egress
            egress.bind("chat")
            real = egress._write
            def broken(entry):
                raise OSError(28, "No space left on device")
            egress._write = broken
            try:
                egress.system_prompt_once("directives + conscience")
                first = "sent"
            except egress.EgressRefused as e:
                first = str(e)
            egress._write = real
            egress.system_prompt_once("directives + conscience")
            out({"first": first,
                 "logged": [e["kind"] for e in egress.entries()]})
        """)
        self.assertIn("nothing was sent", r["first"])
        self.assertEqual(r["logged"], ["system_prompt"])


# ============================================== after the fixes (verify, hunt)
class AfterTheFixes(EgressTest):
    """verify I-07, I-14, I-15, I-58 and the egress regressions."""

    OLD_HOUSE_NOTES = ["Garage code 4821, gate 2580", "PIN 4821 for the Visa, 1234 for the debit",
                       "Door code 4821 (old one was 1234)",
                       "Le code de l'alarme est 4821, appeler le 613 555 0199"]

    def test_an_old_house_code_note_never_blacks_out_the_whole_answer(self):
        # verify I-07 (3), I-15 (1), regression: the '[hidden: … lock code]'
        # mark itself read as words announced the next number, and release()
        # refused who_am_i, tell_story and GET /conscience whole.
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"], facts=%r, memories=[(
                "When we moved in 1998 the garage code was 4821 and the gate 2580, Anna laughed",
                ())])
            out(1)
        """ % self.OLD_HOUSE_NOTES)
        r = self.py("""
            import jefferey_mcp as m
            who = mcp_call(m, "who_am_i")
            story = mcp_call(m, "tell_story")
            con = mcp_call(m, "get_conscience")
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            g = TestClient(h.app).get("/conscience", headers=H(%r))
            out({"who": who, "story": story, "con": con, "gpt": [g.status_code, g.json()]})
        """ % (TOKENS, TG), JEFFEREY_CLIENT="jefferey")
        for k in ("who", "story", "con"):
            self.assertFalse(r[k].get("refused"), (k, r[k]))
        self.assertEqual(r["gpt"][0], 200, r["gpt"])
        sent = json.dumps(r)
        for code in ("4821", "2580"):
            self.assertNotIn(code, sent)
        self.assertIn("Anna laughed", sent)
        self.assertIn("for the debit", sent)
        sys.path.insert(0, str(CONNECTOR))
        import egress
        masked, _ = egress.mask_text(self.OLD_HOUSE_NOTES[3])
        self.assertIn("613 555 0199", masked, "a phone number is not a code")
        self.assertNotIn("4821", masked)
        self.assertIsNone(egress.looks_secret(masked))

    def test_a_code_in_a_scams_subject_never_switches_off_its_verdict(self):
        # verify I-14 (1): the hidden mark re-triggered the scan on the next
        # number, and the whole verdict was refused on every surface.
        cases = [("Visa Security", "Your PIN 4821 4821 is locked",
                  "URGENT: your account is suspended. Buy two Google Play cards and send "
                  "the codes immediately. Do not tell your bank."),
                 ("Alarm code 1234 ref 5678", "Refund pending",
                  "Your refund is pending. Buy two Google Play cards and send the codes. "
                  "Act now, do not tell your bank."),
                 ("Desjardins", "Votre NIP 4321, dossier 8765",
                  "URGENT: votre compte est suspendu. Achetez des cartes Google Play.")]
        r = self.py("""
            cases = %r
            import jefferey_chat as jc, jefferey_mcp as m
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            res = []
            for s, sub, body in cases:
                a = {"sender": s, "subject": sub, "body": body}
                res.append([jc.dispatch_tool("triage_message", a), mcp_call(m, "triage_message", a),
                            c.post("/triage", json=a, headers=H(%r)).json()])
            out(res)
        """ % (cases, TOKENS, TA), JEFFEREY_CLIENT="jefferey")
        for row in r:
            for v in row:
                self.assertFalse(v.get("refused"), v)
                self.assertEqual(v.get("verdict"), "likely_scam", v)
                self.assertNotIn("4821", json.dumps(v))

    def test_a_value_refused_for_its_label_is_never_written_in_the_record(self):
        # verify I-07 (2), I-58 (3): refused, then written word for word, twice.
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            out([d("set_profile_field", {"field": f, "value": v}).get("stored")
                 for f, v in [("bank login", "laszlo / Hunter22!"), ("alarm code", "4821"),
                              ("passport", "AB123456"), ("Mother's maiden", "Kovacsne")]])
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r, [False] * 4)
        log = self.log_text()
        for v in ("Hunter22", "4821", "AB123456", "Kovacsne"):
            self.assertNotIn(v, log)

    def test_a_key_question_cannot_carry_a_secret_into_the_access_log(self):
        # verify I-14 (2): selfcloud_check_access was let through as a 'read',
        # and wrote 'jefferey: password: Soleil2024Zq' into the access log.
        r = self.py("""
            import jefferey_mcp as m
            out(mcp_call(m, "selfcloud_check_access", {"client": "jefferey",
                                                       "scope": "password: Soleil2024Zq"}))
        """, JEFFEREY_CLIENT="jefferey")
        self.assertTrue(r.get("refused"), r)
        for p in self.tmp.rglob("*.jsonl"):
            self.assertNotIn("Soleil2024Zq", p.read_text(), p)

    def test_ordinary_notes_pass_the_door(self):
        # the regression list: each was stored and sent by the parent commit
        notes = ["Dr. Patel put me on a combination pill, 250 mg twice a day",
                 "Is a combination of 2 Tylenol 500 mg ok?", "I changed my password on 2026-10-14",
                 "The door code changed on 2026-09-01, Maria has the new one",
                 "Keypad batteries replaced 2026-09-01", "Transit fare is 3.70",
                 "OC Transpo transit pass costs 128 a month", "The institution has 300 beds",
                 "Hydro account 123456789 is in my name", "He gave me his Legion pin 1985"]
        r = self.py("""
            import jefferey_chat as jc
            out([jc.dispatch_tool("remember_fact", {"fact": n}) for n in %r])
        """ % notes, JEFFEREY_CLIENT="jefferey")
        self.assertEqual([x.get("refused") for x in r], [None] * len(notes), r)
        kept = [f["fact"] for f in json.loads(self.store.read_text())["facts"]]
        self.assertEqual(kept, notes)
        # round 7, D3: on the way out, a note that names a code (a combination,
        # a password, a door code, a keypad) has every number in it hidden
        for n, x in zip(notes, r):
            if any(w in n.lower() for w in ("combination", "password", "code", "keypad")):
                self.assertNotEqual(x["fact"], n, n)
                self.assertIn("[hidden: a number in a note that mentions a code]", x["fact"], n)
            else:
                self.assertEqual(x["fact"], n)

    def test_secrets_written_the_way_people_say_them_are_caught(self):
        said = ["The code for the front door is 4821", "The code to the garage is 4821",
                "the door code at the new house is 4821", "Alarm: 7731", "Front door: 4821",
                "the alarm is 4821", "ATM code 4821", "Buzzer 2580",
                "le code de ma carte est 4321", "Mon code bancaire est 4321",
                "Le NIP de ma carte Desjardins, je l'oublie toujours, c'est 4321",
                "PIN: 48 21", "my PIN is 4 8 2 1", "My bank login is laszlo / Hunter22!",
                "Desjardins: user laszlo, pass Soleil2024", "hasło: Tulipe2024",
                "Mot de passe de ma banque: soleil"]
        r = self.py("""
            import jefferey_mcp as m
            out([mcp_call(m, "remember_fact", {"fact": t}).get("refused") for t in %r])
        """ % said, JEFFEREY_CLIENT="jefferey")
        for t, refused in zip(said, r):
            self.assertTrue(refused, t)
        self.assertEqual(json.loads(self.store_text() or '{"facts": []}').get("facts", []), [])

    def test_other_names_for_identity_documents_stay_out_and_a_plate_does_not(self):
        r = self.py("""
            import jefferey_chat as jc
            d = jc.dispatch_tool
            names = ["Travel document number", "Document number", "ID number", "Photo ID",
                     "Pasaporte", "Reisepass", "Driving permit", "Health #", "Birthplace",
                     "Born in", "First pet's name", "Memorable word", "Mother's maiden",
                     "Maiden", "City of birth", "Country of birth", "Mother's family name"]
            refused = {n: d("set_profile_field", {"field": n, "value": "GA123456"}).get("stored")
                       for n in names}
            plate = d("set_profile_field", {"field": "Licence plate", "value": "CBDA 123"})
            out({"refused": refused, "plate": plate})
        """, JEFFEREY_CLIENT="jefferey")
        for n, stored in r["refused"].items():
            self.assertFalse(stored, n)
        # a plate is not an identity document: kept — from an AI, beside his
        # own details until he confirms it (round 8, S2)
        self.assertTrue(r["plate"].get("pending"), r["plate"])

    def test_old_profile_keys_written_as_one_word_stay_home(self):
        r = self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"], profile={
                "passportno": "GA123456", "mothers_maiden": "Kovacs",
                "document_number": "X1234567", "postal_code": "K1A 0B1"})
            import jefferey_mcp as m
            out(mcp_call(m, "get_profile"))
        """, JEFFEREY_CLIENT="claude-raw")
        sent = json.dumps(r)
        for v in ("GA123456", "Kovacs", "X1234567"):
            self.assertNotIn(v, sent)

    def test_ordinary_mail_is_not_called_suspicious(self):
        # verify I-14 (3): a Hydro bill, an Aeroplan statement and a bank's
        # eStatement were 'suspicious', with "a real bank never asks for it".
        mail = [("Hydro Ottawa", "Your bill is ready",
                 "Your bill for account 1234567 is ready. Amount due $84.12 by Nov 1."),
                ("Aeroplan", "Points",
                 "Hi Laszlo, your Aeroplan number 123456782 earned 500 points this month."),
                ("RBC", "Statement", "Your eStatement for chequing account 12345-1234567 is "
                                     "now available in online banking."),
                ("Shoppers", "Rx ready", "Your prescription Rx 4532015 is ready for pickup. "
                                         "Combination pill 250 mg.")]
        r = self.py("""
            import jefferey_chat as jc
            out([jc.dispatch_tool("triage_message", {"sender": s, "subject": t, "body": b})
                 for s, t, b in %r])
        """ % mail, JEFFEREY_CLIENT="jefferey")
        for (s, _, _), v in zip(mail, r):
            self.assertNotIn(v.get("verdict"), ("suspicious", "likely_scam"), (s, v))
            self.assertNotIn("never asks for it", json.dumps(v), s)

    def test_a_pasted_secret_with_the_door_shut_says_the_door_is_shut(self):
        (self.tmp / "door-shut").write_text("shut")
        r = self.py("""
            import jefferey_chat as jc, io, contextlib
            jc.make_client = lambda: None
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                jc.chat(once="Interac: your security code is 551203. If you did not request "
                             "it, call 1-833-555-0100 immediately and read us the code.")
            out(buf.getvalue())
        """, JEFFEREY_CLIENT="jefferey")
        self.assertIn("door is shut", r)
        self.assertIn("very likely a scam", r)


# ===================================================== repair round 4 (R1)
class AMarkNeverShieldsWhatFollowsIt(EgressTest):
    """R1: a '[hidden…]' mark an engine wrote between a word that announces a
    secret and the secret itself switched the scan off. The note was kept,
    and later went out word for word to a plain guest (claude-raw) in
    get_conscience. A mark hides nothing when someone else typed it."""

    SHIELDED = ["My PIN [hidden] 4821",
                "The alarm code is [hidden: a code] 7731",
                "password: [hidden: looks like a password] Hunter22!",
                "The garage code is [hidden: looks like a PIN or a door, alarm or lock code], "
                "changed to 5932 today",
                "Bank password: [hidden: looks like a password or PIN] — he changed it to "
                "Soleil2025!",
                "password: Hun[hidden]ter22!"]
    VALUES = ["4821", "7731", "Hunter22", "5932", "Soleil2025", "ter22"]

    def test_an_engine_cannot_slip_a_secret_in_behind_a_mark(self):
        r = self.py("""
            notes = %r
            import jefferey_chat as jc, jefferey_mcp as m
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            res = []
            for n in notes:
                res.append([bool(jc.dispatch_tool("remember_fact", {"fact": n}).get("refused")),
                            bool(mcp_call(m, "remember_fact", {"fact": n}).get("refused")),
                            c.post("/facts", json={"fact": n}, headers=H(%r)).status_code])
            out(res)
        """ % (self.SHIELDED, TOKENS, TA), JEFFEREY_CLIENT="jefferey")
        for note, (chat, mcp, http) in zip(self.SHIELDED, r):
            self.assertTrue(chat, ("terminal kept it", note))
            self.assertTrue(mcp, ("Claude kept it", note))
            self.assertEqual(http, 403, ("ChatGPT kept it", note))
        stored = self.store_text()
        for v in self.VALUES:
            self.assertNotIn(v, stored)
            self.assertNotIn(v, self.log_text())

    def test_one_already_kept_behind_a_mark_never_goes_out(self):
        # written before this fix, or by hand: the release scan reads through
        # the mark too, and hides only the secret — the answer still goes
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"], facts=%r + ["Anna calls on Sundays"])
            out(1)
        """ % self.SHIELDED)
        r = self.py("""
            import jefferey_mcp as m
            con = mcp_call(m, "get_conscience")
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            g = TestClient(h.app).get("/conscience", headers=H(%r))
            out({"con": con, "gpt": [g.status_code, g.json()]})
        """ % (TOKENS, TG), JEFFEREY_CLIENT="claude-raw")
        self.assertFalse(r["con"].get("refused"), r["con"])
        self.assertEqual(r["gpt"][0], 200, r["gpt"])
        sent = json.dumps(r)
        self.assertIn("Anna calls on Sundays", sent)
        for v in self.VALUES:
            self.assertNotIn(v, sent)
        log = self.log_text()
        for v in self.VALUES:
            self.assertNotIn(v, log)

    def test_what_jefferey_hid_itself_reads_clean_and_is_never_kept_again(self):
        # JEFFEREY's own answer reads clean when scanned again, and a phone
        # number or a reference after a hidden code is still not a code
        # (I-07, I-15). Handed back by an engine, it is not kept: it already
        # has something hidden in it (R1, round 6 — the structural rule;
        # rounds 4 and 5 kept it, and each way of reading what followed a
        # mark let another secret in).
        r = self.py("""
            import egress, jefferey_chat as jc
            notes = ["Garage code 4821, gate 2580", "Le code de l'alarme est 4821, appeler le "
                     "613 555 0199", "Alarm code 1234 ref 5678", "Votre NIP 4321, dossier 8765"]
            masked = [egress.mask_text(n)[0] for n in notes]
            out({"masked": masked, "again": [egress.looks_secret(x) for x in masked],
                 "kept": [jc.dispatch_tool("remember_fact", {"fact": x}).get("refused")
                          for x in masked]})
        """, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r["again"], [None] * 4)
        self.assertEqual(r["kept"], [True] * 4)
        self.assertNotIn("[hidden", self.store_text())
        joined = " ".join(r["masked"])
        for v in ("4821", "2580", "1234", "4321"):
            self.assertNotIn(v, joined)
        for v in ("613 555 0199", "ref 5678", "dossier 8765"):
            self.assertIn(v, joined)


# ===================================================== repair round 5 (R1)
class APhoneOrReferenceIsSteppedOver(EgressTest):
    """R1, round 5: to keep JEFFEREY's own answer clean when it came back in,
    round 4 made a phone number, or a number after 'ref', 'dossier', 'tel' or
    'call', END the search for the value a word announced. Every note below
    was then kept on all three surfaces and its PIN went out in clear to
    claude-raw and gpt-raw. The parent refused them all. A phone or reference
    number is now stepped over and the reading goes on; a number after 'tel'
    or 'call' is still the PIN when nothing further on is."""

    KEPT_IN_ROUND_4 = [
        "The alarm code (call 613-555-0199 if it rings) is 4821",
        "Le code de l'alarme (appeler le 613 555 0199 si ça sonne) est 4821",
        "Votre NIP, dossier 8765, est 4321",
        "My bank PIN (ref 5678) is 4822",
        "Voicemail PIN: call *98 then 4823",
        "My PIN, tel 4824",
        "My debit card PIN: call 4825",
        "PIN for my phone 4826",
        "Voicemail PIN: dial 1 800 555 0199 and enter 4827",
        "Bank code: call 1-800-769-2511 then enter 482193",
        "NIP du téléphone 4828",
        "Alarm code, call the company 613 555 0199 first, then 4829",
        "My PIN [hidden]\n\n4830",
    ]
    PINS = ["4821", "4321", "4822", "4823", "4824", "4825", "4826", "4827", "482193",
            "4828", "4829", "4830"]

    def test_none_of_them_is_kept_on_any_surface(self):
        r = self.py("""
            notes = %r
            import jefferey_chat as jc, jefferey_mcp as m
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            out([[bool(jc.dispatch_tool("remember_fact", {"fact": n}).get("refused")),
                  bool(mcp_call(m, "remember_fact", {"fact": n}).get("refused")),
                  c.post("/facts", json={"fact": n}, headers=H(%r)).status_code] for n in notes])
        """ % (self.KEPT_IN_ROUND_4, TOKENS, TA), JEFFEREY_CLIENT="jefferey")
        for note, (chat, mcp, http) in zip(self.KEPT_IN_ROUND_4, r):
            self.assertTrue(chat, ("terminal kept it", note))
            self.assertTrue(mcp, ("Claude kept it", note))
            self.assertEqual(http, 403, ("ChatGPT kept it", note))
        stored = self.store_text()
        for v in self.PINS:
            self.assertNotIn(v, stored)

    def test_one_already_kept_goes_out_with_the_pin_hidden_and_the_phone_kept(self):
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"], facts=%r)
            out(1)
        """ % self.KEPT_IN_ROUND_4)
        r = self.py("""
            import jefferey_mcp as m
            con = mcp_call(m, "get_conscience")
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            g = TestClient(h.app).get("/conscience", headers=H(%r))
            out({"con": con, "gpt": [g.status_code, g.json()]})
        """ % (TOKENS, TG), JEFFEREY_CLIENT="claude-raw")
        self.assertFalse(r["con"].get("refused"), r["con"])
        self.assertEqual(r["gpt"][0], 200, r["gpt"])
        sent = json.dumps(r, ensure_ascii=False)
        for v in self.PINS:
            self.assertNotIn(v, sent)
        # what the PIN is not stays readable: the phone numbers and the words
        # (the alarm and bank notes are private, so they are not in a list).
        # Round 7, D3: a file number in a note that names a PIN is hidden too.
        for v in ("1 800 555 0199", "Votre NIP, dossier", "call *98 then"):
            self.assertIn(v, sent)
        self.assertNotIn("8765", sent)

    def test_a_year_or_a_birthday_after_a_code_is_not_the_code(self):
        # Round 4 read the mark as not there, so the next number was 'the
        # code', and on release the year was hidden. A note an engine hands
        # back with JEFFEREY's own mark in it is now refused for what it is
        # (R1, round 6: it already has something hidden in it).
        M = "[hidden: looks like a PIN or a door, alarm or lock code]"
        notes = [f"Alarm code {M}, the house was built in 1987",
                 f"Gate code {M} and the gate is at 1550 Elm Road",
                 f"Garage code {M} - we moved in 2019",
                 f"Alarm code {M}\nAnna's birthday is 12 May 1975"]
        r = self.py("""
            import jefferey_mcp as m
            out([mcp_call(m, "remember_fact", {"fact": n}).get("refused") for n in %r])
        """ % notes, JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r, [True] * 4, r)
        sys.path.insert(0, str(CONNECTOR))
        import egress
        kept = {
            "My alarm code is 4821 and my birthday is March 3 1950": "March 3 1950",
            "My PIN [hidden] and I was born in 1948": "born in 1948",
            "Alarm code 4821, the house was built in 1987": "the house was built in 1987",
            "Garage code 4821 - we moved in 2019": "we moved in 2019",
            "Gate code 4821 and the gate is at 1550 Elm Road": "1550 Elm Road",
        }
        for text, words in kept.items():
            masked, _ = egress.mask_text(text)
            self.assertIn(words, masked, text)
            self.assertNotIn("4821", masked, text)
            self.assertIsNone(egress.looks_secret(masked), masked)
        # A password hides the rest of its clause: a passphrase's tail never
        # leaks (R1, round 6), and the next sentence still goes.
        for text, gone, stays in (
                ("My email password is Hunter22! and my daughter Anna lives in Ottawa. She "
                 "visits on Sundays.", "Hunter22", "She visits on Sundays."),
                ("Wifi password: maple-tree-42 (the router is in the basement)\nThe printer is "
                 "upstairs.", "maple-tree-42", "The printer is upstairs."),
                ("Netflix password Sunflower77 and Disney plus is the same; Anna knows it.",
                 "Sunflower77", "Anna knows it.")):
            masked = egress.mask_text(text)[0]
            self.assertNotIn(gone, masked)
            self.assertIn(stays, masked)
            self.assertIsNone(egress.looks_secret(masked), masked)


if __name__ == "__main__":
    unittest.main()
