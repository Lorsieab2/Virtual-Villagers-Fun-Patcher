from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    EXPANDED_PATCH_MODES,
    FunPatch,
    PatcherError,
    _relocate_expanded_shr_fun_patches,
    _validate_vv4_expanded_contract,
    _validate_vv4_origins_relocation_contract,
    load_builds,
)


CONTRACT = json.loads(
    (ROOT / "data" / "vv4_expanded_256_contract.json").read_text(encoding="utf-8")
)
EXPANDED = json.loads(
    (ROOT / "data" / "expanded_256.json").read_text(encoding="utf-8")
)
ORIGINS = json.loads(
    (ROOT / "data" / "vv4_origins_feature.json").read_text(encoding="utf-8")
)


class VV4Expanded256ContractTests(unittest.TestCase):
    def test_contract_is_exact_build_and_publication_fail_closed(self) -> None:
        build = next(item for item in load_builds() if item.id == "vv4")
        self.assertEqual(build.sha256, CONTRACT["source_sha256"])
        self.assertFalse(CONTRACT["publication"]["enabled"])
        self.assertEqual(set(CONTRACT["publication"]["modes"]), EXPANDED_PATCH_MODES)
        _validate_vv4_expanded_contract(EXPANDED["games"]["vv4"])

    def test_four_current_origins_absolute_operands_are_guarded_in_shared_manifest(self) -> None:
        expected = CONTRACT["current_origins_shr_absolute_operands"]
        self.assertEqual(len(expected), 4)
        by_offset = {
            item["offset"]: item for item in EXPANDED["games"]["vv4"]["patches"]
        }
        for item in expected:
            with self.subTest(offset=item["offset"]):
                actual = by_offset[item["offset"]]
                self.assertEqual(
                    {
                        key: actual[key]
                        for key in ("offset", "before", "after", "purpose")
                    },
                    {
                        key: item[key]
                        for key in ("offset", "before", "after", "purpose")
                    },
                )

    def test_stock_save_fallback_and_conversion_scope_are_exactly_pinned(self) -> None:
        patches = {
            item["offset"]: item for item in EXPANDED["games"]["vv4"]["patches"]
        }
        loader = CONTRACT["stock_save_compatibility"]["loader_hook"]
        cave = CONTRACT["stock_save_compatibility"]["conversion_cave"]
        self.assertEqual(
            {key: patches[loader["offset"]][key] for key in ("before", "after", "purpose")},
            {key: loader[key] for key in ("before", "after", "purpose")},
        )
        cave_patch = patches[cave["offset"]]
        self.assertEqual(len(bytes.fromhex(cave_patch["before"])), cave["length"])
        cave_after = bytes.fromhex(cave_patch["after"])
        for sequence in cave["required_sequences"]:
            self.assertIn(bytes.fromhex(sequence), cave_after)
        self.assertIn("accept an exact stock VV4 save", cave_patch["purpose"])
        self.assertIn("reload", CONTRACT["stock_save_compatibility"]["scope"]["reload_and_conversion"])
        self.assertIn("player/runtime confirmation", " ".join(CONTRACT["runtime_gates"]))

    def test_four_origins_payload_absolute_operands_are_not_raw_sweep_discovered(self) -> None:
        feature = FunPatch(ORIGINS)
        relocation = ORIGINS["expanded_shr_relocations"]
        _validate_vv4_origins_relocation_contract(feature, relocation)
        expected_offsets = {
            item["offset"] for item in CONTRACT["origins_payload_shr_absolute_operands"]
        }
        actual_payload_offsets = {
            item["offset"]
            for item in relocation["patches"]
            if item.get("kind", "absolute") == "absolute"
            and item["offset"] in expected_offsets
        }
        self.assertEqual(actual_payload_offsets, expected_offsets)
        self.assertEqual(
            {
                item["offset"]
                for item in relocation["patches"]
                if item.get("kind", "absolute") == "absolute"
            },
            expected_offsets
            | {
                item["offset"]
                for item in CONTRACT["all_feature_stale_origins_shr_absolute_operands"]
            },
        )

    def _guarded_relocation_buffer(self) -> bytearray:
        data = bytearray(0xCC300)
        for item in ORIGINS["expanded_shr_relocations"]["patches"]:
            offset = int(item["offset"], 0)
            before = bytes.fromhex(item["before"])
            data[offset : offset + len(before)] = before
        return data

    def test_expanded_relocation_updates_only_explicit_records(self) -> None:
        feature = FunPatch(ORIGINS)
        build = next(item for item in load_builds() if item.id == "vv4")
        data = self._guarded_relocation_buffer()
        applied = _relocate_expanded_shr_fun_patches(
            build,
            "experimental_expanded_256",
            [feature],
            data,
        )
        declared = ORIGINS["expanded_shr_relocations"]["patches"]
        self.assertEqual(
            [item["offset"] for item in applied], [item["offset"] for item in declared]
        )
        delta = 0x85A004 - 0x728004
        for item in CONTRACT["origins_payload_shr_absolute_operands"]:
            offset = int(item["offset"], 0)
            expected = int(item["stock_virtual_address"], 0) + delta
            self.assertEqual(int.from_bytes(data[offset : offset + 4], "little"), expected)

    def test_expanded_rel32_rows_relocate_moved_sources_and_targets(self) -> None:
        feature = FunPatch(ORIGINS)
        build = next(item for item in load_builds() if item.id == "vv4")
        data = self._guarded_relocation_buffer()
        applied = _relocate_expanded_shr_fun_patches(
            build,
            "experimental_expanded_256",
            [feature],
            data,
        )
        by_offset = {item["offset"]: item for item in applied}
        relocation = ORIGINS["expanded_shr_relocations"]
        stock_va = int(relocation["stock_virtual_address"], 0)
        expanded_va = int(relocation["expanded_virtual_address"], 0)
        delta = expanded_va - stock_va
        for row in relocation["patches"]:
            if row.get("kind") != "rel32":
                continue
            source_va = int(row["source_virtual_address"], 0)
            if stock_va <= source_va < stock_va + 0x1000:
                source_va += delta
            target_stock = int(row["target_stock_virtual_address"], 0)
            target_expanded_value = row.get("target_expanded_virtual_address")
            target_expanded = (
                int(target_expanded_value, 0)
                if isinstance(target_expanded_value, str)
                else target_stock + delta
                if stock_va <= target_stock < stock_va + 0x1000
                else target_stock
            )
            expected = (target_expanded - (source_va + 5)).to_bytes(
                4, "little", signed=True
            ).hex().upper()
            with self.subTest(offset=row["offset"]):
                self.assertEqual(by_offset[row["offset"]]["after"], expected)
        self.assertEqual(by_offset["0xCC02A"]["after"], "12020000")

    def test_stock_mode_does_not_relocate_and_negative_guards_fail_closed(self) -> None:
        feature = FunPatch(ORIGINS)
        build = next(item for item in load_builds() if item.id == "vv4")
        data = self._guarded_relocation_buffer()
        before = bytes(data)
        self.assertEqual(
            _relocate_expanded_shr_fun_patches(
                build, "collection_progression", [feature], data
            ),
            [],
        )
        self.assertEqual(bytes(data), before)

        broken_data = self._guarded_relocation_buffer()
        broken_data[int("0xCC182", 0)] ^= 1
        with self.assertRaisesRegex(PatcherError, "guard failed"):
            _relocate_expanded_shr_fun_patches(
                build, "experimental_expanded_256", [feature], broken_data
            )

        broken_feature = copy.deepcopy(ORIGINS)
        next(
            item
            for item in broken_feature["expanded_shr_relocations"]["patches"]
            if item["offset"] == "0xCC182"
        )["before"] = "FFFFFFFF"
        with self.assertRaisesRegex(PatcherError, "guard drift"):
            _validate_vv4_origins_relocation_contract(
                FunPatch(broken_feature), broken_feature["expanded_shr_relocations"]
            )

        broken_manifest = copy.deepcopy(EXPANDED["games"]["vv4"])
        next(
            item
            for item in broken_manifest["patches"]
            if item["offset"] == "0x20902"
        )["after"] = "04A08500"
        with self.assertRaisesRegex(PatcherError, "current-Origins"):
            _validate_vv4_expanded_contract(broken_manifest)


if __name__ == "__main__":
    unittest.main()
