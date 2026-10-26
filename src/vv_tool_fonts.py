"""The tool windows' fonts: the Virtual Families 1 patcher's (the owner, 2026-10-25: "I like the VF1 patcher's
font better for the game tools").

VF1's tool windows are Segoe UI throughout.  Their labels, buttons and pickers are Tk's default font (Segoe UI 9
on Windows), as the VV tool windows' already are; the difference was the tools' text areas: a tk.Text that sets
no font falls back to Tk's fixed-width Courier, where VF1 sets Segoe UI explicitly
(Virtual-Families-1-Patcher patcher/vf1_game_mechanics.py open_window):

  * TEXT     -- a tool's text area:                     Segoe UI 10
  * HEADING  -- a heading inside one (a group's name):  Segoe UI 12 bold
  * LABEL    -- a small bold label inside one:          Segoe UI 9 bold

Only the Tools tab's windows use these; the main patcher window keeps its own look.  The fonts are named Tk
fonts, one set per Tk root, so `tkfont.nametofont(box.cget("font"))` still works on a box given one.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

FAMILY = "Segoe UI"
TEXT = (FAMILY, 10)
HEADING = (FAMILY, 12, "bold")
LABEL = (FAMILY, 9, "bold")
BOLD = (FAMILY, 10, "bold")
HEADING_SPACING = {"spacing1": 10, "spacing3": 4}

_SPECS = {"text": TEXT, "heading": HEADING, "label": LABEL, "bold": BOLD}


def fonts(widget) -> dict[str, tkfont.Font]:
    """The named tool fonts of `widget`'s Tk root: "text", "heading", "label" and "bold" (TEXT in bold)."""
    root = widget._root()
    found = getattr(root, "_vv_tool_fonts", None)
    if found is None:
        found = {}
        for key, (family, size, *weight) in _SPECS.items():
            found[key] = tkfont.Font(root=root, family=family, size=size, weight=weight[0] if weight else "normal")
        root._vv_tool_fonts = found
    return found


def text_font(widget) -> tkfont.Font:
    """A tool's text-area font (Segoe UI 10), for `widget`'s Tk root."""
    return fonts(widget)["text"]


def tool_text(parent, **options) -> tk.Text:
    """A tk.Text for a tool window, in the tool text font unless `options` gives one."""
    options.setdefault("font", text_font(parent))
    return tk.Text(parent, **options)
