"""Improved Pathfinding (A New Home, The Lost Children): the companion, its two
rows, the detour sites and the loader bridges.

The routing itself runs at runtime in native/vvfp_pathfinding/
pathfinding_harness.c (32-bit, loads the TEST build, synthetic grids laid out
as the games keep theirs).  This file pins what Python can check: both rows
pin the shipped DLL and change no executable bytes; each detour site's stock
bytes are exactly what the stock executable holds there, so the DLL's
verify-then-install can succeed on the real game and nothing else could match
by accident; the DLL exports what the bridges and the harness call; both
Origins companions carry the bridge and it is compiled into the shipped DLLs;
the rows are registered with the patcher, bundled into the release, and
described; and the harness passes where the 32-bit toolchain exists.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "pathfinding" / "VVFP Improved Pathfinding.dll"
SOURCE = ROOT / "native" / "vvfp_pathfinding" / "vvfp_pathfinding.c"
DEF = ROOT / "native" / "vvfp_pathfinding" / "vvfp_pathfinding.def"
# The probes the harness drives exist only in the TEST build (VVFP_TEST).
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Improved Pathfinding.test.dll"
TEST_DEF = ROOT / "native" / "vvfp_pathfinding" / "vvfp_pathfinding_test.def"
# tests/test_dlls/ is export-ignore: the release source archive carries no test
# build, so there the tests that drive one skip instead of failing.
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
HARNESS_BUILD = ROOT / "scripts" / "build_pathfinding_harness.ps1"
MANIFESTS = {
    "vv1": ROOT / "data" / "vv1_improved_pathfinding_feature.json",
    "vv2": ROOT / "data" / "vv2_improved_pathfinding_feature.json",
}
STOCK = {
    "vv1": ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
    "vv2": ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe",
}
ORIGINS_C = {
    "vv1": ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c",
    "vv2": ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c",
}
ORIGINS_DLL = {
    "vv1": ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll",
    "vv2": ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll",
}
ORIGINS_MANIFEST = {
    "vv1": ROOT / "data" / "vv1_origins_feature.json",
    "vv2": ROOT / "data" / "vv2_origins_feature.json",
}
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)


def _exports(path: Path) -> set[str]:
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
    return {e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}


def _stock_bytes(game: str, va: int, length: int) -> bytes:
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    data = STOCK[game].read_bytes()
    offset = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
    return data[offset:offset + length]


class RowsAndDllTests(unittest.TestCase):
    def test_both_rows_pin_the_shipped_dll_and_change_no_bytes(self):
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for game, path in MANIFESTS.items():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["id"], f"{game}_improved_pathfinding")
            self.assertEqual(manifest["game_id"], game)
            self.assertEqual(manifest["name"], "Improved Pathfinding")
            self.assertTrue(manifest["enabled"])
            self.assertEqual(manifest["patches"], [], "the row changes no executable bytes")
            pinned = {f["destination"]: f["sha256"].upper() for f in manifest["companion_files"]}
            self.assertEqual(pinned, {"VVFP Improved Pathfinding.dll": sha}, game)
            self.assertEqual(manifest["dependencies"], [f"{game}_enable_origins_exclusive_features"])

    def test_the_description_is_the_owners_and_states_its_dependency_in_bold(self):
        for path in MANIFESTS.values():
            description = json.loads(path.read_text(encoding="utf-8"))["description"]
            self.assertIn("Updates the pathfinding to resemble VV3-VV5.", description)
            self.assertIn("Hopefully villagers don't get stuck behind things anymore!", description)
            self.assertIn("**Requires Enable Origins-Exclusive Features**", description)

    def test_each_detour_sites_stock_bytes_are_what_the_stock_executable_holds(self):
        """The DLL installs only after matching these bytes in the running
        game, so they must be the stock bytes -- and long enough to be a
        whole instruction sequence of at least the five a jmp overwrites."""
        source = SOURCE.read_text(encoding="utf-8")
        for game, path in MANIFESTS.items():
            for site in json.loads(path.read_text(encoding="utf-8"))["runtime_detours"]:
                va = int(site["va"], 16)
                stock = bytes.fromhex(site["stock_bytes"])
                self.assertGreaterEqual(len(stock), 5, site)
                self.assertEqual(_stock_bytes(game, va, len(stock)), stock, f"{game} {site['va']}")
                # And the DLL carries the same bytes for the same site.
                self.assertIn(f"0x{va:X}u", source, site["va"])
                spelled = ", ".join(f"0x{b:02X}" for b in stock)
                self.assertIn(spelled, source, f"the DLL's stock bytes for {site['va']}")

    def test_the_sites_are_the_routines_the_decompilation_identified(self):
        """A New Home's blocked-walk handler is the only caller of the
        sideways nudge and of the give-up that clears the queue; The Lost
        Children's flood and descent are the two routines the follower uses.
        Pinned by their first instructions, which are distinctive."""
        self.assertEqual(_stock_bytes("vv1", 0x43DFC0, 7), bytes.fromhex("5153558B6C2410"))
        self.assertEqual(_stock_bytes("vv2", 0x41A700, 10), bytes.fromhex("B810B90100E846EB0400"),
                         "mov eax, 1B910h; call __chkstk: the 0x1B910-byte field on the stack")
        self.assertEqual(_stock_bytes("vv2", 0x41A9B0, 5), bytes.fromhex("B867666666"),
                         "the divide-by-ten constant that begins the descent")

    def test_the_dll_exports_what_the_bridges_and_the_harness_call(self):
        """The bridges call VvfpPathfindingInstall in the shipped DLL; the
        harness drives the probes, which only the TEST build carries."""
        exports = _exports(DLL)
        self.assertIn("VvfpPathfindingInstall", exports)
        self.assertFalse({n for n in exports if "Probe" in n or "Stats" in n},
                         "the shipped DLL exports no probe or counter")
        definition = DEF.read_text(encoding="utf-8")
        self.assertIn("VvfpPathfindingInstall=_VvfpPathfindingInstall@4", definition)
        self.assertNotIn("Probe", definition)
        self.assertIn("VvfpPathfindingProbeVv1=", TEST_DEF.read_text(encoding="utf-8"))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_test_build_exports_what_the_harness_calls(self):
        test_exports = _exports(TEST_DLL)
        for name in ("VvfpPathfindingInstall", "VvfpPathfindingProbeVv1",
                     "VvfpPathfindingProbeVv1Route", "VvfpPathfindingProbeVv2Flood",
                     "VvfpPathfindingProbeVv2Next", "VvfpPathfindingProbeSite",
                     "VvfpPathfindingProbeSiteBytes", "VvfpPathfindingStats"):
            self.assertIn(name, test_exports)

    def test_the_dll_verifies_before_it_writes_and_never_leaves_a_writable_code_page(self):
        source = SOURCE.read_text(encoding="utf-8")
        prepare = source[source.index("static int prepare_detour("):]
        prepare = prepare[:prepare.index("\n}")]
        self.assertLess(prepare.index("stock_bytes_present("), prepare.index("VirtualAlloc("))
        self.assertIn("PAGE_EXECUTE_READ, &old", prepare, "the trampoline page is made read-execute")
        write = source[source.index("static int write_site("):]
        write = write[:write.index("\n}")]
        self.assertIn("VirtualProtect(site, (SIZE_T)d->length, old, &old);", write,
                      "the site's protection is put back after the write")
        self.assertIn("FlushInstructionCache(", write)
        # Codex (#454, P2): all sites are prepared before any is written, and
        # a write that fails part-way restores the sites already written.
        install = source[source.index("__stdcall VvfpPathfindingInstall("):]
        install = install[:install.index("\n}")]
        self.assertLess(install.index("prepare_detour(&set[i])"), install.index("install_detour(&set[i])"))
        self.assertIn("restore_detour(&set[i]);", install)
        restore = source[source.index("static void restore_detour("):]
        restore = restore[:restore.index("\n}")]
        # Codex (#455, P2): a site whose stock bytes could not be put back is
        # still detoured, so its trampoline page must not be freed.
        self.assertIn("if (write_site(d, d->stock)) {", restore)
        self.assertIn("for (i = failed; i < count; ++i) {", install,
                      "only the never-written sites' pages are discarded unconditionally")
        # Nothing runs from DllMain.
        dllmain = source[source.index("BOOL WINAPI DllMain("):]
        self.assertIn("return TRUE;", dllmain)
        self.assertNotIn("Install", dllmain)

    def test_a_new_home_ends_like_the_secret_city_and_never_nudges(self):
        """The owner: exactly VV3.  A route is always followed while one
        exists (a hut or the side of anything is never "unreachable"); with
        no route at all -- the goal on an obstacle or walled off -- the action
        ends at once through the game's own queue clear (0x439470), the call
        The Secret City's 0x460F70 corresponds to, never through fifteen
        nudges first.  The stock handler runs only with no village or grid."""
        source = SOURCE.read_text(encoding="utf-8")
        stub = source[source.index("vv1_blocked_stub(void) {"):]
        stub = stub[:stub.index("\n}")]
        self.assertIn("jmp dword ptr [vv1_trampoline]", stub)
        self.assertIn("ret 8", stub, "thiscall with two stack arguments")
        handler = source[source.index("static int __cdecl vv1_blocked("):]
        handler = handler[:handler.index("\n}")]
        self.assertEqual(handler.count("return 0;"), 2, "only a missing village or grid falls through")
        self.assertIn("((vv1_give_up_t)VV1_GIVE_UP)(village, NULL, idx);", handler)
        self.assertIn("#define VV1_GIVE_UP 0x439470u", source)
        self.assertNotIn("GUARD_LIMIT", source,
                         "no retry guard ever hands a routed villager back to the stock handler")
        corner = source[source.index("static int vv1_route("):]
        corner = corner[:corner.index("\n}")]
        self.assertIn("return CORNER_NONE;             /* a goal on an obstacle: refused", corner)
        # The whole route is queued at once, last corner first, within the
        # queue's free entries, so the villager never meets the obstacle again.
        self.assertIn("for (i = count - 1; i >= 0; --i) {", handler)
        self.assertIn("room = VV1_QUEUE_ENTRIES - 1 - occupied;", handler)
        self.assertEqual(_stock_bytes("vv1", 0x439470, 7), bytes.fromhex("8B44240469C0D8"),
                         "0x439470 is the record-stride routine the stock handler calls to give up")
        flood = source[source.index("static int __cdecl vv2_flood("):]
        flood = flood[:flood.index("\n}")]
        self.assertIn("if (!vv2_walkable(grid, gx, gy, allow24)) {", flood)
        self.assertIn("return 0;", flood[flood.index("if (!vv2_walkable(grid, gx, gy, allow24)) {"):],
                      "The Lost Children keeps its (and The Secret City's) refusal of a goal on an obstacle")


class BridgeTests(unittest.TestCase):
    def test_both_origins_companions_load_the_dll_by_full_path_and_install_for_their_game(self):
        vv1 = ORIGINS_C["vv1"].read_text(encoding="utf-8")
        vv2 = ORIGINS_C["vv2"].read_text(encoding="utf-8")
        bridge = vv1[vv1.index("static void vvfp_pathfinding_bridge(int game_id)"):]
        bridge = bridge[:bridge.index("\n}")]
        self.assertIn("GetModuleFileNameA(NULL, path, MAX_PATH)", bridge)
        self.assertIn('lstrcpyA(slash + 1, "VVFP Improved Pathfinding.dll");', bridge)
        self.assertIn("LoadLibraryA(path)", bridge, "by full path, never a bare name")
        self.assertIn('GetProcAddress(companion, "VvfpPathfindingInstall")', bridge)
        self.assertIn("install(game_id)", bridge)
        # Called from each game's per-frame tick, outside DllMain.
        tick = vv1[vv1.index("__stdcall Vv1MaskTick(void) {"):]
        self.assertIn("vvfp_pathfinding_bridge(1);", tick[:600])
        self.assertIn('#include "../vv1_origins_icons/vv1_origins_icons.c"', vv2)
        sweep = vv2[vv2.index("__stdcall Vv2MaskSweep(unsigned char *base) {"):]
        self.assertIn("vvfp_pathfinding_bridge(2);", sweep[:300])
        self.assertLess(sweep.index("vvfp_pathfinding_bridge(2);"), sweep.index("return;"),
                        "before the sweep's own early returns, so a frame with no village still installs")

    def test_the_shipped_origins_dlls_carry_the_bridge_and_are_pinned(self):
        for game in ("vv1", "vv2"):
            data = ORIGINS_DLL[game].read_bytes()
            self.assertIn(b"VVFP Improved Pathfinding.dll", data, game)
            self.assertIn(b"VvfpPathfindingInstall", data, game)
            manifest = json.loads(ORIGINS_MANIFEST[game].read_text(encoding="utf-8"))
            pinned = [f["sha256"].upper() for f in manifest["companion_files"]
                      if f["destination"] == ORIGINS_DLL[game].name]
            self.assertEqual(pinned, [hashlib.sha256(data).hexdigest().upper()], game)


class RegistrationTests(unittest.TestCase):
    def test_the_rows_are_registered_bundled_and_documented(self):
        patcher = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertIn('ROOT / "data" / "vv1_improved_pathfinding_feature.json"', patcher)
        self.assertIn('ROOT / "data" / "vv2_improved_pathfinding_feature.json"', patcher)
        self.assertIn("for feature_path in (IMPROVED_PATHFINDING_FEATURE_PATHS + WATERING_BUILDS_FEATURE_PATHS", patcher)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("assets/pathfinding/VVFP Improved Pathfinding.dll", release)
        self.assertIn("data/vv1_improved_pathfinding_feature.json", release)
        self.assertIn("data/vv2_improved_pathfinding_feature.json", release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme.count("**Improved Pathfinding**"), 2, "one README row per game")
        self.assertTrue((ROOT / "docs" / "improved-pathfinding.md").is_file())

    def test_the_patcher_lists_both_rows(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher as vfp
        ids = {p.id: p for p in vfp.load_public_fun_patches()}
        for game in ("vv1", "vv2"):
            self.assertIn(f"{game}_improved_pathfinding", ids)
            self.assertEqual(ids[f"{game}_improved_pathfinding"].game_id, game)


class HarnessTests(unittest.TestCase):
    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_harness_passes_against_the_test_build(self):
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(HARNESS_BUILD)],
            capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)


if __name__ == "__main__":
    unittest.main()
