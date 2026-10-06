"""A New Home: "Fix Vanilla Bugs" (vv1_fix_vanilla_bugs).

One row holds every base-game bug fix the owner has approved for A New Home;
each fix is its own exact-byte patch in the row and has its own tests here.
A later approved fix is added as another patch in the same row and another
test class below.

1. A Mysterious Vial (blue liquid), "Drink the liquid", toddler result.  The
   two-choice resolve 0x419380, case 0x419C3F: rand(100) < 50 turns the
   drinker back into a toddler -- age +0x348 and +0x34C := 80, pregnancy
   +0x358 := 0 (0x419CC1) -- but leaves the litter size +0x35C alone.  The
   conception routine writes +0x35C only for twins (0x43BC4E) and triplets
   (0x43BC8C), never for one baby, and delivery reads it (0x42F011), so a
   villager who drank while carrying twins or triplets keeps 2 or 3 and her
   next single pregnancy brings twins or triplets.  Seen live (v1.35.49 test
   build without the fix, 2026-10-02): Pupa, set pregnant with litter 2,
   drank and became a toddler: +0x358 1028 -> 0, +0x35C stayed 2.

   The record tail 0x419CC1..0x419CEB is re-encoded with the drinker's record
   computed once, which leaves room to clear +0x35C beside +0x358 -- as the
   game's own delivery (0x42F0B2/0x42F0C7) and villager creation
   (0x43C71C/0x43C722, 0x43CAB8/0x43CABE) do.  Everything else the tail
   leaves (fields, EAX/ECX/EDX, the popped registers) is the base game's.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from capstone.x86 import X86_OP_MEM
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    load_builds,
    load_fun_patches,
    load_public_fun_patches,
    render_patched_bytes,
)

FEATURE_ID = "vv1_fix_vanilla_bugs"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")

VIAL_OFFSET = 0x19CC1
VIAL_STOCK = bytes.fromhex(
    "899C02580300008B8E985000008B96A850000069C9D80300005F8D04118B88480300005D5E89884C030000"
)
VIAL_PATCHED = bytes.fromhex(
    "8D040289985803000089985C0300008B96A85000008B88480300005F5D5E89884C0300000F1F8000000000"
)
# Every default name can be chosen (tests/test_every_default_name_can_be_chosen.py):
# the creator's and the twin's name rolls cover the whole list.
NAME_FIXES = (
    (0x3C645, bytes.fromhex("6A64"), bytes.fromhex("6A65")),
    (0x3C657, bytes.fromhex("40"), bytes.fromhex("90")),
    (0x3C674, bytes.fromhex("40"), bytes.fromhex("90")),
    (0x3C9FB, bytes.fromhex("83F862"), bytes.fromhex("83F864")),
    (0x3CA06, bytes.fromhex("6A64"), bytes.fromhex("6A65")),
    (0x3CA10, bytes.fromhex("40"), bytes.fromhex("90")),
)
FIXES = ((VIAL_OFFSET, VIAL_STOCK, VIAL_PATCHED),) + NAME_FIXES

# Game addresses and fields.
BLUE_VIAL = 0x419C3F           # resolve 0x419380's case for the blue vial
RAND = 0x402F10
STUBS = {
    0x433970: 4,   # text table lookup
    0x44B23D: 0,   # sprintf (cdecl)
    0x4184A0: 8,   # show the result text
    0x443FA0: 8,   # queue the dance (the other result)
}
STRIDE = 0x3D8
AGE, AGE2, PREGNANT, LITTER, HEALTH = 0x348, 0x34C, 0x358, 0x35C, 0x344

STACK = 0x70000000
THIS = 0x20000000
POOL = 0x30000000
RETURN = 0x0BAD0000
FRAME = 0x2710


def _vv1():
    return next(build for build in load_builds() if build.id == "vv1")


def _render(mode: str, ids) -> bytes:
    rendered, _ = render_patched_bytes(STOCK, _vv1(), mode, list(ids))
    return bytes(rendered)


def _other_public_vv1_ids() -> list[str]:
    return [p.id for p in load_public_fun_patches() if p.game_id == "vv1" and p.id != FEATURE_ID]


def _changed_bytes(before: bytes, after: bytes) -> list[int]:
    field = pefile.PE(data=after, fast_load=True).OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    return [
        i for i in range(min(len(before), len(after)))
        if before[i] != after[i] and not field <= i < field + 4
    ]


def _allowed() -> set[int]:
    allowed = set()
    for offset, before, _ in FIXES:
        allowed.update(range(offset, offset + len(before)))
    return allowed


def _drink(exe: bytes, roll: int, drinker: int, pregnant: int, litter: int):
    """Run the blue vial's "Drink the liquid" (choice 1) inside a frame laid
    out as the resolve's own; return the drinker's record and the registers
    the resolve returns with."""
    pe = pefile.PE(data=exe)
    image = pe.get_memory_mapped_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(0x400000, image)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(THIS, 0x10000)
    mu.mem_map(POOL, 0x100000)
    mu.mem_map(RETURN, 0x1000)
    mu.mem_write(THIS + 0x509C, struct.pack("<i", 1))          # choice: drink
    mu.mem_write(THIS + 0x5098, struct.pack("<i", drinker))
    mu.mem_write(THIS + 0x50A8, struct.pack("<I", POOL))
    rec = POOL + drinker * STRIDE
    for field, value in ((AGE, 1028), (AGE2, 1028), (PREGNANT, pregnant), (LITTER, litter), (HEALTH, 99)):
        mu.mem_write(rec + field, struct.pack("<i", value))
    calls = []

    def on_code(uc, address, size, user_data):
        pop = None
        value = 0
        if address == RAND:
            pop, value = 0, roll
        elif address in STUBS:
            pop = STUBS[address]
        if pop is None:
            return
        calls.append(address)
        esp = uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_EAX, value)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        uc.reg_write(UC_X86_REG_EIP, ret)

    mu.hook_add(UC_HOOK_CODE, on_code)
    top = STACK - 4
    mu.mem_write(top, struct.pack("<I", RETURN))
    esp = top - FRAME - 16
    # pushed by the prologue: ebx, esi, then ebp, edi
    mu.mem_write(esp, struct.pack("<IIII", 0x5EED0004, 0x5EED0003, 0x5EED0002, 0x5EED0001))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ESI, THIS)
    mu.reg_write(UC_X86_REG_EBX, 0)        # the resolve's zero register (0x419394)
    mu.emu_start(BLUE_VIAL, RETURN, count=100000)
    assert mu.reg_read(UC_X86_REG_ESP) == STACK
    assert tuple(mu.reg_read(r) for r in (UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESI, UC_X86_REG_EBX)) == (
        0x5EED0004, 0x5EED0003, 0x5EED0002, 0x5EED0001)
    record = bytes(mu.mem_read(rec, STRIDE))
    registers = tuple(mu.reg_read(r) for r in (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX))
    pool = bytes(mu.mem_read(POOL, 0x100000))
    return record, registers, calls, pool


def _field(record: bytes, offset: int) -> int:
    return struct.unpack_from("<i", record, offset)[0]


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.feature = next(p for p in load_fun_patches() if p.id == FEATURE_ID)

    def test_manifest_row(self) -> None:
        raw = self.feature.raw
        self.assertEqual(raw["game_id"], "vv1")
        self.assertEqual(raw["name"], "Fix Vanilla Bugs")
        self.assertIn(FEATURE_ID, {p.id for p in load_public_fun_patches()})
        self.assertNotIn("dependencies", raw)
        self.assertIn("**Needs no other patch.**", raw["description"])
        pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])) for p in raw["patches"]]
        self.assertEqual(pinned, list(FIXES))

    def test_default_on(self) -> None:
        from vv_fun_patcher_gui import DEFAULT_OFF_FUN_PATCH_IDS, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS

        self.assertNotIn(FEATURE_ID, DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(FEATURE_ID, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)

    def test_stock_bytes_and_offset(self) -> None:
        pe = pefile.PE(str(STOCK), fast_load=True)
        self.assertEqual(pe.get_offset_from_rva(0x419CC1 - 0x400000), VIAL_OFFSET)
        self.assertEqual(self.stock[VIAL_OFFSET:VIAL_OFFSET + len(VIAL_STOCK)], VIAL_STOCK)
        # the resolve keeps EBX zero for the whole switch
        self.assertEqual(self.stock[0x19394:0x19396], bytes.fromhex("33DB"))

    def test_the_litter_is_written_only_by_these_stock_sites(self) -> None:
        """Root cause, pinned: +0x35C is written by delivery, by the two
        villager creators and, for twins and triplets only, by conception;
        the vial result clears +0x358 without it."""
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.detail = True
        md.skipdata = True
        writes = {PREGNANT: [], LITTER: []}
        for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            try:
                ops = ins.operands
            except Exception:  # skipdata
                continue
            if ins.mnemonic == "mov" and ops and ops[0].type == X86_OP_MEM and ops[0].mem.disp in writes \
                    and ins.reg_name(ops[0].mem.base) != "esp":
                writes[ops[0].mem.disp].append(ins.address)
        self.assertEqual(writes[LITTER], [0x424326, 0x42F0C7, 0x43BC4E, 0x43BC8C, 0x43C722, 0x43CABE])
        self.assertEqual(writes[PREGNANT], [0x4195BE, 0x419CC1, 0x41C1E4, 0x42431C, 0x42F0B2, 0x43BBFA, 0x43C71C, 0x43CAB8])

    def test_nothing_else_branches_into_the_region(self) -> None:
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        start, end = 0x419CC1, 0x419CC1 + len(VIAL_STOCK)
        incoming = []
        for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            if not (ins.mnemonic.startswith("j") or ins.mnemonic == "call"):
                continue
            try:
                target = int(ins.op_str, 16)
            except ValueError:
                continue
            if start <= target < end and not start <= ins.address < end:
                incoming.append((hex(ins.address), hex(target)))
        self.assertEqual(incoming, [])

    def test_patched_region_decodes(self) -> None:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        listing = [(i.address, i.mnemonic, i.op_str) for i in md.disasm(VIAL_PATCHED, 0x419CC1)]
        self.assertEqual(sum(i.size for i in md.disasm(VIAL_PATCHED, 0x419CC1)), len(VIAL_STOCK))
        self.assertEqual(
            listing,
            [
                (0x419CC1, "lea", "eax, [edx + eax]"),
                (0x419CC4, "mov", "dword ptr [eax + 0x358], ebx"),
                (0x419CCA, "mov", "dword ptr [eax + 0x35c], ebx"),
                (0x419CD0, "mov", "edx, dword ptr [esi + 0x50a8]"),
                (0x419CD6, "mov", "ecx, dword ptr [eax + 0x348]"),
                (0x419CDC, "pop", "edi"),
                (0x419CDD, "pop", "ebp"),
                (0x419CDE, "pop", "esi"),
                (0x419CDF, "mov", "dword ptr [eax + 0x34c], ecx"),
                (0x419CE5, "nop", "dword ptr [eax]"),
            ],
        )

    def test_render_alone_in_every_mode(self) -> None:
        allowed = _allowed()
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, [])
                rendered = _render(mode, [FEATURE_ID])
                for offset, before, after in FIXES:
                    self.assertEqual(without[offset:offset + len(before)], before)
                    self.assertEqual(rendered[offset:offset + len(after)], after)
                diff = _changed_bytes(without, rendered)
                self.assertTrue(diff)
                self.assertTrue(set(diff) <= allowed, [hex(i) for i in sorted(set(diff) - allowed)[:8]])
                self.assertEqual(len(rendered), len(without))

    def test_render_with_every_other_vv1_patch_in_every_mode(self) -> None:
        others = _other_public_vv1_ids()
        self.assertGreater(len(others), 10)
        allowed = _allowed()
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, others)
                rendered = _render(mode, others + [FEATURE_ID])
                for offset, before, after in FIXES:
                    self.assertEqual(without[offset:offset + len(before)], before)
                    self.assertEqual(rendered[offset:offset + len(after)], after)
                diff = _changed_bytes(without, rendered)
                self.assertTrue(set(diff) <= allowed, [hex(i) for i in sorted(set(diff) - allowed)[:8]])
                self.assertEqual(len(rendered), len(without))


class BlueVialLitterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        others = _other_public_vv1_ids()
        cls.builds = {}
        for mode in MODES:
            cls.builds[(mode, "stock")] = _render(mode, [])
            cls.builds[(mode, "patched")] = _render(mode, [FEATURE_ID])
            cls.builds[(mode, "patched_with_all")] = _render(mode, others + [FEATURE_ID])

    def test_emulated_toddler_result_ends_the_whole_pregnancy(self) -> None:
        for (mode, label), exe in self.builds.items():
            stock = self.builds[(mode, "stock")]
            for drinker in (0, 5, 200):
                for pregnant, litter in ((1028, 2), (900, 3), (0, 0), (0, 2)):
                    with self.subTest(mode=mode, build=label, drinker=drinker, litter=litter, pregnant=pregnant):
                        record, registers, calls, pool = _drink(exe, 10, drinker, pregnant, litter)
                        self.assertEqual((_field(record, AGE), _field(record, AGE2)), (80, 80))
                        self.assertEqual(_field(record, PREGNANT), 0)
                        self.assertEqual(_field(record, LITTER), litter if label == "stock" else 0)
                        s_record, s_registers, s_calls, s_pool = _drink(stock, 10, drinker, pregnant, litter)
                        # Everything else is the base game's: the record but
                        # the litter, the rest of the pool, the registers the
                        # resolve returns with and the calls it makes.
                        mask = lambda r: r[:LITTER] + r[LITTER + 4:]  # noqa: E731
                        self.assertEqual(mask(record), mask(s_record))
                        start = drinker * STRIDE
                        self.assertEqual(pool[:start] + pool[start + STRIDE:], s_pool[:start] + s_pool[start + STRIDE:])
                        self.assertEqual(registers, s_registers)
                        self.assertEqual(calls, s_calls)

    def test_emulated_dance_result_unchanged(self) -> None:
        for (mode, label), exe in self.builds.items():
            with self.subTest(mode=mode, build=label):
                record, _registers, calls, _pool = _drink(exe, 50, 7, 1028, 2)
                self.assertEqual((_field(record, AGE), _field(record, PREGNANT), _field(record, LITTER)), (1028, 1028, 2))
                self.assertIn(0x443FA0, calls)


if __name__ == "__main__":
    unittest.main()
