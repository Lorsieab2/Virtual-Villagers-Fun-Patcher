"""Regression tests for the VV4 "Optional Text changes" asset-swap patch.

The patch applied fine but could not be removed/toggled off: its companion
manifest set ``restore_sha256`` without a ``restore_source`` asset, so
``_remove_companion_files`` raised ``KeyError('restore_source')`` and the base
``Assets/sm.xml`` could never be restored.  These tests pin that the manifest
carries a real restore source and that a full apply->remove round-trip works.
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as v  # noqa: E402

MANIFEST = ROOT / "data" / "vv4_text_changes.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class VV4TextChangesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.companion = self.manifest["companion_files"][0]

    def test_manifest_has_restore_source_and_all_assets(self) -> None:
        c = self.companion
        # every hash-guarded field must be present, including the restore source
        for key in ("source", "destination", "sha256", "preimage_sha256",
                    "restore_source", "restore_sha256"):
            self.assertIn(key, c, f"companion manifest missing '{key}'")
        self.assertEqual(c["destination"], "Assets/sm.xml")
        edited = ROOT / c["source"]
        base = ROOT / c["restore_source"]
        self.assertTrue(edited.is_file(), "edited sm.xml asset is missing")
        self.assertTrue(base.is_file(), "base sm.xml restore asset is missing")
        self.assertEqual(_sha(edited), c["sha256"].upper())
        self.assertEqual(_sha(base), c["restore_sha256"].upper())
        # the guard compares against the base file
        self.assertEqual(c["preimage_sha256"].upper(), c["restore_sha256"].upper())

    def _apply_over(self, current_bytes: bytes):
        """Run _copy_companion_files against a temp game whose Assets/sm.xml is
        `current_bytes`; return the resulting sm.xml Path (raises on guard)."""
        import tempfile
        feature = next(p for p in v.load_fun_patches()
                       if p.id == "vv4_optional_text_changes")
        td = tempfile.mkdtemp()
        out = Path(td)
        (out / "Assets").mkdir()
        sm = out / "Assets" / "sm.xml"
        sm.write_bytes(current_bytes)
        v._copy_companion_files(out, [feature])
        return sm

    def test_apply_over_base_installs_edit(self) -> None:
        base = (ROOT / self.companion["restore_source"]).read_bytes()
        sm = self._apply_over(base)
        self.assertEqual(_sha(sm), self.companion["sha256"].upper())

    def test_reapply_over_already_edited_is_idempotent(self) -> None:
        # the re-apply case that used to fail with "preimage mismatch"
        edited = (ROOT / self.companion["source"]).read_bytes()
        sm = self._apply_over(edited)
        self.assertEqual(_sha(sm), self.companion["sha256"].upper())

    def test_apply_over_foreign_sm_xml_is_refused(self) -> None:
        # a localized/user-modified file must NOT be silently clobbered
        with self.assertRaises(v.PatcherError):
            self._apply_over(b"<root>a localized or user-modified sm.xml</root>\r\n")

    def test_apply_then_remove_round_trip_restores_base(self) -> None:
        feature = next(p for p in v.load_fun_patches()
                       if p.id == "vv4_optional_text_changes")
        c = self.companion
        base = ROOT / c["restore_source"]
        edited_hash = c["sha256"].upper()
        base_hash = c["restore_sha256"].upper()
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / "Assets").mkdir()
            sm = out / "Assets" / "sm.xml"
            sm.write_bytes(base.read_bytes())          # game ships the base file
            # apply -> swap in the edited version
            v._copy_companion_files(out, [feature])
            self.assertEqual(_sha(sm), edited_hash, "apply did not install edited sm.xml")
            self.assertIn(b"Esteemed Elder", sm.read_bytes())
            # remove -> restore the base version
            v._remove_companion_files(out, [feature])
            self.assertEqual(_sha(sm), base_hash, "remove did not restore base sm.xml")
            self.assertNotIn(b"Esteemed Elder", sm.read_bytes())


if __name__ == "__main__":
    unittest.main()
