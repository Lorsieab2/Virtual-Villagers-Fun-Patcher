"""scripts/export_game_mechanics_claims.py, The Secret City (VV3): every line the Game Mechanics window renders
from the fixtures, the fruit trees, the techs, the patches and the tree timing patches' schedule is in the claims
file, and the file is written under its name with its statuses, evidence and patches.  The shared checks are in
tests/game_mechanics_claims_cases.py."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import game_mechanics_claims_cases as cases  # noqa: E402
import test_game_mechanics as t  # noqa: E402

gm = cases.gm
export = cases.export


class Coverage(cases.ClaimsCases, unittest.TestCase):
    GAME = 3

    def test_the_secret_citys_trees_and_patches(self) -> None:
        clock = (6, 0, 100_000, 50_000)
        for speed, c in ((6, clock), (3, (3, 0, 100_000, 50_000)), (1009, (0, 10, 100_000, 50_000))):
            for trees in ([(1, 46_400, 49_000, 300)], [(0, 1, 40_000, 100)], [(2, 1, 1, 1000)],
                          [(0, 49_000, 45_000, 10)]):
                for techs in ((1, 1, 1, 1, 1, 0, 0), (3, 3, 3, 3, 3, 3, 0)):
                    data = t.make_save(clock=c, speed=speed, trees=trees, techs=techs)
                    for features in (None, [], ["vv3_nature_honey_refill"]):
                        with self.subTest(speed=speed, trees=trees, techs=techs, features=features):
                            self.assert_covered(3, self.page(3, data, t.EPOCH + 100_000 + 20_000, features))

    def test_the_tree_timing_patches_schedule(self) -> None:
        clock = (6, 0, 100_000, 50_000)
        for speed, c in ((6, clock), (1005, (0, 6, 100_000, 50_000))):
            data = t.make_save(clock=c, speed=speed, trees=[(1, 46_400, 49_000, 300), (0, 1_000, 40_000, 1000)])
            for mode in (1, 2):
                with self.subTest(speed=speed, mode=mode):
                    timers = export._tree_timer_file(data, mode)
                    base = next(item.base for item in cases.vv_tribe_rename.GAMES if item.number == 3)
                    root = Path(tempfile.mkdtemp(prefix="gmt"))
                    self.addCleanup(shutil.rmtree, root, True)
                    folder = root / base
                    place = folder / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Fruit Trees"
                    place.mkdir(parents=True)
                    (place / "Virtual Villagers 3 Fruit Tree Timers - Save 1.dat").write_bytes(timers)
                    (folder / f"{base}1.ldw").write_bytes(data)
                    facts = gm.read(folder, 3, 1, [], now=t.EPOCH + 120_000)
                    self.assertTrue(any("schedule, read from its file" in f.text for f in facts))
                    self.assert_covered(3, facts)

    def check_claims_file(self, text: str) -> None:
        super().check_claims_file(text)
        self.assertIn("Virtual Villagers 3 - The Secret City - Game Mechanics Claims.txt", export.file_name(3))
        for status in ("UNCONFIRMED", "READ FROM THE SAVE", "VERIFIED FROM RUNNING CODE"):
            self.assertIn(f"Status: {status}", text)
        self.assertIn("- Honey: # of 3000", text)                 # a rule's own number kept, the save's not
        self.assertIn("- Tree #: Mango\n", text)
        self.assertIn("- Planted at <date>; refills every ", text)
        self.assertRegex(text, r"- Planted when the village was <time> old, counted on Normal speed \(started [^;]+; the "
                               r"save keeps no real date before [^)]+\); refills every ")
        self.assertIn("Patches: Nature Level 1 Actually Replenishes Food Sources Faster", text)


if __name__ == "__main__":
    unittest.main()
