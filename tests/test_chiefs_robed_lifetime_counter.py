"""Chiefs Robed is a lifetime counter hooked to the robing, not a snapshot.

The owner asked for "Chiefs Robed: everyone who has been made Chief with
the robe and bears the title Tribal Chief", and
docs/village-statistics-requirements.md adds the governing constraint:
"All counters are lifetime totals from creation of the individual save.
They must not be reconstructed only from current village state when that
would lose historical events."

Two wrong implementations are ruled out, for opposite reasons, and this
module guards against both.

WRONG ONE: the chief puzzle. The owner named this directly -- the counter
"shouldn't depend on the puzzle since the puzzle only completes upon the
first chief being made". VV3's puzzle-progress routine at 0x435990 runs
its completion branch exactly once, on the transition to complete. A chief
can die and be replaced many times without re-firing it, so a
puzzle-hooked counter reads 1 forever while looking plausible.

WRONG TWO: walking the living villagers for the chief flag. That reports
who holds the robe NOW, so it falls back to 1 -- or 0 -- as chiefs die,
and a lifetime total that can decrease is not a lifetime total. Review
caught this on #351 after the first attempt did exactly that.

RIGHT: a wrapper on sub_45FBC0, the robing routine itself. It is the only
writer of the chief flag +0xE80 in the whole image, and its single caller
sub_431FE0 is the ceremony -- which goes on to call the puzzle routine at
0x432042, proving the puzzle is downstream of robing. Hooking the robing
therefore catches every replacement the puzzle misses.

These assertions read the builder and exporter sources rather than running
the game, which is a real limitation: they pin the code that decides the
row, not an observed count.
"""

from __future__ import annotations

import base64
import json
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native" / "statistics_export" / "statistics_export.c"
BUILDER = ROOT / "scripts" / "build_statistics_features.py"
MANIFEST = ROOT / "data" / "statistics_features.json"
REQUIREMENTS = ROOT / "docs" / "village-statistics-requirements.md"


class ChiefsRobedIsALifetimeCounterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exporter = EXPORTER.read_text(encoding="utf-8")
        self.builder = BUILDER.read_text(encoding="utf-8")

    def test_the_row_is_emitted(self) -> None:
        self.assertIn('fprintf(file, "Chiefs Robed: %d\\n"', self.exporter)

    def test_the_row_is_not_a_walk_of_living_villagers(self) -> None:
        """A roster snapshot loses every chief who has died.

        The requirements forbid reconstructing a lifetime total from current
        state when that loses history, and such a value can count DOWN.
        """
        self.assertNotIn("count_robed_chiefs", self.exporter)
        self.assertNotIn("count_village_elders", self.exporter)

    def test_the_counter_is_advanced_at_the_robing_routine(self) -> None:
        """sub_45FBC0 is the only writer of the chief flag in the image."""
        self.assertIn('"robing_hook_va": 0x45FBC0,', self.builder)
        self.assertIn("robing_stat_va", self.builder)

    def test_the_counter_is_not_hooked_to_the_chief_puzzle(self) -> None:
        """0x435990 is the puzzle-progress routine; it fires once per puzzle."""
        self.assertNotIn("0x435990", self.builder)

    def test_the_hook_guard_pins_the_stock_bytes(self) -> None:
        """A hook whose guard does not match would patch the wrong site."""
        self.assertIn('"robing_guard": "8B4424048B88740E0000"', self.builder)

    def test_the_wrapper_replays_the_instructions_it_displaced(self) -> None:
        """The two displaced instructions must run before the stock body."""
        block = self.builder[self.builder.index("robing_wrapper = assemble(") :]
        block = block[: block.index('"""', block.index('f"""') + 6)]
        self.assertIn("mov eax, [esp + 4]", block)
        self.assertIn("mov ecx, [eax + 0xE74]", block)
        self.assertIn("inc dword ptr", block)


class ChiefsRobedPatchIsInTheManifestTests(unittest.TestCase):
    """The row is worthless if the hook does not reach the built artifact."""

    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.vv3 = [f for f in self.manifest["features"] if f["game_id"] == "vv3"]

    def test_the_robing_hook_patch_is_present(self) -> None:
        offsets = {
            p["offset"] for feature in self.vv3 for p in feature["patches"]
        }
        self.assertIn(
            "0x5FBC0",
            offsets,
            "the robing hook did not reach data/statistics_features.json",
        )

    def test_the_hook_jumps_into_the_cave_and_the_cave_jumps_back(self) -> None:
        """Both directions, checked arithmetically rather than by eye.

        A wrapper that returns to the wrong address corrupts the robing and
        would not be caught by any string comparison.
        """
        hook_va = 0x45FBC0
        cave_va = 0x47B464
        patches = {
            p["offset"]: p for feature in self.vv3 for p in feature["patches"]
        }
        hook = patches["0x5FBC0"]
        after = bytes.fromhex(str(hook["after"]))
        self.assertEqual(after[0], 0xE9, "the hook is not a near jump")
        forward = struct.unpack("<i", after[1:5])[0]
        wrapper_va = hook_va + 5 + forward

        cave = patches["0x7B464"]
        payload = base64.b64decode(str(cave["after_base64"]))
        wrapper_offset = wrapper_va - cave_va
        self.assertGreater(wrapper_offset, 0)
        self.assertLess(wrapper_offset, len(payload))

        body = payload[wrapper_offset : wrapper_offset + 32]
        jump = body.index(0xE9)
        back = struct.unpack("<i", body[jump + 1 : jump + 5])[0]
        target = wrapper_va + jump + 5 + back
        self.assertEqual(
            target,
            hook_va + len(bytes.fromhex(str(hook["before"]))),
            "the wrapper does not return just past the bytes it displaced",
        )

    def test_the_wrapper_does_not_collide_with_the_burial_wrapper(self) -> None:
        """The burial wrapper sits at cave 0x190; this one must END before it.

        Checked against the wrapper's real length, not just its start: a
        wrapper that begins below 0x190 can still run into the burial
        wrapper, and overlapping cave allocations corrupt whichever patch is
        written second with no error at patch time.
        """
        cave_va = 0x47B464
        patches = {
            p["offset"]: p for feature in self.vv3 for p in feature["patches"]
        }
        after = bytes.fromhex(str(patches["0x5FBC0"]["after"]))
        wrapper_va = 0x45FBC0 + 5 + struct.unpack("<i", after[1:5])[0]
        start = wrapper_va - cave_va
        self.assertGreaterEqual(start, 0xB2, "wrapper starts before its gap")

        payload = base64.b64decode(str(patches["0x7B464"]["after_base64"]))
        body = payload[start : start + 64]
        end = start + body.index(0xE9) + 5
        self.assertLessEqual(
            end,
            0x190,
            "the robing wrapper runs into the burial wrapper at cave 0x190",
        )


class VillageEldersStillNeedsALifetimeCounterTests(unittest.TestCase):
    """The row is knowingly unfinished; this pins why, so it is not forgotten.

    The field it reads has zero references in any of the three later-game
    executables, so nothing in the stock game writes it. The fix is a
    lifetime mastery counter, NOT a roster walk -- the walk was tried and
    correctly rejected in review.
    """

    def setUp(self) -> None:
        self.exporter = EXPORTER.read_text(encoding="utf-8")

    def test_the_known_gap_is_recorded_next_to_the_field(self) -> None:
        self.assertIn("ZERO references", self.exporter)

    def test_no_writer_reintroduces_a_roster_walk_for_elders(self) -> None:
        self.assertNotIn("count_village_elders", self.exporter)


class RequirementsStillGovernTests(unittest.TestCase):
    def test_lifetime_totals_are_still_required(self) -> None:
        """If this sentence goes, the reasoning above needs revisiting."""
        text = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertIn("lifetime totals", text)
        self.assertIn("must not be reconstructed only from current", text)


if __name__ == "__main__":
    unittest.main()
