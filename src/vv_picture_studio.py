"""Picture Studio (Tools tab -> "Picture Studio..."): the villagers of a save, and villagers you make
yourself, drawn exactly as each Virtual Villagers game draws them, saved as transparent PNG pictures.

One window for all five games, with a renderer per game (docs/picture-studio.md):
src/vv_pictures_vv1.py (A New Home) ... src/vv_pictures_vv5.py (New Believers), each a port of that
game's own villager draw code, proven against the game in tests/test_pictures_vv<n>.py.

* "From my save": the game, the save folder and the save (read only); everyone the save holds -- the
  villagers, the bodies awaiting burial, The Lost Children's Esteemed Elder statues, New Believers'
  heathens -- each drawn with the head, body, age, mask and head look the save and the patcher's own files
  give, in the pose, direction and frame picked under the picture (the save does not keep those).
  "Save PNG...", "Save all in this group..." and "Save the whole village...".
* "Make your own": every head, body, mask, sex, life stage and age, pose, direction and frame the game
  has, and the patcher's own art (the Origins masks, A New Home's grey hair, Change Appearance's head look).
* PNGs: transparent, cut to the drawn pixels with a small margin (or none), at the game's size, 2x or 4x
  (crisp) or any width and height (smooth).

The pictures come from the player's own game folder, copied once into "Picture Studio Pictures" beside the
patcher (vv_picture_image.picture_source); no game art ships with the patcher.  Saves, the patcher's data
files and game folders are only read: nothing is written but the PNGs the player saves (and the picture
cache).
"""
from __future__ import annotations

import importlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import vv_picture_image as pi
import vv_pictures_common as common

TITLE = "Picture Studio"
GAMES = dict(common.TITLES)
RENDERER_MODULES = {n: f"vv_pictures_vv{n}" for n in GAMES}
PREVIEW = 300                           # the preview's side, in pixels
FIELD_COLUMNS = 2                       # comboboxes per row on Make your own and under the save preview
PATCHER_MARK = "  (patcher)"
# A New Home's Grey Hair at 55 adds these to the game's Images folder: a game folder holding them was
# patched with it (data/vv1_grey_hair_feature.json).
GREY_HAIR_FILES = ("vvfp_grey_male_heads.png", "vvfp_grey_female_heads.png")

HELP = (
    "Picture Studio",
    [
        "Shows the villagers in your saves, and villagers you make yourself, drawn exactly as the game draws "
        "them, and saves them as PNG pictures with a clear (transparent) background. All five games.",
        "From my save: pick the game, the save folder and the save. The list shows everyone the save holds: the "
        "villagers, the bodies awaiting burial (drawn as the game draws them, a skeleton), The Lost Children's "
        "Esteemed Elder statues and New Believers' heathens. Each is drawn with the head, body, age and life stage "
        "the save gives, and with the patcher's own changes: the Origins masks, Change Appearance's head look "
        "(Young, Old or Auto) and, in A New Home, Grey Hair at 55. The save does not keep a villager's pose, so "
        "pick the pose, direction, frame and the rest under the picture.",
        "Make your own: pick the sex, the life stage and age (children are drawn smaller year by year, exactly as "
        "the game scales them), the head and body (every one the game has), the mask, the head look, and the "
        "pose, direction and frame. Choices marked (patcher) are the patcher's own art.",
        "Saving: \"Save PNG...\" saves the picture shown. Pick the size first: the game's own size, 2x or 4x "
        "(each pixel made a crisp square), or your own width and height (smoothly scaled; leave one empty to keep "
        "the shape). The picture is cut to what is drawn, with a small clear margin, or none if you untick it. "
        "\"Save all in this group\" saves everyone in the group picked in the list; \"Save the whole village\" "
        "saves everyone, each group in its own folder, inside a new folder you choose.",
        "The pictures come from your own copy of the game: the first time the window finds the game folder, it "
        "copies the pictures it needs into its own folder, \"Picture Studio Pictures\" beside the patcher, and "
        "uses them from then on. If it has not found one yet, click \"Find game...\" and pick the game folder "
        "(the one with the Images folder). Your saves, the patcher's files and your game folders are only read, "
        "never changed, so the game may be running.",
    ],
)


def show_help(parent: tk.Misc) -> tk.Toplevel:
    title, lines = HELP
    window = tk.Toplevel(parent)
    window.title(f"How to use: {title}")
    window.transient(parent)
    frame = ttk.Frame(window, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Button(frame, text="Close", command=window.destroy).pack(side="bottom", anchor="e", pady=(6, 0))
    body = ttk.Frame(frame)
    body.pack(fill="both", expand=True)
    rows = max(10, min(30, (window.winfo_screenheight() - 200) // 17))
    text = tk.Text(body, width=82, height=rows, wrap="word", font=("Segoe UI", 9), relief="flat", borderwidth=0,
                   background=ttk.Style(window).lookup("TFrame", "background") or "#f0f0f0")
    scroll = ttk.Scrollbar(body, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    text.insert("1.0", "\n\n".join(lines))
    text.configure(state="disabled")
    window.help_text = text
    window.bind("<Escape>", lambda _e: window.destroy())
    return window


def load_renderer_module(game: int):
    try:
        return importlib.import_module(RENDERER_MODULES[game])
    except ImportError:
        return None


def data_files(module) -> list[str]:
    getter = getattr(module, "required_data_files", None)
    return list(getter()) if callable(getter) else []


def export_options(size: str, width: str = "", height: str = "", margin: bool = True) -> dict:
    """The options for vv_picture_image.export from the window's choices: "1x" / "2x" / "4x", or
    "custom" with a width and/or height in pixels."""
    options: dict = {"margin": pi.MARGIN if margin else 0}
    if size == "custom":
        def number(text: str) -> int:
            text = str(text or "").strip()
            if not text:
                return 0
            if not text.isdigit() or int(text) <= 0:
                raise pi.PictureError("A width or height is a whole number of pixels, 1 or more.")
            return int(text)
        options["size"] = (number(width), number(height))
    else:
        options["scale"] = dict(pi.SIZES).get(size, 1)
    return options


def grey_hair_patched(folders) -> bool | None:
    """Whether a game folder of A New Home holds Grey Hair at 55's pictures: True, False, or None when no
    game folder is known."""
    seen = False
    for folder in folders:
        images = pi.images_folder(Path(folder))
        if not images.is_dir():
            continue
        seen = True
        if all((images / name).is_file() for name in GREY_HAIR_FILES):
            return True
    return False if seen else None


# ------------------------------------------------------------------ the window

_open_window: "PictureStudio | None" = None


def open_picture_studio(app, build=None) -> "PictureStudio":
    """Open (or raise) Picture Studio from the patcher window `app`; `build` (a game build, or None) picks
    the game shown first."""
    game = 1
    title = getattr(build, "title", None)
    if title:
        game = next((n for n, t in GAMES.items() if title.endswith(t)), 1)
    return open_window(app, game, app=app)


def open_window(parent: tk.Misc, game: int = 1, *, app=None, documents: Path | None = None,
                game_folders=()) -> "PictureStudio":
    global _open_window
    if _open_window is not None and _open_window.window.winfo_exists():
        _open_window.window.deiconify()
        _open_window.window.lift()
        _open_window.game_var.set(GAMES[game])
        return _open_window
    _open_window = PictureStudio(parent, game, app=app, documents=documents, game_folders=game_folders)
    return _open_window


class PictureStudio:
    def __init__(self, parent: tk.Misc, game: int = 1, *, app=None, documents: Path | None = None,
                 game_folders=()) -> None:
        self.app = app
        self.documents = documents
        self.extra_game_folders: dict[int, list[Path]] = {}
        self.given_game_folders = [Path(f) for f in game_folders]
        self.window = tk.Toplevel(parent)
        self.window.title(TITLE)
        screen_w, screen_h = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        width, height = min(1220, screen_w - 60), min(820, screen_h - 110)
        self.window.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 3)}")
        self.window.minsize(min(780, width), min(520, height))
        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.game_var = tk.StringVar(master=self.window, value=GAMES.get(game, GAMES[1]))
        self.folder_var = tk.StringVar(master=self.window)
        self.slot_var = tk.StringVar(master=self.window)
        self.status_var = tk.StringVar(master=self.window)
        self.size_var = tk.StringVar(master=self.window, value="1x")
        self.width_var = tk.StringVar(master=self.window)
        self.height_var = tk.StringVar(master=self.window)
        self.margin_var = tk.BooleanVar(master=self.window, value=True)
        self.folders: list[Path] = []
        self.slots: list[tuple[int, str]] = []
        self.module = None
        self.renderer = None
        self.items: list[pi.SavedItem] = []
        self.item_nodes: dict[str, pi.SavedItem] = {}
        self.location_nodes: dict[str, str] = {}
        self.shown: dict[str, pi.Image] = {}
        self.pose_boxes: dict[str, dict] = {}
        self.custom_boxes: dict[str, dict] = {}
        self.subjects: list[pi.Subject] = []
        self.grey_hair: bool | None = None
        self.quiet = False                            # tests: messages are kept, not shown
        self.last_message = ""
        self._build()
        self.game_var.trace_add("write", lambda *_a: self._load_folders())
        self._load_folders()

    # ---- layout
    def _build(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="Game:").pack(side="left")
        ttk.Combobox(top, textvariable=self.game_var, values=list(GAMES.values()), state="readonly",
                     width=17).pack(side="left", padx=(4, 12))
        ttk.Label(top, text="Save folder:").pack(side="left")
        self.folder_box = ttk.Combobox(top, textvariable=self.folder_var, state="readonly", width=40)
        self.folder_box.pack(side="left", padx=(4, 12))
        self.folder_box.bind("<<ComboboxSelected>>", lambda _e: self._load_slots())
        ttk.Label(top, text="Save:").pack(side="left")
        self.slot_box = ttk.Combobox(top, textvariable=self.slot_var, state="readonly", width=26)
        self.slot_box.pack(side="left", padx=(4, 12))
        self.slot_box.bind("<<ComboboxSelected>>", lambda _e: self._fill_save_list())
        ttk.Button(top, text="?", width=2, command=lambda: show_help(self.window)).pack(side="right")
        self.find_button = ttk.Button(top, text="Find game...", command=self.find_game)
        self.find_button.pack(side="right", padx=(0, 8))
        ttk.Label(outer, textvariable=self.status_var, foreground="#245a9a", wraplength=1150,
                  justify="left").pack(anchor="w", pady=(6, 0))

        options = ttk.LabelFrame(outer, text="PNG pictures", padding=(10, 4))
        options.pack(fill="x", pady=(6, 0))
        ttk.Label(options, text="Size:").pack(side="left")
        for label, value in (("Game size", "1x"), ("2x", "2x"), ("4x", "4x"), ("Custom:", "custom")):
            ttk.Radiobutton(options, text=label, value=value, variable=self.size_var).pack(side="left", padx=(4, 0))
        ttk.Entry(options, textvariable=self.width_var, width=6).pack(side="left", padx=(2, 0))
        ttk.Label(options, text="x").pack(side="left", padx=2)
        ttk.Entry(options, textvariable=self.height_var, width=6).pack(side="left")
        ttk.Label(options, text="px").pack(side="left", padx=(2, 12))
        ttk.Checkbutton(options, text="Small clear margin", variable=self.margin_var).pack(side="left")

        self.body = ttk.Frame(outer)
        self.body.pack(fill="both", expand=True, pady=(8, 0))
        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right")

    def close(self) -> None:
        global _open_window
        if _open_window is self:
            _open_window = None
        if self.window.winfo_exists():
            self.window.destroy()

    @property
    def game(self) -> int:
        return next((n for n, t in GAMES.items() if t == self.game_var.get()), 1)

    # ---- the save
    def _load_folders(self) -> None:
        try:
            self.folders = common.save_folders(self.game, self.documents)
        except OSError:
            self.folders = []
        self.folder_box.configure(values=[f.name for f in self.folders])
        if self.folders:
            self.folder_box.current(0)
        else:
            self.folder_var.set("")
        self._load_slots(reload=True)

    def _load_slots(self, reload: bool = True) -> None:
        self.slots = []
        folder = self.current_folder()
        if folder is not None:
            try:
                self.slots = common.slots(folder, self.game)
            except OSError:
                self.slots = []
        self.slot_box.configure(values=[f"Save {slot}: {name or '(no name)'}" for slot, name in self.slots])
        if self.slots:
            self.slot_box.current(0)
        else:
            self.slot_var.set("")
        if reload:
            self._reload()

    def current_folder(self) -> Path | None:
        index = self.folder_box.current()
        return self.folders[index] if 0 <= index < len(self.folders) else None

    def current_slot(self) -> int | None:
        index = self.slot_box.current()
        return self.slots[index][0] if 0 <= index < len(self.slots) else None

    # ---- where the game's pictures are
    def game_folders(self) -> list[Path]:
        """Every folder the game may be in: the ones picked with Find game..., the ones given, and the
        patcher window's (the built game beside the save folder's name, the original game's folder)."""
        out = list(self.extra_game_folders.get(self.game, [])) + list(self.given_game_folders)
        app = self.app
        folder = self.current_folder()
        if app is not None:
            places = getattr(app, "_game_folders_for", None)
            if callable(places) and folder is not None:
                try:
                    out += [Path(p) for p in places(folder)]
                except Exception:              # noqa: BLE001 -- a guess at where the game is, never an error
                    pass
            sources = []
            for name in ("exe_var",):
                var = getattr(app, name, None)
                if var is not None:
                    try:
                        sources.append(var.get().strip())
                    except Exception:          # noqa: BLE001
                        pass
            for var in (getattr(app, "all_folder_vars", None) or {}).values():
                try:
                    sources.append(var.get().strip())
                except Exception:              # noqa: BLE001
                    pass
            for value in filter(None, sources):
                path = Path(value)
                out.append(path.parent if path.suffix.lower() == ".exe" else path)
        return [Path(p) for p in dict.fromkeys(str(p) for p in out)]

    def _reload(self) -> None:
        game = self.game
        self.module = load_renderer_module(game)
        self.renderer = None
        problems = []
        folders = self.game_folders()
        if self.module is not None:
            source = pi.picture_source(game, folders, self.module.required_files(), self.module.patcher_art(),
                                       data_files=data_files(self.module))
            if source.problem:
                problems.append(source.problem)
            try:
                self.renderer = self.module.load(source)
            except Exception as exc:           # noqa: BLE001 -- shown, never fatal
                problems.append(f"The pictures could not be read ({exc}).")
                self.renderer = None
            if self.renderer is not None and getattr(self.renderer, "problem", "") \
                    and self.renderer.problem not in problems:
                problems.append(self.renderer.problem)
        self.grey_hair = grey_hair_patched(folders) if game == 1 else None
        save = (f"{self.folder_var.get()}, {self.slot_var.get()}." if self.current_slot() is not None
                else "No save of this game was found in Documents\\LDW.")
        self.status_var.set(" ".join(x for x in (save, " ".join(problems)) if x))
        self._refresh()

    def _refresh(self) -> None:
        for child in self.body.winfo_children():
            child.destroy()
        self.shown.clear()
        self.pose_boxes = {}
        self.custom_boxes = {}
        if self.renderer is None:
            ttk.Label(self.body, text="The pictures for this game could not be loaded.",
                      font=("Segoe UI", 11)).pack(anchor="w", pady=20)
            return
        self.notebook = ttk.Notebook(self.body)
        self.notebook.pack(fill="both", expand=True)
        self._build_save_tab()
        self._build_custom_tab()

    # ---- shared widgets
    def _preview_pane(self, parent) -> dict:
        pane = ttk.Frame(parent, padding=(10, 0))
        style = ttk.Style(self.window)
        canvas = tk.Canvas(pane, width=PREVIEW, height=PREVIEW, highlightthickness=1, highlightbackground="#c0c0c0",
                           background=style.lookup("TFrame", "background") or "#f0f0f0")
        canvas.pack(anchor="n")
        info = ttk.Label(pane, text="", wraplength=PREVIEW, justify="left")
        info.pack(anchor="w", pady=(6, 0))
        return {"pane": pane, "canvas": canvas, "info": info}

    def _field_boxes(self, parent, fields, on_change, keep: dict | None = None) -> dict:
        """One labelled combobox per Field, FIELD_COLUMNS to a row; returns key -> {box, field}."""
        boxes = {}
        keep = keep or {}
        for index, field in enumerate(fields):
            row, column = divmod(index, FIELD_COLUMNS)
            ttk.Label(parent, text=f"{field.label}:").grid(row=row, column=column * 2, sticky="w", pady=2,
                                                           padx=(0 if column == 0 else 14, 4))
            labels = [o.label + (PATCHER_MARK if o.patcher else "") for o in field.options]
            width = max(12, min(34, max((len(text) for text in labels), default=12) + 2))
            box = ttk.Combobox(parent, values=labels, state="readonly", width=width)
            box.grid(row=row, column=column * 2 + 1, sticky="w", pady=2)
            keys = [o.key for o in field.options]
            wanted = keep.get(field.key, field.default)
            if wanted in keys:
                box.current(keys.index(wanted))
            elif labels:
                box.current(0)
            box.bind("<<ComboboxSelected>>", lambda _e: on_change())
            boxes[field.key] = {"box": box, "field": field}
        return boxes

    @staticmethod
    def _values(boxes: dict) -> dict:
        out = {}
        for key, entry in boxes.items():
            index = entry["box"].current()
            options = entry["field"].options
            if 0 <= index < len(options):
                out[key] = options[index].key
        return out

    def _show(self, preview: dict, image, text: str, error: bool = False) -> None:
        canvas = preview["canvas"]
        canvas.delete("all")
        preview["info"].configure(text=text, foreground="#a01010" if error else "")
        if image is None:
            return
        shown = image.cropped(pi.MARGIN)
        biggest = max(shown.width, shown.height, 1)
        if biggest <= PREVIEW:
            factor = max(1, min(4, PREVIEW // biggest))
            photo = shown.photo(tk, self.window)
            if factor > 1:
                photo = photo.zoom(factor)
        else:
            photo = shown.photo(tk, self.window, max_side=PREVIEW)
        canvas.create_image(PREVIEW // 2, PREVIEW // 2, image=photo)
        canvas.photo = photo

    # ---- From my save
    def _build_save_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="From my save")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        self.save_tree = ttk.Treeview(left, columns=("what",), show="tree headings", selectmode="browse")
        self.save_tree.heading("#0", text="In the save")
        self.save_tree.heading("what", text="Kind")
        self.save_tree.column("#0", width=380)
        self.save_tree.column("what", width=90, stretch=False)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.save_tree.yview)
        self.save_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.save_tree.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(tab)
        right.pack(side="left", fill="y")
        self.save_preview = self._preview_pane(right)
        self.save_preview["pane"].pack(fill="x")
        poses = ttk.LabelFrame(right, text="Pose (the save does not keep it)", padding=(8, 4))
        poses.pack(fill="x", padx=10, pady=(6, 0))
        keep = {}
        if self.grey_hair is not None:
            keep["grey_hair"] = self.grey_hair
        self.pose_boxes = self._field_boxes(poses, self.renderer.saved_fields(), self._show_saved, keep)
        buttons = ttk.Frame(right, padding=(10, 6))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Save PNG...", command=lambda: self.save_png("save")).pack(side="left")
        ttk.Button(buttons, text="Save all in this group...", command=self.save_group).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Save the whole village...", command=self.save_village).pack(side="left",
                                                                                            padx=(6, 0))
        self.save_tree.bind("<<TreeviewSelect>>", lambda _e: self._show_saved())
        self._fill_save_list()

    def _fill_save_list(self) -> None:
        if not hasattr(self, "save_tree") or not self.save_tree.winfo_exists():
            return
        tree = self.save_tree
        tree.delete(*tree.get_children())
        self.items = []
        self.item_nodes = {}
        self.location_nodes = {}
        self.shown.pop("save", None)
        folder, slot = self.current_folder(), self.current_slot()
        if folder is None or slot is None:
            self._show(self.save_preview, None, "Pick a save folder and a save to see who the save holds.")
            return
        try:
            self.items = self.renderer.saved_items(folder, slot)
        except Exception as exc:               # noqa: BLE001 -- shown, never fatal: the window only reads
            self._show(self.save_preview, None, f"The save could not be read: {exc}", error=True)
            return
        for item in self.items:
            parent = self.location_nodes.get(item.location)
            if parent is None:
                parent = tree.insert("", "end", text=item.location, open=True)
                self.location_nodes[item.location] = parent
            node = tree.insert(parent, "end", text=item.label, values=(item.kind,))
            self.item_nodes[node] = item
        self._show(self.save_preview, None, "Click a villager to see the picture." if self.items
                   else "Nobody is in this save.")

    def selected_item(self) -> pi.SavedItem | None:
        selection = self.save_tree.selection()
        return self.item_nodes.get(selection[0]) if selection else None

    def selected_location(self) -> str | None:
        selection = self.save_tree.selection()
        if not selection:
            return None
        item = self.item_nodes.get(selection[0])
        return item.location if item is not None else self.save_tree.item(selection[0], "text")

    def pose(self) -> dict:
        return self._values(self.pose_boxes)

    def render_item(self, item: pi.SavedItem) -> pi.Image:
        return self.renderer.render_saved(self.current_folder(), self.current_slot(), item.id, **self.pose())

    def _show_saved(self) -> None:
        item = self.selected_item()
        if item is None:
            return
        try:
            image = self.render_item(item)
        except Exception as exc:               # noqa: BLE001 -- shown, never fatal
            self.shown.pop("save", None)
            self._show(self.save_preview, None, f"{item.label}: this cannot be drawn ({exc}).", error=True)
            return
        self.shown["save"] = image
        self._show(self.save_preview, image, item.detail or item.label)

    # ---- Make your own
    def _build_custom_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Make your own")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        self.custom_notebook = ttk.Notebook(left)
        self.custom_notebook.pack(fill="both", expand=True)
        right = ttk.Frame(tab)
        right.pack(side="left", fill="y")
        self.custom_preview = self._preview_pane(right)
        self.custom_preview["pane"].pack(fill="x")
        buttons = ttk.Frame(right, padding=(10, 6))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Save PNG...", command=lambda: self.save_png("custom")).pack(anchor="w")
        try:
            self.subjects = list(self.renderer.custom_choices())
        except Exception as exc:               # noqa: BLE001
            self.subjects = []
            self._show(self.custom_preview, None, f"Nothing can be made here ({exc}).", error=True)
        for subject in self.subjects:
            frame = ttk.Frame(self.custom_notebook, padding=10)
            self.custom_notebook.add(frame, text=subject.title)
            fields = ttk.Frame(frame)
            fields.pack(anchor="nw", fill="x")
            self.custom_boxes[subject.key] = self._field_boxes(fields, subject.fields, self._show_custom)
            if subject.note:
                ttk.Label(frame, text=subject.note, wraplength=560, justify="left",
                          foreground="#555555").pack(anchor="w", pady=(10, 0))
        self.custom_notebook.bind("<<NotebookTabChanged>>", lambda _e: self._show_custom())
        self._show_custom()

    def current_subject(self) -> pi.Subject | None:
        try:
            index = self.custom_notebook.index(self.custom_notebook.select())
        except tk.TclError:
            return None
        return self.subjects[index] if 0 <= index < len(self.subjects) else None

    def custom_spec(self) -> dict | None:
        subject = self.current_subject()
        if subject is None:
            return None
        spec = {"subject": subject.key}
        spec.update(self._values(self.custom_boxes.get(subject.key, {})))
        return spec

    def _show_custom(self) -> None:
        spec = self.custom_spec()
        if spec is None:
            return
        try:
            image = self.renderer.render_custom(spec)
        except Exception as exc:               # noqa: BLE001 -- shown, never fatal
            self.shown.pop("custom", None)
            self._show(self.custom_preview, None, f"This cannot be drawn: {exc}", error=True)
            return
        self.shown["custom"] = image
        self._show(self.custom_preview, image, "")

    # ---- saving
    def export_choice(self) -> dict:
        return export_options(self.size_var.get(), self.width_var.get(), self.height_var.get(), self.margin_var.get())

    def picture_name(self, which: str) -> str:
        if which == "save":
            item = self.selected_item()
            return pi.safe_file_name(item.label if item else "picture")
        subject = self.current_subject()
        parts = []
        if subject is not None:
            for entry in self.custom_boxes.get(subject.key, {}).values():
                index = entry["box"].current()
                if 0 <= index < len(entry["field"].options) and entry["field"].key in (
                        "sex", "stage", "life", "head", "body", "mask", "pose", "kind"):
                    parts.append(entry["field"].options[index].label)
        return pi.safe_file_name(" - ".join(parts) or (subject.title if subject else "picture"))

    def save_png(self, which: str, path: str | None = None) -> Path | None:
        image = self.shown.get(which)
        if image is None:
            self._tell("info", "Pick a picture first.")
            return None
        try:
            options = self.export_choice()
        except pi.PictureError as exc:
            self._tell("warning", str(exc))
            return None
        if path is None:
            path = filedialog.asksaveasfilename(parent=self.window, title="Save PNG", defaultextension=".png",
                                                initialfile=self.picture_name(which) + ".png",
                                                filetypes=[("PNG picture", "*.png")])
        if not path:
            return None
        try:
            return pi.save_png(image, path, **options)
        except (OSError, pi.PictureError) as exc:
            self._tell("warning", f"The picture could not be saved: {exc}")
            return None

    def _new_folder(self, folder: Path, name: str) -> Path:
        target = Path(folder) / pi.safe_file_name(name)
        n = 2
        while target.exists():
            target = Path(folder) / pi.safe_file_name(f"{name} ({n})")
            n += 1
        target.mkdir(parents=True)
        return target

    def _save_items(self, items, target: Path, options: dict, by_group: bool) -> tuple[int, list[str]]:
        saved, failed = 0, []
        folders: dict[str, Path] = {}
        for item in items:
            where = target
            if by_group:
                where = folders.get(item.location)
                if where is None:
                    where = folders[item.location] = self._new_folder(target, item.location)
            try:
                image = self.render_item(item)
                pi.save_png(image, pi.unique_path(where, pi.safe_file_name(item.label)), **options)
                saved += 1
            except (OSError, pi.PictureError) as exc:
                failed.append(f"{item.label}: {exc}")
        return saved, failed

    def _village_label(self) -> str:
        return self.slot_var.get().split(": ", 1)[-1] if self.current_slot() is not None else "Save"

    def save_group(self, folder: str | None = None) -> Path | None:
        location = self.selected_location()
        if location is None:
            self._tell("info", "Pick a group in the list (or anyone in it) first.")
            return None
        return self._save_many([i for i in self.items if i.location == location], folder,
                               f"{self._village_label()} - {location}", by_group=False)

    def save_village(self, folder: str | None = None) -> Path | None:
        if not self.items:
            self._tell("info", "Pick a save with villagers in it first.")
            return None
        return self._save_many(self.items, folder, f"{self._village_label()} - {GAMES[self.game]}", by_group=True)

    def _save_many(self, items, folder, name: str, by_group: bool) -> Path | None:
        try:
            options = self.export_choice()
        except pi.PictureError as exc:
            self._tell("warning", str(exc))
            return None
        if folder is None:
            folder = filedialog.askdirectory(parent=self.window, title="Save the pictures in...")
        if not folder:
            return None
        try:
            target = self._new_folder(Path(folder), name)
        except OSError as exc:
            self._tell("warning", f"The folder could not be made: {exc}")
            return None
        saved, failed = self._save_items(items, target, options, by_group)
        text = f"{saved} picture(s) saved in {target}."
        if failed:
            text += "\nNot saved:\n" + "\n".join(failed[:10])
        self._tell("info", text)
        return target

    def _tell(self, kind: str, text: str) -> None:
        self.last_message = text
        if not self.quiet:
            (messagebox.showwarning if kind == "warning" else messagebox.showinfo)(TITLE, text, parent=self.window)

    # ---- the pictures
    def find_game(self, chosen: str | None = None) -> str:
        """"Find game...": pick a game folder; the pictures are copied from it into the Studio's own
        folder (the game folder is only read)."""
        game = self.game
        if self.module is None:
            return ""
        if chosen is None:
            chosen = filedialog.askdirectory(parent=self.window, title=f"Choose your {common.title(game)} game folder")
        if not chosen:
            return ""
        folder = Path(chosen)
        if not pi.is_game_folder(game, folder, self.module.required_files(), data_files(self.module)):
            result = (f"{folder} is not a {common.title(game)} game folder: its Images folder does not have every "
                      "picture the game draws villagers with.")
            self._tell("warning", result)
            return result
        self.extra_game_folders.setdefault(game, []).insert(0, folder)
        built, why = pi.build_cache(game, folder, self.module.required_files(), data_files=data_files(self.module))
        if not built:
            self._tell("warning", f"The pictures could not be copied: {why} They are read from the game folder "
                                  "while this window is open.")
        self._reload()
        return "" if built else why
