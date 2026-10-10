"""Random last names in Repair Saves & Logs' "Give villagers last names" (the owner, 2026-10-10: "for the
repair logs, can you add an option for 'random' last names everywhere"), and the red bold the last-names
window shows for every villager whose last name the current choice will change.

src/vv_last_names.py random_last_names chooses the names (pure); the window shows them (Random last
names... in src/vv_fun_patcher_gui.py) and the existing give_last_names writes them, so the save, every
log and the rules change together, with a backup first and refused while the game runs.
"""
from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_last_names_rename import NoGame, Running  # noqa: E402
from test_missing_last_names import NOW, Village  # noqa: E402

GUI_SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")


def clan(game: int):
    """A small family in `game`: Ago and Bela (founders, no last name), their children Cy and Di, Di's child
    Eb; Fay arrived (no parents); Zed has head 0, body 0 and age 0 and a last name already."""
    names = tools.load_checker().LAST_NAMES[game]
    people = [
        ln.Living(0, "Ago", "Male", 0, 0, 1, names[0], age=0),
        ln.Living(1, "Bela", "Female", 1, 1, 1, names[1]),
        ln.Living(2, "Cy", "Male", 2, 2, 1, names[0]),
        ln.Living(3, "Di", "Female", 3, 3, 1, names[0]),
        ln.Living(4, "Eb", "Male", 4, 4, 1, names[0]),
        ln.Living(5, "Fay", "Female", 5, 5, 1, "", arrived=True),
        ln.Living(6, f"Zed {names[2]}", "Male", 0, 0, 1, names[2], age=0),
    ]
    by = {v.name: v.identity for v in people}
    parents = {by["Cy"]: (by["Ago"], by["Bela"]), by["Di"]: (by["Ago"], by["Bela"]),
               by["Eb"]: (None, by["Di"])}
    return people, parents, by


class Choosing(unittest.TestCase):
    def test_only_the_villagers_without_a_last_name_in_every_game(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                people, parents, by = clan(game)
                names, unfit = ln.random_last_names(game, people, parents, 7)
                self.assertEqual(unfit, [])
                self.assertEqual(set(names), {by[n] for n in ("Ago", "Bela", "Cy", "Di", "Eb", "Fay")},
                                 "Zed has one and keeps it; head 0, body 0, age 0 are real villagers")
                for key, last in names.items():
                    self.assertIn(last, tools.load_checker().LAST_NAMES[game])
                    v = next(p for p in people if p.identity == key)
                    self.assertLessEqual(len(ln.with_last(game, v.name, last)), ln.ROOM[game])

    def test_everyone_replaces_what_they_have(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                people, parents, by = clan(game)
                names, _unfit = ln.random_last_names(game, people, parents, 7, who="everyone")
                self.assertEqual(set(names), {v.identity for v in people}, "all of them, each a different name")
                zed = next(v for v in people if v.name.startswith("Zed"))
                self.assertNotEqual(names[zed.identity], ln.split_name(game, zed.name)[1])

    def test_a_family_shares_one_name_and_each_villager_draws_their_own_otherwise(self):
        people, parents, by = clan(3)
        shared, _ = ln.random_last_names(3, people, parents, 11, who="everyone", families=True)
        self.assertEqual(shared[by["Cy"]], shared[by["Ago"]], "the father's, by the default rule")
        self.assertEqual(shared[by["Di"]], shared[by["Ago"]])
        self.assertEqual(shared[by["Eb"]], shared[by["Di"]], "a child with only a mother takes hers")
        mother, _ = ln.random_last_names(3, people, parents, 11, who="everyone", families=True, rule="mother")
        self.assertEqual(mother[by["Cy"]], mother[by["Bela"]])
        either, _ = ln.random_last_names(3, people, parents, 11, who="everyone", families=True, rule="random")
        self.assertIn(either[by["Cy"]], {either[by["Ago"]], either[by["Bela"]]})
        single, _ = ln.random_last_names(3, people, parents, 11, who="everyone", families=False)
        self.assertEqual(len(single), len(people))
        self.assertGreater(len(set(single.values())), 3, "fully random: nothing ties them together")

    def test_only_without_keeps_a_family_with_a_name_in_mind(self):
        people, parents, by = clan(3)
        ago = people[0]
        ago.name = "Ago Akikai"                  # Ago has one; his children have none
        names, _ = ln.random_last_names(3, people, parents, 5, families=True)
        self.assertNotIn(by["Ago"], names)
        self.assertEqual(names[by["Cy"]], names[by["Bela"]], "the mother's, new, since the father's is theirs")
        again, _ = ln.random_last_names(3, people, parents, 5, families=True, current={by["Ago"]: "Akikai"})
        self.assertEqual(again, names)

    def test_the_boxes_decide_who_has_none(self):
        people, parents, by = clan(3)
        names, _ = ln.random_last_names(3, people, parents, 5, current={by["Ago"]: "Wikimak"})
        self.assertNotIn(by["Ago"], names, "a name typed in the box counts")

    def test_the_same_seed_gives_the_same_names_and_another_seed_others(self):
        for families in (False, True):
            people, parents, _by = clan(2)
            a = ln.random_last_names(2, people, parents, 100, who="everyone", families=families)
            self.assertEqual(a, ln.random_last_names(2, people, parents, 100, who="everyone", families=families))
            self.assertNotEqual(a, ln.random_last_names(2, people, parents, 101, who="everyone",
                                                        families=families), "Reroll changes the names")
        seeds = {ln.random_seed() for _ in range(5)}
        self.assertGreater(len(seeds), 1)

    def test_heathens_are_left_alone_and_names_that_cannot_fit_are_reported(self):
        people, parents, by = clan(5)
        names, _ = ln.random_last_names(5, people, parents, 3, who="everyone", skip={by["Fay"]})
        self.assertNotIn(by["Fay"], names)
        people[0].name = "A" * (ln.ROOM[5] - 1)           # no last name can follow it
        names, unfit = ln.random_last_names(5, people, parents, 3)
        self.assertIn(people[0].identity, unfit)
        self.assertNotIn(people[0].identity, names)

    def test_an_unused_name_is_preferred_but_names_may_repeat(self):
        people, parents, _by = clan(1)
        names, _ = ln.random_last_names(1, people, parents, 9, who="everyone")
        self.assertEqual(len(set(names.values())), len(names), "the list has enough for all of them")
        many = [ln.Living(k, f"V{k}", "Male", k, k, 1, "") for k in range(80)]
        names, _ = ln.random_last_names(1, many, {}, 9)
        self.assertEqual(len(names), 80, "more villagers than names: they repeat, all the same")


class Written(Village):
    """Giving the random names goes through give_last_names: the save and every log together."""

    def chosen(self, **options):
        people, parents = ln.everyone(self.folder, 3, 1)
        names, unfit = ln.random_last_names(3, people, parents, 21, **options)
        self.assertEqual(unfit, [])
        return {k: v for k, v in names.items() if next(p for p in people if p.identity == k).alive}, people

    def test_the_save_and_the_logs_agree_after(self):
        chosen, people = self.chosen()
        before = {v.identity: v.name for v in people}
        result = ln.give_last_names(self.folder, 3, 1, chosen, NoGame(), NOW)
        self.assertTrue(Path(result.backup.backup_folder).is_dir(), "a backup first")
        after = {v.name for v in ln.living(self.folder, 3, 1)}
        for key, last in chosen.items():
            self.assertIn(ln.with_last(3, key[0], last), after)
        births = (self.folder / "Virtual Villagers Fun Patcher Logs" / "Births and Conceptions"
                  / "Virtual Villagers 3 Births and Conceptions Log 1.txt").read_text(encoding="latin-1")
        kalea = next(k for k in chosen if k[0] == "Kalea")
        self.assertIn(f"Name: Kalea {chosen[kalea]}", births)
        self.assertNotIn("Name: Kalea\r\n", births)
        self.assertIn("Ago Akikai", {n for n in after}, "a villager who had one is untouched")
        self.assertEqual(before[kalea], "Kalea")

    def test_everyone_and_by_family_are_written_too(self):
        chosen, _people = self.chosen(who="everyone", families=True)
        ln.give_last_names(self.folder, 3, 1, chosen, NoGame(), NOW)
        names = {v.name for v in ln.living(self.folder, 3, 1)}
        self.assertNotIn("Ago Akikai", names, "everyone's last name was replaced")
        kid = next(n for n in names if n.startswith("Kid "))
        ago = next(n for n in names if n.startswith("Ago "))
        self.assertEqual(kid.split(" ")[1], ago.split(" ")[1], "the family shares one name")

    def test_refused_while_the_game_runs_and_nothing_changes(self):
        chosen, _ = self.chosen()
        before = self.save.read_bytes()
        with self.assertRaises(Exception):
            ln.give_last_names(self.folder, 3, 1, chosen, Running(), NOW)
        self.assertEqual(self.save.read_bytes(), before)

    def test_an_earlier_record_that_gives_a_name_is_a_contradiction_to_ask_about(self):
        people, _parents = ln.everyone(self.folder, 3, 1)
        self._log("Tribe History/Village History 1.txt",
                  "=== Virtual Villagers 3 -- 2026-10-01 ===\nVillage: Tribe (Save 1)\n"
                  "Villager 1\n  Name: Kalea Bahati\n  Head: 4\n  Body: 4\n\n")
        found = ln.random_conflicts(self.folder, 3, 1, people)
        self.assertEqual({k[0]: v for k, v in found.items()}, {"Kalea": ["Bahati"]})
        self._log("Deaths/Virtual Villagers 3 Deaths Log 2.txt",
                  "Village: Tribe (Save 1)\nDeath 1\n  Name: Zero Moa\n  Age at death: 1400\n"
                  "  Head: 0\n  Body: 0\n\n")
        self.assertNotIn("Zero", {k[0] for k in ln.random_conflicts(self.folder, 3, 1, people)},
                         "a dead namesake with the same looks is someone else")

    def test_heathens_none_here(self):
        self.assertEqual(ln.heathen_identities(self.folder, 3, 1), set())


class RedBold(unittest.TestCase):
    def test_changed_rows_are_red_bold_and_the_rest_normal(self):
        now = {"a": "", "b": "Akikai", "c": "Wikimak"}
        self.assertEqual(ln.__name__, "vv_last_names")
        import vv_fun_patcher_gui as gui
        changing = gui.last_names_changing(now, {"a": "Moa", "b": "Akikai", "c": ""})
        self.assertEqual(changing, {"a", "c"}, "set back to the name they have: normal again")
        red = gui.last_name_row_style(True, False)
        self.assertTrue(red["bold"])
        self.assertEqual(red["foreground"], gui.LAST_NAME_CHANGED_COLOUR)
        self.assertEqual(gui.last_name_row_style(False, False), {"bold": False, "foreground": None, "background": None})

    def test_a_row_the_prompt_asked_about_keeps_its_background(self):
        import vv_fun_patcher_gui as gui
        asked_changed = gui.last_name_row_style(True, True)
        self.assertEqual(asked_changed["background"], gui.LAST_NAME_ASKED_BACKGROUND)
        self.assertEqual(asked_changed["foreground"], gui.LAST_NAME_CHANGED_COLOUR)
        asked_same = gui.last_name_row_style(False, True)
        self.assertEqual((asked_same["bold"], asked_same["foreground"], asked_same["background"]),
                         (False, "#000000", gui.LAST_NAME_ASKED_BACKGROUND))

    def test_the_window_restyles_on_every_change(self):
        body = GUI_SOURCE[GUI_SOURCE.index("    def _last_names_dialog("):GUI_SOURCE.index("    def _own_rules_dialog(")]
        self.assertIn("restyle()", body[body.index("def marks()"):body.index("def restyle()")])
        self.assertIn("last_names_changing(now,", body)
        self.assertIn('text="Random last names…", command=random_dialog', body)
        self.assertIn("Everyone (replaces the last names they have now)", body)
        self.assertIn("Only villagers who have no last name", body)
        self.assertIn("Fully random per villager", body)
        self.assertIn("Each family shares one random name", body)
        self.assertIn('text="Reroll"', body)
        self.assertIn("askokcancel", body)
        self.assertIn("random_conflicts", body)


def widgets(root):
    for child in root.winfo_children():
        yield child
        yield from widgets(child)


class TheWindow(Village):
    """The real last-names window, driven: Random last names..., Everyone, Reroll, Cancel, Use these, OK."""

    def setUp(self):
        super().setUp()
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display: {exc}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def label(self, window, name):
        for w in widgets(window):
            text = str(w.cget("text")) if "text" in w.keys() else ""
            if text.startswith(name + " (") and w.winfo_class() in ("Label", "TLabel"):
                return w
        raise AssertionError(f"no row for {name}")

    def bold(self, label) -> bool:
        import tkinter.font as tkfont
        return tkfont.Font(root=self.root, font=label.cget("font")).actual()["weight"] == "bold"

    def red_rows(self, window):
        out = set()
        for name in ("Ago Akikai", "Aipi", "Kid", "Kalea", "Mele Ana", "Big Bob", "Zero", "Moa Akikai"):
            lab = self.label(window, name)
            if self.bold(lab):
                self.assertEqual(str(lab.cget("foreground")), "#d62828", name)
                out.add(name)
            else:
                self.assertNotEqual(str(lab.cget("foreground")), "#d62828", name)
        return out

    def button(self, window, text):
        for w in widgets(window):
            if w.winfo_class() in ("TButton", "Button") and str(w.cget("text")) == text:
                return w
        raise AssertionError(text)

    def toplevels(self):
        return [w for w in widgets(self.root) if isinstance(w, tk.Toplevel)]

    def drive(self, steps, names=None, answer_ok=True):
        import vv_fun_patcher_gui as gui
        fake = SimpleNamespace(_repair_questions=lambda *a, **k: None)
        info = SimpleNamespace(slot=1, name="Tribe")
        names = names if names is not None else {"chosen": {}, "answers": {}}
        names_var = tk.BooleanVar(master=self.root)
        seen = {}
        queue = list(steps)

        def next_step():
            if not queue:
                return
            step = queue.pop(0)
            step(seen)
            if queue:
                self.root.after(150, next_step)

        self.root.after(300, next_step)
        asked = mock.patch.object(gui.messagebox, "askokcancel", return_value=answer_ok)
        errors = mock.patch.object(gui.messagebox, "showerror", side_effect=AssertionError)
        with asked as ask, errors:
            gui.App._last_names_dialog(fake, self.root, self.folder, 3, info, names, names_var)
        seen["asked"] = ask.call_count
        seen["names"], seen["var"] = names, names_var.get()
        return seen

    def test_nothing_is_red_to_begin_with_and_cancel_leaves_everything_normal(self):
        def second(seen):
            sub = self.toplevels()[-1]
            seen["preview"] = self.red_rows(self.toplevels()[0])
            self.button(sub, "Cancel").invoke()

        # The sub-dialog blocks, so its steps run from inside the nested loop.
        def open_random(seen):
            win = self.toplevels()[-1]
            seen["start"] = self.red_rows(win)
            self.root.after(200, lambda: second(seen))
            self.button(win, "Random last names…").invoke()
            seen["after_cancel"] = self.red_rows(win)
            self.button(win, "Cancel").invoke()

        seen = self.drive([open_random])
        self.assertEqual(seen["start"], set())
        self.assertEqual(seen["preview"], {"Aipi", "Kid", "Kalea", "Zero"}, "those with no last name, in red bold")
        self.assertEqual(seen["after_cancel"], set(), "Cancel puts every row back to normal")
        self.assertFalse(seen["var"])
        self.assertEqual(seen["names"]["chosen"], {}, "nothing is applied on cancel")

    def test_the_options_update_the_highlight_live_and_use_these_keeps_it(self):
        def open_random(seen):
            win = self.toplevels()[-1]
            self.root.after(200, lambda: in_sub(seen, win))
            self.button(win, "Random last names…").invoke()
            seen["kept"] = self.red_rows(win)
            self.button(win, "OK").invoke()

        def in_sub(seen, win):
            sub = self.toplevels()[-1]
            radios = {str(w.cget("text")): w for w in widgets(sub) if w.winfo_class() == "TRadiobutton"}
            seen["missing"] = self.red_rows(win)
            radios["Everyone (replaces the last names they have now)"].invoke()
            seen["everyone"] = self.red_rows(win)
            self.button(sub, "Reroll").invoke()
            seen["reroll"] = self.red_rows(win)
            radios["Only villagers who have no last name"].invoke()
            seen["back"] = self.red_rows(win)
            next(w for w in widgets(sub) if w.winfo_class() == "TRadiobutton"
                 and str(w.cget("text")).startswith("Each family")).invoke()
            seen["family"] = self.red_rows(win)
            self.button(sub, "Use these").invoke()

        seen = self.drive([open_random])
        none = {"Aipi", "Kid", "Kalea", "Zero"}
        self.assertEqual(seen["missing"], none)
        self.assertEqual(seen["everyone"], none | {"Ago Akikai", "Mele Ana", "Big Bob", "Moa Akikai"},
                         "everyone: all of them, replacing the names they have")
        self.assertEqual(seen["reroll"], seen["everyone"], "Reroll keeps the highlight")
        self.assertEqual(seen["back"], none, "rows the option no longer covers go back to normal")
        self.assertEqual(seen["family"], none)
        self.assertEqual(seen["kept"], none)
        self.assertEqual(seen["asked"], 0, "no confirmation: Everyone was switched back before Use these")
        chosen = seen["names"]["chosen"]
        self.assertEqual({k[0] for k in chosen}, {"Aipi", "Kid", "Kalea", "Zero"})
        self.assertTrue(seen["var"])
        self.assertTrue(all(chosen.values()))

    def box(self, window, label):
        row = label.grid_info()["row"]
        return next(w for w in widgets(window) if w.winfo_class() == "TCombobox"
                    and w.grid_info().get("row") == row and w.grid_info().get("column") == 1)

    def test_editing_a_row_back_makes_it_normal_and_the_prompts_rows_keep_their_background(self):
        def open_random(seen):
            win = self.toplevels()[-1]
            seen["asked_start"] = self.label(win, "Kalea").cget("background")
            self.root.after(200, lambda: in_sub(seen))
            self.button(win, "Random last names…").invoke()
            seen["red"] = self.red_rows(win)
            kalea = self.label(win, "Kalea")
            seen["asked_red_background"] = kalea.cget("background")
            self.box(win, kalea).set("(no last name)")
            seen["edited_back"] = self.red_rows(win)
            seen["asked_back_background"] = self.label(win, "Kalea").cget("background")
            self.box(win, self.label(win, "Ago Akikai")).set("Wikimak")
            seen["typed"] = self.red_rows(win)
            self.button(win, "OK").invoke()

        def in_sub(seen):
            self.button(self.toplevels()[-1], "Use these").invoke()

        names = {"chosen": {}, "answers": {}, "highlight": {("Kalea", 4, 4)}}
        seen = self.drive([open_random], names=names)
        self.assertEqual(seen["asked_start"], "#fff2a8")
        self.assertEqual(seen["red"], {"Aipi", "Kid", "Kalea", "Zero"})
        self.assertEqual(seen["asked_red_background"], "#fff2a8", "the 'asked about' background stays")
        self.assertEqual(seen["edited_back"], {"Aipi", "Kid", "Zero"}, "back to the name they have: normal")
        self.assertEqual(seen["asked_back_background"], "#fff2a8")
        self.assertEqual(seen["typed"], {"Aipi", "Kid", "Zero", "Ago Akikai"}, "a typed change is red bold too")
        self.assertEqual({k[0] for k in seen["names"]["chosen"]}, {"Aipi", "Kid", "Zero", "Ago Akikai"})

    def test_everyone_asks_before_it_changes_the_whole_village(self):
        def open_random(seen):
            win = self.toplevels()[-1]
            self.root.after(200, lambda: in_sub(seen, win))
            self.button(win, "Random last names…").invoke()
            seen["kept"] = self.red_rows(win)
            self.button(win, "Cancel").invoke()

        def in_sub(seen, win):
            sub = self.toplevels()[-1]
            next(w for w in widgets(sub) if w.winfo_class() == "TRadiobutton"
                 and str(w.cget("text")).startswith("Everyone")).invoke()
            self.button(sub, "Use these").invoke()
            seen["still_open"] = sub.winfo_exists()
            self.button(sub, "Cancel").invoke()

        seen = self.drive([open_random], answer_ok=False)
        self.assertEqual(seen["asked"], 1)
        self.assertTrue(seen["still_open"], "declining the warning keeps the choice open")
        self.assertEqual(seen["kept"], set(), "cancelled: every row normal again")
        self.assertEqual(seen["names"]["chosen"], {}, "Cancel in the window: nothing applied")


if __name__ == "__main__":
    unittest.main()
