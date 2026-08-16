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
                    "0x270", "0x28C", "0x28470", "0x56900",
                    "0x85D30", "0x8B009", "0x8B530", "0x8B710",
                    "0x35ACA", "0x8B900",
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
                },
                "data/vv2_origins_feature.json": {
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
                "data/vv3_origins_feature.json": {"0x7B664", "0xA3180"},
                "data/vv4_origins_feature.json": {
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
                },
                "data/vv5_origins_feature.json": {"0x94B37", "0x94EA0", "0xDB000"},
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
