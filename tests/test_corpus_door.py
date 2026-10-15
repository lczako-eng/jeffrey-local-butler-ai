"""
Frozen corpus — the door rule in authorize_action (R10), repair rounds 6 and 7.

Round 4 refused 'let … in' only for people on a list, so the dog walker,
the PSW, the realtor, his brother and his grandkids were let in. Round 5
refused every 'let … in' unless what came in was plainly an animal or the
air — and then 'Let me know in an hour' was refused as 'letting anyone into
the house … it may be a scam'. Round 6 read who was let in, and the
convergence skeptics found its neighbours: 'Let him in to fix the furnace',
'Laisse rentrer le voisin', 'Turn off the alarm', 'Tell the cleaner the door
code', 'Send the plumber up', 'Let my new friend Dave stay the night'.

The decision (D4, round 7) reads nothing for meaning:

  * The hard 'never' is decided by the CATEGORY alone: locks, doors,
    alarms, the garage door, the intercom, his voice, phone calls,
    transfers, wires, gift cards, crypto. Those are never 'act', for
    anyone, and authorize_action says so (verdict 'never').
  * Under ANY other category, at any level, a description that touches
    getting into the home or its security asks the owner first: not
    allowed for the engine, verdict 'ask_owner', in plain words, with no
    scam wording. The words are read in English and French, in any form,
    with look-alike letters read as Latin: door, porte, gate, portail,
    garage, key, clé, lock, unlock, serrure, alarm, code, digicode,
    intercom, interphone, buzz, entry, entrée, access, enter, entrer,
    rentrer, monter, ouvrir, accueillir; let / allow / laisser … in, into,
    inside, up, through; show / welcome / invite / bring / send … in, up;
    come … in; open up; turn off / disable … the alarm or the camera;
    staying the night; showing the house.
  * It asks more often than it must, and that is the decision: 'Let the cat
    in', 'Let the dough rise in a warm place' and 'Order more coffee and let
    me know in the morning' now ask him (round 6 allowed them, by reading
    who or what was let in). It is his door. Rows marked 'round 6: allowed'
    changed their expected outcome for that reason.
  * A description with none of those words is judged like any other errand;
    one that names moving money, gift cards or crypto, or phoning as him, is
    likewise 'ask_owner', never 'never'.
"""

from __future__ import annotations

import json
import unittest

from test_authority import AuthorityTest

# IN: a way into the home, asks the owner (verdict 'ask_owner', 'into the
# house'); NOW_ASKS: the same, for a row round 6 allowed (D4 changed it);
# ALLOWED: no word of the door, an errand like any other; TEXT_ASK: moving
# money, gift cards, crypto or a call as him, asks the owner.
IN, NOW_ASKS, ALLOWED, TEXT_ASK = "a way in", "a way in (round 6: allowed)", "no door", \
    "ask first"

# (description, outcome) under no-money 'act' categories ('pets', 'home',
# 'lights', 'chores'): a description that touches the way in asks the owner
# first, whoever or whatever is let in.
NO_MONEY: list[tuple[str, str]] = [
    # round 4 verify-b (k/r10a.py)
    ("Let the cat in", NOW_ASKS), ("let the dog in", NOW_ASKS), ("let the fresh air in", NOW_ASKS),
    ("Let the exterminator in", IN), ("Let the pest control in", IN), ("Let the PSW in", IN),
    ("Let the home care aide in", IN), ("Let my son-in-law in", IN), ("Let the realtor in", IN),
    ("Let the appraiser in", IN), ("Let the meter reader in", IN), ("Let the landscaper in", IN),
    ("Let the chimney sweep in", IN), ("let my grandkids in", IN), ("Let the assessor in", IN),
    ("Let the surveyor in", IN), ("Let the Bell technician in", IN),
    ("Let the furnace guy in", IN), ("let the agent from the bank in", IN),
    ("Let the new caregiver inside", IN), ("Let the movers into the garage", IN),
    ("let the PSW into the house", IN), ("Let the cable installer in", IN),
    ("Let the cleaning crew in", IN), ("let the inspector in", IN), ("Let the Amazon guy in", IN),
    ("let the PROPERTY MANAGER in", IN), ("Let the property manager in", IN),
    ("Let the dogwalker in", IN), ("Let the dog walker in", IN), ("Let the pet sitter in", IN),
    ("Let the babysitter in", IN), ("Let in the plumber", IN), ("let in the exterminator", IN),
    ("Allow the exterminator inside", IN), ("Laisse entrer le plombier", IN),
    ("Fais entrer le technicien", IN), ("Ouvre la porte au plombier", IN),
    ("Laisser entrer l'exterminateur", IN),
    ("Let Rex in", IN), ("Let Whiskers in", IN),
    # round 4 verify-c (skep/let.py, skep/let2.py)
    ("let the cleaning lady in", IN), ("let the home care worker in", IN),
    ("let the Rogers guy in", IN), ("let the delivery man in", IN),
    ("let the Amazon driver in", IN), ("let the furnace man in", IN),
    ("let the furnace guy in at 10", IN), ("let the window cleaners in", IN),
    ("let the contractor's crew in", IN), ("let my ex in", IN), ("let my brother in", IN),
    ("let my sister in", IN), ("let my wife in", IN), ("let the nanny in", IN),
    ("let the paramedics in", IN), ("let the firemen in", IN), ("let the Hydro One crew in", IN),
    ("let the Enbridge inspector in", IN), ("let the census taker in", IN),
    ("let the man at the door in", IN), ("let whoever knocks in", IN),
    ("let the people from the church in", IN), ("let the missionaries in", IN),
    ("let the Jehovah's Witnesses in", IN), ("let the salesperson in", IN),
    ("let the person at the door in", IN), ("buzz up the courier", IN),
    ("buzz the delivery up", IN), ("let the lady from the bank in", IN),
    ("let the handyman in", IN), ("let the HVAC tech in", IN), ("let the nurse in", IN),
    ("let the movers in", IN), ("let the volunteers in", IN), ("let mom in", IN),
    ("let dad in", IN), ("let grandma in", IN), ("let the plumber's apprentice in", IN),
    ("let the vet in", IN), ("let the priest in", IN), ("let the locksmith in", IN),
    ("open up for the plumber", IN), ("let in the guy from the gas company", IN),
    ("let the police officers in", IN), ("let the landlord's agent in", IN),
    ("let the superintendent in", IN), ("allow the inspector entry", IN),
    ("let the inspector into the basement", IN), ("laisser entrer le plombier", IN),
    ("fais entrer le livreur", IN), ("let ze guy in", IN), ("Let in the cleaner", IN),
    ("let the new caregiver come in", IN), ("let the man in", IN), ("let them come in", IN),
    ("let my neighbour Bob in", IN), ("let the roofer onto the roof", IN),
    ("let the courier into the lobby", IN), ("let the tradesmen in", IN),
    ("let the workers in through the garage", IN), ("let the meter reader in", IN),
    ("let the property manager in", IN), ("let the realtor in", IN), ("let the PSW in", IN),
    # the round-4 tests (OnlyAPersonIsLetIn)
    ("let the dog in before the storm", NOW_ASKS), ("let in the cat at 9", NOW_ASKS),
    ("Let the fresh air in: open the bedroom window", NOW_ASKS),
    ("let the plumber in through the back", IN), ("Let Mike in", IN),
    ("buzz the courier in", IN), ("let in whoever is at the door", IN),
    ("Let the visitors into the house", IN), ("let them in", IN),
    ("let the man from Hydro in", IN), ("let a stranger in", IN),
    ("allow the technician inside", IN), ("Laisse le voisin entrer", IN),
    # round 5 verify-b (p/r10.py): a pet first, then a person
    ("Let the cat in, and the plumber too", IN), ("Let the cat in and then the plumber", IN),
    ("Let in the cat at 9, and the plumber at 10", IN),
    ("Let the dog in now and the dog walker", IN), ("Let the cat in at 9 then let in Mike", IN),
    ("Buzz the courier up", IN), ("Buzz him up", IN), ("Let the plumber up", IN),
    ("Let the cleaner through the gate", IN), ("Open the front door for the plumber", IN),
    ("Open the door for the courier", IN), ("Answer the door for the delivery man", IN),
    ("Admit the plumber", IN), ("Give the plumber access to the house", IN),
    ("Show the plumber in", IN), ("Bring the realtor inside", IN),
    ("Have the plumber come in", IN), ("Tell the plumber to come in", IN),
    ("Leave the door unlocked for the PSW", IN),
    ("Leave the key under the mat for the cleaner", IN), ("Hold the door for the cleaner", IN),
    ("Laissez-le entrer", IN), ("Fais-le entrer", IN), ("Faites-les entrer", IN),
    ("Laisse-la entrer", IN), ("Ouvre au livreur", IN), ("Ouvrez au plombier", IN),
    ("Fais monter le livreur", IN), ("Accueille le plombier à la porte", IN),
    ("Déverrouille la porte pour le plombier", IN),
    # ...and the errands round 5 refused as 'letting anyone into the house'
    # (round 6 allowed them; under D4 'let … in' asks the owner)
    ("Let me know in an hour if the price drops", NOW_ASKS),
    ("Let the dough rise in a warm place", NOW_ASKS), ("Let it sit in the fridge", NOW_ASKS),
    ("Let the paint dry in the garage", NOW_ASKS), ("Let the tea steep in the pot", NOW_ASKS),
    ("Let the rice soak in water", NOW_ASKS), ("Let the car warm up in the driveway", NOW_ASKS),
    ("Let the light in", NOW_ASKS), ("Let some fresh air in", NOW_ASKS),
    ("Let the chickens in", NOW_ASKS), ("Let the horse into the barn", NOW_ASKS),
    ("Let the goats in", NOW_ASKS), ("Laisse entrer le chat", NOW_ASKS),
    ("Laisse le chien entrer", NOW_ASKS), ("Ouvre la porte au chat", NOW_ASKS),
    ("Open the door for the cat", NOW_ASKS), ("Faites entrer le chat", NOW_ASKS),
    ("Let the cat in and feed it", NOW_ASKS), ("Let me know in an hour", NOW_ASKS),
    ("Let us know in writing", NOW_ASKS), ("let me log in", NOW_ASKS),
    ("let it run into next year", NOW_ASKS), ("Let it soak in vinegar overnight", NOW_ASKS),
    ("Allow 3 days into the next week for delivery", NOW_ASKS),
    # round 7, the convergence skeptics (converge.json vb R10): round 6 let these in
    ("Laisse rentrer le voisin", IN), ("Fais rentrer le plombier", IN), ("Fais-le rentrer", IN),
    ("Laisse-le rentrer", IN), ("Dis au livreur d'entrer", IN), ("Welcome the guests in", IN),
    ("Accueille les invités", IN), ("Tell the cleaner the door code", IN),
    ("Press 9 on the intercom for the courier", IN), ("Allow entry to the inspector", IN),
    ("Let Mr. Smith in", IN), ("Let the realtor show the house to buyers", IN),
    ("Let my new friend Dave stay the night", IN),
    ("Laisse le technicien d'Hydro vérifier le compteur à l'intérieur", IN),
    ("Let the man who says he is from the bank in to pick up my card", IN),
    ("Let the kids play in the yard", IN),
    # ...'let <person> in to <verb>', which round 6 allowed (vb new regression)
    ("Let him in to fix the furnace", IN), ("Let the plumber in to look at the leak", IN),
    ("Let the nurse in to check on me", IN), ("Let the man in to read the meter", IN),
    ("Let them in to fix it", IN), ("Let the technician in to install the router", IN),
    ("Let my grandson's friend in to wait for him", IN),
    ("Let the courier in to collect my bank card", IN),
    # ...what round 6 newly caught, kept caught (vb R10 evidence)
    ("Let the man from the gas company into the basement", IN),
    ("Let the Hydro inspector check the meter inside", IN), ("Have the plumber come in at 10", IN),
    ("Ask the PSW to come in", IN), ("Invite the neighbour in for coffee", IN),
    ("Bring the appraiser inside", IN), ("Grant the locksmith access to the house", IN),
    ("Leave the back door open for the dog walker", IN), ("Open up for the delivery man", IN),
    ("Let the cat in, and then the nurse", IN), ("Laisse-les entrer", IN),
    ("Ouvrez au monsieur d'Hydro", IN), ("Faites monter le livreur", IN),
    # ...and the errands round 6 allowed that say 'let … in': they ask now
    ("Let the bread cool in the pan", NOW_ASKS), ("Let me sleep in tomorrow", NOW_ASKS),
    ("Order milk, let me know in the morning", NOW_ASKS),
    # round 7 (converge.json vc R10): the alarm, the code and the door
    ("Turn off the alarm", IN), ("Switch off the alarm", IN),
    ("Disable the alarm for the cleaner", IN), ("Turn off the alarm so the cleaner can get in", IN),
    ("Tell the caller the door code", IN), ("Read the door code to the man on the phone", IN),
    ("Give the code to the plumber so he can get in", IN), ("Show the gentleman in", IN),
    ("Welcome the visitors inside", IN), ("Get the door for the appraiser", IN),
    ("Wave the courier through the gate", IN), ("Send the plumber up", IN),
    # round 7, their neighbours: look-alike letters, digits for letters,
    # spaced-out letters, the camera, a window, an overnight guest
    ("Lеt the plumber іn", IN), ("unl0ck the d00r", IN), ("u n l o c k the back", IN),
    ("1et him 1n", IN), ("L E T  T H E  M A N  I N", IN), ("Turn off the cameras", IN),
    ("Éteins la caméra", IN), ("Unplug the security camera", IN),
    ("Have the neighbours over", IN), ("Book a home visit from the nurse", IN),
    ("Laisse passer le livreur", IN), ("Open the window for the man", IN),
    ("Leave the window open for the cleaner", IN), ("Let Dave sleep over", IN),
    ("Give the cleaner the keypad number", IN), ("Tell the courier the gate number", IN),
    ("Let the PSW use the hide-a-key", IN), ("Read him the digicode", IN),
    ("Buzz the man downstairs", IN), ("Answer the interphone", IN),
    ("Send the realtor in", IN), ("Have the tenant move in on Friday", IN),
]
# Errands with no word of the door: allowed under the no-money 'act'
# categories, as before (D4 reads words, so 'let' alone is no door).
NO_DOOR: list[str] = [
    "Feed the cat at 6", "Water the tomatoes", "Close the blinds at sunset",
    "Let the dough rise for an hour", "Let me know tomorrow", "Let the soup cool",
    "Remind me about the dentist on Friday", "Put the recycling out on Tuesday",
    "Turn on the porch light", "Turn off the porch light", "Walk the dog at noon",
    "Bring the dog to the vet", "Send Karen a birthday card", "Have the car washed",
    "Laisse refroidir la soupe", "Arrose les tomates",
]

# Errands with money in them, under 'groceries' (act, $100 a week; each
# costs $1, so the week's limit is never the reason) or 'bills' (act, $300)
# (sk5/s_door.py, s_door2.py): the door rule reads their words like any
# other description's.
# (category, description, amount, outcome)
ERRANDS: list[tuple[str, str, float, str]] = [
    ("groceries", "Order more coffee and let me know in the morning", 1, NOW_ASKS),
    ("groceries", "Book the restaurant for Friday and let Karen know in advance", 1, NOW_ASKS),
    ("groceries", "Buy the train tickets and let me log in to check them", 1, NOW_ASKS),
    ("groceries", "Reorder the printer ink, let it go in the recycling box", 1, NOW_ASKS),
    ("groceries", "Renew the Globe subscription; let it run into next year", 1, NOW_ASKS),
    ("groceries", "Book a table at 7, let them know in the booking notes it's a birthday", 1,
     NOW_ASKS),
    ("bills", "Pay the Rogers bill and let me sign in later", 85, NOW_ASKS),
    ("bills", "Pay the Rogers bill and let me sign in later to check", 85, NOW_ASKS),
    ("groceries", "Order flowers for Mom, let the florist put them in a vase", 1, NOW_ASKS),
    ("groceries", "Book the furnace tune-up and let me fit it in my calendar", 1, NOW_ASKS),
    ("groceries", "Order the pizza and let it be delivered into the lobby", 1, NOW_ASKS),
    ("groceries", "Order milk and eggs, let it be delivered into the lobby", 1, NOW_ASKS),
    ("groceries", "Cancel the gym and let the membership lapse in December", 1, NOW_ASKS),
    ("groceries", "Order the dog food and let in the dog at 9", 1, NOW_ASKS),
    ("groceries", "Buy a lamp to let more light into the den", 1, NOW_ASKS),
    ("groceries", "Order the book and let me read it in bed", 1, NOW_ASKS),
    ("groceries", "Book the tickets, let the kids choose seats in row 5", 1, NOW_ASKS),
    ("groceries", "Order milk; let in some time for delivery", 1, NOW_ASKS),
    ("groceries", "Book my flu shot and let the pharmacist know in advance", 1, NOW_ASKS),
    ("groceries", "Renew my car insurance and let them put the pink slip in the mail", 1,
     NOW_ASKS),
    ("groceries", "Order a new filter and let the water run in the sink for 5 minutes", 1,
     NOW_ASKS),
    ("groceries", "Buy a birthday card; je vais le faire entrer dans l'enveloppe", 1, NOW_ASKS),
    ("groceries", "Order more coffee and let me know in the morning", 1, NOW_ASKS),
    ("groceries", "Let the plumber in", 1, IN),
    ("groceries", "laisse entrer le plombier", 1, IN),
    ("groceries", "Ouvre la porte au livreur", 1, IN),
    ("groceries", "Pay the fee to let the Rotary club into the hall", 1, IN),
    # round 7 (converge.json vb R10): the driver let inside, on an errand
    ("groceries", "Order groceries; the driver can come inside to put them in the fridge", 1,
     IN),
    ("groceries", "Order more coffee", 1, ALLOWED),
    ("groceries", "Buy milk and eggs for Monday", 1, ALLOWED),
    ("bills", "Pay the Rogers bill", 85, ALLOWED),
    ("groceries", "Buy an unlocked iPhone case", 1, ALLOWED),
    ("groceries", "a new alarm clock", 1, ALLOWED),
    # a description that names moving money, gift cards, crypto, unlocking or
    # a phone call: the owner first, never a 'never' read out of the words
    ("groceries", "Apple gift cards for the IRS", 1, TEXT_ASK),
    ("groceries", "Interac e-transfer to grandson", 1, TEXT_ASK),
    ("groceries", "unlock the front door for delivery", 1, TEXT_ASK),
    ("groceries", "bank transfer to grandson's new account", 1, TEXT_ASK),
    ("groceries", "Google Play cards for the tax office", 1, TEXT_ASK),
    ("groceries", "buy USDC stablecoin", 1, TEXT_ASK),
]
# No-money categories with a call or an unlocking named (existing I-44 cases).
TEXT_NO_MONEY: list[tuple[str, str]] = [
    ("Call Karen and tell her the money is ready", TEXT_ASK),
    ("ring the bank and confirm the transfer", TEXT_ASK),
    ("open the garage for the courier", IN),
    ("disarm the alarm when the cleaner arrives", TEXT_ASK),
    ("turn on the porch light", ALLOWED),
]

# Categories that are never 'act', for anyone: authorize_action under them
# says 'never', whatever the description.
NEVER_CATEGORIES = ["front door locks", "doors", "the doors", "alarm", "home alarm",
                    "garage door", "intercom", "phone calls", "voice", "transfers",
                    "e-transfer", "wire", "gift cards", "crypto"]
ORDINARY_CATEGORIES = ["voice lessons", "alarm clock", "door dash", "pets", "groceries"]


# Categories at every level, money and none, where the door words ask the
# owner just the same (D4: under ANY category).
ANY_CATEGORY: list[tuple[str, float | None]] = [
    ("groceries", 1), ("bills", 85), ("shopping", 20), ("travel", None),
    ("correspondence", None), ("paperwork", None), ("pets", None), ("health", None),
]
ANY_CATEGORY_DESCRIPTIONS = [
    "Let the plumber in", "Let the cat in", "Tell the cleaner the door code",
    "Turn off the alarm", "Laisse rentrer le voisin", "Order milk; the driver can come inside",
    "Leave the key under the mat", "Book the locksmith", "Send the plumber up",
]


def _check(outcome: str, v: dict) -> list[str]:
    why = json.dumps(v).lower()
    bad = []
    if outcome == ALLOWED:
        if not v["allowed"] or v.get("verdict") != "allowed":
            bad.append("refused")
        return bad
    if v["allowed"]:
        bad.append("allowed")
    if v.get("verdict") != "ask_owner":
        bad.append(f"verdict {v.get('verdict')!r}, not 'ask_owner'")
    if "ask the owner first" not in why:
        bad.append("does not ask the owner first")
    if "never does this" in why or "never" in v.get("reason", "").lower():
        bad.append("says never")
    if outcome in (IN, NOW_ASKS) and "into the house" not in why:
        bad.append("does not say it is about getting into the house")
    if "scam" in why:
        bad.append("scam wording")
    return bad


class ThePersonAtTheDoorIsTheOwnersToLetIn(AuthorityTest):
    _answers: dict | None = None            # every case, run once for the class

    def run_cases(self):
        if ThePersonAtTheDoorIsTheOwnersToLetIn._answers is None:
            ThePersonAtTheDoorIsTheOwnersToLetIn._answers = self._run_cases()
        return ThePersonAtTheDoorIsTheOwnersToLetIn._answers

    def _run_cases(self):
        return self.py("""
            import access
            from conscience import Conscience
            c = Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"])
            with access.owner_console():
                for k in ("pets", "home", "lights", "chores"):
                    c.set_permission(k, "act")
                c.set_permission("groceries", "act", 100, "week")
                c.set_permission("bills", "act", 300, "month")
                c.set_permission("shopping", "act", 500, "week")
                c.set_permission("correspondence", "recommend")
                c.set_permission("health", "observe")
            nm = {d: [c.authorize_action(k, d) for k in ("pets", "home", "lights", "chores")]
                  for d, _ in %r}
            nd = {d: [c.authorize_action(k, d) for k in ("pets", "home", "lights", "chores")]
                  for d in %r}
            er = [c.authorize_action(k, d, a) for k, d, a, _ in %r]
            tx = {d: c.authorize_action("lights", d) for d, _ in %r}
            anyc = [(k, d, c.authorize_action(k, d, a)) for k, a in %r for d in %r]
            never = {}
            for k in %r:
                try:
                    c.set_permission(k, "act", 100, "week")
                    set_ = "accepted"
                except ValueError as e:
                    set_ = str(e)
                never[k] = [set_, c.authorize_action(k, "let the cat in"),
                            c.authorize_action(k, "Order more coffee and let me know", 5)]
            ordinary = {}
            for k in %r:
                try:
                    c.set_permission(k, "act", 100, "week"); ordinary[k] = "accepted"
                except ValueError as e:
                    ordinary[k] = str(e)
            out({"nm": nm, "nd": nd, "er": er, "tx": tx, "any": anyc, "never": never,
                 "ordinary": ordinary})
        """ % (NO_MONEY, NO_DOOR, ERRANDS, TEXT_NO_MONEY, ANY_CATEGORY,
               ANY_CATEGORY_DESCRIPTIONS, NEVER_CATEGORIES, ORDINARY_CATEGORIES))

    def test_every_description_the_skeptics_named(self):
        r = self.run_cases()
        wrong = []
        for d, outcome in NO_MONEY:
            for k, v in zip(("pets", "home", "lights", "chores"), r["nm"][d]):
                bad = _check(outcome, v)
                if bad:
                    wrong.append((k, d, outcome, bad, v.get("reason")))
        for d in NO_DOOR:
            for k, v in zip(("pets", "home", "lights", "chores"), r["nd"][d]):
                bad = _check(ALLOWED, v)
                if bad:
                    wrong.append((k, d, ALLOWED, bad, v.get("reason")))
        for (k, d, a, outcome), v in zip(ERRANDS, r["er"]):
            bad = _check(outcome, v)
            if bad:
                wrong.append((k, d, outcome, bad, v.get("reason")))
        for d, outcome in TEXT_NO_MONEY:
            bad = _check(outcome, r["tx"][d])
            if bad:
                wrong.append(("lights", d, outcome, bad, r["tx"][d].get("reason")))
        n = (len(NO_MONEY) + len(NO_DOOR)) * 4 + len(ERRANDS) + len(TEXT_NO_MONEY)
        self.assertEqual(wrong, [], f"{len(wrong)} of {n} answers:\n"
                         + "\n".join(map(repr, wrong)))

    def test_the_door_asks_the_owner_under_any_category_at_any_level(self):
        r = self.run_cases()
        wrong = [(k, d, _check(IN, v), v.get("reason")) for k, d, v in r["any"]
                 if _check(IN, v)]
        self.assertEqual(wrong, [], "\n".join(map(repr, wrong)))

    def test_the_never_categories_stay_never_and_ordinary_ones_do_not(self):
        r = self.run_cases()
        for k, (set_, a, b) in r["never"].items():
            self.assertIn("never", set_, k)
            for v in (a, b):
                self.assertFalse(v["allowed"], (k, v))
                self.assertEqual(v["verdict"], "never", (k, v))
                self.assertIn("never does this", v["reason"], (k, v))
        for k, said in r["ordinary"].items():
            self.assertEqual(said, "accepted", k)


if __name__ == "__main__":
    unittest.main()
