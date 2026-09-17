"""The Village Population roster must agree with the layouts it borrows.

The owner asked for "a log of all the villagers in the village" with name, head
and body, parents where present, likes and dislikes, and skill values -- titled
"Village Population", 256 villagers per file.

Every offset this exporter uses is already established and shipped elsewhere:
the villager array RVA, record base, stride, slot count, active flag and skill
table come from the statistics companion's Village Elders row, and the name,
head and body come from the parentage companion's layout table. So these guards
do not re-derive them. They check that the two copies AGREE, which is the
failure this arrangement actually invites -- a later change to one companion
silently leaving the other reading a stale offset, which does not crash and
does not look wrong, it just logs 150 wrong numbers.
"""

from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POPULATION = ROOT / "native/population_export/population_export.c"
PARENTAGE = ROOT / "native/parentage_export/parentage_export.c"
STATISTICS = ROOT / "native/statistics_export/statistics_export.c"
STOCK = ROOT / "research/stock-executables"

EXES = {
    3: "Virtual Villagers - The Secret City.exe",
    4: "Virtual Villagers - The Tree of Life.exe",
    5: "Virtual Villagers - New Believers.exe",
}


def _population_rows() -> dict[int, dict[str, int]]:
    """Each supported game's row, read from the exporter's own table."""
    source = POPULATION.read_text(encoding="utf-8")
    table = source[source.index("GAME_LAYOUTS[6] = {"):]
    table = re.sub(r"/\*.*?\*/", "", table, flags=re.DOTALL)
    rows: dict[int, dict[str, int]] = {}
    for match in re.finditer(
        r'\{\s*1,\s*((?:0x[0-9A-Fa-f]+u?|\d+u?|,|\s)+?)"Virtual Villagers (\d)"',
        table,
        re.DOTALL,
    ):
        values = [
            int(v.rstrip("u"), 0)
            for v in re.findall(r"0x[0-9A-Fa-f]+u?|\b\d+u?\b", match.group(1))
        ]
        names = [
            "villagers_rva", "record_base", "stride", "slots",
            "active", "age", "head", "body",
            "name", "name_capacity",
            "father_name", "father_name_capacity",
            "father_head", "father_body",
            "skills", "skill_count", "skills_are_float",
        ]
        rows[int(match.group(2))] = dict(zip(names, values))
    return rows


class VillagePopulationLayoutsAgreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = _population_rows()

    def test_exactly_three_games_are_supported(self) -> None:
        """VV1 and VV2 are absent on purpose, not by oversight.

        Their villager arrays are not reachable from any existing hook, so a
        row for either would need an array address that is not established.
        """
        self.assertEqual(sorted(self.rows), [3, 4, 5])

    def test_every_offset_matches_the_parentage_layout(self) -> None:
        """Name, head, body and the father copies are shared with parentage."""
        parentage = PARENTAGE.read_text(encoding="utf-8")
        table = parentage[parentage.index("GAME_LAYOUTS[6] = {"):]
        blocks = dict(
            (int(num), re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL))
            for body, num in re.findall(
                r"\{([^{}]*?)L\"Virtual Villagers (\d) Parentage Log\"",
                table,
                re.DOTALL,
            )
        )
        for game, row in self.rows.items():
            with self.subTest(game=game):
                values = [
                    int(v, 0)
                    for v in re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", blocks[game])
                ]
                # supported, stride, slots, record_base, active, age, head,
                # body, id, name, name_capacity, father, ...
                self.assertEqual(row["stride"], values[1], "stride")
                self.assertEqual(row["slots"], values[2], "slots")
                self.assertEqual(row["record_base"], values[3], "record base")
                self.assertEqual(row["active"], values[4], "active flag")
                self.assertEqual(row["age"], values[5], "age")
                self.assertEqual(row["head"], values[6], "head")
                self.assertEqual(row["body"], values[7], "body")
                self.assertEqual(row["name"], values[9], "name")
                self.assertEqual(row["name_capacity"], values[10], "name cap")

    def test_every_array_and_skill_offset_matches_the_statistics_row(self) -> None:
        """The array RVA and skill table are shared with Village Elders.

        Both companions read the same array. If one is ever corrected and the
        other is not, the roster reads a stale base and logs 150 wrong
        villagers -- silently, because nothing crashes and the output still
        looks like a roster.
        """
        statistics = STATISTICS.read_text(encoding="utf-8")
        stripped = re.sub(r"/\*.*?\*/", "", statistics, flags=re.DOTALL)
        literals = {
            int(value, 16)
            for value in re.findall(r"0[xX]([0-9A-Fa-f]+)[uU]?", stripped)
        }
        for game, row in self.rows.items():
            with self.subTest(game=game):
                self.assertIn(
                    row["villagers_rva"],
                    literals,
                    "the villager array RVA %#x does not appear in the "
                    "statistics companion" % row["villagers_rva"],
                )
                self.assertIn(
                    row["skills"],
                    literals,
                    "the skill offset %#x does not appear in the statistics "
                    "companion" % row["skills"],
                )
                self.assertIn(
                    row["active"],
                    literals,
                    "the active-flag offset %#x does not appear in the "
                    "statistics companion" % row["active"],
                )

    def test_the_array_fits_inside_every_image(self) -> None:
        """A base that ran past the image would walk arbitrary memory."""
        for game, row in self.rows.items():
            exe = STOCK / EXES[game]
            if not exe.is_file():
                self.skipTest("%s is not available" % EXES[game])
            blob = exe.read_bytes()
            with self.subTest(game=game):
                pe = struct.unpack_from("<I", blob, 0x3C)[0]
                size_of_image = struct.unpack_from("<I", blob, pe + 24 + 56)[0]
                last = (
                    row["villagers_rva"]
                    + row["record_base"]
                    + (row["slots"] - 1) * row["stride"]
                )
                highest = max(
                    row["active"],
                    row["name"] + row["name_capacity"],
                    row["skills"] + row["skill_count"] * 4,
                )
                self.assertLessEqual(
                    last + highest,
                    size_of_image,
                    "the last record's highest field falls outside the image",
                )

    def test_the_array_lives_in_a_writable_data_section(self) -> None:
        """A villager array in .text or .rdata would be the wrong address."""
        for game, row in self.rows.items():
            exe = STOCK / EXES[game]
            if not exe.is_file():
                self.skipTest("%s is not available" % EXES[game])
            blob = exe.read_bytes()
            with self.subTest(game=game):
                pe = struct.unpack_from("<I", blob, 0x3C)[0]
                count = struct.unpack_from("<H", blob, pe + 6)[0]
                opt = struct.unpack_from("<H", blob, pe + 20)[0]
                rva = row["villagers_rva"]
                for index in range(count):
                    off = pe + 24 + opt + index * 40
                    vsize, vaddr, rsize, _ = struct.unpack_from(
                        "<IIII", blob, off + 8)
                    chars = struct.unpack_from("<I", blob, off + 36)[0]
                    if vaddr <= rva < vaddr + max(vsize, rsize):
                        self.assertTrue(
                            chars & 0x80000000,
                            "the villager array is in a read-only section",
                        )
                        break
                else:
                    self.fail("the array RVA is not inside any section")

    def test_vv5_alone_has_six_skills(self) -> None:
        """Carrying VV3's five across would drop a whole column."""
        self.assertEqual(self.rows[3]["skill_count"], 5)
        self.assertEqual(self.rows[4]["skill_count"], 5)
        self.assertEqual(self.rows[5]["skill_count"], 6)

    def test_vv3_alone_stores_skills_as_integers(self) -> None:
        """Reading int32 skills through the float path yields nonsense.

        VV3's own predicate compares against 0x58, which is 88 as an integer;
        the other two compare against 88.0f. Taking the wrong branch reinterprets
        the bits rather than converting them.
        """
        self.assertEqual(self.rows[3]["skills_are_float"], 0)
        self.assertEqual(self.rows[4]["skills_are_float"], 1)
        self.assertEqual(self.rows[5]["skills_are_float"], 1)


class VillagePopulationBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = POPULATION.read_text(encoding="utf-8")

    def test_the_roster_is_truncated_not_appended(self) -> None:
        """A snapshot supersedes; appending would describe several moments."""
        self.assertIn('_wfopen(path, L"w")', self.source)
        self.assertNotIn('_wfopen(path, L"a")', self.source)

    def test_the_file_rolls_at_the_requested_count(self) -> None:
        """The owner asked for "text files hold 256 villagers each"."""
        self.assertIn("VILLAGERS_PER_FILE = 256", self.source)

    def test_an_absent_father_is_detected_by_name_not_appearance(self) -> None:
        """0 is a valid head and a valid body, so it cannot mean "absent".

        Testing head or body against zero would discard a father genuinely at
        row 0 of the spritesheet, which is a real villager the owner has said
        exists.
        """
        self.assertIn("record[g->father_name] != '\\0'", self.source)
        self.assertNotIn("father_head] != 0", self.source)
        self.assertNotIn("father_body] != 0", self.source)

    def test_only_live_slots_are_written(self) -> None:
        """An empty slot holds stale data that reads as a plausible villager."""
        self.assertIn("(record + g->active) != 1", self.source)

    def test_the_layout_guard_rejects_a_half_declared_father_block(self) -> None:
        """Half a block prints a name beside somebody else's appearance."""
        self.assertIn("g->father_name == 0u || g->father_head == 0u",
                      self.source)


if __name__ == "__main__":
    unittest.main()
