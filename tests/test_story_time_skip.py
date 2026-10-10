"""Choose Time Skip Amount (Story / Cheat Upgrades).

The owner (2026-10-10): "add a cheat upgrade: Choose Time Skip Amount (costs
same as the normal upgrade). Choose a number of years to skip from 1-72."

The Story companion (native/vvfp_story_upgrades/story_time_skip.inc) runs the
skip as a series of the Origins companion's own Time Warp steps, handed to it
through the host table (native/shared/story_bridge.h).  These tests drive the
TEST build in the emulator with a host whose step and settled entries are
stubs, so the scheduling, the price and the refusals are checked against the
companion's real code; the Origins companion's own step (its Time Warp
advance) is checked statically against its source.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

from test_story_custom_island_event import (  # noqa: E402
    SCRATCH, Story, emulated, have_stock,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "vvfp_story_upgrades" / "story_time_skip.inc"
BRIDGE = ROOT / "native" / "shared" / "story_bridge.h"
VV1 = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
TECH = 0xA2FC                         # A New Home: the world's tech points


class TimeSkipHost:
    """A host table with the time skip's two entries.  `step_years` is what
    one Time Warp buys now (-1 = paused); `settled` what the villager tick
    answers."""

    def __init__(self, story: Story, step_years: int = 6):
        proc = story.proc
        self.step_years = step_years
        self.settled = False
        self.steps: list[int] = []
        code = proc.alloc(0x100)
        proc.write(code, b"\xC3" * 0x60)
        table = proc.alloc(0x40)
        proc.write(table, struct.pack("<7I", 28, code, code + 0x10, code + 0x20, 0,
                                      code + 0x40, code + 0x50))
        proc.stub(code, lambda p: (1, 0))
        proc.stub(code + 0x10, lambda p: (0, 4))
        proc.stub(code + 0x20, lambda p: (1, 8))

        def step(p):
            wanted = p.arg(0)
            if self.step_years < 0:
                return 0xFFFFFFFF, 4
            years = min(wanted, self.step_years)
            self.steps.append(years)
            self.settled = False
            return years, 4
        proc.stub(code + 0x40, step)
        proc.stub(code + 0x50, lambda p: (1 if self.settled else 0, 0))
        assert proc.export("VvfpStoryAttachHost", story.n, table) == 1


def state(story: Story) -> dict:
    story.proc.export("VvfpStoryProbeTimeSkipState", SCRATCH)
    active, game, remaining, waiting = struct.unpack("<4i", story.proc.read(SCRATCH, 16))
    return {"active": active, "game": game, "remaining": remaining, "waiting": waiting}


def tick(story: Story, at: int) -> None:
    story.proc.export("VvfpStoryProbeSetTick", at)
    story.proc.export("VvfpStoryInstall", story.n)


@emulated
@unittest.skipUnless(have_stock("vv1"), "stock A New Home is not in inputs/")
class VV1TimeSkipTests(unittest.TestCase):
    def make(self, step_years: int = 6, tech: int = 0, charged: bool = False):
        story = Story("vv1")
        story.village.put(0, sex="f", years=20, name="Ama")
        story.proc.put32(story.village.world + TECH, tech)
        if charged:
            story.proc.export("VvfpStoryProbeCharges", 1, 1)
        return story, TimeSkipHost(story, step_years)

    def test_seventy_two_years_is_twelve_normal_time_warps(self):
        story, host = self.make(step_years=6)
        self.assertEqual(story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 72, 1000), 6)
        self.assertEqual(state(story), {"active": 1, "game": 1, "remaining": 66, "waiting": 1})
        at = 1000
        for _ in range(200):
            at += 100
            tick(story, at)                   # not replayed yet: no step
            host.settled = True               # the villager tick has run
            tick(story, at + 50)
            if not state(story)["active"]:
                break
        self.assertEqual(host.steps, [6] * 12)
        self.assertEqual(sum(host.steps), 72)
        self.assertEqual(state(story)["active"], 0)

    def test_a_step_waits_for_the_villager_tick(self):
        story, host = self.make(step_years=12)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 30, 0)
        for at in range(100, 5000, 100):
            tick(story, at)
        self.assertEqual(host.steps, [12])    # never settled: no second step
        host.settled = True
        tick(story, 5100)
        self.assertEqual(host.steps, [12, 12])
        host.settled = True
        tick(story, 5200)
        self.assertEqual(host.steps, [12, 12, 6])   # the last step is what is left
        self.assertEqual(state(story)["active"], 0)

    def test_a_tick_never_seen_lapses_after_twenty_seconds(self):
        story, host = self.make(step_years=3)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 6, 0)
        tick(story, 19999)
        self.assertEqual(host.steps, [3])
        tick(story, 20000)
        self.assertEqual(host.steps, [3, 3])

    def test_one_step_skip_finishes_at_once(self):
        story, host = self.make(step_years=12)
        self.assertEqual(story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 5, 0), 5)
        self.assertEqual(host.steps, [5])
        self.assertEqual(state(story)["active"], 0)

    def test_paused_waits_and_goes_on_when_running(self):
        story, host = self.make(step_years=6)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 12, 0)
        host.step_years = -1                  # paused
        host.settled = True
        tick(story, 100)
        tick(story, 200)
        self.assertEqual(host.steps, [6])
        self.assertEqual(state(story)["remaining"], 6)
        host.step_years = 6
        tick(story, 300)
        self.assertEqual(host.steps, [6, 6])

    def test_paused_at_purchase_starts_nothing_and_charges_nothing(self):
        story, host = self.make(step_years=-1, tech=80000, charged=True)
        self.assertEqual(story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 10, 0), 0xFFFFFFFF)
        self.assertEqual(state(story)["active"], 0)
        self.assertEqual(story.proc.u32(story.village.world + TECH), 80000)

    def test_years_outside_one_to_seventy_two_are_refused(self):
        story, host = self.make()
        for years in (0, 73, -1):
            self.assertEqual(story.proc.export("VvfpStoryProbeTimeSkipStart", 1, years & 0xFFFFFFFF, 0), 0)
        self.assertEqual(host.steps, [])

    def test_price_is_the_time_warps(self):
        story, host = self.make(tech=80000)
        self.assertEqual(story.proc.export("VvfpStoryProbeTimeSkipPrice", 1), 0)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 6, 0)
        self.assertEqual(story.proc.u32(story.village.world + TECH), 80000)    # free

        story, host = self.make(tech=80000, charged=True)
        self.assertEqual(story.proc.export("VvfpStoryProbeTimeSkipPrice", 1), 50000)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 72, 0)
        self.assertEqual(story.proc.u32(story.village.world + TECH), 30000)    # charged once
        host.settled = True
        tick(story, 100)
        self.assertEqual(story.proc.u32(story.village.world + TECH), 30000)

    def test_another_village_drops_the_rest(self):
        story, host = self.make(step_years=6)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 24, 0)
        story.proc.export("VvfpStoryVillageReset", 1, 1)     # Start Over / deleted tribe
        host.settled = True
        tick(story, 100)
        self.assertEqual(host.steps, [6])
        self.assertEqual(state(story)["active"], 0)

    def test_an_empty_village_ends_the_skip(self):
        story, host = self.make(step_years=6)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 24, 0)
        host.step_years = 0                   # nobody left to advance
        host.settled = True
        tick(story, 100)
        self.assertEqual(state(story)["active"], 0)

    def test_an_old_host_still_attaches_without_the_time_skip(self):
        story = Story("vv1")                  # its Host is the 20-byte table
        self.assertEqual(story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 6, 0), 0)


class StaticTimeSkipTests(unittest.TestCase):
    def test_bounds_and_price(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("#define TIME_SKIP_MIN_YEARS 1", text)
        self.assertIn("#define TIME_SKIP_MAX_YEARS 72", text)
        self.assertIn("#define TIME_SKIP_PRICE 50000", text)

    def test_vv1_step_is_the_time_warp_at_the_current_speed(self):
        text = VV1.read_text(encoding="utf-8")
        body = text[text.index("static int __stdcall vv1_story_time_skip_step(int years) {"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("step = vv1_time_warp_years(speed);", body)
        self.assertIn("vv1_time_warp_apply(speed, step)", body)
        self.assertIn("return -1;", body)
        # 20 age units a year, the Time Warp's own conversion.
        self.assertIn("#define VV1_TW_UNITS_PER_YEAR    20", text)
        self.assertRegex(text, r"vv1_story_time_skip_step, vv1_story_time_skip_settled")

    def test_the_button_is_not_under_the_island_event_lock(self):
        text = BRIDGE.read_text(encoding="utf-8")
        clicked = text[text.index("static int vvfp_story_pick_clicked("):]
        self.assertLess(clicked.index("VVFP_STORY_TIME_SKIP_ID"), clicked.index("blocked_reason != NULL"))
        self.assertTrue(re.search(r"#define VVFP_STORY_TIME_SKIP_ID 4093", text))


ALL_GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
COMPANIONS = {
    "vv1": (VV1, "vv1_story_time_skip_step", "vv1_time_warp_apply(speed, step)"),
    "vv2": (ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c",
            "vv2_story_time_skip_step", "vv2_time_warp_apply(base, speed, step)"),
    "vv3": (ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c",
            "vv3_story_time_skip_step", "vv3_time_warp_apply(speed, step)"),
    "vv4": (ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c",
            "vv4_story_time_skip_step", "vv4_time_warp_apply(speed, step)"),
    "vv5": (ROOT / "native" / "vv5_task9_origins" / "vv5_task9_origins.c",
            "vv5_story_time_skip_step", "vv5_time_warp_apply(speed, step)"),
}


@emulated
class EveryGameTimeSkipTests(unittest.TestCase):
    """The scheduler is game-independent: every game's Story companion runs 72
    years as 1-year-exact steps of whatever its Time Warp buys."""

    def test_seventy_two_years_in_every_game(self):
        for game in ALL_GAMES:
            if not have_stock(game):
                continue
            for per_step, expected in ((3, 24), (6, 12), (12, 6)):
                with self.subTest(game=game, per_step=per_step):
                    story = Story(game)
                    host = TimeSkipHost(story, per_step)
                    self.assertEqual(
                        story.proc.export("VvfpStoryProbeTimeSkipStart", story.n, 72, 0), per_step)
                    at = 0
                    for _ in range(100):
                        host.settled = True
                        at += 100
                        tick(story, at)
                        if not state(story)["active"]:
                            break
                    self.assertEqual(host.steps, [per_step] * expected)
                    self.assertEqual(sum(host.steps), 72)

    def test_bounds_in_every_game(self):
        for game in ALL_GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = Story(game)
                host = TimeSkipHost(story, 6)
                for years in (0, 73):
                    self.assertEqual(
                        story.proc.export("VvfpStoryProbeTimeSkipStart", story.n, years, 0), 0)
                self.assertEqual(host.steps, [])
                self.assertEqual(story.proc.export("VvfpStoryProbeTimeSkipPrice", story.n), 0)


class StaticEveryGameTests(unittest.TestCase):
    def test_every_companion_steps_with_its_own_time_warp(self):
        for game, (path, name, apply_call) in COMPANIONS.items():
            with self.subTest(game=game):
                text = path.read_text(encoding="utf-8")
                start = text.index(f"static int __stdcall {name}(int years) {{")
                body = text[start:text.index("\n}\n", start)]
                self.assertIn(apply_call, body)
                self.assertIn("return -1;", body)            # paused: nothing changed
                self.assertIn("if (step > years)", body)     # never more than asked
                self.assertIn(f"{name}, ", text[text.index("vvfp_story_host_table(void) {"):])
                self.assertIn("command == VVFP_STORY_TIME_SKIP_ID", text)
                self.assertRegex(text, r"#define VV\d_TW_UNITS_PER_YEAR\s+20")

    def test_every_game_offers_it_in_the_catalog(self):
        for game in ALL_GAMES:
            with self.subTest(game=game):
                data = (ROOT / "data" / f"{game}_story_cheat_upgrades_feature.json").read_text(
                    encoding="utf-8")
                self.assertIn("Choose Time Skip Amount", data)
                self.assertIn("1 to 72", data)
                self.assertIn("**Keep the game running", data)

if __name__ == "__main__":
    unittest.main()
