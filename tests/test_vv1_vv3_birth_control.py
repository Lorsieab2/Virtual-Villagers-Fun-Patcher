from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scripts.build_vv1_birth_control_page import build_page  # noqa: E402
from vv_fun_patcher import (  # noqa: E402
    PatcherError,
    _apply_pe_append_transactions,
    _remove_feature_bytes,
    load_builds,
    load_fun_patches,
    render_patched_bytes,
    resolve_fun_patch_ids,
)


VV1_SHA256 = "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D"
VV3_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
VV1_PAGE_SHA256 = "07944F005CF5048EAF744BC33564FE86FCFBC72DF30FD03AF60CDEFC2EE105BE"
VV1_STANDALONE_RENDER_SHA256 = {
    "vv1_birth_control": {
        "stock": "5B3D329D9B16E21DFD4C74F05B10A4A14E671C96AE481576E01914ED8FD8C4A5",
        "collection_progression": "C02F431266FB9AC5C9C6FD62EE92D1AEEC6C3AF699F907CBE698FA4784664054",
        "immediate_fixed": "C02F431266FB9AC5C9C6FD62EE92D1AEEC6C3AF699F907CBE698FA4784664054",
    },
    "vv1_enable_origins_exclusive_features": {
        "stock": "93EB16AD2A8EA6EFC9F7F6376332DBEC1DC10F3E68B518A1A2643882ACBF7B98",
        "collection_progression": "25FEE305906ADF67587A862D3038F78FA6BDAEA0F2DCECE1156FAFCEFB93BBFF",
        "immediate_fixed": "25FEE305906ADF67587A862D3038F78FA6BDAEA0F2DCECE1156FAFCEFB93BBFF",
    },
}
VV1_REJECTED_OFFSETS = {0x3DBBE, 0x458D0, 0x447840, 0x45930, 0x56740}
VV1_STOCK = ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe"


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
            0x46E96: ("813868010000", "E9E591040090"),
            0x47084: ("813968010000", "E93790040090"),
            0x477FA: ("3950F47C2A", "E901890400"),
            0x39C80: ("83FE01", "83FE05"),
            0x39C83: ("0F8E99FEFFFF", "E9B864050090"),
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
        # The "actor is not the category-2 carrier" branch must recompute the
        # candidate record from EBX*0x3D8+ESI rather than read a stale EDI --
        # see build_vv1_birth_control_page.py's own comment on this fix (EDI
        # is reassigned twice by the stock function before this splice point,
        # ending up as a small RNG(3)+5 integer, not a pointer).
        manual_candidate = bytes.fromhex("8BC369C0D803000003C681B848030000E8030000")
        self.assertIn(manual_candidate, page[0x000:0x080])
        self.assertNotIn(bytes.fromhex("81BF48030000E8030000"), page)
        # Regression pin for the second half of the same stale-EDI bug
        # (live crash at 0x43DDE1, Windows fault offset 0x3DDE1): the reject
        # path jumps into the stock block at 0x43DD9E, which dereferences the
        # candidate record out of EDI six times. EDI holds the RNG(3)+5
        # duration by this splice point, so the reject path MUST rebuild it as
        # esi + ebx*0x3D8 first. Without these bytes the manual drag-pair
        # crashes on rejection instead of on the age compare.
        manual_reject_restores_edi = bytes.fromhex("8BFB69FFD803000001F7")
        self.assertIn(manual_reject_restores_edi, page[0x000:0x080])
        self.assertEqual(page[0x080:0x086], bytes.fromhex("813868010000"))
        self.assertEqual(page[0x0C0:0x0C6], bytes.fromhex("813968010000"))
        self.assertEqual(page[0x100:0x107], bytes.fromhex("8178F468010000"))
        self.assertEqual(page[0x140:0x146], bytes.fromhex("0F8E3E000000"))
        self.assertIn(bytes.fromhex("817FD003000002"), page)
        self.assertIn(bytes.fromhex("6A64"), page)
        self.assertIn(bytes.fromhex("83C40483F84B"), page)
        self.assertNotIn(bytes.fromhex("E900000000"), page)

    def test_all_early_birth_control_records_state_literal_vv4_vv5_contract(self) -> None:
        features = {
            item.id: item
            for item in load_fun_patches()
            if item.id in {"vv1_birth_control", "vv2_birth_control", "vv3_birth_control"}
        }
        self.assertEqual(set(features), {"vv1_birth_control", "vv2_birth_control", "vv3_birth_control"})
        for feature in features.values():
            with self.subTest(feature=feature.id):
                text = " ".join(
                    [
                        feature.description,
                        *feature.raw.get("behavior_changes", []),
                        *feature.raw.get("explicit_non_changes", []),
                    ]
                )
                self.assertIn("25% non-preference fallback", text)
                self.assertIn("native", text.lower())
                self.assertIn("conception", text.lower())
                self.assertIn("delivery", text.lower())

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

    def test_vv1_birth_control_origins_overlay_contract_is_bounded(self) -> None:
        catalog = load_fun_patches()
        birth = next(item for item in catalog if item.id == "vv1_birth_control")
        origins = next(item for item in catalog if item.id == "vv1_enable_origins_exclusive_features")

        self.assertNotIn("vv1_birth_control", origins.raw.get("conflicts", []))
        transaction = birth.raw["pe_append_transaction"]
        overlay = transaction["composition_overlays"][origins.id]
        self.assertEqual(overlay["overlay_length"], 0x400)
        self.assertEqual(overlay["page_virtual_address"], "0x490C00")
        self.assertEqual(overlay["overlay_offset"], "0x8EC00")
        self.assertEqual(overlay["overlay_preimage"]["kind"], "zero_fill")
        self.assertEqual(overlay["overlay_preimage"]["length"], 0x400)
        self.assertEqual(
            overlay["hook_offsets"],
            ["0x3DD03", "0x46E96", "0x47084", "0x477FA", "0x39C83"],
        )
        builds = {build.id: build for build in load_builds()}
        origins_only, _ = render_patched_bytes(
            VV1_STOCK,
            builds["vv1"],
            "stock",
            [origins.id],
        )
        origins_code_page = origins_only[0x8E000:0x8F000]
        self.assertEqual(
            max(index for index, value in enumerate(origins_code_page) if value),
            0x8A0,
        )
        self.assertEqual(origins_code_page[0x8A1:], b"\x00" * 0x75F)
        self.assertEqual(origins_only[0x8F000:0x90000], b"\x00" * 0x1000)

    def test_vv1_append_base_precedes_overlay_independent_of_catalog_order(self) -> None:
        catalog = load_fun_patches()
        birth = next(item for item in catalog if item.id == "vv1_birth_control")
        origins = next(
            item
            for item in catalog
            if item.id == "vv1_enable_origins_exclusive_features"
        )
        composed = bytearray(VV1_STOCK.read_bytes())
        applied = _apply_pe_append_transactions(
            composed,
            [birth, origins],
            "stock",
        )
        append_records = [
            record
            for record in applied
            if record["offset"] in {"0x8E000", "0x8EC00"}
        ]
        self.assertEqual(
            [record["offset"] for record in append_records],
            ["0x8E000", "0x8EC00"],
        )
        self.assertEqual(
            [record["owner"] for record in append_records],
            [
                "feature:vv1_enable_origins_exclusive_features",
                "feature:vv1_birth_control",
            ],
        )
        self.assertEqual(
            composed[0x8EC00:0x8F000],
            build_page(0x490C00)[0][:0x400],
        )

    def test_vv1_birth_control_and_origins_co_selection_is_allowed(self) -> None:
        resolved = resolve_fun_patch_ids(
            ["vv1_birth_control", "vv1_enable_origins_exclusive_features"],
            game_id="vv1",
        )
        self.assertEqual(
            set(resolved),
            {"vv1_birth_control", "vv1_enable_origins_exclusive_features"},
        )

    def test_vv1_maximal_compatible_sets_render_and_keep_birth_control_independent(self) -> None:
        """Exercise standalone and composed VV1 selections in every normal mode."""
        builds = {build.id: build for build in load_builds()}
        maximal_sets = {
            "origins-family": ["vv1_enable_origins_exclusive_features"],
            "birth-control-family": ["vv1_birth_control"],
            "origins-plus-birth-control": [
                "vv1_birth_control",
                "vv1_enable_origins_exclusive_features",
            ],
            "all-current-vv1-features": [
                item.id for item in load_fun_patches() if item.game_id == "vv1"
            ],
        }
        for family, patch_ids in maximal_sets.items():
            with self.subTest(family=family):
                resolved = resolve_fun_patch_ids(patch_ids, game_id="vv1")
                self.assertEqual(set(resolved), set(patch_ids))
                for mode in ("stock", "collection_progression", "immediate_fixed"):
                    with self.subTest(mode=mode):
                        rendered, applied = render_patched_bytes(
                            VV1_STOCK,
                            builds["vv1"],
                            mode,
                            patch_ids,
                        )
                        self.assertGreater(len(applied), 0)
                        self.assertNotEqual(rendered, VV1_STOCK.read_bytes())
                        if family in {"origins-family", "birth-control-family"}:
                            feature_id = patch_ids[0]
                            self.assertEqual(
                                hashlib.sha256(rendered).hexdigest().upper(),
                                VV1_STANDALONE_RENDER_SHA256[feature_id][mode],
                            )
                        if family == "origins-plus-birth-control":
                            self.assertEqual(len(rendered), 0x90000)
                            self.assertEqual(
                                rendered[0x8EC00:0x8F000],
                                build_page(0x490C00)[0][:0x400],
                            )
                            self.assertEqual(
                                rendered[0x8F000:0x90000],
                                b"\x00" * 0x1000,
                            )

    def test_vv1_birth_control_hook_relocations_are_generated_for_overlay(self) -> None:
        builds = {build.id: build for build in load_builds()}
        rendered, _ = render_patched_bytes(
            VV1_STOCK,
            builds["vv1"],
            "stock",
            ["vv1_birth_control", "vv1_enable_origins_exclusive_features"],
        )
        self.assertEqual(rendered[0x3DD03:0x3DD03 + 7].hex().upper(), "E9F82E05009090")
        self.assertEqual(rendered[0x46E96:0x46E96 + 6].hex().upper(), "E9E59D040090")
        self.assertEqual(rendered[0x47084:0x47084 + 6].hex().upper(), "E9379C040090")
        self.assertEqual(rendered[0x477FA:0x477FA + 5].hex().upper(), "E901950400")
        self.assertEqual(rendered[0x39C83:0x39C83 + 6].hex().upper(), "E9B870050090")

    def test_vv1_composed_removal_requires_birth_control_before_origins(self) -> None:
        builds = {build.id: build for build in load_builds()}
        rendered, _ = render_patched_bytes(
            VV1_STOCK,
            builds["vv1"],
            "stock",
            ["vv1_birth_control", "vv1_enable_origins_exclusive_features"],
        )
        birth = next(item for item in load_fun_patches() if item.id == "vv1_birth_control")
        origins = next(
            item
            for item in load_fun_patches()
            if item.id == "vv1_enable_origins_exclusive_features"
        )
        with self.assertRaisesRegex(PatcherError, "remove Birth Control first"):
            _remove_feature_bytes(rendered, origins, "stock")
        _remove_feature_bytes(rendered, birth, "stock")
        expected_origins, _ = render_patched_bytes(
            VV1_STOCK,
            builds["vv1"],
            "stock",
            ["vv1_enable_origins_exclusive_features"],
        )
        self.assertEqual(rendered, expected_origins)
        _remove_feature_bytes(rendered, origins, "stock")
        checksum = 0x150  # exact VV1 PE checksum field offset (e_lfanew 0xF8 + 0x58)
        restored = bytearray(rendered)
        stock = bytearray(VV1_STOCK.read_bytes())
        restored[checksum : checksum + 4] = b"\x00" * 4
        stock[checksum : checksum + 4] = b"\x00" * 4
        self.assertEqual(restored, stock)


if __name__ == "__main__":
    unittest.main()
