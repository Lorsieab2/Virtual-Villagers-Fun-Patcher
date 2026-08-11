from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402
from scripts import build_playtest_bundle as bundle  # noqa: E402


STOCK = ROOT / "research" / "stock-executables"
MODE = "experimental_expanded_256_progression"
COMPANION_NAME = "VVFP Origins Icons.dll"
COMPANION_SHA256 = (
    "B402ED8316CD6EB2C43B056848E622DC0924188C81C683F5E2813466AF8045D0"
)
EXPECTED_SHA256 = {
    "vv3": "75661039771ADAABD9C6B3F7C9575E3A22C8AC4595563293D2326C98C3F241F3",
    "vv4": "B7E46D20596C6B335372FCAEF202BA7A25D7816A11078F4F0C27A308740A6622",
    "vv5": "B6AD620FA4B1D339B18130BA737EDC17CB0C40E326D0D461AA43166B79ABAA88",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def catalog_ids(game_id: str) -> list[str]:
    if game_id == "vv5":
        return ["vv5_enable_origins_exclusive_features"]
    return []


class ExpandedTimeWarpPlaytestRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builds = {
            build.id: build for build in patcher.load_builds() if build.id in {"vv3", "vv4", "vv5"}
        }

    def test_publication_catalog_and_authenticated_records_remain_unchanged(self) -> None:
        self.assertFalse(patcher.EXPANDED_256_PUBLICATION_ENABLED)
        normal_ids = {item.id for item in patcher.load_fun_patches()}
        for feature_id in patcher.EXPANDED_TIME_WARP_IDS.values():
            self.assertNotIn(feature_id, normal_ids)
        authenticated = {
            item.id: item
            for item in patcher.load_fun_patches(include_expanded_time_warp=True)
            if item.id in patcher.EXPANDED_TIME_WARP_IDS.values()
        }
        self.assertEqual(set(authenticated), set(patcher.EXPANDED_TIME_WARP_IDS.values()))
        for item in authenticated.values():
            self.assertNotIn("playtest_only", item.raw)
            self.assertNotIn("playtest_status", item.raw)

    def test_api_dry_run_routes_only_the_matching_hidden_time_warp(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            playtest_root = Path(temp).resolve()
            for game_id, build in self.builds.items():
                with self.subTest(game=game_id):
                    result = patcher.dry_run(
                        STOCK / build.input_name,
                        MODE,
                        catalog_ids(game_id),
                        playtest_disabled_feature_ids=[
                            patcher.EXPANDED_TIME_WARP_IDS[game_id]
                        ],
                        playtest_output_root=playtest_root,
                    )
                    self.assertTrue(result["playtest_only"])
                    self.assertEqual(
                        result["playtest_status"],
                        "runtime/player stress test; not catalog/publication evidence",
                    )
                    self.assertEqual(result["result_sha256"], EXPECTED_SHA256[game_id])
                    self.assertTrue(result["output_name"].endswith(" - Modded 256 Playtest.exe"))
                    self.assertEqual(Path(result["output_folder"]).parent, playtest_root)
                    self.assertEqual(
                        result["fun_patches"][-1],
                        patcher.EXPANDED_TIME_WARP_IDS[game_id],
                    )

    def test_cli_dry_run_accepts_hidden_argument_but_not_normal_fun_patch_choice(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            playtest_root = Path(temp).resolve()
            for game_id, build in self.builds.items():
                with self.subTest(game=game_id):
                    command = [
                        sys.executable,
                        "-B",
                        str(ROOT / "src" / "vv_fun_patcher.py"),
                        "dry-run",
                        str(STOCK / build.input_name),
                        "--patch-mode",
                        MODE,
                        "--playtest-disabled-feature",
                        patcher.EXPANDED_TIME_WARP_IDS[game_id],
                        "--playtest-output-root",
                        str(playtest_root),
                    ]
                    for feature_id in catalog_ids(game_id):
                        command.extend(["--fun-patch", feature_id])
                    completed = subprocess.run(
                        command,
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    result = json.loads(completed.stdout)
                    self.assertTrue(result["playtest_only"])
                    self.assertEqual(result["result_sha256"], EXPECTED_SHA256[game_id])

            rejected = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "src" / "vv_fun_patcher.py"),
                    "dry-run",
                    str(STOCK / self.builds["vv3"].input_name),
                    "--patch-mode",
                    "collection_progression",
                    "--fun-patch",
                    patcher.EXPANDED_TIME_WARP_IDS["vv3"],
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("invalid choice", rejected.stderr)

    def test_cli_apply_reaches_only_the_separate_playtest_publication(self) -> None:
        build = self.builds["vv3"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source_folder = root / "source"
            source_folder.mkdir()
            source = source_folder / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            playtest_root = root / "playtest"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "src" / "vv_fun_patcher.py"),
                    "apply",
                    str(source),
                    "--patch-mode",
                    MODE,
                    "--playtest-disabled-feature",
                    patcher.EXPANDED_TIME_WARP_IDS["vv3"],
                    "--playtest-output-root",
                    str(playtest_root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            folder = playtest_root / f"{build.title} - Modded 256 Playtest"
            output = folder / f"{build.title} - Modded 256 Playtest.exe"
            log_path = output.with_suffix(".patch-log.json")
            self.assertEqual(digest(output), EXPECTED_SHA256["vv3"])
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertTrue(log["playtest_only"])
            self.assertEqual(log["save_handling"]["status"], "not_requested")
            self.assertTrue(log["retained_untouched_stock_executable"])

    def test_preparse_bypass_is_exactly_one_single_apply_request(self) -> None:
        exact = [
            "apply",
            "missing.exe",
            "--patch-mode",
            MODE,
            "--playtest-disabled-feature",
            patcher.EXPANDED_TIME_WARP_IDS["vv3"],
            "--playtest-output-root",
            "C:/VVFP-Playtest",
        ]
        patcher._preparse_publication_mode(exact)
        patcher._preparse_publication_mode(["dry-run", *exact[1:]])
        rejected = [
            exact + ["--playtest-disabled-feature", patcher.EXPANDED_TIME_WARP_IDS["vv4"]],
            exact + ["--output-root", "C:/ordinary"],
            exact + ["--copy-vanilla-saves"],
            exact + ["--save-root", "C:/saves"],
            [
                "apply-all",
                "--patch-mode",
                MODE,
                "--playtest-disabled-feature",
                patcher.EXPANDED_TIME_WARP_IDS["vv3"],
                "--playtest-output-root",
                "C:/VVFP-Playtest",
            ],
            ["apply", "missing.exe", "--patch-mode", MODE],
            ["dry-run", "missing.exe", "--patch-mode", MODE],
            [
                "dry-run-all",
                "--patch-mode",
                MODE,
                "--playtest-disabled-feature",
                patcher.EXPANDED_TIME_WARP_IDS["vv3"],
                "--playtest-output-root",
                "C:/VVFP-Playtest",
            ],
        ]
        for tokens in rejected:
            with self.subTest(tokens=tokens), self.assertRaisesRegex(
                patcher.PatcherError, "Expanded-256 publication is disabled"
            ):
                patcher._preparse_publication_mode(tokens)

    def test_argparse_abbreviation_cannot_bypass_output_root_prepass(self) -> None:
        build = self.builds["vv3"]
        with tempfile.TemporaryDirectory() as temp:
            absolute = str(Path(temp).resolve())
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "src" / "vv_fun_patcher.py"),
                    "dry-run",
                    str(STOCK / build.input_name),
                    "--patch-mode",
                    MODE,
                    "--playtest-disabled-feature",
                    patcher.EXPANDED_TIME_WARP_IDS["vv3"],
                    "--playtest-output-root",
                    absolute,
                    "--output-r",
                    absolute,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("unrecognized arguments: --output-r", completed.stderr)

    def test_ordinary_expanded_dry_run_and_hidden_normal_channel_are_closed(self) -> None:
        build = self.builds["vv3"]
        source = STOCK / build.input_name
        feature_id = patcher.EXPANDED_TIME_WARP_IDS["vv3"]
        absolute = (ROOT / "playtest-root-not-created").resolve()
        with self.assertRaisesRegex(
            patcher.PatcherError, "Expanded-256 publication is disabled"
        ):
            patcher.dry_run(source, MODE)
        with self.assertRaisesRegex(
            patcher.PatcherError, "unavailable through normal fun-patch selection"
        ):
            patcher.dry_run(source, MODE, [feature_id])
        with self.assertRaisesRegex(
            patcher.PatcherError, "both normal and hidden playtest arguments"
        ):
            patcher.dry_run(
                source,
                MODE,
                [feature_id],
                playtest_disabled_feature_ids=[feature_id],
                playtest_output_root=absolute,
            )
        with self.assertRaisesRegex(
            patcher.PatcherError, "Expanded-256 publication is disabled"
        ):
            patcher.dry_run_all({}, MODE)

    def test_api_rejects_wrong_multiple_stock_root_and_save_requests(self) -> None:
        build = self.builds["vv3"]
        source = STOCK / build.input_name
        feature_id = patcher.EXPANDED_TIME_WARP_IDS["vv3"]
        other_id = patcher.EXPANDED_TIME_WARP_IDS["vv4"]
        absolute = (ROOT / "playtest-root-not-created").resolve()
        with self.assertRaisesRegex(patcher.PatcherError, "match the identified source game"):
            patcher.dry_run(
                source,
                MODE,
                playtest_disabled_feature_ids=[other_id],
                playtest_output_root=absolute,
            )
        with self.assertRaisesRegex(patcher.PatcherError, "exactly one"):
            patcher.dry_run(
                source,
                MODE,
                playtest_disabled_feature_ids=[feature_id, other_id],
                playtest_output_root=absolute,
            )
        with self.assertRaisesRegex(patcher.PatcherError, "require --playtest-output-root"):
            patcher.dry_run(
                source,
                MODE,
                playtest_disabled_feature_ids=[feature_id],
            )
        with self.assertRaisesRegex(patcher.PatcherError, "cannot use --output-root"):
            patcher.dry_run(
                source,
                MODE,
                output_root=absolute,
                playtest_disabled_feature_ids=[feature_id],
                playtest_output_root=absolute / "separate",
            )
        with self.assertRaisesRegex(patcher.PatcherError, "absolute path"):
            patcher.dry_run(
                source,
                MODE,
                playtest_disabled_feature_ids=[feature_id],
                playtest_output_root=Path("relative-playtest"),
            )
        with self.assertRaisesRegex(patcher.PatcherError, "Expanded-256 mode"):
            patcher.dry_run(
                source,
                "collection_progression",
                playtest_disabled_feature_ids=[feature_id],
                playtest_output_root=absolute,
            )
        for kwargs in (
            {"copy_saves": True},
            {"replace_modded_saves": True},
            {"save_root": absolute / "saves"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(
                patcher.PatcherError, "cannot copy or replace saves"
            ):
                patcher.apply_patch(
                    source,
                    MODE,
                    playtest_disabled_feature_ids=[feature_id],
                    playtest_output_root=absolute,
                    **kwargs,
                )

    def test_playtest_apply_rejects_save_like_and_reparse_source_before_staging(self) -> None:
        build = self.builds["vv3"]
        feature_id = patcher.EXPANDED_TIME_WARP_IDS["vv3"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source_folder = root / "source"
            source_folder.mkdir()
            source = source_folder / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            playtest_root = root / "playtest"
            for relative in (
                "slot.ldw",
                "slot.sav",
                "slot.save",
                "slot.savegame",
                "saves/slot.dat",
            ):
                with self.subTest(relative=relative):
                    candidate = source_folder / relative
                    candidate.parent.mkdir(parents=True, exist_ok=True)
                    candidate.write_bytes(b"must not be copied")
                    with self.assertRaisesRegex(patcher.PatcherError, "save-like content"):
                        patcher.apply_patch(
                            source,
                            MODE,
                            playtest_disabled_feature_ids=[feature_id],
                            playtest_output_root=playtest_root,
                        )
                    self.assertFalse(playtest_root.exists())
                    candidate.unlink()
                    if candidate.parent != source_folder:
                        candidate.parent.rmdir()

            link = source_folder / "linked-support.dat"
            try:
                link.symlink_to(source)
            except OSError:
                real_snapshot = patcher._capture_tree_snapshot

                def reject_source(path: Path) -> dict[str, object]:
                    if Path(path) == source_folder:
                        raise patcher.PatcherError("Reparse/symlink entry rejected")
                    return real_snapshot(path)

                with mock.patch.object(
                    patcher, "_capture_tree_snapshot", side_effect=reject_source
                ):
                    with self.assertRaisesRegex(
                        patcher.PatcherError, "Reparse/symlink"
                    ):
                        patcher.apply_patch(
                            source,
                            MODE,
                            playtest_disabled_feature_ids=[feature_id],
                            playtest_output_root=playtest_root,
                        )
            else:
                with self.assertRaisesRegex(patcher.PatcherError, "Reparse/symlink"):
                    patcher.apply_patch(
                        source,
                        MODE,
                        playtest_disabled_feature_ids=[feature_id],
                        playtest_output_root=playtest_root,
                    )
                link.unlink()
            self.assertFalse(playtest_root.exists())

    def test_complete_folder_apply_for_all_three_games_is_save_free_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            playtest_root = root / "published"
            for game_id, build in self.builds.items():
                with self.subTest(game=game_id):
                    source_folder = root / f"source-{game_id}"
                    source_folder.mkdir()
                    source = source_folder / build.input_name
                    shutil.copy2(STOCK / build.input_name, source)
                    (source_folder / "support.dat").write_bytes(b"unchanged support file")
                    source_hash = digest(source)
                    output, log_path = patcher.apply_patch(
                        source,
                        MODE,
                        fun_patch_ids=catalog_ids(game_id),
                        playtest_disabled_feature_ids=[
                            patcher.EXPANDED_TIME_WARP_IDS[game_id]
                        ],
                        playtest_output_root=playtest_root,
                    )
                    self.assertEqual(digest(source), source_hash)
                    self.assertEqual(output.parent.parent, playtest_root)
                    self.assertTrue(output.name.endswith(" - Modded 256 Playtest.exe"))
                    self.assertEqual(digest(output), EXPECTED_SHA256[game_id])
                    self.assertEqual(digest(output.parent / build.input_name), source_hash)
                    self.assertEqual(
                        (output.parent / "support.dat").read_bytes(),
                        b"unchanged support file",
                    )
                    companion = output.parent / COMPANION_NAME
                    self.assertEqual(digest(companion), COMPANION_SHA256)
                    log = json.loads(log_path.read_text(encoding="utf-8"))
                    self.assertTrue(log["playtest_only"])
                    self.assertEqual(log["source_sha256"], source_hash)
                    self.assertEqual(log["output_sha256"], digest(output))
                    self.assertEqual(log["save_handling"]["status"], "not_requested")
                    self.assertTrue(log["retained_untouched_stock_executable"])
                    comparison = log["source_output_comparison"]
                    self.assertEqual(comparison["modified"], [])
                    self.assertEqual(comparison["removed"], [])
                    self.assertTrue(comparison["no_removals_proven"])
                    self.assertTrue(any(Path(item["path"]).name == COMPANION_NAME for item in log["companion_files"]))
                    files = [path for path in output.parent.rglob("*") if path.is_file()]
                    for suffix in bundle.SAVE_SUFFIXES:
                        self.assertFalse(
                            any(path.suffix.casefold() == suffix for path in files),
                            suffix,
                        )
                    inventory = bundle._inventory(output.parent, reject_saves=True)
                    self.assertGreater(inventory["file_count"], 0)
                    with mock.patch.object(
                        bundle,
                        "_is_reparse",
                        side_effect=lambda path, st=None: path.name == "support.dat",
                    ):
                        with self.assertRaisesRegex(bundle.BundleError, "reparse/link"):
                            bundle._inventory(output.parent, reject_saves=True)


if __name__ == "__main__":
    unittest.main()
