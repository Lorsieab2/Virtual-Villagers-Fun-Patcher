"""No Fishing at Science Level 2 (The Tree of Life): the Clothing Hut's site appears at Science 3, and a site that
already shows below Science 3 is locked again with its progress kept.  The traces are in
scripts/build_vv4_no_fishing_at_science_2_feature.py.

Run stock and patched in unicorn from the executable the patcher renders, on the game's own Clothing Hut object
(constructed by its own constructor 0x431190) and its own map (0x6C4658):
  * a new site at Science 1, 2 and 3 (the per-object update 0x4300E0, which asks the reveal predicate);
  * a site saved showing (state 3, painted by the load's own paint) with 0, partial and most of its points at
    Science 2: patched, it is hidden and unpainted -- the map exactly as before the paint -- with its progress, place
    and saved fields untouched; at Science 3 it is back, in the same place, painted exactly as before;
  * a finished Clothing Hut at Science 2 is never touched;
  * project 22's percent (0x438980, the Building dispatcher's and Builders Fix Huts' test) and the task-15
    continuation (0x463786) while locked and once Science is 3.
Tests that need the stock executable skip when it is absent.
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

import vv_fun_patcher as patcher  # noqa: E402
from vv_fun_patcher_gui import default_fun_patch_selection, owners_default_fun_patch_selection  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

FEATURE_ID = "vv4_no_fishing_at_science_2"
FEATURE_PATH = ROOT / "data" / "vv4_no_fishing_at_science_2_feature.json"
STOCK_DIR = ROOT / "research" / "stock-executables"

HUT = 0x4D82D8              # the Clothing Hut's building object
CTOR = 0x431190
UPDATE = 0x4300E0           # vtable +0x24
PAINT = 0x430A20            # vtable +0x70, what the load runs after restoring the record
SAVE, LOAD = 0x42FE80, 0x42FE30  # vtable +0x10 / +0x0C: the object's 0x1C-byte saved record +0x28..+0x43
SCIENCE = 0x4D6F5C
PROGRESS = 0x4D8CA8
THRESHOLD = 0x4D8B78
MANAGER = 0x4D8BF8
PERCENT = 0x438980
MAP, MAP_SIZE = 0x6C4658, 0x100 * 0x100 * 4
RAND = 0x471CF8             # the C runtime's rand(), which needs the thread block; stubbed
PLACE = (800, 800)          # the saved site's place, in world pixels
MASK_W, MASK_H = 6, 4       # its footprint, in map cells


def build():
    return next(b for b in patcher.load_builds() if b.id == "vv4")


def stock_path() -> Path:
    path = STOCK_DIR / build().input_name
    if not path.is_file():
        raise unittest.SkipTest("stock vv4 exe not present in this checkout")
    return path


_RENDERS: dict = {}


def rendered(patched: bool) -> bytes:
    if patched not in _RENDERS:
        path = stock_path()
        _RENDERS[patched] = bytes(patcher.render_patched_bytes(
            path, build(), patcher.DEFAULT_PATCH_MODE, [FEATURE_ID])[0]) if patched else path.read_bytes()
    return _RENDERS[patched]


class Machine:
    STACK, SCRATCH, RET = 0x20000000, 0x30000000, 0x2FFF0000

    def __init__(self, exe: bytes):
        pe = pefile.PE(data=exe, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFFF) & ~0xFFFF
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc.mem_map(base, size)
        self.uc.mem_write(base, pe.get_memory_mapped_image()[:size])
        self.uc.mem_map(self.STACK, 0x100000)
        self.uc.mem_map(self.SCRATCH, 0x100000)
        self.uc.mem_map(self.RET & ~0xFFFF, 0x10000)
        self.seed = 12345
        self.uc.hook_add(UC_HOOK_CODE, self._rand, begin=RAND, end=RAND)

    def _rand(self, uc, _a, _s, _d):
        self.seed = (self.seed * 1103515245 + 12345) & 0x7FFFFFFF
        uc.reg_write(UC_X86_REG_EAX, (self.seed >> 16) & 0x7FFF)
        sp = uc.reg_read(UC_X86_REG_ESP)
        uc.reg_write(UC_X86_REG_EIP, self.r32(sp))
        uc.reg_write(UC_X86_REG_ESP, sp + 4)

    def w32(self, at: int, value: int) -> None:
        self.uc.mem_write(at, struct.pack("<i", value))

    def r32(self, at: int) -> int:
        return struct.unpack("<I", bytes(self.uc.mem_read(at, 4)))[0]

    def s32(self, at: int) -> int:
        return struct.unpack("<i", bytes(self.uc.mem_read(at, 4)))[0]

    def r8(self, at: int) -> int:
        return self.uc.mem_read(at, 1)[0]

    def call(self, fn: int, ecx: int, *args: int, esi: int = 0) -> int:
        sp = self.STACK + 0xF0000
        for value in reversed(args):
            sp -= 4
            self.w32(sp, value)
        sp -= 4
        self.w32(sp, self.RET)
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_ECX, ecx)
        self.uc.reg_write(UC_X86_REG_ESI, esi)
        self.uc.emu_start(fn, self.RET, count=5_000_000)
        return self.uc.reg_read(UC_X86_REG_EAX)

    def map_bytes(self) -> bytes:
        """The map's cells.  (Each area's bounds flag at 0x704668 is set to 1 by every paint, 0x46CE8A, and at map
        load, 0x46C192; it only asks for the area's bounds to be measured again, 0x46C4C9, and is never cleared by
        the game's erase.)"""
        return bytes(self.uc.mem_read(MAP, MAP_SIZE))


class Hut:
    """The game's own Clothing Hut object in a machine: constructed, its footprint masks given (the game loads them
    from the hut's sprite, 0x42FD20), Science set."""

    def __init__(self, patched: bool, science: int):
        self.m = Machine(rendered(patched))
        self.m.call(CTOR, HUT)
        mask = Machine.SCRATCH + 0x1000
        self.m.uc.mem_write(mask, b"\x01" * (MASK_W * MASK_H))
        self.m.w32(HUT + 0x6C, mask)
        self.m.w32(HUT + 0x70, 0)
        self.m.w32(HUT + 0x74, MASK_W)
        self.m.w32(HUT + 0x78, MASK_H)
        self.science(science)

    def science(self, level: int) -> None:
        self.m.w32(SCIENCE, level)

    def saved_showing(self, progress: int) -> None:
        """A save written with the site showing: its record (+0x28..+0x43) and the progress table as the loader
        0x4387A0 / 0x42FE30 restore them, then the load's own paint."""
        self.m.w32(HUT + 0x28, PLACE[0])
        self.m.w32(HUT + 0x2C, PLACE[1])
        self.m.uc.mem_write(HUT + 0x30, b"\x01")
        self.m.w32(HUT + 0x34, 3)
        self.m.w32(HUT + 0x38, 2000)
        self.m.w32(HUT + 0x3C, -1)
        self.m.w32(HUT + 0x40, 0)
        self.m.w32(PROGRESS, progress)
        self.m.call(PAINT, HUT)

    def update(self, times: int = 1) -> None:
        for _ in range(times):
            self.m.call(UPDATE, HUT)

    @property
    def state(self) -> int:
        return self.m.s32(HUT + 0x34)

    @property
    def stage(self) -> int:
        return self.m.s32(HUT + 0x40)

    @property
    def progress(self) -> int:
        return self.m.s32(PROGRESS)

    @property
    def place(self) -> tuple[int, int]:
        return self.m.s32(HUT + 0x28), self.m.s32(HUT + 0x2C)

    def record(self) -> bytes:
        """The saved fields other than the state and the stage (+0x28..+0x33, +0x38)."""
        return bytes(self.m.uc.mem_read(HUT + 0x28, 0xC)) + bytes(self.m.uc.mem_read(HUT + 0x38, 4))

    def percent(self) -> int:
        return struct.unpack("<i", struct.pack("<I", self.m.call(PERCENT, MANAGER, 22)))[0]


class FeatureRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = json.loads(FEATURE_PATH.read_text(encoding="utf-8"))

    def test_the_row(self) -> None:
        self.assertEqual(self.record["id"], FEATURE_ID)
        self.assertEqual(self.record["name"], "No Fishing at Science Level 2")
        self.assertEqual(self.record["game_id"], "vv4")
        self.assertIn(FEATURE_ID, {p.id for p in patcher.load_public_fun_patches()})

    def test_the_description_gives_the_numbers_the_relock_and_why(self) -> None:
        text = self.record["description"]
        self.assertTrue(text.startswith("**Needs no other patch.**"))
        for words in ("Science level 2 (8,000 tech points)", "Science level 3 (70,000 tech points)",
                      "Cloth Invented", "Fishing Nets", "locked again", "all the building it already had",
                      "Nothing is reset or lost", "already finished is never affected", "off by default"):
            self.assertIn(words, text)

    def test_off_by_default_and_in_owners_defaults(self) -> None:
        """Off everywhere (the owner, 2026-11-08: "The "Clothing hut at Science Level 3" patch should be DEFAULT OFF
        everywhere"): Owner's Defaults ticks Clothmaking Unlocks at Science Level 3 instead."""
        self.assertFalse(default_fun_patch_selection(FEATURE_ID))
        self.assertFalse(owners_default_fun_patch_selection(FEATURE_ID))

    def test_every_edit_is_guarded_by_the_stock_bytes(self) -> None:
        data = stock_path().read_bytes()
        for p in self.record["patches"]:
            with self.subTest(offset=p["offset"]):
                off = int(p["offset"], 16)
                self.assertEqual(data[off:off + len(p["before"]) // 2].hex().upper(), p["before"])
                self.assertEqual(len(p["before"]), len(p["after"]))

    def test_the_generator_reproduces_the_record(self) -> None:
        stock_path()
        spec = importlib.util.spec_from_file_location(
            "build_vv4_no_fishing", ROOT / "scripts" / "build_vv4_no_fishing_at_science_2_feature.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        self.assertEqual(gen.feature(), self.record)


@unittest.skipUnless(HAVE_EMULATOR, "unicorn / pefile not installed")
class SiteTests(unittest.TestCase):
    def test_a_new_site_appears_at_science_2_stock_and_3_patched(self) -> None:
        for patched, shown_from in ((False, 2), (True, 3)):
            for science in (1, 2, 3):
                with self.subTest(patched=patched, science=science):
                    hut = Hut(patched, science)
                    blank = hut.m.map_bytes()
                    hut.update(3)
                    if science >= shown_from:
                        self.assertEqual(hut.state, 3)
                        self.assertEqual(hut.stage, 0)
                        self.assertNotEqual(hut.m.map_bytes(), blank, "the revealed site is painted")
                    else:
                        self.assertEqual(hut.state, 4)
                        self.assertEqual(hut.stage, -1)
                        self.assertEqual(hut.m.map_bytes(), blank)
                    self.assertEqual(hut.progress, 0)

    def test_a_showing_unbuilt_site_is_relocked_below_science_3_with_its_progress_kept(self) -> None:
        for progress in (0, 1, 150, 399, 400, 1200, 1999):
            with self.subTest(progress=progress):
                hut = Hut(True, 2)
                blank = hut.m.map_bytes()
                hut.saved_showing(progress)
                painted = hut.m.map_bytes()
                self.assertNotEqual(painted, blank)
                record = hut.record()
                hut.update(3)
                self.assertEqual(hut.state, 4)
                self.assertEqual(hut.stage, -1, "nothing is drawn")
                self.assertEqual(hut.m.map_bytes(), blank, "its map area is gone, and only its own")
                self.assertEqual(hut.progress, progress)
                self.assertEqual(hut.record(), record, "place and saved fields untouched")
                self.assertEqual(hut.m.r8(HUT + 0x54), 0, "not left dragging")
                self.assertLess(hut.percent(), 1, "no builder is offered it")
                # Science 3: back where it was, painted as before, with its points.
                hut.science(3)
                hut.update(3)
                self.assertEqual(hut.state, 3)
                self.assertEqual(hut.progress, progress)
                if progress:
                    self.assertEqual(hut.place, PLACE)
                    self.assertEqual(hut.record(), record)
                    self.assertEqual(hut.m.map_bytes(), painted)
                    self.assertGreaterEqual(hut.stage, 0)
                    expected = 100 - (2000 - progress) * 100 // 2000
                    self.assertEqual(hut.percent(), expected - 1 if expected == 100 else expected)
                else:
                    # No points: to the game a site never placed, so its own reveal places it again (maybe in a
                    # new spot; telling it apart would need a mark in a spare save byte, which the project
                    # forbids).  Nothing is lost: still 0 points, the saved fields other than the place kept.
                    self.assertEqual(hut.progress, 0)
                    self.assertEqual(hut.record()[8:], record[8:], "everything but the place is kept")
                    self.assertEqual(hut.percent(), 0)
                    self.assertEqual(hut.stage, 0)
                    self.assertNotEqual(hut.m.map_bytes(), blank, "painted where the game placed it")

    def test_a_site_saved_while_relocked_stays_hidden_after_load_and_returns_at_science_3(self) -> None:
        """Relocked (state 4) with points, saved with the game's own save 0x42FE80, loaded into a fresh game with
        its own load 0x42FE30 (which paints a site unless it is in state 4): hidden and unpainted at Science 2,
        back at Science 3 in the same place, painted as before, with its points."""
        for progress in (1, 150, 399, 400, 1200, 1999):
            with self.subTest(progress=progress):
                hut = Hut(True, 2)
                hut.saved_showing(progress)
                painted, record = hut.m.map_bytes(), hut.record()
                hut.update(2)
                self.assertEqual(hut.state, 4)
                buffer = Machine.SCRATCH + 0x4000
                self.assertEqual(hut.m.call(SAVE, HUT, buffer, 0x1C), 0x1C)
                saved = bytes(hut.m.uc.mem_read(buffer, 0x1C))
                again = Hut(True, 2)
                blank = again.m.map_bytes()
                again.m.uc.mem_write(buffer, saved)
                again.m.w32(PROGRESS, progress)
                self.assertEqual(again.m.call(LOAD, HUT, buffer), 0x1C)
                again.update(3)
                self.assertEqual((again.state, again.stage, again.progress), (4, -1, progress))
                self.assertEqual(again.m.map_bytes(), blank, "not painted by the load")
                self.assertLess(again.percent(), 1)
                again.science(3)
                again.update(3)
                self.assertEqual((again.state, again.progress, again.place), (3, progress, PLACE))
                self.assertEqual(again.record(), record)
                self.assertEqual(again.m.map_bytes(), painted)
                self.assertGreaterEqual(again.stage, 0)

    def test_the_stock_game_keeps_a_showing_site_at_science_2(self) -> None:
        hut = Hut(False, 2)
        hut.saved_showing(700)
        painted = hut.m.map_bytes()
        hut.update(3)
        self.assertEqual((hut.state, hut.progress), (3, 700))
        self.assertGreaterEqual(hut.stage, 0)
        self.assertEqual(hut.m.map_bytes(), painted)
        self.assertGreaterEqual(hut.percent(), 1)

    def test_a_finished_clothing_hut_is_never_touched(self) -> None:
        for patched in (False, True):
            for science in (1, 2, 3):
                with self.subTest(patched=patched, science=science):
                    hut = Hut(patched, science)
                    hut.saved_showing(2000)
                    hut.m.w32(HUT + 0x34, 0)
                    hut.m.w32(HUT + 0x3C, -1)
                    painted = hut.m.map_bytes()
                    hut.update(3)
                    self.assertEqual((hut.state, hut.progress), (0, 2000))
                    self.assertEqual(hut.m.map_bytes(), painted)
                    self.assertEqual(hut.percent(), 100)

    def test_percent_matches_stock_at_science_3(self) -> None:
        for progress in (0, 21, 1000, 1999, 2000):
            with self.subTest(progress=progress):
                values = []
                for patched in (False, True):
                    hut = Hut(patched, 3)
                    hut.saved_showing(progress)
                    values.append(hut.percent())
                self.assertEqual(values[0], values[1])


@unittest.skipUnless(HAVE_EMULATOR, "unicorn / pefile not installed")
class BuilderTaskTests(unittest.TestCase):
    """The task-15 continuation 0x463786 (a villager whose task is building the Clothing Hut): it keeps the task
    (on to 0x463837, which starts the build again) or drops it (0x4636DD, task 0)."""

    KEEP, DROP = 0x463837, 0x4636DD

    def run_task(self, patched: bool, science: int, progress: int) -> int:
        hut = Hut(patched, science)
        m = hut.m
        m.w32(PROGRESS, progress)
        context, villager = Machine.SCRATCH + 0x2000, Machine.SCRATCH + 0x8000
        m.w32(context + 0x1B88, villager)
        m.w32(villager + 0x1C54, 15)
        reached = []

        def stop(uc, address, _s, _d):
            reached.append(address)
            uc.emu_stop()
        m.uc.hook_add(UC_HOOK_CODE, stop, begin=self.KEEP, end=self.KEEP)
        m.uc.hook_add(UC_HOOK_CODE, stop, begin=self.DROP, end=self.DROP)
        m.uc.reg_write(UC_X86_REG_ESP, Machine.STACK + 0xF0000)
        m.uc.reg_write(UC_X86_REG_ESI, context)
        m.uc.emu_start(0x463786, Machine.RET, count=100_000)
        return reached[0]

    def test_locked_the_villager_drops_the_task(self) -> None:
        for science in (1, 2, 3):
            for progress in (0, 500, 2000):
                with self.subTest(science=science, progress=progress):
                    stock = self.run_task(False, science, progress)
                    patched = self.run_task(True, science, progress)
                    self.assertEqual(stock, self.DROP if progress == 2000 else self.KEEP)
                    self.assertEqual(patched, stock if science >= 3 else self.DROP)


if __name__ == "__main__":
    unittest.main()
