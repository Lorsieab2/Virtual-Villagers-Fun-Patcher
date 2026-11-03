"""Weather crash audit: the weather routines of all five games cannot crash.

The owner asked whether there is "any weather crash" after the divide-by-zero audit found the rain's
zero-length line (docs/reports/div-by-zero/NOTES.md; tests/test_no_divide_by_zero_crashes.py).  This
file is the weather audit's running evidence (docs/reports/weather/NOTES.md): it RUNS the stock
weather routines in unicorn to confirm the guards that make every weather routine but that one line
safe, and checks the stock bytes of the guards the report quotes.

The one reachable weather crash -- the rain's zero-length line in the engine's alpha line drawer
(The Secret City 0x403D20, The Tree of Life 0x404280, New Believers 0x404210) -- is already fixed by
PR #679 and is tested by tests/test_no_divide_by_zero_crashes.py.  This file adds no fix; it locks in
"found safe":

  * New Believers' lightning builder 0x41DDC0 returns -1 instead of writing past its 32-segment
    array when the bolt is full (emulated on the stock exe, both at capacity and one below);
  * the lightning draw 0x41DBF0 skips a zero-length segment, so the lightning never reaches the line
    drawer with a zero-length line (stock bytes);
  * the rain draw's loop bound is the intensity times 512, over a 512-drop array (stock bytes);
  * the weather change / draw / tick dispatchers bound the weather type before the jump table, so a
    type read from any save cannot wild-jump (stock bytes).

A New Home and The Lost Children have no weather rendering at all, so there is nothing to run for
them; that absence is asserted from the divide-by-zero audit's line-drawer table.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_INTR, UC_MODE_32, Uc, UcError
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
except ImportError:  # pragma: no cover
    pefile = None

STOCK_DIR = ROOT / "research" / "stock-executables"
NAMES = {"vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City",
         "vv4": "The Tree of Life", "vv5": "New Believers"}
BASE = 0x400000
HEAP, STK = 0x10000000, 0x20000000
RETURN = 0x0BAD0000
NO_STOCK = "stock executables are not available"

# New Believers' lightning builder and its 32-segment-capacity guard.
VV5_LIGHTNING_BUILDER = 0x41DDC0
VV5_LIGHTNING_CAP = 0x20                 # the array holds 32 segments
VV5_SEG_COUNT_OFF = 0x6A4                # +0x6A4: the live segment count
VV5_BOLT_SIZE = 0x6A8                    # one bolt record

# Stock-byte guards the report quotes (file offset = VA - 0x400000).
GUARD_BYTES = {
    # The lightning builder: cmp dword[ebx+0x6A4],0x20 ; jl build (else return -1).
    ("vv5", 0x41DDC6): bytes.fromhex("83bba406000020") + b"\x7c",
    # The lightning builder's two divisors are clamped >= 2: cmp ecx,2 ; jge ; mov ecx,2.
    ("vv5", 0x41DDFB): bytes.fromhex("83f9027d05b9020000"),
    # The lightning draw skips a zero-length segment: cmp eax,ecx ; jne draw ; cmp ebx,[esp+0x2C] ; je skip.
    ("vv5", 0x41DCD0): bytes.fromhex("3bc175063b5c242c74"),
    # The weather change dispatcher bounds the type before its jump table: cmp eax,5 ; ja skip.
    ("vv5", 0x47707C): bytes.fromhex("83f805"),             # cmp eax, 5
    ("vv4", 0x46BC4C): bytes.fromhex("83f804"),             # cmp eax, 4
    ("vv3", 0x41FB5C): bytes.fromhex("83f804"),             # cmp eax, 4
}


def _stock_path(game: str) -> Path:
    return STOCK_DIR / f"Virtual Villagers - {NAMES[game]}.exe"


def _have(game: str) -> bool:
    return pefile is not None and _stock_path(game).is_file()


def _stock(game: str) -> bytes:
    return _stock_path(game).read_bytes()


class _Machine:
    """A mapped stock executable with a stub for the game's rand(), for a single thiscall."""

    def __init__(self, data: bytes, rand: int = 0, rand_value: int = 0) -> None:
        self.rand, self.rand_value = rand, rand_value
        pe = pefile.PE(data=data, fast_load=True)
        image = pe.get_memory_mapped_image()
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, image)
        for area in (HEAP, STK):
            mu.mem_map(area, 0x400000)
        mu.mem_map(RETURN, 0x1000)
        self.interrupt = None
        self.mu = mu
        self.hook = mu.hook_add(UC_HOOK_CODE, self._code)
        self.ihook = mu.hook_add(UC_HOOK_INTR, self._intr)

    def _code(self, uc, address, size, _u) -> None:
        if self.rand and address == self.rand:          # cdecl rand(n): answer, pop nothing (caller pops)
            esp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_EAX, self.rand_value)
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
            uc.reg_write(UC_X86_REG_ESP, esp + 4)

    def _intr(self, uc, intno, _u) -> None:
        self.interrupt = intno
        uc.emu_stop()

    def put(self, va: int, value: int) -> None:
        self.mu.mem_write(va, struct.pack("<i", value))

    def thiscall(self, entry: int, this: int, args: tuple[int, ...]) -> dict:
        esp = STK + 0x200000
        frame = struct.pack("<I", RETURN) + b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        self.mu.mem_write(esp, frame)
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.reg_write(UC_X86_REG_ECX, this)
        try:
            self.mu.emu_start(entry, RETURN, count=2_000_000)
        except UcError as error:
            return {"result": "fault", "error": str(error), "eip": self.mu.reg_read(UC_X86_REG_EIP)}
        if self.interrupt is not None:
            return {"result": "fault", "intno": self.interrupt, "eip": self.mu.reg_read(UC_X86_REG_EIP)}
        return {"result": "returned", "eax": self.mu.reg_read(UC_X86_REG_EAX),
                "esp": self.mu.reg_read(UC_X86_REG_ESP), "esp0": esp}


@unittest.skipUnless(pefile is not None and _have("vv5"), NO_STOCK)
class LightningBuilderTests(unittest.TestCase):
    """New Believers' lightning builder bounds its 32-segment array."""

    RAND = 0x403660

    def _builder(self, segment_count: int, rand_value: int) -> dict:
        m = _Machine(_stock("vv5"), rand=self.RAND, rand_value=rand_value)
        bolt = HEAP + 0x10000
        m.put(bolt + VV5_SEG_COUNT_OFF, segment_count)
        # ret 0x14: five dword args (x, y and three the full-bolt path never reads).
        return m.thiscall(VV5_LIGHTNING_BUILDER, bolt, (400, 300, 1, 1, 1))

    def test_a_full_bolt_returns_minus_one_and_writes_no_segment(self) -> None:
        out = self._builder(VV5_LIGHTNING_CAP, rand_value=0)
        self.assertEqual(out["result"], "returned")
        self.assertEqual(out["eax"] & 0xFFFFFFFF, 0xFFFFFFFF)     # -1: bolt full, nothing added
        self.assertEqual(out["esp"], out["esp0"] + 4 + 0x14)     # ret 0x14 balanced

    def test_a_bolt_one_below_capacity_does_not_fault(self) -> None:
        # 31 of 32 used: the builder passes the capacity guard and runs its real body on the stock
        # exe (two idiv by divisors it clamps to >= 2) without a divide error or an out-of-range write.
        out = self._builder(VV5_LIGHTNING_CAP - 1, rand_value=1)
        self.assertEqual(out["result"], "returned", out)


@unittest.skipUnless(pefile is not None and all(_have(g) for g in ("vv3", "vv4", "vv5")), NO_STOCK)
class GuardByteTests(unittest.TestCase):
    """The stock bytes of the guards the report quotes are really there."""

    def test_the_quoted_guards_are_present_in_the_stock_exe(self) -> None:
        for (game, va), want in GUARD_BYTES.items():
            with self.subTest(game=game, va=hex(va)):
                off = va - BASE
                self.assertEqual(_stock(game)[off:off + len(want)], want)

    def test_the_rain_draw_loop_is_bounded_by_intensity_times_512(self) -> None:
        # New Believers' rain draw 0x476730 loops while intensity (0x718ECC) * 512.0 (0x4B8EA0) is
        # greater than the drop index: fld[0x718ECC]; fmul[0x4B8EA0]; fcompp.  The intensity is the
        # weather object's +0x2C, which the tick clamps to [0, 1], so the index reaches at most 512 --
        # the array the rain ctor fills.
        data = _stock("vv5")
        self.assertIn(bytes.fromhex("d905cc8e7100"), data[0x76820:0x76840])   # fld dword [0x718ECC]
        self.assertIn(bytes.fromhex("dc0da08e4b00"), data[0x76820:0x76840])   # fmul qword [0x4B8EA0] (512.0)
        self.assertEqual(struct.unpack("<d", data[0xB8EA0:0xB8EA8])[0], 512.0)


class NoWeatherInEarlyGamesTests(unittest.TestCase):
    """A New Home and The Lost Children have no weather rendering to crash."""

    def test_the_divide_audit_records_no_line_drawer_for_vv1_or_vv2(self) -> None:
        notes = " ".join((ROOT / "docs" / "reports" / "div-by-zero" / "NOTES.md")
                          .read_text(encoding="utf-8").split())
        self.assertIn("A New Home and The Lost Children have no line drawer", notes)

    def test_the_weather_report_lists_every_game(self) -> None:
        notes = (ROOT / "docs" / "reports" / "weather" / "NOTES.md").read_text(encoding="utf-8")
        for name in NAMES.values():
            self.assertIn(name, notes)
        self.assertIn("one reachable weather crash", notes)


if __name__ == "__main__":
    unittest.main()
