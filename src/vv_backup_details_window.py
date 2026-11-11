"""The Backups window (the owner, 2026-11-09: "ALSO SHOW VITAL STATISTICS FOR EACH BACKUP IN A WINDOW!!!"): every
backup of one game's save folder, newest first, and for the backup chosen the vital statistics of each slot save in
it (src/vv_backup_details.py).  Opened from the Tools tab (each game's row, and the Backups... button), from Restore
Saves (Details..., for the backup chosen there) and from Repair Saves & Logs.

It only reads: no save, backup, log or setting is written, so it may be open while the game runs.  The window is
resizable; the pickers and buttons keep their height and the list and the details scroll on their own, so nothing
is ever cut off and the patcher's page is not made any taller.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import vv_backup_details as details
import vv_save_backup
import vv_tool_fonts
import vv_tribe_rename
from vv_scrollbars import horizontal_bar

TITLE = "Backups"
WIDTH, HEIGHT = 900, 640
MIN_WIDTH, MIN_HEIGHT = 600, 460
INTRO = ("Every backup of the save folder, newest first (Back Up Saves' and the ones each tool makes first, such as "
         "\"(before restore)\" and \"(before repair re-arm)\"). Choose one to see, for each save slot in it, the "
         "tribe, population, food, tech points, technology levels, game speed and when it was last saved and last "
         "played. A value that cannot be read says \"unknown\". This window only reads: nothing is changed.")


def _game_number(game) -> int | None:
    """1-5 from a game number, a title, or a build (anything with .title)."""
    if isinstance(game, int):
        return game if 1 <= game <= 5 else None
    title = getattr(game, "title", game)
    if not isinstance(title, str):
        return None
    try:
        return vv_tribe_rename.game_for_title(title).number
    except vv_tribe_rename.RenameError:
        return None


def show_backup_details(parent, game=None, save_folder: Path | None = None, backup: Path | None = None,
                        documents: Path | None = None) -> tk.Toplevel | None:
    """The window, at ``game`` (1-5, a title or a build; the first game when None), ``save_folder`` (else the
    game's first Modded save folder) and ``backup`` (a backup folder in it; else the newest).  Read-only."""
    if documents is None:
        documents = vv_save_backup.documents_folder()
    titles = [item.title for item in vv_tribe_rename.GAMES]
    number = _game_number(game)
    if number is None and save_folder is not None:
        number = vv_save_backup.game_number(Path(save_folder))
    number = number or 1

    window = tk.Toplevel(parent)
    window.title(f"{TITLE} - {titles[number - 1].removeprefix('Virtual Villagers - ')}")
    window.transient(parent)
    width = min(WIDTH, max(MIN_WIDTH, window.winfo_screenwidth() - 80))
    height = min(HEIGHT, max(MIN_HEIGHT, window.winfo_screenheight() - 120))
    window.geometry(f"{width}x{height}")
    window.minsize(MIN_WIDTH, MIN_HEIGHT)
    window.resizable(True, True)
    fonts = vv_tool_fonts.fonts(window)

    outer = ttk.Frame(window, padding=12)
    outer.pack(fill="both", expand=True)
    top = ttk.Frame(outer)
    intro = ttk.Label(top, text=INTRO, wraplength=width - 60, justify="left")
    intro.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    top.bind("<Configure>", lambda event: intro.configure(wraplength=max(200, event.width - 8)))
    game_var, folder_var = tk.StringVar(master=window, value=titles[number - 1]), tk.StringVar(master=window)
    ttk.Label(top, text="Game:").grid(row=1, column=0, sticky="w")
    game_box = ttk.Combobox(top, textvariable=game_var, values=titles, state="readonly", width=48)
    game_box.grid(row=1, column=1, sticky="we", pady=2)
    ttk.Label(top, text="Save folder:").grid(row=2, column=0, sticky="w", padx=(0, 8))
    folder_box = ttk.Combobox(top, textvariable=folder_var, state="readonly", width=48)
    folder_box.grid(row=2, column=1, sticky="we", pady=2)
    top.columnconfigure(1, weight=1)

    buttons = ttk.Frame(outer)
    # The list and the details share the height in a paned window, each with a minimum of its own (Codex, #751:
    # at the smallest size, or with large fonts, a fixed list left the details no room); the sash moves the split.
    line = max(12, fonts["text"].metrics("linespace"))
    paned = tk.PanedWindow(outer, orient="vertical", sashwidth=6, sashrelief="flat", borderwidth=0,
                           background=ttk.Style(window).lookup("TFrame", "background"))
    list_pane = ttk.Frame(paned)
    ttk.Label(list_pane, text="Backups (newest first):", font=fonts["bold"]).pack(anchor="w", pady=(8, 2))
    list_row = ttk.Frame(list_pane)
    list_row.pack(fill="both", expand=True)
    listbox = tk.Listbox(list_row, height=5, exportselection=False, font=fonts["text"])
    list_bar = ttk.Scrollbar(list_row, orient="vertical", command=listbox.yview)
    listbox.configure(yscrollcommand=list_bar.set)
    list_bar.pack(side="right", fill="y")
    listbox.pack(side="left", fill="both", expand=True)
    horizontal_bar(listbox)                     # a long backup name scrolls sideways
    body = ttk.Frame(paned)
    text = vv_tool_fonts.tool_text(body, wrap="word", height=8, relief="flat", padx=8, pady=6)
    text_bar = ttk.Scrollbar(body, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=text_bar.set)
    text_bar.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    text.tag_configure("heading", font=fonts["heading"])
    text.tag_configure("slot", font=fonts["bold"])
    paned.add(list_pane, minsize=fonts["bold"].metrics("linespace") + 10 + 3 * line, stretch="always")
    paned.add(body, minsize=7 * line, stretch="always")
    # Packed in this order, the buttons and then the list and details get their room first; the intro and the
    # pickers above them take what is left.
    buttons.pack(side="bottom", fill="x", pady=(8, 0))
    paned.pack(side="bottom", fill="both", expand=True, pady=(0, 0))
    top.pack(side="top", fill="x")

    state: dict = {"folders": [], "backups": [], "read": {}, "want": Path(backup) if backup else None,
                   "folder": Path(save_folder) if save_folder else None}
    window.backups_state = state            # for the tests
    window.backups_list = listbox
    window.backups_text = text
    window.backups_text_bar = text_bar
    window.backups_paned = paned
    window.backups_game = game_var
    window.backups_folder = folder_box

    def show(lines: list[str]) -> None:
        text.configure(state="normal")
        text.delete("1.0", "end")
        for line in lines:
            tag = ("heading" if line.startswith("Backup: ") else
                   "slot" if line.startswith("Save ") else ())
            text.insert("end", line + "\n", tag)
        text.configure(state="disabled")

    def game_now() -> int:
        return vv_tribe_rename.game_for_title(game_var.get()).number

    def load_folders(_event=None) -> None:
        title = game_var.get()
        window.title(f"{TITLE} - {title.removeprefix('Virtual Villagers - ')}")
        folders = vv_save_backup.find_save_folders(title, documents) if documents is not None else []
        wanted = state.pop("folder", None)
        if wanted is not None and all(Path(f) != wanted for f in folders):
            folders = [wanted] + list(folders)
        state["folders"] = list(folders)
        folder_box.configure(values=[str(f) for f in folders])
        if folders:
            index = next((n for n, f in enumerate(folders) if Path(f) == wanted), 0)
            folder_box.current(index)
        else:
            folder_var.set("")
        load_backups()

    def load_backups(_event=None) -> None:
        listbox.delete(0, "end")
        state["backups"] = []
        index = folder_box.current()
        if index < 0 or not state["folders"]:
            show(["No save folder of this game was found in Documents\\LDW."
                  if documents is not None else
                  "Windows did not report where your Documents folder is, so the save folders cannot be found."])
            return
        try:
            found = vv_save_backup.list_backups(Path(state["folders"][index]))
        except OSError as exc:
            show([f"The backups could not be listed ({exc.strerror or exc})."])
            return
        state["backups"] = found
        for info in found:
            listbox.insert("end", details.summary(info))
        if not found:
            show(["This save folder has no backups yet. Use Back Up Saves to make one."])
            return
        wanted = state.pop("want", None)
        chosen = next((n for n, info in enumerate(found) if wanted is not None and Path(info.path) == wanted), 0)
        listbox.selection_clear(0, "end")
        listbox.selection_set(chosen)
        listbox.see(chosen)
        selected()

    def selected(_event=None) -> None:
        chosen = listbox.curselection()
        if not chosen or chosen[0] >= len(state["backups"]):
            return
        info = state["backups"][chosen[0]]
        key = (game_now(), str(info.path))
        if key not in state["read"]:
            window.configure(cursor="watch")
            window.update_idletasks()
            try:
                state["read"][key] = details.backup_lines(details.read_backup(game_now(), info))
            finally:
                window.configure(cursor="")
        show(state["read"][key])

    def refresh() -> None:
        chosen = listbox.curselection()
        if chosen and chosen[0] < len(state["backups"]):
            state["want"] = Path(state["backups"][chosen[0]].path)
        state["read"].clear()
        index = folder_box.current()
        if index >= 0 and state["folders"]:
            state["folder"] = Path(state["folders"][index])
        load_folders()

    game_box.bind("<<ComboboxSelected>>", load_folders)
    folder_box.bind("<<ComboboxSelected>>", load_backups)
    listbox.bind("<<ListboxSelect>>", selected)
    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left")
    ttk.Button(buttons, text="Close", command=window.destroy).pack(side="right")
    window.backups_refresh = refresh
    window.backups_select = selected
    window.protocol("WM_DELETE_WINDOW", window.destroy)
    window.bind("<Escape>", lambda _event: window.destroy())
    try:
        load_folders()
    except Exception as exc:  # noqa: BLE001 -- never leave a half-built window behind
        window.destroy()
        messagebox.showerror(TITLE, f"The backups could not be read ({exc}).", parent=parent)
        return None
    window.update_idletasks()
    # The smallest size shows everything at the fonts in use (large system fonts make it larger), up to the screen.
    window.minsize(MIN_WIDTH, max(MIN_HEIGHT, min(outer.winfo_reqheight(), window.winfo_screenheight() - 80)))
    window.grab_set()                       # the patcher's Windows-way hold (vv_fun_patcher_gui._hold)
    listbox.focus_set()
    return window
