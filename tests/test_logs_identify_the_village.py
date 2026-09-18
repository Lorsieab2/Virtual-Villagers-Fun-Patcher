"""Every exported log opens by naming the village it describes.

The owner keeps several villages per game, so a log that opens with only the
game's title cannot be matched to the village it came from. They asked for the
tribe name and the savegame number -- "do both" -- across the parentage log,
Village Population and Village Statistics.

These guards are about the things that would silently produce a log with no
header, or with the wrong village, while every other check stayed green:

  * the per-game name offsets, which were measured rather than derived, and
    which sit inside each game's own save buffer;
  * the +8 bias, which is applied in exactly one place so that no caller can
    disagree about whether it has already been applied;
  * the stdcall decoration on the population export, which encodes the argument
    byte count -- adding an argument without updating it breaks the export
    silently, and the roster simply stops being written;
  * the handoff to the parentage log, which runs at conception and has no save
    context of its own.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "native" / "shared"
IDENTITY_C = SHARED / "village_identity.c"
IDENTITY_H = SHARED / "village_identity.h"
STATISTICS_C = ROOT / "native" / "statistics_export" / "statistics_export.c"
POPULATION_C = ROOT / "native" / "population_export" / "population_export.c"
POPULATION_DEF = ROOT / "native" / "population_export" / "population_export.def"
PARENTAGE_C = ROOT / "native" / "parentage_export" / "parentage_export.c"

# Measured across 348 real save files spanning both of the owner's save folders,
# every slot and multiple villages per game, and separately confirmed by the
# owner against what the games display.
EXPECTED_OFFSETS = {
    1: 0x00008,
    2: 0x00008,
    3: 0x12ECC,
    4: 0x170B8,
    5: 0x17D14,
}

# What each game pushes as its save buffer length at its own save call site.
# Every name offset has to lie inside its game's buffer, or the read would leave
# the block the game is about to write.
BUFFER_LENGTHS = {
    1: 0x0ABDC,
    2: 0x30370,
    3: 0x12F1C,
    4: 0x1710C,
    5: 0x17D78,
}


class VillageNameOffsetTests(unittest.TestCase):
    def offsets(self):
        """The offset table as the C file actually declares it."""
        source = IDENTITY_C.read_text(encoding="utf-8")
        match = re.search(
            r"static const unsigned int NAME_OFFSETS\[5\]\s*=\s*\{(.*?)\};",
            source,
            re.S,
        )
        self.assertIsNotNone(match, "the offset table is not declared as expected")
        found = re.findall(r"0x([0-9A-Fa-f]+)u", match.group(1))
        self.assertEqual(len(found), 5, "the table must carry one offset per game")
        return {index + 1: int(value, 16) for index, value in enumerate(found)}

    def test_each_game_uses_its_measured_offset(self) -> None:
        self.assertEqual(self.offsets(), EXPECTED_OFFSETS)

    def test_every_offset_lies_inside_that_games_save_buffer(self) -> None:
        """A name outside the buffer would be read from memory the save does
        not cover, which is how a plausible-looking offset produces garbage on
        someone else's village rather than on the machine it was measured on."""
        for game, offset in sorted(self.offsets().items()):
            with self.subTest(game=game):
                self.assertLess(
                    offset,
                    BUFFER_LENGTHS[game],
                    "VV%d's name offset is outside the buffer it pushes" % game,
                )

    def test_the_later_games_do_not_share_an_offset(self) -> None:
        """VV3, VV4 and VV5 keep the name near the end of their buffers, within
        0xC60 of each other. If two games were given the same offset, one of
        them would read the wrong field and the mistake would look like a
        working feature on the game it was measured against."""
        offsets = self.offsets()
        distinct = {offsets[game] for game in (3, 4, 5)}
        self.assertEqual(
            len(distinct), 3, "VV3, VV4 and VV5 must each have their own offset")


class SaveBufferBiasTests(unittest.TestCase):
    def test_the_bias_is_defined_once_and_is_eight(self) -> None:
        """The buffer begins at manager + 8 (`lea eax, [esi + 8]`) in all five
        games. Defining it once is what stops a caller applying it a second
        time, which is a mistake that reads eight bytes into the name and
        returns a truncated village that still looks like a name."""
        source = IDENTITY_C.read_text(encoding="utf-8")
        defines = re.findall(r"#define\s+SAVE_BUFFER_BIAS\s+(\d+)", source)
        self.assertEqual(defines, ["8"], "the bias must be defined exactly once, as 8")

    def test_the_reader_applies_the_bias_itself(self) -> None:
        source = IDENTITY_C.read_text(encoding="utf-8")
        self.assertIn(
            "SAVE_BUFFER_BIAS + offset",
            source,
            "the reader must apply the bias, so callers cannot disagree about it",
        )


class PopulationExportDecorationTests(unittest.TestCase):
    def test_the_decoration_matches_the_argument_bytes(self) -> None:
        """The .def pins the stdcall decoration, which encodes the argument
        byte count. The export takes an int and two pointers, so 12 bytes. A
        stale @8 here does not fail the build -- it fails to export, and the
        roster silently stops being written."""
        text = POPULATION_DEF.read_text(encoding="utf-8")
        self.assertIn(
            "_WriteVillagePopulation@12",
            text,
            "the population export takes 12 bytes of arguments",
        )
        self.assertNotIn(
            "_WriteVillagePopulation@8",
            text,
            "an @8 decoration is stale and would break the export",
        )

    def test_the_signature_has_three_parameters(self) -> None:
        """The parameter list is taken by matching parentheses from the opening
        one of the argument list. Searching for the next ")" instead finds the
        one closing __declspec(dllexport), which yields an empty body that no
        assertion can be made about -- a test that fails for its own reason
        rather than the product's."""
        source = POPULATION_C.read_text(encoding="utf-8")
        marker = "__stdcall WriteVillagePopulation("
        start = source.index(marker) + len(marker) - 1
        depth = 0
        for end in range(start, len(source)):
            if source[end] == "(":
                depth += 1
            elif source[end] == ")":
                depth -= 1
                if depth == 0:
                    break
        body = source[start:end]
        for expected in ("int game_id", "module_pointer", "village"):
            self.assertIn(expected, body, "missing %s" % expected)


class LogsCarryTheVillageTests(unittest.TestCase):
    def test_every_statistics_writer_prints_the_village(self) -> None:
        """All four writers -- VV1, VV2, the shared later-game writer and VV5 --
        must carry it, not just the one that happened to be checked."""
        source = STATISTICS_C.read_text(encoding="utf-8")
        self.assertEqual(
            source.count('"Village Statistics\\n"\n        "%s\\n"'),
            4,
            "each statistics writer must print the identifying line",
        )

    def test_the_roster_prints_it_on_both_of_its_files(self) -> None:
        """The roster rolls over into a second file once the village is large
        enough. A header on only the first file would leave the continuation
        unidentifiable, which is exactly the problem being fixed."""
        source = POPULATION_C.read_text(encoding="utf-8")
        self.assertEqual(
            source.count('"%s Village Population\\n%s\\n", g->title, village'),
            2,
            "both the first roster file and its roll-over must be identified",
        )

    def test_the_statistics_export_publishes_for_the_parentage_log(self) -> None:
        source = STATISTICS_C.read_text(encoding="utf-8")
        self.assertIn(
            "vv_village_publish(village)",
            source,
            "the save-time export must publish the village for the others",
        )

    def test_the_parentage_log_writes_its_header_only_on_a_new_file(self) -> None:
        """The parentage log is appended to across a village's whole history.
        Writing the header per record would interleave it between conceptions,
        so it is gated on the file being empty."""
        source = PARENTAGE_C.read_text(encoding="utf-8")
        self.assertIn("vv_village_recall(village, sizeof village)", source)
        recall = source.index("vv_village_recall(village")
        window = source[max(0, recall - 600):recall]
        self.assertIn(
            "ftell(file) == 0",
            window,
            "the header must be gated on the log file being new",
        )

    def test_the_gate_is_ftell_not_the_record_count(self) -> None:
        """existing_records counts every file in the run, so it is non-zero for
        a brand-new roll-over file -- which is precisely a file that still needs
        a header. Using it would leave every roll-over log unidentified."""
        source = PARENTAGE_C.read_text(encoding="utf-8")
        recall = source.index("vv_village_recall(village")
        window = source[max(0, recall - 600):recall]
        self.assertNotIn(
            "existing_records == 0",
            window,
            "the header gate must not depend on the run-wide record count",
        )


class HeaderAssemblyTests(unittest.TestCase):
    def test_it_degrades_rather_than_guessing(self) -> None:
        """A village that cannot be named still has a slot, and a log with no
        identity at all must print no header rather than an empty one."""
        source = IDENTITY_C.read_text(encoding="utf-8")
        self.assertIn('"Village: %s (Save %d)\\n"', source, "both halves")
        self.assertIn('"Village: %s\\n"', source, "name only")
        self.assertIn('"Save %d\\n"', source, "slot only")

    def test_the_shared_block_is_scoped_to_the_process(self) -> None:
        """A bare Local\\ name is per-logon-session. Two Virtual Villagers games
        running at once would map the same block, and the second to save would
        relabel the first one's parentage log with its own village."""
        source = IDENTITY_C.read_text(encoding="utf-8")
        self.assertIn(
            "GetCurrentProcessId()",
            source,
            "the shared block's name must be scoped to the process",
        )


if __name__ == "__main__":
    unittest.main()
