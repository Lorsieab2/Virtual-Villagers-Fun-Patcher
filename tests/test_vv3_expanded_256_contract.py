from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from vv3_expanded_256_contract import (
    VV3_LAYOUT,
    VV3_PUBLICATION_BLOCKERS,
    VV3_STORED_INDEX_AUDIT,
    accept_save_layout,
    build_physical_record_pool,
    classify_index,
    publication_ready,
    record_from_pool,
    validate_vv3_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class VV3Expanded256ContractTests(unittest.TestCase):
    def test_reviewed_manifest_facts_are_pinned(self) -> None:
        manifest = json.loads(
            (ROOT / "data" / "expanded_256.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_vv3_manifest(manifest), ())

    def test_reviewed_manifest_partitions_fail_closed(self) -> None:
        manifest = json.loads(
            (ROOT / "data" / "expanded_256.json").read_text(encoding="utf-8")
        )
        mutations = {
            "physical pool": lambda patches: patches.__setitem__(
                next(i for i, row in enumerate(patches) if row["offset"] == "0x258"),
                {
                    **next(row for row in patches if row["offset"] == "0x258"),
                    "after": "18352200",
                },
            ),
            "bound operand": lambda patches: next(
                row for row in patches if row["purpose"] == "expand record loop bound"
            ).__setitem__("purpose", "unreviewed bound"),
            "reverse endpoint": lambda patches: next(
                row
                for row in patches
                if row["purpose"]
                == "move the VV3 mating spatial scan endpoint from record 149 to record 255"
            ).__setitem__("purpose", "unreviewed endpoint"),
            "candidate restore": lambda patches: next(
                row
                for row in patches
                if row["purpose"] == "restore expanded candidate-array stack frame"
            ).__setitem__("purpose", "unreviewed restore"),
            "tail relocation": lambda patches: next(
                row
                for row in patches
                if row["purpose"] == "relocate absolute .data tail reference"
            ).__setitem__("purpose", "unreviewed tail relocation"),
            ".shr relocation": lambda patches: next(
                row for row in patches if row["purpose"] == "move absolute .shr reference"
            ).__setitem__("purpose", "unreviewed .shr relocation"),
        }
        for label, mutate in mutations.items():
            broken = copy.deepcopy(manifest)
            mutate(broken["games"]["vv3"]["patches"])
            with self.subTest(label=label):
                self.assertTrue(validate_vv3_manifest(broken))

    def test_stock_import_expanded_save_and_reload_are_byte_stable(self) -> None:
        stock = bytes(
            (offset * 131 + 17) & 0xFF
            for offset in range(VV3_LAYOUT.stock_save_size)
        )
        expanded = accept_save_layout(stock)
        self.assertEqual(len(expanded), VV3_LAYOUT.expanded_save_size)
        self.assertEqual(accept_save_layout(expanded), expanded)
        self.assertEqual(accept_save_layout(accept_save_layout(stock)), expanded)
        self.assertEqual(
            expanded[: VV3_LAYOUT.gap_offset],
            stock[: VV3_LAYOUT.gap_offset],
        )
        self.assertEqual(
            expanded[
                VV3_LAYOUT.gap_offset : VV3_LAYOUT.gap_offset
                + VV3_LAYOUT.inserted_bytes
            ],
            b"\0" * VV3_LAYOUT.inserted_bytes,
        )
        self.assertEqual(
            expanded[VV3_LAYOUT.gap_offset + VV3_LAYOUT.inserted_bytes :],
            stock[VV3_LAYOUT.gap_offset :],
        )

    def test_loader_model_accepts_only_exact_stock_or_expanded_sizes(self) -> None:
        with self.assertRaises(ValueError):
            accept_save_layout(b"stock-size-minus-one" * 100)
        with self.assertRaises(ValueError):
            accept_save_layout(b"expanded-size-plus-one" * 100)

    def test_all_256_records_are_logical_and_four_padding_records_are_zero(self) -> None:
        records = [
            bytes([index]) * VV3_LAYOUT.live_record_stride
            for index in range(VV3_LAYOUT.logical_record_count)
        ]
        for sparse_hole in (150, 200):
            records[sparse_hole] = b"\0" * VV3_LAYOUT.live_record_stride
        pool = build_physical_record_pool(records)
        expected_size = (
            VV3_LAYOUT.physical_record_count * VV3_LAYOUT.live_record_stride
        )
        self.assertEqual(len(pool), expected_size)
        for index in (149, 150, 254, 255):
            expected = (
                b"\0" * VV3_LAYOUT.live_record_stride
                if index == 150
                else bytes([index]) * VV3_LAYOUT.live_record_stride
            )
            with self.subTest(index=index):
                self.assertEqual(record_from_pool(pool, index), expected)
        padding_start = VV3_LAYOUT.logical_record_count * VV3_LAYOUT.live_record_stride
        self.assertEqual(
            pool[padding_start:],
            b"\0" * (VV3_LAYOUT.padding_record_count * VV3_LAYOUT.live_record_stride),
        )
        for invalid in (256, 257, 258, 259, -1):
            with self.subTest(index=invalid), self.assertRaises(IndexError):
                record_from_pool(pool, invalid)

    def test_record_255_is_valid_but_byte_ff_sentinel_is_not_assumed(self) -> None:
        self.assertEqual(classify_index(255), "record")
        self.assertEqual(classify_index(256), "invalid")
        self.assertEqual(classify_index(259), "invalid")
        self.assertEqual(classify_index(0xFF, sentinel=0xFF), "sentinel")
        self.assertEqual(VV3_STORED_INDEX_AUDIT["status"], "incomplete")
        self.assertEqual(VV3_STORED_INDEX_AUDIT["sentinel"], "unresolved")

    def test_publication_remains_fail_closed_until_runtime_gates_close(self) -> None:
        self.assertFalse(publication_ready())
        self.assertGreaterEqual(len(VV3_PUBLICATION_BLOCKERS), 4)


if __name__ == "__main__":
    unittest.main()
