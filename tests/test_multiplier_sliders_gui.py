"""The patcher window's multiplier sliders (the owner, 2026-11-15; 2026-11-17: every slider goes LESS as well as
more): 0.1-10x Tech Cost, Hungrier Villagers, 0.1-10x Sickness, Louder Wind Flutes and More Frequent Island Events
all go from 0.1 to 10 in tenths (1 the normal game) on a logarithmic track, keep their defaults (3, 2, 2, 5 and 2)
and Owner's Defaults values (2, 2, 2, Louder Wind Flutes' own 5 and 2), and each has a box beside it to type the
number in: kept in sync with the slider both ways, numbers rounded to a tenth and kept within 0.1 to 10 (the owner, 2026-11-17: every slider capped at 10), anything
else put back to the slider's number, and copy / cut / paste working in it.  Saved numbers outside the range are
kept to its nearest end; nothing out of range is ever saved."""
from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

SLIDERS = (  # (variable, scale, box, range, default, help key, label)
    ("tech_cost_var", "tech_cost_scale", "tech_cost_box", "TECH_COST_MULTIPLIER_RANGE", 3, "tech_cost_multiplier",
     "0.1-10x Tech Cost:"),
    ("meal_var", "meal_scale", "meal_box", "MEAL_MULTIPLIER_RANGE", 2, "meal_multiplier", "Hungrier Villagers:"),
    ("sickness_var", "sickness_scale", "sickness_box", "SICKNESS_MULTIPLIER_RANGE", 2, "sickness_multiplier",
     "0.1-10x Sickness:"),
    ("louder_flutes_var", "louder_flutes_scale", "louder_flutes_box", "LOUDER_FLUTES_MULTIPLIER_RANGE", 5,
     "louder_flutes_multiplier", "Louder Wind Flutes:"),
    ("island_frequency_var", "island_frequency_scale", "island_frequency_box", "ISLAND_FREQUENCY_MULTIPLIER_RANGE", 2,
     "island_frequency_multiplier", "More Frequent Island Events:"),
)


def source() -> str:
    return (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")


class Ranges(unittest.TestCase):
    def test_every_range_is_a_tenth_to_10(self) -> None:
        for *_, multipliers, _default, _key, _label in ((s[0], s[3], s[4], s[5], s[6]) for s in SLIDERS):
            r = getattr(patcher, multipliers)
            with self.subTest(range=multipliers):
                self.assertEqual((r[0], r[-1], len(r)), (0.1, 10, 100))
                self.assertEqual(list(r)[:3], [0.1, 0.2, 0.3])
                self.assertEqual(list(r)[9], 1)
                for inside in (0.1, 0.5, 1, 1.5, 2, 9.9, 10, 2.0):
                    self.assertIn(inside, r)
                for outside in (0, 0.05, 0.25, 10.1, 11, 100, -1, True, "2", None, float("nan"), float("inf")):
                    self.assertNotIn(outside, r)

    def test_numbers_are_ints_when_whole(self) -> None:
        self.assertEqual(patcher.multiplier_number(20), 2)
        self.assertIsInstance(patcher.multiplier_number(20), int)
        self.assertEqual(patcher.multiplier_number(5), 0.5)
        self.assertEqual([patcher.multiplier_text(v) for v in (2, 2.0, 0.5, 12.3, 100, 0.1)],
                         ["2", "2", "0.5", "12.3", "100", "0.1"])
        with self.assertRaises(ValueError):
            patcher.multiplier_text(0.25)

    def test_the_command_line_takes_tenths(self) -> None:
        parse = patcher.multiplier_argument(patcher.TECH_COST_MULTIPLIER_RANGE)
        self.assertEqual(parse("0.5"), 0.5)
        self.assertEqual(parse("3"), 3)
        for bad in ("0", "101", "abc", "0.05", ""):
            with self.subTest(bad=bad), self.assertRaises(argparse.ArgumentTypeError):
                parse(bad)

    def test_validation_names_the_slider_and_refuses_out_of_range(self) -> None:
        self.assertEqual(patcher.validate_tech_cost_multiplier(0.5), 0.5)
        self.assertEqual(patcher.validate_tech_cost_multiplier(2.0), 2)
        for bad in (0, 0.05, 101, True, "2"):
            with self.subTest(bad=bad), self.assertRaises(patcher.PatcherError):
                patcher.validate_tech_cost_multiplier(bad)


class Source(unittest.TestCase):
    def test_every_slider_has_a_track_a_box_a_help_and_its_default(self) -> None:
        text = source()
        # Every slider is on the Difficulty Sliders page (the owner, 2026-11-18), by its variable, range and "?".
        table = {spec[2]: spec for spec in gui.DIFFICULTY_SLIDERS}
        for var, scale, box, multipliers, default, key, label in SLIDERS:
            with self.subTest(var=var):
                self.assertIn(f"self.{var} = tk.DoubleVar(value=", text)
                self.assertEqual(table[key][:2], (var, getattr(patcher, multipliers)))
        for slider in patcher.RUNTIME_SLIDERS:
            self.assertEqual(table[f"{slider.key}_multiplier"][1:], (patcher.RUNTIME_SLIDER_RANGE,
                                                                    f"{slider.key}_multiplier", slider.row_suffix))
        self.assertNotIn("self._multiplier_slider(\n            fun_settings", text)
        self.assertEqual((patcher.TECH_COST_MULTIPLIER_DEFAULT, patcher.MEAL_MULTIPLIER_DEFAULT,
                          patcher.SICKNESS_MULTIPLIER_DEFAULT, patcher.LOUDER_FLUTES_MULTIPLIER_DEFAULT,
                          patcher.ISLAND_FREQUENCY_MULTIPLIER_DEFAULT), (3, 2, 2, 5, 2))

    def test_owners_defaults_keeps_its_values(self) -> None:
        text = source()
        body = text[text.index("def _owners_default_fun_patches("):]
        body = body[:body.index("\n    def ")]
        self.assertIn('for name in ("tech_cost_var", "meal_var", "sickness_var"):', body)
        self.assertEqual(gui.OWNERS_DEFAULT_SLIDER, 2)
        self.assertIn("self.louder_flutes_var.set(LOUDER_FLUTES_MULTIPLIER_DEFAULT)", body)
        self.assertTrue(gui.owners_default_fun_patch_selection("vv4_louder_wind_flutes"))
        self.assertIn("self.island_frequency_var.set(ISLAND_FREQUENCY_MULTIPLIER_DEFAULT)", body)
        for game in range(1, 6):
            self.assertTrue(gui.owners_default_fun_patch_selection(f"vv{game}_more_frequent_island_events"))
            self.assertFalse(gui.default_fun_patch_selection(f"vv{game}_more_frequent_island_events"))
            self.assertFalse(gui.select_all_fun_patch_selection(f"vv{game}_more_frequent_island_events"))

    def test_the_frequency_and_flute_sliders_are_saved_restored_and_followed(self) -> None:
        text = source()
        self.assertIn('"island_frequency_multiplier": (App._island_frequency_multiplier(self)', text)
        self.assertIn("            self.island_frequency_var.set(saved_island_frequency_multiplier(data))", text)
        self.assertIn('self.island_frequency_var.trace_add("write", lambda *_args: self._island_frequency_changed())',
                      text)
        self.assertIn("        self._island_frequency_changed()    # the saved number", text)
        self.assertIn('"louder_flutes_multiplier": (App._louder_flutes_multiplier(self) if hasattr(self, '
                      '"louder_flutes_var")', text)
        self.assertIn("            self.louder_flutes_var.set(saved_louder_flutes_multiplier(data))", text)
        self.assertIn('self.louder_flutes_var.trace_add("write", lambda *_args: self._louder_flutes_changed())',
                      text)


class Saved(unittest.TestCase):
    """Saved settings keep their values; old numbers outside the range go to its nearest end; anything that is not a
    number is the default."""

    CASES = ((2, 2), (10, 10), (100, 10), (0.5, 0.5), (0.1, 0.1), (1, 1), (2.0, 2), (1.25, 1.2), (1.26, 1.3),
             (0, 0.1), (-5, 0.1), (0.01, 0.1), (10.1, 10), (11, 10), (101, 10), (500, 10), (float("inf"), 10))

    def test_every_slider_restores_and_clamps(self) -> None:
        for read, key, default in ((gui.saved_tech_cost_multiplier, "tech_cost_multiplier", 3),
                                   (gui.saved_meal_multiplier, "meal_multiplier", 2),
                                   (gui.saved_sickness_multiplier, "sickness_multiplier", 2),
                                   (gui.saved_louder_flutes_multiplier, "louder_flutes_multiplier", 5),
                                   (gui.saved_island_frequency_multiplier, "island_frequency_multiplier", 2)):
            for saved, restored in self.CASES + (("50", default), (True, default), (None, default),
                                                 (float("nan"), default)):
                with self.subTest(key=key, saved=saved):
                    value = read({key: saved})
                    self.assertEqual(value, restored)
                    self.assertIn(value, patcher.TECH_COST_MULTIPLIER_RANGE)
            self.assertEqual(read({}), default)
            self.assertEqual(read(None), default)

    def test_a_whole_saved_number_stays_an_int(self) -> None:
        self.assertIsInstance(gui.saved_tech_cost_multiplier({"tech_cost_multiplier": 2.0}), int)


class Typed(unittest.TestCase):
    def test_typed_numbers_are_rounded_and_kept_within_range(self) -> None:
        r = patcher.TECH_COST_MULTIPLIER_RANGE
        for text, value in (("2", 2), ("10", 10), ("100", 10), (" 42 ", 10), ("7x", 7), ("7 X", 7), ("0", 1),
                            ("1", 1), ("-5", 0.2), ("+9", 9), ("101", 10), ("100000000000000000000", 10),
                            ("0.5", 0.5), (".5", 0.5), ("0,5", 0.5), ("4.5", 4.5), ("1.25", 1.2), ("1.26", 1.3),
                            ("0.04", 1), ("2.", 2), ("-2", 0.5), ("-10", 0.1), ("-3.3", 0.3), ("-1", 1),
                            ("-0.5", 1), ("-40", 0.1), ("-1000", 0.1),
                            ("abc", None), ("", None), ("  ", None), ("1e3", None), ("٣", None), ("x", None),
                            ("--3", None), (".", None), ("1.2.3", None)):
            with self.subTest(text=text):
                self.assertEqual(gui.typed_multiplier(text, r), value)


class Labels(unittest.TestCase):
    """The owner (2026-11-17): "-10 to 10" is just the label -- 10 is x 10, -10 a tenth, the middle the normal game;
    the number kept and saved is the multiplier, so old settings keep their effect."""

    def test_the_labels(self) -> None:
        self.assertEqual([gui.multiplier_label(v) for v in (0.1, 0.2, 0.3, 0.5, 0.8, 1, 2, 2.5, 10)],
                         ["-10", "-5", "-3.3", "-2", "-1.2", "1", "2", "2.5", "10"])

    def test_every_number_reads_back_as_itself(self) -> None:
        for r in (patcher.TECH_COST_MULTIPLIER_RANGE, patcher.RUNTIME_SLIDER_RANGE):
            for value in r:
                with self.subTest(value=value):
                    self.assertEqual(gui.typed_multiplier(gui.multiplier_label(value), r), value)

    def test_the_ends_and_the_middle(self) -> None:
        r = patcher.RUNTIME_SLIDER_RANGE
        self.assertEqual((gui.typed_multiplier("10", r), gui.typed_multiplier("-10", r)), (10, 0.1))
        self.assertEqual(gui.slider_value(gui.SLIDER_STEPS // 2, r), 1)      # the middle of a -10 to 10 slider
        self.assertEqual((gui.multiplier_label(r[0]), gui.multiplier_label(r[-1])), ("-10", "10"))
        self.assertEqual(gui.multiplier_label(patcher.TECH_COST_MULTIPLIER_RANGE[-1]), "10")
        for typed in ("0", "-1", "-0.5", "1"):
            self.assertEqual(gui.typed_multiplier(typed, r), 1)

    def test_saved_numbers_keep_their_effect(self) -> None:
        for saved in (0.1, 0.5, 2, 10):
            self.assertEqual(gui.saved_runtime_slider_multiplier({"food_gain_multiplier": saved}, "food_gain"), saved)
            self.assertEqual(gui.saved_tech_cost_multiplier({"tech_cost_multiplier": saved}), saved)


class Track(unittest.TestCase):
    """The logarithmic track: 1 a third of the way along, both ends reachable, every position a number in range."""

    def test_positions(self) -> None:
        r = patcher.TECH_COST_MULTIPLIER_RANGE
        self.assertEqual(gui.slider_position(0.1, r), 0)
        self.assertEqual(gui.slider_position(10, r), gui.SLIDER_STEPS)
        self.assertEqual(gui.slider_position(1, r), 500)
        self.assertEqual(gui.slider_value(0, r), 0.1)
        self.assertEqual(gui.slider_value(gui.SLIDER_STEPS, r), 10)
        self.assertEqual(gui.slider_value(500, r), 1)
        for position in range(0, gui.SLIDER_STEPS + 1):
            self.assertIn(gui.slider_value(position, r), r)
        for value in (0.1, 0.5, 1, 2, 3, 5, 7.5, 10):
            with self.subTest(value=value):
                self.assertEqual(gui.slider_value(gui.slider_position(value, r), r), value)


class Tk(unittest.TestCase):
    """The slider and its box, in a real Tk window (App._multiplier_slider on a stand-in that counts saves)."""

    def setUp(self) -> None:
        import tkinter as tk
        from tkinter import ttk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - no display
            raise unittest.SkipTest(f"no Tk display ({exc})")
        self.addCleanup(self.root.destroy)
        self.tk = tk
        self.saves = 0
        outer = self

        class Stand:
            _multiplier_box = gui.App._multiplier_box

            def _save_settings(self) -> None:
                outer.saves += 1

            def _help_button(self, parent, _key):
                return ttk.Label(parent, text="?")

        self.var = tk.DoubleVar(value=5)
        group = tk.Frame(self.root)
        group.pack()
        self.scale, self.box = gui.App._multiplier_slider(
            Stand(), group, "Test:", self.var, patcher.TECH_COST_MULTIPLIER_RANGE, "tech_cost_multiplier")
        self.root.update()

    def value(self):
        return gui.App._slider_number(self.var, patcher.TECH_COST_MULTIPLIER_RANGE, None)

    def typed(self, text: str) -> None:
        self.box.delete(0, "end")
        self.box.insert(0, text)
        self.box.commit()

    def test_typing_moves_the_slider(self) -> None:
        r = patcher.TECH_COST_MULTIPLIER_RANGE
        for text, value in (("5", 5), ("9.5", 9.5), ("2", 2), ("10", 10), ("0.5", 0.5), ("0.1", 0.1), ("1", 1)):
            with self.subTest(text=text):
                self.typed(text)
                self.assertEqual(self.value(), value)
                self.assertEqual(self.scale.get(), gui.slider_position(value, r))
                self.assertEqual(self.box.get(), gui.multiplier_label(value))

    def test_out_of_range_is_kept_within_range_and_nothing_bad_is_kept(self) -> None:
        for text, value in (("500", 10), ("100", 10), ("0", 1), ("-40", 0.1), ("0.04", 1), ("-2", 0.5)):
            with self.subTest(text=text):
                self.typed(text)
                self.assertEqual(self.value(), value)
                self.assertEqual(self.box.get(), gui.multiplier_label(value))
        self.typed("3.3")
        for text in ("abc", "", "1e3"):
            with self.subTest(text=text):
                self.typed(text)
                self.assertEqual(self.value(), 3.3)
                self.assertEqual(self.box.get(), "3.3")

    def test_enter_and_leaving_the_box_commit(self) -> None:
        self.box.focus_force()             # a key goes to the widget with the focus
        self.root.update()
        self.box.delete(0, "end")
        self.box.insert(0, "7.7")
        self.box.event_generate("<Return>")
        self.assertEqual(self.value(), 7.7)
        self.box.delete(0, "end")
        self.box.insert(0, "0.3")
        self.box.event_generate("<FocusOut>")
        self.assertEqual(self.value(), 0.3)

    def test_the_slider_and_other_settings_move_the_box(self) -> None:
        r = patcher.TECH_COST_MULTIPLIER_RANGE
        for position in (0, 500, gui.SLIDER_STEPS):
            self.scale.set(position)
            self.root.update()
            self.assertEqual(self.box.get(), gui.multiplier_label(gui.slider_value(position, r)))
        self.var.set(9)                     # settings loaded, Owner's Defaults
        self.root.update()
        self.assertEqual(self.box.get(), "9")
        self.assertEqual(self.scale.get(), gui.slider_position(9, r))

    def test_copy_cut_and_paste(self) -> None:
        self.typed("4.2")
        self.box.focus_force()
        self.box.select_range(0, "end")
        self.box.event_generate("<<Copy>>")
        self.assertEqual(self.root.clipboard_get(), "4.2")
        self.root.clipboard_clear()
        self.root.clipboard_append("0.7")
        self.box.select_range(0, "end")
        self.box.icursor("end")
        self.box.event_generate("<<Paste>>")
        self.assertEqual(self.box.get(), "0.7")
        self.box.commit()
        self.assertEqual(self.value(), 0.7)
        self.root.clipboard_clear()
        self.root.clipboard_append("250")
        self.box.delete(0, "end")
        self.box.event_generate("<<Paste>>")
        self.box.commit()
        self.assertEqual(self.value(), 10)        # a pasted number out of range is kept within it too
        self.box.select_range(0, "end")
        self.box.event_generate("<<Cut>>")
        self.assertEqual(self.root.clipboard_get(), "10")
        self.assertEqual(self.box.get(), "")
        self.box.commit()
        self.assertEqual(self.box.get(), "10")      # an empty box shows the slider's number again

    def test_saves_only_when_the_number_changes(self) -> None:
        self.typed("4")
        self.assertEqual(self.saves, 1)
        self.typed("4")
        self.typed("4.0")
        self.typed("nonsense")
        self.assertEqual(self.saves, 1)


class Translated(unittest.TestCase):
    """The Difficulty Sliders page's own text is shown in the player's language (vv_translations.display_text), each
    line a template row vvfp.gui/difficulty_sliders.* (scripts/build_patch_text_inventory.py)."""

    def test_the_page_text_goes_through_the_translations(self) -> None:
        import json
        from unittest import mock
        import vv_how_to_use
        import vv_translations
        lines = (gui.DIFFICULTY_SLIDERS_TITLE, gui.DIFFICULTY_SLIDERS_BUTTON, gui.DIFFICULTY_SLIDERS_INTRO,
                 gui.DIFFICULTY_SLIDER_OFF_NOTE, *vv_how_to_use.guide("difficulty_sliders").lines)
        with mock.patch.object(vv_translations, "display_text", lambda game, english, translation=None: "T:" + english):
            for english in lines:
                self.assertEqual(gui.gui_text(english), "T:" + english)
        with mock.patch.object(vv_translations, "display_text", lambda game, english, translation=None: english):
            self.assertEqual(gui.gui_text(gui.DIFFICULTY_SLIDERS_TITLE), gui.DIFFICULTY_SLIDERS_TITLE)
        rows = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text("utf-8"))["strings"]
        template = {r["english"] for r in rows if r["stem"].startswith("vvfp.gui/difficulty_sliders.")}
        self.assertEqual(template, set(lines))
        text = source()
        for shown in ("text=gui_text(DIFFICULTY_SLIDERS_BUTTON)", "gui_text(DIFFICULTY_SLIDERS_TITLE)",
                      "gui_text(DIFFICULTY_SLIDERS_INTRO)", "gui_text(DIFFICULTY_SLIDER_OFF_NOTE,",
                      "text=gui_text(line)", "text=gui_text(guide.title)"):
            self.assertIn(shown, text)


if __name__ == "__main__":
    unittest.main()
