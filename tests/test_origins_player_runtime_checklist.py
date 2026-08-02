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
            "Cure all Villagers | 30,000 tech points",
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
            "VV2's paused Time Warp must refuse",
            "VV2's certified Tech Point Doubler and Food Point Doubler paths are purchasable, removable, and repurchasable",
            "The withdrawn VV2 Full Mastery candidate targets its five native skill fields",
            "913be6982bc17d606470f31d3df3d3430942cb6a",
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

    def test_machine_readable_origins_descriptions_match_checklist_costs(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for game in (1, 2, 3, 4, 5):
            origins = json.loads((ROOT / "data" / f"vv{game}_origins_feature.json").read_text(encoding="utf-8"))
            wide = json.loads((ROOT / "data" / f"vv{game}_origins_village_wide_upgrades.json").read_text(encoding="utf-8"))
            self.assertIn("Tech Point", origins["description"])
            self.assertIn("Food Point", origins["description"])
            if game in (4, 5):
                self.assertNotIn("30,000", origins["description"])
                folded_origins = origins["description"].casefold()
                for phrase in ("withdrawn", "unavailable", "unreachable"):
                    self.assertIn(phrase, folded_origins)
                self.assertTrue(
                    "not part of this playtest" in folded_origins
                    or "not part of this candidate" in folded_origins
                )
            else:
                self.assertIn("30,000", origins["description"])
            self.assertIn("1,000,000", wide["description"])
        self.assertIn("VV3Run2 is hard-withdrawn", text)
        self.assertIn("36f14702b938a6235230a3fd3e0c34328d3ac745", text)
        self.assertIn("package or continue runtime testing", text)
        self.assertNotIn("permits runtime playtesting", text)
        self.assertIn("f1555e295e828af2165ab0b7ea9f051ac9736418", text)
        self.assertIn("`-1` means empty but never terminates the scan", text)
        self.assertIn("every duplicate Like and every Dislike", text)
        self.assertIn("first physical `-1`", text)
        self.assertIn("0x420D22", text)
        self.assertNotIn("Only VV3 All Villagers Like Running is currently available", text)
        self.assertIn("each row would charge exactly 1,000,000 once", text)

    def test_committed_mastery_helpers_write_exact_native_skill_counts(self) -> None:
        expected = {
            "vv1": ([0x3BC, 0x3C0, 0x3C4, 0x3C8, 0x3CC], bytes.fromhex("5A000000")),
            "vv2": ([0x7E4, 0x7E8, 0x7EC, 0x7F0, 0x7F4], bytes.fromhex("5A000000")),
            "vv3": ([0xEAC, 0xEB0, 0xEB4, 0xEB8, 0xEBC], bytes.fromhex("5A000000")),
            "vv4": ([0x1C5C, 0x1C60, 0x1C64, 0x1C68, 0x1C6C], bytes.fromhex("0000B442")),
            "vv5": ([7260, 7264, 7268, 7272, 7276, 7280], bytes.fromhex("0000B442")),
        }
        for game, (offsets, value) in expected.items():
            with self.subTest(game=game):
                base = json.loads((ROOT / "data" / f"{game}_origins_feature.json").read_text(encoding="utf-8"))
                wide = json.loads((ROOT / "data" / f"{game}_origins_village_wide_upgrades.json").read_text(encoding="utf-8"))
                base_bytes = b"".join(bytes.fromhex(item["after"]) for item in base["patches"])
                wide_bytes = bytes.fromhex(wide["patches"][0]["after"])
                base_stores = sum(
                    base_bytes.count(b"\xC7\x82" + offset.to_bytes(4, "little") + value)
                    for offset in offsets
                )
                wide_stores = sum(
                    wide_bytes.count(b"\xC7\x86" + offset.to_bytes(4, "little") + value)
                    for offset in offsets
                )
                self.assertEqual(base_stores, len(offsets))
                self.assertEqual(wide_stores, len(offsets))
                if game == "vv1":
                    # VV1's documented no-preference fallback writes Farming's
                    # checked-job marker (+3D0=1); it is not a sixth skill.
                    fallback = b"\xC7\x82\xD0\x03\x00\x00\x01\x00\x00\x00"
                    self.assertEqual(base_bytes.count(fallback), 1)
                    self.assertEqual(wide_bytes.count(fallback), 0)
                self.assertIn(
                    f"five skills in VV1–VV4 and six in VV5",
                    DOC.read_text(encoding="utf-8"),
                )

    def test_no_loaded_patch_advertises_unimplemented_appearance_options(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        from vv_fun_patcher import load_fun_patches  # noqa: PLC0415

        forbidden = {"change outfit", "change head", "give heathen mask", "play as the heathens!"}
        for patch in load_fun_patches():
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
                    (ROOT / "assets/origins/VVFP Origins Icons.dll").read_bytes()
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
