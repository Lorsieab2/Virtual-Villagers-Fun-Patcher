"""The Family Tree Maker's family tree picture (src/vv_genealogy.py's village, drawn).

The owner (2026-10-07) showed a hand-made Secret City tree and asked for the same: one row per
generation, each villager with "the name, age in game units and years", "as many colors as needed
to distinguish the family lines", "pictures of the correct head values", and "twins and triplets
should be connected with a triangle".  Later the same day: the heads are "the same head sprite as
you use for the Origins Change Appearance menus"; "deceased villagers should not be faded (hard to
read), just put (deceased) in their entry"; and an expecting mother gets "another child with a
diamond portrait that says Upcoming child".

* Each villager is a frame -- square for a male, round for a female (the owner's example) -- with
  the head Change Appearance shows: the whole 40x65 cell of column 5 of the game's own head sheet
  in the game folder's Images, the row the head value, the young sheet at every age.
  Without the game folder the frame shows the initial instead.
* A baby on the way is a diamond, "Upcoming child", under its mother and the expected father.
* Each family -- a mother and father and their children -- has a colour of its own: the lines from
  the parents to the children, and the children's frames.  Founders' frames are grey.
* Children born together hang from one point of their family's line, which opens into a triangle.
* Villagers with no recorded parent or child sit apart, under "Unrelated Individuals", level with their
  generation.
* The player's marks and edits (the owner: "mark special villagers with a border (any color) with a
  matching key", "make all the fields editable in case there are errors or the player wants to
  type something in a portrait"): every entry's lines, the title and the generation labels may be
  replaced, and any villager may carry a mark of the player's own -- a label and a colour -- drawn
  as a second border, every mark listed in the Key.  They are kept in the save folder's
  Virtual Villagers Fun Patcher Data\\Genealogy, by villager (name, head and body), so a new tree
  keeps them.

The page is HTML with the tree in SVG; the picture (PNG or JPG) is drawn with Windows' own GDI+
(src/vv_gdiplus.py): nothing to install.
"""
from __future__ import annotations

import base64
import html
import json
import math
import re
import struct
import zlib
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import vv_genealogy as gen

NODE_W = 106
NODE_H = 156
TRANSPARENT = "transparent"             # a colour that shows nothing (the owner asked for it)
LINE_WIDTH = 2.2                        # a family line's weight unless the player says
GAP_X = 22
LEFT = 300                      # the generation labels' column
TOP = 150
OTHER_GAP = 110                 # between the tree and the "Unrelated Individuals" column

# The head is the one the Origins Change Appearance menus show: the whole 40x65 cell of column 5
# (HEAD_FRAME in scripts/build_vv1_appearance_bitmaps.py, build_vv2_appearance_sheets.py and
# build_vv3_appearance_bmps.py; VV_HEAD_FRAME_COL in native/vv4_origins_icons), always from the
# young sheet, never the older-looking one.
HEAD_W, HEAD_H = 40, 65
HEAD_FRAME = 5
HEAD_SCALE = 4 / 3                # tkinter scales by whole ratios: zoom 4, subsample 3
LINE_H = 13
# The face fills the top 46 rows of a head cell (the hair reaches at most 43 rows down in every
# game's column 5, A New Home's long hair apart): centring is by the face, the cell drawn whole.
FACE_H = 46
MARK_GAP = 6                    # the player's mark: a second border this far outside the frame

# Each game's head sheets: (male, female).  Only the young ones, at every age (the owner: "I don't
# want any 'Old' villager heads to be on the tree. For any game").
SHEETS = {
    1: ("male_heads.png", "female_heads.png"),
    2: ("male_heads.png", "female_heads.png"),
    3: ("male_heads.png", "female_heads.png"),
    4: ("male_heads00.png", "female_heads00.png"),
    5: ("male_heads00.png", "female_heads00.png"),
}

BACKGROUND = "#e8f0e0"
BACKGROUNDS = Path(__file__).resolve().parents[1] / "assets" / "genealogy" / "backgrounds"
# The owner: "Generations should not necessarily be on the exact same row.  Feel free to vary
# their position vertically/horizontally like my example for legibility.  (add a toggle: One
# straight row vs dynamic positioning)".
POSITIONING = {"dynamic": "Families under their parents", "rows": "One straight row per generation"}
NUMBERINGS = {"roman": "Roman numerals (I, II, III)", "numbers": "Numbers (1, 2, 3)"}
# The parts of a generation's label the player may delete one by one (the owner: ""Founders" "I."
# "5 Total: ..." "0 living" etc.").
LABEL_PARTS = {"number": "the number", "name": "the name", "total": "the totals line", "living": "the living line",
               "upcoming": "the upcoming line"}
SUBGAP = 46                     # between two rows of one generation: room for a line to step sideways
SUB_COST = 8                    # how many places a family may move along rather than step down a row
MAX_SUBROWS = 4
FITS = {"contain": "Whole picture (nothing cut off)", "cover": "Fill the page (cuts off the edges)",
        "stretch": "Stretch to the page", "tile": "Repeat (tile)"}
# The classic rainbow ombre the owner showed: every bright hue, red at both ends, drawn across the page
# (left to right) or down it (top to bottom).
RAINBOW = ["#ff0000", "#ff00ff", "#6000ff", "#0060ff", "#00ffff", "#00ff00", "#ffff00", "#ff8000", "#ff0000"]
RAINBOWS = {"rainbow-across": "across", "rainbow-down": "down"}
# Ready-made backgrounds: (name, colour, gradient's lower colour, a RAINBOWS key, or "", picture or "").  A picture
# is one of the games' own, never shipped with the patcher: "game:" is in this game's Images folder,
# "vvN:" in game N's (found through the game folders the patcher knows), so a preset is offered only
# when its picture is there.
PRESETS = [
    ("Leaf green (the patcher's own)", BACKGROUND, "", ""),
    ("Parchment", "#f3e7c9", "#e2cfa0", ""),
    ("Sea and sand", "#bfe3ef", "#efe2bb", ""),
    ("Sunset", "#ffd9a8", "#f2a7a0", ""),
    ("Moonlit night", "#2b3550", "#141a2b", ""),
    ("Jungle", "#d7ead0", "#7fa86f", ""),
    ("Lagoon", "#d4f1ee", "#5fa8a6", ""),
    ("Volcano", "#f6d2a2", "#7a3b2e", ""),
    ("White", "#ffffff", "", ""),
    ("Rainbow (across)", "#ffffff", "rainbow-across", ""),
    ("Rainbow (top to bottom)", "#ffffff", "rainbow-down", ""),
    # The owner's own pictures, shipped with the patcher (assets/genealogy/backgrounds), and only those
    # (the owner: "I want these and only these backgrounds as defaults: along with your plain
    # gradient ones").
    ("Sunset over the sea", "#d4f1ee", "", "asset:sunset-over-the-sea.png"),
    ("Palms at sunset", "#ffd9a8", "", "asset:palms-at-sunset.png"),
    ("The island in the sea", "#bfe9ec", "", "asset:island-in-the-sea.png"),
    ("The city in the mist", "#e8eef0", "", "asset:city-in-the-mist.png"),
    ("The blue island", "#1e6fb5", "", "asset:blue-island.png"),
    ("Mountains and sea", "#e6eef2", "", "asset:mountains-and-sea.png"),
    ("The tree on the rocks", "#e6eef2", "", "asset:tree-on-the-rocks.png"),
    ("Parchment in bamboo", "#efdcb4", "", "asset:parchment-in-bamboo.png"),
    ("The mausoleum", "#16302f", "", "asset:mausoleum.png"),
    ("The green tree", "#cfe6d0", "", "asset:green-tree.png"),
    ("Starry night", "#000000", "", "asset:starry-night.png"),
]
# How a ready-made picture fits the page when picked (any other picture: stretched to the page).  The
# starry night is small and repeats without a seam, so it is tiled rather than blown up and blurred.
PRESET_FITS = {"asset:starry-night.png": "tile"}
INK = "#1d2a1d"
LIGHT_INK = "#f4f1e6"
GREY = "#8a8f88"


# The owner: "distinct colors for every single individual unrelated person, siblings that share
# both parents to have the same color.  Each pairing has a single-color connector.  Each set of
# full siblings has a single-color connector that's different from their parents", "I literally
# use all colors in my example - shades of gray, white, red, tan, orange, pink... everything."
# So the colours are every colour of a fine grid -- greys, white, tans and pastels included -- taken
# one at a time, each the one that looks least like every colour already taken and like the
# background (CIE Lab distance), so each is as distinct as any can be and none fades into the
# background.
_LEVELS = (0, 51, 102, 153, 204, 255)
_GRID = ["#%02x%02x%02x" % (r, g, b) for r in _LEVELS for g in _LEVELS for b in _LEVELS] + [
    "#d2b48c", "#c0c0c0", "#808080", "#404040", "#f5deb3", "#ffc0cb", "#ffa500", "#a0522d"]
_SEEN: dict = {}


def _lab(colour: str) -> tuple[float, float, float]:
    if colour == TRANSPARENT:                   # colours are kept apart from the page underneath
        colour = BACKGROUND
    def linear(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(int(colour[i:i + 2], 16)) for i in (1, 3, 5))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def distinct_colours(n: int, background: str = BACKGROUND, avoid: tuple = ()) -> list[str]:
    """n colours, each as unlike the others, the background and the colours to `avoid` as the
    grid allows (they come round again only past the grid's last)."""
    key = (n, background, avoid)
    if key not in _SEEN:
        points = {c: _lab(c) for c in _GRID}
        kept = [_lab(background)] + [_lab(c) for c in avoid]
        nearest = {c: min(math.dist(lab, k) for k in kept) for c, lab in points.items()}
        out: list[str] = []
        while len(out) < n:
            if not nearest:
                out += out[:n - len(out)]
                break
            pick = max(nearest, key=lambda c: (nearest[c], c))
            out.append(pick)
            del nearest[pick]
            for c in nearest:
                nearest[c] = min(nearest[c], math.dist(points[c], points[pick]))
        _SEEN[key] = out
    return list(_SEEN[key])


@dataclass
class Family:
    id: int
    father: int | None
    mother: int | None
    children: list[int]
    colour: str = GREY                  # the full siblings': their connector and their frames
    lane_y: float = 0.0                 # the children's line, between the rows
    couple_y: float = 0.0
    drops: dict = field(default_factory=dict)   # parent -> where the family's line leaves them


@dataclass
class Edits:
    """The player's marks and edits for one village's tree.  Blank means the patcher's own."""
    title: str = ""
    subtitle: str = ""
    centre_heads: bool = True           # the head and its lines in the middle of the frame
    diagonal_lines: bool = False        # a dragged line piece may move any way (else only across itself)
    show_units: bool = True             # "<age> game units" in the portraits
    show_years: bool = True             # "<years> years old" in the portraits
    number_names: bool = False          # villagers who share a name numbered: "Soda I", "Soda II"...
    number_order: str = "oldest"        # vv_genealogy.NUMBER_ORDERS: who is "I"
    sort: str = "appearance"            # vv_genealogy.SORTS
    positioning: str = "dynamic"        # POSITIONING
    numbering: str = "roman"            # NUMBERINGS: the generations' numbers
    background: str = TRANSPARENT       # "#rrggbb" or TRANSPARENT (the owner's default); blank the patcher's own
    background2: str = ""               # a gradient's lower colour ("" none)
    rainbow: str = ""                   # a RAINBOWS key instead of that gradient ("" none)
    background_image: str = ""          # a picture file, or "game:<name>" in the game's Images
    background_fit: str = "stretch"     # FITS (the owner's default: "stretch to the page")
    background_opacity: int = 60        # 0-100: how strongly the picture shows over the colour
    ink: str = ""                       # the text's colour
    font: str = ""                      # the font for every word on the tree ("" the patcher's own)
    styles: dict[str, dict] = field(default_factory=dict)             # ROLES key -> its own style
    family_colours: dict[str, str] = field(default_factory=dict)      # family key -> its pairing's colour
    person_colours: dict[str, str] = field(default_factory=dict)      # entry key -> a parentless villager's
    # Where the player dragged the words around the tree (the owner: "allow the option to move
    # anything by dragging it"): MOVABLE name -> [right, down].  A villager's own is in entries.
    moved: dict[str, list] = field(default_factory=dict)
    # The player's order of a generation (the owner: "allow customizability/reordering of
    # villagers within generations"): "3" -> entry keys, left to right.  A villager's own
    # generation, when the player puts them in another, is in entries.
    orders: dict[str, list] = field(default_factory=dict)
    portrait_fill: str = "#ffffff"      # inside every portrait
    shapes: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SHAPES))     # GROUPS -> shape
    borders: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_BORDERS))   # GROUPS -> border
    plate_colour: str = ""              # the boxes behind words on a picture ("" the background's colour)
    opacity: dict[str, int] = field(default_factory=dict)              # OPACITY -> percent (unset: its default)
    sizes: dict[str, list] = field(default_factory=dict)               # GROUPS -> [width, height] of the frame
    line_width: float = LINE_WIDTH      # every family line's weight
    line_dash: str = ""                 # LINE_TYPES: every family line's type
    family_lines: dict[str, dict] = field(default_factory=dict)        # family key -> {"width", "dash"}
    mark_style: str = "border"          # MARK_STYLES
    mark_glow: float = 14.0             # how far a glow reaches
    mark_opacity: int = 100             # percent
    label_line_width: float = 2.0       # the line beside each generation's label
    label_line_reach: float = 0.0       # how far past the generation's portraits it reaches, each end
    # What the player deleted from the tree (the owner: "omit anything I like"): "word:<MOVABLE
    # name>" and "line:<family key>|<piece>".  A villager deleted is "hidden" in their entry.
    pages: list[int] = field(default_factory=list)                     # the generations that start a new page
    hidden: list[str] = field(default_factory=list)
    # Pieces of line the player dragged (the owner: "move individual lines and still keep the
    # connections to portraits"): "<family key>|<piece>" -> how far it was dragged.
    line_moves: dict[str, list | float] = field(default_factory=dict)   # piece -> [right, down]
    generations: dict[str, list[str]] = field(default_factory=dict)   # "2" -> the label's lines
    words: dict[str, str] = field(default_factory=dict)                # WORDS -> the player's own words
    marks: dict[str, str] = field(default_factory=dict)               # label -> "#rrggbb", in order
    entries: dict[str, dict] = field(default_factory=dict)            # entry key -> {"lines", "mark"}
    # Stickers (the owner: "any image file on the computer where people can drag and place them
    # like a scrapbook", "resize, rotate, transform"): pictures on top of the tree, bottom one first.
    stickers: list[dict] = field(default_factory=list)

    @staticmethod
    def path(folder: Path, game: int, slot: int) -> Path:
        import vv_log_tools as tools
        return (Path(folder) / tools.DATA / "Genealogy"
                / f"Virtual Villagers {game} Genealogy Edits - Save {slot}.json")

    @classmethod
    def load(cls, path: Path) -> "Edits":
        """The saved edits; none when there is no file.  A file that is not this format raises
        ValueError (it is never overwritten unasked)."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{Path(path).name} could not be read: {exc}") from exc
        if not isinstance(data, dict) or data.get("format") != 1:
            raise ValueError(f"{Path(path).name} is not a Family Tree Maker edits file.")
        return cls.from_data(data)

    @classmethod
    def from_data(cls, data: dict) -> "Edits":
        """The edits from their saved form (every value checked); ValueError when the form is damaged."""
        try:
            return cls._from_data(data)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(f"the saved edits are damaged ({exc})") from exc

    @classmethod
    def _from_data(cls, data: dict) -> "Edits":
        out = cls(str(data.get("title", "")), str(data.get("subtitle", "")),
                  data.get("centre_heads", True) is not False)
        out.diagonal_lines = data.get("diagonal_lines") is True
        out.show_units = data.get("show_units", True) is not False
        out.show_years = data.get("show_years", True) is not False
        out.number_names = data.get("number_names") is True
        if data.get("number_order") in gen.NUMBER_ORDERS:
            out.number_order = data["number_order"]
        if data.get("sort") in gen.SORTS:
            out.sort = data["sort"]
        if data.get("positioning") in POSITIONING:
            out.positioning = data["positioning"]
        if data.get("numbering") in NUMBERINGS:
            out.numbering = data["numbering"]
        for attr in ("background", "background2", "ink"):
            if is_colour(data.get(attr)):
                setattr(out, attr, data[attr])
        if data.get("rainbow") in RAINBOWS:
            out.rainbow = data["rainbow"]
        out.background_image = str(data.get("background_image", ""))
        if data.get("background_fit") in FITS:
            out.background_fit = data["background_fit"]
        if isinstance(data.get("background_opacity"), int):
            out.background_opacity = max(0, min(100, data["background_opacity"]))
        for key, colour in dict(data.get("family_colours", {})).items():
            if is_colour(colour):
                out.family_colours[str(key)] = colour
        for key, colour in dict(data.get("person_colours", {})).items():
            if is_colour(colour):
                out.person_colours[str(key)] = colour
        for key, lines in dict(data.get("generations", {})).items():
            out.generations[str(key)] = [str(line) for line in lines]
        for key, text in dict(data.get("words", {})).items():
            if key in WORDS and isinstance(text, str):
                out.words[key] = text
        for label, colour in dict(data.get("marks", {})).items():
            if is_colour(colour):
                out.marks[str(label)] = str(colour)
        for key, entry in dict(data.get("entries", {})).items():
            if not isinstance(entry, dict):     # damaged: that villager's edits are passed over
                continue
            item = {}
            if isinstance(entry.get("lines"), list):
                item["lines"] = [str(line) for line in entry["lines"]]
            if entry.get("mark"):
                item["mark"] = str(entry["mark"])
            if entry.get("hidden") is True:
                item["hidden"] = True
            if entry.get("shape") in PORTRAIT_SHAPES:
                item["shape"] = entry["shape"]
            if entry.get("border") in BORDERS:
                item["border"] = entry["border"]
            if isinstance(entry.get("generation"), int) and 1 <= entry["generation"] <= 99:
                item["generation"] = entry["generation"]
            for axis in ("dx", "dy"):
                shift = _number(entry.get(axis), -STICKER_MAX, STICKER_MAX, 0.0)
                if shift:
                    item[axis] = shift
            for axis in ("w", "h"):
                if axis in entry:
                    item[axis] = _number(entry[axis], FRAME_MIN, FRAME_MAX, FRAME_MIN)
            angle = _number(entry.get("angle"), 0.0, 360.0, 0.0) % 360
            if angle:
                item["angle"] = angle
            if item:
                out.entries[str(key)] = item
        for piece, shift in dict(data.get("line_moves", {})).items():
            if isinstance(shift, list) and len(shift) == 2:
                shift = [_number(v, -STICKER_MAX, STICKER_MAX, 0.0) for v in shift]
            else:                               # saved before lines moved both ways: across itself
                shift = _number(shift, -STICKER_MAX, STICKER_MAX, 0.0)
            if shift:
                out.line_moves[str(piece)] = shift
        for group, size in dict(data.get("sizes", {})).items():
            if group in GROUPS and isinstance(size, list) and len(size) == 2:
                out.sizes[group] = [_number(v, FRAME_MIN, FRAME_MAX, NODE_H) for v in size]
        out.line_width = _number(data.get("line_width"), *LINE_WIDTHS, LINE_WIDTH)
        if data.get("line_dash") in LINE_TYPES:
            out.line_dash = data["line_dash"]
        for key, style in dict(data.get("family_lines", {})).items():
            item = {}
            if isinstance(style, dict) and "width" in style:
                item["width"] = _number(style["width"], *LINE_WIDTHS, LINE_WIDTH)
            if isinstance(style, dict) and style.get("dash") in LINE_TYPES:
                item["dash"] = style["dash"]
            if item:
                out.family_lines[str(key)] = item
        if data.get("mark_style") in MARK_STYLES:
            out.mark_style = data["mark_style"]
        out.mark_glow = _number(data.get("mark_glow"), 2.0, 60.0, 14.0)
        out.mark_opacity = int(_number(data.get("mark_opacity"), 0, 100, 100))
        out.label_line_width = _number(data.get("label_line_width"), *LINE_WIDTHS, 2.0)
        out.label_line_reach = _number(data.get("label_line_reach"), 0.0, 1000.0, 0.0)
        for part, value in dict(data.get("opacity", {})).items():
            if part in OPACITY:
                out.opacity[part] = int(_number(value, 0, 100, OPACITY[part][1]))
        for attr in ("portrait_fill", "plate_colour"):
            if is_colour(data.get(attr)):
                setattr(out, attr, data[attr])
        for attr, choices in (("shapes", PORTRAIT_SHAPES), ("borders", BORDERS)):
            for group, value in dict(data.get(attr, {})).items():
                if group in GROUPS and value in choices:
                    getattr(out, attr)[group] = value
        if isinstance(data.get("pages"), list):
            out.pages = sorted({int(g) for g in data["pages"] if isinstance(g, int) and 2 <= g <= 99})
        if isinstance(data.get("hidden"), list):
            out.hidden = [str(h) for h in data["hidden"]]
        for g, keys in dict(data.get("orders", {})).items():
            if isinstance(keys, list):
                out.orders[str(g)] = [str(k) for k in keys]
        for name, shift in dict(data.get("moved", {})).items():
            if isinstance(shift, list) and len(shift) == 2:
                out.moved[str(name)] = [_number(shift[0], -STICKER_MAX, STICKER_MAX, 0.0),
                                        _number(shift[1], -STICKER_MAX, STICKER_MAX, 0.0)]
        if isinstance(data.get("font"), str):
            out.font = data["font"]
        for role, style in dict(data.get("styles", {})).items():
            if role in ROLES and isinstance(style, dict):
                out.styles[role] = clean_style(style)
        for raw in data.get("stickers", []) if isinstance(data.get("stickers"), list) else []:
            sticker = clean_sticker(raw)
            if sticker is not None:
                out.stickers.append(sticker)
        return out

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.to_data(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)

    def to_data(self) -> dict:
        return {"format": 1, "title": self.title, "subtitle": self.subtitle,
                "centre_heads": self.centre_heads, "diagonal_lines": self.diagonal_lines,
                "show_units": self.show_units, "show_years": self.show_years, "number_names": self.number_names,
                "number_order": self.number_order,
                "sort": self.sort, "positioning": self.positioning,
                "numbering": self.numbering,
                "background": self.background, "background2": self.background2, "rainbow": self.rainbow,
                "background_image": self.background_image, "background_fit": self.background_fit,
                "background_opacity": self.background_opacity,
                "ink": self.ink, "family_colours": self.family_colours,
                "person_colours": self.person_colours, "moved": self.moved, "orders": self.orders,
                "portrait_fill": self.portrait_fill, "plate_colour": self.plate_colour, "hidden": self.hidden,
                "pages": self.pages,
                "shapes": self.shapes, "borders": self.borders, "opacity": self.opacity,
                "sizes": self.sizes, "line_width": self.line_width, "line_dash": self.line_dash,
                "family_lines": self.family_lines, "mark_style": self.mark_style, "mark_glow": self.mark_glow,
                "mark_opacity": self.mark_opacity, "label_line_width": self.label_line_width,
                "label_line_reach": self.label_line_reach,
                "line_moves": self.line_moves,
                "generations": self.generations, "words": self.words, "marks": self.marks, "entries": self.entries,
                "font": self.font, "styles": self.styles, "stickers": self.stickers}




def is_colour(value) -> bool:
    return isinstance(value, str) and (value == TRANSPARENT or re.fullmatch(r"#[0-9a-fA-F]{6}", value) is not None)


STICKER_MIN = 6.0                       # the smallest a sticker's side may be
STICKER_MAX = 20000.0
PICTURE_TYPES = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
# Each game's logo, in its own Images folder (never shipped with the patcher).
LOGOS = [(f"{title} logo", f"vv{n}:logo1.png") for n, title in
         ((1, "A New Home"), (2, "The Lost Children"), (3, "The Secret City"), (4, "The Tree of Life"),
          (5, "New Believers"))]


def _number(value, low: float, high: float, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return default
    return max(low, min(high, float(value)))


# The words on the tree a player can give their own font, size, style and colour.
ROLES = {
    "title": "Title",
    "subtitle": "Subtitle",
    "key": "Key (the marks)",
    "labels": "Generation labels",
    "names": "Names in the portraits",
    "portraits": "Other words in the portraits",
    "others": "Unrelated Individuals heading",
    "footer": "Footer",
}
ALIGNS = {"left": "Left", "centre": "Centre", "right": "Right"}
# A portrait's shape and border (the owner's lists).
PORTRAIT_SHAPES = {"rectangle": "Rectangle", "rounded_rect": "Rounded rectangle", "rect": "Square",
                   "rounded": "Rounded square", "circle": "Circle", "ellipse": "Oval",
                   "heart": "Heart", "triangle": "Triangle", "diamond": "Diamond", "cross": "Cross", "x": "X",
                   "plus": "Plus", "star": "Star", "hexagon": "Hexagon", "octagon": "Octagon"}
BORDERS = {"thin": "Thin line", "thick": "Thick line", "extra": "Extra thick line", "dotted": "Dotted",
           "dashed": "Dashed",
           "dashdot": "Dotted and dashed"}
BORDER_WIDTHS = {"thin": 1.5, "thick": 3.0, "extra": 6.0, "dotted": 2.5, "dashed": 2.5, "dashdot": 2.5}
# How see-through each part of the tree is, in percent, until the player says (pictures and text
# boxes have their own).
OPACITY = {"words": ("Words", 100), "plates": ("Boxes behind words", 80), "portraits": ("Portraits", 100),
           "lines": ("Family lines", 100)}
# The family lines' look (the owner: "I want to change line weights, types, absolutely everything in
# batch!"): every line's, or one family's.
LINE_TYPES = {"": "Solid", "dotted": "Dotted", "dashed": "Dashed", "dashdot": "Dotted and dashed"}
LINE_WIDTHS = (0.25, 20.0)
# How a special mark is drawn (the owner: "can marks be a "glow" around the portrait instead?").
MARK_STYLES = {"border": "A border round the portrait", "glow": "A glow round the portrait"}
GLOW_RINGS = 16
# Who gets which until the player says (males, females, babies on the way).
GROUPS = {"Male": "Males", "Female": "Females", "Upcoming": "Babies on the way"}
DEFAULT_SHAPES = {"Male": "rect", "Female": "circle", "Upcoming": "diamond"}       # the owner's
DEFAULT_BORDERS = {"Male": "thick", "Female": "thick", "Upcoming": "thick"}     # the owner's: all alike
SHAPES = {"rect": "Rectangle", "ellipse": "Oval"}           # a text box's own shape
VALIGNS = {"top": "Top", "middle": "Middle", "bottom": "Bottom"}


# Superscript and subscript: the words this much smaller, raised or lowered by this much of their size.
SCRIPTS = {"super": (0.65, -0.35), "sub": (0.65, 0.2)}


def clean_style(raw: dict) -> dict:
    """A role's style, every value in range: only what the player set."""
    out: dict = {}
    if isinstance(raw.get("font"), str) and raw["font"]:
        out["font"] = raw["font"]
    if raw.get("scale") is not None:
        out["scale"] = int(_number(raw.get("scale"), 25, 400, 100))
    for flag in ("bold", "italic", "underline", "strike"):
        if isinstance(raw.get(flag), bool):
            out[flag] = raw[flag]
    if raw.get("script") in SCRIPTS:
        out["script"] = raw["script"]
    if is_colour(raw.get("colour")):
        out["colour"] = raw["colour"]
    return out


def clean_sticker(raw) -> dict | None:
    """A sticker (a picture, or a text box) as the edits file keeps it, every value in range;
    None when it is neither."""
    if not isinstance(raw, dict):
        return None
    kind = "text" if raw.get("kind") == "text" else "picture"
    if kind == "picture" and (not isinstance(raw.get("picture"), str) or not raw["picture"]):
        return None
    out = {"kind": kind}
    if kind == "text":
        out.update({
            "text": str(raw.get("text", "")),
            "font": str(raw.get("font", "")),
            "size": _number(raw.get("size"), 4, 400, 24.0),
            "bold": raw.get("bold") is True,
            "italic": raw.get("italic") is True,
            "underline": raw.get("underline") is True,
            "strike": raw.get("strike") is True,
            "colour": raw["colour"] if is_colour(raw.get("colour")) else INK,
            "align": raw["align"] if raw.get("align") in ALIGNS else "centre",
            "valign": raw["valign"] if raw.get("valign") in VALIGNS else "middle",
            "fill": raw["fill"] if is_colour(raw.get("fill")) else "",
            "fill_opacity": _number(raw.get("fill_opacity"), 0, 100, 100.0),
            "border": raw["border"] if is_colour(raw.get("border")) else "",
            "border_width": _number(raw.get("border_width"), 0, 40, 2.0),
            "shape": raw["shape"] if raw.get("shape") in SHAPES else "rect",
        })
    else:
        out["picture"] = raw["picture"]
    return {
        **out,
        "cx": _number(raw.get("cx"), -STICKER_MAX, STICKER_MAX, 200.0),
        "cy": _number(raw.get("cy"), -STICKER_MAX, STICKER_MAX, 200.0),
        "w": _number(raw.get("w"), STICKER_MIN, STICKER_MAX, 200.0),
        "h": _number(raw.get("h"), STICKER_MIN, STICKER_MAX, 200.0),
        "angle": _number(raw.get("angle"), -1e6, 1e6, 0.0) % 360,
        "flip_h": raw.get("flip_h") is True,
        "flip_v": raw.get("flip_v") is True,
        "opacity": _number(raw.get("opacity"), 0, 100, 100.0),
    }


def turn(x: float, y: float, angle: float) -> tuple[float, float]:
    """(x, y) turned clockwise (on the screen, y down) by `angle` degrees about the origin."""
    a = math.radians(angle)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def is_dark(colour: str) -> bool:
    """Whether dark words would be hard to read on this colour (nothing shows through transparent)."""
    if colour == TRANSPARENT:
        return False
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b < 110


def parse_colour(text: str) -> str | None:
    """A colour the player typed: "#d4a017", "d4a017", red, green and blue 0-255 ("212, 160, 23"
    or "rgb(212, 160, 23)"), or "transparent" (or "none").  None when it is neither."""
    text = text.strip()
    if text.lower() in ("transparent", "none", "clear"):
        return TRANSPARENT
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", text)
    if m:
        return "#" + m.group(1).lower()
    m = re.fullmatch(r"(?:rgb\s*\()?\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*\)?", text, re.I)
    if m and all(int(v) <= 255 for v in m.groups()):
        return "#%02x%02x%02x" % tuple(int(v) for v in m.groups())
    return None


def family_key(village: gen.Village, fam: "Family") -> str:
    """Which family a colour is for: its father's and mother's keys."""
    def one(pid):
        return entry_key(village, village.people[pid]) if pid is not None else "-"
    return f"{one(fam.father)}||{one(fam.mother)}"


# Where Save to Save Folder keeps the editable tree files, in the save folder.
TREES = "Virtual Villagers Fun Patcher Family Trees"
TREE_SUFFIX = ".vvtree"
TREE_FORMAT = "Virtual Villagers Fun Patcher family tree"


def renamed_keys(text: str, renames: dict[tuple, str]) -> str:
    """Saved edits (an edits file or a .vvtree, as text) with each renamed villager's key --
    "<name>|<head>|<body>", in an entry, a family, an order, a line piece -- under their new name."""
    for (name, head, body), new in renames.items():
        key = json.dumps(new)[1:-1] + f"|{head}|{body}"
        text = re.sub(rf'(?<=["|: ]){re.escape(json.dumps(name)[1:-1])}\|{head}\|{body}(?=["| ])',
                      lambda _found, key=key: key, text)
    return text


def entry_key(village: gen.Village, p: gen.Person) -> str:
    """Who an edit is for: the villager's name, head and body; a baby on the way by its mother."""
    if p.upcoming:
        m = village.people[p.mother]
        return f"upcoming|{m.name}|{m.head}|{m.body}|{-(p.body or 0)}"
    return f"{p.name}|{p.head}|{p.body}"


@dataclass
class Layout:
    village: gen.Village
    rows: dict[int, list[int]]                    # generation -> person ids, left to right
    x: dict[int, float]
    y: dict[int, float]
    families: list[Family]
    others: list[int]
    others_left: float
    width: float
    height: float
    tops: dict[int, float] = field(default_factory=dict)         # generation -> its row's top
    bands: dict[int, float] = field(default_factory=dict)        # generation -> its rows' height
    birth_colour: dict[int, str] = field(default_factory=dict)
    edits: Edits = field(default_factory=Edits)
    page: int = 0                       # which page of the tree this is (page_spans)
    names: dict[int, str] = field(default_factory=dict)          # Number Duplicate Names: id -> "Soda II"
    pages: int = 1
    _spans: list = field(default_factory=list, repr=False)

    @property
    def background(self) -> str:
        return self.edits.background or BACKGROUND

    @property
    def ink(self) -> str:
        """The words on the background: the player's colour, else dark on a light background and
        light on a dark one."""
        return self.edits.ink or (LIGHT_INK if is_dark(self.background) else INK)

    @property
    def portrait_ink(self) -> str:
        """The words in the portraits, which are white: the player's colour, else dark."""
        return self.edits.ink or INK

    def entry(self, p: gen.Person) -> dict:
        return self.edits.entries.get(entry_key(self.village, p), {})

    def shape(self, p: gen.Person) -> str:
        return shape_of(self.edits, self.village, p)

    def border(self, p: gen.Person) -> str:
        return self.entry(p).get("border") or self.edits.borders[group_of(p)]

    def frame(self, q: int) -> tuple[float, float, float, float, float]:
        """q's portrait frame (left, top, width, height, angle): its shape at the shape's own
        proportions, as tall as a portrait, unless the player resized it; centred on the portrait;
        turned `angle` degrees about its middle."""
        p = self.village.people[q]
        w, h = frame_size(self.edits, self.village, p)
        return self.x[q] + NODE_W / 2 - w / 2, self.y[q] + NODE_H / 2 - h / 2, w, h, self.entry(p).get("angle", 0.0)

    def spans(self) -> list[tuple[float, float, float]]:
        """Every portrait's frame across (left, right) and its top: what a line keeps clear of
        (worked out once: every route asks)."""
        if not self._spans:
            for q in self.x:
                xs = [px for px, _py in self.frame_points(q)]
                self._spans.append((min(xs), max(xs), self.y[q]))
        return self._spans

    def frame_points(self, q: int) -> list[tuple[float, float]]:
        kind = self.shape(self.village.people[q])
        x, y, w, h, angle = self.frame(q)
        return shape_points(kind, x, y, w, h, corner_radius(kind), angle)

    def mark(self, p: gen.Person) -> str | None:
        """The colour of the player's mark on this villager, if any."""
        return self.edits.marks.get(self.entry(p).get("mark", ""))


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def arrange(village: gen.Village, edits: Edits) -> None:
    """Each villager's generation and number as the tree shows them: the records' generation
    unless the player put them in another; numbered generation by generation in the tree's sort,
    or in the player's own order of a generation, left to right.  A villager deleted from the
    tree has no number, so the others' run on without a gap."""
    for pid, p in village.people.items():
        own = edits.entries.get(entry_key(village, p), {}).get("generation")
        p.generation = own or village.base_generation.get(pid, p.generation)
    gen.number_people(village, edits.sort)
    gone = {pid for pid, p in village.people.items() if edits.entries.get(entry_key(village, p), {}).get("hidden")}
    if not edits.orders and not gone:
        return
    for pid in gone:
        village.people[pid].number = None
    n = 0
    for g in sorted({p.generation for p in village.known()}):
        row = sorted((p for p in village.known() if p.generation == g and p.id not in gone), key=lambda p: p.number)
        order = {key: i for i, key in enumerate(edits.orders.get(str(g), []))}
        row.sort(key=lambda p: (order.get(entry_key(village, p), len(order)), p.number))
        for p in row:
            n += 1
            p.number = n


def _place(p: gen.Person) -> tuple:
    """A row's order is its numbers' (vv_genealogy.number_people); babies on the way last."""
    return (p.upcoming, p.number or 0, p.order_key())


def group_of(p: gen.Person) -> str:
    """GROUPS: a baby on the way, a female or a male."""
    return "Upcoming" if p.upcoming else ("Female" if p.sex == "Female" else "Male")


def shape_of(edits: Edits, village: gen.Village, p: gen.Person) -> str:
    """The villager's portrait shape: their own, else their group's."""
    return edits.entries.get(entry_key(village, p), {}).get("shape") or edits.shapes[group_of(p)]


def frame_size(edits: Edits, village: gen.Village, p: gen.Person, own: bool = True) -> tuple[float, float]:
    """A portrait frame's width and height: the villager's own (`own`), else their group's default
    size, else their shape's own proportions, a portrait tall."""
    gw, gh = edits.sizes.get(group_of(p)) or (natural_width(shape_of(edits, village, p)), NODE_H)
    entry = edits.entries.get(entry_key(village, p), {}) if own else {}
    return entry.get("w", gw), entry.get("h", gh)


def page_spans(edits: Edits, village: gen.Village) -> list[tuple[int, int]]:
    """Each page's first and last generation (the generations as arrange gives them)."""
    gens = sorted({p.generation for p in village.people.values()}) or [1]
    starts = [gens[0]] + [g for g in edits.pages if gens[0] < g <= gens[-1]]
    return [(lo, starts[k + 1] - 1 if k + 1 < len(starts) else gens[-1]) for k, lo in enumerate(starts)]


def layout(village: gen.Village, edits: Edits | None = None, page: int = 0) -> Layout:
    people = village.people
    gone = {pid for pid, p in people.items()
            if (edits or Edits()).entries.get(entry_key(village, p), {}).get("hidden")}
    spans = page_spans(edits or Edits(), village)
    page = max(0, min(page, len(spans) - 1))
    first, last = spans[page]
    off = {pid for pid, p in people.items() if not first <= p.generation <= last}     # on another page
    fam_of: dict[tuple, Family] = {}
    for p in sorted(people.values(), key=lambda q: (q.generation, q.upcoming, -(q.age or 0), q.id)):
        if p.father is None and p.mother is None or p.id in gone:
            continue
        key = (p.father, p.mother)
        if key not in fam_of:
            fam_of[key] = Family(len(fam_of) + 1, p.father, p.mother, [])
        fam_of[key].children.append(p.id)
    families = list(fam_of.values())
    in_tree = set()
    for fam in families:
        in_tree.update(fam.children)
        in_tree.update(q for q in (fam.father, fam.mother) if q is not None)
    in_tree -= gone
    others = sorted((pid for pid in people if pid not in in_tree and pid not in gone and pid not in off),
                    key=lambda q: (people[q].generation, _place(people[q])))
    if off:                             # one page of a longer tree: its own generations, not joined to others
        in_tree -= off
        for fam in families:
            fam.children = [c for c in fam.children if c not in off]
        families = [f for f in families if f.children and any(q in in_tree for q in (f.father, f.mother))]
    # Each row in age order, oldest on the left (the owner: "oldest on the left, youngest on the
    # right"), numbered so (vv_genealogy.number_people).
    rows: dict[int, list[int]] = {}
    for pid in sorted(in_tree, key=lambda q: (people[q].generation, _place(people[q]))):
        rows.setdefault(people[pid].generation, []).append(pid)
    edits = edits or Edits()
    step = max([NODE_W] + [frame_size(edits, village, people[q], own=False)[0] for q in in_tree | set(others)]) + GAP_X
    x: dict[int, float] = {}
    sub: dict[int, int] = {q: 0 for q in in_tree}
    if edits.positioning == "dynamic" and rows:
        x, sub = _dynamic(people, rows, families, step)
        tree_right = max(x.values()) + NODE_W
    else:
        # Every row centred under the widest (the owner: "center everything ... both
        # horizontally and vertically").
        widest_row = max((len(row) for row in rows.values()), default=1)
        for row in rows.values():
            indent = (widest_row - len(row)) * step / 2
            for i, pid in enumerate(row):
                x[pid] = LEFT + indent + i * step
        tree_right = LEFT + widest_row * step - GAP_X
    others_left = tree_right + OTHER_GAP
    per_row: dict[int, int] = {}
    for pid in others:
        g = people[pid].generation
        x[pid] = others_left + per_row.get(g, 0) * step
        per_row[g] = per_row.get(g, 0) + 1
    widest = max(per_row.values(), default=0)
    width = (others_left + widest * step + 40) if others else tree_right + 60
    # Where the player dragged villagers.
    shifts = {q: edits.entries.get(entry_key(village, people[q]), {}) for q in x}
    for q, entry in shifts.items():
        x[q] = max(MARGIN, x[q] + entry.get("dx", 0.0))
    width = max([width] + [x[q] + NODE_W + 40 for q in x])
    # One lane per family (the owner: "spread the lines connecting parents to children a bit more
    # vertically"): every family whose children are in a row has a line of its own between that
    # row and the one above, shared only with families whose lines do not overlap it; the gap
    # between the rows is as tall as its lanes need.
    _drops(people, families, x)
    lanes = _lanes(people, families, x)
    _order_lanes(people, families, x, lanes)
    gens = sorted({people[q].generation for q in x})
    bands = {g: NODE_H + max((sub[q] for q in x if q in sub and people[q].generation == g), default=0)
             * (NODE_H + SUBGAP) for g in gens}
    tops: dict[int, float] = {}
    top = float(TOP)
    for k, g in enumerate(gens):
        if k:
            couples = lanes.couple_count.get(g, 0)
            top += (bands[gens[k - 1]] + LANE_TOP + couples * LANE + (BAND_GAP if couples else 0)
                    + max(1, lanes.count.get(g, 0)) * LANE + LANE_BOTTOM)
        tops[g] = top
    for fam in families:
        g = lanes.row.get(fam.id)
        if g is None:
            continue
        kids_band = lanes.count[g] * LANE
        fam.lane_y = tops[g] - LANE_BOTTOM - (lanes.count[g] - lanes.index[fam.id]) * LANE + LANE / 2
        if fam.id in lanes.couple_index:
            fam.couple_y = (tops[g] - LANE_BOTTOM - kids_band - BAND_GAP
                            - (lanes.couple_count[g] - lanes.couple_index[fam.id]) * LANE + LANE / 2)
    row_y = {pid: tops[people[pid].generation] + sub.get(pid, 0) * (NODE_H + SUBGAP) for pid in x}
    y = {pid: max(MARGIN, row_y[pid] + shifts[pid].get("dy", 0.0)) for pid in x}
    # A family's lines go with its children when they are dragged up or down (the owner: "so they're
    # neat and not overlapping when moved to a new position").
    for fam in families:
        kids = [c for c in fam.children if c in y]
        if kids and fam.lane_y:
            fam.lane_y += min(y[c] for c in kids) - min(row_y[c] for c in kids)
            parents = [q for q in (fam.father, fam.mother) if q in y]
            if fam.couple_y and parents:        # just under the parents, above the children's line
                lift = max(y[q] - row_y[q] for q in parents)
                fam.couple_y = min(fam.couple_y + lift, fam.lane_y - LANE)
    height = tops[gens[-1]] + bands[gens[-1]] + 190 if gens else TOP + NODE_H + 190
    height = max([height] + [y[q] + NODE_H + 190 for q in y])
    out = Layout(village, rows, x, y, families, others, others_left, width, height, tops=tops, bands=bands,
                 edits=edits, page=page, pages=len(spans),
                 names=gen.duplicate_names(village, edits.number_order) if edits.number_names else {})
    # One colour each: every villager with no recorded parents, every pairing, every set of full
    # brothers and sisters -- oldest first, so the most distinct go to the founders.
    e = out.edits
    alone = sorted((q for q in x if people[q].father is None and people[q].mother is None),
                   key=lambda q: (people[q].generation, _place(people[q])))
    pool = iter(distinct_colours(len(alone) + len(families), out.background))
    for q in alone:
        out.birth_colour[q] = e.person_colours.get(entry_key(village, people[q]), next(pool))
    for fam in families:
        fam.colour = e.family_colours.get(family_key(village, fam), next(pool))
        for c in fam.children:
            out.birth_colour[c] = fam.colour
    return out


def _dynamic(people: dict, rows: dict[int, list[int]], families: list[Family],
             step: float) -> tuple[dict[int, float], dict[int, int]]:
    """Each villager's x and row within their generation, families placed under their parents
    (the owner's example): the founders in a row; then, generation by generation, each set of
    brothers and sisters together, as near the middle of their parents as the room allows, and a
    villager without recorded parents beside their partner.  A family that would be pushed more
    than a few places from its parents steps down into another row of its generation instead."""
    x: dict[int, float] = {}
    sub: dict[int, int] = {}
    gens = sorted(rows)
    for i, q in enumerate(rows[gens[0]]):
        x[q], sub[q] = i * step, 0
    partners: dict[int, set] = {}
    for f in families:
        if f.father is not None and f.mother is not None:
            partners.setdefault(f.father, set()).add(f.mother)
            partners.setdefault(f.mother, set()).add(f.father)

    def centre(qs) -> float | None:
        points = [x[q] + NODE_W / 2 for q in qs if q is not None and q in x]
        return sum(points) / len(points) if points else None

    for g in gens[1:]:
        members = rows[g]
        groups: list[list] = []
        grouped: set[int] = set()
        for f in families:
            kids = [c for c in members if c in f.children]
            if kids:
                groups.append([centre((f.father, f.mother)), kids])
                grouped.update(kids)
        groups += [[None, [q]] for q in members if q not in grouped]
        taken: list[list[tuple[float, float]]] = []     # each row's places taken, (left, right)

        def nearest(row: list, ideal: float, span: float) -> float:
            """The free place in `row` for `span` nearest `ideal`."""
            def fits(left: float) -> bool:
                return all(left + span <= lo or hi <= left for lo, hi in row)
            places = [ideal] + [hi for _lo, hi in row] + [lo - span for lo, _hi in row]
            return min((p for p in places if fits(p)), key=lambda p: (abs(p - ideal), p))

        def put(group: list) -> None:
            wanted, kids = group
            span = len(kids) * step
            if wanted is None:                  # nobody to stand near: the end of the first row
                ends = [hi for row in taken[:1] for _lo, hi in row]
                wanted = max(ends, default=0.0) + span / 2
            ideal = wanted - (span - GAP_X) / 2
            best = None
            for k in range(min(len(taken) + 1, MAX_SUBROWS)):
                left = nearest(taken[k], ideal, span) if k < len(taken) else ideal
                cost = abs(left - ideal) / step + k * SUB_COST
                if best is None or cost < best[0]:
                    best = (cost, k, left)
            _cost, k, left = best
            if k == len(taken):
                taken.append([])
            taken[k].append((left, left + span))
            for i, q in enumerate(kids):
                x[q], sub[q] = left + i * step, k

        waiting = []
        for group in sorted((gr for gr in groups if gr[0] is not None), key=lambda gr: gr[0]):
            put(group)
        for group in groups:
            if group[0] is None:
                group[0] = centre(r for q in group[1] for r in partners.get(q, ()))
                if group[0] is None:
                    waiting.append(group)
                else:
                    put(group)
        for group in waiting:
            put(group)
    shift = LEFT - min(x.values())
    return {q: v + shift for q, v in x.items()}, sub


LANE = 14                       # between two families' lines
BAND_GAP = 10                   # between the couples' lines and the children's
LANE_TOP = 30                   # under the row above, before the first lane
LANE_BOTTOM = 46                # under the last lane: the children's drops and the triangles


@dataclass
class _Lanes:
    row: dict[int, int]         # family -> its children's generation
    index: dict[int, int]       # family -> its children's lane in that gap (0 the highest)
    count: dict[int, int]       # generation -> children's lanes in the gap above it
    couple_index: dict[int, int] = field(default_factory=dict)  # family -> its couple's lane
    couple_count: dict[int, int] = field(default_factory=dict)  # generation -> couples' lanes


def _pack(spans: list[tuple[float, float, int]], index: dict[int, int]) -> int:
    """Lines side by side share a lane when they do not overlap: each line's lane, and how many."""
    ends: list[float] = []
    for lo, hi, fid in sorted(spans):
        for k, end in enumerate(ends):
            if end + GAP_X < lo:
                ends[k] = hi
                index[fid] = k
                break
        else:
            ends.append(hi)
            index[fid] = len(ends) - 1
    return len(ends)


def _lanes(people: dict, families: list[Family], x: dict[int, float]) -> _Lanes:
    """The gap above each row: the couples' lines above, the children's lines below."""
    out = _Lanes({}, {}, {})
    kids_by_row: dict[int, list[tuple[float, float, int]]] = {}
    couples_by_row: dict[int, list[tuple[float, float, int]]] = {}
    for fam in families:
        kids = [c for c in fam.children if c in x]
        if not kids:
            continue
        g = min(people[c].generation for c in kids)
        out.row[fam.id] = g
        parents = [fam.drops[q] for q in (fam.father, fam.mother) if q is not None and q in x]
        xs = _hangs(people, fam, x)
        if len(parents) == 2:
            couples_by_row.setdefault(g, []).append((min(parents), max(parents), fam.id))
            xs.append(sum(parents) / 2)
        else:
            xs += parents
        kids_by_row.setdefault(g, []).append((min(xs), max(xs), fam.id))
    for g, spans in kids_by_row.items():
        out.count[g] = _pack(spans, out.index)
    # Every couple has a level of its own: couples' lines are often one colour, and two side by
    # side on one level would read as one line.
    for g, spans in couples_by_row.items():
        for k, (_lo, _hi, fid) in enumerate(sorted(spans)):
            out.couple_index[fid] = k
        out.couple_count[g] = len(spans)
    return out


def _drops(people: dict, families: list[Family], x: dict[int, float]) -> None:
    """Where each family's line leaves each parent: a parent of several families (one father,
    many mothers) gets one point each along the bottom of their frame, in the order of the
    families' children, so no two families' lines lie on top of each other."""
    by_parent: dict[int, list[Family]] = {}
    for fam in families:
        if not any(c in x for c in fam.children):
            continue
        for q in (fam.father, fam.mother):
            if q is not None and q in x:
                by_parent.setdefault(q, []).append(fam)
    for q, fams in by_parent.items():
        fams.sort(key=lambda f: sum(_hangs(people, f, x)) / max(1, len(_hangs(people, f, x))))
        span = min(NODE_W - 30, 16 * (len(fams) - 1))
        for k, fam in enumerate(fams):
            dx = -span / 2 + span * k / (len(fams) - 1) if len(fams) > 1 else 0.0
            fam.drops[q] = x[q] + NODE_W / 2 + dx


def _hangs(people: dict, fam: Family, x: dict[int, float]) -> list[float]:
    """Where the family's children hang from its line: one point each, or one for twins."""
    groups: dict[object, list[int]] = {}
    for c in fam.children:
        if c in x:
            groups.setdefault(people[c].litter or ("one", c), []).append(c)
    return [sum(x[c] + NODE_W / 2 for c in members) / len(members) for members in groups.values()]


def _stem(fam: Family, parents: list[int]) -> float:
    return sum(fam.drops[q] for q in parents) / len(parents)


def _order_lanes(people: dict, families: list[Family], x: dict[int, float], lanes: _Lanes) -> None:
    """The order of the lines in each gap that crosses the fewest other lines (the owner: "at
    most a single point of intersection between lines"): lanes are swapped while a swap helps."""
    for g in set(lanes.row.values()):
        fams = [f for f in families if lanes.row.get(f.id) == g]
        couples = lanes.couple_count.get(g, 0)
        kids = lanes.count.get(g, 0)
        couple_order = list(range(couples))
        kid_order = list(range(kids))

        def crossings() -> int:
            vertical, horizontal = [], []
            for f in fams:
                parents = [q for q in (f.father, f.mother) if q is not None and q in x]
                hangs = _hangs(people, f, x)
                ky = couples + 1 + kid_order.index(lanes.index[f.id])
                if f.id in lanes.couple_index:
                    cy = couple_order.index(lanes.couple_index[f.id])
                    stem = _stem(f, parents)
                    vertical += [(f.id, f.drops[q], -1e9, cy) for q in parents]
                    vertical.append((f.id, stem, cy, ky))
                    horizontal.append((f.id, min(f.drops[q] for q in parents), max(f.drops[q] for q in parents), cy))
                    xs = hangs + [stem]
                else:
                    vertical += [(f.id, f.drops[q], -1e9, ky) for q in parents]
                    xs = hangs + [f.drops[q] for q in parents]
                vertical += [(f.id, h, ky, 1e9) for h in hangs]
                horizontal.append((f.id, min(xs), max(xs), ky))
            return sum(1 for fv, vx, y0, y1 in vertical for fh, x0, x1, hy in horizontal
                       if fv != fh and x0 < vx < x1 and y0 < hy < y1)

        best = crossings()
        for _pass in range(30):
            better = False
            for order in (couple_order, kid_order):
                for k in range(len(order) - 1):
                    order[k], order[k + 1] = order[k + 1], order[k]
                    now = crossings()
                    if now < best:
                        best, better = now, True
                    else:
                        order[k], order[k + 1] = order[k + 1], order[k]
            if not better:
                break
        for f in fams:
            lanes.index[f.id] = kid_order.index(lanes.index[f.id])
            if f.id in lanes.couple_index:
                lanes.couple_index[f.id] = couple_order.index(lanes.couple_index[f.id])


def _leave_y(lay: "Layout", q: int, at: float) -> float:
    """Where a line leaving the bottom of q's portrait at x `at` starts, on its edge."""
    return _edge_y(lay, q, at, bottom=True)


def _arrive_y(lay: "Layout", q: int, at: float) -> float:
    """Where a line reaching the top of q's portrait at x `at` ends, on its edge."""
    return _edge_y(lay, q, at, bottom=False)


CLEAR = 7                                # how far a line keeps from a frame it passes


def _route(lay: "Layout", at: float, y0: float, y1: float, jogs: dict, back: bool = False,
           start: float | None = None) -> list[list]:
    """A line down from (at, y0) to y1 that never runs through a frame: straight while nothing is
    in the way; at each row of frames in the way, it steps sideways just above that row into the
    nearest gap between its frames and carries on down; a line that must end at a frame (`back`)
    steps back just above y1.  Each step in a gap has a height of its own.  `start` is where the
    drawn line begins when that is above y0 (the curve of a circle's frame)."""
    frames = lay.spans()
    legs: list[list] = []
    x, y, low = at, (start if start is not None else y0), y0
    for _step in range(40):
        blocking = [fy for fx0, fx1, fy in frames
                    if fx0 - CLEAR < x < fx1 + CLEAR and fy < y1 - 1 and fy + NODE_H > low + 1]
        if not blocking:
            break
        top = min(blocking)
        row = [(fx0 - CLEAR, fx1 + CLEAR) for fx0, fx1, fy in frames if fy < top + NODE_H and fy + NODE_H > top]
        gap = next(gx for d in range(0, 8000) for gx in (x + d, x - d) if all(not lo < gx < hi for lo, hi in row))
        k = jogs.get(round(top), 0)
        jogs[round(top)] = k + 1
        side = max(low + 4, top - 12 - 5 * (k % 3))
        legs += [[(x, y), (x, side)], [(x, side), (gap, side)]]
        x, y, low = gap, side, side
    if back and x != at:
        k = jogs.get(round(y1), 0)
        jogs[round(y1)] = k + 1
        up = max(low + 4, y1 - 12 - 5 * (k % 3))
        return legs + [[(x, y), (x, up)], [(x, up), (at, up)], [(at, up), (at, y1)]]
    return legs + [[(x, y), (x, y1)]]


def lines(lay: Layout) -> list[tuple[str, list[tuple[float, float]], int, str]]:
    """Every connector as (colour, polyline, family id, which piece it is), all in the pairing's
    one colour (the owner: the siblings' and the parents' connector lines "should be the same
    color").  Two parents drop to their couple's line; from its middle a stem falls to the
    children's line, and each child hangs straight down from that (babies born together from one
    point that opens into a triangle).  A lone parent drops straight to the children's line.
    Pieces the player dragged are where they put them (still joined, still touching the
    portraits), and no two families' pieces lie on each other."""
    people = lay.village.people
    # [colour, points, family id, piece, {end: (side, villager) of a portrait it is on},
    #  {end: the piece that end is attached to}]
    drawn: list[list] = []
    jogs: dict = {}

    def add(points: list, piece: str, anchors: dict | None = None, up: dict | None = None) -> str:
        drawn.append([fam.colour, points, fam.id, piece, anchors or {}, up or {}])
        return piece

    def cx(pid: int) -> float:
        return lay.x[pid] + NODE_W / 2

    def key(pid: int) -> str:
        return entry_key(lay.village, people[pid])

    for fam in lay.families:
        kids = [c for c in fam.children if c in lay.x]
        if not kids:
            continue
        lane = fam.lane_y
        row = min(lay.y[c] for c in kids)
        parents = [q for q in (fam.father, fam.mother) if q is not None and q in lay.x]
        groups: dict[object, list[int]] = {}
        for c in kids:
            groups.setdefault(people[c].litter or ("one", c), []).append(c)
        def clearest_down(c: int, at: float, lane: float) -> float:
            """Where along child c's portrait their line from the children's line comes down with the
            fewest steps aside: `at` (their middle) when its way is clear."""
            xs = [px for px, _py in lay.frame_points(c)]
            low, high = min(xs) + 12, max(xs) - 12

            def steps(x: float) -> int:
                return len(_route(lay, x, lane, lay.y[c], dict(jogs), back=True))
            best, fewest = at, steps(at)
            for k in range(1, int((high - low) / 4) + 1):
                if fewest == 1:
                    break
                for x in (at + 4 * k, at - 4 * k):
                    if low <= x <= high and steps(x) < fewest:
                        best, fewest = x, steps(x)
            return best

        hang = [sum(cx(c) for c in members) / len(members) if len(members) > 1
                else clearest_down(members[0], cx(members[0]), fam.lane_y) for members in groups.values()]
        target = "couple" if len(parents) == 2 else "lane"

        def clearest(q: int, at: float, end: float) -> float:
            """Where along q's portrait the line to `end` leaves with the fewest steps aside (the
            owner: "minimize line bumps"): `at` when its way is clear, else the nearest clearer place."""
            xs = [px for px, _py in lay.frame_points(q)]
            low, high = min(xs) + 12, max(xs) - 12

            def steps(x: float) -> int:
                if lay.y[q] > end:
                    return len(_route(lay, x, end, _arrive_y(lay, q, x), dict(jogs), back=True))
                return len(_route(lay, x, lay.y[q] + NODE_H, end, dict(jogs), start=_leave_y(lay, q, x)))
            best, fewest = at, steps(at)
            for k in range(1, int((high - low) / 4) + 1):
                if fewest == 1:
                    break
                for x in (at + 4 * k, at - 4 * k):
                    if low <= x <= high and steps(x) < fewest:
                        best, fewest = x, steps(x)
            return best

        def leave(q: int, end: float) -> float:
            """The parent's line to `end` (the couple's line, or for a lone parent the children's);
            where it arrives.  A parent below it (put in a later generation by the player) leaves
            from the top of their frame and goes up."""
            at = clearest(q, fam.drops[q], end)
            if lay.y[q] > end:
                legs = _route(lay, at, end, _arrive_y(lay, q, at), jogs, back=True)
                names = [f"from {key(q)} {k}" for k in range(len(legs))]
                for k, leg in enumerate(legs):
                    add(leg, names[k], {1: ("top", q)} if k == len(legs) - 1 else None,
                        {0: names[k - 1] if k else target})
                return at
            legs = _route(lay, at, lay.y[q] + NODE_H, end, jogs, start=_leave_y(lay, q, at))
            names = [f"from {key(q)} {k}" for k in range(len(legs))]
            for k, leg in enumerate(legs):
                add(leg, names[k], {0: ("bottom", q)} if k == 0 else None,
                    {1: names[k + 1] if k < len(legs) - 1 else target})
            return legs[-1][-1][0]

        if len(parents) == 2:
            couple = fam.couple_y
            ends = [leave(q, couple) for q in parents]
            add([(min(ends), couple), (max(ends), couple)], "couple")
            stem = sum(ends) / 2
            add([(stem, couple), (stem, lane)], "stem", up={0: "couple", 1: "lane"})
            xs = hang + [stem]
        else:
            xs = hang + [leave(q, lane) for q in parents]
        add([(min(xs), lane), (max(xs), lane)], "lane")
        for members, apex in zip(groups.values(), hang):
            first = key(members[0])
            if len(members) == 1:
                c = members[0]
                legs = _route(lay, apex, lane, lay.y[c], jogs, back=True)
                (ex, _ey) = legs[-1][-1]            # the last stretch ends on the frame as drawn
                legs[-1][-1] = (ex, _arrive_y(lay, c, ex))
                names = [f"to {first} {k}" for k in range(len(legs))]
                for k, leg in enumerate(legs):
                    add(leg, names[k], {1: ("top", c)} if k == len(legs) - 1 else None,
                        {0: names[k - 1] if k else "lane"})
                continue
            tip, base = row - LANE_BOTTOM + 14, row - 8
            if row > lay.tops[people[members[0]].generation]:       # babies in a lower row
                tip = row - SUBGAP + 14
            legs = _route(lay, apex, lane, tip, jogs, back=True)
            names = [f"to {first} {k}" for k in range(len(legs))]
            for k, leg in enumerate(legs):
                add(leg, names[k], up={0: names[k - 1] if k else "lane"})
            for c in members:
                add([(apex, tip), (cx(c), base), (cx(c), _arrive_y(lay, c, cx(c)))], f"leg {key(c)}",
                    {2: ("top", c)}, {0: names[-1]})
            add([(min(cx(c) for c in members), base), (max(cx(c) for c in members), base)], f"bar {first}")
    families = {f.id: family_key(lay.village, f) for f in lay.families}
    for s in list(drawn):
        shift = lay.edits.line_moves.get(f"{families[s[2]]}|{s[3]}")
        if shift and len(s[1]) == 2 and not s[3].startswith("bar "):
            (x0, y0), (x1, y1) = s[1]
            upright = x0 == x1 and y0 != y1
            if not isinstance(shift, list):     # across itself: an upright piece sideways, else up or down
                shift = [shift, 0.0] if upright else [0.0, shift]
            elif not lay.edits.diagonal_lines:  # only across itself, so every line stays square
                shift = [shift[0], 0.0] if upright else [0.0, shift[1]]
            _move_piece(drawn, s, *shift, lay=lay)
    _separate(drawn, lay)
    _fit(drawn)
    return [(colour, points, fid, piece) for colour, points, fid, piece, _anchors, _up in drawn]


def _fit(drawn: list) -> None:
    """Each straight piece that others are attached to runs exactly between the outermost of them
    (and its own attached ends): no stub left sticking out past a line moved inward, and no gap."""
    for s in drawn:
        if len(s[1]) != 2 or s[1][0] == s[1][1]:
            continue
        a, b = s[1]
        points = [o[1][end] for o in drawn if o is not s and o[2] == s[2]
                  for end, name in o[5].items() if name == s[3]]
        if not points:
            continue
        points += [s[1][end] for end in (0, 1) if end in s[4] or end in s[5]]
        ts = [_along(pt, a, b) for pt in points]
        lo, hi = min(ts), max(ts)
        s[1] = [(a[0] + lo * (b[0] - a[0]), a[1] + lo * (b[1] - a[1])),
                (a[0] + hi * (b[0] - a[0]), a[1] + hi * (b[1] - a[1]))]


def _along(pt: tuple, a: tuple, b: tuple) -> float:
    """Where pt is along the piece from a to b: 0 at a, 1 at b."""
    (px, py), (ax, ay), (bx, by) = pt, a, b
    length = (bx - ax) ** 2 + (by - ay) ** 2
    return 0.0 if length < 1e-9 else ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / length


def _onto(pt: tuple, piece: list) -> tuple:
    """pt slid onto a straight piece's line (the piece made longer when it lands past an end)."""
    a, b = piece[1][0], piece[1][-1]
    t = _along(pt, a, b)
    if a == b:                                  # no length: a level line, stretched to reach it
        landed = (pt[0], a[1])
        if len(piece[1]) == 2:
            piece[1] = [(min(a[0], landed[0]), a[1]), (max(a[0], landed[0]), a[1])]
        return landed
    landed = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    if t < 0 and len(piece[1]) == 2:
        piece[1] = [landed, b]
    elif t > 1 and len(piece[1]) == 2:
        piece[1] = [a, landed]
    return landed


def _move_piece(drawn: list, s: list, dx: float, dy: float, lay: Layout | None = None) -> None:
    """A straight piece dragged (dx, dy), its lines kept whole (the owner: "Keep. The. Lines.
    Connected. No. matter. How. they. are. moved."): an end attached to another piece slides along
    that piece, an end on a portrait slides along the portrait's edge, and every piece attached to
    it follows, turning diagonal if it must (the owner: "diagonal is ok")."""
    pieces = {(o[2], o[3]): o for o in drawn}
    old = list(s[1])
    new = []
    for end, (x, y) in enumerate(old):
        moved = (x + dx, y + dy)
        if end in s[4] and lay is not None:
            side, q = s[4][end]
            xs = [px for px, _py in lay.frame_points(q)]
            lo, hi = min(xs) + 12, max(xs) - 12
            nx = min(max(moved[0], lo), hi) if lo < hi else (min(xs) + max(xs)) / 2
            moved = (nx, _leave_y(lay, q, nx) if side == "bottom" else _arrive_y(lay, q, nx))
        elif end in s[5] and (s[2], s[5][end]) in pieces:
            moved = _onto(moved, pieces[(s[2], s[5][end])])
        new.append(moved)
    s[1] = new
    _follow(drawn, s, old, new, set())


def _follow(drawn: list, s: list, old: list, new: list, seen: set) -> None:
    """The pieces attached to s, which moved from `old` to `new`, keep their ends on it: each end
    stays the same way along it, and whatever is attached to them follows in turn."""
    seen = seen | {s[3]}
    for other in drawn:
        if other is s or other[2] != s[2] or other[3] in seen:
            continue
        before = list(other[1])
        points = list(other[1])
        for end, name in other[5].items():
            if name == s[3]:
                t = _along(points[end], old[0], old[-1])
                points[end] = (new[0][0] + t * (new[-1][0] - new[0][0]), new[0][1] + t * (new[-1][1] - new[0][1]))
        if points != before:
            other[1] = points
            _follow(drawn, other, before, points, seen)


APART = 4                               # how far a line moves off another it would lie on


def _separate(drawn: list, lay: Layout | None = None) -> None:
    """No two families' lines lie on top of each other (the owner: "they can be as close as
    possible but not overlapping"): a straight run along another family's run moves the least it
    can, APART at a time -- an upright one sideways, a level one up or down -- keeping its line
    whole as any dragged piece does."""
    def upright(s) -> bool:
        pts = s[1]
        return len(pts) == 2 and pts[0][0] == pts[1][0] and pts[0][1] != pts[1][1]

    def level(s) -> bool:
        pts = s[1]
        return len(pts) == 2 and pts[0][1] == pts[1][1] and pts[0][0] != pts[1][0]

    def span(pts, axis: int) -> tuple[float, float]:
        a, b = pts[0][axis], pts[1][axis]
        return min(a, b), max(a, b)

    def overlaps(a, b, axis: int) -> bool:
        """Runs on one line (the other axis within a pixel) sharing more than a pixel of it."""
        (a0, a1), (b0, b1) = span(a, 1 - axis), span(b, 1 - axis)
        return abs(a[0][axis] - b[0][axis]) < 1 and min(a1, b1) - max(a0, b0) > 1

    for _round in range(12):
        moved = False
        for kind, axis in ((upright, 0), (level, 1)):
            runs = [s for s in drawn if kind(s)]
            for i, a in enumerate(runs):
                if not kind(a) or not any(b[2] != a[2] and kind(b) and overlaps(a[1], b[1], axis) for b in runs[:i]):
                    continue
                for step in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6):
                    shift = step * APART
                    trial = [tuple(v + shift if k == axis else v for k, v in enumerate(pt)) for pt in a[1]]
                    if not any(b is not a and b[2] != a[2] and kind(b) and overlaps(trial, b[1], axis) for b in runs):
                        break
                _move_piece(drawn, a, shift if axis == 0 else 0.0, shift if axis == 1 else 0.0, lay)
                moved = True
        if not moved:
            break


# ---------------------------------------------------------------------------
# Head pictures
# ---------------------------------------------------------------------------

def sheet_name(game: int, p: gen.Person) -> str | None:
    if p.upcoming or p.sex not in ("Male", "Female"):
        return None
    return SHEETS[game][0] if p.sex == "Male" else SHEETS[game][1]


def sheets_present(game: int, images: Path | None) -> dict[str, Path]:
    if images is None:
        return {}
    out = {}
    for name in SHEETS[game]:
        path = Path(images) / name
        if path.is_file():
            out[name] = path
    return out


_BOXES: dict[str, dict[int, tuple[int, int, int, int]]] = {}
DEFAULT_BOX = (0, 0, HEAD_W, FACE_H)


def head_boxes(path: Path) -> dict[int, tuple[int, int, int, int]]:
    """Each head row's visible pixels in the column the tree draws (x0, y0, x1, y1 inside the
    40x65 cell): the head is centred by what shows, not by the cell (A New Home's male faces fill
    only its top 25 rows).  Read with the standard library: an 8-bit RGBA PNG, not interlaced --
    the games' own head sheets; anything else gives no boxes (the tree then uses DEFAULT_BOX)."""
    key = str(path)
    if key in _BOXES:
        return _BOXES[key]
    out: dict[int, tuple[int, int, int, int]] = {}
    try:
        data = Path(path).read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError
        at, idat, width, height = 8, [], 0, 0
        while at < len(data):
            length, kind = struct.unpack(">I4s", data[at:at + 8])
            body = data[at + 8:at + 8 + length]
            if kind == b"IHDR":
                width, height, depth, colour, _c, _f, interlace = struct.unpack(">IIBBBBB", body)
                if depth != 8 or colour != 6 or interlace != 0:
                    raise ValueError
            elif kind == b"IDAT":
                idat.append(body)
            at += 12 + length
        raw = zlib.decompress(b"".join(idat))
        stride, bpp = width * 4, 4
        prev = bytearray(stride)
        alpha = []
        for row in range(height):
            filt = raw[row * (stride + 1)]
            line = bytearray(raw[row * (stride + 1) + 1:(row + 1) * (stride + 1)])
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                if filt == 1:
                    line[i] = (line[i] + a) & 255
                elif filt == 2:
                    line[i] = (line[i] + b) & 255
                elif filt == 3:
                    line[i] = (line[i] + ((a + b) >> 1)) & 255
                elif filt == 4:
                    pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                    pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                    line[i] = (line[i] + pred) & 255
            alpha.append(line[3::4])
            prev = line
        left = HEAD_FRAME * HEAD_W
        for r in range(height // HEAD_H):
            box = None
            for y in range(HEAD_H):
                row_alpha = alpha[r * HEAD_H + y][left:left + HEAD_W]
                xs = [x for x, value in enumerate(row_alpha) if value > 24]
                if xs:
                    if box is None:
                        box = [xs[0], y, xs[-1] + 1, y + 1]
                    else:
                        box = [min(box[0], xs[0]), box[1], max(box[2], xs[-1] + 1), y + 1]
            if box is not None:
                out[r] = tuple(box)
    except (OSError, ValueError, zlib.error, struct.error, IndexError):
        out = {}
    _BOXES[key] = out
    return out


def face_box(present: dict, sheet: str | None, row: int | None) -> tuple[int, int, int, int]:
    if sheet in present and row is not None:
        return head_boxes(present[sheet]).get(row, DEFAULT_BOX)
    return DEFAULT_BOX


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


# ---------------------------------------------------------------------------
# Words around the tree
# ---------------------------------------------------------------------------

def generation_label(lay: Layout, g: int) -> list[str]:
    return [text for _part, text in label_lines(lay, g)]


def label_lines(lay: Layout, g: int) -> list[tuple[str, str]]:
    """The generation's label as drawn, line by line: (which part it is, its words).  The player's
    own lines are "custom<k>"; otherwise "first" (the number and the name) and the LABEL_PARTS
    lines, less the parts the player deleted (from this generation or from every one)."""
    if lay.edits.generations.get(str(g)):
        return [(f"custom{k}", text) for k, text in enumerate(lay.edits.generations[str(g)])]
    parts = default_label_parts(lay, g)
    shown = [part for part in parts
             if f"label:{g}:{part}" not in lay.edits.hidden and f"label:*:{part}" not in lay.edits.hidden]
    first = " ".join(parts[part] for part in ("number", "name") if part in shown)
    return ([("first", first)] if first else []) + [(part, parts[part]) for part in ("total", "living", "upcoming")
                                                     if part in parts and part in shown]


def default_generation_label(lay: Layout, g: int) -> list[str]:
    """The label the tree draws when the player has written none of their own."""
    return [text for _part, text in label_lines(replace(lay, edits=replace(lay.edits, generations={})), g)]


def generation_number(lay: Layout, g: int) -> str:
    return gen.roman(g) if lay.edits.numbering == "roman" else str(g)


def default_label_parts(lay: Layout, g: int) -> dict[str, str]:
    v = lay.village
    members = [v.people[q] for q in lay.x if v.people[q].generation == g]
    people = [p for p in members if not p.upcoming]
    upcoming = len(members) - len(people)
    women = sum(p.sex == "Female" for p in people)
    men = sum(p.sex == "Male" for p in people)
    alive = sum(p.alive for p in people)
    out = {"number": f"{generation_number(lay, g)}.", "name": "Founders" if g == 1 else f"Generation {g}",
           "total": f"{len(people)} total: {women} females, {men} males", "living": f"{alive} living"}
    if upcoming:
        out["upcoming"] = f"{upcoming} upcoming"
    return out


def title_lines(lay: Layout, game_title: str) -> tuple[str, str]:
    first, second = default_title_lines(lay, game_title)
    page = f" -- Page {lay.page + 1} of {lay.pages}" if lay.pages > 1 else ""
    return (lay.edits.title or first) + page, lay.edits.subtitle or second


def default_title_lines(lay: Layout, game_title: str) -> tuple[str, str]:
    v = lay.village
    name = v.tribe or f"Save {v.slot}"
    return (f"{game_title} -- Family Tree",
            f"{name} (Save {v.slot}) -- {len(v.known())} villagers known, {len(v.living())} living -- "
            f"{datetime.now():%Y-%m-%d %H:%M}")


# Words the tree writes that the player may retype (the owner: "I wanna rename "unrelated
# individuals" to something else").  The footer's own words are footer(lay).
WORDS = {"others": "Unrelated Individuals", "others_note": "no recorded parent or child", "footer": ""}


def words(lay: Layout, key: str) -> str:
    return lay.edits.words.get(key) or (footer(lay) if key == "footer" else WORDS[key])


FOOTER = ("Each unrelated villager has a colour of their own and full brothers and sisters share one; each "
          "pairing has its own connector; a triangle joins twins and triplets.  Generation I is the founders; a "
          "villager who arrived later is in the generation they first appear in.  Made by the Virtual Villagers "
          "Fun Patcher's Family Tree Maker from the save and the patcher's logs.")


def footer(lay: Layout) -> str:
    """The Key: which portrait shape each group is drawn in (as the player set them), then FOOTER."""
    def plural(shape: str) -> str:
        name = PORTRAIT_SHAPES[shape].lower()
        return name + ("es" if name.endswith(("s", "x")) else "s")
    groups = "; ".join(f"{label}: {plural(lay.edits.shapes[group])}" for group, label in GROUPS.items())
    return f"{groups}.  {FOOTER}"


def node_text(lay: Layout, p: gen.Person) -> list[str]:
    """The entry's lines: the player's own, or the patcher's (default_text)."""
    lines = lay.entry(p).get("lines")
    return lines if lines else default_text(lay, p)


def default_text(lay: Layout, p: gen.Person) -> list[str]:
    """Name, age in game units and years, and what else there is to say: "(deceased)" for the
    dead (the owner: deceased villagers are not faded, their entry says so)."""
    if p.upcoming:
        size = sum(1 for q in lay.village.people.values() if p.litter is not None and q.litter == p.litter)
        return ["Upcoming child"] + ([{2: "(twins)", 3: "(triplets)"}[size]] if size in (2, 3) else [])
    e = lay.edits
    ages = (["age unknown"] if p.age is None and (e.show_units or e.show_years) else
            [] if p.age is None else
            ([f"{p.age} game units"] if e.show_units else []) + ([f"{p.years} years old"] if e.show_years else []))
    if p.alive:
        extra = "Heathen" if p.heathen else ""
    else:
        extra = {"died": "(deceased)", "disappeared": "(disappeared)"}.get(p.gone, "(left the village)")
    return [f"{p.number}. {lay.names.get(p.id, p.name)}"] + ages + ([extra] if extra else [])


def placement(lay: Layout, p: gen.Person, box: tuple = None) -> tuple[float, float, float, list]:
    """(the head cell's left and top inside the frame, the first line's baseline, the lines as
    drawn): the face (the head's visible pixels, `box`) and the lines centred together (the owner:
    "center the heads within the portrait shapes vertically and horizontally"), or the head at the
    top when the player turns centring off ("in case players type a lot of stuff")."""
    x0, y0, x1, y1 = box or DEFAULT_BOX
    face = (y1 - y0) * HEAD_SCALE
    face_top = 6.0 if lay.edits.centre_heads else 10.0
    lines = shown_text(lay, p, int((NODE_H - face_top - face - 8 - 6) // LINE_H))
    if lay.edits.centre_heads:
        face_top = max(face_top, (NODE_H - (face + 8 + len(lines) * LINE_H)) / 2)
    left = NODE_W / 2 - (x0 + x1) / 2 * HEAD_SCALE
    return left, face_top - y0 * HEAD_SCALE, face_top + face + 8 + LINE_H - 3, lines


WRAP = 17                               # characters across a portrait


def _wrap(text: str, n: int = WRAP) -> list[str]:
    """A line as it fits across a portrait: broken between words, a word too long for one line
    broken where it must."""
    out: list[str] = []
    line = ""
    for word in text.split(" "):
        while len(word) > n:
            if line:
                out.append(line)
                line = ""
            out.append(word[:n])
            word = word[n:]
        if not line:
            line = word
        elif len(line) + 1 + len(word) <= n:
            line += " " + word
        else:
            out.append(line)
            line = word
    out.append(line)
    return out


def shown_text(lay: Layout, p: gen.Person, room: int) -> list[tuple[str, bool]]:
    """The portrait's lines as drawn, each with whether it is bold (the first line, the name):
    every line wrapped to fit across, and as many as fit below the head -- the last of them ending
    in ... when some did not."""
    out = [(piece, k == 0) for k, text in enumerate(node_text(lay, p)) for piece in _wrap(text)]
    room = max(1, room)
    if len(out) > room:
        last, bold = out[room - 1]
        out = out[:room - 1] + [(last[:WRAP - 1] + "…", bold)]
    return out


def _unit_outlines() -> dict[str, list[tuple[float, float]]]:
    """Each many-sided shape in a 1 x 1 box."""
    def fit(points: list) -> list:
        xs, ys = zip(*points)
        return [((px - min(xs)) / (max(xs) - min(xs)), (py - min(ys)) / (max(ys) - min(ys))) for px, py in points]

    plus = [(0.33, 0), (0.67, 0), (0.67, 0.33), (1, 0.33), (1, 0.67), (0.67, 0.67), (0.67, 1), (0.33, 1),
            (0.33, 0.67), (0, 0.67), (0, 0.33), (0.33, 0.33)]
    turned = [((px - 0.5) * math.cos(math.pi / 4) - (py - 0.5) * math.sin(math.pi / 4),
               (px - 0.5) * math.sin(math.pi / 4) + (py - 0.5) * math.cos(math.pi / 4)) for px, py in plus]
    star = [(math.sin(k * math.pi / 5) * (0.5 if k % 2 == 0 else 0.2),
             -math.cos(k * math.pi / 5) * (0.5 if k % 2 == 0 else 0.2)) for k in range(10)]
    heart = [(16 * math.sin(t) ** 3, -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)))
             for t in (k * 2 * math.pi / 72 for k in range(72))]
    return {
        "diamond": [(0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)],
        "triangle": [(0.5, 0), (1, 1), (0, 1)],
        "plus": plus,
        "cross": [(0.35, 0), (0.65, 0), (0.65, 0.25), (1, 0.25), (1, 0.5), (0.65, 0.5), (0.65, 1), (0.35, 1),
                  (0.35, 0.5), (0, 0.5), (0, 0.25), (0.35, 0.25)],
        "x": fit(turned),
        "star": fit(star),
        "hexagon": [(0.5, 0), (1, 0.25), (1, 0.75), (0.5, 1), (0, 0.75), (0, 0.25)],
        "octagon": [(0.3, 0), (0.7, 0), (1, 0.3), (1, 0.7), (0.7, 1), (0.3, 1), (0, 0.7), (0, 0.3)],
        "heart": fit(heart),
    }


OUTLINES = _unit_outlines()


SVG_DASHES = {"dotted": "1.5 4", "dashed": "8 5", "dashdot": "8 4 1.5 4"}
TK_DASHES = {"dotted": (2, 4), "dashed": (8, 5), "dashdot": (8, 4, 2, 4)}
GDI_DASHES = {"dotted": 2, "dashed": 1, "dashdot": 3}       # GDI+'s dash styles


# Each shape's own width for its height (the owner: "I want the shapes to not look so squashed
# horizontally. or vertically, by default"): a portrait's frame is drawn this wide for a portrait's
# height until the player resizes it.  The heart's and the star's are their outlines' own; a
# diamond is a playing card's.  A rectangle, a rounded rectangle and an oval fill the portrait.
ASPECTS = {"rect": 1.0, "rounded": 1.0, "circle": 1.0, "heart": 1.107, "star": 1.051, "triangle": 1.155, "diamond": 0.7, "cross": 0.75, "x": 1.0,
           "plus": 1.0, "hexagon": 0.866, "octagon": 1.0}
FRAME_MIN, FRAME_MAX = 8.0, 1200.0      # a resized frame's sides
# What the size boxes step through (the owner: "values correspond to typical font sizes"): a word
# processor's font sizes, on up to a whole portrait and beyond; line weights as a word processor's.
SIZE_STEPS = (8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72, 96, 106, 120, 144, 156, 180, 200,
              240, 300, 400, 500, 600, 800, 1000, 1200)
LINE_STEPS = (0.25, 0.5, 0.75, 1, 1.5, 2.2, 2.25, 3, 4.5, 6, 8, 10, 12, 16, 20)


def natural_width(kind: str) -> float:
    return NODE_H * ASPECTS[kind] if kind in ASPECTS else NODE_W


def shape_points(kind: str, x: float, y: float, w: float, h: float, radius: float = 0.0,
                 angle: float = 0.0) -> list[tuple[float, float]]:
    """Any shape's edge as corners (an oval by 48, each rounded corner by 6), turned `angle` degrees
    about the box's middle."""
    corners = outline(kind, x, y, w, h)
    if corners is None and kind in ("ellipse", "circle"):
        ox, oy, ow, oh = oval_box(kind, x, y, w, h)
        corners = [(ox + ow / 2 * (1 + math.cos(t)), oy + oh / 2 * (1 + math.sin(t)))
                   for t in (k * 2 * math.pi / 48 for k in range(48))]
    elif corners is None:
        r = min(radius, w / 2, h / 2)
        corners = [(cx + r * math.cos(math.radians(start + k * 18)), cy + r * math.sin(math.radians(start + k * 18)))
                   for cx, cy, start in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90),
                                         (x + r, y + r, 180))
                   for k in range(6)]
    if not angle:
        return corners
    mx, my = x + w / 2, y + h / 2
    return [(mx + dx, my + dy) for dx, dy in (turn(px - mx, py - my, angle) for px, py in corners)]


def inside(corners: list[tuple[float, float]], x: float, y: float) -> bool:
    """Whether (x, y) is inside the shape these corners outline."""
    hit = False
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


def box_corners(cx: float, cy: float, w: float, h: float, angle: float) -> list[tuple[float, float]]:
    """A box's top left, top right, bottom right and bottom left, turned about its middle."""
    out = []
    for lx, ly in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        dx, dy = turn(lx * w / 2, ly * h / 2, angle)
        out.append((cx + dx, cy + dy))
    return out


def outline(kind: str, x: float, y: float, w: float, h: float) -> list[tuple[float, float]] | None:
    """A many-sided shape's corners in the box, or None for a square, rounded square, circle or oval."""
    unit = OUTLINES.get(kind)
    return [(x + px * w, y + py * h) for px, py in unit] if unit else None


def oval_box(kind: str, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    """The box an oval fills: the whole box, or for a circle the largest square in its middle."""
    if kind != "circle":
        return x, y, w, h
    d = min(w, h)
    return x + (w - d) / 2, y + (h - d) / 2, d, d


def corner_radius(kind: str) -> float:
    return 24.0 if kind in ("rounded", "rounded_rect") else 0.0


def _edge_y(lay: "Layout", q: int, at: float, bottom: bool) -> float:
    """Where a straight up-and-down line at x `at` meets the edge of q's portrait: its bottom edge
    (`bottom`) or its top -- whatever its shape."""
    corners = lay.frame_points(q)
    meets = []
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        if min(ax, bx) <= at <= max(ax, bx) and ax != bx:
            meets.append(ay + (at - ax) / (bx - ax) * (by - ay))
    if not meets:                       # a frame made narrower than where the line comes down
        _x, y, _w, h, _a = lay.frame(q)
        return y + h if bottom else y
    return max(meets) if bottom else min(meets)


def key_marks(lay: Layout) -> list[tuple[str, str]]:
    """The Key: every mark the player has given someone in this tree, in the player's order."""
    used = {lay.entry(lay.village.people[q]).get("mark") for q in lay.x}
    return [(label, colour) for label, colour in lay.edits.marks.items() if label in used]


# ---------------------------------------------------------------------------
# The scene: everything the tree draws, once, for every way of drawing it (the page's SVG, the
# editor's canvas, the picture GDI+ saves).  Each item that belongs to a villager carries its id.
# ---------------------------------------------------------------------------

@dataclass
class Shape:
    kind: str                           # "rect", "ellipse" or "diamond"
    x: float
    y: float
    w: float
    h: float
    stroke: str
    width: float = 3.0
    fill: str | None = "#ffffff"
    radius: float = 8.0                 # a rect's corners
    dash: str = ""                      # BORDERS: "dotted", "dashed", "dashdot" or "" solid
    pid: int | None = None
    opacity: float = 1.0                # a plate behind words on a picture
    target: tuple | None = None         # what a right click recolours
    move: str = ""                      # MOVABLE: what dragging it moves
    angle: float = 0.0                  # turned this many degrees about its middle

    def points(self) -> list[tuple[float, float]]:
        return shape_points(self.kind, self.x, self.y, self.w, self.h, self.radius, self.angle)


@dataclass
class Line:
    points: list
    colour: str
    width: float = LINE_WIDTH
    target: tuple | None = None
    move: str = ""
    piece: str = ""                     # a family line's piece: "<family key>|<piece>", draggable
    opacity: float = 1.0
    dash: str = ""                      # LINE_TYPES


@dataclass
class Text:
    x: float
    y: float                            # the baseline
    text: str
    size: float
    colour: str
    bold: bool = False
    centre: bool = False                # x is the middle (else the start)
    pid: int | None = None
    role: str = ""                      # ROLES: whose style the player may change
    font: str = ""
    italic: bool = False
    underline: bool = False
    strike: bool = False
    target: tuple | None = None
    move: str = ""
    part: str = ""                      # a generation label's line: "<generation>|<label_lines part>"
    edit: str = ""                      # what retyping it changes (the editor's _edit_in_place)
    opacity: float = 1.0


@dataclass
class Head:
    x: float
    y: float
    sheet: str
    row: int
    pid: int | None = None
    opacity: float = 1.0
    scale: float = 1.0                  # of a resized portrait (HEAD_SCALE times this)


@dataclass
class Sticker:
    """A picture or a text box laid on the tree: its middle, size, turn (degrees clockwise),
    mirrorings and opacity (0-1).  `index` is its place in the edits' stickers; `picture` is None
    for a text box."""
    index: int
    picture: Path | None
    cx: float
    cy: float
    w: float
    h: float
    angle: float = 0.0
    flip_h: bool = False
    flip_v: bool = False
    opacity: float = 1.0
    text: str = ""
    font: str = ""
    size: float = 24.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    colour: str = INK
    align: str = "centre"
    valign: str = "middle"
    fill: str = ""
    fill_opacity: float = 100.0
    border: str = ""
    border_width: float = 0.0
    shape: str = "rect"

    def corners(self) -> list[tuple[float, float]]:
        """Top left, top right, bottom right, bottom left, turned."""
        return box_corners(self.cx, self.cy, self.w, self.h, self.angle)

    def bounds(self) -> tuple[float, float, float, float]:
        xs, ys = zip(*self.corners())
        return min(xs), min(ys), max(xs), max(ys)

    def contains(self, x: float, y: float) -> bool:
        lx, ly = turn(x - self.cx, y - self.cy, -self.angle)
        return abs(lx) <= self.w / 2 and abs(ly) <= self.h / 2


@dataclass
class Backdrop:
    colour: str
    colour2: str = ""                   # a gradient to this colour at the bottom, or a RAINBOWS key
    picture: Path | None = None
    fit: str = "cover"
    soften: int = 0                     # percent the picture fades (into the colour or gradient under it)


@dataclass
class Scene:
    width: float
    height: float
    background: str
    items: list = field(default_factory=list)
    boxes: dict = field(default_factory=dict)       # pid -> (x, y, w, h), what a click selects
    stickers: list = field(default_factory=list)    # the Sticker items, bottom one first


def picture_path(name: str, images: Path | None, library: dict | None = None) -> Path | None:
    """A background picture's file: the player's own, one in this game's Images ("game:<file>"),
    or one in game N's ("vvN:<file>", `library` holding each known game's Images folder)."""
    if not name:
        return None
    path = None
    if name.startswith("asset:"):
        path = BACKGROUNDS / name[6:]
    elif name.startswith("game:"):
        path = Path(images) / name[5:] if images is not None else None
    elif name[:2] == "vv" and name[3:4] == ":" and name[2:3].isdigit():
        folder = (library or {}).get(int(name[2]))
        path = Path(folder) / name[4:] if folder is not None else None
    else:
        path = Path(name)
    return path if path is not None and path.is_file() else None


def presets_available(images: Path | None, library: dict | None = None) -> list[tuple]:
    """The ready-made backgrounds whose picture (if any) this computer has."""
    return [p for p in PRESETS if not p[3] or picture_path(p[3], images, library) is not None]


def scene(lay: Layout, game_title: str, present: dict, images: Path | None = None,
          library: dict | None = None) -> Scene:
    """The whole tree as shapes, lines, text and heads.  `present` names the head sheets found;
    `images` is the game's Images folder and `library` each known game's (for the games' own
    background pictures)."""
    v = lay.village
    ink = lay.ink
    out = Scene(lay.width, lay.height, lay.background)
    add = out.items.append
    add(Backdrop(lay.background, lay.edits.rainbow or lay.edits.background2, picture_path(lay.edits.background_image, images, library),
                 lay.edits.background_fit, 100 - lay.edits.background_opacity))
    t1, t2 = title_lines(lay, game_title)
    middle = lay.width / 2
    # The tree's heading over its founders (the owner: "the heading of the tree should preferably
    # be centered with the founders' portraits").
    first = lay.rows[min(lay.rows)] if lay.rows else []
    head = (min(lay.x[q] for q in first) + max(lay.x[q] for q in first) + NODE_W) / 2 if first else middle
    plate = out.items[0].picture is not None        # words on a picture get a plate behind them
    plate_colour = lay.edits.plate_colour or lay.background
    if plate:
        span = max(len(t1) * 17, len(t2) * 8) + 60
        add(Shape("rect", head - span / 2, 14, span, 104, plate_colour, width=0, fill=plate_colour, move="title",
                  radius=14, target=("plate",)))
    add(Text(head, 48, t1, 30, ink, bold=True, centre=True, role="title", move="title", edit="title"))
    add(Text(head, 78, t2, 15, ink, centre=True, role="subtitle", move="subtitle", edit="subtitle"))
    keys = key_marks(lay)
    kx = head - sum(50 + 8 * len(label) for label, _c in keys) / 2
    for label, colour in keys:
        add(Shape("rect", kx, 94, 26, 16, colour, width=4, radius=4, target=("mark", label), move="key"))
        add(Text(kx + 34, 107, label, 14, ink, role="key", move="key", edit=f"mark:{label}"))
        kx += 50 + 8 * len(label)
    for g in sorted({v.people[q].generation for q in lay.x}):
        # Beside the generation's portraits as drawn, wherever they are (the owner: "so they're
        # actually accurate"); its rows' place when it has none drawn.
        ys = [py for q in lay.x if v.people[q].generation == g and q not in lay.others
              for _px, py in lay.frame_points(q)]
        top, bottom = (min(ys), max(ys)) if ys else (lay.tops[g], lay.tops[g] + lay.bands.get(g, NODE_H))
        y0 = top
        reach = lay.edits.label_line_reach
        if plate:
            add(Shape("rect", 12, top + 6, 228, bottom - top - 12, plate_colour, width=0,
                      fill=plate_colour, move=f"label{g}", radius=12, target=("plate",)))
        for k, (part, text) in enumerate(label_lines(lay, g)):
            add(Text(24, y0 + 40 + k * 22, text, 18 if k == 0 else 14, ink, bold=k == 0, role="labels",
                     move=f"label{g}", part=f"{g}|{part}", edit=f"label:{g}"))
        add(Line([(250, top - reach), (250, bottom + reach)], ink, lay.edits.label_line_width, target=("ink",),
                 move=f"label{g}"))
    if lay.others:
        # Off to the right, level with the tree's heading (the owner).
        add(Text(lay.others_left, 48, words(lay, "others"), 24, ink, bold=True, role="others", move="others",
                 edit="word:others"))
        add(Text(lay.others_left, 72, words(lay, "others_note"), 13, ink, role="others", move="others_note",
                 edit="word:others_note"))
    fams = {f.id: f for f in lay.families}
    for colour, points, fid, piece in lines(lay):
        key = family_key(v, fams[fid])
        if f"line:{key}|{piece}" not in lay.edits.hidden:
            style = lay.edits.family_lines.get(key, {})
            add(Line(points, colour, style.get("width", lay.edits.line_width), target=("family", key),
                     piece=f"{key}|{piece}", dash=style.get("dash", lay.edits.line_dash)))
    for pid in lay.x:
        _node(lay, v.people[pid], present, add)
        xs, ys = zip(*lay.frame_points(pid))
        x0, y0 = min(min(xs), lay.x[pid]), min(min(ys), lay.y[pid])
        x1, y1 = max(max(xs), lay.x[pid] + NODE_W), max(max(ys), lay.y[pid] + NODE_H)
        out.boxes[pid] = (x0, y0, x1 - x0, y1 - y0)
    key_text = words(lay, "footer")
    if plate:
        add(Shape("rect", middle - len(key_text) * 3.4, lay.height - 110, len(key_text) * 6.8, 30, plate_colour,
                  move="footer", width=0, fill=plate_colour, radius=10, target=("plate",)))
    add(Text(middle, lay.height - 90, key_text, 13, ink, centre=True, role="footer", move="footer",
             edit="word:footer"))
    out.items[:] = [i for i in out.items if f"word:{getattr(i, 'move', '')}" not in lay.edits.hidden]
    _apply_styles(out.items, lay.edits)
    _apply_opacity(out.items, lay.edits)
    _apply_moves(out.items, lay.edits)
    for k, raw in enumerate(lay.edits.stickers):
        item = sticker_item(k, raw, images, library)
        if item is not None:
            add(item)
            out.stickers.append(item)
    _fit_page(out)
    return out


MOVABLE = {"title": "the title", "subtitle": "the subtitle", "key": "the Key", "others": "the Unrelated "
           "Individuals heading", "others_note": "the line under the Unrelated Individuals heading",
           "footer": "the footer"}   # and "label<generation>": that generation's label


MARGIN = 10                             # nothing dragged goes nearer the page's edge than this


def _extent(item) -> tuple[float, float, float, float] | None:
    """An item's box on the page (words by their likely width)."""
    if isinstance(item, Line):
        xs, ys = zip(*item.points)
        return min(xs), min(ys), max(xs), max(ys)
    if isinstance(item, Shape):
        xs, ys = zip(*item.points())
        return min(xs), min(ys), max(xs), max(ys)
    if isinstance(item, Text):
        width = len(item.text) * item.size * 0.55
        left = item.x - width / 2 if item.centre else item.x
        return left, item.y - item.size, left + width, item.y + item.size * 0.3
    if isinstance(item, Sticker):
        return item.bounds()
    return None


def _apply_moves(items: list, edits: Edits) -> None:
    """The words the player dragged, where they dragged them -- never off the top or left of the
    page (the owner: the words go "ON TOP OF THE PICTURE, NOT OUTSIDE")."""
    groups: dict[str, list] = {}
    for item in items:
        if edits.moved.get(getattr(item, "move", "")):
            groups.setdefault(item.move, []).append(item)
    for name, group in groups.items():
        dx, dy = edits.moved[name]
        boxes = [b for b in map(_extent, group) if b is not None]
        dx = max(dx, MARGIN - min(b[0] for b in boxes))
        dy = max(dy, MARGIN - min(b[1] for b in boxes))
        for item in group:
            if isinstance(item, Line):
                item.points = [(px + dx, py + dy) for px, py in item.points]
            else:
                item.x += dx
                item.y += dy


def _fit_page(out: "Scene") -> None:
    """The page as large as everything on it (words, pictures and lines dragged right or down), so
    the background lies under all of it."""
    boxes = [b for b in map(_extent, out.items) if b is not None]
    if boxes:
        out.width = max(out.width, max(b[2] for b in boxes) + 2 * MARGIN)
        out.height = max(out.height, max(b[3] for b in boxes) + 2 * MARGIN)


def see_through(edits: Edits, part: str) -> float:
    """How opaque a part of the tree is (OPACITY), 0 to 1."""
    return edits.opacity.get(part, OPACITY[part][1]) / 100


def _apply_opacity(items: list, edits: Edits) -> None:
    """Each item as see-through as its part of the tree: the boxes behind words, the portraits (their
    frames, heads and words), the family lines and every other word."""
    for item in items:
        if isinstance(item, Shape) and item.target == ("plate",):
            item.opacity *= see_through(edits, "plates")
        elif isinstance(item, (Shape, Head)) and item.pid is not None or isinstance(item, Text) and item.pid is not None:
            item.opacity *= see_through(edits, "portraits")
        elif isinstance(item, Line) and item.piece:
            item.opacity *= see_through(edits, "lines")
        elif isinstance(item, (Text, Line)):
            item.opacity *= see_through(edits, "words")


def _apply_styles(items: list, edits: Edits) -> None:
    """The player's fonts: one for every word, and each role's own font, size, style and colour."""
    for item in items:
        if not isinstance(item, Text) or not item.role:
            continue
        style = edits.styles.get(item.role, {})
        item.font = style.get("font") or edits.font
        item.size = item.size * style.get("scale", 100) / 100
        item.bold = style.get("bold", item.bold)
        item.italic = style.get("italic", False)
        item.underline = style.get("underline", False)
        item.strike = style.get("strike", False)
        item.colour = style.get("colour", item.colour)
        if style.get("script") in SCRIPTS:      # smaller, raised or lowered: drawn so everywhere
            shrink, shift = SCRIPTS[style["script"]]
            item.y += item.size * shift
            item.size *= shrink


def sticker_item(index: int, raw: dict, images: Path | None, library: dict | None = None) -> Sticker | None:
    """A sticker to draw; None when its picture is not on this computer."""
    common = (raw["cx"], raw["cy"], raw["w"], raw["h"], raw["angle"], raw["flip_h"], raw["flip_v"],
              raw["opacity"] / 100)
    if raw["kind"] == "text":
        return Sticker(index, None, *common, text=raw["text"], font=raw["font"], size=raw["size"],
                       bold=raw["bold"], italic=raw["italic"], underline=raw["underline"], strike=raw["strike"],
                       colour=raw["colour"],
                       align=raw["align"], valign=raw["valign"], fill=raw["fill"],
                       fill_opacity=raw["fill_opacity"], border=raw["border"], border_width=raw["border_width"],
                       shape=raw["shape"])
    path = picture_path(raw["picture"], images, library)
    if path is None:
        return None
    return Sticker(index, path, *common)


def new_shape(shape: str, cx: float, cy: float) -> dict:
    """A plain shape (an empty text box with a fill and a border), to type in if wished."""
    return clean_sticker({"kind": "text", "text": "", "shape": shape, "cx": cx, "cy": cy, "w": 180, "h": 120,
                          "fill": "#ffffff", "border": INK, "border_width": 2})


def new_text_box(cx: float, cy: float, text: str = "Type here", font: str = "") -> dict:
    return clean_sticker({"kind": "text", "text": text, "font": font, "cx": cx, "cy": cy, "w": 260, "h": 90,
                          "size": 24})


def new_sticker(picture: str, path: Path, cx: float, cy: float, longest: float = 300.0) -> dict:
    """A sticker for a picture just added: its own shape, its longer side `longest` (or the
    picture's own size when smaller)."""
    pw, ph = _picture_size(path)
    pw, ph = max(1, pw), max(1, ph)
    scale = min(1.0, longest / max(pw, ph))
    return clean_sticker({"picture": picture, "cx": cx, "cy": cy, "w": max(STICKER_MIN, pw * scale),
                          "h": max(STICKER_MIN, ph * scale)})


def _node(lay: Layout, p: gen.Person, present: dict, add) -> None:
    x, y = lay.x[p.id], lay.y[p.id]
    colour = lay.birth_colour.get(p.id, GREY)
    ink = lay.portrait_ink
    kind = lay.shape(p)
    border = lay.border(p)
    mark = lay.mark(p)
    fx, fy, fw, fh, angle = lay.frame(p.id)
    see = lay.edits.mark_opacity / 100
    target = ("mark", lay.entry(p).get("mark"))
    if mark and lay.edits.mark_style == "glow":
        reach = lay.edits.mark_glow
        for k in range(GLOW_RINGS, 0, -1):     # outermost (faintest) first
            m = reach * (k - 0.5) / GLOW_RINGS
            add(Shape(kind, fx - m, fy - m, fw + 2 * m, fh + 2 * m, mark, width=2 * reach / GLOW_RINGS + 0.6, fill=None,
                      radius=corner_radius(kind) + m, pid=p.id, target=target, angle=angle,
                      opacity=see * (1 - (k - 1) / GLOW_RINGS) * 0.45))
    elif mark:
        m = MARK_GAP
        add(Shape(kind, fx - m, fy - m, fw + 2 * m, fh + 2 * m, mark, width=4, fill=None,
                  radius=corner_radius(kind) + m, pid=p.id, target=target, angle=angle, opacity=see))
    add(Shape(kind, fx, fy, fw, fh, colour, width=BORDER_WIDTHS[border], radius=corner_radius(kind),
              dash=border if border in ("dotted", "dashed", "dashdot") else "", pid=p.id,
              target=("person", p.id), fill=lay.edits.portrait_fill, angle=angle))
    # The face and words grow or shrink with a frame the player resized, about its middle, and
    # never turn (the owner: "shrink/grow with the frame, stay upright").
    w0, h0 = frame_size(lay.edits, lay.village, p, own=False)
    scale = max(0.2, min(4.0, fw / w0, fh / h0)) if (fw, fh) != (w0, h0) else 1.0
    middle = (x + NODE_W / 2, y + NODE_H / 2)

    def put(item) -> None:
        if scale != 1.0:
            item.x = middle[0] + (item.x - middle[0]) * scale
            item.y = middle[1] + (item.y - middle[1]) * scale
            if isinstance(item, Head):
                item.scale = scale
            elif isinstance(item, Text):
                item.size *= scale
            else:
                item.w, item.h = item.w * scale, item.h * scale
        add(item)

    if p.upcoming:
        for k, text in enumerate(node_text(lay, p)):
            put(Text(x + NODE_W / 2, y + NODE_H / 2 + 4 + k * 15, text, 12 if k == 0 else 11, ink,
                     bold=k == 0, centre=True, pid=p.id, role="names" if k == 0 else "portraits",
                     edit=f"person:{p.id}"))
        return
    sheet = sheet_name(lay.village.game, p)
    box = face_box(present, sheet, p.head)
    head_left, head_top, text_top, lines = placement(lay, p, box)
    if sheet in present and p.head is not None and p.head >= 0:
        put(Head(x + head_left, y + head_top, sheet, p.head, pid=p.id))
    else:
        mid = y + head_top + FACE_H * HEAD_SCALE / 2
        put(Shape("ellipse", x + NODE_W / 2 - 26, mid - 26, 52, 52, colour, width=1, fill=colour, pid=p.id,
                  target=("person", p.id)))
        put(Text(x + NODE_W / 2, mid + 10, p.name[:1], 28, "#ffffff", bold=True, centre=True, pid=p.id))
    for k, (text, bold) in enumerate(lines):
        put(Text(x + NODE_W / 2, y + text_top + k * LINE_H, text, 11.5 if bold else 10, ink,
                 bold=bold, centre=True, pid=p.id, role="names" if bold else "portraits", edit=f"person:{p.id}"))


def _svg_opacity(item) -> str:
    return f' opacity="{item.opacity:g}"' if item.opacity < 1 else ""


def gradient_stops(b: Backdrop) -> list[tuple[str, float]]:
    """A background gradient's colours and where each sits (0 the top or left, 1 the bottom or right)."""
    if b.colour2 in RAINBOWS:
        return [(c, k / (len(RAINBOW) - 1)) for k, c in enumerate(RAINBOW)]
    return [(b.colour, 0.0), (b.colour2, 1.0)]


def _svg_backdrop(b: Backdrop, sc: Scene) -> str:
    out = []
    if b.colour2:
        stops = gradient_stops(b)
        end = 'x2="1" y2="0"' if RAINBOWS.get(b.colour2) == "across" else 'x2="0" y2="1"'
        out.append(f'<defs><linearGradient id="bg" x1="0" y1="0" {end}>'
                   + "".join(f'<stop offset="{at:g}" stop-color="{c}"/>' for c, at in stops)
                   + '</linearGradient></defs><rect width="100%" height="100%" fill="url(#bg)"/>')
    if b.picture is not None:
        href = _href(b.picture)
        if b.fit == "tile":
            w, h = _picture_size(b.picture)
            out.append(f'<defs><pattern id="tile" width="{w}" height="{h}" patternUnits="userSpaceOnUse">'
                       f'<image width="{w}" height="{h}" href="{href}"/></pattern></defs>'
                       f'<rect width="100%" height="100%" fill="url(#tile)"/>')
        else:
            aspect = {"stretch": "none", "cover": "xMidYMid slice"}.get(b.fit, "xMidYMid meet")
            out.append(f'<image width="{sc.width:.0f}" height="{sc.height:.0f}" preserveAspectRatio="{aspect}" '
                       f'href="{href}"/>')
        if b.soften:
            out[-1] = out[-1].replace("<image ", f'<image opacity="{1 - b.soften / 100:.2f}" ', 1)
    return "".join(out)


def _href(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    kind = "jpeg" if suffix in ("jpg", "jpeg") else suffix
    return f"data:image/{kind};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _svg_sticker(s: Sticker) -> str:
    fx, fy = (-1 if s.flip_h else 1), (-1 if s.flip_v else 1)
    fade = f' opacity="{s.opacity:.3f}"' if s.opacity < 1 else ""
    head = f'<g transform="translate({s.cx:.1f} {s.cy:.1f}) rotate({s.angle:.2f}) scale({fx} {fy})"{fade}>'
    x, y = -s.w / 2, -s.h / 2
    if s.picture is not None:
        return (f'{head}<image x="{x:.1f}" y="{y:.1f}" width="{s.w:.1f}" height="{s.h:.1f}" '
                f'preserveAspectRatio="none" href="{_href(s.picture)}"/></g>')
    out = [head]
    box = (f'<ellipse cx="0" cy="0" rx="{s.w / 2:.1f}" ry="{s.h / 2:.1f}"' if s.shape == "ellipse"
           else f'<rect x="{x:.1f}" y="{y:.1f}" width="{s.w:.1f}" height="{s.h:.1f}"')
    if s.fill:
        out.append(f'{box} fill="{s.fill}" fill-opacity="{s.fill_opacity / 100:.3f}"/>')
    if s.border and s.border_width > 0:
        out.append(f'{box} fill="none" stroke="{s.border}" stroke-width="{s.border_width:g}"/>')
    pad = s.border_width + 4 if s.border else 4
    css = (f"box-sizing:border-box;width:100%;height:100%;padding:{pad:g}px;display:flex;flex-direction:column;"
           f"justify-content:{ {'top': 'flex-start', 'middle': 'center', 'bottom': 'flex-end'}[s.valign] };"
           f"text-align:{ {'left': 'left', 'centre': 'center', 'right': 'right'}[s.align] };"
           f"font-family:'{html.escape(s.font or 'Segoe UI')}', 'Segoe UI', Arial, sans-serif;font-size:{s.size:g}px;"
           f"color:{s.colour};white-space:pre-wrap;overflow-wrap:anywhere;overflow:hidden;line-height:1.2;"
           + ("font-weight:bold;" if s.bold else "") + ("font-style:italic;" if s.italic else "")
           + (f"text-decoration:{' '.join(d for d, on in (('underline', s.underline), ('line-through', s.strike)) if on)};"
              if s.underline or s.strike else ""))
    out.append(f'<foreignObject x="{x:.1f}" y="{y:.1f}" width="{s.w:.1f}" height="{s.h:.1f}">'
               f'<div xmlns="http://www.w3.org/1999/xhtml" style="{css}"><div>{html.escape(s.text)}</div></div>'
               f'</foreignObject></g>')
    return "".join(out)


def _picture_size(path: Path) -> tuple[int, int]:
    """A PNG's or JPEG's width and height, read from its header."""
    data = Path(path).read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:4] in (b"GIF8",):
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"BM":
        w, h = struct.unpack("<ii", data[18:26])
        return w, abs(h)
    at = 2
    while at < len(data) - 9:
        if data[at] != 0xFF:
            at += 1
            continue
        marker = data[at + 1]
        length = struct.unpack(">H", data[at + 2:at + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[at + 5:at + 9])
            return w, h
        at += 2 + length
    return 800, 600


def to_svg(sc: Scene, present: dict, describe=None) -> str:
    """The scene as SVG, the head sheets embedded once each."""
    e = html.escape
    ids = {name: f"sheet{k}" for k, name in enumerate(present)}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{sc.width:.0f}" height="{sc.height:.0f}" '
           f'viewBox="0 0 {sc.width:.0f} {sc.height:.0f}" font-family="Segoe UI, Arial, sans-serif">',
           f'<rect width="100%" height="100%" fill="{sc.background}"/>', "<defs>"]
    for name, path in present.items():
        w, h = _png_size(path)
        data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        out.append(f'<image id="{ids[name]}" width="{w}" height="{h}" '
                   f'style="image-rendering:pixelated" href="data:image/png;base64,{data}"/>')
    out.append("</defs>")
    hw, hh = HEAD_W * HEAD_SCALE, HEAD_H * HEAD_SCALE
    for item in sc.items:
        if isinstance(item, Backdrop):
            out.append(_svg_backdrop(item, sc))
        elif isinstance(item, Line):
            pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in item.points)
            out.append(f'<polyline points="{pts}" fill="none" stroke="{item.colour}" stroke-width="{item.width}"'
                       f' stroke-linejoin="round"{_svg_opacity(item)}'
                       + (f' stroke-dasharray="{SVG_DASHES[item.dash]}"' if item.dash else "") + "/>")
        elif isinstance(item, Shape):
            fill = item.fill or "none"
            dash = f' stroke-dasharray="{SVG_DASHES[item.dash]}"' if item.dash else ""
            dash += f' opacity="{item.opacity}"' if item.opacity < 1 else ""
            if item.angle:
                dash += f' transform="rotate({item.angle:g} {item.x + item.w / 2:.1f} {item.y + item.h / 2:.1f})"'
            common = f'fill="{fill}" stroke="{item.stroke}" stroke-width="{item.width}"{dash}'
            corners = outline(item.kind, item.x, item.y, item.w, item.h)
            if item.kind in ("ellipse", "circle"):
                ox, oy, ow, oh = oval_box(item.kind, item.x, item.y, item.w, item.h)
                out.append(f'<ellipse cx="{ox + ow / 2:.1f}" cy="{oy + oh / 2:.1f}" '
                           f'rx="{ow / 2:.1f}" ry="{oh / 2:.1f}" {common}/>')
            elif corners is not None:
                pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in corners)
                out.append(f'<polygon points="{pts}" {common}/>')
            else:
                out.append(f'<rect x="{item.x:.1f}" y="{item.y:.1f}" width="{item.w:.1f}" height="{item.h:.1f}" '
                           f'rx="{item.radius}" {common}/>')
        elif isinstance(item, Head):
            out.append(f'<svg x="{item.x:.1f}" y="{item.y:.1f}" width="{hw * item.scale:.1f}" '
                       f'height="{hh * item.scale:.1f}" '
                       f'viewBox="{HEAD_FRAME * HEAD_W} {item.row * HEAD_H} {HEAD_W} {HEAD_H}" '
                       f'style="image-rendering:pixelated"{_svg_opacity(item)}><use href="#{ids[item.sheet]}"/></svg>')
        elif isinstance(item, Sticker):
            out.append(_svg_sticker(item))
        elif isinstance(item, Text):
            weight = ' font-weight="bold"' if item.bold else ""
            weight += ' font-style="italic"' if item.italic else ""
            lines = " ".join(d for d, on in (("underline", item.underline), ("line-through", item.strike)) if on)
            weight += f' text-decoration="{lines}"' if lines else ""
            weight += f' font-family="{e(item.font)}, Segoe UI, Arial, sans-serif"' if item.font else ""
            anchor = ' text-anchor="middle"' if item.centre else ""
            out.append(f'<text x="{item.x:.1f}" y="{item.y:.1f}" font-size="{item.size}"{weight}{anchor} '
                       f'fill="{item.colour}"{_svg_opacity(item)}>{e(item.text)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def html_page(svg_text: str, title: str, report_text: str, background: str = BACKGROUND) -> str:
    e = html.escape
    return ("<!doctype html>\n<html><head><meta charset=\"utf-8\">"
            f"<title>{e(title)}</title>"
            "<style>body{margin:0;background:" + background + ";font-family:Segoe UI,Arial,sans-serif}"
            ".bar{position:sticky;top:0;background:#1d2a1d;color:#fff;padding:6px 12px;z-index:2}"
            ".bar button{margin-left:6px}#wrap{overflow:auto}"
            "pre{background:#fff;margin:12px;padding:12px;white-space:pre-wrap;font-size:13px}</style>"
            "</head><body>"
            f"<div class=\"bar\">{e(title)} <button onclick=\"zoom(1.25)\">Zoom in</button>"
            "<button onclick=\"zoom(0.8)\">Zoom out</button><button onclick=\"zoom(0)\">Fit</button></div>"
            f"<div id=\"wrap\">{svg_text}</div>"
            f"<h2 style=\"margin:12px\">The Genealogy report</h2><pre>{e(report_text)}</pre>"
            "<script>var p=[].slice.call(document.querySelectorAll('#wrap svg')),f=1,"
            "w=Math.max.apply(null,p.map(function(s){return +s.getAttribute('width')}));"
            "function zoom(k){f=k?f*k:Math.min(1,(innerWidth-20)/w);"
            "p.forEach(function(s){s.style.width=(+s.getAttribute('width')*f)+'px';s.style.height='auto'})}"
            "zoom(0)</script>"
            "</body></html>\n")


# ---------------------------------------------------------------------------
# Writing it all
# ---------------------------------------------------------------------------

@dataclass
class Written:
    report: Path
    page: Path
    picture: Path | None


def build(folder: Path, game: int, slot: int, edits: Edits | None = None) -> tuple[gen.Village, Edits, Layout]:
    """The village, its edits (the saved ones unless given) and its tree."""
    folder = Path(folder)
    village = gen.load_village(folder, game, slot)
    if edits is None:
        edits = Edits.load(Edits.path(folder, game, slot))
    arrange(village, edits)
    return village, edits, layout(village, edits)


def write(folder: Path, game: int, slot: int, images: Path | None, game_title: str,
          out: Path | None = None, edits: Edits | None = None, library: dict | None = None) -> Written:
    """The genealogy report, the tree's page and (on Windows) its picture, in the save folder's
    Virtual Villagers Fun Patcher Logs\\Genealogy (or `out`) -- each run replaces the slot's last
    ones.  Nothing else is written."""
    import vv_log_tools as tools
    import vv_gdiplus
    folder = Path(folder)
    village, edits, lay = build(folder, game, slot, edits)
    present = sheets_present(game, images)
    pages = [scene(layout(village, edits, k), game_title, present, images, library)     # as the player arranged it
             for k in range(lay.pages)]
    title = title_lines(replace(lay, pages=1), game_title)[0]
    arrange(village, Edits(sort=edits.sort))         # the report: the records' generations
    text = gen.report(village, game_title)
    out = Path(out) if out is not None else folder / tools.LOGS / "Genealogy"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"Virtual Villagers {game} Genealogy - Save {slot}"
    report_path = out / f"{stem}.txt"
    report_path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    page_path = out / f"{stem}.html"
    page_path.write_bytes(html_page("\n".join(to_svg(sc, present) for sc in pages), title, text,
                                    lay.background).encode("utf-8"))
    picture = out / f"{stem}.png"
    made = vv_gdiplus.save_scene(pages[0], present, picture)
    for k, sc in enumerate(pages[1:], 2):        # the later pages beside the first
        vv_gdiplus.save_scene(sc, present, out / f"{stem} - Page {k}.png")
    for old in out.glob(f"{stem} - Page *.png"):  # pages an earlier, longer tree had
        number = old.stem.rpartition(" ")[2]
        if number.isdigit() and int(number) > len(pages):
            old.unlink(missing_ok=True)
    return Written(report_path, page_path, picture if made else None)


def write_pairs(folder: Path, game: int, slot: int, rules: gen.Rules, game_title: str,
                out: Path | None = None) -> tuple[Path, str]:
    """The pairing suggestions report, numbered as the family tree is (the tree's sort), in the save
    folder's own Family Trees folder beside the tree files (the owner) -- or `out`.  Nothing else is
    written."""
    folder = Path(folder)
    village = gen.load_village(folder, game, slot)
    arrange(village, Edits.load(Edits.path(folder, game, slot)))
    text = gen.pair_report(village, rules, game_title)
    out = Path(out) if out is not None else folder / TREES
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"Virtual Villagers {game} Village Matchmaker - Save {slot}.txt"
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    return path, text
