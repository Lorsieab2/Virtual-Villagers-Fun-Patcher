"""The Owner's Defaults button.

The owner: "can you add a new button to the patcher? Owner's Defaults: Every
patch EXCEPT FOR LEARNING NEVER FAILS is on. (makes my life easier)" -- so it
ticks the other default-off patches too (e.g. VV1 Mushroom/Collectible Duplication Cheat), unlike Default Patches.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vfp  # noqa: E402
from vv_fun_patcher_gui import (  # noqa: E402
    DEFAULT_OFF_FUN_PATCH_IDS,
    owners_default_fun_patch_selection,
)

GUI = ROOT / "src" / "vv_fun_patcher_gui.py"


def _ids():
    return {p.id for p in vfp.load_public_fun_patches()}


def _owner_keeps_off(patch_id: str) -> bool:
    """The owner's one exception: Learning Skills Never Fails.  Story / Cheat
    Upgrades and 256 Villagers (Experimental) are ticked (owner, 2026-10-03:
    "please toggle ON in the Owner's Defaults: 256 experimental patches,
    Story events patches").  ...and of The Secret City's two fruit-tree schedules, which are
    never built together, the owner picks Fruit Trees Take Turns Refilling, so All Fruit Trees
    Refill at the Same Time stays off."""
    # The owner (2026-11-01): "For Owner's Defaults, I'd like to have the ingame fonts toggled on" -- Use
    # Unicode Font, the alternative of Render Unicode with In-Game Fonts, stays off.
    # 2-10x Tech Cost IS ticked (the owner, 2026-11-07: "sure, default them on in vv1-3 too!"); Story / Cheat
    # Upgrades cost Tech Points is not ("set "story upgrades cost tech points" default off in owner's defaults").
    # Move the "Playing in the dirt" Spot stays off (the owner, 2026-11-08): Puddle Play Moves to the Lake Shore,
    # ticked, moves "Playing in the dirt" to the lake shore, and the two untick each other.
    return ("learning_never_fails" in patch_id or patch_id == "vv3_fruit_trees_refill_together"
            or patch_id.endswith("_unicode_font") or patch_id.endswith("_story_cheat_upgrades_cost_tech_points")
            or patch_id == "vv5_playing_in_the_dirt_spot"
            # The owner (2026-11-11): Yellow Breadfruit Refills Partially Every Time is off in Owner's Defaults.
            or patch_id == "vv4_yellow_fruit_refills_partially")


class OwnersDefaultsTests(unittest.TestCase):
    def test_everything_but_learning_never_fails_is_ticked(self):
        for patch_id in sorted(_ids()):
            with self.subTest(patch=patch_id):
                self.assertEqual(owners_default_fun_patch_selection(patch_id),
                                 not _owner_keeps_off(patch_id))

    def test_story_cheat_upgrades_and_256_are_ticked(self):
        ids = _ids()
        wanted = [f"vv{game}_story_cheat_upgrades" for game in range(1, 6)]
        wanted += ["vv3_population_256", "vv4_population_256", "vv5_population_256"]
        for patch_id in wanted:
            with self.subTest(patch=patch_id):
                self.assertIn(patch_id, ids)
                self.assertTrue(owners_default_fun_patch_selection(patch_id))

    def test_it_ticks_the_other_default_off_patches(self):
        others = {p for p in DEFAULT_OFF_FUN_PATCH_IDS if not _owner_keeps_off(p)}
        self.assertTrue(others, "there is at least one other default-off patch to cover")
        for patch_id in sorted(others):
            with self.subTest(patch=patch_id):
                self.assertTrue(owners_default_fun_patch_selection(patch_id))

    def test_no_ticked_patch_needs_a_learning_patch(self):
        # Otherwise the GUI's dependency closure would tick it straight back.
        for patch in vfp.load_public_fun_patches():
            if not owners_default_fun_patch_selection(patch.id):
                continue
            for dep in patch.raw.get("dependencies") or ():
                with self.subTest(patch=patch.id, dependency=dep):
                    self.assertNotIn("learning_never_fails", dep)

    def test_the_button_exists_and_uses_its_rule(self):
        source = GUI.read_text(encoding="utf-8")
        self.assertIn('text="Owner\'s Defaults"', source)
        self.assertIn("command=self._owners_default_fun_patches", source)
        body = source[source.index("def _owners_default_fun_patches("):]
        body = body[:body.index("\n    def ")]
        self.assertIn("owners_default_fun_patch_selection(patch_id)", body)
        self.assertIn("self._fun_patch_changed()", body)


if __name__ == "__main__":
    unittest.main()
