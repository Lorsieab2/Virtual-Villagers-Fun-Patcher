"""Story / Cheat Upgrades: The Secret City's Recharge Chief Powers.

The owner (2026-10-20): "add an equivalent 'Recharge Chief Powers' in the
Upgrades menu that makes the chief's powers available immediately after
purchase, with the same tech point cost."  The equivalent is The Lost
Children's Pick Gong of Wonder Outcome (which makes the Gong ready to ring at
once): charged through the same story_charged path, at the Island Event
upgrade's price -- 0, or 30,000 with "Story / Cheat Upgrades cost Tech
Points".

The chief's three once-a-day powers keep their next-use clock time in the
world object (0x428B60()): +0x12F00 food (0x421A30), +0x12EFC lessons
(0x466828), +0x12EF8 rare collectible (0x421BE0).  A use rests while the
stamp is ahead of the clock 0x403330 and then writes clock + 0x14370; the
robe's success 0x431FE0 writes the game's own ready value 0 to all three.

These tests run the shipped test build of the Story companion beside the
rendered executable (all three population modes) in the emulator, and the
game's own power routines afterwards.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

from test_story_custom_island_event import MODES, Story, emulated, have_stock

try:
    from story_emulator import HEAP
except ImportError:  # pragma: no cover - environment dependent
    HEAP = 0

ROOT = Path(__file__).resolve().parents[1]
C3 = ROOT / "native" / "vvfp_story_upgrades" / "story_c3.inc"
COMPANION = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
OUTCOMES_UI = ROOT / "native" / "vvfp_story_upgrades" / "story_outcomes_ui.inc"
DEF = ROOT / "native" / "vvfp_story_upgrades" / "vvfp_story_upgrades.def"
TEST_DEF = ROOT / "native" / "vvfp_story_upgrades" / "vvfp_story_upgrades_test.def"

CLOCK = 1_700_000_000
REST = 0x14370                        # 23 hours: what each use adds to the clock
FOOD, LESSONS, COLLECTIBLE = 0x12F00, 0x12EFC, 0x12EF8
STAMPS = (FOOD, LESSONS, COLLECTIBLE)
LEADERSHIP = 0x582618 + 4 * 4         # technology 4, read by 0x426FC0(4)
TECH = 0x582644                       # the village's tech points
CHIEF_BYTE = 0xE80
ISLAND_EVENT_PRICE = 30000
IDOK, IDCANCEL = 1, 2


def make(mode: str = "collection_progression", *, chief: bool = True, leadership: int = 3,
         stamps=(CLOCK + 5000, CLOCK + 6000, CLOCK + 7000), tech: int = 0,
         charged: bool = False) -> tuple[Story, int]:
    story = Story("vv3", mode)
    p = story.proc
    world = p.alloc(0x13000)
    p.put32(0x4B309C, world)
    p.stub(0x428B60, lambda q: (world, 0))
    p.stub(0x403330, lambda q: (CLOCK, 0))
    story.village.put(0, sex="m", years=30, name="Kai")
    story.village.put(1, sex="f", years=8, name="Lani")
    if chief:
        p.write(story.village.record(0) + CHIEF_BYTE, b"\1")
    p.put32(LEADERSHIP, leadership)
    for off, value in zip(STAMPS, stamps):
        p.put32(world + off, value)
    p.put32(TECH, tech)
    if charged:
        p.export("VvfpStoryProbeCharges", 3, 1)
    return story, world


def stamps(story: Story, world: int) -> tuple[int, ...]:
    return tuple(story.proc.u32(world + off) for off in STAMPS)


def buy(story: Story) -> int:
    return story.proc.export("VvfpStoryRechargeChiefPowers", 3, 0)


@emulated
@unittest.skipUnless(have_stock("vv3"), "stock The Secret City is not in inputs/")
class RechargeTests(unittest.TestCase):
    def test_every_chief_power_is_ready_after_the_purchase_in_every_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                story, world = make(mode)
                self.assertEqual(buy(story), 1)
                self.assertEqual(stamps(story, world), (0, 0, 0))
                self.assertEqual(story.proc.u32(TECH), 0, "free: nothing charged")
                self.assertIn("Do you want to buy Recharge Chief Powers for 0 tech points?",
                              story.proc.messages[0])
                self.assertIn("ready to use now", story.proc.messages[-1])

    def test_only_a_resting_power_is_written(self):
        story, world = make(stamps=(CLOCK - 10, CLOCK + 6000, CLOCK))
        self.assertEqual(buy(story), 1)
        self.assertEqual(stamps(story, world), (CLOCK - 10, 0, CLOCK))

    def test_no_chief_writes_nothing_and_charges_nothing(self):
        for charged in (False, True):
            with self.subTest(charged=charged):
                story, world = make(chief=False, tech=100000, charged=charged)
                before = stamps(story, world)
                self.assertEqual(buy(story), 0)
                self.assertEqual(stamps(story, world), before)
                self.assertEqual(story.proc.u32(TECH), 100000)
                self.assertIn("no Tribal Chief", story.proc.messages[-1])
                self.assertFalse(any("Do you want to buy" in m for m in story.proc.messages))

    def test_a_dead_chief_is_no_chief(self):
        story, world = make(tech=100000, charged=True)
        story.proc.put32(story.village.record(0) + 0xE78, 0)     # health 0: a skeleton
        before = stamps(story, world)
        self.assertEqual(buy(story), 0)
        self.assertEqual(stamps(story, world), before)
        self.assertEqual(story.proc.u32(TECH), 100000)

    def test_a_chief_without_leadership_has_no_powers_yet(self):
        story, world = make(leadership=0, tech=100000, charged=True)
        before = stamps(story, world)
        self.assertEqual(buy(story), 0)
        self.assertEqual(stamps(story, world), before)
        self.assertEqual(story.proc.u32(TECH), 100000)
        self.assertIn("no powers yet", story.proc.messages[-1])

    def test_every_power_ready_already_is_nothing_to_buy(self):
        story, world = make(stamps=(CLOCK, 0, CLOCK - 1), tech=100000, charged=True)
        self.assertEqual(buy(story), 0)
        self.assertEqual(stamps(story, world), (CLOCK, 0, CLOCK - 1))
        self.assertEqual(story.proc.u32(TECH), 100000)
        self.assertIn("ready to use already", story.proc.messages[-1])

    def test_cancel_writes_nothing_and_charges_nothing(self):
        story, world = make(tech=100000, charged=True)
        story.proc.message_answer = IDCANCEL
        before = stamps(story, world)
        self.assertEqual(buy(story), 0)
        self.assertEqual(stamps(story, world), before)
        self.assertEqual(story.proc.u32(TECH), 100000)


@emulated
@unittest.skipUnless(have_stock("vv3"), "stock The Secret City is not in inputs/")
class PriceTests(unittest.TestCase):
    """Both pricing variants, at the price Pick Gong of Wonder Outcome and the
    island event purchases charge (VvfpStoryEventPrice)."""

    def test_free_variant_costs_zero(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                story, world = make(mode, tech=12345)
                self.assertEqual(story.proc.export("VvfpStoryEventPrice", 3), 0)
                self.assertEqual(buy(story), 1)
                self.assertEqual(story.proc.u32(TECH), 12345)

    def test_cost_variant_charges_the_island_event_price_once(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                story, world = make(mode, tech=40000, charged=True)
                price = story.proc.export("VvfpStoryEventPrice", 3)
                self.assertEqual(price, ISLAND_EVENT_PRICE)
                self.assertEqual(buy(story), 1)
                self.assertEqual(stamps(story, world), (0, 0, 0))
                self.assertEqual(story.proc.u32(TECH), 40000 - price)
                self.assertIn("for 30,000 tech points?", story.proc.messages[0])

    def test_cost_variant_with_too_few_tech_points_is_refused_untouched(self):
        story, world = make(tech=ISLAND_EVENT_PRICE - 1, charged=True)
        before = stamps(story, world)
        self.assertEqual(buy(story), 0)
        self.assertEqual(stamps(story, world), before)
        self.assertEqual(story.proc.u32(TECH), ISLAND_EVENT_PRICE - 1)
        self.assertIn("This costs 30,000 tech points", story.proc.messages[-1])

    def test_priced_exactly_as_pick_gong_of_wonder_outcome(self):
        """The same charge path and price function as the Gong's purchase."""
        c3 = C3.read_text(encoding="utf-8")
        self.assertIn("return story_charged(game, owner, story_recharge_chief_powers);", c3)
        gong = OUTCOMES_UI.read_text(encoding="utf-8")
        self.assertIn("return story_charged(game, owner, story_pick_gong_outcome);", gong)
        self.assertIn("story_price_text(game)", c3)


@emulated
@unittest.skipUnless(have_stock("vv3"), "stock The Secret City is not in inputs/")
class StockUseAfterwardsTests(unittest.TestCase):
    """After the purchase each power runs through the game's own routine and
    rests again for 0x14370 seconds, as it always does."""

    def _record_actions(self, story: Story) -> list[int]:
        actions: list[int] = []

        def do_action(q):
            actions.append(q.arg(0))
            return 0, 8
        story.proc.stub(0x455570, do_action)
        story.proc.stub(0x460F70, lambda q: (0, 4))
        return actions

    def _hotspot(self, routine: int, stamp: int, power_action: int):
        story, world = make()
        self.assertEqual(buy(story), 1)
        actions = self._record_actions(story)
        chief = story.village.record(0)
        story.proc.call(routine, [chief])
        self.assertEqual(actions, [power_action], "the power runs")
        self.assertEqual(story.proc.u32(world + stamp), CLOCK + REST, "and rests again")
        story.proc.call(routine, [chief])
        self.assertEqual(actions[-1], 0x72, "a second use the same day is refused")
        self.assertEqual(story.proc.u32(world + stamp), CLOCK + REST)

    def test_granting_food(self):
        self._hotspot(0x421A30, FOOD, 0x87)

    def test_pointing_out_a_rare_collectible(self):
        self._hotspot(0x421BE0, COLLECTIBLE, 0x89)

    def test_educating_the_children(self):
        story, world = make()
        self.assertEqual(buy(story), 1)
        p = story.proc
        actions = self._record_actions(story)
        p.stub(0x45D460, lambda q: (0, 0x10))
        p.stub(0x45E0C0, lambda q: (0, 0x10))
        holder = p.alloc(0x20)
        p.put32(holder + 0x10, world)
        stack = HEAP + 0x3000000
        p.set_reg("esp", stack)
        p.write(stack, bytes(0x40))
        p.set_reg("esi", story.village.record(0))
        p.set_reg("ebx", holder)
        p.run(0x466836, 0x4668DA)
        self.assertIn(0x39, actions, "the lesson runs")
        self.assertEqual(p.u32(world + LESSONS), CLOCK + REST, "and rests again")


class StaticTests(unittest.TestCase):
    def test_the_purchase_writes_the_robes_own_ready_value(self):
        c3 = C3.read_text(encoding="utf-8")
        self.assertIn("{ 0x12F00u, 0x12EFCu, 0x12EF8u }", c3)
        self.assertIn("*(unsigned int *)(world + C3_CHIEF_POWER_STAMPS[k]) = 0;", c3)
        self.assertIn("0x45FC00u", c3)

    def test_the_export_is_in_both_builds(self):
        for path in (DEF, TEST_DEF):
            self.assertIn("VvfpStoryRechargeChiefPowers=_VvfpStoryRechargeChiefPowers@8",
                          path.read_text(encoding="utf-8"))

    def test_the_vv3_tech_menu_offers_the_button_without_the_island_lock(self):
        src = COMPANION.read_text(encoding="utf-8")
        self.assertIn('vvfp_story_label(3, "Recharge Chief Powers"', src)
        self.assertIn('"VvfpStoryRechargeChiefPowers"', src)
        self.assertIn("vv3_story_add_recharge_button(window);", src)
        handler = src[src.index("if (command == VV3_STORY_RECHARGE_ID)"):]
        handler = handler[:handler.index("return TRUE;")]
        self.assertNotIn("vv3_row_block_reason", handler)
        self.assertTrue(re.search(r"#define VV3_STORY_RECHARGE_ID 4094\b", src))


if __name__ == "__main__":
    unittest.main()
