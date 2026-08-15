from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".tools" / "python-packages"))

import vv_fun_patcher as patcher  # noqa: E402


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
BASE_PATH = ROOT / "data" / "candidates" / "vv3_origins_full_mastery_base_candidate.json"
FEATURE_PATH = ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate.json"
MAP_PATH = ROOT / "data" / "candidates" / "vv3_full_mastery_all_candidate_map.json"
DLL_PATH = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
FOUNDATION_DLL_PATH = (
    ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrade Foundation.dll"
)
BUILDER_PATH = ROOT / "scripts" / "build_vv3_safe_upgrade_resources.py"
STOCK_MODES = ("collection_progression", "immediate_fixed")
EXPANDED_MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def load_resource_builder():
    spec = importlib.util.spec_from_file_location("vv3_safe_resources", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_dialogex_independently(blob: bytes) -> tuple[str, int, list[int], int]:
    """Spec-level DIALOGEX walk, deliberately independent of the builder."""
    if len(blob) < 26 or struct.unpack_from("<HH", blob, 0) != (1, 0xFFFF):
        raise AssertionError("resource is not DIALOGEX")

    def skip_field(cursor: int) -> tuple[int, str | None]:
        first = struct.unpack_from("<H", blob, cursor)[0]
        if first == 0:
            return cursor + 2, None
        if first == 0xFFFF:
            return cursor + 4, None
        start = cursor
        while struct.unpack_from("<H", blob, cursor)[0] != 0:
            cursor += 2
        return cursor + 2, blob[start:cursor].decode("utf-16le")

    count = struct.unpack_from("<H", blob, 16)[0]
    style = struct.unpack_from("<I", blob, 12)[0]
    cursor = 26
    for _ in range(3):
        cursor, _ = skip_field(cursor)
    face = ""
    if style & 0x40:  # DS_SETFONT
        cursor += 6  # point size, weight, italic, charset
        cursor, parsed_face = skip_field(cursor)
        face = parsed_face or ""
    cursor = (cursor + 3) & ~3
    first_item = cursor
    control_ids: list[int] = []
    for _ in range(count):
        cursor = (cursor + 3) & ~3
        if cursor + 24 > len(blob):
            raise AssertionError("DIALOGEX item header is truncated")
        control_ids.append(struct.unpack_from("<I", blob, cursor + 20)[0])
        cursor += 24
        cursor, _ = skip_field(cursor)
        cursor, _ = skip_field(cursor)
        extra_bytes = struct.unpack_from("<H", blob, cursor)[0]
        cursor += 2 + extra_bytes
        cursor = (cursor + 3) & ~3
    return face, first_item, control_ids, cursor


class SourceReadSpy:
    def __init__(self) -> None:
        self.read_count = 0

    def read_bytes(self) -> bytes:
        self.read_count += 1
        raise AssertionError("expanded VV3 upgrade guard reached source.read_bytes()")


class VV3SafeUpgradeSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_raw = json.loads(BASE_PATH.read_text(encoding="utf-8"))
        cls.feature_raw = json.loads(FEATURE_PATH.read_text(encoding="utf-8"))
        cls.mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        cls.base = patcher.FunPatch(cls.base_raw)
        cls.feature = patcher.FunPatch(cls.feature_raw)
        cls.build = next(item for item in patcher.load_builds() if item.id == "vv3")
        catalog = {item.id: item for item in patcher.load_fun_patches() if item.game_id == "vv3"}
        cls.statistics = catalog["vv3_write_village_statistics"]

    def test_resource_only_projection_is_deterministic_and_nonresource_exact(self) -> None:
        module = load_resource_builder()
        source = module.SOURCE.read_bytes()
        expected = DLL_PATH.read_bytes()
        self.assertEqual(module.build_resource_only_companion(source), expected)
        self.assertEqual(sha(expected), "8DB27C9208C0060046513078DF53A4DC8D7347AF5A9FD27177803E9388648BEE")
        foundation = FOUNDATION_DLL_PATH.read_bytes()
        self.assertEqual(
            module.build_resource_only_companion(
                source, include_individual_full_mastery=False
            ),
            foundation,
        )
        self.assertEqual(sha(foundation), "A99584788F1726AF2DFDAE83BC9F42DE82DBD2DBA6E1ECD56222D2BDACB47681")
        raw, size, _, _ = module._resource_section(source)
        self.assertEqual(expected[:raw], source[:raw])
        self.assertEqual(expected[raw + size :], source[raw + size :])

    def test_parsed_dialogs_contain_only_truthful_phase1_commands(self) -> None:
        module = load_resource_builder()
        data = DLL_PATH.read_bytes()
        controls: dict[int, set[int]] = {}
        for path, _, _, _, blob in module.resource_leaves(data):
            if path[0] != 5 or path[1] not in module.TARGET_COUNTS:
                continue
            face, first_item, control_ids, parsed_end = parse_dialogex_independently(blob)
            self.assertEqual(face, "Segoe UI")
            self.assertEqual(parsed_end, len(blob))
            self.assertEqual(len(control_ids), module.PUBLIC_TARGET_COUNTS[path[1]])
            if path[1] == 202:
                self.assertEqual(first_item, 0x5C)
                self.assertEqual(
                    control_ids,
                    [0xFFFFFFFF, 0xFFFFFFFF, 1101, 0xFFFFFFFF, 0xFFFFFFFF, 1001, 2],
                )
            controls[path[1]] = set(control_ids)
        self.assertEqual(controls[201] & set(range(1000, 1009)), set(range(1000, 1005)))
        self.assertEqual(controls[202] & set(range(1000, 1009)), {1001})
        self.assertEqual(
            controls[203] & set(range(1000, 1009)),
            set(range(1000, 1005)) | {1007},
        )
        for text in (
            "Cure all Villagers",
            "All Villagers Like Running",
            "All Villagers are 18",
            "Grant Youth",
            "Grant Running",
            "Set Age to 18",
        ):
            self.assertNotIn(text.encode("utf-16le"), data)

        foundation_controls: set[int] | None = None
        foundation = FOUNDATION_DLL_PATH.read_bytes()
        for path, _, _, _, blob in module.resource_leaves(foundation):
            if path[:2] == (5, 202):
                face, first_item, control_ids, parsed_end = parse_dialogex_independently(blob)
                self.assertEqual((face, first_item, parsed_end), ("Segoe UI", 0x5C, len(blob)))
                foundation_controls = set(control_ids)
        self.assertEqual(foundation_controls, {0xFFFFFFFF, 2})

    def test_final_hooks_and_preserved_tech_mastery_bytes_in_all_compositions(self) -> None:
        expected_tech_hook = bytes.fromhex("E92D81FDFF9090")
        expected_tech_guard = bytes.fromhex(
            "83FB050F849C7D02008B049D543F4A00E9C07E02000000000000000000000000"
        )
        expected_detail_guard = bytes.fromhex("E926010000")
        expected_regions = {
            "tech_prefix": "C5087BF1F400E0DE81419D13FF282EE1980A8800247CEED640D1DAF45D1666A4",
            "tech_suffix": "8986402C79E8CD8CEE3D45D41E2C67DAEAA97F3D9DE6D6F08B9631BE724D3C9D",
            "village_mastery_slot": "B1499EB3B10B7E4728746711E9F63B88211E4B80CA378742ADC5DC06782DAADA",
        }
        for mode in STOCK_MODES:
            compositions = {
                "origins": [self.base],
                "village_full_mastery": [self.base, self.feature],
                "statistics": [self.base, self.feature, self.statistics],
            }
            for name, features in compositions.items():
                with self.subTest(mode=mode, composition=name):
                    rendered, _ = patcher.render_patched_bytes(
                        STOCK, self.build, mode, _fun_patches_override=features
                    )
                    self.assertEqual(rendered[0xA35EF:0xA35F6], expected_tech_hook)
                    self.assertEqual(rendered[0x7B721:0x7B741], expected_tech_guard)
                    self.assertEqual(rendered[0xA38C3:0xA38C8], expected_detail_guard)
                    self.assertEqual(sha(rendered[0xA34C0:0xA35EF]), expected_regions["tech_prefix"])
                    self.assertEqual(sha(rendered[0xA35F6:0xA36F1]), expected_regions["tech_suffix"])
                    slot_hash = sha(rendered[0xCB100:0xCB800])
                    if self.feature in features:
                        self.assertEqual(slot_hash, expected_regions["village_mastery_slot"])
                    else:
                        self.assertEqual(
                            slot_hash,
                            "ACCC1E40B883376B131677C68D622FD37E7259C1C56E6BBA6A5273DA80757D8B",
                        )
                    map_key = {
                        "origins": "base_only_sha256",
                        "village_full_mastery": "base_plus_mastery_sha256",
                        "statistics": "statistics_composition_sha256",
                    }[name]
                    self.assertEqual(
                        sha(rendered), self.mapping["rendered_candidates"][mode][map_key]
                    )

    def test_expanded_upgrade_ids_reject_before_variant_catalog_companion_or_source(self) -> None:
        for mode in EXPANDED_MODES:
            for selected_id in patcher.VV3_STOCK_ONLY_UPGRADE_IDS:
                for pathway in ("public", "override"):
                    with self.subTest(mode=mode, selected_id=selected_id, pathway=pathway):
                        source = SourceReadSpy()
                        selected = patcher.FunPatch({"id": selected_id})
                        with (
                            mock.patch.object(patcher, "get_patch_variant") as variant_spy,
                            mock.patch.object(patcher, "_selected_fun_patches") as catalog_spy,
                            mock.patch.object(patcher, "_validate_companion_sources") as companion_spy,
                        ):
                            kwargs = (
                                {"fun_patch_ids": (selected_id,)}
                                if pathway == "public"
                                else {"_fun_patches_override": [selected]}
                            )
                            with self.assertRaisesRegex(
                                patcher.PatcherError,
                                "VV3 Origins upgrade surfaces support stock modes only",
                            ):
                                patcher.render_patched_bytes(
                                    source,  # type: ignore[arg-type]
                                    self.build,
                                    mode,
                                    **kwargs,
                                )
                        self.assertEqual(source.read_count, 0)
                        variant_spy.assert_not_called()
                        catalog_spy.assert_not_called()
                        companion_spy.assert_not_called()

    def test_individual_overlap_exception_is_narrow_and_foreign_collision_fails(self) -> None:
        foreign = patcher.FunPatch(
            {
                "id": "vv3_foreign_detail_overlap",
                "game_id": "vv3",
                "name": "foreign overlap",
                "enabled": True,
                "patches": [
                    {
                        "offset": "0xA38C3",
                        "before": "E926010000",
                        "after": "9090909090",
                        "purpose": "unauthorized Detail overlap",
                    }
                ],
            }
        )
        with self.assertRaisesRegex(patcher.PatcherError, "Patch overlap"):
            patcher.render_patched_bytes(
                STOCK,
                self.build,
                "collection_progression",
                _fun_patches_override=[self.base, self.feature, foreign],
            )

    def test_uninstall_round_trips_and_expanded_rejects_before_append(self) -> None:
        for mode in STOCK_MODES:
            baseline, _ = patcher.render_patched_bytes(
                STOCK, self.build, mode, _fun_patches_override=[]
            )
            origins, _ = patcher.render_patched_bytes(
                STOCK, self.build, mode, _fun_patches_override=[self.base]
            )
            mastery, _ = patcher.render_patched_bytes(
                STOCK, self.build, mode, _fun_patches_override=[self.base, self.feature]
            )
            work = bytearray(mastery)
            patcher._remove_feature_bytes(work, self.feature, mode)
            self.assertEqual(work, origins)
            patcher._remove_feature_bytes(work, self.base, mode)
            self.assertEqual(work, baseline)
        for mode in EXPANDED_MODES:
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(patcher.PatcherError, "stock modes only"):
                    patcher.render_patched_bytes(
                        STOCK,
                        self.build,
                        mode,
                        _fun_patches_override=[self.base, self.feature],
                    )


if __name__ == "__main__":
    unittest.main()
