"""The patcher window's multiplier sliders (the owner, 2026-11-15): 2-100x Tech Cost, Hungrier Villagers, 2-100x
Sickness, Louder Wind Flutes and More Frequent Island Events all go from 2 to 100, keep their defaults (3, 2, 2,
5 and 2) and Owner's Defaults values (2, 2, 2, Louder Wind Flutes' own 5 and 2), and each has a box beside it to
type the number in: kept in sync with the slider both ways, out-of-range numbers kept within 2 to 100, anything else put back to the slider's number, and
copy / cut / paste working in it.  Nothing out of range is ever saved."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

SLIDERS = (  # (variable, scale, box, range, default, help key)
    ("tech_cost_var", "tech_cost_scale", "tech_cost_box", "TECH_COST_MULTIPLIER_RANGE", 3, "tech_cost_multiplier"),
    ("meal_var", "meal_scale", "meal_box", "MEAL_MULTIPLIER_RANGE", 2, "meal_multiplier"),
    ("sickness_var", "sickness_scale", "sickness_box", "SICKNESS_MULTIPLIER_RANGE", 2, "sickness_multiplier"),
    ("louder_flutes_var", "louder_flutes_scale", "louder_flutes_box", "LOUDER_FLUTES_MULTIPLIER_RANGE", 5,
     "louder_flutes_multiplier"),
    ("island_frequency_var", "island_frequency_scale", "island_frequency_box", "ISLAND_FREQUENCY_MULTIPLIER_RANGE", 2,
     "island_frequency_multiplier"),
)


def source() -> str:
    return (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")


class Source(unittest.TestCase):
    def test_every_slider_is_2_to_100_with_a_box_and_its_default(self) -> None:
        text = source()
        for var, scale, box, multipliers, default, key in SLIDERS:
            with self.subTest(var=var):
                self.assertEqual(list(getattr(patcher, multipliers)), list(range(2, 101)))
                body = text[text.index(f"self.{scale} = tk.Scale("):]
                body = body[:body.index(")\n")]
                self.assertIn(f"variable=self.{var}", body)
                self.assertIn(f"from_={multipliers}[0], to={multipliers}[-1], resolution=1", body)
                self.assertIn(f"self.{box} = self._multiplier_box(", text)
                group = var.replace("_var", "_group")
                self.assertIn(f'self._help_button({group}, "{key}")', text)
        self.assertEqual((patcher.TECH_COST_MULTIPLIER_DEFAULT, patcher.MEAL_MULTIPLIER_DEFAULT,
                          patcher.SICKNESS_MULTIPLIER_DEFAULT, patcher.LOUDER_FLUTES_MULTIPLIER_DEFAULT), (3, 2, 2, 5))
        self.assertIn("self.louder_flutes_var = tk.IntVar(value=LOUDER_FLUTES_MULTIPLIER_DEFAULT)", text)
        self.assertEqual(patcher.ISLAND_FREQUENCY_MULTIPLIER_DEFAULT, 2)
        self.assertIn("self.island_frequency_var = tk.IntVar(value=ISLAND_FREQUENCY_MULTIPLIER_DEFAULT)", text)
        for label in ("2-100x Tech Cost:", "Hungrier Villagers:", "2-100x Sickness:", "Louder Wind Flutes:",
                      "More Frequent Island Events:"):
            self.assertIn(f'text="{label}"', text)

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

    def test_the_frequency_slider_is_saved_restored_and_followed(self) -> None:
        text = source()
        self.assertIn('"island_frequency_multiplier": (App._island_frequency_multiplier(self)', text)
        self.assertIn("            self.island_frequency_var.set(saved_island_frequency_multiplier(data))", text)
        self.assertIn('self.island_frequency_var.trace_add("write", lambda *_args: self._island_frequency_changed())',
                      text)
        self.assertIn("        self._island_frequency_changed()    # the saved number", text)
        for saved, restored in ((2, 2), (10, 10), (100, 100), (1, 2), (101, 2), ("50", 2), (True, 2), (None, 2)):
            with self.subTest(saved=saved):
                self.assertEqual(gui.saved_island_frequency_multiplier({"island_frequency_multiplier": saved}),
                                 restored)
        self.assertEqual(gui.saved_island_frequency_multiplier({}), 2)

    def test_the_flute_slider_is_saved_restored_and_followed(self) -> None:
        text = source()
        self.assertIn('"louder_flutes_multiplier": (App._louder_flutes_multiplier(self) if hasattr(self, '
                      '"louder_flutes_var")', text)
        self.assertIn("            self.louder_flutes_var.set(saved_louder_flutes_multiplier(data))", text)
        self.assertIn('self.louder_flutes_var.trace_add("write", lambda *_args: self._louder_flutes_changed())',
                      text)
        for saved, restored in ((2, 2), (5, 5), (10, 10), (100, 100), (1, 5), (101, 5), ("50", 5), (5.0, 5),
                                (True, 5), (None, 5)):
            with self.subTest(saved=saved):
                self.assertEqual(gui.saved_louder_flutes_multiplier({"louder_flutes_multiplier": saved}), restored)
        self.assertEqual(gui.saved_louder_flutes_multiplier({}), 5)
        self.assertEqual(gui.saved_louder_flutes_multiplier(None), 5)

    def test_the_other_sliders_restore_up_to_100(self) -> None:
        for read, key, default in ((gui.saved_tech_cost_multiplier, "tech_cost_multiplier", 3),
                                   (gui.saved_meal_multiplier, "meal_multiplier", 2),
                                   (gui.saved_sickness_multiplier, "sickness_multiplier", 2)):
            for saved, restored in ((2, 2), (10, 10), (100, 100), (101, default), (1, default)):
                with self.subTest(key=key, saved=saved):
                    self.assertEqual(read({key: saved}), restored)


class Typed(unittest.TestCase):
    def test_typed_numbers_are_kept_within_2_to_100(self) -> None:
        r = range(2, 101)
        for text, value in (("2", 2), ("10", 10), ("100", 100), (" 42 ", 42), ("7x", 7), ("7 X", 7), ("0", 2),
                            ("1", 2), ("-5", 2), ("+9", 9), ("101", 100), ("100000000000000000000", 100),
                            ("abc", None), ("", None), ("  ", None), ("4.5", None), ("1e3", None), ("٣", None),
                            ("x", None), ("--3", None)):
            with self.subTest(text=text):
                self.assertEqual(gui.typed_multiplier(text, r), value)


class Tk(unittest.TestCase):
    """The box itself, in a real Tk window (App._multiplier_box on a stand-in that counts saves)."""

    def setUp(self) -> None:
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:  # pragma: no cover - no display
            raise unittest.SkipTest(f"no Tk display ({exc})")
        self.addCleanup(self.root.destroy)
        self.tk = tk
        self.saves = 0
        outer = self

        class Stand:
            def _save_settings(self) -> None:
                outer.saves += 1

        self.var = tk.IntVar(value=5)
        group = tk.Frame(self.root)
        group.pack()
        self.scale = tk.Scale(group, variable=self.var, orient="horizontal", from_=2, to=100, resolution=1)
        self.scale.pack()
        self.box = gui.App._multiplier_box(Stand(), group, self.var, range(2, 101))
        self.root.update()

    def typed(self, text: str) -> None:
        self.box.delete(0, "end")
        self.box.insert(0, text)
        self.box.commit()

    def test_typing_moves_the_slider(self) -> None:
        for text, value in (("50", 50), ("100", 100), ("2", 2), ("10", 10)):
            with self.subTest(text=text):
                self.typed(text)
                self.assertEqual(self.var.get(), value)
                self.assertEqual(self.scale.get(), value)
                self.assertEqual(self.box.get(), str(value))

    def test_out_of_range_is_kept_within_2_to_100_and_nothing_bad_is_kept(self) -> None:
        for text, value in (("500", 100), ("0", 2), ("1", 2), ("-40", 2)):
            with self.subTest(text=text):
                self.typed(text)
                self.assertEqual(self.var.get(), value)
                self.assertEqual(self.box.get(), str(value))
        self.typed("33")
        for text in ("abc", "", "4.5"):
            with self.subTest(text=text):
                self.typed(text)
                self.assertEqual(self.var.get(), 33)
                self.assertEqual(self.box.get(), "33")

    def test_enter_and_leaving_the_box_commit(self) -> None:
        self.box.delete(0, "end")
        self.box.insert(0, "77")
        # A key goes to the widget that has the focus (another window may hold it while the suite runs).
        self.box.focus_force()
        self.root.update()
        self.box.event_generate("<Return>", when="now")
        self.assertEqual(self.var.get(), 77)
        self.box.delete(0, "end")
        self.box.insert(0, "12")
        self.box.event_generate("<FocusOut>")
        self.assertEqual(self.var.get(), 12)

    def test_the_slider_and_other_settings_move_the_box(self) -> None:
        for value in (2, 64, 100):
            self.scale.set(value)
            self.root.update()
            self.assertEqual(self.box.get(), str(value))
        self.var.set(9)                     # settings loaded, Owner's Defaults
        self.assertEqual(self.box.get(), "9")

    def test_copy_cut_and_paste(self) -> None:
        self.typed("42")
        self.box.focus_force()
        self.box.select_range(0, "end")
        self.box.event_generate("<<Copy>>")
        self.assertEqual(self.root.clipboard_get(), "42")
        self.root.clipboard_clear()
        self.root.clipboard_append("88")
        self.box.select_range(0, "end")
        self.box.icursor("end")
        self.box.event_generate("<<Paste>>")
        self.assertEqual(self.box.get(), "88")
        self.box.commit()
        self.assertEqual(self.var.get(), 88)
        self.root.clipboard_clear()
        self.root.clipboard_append("250")
        self.box.delete(0, "end")
        self.box.event_generate("<<Paste>>")
        self.box.commit()
        self.assertEqual(self.var.get(), 100)       # a pasted number out of range is kept within it too
        self.box.select_range(0, "end")
        self.box.event_generate("<<Cut>>")
        self.assertEqual(self.root.clipboard_get(), "100")
        self.assertEqual(self.box.get(), "")
        self.box.commit()
        self.assertEqual(self.box.get(), "100")     # an empty box shows the slider's number again

    def test_saves_only_when_the_number_changes(self) -> None:
        self.typed("40")
        self.assertEqual(self.saves, 1)
        self.typed("40")
        self.typed("nonsense")
        self.assertEqual(self.saves, 1)


if __name__ == "__main__":
    unittest.main()
