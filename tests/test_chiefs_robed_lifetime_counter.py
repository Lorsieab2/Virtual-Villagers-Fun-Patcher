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


class ChiefsRobedIsSeededForExistingSavesTests(unittest.TestCase):
    """A save that predates the hook must not export a confident 0.

    The wrapper only counts robings that happen after the patch is
    installed. Without a seed, a village that already has a chief exports
    Chiefs Robed: 0 and stays short by every pre-install robing for ever,
    which is not a lifetime total "from creation of the individual save".
    Review raised this on #351 after the counter itself was correct.

    The baseline is deliberately modest. Nothing in a save records chiefs
    who have died -- that is why the row needs a counter and not a walk --
    so the only recoverable fact is whether a chief exists now. Seeding 1
    in that case is exact for a village that has never lost a chief and a
    lower bound for one that has, and it never overstates.
    """

    def setUp(self) -> None:
        self.exporter = EXPORTER.read_text(encoding="utf-8")
        self.builder = BUILDER.read_text(encoding="utf-8")

    def test_the_counter_is_seeded_once(self) -> None:
        self.assertIn("static int seeded_robing_total(", self.exporter)
        self.assertIn("ROBING_BASELINE_MARKER", self.exporter)

    def test_the_seed_is_gated_on_a_marker_not_on_the_value(self) -> None:
        """A new village with no chief looks identical to an unseeded one.

        Gating on `counter == 0` would re-seed every export and pin a
        village that has genuinely never had a chief at 1 for ever.
        """
        block = self.exporter[self.exporter.index("static int seeded_robing_total(") :]
        block = block[: block.index("\n}\n")]
        self.assertIn("!= (int)ROBING_BASELINE_MARKER", block)

    def test_the_marker_is_written_even_when_no_chief_is_found(self) -> None:
        """Otherwise the walk repeats on every export for a chiefless village.

        Checked by INDENTATION, not by textual order. Moving the write inside
        the `if (baseline > stored)` block leaves it after that test in the
        text, so an ordering check passes while the bug is present: a village
        with no chief yet would never be marked, would re-walk on every
        export, and would be seeded the moment it gained its first chief --
        double-counting that chief against the hook.

        The marker write belongs at the same indent as the `if`, so it runs on
        both paths.
        """
        body = self.exporter[self.exporter.index("static int seeded_robing_total(") :]
        body = body[: body.index("\n}\n")]
        marker_lines = [
            line for line in body.splitlines()
            if "write_int(counters, marker_offset" in line
        ]
        self.assertEqual(len(marker_lines), 1, "expected exactly one marker write")
        indent = len(marker_lines[0]) - len(marker_lines[0].lstrip())
        self.assertEqual(
            indent,
            8,
            "the marker write is nested inside the raise, so a chiefless "
            "village would never be marked as seeded",
        )

    def test_the_seed_never_lowers_a_counter_that_has_run_ahead(self) -> None:
        """The baseline raises, never replaces.

        A save whose counter has already passed the baseline -- any village
        that has robed a chief since the patch was installed -- must not be
        walked back to 1. `>` is the only comparison that is safe here; `!=`
        or `<` would overwrite a larger stored value.
        """
        body = self.exporter[self.exporter.index("static int seeded_robing_total(") :]
        body = body[: body.index("\n}\n")]
        guards = [
            line.strip() for line in body.splitlines()
            if "baseline" in line and "stored" in line and "if" in line
        ]
        self.assertEqual(
            guards,
            ["if (baseline > stored) {"],
            "the seed must raise the counter, never replace it",
        )

    def test_the_marker_has_its_own_reserve_slot(self) -> None:
        """+0x48, clear of burials (+0x38/+0x3C), deaths (+0x40), chiefs (+0x44)."""
        self.assertIn('"robing_marker_va": 0x5824E8,', self.builder)

    def test_the_baseline_reads_the_runtime_confirmed_chief_flag(self) -> None:
        """+0xE80, not the +0xAC measured in the saved record.

        The saved record has stride 0x11C and the in-memory one 0x1F8C, so a
        save-file offset is meaningless at runtime.
        """
        self.assertIn("0xF10u, 0xE80u", self.exporter)
        self.assertNotIn("0xACu", self.exporter)


class VillageEldersCountsTheLivingAndTheDeadTests(unittest.TestCase):
    """The row is fixed, and this pins the shape of the fix.

    This class previously asserted the row was knowingly unfinished. That was
    correct at the time: the field it read, statistics+0x1C, has zero
    non-stack references in any of the three later-game executables, and the
    obvious repair -- a bare walk of the living roster -- was tried and
    correctly rejected in review, because it is not a lifetime total and
    counts DOWN as elders die.

    What changed is the owner's instruction that the row be retroactive: "a
    retroactive counter for dead villagers too would be nice." That resolves
    the objection rather than overriding it. The walk is paired with the
    verdict each game's burial writer already persisted, so the figure covers
    villagers who have died and only ever grows.

    These tests exist so the buried half cannot be dropped later, leaving the
    bare walk the review rejected.
    """

    def setUp(self) -> None:
        self.exporter = EXPORTER.read_text(encoding="utf-8")

    def test_the_dead_field_is_no_longer_read_for_this_row(self) -> None:
        """statistics+0x1C is never written by any of the three games."""
        self.assertIn("count_living_elders", self.exporter)
        self.assertIn("count_buried_elders", self.exporter)

    def test_a_bare_roster_walk_is_never_shipped_alone(self) -> None:
        """Every living count must be paired with a buried count.

        A walk on its own is the design review rejected: it reports who holds
        the status now and falls as elders die. The pairing is what makes the
        row a lifetime figure.
        """
        living = self.exporter.count("count_living_elders(")
        buried = self.exporter.count("count_buried_elders(")
        # One definition plus N call sites each; the call counts must match.
        self.assertGreaterEqual(living, 2)
        self.assertEqual(
            living,
            buried,
            "every count_living_elders call must be paired with a "
            "count_buried_elders call, or the row loses its dead elders",
        )

    def test_the_buried_half_is_actually_added(self) -> None:
        """Not merely present -- ADDED to the living count.

        Mutation testing caught this: a guard that only checked
        count_buried_elders appeared in the file still passed when the call
        was multiplied by zero, which is the bare roster walk review
        rejected wearing the right name.
        """
        # Skip the definition, which is `static int count_living_elders(`.
        calls = [
            match
            for match in re.finditer(r"count_living_elders\(", self.exporter)
            if "static int " not in self.exporter[max(0, match.start() - 12):match.start()]
        ]
        self.assertGreaterEqual(len(calls), 2, "expected a call site per game")
        for call in calls:
            tail = self.exporter[call.end(): call.end() + 600]
            self.assertRegex(
                tail,
                r"\)\s*\n\s*\+\s*count_buried_elders\(",
                "a living count is not summed with a buried count",
            )
        self.assertNotIn("* count_buried_elders", self.exporter)
        self.assertNotIn("0 * count", self.exporter)

    def test_the_mastery_bar_is_three(self) -> None:
        """The owner's definition: Master status in at least THREE skills."""
        self.assertIn("if (mastered >= 3) {", self.exporter)

    def test_graves_are_gated_on_occupancy(self) -> None:
        """Without the gate the terminator slot is counted.

        In the owner's VV5 saves slot 499 carries a garbage name and a
        non-boolean byte where the elder flag lives, which is what made an
        early count report three distinct values for a field `setnl` can only
        write as 0 or 1.
        """
        body = self.exporter[self.exporter.index("static int count_buried_elders"):]
        body = body[: body.index("\n}")]
        self.assertIn("read_int(record, occupied_offset) == 0", body)
        self.assertIn("continue;", body)

    def test_vv4s_elder_flag_is_patch_owned_not_the_stock_byte(self) -> None:
        """VV4 must write +0x37, never +0x31.

        +0x31 is where the stock burial writer stores sub_46AC70's verdict,
        and that routine is `cmp edx, 5` -- mastered ALL five skills. Pointing
        the patch flag there would both clobber a stock field and count a
        far rarer thing under the owner's three-or-more label.
        """
        builder = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"elder_grave_offset": 0x37,', builder)
        self.assertNotIn('"elder_grave_offset": 0x31,', builder)

    def test_vv4s_wrapper_replays_the_instruction_it_stole(self) -> None:
        """The splice takes `call sub_46AC70`; it must be replayed.

        Without the replay grave+0x31 never receives its stock value, so the
        patch would silently change behaviour the owner did not ask to change
        -- and the epitaph selector downstream reads that field.
        """
        builder = BUILDER.read_text(encoding="utf-8")
        block = builder[builder.index("elder_hook_va = config.get"):]
        block = block[: block.index("robing_hook_va = config.get")]
        self.assertIn("call 0x{elder_stolen_target:X}", block)
        # Decoded from the guard bytes, so the replay cannot drift from the
        # instruction actually being replaced.
        self.assertIn("elder_stolen_target = (", block)
        self.assertIn('int.from_bytes(elder_guard[1:5], "little", signed=True)', block)

    def test_the_skill_encoding_and_count_are_not_shared_between_games(self) -> None:
        """VV5 has six skills; VV3 and VV4 have five. VV3 stores int32.

        Carrying either across games is silently wrong: six slots on a
        five-skill game reads past the block, and the wrong encoding compares
        a float bit pattern against an integer threshold.
        """
        self.assertIn("0xEACu, 5u, 0", self.exporter)      # VV3 int32, 5
        self.assertIn("0x1C5Cu, 5u, 1", self.exporter)     # VV4 float, 5
        self.assertIn("0x1C5Cu, 6u, 1", self.exporter)     # VV5 float, 6


class RequirementsStillGovernTests(unittest.TestCase):
    def test_lifetime_totals_are_still_required(self) -> None:
        """If this sentence goes, the reasoning above needs revisiting."""
        text = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertIn("lifetime totals", text)
        self.assertIn("must not be reconstructed only from current", text)


if __name__ == "__main__":
    unittest.main()
