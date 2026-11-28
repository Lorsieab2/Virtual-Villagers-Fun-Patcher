"""A Skin Tones failure at patch time is never silent (Codex on #900): the tone pictures that could not be made
become a warning in the patch's log, on the command line and in the window when the patch is done."""
from __future__ import annotations

import inspect
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402


def _row(game: int):
    return types.SimpleNamespace(id=f"vv{game}_skin_tones", raw={})


class SkinToneWarnings(unittest.TestCase):
    def setUp(self):
        patcher.clear_patch_warnings()
        self.addCleanup(patcher.clear_patch_warnings)

    def test_a_failure_is_a_warning(self):
        import vv_skin_tone_art
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(vv_skin_tone_art, "install", side_effect=OSError("disk full")):
            (Path(folder) / "Images").mkdir()
            patcher._write_skin_tone_sheets(Path(folder), [_row(4)])
        self.assertEqual(patcher.patch_warnings(),
                         ["Skin Tones: the tone pictures could not be made (disk full); the game will show its own "
                          "skin."])

    def test_success_is_no_warning(self):
        import vv_skin_tone_art
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(vv_skin_tone_art, "install", return_value=["a.png"]):
            (Path(folder) / "Images").mkdir()
            patcher._write_skin_tone_sheets(Path(folder), [_row(4)])
        self.assertEqual(patcher.patch_warnings(), [])

    def test_the_log_the_command_line_and_the_window_carry_it(self):
        source = inspect.getsource(patcher.apply_patch)
        self.assertIn('log_data["warnings"] = PATCH_WARNINGS[warnings_before:]', source)
        self.assertLess(source.index("warnings_before = len(PATCH_WARNINGS)"),
                        source.index("_copy_companion_files(staging_folder, fun_patches)"))
        self.assertLess(source.index('log_data["warnings"]'), source.index("write_transparency_artifacts("))
        main = inspect.getsource(patcher.main)
        self.assertEqual(main.count('print(f"Warning: {warning}")'), 2, "apply and apply-all print them")
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertEqual(gui.count("self._show_patch_warnings()"), 2, "one game and all five show them")
        self.assertEqual(gui.count("clear_patch_warnings()"), 2)


if __name__ == "__main__":
    unittest.main()
