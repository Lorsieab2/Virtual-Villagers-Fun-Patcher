"""Repair Saves & Logs' retroactive rows say so when no game could be found for the save folder.

The live test (2026-11-23): with no game folder for the save folder (its name not the game folder's), the
"skill preferences on graves" and "Esteemed Elder" rows did nothing and said nothing.  They now say why
(src/vv_log_additions.py plan_apprentice, plan_esteemed), with no place looked in as well as with places that hold
no exe.  Nothing is written.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_apprentice_repair as ta  # noqa: E402
import vv_log_additions as additions  # noqa: E402


class NoGameNoteTests(unittest.TestCase):
    def test_the_rows_say_the_game_could_not_be_told(self) -> None:
        for game in (1, 2):
            for folders in (None, [], "missing"):
                with self.subTest(game=game, folders=folders):
                    f = ta.Fixture(game, None)
                    try:
                        looked = [f.folder.parent / "No Such Game"] if folders == "missing" else folders
                        before = {p: p.read_bytes() for p in f.folder.rglob("*") if p.is_file()}
                        kinds = {k.id: k for k in additions.plan(f.folder, game, 1, looked)}
                        preferred = [n for n in kinds["apprentice"].notes if "Checked Skill Preferences" in n]
                        self.assertTrue(preferred and "could not be told" in preferred[0])
                        self.assertTrue(any("Esteemed Elders in Every Game could not be told" in n
                                            for n in kinds["esteemed"].notes))
                        self.assertEqual({p: p.read_bytes() for p in f.folder.rglob("*") if p.is_file()}, before)
                    finally:
                        f.close()


if __name__ == "__main__":
    unittest.main()
