"""Story / Cheat Upgrades cost Tech Points (all five games).

The owner (2026-10-06): "an optional patch for the Story/Cheats patch ...
basically nullifies the 'everything costs 0 points' when Story/Cheats patch is
checked.  Custom Island Events/Custom Gong of Wonder/Pick Island Event will
cost the normal 'Island Event' upgrade cost", and "That patch should be
checked on if Story/Cheat upgrades is also on by default."

No executable byte of its own: the patcher sets bit 30 of the startup
loader's word; the Origins companion passes it to "VVFP Story Upgrades.dll"
(VvfpStoryCharge) before the install, which then verifies every price site
but writes none of the zero prices, and charges the Island Event upgrade's
30,000 for the story events.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
from test_story_custom_island_event import GAMES, TEST_DLL, emulated, have_stock, render  # noqa: E402

try:
    from story_emulator import Process
except ImportError:  # pragma: no cover - environment dependent
    Process = None

COST = "vv{}_story_cheat_upgrades_cost_tech_points"


def _price_sites(game: str) -> list[tuple[int, bytes, bytes]]:
    record = json.loads((ROOT / "data" / f"{game}_story_cheat_upgrades_feature.json").read_text(encoding="utf-8"))
    return [(int(d["va"], 16), bytes.fromhex(d["stock_bytes"]), bytes.fromhex(d["written_bytes"]))
            for d in record["runtime_detours"] if "written_bytes" in d and "price" in d["routine"]]


@emulated
class ChargeInstallTests(unittest.TestCase):
    def test_charging_keeps_every_price_and_the_events_cost_an_island_event(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            n = int(game[2:])
            for charge in (False, True):
                proc = Process(render(game, "collection_progression"), TEST_DLL)
                if charge:
                    proc.export("VvfpStoryCharge", n)
                self.assertEqual(proc.export("VvfpStoryInstall", n), 1)
                sites = _price_sites(game)
                with self.subTest(game=game, charge=charge):
                    self.assertTrue(sites)
                    for va, stock, written in sites:
                        self.assertEqual(proc.read(va, len(stock)), stock if charge else written)
                    self.assertEqual(proc.export("VvfpStoryInstalled", n), 1)
                    self.assertEqual(proc.export("VvfpStoryActive", n), 0 if charge else 1, "free")
                    self.assertEqual(proc.export("VvfpStoryEventPrice", n), 30000 if charge else 0)

    def test_a_charge_after_the_install_changes_nothing(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        proc = Process(render("vv3", "stock"), TEST_DLL)
        self.assertEqual(proc.export("VvfpStoryInstall", 3), 1)
        proc.export("VvfpStoryCharge", 3)
        self.assertEqual((proc.export("VvfpStoryActive", 3), proc.export("VvfpStoryEventPrice", 3)), (1, 0))


class SelectionTests(unittest.TestCase):
    def test_bit_30_only_with_the_row(self):
        catalog = {p.id: p for p in patcher.load_public_fun_patches()}
        for game in GAMES:
            n = int(game[2:])
            story = [catalog[f"{game}_origins_village_wide_upgrades"], catalog[f"{game}_story_cheat_upgrades"]]
            with self.subTest(game=game):
                self.assertFalse(patcher._startup_loader_mask(game, story) & patcher.STARTUP_LOADER_STORY_CHARGES)
                self.assertTrue(patcher._startup_loader_mask(game, story + [catalog[COST.format(n)]])
                                & patcher.STARTUP_LOADER_STORY_CHARGES)
                self.assertEqual(catalog[COST.format(n)].raw["dependencies"], [f"{game}_story_cheat_upgrades"])

    def test_the_bit_is_the_one_the_companions_read(self):
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        self.assertIn("#define VVFP_STARTUP_STORY_CHARGES 0x40000000u", header)
        self.assertEqual(patcher.STARTUP_LOADER_STORY_CHARGES, 0x40000000)

    def test_the_window_ticks_it_with_story_cheat_upgrades(self):
        import vv_fun_patcher_gui as gui
        for n in range(1, 6):
            with self.subTest(game=n):
                self.assertEqual(gui.COTICKED_FUN_PATCH_IDS[f"vv{n}_story_cheat_upgrades"], COST.format(n))
                self.assertIn(COST.format(n), gui.DEFAULT_OFF_FUN_PATCH_IDS)
                self.assertNotIn(COST.format(n), gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)


if __name__ == "__main__":
    unittest.main()
