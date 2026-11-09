"""Respecting the Legacy of Isola (New Believers): one row that ticks the owner's five respectful patches, built like
Classic VV Difficulty (scripts/build_respecting_the_legacy_of_isola_feature.py).  Off by default; on in Owner's
Defaults and Select All; drawn with a green title; not part of Classic VV Difficulty."""
from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_respecting_the_legacy_of_isola_feature as builder  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402
import vv_how_to_use as how  # noqa: E402

ID = "vv5_respecting_the_legacy_of_isola"
PIECES = {
    "vv5_guardians_of_isola_rewrite": "Guardians of Isola Rewrite",
    "vv5_respectful_hovel_cover": "Shrine to the Ancestors",
    "vv5_heathens_keep_masks_when_converted": "Heathens Keep Their Masks When Converted",
    "vv5_hovel_memorial_actions": "Memorial Actions Can Also Occur at the Heathen Hovel",
    "vv5_heathen_conversion_notice": "Popup When Believers Become Heathens",
}
NOT_PIECES = ("vv5_last_names", "vv5_heathen_mommy_puzzle_restoration", "vv5_devoted_soul_epitaph")
# The owner's own opening sentences for each piece.
OPENINGS = {
    "vv5_guardians_of_isola_rewrite": "Changes some aspects of VV5 to make things more culturally respectful "
                                      "(hopefully!) Focused around peace, post-traumatic healing and growth.",
    "vv5_respectful_hovel_cover": "Turns the restored hovel into an ancestral shrine. A sacred, peaceful place where "
                                  "villagers can honor the ancestral spirits that guide them.",
    "vv5_heathens_keep_masks_when_converted": "\"Heathen\" masks are culturally important to them. Their choices "
                                              "must be honored.",
    "vv5_hovel_memorial_actions": "Best paired with \"Shrine to the Ancestors\". Villagers will sometimes come here "
                                  "to pay their respects to those that passed on, and others that guide their fate.",
    "vv5_heathen_conversion_notice": "Meant to make VV5 harder and push players to take care of their tribe.",
}


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _window(ticked=()):
    """The window's selection state, with the real dependency methods bound to it."""
    win = types.SimpleNamespace()
    win.fun_patches = gui.load_public_fun_patches()
    win.fun_patch_vars = {patch.id: _Var(patch.id in ticked) for patch in win.fun_patches}
    win._last_fun_selection = set(ticked)
    for name in ("_patch_dependency_map", "_apply_gui_dependency_selection"):
        setattr(win, name, types.MethodType(getattr(gui.App, name), win))
    return win


def _ticked(win) -> set[str]:
    return {patch_id for patch_id, var in win.fun_patch_vars.items() if var.get()}


class TheRowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.public = {p.id: p for p in patcher.load_public_fun_patches()}

    def test_its_dependencies_are_exactly_the_five_pieces(self) -> None:
        row = self.public[ID]
        self.assertEqual(row.name, "Respecting the Legacy of Isola")
        self.assertEqual(row.game_id, "vv5")
        self.assertEqual(row.raw["dependencies"], list(PIECES))
        self.assertEqual(row.raw["patches"], [])
        self.assertEqual(row.raw["companion_files"], [])
        for patch_id, name in PIECES.items():
            self.assertEqual(self.public[patch_id].name, name)
        for patch_id in NOT_PIECES:
            self.assertNotIn(patch_id, row.raw["dependencies"])

    def test_the_committed_file_is_the_builders(self) -> None:
        committed = json.loads((ROOT / "data" / f"{ID}_feature.json").read_text(encoding="utf-8"))
        self.assertEqual(committed, builder.feature())
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn(f'"data/{ID}_feature.json"', release)

    def test_the_description_states_its_dependencies_in_bold_first_and_lists_each_piece(self) -> None:
        description = self.public[ID].description
        self.assertTrue(description.startswith("**Needs all five of the patches it names: "))
        first_bold = gui.split_bold(description)[0]
        self.assertTrue(first_bold[1])
        for name in PIECES.values():
            self.assertIn(name, first_bold[0])
        for patch_id, opening in OPENINGS.items():
            self.assertIn(f": {opening}", description)
        bold = " ".join(text for text, is_bold in gui.split_bold(description) if is_bold)
        self.assertIn("Origins-exclusive base", bold)
        self.assertIn("adds the Origins Upgrades buttons", bold)
        self.assertIn("Story / Cheat Upgrades", bold)

    def test_each_piece_opens_with_the_owners_sentence(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        howto = " ".join((ROOT / "How to Use.txt").read_text(encoding="utf-8").split())
        for patch_id, opening in OPENINGS.items():
            with self.subTest(patch=patch_id):
                description = self.public[patch_id].description
                if description.startswith("**"):
                    # Right after the bold dependency sentence the row opens with.
                    description = description.split(" Villager Details screens. ", 1)[1]
                self.assertTrue(description.startswith(opening), description[:120])
                guide = how.guide(how.patch_key(patch_id), PIECES[patch_id]).lines
                self.assertTrue(guide[0].startswith(opening.split(". ")[0]), guide[0])
                self.assertIn(opening, readme)
                self.assertIn(opening, howto)

    def test_ticking_it_ticks_the_five_and_unticking_one_unticks_it(self) -> None:
        win = _window()
        win.fun_patch_vars[ID].set(True)
        win._apply_gui_dependency_selection()
        self.assertEqual(_ticked(win), {ID} | set(PIECES))
        for piece in PIECES:
            with self.subTest(unticked=piece):
                win = _window({ID} | set(PIECES))
                win.fun_patch_vars[piece].set(False)
                win._apply_gui_dependency_selection()
                self.assertEqual(_ticked(win), set(PIECES) - {piece})

    def test_the_patcher_builds_it_only_with_its_pieces(self) -> None:
        with self.assertRaises(patcher.PatcherError):
            patcher.resolve_fun_patch_ids([ID], game_id="vv5")
        resolved = patcher.resolve_fun_patch_ids(list(PIECES) + [ID], game_id="vv5")
        self.assertLess(max(resolved.index(p) for p in PIECES), resolved.index(ID))

    def test_defaults_off_owners_defaults_and_select_all_on(self) -> None:
        self.assertFalse(gui.default_fun_patch_selection(ID))
        self.assertTrue(gui.owners_default_fun_patch_selection(ID))
        self.assertTrue(gui.select_all_fun_patch_selection(ID))
        self.assertEqual(gui.row_description(self.public[ID]).count(gui.MANUALLY_ON), 1)
        # Its pieces are ticked by both bulk buttons, so the row never unticks itself there.
        for piece in PIECES:
            self.assertTrue(gui.owners_default_fun_patch_selection(piece), piece)
            self.assertTrue(gui.select_all_fun_patch_selection(piece), piece)

    def test_its_title_is_green_not_classic_red(self) -> None:
        style, colour = gui.TITLE_COLOURS[ID]
        self.assertEqual(colour, gui.LEGACY_OF_ISOLA_TITLE_COLOUR)
        self.assertNotEqual(colour, gui.CLASSIC_DIFFICULTY_TITLE_COLOUR)
        red, green, blue = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
        self.assertGreater(green, max(red, blue))
        self.assertNotEqual(style, gui.TITLE_COLOURS["vv5_classic_vv_difficulty"][0])
        for patch_id in gui.CLASSIC_DIFFICULTY_FUN_PATCH_IDS:
            self.assertEqual(gui.TITLE_COLOURS[patch_id][1], gui.CLASSIC_DIFFICULTY_TITLE_COLOUR)
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("title_style, colour = TITLE_COLOURS[patch.id]", source)
        self.assertIn("button.configure(style=title_style)", source)

    def test_it_is_not_part_of_classic_vv_difficulty(self) -> None:
        classic = self.public["vv5_classic_vv_difficulty"].raw["dependencies"]
        self.assertNotIn(ID, classic)
        self.assertFalse(set(PIECES) & set(classic))
        self.assertFalse(set(self.public[ID].raw["dependencies"]) & set(classic))
        self.assertNotIn(ID, gui.CLASSIC_DIFFICULTY_FUN_PATCH_IDS)

    def test_its_guide_names_the_five(self) -> None:
        guide = how.guide(how.patch_key(ID), "Respecting the Legacy of Isola").lines
        text = " ".join(guide)
        for name in PIECES.values():
            self.assertIn(name, text)
        self.assertIn("Owner's Defaults and Select All tick it", text)
        self.assertIn("green", text)


if __name__ == "__main__":
    unittest.main()
