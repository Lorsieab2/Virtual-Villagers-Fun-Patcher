"""The Game Mechanics window (the owner, 2026-10-22): a tool of its own on the Tools tab.

One tab for each game (the owner, 2026-10-23).  In each, pick a save folder and a tribe; the tab shows that
save's hidden game rules as src/vv_game_mechanics.py reads them, grouped, in real time only, with a link to
each group at the top of the page.  A game with no save found still shows its general rules.  It only reads:
no save, log, data file, report or backup is written (unlike the tribe pickers that run the reconciliation,
it runs nothing else), so it may be open while the game runs -- it then shows the save as last written.

The window is resizable: the intro, each tab's pickers and links and the buttons keep their height, and each
tab's page is a Text box with its own scroll bar that takes the rest, so nothing is ever cut off
(tests/test_game_mechanics.py, tests/test_window_scrollbars.py).

LIVE (the owner, 2026-10-24; docs/game-mechanics-window.md):
  * A fact with a moment still to come (Fact.due) shows its date and a countdown right after it on the same
    bullet.  ONE timer (TICK_MS) ticks every countdown on every tab and drives Auto-refresh; it reads no file.
  * Refresh reads every source again -- the save, the patcher's logs, the save folder's .dat files and logs,
    the game's exe as it is now -- and restarts the countdowns, keeping the tab, the save folder, the tribe and
    the scroll position.  The other tabs are read again when next shown.
  * Auto-refresh (off by default) refreshes every AUTO_REFRESH_SECONDS.
  * The top of each tab says when the save was last written; when the game for it is running (found read-only
    in the list of running programs) it says the values are from that last save -- the games save only on a
    clean quit.
  * Browse... beside the save folder picks the game's exe, kept per save folder in the patcher's own settings
    (app.game_mechanics_exes, saved by app._save_settings), never in the save.
  * Closing cancels the timer and every callback the window scheduled before it is destroyed (the stale
    after-callback bug fixed in the Virtual Families repos).
`clock`, `PROCESSES` and `ask_exe` are module names so the tests can give a fake clock, a fake process list
and a fake file dialog.
"""
from __future__ import annotations

import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import vv_game_mechanics as gm
import vv_save_backup
import vv_tribe_rename

TITLE = gm.TITLE
INTRO = ("For the curious: the hidden rules of each game -- its food sources, refills and more -- worked out from "
         "a village's save, at the save's game speed, with the patches in the game that change them. All times "
         "are real times. It only reads: nothing is changed, so the game may be running.")
WIDTH, HEIGHT = 900, 720
LABEL_RED = "#b00020"
MIN_WIDTH, MIN_HEIGHT = 600, 600
LINKS_PER_ROW = 5
TICK_MS = 1000                  # the one timer: every countdown, and Auto-refresh
AUTO_REFRESH_SECONDS = 30
AUTO_REFRESH = "Auto-refresh every 30 seconds"
RUNNING_RED = LABEL_RED
SETTINGS_KEY = "game_mechanics_exes"

clock = time.time               # real now (Unix seconds); the tests replace it
PROCESSES = None                # a vv_save_backup.ProcessController; None: Windows' own list


def _ask_exe(parent, folder: Path, current: Path | None) -> str:
    start = current.parent if current is not None and current.parent.is_dir() else Path.home()
    return filedialog.askopenfilename(
        parent=parent, title=f"The game that saves into {folder.name}",
        initialdir=str(start), initialfile=vv_save_backup.game_exe_name(folder),
        filetypes=[("Programs", "*.exe"), ("All files", "*.*")])


ask_exe = _ask_exe


def page(folder: Path, game: int, slot: int, game_folders: list[Path], exe: Path | None = None,
         now: float | None = None) -> tuple[str, list[gm.Countdown]]:
    """The page for one save slot and its countdowns; a save or file it cannot read is said on the page."""
    now = clock() if now is None else now
    try:
        return gm.render_live(gm.read(folder, game, slot, game_folders, now=now, exe=exe), now)
    except Exception as exc:  # noqa: BLE001 -- shown, never fatal: the window only reads
        return f"The game mechanics could not be read ({exc}). Nothing was changed.", []


def page_text(folder: Path, game: int, slot: int, game_folders: list[Path]) -> str:
    """The page for one save slot as text."""
    return page(folder, game, slot, game_folders)[0]


def general_text(game: int) -> str:
    """A game's general rules, when no save of it is found."""
    try:
        return gm.GENERAL_NOTE + "\n\n" + gm.render(gm.general(game, clock()))
    except Exception as exc:  # noqa: BLE001 -- shown, never fatal
        return f"The game mechanics could not be shown ({exc})."


def chosen_exe(app, folder: Path) -> Path | None:
    """The game exe the player chose with Browse... for `folder`, from the patcher's settings."""
    store = getattr(app, SETTINGS_KEY, None)
    value = store.get(str(folder)) if isinstance(store, dict) else None
    return Path(value) if isinstance(value, str) and value else None


def remember_exe(app, folder: Path, exe: Path) -> None:
    """Keep the chosen exe for `folder` in the patcher's own settings file (never the save)."""
    store = getattr(app, SETTINGS_KEY, None)
    if not isinstance(store, dict):
        store = {}
        setattr(app, SETTINGS_KEY, store)
    store[str(folder)] = str(exe)
    save = getattr(app, "_save_settings", None)
    if callable(save):
        try:
            save()
        except OSError:
            pass                 # the choice still holds while the patcher is open


def game_running(save_folder: Path, exe: Path | None = None, processes=None) -> bool:
    """Whether the game that saves into `save_folder` is running: a program named as the save folder's game, or
    as the chosen exe, in the list of running programs.  Only looks: nothing is opened, paused or closed."""
    names = {vv_save_backup.game_exe_name(Path(save_folder)).casefold()}
    if exe is not None:
        names.add(Path(exe).name.casefold())
    try:
        controller = processes if processes is not None else (PROCESSES or vv_save_backup.WindowsProcesses())
        return any(controller.find(name) for name in sorted(names))
    except (OSError, vv_save_backup.BackupError, AttributeError, ValueError):
        return False


def save_status(save: Path | None, running: bool) -> str:
    """The line at the top of a tab: when the save was last written, and whether the values may be behind."""
    if save is None:
        return ""
    try:
        written = gm.when(save.stat().st_mtime)
    except OSError:
        return f"The save {save.name} could not be read."
    if running:
        return (f"The game is running: values are from the last save at {written}. The games save only when "
                "they are closed normally.")
    return f"The save was last written {written}."


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
    jobs: dict[str, str] = {}               # every callback the window has scheduled, by name
    live = {"last_refresh": clock(), "closed": False}
    auto_var = tk.BooleanVar(master=window, value=False)
    window.mechanics_tabs = tabs            # for the tests
    window.mechanics_notebook = notebook
    window.mechanics_parts = (top, intro, buttons, label_note)
    window.mechanics_jobs = jobs
    window.mechanics_auto = auto_var

    for item in app.builds:
        saves = vv_tribe_rename.game_for_title(item.title)
        tabs[saves.number] = _game_tab(window, notebook, app, item.title, saves, documents, bold)

    first = vv_tribe_rename.game_for_title(build.title).number if build is not None else min(tabs)

    def current() -> int:
        return list(tabs)[notebook.index(notebook.select())]

    def changed(_event=None) -> None:
        number = current()
        if not tabs[number]["loaded"]:
            tabs[number]["load"]()
        elif tabs[number]["stale"]:
            tabs[number]["reload"]()

    notebook.bind("<<NotebookTabChanged>>", changed)
    notebook.select(list(tabs).index(first))
    changed()

    def refresh() -> None:
        """Read every source again for the tab shown; the others are read again when next shown."""
        if live["closed"]:
            return
        live["last_refresh"] = clock()
        shown = current()
        for number, record in tabs.items():
            if number != shown and record["loaded"]:
                record["stale"] = True
        record = tabs[shown]
        record["reload"]() if record["loaded"] else record["load"]()

    def tick() -> None:
        """The one timer: every countdown on every tab, then Auto-refresh when it is due."""
        job = jobs.pop("tick", None)
        if job is not None:                 # a tick called early (tests) never leaves the timer's own behind
            try:
                window.after_cancel(job)
            except tk.TclError:
                pass
        if live["closed"]:
            return
        now = clock()
        for record in tabs.values():
            record["tick"](now)
        if auto_var.get() and now - live["last_refresh"] >= AUTO_REFRESH_SECONDS:
            refresh()
        schedule()

    def schedule() -> None:
        if not live["closed"] and "tick" not in jobs:
            jobs["tick"] = window.after(TICK_MS, tick)

    def auto_changed() -> None:
        live["last_refresh"] = clock()      # the first automatic refresh is a full 30 seconds after ticking it

    def cancel_all() -> None:
        """Cancel every callback the window scheduled, and any Tk left for its widgets, before it goes."""
        live["closed"] = True
        for name in list(jobs):
            try:
                window.after_cancel(jobs.pop(name))
            except tk.TclError:
                pass
        path = str(window)
        try:
            pending = window.tk.splitlist(window.tk.call("after", "info"))
        except tk.TclError:
            pending = ()
        for job in pending:
            try:
                script = window.tk.call("after", "info", job)
                words = " ".join(str(part) for part in window.tk.splitlist(script))
            except tk.TclError:
                continue
            if path + "." in words or words.endswith(path) or f"{path} " in words:
                try:
                    window.tk.call("after", "cancel", job)
                except tk.TclError:
                    pass

    def close() -> None:
        cancel_all()
        window.destroy()

    def destroyed(event) -> None:
        if event.widget is window:
            cancel_all()

    window.bind("<Destroy>", destroyed, add="+")
    window.protocol("WM_DELETE_WINDOW", close)
    ttk.Button(buttons, text="Refresh", command=refresh).pack(side="left")
    auto_button = ttk.Checkbutton(buttons, text=AUTO_REFRESH, variable=auto_var, command=auto_changed)
    auto_button.pack(side="left", padx=(8, 0))
    window.mechanics_auto_button = auto_button
    ttk.Button(buttons, text="Close", command=close).pack(side="right")
    window.mechanics_refresh = refresh
    window.mechanics_tick = tick
    window.mechanics_close = close
    schedule()
    return window


def _game_tab(window, notebook, app, title: str, saves, documents, bold) -> dict:
    """One game's tab: its save picker, links to its groups, and its page."""
    tab = ttk.Frame(notebook, padding=8)
    notebook.add(tab, text=title.removeprefix("Virtual Villagers - ").replace("Virtual Villagers", "A New Home"))
    pickers = ttk.Frame(tab)
    pickers.pack(fill="x")
    folder_var = tk.StringVar(master=window)
    ttk.Label(pickers, text="Save folder:").grid(row=0, column=0, sticky="w")
    folder_box = ttk.Combobox(pickers, textvariable=folder_var, state="readonly", width=48)
    folder_box.grid(row=0, column=1, sticky="we", pady=2)
    browse = ttk.Button(pickers, text="Browse...")
    browse.grid(row=0, column=2, sticky="w", padx=(6, 0), pady=2)
    ttk.Label(pickers, text="Tribe:").grid(row=1, column=0, sticky="nw", pady=(4, 0))
    slot_list = tk.Listbox(pickers, height=3, width=60, exportselection=False)
    slot_list.grid(row=1, column=1, columnspan=2, sticky="we", pady=(4, 2))
    pickers.columnconfigure(1, weight=1)
    status = ttk.Label(tab, text="", justify="left", wraplength=MIN_WIDTH - 60)
    status.pack(fill="x", anchor="w", pady=(4, 0))
    tab.bind("<Configure>", lambda event: status.configure(wraplength=max(200, event.width - 24)), add="+")
    links = ttk.Frame(tab)
    links.pack(fill="x", pady=(6, 0))
    page_frame = ttk.Frame(tab)
    page_frame.pack(fill="both", expand=True, pady=(6, 0))
    box = tk.Text(page_frame, wrap="word", height=1)
    bar = ttk.Scrollbar(page_frame, orient="vertical", command=box.yview)
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

    def folder() -> Path | None:
        index = folder_box.current()
        return state["folders"][index] if 0 <= index < len(state["folders"]) else None

    def jump(group: str) -> None:
        index = box.index(f"group:{group}")
        box.yview(index)

    def show(*_args) -> None:
        info = chosen()
        where = folder()
        spans: list[gm.Countdown] = []
        save = None
        exe = chosen_exe(app, where) if where is not None else None
        if not state["folders"]:
            text = general_text(saves.number)
            status.configure(text="No save folder was found for this game: these are its general rules.",
                             foreground="")
        elif info is None:
            text = "Choose a tribe."
            status.configure(text="", foreground="")
        else:
            places = getattr(app, "_game_folders_for", None)
            text, spans = page(where, saves.number, info.slot, places(where) if places else [], exe)
            save = gm.save_path(where, saves.number, info.slot)
        if save is not None:
            running = game_running(where, exe)
            status.configure(text=save_status(save, running), foreground=RUNNING_RED if running else "")
            record["running"] = running
        else:
            record["running"] = False
        box.configure(state="normal")
        for tag, _due in record["countdowns"]:
            box.tag_delete(tag)
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
        countdowns = []
        for n, span in enumerate(spans):
            tag = f"due{n}"
            box.tag_add(tag, f"{span.line}.{span.column}", f"{span.line}.{span.column + span.length}")
            countdowns.append((tag, span.due))
        record["countdowns"] = countdowns
        box.configure(state="disabled")
        for child in links.winfo_children():
            child.destroy()
        for n, group in enumerate(found):
            ttk.Button(links, text=group, command=lambda g=group: jump(g)).grid(
                row=n // LINKS_PER_ROW, column=n % LINKS_PER_ROW, sticky="we", padx=(0, 4), pady=(0, 2))
        for column in range(LINKS_PER_ROW):
            links.columnconfigure(column, weight=1)
        record["groups"] = found
        record["stale"] = False

    def tick(now: float) -> None:
        """Each countdown's words at `now`, in place; nothing is read."""
        if not record["countdowns"]:
            return
        box.configure(state="normal")
        try:
            for tag, due in record["countdowns"]:
                ranges = box.tag_ranges(tag)
                if not ranges:
                    continue
                start, end = str(ranges[0]), str(ranges[-1])
                words = gm.countdown_span(due, now)
                if box.get(start, end) == words:
                    continue
                tags = tuple(name for name in box.tag_names(start) if name != "sel")
                box.insert(start, words, tags)
                box.delete(f"{start} + {len(words)} chars", f"{end} + {len(words)} chars")
        finally:
            box.configure(state="disabled")

    def load_slots(*_args, keep_slot: int | None = None) -> None:
        slot_list.delete(0, "end")
        state["slots"] = []
        where = folder()
        if where is not None:
            state["slots"] = vv_tribe_rename.read_slots(saves, where)
            for info in state["slots"]:
                slot_list.insert("end", info.label)
            named = [n for n, info in enumerate(state["slots"]) if info.name is not None]
            kept = next((n for n in named if state["slots"][n].slot == keep_slot), None)
            pick = kept if kept is not None else (named[0] if named else None)
            if pick is not None:
                slot_list.selection_set(pick)
                slot_list.see(pick)
        browse.configure(state="normal" if where is not None else "disabled")
        show()

    def find_folders(keep: Path | None = None) -> None:
        state["folders"] = vv_save_backup.find_save_folders(title, documents)
        folder_box.configure(values=[item.name for item in state["folders"]])
        if state["folders"]:
            index = next((n for n, item in enumerate(state["folders"]) if keep is not None and item == keep), 0)
            folder_box.current(index)
        else:
            folder_var.set("(no save folder found)")

    def load() -> None:
        record["loaded"] = True
        find_folders()
        load_slots()

    def reload() -> None:
        """Refresh: every source read again; the folder, tribe and scroll position kept."""
        if not record["loaded"]:
            load()
            return
        try:
            top_line = box.index("@0,0")
        except tk.TclError:
            top_line = None
        fraction = box.yview()[0]
        keep = folder()
        info = chosen()
        find_folders(keep)
        load_slots(keep_slot=info.slot if info is not None else None)
        box.update_idletasks()
        if top_line is not None and top_line != "1.0":
            box.yview(top_line)
        else:
            box.yview_moveto(fraction)

    def browse_exe() -> None:
        where = folder()
        if where is None:
            return
        picked = ask_exe(window, where, chosen_exe(app, where))
        if not picked:
            return
        exe = Path(picked)
        if not exe.is_file() or exe.suffix.lower() != ".exe":
            messagebox.showerror(TITLE, f"{exe} is not a program (.exe). Nothing was changed.", parent=window)
            return
        remember_exe(app, where, exe)
        reload()

    browse.configure(command=browse_exe, state="disabled")
    folder_box.bind("<<ComboboxSelected>>", load_slots)
    slot_list.bind("<<ListboxSelect>>", show)
    record = {"tab": tab, "page": box, "pickers": pickers, "links": links, "status": status, "browse": browse,
              "load": load, "reload": reload, "show": show, "tick": tick, "jump": jump, "loaded": False,
              "stale": False, "groups": [], "countdowns": [], "running": False, "folder": folder,
              "slots": slot_list, "browse_exe": browse_exe}
    return record
