"""Tribal Chief Lessons Stop at 50 (The Secret City): the companion, the row,
the stub and the site.

Pinned here against the stock executable and the shipped files:

* The site's stock bytes are callback 42's `push 5; call 0x4032D0`, the
  case whose five branches add RNG(3)+7 through the 100-capped helper.
* The award, RUN in an emulator through the DLL's probe export with a
  scripted generator: only skills below 50 are chosen, the gain stops at
  exactly 50, a Master is never lowered, all-at-50 awards nothing.
* The stub assembles to the addresses the manifest names, resolves the
  companion through the stock import table, calls VvfpLessonCapAward(3,
  record) with the case's record and returns through `pop esi; ret 8`;
  without the companion it replays the displaced bytes into the stock case.
* The overlay sits in the zero range of Origins' page after the fix-huts
  overlay, and the composed image renders in every mode with all four
  overlaying rows selected.
* The row is registered, bundled, default-on, depends on Origins and pins
  the DLL.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DLL = ROOT / "assets" / "lesson_cap" / "VVFP Lesson Cap.dll"
MANIFEST = ROOT / "data" / "vv3_chief_lessons_cap_feature.json"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
FEATURE = "vv3_chief_lessons_cap_50"
ORIGINS = "vv3_enable_origins_exclusive_features"
STACK = 0x70000000
SKILLS_AT = 0x50000000
RNG_AT = 0x7E000000
RETURN = 0x7F000000
CAP = 50


def _stock(va: int, n: int) -> bytes:
    pe = pefile.PE(str(STOCK), fast_load=True)
    data = STOCK.read_bytes()
    return data[pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase):][:n]


class Probe:
    """VvfpLessonCapProbe(skills, rng) in the emulator with a scripted rng."""

    def __init__(self, skills: list[int], rng: list[int]):
        pe = pefile.PE(str(DLL))
        base = pe.OPTIONAL_HEADER.ImageBase
        exports = {e.name.decode(): base + e.address
                   for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        mu.mem_map(base, size)
        mu.mem_write(base, pe.get_memory_mapped_image())
        mu.mem_map(SKILLS_AT, 0x1000)
        mu.mem_write(SKILLS_AT, struct.pack("<5i", *skills))
        mu.mem_map(RNG_AT, 0x1000)
        mu.mem_write(RNG_AT, b"\xC3")
        mu.mem_map(RETURN, 0x1000)
        mu.mem_write(RETURN, b"\xC3")
        mu.mem_map(STACK - 0x10000, 0x20000)
        esp = STACK - 0x200
        mu.mem_write(esp, struct.pack("<3I", RETURN, SKILLS_AT, RNG_AT))
        mu.reg_write(UC_X86_REG_ESP, esp)
        self.rng = list(rng)
        self.calls: list[int] = []
        mu.hook_add(UC_HOOK_CODE, self._hook)
        mu.emu_start(exports["VvfpLessonCapProbe"], RETURN, count=100000)
        self.mu = mu
        self.eip = mu.reg_read(UC_X86_REG_EIP)
        self.result = mu.reg_read(UC_X86_REG_EAX)
        self.stats = struct.unpack("<3i", mu.mem_read(exports["VvfpLessonCapStats"], 12))

    def _hook(self, mu, address, size, user_data):
        if address == RNG_AT:
            esp = mu.reg_read(UC_X86_REG_ESP)
            bound = struct.unpack("<I", mu.mem_read(esp + 4, 4))[0]
            self.calls.append(bound)
            value = self.rng.pop(0) if self.rng else 0
            assert 0 <= value < bound, (value, bound)
            mu.reg_write(UC_X86_REG_EAX, value)

    def skills(self) -> list[int]:
        return list(struct.unpack("<5i", self.mu.mem_read(SKILLS_AT, 20)))


class AwardTests(unittest.TestCase):
    def test_one_of_five_below_50_gains_7_to_9(self):
        for pick, extra in ((0, 0), (4, 2), (2, 1)):
            p = Probe([10, 20, 30, 40, 0], rng=[pick, extra])
            self.assertEqual(p.eip, RETURN)
            self.assertEqual(p.calls, [5, 3])
            expected = [10, 20, 30, 40, 0]
            expected[pick] += 7 + extra
            self.assertEqual(p.skills(), expected)
            self.assertEqual(p.result, 1)
            self.assertEqual(p.stats, (1, 1, 0))

    def test_the_gain_stops_at_exactly_50(self):
        for start, extra in ((49, 0), (49, 2), (43, 0), (43, 2), (42, 1)):
            p = Probe([start, 0, 0, 0, 0], rng=[0, extra])
            self.assertEqual(p.skills()[0], min(CAP, start + 7 + extra), (start, extra))
        self.assertEqual(Probe([41, 0, 0, 0, 0], rng=[0, 1]).skills()[0], 49)

    def test_only_skills_below_50_are_chosen_and_none_is_lowered(self):
        for k, index in ((0, 1), (1, 3), (2, 4)):
            p = Probe([100, 12, 50, 33, 49], rng=[k, 1])
            self.assertEqual(p.calls, [3, 3], "RNG(3) picks among the three below 50")
            expected = [100, 12, 50, 33, 49]
            expected[index] = min(CAP, expected[index] + 8)
            self.assertEqual(p.skills(), expected, k)
        p = Probe([100, 60, 50, 51, 99], rng=[])
        self.assertEqual(p.skills(), [100, 60, 50, 51, 99])
        self.assertEqual(p.calls, [], "nothing eligible: the RNG is not consulted")
        self.assertEqual(p.result, 0)
        self.assertEqual(p.stats, (1, 0, 1))

    def test_all_at_50_awards_nothing(self):
        p = Probe([50] * 5, rng=[])
        self.assertEqual(p.skills(), [50] * 5)
        self.assertEqual(p.calls, [])
        self.assertEqual(p.result, 0)

    def test_the_award_export_and_the_game_rng_are_what_the_stub_expects(self):
        pe = pefile.PE(str(DLL))
        names = {e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        self.assertIn("VvfpLessonCapAward", names, "undecorated: the stub resolves this name")
        self.assertEqual({e.dll.decode().upper() for e in pe.DIRECTORY_ENTRY_IMPORT}, {"KERNEL32.DLL"})
        source = (ROOT / "native" / "vvfp_lesson_cap" / "vvfp_lesson_cap.c").read_text(encoding="utf-8")
        self.assertIn("((rng_t)0x4032D0u)", source)
        self.assertIn("0xEACu", source)
        # The stock RNG is a cdecl(int) at 0x4032D0 and the case reads the
        # skills at record+0xEAC: both are what callback 42 itself uses.
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        case = "\n".join(f"{i.mnemonic} {i.op_str}" for i in md.disasm(_stock(0x458F2B, 0x23), 0x458F2B))
        self.assertIn("push 3\ncall 0x4032d0", case)
        self.assertIn("add ecx, 0xeac", case)
        self.assertIn("call 0x455740", case)


class RowTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.overlay = self.manifest["pe_append_transaction"]["composition_overlays"][ORIGINS]

    def test_the_site_patch_replaces_the_exact_stock_bytes(self):
        (patch,) = self.overlay["hook_patches"]
        self.assertEqual(int(patch["offset"], 16), 0x458F11 - 0x400000)
        self.assertEqual(_stock(0x458F11, 7), bytes.fromhex(patch["before"]))
        self.assertEqual(bytes.fromhex(patch["before"]), bytes.fromhex("6A05E8B8A3FAFF"))
        after = bytes.fromhex(patch["after"])
        rel, = struct.unpack("<i", after[1:5])
        self.assertEqual(0x458F11 + 5 + rel, int(self.overlay["page_virtual_address"], 16))
        self.assertEqual(after[5:], b"\x90\x90")
        # Only the jump table reaches the case: the bytes before it end a
        # case with `pop esi; ret 8`, so nothing falls into the detour.
        self.assertEqual(_stock(0x458F0D, 4), bytes.fromhex("5EC20800"))
        table = _stock(0x4593AC + 42 * 4, 4)
        self.assertEqual(struct.unpack("<I", table)[0], 0x458F11, "callback 42's table entry")

    def test_the_stub_resolves_the_companion_and_takes_the_stock_paths(self):
        page = bytes.fromhex(self.overlay["append_bytes"])
        base = int(self.overlay["page_virtual_address"], 16)
        self.assertEqual(base, 0x6DFC00, "after the fix-huts overlay at 0x6DF800")
        self.assertEqual(self.overlay["overlay_offset"], "0xCBC00")
        self.assertIn(b"VVFP Lesson Cap.dll\0", page)
        self.assertIn(b"VvfpLessonCapAward\0", page)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        text = "\n".join(f"{i.mnemonic} {i.op_str}" for i in md.disasm(page[:0x80], base))
        self.assertIn("call dword ptr [0x47c074]", text, "GetModuleHandleA")
        self.assertIn("call dword ptr [0x47c124]", text, "LoadLibraryA")
        self.assertIn("call dword ptr [0x47c128]", text, "GetProcAddress")
        self.assertIn("mov dword ptr [0x6e0ff4], eax", text, "the resolved export, cached in .vv3md")
        self.assertIn("push dword ptr [esp + 0x28]\npush 3\ncall eax\nadd esp, 8\npopal \npop esi\nret 8", text)
        self.assertIn("popal \npush 5\ncall 0x4032d0\njmp 0x458f18", text, "no companion: the stock case")
        pe = pefile.PE(str(STOCK), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        imports = {i.name: i.address for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports[b"GetModuleHandleA"], 0x47C074)
        self.assertEqual(imports[b"LoadLibraryA"], 0x47C124)
        self.assertEqual(imports[b"GetProcAddress"], 0x47C128)

    def test_the_cache_slot_is_unclaimed(self):
        """0x6E0FF4 in .vv3md: nothing else references it (fix-huts uses 0x6E0FF8)."""
        for path, key in ((ROOT / "data" / "vv3_origins_feature.json", None),
                          (ROOT / "data" / "vv3_parentage_feature.json", "vv3_write_parentage_log"),
                          (ROOT / "data" / "vv3_builders_fix_huts_feature.json", None)):
            d = json.loads(path.read_text(encoding="utf-8"))
            feats = [f for f in d.get("features", [d]) if key is None or f["id"] == key]
            for f in feats:
                blobs = [bytes.fromhex(p["after"]) for p in f.get("patches", [])]
                t = f.get("pe_append_transaction", {})
                for lay in t.get("layouts", {}).values():
                    blobs.append(bytes.fromhex(lay["append_bytes"]))
                for ov in t.get("composition_overlays", {}).values():
                    blobs.append(bytes.fromhex(ov["append_bytes"]))
                for b in blobs:
                    for i in range(len(b) - 3):
                        v = struct.unpack_from("<I", b, i)[0]
                        self.assertNotEqual(v, 0x6E0FF4, f"{path.name} references the cache slot")

    def test_the_composed_image_renders_in_every_mode_with_every_overlay(self):
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv3")
        page = bytes.fromhex(self.overlay["append_bytes"])[:0x400]
        fix_huts = json.loads((ROOT / "data" / "vv3_builders_fix_huts_feature.json").read_text(encoding="utf-8"))
        fix_page = bytes.fromhex(fix_huts["pe_append_transaction"]["composition_overlays"][ORIGINS]["append_bytes"])[:0x400]
        for mode in vfp.load_patch_modes():
            rendered, applied = vfp.render_patched_bytes(
                STOCK, build, mode.id,
                [ORIGINS, "vv3_write_parentage_log", "vv3_builders_fix_huts", FEATURE])
            self.assertEqual(bytes(rendered[0xCBC00:0xCC000]), page, mode.id)
            self.assertEqual(bytes(rendered[0xCB800:0xCBC00]), fix_page, "fix-huts overlay intact")
            self.assertEqual(bytes(rendered[0x58F11:0x58F18]), bytes.fromhex(self.overlay["hook_patches"][0]["after"]), mode.id)
            owners = {edit["owner"] for edit in applied}
            self.assertIn(f"feature:{FEATURE}", owners)

    def test_the_row_is_registered_bundled_default_on_and_pins_the_dll(self):
        import vv_fun_patcher as vfp
        from vv_fun_patcher_gui import default_fun_patch_selection
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        ids = {p.id: p for p in vfp.load_public_fun_patches()}
        self.assertIn(FEATURE, ids)
        self.assertTrue(default_fun_patch_selection(FEATURE), "the owner: selectable by default")
        self.assertEqual(self.manifest["dependencies"], [ORIGINS])
        self.assertEqual([c["sha256"] for c in self.manifest["companion_files"]], [sha])
        self.assertIn("**Requires Enable Origins-Exclusive Features**", self.manifest["description"])
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("assets/lesson_cap/VVFP Lesson Cap.dll", release)
        self.assertIn("data/vv3_chief_lessons_cap_feature.json", release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme.count("**Tribal Chief Lessons Stop at 50**"), 1)
        self.assertIn(f"`{FEATURE}`", readme)


if __name__ == "__main__":
    unittest.main()
