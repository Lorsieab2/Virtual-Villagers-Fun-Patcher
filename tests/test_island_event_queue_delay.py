"""The purchased Island Event is QUEUED, never made due on the next tick.

Every game's Island Event upgrade used to make the event due immediately by
storing a constant zero into the world's island-event due stamp. The
island-event handler then fired it in whatever tick it next ran -- which is
also the tick a NATURAL island event can be due in, so a purchased event and a
natural one could present back to back.

Each game now stamps `now + delay` instead, read from that game's own
scheduler clock. Those clocks all convert GetSystemTimeAsFileTime through
0x989680 (10,000,000), so they return Unix epoch SECONDS: the same units the
due stamp already holds and the same units Time Warp subtracts in. The delay is
therefore real seconds at every game speed rather than a frame count.

The barrel got the same treatment per game, but each game already had its own
cue mechanism for it (VV1 BARREL_DELAY_TICKS, VV2 BARREL_CUE_FRAMES, VV3 a due
stamp in its appended R/W page), so only the Island Event needed adding.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# game -> (generator, scheduler clock VA, world due-stamp field)
GAMES = {
    "vv1": ("scripts/build_vv1_origins_feature.py", "0x402F70", 0xA300),
    "vv2": ("scripts/build_vv2_origins_feature.py", "0x403200", 0x2EAE0),
}


def island_branch(text: str) -> str:
    """The assembly of do_island_event up to the next label."""
    start = text.find("        do_island_event:")
    if start == -1:
        return ""
    rest = text[start + len("        do_island_event:"):]
    nxt = re.search(r"^\s{8}[a-z_0-9]+:\s*$", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


class IslandEventIsQueuedTests(unittest.TestCase):
    def test_no_game_makes_the_island_event_due_immediately(self) -> None:
        """Storing a constant zero is the bug this replaced."""
        for gid, (script, _clock, field) in GAMES.items():
            with self.subTest(game=gid):
                branch = island_branch((ROOT / script).read_text(encoding="utf-8"))
                self.assertTrue(branch, f"{gid} has no do_island_event branch")
                self.assertNotIn(
                    f"mov dword ptr [edi + 0x{field:X}], 0",
                    branch,
                    f"{gid} still makes the Island Event due on the next tick",
                )

    def test_every_game_stamps_the_delay_from_its_own_clock(self) -> None:
        for gid, (script, clock, field) in GAMES.items():
            with self.subTest(game=gid):
                text = (ROOT / script).read_text(encoding="utf-8")
                branch = island_branch(text)
                self.assertIn("ISLAND_QUEUE_CLOCK_VA", branch,
                              f"{gid} does not call its scheduler clock")
                self.assertIn("ISLAND_QUEUE_DELAY_SECONDS", branch,
                              f"{gid} does not add a delay")
                self.assertIn(f"mov dword ptr [edi + 0x{field:X}], eax", branch,
                              f"{gid} does not store the computed due time")
                self.assertIn(f"ISLAND_QUEUE_CLOCK_VA = {clock}", text,
                              f"{gid} points at the wrong clock")

    def test_the_world_pointer_is_preserved_across_the_clock_call(self) -> None:
        """edi holds the world and is also the store's base register.

        The clocks do not write edi, but the branch must not depend on that:
        a call that clobbered it would corrupt the store target.
        """
        for gid, (script, _clock, _field) in GAMES.items():
            with self.subTest(game=gid):
                branch = island_branch((ROOT / script).read_text(encoding="utf-8"))
                call = branch.find("call 0x{ISLAND_QUEUE_CLOCK_VA:X}")
                self.assertNotEqual(call, -1)
                self.assertIn("push edi", branch[:call])
                self.assertIn("pop edi", branch[call:])

    def test_the_delay_is_a_positive_number_of_seconds(self) -> None:
        for gid, (script, _clock, _field) in GAMES.items():
            with self.subTest(game=gid):
                text = (ROOT / script).read_text(encoding="utf-8")
                match = re.search(r"^ISLAND_QUEUE_DELAY_SECONDS = (\d+)$", text, re.M)
                self.assertIsNotNone(match, f"{gid} has no delay constant")
                self.assertGreater(int(match.group(1)), 0)

    def test_the_reason_is_recorded_beside_the_constant(self) -> None:
        """A future edit that reverts to zero must see why it cannot."""
        for gid, (script, _clock, _field) in GAMES.items():
            with self.subTest(game=gid):
                text = (ROOT / script).read_text(encoding="utf-8")
                where = text.find("ISLAND_QUEUE_CLOCK_VA = ")
                comment = text[max(0, where - 900):where]
                self.assertIn("0x989680", comment)
                self.assertIn("epoch", comment.lower())


if __name__ == "__main__":
    unittest.main()
