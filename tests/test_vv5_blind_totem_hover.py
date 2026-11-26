"""New Believers' Fix Vanilla Bugs: a villager held over The Blind Totem says something, as over every other totem.

The owner (2026-11-25): "please add a fix for people to see the blind totem like the others when villagers are
hovered over them".

While the player drags a villager, the mouse-move handler (0x4462CD) calls the hover dispatcher 0x479780: it finds
the map area under the villager (0x477860) and calls that area's handler (the registry 0x77DC80, 12 bytes an area,
filled by 0x479810) with message 1; message 0 is a drop (0x4794A0) and 2 a click (0x479740).  Each totem registers
its own area, and its message-1 case shows a line: The Hungry Totem (area 0x13, 0x439540) "The Hungry Totem should
be torn down." while unsolved and "{name} sees the remnants of a totem." once solved, and the same for The Knowing
(0x14, 0x43C250), Blocking (0x17, 0x433150), Hollow (0x1A, 0x433740), Pain (0x16, 0x43A5B0) and Rainbow (0x1E,
0x43B920) Totems.

The Blind Totem (CClosedEyeTotemPuzzle, puzzle 15) registers its totem as area 0x2D with the handler 0x434520
(0x4345A3: 0x479810(0x2D, 0x434520, 6, 0)).  Its drop and click cases say string 0x74 eSayMissingEye "It's missing
its eye" while unsolved, but its hover case (0x434554-0x434562) only asks whether the puzzle is solved
(0x43AE80(0xF)), drops the answer and returns: nothing is shown.  The game ships the two lines it was meant for and
never uses them: 0x256 eSayTotemNeedsEye "The totem is missing its eye." and 0x257 eSayTotemShinyEye "The totem
has a shiny eye!" (no code pushes either id).

The fix rewrites the handler in place, 0x434520-0x434569 (its own 67 bytes and 7 of the int3 bytes after it, no
other code jumps there): the drop and click cases are the stock ones (0x74 while unsolved, nothing once solved,
nothing for any other message); the hover case shows 0x256 + solved through the same caption routine the other
totems' unsolved lines use, 0x44EF60(id, -1).
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

FIX = (0x34520,
       bytes.fromhex("8B44240483E800740A83E801742683E801751E6A0FB908E05100E84169000084C0750E6AFF6A74B9680F5200"
                     "E80FAA0100B001C36A0FB908E05100E820690000B001C3" + "CC" * 7),
       bytes.fromhex("8B44240483F801741DA9FDFFFFFF75376A0FB908E05100E84469000084C075276AFF6A74EB176A0FB908E051"
                     "00E82E6900000FB6C06AFF055602000050B9680F5200E8F9A90100B001C3"))
HANDLER, AREA, PUZZLE = 0x434520, 0x2D, 0xF
HOVER_DISPATCH, POSITION, AREA_AT, REGISTER = 0x479780, 0x466350, 0x477860, 0x479810
DONE, SAY, SAY_NAME = 0x43AE80, 0x44EF60, 0x44F060
PROJECTS, THRESHOLDS = 0x51E008, 0x51DF30
MISSING_EYE, NEEDS_EYE, SHINY_EYE, REMNANTS = 0x74, 0x256, 0x257, 0x254
DROP, HOVER, CLICK = 0, 1, 2
# The other totems' own areas: (name, area, handler, the registry's two numbers, puzzle, its "should be torn
# down" line), each registered as 0x479810(area, handler, a, b) by its totem's constructor.
TOTEMS = (("The Hungry Totem", 0x13, 0x439540, 6, 0, 3, 0x250),
          ("The Knowing Totem", 0x14, 0x43C250, 6, 0, 4, 0x24F),
          ("The Blocking Totem", 0x17, 0x433150, 6, 0, 7, 0x251),
          ("The Hollow Totem", 0x1A, 0x433740, 6, 1, 8, 0x253),
          ("The Pain Totem", 0x16, 0x43A5B0, 2, 0, 11, 0x25B),
          ("The Rainbow Totem", 0x1E, 0x43B920, 6, 0, 12, 0x252))


def blind_totem_hover_fixes() -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to vv5_fix_vanilla_bugs (first in its list)."""
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


@functools.lru_cache(maxsize=None)
def _image(data: bytes) -> bytes:
    import pefile
    return pefile.PE(data=data, fast_load=True).get_memory_mapped_image()


def _texts(img: bytes) -> dict:
    out = {}
    for k in range(1409):
        i, _name, text, _ = struct.unpack_from("<4I", img, 0x4D31F0 - BASE + 16 * k)
        out[i] = img[text - BASE:img.index(b"\0", text - BASE)]
    return out


class Manifest(unittest.TestCase):
    def test_the_row_carries_the_fix_and_says_so(self) -> None:
        from vv_fun_patcher import load_fun_patches
        row = next(p for p in load_fun_patches() if p.id == FEATURE).raw
        first = row["patches"][0]
        self.assertEqual((int(first["offset"], 16), bytes.fromhex(first["before"]), bytes.fromhex(first["after"])),
                         FIX)
        self.assertIn("The Blind Totem says something when a villager is held over it", row["description"])
        self.assertTrue(row["description"].endswith("**Needs no other patch.**"))
        self.assertTrue(any(c.startswith("The Blind Totem's area handler 0x434520") for c in row["behavior_changes"]))


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Stock(unittest.TestCase):
    def test_the_stock_block_and_what_it_rests_on(self) -> None:
        import pefile
        raw = _stock()
        offset, before, after = FIX
        self.assertEqual(len(after), len(before))
        self.assertEqual(raw[offset:offset + len(before)], before)
        self.assertEqual(pefile.PE(data=raw, fast_load=True).get_offset_from_rva(offset), offset)
        img = _image(raw)
        at = lambda va, n: img[va - BASE:va - BASE + n]  # noqa: E731
        # The done getter: [0x51E008 + 8 n] >= [0x51DF30 + 4 n], setge al, ret 4.
        self.assertEqual(at(DONE, 20), bytes.fromhex("8B4424048B0CC13B0C8530DF51000F9DC0C20400"))
        # The caption routine's text id and its argument (-1: no number), ret 8.
        self.assertEqual(at(SAY, 4), bytes.fromhex("56578B7C"))
        self.assertEqual(at(0x44F002, 3), bytes.fromhex("C20800"))
        # The Blind Totem's three areas, registered by its constructor 0x434570 (CClosedEyeTotemPuzzle).
        self.assertEqual(at(0x434578, 6), bytes.fromhex("C706DC974900"))
        self.assertEqual(at(0x4345A3, 11), bytes.fromhex("6A006A066820454300") + bytes((0x6A, AREA)))
        self.assertEqual(at(0x4345AE, 1), b"\xE8")
        self.assertEqual(0x4345B3 + struct.unpack_from("<i", img, 0x4345AF - BASE)[0], REGISTER)
        # The other totems' own areas.
        for name, area, handler, a, b, _puzzle, _line in TOTEMS:
            with self.subTest(totem=name):
                site = bytes((0x6A, b, 0x6A, a, 0x68)) + struct.pack("<I", handler) + bytes((0x6A, area, 0xE8))
                self.assertTrue(site in img[0x432000 - BASE:0x43D000 - BASE])
        texts = _texts(img)
        self.assertEqual(texts[MISSING_EYE], b"It's missing its eye")
        self.assertEqual(texts[NEEDS_EYE], b"The totem is missing its eye.")
        self.assertEqual(texts[SHINY_EYE], b"The totem has a shiny eye!")
        self.assertEqual(texts[REMNANTS], b"{name} sees the remnants of a totem.")
        self.assertEqual(texts[0x250], b"The Hungry Totem should be torn down.")

    def test_the_two_lines_are_never_used(self) -> None:
        import capstone
        img = _image(_stock())
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.skipdata = True
        md.detail = True
        used = set()
        for i in md.disasm(img[0x1000:0x98000], BASE + 0x1000):
            if i.mnemonic in ("push", "mov") and i.operands and i.operands[-1].type == capstone.CS_OP_IMM:
                if i.operands[-1].imm in (NEEDS_EYE, SHINY_EYE, 0x250, REMNANTS):
                    used.add(i.operands[-1].imm)
        self.assertIn(0x250, used)
        self.assertIn(REMNANTS, used)
        self.assertNotIn(NEEDS_EYE, used)
        # 0x257 appears once as a widget number (0x43DC0A, the Collections screen), never as a text id.
        img_fixed = _image(_fixed())
        self.assertIn(bytes.fromhex("0556020000"), img_fixed[HANDLER - BASE:HANDLER - BASE + 0x4A])

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
                if HANDLER < target < HANDLER + 0x50 and not HANDLER <= i.address < HANDLER + 0x43:
                    refs.append(i.address)
        self.assertEqual(refs, [])
        # Only the registry holds the handler's address (the constructor's push), nothing else.
        self.assertEqual(raw.count(struct.pack("<I", HANDLER)), 1)

    def test_the_fixed_code(self) -> None:
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        offset, _before, after = FIX
        text = [f"{i.mnemonic} {i.op_str}".strip() for i in md.disasm(after, BASE + offset)]
        self.assertEqual(text, [
            "mov eax, dword ptr [esp + 4]", "cmp eax, 1", "je 0x434546", "test eax, 0xfffffffd", "jne 0x434567",
            "push 0xf", "mov ecx, 0x51e008", "call 0x43ae80", "test al, al", "jne 0x434567",
            "push -1", "push 0x74", "jmp 0x43455d",
            "push 0xf", "mov ecx, 0x51e008", "call 0x43ae80", "movzx eax, al", "push -1", "add eax, 0x256",
            "push eax",
            "mov ecx, 0x520f68", "call 0x44ef60", "mov al, 1", "ret"])
        self.assertEqual(_fixed()[offset + len(after):offset + 0x50], b"\xCC" * (0x50 - len(after)))


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

    def test_a_changed_stock_byte_is_refused(self) -> None:
        import tempfile
        from vv_fun_patcher import PatcherError, load_builds, render_patched_bytes
        build = next(b for b in load_builds() if b.id == "vv5")
        offset, before, _after = FIX
        for k in (0, len(before) // 2, len(before) - 1):
            with self.subTest(byte=k), tempfile.TemporaryDirectory() as tmp:
                data = bytearray(_stock())
                data[offset + k] ^= 0x01
                exe = Path(tmp) / STOCK.name
                exe.write_bytes(bytes(data))
                with self.assertRaises(PatcherError):
                    render_patched_bytes(exe, build, "stock", [FEATURE])


class _Emulator:
    """The real code in unicorn: the registry filled by 0x479810, the hover dispatcher 0x479780 run for a villager
    standing on a given area, every line the caption routines are asked for recorded."""

    STACK, VIL, RET, POS = 0x0F000000, 0x0E000000, 0x0DEAD000, 0x0E800000

    def __init__(self, data: bytes) -> None:
        from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
        img = _image(data)
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (len(img) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, img)
        mu.mem_map(self.STACK - 0x10000, 0x10000)
        mu.mem_map(self.VIL, 0x4000)
        mu.mem_map(self.POS, 0x1000)
        mu.mem_map(self.RET, 0x1000)
        vil = bytearray(0x4000)
        struct.pack_into("<iI", vil, 0x1B8C, 0x200, 1)          # an adult (age 512 >= 0x118), female
        vil[0x1B9C:0x1BA2] = b"Aipi\0\0"
        mu.mem_write(self.VIL, bytes(vil))
        self.area = 0
        self.said: list = []
        for a in (SAY, SAY_NAME, POSITION, AREA_AT):
            mu.hook_add(UC_HOOK_CODE, self._hook, begin=a, end=a)

    def _back(self, eax: int, pop: int) -> None:
        from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP
        sp = self.mu.reg_read(UC_X86_REG_ESP)
        to = struct.unpack("<I", self.mu.mem_read(sp, 4))[0]
        self.mu.reg_write(UC_X86_REG_EAX, eax)
        self.mu.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        self.mu.reg_write(UC_X86_REG_EIP, to)

    def _hook(self, uc, addr, _size, _data) -> None:
        from unicorn.x86_const import UC_X86_REG_ESP
        sp = uc.reg_read(UC_X86_REG_ESP)
        if addr == SAY:
            self.said.append(struct.unpack("<Ii", uc.mem_read(sp + 4, 8)))
            self._back(0, 8)
        elif addr == SAY_NAME:
            text, name = struct.unpack("<II", uc.mem_read(sp + 4, 8))
            self.said.append((text, "name" if name == self.VIL + 0x1B9C else name))
            self._back(0, 16)
        elif addr == POSITION:                                    # the villager's map point
            self._back(self.POS, 4)
        elif addr == AREA_AT:                                     # the area at that point
            self._back(self.area, 8)

    def call(self, fn: int, *args: int, ecx: int = 0) -> int:
        from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP
        sp = self.STACK - 0x200
        self.mu.mem_write(sp, struct.pack(f"<{1 + len(args)}I", self.RET, *args))
        self.mu.reg_write(UC_X86_REG_ESP, sp)
        self.mu.reg_write(UC_X86_REG_ECX, ecx)
        self.mu.emu_start(fn, self.RET, count=200000)
        return self.mu.reg_read(UC_X86_REG_EAX) & 0xFF

    def solved(self, puzzle: int, solved: bool) -> None:
        self.mu.mem_write(PROJECTS + 8 * puzzle, struct.pack("<i", 5 if solved else 0))
        self.mu.mem_write(THRESHOLDS + 4 * puzzle, struct.pack("<i", 5))

    def register(self, area: int, handler: int, a: int, b: int) -> None:
        # As the constructors do: 0x479810(area, handler, a, b), cdecl.
        self.call(REGISTER, area, handler, a, b)

    def hover(self, area: int) -> tuple:
        self.area, self.said = area, []
        held = self.call(HOVER_DISPATCH, self.VIL, ecx=0x77DECC)
        return self.said, held

    def handler(self, message: int) -> tuple:
        self.said = []
        return self.said, self.call(HANDLER, message, self.VIL)


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Emulated(unittest.TestCase):
    def _emu(self, data: bytes) -> _Emulator:
        emu = _Emulator(data)
        emu.register(AREA, HANDLER, 6, 0)
        for _name, area, handler, a, b, _puzzle, _line in TOTEMS:
            emu.register(area, handler, a, b)
        return emu

    def test_stock_says_nothing_over_the_blind_totem(self) -> None:
        emu = self._emu(_stock())
        for solved in (False, True):
            emu.solved(PUZZLE, solved)
            self.assertEqual(emu.hover(AREA), ([], 1))

    def test_fixed_says_the_games_own_lines(self) -> None:
        emu = self._emu(_fixed())
        emu.solved(PUZZLE, False)
        self.assertEqual(emu.hover(AREA), ([(NEEDS_EYE, -1)], 1))
        emu.solved(PUZZLE, True)
        self.assertEqual(emu.hover(AREA), ([(SHINY_EYE, -1)], 1))

    def test_every_other_totem_says_a_line_on_the_same_path(self) -> None:
        for data in (_stock(), _fixed()):
            emu = self._emu(data)
            for name, area, _handler, _a, _b, puzzle, line in TOTEMS:
                with self.subTest(totem=name):
                    emu.solved(puzzle, False)
                    self.assertEqual(emu.hover(area), ([(line, -1)], 1))
                    emu.solved(puzzle, True)
                    # Once solved: "{name} sees the remnants of a totem."; the fallen Rainbow Totem says nothing.
                    solved = [] if area == 0x1E else [(REMNANTS, "name")]
                    self.assertEqual(emu.hover(area), (solved, 1))

    def test_drop_click_and_other_messages_are_the_stock_ones(self) -> None:
        stock, fixed = self._emu(_stock()), self._emu(_fixed())
        for solved in (False, True):
            for message in (DROP, CLICK, 3, 7, 0xFFFFFFFF, 0x80000002):
                with self.subTest(solved=solved, message=message):
                    stock.solved(PUZZLE, solved)
                    fixed.solved(PUZZLE, solved)
                    expect = ([(MISSING_EYE, -1)], 1) if message in (DROP, CLICK) and not solved else ([], 1)
                    self.assertEqual(stock.handler(message), expect)
                    self.assertEqual(fixed.handler(message), expect)

    def test_with_the_patcher(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                emu = self._emu(_render(mode, _others() + (FEATURE,)))
                emu.solved(PUZZLE, False)
                self.assertEqual(emu.hover(AREA), ([(NEEDS_EYE, -1)], 1))
                emu.solved(PUZZLE, True)
                self.assertEqual(emu.hover(AREA), ([(SHINY_EYE, -1)], 1))
                emu = self._emu(_render(mode, _others()))
                emu.solved(PUZZLE, False)
                self.assertEqual(emu.hover(AREA), ([], 1))


if __name__ == "__main__":
    unittest.main()
