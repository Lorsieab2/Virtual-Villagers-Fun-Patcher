"""Fix Vanilla Bugs: the Overview Map's fire (The Lost Children).

The owner: "the fire graphic in the overview map in vv2 looks ugly, change it to the ones used in vv3-5 with
the same animations"; from the mockups: no "orange fake opaque circle glow", the village's own fire at The
Secret City's speed; "in stock the fire graphic sits in the stone circle already. no need to change anything"
(its place).

All four games ship the same firestrip.png (4 x 2 frames of 128 x 128).  The Lost Children's map objects
routine 0x41BAD0 (called by the Overview Map's draw 0x436C30) draws the fire inside its loop over the map's
objects (0x41C143..0x41C18B): frame 0 only, at the fixed screen spot (0x13B, 0xCD), at 25%, once per object
in the list.  So the fire never moves and its soft glow is laid over itself once per object into a solid
yellow blob.  The Secret City,
The Tree of Life and New Believers draw their burning fire once, as the effect their village view uses
(effect 9: firestrip, 8 frames in order, looping), where the village view places it, at the map's scale; The
Secret City moves it on one frame every 7 game frames (0x429710 counts to 6), The Tree of Life and New
Believers every 4 (0x41D430 / 0x41D950 count to 3).

The Lost Children's village fire is effect 11 (lit at 0x42EA4E, at (0x2B1, 0x2EE)): firestrip frames 0..6
(7 frames, 0x42301D; frame 7 is never shown), one frame every 7 game frames (the effects counter 0x42332A
counts to 6; a game frame is 33 ms, 0x4087AE) -- The Secret City's speed.  The game has no smoke art and its
fire spawns none.

The fix re-encodes the loop's end in place (0x41C143..0x41C19B, into the routine's own nop padding before
0x41C1A0): the loop ends first, then the fire is drawn once -- while it burns (the stock test of the fire
timer +0x2EAC4 against the clock 0x403200) -- as frame (SDL_GetTicks() / 231) mod 7, at 25%, at the map's
stock place and size, (0x13B, 0xCD) at 25% with the centring flag 1 (the shrunk frame is centred in the full
frame's box: on screen (363, 253), in the stone circle).  The routine's empty-list
exit (0x41BADB) now goes to the fire too, so it shows whenever it burns.

Everything here RUNS the stock and the patcher's rendered bytes in unicorn.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, load_fun_patches, render_patched_bytes  # noqa: E402

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESP
except ImportError:  # pragma: no cover
    pefile = None

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
FEATURE_ID = "vv2_fix_vanilla_bugs"
MODES = ("stock", "collection_progression", "immediate_fixed")

ROUTINE = 0x41BAD0          # the Overview Map's map objects, thiscall, no arguments
CLOCK = 0x403200            # the game's clock (the fire timer's units)
TICKS = 0x4679EA            # SDL_GetTicks thunk
DRAW = 0x409610             # sprite frame at a percent: (sprite, x, y, frame, percent, 1), ret 0x18
LOOP_TOP = 0x41BAF0
MAP_ORIGIN, VILLAGE_FIRE = (0xBE, 0x3E), (0x2B1, 0x2EE)
STOCK_AT = (0x13B, 0xCD)     # the corner of the full 128 x 128 frame; drawn centred at 25%: (363, 253)
FRAMES, MS_PER_FRAME = 7, 7 * 0x21

FIXES = (
    (0x1BADD, bytes.fromhex("B7060000"), bytes.fromhex("71060000")),
    (0x1C143, bytes.fromhex(
        "8B8F801600008B81C4EA020083C61485C07435E8A570FEFF8B8F801600003981C4EA020076228B97741600008B8F7C160000"
        "6A016A196A0068CD000000683B01000052E885D4FEFF8A46F484C00F855AF9FFFF5E5D5FC39090"), bytes.fromhex(
        "83C614807EF4000F85A0F9FFFF5E5DE8A970FEFF8B8F801600003981C4EA02007635E880B8040033D2B9E7000000F7F1"
        "6A075933D2F7F16A016A195268CD000000683B010000FFB7741600008B8F7C160000E876D4FEFF5FC3")),
)

# emulation layout
THIS, GAME, STK, RETURN = 0x10000000, 0x11000000, 0x20000000, 0x0BAD0000
FIRESTRIP, PAINTER, SKIP_SPRITE = 0x12000000, 0x12000100, 0x12000200
NO_STOCK = "the stock executable is not available"


def overview_map_fire_fixes(game: str) -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to <game>_fix_vanilla_bugs."""
    return FIXES if game == "vv2" else ()


def _have() -> bool:
    return pefile is not None and STOCK.is_file()


@functools.lru_cache(maxsize=None)
def _render(mode: str) -> bytes:
    build = next(b for b in load_builds() if b.id == "vv2")
    data, _ = render_patched_bytes(STOCK, build, mode, [FEATURE_ID])
    return bytes(data)


@functools.lru_cache(maxsize=None)
def _image(data: bytes) -> bytes:
    return pefile.PE(data=data).get_memory_mapped_image()


def run_map_objects(exe: bytes, objects: int, burning: bool, now: int = 5000, ticks: int = 0) -> list:
    """Run 0x41BAD0 on a list of `objects` map objects that draw nothing themselves (the stock passes over a
    sprite equal to +0x15E8 at frame 13 straight to the loop's end) and return every sprite draw made, as
    (painter, sprite, x, y, frame, percent, flag)."""
    image = _image(exe)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(0x400000, image)
    for base, size in ((THIS, 0x10000), (GAME, 0x40000), (STK - 0x10000, 0x10000), (RETURN, 0x1000),
                       (FIRESTRIP, 0x1000)):
        mu.mem_map(base, size)

    def w(at: int, value: int) -> None:
        mu.mem_write(at, struct.pack("<I", value & 0xFFFFFFFF))

    w(THIS + 0x15E8, SKIP_SPRITE)
    w(THIS + 0x1674, FIRESTRIP)
    w(THIS + 0x167C, PAINTER)
    w(THIS + 0x1680, GAME)
    w(GAME + 0x2EAC4, now + 100 if burning else now - 1)
    for k in range(objects + 1):
        entry = THIS + 0x1EC + 0x14 * k
        mu.mem_write(entry - 0xC, b"\1" if k < objects else b"\0")
        w(entry, SKIP_SPRITE)
        w(entry + 4, 13)
    draws = []

    def on_code(m, address, size, _):
        if address not in (CLOCK, TICKS, DRAW):
            return
        esp = m.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", m.mem_read(esp, 4))[0]
        pop = 0
        if address == CLOCK:
            m.reg_write(UC_X86_REG_EAX, now)
        elif address == TICKS:
            m.reg_write(UC_X86_REG_EAX, ticks)
            m.reg_write(UC_X86_REG_ECX, 0xDEAD)
        else:
            args = struct.unpack("<6I", m.mem_read(esp + 4, 24))
            draws.append((m.reg_read(UC_X86_REG_ECX),) + args)
            pop = 24
        m.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        m.reg_write(UC_X86_REG_EIP, ret)

    mu.hook_add(UC_HOOK_CODE, on_code)
    w(STK - 4, RETURN)
    mu.reg_write(UC_X86_REG_ESP, STK - 4)
    mu.reg_write(UC_X86_REG_ECX, THIS)
    mu.reg_write(UC_X86_REG_EDI, 0x5EED0001)
    mu.emu_start(ROUTINE, RETURN, count=100_000)
    assert mu.reg_read(UC_X86_REG_ESP) == STK
    assert mu.reg_read(UC_X86_REG_EDI) == 0x5EED0001
    return draws


@unittest.skipUnless(_have(), NO_STOCK)
class OverviewMapFireTests(unittest.TestCase):
    def test_stock_bytes_and_row(self) -> None:
        stock = STOCK.read_bytes()
        for offset, before, _after in FIXES:
            self.assertEqual(stock[offset:offset + len(before)], before)
        # the 4 bytes past the stock epilogue (pop edi; ret at 0x41C198) are padding before 0x41C1A0
        self.assertEqual(stock[0x1C198:0x1C1A0], bytes.fromhex("5FC3909090909090"))
        raw = next(p for p in load_fun_patches() if p.id == FEATURE_ID).raw
        rows = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])) for p in raw["patches"]]
        for fix in FIXES:
            self.assertIn(fix, rows)
        self.assertIn("The Overview Map's fire looks like the village's own fire", raw["description"])

    def test_fixed_code(self) -> None:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        listing = [(i.mnemonic, i.op_str) for i in md.disasm(FIXES[1][2], 0x41C143)]
        self.assertEqual(listing, [
            ("add", "esi, 0x14"), ("cmp", "byte ptr [esi - 0xc], 0"), ("jne", hex(LOOP_TOP)),
            ("pop", "esi"), ("pop", "ebp"),
            ("call", hex(CLOCK)), ("mov", "ecx, dword ptr [edi + 0x1680]"),
            ("cmp", "dword ptr [ecx + 0x2eac4], eax"), ("jbe", "0x41c19a"),
            ("call", hex(TICKS)), ("xor", "edx, edx"), ("mov", "ecx, 0xe7"), ("div", "ecx"),
            ("push", "7"), ("pop", "ecx"), ("xor", "edx, edx"), ("div", "ecx"),
            ("push", "1"), ("push", "0x19"), ("push", "edx"), ("push", "0xcd"), ("push", "0x13b"),
            ("push", "dword ptr [edi + 0x1674]"), ("mov", "ecx, dword ptr [edi + 0x167c]"), ("call", hex(DRAW)),
            ("pop", "edi"), ("ret", ""),
        ])
        je = next(md.disasm(STOCK.read_bytes()[0x1BADB:0x1BADD] + FIXES[0][2], 0x41BADB))
        self.assertEqual((je.mnemonic, je.op_str), ("je", "0x41c152"))

    def test_nothing_else_branches_into_the_rewritten_block(self) -> None:
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        incoming = set()
        for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            if ins.mnemonic.startswith("j") or ins.mnemonic == "call":
                try:
                    target = int(ins.op_str, 16)
                except ValueError:
                    continue
                if 0x41C143 < target < 0x41C1A0 and not 0x41C143 <= ins.address < 0x41C1A0:
                    incoming.add((hex(ins.address), hex(target)))
        # only the empty-list exit, which the fix retargets to 0x41C152
        self.assertEqual(incoming, {("0x41badb", "0x41c198")})

    def test_stock_draws_frame_0_once_per_object(self) -> None:
        stock = STOCK.read_bytes()
        draws = run_map_objects(stock, 12, True)
        self.assertEqual(draws, [(PAINTER, FIRESTRIP) + STOCK_AT + (0, 25, 1)] * 12)
        self.assertEqual(run_map_objects(stock, 12, True, ticks=999_999), draws)   # never animates
        self.assertEqual(run_map_objects(stock, 0, True), [])
        self.assertEqual(run_map_objects(stock, 12, False), [])

    def test_fixed_draws_the_village_frames_in_turn_once_in_the_stock_place(self) -> None:
        for mode in MODES:
            exe = _render(mode)
            for objects in (0, 1, 12):
                with self.subTest(mode=mode, objects=objects):
                    self.assertEqual(run_map_objects(exe, objects, False), [])
                    frames = []
                    for k in range(15):
                        draws = run_map_objects(exe, objects, True, ticks=k * MS_PER_FRAME + 50)
                        self.assertEqual(len(draws), 1)
                        painter, sprite, x, y, frame, percent, flag = draws[0]
                        self.assertEqual((painter, sprite, (x, y), percent, flag),
                                         (PAINTER, FIRESTRIP, STOCK_AT, 25, 1))
                        frames.append(frame)
                    self.assertEqual(frames, [k % FRAMES for k in range(15)])
                    # a frame lasts 231 ms
                    self.assertEqual(run_map_objects(exe, objects, True, ticks=MS_PER_FRAME - 1)[0][4], 0)
                    self.assertEqual(run_map_objects(exe, objects, True, ticks=MS_PER_FRAME)[0][4], 1)

    def test_the_place_stays_the_stock_one_in_the_stone_circle(self) -> None:
        # The owner: "in stock the fire graphic sits in the stone circle already".  The fix keeps the stock
        # (315, 205), 25% and the flag 1: with it the scaled draw (0x409610 -> 0x408DA0 -> 0x408160, the
        # branch at 0x4081E4) treats (x, y) as the corner of the full-size frame and centres the shrunk frame
        # in it, so the 32 x 32 fire shows at (363, 253), in the stone circle: the village fire (effect 11 at
        # (0x2B1, 0x2EE)) at 1/4 from the map's box (0xBE, 0x3E) is (362, 249), 1 and 4 map pixels away.  (A first mockup forgot the centring and drew the shrunk frame from
        # (315, 205): 48 pixels up and left, on a dirt patch.)
        image = _image(STOCK.read_bytes())

        def at(va: int, n: int) -> bytes:
            return image[va - 0x400000:va - 0x400000 + n]

        self.assertEqual(at(0x41C175, 15), bytes.fromhex("6A016A196A0068CD000000683B0100"))   # the stock push list
        fixed = FIXES[1][2]
        self.assertIn(bytes.fromhex("6A016A195268CD000000683B010000"), fixed)            # the same, frame in edx
        self.assertEqual(at(0x4081E4, 3), bytes.fromhex("803A00"))       # the centring flag's test
        shown = (STOCK_AT[0] + (128 - 32) // 2, STOCK_AT[1] + (128 - 32) // 2)
        self.assertEqual(shown, (363, 253))
        pit = (MAP_ORIGIN[0] + VILLAGE_FIRE[0] // 4, MAP_ORIGIN[1] + VILLAGE_FIRE[1] // 4)
        self.assertEqual((shown[0] - pit[0], shown[1] - pit[1]), (1, 4))   # within a few map pixels of the village fire
        self.assertEqual(at(0x42EA56, 18), bytes.fromhex("B9EE020000518B4E08B8B1020000506A0BE8"))
        self.assertEqual(at(0x436433, 14), bytes.fromhex("C746603E000000C7465CBE000000"))
        # the village fire: 7 frames (0x42301D), one every 7 game frames (0x42332A counts to 6), 33 ms a frame
        self.assertEqual(at(0x42301D, 7), bytes.fromhex("C7421807000000"))
        self.assertEqual(at(0x42332A, 3), bytes.fromhex("83F806"))
        self.assertEqual(at(0x4087AE, 7), bytes.fromhex("C7467421000000"))
        self.assertEqual(MS_PER_FRAME, 231)

if __name__ == "__main__":
    unittest.main()
