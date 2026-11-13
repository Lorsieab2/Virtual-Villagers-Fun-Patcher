"""The Custom Island Event Library window (src/vv_cie_library_window.py; the owner, 2026-11-12: the branching editor
lives in the patcher).  The plain helpers are tested here directly; the window itself is built in its own interpreter
(as the other window tests do) and skips cleanly when there is no Tk display: it opens and closes, loads The Aspiring
Adventurer, a weight edited changes the chances, a link to no part shows its problem (and the problem leads to its
part), Save writes the .json and the .cieg into the library (the .cieg round-trips), and no page is tall."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_cie_graph as cg  # noqa: E402
import vv_cie_library_window as w  # noqa: E402

NO_TK = 3
WINDOWS_LIMIT = 32767
PAGE_BUDGET = 4000


class Helpers(unittest.TestCase):
    def test_the_example_and_a_new_event_pass_every_check(self) -> None:
        for g in (w.example_event(), w.new_event(), w.example_event(w.CAVE_EXAMPLE)):
            self.assertEqual(cg.validate(g)[1], [], g["title"])
        self.assertEqual(w.example_event()["title"], "The Aspiring Adventurer")

    def test_the_tree_shows_a_shared_part_once_and_links_it_after(self) -> None:
        rows = w.outline(w.example_event())
        parts = [target for _i, _p, _words, kind, target in rows if kind == "node"]
        self.assertEqual(len(parts), len(set(parts)))                     # each part once
        self.assertEqual(set(parts), set(w.example_event()["nodes"]))     # and every part
        links = [words for _i, _p, words, kind, _t in rows if kind == "link"]
        self.assertTrue(any("deadly  (shared: shown above)" in words for words in links), links)
        buttons = [words for _i, _p, words, kind, _t in rows if kind == "choice"]
        self.assertEqual(buttons, ["Button A: Go investigate!", "Button B: Stay on the safe path"])
        self.assertTrue(any(words.startswith("2 in 4: find_dirt") for _i, _p, words, _k, _t in rows))
        self.assertTrue(any(words.startswith("1 in 3: if the friend takes part: A8") for _i, _p, words, _k, _t
                            in rows))

    def test_a_loop_and_a_broken_link_never_hang_the_tree(self) -> None:
        g = w.new_event()
        g["nodes"]["two"] = w.blank_node()
        g["nodes"]["start"]["children"] = [{"next": "two", "weight": 1, "if": None, "else": None}]
        g["nodes"]["two"]["children"] = [{"next": "start", "weight": 1, "if": None, "else": None},
                                         {"next": "nowhere", "weight": 1, "if": None, "else": None}]
        self.assertFalse(w.walkable(g))
        kinds = [kind for *_rest, kind, _t in w.outline(g)]
        self.assertIn("missing", kinds)
        self.assertIn("link", kinds)
        self.assertEqual(w.fit_meter(g, "start", False), {})
        self.assertIn("once every link leads to a part", w.chances_text(g, 1))

    def test_rename_and_delete_follow_every_link(self) -> None:
        g = w.example_event()
        w.rename_node(g, "deadly", "the_beast")
        self.assertNotIn("deadly", g["nodes"])
        self.assertEqual(cg.validate(g)[1], [])
        w.delete_node(g, "find_meat")
        self.assertFalse(any(c["next"] == "find_meat" for n in g["nodes"].values() for c in n["children"]))

    def test_plain_words_for_conditions_and_changes(self) -> None:
        self.assertEqual(w.describe_cond({"role": "friend"}), "the friend takes part")
        self.assertEqual(w.describe_cond({"not": {"game": [5]}}), "not in New Believers")
        self.assertEqual(w.describe_cond({"patch": "guardians_of_isola"}), "with Guardians of Isola on")
        self.assertEqual(w.describe_effect({"do": "kill", "role": "subject", "cause": "unknown"}),
                         "The main villager dies (recorded as \"Unknown causes\")")
        self.assertEqual(w.describe_effect({"do": "kill", "role": "friend", "cause": "Eaten by a shark"}),
                         "The friend dies (recorded as \"Eaten by a shark\")")
        self.assertIn("kept as the award", w.describe_effect({"do": "food", "amount": 500, "scaled": True,
                                                              "defer": True}))
        self.assertEqual(w.plain_problem("node a_open: 'x' names no node"), "part a_open: 'x' names no node")
        nodes = w.example_event()["nodes"]
        self.assertEqual(w.problem_node("node a_open: 'zzz' names no node", nodes), "a_open")
        self.assertEqual(w.problem_node("The Secret City: the popup of b_open+b_lost takes 11 pages", nodes),
                         "b_open")
        # The window's own words never show a code label.
        shown = " ".join([w.INTRO, w.HELP_TEXT, w.SCROLLING, *w.EFFECT_NAMES.values(), *w.RISKY.values(),
                          *w.TYPE_WORDS.values(), *w.POPUP_WORDS.values(), *w.KIND_WORDS.values()])
        for word in ("node", "json", "cieg", "graph", "defer", "pay_award", "branch", "optional"):
            self.assertNotIn(word, shown.lower())

    def test_only_the_changes_every_target_game_can_make(self) -> None:
        self.assertNotIn("status", w.effect_kinds([1, 2, 3, 4, 5]))
        self.assertIn("status", w.effect_kinds([5]))
        self.assertIn("kill", w.effect_kinds([1, 2, 3, 4, 5]))
        self.assertEqual(w.effect_kinds([]), [])
        for kind in w.effect_kinds([1, 2, 3, 4, 5]):
            e = w.new_effect(kind, [1, 2, 3, 4, 5])
            g = w.new_event()
            g["nodes"]["start"]["effects"] = [e] if kind != "pay_award" else [
                {"do": "food", "amount": 5, "scaled": False, "defer": True}, e]
            self.assertEqual(cg.validate(g)[1], [], kind)
        # The risky ones are marked.
        self.assertEqual(set(w.RISKY), {"kill", "vanish", "sick", "status"})
        self.assertEqual(w.CAUSE_WORDS, {"custom": "Died in a custom island event", "unknown": "Unknown causes"})

    def test_the_fit_meter_counts_pages_or_only_the_text_limit(self) -> None:
        g = w.example_event()
        pages = w.fit_meter(g, "intro", False)
        self.assertEqual(sorted(pages), [1, 2, 3, 4, 5])
        for fit in pages.values():
            self.assertEqual((fit.unit, fit.limit, fit.over), ("pages", cg.MAX_PAGES, False))
            self.assertGreaterEqual(fit.used, 1)
        chars = w.fit_meter(g, "intro", True)
        for fit in chars.values():
            self.assertEqual((fit.unit, fit.limit), ("characters", cg.POPUP_TEXT_MAX))
        self.assertIsNone(w.fit_meter(g, "deadly", False)[1])                    # a silent split shows nothing
        g["nodes"]["intro"]["text"] = " ".join(["(Name) waits."] * 160)
        over = w.fit_meter(g, "intro", False)[3]
        self.assertTrue(over.over, over)
        self.assertTrue(cg.validate(g)[1])

    def test_save_writes_both_files_atomically_and_the_binary_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            g = w.example_event()
            saved = w.save_event(g, Path(tmp), "My Adventure")
            folder = Path(tmp) / "Virtual Villagers Fun Patcher" / "Custom Island Events"
            self.assertEqual((saved.json, saved.cieg, saved.problems),
                             (folder / "My Adventure.json", folder / "My Adventure.cieg", []))
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["My Adventure.cieg", "My Adventure.json"])
            back = cg.decompile_graph(saved.cieg.read_bytes())
            self.assertEqual(back, cg.load(json.loads(saved.json.read_text(encoding="utf-8"))))
            self.assertEqual(w.read_event(saved.json), g)
            self.assertEqual(w.library_events(Path(tmp)), [("My Adventure", 0)])
            # An event with problems: its .json alone, and the library says it has problems.
            g["nodes"]["a_open"]["children"][0]["next"] = "nowhere"
            broken = w.save_event(g, Path(tmp), "Broken")
            self.assertIsNone(broken.cieg)
            self.assertTrue(broken.problems)
            self.assertFalse((folder / "Broken.cieg").exists())
            self.assertEqual(dict(w.library_events(Path(tmp)))["Broken"], len(broken.problems))
            self.assertFalse([p for p in folder.iterdir() if ".tmp" in p.name])


TK_CHILD = r"""
import json, sys, tkinter
from pathlib import Path
from tkinter import ttk
sys.path.insert(0, sys.argv[1])
import vv_save_backup, vv_cie_graph as cg, vv_cie_library_window as w
save = Path(sys.argv[2])
vv_save_backup.documents_folder = lambda: save.parent
vv_save_backup.find_save_folders = lambda title, documents: [save] if "Secret City" in title else []
asked = []
w.ASK_YES_NO = lambda *a, **k: asked.append(a[1]) or True
w.SHOW_INFO = w.SHOW_ERROR = lambda *a, **k: asked.append(a[1])
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
root.withdraw()


class Build:
    def __init__(self, title):
        self.title = title


root.builds = [Build(t) for t in w.GAME_TITLES.values()]
window = w.open_cie_library(root, root.builds[2])
window.update()
lib = window.cie
out = {"title": window.title(), "resizable": list(window.resizable()), "folders": [str(f) for f in lib.folders],
       "tabs": [lib.tabs.tab(t, "text") for t in lib.tabs.tabs()], "new_problems": lib.problems}
lib.new_from_example()
window.update()
out["example_problems"] = lib.problems
out["example_tree"] = len(lib.tree_rows)
lib.select_node("a_open", "Next")
lib.select_child(0)
window.update()
before = lib.chances_shown()
lib.weight_var.set("6")
window.update()
lib.refresh_now()
after = lib.chances_shown()
out["weight"] = lib.g["nodes"]["a_open"]["children"][0]["weight"]
out["row"] = list(lib.children_table.item("0", "values"))
out["chances_before"] = [l for l in before.splitlines() if l.strip().startswith("A7")][0]
out["chances_after"] = [l for l in after.splitlines() if l.strip().startswith("A7")][0]
lib.next_var.set("no_such_part")
lib.refresh_now()
out["link_problems"] = lib.problems
out["status"] = lib.status.cget("text")
lib.select_node("intro", "Text")
out["jump"] = lib.jump_to_problem(0)
out["selected"] = lib.nid
out["shown_tab"] = lib.tabs.tab(lib.tabs.select(), "text")
lib.select_child(0)
lib.next_var.set("find_dirt")
lib.refresh_now()
out["fixed_problems"] = lib.problems
saved = lib.save_as("My Adventure")
out["saved"] = [str(saved.json), str(saved.cieg)]
out["library"] = lib.library
out["dirty_after_save"] = lib.dirty
# The Cave Explorers: three questions, the second and third after other pages (version 2).
lib.load_event(w.example_event(w.CAVE_EXAMPLE), None, dirty=False)
lib.refresh_now()
out["cave_problems"] = lib.problems
out["cave_version"] = lib.g["version"]
# A question added to a later page: its kind chosen, both buttons labelled and pointed at their parts.
lib.load_event(w.new_event(), None, dirty=False)
lib.add_part()
mid = lib.nid
lib.add_part()
left = lib.nid
lib.select_node(mid, "Text")
lib.add_part()
right = lib.nid
lib.select_node(mid, "Next")
lib.type_box.set(w.TYPE_WORDS["question"])
lib._type_changed()
window.update()
lib.choice_vars[0][0].set("Go left")
lib.choice_vars[1][0].set("Go right")
window.update()
lib.refresh_now()
out["mid_version"] = lib.g["version"]
out["mid_choices"] = [dict(c) for c in lib.g["nodes"][mid]["choices"]]
out["mid_parts"] = [mid, left, right]
out["mid_problems"] = lib.problems
# A button to no part, and a button straight into another question: both are problems.
lib.choice_vars[1][1].set("")
lib._choice_set(1, "next")
lib.refresh_now()
out["dangling_problems"] = lib.problems
lib.choice_vars[1][1].set(mid)
lib._choice_set(1, "next")
lib.refresh_now()
out["loop_problems"] = lib.problems
# Version 3: a puzzle needed (picked in the Event tab's list), a bad range and a bad age gap on the Check tab.
lib.load_event(w.new_event(), None, dirty=False)
lib.puzzle_game.set("A New Home")
lib._show_puzzles()
lib.puzzle_list.selection_set(14)
lib._puzzles_changed()
lib.refresh_now()
out["puzzle_req"] = lib.g["requirement"].get("puzzles")
out["puzzle_version"] = lib.g["version"]
out["puzzle_problems"] = lib.problems
out["puzzle_note"] = lib.puzzle_note.cget("text")
lib.g["nodes"]["start"]["effects"] = [{"do": "food", "amount": 100, "max": 50, "scaled": False, "defer": False}]
lib.g["roles"]["friend"] = w.new_role()
lib.g["roles"]["friend"]["max_age_gap"] = {"role": "friend", "years": 5}
lib.refresh_now()
out["v3_problems"] = lib.problems
lib.load_event(w.example_event(), None, dirty=False)
# Every scrolled page is far below the Windows limit.
heights = {}
def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)
for tab in lib.tabs.tabs():
    lib.tabs.select(tab)
    window.update()
for widget in walk(window):
    if isinstance(widget, tkinter.Canvas):
        for item in widget.find_all():
            if widget.type(item) == "window":
                inner = widget.nametowidget(widget.itemcget(item, "window"))
                heights[str(widget)] = inner.winfo_reqheight()
out["heights"] = heights
out["window_height"] = window.winfo_height()
out["screen_height"] = window.winfo_screenheight()
# The words on the window: no code labels.
words = []
for widget in walk(window):
    try:
        text = widget.cget("text")
    except tkinter.TclError:
        continue
    if text:
        words.append(str(text))
out["words"] = words
lib.close()
out["closed"] = not window.winfo_exists()
out["asked"] = asked
root.destroy()
print(json.dumps(out))
"""


class Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save = Path(tmp) / "Virtual Villagers - The Secret City"
            save.mkdir()
            done = subprocess.run([sys.executable, "-c", TK_CHILD, str(ROOT / "src"), str(save)],
                                  capture_output=True, text=True, timeout=300)
            cls.code, cls.stderr = done.returncode, done.stderr
            cls.out = json.loads(done.stdout.strip().splitlines()[-1]) if done.returncode == 0 else {}
            if cls.out:
                cls.json_bytes = Path(cls.out["saved"][0]).read_bytes()
                cls.cieg_bytes = Path(cls.out["saved"][1]).read_bytes()

    def setUp(self) -> None:
        if self.code == NO_TK:
            self.skipTest(f"no Tk display: {self.stderr.strip()}")
        self.assertEqual(self.code, 0, self.stderr)

    def test_opens_resizable_with_its_tabs_and_closes(self) -> None:
        self.assertTrue(self.out["title"].startswith(w.TITLE))
        self.assertEqual(self.out["resizable"], [True, True])
        self.assertEqual(self.out["tabs"], ["Event", "Text", "Next", "Changes", "Roles", "Check"])
        self.assertEqual(self.out["new_problems"], [])
        self.assertEqual(len(self.out["folders"]), 1)
        self.assertTrue(self.out["closed"])

    def test_loads_the_aspiring_adventurer(self) -> None:
        self.assertEqual(self.out["example_problems"], [])
        self.assertGreater(self.out["example_tree"], 30)

    def test_a_weight_edited_changes_the_chances(self) -> None:
        self.assertEqual(self.out["weight"], 6)
        self.assertEqual(self.out["row"][:3], ["find_dirt", "6", "75%"])
        self.assertTrue(self.out["chances_before"].endswith("12.5%"), self.out["chances_before"])
        self.assertNotEqual(self.out["chances_before"], self.out["chances_after"])
        self.assertTrue(self.out["chances_after"].endswith("18.75%"), self.out["chances_after"])

    def test_a_link_to_no_part_is_an_error_that_leads_to_its_part(self) -> None:
        self.assertIn("node a_open: 'no_such_part' names no node", self.out["link_problems"])
        self.assertIn("problem(s) to fix on the Check tab", self.out["status"])
        self.assertEqual((self.out["jump"], self.out["selected"], self.out["shown_tab"]), ("a_open", "a_open", "Text"))
        self.assertEqual(self.out["fixed_problems"], [])

    def test_save_writes_the_library_and_the_binary_round_trips(self) -> None:
        json_path, cieg_path = map(Path, self.out["saved"])
        self.assertEqual(json_path.parent.parts[-2:], ("Virtual Villagers Fun Patcher", "Custom Island Events"))
        self.assertEqual((json_path.name, cieg_path.name), ("My Adventure.json", "My Adventure.cieg"))
        g = cg.load(json.loads(self.json_bytes.decode("utf-8")))
        self.assertEqual(g["nodes"]["a_open"]["children"][0]["weight"], 6)
        self.assertEqual(cg.decompile_graph(self.cieg_bytes), g)
        self.assertEqual(cg.compile_graph(g), self.cieg_bytes)
        self.assertEqual(self.out["library"], ["My Adventure"])
        self.assertFalse(self.out["dirty_after_save"])

    def test_the_cave_explorers_example_asks_three_questions(self) -> None:
        self.assertEqual(self.out["cave_problems"], [])
        self.assertEqual(self.out["cave_version"], 3)

    def test_puzzles_ranges_and_age_gaps(self):
        self.assertEqual(self.out["puzzle_req"], {"1": ["The Cave"]})
        self.assertEqual(self.out["puzzle_version"], 3)
        self.assertEqual(self.out["puzzle_problems"], [])
        self.assertIn("A New Home: The Cave", self.out["puzzle_note"])
        text = "\n".join(self.out["v3_problems"])
        self.assertIn("its top is above its amount", text)
        self.assertIn("the age gap names another villager role", text)

    def test_a_question_on_a_later_page(self) -> None:
        mid, left, right = self.out["mid_parts"]
        self.assertGreaterEqual(self.out["mid_version"], 2, "a question past the start needs version 2 or later")
        self.assertEqual(self.out["mid_choices"], [{"label": "Go left", "next": left},
                                                    {"label": "Go right", "next": right}])
        self.assertEqual(self.out["mid_problems"], [])
        self.assertIn(f"node {mid}: '' names no node", self.out["dangling_problems"])
        self.assertTrue(any(p.startswith("a cycle:") for p in self.out["loop_problems"]), self.out["loop_problems"])

    def test_no_page_is_tall(self) -> None:
        self.assertTrue(self.out["heights"])
        for name, height in self.out["heights"].items():
            self.assertLess(height, WINDOWS_LIMIT, name)
            self.assertLess(height, PAGE_BUDGET, name)
        self.assertLessEqual(self.out["window_height"], self.out["screen_height"])

    def test_the_window_shows_no_code_labels(self) -> None:
        text = " ".join(self.out["words"]).lower()
        for word in ("node", "json", "cieg", "pay_award", "defer", "graph"):
            self.assertNotIn(word, text)
        self.assertEqual(self.out["asked"], [])                        # nothing asked: nothing was left unsaved


class Wiring(unittest.TestCase):
    def test_a_button_on_the_tools_tab_with_its_guide(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn('text="Custom Island Event Library...",', source)
        self.assertIn("vv_cie_library_window.open_cie_library(self, None)", source)
        self.assertIn('self._help_button(stew_tools, "custom_island_event_library")', source)
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))["controls"]
        self.assertEqual(guide["custom_island_event_library"]["title"], w.TITLE)

    def test_it_ships(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for path in ("src/vv_cie_library_window.py", "src/vv_cie_graph.py",
                     "data/cie_graphs/the_aspiring_adventurer.json", "data/cie_graphs/the_cave_explorers.json"):
            self.assertIn(f'"{path}"', release)

    def test_translation_coverage(self) -> None:
        """The window is a patcher tool window: like Stew Recipes and Game Mechanics its words are the patcher's
        own English and none of them is shown in a game.  The words it puts into a game are the death causes it
        offers: the two stock ones are the patcher's in-game strings, already in the translation template."""
        rows = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        english = {row["english"] for row in rows["strings"]}
        for words in w.CAUSE_WORDS.values():
            self.assertIn(words, english)
        # Nothing in the window claims a translation key it does not have.
        source = (ROOT / "src" / "vv_cie_library_window.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"vvfp\.[a-z_]+/", source))


if __name__ == "__main__":
    unittest.main()
