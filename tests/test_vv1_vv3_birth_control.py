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
    load_builds,
    load_fun_patches,
    render_patched_bytes,
    resolve_fun_patch_ids,
)


VV1_SHA256 = "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D"
VV3_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
VV1_PAGE_SHA256 = "07944F005CF5048EAF744BC33564FE86FCFBC72DF30FD03AF60CDEFC2EE105BE"
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

    def test_vv1_birth_control_overlap_is_fail_closed(self) -> None:
        catalog = load_fun_patches()
        origins = next(item for item in catalog if item.id == "vv1_enable_origins_exclusive_features")

        # Both independent features use the exact stock tail at 0x8E000.  They
        # remain independently selectable, but composition is explicitly
        # rejected so the generic append path can never corrupt either owner.
        self.assertIn("vv1_birth_control", origins.raw.get("conflicts", []))

    def test_vv1_birth_control_and_origins_co_selection_is_rejected(self) -> None:
        with self.assertRaisesRegex(PatcherError, "conflicts"):
            resolve_fun_patch_ids(
                ["vv1_birth_control", "vv1_enable_origins_exclusive_features"],
                game_id="vv1",
            )

    def test_vv1_maximal_compatible_sets_render_and_keep_birth_control_independent(self) -> None:
        """Exercise both complete VV1 selections split by the append owner.

        Origins owns the two-page .vv1mc/.vv1md append and Birth Control owns
        the one-page .vv1bc append.  The stock tail cannot host both layouts;
        each maximal compatible set must nevertheless remain renderable in all
        ordinary modes, with Birth Control covered as its own full selection.
        """
        builds = {build.id: build for build in load_builds()}
        all_vv1 = [patch.id for patch in load_fun_patches() if patch.game_id == "vv1"]
        maximal_sets = {
            "origins-family": [patch_id for patch_id in all_vv1 if patch_id != "vv1_birth_control"],
            "birth-control-family": [
                patch_id
                for patch_id in all_vv1
                if patch_id
                not in {
                    "vv1_enable_origins_exclusive_features",
                    "vv1_origins_village_wide_upgrades",
                }
            ],
        }
        for family, patch_ids in maximal_sets.items():
            with self.subTest(family=family):
                resolved = resolve_fun_patch_ids(patch_ids, game_id="vv1")
                if family == "origins-family":
                    self.assertIn("vv1_enable_origins_exclusive_features", resolved)
                    self.assertNotIn("vv1_birth_control", resolved)
                else:
                    self.assertIn("vv1_birth_control", resolved)
                    self.assertNotIn("vv1_enable_origins_exclusive_features", resolved)
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


if __name__ == "__main__":
    unittest.main()
