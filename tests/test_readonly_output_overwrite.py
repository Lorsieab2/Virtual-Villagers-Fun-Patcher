"""Re-creating an output over an earlier one works when the game folder
carries read-only files or folders.

Found while rebuilding the owner's debug builds: their source games live in
"Read-Only Vanilla" copies, so the output inherited a read-only Images\\DRM
folder, and the second apply failed with "Access is denied" in the owned-tree
cleanup (Windows refuses rmdir/unlink on read-only entries).
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK_VV1 = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"


def _make_readonly(path: Path) -> None:
    os.chmod(path, stat.S_IREAD)


def _writable(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            os.chmod(os.path.join(dirpath, name), stat.S_IWRITE | stat.S_IREAD)


class ReadOnlyCleanupTests(unittest.TestCase):
    def test_owned_cleanup_removes_read_only_files_and_folders(self):
        base = Path(tempfile.mkdtemp())
        try:
            tree = base / "owned"
            (tree / "Images" / "DRM").mkdir(parents=True)
            f = tree / "Images" / "DRM" / "x.txt"
            f.write_text("x")
            _make_readonly(f)
            _make_readonly(tree / "Images" / "DRM")
            _make_readonly(tree / "Images")
            vfp._cleanup_owned_tree(tree)
            self.assertFalse(tree.exists())
        finally:
            _writable(base)
            shutil.rmtree(base, ignore_errors=True)

    @unittest.skipUnless(os.name == "nt", "the read-only attribute bites on Windows")
    def test_applying_twice_over_a_game_with_a_read_only_folder(self):
        base = Path(tempfile.mkdtemp())
        try:
            game = base / "game"
            (game / "Images" / "DRM").mkdir(parents=True)
            shutil.copy2(STOCK_VV1, game / STOCK_VV1.name)
            (game / "Images" / "DRM" / "drm.dat").write_bytes(b"drm")
            _make_readonly(game / "Images" / "DRM" / "drm.dat")
            _make_readonly(game / "Images" / "DRM")
            out = base / "out"
            cmd = [sys.executable, str(ROOT / "src" / "vv_fun_patcher.py"), "apply", "--overwrite",
                   "--patch-mode", "stock", "--output-root", str(out), str(game / STOCK_VV1.name)]
            for attempt in (1, 2):
                result = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, f"apply #{attempt}: {result.stderr[-600:]}")
            modded = out / "Virtual Villagers - A New Home - Modded"
            self.assertTrue((modded / "Images" / "DRM" / "drm.dat").is_file())
            leftovers = [p.name for p in out.iterdir() if p.name.startswith(".")]
            self.assertEqual(leftovers, [], "no failed/recovery folders left behind")
        finally:
            _writable(base)
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
