"""The Game Mechanics window (the owner, 2026-10-22): a tool of its own on the Tools tab.

One tab for each game (the owner, 2026-10-23).  In each, pick a save folder and a tribe; the tab shows that
save's hidden game rules as src/vv_game_mechanics.py reads them, grouped, in real time only, with a link to
each group at the top of the page.  A game with no save found still shows its general rules.  It only reads:
no save, log, data file, report or backup is written (unlike the tribe pickers that run the reconciliation,
it runs nothing else), so it may be open while the game runs -- it then shows the save as last written.

The window is resizable: the intro, each tab's pickers and links and the buttons keep their height, and each
tab's page is a Text box with its own scroll bar that takes the rest, so nothing is ever cut off
(tests/test_game_mechanics.py, tests/test_window_scrollbars.py).
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
INTRO = ("For the curious: the hidden rules of each game -- its food sources, refills and more -- worked out from "
         "a village's save, at the save's game speed, with the patches in the game that change them. All times "
         "are real times. It only reads: nothing is changed, so the game may be running.")
WIDTH, HEIGHT = 900, 720
LABEL_RED = "#b00020"
MIN_WIDTH, MIN_HEIGHT = 600, 560
LINKS_PER_ROW = 5


def page_text(folder: Path, game: int, slot: int, game_folders: list[Path]) -> str:
    """The page for one save slot; a save or file it cannot read is said on the page, never raised."""
    try:
        return gm.render(gm.read(folder, game, slot, game_folders))
    except Exception as exc:  # noqa: BLE001 -- shown, never fatal: the window only reads
        return f"The game mechanics could not be read ({exc}). Nothing was changed."


def general_text(game: int) -> str:
    """A game's general rules, when no save of it is found."""
    try:
        return gm.GENERAL_NOTE + "\n\n" + gm.render(gm.general(game))
    except Exception as exc:  # noqa: BLE001 -- shown, never fatal
        return f"The game mechanics could not be shown ({exc})."


def open_game_mechanics(app, build) -> tk.Toplevel | None:
    """The window, opened at `build`'s game (or the first game).  `app` gives the games (app.builds) and
    where each game's folder may be (app._game_folders_for), for the patches in it."""
    documents = vv_save_backup.documents_folder()
    if documents is None:
        messagebox.showerror(TITLE, "Windows did not report where your Documents folder is, so the "
                                    "save folders cannot be found.", parent=app)
        return None
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
    top = ttk.Frame(outer)
    top.pack(fill="x")
    intro = ttk.Label(top, text=INTRO, wraplength=width - 60, justify="left")
    intro.pack(anchor="w")
    # What the UNCONFIRMED label means (the owner, 2026-10-23), right under the intro.
    label_note = ttk.Label(top, text=gm.LABEL_NOTE, wraplength=width - 60, justify="left", foreground=LABEL_RED)
    label_note.pack(anchor="w", pady=(4, 8))
    # The intro wraps at the window's width as it is resized, so it never runs off the side.
    top.bind("<Configure>", lambda event: (intro.configure(wraplength=max(200, event.width - 8)),
                                           label_note.configure(wraplength=max(200, event.width - 8))))
    buttons = ttk.Frame(outer)
    buttons.pack(side="bottom", fill="x", pady=(8, 0))
    notebook = ttk.Notebook(outer)
    notebook.pack(fill="both", expand=True)

    probe = tk.Text(window)
    bold = tkfont.nametofont(probe.cget("font")).copy()
    probe.destroy()
    bold.configure(weight="bold")
    window.bold_font = bold                 # kept while the window is open
    tabs: dict[int, dict] = {}
    window.mechanics_tabs = tabs            # for the tests
    window.mechanics_notebook = notebook
    window.mechanics_parts = (top, intro, buttons, label_note)

    for item in app.builds:
        saves = vv_tribe_rename.game_for_title(item.title)
        tabs[saves.number] = _game_tab(window, notebook, app, item.title, saves, documents, bold)

    first = vv_tribe_rename.game_for_title(build.title).number if build is not None else min(tabs)

    def changed(_event=None) -> None:
        number = list(tabs)[notebook.index(notebook.select())]
        if not tabs[number]["loaded"]:
            tabs[number]["load"]()

    notebook.bind("<<NotebookTabChanged>>", changed)
    notebook.select(list(tabs).index(first))
    changed()

    def refresh() -> None:
        tabs[list(tabs)[notebook.index(notebook.select())]]["show"]()

    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(buttons, text="Close", command=window.destroy).pack(side="left", padx=(8, 0))
    return window


def _game_tab(window, notebook, app, title: str, saves, documents, bold) -> dict:
    """One game's tab: its save picker, links to its groups, and its page."""
    tab = ttk.Frame(notebook, padding=8)
    notebook.add(tab, text=title.removeprefix("Virtual Villagers - ").replace("Virtual Villagers", "A New Home"))
    pickers = ttk.Frame(tab)
    pickers.pack(fill="x")
    folder_var = tk.StringVar()
    ttk.Label(pickers, text="Save folder:").grid(row=0, column=0, sticky="w")
    folder_box = ttk.Combobox(pickers, textvariable=folder_var, state="readonly", width=48)
    folder_box.grid(row=0, column=1, sticky="we", pady=2)
    ttk.Label(pickers, text="Tribe:").grid(row=1, column=0, sticky="nw", pady=(4, 0))
    slot_list = tk.Listbox(pickers, height=3, width=60, exportselection=False)
    slot_list.grid(row=1, column=1, sticky="we", pady=(4, 2))
    pickers.columnconfigure(1, weight=1)
    links = ttk.Frame(tab)
    links.pack(fill="x", pady=(6, 0))
    page = ttk.Frame(tab)
    page.pack(fill="both", expand=True, pady=(6, 0))
    box = tk.Text(page, wrap="word", height=1)
    bar = ttk.Scrollbar(page, orient="vertical", command=box.yview)
    box.configure(yscrollcommand=bar.set, state="disabled")
    bar.pack(side="right", fill="y")
    box.pack(side="left", fill="both", expand=True)
    box.tag_configure("group", font=bold)
    box.tag_configure("unconfirmed", font=bold, foreground=LABEL_RED)
    # Bullets (the owner, 2026-10-23): a wrapped line continues under the bullet's text, not under the bullet.
    plain = tkfont.nametofont(box.cget("font"))
    box.tag_configure("bullet", lmargin1=0, lmargin2=plain.measure(gm.BULLET))
    box.tag_configure("sub", lmargin1=0, lmargin2=plain.measure(gm.SUB_BULLET))
    state: dict = {"folders": [], "slots": []}

    def chosen():
        picked = slot_list.curselection()
        if not picked or not state["folders"]:
            return None
        info = state["slots"][picked[0]]
        return info if info.name is not None else None

    def jump(group: str) -> None:
        index = box.index(f"group:{group}")
        box.yview(index)

    def show(*_args) -> None:
        info = chosen()
        if not state["folders"]:
            text = general_text(saves.number)
        elif info is None:
            text = "Choose a tribe."
        else:
            folder = state["folders"][folder_box.current()]
            places = getattr(app, "_game_folders_for", None)
            text = page_text(folder, saves.number, info.slot, places(folder) if places else [])
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        found: list[str] = []
        for number, line in enumerate(text.split("\n"), 1):
            if line in gm.GROUPS:
                box.tag_add("group", f"{number}.0", f"{number}.end")
                box.mark_set(f"group:{line}", f"{number}.0")
                found.append(line)
            elif line.startswith(gm.SUB_BULLET):
                box.tag_add("sub", f"{number}.0", f"{number}.end")
            elif line.startswith(gm.BULLET):
                box.tag_add("bullet", f"{number}.0", f"{number}.end")
            at = line.find(gm.UNCONFIRMED)
            if at >= 0:
                box.tag_add("unconfirmed", f"{number}.{at}", f"{number}.{at + len(gm.UNCONFIRMED)}")
        box.configure(state="disabled")
        for child in links.winfo_children():
            child.destroy()
        for n, group in enumerate(found):
            ttk.Button(links, text=group, command=lambda g=group: jump(g)).grid(
                row=n // LINKS_PER_ROW, column=n % LINKS_PER_ROW, sticky="we", padx=(0, 4), pady=(0, 2))
        for column in range(LINKS_PER_ROW):
            links.columnconfigure(column, weight=1)
        record["groups"] = found

    def load_slots(*_args) -> None:
        slot_list.delete(0, "end")
        state["slots"] = []
        index = folder_box.current()
        if 0 <= index < len(state["folders"]):
            state["slots"] = vv_tribe_rename.read_slots(saves, state["folders"][index])
            for info in state["slots"]:
                slot_list.insert("end", info.label)
            first = next((n for n, info in enumerate(state["slots"]) if info.name is not None), None)
            if first is not None:
                slot_list.selection_set(first)
        show()

    def load() -> None:
        record["loaded"] = True
        state["folders"] = vv_save_backup.find_save_folders(title, documents)
        folder_box.configure(values=[folder.name for folder in state["folders"]])
        if state["folders"]:
            folder_box.current(0)
        else:
            folder_var.set("(no save folder found)")
        load_slots()

    folder_box.bind("<<ComboboxSelected>>", load_slots)
    slot_list.bind("<<ListboxSelect>>", show)
    record = {"tab": tab, "page": box, "pickers": pickers, "links": links, "load": load, "show": show,
              "jump": jump, "loaded": False, "groups": []}
    return record
