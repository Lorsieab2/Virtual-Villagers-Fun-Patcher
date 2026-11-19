"""The Custom Stuff window (Tools tab, "Custom Stuff..."): the player's own first names, last names, and likes and
dislikes for each game, with an AI prompt and templates for making lists with any AI (src/vv_custom_stuff.py).

The owner (2026-11-19): a "Custom Stuff" window with tabs per game -- names, last names, likes and dislikes now; art
tabs (heads, outfits) come in a later version, so the notebook simply gets more tabs then.  Players type or paste
entries (one per line) or Import a .txt file; Check shows why a line is refused; Save keeps the lists and copies the
checked entries to every patched copy of the game the patcher knows, used from the game's next start.
"""
from __future__ import annotations

from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import vv_custom_stuff as cs

TITLE = "Custom Stuff"
INTRO = ("Add your own names to each game. They are additions: the game's own names always stay, and every name, the "
         "game's and yours, is equally likely. One entry per line; lines starting with # are notes.")
PATCH_ROW_NOTE = ("The game must be patched with the \"Custom Stuff: Your Own Names\" row (on by default); your last "
                  "names also need \"Villagers Have Last Names\". Saved lists are used from the game's next start, "
                  "with no re-patching.")
LIKES_NOTE = ("Likes and dislikes are kept and copied with your names, but the games do not show them yet: giving "
              "them to villagers the way the game gives its own comes in a later version.")
TABS = (
    ("Names", ("male", "female")),
    ("Last Names", ("last",)),
    ("Likes and Dislikes", ("likes",)),
)
EDITOR_LABELS = {
    "male": "Male first names",
    "female": "Female first names",
    "last": "Last names",
    "likes": "Likes and dislikes (each can be either)",
}


class CustomStuffWindow:
    def __init__(self, app, build=None, root: Path | None = None):
        self.app = app
        self.root = root
        self.games = list(cs.GAMES)
        self.titles = [f"Virtual Villagers - {cs.TITLES[n]}" for n in self.games]
        start = 1
        if build is not None:
            for n, title in cs.TITLES.items():
                if str(getattr(build, "title", "")).endswith(title):
                    start = n
        self.texts: dict[int, dict[str, str]] = {}      # game -> kind -> the text being edited
        self.saved: dict[int, dict[str, str]] = {}
        self.game = start
        top = self.top = tk.Toplevel(app)
        top.title(TITLE)
        try:
            top.transient(app)
        except tk.TclError:
            pass
        frame = ttk.Frame(top, padding=14)
        frame.pack(fill="both", expand=True)
        self.frame = frame
        ttk.Label(frame, text=INTRO, wraplength=640, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(frame, text="Game:").grid(row=1, column=0, sticky="w", pady=(8, 2))
        self.game_var = tk.StringVar(master=top, value=self.titles[self.games.index(start)])
        box = ttk.Combobox(frame, textvariable=self.game_var, values=self.titles, state="readonly", width=48)
        box.grid(row=1, column=1, sticky="w", pady=(8, 2))
        box.bind("<<ComboboxSelected>>", lambda _e: self.switch_game())
        ttk.Label(frame, text=PATCH_ROW_NOTE, wraplength=640, justify="left", foreground="#555555").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(2, 6))

        self.notebook = ttk.Notebook(frame)
        self.notebook.grid(row=3, column=0, columnspan=2, sticky="nsew")
        self.editors: dict[str, tk.Text] = {}
        self.problems: dict[str, tk.StringVar] = {}
        for tab_name, kinds in TABS:
            tab = ttk.Frame(self.notebook, padding=8)
            self.notebook.add(tab, text=tab_name)
            for column, kind in enumerate(kinds):
                self._list_editor(tab, kind, column)
            if "likes" in kinds:
                ttk.Label(tab, text=LIKES_NOTE, wraplength=600, justify="left", foreground="#9a5a24").grid(
                    row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self._ai_tab()

        self.status_var = tk.StringVar(master=top)
        ttk.Label(frame, textvariable=self.status_var, wraplength=640, justify="left", foreground="#245a9a").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Save", command=self.save).pack(side="left")
        ttk.Button(buttons, text="Close", command=self.close).pack(side="left", padx=(8, 0))
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.bind("<Escape>", lambda _e: self.close())
        top.custom_stuff = self
        self.load_game(start)

    # ---- building ----------------------------------------------------------------------------------------

    def _list_editor(self, tab: ttk.Frame, kind: str, column: int) -> None:
        box = ttk.LabelFrame(tab, text=EDITOR_LABELS[kind], padding=6)
        box.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        inner = ttk.Frame(box)
        inner.pack(fill="both", expand=True)
        text = tk.Text(inner, width=30 if kind != "likes" else 44, height=14, undo=True, wrap="none")
        scroll = ttk.Scrollbar(inner, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="left", fill="y")
        self.editors[kind] = text
        row = ttk.Frame(box)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="Import...", command=lambda k=kind: self.import_file(k)).pack(side="left")
        ttk.Button(row, text="Export...", command=lambda k=kind: self.export_file(k)).pack(side="left", padx=(6, 0))
        ttk.Button(row, text="Check", command=lambda k=kind: self.check(k)).pack(side="left", padx=(6, 0))
        var = tk.StringVar(master=self.top)
        ttk.Label(box, textvariable=var, wraplength=280 if kind != "likes" else 420, justify="left",
                  foreground="#555555").pack(fill="x", pady=(4, 0))
        self.problems[kind] = var
        tab.columnconfigure(column, weight=1)
        tab.rowconfigure(0, weight=1)

    def _ai_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="AI Help")
        ttk.Label(tab, wraplength=620, justify="left", text=(
            "Make a list with any AI chat: pick what you want, copy the prompt, paste it into the AI, then paste its "
            "answer into the right tab here, press Check, and Save. The prompt carries the game's own list as the "
            "style to match and the same rules the Check button uses. Save Template... writes a ready-to-fill .txt "
            "file for Import...")).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(tab, text="Make:").grid(row=1, column=0, sticky="w", pady=(8, 2))
        self.ai_kind = tk.StringVar(master=self.top, value=cs.KIND_LABELS["male"])
        kinds = ttk.Combobox(tab, textvariable=self.ai_kind, state="readonly", width=24,
                             values=[cs.KIND_LABELS[k] for k in cs.KINDS])
        kinds.grid(row=1, column=1, sticky="w", pady=(8, 2))
        kinds.bind("<<ComboboxSelected>>", lambda _e: self.refresh_prompt())
        ttk.Label(tab, text="How many:").grid(row=1, column=2, sticky="e", padx=(12, 4), pady=(8, 2))
        self.ai_count = tk.StringVar(master=self.top, value="40")
        count = ttk.Spinbox(tab, from_=5, to=200, increment=5, textvariable=self.ai_count, width=6,
                            command=self.refresh_prompt)
        count.grid(row=1, column=3, sticky="w", pady=(8, 2))
        count.bind("<KeyRelease>", lambda _e: self.refresh_prompt())
        self.prompt_text = tk.Text(tab, width=80, height=14, wrap="word")
        self.prompt_text.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(6, 0))
        row = ttk.Frame(tab)
        row.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        ttk.Button(row, text="Copy Prompt", command=self.copy_prompt).pack(side="left")
        ttk.Button(row, text="Save Prompt...", command=self.save_prompt).pack(side="left", padx=(6, 0))
        ttk.Button(row, text="Save Template...", command=self.save_template).pack(side="left", padx=(6, 0))
        tab.columnconfigure(3, weight=1)
        tab.rowconfigure(2, weight=1)

    # ---- the game's lists --------------------------------------------------------------------------------

    def _kind_of_label(self, label: str) -> str:
        for kind, text in cs.KIND_LABELS.items():
            if text == label:
                return kind
        return "male"

    def _store_editors(self) -> None:
        texts = self.texts.setdefault(self.game, {})
        for kind, widget in self.editors.items():
            texts[kind] = widget.get("1.0", "end-1c")

    def load_game(self, game: int) -> None:
        self.game = game
        if game not in self.texts:
            self.texts[game] = {k: cs.read_library(game, k, self.root) for k in cs.KINDS}
            self.saved[game] = dict(self.texts[game])
        for kind, widget in self.editors.items():
            widget.delete("1.0", "end")
            widget.insert("1.0", self.texts[game][kind])
            widget.edit_reset()
            self.problems[kind].set("")
        self.refresh_prompt()
        self.status_var.set("")

    def switch_game(self) -> None:
        self._store_editors()
        title = self.game_var.get()
        self.load_game(self.games[self.titles.index(title)] if title in self.titles else 1)

    def dirty_games(self) -> list[int]:
        self._store_editors()
        return [g for g, texts in self.texts.items() if texts != self.saved.get(g)]

    def check(self, kind: str) -> list[cs.Checked]:
        checked = cs.check_entries(self.game, kind, self.editors[kind].get("1.0", "end-1c"))
        kept = sum(1 for c in checked if c.ok)
        lines = [f"{kept} kept."]
        refused = [c for c in checked if not c.ok]
        if refused:
            lines.append(f"{len(refused)} refused:")
            lines += [f"Line {c.line}: \"{c.text}\" {c.problem}." for c in refused[:12]]
            if len(refused) > 12:
                lines.append(f"... and {len(refused) - 12} more.")
        noted = [c for c in checked if c.note]
        lines += [f"Line {c.line}: \"{c.text}\" {c.note}." for c in noted[:4]]
        self.problems[kind].set("\n".join(lines))
        return checked

    # ---- files -------------------------------------------------------------------------------------------

    def import_file(self, kind: str) -> None:
        path = filedialog.askopenfilename(parent=self.top, title=f"Import {cs.KIND_LABELS[kind]}",
                                          filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            data = Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror(TITLE, f"Could not read {path}:\n{exc}", parent=self.top)
            return
        widget = self.editors[kind]
        current = widget.get("1.0", "end-1c")
        if current and not current.endswith("\n"):
            widget.insert("end", "\n")
        widget.insert("end", data)
        self.check(kind)
        self.status_var.set(f"Imported {Path(path).name}: press Save to keep it.")

    def export_file(self, kind: str) -> None:
        path = filedialog.asksaveasfilename(parent=self.top, title=f"Export {cs.KIND_LABELS[kind]}",
                                            defaultextension=".txt", initialfile=cs.FILE_NAMES[kind],
                                            filetypes=[("Text files", "*.txt")])
        if not path:
            return
        try:
            Path(path).write_text(self.editors[kind].get("1.0", "end-1c") + "\n", encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(TITLE, f"Could not write {path}:\n{exc}", parent=self.top)
            return
        self.status_var.set(f"Exported to {path}.")

    def patched_folders(self, game: int) -> list[Path]:
        try:
            import vv_translations_window
            return [f for f in vv_translations_window.patched_folders(self.app, game)
                    if (Path(f) / cs.PATCHER_FILES).is_dir()]
        except Exception:                       # no known folders: the next build copies the lists
            return []

    def save(self) -> bool:
        games = self.dirty_games() or [self.game]
        applied: list[str] = []
        for game in games:
            for kind in cs.KINDS:
                try:
                    cs.write_library(game, kind, self.texts[game][kind], self.root)
                except OSError as exc:
                    messagebox.showerror(TITLE, f"Could not save your {cs.KIND_LABELS[kind]}:\n{exc}", parent=self.top)
                    return False
            self.saved[game] = dict(self.texts[game])
            for folder in self.patched_folders(game):
                try:
                    if cs.apply_library(game, folder, self.root) is not None:
                        applied.append(str(folder))
                except OSError:
                    pass
        for kind in self.editors:
            self.check(kind)
        where = (" Copied to: " + "; ".join(applied) + ".") if applied else (
            " No patched copy was found yet: the next build copies them.")
        self.status_var.set("Saved." + where)
        return True

    def close(self) -> None:
        if self.dirty_games():
            answer = messagebox.askyesnocancel(TITLE, "Save your changes before closing?", parent=self.top)
            if answer is None:
                return
            if answer and not self.save():
                return
        self.top.destroy()

    # ---- AI help -----------------------------------------------------------------------------------------

    def _count(self) -> int:
        try:
            return max(1, min(200, int(self.ai_count.get())))
        except ValueError:
            return 40

    def refresh_prompt(self) -> None:
        kind = self._kind_of_label(self.ai_kind.get())
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", cs.ai_prompt(self.game, kind, self._count()))

    def copy_prompt(self) -> None:
        self.top.clipboard_clear()
        self.top.clipboard_append(self.prompt_text.get("1.0", "end-1c"))
        self.status_var.set("The prompt is copied: paste it into your AI chat.")

    def save_prompt(self) -> None:
        kind = self._kind_of_label(self.ai_kind.get())
        path = filedialog.asksaveasfilename(parent=self.top, title="Save prompt", defaultextension=".txt",
                                            initialfile=f"Custom Stuff - AI Prompt - {cs.KIND_LABELS[kind]}.txt",
                                            filetypes=[("Text files", "*.txt")])
        if path:
            Path(path).write_text(self.prompt_text.get("1.0", "end-1c") + "\n", encoding="utf-8")
            self.status_var.set(f"Saved the prompt to {path}.")

    def save_template(self) -> None:
        kind = self._kind_of_label(self.ai_kind.get())
        path = filedialog.asksaveasfilename(parent=self.top, title="Save template", defaultextension=".txt",
                                            initialfile=f"Custom Stuff - Template - {cs.KIND_LABELS[kind]}.txt",
                                            filetypes=[("Text files", "*.txt")])
        if path:
            Path(path).write_text(cs.template_text(self.game, kind), encoding="utf-8")
            self.status_var.set(f"Saved the template to {path}.")


def open_custom_stuff(app, build=None) -> tk.Toplevel:
    """The Custom Stuff window, for ``build`` (the One Game tab's game) or, with None, A New Home."""
    return CustomStuffWindow(app, build).top
