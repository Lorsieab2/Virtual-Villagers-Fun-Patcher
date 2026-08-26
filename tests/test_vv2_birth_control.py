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

from vv_fun_patcher import (  # noqa: E402
    PatcherError,
    _pe_checksum_layout,
    identify,
    load_builds,
    load_fun_patches,
    load_patch_modes,
    render_patched_bytes,
    resolve_fun_patch_ids,
)

FEATURE_ID = "vv2_birth_control"
STOCK = (
    ROOT
    / "research"
    / "stock-executables"
    / "Virtual Villagers - The Lost Children.exe"
)
BUILD_SHA256 = "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"
AUDIT_COMMIT = "74778bd6a7d3a17dd990636cf6d4e769466800c6"
BLOCKS = (
    (
        0x6488D,
        0x46488D,
        bytes.fromhex(
            "8B530883FA0275073DE80300007C1983BF38050000020F8594010000"
            "81F9E80300000F8D88010000"
        ),
        bytes.fromhex(
            "8B53083DE80300000F8DA2010000"
            "9090909090909090909090909090909090909090909090909090"
        ),
        0x464A3D,
    ),
    (
        0x64A8F,
        0x464A8F,
        bytes.fromhex(
            "8B530883FA0275073DE80300007C1983BF38050000020F85A7010000"
            "81F9E80300000F8D9B010000"
        ),
        bytes.fromhex(
            "8B53083DE80300000F8DB5010000"
            "9090909090909090909090909090909090909090909090909090"
        ),
        0x464C52,
    ),
)

EXCLUDED_STOCK_WINDOWS = (
    # Direct special outcomes.
    (0x22006, bytes.fromhex("E875990200")),  # Love Note -> pregnancy writer
    (0x4EB3E, bytes.fromhex("E83DCEFFFF")),  # Gong grants life -> writer
    (0x217F9, bytes.fromhex("E8C2B60200")),  # Silver Mirror -> clone constructor
    # Shared pregnancy writer and pending-delivery operations.
    (0x4B980, bytes.fromhex("578BF9E888F9FFFF84C00F8449010000")),
    (0x3BE8E, bytes.fromhex("E82D370100")),
    (0x3BF70, bytes.fromhex("898439400500")),
    (0x3BF85, bytes.fromhex("898439440500")),
    # Manual carrier checks remain completely stock.
    (
        0x4F7C8,
        bytes.fromhex(
            "8B8F38050000B8020000003BC8750C81BF30050000E80300007C1C"
            "3983380500000F856D03000081BB30050000E80300000F8D5D030000"
        ),
    ),
)

PREGNANCY_WRITER_CALLS = (
    (0x22006, bytes.fromhex("E875990200")),
    (0x4EB3E, bytes.fromhex("E83DCEFFFF")),
    (0x4F8F0, bytes.fromhex("E88BC0FFFF")),
    (0x4F930, bytes.fromhex("E84BC0FFFF")),
    (0x64A38, bytes.fromhex("E8436FFEFF")),
    (0x64C4D, bytes.fromhex("E82E6DFEFF")),
)


class VV2BirthControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = next(build for build in load_builds() if build.id == "vv2")
        cls.feature = next(patch for patch in load_fun_patches() if patch.id == FEATURE_ID)

    def test_exact_build_identity_and_fingerprint_refusal(self) -> None:
        self.assertEqual(self.build.size, 724_992)
        self.assertEqual(self.build.sha256, BUILD_SHA256)
        self.assertEqual(STOCK.stat().st_size, self.build.size)
        self.assertEqual(hashlib.sha256(STOCK.read_bytes()).hexdigest().upper(), BUILD_SHA256)
        self.assertEqual(identify(STOCK).id, "vv2")

        with tempfile.TemporaryDirectory() as temp:
            altered = Path(temp) / self.build.input_name
            data = bytearray(STOCK.read_bytes())
            data[0x100] ^= 1
            altered.write_bytes(data)
            with self.assertRaisesRegex(PatcherError, "not one of the five exact supported"):
                identify(altered)

    def test_manifest_has_exact_two_equal_length_guarded_blocks(self) -> None:
        self.assertEqual(self.feature.game_id, "vv2")
        self.assertEqual(self.feature.name, "Birth Control")
        self.assertEqual(len(self.feature.patches), 2)
        self.assertIn(AUDIT_COMMIT, self.feature.raw["evidence_status"])
        for patch, (offset, _, before, after, _) in zip(
            self.feature.patches, BLOCKS, strict=True
        ):
            with self.subTest(offset=hex(offset)):
                self.assertEqual(int(patch["offset"], 0), offset)
                self.assertEqual(bytes.fromhex(patch["before"]), before)
                self.assertEqual(bytes.fromhex(patch["after"]), after)
                self.assertEqual(len(before), 40)
                self.assertEqual(len(after), 40)
                self.assertEqual(STOCK.read_bytes()[offset : offset + 40], before)

    def test_new_blocks_preserve_edx_compare_eax_and_target_exact_boundaries(self) -> None:
        for _, va, _, after, target in BLOCKS:
            with self.subTest(va=hex(va)):
                self.assertEqual(after[:3], bytes.fromhex("8B5308"))
                self.assertEqual(after[3:8], bytes.fromhex("3DE8030000"))
                self.assertEqual(after[8:10], bytes.fromhex("0F8D"))
                displacement = struct.unpack_from("<i", after, 10)[0]
                self.assertEqual(va + 14 + displacement, target)
                self.assertEqual(after[14:], b"\x90" * 26)

    def test_feature_selection_and_deselection_are_all_or_none_in_every_mode(self) -> None:
        for mode in load_patch_modes():
            with self.subTest(mode=mode.id):
                selected, selected_applied = render_patched_bytes(
                    STOCK, self.build, mode.id, [FEATURE_ID]
                )
                deselected, deselected_applied = render_patched_bytes(
                    STOCK, self.build, mode.id, []
                )
                selected_feature = [
                    edit
                    for edit in selected_applied
                    if edit["owner"] == f"feature:{FEATURE_ID}"
                ]
                self.assertEqual(
                    [int(edit["offset"], 0) for edit in selected_feature],
                    [block[0] for block in BLOCKS],
                )
                self.assertFalse(
                    any(
                        edit["owner"] == f"feature:{FEATURE_ID}"
                        for edit in deselected_applied
                    )
                )
                for offset, _, before, after, _ in BLOCKS:
                    self.assertEqual(selected[offset : offset + 40], after)
                    self.assertEqual(deselected[offset : offset + 40], before)

    def test_guard_failure_is_atomic_and_returns_no_partial_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            altered = Path(temp) / self.build.input_name
            data = bytearray(STOCK.read_bytes())
            data[BLOCKS[1][0]] ^= 1
            altered.write_bytes(data)
            with self.assertRaisesRegex(PatcherError, "Byte guard failed at 0x64A8F"):
                render_patched_bytes(altered, self.build, "collection_progression", [FEATURE_ID])
            self.assertEqual(altered.read_bytes(), data)

    def test_only_two_blocks_and_checksum_differ_from_deselected_render(self) -> None:
        allowed = set()
        for offset, _, _, _, _ in BLOCKS:
            allowed.update(range(offset, offset + 40))
        for mode in load_patch_modes():
            with self.subTest(mode=mode.id):
                selected, _ = render_patched_bytes(STOCK, self.build, mode.id, [FEATURE_ID])
                deselected, _ = render_patched_bytes(STOCK, self.build, mode.id, [])
                checksum_offset, _ = _pe_checksum_layout(selected)
                allowed_with_checksum = allowed | set(range(checksum_offset, checksum_offset + 4))
                differences = {
                    index
                    for index, (left, right) in enumerate(zip(selected, deselected, strict=True))
                    if left != right
                }
                self.assertTrue(differences)
                self.assertTrue(differences.issubset(allowed_with_checksum))

    def test_special_outcomes_writer_and_delivery_paths_remain_exactly_stock(self) -> None:
        stock = STOCK.read_bytes()
        patched_intervals = [
            range(offset, offset + len(after))
            for offset, _, _, after, _ in BLOCKS
        ]
        for offset, expected in EXCLUDED_STOCK_WINDOWS + PREGNANCY_WRITER_CALLS:
            with self.subTest(stock_offset=hex(offset)):
                self.assertEqual(stock[offset : offset + len(expected)], expected)
                self.assertFalse(
                    any(
                        index in interval
                        for interval in patched_intervals
                        for index in range(offset, offset + len(expected))
                    )
                )

        for mode in load_patch_modes():
            with self.subTest(mode=mode.id):
                rendered, _ = render_patched_bytes(
                    STOCK, self.build, mode.id, [FEATURE_ID]
                )
                for offset, expected in EXCLUDED_STOCK_WINDOWS + PREGNANCY_WRITER_CALLS:
                    self.assertEqual(
                        rendered[offset : offset + len(expected)],
                        expected,
                        f"{mode.id} changed excluded stock path at {offset:#x}",
                    )

    def test_composes_with_complete_vv2_catalog_in_every_mode_without_overlap(self) -> None:
        catalog = [
            patch
            for patch in load_fun_patches()
            if patch.game_id == "vv2"
            and patch.id != "vv2_full_mastery_all_stage_a_candidate"
        ]
        ids = [patch.id for patch in catalog]
        selected = resolve_fun_patch_ids(ids, game_id="vv2", patches=catalog)
        self.assertIn(FEATURE_ID, selected)
        for mode in load_patch_modes():
            with self.subTest(mode=mode.id):
                rendered, applied = render_patched_bytes(
                    STOCK, self.build, mode.id, selected
                )
                self.assertEqual(len(rendered), self.build.size)
                owners = {edit["owner"] for edit in applied}
                self.assertTrue(
                    {f"feature:{patch_id}" for patch_id in selected}.issubset(owners)
                )
                feature_offsets = [
                    int(edit["offset"], 0)
                    for edit in applied
                    if edit["owner"] == f"feature:{FEATURE_ID}"
                ]
                self.assertEqual(feature_offsets, [0x6488D, 0x64A8F])

    def test_documentation_and_transparency_are_exact_and_deterministic(self) -> None:
        from scripts.generate_transparency_docs import build_document

        first = build_document()
        second = build_document()
        committed = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertEqual(first, committed)
        # Derive the heading from the patch data rather than hardcoding the
        # literal title: transparency-log.md is GENERATED, so a hardcoded
        # marker silently pins a stale doc instead of the contract and only
        # breaks when someone regenerates for an unrelated reason.
        patch = next(p for p in load_fun_patches() if p.id == FEATURE_ID)
        self.assertEqual(first.count(f"#### {patch.name} (`{patch.id}`)"), 1)
        for path in (
            ROOT / "README.md",
            ROOT / "How to Use.txt",
            ROOT / "docs" / "villager-breeding-overhaul-research.md",
            ROOT / "docs" / "transparency-log.md",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Birth Control", text)
        research = (
            ROOT / "docs" / "villager-breeding-overhaul-research.md"
        ).read_text(encoding="utf-8")
        for marker in (
            AUDIT_COMMIT,
            "0x6488D",
            "0x64A8F",
            "0x464A3D",
            "0x464C52",
            "writer-reaching opcode-12",
            "no male upper-age gate",
        ):
            self.assertIn(marker, research)
        self.assertIn("25% non-preference fallback", self.feature.description)
        self.assertIn("conception roll", self.feature.description)
        self.assertIn("pregnancy writer", self.feature.description)
        self.assertIn("delivery", self.feature.description)

    def test_special_outcome_exclusion_is_a_mandatory_cross_game_contract(self) -> None:
        research = (
            ROOT / "docs" / "villager-breeding-overhaul-research.md"
        ).read_text(encoding="utf-8")
        checklist = (
            ROOT / "docs" / "origins-player-runtime-checklist.md"
        ).read_text(encoding="utf-8")
        transparency = (
            ROOT / "docs" / "transparency-log.md"
        ).read_text(encoding="utf-8")
        combined = "\n".join((research, checklist, transparency))
        for marker in (
            "Hard special-outcome exclusion contract",
            "ordinary manual, autonomous, or catch-up",
            "Island Event pregnancy, birth, and child outcomes",
            "age, sex, preference, eligibility, conception, pregnancy, delivery",
            "capacity, RNG",
            "messages",
            "statistics",
            "state writes",
            "VV2 Gong of Wonder",
            "Love Note",
            "Silver Mirror",
            "pending delivery",
            "0x22006",
            "0x4EB3E",
            "0x217F9",
            "0x4B980",
        ):
            self.assertIn(marker, combined)
        self.assertIn("VV1 and VV3", research)
        self.assertIn("future GO", research)
        self.assertIn("VV3 remains ON HOLD", research)
        self.assertIn(
            "Do not interpret a special outcome bypassing Birth Control as a defect",
            " ".join(checklist.split()),
        )

    def test_machine_readable_non_changes_preserve_exact_scope(self) -> None:
        text = " ".join(self.feature.raw["explicit_non_changes"])
        for marker in (
            "manual carrier/female-only",
            "no male upper-age gate",
            "token 43 exact string work",
            "willingness token 39 learning",
            "planner logic",
            "pregnancy writer",
            "delivery",
            "save format",
            "RNG",
            "food",
            "fertility",
            "capacity",
            "messages",
            "statistics",
            "Love Note event",
            "Gong grant",
            "Silver Mirror clone",
            "direct/event births",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
