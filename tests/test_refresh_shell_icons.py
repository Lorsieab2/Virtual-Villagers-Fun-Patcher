"""A patched game's icon shows again in a pinned taskbar or Start item and in Explorer.

The publish swaps the modified game's folder in by a rename, so Windows was never told the EXE at that path is a
new file and kept a stale, blank icon for it (the owner, 2026-10-27: the pinned Secret City - Modded 256 showed no
icon).  apply_patch now tells the shell the EXE changed and that icons must be read again."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

STOCK_VV3 = ROOT / "inputs" / "vv3-stock-copy" / "Virtual Villagers - The Secret City.exe"


class RefreshShellIcons(unittest.TestCase):

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_the_shell_is_told_the_exe_and_its_folder_changed_then_to_drop_its_icons(self):
        calls = []

        class Shell32:
            class SHChangeNotify:
                argtypes = restype = None

                def __new__(cls, event, flags, item, _other):
                    calls.append((event, flags, getattr(item, "value", item)))

        exe = Path(r"C:\Games\Modded\Game - Modded.exe")
        with mock.patch("ctypes.WinDLL", return_value=Shell32):
            patcher.refresh_shell_icons(exe)
        self.assertEqual(calls, [
            (patcher.SHCNE_UPDATEITEM, patcher.SHCNF_PATHW | patcher.SHCNF_FLUSHNOWAIT, str(exe)),
            (patcher.SHCNE_UPDATEITEM, patcher.SHCNF_PATHW | patcher.SHCNF_FLUSHNOWAIT, str(exe.parent)),
            (patcher.SHCNE_ASSOCCHANGED, patcher.SHCNF_IDLIST | patcher.SHCNF_FLUSHNOWAIT, None),
        ])

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_the_real_call_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / "Game.exe"
            exe.write_bytes(b"MZ")
            patcher.refresh_shell_icons(exe)

    def test_a_shell_failure_never_fails_a_patch(self):
        with mock.patch("ctypes.WinDLL", side_effect=OSError("no shell32")):
            patcher.refresh_shell_icons(Path("Game.exe"))

    def test_a_bad_argument_never_fails_a_patch(self):
        import ctypes

        class Shell32:
            class SHChangeNotify:
                argtypes = restype = None

                def __new__(cls, *_args):
                    raise ctypes.ArgumentError("bad argument")

        with mock.patch("ctypes.WinDLL", return_value=Shell32), mock.patch.object(patcher.os, "name", "nt"):
            patcher.refresh_shell_icons(Path("Game.exe"))

    def test_nothing_is_called_off_windows(self):
        with mock.patch("ctypes.WinDLL") as windll, mock.patch.object(patcher.os, "name", "posix"):
            patcher.refresh_shell_icons(Path("Game.exe"))
        windll.assert_not_called()

    def test_a_failed_patch_never_refreshes(self):
        """The refresh runs only after a publish that succeeded: a patch that is refused tells the shell nothing."""
        with tempfile.TemporaryDirectory() as out, \
                mock.patch.object(patcher, "refresh_shell_icons") as refresh:
            missing = Path(out) / "missing.exe"
            with self.assertRaises(Exception):
                patcher.apply_patch(missing, "stock", False, [], output_root=Path(out))
        refresh.assert_not_called()

    def test_a_patch_refreshes_the_published_exe(self):
        if not STOCK_VV3.is_file():
            self.skipTest("stock VV3 executable not present")
        with tempfile.TemporaryDirectory() as out, \
                mock.patch.object(patcher, "refresh_shell_icons") as refresh:
            output, _log = patcher.apply_patch(STOCK_VV3, "stock", False, [], output_root=Path(out))
        refresh.assert_called_once_with(output)


if __name__ == "__main__":
    unittest.main()
