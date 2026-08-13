from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher


FEATURE_ID = "vv3_everyone_tries_on_robe"
MODES = (
    "collection_progression",
    "immediate_fixed",
)
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
EXPANDED_PROTOTYPE = ROOT / "research" / "vv3-expanded-prototype.exe"
PAYLOAD_SHA256 = "0E9B56C94BAB762CD8690668CD2C96F36D5E7F4D9C3545C0EBD7A3C3726EE84E"
ZERO_CAVE_SHA256 = "22B94C6893BFC091BE2A9F454A045184DF6C0398CFFA2B4E90C0065DD6EEB1B0"
ISOLATED_RESULTS = {
    "stock": (
        "7C9C9198FFF3681316080CBAB3D54424E6887747DA97C8B26388E9F48C96FA2F",
        "4FC00C00",
    ),
}
RENDERED_RESULTS = {
    "collection_progression": (
        "C75EACEDBFDAD6D846AFD01D8F227291F5B6E2013B07E2C8A59AA111B2BBD8C0",
        "C2620D00",
    ),
    "immediate_fixed": (
        "D79888259910E818742F2EB5889BB15A3E75781E6A4F43BEB3906D86A02B58B1",
        "C0A40D00",
    ),
}
BASE_RESULTS = {
    "collection_progression": "D83FF587DB844C29515ECEDAE0E8C390038BA44854A4DF83DE16F3186F0AD27F",
    "immediate_fixed": "BB87E3ECFACCB1290860028FFC9444B8D15AF19392FE8D1448FDC6FC672378C1",
}
EXPANDED_COMPOSITION_RESULTS = {
    "experimental_expanded_256": (
        "20B68A0F5BA4E9869C4F7FD9C53E6E81610EDC259E9F4906C201CF7D519E237C",
        "67E80C00",
    ),
    "experimental_expanded_256_progression": (
        "CC0A7F1B17099C6F29BE0BC163BBDBDB94F43398CB6BC10905811645842A2282",
        "71630D00",
    ),
}
STOCK_CATALOG_COMPOSITION_RESULTS = {
    "collection_progression": (
                    "03F9CF804B881BB80EA5B9746D19B713F902CE3E30979A903C20B9440B09E405",
                    "CD590D00",
    ),
    "immediate_fixed": (
                    "BE73A3C44336130834E8180C49F32D32FF504332E419482A4E6467DF29EC0529",
                    "CB9B0D00",
    ),
}


def digest(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest().upper()


class VV3EveryoneTriesOnRobeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = next(item for item in patcher.load_builds() if item.id == "vv3")
        cls.feature = patcher.get_fun_patch(FEATURE_ID)
        cls.payload_row = next(
            row for row in cls.feature.patches if row["offset"] == "0xB4100"
        )
        cls.payload = bytes.fromhex(cls.payload_row["after"])

    def test_visible_optional_catalog_entry_is_unselected_by_default(self) -> None:
        raw = self.feature.raw
        self.assertTrue(raw["enabled"])
        self.assertTrue(raw["catalog_enabled"])
        self.assertFalse(raw["catalog_hidden"])
        self.assertFalse(raw["default_selected"])
        self.assertEqual(tuple(raw["supported_modes"]), ("stock", *MODES))
        self.assertEqual(raw.get("dependencies", []), [])
        self.assertEqual(
            patcher.resolve_fun_patch_ids([], game_id="vv3"),
            [],
        )
        self.assertEqual(
            patcher.resolve_fun_patch_ids([FEATURE_ID], game_id="vv3"),
            [FEATURE_ID],
        )

    def test_exact_reviewed_payload_and_three_owned_ranges(self) -> None:
        self.assertEqual(len(self.payload), 235)
        self.assertEqual(digest(self.payload), PAYLOAD_SHA256)
        self.assertEqual(self.payload[0xCD], 0x90)
        zero_cave = bytes.fromhex(self.payload_row["before"])
        self.assertEqual(len(zero_cave), 235)
        self.assertEqual(digest(zero_cave), ZERO_CAVE_SHA256)

        common = {row["offset"]: row for row in self.feature.patches}
        self.assertEqual(set(common), {"0x280", "0x29C", "0xB4100"})
        self.assertEqual(common["0x280"]["before"], "04000000")
        self.assertEqual(common["0x280"]["after"], "00100000")
        # D166 fix: the VirtualSize patch above only extended the declared
        # size of .shr; it never set the section's own executable
        # permission bit, so the robe wrapper it maps was written into a
        # page Windows would refuse to execute. This second patch adds the
        # missing permission bit (0x20000000) while preserving every other
        # bit already set on the section.
        self.assertEqual(common["0x29C"]["before"], "400000D0")
        self.assertEqual(common["0x29C"]["after"], "600000F0")
        for mode in MODES:
            rows = self.feature.raw["patch_mode_overrides"][mode]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["offset"], "0x22B2A")
            self.assertEqual(rows[0]["before"], "60194200")
            expected = "00117A00" if mode.startswith("experimental_") else "00816C00"
            self.assertEqual(rows[0]["after"], expected)

    def test_original_callback_gate_and_native_callback_fanout(self) -> None:
        # The wrapper first calls the unchanged stock callback and requires AL=1,
        # then requires its initiator to be active, living, non-nursing, and in
        # action 120 or 121. Every other eligible record is sent through that
        # same native callback, so stock success/failure and Chief selection stay
        # authoritative for every villager.
        original_call = bytes.fromhex("56B860194200FFD083C40488C384C0747B")
        initiator_gate = bytes.fromhex(
            "83BE100F0000007472"
            "83BE780E0000007E69"
            "83BE8C0E0000007560"
            "8B86240F000083F878740583F8797550"
        )
        self.assertEqual(self.payload.index(original_call), 12)
        self.assertEqual(self.payload.index(initiator_gate), 29)
        self.assertLess(self.payload.index(initiator_gate), self.payload.index(bytes.fromhex("BF24E15900")))
        self.assertNotIn(bytes.fromhex("800E0000"), self.payload)
        self.assertNotIn(bytes.fromhex("880E0000"), self.payload)

        self.assertIn(bytes.fromhex("81F996000000740881F900010000753A"), self.payload)
        self.assertIn(bytes.fromhex("BF24E15900"), self.payload)
        self.assertIn(bytes.fromhex("81C78C1F0000"), self.payload)
        self.assertIn(bytes.fromhex("83BF100F000000741F"), self.payload)
        self.assertIn(bytes.fromhex("83BF780E0000007E16"), self.payload)
        self.assertIn(bytes.fromhex("83BF8C0E000000750D"), self.payload)

        self.assertEqual(self.payload.count(bytes.fromhex("B860194200FFD0")), 2)
        self.assertNotIn(bytes.fromhex("6A79"), self.payload)
        self.assertNotIn(bytes.fromhex("6A78"), self.payload)
        self.assertNotIn(bytes.fromhex("B8B0114600FFD0"), self.payload)
        self.assertNotIn(bytes.fromhex("B870554500FFD0"), self.payload)
        self.assertNotIn(bytes.fromhex("B8301C4500FFD0"), self.payload)
        self.assertNotIn(bytes.fromhex("6A006A646A05"), self.payload)
        self.assertIn(bytes.fromhex("5157B860194200FFD083C40459"), self.payload)
        self.assertIn(bytes.fromhex("88D88D65F45F5E5B5DC3"), self.payload)

    def test_authenticated_stock_preimages_and_native_action_registrations(self) -> None:
        source = STOCK.read_bytes()
        self.assertEqual(len(source), 831488)
        self.assertEqual(digest(source), self.build.sha256)
        self.assertEqual(source[0x278:0x280].split(b"\0", 1)[0], b".shr")
        self.assertEqual(source[0x280:0x284], bytes.fromhex("04000000"))
        self.assertEqual(source[0x284:0x288], bytes.fromhex("00802C00"))
        self.assertEqual(source[0x288:0x28C], bytes.fromhex("00100000"))
        self.assertEqual(source[0x28C:0x290], bytes.fromhex("00400B00"))
        self.assertEqual(source[0x29C:0x2A0], bytes.fromhex("400000D0"))
        self.assertEqual(source[0x22B2A:0x22B2E], bytes.fromhex("60194200"))
        self.assertEqual(source[0x2883A:0x2883E], bytes.fromhex("96000000"))
        self.assertEqual(
            source[0x542E6:0x542F2],
            bytes.fromhex("68B01B45006A78E8BECEFEFF"),
        )
        self.assertEqual(
            source[0x542F2:0x542FE],
            bytes.fromhex("68301C45006A79E8B2CEFEFF"),
        )
        self.assertEqual(digest(source[0xB4000:0xB5000]), "AD7FACB2586FC6E966C004D7D1D16B024F5805FF7CB47C7A85DABD8B48892CA7")
        self.assertEqual(digest(source[0xB4100:0xB41EB]), ZERO_CAVE_SHA256)

    def test_isolated_authenticated_stock_and_expanded_prototype_results(self) -> None:
        cases = (
            ("stock", STOCK, "collection_progression"),
        )
        for name, path, mode in cases:
            with self.subTest(name=name):
                data = bytearray(path.read_bytes())
                rows = [
                    *self.feature.patches,
                    *self.feature.raw["patch_mode_overrides"][mode],
                ]
                for row in rows:
                    offset = int(row["offset"], 0)
                    before = bytes.fromhex(row["before"])
                    after = bytes.fromhex(row["after"])
                    self.assertEqual(data[offset : offset + len(before)], before)
                    data[offset : offset + len(after)] = after
                checksum_offset, _ = patcher._pe_checksum_layout(data)
                struct.pack_into("<I", data, checksum_offset, 0)
                struct.pack_into("<I", data, checksum_offset, patcher.pe_checksum(data))
                expected_hash, expected_checksum = ISOLATED_RESULTS[name]
                self.assertEqual(digest(data), expected_hash)
                self.assertEqual(data[checksum_offset : checksum_offset + 4].hex().upper(), expected_checksum)

    def test_current_renderer_modes_and_exact_uninstall_roundtrip(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = patcher.render_patched_bytes(
                    STOCK, self.build, mode, [FEATURE_ID]
                )
                expected_hash, expected_checksum = RENDERED_RESULTS[mode]
                self.assertEqual(digest(rendered), expected_hash)
                self.assertEqual(rendered[0x160:0x164].hex().upper(), expected_checksum)
                owner = [
                    row for row in applied
                    if row.get("owner") == f"feature:{FEATURE_ID}"
                ]
                self.assertEqual(len(owner), 4)
                intervals = sorted(
                    (int(row["offset"], 0), int(row["offset"], 0) + len(bytes.fromhex(row["after"])))
                    for row in owner
                )
                self.assertTrue(all(left[1] <= right[0] for left, right in zip(intervals, intervals[1:])))
                self.assertEqual(rendered[0x280:0x284], bytes.fromhex("00100000"))
                self.assertEqual(digest(rendered[0xB4100:0xB41EB]), PAYLOAD_SHA256)
                # D166 fix: .shr is now actually marked executable (bit
                # 0x20000000 added), not just declared bigger.
                self.assertEqual(rendered[0x29C:0x2A0], bytes.fromhex("600000F0"))
                if mode.startswith("experimental_"):
                    self.assertEqual(rendered[0x284:0x288], bytes.fromhex("00103A00"))
                    self.assertEqual(rendered[0x22B2A:0x22B2E], bytes.fromhex("00117A00"))
                    self.assertEqual(rendered[0x2883A:0x2883E], bytes.fromhex("00010000"))
                    self.assertEqual(rendered[0x27A39:0x27A3D], bytes.fromhex("E4040000"))
                    details = [
                        row for row in applied
                        if row.get("owner") == "automatic:vv3-expanded-detail-roster-layout"
                    ]
                    self.assertEqual(len(details), 151)
                    self.assertEqual(
                        len([
                            row for row in applied
                            if row.get("owner")
                            == "automatic:vv3-expanded-chief-candidate-assignment"
                        ]),
                        1,
                    )
                else:
                    self.assertEqual(rendered[0x284:0x288], bytes.fromhex("00802C00"))
                    self.assertEqual(rendered[0x22B2A:0x22B2E], bytes.fromhex("00816C00"))
                    self.assertEqual(rendered[0x2883A:0x2883E], bytes.fromhex("96000000"))

                baseline, _ = patcher.render_patched_bytes(STOCK, self.build, mode, [])
                self.assertEqual(digest(baseline), BASE_RESULTS[mode])
                removed = bytearray(rendered)
                rows = patcher._remove_feature_bytes(removed, self.feature, mode)
                self.assertEqual(len(rows), 4)
                self.assertEqual(removed, baseline)

    @unittest.skip("Expanded-256 modes were removed from the public patcher")
    def test_expanded_composition_keeps_automatic_repairs_and_removes_cleanly(self) -> None:
        compatible = [
            "vv3_nature_honey_refill",
            "vv3_nature_level_three_alters_mortality",
            "vv3_rare_collectible_retry",
            "vv3_write_village_statistics",
        ]
        for mode, expected in EXPANDED_COMPOSITION_RESULTS.items():
            with self.subTest(mode=mode):
                rendered, applied = patcher.render_patched_bytes(
                    STOCK, self.build, mode, [*compatible, FEATURE_ID]
                )
                self.assertEqual(digest(rendered), expected[0])
                self.assertEqual(rendered[0x160:0x164].hex().upper(), expected[1])
                self.assertEqual(rendered[0x27A39:0x27A3D], bytes.fromhex("E4040000"))
                self.assertEqual(
                    len([
                        row for row in applied
                        if row.get("owner") == "automatic:vv3-expanded-detail-roster-layout"
                    ]),
                    151,
                )
                self.assertEqual(
                    len([
                        row for row in applied
                        if row.get("owner")
                        == "automatic:vv3-expanded-chief-candidate-assignment"
                    ]),
                    1,
                )
                parent, _ = patcher.render_patched_bytes(
                    STOCK, self.build, mode, compatible
                )
                removed = bytearray(rendered)
                patcher._remove_feature_bytes(removed, self.feature, mode)
                self.assertEqual(removed, parent)

    def test_stock_composition_with_complete_current_vv3_catalog_is_exact(self) -> None:
        selected = [
            item.id for item in patcher.load_fun_patches()
            if item.game_id == "vv3"
        ]
        self.assertNotIn("vv3_full_mastery_all_stage_a_candidate", selected)
        for mode, expected in STOCK_CATALOG_COMPOSITION_RESULTS.items():
            with self.subTest(mode=mode):
                rendered, _ = patcher.render_patched_bytes(
                    STOCK, self.build, mode, selected
                )
                self.assertEqual(digest(rendered), expected[0])
                self.assertEqual(rendered[0x160:0x164].hex().upper(), expected[1])
                parent, _ = patcher.render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    [item for item in selected if item != FEATURE_ID],
                )
                removed = bytearray(rendered)
                patcher._remove_feature_bytes(removed, self.feature, mode)
                self.assertEqual(removed, parent)

    def test_owned_ranges_do_not_collide_with_existing_manifests_or_repairs(self) -> None:
        owned = ((0x280, 0x284), (0x22B2A, 0x22B2E), (0xB4100, 0xB41EB))
        ranges: list[tuple[int, int, str]] = []

        def add(row: dict, owner: str) -> None:
            offset = int(row["offset"], 0)
            if "before" in row:
                length = len(bytes.fromhex(row["before"]))
            else:
                length = int(row["length"])
            ranges.append((offset, offset + length, owner))

        manifest = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        for game in manifest["games"]:
            if game["id"] != "vv3":
                continue
            for row in game["safety_patches"]:
                add(row, "automatic:safety")
            for mode, variant in game["variants"].items():
                for row in variant["patches"]:
                    add(row, f"automatic:{mode}")
        for feature in patcher.load_fun_patches():
            if feature.game_id != "vv3" or feature.id == FEATURE_ID:
                continue
            for row in feature.patches:
                add(row, feature.id)
            for mode, rows in feature.raw.get("patch_mode_overrides", {}).items():
                for row in rows:
                    add(row, f"{feature.id}:{mode}")
        expanded = json.loads((ROOT / "data" / "expanded_256.json").read_text(encoding="utf-8"))
        for row in expanded["games"]["vv3"]["patches"]:
            add(row, "automatic:expanded")
        for row in (
            patcher.VV3_EXPANDED_HEALER_ENDPOINT_REPAIR,
            *patcher.VV3_EXPANDED_CAPACITY_CORRECTIONS,
            patcher.VV3_EXPANDED_CHIEF_CANDIDATE_ASSIGNMENT_REPAIR,
            patcher.VV3_EXPANDED_DETAIL_ROSTER_CLASS_SIZE,
        ):
            add(row, "automatic:reviewed-repair")
        ranges.extend(
            (offset, offset + 4, "automatic:details")
            for offset, _before, _after in patcher.VV3_EXPANDED_DETAIL_ROSTER_DISPLACEMENTS
        )
        collisions = [
            (hex(start), hex(end), owner, hex(left), hex(right))
            for start, end, owner in ranges
            for left, right in owned
            if start < right and left < end
        ]
        self.assertEqual(collisions, [])

    def test_corrupt_owned_preimages_fail_without_touching_source(self) -> None:
        for offset, label in ((0x280, "section"), (0x22B2A, "hook"), (0xB4100, "cave")):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / STOCK.name
                data = bytearray(STOCK.read_bytes())
                data[offset] ^= 1
                path.write_bytes(data)
                before = path.read_bytes()
                with self.assertRaisesRegex(patcher.PatcherError, "Byte guard failed"):
                    patcher.render_patched_bytes(
                        path, self.build, "collection_progression", [FEATURE_ID]
                    )
                self.assertEqual(path.read_bytes(), before)

    def test_shr_section_is_actually_executable_in_the_real_render(self) -> None:
        """Regression test for a crash-causing bug found by an independent
        PE re-parse of the real rendered output: the 0x280 patch extends
        .shr's declared VirtualSize, but a section's VirtualSize has no
        effect on whether Windows will execute code from it -- that's
        controlled by the section's own Characteristics bit 0x20000000,
        which nothing patched. The 235-byte robe wrapper this feature
        writes to 0xB4100 lived in a page Windows would refuse to execute.
        This feature has no dependency on the Origins feature (which fixes
        .shr's permissions for other VV3 patches), so any player selecting
        only "Everyone Tries on Robe" would hit this. Verified against the
        actual rendered PE section table, not the patch manifest's claims.
        """
        try:
            import pefile
        except ImportError:
            self.skipTest("pefile not available")

        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, _ = patcher.render_patched_bytes(
                    STOCK, self.build, mode, [FEATURE_ID]
                )
                pe = pefile.PE(data=bytes(rendered), fast_load=True)
                shr = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".shr")
                self.assertTrue(
                    bool(shr.Characteristics & 0x20000000),
                    ".shr is still not marked executable",
                )
                self.assertGreaterEqual(shr.Misc_VirtualSize, 0x1000)


if __name__ == "__main__":
    unittest.main()
