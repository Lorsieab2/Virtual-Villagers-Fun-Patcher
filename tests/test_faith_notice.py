"""Popup When Believers Become Heathens (New Believers).

The owner (2026-11-08): "When my villagers turn into heathens due to faith decreases: the bottom bar should say "a
villager has left the tribe!" or whatever the message is" and "There should be a popup too: (NUMBER) villagers have
stopped believing in you because of: (REASONS)".

* The bottom bar: the stock to-a-Heathen routine 0x4669E0 already says the game's own string 0x48
  (eSayStoppedBelieving) on every conversion; checked on the stock executable and its string table.
* "VVFP Faith Notice.dll" (the shipped DLL) runs in the emulator beside New Believers' executable, stock and with
  Faith Loss is Doubled/Gains Halved: the life tick's call of the Faith drift 0x468040 (0x472D17) is run with the
  game's own drift code, the game routines it asks stubbed, and the conversions and their reasons are read back
  through the companion's exports -- and the drift's own random numbers and result are the same with it as without.
* "VVFP Story Upgrades.test.dll" composes and arms the popup (story_faith_notice.inc), in both wordings, and waits
  its turn.
"""
from __future__ import annotations

import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
from vv_fun_patcher_gui import default_fun_patch_selection  # noqa: E402

try:
    import pefile
    from story_emulator import Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

_spec = importlib.util.spec_from_file_location("build_faith_notice_feature",
                                               ROOT / "scripts" / "build_faith_notice_feature.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

DLL = ROOT / "assets" / "faith_notice" / "VVFP Faith Notice.dll"
STOCK = ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe"
FAITH_LOSS = "vv5_faith_loss_doubled_gains_halved"

LIFE_CALL, AFTER_CALL = 0x472D17, 0x472D1C
RAND, PROJECT_DONE, STATUE_STAGE, TECH, BELIEVERS, MANAGER_OF = (0x403660, 0x43AE80, 0x4271C0, 0x423600, 0x4713F0,
                                                                 0x425950)
TO_HEATHEN, TO_BELIEVER, FOOD = 0x4669E0, 0x4668B0, 0x51D34C
# The companion's reasons, in VvfpFaithNoticePending's out[1..5].
STARVATION, HUNGER, SICKNESS, BELIEVERS, OTHER = range(5)


def only(*reasons: int) -> tuple:
    """The five counts for one conversion each of `reasons`."""
    counts = [0] * 5
    for r in reasons:
        counts[r] += 1
    return tuple(counts)

_renders: dict = {}


def build():
    return next(b for b in patcher.load_builds() if b.id == "vv5")


def rendered(ids: tuple) -> bytes:
    if not STOCK.is_file():
        raise unittest.SkipTest("stock New Believers is not in inputs/")
    if ids not in _renders:
        _renders[ids] = STOCK.read_bytes() if not ids else bytes(
            patcher.render_patched_bytes(STOCK, build(), patcher.DEFAULT_PATCH_MODE, list(ids))[0])
    return _renders[ids]


class Village:
    """New Believers' executable (and the companion, when `dll`) with one villager record and the game routines
    the drift asks stubbed.  rand gives `rolls` in order, then 99."""

    def __init__(self, exe: bytes, *, dll: bool = True):
        self.proc = Process(exe, DLL if dll else None)
        p = self.proc
        if dll:
            p.export("VvfpStartup", 5, 0)
        self.record = p.alloc(0x3000)
        self.game = p.alloc(0x20000)
        p.write(self.game + 0x17E39, b"\x01")           # the island runs: the setter converts
        self.rolls: list[int] = []
        self.drawn: list[int] = []
        self.food = 1000
        self.believers = 20

        def rand(q):
            value = self.rolls.pop(0) if self.rolls else 99
            self.drawn.append((q.arg(0), value))
            return value % q.arg(0), 0

        def to_heathen(q):
            q.write(q.reg("ecx") + 0x1CEC, b"\x01")
            return 0, 0
        p.stub(RAND, rand)
        p.stub(PROJECT_DONE, lambda q: (0, 4))
        p.stub(STATUE_STAGE, lambda q: (0, 0))
        p.stub(TECH, lambda q: (0, 4))
        p.stub(BELIEVERS, lambda q: (self.believers, 0))
        p.stub(MANAGER_OF, lambda q: (self.game, 0))
        p.stub(TO_HEATHEN, to_heathen)
        p.stub(TO_BELIEVER, lambda q: (0, 0))

    def drift(self, *, faith: int, rolls=(), food=None, sick=0, believers=None, heathen=0) -> int:
        """One age unit's drift through the life tick's call: the record's Faith after it."""
        p = self.proc
        self.rolls = list(rolls)
        if food is not None:
            self.food = food
        if believers is not None:
            self.believers = believers
        p.put32(FOOD, self.food)
        p.put32(self.record + 0x1CF0, faith)
        p.write(self.record + 0x1C48, bytes([sick]))
        p.write(self.record + 0x1CEC, bytes([heathen]))
        p.call(LIFE_CALL, ecx=self.record, until=AFTER_CALL)
        return struct.unpack("<i", p.read(self.record + 0x1CF0, 4))[0]

    def heathen(self) -> bool:
        return self.proc.read(self.record + 0x1CEC, 1) != b"\0"

    def slot(self, slot: int) -> None:
        """The save slot the game's save manager says (native/shared/game_save_slot.h: [0x4DACE0] + 0x17D80)."""
        p = self.proc
        if not hasattr(self, "_manager"):
            self._manager = p.alloc(0x20000)
            p.put32(0x4DACE0, self._manager)
        p.put32(self._manager + 0x17D80, slot)

    def pending(self, tick: int):
        """(count, reasons) when the popup may come at `tick`, else None."""
        p = self.proc
        p.tick = tick
        out = p.alloc(32)
        if not p.export("VvfpFaithNoticePending", 5, out):
            return None
        values = struct.unpack("<6I", p.read(out, 24))
        return values[0], values[1:]


def skip_without_emulator(cls):
    return unittest.skipUnless(HAVE_EMULATOR, "unicorn/pefile not installed")(
        unittest.skipUnless(DLL.is_file(), "the companion is not built")(cls))


class Manifest(unittest.TestCase):
    def test_the_manifest_is_the_generators(self):
        path = ROOT / "data" / "vv5_heathen_conversion_notice_feature.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), gen.feature())

    def test_on_by_default_registered_and_documented(self):
        rows = {p.id: p for p in patcher.load_public_fun_patches()}
        self.assertIn(gen.NOTICE_ID, rows)
        self.assertTrue(default_fun_patch_selection(gen.NOTICE_ID))
        self.assertIn("VVFP Faith Notice.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP Faith Notice.dll"', header)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"assets/faith_notice/VVFP Faith Notice.dll"', release)
        self.assertIn('"data/vv5_heathen_conversion_notice_feature.json"', release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"- Patch ID: `{gen.NOTICE_ID}`", readme)
        howto = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        self.assertIn(gen.NOTICE_ID, {i for entry in howto["patches"] for i in entry.get("ids", [])})

    def test_the_story_companion_asks_this_companions_exports(self):
        story = (ROOT / "native" / "vvfp_story_upgrades" / "story_faith_notice.inc").read_text(encoding="utf-8")
        exports = (ROOT / "native" / "vvfp_faith_notice" / "vvfp_faith_notice.def").read_text(encoding="utf-8")
        for name in ("VvfpFaithNoticePending", "VvfpFaithNoticeTaken"):
            self.assertIn(f'"{name}"', story)
            self.assertIn(name, exports)
        self.assertIn('GetModuleHandleA("VVFP Faith Notice.dll")', story)


@unittest.skipUnless(HAVE_EMULATOR, "unicorn/pefile not installed")
class BottomBar(unittest.TestCase):
    def test_the_stock_game_already_says_eSayStoppedBelieving_on_every_conversion(self):
        """0x4669E0 -- the setter 0x467F90's one way to a Heathen (0x467FDF) -- says string 0x48 through the say bar
        0x520F68 (0x44EF60) first thing; string 0x48 is eSayStoppedBelieving in the exe's own string table."""
        image = pefile.PE(data=rendered(()), fast_load=True).get_memory_mapped_image()
        at = lambda va, n: bytes(image[va - 0x400000:va - 0x400000 + n])  # noqa: E731
        self.assertEqual(at(0x4669E1, 16), bytes.fromhex("6AFF8BF16A48B9680F5200E86F85FEFF"),
                         "push -1; mov esi,ecx; push 0x48; mov ecx,0x520F68; call 0x44EF60")
        self.assertEqual(at(0x467FDF, 5), bytes.fromhex("E8FCE9FFFF"), "the setter calls 0x4669E0")
        entry = 0x4D3660
        self.assertEqual(struct.unpack("<I", at(entry, 4))[0], 0x48)
        name, text = struct.unpack("<2I", at(entry + 4, 8))
        self.assertEqual(at(name, 21), b"eSayStoppedBelieving\0")
        self.assertEqual(at(text, 41), b"A villager has stopped believing in you!\0")
        isola = (ROOT / "data" / "guardians_of_isola" / "new" / "Assets" / "sm.xml").read_text(encoding="utf-8")
        at_id = isola.index('<Text id="eSayStoppedBelieving">')
        self.assertIn("A villager has left the tribe!", isola[at_id:at_id + 120])


@skip_without_emulator
class FaithNoticeCompanion(unittest.TestCase):
    def test_installs_its_five_calls(self):
        v = Village(rendered(()))
        self.assertEqual(v.proc.export("VvfpFaithNoticeInstalled"), 1)
        for va, stock, _ in gen.SITES:
            got = v.proc.read(va, 5)
            self.assertEqual(got[0], 0xE8)
            target = (va + 5 + struct.unpack("<i", got[1:])[0]) & 0xFFFFFFFF
            self.assertTrue(v.proc.dll_base <= target < v.proc.dll_base + v.proc.dll_size, hex(va))
        for exe in (rendered((FAITH_LOSS,)), rendered(("vv5_new_heathens_get_heathen_faith",))):
            self.assertEqual(Village(exe).proc.export("VvfpFaithNoticeInstalled"), 1)

    def test_not_installed_in_another_game_or_on_unknown_bytes(self):
        proc = Process(rendered(()), DLL)
        proc.export("VvfpStartup", 4, 0)
        self.assertEqual(proc.export("VvfpFaithNoticeInstalled"), 0)
        proc = Process(rendered(()), DLL)
        proc.write(0x46805B - 2, b"\x90\x90")        # a threshold the companion cannot read
        before = proc.read(0x472D17, 5)
        proc.export("VvfpStartup", 5, 0)
        self.assertEqual(proc.export("VvfpFaithNoticeInstalled"), 0)
        self.assertEqual(proc.read(0x472D17, 5), before, "nothing written")

    def test_each_reason_is_the_roll_that_hit(self):
        stock = rendered(())
        cases = (
            ("food under 10", dict(food=5, rolls=[0]), STARVATION),
            ("food 10 to 250", dict(food=100, rolls=[0]), HUNGER),
            ("food under 10, its second roll", dict(food=5, rolls=[50, 0]), STARVATION),
            ("sickness", dict(sick=1, rolls=[0]), SICKNESS),
            ("too few believers", dict(believers=3, rolls=[0]), BELIEVERS),
            ("food and too few believers: the food first", dict(food=100, believers=3, rolls=[0, 0]), HUNGER),
            ("sickness, food missed", dict(food=100, sick=1, rolls=[50, 0]), SICKNESS),
        )
        for name, case, reasons in cases:
            with self.subTest(name):
                v = Village(stock)
                self.assertLessEqual(v.drift(faith=1, **case), 0)
                self.assertTrue(v.heathen())
                self.assertIsNone(v.pending(0), "it waits for the quiet")
                self.assertEqual(v.pending(gen_quiet()), (1, only(reasons)))

    def test_island_event_conversions_are_never_counted(self):
        """Only the Faith drift's conversions bring the popup.  The Spa and The Cracked Mask call the setter with -10
        themselves (0x415D02, 0x416C51), the Custom Island Event's "Becomes a Heathen" calls 0x4669E0 itself
        (story_c5.inc c5_set_status): none of them inside the life tick's drift call, so none is counted -- nor is a
        Heathen the creator 0x46FD20 makes for an island event, a barrel or the Story / Cheat Upgrades (never a
        believer)."""
        v = Village(rendered(()))
        p = v.proc
        p.put32(v.record + 0x1CF0, 10)
        p.call(0x467F90, [0xFFFFFFF6, 1], ecx=v.record)     # The Spa / The Cracked Mask: SetFaith(-10, 1)
        self.assertTrue(v.heathen())
        p.write(v.record + 0x1CEC, b"\0")
        p.call(TO_HEATHEN, ecx=v.record)                    # the Custom Island Event's "Becomes a Heathen"
        self.assertTrue(v.heathen())
        self.assertIsNone(v.pending(100000))
        v.drift(faith=1, food=100, rolls=[0])               # the drift's own: counted
        self.assertEqual(v.pending(200000), (1, only(HUNGER)))
        island = (ROOT / "native" / "vvfp_story_upgrades" / "story_c5.inc").read_text(encoding="utf-8")
        self.assertIn("TC0(0x4669E0u, r);", island)
        self.assertIn("TC9(0x46FD20u, C5_MANAGER", island)

    def test_a_batch_belongs_to_its_village(self):
        """Codex (#732): the counts of one village never show in another's popup.  Loading another slot before the
        popup -- in the quiet wait, or while another event holds it -- drops the batch; a conversion in the new
        village starts its own; Start Over or a deleted tribe (VvfpFaithNoticeVillageReset, from VVFP Story
        Upgrades.dll's VvfpStoryVillageReset) drops it too."""
        v = Village(rendered(()))
        quiet = gen_quiet()
        v.slot(1)
        v.proc.tick = 1000
        v.drift(faith=1, food=100, rolls=[0])
        v.slot(2)                                           # another village loaded during the wait
        self.assertIsNone(v.pending(1000 + quiet))
        v.slot(1)
        self.assertIsNone(v.pending(1000 + quiet), "dropped, not kept for when slot 1 comes back")
        v.proc.tick = 5000
        v.drift(faith=1, food=100, rolls=[0])               # slot 1: a new batch
        v.slot(2)
        v.proc.tick = 5010
        v.drift(faith=1, sick=1, food=1000, rolls=[0])      # slot 2's own conversion: slot 1's batch is not added
        self.assertEqual(v.pending(5010 + quiet), (1, only(SICKNESS)))
        v.proc.export("VvfpFaithNoticeTaken", 5)
        v.proc.tick = 9000
        v.drift(faith=1, food=100, rolls=[0])
        v.proc.export("VvfpFaithNoticeVillageReset", 5)     # Start Over in the same slot
        self.assertIsNone(v.pending(9000 + quiet))
        v.proc.tick = 12000
        v.drift(faith=1, food=100, rolls=[0])               # the new tribe's own
        self.assertEqual(v.pending(12000 + quiet), (1, only(HUNGER)))

    def test_no_conversion_counts_nothing(self):
        v = Village(rendered(()))
        self.assertEqual(v.drift(faith=5, food=100, rolls=[0]), 4)
        self.assertEqual(v.drift(faith=50, food=9000, rolls=[0]), 51)
        # The food roll, the believers' roll (20 believers: a gain on < 4), then stock's 50% skip below Faith 5.
        self.assertEqual(v.drift(faith=1, food=100, rolls=[0, 99, 10]), 1, "stock's 50% skip below Faith 5")
        self.assertFalse(v.heathen())
        self.assertIsNone(v.pending(100000))

    def test_a_catch_up_is_one_popup_after_the_quiet(self):
        v = Village(rendered(()))
        quiet = gen_quiet()
        for k, case in enumerate((dict(food=100, rolls=[0]), dict(sick=1, food=1000, rolls=[0]),
                                  dict(food=1000, believers=4, rolls=[0]))):
            v.proc.tick = 1000 + 10 * k
            v.drift(faith=1, **case)
        self.assertIsNone(v.pending(1020 + quiet - 1))
        self.assertEqual(v.pending(1020 + quiet), (3, only(HUNGER, SICKNESS, BELIEVERS)))
        v.proc.export("VvfpFaithNoticeTaken", 5)
        self.assertIsNone(v.pending(1020 + 10 * quiet), "taken: counting starts again")
        v.proc.tick = 50000
        v.drift(faith=1, food=100, rolls=[0])
        self.assertEqual(v.pending(50000 + quiet), (1, only(HUNGER)))
        v.proc.export("VvfpFaithNoticeTaken", 4)
        self.assertEqual(v.pending(50000 + quiet), (1, only(HUNGER)), "another game's Taken is ignored")

    def test_with_faith_loss_the_reasons_follow_the_doubled_thresholds(self):
        """A roll of 15 hits food 10..250 only with Faith Loss (< 20; stock < 10); a believers roll of 15 with 4
        believers hits only with Faith Loss (< 16; stock < 8).  The rolls in the drift's order: food, the believers'
        roll, then (stock) the skip below Faith 5 or (Faith Loss, a food fall to 0) the 3-in-10 roll."""
        for ids, hits in (((), False), ((FAITH_LOSS,), True)):
            with self.subTest(ids=ids):
                for case, reason in ((dict(food=100, rolls=[15, 99, 0]), HUNGER),
                                     (dict(food=1000, believers=4, rolls=[15, 99]), BELIEVERS)):
                    v = Village(rendered(ids))
                    after = v.drift(faith=1, **case)
                    if hits:
                        self.assertTrue(v.heathen(), case)
                        self.assertEqual(v.pending(gen_quiet()), (1, only(reason)))
                    else:
                        self.assertEqual(after, 1, case)
                        self.assertIsNone(v.pending(gen_quiet()))

    def test_faith_losss_nine_in_ten_keep_the_believer_and_count_nothing(self):
        v = Village(rendered((FAITH_LOSS,)))
        # The food roll, the believers' roll, then the 3-in-10 roll: rand(10) = 5, the believer stays at Faith 1.
        self.assertEqual(v.drift(faith=1, food=100, rolls=[0, 99, 5]), 1)
        self.assertFalse(v.heathen())
        self.assertIsNone(v.pending(100000))
        self.assertEqual(v.drift(faith=1, food=100, rolls=[0, 99, 0]), 0)    # rand(10) = 0: becomes a Heathen
        self.assertTrue(v.heathen())

    def test_the_drift_draws_and_moves_exactly_as_without_the_companion(self):
        import random
        rng = random.Random(5)
        for ids in ((), (FAITH_LOSS,)):
            exe = rendered(ids)
            with_dll, without = Village(exe), Village(exe, dll=False)
            for _ in range(60):
                case = dict(faith=rng.choice((1, 2, 3, 30, 80)), food=rng.choice((5, 100, 1000, 9000)),
                            sick=rng.choice((0, 1)), believers=rng.choice((1, 6, 11, 12, 40)),
                            rolls=[rng.randrange(100) for _ in range(12)])
                with self.subTest(ids=ids, case=case):
                    with_dll.drawn.clear()
                    without.drawn.clear()
                    a = with_dll.drift(**case)
                    b = without.drift(**case)
                    self.assertEqual(a, b)
                    self.assertEqual(with_dll.drawn, without.drawn)
                    self.assertEqual(with_dll.heathen(), without.heathen())

    def test_all_three_rows_in_every_mode_with_and_without_256_villagers(self):
        """Faith Loss (the cave's own 1-in-10 rule), New Heathens Get a Heathen's Faith (-38 - rand(30)) and this
        companion, composed by
        the patcher in each population mode, with and without 256 Villagers (which moves the villager manager the
        drift's believers count reads, 0x46815E)."""
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            for extra in ((), ("vv5_population_256",)):
                with self.subTest(mode=mode, extra=extra):
                    ids = patcher.resolve_fun_patch_ids(
                        list(extra) + [FAITH_LOSS, "vv5_new_heathens_get_heathen_faith", gen.NOTICE_ID],
                        game_id="vv5")
                    exe = bytes(patcher.render_patched_bytes(STOCK, build(), mode, ids)[0])
                    v = Village(exe)
                    self.assertEqual(v.proc.export("VvfpFaithNoticeInstalled"), 1)
                    self.assertEqual(v.proc.u32(0x46815F), 0x800000 if extra else 0x554148)
                    self.assertEqual(v.drift(faith=1, food=100, rolls=[0, 99, 5]), 1, "9 in 10: stays")
                    self.assertIsNone(v.pending(100000))
                    # 1 in 10: a Heathen, then the blue Heathen's Faith: rand(30) gives 99 % 30 = 9, so -47.
                    self.assertEqual(v.drift(faith=1, food=100, rolls=[0, 99, 0]), -47)
                    self.assertTrue(v.heathen())
                    self.assertEqual(v.pending(200000), (1, only(HUNGER)))


def gen_quiet() -> int:
    """The companion's quiet wait (FN_QUIET_MS), read from its source."""
    import re
    source = (ROOT / "native" / "vvfp_faith_notice" / "vvfp_faith_notice.c").read_text(encoding="utf-8")
    return int(re.search(r"#define FN_QUIET_MS (\d+)u", source).group(1))


# ---------------------------------------------------------------------------
# The popup (VVFP Story Upgrades.dll)
# ---------------------------------------------------------------------------

def story_harness():
    try:
        from test_story_custom_island_event import SCRATCH, Story, TEST_DLL
        from test_story_time_skip import island_ready, tick
    except ImportError:  # pragma: no cover
        raise unittest.SkipTest("the story harness is not importable")
    if not HAVE_EMULATOR or not TEST_DLL.is_file():
        raise unittest.SkipTest("the story test build is not present")
    if not STOCK.is_file():
        raise unittest.SkipTest("stock New Believers is not in inputs/")
    return SCRATCH, Story, island_ready, tick


# The owner's words (2026-11-08); the list is a paragraph of its own.
OPENING = ("Several of your villagers have lost faith in you due to the dire conditions and have "
           "decided to join the heathens' tribe.\n\n")
OPENING_ONE = ("One of your villagers has lost faith in you due to the dire conditions and has "
               "decided to join the heathens' tribe.\n\n")
ISOLA = ("Several of your villagers have lost hope due to the dire conditions and have decided to "
         "join the Isolans' tribe.\n\n")
ISOLA_ONE = ("One of your villagers has lost hope due to the dire conditions and has decided to join "
             "the Isolans' tribe.\n\n")
TITLE = "The Breaking Point"


class Popup(unittest.TestCase):
    def story(self):
        scratch, Story, island_ready, tick = story_harness()
        story = Story("vv5")
        island_ready(story)
        return story, scratch, tick

    def armed(self, story, scratch) -> tuple[str, str]:
        p = story.proc
        p.export("VvfpStoryProbeArmedNotice", scratch, scratch + 0x100)
        return p.cstring(scratch), p.cstring(scratch + 0x100)

    def counts(self, story, scratch, counts) -> None:
        story.proc.write(scratch + 0x800, struct.pack("<5I", *counts))
        story.proc.export("VvfpStoryProbeFaithNotice", scratch + 0x800)

    def isola(self, story, text: bytes) -> None:
        """The game's string 0x48 as the Guardians of Isola sm.xml loads it (the entry's +0xC)."""
        p = story.proc
        entry, loaded = p.alloc(16), p.alloc(64)
        p.write(loaded, text + b"\0")
        p.write(entry, struct.pack("<4I", 0x48, 0x4B6FCC, 0x4B6FA0, loaded))
        p.put32(0x5240A8 + 4 * 0x48, entry)

    def test_the_popup_says_how_many_and_why(self):
        for counts, text in (
                ((3, 0, 1, 2, 0), f"{OPENING}3 villagers have left due to starvation, 1 due to sickness and 2 due "
                                  "to too few believers."),
                ((0, 0, 0, 1, 0), f"{OPENING_ONE}1 villager has left due to too few believers."),
                ((0, 2, 0, 0, 0), f"{OPENING}2 villagers have left due to hunger."),
                ((1, 1, 0, 0, 0), f"{OPENING}1 villager has left due to starvation and 1 due to hunger."),
                ((2, 5, 1, 3, 0), f"{OPENING}2 villagers have left due to starvation, 5 due to hunger, 1 due to "
                                  "sickness and 3 due to too few believers."),
                ((0, 0, 0, 0, 2), f"{OPENING}2 villagers have left due to a loss of faith.")):
            with self.subTest(counts=counts):
                story, scratch, tick = self.story()
                p = story.proc
                self.counts(story, scratch, counts)
                tick(story, 100)
                self.assertEqual(self.armed(story, scratch), (TITLE, text))
                self.assertEqual(p.export("VvfpStoryProbeCustomPending", 5), 1)
                self.assertEqual(p.export("VvfpStoryProbeFaithNoticeTaken"), 1)
                tick(story, 200)
                self.assertEqual(p.export("VvfpStoryProbeFaithNoticeTaken"), 1, "once")

    def test_the_title_is_one_constant_with_its_own_key(self):
        source = (ROOT / "native" / "vvfp_story_upgrades" / "story_faith_notice.inc").read_text(encoding="utf-8")
        self.assertIn('#define FAITH_NOTICE_TITLE "The Breaking Point"', source)
        self.assertIn('"vvfp.story/story_faith_notice.FAITH_NOTICE_TITLE.s0", FAITH_NOTICE_TITLE', source)

    def test_the_longest_popup_is_delivered_whole(self):
        story, scratch, tick = self.story()
        p = story.proc
        self.counts(story, scratch, (99, 99, 99, 99, 99))
        tick(story, 100)
        title, text = self.armed(story, scratch)
        self.assertTrue(text.startswith(OPENING) and text.endswith("and 99 due to a loss of faith."), text)
        self.assertEqual(p.export("VvfpStoryProbeDeliver", 5, scratch + 0x1000, 4096), 1)
        self.assertIn("99 due to a loss of faith.", p.cstring(scratch + 0x1000).replace("\n", " "))
        self.assertEqual(p.export("VvfpStoryTimeSkipNoticeShown", 5), 1, "not an island event: not logged as one")

    def test_with_guardians_of_isola_the_isolans_tribe(self):
        story, scratch, tick = self.story()
        self.isola(story, b"A villager has left the tribe!")
        self.counts(story, scratch, (4, 0, 0, 0, 0))
        tick(story, 100)
        self.assertEqual(self.armed(story, scratch),
                         (TITLE, f"{ISOLA}4 villagers have left due to starvation."))
        story, scratch, tick = self.story()
        self.isola(story, b"A villager has left the tribe!")
        self.counts(story, scratch, (0, 0, 0, 1, 0))
        tick(story, 100)
        self.assertEqual(self.armed(story, scratch)[1],
                         f"{ISOLA_ONE}1 villager has left due to too few tribe members.")
        story, scratch, tick = self.story()
        self.isola(story, b"A villager has left the tribe!")
        self.counts(story, scratch, (0, 0, 0, 0, 3))
        tick(story, 100)
        self.assertEqual(self.armed(story, scratch)[1], f"{ISOLA}3 villagers have left due to a loss of hope.")

    def test_the_stock_string_keeps_the_stock_wording(self):
        story, scratch, tick = self.story()
        self.isola(story, b"A villager has stopped believing in you!")
        self.counts(story, scratch, (0, 0, 2, 0, 0))
        tick(story, 100)
        self.assertEqual(self.armed(story, scratch)[1], f"{OPENING}2 villagers have left due to sickness.")

    def test_it_waits_for_an_open_island_event_and_a_queued_one(self):
        story, scratch, tick = self.story()
        p = story.proc
        p.export("VvfpStoryProbeIslandEventOpen", 1)
        self.counts(story, scratch, (0, 2, 0, 0, 0))
        tick(story, 100)
        self.assertEqual(self.armed(story, scratch), ("", ""))
        self.assertEqual(p.export("VvfpStoryProbeFaithNoticeTaken"), 0, "the count is kept")
        p.export("VvfpStoryProbeIslandEventOpen", 0)
        tick(story, 200)
        self.assertEqual(self.armed(story, scratch)[0], TITLE)
        story, scratch, tick = self.story()
        p = story.proc
        p.export("VvfpStoryProbeArm", 5, 0, 0)          # a Pick Island Event is on its way
        picked = p.export("VvfpStoryProbeArmedSlot")
        self.assertNotEqual(picked, 0xFFFFFFFF)
        self.counts(story, scratch, (0, 2, 0, 0, 0))
        tick(story, 100)
        self.assertEqual(p.export("VvfpStoryProbeFaithNoticeTaken"), 0)
        self.assertEqual(p.export("VvfpStoryProbeArmedSlot"), picked, "the pick is left alone")

    def test_it_waits_while_the_game_is_paused(self):
        """Armed only while the game runs, so the game's trigger shows it at once and it never holds the event
        slot against a purchase."""
        try:
            from test_story_time_skip import TimeSkipHost
        except ImportError:  # pragma: no cover
            self.skipTest("the time skip harness is not importable")
        story, scratch, tick = self.story()
        p = story.proc
        host = TimeSkipHost(story, -1)                  # its clock entry says "paused"
        self.counts(story, scratch, (0, 1, 0, 0, 0))
        tick(story, 100)
        self.assertEqual(p.export("VvfpStoryProbeFaithNoticeTaken"), 0)
        host.step_years = 6                             # running again
        tick(story, 200)
        self.assertEqual(p.export("VvfpStoryProbeFaithNoticeTaken"), 1)

    def test_it_waits_for_a_time_skip_and_its_own_popup(self):
        try:
            from test_story_time_skip import TimeSkipHost, notice
        except ImportError:  # pragma: no cover
            self.skipTest("the time skip harness is not importable")
        story, scratch, tick = self.story()
        p = story.proc
        host = TimeSkipHost(story, 12)
        assert p.export("VvfpStoryProbeTimeSkipStart", 5, 24, 0) > 0
        self.counts(story, scratch, (0, 5, 0, 0, 0))
        tick(story, 100)
        self.assertEqual(p.export("VvfpStoryProbeFaithNoticeTaken"), 0, "not during the skip")
        at = 100
        for _ in range(10):
            host.settled = True
            at += 100
            tick(story, at)
        self.assertEqual(notice(story)["armed"], 1, "the skip's own popup first")
        self.assertEqual(self.armed(story, scratch)[0], "Time Skip")
        self.assertEqual(p.export("VvfpStoryProbeFaithNoticeTaken"), 0, "then the believers', in its turn")

    def test_start_over_drops_a_waiting_batch(self):
        story, scratch, tick = self.story()
        p = story.proc
        p.export("VvfpStoryProbeIslandEventOpen", 1)        # held by an open event
        self.counts(story, scratch, (0, 2, 0, 0, 0))
        tick(story, 100)
        p.export("VvfpStoryVillageReset", 5, 1)             # Start Over
        p.export("VvfpStoryProbeIslandEventOpen", 0)
        tick(story, 200)
        self.assertEqual(p.export("VvfpStoryProbeFaithNoticeTaken"), 0)
        self.assertEqual(self.armed(story, scratch), ("", ""))

    def test_only_in_new_believers(self):
        scratch, Story, island_ready, tick = story_harness()
        story = Story("vv1")
        island_ready(story)
        story.proc.write(scratch + 0x800, struct.pack("<5I", 0, 2, 0, 0, 0))
        story.proc.export("VvfpStoryProbeFaithNotice", scratch + 0x800)
        tick(story, 100)
        self.assertEqual(story.proc.export("VvfpStoryProbeFaithNoticeTaken"), 0)


if __name__ == "__main__":
    unittest.main()
