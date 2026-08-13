from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher  # noqa: E402
from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    Record,
    _relocate_expanded_shr_fun_patches,
    _validate_vv4_expanded_contract,
    _validate_vv4_origins_relocation_contract,
    _validate_vv5_origins_relocation_contract,
    _expanded_patches,
    _apply_pe_append_transactions,
    load_builds,
    render_patched_bytes,
)


VV4_CONTRACT = json.loads(
    (ROOT / "data" / "vv4_expanded_256_contract.json").read_text(encoding="utf-8")
)
VV4_EXPANDED = json.loads(
    (ROOT / "data" / "expanded_256.json").read_text(encoding="utf-8")
)
VV4_FEATURE = json.loads(
    (ROOT / "data" / "vv4_origins_feature.json").read_text(encoding="utf-8")
)
VV5_FEATURE = json.loads(
    (ROOT / "data" / "vv5_origins_feature.json").read_text(encoding="utf-8")
)
EXPANDED_MANIFEST = json.loads(
    (ROOT / "data" / "expanded_256.json").read_text(encoding="utf-8")
)
VV4_BUILD = next(item for item in load_builds() if item.id == "vv4")
VV5_BUILD = next(item for item in load_builds() if item.id == "vv5")
VV3_BUILD = next(item for item in load_builds() if item.id == "vv3")


class Expanded256AdversarialContractTests(unittest.TestCase):
    def test_expanded_manifest_identity_is_complete_for_vv4_and_vv5(self) -> None:
        for build in (VV4_BUILD, VV5_BUILD):
            with self.subTest(game=build.id):
                patches = _expanded_patches(build, {"expanded_records": True})
                self.assertEqual(
                    len(patches), EXPANDED_MANIFEST["games"][build.id]["patch_count"]
                )

    def test_expanded_manifest_identity_mutations_fail_closed(self) -> None:
        for game_id, build in (("vv4", VV4_BUILD), ("vv5", VV5_BUILD)):
            for mutation in ("prototype", "count", "missing", "duplicate", "row"):
                broken = copy.deepcopy(EXPANDED_MANIFEST)
                game = broken["games"][game_id]
                if mutation == "prototype":
                    game["prototype_sha256"] = "0" * 64
                elif mutation == "count":
                    game["patch_count"] -= 1
                elif mutation == "missing":
                    game["patches"].pop()
                elif mutation == "duplicate":
                    game["patches"].append(copy.deepcopy(game["patches"][0]))
                else:
                    game["patches"][0]["after"] = "00" * (len(bytes.fromhex(game["patches"][0]["after"])))
                with tempfile.TemporaryDirectory() as temp_dir, self.subTest(game=game_id, mutation=mutation):
                    manifest_path = Path(temp_dir) / "expanded.json"
                    manifest_path.write_text(json.dumps(broken), encoding="utf-8")
                    with patch.object(vv_fun_patcher, "EXPANDED_MANIFEST_PATH", manifest_path):
                        with self.assertRaises(PatcherError):
                            _expanded_patches(build, {"expanded_records": True})

    def test_relocation_helper_rejects_cross_game_feature_identity(self) -> None:
        feature = FunPatch(VV4_FEATURE)
        data = self._vv4_buffer()
        with self.assertRaisesRegex(PatcherError, "game identity"):
            _relocate_expanded_shr_fun_patches(
                VV5_BUILD, "experimental_expanded_256", [feature], data
            )

    def test_generic_rel32_inconsistent_stock_preimage_is_rejected(self) -> None:
        feature = FunPatch(
            {
                "id": "adversarial_rel32",
                "game_id": "vv5",
                "expanded_shr_relocations": {
                    "stock_virtual_address": "0x7B2000",
                    "expanded_virtual_address": "0x8EB000",
                    "patches": [
                        {
                            "offset": "0x20",
                            "before": "00000000",
                            "kind": "rel32",
                            "source_virtual_address": "0x401000",
                            "target_stock_virtual_address": "0x450000",
                        }
                    ],
                },
            }
        )
        data = bytearray(0x100)
        snapshot = bytes(data)
        with self.assertRaisesRegex(PatcherError, "stock preimage"):
            _relocate_expanded_shr_fun_patches(
                VV5_BUILD, "experimental_expanded_256", [feature], data
            )
        self.assertEqual(bytes(data), snapshot)

    def test_append_header_guards_are_transactional(self) -> None:
        feature = FunPatch(
            {
                "id": "adversarial_append",
                "name": "Adversarial append",
                "game_id": "vv5",
                "pe_append_transaction": {
                    "layouts": {
                        "experimental_expanded_256": {
                            "original_file_size": "0x4",
                            "append_offset": "0x4",
                            "append_bytes": "00" * 0x1000,
                            "purpose": "adversarial append",
                            "header_patches": [
                                {"offset": "0x0", "before": "AA", "after": "BB", "purpose": "first"},
                                {"offset": "0x1", "before": "FF", "after": "CC", "purpose": "second"},
                            ],
                        }
                    }
                },
            }
        )
        data = bytearray.fromhex("AA00CCDD")
        snapshot = bytes(data)
        with self.assertRaisesRegex(PatcherError, "append header guard failed"):
            _apply_pe_append_transactions(
                data, [feature], "experimental_expanded_256"
            )
        self.assertEqual(bytes(data), snapshot)
    @staticmethod
    def _mutated_row_value(field: str, value: object) -> object:
        if field == "kind":
            return "absolute" if value == "rel32" else "rel32"
        if field == "purpose":
            return f"{value} [mutated]"
        if field in {"before", "expanded_skip_before"}:
            mutated = bytearray.fromhex(str(value))
            mutated[-1] ^= 1
            return mutated.hex().upper()
        if field == "offset" or "virtual_address" in field:
            return f"0x{int(str(value), 0) + 1:X}"
        if isinstance(value, str):
            return f"{value}-mutated"
        return None if value is not None else "mutated"

    @classmethod
    def _mutate_relocation_row(
        cls, feature: dict[str, object], offset: str, field: str
    ) -> dict[str, object]:
        broken = copy.deepcopy(feature)
        rows = broken["expanded_shr_relocations"]["patches"]
        row = next(item for item in rows if item["offset"] == offset)
        if field not in row:
            row[field] = cls._mutated_row_value(field, row.get("kind"))
        else:
            row[field] = cls._mutated_row_value(field, row[field])
        return broken

    @staticmethod
    def _vv4_buffer() -> bytearray:
        data = bytearray(0xCC300)
        for item in VV4_FEATURE["expanded_shr_relocations"]["patches"]:
            offset = int(item["offset"], 0)
            data[offset : offset + 4] = bytes.fromhex(item["before"])
        return data

    @staticmethod
    def _vv5_buffer() -> bytearray:
        data = bytearray(0xDC000)
        for item in VV5_FEATURE["expanded_shr_relocations"]["patches"]:
            offset = int(item["offset"], 0)
            data[offset : offset + 4] = bytes.fromhex(item["before"])
        return data

    def test_vv4_missing_all_four_shared_operands_fails_closed(self) -> None:
        for expected in VV4_CONTRACT["current_origins_shr_absolute_operands"]:
            broken = copy.deepcopy(VV4_EXPANDED["games"]["vv4"])
            broken["patches"] = [
                item for item in broken["patches"] if item["offset"] != expected["offset"]
            ]
            with self.subTest(offset=expected["offset"]), self.assertRaisesRegex(
                PatcherError, "current-Origins"
            ):
                _validate_vv4_expanded_contract(broken)

    def test_vv4_missing_or_duplicate_each_of_eight_payload_rows_fails_closed(self) -> None:
        expected_offsets = {
            item["offset"]
            for group in (
                VV4_CONTRACT["origins_payload_shr_absolute_operands"],
                VV4_CONTRACT["all_feature_stale_origins_shr_absolute_operands"],
            )
            for item in group
        }
        self.assertEqual(len(expected_offsets), 8)
        for offset in expected_offsets:
            broken = copy.deepcopy(VV4_FEATURE)
            broken["expanded_shr_relocations"]["patches"] = [
                item
                for item in broken["expanded_shr_relocations"]["patches"]
                if item["offset"] != offset
            ]
            with self.subTest(kind="missing", offset=offset), self.assertRaisesRegex(
                PatcherError, "exactly thirteen|guard drift"
            ):
                _validate_vv4_origins_relocation_contract(
                    FunPatch(broken), broken["expanded_shr_relocations"]
                )

            duplicate = copy.deepcopy(VV4_FEATURE)
            duplicate["expanded_shr_relocations"]["patches"].append(
                next(
                    item
                    for item in duplicate["expanded_shr_relocations"]["patches"]
                    if item["offset"] == offset
                )
            )
            with self.subTest(kind="duplicate", offset=offset), self.assertRaisesRegex(
                PatcherError, "exactly thirteen|duplicate"
            ):
                _validate_vv4_origins_relocation_contract(
                    FunPatch(duplicate), duplicate["expanded_shr_relocations"]
                )

    def test_vv4_wrong_relocation_class_hash_and_publication_fail_closed(self) -> None:
        wrong_class = copy.deepcopy(VV4_FEATURE)
        next(
            item
            for item in wrong_class["expanded_shr_relocations"]["patches"]
            if item["offset"] == "0xCC182"
        )["kind"] = "rel32"
        with self.assertRaisesRegex(PatcherError, "exactly eight|guard drift"):
            _validate_vv4_origins_relocation_contract(
                FunPatch(wrong_class), wrong_class["expanded_shr_relocations"]
            )

        wrong_hash = copy.deepcopy(VV4_EXPANDED["games"]["vv4"])
        wrong_hash["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(PatcherError, "fingerprint"):
            _validate_vv4_expanded_contract(wrong_hash)

        with tempfile.TemporaryDirectory() as temp_dir:
            contract_path = Path(temp_dir) / "vv4-contract.json"
            broken_contract = copy.deepcopy(VV4_CONTRACT)
            broken_contract["publication"]["enabled"] = True
            contract_path.write_text(json.dumps(broken_contract), encoding="utf-8")
            with patch.object(vv_fun_patcher, "VV4_EXPANDED_CONTRACT_PATH", contract_path):
                with self.assertRaisesRegex(PatcherError, "identity or fail-closed"):
                    _validate_vv4_expanded_contract(VV4_EXPANDED["games"]["vv4"])

    def test_vv4_every_relocation_row_field_is_exactly_pinned(self) -> None:
        rows = VV4_FEATURE["expanded_shr_relocations"]["patches"]
        for row in rows:
            fields = set(row) | {"kind"}
            for field in sorted(fields):
                broken = self._mutate_relocation_row(
                    VV4_FEATURE, row["offset"], field
                )
                with self.subTest(offset=row["offset"], field=field), self.assertRaises(
                    PatcherError
                ):
                    _validate_vv4_origins_relocation_contract(
                        FunPatch(broken), broken["expanded_shr_relocations"]
                    )

        broken_digest = copy.deepcopy(VV4_FEATURE)
        broken_digest["expanded_shr_relocations"]["ledger_sha256"] = "0" * 64
        with self.assertRaisesRegex(PatcherError, "ledger digest"):
            _validate_vv4_origins_relocation_contract(
                FunPatch(broken_digest), broken_digest["expanded_shr_relocations"]
            )

    def test_vv4_rel32_rows_pin_stock_preimage_and_partition(self) -> None:
        expected = {"0x896CC", "0x89734", "0x8973C", "0x89746", "0xCC02A"}
        rows = VV4_FEATURE["expanded_shr_relocations"]["patches"]
        self.assertEqual(
            {row["offset"] for row in rows if row.get("kind") == "rel32"},
            expected,
        )
        for offset in sorted(expected):
            broken = copy.deepcopy(VV4_FEATURE)
            row = next(
                item
                for item in broken["expanded_shr_relocations"]["patches"]
                if item["offset"] == offset
            )
            row["before"] = "00000000"
            with self.subTest(offset=offset), self.assertRaisesRegex(
                PatcherError, "stock preimage"
            ):
                _validate_vv4_origins_relocation_contract(
                    FunPatch(broken), broken["expanded_shr_relocations"]
                )

    def test_vv4_stock_mode_and_failed_expanded_preflight_do_not_mutate(self) -> None:
        feature = FunPatch(VV4_FEATURE)
        stock_data = self._vv4_buffer()
        stock_before = bytes(stock_data)
        self.assertEqual(
            _relocate_expanded_shr_fun_patches(
                VV4_BUILD, "collection_progression", [feature], stock_data
            ),
            [],
        )
        self.assertEqual(bytes(stock_data), stock_before)

        broken_data = self._vv4_buffer()
        broken_data[int("0xCC02A", 0)] ^= 1
        broken_before = bytes(broken_data)
        with self.assertRaisesRegex(PatcherError, "guard failed"):
            _relocate_expanded_shr_fun_patches(
                VV4_BUILD, "experimental_expanded_256", [feature], broken_data
            )
        self.assertEqual(bytes(broken_data), broken_before)

    def test_vv5_exact_partition_hash_and_row_integrity_are_validated(self) -> None:
        self.assertEqual(
            sum(
                item.get("kind", "absolute") == "absolute"
                and "external" not in item.get("purpose", "")
                for item in VV5_FEATURE["expanded_shr_relocations"]["patches"]
            ),
            23,
        )
        self.assertEqual(
            sum(
                item.get("kind", "absolute") == "rel32"
                for item in VV5_FEATURE["expanded_shr_relocations"]["patches"]
            ),
            36,
        )
        self.assertEqual(
            sum("external" in item.get("purpose", "") for item in VV5_FEATURE["expanded_shr_relocations"]["patches"]),
            7,
        )
        _validate_vv5_origins_relocation_contract(
            FunPatch(VV5_FEATURE), VV5_FEATURE["expanded_shr_relocations"]
        )

        for mutation in ("duplicate", "missing", "wrong_class", "wrong_hash"):
            broken = copy.deepcopy(VV5_FEATURE)
            patches = broken["expanded_shr_relocations"]["patches"]
            if mutation == "duplicate":
                patches.append(copy.deepcopy(patches[0]))
            elif mutation == "missing":
                del patches[0]
            elif mutation == "wrong_class":
                next(item for item in patches if item["offset"] == "0x18910")["kind"] = "absolute"
            else:
                broken["expanded_shr_relocations"]["evidence"]["exact_stock_sha256"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(PatcherError):
                _validate_vv5_origins_relocation_contract(
                    FunPatch(broken), broken["expanded_shr_relocations"]
                )

        wrong_absolute_class = copy.deepcopy(VV5_FEATURE)
        next(
            item
            for item in wrong_absolute_class["expanded_shr_relocations"]["patches"]
            if item["offset"] == "0xDB087"
        )["kind"] = "rel32"
        with self.assertRaisesRegex(PatcherError, "absolute relocation class"):
            _validate_vv5_origins_relocation_contract(
                FunPatch(wrong_absolute_class),
                wrong_absolute_class["expanded_shr_relocations"],
            )

        for key in (
            "payload_internal_absolute_sites",
            "cross_section_rel32_sites",
            "external_absolute_sites",
        ):
            wrong_partition = copy.deepcopy(VV5_FEATURE)
            wrong_partition["expanded_shr_relocations"]["evidence"][key] += 1
            with self.subTest(evidence=key), self.assertRaisesRegex(
                PatcherError, "evidence"
            ):
                _validate_vv5_origins_relocation_contract(
                    FunPatch(wrong_partition),
                    wrong_partition["expanded_shr_relocations"],
                )

    def test_vv5_every_relocation_row_field_is_exactly_pinned(self) -> None:
        rows = VV5_FEATURE["expanded_shr_relocations"]["patches"]
        for row in rows:
            fields = set(row) | {"kind"}
            for field in sorted(fields):
                broken = self._mutate_relocation_row(
                    VV5_FEATURE, row["offset"], field
                )
                with self.subTest(offset=row["offset"], field=field), self.assertRaises(
                    PatcherError
                ):
                    _validate_vv5_origins_relocation_contract(
                        FunPatch(broken), broken["expanded_shr_relocations"]
                    )

        broken_digest = copy.deepcopy(VV5_FEATURE)
        broken_digest["expanded_shr_relocations"]["ledger_sha256"] = "0" * 64
        with self.assertRaisesRegex(PatcherError, "ledger digest"):
            _validate_vv5_origins_relocation_contract(
                FunPatch(broken_digest), broken_digest["expanded_shr_relocations"]
            )

    def test_vv5_moved_and_unmoved_rel32_target_errors_fail_closed(self) -> None:
        delta = int("0x8EB000", 0) - int("0x7B2000", 0)
        for offset, target in (("0x18910", "0x7B2180"), ("0xDB01C", "0x450D40")):
            broken = copy.deepcopy(VV5_FEATURE)
            row = next(
                item
                for item in broken["expanded_shr_relocations"]["patches"]
                if item["offset"] == offset
            )
            row["target_expanded_virtual_address"] = (
                target if offset == "0x18910" else f"0x{int(target, 0) + delta:X}"
            )
            with self.subTest(offset=offset), self.assertRaisesRegex(
                PatcherError, "moved/unmoved target"
            ):
                _validate_vv5_origins_relocation_contract(
                    FunPatch(broken), broken["expanded_shr_relocations"]
                )

    def test_vv5_rel32_rows_pin_stock_preimages(self) -> None:
        for row in VV5_FEATURE["expanded_shr_relocations"]["patches"]:
            if row.get("kind") != "rel32":
                continue
            broken = copy.deepcopy(VV5_FEATURE)
            broken_row = next(
                item
                for item in broken["expanded_shr_relocations"]["patches"]
                if item["offset"] == row["offset"]
            )
            broken_row["before"] = "00000000"
            with self.subTest(offset=row["offset"]), self.assertRaisesRegex(
                PatcherError, "stock preimage"
            ):
                _validate_vv5_origins_relocation_contract(
                    FunPatch(broken), broken["expanded_shr_relocations"]
                )

    def test_vv5_stale_preimage_is_transactional_and_stock_mode_is_noop(self) -> None:
        feature = FunPatch(VV5_FEATURE)
        stock_data = self._vv5_buffer()
        stock_before = bytes(stock_data)
        self.assertEqual(
            _relocate_expanded_shr_fun_patches(
                VV5_BUILD, "collection_progression", [feature], stock_data
            ),
            [],
        )
        self.assertEqual(bytes(stock_data), stock_before)

        stale_data = self._vv5_buffer()
        stale_data[int("0xDB087", 0)] ^= 1
        stale_before = bytes(stale_data)
        with self.assertRaisesRegex(PatcherError, "guard failed"):
            _relocate_expanded_shr_fun_patches(
                VV5_BUILD, "experimental_expanded_256", [feature], stale_data
            )
        self.assertEqual(bytes(stale_data), stale_before)

        partial_data = self._vv5_buffer()
        partial_data[int("0xDBB27", 0)] ^= 1
        partial_before = bytes(partial_data)
        with self.assertRaisesRegex(PatcherError, "guard failed"):
            _relocate_expanded_shr_fun_patches(
                VV5_BUILD, "experimental_expanded_256", [feature], partial_data
            )
        self.assertEqual(bytes(partial_data), partial_before)

    def test_overlapping_writes_are_rejected_before_any_mutation(self) -> None:
        before = "00207B00"
        feature = FunPatch(
            {
                "id": "adversarial_overlap",
                "name": "Adversarial overlap",
                "expanded_shr_relocations": {
                    "stock_virtual_address": "0x7B2000",
                    "expanded_virtual_address": "0x8EB000",
                    "patches": [
                        {"offset": "0x20", "before": before},
                        {"offset": "0x20", "before": before},
                    ],
                },
            }
        )
        data = bytearray(0x100)
        data[0x20 : 0x24] = bytes.fromhex(before)
        snapshot = bytes(data)
        with self.assertRaisesRegex(PatcherError, "overlap"):
            _relocate_expanded_shr_fun_patches(
                VV5_BUILD, "experimental_expanded_256", [feature], data
            )
        self.assertEqual(bytes(data), snapshot)

    def test_vv3_render_rejects_negative_manifest_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "synthetic-vv3-input.bin"
            data = bytearray(0x200)
            data[:2] = b"MZ"
            data[0x3C:0x40] = (0x80).to_bytes(4, "little")
            data[0x80:0x84] = b"PE\0\0"
            data[0x94:0x96] = (0xE0).to_bytes(2, "little")
            data[0x98:0x9A] = (0x10B).to_bytes(2, "little")
            source.write_bytes(data)
            last = data[-1]
            build = Record(
                {
                    "id": "vv3",
                    "title": "Synthetic VV3",
                    "size": len(data),
                    "input_name": source.name,
                    "villager_slots": 150,
                    "variants": {"collection_progression": {"patches": []}},
                    "safety_patches": [],
                }
            )
            feature = FunPatch(
                {
                    "id": "test_vv3_negative_offset",
                    "name": "test VV3 negative offset",
                    "game_id": "vv3",
                    "patches": [
                        {
                            "offset": "-1",
                            "before": f"{last:02X}",
                            "after": f"{last ^ 1:02X}",
                            "purpose": "adversarial negative offset",
                        }
                    ],
                    "patch_mode_overrides": {},
                }
            )
            with self.assertRaisesRegex(PatcherError, "outside the input buffer"):
                render_patched_bytes(
                    source,
                    build,
                    "collection_progression",
                    _fun_patches_override=[feature],
                )

    def test_append_header_rejects_out_of_buffer_offset_before_mutation(self) -> None:
        feature = FunPatch(
            {
                "id": "test_bad_append_header_offset",
                "name": "test bad append header offset",
                "game_id": "vv3",
                "patches": [],
                "pe_append_transaction": {
                    "layouts": {
                        "experimental_expanded_256": {
                            "original_file_size": "0x8",
                            "append_offset": "0x8",
                            "append_bytes": "00" * 0x1000,
                            "purpose": "adversarial append",
                            "header_patches": [
                                {
                                    "offset": "-1",
                                    "before": "00",
                                    "after": "01",
                                    "purpose": "adversarial negative header offset",
                                }
                            ],
                        }
                    }
                },
            }
        )
        data = bytearray(8)
        before = bytes(data)
        with self.assertRaisesRegex(PatcherError, "outside the input buffer"):
            _apply_pe_append_transactions(
                data,
                [feature],
                "experimental_expanded_256",
            )
        self.assertEqual(bytes(data), before)


if __name__ == "__main__":
    unittest.main()
