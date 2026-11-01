"""Picture Studio's "Everything" tab (src/vv_picture_studio.py): every picture the game ships, drawn as the game
draws it, sorted by category (src/vv_pictures_assets.py; each game's src/vv_assets_vv<n>.py), saved as
transparent PNGs at the window's size choice (game size, 2x, 4x or custom).

* The list: category, then group, then each asset; a click shows its first picture, the "Picture" box picks any
  other (a state, a frame, a fill level, a cell ...).  The line under the picture says what it is and how
  much of it is the game's own placing.
* "Save PNG...": the picture shown.  "Save all of this...": every picture of the asset picked.  "Save all...":
  every picture of the category chosen beside it (or every category), each category in its own folder, inside
  a new folder.

The pictures are read from the player's own game folder into "Picture Studio Pictures\\Everything" (all of its
Images, nothing shipped).  Nothing else is written.
"""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

import vv_picture_image as pi
import vv_pictures_assets as pa

TAB_TITLE = "Everything"
ALL_CATEGORIES = "Every category"
HELP_LINE = (
    "Everything: every picture the game ships, drawn as the game draws it, sorted by category: creatures, "
    "buildings and objects at each stage, puzzles in each state, collectibles, plants and food, the island scene, "
    "the Tech screen's bars empty, part filled and full, meters at several fill levels, panels and buttons in each "
    "state, icons, cursors, fonts, effects and whole screens, then every sheet the game ships cell by cell (Source "
    "sheets). Art the game ships but never draws is marked (unused); the patcher's own art is marked (patcher). "
    "Pick a picture in the Picture box; \"Save all...\" saves every picture of the category chosen (or of every "
    "category), each category in its own folder.")


class EverythingTab:
    """The tab, inside a PictureStudio window (`studio`)."""

    def __init__(self, studio, notebook: ttk.Notebook) -> None:
        self.studio = studio
        self.frame = ttk.Frame(notebook, padding=6)
        notebook.add(self.frame, text=TAB_TITLE)
        self.loaded_for: int | None = None
        self.sheets = None
        self.assets: list[pa.Asset] = []
        self.nodes: dict[str, pa.Asset] = {}
        self.image = None
        self.category_var = tk.StringVar(master=studio.window, value=ALL_CATEGORIES)
        self._build()
        notebook.bind("<<NotebookTabChanged>>", lambda _e: self._maybe_load(notebook), add="+")

    # ---- layout
    def _build(self) -> None:
        left = ttk.Frame(self.frame)
        left.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(left, columns=("count",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="What the game draws")
        self.tree.heading("count", text="Pictures")
        self.tree.column("#0", width=400)
        self.tree.column("count", width=70, stretch=False, anchor="e")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._select())
        right = ttk.Frame(self.frame)
        right.pack(side="left", fill="y")
        self.preview = self.studio._preview_pane(right)
        self.preview["pane"].pack(fill="x")
        pick = ttk.Frame(right, padding=(10, 6, 10, 0))
        pick.pack(fill="x")
        ttk.Label(pick, text="Picture:").pack(side="left")
        self.frame_box = ttk.Combobox(pick, state="readonly", width=40)
        self.frame_box.pack(side="left", padx=(4, 0))
        self.frame_box.bind("<<ComboboxSelected>>", lambda _e: self._show_frame())
        buttons = ttk.Frame(right, padding=(10, 6))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Save PNG...", command=self.save_png).pack(side="left")
        ttk.Button(buttons, text="Save all of this...", command=self.save_asset).pack(side="left", padx=(6, 0))
        many = ttk.Frame(right, padding=(10, 0))
        many.pack(fill="x")
        self.category_box = ttk.Combobox(many, textvariable=self.category_var, state="readonly", width=26)
        self.category_box.pack(side="left")
        ttk.Button(many, text="Save all...", command=self.save_all).pack(side="left", padx=(6, 0))

    def _maybe_load(self, notebook) -> None:
        try:
            if notebook.select() != str(self.frame):
                return
        except tk.TclError:
            return
        if self.loaded_for != self.studio.game:
            self.load()

    # ---- the list
    def load(self) -> None:
        studio = self.studio
        game = studio.game
        self.loaded_for = game
        self.sheets, _module, self.assets, problem = pa.load(game, studio.game_folders())
        tree = self.tree
        tree.delete(*tree.get_children())
        self.nodes = {}
        groups: dict[tuple, str] = {}
        for asset in self.assets:
            ckey = (asset.category,)
            if ckey not in groups:
                groups[ckey] = tree.insert("", "end", text=asset.category, open=False)
            parent = groups[ckey]
            if asset.group:
                gkey = (asset.category, asset.group)
                if gkey not in groups:
                    groups[gkey] = tree.insert(parent, "end", text=asset.group, open=False)
                parent = groups[gkey]
            count = "" if asset.lazy else str(len(asset.frames))
            node = tree.insert(parent, "end", text=asset.shown, values=(count,))
            self.nodes[node] = asset
        categories = list(dict.fromkeys(a.category for a in self.assets))
        self.category_box.configure(values=[ALL_CATEGORIES] + categories)
        self.category_var.set(ALL_CATEGORIES)
        self.frame_box.configure(values=[])
        self.frame_box.set("")
        self.image = None
        if problem:
            text = problem
        elif self.assets:
            text = (f"{len(self.assets)} entries in {len(categories)} categories. Click one to see it.")
        else:
            text = "Nothing to show for this game."
        studio._show(self.preview, None, text, error=bool(problem) and not self.assets)

    def selected(self) -> pa.Asset | None:
        selection = self.tree.selection()
        return self.nodes.get(selection[0]) if selection else None

    def frames(self, asset: pa.Asset) -> tuple:
        return pa.frames_of(self.sheets, asset)

    def _select(self) -> None:
        asset = self.selected()
        if asset is None:
            return
        try:
            frames = self.frames(asset)
        except (pi.PictureError, OSError) as exc:
            self.studio._show(self.preview, None, f"{asset.shown}: this cannot be drawn ({exc}).", error=True)
            return
        labels = [f.label or "the picture" for f in frames]
        self.frame_box.configure(values=labels, width=max(20, min(48, max((len(t) for t in labels), default=20) + 2)))
        if labels:
            self.frame_box.current(0)
        self._show_frame()

    def current_frame(self):
        asset = self.selected()
        if asset is None:
            return None, None
        frames = self.frames(asset)
        index = self.frame_box.current()
        return asset, (frames[index] if 0 <= index < len(frames) else (frames[0] if frames else None))

    def _show_frame(self) -> None:
        asset, frame = self.current_frame()
        if asset is None or frame is None:
            return
        try:
            self.image = pa.render_frame(self.sheets, frame)
        except (pi.PictureError, OSError, ValueError) as exc:
            self.image = None
            self.studio._show(self.preview, None, f"{asset.shown}: this cannot be drawn ({exc}).", error=True)
            return
        lines = [asset.shown + (f" - {frame.label}" if frame.label else "")]
        if asset.note:
            lines.append(asset.note[0].upper() + asset.note[1:] + ("" if asset.note.endswith(".") else "."))
        self.studio._show(self.preview, self.image, "\n".join(lines))

    # ---- saving
    def save_png(self, path: str | None = None) -> Path | None:
        studio = self.studio
        asset, frame = self.current_frame()
        if asset is None or frame is None or self.image is None:
            studio._tell("info", "Pick a picture first.")
            return None
        try:
            options = studio.export_choice()
        except pi.PictureError as exc:
            studio._tell("warning", str(exc))
            return None
        if path is None:
            path = filedialog.asksaveasfilename(parent=studio.window, title="Save PNG", defaultextension=".png",
                                                initialfile=pa.frame_file_stem(asset, frame) + ".png",
                                                filetypes=[("PNG picture", "*.png")])
        if not path:
            return None
        try:
            return pi.save_png(self.image, path, **options)
        except (OSError, pi.PictureError) as exc:
            studio._tell("warning", f"The picture could not be saved: {exc}")
            return None

    def save_asset(self, folder: str | None = None) -> Path | None:
        asset = self.selected()
        if asset is None:
            self.studio._tell("info", "Pick something in the list first.")
            return None
        return self._save([asset], folder, asset.shown)

    def save_all(self, folder: str | None = None, category: str | None = None) -> Path | None:
        category = category or self.category_var.get() or ALL_CATEGORIES
        chosen = self.assets if category == ALL_CATEGORIES else [a for a in self.assets if a.category == category]
        if not chosen:
            self.studio._tell("info", "There is nothing to save for this game yet.")
            return None
        name = f"{self.studio.game_var.get()} - " + ("Everything" if category == ALL_CATEGORIES else category)
        return self._save(chosen, folder, name)

    def _save(self, assets, folder, name: str) -> Path | None:
        studio = self.studio
        try:
            options = studio.export_choice()
        except pi.PictureError as exc:
            studio._tell("warning", str(exc))
            return None
        if folder is None:
            folder = filedialog.askdirectory(parent=studio.window, title="Save the pictures in...")
        if not folder:
            return None
        try:
            target = studio._new_folder(Path(folder), name)
        except OSError as exc:
            studio._tell("warning", f"The folder could not be made: {exc}")
            return None

        def progress(done, total):
            if done % 50 == 0 or done == total:
                studio.status_var.set(f"Saving pictures: {done} of {total}...")
                try:
                    studio.window.update()
                except tk.TclError:
                    return False
            return True
        saved, failed = pa.save_assets(self.sheets, assets, target, options, progress)
        text = f"{saved} picture(s) saved in {target}."
        if failed:
            text += "\nNot saved:\n" + "\n".join(failed[:10])
        studio.status_var.set(text.splitlines()[0])
        studio._tell("info", text)
        return target


def add_tab(studio, notebook: ttk.Notebook) -> EverythingTab:
    return EverythingTab(studio, notebook)
