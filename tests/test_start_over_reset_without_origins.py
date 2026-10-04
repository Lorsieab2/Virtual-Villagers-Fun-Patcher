"""Start Over resets the logs even in a build without Origins, in all five.

Start Over keeps the tribe name and the save slot, so a per-slot log or .dat
file that survives it is appended to by the next village. The tribe-delete
hook -- the save-slot menu's own call to deleteSave -- routes the delete
through VVFP Save Reset.dll, which removes those files.

Only Origins carried that hook. A build with the Births and Conceptions log
or the Village Statistics log and WITHOUT Origins left the hook site stock in
VV1, VV3, VV4 and VV5 (VV2's parentage log depends on Origins, so there only
the statistics-only build), so Start Over never reached the DLL. Measured on
origin/main: 42 of the 120 {origins, parentage, statistics} x 5 games x 3
modes renders were file-owning builds with a stock hook.

The patcher now hands the reset to exactly one selected file-owning feature
when nothing selected writes the hook itself. These tests hold that rule and
the bytes it produces:

  * which feature carries it for every subset, and that it is never two;
  * the block is derived from the game's own Origins block -- rebuilt from
    the template it must equal Origins' bytes -- and VV5, whose Origins cave
    exists in the stock image, is byte-identical to Origins at hook and block;
  * rendered builds call a block in mapped executable code that pushes this
    game's id, names the Save Reset DLL and export, and falls through to the
    stock hook's own call target, with the executable-name crash guard still
    applied in VV1-VV3;
  * the Save Reset DLL is actually written beside a statistics-only build.
"""
from __future__ import annotations

import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

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
# Measured in the five stock executables and in the Origins-only builds that
# test_origins_only_build_sweeps_the_slot proves: the menu's delete call and
# the deleteSave thunk it calls.
HOOK = {"vv1": 0x13E07, "vv2": 0x14E77, "vv3": 0x1B5D3, "vv4": 0x18CD5, "vv5": 0x193F5}
THUNK = {"vv1": 0x41BFF0, "vv2": 0x424C70, "vv3": 0x427E00, "vv4": 0x41F1D0, "vv5": 0x424690}
HAVE_STOCK = all((STOCK / name).is_file() for name in EXE.values())
DLL = "VVFP Save Reset.dll"
DLL_NAME = b"VVFP Save Reset.dll\x00"
EXPORT_NAME = b"ResetDeletedTribe\x00"


def _ids(game: str, subset: str) -> list[str]:
    public = {
        "origins": f"{game}_origins_village_wide_upgrades",
        "parentage": f"{game}_write_parentage_log",
        "statistics": f"{game}_write_village_statistics",
    }
    return [public[item] for item in subset.split("+") if item]


def _selected(game: str, subset: str) -> list:
    build = next(b for b in vp.load_builds() if b.id == game)
    return vp._attach_start_over_reset(
        game, vp._selected_fun_patches(build, _ids(game, subset))
    )


def _writers_of_hook(game: str, features: list) -> list[str]:
    return [
        feature.id
        for feature in features
        if vp._feature_writes_offset(feature, HOOK[game])
    ]


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


def _expected_writer(game: str, subset: str) -> str | None:
    parts = set(filter(None, subset.split("+")))
    # VV2's parentage log depends on Origins, which is resolved in.
    if "origins" in parts or (game == "vv2" and "parentage" in parts):
        return f"{game}_enable_origins_exclusive_features"
    if "parentage" in parts:
        return f"{game}_write_parentage_log"
    if "statistics" in parts:
        return f"{game}_write_village_statistics"
    return None


class CarrierSelectionTests(unittest.TestCase):
    def test_exactly_one_feature_writes_the_hook_when_one_is_needed(self) -> None:
        for game in EXE:
            for subset in SUBSETS:
                with self.subTest(game=game, subset=subset or "none"):
                    features = _selected(game, subset)
                    expected = _expected_writer(game, subset)
                    self.assertEqual(
                        _writers_of_hook(game, features),
                        [expected] if expected else [],
                    )

    def test_the_carrier_ships_the_save_reset_companion(self) -> None:
        for game in EXE:
            for subset in SUBSETS:
                with self.subTest(game=game, subset=subset or "none"):
                    features = _selected(game, subset)
                    shipped = [
                        item
                        for feature in features
                        if vp._feature_writes_offset(feature, HOOK[game])
                        for item in feature.raw.get("companion_files", [])
                        if item.get("destination") == DLL
                    ]
                    expected = 1 if _expected_writer(game, subset) else 0
                    self.assertEqual(len(shipped), expected)
                    for item in shipped:
                        self.assertEqual(
                            item["sha256"].upper(),
                            vp.sha256(ROOT / item["source"]),
                        )

    def test_attaching_twice_changes_nothing(self) -> None:
        for game in EXE:
            with self.subTest(game=game):
                once = _selected(game, "statistics")
                twice = vp._attach_start_over_reset(game, once)
                self.assertEqual([f.raw for f in once], [f.raw for f in twice])

    def test_the_catalog_records_are_not_modified(self) -> None:
        """The carrier is a copy; the catalog's own record keeps its bytes."""
        for game in EXE:
            with self.subTest(game=game):
                _selected(game, "statistics")
                record = next(
                    p for p in vp.load_fun_patches()
                    if p.id == f"{game}_write_village_statistics"
                )
                self.assertFalse(vp._feature_writes_offset(record, HOOK[game]))
                self.assertNotIn("_start_over_reset_carrier", record.raw)


class DerivedFromOriginsTests(unittest.TestCase):
    def _origins_block(self, game: str) -> tuple[int, bytes]:
        origins = next(
            p for p in vp.load_fun_patches()
            if p.id == f"{game}_enable_origins_exclusive_features"
        )
        hook = next(
            p for p in origins.raw["patches"] if int(p["offset"], 0) == HOOK[game]
        )
        after = bytes.fromhex(hook["after"])
        stub_va = 0x400000 + HOOK[game] + 5 + struct.unpack_from("<i", after, 1)[0]
        return stub_va - 0x28, after

    def test_the_template_rebuilds_every_origins_block_exactly(self) -> None:
        """The carrier's bytes come from the same template, so the template
        must reproduce each game's Origins block byte for byte."""
        for game in EXE:
            with self.subTest(game=game):
                patches, _companion = vp._start_over_reset_from_origins(game)
                block = bytes.fromhex(
                    next(p for p in patches if len(p["after"]) == 0x62 * 2)["after"]
                )
                self.assertEqual(block[:0x14], DLL_NAME)
                self.assertEqual(block[0x14 : 0x14 + len(EXPORT_NAME)], EXPORT_NAME)
                cave = vp.START_OVER_RESET_CAVE[game]
                code = 0x28
                iats = [struct.unpack_from("<I", block, code + at)[0] for at in (8, 0x17, 0x27)]
                self.assertEqual(
                    vp._start_over_reset_block(cave["va"], *iats, int(game[2]), THUNK[game]),
                    block,
                )
                self.assertEqual(struct.unpack_from("<I", block, code + 2)[0], cave["va"])
                self.assertEqual(block[code + 0x31], int(game[2]))
                jump_end = cave["va"] + code + 0x3A
                self.assertEqual(
                    jump_end + struct.unpack_from("<i", block, code + 0x36)[0],
                    THUNK[game],
                )

    def test_a_drifted_origins_block_is_refused(self) -> None:
        """The carrier copies nothing it has not matched against the template.

        VV4's Origins block is a plain patch at 0xCC8E8; flip its game-id byte,
        then its tail jump, and the derivation must refuse both.
        """
        real = vp.load_fun_patches
        for label, at in (("game id", 0x28 + 0x31), ("tail jump", 0x28 + 0x36)):
            with self.subTest(drift=label):
                def drifted(*args, _at=at, **kwargs):
                    out = []
                    for record in real(*args, **kwargs):
                        if record.id == "vv4_enable_origins_exclusive_features":
                            raw = dict(record.raw)
                            patches = []
                            for patch in raw["patches"]:
                                if int(patch["offset"], 0) == 0xCC8E8:
                                    after = bytearray(bytes.fromhex(patch["after"]))
                                    after[_at] ^= 0x01
                                    patch = dict(patch, after=after.hex().upper())
                                patches.append(patch)
                            raw["patches"] = patches
                            record = vp.Record(raw)
                        out.append(record)
                    return out

                vp.load_fun_patches = drifted
                try:
                    with self.assertRaises(vp.PatcherError):
                        vp._start_over_reset_from_origins("vv4")
                finally:
                    vp.load_fun_patches = real

    def test_vv5_is_byte_identical_to_origins(self) -> None:
        patches, _companion = vp._start_over_reset_from_origins("vv5")
        origins = next(
            p for p in vp.load_fun_patches()
            if p.id == "vv5_enable_origins_exclusive_features"
        )
        by_offset = {int(p["offset"], 0): p for p in origins.raw["patches"]}
        for patch in patches:
            with self.subTest(offset=patch["offset"]):
                theirs = by_offset[int(patch["offset"], 0)]
                self.assertEqual(patch["after"].upper(), theirs["after"].upper())
                self.assertEqual(patch["before"].upper(), theirs["before"].upper())

    def test_vv2_copies_origins_own_shr_mapping_patches(self) -> None:
        patches, _companion = vp._start_over_reset_from_origins("vv2")
        origins = next(
            p for p in vp.load_fun_patches()
            if p.id == "vv2_enable_origins_exclusive_features"
        )
        by_offset = {int(p["offset"], 0): p for p in origins.raw["patches"]}
        headers = [p for p in patches if int(p["offset"], 0) < 0x400]
        self.assertEqual([int(p["offset"], 0) for p in headers], [0x268, 0x284])
        for patch in headers:
            theirs = by_offset[int(patch["offset"], 0)]
            self.assertEqual(patch["after"].upper(), theirs["after"].upper())


def _sections(data: bytes):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    for index in range(count):
        base = pe + 24 + opt + 40 * index
        vsz, va, rsz, ro = struct.unpack_from("<IIII", data, base + 8)
        yield vsz, va, rsz, ro, struct.unpack_from("<I", data, base + 36)[0]


def _va_to_mapped_exec_offset(data: bytes, va: int, length: int) -> int | None:
    for vsz, sva, rsz, ro, chars in _sections(data):
        start = 0x400000 + sva
        mapped = min((vsz + 0xFFF) & ~0xFFF, rsz)
        if start <= va and va + length <= start + mapped and chars & 0x20000000:
            return ro + va - start
    return None


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class PlacementGuardTests(unittest.TestCase):
    """Render refuses a block the loader would not map as executable code."""

    def _check(self, game: str, cave: dict) -> None:
        saved = vp.START_OVER_RESET_CAVE[game]
        vp.START_OVER_RESET_CAVE[game] = cave
        try:
            vp._validate_start_over_reset_placement((STOCK / EXE[game]).read_bytes(), game)
        finally:
            vp.START_OVER_RESET_CAVE[game] = saved

    def test_every_shipped_placement_passes(self) -> None:
        for game in EXE:
            with self.subTest(game=game):
                self._check(game, vp.START_OVER_RESET_CAVE[game])

    def test_vv2_shr_without_its_mapping_patches_is_refused(self) -> None:
        with self.assertRaises(vp.PatcherError):
            self._check("vv2", {"file": 0x9A010, "va": 0x49C010, "headers": ()})

    def test_a_non_executable_section_is_refused(self) -> None:
        # VV4 .rdata tail: mapped, readable, not executable.
        with self.assertRaises(vp.PatcherError):
            self._check("vv4", {"file": 0xB7800, "va": 0x4B7800, "headers": ()})

    def test_a_wrong_assembled_address_is_refused(self) -> None:
        with self.assertRaises(vp.PatcherError):
            self._check("vv3", {"file": 0x7B800, "va": 0x47B810, "headers": ()})

    def test_render_itself_refuses_a_bad_placement(self) -> None:
        saved = vp.START_OVER_RESET_CAVE["vv2"]
        vp.START_OVER_RESET_CAVE["vv2"] = {"file": 0x9A010, "va": 0x49C010, "headers": ()}
        try:
            build = next(b for b in vp.load_builds() if b.id == "vv2")
            with self.assertRaises(vp.PatcherError):
                vp.render_patched_bytes(
                    STOCK / EXE["vv2"], build, "collection_progression",
                    _ids("vv2", "statistics"),
                )
        finally:
            vp.START_OVER_RESET_CAVE["vv2"] = saved

    def test_past_the_mapped_page_is_refused(self) -> None:
        # VV1 .text maps to 0x57000; raw data continues nowhere past it.
        with self.assertRaises(vp.PatcherError):
            self._check("vv1", {"file": 0x56FC0, "va": 0x456FC0, "headers": ()})


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class RenderedBuildTests(unittest.TestCase):
    """Real renders: the hook reaches a working block, exactly once."""

    rendered: dict[tuple[str, str], bytes] = {}

    @classmethod
    def setUpClass(cls) -> None:
        cls.rendered = {}
        for game in EXE:
            build = next(b for b in vp.load_builds() if b.id == game)
            for subset in ("parentage", "statistics", "origins+statistics", ""):
                data, applied = vp.render_patched_bytes(
                    STOCK / EXE[game], build, "collection_progression", _ids(game, subset)
                )
                if game not in vp.NAME_CRASH_IMMUNITY_EXEMPT_BUILD_IDS:
                    # Publication requires it; it must still find its own cave.
                    vp._require_name_crash_immunity(data, build.input_name, applied)
                cls.rendered[(game, subset)] = bytes(data)

    def test_the_hook_calls_one_working_block(self) -> None:
        stock = {g: (STOCK / EXE[g]).read_bytes() for g in EXE}
        for (game, subset), data in sorted(self.rendered.items()):
            with self.subTest(game=game, subset=subset or "none"):
                hook = HOOK[game]
                blocks = []
                at = data.find(DLL_NAME)
                while at != -1:
                    # The main-menu Start Over stub carries the same two names
                    # (tests/test_main_menu_start_over_reset.py); the
                    # tribe-delete block is the one that pushes edi, the raw
                    # slot, at code +0x2F.
                    if (
                        data[at + 0x14 : at + 0x14 + len(EXPORT_NAME)] == EXPORT_NAME
                        and data[at + 0x28 + 0x2F : at + 0x28 + 0x31] == b"\x57\x6a"
                    ):
                        blocks.append(at)
                    at = data.find(DLL_NAME, at + 1)
                if not subset:
                    self.assertEqual(data[hook : hook + 5], stock[game][hook : hook + 5])
                    self.assertEqual(blocks, [])
                    continue
                self.assertEqual(len(blocks), 1, "the reset block must exist exactly once")
                self.assertEqual(data[hook], 0xE8)
                stub_va = 0x400000 + hook + 5 + struct.unpack_from("<i", data, hook + 1)[0]
                block_off = _va_to_mapped_exec_offset(data, stub_va - 0x28, 0x62)
                self.assertIsNotNone(
                    block_off, "the hook does not land in mapped executable code"
                )
                self.assertEqual(block_off, blocks[0])
                block = data[block_off : block_off + 0x62]
                iats = [struct.unpack_from("<I", block, 0x28 + at)[0] for at in (8, 0x17, 0x27)]
                self.assertEqual(
                    vp._start_over_reset_block(
                        stub_va - 0x28, *iats, int(game[2]), THUNK[game]
                    ),
                    block,
                )
                stock_target = (
                    0x400000 + hook + 5
                    + struct.unpack_from("<i", stock[game], hook + 1)[0]
                )
                self.assertEqual(stock_target, THUNK[game])

    def test_vv5_without_origins_matches_the_origins_build(self) -> None:
        with_origins = self.rendered[("vv5", "origins+statistics")]
        for subset in ("parentage", "statistics"):
            data = self.rendered[("vv5", subset)]
            with self.subTest(subset=subset):
                self.assertEqual(data[0x193F5:0x193FA], with_origins[0x193F5:0x193FA])
                self.assertEqual(data[0x94730:0x94792], with_origins[0x94730:0x94792])


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class RemovalKeepsTheRuleTests(unittest.TestCase):
    """Removing one feature leaves exactly the image the rest would render.

    Removal is handed one feature and reads the rest back from the image, so
    it must hand the reset on, keep it, or take it away just as rendering the
    remaining selection would.
    """

    CASES = (
        ("parentage", "parentage"),
        ("statistics", "statistics"),
        ("parentage+statistics", "parentage"),
        ("parentage+statistics", "statistics"),
        ("origins+statistics", "origins"),
        ("origins+statistics", "statistics"),
        ("origins+parentage", "parentage"),
    )

    def test_removal_round_trips(self) -> None:
        mode = "collection_progression"
        for game in EXE:
            build = next(b for b in vp.load_builds() if b.id == game)
            for installed_subset, remove in self.CASES:
                if game == "vv2" and "parentage" in installed_subset:
                    continue  # VV2's parentage log depends on Origins
                with self.subTest(game=game, installed=installed_subset, remove=remove):
                    installed_ids = _ids(game, installed_subset)
                    feature_id = _ids(game, remove)[0]
                    if remove == "origins":
                        feature_id = f"{game}_enable_origins_exclusive_features"
                    data, _ = vp.render_patched_bytes(
                        STOCK / EXE[game], build, mode, installed_ids
                    )
                    # The selection as resolved, minus only the one removed.
                    resolved = [
                        f.id for f in vp._selected_fun_patches(build, installed_ids)
                    ]
                    remaining = [
                        i for i in resolved
                        if i != feature_id
                        and not (remove == "origins" and i.endswith("_origins_village_wide_upgrades"))
                    ]
                    if remove == "origins":
                        wide = f"{game}_origins_village_wide_upgrades"
                        vp._remove_feature_bytes(data, vp.get_fun_patch(wide), mode)
                    vp._remove_feature_bytes(data, vp.get_fun_patch(feature_id), mode)
                    expected, _ = vp.render_patched_bytes(
                        STOCK / EXE[game], build, mode, remaining
                    )
                    self.assertEqual(bytes(data), bytes(expected))

    def test_the_save_reset_dll_leaves_with_the_last_hook(self) -> None:
        mode = "collection_progression"
        game = "vv4"
        build = next(b for b in vp.load_builds() if b.id == game)

        def folder_for(features) -> pathlib.Path:
            folder = pathlib.Path(tempfile.mkdtemp(prefix="vv4_reset_rm_"))
            for feature in features:
                for item in feature.raw.get("companion_files", []):
                    shutil.copy2(ROOT / item["source"], folder / item["destination"])
            return folder

        for installed_subset, remove, dll_stays in (
            ("statistics", "statistics", False),
            ("parentage+statistics", "parentage", True),
            ("parentage", "parentage", False),
        ):
            with self.subTest(installed=installed_subset, remove=remove):
                ids = _ids(game, installed_subset)
                features = vp._attach_start_over_reset(
                    game, vp._selected_fun_patches(build, ids)
                )
                data, _ = vp.render_patched_bytes(STOCK / EXE[game], build, mode, ids)
                folder = folder_for(features)
                try:
                    vp._remove_feature_bytes(
                        data, vp.get_fun_patch(_ids(game, remove)[0]), mode,
                        output_folder=folder,
                    )
                    self.assertEqual((folder / DLL).is_file(), dll_stays)
                finally:
                    shutil.rmtree(folder, ignore_errors=True)


@unittest.skipUnless(HAVE_STOCK, "requires all five stock executables")
class PublishedBuildShipsTheDllTests(unittest.TestCase):
    def test_a_statistics_only_build_ships_the_save_reset_dll(self) -> None:
        for game in ("vv2", "vv4"):
            with self.subTest(game=game):
                work = pathlib.Path(tempfile.mkdtemp(prefix=f"{game}_reset_"))
                try:
                    source_dir = work / "game"
                    source_dir.mkdir()
                    shutil.copy2(STOCK / EXE[game], source_dir / EXE[game])
                    output, _log = vp.apply_patch(
                        source_dir / EXE[game],
                        patch_mode="collection_progression",
                        fun_patch_ids=_ids(game, "statistics"),
                        output_root=work / "out",
                    )
                    dll = output.parent / DLL
                    self.assertTrue(dll.is_file(), "the hook's DLL was not shipped")
                    self.assertEqual(
                        vp.sha256(dll),
                        vp.sha256(ROOT / "assets" / "save_reset" / DLL),
                    )
                    self.assertEqual(output.read_bytes()[HOOK[game]], 0xE8)
                    self.assertNotEqual(
                        output.read_bytes()[HOOK[game] : HOOK[game] + 5],
                        (STOCK / EXE[game]).read_bytes()[HOOK[game] : HOOK[game] + 5],
                    )
                finally:
                    shutil.rmtree(work, ignore_errors=True)


class PopulationPagesAreMatchedByVillageTests(unittest.TestCase):
    """Start Over deletes the erased village's roster pages, not "page <slot>".

    The roster is numbered by roll-over PAGE in a folder every slot shares,
    and each page carries the village header on its second line. The reset
    used to delete "Village Population <slot>.txt", which on slot 1 erased
    page 1 of whichever village saved last and on slots 2-5 a page of some
    other roster or nothing. The on-disk proof is the harness
    (scripts/build_save_reset_harness.ps1); these hold its cases in place and
    check the SHIPPED DLL carries the fix rather than only the source.
    """

    RESET_C = ROOT / "native" / "shared" / "save_reset.c"
    HARNESS = ROOT / "native" / "shared" / "save_reset_harness.c"
    DLL_PATH = ROOT / "assets" / "save_reset" / DLL

    def test_the_source_no_longer_addresses_the_roster_by_slot(self) -> None:
        text = self.RESET_C.read_text(encoding="utf-8")
        self.assertNotIn('Village Population %d.txt", sub_w, slot', text)
        self.assertEqual(text.count("delete_village_population_pages(sub_w, village)"), 2)
        self.assertIn("log_line_matches(path, village, 1)", text)

    def test_the_harness_covers_every_case(self) -> None:
        text = self.HARNESS.read_text(encoding="utf-8")
        for case in (
            "POPULATION PAGE 2 OF THE ERASED VILLAGE DELETED",
            "ANOTHER VILLAGE'S POPULATION PAGE 1 SURVIVES A SLOT-1 RESET",
            "SLOT-2 RESET DELETES ITS VILLAGE'S PAGE 1 (slot number irrelevant)",
            "NULL village leaves population pages alone",
            "erased village's page in the RETIRED folder deleted",
        ):
            with self.subTest(case=case):
                self.assertIn(case, text)

    def test_the_shipped_dll_carries_the_fix(self) -> None:
        blob = self.DLL_PATH.read_bytes()
        self.assertIn("%ls\\Village Population *.txt".encode("utf-16-le"), blob)
        self.assertNotIn("%ls\\Village Population %d.txt".encode("utf-16-le"), blob)


CL = pathlib.Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)


class SaveResetHarnessRunsTests(unittest.TestCase):
    """The on-disk reset harness is BUILT AND RUN, not only read as text.

    Until this test no part of the suite ran scripts/build_save_reset_harness.ps1,
    and the harness failed on every run from #495 onward without anyone seeing
    it: its custom-titles loop Starts Over slot 1 in all five games, and VV2's
    slot-1 Start Over rightly deletes "vv2_masks_1.dat" -- the very file the
    later "survivors" check used as "another game's sidecar". The shipped reset
    was right; the fixture had been consumed. The harness now asserts that
    deletion and restores the file, and this test keeps it green.
    """

    BUILD = ROOT / "scripts" / "build_save_reset_harness.ps1"

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_harness_passes(self) -> None:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(self.BUILD)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("OK (0 failures)", result.stdout)
        self.assertNotIn("[FAIL]", result.stdout)
        for case in (
            "[PASS] VV2 slot-1 reset deletes VV2's own slot-1 sidecar",
            "[PASS] survivor: VV1 slot-2 sidecar present after all five refusals",
            "[PASS] survivor: the game's own .ldw present after all five refusals",
            "[PASS] survivor: VV2 slot-1 sidecar present after all five refusals",
        ):
            with self.subTest(case=case):
                self.assertIn(case, result.stdout)


if __name__ == "__main__":
    unittest.main()
