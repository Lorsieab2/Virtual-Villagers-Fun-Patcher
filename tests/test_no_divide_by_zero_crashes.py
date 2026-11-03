"""Fix Vanilla Bugs: no divide-by-zero crash in the line drawer (The Secret City, The Tree of Life, New Believers).

The owner (Virtual Families chat): "Make sure the bank crash bug isnt in any game!!!"  Every integer
division in the five stock executables was audited (docs/reports/div-by-zero/NOTES.md); this is the
one whose divisor can be 0 from what the game itself does.

The engine's alpha line drawer -- The Secret City 0x403D20, The Tree of Life 0x404280, New Believers
0x404210 -- spreads the alpha change over the line by dividing it by the longer of 2|dx| and 2|dy|
(`idiv ebx` at 0x403EC4 / 0x404432 / 0x4043C2).  A line whose two ends are the same point divides
by 0 and the game stops.  Its callers are the rain (0x41F5F0 / 0x46B6D0 / 0x476730: each drop is a
line from its point to its previous point) and New Believers' lightning (0x41DBF0, which skips a
zero-length segment itself).  The rain initialiser (New Believers 0x4764C0, the same code in the
other two) sets each drop's point to (rand(800), rand(600)) but never its previous point, which the
rain object's constructor zeroes; a drop whose new point is its previous point is a zero-length line
until its first rain update moves it.  A New Home and The Lost Children have no line drawer.

The fix keeps the undivided step when both lengths are 0 (`test ebx, ebx; jz`), so the line is drawn
as its one point; every other line runs the base game's division.  The Tree of Life and New Believers
are rewritten in place (25 bytes); The Secret City's 13 bytes send the 2|dy| branch to an 11-byte
check in the unused padding at 0x4045A4.

Everything here RUNS the stock and the patcher's rendered bytes in unicorn.
"""
from __future__ import annotations

import functools
import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, load_fun_patches, render_patched_bytes  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_INTR, UC_MODE_32, Uc, UcError
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
except ImportError:  # pragma: no cover
    pefile = None

STOCK_DIR = ROOT / "research" / "stock-executables"
NAMES = {"vv3": "The Secret City", "vv4": "The Tree of Life", "vv5": "New Believers"}
MODES = ("stock", "collection_progression", "immediate_fixed")
BASE = 0x400000
HEAP, STK, PIX = 0x10000000, 0x20000000, 0x30000000
RETURN = 0x0BAD0000
WIDE_STOCK = bytes.fromhex("3BFB8BC2997E0AF7FF8BD089542444EB08F7FB8BD089442444")
WIDE_FIXED = bytes.fromhex("3BFB8BC2997E04F7FFEB0685DB7402F7FB8BD0894424446690")
FIXES = {
    "vv3": ((0x3EB9, bytes.fromhex("3BFB8BC2997E04F7FFEB02F7FB"), bytes.fromhex("3BFB8BC2990F8EE0060000F7FF")),
            (0x45A4, bytes.fromhex("9090909090909090909090"), bytes.fromhex("85DB7402F7FBE917F9FFFF"))),
    "vv4": ((0x4421, WIDE_STOCK, WIDE_FIXED),),
    "vv5": ((0x43B1, WIDE_STOCK, WIDE_FIXED),),
}
LINE = {"vv3": 0x403D20, "vv4": 0x404280, "vv5": 0x404210}           # the line drawer
DIVIDE = {"vv3": 0x403EC4, "vv4": 0x404432, "vv5": 0x4043C2}         # its idiv ebx
RAIN = {  # draw routine, intensity float, graphics global, camera x / y
    "vv3": (0x41F5F0, 0x4B86EC, 0x4B34A8, 0x580A6C, 0x580A70),
    "vv4": (0x46B6D0, 0x6C4648, 0x4CB928, 0x72563C, 0x725640),
    "vv5": (0x476730, 0x718ECC, 0x4DB0E8, 0x7B00B4, 0x7B00B8),
}
RAND = {"vv3": 0x4032D0, "vv4": 0x4036D0, "vv5": 0x403660}         # the game's rand(n), answered 0 here
NO_STOCK = "stock executables are not available"


def zero_length_line_fixes(game: str) -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to <game>_fix_vanilla_bugs."""
    return FIXES.get(game, ())


def _stock_path(game: str) -> Path:
    return STOCK_DIR / f"Virtual Villagers - {NAMES[game]}.exe"


def _have(game: str) -> bool:
    return pefile is not None and _stock_path(game).is_file()


@functools.lru_cache(maxsize=None)
def _build(game: str):
    return next(b for b in load_builds() if b.id == game)


@functools.lru_cache(maxsize=None)
def _render(game: str, mode: str) -> bytes:
    data, _ = render_patched_bytes(_stock_path(game), _build(game), mode, [f"{game}_fix_vanilla_bugs"])
    return bytes(data)


@functools.lru_cache(maxsize=None)
def _stock(game: str) -> bytes:
    return _stock_path(game).read_bytes()


class _Machine:
    """The mapped executable, the engine's surface wrapper and the SDL calls the drawer makes."""

    def __init__(self, data: bytes, rand: int = 0) -> None:
        self.rand = rand
        pe = pefile.PE(data=data)
        image = pe.get_memory_mapped_image()
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, image)
        for area in (HEAP, STK, PIX):
            mu.mem_map(area, 0x400000)
        mu.mem_map(RETURN, 0x1000)
        self.imports = {imp.address: (imp.name or b"?").decode()
                        for entry in pe.DIRECTORY_ENTRY_IMPORT for imp in entry.imports}
        self.calls: list[str] = []
        self.interrupt: int | None = None
        self.mu = mu
        self.hooks = [mu.hook_add(UC_HOOK_CODE, self._thunk), mu.hook_add(UC_HOOK_INTR, self._intr)]
        # The surface wrapper: SDL_Surface* at +0x30, clip rectangle +0x60..+0x6C (0,0)-(1023,767).
        self.surface = HEAP
        self.put(HEAP + 0x30, HEAP + 0x1000)
        for off, value in ((0x60, 0), (0x64, 0), (0x68, 1023), (0x6C, 767)):
            self.put(HEAP + off, value)
        self.put(HEAP + 0x1000 + 4, HEAP + 0x2000)        # format
        self.put(HEAP + 0x1000 + 0x10, 1024 * 4)          # pitch
        self.put(HEAP + 0x1000 + 0x14, PIX)               # pixels

    def put(self, va: int, value: int, fmt: str = "<i") -> None:
        self.mu.mem_write(va, struct.pack(fmt, value))

    def _thunk(self, uc, address, size, _user) -> None:
        if address == self.rand:                          # a drop that leaves the view is re-rolled
            esp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EAX, 0)
            uc.reg_write(UC_X86_REG_ESP, esp + 4)         # cdecl: the caller pops
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
            return
        if bytes(uc.mem_read(address, 2)) != b"\xff\x25":
            return
        name = self.imports.get(struct.unpack("<I", uc.mem_read(address + 2, 4))[0])
        if not name:
            return
        self.calls.append(name)
        esp = uc.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_EAX, 0x00FF00FF if "MapRGB" in name else 0)
        uc.reg_write(UC_X86_REG_ESP, esp + 4)             # SDL is cdecl: the caller pops
        uc.reg_write(UC_X86_REG_EIP, back)

    def _intr(self, uc, intno, _user) -> None:
        self.interrupt = intno
        uc.emu_stop()

    def close(self) -> None:
        """Drop the engine (its hooks point back here), so a long run does not hold hundreds of them."""
        for hook in self.hooks:
            self.mu.hook_del(hook)
        self.hooks = []
        self.mu = None

    def run(self, entry: int, esp: int, ecx: int) -> dict:
        try:
            return self._run(entry, esp, ecx)
        finally:
            self.close()

    def _run(self, entry: int, esp: int, ecx: int) -> dict:
        mu = self.mu
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, ecx)
        try:
            mu.emu_start(entry, RETURN, count=3_000_000)
        except UcError as error:
            return {"result": "fault", "error": str(error), "eip": mu.reg_read(UC_X86_REG_EIP)}
        if self.interrupt is not None:
            return {"result": "fault", "error": f"interrupt {self.interrupt}", "eip": mu.reg_read(UC_X86_REG_EIP),
                    "intno": self.interrupt}
        eip = mu.reg_read(UC_X86_REG_EIP)
        return {"result": "returned" if eip == RETURN else f"stopped at {eip:#x}",
                "esp": mu.reg_read(UC_X86_REG_ESP), "pixels": bytes(mu.mem_read(PIX, 0x300000))}


def run_line(game: str, data: bytes, x0: int, y0: int, x1: int, y1: int,
             alpha0: float = 0.5, alpha1: float = 0.0) -> dict:
    m = _Machine(data)
    esp = STK + 0x200000
    frame = struct.pack("<I", RETURN) + b"".join(struct.pack("<i", v) for v in (x0, y0, x1, y1, 0x7F7F7F))
    m.mu.mem_write(esp, frame + struct.pack("<ff", alpha0, alpha1))
    out = m.run(LINE[game], esp, m.surface)
    out["calls"] = m.calls
    out["esp0"] = esp
    return out


def run_rain(game: str, data: bytes, drop: tuple[int, int, int, int, int, int]) -> dict:
    """One rain frame with only drop 0 showing (intensity 0.5 / 512); drop = (x, y, px, py, vx, vy)."""
    draw, intensity, graphics, cam_x, cam_y = RAIN[game]
    m = _Machine(data, RAND[game])
    m.put(HEAP + 0x3000, m.surface)
    m.put(graphics, HEAP + 0x3000)
    m.put(cam_x, 0)
    m.put(cam_y, 0)
    m.mu.mem_write(intensity, struct.pack("<f", 0.5 / 512))
    rain = HEAP + 0x10000
    for k, value in enumerate(drop):
        m.put(rain + 4 * k, value)
    esp = STK + 0x200000
    m.mu.mem_write(esp, struct.pack("<I", RETURN))
    out = m.run(draw, esp, rain)
    out["calls"] = m.calls
    return out


class RowTests(unittest.TestCase):
    def test_each_row_carries_its_fix_and_says_so(self) -> None:
        rows = {p.raw["game_id"]: p.raw for p in load_fun_patches() if p.raw["id"].endswith("_fix_vanilla_bugs")}
        for game, fixes in FIXES.items():
            with self.subTest(game=game):
                row = rows[game]
                pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"]))
                          for p in row["patches"]]
                for fix in fixes:
                    self.assertIn(fix, pinned)
                self.assertIn("raindrop of no length", row["description"])
                self.assertTrue(row["description"].endswith("**Needs no other patch.**"))
                self.assertTrue(any("line drawer" in text for text in row["behavior_changes"]))
        for game in ("vv1", "vv2"):
            self.assertNotIn("raindrop of no length", rows[game]["description"])


@unittest.skipUnless(all(_have(g) for g in NAMES), NO_STOCK)
class StockBytesTests(unittest.TestCase):
    def test_the_sites_hold_the_stock_bytes(self) -> None:
        for game, fixes in FIXES.items():
            for offset, before, _ in fixes:
                with self.subTest(game=game, offset=hex(offset)):
                    self.assertEqual(_stock(game)[offset:offset + len(before)], before)

    def test_every_mode_writes_the_fix(self) -> None:
        for game, fixes in FIXES.items():
            for mode in MODES:
                data = _render(game, mode)
                for offset, _, after in fixes:
                    with self.subTest(game=game, mode=mode, offset=hex(offset)):
                        self.assertEqual(data[offset:offset + len(after)], after)

    def test_the_secret_city_padding_is_no_branch_target(self) -> None:
        import capstone
        data = _stock("vv3")
        pe = pefile.PE(data=data)
        text = pe.sections[0]
        code = data[text.PointerToRawData:text.PointerToRawData + text.Misc_VirtualSize]
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.skipdata = True
        lo, hi = 0x4045A4, 0x4045B0
        for insn in md.disasm(code, BASE + text.VirtualAddress):
            if insn.id and (insn.mnemonic.startswith("j") or insn.mnemonic in ("call", "loop")):
                if insn.op_str.startswith("0x"):
                    self.assertFalse(lo <= int(insn.op_str, 16) < hi, hex(insn.address))
        self.assertNotIn(struct.pack("<I", lo), data)
        # 0x4045A0 ends a jump table (0x4043A9); the padding runs to the next routine at 0x4045B0.
        self.assertEqual(data[0x45A0:0x45A4], struct.pack("<I", 0x4043A9))
        self.assertEqual(data[0x45A4:0x45B0], b"\x90" * 12)


@unittest.skipUnless(all(_have(g) for g in NAMES), NO_STOCK)
class EmulationTests(unittest.TestCase):
    def test_a_zero_length_line_crashes_the_stock_game_and_not_the_fixed_one(self) -> None:
        for game in NAMES:
            for x, y in ((100, 100), (0, 0), (1023, 767)):
                with self.subTest(game=game, point=(x, y)):
                    stock = run_line(game, _stock(game), x, y, x, y)
                    self.assertEqual(stock["result"], "fault")
                    self.assertEqual(stock.get("intno"), 0)                 # #DE, divide error
                    self.assertEqual(stock["eip"], DIVIDE[game])
                    for mode in MODES:
                        fixed = run_line(game, _render(game, mode), x, y, x, y)
                        self.assertEqual(fixed["result"], "returned", mode)
                        self.assertEqual(fixed["esp"], fixed["esp0"] + 4 + 0x1C)
                        self.assertEqual(fixed["calls"][-1], "SDL_UnlockSurface")
                        lit = [i for i in range(0, len(fixed["pixels"]), 4) if fixed["pixels"][i:i + 4] != b"\0" * 4]
                        self.assertEqual(lit, [(y * 1024 + x) * 4])           # the one point

    def test_every_other_line_is_drawn_exactly_as_before(self) -> None:
        rng = random.Random(1409)
        cases = [(10, 10, 11, 10), (10, 10, 10, 11), (5, 5, 4, 4), (0, 0, 1023, 767), (300, 200, 290, 170)]
        cases += [tuple(rng.randrange(0, 200) for _ in range(4)) for _ in range(12)]
        for game in NAMES:
            fixed_data = _render(game, "immediate_fixed")
            for x0, y0, x1, y1 in cases:
                if (x0, y0) == (x1, y1):
                    continue
                for alphas in ((0.5, 0.0), (1.0, 1.0), (0.2, 0.9)):
                    with self.subTest(game=game, line=(x0, y0, x1, y1), alphas=alphas):
                        stock = run_line(game, _stock(game), x0, y0, x1, y1, *alphas)
                        fixed = run_line(game, fixed_data, x0, y0, x1, y1, *alphas)
                        self.assertEqual(stock["result"], "returned")
                        self.assertEqual(fixed["result"], "returned")
                        self.assertEqual(fixed["esp"], stock["esp"])
                        self.assertEqual(fixed["pixels"], stock["pixels"])

    def test_a_rain_drop_still_on_its_previous_point_crashes_only_the_stock_game(self) -> None:
        for game in NAMES:
            with self.subTest(game=game):
                moving = run_rain(game, _stock(game), (300, 200, 290, 170, 10, 30))
                self.assertEqual(moving["result"], "returned")
                fresh = (0, 0, 0, 0, 10, 30)          # rolled (0, 0) onto the zeroed previous point
                stock = run_rain(game, _stock(game), fresh)
                self.assertEqual(stock["result"], "fault")
                self.assertEqual(stock["eip"], DIVIDE[game])
                for mode in MODES:
                    self.assertEqual(run_rain(game, _render(game, mode), fresh)["result"], "returned", mode)


if __name__ == "__main__":
    unittest.main()
