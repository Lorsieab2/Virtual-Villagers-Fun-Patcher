"""New Believers' Fix Vanilla Bugs: clicking the finished Clothing Hut said "Construction 100% completed".

The owner (2026-11-22): "when the vv5 clothing hut is complete, remove the construction 100% complete message when
its clicked on".

Each building's area handler gets a message number: 0 a villager dropped on it, 1 a villager passing over it, 2 a
click.  On a click the three population huts (0x479E40 / 0x479F40 / 0x47A050), the love shack (0x47A150) and the
nursery school (0x43AA30) show string 0x96 eSayConstructionProgress "Construction %d%% completed" only while their
project has progress (0x43AEA0(n) >= 1 on the project table 0x51E008) and is not done (0x43AE80(n)); a finished one
shows nothing.  The Clothing Hut's handler 0x47A230 (area 9, project 0x16) skips the done test (0x47A24F-0x47A26F),
so a finished hut says "Construction 100% completed" on every click.

The fix rewrites the same 33 bytes in place, no cave: the done test 0x43AE80(0x16) first, done -> the handler's own
exit 0x47A280 (mov al,1 / pop esi / add esp,8 / ret, the same bytes as the stock exit 0x47A3DF the check jumped to);
then the stock progress 0x43AEA0(0x16), below 1 -> 0x47A280; the message call at 0x47A270 is the stock one.  An
island event that damages the hut (structure_damage.h: project 22 made unfinished again) makes the done test fail,
so its progress shows again.  Nothing else jumps into the block.

The Tree of Life's Clothing Hut (0x46F600) shows its "Cloth making percent completed:" line once finished and the
construction line only before; The Secret City's (0x469DBB, label 0x4B) tests done first; A New Home and The Lost
Children have no clothing hut and their population huts test done too (see the Stock class).
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

STOCK_DIR = ROOT / "research" / "stock-executables"
STOCK = STOCK_DIR / "Virtual Villagers - New Believers.exe"
FEATURE = "vv5_fix_vanilla_bugs"
BASE = 0x400000
MODES = ("stock", "collection_progression", "immediate_fixed")

FIX = (0x7A24F,
       bytes.fromhex("6A16B908E05100E8450CFCFF83F8010F8C7B0100006A16B908E05100E8300CFCFF"),
       bytes.fromhex("6A16B908E05100E8250CFCFF84C075216A16B908E05100E8350CFCFF83F8017C10"))
HANDLER, DONE, PERCENT, SAY = 0x47A230, 0x43AE80, 0x43AEA0, 0x44EF60
PROJECTS, THRESHOLDS, HUT = 0x51E008, 0x51DF30, 0x16
PROGRESS, THRESHOLD = PROJECTS + 8 * HUT, THRESHOLDS + 4 * HUT
CONSTRUCTION = 0x96
CLICK = 2


def clothing_hut_click_fixes() -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to vv5_fix_vanilla_bugs."""
    return (FIX,)


@functools.lru_cache(maxsize=None)
def _stock() -> bytes:
    return STOCK.read_bytes()


def _fixed() -> bytes:
    offset, _before, after = FIX
    stock = _stock()
    return stock[:offset] + after + stock[offset + len(after):]


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
        last = row["patches"][-1]
        self.assertEqual((int(last["offset"], 16), bytes.fromhex(last["before"]), bytes.fromhex(last["after"])), FIX)
        self.assertIn('Clicking the finished Clothing Hut no longer says "Construction 100% completed"',
                      row["description"])
        self.assertTrue(row["description"].endswith("**Needs no other patch.**"))

    def test_the_damage_effect_names_the_same_project(self) -> None:
        text = (ROOT / "native" / "shared" / "structure_damage.h").read_text(encoding="utf-8")
        self.assertIn("{ 22, 0x51DAB0u }", text)        # the clothing hut, project 22 = 0x16
        self.assertIn("{ SD_V5_BUILDINGS, 0x51E008u, 0x51DF30u,", text)


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Stock(unittest.TestCase):
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
        self.assertEqual(at(DONE, 20), bytes.fromhex("8B4424048B0CC13B0C8530DF51000F9DC0C20400"))
        # The exit the fix uses and the stock exit it replaces: mov al,1 / pop esi / add esp,8 / ret.
        self.assertEqual(at(0x47A280, 7), bytes.fromhex("B0015E83C408C3"))
        self.assertEqual(at(0x47A3DF, 7), bytes.fromhex("B0015E83C408C3"))
        # The stock message call after the block: push eax; push 0x96; mov ecx, 0x520F68; call 0x44EF60.
        self.assertEqual(at(0x47A270, 16), bytes.fromhex("506896000000B9680F5200E8E04CFDFF"))
        # Registered for area 9 (0x47A963: 0x479810(9, 0x47A230, 5, 1)).
        self.assertEqual(at(0x47A963, 11), bytes.fromhex("6A016A056830A247006A09"))
        texts = {}
        for k in range(1409):
            i, _name, text, _ = struct.unpack_from("<4I", img, 0x4D31F0 - BASE + 16 * k)
            if i == CONSTRUCTION:
                texts[i] = img[text - BASE:img.index(b"\0", text - BASE)]
        self.assertEqual(texts, {CONSTRUCTION: b"Construction %d%% completed"})

    def test_every_other_building_tests_done_before_the_line(self) -> None:
        img = _stock()
        # push n / mov ecx, 0x51E008 / call 0x43AE80 / test al,al / jne -- right before each one's progress line.
        for va, n in ((0x479E99, 0x13), (0x479F6B, 0x14), (0x47A07A, 0x15), (0x47A175, 0x17), (0x43AA63, 0x18)):
            with self.subTest(project=n):
                o = va - BASE
                self.assertEqual(img[o:o + 7], bytes((0x6A, n)) + bytes.fromhex("B908E05100"))
                self.assertEqual(img[o + 7], 0xE8)
                self.assertEqual(o + 12 + struct.unpack_from("<i", img, o + 8)[0], DONE - BASE)
                self.assertEqual(img[o + 12:o + 14], bytes.fromhex("84C0"))

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
                if 0x47A250 <= target <= 0x47A26F:
                    refs.append(i.address)
        self.assertEqual(refs, [])

    def test_the_other_games_already_test_done(self) -> None:
        def exe(name: str) -> bytes:
            return (STOCK_DIR / f"Virtual Villagers - {name}.exe").read_bytes()
        tol = exe("The Tree of Life")
        # 0x46F61F: push 0x16; mov ecx, 0x4D8BF8; call 0x438960 (done); test al,al; je -> construction line, else the
        # cloth-making line 0x7D.
        self.assertEqual(tol[0x6F61F:0x6F62F], bytes.fromhex("6A16B9F88B4D00E83593FCFF84C07419"))
        city = exe("The Secret City")
        # 0x469DD0: push 3; mov ecx, 0x594620; call 0x4321F0 (done); test al,al; jne exit; then label 0x4B.
        self.assertEqual(city[0x69DD0:0x69DE4], bytes.fromhex("6A03B920465900E81484FCFF84C00F85D0020000"))
        lost = exe("The Lost Children")
        # Each hut's line (0x4B/0x4C/0x4D) only while its built flag (+0x2E818/+0x2E820/+0x2E828) is 0.
        for at, flag, label in ((0x311EA, 0x2E818, 0x4B), (0x31209, 0x2E820, 0x4C), (0x31228, 0x2E828, 0x4D)):
            self.assertEqual(struct.unpack_from("<I", lost, at + 2)[0], flag)
            self.assertIn(bytes((0x6A, label)), lost[at:at + 20])
        home = exe("A New Home")
        # Built huts paint map type 0xC / 0xD (no line) instead of the sites' 0x28 / 0x29 (0x414ADE, 0x414BC3).
        self.assertEqual(home[0x14AD5:0x14AE0], bytes.fromhex("84C07409BFC00300006A0C"))
        self.assertEqual(home[0x14BB5:0x14BC5], bytes.fromhex("84C0740EB922040000BF9E0400006A0D"))


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Modes(unittest.TestCase):
    def test_alone_with_the_others_and_without_in_every_mode(self) -> None:
        offset, before, after = FIX
        others = _others()
        self.assertGreater(len(others), 10)
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertEqual(_render(mode, (FEATURE,))[offset:offset + len(after)], after)
                self.assertEqual(_render(mode, others + (FEATURE,))[offset:offset + len(after)], after)
                self.assertEqual(_render(mode, others)[offset:offset + len(before)], before)


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Emulated(unittest.TestCase):
    """The handler's click case run in unicorn: the messages it shows and what it returns."""

    def _click(self, data: bytes, progress: int, threshold: int = 2000, percent: int = 0) -> tuple:
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
                said.append(struct.unpack("<II", uc.mem_read(sp + 4, 8)))
                back(uc, 0, 8)
            elif addr == PERCENT + 0x16:       # past the "no progress -> 0" exit: the building's own virtuals
                uc.reg_write(UC_X86_REG_ESP, sp + 8)   # pop edi, pop ebp as the getter's own exit does
                back(uc, percent, 4)
        for a in (SAY, PERCENT + 0x16):
            mu.hook_add(UC_HOOK_CODE, hook, begin=a, end=a)
        sp = stack - 0x100
        mu.mem_write(sp, struct.pack("<III", ret, CLICK, vil))     # handler(2 = click, villager)
        mu.reg_write(UC_X86_REG_ESP, sp)
        mu.emu_start(HANDLER, ret, count=10000)
        self.assertEqual(mu.reg_read(UC_X86_REG_ESP), sp + 4)      # a plain ret: the caller cleans up
        return said, mu.reg_read(UC_X86_REG_EAX) & 0xFF

    def test_nothing_built_building_and_finished(self) -> None:
        stock, fixed = _stock(), _fixed()
        for data in (stock, fixed):
            self.assertEqual(self._click(data, 0), ([], 1))                     # nothing built: no line
            for percent in (1, 37, 99):                                          # being built (or damaged)
                self.assertEqual(self._click(data, 50, percent=percent), ([(CONSTRUCTION, percent)], 1))
        for progress in (2000, 2050):                                            # finished
            self.assertEqual(self._click(stock, progress, percent=100), ([(CONSTRUCTION, 100)], 1))   # the bug
            self.assertEqual(self._click(fixed, progress, percent=100), ([], 1))

    def test_damaged_again_shows_its_progress_again(self) -> None:
        # structure_damage.h lowers project 22's progress below its threshold: done fails, the line is back.
        fixed = _fixed()
        self.assertEqual(self._click(fixed, 2000, percent=100), ([], 1))
        self.assertEqual(self._click(fixed, 1400, percent=70), ([(CONSTRUCTION, 70)], 1))

    def test_with_the_patcher(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                data = _render(mode, _others() + (FEATURE,))
                self.assertEqual(self._click(data, 0), ([], 1))
                self.assertEqual(self._click(data, 50, percent=37), ([(CONSTRUCTION, 37)], 1))
                self.assertEqual(self._click(data, 2000, percent=100), ([], 1))


if __name__ == "__main__":
    unittest.main()
