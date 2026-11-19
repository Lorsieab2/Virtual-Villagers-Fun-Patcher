"""Player Events (src/vv_player_events.py, docs/player-events-format.md): the plain-text format, its checks, the
compile into the collection's own files, the AI prompt, and the round trip of the built-in events.

Run alone: python -m pytest -p no:xdist tests/test_player_events.py"""
from __future__ import annotations

import copy
import json
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import vv_cie_graph as cie  # noqa: E402
import vv_event_content as content  # noqa: E402
import vv_player_events as pe  # noqa: E402

DOC = (ROOT / "docs" / "player-events-format.md").read_text(encoding="utf-8")


def doc_block(start: str) -> str:
    """The doc's code block that starts with `start`."""
    for block in re.findall(r"```\n(.*?)```", DOC, re.S):
        if block.startswith(start):
            return block
    raise AssertionError(f"no example starting {start!r} in the doc")


def one(text: str) -> pe.Item:
    items = pe.parse_text(text, "t.txt")
    assert len(items) == 1, [i.title for i in items]
    return items[0]


def compiled(text: str) -> pe.Compiled:
    it = one(text)
    assert not it.problems, [str(p) for p in it.problems]
    c, probs = pe.compile_item(it, "pl_test_001")
    assert c is not None, probs
    return c


SIMPLE = """\
Title: The Coconut That Would Not Open
Applies to: VV1, VV3
Themes: comedy
Event:
(Name) has been trying to open the same coconut since sunrise.
Choice 1: Lend a Hand
* Outcome A (weight 3): (Name) and (helper) crack it open together.
  Effect: FOOD GAIN (small)
* Outcome B: The coconut rolls into the sea.
  Effect: INJURY helper (minor)
Choice 2: Leave (Him/Her) to It
* Outcome A: (Name) invents a splitting wedge.
  Effect: SKILL + Building a little
"""


class SimpleEvents(unittest.TestCase):
    def test_the_owner_layout_builds_a_question_with_random_outcomes(self):
        c = compiled(SIMPLE)
        g = c.graph
        self.assertEqual(c.games, [1, 3])
        self.assertEqual(g["start"], "ask")
        ask = g["nodes"]["ask"]
        self.assertEqual(ask["type"], "question")
        self.assertEqual([ch["label"] for ch in ask["choices"]], ["Lend a Hand", "Leave (Him/Her) to It"])
        branch = g["nodes"]["c1"]
        self.assertEqual(branch["type"], "branch")
        self.assertEqual([ch["weight"] for ch in branch["children"]], [3, 1])
        self.assertEqual(ask["choices"][1]["next"], "c2o1")          # one outcome: no roll
        self.assertEqual(list(g["roles"]), ["subject", "helper"])
        self.assertEqual(g["nodes"]["c1o2"]["effects"][0]["do"], "health_change")
        self.assertEqual(g["nodes"]["c1o2"]["effects"][0]["role"], "helper")
        self.assertTrue(c.cieg.startswith(b"CIEG"))

    def test_the_new_layout_and_its_effect_table(self):
        text = ("NEW-001 — THE BASKET LEFT IN THE RAIN   [VV1, VV2]\n"
                "A basket of fruit sat in the rain.\n"
                "  [Choice] Tip It Out\n"
                "      (Random outcome 1 of 2)\n"
                "      The top layer is sound, and the villagers rescue a little food.\n"
                "      (Random outcome 2 of 2)\n"
                "      The bottom has gone sour.\n"
                "  [Choice] Hang It High\n"
                "      (Random outcome 1 of 2)\n"
                "      The net holds.\n"
                "      (Random outcome 2 of 2)\n"
                "      The net sags.\n"
                "NEW-001 | A1 | FOOD GAIN (small) | \"The top layer is sound, and the villagers rescue a little food.\"\n"
                "NEW-001 | A2 | FOOD LOSS (small) | \"The bottom has gone sour.\"\n")
        c = compiled(text)
        self.assertEqual(c.title, "The Basket Left in the Rain")
        self.assertEqual(c.games, [1, 2])
        fx = c.graph["nodes"]["c1o2"]["effects"]
        self.assertEqual(fx[0]["do"], "food")
        self.assertLess(fx[0]["per_game"]["1"][0], 0)

    def test_title_case_is_checked_for_titles_and_choices(self):
        it = one(SIMPLE.replace("Lend a Hand", "lend a hand").replace("Would Not Open", "would not open"))
        words = " ".join(p.text for p in it.problems)
        self.assertIn("title is not in Title Case", words)
        self.assertIn("choice is not in Title Case", words)
        self.assertIsNone(pe.title_case_problem("The Basket Left in the Rain"))
        self.assertIsNone(pe.title_case_problem("RESTORE IT CAREFULLY"))

    def test_carriers_are_born_female_adults_unless_any_birth_sex(self):
        text = SIMPLE.replace("Effect: SKILL + Building a little", "Effect: PREGNANT mother WITH father")
        c = compiled(text)
        e = c.graph["nodes"]["c2o1"]["effects"][0]
        self.assertEqual((e["do"], e["role"], e.get("partner")), ("pregnant", "mother", "father"))
        self.assertNotIn("any_birth_sex", e)
        self.assertGreaterEqual(c.graph["roles"]["mother"]["min_age"], 18)
        e2 = compiled(text.replace("WITH father", "WITH father (ANY BIRTH SEX)")).graph["nodes"]["c2o1"]["effects"][0]
        self.assertTrue(e2["any_birth_sex"])

    def test_a_deadly_event_is_tagged_and_kept_for_the_61_gate(self):
        c = compiled(SIMPLE.replace("Effect: INJURY helper (minor)", "Effect: DEATH helper"))
        # The engine gates kill / vanish / ... itself; the content filters for deaths are written in.
        self.assertIn("island_event_filter_f03", c.graph["patches"])

    def test_bad_lines_are_reported_with_their_line_and_the_rest_installs(self):
        text = SIMPLE.replace("Effect: FOOD GAIN (small)", "Effect: FOOD RAIN (small)") + "\n" + SIMPLE.replace(
            "The Coconut That Would Not Open", "The Second Coconut")
        items = pe.parse_text(text, "t.txt")
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0].problems)
        self.assertEqual(items[0].problems[0].line, 8)
        self.assertFalse(items[1].problems)

    def test_guardians_of_isola_words_are_added_in_new_believers(self):
        text = SIMPLE.replace("Applies to: VV1, VV3", "Applies to: VV5").replace(
            "since sunrise.", "since sunrise, watched by two Heathens.")
        g = compiled(text).graph
        v = g["nodes"]["ask"]["variants"]
        self.assertTrue(any("Isolans" in x["text"] for x in v))

    def test_guardians_of_isola_believer_words(self):
        cases = {
            # The tribe as against the Isolans (the sentence names them): the tribe, its verb agreeing.
            "The believers gather while the Isolans watch.": "The tribe gathers while the Isolans watch.",
            "The believers are worried about the Heathens, and they talk.":
                "The tribe is worried about the Isolans, and they talk.",
            "All the believers have gone home; the Isolans stay.": "The whole tribe has gone home; the Isolans stay.",
            "The believers carry torches past the Isolan camp.": "The tribe carries torches past the Isolan camp.",
            "The believers quickly hurry from the Isolans.": "The tribe quickly hurry from the Isolans.",   # an adverb
            "The believers watched the Heathens.": "The tribe watched the Isolans.",
            "Our believers don't agree with the Isolans.": "The tribe doesn't agree with the Isolans.",
            "A believer smiles at an Isolan.": "A tribe member smiles at an Isolan.",
            "Two believers argue with a Heathen.": "Two tribe members argue with an Isolan.",
            # A person of faith (against a skeptic): the faithful, a villager of faith.
            "The believers gather.": "The faithful gather.",
            "Believers maintain it was a sign.": "The faithful maintain it was a sign.",
            "Some believers question it.": "Some of the faithful question it.",
            "A believer smiles.": "A villager of faith smiles.",
            "Two believers argue.": "Two villagers of faith argue.",
            "the new believers arrive": "the newcomers arrive",
            "New Believers is the game.": "New Believers is the game.",
        }
        for before, after in cases.items():
            self.assertEqual(pe._guardians(before), after, before)
        text = SIMPLE.replace("Applies to: VV1, VV3", "Applies to: VV5").replace(
            "since sunrise.", "since sunrise, watched by a believer.")
        v = compiled(text).graph["nodes"]["ask"]["variants"]
        self.assertTrue(any("a villager of faith" in x["text"] for x in v))
        self.assertIn("rather than \"believers\"", pe.ai_prompt())


class EveryEffectWord(unittest.TestCase):
    CASES = {
        "FOOD GAIN (huge)": "food", "TECH LOSS (normal)": "tech", "FOOD GAIN 200 TO 800": "food",
        "TECH AWARD (small)": "tech", "PAY AWARD": "pay_award", "SKILL - Research some": "skill",
        "MASTER Healing": "skill", "SKILL SET Healing 50": "skill", "LIKE + swimming": "preference",
        "DISLIKE - snakes": "preference", "LIKE + random": "preference", "INJURY fisher (serious)": "health_change",
        "ILLNESS fisher": "sick", "HEALTH fisher +10 TO +20": "health_change", "HEAL fisher": "health",
        "DEATH fisher CAUSE \"Lost at sea\"": "kill", "DISAPPEARS (fisher)": "vanish",
        "LOST FOREVER fisher": "die_unrecovered", "PREGNANCY LOSS mother": "baby_lost",
        "BIRTH THEN DEATH mother": "birth_then_die", "EARLY BIRTH mother": "deliver_early",
        "NEW VILLAGER (adult)": "new_villager", "DUPLICATE OF fisher": "new_villager", "CLONE OF fisher": "clone",
        "PREGNANT mother": "pregnant", "NURSING father WITH mother (ANY BIRTH SEX)": "nursing",
        "NEW LOOK (both) fisher": "appearance", "OLD LOOK fisher": "old_look", "SEX CHANGE fisher": "sex_change",
        "BODY SWAP fisher WITH cook": "body_swap", "LOSE NAME fisher": "lose_name", "CHANGE NAME fisher": "change_name",
        "CHANGE AGE fisher YOUNGER 5 YEARS": "change_age", "CHANGE AGE fisher TO elder": "change_age",
        "MOOD GOOD fisher": "mood", "CELEBRATE": "celebrate", "DAMAGE (small)": "damage",
        "BECOMES HEATHEN fisher": "status", "STORY MUTE fisher": "trait",
        "ACTION fisher \"Dance\"": "action",
        "CURE fisher": "cure", "REPAIR": "repair", "YOUNG LOOK fisher": "young_look",
        "SKILL + BEST some": "skill", "EVERYONE: MOOD GOOD": "mood", "EVERY HEALER: SKILL + Healing some": "skill",
        "3 RANDOM VILLAGERS: ILLNESS": "sick", "NEW VILLAGER (adult woman)": "new_villager",
        "NEW BABY OF THE NEWCOMERS": "new_villager", "PREGNANT mother WITH father (TWINS)": "pregnant",
        "CHANGE AGE fisher OLDER 20 YEARS (NEVER PAST ELDER)": "change_age", "CLONE OF newcomer": "clone",
        "OTHER PRESENTATION fisher": "presentation",
    }

    def test_the_new_kinds_carry_their_fields(self):
        def first(words):
            return pe.plain_effect(words).effects[0]
        self.assertEqual(first("EVERYONE: MOOD GOOD")["target"], {"all": True})
        self.assertNotIn("role", first("EVERYONE: MOOD GOOD"))
        self.assertEqual(first("EVERY HEALER: SKILL + Healing some")["target"], {"skill": "Healing"})
        self.assertEqual(first("3 RANDOM VILLAGERS: ILLNESS")["target"], {"random": 3})
        self.assertTrue(first("SKILL + BEST some")["best"])
        self.assertEqual(first("NEW VILLAGER (adult woman)")["sex"], "female")
        self.assertTrue(first("NEW BABY OF THE NEWCOMERS")["child_of_newest"])
        self.assertEqual(first("PREGNANT mother WITH father (TWINS OR TRIPLETS)")["babies"], "roll")
        self.assertEqual(first("CHANGE AGE fisher OLDER 20 YEARS (NEVER PAST ELDER)")["max_age"], 75)
        self.assertEqual(first("CLONE OF newcomer")["role"], "$newest")
        self.assertIsInstance(pe.plain_effect("EVERYONE: DEATH"), str)

    def test_every_plain_word_effect(self):
        for words, do in self.CASES.items():
            got = pe.plain_effect(words)
            self.assertNotIsInstance(got, str, (words, got))
            self.assertEqual(got.effects[0]["do"], do, words)

    def test_every_effect_kind_of_the_engine_has_plain_words(self):
        kinds = {do for do in self.CASES.values()}
        engine = set(cie.EFFECT_CODES) - {"skill_set"}
        self.assertEqual(engine - kinds, set())

    def test_the_effects_compile_in_a_new_believers_event(self):
        lines = [w for w in self.CASES if not w.startswith(("ACTION", "PAY AWARD"))]
        text = ("Title: Every Effect\nApplies to: VV5\nRole mother: nursing parent\n"
                "Role cook: adult\nRole father: adult\nEvent:\n(Name) wakes up.\nChoice 1: Go\n")
        for k, w in enumerate(lines):
            text += f"* Outcome {k}: Something happens.\n  Effect: {w}\n"
        text += "Choice 2: Stay\n* Outcome A: Nothing happens.\n"
        it = one(text)
        self.assertFalse(it.problems, [str(p) for p in it.problems])
        c, probs = pe.compile_item(it, "pl_every_001")
        self.assertIsNotNone(c, probs)


class ChangeNameToAFixedName(unittest.TestCase):
    """Effect 33 with a fixed name (engine 00e56af2c): the string field; the engine's name rule."""

    def test_the_name_compiles_into_the_effect_string_and_back(self):
        c = compiled(SIMPLE.replace("Effect: SKILL + Building a little", "Effect: CHANGE NAME TO Lani"))
        e = c.graph["nodes"]["c2o1"]["effects"][0]
        self.assertEqual((e["do"], e["name"]), ("change_name", "Lani"))
        back = cie.decompile_graph(c.cieg)
        names = [x.get("name") for n in back["nodes"].values() for x in n.get("effects", [])
                 if x["do"] == "change_name"]
        self.assertEqual(names, ["Lani"])
        c2 = compiled(SIMPLE.replace("Effect: SKILL + Building a little",
                                     "Effect: CHANGE NAME helper TO Mary-Ann O'Neil"))
        e2 = c2.graph["nodes"]["c2o1"]["effects"][0]
        self.assertEqual((e2["role"], e2["name"]), ("helper", "Mary-Ann O'Neil"))
        rnd = compiled(SIMPLE.replace("Effect: SKILL + Building a little", "Effect: CHANGE NAME"))
        self.assertNotIn("name", rnd.graph["nodes"]["c2o1"]["effects"][0])

    def test_a_bad_name_is_a_line_numbered_problem(self):
        for bad in ("1Lani", "Lani!", "A" * 32, "La_ni"):
            it = one(SIMPLE.replace("Effect: SKILL + Building a little", f"Effect: CHANGE NAME TO {bad}"))
            self.assertTrue(any(p.line == 13 and "CHANGE NAME" in p.text for p in it.problems), (bad, it.problems))
        _g, probs = cie.normalize({"format": cie.FORMAT, "version": 6, "title": "T", "games": [1],
                                   "roles": {"subject": {"kind": "villager"}}, "start": "a",
                                   "nodes": {"a": {"text": "Hi.", "effects": [
                                       {"do": "change_name", "name": "Bad!"}]}}})
        self.assertTrue(any("change_name name" in p for p in probs))
        self.assertTrue(cie.CHANGE_NAME_RE.match("Dr. Lani"))
        self.assertFalse(cie.CHANGE_NAME_RE.match("Lani "))


class TwoClones(unittest.TestCase):
    """Up to two clones of a villager (the owner): "count" 1 or 2, effect 30's value a (engine 3a670e469)."""

    def effect(self, words: str) -> dict:
        c = compiled(SIMPLE.replace("Effect: SKILL + Building a little", f"Effect: {words}"))
        e = c.graph["nodes"]["c2o1"]["effects"][0]
        back = cie.decompile_graph(c.cieg)
        again = [x for n in back["nodes"].values() for x in n.get("effects", []) if x["do"] == "clone"]
        self.assertEqual(again[0].get("count"), e.get("count"))
        return e

    def test_one_or_two_clones(self):
        self.assertNotIn("count", self.effect("CLONE OF helper"))
        self.assertEqual(self.effect("CLONE OF helper (2)")["count"], 2)
        self.assertEqual(self.effect("TWO CLONES OF helper")["count"], 2)
        self.assertNotIn("count", self.effect("CLONE OF helper (1)"))

    def test_more_than_two_is_refused(self):
        self.assertIsInstance(pe.plain_effect("CLONE OF helper (3)"), str)


class VillageSolidarityTag(unittest.TestCase):
    """"Solidarity: raise|lower|neutral" under an outcome: the page's node tag (cie-v6-binary.md 32)."""

    TAGGED = SIMPLE.replace("  Effect: FOOD GAIN (small)\n", "  Effect: FOOD GAIN (small)\n  Solidarity: Raise\n") \
                   .replace("  Effect: INJURY helper (minor)\n", "  Effect: INJURY helper (minor)\n  Solidarity: lower\n")

    @staticmethod
    def node_flags(cieg: bytes) -> dict[str, int]:
        """Each node's flags byte (byte 3 of its record), read straight from the compiled file."""
        h = cie._HEADER6.unpack_from(cieg, 0)
        n_node, n_string, o_node, o_string = h[10], h[15], h[19], h[25]
        offs = [struct.unpack_from("<I", cieg, o_string + 4 * i)[0] for i in range(n_string)]
        base = o_string + 4 * n_string
        out = {}
        for i in range(n_node):
            rec = o_node + i * cie._NODE.size
            sid = struct.unpack_from("<H", cieg, rec + 4)[0]
            name = cieg[base + offs[sid]:cieg.index(b"\0", base + offs[sid])].decode("ascii")
            out[name] = cieg[rec + 3]
        return out

    def test_the_line_tags_the_outcome_page_and_compiles_to_the_flag_bits(self):
        c = compiled(self.TAGGED)
        nodes = c.graph["nodes"]
        self.assertEqual(nodes["c1o1"]["solidarity"], "raise")
        self.assertEqual(nodes["c1o2"]["solidarity"], "lower")
        self.assertNotIn("solidarity", nodes["c2o1"])
        flags = self.node_flags(c.cieg)
        self.assertEqual(flags["c1o1"], 2)          # raise: code 1 in bits 1-2
        self.assertEqual(flags["c1o2"], 4)          # lower: code 2
        self.assertEqual(flags["c2o1"], 0)
        back = cie.decompile_graph(c.cieg)
        self.assertEqual(back["nodes"]["c1o1"]["solidarity"], "raise")
        self.assertEqual(back["nodes"]["c1o2"]["solidarity"], "lower")
        self.assertNotIn("solidarity", back["nodes"]["c2o1"])
        neutral = compiled(SIMPLE.replace("* Outcome B: The coconut rolls into the sea.\n",
                                          "* Outcome B: The coconut rolls into the sea.\n  Solidarity: neutral\n"))
        self.assertEqual(self.node_flags(neutral.cieg)["c1o2"], 6)

    def test_the_tag_round_trips_through_the_full_format(self):
        it = one(self.TAGGED)
        text = pe.full_text(it.graph, {})
        self.assertIn("  solidarity: raise\n", text)
        again = one(text)
        self.assertEqual([str(p) for p in again.problems], [])
        self.assertEqual(again.graph["nodes"]["c1o1"]["solidarity"], "raise")
        self.assertEqual(again.graph["nodes"]["c1o2"]["solidarity"], "lower")
        c, probs = pe.compile_item(again, "pl_test_001")
        self.assertIsNotNone(c, probs)
        self.assertEqual(self.node_flags(c.cieg), self.node_flags(compiled(self.TAGGED).cieg))

    def test_another_word_is_refused(self):
        it = one(SIMPLE.replace("  Effect: FOOD GAIN (small)\n", "  Effect: FOOD GAIN (small)\n  Solidarity: up\n"))
        self.assertTrue(any(p.line == 9 and "not raise, lower or neutral" in p.text for p in it.problems),
                        [str(p) for p in it.problems])

    def test_the_prompt_offers_the_line(self):
        text = pe.ai_prompt()
        self.assertIn('"Solidarity: raise", "Solidarity: lower" or "Solidarity: neutral" under an outcome', text)
        self.assertIn("unless the Village Solidarity patch is on", text)
        _g, probs = cie.normalize({"format": cie.FORMAT, "version": 6, "title": "T", "games": [1],
                                   "roles": {"subject": {"kind": "villager"}}, "start": "a",
                                   "nodes": {"a": {"text": "Hi.", "effects": [{"do": "clone", "count": 3}]}}})
        self.assertTrue(any("clone count is 1 or 2" in p for p in probs))

    def test_the_record_holds_the_count(self):
        g = {"format": cie.FORMAT, "version": 6, "title": "T", "games": [1], "roles": {"subject": {"kind": "villager"}},
             "start": "a", "nodes": {"a": {"text": "Hi.", "effects": [{"do": "clone", "count": 2}]}}}
        data = cie.compile_graph(cie.load(g))
        record = struct.pack("<BBBBii", cie.EFFECT_CODES["clone"], 0, 0, 0, 2, 0)
        self.assertIn(record, data)
        self.assertIn("TWO CLONES", pe.FORMAT_SECTION)


class LoseNameNeedsABump(unittest.TestCase):
    """The owner: a "?" name only comes from a bump on the head or something like it -- a soft warning, never an
    error."""

    def test_a_lose_name_page_without_a_cause_warns_but_installs(self):
        text = SIMPLE.replace("Effect: SKILL + Building a little", "Effect: LOSE NAME")
        it = one(text)
        self.assertFalse(it.problems)
        self.assertEqual(len(it.warnings), 1)
        self.assertEqual(it.warnings[0].line, 12)
        self.assertIn("Warning (not an error)", it.warnings[0].text)
        self.assertIsNotNone(pe.compile_item(it, "pl_t_001")[0])
        self.assertTrue(any("Warning" in p.text for p in pe.check_items([it])))
        bumped = one(text.replace("(Name) invents a splitting wedge.",
                                  "A falling coconut knocks (Name) on the head."))
        self.assertEqual(bumped.warnings, [])
        self.assertIn("bump on the head", pe.FORMAT_SECTION)
        self.assertIn("bump on the head", DOC)


class FormatSectionMatchesTheParser(unittest.TestCase):
    """The prompt's format section is what the parser reads: its example parses and compiles, and every effect it
    lists is a line the parser accepts."""

    def test_the_prompt_example_parses_and_compiles(self):
        fmt = pe.FORMAT_SECTION
        example = fmt[fmt.index("Title: The Coconut"):fmt.index("Names and pronouns")]
        compiled(example)

    def test_every_effect_the_prompt_lists_is_accepted(self):
        fmt = pe.FORMAT_SECTION
        section = fmt[fmt.index("Gameplay effects"):fmt.index("Optional lines")]
        samples = {"<skill>": "Healing", "<thing>": "swimming", "<who>": "fisher", "<n>": "5", "<name>": "Lani",
                   "<0-100>": "50", "<the game's own action words>": "Dance"}
        found = 0
        for phrase in pe.EFFECT_VOCABULARY:
            line = phrase
            for k, v in samples.items():
                line = line.replace(k, v)
            line = line.replace("a little|some|a lot|hugely", "a little").replace("[<who>|everyone]", "")
            line = re.sub(r"\[([^\]]*)\]", r"\1", line)
            line = re.sub(r"([A-Za-z0-9<>]+)(?:\|[A-Za-z0-9<>]+)+", r"\1", line)
            line = line.replace("<who>", "fisher").replace("(size)", "(small)").replace("...", "some").strip()
            got = pe.plain_effect(line)
            self.assertNotIsInstance(got, str, (phrase, line, got))
            head = phrase.split(" <")[0].split(" (")[0].split(" +")[0].split(" -")[0].split(" [")[0]
            head = re.sub(r" \d.*", "", head)
            self.assertIn(head.split("|")[0], section, phrase)
            found += 1
        self.assertGreater(found, 30)

    def test_every_craft_the_prompt_lists_parses_to_its_skills(self):
        # The prompt's crafts lines (style guide 8c) are read back word by word: each "words = Skill or Skill" group
        # must be what the parser gives for "SKILL + <craft> some".
        text = re.sub(r"\s+", " ", pe.ai_prompt())
        m = re.search(r"so <skill> may also be a craft: (.+?)\. Where two skills", text)
        self.assertIsNotNone(m, "the prompt lists the crafts")
        groups = 0
        for group in m.group(1).split("; "):
            words, skills = group.split(" = ")
            want = skills.split(" or ")
            for word in words.split(", "):
                with self.subTest(craft=word):
                    got = pe.plain_effect(f"SKILL + {word} some")
                    self.assertNotIsInstance(got, str, got)
                    self.assertEqual(got.effects[0]["skills"], want)
            groups += 1
        self.assertGreaterEqual(groups, 8)
        self.assertIn("Doubt is flavor only", text)
        self.assertIn("a doodle is not a sigil", text)
        self.assertIn("Only in VV4, which has cloth bolts, does it use up the village's real cloth bolts", text)
        self.assertIn("sails, awnings, patching roofs and huts, mending nets, bandaged repairs", text)

    def test_the_prompt_keeps_the_owner_sections_and_takes_the_players_parts(self):
        s = pe.Settings(count=3, favour=["sea"], rules={"no_deaths": True})
        text = pe.ai_prompt(5, s, "Themes: sea\nNo talking animals.\n# a note\n")
        for heading in ("1. Study My Events First", "2. Create an Interesting Story", "5. Respect My Content Rules",
                        "6. Respect Isola's World and Lore", "9. Output Format", "Final Instruction"):
            self.assertIn(heading, text)
        self.assertIn("Write Three Original Virtual Villagers Island Events", text)
        self.assertIn("distinct from the others", text)
        self.assertIn("THE PLAYER'S OWN RULES AND THEMES", text)
        self.assertIn("No talking animals.", text)
        self.assertNotIn("# a note", text)
        self.assertIn("- No deaths", text)
        self.assertIn(pe.TONE_NAME, text)
        self.assertIn("Title Case", text)
        self.assertNotIn("sentence case", text)
        one_event = pe.ai_prompt()
        self.assertIn("Write ONE Original", one_event)

    def test_the_shipped_prompt_is_the_default_prompt(self):
        shipped = (pe.PLAYER_FOLDER / pe.PROMPT_NAME).read_text(encoding="utf-8")
        self.assertEqual(shipped.replace("\r\n", "\n"), pe.ai_prompt())

    def test_the_style_guide_ships_byte_for_byte_and_the_prompt_follows_it(self):
        a = (pe.PLAYER_FOLDER / pe.STYLE_NAME).read_bytes()
        self.assertEqual(a, pe.STYLE_SOURCE.read_bytes())
        self.assertTrue(a.startswith(b"ISOLA ISLAND EVENT STYLE GUIDE"))
        self.assertIn(b"THE KEY TO THIS GUIDE", a)
        # The owner's updated master (2026-11-18): crafts, cloth, songs, lavastones, schools of thought, living culture.
        for heading in (b"8b. DEVOTION IN VV1-VV4", b"8c. CRAFTS COUNT AS THEIR MAIN SKILL",
                        b"8d. CLOTH IS A BUILDING AND REPAIR MATERIAL", b"8e. SONGS, CHANTS AND SPEECHES",
                        b"8f. LAVASTONES", b"8g. ISOLA'S SCHOOLS OF THOUGHT", b"10. ALWAYS",
                        b"Isola has a rich culture and living traditions of its own", b"APPENDIX A"):
            self.assertIn(heading, a)
        flat = re.sub(rb"\s+", b" ", a)
        self.assertIn(b"In VV4, which has cloth bolts, an event that uses cloth this way uses up real cloth bolts", flat)
        self.assertIn(b"potions, stews, remedies, poultices, salves, tonics and anything similar = Research or Healing",
                      flat)
        text = pe.ai_prompt()
        self.assertIn(f'follow my style guide, "{pe.STYLE_NAME}"', text)
        self.assertIn("does not apply to my own handwritten events", text)
        self.assertIn(f'THE KEY: my handwritten events ("{pe.TONE_NAME}") and my 20 example events '
                      f'("{pe.EXAMPLE_NAME}") are the key to my style guide', text)
        self.assertIn("Study both before you write", text)

    def test_the_owner_files_ship_byte_for_byte_and_the_prompt_names_them(self):
        for name in pe.OWNER_FILES:
            with self.subTest(name=name):
                self.assertEqual((pe.PLAYER_FOLDER / name).read_bytes(), (pe.OWNER_DOCS / name).read_bytes())
                self.assertIn(f'"{name}"', pe.ai_prompt())
        text = pe.ai_prompt()
        self.assertIn("balancing them", text)
        themes = pe.default_themes()
        self.assertIn("caves and exploring", themes)
        self.assertGreater(len(themes), 60)
        self.assertFalse([t for t in themes if "outcome showcase" in t])      # the drafts waiting for a GO left out
        self.assertTrue(pe.theme_hit(["sea"], ["dolphins and the sea"]))
        self.assertFalse(pe.theme_hit(["seaweed"], ["dolphins and the sea"]))

    def test_the_example_events_are_never_installed_as_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Player Events"
            src = pe.ensure_game_folder(1, root)
            (src / pe.EXAMPLE_NAME).write_bytes((pe.PLAYER_FOLDER / pe.EXAMPLE_NAME).read_bytes())
            (src / "mine.txt").write_text(SIMPLE, encoding="utf-8")
            out, report = pe.compile_folder(1, src, pe.Settings())
            self.assertEqual(report.installed, ["mine.txt: The Coconut That Would Not Open"])
            self.assertEqual([n for n in out if n.startswith("manifest-")], ["manifest-pl_mine.txt"])

    def test_the_tone_reference_ships_byte_for_byte(self):
        a = (pe.PLAYER_FOLDER / pe.TONE_NAME).read_bytes()
        self.assertEqual(a, pe.TONE_SOURCE.read_bytes())
        self.assertTrue(a.startswith(b"MORE ISLAND EVENTS") or len(a) > 10000)


class DocExamples(unittest.TestCase):
    def test_the_simple_example(self):
        compiled(doc_block("Title: The Coconut"))

    def test_the_full_example(self):
        c = compiled(doc_block("Title: The Great Beautification Project"))
        self.assertEqual(c.graph["nodes"]["ask"]["choices"][2]["if"], {"game": [3]})
        self.assertEqual(c.graph["nodes"]["r1"]["effects"][1]["role"], "builder1")

    def test_the_piece_example(self):
        items = pe.parse_text(doc_block("Piece: reef_setup"), "p.txt")
        self.assertEqual([i.kind for i in items], ["piece"] * 3)
        self.assertFalse([str(p) for i in items for p in i.problems])
        data, probs = pe.compile_pieces(items, 1)
        self.assertFalse([str(p) for p in probs])
        magic, version, head, size, crc = struct.unpack_from("<4sHHII", data)
        self.assertEqual((magic, version, head, size), (b"VPCB", 2, 64, len(data)))   # v2: 20-byte effects
        self.assertEqual(crc, zlib.crc32(data[:12] + b"\0\0\0\0" + data[16:]) & 0xFFFFFFFF)
        count, pieces_at = struct.unpack_from("<II", data, 20)
        self.assertEqual(count, 3)
        kinds = [data[pieces_at + 64 * k + 4] for k in range(count)]
        self.assertEqual(kinds, [1, 2, 3])


class Pieces(unittest.TestCase):
    def test_romance_never_meets_a_minor(self):
        text = ("Piece: kiss\nKind: Approach\nFamily: f\nLabel: Steal a Kiss\nTags: romance\n"
                "Role a: villager\nText: (A) falls for someone.\n")
        it = one(text)
        self.assertFalse(it.problems, [str(p) for p in it.problems])
        self.assertIn("minor", it.piece["never"])
        self.assertGreaterEqual(it.piece["slots"]["a"][0]["min_age"], 18)
        untagged = one(text.replace("Tags: romance\n", ""))
        self.assertTrue(any("romance" in p.text for p in untagged.problems))
        child = one("Piece: kid\nKind: Flavour\nRole k: child\nText: (K) builds a sandcastle.\n")
        self.assertIn("minor", child.piece["tags"])
        self.assertIn("romance", child.piece["never"])


class PieceEffectRecords(unittest.TestCase):
    """A mixer piece's effect record holds what vv_cie_graph's compiler writes for the same effect (Codex, #774)."""

    TEXT = ("Piece: x\nKind: Approach\nFamily: f\nLabel: Wave\nRole a: villager\nText: (A) waves at a boat.\n\n"
            "Piece: newc\nKind: Outcome\nFamily: f\nAnswers: x\nLabel: Welcome Her\nRole a: villager\n"
            "Text: (A) greets a stranger.\nEffect: NEW VILLAGER (adult woman)\nEffect: OTHER PRESENTATION (A)\n"
            "Effect: OWN PRESENTATION (A)\n")

    def records(self) -> list[tuple]:
        items = pe.parse_text(self.TEXT, "p.txt")
        data, probs = pe.compile_pieces(items, 1)
        self.assertFalse([str(p) for p in probs])
        effects_at, n_fx = struct.unpack_from("<II", data, 36)
        return [struct.unpack_from("<BBBBiiII", data, effects_at + 20 * k) for k in range(n_fx)]

    def test_a_new_villager_keeps_its_sex_and_copies_nobody(self):
        code, role, flags, _sel, a, b, _st, _extra = self.records()[0]
        self.assertEqual(code, cie.EFFECT_CODES["new_villager"])
        self.assertEqual((a, b), (cie.NEW_VILLAGER_AGES["adult"], cie.NEW_VILLAGER_SEX["female"]))
        self.assertEqual(role, 0xFF, "no copy_of: a new villager, not a lookalike of the piece's villager")
        self.assertEqual(flags, 0)
        man = pe._effect_record({"do": "new_villager", "age": "child", "sex": "male", "child_of_newest": True}, {}, 1)
        self.assertEqual(man[:4], (cie.EFFECT_CODES["new_villager"], cie.CHILD_OF_NEWEST_FLAG,
                                   cie.NEW_VILLAGER_AGES["child"], cie.NEW_VILLAGER_SEX["male"]))

    def test_other_presentation_is_on_and_own_is_off(self):
        other, own = self.records()[1:3]
        self.assertEqual((other[0], other[4]), (cie.EFFECT_CODES["presentation"], 1))
        self.assertEqual((own[0], own[4]), (cie.EFFECT_CODES["presentation"], 0))

    def test_every_effect_kind_has_a_layout_and_an_unknown_one_is_refused(self):
        for do in cie.EFFECT_CODES:
            if do == "skill_set":
                continue                         # the code of "skill" with "set", never a kind of its own
            with self.subTest(do=do):
                *_, bad = pe._effect_record({"do": do}, {}, 1)
                self.assertNotIn("not supported", bad)
        saved = dict(cie.EFFECT_CODES)
        try:
            cie.EFFECT_CODES["mystery_effect"] = 99
            record = pe._effect_record({"do": "mystery_effect", "role": "a"}, {"a": 0}, 1)
        finally:
            cie.EFFECT_CODES.clear()
            cie.EFFECT_CODES.update(saved)
        self.assertEqual(record[:5], (0, 0, 0, 0, ""))
        self.assertIn("not supported in mixer pieces", record[5])

    GROUPS = ("Piece: x\nKind: Approach\nFamily: f\nLabel: Wave\nRole a: villager\nText: (A) waves at a boat.\n\n"
              "Piece: party\nKind: Outcome\nFamily: f\nAnswers: x\nLabel: Throw a Party\nRole a: villager\n"
              "Text: (A) throws a party.\nEffect: EVERYONE: MOOD GOOD\nEffect: EVERY HEALER: SKILL + Healing some\n"
              "Effect: 3 RANDOM VILLAGERS: ILLNESS\n")

    def test_group_effects_are_written_with_their_selector(self):
        items = pe.parse_text(self.GROUPS, "p.txt")
        self.assertFalse([str(p) for i in items for p in i.problems])
        data, probs = pe.compile_pieces(items, 1)
        self.assertFalse([str(p) for p in probs])
        effects_at, n_fx = struct.unpack_from("<II", data, 36)
        strings_at = struct.unpack_from("<I", data, 28)[0]
        recs = [struct.unpack_from("<BBBBiiII", data, effects_at + 20 * k) for k in range(n_fx)]
        self.assertEqual([(r[0], r[1], r[3]) for r in recs],
                         [(cie.EFFECT_CODES["mood"], cie.TARGET_ROLE, cie.TARGET_ALL),
                          (cie.EFFECT_CODES["skill"], cie.TARGET_ROLE, cie.TARGET_SKILL),
                          (cie.EFFECT_CODES["sick"], cie.TARGET_ROLE, cie.TARGET_RANDOM)])
        self.assertEqual(recs[2][7], 3, "3 random villagers: N in the extra")
        skill_at = strings_at + recs[1][7]
        self.assertEqual(data[skill_at:data.index(b"\0", skill_at)], b"Healing", "the skill's name in the extra")

    def test_an_effect_the_file_cannot_hold_is_kept_as_flavor_and_the_piece_stays(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "mine.txt").write_text(self.GROUPS, encoding="utf-8")
            orig = pe._piece_effect_target

            def failing(e, local):
                if e["do"] == "sick":
                    raise KeyError("a group the file cannot hold")
                return orig(e, local)
            pe._piece_effect_target = failing
            try:
                out, report = pe.compile_folder(1, folder, pe.Settings())
            finally:
                pe._piece_effect_target = orig
        self.assertEqual(report.pieces, 2, "both pieces are kept")
        self.assertTrue(any(name.startswith("pieces-") for name in out))
        self.assertFalse(report.skipped, "nothing is Left out over an effect")
        self.assertTrue(any("kept as flavor" in n for n in report.notes), report.notes)

    def test_a_role_constraint_a_slot_cannot_hold_is_reported(self):
        text = ("Piece: x\nKind: Approach\nFamily: f\nLabel: Ask the Healer\nRole h: adult, skill Healing 50+\n"
                "Role w: adult, spouse of h\nText: (H) and (W) talk.\n")
        items = pe.parse_text(text, "p.txt")
        self.assertFalse([str(p) for i in items for p in i.problems])
        data, probs = pe.compile_pieces(items, 1)
        self.assertTrue(data, "the piece is kept")
        notes = [p.text for p in probs if p.kind == "note"]
        self.assertTrue(any("role h" in n and "skill Healing 50+" in n for n in notes), notes)
        self.assertTrue(any("role w" in n and "spouse of h" in n for n in notes), notes)
        self.assertFalse([p for p in probs if p.kind == "problem"])

    def test_only_an_outcomes_effects_are_written_the_others_are_kept_as_flavor(self):
        # The composer makes only an outcome's effects (story_procedural.inc): an effect on an approach is story only.
        text = self.GROUPS.replace("Text: (A) waves at a boat.\n", "Text: (A) waves at a boat.\nEffect: MOOD GOOD (A)\n")
        items = pe.parse_text(text, "p.txt")
        self.assertFalse([str(p) for i in items for p in i.problems])
        data, probs = pe.compile_pieces(items, 1)
        self.assertEqual([(p.kind, "only an outcome" in p.text) for p in probs], [("flavor", True)])
        self.assertEqual(struct.unpack_from("<I", data, 40)[0], 3, "the outcome's three effects only")
        self.assertEqual(struct.unpack_from("<I", data, 20)[0], 2, "both pieces kept")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "mine.txt").write_text(text, encoding="utf-8")
            _out, report = pe.compile_folder(1, Path(d), pe.Settings())
        self.assertFalse(report.skipped)
        self.assertTrue(any("only an outcome" in n and "kept as flavor" in n for n in report.notes), report.notes)

    def test_a_favoured_theme_weighs_the_outcomes_answers(self):
        # The composer draws an outcome by its Answers link weights (pc_link_weight), so a favoured theme's
        # multiplier goes there; with no theme favoured they are as written.
        items = pe.parse_text(self.GROUPS, "p.txt")

        def links(multiplier):
            data, _ = pe.compile_pieces(items, 1, multiplier)
            links_at, n_link = struct.unpack_from("<II", data, 52)
            return [struct.unpack_from("<II", data, links_at + 8 * k)[1] for k in range(n_link)]
        plain = links(None)
        self.assertEqual(len(plain), 1)
        self.assertEqual(links({"party": pe.THEME_FAVOUR}), [plain[0] * pe.THEME_FAVOUR])
        self.assertEqual(links({"x": pe.THEME_FAVOUR}), plain, "an approach's own multiplier is not its answers'")

    def test_ages_a_villager_can_have_load_and_impossible_ones_are_reported(self):
        # Codex P2 (#774): a role's ages outside 0..120 once made the engine refuse the whole file.  90+ is kept as
        # written; 130+ (nobody) and 50 to 30 are written within the bounds and reported; every piece stays.
        def slot_ages(text):
            items = pe.parse_text(text, "p.txt")
            self.assertFalse([str(p) for i in items for p in i.problems])
            data, probs = pe.compile_pieces(items, 1)
            slots_at = struct.unpack_from("<I", data, 44)[0]
            return struct.unpack_from("<BB", data, slots_at + 6), [p for p in probs if p.kind != "note"], \
                [p.text for p in probs if p.kind == "note"], struct.unpack_from("<I", data, 20)[0]
        base = "Piece: old\nKind: Flavour\nRole e: {}\nText: (E) remembers.\n\n" \
               "Piece: kid\nKind: Flavour\nRole k: child\nText: (K) plays.\n"
        ages, bad, notes, count = slot_ages(base.format("90+"))
        self.assertEqual((ages, bad, notes, count), ((90, 0), [], [], 2))
        for words in ("130+", "50 to 30"):
            with self.subTest(words=words):
                ages, bad, notes, count = slot_ages(base.format(words))
                self.assertEqual(bad, [])
                self.assertTrue(all(a <= pe.AGE_LIMIT for a in ages) and (ages[1] == 0 or ages[1] >= ages[0]))
                self.assertTrue(any("can ever be cast" in n for n in notes), notes)
                self.assertEqual(count, 2, "both pieces kept")

    def test_tag_bits_are_ored_so_a_minor_keeps_its_block(self):
        # A child's piece is tagged minor (and never romance) by finish_piece; "Tags: minor, minor" and both
        # words for one bit ("lesser") once added the bit twice and carried it into the next one.
        text = ("Piece: kid\nKind: Flavour\nRole k: child\nTags: minor, minor, lesser, "
                "portraying anyone as lesser\nText: (K) builds a sandcastle.\n")
        items = pe.parse_text(text, "p.txt")
        self.assertFalse([str(p) for i in items for p in i.problems])
        data, _ = pe.compile_pieces(items, 1)
        pieces_at = struct.unpack_from("<I", data, 24)[0]
        never, tags = struct.unpack_from("<II", data, pieces_at + 24)
        bits = pe.BLOCK_TAGS
        low = (1 << 5) - 1
        self.assertEqual(tags & low, (1 << bits["minor"]) | (1 << bits["lesser"]), "minor and lesser, each once")
        self.assertTrue(never & (1 << bits["romance"]), "a minor's piece never meets romance")

    def test_duplicate_of_the_villager_is_the_pieces_main_slot(self):
        text = ("Piece: x\nKind: Approach\nFamily: f\nLabel: Wave\nRole a: villager\nText: (A) waves at a boat.\n\n"
                "Piece: twin\nKind: Outcome\nFamily: f\nAnswers: x\nLabel: Meet a Double\nRole a: villager\n"
                "Text: (A) meets someone who looks the same.\nEffect: DUPLICATE OF villager\n")
        items = pe.parse_text(text, "p.txt")
        self.assertFalse([str(p) for i in items for p in i.problems])
        data, probs = pe.compile_pieces(items, 1)
        self.assertFalse([str(p) for p in probs], "not kept as flavor: its villager is the piece's main slot")
        effects_at, n_fx = struct.unpack_from("<II", data, 36)
        code, role, *_ = struct.unpack_from("<BBBBiiII", data, effects_at)
        self.assertEqual((n_fx, code), (1, cie.EFFECT_CODES["new_villager"]))
        twin = next(i for i in items if i.piece["id"] == "twin").piece
        self.assertEqual(role, list(twin["slots"]).index("subject"), "copy_of the piece's main slot")

    def test_exported_new_villagers_keep_their_sex_and_parents(self):
        for e in ({"do": "new_villager", "age": "adult", "sex": "female"},
                  {"do": "new_villager", "age": "child", "child_of_newest": True},
                  {"do": "new_villager", "sex": "male"},
                  {"do": "new_villager", "age": "teen", "sex": "male", "child_of_newest": True}):
            with self.subTest(effect=e):
                back = pe.plain_effect(pe._plain_of(e))
                self.assertNotIsInstance(back, str, back)
                self.assertEqual({k: v for k, v in back.effects[0].items() if v is not None}, e)


class ExportRoundTrip(unittest.TestCase):
    """The library's "export as mixer pieces" (pieces_file_text): every effect kind the pieces file holds, with every
    target and field the plain words can say, comes back as the same piece effect in every game; an effect the words
    cannot hold exactly is kept as flavor and the file says so -- never written as something else (Codex, #774)."""

    EXACT = [
        {"do": "food", "size": "normal", "scaled": True}, {"do": "food", "size": "small", "loss": True, "scaled": True},
        {"do": "food", "size": "large", "defer": True, "scaled": True}, {"do": "food", "amount": 200, "max": 800,
                                                                         "scaled": True},
        {"do": "food", "amount": 500, "scaled": True}, {"do": "food", "amount": -300, "max": -100, "scaled": True},
        {"do": "tech", "size": "huge", "scaled": True}, {"do": "tech", "amount": 50, "max": 90, "scaled": True},
        {"do": "skill", "role": "subject", "skills": ["Healing"], "size": "small"},
        {"do": "skill", "role": "friend", "skills": ["Farming"], "size": "large", "loss": True},
        {"do": "skill", "role": "subject", "skills": ["Building"], "set": 100},
        {"do": "skill", "role": "friend", "best": True, "size": "normal"},
        {"do": "preference", "role": "subject", "like": "dancing"},
        {"do": "preference", "role": "friend", "dislike": "rocks", "remove": True},
        {"do": "preference", "role": "subject", "like": "random"},
        {"do": "health", "role": "friend", "value": 100},
        {"do": "health_change", "role": "subject", "min": -40, "max": -20},
        {"do": "sick", "role": "friend"}, {"do": "kill", "role": "lost", "cause": "a fall"},
        {"do": "vanish", "role": "gone"}, {"do": "die_unrecovered", "role": "away"},
        {"do": "old_look", "role": "subject"}, {"do": "young_look", "role": "friend"}, {"do": "cure", "role": "friend"},
        {"do": "sex_change", "role": "friend"}, {"do": "lose_name", "role": "friend"},
        {"do": "change_name", "role": "subject"}, {"do": "change_name", "role": "friend", "name": "Kai"},
        {"do": "clone", "role": "subject"}, {"do": "clone", "role": "friend", "count": 2},
        {"do": "body_swap", "role": "subject", "with": "friend"},
        {"do": "change_age", "role": "friend", "to": "elder"},
        {"do": "change_age", "role": "subject", "years": [3, 5]},
        {"do": "change_age", "role": "friend", "years": [-10, -2], "max_age": 60},
        {"do": "mood", "role": "subject", "mood": "good"}, {"do": "mood", "role": "friend", "mood": "bad"},
        {"do": "celebrate", "who": "all"}, {"do": "celebrate", "who": "friend"},
        {"do": "damage", "size": "normal", "structures": "any"}, {"do": "repair", "structures": "any"},
        {"do": "presentation", "role": "friend", "on": True}, {"do": "presentation", "role": "subject", "on": False},
        {"do": "appearance", "role": "friend", "head": "random"},
        {"do": "appearance", "role": "subject", "head": "random", "body": "random"},
        {"do": "new_villager", "age": "adult", "sex": "female"},
        {"do": "new_villager", "age": "child", "child_of_newest": True},
        {"do": "new_villager", "copy_of": "friend", "age": "child"},
        {"do": "mood", "target": {"all": True}, "mood": "good"},
        {"do": "skill", "target": {"skill": "Healing"}, "skills": ["Healing"], "size": "normal"},
        {"do": "sick", "target": {"random": 3}},
    ]
    FLAVOR = [
        {"do": "skill", "role": "subject", "skills": ["Healing"], "min": 3, "max": 7},       # no size word for 3-7
        {"do": "food", "amount": 200, "max": 800, "scaled": False},                       # unscaled: no words for it
    ]

    def graph(self, effects):
        return {"format": "vvfp-cie-graph", "version": 6, "title": "Round Trip", "games": [1, 2, 3, 4, 5],
                "roles": {"subject": {"kind": "villager", "min_age": 18},
                          "friend": {"kind": "villager", "min_age": 18, "protected": "allow"},
                          **{k: {"kind": "villager", "min_age": 18, "protected": "allow"} for k in ("lost", "gone", "away")}},
                "start": "ask",
                "nodes": {"ask": {"type": "question",
                                  "text": "(subject) meets (friend), (lost), (gone) and (away) at the shore.",
                                  "choices": [{"label": "Talk", "next": "out"}, {"label": "Leave", "next": "out"}]},
                          "out": {"type": "popup", "text": "Something changes.\n\nIt stays changed.", "effects": effects,
                                  "children": []}}}

    def test_every_effect_round_trips_or_the_export_is_refused(self):
        for e in self.FLAVOR:
            with self.subTest(effect=e), self.assertRaises(ValueError) as refused:
                pe.pieces_file_text(self.graph(copy.deepcopy(self.EXACT + [e])))
            self.assertIn("no exact plain words", str(refused.exception))
        g = self.graph(copy.deepcopy(self.EXACT))
        norm, _ = cie.normalize(copy.deepcopy(g), pe._shared_pools())
        want = [pe._piece_signature(e if e.get("role") or "target" in e or e["do"] in (
            "food", "tech", "pay_award", "damage", "repair", "celebrate", "new_villager") else dict(e, role="subject"))
                for e in norm["nodes"]["out"]["effects"]]
        text = pe.pieces_file_text(g)
        items = pe.parse_text(text, "export.txt")
        self.assertFalse([str(p) for i in items for p in i.problems])
        outcomes = [i for i in items if i.piece["kind"] == pe.PIECE_KINDS["outcome"]]
        self.assertNotIn("# kept as flavor", text)
        outcome = outcomes[0]
        got = [pe._piece_signature(e) for _ln, e in outcome.piece["effects"]]
        self.assertEqual(got, want[:len(self.EXACT)], "every exact effect, in its order, the same piece effect")
        for game in range(1, 6):
            with self.subTest(game=game):
                data, probs = pe.compile_pieces(items, game)
                self.assertFalse([str(p) for p in probs if p.kind != "note"])
                self.assertEqual(struct.unpack_from("<I", data, 40)[0], len(self.EXACT) * len(outcomes),
                                 "every effect written")

    @staticmethod
    def event_records(g: dict, game: int) -> list[tuple]:
        """The ordinary event compiler's effect records for `g` (vv_cie_graph.compile_graph), each as names and values:
        (code, role, flags, selector, a, b, string, extra) with role indexes as role names, strings as their text and
        a food / tech effect's own range for `game` (its per-game string read)."""
        packed: list[tuple] = []
        real = cie._EFFECT

        class Spy:
            size = real.size

            def pack(self, *v):
                packed.append(v)
                return real.pack(*v)
        cie._EFFECT = Spy()
        try:
            blob = cie.compile_graph(cie.load(copy.deepcopy(g), scrolling=True))
        finally:
            cie._EFFECT = real
        u16 = lambda at: struct.unpack_from("<H", blob, at)[0]  # noqa: E731
        u32 = lambda at: struct.unpack_from("<I", blob, at)[0]  # noqa: E731
        n_role, n_string, o_role, o_string = u16(26), u16(38), u32(44), u32(72)

        def s(i):
            if i == 0xFFFF:
                return ""
            at = o_string + 4 * n_string + u32(o_string + 4 * i)
            return blob[at:blob.index(b"\0", at)].decode()
        names = [s(u16(o_role + 16 * i + 4)) for i in range(n_role)]
        out = []
        for code, role, flags, sel, a, b, st, last in packed:
            text = s(st)
            if code in (cie.EFFECT_CODES["food"], cie.EFFECT_CODES["tech"]) and text:
                a, b = cie.per_game_parse(text).get(game, cie.per_game_parse(text).get(str(game), (a, b)))
                text = ""
            if code in (cie.EFFECT_CODES[k] for k in ("pregnant", "nursing", "body_swap")) and a < n_role:
                a = names[a]
            out.append((code, names[role] if role < n_role else role, flags, sel, a, b or a, text,
                        s(last) if sel == cie.TARGET_SKILL else last))
        return out

    @staticmethod
    def piece_records(data: bytes, piece_index: int) -> list[tuple]:
        """The same tuple for every effect of piece `piece_index` in a VPCB v2 file (slot indexes as slot names)."""
        pieces_at, strings_at = struct.unpack_from("<II", data, 24)
        effects_at, slots_at = struct.unpack_from("<I", data, 36)[0], struct.unpack_from("<I", data, 44)[0]

        def s(off):
            if off == 0xFFFFFFFF:
                return ""
            at = strings_at + off
            return data[at:data.index(b"\0", at)].decode()
        rec = pieces_at + 64 * piece_index
        first_slot, n_slot = struct.unpack_from("<I", data, rec + 40)[0], struct.unpack_from("<H", data, rec + 44)[0]
        first_fx, n_fx = struct.unpack_from("<I", data, rec + 48)[0], struct.unpack_from("<H", data, rec + 52)[0]
        names = [s(struct.unpack_from("<I", data, slots_at + 16 * (first_slot + k))[0]) for k in range(n_slot)]
        out = []
        for k in range(n_fx):
            code, role, flags, sel, a, b, st, extra = struct.unpack_from("<BBBBiiII", data, effects_at + 20 * (first_fx + k))
            if code in (cie.EFFECT_CODES[x] for x in ("pregnant", "nursing", "body_swap")) and a < n_slot:
                a = names[a]
            out.append((code, names[role] if role < n_slot else role, flags, sel, a, b or a, s(st),
                        s(extra) if sel == cie.TARGET_SKILL else extra))
        return out

    def test_the_pieces_hold_what_the_event_compiler_writes(self):
        # Exported, imported and compiled as pieces, every exact effect is the ordinary compiler's own record for the
        # same event, field by field, in every game (the encoder and the exporter checked at once).
        g = self.graph(copy.deepcopy(self.EXACT))
        items = pe.parse_text(pe.pieces_file_text(g), "export.txt")
        self.assertFalse([str(p) for i in items for p in i.problems])
        pieces = [i for i in items if not i.problems]
        first_outcome = next(k for k, i in enumerate(pieces) if i.piece["kind"] == pe.PIECE_KINDS["outcome"])
        for game in range(1, 6):
            with self.subTest(game=game):
                data, _ = pe.compile_pieces(items, game)
                want = self.event_records(g, game)
                got = self.piece_records(data, first_outcome)
                self.assertEqual(len(got), len(self.EXACT))
                for e, w, h in zip(self.EXACT, want, got):
                    self.assertEqual(h, w, e)

    MULTI = {"format": "vvfp-cie-graph", "version": 6, "title": "Many Ways", "games": [1, 2, 3, 4, 5],
             "roles": {"subject": {"kind": "villager", "min_age": 18},
                       "friend": {"kind": "villager", "min_age": 18},
                       "lost": {"kind": "villager", "min_age": 18, "protected": "allow"},
                       "visitor": {"kind": "stranger", "sex": "random", "named": True}},
             "start": "ask",
             "nodes": {
                 "ask": {"type": "question", "text": "(subject) and (friend) meet (visitor.name) and (lost).",
                         "choices": [{"label": "Trade", "next": "p1"}, {"label": "Gamble", "next": "br"},
                                     {"label": "Rest", "next": "p5"}]},
                 "p1": {"type": "popup", "text": "(visitor.name) trades.",
                        "effects": [{"do": "food", "amount": 100, "scaled": True}],
                        "children": [{"next": "p2"}]},
                 "p2": {"type": "popup", "text": "The trade goes on.",
                        "effects": [{"do": "tech", "amount": 200, "scaled": True}], "children": [{"next": "p2b"}]},
                 "p2b": {"type": "popup", "text": "It ends.", "effects": [{"do": "mood", "role": "friend",
                                                                            "mood": "good"}]},
                 "br": {"type": "branch", "children": [{"next": "p3", "weight": 3}, {"next": "br2", "weight": 1}]},
                 "br2": {"type": "branch", "children": [{"next": "p4", "weight": 1}, {"next": "p7", "weight": 2}]},
                 "p7": {"type": "popup", "text": "Luck wavers.", "effects": [{"do": "mood", "role": "friend",
                                                                                "mood": "bad"}]},
                 "p3": {"type": "popup", "text": "Luck holds.", "effects": [{"do": "mood", "role": "subject",
                                                                              "mood": "good"}]},
                 "p4": {"type": "popup", "text": "Luck fails.", "effects": [{"do": "kill", "role": "lost",
                                                                              "cause": "a fall"}]},
                 "p5": {"type": "popup", "text": "(friend) rests.\n\nThe day is quiet.",
                        "effects": [{"do": "sick", "role": "friend"},
                                    {"do": "food", "size": "small", "scaled": True},
                                    {"do": "celebrate", "who": "friend"}]}}}

    @staticmethod
    def graph_paths(nodes, start):
        """Every path from a page to an end, written here independently of the exporter."""
        out = []

        def walk(path):
            n = nodes[path[-1]]
            nxt = [ch["next"] for ch in n.get("choices", [])] if n["type"] == "question" else \
                [ch["next"] for ch in n.get("children", [])]
            nxt = [x for x in nxt if x not in path]
            if not nxt:
                out.append(path)
            for x in nxt:
                walk(path + [x])
        walk([start])
        return out

    def test_a_role_name_with_digits_survives_the_export(self):
        # "Role helper2:" must parse back as the helper2 slot (Codex, #774), not be lost as an unknown line.
        g = json.loads(json.dumps(self.MULTI).replace('"friend"', '"helper2"').replace("(friend)", "(helper2)"))
        items = pe.parse_text(pe.pieces_file_text(g), "export.txt")
        self.assertFalse([str(p) for i in items for p in i.problems])
        setup = next(i for i in items if i.piece["kind"] == pe.PIECE_KINDS["setup"])
        self.assertIn("helper2", setup.piece["slots"])

    def test_every_path_keeps_every_effect_or_says_it_is_flavor(self):
        # For every path through the event, the effects along it (kind, target, every field) are the effects of the
        # matching exported outcome, or are kept as flavor and listed in the file -- never dropped silently.
        g = copy.deepcopy(self.MULTI)
        norm, _ = cie.normalize(copy.deepcopy(g), pe._shared_pools())
        nodes = norm["nodes"]
        text = pe.pieces_file_text(g)
        items = pe.parse_text(text, "export.txt")
        self.assertFalse([str(p) for i in items for p in i.problems])
        self.assertTrue(all("visitor" in i.piece["slots"] for i in items), "the named stranger is a slot")
        self.assertEqual(next(i for i in items if i.piece["kind"] == pe.PIECE_KINDS["setup"])
                         .piece["slots"]["visitor"][0]["kind"], "stranger")

        def sig(e):
            e = dict(e)
            if e.get("role") is None and "target" not in e and e["do"] not in (
                    "food", "tech", "pay_award", "damage", "repair", "celebrate", "new_villager"):
                e["role"] = "subject"
            return pe._piece_signature(e)
        outcomes = [i for i in items if i.piece["kind"] == pe.PIECE_KINDS["outcome"]]
        got = sorted(sorted(sig(e) for _ln, e in o.piece["effects"]) for o in outcomes)
        want, flavored = [], 0
        for c in nodes["ask"]["choices"]:
            for path in self.graph_paths(nodes, c["next"]):
                effects = [e for nid in path for e in nodes[nid].get("effects", [])]
                kept = [e for e in effects if pe._plain_of(e)]
                flavored += len(effects) - len(kept)
                want.append(sorted(sig(e) for e in kept))
        self.assertEqual(got, sorted(want))
        self.assertEqual(len(outcomes), 5, "Trade (one path of three pages), Gamble (3), Rest (1)")
        self.assertEqual(flavored, 0)
        self.assertNotIn("# kept as flavor", text)
        rest = next(o for o in outcomes if o.piece["links"][0][0].endswith("_a3")).piece
        approach = next(i for i in items if i.piece["id"].endswith("_a3")).piece
        self.assertEqual((approach["text"], rest["text"]), ("(friend) rests.", "The day is quiet."),
                         "a one-page answer's text split between its approach and outcome, never shown twice")
        trade = next(o for o in outcomes if o.piece["links"][0][0].endswith("_a1"))
        self.assertEqual([e["do"] for _ln, e in trade.piece["effects"]], ["food", "tech", "mood"],
                         "the answer's own first page's food, then the later pages' effects")

    def test_what_pieces_cannot_carry_is_refused_by_name(self):
        # The export carries an event exactly or refuses it, naming the feature (Codex, #774): the event itself is
        # never changed, and a player's own files keep the owner's "kept as flavor" rule.
        cases = []
        pooled = copy.deepcopy(self.MULTI)
        pooled["pools"] = {"gift": {"items": ["a shell", "a feather"]}}
        pooled["nodes"]["p1"]["text"] = "(visitor.name) trades {gift}."
        cases.append((pooled, "uses a text pool or pick ({gift})"))
        second = copy.deepcopy(self.MULTI)
        second["nodes"]["p5"] = {"type": "question", "text": "(friend) asks around.",
                                 "choices": [{"label": "Rest", "next": "p3"}, {"label": "Push On", "next": "p7"}]}
        cases.append((second, "is a second question"))
        flat = copy.deepcopy(self.MULTI)
        flat["nodes"]["p5"]["text"] = "(friend) rests."
        cases.append((flat, "has one page of one paragraph"))
        # Every part of the requirement, not only its condition (Codex, #774): a puzzle that must be solved first
        # has no piece form, so the export refuses, naming it.
        puzzled = copy.deepcopy(self.MULTI)
        puzzled.setdefault("requirement", {})["puzzles"] = {"1": ["The Cave"]}
        cases.append((puzzled, "a puzzle that must be solved first"))
        # An opening page before the first question, with its own text and food (Codex, #774): refused, named.
        opened = copy.deepcopy(self.MULTI)
        opened["nodes"]["intro"] = {"type": "popup", "text": "(visitor.name) arrives.",
                                    "effects": [{"do": "food", "amount": 100, "scaled": True}],
                                    "children": [{"next": "ask"}]}
        opened["start"] = "intro"
        cases.append((opened, "opens with page intro before its first question"))
        for g, words in cases:
            with self.subTest(words=words), self.assertRaises(ValueError) as refused:
                pe.pieces_file_text(g)
            self.assertIn(words, str(refused.exception))
            self.assertIn("The event itself is unchanged", str(refused.exception))

    def test_every_outcomes_overall_chance_survives(self):
        # Nested random branches: each final outcome's overall chance (the product of its shares at every fork),
        # computed here on its own, is its Answers weight's share among the approach's outcomes.
        from fractions import Fraction
        g = copy.deepcopy(self.MULTI)
        nodes = cie.normalize(copy.deepcopy(g), pe._shared_pools())[0]["nodes"]
        items = pe.parse_text(pe.pieces_file_text(g), "export.txt")
        gamble = [i for i in items if i.piece["kind"] == pe.PIECE_KINDS["outcome"]
                  and i.piece["links"][0][0].endswith("_a2")]

        def chances(nid, share):
            kids = nodes[nid].get("children") or []
            if not kids:
                return {nid: share}
            total = sum(k.get("weight", 1) for k in kids)
            out = {}
            for k in kids:
                out.update(chances(k["next"], share * Fraction(k.get("weight", 1), total)))
            return out
        want = chances("br", Fraction(1))
        self.assertEqual(want, {"p3": Fraction(3, 4), "p4": Fraction(1, 12), "p7": Fraction(2, 12)})
        total = sum(i.piece["links"][0][1] for i in gamble)
        got = {}
        for i in gamble:
            end = next(nid for nid in want if nodes[nid]["text"] in i.piece["text"])
            got[end] = Fraction(i.piece["links"][0][1], total)
        self.assertEqual(got, want)

    def test_every_roles_requirements_survive(self):
        g = {"format": "vvfp-cie-graph", "version": 6, "title": "Roles", "games": [3],
             "roles": {"subject": {"kind": "villager", "sex": "male", "min_age": 20, "max_age": 40},
                       "chief": {"kind": "villager", "special": "tribal_chief", "protected": "allow"},
                       "healer": {"kind": "villager", "min_age": 18, "optional": True,
                                  "skill": {"names": ["Healing"], "min": 30, "pick": "highest"}},
                       "wife": {"kind": "villager", "sex": "female", "min_age": 18,
                                "relation": {"spouse_of": "subject"}},
                       "visitor": {"kind": "stranger", "sex": "female", "named": True}},
             "start": "ask",
             "nodes": {"ask": {"type": "question",
                               "text": "(subject), (wife), (healer) and (chief) meet (visitor.name).",
                               "choices": [{"label": "Greet", "next": "a"}, {"label": "Wait", "next": "a"}]},
                       "a": {"type": "popup", "text": "They talk.\n\nThey part."}}}
        roles = cie.normalize(copy.deepcopy(g), pe._shared_pools())[0]["roles"]
        text = pe.pieces_file_text(g)
        self.assertNotIn("# role", text, "every requirement held")
        for it in pe.parse_text(text, "export.txt"):
            for rid, r in roles.items():
                slot = it.piece["slots"][rid][0]
                with self.subTest(piece=it.piece["id"], role=rid):
                    for key, value in r.items():
                        if key == "sex" and value in ("any", "random") and slot.get(key) in (None, "any", "random"):
                            continue
                        if (key, value) in (("optional", False), ("protected", "auto")) and slot.get(key) is None:
                            continue                     # the defaults, which the words leave unwritten
                        self.assertEqual(slot.get(key), value, key)
        self.assertIn("tribal chief", text)

    def test_each_kind_alone(self):
        for e in self.EXACT:
            with self.subTest(effect=e):
                norm, _ = cie.normalize(self.graph([copy.deepcopy(e)]), pe._shared_pools())
                self.assertTrue(pe._plain_of(norm["nodes"]["out"]["effects"][0]), "plain words that read back the same")
        for e in self.FLAVOR:
            with self.subTest(effect=e):
                norm, _ = cie.normalize(self.graph([copy.deepcopy(e)]), pe._shared_pools())
                self.assertEqual(pe._plain_of(norm["nodes"]["out"]["effects"][0]), "", "kept as flavor")


class InstallAndRules(unittest.TestCase):
    def test_an_id_and_a_later_number_never_share_a_file(self):
        # Codex P2 (#774): in foo.txt the first event's Id pl_foo_002 is the second event's own number; both once
        # compiled as pl_foo_002, the second .cieg over the first, and the report said both were installed.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            first = SIMPLE.replace("Applies to: VV1, VV3\n", "Applies to: VV1, VV3\nId: pl_foo_002\n")
            second = SIMPLE.replace("The Coconut That Would Not Open", "The Second Coconut")
            third = SIMPLE.replace("The Coconut That Would Not Open", "The Third Coconut").replace(
                "Applies to: VV1, VV3\n", "Applies to: VV1, VV3\nId: pl_foo_002\n")
            (folder / "foo.txt").write_text(first + "\n" + second + "\n" + third, encoding="utf-8")
            out, report = pe.compile_folder(1, folder, pe.Settings())
        self.assertEqual(pe.group_name("foo", set())[0], "pl_foo")
        ciegs = sorted(n for n in out if n.endswith(".cieg"))
        self.assertEqual(len(ciegs), 3, ciegs)
        self.assertEqual(len(report.installed), 3)
        rows = [line.split("\t")[0] for line in out["manifest-pl_foo.txt"].decode().splitlines()
                if not line.startswith("#")]
        self.assertEqual(sorted(f"{r}.cieg" for r in rows), ciegs, "each row its own file")
        self.assertIn("pl_foo_002.cieg", ciegs)
        self.assertEqual(sum("already used" in n for n in report.notes), 2, report.notes)

    def test_install_writes_only_its_own_files_and_reports_bad_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Player Events"
            src = pe.ensure_game_folder(1, root)
            (src / "My Events.txt").write_text(SIMPLE + "\n" + SIMPLE.replace(
                "The Coconut That Would Not Open", "A Broken One").replace("Choice 2: Leave (Him/Her) to It\n", "")
                .replace("* Outcome A: (Name) invents a splitting wedge.\n  Effect: SKILL + Building a little\n", ""),
                encoding="utf-8")
            (src / "pieces.txt").write_text(doc_block("Piece: reef_setup"), encoding="utf-8")
            game = Path(tmp) / "Game"
            coll = game / pe.PATCHER_FILES / pe.COLLECTION_FOLDER
            coll.mkdir(parents=True)
            (coll / "manifest-v28.txt").write_text("# built in\nall_x\tX\t1\t1\t\t\t\t\t\n", encoding="utf-8")
            (coll / "all_x.cieg").write_bytes(b"CIEG")
            (coll / "pl_stale_001.cieg").write_bytes(b"old")
            (coll / "manifest-pl_old.txt").write_text("# an earlier patch's\n", encoding="utf-8")
            report = pe.install(1, game, src, pe.Settings(), root)
            names = sorted(p.name for p in coll.iterdir())
            mine = pe.group_name("My Events", set())[0]
            self.assertTrue(mine.startswith("pl_my") and len(mine) == 9, mine)
            self.assertEqual(pe.group_name("My Events", set())[0], mine)          # the same every patch
            self.assertIn(f"manifest-{mine}.txt", names)
            self.assertIn("pieces-pl_pieces.pcb", names)
            self.assertEqual(names.count("manifest-v28.txt"), 1)                   # the collection's own, untouched
            self.assertEqual((coll / "manifest-v28.txt").read_text(encoding="utf-8")[:10], "# built in")
            self.assertFalse([n for n in names if "collection" in n])              # nothing copied any more
            self.assertIn("all_x.cieg", names)
            self.assertNotIn("pl_stale_001.cieg", names)
            self.assertNotIn("manifest-pl_old.txt", names)
            self.assertTrue(all(len(n) <= 22 for n in names if n.startswith(("manifest-", "pieces-"))), names)
            self.assertEqual(len(report.installed), 1)
            self.assertTrue(any("A Broken One" in s or "line" in s for s in report.skipped))
            rows = [r for r in (coll / f"manifest-{mine}.txt").read_text(encoding="utf-8").splitlines()
                    if not r.startswith("#")]
            ident, title, games, weight = rows[0].split("\t")[:4]
            self.assertTrue((coll / f"{ident}.cieg").is_file())
            self.assertLessEqual(len(ident), pe.VV1_ID_MAX)
            self.assertEqual((title, games, weight), ("The Coconut That Would Not Open", "1,3", "1"))
            shown = game / pe.PATCHER_FILES / pe.INSTALLED_FOLDER
            self.assertTrue((shown / pe.PROMPT_NAME).is_file())
            self.assertTrue((shown / pe.TONE_NAME).is_file())
            for name in pe.OWNER_FILES:
                self.assertEqual((shown / name).read_bytes(), (pe.OWNER_DOCS / name).read_bytes(), name)
            self.assertFalse([p for p in coll.iterdir() if "example" in p.name.lower()])
            # Favoured themes weigh three times; Only my themes leaves the others out; ticked rules are enforced.
            pe.install(1, game, src, pe.Settings(favour=["comedy"]), root)
            row = [r for r in (coll / f"manifest-{mine}.txt").read_text(encoding="utf-8").splitlines()
                   if not r.startswith("#")][0]
            self.assertEqual(row.split("\t")[3], "3")
            r2 = pe.install(1, game, src, pe.Settings(favour=["sea"], only_my_themes=True), root)
            self.assertEqual(r2.installed, [])
            r3 = pe.install(1, game, src, pe.Settings(rules={"no_losses": False, "no_lasting_changes": True}), root)
            self.assertEqual(len(r3.installed), 1)
            death = SIMPLE.replace("Effect: INJURY helper (minor)", "Effect: DEATH helper")
            (src / "My Events.txt").write_text(death, encoding="utf-8")
            r4 = pe.install(1, game, src, pe.Settings(rules={"no_deaths": True}), root)
            self.assertEqual(r4.installed, [])
            self.assertTrue(any("No deaths" in s for s in r4.skipped))

    def test_long_file_names_get_short_groups_and_collisions_are_reported(self):
        taken: set[str] = set()
        a, note_a = pe.group_name("Stories of the Sea", taken)
        self.assertEqual((len(a), note_a), (pe.GROUP_NAME_MAX, ""))
        self.assertEqual(pe.group_name("short", set()), ("pl_short", ""))
        b, note_b = pe.group_name("Stories of the Sea", taken)        # a second file that meets the first
        self.assertNotEqual(a, b)
        self.assertEqual(len(b), pe.GROUP_NAME_MAX)
        self.assertIn("already taken", note_b)
        self.assertLessEqual(len(f"manifest-{b}.txt"), 22)

    def test_settings_and_rules_files_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            s = pe.Settings(count=4, favour=["sea"], only_my_themes=True, rules={"no_deaths": True})
            pe.save_settings(2, s, root)
            self.assertEqual(pe.load_settings(2, root).to_json(), s.to_json())
            pe.write_rules(2, "Themes: sea, storms\nNo sharks.", root)
            self.assertEqual(pe.rules_themes(pe.read_rules(2, root)), ["sea", "storms"])


class OwnerLayout(unittest.TestCase):
    """The owner's own layout (S001. Title [VV..] / WHO / EVENT TEXT / CHOICE / First popup / Ending / MIXER SEED),
    read from the shipped example file (reference only: it is never installed)."""

    @classmethod
    def setUpClass(cls):
        cls.items, cls.file_problems = pe.parse_file(pe.PLAYER_FOLDER / pe.EXAMPLE_NAME)

    def test_the_example_file_reads_as_events_and_pieces(self):
        events = [i for i in self.items if i.kind == "event"]
        pieces = [i for i in self.items if i.kind == "piece"]
        self.assertEqual(len(events), 20)
        self.assertEqual(events[0].title, "The Spring That Talks Back")
        self.assertGreater(len(pieces), 200)
        done, total = pe.owner_coverage(self.items)
        self.assertGreaterEqual(done / total, 0.99, (done, total))

    def test_s001_compiles_with_its_popups_chances_and_effects(self):
        it = next(i for i in self.items if i.code == "S001")
        self.assertEqual(it.problems, [])
        c, probs = pe.compile_item(it, "pl_s001_001")
        self.assertIsNotNone(c, probs)
        g = c.graph
        lead = g["nodes"]["c1"]
        self.assertTrue(lead["text"].startswith("(Name) clears"))
        self.assertEqual([ch["weight"] for ch in lead["children"]], [50, 50])
        end = g["nodes"]["c1o1"]
        self.assertEqual(end["popup"], "new")                         # an ending is its own popup
        kinds = [(e["do"], e.get("skills"), e.get("like")) for e in end["effects"]]
        self.assertIn(("skill", ["Farming"], None), kinds)
        self.assertEqual(end["effects"][0]["min"], 20)
        b2 = [e for e in g["nodes"]["c2o2"]["effects"] if e["do"] == "preference"][0]
        self.assertTrue(b2.get("remove"))

    def test_the_seed_becomes_pieces(self):
        s1 = [i for i in self.items if i.kind == "piece" and i.piece["id"].startswith("s001_")]
        kinds = [i.piece["kind"] for i in s1]
        self.assertEqual(kinds.count(1), 1)
        self.assertEqual(kinds.count(2), 4)
        self.assertGreaterEqual(kinds.count(3), 7)
        self.assertGreaterEqual(kinds.count(4), 4)
        outcome = next(i for i in s1 if i.piece["kind"] == 3)
        self.assertTrue(outcome.piece["links"])
        self.assertIn("(Seeker)", outcome.piece["text"])
        data, probs = pe.compile_pieces([i for i in s1 if not i.problems], 1)
        self.assertTrue(data.startswith(b"VPCB"), probs)

    def test_the_phrase_table(self):
        import vv_owner_layout as owner
        cases = {
            "tech gain (small amount)": "tech", "food loss (normal)": "food",
            "gains 20 to 30 Farming; now likes farming": "skill",
            "skill + research (some, +10) for (young name)": "skill", "(name2) Building becomes MASTER (100)": "skill",
            "(name) gains 10 to 20 in (his/her) best skill": "skill", "every healer gains 10 healing": "skill",
            "injured (loses health)": "health_change", "permanent disability (health loss 30%)": "health_change",
            "(name)'s illness is cured": "cure", "all sick villagers are cured (stock island-event effect)": "cure",
            "three random villagers have an illness (need the healers)": "sick", "(name1) DIES (a grave)": "kill",
            "disappears (no grave)": "vanish", "NEW VILLAGER (an elder) arrives and stays": "new_villager",
            "NEW VILLAGERS (two adults) arrive and stay, with their baby": "new_villager",
            "DUPLICATE of (name), named (new name)": "new_villager", "CLONE of (name) (2), named (new name)": "clone",
            "body swap between (name) and (name2) (permanent)": "body_swap",
            "loses name (name becomes \"?\")": "lose_name", "changes name: (name)'s first name becomes Lani":
                "change_name", "changes age (20 years older; never past elder)": "change_age",
            "changes age (to 16, teen)": "change_age", "\"old\" head look": "old_look",
            "new look (the young head look)": "young_look", "new look for (name) (new clothes)": "appearance",
            "every villager is happier (stock island-event effect)": "mood",
            "the damaged huts are repaired (stock island-event effect)": "repair",
            "(any birth sex) (name) is pregnant with one baby, with (name2) as the other parent (magic)": "pregnant",
            "pregnant, with (name2) as the other parent (twins or triplets, if the game allows twins)": "pregnant",
            "(any birth sex) (name) becomes nursing the abandoned baby (single parent)": "nursing",
        }
        for phrase, do in cases.items():
            with self.subTest(phrase=phrase):
                effects, _roles, _notes = owner.owner_effects(phrase, [1, 2, 3, 4, 5])
                self.assertIn(do, [e["do"] for e in effects])
        effects, _r, _n = owner.owner_effects("changes age (20 years older; never past elder)", [1])
        self.assertEqual(effects[0]["max_age"], 75)
        effects, _r, _n = owner.owner_effects("CLONE of (name) (2), named (new name)", [1])
        self.assertEqual(effects[0]["count"], 2)
        for nothing in ("none", "joins the village", "body swap, then swapped back (no lasting change)"):
            self.assertEqual(owner.owner_effects(nothing, [1])[0], [])
        with self.assertRaises(owner.Unmapped):
            owner.owner_effects("each now likes the other's favourite job", [1])

    def test_crafts_count_as_their_main_skill(self):
        # Style guide 8b-8c (the owner, 2026-11-18), in the importer's plain words and the owner's own layout (the GO
        # files): a craft is its main skill, two skills are one of them at random, doubt and doodles are flavor.
        import vv_owner_layout as owner
        want = {
            "cooking": ["Farming"], "fishing": ["Farming"], "gathering": ["Farming"], "hunting": ["Farming"],
            "trapping": ["Farming"], "carving": ["Building"], "sculpture": ["Building"], "weaving": ["Building"],
            "pottery": ["Building"], "canoe-making": ["Building"], "jewelry": ["Building"],
            "craftmaking": ["Building"], "weaponsmithing": ["Building"], "bow-making": ["Building"],
            "archery": ["Farming", "Building"], "stargazing": ["Research"], "scroll-keeping": ["Research"],
            "writing": ["Research"], "alchemy": ["Research"], "mapping": ["Research"],
            "potions": ["Research", "Healing"], "potion": ["Research", "Healing"], "stews": ["Research", "Healing"],
            "remedies": ["Research", "Healing"], "poultices": ["Research", "Healing"], "salves": ["Research", "Healing"],
            "tonics": ["Research", "Healing"], "magic": ["Healing", "Devotion"], "spells": ["Healing", "Devotion"],
            "charms": ["Healing", "Devotion"], "blessings": ["Healing", "Devotion"], "sigil": ["Healing", "Devotion"],
            "herbalism": ["Healing"], "bonesetting": ["Healing"], "midwifery": ["Healing"],
            "teaching": ["Parenting"], "storytelling": ["Parenting"], "omens": ["Research", "Devotion"],
            "prayer": ["Devotion"], "ritual": ["Devotion"], "devotion": ["Devotion"], "healing": ["Healing"],
            "doubt": [], "doodle": [], "doodles": [],
        }
        for word, skills in want.items():
            with self.subTest(word=word):
                got = pe.plain_effect(f"SKILL + {word.title()} some")
                self.assertNotIsInstance(got, str, got)
                self.assertEqual([e.get("skills") for e in got.effects], [skills] if skills else [])
                if not skills:
                    self.assertIn("flavor only", got.note)
                effects, _r, _n = owner.owner_effects(f"gains 10 to 20 {word}", [1, 2, 3, 4, 5])
                self.assertEqual([e.get("skills") for e in effects], [skills] if skills else [])
        got = pe.plain_effect("MASTER Canoe-making FOR builder1")
        self.assertEqual(got.effects, [{"do": "skill", "role": "builder1", "skills": ["Building"], "set": 100}])
        got = pe.plain_effect("EVERYONE: SKILL + Potions a little")
        self.assertEqual(got.effects[0]["skills"], ["Research", "Healing"])
        self.assertEqual(owner.owner_effects("skill + weaving (some)", [4])[0][0]["skills"], ["Building"])
        with self.assertRaises(owner.Unmapped):
            owner.owner_effects("gains 10 juggling", [1])
        compiled(SIMPLE.replace("Effect: SKILL + Building a little", "Effect: SKILL + Magic a little"))

    def test_the_engine_forms_of_5ee2b3dc0(self):
        import vv_owner_layout as owner
        self.assertEqual(owner.normalize_text("(new name) and (New Name 2) smile; (name2.he/she) waves"),
                         "(made1) and (Made2) smile; (friend.he/she) waves")
        effects, _r, _n = owner.owner_effects("NEW LOOK for three random villagers (star-stone jewellery)", [1])
        self.assertEqual(effects[0], {"do": "appearance", "body": "random", "target": {"random": 3}})
        c = compiled(SIMPLE.replace("(Name) invents a splitting wedge.",
                                    "A double of (name) appears; (made1) says the wedge is (his/hers) now.").replace(
            "Effect: SKILL + Building a little", "Effect: DUPLICATE OF villager"))
        self.assertIn(b"(made1)", c.cieg)
        bad = one(SIMPLE.replace("Choice 1: Lend a Hand", "Choice 1: Lend (Made1) a Hand"))
        _c, probs = pe.compile_item(bad, "pl_t_001")
        self.assertTrue(probs)

    def test_an_unmapped_phrase_is_a_line_numbered_problem(self):
        text = (pe.PLAYER_FOLDER / pe.EXAMPLE_NAME).read_text(encoding="utf-8")
        start = text.index("S001.")
        end = text.index("MIXER SEED S001")
        block = text[start:end].replace("EFFECT: now dislikes swimming", "EFFECT: turns into a parrot", 1)
        it = one(block)
        self.assertTrue(any("phrase table" in p.text and "parrot" in p.text and p.line > 1 for p in it.problems))


class StyleWarnings(unittest.TestCase):
    def test_first_and_second_person_outside_quotes_warn(self):
        it = one(SIMPLE.replace("(Name) invents a splitting wedge.", "You invent a splitting wedge."))
        self.assertTrue(any("outside quoted speech" in w.text for w in it.warnings))
        quoted = one(SIMPLE.replace("(Name) invents a splitting wedge.", "\"You did it!\" says (name). Your villagers gain food."))
        self.assertFalse([w for w in quoted.warnings if "outside quoted speech" in w.text])
        self.assertIsNone(pe.person_problem("I said \"we\" in quotes. Your villagers gain 5 food."[2:]))

    def test_likes_that_do_nothing_warn(self):
        it = one(SIMPLE.replace("Effect: SKILL + Building a little", "Effect: LIKE + ants"))
        self.assertTrue(any("does nothing in VV1" in w.text for w in it.warnings))
        self.assertFalse(it.problems)

    def test_count_tokens_are_checked_and_shown(self):
        c = compiled(SIMPLE.replace("(Name) invents a splitting wedge.",
                                    "(Name) is expecting {#babies:a baby|twins|triplets}.").replace(
            "Effect: SKILL + Building a little", "Effect: PREGNANT (TWINS OR TRIPLETS)"))
        self.assertIn("{#babies:a baby|twins|triplets}", c.graph["nodes"]["c2o1"]["text"])
        self.assertIn(b"{#babies:", c.cieg)
        bad = one(SIMPLE.replace("Lend a Hand", "Lend a Hand"), )
        it = one(SIMPLE.replace("(Name) invents a splitting wedge.", "{#babies:a. baby}"))
        _c, probs = pe.compile_item(it, "pl_t_001")
        self.assertTrue(any("count" in p for p in probs))
        self.assertIsNotNone(bad)


class Preview(unittest.TestCase):
    def test_preview_shows_the_popups(self):
        text = pe.preview(one(SIMPLE), 1, seed=1)
        self.assertIn("[Popup 1]", text)
        self.assertIn("coconut", text)
        self.assertIn("Chosen:", text)


class LibraryExport(unittest.TestCase):
    def test_an_editor_event_saves_as_a_player_event_and_as_pieces(self):
        g = json.loads((ROOT / "data" / "cie_graphs" / "the_aspiring_adventurer.json").read_text(encoding="utf-8"))
        norm, _ = cie.normalize(g)
        text = pe.event_file_text(norm)
        it = one(text)
        self.assertFalse(it.problems, [str(p) for p in it.problems])
        want, probs = cie.validate(norm)
        got, probs2 = cie.validate({k: v for k, v in it.graph.items()})
        self.assertEqual(probs, probs2)
        self.assertEqual(cie.compile_graph(got), cie.compile_graph(want))
        # Its variants and its roles' protections have no piece form: the export refuses, naming them (the event
        # itself is unchanged), never writes something else.
        with self.assertRaises(ValueError) as refused:
            pe.pieces_file_text(norm)
        self.assertIn("text variants", str(refused.exception))
        self.assertIn("unchanged", str(refused.exception))


class BuiltInEventsRoundTrip(unittest.TestCase):
    """The owner: "a player file can do anything the built-in events do". 50 built-in collection events across every
    source, written as FULL player events and read back, compile to the same bytes as the collection's own build."""

    def test_fifty_built_in_events_compile_identically(self):
        from collection_check import graph_for_engine
        events = []
        for p in sorted((ROOT / "data" / "event_collection").rglob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("format") == "vvfp-cie-graph" and isinstance(d.get("collection"), dict):
                events.append((p, d))
        by_source: dict[str, list] = {}
        for p, d in events:
            by_source.setdefault(d["collection"].get("source", "v28"), []).append((p, d))
        sample = []
        while len(sample) < 50 and any(by_source.values()):
            for src in sorted(by_source):
                if by_source[src] and len(sample) < 50:
                    lst = by_source[src]
                    sample.append(lst.pop(len(lst) // 2 if len(sample) % 2 else 0))
        self.assertEqual(len(sample), 50)
        self.assertGreaterEqual(len({d["collection"].get("source", "v28") for _p, d in sample}), 5)
        for p, d in sample:
            with self.subTest(event=p.name):
                src = d["collection"].get("source", "v28")
                gi = graph_for_engine(d)
                norm, probs = cie.validate(gi, scrolling=True, shared_pools=cie.SHARED_POOLS)
                self.assertEqual(probs, [])
                ident = d["collection"]["id"]
                tags = content.node_tags_for(src, ident, norm)
                extras = content.extras_for(src, ident, norm)
                want = cie.compile_graph(content.inject(norm, tags, extras)[0])
                meta = {"node_filters": tags, "speaks": extras["speaks"], "traits": extras["traits"],
                        "auto_filters": False, "auto_speakers": False,
                        "description": d["collection"].get("description", "")}
                items = pe.parse_text(pe.full_text(gi, meta), p.name)
                self.assertEqual(len(items), 1)
                self.assertEqual([str(x) for x in items[0].problems], [])
                c, cprobs = pe.compile_item(items[0], keep_collection=True)
                self.assertIsNotNone(c, cprobs)
                self.assertEqual(c.cieg, want)


if __name__ == "__main__":
    unittest.main()
