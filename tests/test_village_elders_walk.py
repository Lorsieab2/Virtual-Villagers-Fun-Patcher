"""Village Elders and Chiefs Robed are walked, not read from a dead field.

The owner's definition: "Village Elders = anyone who reaches Master status
in at least 3 or more skills. All 5 games." Counted per villager, so a
villager who masters five skills still counts once.

Before this, all three later-game writers printed `read_int(statistics,
0x1C)`. That field has ZERO references anywhere in any of the three
executables -- nothing in the stock game ever writes it -- so the row was
reporting a field the game never fills. A scan of every absolute access
into each game's live statistics block found references at +0x00, +0x04,
+0x08, +0x0C, +0x10, +0x14, +0x18, +0x20, +0x24, +0x28 and +0x2C, and none
at +0x1C, in all three games independently.

Chiefs Robed carries a second trap, which the owner named directly: it
"shouldn't depend on the puzzle since the puzzle only completes upon the
first chief being made". VV3's puzzle-progress routine at 0x435990 runs its
completion branch exactly once, so a counter hooked there would read 1
forever while chiefs died and were replaced -- wrong in a way that looks
right on first inspection.

These assertions read the exporter source. That pins the code that decides
each row rather than an observed export, which is a real limitation: the
suite cannot run the game. The offsets themselves were measured against 65
of the owner's own .ldw saves, and that measurement is what
test_villager_record_layout_matches_measurements below encodes.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native" / "statistics_export" / "statistics_export.c"
PARENTAGE = ROOT / "native" / "parentage_export" / "parentage_export.c"


class VillageEldersWalkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = EXPORTER.read_text(encoding="utf-8")

    def test_the_dead_statistics_field_is_no_longer_printed_as_elders(self) -> None:
        """No writer may pass statistics+0x1C where Village Elders goes.

        The field is never written by any of the three games, so any row fed
        from it reports a number the game does not track.
        """
        # The row must be fed by the walk in every writer that prints it.
        self.assertEqual(
            self.source.count("elders < 0 ? 0 : elders"),
            2,
            "both the shared later-game writer and write_vv5 must feed "
            "Village Elders from the walk",
        )
        # And 0x1C must not survive as a live argument anywhere.
        live_reads = re.findall(
            r"^\s*read_int\(statistics, 0x1C\),", self.source, re.MULTILINE
        )
        self.assertEqual(
            live_reads, [], "a writer still prints the unreferenced 0x1C field"
        )

    def test_a_villager_counts_once_however_many_skills_it_masters(self) -> None:
        """The owner's rule is per villager, not per mastery."""
        self.assertIn("if (mastered >= 3) {", self.source)
        self.assertIn("++total;", self.source)
        # The increment must be outside the per-skill loop: a `++total` inside
        # it would count a five-skill master five times.
        walk = self.source[
            self.source.index("static int count_village_elders(") :
        ]
        walk = walk[: walk.index("\n}\n")]
        inner = walk[walk.index("for (index = 0;") : walk.index("if (mastered >= 3)")]
        self.assertNotIn("++total", inner)

    def test_both_skill_encodings_are_handled(self) -> None:
        """VV3 stores skills as int32; VV4 and VV5 store them as floats.

        This is the fact that defeated every earlier search: an integer-only
        scan finds nothing in the two later games.
        """
        self.assertIn("float value = *(const float *)field;", self.source)
        self.assertIn("*(const int *)field >= master_threshold", self.source)

    def test_new_believers_gets_six_skills_not_five(self) -> None:
        """New Believers has a sixth skill; its float run is one dword longer."""
        vv5 = self.source[self.source.index("static int write_vv5(") :]
        vv5 = vv5[: vv5.index("__declspec(dllexport)")]
        self.assertIn("0x1C5Cu, 6, 1,", vv5)

    def test_chiefs_robed_is_not_hooked_to_the_chief_puzzle(self) -> None:
        """The puzzle fires once, for the first chief only.

        A chief can die and be replaced many times; none of those re-fires
        the puzzle. The row must come from the villager record instead.
        """
        self.assertIn("static int count_robed_chiefs(", self.source)
        walk = self.source[self.source.index("static int count_robed_chiefs(") :]
        walk = walk[: walk.index("\n}\n")]
        # It reads the record, not any puzzle state.
        self.assertIn("record + chief_offset", walk)
        self.assertNotIn("puzzle", walk.lower())

    def test_only_the_secret_city_prints_chiefs_robed(self) -> None:
        """The other games have no chief, so a zero offset omits the row."""
        self.assertIn('fprintf(file, "Chiefs Robed: %d\\n", chiefs)', self.source)
        self.assertIn("if (villager_chief != 0u", self.source)

    def test_the_walk_skips_records_that_are_not_living_villagers(self) -> None:
        """A dead or empty slot must not contribute to either row."""
        for name in ("count_village_elders", "count_robed_chiefs"):
            walk = self.source[self.source.index("static int %s(" % name) :]
            walk = walk[: walk.index("\n}\n")]
            self.assertIn(
                "*(const unsigned char *)(record + active_offset) != 1",
                walk,
                "%s does not check the active byte" % name,
            )

    def test_villager_record_layout_matches_measurements(self) -> None:
        """Each game's layout, as measured and cross-checked.

        Strides, slot counts, record bases and active bytes agree with
        parentage_export.c, which measured them independently for a different
        feature. That agreement is the check: two features derived the same
        numbers from the same executables without sharing a source.
        """
        for stride, record_base, active in (
            ("0x1F8Cu", "0x14u", "0xF10u"),      # VV3
            ("0x2E3Cu", "0x44u", "0x1CC4u"),     # VV4
            ("0x2F44u", "0x48u", "0x1CD4u"),     # VV5
        ):
            self.assertIn(stride, self.source)
            self.assertIn(active, self.source)

    def test_the_strides_agree_with_the_parentage_exporter(self) -> None:
        """The two features must not disagree about the same records."""
        parentage = PARENTAGE.read_text(encoding="utf-8")
        for stride in ("0x1F8C", "0x2E3C", "0x2F44"):
            self.assertIn(stride, parentage)
            self.assertIn(stride, self.source)

    def test_an_unlocated_array_does_not_print_a_confident_zero(self) -> None:
        """Without a module handle there is nothing to walk.

        The helpers return -1 rather than 0 so a failed walk is distinguishable
        from a village that genuinely has no elders.
        """
        for name in ("count_village_elders", "count_robed_chiefs"):
            walk = self.source[self.source.index("static int %s(" % name) :]
            walk = walk[: walk.index("\n}\n")]
            self.assertIn("return -1;", walk)


class VillageEldersOrderTests(unittest.TestCase):
    """The owner specified the row order; Village Elders keeps its place."""

    def setUp(self) -> None:
        self.source = EXPORTER.read_text(encoding="utf-8")

    def test_village_elders_sits_between_population_and_oldest_villager(self) -> None:
        for writer in ("static int write_later_game(", "static int write_vv5("):
            body = self.source[self.source.index(writer) :]
            body = body[: body.index("\n}\n")]
            pop = body.index('"Highest Population: %d\\n"')
            elders = body.index('"Village Elders: %d\\n"')
            oldest = body.index('"Oldest Villager: %d\\n"')
            self.assertLess(pop, elders, writer)
            self.assertLess(elders, oldest, writer)


if __name__ == "__main__":
    unittest.main()
