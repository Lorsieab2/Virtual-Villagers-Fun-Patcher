"""The Stew Recipes window (the owner, 2026-11-10: "Separate window"): a tool of its own on the Tools tab.

One tab for each game that cooks stews -- The Lost Children, The Secret City and The Tree of Life -- showing that
game's page from src/vv_stew_recipes.py: every recipe's herbs by their in-game names, its water and what happens.  It
reads no save and no file: the pages are the games' own code, written down once.  A line the code does not settle
carries UNCONFIRMED in red, as in Game Mechanics.

The window is resizable: the intro and the Close button keep their height, and each tab's page is a Text box with
its own scroll bar that takes the rest (tests/test_window_scrollbars.py), so a page never grows the window.
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import vv_game_mechanics as gm
import vv_stew_recipes as recipes
import vv_tool_fonts

TITLE = "Stew Recipes"
INTRO = ("Every stew the cauldron makes in three of the games: the herbs by the names the game shows, the water it "
         "takes and what happens when it is eaten. Anything from the cauldron counts as a stew. Read from each "
         "game's own code; nothing is read from your saves and nothing is changed.")
LABEL_RED = "#b00020"
WIDTH, HEIGHT = 900, 720
MIN_WIDTH, MIN_HEIGHT = 600, 500
NOTE = ("UNCONFIRMED, in red, marks a line the game's code does not settle, or where what players have seen and the "
        "code disagree.")
GAMES = ((2, "The Lost Children"), (3, "The Secret City"), (4, "The Tree of Life"))


def page_text(game: int) -> str:
    """One game's page as the window shows it: its lines, without the group's heading."""
    try:
        lines = gm.render(recipes.facts(game)).split("\n")
    except Exception as exc:  # noqa: BLE001 -- shown, never fatal: the window only reads
        return f"The stew recipes could not be shown ({exc})."
    return "\n".join(lines[1:] if lines and lines[0] == recipes.GROUP else lines)


def _fill(box: tk.Text, text: str) -> None:
    box.configure(state="normal")
    box.delete("1.0", "end")
    box.insert("1.0", text)
    for number, line in enumerate(text.split("\n"), 1):
        if line.startswith(gm.SUB_BULLET):
            box.tag_add("sub", f"{number}.0", f"{number}.end")
        elif line.startswith(gm.BULLET):
            box.tag_add("bullet", f"{number}.0", f"{number}.end")
        at = line.find(gm.UNCONFIRMED)
        if at >= 0:
            box.tag_add("unconfirmed", f"{number}.{at}", f"{number}.{at + len(gm.UNCONFIRMED)}")
    box.configure(state="disabled")


def open_stew_recipes(app, game: int | None = None) -> tk.Toplevel:
    """The window, opened at `game`'s tab (2, 3 or 4; the first otherwise)."""
    window = tk.Toplevel(app)
    window.title(TITLE)
    window.transient(app)
    width = min(WIDTH, max(MIN_WIDTH, window.winfo_screenwidth() - 80))
    height = min(HEIGHT, max(MIN_HEIGHT, window.winfo_screenheight() - 120))
    window.geometry(f"{width}x{height}")
    window.minsize(MIN_WIDTH, MIN_HEIGHT)
    window.resizable(True, True)

    outer = ttk.Frame(window, padding=12)
    outer.pack(fill="both", expand=True)
    intro = ttk.Label(outer, text=INTRO, wraplength=width - 60, justify="left")
    intro.pack(anchor="w")
    note = ttk.Label(outer, text=NOTE, wraplength=width - 60, justify="left", foreground=LABEL_RED)
    note.pack(anchor="w", pady=(4, 8))
    outer.bind("<Configure>", lambda event: (intro.configure(wraplength=max(200, event.width - 8)),
                                             note.configure(wraplength=max(200, event.width - 8))))
    buttons = ttk.Frame(outer)
    buttons.pack(side="bottom", fill="x", pady=(8, 0))
    ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
    notebook = ttk.Notebook(outer)
    notebook.pack(fill="both", expand=True)

    tabs: dict[int, tk.Text] = {}
    for number, name in GAMES:
        tab = ttk.Frame(notebook, padding=8)
        notebook.add(tab, text=name)
        # The VF1 patcher's page (src/vv_tool_fonts.py), as Game Mechanics: Segoe UI 10, labels 9 bold.
        box = vv_tool_fonts.tool_text(tab, wrap="word", height=1, padx=8, pady=8, borderwidth=1, relief="solid")
        bar = ttk.Scrollbar(tab, orient="vertical", command=box.yview)
        box.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        box.pack(side="left", fill="both", expand=True)
        box.tag_configure("unconfirmed", font=vv_tool_fonts.fonts(box)["label"], foreground=LABEL_RED)
        # A wrapped line continues under the bullet's text, not under the bullet (as Game Mechanics).
        plain = tkfont.nametofont(box.cget("font"))
        box.tag_configure("bullet", lmargin1=0, lmargin2=plain.measure(gm.BULLET))
        box.tag_configure("sub", lmargin1=0, lmargin2=plain.measure(gm.SUB_BULLET))
        _fill(box, page_text(number))
        tabs[number] = box
    numbers = [number for number, _name in GAMES]
    notebook.select(numbers.index(game) if game in numbers else 0)
    window.stew_tabs = tabs                 # for the tests
    window.stew_notebook = notebook
    return window
