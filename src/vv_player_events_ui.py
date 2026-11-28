"""The Player Events part of each game's Island Events section (v1.35.97; the owner, 2026-11-15).

Buttons to add the player's own event files, open their folder, check a file (every problem with its line), preview
an event as the game would show it, copy the AI prompt and the owner's tone reference; the number of events the
prompt asks for, the player's own rules and themes (an editable box saved in the game's folder), the rules the
importer enforces, the favoured themes, and the prompt itself in a read-only box whose text can be selected and
copied.  Everything is kept small (the page-height guard): the long texts sit in boxes of a few lines that scroll.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import vv_player_events as pe
from vv_scrollbars import horizontal_bar

ASK_FILES = filedialog.askopenfilenames
ASK_FILE = filedialog.askopenfilename
SHOW_INFO = messagebox.showinfo
SHOW_ERROR = messagebox.showerror
ASK_YES_NO = messagebox.askyesno
ASK_INTEGER = simpledialog.askinteger

INTRO = ("Your own island events: put text files in this game's Player Events folder (or use Add Event Files...). "
         "At patch time they join the Isola Grand Event Collection and come in the normal draw like any event, "
         "with the content filters, content notes and the rule that below 61 villagers no event takes more than 2. "
         "Copy AI Prompt gives a prompt to paste into any AI; it answers with a file in exactly this format. "
         "docs/player-events-format.md explains every line.")


def _open(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _copy(widget, text: str) -> None:
    widget.clipboard_clear()
    widget.clipboard_append(text)
    widget.update_idletasks()


def read_only(text: tk.Text) -> None:
    """A Text the player can select in and copy from (Ctrl+C, Ctrl+A, the menu) but not change."""
    def key(event):
        ctrl = event.state & 0x4
        if ctrl and event.keysym.lower() in ("c", "a", "insert"):
            if event.keysym.lower() == "a":
                text.tag_add("sel", "1.0", "end-1c")
                return "break"
            return None
        if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "Shift_L", "Shift_R",
                            "Control_L", "Control_R"):
            return None
        return "break"
    text.bind("<Key>", key)
    text.bind("<<Paste>>", lambda _e: "break")
    text.bind("<<Cut>>", lambda _e: "break")
    menu = tk.Menu(text, tearoff=False)
    menu.add_command(label="Copy", command=lambda: text.event_generate("<<Copy>>"))
    menu.add_command(label="Select All", command=lambda: text.tag_add("sel", "1.0", "end-1c"))
    text.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))


def editable(text: tk.Text) -> None:
    menu = tk.Menu(text, tearoff=False)
    for label, ev in (("Cut", "<<Cut>>"), ("Copy", "<<Copy>>"), ("Paste", "<<Paste>>")):
        menu.add_command(label=label, command=lambda ev=ev: text.event_generate(ev))
    menu.add_command(label="Select All", command=lambda: text.tag_add("sel", "1.0", "end-1c"))
    text.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))


def report_window(parent, title: str, body: str) -> tk.Toplevel:
    """A small window with a long text (a check's problems, a preview) the player can scroll, select and copy."""
    top = tk.Toplevel(parent)
    top.title(title)
    top.transient(parent.winfo_toplevel())
    top.geometry("760x520")
    frame = ttk.Frame(top, padding=8)
    frame.pack(fill="both", expand=True)
    text = tk.Text(frame, wrap="word", height=24, width=90)
    bar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    text.insert("1.0", body)
    read_only(text)
    buttons = ttk.Frame(top, padding=(8, 0, 8, 8))
    buttons.pack(fill="x")
    ttk.Button(buttons, text="Close", command=top.destroy).pack(side="right")
    ttk.Button(buttons, text="Copy All", command=lambda: _copy(top, text.get("1.0", "end-1c"))).pack(
        side="right", padx=(0, 6))
    top._text = text                     # noqa: SLF001 (a preview's Again button rewrites it)
    top._buttons = buttons               # noqa: SLF001
    top.grab_set()                       # the patcher's _hold: the Windows way
    return top


class PlayerEventsSection:
    """The section's widgets and actions for one game."""

    def __init__(self, parent, game: int, requirement_font=None, root: Path | None = None) -> None:
        self.game = game
        self.root = root
        self.folder = pe.ensure_game_folder(game, root)
        self.settings = pe.load_settings(game, root)
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="x", pady=(10, 0))
        head = ttk.Frame(self.frame)
        head.pack(fill="x")
        ttk.Label(head, text="Player Events", font=requirement_font).pack(side="left")
        self.enabled = tk.BooleanVar(master=self.frame, value=self.settings.enabled)
        ttk.Checkbutton(head, text="Install my player events when patching", variable=self.enabled,
                        command=self.save).pack(side="left", padx=(12, 0))
        ttk.Label(self.frame, text=INTRO, wraplength=640, justify="left").pack(anchor="w", pady=(2, 4))
        row1 = ttk.Frame(self.frame)
        row1.pack(fill="x", pady=(0, 2))
        for words, command in (("Add Event Files...", self.add_files), ("Open Player Events Folder", self.open_folder),
                               ("Check File...", self.check_file), ("Preview...", self.preview_file)):
            ttk.Button(row1, text=words, command=command).pack(side="left", padx=(0, 4))
        row2 = ttk.Frame(self.frame)
        row2.pack(fill="x", pady=(0, 4))
        for words, command in (("Copy AI Prompt", self.copy_prompt), ("Copy Reference Events", self.copy_reference),
                               ("Open Reference Folder", self.open_reference),
                               ("Choose Reference File...", self.choose_reference)):
            ttk.Button(row2, text=words, command=command).pack(side="left", padx=(0, 4))
        row3 = ttk.Frame(self.frame)
        row3.pack(fill="x", pady=(0, 4))
        row4 = ttk.Frame(self.frame)
        row4.pack(fill="x", pady=(0, 4))
        for words, name in (("Style Guide", pe.STYLE_NAME), ("Themes List", pe.THEMES_NAME),
                            ("Outcomes List", pe.OUTCOMES_NAME), ("Example Events", pe.EXAMPLE_NAME)):
            ttk.Button(row3, text=f"Copy {words}", command=lambda n=name: self.copy_owner(n)).pack(
                side="left", padx=(0, 4))
            ttk.Button(row4, text=f"Show {words}", command=lambda n=name: self.show_owner(n)).pack(
                side="left", padx=(0, 4))
        ttk.Label(self.frame, text="The key: Lorsieab2's handwritten events (Copy Reference Events) + 20 example "
                                   "events (Copy Example Events); the style guide is drawn from them. With the themes "
                                   "and outcomes lists they are the defaults the AI prompt names: give them to the AI "
                                   "with it. The example events are reference only, never installed as events.",
                  wraplength=640, justify="left").pack(anchor="w")
        self.reference_label = ttk.Label(self.frame, text="", wraplength=640, justify="left")
        self.reference_label.pack(anchor="w")
        count_row = ttk.Frame(self.frame)
        count_row.pack(fill="x", pady=(4, 2))
        ttk.Label(count_row, text="Events the prompt asks for:").pack(side="left")
        self.count = tk.IntVar(master=self.frame, value=self.settings.count)
        spin = ttk.Spinbox(count_row, from_=1, to=50, width=5, textvariable=self.count, command=self.save)
        spin.pack(side="left", padx=(6, 0))
        spin.bind("<FocusOut>", lambda _e: self.save())
        # Your Rules and Themes: free text for the prompt; a "Themes:" line lists the player's themes.
        ttk.Label(self.frame, text="Your Rules and Themes (added to the AI prompt; a line \"Themes: a, b\" lists your "
                                   "themes):", wraplength=640, justify="left").pack(anchor="w", pady=(4, 0))
        rules_box = ttk.Frame(self.frame)
        rules_box.pack(fill="x")
        self.rules = tk.Text(rules_box, height=4, width=80, wrap="word", undo=True)
        bar = ttk.Scrollbar(rules_box, orient="vertical", command=self.rules.yview)
        self.rules.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.rules.pack(side="left", fill="x", expand=True)
        self.rules.insert("1.0", pe.read_rules(game, root))
        self.rules.edit_modified(False)
        editable(self.rules)
        self.rules.bind("<FocusOut>", lambda _e: self.save_rules())
        ticks = ttk.Frame(self.frame)
        ticks.pack(fill="x", pady=(4, 0))
        ttk.Label(ticks, text="Rules the patcher enforces (an event that breaks one is left out):").grid(
            row=0, column=0, columnspan=2, sticky="w")
        self.rule_vars: dict[str, tk.BooleanVar] = {}
        for k, (key, (words, _kinds)) in enumerate(pe.RULES.items()):
            var = tk.BooleanVar(master=self.frame, value=bool(self.settings.rules.get(key)))
            self.rule_vars[key] = var
            ttk.Checkbutton(ticks, text=words, variable=var, command=self.save).grid(
                row=1 + k // 2, column=k % 2, sticky="w", padx=(0, 12))
        self.theme_frame = ttk.Frame(self.frame)
        self.theme_frame.pack(fill="x", pady=(4, 0))
        self.only_mine = tk.BooleanVar(master=self.frame, value=self.settings.only_my_themes)
        self.theme_names: list[str] = []
        self.theme_list: tk.Listbox | None = None
        self.show_themes()
        ttk.Label(self.frame, text="The AI prompt (select and copy, or use Copy AI Prompt):").pack(anchor="w",
                                                                                                pady=(6, 0))
        prompt_box = ttk.Frame(self.frame)
        prompt_box.pack(fill="x")
        self.prompt = tk.Text(prompt_box, height=8, width=80, wrap="word")
        pbar = ttk.Scrollbar(prompt_box, orient="vertical", command=self.prompt.yview)
        self.prompt.configure(yscrollcommand=pbar.set)
        pbar.pack(side="right", fill="y")
        self.prompt.pack(side="left", fill="x", expand=True)
        read_only(self.prompt)
        self.files_label = ttk.Label(self.frame, text="", wraplength=640, justify="left")
        self.files_label.pack(anchor="w", pady=(4, 0))
        self.refresh()

    # ---- State ----------------------------------------------------------------------------------------------------

    def save(self) -> None:
        try:
            self.settings.count = max(1, min(50, int(self.count.get())))
        except (tk.TclError, ValueError):
            self.settings.count = 1
        self.settings.enabled = bool(self.enabled.get())
        self.settings.rules = {k: bool(v.get()) for k, v in self.rule_vars.items()}
        if self.theme_list is not None:
            self.settings.favour = [self.theme_names[i] for i in self.theme_list.curselection()]
        self.settings.only_my_themes = bool(self.only_mine.get())
        try:
            pe.save_settings(self.game, self.settings, self.root)
        except OSError as exc:
            SHOW_ERROR("Player Events", f"The settings could not be saved: {exc}", parent=self.frame)
        self.show_prompt()

    def save_rules(self) -> None:
        if not self.rules.edit_modified():
            return
        try:
            pe.write_rules(self.game, self.rules.get("1.0", "end-1c"), self.root)
        except OSError as exc:
            SHOW_ERROR("Player Events", f"Your rules could not be saved: {exc}", parent=self.frame)
            return
        self.rules.edit_modified(False)
        self.show_themes()
        self.show_prompt()

    def prompt_text(self) -> str:
        self.save_rules()
        return pe.ai_prompt(self.game, self.settings, self.rules.get("1.0", "end-1c"))

    def show_prompt(self) -> None:
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", pe.ai_prompt(self.game, self.settings, self.rules.get("1.0", "end-1c")))

    def themes_found(self) -> list[str]:
        themes = pe.rules_themes(self.rules.get("1.0", "end-1c"))
        for path in sorted(self.folder.glob("*.txt")):
            if path.name in (pe.RULES_NAME,):
                continue
            items, _p = pe.parse_file(path)
            for it in items:
                themes += it.meta.get("themes", []) if it.kind == "event" else (it.piece or {}).get("themes", [])
        return list(dict.fromkeys(t.lower() for t in themes if t))

    def show_themes(self) -> None:
        """The "favour these themes" picker: your own themes (your rules' Themes line, your files' Themes lines), then
        every theme of the owner's themes list -- a short list that scrolls, several may be chosen."""
        chosen = set(self.settings.favour) if self.theme_list is None else \
            {self.theme_names[i] for i in self.theme_list.curselection()}
        for w in self.theme_frame.winfo_children():
            w.destroy()
        self.theme_list = None
        mine = self.themes_found()
        self.theme_names = list(dict.fromkeys(mine + pe.default_themes() + sorted(chosen)))
        ttk.Label(self.theme_frame, text=f"Favour these themes (click to choose several; their player events and "
                                         f"pieces come {pe.THEME_FAVOUR} times as often). Yours first, then the "
                                         "owner's themes list:", wraplength=640, justify="left").pack(anchor="w")
        box = ttk.Frame(self.theme_frame)
        box.pack(fill="x")
        self.theme_list = tk.Listbox(box, selectmode="multiple", height=5, exportselection=False, width=60)
        bar = ttk.Scrollbar(box, orient="vertical", command=self.theme_list.yview)
        self.theme_list.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.theme_list.pack(side="left", fill="x", expand=True)
        horizontal_bar(self.theme_list)              # a long theme scrolls sideways
        for k, t in enumerate(self.theme_names):
            self.theme_list.insert("end", t)
            if t in chosen:
                self.theme_list.selection_set(k)
        self.theme_list.bind("<<ListboxSelect>>", lambda _e: self.save())
        ttk.Checkbutton(self.theme_frame, text="Only my themes (leave out my other player events and pieces)",
                        variable=self.only_mine, command=self.save).pack(anchor="w")

    def refresh(self) -> None:
        files = [p.name for p in sorted(self.folder.glob("*.txt")) if p.name != pe.RULES_NAME]
        self.files_label.configure(text=f"{len(files)} file(s) in {self.folder}: " + (", ".join(files[:8]) or
                                                                                      "none yet")
                                   + (" ..." if len(files) > 8 else ""))
        ref = pe.reference_file(self.settings)
        self.reference_label.configure(text=f"Tone reference: {ref.name}"
                                       + ("" if not self.settings.reference else " (your own; Choose Reference "
                                          "File... and Cancel goes back to the owner's)"))
        self.show_prompt()

    # ---- Actions --------------------------------------------------------------------------------------------------

    def open_folder(self) -> None:
        _open(self.folder)

    def add_files(self) -> None:
        paths = ASK_FILES(parent=self.frame, title="Add Player Event files",
                          filetypes=[("Player Event files", "*.txt"), ("All files", "*.*")])
        if not paths:
            return
        lines: list[str] = []
        for raw in paths:
            src = Path(raw)
            items, file_problems = pe.parse_file(src)
            problems = file_problems + pe.check_items(items)
            target = self.folder / src.name
            if target.exists() and target.resolve() != src.resolve() and not ASK_YES_NO(
                    "Player Events", f"{src.name} is already in the folder. Replace it?", parent=self.frame):
                continue
            if target.resolve() != src.resolve():
                shutil.copyfile(src, target)
            events = sum(1 for i in items if i.kind == "event")
            pieces = sum(1 for i in items if i.kind == "piece")
            lines.append(f"{src.name}: {events} event(s), {pieces} piece(s), {len(problems)} problem(s)")
            lines += [f"  {p}" for p in problems[:60]]
        self.show_themes()
        self.refresh()
        if lines:
            report_window(self.frame, "Player Event files added", "\n".join(lines) + "\n\nA bad event or line is "
                          "left out at patch time; the rest still install.")

    def _pick(self, title: str) -> Path | None:
        raw = ASK_FILE(parent=self.frame, title=title, initialdir=str(self.folder),
                       filetypes=[("Player Event files", "*.txt"), ("All files", "*.*")])
        return Path(raw) if raw else None

    def check_file(self) -> None:
        path = self._pick("Check a Player Event file")
        if path is None:
            return
        items, file_problems = pe.parse_file(path)
        problems = file_problems + pe.check_items(items)
        events = [i for i in items if i.kind == "event"]
        pieces = [i for i in items if i.kind == "piece"]
        head = f"{path.name}: {len(events)} event(s), {len(pieces)} piece(s).\n"
        body = ("No problems: every event and piece is ready." if not problems else
                f"{len(problems)} problem(s) (a bad event is left out at patch time; the rest still install):\n\n"
                + "\n".join(str(p) for p in problems))
        report_window(self.frame, "Check File", head + "\n" + body)

    def preview_file(self) -> None:
        path = self._pick("Preview an event")
        if path is None:
            return
        items, file_problems = pe.parse_file(path)
        events = [i for i in items if i.kind == "event"]
        if not events:
            SHOW_INFO("Preview", "That file has no event to preview.", parent=self.frame)
            return
        pick = 1
        if len(events) > 1:
            pick = ASK_INTEGER("Preview", "Which event? (1 = the first in the file)\n\n" + "\n".join(
                f"{k}. {e.title}" for k, e in enumerate(events[:30], 1)), parent=self.frame, minvalue=1,
                maxvalue=len(events)) or 0
            if not pick:
                return
        it = events[pick - 1]
        top = report_window(self.frame, "Preview", pe.preview(it, self.game))

        def again():
            top._text.delete("1.0", "end")       # noqa: SLF001
            top._text.insert("1.0", pe.preview(it, self.game))   # noqa: SLF001
        ttk.Button(top._buttons, text="Again (new random outcomes)", command=again).pack(side="left")  # noqa: SLF001

    def copy_prompt(self) -> None:
        _copy(self.frame, self.prompt_text())
        SHOW_INFO("Player Events", "The AI prompt is on the clipboard. Paste it into any AI with the tone reference "
                  f"file ({pe.reference_file(self.settings).name}: Copy Reference Events puts its text on the "
                  "clipboard), then save the answer as a .txt file and add it here.", parent=self.frame)

    def copy_reference(self) -> None:
        ref = pe.reference_file(self.settings)
        try:
            _copy(self.frame, ref.read_text(encoding="utf-8-sig"))
        except OSError as exc:
            SHOW_ERROR("Player Events", f"The reference file could not be read: {exc}", parent=self.frame)
            return
        SHOW_INFO("Player Events", f"{ref.name} is on the clipboard.", parent=self.frame)

    def open_reference(self) -> None:
        _open(pe.reference_file(self.settings).parent)

    def _owner_text(self, name: str) -> str | None:
        try:
            return pe.shipped_file(name).read_text(encoding="utf-8-sig")
        except OSError as exc:
            SHOW_ERROR("Player Events", f"{name} could not be read: {exc}", parent=self.frame)
            return None

    def copy_owner(self, name: str) -> None:
        """The owner's style guide, themes list or outcomes list on the clipboard."""
        text = self._owner_text(name)
        if text is not None:
            _copy(self.frame, text)
            SHOW_INFO("Player Events", f"{name} is on the clipboard: give it to the AI with the prompt.",
                      parent=self.frame)

    def show_owner(self, name: str) -> None:
        text = self._owner_text(name)
        if text is not None:
            report_window(self.frame, name, text)

    def choose_reference(self) -> None:
        raw = ASK_FILE(parent=self.frame, title="Choose your own tone reference (Cancel: the owner's events)",
                       filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        self.settings.reference = raw or ""
        self.save()
        self.refresh()


def show_patch_reports(parent) -> None:
    """After a patch: what each game's Player Events installed and left out (only when something was left out)."""
    reports = dict(pe.LAST_REPORTS)
    pe.LAST_REPORTS.clear()
    lines = []
    for game, r in sorted(reports.items()):
        if r.skipped or r.notes:
            lines.append(f"{pe.GAME_NAMES[game]}: {len(r.installed)} player event(s) installed, "
                         f"{r.pieces} piece(s)" + ("; left out:" if r.skipped else ""))
            lines += [f"  {x}" for x in r.skipped]
            lines += [f"  Note: {x}" for x in r.notes]
    if lines:
        report_window(parent, "Player Events", "\n".join(lines))
