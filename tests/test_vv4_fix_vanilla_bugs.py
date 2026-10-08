"""The Tree of Life: "Fix Vanilla Bugs" (vv4_fix_vanilla_bugs).

One row holds every base-game bug fix approved for The Tree of Life; each fix is its own
exact-byte patch (or group of patches) in the row with its own tests here.  A later fix is added
as more patches in the same row and another test class below.

1. A village of exactly 150 villagers cannot be loaded again.  The save writer 0x4660A0 packs
   every active, non-ghost villager into the 150 x 0x104-byte table at GameState+0xC868 and then
   writes a 0 end-of-list flag at entry[count].  With 150 villagers that flag lands on
   GameState+0x160C0, the first byte of the progress block (0x4D8BF8) that was saved just before
   (0x41F0DC); its size dword 0x250 becomes 0x200, the load-time check 0x4387A0 compares it with
   the computed size and fails, and the game opens on an empty main menu offering a new tribe.
   Seen live (v1.35.50 test build, Immediate Fixed, 2026-10-02): 149 saved and reloaded; 150 was
   written with the size 0x200 and the village did not load.  The base game's cap (115) never
   reaches 150; the patcher's Collection Progression and Immediate Fixed modes do.

   The fix keeps all 150 villagers:
   * the writer writes the end flag only when fewer than 150 were saved;
   * the loader 0x466110 stops after 150 entries (the base game reads until a 0 flag, so an
     intact full table would be read past its end);
   * the block check accepts a stored size that equals the computed one with its low byte
     zeroed only when the table's last entry (#150, immediately before the block) is in use --
     the exact signature of a save the unfixed game damaged -- so those villages load again.
   New Believers' own writer (0x46F9B0, `cmp ebx, 0x96; jge`) and reader (0x46FA20, bound
   0xA410) already do the first two; this matches them.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from vv_fun_patcher import (  # noqa: E402
    EXPERIMENTAL_FUN_PATCH_IDS,
    load_builds,
    load_fun_patches,
    load_public_fun_patches,
    render_patched_bytes,
)
from save_table_emulator import VV4, SaveTableCases  # noqa: E402

FEATURE_ID = "vv4_fix_vanilla_bugs"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")

WRITER_OFFSET = 0x660F1
WRITER_STOCK = bytes.fromhex("E87A9DFBFF69DB040100005F5EC6841868C80000005DB0015BC20400CCCCCC")
WRITER_PATCHED = bytes.fromhex("81FB96000000730DE8729DFBFFC6843868C80000005F5E5DB0015BC20400CC")
LOADER_OFFSET = 0x6613D
LOADER_STOCK = bytes.fromhex(
    "743633F6E82A9DFBFF8D843068C80000508BCFE88B7AFFFF83C3018BF381C73C2E000069F604010000E8059DFBFF"
    "80BC3068C800000075CC5F5EB0015BC20400CCCCCC"
)
LOADER_PATCHED = bytes.fromhex(
    "743933F6E82A9DFBFF8D843068C80000508BCFE88B7AFFFF81C60401000081FE58980000731581C73C2E0000E802"
    "9DFBFF80BC3068C800000075C95F5EB0015BC20400"
)
CHECK_OFFSET = 0x387A0
CHECK_STOCK = bytes.fromhex(
    "538B5C2408568B33578BF9E8C0FFFFFF3D001000007F4B8BCFE8B2FFFFFF3BF075408D7304B934000000F3A5BFD4"
    "000000BE888B4D008B0E33C085C9740F8B018B400C8D141F52FFD085C07C1583C60403F881FEF08B4D007CDC5F5E"
    "B0015BC204005F5E32C05BC20400CCCCCCCCCCCC"
)
CHECK_PATCHED = bytes.fromhex(
    "538B5C2408568B335789CFE8C0FFFFFF3D001000007F4F39C6741189C130C939CE754380BBFCFEFFFF01753A8D73"
    "046A3459F3A5BFD4000000BE888B4D008B0E31C085C9740F8B018B400C8D141F52FFD085C07C1183C60401C781FE"
    "F08B4D007CDCB001EB0230C05F5E5BC20400CCCC"
)
FIXES = (
    (WRITER_OFFSET, WRITER_STOCK, WRITER_PATCHED),
    (LOADER_OFFSET, LOADER_STOCK, LOADER_PATCHED),
    (CHECK_OFFSET, CHECK_STOCK, CHECK_PATCHED),
    # Every default name can be chosen (tests/test_every_default_name_can_be_chosen.py).
    (0x65DB5, bytes.fromhex("68B7000000"), bytes.fromhex("68B9000000")),
    (0x65DC1, bytes.fromhex("83C001"), bytes.fromhex("83C000")),
)
PERCENT_FIXES = (  # '%' in a name never a format; text boxes refuse it (#566)
    (0x000402B9, bytes.fromhex("8D8E9C1B0000518D54242C52E81114030083C408"), bytes.fromhex("8D8E9C1B000051B872A84800EBE2909090909090")),
    (0x0000D813, bytes.fromhex("8B71308814308B5130C644020100"), bytes.fromhex("83FA2574108B71306689143089F2")),
)
FIXES = FIXES + PERCENT_FIXES


def _vv4():
    return next(build for build in load_builds() if build.id == "vv4")


def _render(mode: str, ids) -> bytes:
    rendered, _ = render_patched_bytes(STOCK, _vv4(), mode, list(ids))
    return bytes(rendered)


def _other_public_vv4_ids() -> list[str]:
    # The ordinary build: 256 Villagers (Experimental) replaces the save
    # writer and loader these rows fix (its own tests cover the two together,
    # tests/test_vv4_population_256.py FixVanillaBugsTests).
    return [p.id for p in load_public_fun_patches()
            if p.game_id == "vv4" and p.id != FEATURE_ID and p.id not in EXPERIMENTAL_FUN_PATCH_IDS]


def _changed_bytes(before: bytes, after: bytes) -> list[int]:
    field = pefile.PE(data=after, fast_load=True).OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    return [
        i for i in range(min(len(before), len(after)))
        if before[i] != after[i] and not field <= i < field + 4
    ]


def _listing(code: bytes, va: int) -> list[tuple[int, str, str]]:
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    out = [(i.address, i.mnemonic, i.op_str) for i in md.disasm(code, va)]
    assert sum(i.size for i in md.disasm(code, va)) == len(code)
    return out


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.feature = next(p for p in load_fun_patches() if p.id == FEATURE_ID)

    def test_manifest_row(self) -> None:
        raw = self.feature.raw
        self.assertEqual(raw["game_id"], "vv4")
        self.assertEqual(raw["name"], "Fix Vanilla Bugs")
        self.assertIn(FEATURE_ID, {p.id for p in load_public_fun_patches()})
        self.assertNotIn("dependencies", raw)
        self.assertIn("**Needs no other patch.**", raw["description"])
        self.assertIn("150 villagers", raw["description"])
        pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])) for p in raw["patches"]]
        self.assertEqual(pinned, list(FIXES))

    def test_default_on(self) -> None:
        from vv_fun_patcher_gui import DEFAULT_OFF_FUN_PATCH_IDS, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS
        self.assertNotIn(FEATURE_ID, DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(FEATURE_ID, OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)

    def test_stock_bytes_and_offsets(self) -> None:
        pe = pefile.PE(str(STOCK), fast_load=True)
        for va, (offset, before, _after) in zip((0x4660F1, 0x46613D, 0x4387A0), FIXES):
            self.assertEqual(pe.get_offset_from_rva(va - 0x400000), offset)
            self.assertEqual(self.stock[offset:offset + len(before)], before)
            self.assertEqual(len(before), len(_after))

    def test_nothing_else_branches_into_a_rewritten_region(self) -> None:
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        regions = [(0x400000 + off, 0x400000 + off + len(before)) for off, before, _ in FIXES]
        incoming = []
        for ins in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress):
            if not (ins.mnemonic.startswith("j") or ins.mnemonic == "call"):
                continue
            try:
                target = int(ins.op_str, 16)
            except ValueError:
                continue
            for start, end in regions:
                # Entering at a region's first byte is how the stock code reaches it; the
                # loader's region also keeps its loop head 0x466141 where it was.
                if start < target < end and not start <= ins.address < end and target != 0x466141:
                    incoming.append((hex(ins.address), hex(target)))
        self.assertEqual(incoming, [])

    def test_render_alone_in_every_mode(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, [])
                rendered = _render(mode, [FEATURE_ID])
                allowed = set()
                for offset, before, after in FIXES:
                    self.assertEqual(without[offset:offset + len(before)], before)
                    self.assertEqual(rendered[offset:offset + len(after)], after)
                    allowed.update(range(offset, offset + len(before)))
                diff = _changed_bytes(without, rendered)
                self.assertTrue(diff)
                self.assertTrue(set(diff) <= allowed, [hex(i) for i in sorted(set(diff) - allowed)[:8]])
                self.assertEqual(len(rendered), len(without))

    def test_render_with_every_other_vv4_patch_in_every_mode(self) -> None:
        others = _other_public_vv4_ids()
        self.assertGreater(len(others), 10)
        allowed = set()
        for offset, before, _ in FIXES:
            allowed.update(range(offset, offset + len(before)))
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


class _Builds:
    @classmethod
    def builds(cls) -> dict[tuple[str, str], bytes]:
        if not hasattr(cls, "_builds"):
            others = _other_public_vv4_ids()
            builds = {}
            for mode in MODES:
                builds[(mode, "stock")] = _render(mode, [])
                builds[(mode, "patched")] = _render(mode, [FEATURE_ID])
                builds[(mode, "patched_with_all")] = _render(mode, others + [FEATURE_ID])
            cls._builds = builds
        return cls._builds


class Save150DecodeTests(unittest.TestCase):
    def test_writer_decoded(self) -> None:
        self.assertEqual(
            _listing(WRITER_PATCHED, 0x4660F1),
            [
                (0x4660F1, "cmp", "ebx, 0x96"),
                (0x4660F7, "jae", "0x466106"),
                (0x4660F9, "call", "0x41fe70"),
                (0x4660FE, "mov", "byte ptr [eax + edi + 0xc868], 0"),
                (0x466106, "pop", "edi"),
                (0x466107, "pop", "esi"),
                (0x466108, "pop", "ebp"),
                (0x466109, "mov", "al, 1"),
                (0x46610B, "pop", "ebx"),
                (0x46610C, "ret", "4"),
                (0x46610F, "int3", ""),
            ],
        )

    def test_writer_edi_is_the_entry_offset(self) -> None:
        # The end flag is addressed with EDI, which the stock loop advances by 0x104 per saved
        # villager (0x4660E0) exactly as it advances EBX by one; the stock code used EBX*0x104.
        stock = _listing(STOCK.read_bytes()[0x660A0:0x660F1], 0x4660A0)
        self.assertIn((0x4660A6, "xor", "edi, edi"), stock)
        self.assertIn((0x4660DD, "add", "ebx, 1"), stock)
        self.assertIn((0x4660E0, "add", "edi, 0x104"), stock)

    def test_loader_decoded(self) -> None:
        self.assertEqual(
            _listing(LOADER_PATCHED, 0x46613D),
            [
                (0x46613D, "je", "0x466178"),
                (0x46613F, "xor", "esi, esi"),
                (0x466141, "call", "0x41fe70"),
                (0x466146, "lea", "eax, [eax + esi + 0xc868]"),
                (0x46614D, "push", "eax"),
                (0x46614E, "mov", "ecx, edi"),
                (0x466150, "call", "0x45dbe0"),
                (0x466155, "add", "esi, 0x104"),
                (0x46615B, "cmp", "esi, 0x9858"),
                (0x466161, "jae", "0x466178"),
                (0x466163, "add", "edi, 0x2e3c"),
                (0x466169, "call", "0x41fe70"),
                (0x46616E, "cmp", "byte ptr [eax + esi + 0xc868], 0"),
                (0x466176, "jne", "0x466141"),
                (0x466178, "pop", "edi"),
                (0x466179, "pop", "esi"),
                (0x46617A, "mov", "al, 1"),
                (0x46617C, "pop", "ebx"),
                (0x46617D, "ret", "4"),
            ],
        )
        self.assertEqual(0x9858, 150 * 0x104)

    def test_check_decoded(self) -> None:
        listing = _listing(CHECK_PATCHED, 0x4387A0)
        self.assertEqual(
            listing[:17],
            [
                (0x4387A0, "push", "ebx"),
                (0x4387A1, "mov", "ebx, dword ptr [esp + 8]"),
                (0x4387A5, "push", "esi"),
                (0x4387A6, "mov", "esi, dword ptr [ebx]"),
                (0x4387A8, "push", "edi"),
                (0x4387A9, "mov", "edi, ecx"),
                (0x4387AB, "call", "0x438770"),
                (0x4387B0, "cmp", "eax, 0x1000"),
                (0x4387B5, "jg", "0x438806"),
                (0x4387B7, "cmp", "esi, eax"),
                (0x4387B9, "je", "0x4387cc"),
                (0x4387BB, "mov", "ecx, eax"),
                (0x4387BD, "xor", "cl, cl"),
                (0x4387BF, "cmp", "esi, ecx"),
                (0x4387C1, "jne", "0x438806"),
                (0x4387C3, "cmp", "byte ptr [ebx - 0x104], 1"),
                (0x4387CA, "jne", "0x438806"),
            ],
        )
        # the rest is the stock copy-and-load loop, re-encoded (shared epilogue, push/pop 0x34)
        self.assertIn((0x4387D4, "mov", "edi, 0xd4"), listing)
        self.assertIn((0x4387D9, "mov", "esi, 0x4d8b88"), listing)
        self.assertIn((0x4387FA, "cmp", "esi, 0x4d8bf0"), listing)
        self.assertEqual(listing[-3:], [(0x43880B, "ret", "4"), (0x43880E, "int3", ""), (0x43880F, "int3", "")])

    def test_only_caller_passes_the_block_right_after_the_table(self) -> None:
        # 0x4387A0 is called once, with GameState+0x160C0, so [ebx-0x104] is the table's entry #150.
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        calls = [i.address for i in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress)
                 if i.mnemonic == "call" and i.op_str == "0x4387a0"]
        self.assertEqual(calls, [0x41FCD0])
        site = _listing(STOCK.read_bytes()[0x1FCC4:0x1FCD5], 0x41FCC4)
        self.assertEqual(site[0], (0x41FCC4, "lea", "edx, [ebx + 0x160c0]"))
        self.assertEqual(0xC868 + 150 * 0x104, 0x160C0)


class Save150EmulationTests(SaveTableCases, unittest.TestCase, _Builds):
    LAYOUT = VV4


if __name__ == "__main__":
    unittest.main()
