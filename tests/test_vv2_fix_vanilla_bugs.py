"""The Lost Children: "Fix Vanilla Bugs" (vv2_fix_vanilla_bugs).

One row holds every base-game bug fix the owner has approved for The Lost
Children; each fix is its own exact-byte patch (or group of patches) in the
row and has its own tests here.  A later approved fix is added as another
patch in the same row and another test class below.

1. The Crystal Ball (two-choice island event, chooser case 13).  "Keep it"
   (resolve 0x4204B0, case 13 at 0x421401) builds a list of every OTHER
   living villager (active byte +0x30 set, health +0x52C > 0, index != the
   keeper [this+0x50A0]) at 0x421450..0x421478, then calls rand(count) at
   0x42147B and reads list[r] at 0x421480.  With nobody else living the count
   is 0, rand(0) returns 0 and an uninitialised stack slot is used as a
   villager index: seen live, the game closes (2 of 2 tries), while with two
   villagers it works.  The owner: "Definitely fix the crash! Or make it so
   that it's not possible to get that event or body swap effect if it does
   appear."

   Both are done.  The chooser's case 13 (0x41F626) keeps the base game's own
   test (0x44BAE0(1): a living villager aged 14 or over) and now also needs
   at least two living villagers, so the finder always has someone to trade
   places with.  And the Keep-it swap is re-encoded compactly in its own
   bytes (same nine fields, same three text copies through the same routine,
   same order of the text copies) behind a test of the count: with an empty
   list nothing is swapped.  That second guard keeps Pick Island Event safe,
   which can deliver an event past its condition.  The freed bytes hold the
   case-13 count and int3 padding.
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc, UcError
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    load_builds,
    load_fun_patches,
    load_public_fun_patches,
    render_patched_bytes,
)

FEATURE_ID = "vv2_fix_vanilla_bugs"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")

HOOK_OFFSET = 0x1F636
HOOK_STOCK = bytes.fromhex("0F95C3EB5B")
HOOK_PATCHED = bytes.fromhex("E9951F0000")
SWAP_OFFSET = 0x21480
SWAP_LENGTH = 0x2EC
COUNT_VA = 0x4215D0

# Game addresses.
CHOOSER = 0x41F570
CHOOSER_DONE = 0x41F696
RAND = 0x4031A0
SPRINTF = 0x4682BD
STRCPY = 0x46C400       # the swap's name copies since #566
LOOP_START = 0x421443          # Keep it: the other-villager list is built from here
EPILOGUE = 0x42176C
STRIDE = 0xE48C
RECORDS = 256
FIELDS = (0x7E4, 0x7E8, 0x7EC, 0x7F0, 0x7F4, 0x5F0, 0x5F4, 0x6E8, 0x6EC)
TEXT = 0x564
TEXT_LEN = 0x18

# Emulation layout.
STACK = 0x70000000
THIS = 0x20000000
POOL = 0x30000000
RETURN = 0x0BAD0000
FRAME = 0x2C2C


def _vv2():
    return next(build for build in load_builds() if build.id == "vv2")


def _render(mode: str, ids) -> bytes:
    rendered, _ = render_patched_bytes(STOCK, _vv2(), mode, list(ids))
    return bytes(rendered)


def _other_public_vv2_ids() -> list[str]:
    return [p.id for p in load_public_fun_patches() if p.game_id == "vv2" and p.id != FEATURE_ID]


def _changed_bytes(before: bytes, after: bytes) -> list[int]:
    field = pefile.PE(data=after, fast_load=True).OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    return [
        i for i in range(min(len(before), len(after)))
        if before[i] != after[i] and not field <= i < field + 4
    ]


def _patched_region() -> bytes:
    feature = next(p for p in load_fun_patches() if p.id == FEATURE_ID)
    return bytes.fromhex(next(p for p in feature.raw["patches"] if int(p["offset"], 16) == SWAP_OFFSET)["after"])


# Every default name can be chosen (tests/test_every_default_name_can_be_chosen.py):
# the name rolls cover the whole list.
NAME_FIXES = (
    (0x4CCF1, bytes.fromhex("6A7B"), bytes.fromhex("6A7D")),
    (0x4CCFD, bytes.fromhex("40"), bytes.fromhex("90")),
    (0x4CD1A, bytes.fromhex("40"), bytes.fromhex("90")),
    (0x4D034, bytes.fromhex("83F87B"), bytes.fromhex("83F87C")),
    (0x4D03F, bytes.fromhex("6A7B"), bytes.fromhex("6A7D")),
    (0x4D049, bytes.fromhex("40"), bytes.fromhex("90")),
)

PERCENT_FIXES = (  # '%' in a name never a format; text boxes refuse it (#566)
    (0x0001F3B0, bytes.fromhex("E8088F0400"), bytes.fromhex("E84BD00400")),
    (0x00021826, bytes.fromhex("E8926A0400"), bytes.fromhex("E8D5AB0400")),
    (0x00029AA3, bytes.fromhex("E815E80300"), bytes.fromhex("E858290400")),
    (0x00037422, bytes.fromhex("E8960E0300"), bytes.fromhex("E8D94F0300")),
    (0x0004480D, bytes.fromhex("E8AB3A0200"), bytes.fromhex("E8EE7B0200")),
    (0x0004D05E, bytes.fromhex("E85AB20100"), bytes.fromhex("E89DF30100")),
    (0x0004D089, bytes.fromhex("E82FB20100"), bytes.fromhex("E872F30100")),
    (0x0004D397, bytes.fromhex("E821AF0100"), bytes.fromhex("E864F00100")),
    (0x0004D3C2, bytes.fromhex("E8F6AE0100"), bytes.fromhex("E839F00100")),
    (0x0004D3EF, bytes.fromhex("E8C9AE0100"), bytes.fromhex("E80CF00100")),
    (0x000650BA, bytes.fromhex("E8FE310000"), bytes.fromhex("E841730000")),
    (0x0000C8BB, bytes.fromhex("8B71308814308B5130C644020100"), bytes.fromhex("83FA2574278B71306689143089F2")),
)


def _allowed() -> set[int]:
    allowed = set(range(HOOK_OFFSET, HOOK_OFFSET + 5)) | set(range(SWAP_OFFSET, SWAP_OFFSET + SWAP_LENGTH))
    for offset, before, _ in NAME_FIXES + PERCENT_FIXES:
        allowed.update(range(offset, offset + len(before)))
    return allowed


class _Village:
    """The real executable image in unicorn with a 256-record villager pool.
    rand returns `rolls` in turn (0 when they run out, as rand(0) and rand(1)
    do); sprintf(dst, src) is the game's own call with a plain-text source,
    performed here as a copy."""

    def __init__(self, exe: bytes, living, rolls=()) -> None:
        pe = pefile.PE(data=exe)
        image = pe.get_memory_mapped_image()
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0x400000, image)
        mu.mem_map(STACK - 0x20000, 0x30000)
        mu.mem_map(THIS, 0x10000)
        mu.mem_map(POOL, (RECORDS * STRIDE + 0x10000) & ~0xFFF)
        mu.mem_map(RETURN, 0x1000)
        mu.mem_write(THIS + 0x50B0, struct.pack("<I", POOL))
        self.rolls = list(rolls)
        self.rand_bounds: list[int] = []
        self.texts_copied = 0
        rng = random.Random(len(living))
        for index in range(RECORDS):
            self._fill(index, rng)
        for index, (active, health, age) in living.items():
            rec = self.rec(index)
            mu.mem_write(rec + 0x30, bytes([active]))
            mu.mem_write(rec + 0x52C, struct.pack("<i", health))
            mu.mem_write(rec + 0x530, struct.pack("<i", age))
        mu.hook_add(UC_HOOK_CODE, self._on_code)

    def _fill(self, index: int, rng: random.Random) -> None:
        rec = self.rec(index)
        self.mu.mem_write(rec + 0x30, b"\0")
        self.mu.mem_write(rec + 0x52C, struct.pack("<i", 0))
        for field in FIELDS:
            self.mu.mem_write(rec + field, struct.pack("<I", rng.getrandbits(32)))
        name = f"text{index:03d}-{rng.getrandbits(16):04x}".encode()
        self.mu.mem_write(rec + TEXT, name.ljust(TEXT_LEN, b"\0"))

    @staticmethod
    def rec(index: int) -> int:
        return POOL + index * STRIDE

    def _on_code(self, mu, address, size, user_data) -> None:
        if address == RAND:
            esp = mu.reg_read(UC_X86_REG_ESP)
            self.rand_bounds.append(struct.unpack("<i", mu.mem_read(esp + 4, 4))[0])
            self._return(self.rolls.pop(0) if self.rolls else 0, 0)
        elif address in (SPRINTF, STRCPY):
            esp = mu.reg_read(UC_X86_REG_ESP)
            dst, src = struct.unpack("<II", mu.mem_read(esp + 4, 8))
            raw = bytes(mu.mem_read(src, 0x100))
            mu.mem_write(dst, raw[:raw.index(0) + 1])
            self.texts_copied += 1
            self._return(0, 0)

    def _return(self, value: int, pop: int) -> None:
        mu = self.mu
        esp = mu.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", mu.mem_read(esp, 4))[0]
        mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        mu.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        mu.reg_write(UC_X86_REG_EIP, ret)

    def snapshot(self) -> bytes:
        return bytes(self.mu.mem_read(POOL, RECORDS * STRIDE))

    def choose(self) -> int:
        """Run the two-choice chooser 0x41F570 and return the event it picks."""
        mu = self.mu
        esp = STACK - 4
        mu.mem_write(esp, struct.pack("<I", RETURN))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, THIS)
        saved = (0x5EED0001, 0x5EED0002, 0x5EED0003, 0x5EED0004)
        for reg, value in zip((UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_EDI, UC_X86_REG_ESI), saved):
            mu.reg_write(reg, value)
        mu.emu_start(CHOOSER, RETURN, count=2_000_000)
        assert mu.reg_read(UC_X86_REG_ESP) == STACK
        assert tuple(mu.reg_read(r) for r in (UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_EDI, UC_X86_REG_ESI)) == saved
        return mu.reg_read(UC_X86_REG_EAX)

    def keep(self, keeper: int, garbage: int = 0x7FFF0000) -> None:
        """Run "Keep it" from the list build (0x421443) through the resolve's
        epilogue, inside a frame laid out as the resolve's own: 0x2C2C bytes of
        locals (filled with `garbage`, as an unset stack slot would be) under
        the four registers the prologue pushed."""
        mu = self.mu
        mu.mem_write(THIS + 0x50A0, struct.pack("<I", keeper))
        top = STACK - 4
        mu.mem_write(top, struct.pack("<I", RETURN))
        locals_base = top - FRAME
        mu.mem_write(locals_base, struct.pack("<I", garbage) * (FRAME // 4))
        esp = locals_base - 16
        # pushed by the prologue: ebx, ebp, esi, edi (edi pushed last)
        mu.mem_write(esp, struct.pack("<IIII", 0x5EED0004, 0x5EED0003, 0x5EED0002, 0x5EED0001))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ESI, THIS)
        mu.reg_write(UC_X86_REG_EBX, 0)       # the resolve's zero register (0x4204C5)
        mu.reg_write(UC_X86_REG_EDI, 0)
        mu.reg_write(UC_X86_REG_EBP, 0)
        mu.emu_start(LOOP_START, RETURN, count=200_000)
        assert mu.reg_read(UC_X86_REG_ESP) == STACK
        assert tuple(mu.reg_read(r) for r in (UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_EBP, UC_X86_REG_EBX)) == (
            0x5EED0004, 0x5EED0003, 0x5EED0002, 0x5EED0001)


class _Builds:
    @classmethod
    def builds(cls) -> dict:
        if not hasattr(cls, "_builds"):
            others = _other_public_vv2_ids()
            builds = {}
            for mode in MODES:
                builds[(mode, "stock")] = _render(mode, [])
                builds[(mode, "patched")] = _render(mode, [FEATURE_ID])
                builds[(mode, "patched_with_all")] = _render(mode, others + [FEATURE_ID])
            cls._builds = builds
        return cls._builds


ADULT, CHILD = 400, 100


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.feature = next(p for p in load_fun_patches() if p.id == FEATURE_ID)

    def test_manifest_row(self) -> None:
        raw = self.feature.raw
        self.assertEqual(raw["game_id"], "vv2")
        self.assertEqual(raw["name"], "Fix Vanilla Bugs")
        self.assertIn(FEATURE_ID, {p.id for p in load_public_fun_patches()})
        self.assertNotIn("dependencies", raw)
        self.assertIn("**Needs no other patch.**", raw["description"])
        offsets = [(int(p["offset"], 16), len(bytes.fromhex(p["before"]))) for p in raw["patches"]]
        self.assertEqual(offsets, [(HOOK_OFFSET, 5), (SWAP_OFFSET, SWAP_LENGTH)]
                         + [(offset, len(before)) for offset, before, _ in NAME_FIXES + PERCENT_FIXES])
        self.assertEqual([(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"]))
                          for p in raw["patches"][2:]], list(NAME_FIXES + PERCENT_FIXES))
        self.assertEqual(bytes.fromhex(raw["patches"][0]["before"]), HOOK_STOCK)
        self.assertEqual(bytes.fromhex(raw["patches"][0]["after"]), HOOK_PATCHED)
        self.assertEqual(bytes.fromhex(raw["patches"][1]["before"]), self.stock[SWAP_OFFSET:SWAP_OFFSET + SWAP_LENGTH])

    def test_default_on(self) -> None:
        from vv_fun_patcher_gui import DEFAULT_OFF_FUN_PATCH_IDS, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS

        self.assertNotIn(FEATURE_ID, DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(FEATURE_ID, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)

    def test_stock_bytes(self) -> None:
        pe = pefile.PE(str(STOCK), fast_load=True)
        self.assertEqual(pe.get_offset_from_rva(0x41F636 - 0x400000), HOOK_OFFSET)
        self.assertEqual(pe.get_offset_from_rva(0x421480 - 0x400000), SWAP_OFFSET)
        self.assertEqual(self.stock[HOOK_OFFSET:HOOK_OFFSET + 5], HOOK_STOCK)
        # case 13 as the base game has it: 0x44BAE0(1) != -1
        self.assertEqual(self.stock[0x1F626:0x1F63B], bytes.fromhex("8B8EB05000006A01E8ADC4020083F8FF0F95C3EB5B"))
        # the list build and the rand call the Story companion redirects stay put
        self.assertEqual(self.stock[0x2147A:0x21480], bytes.fromhex("57E8201DFEFF"))

    def test_nothing_else_branches_into_the_rewritten_regions(self) -> None:
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        regions = ((0x41F636, 0x41F63B), (0x421480, 0x421480 + SWAP_LENGTH))
        incoming = []
        for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            if not (ins.mnemonic.startswith("j") or ins.mnemonic == "call"):
                continue
            try:
                target = int(ins.op_str, 16)
            except ValueError:
                continue
            for start, end in regions:
                if start <= target < end and not start <= ins.address < end:
                    incoming.append((hex(ins.address), hex(target)))
        self.assertEqual(incoming, [])
        data = STOCK.read_bytes()
        pointers = [
            hex(off) for off in range(0, len(data) - 3)
            if any(s <= struct.unpack_from("<I", data, off)[0] < e for s, e in regions)
        ]
        self.assertEqual(pointers, [])

    def test_patched_code_decodes(self) -> None:
        region = _patched_region()
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        hook = next(md.disasm(HOOK_PATCHED, 0x41F636))
        self.assertEqual((hook.mnemonic, hook.op_str), ("jmp", hex(COUNT_VA)))
        keep = list(md.disasm(region[:0x4215CF - 0x421480], 0x421480))
        self.assertEqual([(i.mnemonic, i.op_str) for i in keep[:2]], [("test", "edi, edi"), ("je", "0x4215c7")])
        self.assertEqual((keep[2].mnemonic, keep[2].op_str), ("mov", "edi, dword ptr [esp + eax*4 + 0x2840]"))
        self.assertEqual([(i.address, i.mnemonic, i.op_str) for i in keep[-2:]],
                         [(0x4215C7, "add", "esp, 4"), (0x4215CA, "jmp", hex(EPILOGUE))])
        calls = [i.op_str for i in keep if i.mnemonic == "call"]
        self.assertEqual(calls, [hex(STRCPY)] * 3)
        end = 0x4215CF
        self.assertEqual(region[end - 0x421480:COUNT_VA - 0x421480], b"\xCC")
        count = list(md.disasm(region[COUNT_VA - 0x421480:], COUNT_VA))
        listing = []
        for ins in count:
            listing.append((ins.mnemonic, ins.op_str))
            if ins.mnemonic == "jmp" and ins.op_str == hex(CHOOSER_DONE) and len(listing) > 3:
                break
        self.assertEqual(
            listing,
            [
                ("setne", "bl"), ("jne", "0x4215da"), ("jmp", hex(CHOOSER_DONE)),
                ("mov", "ecx, dword ptr [esi + 0x50b0]"), ("xor", "eax, eax"), ("xor", "edx, edx"),
                ("add", "ecx, 0x30"),
                ("cmp", "byte ptr [ecx], 0"), ("je", "0x4215f6"),
                ("cmp", "dword ptr [ecx + 0x4fc], 0"), ("jle", "0x4215f6"), ("inc", "eax"),
                ("add", "ecx, 0xe48c"), ("inc", "edx"), ("cmp", "edx, 0x100"), ("jl", "0x4215e7"),
                ("cmp", "eax, 2"), ("setge", "bl"), ("jmp", hex(CHOOSER_DONE)),
            ],
        )
        tail = region[0x421610 - 0x421480:]
        self.assertEqual(tail, b"\xCC" * len(tail))

    def test_render_alone_in_every_mode(self) -> None:
        allowed = _allowed()
        region = _patched_region()
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, [])
                rendered = _render(mode, [FEATURE_ID])
                self.assertEqual(without[HOOK_OFFSET:HOOK_OFFSET + 5], HOOK_STOCK)
                self.assertEqual(rendered[HOOK_OFFSET:HOOK_OFFSET + 5], HOOK_PATCHED)
                self.assertEqual(rendered[SWAP_OFFSET:SWAP_OFFSET + SWAP_LENGTH], region)
                diff = _changed_bytes(without, rendered)
                self.assertTrue(diff)
                self.assertTrue(set(diff) <= allowed, [hex(i) for i in sorted(set(diff) - allowed)[:8]])
                self.assertEqual(len(rendered), len(without))

    def test_render_with_every_other_vv2_patch_in_every_mode(self) -> None:
        others = _other_public_vv2_ids()
        self.assertGreater(len(others), 10)
        allowed = _allowed()
        region = _patched_region()
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, others)
                rendered = _render(mode, others + [FEATURE_ID])
                self.assertEqual(without[HOOK_OFFSET:HOOK_OFFSET + 5], HOOK_STOCK)
                self.assertEqual(without[SWAP_OFFSET:SWAP_OFFSET + SWAP_LENGTH], STOCK.read_bytes()[SWAP_OFFSET:SWAP_OFFSET + SWAP_LENGTH])
                self.assertEqual(rendered[SWAP_OFFSET:SWAP_OFFSET + SWAP_LENGTH], region)
                diff = _changed_bytes(without, rendered)
                self.assertTrue(set(diff) <= allowed, [hex(i) for i in sorted(set(diff) - allowed)[:8]])
                self.assertEqual(len(rendered), len(without))


class CrystalBallConditionTests(unittest.TestCase, _Builds):
    """The chooser, run for real with every rand roll answering 13 (the
    Crystal Ball): it returns 13 when the event's condition holds and the
    chooser's own fallback, event 5, after ten failed tries."""

    VILLAGES = {
        "nobody": ({}, 5, 5),
        "one living adult": ({3: (1, 80, ADULT)}, 13, 5),
        "one living child": ({3: (1, 80, CHILD)}, 5, 5),
        "adult and child": ({3: (1, 80, ADULT), 9: (1, 80, CHILD)}, 13, 13),
        "two children": ({3: (1, 80, CHILD), 9: (1, 80, CHILD)}, 5, 5),
        "adult and a dead villager": ({3: (1, 80, ADULT), 9: (1, 0, ADULT)}, 13, 5),
        "adult and an inactive record": ({3: (1, 80, ADULT), 9: (0, 80, ADULT)}, 13, 5),
        "adult and negative health": ({3: (1, 80, ADULT), 9: (1, -5, ADULT)}, 13, 5),
        "two adults at the ends": ({0: (1, 1, ADULT), 255: (1, 1, ADULT)}, 13, 13),
        "many": ({i: (1, 50, ADULT) for i in range(0, 200, 7)}, 13, 13),
    }

    def test_emulated_condition(self) -> None:
        stock_rolls = {}
        for (mode, label), exe in self.builds().items():
            for name, (living, stock_event, fixed_event) in self.VILLAGES.items():
                with self.subTest(mode=mode, build=label, village=name):
                    village = _Village(exe, living, rolls=[13] * 64)
                    event = village.choose()
                    self.assertEqual(event, stock_event if label == "stock" else fixed_event)
                    if label == "stock":
                        stock_rolls[(mode, name)] = village.rand_bounds
                    elif stock_event == fixed_event:
                        # The count consumes no random number: the same rolls
                        # as the base game whenever the outcome is the same.
                        self.assertEqual(village.rand_bounds, stock_rolls[(mode, name)])
                    else:
                        # Refused: ten event rolls, each followed by the
                        # base game's own adult picker roll.
                        self.assertEqual(village.rand_bounds[0::2], [22] * 10)


class CrystalBallKeepTests(unittest.TestCase, _Builds):
    def _keep(self, exe, living, keeper, roll, garbage=0x7FFF0000):
        village = _Village(exe, living, rolls=[roll])
        before = village.snapshot()
        village.keep(keeper, garbage)
        return village, before, village.snapshot()

    def test_emulated_swap_is_the_base_games_when_someone_else_lives(self) -> None:
        cases = [
            ({3: (1, 80, ADULT), 9: (1, 80, CHILD)}, 3, 0),
            ({3: (1, 80, ADULT), 9: (1, 80, CHILD)}, 9, 0),
            ({i: (1, 10 + i, ADULT) for i in range(0, 60, 3)}, 12, 5),
            ({i: (1, 10 + i, ADULT) for i in range(0, 60, 3)}, 57, 18),
            ({0: (1, 5, ADULT), 4: (1, 0, ADULT), 5: (0, 5, ADULT), 255: (1, 7, CHILD)}, 0, 0),
        ]
        for mode in MODES:
            stock = self.builds()[(mode, "stock")]
            for label in ("patched", "patched_with_all"):
                exe = self.builds()[(mode, label)]
                for living, keeper, roll in cases:
                    with self.subTest(mode=mode, build=label, keeper=keeper, roll=roll, n=len(living)):
                        s_village, before, s_after = self._keep(stock, living, keeper, roll)
                        p_village, p_before, p_after = self._keep(exe, living, keeper, roll)
                        self.assertEqual(before, p_before)
                        self.assertNotEqual(s_after, before)
                        # Byte for byte the same villagers afterwards.
                        self.assertEqual(p_after, s_after)
                        self.assertEqual(p_village.rand_bounds, s_village.rand_bounds)
                        self.assertEqual((p_village.texts_copied, s_village.texts_copied), (3, 3))
                        # and it is a swap with the roll's villager
                        others = [i for i in sorted(living) if i != keeper and living[i][0] and living[i][1] > 0]
                        partner = others[roll]
                        for field in FIELDS + (TEXT,):
                            k, p = _Village.rec(keeper) - POOL + field, _Village.rec(partner) - POOL + field
                            size = TEXT_LEN if field == TEXT else 4
                            self.assertEqual(p_after[k:k + size], before[p:p + size])
                            self.assertEqual(p_after[p:p + size], before[k:k + size])

    def test_emulated_keep_with_nobody_else_is_skipped(self) -> None:
        lonely = {3: (1, 80, ADULT), 9: (1, 0, ADULT), 10: (0, 80, ADULT)}
        for (mode, label), exe in self.builds().items():
            for garbage in (0x7FFF0000, 7):
                with self.subTest(mode=mode, build=label, garbage=garbage):
                    if label == "stock":
                        # The base game reads the unset slot: a wild index
                        # faults (the reported crash), a small one swaps with
                        # whatever record it names.
                        if garbage == 0x7FFF0000:
                            with self.assertRaises(UcError):
                                self._keep(exe, lonely, 3, 0, garbage)
                        else:
                            _v, before, after = self._keep(exe, lonely, 3, 0, garbage)
                            self.assertNotEqual(after, before)
                        continue
                    village, before, after = self._keep(exe, lonely, 3, 0, garbage)
                    self.assertEqual(after, before)
                    self.assertEqual(village.rand_bounds, [0])
                    self.assertEqual(village.texts_copied, 0)


if __name__ == "__main__":
    unittest.main()
