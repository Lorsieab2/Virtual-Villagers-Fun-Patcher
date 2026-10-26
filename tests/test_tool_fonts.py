"""The tool windows use the Virtual Families 1 patcher's fonts (the owner, 2026-10-25: "I like the VF1
patcher's font better for the game tools"): text areas Segoe UI 10, headings 12 bold, labels 9 bold
(src/vv_tool_fonts.py).  A tk.Text that sets no font shows Tk's fixed-width Courier, so every tool text area
goes through vv_tool_fonts.tool_text or names its font."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_tool_fonts  # noqa: E402

TOOL_MODULES = ("vv_fun_patcher_gui", "vv_game_mechanics_window", "vv_genealogy_window", "vv_tree_editor_tools",
                "vv_villager_info")


class ToolFontTests(unittest.TestCase):
    def test_the_vf1_fonts(self) -> None:
        self.assertEqual(vv_tool_fonts.TEXT, ("Segoe UI", 10))
        self.assertEqual(vv_tool_fonts.HEADING, ("Segoe UI", 12, "bold"))
        self.assertEqual(vv_tool_fonts.LABEL, ("Segoe UI", 9, "bold"))

    def test_no_tool_text_area_falls_back_to_courier(self) -> None:
        for module in TOOL_MODULES:
            source = (ROOT / "src" / f"{module}.py").read_text(encoding="utf-8")
            for match in re.finditer(r"\btk\.Text\(", source):
                call = source[match.end():match.end() + 400].split(")\n")[0]
                with self.subTest(module=module, line=source.count("\n", 0, match.start()) + 1):
                    self.assertIn("font=", call)

    def test_named_fonts_per_root(self) -> None:
        import tkinter as tk
        import tkinter.font as tkfont
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no Tk display: {exc}")
        try:
            root.withdraw()
            box = vv_tool_fonts.tool_text(root)
            actual = tkfont.nametofont(box.cget("font"), root=root).actual()
            self.assertEqual((actual["size"], actual["weight"]), (10, "normal"))
            heading = vv_tool_fonts.fonts(root)["heading"].actual()
            self.assertEqual((heading["size"], heading["weight"]), (12, "bold"))
            self.assertIs(vv_tool_fonts.fonts(box)["text"], vv_tool_fonts.text_font(root))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
