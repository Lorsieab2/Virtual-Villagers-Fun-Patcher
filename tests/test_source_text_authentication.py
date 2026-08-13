from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher


class SourceTextAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(
            (ROOT / "data/source-text-authentication.json").read_text(encoding="utf-8")
        )

    def test_algorithm_is_explicit_and_versioned(self):
        self.assertEqual(self.inventory["algorithm"], patcher.SOURCE_TEXT_DIGEST_ALGORITHM)
        self.assertEqual(self.inventory["algorithm"], "vvfp.source-text.v1")

    def test_every_inventory_digest_matches_windows_worktree_and_git_blob(self):
        for artifact in self.inventory["artifacts"]:
            with self.subTest(path=artifact["path"]):
                worktree = (ROOT / artifact["path"]).read_bytes()
                blob = subprocess.run(
                    ["git", "show", f"HEAD:{artifact['path']}"],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                ).stdout
                self.assertEqual(patcher.source_text_sha256(worktree), artifact["sha256"])
                self.assertEqual(patcher.source_text_sha256(blob), artifact["sha256"])

    def test_lf_crlf_cr_and_bom_have_one_digest(self):
        lf = b'{"enabled":false}\n'
        variants = (lf, lf.replace(b"\n", b"\r\n"), lf.replace(b"\n", b"\r"), b"\xef\xbb\xbf" + lf)
        self.assertEqual(len({patcher.source_text_sha256(item) for item in variants}), 1)

    def test_semantic_byte_change_still_changes_digest(self):
        original = b'{"enabled":false}\n'
        changed = b'{"enabled":true}\n'
        self.assertNotEqual(patcher.source_text_sha256(original), patcher.source_text_sha256(changed))

    def test_invalid_utf8_is_rejected(self):
        with self.assertRaises(patcher.PatcherError):
            patcher.source_text_sha256(b"\xff")


if __name__ == "__main__":
    unittest.main()
