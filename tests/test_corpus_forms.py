"""
Frozen corpus — forms and the vault (R3, R4), repair round 6.

Two repair rounds patched the reading of a form's boxes word by word, and
each broke the boxes next to the ones it fixed: round 5 let his credit card
into 'ID card number', 'Union card number', 'National card number', 'PC card
number' and boxes that said 'do not enter a credit card number here', and it
emptied his own side of a two-sided bill of sale that had a plain 'Phone'
box. This file freezes every box and every form the round-4 and round-5
skeptics reported, with the outcome the product's principles ask for.

The structural rules it holds the forms to:

  R3  A payment card's secret (its number, its security code, its expiry)
      goes only into a box whose name or description EXPLICITLY asks for a
      credit, debit or payment card (or names a card brand, or CVV/CVC), and
      whose words name nothing else: no other card or number (health, ID,
      membership, library, union, national, PC, gift, Aeroplan, OHIP, VAC…,
      in English and French), no 'not' or 'do not'. Every word must be one a
      payment-card box uses. Anything else goes back to him (needs_you) with
      a plain reason. Failing closed is correct: a plain 'Card number' box
      now goes to him; a non-payment box never gets his card.

  R4  On a form with boxes for both a seller and a buyer, the side the model
      SAID (owner_is) is his, and a plain contact box (Phone, Email,
      Address, with no party word) follows that side; with nothing said,
      both sides' boxes and the plain contact boxes go to him. On a form with
      one side only and a shop's word (vendor, shop, store, merchant,
      retailer, dealer, warehouse, 'sold by', 'purchased from'…), or with a
      box for him himself ('Your name'), the party boxes go to him. A shop's
      box is never his.

FILL means the secret (or his detail) goes in; ASK means the box goes back
to him (needs_you) and nothing of his goes in; REFUSE means nothing goes in
(a box that names no card at all is not offered back as his to fill).
"""

from __future__ import annotations

import json
import unittest

from test_paperwork import PaperworkTest, TA, TOKENS

FILL, ASK, REFUSE = "fill", "ask", "refuse"
CARD = "4111111111111111"
NAME, ADDR, PHONE, MAIL = "Laszlo Czako", "12 Elm St", "613-555-0100", "laszlo@example.com"

# ------------------------------------------------------------------- R3
# (vault secret, box name, box description, outcome)
CARD_BOXES: list[tuple[str, str, str, str]] = [
    # round 4 verify-b (k/r3a.py): 'Card number' described as another card
    ("visa_card", "Card number", "Health card number", ASK),
    ("visa_card", "Card number", "Health card #", ASK),
    ("visa_card", "Card number", "Health card no.", ASK),
    ("visa_card", "Card number", "Enter your OHIP number", ASK),
    ("visa_card", "Card number", "OHIP #", ASK),
    ("visa_card", "Card number", "Ontario health number", ASK),
    ("visa_card", "Card number", "Medicare number", ASK),
    ("visa_card", "Card number", "Membership number", ASK),
    ("visa_card", "Card number", "Aeroplan number", ASK),
    ("visa_card", "Card number", "Air Miles collector number", ASK),
    ("visa_card", "Card number", "PC Optimum card", ASK),
    ("visa_card", "Card number", "Gift card number", ASK),
    ("visa_card", "Card number", "Presto card number", ASK),
    ("visa_card", "Card number", "Student ID card", ASK),
    ("visa_card", "Card number", "the number on the front of your health card", ASK),
    ("visa_card", "Card number", "Numéro de carte d'assurance maladie", ASK),
    ("visa_card", "Card number", "Numéro d'assurance maladie (RAMQ)", ASK),
    ("visa_card", "Card number", "Carte Soleil", ASK),
    ("visa_card", "Card number", "Numéro de la carte santé", ASK),
    ("visa_card", "Numéro de carte", "Carte d'assurance maladie", ASK),
    ("visa_card", "Card number", "Library", ASK),
    ("visa_card", "Card number", "Health", ASK),
    ("visa_card", "Card number", "Patient number", ASK),
    ("visa_card", "Card number", "Veterans Affairs Canada client number", ASK),
    ("visa_card", "Card number", "Card number on your health card", ASK),
    ("visa_card", "Card #", "OHIP", ASK),
    ("visa_card", "Card no.", "Health insurance", ASK),
    ("visa_card", "Card number", "Credit card number", FILL),
    ("visa_card", "Card number", "Visa or Mastercard", FILL),
    ("visa_card", "Card number", "", ASK),                        # names no payment card
    ("visa_card", "Card number", "Card number (16 digits)", ASK),
    ("visa_card", "Card number", "Credit card number used for the deposit", FILL),
    # round 4 verify-b (k/r3c.py): payment descriptions
    ("visa_card", "Card number", "Your card number (the long number on the front of your card)",
     ASK),
    ("visa_card", "Card number", "Enter the number on your bank card", FILL),
    ("visa_card", "Card number", "Numéro de carte de crédit", FILL),
    ("visa_card", "Card number", "Card number (credit or debit card)", FILL),
    ("visa_card", "Card number", "The 16-digit number on the front of the card", ASK),
    ("visa_card", "Card number", "Credit card number - no spaces", FILL),
    ("visa_card", "Card number", "Card number as it appears on your statement", ASK),
    ("visa_card", "Card number", "Card number shown on your Visa card", FILL),
    ("visa_card", "Credit card number", "Card number", FILL),
    ("visa_card", "Numéro de carte", "Numéro de la carte", ASK),
    ("visa_card", "Card number", "Debit or credit card", FILL),
    ("visa_card", "Card number", "Number on the card you will pay with", ASK),
    ("visa_card", "Card number", "Payment card number", FILL),
    ("visa_card", "Card number", "Card number for the monthly payment card", FILL),
    ("visa_card", "Card number", "Card number of the card holder", ASK),
    ("visa_card", "Card number", "Cardholder's card number", ASK),
    ("visa_card", "Card number", "Number of the card being charged", ASK),
    # round 4 verify-c (skep/vf.py)
    ("visa_card", "Debit card number", "", FILL),
    ("visa_card", "Bank card number", "", FILL),
    ("visa_card", "Visa card number", "", FILL),
    ("visa_card", "Mastercard number", "", FILL),
    ("visa_card", "Credit card", "", FILL),
    ("visa_card", "Card number", "Card used for payment", ASK),
    ("visa_card", "Card number", "Number of the card you pay with", ASK),
    ("visa_card", "Card number", "Long number on the front of the card", ASK),
    ("visa_card", "Card number", "Your Visa card", FILL),
    ("visa_card", "Card number", "Enter your credit card", FILL),
    ("visa_card", "Card number", "Credit or debit card", FILL),
    ("visa_card", "Card number", "Amex, Visa or Mastercard", FILL),
    ("visa_card", "Card No.", "Credit card number", FILL),
    ("visa_card", "cc_number", "Credit card number", FILL),
    ("visa_card", "Text1", "Credit card number", FILL),
    ("visa_card", "Card number", "Card number on your Costco Mastercard", ASK),
    ("visa_card", "Card number", "Your Capital One card", ASK),
    ("visa_card", "Card number", "Your RBC card", ASK),
    ("visa_card", "Card number", "Your TD Visa card", FILL),
    ("visa_card", "Card number", "Your PC Financial Mastercard", ASK),
    ("visa_cvv", "CVV", "3 digits on the back of your card", FILL),
    ("visa_cvv", "Security code", "On the back of your credit card", FILL),
    ("visa_cvv", "CVC", "Card verification code", FILL),
    ("visa_cvv", "Security code", "3 digits next to your signature on the card", ASK),
    # round 4 verify-c (skep/card.py)
    ("visa_card", "Card number", "Credit card number (Visa, Mastercard or Amex)", FILL),
    ("visa_card", "Card number", "16 digits on the front of your card", ASK),
    ("visa_card", "Card number", "Enter the long number on the front of your Visa", ASK),
    ("visa_card", "Card number", "Please enter your card number. We accept Visa and Mastercard. "
                                 "Never enter your PIN.", ASK),
    ("visa_card", "Card number", "Credit or debit card number", FILL),
    ("visa_card", "Card number", "The card you are paying with", ASK),
    ("visa_card", "Card number", "Credit card number - not your gift card", ASK),
    ("visa_card", "Credit card number", "", FILL),
    ("visa_card", "Credit card number", "Number on your credit card", FILL),
    ("visa_card", "Card number", "Your Costco Mastercard or any Visa", ASK),
    ("visa_card", "Payment card number", "Visa or Mastercard", FILL),
    ("visa_cvv", "CVV", "3-digit security code on the back of the card", FILL),
    ("visa_cvv", "Security code", "3 digits on the back of your credit card", FILL),
    # round 5 verify-b (p/r3.py): ID, union, national, PC cards and 'do not'
    ("visa_card", "Card number", "ID card number", ASK),
    ("visa_card", "Card number", "Your ID card", ASK),
    ("visa_card", "Card number", "ID number", ASK),
    ("visa_card", "Card number", "Card ID", ASK),
    ("visa_card", "Card number", "Please do not type a credit card number in this box because we "
                                 "only need the ten digit number printed on the front of your "
                                 "Ontario health card", ASK),
    ("visa_card", "Card number", "Do not enter a credit card number here but the number on your "
                                 "health card", ASK),
    ("visa_card", "Card number", "Never your credit card number: we need the number on the green "
                                 "Ontario health card", ASK),
    ("visa_card", "Card number", "Number on the front of the green card", ASK),
    ("visa_card", "Card number", "Your 10 digit card number", ASK),
    ("visa_card", "Card number", "Enter the 10-digit number and 2-letter version code", ASK),
    ("visa_card", "Card number", "Number and version code", ASK),
    ("visa_card", "Card number", "Visa number", ASK),               # a travel visa, as like as not
    ("visa_card", "Card number", "Visa number (see your passport)", ASK),
    ("visa_card", "Card number", "Your Visa number as printed in your passport", ASK),
    ("visa_card", "Card number", "PC card number", ASK),
    ("visa_card", "Card number", "Canadian Tire card number", ASK),
    ("visa_card", "Card number", "Costco card number", ASK),
    ("visa_card", "Card number", "Your Costco card", ASK),
    ("visa_card", "Card number", "Card number (Costco)", ASK),
    ("visa_card", "Card number", "Desjardins card number", ASK),
    ("visa_card", "Card number", "Bank card number for library services", ASK),
    ("visa_card", "Card number", "Bank of Canada", ASK),
    ("visa_card", "Card number", "National card number", ASK),
    ("visa_card", "Card number", "Union card number", ASK),
    ("visa_card", "Card number", "Union membership number", ASK),
    ("visa_card", "Card number", "Royal Canadian Legion card", ASK),
    ("visa_card", "Card number", "Capital One", ASK),
    ("visa_card", "Card number", "Royal Canadian Legion member number", ASK),
    ("visa_card", "Card number", "National Health card", ASK),
    ("visa_card", "Card number", "Indian Status card number", ASK),
    ("visa_card", "Card number", "Status card", ASK),
    ("visa_card", "Card number", "Numéro de carte", ASK),
    ("visa_card", "Card number", "Numéro de la carte d'identité", ASK),
    ("visa_card", "Card number", "Numéro de carte RAMQ", ASK),
    ("visa_card", "Card number", "Numéro de carte Desjardins", ASK),
    ("visa_card", "Card number", "Numéro de la carte de crédit, pas la carte santé", ASK),
    ("visa_card", "Card number", "Carte d'assurance maladie, pas la carte de crédit", ASK),
    ("visa_card", "Card number", "SIN card number", ASK),
    ("visa_card", "Card number", "Social insurance card number", ASK),
    ("visa_card", "Card number", "Medical card number", ASK),
    ("visa_card", "Card number", "Enter the card number shown on the front of your OHIP card", ASK),
    ("visa_card", "Card number", "Enter your health card", ASK),
    ("visa_card", "Card number", "Enter your credit card number. Health card number goes in box 7.",
     ASK),
    ("visa_card", "Card number", "Card used at the pharmacy", ASK),
    ("visa_card", "Card number", "Pharmacy card number", ASK),
    ("visa_card", "Card number", "Interac card number", ASK),
    ("visa_card", "Card number", "Interac e-Transfer card", ASK),
    ("visa_card", "Credit card number", "Health card number", ASK),
    ("visa_card", "Credit card number", "Aeroplan number", ASK),
    # round 5 verify-c (sk5/s_card.py): plain payment boxes and their descriptions
    ("visa_card", "Card number", "As it appears on your card", ASK),
    ("visa_card", "Card number", "Enter the number as it appears on your card", ASK),
    ("visa_card", "Card number", "No spaces or dashes", ASK),
    ("visa_card", "Card number", "Card to be charged", ASK),
    ("visa_card", "Card number", "The card we will charge each month", ASK),
    ("visa_card", "Card number", "Card used for automatic payments", ASK),
    ("visa_card", "Card number", "Credit card for the deposit", FILL),
    ("visa_card", "Card number", "Visa or Mastercard only", FILL),
    ("visa_card", "Card number", "We accept Visa, Mastercard and Amex", FILL),
    ("visa_card", "Card number", "Required", ASK),
    ("visa_card", "Card number", "Required field", ASK),
    ("visa_card", "Card number", "Please enter your card number", ASK),
    ("visa_card", "Credit card number", "Card number for payment of the annual fee", FILL),
    ("visa_card", "Credit card number", "For your donation", FILL),
    ("visa_card", "Credit card number", "Monthly gift", ASK),        # 'gift' names a gift card
    ("visa_card", "Credit card number", "Billing card", FILL),
    ("visa_card", "Credit card number", "Number of the card you will pay with", FILL),
    ("visa_card", "Numéro de carte de crédit", "", FILL),
    ("visa_card", "Numéro de carte", "Carte de crédit", FILL),
    ("visa_card", "Numéro de carte", "Le numéro inscrit sur votre carte", ASK),
    ("visa_card", "Numéro de carte de crédit", "Sans espaces", FILL),
    ("visa_card", "Card number", "16 digits", ASK),
    ("visa_card", "Cardholder card number", "", ASK),
    ("visa_card", "Payment card number", "Debit or credit", FILL),
    ("visa_card", "Card number", "Your Costco Mastercard", ASK),
    ("visa_card", "CC number", "", FILL),
    ("visa_card", "Credit card #", "", FILL),
    ("visa_card", "Card #", "Visa", ASK),
    ("visa_card", "Card number", "Card number*", ASK),
    ("visa_card", "Card No.", "Enter card number", ASK),
    ("visa_card", "Credit card number", "Card details", FILL),
    ("visa_card", "Credit card number", "Primary cardholder", ASK),
    ("visa_card", "Credit card number", "Card on file", ASK),
    ("visa_card", "Credit card number", "To pay for your order", FILL),
    ("visa_card", "Credit card number", "For the parking permit", ASK),
    # round 5 verify-c (sk5/s_card2.py): boxes about the card that are not its number
    ("visa_card", "Credit card", "Name on the card", ASK),
    ("visa_card", "Credit card", "Expiry date", ASK),
    ("visa_card", "Card", "Name as it appears on your card", ASK),
    ("visa_card", "Credit card", "Cardholder name", ASK),
    ("visa_card", "Visa", "Expiry", ASK),
    ("visa_card", "Credit card", "Last 4 digits", ASK),
    ("visa_card", "Card number", "Last 4 digits only", ASK),
    ("visa_card", "Card number", "Last four digits of your card", ASK),
    ("visa_card", "Credit card", "Billing address on file for the card", ASK),
    ("visa_card", "Credit card", "Postal code of the card", ASK),
    ("visa_card", "Credit card number", "Not your gift card", ASK),
    ("visa_card", "Card number", "Health card", ASK),
    ("visa_card", "Card number", "OHIP", ASK),
    ("visa_card", "Card number", "Membership", ASK),
    ("visa_card", "Card number", "Air Miles", ASK),
    ("visa_cvv", "Card", "The 3 digits on the back of your card", ASK),
    ("visa_cvv", "Security code", "", ASK),
    ("visa_cvv", "Security code", "3 digits on the back of your card", ASK),
    ("visa_cvv", "CVV", "Your Visa", FILL),
    ("visa_cvv", "Credit card", "", ASK),                   # the number's box, not the code's
    ("visa_cvv", "Card number", "Security code", ASK),
    # the expiry is a payment-card secret too: only into an expiry box that
    # names a payment card, never into the number's box
    ("visa_expiry", "Credit card number", "", ASK),
    ("visa_expiry", "Credit card expiry date", "", FILL),
    ("visa_expiry", "Expiry date", "", REFUSE),      # names no card at all
    ("visa_expiry", "Expiry date", "Passport expiry date", ASK),
    ("visa_expiry", "Expiry", "Credit card expiry (MM/YY)", FILL),
]

# Secrets that are not a payment card keep the rule they had (round 4
# verify-c skep/vf.py, skep/card.py): (secret, box texts, fits). A word the
# secret's own box does not use ('Ontario') still sends it back to him.
OTHER_SECRETS: list[tuple[str, tuple[str, ...], bool]] = [
    ("sin", ("SIN", "Social insurance number"), True),
    ("sin", ("Social insurance number", "9 digits, no spaces"), True),
    ("sin", ("SIN", "Social Insurance Number (9 digits)"), True),
    ("sin", ("SIN", "Health card number"), False),
    ("health_card", ("Health card number", "OHIP number"), True),
    ("health_card", ("Health card number", "Ontario health card (OHIP) number"), False),
    ("ohip", ("OHIP number", "Ontario health card"), False),
    ("ohip", ("Health card number",), True),
    ("bank_account", ("Account number", "Bank account number"), True),
    ("passport", ("Passport number", "As shown on your passport"), True),
    ("visa_card", ("Health card number",), False),
]

# fill_form labels, with any hint in brackets (k/r3b.py, p/r3b.py,
# skep/card.py): each on the terminal, MCP and HTTP.
CARD_LABELS: list[tuple[str, str]] = [
    ("Card number (Health card)", ASK), ("Card number - Health card", ASK),
    ("Card number: health card", ASK), ("Card number, health card", ASK),
    ("Card number / OHIP", ASK), ("Health card - card number", ASK),
    ("Card number (Membership)", ASK), ("Card number (Library)", ASK),
    ("Card number (health insurance)", ASK), ("Card number — library card", ASK),
    ("Numéro de carte (carte santé)", ASK), ("Card number", ASK),
    ("Card number (ID card)", ASK), ("Card number (Union card)", ASK),
    ("Card number (do not use a credit card number here but your health card)", ASK),
    ("ID card number", ASK), ("Union card number", ASK), ("Card number (PC card)", ASK),
    ("Credit card number (Visa, Mastercard or Amex)", FILL),
    ("Card number (16 digits on the front of your card)", ASK),
    ("Card number (no spaces)", ASK), ("Card number (debit or credit)", FILL),
    ("Card number [as printed on your card]", ASK),
    ("Card number (the card you pay with, not your health card)", ASK),
    ("Credit card number", FILL), ("Numéro de carte de crédit", FILL),
]

# ------------------------------------------------------------------- R4
# (what it is, boxes, owner_is, the boxes that get his details)
SIDES: list[tuple[str, list[str], str, set[str]]] = [
    # round 4 verify-c (skep/ff.py, skep/s30.py)
    ("warranty purchaser + dealer, buyer said",
     ["Purchaser name", "Purchaser address", "Purchaser phone", "Dealer name",
      "Date of purchase", "Model number"], "buyer", set()),
    ("warranty purchaser + dealer, nothing said",
     ["Purchaser name", "Purchaser address", "Dealer name", "Date of purchase"], "", set()),
    ("buyer-only registration, buyer said", ["Buyer name", "Buyer address", "Buyer phone", "Item"],
     "buyer", {"Buyer name", "Buyer address", "Buyer phone"}),
    ("auction buyer registration, nothing said", ["Buyer name", "Buyer phone", "Paddle number"],
     "", set()),
    ("consignment, seller boxes only, seller said",
     ["Seller name", "Seller address", "Seller phone", "Item description"], "seller",
     {"Seller name", "Seller address", "Seller phone"}),
    ("farmers market vendor form, seller said",
     ["Vendor name", "Vendor address", "Vendor phone", "Products sold"], "seller", set()),
    ("bill of sale, seller said", ["Seller name", "Seller address", "Buyer name", "Buyer address",
                                   "VIN"], "seller", {"Seller name", "Seller address"}),
    ("car dealer's sale, buyer said",
     ["Purchaser name", "Purchaser address", "Dealership name", "Salesperson", "VIN"], "buyer",
     set()),
    ("plain form with a store box", ["Full name", "Address", "Phone number", "Store number"], "",
     {"Full name", "Address", "Phone number"}),
    ("rebate form", ["Your name", "Your address", "Store where purchased", "Purchase date"], "",
     {"Your name", "Your address"}),
    ("applicant form", ["Applicant name", "Applicant address", "Applicant phone"], "",
     {"Applicant name", "Applicant address", "Applicant phone"}),
    ("applicant form with a buyer box", ["Applicant name", "Applicant address", "Buyer name"], "",
     {"Applicant name", "Applicant address"}),
    ("selling-30, nothing said", ["Seller full name", "Seller address", "Driver's licence number",
                                  "VIN", "Odometer reading", "Sale price", "Seller signature"], "",
     set()),
    ("selling-30, seller said", ["Seller full name", "Seller address", "Driver's licence number",
                                 "VIN", "Odometer reading", "Sale price", "Seller signature"],
     "seller", {"Seller full name", "Seller address"}),
    # round 4 verify-b (k/r4a.py), each with nothing, 'seller' and 'buyer' said
    *[(f"warranty FR, owner_is={s!r}", ["Votre nom", "Nom du vendeur", "Adresse du vendeur",
                                         "Date d'achat"], s, {"Votre nom"})
      for s in ("", "seller", "buyer")],
    *[(f"warranty purchased-from, owner_is={s!r}",
       ["Your name", "Your address", "Purchased from", "Purchased from - address",
        "Place of purchase", "Sold by"], s, {"Your name", "Your address"})
      for s in ("", "seller", "buyer")],
    *[(f"warranty supplier, owner_is={s!r}",
       ["Name", "Address", "Supplier name", "Supplier address", "Installer name",
        "Installer address", "Distributor name"], s, {"Name", "Address"})
      for s in ("", "seller", "buyer")],
    *[(f"warranty seller box beside his own, owner_is={s!r}",
       ["Your name", "Seller name", "Seller address", "Date of purchase"], s, {"Your name"})
      for s in ("", "seller", "buyer")],
    ("purchaser and vendor, nothing said",
     ["Purchaser name", "Purchaser address", "Vendor name", "Vendor address", "Model number"], "",
     set()),
    ("purchaser and vendor, buyer said",
     ["Purchaser name", "Purchaser address", "Vendor name", "Vendor address", "Model number"],
     "buyer", {"Purchaser name", "Purchaser address"}),
    ("purchaser and vendor, seller said",
     ["Purchaser name", "Purchaser address", "Vendor name", "Vendor address", "Model number"],
     "seller", {"Vendor name", "Vendor address"}),
    ("private car sale, nothing said",
     ["Vendor name", "Vendor address", "Purchaser name", "Purchaser address", "VIN"], "", set()),
    ("private car sale, seller said",
     ["Vendor name", "Vendor address", "Purchaser name", "Purchaser address", "VIN"], "seller",
     {"Vendor name", "Vendor address"}),
    ("private car sale, buyer said",
     ["Vendor name", "Vendor address", "Purchaser name", "Purchaser address", "VIN"], "buyer",
     {"Purchaser name", "Purchaser address"}),
    *[(f"lease, owner_is={s!r}", ["Landlord name", "Landlord address", "Tenant name",
                                   "Tenant address"], s, set()) for s in ("", "seller", "buyer")],
    *[(f"consignment, owner_is={s!r}", ["Consignor name", "Consignor address", "Consignee name",
                                         "Consignee address"], s, set())
      for s in ("", "seller", "buyer")],
    *[(f"trade-in, owner_is={s!r}", ["Customer name", "Customer address", "Dealer name",
                                      "Dealer address"], s, set()) for s in ("", "seller", "buyer")],
    *[(f"realtor, owner_is={s!r}", ["Listing agent", "Agent name", "Agent address", "Client name",
                                     "Client address"], s, set()) for s in ("", "seller", "buyer")],
    *[(f"donation, owner_is={s!r}", ["Donor name", "Donor address", "Recipient name",
                                      "Recipient address"], s, set())
      for s in ("", "seller", "buyer")],
    ("French bill of sale, nothing said", ["Nom du vendeur", "Adresse du vendeur",
                                           "Nom de l'acheteur", "Adresse de l'acheteur"], "", set()),
    ("French bill of sale, seller said", ["Nom du vendeur", "Adresse du vendeur",
                                          "Nom de l'acheteur", "Adresse de l'acheteur"], "seller",
     {"Nom du vendeur", "Adresse du vendeur"}),
    ("French bill of sale, buyer said", ["Nom du vendeur", "Adresse du vendeur",
                                         "Nom de l'acheteur", "Adresse de l'acheteur"], "buyer",
     {"Nom de l'acheteur", "Adresse de l'acheteur"}),
    # round 5 verify-b (p/r4.py)
    ("warranty retailer", ["Your name", "Your address", "Retailer name", "Retailer address",
                           "Date of purchase"], "", {"Your name", "Your address"}),
    ("warranty dealer", ["Your name", "Dealer name", "Dealer address"], "", {"Your name"}),
    ("warranty store", ["Your name", "Store name", "Store address"], "", {"Your name"}),
    ("warranty merchant", ["Your name", "Merchant name", "Merchant address"], "", {"Your name"}),
    ("warranty bought at", ["Your name", "Bought at", "Name of store", "Where bought"], "",
     {"Your name"}),
    ("warranty reseller", ["Your name", "Reseller", "Authorized dealer", "Service provider",
                           "Company name"], "", {"Your name"}),
    ("warranty warehouse", ["Your name", "Warehouse name", "Warehouse address"], "buyer",
     {"Your name"}),
    ("warranty FR shops", ["Votre nom", "Acheté chez", "Lieu d'achat", "Marchand", "Détaillant",
                           "Concessionnaire", "Nom du commerce"], "", {"Votre nom"}),
    ("warranty FR retailer", ["Nom", "Nom du détaillant", "Adresse du détaillant",
                              "Nom du marchand"], "", {"Nom"}),
    ("warranty brand", ["Name", "Address", "Brand", "Make", "Manufacturer name"], "",
     {"Name", "Address"}),
    ("purchaser and seller, buyer said", ["Purchaser name", "Seller name", "Seller address"],
     "buyer", {"Purchaser name"}),
    ("purchaser and seller, nothing said", ["Purchaser name", "Seller name", "Seller address"], "",
     set()),
    ("bill of sale 'sold by', seller said", ["Sold by", "Bought by", "VIN", "Price"], "seller",
     set()),
    ("bill of sale 'sold by (name)', seller said", ["Sold by (name)", "Sold to (name)", "VIN"],
     "seller", set()),
    ("bill of sale 'vendu par', seller said", ["Vendu par", "Acheté par", "NIV"], "seller", set()),
    ("bill of sale 'sold by', buyer said", ["Sold by", "Bought by", "VIN"], "buyer", set()),
    ("'purchased from' beside the purchaser, buyer said", ["Purchased from", "Purchaser name",
                                                           "VIN"], "buyer", set()),
    ("private sale, his own boxes and the buyer's, seller said",
     ["Your name", "Your address", "Buyer name", "VIN"], "seller", {"Your name", "Your address"}),
    ("private sale, his own box beside both sides, seller said",
     ["Your name", "Seller name", "Buyer name", "VIN"], "seller", {"Your name", "Seller name"}),
    ("selling-30 short, nothing said", ["Seller full name", "Seller address", "VIN"], "", set()),
    ("selling-30, 'vendor' said", ["Seller full name", "Seller address", "VIN"], "vendor",
     {"Seller full name", "Seller address"}),
    ("selling-30 French, 'vendeur' said", ["Nom du vendeur", "Adresse du vendeur", "NIV"],
     "vendeur", {"Nom du vendeur", "Adresse du vendeur"}),
    ("vendor registration, seller said", ["Vendor name", "Vendor address", "Products sold"],
     "seller", set()),
    ("farmers market, his own box beside the vendor's", ["Your name", "Vendor name", "Booth"],
     "seller", {"Your name"}),
    ("consignor, seller said", ["Consignor name", "Consignor address", "Item"], "seller", set()),
    ("estate sale with a dealer box, seller said",
     ["Seller name", "Seller address", "Buyer name", "Buyer address", "Dealer name"], "seller",
     {"Seller name", "Seller address"}),
    # round 5 verify-c (sk5/s_side.py): plain contact boxes on his own bill of sale
    ("bill of sale with Phone, seller said",
     ["Seller name", "Seller address", "Buyer name", "Buyer address", "Phone", "Date of sale",
      "Price"], "seller", {"Seller name", "Seller address", "Phone"}),
    ("bill of sale with Email, seller said",
     ["Seller name", "Seller address", "Buyer name", "Buyer address", "Email", "Vehicle"],
     "seller", {"Seller name", "Seller address", "Email"}),
    ("bill of sale, plain, seller said",
     ["Seller name", "Seller address", "Buyer name", "Buyer address", "Vehicle", "Price"],
     "seller", {"Seller name", "Seller address"}),
    ("bill of sale with Contact phone, seller said",
     ["Seller full name", "Seller address", "Buyer full name", "Buyer address", "Contact phone",
      "Signature"], "seller", {"Seller full name", "Seller address", "Contact phone"}),
    ("bill of sale with Phone, buyer said",
     ["Seller name", "Seller address", "Buyer name", "Buyer address", "Phone", "Date of sale",
      "Price"], "buyer", {"Buyer name", "Buyer address", "Phone"}),
    ("bill of sale with Phone and Address, nothing said",
     ["Seller name", "Buyer name", "Phone", "Address", "Date of sale"], "", set()),
    ("kijiji listing, seller said", ["Seller name", "Phone number", "Email address", "Item",
                                     "Asking price"], "seller",
     {"Seller name", "Phone number", "Email address"}),
    ("buyer registration with plain boxes, buyer said",
     ["Buyer name", "Buyer address", "Phone", "Email", "Item"], "buyer",
     {"Buyer name", "Buyer address", "Phone", "Email"}),
    ("consignment with a hint, seller said", ["Consignor (seller) name", "Seller address", "Phone",
                                              "Item"], "seller", {"Seller address", "Phone"}),
]
# boxes on a form with both sides that must come back to him when nothing
# was said (R4: a plain contact box could be either side's)
UNSAID_PLAIN = {"bill of sale with Phone and Address, nothing said": ["Phone", "Address"]}

# What was said that is no side at all: refused on every surface.
NOT_A_SIDE = ["I am selling my car", "owner", "spouse", "seller buyer"]

# fill_pdf with his own name or address handed in (k/r4b.py, sk5/s_pdf.py):
# (boxes on the form, the box written, owner_is, written?)
PDF_SIDES: list[tuple[list[str], str, str, bool]] = [
    (["Your name", "Vendor name", "Vendor address"], "Vendor address", "", False),
    (["Your name", "Vendor name", "Vendor address"], "Vendor name", "buyer", False),
    (["Your name", "Vendor name", "Vendor address"], "Vendor name", "seller", False),
    (["Your name", "Supplier name", "Supplier address"], "Supplier name", "", False),
    (["Your name", "Purchased from"], "Purchased from", "", False),
    (["Your name", "Sold by"], "Sold by", "", False),
    (["Your name", "Retailer name"], "Retailer name", "", False),
    (["Your name", "Store name"], "Store name", "", False),
    (["Your name", "Nom du magasin"], "Nom du magasin", "", False),
    (["Your name", "Nom du vendeur"], "Nom du vendeur", "", False),
    (["Seller name", "Buyer name"], "Seller name", "seller", True),
    (["Seller name", "Buyer name"], "Buyer name", "seller", False),
    (["Seller name", "Buyer name", "Dealer name"], "Seller name", "seller", True),
    (["Seller name", "Buyer name", "Dealer name"], "Dealer name", "seller", False),
    (["Seller name", "Buyer name"], "Seller name", "", False),
    (["Seller name", "Buyer name"], "Seller name", "Seller", True),
    (["Seller name", "Buyer name"], "Seller name", "the vendor", True),
    (["Seller name", "Buyer name"], "Seller name", "vendeur", True),
    (["Seller name", "Buyer name"], "Seller name", "I am the seller", False),
    (["Seller name", "Buyer name"], "Seller name", "owner", False),
    (["Seller name", "Seller address", "Buyer name", "Buyer address", "Phone", "Vehicle VIN",
      "Price"], "Seller name", "seller", True),
    (["Seller name", "Seller address", "Buyer name", "Buyer address", "Phone", "Vehicle VIN",
      "Price"], "Phone", "seller", True),
    (["Seller name", "Seller address", "Buyer name", "Buyer address", "Phone", "Vehicle VIN",
      "Price"], "Phone", "", False),
    (["Seller full name", "Seller address", "VIN"], "Seller full name", "seller", True),
    (["Vendor name", "Vendor address", "Products sold"], "Vendor name", "seller", False),
]


def _value(box: str) -> str:
    low = box.lower()
    if "phone" in low:
        return PHONE
    if "address" in low or "adresse" in low:
        return ADDR
    return NAME


class PaymentSecretsGoOnlyWhereAPaymentCardIsNamed(PaperworkTest):

    def test_every_box_the_skeptics_named(self):
        r = self.py("""
            import representative as rp
            import jefferey_mcp as m
            keep_secrets(visa_card=%r, visa_cvv="123", visa_expiry="09/29")
            res = []
            for i, (secret, name, tip, _) in enumerate(%r):
                texts = [name] + ([tip] if tip else [])
                form = make_form(f"c{i}.pdf", [{"name": name, "tu": tip}] if tip
                                 else [{"name": name}])
                x = mcp_call(m, "fill_pdf", {"pdf_path": form, "values": {name: "vault:" + secret}})
                res.append({"fits": rp.vault_fits(secret, *texts),
                            "written": "written" in x,
                            "needs_you": [n["field"] for n in x.get("needs_you", [])],
                            "why": " ".join(n["why"] for n in x.get("needs_you", []))})
            out(res)
        """ % (CARD, CARD_BOXES), JEFFEREY_CLIENT="jefferey")
        wrong = []
        for (secret, name, tip, want), got in zip(CARD_BOXES, r):
            if want == FILL:
                ok = got["fits"] and got["written"]
            elif want == REFUSE:
                ok = not got["fits"] and not got["written"]
            else:
                ok = not got["fits"] and not got["written"] and got["needs_you"] == [name]
            if not ok:
                wrong.append((secret, name, tip, want, got))
        self.assertEqual(wrong, [], f"{len(wrong)} of {len(CARD_BOXES)} boxes:\n"
                         + "\n".join(map(repr, wrong)))
        self.assertNotIn(CARD, self.egress.read_text() if self.egress.exists() else "")

    def test_the_plain_reason_says_what_the_box_lacks(self):
        r = self.py("""
            import representative as rp
            out({" | ".join(t): rp.box_disagrees(*t) for t in [("Card number",),
                 ("Card number", "Health card number"), ("Card number", "ID card number"),
                 ("Card number", "Do not enter a credit card number here"),
                 ("Credit card number",)]})
        """)
        self.assertIn("credit", r["Card number"].lower())
        for k in ("Card number | Health card number", "Card number | ID card number",
                  "Card number | Do not enter a credit card number here"):
            self.assertTrue(r[k], k)
        self.assertIsNone(r["Credit card number"])

    def test_other_secrets_keep_their_own_rule(self):
        r = self.py("""
            import representative as rp
            out([rp.vault_fits(s, *t) for s, t, _ in %r])
        """ % (OTHER_SECRETS,))
        self.assertEqual(r, [w for _, _, w in OTHER_SECRETS])

    def test_fill_form_labels_on_every_surface(self):
        r = self.py("""
            import jefferey_mcp as m, jefferey_chat as jc
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            keep_secrets(visa_card=%r)
            res = []
            for l, _ in %r:
                res.append([mcp_call(m, "fill_form", {"fields": [l]}),
                            c.post("/forms/fill", json={"fields": [l]}, headers=H(%r)).json(),
                            jc.dispatch_tool("fill_form", {"fields": [l]})])
            out(res)
        """ % (TOKENS, CARD, CARD_LABELS, TA), JEFFEREY_CLIENT="jefferey")
        wrong = []
        for (label, want), rows in zip(CARD_LABELS, r):
            for surface, x in zip(("mcp", "http", "terminal"), rows):
                filled = x.get("filled", {})
                left = [n["field"] for n in x.get("needs_you", [])]
                ok = (filled == {label: "vault:visa_card"} if want == FILL
                      else label not in filled and label in left)
                if not ok:
                    wrong.append((label, surface, want, filled, left))
        self.assertEqual(wrong, [], "\n".join(map(repr, wrong)))


class TheSideHeIsOnIsTheSideTheModelSaid(PaperworkTest):

    def test_every_form_the_skeptics_named_on_every_surface(self):
        r = self.py("""
            import jefferey_chat as jc
            for f, v in (("full name", %r), ("address", %r), ("phone", %r), ("email", %r)):
                his(f, v)       # his own details, set by him (round 8, S2)
            import jefferey_mcp as m
            os.environ["JEFFEREY_HTTP_TOKENS"] = %r
            import jefferey_http as h
            from fastapi.testclient import TestClient
            c = TestClient(h.app)
            res = []
            for _, f, said, _ in %r:
                res.append([jc.dispatch_tool("fill_form", {"fields": f, "owner_is": said}),
                            mcp_call(m, "fill_form", {"fields": f, "owner_is": said}),
                            c.post("/forms/fill", json={"fields": f, "owner_is": said},
                                   headers=H(%r)).json()])
            bad = [[jc.dispatch_tool("fill_form", {"fields": ["Seller name", "Buyer name"],
                                                   "owner_is": w}),
                    mcp_call(m, "fill_form", {"fields": ["Seller name"], "owner_is": w})]
                   for w in %r]
            out({"res": res, "bad": bad})
        """ % (NAME, ADDR, PHONE, MAIL, TOKENS, SIDES, TA, NOT_A_SIDE),
            JEFFEREY_CLIENT="jefferey")
        mine = {NAME, ADDR, PHONE, MAIL}
        wrong = []
        for (title, fields, said, his), rows in zip(SIDES, r["res"]):
            for surface, x in zip(("terminal", "mcp", "http"), rows):
                filled = x.get("filled", {})
                left = {n["field"] for n in x.get("needs_you", [])}
                problems = []
                if set(filled) != his:
                    problems.append(("filled", sorted(filled), "want", sorted(his)))
                if any(v not in mine for v in filled.values()):
                    problems.append(("values", filled))
                for b in UNSAID_PLAIN.get(title, []):
                    if b not in left:
                        problems.append(("not left for him", b))
                if problems:
                    wrong.append((title, surface, problems))
        self.assertEqual(wrong, [], f"{len(wrong)} form readings:\n" + "\n".join(map(repr, wrong)))
        for w, rows in zip(NOT_A_SIDE, r["bad"]):
            for x in rows:
                self.assertTrue(x.get("refused"), (w, x))
                self.assertNotIn("filled", x, w)

    def test_his_details_handed_to_fill_pdf(self):
        r = self.py("""
            import jefferey_chat as jc
            for f, v in (("full name", %r), ("address", %r), ("phone", %r)):
                his(f, v)       # his own details, set by him (round 8, S2)
            import jefferey_mcp as m
            res = []
            for i, (names, box, said, _) in enumerate(%r):
                form = make_form(f"p{i}.pdf", [{"name": n} for n in names])
                v = %r if "phone" in box.lower() else (%r if "address" in box.lower() else %r)
                x = mcp_call(m, "fill_pdf", {"pdf_path": form, "owner_is": said,
                                             "values": {box: v}})
                res.append("written" in x)
            out(res)
        """ % (NAME, ADDR, PHONE, PDF_SIDES, PHONE, ADDR, NAME), JEFFEREY_CLIENT="jefferey")
        wrong = [(names, box, said, want) for (names, box, said, want), got in zip(PDF_SIDES, r)
                 if got != want]
        self.assertEqual(wrong, [], "\n".join(map(repr, wrong)))

    def test_a_pdf_bill_of_sale_says_whose_side_it_took(self):
        r = self.py("""
            import jefferey_chat as jc
            for f, v in (("full name", %r), ("address", %r), ("phone", %r)):
                his(f, v)       # his own details, set by him (round 8, S2)
            import jefferey_mcp as m
            p = make_form("bos.pdf", [{"name": n} for n in ["Seller name", "Seller address",
                          "Buyer name", "Buyer address", "Phone", "Vehicle VIN", "Price"]])
            out({"read": mcp_call(m, "pdf_form_fields", {"pdf_path": p, "owner_is": "seller"}),
                 "fill": mcp_call(m, "fill_pdf", {"pdf_path": p, "owner_is": "seller",
                                  "values": {"Seller name": %r, "Seller address": %r}})})
        """ % (NAME, ADDR, PHONE, NAME, ADDR), JEFFEREY_CLIENT="jefferey")
        self.assertEqual(r["read"]["owner_is"], "seller", r["read"])
        self.assertEqual(sorted(r["read"]["for_someone_else"]), ["Buyer address", "Buyer name"])
        self.assertIn("written", r["fill"], r["fill"])


if __name__ == "__main__":
    unittest.main()
