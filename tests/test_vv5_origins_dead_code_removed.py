"""VV5 Origins carries no unreachable code, and every upgrade stays reachable.

The shipped VV5 Origins record is the Task9 one. Its Tech and Detail menus live
in the appended .vv5t9 page; the base .shr payload only keeps what live code
reaches: the two Upgrades-button constructors, the Tech/Detail handlers and
their absolute jumps into the page, the Barrel selector, the two doubler
wrappers and the "Upgrades" label. The legacy .shr menus, their dialog,
message and record helpers, the Cure/village-wide dispatch helper at 0x494EA0,
its 0x494B32 stub, the 0x494B37 preflight, the 640-byte village-wide extension
at 0x494C20 and the Task9 page's resolve_manager were unreachable in every
public build and were removed.

These tests render all three public modes, with Origins alone and with the
full public catalog, and run a reachability pass over the result: roots are
every rel32 branch/call and every 32-bit value anywhere OUTSIDE the
Origins-owned regions that lands inside them, and recursive disassembly
follows code from there. Every non-zero byte of the .shr payload and of the
.text-tail range must be reached, and every Task9 action routine the Tech and
Details menus offer must be reached too.
"""
from __future__ import annotations

import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

import capstone
from capstone import x86 as X
import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
MODES = ("stock", "collection_progression", "immediate_fixed")
BASE_ID = "vv5_enable_origins_exclusive_features"
ROUTE_ID = "vv5_origins_village_wide_upgrades"

SHR = (0x7B2000, 0x7B3000)
SHR_CODE_END = 0x7B2D00                  # the .shr string area starts here
TEXT_TAIL = (0x494B32, 0x494FD0)         # where the removed caves lived
PAGE = (0x7C9000, 0x7D1000)
PAGE_CODE_END = 0x7D0000
REGIONS = (SHR, TEXT_TAIL, PAGE)

# Every action the two Task9 menus dispatch to, plus the entries themselves.
TASK9_ACTIONS = (
    "tech_entry", "detail_entry", "tech_menu", "detail_menu", "age",
    "time_warp", "mastery", "running", "heal", "island", "barrel",
    "appearance", "complete_collections", "reset_collections", "running_all",
    "mastery_all", "age18_all", "division_parenting", "division_no_parenting",
    "appearance_all", "barrel_close_arm",
)

_renders: dict[tuple[str, str], bytes] = {}
_analyses: dict[tuple[str, str], tuple] = {}


def task9_builder():
    spec = importlib.util.spec_from_file_location(
        "vv5_task9_builder_reach", ROOT / "scripts" / "build_vv5_task9_native_actions.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render(scope: str, mode: str) -> bytes:
    key = (scope, mode)
    if key not in _renders:
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        if scope == "alone":
            ids = [BASE_ID]
        else:
            public = [p.id for p in vfp.load_public_fun_patches() if p.game_id == "vv5"]
            ids = vfp.resolve_fun_patch_ids(public, game_id="vv5")
        image, _ = vfp.render_patched_bytes(STOCK, build, mode, ids)
        _renders[key] = bytes(image)
    return _renders[key]


def region_of(value: int):
    for lo, hi in REGIONS:
        if lo <= value < hi:
            return (lo, hi)
    return None


def code_limit(value: int) -> int:
    return {SHR: SHR_CODE_END, PAGE: PAGE_CODE_END, TEXT_TAIL: TEXT_TAIL[1]}[region_of(value)]


def analyse(data: bytes):
    """Return (image, reached byte VAs) for one rendered executable."""
    pe = pefile.PE(data=data, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    size = pe.OPTIONAL_HEADER.SizeOfImage
    image = bytearray(size)
    image[: pe.OPTIONAL_HEADER.SizeOfHeaders] = data[: pe.OPTIONAL_HEADER.SizeOfHeaders]
    executable = []
    for section in pe.sections:
        raw = data[section.PointerToRawData: section.PointerToRawData + section.SizeOfRawData]
        image[section.VirtualAddress: section.VirtualAddress + len(raw)] = raw[: size - section.VirtualAddress]
        if section.Characteristics & 0x20000000:
            executable.append((section.VirtualAddress, section.VirtualAddress + max(section.Misc_VirtualSize, len(raw))))
    inside = bytearray(size)
    for lo, hi in REGIONS:
        inside[lo - base: hi - base] = b"\1" * (hi - lo)

    roots: set[int] = set()
    view = memoryview(image)
    for shift in range(4):
        for index, (value,) in enumerate(struct.iter_unpack("<I", view[shift: shift + (size - shift) // 4 * 4])):
            rva = shift + index * 4
            if not inside[rva] and region_of(value):
                roots.add(value)
    for lo, hi in executable:
        for rva in range(lo, min(hi, size - 6)):
            if inside[rva]:
                continue
            op = image[rva]
            if op in (0xE8, 0xE9):
                target = (base + rva + 5 + struct.unpack_from("<i", image, rva + 1)[0]) & 0xFFFFFFFF
            elif op == 0x0F and 0x80 <= image[rva + 1] <= 0x8F:
                target = (base + rva + 6 + struct.unpack_from("<i", image, rva + 2)[0]) & 0xFFFFFFFF
            else:
                continue
            if region_of(target):
                roots.add(target)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    live: set[int] = set()
    data_refs: set[int] = set()
    work = []
    for value in roots:
        if value < code_limit(value):
            work.append(value)
        else:
            data_refs.add(value)
    seen: set[int] = set()
    while work:
        va = work.pop()
        while va not in seen and region_of(va):
            seen.add(va)
            insn = next(md.disasm(bytes(image[va - base: va - base + 16]), va), None)
            if insn is None:
                break
            live.update(range(va, va + insn.size))
            for op in insn.operands:
                value = None
                if op.type == X.X86_OP_IMM:
                    value = op.imm & 0xFFFFFFFF
                elif op.type == X.X86_OP_MEM and op.mem.base == 0:
                    value = op.mem.disp & 0xFFFFFFFF
                if value is None or not region_of(value):
                    continue
                if op.type == X.X86_OP_IMM and value < code_limit(value):
                    work.append(value)
                else:
                    data_refs.add(value)
            if insn.mnemonic in ("ret", "jmp", "int3", "ud2", "hlt"):
                break
            va += insn.size
    for ref in data_refs:
        cursor = ref
        while region_of(cursor) and image[cursor - base] and cursor - ref < 256:
            live.add(cursor)
            cursor += 1
        live.update(range(ref, ref + 4))
    return image, base, live


def analysis(scope: str, mode: str):
    key = (scope, mode)
    if key not in _analyses:
        _analyses[key] = analyse(render(scope, mode))
    return _analyses[key]


def unreached(image, base, live, lo, hi) -> list[str]:
    runs: list[list[int]] = []
    for va in range(lo, hi):
        if image[va - base] and va not in live:
            if runs and va - runs[-1][1] <= 16:
                runs[-1][1] = va + 1
            else:
                runs.append([va, va + 1])
    return [f"{a:#x}-{b:#x}" for a, b in runs]


class VV5OriginsCarriesNoUnreachableCode(unittest.TestCase):
    def test_every_origins_shr_and_text_tail_byte_is_reached(self) -> None:
        for scope in ("alone", "full"):
            for mode in MODES:
                with self.subTest(scope=scope, mode=mode):
                    image, base, live = analysis(scope, mode)
                    self.assertEqual(unreached(image, base, live, *SHR), [], ".shr")
                    self.assertEqual(unreached(image, base, live, *TEXT_TAIL), [], ".text tail")

    def test_removed_regions_are_back_to_stock_zero(self) -> None:
        stock = STOCK.read_bytes()
        for scope in ("alone", "full"):
            for mode in MODES:
                image = render(scope, mode)
                for lo, hi, what in (
                    (0x94B32, 0x94BB0, "Cure stub and village-wide preflight"),
                    (0x94C20, 0x94EA0, "village-wide extension"),
                    (0x94EA0, 0x94FD0, "Cure/village-wide dispatch helper"),
                    (0xDB1C0, 0xDB2C0, "legacy dialog, message and record helpers"),
                    (0xDB2C7, 0xDB600, "legacy Tech menu body"),
                    (0xDB607, 0xDBA00, "legacy Detail menu body"),
                    (0xDBD09, 0xDC000, "legacy strings and price tables"),
                ):
                    with self.subTest(scope=scope, mode=mode, region=what):
                        self.assertEqual(image[lo:hi], stock[lo:hi])

    def test_every_task9_upgrade_is_reached_from_the_live_hooks(self) -> None:
        builder = task9_builder()
        self.assertNotIn("resolve_manager", builder.OFF)
        for scope in ("alone", "full"):
            for mode in MODES:
                with self.subTest(scope=scope, mode=mode):
                    _, _, live = analysis(scope, mode)
                    missing = [
                        name for name in TASK9_ACTIONS
                        if PAGE[0] + builder.OFF[name] not in live
                    ]
                    self.assertEqual(missing, [])

    def test_the_old_cure_all_write_into_villager_record_0_is_gone(self) -> None:
        # The removed helper's Cure All loop ran `inc dword ptr [0x55490C]`
        # per cured villager: not People Cured (0x51D368) but villager record
        # 0 (0x554190) +0x77C, entry 21 field +0x44 of its action queue.
        bad = bytes.fromhex("FF050C495500")
        for relative in ("data/vv5_origins_feature.json", "data/vv5_task9_native_actions.json"):
            with self.subTest(manifest=relative):
                text = (ROOT / relative).read_text(encoding="utf-8").upper()
                self.assertNotIn(bad.hex().upper(), text)
        for scope in ("alone", "full"):
            for mode in MODES:
                with self.subTest(scope=scope, mode=mode):
                    self.assertNotIn(bad, render(scope, mode))

    def test_the_public_route_adds_nothing_and_removes_nothing(self) -> None:
        # The village-wide row is the player's route to the Origins upgrades;
        # with its dead extension gone it must render exactly as its base.
        route = json.loads((ROOT / "data" / f"{ROUTE_ID}.json").read_text(encoding="utf-8"))
        self.assertEqual(route["patches"], [])
        self.assertEqual(route["dependencies"], [BASE_ID])
        self.assertNotIn("extension_abi", route)
        public = {p.id for p in vfp.load_public_fun_patches() if p.game_id == "vv5"}
        self.assertIn(ROUTE_ID, public)
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        for mode in MODES:
            with self.subTest(mode=mode):
                with_route, _ = vfp.render_patched_bytes(
                    STOCK, build, mode, vfp.resolve_fun_patch_ids([ROUTE_ID], game_id="vv5")
                )
                self.assertEqual(bytes(with_route), render("alone", mode))


if __name__ == "__main__":
    unittest.main()
