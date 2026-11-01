"""Picture Studio's "Everything" tab (src/vv_picture_studio.py): every picture each Virtual Villagers game
ships, drawn as the game draws it, sorted by category, saved as transparent PNGs (docs/picture-studio-assets.md).

Two kinds of entry, for each of the five games:

* **Composed assets** (each game's src/vv_assets_vv<n>.py ``assets()``): what the game assembles on screen --
  a creature's animation frames, a hut at each build stage, a puzzle object in each state, the Tech screen's
  bars empty, part filled and full, a meter at a fill level, a button normal / hover / pressed, the island
  scene from its tiles, the title and loading screens.  Each frame is a plan: the list of blits the game makes
  (vv_picture_image.Draw: sheet, cell, place, scale, alpha), in its order, proven against the game's own draw
  code by emulating it (tests/test_assets_vv<n>.py).
* **Source sheets** (made here from each game's ``sheet_table()``): every picture file in the game's Images
  folder, cell by cell -- cut as the game's own sprite constructor cuts it when the game builds it, or, for a
  picture the game never loads, at the gaps the sheet itself has (labelled "(unused)").  Nothing is missed:
  a file the table does not know is still listed, whole or cut at its own gaps.

Unused art is labelled "(unused)"; the patcher's own art "(patcher)".  The pictures are read from the
player's own game folder, copied once into "Picture Studio Pictures\\Everything\\<game>" (all of its Images,
nothing shipped).  JPEG pictures are decoded by src/vv_jpeg.py.  Nothing here writes anything but the cache
and the PNGs the player saves.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import uuid

import vv_picture_image as pi

# The categories, in the order the window lists them.  A game lists only those it has something in.
CREATURES = "Creatures"
BUILDINGS = "Buildings and objects"
PUZZLES = "Puzzles"
COLLECTIBLES = "Collectibles"
PLANTS = "Plants and food"
VILLAGERS = "Villagers"
SCENE = "Scene"
TECH = "UI: Tech screen"
METERS = "UI: Meters"
PANELS = "UI: Panels and buttons"
ICONS = "Icons"
CURSORS = "Cursors"
FONTS = "Fonts and digits"
EFFECTS = "Effects"
SCREENS = "Screens"
PATCHER = "Patcher art"
UNUSED = "Unused"
SHEETS = "Source sheets"
CATEGORIES = (CREATURES, BUILDINGS, PUZZLES, COLLECTIBLES, PLANTS, VILLAGERS, SCENE, TECH, METERS, PANELS,
              ICONS, CURSORS, FONTS, EFFECTS, SCREENS, PATCHER, UNUSED, SHEETS)
UNUSED_MARK = " (unused)"
PATCHER_MARK = " (patcher)"
NOT_PLACED = "position not from the game"
PICTURE_EXTENSIONS = (".png", ".jpg", ".jpeg")
CACHE_SUBFOLDER = "Everything"
JPEG_MAGIC = b"\xff\xd8"
ASSET_MODULES = {n: f"vv_assets_vv{n}" for n in range(1, 6)}


# ------------------------------------------------------------------ what the game modules give

@dataclass(frozen=True)
class Frame:
    """One picture of an asset: `plan` is the game's blits, in its order (vv_picture_image.Draw; a Draw
    may carry a `tint` (r, g, b) attribute for a colour-modulated blit, see TintDraw)."""
    label: str
    plan: tuple


@dataclass(frozen=True)
class TintDraw(pi.Draw):
    """A blit the game colour-modulates (SDL_SetSurfaceColorMod / a tinted draw): each colour channel
    multiplied by tint / 255."""
    tint: tuple = (255, 255, 255)

    def key(self) -> tuple:
        return super().key() + (tuple(self.tint),)


@dataclass(frozen=True)
class Asset:
    """One entry of the Everything tab.

    key: unique and stable within the game (used for nothing the player sees).
    category: one of CATEGORIES.  group: an optional sub-heading inside it ("Huts", "Fish" ...).
    label: what the window shows and the PNG is named (the window adds " (unused)" / " (patcher)").
    frames: every picture of it (a state, a frame of an animation, a fill level ...).
    unused: art the game ships but never draws.  patcher: the patcher's own art.
    note: anything the player should know ("position not from the game" ...).
    proof: how the plan is proven, in a few words ("emulated 0x4xxxxx", "constructor 0x40A070", "sheet").
    """
    key: str
    category: str
    label: str
    frames: tuple
    group: str = ""
    unused: bool = False
    patcher: bool = False
    note: str = ""
    proof: str = ""
    lazy: bool = False              # a picture file whose pieces (cut at its own gaps) are found when shown

    @property
    def shown(self) -> str:
        return self.label + (UNUSED_MARK if self.unused else "") + (PATCHER_MARK if self.patcher else "")


@dataclass(frozen=True)
class SheetSpec:
    """How the game builds one sprite from its Images files (one sheet, or a grid of sheets), as its sprite
    constructor is called in the stock exe: `name` and `cols` x `rows` cells as vv_picture_image.Atlas.
    `whole`: built whole (the engine's whole-picture constructor, one cell).  `used`: the game draws it.
    `where`: the constructor call(s) it was read from ("0x43C1A0" ...), for the docs and tests.
    `category`: the category its cells are listed under besides Source sheets (optional)."""
    name: str
    cols: int = 1
    rows: int = 1
    sheets: tuple = (1, 1)
    suffix: str = ".png"
    whole: bool = False
    used: bool = True
    where: str = ""
    label: str = ""

    @property
    def atlas(self) -> pi.Atlas:
        return pi.Atlas(self.name, max(1, self.cols), max(1, self.rows), tuple(self.sheets), self.suffix)

    def files(self) -> list[str]:
        return self.atlas.files()


def cell_plan(sheets: "AssetSheets", atlas: pi.Atlas, col: int, row: int, x: int = 0, y: int = 0,
              scale: float = 1.0, alpha: float = 1.0, what: str = "") -> pi.Draw:
    """One blit of cell (col, row) of `atlas`, cut as the engine cuts it (vv_picture_image.Atlas.cell)."""
    name, rect = atlas.cell(sheets.size, col, row)
    return pi.Draw(name, rect, x, y, scale, alpha, what)


def whole_plan(sheets: "AssetSheets", name: str, x: int = 0, y: int = 0, alpha: float = 1.0,
               what: str = "") -> pi.Draw:
    """A whole picture blitted at (x, y)."""
    w, h = sheets.size(name)
    return pi.Draw(name, (0, 0, w, h), x, y, 1.0, alpha, what)


def one(sheets: "AssetSheets", key: str, category: str, label: str, name: str, **kw) -> Asset:
    """An asset that is one whole picture."""
    return Asset(key, category, label, (Frame("", (whole_plan(sheets, name),)),), **kw)


# ------------------------------------------------------------------ pictures: PNG and JPEG

def is_picture(data: bytes) -> bool:
    return bool(data) and (data.startswith(pi.PNG_MAGIC) or data.startswith(JPEG_MAGIC))


def decode_picture(data: bytes) -> pi.Image:
    if data.startswith(JPEG_MAGIC):
        import vv_jpeg
        return vv_jpeg.decode_jpeg(data)
    return pi.decode_png(deinterlace_png(data))


ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))


def deinterlace_png(data: bytes) -> bytes:
    """An Adam7-interlaced PNG (a few of the games' sheets are; libpng reads them) as the same picture
    non-interlaced, so vv_picture_image.decode_png reads it; any other PNG unchanged."""
    data = bytes(data)
    if not data.startswith(pi.PNG_MAGIC) or len(data) < 29 or data[28] != 1:
        return data
    import zlib
    chunks = list(pi._chunks(data))
    header = next(body for kind, body in chunks if kind == b"IHDR")
    width, height, depth, colour, _c, _f, _i = struct.unpack(">IIBBBBB", header)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    bits = depth * channels
    raw = zlib.decompress(b"".join(body for kind, body in chunks if kind == b"IDAT"))
    full = [[0] * width for _ in range(height)]
    at = 0
    for x0, y0, dx, dy in ADAM7:
        pw, ph = -(-(width - x0) // dx) if width > x0 else 0, -(-(height - y0) // dy) if height > y0 else 0
        if not pw or not ph:
            continue
        row_bytes = (pw * bits + 7) // 8
        size = ph * (row_bytes + 1)
        rows = pi._unfilter(raw[at:at + size], pw, ph, max(1, bits // 8), row_bytes)
        at += size
        for j in range(ph):
            line = rows[j * row_bytes:(j + 1) * row_bytes]
            value = int.from_bytes(line, "big")
            total = row_bytes * 8
            for i in range(pw):
                full[y0 + j * dy][x0 + i * dx] = (value >> (total - (i + 1) * bits)) & ((1 << bits) - 1)
    out_rows = bytearray()
    row_bytes = (width * bits + 7) // 8
    for row in full:
        value = 0
        for v in row:
            value = (value << bits) | v
        value <<= row_bytes * 8 - width * bits
        out_rows += b"\0" + value.to_bytes(row_bytes, "big")
    head = struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, 0)
    extra = b"".join(pi._chunk(kind, body) for kind, body in chunks if kind in (b"PLTE", b"tRNS"))
    return pi.PNG_MAGIC + pi._chunk(b"IHDR", head) + extra + pi._chunk(b"IDAT", zlib.compress(bytes(out_rows))) \
        + pi._chunk(b"IEND", b"")


def picture_size(data: bytes) -> tuple[int, int]:
    if data.startswith(JPEG_MAGIC):
        import vv_jpeg
        return vv_jpeg.jpeg_size(data)
    if not data.startswith(pi.PNG_MAGIC) or len(data) < 24:
        raise pi.PictureError("not a PNG or JPEG picture")
    return struct.unpack(">II", data[16:24])


class AssetSheets(pi.Sheets):
    """vv_picture_image.Sheets that also reads the games' JPEG pictures."""

    def image(self, name: str) -> pi.Image:
        key = name.casefold()
        if key not in self._images:
            self._images[key] = decode_picture(self._data(name))
        return self._images[key]

    def size(self, name: str) -> tuple[int, int]:
        key = name.casefold()
        if key not in self._sizes:
            if key in self._images:
                image = self._images[key]
                self._sizes[key] = (image.width, image.height)
            else:
                try:
                    self._sizes[key] = picture_size(self._data(name))
                except pi.PictureError:
                    raise pi.PictureError(f"The game picture {name} is not a PNG or JPEG.") from None
        return self._sizes[key]

    def names(self) -> list[str]:
        """Every picture file the source has (the cache's or the game folder's Images)."""
        lister = getattr(self.source, "names", None)
        return sorted(lister(), key=str.casefold) if callable(lister) else []


# ------------------------------------------------------------------ drawing

def _piece(sheets: pi.Sheets, call) -> pi.Image:
    piece = sheets.piece(call)
    tint = getattr(call, "tint", None)
    if tint is not None and tuple(tint) != (255, 255, 255):
        out = piece.copy()
        r, g, b = tint
        d = out.data
        for i in range(0, len(d), 4):
            d[i], d[i + 1], d[i + 2] = d[i] * r // 255, d[i + 1] * g // 255, d[i + 2] * b // 255
        return out
    return piece


def render_plan(sheets: pi.Sheets, plan) -> pi.Image:
    """A plan drawn on a transparent canvas just big enough for it (vv_picture_image.render_plan, with tints;
    one plain blit is the cell itself)."""
    plan = list(plan)
    if not plan:
        return pi.Image(1, 1)
    if len(plan) == 1 and plan[0].alpha == 1.0 and getattr(plan[0], "tint", None) in (None, (255, 255, 255)):
        return sheets.piece(plan[0]).copy()
    left = top = 10 ** 9
    right = bottom = -10 ** 9
    pieces = []
    for call in plan:
        piece = _piece(sheets, call)
        pieces.append(piece)
        left, top = min(left, call.x), min(top, call.y)
        right, bottom = max(right, call.x + piece.width), max(bottom, call.y + piece.height)
    canvas = pi.Image(max(1, right - left), max(1, bottom - top))
    for call, piece in zip(plan, pieces):
        alpha = pi.surface_alpha(call.alpha)
        if alpha >= 255 and piece.width and _opaque(piece):
            _copy(canvas, piece, call.x - left, call.y - top)       # an opaque blit: its pixels as they are
        else:
            canvas.draw(piece, call.x - left, call.y - top, alpha)
    return canvas


def _opaque(image: pi.Image) -> bool:
    return image.data[3::4].count(255) == image.width * image.height


def _copy(canvas: pi.Image, piece: pi.Image, x: int, y: int) -> None:
    """An opaque piece put on the canvas (what Image.draw does for alpha 255), row by row."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.width, x + piece.width), min(canvas.height, y + piece.height)
    if x1 <= x0 or y1 <= y0:
        return
    n = (x1 - x0) * 4
    for yy in range(y0, y1):
        s = ((yy - y) * piece.width + (x0 - x)) * 4
        d = (yy * canvas.width + x0) * 4
        canvas.data[d:d + n] = piece.data[s:s + n]


def render_frame(sheets: pi.Sheets, frame: Frame) -> pi.Image:
    return render_plan(sheets, frame.plan)


# ------------------------------------------------------------------ the source sheets, cell by cell

def own_gaps(image: pi.Image) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """(column spans, row spans) of a picture cut at its own fully clear columns and rows (an unused sheet's
    cells come from the sheet itself): the runs of columns (rows) that hold any drawn pixel."""
    w, h, alphas = image.width, image.height, image.data[3::4]
    cols = [any(alphas[y * w + x] for y in range(h)) for x in range(w)]
    rows = [any(alphas[y * w:(y + 1) * w]) for y in range(h)]

    def runs(flags):
        out, start = [], None
        for i, f in enumerate(flags + [False]):
            if f and start is None:
                start = i
            elif not f and start is not None:
                out.append((start, i))
                start = None
        return out
    return runs(cols), runs(rows)


def sheet_frames(sheets: AssetSheets, spec: SheetSpec) -> tuple:
    """Every cell of a sheet the game builds, as its constructor cuts it."""
    if spec.whole or (spec.cols, spec.rows, tuple(spec.sheets)) == (1, 1, (1, 1)):
        return (Frame("whole", (whole_plan(sheets, spec.name),)),)
    atlas = spec.atlas
    frames = []
    for row in range(atlas.rows):
        for col in range(atlas.cols):
            frames.append(Frame(f"column {col + 1}, row {row + 1}", (cell_plan(sheets, atlas, col, row),)))
    return tuple(frames)


def gap_frames(sheets: AssetSheets, name: str) -> tuple:
    """A picture the game never builds: whole, plus each cell at the sheet's own gaps (when it has more than
    one)."""
    w, h = sheets.size(name)
    frames = [Frame("whole", (pi.Draw(name, (0, 0, w, h), 0, 0),))]
    try:
        image = sheets.image(name)
    except pi.PictureError:
        return tuple(frames)
    col_spans, row_spans = own_gaps(image)
    if len(col_spans) * len(row_spans) > 1:
        for r, (y0, y1) in enumerate(row_spans):
            for c, (x0, x1) in enumerate(col_spans):
                piece = image.sub(x0, y0, x1 - x0, y1 - y0)
                if piece.bbox() is None:
                    continue
                frames.append(Frame(f"piece {c + 1}, {r + 1} (cut at the sheet's own gaps)",
                                    (pi.Draw(name, (x0, y0, x1, y1), x0, y0),)))
    return tuple(frames)


PATCHER_PREFIX = "vvfp"          # the patcher's own files in a patched game's Images start with this


def source_sheet_assets(sheets: AssetSheets, table, files=None, patcher_images=()) -> list[Asset]:
    """Source sheets: one asset per sprite of `table` (its cells as the game cuts them), then one per picture
    file no sprite of the table reads: a file the patcher put in a patched game's Images (`patcher_images`, or
    a name starting "vvfp") is listed as the patcher's; any other is unused, cut at its own gaps."""
    files = list(files if files is not None else sheets.names())
    present = {f.casefold() for f in files}
    patcher_names = {n.casefold() for n in patcher_images}
    covered: set[str] = set()
    out = []
    seen: set[tuple] = set()
    for spec in table:
        names = spec.files()
        one_cell = spec.whole or (spec.cols * spec.rows == 1 and not spec.atlas.grid)
        cut = (tuple(n.casefold() for n in names),) + ((1, 1) if one_cell else (spec.cols, spec.rows))
        if cut in seen:                         # the same sprite built at two places: listed once
            continue
        seen.add(cut)
        covered.update(n.casefold() for n in names)
        if not all(n.casefold() in present for n in names):
            continue
        label = spec.label or (spec.name if not spec.atlas.grid else
                               f"{spec.name}{names[0][len(spec.name):-len(spec.suffix)]}-"
                               f"{names[-1][len(spec.name):-len(spec.suffix)]}{spec.suffix}")
        geometry = "whole" if spec.whole or spec.cols * spec.rows == 1 else f"{spec.cols} x {spec.rows} cells"
        out.append(Asset(f"sheet:{spec.name}:{spec.cols}x{spec.rows}", SHEETS, label, sheet_frames(sheets, spec),
                         group="Built by the game" if spec.used else "Built, never drawn",
                         unused=not spec.used,
                         note=f"{geometry}, as the game's constructor cuts it" + (f" ({spec.where})" if spec.where else ""),
                         proof="constructor"))
    for name in files:
        if name.casefold() in covered or not name.casefold().endswith(PICTURE_EXTENSIONS):
            continue
        whole = (Frame("whole", (whole_plan(sheets, name),)),)
        if name.casefold() in patcher_names or name.casefold().startswith(PATCHER_PREFIX):
            out.append(Asset(f"file:{name}", SHEETS, name, whole, group="Added by the patcher", patcher=True,
                             note="put in the game's Images by a patch; cells cut at the sheet's own gaps",
                             proof="sheet", lazy=True))
            continue
        out.append(Asset(f"file:{name}", SHEETS, name, whole, group="Never loaded by the game", unused=True,
                         note="cells cut at the sheet's own gaps; " + NOT_PLACED, proof="sheet", lazy=True))
    return out


def frames_of(sheets: AssetSheets, asset: Asset) -> tuple:
    """Every frame of an asset; a lazy one (a picture file cut at its own gaps) is cut now, once."""
    if not asset.lazy:
        return asset.frames
    cache = getattr(sheets, "_gap_frames", None)
    if cache is None:
        cache = sheets._gap_frames = {}
    name = asset.frames[0].plan[0].file
    if name.casefold() not in cache:
        cache[name.casefold()] = gap_frames(sheets, name)
    return cache[name.casefold()]


# ------------------------------------------------------------------ the game modules

def load_module(game: int):
    try:
        return importlib.import_module(ASSET_MODULES[game])
    except ImportError:
        return None


def all_assets(game: int, sheets: AssetSheets, module=None) -> list[Asset]:
    """Every asset of a game: its composed assets, then the source sheets; sorted by category (CATEGORIES)
    then group, keeping each game's own order inside a group."""
    module = module or load_module(game)
    composed = list(module.assets(sheets)) if module is not None else []
    table = list(module.sheet_table()) if module is not None else []
    added = getattr(module, "patcher_images", None)
    sources = source_sheet_assets(sheets, table, patcher_images=added() if callable(added) else ())
    # Every unused picture is also under Unused (unless the game's own table already lists it there).
    listed = {d.file.casefold() for a in composed if a.category == UNUSED for f in a.frames for d in f.plan}
    unused = [Asset("unused-" + a.key, UNUSED, a.label, a.frames, group=a.group, unused=True, note=a.note,
                    proof=a.proof, lazy=a.lazy)
              for a in sources if a.unused and not {d.file.casefold() for f in a.frames for d in f.plan} & listed]
    out = composed + mod_art_assets(game, sheets, table) + unused + sources
    order = {c: i for i, c in enumerate(CATEGORIES)}
    return [a for _i, a in sorted(enumerate(out), key=lambda p: (order.get(p[1].category, len(order)), p[0]))]


def by_category(assets) -> dict[str, list[Asset]]:
    out: dict[str, list[Asset]] = {}
    for asset in assets:
        out.setdefault(asset.category, []).append(asset)
    return out


# ------------------------------------------------------------------ saving

def frame_file_stem(asset: Asset, frame: Frame) -> str:
    """A frame's PNG name: the entry (without a picture's own extension) and, when it has several, the frame."""
    shown = re.sub(r"(?i)\.(png|jpe?g)\b", "", asset.shown)
    if (len(asset.frames) == 1 and not asset.lazy) or not frame.label:
        return pi.safe_file_name(shown)
    return pi.safe_file_name(f"{shown} - {frame.label}", limit=120)


def save_assets(sheets: pi.Sheets, assets, folder: Path, options: dict, progress=None) -> tuple[int, list[str]]:
    """Every frame of every asset into `folder`: a folder per category (and per group), an asset with several
    frames in a folder of its own.  (saved, failures)."""
    saved, failed = 0, []
    folder = Path(folder)
    made: dict[tuple, Path] = {}

    def where(*parts) -> Path:
        key = tuple(parts)
        if key not in made:
            path = folder.joinpath(*(pi.safe_file_name(p.replace(": ", " - ")) for p in parts if p))
            path.mkdir(parents=True, exist_ok=True)
            made[key] = path
        return made[key]
    total = sum(len(a.frames) for a in assets)
    done = 0
    for asset in assets:
        frames = frames_of(sheets, asset) if isinstance(sheets, AssetSheets) else asset.frames
        target = where(asset.category, asset.group)
        if len(frames) > 1:                     # a folder of its own, named without the picture's extension
            target = where(asset.category, asset.group, re.sub(r"(?i)\.(png|jpe?g)\b", "", asset.shown))
        for frame in frames:
            try:
                image = render_frame(sheets, frame)
                pi.save_png(image, pi.unique_path(target, frame_file_stem(asset, frame)), **options)
                saved += 1
            except (OSError, pi.PictureError, ValueError) as exc:
                failed.append(f"{asset.shown} {frame.label}: {exc}")
            done += 1
            if progress is not None and progress(done, total) is False:
                return saved, failed
    return saved, failed


# ------------------------------------------------------------------ the cache: every picture of the game

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def cache_root(root: Path | None = None) -> Path:
    return Path(root) if root is not None else pi.CACHE_ROOT / CACHE_SUBFOLDER


def game_pictures(folder: Path) -> list[str]:
    """Every picture file in a game folder's Images (read only)."""
    try:
        return sorted((p.name for p in pi.images_folder(folder).iterdir()
                       if p.is_file() and p.suffix.casefold() in PICTURE_EXTENSIONS), key=str.casefold)
    except OSError:
        return []


# A picture each game ships and no other game has, so one game's folder (or cache) is never taken for
# another's: the villager sheets the Studio requires are shared (A New Home's are in The Lost Children and
# The Secret City, The Tree of Life's in New Believers).  Each was checked against all five installs.
GAME_MARKERS = {1: ("berry1.png",), 2: ("briars.png",), 3: ("alchemylab.png",), 4: ("blacktreesap.png",),
                5: ("blinkyeyes.png",)}


def is_games_pictures(game: int, names) -> bool:
    """Whether a list of Images file names is this game's (it has the game's own marker pictures)."""
    have = {n.casefold() for n in names}
    return all(m.casefold() in have for m in GAME_MARKERS[game])


def is_everything_folder(game: int, folder: Path) -> bool:
    """Whether `folder` is this game's folder: its Images has pictures, among them the game's markers."""
    return is_games_pictures(game, game_pictures(Path(folder)))


class EverythingCache:
    """The Everything tab's copy of one game's pictures (every file of its Images), checked against its
    manifest before use."""

    def __init__(self, game: int, root: Path | None = None, folder: Path | None = None) -> None:
        self.folder = Path(folder) if folder is not None else cache_root(root) / pi.GAME_FOLDERS[game]
        self.problem = ""
        self.copy = None
        self._data: dict[str, bytes] = {}
        self._names: list[str] = []
        try:
            manifest = json.loads((self.folder / pi.MANIFEST).read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.problem = "no cache"
            return
        except (OSError, ValueError) as exc:
            self.problem = f"its manifest could not be read ({exc})"
            return
        if not isinstance(manifest, dict) or manifest.get("format") != pi.CACHE_FORMAT + " (Everything)" \
                or manifest.get("version") != pi.CACHE_VERSION or manifest.get("game") != game \
                or not isinstance(manifest.get("files"), dict) or not manifest["files"]:
            self.problem = "its manifest is not this version's"
            return
        for name, entry in manifest["files"].items():
            if not isinstance(entry, dict) or Path(name).name != name:
                self.problem = f"its manifest entry for {name!r} is not valid"
                return
            try:
                data = (self.folder / name).read_bytes()
            except OSError:
                self.problem = f"{name} is missing from it"
                return
            if len(data) != entry.get("size") or _sha256(data) != str(entry.get("sha256", "")).upper() \
                    or not is_picture(data):
                self.problem = f"{name} does not match its manifest"
                return
            self._data[name.casefold()] = data
            self._names.append(name)
        if not is_games_pictures(game, self._names):
            self.problem = f"it holds another game's pictures, not {pi.GAME_FOLDERS[game]}'s"
            self._data, self._names = {}, []
            return
        self.copy = manifest.get("built_from")

    @property
    def ok(self) -> bool:
        return not self.problem

    def read(self, name: str) -> bytes | None:
        return self._data.get(name.casefold())

    def names(self) -> list[str]:
        return list(self._names)


class GameFolderSource:
    """A game folder's Images, read straight from it (read only)."""

    def __init__(self, folder: Path) -> None:
        self.copy = Path(folder)
        self.problem = ""

    def read(self, name: str) -> bytes | None:
        return pi._read_from(pi.images_folder(self.copy), name)

    def names(self) -> list[str]:
        return game_pictures(self.copy)


def build_everything_cache(game: int, folder: Path, root: Path | None = None) -> tuple[bool, str]:
    """(built, why not): copy every picture of a game folder's Images (read only) into the cache, all or
    nothing: written in a temporary folder beside it, checked, then swapped in."""
    root = cache_root(root)
    final = root / pi.GAME_FOLDERS[game]
    names = game_pictures(folder)
    if not names:
        return False, f"{folder} has no pictures in an Images folder."
    if not is_games_pictures(game, names):
        return False, f"{folder} is not a Virtual Villagers - {pi.GAME_FOLDERS[game]} game folder."
    temp = root / f".{final.name}.building-{uuid.uuid4().hex[:12]}"
    old = root / f".{final.name}.old-{uuid.uuid4().hex[:12]}"
    try:
        root.mkdir(parents=True, exist_ok=True)
        for leftover in root.glob(f".{final.name}.*"):
            if leftover.is_dir():
                shutil.rmtree(leftover, ignore_errors=True)
        temp.mkdir()
        entries = {}
        for name in names:
            data = pi._read_from(pi.images_folder(folder), name)
            if data is None or not is_picture(data):
                continue                       # not a picture the games read (a stray file): left out
            (temp / name).write_bytes(data)
            entries[name] = {"size": len(data), "sha256": _sha256(data)}
        manifest = {"format": pi.CACHE_FORMAT + " (Everything)", "version": pi.CACHE_VERSION, "game": game,
                    "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "built_from": str(folder), "files": entries}
        (temp / pi.MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        check = EverythingCache(game, folder=temp)
        if not check.ok:
            raise OSError(f"the new cache did not read back: {check.problem}")
        if final.exists():
            os.replace(final, old)
        os.replace(temp, final)
    except OSError as exc:
        shutil.rmtree(temp, ignore_errors=True)
        if old.exists() and not final.exists():
            try:
                os.replace(old, final)
            except OSError:
                pass
        return False, f"The picture cache could not be written in {root} ({exc})."
    shutil.rmtree(old, ignore_errors=True)
    return True, ""


def read_patcher_art(where) -> bytes | None:
    """One piece of the patcher's own art: a file (a Path), or a picture inside a shipped companion DLL
    ((dll Path, resource type, resource id), read with vv_picture_image.pe_resource), read only."""
    try:
        if isinstance(where, tuple):
            dll, kind, ident = where
            return pi.pe_resource(Path(dll).read_bytes(), int(kind), int(ident))
        return Path(where).read_bytes()
    except OSError:
        return None


REPO = Path(__file__).resolve().parents[1]
# The Origins companion each game's release installs, which carries the Origins icons (icon groups 101-110,
# RT_GROUP_ICON 14 / RT_ICON 3, PNG images) -- the release ships these DLLs, not the loose assets\origins\*.png.
ORIGINS_DLLS = {1: "assets/origins/VVFP VV1 Origins Icons.dll", 2: "assets/origins/VVFP VV2 Origins Icons.dll",
                3: "data/candidates/VVFP VV3 Safe Upgrades.dll", 4: "assets/origins/VVFP VV4 Origins Icons.dll",
                5: "data/candidates/VVFP VV5 Task9 Origins Icons.dll"}


def origins_icon(game: int, group: int):
    """(dll, RT_ICON, id) of the largest PNG image of Origins icon `group` (101-110) in the game's shipped
    Origins companion, or None."""
    dll = REPO / ORIGINS_DLLS[game]
    try:
        data = dll.read_bytes()
    except OSError:
        return None
    directory = pi.pe_resource(data, 14, group)
    if not directory or len(directory) < 6:
        return None
    count = struct.unpack_from("<H", directory, 4)[0]
    best = None
    for k in range(count):
        if 6 + 14 * k + 14 > len(directory):
            break
        width, _h, _c, _r, _p, _b, _size, ident = struct.unpack_from("<BBBBHHIH", directory, 6 + 14 * k)
        width = width or 256
        image = pi.pe_resource(data, 3, ident) or b""
        if image.startswith(pi.PNG_MAGIC) and (best is None or width > best[0]):
            best = (width, ident)
    return (dll, 3, best[1]) if best else None


# The patcher's replacement art for a game's own pictures (its "new" folders, which the release ships): drawn by
# the game in place of the picture of the same name, so cut as that picture is.
MOD_ART = {1: (("Visual Mods", "data/vv1_visual_mods/new/Images"),),
           5: (("Guardians of Isola", "data/guardians_of_isola/new/Images"),)}


def mod_art(game: int) -> dict[str, tuple[str, str, Path]]:
    """{overlay name: (mod, the game picture it replaces, file)} for the game's replacement art."""
    out = {}
    for mod, folder in MOD_ART.get(game, ()):
        try:
            files = sorted(p for p in (REPO / folder).iterdir() if p.suffix.casefold() in PICTURE_EXTENSIONS)
        except OSError:
            continue
        for path in files:
            out[f"vvfp {mod} - {path.name}"] = (mod, path.name, path)
    return out


def mod_art_assets(game: int, sheets: AssetSheets, table) -> list[Asset]:
    """The replacement art, each cut as the game cuts the picture it replaces (its sprite in `table`)."""
    specs = {}
    for spec in table:
        files = spec.files()
        if len(files) == 1:
            specs.setdefault(files[0].casefold(), spec)
    out = []
    for name, (mod, replaces, _path) in mod_art(game).items():
        if not sheets.has(name):
            continue
        spec = specs.get(replaces.casefold())
        if spec is not None:
            spec = SheetSpec(name, spec.cols, spec.rows, whole=spec.whole, used=spec.used, where=spec.where)
            frames = sheet_frames(sheets, spec)
            note = f"drawn by the game in place of {replaces}, cut as the game cuts it"
        else:
            frames = (Frame("whole", (whole_plan(sheets, name),)),)
            note = f"replaces {replaces}"
        out.append(Asset(f"mod:{name}", PATCHER, f"{replaces} ({mod})", frames, group=mod, patcher=True, note=note,
                         proof="constructor" if spec is not None else "sheet"))
    return out


class PatcherOverlay:
    """The patcher's own art (by name) first, then the game's pictures."""

    def __init__(self, base, patcher: dict | None = None) -> None:
        self.base = base
        self.patcher = {name.casefold(): (name, where if isinstance(where, tuple) else Path(where))
                        for name, where in (patcher or {}).items()}
        self.problem = getattr(base, "problem", "") if base is not None else ""
        self.copy = getattr(base, "copy", None)
        self._read: dict[str, bytes | None] = {}

    def read(self, name: str) -> bytes | None:
        key = name.casefold()
        entry = self.patcher.get(key)
        if entry is not None:
            if key not in self._read:
                self._read[key] = read_patcher_art(entry[1])
            return self._read[key]
        return self.base.read(name) if self.base is not None else None

    def names(self) -> list[str]:
        """The game's pictures only (the patcher's art is listed by the game module's own assets)."""
        lister = getattr(self.base, "names", None)
        return lister() if callable(lister) else []


def picture_source(game: int, folders, patcher: dict | None = None, root: Path | None = None,
                   prefer: Path | None = None) -> PatcherOverlay:
    """The Everything tab's pictures for a game: the cache when it is whole and this game's; else built
    from the first of `folders` that is this game's folder; else read from that folder; else none (with
    why).  `prefer` (the folder just picked with "Find game...") replaces the cache when it was built from
    another folder."""
    cache = EverythingCache(game, root)
    if cache.ok and (prefer is None or str(cache.copy) == str(prefer)):
        return PatcherOverlay(cache, patcher)
    if prefer is not None:
        folders = [prefer, *folders]
    found = [Path(f) for f in dict.fromkeys(str(f) for f in folders if f) if is_everything_folder(game, Path(f))]
    for folder in found:
        built, _why = build_everything_cache(game, folder, root)
        if built:
            cache = EverythingCache(game, root)
            if cache.ok:
                return PatcherOverlay(cache, patcher)
    if found:
        return PatcherOverlay(GameFolderSource(found[0]), patcher)
    overlay = PatcherOverlay(None, patcher)
    overlay.problem = (f"The pictures come from your own copy of Virtual Villagers - {pi.GAME_FOLDERS[game]}, and "
                       "none was found yet: click \"Find game...\" and pick its game folder (the one with the Images "
                       "folder).")
    return overlay


def load(game: int, folders=(), root: Path | None = None, prefer: Path | None = None):
    """(sheets, module, assets, problem) for the Everything tab."""
    module = load_module(game)
    patcher = dict(module.patcher_art()) if module is not None and hasattr(module, "patcher_art") else {}
    patcher.update({name: path for name, (_mod, _replaces, path) in mod_art(game).items()})
    source = picture_source(game, folders, patcher, root, prefer)
    sheets = AssetSheets(source)
    problem = source.problem
    try:
        assets = all_assets(game, sheets, module) if source.base is not None else []
    except Exception as exc:                   # noqa: BLE001 -- shown, never fatal
        assets, problem = [], f"The pictures could not be listed ({exc})."
    return sheets, module, assets, problem


# ------------------------------------------------------------------ contact sheets (for the docs and checks)

def contact_sheet(sheets: pi.Sheets, assets, columns: int = 10, cell: int = 128, gap: int = 6,
                  frames_per_asset: int = 8, background=(236, 236, 236, 255)) -> pi.Image:
    """A grid of thumbnails: up to `frames_per_asset` frames of each asset, each shrunk (never enlarged) to
    fit `cell` x `cell`, on a light background (no labels: the scripts/ writer adds them)."""
    tiles: list[pi.Image] = []
    for asset in assets:
        frames = frames_of(sheets, asset) if isinstance(sheets, AssetSheets) else asset.frames
        if len(frames) > frames_per_asset:
            step = len(frames) / frames_per_asset
            frames = tuple(frames[int(i * step)] for i in range(frames_per_asset))
        for frame in frames:
            try:
                image = render_frame(sheets, frame).cropped(0)
            except (pi.PictureError, OSError, ValueError):
                image = pi.Image(1, 1)
            biggest = max(image.width, image.height)
            if biggest > cell:
                f = biggest / cell
                image = image.resized(max(1, int(image.width / f)), max(1, int(image.height / f)))
            tiles.append(image)
    rows = max(1, -(-len(tiles) // columns))
    out = pi.Image(columns * (cell + gap) + gap, rows * (cell + gap) + gap)
    out.data[:] = bytes(background) * (out.width * out.height)
    for i, tile in enumerate(tiles):
        r, c = divmod(i, columns)
        x = gap + c * (cell + gap) + (cell - tile.width) // 2
        y = gap + r * (cell + gap) + (cell - tile.height) // 2
        out.draw(tile, x, y)
    return out
