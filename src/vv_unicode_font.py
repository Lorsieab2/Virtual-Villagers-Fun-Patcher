"""Unicode Font (Tools tab -> "Unicode Font..."): pick the typeface "Use Unicode Font (overrides in-game fonts)" draws all
of a game's text with, and see each of the game's two fonts drawn with it as the game will draw them.

Any font installed in Windows (with a search) or a .ttf / .otf / .ttc file.  The choice is the one the patch-selection
"Unicode Font" box and the command line's --unicode-font already write (vv_fun_patcher.set_unicode_font_face), plus the
font FILE when one is chosen (--unicode-font-file / set_unicode_font_file): at the next patch the face goes on the first
line of "VVFP Unicode Font.txt" beside "VVFP Unicode Font.dll" and the file is copied into a "Unicode Font" folder there,
named on the second line; the companion loads it for the game only (AddFontResourceExW with FR_PRIVATE).  A re-patch
keeps the choice (patcher_local_settings.json).  Nothing here touches a game or a save.

The preview is the companion's own arithmetic (native/vvfp_unicode_text/runtime_glyphs.inc): each game font keeps its line
height, baseline and weight; the face's em is fitted so that "The quick brown fox jumps over the lazy dog 0123456789" is
as wide as the game font draws it, within 60% to 130% of the game font's own em (fit_em), and a character the face lacks
comes from the shared fallback chain (FALLBACK_CHAIN).
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import vv_font_glyphs as vfg

TITLE = "Unicode Font"
DEFAULT_FACE = "Segoe UI"
FIT_REFERENCE = "The quick brown fox jumps over the lazy dog 0123456789"
SAMPLE = "The Smith Family – Zoë, İlkay, Łukasz 日本 \U0001f44d"
FONT_FILES = (("Font files", "*.ttf *.otf *.ttc"), ("All files", "*.*"))
FONT_SUFFIXES = (".ttf", ".otf", ".ttc")
GAME_FONTS = ("ldwBurweed27", "ldwarialbold")
GAME_FONT_NAMES = {"ldwBurweed27": "Burweed (titles and names)", "ldwarialbold": "Arial Bold (text)"}

# The shared fallback chain (UNICODE_SPEC section 3) in the order native/vvfp_unicode_text/runtime_glyphs.inc tries it
# (tests/test_unicode_parity_ui.py keeps the two lists in step).  With Use Unicode Font the chosen face comes first.
FALLBACK_CHAIN = (
    "Segoe UI", "Segoe UI Historic", "Segoe UI Symbol", "Segoe UI Emoji", "Yu Gothic UI", "Yu Gothic", "Meiryo",
    "Microsoft YaHei UI", "Microsoft YaHei", "Microsoft JhengHei UI", "Malgun Gothic", "SimSun-ExtB", "Nirmala UI",
    "Ebrima", "Gadugi", "Leelawadee UI", "Myanmar Text", "Javanese Text", "Mongolian Baiti", "Microsoft Himalaya",
    "Microsoft Yi Baiti", "Microsoft New Tai Lue", "Microsoft Tai Le", "Microsoft PhagsPa", "Sylfaen", "Cambria Math",
    "Noto Sans", "Noto Sans Symbols", "Noto Sans Symbols 2", "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans Math",
    "Noto Sans Cuneiform", "Noto Color Emoji",
)


class FontChoiceError(Exception):
    """A choice that cannot be used, with a reason a player can read."""


# ---------------------------------------------------------------------------------------------------
# The arithmetic (the companion's rg_ppem / rg_fit_em, in whole numbers)

def own_em(cap: int) -> int:
    """The game font's own em: the one a face with Arial's capitals (716 per 1000 em) has at this cap height."""
    return (cap * 1000 + 358) // 716


def fit_em(own: int, game_width: int, face_width: int, probe: int = 200) -> int:
    """The em at which FIT_REFERENCE is as wide in the face as the game font draws it (`face_width` is its width at
    `probe` pixels per em), kept within 60% to 130% of `own`; `own` when either width is unknown."""
    if game_width <= 0 or face_width <= 0:
        return own
    em = (probe * game_width * 2 + face_width) // (2 * face_width)
    return max(own * 6 // 10, min(own * 13 // 10, em))


# ---------------------------------------------------------------------------------------------------
# Fonts

def font_file_family(data: bytes) -> str | None:
    """The family name of a TrueType / OpenType file (a collection's first font), or None."""
    return vfg.ttf_family(data)


def check_font_file(path: str | Path) -> tuple[Path, str]:
    """(the file, its family) for a font file the game can load; FontChoiceError otherwise."""
    path = Path(path)
    if path.suffix.lower() not in FONT_SUFFIXES:
        raise FontChoiceError("Choose a .ttf, .otf or .ttc font file.")
    try:
        family = font_file_family(path.read_bytes())
    except OSError as exc:
        raise FontChoiceError(f"{path.name} cannot be read: {exc}") from exc
    if not family:
        raise FontChoiceError(f"{path.name} is not a font file Windows can use.")
    return path, family


def installed_faces() -> list[str]:
    """Every font family Windows has, as Tk lists them (vertical "@" faces and names longer than the companion's 63
    characters left out)."""
    import tkinter.font as tkfont
    names = {name for name in tkfont.families() if not name.startswith("@") and len(name) <= 63}
    return sorted(names, key=str.casefold)


def add_private_font(path: Path) -> bool:
    """Make a font file available to this process only (FR_PRIVATE), as the companion does in the game."""
    if sys.platform != "win32":
        return False
    import ctypes
    add = ctypes.WinDLL("gdi32").AddFontResourceExW
    add.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
    return add(str(path), 0x10, None) > 0


# ---------------------------------------------------------------------------------------------------
# The preview: a game font's text drawn with the chosen face

def render(game: str, font: str, face: str, text: str, images_dir):
    """`text` on one line in `face`, as "Use Unicode Font" draws it in `font` of `game` (vv_picture_image.Image), or
    None where this machine cannot draw (no Windows GDI).  Windows shapes each run of one script as a whole
    (Uniscribe: joined Arabic, combining marks, ZWJ emoji), in the first face of the chain that has every glyph of it
    (the chosen face first); the game's own letters are never used."""
    from vv_picture_image import Image
    glyphs = vfg._font(game, font, images_dir)
    gdi = glyphs.gdi
    if gdi is None:
        return None
    m = glyphs.metrics
    drawer = _Drawer(gdi, glyphs, face, m.baseline - m.cap_top)
    cells = drawer.cells(text)
    width = max(1, sum(w for w, _mask in cells) + m.spacing * len(cells))
    out = Image.new(width, m.line)
    x = 0
    for w, mask in cells:
        if mask is not None:
            tile = Image(mask.w, mask.h, bytearray(b"".join(bytes((255, 255, 255, a)) for a in mask.px)))
            out.draw(tile, x, 0)
        x += w + m.spacing
    return out


class _Run:
    """Glyphs of a run of text shaped in one face: glyph ids, advances, offsets (Uniscribe's, in visual order)."""

    def __init__(self, glyphs: list[int], advances: list[int], offsets: list[tuple[int, int]]) -> None:
        self.glyphs, self.advances, self.offsets = glyphs, advances, offsets


def _usp():
    import ctypes
    usp = ctypes.WinDLL("usp10")
    c = ctypes
    usp.ScriptItemize.argtypes = [c.c_wchar_p, c.c_int, c.c_int, c.c_void_p, c.c_void_p, c.c_void_p,
                                  c.POINTER(c.c_int)]
    usp.ScriptShape.argtypes = [c.c_void_p, c.POINTER(c.c_void_p), c.c_wchar_p, c.c_int, c.c_int, c.c_void_p,
                                c.c_void_p, c.c_void_p, c.c_void_p, c.POINTER(c.c_int)]
    usp.ScriptPlace.argtypes = [c.c_void_p, c.POINTER(c.c_void_p), c.c_void_p, c.c_int, c.c_void_p, c.c_void_p,
                                c.c_void_p, c.c_void_p, c.c_void_p]
    usp.ScriptLayout.argtypes = [c.c_int, c.c_void_p, c.c_void_p, c.c_void_p]
    usp.ScriptGetFontProperties.argtypes = [c.c_void_p, c.POINTER(c.c_void_p), c.c_void_p]
    return usp


def items(text: str) -> list[tuple[int, int, bytes, int]]:
    """Windows' runs of `text` (ScriptItemize): (start, end) in UTF-16 units, the run's analysis (4 bytes) and its bidi
    level, in logical order."""
    import ctypes
    n = len(text.encode("utf-16-le")) // 2
    if n == 0:
        return []
    cap = n + 2
    buf = (ctypes.c_ubyte * (8 * (cap + 1)))()
    count = ctypes.c_int(0)
    if _usp().ScriptItemize(text, n, cap, None, None, buf, ctypes.byref(count)) != 0:
        return []
    out = []
    raw = bytes(buf)
    for i in range(count.value):
        pos = int.from_bytes(raw[8 * i:8 * i + 4], "little")
        end = int.from_bytes(raw[8 * (i + 1):8 * (i + 1) + 4], "little")
        analysis = raw[8 * i + 4:8 * i + 8]
        level = int.from_bytes(analysis[2:4], "little") & 0x1F
        out.append((pos, end, analysis, level))
    return out


def shape_run(gdi, cache: dict, name: str, ppem: int, text: str, analysis: bytes):
    """`text` (one run) shaped and placed in the face selected at `ppem` (Uniscribe ScriptShape + ScriptPlace); None
    when the face lacks a glyph of it."""
    import ctypes
    c = ctypes
    usp = _usp()
    gdi._select(name, 700, ppem)
    n = len(text.encode("utf-16-le")) // 2
    cap = 3 * n + 16
    sc = cache.setdefault((name, ppem), c.c_void_p())
    analysis_buf = (c.c_ubyte * 4)(*analysis)
    glyphs = (c.c_ushort * cap)()
    clusters = (c.c_ushort * cap)()
    attrs = (c.c_ushort * cap)()
    total = c.c_int(0)
    if usp.ScriptShape(gdi.dc, c.byref(sc), text, n, cap, analysis_buf, glyphs, clusters, attrs, c.byref(total)) != 0:
        return None
    count = total.value
    props = (c.c_ubyte * 16)()
    c.cast(props, c.POINTER(c.c_int))[0] = 16
    default = None
    if usp.ScriptGetFontProperties(gdi.dc, c.byref(sc), props) == 0:
        default = c.cast(c.byref(props, 6), c.POINTER(c.c_ushort))[0]            # wgDefault
    for i in range(count):
        if (glyphs[i] == default or glyphs[i] == 0) and not attrs[i] & 0x40:        # a zero-width joiner is no gap
            return None
    advances = (c.c_int * count)()
    offsets = (c.c_int * (2 * count))()
    abc = (c.c_int * 3)()
    if usp.ScriptPlace(gdi.dc, c.byref(sc), glyphs, count, attrs, analysis_buf, advances, offsets, abc) != 0:
        return None
    return _Run([glyphs[i] for i in range(count)], [advances[i] for i in range(count)],
                [(offsets[2 * i], offsets[2 * i + 1]) for i in range(count)])


class _Drawer:
    def __init__(self, gdi, glyphs, face: str, cap: int) -> None:
        self.gdi, self.glyphs, self.face = gdi, glyphs, face
        self.cap = cap
        self.metrics = glyphs.metrics
        self.own = own_em(cap)
        self.ems: dict[str, int] = {}
        self.bold: dict[str, int] = {}
        self.target = glyphs.sheet.box(ord("H")).total()
        self.caches: dict = {}

    def faces(self):
        for name in (self.face,) + FALLBACK_CHAIN:
            if self.gdi.has_face(name, 700):
                yield name

    def indexed(self, name: str, ppem: int, glyph: int):
        """(mask, rows above the baseline, columns from the pen, advance) of a glyph by index (GGO_GLYPH_INDEX)."""
        gdi = self.gdi
        gm = gdi.GLYPHMETRICS()
        one, zero = gdi.FIXED(0, 1), gdi.FIXED(0, 0)
        mat = gdi.MAT2(one, zero, zero, one)
        gdi._select(name, 700, ppem)
        size = gdi.gdi.GetGlyphOutlineW(gdi.dc, glyph, 0x80 | 6, gdi.ct.byref(gm), 0, None, gdi.ct.byref(mat))
        if size == 0xFFFFFFFF:
            return None, 0, 0, 0
        if size == 0:
            return None, 0, 0, gm.gmCellIncX
        buf = (gdi.ct.c_ubyte * size)()
        gdi.gdi.GetGlyphOutlineW(gdi.dc, glyph, 0x80 | 6, gdi.ct.byref(gm), size, buf, gdi.ct.byref(mat))
        w, h = gm.gmBlackBoxX, gm.gmBlackBoxY
        pitch = (w + 3) & ~3
        mask = vfg.Mask.blank(w, h)
        for y in range(h):
            for x in range(w):
                v = buf[y * pitch + x]
                mask.px[y * w + x] = (v * 255 + 32) // 64 if v < 64 else 255
        return mask, gm.gmptGlyphOrigin.y, gm.gmptGlyphOrigin.x, gm.gmCellIncX

    def em(self, name: str) -> int:
        if name not in self.ems:
            if name == self.face:
                game = self.glyphs.text_width(FIT_REFERENCE)
                probe = sum(self.advance(name, 200, c) for c in FIT_REFERENCE)
                self.ems[name] = fit_em(self.own, game, probe)
            else:
                # a fallback face: the em at which its capital H is as tall as the game font's
                best = self.own
                for ppem in range(6, 81):
                    r = self.gdi.raster(name, 700, ppem, "H")
                    if r is not None and r[0].h >= self.cap:
                        best = ppem
                        break
                self.ems[name] = best
        return self.ems[name]

    def advance(self, name: str, ppem: int, ch: str) -> int:
        gm = self.gdi.GLYPHMETRICS()
        one, zero = self.gdi.FIXED(0, 1), self.gdi.FIXED(0, 0)
        mat = self.gdi.MAT2(one, zero, zero, one)
        self.gdi._select(name, 700, ppem)
        size = self.gdi.gdi.GetGlyphOutlineW(self.gdi.dc, ord(ch), 0, self.gdi.ct.byref(gm), 0, None,
                                             self.gdi.ct.byref(mat))     # GGO_METRICS
        return gm.gmCellIncX if size != 0xFFFFFFFF else 0

    def thickness(self, name: str, ppem: int) -> int:
        """Thickening steps, as the companion: while the face's H is lighter than the game font's own."""
        if name not in self.bold:
            steps = 0
            r = self.gdi.raster(name, 700, ppem, "H")
            if r is not None:
                m = r[0]
                while steps < 2 and m.total() * 100 < self.target * 85:
                    m = vfg._embolden(m)
                    steps += 1
            self.bold[name] = steps
        return self.bold[name]

    def shaped(self, text: str, analysis: bytes):
        """(face, ppem, _Run) for the first face that has every glyph of the run, or None."""
        for name in self.faces():
            ppem = self.em(name)
            run = shape_run(self.gdi, self.caches, name, ppem, text, analysis)
            if run is not None:
                return name, ppem, run
        return None

    def cells(self, text: str):
        """[(advance, mask)] one per run of `text`, in visual order: the run's glyphs drawn side by side at their placed
        offsets on the font's baseline."""
        import ctypes
        m = self.metrics
        pieces = items(text)
        if not pieces:
            return []
        units = text.encode("utf-16-le")
        order = list(range(len(pieces)))
        levels = (ctypes.c_ubyte * len(pieces))(*[p[3] for p in pieces])
        visual = (ctypes.c_int * len(pieces))()
        if _usp().ScriptLayout(len(pieces), levels, visual, None) == 0:
            order = [visual[i] for i in range(len(pieces))]          # visual position -> logical run
        out = []
        for index in order:
            start, end, analysis, _level = pieces[index]
            run_text = units[2 * start:2 * end].decode("utf-16-le")
            found = self.shaped(run_text, analysis)
            if found is None:
                out.append((m.left + m.right + 4, None))       # no face has it: the game draws Segoe UI's missing box
                continue
            name, ppem, run = found
            out.append(self.draw(name, ppem, run))
        return out

    def draw(self, name: str, ppem: int, run: _Run):
        m = self.metrics
        pad = 4
        total = sum(run.advances)
        canvas = vfg.Mask.blank(total + 2 * pad + ppem, m.line)
        pen = 0
        steps = self.thickness(name, ppem)
        for glyph, advance, (du, dv) in zip(run.glyphs, run.advances, run.offsets):
            mask, above, left, _cell = self.indexed(name, ppem, glyph)
            if mask is not None and mask.w:
                for _ in range(steps):
                    mask = vfg._embolden(mask)
                x0 = pad + pen + du + left
                y0 = m.baseline - above - dv
                for y in range(mask.h):
                    for x in range(mask.w):
                        cx, cy = x0 + x, y0 + y
                        if 0 <= cx < canvas.w and 0 <= cy < canvas.h:
                            i = cy * canvas.w + cx
                            canvas.px[i] = max(canvas.px[i], mask.px[y * mask.w + x])
            pen += advance
        return total, _crop(canvas, pad, total)


def _crop(canvas, pad: int, total: int):
    """The cell of a run: from its pen start (`pad` columns in) to the end of its advance or its ink."""
    ink = canvas.ink()
    right = max(pad + total, ink[2] + 1) if ink else pad + total
    return canvas.crop(pad, 0, right, canvas.h) if right > pad else None


# ---------------------------------------------------------------------------------------------------
# The window

_open_window = None


def open_window(parent: tk.Misc, *, images_dirs=None, get_choice=None, set_choice=None, show_help=None,
                hold=None) -> "UnicodeFontWindow":
    """Open (or raise) the window.  get_choice() -> (face, font file or None); set_choice(face, file) stores it
    (the patcher window's Unicode Font box and its saved settings); images_dirs: {"vv1": Path, ...} of folders that
    hold each game's font pictures (the preview needs one)."""
    global _open_window
    if _open_window is not None and _open_window.window.winfo_exists():
        _open_window.window.deiconify()
        _open_window.window.lift()
        return _open_window
    _open_window = UnicodeFontWindow(parent, images_dirs or {}, get_choice, set_choice, show_help, hold)
    return _open_window


class UnicodeFontWindow:
    def __init__(self, parent, images_dirs, get_choice, set_choice, show_help, hold) -> None:
        self.window = tk.Toplevel(parent)
        self.window.title(TITLE)
        self.window.geometry("900x660")
        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.images_dirs = {k: Path(v) for k, v in images_dirs.items() if v}
        self.get_choice, self.set_choice, self.show_help = get_choice, set_choice, show_help
        self.search_var = tk.StringVar(master=self.window)
        self.game_var = tk.StringVar(master=self.window)
        self.sample_var = tk.StringVar(master=self.window, value=SAMPLE)
        self.status_var = tk.StringVar(master=self.window)
        self.face, self.font_file = DEFAULT_FACE, None
        self.quiet = False
        self.last_message = ""
        self._photos: list = []
        self.faces = installed_faces()
        self._build()
        if get_choice is not None:
            face, file = get_choice()
            self.set_face(face or DEFAULT_FACE, Path(file) if file else None)
        else:
            self.set_face(DEFAULT_FACE)
        if hold is not None:
            hold(self.window)

    def _build(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="Preview game:").pack(side="left")
        games = [f"{n}" for n in sorted(self.images_dirs)] or ["(no game pictures found)"]
        box = ttk.Combobox(top, textvariable=self.game_var, values=games, state="readonly", width=10)
        box.pack(side="left", padx=4)
        self.game_var.set(games[0])
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        ttk.Label(top, text="Text:").pack(side="left", padx=(12, 0))
        entry = ttk.Entry(top, textvariable=self.sample_var, width=44)
        entry.pack(side="left", padx=4)
        entry.bind("<KeyRelease>", lambda _e: self.refresh())
        if self.show_help is not None:
            ttk.Button(top, text="?", width=2, command=self.show_help).pack(side="right")
        ttk.Label(outer, textvariable=self.status_var, foreground="#245a9a", wraplength=860, justify="left").pack(
            anchor="w", pady=(6, 0))
        middle = ttk.Frame(outer)
        middle.pack(fill="both", expand=True, pady=(8, 0))
        left = ttk.Frame(middle)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Installed fonts (search):").pack(anchor="w")
        ttk.Entry(left, textvariable=self.search_var, width=34).pack(anchor="w", fill="x")
        self.search_var.trace_add("write", lambda *_a: self.fill_faces())
        holder = ttk.Frame(left)
        holder.pack(fill="y", expand=True, pady=(4, 0))
        self.face_list = tk.Listbox(holder, width=34, height=20, exportselection=False)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.face_list.yview)
        self.face_list.configure(yscrollcommand=scroll.set)
        self.face_list.pack(side="left", fill="y")
        scroll.pack(side="left", fill="y")
        self.face_list.bind("<<ListboxSelect>>", lambda _e: self.face_picked())
        ttk.Button(left, text="Choose a font file...", command=self.choose_file).pack(anchor="w", pady=(6, 0))
        ttk.Button(left, text="Segoe UI (the default)", command=lambda: self.set_face(DEFAULT_FACE)).pack(
            anchor="w", pady=(4, 0))
        right = ttk.Frame(middle)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(right, text="How the game's two fonts will look (drawn as the game will draw them):").pack(anchor="w")
        self.canvas = tk.Canvas(right, background="#28407a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=(4, 0))
        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Save", command=self.save).pack(side="right")
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right", padx=(0, 8))
        self.fill_faces()

    def fill_faces(self) -> None:
        term = self.search_var.get().strip().casefold()
        self.shown_faces = [f for f in self.faces if term in f.casefold()]
        self.face_list.delete(0, "end")
        for f in self.shown_faces:
            self.face_list.insert("end", f)

    def face_picked(self) -> None:
        picked = self.face_list.curselection()
        if picked:
            self.set_face(self.shown_faces[picked[0]])

    def set_face(self, face: str, font_file: Path | None = None) -> None:
        self.face, self.font_file = face, font_file
        if font_file is not None:
            add_private_font(font_file)
        where = f" (from the file {font_file.name})" if font_file else ""
        self.status_var.set(f"Chosen: {face}{where}.  Use Unicode Font draws every character with it; one it lacks comes "
                            "from the fallback fonts (Segoe UI, Segoe UI Symbol, Segoe UI Emoji in colour, the CJK fonts...).")
        self.refresh()

    def choose_file(self, path: str | None = None) -> None:
        if path is None:
            path = filedialog.askopenfilename(parent=self.window, title="Choose a font file", filetypes=FONT_FILES)
            if not path:
                return
        try:
            file, family = check_font_file(path)
        except FontChoiceError as exc:
            self._message("error", str(exc))
            return
        self.set_face(family, file)

    def refresh(self) -> None:
        self.canvas.delete("all")
        self._photos = []
        game = self.game_var.get()
        folder = self.images_dirs.get(game)
        if folder is None:
            self.canvas.create_text(10, 10, anchor="nw", fill="#ffffff",
                                    text="Find a game with Picture Studio first: the preview draws on the game's own fonts.")
            return
        y = 8
        for font in GAME_FONTS:
            try:
                picture = render(game, font, self.face, self.sample_var.get(), folder)
            except Exception as exc:                       # noqa: BLE001 -- shown, never fatal
                self.canvas.create_text(8, y, anchor="nw", fill="#ff8080", text=f"{font}: {exc}")
                y += 20
                continue
            self.canvas.create_text(8, y, anchor="nw", fill="#ffffff", text=f"{GAME_FONT_NAMES[font]}, {self.face}")
            y += 18
            if picture is None:
                continue
            photo = picture.photo(tk, self.window)
            self._photos.append(photo)
            self.canvas.create_image(8, y, image=photo, anchor="nw")
            y += picture.height + 14

    def save(self):
        if self.set_choice is None:
            self._message("error", "This window is not connected to the patcher.")
            return None
        try:
            self.set_choice(self.face, self.font_file)
        except Exception as exc:                          # noqa: BLE001 -- shown
            self._message("error", str(exc))
            return None
        self.status_var.set(f"Saved: {self.face} is used the next time you patch a game with Use Unicode Font ticked.")
        return self.face

    def _message(self, kind: str, text: str) -> None:
        self.last_message = text
        if self.quiet:
            return
        (messagebox.showerror if kind == "error" else messagebox.showinfo)(TITLE, text, parent=self.window)

    def close(self) -> None:
        global _open_window
        if _open_window is self:
            _open_window = None
        if self.window.winfo_exists():
            self.window.destroy()
