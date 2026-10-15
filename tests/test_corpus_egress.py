"""
Frozen corpus — the egress door's secret scan (R1), repair round 6.

Two repair rounds patched the scan case by case, and each broke cases next
to the ones it fixed. This file freezes EVERY concrete case the round-4 and
round-5 skeptics reported for the door, with the outcome the product's
principles ask for, so no later change can quietly trade one case for
another again. Where safety and convenience conflict, the case expects the
safe outcome.

The structural rules it holds the door to:

  * A '[hidden …]' mark is JEFFEREY's own, and only JEFFEREY makes one. Text
    an engine hands in that holds one is refused for storing, on every
    surface, with a plain message ("this text already has something hidden
    in it; JEFFEREY does not store text it hid"). That ends the whole class
    of 'a secret written after a mark'. A tool that only reads what it is
    given (a scam check) still answers, and counts the mark as a sign that a
    secret was there.
  * After a password word, once its value is found, the rest of that clause
    is hidden (to the end of the sentence, the line or a semicolon), so a
    passphrase's tail never leaks. 'The password is car' is a password.
  * A phone number, a reference, case or ticket number, a time, a year, a
    street number or an amount never stops the search for a PIN or a code:
    it is stepped over, and only an unexplained number is the code. A note
    with a code word and a phone or reference number, but no code, is kept.

Outcomes:
  MARK    refused at the door with the 'already has something hidden' message;
          if an older version kept it, it still never goes out with the
          secret in it ('values')
  SECRET  refused at the door; on the way out the values are hidden, the
          words listed in 'kept' still go
  BENIGN  kept, and goes out word for word
"""

from __future__ import annotations

import itertools
import json
import random
import re
import unittest

from test_egress import EgressTest, TOKENS, TA, TG

MARK, SECRET, BENIGN = "mark", "secret", "benign"
M = "[hidden: looks like a PIN or a door, alarm or lock code]"
P = "[hidden: looks like a password or PIN]"

# (text, outcome, values that must never go out, words that must still go out)
CASES: list[tuple[str, str, list[str], list[str]]] = [
    # ---------------------------------------------------------------- round 4
    # verify-b: a phone, ref, dossier, tel or call between the word and the
    # PIN switched the scan off (stored on 93db2aa, sent to claude-raw)
    ("Votre NIP, dossier 8765, est 4321", SECRET, ["4321"], ["dossier 8765"]),
    ("My PIN, tel 4824", SECRET, ["4824"], []),
    ("My debit card PIN: call 4825", SECRET, ["4825"], []),
    ("Voicemail PIN: call *98 then 4823", SECRET, ["4823"], ["call *98 then"]),
    ("My bank PIN (ref 5678) is 4822", SECRET, ["4822"], ["ref 5678"]),
    ("The alarm code (call 613-555-0199 if it rings) is 4821", SECRET, ["4821"],
     ["613-555-0199"]),
    ("Le code de l'alarme (appeler le 613 555 0199 si ça sonne) est 4821", SECRET, ["4821"],
     ["613 555 0199"]),
    # verify-c: the same hole
    ("PIN for my phone 4821", SECRET, ["4821"], []),
    ("Voicemail PIN: dial 1 800 555 0199 and enter 4821", SECRET, ["4821"], ["1 800 555 0199"]),
    ("Bank code: call 1-800-769-2511 then enter 482193", SECRET, ["482193"], ["1-800-769-2511"]),
    ("NIP du téléphone 4821", SECRET, ["4821"], []),
    # verify-b: a mark followed by a blank line
    ("My PIN [hidden]\n\n4821", MARK, ["4821"], []),
    # verify-b regression: his own masked note followed by a year or a street
    # (refused now: it holds a mark — the structural rule)
    (f"Alarm code {M}, the house was built in 1987", MARK, [], []),
    (f"Gate code {M} and the gate is at 1550 Elm Road", MARK, [], []),
    (f"Garage code {M} - we moved in 2019", MARK, [], []),
    (f"Alarm code {M}\nAnna's birthday is 12 May 1975", MARK, [], []),
    # verify-c over-masking: a code's value is hidden, a year or a birthday
    # after it in the same sentence still goes; a password hides its clause
    ("My alarm code is 4821 and my birthday is March 3 1950", SECRET, ["4821"], ["March 3 1950"]),
    ("My email password is Hunter22! and my daughter Anna lives in Ottawa with her two kids",
     SECRET, ["Hunter22"], ["My email password is"]),
    ("Wifi password: maple-tree-42 (the router is in the basement next to the furnace)",
     SECRET, ["maple-tree-42"], ["Wifi password:"]),
    ("My PIN [hidden] and I was born in 1948", MARK, [], []),
    ("door code [hidden] — the house number is 4821", MARK, [], []),
    # verify-b R1 (round 4): the reproduced marks and every variant
    ("My PIN [hidden] 4821", MARK, ["4821"], []),
    ("The alarm code is [hidden: a code] 7731", MARK, ["7731"], []),
    ("password: [hidden: looks like a password] Hunter22!", MARK, ["Hunter22"], []),
    ("The garage code is [hidden: looks like a PIN or a door, alarm or lock code], changed "
     "to 5932 today", MARK, ["5932"], []),
    ("Bank password: [hidden: looks like a password or PIN] — he changed it to Soleil2025!",
     MARK, ["Soleil2025"], []),
    ("password: Hun[hidden]ter22!", MARK, ["ter22"], []),
    ("My PIN [Hidden] 4821", MARK, ["4821"], []),
    ("My PIN [HIDDEN] 4821", MARK, ["4821"], []),
    ("My PIN [hidden ] 4821", MARK, ["4821"], []),
    ("My PIN [hidden - a code] 4821", MARK, ["4821"], []),
    ("My PIN [hidden…] 4821", MARK, ["4821"], []),
    ("My PIN [hidden][hidden] 4821", MARK, ["4821"], []),
    ("My PIN [hidden] [hidden] [hidden] 4821", MARK, ["4821"], []),
    ("My PIN\n[hidden]\n4821", MARK, ["4821"], []),
    ("My PIN [hidden: " + "x" * 125 + "] 4821", MARK, ["4821"], []),
    ("Mon NIP [hidden] 4821", MARK, ["4821"], []),
    ("Le code de la porte est [hidden: un code] 4821", MARK, ["4821"], []),
    ("Mot de passe: [hidden] Soleil2025!", MARK, ["Soleil2025"], []),
    ("Card [hidden: looks like a card number] 4111 1111 1111 1111", MARK, ["4111 1111"], []),
    ("Card 4111 [hidden] 1111 1111 1111", MARK, ["1111 1111"], []),
    ("4111 1111 [hidden] 1111 1111", MARK, ["4111 1111"], []),
    ("SIN [hidden] 046 454 286", MARK, ["046 454 286"], []),
    ("SIN 046 [hidden] 454 286", MARK, ["454 286"], []),
    ("PIN 48[hidden]21", MARK, ["48", "21"], []),
    ("PIN 4[hidden]8[hidden]2[hidden]1", MARK, [], []),
    ("pass[hidden]word: Hunter22!", MARK, ["Hunter22"], []),
    ("PI[hidden]N 4821", MARK, ["4821"], []),
    ("pa[hidden]ss[hidden]word Hunter22!", MARK, ["Hunter22"], []),
    ("My PIN [hidden] is 4821", MARK, ["4821"], []),
    ("My PIN [hidden: looks like a PIN] (changed today) is 4821", MARK, ["4821"], []),
    ("My PIN [hidden] 4 8 2 1", MARK, ["4 8 2 1"], []),
    ("My PIN [hidden] four eight two one", MARK, [], []),
    ("Garage code [hidden], call 613-555-0199 then 4821", MARK, ["4821"], []),
    ("Garage code [hidden] ref 5678 4821", MARK, ["4821"], []),
    ("Garage code [hidden] tel 4821", MARK, ["4821"], []),
    ("Garage code [hidden] phone 4821", MARK, ["4821"], []),
    ("Alarm code [hidden: x] invoice 4821", MARK, [], []),
    ("password [hidden] ref Hunter22!", MARK, ["Hunter22"], []),
    ("api key [hidden] sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789ABCD", MARK,
     ["sk-ant-api03"], []),
    ("AKIA[hidden]IOSFODNN7EXAMPLE", MARK, ["IOSFODNN7EXAMPLE"], []),
    ("sk-ant-api03-abcdefghij[hidden]klmnopqrstuvwxyz0123456789ABCD", MARK,
     ["klmnopqrstuvwxyz0123456789ABCD"], []),
    # the same list's notes without a mark
    ("My PIN is [redacted] 4821", SECRET, ["4821"], []),
    ("My bank PIN, call me if you forget: 4821", SECRET, ["4821"], []),
    ("My PIN, tel 4821", SECRET, ["4821"], []),
    ("Alarm code: call 4821", SECRET, ["4821"], []),
    ("Alarm code (dossier) 4821", SECRET, ["4821"], []),
    # ---------------------------------------------------------------- round 5
    # verify-b: a secret after a mark, stored on 5adc37b and sent in clear
    ("Wifi password[hidden]Bluebird77", MARK, ["Bluebird77"], []),
    ("Le NIP[hidden]7731", MARK, ["7731"], []),
    ("Mon NIP [hidden], maintenant c'est 1962", MARK, ["1962"], []),
    (f"Garage code {M}\nnow 5932", MARK, ["5932"], []),
    (f"My PIN {M}: 1955", MARK, ["1955"], []),
    ("Bank PIN [hidden], new number 7741", MARK, ["7741"], []),
    ("Bank PIN[hidden]4821", MARK, ["4821"], []),
    (f"The garage code is {M}, changed to 1987 today", MARK, ["1987"], []),
    ("Mot de passe Netflix[hidden]Soleil2025!", MARK, ["Soleil2025"], []),
    # verify-b: false refusals (round 4 kept them)
    ("Alarm code reset: called 613-555-0199, they will send a tech at 1430", BENIGN, [],
     ["613-555-0199", "1430"]),
    ("PIN reset requested: phoned 1-800-769-2511, ticket 58213", BENIGN, [],
     ["1-800-769-2511", "ticket 58213"]),
    ("Forgot my PIN, called RBC at 1-800-769-2511, case 58213", BENIGN, [], ["case 58213"]),
    ("Lost my bank card PIN, phoned 1-800-769-2511 on Monday, new card arrives in 7 to 10 "
     "business days", BENIGN, [], ["1-800-769-2511"]),
    # verify-b: still missed in both rounds
    ("My PIN [hidden] call 4821", MARK, ["4821"], []),
    ("Codes: garage 4821, alarm 7731, shed 1234", SECRET, ["4821", "7731", "1234"], ["Codes:"]),
    ("My PIN is four eight two one", SECRET, ["four eight two one"], ["My PIN is"]),
    # verify-c 1: the end of a passphrase leaked on release
    ("Wifi password: Blue42 Sky House", SECRET, ["Blue42", "Sky House"], ["Wifi password:"]),
    ("My password is Rover2 loves bones", SECRET, ["Rover2", "loves bones"], []),
    ("The Netflix password is Tiger7 Lily Pad", SECRET, ["Tiger7", "Lily Pad"], []),
    ("My bank password is Sunny2day Morning Glory", SECRET, ["Sunny2day", "Morning Glory"], []),
    ("My password is blue sky - forever", SECRET, ["blue sky", "forever"], ["My password is"]),
    # verify-c 2: a secret after a mark, stored on 5adc37b
    (f"Door code {M}\nBackup: 7731", MARK, ["7731"], []),
    (f"My bank PIN {M}, the new one is 1952", MARK, ["1952"], []),
    (f"PIN {M} 613 555 0199 5932", MARK, ["5932"], []),
    (f"Password: {P} purple monkey", MARK, ["purple monkey"], []),
    # verify-c 3: a plain word after a password word is the password
    ("The password is car", SECRET, [" car"], ["The password is"]),
    ("My password is car", SECRET, [" car"], ["My password is"]),
    ("Mot de passe: car", SECRET, [" car"], ["Mot de passe:"]),
    # verify-c 4: benign notes with a code word and a phone or file number
    ("The door code changed, call Mike 613-555-0199, he lives at 1550 Elm Road", BENIGN, [],
     ["613-555-0199", "1550 Elm Road"]),
    ("My PIN was locked so I called 1-800-555-0199 at 1030 this morning", BENIGN, [],
     ["1-800-555-0199", "1030"]),
    ("Called about my PIN reset, ref 5678.", BENIGN, [], ["ref 5678"]),
    ("Le code de la porte a changé, appeler le 613 555 0199, dossier 88213", BENIGN, [],
     ["613 555 0199", "dossier 88213"]),
    ("PIN reset: call 1-888-555-0123, case 99812 opened Oct 3", BENIGN, [],
     ["1-888-555-0123", "case 99812"]),
]

# verify-c's own corpus (sk5/corp_mine.py): benign notes
CORP_BENIGN = [
    "I forgot my PIN, so I called the bank at 1-800-769-2511 and they mailed a new card. "
    "Ref 55821.",
    "Called about my PIN reset, ref 5678.",
    "My PIN letter came today, ref 5678",
    "My PIN was locked so I called 1-800-555-0199 at 1030 this morning",
    "Need to change the garage code, call the installer at 613 555 0199 after 1500",
    "Alarm code: call ADT 1-800-238-2727 and give them account 7731",
    "The door code changed, call Mike 613-555-0199, he lives at 1550 Elm Road",
    "The gate code is on the fridge, call 613 555 0199 if you cannot find it, apartment 1204",
    "Reset my password: called 1 800 555 0199, ticket 482193",
    "PIN: ask the bank, call 613 555 0199, they close at 1700",
    "My debit PIN expired, tel 613 555 0199 ext 2201",
    "The keypad code, call Linda 613 555 0199 for 2 hours",
    "Voicemail password: call 1-800-555-0199 to reset it, it costs $25",
    "For a new alarm code call 613 555 0199 and quote order 482193",
    "The alarm code company: phone 613-555-0199, invoice 20931 paid",
    "To change the garage door code call Chamberlain 1-800-528-9131 and have serial 4419220 ready",
    "Le code de la porte, appeler le 613 555 0199, dossier 88213",
    "My bank PIN, tel 613-555-0199 open 0900 to 1700",
    "The safe combination is with the lawyer, call 613-555-0199, file 2291",
    "PIN reset: call 1-888-555-0123, case 99812 opened Oct 3",
    "Password help line 1-800-555-0199, wait time 45 minutes, option 3",
    "The password is in my wallet. Room 4821.",
    "My password needs changing; the help desk ticket is INC0012345",
    "Remind me to change my PIN on 2026-11-02",
    "The door code is on the card in the kitchen drawer, 3rd drawer down",
    "My password for the bank expired on March 3 and I need a new one",
    "The combination pill, 250 mg, twice a day",
    "My Legion pin 1985 is in the drawer",
    "Postal code K1A 0B1",
    "My blood pressure was 140 over 90 and my PIN is fine",
    "Garage code: the installer number is 613-555-0199 and his name is Bob",
    "PIN number: phone the branch, 613-555-0199, before 2027",
    "Netflix password changed, Bell says invoice 448213 is due",
    "The alarm number is 1-800-555-0199 and it covers 3 doors",
    "wifi: see router label, phone support 1-866-310-2355",
]
# ...the notes in that list that carry a mark: refused now (the structural rule)
CORP_BENIGN_MARKED = [
    "My PIN [hidden] — I was born in 1948 and live at 1550 Elm Road.",
    f"Alarm code {M}. Call ADT at 613 555 0199 if it rings.",
    f"Alarm code {M}, the alarm company is 613-555-0199, account 88213",
    f"My PIN {M} and my birthday is March 3 1950",
    f"Door code {M}. Our house is 4821 Maple Avenue",
    f"The wifi password {P} is on the router; the router model is AC1750",
    f"Password {P} — remember to pay the Rogers bill of 82.50",
    f"My PIN {M} for the card ending 4821",
    f"Garage code {M} — Mike comes Tuesday at 1030",
    f"Alarm code {M}; the cottage is lot 1204",
    f"PIN {M}. Flight AC 8821 leaves at 0930.",
    f"Password {P} and Emma2010 is the name of her blog",
    f"Alarm code {M}, ref 5678",
]
# ...and its secrets: (text, values)
CORP_SECRET = [
    # in its benign list, but 'account' and five digits is read as a bank
    # account number, on the safe side (it was refused in rounds 4 and 5 too)
    ("The alarm company number is 613-555-0199, account 88213", ["88213"]),
    ("My password is Rover2 loves bones", ["Rover2", "loves bones"]),
    ("Wifi password: Blue42 Sky House", ["Blue42", "Sky House"]),
    ("My bank password is Sunny2day Morning Glory", ["Sunny2day", "Morning Glory"]),
    ("password: maple-tree-42", ["maple-tree-42"]),
    ("password: correct horse battery staple", ["correct horse battery staple"]),
    ("The password is purple monkey dishwasher", ["purple monkey dishwasher"]),
    ("My password is blue sky - forever", ["blue sky", "forever"]),
    ("Password: Tulip99 (capital T)", ["Tulip99"]),
    ("My password is Hunter22 Tulip99", ["Hunter22", "Tulip99"]),
    ("password is (Hunter22)", ["Hunter22"]),
    ("my password is -Hunter22", ["Hunter22"]),
    ("The alarm code is 4821", ["4821"]),
    ("Alarm code: call the company 613 555 0199 first, then 4821", ["4821"]),
    ("My PIN is 4821, call the bank at 1-800-769-2511 if it fails", ["4821"]),
    ("My PIN: 4821. Call 1-800-769-2511 if lost.", ["4821"]),
    ("Alarm code is 4821 and the house is 1550 Elm Road", ["4821"]),
    ("My PIN, call 613 555 0199, is 4821", ["4821"]),
    ("The garage code, tel 613-555-0199, is 7731", ["7731"]),
    ("Wifi password: Sunflower77 (the router is in the basement)", ["Sunflower77"]),
    ("My password is Soleil2024! - don't share", ["Soleil2024"]),
    ("mot de passe: Soleil-2024 (banque)", ["Soleil-2024"]),
    ("my bank login is laszlo / Hunter22!", ["Hunter22"]),
    ("My card is 4111 1111 1111 1111", ["4111 1111 1111 1111"]),
    ("SIN 046 454 286", ["046 454 286"]),
    ("PIN 4821 and alarm 7731", ["4821", "7731"]),
    ("My PIN is 4 8 2 1", ["4 8 2 1"]),
    ("My PIN, tel 4824", ["4824"]),
    ("My PIN ref 4821", ["4821"]),
    ("password Hunter22", ["Hunter22"]),
    ("the code for the front door is 4821", ["4821"]),
    ("My PIN is 4821 (ref 5678)", ["4821"]),
    ("My PIN (ref 5678) is 4821", ["4821"]),
    ("The PIN for my debit card is 4821, ref 5678", ["4821"]),
]
CORP_SECRET_MARKED = [
    ("My PIN [hidden] 4821", ["4821"]), ("My PIN [hidden: x], new one is 5932", ["5932"]),
    ("door code [hidden] changed to 5932 today", ["5932"]), ("Garage code [hidden], 7731", ["7731"]),
    ("password [hidden] Hunter22!", ["Hunter22"]), ("password: [hidden] Tulip99", ["Tulip99"]),
    ("PIN [hidden] 1987", ["1987"]), ("PIN [hidden] 48 21", ["48 21"]),
    ("My PIN [hidden]. 4821", []), ("Le code de la porte [hidden] 4821", ["4821"]),
    ("code de l'alarme [hidden], nouveau 5932", ["5932"]),
    ("Alarm code [hidden] or else 4821", ["4821"]),
    ("password: [hidden] - the new one is Hunter33!", ["Hunter33"]),
    ("Alarm code [hidden: x]\n4821", ["4821"]), ("My PIN [hidden]\n4821", ["4821"]),
    ("pin [hidden] 4821 1550 Elm Road", ["4821"]),
]
# verify-c's marks corpus (sk5/corp_mark.py): every one is a secret after a mark
CORP_MARK = [
    (f"My PIN {M}, it's 4821", ["4821"]), (f"My PIN {M} is 4821", ["4821"]),
    (f"My PIN {M} = 4821", ["4821"]), (f"PIN {M}: 4821", ["4821"]), (f"PIN {M} (4821)", ["4821"]),
    (f"PIN {M} 4821.", ["4821"]), (f"PIN {M} — 4821", ["4821"]), (f"PIN {M} - 4821", ["4821"]),
    (f"PIN {M}, 4821", ["4821"]), (f"PIN {M} 2026", ["2026"]),
    (f"PIN {M}, the new one is 2026", ["2026"]), (f"alarm code {M}, now 1990", ["1990"]),
    (f"Alarm code {M} and the garage is 7731", ["7731"]),
    (f"Garage code {M}, backup code 7731", ["7731"]), (f"Door code {M}\nBackup: 7731", ["7731"]),
    (f"PIN {M} or 4 8 2 1", ["4 8 2 1"]), (f"PIN {M} 4821 #", ["4821"]),
    (f"Password {P} Hunter22", ["Hunter22"]), (f"Password {P}, Hunter22", ["Hunter22"]),
    (f"Password {P} or Tulip99!", ["Tulip99"]),
    (f"password {P} - new: Sunflower77", ["Sunflower77"]), (f"Password {P} Blue Sky", ["Blue Sky"]),
    (f"Password: {P} purple monkey", ["purple monkey"]),
    (f"wifi password {P} BlueHouse20", ["BlueHouse20"]),
    (f"mot de passe {P} Soleil2024", ["Soleil2024"]), (f"NIP {M} 4821", ["4821"]),
    (f"Code de la porte {M}, 4821", ["4821"]), (f"PIN {M} call 4821", ["4821"]),
    (f"PIN {M} ref 4821", ["4821"]), (f"My PIN {M}{M} 4821", ["4821"]),
    (f"My PIN {M} {M} 4821", ["4821"]), (f"PIN {M}\n\n4821", ["4821"]),
    (f"PIN {M} at 4821", ["4821"]), (f"My PIN {M} for card 4821 is 5932", ["5932"]),
    (f"PIN {M} for the debit card, 5932", ["5932"]), (f"Visa PIN {M}, MC PIN 5932", ["5932"]),
    (f"PIN {M}; 5932", ["5932"]), (f"PIN {M}. New PIN 5932", ["5932"]),
    (f"PIN {M} 5932 1550 Elm Rd", ["5932"]), (f"PIN {M} 613 555 0199 5932", ["5932"]),
]


def fuzz2_cases() -> list[tuple[str, str]]:
    """verify-b round 5 (p/fuzz2.py): 540 mark + link + value combinations;
    132 more were stored on 5adc37b than on 93db2aa."""
    kws = ["My PIN", "The garage code is", "Alarm code", "Mon NIP", "Le code de la porte est",
           "Bank PIN"]
    mids = [", now", ": ", ".\nNew one:", "\nnow", ", changed to", ", new number", ", the new one is",
            " - now", "; nouveau", ", maintenant c'est", " (old), new", ", he changed it to", ", use",
            ", or", " / new"]
    vals = ["5932", "1987", "2019", "7731#", "0000", "482193"]
    return [(f"{k} {M}{mid} {v}", v.rstrip("#")) for k, mid, v in itertools.product(kws, mids, vals)]


def fuzz_strings(n: int = 1500) -> list[str]:
    """verify-b round 5 (p/fuzz.py), seeded: what JEFFEREY hides is clean
    when it is read again."""
    rnd = random.Random(1)
    kws = ["PIN", "my PIN", "garage code", "alarm code", "password", "mot de passe", "NIP",
           "door code", "wifi password", "code", "the code to the shed", "passcode", "combination"]
    fill = ["is", ":", "-", ",", "call", "tel", "ref", "613-555-0199", "1-800-769-2511", "then",
            "and", "the", "new", "one", "changed to", "in", "1987", "2019", "4821", "7731",
            "Hunter22!", "Soleil2025", "bluebird", "Elm Street", "12", "apt", "(", ")", "\n",
            "since", "Monday", "today", "dollars", "$40", "5 mg", "4111 1111 1111 1111",
            "046 454 286", "or", "try", "#", "was", "est", "c'est", "maintenant"]
    return [rnd.choice(kws) + " " + " ".join(rnd.choice(fill) for _ in range(rnd.randint(1, 9)))
            for _ in range(n)]


def all_rows() -> list[tuple[str, str, list[str], list[str]]]:
    rows = list(CASES)
    rows += [(t, BENIGN, [], []) for t in CORP_BENIGN]
    rows += [(t, MARK, [], []) for t in CORP_BENIGN_MARKED]
    rows += [(t, SECRET, v, []) for t, v in CORP_SECRET]
    rows += [(t, MARK, v, []) for t, v in CORP_SECRET_MARKED + CORP_MARK]
    return rows


UNIT = """
import egress
egress.bind("test")
rows = %r
res = []
for text, want, values, kept in rows:
    try:
        egress.admit("remember_fact", {"fact": text})
        door = "kept"
    except egress.EgressRefused as e:
        door = "mark" if "already has something hidden in it" in str(e) else "secret"
    shown, _ = egress.mask({"fact": text})
    shown = shown["fact"]
    res.append({"door": door, "shown": shown, "again": egress.looks_secret(shown)})
out(res)
"""


class TheDoorsFrozenCorpus(EgressTest):
    """Every case in the table, at the door (admit) and on the way out
    (what an engine is shown of a note that is already kept)."""

    def check(self, rows):
        got = self.py(UNIT % (rows,))
        bad = []
        for (text, want, values, kept), g in zip(rows, got):
            door = {MARK: "mark", SECRET: "secret", BENIGN: "kept"}[want]
            why = []
            if g["door"] != door:
                why.append(f"door said {g['door']}, wanted {door}")
            for v in values:
                if v in g["shown"]:
                    why.append(f"{v!r} goes out")
            for k in kept:
                if k not in g["shown"]:
                    why.append(f"{k!r} no longer goes out")
            if want == BENIGN and g["shown"] != text:
                why.append(f"something was hidden: {g['shown']!r}")
            if g["again"]:
                why.append(f"what goes out still looks like {g['again']}")
            if why:
                bad.append((text, why, g["shown"]))
        self.assertEqual(bad, [], "\n" + "\n".join(f"{t!r}: {w} -> {s!r}" for t, w, s in bad))

    def test_the_named_cases(self):
        self.check(CASES)

    def test_the_skeptics_own_benign_notes_are_kept(self):
        self.check([(t, BENIGN, [], []) for t in CORP_BENIGN])

    def test_the_skeptics_own_secrets_are_refused_and_hidden(self):
        self.check([(t, SECRET, v, []) for t, v in CORP_SECRET])

    def test_every_marked_note_is_refused_and_never_leaks(self):
        self.check([(t, MARK, [], []) for t in CORP_BENIGN_MARKED]
                   + [(t, MARK, v, []) for t, v in CORP_SECRET_MARKED + CORP_MARK])

    def test_the_540_mark_combinations(self):
        self.check([(t, MARK, [v], []) for t, v in fuzz2_cases()])

    def test_what_jefferey_hides_is_clean_when_read_again(self):
        r = self.py("""
            import egress
            bad = []
            for s in %r:
                m, _ = egress.mask_text(s)
                if egress.looks_secret(m):
                    bad.append([s, m])
            out(bad)
        """ % (fuzz_strings(),))
        self.assertEqual(r, [], r[:5])


class AMarkIsRefusedOnEverySurface(EgressTest):
    """The structural rule on the three surfaces: Claude (MCP), ChatGPT
    (HTTP) and the terminal refuse to keep text that holds a mark, and say
    why in plain words; nothing is stored."""

    NOTES = ["Wifi password[hidden]Bluebird77", "Le NIP[hidden]7731",
             "Mon NIP [hidden], maintenant c'est 1962", f"Garage code {M}\nnow 5932",
             f"My PIN {M}: 1955", "Bank PIN [hidden], new number 7741", "Bank PIN[hidden]4821",
             f"Door code {M}\nBackup: 7731", f"Password: {P} purple monkey",
             f"Alarm code {M}, the house was built in 1987"]

    def test_refused_with_a_plain_message_and_nothing_stored(self):
        r = self.py("""
            notes = %r
            import jefferey_chat as jc, jefferey_mcp as m
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            res = []
            for n in notes:
                t = jc.dispatch_tool("remember_fact", {"fact": n})
                mc = mcp_call(m, "remember_fact", {"fact": n})
                ht = c.post("/facts", json={"fact": n}, headers=H(%r))
                res.append([str(t.get("reason") or t.get("error") or t), str(mc.get("reason")),
                            ht.status_code, ht.text])
            out(res)
        """ % (self.NOTES, TOKENS, TA), JEFFEREY_CLIENT="jefferey")
        for note, (chat, mcp, code, http) in zip(self.NOTES, r):
            for where, said in (("terminal", chat), ("Claude", mcp), ("ChatGPT", http)):
                self.assertIn("already has something hidden in it", said, (where, note))
                self.assertIn("JEFFEREY does not store text it hid", said, (where, note))
            self.assertEqual(code, 403, note)
        stored = self.store_text()
        log = re.sub(r"[0-9a-f]{64}", "", self.log_text())   # fingerprints are not values
        for v in ("Bluebird77", "7731", "1962", "5932", "1955", "7741", "4821", "purple monkey",
                  "1987"):
            self.assertNotIn(v, stored)
            self.assertNotIn(v, log)

    def test_one_kept_by_an_older_version_never_goes_out(self):
        self.py("""
            seed(os.environ["JEFFEREY_CONSCIENCE_PATH"], facts=%r + ["Anna calls on Sundays"])
            out(1)
        """ % self.NOTES)
        r = self.py("""
            import jefferey_mcp as m
            con = mcp_call(m, "get_conscience")
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            g = TestClient(h.app).get("/conscience", headers=H(%r))
            out({"con": con, "gpt": [g.status_code, g.json()]})
        """ % (TOKENS, TG), JEFFEREY_CLIENT="claude-raw")
        self.assertEqual(r["gpt"][0], 200, r["gpt"])
        r2 = self.py("""
            import jefferey_mcp as m
            out([mcp_call(m, "explain_basis", {"topic": q}) for q in
                 ("wifi password", "bank PIN", "garage code", "door code", "NIP")])
        """, JEFFEREY_CLIENT="jefferey")
        sent = json.dumps([r, r2], ensure_ascii=False)
        self.assertIn("Anna calls on Sundays", sent)
        log = re.sub(r"[0-9a-f]{64}", "", self.log_text())   # fingerprints are not values
        for v in ("Bluebird77", "7731", "1962", "5932", "1955", "7741", "4821", "purple monkey"):
            self.assertNotIn(v, sent)
            self.assertNotIn(v, log)


class AMarkIsStillASignForAScamCheck(EgressTest):
    """A tool that only reads what it is given still answers, and counts a
    mark as a secret having been there (a message that quoted a PIN)."""

    def test_triage_reads_a_mark_as_a_secret_quoted(self):
        msgs = [("Bank Security", "Verify now",
                 f"Your PIN {M} was used. Call us at once and read it back to confirm."),
                ("Desjardins", "Urgent", f"Votre NIP {M} est bloqué. Rappelez-nous et dites-le.")]
        r = self.py("""
            import jefferey_chat as jc, jefferey_mcp as m
            res = []
            for s, sub, body in %r:
                a = {"sender": s, "subject": sub, "body": body}
                res.append([jc.dispatch_tool("triage_message", a), mcp_call(m, "triage_message", a)])
            out(res)
        """ % (msgs,), JEFFEREY_CLIENT="jefferey")
        for row in r:
            for v in row:
                self.assertFalse(v.get("refused"), v)
                flags = " ".join(v.get("scam_flags", []))
                self.assertIn("looks like", flags, v)


if __name__ == "__main__":
    unittest.main()
