"""Picture Studio's "Text" tab (src/vv_picture_studio.py adds it with add_tab): type anything, see it in a
game's own font, save it as a transparent PNG.  The drawing is src/vv_pictures_text.py's
(docs/picture-studio-text.md); this is only the window.
"""
from __future__ import annotations

import tkinter as tk
import unicodedata
from tkinter import colorchooser, ttk

import vv_picture_image as pi
import vv_pictures_text as text

PREVIEW_W, PREVIEW_H = 560, 300
SAMPLE = "Welcome to the island!\nCafé à la crème, Łódź, Ångström"
MARK_COLOURS = {text.SOURCE_PATCHER: "#2a6fdb", text.SOURCE_MADE: "#e07800", text.SOURCE_EMOJI: "#a040d0",
                "missing": "#d02020"}
BACKGROUNDS = {"Dark": "#2d3b4c", "Light": "#f4f1e8", "Grass green": "#4e7a3a", "Black": "#000000",
               "White": "#ffffff"}
CUSTOM = "Custom colour..."


def add_tab(studio) -> "TextTab | None":
    """Add the Text tab to the Studio's notebook (called from PictureStudio._refresh)."""
    notebook = getattr(studio, "notebook", None)
    if notebook is None:
        return None
    tab = TextTab(studio, notebook)
    studio.text_tab = tab
    return tab


class TextTab:
    def __init__(self, studio, notebook: ttk.Notebook) -> None:
        self.studio = studio
        self.window = studio.window
        self.game = studio.game
        self.frame = ttk.Frame(notebook, padding=6)
        notebook.add(self.frame, text="Text")
        self.sheets: dict[str, pi.Image] = {}
        self.images_dir = None
        self.problem = ""
        self.renderers: dict = {}
        self.rendered: text.Rendered | None = None
        self.custom_colour = (255, 255, 255)
        self._after = None
        self._load_sheets()
        self._build()
        self.refresh()

    # ---- the fonts
    def _load_sheets(self) -> None:
        try:
            source = text.font_source(self.game, self.studio.game_folders())
        except Exception as exc:               # noqa: BLE001 -- shown, never fatal
            self.problem = f"The fonts could not be read ({exc})."
            return
        if source.problem:
            self.problem = source.problem
        self.images_dir = text.sheet_folder(source)
        for info in text.font_infos(self.game):
            data = source.read(info["sheet"])
            if data is None:
                continue
            try:
                self.sheets[info["key"]] = pi.decode_png(data)
            except pi.PictureError as exc:
                self.problem = f"{info['sheet']} could not be read ({exc})."

    def font_choices(self) -> list[tuple[str, str]]:
        """(key, name) of every font offered: the game's two (when its pictures are found) and Burweed ICG
        when it is installed."""
        out = [(info["key"], info["name"]) for info in text.font_infos(self.game) if info["key"] in self.sheets]
        if text.ttf_installed():
            out.append((text.TTF_KEY, text.TTF_NAME))
        return out

    # ---- layout
    def _build(self) -> None:
        f = self.frame
        left = ttk.Frame(f)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(f, padding=(10, 0, 0, 0))
        right.pack(side="left", fill="y")

        row = ttk.Frame(left)
        row.pack(fill="x")
        ttk.Label(row, text="Font:").pack(side="left")
        self.fonts = self.font_choices()
        self.font_box = ttk.Combobox(row, values=[n for _k, n in self.fonts], state="readonly", width=26)
        self.font_box.pack(side="left", padx=(4, 10))
        if self.fonts:
            self.font_box.current(0)
        self.font_box.bind("<<ComboboxSelected>>", lambda _e: self._font_changed())
        ttk.Label(row, text="Size (px):").pack(side="left")
        self.size_var = tk.StringVar(master=self.window, value="27")
        self.size_box = ttk.Spinbox(row, from_=6, to=400, width=5, textvariable=self.size_var,
                                    command=self.schedule)
        self.size_box.pack(side="left", padx=(4, 10))
        self.size_box.bind("<KeyRelease>", lambda _e: self.schedule())
        ttk.Label(row, text="Align:").pack(side="left")
        self.align_keys = list(text.ALIGNMENTS)
        self.align_box = ttk.Combobox(row, values=list(text.ALIGNMENTS.values()), state="readonly", width=40)
        self.align_box.current(0)
        self.align_box.pack(side="left", padx=(4, 0))
        self.align_box.bind("<<ComboboxSelected>>", lambda _e: self.schedule())

        row2 = ttk.Frame(left)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Colour:").pack(side="left")
        self.colours = text.game_colours(self.game)
        self.colour_box = ttk.Combobox(row2, values=[c.name for c in self.colours] + [CUSTOM], state="readonly",
                                       width=44)
        self.colour_box.current(0)
        self.colour_box.pack(side="left", padx=(4, 10))
        self.colour_box.bind("<<ComboboxSelected>>", lambda _e: self._colour_changed())
        self.swatch = tk.Label(row2, width=3, relief="solid", borderwidth=1)
        self.swatch.pack(side="left", padx=(0, 10))
        ttk.Label(row2, text="Opacity:").pack(side="left")
        self.opacity_var = tk.StringVar(master=self.window, value="255")
        spin = ttk.Spinbox(row2, from_=1, to=255, width=4, textvariable=self.opacity_var, command=self.schedule)
        spin.pack(side="left", padx=(4, 0))
        spin.bind("<KeyRelease>", lambda _e: self.schedule())

        row3 = ttk.Frame(left)
        row3.pack(fill="x", pady=(6, 0))
        self.outlined_var = tk.BooleanVar(master=self.window, value=False)
        ttk.Checkbutton(row3, text="Outlined title (The Tree of Life's and New Believers' dark copies behind)",
                        variable=self.outlined_var, command=self.schedule).pack(side="left")
        row4 = ttk.Frame(left)
        row4.pack(fill="x", pady=(2, 0))
        self.mark_var = tk.BooleanVar(master=self.window, value=True)
        ttk.Checkbutton(row4, text="Outline the letters that are not the game's own (preview only)",
                        variable=self.mark_var, command=self.schedule).pack(side="left")
        self.stock_var = tk.BooleanVar(master=self.window, value=False)
        ttk.Checkbutton(row4, text="As the unpatched game draws it", variable=self.stock_var,
                        command=self.schedule).pack(side="left", padx=(12, 0))

        box = ttk.Frame(left)
        box.pack(fill="both", expand=True, pady=(8, 0))
        self.text_box = tk.Text(box, height=7, width=60, wrap="none", undo=True, font=("Segoe UI", 11))
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.text_box.yview)
        self.text_box.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text_box.pack(side="left", fill="both", expand=True)
        self.text_box.insert("1.0", SAMPLE)
        self.text_box.bind("<<Modified>>", self._modified)
        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(buttons, text="Insert character...", command=self.open_picker).pack(side="left")
        ttk.Button(buttons, text="Clear", command=lambda: self.set_text("")).pack(side="left", padx=(6, 0))
        self.name_label = ttk.Label(left, text="", wraplength=640, justify="left")
        self.name_label.pack(anchor="w", pady=(6, 0))
        note = ("Letters the game's font has are drawn from the game's own picture, exactly where the game puts "
                "them. Anything else is made in the font's style: an accented letter from the game's letter "
                "with the accent added, other letters and symbols from a Windows font sized and shaded to "
                "match, emoji in full colour.")
        ttk.Label(left, text=note, wraplength=640, justify="left", foreground="#555555").pack(anchor="w", pady=(6, 0))

        top = ttk.Frame(right)
        top.pack(fill="x")
        ttk.Label(top, text="Background:").pack(side="left")
        self.bg_box = ttk.Combobox(top, values=list(BACKGROUNDS), state="readonly", width=12)
        self.bg_box.current(0)
        self.bg_box.pack(side="left", padx=(4, 0))
        self.bg_box.bind("<<ComboboxSelected>>", lambda _e: self.schedule())
        holder = ttk.Frame(right)
        holder.pack(fill="both", expand=True, pady=(6, 0))
        self.canvas = tk.Canvas(holder, width=PREVIEW_W, height=PREVIEW_H, highlightthickness=1,
                                highlightbackground="#c0c0c0", background=BACKGROUNDS["Dark"])
        xs = ttk.Scrollbar(holder, orient="horizontal", command=self.canvas.xview)
        ys = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.info = ttk.Label(right, text="", wraplength=PREVIEW_W, justify="left")
        self.info.pack(anchor="w", pady=(6, 0))
        legend = ttk.Frame(right)
        legend.pack(anchor="w", pady=(2, 0))
        for source, label in ((text.SOURCE_PATCHER, "patcher-made"), (text.SOURCE_MADE, "generated"),
                              (text.SOURCE_EMOJI, "emoji")):
            tk.Label(legend, text="  ", background=MARK_COLOURS[source]).pack(side="left")
            ttk.Label(legend, text=label).pack(side="left", padx=(3, 10))
        ttk.Button(right, text="Save PNG...", command=self.save).pack(anchor="w", pady=(8, 0))
        self._font_changed(refresh=False)
        self._colour_changed(refresh=False)

    # ---- choices
    def font_key(self) -> str | None:
        index = self.font_box.current()
        return self.fonts[index][0] if 0 <= index < len(self.fonts) else None

    def _font_changed(self, refresh: bool = True) -> None:
        ttf = self.font_key() == text.TTF_KEY
        if not ttf:
            renderer = self.renderer()
            self.size_var.set(str(renderer.line_height) if renderer is not None else "")
        self.size_box.configure(state="normal" if ttf else "disabled")
        if refresh:
            self.schedule()

    def colour(self) -> int:
        try:
            opacity = max(1, min(255, int(self.opacity_var.get())))
        except ValueError:
            opacity = 255
        index = self.colour_box.current()
        if 0 <= index < len(self.colours):
            chosen = self.colours[index]
            rgb = chosen.rgb
            if chosen.alpha != 255 and opacity == 255:
                opacity = chosen.alpha
        else:
            rgb = self.custom_colour
        return text.colour_value(rgb, opacity)

    def _colour_changed(self, refresh: bool = True) -> None:
        if self.colour_box.get() == CUSTOM and refresh:
            picked = colorchooser.askcolor(color="#%02x%02x%02x" % self.custom_colour, parent=self.window,
                                           title="Text colour")
            if picked and picked[0]:
                self.custom_colour = tuple(int(v) for v in picked[0])
        value = self.colour()
        self.swatch.configure(background="#%02x%02x%02x" % (value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF))
        if refresh:
            self.schedule()

    def get_text(self) -> str:
        return self.text_box.get("1.0", "end-1c")

    def set_text(self, value: str) -> None:
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", value)
        self.schedule()

    def insert(self, value: str) -> None:
        self.text_box.insert("insert", value)
        self.text_box.focus_set()
        self.schedule()

    def _modified(self, _event=None) -> None:
        if self.text_box.edit_modified():
            self.text_box.edit_modified(False)
            self.schedule()

    def schedule(self) -> None:
        if self._after is not None:
            try:
                self.window.after_cancel(self._after)
            except tk.TclError:
                pass
        self._after = self.window.after(120, self.refresh)

    # ---- drawing
    def renderer(self) -> text.TextRenderer | None:
        key = self.font_key()
        if key is None:
            return None
        size = 27
        if key == text.TTF_KEY:
            try:
                size = max(6, min(400, int(self.size_var.get())))
            except ValueError:
                size = 27
        cache_key = (key, size)
        if cache_key not in self.renderers:
            self.renderers[cache_key] = text.TextRenderer(self.game, key, self.sheets.get(key), ttf_size=size,
                                                          images_dir=self.images_dir)
        return self.renderers[cache_key]

    def render(self) -> text.Rendered | None:
        renderer = self.renderer()
        if renderer is None:
            return None
        value = self.get_text()
        if self.stock_var.get() and renderer.font is not None:
            image = text.game_render(renderer.font, renderer.sheet, text.game_bytes(value), self.colour())
            return text.Rendered(image, counts={text.SOURCE_GAME: len(value)})
        align = self.align_keys[max(0, self.align_box.current())]
        effect = text.EFFECT_OUTLINED if self.outlined_var.get() else text.EFFECT_NONE
        return renderer.render(value, self.colour(), align, effect)

    def refresh(self) -> None:
        self._after = None
        self._show_name_fit()
        canvas = self.canvas
        canvas.delete("all")
        canvas.configure(background=BACKGROUNDS.get(self.bg_box.get(), BACKGROUNDS["Dark"]))
        if not self.fonts:
            self.studio.shown.pop("text", None)
            self.info.configure(text=self.problem or "The game's fonts were not found: click \"Find game...\".",
                                foreground="#a01010")
            return
        try:
            self.rendered = self.render()
        except Exception as exc:               # noqa: BLE001 -- shown, never fatal
            self.rendered = None
            self.studio.shown.pop("text", None)
            self.info.configure(text=f"This cannot be drawn: {exc}", foreground="#a01010")
            return
        if self.rendered is None:
            return
        image = self.rendered.image
        self.studio.shown["text"] = image
        shown = image.cropped(pi.MARGIN)
        offset = (image.bbox() or (0, 0, 0, 0))[:2]
        zoom = max(1, min(4, PREVIEW_W // max(1, shown.width), PREVIEW_H // max(1, shown.height)))
        photo = shown.photo(tk, self.window)
        if zoom > 1:
            photo = photo.zoom(zoom)
        canvas.create_image(0, 0, image=photo, anchor="nw")
        canvas.photo = photo
        if self.mark_var.get():
            ox, oy = offset[0] - pi.MARGIN, offset[1] - pi.MARGIN
            for x, y, w, h, source, _cluster in self.rendered.boxes:
                colour = MARK_COLOURS.get(source)
                if colour:
                    canvas.create_rectangle((x - ox) * zoom, (y - oy) * zoom, (x - ox + w) * zoom - 1,
                                            (y - oy + h) * zoom - 1, outline=colour, dash=(2, 2))
        canvas.configure(scrollregion=(0, 0, shown.width * zoom, shown.height * zoom))
        self.info.configure(text=self._summary(zoom), foreground="")

    def _summary(self, zoom: int) -> str:
        r = self.rendered
        parts = []
        for source in (text.SOURCE_GAME, text.SOURCE_PATCHER, text.SOURCE_MADE, text.SOURCE_EMOJI):
            n = r.counts.get(source, 0)
            if n:
                parts.append(f"{n} {text.SOURCE_LABELS[source]}")
        line = ", ".join(parts) or "Nothing to draw."
        if r.missing:
            line += f". {len(r.missing)} could not be drawn: {' '.join(r.missing[:10])}"
        size = f"{r.image.width} x {r.image.height} pixels at the game's size" + (f", shown {zoom}x" if zoom > 1 else "")
        return f"{line}.  {size}."

    def _show_name_fit(self) -> None:
        value = self.get_text()
        used = text.name_bytes(value)
        too_long = [f"{text.TITLES[g]} ({text.NAME_BYTES[g]})" for g in text.TITLES if used > text.NAME_BYTES[g]]
        if "\n" in value:
            fit = "a name is one line"
        elif not too_long:
            fit = "fits every game's name field"
        else:
            fit = "too long for " + ", ".join(too_long)
        mine = text.NAME_BYTES[self.game]
        self.name_label.configure(
            text=f"As a villager name: {used} bytes of UTF-8 ({text.TITLES[self.game]} holds {mine}); {fit}.",
            foreground="#a01010" if used > mine or "\n" in value else "")

    # ---- saving
    def picture_name(self) -> str:
        first = next((line for line in self.get_text().splitlines() if line.strip()), "text")
        return pi.safe_file_name(first[:40])

    def save(self, path: str | None = None):
        if self.studio.shown.get("text") is None:
            self.refresh()
        if path is None:
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(parent=self.window, title="Save PNG", defaultextension=".png",
                                                initialfile=self.picture_name() + ".png",
                                                filetypes=[("PNG picture", "*.png")])
        if not path:
            return None
        return self.studio.save_png("text", path)

    # ---- the character picker
    def open_picker(self) -> "CharacterPicker":
        return CharacterPicker(self)


class CharacterPicker:
    """"Insert character...": search by name or code point, the common accented letters, the combining
    accents (typed after a letter), or any code point."""

    def __init__(self, tab: TextTab) -> None:
        self.tab = tab
        w = self.window = tk.Toplevel(tab.window)
        w.title("Insert character")
        w.transient(tab.window)
        w.bind("<Escape>", lambda _e: w.destroy())
        outer = ttk.Frame(w, padding=10)
        outer.pack(fill="both", expand=True)
        search = ttk.Frame(outer)
        search.pack(fill="x")
        ttk.Label(search, text="Search (a name like \"e acute\", \"smiling face\", or a code like U+00E9):").pack(anchor="w")
        self.query = tk.StringVar(master=w)
        entry = ttk.Entry(search, textvariable=self.query, width=50)
        entry.pack(side="left", fill="x", expand=True, pady=(2, 0))
        entry.bind("<Return>", lambda _e: self.search())
        ttk.Button(search, text="Search", command=self.search).pack(side="left", padx=(6, 0))
        lists = ttk.Frame(outer)
        lists.pack(fill="both", expand=True, pady=(6, 0))
        self.results = tk.Listbox(lists, height=10, width=70, font=("Segoe UI", 11))
        scroll = ttk.Scrollbar(lists, orient="vertical", command=self.results.yview)
        self.results.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.results.pack(side="left", fill="both", expand=True)
        self.results.bind("<Double-Button-1>", lambda _e: self.insert_selected())
        self.results.bind("<Return>", lambda _e: self.insert_selected())
        self.found: list[str] = []
        ttk.Button(outer, text="Insert", command=self.insert_selected).pack(anchor="e", pady=(4, 0))

        palette = ttk.LabelFrame(outer, text="Accented letters and punctuation (click to insert)", padding=6)
        palette.pack(fill="x", pady=(8, 0))
        self._grid(palette, text.COMMON_ACCENTS, 32)
        marks = ttk.LabelFrame(outer, text="Accents to put on the letter before the cursor", padding=6)
        marks.pack(fill="x", pady=(8, 0))
        self._grid(marks, text.COMBINING_MARKS[:48], 24, combining=True)
        entry.focus_set()

    def _grid(self, parent, chars, columns: int, combining: bool = False) -> None:
        for i, ch in enumerate(chars):
            shown = "◌" + ch if combining else ch
            b = tk.Button(parent, text=shown, width=2, relief="groove", font=("Segoe UI", 10),
                          command=lambda c=ch: self.tab.insert(c))
            b.grid(row=i // columns, column=i % columns, padx=1, pady=1)
            b.bind("<Enter>", lambda _e, c=ch: self.window.title(f"Insert character: {text.char_name(c)}"))

    def search(self) -> None:
        self.found = text.search_characters(self.query.get())
        self.results.delete(0, "end")
        for ch in self.found:
            cat = unicodedata.category(ch)
            shown = ("◌" + ch) if cat.startswith("M") else ch
            self.results.insert("end", f"{shown}    U+{ord(ch):04X}    {text.char_name(ch).title()}")
        if self.found:
            self.results.selection_set(0)

    def insert_selected(self) -> None:
        selection = self.results.curselection()
        if selection and selection[0] < len(self.found):
            self.tab.insert(self.found[selection[0]])
