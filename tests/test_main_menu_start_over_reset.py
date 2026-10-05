"""The main menu's Start Over runs the Save Reset, in all five games.

Live, VV2 v1.35.41 with every public patch: a village saved, back to the main
menu, Start Over -> "Are you sure you want to restart the current game?" ->
OK. A marker named exactly as VVFP Save Reset.dll deletes it survived, and so
did the Births and Conceptions log, through two Start Overs: the reset hook
sits on the SAVE-SLOT menu's tribe delete, and the main menu's Start Over
never calls deleteSave.

The main-menu button handler, on OK, runs `mov ecx,[esi+0xC]; call Restart`
-- Restart keeps the tribe name, re-creates the village and saves it into the
same slot. The patcher now rewrites that one call to a stub that calls
ResetDeletedTribe(game, [village + current-slot field]) and then tail-jumps to
Restart. These tests hold:

  * the stock facts the hook stands on, in every game: the site is the call
    after the eSayConfirmRestart dialog, Restart has no other caller, and the
    slot field is the one the save-slot menu compares against a deleted slot;
  * the one-carrier rule: Origins, else parentage, else statistics carries
    it, exactly once, and a second attach changes nothing;
  * every {Origins, parentage, statistics} subset in all three modes renders
    the hook exactly once, to the template block, in mapped executable code,
    with the tribe-delete hook still installed and the executable-name crash
    guard still applied in VV1-VV3;
  * RUN in an emulator from the rewritten call: the companion is called once
    with (game, current slot), and Restart is entered with every register and
    the stack exactly as the stock call leaves them -- also when the DLL or the
    export is missing, with no call at all;
  * removing a feature leaves the image rendering the rest would produce,
    including Origins handing the stub to the carrier placement;
  * render refuses a stub that the final image would not map as code.
"""
from __future__ import annotations

import pathlib
import re
import struct
import sys
import unittest

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
EXE = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
HAVE_STOCK = all((STOCK / name).is_file() for name in EXE.values())
MODES = ("stock", "collection_progression", "immediate_fixed")
# Measured in the five stock executables (see the module docstring and the
# comment above MAIN_MENU_START_OVER): the call after the confirmation, the
# restart routine it calls, and the village's current-slot field.
SITE = {"vv1": 0x26F68, "vv2": 0x32AF4, "vv3": 0x6B7E4, "vv4": 0x44647, "vv5": 0x47797}
RESTART = {"vv1": 0x41C7C0, "vv2": 0x4255E0, "vv3": 0x4283C0, "vv4": 0x41F3E0, "vv5": 0x424930}
SLOT = {"vv1": 0xABE4, "vv2": 0x30378, "vv3": 0x12F24, "vv4": 0x17114, "vv5": 0x17D80}
# The save-slot menu's own tribe-delete call (the older hook).
DELETE_HOOK = {"vv1": 0x13E07, "vv2": 0x14E77, "vv3": 0x1B5D3, "vv4": 0x18CD5, "vv5": 0x193F5}
CONFIRM_RESTART = b"Are you sure you want to restart the current game?\x00"
DLL = "VVFP Save Reset.dll"
SUBSETS = (
    "",
    "origins",
    "parentage",
    "statistics",
    "origins+parentage",
    "origins+statistics",
    "parentage+statistics",
    "origins+parentage+statistics",
)


def _ids(game: str, subset: str) -> list[str]:
    public = {
        "origins": f"{game}_origins_village_wide_upgrades",
        "parentage": f"{game}_write_parentage_log",
        "statistics": f"{game}_write_village_statistics",
    }
    return [public[item] for item in subset.split("+") if item]


def _build(game: str):
    return next(b for b in vp.load_builds() if b.id == game)


def _selected(game: str, subset: str) -> list:
    return vp._attach_start_over_reset(
        game, vp._selected_fun_patches(_build(game), _ids(game, subset))
    )


def _expected_carrier(game: str, subset: str) -> str | None:
    parts = set(filter(None, subset.split("+")))
    # VV2's parentage log depends on Origins, which is resolved in.
    if "origins" in parts or (game == "vv2" and "parentage" in parts):
        return f"{game}_enable_origins_exclusive_features"
    if "parentage" in parts:
        return f"{game}_write_parentage_log"
    if "statistics" in parts:
        return f"{game}_write_village_statistics"
    return None


def _placement(game: str, subset: str) -> str | None:
    carrier = _expected_carrier(game, subset)
    if carrier is None:
        return None
    return "origins" if carrier.endswith("_enable_origins_exclusive_features") else "carrier"


def _iats(game: str) -> list[int]:
    patches, _companion = vp._start_over_reset_from_origins(game)
    block = next(bytes.fromhex(p["after"]) for p in patches if len(p["after"]) == 0x62 * 2)
    return [struct.unpack_from("<I", block, 0x28 + at)[0] for at in (8, 0x17, 0x27)]


def _exec_offset(data: bytes, va: int, length: int) -> int | None:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    for index in range(count):
        base = pe + 24 + opt + 40 * index
        vsz, sva, rsz, ro = struct.unpack_from("<IIII", data, base + 8)
        chars = struct.unpack_from("<I", data, base + 36)[0]
        start = 0x400000 + sva
        mapped = min((vsz + 0xFFF) & ~0xFFF, rsz)
        if start <= va and va + length <= start + mapped and chars & 0x20000000:
            return ro + va - start
    return None


def _rel32_callers(data: bytes, target: int) -> list[int]:
    """VAs of every E8/E9 rel32 in executable sections that reaches target."""
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    found = []
    for index in range(count):
        base = pe + 24 + opt + 40 * index
        vsz, sva, rsz, ro = struct.unpack_from("<IIII", data, base + 8)
        if not struct.unpack_from("<I", data, base + 36)[0] & 0x20000000:
            continue
        end = ro + min((vsz + 0xFFF) & ~0xFFF, rsz) - 5
        for opcode in (b"\xe8", b"\xe9"):
            at = data.find(opcode, ro, end)
            while at != -1:
                va = 0x400000 + sva + at - ro
                if (va + 5 + struct.unpack_from("<i", data, at + 1)[0]) & 0xFFFFFFFF == target:
                    found.append(va)
                at = data.find(opcode, at + 1, end)
    return sorted(found)


def _call_target(data: bytes, offset: int) -> int:
    assert data[offset] == 0xE8
    return (0x400000 + offset + 5 + struct.unpack_from("<i", data, offset + 1)[0]) & 0xFFFFFFFF


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class StockFactsTests(unittest.TestCase):
    """What the hook stands on, re-measured from each stock executable."""

    def test_the_site_is_the_confirmed_restart_call(self) -> None:
        for game, name in EXE.items():
            with self.subTest(game=game):
                data = (STOCK / name).read_bytes()
                site = SITE[game]
                self.assertEqual(data[site - 3 : site], b"\x8b\x4e\x0c")  # mov ecx,[esi+0xC]
                self.assertEqual(_call_target(data, site), RESTART[game])
                # The confirmation text's string id, from the game's own table
                # (id dword, then its pointers), is what the dialog pushes just
                # before the site.
                text_va = 0x400000 + data.find(CONFIRM_RESTART)
                refs = [m.start() for m in re.finditer(re.escape(struct.pack("<I", text_va)), data)]
                self.assertEqual(len(refs), 1)
                at = refs[0] - 4
                while struct.unpack_from("<I", data, at)[0] >= 0x1000:
                    at -= 4
                string_id = struct.unpack_from("<I", data, at)[0]
                window = data[site - 0x40 : site]
                push = (
                    bytes([0x6A, string_id]) if string_id < 0x80
                    else b"\x68" + struct.pack("<I", string_id)
                )
                self.assertIn(push, window, "the eSayConfirmRestart dialog is not right before the site")

    def test_restart_has_no_other_caller(self) -> None:
        for game, name in EXE.items():
            with self.subTest(game=game):
                data = (STOCK / name).read_bytes()
                pe = pefile.PE(data=data, fast_load=True)
                text = pe.sections[0]
                raw = data[text.PointerToRawData : text.PointerToRawData + text.SizeOfRawData]
                va0 = 0x400000 + text.VirtualAddress
                callers = []
                for i in range(len(raw) - 5):
                    if raw[i] in (0xE8, 0xE9):
                        if (va0 + i + 5 + struct.unpack_from("<i", raw, i + 1)[0]) & 0xFFFFFFFF == RESTART[game]:
                            callers.append(va0 + i)
                self.assertEqual(callers, [0x400000 + SITE[game]])
                self.assertNotIn(struct.pack("<I", RESTART[game]), raw)  # no pointer to it

    def test_the_slot_field_is_the_one_the_save_slot_menu_compares(self) -> None:
        """After its delete, the save-slot menu tests `[village+slot] == edi`."""
        for game, name in EXE.items():
            with self.subTest(game=game):
                data = (STOCK / name).read_bytes()
                after = DELETE_HOOK[game] + 5
                self.assertEqual(data[after : after + 5], b"\x8b\x4e\x4c\x39\xb9")
                self.assertEqual(struct.unpack_from("<I", data, after + 5)[0], SLOT[game])

    def test_the_tables_match_the_patcher(self) -> None:
        for game in EXE:
            with self.subTest(game=game):
                spec = vp.MAIN_MENU_START_OVER[game]
                self.assertEqual(
                    (spec["site"], spec["restart"], spec["slot"]),
                    (SITE[game], RESTART[game], SLOT[game]),
                )


class CarrierSelectionTests(unittest.TestCase):
    def test_exactly_one_feature_writes_the_site_when_one_is_needed(self) -> None:
        for game in EXE:
            for subset in SUBSETS:
                with self.subTest(game=game, subset=subset or "none"):
                    features = _selected(game, subset)
                    writers = [
                        f.id for f in features if vp._feature_writes_offset(f, SITE[game])
                    ]
                    expected = _expected_carrier(game, subset)
                    self.assertEqual(writers, [expected] if expected else [])
                    # The tribe-delete hook is written whenever this one is.
                    delete_writers = [
                        f.id for f in features
                        if vp._feature_writes_offset(f, DELETE_HOOK[game])
                    ]
                    self.assertEqual(len(delete_writers), 1 if expected else 0)

    def test_the_carrier_ships_the_save_reset_dll(self) -> None:
        for game in EXE:
            for subset in SUBSETS:
                if not subset:
                    continue
                with self.subTest(game=game, subset=subset):
                    features = _selected(game, subset)
                    carrier = next(
                        f for f in features if vp._feature_writes_offset(f, SITE[game])
                    )
                    self.assertTrue(
                        any(
                            item.get("destination") == DLL
                            for item in carrier.raw.get("companion_files", [])
                        )
                    )

    def test_attaching_twice_changes_nothing(self) -> None:
        for game in EXE:
            for subset in ("origins", "statistics", "parentage+statistics"):
                with self.subTest(game=game, subset=subset):
                    once = _selected(game, subset)
                    twice = vp._attach_start_over_reset(game, once)
                    self.assertEqual([f.raw for f in once], [f.raw for f in twice])

    def test_the_catalog_records_are_not_modified(self) -> None:
        for game in EXE:
            with self.subTest(game=game):
                _selected(game, "origins+parentage+statistics")
                _selected(game, "statistics")
                for record in vp.load_fun_patches():
                    if record.raw.get("game_id") == game:
                        self.assertFalse(vp._feature_writes_offset(record, SITE[game]), record.id)
                        self.assertNotIn("_main_menu_start_over_carrier", record.raw)

    def test_the_block_is_the_template(self) -> None:
        for game in EXE:
            for placement in ("origins", "carrier"):
                with self.subTest(game=game, placement=placement):
                    cave = vp.MAIN_MENU_START_OVER_CAVE[game][placement]
                    block_patch, hook = vp._main_menu_start_over_patches(game, placement)
                    block = bytes.fromhex(block_patch["after"])
                    self.assertEqual(len(block), 0x6B)
                    self.assertEqual(block[:0x14], b"VVFP Save Reset.dll\x00")
                    self.assertEqual(block[0x14:0x26], b"ResetDeletedTribe\x00")
                    code = block[0x28:]
                    # Loader identical to the proven tribe-delete block's.
                    reset = vp._start_over_reset_block(
                        cave["va"], *_iats(game), int(game[2]), 0
                    )
                    self.assertEqual(code[:0x1D], reset[0x28 : 0x28 + 0x1D])
                    # ecx from the pushad copy; push [ecx+slot]; push game; call eax.
                    self.assertEqual(code[0x2F:0x33], b"\x8b\x4c\x24\x18")
                    self.assertEqual(code[0x33:0x35], b"\xff\xb1")
                    self.assertEqual(struct.unpack_from("<I", code, 0x35)[0], SLOT[game])
                    self.assertEqual(code[0x39:0x3D], bytes([0x6A, int(game[2]), 0xFF, 0xD0]))
                    self.assertEqual(code[0x3D:0x3F], b"\x61\xe9")
                    end = cave["va"] + 0x28 + 0x43
                    self.assertEqual(end + struct.unpack_from("<i", code, 0x3F)[0], RESTART[game])
                    # Both failure branches land on popad.
                    self.assertEqual(code[0x1D:0x1F], b"\x74\x1e")
                    self.assertEqual(code[0x2D:0x2F], b"\x74\x0e")
                    self.assertEqual(0x1F + 0x1E, 0x3D)
                    self.assertEqual(0x2F + 0x0E, 0x3D)
                    after = bytes.fromhex(hook["after"])
                    self.assertEqual(
                        0x400000 + SITE[game] + 5 + struct.unpack_from("<i", after, 1)[0],
                        cave["va"] + 0x28,
                    )


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class RenderedMatrixTests(unittest.TestCase):
    """Every {Origins, parentage, statistics} subset x 5 games x 3 modes."""

    rendered: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.rendered = {}
        for game in EXE:
            build = _build(game)
            for mode in MODES:
                for subset in SUBSETS:
                    data, applied = vp.render_patched_bytes(
                        STOCK / EXE[game], build, mode, _ids(game, subset)
                    )
                    if game not in vp.NAME_CRASH_IMMUNITY_EXEMPT_BUILD_IDS:
                        vp._require_name_crash_immunity(data, build.input_name, applied)
                    cls.rendered[(game, mode, subset)] = (bytes(data), applied)

    def test_the_hook_is_installed_exactly_once_to_a_working_block(self) -> None:
        for (game, mode, subset), (data, applied) in sorted(self.rendered.items()):
            with self.subTest(game=game, mode=mode, subset=subset or "none"):
                stock = (STOCK / EXE[game]).read_bytes()
                site = SITE[game]
                site_rows = [r for r in applied if int(r["offset"], 16) == site]
                placement = _placement(game, subset)
                if placement is None:
                    self.assertEqual(data[site : site + 5], stock[site : site + 5])
                    self.assertEqual(site_rows, [])
                    for cave in vp.MAIN_MENU_START_OVER_CAVE[game].values():
                        self.assertNotIn(
                            b"ResetDeletedTribe", data[cave["file"] : cave["file"] + 0x6B]
                        )
                    continue
                self.assertEqual(len(site_rows), 1, "the hook must be written exactly once")
                self.assertEqual(
                    site_rows[0]["owner"], f"feature:{_expected_carrier(game, subset)}"
                )
                cave = vp.MAIN_MENU_START_OVER_CAVE[game][placement]
                self.assertEqual(_call_target(data, site), cave["va"] + 0x28)
                offset = _exec_offset(data, cave["va"], 0x6B)
                self.assertEqual(offset, cave["file"], "the block is not mapped executable code")
                block = data[offset : offset + 0x6B]
                self.assertEqual(
                    block,
                    vp._main_menu_start_over_block(
                        cave["va"], *_iats(game), int(game[2]), SLOT[game], RESTART[game]
                    ),
                )
                block_rows = [r for r in applied if int(r["offset"], 16) == cave["file"]]
                self.assertEqual(len(block_rows), 1)
                # The site in mapped code too, and the tribe-delete hook still live.
                self.assertIsNotNone(_exec_offset(data, 0x400000 + site, 5))
                self.assertNotEqual(
                    data[DELETE_HOOK[game] : DELETE_HOOK[game] + 5],
                    stock[DELETE_HOOK[game] : DELETE_HOOK[game] + 5],
                )
                # Nothing else in the image calls or jumps to the stub.
                self.assertEqual(_rel32_callers(data, cave["va"] + 0x28), [0x400000 + site])

    def test_the_crash_guard_is_still_applied_in_vv1_to_vv3(self) -> None:
        for (game, mode, subset), (_data, applied) in sorted(self.rendered.items()):
            if game in vp.NAME_CRASH_IMMUNITY_EXEMPT_BUILD_IDS:
                continue
            with self.subTest(game=game, mode=mode, subset=subset or "none"):
                self.assertTrue(
                    any(r.get("owner") == "automatic:name_crash_immunity" for r in applied)
                )


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class FullCatalogTests(unittest.TestCase):
    """Every public feature at once, and every feature that does not pull in
    Origins at once: the hook still lands exactly once and nothing overlaps."""

    def test_every_public_feature_and_every_non_origins_feature(self) -> None:
        # 256 Villagers (Experimental) builds a different executable; its
        # compositions are tested in tests/test_vv3_population_256.py.
        public = [p for p in vp.load_public_fun_patches()
                  if p.id not in vp.EXPERIMENTAL_FUN_PATCH_IDS]
        base = set(vp.INTERNAL_ORIGINS_BASE_FEATURE_ID_SET)
        for game in EXE:
            build = _build(game)
            ids = [p.id for p in public if p.game_id == game]
            no_origins = []
            for pid in ids:
                try:
                    closed = vp.resolve_fun_patch_ids([pid], game_id=game)
                except Exception:  # needs a prerequisite ticked explicitly
                    continue
                if not set(closed) & base and pid not in vp.PUBLIC_ORIGINS_VILLAGE_WIDE_PATCH_ID_SET:
                    no_origins.append(pid)
            for label, selection, placement in (
                ("full", vp.resolve_fun_patch_ids(ids, game_id=game), "origins"),
                ("no origins", no_origins, "carrier"),
            ):
                for mode in MODES:
                    with self.subTest(game=game, selection=label, mode=mode):
                        data, applied = vp.render_patched_bytes(
                            STOCK / EXE[game], build, mode, selection
                        )
                        if game not in vp.NAME_CRASH_IMMUNITY_EXEMPT_BUILD_IDS:
                            vp._require_name_crash_immunity(data, build.input_name, applied)
                        cave = vp.MAIN_MENU_START_OVER_CAVE[game][placement]
                        self.assertEqual(_call_target(data, SITE[game]), cave["va"] + 0x28)
                        self.assertEqual(
                            len([r for r in applied if int(r["offset"], 16) == SITE[game]]), 1
                        )
                        self.assertEqual(_exec_offset(data, cave["va"], 0x6B), cave["file"])


# ---------------------------------------------------------------- emulation
SCRATCH = 0x0F000000
FAKE_MODULE = SCRATCH + 0x100
FAKE_GMH = SCRATCH + 0x140
FAKE_LOAD = SCRATCH + 0x180
FAKE_PROC = SCRATCH + 0x1C0
FAKE_EXPORT = SCRATCH + 0x200
FAKE_OTHER = SCRATCH + 0x240
VILLAGE = 0x0C000000
STACK_TOP = 0x10800000
REGS = dict(eax=UC_X86_REG_EAX, ebx=UC_X86_REG_EBX, ecx=UC_X86_REG_ECX, edx=UC_X86_REG_EDX,
            esi=UC_X86_REG_ESI, edi=UC_X86_REG_EDI, ebp=UC_X86_REG_EBP, esp=UC_X86_REG_ESP)
SENTINELS = dict(eax=0x0A0A0A0A, ebx=0x11111111, ecx=VILLAGE, edx=0x33333333,
                 esi=0x44444444, edi=0x55555555, ebp=0x66666666)
# (GetModuleHandleA result, LoadLibraryA result, GetProcAddress result)
SCENARIOS = {
    "already loaded": (FAKE_MODULE, None, FAKE_EXPORT),
    "loaded on demand": (0, FAKE_MODULE, FAKE_EXPORT),
    "DLL missing": (0, 0, None),
    "export missing": (FAKE_MODULE, None, 0),
}


def _emulate(image: bytes, game: str, scenario: str, slot_value: int) -> dict:
    gmh, load, proc = SCENARIOS[scenario]
    pe = pefile.PE(data=image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image[: pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
    mu.mem_map(SCRATCH, 0x1000)
    mu.mem_map(VILLAGE, 0x40000)
    mu.mem_write(VILLAGE + SLOT[game], struct.pack("<I", slot_value))
    mu.mem_map(STACK_TOP - 0x10000, 0x10000)

    # Like the real APIs, every fake clobbers the volatile ecx and edx, so a
    # stub that trusted the live ecx after a call would read the wrong slot.
    clobber = b"\xb9\xef\xbe\xad\xde\xba\xce\xfa\xed\xfe"  # mov ecx/edx, junk

    def ret(value: int | None, pop: int) -> bytes:
        if value is None:
            return b"\xf4"
        return b"\xb8" + struct.pack("<I", value) + clobber + b"\xc2" + struct.pack("<H", pop)

    stubs = {
        b"GetModuleHandleA": (FAKE_GMH, ret(gmh, 4)),
        b"LoadLibraryA": (FAKE_LOAD, ret(load, 4)),
        b"GetProcAddress": (FAKE_PROC, ret(proc, 8)),
    }
    mu.mem_write(FAKE_OTHER, b"\xf4")
    mu.mem_write(FAKE_EXPORT, ret(7, 8))  # returns 7, stdcall two dwords
    found = set()
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        for imp in entry.imports:
            target = FAKE_OTHER
            if imp.name in stubs:
                target, body = stubs[imp.name]
                mu.mem_write(target, body)
                found.add(imp.name)
            mu.mem_write(imp.address, struct.pack("<I", target))
    assert found == set(stubs), found
    seen = {"calls": [], "names": [], "modules": []}

    def hook(uc, address, size, _):
        esp = uc.reg_read(UC_X86_REG_ESP)
        if address in (FAKE_GMH, FAKE_LOAD):
            ptr = struct.unpack("<I", uc.mem_read(esp + 4, 4))[0]
            seen["modules"].append(bytes(uc.mem_read(ptr, 32)).split(b"\0")[0])
            if address == FAKE_LOAD and load is None:
                raise AssertionError("LoadLibraryA called although the module was loaded")
        elif address == FAKE_PROC:
            ptr = struct.unpack("<I", uc.mem_read(esp + 8, 4))[0]
            seen["names"].append(bytes(uc.mem_read(ptr, 32)).split(b"\0")[0])
        elif address == FAKE_EXPORT:
            seen["calls"].append(struct.unpack("<2i", uc.mem_read(esp + 4, 8)))
        elif address == FAKE_OTHER:
            raise AssertionError("an unexpected import was called")

    mu.hook_add(UC_HOOK_CODE, hook)
    start_esp = STACK_TOP - 0x200
    mu.reg_write(UC_X86_REG_ESP, start_esp)
    for name, value in SENTINELS.items():
        mu.reg_write(REGS[name], value)
    site_va = 0x400000 + SITE[game]
    mu.emu_start(site_va, RESTART[game], count=200)
    return dict(
        eip=mu.reg_read(UC_X86_REG_EIP),
        regs={name: mu.reg_read(reg) for name, reg in REGS.items()},
        top=struct.unpack("<I", mu.mem_read(mu.reg_read(UC_X86_REG_ESP), 4))[0],
        start_esp=start_esp,
        **seen,
    )


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class StubExecutesTests(unittest.TestCase):
    """Run the rendered call site; only the three loader imports are faked."""

    def _check_restart_entered(self, game: str, out: dict) -> None:
        self.assertEqual(out["eip"], RESTART[game], "Restart was not reached")
        self.assertEqual(out["regs"]["esp"], out["start_esp"] - 4)
        self.assertEqual(out["top"], 0x400000 + SITE[game] + 5, "wrong return address")
        for name, value in SENTINELS.items():
            self.assertEqual(out["regs"][name], value, f"{name} changed")

    def test_the_stub_resets_the_current_slot_then_restarts(self) -> None:
        for game in EXE:
            build = _build(game)
            for subset in ("origins+statistics", "statistics", "parentage"):
                if game == "vv2" and subset == "parentage":
                    continue  # resolves Origins in; covered by origins+statistics
                image, _ = vp.render_patched_bytes(
                    STOCK / EXE[game], build, "collection_progression", _ids(game, subset)
                )
                image = bytes(image)
                for scenario in SCENARIOS:
                    for slot in (1, 3, 5):
                        with self.subTest(game=game, subset=subset, scenario=scenario, slot=slot):
                            out = _emulate(image, game, scenario, slot)
                            self._check_restart_entered(game, out)
                            if scenario in ("DLL missing", "export missing"):
                                self.assertEqual(out["calls"], [])
                            else:
                                self.assertEqual(out["calls"], [(int(game[2]), slot)])
                                self.assertEqual(out["names"], [b"ResetDeletedTribe"])
                            self.assertTrue(out["modules"])
                            self.assertEqual(set(out["modules"]), {b"VVFP Save Reset.dll"})

    def test_a_build_without_file_owners_restarts_without_a_call(self) -> None:
        for game in EXE:
            with self.subTest(game=game):
                image, _ = vp.render_patched_bytes(
                    STOCK / EXE[game], _build(game), "collection_progression", []
                )
                out = _emulate(bytes(image), game, "already loaded", 2)
                self._check_restart_entered(game, out)
                self.assertEqual(out["calls"], [])
                self.assertEqual(out["modules"], [])


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class RemovalTests(unittest.TestCase):
    """Removing one feature leaves exactly the image the rest would render."""

    CASES = (
        ("statistics", "statistics", None),
        ("parentage+statistics", "parentage", "carrier"),
        ("parentage+statistics", "statistics", "carrier"),
        ("origins+statistics", "origins", "carrier"),
        ("origins+statistics", "statistics", "origins"),
        ("origins+parentage+statistics", "statistics", "origins"),
        ("origins", "origins", None),
        # Not covered: removing Origins while the parentage log composes onto
        # its appended page refuses on origin/main already (the page guard),
        # which fails closed and is not this hook's to change.
    )

    def test_removal_round_trips(self) -> None:
        for mode in MODES:
            for game in EXE:
                build = _build(game)
                for installed, remove, placement in self.CASES:
                    if game == "vv2" and "parentage" in installed:
                        continue  # VV2's parentage log depends on Origins
                    with self.subTest(game=game, mode=mode, installed=installed, remove=remove):
                        ids = _ids(game, installed)
                        data, _ = vp.render_patched_bytes(STOCK / EXE[game], build, mode, ids)
                        resolved = [f.id for f in vp._selected_fun_patches(build, ids)]
                        if remove == "origins":
                            feature_id = f"{game}_enable_origins_exclusive_features"
                            wide = f"{game}_origins_village_wide_upgrades"
                            vp._remove_feature_bytes(data, vp.get_fun_patch(wide), mode)
                            remaining = [i for i in resolved if i not in (feature_id, wide)]
                        else:
                            feature_id = _ids(game, remove)[0]
                            remaining = [i for i in resolved if i != feature_id]
                        vp._remove_feature_bytes(data, vp.get_fun_patch(feature_id), mode)
                        expected, _ = vp.render_patched_bytes(
                            STOCK / EXE[game], build, mode, remaining
                        )
                        self.assertEqual(bytes(data), bytes(expected))
                        if placement is None:
                            self.assertEqual(_call_target(bytes(data), SITE[game]), RESTART[game])
                        else:
                            cave = vp.MAIN_MENU_START_OVER_CAVE[game][placement]
                            self.assertEqual(
                                _call_target(bytes(data), SITE[game]), cave["va"] + 0x28
                            )


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class PlacementGuardTests(unittest.TestCase):
    def test_render_refuses_a_stub_the_image_would_not_map_as_code(self) -> None:
        # VV4 .rsrc (zero bytes): mapped, never executable.  (Its .rdata tail, the
        # example this used before, is executable in every build now: the
        # safety layer's record guards live there.)
        saved = vp.MAIN_MENU_START_OVER_CAVE["vv4"]["carrier"]
        vp.MAIN_MENU_START_OVER_CAVE["vv4"]["carrier"] = {"file": 0xCF900, "va": 0x72B900}
        try:
            with self.assertRaises(vp.PatcherError):
                vp.render_patched_bytes(
                    STOCK / EXE["vv4"], _build("vv4"), "collection_progression",
                    _ids("vv4", "statistics"),
                )
        finally:
            vp.MAIN_MENU_START_OVER_CAVE["vv4"]["carrier"] = saved

    def test_a_stock_site_with_a_carrier_is_refused(self) -> None:
        data = (STOCK / EXE["vv3"]).read_bytes()
        vp._validate_main_menu_start_over(data, "vv3")  # stock and not required: fine
        with self.assertRaises(vp.PatcherError):
            vp._validate_main_menu_start_over(data, "vv3", required=True)

    def test_a_foreign_call_at_the_site_is_refused(self) -> None:
        data = bytearray((STOCK / EXE["vv1"]).read_bytes())
        data[SITE["vv1"] + 1] ^= 0x10
        with self.assertRaises(vp.PatcherError):
            vp._validate_main_menu_start_over(data, "vv1")


class SavedVillageHeaderTests(unittest.TestCase):
    """The erased village is read from the slot's own save, not a prior save.

    Live, VV2: launch the game and press Start Over at once, and the old
    village's Births and Conceptions log survived -- nothing had been saved in
    that process, so there was no published header to match it by, and the
    new village then wrote into the old one's log. VVFP Save Reset.dll now
    reads the name from "<base><slot>.ldw" (both hooks run before the game
    removes or overwrites it) through the exporters' own vv_village_name and
    vv_village_header. The on-disk proof is the harness
    (scripts/build_saved_village_harness.ps1, which compiles the shipped
    source); these hold its cases, the layout and the shipped DLL in place.
    """

    EXPORT_C = ROOT / "native" / "save_reset_export" / "save_reset_export.c"
    HARNESS = ROOT / "native" / "save_reset_export" / "saved_village_harness.c"
    IDENTITY_C = ROOT / "native" / "shared" / "village_identity.c"
    DLL_PATH = ROOT / "assets" / "save_reset" / DLL

    def _table(self, text: str, name: str) -> list[int]:
        match = re.search(name + r"\[5\] = \{([^}]*)\}", text)
        self.assertIsNotNone(match, name)
        return [int(v.strip().rstrip("u"), 0) for v in match.group(1).split(",")]

    def test_the_save_buffer_ends_at_the_slot_field(self) -> None:
        """The game's current-slot field sits right after the save buffer
        (village + 8 + length), which ties the three measurements together."""
        text = self.EXPORT_C.read_text(encoding="utf-8")
        lengths = self._table(text, "SAVE_BUFFER_BYTES")
        for index, game in enumerate(EXE):
            with self.subTest(game=game):
                self.assertEqual(8 + lengths[index], SLOT[game])
        self.assertEqual(self._table(text, "SAVE_FILE_HEADER"), [12, 12, 12, 24, 24])
        self.assertEqual(self._table(text, "SAVE_LENGTH_AT"), [8, 8, 8, 16, 16])

    def test_the_name_is_read_with_the_exporters_own_functions(self) -> None:
        text = self.EXPORT_C.read_text(encoding="utf-8")
        body = text[text.index("int vv_saved_village_header(") :]
        self.assertIn("vv_village_name(game,", body)
        self.assertIn("data + SAVE_FILE_HEADER[game - 1] - 8", body)
        self.assertIn("vv_village_header(header, sizeof header, name, slot)", body)
        self.assertIn("valid != 1", body)
        self.assertIn("!(tail[-1] >= L'0' && tail[-1] <= L'9')", text)

    def test_the_reset_prefers_the_save_then_the_published_header(self) -> None:
        text = self.EXPORT_C.read_text(encoding="utf-8")
        body = text[text.index("int __stdcall ResetDeletedTribe(") :]
        saved = body.index("vv_saved_village_header(game, slot, folder")
        recalled = body.index("vv_village_recall(village")
        self.assertLess(saved, recalled)
        self.assertIn("header_is_for_slot(village, slot)", body[recalled:])

    def test_the_folder_reserve_is_only_the_readers_filter(self) -> None:
        # A larger reserve refuses a long Documents path whose saves still
        # fit, and then the reset cannot name the village (Codex P2, #487).
        text = self.EXPORT_C.read_text(encoding="utf-8")
        self.assertIn("#define SAVE_FILTER_RESERVE 8", text)
        self.assertEqual(len("\\*1.ldw") + 1, 8)
        body = text[text.index("int __stdcall ResetDeletedTribe(") :]
        self.assertIn("vv_save_folder_w(folder, SAVE_FILTER_RESERVE)", body)
        reader = text[text.index("int vv_saved_village_header(") :]
        self.assertIn("lstrlenW(folder) + SAVE_FILTER_RESERVE >= MAX_PATH", reader)

    def test_the_harness_covers_every_case(self) -> None:
        text = self.HARNESS.read_text(encoding="utf-8")
        self.assertIn('#include "save_reset_export.c"', text)  # the shipped source
        for case in (
            "the header is exactly the exporters'",
            "slot 1 names its own village, not slot 2's",
            "slot 1 with no save of its own returns nothing",
            "backups 21 and 41 are never read as slot 1",
            "two valid saves for one slot: nothing is returned",
            "a file one byte too long is refused",
            "a file without the ldwg magic is refused",
            "a file whose length field is not this game's buffer is refused",
            "another game's save is refused",
            "a control byte in the name returns nothing",
            "the base name is found, not assumed",
        ):
            with self.subTest(case=case):
                self.assertIn(case, text)

    def test_the_harness_uses_the_exporters_name_offsets(self) -> None:
        identity = self.IDENTITY_C.read_text(encoding="utf-8")
        match = re.search(r"NAME_OFFSETS\[5\] = \{([^}]*)\}", identity)
        offsets = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]+)", match.group(1))]
        harness = self.HARNESS.read_text(encoding="utf-8")
        self.assertEqual(self._table(harness, "NAME_AT"), offsets)

    def test_the_shipped_dll_carries_the_reader(self) -> None:
        blob = self.DLL_PATH.read_bytes()
        self.assertIn("%ls\\*%d.ldw".encode("utf-16-le"), blob)
        self.assertEqual(
            vp.sha256(self.DLL_PATH),
            next(
                item["sha256"].upper()
                for item in vp._start_over_reset_from_origins("vv2")[1:]
            ),
        )


if __name__ == "__main__":
    unittest.main()
