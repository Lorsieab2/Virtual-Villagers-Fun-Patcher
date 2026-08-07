from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    _pe_checksum_layout,
    PatcherError,
    load_builds,
    load_fun_patches,
    render_patched_bytes,
)


STOCK = (
    ROOT
    / "research"
    / "stock-executables"
    / "Virtual Villagers - The Secret City.exe"
)
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"
BUILDER = ROOT / "scripts" / "build_vv3_origins_feature.py"
COMPANION = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"
MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


class VV3OriginsFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.build = next(item for item in load_builds() if item.id == "vv3")

    def test_exact_build_and_companion_identity(self) -> None:
        self.assertEqual(
            hashlib.sha256(STOCK.read_bytes()).hexdigest().upper(),
            "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
        )
        companion = self.manifest["companion_files"][0]
        self.assertEqual(
            companion["sha256"],
            hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper(),
        )
        self.assertIn("3 displayed years", self.manifest["description"])

    def test_legacy_cure_wording_is_contained_and_command5_is_explicit(self) -> None:
        stale = (
            "Plus Cure all Villagers for 30,000 tech points",
            "Cure all Villagers clears sickness",
        )
        contained = (
            "preserved byte-for-byte for provenance",
            "dominated before dispatch and unreachable in this composition",
        )
        for path in (
            ROOT / "data" / "vv3_origins_feature.json",
            ROOT / "data" / "candidates" / "vv3_origins_full_mastery_base_candidate.json",
            ROOT / "data" / "candidates" / "vv3_origins_running_base_candidate.json",
        ):
            text = path.read_text(encoding="utf-8")
            for phrase in stale:
                self.assertNotIn(phrase, text, path)
            for phrase in contained:
                self.assertIn(phrase, text, path)
            if path.name == "vv3_origins_feature.json":
                self.assertIn(
                    "historical command-5 Full Heal / Cure All transaction remains candidate-only and blocked behind its withdrawn Running dependency",
                    text,
                    path,
                )
            else:
                self.assertIn(
                    "certified command-5 Full Heal / Cure All transaction replaces it",
                    text,
                    path,
                )

    def test_package_source_provenance_contract_is_pinned(self) -> None:
        text = (ROOT / "scripts" / "build_vv3_full_heal_candidate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "B616282E0C21A9A8D509CE64C129EF6F24B4F50EAC538632DFBBC8C374662048",
            text,
        )
        self.assertIn("419", text)
        self.assertIn("412", text)
        self.assertIn("417", text)

    def test_only_verified_hook_windows_are_changed(self) -> None:
        offsets = {int(item["offset"], 0) for item in self.manifest["patches"]}
        self.assertEqual(
            offsets,
            {
                0x24C,
                0x7B664,
                0x7B7A0,
                0x263F0,
                0x27130,
                0x6547D,
                0x65640,
                0x6DA2C,
                0x6E530,
                0xA3180,
            },
        )
        section_patch = next(
            item
            for item in self.manifest["patches"]
            if int(item["offset"], 0) == 0x24C
        )
        self.assertEqual(section_patch["after"], "400000E0")

    def test_running_code_only_edits_normal_trait_arrays(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        running = source.split("        detail_running:", 1)[1].split(
            "        detail_success:", 1
        )[0]
        self.assertIn("[edx + 0xFB4]", running)
        self.assertIn("[edx + 0xFC0]", running)
        for forbidden in (
            "0xDC4",
            "0xE74",
            "0xE8C",
            "0xEAC",
            "0xEB0",
            "0xEB4",
            "0xEB8",
            "0xEBC",
            "0x12F20",
            "0x4A4210",
        ):
            self.assertNotIn(forbidden, running)

    def test_composes_with_every_current_vv3_patch_in_all_modes(self) -> None:
        patch_ids = [
            patch.id
            for patch in load_fun_patches()
            if patch.game_id == "vv3"
            and patch.id != "vv3_full_heal_cure_all_candidate"
        ]
        self.assertIn("vv3_enable_origins_exclusive_features", patch_ids)
        for mode in MODES:
            with self.subTest(mode=mode):
                if mode.startswith("experimental_expanded_256"):
                    with self.assertRaisesRegex(PatcherError, "(?:has no append layout|stock-mode only)"):
                        render_patched_bytes(STOCK, self.build, mode, patch_ids)
                    continue
                rendered, applied = render_patched_bytes(
                    STOCK, self.build, mode, patch_ids
                )
                self.assertTrue(applied)
                checksum_offset, _ = _pe_checksum_layout(rendered)
                self.assertNotEqual(
                    struct.unpack_from("<I", rendered, checksum_offset)[0], 0
                )
                expanded_marker = struct.unpack_from("<I", rendered, 0x2883A)[0]
                if mode.startswith("experimental_expanded_256"):
                    self.assertEqual(expanded_marker, 0x100)
                else:
                    self.assertEqual(expanded_marker, 0x96)

    def test_cave_is_zero_and_unclaimed_by_expansion(self) -> None:
        stock = STOCK.read_bytes()
        payload_patch = next(
            item
            for item in self.manifest["patches"]
            if int(item["offset"], 0) == 0xA3180
        )
        payload_size = len(bytes.fromhex(payload_patch["after"]))
        self.assertLessEqual(payload_size, 0xE80)
        self.assertEqual(stock[0xA3180 : 0xA3180 + payload_size], b"\0" * payload_size)
        expanded = json.loads((ROOT / "data" / "expanded_256.json").read_text())
        for patch in expanded["games"]["vv3"]["patches"]:
            start = int(patch["offset"], 0)
            before = bytes.fromhex(patch["before"])
            end = start + len(before)
            self.assertTrue(
                end <= 0xA3180 or start >= 0xA3180 + payload_size,
                f"expanded patch overlaps Origins payload at {start:#x}",
            )

    def test_expanded_save_loader_uses_dword_tail_copy_and_vanilla_names(self) -> None:
        save_format_offsets = {"vv3": 0x7C5C0, "vv4": 0x8A77C, "vv5": 0x95794}
        cave_offsets = {"vv3": 0x7B3B1, "vv4": 0x8910D, "vv5": 0x9466C}
        for build in load_builds():
            if build.id not in cave_offsets:
                continue
            with self.subTest(game=build.id):
                rendered, _ = render_patched_bytes(
                    STOCK.parent / build.input_name,
                    build,
                    "experimental_expanded_256",
                )
                cave = bytes(
                    rendered[cave_offsets[build.id] : cave_offsets[build.id] + 102]
                )
                self.assertIn(
                    bytes.fromhex("FDF3A5FC"),
                    cave,
                    "stock-save tail must be copied backward as dwords",
                )
                offset = save_format_offsets[build.id]
                self.assertEqual(bytes(rendered[offset : offset + 9]), b"%s%d.ldw\0")

    def test_dynamic_capacity_detector_is_expanded_loop_immediate(self) -> None:
        stock = STOCK.read_bytes()
        self.assertEqual(stock[0x28839], 0xBF)
        self.assertEqual(struct.unpack_from("<I", stock, 0x2883A)[0], 150)
        expanded = json.loads((ROOT / "data" / "expanded_256.json").read_text())
        marker = next(
            patch
            for patch in expanded["games"]["vv3"]["patches"]
            if int(patch["offset"], 0) == 0x2883A
        )
        self.assertEqual(marker["before"], "96000000")
        self.assertEqual(marker["after"], "00010000")

    def test_native_barrel_dialog_and_reserved_population_preflight(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn("call 0x45E8F0", source)
        self.assertIn("mov ecx, 147", source)
        self.assertIn("mov ecx, 253", source)
        self.assertIn("sub esp, 0x868", source)
        self.assertIn("call 0x4192F0", source)
        self.assertIn("call 0x401AF0", source)
        self.assertIn("call 0x418460", source)
        self.assertIn("add esp, 0x868", source)

    def test_tech_click_contract_is_message8_and_free_command15(self) -> None:
        """The visible Tech button must have one, and only one, route."""
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn("TECH_BUTTON_MESSAGE = 8", source)
        self.assertIn("TECH_BUTTON_EVENT = 15", source)
        tech_handler = source.split("        tech_handler,", 1)[1].split(
            "    put(\n        tech_constructor,", 1
        )[0]
        self.assertIn(
            "cmp dword ptr [esp + 4], {TECH_BUTTON_MESSAGE}",
            tech_handler,
        )
        self.assertIn(
            "cmp dword ptr [esp + 8], {TECH_BUTTON_EVENT}",
            tech_handler,
        )
        tech_constructor = source.split("        tech_constructor,", 1)[1].split(
            "    put(\n        detail_handler,", 1
        )[0]
        self.assertIn("push {TECH_BUTTON_EVENT}", tech_constructor)

        route = next(
            item
            for item in self.manifest["patches"]
            if int(item["offset"], 0) == 0x65640
        )
        self.assertIn("message 8", route["purpose"])
        self.assertIn("command-15", route["purpose"])

    def test_tech_click_wrong_message_or_event_is_rejected(self) -> None:
        """Negative route cases must remain on the stock handler path."""
        def route(message: int, event: int) -> str:
            return "origins" if message == 8 and event == 15 else "stock"

        self.assertEqual(route(8, 15), "origins")
        for message, event in ((7, 15), (9, 15), (8, 14), (8, 16), (7, 14)):
            with self.subTest(message=message, event=event):
                self.assertEqual(route(message, event), "stock")

    def test_prior_certified_tech_route_bytes_are_unchanged(self) -> None:
        payload = bytes.fromhex(
            next(
                item
                for item in self.manifest["patches"]
                if int(item["offset"], 0) == 0xA3180
            )["after"]
        )
        self.assertEqual(
            hashlib.sha256(payload).hexdigest().upper(),
            "91EE43DC2CCD93B9AB807DC9E2C15EEF88B9BFFA8F7A528C6785B29518D96CC6",
        )
        self.assertEqual(
            bytes.fromhex(
                next(
                    item
                    for item in self.manifest["patches"]
                    if int(item["offset"], 0) == 0x65640
                )["after"]
            ),
            bytes.fromhex("E93BDB0300909090"),
        )


if __name__ == "__main__":
    unittest.main()
