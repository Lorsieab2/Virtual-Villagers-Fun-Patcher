"""Picture Studio's Text tab: any text, drawn in the games' own bitmap fonts (docs/picture-studio-text.md).

Every game builds exactly two bitmap fonts, from two white glyph sheets in its Images folder:

* "Arial Bold (game font)": ldwarialbold.png, 20 pixels a line (the dialogs, labels and buttons);
* "Burweed (game font)": ldwBurweed27.png, 27 pixels a line (the titles and the renderer's default font).

Their glyph tables (which cell of the sheet each byte is) are compiled into the executables; they are kept,
numbers only, in data/vv_font_tables.json (scripts/build_vv_font_tables.py reads them from the stock
executables).  The sheets themselves are the player's own, copied once from the game folder into "Picture
Studio Pictures\\Fonts" (vv_picture_image.picture_source); no game art ships.

The game's way (proven in tests/test_pictures_text.py by running each game's own loader and text draw in
Unicorn and comparing every blit with `game_plan`):

* the loader (A New Home 0x402240; the same code in every game) walks the table keeping a running x / y shift,
  wraps an entry whose right edge passes the sheet's width onto the next row (line height + 1 down), masks
  the byte codes 0x80-0xFF stored as negative numbers, and indexes each byte to the FIRST entry with that
  code -- a byte with no entry gets entry 0 (A New Home and The Lost Children: "A"; the later games: "!");
* the draw (A New Home 0x409160) takes the text as bytes: "\\n" goes back to the start x and down one line
  height; every other byte's cell is blitted at the pen and the pen moves by the cell's width plus the
  font's letter spacing (1 for A New Home's and The Lost Children's Arial Bold, else 0); a zero-width cell
  is neither drawn nor advanced;
* colour is 0xAABBGGRR: the sheet's pixels are ANDed with the colour (white leaves the sheet as it is; the
  alpha channel is kept), and an alpha below 255 fades the blit (the games' surface alpha); alpha 0 means
  the default, opaque white;
* centred text (0x4094C0) starts at cx - trunc(width / 2), every line at the same x; the width (0x402160)
  is, per line, the sum of each cell's width plus spacing, the widest line, less one spacing.

Any Unicode text is drawn: the text is cut into grapheme clusters (emoji sequences, flags and a letter with
its accents stay whole) and each cluster is drawn from, in this order,
  (a) the game's own glyph (the cluster in Windows-1252 is a byte the sheet has a cell for);
  (b) the patcher's own glyph for that font, when the patcher has one (`patcher_glyph`, the in-game accented
      letters' art, src/vv_font_glyphs.py when present);
  (c) a glyph made in the font's style: a letter with accents is the base letter (a or b) with each accent
      generated and placed on it (unicodedata NFD), a compatibility form is its parts (NFKD), anything else
      is drawn from a Windows font sized to the sheet's cap height and quantised to its alpha levels
      (src/vv_glyph_maker.py), emoji in full colour.
Generated glyphs are marked in the preview (`Rendered.boxes`), never in the exported PNG.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import vv_picture_image as pi

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "data" / "vv_font_tables.json"
TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
FONT_KEYS = ("arialbold", "burweed")
CACHE_SUBFOLDER = "Fonts"                 # "Picture Studio Pictures\\Fonts\\<game>": the sheets, apart from the villagers'
TTF_KEY = "burweed-icg"                   # the installed Burweed ICG TrueType font, any size
TTF_FACE = "Burweed ICG"
TTF_NAME = "Burweed ICG (installed)"
DEFAULT_COLOUR = 0xFFFFFFFF               # every game's default text colour (A New Home [0x486118])

# A villager's name field, in bytes before its closing NUL (scripts/vvfp_consistency_check.py LAYOUTS:
# A New Home 0x1C, The Lost Children 0x18, the later three 0x19).  The games keep names as UTF-8 (invalid
# UTF-8 is read as Windows-1252), so a name's size is its UTF-8 length.
NAME_BYTES = {1: 27, 2: 23, 3: 24, 4: 24, 5: 24}

SOURCE_GAME, SOURCE_PATCHER, SOURCE_MADE, SOURCE_EMOJI = "game", "patcher", "generated", "emoji"
SOURCE_LABELS = {SOURCE_GAME: "the game's own", SOURCE_PATCHER: "patcher-made", SOURCE_MADE: "generated",
                 SOURCE_EMOJI: "emoji (generated, full colour)"}

ALIGN_LEFT, ALIGN_CENTRE, ALIGN_CENTRE_LINES, ALIGN_RIGHT = "left", "centre", "centre-lines", "right"
ALIGNMENTS = {
    ALIGN_LEFT: "Left (the game's text draw)",
    ALIGN_CENTRE: "Centred (the game's: every line starts where the widest starts)",
    ALIGN_CENTRE_LINES: "Centre each line",
    ALIGN_RIGHT: "Right",
}
EFFECT_NONE, EFFECT_OUTLINED = "none", "outlined"


# --------------------------------------------------------------------------------------- the colours

@dataclass(frozen=True)
class GameColour:
    name: str
    value: int                     # 0xAABBGGRR, as the game passes it
    games: tuple = (1, 2, 3, 4, 5)

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self.value & 0xFF, (self.value >> 8) & 0xFF, (self.value >> 16) & 0xFF

    @property
    def alpha(self) -> int:
        return (self.value >> 24) & 0xFF


def _c(r: int, g: int, b: int, a: int = 0xFF) -> int:
    return a << 24 | b << 16 | g << 8 | r


# The colours the games draw text in: every call of every text draw, and the button and label colour
# setters, read from the executables (docs/picture-studio-text.md "The colours").  The many draws whose
# colour is a zero constant are drawn in the default white.
GAME_COLOURS = (
    GameColour("White (the default; most text)", DEFAULT_COLOUR),
    GameColour("Black (button labels)", _c(0, 0, 0)),
    GameColour("Dark grey (a button label pointed at or pressed)", _c(0x55, 0x55, 0x55)),
    GameColour("Dark brown (labels)", _c(0x45, 0x22, 0x00)),
    GameColour("Dark olive (some buttons)", _c(0x33, 0x33, 0x00), (2, 3, 4, 5)),
    GameColour("Charcoal (labels)", _c(0x22, 0x22, 0x22), (1, 2, 3)),
    GameColour("Dark green (a label)", _c(0x00, 0x99, 0x00), (1,)),
    GameColour("Light grey", _c(0xDC, 0xDC, 0xDC), (3,)),
    GameColour("Disabled grey (half see-through, over a label)", _c(0x64, 0x64, 0x64, 0x80)),
    GameColour("Cream (the pulsing message)", _c(0xF5, 0xEA, 0xD1), (4, 5)),
    GameColour("Yellow (the pulsing message)", _c(0xFA, 0xE6, 0x00), (4, 5)),
    GameColour("Pale cream (labels)", _c(0xF4, 0xE9, 0xC9), (4, 5)),
    GameColour("Pale grey (a label)", _c(0xD2, 0xCC, 0xC4), (4, 5)),
    GameColour("Light cyan (the outlined title)", _c(0x62, 0xE7, 0xF5), (4, 5)),
    GameColour("Dark teal (the outlined title's shadow)", _c(0x13, 0x51, 0x68), (4, 5)),
    GameColour("Green (buttons, labels)", _c(0x00, 0xFF, 0x00), (1, 4, 5)),
)
# The Tree of Life's and New Believers' outlined title (0x43CE79 / 0x43F749): two dark teal copies of the
# text at (-1, -1) and (+2, +2), then the light copy.
OUTLINE_COPIES = ((-1, -1), (2, 2))
OUTLINE_SHADOW = _c(0x13, 0x51, 0x68)


def game_colours(game: int) -> list[GameColour]:
    return [c for c in GAME_COLOURS if game in c.games]


def colour_value(rgb: tuple[int, int, int], alpha: int = 255) -> int:
    r, g, b = rgb
    return _c(r, g, b, alpha)


# ---------------------------------------------------------------------------------------- the fonts

class TextError(pi.PictureError):
    """Text that cannot be drawn, in words for the player."""


@lru_cache(maxsize=1)
def _tables() -> dict:
    data = json.loads(TABLES.read_text(encoding="utf-8"))
    if data.get("format") != "Virtual Villagers Fun Patcher: game font tables" or data.get("version") != 1:
        raise TextError("The font tables (data\\vv_font_tables.json) are not this version's.")
    return data


def font_infos(game: int) -> list[dict]:
    """The game's fonts as data/vv_font_tables.json keeps them (key, name, sheet, spacing, entries ...)."""
    return list(_tables()["games"][str(game)])


def font_info(game: int, key: str) -> dict:
    for info in font_infos(game):
        if info["key"] == key:
            return info
    raise TextError(f"{TITLES.get(game, game)} has no font {key!r}.")


def sheet_names(game: int) -> list[str]:
    return [info["sheet"] for info in font_infos(game)]


@dataclass(frozen=True)
class Cell:
    """One glyph-table entry after the loader: its byte and its (left, top, right, bottom) on the sheet."""
    code: int
    rect: tuple

    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]


class GameFont:
    """A game's bitmap font as its loader leaves it."""

    def __init__(self, game: int, key: str, sheet_size: tuple[int, int] | None = None) -> None:
        info = font_info(game, key)
        self.game, self.key = game, key
        self.name, self.sheet = info["name"], info["sheet"]
        self.spacing = int(info["spacing"])
        self.sheet_size = tuple(sheet_size or info["sheet_size"])
        self.cells, self.index, self.line_height = load_table(info["entries"], self.sheet_size[0])
        self.has = [False] * 256          # the bytes with a cell of their own (the rest draw cell 0)
        for cell in self.cells:
            if 0 <= cell.code < 256:
                self.has[cell.code] = True

    def cell(self, code: int) -> Cell:
        """get_glyph (A New Home 0x402430): a byte's cell, or cell (code & 0x7FFF) for a code over 0xFF."""
        if code < 0:
            code &= 0xFF
        if code < 0x100:
            return self.cells[self.index[code]]
        return self.cells[code & 0x7FFF]

    def width(self, data: bytes, scale: float = 1.0) -> int:
        """The game's text width (A New Home 0x402160) of `data` (bytes)."""
        widest = line = 0
        for b in data:
            if b == 0:
                break
            if b == 10:
                widest = max(widest, line)
                line = 0
                continue
            line += int((self.cell(b).width + self.spacing) * pi.f32(scale))
        widest = max(widest, line)
        return widest - self.spacing if widest else 0


def load_table(entries, sheet_width: int) -> tuple[list[Cell], list[int], int]:
    """(cells, index[256], line height): the game's font loader (A New Home 0x402240) on a stored table."""
    rows = [list(e) for e in entries]
    if not rows:
        raise TextError("The font has no glyphs.")
    line_height = rows[0][4] - rows[0][2]
    xs = ys = 0
    for i, row in enumerate(rows):
        if i >= 0x100:
            break
        row[2] += ys
        row[4] += ys
        row[1] -= xs
        row[3] -= xs
        if row[3] > sheet_width:
            xs += row[1]
            ys += line_height + 1
            row[3] -= row[1]
            row[1] = 0
            row[2] += line_height + 1
            row[4] += line_height + 1
    for row in rows:
        if row[0] < 0:
            row[0] &= 0xFF
    index = [0] * 256
    for c in range(1, 256):
        for k, row in enumerate(rows):
            if row[0] == c:
                index[c] = k
                break
    return [Cell(r[0], tuple(r[1:5])) for r in rows], index, line_height


@dataclass(frozen=True)
class GameDraw:
    """One blit the game's text draw makes: the byte, its cell rect on the sheet, the place."""
    code: int
    rect: tuple
    x: int
    y: int


def game_plan(font: GameFont, data: bytes, x: int, y: int) -> list[GameDraw]:
    """The blits of the game's text draw (A New Home 0x409160) for `data` at (x, y)."""
    out = []
    start = x
    for b in data:
        if b == 0:
            break
        if b == 10:
            x = start
            y += font.line_height
            continue
        cell = font.cell(b)
        if cell.width == 0:
            continue
        out.append(GameDraw(b, cell.rect, x, y))
        x += cell.width + font.spacing
    return out


def centred_x(font: GameFont, data: bytes, cx: int) -> int:
    """Where the game's centred draw (A New Home 0x4094C0) starts: cx - trunc(width / 2)."""
    return cx - int(font.width(data) / 2)


def game_bytes(text: str) -> bytes:
    """The text as the game holds it (Windows-1252; a character it cannot hold becomes "?")."""
    return text.replace("\r\n", "\n").encode("cp1252", errors="replace")


# ------------------------------------------------------------------------------------ the sheets

def font_cache_root() -> Path:
    return pi.CACHE_ROOT / CACHE_SUBFOLDER


def font_source(game: int, folders, root: Path | None = None) -> pi.Pictures:
    """The game's font sheets: the Studio's own copy ("Picture Studio Pictures\\Fonts\\<game>"), made from
    the first game folder that has them (read only)."""
    return pi.picture_source(game, folders, sheet_names(game), root=root or font_cache_root())


# ------------------------------------------------------------------ the patcher's own glyphs (b)

PATCHER_FONT_NAMES = {"arialbold": "ldwarialbold", "burweed": "ldwBurweed27"}


def patcher_glyph(game: int, key: str, char: str, images_dir: Path | None = None):
    """The patcher's own glyph for a character the game font lacks -- the letter the patched game itself
    draws (the in-game Unicode text: src/vv_font_glyphs.py, shared with the companion DLL, when the patcher
    has it) -- as an Image one line tall (its width is the advance), white like the sheets; None when there
    is none, or when it is the game's own letter.

    vv_font_glyphs' interface: glyph("vv<n>", "ldwarialbold" | "ldwBurweed27", char, images_dir) -> Glyph
    (.mask: the box, line-tall; .source: "game", "alias", "ttf:...", "composed:...", "stand-in:...";
    .image(colour)) | None, images_dir holding the font sheets.  An older shape, glyph_image(game, key,
    char) -> Image | None, is read too."""
    try:
        import vv_font_glyphs  # noqa: PLC0415 -- optional: the in-game Unicode text's module
    except ImportError:
        return None
    try:
        glyph = getattr(vv_font_glyphs, "glyph", None)
        if callable(glyph) and images_dir is not None:
            made = glyph(f"vv{game}", PATCHER_FONT_NAMES[key], char, Path(images_dir))
            if made is None or getattr(made, "source", "") == "game":
                return None
            image = made.image((255, 255, 255))
            return image if isinstance(image, pi.Image) and image.width else None
        getter = getattr(vv_font_glyphs, "glyph_image", None)
        if callable(getter):
            image = getter(game, key, char)
            return image if isinstance(image, pi.Image) else None
    except Exception:                    # noqa: BLE001 -- another module's art is never fatal here
        return None
    return None


def sheet_folder(source: pi.Pictures) -> Path | None:
    """The folder that holds the font sheets as files (the Studio's copy, or the game's Images)."""
    base = getattr(source, "base", None)
    if isinstance(base, pi.CacheSource) and base.ok:
        return base.folder
    if isinstance(base, pi.FolderSource):
        return pi.images_folder(base.copy)
    return None


# --------------------------------------------------------------------------- the font's style (c)

def _maker():
    try:
        import vv_glyph_maker  # noqa: PLC0415
    except ImportError:
        return None
    return vv_glyph_maker


def _ink_rows(image: pi.Image, rect: tuple) -> tuple[int, int] | None:
    """(first, last + 1) rows of a cell with any alpha, relative to the cell's top."""
    left, top, right, bottom = rect
    rows = [y for y in range(top, bottom)
            if any(image.data[(y * image.width + x) * 4 + 3] for x in range(left, right))]
    return (rows[0] - top, rows[-1] + 1 - top) if rows else None


def font_style(font: GameFont, sheet: pi.Image):
    """The vv_glyph_maker.GlyphStyle that matches a game font: its line height, baseline ('H'), cap and x
    heights, its fill (white), no outline (the sheets have none) and the alpha levels its sheet uses."""
    maker = _maker()
    if maker is None:
        return None
    h = _ink_rows(sheet, font.cell(ord("H")).rect) if font.has[ord("H")] else None
    x = _ink_rows(sheet, font.cell(ord("x")).rect) if font.has[ord("x")] else None
    baseline = h[1] if h else font.line_height * 3 // 4
    cap = (h[1] - h[0]) if h else font.line_height // 2
    xh = (x[1] - x[0]) if x else max(1, cap * 2 // 3)
    alphas = sorted({sheet.data[i] for i in range(3, len(sheet.data), 4)} - {0})
    face, bold = ("Arial", True) if font.key == "arialbold" else (_burweed_face(maker), False)
    return maker.GlyphStyle(line_height=font.line_height, baseline=baseline, cap_height=cap, x_height=xh,
                            fill=(255, 255, 255), outline=None, outline_width=0,
                            alpha_levels=tuple(alphas) if alphas else None, face=face, bold=bold)


def _burweed_face(maker) -> str:
    """Burweed ICG when the player has it installed (the font the Burweed sheet was drawn from), else a
    hand-lettered Windows font."""
    try:
        if maker.font_installed(TTF_FACE):
            return TTF_FACE
    except Exception:                    # noqa: BLE001
        pass
    return "Segoe Print"


def ttf_installed() -> bool:
    maker = _maker()
    try:
        return bool(maker and maker.available() and maker.font_installed(TTF_FACE))
    except Exception:                    # noqa: BLE001
        return False


# ------------------------------------------------------------------------------------ the layout

def clusters(text: str) -> list[str]:
    """The text cut into grapheme clusters (vv_glyph_maker.segment; without it, characters with their
    combining marks)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    maker = _maker()
    if maker is not None:
        return maker.segment(text)
    out: list[str] = []
    for ch in text:
        if out and out[-1] != "\n" and unicodedata.category(ch).startswith("M"):
            out[-1] += ch
        else:
            out.append(ch)
    return out


@dataclass
class Piece:
    """One drawn cluster: its picture (white, untinted, except emoji), where it goes relative to the pen and
    the line's top, how far the pen moves, and where it came from."""
    cluster: str
    source: str
    image: pi.Image
    left: int
    top: int
    advance: int
    colour: bool = False            # a full-colour emoji: never tinted
    game_rect: tuple | None = None  # a game glyph's cell on the sheet
    detail: str = ""


@dataclass
class Rendered:
    image: pi.Image
    boxes: list = field(default_factory=list)      # (x, y, w, h, source, cluster) on `image`
    counts: dict = field(default_factory=dict)     # source -> number of clusters
    missing: list = field(default_factory=list)    # clusters nothing could draw


def _tofu(height: int, width: int) -> pi.Image:
    """A hollow box, the font's height: what is drawn when nothing can make a glyph."""
    w, h = max(3, width), max(3, height)
    img = pi.Image(w, h)
    for x in range(w):
        for y in (0, h - 1):
            img.data[(y * w + x) * 4:(y * w + x) * 4 + 4] = b"\xff\xff\xff\xff"
    for y in range(h):
        for x in (0, w - 1):
            img.data[(y * w + x) * 4:(y * w + x) * 4 + 4] = b"\xff\xff\xff\xff"
    return img


class TextRenderer:
    """Lays out and draws any text in one font: a game font (with its sheet) or the installed TTF."""

    def __init__(self, game: int, key: str, sheet: pi.Image | None = None, ttf_size: int = 27,
                 images_dir: Path | None = None) -> None:
        self.game, self.key = game, key
        self.images_dir = images_dir          # the sheets as files, for the patcher's own glyphs
        self.ttf = key == TTF_KEY
        self.maker = _maker()
        self._pieces: dict[str, Piece | None] = {}
        if self.ttf:
            self.font = None
            self.sheet = None
            self.size = max(4, int(ttf_size))
            metrics = self.maker.ttf_metrics(TTF_FACE, self.size) if self.maker else None
            if not metrics:
                raise TextError(f"{TTF_NAME} is not installed.")
            self.line_height, self.baseline = metrics
            self.spacing = 0
            self.style = None
            return
        if sheet is None:
            raise TextError("The font's picture is needed.")
        self.font = GameFont(game, key, (sheet.width, sheet.height))
        self.sheet = sheet
        self.line_height = self.font.line_height
        self.spacing = self.font.spacing
        self.style = font_style(self.font, sheet)

    # ---- one cluster
    def _game_piece(self, ch: str) -> Piece | None:
        if len(ch) != 1:
            return None
        try:
            b = ch.encode("cp1252")
        except UnicodeEncodeError:
            return None
        if len(b) != 1 or not self.font.has[b[0]]:
            return None
        cell = self.font.cell(b[0])
        return Piece(ch, SOURCE_GAME, self.sheet.sub(cell.rect[0], cell.rect[1], cell.width,
                                                     cell.rect[3] - cell.rect[1]), 0, 0, cell.width,
                     game_rect=cell.rect)

    def _patcher_piece(self, ch: str) -> Piece | None:
        if len(ch) != 1:
            return None
        image = patcher_glyph(self.game, self.key, ch, self.images_dir)
        if image is None:
            return None
        return Piece(ch, SOURCE_PATCHER, image, 0, 0, image.width)

    def _own(self, ch: str) -> Piece | None:
        """(a) or (b): the game's glyph, else the patcher's."""
        return self._game_piece(ch) or self._patcher_piece(ch)

    def _made(self, cluster: str) -> Piece | None:
        maker = self.maker
        if maker is None or not maker.available():
            return None
        if self.ttf:
            g = maker.render_ttf_text(TTF_FACE, self.size, cluster)
        else:
            g = maker.render_cluster(cluster, self.style)
        if g is None:
            return None
        source = SOURCE_EMOJI if g.kind == "emoji" else (SOURCE_GAME if self.ttf else SOURCE_MADE)
        return Piece(cluster, source, g.image, g.left, g.top, g.advance, colour=bool(g.colour),
                     detail=g.face)

    def _composed(self, cluster: str) -> Piece | None:
        """A letter with accents: the longest leading part the font (or the patcher) has, with each
        remaining combining mark generated and placed on it (NFD)."""
        maker = self.maker
        decomposed = unicodedata.normalize("NFD", cluster)
        for k in range(len(decomposed) - 1, 0, -1):
            head = unicodedata.normalize("NFC", decomposed[:k])
            rest = decomposed[k:]
            if len(head) != 1 or not all(unicodedata.combining(m) for m in rest):
                continue
            base = self._own(head)
            if base is None:
                continue
            if maker is None or not maker.available():
                return None
            box = _ink_box(base.image)
            if box is None:
                box = (0, self.style.baseline - self.style.x_height, base.advance, self.style.baseline)
            layers = [(base.image, base.left, base.top)]
            for mark in rest:
                g = maker.render_mark(mark, self.style, box)
                if g is None:
                    return None
                layers.append((g.image, g.left, g.top))
                if g.image.width and g.image.height:
                    box = (min(box[0], g.left), min(box[1], g.top), max(box[2], g.left + g.image.width),
                           max(box[3], g.top + g.image.height))
            image, left, top = _stack(layers)
            return Piece(cluster, SOURCE_MADE, image, left, top, base.advance,
                         detail=f"{head} from {SOURCE_LABELS[base.source]} glyph, accents generated")
        return None

    def _parts(self, cluster: str) -> Piece | None:
        """A compatibility character (a ligature, a full-width or circled letter ...) whose parts (NFKD) the
        font has: the parts side by side."""
        parts = unicodedata.normalize("NFKD", cluster)
        if parts == cluster or len(parts) > 8:
            return None
        pieces = [self._own(ch) for ch in parts]
        if not pieces or any(p is None for p in pieces):
            return None
        layers, x = [], 0
        for p in pieces:
            layers.append((p.image, x + p.left, p.top))
            x += p.advance + self.spacing
        image, left, top = _stack(layers)
        return Piece(cluster, SOURCE_MADE, image, left, top, x - self.spacing,
                     detail="made of " + parts)

    def piece(self, cluster: str) -> Piece | None:
        if cluster in self._pieces:
            return self._pieces[cluster]
        made = None
        if self.ttf:
            made = self._made(cluster)
        else:
            nfc = unicodedata.normalize("NFC", cluster)
            made = self._own(nfc) if len(nfc) == 1 else None
            if made is None and cluster == "\t":
                space = self._own(" ")
                if space is not None:
                    made = Piece(cluster, space.source, pi.Image(0, 0), 0, 0,
                                 4 * space.advance + 3 * self.spacing)
            if made is None:
                is_emoji = self.maker is not None and self.maker.is_emoji(cluster)
                if not is_emoji:
                    made = self._composed(nfc) or self._parts(nfc)
                if made is None:
                    made = self._made(cluster)
        if made is not None and made.cluster != cluster:
            made.cluster = cluster
        self._pieces[cluster] = made
        return made

    # ---- the text
    def lines(self, text: str) -> list[list[Piece]]:
        out: list[list[Piece]] = [[]]
        for cluster in _rtl_runs(clusters(text)):
            if cluster == "\n":
                out.append([])
                continue
            if len(cluster) == 1 and unicodedata.category(cluster) in ("Cc", "Cf") and cluster != "\t":
                continue
            piece = self.piece(cluster)
            if piece is None:
                adv = max(3, self.line_height // 3)
                piece = Piece(cluster, "missing", _tofu(self.line_height * 2 // 3, adv),
                              0, self.line_height // 6, adv)
            out[-1].append(piece)
        return out

    def line_width(self, line: list[Piece]) -> int:
        """The game's width rule: each piece's advance plus the spacing, less one spacing."""
        if not line:
            return 0
        total = sum(p.advance + self.spacing for p in line)
        return total - self.spacing if total else 0

    def render(self, text: str, colour: int = DEFAULT_COLOUR, align: str = ALIGN_LEFT,
               effect: str = EFFECT_NONE) -> Rendered:
        """The text drawn on a transparent canvas just big enough for it (and the pieces' places)."""
        lines = self.lines(text)
        widths = [self.line_width(line) for line in lines]
        widest = max(widths, default=0)
        placed = []                 # (piece, pen x, line top)
        for n, line in enumerate(lines):
            if align == ALIGN_CENTRE:
                x = -int(widest / 2)
            elif align == ALIGN_CENTRE_LINES:
                x = -int(widths[n] / 2)
            elif align == ALIGN_RIGHT:
                x = -widths[n]
            else:
                x = 0
            y = n * self.line_height
            for p in line:
                if p.advance or p.image.width:
                    placed.append((p, x, y))
                x += p.advance + self.spacing
        copies = [((0, 0), colour)]
        if effect == EFFECT_OUTLINED:
            copies = [(off, OUTLINE_SHADOW) for off in OUTLINE_COPIES] + copies
        top, bottom = 0, max(1, len(lines) * self.line_height)
        left, right = (10 ** 9, -10 ** 9) if placed else (0, 1)
        for p, x, y in placed:
            for (dx, dy), _c2 in copies:
                left, top = min(left, x + p.left + dx, x), min(top, y + p.top + dy)
                right = max(right, x + p.left + dx + p.image.width, x + p.advance)
                bottom = max(bottom, y + p.top + dy + p.image.height)
        if right <= left:
            right = left + 1
        canvas = pi.Image(right - left, bottom - top)
        result = Rendered(canvas)
        for (dx, dy), value in copies:
            if (value >> 24) & 0xFF == 0:
                value = DEFAULT_COLOUR
            tint = (value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF)
            fade = (value >> 24) & 0xFF
            for p, x, y in placed:
                if not p.image.width or not p.image.height:
                    continue
                image = p.image if p.colour else _and_tint(p.image, tint)
                canvas.draw(image, x + p.left + dx - left, y + p.top + dy - top,
                            255 if fade == 255 else pi.surface_alpha(fade / 255.0))
        for p, x, y in placed:
            result.counts[p.source] = result.counts.get(p.source, 0) + 1
            if p.source == "missing":
                result.missing.append(p.cluster)
            if p.source != SOURCE_GAME:
                w = max(p.image.width, p.advance, 1)
                result.boxes.append((x + min(p.left, 0) - left, y + min(p.top, 0) - top, w,
                                     max(p.image.height, 1), p.source, p.cluster))
        return result


def _rtl(cluster: str) -> bool:
    return unicodedata.bidirectional(cluster[0]) in ("R", "AL")


def _rtl_runs(parts: list[str]) -> list[str]:
    """Clusters, with each run of right-to-left ones (Arabic, Hebrew ...; the spaces between their words
    too) made one, so Windows shapes and orders the run as a whole: joined Arabic letters, read right to
    left."""
    out: list[str] = []
    i = 0
    while i < len(parts):
        if not _rtl(parts[i]):
            out.append(parts[i])
            i += 1
            continue
        j = i + 1
        while j < len(parts):
            if _rtl(parts[j]) or unicodedata.bidirectional(parts[j][0]) in ("NSM", "AN"):
                j += 1
            elif parts[j] == " " and j + 1 < len(parts) and _rtl(parts[j + 1]):
                j += 1
            else:
                break
        out.append("".join(parts[i:j]))
        i = j
    return out


def _ink_box(image: pi.Image) -> tuple | None:
    return image.bbox()


def _stack(layers) -> tuple[pi.Image, int, int]:
    """Images (image, left, top) drawn in order on one canvas: (canvas, its left, its top)."""
    left = min(x for _i, x, _y in layers)
    top = min(y for _i, _x, y in layers)
    right = max(x + i.width for i, x, _y in layers)
    bottom = max(y + i.height for i, _x, y in layers)
    canvas = pi.Image(max(0, right - left), max(0, bottom - top))
    for image, x, y in layers:
        canvas.draw(image, x - left, y - top)
    return canvas, left, top


@lru_cache(maxsize=4096)
def _and_table(value: int) -> bytes:
    return bytes(v & value for v in range(256))


def _and_tint(image: pi.Image, tint: tuple[int, int, int]) -> pi.Image:
    """The game's recolour (A New Home 0x402510): every pixel ANDed with the colour, alpha kept."""
    if tint == (255, 255, 255):
        return image
    out = image.copy()
    d = out.data
    for channel, value in enumerate(tint):
        if value != 255:
            d[channel::4] = d[channel::4].translate(_and_table(value))
    return out


def game_render(font: GameFont, sheet: pi.Image, data: bytes, colour: int = DEFAULT_COLOUR) -> pi.Image:
    """`data` (bytes) drawn exactly as the stock game draws it, every byte its own cell or cell 0."""
    plan = game_plan(font, data, 0, 0)
    if (colour >> 24) & 0xFF == 0:
        colour = DEFAULT_COLOUR
    tint = (colour & 0xFF, (colour >> 8) & 0xFF, (colour >> 16) & 0xFF)
    fade = (colour >> 24) & 0xFF
    lines = data.count(b"\n") + 1
    right = max((d.x + d.rect[2] - d.rect[0] for d in plan), default=1)
    canvas = pi.Image(max(1, right), lines * font.line_height)
    tinted = _and_tint(sheet, tint)
    for d in plan:
        canvas.draw(tinted.sub(d.rect[0], d.rect[1], d.rect[2] - d.rect[0], d.rect[3] - d.rect[1]), d.x, d.y,
                    255 if fade == 255 else pi.surface_alpha(fade / 255.0))
    return canvas


# ------------------------------------------------------------------------------- the name counter

def name_bytes(text: str) -> int:
    """How many bytes the text takes as a villager's name (UTF-8, as the games keep names)."""
    return len(text.encode("utf-8", errors="surrogatepass"))


def name_fit(game: int, text: str) -> tuple[int, int, bool]:
    """(bytes the text takes, bytes the game's name field holds, fits)."""
    used = name_bytes(text)
    return used, NAME_BYTES[game], used <= NAME_BYTES[game] and "\n" not in text


# ----------------------------------------------------------------------- the character picker

COMMON_ACCENTS = (
    "ÀÁÂÃÄÅĀĂĄÆÇĆĈĊČĎĐÈÉÊËĒĔĖĘĚĜĞĠĢĤĦÌÍÎÏĨĪĬĮİĴĶĹĻĽĿŁÑŃŅŇÒÓÔÕÖØŌŎŐŒŔŖŘŚŜŞŠȘŢŤȚŦÙÚÛÜŨŪŬŮŰŲŴÝŸŶŹŻŽÞ"
    "àáâãäåāăąæçćĉċčďđèéêëēĕėęěĝğġģĥħìíîïĩīĭįıĵķĺļľŀłñńņňòóôõöøōŏőœŕŗřśŝşšșţťțŧùúûüũūŭůűųŵýÿŷźżžþßð"
    "¡¿«»‹›„“”‘’‚–—…•·°±×÷€£¥¢©®™§¶¹²³¼½¾"
)
COMBINING_MARKS = tuple(chr(c) for c in range(0x0300, 0x0370))


def char_name(ch: str) -> str:
    return unicodedata.name(ch, "") or f"U+{ord(ch):04X}"


def search_characters(query: str, limit: int = 300) -> list[str]:
    """Characters by name ("e acute", "smiling", "hiragana ka") or code point ("U+00E9", "e9", "0x1F600")."""
    query = query.strip()
    if not query:
        return []
    found: list[str] = []
    code = query.upper().removeprefix("U+").removeprefix("0X")
    if code and all(c in "0123456789ABCDEF" for c in code) and len(code) <= 6:
        value = int(code, 16)
        if value <= 0x10FFFF and not 0xD800 <= value <= 0xDFFF:
            found.append(chr(value))
    if len(query) == 1:
        found.append(query)
    words = query.upper().split()
    if words:
        for value in _named_points():
            name = unicodedata.name(chr(value))
            if all(w in name for w in words):
                found.append(chr(value))
                if len(found) >= limit:
                    break
    return list(dict.fromkeys(found))[:limit]


@lru_cache(maxsize=1)
def _named_points() -> tuple[int, ...]:
    """Every code point with a name, the common blocks first (Latin, Greek, Cyrillic, symbols, emoji)."""
    first = list(range(0x20, 0x2000)) + list(range(0x1F000, 0x1FB00)) + list(range(0x2000, 0x3000))
    rest = [c for c in range(0x3000, 0x110000) if not (0xD800 <= c <= 0xDFFF) and not (0x1F000 <= c < 0x1FB00)]
    return tuple(c for c in first + rest if unicodedata.name(chr(c), ""))
