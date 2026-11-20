"""Game Mechanics' Minimum Detail (the owner, 2026-11-17: "only gives vital stats and numbers, hides all the
explanations and stuff"): src/vv_game_mechanics.py minimum(), on every game's general page and the committed save
fixtures of all five games, and the window's tick box (src/vv_game_mechanics_window.py)."""
from __future__ import annotations

import json
import re
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_window as w  # noqa: E402
from test_game_mechanics_time_units import pages  # noqa: E402

VITAL = gm.GROUPS[0]


class MinimumDetail(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pages = list(pages())

    def test_every_game_is_covered(self) -> None:
        names = [name for name, _ in self.pages]
        for game in range(1, 6):
            self.assertIn(f"general {game}", names)
            self.assertIn(f"vv{game}-huttest-1", names)

    def test_explanations_are_hidden(self) -> None:
        for name, facts in self.pages:
            with self.subTest(name):
                full, short = gm.render(facts), gm.render(gm.minimum(facts))
                self.assertLess(len(short), len(full) * 0.7)
                for gone in ("How it is worked out", "Ages run on the game's clock (see Time and units)",
                             "With the patcher's", "\nTime and units\n",
                             "\nHidden keys, clicks and cheats\n", "DEAD (never runs)"):
                    self.assertNotIn(gone, "\n" + short + "\n")
                for fact in gm.minimum(facts):
                    self.assertFalse(fact.text.startswith(("How ", "Normally", "DEAD")), fact.text)
                # Sources keeps one short line (the owner, 2026-11-18): the exe and how its patches were read, or a
                # warning; the general page has no Sources at all.
                sources = [f.text for f in gm.minimum(facts) if f.group == gm.SOURCES]
                if name.startswith("general"):
                    self.assertEqual(sources, [])
                else:
                    self.assertEqual(len(sources), 1, sources)
                    self.assertTrue(sources[0].startswith(("Sources: ", "Warning: ")), sources)

    def test_each_line_is_a_short_answer_with_a_number(self) -> None:
        for name, facts in self.pages:
            with self.subTest(name):
                originals = [fact.text for fact in facts]
                for fact in gm.minimum(facts):
                    if fact.group == gm.SOURCES:          # the one Sources line is written for Minimal Detail
                        continue
                    # Every kept line is the start of a line of the full page: its first sentence, or a heading.
                    self.assertTrue(any(text.startswith(fact.text.removesuffix(":")) for text in originals), fact.text)
                    if fact.group != VITAL and fact.due is None and not fact.text.endswith(":"):
                        self.assertRegex(fact.text, r"\d", fact.text)
                    self.assertEqual(fact.text, gm.first_sentence(fact.text))

    def test_vital_statistics_and_save_values_are_kept(self) -> None:
        for name, facts in self.pages:
            with self.subTest(name):
                short = gm.minimum(facts)
                # Every vital statistic stays (its answer), number or not; only the explanations among them go.
                vital = [gm.first_sentence(f.text) for f in facts if f.group == VITAL and not gm._TIPS.search(f.text)]
                self.assertEqual([t for t in vital if not gm._EXPLAINS.search(t) and not t.endswith(":")],
                                 [f.text for f in short if f.group == VITAL and not f.text.endswith(":")])
                # Every countdown stays.
                self.assertEqual(sum(f.due is not None for f in facts), sum(f.due is not None for f in short))
                if not name.startswith("general"):
                    self.assertTrue(any(f.group == "Village counts" for f in short))
        page = dict(self.pages)["vv4-huttest-1"]
        text = gm.render(gm.minimum(page))
        for kept in ("Food in storage: 99,997,213.", "Tech points: 99,951,999.", "Population: 6 villagers.",
                     "Tech Points Earned: 2,099", "Mushrooms: brown worth 6 food, red (rare) 35, 8% of them red."):
            self.assertIn(kept, text)
        for gone in ("Research brings them;", "farmers needed = the food eaten"):
            self.assertNotIn(gone, text)

    def test_tutorial_and_random_tips_are_hidden(self) -> None:
        # The owner, 2026-11-19: "tutorial and random tips should not be shown in minimal detail on".
        for name, facts in self.pages:
            with self.subTest(name):
                short = gm.render(gm.minimum(facts))
                for word in ("tutorial", "Tutorial", "random tip", "Random tip", "tip pop-up"):
                    self.assertNotIn(word, short)
        facts = [gm.Fact("Chances", "The tutorial's first embrace skips the food refusal and the roll (1 in 1).", gm.SAVE),
                 gm.Fact("Chances", "Embraces: 1 in 3.", gm.SAVE)]
        self.assertEqual([f.text for f in gm.minimum(facts)], ["Embraces: 1 in 3."])

    def test_hours_since_last_played_is_a_vital_statistic(self) -> None:
        # The owner, 2026-11-19: "the number of hours since the save was played should be shown in vital statistics".
        for name, facts in self.pages:
            if name.startswith("general"):
                continue
            with self.subTest(name):
                span = r"[\d,]+\.\d hours = [\d,]+\.\d days( = [\d,]+\.\d years)?"
                for page in (facts, gm.minimum(facts)):
                    for label, tail in (("Time since save was last played", r"last saved [^)]+\)\.( .+ would count "
                                                                              r"if it were played now\.)?"),
                                        ("Time since save was created", r"created [^)]+\)\.")):
                        hits = [f.text for f in page if f.group == VITAL and f.text.startswith(label + ": ")]
                        self.assertEqual(len(hits), 1, (name, label))
                        self.assertRegex(hits[0], rf"^{label}: {span} \(real time; {tail}$")

    def test_hours_days_years(self) -> None:
        self.assertEqual(gm.hours_days_years(547.6 * 3600), "547.6 hours = 22.8 days")
        self.assertEqual(gm.hours_days_years(400 * 86400), "9,600.0 hours = 400.0 days = 1.1 years")
        self.assertEqual(gm.hours_days_years(-5), "0.0 hours = 0.0 days")

    def test_first_sentence(self) -> None:
        self.assertEqual(gm.first_sentence("Tech points: 1,234. Research brings them."), "Tech points: 1,234.")
        self.assertEqual(gm.first_sentence("About 0.6 villagers. More."), "About 0.6 villagers.")
        self.assertEqual(gm.first_sentence('It says "Good! Well done." Then more.'), 'It says "Good! Well done."')
        self.assertEqual(gm.first_sentence("No stop at all"), "No stop at all")

    def test_a_left_out_parent_heads_its_kept_numbers(self) -> None:
        facts = [gm.Fact("Refills", "Time to full: the bushes refill on their own.", gm.SAVE),
                 gm.Fact("Refills", "From empty: 2 hours.", gm.SAVE, sub=True),
                 gm.Fact("Refills", "Nothing here is a number.", gm.SAVE),
                 gm.Fact("Refills", "Bush: 5 of 10.", gm.SAVE, sub=True)]
        self.assertEqual([(f.text, f.sub) for f in gm.minimum(facts)],
                         [("Time to full:", False), ("From empty: 2 hours.", True), ("Bush: 5 of 10.", False)])


TK_CHILD = r"""
import sys, tkinter
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import vv_save_backup, vv_game_mechanics_window as w
vv_save_backup.documents_folder = lambda: Path(sys.argv[1])
vv_save_backup.find_save_folders = lambda title, documents: []      # every tab shows its general rules
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
root.withdraw()
class Build:
    def __init__(self, title):
        self.title = title
root.builds = [Build(t) for t in ["Virtual Villagers - A New Home", "Virtual Villagers - The Lost Children",
               "Virtual Villagers - The Secret City", "Virtual Villagers - The Tree of Life",
               "Virtual Villagers - New Believers"]]
root._game_folders_for = lambda save_folder: []
saved = []
root._save_settings = lambda: saved.append(root.game_mechanics_minimum)
window = w.open_game_mechanics(root, root.builds[3])
window.update()
page = window.mechanics_tabs[4]["page"]
before = page.get("1.0", "end")
off = window.mechanics_minimum.get()
window.mechanics_minimum_button.invoke()
window.update()
after = page.get("1.0", "end")
buttons = window.mechanics_parts[2]
print(off, saved, len(after) < len(before) * 0.7, "How it is worked out" in before, "How it is worked out" in after,
      buttons.winfo_reqwidth() <= w.MIN_WIDTH - 24)
window.mechanics_close()
root.game_mechanics_minimum = True
again = w.open_game_mechanics(root, root.builds[3])
again.update()
print(again.mechanics_minimum.get(), "How it is worked out" in again.mechanics_tabs[4]["page"].get("1.0", "end"))
root.destroy()
"""


class RealWindow(unittest.TestCase):
    def test_real_window(self) -> None:
        import subprocess
        done = subprocess.run([sys.executable, "-c", TK_CHILD, str(ROOT / "src")], capture_output=True, text=True,
                              timeout=180)
        if done.returncode == 3:
            self.skipTest(f"no display: {done.stderr.strip()}")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split("\n")[:2], ["False [True] True True False True", "True False"])

    def test_off_by_default_and_kept_in_the_settings(self) -> None:
        saved = []
        app = types.SimpleNamespace(_save_settings=lambda: saved.append(app.game_mechanics_minimum))
        w.remember_minimum(app, True)
        w.remember_minimum(app, False)
        self.assertEqual(saved, [True, False])
        source = (ROOT / "src" / "vv_game_mechanics_window.py").read_text(encoding="utf-8")
        self.assertIn("value=getattr(app, MINIMUM_KEY, False) is True", source)
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn('"game_mechanics_minimum": getattr(self, "game_mechanics_minimum", False) is True', gui)
        self.assertIn('self.game_mechanics_minimum = data.get("game_mechanics_minimum") is True', gui)

    def test_the_page_follows_the_box(self) -> None:
        full, short = w.general_text(4), w.general_text(4, minimum=True)
        self.assertIn("How it is worked out", full)
        self.assertNotIn("How it is worked out", short)
        self.assertTrue(short.startswith(gm.GENERAL_NOTE))

    def test_the_label_is_in_the_translation_template(self) -> None:
        data = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        rows = [r for r in data["strings"] if r["stem"] == "vvfp.gui/game_mechanics.minimum_detail"]
        self.assertEqual([r["english"] for r in rows], [gm.MINIMUM_DETAIL])
        self.assertTrue(re.search(r"display_text\(first, gm\.MINIMUM_DETAIL\)",
                                  (ROOT / "src" / "vv_game_mechanics_window.py").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
