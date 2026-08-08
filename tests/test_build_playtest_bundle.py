from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_playtest_bundle.py"


def load_module():
    spec = importlib.util.spec_from_file_location("vvfp_build_playtest_bundle", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load playtest bundle builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlaytestBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = load_module()

    def _fixture(self, root: Path) -> tuple[Path, str]:
        source = root / "Virtual Villagers - The Lost Children"
        source.mkdir()
        exe = source / "Virtual Villagers - The Lost Children.exe"
        payload = b"MZ" + bytes(range(32))
        exe.write_bytes(payload)
        (source / "Readme.txt").write_text("stock", encoding="utf-8")
        return source, hashlib.sha256(payload).hexdigest().upper()

    def _spec_patch(self, digest: str) -> mock._patch:
        return mock.patch.dict(
            self.bundle.GAME_SPECS,
            {
                "vv2": {
                    "title": "Virtual Villagers - The Lost Children",
                    "exe": "Virtual Villagers - The Lost Children.exe",
                    "size": 34,
                    "sha256": digest,
                }
            },
            clear=True,
        )

    def test_exact_stock_inventory_and_reparse_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, digest = self._fixture(Path(temporary))
            with self._spec_patch(digest):
                result = self.bundle.verify_stock_folder("vv2", source)
            self.assertEqual(result["stock_sha256"], digest)
            self.assertEqual(result["inventory"]["file_count"], 2)

    def test_save_like_source_is_rejected_before_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source, digest = self._fixture(Path(temporary))
            (source / "Village0.ldw").write_bytes(b"save")
            with self._spec_patch(digest), self.assertRaisesRegex(self.bundle.BundleError, "save-like"):
                self.bundle.verify_stock_folder("vv2", source)

    def test_disabled_or_pending_features_are_never_playtest_ready(self) -> None:
        fake = SimpleNamespace(
            get_fun_patch=lambda _feature: SimpleNamespace(
                raw={
                    "id": "reset_all_collections",
                    "game_id": "vv2",
                    "enabled": False,
                    "catalog_enabled": False,
                    "catalog_hidden": True,
                    "native_output": False,
                }
            )
        )
        with mock.patch.object(self.bundle, "_patcher_module", return_value=fake):
            with self.assertRaisesRegex(self.bundle.BundleError, "disabled"):
                self.bundle._assert_playtest_ready("vv2", "reset_all_collections")

    def test_pending_features_are_never_playtest_ready(self) -> None:
        fake = SimpleNamespace(
            get_fun_patch=lambda _feature: SimpleNamespace(
                raw={
                    "id": "complete_all_collections",
                    "game_id": "vv2",
                    "enabled": True,
                    "catalog_enabled": True,
                    "catalog_hidden": False,
                    "native_output": True,
                    "runtime_player_status": "pending",
                }
            )
        )
        with mock.patch.object(self.bundle, "_patcher_module", return_value=fake):
            with self.assertRaisesRegex(self.bundle.BundleError, "pending"):
                self.bundle._assert_playtest_ready("vv2", "complete_all_collections")

    def test_package_manifest_crc_and_zip_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, digest = self._fixture(root)
            game = root / "Virtual Villagers - The Lost Children - Modded"
            game.mkdir()
            (game / "Virtual Villagers - The Lost Children.exe").write_bytes((source / "Virtual Villagers - The Lost Children.exe").read_bytes())
            (game / "Virtual Villagers - The Lost Children - Modded.exe").write_bytes(b"modded")
            (game / "Readme.txt").write_text("playtest", encoding="utf-8")
            output_root = root / "outputs"
            with self._spec_patch(digest), mock.patch.object(self.bundle, "OUTPUTS_ROOT", output_root.resolve()), mock.patch.object(self.bundle, "_assert_feature_ids", return_value=[]):
                result = self.bundle.package_folder("vv2", game, output_root, ["feature"], "collection_progression")
            zip_path = Path(result["zip"])
            self.assertTrue(zip_path.is_file())
            with zipfile.ZipFile(zip_path) as archive:
                self.assertIsNone(archive.testzip())
                names = archive.namelist()
                self.assertIn("Virtual Villagers - The Lost Children - Modded/PLAYTEST-BUNDLE-MANIFEST.json", names)
                self.assertIn("Virtual Villagers - The Lost Children - Modded/Readme.txt", names)
            external = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(external["zip_sha256"], result["zip_sha256"])
            self.assertEqual(external["zip_entries"], result["zip_entries"])

    def test_package_rejects_save_like_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, digest = self._fixture(root)
            game = root / "Virtual Villagers - The Lost Children - Modded"
            game.mkdir()
            (game / "Virtual Villagers - The Lost Children.exe").write_bytes((source / "Virtual Villagers - The Lost Children.exe").read_bytes())
            (game / "Virtual Villagers - The Lost Children - Modded.exe").write_bytes(b"modded")
            (game / "Village0.ldw").write_bytes(b"save")
            output_root = root / "outputs"
            with self._spec_patch(digest), mock.patch.object(self.bundle, "OUTPUTS_ROOT", output_root.resolve()), mock.patch.object(self.bundle, "_assert_feature_ids", return_value=[]):
                with self.assertRaisesRegex(self.bundle.BundleError, "save-like"):
                    self.bundle.package_folder("vv2", game, output_root, ["feature"], "collection_progression")


if __name__ == "__main__":
    unittest.main()
