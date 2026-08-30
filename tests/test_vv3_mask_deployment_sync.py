from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
DEPLOYED = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"
BUILDER = ROOT / "scripts" / "build_vv3_safe_upgrade_resources.py"
COMPILE_SCRIPT = ROOT / "scripts" / "build_vv3_full_mastery_candidate_dll.ps1"
ORIGINS_BUILDER = ROOT / "scripts" / "build_vv3_origins_feature.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("vv3_safe_upgrade_sync", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load VV3 companion synchronizer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VV3MaskDeploymentSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = _load_builder()

    def test_deployed_companion_is_byte_identical_to_canonical_build(self) -> None:
        canonical = SOURCE.read_bytes()
        deployed = DEPLOYED.read_bytes()
        self.assertEqual(deployed, canonical)
        # Assert against the synchronizer's own reviewed pin rather than a second
        # copy of the digest.  A duplicated literal here silently goes stale on
        # every legitimate DLL rebuild, which is exactly how it drifted before.
        self.assertEqual(
            hashlib.sha256(deployed).hexdigest().upper(),
            self.builder.SOURCE_SHA256,
        )
        self.assertEqual(len(deployed), self.builder.SOURCE_SIZE)

    def test_manifest_hash_is_the_canonical_deployed_hash(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        companion = manifest["companion_files"][0]
        self.assertEqual(companion["source"], "data/candidates/VVFP VV3 Safe Upgrades.dll")
        self.assertEqual(
            companion["sha256"],
            hashlib.sha256(SOURCE.read_bytes()).hexdigest().upper(),
        )

    def test_patcher_output_contains_the_village_mask_hook_and_append(self) -> None:
        stock = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
        if not stock.is_file():
            self.skipTest("stock VV3 executable fixture is unavailable")
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher
        build = next(item for item in vv_fun_patcher.load_builds() if item.id == "vv3")
        rendered, _ = vv_fun_patcher.render_patched_bytes(
            stock, build, "collection_progression", ["vv3_enable_origins_exclusive_features"]
        )
        self.assertEqual(rendered[0x60C7F:0x60C84], bytes.fromhex("E87CE32700"))
        self.assertEqual(len(rendered), 0xCB000 + 0x2000)

    def test_canonical_build_contains_every_mask_export(self) -> None:
        exports = self.builder.export_names(SOURCE.read_bytes())
        self.assertTrue(self.builder.REQUIRED_MASK_EXPORTS <= exports)
        self.assertTrue(self.builder.REQUIRED_RUNNING_EXPORTS <= exports)
        self.assertIn("VV3RunningMaskBoundary", exports)
        self.assertEqual(len(exports), 32)

    def test_deployed_companion_carries_the_source_result_messages(self) -> None:
        """The shipped DLL must contain the strings the C source defines.

        Editing a user-facing string in the C source without rebuilding leaves
        the source-only assertions passing while the game keeps showing the old
        text.  That happened with the mask-refusal message: the source said
        "No active save slot is available yet" while the released companion
        still said "until this village has been saved at least once".
        """
        source = (
            ROOT
            / "native"
            / "vv3_full_mastery_candidate"
            / "vv3_full_mastery_candidate.c"
        ).read_text(encoding="utf-8")
        deployed = DEPLOYED.read_bytes()
        # Each distinct Change Appearance for All refusal reason.
        for phrase in (
            "No active save slot is available yet",
            "That mask option was not recognized",
            "Some villagers cannot be told apart",
            "There was no room to record the selected masks",
            "No eligible villagers matched the selected appearance options.",
        ):
            with self.subTest(message=phrase):
                self.assertIn(phrase, source, "phrase is missing from the C source")
                self.assertIn(
                    phrase.encode("ascii"),
                    deployed,
                    "the deployed companion predates this source string; "
                    "rebuild the canonical DLL and re-pin it",
                )
        # And the superseded wording must not still be shipping.
        self.assertNotIn(
            b"until this village has been saved at least once",
            deployed,
            "the deployed companion still carries the replaced message",
        )

    def test_synchronize_repairs_a_stale_deployed_copy(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / DEPLOYED.name
            target.write_bytes(b"stale companion")
            with patch.object(self.builder, "OUTPUT", target):
                size, digest, exports = self.builder.synchronize()
            canonical = SOURCE.read_bytes()
            self.assertEqual(target.read_bytes(), canonical)
            self.assertEqual(size, len(canonical))
            self.assertEqual(digest, hashlib.sha256(canonical).hexdigest().upper())
            self.assertTrue(self.builder.REQUIRED_MASK_EXPORTS <= exports)
            self.assertTrue(self.builder.REQUIRED_RUNNING_EXPORTS <= exports)

    def test_compile_path_runs_synchronizer_after_native_build(self) -> None:
        script = COMPILE_SCRIPT.read_text(encoding="utf-8")
        invocation = '& python (Join-Path $projectRoot "scripts\\build_vv3_safe_upgrade_resources.py")'
        self.assertIn(invocation, script)
        self.assertIn('throw "VV3 Safe Upgrades companion synchronization failed."', script)

    def test_origins_builder_rejects_companion_drift(self) -> None:
        script = ORIGINS_BUILDER.read_text(encoding="utf-8")
        self.assertIn("CANONICAL_COMPANION", script)
        self.assertIn("COMPANION.read_bytes() != CANONICAL_COMPANION.read_bytes()", script)
        self.assertIn("VV3 deployed companion is stale", script)


if __name__ == "__main__":
    unittest.main()
