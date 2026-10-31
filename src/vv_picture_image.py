"""Picture Studio's shared pieces (the Tools tab's "Picture Studio...", src/vv_picture_studio.py): an
RGBA image, a PNG reader and writer, the export sizes, the games' sprite atlases and blitter, and the
Studio's own picture cache.  Pure Python (zlib and struct only): the patcher ships no Pillow, and Tk
cannot write PNGs with alpha reliably.

The Image, PNG and export code is the Fish & Plant Tycoon Fix Patcher's Picture Studio's
(picture_image.py), unchanged.  What is the Virtual Villagers games' own:

* Atlas: the engine's sprite atlas -- one sheet ("male_heads.png", 7 x 20 cells) or a grid of sheets
  ("male_bodies" 2 x 2 sheets: male_bodies00.png ... male_bodies11.png, 32 x 20 cells) -- and how it
  cuts a cell (A New Home's 0x409F90; the constructors 0x40A070 and 0x40A0F0).
* Draw / composite: one blit of a cell at a place, a scale and a surface alpha, as the engine's
  software blitter draws it (A New Home's 0x403D70), proven pixel for pixel by tests/test_picture_studio.py.

Each game's renderer (src/vv_pictures_vv1.py ... vv_pictures_vv5.py) plans its draws from the game's
own villager draw code (docs/picture-studio.md).  No game art ships with the patcher: the sheets are
read from the player's own game folder and kept in "Picture Studio Pictures" beside the patcher.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import uuid
import zlib

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MARGIN = 4
SIZES = (("1x", 1), ("2x", 2), ("4x", 4))
MAX_SIDE = 8192                 # the largest picture the Studio writes (a custom size is capped)


class PictureError(Exception):
    """A picture that cannot be drawn or read, in words for the player."""


# ------------------------------------------------------------------ the image


class Image:
    """Straight (not premultiplied) 8-bit RGBA, rows top to bottom."""

    __slots__ = ("width", "height", "data")

    def __init__(self, width: int, height: int, data: bytearray | None = None) -> None:
        if width < 0 or height < 0:
            raise ValueError("an image cannot have a negative size")
        self.width, self.height = int(width), int(height)
        self.data = bytearray(self.width * self.height * 4) if data is None else bytearray(data)
        if len(self.data) != self.width * self.height * 4:
            raise ValueError("the pixel data does not fit the size")

    @classmethod
    def new(cls, width: int, height: int) -> "Image":
        return cls(width, height)

    @classmethod
    def from_png(cls, data: bytes) -> "Image":
        return decode_png(data)

    def to_png(self) -> bytes:
        return encode_png(self)

    def copy(self) -> "Image":
        return Image(self.width, self.height, self.data)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Image) and (self.width, self.height) == (other.width, other.height) \
            and self.data == other.data

    def __repr__(self) -> str:
        return f"Image({self.width}x{self.height})"

    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]:
        at = (y * self.width + x) * 4
        return tuple(self.data[at:at + 4])

    def sub(self, x: int, y: int, w: int, h: int) -> "Image":
        """The w x h piece at (x, y); any part outside the image is transparent."""
        out = Image(w, h)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 <= x0 or y1 <= y0:
            return out
        row = (x1 - x0) * 4
        for yy in range(y0, y1):
            src = (yy * self.width + x0) * 4
            dst = ((yy - y) * w + (x0 - x)) * 4
            out.data[dst:dst + row] = self.data[src:src + row]
        return out

    def cell(self, cols: int, rows: int, index: int) -> "Image":
        """Cell `index` of a cols x rows grid (cells numbered across, then down; see cell_rect)."""
        left, top, right, bottom = cell_rect(self.width, self.height, cols, rows, index)
        return self.sub(left, top, right - left, bottom - top)

    def flipped(self) -> "Image":
        out = Image(self.width, self.height)
        stride = self.width * 4
        for y in range(self.height):
            row = self.data[y * stride:(y + 1) * stride]
            pixels = [row[i:i + 4] for i in range(0, stride, 4)]
            out.data[y * stride:(y + 1) * stride] = b"".join(reversed(pixels))
        return out

    def draw(self, src: "Image", x: int, y: int, alpha: int = 255, tint=None) -> None:
        """src over this image at (x, y), clipped. `alpha` multiplies src's alpha (SDL's
        per-surface alpha); `tint` (r, g, b) multiplies its colour (a colour mod)."""
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + src.width), min(self.height, y + src.height)
        if x1 <= x0 or y1 <= y0 or alpha <= 0:
            return
        alpha = min(255, int(alpha))
        # The games' blitter (Fish Tycoon 0x4041C0, 0x404D5E): each pixel's alpha a becomes
        # (a * A + 127) >> 8 under a surface alpha A below 255.
        weights = None if alpha == 255 else bytes((a * alpha + 127) >> 8 for a in range(256))
        sd, dd = src.data, self.data
        tr, tg, tb = tint if tint is not None else (255, 255, 255)
        for yy in range(y0, y1):
            s = ((yy - y) * src.width + (x0 - x)) * 4
            d = (yy * self.width + x0) * 4
            for _ in range(x1 - x0):
                sa = sd[s + 3]
                if sa:
                    if weights is not None:
                        sa = weights[sa]
                    r, g, b = sd[s], sd[s + 1], sd[s + 2]
                    if tint is not None:
                        r, g, b = r * tr // 255, g * tg // 255, b * tb // 255
                    if sa == 255:
                        dd[d], dd[d + 1], dd[d + 2], dd[d + 3] = r, g, b, 255
                    elif sa:
                        da = dd[d + 3]
                        if da == 0:
                            dd[d], dd[d + 1], dd[d + 2], dd[d + 3] = r, g, b, sa
                        else:
                            # straight-alpha "over": out = src + dst * (1 - src_a)
                            keep = da * (255 - sa)            # dst weight, x 255
                            oa255 = sa * 255 + keep           # out alpha, x 255
                            dd[d] = (r * sa * 255 + dd[d] * keep + oa255 // 2) // oa255
                            dd[d + 1] = (g * sa * 255 + dd[d + 1] * keep + oa255 // 2) // oa255
                            dd[d + 2] = (b * sa * 255 + dd[d + 2] * keep + oa255 // 2) // oa255
                            dd[d + 3] = (oa255 + 127) // 255
                s += 4
                d += 4

    def bbox(self) -> tuple[int, int, int, int] | None:
        """(left, top, right, bottom), right and bottom exclusive, of the pixels with any alpha."""
        w, h, data = self.width, self.height, self.data
        alphas = data[3::4]
        top = bottom = None
        left, right = w, 0
        for y in range(h):
            row = alphas[y * w:(y + 1) * w]
            if any(row):
                if top is None:
                    top = y
                bottom = y + 1
                first = next(i for i, a in enumerate(row) if a)
                last = w - next(i for i, a in enumerate(reversed(row)) if a)
                left, right = min(left, first), max(right, last)
        if top is None:
            return None
        return left, top, right, bottom

    def cropped(self, margin: int = MARGIN) -> "Image":
        """Cut to the drawn pixels plus `margin` transparent pixels each side; an image with
        nothing drawn is 1 x 1 transparent (plus the margin)."""
        box = self.bbox()
        if box is None:
            return Image(1 + 2 * margin, 1 + 2 * margin)
        left, top, right, bottom = box
        return self.sub(left - margin, top - margin, right - left + 2 * margin, bottom - top + 2 * margin)

    def scaled(self, factor: int) -> "Image":
        """Nearest neighbour, crisp: every pixel becomes factor x factor."""
        factor = int(factor)
        if factor < 1:
            raise ValueError("the scale must be 1 or more")
        if factor == 1:
            return self.copy()
        out = Image(self.width * factor, self.height * factor)
        stride = self.width * 4
        out_stride = stride * factor
        for y in range(self.height):
            row = self.data[y * stride:(y + 1) * stride]
            wide = b"".join(bytes(row[i:i + 4]) * factor for i in range(0, stride, 4))
            for k in range(factor):
                at = (y * factor + k) * out_stride
                out.data[at:at + out_stride] = wide
        return out

    def resized(self, width: int, height: int) -> "Image":
        """Smooth scaling to width x height: a linear (triangle) filter, widened when shrinking
        so every source pixel counts, on premultiplied colour so transparent edges stay clean."""
        width, height = int(width), int(height)
        if width < 1 or height < 1:
            raise ValueError("a picture must be at least 1 x 1")
        if (width, height) == (self.width, self.height):
            return self.copy()
        # premultiply into floats per channel
        n = self.width * self.height
        src = self.data
        pre = [0.0] * (n * 4)
        for i in range(n):
            a = src[i * 4 + 3]
            if a:
                f = a / 255.0
                pre[i * 4] = src[i * 4] * f
                pre[i * 4 + 1] = src[i * 4 + 1] * f
                pre[i * 4 + 2] = src[i * 4 + 2] * f
                pre[i * 4 + 3] = float(a)
        horizontal = _resample_weights(self.width, width)
        vertical = _resample_weights(self.height, height)
        # pass 1: rows
        mid = [0.0] * (width * self.height * 4)
        for y in range(self.height):
            base = y * self.width * 4
            out = y * width * 4
            for x, (first, weights) in enumerate(horizontal):
                r = g = b = a = 0.0
                at = base + first * 4
                for wgt in weights:
                    r += pre[at] * wgt
                    g += pre[at + 1] * wgt
                    b += pre[at + 2] * wgt
                    a += pre[at + 3] * wgt
                    at += 4
                o = out + x * 4
                mid[o], mid[o + 1], mid[o + 2], mid[o + 3] = r, g, b, a
        # pass 2: columns, then un-premultiply
        result = Image(width, height)
        dd = result.data
        row4 = width * 4
        for y, (first, weights) in enumerate(vertical):
            for x in range(width):
                r = g = b = a = 0.0
                at = first * row4 + x * 4
                for wgt in weights:
                    r += mid[at] * wgt
                    g += mid[at + 1] * wgt
                    b += mid[at + 2] * wgt
                    a += mid[at + 3] * wgt
                    at += row4
                o = (y * width + x) * 4
                alpha = int(a + 0.5)
                if alpha <= 0:
                    continue
                dd[o] = max(0, min(255, int(r / a * 255.0 + 0.5)))
                dd[o + 1] = max(0, min(255, int(g / a * 255.0 + 0.5)))
                dd[o + 2] = max(0, min(255, int(b / a * 255.0 + 0.5)))
                dd[o + 3] = min(255, alpha)
        return result

    def photo(self, tk_mod, master, max_side: int | None = None):
        """A Tk PhotoImage of this image (Tk reads PNG alpha), shrunk by whole steps to fit
        `max_side`, or blown up crisply when small."""
        image = self
        if max_side:
            biggest = max(1, image.width, image.height)
            if biggest > max_side:
                factor = -(-biggest // max_side)
                image = image.resized(max(1, image.width // factor), max(1, image.height // factor))
        return tk_mod.PhotoImage(master=master, data=base64.b64encode(image.to_png()))


def _resample_weights(src: int, dst: int) -> list[tuple[int, list[float]]]:
    """For each output position, (first source index, weights) of a triangle filter."""
    scale = dst / src
    support = max(1.0, 1.0 / scale)
    out = []
    for i in range(dst):
        centre = (i + 0.5) / scale
        lo = max(0, int(centre - support))
        hi = min(src, int(centre + support) + 1)
        weights = []
        for j in range(lo, hi):
            wgt = 1.0 - abs((j + 0.5 - centre) / support)
            weights.append(max(0.0, wgt))
        total = sum(weights)
        if total <= 0:
            nearest = min(src - 1, max(0, int(centre)))
            out.append((nearest, [1.0]))
            continue
        # trim zero weights at the ends
        while weights and weights[0] == 0.0:
            weights.pop(0)
            lo += 1
        while weights and weights[-1] == 0.0:
            weights.pop()
        out.append((lo, [w / total for w in weights]))
    return out


# ------------------------------------------------------------------ PNG


def _chunks(data: bytes):
    if not data.startswith(PNG_MAGIC):
        raise PictureError("not a PNG file")
    at = 8
    while at + 8 <= len(data):
        length, kind = struct.unpack_from(">I4s", data, at)
        body = data[at + 8:at + 8 + length]
        if len(body) != length:
            raise PictureError("the PNG file is cut short")
        yield kind, body
        at += 12 + length
        if kind == b"IEND":
            return


def _unfilter(raw: bytes, width: int, height: int, bpp: int, row_bytes: int) -> bytearray:
    """Undo the PNG row filters (None, Sub, Up, Average, Paeth)."""
    out = bytearray(height * row_bytes)
    prev = bytearray(row_bytes)
    at = 0
    for y in range(height):
        kind = raw[at]
        line = bytearray(raw[at + 1:at + 1 + row_bytes])
        at += 1 + row_bytes
        if len(line) != row_bytes:
            raise PictureError("the PNG image data is cut short")
        if kind == 0:
            pass
        elif kind == 1:
            for i in range(bpp, row_bytes):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif kind == 2:
            line = bytearray((a + b) & 0xFF for a, b in zip(line, prev))
        elif kind == 3:
            for i in range(row_bytes):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(row_bytes):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                if pa <= pb and pa <= pc:
                    pred = a
                elif pb <= pc:
                    pred = b
                else:
                    pred = c
                line[i] = (line[i] + pred) & 0xFF
        else:
            raise PictureError(f"the PNG uses an unknown row filter ({kind})")
        out[y * row_bytes:(y + 1) * row_bytes] = line
        prev = line
    return out


def decode_png(data: bytes) -> Image:
    """Any non-interlaced PNG: grey, grey+alpha, RGB, RGBA (8 or 16 bits) or palette (1-8
    bits), with tRNS transparency. Returns straight RGBA."""
    header = None
    palette = b""
    trns = None
    idat = []
    for kind, body in _chunks(bytes(data)):
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            trns = body
        elif kind == b"IDAT":
            idat.append(body)
    if header is None:
        raise PictureError("the PNG has no header")
    width, height, depth, colour, _comp, _filter, interlace = header
    if interlace:
        raise PictureError("interlaced PNGs are not read")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour)
    if channels is None or depth not in (1, 2, 4, 8, 16):
        raise PictureError("the PNG's colour format is not one the games use")
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        raise PictureError(f"the PNG image data could not be unpacked ({exc})") from None
    bits = depth * channels
    row_bytes = (width * bits + 7) // 8
    bpp = max(1, bits // 8)
    rows = _unfilter(raw, width, height, bpp, row_bytes)
    image = Image(width, height)
    out = image.data
    if depth == 16:                      # keep the high byte of each sample
        rows = rows[0::2]
        row_bytes //= 2
        depth = 8
    if colour == 6 and depth == 8:
        out[:] = rows
    elif colour == 2 and depth == 8:
        key = struct.unpack(">HHH", trns) if trns and len(trns) >= 6 else None
        out[0::4] = rows[0::3]
        out[1::4] = rows[1::3]
        out[2::4] = rows[2::3]
        out[3::4] = b"\xff" * (width * height)
        if key is not None:
            key = bytes(k & 0xFF for k in key)
            for i in range(width * height):
                if out[i * 4:i * 4 + 3] == key:
                    out[i * 4 + 3] = 0
    elif colour == 4 and depth == 8:
        out[0::4] = rows[0::2]
        out[1::4] = rows[0::2]
        out[2::4] = rows[0::2]
        out[3::4] = rows[1::2]
    elif colour in (0, 3):
        if colour == 3:
            entries = len(palette) // 3
            alpha = list(trns or b"") + [255] * 256
            table = [bytes(palette[i * 3:i * 3 + 3]) + bytes([alpha[i]]) for i in range(entries)]
            table += [b"\0\0\0\xff"] * (256 - entries)
        else:
            levels = (1 << depth) - 1
            key = struct.unpack(">H", trns[:2])[0] if trns and len(trns) >= 2 else None
            table = []
            for v in range(256):
                grey = v * 255 // levels if v <= levels else 0
                table.append(bytes((grey, grey, grey, 0 if key == v else 255)))
        per_byte = 8 // depth
        mask = (1 << depth) - 1
        pixels = bytearray()
        for y in range(height):
            line = rows[y * row_bytes:(y + 1) * row_bytes]
            if depth == 8:
                values = line[:width]
            else:
                values = [(b >> (8 - depth * (k + 1))) & mask for b in line for k in range(per_byte)][:width]
            pixels += b"".join(table[v] for v in values)
        out[:] = pixels
    else:
        raise PictureError("the PNG's colour format is not one the games use")
    return image


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def encode_png(image: Image) -> bytes:
    """An 8-bit RGBA PNG (colour type 6), every row filtered None or Sub, whichever packs
    smaller (Up for rows that repeat)."""
    stride = image.width * 4
    raw = bytearray()
    prev = bytes(stride)
    for y in range(image.height):
        row = bytes(image.data[y * stride:(y + 1) * stride])
        if row == prev and y:
            raw += b"\x02" + bytes(stride)
        else:
            raw += b"\x00" + row
        prev = row
    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0)
    return PNG_MAGIC + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) \
        + _chunk(b"IEND", b"")


# ------------------------------------------------------------------ export


def export(image: Image, *, scale: int = 1, size: tuple[int, int] | None = None, margin: int = MARGIN) -> Image:
    """Crop to the drawn pixels plus `margin` (0: none), then scale: `scale` crisply
    (nearest neighbour) or `size=(w, h)` smoothly; a 0 in size keeps the aspect ratio."""
    out = image.cropped(max(0, int(margin)))
    if size is not None:
        w, h = (int(v or 0) for v in size)
        if w <= 0 and h <= 0:
            raise PictureError("Give a width, a height or both.")
        if w <= 0:
            w = max(1, round(out.width * h / out.height))
        if h <= 0:
            h = max(1, round(out.height * w / out.width))
        if w > MAX_SIDE or h > MAX_SIDE:
            raise PictureError(f"A picture can be at most {MAX_SIDE} pixels wide or high.")
        return out.resized(w, h)
    scale = int(scale)
    if scale < 1 or out.width * scale > MAX_SIDE or out.height * scale > MAX_SIDE:
        raise PictureError(f"A picture can be at most {MAX_SIDE} pixels wide or high.")
    return out.scaled(scale)


def save_png(image: Image, path, **options) -> Path:
    """Export (see `export`) and write the PNG through a temporary file beside it, so a
    failed write never leaves half a file."""
    path = Path(path)
    data = export(image, **options).to_png()
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return path


_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_file_name(text: str, limit: int = 80) -> str:
    """A label as a Windows file name (no extension): forbidden characters become "-", no
    trailing dot or space, never a reserved device name, never empty."""
    name = _BAD.sub("-", str(text)).strip().rstrip(". ")[:limit].rstrip(". ")
    if not name:
        name = "picture"
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return name


def unique_path(folder: Path, stem: str, suffix: str = ".png") -> Path:
    """folder/stem.png, or "stem (2).png" and so on when that name is taken."""
    path = Path(folder) / f"{stem}{suffix}"
    n = 2
    while path.exists():
        path = Path(folder) / f"{stem} ({n}){suffix}"
        n += 1
    return path


# ------------------------------------------------------------------ what renderers return


@dataclass(frozen=True)
class SavedItem:
    """One thing in a save the window lists: `id` is the renderer's own (stable for one read of
    the save), `label` the line shown and the PNG's name, `location` the group it is listed under
    ("Villagers", "Bodies awaiting burial", "Statues" ...), `kind` a word for the Kind column."""
    id: str
    label: str
    location: str
    kind: str
    detail: str = ""


@dataclass(frozen=True)
class Option:
    key: object
    label: str
    patcher: bool = False          # added by a patcher feature (the window marks it "(patcher)")


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    options: tuple
    default: object = None


@dataclass(frozen=True)
class Subject:
    """One "Make your own" tab (the villager; a game may add others, a statue, a ghost ...)."""
    key: str
    title: str
    fields: tuple
    note: str = ""


# ------------------------------------------------------------------ the engine's sprite atlases


@dataclass(frozen=True)
class Atlas:
    """A sprite atlas as the games' engine builds it (A New Home 0x40A070 / 0x40A0F0, the same code in
    every game): `name` is one sheet ("male_heads.png") or, with `sheets` (across, down) other than
    (1, 1), the prefix of a grid of sheets named prefix + across + down + suffix
    ("male_bodies" -> male_bodies00.png, male_bodies10.png, male_bodies01.png ...), cut into
    `cols` x `rows` cells across the whole grid."""
    name: str
    cols: int
    rows: int
    sheets: tuple = (1, 1)
    suffix: str = ".png"

    @property
    def grid(self) -> bool:
        return tuple(self.sheets) != (1, 1)

    def files(self) -> list[str]:
        """Every sheet file, in the order the constructor loads them (across, then down)."""
        if not self.grid:
            return [self.name]
        across, down = self.sheets
        return [f"{self.name}{x}{y}{self.suffix}" for y in range(down) for x in range(across)]

    def cell(self, size, col: int, row: int) -> tuple[str, tuple[int, int, int, int]]:
        """(sheet file, (left, top, right, bottom)) of cell (col, row), as 0x409F90 cuts it.
        `size(name)` gives a sheet's (width, height).

        One sheet: the cell is width // cols by height // rows; the column and row are clamped to
        the last one.  A grid: the cell is (the last row of sheets' summed width) // cols by (the
        summed heights of each row's last sheet) // rows; the first sheet's size in cells says how
        many columns and rows each sheet holds; (col, row) picks the sheet across // and down //,
        wrapping past the last sheet, and its place in that sheet is the remainder (then clamped as
        a single sheet's is)."""
        if not self.grid:
            w, h = size(self.name)
            cw, ch = w // self.cols, h // self.rows
            col = min(col, self.cols - 1)
            row = min(row, self.rows - 1)
            return self.name, (cw * col, ch * row, cw * col + cw, ch * row + ch)
        files = self.files()
        across, down = self.sheets
        sum_w = sum(size(files[(down - 1) * across + x])[0] for x in range(across))
        sum_h = sum(size(files[y * across + across - 1])[1] for y in range(down))
        cw, ch = sum_w // self.cols, sum_h // self.rows
        first_w, first_h = size(files[0])
        per_col, per_row = first_w // cw, first_h // ch
        sheet_row, local_row = _cdivmod(row, per_row)
        sheet_col, local_col = _cdivmod(col, per_col)
        index = across * sheet_row + sheet_col
        if index >= across * down:
            index = _cdivmod(index, across * down)[1]
        local_col = min(local_col, self.cols - 1)
        local_row = min(local_row, self.rows - 1)
        return files[index], (cw * local_col, ch * local_row, cw * local_col + cw, ch * local_row + ch)


def _cdivmod(a: int, b: int) -> tuple[int, int]:
    """C's a / b and a % b (toward zero), as the game's idiv gives them."""
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return q, a - q * b


def f32(value: float) -> float:
    """The value as a 32-bit float, as the game stores it."""
    return struct.unpack("<f", struct.pack("<f", value))[0]


def percent_scale(percent: int) -> float:
    """The blitter's scale for an integer percentage, as A New Home's 0x408AF0 makes it: fild the
    percentage, fmul by the 32-bit 0.01 at 0x457454, fstp to a 32-bit float."""
    return f32(int(percent) * f32(0.01))


def scaled_size(w: int, h: int, scale: float) -> tuple[int, int]:
    """The blitter's drawn size (0x403D70: fild, fmul by the 32-bit scale, ftol): truncated."""
    return int(w * scale), int(h * scale)


def centre_offset(w: int, h: int, percent: int) -> tuple[int, int]:
    """How far A New Home's place-scaled 0x407ED0 moves a cell's top-left when it centres a cell
    drawn at `percent`: the rounded size is ftol(w x s + 0.5), and x moves by -((rounded - w) / 2)
    in C's division."""
    if percent == 100:
        return 0, 0
    s = f32(int(percent) * f32(0.01))
    rw, rh = int(w * s + 0.5), int(h * s + 0.5)
    return -_cdivmod(rw - w, 2)[0], -_cdivmod(rh - h, 2)[0]


def surface_alpha(alpha: float) -> int:
    """The blitter's surface alpha as a byte: ftol(alpha x 255 + 0.5) of the 32-bit alpha."""
    return int(f32(alpha) * 255.0 + 0.5)


@dataclass(frozen=True)
class Draw:
    """One blit as the game makes it: the cell `rect` (left, top, right, bottom) of sheet `file`, its
    top-left at (x, y) (after any centring the game does before the blit), drawn at `scale` (the
    blitter's own float; 1.0 is unscaled) and surface `alpha` (float; 1.0 opaque).  `what` names
    the part ("body", "head", "mask", "shadow" ...): for people, never compared by the tests."""
    file: str
    rect: tuple
    x: int
    y: int
    scale: float = 1.0
    alpha: float = 1.0
    what: str = field(default="", compare=False)

    def key(self) -> tuple:
        """What the tests compare with the game's own blit."""
        return (self.file.casefold(), tuple(self.rect), self.x, self.y, round(self.scale, 6),
                surface_alpha(self.alpha))


def blit_piece(sheet: "Image", rect: tuple, scale: float) -> "Image":
    """The pixels the game's software blitter (A New Home 0x403D70) puts down for a cell, in
    straight RGBA, before its surface alpha: unscaled, the cell itself; scaled down, each of the
    trunc(w x s) by trunc(h x s) pixels is the plain average (sums of each channel, alpha included,
    divided by the count and truncated) of a box of source pixels, the boxes laid out by a position
    that starts half a step before the cell's left (top) and grows by w / width (h / height), each
    box running from the one before it to trunc(position) + 1, never past the cell (0x404128 -
    0x4045B3, in double precision as Windows runs the x87).  Scaled up (the games' villagers never
    are): nearest pixel."""
    left, top, right, bottom = rect
    w, h = right - left, bottom - top
    if scale == 1.0 or w <= 0 or h <= 0:
        return sheet.sub(left, top, w, h)
    dw, dh = scaled_size(w, h, scale)
    if dw <= 0 or dh <= 0:
        return Image(0, 0)
    out = Image(dw, dh)
    src, dst, sw = sheet.data, out.data, sheet.width
    if scale > 1.0:
        xs = [left + min(w - 1, int(i * w / dw)) for i in range(dw)]
        ys = [top + min(h - 1, int(j * h / dh)) for j in range(dh)]
        for j, sy in enumerate(ys):
            for i, sx in enumerate(xs):
                s_at, d_at = (sy * sw + sx) * 4, (j * dw + i) * 4
                dst[d_at:d_at + 4] = src[s_at:s_at + 4]
        return out

    def spans(first: int, size: int, n: int) -> list[tuple[int, int]]:
        step = size / n
        last = first + size - 1
        pos = first - 0.5 * step
        prev = first - 1
        result = []
        for _ in range(n):
            pos += step
            end = min(int(pos) + 1, last)
            result.append((prev + 1, end))
            prev = end
        return result

    xs, ys = spans(left, w, dw), spans(top, h, dh)
    for j, (y0, y1) in enumerate(ys):
        if y0 > y1:
            continue
        for i, (x0, x1) in enumerate(xs):
            if x0 > x1:
                continue
            n = (x1 - x0 + 1) * (y1 - y0 + 1)
            r = g = b = a = 0
            for yy in range(y0, y1 + 1):
                at = (yy * sw + x0) * 4
                for _ in range(x1 - x0 + 1):
                    r += src[at]
                    g += src[at + 1]
                    b += src[at + 2]
                    a += src[at + 3]
                    at += 4
            d_at = (j * dw + i) * 4
            dst[d_at:d_at + 4] = bytes((r // n, g // n, b // n, a // n))
    return out


class Sheets:
    """Decoded sheets, read once from a source with .read(name) -> bytes | None."""

    def __init__(self, source) -> None:
        self.source = source
        self._images: dict = {}
        self._sizes: dict = {}

    def _data(self, name: str) -> bytes:
        data = self.source.read(name) if self.source is not None else None
        if data is None:
            raise PictureError(f"The game picture {name} was not found.")
        return data

    def image(self, name: str) -> Image:
        key = name.casefold()
        if key not in self._images:
            self._images[key] = decode_png(self._data(name))
        return self._images[key]

    def size(self, name: str) -> tuple[int, int]:
        """A sheet's (width, height), from its PNG header only."""
        key = name.casefold()
        if key not in self._sizes:
            if key in self._images:
                image = self._images[key]
                self._sizes[key] = (image.width, image.height)
            else:
                data = self._data(name)
                if not data.startswith(PNG_MAGIC) or len(data) < 24:
                    raise PictureError(f"The game picture {name} is not a PNG.")
                self._sizes[key] = struct.unpack(">II", data[16:24])
        return self._sizes[key]

    def has(self, name: str) -> bool:
        try:
            self.size(name)
        except PictureError:
            return False
        return True

    def cell(self, atlas: Atlas, col: int, row: int) -> tuple[str, tuple]:
        return atlas.cell(self.size, col, row)

    def piece(self, call: Draw) -> Image:
        key = ("piece", call.file.casefold(), tuple(call.rect), call.scale)
        cached = self._images.get(key)
        if cached is None:
            cached = blit_piece(self.image(call.file), call.rect, call.scale)
            self._images[key] = cached
        return cached


def plan_bounds(sheets: Sheets, plan) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) the plan's blits cover."""
    left = top = 10 ** 9
    right = bottom = -10 ** 9
    for call in plan:
        piece = sheets.piece(call)
        left, top = min(left, call.x), min(top, call.y)
        right, bottom = max(right, call.x + piece.width), max(bottom, call.y + piece.height)
    if left > right:
        return 0, 0, 1, 1
    return left, top, right, bottom


def composite(sheets: Sheets, plan, width: int, height: int, origin: tuple[int, int] = (0, 0)) -> Image:
    """Draw a plan (Draw calls, in the game's order) on a transparent width x height canvas, each
    blit moved by -origin."""
    canvas = Image(width, height)
    ox, oy = origin
    for call in plan:
        canvas.draw(sheets.piece(call), call.x - ox, call.y - oy, surface_alpha(call.alpha))
    return canvas


def render_plan(sheets: Sheets, plan) -> Image:
    """A plan drawn on a canvas just big enough for it."""
    left, top, right, bottom = plan_bounds(sheets, plan)
    return composite(sheets, plan, right - left, bottom - top, (left, top))


def pe_resource(data: bytes, kind: int, ident: int) -> bytes | None:
    """One resource of a PE file (the first language), pure Python: the patcher art a shipped companion DLL carries (an RCDATA picture), read without pefile."""
    try:
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe:pe + 4] != b"PE\0\0":
            return None
        sections = struct.unpack_from("<H", data, pe + 6)[0]
        opt = pe + 24
        opt_size = struct.unpack_from("<H", data, pe + 20)[0]
        rsrc_rva = struct.unpack_from("<I", data, opt + 96 + 2 * 8)[0]
        table = opt + opt_size
        spans = [struct.unpack_from("<IIII", data, table + i * 40 + 8) for i in range(sections)]

        def offset(rva: int) -> int:
            for vsize, va, rsize, raw in spans:
                if va <= rva < va + max(vsize, rsize):
                    return raw + rva - va
            raise ValueError("rva")
        root = offset(rsrc_rva)

        def find(directory: int, wanted: int | None) -> int | None:
            named, ids = struct.unpack_from("<HH", data, directory + 12)
            for k in range(named + ids):
                name, target = struct.unpack_from("<II", data, directory + 16 + 8 * k)
                if wanted is None or (not name & 0x80000000 and name == wanted):
                    return target
            return None
        level = find(root, kind)
        if level is None or not level & 0x80000000:
            return None
        level = find(root + (level & 0x7FFFFFFF), ident)
        if level is None or not level & 0x80000000:
            return None
        leaf = find(root + (level & 0x7FFFFFFF), None)
        if leaf is None or leaf & 0x80000000:
            return None
        rva, size = struct.unpack_from("<II", data, root + leaf)
        start = offset(rva)
        return bytes(data[start:start + size])
    except (struct.error, ValueError, IndexError):
        return None


# ------------------------------------------------------------------ the Studio's picture cache

CACHE_FOLDER = "Picture Studio Pictures"
CACHE_FORMAT = "Virtual Villagers Fun Patcher: Picture Studio Pictures"
CACHE_VERSION = 1
MANIFEST = "manifest.json"
CACHE_ROOT = Path(__file__).resolve().parents[1] / CACHE_FOLDER     # a test points it elsewhere
GAME_FOLDERS = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
                5: "New Believers"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def images_folder(game_folder: Path) -> Path:
    return Path(game_folder) / "Images"


def data_name(name: str) -> str | None:
    """"animpts.dat" for "Assets/animpts.dat" or "Assets\\animpts.dat": a file the renderer reads from
    the game's Assets folder (its drawing tables); None for a picture under Images."""
    text = str(name).replace("\\", "/")
    if text.casefold().startswith("assets/"):
        return text.split("/", 1)[1]
    return None


def _read_from(folder: Path, name: str) -> bytes | None:
    """`name` from a folder (read only), its letter case as the disk has it."""
    try:
        return (Path(folder) / name).read_bytes()
    except OSError:
        pass
    try:
        for entry in Path(folder).iterdir():
            if entry.name.casefold() == name.casefold() and entry.is_file():
                return entry.read_bytes()
    except OSError:
        return None
    return None


def _read_game_file(folder: Path, name: str, data_files=()) -> bytes | None:
    """A picture from the game's Images folder, or one of its data files (Assets\\<file>), read only."""
    plain = data_name(name)
    if plain is not None:
        return _read_from(Path(folder) / "Assets", plain)
    if name.casefold() in {d.casefold() for d in data_files}:
        return _read_from(Path(folder) / "Assets", name)
    return _read_from(images_folder(folder), name)


class FolderSource:
    """A game folder's Images (and Assets data files), read straight from it (read only)."""

    def __init__(self, folder: Path, data_files=()) -> None:
        self.copy = Path(folder)
        self.problem = ""
        self.data_files = tuple(data_files)

    def read(self, name: str) -> bytes | None:
        data = _read_game_file(self.copy, name, self.data_files)
        if data is None and data_name(name) is None and not name.casefold().endswith(".png"):
            data = _read_from(Path(self.copy) / "Assets", name)
        return data


class CacheSource:
    """The Studio's own copy of one game's pictures and drawing tables, checked against its manifest
    before use: a missing, changed or unlisted file, or an unreadable manifest, and it is not used."""

    def __init__(self, game: int, required, root: Path | None = None, folder: Path | None = None,
                 data_files=()) -> None:
        self.folder = Path(folder) if folder is not None else Path(root or CACHE_ROOT) / GAME_FOLDERS[game]
        self.copy = None
        self.problem = ""
        self._data: dict[str, bytes] = {}
        try:
            manifest = json.loads((self.folder / MANIFEST).read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.problem = "no cache"
            return
        except (OSError, ValueError) as exc:
            self.problem = f"its manifest could not be read ({exc})"
            return
        if not isinstance(manifest, dict) or manifest.get("format") != CACHE_FORMAT \
                or manifest.get("version") != CACHE_VERSION or manifest.get("game") != game \
                or not isinstance(manifest.get("files"), dict):
            self.problem = "its manifest is not this version's"
            return
        files = manifest["files"]
        if any(n not in files for n in list(required) + list(data_files)):
            self.problem = "it is partial"
            return
        for name, entry in files.items():
            if not isinstance(entry, dict) or Path(name).name != name:
                self.problem = f"its manifest entry for {name!r} is not valid"
                return
            try:
                data = (self.folder / name).read_bytes()
            except OSError:
                self.problem = f"{name} is missing from it"
                return
            picture = not entry.get("data")
            if len(data) != entry.get("size") or _sha256(data) != str(entry.get("sha256", "")).upper() \
                    or (picture and not data.startswith(PNG_MAGIC)):
                self.problem = f"{name} does not match its manifest"
                return
            self._data[name.casefold()] = data
        self.copy = manifest.get("built_from")

    @property
    def ok(self) -> bool:
        return not self.problem

    def read(self, name: str) -> bytes | None:
        plain = data_name(name)
        return self._data.get((plain if plain is not None else name).casefold())


def build_cache(game: int, folder: Path, required, root: Path | None = None, data_files=()) -> tuple[bool, str]:
    """(built, why not): copy every sheet the renderer needs from a game folder's Images, and every data
    file it reads from its Assets, (read only) into the cache, all or nothing: written in a temporary
    folder beside it, checked, then swapped in."""
    root = Path(root or CACHE_ROOT)
    final = root / GAME_FOLDERS[game]
    files: dict[str, tuple[bytes, bool]] = {}
    missing = []
    for name in required:
        data = _read_from(images_folder(folder), name)
        if data is None or not data.startswith(PNG_MAGIC):
            missing.append(name)
        else:
            files[name] = (data, False)
    for name in data_files:
        data = _read_from(Path(folder) / "Assets", name)
        if not data:
            missing.append(f"Assets\\{name}")
        else:
            files[name] = (data, True)
    if missing:
        shown = ", ".join(missing[:4]) + (" ..." if len(missing) > 4 else "")
        return False, f"{len(missing)} file(s) are not in {folder} ({shown})."
    temp = root / f".{final.name}.building-{uuid.uuid4().hex[:12]}"
    old = root / f".{final.name}.old-{uuid.uuid4().hex[:12]}"
    try:
        root.mkdir(parents=True, exist_ok=True)
        for leftover in root.glob(f".{final.name}.*"):
            if leftover.is_dir():
                shutil.rmtree(leftover, ignore_errors=True)
        temp.mkdir()
        entries = {}
        for name, (data, is_data) in files.items():
            (temp / name).write_bytes(data)
            entries[name] = {"size": len(data), "sha256": _sha256(data)}
            if is_data:
                entries[name]["data"] = True
        manifest = {"format": CACHE_FORMAT, "version": CACHE_VERSION, "game": game,
                    "built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "built_from": str(folder), "files": entries}
        (temp / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        check = CacheSource(game, required, folder=temp, data_files=data_files)
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


class Pictures:
    """What a renderer reads: the patcher's own art (its assets\\ files, by name) first, then the
    cache (or, when no cache could be made, a game folder itself)."""

    def __init__(self, game: int, base=None, problem: str = "", patcher: dict | None = None) -> None:
        self.game = game
        self.base = base
        self.patcher = {name.casefold(): Path(path) for name, path in (patcher or {}).items()}
        self.problem = problem
        self.copy = getattr(base, "copy", None)

    def read(self, name: str) -> bytes | None:
        path = self.patcher.get(name.casefold())
        if path is not None:
            try:
                return path.read_bytes()
            except OSError:
                return None
        return self.base.read(name) if self.base is not None else None


def is_game_folder(game: int, folder: Path, required, data_files=()) -> bool:
    """Whether `folder` holds every sheet in `required` under Images and every data file under Assets
    (read only)."""
    try:
        names = {p.name.casefold() for p in images_folder(folder).iterdir()}
        if not all(n.casefold() in names for n in required):
            return False
        if data_files:
            assets = {p.name.casefold() for p in (Path(folder) / "Assets").iterdir()}
            return all(n.casefold() in assets for n in data_files)
    except OSError:
        return False
    return True


def picture_source(game: int, folders, required, patcher: dict | None = None,
                   root: Path | None = None, data_files=()) -> Pictures:
    """The pictures for a game: the cache when it is whole; else built from the first of `folders`
    that has every file; else none, with one line saying how to give the Studio a game folder."""
    required, data_files = list(required), list(data_files)
    cache = CacheSource(game, required, root, data_files=data_files)
    if cache.ok:
        return Pictures(game, cache, patcher=patcher)
    reasons = []
    found = [Path(f) for f in dict.fromkeys(str(f) for f in folders if f)
             if is_game_folder(game, Path(f), required, data_files)]
    for folder in found:
        built, why = build_cache(game, folder, required, root, data_files)
        if built:
            cache = CacheSource(game, required, root, data_files=data_files)
            if cache.ok:
                return Pictures(game, cache, patcher=patcher)
            why = f"the new picture cache did not read back ({cache.problem})"
        reasons.append(why)
    if found:
        return Pictures(game, FolderSource(found[0], data_files), patcher=patcher)
    return Pictures(game, None, patcher=patcher, problem=(
        f"The pictures come from your own copy of Virtual Villagers - {GAME_FOLDERS[game]}, and none was found "
        "yet: click \"Find game...\" and pick its game folder (the one with the Images folder)."))
