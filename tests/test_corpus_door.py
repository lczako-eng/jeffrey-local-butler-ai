"""
Frozen corpus — the door rule in authorize_action (R10), repair round 6.

Round 4 refused 'let … in' only for people on a list, so the dog walker,
the PSW, the realtor, his brother and his grandkids were let in. Round 5
refused every 'let … in' unless what came in was plainly an animal or the
air — and then 'Let me know in an hour', 'Let the dough rise in a warm
place' and 'Order milk and eggs, let it be delivered into the lobby' were
refused as 'letting anyone into the house … it may be a scam', whatever the
owner had set. This file freezes every description the round-4 and round-5
skeptics reported.

The structural rule:

  * The hard 'never' is decided by the CATEGORY alone: locks, doors,
    alarms, the garage door, the intercom, his voice, phone calls,
    transfers, wires, gift cards, crypto. Those are never 'act', for
    anyone, and authorize_action says so.
  * A description is never read for 'never'. When it lets a PERSON into
    the home — let / buzz / allow / show / bring … in, open (the door) for,
    leave the door unlocked for, laisser / faire entrer, ouvrir à — or
    names a pronoun for a person, the answer is 'ask the owner first': not
    allowed for the engine, in plain words, with no scam wording. The cat,
    the dog, the chickens and the fresh air may come in as before.
  * An errand that merely uses the words ('let me know in the morning', 'let
    it sit in the fridge', 'let the dough rise') is judged like any other
    errand. A description that names moving money, gift cards or crypto,
    or phoning as him, is likewise 'ask the owner first', never 'never'.
"""

from __future__ import annotations

import json
import unittest

from test_authority import AuthorityTest

IN, NOT_IN, NOT_DOOR, TEXT_ASK = "a person in", "not a person", "no door", "ask first"

# (description, outcome) under no-money 'act' categories ('pets', 'home',
# 'lights', 'chores'): a person let in asks the owner first; anything else
# is allowed there.
NO_MONEY: list[tuple[str, str]] = [
    # round 4 verify-b (k/r10a.py)
    ("Let the cat in", NOT_IN), ("let the dog in", NOT_IN), ("let the fresh air in", NOT_IN),
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
    ("Let Rex in", IN), ("Let Whiskers in", IN),          # a pet's name reads as a person's
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
    ("let the dog in before the storm", NOT_IN), ("let in the cat at 9", NOT_IN),
    ("Let the fresh air in: open the bedroom window", NOT_IN),
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
    ("Let me know in an hour if the price drops", NOT_IN),
    ("Let the dough rise in a warm place", NOT_IN), ("Let it sit in the fridge", NOT_IN),
    ("Let the paint dry in the garage", NOT_IN), ("Let the tea steep in the pot", NOT_IN),
    ("Let the rice soak in water", NOT_IN), ("Let the car warm up in the driveway", NOT_IN),
    ("Let the light in", NOT_IN), ("Let some fresh air in", NOT_IN),
    ("Let the chickens in", NOT_IN), ("Let the horse into the barn", NOT_IN),
    ("Let the goats in", NOT_IN), ("Laisse entrer le chat", NOT_IN),
    ("Laisse le chien entrer", NOT_IN), ("Ouvre la porte au chat", NOT_IN),
    ("Open the door for the cat", NOT_IN), ("Faites entrer le chat", NOT_IN),
    ("Let the cat in and feed it", NOT_IN), ("Let me know in an hour", NOT_IN),
    ("Let us know in writing", NOT_IN), ("let me log in", NOT_IN),
    ("let it run into next year", NOT_IN), ("Let it soak in vinegar overnight", NOT_IN),
    ("Allow 3 days into the next week for delivery", NOT_IN),
]

# Errands with money in them, under 'groceries' (act, $100 a week; each
# costs $1, so the week's limit is never the reason) or 'bills' (act, $300):
# the door rule never touches them (sk5/s_door.py, s_door2.py).
# (category, description, amount, outcome)
ERRANDS: list[tuple[str, str, float, str]] = [
    ("groceries", "Order more coffee and let me know in the morning", 1, NOT_IN),
    ("groceries", "Book the restaurant for Friday and let Karen know in advance", 1, NOT_IN),
    ("groceries", "Buy the train tickets and let me log in to check them", 1, NOT_IN),
    ("groceries", "Reorder the printer ink, let it go in the recycling box", 1, NOT_IN),
    ("groceries", "Renew the Globe subscription; let it run into next year", 1, NOT_DOOR),
    ("groceries", "Book a table at 7, let them know in the booking notes it's a birthday", 1,
     NOT_IN),
    ("bills", "Pay the Rogers bill and let me sign in later", 85, NOT_IN),
    ("bills", "Pay the Rogers bill and let me sign in later to check", 85, NOT_IN),
    ("groceries", "Order flowers for Mom, let the florist put them in a vase", 1, NOT_IN),
    ("groceries", "Book the furnace tune-up and let me fit it in my calendar", 1, NOT_IN),
    ("groceries", "Order the pizza and let it be delivered into the lobby", 1, NOT_IN),
    ("groceries", "Order milk and eggs, let it be delivered into the lobby", 1, NOT_IN),
    ("groceries", "Cancel the gym and let the membership lapse in December", 1, NOT_DOOR),
    ("groceries", "Order the dog food and let in the dog at 9", 1, NOT_IN),
    ("groceries", "Buy a lamp to let more light into the den", 1, NOT_IN),
    ("groceries", "Order the book and let me read it in bed", 1, NOT_IN),
    ("groceries", "Book the tickets, let the kids choose seats in row 5", 1, NOT_IN),
    ("groceries", "Order milk; let in some time for delivery", 1, NOT_IN),
    ("groceries", "Book my flu shot and let the pharmacist know in advance", 1, NOT_IN),
    ("groceries", "Renew my car insurance and let them put the pink slip in the mail", 1,
     NOT_IN),
    ("groceries", "Order a new filter and let the water run in the sink for 5 minutes", 1,
     NOT_IN),
    ("groceries", "Buy a birthday card; je vais le faire entrer dans l'enveloppe", 1, NOT_IN),
    ("groceries", "Order more coffee and let me know in the morning", 1, NOT_IN),
    ("groceries", "Let the plumber in", 1, IN),
    ("groceries", "laisse entrer le plombier", 1, IN),
    ("groceries", "Ouvre la porte au livreur", 1, IN),
    ("groceries", "Pay the fee to let the Rotary club into the hall", 1, IN),
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
    ("turn on the porch light", NOT_IN),
]

# Categories that are never 'act', for anyone: authorize_action under them
# says 'never', whatever the description.
NEVER_CATEGORIES = ["front door locks", "doors", "the doors", "alarm", "home alarm",
                    "garage door", "intercom", "phone calls", "voice", "transfers",
                    "e-transfer", "wire", "gift cards", "crypto"]
ORDINARY_CATEGORIES = ["voice lessons", "alarm clock", "door dash", "pets", "groceries"]


def _check(outcome: str, v: dict) -> list[str]:
    why = json.dumps(v).lower()
    bad = []
    if outcome == NOT_IN:
        if not v["allowed"]:
            bad.append("refused")
    elif outcome == NOT_DOOR:
        if "into the house" in why or "never does this" in why or "scam" in why:
            bad.append("read as a door")
    else:
        if v["allowed"]:
            bad.append("allowed")
        if "ask the owner first" not in why:
            bad.append("does not ask the owner first")
        if "never does this" in why or "never" in v.get("reason", "").lower():
            bad.append("says never")
        if outcome == IN and "into the house" not in why:
            bad.append("does not say it lets someone in")
        if outcome == IN and "scam" in why:
            bad.append("scam wording")
    return bad


class ThePersonAtTheDoorIsTheOwnersToLetIn(AuthorityTest):

    def run_cases(self):
        return self.py("""
            import access
            from conscience import Conscience
            c = Conscience(os.environ["JEFFEREY_CONSCIENCE_PATH"])
            with access.owner_console():
                for k in ("pets", "home", "lights", "chores"):
                    c.set_permission(k, "act")
                c.set_permission("groceries", "act", 100, "week")
                c.set_permission("bills", "act", 300, "month")
            nm = {d: [c.authorize_action(k, d) for k in ("pets", "home", "lights", "chores")]
                  for d, _ in %r}
            er = [c.authorize_action(k, d, a) for k, d, a, _ in %r]
            tx = {d: c.authorize_action("lights", d) for d, _ in %r}
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
            out({"nm": nm, "er": er, "tx": tx, "never": never, "ordinary": ordinary})
        """ % (NO_MONEY, ERRANDS, TEXT_NO_MONEY, NEVER_CATEGORIES, ORDINARY_CATEGORIES))

    def test_every_description_the_skeptics_named(self):
        r = self.run_cases()
        wrong = []
        for d, outcome in NO_MONEY:
            for k, v in zip(("pets", "home", "lights", "chores"), r["nm"][d]):
                bad = _check(outcome, v)
                if bad:
                    wrong.append((k, d, outcome, bad, v.get("reason")))
        for (k, d, a, outcome), v in zip(ERRANDS, r["er"]):
            bad = _check(outcome, v)
            if bad:
                wrong.append((k, d, outcome, bad, v.get("reason")))
        for d, outcome in TEXT_NO_MONEY:
            bad = _check(outcome, r["tx"][d])
            if bad:
                wrong.append(("lights", d, outcome, bad, r["tx"][d].get("reason")))
        n = len(NO_MONEY) * 4 + len(ERRANDS) + len(TEXT_NO_MONEY)
        self.assertEqual(wrong, [], f"{len(wrong)} of {n} answers:\n"
                         + "\n".join(map(repr, wrong)))

    def test_the_never_categories_stay_never_and_ordinary_ones_do_not(self):
        r = self.run_cases()
        for k, (set_, a, b) in r["never"].items():
            self.assertIn("never", set_, k)
            for v in (a, b):
                self.assertFalse(v["allowed"], (k, v))
                self.assertIn("never does this", v["reason"], (k, v))
        for k, said in r["ordinary"].items():
            self.assertEqual(said, "accepted", k)


if __name__ == "__main__":
    unittest.main()
