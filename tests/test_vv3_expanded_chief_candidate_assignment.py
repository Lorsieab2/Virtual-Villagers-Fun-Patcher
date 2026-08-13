from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher


STOCK = ROOT / "research" / "stock-executables"
MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
OWNER = "automatic:vv3-expanded-chief-candidate-assignment"
FUNCTION_RANGE = (0x5FB20, 0x5FBB4)
FUNCTION_SHA256 = (
    "B097C453C22FF7071037A9695B49B4793E46D3D7DB18266F2B6D9FAE3F94751E"
)
ROUTES = {
    "base": [],
    "time_warp": ["vv3_expanded_256_time_warp"],
    "time_warp_statistics": [
        "vv3_expanded_256_time_warp",
        "vv3_write_village_statistics",
    ],
    "hidden_targeted_playtest": [
        "vv3_nature_honey_refill",
        "vv3_nature_level_three_alters_mortality",
        "vv3_rare_collectible_retry",
        "vv3_write_village_statistics",
        "vv3_expanded_256_time_warp",
    ],
}
RESULTS = {
    "experimental_expanded_256": {
        "base": (
            "B83350E70CE2B01FED0FFE745467C6D78D7BB08C3C90E61EFD96809B20724DF6",
            "059F0D00",
            "13D8F8AFA2B8510C5371A33AE63B6D810432A08125899452BBE29F1A5627A936",
        ),
        "time_warp": (
            "B49CC315AB750D535F3C547BC6E5FC40D63FAE8AEA1ACECE91C1E8D066E9C3E5",
            "24160D00",
            "E650C489ADF03C46F004F73754EE8DC33D7B5FF1C17F5FE95E29D02EC58D10D3",
        ),
        "time_warp_statistics": (
            "F95E797E9C25081F2FDF6F21063FAD09CCAFF322129423C9C7784D3E09321E15",
            "950C0D00",
            "2E9A0D996CF1049343F529B0D95E784C5CCE568DE528164B63003368247634A1",
        ),
        "hidden_targeted_playtest": (
            "B67450DD20F28331D89AC94F89A6D80B08CA652DB0ECB7467187072CCCEC1230",
            "5E330D00",
            "94B6282DFBD868EB04F12BD9CC48E8E2B6129906E8C4677483C5BB5210577758",
        ),
        "legacy_origins_running": (
            "99443591BE92F1F44222DF336C0D8911C2C2F5D1DBC76F6ED9692CD4737F4ECE",
            "CBF10C00",
            "2F2D3929779038B09FD85ABF510320E68402E16BE3F968072A7E311EB7DA6070",
        ),
    },
    "experimental_expanded_256_progression": {
        "base": (
            "99DF385FD87545196B7B6BE8416AF618FC1B6C2018AD4DAC851C68D86CFDEE46",
            "101A0D00",
            "CF1765D589F78827F721DEEBD269B88A1E4285CE68DCB0B89D05B2645A021502",
        ),
        "time_warp": (
            "78479CDEE2C45123E11CC63AFCC260E336935982774CA923B7CCFD4DF0652F49",
            "2E910D00",
            "47803F97343B750BF91C6B555D9E2DF3AD5D562F2703AC433208EB17B1B0CFC4",
        ),
        "time_warp_statistics": (
            "1CE1E7B794433EA60F99FE31BC5397AD02C2995CDCABFE67D7C901D516B27E77",
            "9F870D00",
            "5463BC1804FBBB8863D8649B10B09A9B84973C7B1255B34CFFB08946F81A3DA2",
        ),
        "hidden_targeted_playtest": (
            "8833232B7253CF7BFC8CCE5750AB7120AD3F72CAD5B73DB3B8730D9E6E4E7964",
            "68AE0D00",
            "4C3DC96B4B3FC2F7FA22436277EC1877EE35526E2F5C7AA3D03294D501F266B2",
        ),
        "legacy_origins_running": (
            "EBE60C76439A3A33A25AEA3510172AD34F6E91E68168D3A3303AA82802413831",
            "D56C0D00",
            "1876DFC25744F3ED62C68AE2EC5D3D1B48C16864E11FFF954FC45E78A84C5838",
        ),
    },
}


class VV3ExpandedChiefCandidateAssignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = next(item for item in patcher.load_builds() if item.id == "vv3")
        cls.source = STOCK / cls.build.input_name
        cls.stock = cls.source.read_bytes()
        cls.legacy_features = [
            patcher.FunPatch(json.loads(
                (ROOT / "data/candidates/vv3_origins_running_base_candidate.json")
                .read_text(encoding="utf-8")
            )),
            patcher.FunPatch(json.loads(
                (ROOT / "data/candidates/vv3_all_villagers_like_running_candidate.json")
                .read_text(encoding="utf-8")
            )),
        ]

    def render(self, mode: str, ids: list[str] | None = None):
        return patcher.render_patched_bytes(
            self.source,
            self.build,
            mode,
            fun_patch_ids=ids or [],
        )

    @staticmethod
    def restore_broken_manifest_result(rendered: bytes | bytearray) -> bytearray:
        restored = bytearray(rendered)
        repair = patcher.VV3_EXPANDED_CHIEF_CANDIDATE_ASSIGNMENT_REPAIR
        offset = int(repair["offset"], 0)
        restored[offset : offset + 4] = bytes.fromhex(repair["before"])
        patcher._canonicalize_pe_checksum(restored)
        return restored

    def test_immutable_manifest_keeps_exact_broken_lineage_row(self) -> None:
        manifest = json.loads(
            patcher.EXPANDED_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        rows = [
            row
            for row in manifest["games"]["vv3"]["patches"]
            if int(row["offset"], 0) == 0x5FB9C
        ]
        self.assertEqual(rows, [{
            "offset": "0x5FB9C",
            "before": "9C0E0000",
            "after": "94130000",
            "purpose": "move expanded candidate-array stack reference",
        }])
        self.assertEqual(
            patcher.VV3_EXPANDED_CHIEF_CANDIDATE_ASSIGNMENT_REPAIR,
            {
                "offset": "0x5FB9C",
                "before": "94130000",
                "after": "9C0E0000",
                "purpose": (
                    "restore the native record-relative 0xE9C displacement used "
                    "to write the VV3 Tribal Chief candidate flag at record "
                    "offset 0xE88"
                ),
            },
        )

    def test_manifest_transition_then_overlay_restores_record_e88(self) -> None:
        work = bytearray(self.stock)
        self.assertEqual(work[0x5FB99:0x5FBA0], bytes.fromhex("8884319C0E0000"))
        work[0x5FB9C:0x5FBA0] = bytes.fromhex("94130000")
        self.assertEqual(work[0x5FB99:0x5FBA0], bytes.fromhex("88843194130000"))
        records = patcher._apply_vv3_expanded_chief_candidate_assignment_repair(
            work, self.build, MODES[0]
        )
        self.assertEqual(work[0x5FB99:0x5FBA0], bytes.fromhex("8884319C0E0000"))
        self.assertEqual(0xE9C - 0x14, 0xE88)
        self.assertEqual(records, [{
            "offset": "0x5FB9C",
            "before": "94130000",
            "after": "9C0E0000",
            "purpose": patcher.VV3_EXPANDED_CHIEF_CANDIDATE_ASSIGNMENT_REPAIR[
                "purpose"
            ],
            "owner": OWNER,
            "virtual_address": "0x45FB9C",
        }])

    def test_both_expanded_modes_keep_selector_scan_bound_and_frame_exact(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = self.render(mode)
                start, end = FUNCTION_RANGE
                self.assertEqual(
                    hashlib.sha256(rendered[start:end]).hexdigest().upper(),
                    FUNCTION_SHA256,
                )
                self.assertEqual(rendered[0x5FB20:0x5FB26], bytes.fromhex("81EC000C0000"))
                self.assertEqual(rendered[0x5FB2E:0x5FB34], bytes.fromhex("8D868C0E0000"))
                self.assertEqual(rendered[0x5FB78:0x5FB7E], bytes.fromhex("81FA00010000"))
                self.assertEqual(rendered[0x5FB99:0x5FBA0], bytes.fromhex("8884319C0E0000"))
                self.assertEqual(rendered[0x5FBA2:0x5FBA8], bytes.fromhex("81C4000C0000"))
                self.assertEqual(rendered[0x5FBAD:0x5FBB3], bytes.fromhex("81C4000C0000"))
                transitions = [
                    (row["owner"], row["before"], row["after"])
                    for row in applied
                    if int(row["offset"], 0) == 0x5FB9C
                ]
                self.assertEqual(transitions, [
                    ("automatic:population", "9C0E0000", "94130000"),
                    (OWNER, "94130000", "9C0E0000"),
                ])

    def test_base_time_warp_statistics_and_hidden_routes_change_only_repair(self) -> None:
        for mode in MODES:
            for route, ids in ROUTES.items():
                with self.subTest(mode=mode, route=route):
                    rendered, applied = self.render(mode, ids)
                    final_hash, checksum, prior_hash = RESULTS[mode][route]
                    self.assertEqual(hashlib.sha256(rendered).hexdigest().upper(), final_hash)
                    self.assertEqual(rendered[0x160:0x164].hex().upper(), checksum)
                    self.assertEqual(
                        hashlib.sha256(
                            self.restore_broken_manifest_result(rendered)
                        ).hexdigest().upper(),
                        prior_hash,
                    )
                    self.assertEqual(
                        len([row for row in applied if row.get("owner") == OWNER]),
                        1,
                    )

    def test_legacy_origins_running_routes_change_only_repair(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = patcher.render_patched_bytes(
                    self.source,
                    self.build,
                    mode,
                    _fun_patches_override=self.legacy_features,
                )
                final_hash, checksum, prior_hash = RESULTS[mode][
                    "legacy_origins_running"
                ]
                self.assertEqual(hashlib.sha256(rendered).hexdigest().upper(), final_hash)
                self.assertEqual(rendered[0x160:0x164].hex().upper(), checksum)
                self.assertEqual(
                    hashlib.sha256(
                        self.restore_broken_manifest_result(rendered)
                    ).hexdigest().upper(),
                    prior_hash,
                )
                self.assertEqual(
                    len([row for row in applied if row.get("owner") == OWNER]),
                    1,
                )

    def test_robe_route_bytes_are_frozen_around_automatic_overlay(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                repaired, _ = self.render(mode, ["vv3_everyone_tries_on_robe"])
                with mock.patch.object(
                    patcher,
                    "_apply_vv3_expanded_chief_candidate_assignment_repair",
                    return_value=[],
                ):
                    broken, _ = self.render(mode, ["vv3_everyone_tries_on_robe"])
                self.assertEqual(
                    self.restore_broken_manifest_result(repaired),
                    broken,
                )
                repair = patcher.VV3_EXPANDED_CHIEF_CANDIDATE_ASSIGNMENT_REPAIR
                offset = int(repair["offset"], 0)
                patched = bytearray(broken)
                records = patcher._apply_vv3_expanded_chief_candidate_assignment_repair(
                    patched, self.build, mode
                )
                patcher._canonicalize_pe_checksum(patched)
                self.assertEqual(patched, repaired)
                self.assertEqual(len(records), 1)
                self.assertEqual(offset, 0x5FB9C)

    def test_stock_modes_are_frozen_and_direct_overlay_is_noop(self) -> None:
        for mode in ("collection_progression", "immediate_fixed"):
            with self.subTest(mode=mode):
                rendered, applied = self.render(mode)
                direct = bytearray(rendered)
                self.assertEqual(
                    patcher._apply_vv3_expanded_chief_candidate_assignment_repair(
                        direct, self.build, mode
                    ),
                    [],
                )
                self.assertEqual(direct, rendered)
                self.assertFalse(any(row.get("owner") == OWNER for row in applied))
                self.assertEqual(
                    rendered[0x5FB99:0x5FBA0],
                    self.stock[0x5FB99:0x5FBA0],
                )

    def test_preimage_failure_is_transactional_and_exact_rollback_reapplies(self) -> None:
        rendered, _ = self.render(MODES[0])
        broken = self.restore_broken_manifest_result(rendered)
        broken[0x5FB9C] ^= 1
        snapshot = bytes(broken)
        with self.assertRaisesRegex(
            patcher.PatcherError,
            "Chief-candidate assignment repair guard failed",
        ):
            patcher._apply_vv3_expanded_chief_candidate_assignment_repair(
                broken, self.build, MODES[0]
            )
        self.assertEqual(bytes(broken), snapshot)

        rollback = self.restore_broken_manifest_result(rendered)
        records = patcher._apply_vv3_expanded_chief_candidate_assignment_repair(
            rollback, self.build, MODES[0]
        )
        patcher._canonicalize_pe_checksum(rollback)
        self.assertEqual(rollback, rendered)
        self.assertEqual(
            [(row["before"], row["after"]) for row in records],
            [("94130000", "9C0E0000")],
        )


if __name__ == "__main__":
    unittest.main()
