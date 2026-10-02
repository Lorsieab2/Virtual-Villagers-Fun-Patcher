"""The Lost Children: the fire pit's dry grass is drawn above its firewood.

The owner: "Can you allow the Dry grass to render above the wood when they are
both placed in the firepit?"

Root cause, read from the stock executable.  The village scene builds a flat
list of static pictures (entries of 0x14 bytes at scene+0x1E0, appended by
0x41B580 / 0x41B5D0) and the scene draw at 0x41B630 paints that list in
insertion order -- there is no depth sort.  The scene builder adds the fire
pit's two contents back to back:

* 0x41C5EA  if world[+0x30458] == 1: carrying.png (scene+0x15E8) frame 15,
  the dry-grass bundle, at (0x2DE, 0x34A)            -> 0x41B5D0
* 0x41C613  if world[+0x30459] == 1: woodpile.png (scene+0x15F4) at
  (0x2CA, 0x340)                                     -> 0x41B580

The 40x25 grass lies wholly inside the 67x44 woodpile, and the woodpile is
appended second, so it is painted over the grass.

The fix swaps the two self-contained blocks in place (80 bytes, same start
and end); each keeps its own world load, flag test and short jne, and only
the two call displacements are re-aimed.  The tests here pin the bytes,
decode them, render them in every population mode alone and with every other
VV2 patch, and run the real scene-builder region and the real list-append
helpers in an emulator for all four flag states.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    load_builds,
    load_fun_patches,
    load_public_fun_patches,
    render_patched_bytes,
)

FEATURE_ID = "vv2_firepit_dry_grass_above_wood"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")

START, END = 0x41C5EA, 0x41C63A
OFFSET = 0x1C5EA
APPEND_IMAGE = 0x41B580        # (img, x, y): frame left at -1
APPEND_FRAME = 0x41B5D0        # (img, x, y, frame)
STOCK_BYTES = bytes.fromhex(
    "8B868016000080B85804030001751A8B8EE81500006A0F684A03000068DE020000518BCEE8BDEFFFFF"
    "8B968016000080BA590403000175188B86F4150000684003000068CA020000508BCEE846EFFFFF"
)
PATCHED_BYTES = bytes.fromhex(
    "8B968016000080BA590403000175188B86F4150000684003000068CA020000508BCEE86FEFFFFF"
    "8B868016000080B85804030001751A8B8EE81500006A0F684A03000068DE020000518BCEE896EFFFFF"
)

# Emulation layout.
STACK = 0x70000000
SCENE = 0x20000000
WORLD = 0x30000000
RETURN = 0x0BAD0000
WOOD_IMAGE = 0x11110000        # stands in for the woodpile.png handle
CARRY_IMAGE = 0x22220000       # stands in for the carrying.png handle
GRASS = ("carry", 0x2DE, 0x34A, 15)
WOOD = ("wood", 0x2CA, 0x340, -1)


def _vv2():
    return next(build for build in load_builds() if build.id == "vv2")


def _render(mode: str, ids) -> bytes:
    rendered, _ = render_patched_bytes(STOCK, _vv2(), mode, list(ids))
    return bytes(rendered)


def _other_public_vv2_ids() -> list[str]:
    return [
        patch.id
        for patch in load_public_fun_patches()
        if patch.game_id == "vv2" and patch.id != FEATURE_ID
    ]


def _image(exe: bytes) -> tuple[int, bytes]:
    pe = pefile.PE(data=exe)
    return pe.OPTIONAL_HEADER.ImageBase, pe.get_memory_mapped_image()


def _build_list(exe: bytes, grass: bool, wood: bool, preexisting: int = 0):
    """Run the scene builder's fire-pit region with the real append helpers
    and return the static-picture list it leaves behind."""
    base, image = _image(exe)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(base, image)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(SCENE, 0x10000)
    mu.mem_map(WORLD, 0x40000)
    mu.mem_map(RETURN, 0x1000)
    # The list as 0x41C1A0 clears it: used=0, image=0, frame=-1 for all 256.
    for index in range(0x100):
        entry = SCENE + 0x1E0 + index * 0x14
        mu.mem_write(entry, b"\0" * 0x10 + struct.pack("<i", -1))
    # Pictures some earlier part of the scene builder already queued.
    for index in range(preexisting):
        entry = SCENE + 0x1E0 + index * 0x14
        mu.mem_write(entry, b"\1\0\0\0" + struct.pack("<iiIi", index, index, 0x7700 + index, index))
    mu.mem_write(SCENE + 0x1680, struct.pack("<I", WORLD))
    mu.mem_write(SCENE + 0x15F4, struct.pack("<I", WOOD_IMAGE))
    mu.mem_write(SCENE + 0x15E8, struct.pack("<I", CARRY_IMAGE))
    mu.mem_write(WORLD + 0x30458, bytes([int(grass), int(wood)]))
    # Callee-saved registers the builder keeps live across this region.
    mu.reg_write(UC_X86_REG_ESI, SCENE)
    mu.reg_write(UC_X86_REG_EDI, 0x5EED0001)
    mu.reg_write(UC_X86_REG_EBX, 0x5EED0002)
    mu.reg_write(UC_X86_REG_EBP, 0x5EED0003)
    esp = STACK
    mu.reg_write(UC_X86_REG_ESP, esp)
    for reg in (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX):
        mu.reg_write(reg, 0xDEADBEEF)
    mu.emu_start(START, END, count=200)
    preserved = tuple(
        mu.reg_read(reg)
        for reg in (UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_ESP)
    )
    assert preserved == (SCENE, 0x5EED0001, 0x5EED0002, 0x5EED0003, esp), preserved
    names = {WOOD_IMAGE: "wood", CARRY_IMAGE: "carry"}
    entries = []
    for index in range(0x100):
        raw = bytes(mu.mem_read(SCENE + 0x1E0 + index * 0x14, 0x14))
        if raw[0] == 0:
            break
        x, y, img, frame = struct.unpack("<iiIi", raw[4:])
        entries.append((names.get(img, hex(img)), x, y, frame))
    return entries


def _changed_bytes(before: bytes, after: bytes) -> list[int]:
    """Offsets that differ, leaving out the PE header checksum the patcher
    recomputes for every output."""
    field = pefile.PE(data=after, fast_load=True).OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    return [
        i for i in range(min(len(before), len(after)))
        if before[i] != after[i] and not field <= i < field + 4
    ]


class FirepitDrawOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.feature = next(p for p in load_fun_patches() if p.id == FEATURE_ID)

    def test_manifest_row(self) -> None:
        raw = self.feature.raw
        self.assertEqual(raw["game_id"], "vv2")
        self.assertEqual(raw["name"], "Firepit: Dry Grass Drawn Above the Wood")
        self.assertIn(FEATURE_ID, {p.id for p in load_public_fun_patches()})
        self.assertNotIn("dependencies", raw)
        self.assertEqual(len(raw["patches"]), 1)
        patch = raw["patches"][0]
        self.assertEqual(int(patch["offset"], 16), OFFSET)
        self.assertEqual(bytes.fromhex(patch["before"]), STOCK_BYTES)
        self.assertEqual(bytes.fromhex(patch["after"]), PATCHED_BYTES)

    def test_default_on(self) -> None:
        from vv_fun_patcher_gui import DEFAULT_OFF_FUN_PATCH_IDS

        self.assertNotIn(FEATURE_ID, DEFAULT_OFF_FUN_PATCH_IDS)

    def test_stock_bytes_and_offset(self) -> None:
        pe = pefile.PE(str(STOCK), fast_load=True)
        self.assertEqual(pe.get_offset_from_rva(START - 0x400000), OFFSET)
        self.assertEqual(self.stock[OFFSET:OFFSET + 80], STOCK_BYTES)

    def test_patched_region_decodes_as_wood_then_grass(self) -> None:
        listing = [
            (ins.address, ins.mnemonic, ins.op_str)
            for ins in Cs(CS_ARCH_X86, CS_MODE_32).disasm(PATCHED_BYTES, START)
        ]
        self.assertEqual(sum(len(i.bytes) for i in Cs(CS_ARCH_X86, CS_MODE_32).disasm(PATCHED_BYTES, START)), 80)
        self.assertEqual(
            listing,
            [
                (0x41C5EA, "mov", "edx, dword ptr [esi + 0x1680]"),
                (0x41C5F0, "cmp", "byte ptr [edx + 0x30459], 1"),
                (0x41C5F7, "jne", "0x41c611"),
                (0x41C5F9, "mov", "eax, dword ptr [esi + 0x15f4]"),
                (0x41C5FF, "push", "0x340"),
                (0x41C604, "push", "0x2ca"),
                (0x41C609, "push", "eax"),
                (0x41C60A, "mov", "ecx, esi"),
                (0x41C60C, "call", "0x41b580"),
                (0x41C611, "mov", "eax, dword ptr [esi + 0x1680]"),
                (0x41C617, "cmp", "byte ptr [eax + 0x30458], 1"),
                (0x41C61E, "jne", "0x41c63a"),
                (0x41C620, "mov", "ecx, dword ptr [esi + 0x15e8]"),
                (0x41C626, "push", "0xf"),
                (0x41C628, "push", "0x34a"),
                (0x41C62D, "push", "0x2de"),
                (0x41C632, "push", "ecx"),
                (0x41C633, "mov", "ecx, esi"),
                (0x41C635, "call", "0x41b5d0"),
            ],
        )
        # The patched region is exactly the two stock blocks exchanged, apart
        # from the two re-aimed call displacements.
        self.assertEqual(PATCHED_BYTES[:35], STOCK_BYTES[41:76])
        self.assertEqual(PATCHED_BYTES[39:76], STOCK_BYTES[:37])

    def test_nothing_else_in_the_executable_branches_into_the_region(self) -> None:
        """Only the two stock edges to 0x41C5EA enter the region, and they land
        on the first block's own world load, so the swap is safe."""
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        incoming = []
        for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            if not (ins.mnemonic.startswith("j") or ins.mnemonic == "call"):
                continue
            try:
                target = int(ins.op_str, 16)
            except ValueError:
                continue
            if START <= target < END and not START <= ins.address < END:
                incoming.append((ins.address, target))
        self.assertEqual(incoming, [(0x41C5C6, START), (0x41C5D0, START)])

    def test_render_alone_in_every_mode(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, [])
                rendered = _render(mode, [FEATURE_ID])
                self.assertEqual(without[OFFSET:OFFSET + 80], STOCK_BYTES)
                self.assertEqual(rendered[OFFSET:OFFSET + 80], PATCHED_BYTES)
                diff = _changed_bytes(without, rendered)
                self.assertTrue(diff)
                self.assertTrue(all(OFFSET <= i < OFFSET + 80 for i in diff), [hex(i) for i in diff[:8]])
                self.assertEqual(len(rendered), len(without))

    def test_render_with_every_other_vv2_patch_in_every_mode(self) -> None:
        others = _other_public_vv2_ids()
        self.assertGreater(len(others), 10)
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, others)
                rendered = _render(mode, others + [FEATURE_ID])
                self.assertEqual(without[OFFSET:OFFSET + 80], STOCK_BYTES)
                self.assertEqual(rendered[OFFSET:OFFSET + 80], PATCHED_BYTES)
                diff = _changed_bytes(without, rendered)
                self.assertTrue(all(OFFSET <= i < OFFSET + 80 for i in diff), [hex(i) for i in diff[:8]])
                self.assertEqual(len(rendered), len(without))

    def test_emulated_order_flips_only_when_both_are_in_the_pit(self) -> None:
        stock_order = {
            (False, False): [],
            (True, False): [GRASS],
            (False, True): [WOOD],
            (True, True): [GRASS, WOOD],
        }
        patched_order = dict(stock_order)
        patched_order[(True, True)] = [WOOD, GRASS]
        others = _other_public_vv2_ids()
        for mode in MODES:
            builds = {
                "stock": _render(mode, []),
                "patched": _render(mode, [FEATURE_ID]),
                "patched_with_all": _render(mode, others + [FEATURE_ID]),
            }
            for label, exe in builds.items():
                expected = stock_order if label == "stock" else patched_order
                for (grass, wood), order in expected.items():
                    for preexisting in (0, 3):
                        with self.subTest(mode=mode, build=label, grass=grass, wood=wood, pre=preexisting):
                            entries = _build_list(exe, grass, wood, preexisting)
                            self.assertEqual(len(entries), preexisting + len(order))
                            self.assertEqual(entries[preexisting:], order)


if __name__ == "__main__":
    unittest.main()
