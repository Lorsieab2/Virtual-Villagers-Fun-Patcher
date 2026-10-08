"""The Family Tree Maker's portrait text formatted word by word.

The owner (2026-10-08): "please allow text formatting in the family tree portrait text section" --
select words (a line, a word, part of a word), then Bold, Italic, Underline, Strikethrough,
Superscript, Subscript or Colour them, from buttons over the Portrait text box or a right click.
Each portrait's own lines are kept with their runs ([text, style]) in the edits; the tree, the
saved picture and the SVG page draw each run as it is styled.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_gdiplus  # noqa: E402
from test_genealogy import village  # noqa: E402

BOLD = {"bold": True}


def edits_with(runs: list, styles: dict | None = None) -> tuple:
    v = village()
    p = v.people[9]
    lines = ["".join(text for text, _s in line) for line in runs]
    key = ft.entry_key(v, p)
    e = ft.Edits(entries={key: {"lines": lines, "runs": ft.runs_data(runs)}}, styles=styles or {})
    return v, p, e, key


def texts_of(sc: ft.Scene, pid: int) -> list[ft.Text]:
    return [i for i in sc.items if isinstance(i, ft.Text) and i.pid == pid and i.role]


class StoredRunsTests(unittest.TestCase):
    def test_runs_round_trip_through_the_edits_file_and_the_tree_file(self) -> None:
        runs = [[("9. ", {}), ("Ivo", {"italic": True, "colour": "#AA0000"})],
                [("H", {}), ("2", {"script": "sub"}), ("O ", {}), ("fan", {"bold": True, "underline": True,
                                                                               "strike": True})]]
        v, _p, e, key = edits_with(runs)
        stored = e.entries[key]["runs"]
        self.assertEqual(stored[0][1], ["Ivo", {"italic": True, "colour": "#AA0000"}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "edits.json"
            e.save(path)
            back = ft.Edits.load(path)
            # The colour is kept as the file's other colours are: lower case, and the same again.
            self.assertEqual(back.entries[key]["lines"], ["9. Ivo", "H2O fan"])
            self.assertEqual(back.entries[key]["runs"][0][1], ["Ivo", {"italic": True, "colour": "#aa0000"}])
            self.assertEqual(back.entries[key]["runs"][1][1], ["2", {"script": "sub"}])
            again = Path(tmp) / "again.json"
            back.save(again)
            self.assertEqual(ft.Edits.load(again).entries, back.entries)
            # The tree file (Save to Save Folder / Open Tree File) carries the edits as they are.
            tree = {"format": ft.TREE_FORMAT, "game": 1, "slot": 1, "tribe": v.tribe, "edits": back.to_data()}
            opened = ft.Edits.from_data(json.loads(json.dumps(tree))["edits"])
            self.assertEqual(opened.entries, back.entries)
            # Still format 1: an older patcher opens the file and shows the words, unformatted.
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["format"], 1)

    def test_old_files_load_unchanged_and_bad_runs_are_dropped(self) -> None:
        v = village()
        key = ft.entry_key(v, v.people[9])
        old = {"format": 1, "entries": {key: {"lines": ["One", "Two"], "mark": "Chief"}}}
        self.assertEqual(ft.Edits.from_data(old).entries, {key: {"lines": ["One", "Two"], "mark": "Chief"}})
        for runs in ([[["One", BOLD]]],                                 # a line short
                     [[["Onx", BOLD]], [["Two", {}]]],                  # words that are not the line's
                     [[["One", {}]], [["Two", {}]]],                    # nothing formatted
                     [[["One", "bold"]], [["Two", {}]]],                # not a style: unformatted
                     "bold"):
            data = {"format": 1, "entries": {key: {"lines": ["One", "Two"], "runs": runs}}}
            self.assertEqual(ft.Edits.from_data(data).entries[key], {"lines": ["One", "Two"]}, runs)
        # A style keeps only what it may hold.
        data = {"format": 1, "entries": {key: {"lines": ["One"], "runs": [[["O", {"bold": 1, "italic": True,
                                                                                    "script": "up", "font": "X",
                                                                                    "colour": "red"}],
                                                                             ["ne", {}]]]}}}
        self.assertEqual(ft.Edits.from_data(data).entries[key]["runs"], [[["O", {"italic": True}], ["ne", {}]]])

    def test_reset_text_leaves_the_patchers_own_words(self) -> None:
        v, p, e, key = edits_with([[("9. I", BOLD)]])
        lay = ft.layout(v, e)
        self.assertIsNotNone(ft.node_runs(lay, p))
        e.entries[key].pop("lines")
        e.entries[key].pop("runs")
        lay = ft.layout(v, e)
        self.assertIsNone(ft.node_runs(lay, p))
        self.assertEqual(ft.node_text(lay, p), ft.default_text(lay, p))
        self.assertTrue(all(t.runs is None for t in texts_of(ft.scene(lay, "VV", {}), p.id)))


class DrawnRunsTests(unittest.TestCase):
    def test_a_runs_own_style_beats_its_roles(self) -> None:
        styles = {"portraits": {"italic": True, "colour": "#ff0000", "script": "super"}}
        v, p, e, _key = edits_with([[("9. I", {})], [("plain ", {}), ("own", {"italic": False, "colour": "#00ff00",
                                                                             "script": "normal"})]], styles)
        sc = ft.scene(ft.layout(v, e), "VV", {})
        item = next(t for t in texts_of(sc, p.id) if t.text == "plain own")
        self.assertEqual(item.script, "super")
        self.assertEqual(item.size, 10)                  # each run is raised on its own, not the line
        plain, own = (ft.run_look(item, style) for _text, style in item.runs)
        self.assertEqual((plain["italic"], plain["colour"]), (True, "#ff0000"))
        self.assertEqual((own["italic"], own["colour"]), (False, "#00ff00"))
        shrink, shift = ft.SCRIPTS["super"]
        self.assertEqual((plain["size"], plain["dy"]), (10 * shrink, 10 * shift))
        self.assertEqual((own["size"], own["dy"]), (10, 0))
        # The name's line is bold by its role; a run may say not.
        v, p, e, _key = edits_with([[("9. ", {"bold": False}), ("I", {})]])
        name = texts_of(ft.scene(ft.layout(v, e), "VV", {}), p.id)[0]
        self.assertEqual([ft.run_look(name, s)["bold"] for _t, s in name.runs], [False, True])

    def test_plain_words_wrap_exactly_as_before(self) -> None:
        for text in ("Typed by the player, who types a lot", "x" * 40, "a " * 40, "  two  spaces  ", "",
                     "supercalifragilistic word and more words here", "ends with space "):
            cells = [(ch, 1.0, {}) for ch in text]
            wrapped = ["".join(c[0] for c in line) for line in ft._wrap_cells(cells)]
            self.assertEqual(wrapped, ft._wrap(text), text)

    def test_formatted_words_wrap_by_their_fonts_width(self) -> None:
        base = ft.line_base(ft.Edits(), False)
        bold = [(ch, ft.run_width(BOLD, base), BOLD) for ch in "abcdefghijklmnopq"]       # 17 letters
        self.assertEqual(len(ft._wrap_cells(bold)), 2, "17 bold letters are wider than 17 plain ones")
        small = {"script": "super"}
        sup = [(ch, ft.run_width(small, base), small) for ch in "abcdefghijklmnopqrstuvwxy"]  # 25
        self.assertEqual(len(ft._wrap_cells(sup)), 1, "smaller letters fit more")
        # On the name's line (bold already) bold is no wider, and unbolding is narrower.
        name = ft.line_base(ft.Edits(), True)
        self.assertEqual(ft.run_width(BOLD, name), 1.0)
        self.assertLess(ft.run_width({"bold": False}, name), 1.0)
        # Every wrapped line fits across the portrait.
        mixed = [(ch, ft.run_width(s, base), s) for k, ch in enumerate("bold and plain words mixed up " * 3)
                 for s in [BOLD if k % 3 else {}]]
        for line in ft._wrap_cells(mixed):
            if len(line) > 1:
                self.assertLessEqual(sum(c[1] for c in line), ft.WRAP + 1e-9)

    def test_shown_text_wraps_and_cuts_formatted_lines(self) -> None:
        long = "abcdefghij " * 8
        v, p, e, _key = edits_with([[("9. I", {})], [(long, BOLD)]])
        lay = ft.layout(v, e)
        shown = ft.shown_text(lay, p, 4)
        self.assertEqual(len(shown), 4)
        self.assertTrue(shown[-1][0].endswith("…"))
        for text, _bold, runs in shown[1:]:
            self.assertEqual(runs[0][1], BOLD)
            self.assertEqual("".join(t for t, _s in runs), text)
            self.assertLessEqual(len(text) * ft.BOLD_WIDTH, ft.WRAP + 1e-9)
        # A plain line beside them is drawn as ever, with no runs.
        self.assertIsNone(shown[0][2])

    def test_the_svg_draws_each_run(self) -> None:
        v, p, e, _key = edits_with([[("9. ", {}), ("I & co", {"italic": True, "underline": True, "colour": "#123456"})],
                                    [("x", {}), ("2", {"script": "super"}), ("y", {})]])
        svg = ft.to_svg(ft.scene(ft.layout(v, e), "VV", {}), {})
        xml.dom.minidom.parseString(svg)
        self.assertIn('font-style="italic" text-decoration="underline" fill="#123456"', svg)
        self.assertIn("I &amp; co</tspan>", svg)
        shrink, shift = ft.SCRIPTS["super"]
        self.assertIn(f'dy="{10 * shift:g}">2</tspan>', svg)
        self.assertIn(f'dy="{-10 * shift:g}">y</tspan>', svg)

    @unittest.skipUnless(vv_gdiplus.available(), "Windows' own graphics")
    def test_the_picture_draws_formatted_words(self) -> None:
        v, p, e, _key = edits_with([[("9. ", {}), ("BIG", {"bold": True, "colour": "#ff0000"})],
                                    [("x", {}), ("2", {"script": "sub", "strike": True}), ("y", {})]])
        sc = ft.scene(ft.layout(v, e), "VV", {})
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("tree.png", "tree.jpg"):
                self.assertTrue(vv_gdiplus.save_scene(sc, {}, Path(tmp) / name))


class EditingTests(unittest.TestCase):
    def test_format_buttons_toggle_like_a_word_processor(self) -> None:
        plain, name = ft.line_base(ft.Edits(), False), ft.line_base(ft.Edits(), True)
        self.assertEqual(ft.format_styles([{}, {}], [plain, plain], "bold"), [BOLD, BOLD])
        self.assertEqual(ft.format_styles([BOLD, {}], [plain, plain], "bold"), [BOLD, BOLD], "some: all on")
        self.assertEqual(ft.format_styles([BOLD, BOLD], [plain, plain], "bold"), [{}, {}], "all: off")
        self.assertEqual(ft.format_styles([{}], [name], "bold"), [{"bold": False}], "the name unbolded")
        self.assertEqual(ft.format_styles([{"bold": False}], [name], "bold"), [{}])
        self.assertEqual(ft.format_styles([{}], [plain], "super"), [{"script": "super"}])
        self.assertEqual(ft.format_styles([{"script": "sub"}], [plain], "super"), [{"script": "super"}])
        self.assertEqual(ft.format_styles([{"script": "super"}], [plain], "super"), [{}])
        role_super = dict(plain, script="super")
        self.assertEqual(ft.format_styles([{}], [role_super], "super"), [{"script": "normal"}])
        self.assertEqual(ft.format_styles([BOLD], [plain], "colour", "#00ff00"), [{"bold": True, "colour": "#00ff00"}])
        self.assertEqual(ft.format_styles([{"colour": "#00ff00", "italic": True}], [plain], "plain"), [{}])

    def test_retyping_keeps_the_formatting_it_can(self) -> None:
        old = ["9. Ivo", "likes fish"]
        runs = [[("9. ", {}), ("Ivo", BOLD)], [("likes ", {}), ("fish", {"italic": True})]]
        self.assertEqual(ft.carry_styles(old, runs, ["10. Ivo", "likes fish"]),
                         [[["10. ", {}], ["Ivo", BOLD]], [["likes ", {}], ["fish", {"italic": True}]]])
        self.assertEqual(ft.carry_styles(old, runs, ["9. Ivor", "likes big fish"])[0], [["9. ", {}], ["Ivor", BOLD]])
        self.assertIsNone(ft.carry_styles(old, None, ["x"]))
        self.assertIsNone(ft.carry_styles(old, runs, ["9. ", "likes "]))


class WindowWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.src = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")

    def part(self, start: str, end: str) -> str:
        return self.src[self.src.index(start):self.src.index(end, self.src.index(start))]

    def test_the_box_has_format_buttons_a_menu_and_shortcuts(self) -> None:
        tab = self.part("    def _selected_tab(self)", 'box = ttk.LabelFrame(tab, text="Special mark"')
        self.assertIn("for what, label, look in TEXT_FORMATS:", tab)
        self.assertIn("command=lambda w=what: self._format_text(w)", tab)
        for binding in ('"<Button-3>", self._format_menu', '"<Control-b>"', '"<Control-i>"', '"<Control-u>"',
                        '"<Key>", self._type_formatted'):
            self.assertIn(f"self.lines_text.bind({binding}", tab)
        import vv_genealogy_window as gw
        self.assertEqual([w for w, _l, _f in gw.TEXT_FORMATS],
                         ["bold", "italic", "underline", "strike", "super", "sub", "colour", "plain"])
        self.assertEqual(set(gw.FORMAT_NAMES), {w for w, _l, _f in gw.TEXT_FORMATS})

    def test_save_reset_retype_and_renumber_keep_the_runs(self) -> None:
        apply = self.part("    def _apply_text(self)", "    def _restore_text(self)")
        self.assertIn("lines, runs = self._box_text()", apply)
        self.assertIn("runs=runs)", apply)
        restore = self.part("    def _restore_text(self)", "    # ---- the Portrait text box")
        self.assertIn("lines=None, runs=None)", restore)
        retype = self.part("        def set_person(new: str)", "    def _edit_in_place(")
        self.assertIn("ft.carry_styles(ft.node_text(lay, p), ft.node_runs(lay, p), new.split(", retype)
        renumber = self.part("    def _renumber(self)", "    def _number_names(self)")
        self.assertIn("runs=runs)", renumber)
        refresh = self.part("    def _refresh_selected(self)", "    # ---- changing")
        self.assertIn("self._box_load(ft.node_text(self.lay, people[0]), ft.node_runs(self.lay, people[0]))", refresh)

    def test_every_renderer_draws_runs(self) -> None:
        draw = self.part("    def _draw_tree(self)", "    def _tag(self")
        self.assertIn("elif isinstance(item, ft.Text) and item.runs:", draw)
        self.assertIn("ft.run_look(item, style)", draw)
        gdi = (ROOT / "src" / "vv_gdiplus.py").read_text(encoding="utf-8")
        self.assertIn("elif isinstance(item, ft.Text) and item.runs:\n        _draw_runs(", gdi)
        self.assertIn("ft.run_look(item, style)", gdi)


if __name__ == "__main__":
    unittest.main()
