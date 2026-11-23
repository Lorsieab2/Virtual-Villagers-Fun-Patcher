"""Story / Cheat Upgrades hands the game the villager manager the running executable uses (v1.35.98 audit).

256 Villagers (Experimental) moves The Secret City's, The Tree of Life's and New Believers' population manager to
0x800000 (every `mov ecx, <stock manager>` rewritten) and widens the game's loops to 256 records.  The stock address
is then a dead object: a game routine run on it walks 256 records from it, past its 150 into unrelated memory.  Two
places of the adapters passed the stock constant:

* the villager catch-up after a Custom Island Event birth (C<N>_BIRTH: 0x45FFE0 / 0x468430 / 0x472C90);
* "Burying the dead"'s finder of the body to bury (C3_SUPPLY_197 0x45C950, C5_SUPPLY_230 0x470940).

Each runs here in the emulator beside the real rendered executable -- stock and with 256 Villagers -- through the
test build's VvfpStoryProbeManagerCall, the game routine stood in for so the test reads the manager it was given.
"""
from __future__ import annotations

import functools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_story_custom_island_event import (  # noqa: E402
    HAVE_EMULATOR, TEST_DLL, TEST_BUILD_ABSENT, _builds, have_stock, patcher, stock_path,
)

STOCK_MANAGER = {"vv3": 0x59E110, "vv4": 0x50E568, "vv5": 0x554148}
CATCH_UP = {"vv3": 0x45FFE0, "vv4": 0x468430, "vv5": 0x472C90}
BURY_FINDER = {"vv3": 0x45C950, "vv5": 0x470940}
MODE = "collection_progression"


@functools.lru_cache(maxsize=None)
def rendered(game: str, with_256: bool) -> bytes:
    ids = [f"{game}_origins_village_wide_upgrades", f"{game}_story_cheat_upgrades"]
    if with_256:
        ids.append(f"{game}_population_256")
    data, _ = patcher.render_patched_bytes(stock_path(game), _builds()[game], MODE, ids)
    return bytes(data)


def bury_row(game: str) -> int:
    import test_cie_behaviour_labels as labels
    rows = labels.adapter_table(int(game[2]))
    [index] = [i for i, row in enumerate(rows) if row[0] == "Burying the dead (Unsafe)"]
    return index


@unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")
@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class ManagerHandedToTheGame(unittest.TestCase):
    def process(self, game: str, with_256: bool):
        from story_emulator import Process
        if not have_stock(game):
            self.skipTest(f"needs inputs/{game}-stock-copy")
        p = Process(rendered(game, with_256), TEST_DLL)
        self.assertEqual(p.export("VvfpStoryInstall", int(game[2])), 1)
        return p

    def expected(self, game: str, with_256: bool) -> int:
        return 0x800000 if with_256 else STOCK_MANAGER[game]

    def test_the_catch_up_after_a_birth_runs_on_the_running_manager(self):
        for game in ("vv3", "vv4", "vv5"):
            for with_256 in (False, True):
                with self.subTest(game=game, with_256=with_256):
                    p = self.process(game, with_256)
                    seen = []
                    p.stub(CATCH_UP[game], lambda q: (seen.append(q.reg("ecx")), (0, 0))[1])
                    self.assertEqual(p.export("VvfpStoryProbeManagerCall", int(game[2]), 0, 0, 0), 1)
                    self.assertEqual(seen, [self.expected(game, with_256)])

    def test_burying_the_dead_finds_the_body_on_the_running_manager(self):
        for game in ("vv3", "vv5"):
            row = bury_row(game)
            for with_256 in (False, True):
                with self.subTest(game=game, with_256=with_256):
                    p = self.process(game, with_256)
                    seen = []
                    # no body awaiting burial (-1): the change is refused before the action runs
                    p.stub(BURY_FINDER[game], lambda q: (seen.append(q.reg("ecx")), (0xFFFFFFFF, 0))[1])
                    self.assertEqual(p.export("VvfpStoryProbeManagerCall", int(game[2]), 1, 0, row), 0)
                    self.assertEqual(seen, [self.expected(game, with_256)])


if __name__ == "__main__":
    unittest.main()
