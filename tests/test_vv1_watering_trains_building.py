"""Watering the Field Trains Building (A New Home).

The owner: "Watering the field" gives Building skill, but only when it makes
progress towards the garden puzzle.

What is pinned here, all against the stock executable and the shipped DLL:

* "Watering the field" is string 588, and 0x43FC20 is the only job that uses
  it; it queues the garden progress action (type 14, parameter 4) and no
  practice action -- so stock, it trains nothing.
* 0x43B1E6 holds the progress step's stock bytes, and it is the only place
  the garden count (+0x9FBC) is raised.
* The DLL's stub, RUN in an emulator over the real code: with the garden not
  yet done it appends exactly one practice-Building action (0x4399F0: this =
  the villager array, the villager's index, type 6, append mode, skill 4)
  and then performs the stock increment and resumes at 0x43B1F2; with the
  garden done it appends nothing and still increments.  Every register the
  stock code relies on is preserved.
* The jmp written at the site lands on the stub, and the row, bridge,
  bundling and README are in place.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX,
                               UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX,
                               UC_X86_REG_ESI, UC_X86_REG_ESP)

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
DLL = ROOT / "assets" / "watering" / "VVFP VV1 Watering Builds.dll"
MANIFEST = ROOT / "data" / "vv1_watering_trains_building_feature.json"
ORIGINS_C = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
ORIGINS_DLL = ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"
ORIGINS_MANIFEST = ROOT / "data" / "vv1_origins_feature.json"

SITE = 0x43B1E6
RESUME = 0x43B1F2
PUSH_ACTION = 0x4399F0
THIS = 0x50000000          # the villager array (esi)
STATE = 0x60000000         # the village state ([esi+0x3E010])
STACK = 0x70000000
SENTINEL = 0x0BADF00D


def _stock_pe():
    pe = pefile.PE(str(STOCK), fast_load=True)
    return pe, STOCK.read_bytes()


def _stock(va: int, n: int) -> bytes:
    pe, data = _stock_pe()
    off = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
    return data[off:off + n]


def _dll():
    pe = pefile.PE(str(DLL))
    exports = {e.name.decode(): pe.OPTIONAL_HEADER.ImageBase + e.address
               for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    return pe, exports


def _emulator():
    pe, exports = _dll()
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    size = (len(image) + 0xFFFF) & ~0xFFFF
    mu.mem_map(base, size)
    mu.mem_write(base, image)
    mu.mem_map(THIS, 0x100000)
    mu.mem_map(STATE, 0x10000)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(0x400000, 0x100000)          # the game's code pages, for the call targets
    return mu, exports


def _stub_va() -> int:
    """The stub's address: run the probe export in the emulator."""
    mu, exports = _emulator()
    buf = STACK + 0x8000
    esp = STACK + 0x4000
    ret = 0x400100
    args = [buf, buf + 0x20, buf + 0x40, buf + 0x60]   # site, stock, patched, stub
    mu.mem_write(esp, struct.pack("<5I", ret, *args))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(exports["VvfpVv1WateringBuildsProbe"], ret)
    site, = struct.unpack("<I", mu.mem_read(buf, 4))
    stock = bytes(mu.mem_read(buf + 0x20, 12))
    patched = bytes(mu.mem_read(buf + 0x40, 12))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0x60, 4))
    return site, stock, patched, stub


def _run_stub(garden_done: int, progress: int, idx: int):
    mu, exports = _emulator()
    _, _, _, stub = _stub_va()
    # esi = villager array; [esi+0x3E010] = state
    mu.mem_write(THIS + 0x3E010, struct.pack("<I", STATE))
    mu.mem_write(STATE + 0x9FBC, struct.pack("<I", progress))
    mu.mem_write(STATE + 0x9FC0, bytes([garden_done]))
    # The routine's frame at the site: [esp] edi, ebp, ebx, esi, ret, idx
    esp = STACK + 0x4000
    mu.mem_write(esp, struct.pack("<6I", 0xED1, 0xEB9, 0xEB8, THIS, 0x401234, idx))
    regs = {UC_X86_REG_ESP: esp, UC_X86_REG_ESI: THIS, UC_X86_REG_EDI: 0x7777,
            UC_X86_REG_EBX: 0x5555, UC_X86_REG_EBP: 0x6666, UC_X86_REG_ECX: 0x1111,
            UC_X86_REG_EDX: 0x2222, UC_X86_REG_EAX: 0x3333}
    for reg, value in regs.items():
        mu.reg_write(reg, value)
    calls = []
    # 0x4399F0 stands in as: clobber eax/ecx/edx as a real call may, ret 0x1C.
    mu.mem_write(PUSH_ACTION, bytes.fromhex("B8ADDE0000B9ADDE0000BAADDE0000C21C00"))

    def record(uc, address, size, _):
        if address == PUSH_ACTION:
            sp = uc.reg_read(UC_X86_REG_ESP)
            ret, *args = struct.unpack("<8I", uc.mem_read(sp, 32))
            calls.append({"this": uc.reg_read(UC_X86_REG_ECX), "args": args})

    mu.hook_add(UC_HOOK_CODE, record, begin=PUSH_ACTION, end=PUSH_ACTION)
    mu.emu_start(stub, RESUME, count=500)
    out = {name: mu.reg_read(reg) for name, reg in (
        ("eax", UC_X86_REG_EAX), ("esi", UC_X86_REG_ESI), ("edi", UC_X86_REG_EDI),
        ("ebx", UC_X86_REG_EBX), ("ebp", UC_X86_REG_EBP), ("esp", UC_X86_REG_ESP))}
    progress_after, = struct.unpack("<I", mu.mem_read(STATE + 0x9FBC, 4))
    return calls, out, progress_after, esp


class StockTests(unittest.TestCase):
    def test_the_site_holds_the_garden_progress_step(self):
        self.assertEqual(_stock(SITE, 12), bytes.fromhex("8B8610E00300FF80BC9F0000"),
                         "mov eax,[esi+0x3E010]; inc dword ptr [eax+0x9FBC]")
        self.assertEqual(_stock(RESUME, 6), bytes.fromhex("8B8610E00300"))

    def test_watering_the_field_is_string_588_and_trains_nothing_stock(self):
        pe, data = _stock_pe()
        base = pe.OPTIONAL_HEADER.ImageBase
        off = lambda va: pe.get_offset_from_rva(va - base)
        table = {}
        for i in range(0x275):
            sid, en = struct.unpack_from("<2I", data, off(0x487208 + i * 20))
            table[sid] = en
        text = data[off(table[588]):data.index(b"\0", off(table[588]))]
        self.assertEqual(text, b"Watering the field")
        # 0x43FC20 loads it (push 0x24C) and queues 14/4, no type 6.
        body = _stock(0x43FC20, 0x200)
        self.assertIn(bytes.fromhex("684C020000"), body[:0x40], "push 0x24C: string 588")
        end = body.index(bytes.fromhex("E8"), body.index(bytes.fromhex("6A046A006A006A006A006A0E")))
        self.assertNotIn(bytes.fromhex("6A006A006A006A006A06"), body[:end + 40],
                         "no practice (type 6) action is queued by the stock job")
        self.assertIn(bytes.fromhex("6A046A006A006A006A006A0E"), body,
                      "it queues the garden progress action: type 14, parameter 4")


class StubTests(unittest.TestCase):
    def test_the_site_jmp_lands_on_the_stub(self):
        site, stock, patched, stub = _stub_va()
        self.assertEqual(site, SITE)
        self.assertEqual(stock, _stock(SITE, 12))
        self.assertEqual(patched[0], 0xE9)
        rel, = struct.unpack("<i", patched[1:5])
        self.assertEqual((SITE + 5 + rel) & 0xFFFFFFFF, stub)
        self.assertEqual(patched[5:], b"\x90" * 7)

    def test_garden_in_progress_queues_one_practice_building_action(self):
        calls, regs, progress, esp = _run_stub(garden_done=0, progress=41, idx=17)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["this"], THIS)
        # (idx, type, x, y, a6, mode, param)
        self.assertEqual(calls[0]["args"], [17, 6, 0, 0, 0, 0, 4])
        self.assertEqual(progress, 42, "the stock increment still runs")
        self.assertEqual(regs["eax"], STATE, "eax = state, as the stock bytes leave it")
        self.assertEqual((regs["esi"], regs["edi"], regs["ebx"], regs["ebp"], regs["esp"]),
                         (THIS, 0x7777, 0x5555, 0x6666, esp), "registers preserved")

    def test_garden_done_queues_nothing(self):
        calls, regs, progress, esp = _run_stub(garden_done=1, progress=200, idx=3)
        self.assertEqual(calls, [], "no progress, no Building")
        self.assertEqual(progress, 201)
        self.assertEqual(regs["eax"], STATE)
        self.assertEqual(regs["esp"], esp)

    def test_the_last_step_that_completes_the_garden_still_counts(self):
        calls, _, progress, _ = _run_stub(garden_done=0, progress=199, idx=0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(progress, 200)


class RowTests(unittest.TestCase):
    def test_the_row_pins_the_dll_and_changes_no_bytes(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "vv1_watering_trains_building")
        self.assertEqual(manifest["game_id"], "vv1")
        self.assertEqual(manifest["patches"], [])
        self.assertEqual(manifest["dependencies"], ["vv1_enable_origins_exclusive_features"])
        pinned = {f["destination"]: f["sha256"].upper() for f in manifest["companion_files"]}
        self.assertEqual(pinned, {"VVFP VV1 Watering Builds.dll":
                                  hashlib.sha256(DLL.read_bytes()).hexdigest().upper()})
        self.assertIn("**Requires Enable Origins-Exclusive Features**", manifest["description"])

    def test_the_origins_companion_loads_and_installs_it(self):
        source = ORIGINS_C.read_text(encoding="utf-8")
        self.assertIn('"VVFP VV1 Watering Builds.dll"', source)
        self.assertIn('GetProcAddress(companion, "VvfpVv1WateringBuildsInstall")', source)
        tick = source[source.index("__stdcall Vv1MaskTick(void) {"):]
        self.assertIn("vv1_watering_bridge();", tick[:700])
        data = ORIGINS_DLL.read_bytes()
        self.assertIn(b"VVFP VV1 Watering Builds.dll", data)
        pinned = [f["sha256"].upper() for f in json.loads(ORIGINS_MANIFEST.read_text(encoding="utf-8"))["companion_files"]
                  if f["destination"] == ORIGINS_DLL.name]
        self.assertEqual(pinned, [hashlib.sha256(data).hexdigest().upper()])

    def test_registered_bundled_documented(self):
        patcher = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertIn('ROOT / "data" / "vv1_watering_trains_building_feature.json"', patcher)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("assets/watering/VVFP VV1 Watering Builds.dll", release)
        self.assertIn("data/vv1_watering_trains_building_feature.json", release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("- Patch ID: `vv1_watering_trains_building`", readme)


if __name__ == "__main__":
    unittest.main()
