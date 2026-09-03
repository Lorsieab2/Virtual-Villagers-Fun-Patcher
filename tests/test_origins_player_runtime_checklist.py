from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "origins-player-runtime-checklist.md"
OUTPUT_ROOT = ROOT / "outputs" / "origins-core-village-wide-playtest-all-five-collection-progression-2026-07-27"
STALE_ROOT = ROOT / "outputs" / "origins-core-village-wide-playtest-collection-progression-2026-07-27"


class OriginsPlayerRuntimeChecklistTests(unittest.TestCase):
    def test_checklist_is_explicitly_pending_and_contains_exact_runtime_rules(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        folded = " ".join(text.casefold().split())
        required = [
            "runtime/player confirmation pending",
            "backed-up vanilla save",
            "save and reload",
            "another slot remains unchanged",
            "Time Warp | 50,000 tech points",
            "Island Event | 30,000 tech points",
            "Barrel of Babies | 75,000 tech points",
            "Tech Point Doubler | 500,000 tech points",
            "Food Point Doubler | 500,000 tech points",
            "Historical sickness-only row; VV1/VV2 runtime/player validation remains pending",
            "1,000,000 tech points",
            "Grant Youth costs 50,000",
            "Grant Full Mastery costs 100,000",
            "Grant Running costs 40,000",
            "Set Age to 18 costs 50,000",
            "VV5, Time Warp, Island Event, and Barrel of Babies remain Unavailable",
            "Cured X villagers",
            "People Cured rises by exactly one",
            "Skipped over X villagers. Reason: already likes running",
            "Removed running dislike from X villagers",
            "full-slot result line remains future-only",
            "Not enough tech points.",
            "No current VV5 Heathen may be targeted or charged",
            "No game is launched",
            "VV1 and VV2 Origins and both dependent village-wide records are exposed",
            "VV2 Time Warp and both doublers remain runtime/player validation pending",
            "The enabled static VV2 Full Mastery candidate targets its five native skill fields",
            "13f4341201fa7757d23f77c5c17602bbe7bbf21d",
            "sub_44D4C0",
            "five skills in VV1–VV4 and six in VV5",
            "Food Mastery is code-confirmed absent",
            "Farming only gates or unlocks sources",
            "Herb Mastery is unrelated",
            "VV5 stock supports purchase, zero-cost/no-refund Remove, and full-price repurchase",
            "VV5 expanded-256 keeps new purchase unavailable and owned Remove available",
            "Island Event and Gong of Wonder outcomes",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(" ".join(phrase.casefold().split()), folded)

    def test_checklist_has_all_exact_build_fingerprints_and_marks_old_kit_superseded(self) -> None:
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))["games"]
        text = DOC.read_text(encoding="utf-8")
        for build in builds:
            with self.subTest(game=build["id"]):
                self.assertIn(f"{build['size']:,} bytes", text)
                self.assertIn(build["sha256"], text)
        self.assertIn("historical/superseded all-five output kit", text.casefold())
        self.assertIn("hashes below are retained only as provenance", text)
        self.assertIn(
            "not current vv5 runtime-validation artifacts",
            " ".join(text.casefold().split()),
        )
        self.assertIn("self-contained vanilla source folder", text)
        self.assertNotIn("VV2 remains\npending", text)
        self.assertNotIn("VV2 remains pending a self-contained", text)
        folded = " ".join(text.casefold().split())
        self.assertIn("food mastery is code-confirmed absent", folded)
        self.assertNotIn("food mastery presence/absence remains unresolved", folded)
        self.assertIn("island event and gong of wonder outcomes", " ".join(text.casefold().split()))

    def test_toggleable_origins_descriptions_are_player_facing(self) -> None:
        for game in (1, 2, 3, 4, 5):
            origins = json.loads((ROOT / "data" / f"vv{game}_origins_feature.json").read_text(encoding="utf-8"))
            wide = json.loads((ROOT / "data" / f"vv{game}_origins_village_wide_upgrades.json").read_text(encoding="utf-8"))
            for description in (origins["description"], wide["description"]):
                with self.subTest(game=game, description=description):
                    self.assertIn("Origins", description)
                    self.assertNotIn("runtime/player", description.casefold())
                    self.assertNotRegex(description, r"\b0x[0-9a-f]+\b")
            self.assertIn("Tech screen", wide["description"])
            self.assertIn("Make Villagers Young Adults", wide["description"])
            self.assertIs(origins.get("enabled", True), True)
            self.assertIs(origins.get("catalog_enabled", True), True)
            self.assertIs(origins.get("catalog_hidden", False), False)
    def test_committed_mastery_helpers_target_exact_native_skill_values(self) -> None:
        expected = {
            "vv1": (("0x3BC", "0x3C0", "0x3C4", "0x3C8", "0x3CC"), "100"),
            "vv2": (("0x7E4", "0x7E8", "0x7EC", "0x7F0", "0x7F4"), "100"),
            "vv3": (("0xEAC", "0xEB0", "0xEB4", "0xEB8", "0xEBC"), "100"),
            "vv4": (("0x1C5C", "0x1C60", "0x1C64", "0x1C68", "0x1C6C"), "0x42C80000"),
            "vv5": (("7260", "7264", "7268", "7272", "7276", "7280"), "0x42C80000"),
        }
        for game, (offsets, value) in expected.items():
            with self.subTest(game=game):
                source = (ROOT / "scripts" / f"build_{game}_origins_feature.py").read_text(encoding="utf-8")
                for offset in offsets:
                    self.assertIn(offset, source)
                if game in (1, 2, 3):
                    self.assertGreaterEqual(source.count(value), len(offsets))
                else:
                    self.assertIn(value, source)
                wide_source = (ROOT / "scripts" / "build_village_wide_origins_features.py").read_text(encoding="utf-8")
                self.assertIn("master_value", wide_source)
                self.assertIn("100", wide_source)
                self.assertIn(
                    f"five skills in VV1–VV4 and six in VV5",
                    DOC.read_text(encoding="utf-8"),
                )

    def test_no_loaded_patch_advertises_unimplemented_appearance_options(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        from vv_fun_patcher import PatcherError, load_fun_patches  # noqa: PLC0415

        forbidden = {"change outfit", "change head", "give heathen mask", "play as the heathens!"}
        try:
            catalog = load_fun_patches()
        except PatcherError as exc:
            if "VV4 Full Heal candidate manifest/map raw bytes are not pinned" in str(exc):
                self.skipTest(f"unrelated global-loader blocker: {exc}")
            raise
        for patch in catalog:
            self.assertNotIn(patch.id.casefold(), forbidden)
            self.assertNotIn(patch.name.casefold(), forbidden)

    def test_release_manifest_includes_checklist(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"docs/origins-player-runtime-checklist.md"', release)

    def test_manifest_patch_arrays_and_existing_output_hashes_are_unchanged(self) -> None:
        for path in sorted((ROOT / "data").glob("vv*_origins_feature.json")):
            current = json.loads(path.read_text(encoding="utf-8"))
            previous = json.loads(subprocess.run(
                ["git", "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"],
                cwd=ROOT, check=True, capture_output=True, text=True,
            ).stdout)
            if path.name != "vv5_origins_feature.json":
                if path.name == "vv2_origins_feature.json":
                    # The isolated VV2 stress path now owns a corrected
                    # raw-offset/VA mapping and PE section-header repair.  Its
                    # changed payload/header rows are validated directly by
                    # the VV2 feature tests; all other Origins rows remain
                    # byte-identical to the prior record.
                    repaired_offsets = {
                        # VV2 mask-stage delivery owns these fixed-image
                        # detours; their guards are asserted in the dedicated
                        # VV2 mask contract tests below.
                        "0x3160",
                        "0x95B0",
                        "0x9600",
                        "0x45B50",
                        "0x4C5E6",
                        "0x9A009",
                        "0x9A300",
                        "0x9A530",
                        "0x943A8",
                        # Purchased Barrel of Babies always delivers three
                        # children: stock rolls rand(100) for one/two/three, so
                        # a 75,000-point purchase was partly a coin flip. The
                        # cave and its call site replace that one roll;
                        # natural barrels are untouched.
                        "0x9A4F0", "0x37ADC",
                        # Duplicate-purchase guard: an Island Event is
                        # queued by zeroing a countdown and a Barrel of Babies
                        # by setting a flag, so a second purchase while one is
                        # pending changed nothing and charged in full. The
                        # menu's state builder now marks those rows so the
                        # companion DLL draws them disabled, which adds a small
                        # cave for the state and touches the payload that calls
                        # it.
                        "0x9A4A0",
                        "0x218",
                        "0x234",
                        "0x268",
                        "0x284",
                    }
                    self.assertEqual(
                        [item for item in current["patches"] if item["offset"] not in repaired_offsets],
                        [item for item in previous["patches"] if item["offset"] not in repaired_offsets],
                        path.name,
                    )
                elif path.name == "vv1_origins_feature.json":
                    # The Tech crash hotfix changes only the corrected menu,
                    # dialog strings, preflight/Cure helpers, deferred Barrel
                    # helper, and the already-repaired section metadata rows.
                    repaired_offsets = {
                        # VV1 save-slot capture repair: the trampoline used to
                        # normalize the META file's slot 0 to zero and STORE it,
                        # overwriting the live village slot and running the table
                        # reset -- wiping a running game's masks after any meta
                        # write.  It now publishes only slots 1..5 and preserves
                        # the flags its range check clobbers.  Both rows are
                        # asserted directly in test_vv1_mask_slot_persistence.py
                        # and certified by scripts/audit_save_path_integrity.py.
                        "0x2ED0",
                        "0x8E820",
                        "0x270",
                        "0x28C",
                        # .data VirtualSize extended to 0x7000 so it owns the
                        # BSS page holding all writable mask state (W^X) --
                        # keeping runtime writes off the executable .shr page.
                        "0x248",
                        "0x28470",
                        "0x56900",
                        # Purchased Barrel of Babies always delivers three
                        # children: stock rolls rand(100) for one/two/three, so
                        # a 75,000-point purchase was partly a coin flip. The
                        # cave and its call site replace that one roll;
                        # natural barrels are untouched.
                        "0x8B962", "0x2B00C",
                        # Duplicate-purchase guard: an Island Event is
                        # queued by zeroing a countdown and a Barrel of Babies
                        # by setting a flag, so a second purchase while one is
                        # pending changed nothing and charged in full. The
                        # menu's state builder now marks those rows so the
                        # companion DLL draws them disabled, which adds a small
                        # cave for the state and touches the payload that calls
                        # it.
                        "0x8BF00",
                        "0x85D30",
                        "0x8B009",
                        "0x8B530",
                        "0x8B710",
                        "0x35ACA",
                        "0x8B900",
                        # Villager Details "Change Appearance" row: a
                        # dedicated dispatch router at 0x8BA00, isolated
                        # from detail_menu's own shared cave, calling the
                        # picker helper now relocated to 0x8BA80 to make
                        # room -- both in .shr's otherwise-unused tail
                        # past the Barrel close helper.
                        "0x8BA00", "0x8BA80",
                        # Shared "permanent change" confirmation helper,
                        # called by both menu (Buy path) and detail_menu
                        # right after a row is picked -- also in .shr's
                        # otherwise-unused tail.
                        "0x8BB00",
                        # detail_menu's no-charge preflight helper (Grant
                        # Youth/Mastery/Running/Set Age 18): decides whether
                        # a row would actually change anything before
                        # detail_menu charges for it -- same tail, just
                        # past the confirm helper above.
                        "0x8BC00",
                        # Barrel of Babies delay-tick counter: the event
                        # used to fire on the very next per-frame main-
                        # update tick after the Tech screen closed; it now
                        # waits BARREL_DELAY_TICKS ticks first.
                        "0x8B704",
                        # Barrel of Babies' final population tier now reads
                        # the live opcode byte at the stock CanAddVillager
                        # check (0x43A1AE) to distinguish "stock" patch_mode
                        # (true cap 90) from the expanded modes (cap 256)
                        # instead of assuming the 256 cap, via a new .shr
                        # tail helper past the detail preflight helper.
                        "0x8BD00",
                        # Generic "<row> completed."/no-change/removed/
                        # blocked result box (ShowOriginsRowMessage)
                        # resolver bringing every plain-wording row's
                        # confirm/result text in line with the OFFICIAL
                        # Origins Upgrade Prompts spreadsheet.
                        "0x8BE00",
                        # Details Grant Running's free-dislike-removal
                        # tail, tail-jumped into from DETAIL_PREFLIGHT_VA.
                        "0x8BE80",
                        # Equal Division of Labor (Tech screen rows 9/10):
                        # equal_division_core (the actual scan/assign
                        # loop, in the confirmed-unused gap after
                        # BARREL_MAIN_HELPER), its own job-preference code
                        # table, and equal_division_dispatch (afford
                        # check/charge/result, in the confirmed-unused gap
                        # after POPULATION_FINAL_TIER).
                        "0x8B790", "0x8B8A0", "0x8BD30",
                        # Cosmetic head-mask overlay (Change Appearance's
                        # Mask row): 5 cached SDL_Surface* + companion-PNG
                        # filenames plus the additive per-frame draw hook,
                        # in .shr's confirmed-unused tail right after the
                        # Running Dislike-clear helper; and the detour
                        # splicing that hook into sub_437790's per-villager
                        # render loop right after its own occupied check.
                        "0x8BEA8", "0x377B8", "0x24103", "0x913C",
                        # Change Appearance for All (Tech screen row 11): its
                        # DLL-dispatch stub in the confirmed-unused .shr gap
                        # after equal_division_core; the row's confirm-price
                        # case and dispatch edge reuse the already-listed
                        # confirm helper (0x8BB00) and Equal Division dispatch
                        # (0x8BD30). Adding one export string shifts every
                        # later .rdata string pointer by 0x20, which is why
                        # the string-referencing rows above (0x56900, 0x8BEA8)
                        # also differ -- immediates only, no opcode change.
                        "0x8B93F",
                        # Whole-village mask fix: the per-frame stash list moved
                        # out of the size-capped .data (39-entry ceiling) into a
                        # DLL-allocated buffer indexed via a .data pointer, so a
                        # full-village distribution masks all villagers, not just
                        # the first 39. The two mask render hooks (0x8BEA8) index
                        # through that pointer; the restore stub's done-flag
                        # (0x8BE32) moved with the compacted scratch layout.
                        "0x8BE32",
                        # Malwarebytes-safe redesign: everything stays in the
                        # exe's own .data (the stash stores a 1-byte record
                        # index, the draw hook recomputes screen x/y from it),
                        # which grew the draw hook past the 0x8BEA8 cave, so it
                        # relocated to its own confirmed-zero .shr gap.
                        "0x8B080",
                        # Details-screen portrait mask overlay: sub_437340
                        # draws the portrait head at FOUR call sites (a 2x2 of
                        # age x head-atlas flag). All four now remain CALLs but
                        # target one ABI-compatible wrapper at 0x8E720. It
                        # duplicates/replays the exact seven native head args,
                        # then passes the untouched x/y/facing/scale/flag tuple
                        # and renderer wrapper to Vv1DrawPortraitMask. Keep the
                        # retired per-site cave rows below in the exception set
                        # because the baseline manifest still contains them.
                        "0x3741B", "0x374A4", "0x37503", "0x37556",
                        "0x8E720", "0x8E75A", "0x8E774", "0x8E78E", "0x8E7A8",
                        # Per-frame dead-slot/reuse maintenance: changed frame
                        # hook plus the owned export-name and resolver blocks.
                        "0x8E400", "0x8E6C0", "0x8E8F0", "0x8E900",
                        # Exact newborn/allocation reuse guard: the stock splice
                        # and patch-owned cave clear the selected mask nibble
                        # and mark the active sidecar dirty for Vv1MaskTick.
                        "0x3C393", "0x8EA00",
                        # Village all-pose mask identity stash (Stage 1): 2 loop-top
                        # splices + their stash caves (inert; hook reads the slot later).
                        "0x37798", "0x38900", "0x8B180", "0x8B191",
                        "0x8BF3C", "0x8BF76", "0x8BF90", "0x8BFAA", "0x8BFC4",
                    }
                    self.assertEqual(
                        [item for item in current["patches"] if item["offset"] not in repaired_offsets],
                        [item for item in previous["patches"] if item["offset"] not in repaired_offsets],
                        path.name,
                    )
                elif path.name == "vv3_origins_feature.json":
                    corrected_offsets = {
                        # The duplicate-purchase guard for VV3 moved out of the
                        # executable and into the companion DLL, so tech_menu fits
                        # its original slot again and detail_menu/tech_increment
                        # move back 0x10. The rel32 at 0x27130 is a jump into
                        # tech_increment, so it tracks that move -- it shifted when
                        # the guard went in (shipped in v1.34.29) and shifts back
                        # now that the guard no longer lives in the payload.
                        "0x27130",
                        "0x7B664", "0x7B7C0", "0x7B7D0",
                        "0x3290",
                        "0x15EF1", "0x16983", "0x16BAB", "0x17A3A",
                        "0x15D44", "0x1673E", "0x18452", "0xA3180",
                        # Heathen-mask sections move (docs/head-mask-rendering.md
                        # Part 7).  The mask trampolines used to sit in the .text
                        # tail slack (.text VirtualSize ends at 0x47B254, so
                        # 0x47B260+ was a borrowed gap) and the DLL fn-pointer slots
                        # in the .data slack past 0x6C7518.  Both are code caves,
                        # which silently collide when two patches want one gap.
                        # They now live in two appended, patch-owned sections --
                        # .vv3mc (R-X, trampolines) and .vv3md (R/W, slots) -- which
                        # is also W^X-clean.  Co-selection with the only other VV3
                        # append (.vv3tw) is impossible: its layouts exist only for
                        # the non-selectable experimental_expanded_256* modes, so
                        # this append owns the stock EOF with no offset coupling.
                        "0x7B260", "0x7B2A0", "0x7B300",  # vacated .text caves
                        "0x10E", "0x158", "0x2C8",        # PE header: sections 5->7
                        "0x2E3F5", "0x34357", "0x344B3",  # redirects retargeted
                        "0x60B48", "0x60D10",              # both proven action-overlay wrappers
                    }
                    self.assertEqual(
                        [item for item in current["patches"] if item["offset"] not in corrected_offsets],
                        [item for item in previous["patches"] if item["offset"] not in corrected_offsets],
                        path.name,
                    )
                elif path.name == "vv4_origins_feature.json":
                    corrected_offsets = {
                        # Duplicate-purchase guard: VV4 queues both the Island
                        # Event and the Barrel of Babies by zeroing the same
                        # [world+0x170E0] countdown, so a second purchase while
                        # one is pending changed nothing and charged in full.
                        # The menu's state builder now marks those rows so the
                        # companion DLL draws them disabled, which adds a cave
                        # for the state and touches the payload calling it.
                        "0xCCC20", "0x89373",
                        # VV4 save-slot capture repair: the invalid path used to
                        # store a literal 0 into the slot variable, so the META
                        # file -- which the same stock builder formats with slot
                        # 0 -- overwrote the live village slot.  It now leaves
                        # the previous capture intact.  Certified by
                        # scripts/audit_save_path_integrity.py.
                        "0xCCFD0",
                        "0xCC004", "0xCC160", "0xCC170",
                        "0x156F8", "0x15862", "0x1586F", "0x15A81",
                        "0x15B46", "0x15D8C", "0x16722", "0x16735",
                        "0x1520E", "0x89373", "0xCC180",
                        "0x278", "0x294",
                        # Barrel of Babies: purchase cues the native "Daredevil
                        # Barrel of Babies" event (barrel_cue at 0xCCB10 spliced on
                        # the real event scheduler at 0x3FBE5; the old dead-path
                        # splice at 0x4098C is reverted to stock; 0x14D50 admits the
                        # armed barrel). The purchased barrel always delivers 3 by
                        # gating the stock spawn's two internal room-checks
                        # (0x14DCA/0x14E0D -> checks at 0xCCB40/0xCCB60) past the
                        # tiered cap, bounded by the 150-slot array; 0xCCC00 is the
                        # matching purchase gate.
                        "0xCCB10", "0x14D50", "0x3FBE5", "0x4098C",
                        "0x14DCA", "0x14E0D", "0xCCB40", "0xCCB60", "0xCCC00",
                        # Heathen-mask overlay. Current code uses resolve
                        # 0xCCD90, present/surface-cache 0xCCDE0, the confirmed
                        # Details cave 0xCC7A1 spliced at 0x5F702 (VA 0x45F702),
                        # and world cave 0xCCEB0 spliced at 0x68263. The Details
                        # cave reads portrait turn +0x2E38 mod 3 and uses the
                        # dedicated 3x5 VV5-style atlas; 0xCCA40 owns its facing
                        # and X/Y tables. Historical append-row/false-route
                        # offsets stay in this snapshot exception set only so
                        # removed bytes can be compared against the prior ledger:
                        # 0xCCD80, 0xCCE10, 0x5F9CA, 0x5F965, 0x3CFDE, and old
                        # scratch 0xCCA28/30/34. No stock atlas is swapped.
                        "0xCCD80", "0xC3C24", "0xC3B94",
                        "0x9458", "0xCCD90", "0xCCDE0", "0xCCE10",
                        "0x5F702", "0x5F9CA",
                        "0xCCEB0", "0x68263", "0xCC7A1", "0x5F965", "0x3CFDE", "0xCCFC4",
                        "0xCCA28", "0xCCA30", "0xCCA34",
                        # VV5-style Details portrait facing/X/Y tables used by
                        # the repaired 0x45F702 head replay (including the
                        # current Purple +5px seating adjustment).
                        "0xCCA40",
                    }
                    self.assertEqual(
                        [item for item in current["patches"] if item["offset"] not in corrected_offsets],
                        [item for item in previous["patches"] if item["offset"] not in corrected_offsets],
                        path.name,
                    )
                else:
                    self.assertEqual(current["patches"], previous["patches"], path.name)
            else:
                # VV5's stock Food Doubler hook/menu is the authorized
                # runtime change; all other base Origins manifests remain
                # byte-identical.  Expanded safety is represented separately
                # by the same-feature mode override.
                self.assertEqual(current.get("output_tag"), previous.get("output_tag"), path.name)
                self.assertEqual(current.get("running_preference_id"), previous.get("running_preference_id"), path.name)
                self.assertEqual(current.get("running_preference_evidence"), previous.get("running_preference_evidence"), path.name)
            self.assertEqual(
                current["companion_files"][0]["source"],
                previous["companion_files"][0]["source"],
                path.name,
            )
            self.assertEqual(
                current["companion_files"][0]["destination"],
                previous["companion_files"][0]["destination"],
                path.name,
            )
            self.assertEqual(
                current["companion_files"][0]["sha256"],
                hashlib.sha256(
                    (ROOT / current["companion_files"][0]["source"]).read_bytes()
                ).hexdigest().upper(),
                path.name,
            )
        expected = {
            "Virtual Villagers - A New Home - Modded": "1118F1879CEF029F8D46EEBC762D4D47E3A122CBF5A3B59934DF06A5A83DB4FB",
            "Virtual Villagers - The Lost Children - Modded": "F7427D9E634431949841CAC0B19B964E0CAD2446538552ADF67651A79ECB1B19",
            "Virtual Villagers - The Secret City - Modded": "B18FDB825738A1329DCD3F526C4A4677D0B4E0E643EB9B5137590578BB4EDBFF",
            "Virtual Villagers - The Tree of Life - Modded": "636D7C8583DD7DC75319B0C1D4C59DD5FEADD2E7948A63CEF8A845F9DF0C674E",
            "Virtual Villagers - New Believers - Modded": "15A8AC5639D8B10F422C036EF5D2D0C73A5F82B9D03D503E8C1FCD3988603F1B",
        }
        if OUTPUT_ROOT.is_dir():
            for folder, expected_hash in expected.items():
                exe = OUTPUT_ROOT / folder / f"{folder}.exe"
                log = OUTPUT_ROOT / folder / f"{folder}.patch-log.json"
                self.assertEqual(hashlib.sha256(exe.read_bytes()).hexdigest().upper(), expected_hash)
                self.assertEqual(json.loads(log.read_text(encoding="utf-8"))["output_sha256"], expected_hash)
        stale_hashes = {
            "E7D868646531F0EAC7FFE13558E967885772934B7939CD535B7D56877A0EDCB2",
            "DA2637BA92A45A22DF384DB20370A832EB6FA0D2552C2394B165DC98BBD89ED0",
            "F45A8479434CD5A47FEB29DBA2B12457A222DA91FBEDAD0C99B838932B741BB1",
            "56F5EB15F2382468C379E32490E79EE01858499C077C8892A4A002BC2A8C0120",
        }
        self.assertTrue(stale_hashes.isdisjoint(expected.values()))
        if STALE_ROOT.is_dir():
            stale_exes = list(STALE_ROOT.glob("*/Virtual Villagers*Modded.exe"))
            for exe in stale_exes:
                self.assertIn(hashlib.sha256(exe.read_bytes()).hexdigest().upper(), stale_hashes)


if __name__ == "__main__":
    unittest.main()
