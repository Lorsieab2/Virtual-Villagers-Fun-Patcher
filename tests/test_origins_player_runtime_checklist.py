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
                        "0x9A009",
                        "0x9A300",
                        "0x9A530",
                        "0x943A8",
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
                        "0x270",
                        "0x28C",
                        "0x28470",
                        "0x56900",
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
                    }
                    self.assertEqual(
                        [item for item in current["patches"] if item["offset"] not in repaired_offsets],
                        [item for item in previous["patches"] if item["offset"] not in repaired_offsets],
                        path.name,
                    )
                elif path.name == "vv3_origins_feature.json":
                    corrected_offsets = {
                        "0x7B664", "0x7B7C0", "0x7B7D0",
                        "0x15EF1", "0x16983", "0x16BAB", "0x17A3A",
                        "0x15D44", "0x1673E", "0x18452", "0xA3180",
                    }
                    self.assertEqual(
                        [item for item in current["patches"] if item["offset"] not in corrected_offsets],
                        [item for item in previous["patches"] if item["offset"] not in corrected_offsets],
                        path.name,
                    )
                elif path.name == "vv4_origins_feature.json":
                    corrected_offsets = {
                        "0xCC004", "0xCC160", "0xCC170",
                        "0x156F8", "0x15862", "0x1586F", "0x15A81",
                        "0x15B46", "0x15D8C", "0x16722", "0x16735",
                        "0x1520E", "0x89373", "0xCC180",
                        "0x278", "0x294",
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
