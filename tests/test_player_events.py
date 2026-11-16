"""Player Events (src/vv_player_events.py, docs/player-events-format.md): the plain-text format, its checks, the
compile into the collection's own files, the AI prompt, and the round trip of the built-in events.

Run alone: python -m pytest -p no:xdist tests/test_player_events.py"""
from __future__ import annotations

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
    }

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
        self.assertEqual((magic, version, head, size), (b"VPCB", 1, 64, len(data)))
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


class InstallAndRules(unittest.TestCase):
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
        pieces = pe.parse_text(pe.pieces_file_text(norm), "p.txt")
        self.assertTrue(any(p.piece["kind"] == 1 for p in pieces))
        self.assertTrue(any(p.piece["kind"] == 2 for p in pieces))


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
