from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (
    PatcherError,
    apply_all,
    apply_patch,
    dry_run,
    dry_run_all,
    identify,
    load_builds,
    pe_checksum,
    render_patched_bytes,
    sha256,
    validate_all_sources,
)

STOCK = ROOT / "research" / "stock-executables"


class ManifestTests(unittest.TestCase):
    def test_names_and_targets(self) -> None:
        builds = load_builds()
        self.assertEqual(len(builds), 5)
        self.assertEqual([b.villager_slots for b in builds], [256, 256, 150, 150, 150])
        for build in builds:
            self.assertEqual(build.output_name, f"{build.title} - Modified Max Pop.exe")
            self.assertEqual(build.modified_base_cap + build.maximum_bonus, build.villager_slots)
            for patch in build.patches:
                self.assertEqual(len(bytes.fromhex(patch["before"])), len(bytes.fromhex(patch["after"])))

    def test_unknown_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "unknown.exe"
            path.write_bytes(b"not a game")
            with self.assertRaises(PatcherError):
                identify(path)


@unittest.skipUnless(STOCK.is_dir(), "ignored stock executables are not present")
class StockIntegrationTests(unittest.TestCase):
    def sources(self) -> dict[str, Path]:
        return {build.id: STOCK / build.input_name for build in load_builds()}

    def test_all_five_stock_builds_individually(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            output_dir = Path(folder)
            for build in load_builds():
                with self.subTest(game=build.id):
                    source = STOCK / build.input_name
                    self.assertTrue(source.is_file())
                    self.assertEqual(source.stat().st_size, build.size)
                    self.assertEqual(sha256(source), build.sha256)
                    self.assertEqual(identify(source).id, build.id)
                    preview = dry_run(source)
                    self.assertEqual(preview["villager_slots"], build.villager_slots)
                    output, log = apply_patch(source, output_dir)
                    self.assertEqual(output.name, build.output_name)
                    self.assertEqual(output.stat().st_size, source.stat().st_size)
                    self.assertNotEqual(sha256(output), build.sha256)
                    log_data = json.loads(log.read_text(encoding="utf-8"))
                    self.assertEqual(log_data["output_sha256"], sha256(output))
                    rendered, _ = render_patched_bytes(source, build)
                    self.assertEqual(output.read_bytes(), rendered)
                    pe_offset = struct.unpack_from("<I", rendered, 0x3C)[0]
                    checksum_offset = pe_offset + 24 + 64
                    stored = struct.unpack_from("<I", rendered, checksum_offset)[0]
                    copy = bytearray(rendered)
                    self.assertEqual(stored, pe_checksum(copy))
                    self.assertNotEqual(stored, 0)
                    for patch in build.patches:
                        offset = int(patch["offset"], 0)
                        after = bytes.fromhex(patch["after"])
                        self.assertEqual(output.read_bytes()[offset:offset + len(after)], after)

    def test_all_five_bulk_dry_run_and_apply(self) -> None:
        sources = self.sources()
        validated = validate_all_sources(sources)
        self.assertEqual([build.id for build, _ in validated], [build.id for build in load_builds()])
        previews = dry_run_all(sources)
        self.assertEqual(len(previews), 5)
        self.assertEqual([item["game"] for item in previews], [build.title for build in load_builds()])
        with tempfile.TemporaryDirectory() as folder:
            results = apply_all(sources, Path(folder))
            self.assertEqual(len(results), 5)
            for (output, log), build in zip(results, load_builds(), strict=True):
                self.assertEqual(output.name, build.output_name)
                self.assertTrue(output.is_file())
                self.assertTrue(log.is_file())
                self.assertEqual(json.loads(log.read_text(encoding="utf-8"))["output_sha256"], sha256(output))

    def test_bulk_invalid_input_writes_nothing(self) -> None:
        sources = self.sources()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bad = root / "bad.exe"
            bad.write_bytes(b"not a supported game")
            sources["vv5"] = bad
            output_dir = root / "new-output"
            with self.assertRaises(PatcherError):
                apply_all(sources, output_dir)
            self.assertFalse(output_dir.exists())

    def test_bulk_wrong_game_slot_writes_nothing(self) -> None:
        sources = self.sources()
        sources["vv5"] = sources["vv4"]
        with tempfile.TemporaryDirectory() as folder:
            output_dir = Path(folder) / "new-output"
            with self.assertRaises(PatcherError):
                apply_all(sources, output_dir)
            self.assertFalse(output_dir.exists())

    def test_bulk_existing_output_without_overwrite_writes_nothing(self) -> None:
        sources = self.sources()
        builds = load_builds()
        with tempfile.TemporaryDirectory() as folder:
            output_dir = Path(folder)
            sentinel = output_dir / builds[0].output_name
            sentinel.write_bytes(b"keep me")
            with self.assertRaises(PatcherError):
                apply_all(sources, output_dir)
            self.assertEqual(sentinel.read_bytes(), b"keep me")
            for build in builds[1:]:
                self.assertFalse((output_dir / build.output_name).exists())
                self.assertFalse((output_dir / Path(build.output_name).with_suffix(".patch-log.json")).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
