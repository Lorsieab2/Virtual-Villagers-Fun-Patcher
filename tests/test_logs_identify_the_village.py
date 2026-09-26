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

    def test_the_header_is_recalled_chosen_and_gated_in_that_order(self) -> None:
        """Three steps, and the ORDER between them is the whole invariant.

        The village must be recalled BEFORE the log file is chosen, because the
        choice depends on it -- a file belonging to another village has to be
        skipped rather than appended to, or its records are filed under the
        wrong village. The header must then be written only into a new file.

        Asserted as a sequence rather than by searching a fixed window around
        one of the calls. An earlier version of this guard looked 600
        characters back from the recall; when the recall correctly moved
        earlier in the function, the window stopped covering the gate and the
        test failed while the code was right. Position is not the property
        worth pinning here -- relative order is.
        """
        full = PARENTAGE_C.read_text(encoding="utf-8")
        # Both record kinds go through emit_record, which recalls the village
        # and hands it to append_record, which chooses the file and gates the
        # header. So the order is checked across that call: emit_record must
        # recall before it calls append_record, and the choice and the gate
        # must follow inside append_record.
        emit = full[full.index("static int emit_record("):]
        emit = emit[:emit.index("\n}")]
        append = full[full.index("static int append_record("):]
        append = append[:append.index("\n}")]
        emit_recall = emit.find("vv_village_recall(village, sizeof village)")
        self.assertNotEqual(emit_recall, -1, "emit_record never recalls the village")
        self.assertLess(
            emit_recall,
            emit.find("append_record(g, village"),
            "emit_record must recall the village before it writes a record",
        )
        source = "vv_village_recall(village, sizeof village)\n" + append
        recall = source.find("vv_village_recall(village, sizeof village)")
        select = source.find("select_log_file(g, village, path")
        # The gate, located by the measurement that decides it. This
        # used to search for "ftell(file) == 0"; that expression is now
        # gone from the code and survives only inside a comment that
        # explains why it was wrong, so the search matched the comment
        # and compared the wrong position.
        gate = source.find("had_content = log_file_has_content(path);")
        self.assertNotEqual(recall, -1, "the village is never recalled")
        self.assertNotEqual(select, -1, "the file choice is not given the village")
        self.assertNotEqual(gate, -1, "the header is not gated on a new file")
        self.assertLess(
            recall,
            select,
            "the village must be recalled before the log file is chosen, or "
            "records can be appended under another village's header",
        )
        self.assertLess(
            select,
            gate,
            "the file must be chosen before its header is written",
        )

    def test_the_gate_is_the_file_on_disk(self) -> None:
        """Neither the run-wide record count nor ftell.

        existing_records counts every file in the run, so it is non-zero
        for a brand-new roll-over file -- precisely a file that still
        needs a header. Using it would leave every roll-over log
        unidentified.

        ftell is worse, and was what shipped: on a stream freshly opened
        with "a" this CRT reports position 0 however long the file is, so
        the gate held for every record and stamped the header through the
        middle of the log -- 10 times in the owner's VV3 file, 10 in VV5,
        2 in VV2. The file's size on disk is the question actually being
        asked."""
        source = PARENTAGE_C.read_text(encoding="utf-8")
        self.assertNotIn(
            "if (existing_records == 0",
            source,
            "the header gate must not depend on the run-wide record count",
        )
        code = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
        self.assertNotIn(
            "ftell",
            code,
            "the header gate must not use ftell: on a freshly opened "
            "append stream it reports 0 however long the file is",
        )

    def test_a_log_from_another_village_is_not_appended_to(self) -> None:
        """Codex found that switching save slots left the same game-wide file
        selected, so conceptions from the new village were appended under the
        previous village's header. A misattributed record is worse than an
        unlabelled one: parentage cannot be recovered from a child afterwards,
        so the mistake is permanent."""
        source = PARENTAGE_C.read_text(encoding="utf-8")
        self.assertIn(
            "if (!log_belongs_to_village(destination, village)) {",
            source,
            "select_log_file must skip a log belonging to another village",
        )

    def test_a_log_with_no_header_is_never_rotated_away_from(self) -> None:
        """Logs written before headers existed are still the player's. Rotating
        away from one would strand their history in an old file and restart the
        numbering for no reason. The same applies when the current village is
        unknown -- rotating on "I do not know" would start a fresh log on every
        launch."""
        source = PARENTAGE_C.read_text(encoding="utf-8")
        body = source[source.index("static int log_belongs_to_village"):]
        body = body[:body.index("\n}\n")]
        self.assertIn(
            "read_log_header(path, existing, sizeof existing)",
            body,
            "the comparison must read the log's own header",
        )
        self.assertEqual(
            body.count("return 1;"),
            2,
            "a headerless log and an unknown village must each match",
        )


class PublisherLifetimeTests(unittest.TestCase):
    def test_only_one_mapping_handle_is_ever_opened(self) -> None:
        """Codex found the publisher opening a fresh handle on every save and
        never closing one, while its comment claimed a single process-lifetime
        handle. That is one leaked kernel handle per save, and the owner plays
        long sessions with frequent saves.

        The handle genuinely cannot be closed -- a file mapping lives only
        while a handle to it is open, and the parentage log reads it much
        later -- so the fix is to cache exactly one.
        """
        source = IDENTITY_C.read_text(encoding="utf-8")
        self.assertIn(
            "static HANDLE vv_share_handle",
            source,
            "the publisher must cache its mapping handle",
        )
        body = source[source.index("void vv_village_publish("):]
        body = body[:body.index("\n}\n")]
        self.assertIn(
            "if (vv_share_handle == NULL) {",
            body,
            "the mapping must only be created when one is not already held",
        )
        self.assertEqual(
            body.count("vv_share_open(1)"),
            1,
            "the publisher must open the mapping in exactly one place",
        )


class ParentageStandsAloneTests(unittest.TestCase):
    def test_the_parentage_log_does_not_require_the_statistics_feature(
        self,
    ) -> None:
        """Codex correctly found that a parentage log selected WITHOUT Village
        Statistics has no publisher and so gets no header. Making Statistics a
        prerequisite is the wrong fix: the patcher closes a selection over its
        prerequisites in BOTH directions, so unticking Statistics would
        silently untick the parentage log -- trading a missing header line for
        a missing feature.

        The log degrades instead, exactly as it behaved before headers
        existed. This guard exists because the dependency was tried and
        deliberately reverted; re-adding it would quietly remove a feature the
        owner asked for.
        """
        import json

        for game in range(1, 6):
            with self.subTest(game=game):
                manifest = json.loads(
                    (ROOT / "data" / ("vv%d_parentage_feature.json" % game))
                    .read_text(encoding="utf-8")
                )
                for feature in manifest["features"]:
                    # Narrowed to the STATISTICS dependency specifically. VV2's
                    # parentage log legitimately depends on its Origins
                    # upgrades, because VV2's own code cave is occupied by the
                    # renamed-build crash guard and the loader trampoline has
                    # to live in the page Origins appends. A guard that banned
                    # every dependency failed on that unrelated, correct one.
                    self.assertNotIn(
                        "vv%d_write_village_statistics" % game,
                        feature.get("dependencies", []),
                        "VV%d's parentage log must stay selectable without "
                        "Village Statistics" % game,
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
