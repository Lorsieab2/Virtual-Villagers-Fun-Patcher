"""The conception record carries both parents' likes and dislikes, all five games.

The owner's requirement, stated for every Virtual Villagers game: when a
conception happens, record the mother and the father -- each one's name, age
at conception, head, body, LIKES and DISLIKES -- and how many babies were
conceived.  Likes and dislikes are identity: two villagers can share a name,
and these are what tell them apart.

What these guards protect:

  * the record prints Likes and Dislikes under the Mother block AND under the
    Father block, between Body and the next block, in every game;
  * each game's preference offsets, slot count and word list in the parentage
    exporter are the ones the population exporter measured (a second source,
    so a typo in either table fails here rather than printing the wrong word);
  * the three word lists are byte-identical between the two exporters, so the
    Details screen, the population log and the parentage log name the same
    thing for the same index -- one reality;
  * the runtime harness pins the same geometry it feeds the DLL;
  * the SHIPPED DLL carries the new rows, because a source change whose DLL
    was not rebuilt changes nothing a player receives.

The behaviour itself -- that a real villager's likes come out as the right
word for the right parent, that an empty array prints (none), that the father's
are honestly absent when no record was captured (never a namesake's) -- is
exercised by native/parentage_export/parentage_export_harness.c, which loads
the built DLL and reads back the log it writes.
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native/parentage_export/parentage_export.c"
POPULATION = ROOT / "native/population_export/population_export.c"
HARNESS = ROOT / "native/parentage_export/parentage_export_harness.c"
COMPANION = ROOT / "assets/parentage/VVFP Parentage Export.dll"
MANIFESTS = {n: ROOT / f"data/vv{n}_parentage_feature.json" for n in range(1, 6)}


def _strip_comments(source: str) -> str:
    return re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)


def _lists(source: str) -> dict[str, str]:
    """PREFERENCES_47/62/79 as the joined string literal each declares."""
    found = {}
    for match in re.finditer(
        r"static const char (PREFERENCES_\d+)\[\] =\s*((?:\"[^\"]*\"\s*)+);", source
    ):
        found[match.group(1)] = "".join(re.findall(r'"([^"]*)"', match.group(2)))
    return found


def _parentage_rows() -> dict[int, tuple[int, int, int, str]]:
    """(likes, dislikes, slots, list) per game from the parentage exporter's
    layout table: the four preference values in each row.

    The child's skills sit between the preference list and the log name and are
    skipped here. This helper exists to compare the PREFERENCE geometry against
    the population exporter's; the skills have their own cross-table test.
    """
    table = _strip_comments(EXPORTER.read_text(encoding="utf-8"))
    table = table[table.index("GAME_LAYOUTS[6] = {") :]
    rows = re.findall(
        r"(0x[0-9A-Fa-f]+|\d+),\s*(0x[0-9A-Fa-f]+|\d+),\s*(\d+),\s*(PREFERENCES_\d+),\s*"
        r"(?:0x[0-9A-Fa-f]+|\d+),\s*\d+,\s*[01],\s*SKILL_NAMES_VV\d,\s*"
        r'L"Virtual Villagers (\d) Births and Conceptions Log"',
        table,
    )
    return {int(g): (int(a, 0), int(b, 0), int(c), d) for a, b, c, d, g in rows}


def _population_rows() -> dict[int, tuple[int, int, int, str]]:
    """The same four values from the population exporter's rows, which end
    `likes, dislikes, slots, PREFERENCES_x, "Virtual Villagers N"`."""
    table = _strip_comments(POPULATION.read_text(encoding="utf-8"))
    table = table[table.index("GAME_LAYOUTS[6] = {") :]
    rows = re.findall(
        r"(0x[0-9A-Fa-f]+)u,\s*(0x[0-9A-Fa-f]+)u,\s*(\d+)u,\s*(PREFERENCES_\d+),\s*"
        r'"Virtual Villagers (\d)"',
        table,
    )
    return {int(g): (int(a, 0), int(b, 0), int(c), d) for a, b, c, d, g in rows}


def _harness_rows() -> dict[int, tuple[int, int, int]]:
    """(likes, dislikes, slots) per game from the harness's LAYOUTS table."""
    source = _strip_comments(HARNESS.read_text(encoding="utf-8"))
    rows = {}
    for match in re.finditer(r"\{\s*([1-5])\s*,([^}]*)\}", source):
        fields = [f.strip() for f in match.group(2).split(",")]
        # stride, slots, base, active, age, head, body, name, name_cap,
        # father_name, father_key_cap, father_head_copy, father_body_copy,
        # litter, likes, dislikes, pref_slots, ...
        rows[int(match.group(1))] = (
            int(fields[14], 0),
            int(fields[15], 0),
            int(fields[16], 0),
        )
    return rows


class ConceptionRecordPrintsLikesAndDislikesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = EXPORTER.read_text(encoding="utf-8")

    def test_both_parents_get_likes_and_dislikes_between_body_and_the_next_block(self):
        self.assertRegex(
            self.source,
            r'"  Mother: %s\\n"\s*"    Age at conception: %d\\n"\s*"    Head: %d\\n"\s*'
            r'"    Body: %d\\n"\s*"    Likes: %s\\n"\s*"    Dislikes: %s\\n"\s*"  Father: %s\\n"',
            "the mother's likes and dislikes must follow her body, before the Father block",
        )
        self.assertRegex(
            self.source,
            r'"  Father: %s\\n"\s*"    Age at conception: %s\\n"\s*"    Head: %s\\n"\s*'
            r'"    Body: %s\\n"\s*"    Likes: %s\\n"\s*"    Dislikes: %s\\n"\s*'
            r'"  Babies in pregnancy: %d\\n"',
            "the father's likes and dislikes must follow his body, before the baby count",
        )

    def test_the_arguments_are_the_right_parents_words_in_the_right_order(self):
        self.assertIn(
            "*(const int *)(mother + g->body),\n        mother_likes,\n        mother_dislikes,\n        father_name,",
            self.source.replace("\r\n", "\n"),
        )
        self.assertIn(
            "father_body,\n        father_likes,\n        father_dislikes,\n        babies\n",
            self.source.replace("\r\n", "\n"),
        )

    def test_the_mothers_words_are_read_from_her_record_and_the_fathers_from_his(self):
        self.assertIn("preference_text(g, mother, g->likes, mother_likes", self.source)
        self.assertIn("preference_text(g, mother, g->dislikes, mother_dislikes", self.source)
        self.assertIn("preference_text(g, father_from_caller, g->likes, father_likes", self.source)
        self.assertIn("preference_text(g, father_from_caller, g->dislikes, father_dislikes", self.source)
        # ...and never from the by-name scan's result
        self.assertNotIn("preference_text(g, father,", self.source)

    def test_a_missing_father_record_says_what_his_age_says_and_never_scans(self):
        """No captured record, no guess: the same wording his age carries."""
        self.assertIn("memcpy(father_likes, father_age, sizeof father_age);", self.source)
        self.assertIn("memcpy(father_dislikes, father_age, sizeof father_age);", self.source)
        self.assertNotIn("find_record_by_name(g, records, father_likes", self.source)

    def test_an_empty_array_prints_none_rather_than_a_blank_line(self):
        self.assertIn('memcpy(out, "(none)", 7);', self.source)

    def test_the_first_filled_slot_is_what_is_printed(self):
        """Empty is -1 OR past the end of the list; the panel shows the first
        filled slot, and so must the log."""
        body = self.source[self.source.index("static int first_preference(") :]
        body = body[: body.index("\n}\n") + 3]
        self.assertIn("if (value < 0) {\n            continue;", body.replace("\r\n", "\n"))
        self.assertIn("if (preference_name(list, value, out, out_size)) {\n            return 1;", body.replace("\r\n", "\n"))

    def test_every_preference_slot_is_bounds_checked_against_the_stride(self):
        self.assertIn("if (g->likes + g->preference_slots * WORD > stride) return 0;", self.source)
        self.assertIn("if (g->dislikes + g->preference_slots * WORD > stride) return 0;", self.source)


class OffsetsAgreeWithThePopulationExporterTests(unittest.TestCase):
    def test_all_five_games_have_preference_rows_in_both_exporters(self):
        self.assertEqual(sorted(_parentage_rows()), [1, 2, 3, 4, 5])
        self.assertEqual(sorted(_population_rows()), [1, 2, 3, 4, 5])

    def test_each_games_offsets_slots_and_list_are_the_measured_ones(self):
        parentage = _parentage_rows()
        population = _population_rows()
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertEqual(parentage[game], population[game])

    def test_the_word_lists_are_identical_between_the_two_exporters(self):
        """Same index, same word, in the Details screen, the population log and
        the parentage log."""
        parentage = _lists(EXPORTER.read_text(encoding="utf-8"))
        population = _lists(POPULATION.read_text(encoding="utf-8"))
        self.assertEqual(sorted(parentage), ["PREFERENCES_47", "PREFERENCES_62", "PREFERENCES_79"])
        self.assertEqual(parentage, population)
        for name, words in parentage.items():
            self.assertEqual(len(words.split(",")), int(name.rsplit("_", 1)[1]), name)
        self.assertEqual(parentage["PREFERENCES_47"].split(",")[0], "ants", "zero-based: index 0 is ants")

    def test_the_harness_feeds_the_dll_the_same_geometry(self):
        harness = _harness_rows()
        parentage = _parentage_rows()
        self.assertEqual(sorted(harness), [1, 2, 3, 4, 5])
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertEqual(harness[game], parentage[game][:3])

    def test_the_harness_checks_every_required_field_for_every_litter_size(self):
        source = HARNESS.read_text(encoding="utf-8")
        for needle in (
            "mother's name", "mother's age at conception", "mother's head", "mother's body",
            "mother's likes", "mother's dislikes",
            "father's name", "father's age at conception", "father's head", "father's body",
            "father's dislikes", "Likes: (none)",
            "Babies in pregnancy: 1", "Babies in pregnancy: 2", "Babies in pregnancy: 3",
            "Likes: (not captured for this birth)",
        ):
            self.assertIn(needle, source, needle)


class TheShippedDllAndManifestsCarryItTests(unittest.TestCase):
    def test_the_shipped_dll_prints_likes_and_dislikes_for_both_parents(self):
        if not COMPANION.is_file():
            self.skipTest("the parentage companion DLL is not present")
        blob = COMPANION.read_bytes()
        self.assertIn(
            b"    Body: %d\n    Likes: %s\n    Dislikes: %s\n  Father: %s\n", blob,
            "the shipped DLL must print the mother's likes and dislikes -- rebuild it if not",
        )
        self.assertIn(
            b"    Body: %s\n    Likes: %s\n    Dislikes: %s\n  Babies in pregnancy: %d\n", blob,
            "the shipped DLL must print the father's likes and dislikes -- rebuild it if not",
        )
        for head in (b"ants,crowds,resting,laundry,medicine,turnips,",):
            self.assertIn(head, blob, "the preference lists must be in the shipped DLL")
        self.assertEqual(blob.count(b"stars,mango,nature"), 1, "the 79-entry list")
        self.assertEqual(blob.count(b"clouds,dirt\x00"), 1, "the 62-entry list ends at dirt")
        self.assertEqual(blob.count(b"surprises,jokes\x00"), 1, "the 47-entry list ends at jokes")
        self.assertIn(b"(none)", blob)

    def test_every_games_description_promises_likes_and_dislikes(self):
        for game, path in MANIFESTS.items():
            with self.subTest(game=game):
                text = path.read_text(encoding="utf-8")
                self.assertIn("both parents' likes and dislikes", text)
                # ...and it pins the very DLL that prints them (the pin sits
                # at the top level in some manifests and on the companion row
                # in others, so look for the hash anywhere)
                if COMPANION.is_file():
                    digest = hashlib.sha256(COMPANION.read_bytes()).hexdigest().lower()
                    self.assertIn(digest, text.lower(), "the manifest must pin the rebuilt export DLL")


class SkillTablesAgreeWithThePopulationExporterTests(unittest.TestCase):
    """The two companions must name a villager's skills identically.

    The parentage exporter prints a child's skills on a birth record and the
    population exporter prints every villager's on the roster and the history.
    They read the same offsets out of the same record, so a table that drifted
    in one would have the same villager holding "Farming 40" in one log and
    "Parenting 40" in another -- wrong in a way that looks entirely plausible,
    since both are real skills and the number is right.

    The orders were measured per game from the owner's own villagers and are
    NOT interchangeable: VV1 and VV2 differ from VV3-VV5, and VV5 alone has a
    sixth skill. Restating them in a second file is what makes this test
    necessary rather than optional.
    """

    def _tables(self, path: Path) -> dict[str, list[str]]:
        text = path.read_text(encoding="utf-8")
        out = {}
        for game, body in re.findall(
            r"SKILL_NAMES_(VV\d)\[MAX_SKILLS\] = \{(.*?)\};", text, re.S
        ):
            out[game] = re.findall(r'"([^"]+)"', body)
        return out

    def test_the_skill_tables_match_the_population_exporter(self):
        parentage = self._tables(EXPORTER)
        population = self._tables(POPULATION)
        self.assertEqual(sorted(parentage), ["VV1", "VV2", "VV3", "VV4", "VV5"])
        for game in ("VV1", "VV2", "VV3", "VV4", "VV5"):
            with self.subTest(game=game):
                self.assertEqual(parentage[game], population[game])

    def test_every_row_declares_its_skills(self):
        """A row that named no table would silently print no Skills block."""
        table = _strip_comments(EXPORTER.read_text(encoding="utf-8"))
        table = table[table.index("GAME_LAYOUTS[6] = {"):]
        rows = re.findall(
            r"(0x[0-9A-Fa-f]+|\d+),\s*(\d+),\s*([01]),\s*SKILL_NAMES_(VV\d),\s*"
            r'L"Virtual Villagers (\d) Births and Conceptions Log"',
            table,
        )
        self.assertEqual([g for *_, g in rows], ["1", "2", "3", "4", "5"])
        for offset, count, is_float, named, game in rows:
            with self.subTest(game=game):
                # The table a row names must be its own game's.
                self.assertEqual(named, "VV%s" % game)
                self.assertGreater(int(offset, 0), 0)
                # Pinned per game, not merely "5 or 6": VV5 alone has a sixth
                # skill (Devotion), and a VV5 row that quietly dropped to five
                # would omit it from every birth record while every other
                # assertion here still passed.
                self.assertEqual(int(count), 6 if game == "5" else 5)
                # VV4 and VV5 store floats; VV1-VV3 store i32. Reading one as
                # the other yields a plausible number, not a visible failure.
                self.assertEqual(is_float, "1" if game in ("4", "5") else "0")


if __name__ == "__main__":
    unittest.main()
