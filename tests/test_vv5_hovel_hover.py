"""New Believers' Fix Vanilla Bugs: a villager held over The Last Heathen's old mud hut says a line once it is fixed up.

The owner (2026-11-25), with The Blind Totem's line: when a villager is held over the finished mud hut (the Heathen
hovel) after The Last Heathen is solved, "name sees the decorated encampment"; when the hovel memorial is active,
"name sees a heartfelt memorial." (2026-11-26: "...the message should say name sees a heartfelt memorial shrine.").  Before The Last Heathen is solved, the game's own behaviour.

A held villager over a place no area handler takes (the hover dispatcher 0x479780 answers 0) goes to the point-hover
routine 0x444310 (0x4462CD -> 0x444306).  It names a heathen hut by its area (10..14), else the villager under the
point (0x470450), else deep water (0x477820 = 5); anything else says nothing, and the mud hut (x 2152..2287, y
1464..1599, the hut in the cover picture at (1702, 1465)) is none of these, so the game says nothing there, solved or
not.  The Last Heathen (project 25, CConvertLastHeathenPuzzle) is done once the villagers have fixed up the mud hut;
the game then draws its flower cover (0x4370E0).  Memorial Actions Can Also Occur at the Heathen Hovel
(vv5_hovel_memorial_actions) makes the fixed-up hut a memorial from that moment; it is known by its own byte, the
Reflecting registration's push at 0x46409E (stock 0x457E90, the row 0x494DE1).

The fix hooks the "no villager under the point" branch (0x444568, reached only by its je at 0x444438): with project 25
done and the point in the hut, the gray bar shows "{name} sees the decorated encampment." (or "{name} sees a heartfelt
memorial shrine." with the memorial row) through the game's own {name} substitution 0x450710 (entered after its text-table
lookup, 0x45078A, with the patch's own text) and 0x44F060's 5-second clock, then the routine's own exit 0x444598;
otherwise the displaced instructions and the stock deep-water test run as before.  Its pieces sit in .text tail
padding no other patch uses.  The game's lines are "{name} sees the remnants of a totem." and the like, so the
owner's wording takes that form.
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
FEATURE, MEMORIAL = "vv5_fix_vanilla_bugs", "vv5_hovel_memorial_actions"
BASE = 0x400000
MODES = ("stock", "collection_progression", "immediate_fixed")

# The pieces sit in .text tail padding that no manifest claims and no rendered build writes (the Origins carrier
# block ends at 0x4946DB).
FIXES = (
    (0x44568, "5355B9E88E7100", "E9BFFE04009090"),
    (0x9442C, "00" * 52, "6A19B908E05100E8486AFAFF84C0741F8D8598F7FFFF3D8800000073128D8348FAFFFF3D880000007305E979"
                         "FFFFFFE9B0010000"),
    (0x94610, "00" * 12, "5355B9E88E7100E953FFFAFF"),
    (0x943D4, "00" * 42, "B818484900803D9F404600E17505B8805F4C006A016A006A0031C9398F901B00000F94C151E9D20B0000"),
    (0x94FD0, "00" * 44, "8D979C1B0000526A0068FF00000068680F5200E830F5FFFFE86309F9FF89C1E8ECE6F6FF83C005E94CF5FFFF"),
    (0x94548, "00" * 10, "A368105200E94600FBFF"),
    (0x94518, "00" * 32, "81EC80000000890424A1A8974D0031E08944247C8B8C249C000000E980000000"),
    (0x945B8, "00" * 31, "8B9424840000008B842490000000894C2410895424148944240CE9B3C1FBFF"),
    (0x94818, "00" * 38, b"{name} sees the decorated encampment.\0".hex().upper()),
    # "...memorial shrine." (the owner, 2026-11-26) is 41 bytes: past its old 34-byte place at 0x4946DD (0x494700 is the
    # Puzzle 17 chain's), so it is in the zero tail of .rdata's last page, 0x4C5F80 (the respectful cover's name is at
    # 0x4C5FD0, Fix Vanilla Bugs' "eTipDemo" at 0x4C5FF0).
    (0xC5F80, "00" * 41, b"{name} sees a heartfelt memorial shrine.\0".hex().upper()),
)
FIXES = tuple((o, bytes.fromhex(b), bytes.fromhex(a)) for o, b, a in FIXES)
HOVER, BAR, BAR_CLOCK = 0x444310, 0x520F68, 0x521068
RECORD, AREA_AT, VILLAGER_AT, WATER_AT, SAY_NAME = 0x46F950, 0x477840, 0x470450, 0x477820, 0x44F060
GAME, CLOCK, SUBSTITUTE = 0x425950, 0x4036E0, 0x450710
PROJECTS, THRESHOLDS, LAST_HEATHEN = 0x51E008, 0x51DF30, 25
HUT = (2152, 2288, 1464, 1600)                 # x from, x to (not included), y from, y to
ENCAMPMENT = b"Aipi sees the decorated encampment."
HEARTFELT = b"Aipi sees a heartfelt memorial shrine."


def hovel_hover_fixes() -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to vv5_fix_vanilla_bugs (after the Blind Totem's)."""
    return FIXES


@functools.lru_cache(maxsize=None)
def _stock() -> bytes:
    return STOCK.read_bytes()


def _fixed() -> bytes:
    data = bytearray(_stock())
    for offset, _before, after in FIXES:
        data[offset:offset + len(after)] = after
    return bytes(data)


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


def _without_memorial() -> tuple:
    """The other rows less the memorial row and every row that requires it (its requirement lines name it)."""
    import vv_fun_patcher as fp
    catalog = fp.load_fun_patches()
    by_id = {p.id: p for p in catalog}
    name = by_id[MEMORIAL].name
    return tuple(i for i in _others()
                 if i != MEMORIAL and not any(name in line for line in fp.patch_requirements(by_id[i], catalog)))


@functools.lru_cache(maxsize=None)
def _image(data: bytes) -> bytes:
    import pefile
    return pefile.PE(data=data, fast_load=True).get_memory_mapped_image()


class Manifest(unittest.TestCase):
    def test_the_row_carries_the_fix_and_says_so(self) -> None:
        from vv_fun_patcher import load_fun_patches
        row = next(p for p in load_fun_patches() if p.id == FEATURE).raw
        pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"]))
                  for p in row["patches"][1:1 + len(FIXES)]]
        self.assertEqual(pinned, list(FIXES))
        self.assertIn("sees the decorated encampment.", row["description"])
        self.assertIn("sees a heartfelt memorial shrine.", row["description"])
        self.assertTrue(row["description"].endswith("**Needs no other patch.**"))

    def test_the_texts_are_translatable(self) -> None:
        import vv_translations as vt
        rows = {r["stem"]: r for r in vt.load_patcher_strings()}
        self.assertEqual(rows["patch/0x494818"]["english"], "{name} sees the decorated encampment.")
        self.assertEqual(rows["patch/0x4c5f80"]["english"], "{name} sees a heartfelt memorial shrine.")


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Stock(unittest.TestCase):
    def test_the_stock_bytes_and_what_they_rest_on(self) -> None:
        raw = _stock()
        for offset, before, after in FIXES:
            with self.subTest(offset=hex(offset)):
                self.assertEqual(raw[offset:offset + len(before)], before)
                self.assertEqual(len(after), len(before))
        img = _image(raw)
        at = lambda va, n: img[va - BASE:va - BASE + n]  # noqa: E731
        # The branch the hook replaces: push ebx; push ebp; mov ecx, 0x718EE8; call 0x477820; cmp eax, 5.
        self.assertEqual(at(0x444568, 15), bytes.fromhex("5355B9E88E7100E8AC32030083F805"))
        # The routine's exit the fix leaves by: pop ebp; pop ebx; pop edi; pop esi; ret 8.
        self.assertEqual(at(0x444598, 7), bytes.fromhex("5D5B5F5EC20800"))
        # 0x44F060's call of the substitution and its tail, which the fix repeats with its own text.
        self.assertEqual(at(0x44F07F, 6), bytes.fromhex("68FF00000056"))
        self.assertEqual(at(0x44F091, 22), bytes.fromhex("E8BA68FDFF8BC8E84346FBFF83C005898600010000"
                                                          "5E"))
        # 0x450710's prologue up to its text lookup (the thunk is the same with the text given), and its ret 0x20.
        self.assertEqual(at(SUBSTITUTE, 0x26), bytes.fromhex(
            "81EC80000000A1A8974D0033C48944247C8B8C249C0000008B9424840000008B842490000000"))
        # ... [esp+0x10] = arg 7, [esp+0x14] = the bar (edx, kept to 0x45078A), [esp+0xC] = the name, [esp] = text.
        self.assertEqual(at(0x450736, 4), bytes.fromhex("894C2410"))
        self.assertEqual(at(0x450743, 8), bytes.fromhex("895424148944240C"))
        self.assertEqual(at(0x450776, 3), bytes.fromhex("890C24"))
        self.assertEqual(at(0x45078A, 4), bytes.fromhex("53555689"))
        self.assertEqual(at(0x450A4E, 3), bytes.fromhex("C22000"))
        # The memorial row's own byte: the Reflecting registration's push.
        self.assertEqual(at(0x46409E, 5), bytes.fromhex("68907E4500"))

    def test_nothing_else_jumps_into_the_hook_or_the_pieces(self) -> None:
        import capstone
        raw = _stock()
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.skipdata = True
        inside = [(BASE + o + (1 if o == 0x44568 else 0), BASE + o + len(a)) for o, _b, a in FIXES]
        refs = []
        for i in md.disasm(raw[0x1000:0x95000], 0x401000):
            if i.mnemonic.startswith("j") or i.mnemonic == "call":
                try:
                    target = int(i.op_str, 16)
                except ValueError:
                    continue
                if any(a <= target < b for a, b in inside):
                    refs.append(i.address)
        self.assertEqual(refs, [])


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Modes(unittest.TestCase):
    def test_alone_with_the_others_and_without_in_every_mode(self) -> None:
        others = _others()
        for mode in MODES:
            with self.subTest(mode=mode):
                for data in (_render(mode, (FEATURE,)), _render(mode, others + (FEATURE,)),
                             _render(mode, others + (FEATURE, MEMORIAL))):
                    for offset, _before, after in FIXES:
                        self.assertEqual(data[offset:offset + len(after)], after, hex(offset))
                without = _render(mode, others)
                for offset, before, _after in FIXES:
                    self.assertEqual(without[offset:offset + len(before)], before, hex(offset))


class _Emulator:
    """The real point-hover routine 0x444310 and the game's real {name} substitution in unicorn."""

    STACK, VIL, THIS, RET, GAMEOBJ = 0x0F000000, 0x0E000000, 0x0E800000, 0x0DEAD000, 0x0C000000

    def __init__(self, data: bytes) -> None:
        from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
        img = _image(data)
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (len(img) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, img)
        for a in (self.STACK - 0x10000, self.VIL, self.THIS, self.RET, self.GAMEOBJ):
            mu.mem_map(a, 0x10000 if a == self.STACK - 0x10000 else 0x4000)
        vil = bytearray(0x4000)
        struct.pack_into("<iI", vil, 0x1B8C, 0x200, 1)          # an adult woman
        vil[0x1B9C:0x1BA1] = b"Aipi\0"
        mu.mem_write(self.VIL, bytes(vil))
        mu.mem_write(self.THIS + 0x58, struct.pack("<I", 7))
        self.water = False
        self.said: list = []
        for a in (RECORD, AREA_AT, VILLAGER_AT, WATER_AT, SAY_NAME, GAME, CLOCK):
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
        if addr == RECORD:
            self._back(self.VIL, 4)
        elif addr == AREA_AT:
            self._back(0, 8)                                        # no heathen hut here
        elif addr == VILLAGER_AT:
            self._back(0, 16)                                       # nobody under the point
        elif addr == WATER_AT:
            self._back(5 if self.water else 0, 8)
        elif addr == SAY_NAME:
            self.said.append(struct.unpack("<I", uc.mem_read(sp + 4, 4))[0])
            self._back(0, 16)
        elif addr == GAME:
            self._back(self.GAMEOBJ, 0)
        elif addr == CLOCK:
            self._back(1000, 0)

    def solved(self, done: bool) -> None:
        self.mu.mem_write(PROJECTS + 8 * LAST_HEATHEN, struct.pack("<i", 1 if done else 0))
        self.mu.mem_write(THRESHOLDS + 4 * LAST_HEATHEN, struct.pack("<i", 1))

    def hover(self, x: int, y: int, water: bool = False) -> tuple:
        from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP
        self.water, self.said = water, []
        self.mu.mem_write(BAR, b"\0" * 0x104)
        sp = self.STACK - 0x400
        self.mu.mem_write(sp, struct.pack("<III", self.RET, x, y))
        self.mu.reg_write(UC_X86_REG_ESP, sp)
        self.mu.reg_write(UC_X86_REG_ECX, self.THIS)
        self.mu.emu_start(HOVER, self.RET, count=200000)
        assert self.mu.reg_read(UC_X86_REG_ESP) == sp + 12          # ret 8
        bar = bytes(self.mu.mem_read(BAR, 0x100))
        clock = struct.unpack("<I", self.mu.mem_read(BAR_CLOCK, 4))[0]
        return bar[:bar.index(b"\0")], clock, self.said


@unittest.skipUnless(STOCK.is_file(), "stock executables are not available")
class Emulated(unittest.TestCase):
    INSIDE = ((2152, 1464), (2287, 1599), (2220, 1530))
    OUTSIDE = ((2151, 1530), (2288, 1530), (2220, 1463), (2220, 1600), (1800, 1600))

    def test_stock_says_nothing_at_the_hut(self) -> None:
        emu = _Emulator(_stock())
        for done in (False, True):
            emu.solved(done)
            for x, y in self.INSIDE:
                self.assertEqual(emu.hover(x, y), (b"", 0, []))

    def _check(self, data: bytes, line: bytes) -> None:
        emu = _Emulator(data)
        emu.solved(False)
        for x, y in self.INSIDE + self.OUTSIDE:
            self.assertEqual(emu.hover(x, y), (b"", 0, []), (x, y))
        emu.solved(True)
        for x, y in self.INSIDE:
            self.assertEqual(emu.hover(x, y), (line, 1005, []), (x, y))
        for x, y in self.OUTSIDE:
            self.assertEqual(emu.hover(x, y), (b"", 0, []), (x, y))
        # The stock path behind the hook is intact: deep water still says its line (0xF1).
        for done in (False, True):
            emu.solved(done)
            self.assertEqual(emu.hover(1800, 1600, water=True), (b"", 0, [0xF1]))

    def test_fixed_after_the_last_heathen(self) -> None:
        self._check(_fixed(), ENCAMPMENT)

    def test_with_the_memorial_row(self) -> None:
        data = bytearray(_fixed())
        data[0x6409E:0x640A3] = bytes.fromhex("68E14D4900")             # the memorial row's own push
        self._check(bytes(data), HEARTFELT)

    def test_with_the_patcher(self) -> None:
        others, without = _others(), _without_memorial()
        for mode in MODES:
            with self.subTest(mode=mode):
                self._check(_render(mode, without + (FEATURE,)), ENCAMPMENT)
                self._check(_render(mode, others + (FEATURE, MEMORIAL)), HEARTFELT)
                emu = _Emulator(_render(mode, without))
                emu.solved(True)
                self.assertEqual(emu.hover(2220, 1530), (b"", 0, []))


if __name__ == "__main__":
    unittest.main()
