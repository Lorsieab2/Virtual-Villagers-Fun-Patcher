from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher


STOCK = ROOT / "research" / "stock-executables"
MODES = (
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)
OWNER = "automatic:vv3-expanded-detail-roster-layout"
BASE_RESULTS = {
    "experimental_expanded_256": (
        "13D8F8AFA2B8510C5371A33AE63B6D810432A08125899452BBE29F1A5627A936",
        "FDA30D00",
    ),
    "experimental_expanded_256_progression": (
        "CF1765D589F78827F721DEEBD269B88A1E4285CE68DCB0B89D05B2645A021502",
        "081F0D00",
    ),
}
TARGETED_IDS = [
    "vv3_nature_honey_refill",
    "vv3_nature_level_three_alters_mortality",
    "vv3_rare_collectible_retry",
    "vv3_write_village_statistics",
    "vv3_expanded_256_time_warp",
]
TARGETED_RESULTS = {
    "experimental_expanded_256": (
        "94B6282DFBD868EB04F12BD9CC48E8E2B6129906E8C4677483C5BB5210577758",
        "56380D00",
    ),
    "experimental_expanded_256_progression": (
        "4C3DC96B4B3FC2F7FA22436277EC1877EE35526E2F5C7AA3D03294D501F266B2",
        "60B30D00",
    ),
}


class VV3ExpandedDetailRosterLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = next(item for item in patcher.load_builds() if item.id == "vv3")
        cls.source = STOCK / cls.build.input_name

    def render(self, mode: str, ids: list[str] | None = None):
        return patcher.render_patched_bytes(
            self.source,
            self.build,
            mode,
            fun_patch_ids=ids or [],
        )

    @staticmethod
    def restore_layout_preimage(rendered: bytearray) -> None:
        size = patcher.VV3_EXPANDED_DETAIL_ROSTER_CLASS_SIZE
        offset = int(size["offset"], 0)
        rendered[offset : offset + 4] = bytes.fromhex(size["before"])
        for offset, before, _after in patcher.VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS:
            rendered[offset : offset + 4] = before.to_bytes(4, "little")

    def test_reviewed_table_is_exact_and_complete(self) -> None:
        rows = patcher.VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS
        self.assertEqual(len(rows), 150)
        self.assertEqual(len({offset for offset, _, _ in rows}), 150)
        self.assertEqual(
            hashlib.sha256(
                b"".join(struct.pack("<III", *row) for row in rows)
            ).hexdigest().upper(),
            "64D4336A8536A816CC6D4EB88A8F9B2C80682669BBE94F331F0EE91AED24A61E",
        )
        self.assertTrue(all(after - before == 0x1A8 for _, before, after in rows))
        self.assertEqual(min(before for _, before, _ in rows), 0x260)
        self.assertEqual(max(before for _, before, _ in rows), 0x338)
        self.assertIn((0x6CB03, 0x2BC, 0x464), rows)
        self.assertIn((0x6E64D, 0x260, 0x408), rows)

    def test_both_expanded_modes_apply_exact_transaction(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = self.render(mode)
                expected_hash, expected_checksum = BASE_RESULTS[mode]
                self.assertEqual(hashlib.sha256(rendered).hexdigest().upper(), expected_hash)
                self.assertEqual(rendered[0x160:0x164].hex().upper(), expected_checksum)
                records = [row for row in applied if row.get("owner") == OWNER]
                self.assertEqual(len(records), 151)
                self.assertEqual(rendered[0x27A39:0x27A3D], bytes.fromhex("E4040000"))
                for offset, _before, after in patcher.VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS:
                    self.assertEqual(
                        rendered[offset : offset + 4],
                        after.to_bytes(4, "little"),
                    )
                self.assertEqual(rendered[0x6E2C2:0x6E2C6], bytes.fromhex("00010000"))
                self.assertEqual(rendered[0x5FA46:0x5FA4A], bytes.fromhex("886C1F00"))
                for patch in patcher.VV3_EXPANDED_CAPACITY_CORRECTIONS:
                    offset = int(patch["offset"], 0)
                    after = bytes.fromhex(patch["after"])
                    self.assertEqual(rendered[offset : offset + len(after)], after)

    def test_guard_failure_is_transactional(self) -> None:
        rendered, _ = self.render(MODES[0])
        self.restore_layout_preimage(rendered)
        bad_offset = patcher.VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS[77][0]
        rendered[bad_offset] ^= 1
        before = bytes(rendered)
        with self.assertRaisesRegex(
            patcher.PatcherError,
            "Details roster layout guard failed",
        ):
            patcher._apply_vv3_expanded_detail_roster_layout(
                rendered, self.build, MODES[0], set()
            )
        self.assertEqual(bytes(rendered), before)

    def test_origins_replayed_constructor_fields_join_transaction(self) -> None:
        rendered, _ = self.render(MODES[0])
        self.restore_layout_preimage(rendered)
        for offset, before, _after in patcher.VV3_EXPANDED_DETAIL_ORIGINS_REPLAY_DISPLACEMENTS:
            rendered[offset : offset + 4] = before.to_bytes(4, "little")
        records = patcher._apply_vv3_expanded_detail_roster_layout(
            rendered,
            self.build,
            MODES[0],
            {"vv3_enable_origins_exclusive_features"},
        )
        self.assertEqual(len(records), 153)
        for offset, _before, after in patcher.VV3_EXPANDED_DETAIL_ORIGINS_REPLAY_DISPLACEMENTS:
            self.assertEqual(rendered[offset : offset + 4], after.to_bytes(4, "little"))

    def test_origins_removal_rejects_corrupt_overlay_and_dependents_transactionally(self) -> None:
        base = patcher.FunPatch(json.loads(
            (ROOT / "data/candidates/vv3_origins_running_base_candidate.json").read_text(
                encoding="utf-8"
            )
        ))
        running = patcher.FunPatch(json.loads(
            (ROOT / "data/candidates/vv3_all_villagers_like_running_candidate.json").read_text(
                encoding="utf-8"
            )
        ))
        rendered, _ = patcher.render_patched_bytes(
            self.source,
            self.build,
            MODES[0],
            _fun_patches_override=[base, running],
        )

        corrupt_replay = bytearray(rendered)
        patcher._remove_feature_bytes(corrupt_replay, running, MODES[0])
        corrupt_replay[0xA3335] ^= 1
        replay_snapshot = bytes(corrupt_replay)
        with self.assertRaisesRegex(patcher.PatcherError, "Removal guard failed"):
            patcher._remove_feature_bytes(corrupt_replay, base, MODES[0])
        self.assertEqual(bytes(corrupt_replay), replay_snapshot)

        corrupt_atomic = bytearray(rendered)
        patcher._remove_feature_bytes(corrupt_atomic, running, MODES[0])
        corrupt_atomic[-1] ^= 1
        atomic_snapshot = bytes(corrupt_atomic)
        with self.assertRaisesRegex(patcher.PatcherError, "atomic import page differs"):
            patcher._remove_feature_bytes(corrupt_atomic, base, MODES[0])
        self.assertEqual(bytes(corrupt_atomic), atomic_snapshot)

    def test_stock_modes_are_byte_frozen(self) -> None:
        source = bytearray(self.source.read_bytes())
        for mode in ("collection_progression", "immediate_fixed"):
            with self.subTest(mode=mode):
                work = bytearray(source)
                self.assertEqual(
                    patcher._apply_vv3_expanded_detail_roster_layout(
                        work, self.build, mode, set()
                    ),
                    [],
                )
                self.assertEqual(work, source)

    def test_full_targeted_playtest_render_is_exact(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = self.render(mode, TARGETED_IDS)
                expected_hash, expected_checksum = TARGETED_RESULTS[mode]
                self.assertEqual(hashlib.sha256(rendered).hexdigest().upper(), expected_hash)
                self.assertEqual(rendered[0x160:0x164].hex().upper(), expected_checksum)
                self.assertEqual(
                    len([row for row in applied if row.get("owner") == OWNER]),
                    151,
                )
                self.assertEqual(rendered[0x27D57:0x27D5C], bytes.fromhex("E864163900"))
                self.assertEqual(rendered[0x28A4C:0x28A51], bytes.fromhex("E8AF073900"))


if __name__ == "__main__":
    unittest.main()
