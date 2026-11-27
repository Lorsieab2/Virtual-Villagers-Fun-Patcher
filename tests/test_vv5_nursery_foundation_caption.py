"""New Believers' Fix Vanilla Bugs: the unfinished Nursery School's mouse-over caption says "foundation" while
nothing is built yet.

The Nursery School's handler 0x43AA30, case 1 (a villager passes over it, 0x43AA99-0x43AAC0): when project 0x18
(the Nursery School building, CNurseryHut) is not done (0x43AE80(0x18) on the project table 0x51E008), it fetches
the building's progress (0x43AEA0(0x18)) and then drops it: the caption is always string 0x206
eSaySeesNurserySchoolConstruction "{name} sees a nursery school under construction.", and 0x207
eSaySeesNurserySchoolFoundation "{name} sees a nursery school foundation." is never shown.  The Tree of Life's same
handler (0x437749-0x437775) passes 0x251 + (progress < 1), its foundation line while nothing is built.

The fix rewrites the same 40 bytes in place, with no cave: the done test is the getter 0x43AE80's own body written
out (progress [0x51E008 + 8 x 0x18] = [0x51E0C8] >= threshold [0x51DF30 + 4 x 0x18] = [0x51DF90], signed, as its
setge), done -> 0x204 as before; otherwise the stock 0x43AEA0(0x18) is still called, and its result picks 0x206
when above 0, else 0x207.  The caption call at 0x43AAC1 is the stock one.  Nothing else jumps into the block (only
its own jne at 0x43AAA7, which the rewrite replaces).
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
FEATURE = "vv5_fix_vanilla_bugs"
BASE = 0x400000
MODES = ("stock", "collection_progression", "immediate_fixed")

FIX = (0x3AA99,
       bytes.fromhex("6A18B908E05100E8DB03000084C075136A18B908E05100E8EB030000B906020000EB05B904020000"),
       bytes.fromhex("A1C8E051003B0590DF5100B9040200007D166A18B908E05100E8E9030000B90602000085C07F0141"))
HANDLER, DONE, PERCENT, SAY = 0x43AA30, 0x43AE80, 0x43AEA0, 0x44F060
PROGRESS, THRESHOLD = 0x51E0C8, 0x51DF90
COMPLETED, CONSTRUCTION, FOUNDATION = 0x204, 0x206, 0x207


def foundation_caption_fixes() -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to vv5_fix_vanilla_bugs."""
    return (FIX,)


@functools.lru_cache(maxsize=None)
def _stock() -> bytes:
    return STOCK.read_bytes()


@functools.lru_cache(maxsize=None)
def _render(mode: str, ids: tuple) -> bytes:
    from vv_fun_patcher import load_builds, render_patched_bytes
    build = next(b for b in load_builds() if b.id == "vv5")
    data, _ = render_patched_bytes(STOCK, build, mode, list(ids))
    return bytes(data)


def _others() -> tuple:
    import vv_fun_patcher as fp
    return tuple(p.id for p in fp.load_public_fun_patches()
                 if p.game_id == "vv5" and p.id != FEATURE and p.id not in fp.EXPERIMENTAL_FUN_PATCH_IDS
                 and p.id not in fp.ALTERNATIVE_FUN_PATCH_IDS)


class Manifest(unittest.TestCase):
    def test_the_row_carries_the_fix_and_says_so(self) -> None:
        from vv_fun_patcher import load_fun_patches
        row = next(p for p in load_fun_patches() if p.id == FEATURE).raw
        # The Clothing Hut click fix (tests/test_vv5_clothing_hut_click.py) comes after this one.
        from test_vv5_clothing_hut_click import clothing_hut_click_fixes
        from test_duplicate_pickups import dupe_pickup_fixes        # ... and the duplicate-pickup fix after that
        later = len(clothing_hut_click_fixes()) + len(dupe_pickup_fixes("vv5"))
        last = row["patches"][-1 - later]
        self.assertEqual((int(last["offset"], 16), bytes.fromhex(last["before"]), bytes.fromhex(last["after"])), FIX)
        self.assertIn("sees a nursery school foundation", row["description"])
        self.assertTrue(row["description"].endswith("**Needs no other patch.**"))

    def test_game_mechanics_says_it_is_fixed(self) -> None:
        import vv_game_mechanics_nursery as nursery

        class V:
            def __init__(self, has):
                self._has = has

            def has(self, feature):
                return self._has if feature == FEATURE else False
        fixed = " ".join(f.text for f in nursery.lines(V(True), 5))
        self.assertIn("is in the game: it says \"{name} sees a nursery school foundation.\" while nothing is built",
                      fixed)
        self.assertIn("is not in the game.", " ".join(f.text for f in nursery.lines(V(False), 5)))


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class StockCode(unittest.TestCase):
    def test_the_stock_block_and_what_it_rests_on(self) -> None:
        import pefile
        raw = _stock()
        offset, before, after = FIX
        self.assertEqual(raw[offset:offset + len(before)], before)
        self.assertEqual(len(after), len(before))
        pe = pefile.PE(data=raw, fast_load=True)
        self.assertEqual(pe.get_offset_from_rva(offset), offset)
        img = pe.get_memory_mapped_image()
        at = lambda va, n: img[va - BASE:va - BASE + n]  # noqa: E731
        # The done getter whose body the fix writes out: [ecx + 8 n] >= [0x51DF30 + 4 n], setge.
        self.assertEqual(at(DONE, 20), bytes.fromhex("8B4424048B0CC13B0C8530DF51000F9DC0C20400"))
        self.assertEqual((0x51E008 + 8 * 0x18, 0x51DF30 + 4 * 0x18), (PROGRESS, THRESHOLD))
        # The caption call after the block, and the game's own built-in texts of the three ids.
        self.assertEqual(at(0x43AAC1, 4), bytes.fromhex("8B442410"))
        texts = {}
        for k in range(1409):
            i, name, text, _ = struct.unpack_from("<4I", img, 0x4D31F0 - BASE + 16 * k)
            if i in (COMPLETED, CONSTRUCTION, FOUNDATION):
                texts[i] = img[text - BASE:img.index(b"\0", text - BASE)]
        self.assertEqual(texts, {COMPLETED: b"{name} sees the completed nursery school.",
                                 CONSTRUCTION: b"{name} sees a nursery school under construction.",
                                 FOUNDATION: b"{name} sees a nursery school foundation."})

    def test_nothing_else_jumps_into_the_block(self) -> None:
        import capstone
        raw = _stock()
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.skipdata = True
        refs = []
        for i in md.disasm(raw[0x1000:0x98000], 0x401000):
            if i.mnemonic.startswith("j") or i.mnemonic == "call":
                try:
                    target = int(i.op_str, 16)
                except ValueError:
                    continue
                if 0x43AA9A <= target <= 0x43AAC0:
                    refs.append(i.address)
        self.assertEqual(refs, [0x43AAA7])

    def test_the_tree_of_life_chooses(self) -> None:
        img = (STOCK.parent / "Virtual Villagers - The Tree of Life.exe").read_bytes()
        # cmp eax, 1; setl cl; add ecx, 0x251 (0x437767-0x437773): foundation 0x252 while progress < 1.
        self.assertEqual(img[0x37767:0x37773], bytes.fromhex("83F8010F9CC181C151020000"))


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Modes(unittest.TestCase):
    def _fixed(self, data: bytes) -> None:
        offset, _before, after = FIX
        self.assertEqual(data[offset:offset + len(after)], after)

    def test_alone_with_the_others_and_without_in_every_mode(self) -> None:
        offset, before, _after = FIX
        others = _others()
        self.assertGreater(len(others), 10)
        for mode in MODES:
            with self.subTest(mode=mode):
                self._fixed(_render(mode, (FEATURE,)))
                self._fixed(_render(mode, others + (FEATURE,)))
                self.assertEqual(_render(mode, others)[offset:offset + len(before)], before)


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Emulated(unittest.TestCase):
    """The handler's mouse-over case run in unicorn, stock and fixed: only the caption id is recorded."""

    def _caption(self, data: bytes, progress: int, threshold: int = 2000, percent: int = 0) -> int:
        import pefile
        from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
        from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP
        img = pefile.PE(data=data, fast_load=True).get_memory_mapped_image()
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (len(img) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, img)
        stack, vil, ret = 0x0F000000, 0x0E000000, 0x0DEAD000
        mu.mem_map(stack - 0x10000, 0x10000)
        mu.mem_map(vil, 0x4000)
        mu.mem_map(ret, 0x1000)
        mu.mem_write(PROGRESS, struct.pack("<i", progress))
        mu.mem_write(THRESHOLD, struct.pack("<i", threshold))
        said = []

        def back(uc, eax, pop):
            sp = uc.reg_read(UC_X86_REG_ESP)
            to = struct.unpack("<I", uc.mem_read(sp, 4))[0]
            uc.reg_write(UC_X86_REG_EAX, eax)
            uc.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
            uc.reg_write(UC_X86_REG_EIP, to)

        def hook(uc, addr, _size, _data):
            sp = uc.reg_read(UC_X86_REG_ESP)
            if addr == SAY:
                said.append(struct.unpack("<I", uc.mem_read(sp + 4, 4))[0])
                back(uc, 0, 0x10)
            elif addr == PERCENT + 0x16:       # past the "no progress -> 0" exit: the building's own virtuals
                uc.reg_write(UC_X86_REG_ESP, sp + 8)   # pop edi, pop ebp as the getter's own exit does
                back(uc, percent, 4)
        for a in (SAY, PERCENT + 0x16):
            mu.hook_add(UC_HOOK_CODE, hook, begin=a, end=a)
        sp = stack - 0x100
        mu.mem_write(sp, struct.pack("<III", ret, 1, vil))     # handler(1 = mouse-over, villager)
        mu.reg_write(UC_X86_REG_ESP, sp)
        mu.emu_start(HANDLER, ret, count=10000)
        self.assertEqual(len(said), 1)
        return said[0]

    def test_foundation_construction_and_completed(self) -> None:
        stock = _stock()
        offset, _before, after = FIX
        fixed = stock[:offset] + after + stock[offset + len(after):]
        # Nothing built: the percent getter's own early exit returns 0.
        self.assertEqual(self._caption(stock, 0), CONSTRUCTION)            # the base game: always construction
        self.assertEqual(self._caption(fixed, 0), FOUNDATION)
        # Building started: the getter's percent.
        for percent in (2, 37, 99):
            self.assertEqual(self._caption(stock, 50, percent=percent), CONSTRUCTION)
            self.assertEqual(self._caption(fixed, 50, percent=percent), CONSTRUCTION)
        # Done: the completed line, both.
        for progress in (2000, 2050):
            self.assertEqual(self._caption(stock, progress), COMPLETED)
            self.assertEqual(self._caption(fixed, progress), COMPLETED)

    def test_with_the_patcher(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                data = _render(mode, _others() + (FEATURE,))
                self.assertEqual(self._caption(data, 0), FOUNDATION)
                self.assertEqual(self._caption(data, 50, percent=37), CONSTRUCTION)
                self.assertEqual(self._caption(data, 2000), COMPLETED)


if __name__ == "__main__":
    unittest.main()
