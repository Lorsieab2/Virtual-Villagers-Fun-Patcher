"""The Origins Barrel of Babies, as rendered, in all three population modes.

Three defects found while building Story / Cheat Upgrades (v1.35.45), each
checked here by RUNNING the rendered executable's own code in the emulator
(tests/story_emulator.py), never by reading a manifest:

* A New Home / The Lost Children: a one-shot "three children" flag (VV1
  0x48D708, VV2 0x49C704) was armed before the purchased barrel and consumed by
  a detour on the Mysterious Crate's count roll (VV1 0x42B00C) and the
  Mysterious Sack / Vial's strength roll (VV2 0x437ADC) -- never by the barrel,
  whose children come from its magnitude.  So the next crate or sack after a
  purchased barrel was forced to its strongest outcome.  Now: both roll sites
  hold stock bytes, nothing in the image addresses either flag, and the
  purchased barrel still delivers three children through the game's own
  barrel case.
* A New Home: the deferred barrel helper destroyed its operator-new event with
  the plain destructor 0x427620 and never freed the 0x50F0-byte block.  Now it
  calls the class's scalar deleting destructor 0x427A00 with flag 1, which
  frees the block through operator delete 0x44AEAE.
* New Believers: the stock Chutes Without Ladders override ran after the
  Origins barrel stub, so a purchased Barrel could come out as Chutes.  Now a
  purchased Barrel reaches the presenter as the Barrel; a natural event still
  gets the stock override.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    from story_emulator import STACK_TOP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

MODES = ("stock", "collection_progression", "immediate_fixed")


@functools.lru_cache(maxsize=None)
def _builds():
    return {build.id: build for build in patcher.load_builds()}


def stock_path(game: str) -> Path:
    return ROOT / "inputs" / f"{game}-stock-copy" / _builds()[game].input_name


@functools.lru_cache(maxsize=None)
def render(game: str, mode: str) -> bytes:
    data, _ = patcher.render_patched_bytes(
        stock_path(game), _builds()[game], mode, [f"{game}_origins_village_wide_upgrades"])
    return bytes(data)


def _needs(game: str):
    if not HAVE_EMULATOR:
        raise unittest.SkipTest("unicorn / pefile not installed")
    if not stock_path(game).is_file():
        raise unittest.SkipTest(f"{game} stock executable is not present")


def _recorder(log: list, value: int = 0, pop: int = 0, *, ecx: bool = False, args: int = 0):
    def stub(proc):
        entry = [proc.reg("ecx")] if ecx else []
        entry += [proc.arg(i) for i in range(args)]
        log.append(tuple(entry))
        return value, pop
    return stub


# ---------------------------------------------------------------------------
# The "three children" flag is gone; crates and sacks roll as stock.
# ---------------------------------------------------------------------------
class ThreeChildFlagIsGone(unittest.TestCase):
    SITES = {
        # game: (roll site file offset, length, flag VA)
        "vv1": (0x2B00C, 5, 0x48D708),
        "vv2": (0x37ADC, 5, 0x49C704),
    }

    def test_roll_sites_are_stock_and_no_code_addresses_the_flag(self):
        for game, (offset, length, flag) in self.SITES.items():
            _needs(game)
            stock = stock_path(game).read_bytes()
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    data = render(game, mode)
                    self.assertEqual(data[offset:offset + length], stock[offset:offset + length],
                                     "the crate / sack roll is detoured again")
                    self.assertNotIn(struct.pack("<I", flag), data,
                                     f"something in the image addresses the old flag {flag:#x}")

    def test_vv1_crate_roll_runs_stock(self):
        """Run the crate's roll instruction: it calls the game's own rand and
        nothing else, so the crate after a barrel rolls exactly as stock."""
        _needs("vv1")
        for mode in MODES:
            with self.subTest(mode=mode):
                proc = Process(render("vv1", mode))
                rolls = []
                proc.stub(0x402F10, _recorder(rolls, 37, args=1))
                proc.put32(0x48D708, 1)   # even a stale byte there changes nothing
                proc.set_reg("esp", STACK_TOP - 0x2000)
                proc.put32(STACK_TOP - 0x2000, 100)
                proc.mu.emu_start(0x42B00C, 0x42B011, count=1000)
                self.assertEqual(proc.reg("eip"), 0x42B011)
                self.assertEqual(proc.reg("eax"), 37)
                self.assertEqual(len(rolls), 1)


# ---------------------------------------------------------------------------
# A New Home: the purchased barrel is the game's own barrel at magnitude 10.
# ---------------------------------------------------------------------------
CASE_12_CHILD_CALLS = (0x428263, 0x4282C6, 0x4282E3, 0x42833C, 0x428359, 0x428376)


class Vv1PurchasedBarrelIsThreeChildren(unittest.TestCase):
    def test_purchase_token_dispatches_case_12_magnitude_10(self):
        _needs("vv1")
        for mode in MODES:
            with self.subTest(mode=mode):
                proc = Process(render("vv1", mode))
                dispatched = []
                proc.stub(0x427CA0, _recorder(dispatched, 0, 8, args=2))
                event = proc.alloc(0x5100)
                proc.call(0x428470, [1, 0x7F4B1A2C], ecx=event)
                self.assertEqual(dispatched, [(12, 10)])

    def _children(self, mode: str, magnitude: int) -> int:
        proc = Process(render("vv1", mode))
        children = []
        text = proc.alloc(0x40)
        proc.stub(0x433970, lambda p: (text, 4))          # string table lookup
        proc.stub(0x44B23D, lambda p: (0, 0))              # strcpy (cdecl)
        proc.stub(0x427A20, lambda p: (0, 0x10))           # message box setup
        proc.stub(0x402F10, lambda p: (0, 0))              # rand
        # The six child-creation calls of case 12 (stock target 0x43C350; a
        # population mode may route them through its own wrapper).  Whatever
        # each one calls is what creates a child, so stub that.
        for site in CASE_12_CHILD_CALLS:
            image = proc.read(site, 5)
            self.assertEqual(image[0], 0xE8, f"{site:#x} is no longer a call")
            target = (site + 5 + struct.unpack("<i", image[1:])[0]) & 0xFFFFFFFF
            proc.stub(target, _recorder(children, 0, 0x14, args=5))
        event = proc.alloc(0x5100)
        proc.call(0x427CA0, [12, magnitude], ecx=event)
        return len(children)

    def test_case_12_child_count_comes_from_the_magnitude(self):
        _needs("vv1")
        for mode in MODES:
            for magnitude, expected in ((10, 3), (8, 3), (7, 2), (5, 2), (4, 1), (1, 1)):
                with self.subTest(mode=mode, magnitude=magnitude):
                    self.assertEqual(self._children(mode, magnitude), expected)


VV2_CASE_21_CHILD_CALLS = (0x434102, 0x4341A2, 0x4341C3, 0x434262, 0x434283, 0x4342A4)


class Vv2PurchasedBarrelIsThreeChildren(unittest.TestCase):
    def test_purchase_token_dispatches_case_21_magnitude_10(self):
        _needs("vv2")
        for mode in MODES:
            with self.subTest(mode=mode):
                proc = Process(render("vv2", mode))
                dispatched = []
                proc.stub(0x433600, _recorder(dispatched, 0, 8, args=2))
                event = proc.alloc(0x5100)
                proc.call(0x434570, [2, 0x7F4B1A2C], ecx=event)
                self.assertEqual(dispatched, [(21, 10)])

    def _children(self, mode: str, magnitude: int) -> int:
        proc = Process(render("vv2", mode))
        children = []
        text = proc.alloc(0x40)
        proc.write(text, b"x\0")
        proc.stub(0x441680, lambda p: (text, 4))          # string table lookup
        proc.stub(0x4682BD, lambda p: (0, 0))              # strcpy (cdecl)
        proc.stub(0x4031A0, lambda p: (0, 0))              # rand
        for site in VV2_CASE_21_CHILD_CALLS:
            image = proc.read(site, 5)
            self.assertEqual(image[0], 0xE8, f"{site:#x} is no longer a call")
            target = (site + 5 + struct.unpack("<i", image[1:])[0]) & 0xFFFFFFFF
            proc.stub(target, _recorder(children, 0, 0x14, args=5))
        event = proc.alloc(0x5100)
        proc.call(0x433600, [21, magnitude], ecx=event)
        return len(children)

    def test_case_21_child_count_comes_from_the_magnitude(self):
        _needs("vv2")
        for mode in MODES:
            for magnitude, expected in ((10, 3), (8, 3), (7, 2), (5, 2), (4, 1), (1, 1)):
                with self.subTest(mode=mode, magnitude=magnitude):
                    self.assertEqual(self._children(mode, magnitude), expected)


# ---------------------------------------------------------------------------
# A New Home: the deferred barrel helper frees the event it allocates.
# ---------------------------------------------------------------------------
PENDING = 0x48D700
DELAY = 0x48D704
HELPER = 0x48D710
RESUME = 0x424044


class Vv1DeferredBarrelFreesItsEvent(unittest.TestCase):
    def _run(self, mode: str, *, construct: bool, population: int = 5):
        proc = Process(render("vv1", mode))
        log = {name: [] for name in ("new", "construct", "dispatch", "destroy", "delete")}
        block = proc.alloc(0x50F0)
        proc.stub(0x448600, lambda p: (0, 0))               # the call the splice displaced
        # population (12 or fewer always has room; the village here has no
        # hut upgrades, so 13 or more has none)
        proc.stub(0x41CF90, lambda p: (population, 0))
        proc.stub(0x44AF03, _recorder(log["new"], block if construct else 0, args=1))
        proc.stub(0x4286B0, _recorder(log["construct"], 0, 8, ecx=True, args=2))
        proc.stub(0x401AB0, _recorder(log["dispatch"], 0, 8, ecx=True, args=2))
        proc.stub(0x427620, _recorder(log["destroy"], 0, ecx=True))
        proc.stub(0x44AEAE, _recorder(log["delete"], 0, args=1))
        village = proc.alloc(0xA400)
        owner = proc.alloc(0x40)
        proc.put32(owner + 0x10, village)
        proc.write(PENDING, b"\x02")
        proc.put32(DELAY, 179)                              # this tick crosses the delay
        regs = {"esi": owner, "ebx": 0x11111111, "edi": 0x22222222, "ebp": 0x33333333}
        proc.call(HELPER, [], regs=regs, until=RESUME)
        # pushad / popad: the owner's registers survive the helper.
        for name, value in regs.items():
            self.assertEqual(proc.reg(name), value, name)
        return proc, block, log

    def test_dispatched_event_is_destroyed_and_freed(self):
        _needs("vv1")
        for mode in MODES:
            with self.subTest(mode=mode):
                proc, block, log = self._run(mode, construct=True)
                self.assertEqual(log["new"], [(0x50F0,)])
                self.assertEqual(log["construct"], [(block, 1, 0x7F4B1A2C)])
                self.assertEqual(len(log["dispatch"]), 1)
                self.assertEqual(log["destroy"], [(block,)])
                self.assertEqual(log["delete"], [(block,)], "the 0x50F0-byte event leaks")
                self.assertEqual(proc.read(PENDING, 1), b"\x00")
                self.assertEqual(proc.u32(DELAY), 0)

    def test_failed_construction_holds_the_paid_event(self):
        _needs("vv1")
        for mode in MODES:
            with self.subTest(mode=mode):
                proc, _, log = self._run(mode, construct=False)
                self.assertEqual(log["construct"], [])
                self.assertEqual(log["destroy"], [])
                self.assertEqual(log["delete"], [])
                self.assertEqual(proc.read(PENDING, 1), b"\x02", "the paid barrel was dropped")

    def test_no_room_holds_the_paid_event_and_allocates_nothing(self):
        _needs("vv1")
        for mode in MODES:
            with self.subTest(mode=mode):
                proc, _, log = self._run(mode, construct=True, population=13)
                self.assertEqual(log["new"], [])
                self.assertEqual(log["delete"], [])
                self.assertEqual(proc.read(PENDING, 1), b"\x02", "the paid barrel was dropped")


# ---------------------------------------------------------------------------
# New Believers: a purchased Barrel is never turned into Chutes.
# ---------------------------------------------------------------------------
BARREL_BIT_VA = 0x51D388
PRESENTER = 0x41895B


class Vv5PurchasedBarrelSkipsChutesOverride(unittest.TestCase):
    def _select(self, mode: str, *, purchased: bool, override_roll: int):
        proc = Process(render("vv5", mode))
        rolls = iter([0, 70, override_roll])                # index, edi, override roll
        proc.stub(0x403660, lambda p: (next(rolls), 0))
        proc.stub(0x472B80, lambda p: (0, 0))               # not -1: straight to the roll
        proc.stub(0x4713F0, lambda p: (0, 0))
        proc.put32(BARREL_BIT_VA, 4 if purchased else 0)
        esp = STACK_TOP - 0x4000
        proc.put32(esp + 0x10, 7)                           # the only candidate event
        proc.set_reg("esp", esp)
        proc.set_reg("edi", 1)                              # candidate count
        proc.run(0x418909, PRESENTER)
        self.assertEqual(proc.reg("esp"), esp, "stack unbalanced at the presenter")
        self.assertEqual(proc.reg("edi"), 70, "rand(100) result lost from edi")
        return proc

    def test_purchased_barrel_reaches_presenter_as_barrel(self):
        _needs("vv5")
        for mode in MODES:
            for roll in (5, 50):
                with self.subTest(mode=mode, override_roll=roll):
                    proc = self._select(mode, purchased=True, override_roll=roll)
                    self.assertEqual(proc.reg("esi"), 26)
                    self.assertEqual(proc.u32(BARREL_BIT_VA) & 4, 0, "purchase not consumed")

    def test_natural_events_keep_the_stock_chutes_override(self):
        _needs("vv5")
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertEqual(self._select(mode, purchased=False, override_roll=5).reg("esi"), 30)
                self.assertEqual(self._select(mode, purchased=False, override_roll=50).reg("esi"), 7)


if __name__ == "__main__":
    unittest.main()
