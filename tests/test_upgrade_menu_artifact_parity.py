"""Artifact-level checks for the five-game upgrade-menu parity contract.

This module checks only repository-owned manifests, companion bytes, compiled
resource/string evidence, and generated VV5 metadata.  It deliberately makes
no claim about launching a game, native execution, save/load behavior, or
player acceptance; those remain separate runtime/player gates.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]

# VV5's Task9 manifest is the active owner returned by the production loader;
# vv5_origins_feature.json is its pinned active-base input, not the emitted
# companion owner.  The other four game manifests are the active owners.
ACTIVE_MANIFESTS = {
    "vv1": ROOT / "data" / "vv1_origins_feature.json",
    "vv2": ROOT / "data" / "vv2_origins_feature.json",
    "vv3": ROOT / "data" / "vv3_origins_feature.json",
    "vv4": ROOT / "data" / "vv4_origins_feature.json",
    "vv5": ROOT / "data" / "vv5_task9_native_actions.json",
}

ACTIVE_COMPILED_COMPANIONS = {
    "vv1": {
        "source": "assets/origins/VVFP VV1 Origins Icons.dll",
        "destination": "VVFP VV1 Origins Icons.dll",
    },
    "vv2": {
        "source": "assets/origins/VVFP VV2 Origins Icons.dll",
        "destination": "VVFP VV2 Origins Icons.dll",
    },
    "vv3": {
        "source": "data/candidates/VVFP VV3 Safe Upgrades.dll",
        "destination": "VVFP Origins Icons.dll",
    },
    "vv4": {
        "source": "assets/origins/VVFP VV4 Origins Icons.dll",
        "destination": "VVFP VV4 Origins Icons.dll",
    },
    "vv5": {
        "source": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
        "destination": "VVFP Origins Icons.dll",
    },
}

COMMON_ASCII = (
    "Do you want to buy %s for %s tech points?\r\n"
    "Press OK to confirm, or Cancel.",
    "No refund was issued.",
    "Warning: This will change the villager's head genetics.",
    "Warning: This will change the head genetics of every villager of the "
    "selected sex, affecting their descendants.\r\n\r\nProceed?",
)

# Dialog captions/labels are RT_DIALOG resource strings and therefore UTF-16LE
# in a compiled PE.  VV1 intentionally omits the two Collections rows.
COMMON_UTF16 = (
    "Origins Upgrades",
    "Villager Upgrades",
    "Cancel",
    "Press ESC to exit this menu.",
    "Full Heal / Cure All",
    "Grant Running to All Villagers",
    "Equal Division of Labor (Includes Parenting)",
    "Equal Division of Labor (No Parenting)",
)
COLLECTION_UTF16 = ("Complete All Collections", "Reset All Collections")

# These are confirmed stale bytes, not a broad historical-string ban.  The
# VV3 labels cover the old active-menu wording that preceded the current
# parity contract; keeping them absent from the emitted DLL also catches a
# stale dormant-resource copy accidentally retained by a rebuild.
STALE_BYTES = {
    "vv2": (
        "Do you want to buy %s for %u tech points?\r\n"
        "Press OK to confirm, or Cancel.",
    ),
    "vv3": (
        "Do you want to remove %s?\r\n"
        "It will be removed with no refund.\r\n"
        "Press OK to confirm, or Cancel.",
        "Warning: This will change the head genetics of every villager of the "
        "chosen sex.",
        "Full Heal/Cure All Villagers",
        "All Villagers Like Running",
        "Complete all Collections",
        "Reset all Collections",
        "Equal Division of Labor (Incl. Parenting)",
    ),
    "vv4": ("Full Heal/Cure All Villagers",),
}

# The generated page layout does not currently publish routine offsets in its
# map.  This is the stable offset emitted by OFF["show_menu"] in the current
# VV5 builder; the generated map's routine length/hash are checked alongside it.
VV5_SHOW_MENU_OFFSET = 0x670
VV5_LIMITED_CAPABILITY_OR = bytes.fromhex("0D00004000")
VV5_SOURCE_BINDING_PATHS = {
    "task9_builder": "scripts/build_vv5_task9_native_actions.py",
    "companion_c": "native/vv5_task9_origins/vv5_task9_origins.c",
    "companion_def": "native/vv5_task9_origins/vv5_task9_origins.def",
    "companion_rc": "native/vv5_task9_origins/vv5_task9_origins.rc",
    "companion_builder": "scripts/build_vv5_task9_origins_dll.ps1",
    "individual_reference": "src/vv5_individual_transactions.py",
    "full_heal_reference": "src/vv5_full_heal.py",
    "active_base": "data/vv5_origins_feature.json",
    "task8_overlay": "data/candidates/vv5_post_prototype_overlay.json",
    "atomic_generator": "src/expanded_atomic_writer.py",
    "atomic_contract": "data/expanded_atomic_writer_integration.json",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _source_text_sha256(path: Path) -> str:
    """Match build_vv5_task9_native_actions.source_text_sha exactly."""

    text = path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _encoded(text: str, encoding: str) -> bytes:
    return text.encode(encoding)


def _manifest_companion(manifest: dict, source: str) -> dict:
    matches = [
        row
        for row in manifest.get("companion_files", [])
        if isinstance(row, dict) and row.get("source") == source
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one companion source {source!r}, got {len(matches)}"
        )
    return matches[0]


def _assert_present(test: unittest.TestCase, binary: bytes, text: str, encoding: str) -> None:
    needle = _encoded(text, encoding)
    if needle not in binary:
        test.fail(f"missing {encoding} artifact string: {text!r}")


def _assert_absent(test: unittest.TestCase, binary: bytes, text: str, encoding: str) -> None:
    needle = _encoded(text, encoding)
    if needle in binary:
        test.fail(f"found confirmed stale {encoding} artifact string: {text!r}")


class UpgradeMenuArtifactParityTests(unittest.TestCase):
    def test_active_manifest_companion_sources_exist_and_match_declared_sha256(self) -> None:
        """Every active owner must carry hash-authenticated local companions."""

        for game, path in ACTIVE_MANIFESTS.items():
            with self.subTest(game=game):
                manifest = _load_json(path)
                companions = manifest.get("companion_files")
                self.assertIsInstance(companions, list)
                self.assertTrue(companions)
                for index, row in enumerate(companions):
                    with self.subTest(companion=index):
                        self.assertIsInstance(row, dict)
                        source = row.get("source")
                        self.assertIsInstance(source, str)
                        source_path = ROOT / source
                        self.assertTrue(source_path.is_file(), source)
                        declared = row.get("sha256")
                        self.assertIsInstance(declared, str)
                        self.assertRegex(declared, r"^[0-9A-Fa-f]{64}$")
                        self.assertEqual(_sha256(source_path), declared.upper(), source)

    def test_active_manifest_bindings_point_to_expected_companions(self) -> None:
        """The five active owners resolve to the compiled companion shipped."""

        for game, expected in ACTIVE_COMPILED_COMPANIONS.items():
            with self.subTest(game=game):
                manifest = _load_json(ACTIVE_MANIFESTS[game])
                self.assertEqual(manifest.get("game_id"), game)
                self.assertEqual(
                    manifest.get("id"), f"{game}_enable_origins_exclusive_features"
                )
                row = _manifest_companion(manifest, expected["source"])
                self.assertEqual(row.get("destination"), expected["destination"])
                self.assertEqual(
                    row.get("sha256"), _sha256(ROOT / expected["source"])
                )

    def test_compiled_companions_contain_canonical_ascii_and_utf16_strings(self) -> None:
        """Prompts use ANSI bytes; dialog captions/labels use UTF-16LE."""

        for game, expected in ACTIVE_COMPILED_COMPANIONS.items():
            with self.subTest(game=game):
                binary = (ROOT / expected["source"]).read_bytes()
                for text in COMMON_ASCII:
                    with self.subTest(encoding="ASCII", text=text):
                        _assert_present(self, binary, text, "ascii")
                labels = list(COMMON_UTF16)
                if game != "vv1":
                    labels.extend(COLLECTION_UTF16)
                for text in labels:
                    with self.subTest(encoding="UTF-16LE", text=text):
                        _assert_present(self, binary, text, "utf-16le")

    def test_compiled_companions_exclude_confirmed_stale_strings(self) -> None:
        """Known stale prompt/label encodings must not survive compilation."""

        for game, stale in STALE_BYTES.items():
            binary = (ROOT / ACTIVE_COMPILED_COMPANIONS[game]["source"]).read_bytes()
            for text in stale:
                with self.subTest(game=game, text=text, encoding="ASCII"):
                    _assert_absent(self, binary, text, "ascii")
                with self.subTest(game=game, text=text, encoding="UTF-16LE"):
                    _assert_absent(self, binary, text, "utf-16le")

    def test_vv5_generated_manifest_map_bind_current_sources_and_expanded_show_menu(self) -> None:
        """VV5 generated metadata must bind current sources and the limited OR."""

        manifest_path = ACTIVE_MANIFESTS["vv5"]
        map_path = ROOT / "data" / "candidates" / "vv5_task9_native_actions_map.json"
        manifest = _load_json(manifest_path)
        artifact_map = _load_json(map_path)
        bindings = manifest.get("source_bindings")
        self.assertIsInstance(bindings, dict)
        self.assertEqual(set(bindings), set(VV5_SOURCE_BINDING_PATHS))
        self.assertEqual(artifact_map.get("source_bindings"), bindings)
        for name, relative in VV5_SOURCE_BINDING_PATHS.items():
            with self.subTest(binding=name):
                binding = bindings[name]
                self.assertEqual(binding.get("path"), relative)
                self.assertEqual(
                    binding.get("source_text_sha256"),
                    _source_text_sha256(ROOT / relative),
                )

        expanded = artifact_map["layouts"]["experimental_expanded_256"]
        generated = manifest["pe_append_transaction"]["layouts"][
            "experimental_expanded_256"
        ]
        page = bytes.fromhex(generated["append_bytes"])
        self.assertEqual(len(page), 0x8000)
        self.assertEqual(
            hashlib.sha256(page).hexdigest().upper(), generated["page_sha256"]
        )
        self.assertEqual(generated["page_sha256"], expanded["page_sha256"])
        show_length = int(expanded["routine_length"]["show_menu"])
        show_menu = page[VV5_SHOW_MENU_OFFSET : VV5_SHOW_MENU_OFFSET + show_length]
        self.assertEqual(
            hashlib.sha256(show_menu).hexdigest().upper(),
            expanded["routine_sha256"]["show_menu"],
        )
        self.assertIn(VV5_LIMITED_CAPABILITY_OR, show_menu)

    def test_catalog_load_succeeds_after_integration_regeneration(self) -> None:
        """Static catalog construction is a gate; runtime/player proof is separate."""

        sys.path.insert(0, str(ROOT / "src"))
        try:
            from vv_fun_patcher import load_fun_patches

            catalog = load_fun_patches()
        finally:
            sys.path.pop(0)
        self.assertTrue(catalog)
        self.assertTrue(any(p.id == "vv5_enable_origins_exclusive_features" for p in catalog))

    def test_expanded_records_load_with_explicit_archival_boundary(self) -> None:
        """The opt-in loader authenticates both records without reviving modes."""

        sys.path.insert(0, str(ROOT / "src"))
        try:
            from vv_fun_patcher import _load_fun_patch_records

            records = {
                patch.id: patch
                for patch in _load_fun_patch_records(
                    include_expanded_time_warp=True
                )
                if patch.id in {
                    "vv3_expanded_256_time_warp",
                    "vv5_expanded_256_time_warp",
                }
            }
        finally:
            sys.path.pop(0)

        self.assertEqual(
            set(records),
            {"vv3_expanded_256_time_warp", "vv5_expanded_256_time_warp"},
        )
        for patch in records.values():
            with self.subTest(game=patch.game_id):
                self.assertTrue(patch.enabled)
                self.assertFalse(patch.catalog_enabled)
                self.assertTrue(patch.catalog_hidden)
                self.assertTrue(patch.experimental_explicit_selection)
                self.assertEqual(patch.runtime_player_status, "pending")
                self.assertEqual(
                    patch.supported_modes,
                    [
                        "experimental_expanded_256",
                        "experimental_expanded_256_progression",
                    ],
                )
                self.assertEqual(
                    patch.rejected_modes,
                    ["collection_progression", "immediate_fixed"],
                )

        vv3_manifest = _load_json(ROOT / "data" / "vv3_expanded_time_warp.json")
        vv3_map = _load_json(
            ROOT / "data" / "candidates" / "vv3_expanded_time_warp_map.json"
        )
        vv3_core = _load_json(ROOT / "data" / "vv3_expanded_time_warp_core.json")
        self.assertEqual(vv3_manifest["source_bindings"], vv3_map["source_bindings"])
        self.assertEqual(vv3_manifest["source_bindings"], vv3_core["source_bindings"])
        for path, expected in (
            (ROOT / "data" / "vv3_expanded_time_warp.json",
             "F5094E6275F6A019B001B89E265B71ACD365499C00E57E45AB5AFB6C44C9A8C8"),
            (ROOT / "data" / "candidates" / "vv3_expanded_time_warp_map.json",
             "FB308848ED65695E62F65A6074861F8740009962FC99EFFBD8AEFD2A859F0031"),
            (ROOT / "data" / "vv3_expanded_time_warp_core.json",
             "5AA28CEAAFBC6F4278FF01C41F67E0394227C272123EAC9433BD6D011A4087CE"),
        ):
            with self.subTest(artifact=path.name):
                self.assertEqual(_source_text_sha256(path), expected)
        # These are immutable archival bindings.  The current source is known
        # not to be byte-equivalent because the removed Expanded-256 modes make
        # full regeneration unavailable; the loader deliberately does not
        # claim current builder/companion reproducibility for this record.
        self.assertEqual(
            vv3_manifest["source_bindings"]["builder"]["source_text_sha256"],
            "9A193B390E0DF9302F89285463310862A2CEA260D89E869267BE9D1FEB6DDE60",
        )
        self.assertNotEqual(
            _source_text_sha256(ROOT / "scripts" / "build_vv3_expanded_time_warp.py"),
            vv3_manifest["source_bindings"]["builder"]["source_text_sha256"],
        )
        self.assertEqual(
            vv3_manifest["companion_files"][0],
            vv3_map["companion"],
        )
        self.assertEqual(
            vv3_manifest["companion_files"][0]["sha256"],
            "DA624FAB76A1100A9EFDCB655C6341404AF60F87FF613DBDA861161317E97006",
        )
        current_companion = ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll"
        self.assertNotEqual(
            vv3_manifest["companion_files"][0]["sha256"], _sha256(current_companion)
        )
        self.assertNotEqual(
            vv3_manifest["companion_files"][0]["size"], current_companion.stat().st_size
        )
        vv5_manifest = _load_json(ROOT / "data" / "vv5_expanded_time_warp.json")
        vv5_companion = vv5_manifest["companion_contract"]
        self.assertEqual(vv5_companion["sha256"], _sha256(current_companion))
        self.assertEqual(vv5_companion["size"], current_companion.stat().st_size)
        self.assertEqual(vv5_companion["size"], 1753088)
        self.assertEqual(
            vv5_companion["sha256"],
            "75EFE26D42CF3B5132EF520C5010CC335FD130F6F8222F5C59D7863D8132A44C",
        )

    def test_vv3_archival_builder_binding_tamper_fails_closed(self) -> None:
        """A tampered embedded VV3 builder binding cannot pass archival auth."""

        sys.path.insert(0, str(ROOT / "src"))
        try:
            import vv_fun_patcher as patcher
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manifest_path = temp_root / "vv3_expanded_time_warp.json"
            map_path = temp_root / "vv3_expanded_time_warp_map.json"
            core_path = temp_root / "vv3_expanded_time_warp_core.json"
            manifest = _load_json(ROOT / "data" / "vv3_expanded_time_warp.json")
            artifact_map = _load_json(
                ROOT / "data" / "candidates" / "vv3_expanded_time_warp_map.json"
            )
            core = _load_json(ROOT / "data" / "vv3_expanded_time_warp_core.json")
            tampered = "0" * 64
            manifest["source_bindings"]["builder"]["source_text_sha256"] = tampered
            artifact_map["source_bindings"]["builder"]["source_text_sha256"] = tampered
            artifact_map["core"]["source_bindings"]["builder"]["source_text_sha256"] = tampered
            core["source_bindings"]["builder"]["source_text_sha256"] = tampered
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            map_path.write_text(json.dumps(artifact_map, indent=2) + "\n", encoding="utf-8")
            core_path.write_text(json.dumps(core, indent=2) + "\n", encoding="utf-8")

            paths = dict(patcher.EXPANDED_TIME_WARP_PATHS)
            paths["vv3"] = {"manifest": manifest_path, "map": map_path}
            artifact_hashes = {
                game: dict(values)
                for game, values in patcher.EXPANDED_TIME_WARP_ARTIFACT_SHA256.items()
            }
            artifact_hashes["vv3"] = {
                "manifest": patcher.source_text_sha256(manifest_path.read_bytes()),
                "map": patcher.source_text_sha256(map_path.read_bytes()),
                "core": patcher.source_text_sha256(core_path.read_bytes()),
            }
            with mock.patch.object(patcher, "EXPANDED_TIME_WARP_PATHS", paths), \
                    mock.patch.object(patcher, "VV3_EXPANDED_TIME_WARP_CORE_PATH", core_path), \
                    mock.patch.object(patcher, "EXPANDED_TIME_WARP_ARTIFACT_SHA256", artifact_hashes):
                with self.assertRaisesRegex(
                    patcher.PatcherError, "archival builder binding drifted"
                ):
                    patcher._certified_expanded_time_warp_records()

    def test_expanded_records_independently_apply_declared_hashes_and_offsets(self) -> None:
        """Frozen VV3 page and regenerated VV5 overlay are independently replayable."""

        import importlib.util

        sys.path.insert(0, str(ROOT / "src"))
        try:
            from vv_fun_patcher import _load_fun_patch_records

            records = {
                patch.id: patch
                for patch in _load_fun_patch_records(
                    include_expanded_time_warp=True
                )
                if patch.id in {
                    "vv3_expanded_256_time_warp",
                    "vv5_expanded_256_time_warp",
                }
            }
        finally:
            sys.path.pop(0)

        vv3 = records["vv3_expanded_256_time_warp"]
        vv3_manifest = _load_json(ROOT / "data" / "vv3_expanded_time_warp.json")
        vv3_map = _load_json(
            ROOT / "data" / "candidates" / "vv3_expanded_time_warp_map.json"
        )
        builder_path = ROOT / "scripts" / "build_vv3_expanded_time_warp.py"
        spec = importlib.util.spec_from_file_location(
            "vv3_expanded_time_warp_artifact_test", builder_path
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        vv3_page, vv3_details = module.build_page()
        vv3_page_sha = hashlib.sha256(vv3_page).hexdigest().upper()
        self.assertEqual(len(vv3_page), 0x1000)
        self.assertEqual(
            vv3_page_sha,
            "D169B49C63731970FBE832256C8975806301EE16FC872C6F1B608C6E1FB73C92",
        )
        self.assertEqual(vv3_page_sha, vv3_map["layout"]["page_sha256"])
        self.assertEqual(vv3_details["page_sha256"], vv3_page_sha)

        for mode in vv3.supported_modes:
            with self.subTest(game="vv3", mode=mode):
                layout = vv3_manifest["pe_append_transaction"]["layouts"][mode]
                rows = list(layout["header_patches"])
                rows.extend(vv3.raw["patch_mode_overrides"][mode])
                self.assertEqual(
                    int(layout["original_file_size"], 0),
                    0xCB000,
                )
                self.assertEqual(int(layout["append_offset"], 0), 0xCB000)
                for row in rows:
                    before = bytes.fromhex(row["before"])
                    after = bytes.fromhex(row["after"])
                    self.assertEqual(len(before), len(after))
                    self.assertGreaterEqual(int(row["offset"], 0), 0)
                self.assertEqual(layout["page_sha256"], vv3_page_sha)

        vv5 = records["vv5_expanded_256_time_warp"]
        vv5_manifest = _load_json(ROOT / "data" / "vv5_expanded_time_warp.json")
        vv5_map = _load_json(
            ROOT / "data" / "candidates" / "vv5_expanded_time_warp_map.json"
        )
        page_raw = int(vv5_map["page_raw"], 0)
        for mode in vv5.supported_modes:
            with self.subTest(game="vv5", mode=mode):
                baseline = _load_json(
                    ROOT / "data" / "vv5_task9_native_actions.json"
                )["pe_append_transaction"]["layouts"][mode]["append_bytes"]
                page = bytearray(bytes.fromhex(baseline))
                self.assertEqual(len(page), 0x8000)
                for row in vv5.raw["patch_mode_overrides"][mode]:
                    offset = int(row["offset"], 0)
                    local = offset - page_raw
                    self.assertGreaterEqual(local, 0)
                    if "before_fill" in row:
                        before = bytes.fromhex(row["before_fill"]) * int(
                            row["length"]
                        )
                    else:
                        before = bytes.fromhex(row["before"])
                    after = bytes.fromhex(row["after"])
                    self.assertEqual(len(before), len(after))
                    self.assertEqual(page[local:local + len(before)], before)
                    page[local:local + len(after)] = after
                self.assertEqual(
                    hashlib.sha256(page).hexdigest().upper(),
                    vv5_map["layout"]["expanded_time_warp_page_sha256"],
                )
                self.assertEqual(
                    vv5.raw["patch_mode_overrides"][mode][-1]["offset"],
                    vv5_map["layout"]["strings_file_offset"],
                )
                self.assertEqual(
                    vv5.raw["patch_mode_overrides"][mode][-1]["offset"],
                    "0xFB0C9",
                )
                self.assertEqual(
                    vv5_manifest["patch_mode_overrides"][mode],
                    vv5.raw["patch_mode_overrides"][mode],
                )


if __name__ == "__main__":
    unittest.main()
