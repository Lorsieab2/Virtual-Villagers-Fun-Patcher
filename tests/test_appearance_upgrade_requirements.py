from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "appearance-upgrades-requirements.md"
BUILDS = ROOT / "data" / "builds.json"


class AppearanceUpgradeRequirementsTests(unittest.TestCase):
    def test_contract_contains_required_rules_and_stop_boundary(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        required = [
            "Change Outfit belongs in the existing Villager Upgrades window",
            "exactly **5,000 tech points once**",
            "Change Head has the same selected active/living eligibility",
            "Warning: This will change",
            "young and old/gray head choice",
            "choices, in order, are exactly: Chief's mask, blue\nmask, red mask, orange mask, and no mask",
            "Play as the Heathens!",
            "defaults to\nthe blue Heathen mask",
            "Every current Heathen renders with no mask",
            "every native spawn",
            "Vanilla base-game save recognition is mandatory",
            "Executable growth is allowed",
            "remain **STOP** until independently proved",
            "do not authorize chooser-preview implementation",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("exactly **0** only when Play as the Heathens is active", text)
        self.assertIn("never write faction, type/tag, conversion", text)

    def test_contract_lists_exact_build_fingerprints(self) -> None:
        builds = json.loads(BUILDS.read_text(encoding="utf-8"))["games"]
        text = DOC.read_text(encoding="utf-8")
        for build in builds:
            with self.subTest(game=build["id"]):
                self.assertIn(f"{build['size']:,} bytes", text)
                self.assertIn(build["sha256"], text)

    def test_vv1_appearance_audit_is_exact_build_stop(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        required = [
            "disassembly commit `8888682`",
            "record `+0x364`",
            "record `+0x360`",
            "RNG(19)",
            "RNG(20)",
            "Status/action 199",
            "clone path copies both",
            "sub_437790",
            "sub_449140 -> sub_437340",
            "`+0xAD34`",
            "Strange Berries",
            "Change Outfit and Change Head implementations remain ON HOLD",
            "exact save/load serializer mapping",
            "custom chooser/preview",
            "safe composable cave/new-section placement",
            "Do not\ninfer young/old catalogs",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertIn("independent **STOP**", text)
        self.assertIn("1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D", text)

    def test_vv2_appearance_audit_is_independent_exact_build_stop(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        required = [
            "VV2 exact-build appearance audit",
            "724,992-byte build",
            "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
            "independent **STOP**",
            "record stride is `0xE48C`",
            "record `+0x54C`",
            "Native action 69 costs exactly **5,000 tech points**",
            "sub_4229D0",
            "sub_422890",
            "native range of `0..29`",
            "197,488 bytes",
            "not a final user catalog",
            "head/genetics DWORD candidate is record `+0x548`",
            "old/young resources",
            "genetics-warning callback",
            "head feels strange",
            "no direct caller xref",
            "vanilla-save compatibility",
            "requested Change Outfit and Change Head implementations\nremain ON HOLD for VV2",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_vv3_change_outfit_audit_is_exact_build_stop(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        required = [
            "VV3 Change Outfit exact-build audit",
            "a9d3b1ff0e223c0aa5fd8504194845afa4456df1",
            "831,488-byte build",
            "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
            "independent **STOP**",
            "The Clothing Hut",
            "Choose\nan outfit for your villager!",
            "Do you want to spend 5000 tech points to change\nthis villager's clothes?",
            "Getting new clothes!",
            "Not enough tech points\nto make new clothes!",
            "Male/female body resources",
            "young/old head assets",
            "sub_4227F0",
            "sub_4228F0",
            "literal `0x1388` (5,000)",
            "0x004228A2`/`0x228A2",
            "[eax+0x12FB0]",
            "does **not** prove a clothing purchase",
            "selected-villager identity",
            "outfit-field write",
            "Change Outfit remains ON HOLD",
            "sex/age/special/invalid catalog classification",
            "world, Detail, and chooser",
            "stock and expanded-256 layouts",
            "this audit is Outfit-only",
            "special\nconstructor value `29` is outside",
            "chooser accepts exactly `0..28`",
            "there is no rollback snapshot",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_all_five_change_outfit_audits_are_separate_and_on_hold(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        citations = (
            "8888682",
            "ed4cedb5a0d41b28319bf62b8d25596baa3e7a2e",
            "a9d3b1ff0e223c0aa5fd8504194845afa4456df1",
            "23fee766bfbcccc634c565c6bc88f3318e30f244",
            "313651623d2687d3f53ce5cc30c9f5ad07051a8d",
        )
        for citation in citations:
            self.assertIn(citation, text)
        for game in ("VV1", "VV2", "VV3", "VV4", "VV5"):
            self.assertIn(game, text)
        for marker in (
            "Change Outfit remains ON HOLD",
            "requested Change Outfit and Change Head implementations\nremain ON HOLD for VV2",
            "VV4 Change Outfit exact-build audit",
            "VV5 Change Outfit exact-build audit",
            "no custom Change Outfit implementation is authorized",
            "0x46CEC7`/`0x46CED1",
            "button `+0x50`",
            "`0x419E8E`",
            "`0x419E94`/`0x419E9E`",
        ):
            self.assertIn(marker, text)

    def test_all_five_change_head_audits_are_separate_on_hold_and_heathen_safe(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        citations = (
            "ccb5d973909faf222745968cca15109654f767f4",
            "bfd2ad7f07efa730d962787149c1348f2a6c336b",
            "cdf50e399360c1eba04449d359b0d477573b7361",
            "9dd368fe6248c55f53be9a620025e2a655854ddd",
            "388bf9a4e3ee400ba7168317526e9511c77a1048",
        )
        for citation in citations:
            self.assertIn(citation, text)
        for marker in (
            "Change Head exact-build evidence (all five ON HOLD)",
            "### VV1",
            "### VV2",
            "### VV3",
            "### VV4",
            "### VV5",
            "record+0x360",
            "record+0x548",
            "record+0xDF0",
            "record+0x1BB8",
            "current faction `+0x1CEC`",
            "no current Heathen may open",
            "converted former Heathen",
            "sub_419D80",
            "No native Change Head chooser",
            "head-specific 5,000 transaction",
            "no UI row, manifest feature, helper, runtime bytes, or output",
        ):
            self.assertIn(marker, text)

    def test_vv5_mask_system_is_exact_build_stop(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        required = [
            "VV5 mask-system exact-build audit (STOP)",
            "disassembly commit `870d236`",
            "991,232-byte build",
            "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
            "current faction byte is record `+0x1CEC`",
            "generic selector bytes are\n`+0x1CED` and `+0x1CEE`",
            "`+0x1CEF` is a persisted but currently unconsumed\nsidecar",
            "type dword is `+0x1CFC`",
            "blue `0`, orange `1`, red `2`, purple `3`, and Chief `4`",
            "mask overlay\nis gated by current faction",
            "Reset, spawn, conversion, clone, and save/load\nbehavior are mapped",
            "stock Detail portrait has no mask overlay",
            "`Give Heathen Mask` remains **STOP**",
            "native chooser/cost and\nselected-active-living-current-believer/no-charge-Heathen transaction",
            "safe\nmanual encoding",
            "Detail overlay/refresh",
            "collision-free stock+expanded-256\nplacement",
            "`Play as the Heathens!` remains **STOP**",
            "complete\nall-spawn Play interception",
            "Neither feature is registered or\nadvertised",
            "changes no manifests,\ngenerators, companion DLL, outputs, prices, save behavior, or executable\npayloads",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_no_loaded_fun_patch_advertises_unimplemented_appearance_options(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "src"))
        from vv_fun_patcher import load_fun_patches  # noqa: PLC0415

        forbidden = {
            "change outfit",
            "change head",
            "give heathen mask",
            "play as the heathens!",
        }
        for patch in load_fun_patches():
            self.assertNotIn(patch.id.casefold(), forbidden)
            self.assertNotIn(patch.name.casefold(), forbidden)
            self.assertNotIn("change outfit", patch.description.casefold())
            self.assertNotIn("change head", patch.description.casefold())
            self.assertNotIn("give heathen mask", patch.description.casefold())
            self.assertNotIn("play as the heathens!", patch.description.casefold())

    def test_release_manifest_includes_contract(self) -> None:
        text = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"docs/appearance-upgrades-requirements.md"', text)

    def test_existing_executable_manifests_are_unchanged_from_parent_commit(self) -> None:
        manifest_paths = sorted(ROOT.glob("data/*_origins_feature.json"))
        manifest_paths += sorted(ROOT.glob("data/*_origins_village_wide_upgrades.json"))
        try:
            parent = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git parent unavailable for executable-manifest snapshot")
        for path in manifest_paths:
            relative = path.relative_to(ROOT).as_posix()
            before = subprocess.run(
                ["git", "show", f"{parent}:{relative}"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            current_manifest = json.loads(path.read_text(encoding="utf-8"))
            before_manifest = json.loads(before)
            executable_keys = (
                "patches",
                "output_tag",
                "running_preference_id",
                "running_preference_evidence",
            )
            if relative.endswith("_origins_village_wide_upgrades.json"):
                # The five village-wide payloads are intentionally corrected
                # in the current slice. Their guards and ownership metadata
                # remain unchanged; only their generated payload bytes differ.
                current_patch = current_manifest["patches"][0]
                before_patch = before_manifest["patches"][0]
                for patch_key in ("offset", "before", "purpose"):
                    self.assertEqual(
                        current_patch.get(patch_key),
                        before_patch.get(patch_key),
                        f"{relative}:patches[0].{patch_key}",
                    )
                continue
            repaired_offsets = {
                "data/vv1_origins_feature.json": {
                    # Purchased Barrel of Babies always delivers three
                    # children: stock rolls rand(100) for one/two/three, so a
                    # 75,000-point purchase was partly a coin flip. The cave
                    # and its call site replace that one roll; natural barrels
                    # are untouched.
                    "0x8B962", "0x2B00C",

                    # Time Warp moved wholesale into the companion DLL, which
                    # now owns its confirmation (it names the current game
                    # speed and the years), the paused refusal, the charge and
                    # a per-villager advance that does not trip the engine's
                    # own per-speed aging clamp. New .shr stub at 0x8BF80;
                    # menu dispatch and the deleted flat advance are both in
                    # the payload at 0x56900.
                    #
                    # The exe-side "paused" string is dead weight now and was
                    # removed to make room for the export name in a string
                    # block already at its 0x2D0 limit. That shortens the
                    # block by 30 bytes, so every LATER string sits 30 lower
                    # and every stub that pushes one of those addresses has
                    # exactly one immediate byte changed -- verified: the only
                    # differing bytes in each of these are the low bytes of
                    # their push imm32 operands. No behaviour of theirs moves.
                    "0x8BF80", "0x85D30",
                    "0x8B009", "0x8B530", "0x8B93F", "0x8BA80",
                    "0x8BB00", "0x8BD30", "0x8BE00",
                    "0x8E024", "0x8E1B4", "0x8E6C0", "0x8E720", "0x8E900",
                    # Duplicate-purchase guards. An Island Event is queued
                    # by zeroing a countdown and a Barrel of Babies by setting
                    # a flag, so buying a second one while the first is
                    # pending changes nothing and charges in full. The menu's
                    # state builder now marks those rows so the companion DLL
                    # draws them disabled, which needs a small cave to compute
                    # the state in plus the payload block that calls it.
                    "0x8BF00", "0x56900",

                    # VV1 save-slot capture repair: the trampoline used to
                    # normalize the META file's slot 0 to zero and STORE it,
                    # overwriting the live village slot and running the table
                    # reset -- wiping a running game's masks after any meta
                    # write.  It now publishes only slots 1..5 and preserves the
                    # flags its range check clobbers.  Both rows are asserted
                    # directly in test_vv1_mask_slot_persistence.py and
                    # certified by scripts/audit_save_path_integrity.py.
                    "0x2ED0", "0x8E820",
                    "0x270", "0x28C", "0x28470", "0x56900",
                    "0x85D30", "0x8B009", "0x8B530", "0x8B710",
                    "0x35ACA", "0x8B900",
                    # .data VirtualSize extended to 0x7000 so it formally owns
                    # the BSS page (0x48CD18..0x48D000) that now holds all
                    # writable mask state -- keeping runtime writes out of the
                    # executable .shr section (W^X), which is what stopped
                    # Malwarebytes quarantining the running village.
                    "0x248",
                    # Villager Details "Change Appearance" row: a dedicated
                    # dispatch router at 0x8BA00 (isolated from detail_menu's
                    # own shared, byte-constrained cave -- it only ever does
                    # cmp ebx,4 / je 0x8BA00) that calls the picker helper,
                    # now relocated to 0x8BA80 to make room for the router,
                    # both in .shr's otherwise-unused tail.
                    "0x8BA00", "0x8BA80",
                    # Shared "permanent change" confirmation helper, called
                    # by both menu (Buy path) and detail_menu right after a
                    # row is picked -- also in .shr's otherwise-unused tail.
                    "0x8BB00",
                    # detail_menu's no-charge preflight helper (Grant Youth/
                    # Mastery/Running/Set Age 18): decides whether a row
                    # would actually change anything before detail_menu
                    # charges for it -- same tail, just past the confirm
                    # helper above.
                    "0x8BC00",
                    # Barrel of Babies delay-tick counter: the event used to
                    # fire on the very next per-frame main-update tick after
                    # the Tech screen closed; it now waits BARREL_DELAY_TICKS
                    # ticks first so the purchase confirmation can be read.
                    "0x8B704",
                    # Barrel of Babies' final population tier no longer
                    # hardcodes the collection_progression/immediate_fixed
                    # 256-cap threshold -- it reads the live opcode byte at
                    # the stock CanAddVillager check (0x43A1AE) to tell
                    # "stock" patch_mode (true cap 90) apart from the
                    # expanded modes (cap 256) and picks the right ceiling
                    # at runtime. Lives in its own .shr tail helper past the
                    # detail preflight helper above.
                    "0x8BD00",
                    # Generic "<row> completed."/no-change/removed/blocked
                    # result box (ShowOriginsRowMessage) resolver, bringing
                    # every plain-wording Tech/Details row's confirm and
                    # result text in line with the OFFICIAL Origins Upgrade
                    # Prompts spreadsheet -- replaces five removed ASM
                    # strings and the removed ShowOriginsAgeResult call
                    # site. Lives in .shr's tail past the population helper.
                    "0x8BE00",
                    # Details Grant Running's free-dislike-removal tail
                    # (RUNNING_DISLIKE_CLEAR_VA), tail-jumped into from
                    # DETAIL_PREFLIGHT_VA when a villager's Like slots are
                    # full -- OFFICIAL spreadsheet edge case.
                    "0x8BE80",
                    # Equal Division of Labor (Tech screen rows 9/10):
                    # equal_division_core (in the confirmed-unused gap
                    # after BARREL_MAIN_HELPER), its job-preference code
                    # table, and equal_division_dispatch (in the
                    # confirmed-unused gap after POPULATION_FINAL_TIER).
                    "0x8B790", "0x8B8A0", "0x8BD30",
                    # Cosmetic head-mask overlay (Change Appearance's Mask
                    # row): 5 cached SDL_Surface* + companion-PNG filenames
                    # plus the additive per-frame draw hook itself, in
                    # .shr's confirmed-unused tail right after the Running
                    # Dislike-clear helper (0x8BE80); and the detour that
                    # splices the hook into sub_437790's per-villager
                    # render loop right after its own occupied-flag check.
                    "0x8BEA8", "0x377B8", "0x24103", "0x913C",
                    # Change Appearance for All (Tech screen row 11): its
                    # DLL-dispatch stub (resolve + call the whole-village
                    # chooser export, which owns its own afford check,
                    # conditional 450,000 charge and messaging) in the
                    # confirmed-unused .shr gap after equal_division_core.
                    # Row 11's confirm-price case and its dispatch edge reuse
                    # the already-listed confirm helper (0x8BB00) and Equal
                    # Division dispatch (0x8BD30); no other offset changes.
                    "0x8B93F",
                    # Whole-village mask fix: the per-frame masked-villager
                    # stash list moved out of .data (which held only 39 of a
                    # possible 256 entries, so a full-village distribution
                    # rendered most villagers bare) into a DLL-allocated
                    # buffer indexed through a .data pointer. The two mask
                    # render hooks (0x8BEA8) index through that pointer, and
                    # the startup restore stub's done-flag (0x8BE32) moved
                    # with the compacted scratch layout.
                    "0x8BE32",
                    # ...and the redesign that keeps all of that in the exe's
                    # own .data (Malwarebytes flags the exe writing through a
                    # pointer into non-exe memory): the stash now stores a
                    # 1-byte record index and the draw hook recomputes screen
                    # x/y from it, which grew the draw hook past the 0x8BEA8
                    # cave, so it moved to its own confirmed-zero .shr gap.
                    "0x8B080",
                    # Details-screen portrait mask overlay: all four native
                    # head sites remain CALLs but now target one ABI-compatible
                    # wrapper at 0x8E720. It duplicates/replays the exact seven
                    # head args, then passes the untouched tuple and renderer
                    # wrapper to Vv1DrawPortraitMask. The retired per-site cave
                    # rows remain listed because the parent manifest has them.
                    "0x3741B", "0x374A4", "0x37503", "0x37556",
                    "0x8E720", "0x8E75A", "0x8E774", "0x8E78E", "0x8E7A8",
                    # Live mask maintenance: the existing per-frame cache
                    # hook now calls the owned Vv1MaskTick resolver/caller;
                    # its export name and resolver live in the .vv1mc tail.
                    "0x8E400", "0x8E6C0", "0x8E8F0", "0x8E900",
                    # Exact newborn/allocation reuse guard: the stock splice
                    # and its patch-owned cave clear the selected mask nibble
                    # and mark the active sidecar dirty for Vv1MaskTick.
                    "0x3C393", "0x8EA00",
                    # Village all-pose mask identity stash (Stage 1): 2 loop-top
                    # splices + their stash caves (inert; hook reads the slot later).
                    "0x37798", "0x38900", "0x8B180", "0x8B191",
                    "0x8BF3C", "0x8BF76", "0x8BF90", "0x8BFAA", "0x8BFC4",
                },
                "data/vv2_origins_feature.json": {
                    # Purchased Barrel of Babies always delivers three
                    # children: stock rolls rand(100) for one/two/three, so a
                    # 75,000-point purchase was partly a coin flip. The cave
                    # and its call site replace that one roll; natural barrels
                    # are untouched.
                    "0x9A4F0", "0x37ADC",

                    # Duplicate-purchase guards. An Island Event is queued
                    # by zeroing a countdown and a Barrel of Babies by setting
                    # a flag, so buying a second one while the first is
                    # pending changes nothing and charges in full. The menu's
                    # state builder now marks those rows so the companion DLL
                    # draws them disabled, which needs a small cave to compute
                    # the state in plus the payload block that calls it.
                    "0x9A4A0", "0x943A8",

                    # The mask-stage delivery adds five guarded fixed-image
                    # detours; their exact before/after bytes are checked by
                    # tests/test_vv2_mask_render.py.
                    "0x3160", "0x95B0", "0x9600", "0x45B50", "0x4C5E6",
                    "0x943A8", "0x9A009", "0x9A300", "0x9A530",
                    # Change Appearance: the new chooser helper lives at
                    # 0x9AD20 (just past the optional village-wide payload).
                    # Wiring its row into detail_menu grew that block, so the
                    # tech/food/event payload helpers were relocated by 0x20
                    # inside 0x943A8; their three tail-jump sites re-encode to
                    # the new targets with identical behavior.
                    "0x9AD20", "0x26290", "0x262B0", "0x34570", "0x9AE40",
                    # Collections + counted Running/Mastery reports and the
                    # cued Barrel: the Barrel main-village helper (0x9A780)
                    # gained a cue-delay countdown, and a single DLL-dispatch
                    # stub (0x9AF58, in the .shr tail after the whole-village
                    # helper) now routes Grant Running / Grant Full Mastery /
                    # Complete / Reset Collections to their companion-DLL
                    # exports.  Tech-menu routing for those rows lives inside
                    # 0x943A8.
                    "0x9A780", "0x9AF58",
                    # VV5 Task9-style prompts + no-charge-on-no-change + the
                    # fullscreen-safe dialogs.  New .shr helpers: confirm/result
                    # export strings (0x9A204/0x9A218) + result trampoline
                    # (0x9A240) + Detail no-change helper (0x9A380, reusing the
                    # dead Detail-preflight slot).  The DLL dispatch moved into
                    # the dead whole-village slot (0x9AE40); its old 0x9AF58 slot
                    # is now empty.  All confirm/result/no-change routing lives
                    # inside the payload block (0x943A8).
                    "0x9A204", "0x9A218", "0x9A240", "0x9A380",
                },
                # Heathen-mask sections move (docs/head-mask-rendering.md Part 7):
                # the mask trampolines left the .text tail slack (a borrowed gap --
                # .text VirtualSize ends at 0x47B254, so 0x47B260+ was never ours)
                # and the DLL fn-pointer slots left the .data slack past 0x6C7518.
                # Both now live in appended, patch-owned sections .vv3mc (R-X) and
                # .vv3md (R/W), which is also W^X-clean.  The vacated caves, the
                # three PE header edits mapping the new sections, and the retargeted
                # call-site redirects move with it; no upgrade behaviour changes.
                # The second proven action-overlay call site is independently
                # guarded at 0x60D10 for F14 actions 1/2/5/6/7; it shares the
                # same wrapper and stash-after-stock-draw contract as 0x60B48.
                "data/vv3_origins_feature.json": {
                    # The duplicate-purchase guard for VV3 moved out of the
                    # executable and into the companion DLL, so tech_menu fits
                    # its original slot again and detail_menu/tech_increment
                    # move back 0x10. The rel32 at 0x27130 is a jump into
                    # tech_increment, so it tracks that move -- it shifted when
                    # the guard went in (shipped in v1.34.29) and shifts back
                    # now that the guard no longer lives in the payload.
                    "0x27130",
                    "0x7B664", "0xA3180",
                    "0x3290",
                    "0x7B260", "0x7B2A0", "0x7B300",
                    "0x10E", "0x158", "0x2C8",
                    "0x2E3F5", "0x34357", "0x344B3", "0x60B48", "0x60D10",
                },
                "data/vv4_origins_feature.json": {
                    # Duplicate-purchase guards. An Island Event is queued
                    # by zeroing a countdown and a Barrel of Babies by setting
                    # a flag, so buying a second one while the first is
                    # pending changes nothing and charges in full. The menu's
                    # state builder now marks those rows so the companion DLL
                    # draws them disabled, which needs a small cave to compute
                    # the state in plus the payload block that calls it.
                    "0xCCC20", "0x89373",

                    "0x89373", "0xCC004", "0xCC180",
                    # D166 fix: .shr was never marked executable (0x278 is
                    # its VirtualSize field, 0x294 its Characteristics
                    # field -- neither was patched before). The two tail
                    # helpers at 0xCC160/0xCC170 and every one of the 9
                    # tail-jump sites that target them (8 Tech Doubler +
                    # 1 Food Doubler) were assembled against the wrong VA
                    # (IMAGE_BASE + raw file offset instead of the correct
                    # .shr RVA-remapped VA), so every one of their rel32
                    # encodings changes with the fix even though none of
                    # their *behavior* other than "actually reaching the
                    # helper instead of crashing" does.
                    "0x278", "0x294", "0xCC160", "0xCC170",
                    "0x156F8", "0x15862", "0x1586F", "0x15A81",
                    "0x15B46", "0x15D8C", "0x16722", "0x16735",
                    "0x1520E",
                    # Heathen-mask cosmetic overlay (SDL blit via companion
                    # DLL). Replaced the old append-rows approach (render cave
                    # 0xCCD80 and row-count bumps 0xC3C24/0xC3B94) with three
                    # .shr caves -- resolve 0xCCD90, present-surface-cache
                    # 0xCCDE0, head-draw 0xCC7A1 -- the present-call splice
                    # (0x9458), and the confirmed Details head call (0x5F702).
                    # The inherited Island Event call (0x5F9CA) is deliberately
                    # removed and left stock. No row bumps, no atlas swaps. The
                    # proven-wrong Details route (0x5F965) and former scratch
                    # slots (0xCCA28/0xCCA30/0xCCA34) are removed; 0xCC7A1 is
                    # reclaimed for the confirmed Details head cave.
                    "0xCCD80", "0xC3C24", "0xC3B94",
                    "0x9458", "0xCCD90", "0xCCDE0", "0xCCE10",
                    "0x5F702", "0x5F9CA", "0x5F965", "0xCC7A1",
                    "0xCCA28", "0xCCA30", "0xCCA34",
                    # VV5-style Details portrait facing/X/Y tables used by
                    # the repaired 0x45F702 head replay.
                    "0xCCA40",
                    # The DY bytes remain the player-approved uniform 34s;
                    # only the stale purpose text claiming a chief-only +7
                    # adjustment is corrected by the authoritative generator.
                    "0xCCFC4",
                    # Save-slot sidecar namespace: capture the active slot in
                    # owned .shr scratch before the exact 0x403670 save
                    # builder continues its untouched body.
                    "0xCCFCC", "0xCCFD0", "0x3670",
                },
                # 0x1890F: the D37 barrel selector hook — its forced native
                # event index is corrected from 30 (Chutes Without Ladders) to
                # 25 (Barrel O' Babies, "happily adopted"); only the selector
                # body immediate at 0xDB000+0x180 and this hook's purpose text
                # change, no other guard.
                "data/vv5_origins_feature.json": {"0x94B37", "0x94EA0", "0xDB000", "0x1890F"},
            }.get(relative, set())
            if repaired_offsets:
                self.assertEqual(
                    [
                        item for item in current_manifest["patches"]
                        if item["offset"] not in repaired_offsets
                    ],
                    [
                        item for item in before_manifest["patches"]
                        if item["offset"] not in repaired_offsets
                    ],
                    f"{relative}:unrelated patches",
                )
                executable_keys = (
                    "output_tag",
                    "running_preference_id",
                    "running_preference_evidence",
                )
            for key in executable_keys:
                self.assertEqual(current_manifest.get(key), before_manifest.get(key), f"{relative}:{key}")
            if relative != "data/vv3_origins_feature.json":
                self.assertEqual(
                    current_manifest["companion_files"][0]["source"],
                    before_manifest["companion_files"][0]["source"],
                    f"{relative}:companion_files.source",
                )
            self.assertEqual(
                current_manifest["companion_files"][0]["destination"],
                before_manifest["companion_files"][0]["destination"],
                f"{relative}:companion_files.destination",
            )
            active_source = ROOT / current_manifest["companion_files"][0]["source"]
            actual_companion = hashlib.sha256(active_source.read_bytes()).hexdigest().upper()
            self.assertEqual(current_manifest["companion_files"][0]["sha256"], actual_companion)


if __name__ == "__main__":
    unittest.main()
