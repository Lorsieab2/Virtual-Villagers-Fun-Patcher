from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scripts.build_vv1_birth_control_page import build_page  # noqa: E402
from vv_fun_patcher import load_fun_patches  # noqa: E402


VV1_SHA256 = "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D"
VV3_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
VV1_PAGE_SHA256 = "E57E3FE69130016983BAC737A894C0BB62D62288A15023B01D52C2F946958AE8"
VV1_REJECTED_OFFSETS = {0x3DBBE, 0x458D0, 0x447840, 0x45930, 0x56740}


def _patches(feature_id: str) -> list[dict[str, str]]:
    feature = next(item for item in load_fun_patches() if item.id == feature_id)
    return list(feature.raw.get("patches", []))


class VV1VV3BirthControlTests(unittest.TestCase):
    def test_exact_stock_hashes_are_recorded_for_both_new_features(self) -> None:
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))["games"]
        by_id = {item["id"]: item for item in builds}
        self.assertEqual(by_id["vv1"]["sha256"], VV1_SHA256)
        self.assertEqual(by_id["vv3"]["sha256"], VV3_SHA256)

    def test_vv1_has_six_guarded_hooks_and_owned_page_in_every_layout(self) -> None:
        patches = _patches("vv1_birth_control")
        expected = {
            0x3DD03: ("83BD5003000002", "E9F82205009090"),
            0x46E96: ("813868010000", "E9A591040090"),
            0x47084: ("813968010000", "E9F78F040090"),
            0x477FA: ("3950F47C2A", "E9C1880400"),
            0x39C80: ("83FE01", "83FE05"),
            0x39C83: ("0F8E99FEFFFF", "E97864050090"),
        }
        self.assertEqual(len(patches), 6)
        for patch in patches:
            offset = int(patch["offset"], 0)
            with self.subTest(offset=hex(offset)):
                self.assertEqual(
                    (patch["before"], patch["after"]), expected[offset]
                )
                self.assertNotIn(offset, VV1_REJECTED_OFFSETS)

        feature = next(item for item in load_fun_patches() if item.id == "vv1_birth_control")
        layouts = feature.raw["pe_append_transaction"]["layouts"]
        for mode, layout in layouts.items():
            with self.subTest(mode=mode):
                self.assertEqual(layout["append_offset"], "0x8E000")
                self.assertEqual(layout["append_length"], 0x1000)
                self.assertEqual(layout["append_source"], "generated:vv1_birth_control_page")
                self.assertEqual(layout["page_virtual_address"], "0x490000")
                self.assertEqual(layout["page_sha256"], VV1_PAGE_SHA256)

    def test_vv1_page_builder_is_deterministic_and_has_no_unresolved_jumps(self) -> None:
        page, details = build_page()
        self.assertEqual(len(page), 0x1000)
        self.assertEqual(hashlib.sha256(page).hexdigest().upper(), VV1_PAGE_SHA256)
        self.assertEqual(details["page_sha256"], VV1_PAGE_SHA256)
        self.assertEqual(page[0x000:0x007], bytes.fromhex("83BD5003000002"))
        self.assertEqual(page[0x040:0x046], bytes.fromhex("813868010000"))
        self.assertEqual(page[0x080:0x086], bytes.fromhex("813968010000"))
        self.assertEqual(page[0x0C0:0x0C7], bytes.fromhex("8178F468010000"))
        self.assertEqual(page[0x100:0x106], bytes.fromhex("0F8E3E000000"))
        self.assertIn(bytes.fromhex("817FD003000002"), page)
        self.assertNotIn(bytes.fromhex("E900000000"), page)

    def test_vv3_removes_only_the_five_initiator_upper_checks(self) -> None:
        patches = _patches("vv3_birth_control")
        expected = {
            "0x5CE74": "81FAE80300007D5A",
            "0x5CF35": "81FAE80300007D60",
            "0x5CFFC": "81FAE80300007D5D",
            "0x5D0C0": "81FAE80300007D60",
            "0x5D187": "81FAE80300007D60",
        }
        self.assertEqual([int(patch["offset"], 0) for patch in patches], [int(offset, 0) for offset in expected])
        for patch in patches:
            with self.subTest(offset=patch["offset"]):
                self.assertEqual(patch["before"], expected[patch["offset"]])
                self.assertEqual(patch["after"], "9090909090909090")
        self.assertNotIn(0x4584B0, {int(p["offset"], 0) for p in patches})

    def test_vv1_birth_control_does_not_overlap_vv1_origins_ranges(self) -> None:
        catalog = load_fun_patches()
        birth_control = next(item for item in catalog if item.id == "vv1_birth_control")
        origins = next(item for item in catalog if item.id == "vv1_enable_origins_exclusive_features")

        def ranges(feature) -> list[range]:
            edits = list(feature.raw.get("patches", []))
            for mode_edits in feature.raw.get("patch_mode_overrides", {}).values():
                edits.extend(mode_edits)
            result = [
                range(int(patch["offset"], 0), int(patch["offset"], 0) + len(bytes.fromhex(patch["after"])))
                for patch in edits
            ]
            transaction = feature.raw.get("pe_append_transaction", {})
            for patch in transaction.get("layouts", {}).get("stock", {}).get("header_patches", []):
                result.append(range(int(patch["offset"], 0), int(patch["offset"], 0) + len(bytes.fromhex(patch["after"]))))
            layout = transaction.get("layouts", {}).get("stock")
            if layout:
                start = int(layout["append_offset"], 0)
                result.append(range(start, start + int(layout["append_length"])))
            return result

        self.assertTrue(all(a.stop <= b.start or b.stop <= a.start for a in ranges(birth_control) for b in ranges(origins)))


if __name__ == "__main__":
    unittest.main()
