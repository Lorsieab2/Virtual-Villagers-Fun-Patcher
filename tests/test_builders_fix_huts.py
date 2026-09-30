"""Builders Fix Huts When Idle (all five games): the companion,
the five rows, the detour sites and the loaders.

Pinned here against the stock executables and the shipped files:

* Each runtime site's stock bytes (VV1, VV2, VV4, VV5) are exactly what the
  stock executable holds, so the DLL's verify-then-install can succeed on the
  real game; the jmp it writes lands on the game's stub (decoded in an
  emulator from the DLL's own probe).
* The VV1/VV2 choosers, RUN in the emulator over a village image laid out
  as the game keeps its flags: no hut complete -> stock; all complete ->
  stock; some complete -> only a complete hut is ever chosen.
* The Secret City's row: the site patch replaces the exact stock test, the
  overlay stub assembles to the addresses the manifest names (resolves the
  companion through the stock import table, calls VvfpFixHutsDecide(3, esi),
  takes the stock 'started' / 'nothing' paths), sits in a zero range of
  Origins' page after the parentage overlay, and the composed VV3 image
  renders in every mode with the stub in place.
* The rows are selectable by default, registered, bundled and described; the four
  per-frame companions carry the loader bridge and are re-pinned.
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
from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DLL = ROOT / "assets" / "fix_huts" / "VVFP Fix Huts.dll"
# The probes and counters the emulator drives exist only in the TEST build
# (VVFP_TEST, same source; tests/test_shipped_dlls_have_no_test_hooks.py).
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Fix Huts.test.dll"
# tests/test_dlls/ is export-ignore: the release source archive carries no test
# build, so there the tests that drive one skip instead of failing.
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
SOURCE = ROOT / "native" / "vvfp_fix_huts" / "vvfp_fix_huts.c"
STOCK = {g: ROOT / "research" / "stock-executables" / n for g, n in (
    ("vv1", "Virtual Villagers - A New Home.exe"), ("vv2", "Virtual Villagers - The Lost Children.exe"),
    ("vv3", "Virtual Villagers - The Secret City.exe"), ("vv4", "Virtual Villagers - The Tree of Life.exe"),
    ("vv5", "Virtual Villagers - New Believers.exe"))}
MANIFESTS = {g: ROOT / "data" / f"{g}_builders_fix_huts_feature.json" for g in STOCK}
GAME_NO = {"vv1": 1, "vv2": 2, "vv3": 3, "vv4": 4, "vv5": 5}
STACK = 0x70000000
VILLAGE = 0x50000000
STATE = 0x60000000


def _stock(game: str, va: int, n: int) -> bytes:
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    data = STOCK[game].read_bytes()
    return data[pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase):][:n]


def _emulator():
    pe = pefile.PE(str(TEST_DLL))
    exports = {e.name.decode(): pe.OPTIONAL_HEADER.ImageBase + e.address
               for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(base, image)
    mu.mem_map(STACK, 0x10000)
    mu.mem_map(VILLAGE, 0x1000000)
    mu.mem_map(STATE, 0x100000)
    return mu, exports


def _call(mu, fn, *args):
    esp = STACK + 0x8000
    ret = STACK + 0x100
    mu.mem_write(ret, b"\xF4")   # hlt: an end marker
    mu.mem_write(esp, struct.pack("<I", ret) + b"".join(struct.pack("<I", a) for a in args))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(fn, ret, count=200000)
    return mu.reg_read(UC_X86_REG_EAX)


def _probe_site(game_no: int):
    mu, ex = _emulator()
    buf = STACK + 0x4000
    n = _call(mu, ex["VvfpFixHutsProbeSite"], game_no, buf, buf + 0x10, buf + 0x30, buf + 0x50)
    va, = struct.unpack("<I", mu.mem_read(buf, 4))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0x50, 4))
    return n, va, bytes(mu.mem_read(buf + 0x10, n)), bytes(mu.mem_read(buf + 0x30, n)), stub


class RuntimeSiteTests(unittest.TestCase):
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_each_runtime_sites_stock_bytes_match_and_the_jmp_lands_on_the_stub(self):
        for game in ("vv1", "vv2", "vv4", "vv5"):
            manifest = json.loads(MANIFESTS[game].read_text(encoding="utf-8"))
            # The hut site first; the food-gate site second (its own tests
            # are in tests/test_builders_regardless_of_food.py); in A New Home
            # and The Lost Children the Building-level gate third
            # (tests/test_builders_level_gate.py).
            self.assertEqual(len(manifest["runtime_detours"]), 3 if game in ("vv1", "vv2") else 2, game)
            site = manifest["runtime_detours"][0]
            n, va, stock, patched, stub = _probe_site(GAME_NO[game])
            self.assertEqual(va, int(site["va"], 16), game)
            self.assertEqual(stock, bytes.fromhex(site["stock_bytes"]), game)
            self.assertEqual(_stock(game, va, n), stock, game)
            self.assertEqual(patched[0], 0xE9)
            rel, = struct.unpack("<i", patched[1:5])
            self.assertEqual((va + 5 + rel) & 0xFFFFFFFF, stub, game)
            self.assertEqual(patched[5:], b"\x90" * (n - 5), game)

    def test_the_sites_are_the_dispatcher_points_the_source_describes(self):
        # VV1/VV2: the skip roll `push 100; call rand; add esp,4` right before
        # `cmp eax, 20` and the random-hut pick.  VV3-5: `cmp edi, ebx; je`.
        self.assertEqual(_stock("vv1", 0x447724 + 10, 3), bytes.fromhex("83F814"))
        self.assertEqual(_stock("vv1", 0x447737, 2), bytes.fromhex("6A03"), "rand(3) follows")
        self.assertEqual(_stock("vv2", 0x46029D + 10, 3), bytes.fromhex("83F814"))
        self.assertEqual(_stock("vv2", 0x4602B0, 2), bytes.fromhex("6A04"), "rand(4) follows")
        for game, va in (("vv3", 0x45B39E), ("vv4", 0x463F8A), ("vv5", 0x46CADA)):
            self.assertEqual(_stock(game, va, 2), bytes.fromhex("3BFB"), game)
            self.assertEqual(_stock(game, va + 8, 1), b"\x57", f"{game}: push edi (rand(count)) follows")


class ChooserTests(unittest.TestCase):
    """The VV1/VV2 choosers over a village image with the game's own flags."""

    def _choose(self, game_no: int, flags: dict[int, int]) -> int:
        mu, ex = _emulator()
        state_off = {1: 0x3E010, 2: 0xE574D4}[game_no]
        mu.mem_write(VILLAGE + state_off, struct.pack("<I", STATE))
        for off, value in flags.items():
            mu.mem_write(STATE + off, bytes([value]))
        return _call(mu, ex["VvfpFixHutsProbeChoose"], game_no, VILLAGE) & 0xFFFFFFFF

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_vv1_chooses_only_among_complete_huts_while_one_is_incomplete(self):
        none = self._choose(1, {0x9FE8: 0, 0x9FF0: 0, 0x9FF8: 0})
        self.assertEqual(none, 0xFFFFFFFF, "no hut complete: stock")
        every = self._choose(1, {0x9FE8: 1, 0x9FF0: 1, 0x9FF8: 1})
        self.assertEqual(every, 0xFFFFFFFF, "all complete: stock (its own fix-a-hut option)")
        seen = {self._choose(1, {0x9FE8: 1, 0x9FF0: 0, 0x9FF8: 1}) for _ in range(12)}
        self.assertTrue(seen <= {9, 11}, seen)
        self.assertEqual(self._choose(1, {0x9FE8: 0, 0x9FF0: 1, 0x9FF8: 0}), 10)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_vv2_chooses_only_among_complete_huts_while_one_is_incomplete(self):
        self.assertEqual(self._choose(2, {0x2E818: 0, 0x2E820: 0, 0x2E828: 0}), 0xFFFFFFFF)
        self.assertEqual(self._choose(2, {0x2E818: 1, 0x2E820: 1, 0x2E828: 1}), 0xFFFFFFFF)
        seen = {self._choose(2, {0x2E818: 1, 0x2E820: 1, 0x2E828: 0}) for _ in range(12)}
        self.assertTrue(seen <= {24, 25}, seen)


class SecretCityTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFESTS["vv3"].read_text(encoding="utf-8"))
        self.overlay = self.manifest["pe_append_transaction"]["composition_overlays"][
            "vv3_enable_origins_exclusive_features"]

    def test_the_site_patch_replaces_the_exact_stock_test(self):
        # The hut site, the food site and the dispatcher site for the Builders
        # and Healers Work First addendum (tests/test_work_first.py).
        self.assertEqual([p["offset"] for p in self.overlay["hook_patches"]], ["0x5B39E", "0x5C229", "0x5AF00"])
        patch = self.overlay["hook_patches"][0]
        self.assertEqual(int(patch["offset"], 16), 0x45B39E - 0x400000)
        self.assertEqual(_stock("vv3", 0x45B39E, 8), bytes.fromhex(patch["before"]))
        self.assertEqual(bytes.fromhex(patch["before"]), bytes.fromhex("3BFB0F849C030000"))
        after = bytes.fromhex(patch["after"])
        rel, = struct.unpack("<i", after[1:5])
        self.assertEqual(0x45B39E + 5 + rel, int(self.overlay["page_virtual_address"], 16))
        self.assertEqual(after[5:], b"\x90\x90\x90")

    def test_the_stub_resolves_the_companion_and_takes_the_stock_paths(self):
        page = bytes.fromhex(self.overlay["append_bytes"])
        base = int(self.overlay["page_virtual_address"], 16)
        self.assertEqual(base, 0x6DF800, "after the parentage overlay at 0x6DF400")
        self.assertEqual(self.overlay["overlay_offset"], "0xCB800")
        self.assertIn(b"VVFP Fix Huts.dll\0", page)
        self.assertIn(b"VvfpFixHutsDecide\0", page)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        text = "\n".join(f"{i.mnemonic} {i.op_str}" for i in md.disasm(page[:0x80], base))
        self.assertIn("cmp edi, ebx", text)
        self.assertIn("jne 0x45b3a6", text, "an option exists: the stock path")
        self.assertIn("call dword ptr [0x47c074]", text, "GetModuleHandleA")
        self.assertIn("call dword ptr [0x47c124]", text, "LoadLibraryA")
        self.assertIn("call dword ptr [0x47c128]", text, "GetProcAddress")
        self.assertIn("push 3", text)
        self.assertIn("je 0x45b742", text, "nothing to do: the stock path")
        self.assertIn("jmp 0x45b5f0", text, "a job was started: the stock epilogue")
        self.assertIn("mov dword ptr [0x6e0ff8], eax", text, "the resolved export, cached in .vv3md")
        # The stock import table really has those slots.
        pe = pefile.PE(str(STOCK["vv3"]), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        imports = {i.name: i.address for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports if i.name}
        self.assertEqual(imports[b"GetModuleHandleA"], 0x47C074)
        self.assertEqual(imports[b"LoadLibraryA"], 0x47C124)
        self.assertEqual(imports[b"GetProcAddress"], 0x47C128)

    def test_the_cache_slot_is_unclaimed(self):
        """0x6E0FF8 in .vv3md: Origins' and parentage's pages reference nothing there."""
        for path, key in ((ROOT / "data" / "vv3_origins_feature.json", None),
                          (ROOT / "data" / "vv3_parentage_feature.json", "vv3_write_parentage_log")):
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
                        self.assertFalse(0x6E0FF0 <= v < 0x6E1000, f"{path.name} references {v:#x}")

    def test_the_composed_image_renders_in_every_mode_with_the_stub_in_place(self):
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv3")
        page = bytes.fromhex(self.overlay["append_bytes"])[:0x400]
        for mode in vfp.load_patch_modes():
            rendered, applied = vfp.render_patched_bytes(
                STOCK["vv3"], build, mode.id,
                ["vv3_enable_origins_exclusive_features", "vv3_write_parentage_log",
                 "vv3_builders_fix_huts"])
            self.assertEqual(bytes(rendered[0xCB800:0xCBC00]), page, mode.id)
            site = bytes(rendered[0x5B39E:0x5B3A6])
            self.assertEqual(site, bytes.fromhex(self.overlay["hook_patches"][0]["after"]), mode.id)
            owners = {edit["owner"] for edit in applied}
            self.assertIn("feature:vv3_builders_fix_huts", owners)


class RowTests(unittest.TestCase):
    def test_the_rows_are_default_off_registered_bundled_and_pin_the_dll(self):
        import vv_fun_patcher as vfp
        from vv_fun_patcher_gui import default_fun_patch_selection
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        ids = {p.id: p for p in vfp.load_public_fun_patches()}
        for game in STOCK:
            pid = f"{game}_builders_fix_huts"
            self.assertIn(pid, ids)
            self.assertTrue(default_fun_patch_selection(pid), "the owner: selectable by default")
            m = json.loads(MANIFESTS[game].read_text(encoding="utf-8"))
            self.assertEqual(m["dependencies"], [f"{game}_enable_origins_exclusive_features"])
            self.assertEqual([c["sha256"] for c in m["companion_files"]], [sha])
            self.assertIn("**Runs on the Origins-exclusive base, which the patcher installs automatically with it**", m["description"])
            self.assertIn("adds the Origins Upgrades buttons", m["description"])
            self.assertNotIn("Enable Origins-Exclusive Features", m["description"])
            if game != "vv3":
                self.assertEqual(m["patches"], [])
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("assets/fix_huts/VVFP Fix Huts.dll", release)
        for game in STOCK:
            self.assertIn(f"data/{game}_builders_fix_huts_feature.json", release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme.count("**Builders Fix Huts When Idle**"), 5)

    def test_the_four_per_frame_companions_carry_the_loader_bridge(self):
        for path, call in (
            (ROOT / "native/vv1_origins_icons/vv1_origins_icons.c", "vvfp_fix_huts_bridge(1);"),
            (ROOT / "native/vv4_origins_icons/vv4_origins_icons.c", "install(4)"),
            (ROOT / "native/vv5_task9_origins/vv5_task9_origins.c", "install(5)"),
        ):
            source = path.read_text(encoding="utf-8")
            self.assertIn('"VVFP Fix Huts.dll"', source, path.name)
            self.assertIn('GetProcAddress(companion, "VvfpFixHutsInstall")', source, path.name)
            self.assertIn(call, source, path.name)
        # The Lost Children's companion compiles A New Home's source in and
        # calls the shared bridge with its own game id.
        vv2 = (ROOT / "native/vv2_origins_icons/vv2_origins_icons.c").read_text(encoding="utf-8")
        self.assertIn('#include "../vv1_origins_icons/vv1_origins_icons.c"', vv2)
        self.assertIn("vvfp_fix_huts_bridge(2);", vv2)
        for dll in (ROOT / "assets/origins/VVFP VV1 Origins Icons.dll",
                    ROOT / "assets/origins/VVFP VV2 Origins Icons.dll",
                    ROOT / "assets/origins/VVFP VV4 Origins Icons.dll",
                    ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"):
            self.assertIn(b"VVFP Fix Huts.dll", dll.read_bytes(), dll.name)


if __name__ == "__main__":
    unittest.main()
