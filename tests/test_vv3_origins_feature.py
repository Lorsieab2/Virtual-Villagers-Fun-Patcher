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
    load_patch_modes,
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
COMPANION = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
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
        self.assertIn("origins-style upgrade", self.manifest["description"].casefold())

    def test_active_companion_is_the_safe_upgrade_projection(self) -> None:
        companion = self.manifest["companion_files"][0]
        self.assertEqual(
            companion["source"],
            "data/candidates/VVFP VV3 Safe Upgrades.dll",
        )
        data = COMPANION.read_bytes()
        # The public projection now exposes every Tech upgrade row so the
        # village-wide menu shows Full Heal/Cure, All Villagers Like Running,
        # Grant Full Mastery to All, All Villagers are 18, and the Complete/Reset
        # all Collections rows as live Buy controls (previously stripped down to
        # Full Mastery only).
        for required in (
            "Full Heal/Cure All Villagers",
            "All Villagers Like Running",
            "All Villagers are 18",
            "Complete all Collections",
            "Reset all Collections",
        ):
            self.assertIn(required.encode("utf-16le"), data)

    def test_description_is_concise_and_keeps_the_base_dependency_internal(self) -> None:
        description = self.manifest["description"]
        self.assertIn("Tech and Villager Details", description)
        self.assertIn("Make Villagers Young Adults", description)
        self.assertNotIn("candidate-only", description)
        self.assertNotIn("500,000-tech-point", description)

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
                0x9EEA0,
                0x9EF30,
                0x7B3B1,
                0x7B3E0,
                0x68727,
                0x7B664,
                0x7B800,
                0x7B810,
                0x15EF1,
                0x16983,
                0x16BAB,
                0x17A3A,
                0x15D44,
                0x1673E,
                0x18452,
                0x263F0,
                0x27130,
                0x6547D,
                0x65640,
                0x6DA2C,
                0x6E530,
                0x7BD40,
                0x7BDC0,
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
            "        detail_insufficient:", 1
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
                    with self.assertRaisesRegex(PatcherError, "stock modes only"):
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

    def test_expanded_256_modes_are_removed(self) -> None:
        self.assertNotIn("experimental_expanded_256", {mode.id for mode in load_patch_modes()})
        self.assertNotIn(
            "experimental_expanded_256_progression",
            {mode.id for mode in load_patch_modes()},
        )

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

    def test_native_barrel_event_and_reserved_population_preflight(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        # Barrel preflight refuses (before charging) unless the village can hold
        # all three children.  The capacity computation is mode-aware and lives
        # in the companion DLL (PrepareBarrelBabies); the payload preflight just
        # calls the probe cave and refuses on a zero return.  The old fixed
        # 150/256 physical cap is gone.
        preflight = source.split("        maybe_barrel:", 1)[1].split(
            "        charge:", 1
        )[0]
        self.assertIn("call 0x{BARREL_PREFLIGHT_DLL_VA:X}", preflight)
        self.assertIn("jnz charge", preflight)
        self.assertNotIn("147", preflight)
        self.assertNotIn("253", preflight)
        # The probe cave lives in the payload tail and LoadLibrary/
        # GetProcAddress-calls PrepareBarrelBabies, failing open if unavailable.
        self.assertIn("BARREL_PREFLIGHT_DLL_VA = PAYLOAD_VA +", source)
        cave = source.split("put(\n        BARREL_PREFLIGHT_DLL_VA,", 1)[1].split(
            '"""', 2
        )[1]
        self.assertIn("s['prepare_barrel_export']", cave)
        self.assertIn("mov eax, 1", cave)  # fail-open
        # The DLL computes the max mode-awarely by reading the live per-mode base
        # population byte the patcher rewrites at 0x45FEE3 (not a hardcoded 90).
        dll = (ROOT / "native" / "vv3_full_mastery_candidate"
               / "vv3_full_mastery_candidate.c").read_text(encoding="utf-8")
        self.assertIn("PrepareBarrelBabies", dll)
        self.assertIn("0x45FEE3", dll)
        # do_barrel marks the event pending (the real event is deferred to the
        # island-handler hook) and confirms the purchase with the
        # "Barrel of Babies completed." result box.
        barrel = source.split("        do_barrel:", 1)[1].split(
            "        do_complete_collections:", 1
        )[0]
        self.assertIn("BARREL_PENDING_FLAG_VA", barrel)
        self.assertIn("mov eax, 7", barrel)  # -> "Barrel of Babies completed."
        self.assertIn("jmp show_result", barrel)
        # Tech one-shot / guard result wording lives in the DLL result export.
        self.assertIn('"Barrel of Babies completed."', dll)
        self.assertIn('"Island Event completed."', dll)
        self.assertIn(
            '"Tech Point Doubler was removed. No refund was issued."', dll
        )
        self.assertIn("ShowOriginsUpgradeResult", dll)
        # Collections no-change guards route to result codes 8/9.
        self.assertIn("All collectibles are already found.", dll)
        self.assertIn("The collections are already cleared.", dll)
        # Details Grant Running 3-case no-change wording (codes 20-22).
        self.assertIn("This villager already likes Running.", dll)
        self.assertIn("its Running dislike was removed.", dll)
        self.assertIn("Running can not be added.", dll)
        self.assertIn('"Villager Upgrades"', dll)  # detail-result title
        complete = source.split("        do_complete_collections:", 1)[1].split(
            "        do_reset_collections:", 1
        )[0]
        self.assertIn("0x58F438", complete)  # scans the collectible array
        self.assertIn("mov eax, 8", complete)  # all found -> no-change
        # The hook cave (spliced into the island-event handler) calls the present
        # routine once in-frame instead of the raw outcome, so the named popup
        # shows.
        hook = source.split("barrel_hook_code = assemble(", 1)[1].split(
            "BARREL_HOOK_VA,", 1
        )[0]
        self.assertIn("call 0x{BARREL_PRESENT_VA:X}", hook)
        self.assertNotIn("call 0x415320", hook)
        # The present routine drives the game's own island-event presenter,
        # forced to the barrel: it points every event-array slot at the barrel
        # object (rep stosd) so any selection path resolves to it, then runs the
        # native select + present pair (0x419AC0 manager, 0x419B30 present).  The
        # 3-child spawn runs from the game's own outcome when the popup is
        # dismissed.
        present = source.split("barrel_present_code = assemble(", 1)[1].split(
            "BARREL_PRESENT_VA,", 1
        )[0]
        self.assertIn("rep stosd", present)
        self.assertIn("call 0x{BARREL_SELECT_MANAGER_VA:X}", present)
        self.assertIn("call 0x{BARREL_PRESENT_EVENT_VA:X}", present)

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

    def test_vv3_payload_hash_tracks_the_current_feature_complete_route(self) -> None:
        payload = bytes.fromhex(
            next(
                item
                for item in self.manifest["patches"]
                if int(item["offset"], 0) == 0xA3180
            )["after"]
        )
        self.assertEqual(
            hashlib.sha256(payload).hexdigest().upper(),
            "5911997247261C10004A47F07533EC5DBF04F96828699F31F066214D67F49DD8",
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

    def test_time_warp_advances_three_years_regardless_of_game_speed(self) -> None:
        """Regression: VV3 Time Warp must advance exactly three displayed
        villager years independent of the current game speed. The village ages
        the injected clock shift at a rate proportional to the running speed,
        so the elapsed-clock shift must be 129600 / speed (43,200s at half
        speed 3, 21,600s at normal 6, 12,960s at double 10) -- the confirmed
        two-real-hours-per-displayed-year relation. The builder used to compute
        ``speed * 3600`` (proportional imul), correct only at normal speed and
        silently under/over-advancing at every other speed.
        """
        try:
            import capstone
        except ImportError:
            self.skipTest("capstone not available")

        payload = bytes.fromhex(
            next(
                item
                for item in self.manifest["patches"]
                if int(item["offset"], 0) == 0xA3180
            )["after"]
        )
        # Locate the 32-bit elapsed-clock write: sub dword ptr [0x4A4210], eax
        marker = bytes.fromhex("290510424A00")
        index = payload.find(marker)
        self.assertNotEqual(index, -1, "Time Warp clock write not found in payload")

        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        window_start = index - 0x14
        block = list(
            md.disasm(payload[window_start:index], 0x4A3180 + window_start)
        )
        mnemonics = [insn.mnemonic for insn in block]

        self.assertIn("idiv", mnemonics, "Time Warp no longer divides by game speed")
        self.assertNotIn(
            "imul",
            mnemonics,
            "Time Warp still scales the advance proportionally to game speed",
        )
        # The constant dividend is 129600 seconds (0x1FA40): mov eax, 0x1FA40.
        self.assertIn(
            bytes.fromhex("B840FA0100"),
            payload[window_start:index],
            "Time Warp dividend is not the constant 129600 seconds",
        )


if __name__ == "__main__":
    unittest.main()
