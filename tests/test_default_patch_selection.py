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
    default_fun_patch_selection,
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
                  or p.endswith("_story_cheat_upgrades")
                  # 256 Villagers (Experimental): off by default -- it moves
                  # the villager table and changes the save format.
                  or p in ("vv3_population_256", "vv4_population_256", "vv5_population_256")})

    def test_story_cheat_upgrades_is_off_by_default_in_all_five(self) -> None:
        """The owner: Story / Cheat Upgrades is a default-off patch."""
        ids = fun_patch_ids()
        for game in range(1, 6):
            patch_id = "vv%d_story_cheat_upgrades" % game
            with self.subTest(patch=patch_id):
                self.assertIn(patch_id, ids)
                self.assertIn(patch_id, DEFAULT_OFF_FUN_PATCH_IDS)
                self.assertFalse(default_fun_patch_selection(patch_id))

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
        back, must still have a control that does that.
        """
        source = GUI.read_text(encoding="utf-8")
        body = source[source.index("def _select_all_fun_patches("):]
        body = body[:body.index("\n    def ")]
        self.assertIn("set(True)", body)
        self.assertNotIn("default_fun_patch_selection", body)


if __name__ == "__main__":
    unittest.main()
