"""The Game Mechanics window (the owner, 2026-10-22): a tool of its own on the Tools tab.

Pick a game, its save folder and a tribe; the window shows that save's hidden game rules as
src/vv_game_mechanics.py reads them, grouped and in real time only.  It only reads: no save, log,
data file, report or backup is written (unlike the tribe pickers that run the reconciliation, it
runs nothing else), so it may be open while the game runs -- it then shows the save as last written.

The window is resizable: the pickers keep their height at the top and the page below is a Text box
with its own scroll bar that takes the rest, so nothing is ever cut off (tests/test_game_mechanics.py,
tests/test_window_scrollbars.py).
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, ttk

import vv_game_mechanics as gm
import vv_save_backup
import vv_tribe_rename

TITLE = gm.TITLE
INTRO = ("For the curious: the hidden rules of one village -- its food sources, refills and more -- worked "
         "out from its save, at the save's game speed, with the patches in the game that change them. "
         "All times are real times. It only reads: nothing is changed, so the game may be running.")
WIDTH, HEIGHT = 860, 680
LABEL_RED = "#b00020"
MIN_WIDTH, MIN_HEIGHT = 560, 480


def page_text(folder: Path, game: int, slot: int, game_folders: list[Path]) -> str:
    """The page for one save slot; a save or file it cannot read is said on the page, never raised."""
    try:
        return gm.render(gm.read(folder, game, slot, game_folders))
    except Exception as exc:  # noqa: BLE001 -- shown, never fatal: the window only reads
        return f"The game mechanics could not be read ({exc}). Nothing was changed."


def open_game_mechanics(app, build) -> tk.Toplevel | None:
    """The window, for `build`'s game (or the first game).  `app` gives the games (app.builds) and
    where each game's folder may be (app._game_folders_for), for the patches in it."""
    documents = vv_save_backup.documents_folder()
    if documents is None:
        messagebox.showerror(TITLE, "Windows did not report where your Documents folder is, so the "
                                    "save folders cannot be found.", parent=app)
        return None
    titles = [item.title for item in app.builds]
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
    pickers = ttk.Frame(outer)
    pickers.pack(fill="x")
    intro = ttk.Label(pickers, text=INTRO, wraplength=width - 60, justify="left")
    intro.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
    # What the UNCONFIRMED label means (the owner, 2026-10-23), right under the intro.
    label_note = ttk.Label(pickers, text=gm.LABEL_NOTE, wraplength=width - 60, justify="left", foreground=LABEL_RED)
    label_note.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))
    # The intro wraps at the window's width as it is resized, so it never runs off the side.
    pickers.bind("<Configure>", lambda event: (intro.configure(wraplength=max(200, event.width - 8)),
                                               label_note.configure(wraplength=max(200, event.width - 8))))
    game_var = tk.StringVar(value=build.title if build is not None else titles[0])
    folder_var = tk.StringVar()
    state: dict = {"folders": [], "slots": []}
    ttk.Label(pickers, text="Game:").grid(row=2, column=0, sticky="w")
    game_box = ttk.Combobox(pickers, textvariable=game_var, values=titles, state="readonly", width=48)
    game_box.grid(row=2, column=1, sticky="we", pady=2)
    ttk.Label(pickers, text="Save folder:").grid(row=3, column=0, sticky="w")
    folder_box = ttk.Combobox(pickers, textvariable=folder_var, state="readonly", width=48)
    folder_box.grid(row=3, column=1, sticky="we", pady=2)
    ttk.Label(pickers, text="Tribe:").grid(row=4, column=0, sticky="nw", pady=(4, 0))
    slot_list = tk.Listbox(pickers, height=5, width=60, exportselection=False)
    slot_list.grid(row=4, column=1, sticky="we", pady=(4, 2))
    pickers.columnconfigure(1, weight=1)

    buttons = ttk.Frame(outer)
    buttons.pack(side="bottom", fill="x", pady=(8, 0))
    page = ttk.Frame(outer)
    page.pack(fill="both", expand=True, pady=(8, 0))
    box = tk.Text(page, wrap="word", height=1)
    bar = ttk.Scrollbar(page, orient="vertical", command=box.yview)
    box.configure(yscrollcommand=bar.set, state="disabled")
    bar.pack(side="right", fill="y")
    box.pack(side="left", fill="both", expand=True)
    bold = tkfont.nametofont(box.cget("font")).copy()
    bold.configure(weight="bold")
    window.bold_font = bold                 # kept while the window is open
    box.tag_configure("group", font=bold)
    box.tag_configure("unconfirmed", font=bold, foreground=LABEL_RED)
    window.mechanics_page = box             # for the tests
    window.mechanics_parts = (pickers, intro, buttons, label_note)

    def game() -> vv_tribe_rename.GameSaves:
        return vv_tribe_rename.game_for_title(game_var.get())

    def chosen():
        picked = slot_list.curselection()
        if not picked or not state["folders"]:
            return None
        info = state["slots"][picked[0]]
        return info if info.name is not None else None

    def show(*_args) -> None:
        info = chosen()
        if not state["folders"]:
            text = "No save folder was found for this game."
        elif info is None:
            text = "Choose a tribe."
        else:
            folder = state["folders"][folder_box.current()]
            places = getattr(app, "_game_folders_for", None)
            text = page_text(folder, game().number, info.slot, places(folder) if places else [])
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        for number, line in enumerate(text.split("\n"), 1):
            if line in gm.GROUPS:
                box.tag_add("group", f"{number}.0", f"{number}.end")
            at = line.find(gm.UNCONFIRMED)
            if at >= 0:
                box.tag_add("unconfirmed", f"{number}.{at}", f"{number}.{at + len(gm.UNCONFIRMED)}")
        box.configure(state="disabled")

    def load_slots(*_args) -> None:
        slot_list.delete(0, "end")
        state["slots"] = []
        index = folder_box.current()
        if 0 <= index < len(state["folders"]):
            state["slots"] = vv_tribe_rename.read_slots(game(), state["folders"][index])
            for info in state["slots"]:
                slot_list.insert("end", info.label)
            first = next((n for n, info in enumerate(state["slots"]) if info.name is not None), None)
            if first is not None:
                slot_list.selection_set(first)
        show()

    def load_folders(*_args) -> None:
        state["folders"] = vv_save_backup.find_save_folders(game_var.get(), documents)
        folder_box.configure(values=[folder.name for folder in state["folders"]])
        if state["folders"]:
            folder_box.current(0)
        else:
            folder_var.set("")
        load_slots()

    ttk.Button(buttons, text="Refresh", command=show).pack(side="left")
    ttk.Button(buttons, text="Close", command=window.destroy).pack(side="left", padx=(8, 0))
    game_box.bind("<<ComboboxSelected>>", load_folders)
    folder_box.bind("<<ComboboxSelected>>", load_slots)
    slot_list.bind("<<ListboxSelect>>", show)
    load_folders()
    return window
