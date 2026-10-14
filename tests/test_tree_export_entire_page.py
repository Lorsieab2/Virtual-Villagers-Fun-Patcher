"""Family Tree Maker: Export as Picture always saves the whole tree page(s), never the part the window shows."""
from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy_window as gw  # noqa: E402
import vv_gdiplus  # noqa: E402
import test_genealogy as tg  # noqa: E402


class ExportEntirePageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.village = tg.village()
        self.edits = ft.Edits(pages=[3])
        ft.arrange(self.village, self.edits)
        self.count = len(ft.page_spans(self.edits, self.village))
        self.assertGreater(self.count, 1)
        self.scenes = {k: ft.scene(ft.layout(self.village, self.edits, k), "Test", {}) for k in range(self.count)}
        self.fake = SimpleNamespace(
            edits=self.edits, village=self.village, present={}, status=mock.Mock(), z=0.37, page=1,
            _page_scene=lambda k: (None, self.scenes[k]), _preview_picture=mock.Mock())

    def test_every_page_is_saved_whole_beside_the_first(self) -> None:
        calls = []
        with mock.patch.object(vv_gdiplus, "save_scene",
                               lambda sc, present, target, scale=1.0, **kw: calls.append((sc, Path(target), scale, kw))):
            gw.TreeEditor._save_as(self.fake, Path("C:/x/Tree.png"), 2.0)
        self.assertEqual([c[1].name for c in calls],
                         ["Tree.png"] + [f"Tree - Page {k + 1}.png" for k in range(1, self.count)])
        for k, (sc, _target, scale, kw) in enumerate(calls):
            self.assertIs(sc, self.scenes[k])           # the whole page's own scene
            self.assertEqual((sc.width, sc.height), (self.scenes[k].width, self.scenes[k].height))
            self.assertEqual(scale, 2.0)                # the double-size choice only; never the window's zoom
            self.assertEqual(kw, {})                    # no crop of any kind

    def test_a_page_range_still_saves_only_those_whole_pages(self) -> None:
        calls = []
        with mock.patch.object(vv_gdiplus, "save_scene",
                               lambda sc, present, target, scale=1.0, **kw: calls.append(Path(target).name)):
            gw.TreeEditor._save_as(self.fake, Path("C:/x/Tree.png"), 1.0, pages=[1])
        self.assertEqual(calls, ["Tree - Page 2.png"])

    def test_no_view_only_choice_or_crop_is_left(self) -> None:
        self.assertNotIn("view", inspect.signature(gw.TreeEditor._save_as).parameters)
        self.assertFalse(hasattr(gw.TreeEditor, "_view_crop"))
        self.assertNotIn("crop", inspect.signature(vv_gdiplus.save_scene).parameters)
        self.assertNotIn("Exactly what the window shows", inspect.getsource(gw.TreeEditor._export_options))

    @unittest.skipUnless(vv_gdiplus.available(), "needs Windows' graphics")
    def test_the_picture_is_the_whole_page_size(self) -> None:
        sc = self.scenes[0]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "Tree.png"
            self.assertTrue(vv_gdiplus.save_scene(sc, {}, out, scale=1.0))
            data = out.read_bytes()
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        self.assertEqual((width, height), (max(1, int(sc.width)), max(1, int(sc.height))))


if __name__ == "__main__":
    unittest.main()
