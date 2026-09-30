"""Lessons stop at 50 (A New Home, The Lost Children, The Secret City): the
companion, the three rows, the stubs and the sites.

The owner keeps the ordinary lesson rows (cap 100) and adds these as
SEPARATE rows on top of them.

A New Home / The Lost Children (VV1VV2Tests):

* The site the DLL verifies is the lesson row's own cave head, exactly as
  the rendered executable holds it with the lesson row selected, and stock
  (the row off) is zeros there -- so without the lesson row nothing installs.
* The DLL's stub, RUN in an emulator with the game's RNG scripted: callback
  127 awards only a skill below 50 and stops at exactly 50, a Master is
  never lowered, all-at-50 awards nothing and returns `ret 8`; any other
  callback id jumps back into the cave at site+5 with the compare's flags,
  stack and registers untouched.
* The Origins companions carry the loader bridge; both rows depend on the
  lesson row and Origins and patch no executable byte.

The Secret City, pinned against the stock executable and the shipped files:

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
# The probes and counters the emulator drives exist only in the TEST build
# (VVFP_TEST, same source; tests/test_shipped_dlls_have_no_test_hooks.py).
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Lesson Cap.test.dll"
# tests/test_dlls/ is export-ignore: the release source archive carries no test
# build, so there the tests that drive one skip instead of failing.
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
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
        pe = pefile.PE(str(TEST_DLL))
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
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
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

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_gain_stops_at_exactly_50(self):
        for start, extra in ((49, 0), (49, 2), (43, 0), (43, 2), (42, 1)):
            p = Probe([start, 0, 0, 0, 0], rng=[0, extra])
            self.assertEqual(p.skills()[0], min(CAP, start + 7 + extra), (start, extra))
        self.assertEqual(Probe([41, 0, 0, 0, 0], rng=[0, 1]).skills()[0], 49)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
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

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
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
        self.assertIn("**Runs on the Origins-exclusive base, which the patcher installs automatically with it**", self.manifest["description"])
        self.assertNotIn("Enable Origins-Exclusive Features", self.manifest["description"])
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("assets/lesson_cap/VVFP Lesson Cap.dll", release)
        self.assertIn("data/vv3_chief_lessons_cap_feature.json", release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme.count("**Tribal Chief Lessons Stop at 50**"), 1)
        self.assertIn(f"`{FEATURE}`", readme)


VV12 = {
    "vv1": dict(row="vv1_school_lessons_cap_50", lesson="vv1_school_lessons_grant_skill",
                manifest="vv1_school_lessons_cap_feature.json", game_no=1,
                site=0x4566E0, file=0x566E0, rng=0x402F10, stride=0x3D8, skills=0x3BC,
                exe="Virtual Villagers - A New Home.exe",
                companion="native/vv1_origins_icons/vv1_origins_icons.c",
                dll="assets/origins/VVFP VV1 Origins Icons.dll"),
    "vv2": dict(row="vv2_teaching_children_cap_50", lesson="vv2_teaching_children_grants_skill",
                manifest="vv2_teaching_children_cap_feature.json", game_no=2,
                site=0x473D80, file=0x73D80, rng=0x4031A0, stride=0xE48C, skills=0x7E4,
                exe="Virtual Villagers - The Lost Children.exe",
                companion="native/vv2_origins_icons/vv2_origins_icons.c",
                dll="assets/origins/VVFP VV2 Origins Icons.dll"),
}
ARRAY = 0x40000000


def _dll_image():
    pe = pefile.PE(str(TEST_DLL))
    base = pe.OPTIONAL_HEADER.ImageBase
    exports = {e.name.decode(): base + e.address
               for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    return pe, base, exports


def _probe_site(game_no: int):
    pe, base, exports = _dll_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    mu.mem_write(base, pe.get_memory_mapped_image())
    mu.mem_map(SKILLS_AT, 0x1000)
    mu.mem_map(RETURN, 0x1000)
    mu.mem_write(RETURN, b"\xC3")
    mu.mem_map(STACK - 0x10000, 0x20000)
    esp = STACK - 0x200
    mu.mem_write(esp, struct.pack("<6I", RETURN, game_no, SKILLS_AT, SKILLS_AT + 0x10,
                                  SKILLS_AT + 0x20, SKILLS_AT + 0x40))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(exports["VvfpLessonCapProbeSite"], RETURN, count=10000)
    n = mu.reg_read(UC_X86_REG_EAX)
    va = struct.unpack("<I", mu.mem_read(SKILLS_AT, 4))[0]
    expected = bytes(mu.mem_read(SKILLS_AT + 0x10, n))
    patched = bytes(mu.mem_read(SKILLS_AT + 0x20, 5))
    stub = struct.unpack("<I", mu.mem_read(SKILLS_AT + 0x40, 4))[0]
    return va, expected, patched, stub


class StubRun:
    """The DLL's VV1/VV2 stub as the cave's detour enters it: ecx = the
    villager array, [esp+4] = the child's index, [esp+8] = the callback id."""

    def __init__(self, game: str, index: int, callback: int, skills: list[int], rng: list[int]):
        g = VV12[game]
        stub = _probe_site(g["game_no"])[3]
        pe, base, exports = _dll_image()
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
        mu.mem_write(base, pe.get_memory_mapped_image())
        mu.mem_map(g["rng"] & ~0xFFF, 0x1000)
        mu.mem_write(g["rng"], b"\xC3")
        mu.mem_map(g["site"] & ~0xFFF, 0x2000)
        mu.mem_write(g["site"] + 5, b"\xC3")
        mu.mem_map(ARRAY, 0x200000)
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_map(RETURN, 0x1000)
        mu.mem_write(RETURN, b"\xC3")
        self.record = ARRAY + index * g["stride"] + g["skills"]
        mu.mem_write(self.record, struct.pack("<5i", *skills))
        esp = STACK - 0x100
        mu.mem_write(esp, struct.pack("<3I", RETURN, index, callback))
        mu.reg_write(UC_X86_REG_ESP, esp)
        from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EFLAGS
        mu.reg_write(UC_X86_REG_ECX, ARRAY)
        self.g, self.rng, self.calls, self.stopped = g, list(rng), [], None
        mu.hook_add(UC_HOOK_CODE, self._hook)
        mu.emu_start(stub, 0, count=100000)
        self.mu = mu
        self.esp_after = mu.reg_read(UC_X86_REG_ESP)
        self.ecx_after = mu.reg_read(UC_X86_REG_ECX)
        self.zf = bool(mu.reg_read(UC_X86_REG_EFLAGS) & 0x40)
        self.esp_before = esp

    def _hook(self, mu, address, size, user_data):
        if address == self.g["rng"]:
            esp = mu.reg_read(UC_X86_REG_ESP)
            bound = struct.unpack("<I", mu.mem_read(esp + 4, 4))[0]
            self.calls.append(bound)
            value = self.rng.pop(0) if self.rng else 0
            assert 0 <= value < bound, (value, bound)
            mu.reg_write(UC_X86_REG_EAX, value)
        elif address in (self.g["site"] + 5, RETURN):
            self.stopped = address
            mu.emu_stop()

    def skills(self) -> list[int]:
        return list(struct.unpack("<5i", self.mu.mem_read(self.record, 20)))


class VV1VV2Tests(unittest.TestCase):
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_site_is_the_lesson_rows_cave_head_and_nothing_without_it(self):
        import vv_fun_patcher as vfp
        for game, g in VV12.items():
            with self.subTest(game=game):
                va, expected, patched, stub = _probe_site(g["game_no"])
                self.assertEqual(va, g["site"])
                self.assertEqual(expected, bytes.fromhex("837C24087F753F608BF1"))
                rel, = struct.unpack("<i", patched[1:5])
                self.assertEqual(patched[0], 0xE9)
                self.assertEqual(va + 5 + rel, stub)
                build = next(b for b in vfp.load_builds() if b.id == game)
                exe = ROOT / "research" / "stock-executables" / g["exe"]
                rendered, _ = vfp.render_patched_bytes(exe, build, "immediate_fixed", [g["lesson"]])
                self.assertEqual(bytes(rendered[g["file"]:g["file"] + 10]), expected,
                                 "the lesson row's own cave head, as shipped")
                self.assertFalse(any(exe.read_bytes()[g["file"]:g["file"] + 10]),
                                 "stock is zeros: without the lesson row nothing installs")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_callback_127_awards_only_below_50_and_stops_at_50(self):
        for game in VV12:
            with self.subTest(game=game):
                r = StubRun(game, 3, 127, [10, 20, 30, 40, 0], rng=[4, 2])
                self.assertEqual(r.stopped, RETURN, "ret 8 to the action runner")
                self.assertEqual(r.esp_after, r.esp_before + 12)
                self.assertEqual(r.calls, [5, 3])
                self.assertEqual(r.skills(), [10, 20, 30, 40, 9])
                r = StubRun(game, 3, 127, [49, 0, 0, 0, 0], rng=[0, 2])
                self.assertEqual(r.skills()[0], 50)
                r = StubRun(game, 7, 127, [100, 12, 50, 33, 49], rng=[2, 1])
                self.assertEqual(r.calls, [3, 3])
                self.assertEqual(r.skills(), [100, 12, 50, 33, 50])
                r = StubRun(game, 1, 127, [50, 60, 100, 50, 51], rng=[])
                self.assertEqual(r.skills(), [50, 60, 100, 50, 51])
                self.assertEqual(r.calls, [])
                self.assertEqual(r.stopped, RETURN)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_every_other_callback_goes_back_into_the_cave(self):
        for game in VV12:
            for callback in (0, 1, 42, 126, 128):
                with self.subTest(game=game, callback=callback):
                    r = StubRun(game, 2, callback, [1, 2, 3, 4, 5], rng=[])
                    self.assertEqual(r.stopped, VV12[game]["site"] + 5, "the cave's own jne")
                    self.assertEqual(r.esp_after, r.esp_before, "stack untouched")
                    self.assertEqual(r.ecx_after, ARRAY, "ecx untouched")
                    self.assertFalse(r.zf, "the replayed compare: not 127, so jne is taken")
                    self.assertEqual(r.skills(), [1, 2, 3, 4, 5])
                    self.assertEqual(r.calls, [])

    def test_the_rows_depend_on_the_lesson_and_origins_and_the_bridge_is_shipped(self):
        import vv_fun_patcher as vfp
        from vv_fun_patcher_gui import default_fun_patch_selection
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        ids = {p.id for p in vfp.load_public_fun_patches()}
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for game, g in VV12.items():
            with self.subTest(game=game):
                m = json.loads((ROOT / "data" / g["manifest"]).read_text(encoding="utf-8"))
                self.assertIn(g["row"], ids)
                self.assertTrue(default_fun_patch_selection(g["row"]))
                self.assertEqual(m["dependencies"], [g["lesson"], f"{game}_enable_origins_exclusive_features"])
                self.assertEqual(m["patches"], [])
                self.assertEqual([c["sha256"] for c in m["companion_files"]], [sha])
                self.assertIn("**Requires", m["description"])
                self.assertIn(f"`{g['row']}`", readme)
                self.assertIn(f"data/{g['manifest']}", release)
                source = (ROOT / g["companion"]).read_text(encoding="utf-8")
                if game == "vv1":
                    self.assertIn('"VVFP Lesson Cap.dll"', source)
                    self.assertIn('GetProcAddress(companion, "VvfpLessonCapInstall")', source)
                self.assertIn(f"vvfp_lesson_cap_bridge({g['game_no']});", source)
                self.assertIn(b"VVFP Lesson Cap.dll", (ROOT / g["dll"]).read_bytes())
        # The ordinary lesson rows are untouched: still 7 to 9 points, cap 100.
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        v1 = next(f for f in builds["fun_patches"] if f["id"] == "vv1_school_lessons_grant_skill")
        body = next(p for p in v1["patches"] if p["offset"] == "0x566E0")["after"]
        self.assertIn("833F647E06C70764000000", body, "VV1 lesson still caps at 100")
        v2 = next(s for s in builds["fun_patch_support"] if s["game_id"] == "vv2")
        body = next(p for p in v2["patches"] if p["offset"] == "0x73D80")["after"]
        self.assertIn("833F647E06C70764000000", body, "VV2 lesson still caps at 100")


if __name__ == "__main__":
    unittest.main()
