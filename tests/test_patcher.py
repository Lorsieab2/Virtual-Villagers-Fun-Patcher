from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import PatcherError, apply_patch, dry_run, identify, load_builds, pe_checksum, render_patched_bytes, sha256

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
    def test_all_five_stock_builds(self) -> None:
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

if __name__ == "__main__":
    unittest.main(verbosity=2)
