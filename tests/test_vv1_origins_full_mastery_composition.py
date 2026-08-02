from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    FunPatch,
    PatcherError,
    _remove_feature_bytes,
    load_builds,
    load_fun_patches,
    render_patched_bytes,
)


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
GENERATOR = ROOT / "scripts" / "build_vv1_origins_full_mastery_composition.py"
MANIFEST = ROOT / "data" / "candidates" / "vv1_full_mastery_origins_composition.json"
MAP = ROOT / "data" / "candidates" / "vv1_full_mastery_origins_composition_map.json"
BASE_SHA = "5434C71C342B830A5896AFFB610A76C670578760BD33C6145882FA280F6406A3"
MODES = ("collection_progression", "immediate_fixed")


def sha(data: bytes | bytearray) -> str:
    return hashlib.sha256(bytes(data)).hexdigest().upper()


class VV1OriginsCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = next(item for item in load_builds() if item.id == "vv1")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.map = json.loads(MAP.read_text(encoding="utf-8"))
        cls.origins = FunPatch(json.loads((ROOT / "data" / "vv1_origins_feature.json").read_text(encoding="utf-8")))
        cls.composition = FunPatch(cls.manifest)

    def test_disabled_hidden_and_exact_prerequisites(self) -> None:
        self.assertFalse(self.manifest["enabled"])
        self.assertTrue(self.manifest["catalog_hidden"])
        self.assertEqual(self.manifest["dependencies"], ["vv1_enable_origins_exclusive_features"])
        self.assertEqual(self.manifest["required_base_sha256"], BASE_SHA)
        self.assertEqual(
            self.manifest["required_origins_dll_sha256"],
            "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9",
        )
        self.assertTrue(self.map["candidate_enabled"] is False)
        self.assertTrue(self.map["expanded_rejected"])
        self.assertNotIn(
            "vv1_full_mastery_origins_composition",
            {item.id for item in load_fun_patches()},
        )

    def test_rendered_hook_shim_and_direct_entry(self) -> None:
        expected_shim = bytes.fromhex(
            "83FB07740F83FB067205E97E6AFCFFE9AE6AFCFF89F1"
            "E8E51B0000E9A569FCFF"
        )
        for mode in MODES:
            with self.subTest(mode=mode):
                base, _ = render_patched_bytes(
                    STOCK, self.build, mode, _fun_patches_override=[self.origins]
                )
                combined, applied = render_patched_bytes(
                    STOCK,
                    self.build,
                    mode,
                    _fun_patches_override=[self.origins, self.composition],
                )
                self.assertEqual(sha(base), BASE_SHA)
                self.assertEqual(bytes(combined[0x56A88:0x56A8D]), bytes.fromhex("E973950300"))
                self.assertEqual(bytes(combined[0x8E000:0x8E000 + len(bytes.fromhex(self.map["layouts"][mode]["append_bytes"]))]), bytes.fromhex(self.map["layouts"][mode]["append_bytes"]))
                self.assertEqual(bytes(combined[0x8E000:0x8E000 + len(expected_shim)]), expected_shim)
                self.assertNotIn("0x358DC", {item["offset"] for item in applied if item["owner"] == "feature:vv1_full_mastery_origins_composition"})
                self.assertNotIn("0x35AB0", {item["offset"] for item in applied if item["owner"] == "feature:vv1_full_mastery_origins_composition"})
                direct = bytes(combined[0x8E000 + 0x1C00:0x8E000 + 0x1C00 + 16])
                self.assertEqual(direct[:7], bytes.fromhex("5589E5535689CE"))
                self.assertNotIn(bytes.fromhex("E830050000"), bytes(combined[0x8E000 + 0x1C00:0x8E000 + 0x1C00 + 0x200]))

    def test_exact_active_origins_uninstall_and_expanded_rejection(self) -> None:
        for mode in MODES:
            combined, _ = render_patched_bytes(
                STOCK, self.build, mode, _fun_patches_override=[self.origins, self.composition]
            )
            removed = bytearray(combined)
            _remove_feature_bytes(removed, self.composition, mode)
            self.assertEqual(sha(removed), BASE_SHA)
        for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
            with self.subTest(mode=mode), self.assertRaises(PatcherError):
                render_patched_bytes(
                    STOCK, self.build, mode, _fun_patches_override=[self.origins, self.composition]
                )

    def test_generator_is_deterministic(self) -> None:
        before = {path: sha(path.read_bytes()) for path in (MANIFEST, MAP)}
        subprocess.run(
            [sys.executable, str(GENERATOR)], cwd=ROOT, check=True
        )
        after = {path: sha(path.read_bytes()) for path in (MANIFEST, MAP)}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
