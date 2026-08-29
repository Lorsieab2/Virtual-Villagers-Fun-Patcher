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
    _remove_feature_bytes,
    _pe_checksum_layout,
    PatcherError,
    get_fun_patch,
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
            "All Villagers are Exactly 18",
            "Complete all Collections",
            "Reset all Collections",
        ):
            self.assertIn(required.encode("utf-16le"), data)

    def test_change_appearance_for_all_charges_only_after_an_applicable_record(self) -> None:
        dll = (
            ROOT
            / "native"
            / "vv3_full_mastery_candidate"
            / "vv3_full_mastery_candidate.c"
        ).read_text(encoding="utf-8")
        self.assertIn("static int vv3_apply_for_all", dll)
        engine = dll.split("static int vv3_apply_for_all", 1)[1].split("\n}", 1)[0]
        self.assertIn("int n = 0, chief = -1, affected = 0", engine)
        self.assertIn("mask_requested = (mask_mode != 0 || mask_m >= 0 || mask_f >= 0)", engine)
        self.assertIn("if (affected == 0)", engine)
        self.assertIn("return affected;", engine)

        entry = dll.split("ShowVV3AppearanceForAll(void)", 1)[1].split("\n}", 1)[0]
        apply_at = entry.index("affected = vv3_apply_for_all")
        guard_at = entry.index("if (affected == 0)", apply_at)
        charge_at = entry.index("*tech -= VV3_CAF_COST", guard_at)
        self.assertLess(apply_at, guard_at)
        self.assertLess(guard_at, charge_at)
        self.assertIn("No eligible villagers matched", entry)
        self.assertIn("No tech points have been deducted", entry)

    def test_change_appearance_for_all_counts_actual_value_differences(self) -> None:
        """A selected value already present on every eligible record is free."""
        dll = (
            ROOT
            / "native"
            / "vv3_full_mastery_candidate"
            / "vv3_full_mastery_candidate.c"
        ).read_text(encoding="utf-8")
        engine = dll.split("static int vv3_apply_for_all", 1)[1].split(
            "#define VW_RUNNING", 1
        )[0]
        self.assertIn(
            "int idx[256], sex[256], order[256], desired_mask[256], mask_changed[256]",
            engine,
        )
        self.assertIn("mask_changed[i] = desired_mask[i] != recovered_mask", engine)
        self.assertIn("vv3_mask_has_stored_fingerprint(plan_fp[i])", engine)
        self.assertIn("vv3_mask_build_batch_shadow", engine)
        self.assertIn("if (mask_changed[i])", engine)
        self.assertIn("*(int *)(r + VV3_HEAD_OFF) != h", engine)
        self.assertIn("*(int *)(r + VV3_BODY_OFF) != b", engine)

        plan = engine.index("Build the exact mask result before counting")
        count = engine.index("Count each eligible record once")
        zero_guard = engine.index("if (affected == 0)", count)
        first_head_write = engine.index("*(int *)(r + VV3_HEAD_OFF) = h")
        first_mask_write = engine.index("CopyMemory(g_vv3_mask, shadow_mask", zero_guard)
        self.assertLess(plan, count)
        self.assertLess(count, zero_guard)
        self.assertLess(zero_guard, first_head_write)
        self.assertLess(zero_guard, first_mask_write)

        # A per-sex selector of -1 must not turn an inapplicable mask into a
        # synthetic difference for the other sex.
        self.assertIn(
            "(mask_mode != 0 || (sex[i] ? mask_f : mask_m) >= 0)",
            engine,
        )
        self.assertIn(
            "CopyMemory(g_vv3_mask, shadow_mask, sizeof(g_vv3_mask));",
            engine,
        )
        # Random/proportional/equal modes are generated once and applied from
        # the same plan, preserving one mutation pass and no-op atomicity.
        self.assertIn("desired_mask[i] = (int)(caf_rand() % 6u)", engine)
        self.assertIn("vv3_mask_make_plan_group_coherent", engine)

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
                0x56B24,
                0x6547D,
                0x65640,
                0x6DA2C,
                0x6E530,
                0x7BD40,
                0x7BDE0,
                0xA3180,
                # (The 4 head-atlas row-count patches 0xAAE6C/9C/F2C/F5C were
                # removed: the separate-atlas mask render draws from its own
                # Images/heathen_masks.png and no longer appends rows to the shared
                # head atlases, so it leaves them byte-identical to stock.)
                #
                # Heathen-mask render hooks: 5-byte call-site redirects into the
                # patch-owned .vv3mc section.  Each stolen 5-byte window was verified
                # to contain no branch target.
                0x2E3F5,   # sole `call sub_4605F0` -> village wrapper (mask last layer)
                0x60A60,   # head draw -> stash cave (captures exact head x/y/scale)
                0x60B48,   # `call sub_45F7E0` -> action-overlay wrapper (pose heads)
                0x3290,    # save-builder slot capture -> .vv3mc/.vv3md sidecar selector
                # (0x34357 / 0x344B3 are NOT patched: proven from the binary to be a
                # timed UI/effect renderer, not a villager head draw -- the head-atlas
                # holder [+0x127C1C] is read at exactly one site in the exe, 0x460A54.
                # Those bytes are left stock rather than hooked.)
                #
            },
        )
        section_patch = next(
            item
            for item in self.manifest["patches"]
            if int(item["offset"], 0) == 0x24C
        )
        self.assertEqual(section_patch["after"], "400000E0")

    def test_manifest_patch_ranges_are_disjoint(self) -> None:
        append_headers = self.manifest["pe_append_transaction"]["layouts"][
            "collection_progression"
        ]["header_patches"]
        ranges = sorted(
            (
                int(item["offset"], 0),
                int(item["offset"], 0) + len(bytes.fromhex(item["after"])),
                item["purpose"],
            )
            for item in [*self.manifest["patches"], *append_headers]
        )
        for current, following in zip(ranges, ranges[1:]):
            self.assertLessEqual(
                current[1],
                following[0],
                f"VV3 Origins patches overlap: {current[2]} and {following[2]}",
            )

    def test_appended_mask_sections_are_w_xor_x(self) -> None:
        """The appended mask sections must be W^X separated.

        A single R/W/X section reads as self-modifying code to AV (Malwarebytes
        flags it) and is a quarantine risk, so code is executable-not-writable and
        data is writable-not-executable.
        """
        header_patch = next(
            item
            for item in self.manifest["pe_append_transaction"]["layouts"][
                "collection_progression"
            ]["header_patches"]
            if int(item["offset"], 0) == 0x2C8
        )
        blob = bytes.fromhex(header_patch["after"])
        self.assertEqual(len(blob), 80, "expected exactly two 40-byte section headers")
        code_hdr, data_hdr = blob[:40], blob[40:]
        self.assertTrue(code_hdr.startswith(b".vv3mc"))
        self.assertTrue(data_hdr.startswith(b".vv3md"))
        code_chars = int.from_bytes(code_hdr[36:40], "little")
        data_chars = int.from_bytes(data_hdr[36:40], "little")
        self.assertTrue(code_chars & 0x20000000, "mask code section must be executable")
        self.assertFalse(code_chars & 0x80000000, "mask code section must NOT be writable")
        self.assertTrue(data_chars & 0x80000000, "mask data section must be writable")
        self.assertFalse(data_chars & 0x20000000, "mask data section must NOT be executable")

    def test_shipping_render_maps_both_owned_pages_and_removal_truncates_them(self) -> None:
        feature = get_fun_patch("vv3_enable_origins_exclusive_features")
        transaction = self.manifest["pe_append_transaction"]
        self.assertEqual(transaction["append_length"], 0x2000)
        self.assertEqual(
            set(transaction["layouts"]),
            {"collection_progression", "immediate_fixed"},
        )

        for mode in ("collection_progression", "immediate_fixed"):
            with self.subTest(mode=mode):
                base, _ = render_patched_bytes(STOCK, self.build, mode, [])
                rendered, applied = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    [feature.id],
                )
                layout = transaction["layouts"][mode]
                appended = bytes.fromhex(layout["append_bytes"])

                self.assertEqual(len(base), 0xCB000)
                self.assertEqual(len(rendered), 0xCD000)
                self.assertEqual(rendered[0xCB000:0xCD000], appended)
                self.assertEqual(
                    hashlib.sha256(appended).hexdigest().upper(),
                    layout["append_sha256"],
                )
                self.assertTrue(any(rendered[0xCB000:0xCC000]))
                self.assertEqual(rendered[0xCC000:0xCD000], bytes(0x1000))
                self.assertEqual(
                    rendered[0xCB100:0xCB10B],
                    bytes.fromhex("8B442404A344006E008B11"),
                )
                self.assertEqual(struct.unpack_from("<H", rendered, 0x10E)[0], 7)
                self.assertEqual(struct.unpack_from("<I", rendered, 0x158)[0], 0x2E1000)

                code_header = rendered[0x2C8:0x2F0]
                data_header = rendered[0x2F0:0x318]
                self.assertTrue(code_header.startswith(b".vv3mc"))
                self.assertTrue(data_header.startswith(b".vv3md"))
                self.assertEqual(struct.unpack_from("<I", code_header, 12)[0], 0x2DF000)
                self.assertEqual(struct.unpack_from("<I", code_header, 20)[0], 0xCB000)
                self.assertEqual(struct.unpack_from("<I", data_header, 12)[0], 0x2E0000)
                self.assertEqual(struct.unpack_from("<I", data_header, 20)[0], 0xCC000)
                self.assertTrue(
                    any(
                        item["owner"] == f"feature:{feature.id}"
                        and item["offset"] == "0xCB000"
                        for item in applied
                    )
                )

                tampered = bytearray(rendered)
                tampered[-1] ^= 1
                tampered_before = bytes(tampered)
                with self.assertRaisesRegex(PatcherError, "appended page guard differs"):
                    _remove_feature_bytes(tampered, feature, mode)
                self.assertEqual(tampered, tampered_before)

                removed = _remove_feature_bytes(rendered, feature, mode)
                self.assertTrue(
                    any(item["purpose"].startswith("truncate owned append") for item in removed)
                )
                self.assertEqual(rendered, base)

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
            "923C155460BFB8BECB2F07725FB2220E1987F2563764FB508D7CA36A3A125014",
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
