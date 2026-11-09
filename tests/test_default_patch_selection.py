"""The Default Patches button selects everything except the deny-list.

The owner's rule: "if there's a defaults button in the patcher that selects
patches, can you exclude the 'learning never fails' patches for all 5 games
from being selected? otherwise it should select all patches."

There was no such button -- only Select All and Deselect All -- so one was
added, and the fresh-install default was pointed at the same rule so the two
cannot drift apart. These guards exist because the failure mode is silent: a
deny-list entry that matches no real patch leaves that patch selected and
nothing complains.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher_gui import (  # noqa: E402
    DEFAULT_OFF_FUN_PATCH_IDS,
    SELECT_ALL_OFF_FUN_PATCH_IDS,
    default_fun_patch_selection,
    owners_default_fun_patch_selection,
    select_all_fun_patch_selection,
)

GUI = ROOT / "src" / "vv_fun_patcher_gui.py"


def fun_patch_ids() -> set[str]:
    """Every patch a player can tick: builds.json's rows and the generated
    manifests the patcher loads beside them (Story / Cheat Upgrades lives in
    its own five data/*_story_cheat_upgrades_feature.json files)."""
    import vv_fun_patcher as patcher

    builds = json.loads(
        (ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
    return {str(patch["id"]) for patch in builds.get("fun_patches", [])} | {
        patch.id for patch in patcher.load_public_fun_patches()
    }


class DefaultPatchSelectionTests(unittest.TestCase):
    def test_every_denied_id_is_a_real_patch(self) -> None:
        """A typo would leave the patch selected and fail silently.

        This is the whole reason the guard exists: nothing in the GUI checks
        that a deny-list entry corresponds to anything, so a misspelled id
        reads exactly like an empty deny-list.
        """
        ids = fun_patch_ids()
        for denied in sorted(DEFAULT_OFF_FUN_PATCH_IDS):
            with self.subTest(patch=denied):
                self.assertIn(
                    denied, ids,
                    "%s is not a fun patch, so denying it does nothing"
                    % denied)

    def test_all_five_games_are_covered(self) -> None:
        """The owner asked for all five, not whichever happened to match."""
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertIn(
                    "vv%d_learning_never_fails" % game,
                    DEFAULT_OFF_FUN_PATCH_IDS)

    def test_no_learning_patch_is_selected_by_default(self) -> None:
        """Checked against the real catalog, not against the deny-list.

        Asserting the deny-list contains what the deny-list contains proves
        nothing. This asks the actual predicate about every actual patch.
        """
        for patch_id in sorted(fun_patch_ids()):
            if "learning_never_fails" in patch_id:
                with self.subTest(patch=patch_id):
                    self.assertFalse(
                        default_fun_patch_selection(patch_id),
                        "%s must be off by default" % patch_id)

    def test_everything_else_is_selected(self) -> None:
        """"otherwise it should select all patches" -- a deny-list, not an
        allow-list, so a newly added patch is on by default rather than
        silently omitted."""
        for patch_id in sorted(fun_patch_ids()):
            if patch_id in DEFAULT_OFF_FUN_PATCH_IDS:
                continue
            with self.subTest(patch=patch_id):
                self.assertTrue(
                    default_fun_patch_selection(patch_id),
                    "%s must be on by default" % patch_id)

    def test_the_deny_list_holds_back_exactly_the_learning_patches(
        self,
    ) -> None:
        """Nothing else may be quietly excluded along with them -- the one
        other default-off patches the owner asked for are the VV1 Mushroom/Collectible Duplication Cheat and the Super-Secret Golden Mushroom (VV2-VV5)."""
        ids = fun_patch_ids()
        off = {p for p in ids if not default_fun_patch_selection(p)}
        self.assertEqual(
            off, {p for p in ids if "learning_never_fails" in p
                  or p.endswith("_everyone_collects_like_vv1")
                  or p.endswith("_super_secret_golden_mushroom")
                  or p.endswith("_manual_drop_breeding_overrides_birth_control")
                  # Faith Loss is Doubled/Gains Halved (New Believers): a difficulty
                  # change, off by default (the owner, 2026-11-06).
                  or p == "vv5_faith_loss_doubled_gains_halved"
                  # Food Gains are Flat, like VV1-3 (Harder Games): off by default.
                  or p in ("vv4_food_pays_like_earlier_games", "vv5_food_pays_like_earlier_games")
                  # Checked Skill Preferences are listed as Jobs on Graves (all five games): off by default.
                  or p.endswith("_preferred_job_graves")
                  # Story / Cheat Upgrades and its cost row are NOT here: on by
                  # default since the owner's 2026-11-01 rule.
                  # 256 Villagers (Experimental): off by default -- it moves
                  # the villager table and changes the save format.
                  or p in ("vv3_population_256", "vv4_population_256", "vv5_population_256")
                  # The alternative of a pair that can never be built together:
                  # All Fruit Trees Refill at the Same Time is the one ticked.
                  or p == "vv3_fruit_trees_take_turns"
                  # Move the "Playing in the dirt" Spot is the alternative of Puddle Play Moves to the Lake Shore
                  # (the owner, 2026-11-08: off by default, in Owner's Defaults and in Select All).
                  or p == "vv5_playing_in_the_dirt_spot"
                  # Use Unicode Font is the alternative of Render Unicode with In-Game Fonts
                  # (the owner, 2026-11-01: off by default and in Owner's Defaults).
                  or p.endswith("_unicode_font")
                  # 2-10x Tech Cost (all five games; the owner, 2026-11-06: "Default OFF").
                  or p.endswith("_tech_cost_multiplier")
                  # Science Collectibles Only Count When Complete: a difficulty change too.
                  or p.endswith("_science_collectibles_complete")
                  # Hungrier Villagers and Classic VV Difficulty (the owner, 2026-11-07): difficulty changes too.
                  or p.endswith("_hungrier_villagers")
                  or p.endswith("_classic_vv_difficulty")
                  # Collectible Spawn Timing works like VV1-3 (the owner, 2026-11-08): a difficulty change too.
                  or p == "vv4_collectible_spawn_like_vv3"
                  or p == "vv4_harder_fishing_unlock"
                  # 2-10x Sickness and Sickness works like VV1-3 (the owner, 2026-11-08).
                  or p.endswith("_sickness_multiplier") or p.endswith("_sickness_like_vv3")
                  # Yellow Fruit Trees are No Longer Unlimited, a Classic VV Difficulty piece (the owner, 2026-11-08).
                  or p == "vv4_yellow_fruit_trees_limited"
                  # Memorial Actions Can Also Occur at the Heathen Hovel (the owner, 2026-11-08).
                  or p == "vv5_hovel_memorial_actions"
                  # Shrine to the Ancestors (the owner, 2026-11-08): on in Owner's Defaults only.
                  or p == "vv5_respectful_hovel_cover"
                  # Heathens Keep Their Masks When Converted (the owner, 2026-11-08: "default on in OWNERS
                  # DEFAULTS ONLY").
                  or p == "vv5_heathens_keep_masks_when_converted"
                  # Respecting the Legacy of Isola: off by default, on in Owner's Defaults and Select All.
                  or p == "vv5_respecting_the_legacy_of_isola"
                  # Skin Tones (A New Home; a draft): off by default, on in Owner's Defaults and Select All.
                  or p == "vv1_skin_tones"})

    def test_skin_tones_is_off_by_default_and_on_in_owners_defaults_and_select_all(self) -> None:
        """Skin Tones (A New Home; a draft for the owner): off by default, on in Owner's Defaults and Select All
        (no rule says otherwise: it changes neither the output's name nor the save format)."""
        patch_id = "vv1_skin_tones"
        self.assertIn(patch_id, fun_patch_ids())
        self.assertFalse(default_fun_patch_selection(patch_id))
        self.assertTrue(owners_default_fun_patch_selection(patch_id))
        self.assertTrue(select_all_fun_patch_selection(patch_id))

    def test_heathens_keep_masks_is_on_in_owners_defaults_only(self) -> None:
        """The owner (2026-11-08): "NEW PATCH FOR VV5, default on in OWNERS DEFAULTS ONLY." -- Select All ticks it
        like every other Owner's Defaults-only row (Faith Loss, Food Gains are Flat)."""
        patch_id = "vv5_heathens_keep_masks_when_converted"
        self.assertIn(patch_id, fun_patch_ids())
        self.assertFalse(default_fun_patch_selection(patch_id))
        self.assertTrue(owners_default_fun_patch_selection(patch_id))
        self.assertTrue(select_all_fun_patch_selection(patch_id))

    def test_harder_fishing_unlock_is_off_by_default_and_on_in_owners_defaults(self) -> None:
        """Harder Fishing Unlock in VV4 (the owner, 2026-11-08: "Default ON in Owner's Defaults") -- and off in the
        normal defaults, as a change that only makes the game harder.  No Fishing at Science Level 2 is removed
        ("not needed")."""
        from vv_fun_patcher_gui import UNTICKING_CONFLICT_IDS, owners_default_fun_patch_selection

        patch_id = "vv4_harder_fishing_unlock"
        self.assertIn(patch_id, fun_patch_ids())
        self.assertFalse(default_fun_patch_selection(patch_id))
        self.assertTrue(owners_default_fun_patch_selection(patch_id))
        self.assertTrue(select_all_fun_patch_selection(patch_id))
        self.assertNotIn(patch_id, UNTICKING_CONFLICT_IDS)
        self.assertNotIn("vv4_no_fishing_at_science_2", fun_patch_ids())

    def test_the_dirt_spot_is_off_everywhere_and_puddle_play_on_everywhere(self) -> None:
        """The owner (2026-11-08): Move the "Playing in the dirt" Spot is default OFF in the normal defaults,
        Owner's Defaults and Select All; Puddle Play Moves to the Lake Shore keeps its defaults (on everywhere) and
        now moves "Playing in the dirt" too, so the two untick each other."""
        from vv_fun_patcher_gui import UNTICKING_CONFLICT_IDS, owners_default_fun_patch_selection

        spot, puddles = "vv5_playing_in_the_dirt_spot", "vv5_puddles_by_the_lake"
        self.assertTrue({spot, puddles} <= fun_patch_ids())
        for pick in (default_fun_patch_selection, owners_default_fun_patch_selection, select_all_fun_patch_selection):
            with self.subTest(selection=pick.__name__):
                self.assertFalse(pick(spot))
                self.assertTrue(pick(puddles))
        self.assertEqual(UNTICKING_CONFLICT_IDS[spot], puddles)
        self.assertEqual(UNTICKING_CONFLICT_IDS[puddles], spot)

    def test_an_old_saved_selection_with_both_dirt_patches_loads_as_puddle_play_only(self) -> None:
        """Before 2026-11-08 both dirt patches were on by default, so settings saved then tick both; the strict
        resolver refuses the pair, so restoring them keeps Puddle Play Moves to the Lake Shore (the new default)
        and unticks Move the "Playing in the dirt" Spot.  A selection with only the dirt spot keeps it."""
        import shutil
        import tempfile
        import types
        from unittest import mock

        import vv_fun_patcher as patcher
        import vv_fun_patcher_gui as gui

        class Var:
            def __init__(self, value=None):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        spot, puddles = "vv5_playing_in_the_dirt_spot", "vv5_puddles_by_the_lake"
        root = Path(tempfile.mkdtemp(prefix="dsel"))
        self.addCleanup(shutil.rmtree, root, True)
        settings = root / "patcher_local_settings.json"
        public = patcher.load_public_fun_patches()
        old_default = [p.id for p in public if p.id in (spot, puddles) or default_fun_patch_selection(p.id)]

        def load(saved):
            settings.write_text(json.dumps({"fun_patches": saved}), encoding="utf-8")
            win = types.SimpleNamespace(
                fun_patches=public, fun_patch_vars={p.id: Var(False) for p in public},
                _apply_gui_dependency_selection=lambda cotick=True: None, exe_var=Var(), output_root_var=Var(),
                check_logs_var=Var(True), pair_rules={}, tree_window={}, tree_style={}, builds=[],
                all_folder_vars={}, patch_modes=[], patch_mode_var=Var(), game_mechanics_exes={})
            with mock.patch.object(gui, "SETTINGS", settings):
                gui.App._load_settings(win)
            return {pid for pid, var in win.fun_patch_vars.items() if var.get()}

        ticked = load(old_default)
        self.assertIn(puddles, ticked)
        self.assertNotIn(spot, ticked)
        self.assertEqual(ticked, set(old_default) - {spot})
        patcher.resolve_fun_patch_ids([p for p in ticked if p.startswith("vv5_")], game_id="vv5")
        self.assertIn(spot, load([spot]))
        self.assertEqual(gui.restored_fun_selection([spot, puddles, "x"]), [puddles, "x"])
        self.assertEqual(gui.restored_fun_selection([spot, "x"]), [spot, "x"])

    def test_story_cheat_upgrades_and_its_costs_are_on_by_default_in_all_five(self) -> None:
        """The owner (2026-11-01): "Anything that costs (money tech points food
        etc) and anything that adds new content to the game (besides the stuff
        I explicitly mentioned to turn off) stays ON by default." -- so the
        normal defaults tick Story / Cheat Upgrades AND its cost Tech Points
        row in every game, and the upgrades it adds are never free by default."""
        from vv_fun_patcher_gui import COTICKED_FUN_PATCH_IDS

        ids = fun_patch_ids()
        for game in range(1, 6):
            story = "vv%d_story_cheat_upgrades" % game
            cost = "vv%d_story_cheat_upgrades_cost_tech_points" % game
            with self.subTest(game=game):
                self.assertIn(story, ids)
                self.assertIn(cost, ids)
                self.assertNotIn(story, DEFAULT_OFF_FUN_PATCH_IDS)
                self.assertNotIn(cost, DEFAULT_OFF_FUN_PATCH_IDS)
                self.assertTrue(default_fun_patch_selection(story))
                # With Story / Cheat Upgrades on by default, its cost row is on
                # by default too: nothing is free.
                self.assertTrue(default_fun_patch_selection(cost))
                # ...and ticking the upgrades still ticks the cost row.
                self.assertEqual(COTICKED_FUN_PATCH_IDS[story], cost)

    def test_no_default_selection_ticks_story_without_its_costs(self) -> None:
        """Whatever the default ticks, a ticked Story / Cheat Upgrades always
        comes with its cost Tech Points row (all five games)."""
        ids = fun_patch_ids()
        for story in sorted(p for p in ids if p.endswith("_story_cheat_upgrades")):
            with self.subTest(patch=story):
                if default_fun_patch_selection(story):
                    self.assertTrue(default_fun_patch_selection(story + "_cost_tech_points"))

    def test_manual_drop_breeding_is_off_by_default_in_all_five(self) -> None:
        """The owner: "Default-OFF. Owner's-Defaults ON." -- all five games."""
        ids = fun_patch_ids()
        for game in range(1, 6):
            patch_id = "vv%d_manual_drop_breeding_overrides_birth_control" % game
            with self.subTest(patch=patch_id):
                self.assertIn(patch_id, ids)
                self.assertFalse(default_fun_patch_selection(patch_id))

    def test_everyone_collects_is_off_by_default_in_vv2_to_vv5(self) -> None:
        """The owner: "I would like a DEFAULT OFF patch for VV2-VV5"."""
        ids = fun_patch_ids()
        for game in range(2, 6):
            patch_id = "vv%d_everyone_collects_like_vv1" % game
            with self.subTest(patch=patch_id):
                self.assertIn(patch_id, ids)
                self.assertFalse(default_fun_patch_selection(patch_id))
        self.assertNotIn("vv1_everyone_collects_like_vv1", ids,
                         "A New Home already behaves this way")

    def test_the_button_exists_and_uses_the_shared_rule(self) -> None:
        """A button that ticks everything would satisfy its own label.

        The handler must consult the predicate rather than setting True, and
        the fresh-install default must consult it too -- otherwise a player
        who never presses the button gets a different selection from one who
        does, which is the drift this shares a rule to prevent.
        """
        source = GUI.read_text(encoding="utf-8")
        self.assertIn('text="Default Patches"', source)
        self.assertIn("command=self._default_fun_patches", source)

        body = source[source.index("def _default_fun_patches("):]
        body = body[:body.index("\n    def ")]
        self.assertIn("default_fun_patch_selection(patch_id)", body)
        self.assertNotIn("set(True)", body)

        # The fresh-install default, where the vars are created.
        created = source[source.index("self.fun_patch_vars = {"):]
        created = created[:created.index("}")]
        self.assertIn("default_fun_patch_selection(patch.id)", created)
        self.assertNotIn("value=True", created)

    def test_select_all_still_selects_all(self) -> None:
        """Default Patches is a new button, not a redefinition of Select All.

        A player who wants every patch, including the ones the default holds
        back, must still have a control that does that -- except 256 Villagers
        (Experimental), which the owner wants left off even by Select All,
        because it makes a separate "- Modded 256" game with its own saves.
        """
        source = GUI.read_text(encoding="utf-8")
        body = source[source.index("def _select_all_fun_patches("):]
        body = body[:body.index("\n    def ")]
        self.assertIn("select_all_fun_patch_selection(patch_id)", body)
        self.assertNotIn("default_fun_patch_selection", body)

        # ...and the alternative of a pair the patcher never builds together
        # (Fruit Trees Take Turns Refilling; its pair is ticked), so Select All
        # always gives a selection that builds.
        experimental = {"vv3_population_256", "vv4_population_256", "vv5_population_256"}
        held_back = experimental | {"vv3_fruit_trees_take_turns"} | {f"vv{n}_unicode_font" for n in range(1, 6)}
        # ...and Move the "Playing in the dirt" Spot, the alternative of Puddle Play Moves to the Lake Shore.
        held_back |= {"vv5_playing_in_the_dirt_spot"}
        # ...and 2-10x Tech Cost (the owner, 2026-11-06: "players who want it must explicitly choose it").
        held_back |= {f"vv{n}_tech_cost_multiplier" for n in range(1, 6)}
        # ...and Classic VV Difficulty, which would tick 2-10x Tech Cost through its dependencies.
        held_back |= {"vv4_classic_vv_difficulty", "vv5_classic_vv_difficulty"}
        self.assertEqual(set(SELECT_ALL_OFF_FUN_PATCH_IDS), held_back)
        ids = fun_patch_ids()
        self.assertTrue(held_back <= ids)
        for patch_id in sorted(ids):
            self.assertEqual(select_all_fun_patch_selection(patch_id),
                             patch_id not in held_back, patch_id)


    def test_tech_cost_multiplier_is_ticked_only_by_its_own_box(self) -> None:
        """The owner (2026-11-06): "7 should be default off for everything.
        players who want it must explicitly choose it." -- the fresh-install
        default, Default Patches and Select All leave every game's 2-10x Tech
        Cost unticked.  Owner's Defaults ticks it (the owner, 2026-11-07:
        "sure, default them on in vv1-3 too!")."""
        from vv_fun_patcher_gui import COTICKED_FUN_PATCH_IDS, owners_default_fun_patch_selection

        ids = fun_patch_ids()
        for game in range(1, 6):
            patch_id = "vv%d_tech_cost_multiplier" % game
            with self.subTest(patch=patch_id):
                self.assertIn(patch_id, ids)
                self.assertFalse(default_fun_patch_selection(patch_id))
                self.assertTrue(owners_default_fun_patch_selection(patch_id))
                self.assertFalse(select_all_fun_patch_selection(patch_id))
                self.assertNotIn(patch_id, COTICKED_FUN_PATCH_IDS.values())


if __name__ == "__main__":
    unittest.main()


class NewBelieversAndGravesRowsTests(unittest.TestCase):
    def test_checked_skill_preferences_on_graves_is_off_and_on_in_owners_defaults(self) -> None:
        """The owner: Checked Skill Preferences are listed as Jobs on Graves is off in the normal defaults and on in
        Owner's Defaults (all five games)."""
        ids = fun_patch_ids()
        for game in range(1, 6):
            patch_id = f"vv{game}_preferred_job_graves"
            self.assertIn(patch_id, ids)
            self.assertFalse(default_fun_patch_selection(patch_id), patch_id)
            self.assertTrue(owners_default_fun_patch_selection(patch_id), patch_id)

    def test_owners_defaults_tick_the_apprentice_puddle_and_faith_rows(self) -> None:
        """The owner (2026-11-06): Owner's Defaults keeps Children's Graves Say Apprentice (all four games), Puddle
        Play Moves to the Lake Shore and Faith Loss is Doubled/Gains Halved ON; the plain defaults leave only the
        Faith row off (a difficulty change)."""
        rows = ["vv1_apprentice_graves", "vv2_apprentice_graves", "vv3_apprentice_graves", "vv5_apprentice_graves",
                "vv5_puddles_by_the_lake", "vv5_faith_loss_doubled_gains_halved"]
        ids = fun_patch_ids()
        for patch_id in rows:
            self.assertIn(patch_id, ids)
            self.assertTrue(owners_default_fun_patch_selection(patch_id), patch_id)
            self.assertEqual(default_fun_patch_selection(patch_id),
                             patch_id != "vv5_faith_loss_doubled_gains_halved", patch_id)


class ManuallyOnSentenceTests(unittest.TestCase):
    """The owner (2026-11-07): "put a "Needs to be manually turned on." for any patch that is unchecked in normal
    defaults"."""

    def test_every_default_off_row_says_it_and_no_other_does(self) -> None:
        import vv_fun_patcher as patcher
        import vv_fun_patcher_gui as gui
        for patch in patcher.load_fun_patches():
            with self.subTest(patch.id):
                text = gui.row_description(patch)
                if gui.default_fun_patch_selection(patch.id):
                    self.assertEqual(text, patch.description)
                else:
                    self.assertTrue(text.endswith(gui.MANUALLY_ON))
                    self.assertEqual(text.count(gui.MANUALLY_ON), 1)


if __name__ == "__main__":
    unittest.main()
