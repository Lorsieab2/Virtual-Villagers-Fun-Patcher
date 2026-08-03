from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as v  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


class VV3FullHealCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest_path = v.VV3_FULL_HEAL_CANDIDATE_PATHS["manifest"]
        cls.map_path = v.VV3_FULL_HEAL_CANDIDATE_PATHS["map"]
        cls.raw = json.loads(cls.manifest_path.read_text(encoding="utf-8"))
        cls.feature = v.FunPatch(cls.raw)
        cls.build = next(item for item in v.load_builds() if item.id == "vv3")
        cls.stock = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
        cls.chain = v.resolve_fun_patch_ids(
            [
                "vv3_enable_origins_exclusive_features",
                "vv3_full_mastery_all_stage_a_candidate",
                "vv3_individual_grant_running_candidate",
            ],
            game_id="vv3",
        )
        cls.chain_features = list(v._selected_fun_patches(cls.build, cls.chain))

    def _render(self, mode: str) -> bytearray:
        return v.render_patched_bytes(
            self.stock,
            self.build,
            mode,
            self.chain,
            _fun_patches_override=[*self.chain_features, self.feature],
        )[0]

    def test_disabled_hidden_and_exact_pins(self) -> None:
        self.assertFalse(self.raw["enabled"])
        self.assertTrue(self.raw["catalog_hidden"])
        self.assertFalse(self.raw["catalog_enabled"])
        self.assertEqual(sha(self.manifest_path.read_bytes()), v.VV3_FULL_HEAL_MANIFEST_SHA256)
        self.assertEqual(sha(self.map_path.read_bytes()), v.VV3_FULL_HEAL_MAP_SHA256)
        self.assertEqual(self.raw["transaction"], v.VV3_FULL_HEAL_TRANSACTION)
        self.assertEqual(self.raw["messages"], v.VV3_FULL_HEAL_MESSAGES)
        self.assertEqual(self.raw["result_helper"], v.VV3_FULL_HEAL_RESULT_HELPER)
        self.assertEqual(self.raw["health_setter"], v.VV3_FULL_HEAL_HEALTH_SETTER)
        self.assertNotIn(v.VV3_FULL_HEAL_CANDIDATE_ID, {item.id for item in v.load_fun_patches()})

    def test_both_stock_modes_emit_hook_and_cave(self) -> None:
        for mode in ("collection_progression", "immediate_fixed"):
            rendered = self._render(mode)
            self.assertEqual(rendered[0xA35EF : 0xA35F6], v.VV3_FULL_HEAL_HOOK_AFTER)
            self.assertEqual(
                sha(bytes(rendered[0x7B721 : 0x7B721 + v.VV3_FULL_HEAL_CAVE_LENGTH])),
                v.VV3_FULL_HEAL_CAVE_SHA256,
            )
            self.assertEqual(
                bytes(rendered[0x7B664 : 0x7B721]),
                bytes(
                    self._render_without_candidate(mode)[0x7B664 : 0x7B721]
                ),
            )

    def test_both_stock_modes_render_deterministically(self) -> None:
        for mode in ("collection_progression", "immediate_fixed"):
            first = bytes(self._render(mode))
            second = bytes(self._render(mode))
            self.assertEqual(first, second)

    def _render_without_candidate(self, mode: str) -> bytearray:
        return v.render_patched_bytes(
            self.stock,
            self.build,
            mode,
            self.chain,
            _fun_patches_override=self.chain_features,
        )[0]

    def test_expanded_rejects_before_candidate_output(self) -> None:
        with self.assertRaises(v.PatcherError):
            self._render("experimental_expanded_256")
        with self.assertRaises(v.PatcherError):
            self._render("experimental_expanded_256_progression")

    def test_manifest_mutation_refuses_before_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            bad_manifest = temp_path / "manifest.json"
            bad_map = temp_path / "map.json"
            mutated = dict(self.raw)
            mutated["price"] = 1
            bad_manifest.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
            shutil.copy2(self.map_path, bad_map)
            with patch.object(
                v,
                "VV3_FULL_HEAL_CANDIDATE_PATHS",
                {"manifest": bad_manifest, "map": bad_map},
            ):
                with self.assertRaises(v.PatcherError):
                    self._render("collection_progression")

    def test_missing_companion_refuses_before_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(v, "VV3_FULL_HEAL_DLL_PATH", Path(temp) / "missing.dll"):
                with self.assertRaises(v.PatcherError):
                    self._render("collection_progression")

    def test_corrupt_companion_refuses_before_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            corrupt = Path(temp) / "candidate.dll"
            corrupt.write_bytes(b"corrupt companion")
            with patch.object(v, "VV3_FULL_HEAL_DLL_PATH", corrupt):
                with self.assertRaises(v.PatcherError):
                    self._render("immediate_fixed")

    def test_native_and_forbidden_markers(self) -> None:
        cave = bytes.fromhex(self.raw["patches"][1]["after"])
        self.assertIn(b"\x6A\xFF\x6A\x64", cave)
        self.assertNotIn(b"\x94\x0E", cave)
        self.assertNotIn(b"\xFC\x0F", cave)
        self.assertNotIn(b"\xA0\x00\x00\x00", cave)
        self.assertIn("full_record+0xE6C", self.raw["health_setter"]["ecx"])
        self.assertEqual(self.raw["health_setter"]["forbidden"], "full_record+0xA0")
        self.assertEqual(self.raw["result_helper"]["va"], "0x4A3400")


if __name__ == "__main__":
    unittest.main()
