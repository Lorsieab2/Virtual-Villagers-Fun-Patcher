from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    _relocate_expanded_shr_fun_patches,
    load_builds,
)


FEATURE = json.loads(
    (ROOT / "data" / "vv5_origins_feature.json").read_text(encoding="utf-8")
)


class VV5Expanded256RelocationTests(unittest.TestCase):
    def test_selector_tail_rel32_uses_exact_instruction_boundary_and_target(self) -> None:
        row = next(
            item for item in self.relocation["patches"] if item["offset"] == "0xDB1A4"
        )
        payload = bytes.fromhex(self.feature["selector_repair"]["body"]["after"])
        payload_offset = int(self.feature["selector_repair"]["body"]["file_offset"], 0)
        local = 0xDB1A3 - payload_offset
        self.assertEqual(payload[local], 0xE9)
        self.assertEqual(payload[local + 1 : local + 5].hex().upper(), "7267C6FF")
        self.assertEqual(
            payload[0xDB1A0 - payload_offset : 0xDB1A4 - payload_offset].hex().upper(),
            "14C5FFE9",
        )
        self.assertEqual(row["source_virtual_address"], "0x8EB1A3")
        self.assertEqual(row["target_stock_virtual_address"], "0x41891A")
        self.assertEqual(row["target_expanded_virtual_address"], "0x41891A")
        stock_rel = int.from_bytes(bytes.fromhex(row["before"]), "little", signed=True)
        expanded_rel = int.from_bytes(bytes.fromhex("72D7B2FF"), "little", signed=True)
        self.assertEqual(0x7B21A3 + 5 + stock_rel, 0x41891A)
        self.assertEqual(0x8EB1A3 + 5 + expanded_rel, 0x41891A)
        self.assertNotIn("expanded_skip_before", row)

    def setUp(self) -> None:
        self.feature = copy.deepcopy(FEATURE)
        self.build = next(item for item in load_builds() if item.id == "vv5")
        self.relocation = self.feature["expanded_shr_relocations"]

    def _buffer(self) -> bytearray:
        data = bytearray(0xDC000)
        for item in self.relocation["patches"]:
            offset = int(item["offset"], 0)
            before = bytes.fromhex(item["before"])
            data[offset : offset + 4] = before
        return data

    def test_complete_ida_ledger_is_23_internal_plus_36_rel32_plus_7_external(self) -> None:
        evidence = self.relocation["evidence"]
        self.assertEqual(evidence["payload_internal_absolute_sites"], 23)
        self.assertEqual(evidence["cross_section_rel32_sites"], 36)
        self.assertEqual(evidence["external_absolute_sites"], 7)
        self.assertEqual(evidence["complete_current_feature_relocation_sites"], 43)
        self.assertEqual(len(self.relocation["patches"]), 66)
        self.assertEqual(
            sum(item.get("kind", "absolute") == "rel32" for item in self.relocation["patches"]),
            36,
        )
        self.assertEqual(
            sum(
                item.get("kind", "absolute") == "absolute"
                and "external" in item.get("purpose", "")
                for item in self.relocation["patches"]
            ),
            7,
        )

    def test_complete_ledger_offsets_are_frozen(self) -> None:
        expected_internal = {
            "0xDB087", "0xDB147", "0xDB1C3", "0xDB1D2", "0xDB21B", "0xDB22A",
            "0xDB354", "0xDB383", "0xDB399", "0xDB3B4", "0xDB3D5", "0xDB41E",
            "0xDB48E", "0xDB4C4", "0xDB4CB", "0xDB4D2", "0xDB4D8", "0xDB787",
            "0xDB793", "0xDB865", "0xDB88E", "0xDB895", "0xDB89B",
        }
        expected_rel32 = {
            "0x18910", "0x1EB70", "0x237B1", "0x40A25", "0x4AF13", "0x4BC21", "0x94FBF",
            "0xDB01C", "0xDB021", "0xDB043", "0xDB055", "0xDB06C", "0xDB08E", "0xDB096",
            "0xDB0E1", "0xDB103", "0xDB115", "0xDB12C", "0xDB14E", "0xDB156", "0xDB1A4",
            "0xDB272", "0xDB283", "0xDB292", "0xDB38D", "0xDB3C3", "0xDB3ED", "0xDB415",
            "0xDB437", "0xDB45A", "0xDB462", "0xDB46C", "0xDB7AC", "0xDBA56", "0xDBB22", "0xDBB27",
        }
        expected_external = {
            "0x94B80", "0x94B85", "0x94B94", "0x94ED1", "0x94ED6", "0x94EE5", "0x94FBA",
        }
        by_kind = {
            "internal": {
                item["offset"]
                for item in self.relocation["patches"]
                if item.get("kind", "absolute") == "absolute"
                and "external" not in item.get("purpose", "")
            },
            "rel32": {
                item["offset"]
                for item in self.relocation["patches"]
                if item.get("kind", "absolute") == "rel32"
            },
            "external": {
                item["offset"]
                for item in self.relocation["patches"]
                if item.get("kind", "absolute") == "absolute"
                and "external" in item.get("purpose", "")
            },
        }
        self.assertEqual(by_kind["internal"], expected_internal)
        self.assertEqual(by_kind["rel32"], expected_rel32)
        self.assertEqual(by_kind["external"], expected_external)

    def test_expanded_relocation_rewrites_only_guarded_rows_and_preserves_native_overrides(self) -> None:
        data = self._buffer()
        data[0x1EB70 : 0x1EB74] = bytes.fromhex("F67E3456")
        data[0x237B1 : 0x237B5] = bytes.fromhex("8B742408")
        applied = _relocate_expanded_shr_fun_patches(
            self.build,
            "experimental_expanded_256",
            [FunPatch(self.feature)],
            data,
        )
        self.assertEqual(
            {item["offset"] for item in applied},
            {item["offset"] for item in self.relocation["patches"]},
        )
        delta = int(self.relocation["expanded_virtual_address"], 0) - int(
            self.relocation["stock_virtual_address"], 0
        )
        for item in self.relocation["patches"]:
            offset = int(item["offset"], 0)
            actual = bytes(data[offset : offset + 4])
            if item.get("expanded_skip_before"):
                self.assertEqual(actual.hex().upper(), item["expanded_skip_before"])
            elif item.get("kind", "absolute") == "absolute":
                expected = int.from_bytes(bytes.fromhex(item["before"]), "little") + delta
                self.assertEqual(actual, expected.to_bytes(4, "little"))
            else:
                source = int(item["source_expanded_virtual_address"], 0)
                target = int(item["target_expanded_virtual_address"], 0)
                expected = (target - (source + 5)).to_bytes(4, "little", signed=True)
                self.assertEqual(actual, expected)

    def test_stock_mode_is_noop_and_broken_preimages_fail_closed(self) -> None:
        data = self._buffer()
        before = bytes(data)
        self.assertEqual(
            _relocate_expanded_shr_fun_patches(
                self.build, "collection_progression", [FunPatch(self.feature)], data
            ),
            [],
        )
        self.assertEqual(bytes(data), before)

        broken = self._buffer()
        broken[int("0xDB01C", 0)] ^= 1
        with self.assertRaisesRegex(PatcherError, "guard failed"):
            _relocate_expanded_shr_fun_patches(
                self.build,
                "experimental_expanded_256",
                [FunPatch(self.feature)],
                broken,
            )


if __name__ == "__main__":
    unittest.main()
