from __future__ import annotations

import base64
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import PatcherError, load_builds, render_patched_bytes

STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"
MANIFEST = ROOT / "data/statistics_features.json"
DLL = ROOT / "assets/statistics/VVFP Statistics Export.dll"
SOURCE = ROOT / "native/statistics_export/statistics_export.c"
FEATURE_ID = "vv5_write_village_statistics"
ORIGINS_ID = "vv5_enable_origins_exclusive_features"
MODES = (
    "collection_progression",
    "immediate_fixed",
    "experimental_expanded_256",
    "experimental_expanded_256_progression",
)


class VV5StatisticsFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.feature = next(
            item for item in manifest["features"] if item["id"] == FEATURE_ID
        )
        cls.cave_patch = next(
            item
            for item in cls.feature["patches"]
            if int(item["offset"], 0) == 0x94932
        )
        cls.cave = base64.b64decode(cls.cave_patch["after_base64"], validate=True)

    def test_companion_identity_and_vv5_output_field(self) -> None:
        self.assertEqual(
            hashlib.sha256(DLL.read_bytes()).hexdigest().upper(),
            self.feature["companion_files"][0]["sha256"],
        )
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('"Heathens Converted: %d\\n"', source)
        self.assertIn("read_int(statistics, 0x34)", source)
        self.assertIn("write_vv5(", source)

    def test_conversion_hook_is_exactly_guarded(self) -> None:
        patch = next(
            item
            for item in self.feature["patches"]
            if int(item["offset"], 0) == 0x668B0
        )
        self.assertEqual(patch["before"], "83EC10568BF1")
        self.assertEqual(self.stock[0x668B0 : 0x668B6], bytes.fromhex(patch["before"]))
        self.assertEqual(bytes.fromhex(patch["after"])[0], 0xE9)
        self.assertIn("Heathen Mommy as two", patch["purpose"])

    def test_conversion_wrapper_counts_tag_17_as_two_and_others_as_one(self) -> None:
        wrapper = self.cave[0x130:0x160]
        self.assertIn(bytes.fromhex("83B9FC1C000011"), wrapper)
        self.assertIn(bytes.fromhex("83058CD3510002"), wrapper)
        self.assertIn(bytes.fromhex("FF058CD35100"), wrapper)
        self.assertIn(bytes.fromhex("83EC105689CE"), wrapper)

    def test_statistics_and_origins_saved_fields_do_not_overlap(self) -> None:
        origins = json.loads(
            (ROOT / "data/vv5_origins_feature.json").read_text(encoding="utf-8")
        )
        origins_source = (
            ROOT / "scripts/build_vv5_origins_feature.py"
        ).read_text(encoding="utf-8")
        self.assertIn("0x51D388", origins_source)
        self.assertNotIn("0x51D38C", origins_source)
        origins_payload = next(
            item for item in origins["patches"] if int(item["offset"], 0) == 0xDB000
        )
        origins_end = 0xDB000 + len(bytes.fromhex(origins_payload["after"]))
        self.assertLessEqual(0x94932 + len(self.cave), 0xDB000)
        self.assertLessEqual(origins_end, 0xDC000)

    def test_composes_with_origins_in_all_population_modes(self) -> None:
        build = next(build for build in load_builds() if build.id == "vv5")
        for mode in MODES:
            with self.subTest(mode=mode):
                if mode.startswith("experimental_expanded_256"):
                    with self.assertRaisesRegex(PatcherError, "(?:stock-mode only|no append layout)"):
                        render_patched_bytes(
                            STOCK, build, mode, [FEATURE_ID, ORIGINS_ID]
                        )
                    continue
                rendered, _ = render_patched_bytes(
                    STOCK, build, mode, [FEATURE_ID, ORIGINS_ID]
                )
                self.assertNotEqual(
                    bytes(rendered[0x668B0:0x668B6]),
                    bytes.fromhex("83EC10568BF1"),
                )
                self.assertEqual(
                    bytes(rendered[0x94932 + 0x130 : 0x94932 + 0x160]),
                    self.cave[0x130:0x160],
                )
                self.assertNotEqual(
                    bytes(rendered[0xDB000:0xDB010]),
                    self.stock[0xDB000:0xDB010],
                )


if __name__ == "__main__":
    unittest.main()
