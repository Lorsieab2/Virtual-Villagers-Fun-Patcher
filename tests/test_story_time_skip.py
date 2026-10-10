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
    EVENT_BUF, SCRATCH, TEXT_BUF, Story, emulated, have_stock,
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
        self.slot = 1                  # the save slot the companion reports
        code = proc.alloc(0x100)
        proc.write(code, b"\xC3" * 0x60)
        table = proc.alloc(0x40)
        proc.write(table, struct.pack("<7I", 28, code, code + 0x10, code + 0x20, 0,
                                      code + 0x40, code + 0x50))
        proc.stub(code, lambda p: (self.slot, 0))
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

    def test_a_step_waits_while_an_island_event_is_open(self):
        # Live, The Secret City (2026-10-10): a step taken while The Ants and the Granary's popup
        # was open gave every villager "Age: 694 -> 814" in that event's Island Events record.
        story, host = self.make(step_years=6)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 12, 0)
        self.assertEqual(host.steps, [6])
        story.proc.export("VvfpStoryProbeIslandEventOpen", 1)
        host.settled = True
        for at in range(100, 60000, 1000):    # far past the 20-second lapse
            tick(story, at)
        self.assertEqual(host.steps, [6])     # held while the popup is open
        self.assertEqual(state(story), {"active": 1, "game": 1, "remaining": 6, "waiting": 1})
        story.proc.export("VvfpStoryProbeIslandEventOpen", 0)
        tick(story, 60000)
        self.assertEqual(host.steps, [6, 6])  # closed: the step goes on

    def test_a_popup_outlasting_the_lapse_never_stacks_two_steps(self):
        # The game's villager tick does not run in the presenter's modal loop: the replay wait
        # starts again when the popup closes, not from the step.
        story, host = self.make(step_years=6)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 12, 0)
        story.proc.export("VvfpStoryProbeIslandEventOpen", 1)
        tick(story, 30000)                    # open past the lapse, never settled
        story.proc.export("VvfpStoryProbeIslandEventOpen", 0)
        tick(story, 30100)
        self.assertEqual(host.steps, [6])     # still waiting for the replay
        tick(story, 50000)
        self.assertEqual(host.steps, [6, 6])  # the lapse, counted from the close

    def test_the_closing_popup_waits_while_an_island_event_is_open(self):
        story, host = self.make(step_years=6)
        story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 6, 0)
        story.proc.export("VvfpStoryProbeIslandEventOpen", 1)
        host.settled = True
        tick(story, 100)
        story.proc.export("VvfpStoryProbeTimeSkipNotice", SCRATCH)
        self.assertEqual(struct.unpack("<4i", story.proc.read(SCRATCH, 16))[:2], (6, 1))   # still finishing
        story.proc.export("VvfpStoryProbeIslandEventOpen", 0)
        tick(story, 200)
        story.proc.export("VvfpStoryProbeTimeSkipNotice", SCRATCH)
        self.assertEqual(struct.unpack("<4i", story.proc.read(SCRATCH, 16))[1], 0)          # finished

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


class TimeSkipLabelPriceTests(unittest.TestCase):
    """The button's label shows the price the purchase charges, which is the Time Warp's 50,000 -- not the
    Island Event upgrade's 30,000 (the owner's preview 18 showed 30,000 on A New Home's button)."""

    def test_label_price_equals_the_charge_equals_the_time_warps(self):
        bridge = BRIDGE.read_text(encoding="utf-8")
        inc = SOURCE.read_text(encoding="utf-8")
        # the label is built from the Story DLL's own time skip price, not the event price
        self.assertIn('"VvfpStoryTimeSkipPrice"', bridge)
        self.assertRegex(bridge, r'vvfp_story_label_priced\(game, "Choose Time Skip Amount", label, sizeof label,\s*'
                                 r'vvfp_story_time_skip_price\)')
        self.assertNotRegex(bridge, r'vvfp_story_label\(game, "Choose Time Skip Amount"')
        # ...the export is the charge: purchase prompt, charge and label share time_skip_price
        self.assertIn("VvfpStoryTimeSkipPrice(int game) {\n    return time_skip_price(game);", inc)
        self.assertEqual(inc.count("time_skip_price(game)"), 4)
        self.assertIn("#define TIME_SKIP_PRICE 50000", inc)
        for name in ("vvfp_story_upgrades.def", "vvfp_story_upgrades_test.def"):
            self.assertIn("VvfpStoryTimeSkipPrice=_VvfpStoryTimeSkipPrice@4",
                          (ROOT / "native" / "vvfp_story_upgrades" / name).read_text(encoding="utf-8"))

    @emulated
    def test_the_exported_price_is_the_charge_in_every_game(self):
        for game in ALL_GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = Story(game)
                n = story.n
                # free while the row does not charge (label and charge both 0)
                self.assertEqual(story.proc.export("VvfpStoryTimeSkipPrice", n), 0)
                story.proc.export("VvfpStoryProbeCharges", n, 1)
                price = story.proc.export("VvfpStoryTimeSkipPrice", n)
                self.assertEqual(price, 50000)                                  # the Time Warp's price
                self.assertEqual(price, story.proc.export("VvfpStoryProbeTimeSkipPrice", n))   # == the charge
                self.assertNotEqual(price, story.proc.export("VvfpStoryEventPrice", n))      # not the Island Event's


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


# ---------------------------------------------------------------------------
# The closing popup (the owner, 2026-10-10: "please put an Island-Event style
# popup once the Timeskip has finished")
# ---------------------------------------------------------------------------

# Each game's Island Events Seen counter: (in the world, offset) or a fixed address.
EVENT_COUNTER = {"vv1": ("world", 0x9E40), "vv2": ("world", 0x2E51C), "vv3": (None, 0x5824C4),
                 "vv4": (None, 0x4D6E04), "vv5": (None, 0x51D37C)}
# The trigger's own increment, just before it builds the event (stock bytes).
COUNT_SITES = {
    "vv1": [(va, bytes.fromhex("8b88409e0000415789 88409e0000".replace(" ", "")))
            for va in (0x42392F, 0x423965, 0x4239F2)],
    "vv2": [(va, bytes.fromhex("8b881ce50200415789881ce50200")) for va in (0x42F03F, 0x42F078, 0x42F0E3)],
    "vv3": [(0x468862, bytes.fromhex("8b0dc4245800415689 0dc4245800".replace(" ", "")))],
    "vv4": [(0x43FBD6, bytes.fromhex("8305046e4d0001"))],
    "vv5": [(0x442849, bytes.fromhex("83057cd3510001"))],
}


def notice(story: Story) -> dict:
    story.proc.export("VvfpStoryProbeTimeSkipNotice", SCRATCH)
    done, finishing, years, armed = struct.unpack("<4i", story.proc.read(SCRATCH, 16))
    return {"done": done, "finishing": finishing, "waiting_to_arm": years, "armed": armed}


def counter_address(story: Story) -> int:
    where, off = EVENT_COUNTER[story.game]
    return story.village.world + off if where == "world" else off


def island_ready(story: Story) -> None:
    """No island event is on its way and the game's trigger could show one:
    a living adult, an earlier island event, the countdown far off (as the
    Lock tests' worlds)."""
    from test_story_cheat_upgrades import CLOCK

    p = story.proc
    story.village.put(1, sex="m", years=30, name="Adult")
    if story.game == "vv1":
        p.put32(story.village.world + 0xA300, CLOCK + 36000)
        p.stub(0x402F70, lambda q: (CLOCK, 0))
    elif story.game == "vv2":
        p.put32(story.village.world + 0x2EAE0, CLOCK + 36000)
        p.stub(0x403200, lambda q: (CLOCK, 0))
    elif story.game == "vv3":
        manager = p.alloc(0x13000)
        p.put32(0x4B309C, manager)
        p.write(0x6E0050, b"\0")
        p.stub(0x403330, lambda q: (CLOCK, 0))
    elif story.game == "vv4":
        p.put32(story.village.world + 0x170E0, CLOCK + 36000)
        p.write(0x728B04, bytes(12))
        p.stub(0x403750, lambda q: (CLOCK, 0))
    else:
        p.put32(story.village.world + 0x17D3C, CLOCK + 36000)
        p.put32(0x51D388, 0)
    p.put32(counter_address(story), 5)


def run_skip(story: Story, host: "TimeSkipHost", years: int, *, settle_last: bool = True) -> int:
    """Starts a skip of `years` and replays every step; returns the last tick."""
    assert story.proc.export("VvfpStoryProbeTimeSkipStart", story.n, years, 0) > 0
    at = 0
    for _ in range(100):
        if not state(story)["active"]:
            break
        host.settled = True
        at += 100
        tick(story, at)
    if settle_last:
        host.settled = True
    return at


@emulated
class TimeSkipPopupTests(unittest.TestCase):
    """The game's own island-event popup closes a finished skip, once."""

    def _story(self, game, step_years=6):
        if not have_stock(game):
            self.skipTest(f"stock {game} is not in inputs/")
        story = Story(game)
        island_ready(story)
        return story, TimeSkipHost(story, step_years)

    def test_requested_exactly_once_after_the_last_step_is_replayed(self):
        story, host = self._story("vv1", 6)
        at = run_skip(story, host, 18, settle_last=False)
        self.assertEqual(host.steps, [6, 6, 6])
        # The last step is made but not yet replayed: no popup yet.
        for _ in range(5):
            at += 100
            tick(story, at)
        self.assertEqual(notice(story), {"done": 18, "finishing": 1, "waiting_to_arm": 0, "armed": 0})
        self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", 1), 0)
        host.settled = True
        tick(story, at + 100)
        self.assertEqual(notice(story)["armed"], 1)
        self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", 1), 1)
        self.assertEqual(story.proc.export("VvfpStoryProbePending", 1), 1,
                         "the island event is made due, as the Island Event purchase does")
        # Delivered once by the game's own path; later frames ask for nothing more.
        self.assertEqual(story.proc.export("VvfpStoryProbeDeliver", 1, TEXT_BUF, 4096), 1)
        text = story.proc.cstring(TEXT_BUF)
        self.assertEqual(text, "Time Skip\n\n\n\n18 years have passed on the island.")
        # "VVFP Island Events.dll" asks this so the notice is not logged as an island event.
        self.assertEqual(story.proc.export("VvfpStoryTimeSkipNoticeShown", 1), 1)
        self.assertEqual(story.proc.export("VvfpStoryTimeSkipNoticeShown", 2), 0, "only in its own game")
        for k in range(10):
            tick(story, at + 200 + 100 * k)
        self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", 1), 0)
        self.assertEqual(story.proc.export("VvfpStoryProbeDeliver", 1, TEXT_BUF, 4096), 0)
        self.assertEqual(notice(story)["waiting_to_arm"], 0)

    def test_n_is_the_years_the_skip_advanced(self):
        for years, per_step, words in ((1, 6, "1 year has passed on the island."),
                                       (5, 12, "5 years have passed on the island."),
                                       (13, 6, "13 years have passed on the island."),
                                       (72, 12, "72 years have passed on the island.")):
            with self.subTest(years=years):
                story, host = self._story("vv1", per_step)
                at = run_skip(story, host, years)
                tick(story, at + 100)
                self.assertEqual(sum(host.steps), years)
                self.assertEqual(story.proc.export("VvfpStoryProbeDeliver", 1, TEXT_BUF, 4096), 1)
                self.assertTrue(story.proc.cstring(TEXT_BUF).endswith(words), story.proc.cstring(TEXT_BUF))

    def test_never_after_a_cut_short_skip(self):
        def other_slot(host):
            host.slot = 2

        def start_over(story):
            story.proc.export("VvfpStoryVillageReset", story.n, 1)

        def nobody_left(host):
            host.step_years = 0

        for case in ("another village", "start over", "nobody left"):
            with self.subTest(case=case):
                story, host = self._story("vv1", 6)
                story.proc.export("VvfpStoryProbeTimeSkipStart", 1, 24, 0)
                host.settled = True
                tick(story, 100)                           # a second step
                if case == "another village":
                    other_slot(host)
                elif case == "start over":
                    start_over(story)
                else:
                    nobody_left(host)
                at = 100
                for _ in range(20):
                    host.settled = True
                    at += 100
                    tick(story, at)
                self.assertEqual(state(story)["active"], 0)
                self.assertEqual(notice(story)["armed"], 0)
                self.assertEqual(notice(story)["waiting_to_arm"], 0)
                self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", 1), 0)

    def test_dropped_when_the_village_changes_between_the_last_step_and_the_popup(self):
        story, host = self._story("vv1", 6)
        at = run_skip(story, host, 6, settle_last=False)
        story.proc.export("VvfpStoryVillageReset", 1, 1)
        host.settled = True
        tick(story, at + 100)
        self.assertEqual(notice(story), {"done": 6, "finishing": 0, "waiting_to_arm": 0, "armed": 0})
        self.assertEqual(story.proc.export("VvfpStoryProbeCustomPending", 1), 0)

    def test_waits_its_turn_behind_a_queued_island_event(self):
        story, host = self._story("vv1", 6)
        story.proc.export("VvfpStoryProbeArm", 1, 0, 0)    # a Pick Island Event is on its way
        at = run_skip(story, host, 6)
        tick(story, at + 100)
        self.assertEqual(notice(story)["waiting_to_arm"], 6)
        self.assertEqual(notice(story)["armed"], 0)
        self.assertEqual(story.proc.export("VvfpStoryProbeArmedSlot"), 0, "the pick is left alone")

    def test_waits_while_the_game_could_not_show_it(self):
        """A New Home: the village's first island event is always a visitor."""
        story, host = self._story("vv1", 6)
        story.proc.put32(counter_address(story), 0)
        at = run_skip(story, host, 6)
        tick(story, at + 100)
        self.assertEqual(notice(story)["waiting_to_arm"], 6)
        story.proc.put32(counter_address(story), 1)       # the first event has happened
        tick(story, at + 200)
        self.assertEqual(notice(story)["armed"], 1)

    def test_a_players_custom_event_is_never_taken_for_the_notice(self):
        story, host = self._story("vv1", 6)
        from story_custom_fixtures import Event

        story.proc.write(EVENT_BUF, Event(game=1, title="Rain", text="It rained.").pack())
        self.assertEqual(story.proc.export("VvfpStoryProbeQueueCustom", 1, EVENT_BUF, 0), 1)
        self.assertEqual(notice(story)["armed"], 0)
        before = story.proc.u32(counter_address(story))
        self.assertEqual(story.proc.export("VvfpStoryProbeDeliver", 1, TEXT_BUF, 4096), 1)
        self.assertEqual(story.proc.u32(counter_address(story)), before, "a real island event counts")
        self.assertEqual(story.proc.export("VvfpStoryTimeSkipNoticeShown", 1), 0, "and is logged as one")

    def test_every_game_routes_it_to_its_own_island_event_popup(self):
        """VV1 / VV2: the island event's chooser call writes the popup text
        into the event object's own buffer; VV3-VV5: the presenter is handed
        the custom event object whose title and body come through the game's
        own string lookup.  The trigger's count of it is taken back."""
        from test_story_custom_island_event import CHOOSER, HEAP as EMU_HEAP, SELECT

        for game in ALL_GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                story = Story(game)
                island_ready(story)
                host = TimeSkipHost(story, 6)
                p = story.proc
                at = run_skip(story, host, 12)
                tick(story, at + 100)
                self.assertEqual(notice(story)["armed"], 1)
                p.put32(counter_address(story), 6)        # the trigger has counted it (5 + 1)
                if game in CHOOSER:
                    site, resume, chooser = CHOOSER[game]
                    story.record_call(chooser, 8)
                    obj = p.alloc(0x5100)
                    esp = EMU_HEAP + 0x3000000
                    p.put32(esp, 2)
                    p.put32(esp + 4, 6)
                    p.set_reg("esp", esp)
                    p.set_reg("ecx", obj)
                    p.set_reg("esi", obj)
                    p.set_reg("ebp", obj + 0x277F)
                    p.run(site, resume)
                    self.assertNotIn(chooser, story.calls, "the game's own choice is not made")
                    self.assertEqual(p.cstring(obj + 0x277F),
                                     "Time Skip\n\n\n\n12 years have passed on the island.")
                else:
                    table, site, resume, register, lookup, strings, title_id, body_id = SELECT[game]
                    for slot in range(1, 58):
                        p.put32(table + 4 * slot, p.alloc(0x20))
                    p.set_reg("esi", 5)
                    p.set_reg("esp", EMU_HEAP + 0x3000000)
                    p.run(site, resume)
                    obj = p.reg(register)
                    self.assertEqual(obj, p.export("VvfpStoryProbeObject"))
                    vtable = p.u32(obj)
                    title = p.call(p.u32(vtable + 8), [], ecx=obj)
                    body = p.call(p.u32(vtable + 0xC), [], ecx=obj)
                    self.assertEqual(p.cstring(p.call(lookup, [title])), "Time Skip")
                    self.assertEqual(p.cstring(p.call(lookup, [body])), "12 years have passed on the island.")
                self.assertEqual(p.u32(counter_address(story)), 5, "Island Events Seen is not raised by it")
                self.assertEqual(p.export("VvfpStoryProbeCustomPending", story.n), 0, "shown once")


@emulated
class TimeSkipPopupModesTests(unittest.TestCase):
    """The trigger increments the Island Events Seen counter with the stock
    bytes the companion checks, in all three population modes."""

    def test_the_count_sites_are_stock_in_every_mode(self):
        from test_story_custom_island_event import MODES, Process, TEST_DLL, render

        for game in ALL_GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                try:
                    data = render(game, mode)
                except Exception as error:  # a mode the game does not offer
                    if mode == "immediate_fixed":
                        continue
                    raise error
                proc = Process(data, TEST_DLL)
                for va, raw in COUNT_SITES[game]:
                    with self.subTest(game=game, mode=mode, site=hex(va)):
                        self.assertEqual(proc.read(va, len(raw)), raw)


class StaticTimeSkipPopupTests(unittest.TestCase):
    def test_the_count_sites_match_the_companions_table(self):
        text = (ROOT / "native" / "vvfp_story_upgrades" / "story_custom.inc").read_text(encoding="utf-8")
        table = text[text.index("static const ce_count_site CE_COUNT_SITES[] = {"):]
        table = table[:table.index("};")]
        for game, sites in COUNT_SITES.items():
            for va, raw in sites:
                with self.subTest(game=game, site=hex(va)):
                    listed = ", ".join(f"0x{b:02X}" for b in raw)
                    self.assertIn(f"{{ {game[2:]}, 0x{va:06X}u, {{ {listed} }}, {len(raw)} }}", table)

    def test_the_counter_is_taken_back_only_for_the_notice(self):
        text = (ROOT / "native" / "vvfp_story_upgrades" / "story_custom.inc").read_text(encoding="utf-8")
        body = text[text.index("static int ce_deliver(int game, char *text, int size) {"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("notice = ce_armed_is_notice;", body)
        self.assertIn("if (notice) {\n        ce_uncount_notice(game);", body)

    def test_no_log_is_written_for_it(self):
        inc = SOURCE.read_text(encoding="utf-8")
        popup = inc[inc.index("static int time_skip_notice_arm("):inc.index("/* One step of the skip")]
        for writer in ("WriteVillageRecord", "WriteVillageEventRecord", "story_log", "fopen", "CreateFile"):
            self.assertNotIn(writer, popup)
        self.assertIn('lstrcpynA(e->title, "Time Skip", sizeof e->title);', popup)


if __name__ == "__main__":
    unittest.main()
