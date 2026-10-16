"""
Round 9, the second repair — what the confirm check of 356c51f found
(cf9/w/nb: nb1.py, nb2.py, nb3.py, nb7.py, nb7b.py, nb8.py, nb9.py,
nb10.py, nb10b.py).

Structural, each from its probe:

    1  a 'not', 'never', 'pas', 'ni', 'except', 'but' … anywhere in an
       audience means it is not only him ('not me' was a silent yes, and a
       draft to 'pas moi' was never checked)
    2  a character that shows as nothing or as a blank inside a person's
       name is read both ways in every audience — as nothing, and as a
       space: a no holds if either reading holds; a yes only if both agree
       ('Karen\\u2800Novak' was nobody, and heard about his travel)
    3  a question is left out of the guess count only when every word of it
       is a word of the kind his rules close ('my health and my boat number
       4800' … '4824' never counted)
    4  an AI's value about something his rules hold back from it is answered
       the same whatever he holds (set_priority gave back his value)
    5  a sender is someone he recorded only by the sent-from address itself,
       read and matched exactly, accents and marks kept; an address that
       cannot be read is a stranger's, and a warning sign
    6  an audience made only of characters that show as nothing is no
       audience: the draft is checked as for anyone, and says so
    7  everything the shared fold reads as nothing counts as hidden (U+16FE4
       between words hid 'Unlock the front door' and the password)
    8  a merchant name with a mark the fold takes off — an accent, a line, a
       ring, a dot — that his own name for the plan does not have is a
       disguise, and asks him (CAA-QUÉBEC's own accent still matches)

Invented people only: his daughter Anna, his ex-wife Karen Novak, a
neighbour Bob Smith. Every address is on an example domain.
"""

from __future__ import annotations

import json
import unittest

from test_his_own import HisOwnTest

RESET = """
import pathlib
def clear_watch():
    p = pathlib.Path(os.environ['JEFFEREY_CONSCIENCE_PATH'])
    for x in p.parent.glob(p.stem + '.searches.json*'):
        x.unlink()
def reset(sections=("rules", "facts", "memories", "rule_proposals", "priorities", "goals",
                    "people", "_notices", "expected_charges", "charges_seen", "corrections",
                    "charge_proposals")):
    fresh()
    with access.owner_console():
        m.conscience.save_fresh(lambda d: [d.__setitem__(k, []) for k in sections])
        m.conscience.refresh()
    clear_watch()
"""

SURFACES = """
import jefferey_mcp as m, jefferey_chat as jc
h, c = http()
def disclosure(aud, tags):
    fresh(); h.conscience.refresh()
    return [mcp_as(m, "jefferey", "check_disclosure", {"audience": aud, "tags": tags}),
            c.get("/rules/check", params={"audience": aud, "tags": tags}, headers=H(TA)).json(),
            term("check_disclosure", {"audience": aud, "tags": tags}),
            c.get("/rules/guidance", params={"tags": tags, "audience": aud},
                  headers=H(TA)).json().get("disclosure", {})]
def drafts(text, aud):
    fresh(); h.conscience.refresh()
    return [term("check_draft", {"text": text, "audience": aud}),
            mcp_as(m, "jefferey", "check_draft", {"text": text, "audience": aud}),
            c.post("/draft-check", json={"text": text, "audience": aud}, headers=H(TA)).json()]
def guidance(purpose, aud):
    fresh(); h.conscience.refresh()
    return [mcp_as(m, "jefferey", "draft_guidance", {"purpose": purpose, "recipient": aud}),
            c.post("/draft-guidance", json={"purpose": purpose, "recipient": aud},
                   headers=H(TA)).json()]
"""

HIDDEN = {"2800": "⠀", "3164": "ㅤ", "200B": "​", "FEFF": "﻿",
          "16FE4": "\U00016fe4", "0332": "̲"}


# ========================================================================== 1
class F1ANegationIsNeverOnlyHim(HisOwnTest):
    """nb1.py rows A, nb9.py rows D: grounding.only_self read 'not', 'never',
    'pas' and 'even' past as words that make 'me' stronger, so 'not me',
    'pas moi', 'never me' and 'not even me' were wholly him: allowed:true,
    'the owner may always hear about themself', on MCP check_disclosure, HTTP
    /rules/check, the terminal and /rules/guidance, under 'Never tell my
    health to any AI' — and check_draft('Dad has HIV') to 'not me' was
    ok:true while draft_guidance handed over 'I have HIV'."""

    def test_an_audience_with_a_no_in_it_is_asked_about_as_that_audience(self):
        r = self.py(pre=SURFACES + RESET, code="""
            reset()
            with access.owner_console():
                m.life.add_person("Karen Novak", "ex-wife", notes="karen.novak@example.com")
                m.rules.set_rule("disclosure", "health", "Never tell Karen about my health",
                                 audience="Karen Novak", allow=False)
                m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                 audience="any AI", allow=False)
                m.conscience.remember_fact("I have HIV", "health")
                m.conscience.remember_fact("I owe $40,000 on my Visa", "money")
            res = {}
            for aud in ("not me", "pas moi", "never me", "not even me", "NOT ME", "jamais moi",
                        "ni moi", "me? no", "no, me", "everyone but me", "anyone except me",
                        "all except me", "tout le monde sauf moi", "other than me",
                        "besides me", "anyone other than me", "not myself"):
                res[aud] = disclosure(aud, "health")
            for aud in ("not me", "pas moi", "never me", "not even me", "except me"):
                res["draft " + aud] = [drafts("Dad has HIV", aud),
                                       guidance("a post about my HIV and my Visa debt", aud)]
            # he himself, however he writes it, still always hears about himself
            for aud in ("me", "Me", "myself", "just me", "moi", "moi-même", "me, myself and I"):
                res["self " + aud] = disclosure(aud, "health")[:3]
            res["self draft"] = drafts("Dad has HIV", "me")
            out(res)
        """)
        for aud, xs in r.items():
            if aud == "self draft":
                for x in xs:
                    self.assertTrue(x["ok"], x)
                continue
            if aud.startswith("draft "):
                checks, guides = xs
                for x in checks:
                    self.assertFalse(x["ok"], (aud, x))
                for g in guides:
                    s = json.dumps(g)
                    self.assertNotIn("I have HIV", s, aud)
                    self.assertNotIn("40,000", s, aud)
                continue
            for x in xs:
                if aud.startswith("self "):
                    self.assertTrue(x["allowed"], (aud, x))
                else:
                    self.assertFalse(x.get("allowed"), (aud, x))
                    self.assertNotIn("always hear", json.dumps(x), aud)


# ========================================================================== 2
class F2AHiddenCharacterInANameIsReadBothWays(HisOwnTest):
    """nb10.py 'aud' rows, nb10b.py: with 'Anyone may know when I travel'
    and 'Never tell Karen when I travel', check_disclosure('Karen\\u2800Novak',
    travel) was allowed:true on MCP, HTTP and the terminal, and
    draft_guidance's do_not_mention dropped from ['health', 'travel'] to []:
    the audience was read only as 'karennovak'. U+3164, U+200B and U+FEFF the
    same."""

    def test_a_no_holds_if_either_reading_holds_and_a_yes_only_if_both_do(self):
        r = self.py(pre=SURFACES + RESET, code=f"""
            HIDDEN = {HIDDEN!r}
            reset()
            with access.owner_console():
                m.life.add_person("Karen Novak", "ex-wife", notes="karen.novak@example.com")
                m.rules.set_rule("disclosure", "travel", "Anyone may know when I travel",
                                 audience="anyone", allow=True)
                m.rules.set_rule("disclosure", "travel", "Never tell Karen when I travel",
                                 audience="Karen Novak", allow=False)
                m.rules.set_rule("disclosure", "health", "Never tell Karen about my health",
                                 audience="Karen Novak", allow=False)
                m.conscience.remember_fact("I have HIV", "health")
            res = {{}}
            for nm, ch in HIDDEN.items():
                for aud in (f"Karen{{ch}}Novak", f"Kar{{ch}}en", f"Karen{{ch}}N."):
                    g = guidance("tell her about my trip and my HIV", aud)
                    res[f"{{nm}} {{aud!r}}"] = {{
                        "travel": [x.get("allowed") for x in disclosure(aud, "travel")[:3]],
                        "draft": [x.get("ok") for x in drafts("Dad has HIV", aud)],
                        "dnm": [sorted((x.get("disclosure") or {{}}).get("do_not_mention") or [])
                                for x in g]}}
            # controls: a plain stranger, written both ways, still hears what anyone may
            for aud in ("Bob Smith", "Bob\\u2800Smith", "Bob\\u200bSmith"):
                res["ctl " + aud] = [x.get("allowed") for x in disclosure(aud, "travel")[:3]]
            res["ctl Karen Novak"] = [x.get("allowed") for x in disclosure("Karen Novak",
                                                                            "travel")[:3]]
            # his own rule written with a hidden character: its no holds for her
            reset()
            with access.owner_console():
                m.life.add_person("Karen Novak", "ex-wife", notes="karen.novak@example.com")
                m.rules.set_rule("disclosure", "travel", "Anyone may know when I travel",
                                 audience="anyone", allow=True)
                m.rules.set_rule("disclosure", "travel", "Never tell Karen when I travel",
                                 audience="Karen\\u2800Novak", allow=False)
            res["rule no"] = [x.get("allowed") for x in disclosure("Karen Novak", "travel")[:3]]
            # ...and a yes written with one opens nothing that a plain one would not
            reset()
            with access.owner_console():
                m.life.add_person("Karen Novak", "ex-wife", notes="karen.novak@example.com")
                m.rules.set_rule("disclosure", "travel", "Karen may know when I travel",
                                 audience="Karen\\u2800Novak", allow=True)
            res["rule yes"] = [x.get("allowed") for x in disclosure("Karen Novak", "travel")[:3]]
            reset()
            with access.owner_console():
                m.life.add_person("Karen Novak", "ex-wife", notes="karen.novak@example.com")
                m.rules.set_rule("disclosure", "travel", "Karen may know when I travel",
                                 audience="Karen Novak", allow=True)
            res["plain yes, hidden asked"] = [x.get("allowed") for x in
                                              disclosure("Karen\\u2800Novak", "travel")[:3]]
            res["plain yes, plain asked"] = [x.get("allowed") for x in
                                             disclosure("Karen Novak", "travel")[:3]]
            out(res)
        """)
        for k, v in r.items():
            if k.startswith("ctl "):
                want = k != "ctl Karen Novak"
                self.assertEqual(v, [want] * 3, k)
                continue
            if k.startswith(("rule ", "plain yes, hidden")):
                self.assertEqual(v, [False] * 3, k)
                continue
            if k == "plain yes, plain asked":
                self.assertEqual(v, [True] * 3, k)
                continue
            self.assertEqual(v["travel"], [False] * 3, k)
            self.assertEqual(v["draft"], [False] * 3, k)
            for d in v["dnm"]:
                self.assertIn("travel", d, k)
                self.assertIn("health", d, k)


# ========================================================================== 3
class F3OnlyAQuestionMadeOfItsKindsWordsIsNotAGuess(HisOwnTest):
    """nb3.py rows G: subject_closed was true whenever a topic named a kind
    his rules close, whatever else it said, so 25 terminal explain_basis
    calls on 'my health and my boat number 4800' … '4824', and gpt-raw's
    HTTP /basis 'garage code 4800 money' … '4824', never counted: no pause,
    no notice to him."""

    def test_a_guess_with_a_closed_word_added_still_counts(self):
        r = self.py(pre=SURFACES + RESET, code="""
            def setup():
                reset()
                with access.owner_console():
                    m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                     audience="any AI", allow=False)
                    m.rules.set_rule("disclosure", "money", "Never tell my money to any AI",
                                     audience="any AI", allow=False)
                    m.conscience.remember_fact("I have type 2 diabetes and take metformin",
                                               "health")
                    m.conscience.remember_fact("Likes an aisle seat on long flights", "travel")
            def notices():
                m.conscience.refresh()
                return len([n for n in store().get("_notices") or []
                            if n.get("kind") == "searches"])
            res = {}
            setup()
            res["G term"] = [bool(term("explain_basis", {
                "topic": f"my health and my boat number {4800 + i}"}).get("refused"))
                for i in range(25)]
            res["G term notices"] = notices()
            setup()
            res["G2 http"] = [bool(c.get("/basis", params={"topic": f"garage code {4800 + i} money"},
                                         headers=H(TG)).json().get("refused")) for i in range(25)]
            res["G2 http notices"] = notices()
            setup()
            res["G mcp priorities"] = [mcp_as(m, "jefferey", "priorities_for", {
                "context": f"my diabetes and the PIN {4800 + i}"}) for i in range(25)]
            # plain questions about what his rules hold back: never a guess
            setup()
            qs = ["my diabetes", "my sugar", "my medication", "my doctor", "my health",
                  "my pills", "my blood pressure", "ma glycémie", "mon diabète",
                  "mes médicaments", "ma santé", "my HIV meds", "my debt", "my bank",
                  "my credit card", "my pension", "my health and my money"]
            res["plain"] = [bool(term("explain_basis", {"topic": qs[i % len(qs)]}).get("refused"))
                            for i in range(40)]
            res["plain flights"] = term("explain_basis", {"topic": "flights"})
            res["plain notices"] = notices()
            out(res)
        """)
        self.assertTrue(any(r["G term"]), r["G term"])
        self.assertEqual(r["G term"].index(True), 20, r["G term"])
        self.assertEqual(r["G term notices"], 1)
        self.assertTrue(any(r["G2 http"]), r["G2 http"])
        self.assertEqual(r["G2 http notices"], 1)
        self.assertIn("refused", json.dumps(r["G mcp priorities"][-1]))
        self.assertEqual(r["plain"], [False] * 40, r["plain"])
        self.assertIn("aisle", json.dumps(r["plain flights"]))
        self.assertEqual(r["plain notices"], 0)


# ========================================================================== 4
class F4AValueHisRulesHoldBackIsNeverEchoed(HisOwnTest):
    """nb7.py row 3, nb7b.py: with 'Never tell my health to any AI' and his
    value 'my HIV meds: brand name over cost', the jefferey key's
    set_priority(context 'my HIV meds', higher 'cost', lower 'brand name')
    answered higher 'brand name', lower 'cost' and 'He stated the opposite
    himself' on MCP, HTTP /priorities and the terminal — his held value word
    for word — while priorities_for held it back."""

    def test_set_priority_answers_the_same_whatever_he_holds(self):
        r = self.py(pre=SURFACES + RESET, code="""
            import re as _re
            def setup(held):
                reset()
                with access.owner_console():
                    m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                     audience="any AI", allow=False)
                    if held == "opposite":
                        m.conscience.set_priority(context="my HIV meds", higher="brand name",
                                                  lower="cost")
                    elif held == "same":
                        m.conscience.set_priority(context="my HIV meds", higher="cost",
                                                  lower="brand name")
                fresh(); h.conscience.refresh()
            def scrub(x):
                return _re.sub(r'"(?:id|updated|added|at|ts)": "?[^",}]*"?', '', json.dumps(x, sort_keys=True))
            args = {"context": "my HIV meds", "higher": "cost", "lower": "brand name"}
            res = {}
            for held in ("opposite", "same", "none"):
                setup(held)
                a = mcp_as(m, "jefferey", "set_priority", args)
                m.conscience.refresh()
                res[held] = {"stored": sorted((p.get("higher"), p.get("lower"))
                                              for p in store().get("priorities") or []),
                             "asked": [n.get("kind") for n in store().get("_notices") or []]}
                setup(held)
                b = c.post("/priorities", json=args, headers=H(TA)).json()
                setup(held)
                t = term("set_priority", args)
                setup(held)
                g = mcp_as(m, "claude-raw", "set_priority", args)
                res[held].update({"answers": [scrub(x) for x in (a, b, t, g)],
                                  "brand first": [x.get("higher") == "brand name" or
                                                  "opposite" in json.dumps(x)
                                                  for x in (a, b, t, g)]})
            out(res)
        """)
        for held in ("opposite", "same", "none"):
            self.assertEqual(r[held]["brand first"], [False] * 4, held)
        for i in range(4):
            self.assertEqual(r["opposite"]["answers"][i], r["none"]["answers"][i], i)
            self.assertEqual(r["same"]["answers"][i], r["none"]["answers"][i], i)
        # his own value is never turned round, and the question still reaches him
        self.assertEqual(r["opposite"]["stored"], [["brand name", "cost"]])
        self.assertIn("priority_question", r["opposite"]["asked"])


# ========================================================================== 5
class F5TheSenderIsTheSentFromAddressExactly(HisOwnTest):
    """nb8.py: when the sent-from address could not be read (an IP literal,
    'localhost', a quoted local part, a domain in another script), the
    address in the display name won, so '"anna.novak1985@example.com"
    <help.desk@[192.0.2.7]>' was 'Anna, someone he has recorded': the $900
    new-number scam was check_first 0.1 and 'are you away … while nobody's
    home' needs_decision with no interrupt. 'anna.novak1985@exämple.com' and
    'anná.novak1985@example.com' were hers too: the fold took the accents
    off."""

    def test_an_unreadable_or_accented_address_is_a_stranger_and_a_warning(self):
        r = self.py(pre=SURFACES + RESET, code="""
            reset()
            with access.owner_console():
                m.life.add_person("Anna", "daughter", notes="email anna.novak1985@example.com")
            fresh(); h.conscience.refresh()
            MONEY = ("Hi Dad, this is my new number, my phone broke. Can you send me $900 "
                     "for rent today?")
            AWAY = "Are you away this weekend? I want to drop something off while nobody's home."
            def tri(sender, body):
                return [mcp_as(m, "jefferey", "triage_message", {"sender": sender, "body": body}),
                        c.post("/triage", json={"sender": sender, "body": body},
                               headers=H(TA)).json(),
                        term("triage_message", {"sender": sender, "body": body})]
            S = {"e": '"anna.novak1985@example.com" <help.desk@[192.0.2.7]>',
                 "f": '"anna.novak1985@example.com" <helpdesk@localhost>',
                 "g": '"anna.novak1985@example.com" <"help desk"@example.net>',
                 "h": "anna.novak1985@ex\\u00e4mple.com",
                 "i": "ann\\u00e1.novak1985@example.com",
                 "i2": "anna\\u0301.novak1985@example.com",
                 "l": '"anna.novak1985@example.com" <help.desk@\\u4f8b\\u3048.jp>',
                 "m": "Anna <anna.novak1985@[192.0.2.7]>",
                 "n": "Anna <anna.novak1985@example.com",
                 "ctl a": '"Anna" <anna.novak1985@example.com>',
                 "ctl b": "anna.novak1985@example.com <anna.novak1985@example.com>",
                 "ctl c": "ANNA.NOVAK1985@EXAMPLE.COM"}
            res = {}
            for k, s in S.items():
                res[k] = {bn: [[x.get("verdict"), x.get("interrupt"),
                                "someone he has recorded" in str(x.get("sender_is")),
                                "nobody's address he has" in json.dumps(x.get("scam_flags"))]
                               for x in tri(s, b)]
                          for bn, b in (("money", MONEY), ("away", AWAY))}
            out(res)
        """)
        for k, v in r.items():
            for bn, xs in v.items():
                for verdict, interrupt, recorded, lookalike in xs:
                    if k.startswith("ctl"):
                        self.assertTrue(recorded, (k, bn))
                        continue
                    self.assertFalse(recorded, (k, bn))
                    self.assertTrue(interrupt, (k, bn))
                    self.assertTrue(lookalike, (k, bn))
                    if bn == "money":
                        self.assertEqual(verdict, "likely_scam", (k, bn))


# ========================================================================== 6
class F6AnAudienceThatShowsAsNothingIsNoAudience(HisOwnTest):
    """nb9.py rows A: with '\\u200b', '\\u3164', '\\u2800' or ' \\ufeff ' as the
    audience, check_draft('Dad has HIV') was ok:true on the terminal, MCP and
    HTTP /draft-check, and draft_guidance handed over 'I have HIV' and 'I owe
    $40,000 on my Visa': _recipient asked whether the audience was empty
    before reading it."""

    def test_a_blank_audience_is_checked_as_anyone_and_says_so(self):
        r = self.py(pre=SURFACES + RESET, code="""
            reset()
            with access.owner_console():
                m.conscience.remember_fact("I have HIV", "health")
                m.conscience.remember_fact("I owe $40,000 on my Visa", "money")
            res = {}
            for nm, aud in (("200B", "\\u200b"), ("3164", "\\u3164"), ("2800", "\\u2800"),
                            ("FEFF+spaces", " \\ufeff "), ("16FE4", "\\U00016fe4"),
                            ("mixed", "\\u200b \\u2800\\u3164\\u2060"), ("mark", "\\u0332")):
                res[nm] = {"draft": drafts("Dad has HIV", aud),
                           "guide": guidance("a post about my HIV and my Visa debt", aud)}
            res["ctl barbecue"] = drafts("Lovely day for a barbecue on Sunday.", "\\u2800")
            out(res)
        """)
        for k, v in r.items():
            if k == "ctl barbecue":
                for x in v:
                    self.assertTrue(x["ok"], x)
                    self.assertIn("checked_as", x)
                continue
            for x in v["draft"]:
                self.assertFalse(x["ok"], (k, x))
                self.assertIn("anyone", x.get("checked_as", ""), (k, x))
            for g in v["guide"]:
                s = json.dumps(g)
                self.assertNotIn("I have HIV", s, k)
                self.assertNotIn("40,000", s, k)
                self.assertIn("checked_as", g.get("disclosure", {}), k)


# ========================================================================== 7
class F7EverythingTheFoldDropsIsHidden(HisOwnTest):
    """nb10.py row 16FE4: U+16FE4 (a Khitan filler, a combining mark that
    shows as nothing) between words. The fold read it as nothing, but
    has_hidden did not count it, so the text was never also read with a
    space and the words glued: the door allowed
    'Unlock\\U00016fe4the\\U00016fe4front\\U00016fe4door'; an engine's
    'My\\U00016fe4PIN\\U00016fe4is\\U00016fe47731' was stored;
    'Jo\\U00016fe4is\\U00016fe4on\\U00016fe4chemo' was ok to the neighbours; and
    'Netflix\\U00016fe4password:\\U00016fe4Bluebird77' reached claude-raw and
    gpt-raw."""

    def test_has_hidden_counts_every_character_the_fold_reads_as_nothing(self):
        r = self.py(code="""
            import grounding, sys
            missed = []
            for cp in range(0x80, 0x110000):
                if 0xD800 <= cp <= 0xDFFF:
                    continue
                ch = chr(cp)
                if grounding._fold_char(ch, False) == "" and not grounding.has_hidden(ch):
                    missed.append(hex(cp))
            out({"missed": missed[:40], "n": len(missed),
                 "spaced": grounding.spaced("a\\U00016fe4b"),
                 "readings": list(grounding.readings("Unlock\\U00016fe4the\\U00016fe4door"))})
        """)
        self.assertEqual(r["missed"], [], r["n"])
        self.assertEqual(r["spaced"], "a b")
        self.assertIn("Unlock the door", r["readings"])

    def test_u16fe4_between_words_hides_nothing(self):
        r = self.py(pre=SURFACES + RESET, code="""
            import unicodedata
            ch = "\\U00016fe4"
            reset()
            with access.owner_console():
                m.rules.set_rule("disclosure", "health", "Never tell my health to any AI",
                                 audience="any AI", allow=False)
                m.conscience.remember_fact(f"I{ch}take{ch}Ozempic{ch}on{ch}Mondays", "general")
                m.conscience.remember_fact(f"Netflix{ch}password:{ch}Bluebird77", "general")
                m.conscience.set_permission("errands", "act")
            fresh(); h.conscience.refresh()
            s = (json.dumps(mcp_as(m, "claude-raw", "get_conscience"), ensure_ascii=False)
                 + c.get("/conscience", headers=H(TG)).text)
            vis = "".join(x for x in s if x.isascii() or unicodedata.category(x)[0] not in "MCZ")
            res = {"Bluebird77": "Bluebird77" in vis, "Mondays": "Mondays" in s}
            res["door"] = [mcp_as(m, "jefferey", "authorize_action", {
                "category": "errands", "description": d}).get("allowed")
                for d in (f"Let the plumber i{ch}n", f"Unlock{ch}the{ch}front{ch}door{ch}for{ch}him")]
            res["draft"] = [mcp_as(m, "jefferey", "check_draft", {
                "text": t, "audience": "the neighbours"}).get("ok")
                for t in (f"Jo is on che{ch}mo", f"Jo{ch}is{ch}on{ch}chemo")]
            res["stored"] = [not mcp_as(m, "jefferey", "remember_fact", {
                "fact": t, "category": "general"}).get("refused")
                for t in (f"My PIN is 7{ch}7{ch}3{ch}1", f"My{ch}PIN{ch}is{ch}7731")]
            t = mcp_as(m, "jefferey", "triage_message", {"sender": "+1 613 555 0199", "body":
                ch.join("Grandpa it's me I'm in jail and need bail money today please buy "
                        "Google Play gift cards and don't tell Mom".split())})
            res["bail"] = t.get("verdict")
            out(res)
        """)
        self.assertFalse(r["Bluebird77"])
        self.assertFalse(r["Mondays"])
        self.assertEqual(r["door"], [False, False])
        self.assertEqual(r["draft"], [False, False])
        self.assertEqual(r["stored"], [False, False])
        self.assertEqual(r["bail"], "likely_scam")


# ========================================================================== 8
class F8AMarkHisNameDoesNotHaveIsADisguise(HisOwnTest):
    """nb2.py rows C: 'N\\u00c9TFLIX.COM', 'NE\\u0301TFLIX.COM',
    'NET\\u0332FLIX.COM', 'NET\\u20ddFLIX.COM' and 'NETFLI\\u0307X.COM' at
    18.99 each passed as his plan ('expected'); the real NETFLIX.COM two days
    later was a 'duplicate' with $18.99 recoverable, and dispute_pack asked
    for $18.99."""

    def test_a_mark_the_fold_takes_off_asks_him(self):
        r = self.py(pre=SURFACES + RESET, code="""
            def pair(fake, real="NETFLIX.COM", plan="Netflix", amt=18.99, how="mcp"):
                reset()
                with access.owner_console():
                    m.guard.expect_charge(plan, amt, "monthly")
                fresh(); h.conscience.refresh()
                args = {"merchant": fake, "amount": amt, "date": "2026-09-01"}
                if how == "mcp":
                    a = mcp_as(m, "jefferey", "check_charge", args)
                elif how == "http":
                    a = c.post("/charges/check", json=args, headers=H(TA)).json()
                else:
                    a = term("check_charge", args)
                b = mcp_as(m, "jefferey", "check_charge", {"merchant": real, "amount": amt,
                                                           "date": "2026-09-03"})
                p = mcp_as(m, "jefferey", "dispute_pack", {"merchant": plan})
                return [a.get("verdict"), b.get("verdict"), b.get("recoverable"),
                        p.get("amount_in_dispute") or 0]
            res = {}
            for nm, fake in (("acute", "N\\u00c9TFLIX.COM"), ("combining acute", "NE\\u0301TFLIX.COM"),
                             ("low line", "NET\\u0332FLIX.COM"), ("circle", "NET\\u20ddFLIX.COM"),
                             ("dot above", "NETFLI\\u0307X.COM"), ("capital I dot", "NETFL\\u0130X.COM"),
                             ("cedilla", "NETFLIX.\\u00c7OM"), ("dotless i", "NETFL\\u0131X.COM")):
                res[nm] = pair(fake)
            res["http"] = pair("N\\u00c9TFLIX.COM", how="http")
            res["term"] = pair("NET\\u0332FLIX.COM", how="term")
            # his registered name's own accents still match it, either way written
            res["ctl CAA accent"] = pair("CAA-QU\\u00c9BEC", real="CAA QUEBEC",
                                         plan="CAA-Qu\\u00e9bec", amt=95.0)
            res["ctl CAA decomposed"] = pair("CAA-QUE\\u0301BEC", real="CAA QUEBEC",
                                             plan="CAA-Qu\\u00e9bec", amt=95.0)
            res["ctl CAA plain"] = pair("CAA QUEBEC", real="CAA-QU\\u00c9BEC",
                                        plan="CAA-Qu\\u00e9bec", amt=95.0)
            res["CAA other accent"] = pair("CAA-QU\\u00c8BEC", real="CAA QUEBEC",
                                           plan="CAA-Qu\\u00e9bec", amt=95.0)
            res["ctl plain"] = pair("NETFLIX.COM")
            out(res)
        """)
        for k, v in r.items():
            if k == "ctl plain" or k.startswith("ctl CAA"):
                self.assertEqual(v[:2], ["expected", "duplicate"], (k, v))
                continue
            self.assertEqual(v[0], "ask_owner", (k, v))
            self.assertEqual(v[1:], ["expected", 0.0, 0], (k, v))


if __name__ == "__main__":
    unittest.main()
