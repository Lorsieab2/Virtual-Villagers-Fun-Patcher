"""The Super-Secret Golden Mushroom's image companion ("VVFP Golden Mushroom.dll").

A New Home, The Secret City, The Tree of Life and New Believers draw the
mushroom from a NEW image file, Images/golden_mushroom.png, through the DLL;
The Lost Children's own sheet already holds the art.  Everything here RUNS
the shipped DLL and the patcher's rendered executable bytes in an emulator:

* the sites the DLL detours and the call each loader stub replaces hold the
  stock bytes the DLL and the manifest assume, in the stock executables;
* each draw detour, entered as the game enters it: the golden frame of the
  right sheet is drawn with the golden sprite (frame 0, offset) through the
  stock draw with registers and stack intact; anything else passes through
  untouched; a missing or unloadable image skips the draw with the draw's own
  stack cleanup (never the stock frame); the sprite is built once, by the
  game's allocator and constructor, with the bare name "golden_mushroom.png";
* the install (ordinal = game number) writes exactly the probed bytes, is
  idempotent and writes nothing unless every site is stock;
* the executable-side loader stub, from the rendered row: DLL present, DLL
  missing and export missing all preserve every register and esp and return
  into the original callee with the original return address;
* the rows render in every mode alone and with each game's whole catalog, and
  the DLL and the PNG are pinned by the rows and bundled in the release.

A mutation of the golden condition (the frame constant in each stub) is run
here too, so the golden checks are shown able to fail.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX,
    UC_X86_REG_EFLAGS, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

DLL = ROOT / "assets" / "golden_mushroom" / "VVFP Golden Mushroom.dll"
# The probes and counters the emulator drives exist only in the TEST build
# (VVFP_TEST, same source; tests/test_shipped_dlls_have_no_test_hooks.py).
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Golden Mushroom.test.dll"
# tests/test_dlls/ is export-ignore: the release source archive carries no test
# build, so there the tests that drive one skip instead of failing.
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
PNG = ROOT / "assets" / "golden_mushroom" / "golden_mushroom.png"
STOCK = ROOT / "research" / "stock-executables"
NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
ART_GAMES = (1, 3, 4, 5)
DLL_NAME = b"VVFP Golden Mushroom.dll"

# Per game, read from the stock executables (see the DLL source).
ALLOC = {1: 0x44AF03, 3: 0x46EC93, 4: 0x470C5C, 5: 0x47BBDC}
# The spawn's kind roll: the row's 5-byte stub the DLL turns into a jmp, and
# the game's raw C rand() the DLL draws from.
ROLL_SITE = {1: 0x4236ED, 3: 0x42FAD9, 4: 0x489140, 5: 0x4947B0}
ROLL_STUB = bytes.fromhex("85E4C39090")
RAW = {1: 0x44B648, 3: 0x46F3D8, 4: 0x471CF8, 5: 0x47CFD8}
CTOR = {1: 0x40A070, 3: 0x40AF10, 4: 0x40AB10, 5: 0x40B010}
LATER = {  # draw entry, collectables-sheet field, dy
    3: dict(entry=0x42E510, slot=0x58F428 + 0x1B0, dy=0),
    4: dict(entry=0x44C640, slot=0x4CC838 + 0x1B0, dy=0),
    5: dict(entry=0x44F380, slot=0x4DBFC8 + 0x840, dy=1),
}
LOADER = {  # hook call site, original callee, IAT LoadLibraryA, IAT GetProcAddress
    1: (0x43C26E, 0x40A070, 0x457010, 0x4570D4),
    3: (0x42795E, 0x42D3C0, 0x47C124, 0x47C128),
    4: (0x41E971, 0x413720, 0x48A1E0, 0x48A1DC),
    5: (0x423E21, 0x413AD0, 0x4951E0, 0x4951DC),
}

STACK = 0x70000000
HEAP = 0x20000000
FAKE = 0x0F000000          # fake import targets
SENTINEL = 0x0E000000      # return address the emulated caller uses
SPRITE = HEAP + 0x1000     # the sheet the game passes
NEW_SPRITE = HEAP + 0x8000  # what the game's allocator returns
HOLDER, RENDERER = HEAP + 0x2000, HEAP + 0x3000
REGS = {UC_X86_REG_EAX: 0xA0A0A0A0, UC_X86_REG_EBX: 0xB0B0B0B0, UC_X86_REG_EDX: 0xD0D0D0D0,
        UC_X86_REG_ESI: 0x51515151, UC_X86_REG_EDI: 0xD1D1D1D1, UC_X86_REG_EBP: 0xB9B9B9B9}
_CACHE: dict = {}


def _pe_image(data: bytes) -> tuple[bytes, int]:
    pe = pefile.PE(data=data, fast_load=True)
    return pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.SizeOfImage


def _stock_bytes(game: int, va: int, n: int) -> bytes:
    key = ("stock", game)
    if key not in _CACHE:
        _CACHE[key] = _pe_image((STOCK / f"Virtual Villagers - {NAMES[game]}.exe").read_bytes())[0]
    return _CACHE[key][va - 0x400000:va - 0x400000 + n]


def _rendered(game: int) -> bytes:
    """The game with only this row applied -- what the DLL meets at run time
    (the roll stub is the row's own bytes, not stock)."""
    key = ("rendered", game)
    if key not in _CACHE:
        exe = STOCK / f"Virtual Villagers - {NAMES[game]}.exe"
        build = next(b for b in vfp.load_builds() if b.id == f"vv{game}")
        data, _ = vfp.render_patched_bytes(exe, build, "immediate_fixed", [f"vv{game}_super_secret_golden_mushroom"])
        _CACHE[key] = bytes(data)
    return _CACHE[key]


def _rendered_bytes(game: int, va: int, n: int) -> bytes:
    key = ("rendered-image", game)
    if key not in _CACHE:
        _CACHE[key] = _pe_image(_rendered(game))[0]
    return _CACHE[key][va - 0x400000:va - 0x400000 + n]


def _probed(m) -> list:
    return [p for p in (m.probe(i) for i in range(3)) if p]


def _dll():
    if "dll" not in _CACHE:
        pe = pefile.PE(str(TEST_DLL))
        base = pe.OPTIONAL_HEADER.ImageBase
        by_ordinal = {e.ordinal: base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols}
        by_name = {e.name.decode(): base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        iat = {imp.name.decode(): imp.address for d in pe.DIRECTORY_ENTRY_IMPORT for imp in d.imports if imp.name}
        _CACHE["dll"] = (pe.get_memory_mapped_image(), base, by_ordinal, by_name, iat)
    return _CACHE["dll"]


def rd32(mu, a):
    return struct.unpack("<I", mu.mem_read(a, 4))[0]


class Machine:
    """The DLL and a game image in one emulator, kernel32 and the game's
    allocator/constructor scripted."""

    def __init__(self, game: int, *, image_present=True, loads=True, game_bytes: bytes | None = None,
                 mutate=None):
        image, base, self.ordinal, self.exports, iat = _dll()
        self.game = game
        mu = self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        dll = bytearray(image)
        if mutate:
            mutate(dll, base)
        mu.mem_map(base, (len(dll) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(base, bytes(dll))
        gimg, size = _pe_image(game_bytes or _rendered(game))
        mu.mem_map(0x400000, (size + 0xFFF) & ~0xFFF)
        mu.mem_write(0x400000, gimg)
        mu.mem_map(STACK - 0x100000, 0x200000)
        mu.mem_map(HEAP, 0x100000)
        mu.mem_map(FAKE, 0x10000)
        mu.mem_map(SENTINEL, 0x1000)
        self.fakes = {}
        for i, name in enumerate(sorted(iat)):
            addr = FAKE + i * 0x10
            mu.mem_write(iat[name], struct.pack("<I", addr))
            self.fakes[addr] = name
        self.image_present, self.loads = image_present, loads
        self.calls: list = []
        self.writes: list = []
        self.protects: list = []           # (address, length, requested protection) per call
        self.fail_protect_call: int | None = None  # index of a VirtualProtect call to fail
        self.stop_at: set[int] = set()
        self.stopped = None
        self.raw: list = []                # values the game's raw rand() returns, in order
        self.raw_calls = 0
        self.extra: dict = {}              # import name -> handler(machine)
        mu.hook_add(UC_HOOK_CODE, self._hook)

    def _ret(self, value, nargs):
        mu = self.mu
        esp = mu.reg_read(UC_X86_REG_ESP)
        ret = rd32(mu, esp)
        mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        mu.reg_write(UC_X86_REG_ECX, 0xCCCCCCCC)     # volatile registers are clobbered
        mu.reg_write(UC_X86_REG_EDX, 0xDDDDDDDD)
        mu.reg_write(UC_X86_REG_ESP, esp + 4 + 4 * nargs)
        mu.reg_write(UC_X86_REG_EIP, ret)

    def _args(self, n):
        esp = self.mu.reg_read(UC_X86_REG_ESP)
        return struct.unpack(f"<{n}I", self.mu.mem_read(esp + 4, 4 * n))

    def _cstr(self, a):
        return bytes(self.mu.mem_read(a, 260)).split(b"\0")[0]

    def _hook(self, mu, addr, size, _):
        if addr in self.stop_at:
            self.stopped = addr
            mu.emu_stop()
        elif addr in self.fakes:
            name = self.fakes[addr]
            if name == "GetModuleFileNameW":
                # The image check builds a wide path from the executable's
                # own path (native/shared/patcher_files.h).
                _, buf, n = self._args(3)
                path = "C:\\Games\\Village\\game.exe"
                mu.mem_write(buf, path.encode("utf-16-le") + b"\0\0")
                self.calls.append(("GetModuleFileNameW",))
                self._ret(len(path), 3)
            elif name == "GetFileAttributesW":
                path, = self._args(1)
                raw = bytes(mu.mem_read(path, 1024))
                end = next(i for i in range(0, len(raw), 2) if raw[i:i + 2] == b"\0\0")
                self.calls.append(("GetFileAttributesW", raw[:end].decode("utf-16-le")))
                self._ret(0x20 if self.image_present else 0xFFFFFFFF, 1)
            elif name == "VirtualQuery":
                a, mbi, n = self._args(3)
                # BaseAddress, AllocationBase, AllocationProtect, RegionSize, State, Protect, Type
                mu.mem_write(mbi, struct.pack("<7I", a & ~0xFFF, 0x400000, 0x80, 0x1000, 0x1000, 0x20, 0x1000000))
                self._ret(28, 3)
            elif name == "VirtualProtect":
                a, n, new, old = self._args(4)
                if len(self.protects) == self.fail_protect_call:
                    self.protects.append((a, n, new, "failed"))
                    self._ret(0, 4)
                    return
                mu.mem_write(old, struct.pack("<I", 0x20))
                self.writes.append((a, n))
                self.protects.append((a, n, new))
                self._ret(1, 4)
            elif name == "FlushInstructionCache":
                self._ret(1, 3)
            elif name == "GetCurrentProcess":
                self._ret(0xFFFFFFFF, 0)
            elif name in self.extra:
                self.extra[name](self)                 # the finds record's file calls (RecordTests)
            else:
                raise AssertionError(f"unexpected import {name}")
        elif addr == RAW.get(self.game):
            self.raw_calls += 1
            value = self.raw.pop(0) if self.raw else 1
            self._ret(value, 0)                            # cdecl, no arguments
        elif addr == ALLOC.get(self.game):
            n, = self._args(1)
            self.calls.append(("alloc", n))
            mu.reg_write(UC_X86_REG_EAX, NEW_SPRITE)
            esp = mu.reg_read(UC_X86_REG_ESP)
            mu.reg_write(UC_X86_REG_ESP, esp + 4)          # cdecl: the caller pops
            mu.reg_write(UC_X86_REG_EIP, rd32(mu, esp))
        elif addr == CTOR.get(self.game):
            this = mu.reg_read(UC_X86_REG_ECX)
            name, cols, rows = self._args(3)
            self.calls.append(("ctor", this, self._cstr(name), cols, rows))
            mu.mem_write(this + 8, struct.pack("<4I", cols, rows, 29 if self.loads else 0, 22 if self.loads else 0))
            self._ret(this, 3)
            mu.reg_write(UC_X86_REG_EAX, this)

    def export(self, ordinal_or_name, *args):
        """Call a stdcall export; returns eax."""
        mu = self.mu
        target = self.ordinal[ordinal_or_name] if isinstance(ordinal_or_name, int) else self.exports[ordinal_or_name]
        esp = STACK - 0x800
        mu.mem_write(esp, struct.pack(f"<{1 + len(args)}I", SENTINEL, *args))
        mu.reg_write(UC_X86_REG_ESP, esp)
        self.stop_at = {SENTINEL}
        mu.emu_start(target, 0xFFFFFFFF, count=200000)
        assert self.stopped == SENTINEL
        assert mu.reg_read(UC_X86_REG_ESP) == esp + 4 + 4 * len(args), "stdcall cleanup"
        return mu.reg_read(UC_X86_REG_EAX)

    def probe(self, index):
        buf = HEAP + 0x50000
        n = self.export("VvfpGoldenMushroomProbeSite", self.game, index, buf, buf + 0x10, buf + 0x30, buf + 0x50)
        if n == 0:
            return None
        return (rd32(self.mu, buf), bytes(self.mu.mem_read(buf + 0x10, n)),
                bytes(self.mu.mem_read(buf + 0x30, n)), rd32(self.mu, buf + 0x50))

    def record_probe(self):
        """The finds record's site: (va, the row's bytes, the bytes the install writes, the stub)."""
        buf = HEAP + 0x50000
        n = self.export("VvfpGoldenMushroomProbeRecordSite", self.game, buf, buf + 0x10, buf + 0x30, buf + 0x50)
        return (rd32(self.mu, buf), bytes(self.mu.mem_read(buf + 0x10, n)),
                bytes(self.mu.mem_read(buf + 0x30, n)), rd32(self.mu, buf + 0x50))

    def record_stats(self):
        return struct.unpack("<2i", self.mu.mem_read(self.exports["VvfpGoldenMushroomRecordStats"], 8))

    def stats(self):
        return struct.unpack("<3i", self.mu.mem_read(self.exports["VvfpGoldenMushroomStats"], 12))

    def draw(self, start, stack_words, ecx, stops, count=5000):
        """Enter `start` with `stack_words` at esp (a return address first,
        unless start is a call instruction) and run until one of `stops`."""
        mu = self.mu
        esp = STACK - 0x400
        mu.mem_write(esp, struct.pack(f"<{len(stack_words)}I", *stack_words))
        for r, v in REGS.items():
            mu.reg_write(r, v)
        mu.reg_write(UC_X86_REG_ECX, ecx)
        mu.reg_write(UC_X86_REG_ESP, esp)
        self.stop_at = set(stops)
        self.stopped = None
        mu.emu_start(start, 0xFFFFFFFF, count=count)
        return esp


def _installed(game, **kw) -> Machine:
    m = Machine(game, **kw)
    assert m.export(game) == 1, "install refused on the stock image"
    return m


def _sheet(m: Machine, cols, rows):
    m.mu.mem_write(SPRITE + 8, struct.pack("<4I", cols, rows, 40, 40))


class SiteTests(unittest.TestCase):
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_every_detour_site_and_loader_call_is_stock(self):
        rows = {p.id: p.raw for p in vfp.load_fun_patches()}
        for game in ART_GAMES:
            m = Machine(game)
            detours = rows[f"vv{game}_super_secret_golden_mushroom"]["runtime_detours"]
            probed = _probed(m)
            with self.subTest(game=game):
                self.assertEqual([(f"0x{va:X}", stock.hex().upper()) for va, stock, _, _ in probed],
                                 [(d["va"], d["stock_bytes"]) for d in detours])
                for d in detours:
                    self.assertEqual(d["installed_by"], f"VVFP Golden Mushroom.dll, ordinal {game}")
                self.assertEqual(probed[-1][0], ROLL_SITE[game], "the roll site is the last")
                for va, stock, patched, stub in probed:
                    if va == ROLL_SITE[game]:
                        # the row's own stub (never golden without the DLL)
                        self.assertEqual(stock, ROLL_STUB)
                        self.assertEqual(_rendered_bytes(game, va, len(stock)), stock, hex(va))
                        self.assertNotEqual(_stock_bytes(game, va, len(stock)), stock)
                    else:
                        self.assertEqual(_stock_bytes(game, va, len(stock)), stock, hex(va))
                    self.assertIn(patched[0], (0xE8, 0xE9))
                    self.assertEqual(va + 5 + struct.unpack("<i", patched[1:5])[0], stub)
                    self.assertEqual(patched[5:], b"\x90" * (len(stock) - 5))
                site, callee, lla, gpa = LOADER[game]
                code = _stock_bytes(game, site, 5)
                self.assertEqual(code[0], 0xE8)
                self.assertEqual(site + 5 + struct.unpack("<i", code[1:])[0], callee)
        # A New Home: the frame thunk jumps to the 4-argument draw, the fade
        # call site calls the 5-argument thunk.
        self.assertEqual(_stock_bytes(1, 0x4093D0, 7), bytes.fromhex("8B09E9D9F3FFFF"))
        self.assertEqual(0x4093D2 + 5 + struct.unpack("<i", _stock_bytes(1, 0x4093D3, 4))[0], 0x4087B0)
        self.assertEqual(0x41ABA0 + 5 + struct.unpack("<i", _stock_bytes(1, 0x41ABA1, 4))[0], 0x4093E0)
        # carrying.png is built 15 x 1 at the loader's own call site.
        self.assertEqual(_stock_bytes(1, 0x43C263, 11), bytes.fromhex("6A016A0F6824954500") + b"\x8B\xC8")
        # The Secret City / Tree of Life / New Believers: the collectables
        # draw passes the manager's own sheet field and frame = id - base.
        for game, (draw, mgr, field, base) in {3: (0x42D5A0, 0x58F428, 0x1B0, 0x34),
                                               4: (0x413950, 0x4CC838, 0x1B0, 0x46),
                                               5: (0x413D70, 0x4DBFC8, 0x840, 0x50)}.items():
            with self.subTest(game=game, check="sheet field"):
                body = _stock_bytes(game, draw, 0x40)
                self.assertIn(b"\x8B\x89" + struct.pack("<I", field), body)
                self.assertIn(b"\x83\xE8" + bytes([base]), body)
                self.assertEqual(LATER[game]["slot"], mgr + field)
                self.assertEqual(base + 50, {3: 0x66, 4: 0x78, 5: 0x82}[game], "frame 50 is the new id")


def roll_model(raw):
    """The kind roll's rule (owner, 2026-09-29: exactly 1 in 1,000,000): two
    draws, each the first raw value below 32000 within 16 tries (else no),
    taken mod 1000; yes only when both are 0.  Returns (yes, raw calls)."""
    raw, calls = list(raw), 0
    for _ in range(2):
        for _ in range(16):
            calls += 1
            v = raw.pop(0) if raw else 1
            if v < 32000:
                break
        else:
            return False, calls
        if v % 1000:
            return False, calls
    return True, calls


class RollTests(unittest.TestCase):
    """The DLL's answer at the row's roll stub, entered as the spawn calls it."""
    REGS = (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESI,
            UC_X86_REG_EDI, UC_X86_REG_EBP)

    def _roll(self, m, raw):
        mu = m.mu
        m.raw, m.raw_calls = list(raw), 0
        before = [0x11110000 + i for i in range(len(self.REGS))]
        for r, v in zip(self.REGS, before):
            mu.reg_write(r, v)
        esp = STACK - 0x800
        mu.mem_write(esp, struct.pack("<I", SENTINEL))
        mu.reg_write(UC_X86_REG_ESP, esp)
        m.stop_at, m.stopped = {SENTINEL}, None
        mu.emu_start(ROLL_SITE[m.game], 0xFFFFFFFF, count=20000)
        self.assertEqual(m.stopped, SENTINEL)
        self.assertEqual(mu.reg_read(UC_X86_REG_ESP), esp + 4, "stack balanced")
        self.assertEqual([mu.reg_read(r) for r in self.REGS], before, "every register preserved")
        return bool(mu.reg_read(UC_X86_REG_EFLAGS) & 0x40), m.raw_calls

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_without_the_install_the_stub_always_answers_no(self):
        for game in ART_GAMES:
            with self.subTest(game=game):
                self.assertEqual(self._roll(Machine(game), [0, 0]), (False, 0))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_every_raw_value_of_each_draw(self):
        for game in ART_GAMES:
            m = _installed(game)
            with self.subTest(game=game):
                yes_first = yes_second = 0
                for v in range(32768):
                    for raw in ([v, 0], [0, v, 0]):
                        self.assertEqual(self._roll(m, raw), roll_model(raw), raw)
                    if v < 32000:
                        yes_first += self._roll(m, [v, 0])[0]
                        yes_second += self._roll(m, [0, v])[0]
                # 32 of the 32000 accepted values pass each draw: (32/32000)^2
                self.assertEqual((yes_first, yes_second), (32, 32))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_sixteen_draw_cap(self):
        for game in ART_GAMES:
            m = _installed(game)
            with self.subTest(game=game):
                self.assertEqual(self._roll(m, [32767] * 15 + [0, 0]), (True, 17))
                self.assertEqual(self._roll(m, [32000] * 16 + [0, 0]), (False, 16),
                                 "16 rejected draws end the roll: no, and no hang")
                self.assertEqual(self._roll(m, [0] + [32500] * 16 + [0]), (False, 17))
                self.assertEqual(self._roll(m, [0] + [32500] * 15 + [0]), (True, 17))


class InstallTests(unittest.TestCase):
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_install_writes_exactly_the_probed_bytes_once(self):
        for game in ART_GAMES:
            with self.subTest(game=game):
                m = Machine(game)
                probed = _probed(m) + [m.record_probe()]     # the image sites, then the finds record's
                self.assertEqual(m.export(game), 1)
                for va, stock, patched, _ in probed:
                    self.assertEqual(bytes(m.mu.mem_read(va, len(patched))), patched)
                unlocks = [(a, n) for a, n, prot in m.protects if prot == 0x40]
                relocks = [(a, n) for a, n, prot in m.protects if prot == 0x20]
                want = sorted((va, len(p)) for va, _, p, _ in probed)
                self.assertEqual(sorted(unlocks), want, "each site made writable once")
                self.assertEqual(sorted(relocks), want, "and its old protection restored")
                before = len(m.writes)
                self.assertEqual(m.export(game), 1, "a second call reports installed")
                self.assertEqual(len(m.writes), before, "and writes nothing")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_nothing_is_written_unless_every_site_is_stock(self):
        for game in ART_GAMES:
            with self.subTest(game=game):
                m = Machine(game)
                probed = _probed(m)
                record = m.record_probe()
                last_va = probed[-1][0]
                m.mu.mem_write(last_va, b"\xCC")
                self.assertEqual(m.export(game), 0)
                # The image is refused; the finds record is installed on its own.
                self.assertEqual(set(m.writes), {(record[0], len(record[2]))})
                for va, stock, _, _ in probed[:-1]:
                    self.assertEqual(bytes(m.mu.mem_read(va, len(stock))), stock)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_record_site_that_is_not_the_rows_never_stops_the_image(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                m = Machine(game)
                probed = _probed(m) if game != 2 else []
                va, row, _, _ = m.record_probe()
                m.mu.mem_write(va, b"\xCC")
                self.assertEqual(m.export(game), 0 if game == 2 else 1)
                self.assertEqual(bytes(m.mu.mem_read(va, 1)), b"\xCC", "the record site is left alone")
                self.assertEqual(sorted(set(m.writes)), sorted({(p[0], len(p[2])) for p in probed}))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_site_that_cannot_be_made_writable_leaves_every_site_stock(self):
        # Codex (PR #466): A New Home has two sites; if VirtualProtect fails at
        # the second after the first was written, the feature is half-installed
        # (the loader ignores the export's result).  Every site is now unlocked
        # before any is written, and a failure re-locks what was unlocked.
        m = Machine(1)
        probed = _probed(m)
        self.assertEqual(len(probed), 3)
        record = m.record_probe()
        m.fail_protect_call = 1
        self.assertEqual(m.export(1), 0)
        for va, stock, _, _ in probed:
            self.assertEqual(bytes(m.mu.mem_read(va, len(stock))), stock, hex(va))
        first = (probed[0][0], len(probed[0][2]))
        self.assertEqual(m.protects[0][:3], (*first, 0x40))
        self.assertEqual(m.protects[1][3:], ("failed",))
        self.assertEqual(m.protects[2], (*first, 0x20), "the first site is re-locked")
        # ... and then the finds record, on its own.
        self.assertEqual(m.protects[3:], [(record[0], len(record[2]), 0x40), (record[0], len(record[2]), 0x20)])
        self.assertEqual(m.export(1), 0, "and it stays refused")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_different_game_installs_nothing(self):
        m = Machine(3)
        self.assertEqual(m.export(4), 0)
        self.assertEqual(m.writes, [])
        self.assertIn(2, m.ordinal, "The Lost Children's ordinal: the finds record only")


class NewHomeDrawTests(unittest.TestCase):
    """A New Home: the golden frame is frame 15 of a 15 x 1 sheet."""

    def _frame(self, m, cols=15, rows=1, frame=15, x=100, y=200):
        _sheet(m, cols, rows)
        m.mu.mem_write(HOLDER, struct.pack("<I", RENDERER))
        esp = m.draw(0x4093D0, [SENTINEL, SPRITE, x, y, frame], HOLDER, {0x4087B0, SENTINEL})
        return esp

    def _fade(self, m, cols=15, rows=1, frame=15, x=100, y=200, alpha=0x3F000000):
        _sheet(m, cols, rows)
        # enter the call instruction itself: it pushes its own return address
        esp = m.draw(0x41ABA0, [SPRITE, x, y, frame, alpha], HOLDER, {0x4093E0, 0x41ABA5})
        return esp

    def _regs_intact(self, m, ecx):
        for r, v in REGS.items():
            self.assertEqual(m.mu.reg_read(r), v, r)
        self.assertEqual(m.mu.reg_read(UC_X86_REG_ECX), ecx)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_golden_frame_draws_the_new_image_through_the_stock_draw(self):
        m = _installed(1)
        esp = self._frame(m)
        self.assertEqual(m.stopped, 0x4087B0)
        self.assertEqual(m.mu.reg_read(UC_X86_REG_ESP), esp)
        self.assertEqual(struct.unpack("<5I", m.mu.mem_read(esp, 20)), (SENTINEL, NEW_SPRITE, 106, 202, 0))
        self._regs_intact(m, RENDERER)      # ecx = [holder], as the thunk loads it
        # The image stays in the game's own Images folder (the game's sprite
        # loader opens it there), checked by a wide path.
        self.assertEqual(m.calls, [("GetModuleFileNameW",),
                                   ("GetFileAttributesW", "C:\\Games\\Village\\Images\\golden_mushroom.png"),
                                   ("alloc", 0x34), ("ctor", NEW_SPRITE, b"golden_mushroom.png", 1, 1)])
        # built once: the next golden draw reuses it
        self._frame(m, x=5, y=6)
        self.assertEqual(struct.unpack("<5I", m.mu.mem_read(STACK - 0x400, 20)), (SENTINEL, NEW_SPRITE, 11, 8, 0))
        self.assertEqual(len([c for c in m.calls if c[0] == "alloc"]), 1)
        self.assertEqual(m.stats(), (2, 0, 1))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_fading_draw_does_the_same_into_the_five_argument_thunk(self):
        m = _installed(1)
        esp = self._fade(m)
        self.assertEqual(m.stopped, 0x4093E0)
        self.assertEqual(m.mu.reg_read(UC_X86_REG_ESP), esp - 4)
        self.assertEqual(struct.unpack("<6I", m.mu.mem_read(esp - 4, 24)),
                         (0x41ABA5, NEW_SPRITE, 106, 202, 0, 0x3F000000))
        self._regs_intact(m, HOLDER)        # the thunk has not run yet

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_anything_else_passes_through_untouched(self):
        for cols, rows, frame in ((15, 1, 14), (15, 1, 0), (14, 1, 15), (15, 2, 15), (16, 1, 15)):
            with self.subTest(cols=cols, rows=rows, frame=frame):
                m = _installed(1)
                esp = self._frame(m, cols, rows, frame)
                self.assertEqual(m.stopped, 0x4087B0)
                self.assertEqual(struct.unpack("<5I", m.mu.mem_read(esp, 20)), (SENTINEL, SPRITE, 100, 200, frame))
                self._regs_intact(m, RENDERER)
                esp = self._fade(m, cols, rows, frame)
                self.assertEqual(m.stopped, 0x4093E0)
                self.assertEqual(struct.unpack("<6I", m.mu.mem_read(esp - 4, 24)),
                                 (0x41ABA5, SPRITE, 100, 200, frame, 0x3F000000))
                self._regs_intact(m, HOLDER)
                self.assertEqual(m.calls, [], "no image is built for a stock frame")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_an_image_that_is_missing_or_does_not_load_is_never_drawn(self):
        for present, loads in ((False, True), (True, False)):
            with self.subTest(present=present, loads=loads):
                m = _installed(1, image_present=present, loads=loads)
                esp = self._frame(m)
                self.assertEqual(m.stopped, SENTINEL, "the draw is skipped, not sent to the stock frame")
                self.assertEqual(m.mu.reg_read(UC_X86_REG_ESP), esp + 4 + 0x10, "the draw's ret 0x10")
                self._regs_intact(m, RENDERER)
                esp = self._fade(m)
                self.assertEqual(m.stopped, 0x41ABA5)
                self.assertEqual(m.mu.reg_read(UC_X86_REG_ESP), esp + 0x14, "ret 0x14")
                self.assertEqual(m.stats(), (0, 2, 1), "tried once, not every frame")
                self.assertEqual(len([c for c in m.calls if c[0] == "ctor"]), 1 if present else 0)


class LaterGamesDrawTests(unittest.TestCase):
    """The Secret City / The Tree of Life / New Believers: the collectables
    sheet at frame 50, through the world draw entry."""

    def _run(self, game, sheet=SPRITE, frame=50, x=300, y=400, scale=0x3F800000, slot=SPRITE, **kw):
        m = kw.pop("machine", None) or _installed(game, **kw)
        g = LATER[game]
        resume = g["entry"] + 5
        out = HEAP + 0x60000
        # at the resume point, store the x the displaced fild loaded, then stop
        m.mu.mem_write(resume, b"\xDB\x1D" + struct.pack("<I", out) + b"\xF4")
        m.mu.mem_write(g["slot"], struct.pack("<I", slot))
        esp = m.draw(g["entry"], [SENTINEL, sheet, x, y, frame, scale], RENDERER, {resume + 6, SENTINEL})
        return m, esp, out

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_golden_frame_draws_the_new_image_through_the_stock_entry(self):
        for game, g in LATER.items():
            with self.subTest(game=game):
                m, esp, out = self._run(game)
                self.assertEqual(m.stopped, g["entry"] + 11)
                self.assertEqual(m.mu.reg_read(UC_X86_REG_ESP), esp - 4, "the displaced push esi")
                self.assertEqual(struct.unpack("<7I", m.mu.mem_read(esp - 4, 28)),
                                 (REGS[UC_X86_REG_ESI], SENTINEL, NEW_SPRITE, 307, 400 + g["dy"], 0, 0x3F800000))
                self.assertEqual(struct.unpack("<i", m.mu.mem_read(out, 4))[0], 307, "fild dword [esp+8]")
                for r, v in REGS.items():
                    self.assertEqual(m.mu.reg_read(r), v, r)
                self.assertEqual(m.mu.reg_read(UC_X86_REG_ECX), RENDERER)
                self.assertEqual(m.calls[2:], [("alloc", 0x34), ("ctor", NEW_SPRITE, b"golden_mushroom.png", 1, 1)])
                self.assertEqual(m.stats(), (1, 0, 1))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_anything_else_passes_through_untouched(self):
        other = HEAP + 0x4000
        for game, g in LATER.items():
            for sheet, frame, slot in ((SPRITE, 49, SPRITE), (SPRITE, 51, SPRITE), (other, 50, SPRITE),
                                       (SPRITE, 50, other), (0, 50, 0)):
                with self.subTest(game=game, sheet=hex(sheet), frame=frame, slot=hex(slot)):
                    m, esp, out = self._run(game, sheet=sheet, frame=frame, slot=slot)
                    self.assertEqual(m.stopped, g["entry"] + 11)
                    self.assertEqual(struct.unpack("<7I", m.mu.mem_read(esp - 4, 28)),
                                     (REGS[UC_X86_REG_ESI], SENTINEL, sheet, 300, 400, frame, 0x3F800000))
                    self.assertEqual(struct.unpack("<i", m.mu.mem_read(out, 4))[0], 300)
                    for r, v in REGS.items():
                        self.assertEqual(m.mu.reg_read(r), v, r)
                    self.assertEqual(m.mu.reg_read(UC_X86_REG_ECX), RENDERER)
                    self.assertEqual(m.calls, [])

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_sheet_field_is_read_at_every_draw(self):
        for game in LATER:
            with self.subTest(game=game):
                m, esp, _ = self._run(game, slot=HEAP + 0x4000)
                self.assertEqual(rd32(m.mu, esp + 4), SPRITE, "not the sheet yet")
                m, esp, _ = self._run(game, machine=m)
                self.assertEqual(rd32(m.mu, esp + 4), NEW_SPRITE, "the field now holds it")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_an_image_that_is_missing_or_does_not_load_is_never_drawn(self):
        for game in LATER:
            for present, loads in ((False, True), (True, False)):
                with self.subTest(game=game, present=present, loads=loads):
                    m, esp, _ = self._run(game, image_present=present, loads=loads)
                    self.assertEqual(m.stopped, SENTINEL)
                    self.assertEqual(m.mu.reg_read(UC_X86_REG_ESP), esp + 4 + 0x14, "the entry's ret 0x14")
                    for r, v in REGS.items():
                        self.assertEqual(m.mu.reg_read(r), v, r)
                    m, esp, _ = self._run(game, machine=m)
                    self.assertEqual(m.stopped, SENTINEL)
                    self.assertEqual(m.stats(), (0, 2, 1))


class MutationTests(unittest.TestCase):
    """The golden checks above can fail: with the frame constant in a stub
    changed, the golden frame is passed through as a stock one."""

    @staticmethod
    def _mutator(pattern: bytes, replacement: bytes):
        def mutate(image: bytearray, base: int):
            text = image[0x1000:0x2000]
            assert text.count(pattern) >= 1, pattern.hex()
            i = 0x1000 + text.index(pattern)
            image[i:i + len(pattern)] = replacement
        return mutate

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_mutated_frame_constants_break_the_golden_path(self):
        # VV1 frame stub: cmp dword [esp+0x14], 15 -> 14
        m = _installed(1, mutate=self._mutator(bytes.fromhex("837C24140F"), bytes.fromhex("837C24140E")))
        _sheet(m, 15, 1)
        m.mu.mem_write(HOLDER, struct.pack("<I", RENDERER))
        esp = m.draw(0x4093D0, [SENTINEL, SPRITE, 100, 200, 15], HOLDER, {0x4087B0, SENTINEL})
        self.assertEqual(rd32(m.mu, esp + 4), SPRITE, "mutant: the golden frame is not swapped")
        # VV3-VV5 stubs: cmp dword [esp+0x14], 50 -> 51 (the first stub is VV3's)
        m = _installed(3, mutate=self._mutator(bytes.fromhex("837C241432"), bytes.fromhex("837C241433")))
        m.mu.mem_write(LATER[3]["slot"], struct.pack("<I", SPRITE))
        resume = LATER[3]["entry"] + 5
        m.mu.mem_write(resume, b"\xF4")
        esp = m.draw(LATER[3]["entry"], [SENTINEL, SPRITE, 1, 2, 50, 0], RENDERER, {resume})
        self.assertEqual(rd32(m.mu, esp + 4), SPRITE, "mutant: the golden frame is not swapped")


class LoaderStubTests(unittest.TestCase):
    """The executable-side stub, from the patcher's own rendered bytes."""

    def _rendered(self, game, catalog=False):
        key = ("rendered", game, catalog)
        if key not in _CACHE:
            build = next(b for b in vfp.load_builds() if b.id == f"vv{game}")
            rid = f"vv{game}_super_secret_golden_mushroom"
            sel = [p.id for p in vfp.load_fun_patches() if p.game_id == f"vv{game}"
                   and p.id not in vfp.ALTERNATIVE_FUN_PATCH_IDS] if catalog else [rid]
            data, applied = vfp.render_patched_bytes(STOCK / build.input_name, build, "immediate_fixed", sel)
            self.assertIn(f"feature:{rid}", {a["owner"] for a in applied})
            _CACHE[key] = bytes(data)
        return _CACHE[key]

    def _run(self, game, case, catalog=False):
        site, callee, lla_slot, gpa_slot = LOADER[game]
        image, size = _pe_image(self._rendered(game, catalog))
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (size + 0xFFF) & ~0xFFF)
        mu.mem_write(0x400000, image)
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_map(FAKE, 0x10000)
        lla, gpa, export, module = FAKE, FAKE + 0x10, FAKE + 0x20, 0x6A000000
        mu.mem_write(lla_slot, struct.pack("<I", lla))
        mu.mem_write(gpa_slot, struct.pack("<I", gpa))
        esp0 = STACK - 0x100
        mu.mem_write(esp0, struct.pack("<3I", 0x11111111, 0x22222222, 0x33333333))   # the callee's own args
        regs = dict(REGS)
        regs[UC_X86_REG_ECX] = 0xC0C0C0C0
        for r, v in regs.items():
            mu.reg_write(r, v)
        mu.reg_write(UC_X86_REG_ESP, esp0)
        log = []

        def ret(value, nargs):
            esp = mu.reg_read(UC_X86_REG_ESP)
            mu.reg_write(UC_X86_REG_EAX, value)
            mu.reg_write(UC_X86_REG_ECX, 0xBAD)
            mu.reg_write(UC_X86_REG_EDX, 0xBAD)
            mu.reg_write(UC_X86_REG_ESP, esp + 4 + 4 * nargs)
            mu.reg_write(UC_X86_REG_EIP, rd32(mu, esp))

        def hook(uc, addr, size_, _):
            esp = uc.reg_read(UC_X86_REG_ESP)
            if addr == lla:
                name = bytes(uc.mem_read(rd32(uc, esp + 4), 64)).split(b"\0")[0]
                log.append(("LoadLibraryA", name))
                ret(0 if case == "missing" else module, 1)
            elif addr == gpa:
                h, o = struct.unpack("<2I", uc.mem_read(esp + 4, 8))
                log.append(("GetProcAddress", h, o))
                ret(export if case == "present" else 0, 2)
            elif addr == export:
                log.append(("export", esp))
                ret(1, 0)                                   # stdcall, no arguments
            elif addr == callee:
                log.append(("callee", esp, struct.unpack("<4I", uc.mem_read(esp, 16)),
                            {r: uc.reg_read(r) for r in regs}))
                uc.emu_stop()

        mu.hook_add(UC_HOOK_CODE, hook)
        mu.emu_start(site, 0xFFFFFFFF, count=500)
        return log, esp0, regs

    def test_present_missing_and_no_export_all_return_into_the_original_callee(self):
        for game in ART_GAMES:
            site = LOADER[game][0]
            for catalog in (False, True):
                for case in ("present", "missing", "no_export"):
                    with self.subTest(game=game, catalog=catalog, case=case):
                        log, esp0, regs = self._run(game, case, catalog)
                        self.assertEqual(log[0], ("LoadLibraryA", DLL_NAME))
                        self.assertEqual(log[-1][0], "callee")
                        _, esp, top, seen = log[-1]
                        self.assertEqual(esp, esp0 - 4, "esp as the stock call left it")
                        self.assertEqual(top, (site + 5, 0x11111111, 0x22222222, 0x33333333))
                        self.assertEqual(seen, regs, "every register preserved")
                        gpa = [e for e in log if e[0] == "GetProcAddress"]
                        exported = [e for e in log if e[0] == "export"]
                        if case == "missing":
                            self.assertEqual(gpa, [])
                        else:
                            self.assertEqual(gpa, [("GetProcAddress", 0x6A000000, game)], "by ordinal = game")
                        self.assertEqual(len(exported), 1 if case == "present" else 0)


class ManifestTests(unittest.TestCase):
    def test_the_rows_pin_and_bundle_the_dll_and_the_image(self):
        rows = {p.id: p.raw for p in vfp.load_fun_patches()}
        dll_sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        png_sha = hashlib.sha256(PNG.read_bytes()).hexdigest().upper()
        for game in ART_GAMES:
            with self.subTest(game=game):
                self.assertEqual(rows[f"vv{game}_super_secret_golden_mushroom"]["companion_files"], [
                    {"source": "assets/golden_mushroom/VVFP Golden Mushroom.dll",
                     "destination": "VVFP Golden Mushroom.dll", "sha256": dll_sha},
                    {"source": "assets/golden_mushroom/golden_mushroom.png",
                     "destination": "Images/golden_mushroom.png", "sha256": png_sha},
                ])
        self.assertNotIn("companion_files", rows["vv2_super_secret_golden_mushroom"],
                         "The Lost Children draws its own sheet's art")
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"assets/golden_mushroom/VVFP Golden Mushroom.dll"', release)
        self.assertIn('"assets/golden_mushroom/golden_mushroom.png"', release)
        from PIL import Image
        with Image.open(PNG) as im:
            self.assertEqual((im.size, im.mode), ((29, 22), "RGBA"))

    def test_the_loader_patches_are_the_stubs_run_above(self):
        rows = {p.id: p.raw for p in vfp.load_fun_patches()}
        for game in ART_GAMES:
            with self.subTest(game=game):
                patches = rows[f"vv{game}_super_secret_golden_mushroom"]["patches"]
                site = LOADER[game][0]
                hook = next(p for p in patches if int(p["offset"], 16) == site - 0x400000)
                self.assertEqual(hook["before"], _stock_bytes(game, site, 5).hex().upper())
                names = [p for p in patches if bytes.fromhex(p["after"]) == DLL_NAME + b"\0"]
                self.assertEqual(len(names), 1)

    def test_the_rows_render_in_every_mode_alone_and_with_the_whole_catalog(self):
        modes = [m.id for m in vfp.load_patch_modes()]
        rows = vfp.load_fun_patches()
        for game in ART_GAMES:
            build = next(b for b in vfp.load_builds() if b.id == f"vv{game}")
            rid = f"vv{game}_super_secret_golden_mushroom"
            catalog = [p.id for p in rows if p.game_id == f"vv{game}" and p.id not in vfp.ALTERNATIVE_FUN_PATCH_IDS]
            for mode in modes:
                for sel in ([rid], catalog):
                    with self.subTest(game=game, mode=mode, n=len(sel)):
                        data, applied = vfp.render_patched_bytes(STOCK / build.input_name, build, mode, sel)
                        self.assertIn(f"feature:{rid}", {a["owner"] for a in applied})
                        image, _ = _pe_image(bytes(data))
                        site = LOADER[game][0]
                        stub = site + 5 + struct.unpack("<i", image[site - 0x400000 + 1:site - 0x400000 + 5])[0]
                        self.assertEqual(image[stub - 0x400000], 0x60, "the call reaches the loader (pushad)")


# ---- The finds record ----------------------------------------------------------------------------------------
# The owner (2026-11-15): "the patcher should keep a record" of the finds, shown in Game Mechanics.  Each
# delivered golden mushroom appends one "YYYY-MM-DD HH:MM:SS" line to the save's own data file, outside the
# save and the executable.  Here the record stubs run where the row's code runs, with the files the DLL makes
# put in a private temporary folder (the kernel32 / shell32 calls answered from it), and Game Mechanics' own
# reader (src/vv_game_mechanics_counts.py golden_record) reads what was written.
SAVE_MANAGER = {1: (0x48AEDC, 0xABE4), 2: (0x4997BC, 0x30378), 3: (0x4B309C, 0x12F24),
                4: (0x4CB51C, 0x17114), 5: (0x4DACE0, 0x17D80)}    # native/shared/game_save_slot.h
RECORD = {  # site, how the row's code enters it, golden / not-golden registers, where it continues
    1: dict(site=0x444683, golden={}, other=None, next=0x43AFF1),
    2: dict(site=0x4633CD, golden={"carry": 0x50}, other={"carry": 0x4F}, next=0x473E05),
    3: dict(site=0x42E064, golden={UC_X86_REG_ESI: 0x66}, other={UC_X86_REG_ESI: 0x65}, next=0x42E06B),
    4: dict(site=0x41460A, golden={UC_X86_REG_ESI: 0x78}, other={UC_X86_REG_ESI: 0x76}, next=0x489150),
    5: dict(site=0x414915, golden={UC_X86_REG_ESI: 0x82}, other={UC_X86_REG_ESI: 0x80}, next=0x4947C0),
}
DOCS = "C:\\Users\\Player\\Documents"
VV2_VILLAGE, VV2_INDEX = HEAP + 0x10000, 3


class FileCalls:
    """The DLL's file calls, answered from `root` (a real temporary folder standing for C:\\)."""

    def __init__(self, root: Path):
        self.root = root
        self.handles: dict[int, Path] = {}
        self.local(DOCS).mkdir(parents=True)        # the player's Documents folder exists

    def local(self, path: str) -> Path:
        assert path[:3].upper() == "C:\\", path
        return self.root / path[3:].replace("\\", "/")

    @staticmethod
    def wstr(m, a):
        raw = bytes(m.mu.mem_read(a, 2048))
        end = next(i for i in range(0, len(raw), 2) if raw[i:i + 2] == b"\0\0")
        return raw[:end].decode("utf-16-le")

    def install(self, m: Machine) -> None:
        w = lambda a, text: m.mu.mem_write(a, text.encode("utf-16-le") + b"\0\0")  # noqa: E731

        def lstrlenW(m):
            a, = m._args(1)
            m._ret(len(self.wstr(m, a)) if a else 0, 1)

        def lstrcpyW(m):
            d, s = m._args(2)
            w(d, self.wstr(m, s))
            m._ret(d, 2)

        def lstrcpynW(m):
            d, s, n = m._args(3)
            w(d, self.wstr(m, s)[:max(0, n - 1)])
            m._ret(d, 3)

        def lstrcatW(m):
            d, s = m._args(2)
            w(d, self.wstr(m, d) + self.wstr(m, s))
            m._ret(d, 2)

        def CompareStringW(m):
            _loc, _flags, a, na, b, nb = m._args(6)
            sa = self.wstr(m, a) if na == 0xFFFFFFFF else bytes(m.mu.mem_read(a, 2 * na)).decode("utf-16-le")
            sb = self.wstr(m, b) if nb == 0xFFFFFFFF else bytes(m.mu.mem_read(b, 2 * nb)).decode("utf-16-le")
            sa, sb = sa.casefold(), sb.casefold()
            m._ret(1 if sa < sb else 2 if sa == sb else 3, 6)

        def SHGetSpecialFolderPathW(m):
            _h, out, _csidl, _create = m._args(4)
            w(out, DOCS)
            m._ret(1, 4)

        def CreateDirectoryW(m):
            a, _sec = m._args(2)
            p = self.local(self.wstr(m, a))
            existed = p.exists()
            p.mkdir(exist_ok=True)
            m._ret(0 if existed else 1, 2)

        def GetFileAttributesExW(m):
            a, _level, info = m._args(3)
            p = self.local(self.wstr(m, a))
            if not p.exists():
                m._ret(0, 3)
                return
            m.mu.mem_write(info, struct.pack("<I", 0x10 if p.is_dir() else 0x20) + b"\0" * 32)
            m._ret(1, 3)

        def FindFirstFileW(m):
            m._args(2)
            m._ret(0xFFFFFFFF, 2)                   # nothing found: the folder test the routing makes

        def CreateFileW(m):
            a, access, _share, _sec, _disp, _flags, _tmpl = m._args(7)
            p = self.local(self.wstr(m, a))
            assert access == 4, "append only (FILE_APPEND_DATA)"
            p.touch()
            h = 0x500 + 4 * len(self.handles)
            self.handles[h] = p
            m._ret(h, 7)

        def WriteFile(m):
            h, buf, n, wrote, _ov = m._args(5)
            with open(self.handles[h], "ab") as f:
                f.write(bytes(m.mu.mem_read(buf, n)))
            m.mu.mem_write(wrote, struct.pack("<I", n))
            m._ret(1, 5)

        def CloseHandle(m):
            m._args(1)
            m._ret(1, 1)

        def GetLocalTime(m):
            st, = m._args(1)
            m.mu.mem_write(st, struct.pack("<8H", 2026, 11, 0, 15, 9, 8, 7, 0))
            m._ret(0, 1)

        for fn in (lstrlenW, lstrcpyW, lstrcpynW, lstrcatW, CompareStringW, SHGetSpecialFolderPathW,
                   CreateDirectoryW, GetFileAttributesExW, FindFirstFileW, CreateFileW, WriteFile, CloseHandle,
                   GetLocalTime):
            m.extra[fn.__name__] = fn

    def save_folder(self) -> Path:
        # The emulated executable is C:\Games\Village\game.exe: its saves are Documents\LDW\game.
        return self.local(DOCS + "\\LDW\\game")


@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class RecordTests(unittest.TestCase):
    def machine(self, game, slot=2):
        import tempfile
        import shutil
        root = Path(tempfile.mkdtemp(prefix="gm"))
        self.addCleanup(shutil.rmtree, root, True)
        m = Machine(game)
        files = FileCalls(root)
        files.install(m)
        manager, field = SAVE_MANAGER[game]
        m.mu.mem_write(manager, struct.pack("<I", HEAP + 0x60000))
        m.mu.mem_write(HEAP + 0x60000 + field, struct.pack("<I", slot))
        self.assertEqual(m.export(game), 1)
        return m, files

    def find(self, m, game, regs):
        c = RECORD[game]
        mu = m.mu
        esp = STACK - 0x400
        stack = [0x11111111] * 16
        if game == 2:
            # The row's `call 0x473E05` at 0x4633CD: the villager's index is [esp+0x1C] at the call.
            stack[7] = VV2_INDEX
            mu.mem_write(VV2_VILLAGE + VV2_INDEX * 0xE48C + 0x44, struct.pack("<I", regs["carry"]))
            regs = {UC_X86_REG_ESI: VV2_VILLAGE}
        mu.mem_write(esp, struct.pack("<16I", *stack))
        before = {r: v for r, v in REGS.items()}
        before.update(regs)
        for r, v in before.items():
            mu.reg_write(r, v)
        mu.reg_write(UC_X86_REG_ECX, 0xC1C1C1C1)
        before[UC_X86_REG_ECX] = 0xC1C1C1C1
        mu.reg_write(UC_X86_REG_EFLAGS, 0x246)
        mu.reg_write(UC_X86_REG_ESP, esp)
        m.stop_at = {c["next"]}
        m.stopped = None
        mu.emu_start(c["site"], 0xFFFFFFFF, count=400000)
        self.assertEqual(m.stopped, c["next"], "the row's own code continues")
        after = {r: mu.reg_read(r) for r in before}
        if game == 3:
            del after[UC_X86_REG_EAX], before[UC_X86_REG_EAX]   # the replayed movzx loads eax, as the row does
        self.assertEqual(after, before, "every register as it was")
        self.assertEqual(mu.reg_read(UC_X86_REG_EFLAGS) & 0xFFF, 0x246, "and the flags")
        return esp, mu.reg_read(UC_X86_REG_ESP)

    def test_the_record_sites_are_the_rows_bytes_in_every_rendering(self):
        rows = {p.id: p.raw for p in vfp.load_fun_patches()}
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                m = Machine(game)
                va, row, patched, stub = m.record_probe()
                self.assertEqual(va, RECORD[game]["site"])
                self.assertEqual(_rendered_bytes(game, va, len(row)), row)
                detours = rows[f"vv{game}_super_secret_golden_mushroom"]["runtime_detours"]
                self.assertIn({"va": f"0x{va:X}", "stock_bytes": row.hex().upper(), "routine": "part of the secret",
                               "installed_by": f"VVFP Golden Mushroom.dll, ordinal {game}"}, detours)
                self.assertEqual(m.export(game), 1)
                self.assertEqual(bytes(m.mu.mem_read(va, len(patched))), patched)

    def test_each_golden_find_appends_one_line_and_continues_as_the_row(self):
        import vv_game_mechanics_counts as counts
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                m, files = self.machine(game, slot=2)
                esp, after = self.find(m, game, dict(RECORD[game]["golden"]))
                if game == 1:
                    self.assertEqual((after, rd32(m.mu, after)), (esp - 4, 0x64), "the row's push, then its jmp")
                elif game == 2:
                    self.assertEqual((after, rd32(m.mu, after)), (esp - 4, 0x4633D2), "the row's call frame")
                else:
                    self.assertEqual(after, esp)
                self.assertEqual(m.record_stats(), (1, 1))
                self.find(m, game, dict(RECORD[game]["golden"]))
                self.assertEqual(m.record_stats(), (2, 2))
                placed = (files.save_folder() / "Virtual Villagers Fun Patcher" / "Save 2" / "Data"
                          / "Golden Mushrooms" / "Golden Mushrooms - Save 2.txt")
                self.assertEqual(placed.read_bytes(), b"2026-11-15 09:08:07\r\n" * 2)
                self.assertEqual(counts.golden_record(files.save_folder(), 2), ["2026-11-15"] * 2)
                self.assertIsNone(counts.golden_record(files.save_folder(), 1))
                self.assertFalse((files.save_folder() / "Virtual Villagers Fun Patcher Data").exists(),
                                 "no older-layout folder for a new file")

    def test_any_other_kind_is_never_recorded(self):
        for game in (2, 3, 4, 5):
            with self.subTest(game=game):
                m, files = self.machine(game)
                self.find(m, game, dict(RECORD[game]["other"]))
                self.assertEqual(m.record_stats(), (0, 0))
                self.assertFalse(files.save_folder().exists() and any(files.save_folder().rglob("*.txt")))

    def test_no_slot_writes_nothing_and_still_continues(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                m, files = self.machine(game, slot=0)
                self.find(m, game, dict(RECORD[game]["golden"]))
                self.assertEqual(m.record_stats(), (1, 0))
                self.assertFalse(files.save_folder().exists() and any(files.save_folder().rglob("*.txt")))


if __name__ == "__main__":
    unittest.main()
