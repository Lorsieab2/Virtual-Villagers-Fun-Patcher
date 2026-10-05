"""Overwriting with fewer patches must not leave the dropped patches running.

Most companion DLLs switch their feature on merely by being present in the game
folder -- Show Parents, Sort By, Improved Pathfinding, Fix Huts, Work First and
others change no exe bytes at all. The overwrite path used to carry every file
of the earlier install that the fresh tree lacked into the new one, to keep the
player's own files; that swept up the patcher's own companions too, so a patch
unticked in the GUI kept running after "Replace the whole copied folder".
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK_VV1 = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"

# Companion-only VV1 patches: none replaces a stock file, so a folder holding
# only the stock exe is a complete source for them.
COMPANION_PATCHES = (
    "vv1_number_keys",
    "vv1_improved_pathfinding",
    "vv1_sort_by",
    "vv1_builders_fix_huts",
    "vv1_builders_and_healers_work_first",
)


@unittest.skipUnless(STOCK_VV1.is_file(), "stock VV1 executable not present")
class OverwriteDropsUnselectedCompanionsTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        game = self.base / "game"
        game.mkdir()
        self.source = game / STOCK_VV1.name
        shutil.copy2(STOCK_VV1, self.source)

    def _apply(self, root: Path, patch_ids, overwrite: bool) -> Path:
        output, _ = vfp.apply_patch(
            self.source,
            patch_mode="stock",
            overwrite=overwrite,
            fun_patch_ids=list(patch_ids),
            output_root=root,
        )
        return output.parent

    @staticmethod
    def _files(folder: Path) -> set[str]:
        return {
            p.relative_to(folder).as_posix()
            for p in folder.rglob("*")
            if p.is_file() and not p.name.endswith((".patch-log.json", ".transparency.json"))
        }

    def test_the_first_install_really_ships_companions(self):
        # Guards the premise: without companions the later assertions are vacuous.
        folder = self._apply(self.base / "out", COMPANION_PATCHES, overwrite=False)
        dlls = {name for name in self._files(folder) if name.lower().endswith(".dll")}
        self.assertGreaterEqual(len(dlls), len(COMPANION_PATCHES) - 1, dlls)

    def test_overwrite_with_none_matches_a_fresh_install_of_none(self):
        out = self.base / "out"
        folder = self._apply(out, COMPANION_PATCHES, overwrite=False)
        (folder / "my notes.txt").write_text("player file", encoding="utf-8")
        self._apply(out, (), overwrite=True)

        fresh = self._apply(self.base / "fresh", (), overwrite=False)
        expected = self._files(fresh) | {"my notes.txt"}
        self.assertEqual(self._files(folder), expected)
        self.assertEqual(
            (folder / "my notes.txt").read_text(encoding="utf-8"), "player file"
        )

    def test_overwrite_with_a_subset_keeps_only_the_selected_companions(self):
        out = self.base / "out"
        self._apply(out, COMPANION_PATCHES, overwrite=False)
        folder = self._apply(out, ("vv1_number_keys",), overwrite=True)
        fresh = self._apply(self.base / "fresh", ("vv1_number_keys",), overwrite=False)
        self.assertEqual(self._files(folder), self._files(fresh))

    def test_a_companion_recorded_only_in_the_old_log_is_dropped(self):
        # A feature retired from the catalog is known only through the earlier
        # install's own patch log.
        out = self.base / "out"
        folder = self._apply(out, (), overwrite=False)
        retired = folder / "VVFP Retired Feature.dll"
        retired.write_bytes(b"MZ")
        log = next((folder / "Virtual Villagers Fun Patcher Files").glob("*.patch-log.json"))
        data = json.loads(log.read_text(encoding="utf-8"))
        data["companion_files"] = [
            {"feature": "vv1_retired", "path": str(retired), "sha256": "00"}
        ]
        log.write_text(json.dumps(data), encoding="utf-8")
        self._apply(out, (), overwrite=True)
        self.assertFalse(retired.exists())

    def test_a_moved_install_still_drops_its_logged_companions(self):
        # The log's paths are absolute. When the modded folder is moved before
        # the next overwrite, they must still be resolved against the folder
        # the log was published to, not silently kept as player files.
        old_root = self.base / "old"
        folder = self._apply(old_root, (), overwrite=False)
        retired = folder / "VVFP Retired Feature.dll"
        retired.write_bytes(b"MZ")
        log = next((folder / "Virtual Villagers Fun Patcher Files").glob("*.patch-log.json"))
        data = json.loads(log.read_text(encoding="utf-8"))
        data["companion_files"] = [
            {"feature": "vv1_retired", "path": str(retired), "sha256": "00"}
        ]
        log.write_text(json.dumps(data), encoding="utf-8")
        new_root = self.base / "moved"
        new_root.mkdir()
        moved = new_root / folder.name
        shutil.move(str(folder), str(moved))
        self.assertTrue((moved / retired.name).exists())
        self._apply(new_root, (), overwrite=True)
        self.assertFalse((moved / retired.name).exists())


if __name__ == "__main__":
    unittest.main()
