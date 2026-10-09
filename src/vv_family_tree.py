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
* Villagers with no recorded parent or child sit apart, under "Other Members", level with their
  generation.
* The player's marks and edits (the owner: "mark special villagers with a border (any color) with a
  matching key", "make all the fields editable in case there are errors or the player wants to
  type something in a portrait"): every entry's lines, the title and the generation labels may be
  replaced, and any villager may carry a mark of the player's own -- a label and a colour -- drawn
  as a second border, every mark listed in the Key.  They are kept in the save folder's
  Virtual Villagers Fun Patcher Data\\Family Tree Edits, by villager (name, head and body), so a new tree
  keeps them.

The page is HTML with the tree in SVG; the picture (PNG or JPG) is drawn with Windows' own GDI+
(src/vv_gdiplus.py): nothing to install.
"""
from __future__ import annotations

import base64
import html
import json
import functools
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
GAP_MIN, GAP_MAX = 0.0, 400.0           # the player's gap between portraits
TEXT_ALIGNS = {"left": "Left", "centre": "Centre", "right": "Right"}
# The special borders' colours: natural (rope-coloured rope, green vines and leaves, red hibiscus), the
# flowers in a rainbow round the border, the player's own colour for each part, or the player's 2-7
# colours by turns or blending round the border -- always shaded and outlined from each colour.
SPECIAL_COLOUR_MODES = {"natural": "Natural", "rainbow": "Rainbow flowers", "pick": "Pick colours",
                        "alternate": "Alternating colours", "gradient": "Gradient"}
SPECIAL_PARTS = {"rope": "Rope", "vine": "Vine", "leaf": "Leaves", "flower": "Flowers"}
NATURAL = {"rope": "#c9a06a", "vine": "#5b8a35", "leaf": "#6aa83e", "flower": "#e8335a"}
RAINBOW = ("#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#3949ab", "#8e24aa", "#ec407a")
STAMEN = "#f2c230"
# How deep the rainbow is (the owner, 2026-10-09, choosing "15% deeper" for the rope and the flowers alike,
# and as the default): (words, how much of the pure colour is kept).
RAINBOW_STRENGTHS = {"bright": ("Bright", 1.0), "medium": ("Medium", 0.85), "deep": ("Deep", 0.75)}
# Colour schemes for the tree's other parts (the owner, 2026-10-09: rainbow and alternating colours "for
# special marks, plain portrait borders, portrait insides, family lines, detail lines"): as set, a rainbow
# (at the Rainbow strength), or the special borders' 2-7 colours by turns.  Borders and marks run round
# each outline; insides across the tree, villager by villager; family lines family by family; detail
# lines line by line.
COLOUR_SCHEMES = {"own": "Normal", "rainbow": "Rainbow", "alternate": "Alternating colours"}
SCHEME_PARTS = {"borders": "Portrait borders", "marks": "Special marks", "insides": "Portrait insides",
                "details": "Detail lines", "lines": "Family lines"}
# Natural hibiscus colours (the owner, 2026-10-09): each its petals and its darker "eye" in the middle,
# as the flowers grow; or all of them taking turns, or blending from one to the next, round the border
# (in HIBISCUS_ORDER).
HIBISCUS = {"red": ("Red", "#e8335a", "#8c1030"), "pink": ("Pink", "#f48fb6", "#b0124f"),
            "yellow": ("Yellow", "#f7cf3a", "#b3122e"), "orange": ("Orange", "#f5892c", "#a3121f"),
            "white": ("White", "#f8f4ec", "#c2185b"), "purple": ("Purple", "#a86ad0", "#4a1466")}
HIBISCUS_CHOICES = {**{k: v[0] for k, v in HIBISCUS.items()}, "alternate": "Alternating natural colours",
                    "gradient": "Gradient natural colours"}
HIBISCUS_ORDER = ("red", "orange", "yellow", "white", "pink", "purple")


def _colour_ok(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) is not None


def _mix(a: str, b: str, f: float) -> str:
    """`a` f of the way to `b`."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * f) for x, y in zip(ca, cb))


def _shade(colour: str, f: float) -> str:
    """Darker (f < 1, towards black) or lighter (f > 1, towards white)."""
    return _mix(colour, "#000000", 1 - f) if f <= 1 else _mix(colour, "#ffffff", f - 1)


def _blend_round(colours: list, t: float) -> str:
    """The colour `t` (0-1) of the way round a closed border blending through `colours` and back."""
    n = len(colours)
    x = (t % 1.0) * n
    i = int(x)
    return _mix(colours[i % n], colours[(i + 1) % n], x - i)
TEXT_ROOMS = {"auto": "Automatic", "shape": "Follow the shape", "rect": "Rectangle", "oval": "Oval"}
TEXT_VALIGNS = {"top": "Top", "middle": "Middle", "bottom": "Bottom"}
ROW_GAP_MIN, ROW_GAP_MAX = 0.0, 400.0   # the player's room under each generation's row (Edits.row_gap)
FIT_MIN, FIT_MAX = 400, 100000          # the page width portraits shrink to fit
SHRINK_MIN = 0.2                        # never smaller than a fifth
PAGE_GENS, PAGE_GENS_MIN, PAGE_GENS_MAX = 6, 2, 10   # generations on one page: the owner's default and limit
TEXT_SCALE_MIN, TEXT_SCALE_MAX = 25.0, 400.0          # one villager's text size, in percent
# The picture (the face) and the words inside a portrait, apart from the shape (the owner, 2026-10-09: "i
# want to be able to resize the villager's picture and text within the shape"): in percent, for every
# portrait (Edits.picture_size, Edits.text_size) and for one villager (entry "picture_scale", "text_scale").
PICTURE_SCALE_MIN, PICTURE_SCALE_MAX = 25.0, 400.0
# Each generation's row on the tree (the owner, 2026-10-09: "justify portraits ... top middle bottom ...
# left right center"; then: "Line up each row"): the row across the tree, and the portraits in it, of
# different sizes, lined up by their tops, middles or bottoms.
ROW_ALIGNS = {"arranged": "As arranged", "left": "Left", "centre": "Centre", "right": "Right"}
ROW_VALIGNS = {"middle": "Middles", "top": "Tops", "bottom": "Bottoms"}
LEFT = 300                      # the generation labels' column
TOP = 150
OTHER_GAP = 110                 # between the tree and the "Other Members" column

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
    centre_heads: bool = True           # the head and its lines in the middle of the frame (text_valign "middle")
    # The owner, 2026-10-09: "justify text (left right center + top middle bottom)": the portrait's words
    # across (TEXT_ALIGNS) and the face and words together up and down (TEXT_VALIGNS).
    text_align: str = "centre"
    # The owner, 2026-10-09: "a toggle for the text to fit within the portrait shape's space (in things
    # like crosses and x's it runs off)": the words only as wide as the shape is where each line is.
    text_inside: bool = False
    # Whether a turned portrait's words turn with it (the owner, 2026-10-09); off, they stay upright.
    turn_words: bool = False
    # Whether a flipped portrait's words are mirrored with it (the owner, 2026-10-09: "if people want to
    # mirror their text or anything be my guest"); off, they read as usual.
    flip_words: bool = False
    # Where a portrait's words are fitted (the owner, 2026-10-09: "for the more abstract shapes, the
    # auto-generated text boxes should just be a rectangle/oval ... Should be player-selected"): TEXT_ROOMS.
    text_room: str = "auto"
    # The special borders' colours (the owner, 2026-10-09): SPECIAL_COLOUR_MODES; the colours picked for
    # each part ("rope", "vine", "leaf", "flower"); the 7 colours of a palette, of which the first
    # special_count (2-7) are used, by turns or as a gradient.
    special_mode: str = "natural"
    special_pick: dict = field(default_factory=dict)
    special_palette: list = field(default_factory=lambda: list(RAINBOW[:7]))
    special_count: int = 3
    hibiscus: str = "red"               # natural flowers' colour (HIBISCUS_CHOICES)
    special_opacity: float = 100.0      # the special borders' opacity, percent (the owner, 2026-10-09)
    rainbow_strength: str = "medium"    # RAINBOW_STRENGTHS
    schemes: dict = field(default_factory=dict)   # SCHEME_PARTS -> COLOUR_SCHEMES ("own" when absent)
    # The light lines inside a shape (details(): a scallop's ribs, a snail's whorls, a star's points),
    # the owner, 2026-10-09: "with the ability to edit the detailing's color, opacity, line weight".
    detail_lines: bool = True
    detail_colour: str = ""             # "" the portrait's own colour
    detail_opacity: float = 45.0        # percent
    detail_width: float = 1.0
    text_valign: str = "middle"
    row_align: str = "arranged"        # each row across the tree (ROW_ALIGNS)
    row_valign: str = "middle"         # the portraits in a row lined up by (ROW_VALIGNS)
    picture_size: float = 100.0        # every portrait's face, percent (PICTURE_SCALE_MIN..MAX)
    text_size: float = 100.0           # every portrait's words, percent (TEXT_SCALE_MIN..MAX)
    text_wrap: int = 17                 # characters across a portrait before a line wraps (the owner: adjustable)
    portrait_gap: float = 22.0          # pixels between two portraits side by side (the owner: batch-editable)
    row_gap: float = 30.0               # pixels under a generation's row before its children's lines (LANE_TOP)
    show_founder: bool = False          # "Founder" in each generation I portrait (the owner, 2026-10-09)
    fit_width: int = 0                  # 0, or shrink every portrait so the widest row fits this many pixels
    page_generations: int = 6           # the most generations on one page (the owner: 6, up to 10)
    diagonal_lines: bool = False        # a dragged line piece may move any way (else only across itself)
    show_units: bool = True             # "<age> game units" in the portraits
    show_years: bool = True             # "<years> years old" in the portraits
    show_twins: bool = False            # "<name>'s twin" / "<name> and <name>'s triplet" after the age
    number_names: bool = False          # villagers who share a name numbered: "Soda I", "Soda II"...
    number_order: str = "appearance"    # vv_genealogy.NUMBER_ORDERS: who is "I" (the owner's default)
    sort: str = "appearance"            # vv_genealogy.SORTS
    positioning: str = "dynamic"        # POSITIONING
    numbering: str = "roman"            # NUMBERINGS: the generations' numbers
    background: str = "#ffffff"         # "#rrggbb" or TRANSPARENT; white until the player says (the owner, 2026-10-08: "to prevent stupid mistakes"); blank the patcher's own
    background2: str = ""               # a gradient's lower colour ("" none)
    rainbow: str = ""                   # a RAINBOWS key instead of that gradient ("" none)
    background_image: str = ""          # a picture file, or "game:<name>" in the game's Images
    background_fit: str = "stretch"     # FITS (the owner's default: "stretch to the page")
    background_opacity: int = 100       # 0-100: how strongly the picture shows over the colour (the owner, 2026-10-08: not see-through unless asked)
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
    # entry key -> {"lines", "runs" (those lines formatted word by word: clean_runs), "mark", ...}
    entries: dict[str, dict] = field(default_factory=dict)
    # Stickers (the owner: "any image file on the computer where people can drag and place them
    # like a scrapbook", "resize, rotate, transform"): pictures on top of the tree, bottom one first.
    stickers: list[dict] = field(default_factory=list)

    @staticmethod
    def path(folder: Path, game: int, slot: int) -> Path:
        # "Data\Family Tree Edits\... Family Tree Edits - Save N.json"; "Genealogy" / "Genealogy Edits"
        # in older builds, used there until the save folder's files take their new names.
        import vv_save_layout as save_layout
        return save_layout.find(folder, f"{save_layout.DATA}\\{save_layout.TREE_EDITS}\\"
                                        f"Virtual Villagers {game} Family Tree Edits - Save {slot}.json")

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
        out.text_inside = data.get("text_inside") is True
        out.turn_words = data.get("turn_words") is True
        out.flip_words = data.get("flip_words") is True
        mode = data.get("special_mode")
        out.special_mode = mode if mode in SPECIAL_COLOUR_MODES else "natural"
        pick = data.get("special_pick")
        out.special_pick = {k: v for k, v in pick.items() if k in SPECIAL_PARTS and _colour_ok(v)} \
            if isinstance(pick, dict) else {}
        palette = data.get("special_palette")
        if isinstance(palette, list) and len(palette) == 7 and all(_colour_ok(c) for c in palette):
            out.special_palette = list(palette)
        out.special_count = int(_number(data.get("special_count"), 2, 7, 3))
        chosen = "alternate" if data.get("hibiscus") == "random" else data.get("hibiscus")   # "random", before
        out.hibiscus = chosen if chosen in HIBISCUS_CHOICES else "red"
        out.special_opacity = float(_number(data.get("special_opacity"), 0, 100, 100.0))
        strength = data.get("rainbow_strength")
        out.rainbow_strength = strength if strength in RAINBOW_STRENGTHS else "medium"
        schemes = data.get("schemes")
        out.schemes = ({k: v for k, v in schemes.items() if k in SCHEME_PARTS and v in COLOUR_SCHEMES and v != "own"}
                       if isinstance(schemes, dict) else {})
        room = data.get("text_room")
        out.text_room = room if room in TEXT_ROOMS else "auto"
        out.detail_lines = data.get("detail_lines", True) is not False
        colour = data.get("detail_colour")
        out.detail_colour = colour if isinstance(colour, str) and (colour == "" or re.fullmatch(r"#[0-9a-fA-F]{6}", colour)) else ""
        out.detail_opacity = float(_number(data.get("detail_opacity"), 0, 100, 45.0))
        out.detail_width = float(_number(data.get("detail_width"), *LINE_WIDTHS, 1.0))
        align = data.get("text_align")
        out.text_align = align if align in TEXT_ALIGNS else "centre"
        valign = data.get("text_valign")
        out.text_valign = valign if valign in TEXT_VALIGNS else ("middle" if out.centre_heads else "top")
        out.centre_heads = out.text_valign == "middle"     # what an older build reads
        out.diagonal_lines = data.get("diagonal_lines") is True
        out.text_wrap = int(_number(data.get("text_wrap"), WRAP_MIN, WRAP_MAX, WRAP))
        out.row_align = data.get("row_align") if data.get("row_align") in ROW_ALIGNS else "arranged"
        out.row_valign = data.get("row_valign") if data.get("row_valign") in ROW_VALIGNS else "middle"
        out.picture_size = _number(data.get("picture_size"), PICTURE_SCALE_MIN, PICTURE_SCALE_MAX, 100.0)
        out.text_size = _number(data.get("text_size"), TEXT_SCALE_MIN, TEXT_SCALE_MAX, 100.0)
        out.portrait_gap = float(_number(data.get("portrait_gap"), GAP_MIN, GAP_MAX, GAP_X))
        out.row_gap = float(_number(data.get("row_gap"), ROW_GAP_MIN, ROW_GAP_MAX, LANE_TOP))
        out.show_founder = data.get("show_founder", False) is True
        out.page_generations = int(_number(data.get("page_generations"), PAGE_GENS_MIN, PAGE_GENS_MAX, PAGE_GENS))
        fit = data.get("fit_width")
        out.fit_width = int(_number(fit, FIT_MIN, FIT_MAX, 0)) if isinstance(fit, (int, float)) and fit else 0
        out.show_units = data.get("show_units", True) is not False
        out.show_years = data.get("show_years", True) is not False
        out.show_twins = data.get("show_twins", False) is True
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
                runs = runs_data(clean_runs(entry.get("runs"), item["lines"]))
                if runs:
                    item["runs"] = runs
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
            if is_colour(entry.get("fill")):            # this portrait's own inside colour (the owner, 2026-10-09)
                item["fill"] = entry["fill"]
            if is_colour(entry.get("detail")):          # and its own detail lines' colour
                item["detail"] = entry["detail"]
            for flip in ("flip_h", "flip_v"):            # the portrait's shape mirrored (the owner, 2026-10-09)
                if entry.get(flip) is True:
                    item[flip] = True
            text_scale = _number(entry.get("text_scale"), TEXT_SCALE_MIN, TEXT_SCALE_MAX, 100.0)
            if text_scale != 100.0:
                item["text_scale"] = text_scale     # this villager's words, apart from the frame (the owner)
            picture_scale = _number(entry.get("picture_scale"), PICTURE_SCALE_MIN, PICTURE_SCALE_MAX, 100.0)
            if picture_scale != 100.0:
                item["picture_scale"] = picture_scale   # and their face (the owner, 2026-10-09)
            look = entry.get("look")
            if isinstance(look, list) and len(look) == 2 and all(isinstance(v, int) for v in look):
                item["look"] = look             # the look the player chose to show
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
                "centre_heads": self.text_valign == "middle", "text_align": self.text_align, "text_inside": self.text_inside, "turn_words": self.turn_words, "flip_words": self.flip_words, "text_room": self.text_room, "special_mode": self.special_mode, "special_pick": self.special_pick, "special_palette": self.special_palette, "special_count": self.special_count, "hibiscus": self.hibiscus, "special_opacity": self.special_opacity, "rainbow_strength": self.rainbow_strength, "schemes": self.schemes, "detail_lines": self.detail_lines, "detail_colour": self.detail_colour, "detail_opacity": self.detail_opacity, "detail_width": self.detail_width, "text_valign": self.text_valign, "text_wrap": self.text_wrap, "row_align": self.row_align, "row_valign": self.row_valign, "picture_size": self.picture_size, "text_size": self.text_size, "portrait_gap": self.portrait_gap, "row_gap": self.row_gap, "show_founder": self.show_founder, "fit_width": self.fit_width, "page_generations": self.page_generations, "diagonal_lines": self.diagonal_lines,
                "show_units": self.show_units, "show_years": self.show_years, "show_twins": self.show_twins, "number_names": self.number_names,
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




def alphabetical(names) -> list[str]:
    """Choices in a list by name, A to Z (the owner, 2026-10-09: "alphabetize the options"); the
    special borders after the plain ones, themselves A to Z."""
    names = list(names)
    plain = sorted((n for n in names if not n.startswith("Special: ")), key=str.casefold)
    return plain + sorted((n for n in names if n.startswith("Special: ")), key=str.casefold)


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
    "others": "Other Members heading",
    "footer": "Footer",
}
ALIGNS = {"left": "Left", "centre": "Centre", "right": "Right"}
# A portrait's shape and border (the owner's lists).
PORTRAIT_SHAPES = {"rectangle": "Rectangle", "rounded_rect": "Rounded rectangle", "rect": "Square",
                   "rounded": "Rounded square", "circle": "Circle", "ellipse": "Oval",
                   "oval_wide": "Oval (horizontal)",
                   "heart": "Heart", "triangle": "Triangle", "diamond": "Diamond", "cross": "Cross", "x": "X",
                   "plus": "Plus", "star": "Star", "hexagon": "Hexagon", "octagon": "Octagon", "trapezoid": "Trapezoid", "pentagon": "Pentagon",
                   "star4": "4-pointed star", "plump_star": "Plump star", "star6": "6-pointed star",
                   "slim_star6": "Slim 6-pointed star", "arrow_h": "Arrow (horizontal)", "arrow_v": "Arrow (vertical)",
                   "arch": "Arch", "scallop": "Scallop shell", "snail": "Snail shell",
                   "hibiscus": "Hibiscus", "sand_dollar": "Sand dollar", "turtle_v": "Turtle shell (upright)",
                   "turtle_h": "Turtle shell (on its side)", "mermaid_tail": "Mermaid tail (upright)",
                   "mermaid_tail_h": "Mermaid tail (on its side)",
                   "fish_right": "Fish (facing right)", "fish_left": "Fish (facing left)",
                   "wave_circle": "Ocean wave in a circle", "conch": "Conch shell", "starfish": "Starfish", "monstera": "Monstera leaf",
                   "ship_wheel": "Ship's wheel", "coconut": "Coconut", "anchor": "Anchor", "bananas": "Bunch of bananas",
                   "flower": "Flower", "butterfly": "Butterfly", "clover": "Clover", "spade": "Spade", "leaf": "Leaf"}
BORDERS = {"thin": "Thin line", "thick": "Thick line", "extra": "Extra thick line", "dotted": "Dotted",
           "dashed": "Dashed",
           "dashdot": "Dotted and dashed"}
BORDER_WIDTHS = {"thin": 1.5, "thick": 3.0, "extra": 6.0, "dotted": 2.5, "dashed": 2.5, "dashdot": 2.5}
# A special border (the owner, 2026-10-09): a braided rope round the portrait's own shape, whatever
# the shape (special_border).  The stone tablets tried beside it were taken out at the owner's word.
SPECIAL_BORDERS = {"rope": "Special: Braided rope", "vine_leaves": "Special: Vine with leaves",
                   "vine_flowers": "Special: Vine with hibiscus",
                   "vine_both": "Special: Vine with leaves and hibiscus"}
BORDERS.update(SPECIAL_BORDERS)
BORDER_WIDTHS.update({name: 1.5 for name in SPECIAL_BORDERS})
BORDER_WIDTHS.update({name: 0.0 for name in SPECIAL_BORDERS})     # the rope or the vine is the edge
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


# A portrait's own text formatted word by word (the owner: "please allow text formatting in the family
# tree portrait text section" -- select words, then format them): each of the entry's lines is kept as
# runs, [text, style], the style any of RUN_STYLE's keys.  A run's style beats its role's (the names'
# and the other portrait words'); what it leaves out is the role's.  "normal" script undoes a role's
# superscript or subscript for that run.
RUN_FLAGS = ("bold", "italic", "underline", "strike")
RUN_SCRIPTS = ("super", "sub", "normal")


def clean_run_style(raw) -> dict:
    """A run's style, every value in range: only what the player set."""
    if not isinstance(raw, dict):
        return {}
    out = {flag: raw[flag] for flag in RUN_FLAGS if isinstance(raw.get(flag), bool)}
    if raw.get("script") in RUN_SCRIPTS:
        out["script"] = raw["script"]
    if is_colour(raw.get("colour")) and raw["colour"] != TRANSPARENT:
        out["colour"] = raw["colour"].lower()
    return out


def merge_runs(runs) -> list[tuple[str, dict]]:
    """One line's runs with the empty ones dropped and neighbours of one style joined."""
    out: list[tuple[str, dict]] = []
    for text, style in runs:
        if not text:
            continue
        if out and out[-1][1] == style:
            out[-1] = (out[-1][0] + text, style)
        else:
            out.append((text, dict(style)))
    return out


def clean_runs(raw, lines: list[str]) -> list[list[tuple[str, dict]]] | None:
    """The saved runs of an entry's lines, checked: one list of [text, style] per line, their words
    exactly the line's.  None when there are none, none of them is formatted, or they do not match
    the lines (an older patcher retyped the lines and kept the runs: the words win, unformatted)."""
    if not isinstance(raw, list) or len(raw) != len(lines):
        return None
    out = []
    for line, runs in zip(lines, raw):
        if not isinstance(runs, list):
            return None
        pairs = []
        for run in runs:
            if not (isinstance(run, (list, tuple)) and len(run) == 2 and isinstance(run[0], str)):
                return None
            pairs.append((run[0], clean_run_style(run[1])))
        if "".join(text for text, _s in pairs) != line:
            return None
        out.append(merge_runs(pairs))
    return out if any(style for runs in out for _t, style in runs) else None


def runs_data(runs: list[list[tuple[str, dict]]] | None) -> list | None:
    """The runs as the edits file keeps them (lists, for JSON)."""
    return None if not runs else [[[text, dict(style)] for text, style in line] for line in runs]


def carry_styles(old_lines: list[str], old_runs, new_lines: list[str]) -> list | None:
    """The formatting of `old_lines` carried onto their retyped words (clicking the words on the
    tree and retyping them, or renumbering): every character the retyping kept keeps its style, and
    a typed one takes the style of the one before it.  The runs in their saved form, or None."""
    import difflib
    if not old_runs:
        return None
    old_text = "\n".join(old_lines)
    # The old characters' styles in order, a newline between lines unstyled.
    styles: list[dict] = []
    for k, line in enumerate(old_runs):
        if k:
            styles.append({})
        styles.extend(style for text, style in line for _ch in text)
    new_text = "\n".join(new_lines)
    new_styles: list[dict] = [{}] * len(new_text)
    matcher = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            new_styles[j1:j2] = styles[i1:i2]
        else:
            before = new_styles[j1 - 1] if j1 > 0 and new_text[j1 - 1] != "\n" else (
                styles[i1] if i1 < len(styles) else {})
            new_styles[j1:j2] = [before] * (j2 - j1)
    out, at = [], 0
    for line in new_lines:
        out.append(merge_runs((ch, new_styles[at + k]) for k, ch in enumerate(line)))
        at += len(line) + 1
    return runs_data(out) if any(style for line in out for _t, style in line) else None


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


# The tree's look as a whole, which the Family Tree Maker remembers when it closes and gives a tree
# that has no edits of its own yet (the owner, 2026-10-08: "Save the player's settings on close and
# reopen (portrait shape/any other changes)").  Never a village's own things: its title, moved
# portraits, pages, words, families' colours, villagers' entries or stickers.
STYLE_KEYS = (
    "centre_heads", "text_align", "text_inside", "turn_words", "flip_words", "text_room", "special_mode", "special_pick", "special_palette",
    "special_count", "hibiscus", "special_opacity", "rainbow_strength", "schemes", "detail_lines", "detail_colour", "detail_opacity", "detail_width", "text_valign", "text_wrap", "row_align", "row_valign", "picture_size", "text_size", "portrait_gap", "row_gap", "show_founder", "fit_width", "page_generations", "diagonal_lines",
    "show_units", "show_years", "show_twins", "number_names", "number_order", "sort", "positioning", "numbering",
    "background", "background2", "rainbow", "background_image", "background_fit", "background_opacity",
    "ink", "font", "styles", "portrait_fill", "shapes", "borders", "plate_colour", "opacity", "sizes",
    "line_width", "line_dash", "mark_style", "mark_glow", "mark_opacity", "label_line_width",
    "label_line_reach", "marks",
)


def style_of(edits: "Edits") -> dict:
    """The look of `edits` (STYLE_KEYS), as the settings file keeps it."""
    data = edits.to_data()
    return {key: data[key] for key in STYLE_KEYS if key in data}


def styled(style: dict | None) -> "Edits":
    """A new tree's edits with a remembered look; the patcher's own where it has none or it does not
    read (an older or damaged settings file never stops the tree from opening)."""
    base = Edits().to_data()
    if isinstance(style, dict):
        base.update({key: value for key, value in style.items() if key in STYLE_KEYS})
    try:
        return Edits.from_data(base)
    except ValueError:
        return Edits()


def renamed_keys(text: str, renames: dict[tuple, str]) -> str:
    """Saved edits (an edits file or a .vvtree, as text) with each renamed villager's key --
    "<name>|<head>|<body>", in an entry, a family, an order, a line piece -- under their new name."""
    for (name, head, body), new in renames.items():
        key = json.dumps(new)[1:-1] + f"|{head}|{body}"
        text = re.sub(rf'(?<=["|: ]){re.escape(json.dumps(name)[1:-1])}\|{head}\|{body}(?=["| ])',
                      lambda _found, key=key: key, text)
    return _renamed_lines(text, renames)


def _name_pattern(name: str, numbered: bool = False) -> re.Pattern:
    """`name` as a whole name in a line of words: never inside a longer word, and never the start of
    a longer numbered name ("Iruwa Bahati I" is not in "Iruwa Bahati II").  `numbered`: with any
    Roman number after it too."""
    tail = r"(?: [IVXLCDM]+)?(?!\w)" if numbered else r"(?! [IVXLCDM]+(?!\w))(?!\w)"
    return re.compile(rf"(?<!\w){re.escape(name)}{tail}")


def _rename_in_lines(lines: list, runs, pattern: re.Pattern, new: str) -> tuple[list, object]:
    """The player's own lines (and their formatted runs) with the name the pattern finds put as `new`.
    A name the formatting splits across runs is renamed in the lines and the runs dropped for that
    line, so the words always win (clean_runs)."""
    out = [pattern.sub(new, line) if isinstance(line, str) else line for line in lines]
    if isinstance(runs, list) and len(runs) == len(lines):
        runs = [[[pattern.sub(new, r[0]), r[1]] if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str)
                 else r for r in line_runs] if isinstance(line_runs, list) else line_runs
                for line_runs in runs]
        runs = [line_runs if isinstance(line_runs, list) and isinstance(line, str)
                and "".join(r[0] for r in line_runs if isinstance(r, list) and r and isinstance(r[0], str)) == line
                else [[line, {}]] for line, line_runs in zip(out, runs)]
    return out, runs


def _renamed_lines(text: str, renames: dict[tuple, str]) -> str:
    """The edits (as text) with each renamed villager's name put right in the words the player typed
    for their portrait (the owner, 2026-10-08: "the family tree still carries the old names").  Only
    in that villager's own entry: two namesakes can be renamed apart."""
    try:
        data = json.loads(text)
    except ValueError:
        return text
    entries = data.get("entries") if isinstance(data.get("entries"), dict) else \
        (data.get("edits") or {}).get("entries") if isinstance(data.get("edits"), dict) else None
    if not isinstance(entries, dict):
        return text
    changed = False
    for (name, head, body), new in renames.items():
        entry = entries.get(f"{new}|{head}|{body}")
        if not isinstance(entry, dict) or not isinstance(entry.get("lines"), list) or name == new:
            continue
        lines, runs = _rename_in_lines(entry["lines"], entry.get("runs"), _name_pattern(name), new)
        if lines != entry["lines"] or runs != entry.get("runs"):
            entry["lines"] = lines
            if "runs" in entry:
                entry["runs"] = runs
            changed = True
    if not changed:
        return text
    # Written back as it was written: a .vvtree (indent 1), an edits file (indent 2), or one line.
    if not text.startswith("{\n"):
        return json.dumps(data)
    if text.startswith('{\n "'):
        return json.dumps(data, indent=1)
    return json.dumps(data, indent=2, ensure_ascii=False) + ("\n" if text.endswith("\n") else "")


def relooked_keys(text: str, relooked: dict[tuple, tuple]) -> str:
    """Saved edits (as text) with each key of a villager's old look -- before Change Appearance --
    moved to the look they have now, so their edits follow them (as renamed_keys for a new name)."""
    for (name, head, body), (_name, new_head, new_body) in relooked.items():
        old = re.escape(json.dumps(name)[1:-1]) + rf"\|{head}\|{body}"
        new = json.dumps(name)[1:-1] + f"|{new_head}|{new_body}"
        text = re.sub(rf'(?<=["|: ]){old}(?=["| ])', lambda _found, new=new: new, text)
    return text


def full_name_edits(edits: "Edits", village: gen.Village) -> "Edits":
    """The edits with each villager's key under a name the Villager Details screen cut moved to the
    full name the tree shows them by (vv_cut_names; the owner: "Family trees will use the full names
    from the logs"), so marks made while the tree showed the cut name follow them.  The same edits
    when nothing moves."""
    if not village.full_names:
        return edits
    text = json.dumps(edits.to_data())
    moved = renamed_keys(text, village.full_names)
    # Edits kept under both the cut key and the full one become one villager's: merged, never one
    # dropped for the other (review, 2026-10-07).
    return edits if moved == text else Edits.from_data(json.loads(moved, object_pairs_hook=_merge_pairs))


def _merge_pairs(pairs: list) -> dict:
    """A JSON object whose key repeats after re-keying: dictionaries merged (the first one's values
    kept where both have one), lists of names joined without repeats, any other value -- a [dx, dy]
    move among them -- the first one's (review, 2026-10-07)."""
    out: dict = {}
    for key, value in pairs:
        if key not in out:
            out[key] = value
        elif isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = {**value, **out[key]}
        elif (isinstance(out[key], list) and isinstance(value, list)
              and all(isinstance(v, str) for v in out[key] + value)):
            out[key] = out[key] + [v for v in value if v not in out[key]]
    return out


def look_of(edits: "Edits", village: gen.Village, p: gen.Person) -> tuple:
    """The (head, body) the tree shows: the one the player chose after Change Appearance, else now."""
    look = edits.entries.get(entry_key(village, p), {}).get("look")
    return tuple(look) if look else (p.head, p.body)


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
    shrink: float = 1.0                 # this page's Shrink to fit (each page its own; Codex, #575)
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
        """The portrait's shape, as drawn: mirrored when the player flipped it ("heart~h")."""
        entry = self.entry(p)
        return flipped_kind(shape_of(self.edits, self.village, p), entry.get("flip_h", False), entry.get("flip_v", False))

    def border(self, p: gen.Person) -> str:
        return self.entry(p).get("border") or self.edits.borders[group_of(p)]

    def frame(self, q: int) -> tuple[float, float, float, float, float]:
        """q's portrait frame (left, top, width, height, angle): its shape at the shape's own
        proportions, as tall as a portrait, unless the player resized it; centred on the portrait;
        turned `angle` degrees about its middle."""
        p = self.village.people[q]
        w, h = frame_size(self.edits, self.village, p, shrink=self.shrink)
        top = self.y[q] + NODE_H / 2 - h / 2
        if self.edits.row_valign != "middle":   # lined up with the tallest in their row (Edits.row_valign)
            tallest = self.row_heights().get(q, h)
            top += (h - tallest) / 2 if self.edits.row_valign == "top" else (tallest - h) / 2
        return self.x[q] + NODE_W / 2 - w / 2, top, w, h, self.entry(p).get("angle", 0.0)

    def row_heights(self) -> dict[int, float]:
        """Each portrait's row's tallest frame (worked out once: every frame asks).  A row: one
        generation of the tree, or of the Other Members."""
        heights = self.__dict__.get("_row_heights")
        if heights is None:
            tallest: dict[tuple, float] = {}
            rows = {}
            others = set(self.others)
            for q in self.x:
                p = self.village.people[q]
                rows[q] = (p.generation, q in others)
                h = frame_size(self.edits, self.village, p, shrink=self.shrink)[1]
                tallest[rows[q]] = max(tallest.get(rows[q], 0.0), h)
            heights = {q: tallest[row] for q, row in rows.items()}
            self.__dict__["_row_heights"] = heights
        return heights

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


def frame_size(edits: Edits, village: gen.Village, p: gen.Person, own: bool = True,
               unscaled: bool = False, shrink: float = 1.0) -> tuple[float, float]:
    """A portrait frame's width and height: the villager's own (`own`), else their group's default
    size, else their shape's own proportions, a portrait tall -- shrunk to fit the page when the
    player asked (Edits.fit_width; `unscaled`: the sizes as the player set them)."""
    gw, gh = edits.sizes.get(group_of(p)) or (natural_width(shape_of(edits, village, p)), NODE_H)
    entry = edits.entries.get(entry_key(village, p), {}) if own else {}
    s = 1.0 if unscaled else shrink
    return entry.get("w", gw) * s, entry.get("h", gh) * s


def keep_aspect(now: tuple[float, float], axis: int, value: float) -> tuple[float, float]:
    """`now` (width, height) with side `axis` (0 width, 1 height) made `value` and the other side
    following, so the shape keeps its proportions (Keep aspect ratio); the other side within
    FRAME_MIN..FRAME_MAX, rounded to a tenth."""
    w, h = now
    if w <= 0 or h <= 0:
        return (value, h) if axis == 0 else (w, value)
    # The proportions always kept: when the side that follows would pass a limit, it stops there and the
    # typed side gives way (the owner's "800" typed into a turtle shell's box: its "8" made it 8 by 8
    # before, a square for good).
    ratio = (h / w) if axis == 0 else (w / h)
    other = value * ratio
    if other < FRAME_MIN or other > FRAME_MAX:
        other = max(FRAME_MIN, min(FRAME_MAX, other))
        value = max(FRAME_MIN, min(FRAME_MAX, other / ratio))
    value, other = round(value, 1), round(other, 1)
    return (value, other) if axis == 0 else (other, value)


def page_spans(edits: Edits, village: gen.Village) -> list[tuple[int, int]]:
    """Each page's first and last generation (the generations as arrange gives them).  A page ends
    with the generation the next one starts at, and that page shows it again as its founders (the
    owner: "page 1 has generations 1-6.  The second page should have generations 6-12, with the 6th
    generation on the second page being treated as "founders" on the second page")."""
    gens = sorted({p.generation for p in village.people.values()}) or [1]
    starts = [gens[0]] + sorted({g for g in edits.pages if g in gens and g > gens[0]})   # Codex, #557
    spans = [(lo, starts[k + 1] if k + 1 < len(starts) else gens[-1]) for k, lo in enumerate(starts)]
    # No page holds more than the player's number of generations (the owner, 2026-10-08: 6 until they
    # say, 10 at most, so every page stays legible): a longer span goes on over the next pages, each
    # starting with the generation the one before ends with.
    most = edits.page_generations
    out = []
    for lo, hi in spans:
        while hi - lo + 1 > most:
            out.append((lo, lo + most - 1))
            lo += most - 1
        out.append((lo, hi))
    return out


def layout(village: gen.Village, edits: Edits | None = None, page: int = 0) -> Layout:
    """The page laid out.  With Shrink to fit (Edits.fit_width), the portraits shrink until the whole
    page -- the generation labels, the widest row and the Other Members -- fits that width, or until
    they are as small as they go (SHRINK_MIN)."""
    lay = _layout(village, edits, page)
    e = lay.edits
    if not e.fit_width:
        return lay
    for _ in range(8):
        if lay.width <= e.fit_width * 1.005 or lay.shrink <= SHRINK_MIN:
            break
        # What does not shrink (the labels' column and the margins) is left as it is.
        fixed = LEFT + 60
        wanted = lay.shrink * max(0.05, (e.fit_width - fixed) / max(1.0, lay.width - fixed))
        lay = _layout(village, edits, page, max(SHRINK_MIN, min(1.0, wanted)))
    return lay


def _layout(village: gen.Village, edits: Edits | None = None, page: int = 0,
            shrink: float | None = None) -> Layout:
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
    # Every portrait shrunk alike, faces and words with them, so the widest row fits the page width
    # the player chose (the owner, 2026-10-08: "auto resizing of portraits and text to accommodate
    # lots of portraits per page"); the gap between two portraits is the player's.
    shrink_now = 1.0
    shown = in_tree | set(others)
    widest_frame = max([NODE_W] + [frame_size(edits, village, people[q], own=False)[0] for q in shown])
    gap = edits.portrait_gap
    widest_row_n = max([len(r) for r in rows.values()] + [1])
    if shrink is not None:
        shrink_now = shrink
    elif edits.fit_width and LEFT + widest_row_n * (widest_frame + gap) > edits.fit_width:
        room = (edits.fit_width - LEFT) / widest_row_n - gap
        shrink_now = max(SHRINK_MIN, min(1.0, room / widest_frame))
    step = widest_frame * shrink_now + gap
    x: dict[int, float] = {}
    sub: dict[int, int] = {q: 0 for q in in_tree}
    if edits.positioning == "dynamic" and rows:
        x, sub = _dynamic(people, rows, families, step)
        # The right edge of the widest frame, not of a standard portrait: a wide shape (a butterfly) or
        # a big frame must not reach into the Other Members column.
        tree_right = max(x.values()) + NODE_W / 2 + max(NODE_W, step - gap) / 2
    else:
        # Every row centred under the widest (the owner: "center everything ... both
        # horizontally and vertically").
        widest_row = max((len(row) for row in rows.values()), default=1)
        for row in rows.values():
            indent = (widest_row - len(row)) * step / 2
            for i, pid in enumerate(row):
                x[pid] = LEFT + indent + i * step
        tree_right = LEFT + widest_row * step - gap
    if edits.row_align != "arranged" and rows:
        # Each row to the tree's left edge, its middle or its right edge (Edits.row_align); the player's
        # drags still count from there.
        left_edge = min(x[q] for row in rows.values() for q in row)
        right_edge = max(x[q] for row in rows.values() for q in row)
        for row in rows.values():
            lo, hi = min(x[q] for q in row), max(x[q] for q in row)
            shift = (left_edge - lo if edits.row_align == "left" else right_edge - hi if edits.row_align == "right"
                     else (left_edge + right_edge) / 2 - (lo + hi) / 2)
            for q in row:
                x[q] += shift
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
            # The room under the row above is the player's (Edits.row_gap: "vertical portrait clustering").
            top += (bands[gens[k - 1]] + edits.row_gap + couples * LANE + (BAND_GAP if couples else 0)
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
    out = Layout(village, rows, x, y, families, others, others_left, width, height, tops=tops, bands=bands, shrink=shrink_now,
                 edits=edits, page=page, pages=len(spans),
                 names=gen.duplicate_names(village, edits.number_order) if edits.number_names else {})
    # One colour each: every villager with no recorded parents, every pairing, every set of full
    # brothers and sisters -- oldest first, so the most distinct go to the founders.
    e = out.edits
    alone = sorted((q for q in x if all(r is None or r in off for r in (people[q].father, people[q].mother))),
                   key=lambda q: (people[q].generation, _place(people[q])))   # a later page's founders too
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
            # The children's middle under their parents' whatever the gap and shrink (Codex, #575): at
            # the default spacing (step = NODE_W + GAP_X) this is the old wanted - (span - GAP_X) / 2.
            ideal = wanted - NODE_W / 2 - (span - step) / 2
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
    # Every row is "Generation <n>", the first too (the owner: "Just use Generation 1.  Players can type
    # FOUNDERS if they want to").
    out = {"number": f"{generation_number(lay, g)}.", "name": f"Generation {g}",
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
# The owner: "And default: "Other Members"" (the heading over the villagers with no recorded family).
WORDS = {"others": "Other Members", "others_note": "no recorded parent or child", "footer": ""}


def words(lay: Layout, key: str) -> str:
    return lay.edits.words.get(key) or (footer(lay) if key == "footer" else WORDS[key])


FOOTER = ("Each unrelated villager has a colour of their own and full brothers and sisters share one; each "
          "pairing has its own connector; a triangle joins twins and triplets.  Generation I is the founders; a "
          "villager who arrived later is in the generation they first appear in.  Made by the Virtual Villagers "
          "Fun Patcher's Family Tree Maker from the save and the patcher's logs.")


# Plurals English does not make by adding "s" (the owner, 2026-10-09: "monstera leafs; ... butterflys.
# ahem. grammar.").
IRREGULAR_PLURALS = {"leaf": "leaves", "fish": "fish", "starfish": "starfish", "hibiscus": "hibiscus flowers",
                     "bunch": "bunches", "x": "Xs"}


def plural(shape: str) -> str:
    """A portrait shape's name for many of them, as the Key says it: the noun before any "(...)", "in ..."
    or "of ..." made plural ("ovals (horizontal)", "ocean waves in a circle", "bunches of bananas")."""
    name = PORTRAIT_SHAPES.get(shape, shape)
    name = name if name.startswith("Monstera") else name.lower()
    head, rest = re.match(r"(.+?)((?: \(| in | of ).*)?$", name).groups()
    words = head.split(" ")
    last = words[-1]
    if last in IRREGULAR_PLURALS:
        last = IRREGULAR_PLURALS[last]
    elif last.endswith("y") and last[-2:-1] not in ("a", "e", "i", "o", "u"):
        last = last[:-1] + "ies"
    elif last.endswith(("s", "x", "ch", "sh")):
        last += "es"
    else:
        last += "s"
    return " ".join(words[:-1] + [last]) + (rest or "").replace("(on its side)", "(on their sides)")


def footer(lay: Layout) -> str:
    """The Key: which portrait shape each group is drawn in (as the player set them), then FOOTER."""
    groups = "; ".join(f"{label}: {plural(lay.edits.shapes[group])}" for group, label in GROUPS.items())
    return f"{groups}.  {FOOTER}"


def node_text(lay: Layout, p: gen.Person) -> list[str]:
    """The entry's lines: the player's own, or the patcher's (default_text)."""
    lines = lay.entry(p).get("lines")
    return _shown_name_in(lay, p, lines, None)[0] if lines else default_text(lay, p)


def _shown_name_in(lay: Layout, p: gen.Person, lines: list, runs) -> tuple[list, object]:
    """The player's lines for a villager with their name -- with or without a Roman number -- as the
    tree shows it now (the owner, 2026-10-08: the tree's numbering is the rule, "Hawa Awanata II" is
    "Hawa Awanata" when there is no other).  Other words are never touched."""
    if p.upcoming or not p.name:
        return lines, runs
    lines, runs = _rename_in_lines(lines, runs, _name_pattern(gen.unnumbered(p.name), numbered=True),
                                   lay.names.get(p.id, p.name))
    # The facts the records keep changing: the age, in years and in game units, and whether the villager
    # is still here (the owner, 2026-10-09: Kalea Salongo, 16 in the game, still "5 years old" on the tree
    # after Update from Logs/Saves).  Only those words, where the player's lines already have them.
    if p.age is not None:
        lines, runs = _rename_in_lines(lines, runs, AGE_YEARS, f"{p.years} years old")
        lines, runs = _rename_in_lines(lines, runs, AGE_UNITS, f"{p.age} game units")
    if not p.alive:
        status = {"died": "(deceased)", "disappeared": "(disappeared)"}.get(p.gone, "(left the village)")
        lines, runs = _rename_in_lines(lines, runs, STATUS_WORDS, status)
    return lines, runs


AGE_YEARS = re.compile(r"(?<![\w.])\d+ years old(?!\w)")
AGE_UNITS = re.compile(r"(?<![\w.])\d+ game units(?!\w)")
STATUS_WORDS = re.compile(r"\((?:deceased|disappeared|left the village)\)")


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
    founder = ["Founder"] if e.show_founder and p.generation == 1 else []     # the owner, 2026-10-09
    return [f"{p.number}. {lay.names.get(p.id, p.name)}"] + ages + founder + born_with(lay, p) + ([extra] if extra else [])


def born_with(lay: Layout, p: gen.Person) -> list[str]:
    """With "Twins and triplets" on (Edits.show_twins), the line after the age naming who the
    villager was born with (the owner, 2026-10-09: "X's twin/triplet"): "Kalea's twin", "Kalea and
    Hana's triplet".  Nothing for a villager born alone, or with the setting off."""
    if not lay.edits.show_twins or p.litter is None or p.upcoming:
        return []
    others = sorted((q for q in lay.village.people.values()
                     if q.litter == p.litter and q.id != p.id and not q.upcoming), key=lambda q: (q.number or 0, q.id))
    if not others or len(others) > 2:
        return []
    names = [lay.names.get(q.id, q.name) or "(unnamed)" for q in others]
    return [f"{' and '.join(names)}'s {'twin' if len(others) == 1 else 'triplet'}"]


def inner_sizes(lay: Layout, p: gen.Person) -> tuple[float, float]:
    """(the face's size, the words' size) inside this villager's portrait, as factors: every portrait's
    setting times their own."""
    entry = lay.entry(p)
    return (lay.edits.picture_size / 100 * entry.get("picture_scale", 100.0) / 100,
            lay.edits.text_size / 100 * entry.get("text_scale", 100.0) / 100)


def placement(lay: Layout, p: gen.Person, box: tuple = None) -> tuple[float, float, float, list]:
    """(the head cell's left and top inside the frame, the first line's baseline, the lines as
    drawn): the face (the head's visible pixels, `box`) and the lines centred together (the owner:
    "center the heads within the portrait shapes vertically and horizontally"), or the head at the
    top when the player turns centring off ("in case players type a lot of stuff")."""
    x0, y0, x1, y1 = box or DEFAULT_BOX
    pic, words = inner_sizes(lay, p)
    face = (y1 - y0) * HEAD_SCALE * pic
    lh = LINE_H * words                     # the lines spaced as the words are sized
    valign = lay.edits.text_valign
    face_top = 10.0 if valign == "top" else 6.0
    lines = shown_text(lay, p, int(max(LINE_H, NODE_H - face_top - face - 8 - 6) // lh))
    block = face + 8 + len(lines) * lh
    if valign == "middle":
        face_top = max(face_top, (NODE_H - block) / 2)
    elif valign == "bottom":                # the last line just above the frame's foot
        face_top = max(face_top, NODE_H - block - 6)
    left = NODE_W / 2 - (x0 + x1) / 2 * HEAD_SCALE * pic
    return left, face_top - y0 * HEAD_SCALE * pic, face_top + face + 8 + lh - 3, lines


WRAP = 17                               # characters across a portrait, until the player says
WRAP_MIN, WRAP_MAX = 8, 60


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


def node_runs(lay: Layout, p: gen.Person) -> list[list[tuple[str, dict]]] | None:
    """The entry's lines formatted word by word (clean_runs), or None when they are plain."""
    entry = lay.entry(p)
    lines = entry.get("lines")
    if not lines:
        return None
    lines, runs = _shown_name_in(lay, p, lines, entry.get("runs"))
    return clean_runs(runs, lines)


BOLD_WIDTH = 1.1                        # how much wider a bold letter is, near enough


def run_width(style: dict, base: dict) -> float:
    """How wide a letter of a run is against one of its line's own look (`base`: the role's bold
    and script): a bolder letter wider, a superscript or subscript one narrower."""
    def width(bold: bool, script: str) -> float:
        return (BOLD_WIDTH if bold else 1.0) * (SCRIPTS[script][0] if script in SCRIPTS else 1.0)
    bold = style.get("bold", base.get("bold", False))
    script = style.get("script", base.get("script", ""))
    return width(bold, script) / width(base.get("bold", False), base.get("script", ""))


def _wrap_cells(cells: list[tuple[str, float, dict]], n: float = WRAP) -> list[list[tuple[str, float, dict]]]:
    """_wrap for formatted words: each letter (letter, width, style) as wide as its font makes it,
    a plain letter 1 -- so plain words wrap exactly as _wrap wraps them."""
    def wide(cs) -> float:
        return sum(c[1] for c in cs)
    words: list[tuple[tuple | None, list]] = [(None, [])]       # (the space before it, its letters)
    for cell in cells:
        if cell[0] == " ":
            words.append((cell, []))
        else:
            words[-1][1].append(cell)
    out: list[list] = []
    line: list = []
    for space, word in words:
        while wide(word) > n + 1e-9:
            if line:
                out.append(line)
                line = []
            k, used = 0, 0.0
            while k < len(word) and (k == 0 or used + word[k][1] <= n + 1e-9):
                used += word[k][1]
                k += 1
            out.append(word[:k])
            word = word[k:]
        if not line:
            line = word
        elif wide(line) + space[1] + wide(word) <= n + 1e-9:
            line = line + [space] + word
        else:
            out.append(line)
            line = word
    out.append(line)
    return out


def _joined(lines: list[str], n: int) -> list[str]:
    """The patcher's own lines under the name, put side by side while they fit in `n` characters
    (the owner, 2026-10-08: "1379 game units, 68 years old"): the ages with a comma, a note in
    brackets after a space."""
    out: list[str] = []
    for line in lines:
        if out and line and out[-1]:
            joint = _joint(out[-1], line)
            if len(out[-1]) + len(joint) + len(line) <= n:
                out[-1] += joint + line
                continue
        out.append(line)
    return out


def _joint(before: str, after: str) -> str:
    """What goes between two lines put side by side: a space beside a bracketed note -- "(deceased)
    Founder" -- else a comma -- "1379 game units, 68 years old"."""
    return " " if after.startswith("(") or before.endswith(")") else ", "


def _joined_runs(lines: list, n: int, edits: "Edits") -> list:
    """_joined for formatted lines: each keeps its own words' formatting; they are measured as
    wide as their fonts make them (run_width)."""
    base = line_base(edits, False)

    def wide(line) -> float:
        return sum(run_width(style, base) * len(text) for text, style in line)

    def plain(line) -> str:
        return "".join(text for text, _style in line)
    out: list = []
    for line in lines:
        if out and plain(line) and plain(out[-1]):
            joint = _joint(plain(out[-1]), plain(line))
            if wide(out[-1]) + len(joint) + wide(line) <= n + 1e-9:
                out[-1] = list(out[-1]) + [(joint, {})] + list(line)
                continue
        out.append(list(line))
    return out


def _cells_runs(cells: list) -> list[tuple[str, dict]]:
    return merge_runs((c[0], c[2]) for c in cells)


def shown_text(lay: Layout, p: gen.Person, room: int) -> list[tuple[str, bool, list | None]]:
    """The portrait's lines as drawn, each with whether it is bold (the first line, the name) and
    its runs when the player formatted it (else None): every line wrapped to fit across, and as many
    as fit below the head -- the last of them ending in ... when some did not.  Formatted words wrap
    by how wide their fonts make them (run_width), so they never run past the portrait."""
    n = lay.edits.text_wrap
    runs = node_runs(lay, p)
    if runs is None:
        lines = node_text(lay, p)
        if n > WRAP:                    # widened: side by side while they fit (the owner's picture); at the
            lines = lines[:1] + _joined(lines[1:], n)       # default every line stays as typed (Codex, #575)
        out = [(piece, k == 0, None) for k, text in enumerate(lines) for piece in _wrap(text, n)]
        room = max(1, room)
        if len(out) > room:
            last, bold, _r = out[room - 1]
            out = out[:room - 1] + [(last[:n - 1] + "…", bold, None)]
        return out
    pieces: list[tuple[list, bool]] = []
    if n > WRAP:
        runs = runs[:1] + _joined_runs(runs[1:], n, lay.edits)
    for k, line in enumerate(runs):
        base = line_base(lay.edits, k == 0)
        cells = [(ch, run_width(style, base), style) for text, style in line for ch in text]
        pieces.extend((cells_line, k == 0) for cells_line in _wrap_cells(cells, n))
    room = max(1, room)
    if len(pieces) > room:
        last, bold = pieces[room - 1]
        kept, used = [], 0.0
        for cell in last:
            if used + cell[1] > n - 1 + 1e-9:
                break
            kept.append(cell)
            used += cell[1]
        pieces = pieces[:room - 1] + [(kept + [("…", 1.0, kept[-1][2] if kept else {})], bold)]
    out = []
    for cells, bold in pieces:
        line_runs = _cells_runs(cells)
        text = "".join(t for t, _s in line_runs)
        out.append((text, bold, line_runs if any(s for _t, s in line_runs) else None))
    return out


def line_base(edits: "Edits", name: bool) -> dict:
    """A portrait line's own look before its runs': its role's bold, italic, underline, strike and
    script (the name's line -- the first -- bold unless the player said otherwise)."""
    style = edits.styles.get("names" if name else "portraits", {})
    return {"bold": style.get("bold", name), "italic": style.get("italic", False),
            "underline": style.get("underline", False), "strike": style.get("strike", False),
            "script": style.get("script", "")}


def run_effect(style: dict, base: dict) -> dict:
    """How a run looks (its own style over its line's: line_base): every flag, its script ("" none)
    and its own colour ("" its role's)."""
    out = {flag: style.get(flag, base[flag]) for flag in RUN_FLAGS}
    script = style.get("script", base["script"])
    out["script"] = "" if script == "normal" else script
    out["colour"] = style.get("colour", "")
    return out


def format_styles(styles: list[dict], bases: list[dict], what: str, colour: str = "") -> list[dict]:
    """The selected letters' styles (each with its line's line_base) after a format button: a flag
    or superscript / subscript turned on for all of them unless all of them have it already (then
    off), as a word processor does; "colour" (`colour`, or "" back to the role's), "plain" every
    setting off.  A letter keeps only what differs from its line's own look."""
    if what == "plain":
        return [{} for _s in styles]
    if what == "colour":
        return [{**{k: v for k, v in s.items() if k != "colour"}, **({"colour": colour} if colour else {})}
                for s in styles]
    looks = [run_effect(s, b) for s, b in zip(styles, bases)]
    out = []
    if what in RUN_FLAGS:
        target = not all(look[what] for look in looks)
        for s, b in zip(styles, bases):
            new = {k: v for k, v in s.items() if k != what}
            if target != b[what]:
                new[what] = target
            out.append(new)
    elif what in SCRIPTS:
        target = what if not all(look["script"] == what for look in looks) else ""
        for s, b in zip(styles, bases):
            new = {k: v for k, v in s.items() if k != "script"}
            if target != b["script"]:
                new["script"] = target or "normal"
            out.append(new)
    else:
        raise ValueError(f"no such format: {what}")
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
    # The owner, 2026-10-09: 4- and 6-pointed stars too (the 6-pointed one two crossed triangles' outline).
    star6 = [(math.sin(k * math.pi / 6) * (0.5 if k % 2 == 0 else 0.5 / math.sqrt(3)),
              -math.cos(k * math.pi / 6) * (0.5 if k % 2 == 0 else 0.5 / math.sqrt(3))) for k in range(12)]
    # The owner's pictures (2026-10-09): a plumper 5-pointed star, and a 6-pointed one with long thin points.
    plump = [(math.sin(k * math.pi / 5) * (0.5 if k % 2 == 0 else 0.26),
              -math.cos(k * math.pi / 5) * (0.5 if k % 2 == 0 else 0.26)) for k in range(10)]
    slim6 = [(math.sin(k * math.pi / 6) * (0.5 if k % 2 == 0 else 0.19),
              -math.cos(k * math.pi / 6) * (0.5 if k % 2 == 0 else 0.19)) for k in range(12)]
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
        # The owner's picture (2026-10-09): taller than wide, a narrow waist.
        "star4": [(0.5, 0), (0.636, 0.385), (1, 0.5), (0.636, 0.615), (0.5, 1), (0.364, 0.615), (0, 0.5),
                  (0.364, 0.385)],
        "star6": fit(star6),
        "plump_star": fit(plump),
        "slim_star6": fit(slim6),
        # The owner, 2026-10-09: horizontal and vertical arrows (a portrait turns to point any other way).
        "arrow_h": [(0, 0.3), (0.6, 0.3), (0.6, 0), (1, 0.5), (0.6, 1), (0.6, 0.7), (0, 0.7)],
        "arrow_v": [(0.5, 0), (1, 0.4), (0.7, 0.4), (0.7, 1), (0.3, 1), (0.3, 0.4), (0, 0.4)],
        "hexagon": [(0.5, 0), (1, 0.25), (1, 0.75), (0.5, 1), (0, 0.75), (0, 0.25)],
        "octagon": [(0.3, 0), (0.7, 0), (1, 0.3), (1, 0.7), (0.7, 1), (0.3, 1), (0, 0.7), (0, 0.3)],
        "trapezoid": [(0.2, 0), (0.8, 0), (1, 1), (0, 1)],           # the owner, 2026-10-09
        # A wide oval (the owner, 2026-10-09, in place of the leafy oval): "Oval" fills a tall portrait.
        "oval_wide": [(0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)) for a in (2 * math.pi * k / 96 for k in range(96))],
        "pentagon": [(0.5, 0), (1, 0.382), (0.809, 1), (0.191, 1), (0, 0.382)],     # regular; the owner, 2026-10-09
        "heart": fit(heart),
        # The owner's picture (2026-10-09): straight sides, a half-circle top, about two thirds as wide as tall.
        "arch": [(0, 1), (0, 0.327)] + [(0.5 - 0.5 * math.cos(math.pi * k / 36), 0.327 - 0.327 * math.sin(math.pi * k / 36))
                                          for k in range(1, 36)] + [(1, 0.327), (1, 1)],
        **{name: shape[0] for name, shape in SHELLS.items()},     # the shells and the owner's other pictures
    }


def _traced(inside_at, centre: tuple[float, float], rays: int = 240) -> list[tuple[float, float]]:
    """The edge of a shape given as a test of whether a point is in it: along each ray from
    `centre`, the farthest point inside it (so parts that do not touch the centre, a butterfly's
    wings, are traced too)."""
    out = []
    for k in range(rays):
        t = 2 * math.pi * k / rays
        dx, dy = math.cos(t), math.sin(t)
        far = 0.0
        for step in range(1, 700):
            r = step * 0.003
            if inside_at(centre[0] + r * dx, centre[1] + r * dy):
                far = r
        out.append((centre[0] + far * dx, centre[1] + far * dy))
    return out


@functools.lru_cache(maxsize=1)
def _drawn_outlines() -> dict[str, list[tuple[float, float]]]:
    """The owner's shapes of 2026-10-08 -- a flower, a butterfly, a leaf and the playing-card suits'
    clover and spade -- traced from simple parts (circles, ellipses, a heart, a stem), y downward."""
    def disc(cx, cy, r):
        return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r

    def oval(cx, cy, rx, ry, turn_deg=0.0):
        c, s = math.cos(math.radians(turn_deg)), math.sin(math.radians(turn_deg))
        return lambda x, y: (((x - cx) * c + (y - cy) * s) / rx) ** 2 + ((-(x - cx) * s + (y - cy) * c) / ry) ** 2 <= 1

    def stem(top, bottom, half_top, half_bottom, cx=0.0):
        def at(x, y):
            if not top <= y <= bottom:
                return False
            half = half_top + (half_bottom - half_top) * (y - top) / (bottom - top)
            return abs(x - cx) <= half
        return at

    def union(*parts):
        return lambda x, y: any(part(x, y) for part in parts)

    # A six-petalled flower, the owner's picture: six long oval petals from the middle, one
    # straight up and one straight down.
    petals = [oval(0.25 * math.cos(math.radians(-90 + 60 * k)), 0.25 * math.sin(math.radians(-90 + 60 * k)),
                   0.25, 0.165, -90 + 60 * k) for k in range(6)]
    flower = union(disc(0, 0, 0.2), *petals)
    # A butterfly, kept simple (the owner): two round upper wings and two smaller lower ones,
    # meeting in the middle.
    butterfly = union(oval(-0.36, -0.18, 0.4, 0.32, -20), oval(0.36, -0.18, 0.4, 0.32, 20),
                      oval(-0.26, 0.28, 0.28, 0.24, 25), oval(0.26, 0.28, 0.28, 0.24, -25),
                      oval(0, 0.02, 0.2, 0.36))
    # The club (clover) of a deck of cards: three round leaves round a wide middle and a short
    # stem, with room inside for the face and the words (the owner).
    clover = union(disc(0, -0.3, 0.34), disc(-0.36, 0.14, 0.34), disc(0.36, 0.14, 0.34), disc(0, 0.05, 0.32),
                   stem(0.3, 0.68, 0.06, 0.2))
    # The spade: an upside-down heart and a flared stem.
    heart = [(16 * math.sin(t) ** 3, (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t)
                                          - math.cos(4 * t))) for t in (k * 2 * math.pi / 120 for k in range(120))]
    spade_heart = [(px / 28, py / 28 - 0.12) for px, py in heart]      # a wide body: room inside
    def in_heart(x, y):                 # inside() is defined further down the module
        hit = False
        for (ax, ay), (bx, by) in zip(spade_heart, spade_heart[1:] + spade_heart[:1]):
            if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                hit = not hit
        return hit
    def flared(x, y):                   # the stem, flaring in a smooth curve to its foot, from inside the body
        if not 0.0 <= y <= 0.58:
            return False
        return abs(x) <= 0.03 + 0.13 * (y / 0.58) ** 2    # a little smaller (the owner, 2026-10-09)
    spade = union(in_heart, flared)     # the owner, 2026-10-09: no bumps where the stem meets the body
    # A leaf, the owner's picture: a broad blade pointing up to the right, fullest towards its
    # base at the lower left, both ends pointed -- and a stalk from the base "so it's clear".
    leaf_c, leaf_s = math.cos(math.radians(-40)), math.sin(math.radians(-40))

    def along(x, y):                    # (towards the tip, across)
        return x * leaf_c + y * leaf_s, -x * leaf_s + y * leaf_c

    def blade(x, y):
        u, v = along(x, y)
        s = u / 0.62
        return abs(s) <= 1 and abs(v) <= 0.36 * (1 - s * s) ** 0.75 * (1 - 0.22 * s)

    def stalk(x, y):
        u, v = along(x, y)
        return -0.86 <= u <= -0.5 and abs(v) <= 0.028
    leaf = union(blade, stalk)
    return {"flower": _traced(flower, (0, 0)), "butterfly": _traced(butterfly, (0, 0)),
            "clover": _traced(clover, (0, 0)), "spade": _traced(spade, (0, 0.05)),
            "leaf": _traced(leaf, (0, 0))}


def _shells() -> dict[str, tuple[list, list]]:
    """The owner's shells (2026-10-09, from their pictures): a scallop -- seven rounded lobes fanned
    over a hinge, a small ear either side below -- and a snail's shell, its last whorl round a
    spiral.  Each (outline, detail lines) in a 1 x 1 box, y downward; the details are the ribs and
    the whorls' spiral, drawn light (Edits.detail_lines)."""
    out = {}
    # The scallop, its hinge at (0, 0), the fan's radius 1.
    rim, lobes, ribs = [], 7, []
    for k in range(141):
        t = k / 140
        phi = math.radians(165 - 150 * t)
        part = (lobes * t) % 1.0 if k < 140 else 0.0
        r = 0.88 + 0.12 * math.sqrt(math.sin(math.pi * part))
        rim.append((r * math.cos(phi), -r * math.sin(phi)))
    scallop = rim + [(0.34, -0.1), (0.34, 0.02), (-0.34, 0.02), (-0.34, -0.1)]
    for k in range(1, lobes):
        phi = math.radians(165 - 150 * k / lobes)
        ribs.append([(0.0, -0.02), (0.86 * math.cos(phi), -0.86 * math.sin(phi))])
    ribs += [[(0.0, -0.02), (0.34, -0.1)], [(0.0, -0.02), (-0.34, -0.1)]]
    # Taller than the fan's own circle (the owner, 2026-10-09: the first was "too squashed").
    tall = lambda pt: (pt[0], pt[1] * 1.35)
    out["scallop"] = ([tall(pt) for pt in scallop], [[tall(pt) for pt in rib] for rib in ribs])
    # The snail's shell: a spiral growing 1.8 times a turn; its last whorl is the outline, closed by
    # the opening's lip, and the turns inside it the detail line.  Turned so the opening is at the
    # lower right, as in the owner's picture.
    b = math.log(1.8) / (2 * math.pi)
    turn_by = math.radians(35)

    def at(theta):
        r = math.exp(b * theta)
        x, y = r * math.cos(theta), r * math.sin(theta)
        return (x * math.cos(turn_by) - y * math.sin(turn_by), x * math.sin(turn_by) + y * math.cos(turn_by))
    whorl = [at(2 * math.pi * k / 120) for k in range(121)]
    inner = [at(-5 * math.pi + 5 * math.pi * k / 200) for k in range(201)]
    out["snail"] = (whorl, [inner])
    out.update(_more_shapes())
    fitted = {}
    for name, value in out.items():
        edge, lines = value[0], value[1]
        decor = value[2] if len(value) > 2 else []
        xs, ys = zip(*edge)
        x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
        unit = lambda p: ((p[0] - x0) / w, (p[1] - y0) / h)
        fitted[name] = ([unit(p) for p in edge], [[unit(p) for p in line] for line in lines], w / h,
                        [[unit(p) for p in line] for line in decor])
    return fitted


def _smooth(points: list[tuple[float, float]], closed: bool = False, steps: int = 8) -> list[tuple[float, float]]:
    """A curve through `points` (Catmull-Rom), `steps` points between each two."""
    pts = list(points)
    n = len(pts)
    out = []
    last = n if closed else n - 1
    for i in range(last):
        p0 = pts[(i - 1) % n] if closed or i > 0 else pts[i]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed or i + 2 < n else p2
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in (0, 1)))
    if not closed:
        out.append(pts[-1])
    return out


def _ring(cx: float, cy: float, rx: float, ry: float, n: int = 48) -> list[tuple[float, float]]:
    return [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]


def _envelope(polygons: list, centre: tuple[float, float], rays: int = 360) -> list[tuple[float, float]]:
    """The outer edge of several overlapping polygons together, seen from `centre` (inside them): along
    each ray, the farthest place any polygon's edge crosses it."""
    out = []
    cx, cy = centre
    for k in range(rays):
        a = 2 * math.pi * k / rays
        dx, dy = math.cos(a), math.sin(a)
        far = 0.0
        for poly in polygons:
            for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
                ex, ey = bx - ax, by - ay
                den = dx * ey - dy * ex
                if abs(den) < 1e-12:
                    continue
                s = ((ax - cx) * ey - (ay - cy) * ex) / den        # along the ray
                u = ((ax - cx) * dy - (ay - cy) * dx) / den        # along the edge
                if s > 0 and 0 <= u <= 1:
                    far = max(far, s)
        out.append((cx + far * dx, cy + far * dy))
    return out


def _inside_poly(poly, x, y) -> bool:
    hit = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


def _more_shapes() -> dict:
    """The owner's pictures of 2026-10-09: a hibiscus, a sand dollar, a turtle's shell
    (upright and on its side) and a mermaid's tail -- each (outline, light detail lines, lines drawn
    like the border), y downward, before fitting to the 1 x 1 box."""
    out = {}


    # A hibiscus: five broad petals, one straight up; the stamen out to the upper right with its
    # pollen, and light streaks from the middle.
    petals = []
    for k in range(200):
        a = 2 * math.pi * k / 200
        lobe = abs(math.cos(5 * (a + math.pi / 2) / 2)) ** 0.45
        r = 0.5 + 0.5 * lobe + 0.025 * math.cos(15 * (a + math.pi / 2))
        petals.append((r * math.cos(a), r * math.sin(a)))
    streaks = [[(0.1 * math.cos(a), 0.1 * math.sin(a)), (0.36 * math.cos(a), 0.36 * math.sin(a))]
               for a in (2 * math.pi * k / 10 + math.pi / 10 for k in range(10))]
    stamen = _smooth([(0.02, 0.02), (0.25, -0.25), (0.42, -0.55), (0.5, -0.85)], steps=6)
    pollen = [_ring(x, y, 0.045, 0.045, 12) for x, y in ((0.4, -0.92), (0.52, -1.0), (0.62, -0.88), (0.6, -0.75))]
    out["hibiscus"] = (petals, streaks, [stamen] + pollen)

    # A sand dollar: round, a small dip at the top; five petal loops round a centre dot, and five
    # slots between them towards the edge.
    disc = []
    for k in range(120):
        a = 2 * math.pi * k / 120
        dip = 0.06 * math.exp(-((math.atan2(math.sin(a + math.pi / 2), math.cos(a + math.pi / 2))) / 0.3) ** 2)
        disc.append(((1 - dip) * math.cos(a), (1 - dip) * math.sin(a)))
    marks = [_ring(0, 0, 0.07, 0.07, 16)]
    for k in range(5):
        a = math.radians(-90 + 72 * k)
        ca, sa = math.cos(a), math.sin(a)
        loop = []
        for s in range(41):
            u = s / 40 * 2
            along = u if u <= 1 else 2 - u
            across = (1 if u <= 1 else -1) * 0.12 * math.sin(math.pi * along)
            r = 0.12 + 0.5 * along
            loop.append((r * ca - across * sa, r * sa + across * ca))
        marks.append(loop)
        b = math.radians(90 + 72 * k)
        reach = 0.95 if k == 0 else 0.85
        marks.append([(0.62 * math.cos(b), 0.62 * math.sin(b)), (reach * math.cos(b), reach * math.sin(b))])
    out["sand_dollar"] = (disc, marks)

    # A turtle's shell, upright: an oval with a notched rim, an inner rim, three hexagons down the
    # middle and the side plates between them and the rim.
    a_x, a_y = 0.8, 1.0
    shell = []
    for k in range(168):
        a = 2 * math.pi * k / 168
        notch = 0.97 if (k % 12) in (0, 1) else 1.0
        shell.append((notch * a_x * math.cos(a), notch * a_y * math.sin(a)))
    rim_s = 0.86

    def to_rim(x, y, dx, dy):
        for s in range(1, 400):
            px, py = x + dx * s * 0.005, y + dy * s * 0.005
            if (px / (a_x * rim_s)) ** 2 + (py / (a_y * rim_s)) ** 2 >= 1:
                return (px, py)
        return (x, y)
    plates = [_ring(0, 0, a_x * rim_s, a_y * rim_s, 96)]
    w, h = 0.27, 0.2
    for cy in (-0.4, 0.0, 0.4):
        plates.append([(-w, cy), (-w / 2, cy - h), (w / 2, cy - h), (w, cy), (w / 2, cy + h), (-w / 2, cy + h), (-w, cy)])
        for sx in (-1, 1):
            plates.append([(sx * w, cy), to_rim(sx * w, cy, sx, 0)])
    for sx in (-1, 1):
        plates.append([(sx * w / 2, -0.6), to_rim(sx * w / 2, -0.6, sx * 0.45, -1)])
        plates.append([(sx * w / 2, 0.6), to_rim(sx * w / 2, 0.6, sx * 0.45, 1)])
    out["turtle_v"] = (shell, plates)
    out["turtle_h"] = ([(y, x) for x, y in shell], [[(y, x) for x, y in line] for line in plates])

    # A mermaid's tail, traced from the owner's picture (1600 pixels square): two fins over a narrow
    # waist, a wide foot; the fins' lines and five rows of scales.
    tail = _smooth([(108, 40), (330, 110), (560, 210), (680, 330), (705, 410), (760, 300), (930, 190), (1130, 110),
                    (1290, 30), (1280, 200), (1180, 400), (1000, 560), (860, 650), (845, 760), (930, 960),
                    (1040, 1180), (1100, 1400), (1150, 1525), (900, 1490), (600, 1495), (300, 1560), (360, 1350),
                    (450, 1120), (560, 930), (600, 790), (560, 690), (380, 570), (210, 410), (120, 230)],
                   closed=True, steps=6)
    fins = [_smooth([(240, 250), (330, 410), (480, 530), (640, 690)], steps=8),
            _smooth([(1230, 150), (1150, 310), (960, 450), (830, 580)], steps=8)]

    def scales(y, x0, x1, n):
        row, step = [], (x1 - x0) / n
        for i in range(n):
            row += [(x0 + step * (i + s / 10), y - 70 * math.sin(math.pi * s / 10)) for s in range(11)]
        return row
    rows = [scales(840, 650, 830, 1), scales(960, 560, 910, 2), scales(1110, 470, 990, 3),
            scales(1260, 420, 1030, 4), scales(1410, 440, 1040, 3)]
    out["mermaid_tail"] = ([(x / 1000, y / 1000) for x, y in tail],
                           [[(x / 1000, y / 1000) for x, y in line] for line in fins + rows])
    # On its side too (the owner, 2026-10-09): the fins to the left, the foot to the right.
    out["mermaid_tail_h"] = ([(y, x) for x, y in out["mermaid_tail"][0]], [[(y, x) for x, y in line] for line in out["mermaid_tail"][1]])

    # A fish, the owner's picture (540 pixels square), facing right: a smooth body to a rounded nose,
    # a forked tail with sharp tips; an eye and a gill, light.  And the same fish facing left.
    body = _smooth([(148, 240), (230, 200), (330, 178), (430, 192), (500, 230), (525, 272), (500, 315), (430, 352),
                    (330, 372), (230, 355), (142, 292)], steps=8)
    lower = _smooth([(142, 292), (90, 327), (15, 355)], steps=6)
    upper = _smooth([(15, 180), (85, 205), (148, 240)], steps=6)
    fish = body + lower[1:] + [(70, 268)] + upper[:-1]
    face = [_ring(452, 252, 11, 11, 16), _smooth([(395, 215), (410, 272), (395, 330)], steps=8)]
    out["fish_right"] = ([(x / 540, y / 540) for x, y in fish], [[(x / 540, y / 540) for x, y in l] for l in face])
    out["fish_left"] = ([(-x / 540, y / 540) for x, y in fish], [[(-x / 540, y / 540) for x, y in l] for l in face])

    # An ocean wave in a circle, the owner's picture: the circle the outline, the wave across it,
    # curling over at the top, a light detail (the owner, 2026-10-09).
    cx, cy, r = 195, 240, 185
    wave = _smooth([(12, 268), (60, 276), (120, 242), (180, 202), (228, 192), (256, 200), (230, 212), (216, 240),
                    (226, 274), (252, 288), (300, 271), (350, 255), (378, 252)], steps=8)
    out["wave_circle"] = (_ring(0, 0, 1, 1, 96), [[((x - cx) / r, (y - cy) / r) for x, y in wave]])   # the wave light

    # A conch (the owner, 2026-10-09: the first was "too fat for a conch shell"): a slim shell, a
    # pointed stepped spire on top, widest at the shoulder, tapering to a point below, its lip flaring a
    # little on the right; the spire's steps and the opening, light.
    conch = _smooth([(0, 0), (35, 70), (55, 82), (82, 150), (110, 162), (142, 228), (185, 245), (232, 268),
                     (262, 305), (285, 390), (298, 485), (272, 600), (205, 722), (125, 842), (52, 948), (14, 1000),
                     (-18, 960), (-60, 850), (-128, 700), (-196, 545), (-238, 405), (-248, 322), (-222, 272),
                     (-188, 250), (-142, 234), (-110, 162), (-78, 150), (-55, 82), (-32, 70)], closed=True, steps=6)
    bands = [_smooth(band, steps=8) for band in (
        [(-55, 82), (0, 92), (55, 82)], [(-110, 162), (0, 176), (110, 162)], [(-188, 250), (0, 268), (185, 245)])]
    mouth = _smooth([(150, 320), (222, 450), (205, 620), (125, 780), (42, 905), (78, 760), (118, 600),
                     (128, 450), (150, 320)], steps=6)
    out["conch"] = ([(x / 1000, y / 1000) for x, y in conch],
                    [[(x / 1000, y / 1000) for x, y in line] for line in bands + [mouth]])

    # A starfish, the owner's picture: five plump arms with rounded tips and curved sides between
    # them; a ring in the middle, a band and a row of dots down each arm, a line into each gap.
    body = []
    for k in range(250):
        a = 2 * math.pi * k / 250
        # 0 at an arm's tip, 1 halfway to the next: arms tapering to a rounded tip, plump sides.
        off = abs(((a + math.pi / 2) / (2 * math.pi / 5) + 0.5) % 1 - 0.5) * 2
        r = 0.5 + 0.5 * (1 - off) ** 1.25 - 0.06 * max(0.0, 1 - off / 0.12) ** 2
        body.append((r * math.cos(a), r * math.sin(a)))
    marks = [_ring(0, 0, 0.13, 0.13, 32)]
    for k in range(5):
        a = math.radians(-90 + 72 * k)
        ca, sa = math.cos(a), math.sin(a)
        for side in (1, -1):
            marks.append([((0.13 + 0.8 * u) * ca - side * 0.075 * math.sin(math.pi * min(1, u * 1.15)) * sa,
                           (0.13 + 0.8 * u) * sa + side * 0.075 * math.sin(math.pi * min(1, u * 1.15)) * ca)
                          for u in (s / 20 for s in range(21))])
        marks += [_ring((0.2 + 0.12 * d) * ca, (0.2 + 0.12 * d) * sa, 0.022, 0.022, 10) for d in range(6)]
        b = math.radians(-54 + 72 * k)
        marks.append([(0.14 * math.cos(b), 0.14 * math.sin(b)), (0.42 * math.cos(b), 0.42 * math.sin(b))])
    out["starfish"] = (body, marks)

    # A ship's wheel, the owner's picture: the rim with eight rounded handles out from it the outline;
    # the inner rim, the hub and the eight spokes (each a pair of lines), light.
    wheel, half, reach, cap = [], 0.075, 1.3, 0.095
    d = math.asin(half)
    for k in range(8):
        a = math.radians(-90 + 45 * k)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        wheel.append((math.cos(a - d), math.sin(a - d)))
        # out along the handle, round its end, and back (a half circle about its end's middle)
        wheel += [(reach * ux + cap * (-math.cos(s) * nx + math.sin(s) * ux),
                   reach * uy + cap * (-math.cos(s) * ny + math.sin(s) * uy)) for s in
                  (math.pi * j / 12 for j in range(13))]
        wheel.append((math.cos(a + d), math.sin(a + d)))
        b = a + math.radians(45)
        wheel += [(math.cos(a + d + (b - a - 2 * d) * j / 12), math.sin(a + d + (b - a - 2 * d) * j / 12))
                  for j in range(1, 12)]
    hub = [_ring(0, 0, 0.75, 0.75, 72), _ring(0, 0, 0.17, 0.17, 32), _ring(0, 0, 0.1, 0.1, 24)]
    for k in range(8):
        a = math.radians(45 * k)
        ca, sa = math.cos(a), math.sin(a)
        for side in (-0.045, 0.045):
            hub.append([(0.19 * ca - side * sa, 0.19 * sa + side * ca), (0.74 * ca - side * sa, 0.74 * sa + side * ca)])
    out["ship_wheel"] = (wheel, hub)

    # A coconut, the owner's picture: nearly round, its three eyes right at the top drawn like the
    # border, and short hair-like fibres all over it, light.
    nut = [(0.96 * math.cos(a), math.sin(a)) for a in (2 * math.pi * k / 120 for k in range(120))]
    eyes = [_ring(x, y, 0.1, 0.08, 20) for x, y in ((-0.2, -0.8), (0.2, -0.8), (0.0, -0.6))]
    fibres = []
    for row in range(-3, 5):
        y = row * 0.2
        across = 0.96 * math.sqrt(max(0.0, 1 - (y / 0.98) ** 2))
        n = max(1, int(across / 0.17))
        for i in range(n):
            x = -across + (2 * across) * (i + 0.5 + 0.3 * ((row + i) % 2)) / (n + 0.3)
            if y < -0.45 and abs(x) < 0.35:
                continue                        # leave the eyes clear
            lean = x * 0.12                     # following the coconut's round
            fibres.append([(x - lean * 0.5, y - 0.06), (x, y), (x + lean * 0.5, y + 0.06)])
    out["coconut"] = (nut, fibres, eyes)


    # A bunch of three bananas (the owner, 2026-10-09: the traced one "doesnt look natural"): three
    # curved bananas from one stem at the upper left, each tapering to a blunt tip at the right, the
    # lower ones longer and lower; the outline is all of them together, and the edges where one lies
    # over the next and their ridges are light.
    def banana(c1, end, width):
        sx, sy = 0.0, 0.0
        centre = [((1 - u) ** 2 * sx + 2 * (1 - u) * u * c1[0] + u * u * end[0],
                   (1 - u) ** 2 * sy + 2 * (1 - u) * u * c1[1] + u * u * end[1]) for u in (k / 40 for k in range(41))]
        upper, lower = [], []
        for k, (x, y) in enumerate(centre):
            a, b = centre[max(0, k - 1)], centre[min(40, k + 1)]
            tx, ty = b[0] - a[0], b[1] - a[1]
            n = math.hypot(tx, ty) or 1.0
            nx, ny = ty / n, -tx / n                                   # to the banana's upper side
            u = k / 40
            w = width * (min(1.0, u / 0.25) ** 0.7) * (1 - 0.55 * max(0.0, (u - 0.75) / 0.25) ** 2)
            w = max(w, 0.018)
            upper.append((x + nx * w, y + ny * w))
            lower.append((x - nx * w, y - ny * w))
        return upper + lower[::-1], upper, centre
    stalk = [(-0.07, -0.02), (-0.11, -0.1), (-0.04, -0.13), (0.03, -0.04)]
    b1 = banana((0.18, 0.42), (0.98, 0.12), 0.095)
    b2 = banana((0.14, 0.66), (1.02, 0.36), 0.105)
    b3 = banana((0.1, 0.9), (0.96, 0.62), 0.115)
    outline_b = _envelope([stalk, b1[0], b2[0], b3[0]], (0.35, 0.42), rays=480)
    seams = [b2[1][6:39], b3[1][6:39]]                                  # where one lies over the next
    ridges = [b1[2][8:38], b2[2][8:38], b3[2][8:38]]
    out["bananas"] = (outline_b, seams + ridges)

    # An anchor, traced from the owner's picture (550 pixels across): the ring on top, the stock with its
    # round ends, the shank, the curved arms with their barbs; the ring's hole and the shank's middle
    # line, light.
    half = [(275, 18), (300, 24), (316, 48), (312, 78), (296, 98), (297, 150), (378, 150), (395, 143), (413, 152),
            (416, 170), (402, 185), (380, 180), (300, 180), (302, 300), (306, 372), (335, 385), (382, 368),
            (410, 330), (395, 318), (455, 272), (462, 335), (442, 326), (424, 372), (380, 420), (320, 447), (275, 462)]
    whole = half + [(550 - x, y) for x, y in reversed(half[1:-1])]
    ring_hole = _ring(275, 60, 22, 22, 28)
    whole = _smooth(whole, closed=True, steps=4)
    out["anchor"] = ([(x / 550, y / 550) for x, y in whole],
                     [[(x / 550, y / 550) for x, y in line] for line in (ring_hole, [(275, 100), (275, 456)])])

    # A monstera leaf, traced from the owner's picture (1920 pixels square): four slits cut in from the
    # right and lower edges and two from the left, four holes (drawn like the border); the midrib and the
    # curved vein marks, light.
    mon = _smooth([(600, 270), (625, 260), (750, 280), (860, 330), (912, 405), (906, 560), (897, 650), (907, 672),
                   (945, 620), (970, 520), (970, 420), (960, 340), (1000, 335), (1100, 370), (1182, 445),
                   (1160, 600), (1120, 750), (1116, 850), (1142, 880), (1200, 820), (1240, 700), (1272, 580),
                   (1285, 478), (1400, 540), (1500, 650), (1530, 740), (1450, 880), (1350, 1000), (1280, 1100),
                   (1272, 1165), (1300, 1170), (1400, 1110), (1530, 980), (1612, 842), (1642, 900), (1650, 1050),
                   (1640, 1200), (1590, 1290), (1500, 1330), (1350, 1370), (1212, 1412), (1170, 1480),
                   (1120, 1580), (1020, 1650), (870, 1680), (700, 1640), (660, 1598), (760, 1560), (900, 1500),
                   (945, 1460), (930, 1425), (880, 1410), (820, 1430), (720, 1500), (620, 1535), (500, 1500),
                   (400, 1400), (330, 1250), (292, 1050), (286, 885), (305, 875), (380, 940), (470, 980),
                   (560, 970), (640, 905), (672, 862), (600, 850), (480, 830), (395, 790), (370, 730),
                   (375, 620), (420, 500), (500, 440), (560, 390)], closed=True, steps=5)

    def hole(cx, cy, rx, ry, deg):
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        return [(cx + rx * math.cos(a) * c - ry * math.sin(a) * s, cy + rx * math.cos(a) * s + ry * math.sin(a) * c)
                for a in (2 * math.pi * k / 24 for k in range(25))]
    holes = [hole(540, 695, 65, 45, 22), hole(985, 795, 24, 68, 12), hole(1312, 915, 48, 70, 32),
             hole(800, 1225, 90, 44, -25)]
    veins = [[(655, 310), (1190, 1385)]] + [_smooth(v, steps=6) for v in (
        [(585, 525), (630, 565), (682, 575)], [(822, 388), (842, 470), (828, 565)], [(1125, 500), (1090, 590), (1050, 660)],
        [(1395, 618), (1385, 690), (1350, 742)], [(665, 762), (740, 786), (820, 786)], [(660, 1010), (750, 1045), (830, 1022)],
        [(405, 1118), (480, 1165), (568, 1170)], [(1220, 990), (1180, 1080), (1140, 1150)],
        [(1575, 1110), (1530, 1200), (1435, 1260)], [(950, 1280), (1010, 1305), (1083, 1302)],
        [(405, 1338), (560, 1390), (715, 1348)], [(960, 1563), (1010, 1560), (1058, 1527)])]
    scale = lambda line: [(x / 1920, y / 1920) for x, y in line]
    # The holes are inside the leaf: light, like the veins (the owner: words may cross them, not the edge).
    out["monstera"] = (scale(mon), [scale(v) for v in veins] + [scale(h) for h in holes])

    return out


SHELLS = _shells()


def _spokes(kind: str) -> list[list[tuple[float, float]]]:
    """Light lines from a shape's middle out towards each of its points, petals or wings: the
    outline's corners farthest from the middle, each standing well out from its neighbours."""
    pts = OUTLINES.get(kind)
    if not pts:
        return []
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    wide = ASPECTS.get(kind, 1.0)             # its own proportions, not the 1 x 1 box's
    dist = [math.hypot((px - cx) * wide, py - cy) for px, py in pts]
    n, mean = len(pts), sum(dist) / len(dist)
    near = max(1, n // 16)
    tips = [i for i in range(n) if dist[i] > mean * 1.12
            and all(dist[i] >= dist[(i + j) % n] for j in range(1, near + 1))
            and all(dist[i] > dist[(i - j) % n] for j in range(1, near + 1))]     # one line per flat tip
    out = []
    for i in tips:
        px, py = pts[i]
        start = 0.32 if kind == "flower" else 0.18          # the flower's lines begin outside its middle
        out.append([(cx + (px - cx) * start, cy + (py - cy) * start), (cx + (px - cx) * 0.86, cy + (py - cy) * 0.86)])
    return out


# The shapes that carry detail lines (the owner, 2026-10-09: "you can add detailing to the other
# shapes too", its colour, opacity and weight the player's: Edits.detail_*).
SPOKE_SHAPES = ("star", "plump_star", "star4", "star6", "slim_star6", "flower")


def _leaf_veins() -> list[list[tuple[float, float]]]:
    """The leaf's veins (the owner, 2026-10-09: "more interior detail veins"): the midrib from where the
    stalk meets the blade to the tip, and side veins from it towards the tip on both sides, each
    ending a little short of the edge -- in the leaf's 1 x 1 box, measured at its own proportions."""
    pts = OUTLINES.get("leaf")
    if not pts:
        return []
    wide = ASPECTS.get("leaf", 1.0)
    real = [(x * wide, y) for x, y in pts]
    # The tip and the stalk's end: the two corners farthest apart.
    best = (0.0, 0, 0)
    for i in range(0, len(real), 2):
        for j in range(i + 1, len(real), 2):
            d = (real[i][0] - real[j][0]) ** 2 + (real[i][1] - real[j][1]) ** 2
            if d > best[0]:
                best = (d, i, j)
    a, b = real[best[1]], real[best[2]]
    tip, stalk = (a, b) if a[1] < b[1] else (b, a)          # the tip is the upper one (it points up to the right)
    length = math.hypot(tip[0] - stalk[0], tip[1] - stalk[1])
    ux, uy = (tip[0] - stalk[0]) / length, (tip[1] - stalk[1]) / length
    nx, ny = -uy, ux

    def at(f, v=0.0):
        return (stalk[0] + ux * f * length + nx * v, stalk[1] + uy * f * length + ny * v)

    def inside_leaf(x, y):
        hit = False
        for (ax, ay), (bx, by) in zip(real, real[1:] + real[:1]):
            if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                hit = not hit
        return hit
    base = 0.2                                                  # where the stalk meets the blade
    while base < 0.5 and not inside_leaf(*at(base, 0.04)):
        base += 0.01
    veins = [[at(base), at(0.96)]]
    for k in range(7):
        f = base + (0.9 - base) * (k + 0.6) / 7.5
        for side in (1, -1):
            sx, sy = at(f)
            dx, dy = ux * 0.75 + nx * side * 0.66, uy * 0.75 + ny * side * 0.66      # slanting towards the tip
            n = math.hypot(dx, dy)
            dx, dy = dx / n, dy / n
            reach = 0.0
            while reach < 1.0 and inside_leaf(sx + dx * (reach + 0.01), sy + dy * (reach + 0.01)):
                reach += 0.01
            if reach > 0.05:
                end = reach * 0.85
                mid = (sx + dx * end * 0.5 - ux * end * 0.06, sy + dy * end * 0.5 - uy * end * 0.06)
                veins.append([(sx, sy), mid, (sx + dx * end, sy + dy * end)])
    return [[(x / wide, y) for x, y in line] for line in veins]


@functools.lru_cache(maxsize=1)
def _butterfly_lines() -> tuple[list, list]:
    """The butterfly's lines (the owner, 2026-10-09: "should have curly antennae and lines for each
    part of its wings"), on the parts _drawn_outlines makes it of: (light lines -- the body, where
    each upper wing meets the lower, three veins in each wing --, the curly antennae, drawn like the
    border), in its 1 x 1 box."""
    wings = [(-0.36, -0.18, 0.4, 0.32, -20), (0.36, -0.18, 0.4, 0.32, 20),
             (-0.26, 0.28, 0.28, 0.24, 25), (0.26, 0.28, 0.28, 0.24, -25)]
    body = (0, 0.02, 0.2, 0.36, 0)

    def edge(part, t):
        cx, cy, rx, ry, turn_deg = part
        c, s = math.cos(math.radians(turn_deg)), math.sin(math.radians(turn_deg))
        u, v = rx * math.cos(t), ry * math.sin(t)
        return (cx + u * c - v * s, cy + u * s + v * c)

    def within(part, x, y):
        cx, cy, rx, ry, turn_deg = part
        c, s = math.cos(math.radians(turn_deg)), math.sin(math.radians(turn_deg))
        return (((x - cx) * c + (y - cy) * s) / rx) ** 2 + ((-(x - cx) * s + (y - cy) * c) / ry) ** 2 <= 1
    rim = [edge(part, 2 * math.pi * k / 180) for part in wings + [body] for k in range(180)]
    x0, x1 = min(p[0] for p in rim), max(p[0] for p in rim)
    y0, y1 = min(p[1] for p in rim), max(p[1] for p in rim)
    unit = lambda p: ((p[0] - x0) / (x1 - x0), (p[1] - y0) / (y1 - y0))
    light = [[unit(p) for p in _ring(0, 0.02, 0.06, 0.34, 40)]]                  # the body
    for upper, lower in ((wings[0], wings[2]), (wings[1], wings[3])):            # upper meets lower
        seam = [edge(upper, 2 * math.pi * k / 240) for k in range(240)]
        seam = [p for p in seam if within(lower, *p) and abs(p[0]) > 0.06]
        seam.sort(key=lambda p: p[0])
        if seam:
            light.append([unit(p) for p in seam])
    for part in wings:                                                       # three veins in each
        cx, cy = part[0], part[1]
        root = (0.06 if cx > 0 else -0.06, cy * 0.4)
        for k in (-1, 0, 1):
            far = (cx + (cx - root[0]) * 0.55 + k * 0.12 * (1 if cy < 0 else -1), cy + (cy - root[1]) * 0.55 + k * 0.12)
            if within(part, *far):
                light.append([unit(root), unit(far)])
    curls = []
    for side in (-1, 1):                                                     # curly antennae
        stalk = [(side * 0.02 + side * 0.22 * u ** 1.3, -0.3 - 0.42 * u) for u in (k / 20 for k in range(21))]
        ex, ey = stalk[-1]
        # The stalk, and its curled tip a little circle of its own (the owner, 2026-10-09: a special
        # border puts its rope or vine on the stalk and one flower or leaf on the circle).
        curls.append([unit(p) for p in stalk])
        curls.append([unit(p) for p in _ring(ex + side * 0.035, ey - 0.03, 0.04, 0.04, 16)])
    return light, curls


@functools.lru_cache(maxsize=None)
def details(kind: str) -> tuple:
    """A shape's detail lines in its 1 x 1 box, each a tuple of points; none for most shapes."""
    base, flip_h, flip_v = _unflipped(kind)
    if base != kind:
        return tuple(tuple(_mirror(line, flip_h, flip_v)) for line in details(base))
    if kind in SHELLS:
        return tuple(tuple(line) for line in SHELLS[kind][1])
    if kind == "flower":                # its petals' lines and a little circle in the middle, a daisy's
        r, wide = 0.12, ASPECTS.get("flower", 1.0)
        middle = tuple((0.5 + r / wide * math.cos(a), 0.5 + r * math.sin(a)) for a in (2 * math.pi * k / 32 for k in range(33)))
        return tuple(tuple(line) for line in _spokes(kind)) + (middle,)
    if kind in SPOKE_SHAPES:
        return tuple(tuple(line) for line in _spokes(kind))
    if kind == "leaf":
        return tuple(tuple(line) for line in _leaf_veins())
    if kind == "butterfly":
        return tuple(tuple(line) for line in _butterfly_lines()[0])
    return ()


def decor(kind: str) -> tuple:
    base, flip_h, flip_v = _unflipped(kind)
    if base != kind:
        return tuple(tuple(_mirror(line, flip_h, flip_v)) for line in decor(base))
    """Lines drawn like a shape's border, beside its outline: the hibiscus's
    stamen and pollen."""
    if kind == "butterfly":
        return tuple(tuple(line) for line in _butterfly_lines()[1])
    return tuple(tuple(line) for line in SHELLS[kind][3]) if kind in SHELLS else ()


def _raw_aspect(kind: str) -> float:
    xs, ys = zip(*_drawn_outlines()[kind])
    return (max(xs) - min(xs)) / (max(ys) - min(ys))


DRAWN_SHAPES = ("flower", "butterfly", "clover", "spade", "leaf")
# Their widths for their heights as traced (_raw_aspect), fixed so nothing is traced at start-up.
FLOWER_ASPECT, BUTTERFLY_ASPECT, CLOVER_ASPECT, SPADE_ASPECT, LEAF_ASPECT = 0.897, 1.447, 1.06, 0.872, 1.171


class _Outlines(dict):
    """The unit outlines; the traced ones (DRAWN_SHAPES) are worked out the first time one is
    asked for, not as the patcher starts (Codex, #575: tracing takes a noticeable moment)."""
    def __missing__(self, kind: str):
        if kind not in DRAWN_SHAPES:
            raise KeyError(kind)
        # Traced once, ahead of time, into data/tree_shapes.json (scripts/build_tree_shapes.py): tracing
        # here froze the window for seconds the first time a new shape was picked (Codex, #575).
        try:
            stored = json.loads(TREE_SHAPES_FILE.read_text(encoding="utf-8"))
            for name in DRAWN_SHAPES:
                self[name] = [(float(x), float(y)) for x, y in stored[name]]
        except (OSError, ValueError, KeyError, TypeError):
            for name, points in traced_unit_outlines().items():   # the file is missing: trace them
                self[name] = points
        return self[kind]

    def get(self, kind, default=None):
        try:
            return self[kind]
        except KeyError:
            return default


def traced_unit_outlines() -> dict[str, list[tuple[float, float]]]:
    """DRAWN_SHAPES traced and fitted to a 1 x 1 box (what data/tree_shapes.json holds)."""
    out = {}
    for name, points in _drawn_outlines().items():
        xs, ys = zip(*points)
        out[name] = [((px - min(xs)) / (max(xs) - min(xs)), (py - min(ys)) / (max(ys) - min(ys)))
                     for px, py in points]
    return out


TREE_SHAPES_FILE = Path(__file__).resolve().parents[1] / "data" / "tree_shapes.json"


OUTLINES = _Outlines(_unit_outlines())


SVG_DASHES = {"dotted": "1.5 4", "dashed": "8 5", "dashdot": "8 4 1.5 4"}
TK_DASHES = {"dotted": (2, 4), "dashed": (8, 5), "dashdot": (8, 4, 2, 4)}
GDI_DASHES = {"dotted": 2, "dashed": 1, "dashdot": 3}       # GDI+'s dash styles


# Each shape's own width for its height (the owner: "I want the shapes to not look so squashed
# horizontally. or vertically, by default"): a portrait's frame is drawn this wide for a portrait's
# height until the player resizes it.  The heart's and the star's are their outlines' own; a
# diamond is a playing card's.  A rectangle, a rounded rectangle and an oval fill the portrait.
ASPECTS = {"rect": 1.0, "rounded": 1.0, "circle": 1.0, "heart": 1.107, "star": 1.051, "triangle": 1.155, "diamond": 0.7, "cross": 0.75, "x": 1.0,
           "plus": 1.0, "hexagon": 0.866, "octagon": 1.0, "trapezoid": 1.2, "pentagon": 1.051, "star4": 0.863, "star6": 0.866, "plump_star": 1.051, "slim_star6": 0.866,
                "arrow_h": 1.6, "arrow_v": 0.625, "arch": 0.655,
                "oval_wide": 1.5}
ASPECTS.update({name: round(shape[2], 3) for name, shape in SHELLS.items()})
# The owner's shapes of 2026-10-08 take their own drawn proportions.
ASPECTS.update({"flower": FLOWER_ASPECT, "butterfly": BUTTERFLY_ASPECT, "clover": CLOVER_ASPECT, "spade": SPADE_ASPECT,
                "leaf": LEAF_ASPECT})      # _raw_aspect's, fixed (tests/test_tree_new_shapes.py checks them)
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


def flipped_kind(kind: str, flip_h: bool, flip_v: bool) -> str:
    """A shape mirrored across (h) and/or up and down (v): "heart~h", "anchor~v", "star~hv".  A
    rectangle, rounded square, circle or oval looks the same flipped, so it keeps its own name."""
    if not (flip_h or flip_v) or OUTLINES.get(kind) is None:
        return kind
    return f"{kind}~{'h' if flip_h else ''}{'v' if flip_v else ''}"


def base_kind(kind: str) -> str:
    """A shape's own name, without its flips."""
    return kind.partition("~")[0]


def _unflipped(kind: str) -> tuple[str, bool, bool]:
    base, _, how = kind.partition("~")
    return base, "h" in how, "v" in how


def _mirror(points, flip_h: bool, flip_v: bool):
    return [((1 - px) if flip_h else px, (1 - py) if flip_v else py) for px, py in points]


def outline(kind: str, x: float, y: float, w: float, h: float) -> list[tuple[float, float]] | None:
    """A many-sided shape's corners in the box, or None for a square, rounded square, circle or oval
    (a flipped one, flipped_kind, mirrored)."""
    base, flip_h, flip_v = _unflipped(kind)
    unit = OUTLINES.get(base)
    if unit and (flip_h or flip_v):
        unit = _mirror(unit, flip_h, flip_v)
        if flip_h != flip_v:
            unit = unit[::-1]                     # the same way round as before (the special borders' outside)
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
class Poly:
    """A filled outline of any corners -- a special border's rope, vine, leaves and flowers (the owner,
    2026-10-09: "I want the vines to be vines, not just lines"); no `stroke` / `width`: fill only."""
    points: list
    fill: str | None
    stroke: str = ""
    width: float = 0.0
    opacity: float = 1.0


@dataclass
class Text:
    x: float
    y: float                            # the baseline
    text: str
    size: float
    colour: str
    bold: bool = False
    centre: bool = False                # x is the middle (else the start)
    end: bool = False                   # x is the end: right-aligned words (Edits.text_align)
    angle: float = 0.0                  # turned this many degrees (clockwise) about (x, y): Edits.turn_words
    mirror_h: bool = False              # mirrored across, about x (Edits.flip_words)
    mirror_v: bool = False              # mirrored up and down, about the middle of its letters
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
    # The words formatted word by word (a portrait's own text: node_runs): (text, style) pieces drawn
    # one after another as run_look says; None when every word has the item's own look.
    runs: list | None = None
    script: str = ""                    # the role's superscript or subscript, for runs (run_look)


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
    turn_of = {f.id: k for k, f in enumerate(lay.families)}
    for colour, points, fid, piece in lines(lay):
        key = family_key(v, fams[fid])
        colour = scheme_colour(lay.edits, "lines", turn_of[fid] / max(1, len(turn_of)), turn_of[fid]) or colour
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
    # With Shrink to fit, the footer goes onto as many lines as keep it inside that width, rather than
    # widening the page again (Codex, #575); otherwise it is the one line it always was.
    footer_lines = (_wrap(key_text, max(20, int((lay.edits.fit_width - 80) / 6.8)))
                    if lay.edits.fit_width and len(key_text) * 6.8 > lay.edits.fit_width - 80 else [key_text])
    longest = max(len(line) for line in footer_lines)
    if plate:
        add(Shape("rect", middle - longest * 3.4, lay.height - 110, longest * 6.8, 30 + 18 * (len(footer_lines) - 1),
                  plate_colour, move="footer", width=0, fill=plate_colour, radius=10, target=("plate",)))
    for k, line in enumerate(footer_lines):
        add(Text(middle, lay.height - 90 + 18 * k, line, 13, ink, centre=True, role="footer", move="footer",
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


MOVABLE = {"title": "the title", "subtitle": "the subtitle", "key": "the Key", "others": "the Other "
           "Members heading", "others_note": "the line under the Other Members heading",
           "footer": "the footer"}   # and "label<generation>": that generation's label


MARGIN = 10                             # nothing dragged goes nearer the page's edge than this


def _extent(item) -> tuple[float, float, float, float] | None:
    """An item's box on the page (words by their likely width)."""
    if isinstance(item, Line):
        xs, ys = zip(*item.points)
        return min(xs), min(ys), max(xs), max(ys)
    if isinstance(item, Poly):
        xs, ys = zip(*item.points)
        return min(xs), min(ys), max(xs), max(ys)
    if isinstance(item, Shape):
        xs, ys = zip(*item.points())
        return min(xs), min(ys), max(xs), max(ys)
    if isinstance(item, Text):
        width = len(item.text) * item.size * 0.55
        left = item.x - width / 2 if item.centre else item.x - width if item.end else item.x
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
        if style.get("script") in SCRIPTS and item.runs:      # each run raised or lowered on its own
            item.script = style["script"]
        elif style.get("script") in SCRIPTS:    # smaller, raised or lowered: drawn so everywhere
            shrink, shift = SCRIPTS[style["script"]]
            item.y += item.size * shift
            item.size *= shrink


def run_look(item: "Text", style: dict) -> dict:
    """How one run of a formatted Text is drawn: its own style over the item's (its role's) look --
    bold, italic, underline, strike, colour -- and its size and how far its baseline is moved
    (superscript and subscript as SCRIPTS draws a role's)."""
    script = style.get("script", item.script)
    shrink, shift = SCRIPTS.get(script, (1.0, 0.0))
    return {"bold": style.get("bold", item.bold), "italic": style.get("italic", item.italic),
            "underline": style.get("underline", item.underline), "strike": style.get("strike", item.strike),
            "colour": style.get("colour", item.colour), "size": item.size * shrink, "dy": item.size * shift}


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


def _resample(points: list[tuple[float, float]], step: float) -> list[tuple[float, float, float, float]]:
    """A closed outline walked in steps of `step`: (x, y, and the outward normal's dx, dy) at each."""
    pts = points + points[:1]
    lengths = [math.hypot(bx - ax, by - ay) for (ax, ay), (bx, by) in zip(pts, pts[1:])]
    total = sum(lengths)
    if total <= 0:
        return []
    area = sum(ax * by - bx * ay for (ax, ay), (bx, by) in zip(pts, pts[1:]))
    turn_out = 1 if area > 0 else -1             # which side is outside, whichever way the corners run
    n = max(12, int(total / step))
    out, i, walked = [], 0, 0.0
    for k in range(n):
        d = total * k / n
        while i < len(lengths) - 1 and walked + lengths[i] < d:
            walked += lengths[i]
            i += 1
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        f = (d - walked) / lengths[i] if lengths[i] else 0.0
        tx, ty = (bx - ax) / (lengths[i] or 1), (by - ay) / (lengths[i] or 1)
        out.append((ax + (bx - ax) * f, ay + (by - ay) * f, ty * turn_out, -tx * turn_out))
    return out


@functools.lru_cache(maxsize=512)
def _open_places(kind: str, w: float, h: float, radius: float, angle: float) -> tuple:
    """The places along a vine border's outline (its _resample steps) where leaves and flowers may go:
    not in a narrow notch -- a gap of the outside too narrow for them on both its sides, a Monstera's
    slit, a heart's dip, a star's inner corner -- but in a wide one, the anchor's (the owner,
    2026-10-09: "move some of the bottom leaves/flowers to those giant notches").  The same for a
    portrait of the same shape and size wherever it is, so worked out once."""
    outline_points = shape_points(kind, 0.0, 0.0, w, h, radius, angle)
    size = max(6.0, 0.1 * min(w, h))
    walk = _resample(outline_points, size / 8)
    n = len(walk)
    pts = [(x, y) for x, y, _nx, _ny in walk]
    apart = 24                                    # three leaves' lengths along the outline
    near = size * 2.6                            # room for leaves and flowers on both sides of the gap
    out = []
    for k in range(n):
        x, y = pts[k]
        narrow = False
        for j in range(0, n, 2):
            if min(abs(j - k), n - abs(j - k)) <= apart:
                continue
            qx, qy = pts[j]
            if (qx - x) ** 2 + (qy - y) ** 2 < near * near and not inside(outline_points, (x + qx) / 2, (y + qy) / 2):
                narrow = True                     # across a gap of the outside, close by: a narrow notch
                break
        if not narrow or _room_straight_out(outline_points, walk, k, size):
            out.append(k)
    return tuple(out)


def _room_straight_out(outline_points: list, walk: list, k: int, size: float) -> bool:
    """Clear room straight out from step k, and a little either side of straight: the heart's dip, which
    opens wide (the owner, 2026-10-09: a flower there), not a Monstera's slit."""
    n = len(walk)
    nx = sum(walk[(k + d) % n][2] for d in range(-3, 4))
    ny = sum(walk[(k + d) % n][3] for d in range(-3, 4))
    m = math.hypot(nx, ny)
    if m == 0:
        return False
    nx, ny = nx / m, ny / m
    x, y = walk[k][0], walk[k][1]
    for turn_deg in (-30, 0, 30):
        c, s = math.cos(math.radians(turn_deg)), math.sin(math.radians(turn_deg))
        dx, dy = nx * c - ny * s, nx * s + ny * c
        for f in (0.5, 1.0, 1.6, 2.2):
            if inside(outline_points, x + dx * size * f, y + dy * size * f):
                return False
    return True


def _band(path: list[tuple[float, float]], normals: list, half: float, colours: list) -> list:
    """A band `half` wide either side of a closed path, in one filled piece per stretch (each its own
    colour), with its two darker edges."""
    n = len(path)
    out = []
    left = [(x + nx * half, y + ny * half) for (x, y), (nx, ny) in zip(path, normals)]
    right = [(x - nx * half, y - ny * half) for (x, y), (nx, ny) in zip(path, normals)]
    for k in range(n):
        j = (k + 1) % n
        out.append(Poly([left[k], left[j], right[j], right[k]], colours[k], colours[k], 0.6))   # no gaps between
    edge = _shade(colours[0], 0.55)
    out.append(Line(left + left[:1], edge, 1.1))
    out.append(Line(right + right[:1], edge, 1.1))
    return out


def _leaf_items(x: float, y: float, dx: float, dy: float, own: float, base: str) -> list:
    """A leaf `own` long from (x, y) along (dx, dy): filled, its far half shaded, outlined, its midrib."""
    px, py = -dy, dx

    def half(side):
        return [(x + dx * own * u + px * own * 0.32 * math.sin(math.pi * u) * side,
                 y + dy * own * u + py * own * 0.32 * math.sin(math.pi * u) * side) for u in (k / 10 for k in range(11))]
    a, b = half(1), half(-1)
    return [Poly(a + b[::-1][1:-1], base), Poly(b + [(x + dx * own, y + dy * own)], _shade(base, 0.8)),
            Poly(a + b[::-1][1:-1], None, _shade(base, 0.5), 0.9),
            Line([(x, y), (x + dx * own * 0.9, y + dy * own * 0.9)], _shade(base, 0.5), 0.7)]


def _flower_items(cx: float, cy: float, r: float, base: str, turned: float = 0.0, eye: str | None = None) -> list:
    """A hibiscus `r` across at (cx, cy), turned `turned` radians (the owner, 2026-10-09: the flowers
    pointing different ways): its petals outlined, its throat shaded, its deep centre, its stamen."""
    petals = [(cx + r * (0.45 + 0.55 * abs(math.cos(2.5 * (a + 0.3 - turned)))) ** 0.5 * math.cos(a),
               cy + r * (0.45 + 0.55 * abs(math.cos(2.5 * (a + 0.3 - turned)))) ** 0.5 * math.sin(a))
              for a in (2 * math.pi * k / 60 for k in range(60))]
    sx, sy = cx + r * 0.42 * math.cos(turned - math.pi / 4), cy + r * 0.42 * math.sin(turned - math.pi / 4)
    return [Poly(petals, base, _shade(base, 0.55), 0.9),
            Poly(_ring(cx, cy, r * 0.42, r * 0.42, 20)[:-1], _mix(base, eye, 0.35) if eye else _shade(base, 0.85)),
            Poly(_ring(cx, cy, r * 0.2, r * 0.2, 14)[:-1], eye or _shade(base, 0.45)),
            Line([(cx, cy), (sx, sy)], STAMEN, 0.9), Poly(_ring(sx, sy, r * 0.09, r * 0.09, 10)[:-1], STAMEN)]


def _open_band(path: list[tuple[float, float]], half: float, colour: str) -> list:
    """A band `half` wide either side of an open path (a stamen, an antenna), with its darker edges."""
    if len(path) < 2:
        return []
    normals = []
    for k in range(len(path)):
        (ax, ay), (bx, by) = path[max(0, k - 1)], path[min(len(path) - 1, k + 1)]
        m = math.hypot(bx - ax, by - ay) or 1.0
        normals.append(((by - ay) / m, -(bx - ax) / m))
    left = [(x + nx * half, y + ny * half) for (x, y), (nx, ny) in zip(path, normals)]
    right = [(x - nx * half, y - ny * half) for (x, y), (nx, ny) in zip(path, normals)]
    out = [Poly([left[k], left[k + 1], right[k + 1], right[k]], colour, colour, 0.6) for k in range(len(path) - 1)]
    edge = _shade(colour, 0.55)
    return out + [Line(left, edge, 1.0), Line(right, edge, 1.0)]


def sticking_out(kind: str, frame: tuple, outline_points: list) -> list:
    """The shape's lines drawn like its border that stand outside it -- the hibiscus's stamen and pollen,
    the butterfly's antennae -- placed in the frame: (their index in decor(kind), their points, whether
    each is a small circle).  Lines inside the shape (the wave, the coconut's eyes) are not among them."""
    x0, y0, w, h, angle = frame
    cx, cy = x0 + w / 2, y0 + h / 2
    out = []
    for i, line in enumerate(decor(kind)):
        pts = [(x0 + u * w, y0 + v * h) for u, v in line]
        if angle:
            pts = [(cx + dx, cy + dy) for dx, dy in (turn(px - cx, py - cy, angle) for px, py in pts)]
        outside = sum(not inside(outline_points, px, py) for px, py in pts)
        if outside < 0.25 * len(pts):          # mostly inside: an inside detail (the wave), left as it is
            continue
        closed = math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 0.02 * max(w, h)
        out.append((i, pts, closed))
    return out


def _sticking_out(border: str, kind: str, frame: tuple, outline_points: list, size: float, colour_of,
                 flower_look=None) -> list:
    """The special border on the parts standing outside the shape (the owner, 2026-10-09): the rope or
    the vine along each line, and on each small circle one flower -- a leaf on a vine of leaves only --
    or, for the rope, a rope ring."""
    items = []
    for n_out, (_i, pts, closed) in enumerate(sticking_out(kind, frame, outline_points)):
        if closed:
            cx = sum(px for px, _py in pts) / len(pts)
            cy = sum(py for _px, py in pts) / len(pts)
            r = sum(math.hypot(px - cx, py - cy) for px, py in pts) / len(pts)
            if border == "rope":
                ring = _ring(cx, cy, max(r, size * 0.6), max(r, size * 0.6), 24)[:-1]
                items += _open_band(ring + ring[:2], size * 0.3, colour_of("rope", 0.0, 0))
            elif border == "vine_leaves":
                ox, oy = cx - (frame[0] + frame[2] / 2), cy - (frame[1] + frame[3] / 2)
                m = math.hypot(ox, oy) or 1.0
                items += _leaf_items(cx, cy, ox / m, oy / m, max(r * 2.2, size * 0.7), colour_of("leaf", 0.0, 0))
            else:
                petals, eye = flower_look(0.0, n_out, 3.0) if flower_look else (colour_of("flower", 0.0, 0), None)
                items += _flower_items(cx, cy, max(r * 1.3, size * 0.3), petals,
                                       turned=(cx * 7.31 + cy * 3.17) % (2 * math.pi), eye=eye)
        else:
            if border == "rope":
                items += _open_band(pts, size * 0.35, colour_of("rope", 0.0, 0))
            else:
                items += _open_band(pts, max(0.9, size * 0.07), colour_of("vine", 0.0, 0))
    return items


def special_border(border: str, kind: str, frame: tuple, radius: float, edits: "Edits | None" = None) -> list:
    """A special border round a portrait framed (x, y, w, h, angle), along its own outline whatever the
    shape (the owner, 2026-10-09): the braided rope, or a vine -- a real stem -- with leaves, hibiscus
    or both, filled, shaded and outlined in its colours (Edits.special_*), the leaves and flowers small,
    on the outside and never in a notch.  Items to draw (Poly and Line), already turned."""
    e = edits or Edits()
    x0, y0, w, h, angle = frame
    outline_points = shape_points(kind, x0, y0, w, h, radius, angle)
    mode, pick = e.special_mode, e.special_pick
    palette = list(e.special_palette[:e.special_count])

    def flower_look(t: float, j: int, salt: float = 0.0) -> tuple[str, str | None]:
        """A flower's petals and eye: in natural colours, the chosen hibiscus -- or all of them by
        turns or blending round the border; else the mode's colour, its eye shaded from it."""
        if mode == "natural":
            name = e.hibiscus
            if name == "alternate":               # by turns round the border
                name = HIBISCUS_ORDER[j % len(HIBISCUS_ORDER)]
            elif name == "gradient":              # blending from one to the next round the border
                return (_blend_round([HIBISCUS[k][1] for k in HIBISCUS_ORDER], t),
                        _blend_round([HIBISCUS[k][2] for k in HIBISCUS_ORDER], t))
            _words, petals, eye = HIBISCUS[name]
            return petals, eye
        return colour_of("flower", t, j), None

    def colour_of(part: str, t: float, j: int) -> str:
        if mode == "pick":
            return pick.get(part, NATURAL[part])
        decorated = part == "flower" or (part == "leaf" and border == "vine_leaves") or part == "rope"
        if mode == "rainbow" and decorated:
            return _shade(_blend_round(list(RAINBOW), t), RAINBOW_STRENGTHS[e.rainbow_strength][1])
        if mode == "alternate" and decorated:
            return palette[j % len(palette)]
        if mode == "gradient" and decorated:
            return _blend_round(palette, t)
        return NATURAL[part]

    if border == "rope":
        thick = max(5.0, 0.07 * min(w, h))
        walk = _resample(outline_points, thick / 3)
        if not walk:
            return []
        path = [(x, y) for x, y, _nx, _ny in walk]
        normals = [(nx, ny) for _x, _y, nx, ny in walk]
        n = len(walk)
        twists = max(1, n // 3)
        colours = [colour_of("rope", (k // 3) / twists, k // 3) for k in range(n)]
        items = _band(path, normals, thick / 2, colours)
        r = thick / 2
        for k in range(0, n - 3, 3):                 # a strand crossing from the inner edge to the outer
            x0_, y0_, nx0, ny0 = walk[k]
            x1_, y1_, nx1, ny1 = walk[k + 3]
            mx, my = (x0_ + x1_) / 2, (y0_ + y1_) / 2
            items.append(Line([(x0_ - nx0 * r, y0_ - ny0 * r), (mx + (nx0 + nx1) * r * 0.1, my + (ny0 + ny1) * r * 0.1),
                               (x1_ + nx1 * r, y1_ + ny1 * r)], _shade(colours[k], 0.6), 1.0))
        return items + _sticking_out(border, kind, frame, outline_points, thick, colour_of, flower_look)

    size = max(6.0, 0.1 * min(w, h))                 # a leaf's length: small, outside the portrait
    walk = _resample(outline_points, size / 8)
    if not walk:
        return []
    n = len(walk)
    wave = size * 0.12
    path = [(x + nx * wave * (1 + math.sin(2 * math.pi * k / 16)) / 2, y + ny * wave * (1 + math.sin(2 * math.pi * k / 16)) / 2)
            for k, (x, y, nx, ny) in enumerate(walk)]
    normals = [(nx, ny) for _x, _y, nx, ny in walk]
    stem = colour_of("vine", 0.0, 0)
    items = _band(path, normals, max(0.9, size * 0.07), [stem] * n)
    leaves, flowers = border in ("vine_leaves", "vine_both"), border in ("vine_flowers", "vine_both")
    pattern = ["leaf", "leaf", "flower"] if leaves and flowers else ["leaf"] if leaves else ["flower"]
    # Leaves alone or flowers alone sparser than the mix, like it (the owner, 2026-10-09: "similar but
    # different, not too many clustered").
    spacing = {("leaf",): 12, ("flower",): 16}.get(tuple(pattern), 10)
    jitter = 0.32 if len(pattern) > 1 else 0.24
    # Only where the outline is not in a notch (the owner: none there), and spread evenly over those
    # stretches, so a star or an anchor is as full as a circle (the owner: "more on the sparser shapes").
    open_places = list(_open_places(kind, round(w, 1), round(h, 1), round(radius, 2), round(angle, 1)))
    count = max(3, len(open_places) // spacing) if open_places else 0
    if open_places and len(open_places) < 0.75 * n:
        count += 4                                    # a sparse shape: just a few more (the owner, 2026-10-09)
    def wobble(j: int, salt: float) -> float:
        """-1 to 1, the same for the same leaf or flower every time it is drawn."""
        v = math.sin((j + 1) * 12.9898 + salt * 78.233) * 43758.5453
        return (v - math.floor(v)) * 2 - 1
    placed_at = []
    flowers_drawn = 0
    # The bunch of bananas' far tip takes a flower among its leaves (the owner, 2026-10-09): the spot
    # nearest the outline's farthest point along the bunch.
    tip_flower = None
    if leaves and flowers and _unflipped(kind)[0] == "bananas" and count:
        far = max(range(n), key=lambda i: walk[i][0])     # the middle banana's end, the bunch's rightmost
        spots_even = [open_places[min(len(open_places) - 1, max(0, int((j + 0.5 + jitter * wobble(j, 1.0))
                                                                         * len(open_places) / count)))]
                      for j in range(count)]
        tip_flower = min(range(count), key=lambda j: min(abs(spots_even[j] - far), n - abs(spots_even[j] - far)))
    for j in range(count):
        # Irregularly even (the owner, 2026-10-09): each a little off its even place, a little bigger or
        # smaller, leaning a little more or less.
        spot = (j + 0.5 + jitter * wobble(j, 1.0)) * len(open_places) / count
        k = open_places[min(len(open_places) - 1, max(0, int(spot)))]
        if len(pattern) == 1 and placed_at and min(abs(k - placed_at[-1]), n - abs(k - placed_at[-1])) < 0.6 * n / count:
            continue                                  # never two bunched together
        placed_at.append(k)
        own = size * (1 + 0.12 * wobble(j, 2.0))
        x, y = path[k]
        # Outward as the outline runs a few steps either side: at a sharp corner -- the heart's dip --
        # one step's own direction can point inside (the owner, 2026-10-09: the dip's flower above it).
        nx = sum(normals[(k + d) % n][0] for d in range(-3, 4))
        ny = sum(normals[(k + d) % n][1] for d in range(-3, 4))
        m = math.hypot(nx, ny)
        if m == 0:
            continue
        nx, ny = nx / m, ny / m
        if inside(outline_points, x + nx * size * 0.7, y + ny * size * 0.7):
            nx, ny = -nx, -ny
            if inside(outline_points, x + nx * size * 0.7, y + ny * size * 0.7):
                continue                              # no outside here at all
        tx, ty = -ny, nx
        what = "flower" if j == tip_flower else pattern[j % len(pattern)]
        tpos = j / count
        if what == "leaf":
            lean = (0.6 if j % 2 == 0 else -0.6) * (1 + 0.3 * wobble(j, 3.0))        # outward, leaning one way then the other
            dx, dy = nx * 0.8 + tx * lean, ny * 0.8 + ty * lean
            m = math.hypot(dx, dy)
            if m == 0:
                continue
            dx, dy = dx / m, dy / m
            items += _leaf_items(x, y, dx, dy, own, colour_of("leaf", tpos, j))
        else:
            r = own * 0.55
            cx, cy = x + nx * r * 0.95, y + ny * r * 0.95                         # just outside the vine
            petals, eye = flower_look(tpos, flowers_drawn)             # by the flowers alone, not the leaves
            flowers_drawn += 1
            items += _flower_items(cx, cy, r, petals, turned=math.pi * wobble(j, 4.0), eye=eye)
    return items + _sticking_out(border, kind, frame, outline_points, size, colour_of, flower_look)


def scheme_colour(e: "Edits", part: str, t: float, j: int) -> str | None:
    """The colour `part` (SCHEME_PARTS) takes at `t` (0-1 of the way round or across) or by turn `j`, or
    None when the player keeps it as set."""
    mode = e.schemes.get(part, "own")
    if mode == "rainbow":
        return _shade(_blend_round(list(RAINBOW), t), RAINBOW_STRENGTHS[e.rainbow_strength][1])
    if mode == "alternate":
        palette = list(e.special_palette[:e.special_count]) or ["#000000"]
        return palette[j % len(palette)]
    return None


def scheme_outline(e: "Edits", part: str, kind: str, frame: tuple, radius: float, width: float,
                   opacity: float = 1.0, dash: str = "", target: tuple | None = None, pieces: int = 48) -> list:
    """An outline drawn in `part`'s colour scheme, piece by piece round it: a rainbow, or the colours by
    turns in even arcs."""
    x, y, w, h, angle = frame
    walk = _resample(shape_points(kind, x, y, w, h, radius, angle), max(1.0, (w + h) / (pieces * 2)))
    n = len(walk)
    if n < 2:
        return []
    count = max(1, e.special_count)
    arcs = 2 * count if count > 2 else 6
    out = []
    for i in range(pieces):
        a, b = i * n // pieces, (i + 1) * n // pieces
        pts = [walk[k % n][:2] for k in range(a, b + 1)]
        colour = scheme_colour(e, part, i / pieces, i * arcs // pieces) or "#000000"
        out.append(Line(pts, colour, width, target=target, opacity=opacity, dash=dash))
    return out


def _rank(lay: Layout, pid: int) -> tuple[float, int]:
    """Where a villager comes across the tree, in number order: (0-1, their turn)."""
    ranks = lay.__dict__.get("_ranks")
    if ranks is None:
        people = lay.village.people
        order = sorted(lay.x, key=lambda q: (people[q].number or 0, q))
        ranks = {q: (k / max(1, len(order)), k) for k, q in enumerate(order)}
        lay.__dict__["_ranks"] = ranks
    return ranks.get(pid, (0.0, 0))


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
    marks_scheme = mark and lay.edits.schemes.get("marks", "own") != "own"
    if mark and lay.edits.mark_style == "glow" and marks_scheme:      # a rainbow or alternating glow
        reach = lay.edits.mark_glow
        for k in range(GLOW_RINGS, 0, -1):
            m = reach * (k - 0.5) / GLOW_RINGS
            for line in scheme_outline(lay.edits, "marks", kind, (fx - m, fy - m, fw + 2 * m, fh + 2 * m, angle),
                                       corner_radius(kind) + m, 2 * reach / GLOW_RINGS + 0.6,
                                       opacity=see * (1 - (k - 1) / GLOW_RINGS), target=target, pieces=32):
                add(line)
    elif mark and marks_scheme:
        m = MARK_GAP
        for line in scheme_outline(lay.edits, "marks", kind, (fx - m, fy - m, fw + 2 * m, fh + 2 * m, angle),
                                   corner_radius(kind) + m, 4, opacity=see, target=target):
            add(line)
    elif mark and lay.edits.mark_style == "glow":
        reach = lay.edits.mark_glow
        for k in range(GLOW_RINGS, 0, -1):     # outermost (faintest) first
            m = reach * (k - 0.5) / GLOW_RINGS
            add(Shape(kind, fx - m, fy - m, fw + 2 * m, fh + 2 * m, mark, width=2 * reach / GLOW_RINGS + 0.6, fill=None,
                      radius=corner_radius(kind) + m, pid=p.id, target=target, angle=angle,
                      # The player's colour at full strength against the portrait, fading out to
                      # nothing: "a vibrant red halo of light radiating out from the portrait"
                      # (the owner, 2026-10-08; it was capped at 45%, so red came out pale pink).
                      opacity=see * (1 - (k - 1) / GLOW_RINGS)))
    elif mark:
        m = MARK_GAP
        add(Shape(kind, fx - m, fy - m, fw + 2 * m, fh + 2 * m, mark, width=4, fill=None,
                  radius=corner_radius(kind) + m, pid=p.id, target=target, angle=angle, opacity=see))
    rank_t, rank_j = _rank(lay, p.id)
    inside_colour = (lay.entry(p).get("fill") or scheme_colour(lay.edits, "insides", rank_t, rank_j)
                     or lay.edits.portrait_fill)           # their own, else the scheme's, else the tree's
    border_scheme = border not in SPECIAL_BORDERS and lay.edits.schemes.get("borders", "own") != "own"
    dash = border if border in ("dotted", "dashed", "dashdot") else ""
    add(Shape(kind, fx, fy, fw, fh, colour, width=0 if border_scheme else BORDER_WIDTHS[border],
              radius=corner_radius(kind), dash=dash, pid=p.id, target=("person", p.id), fill=inside_colour,
              angle=angle))
    if border_scheme:                           # a rainbow or alternating colours round the outline
        for line in scheme_outline(lay.edits, "borders", kind, (fx, fy, fw, fh, angle), corner_radius(kind),
                                   BORDER_WIDTHS[border], dash=dash, target=("person", p.id)):
            add(line)
    e = lay.edits
    mx, my = fx + fw / 2, fy + fh / 2

    def placed(line):
        pts = [(fx + u * fw, fy + v * fh) for u, v in line]
        if angle:
            pts = [(mx + dx, my + dy) for dx, dy in (turn(px - mx, py - my, angle) for px, py in pts)]
        return pts
    if border in SPECIAL_BORDERS:               # the braided rope or a vine, round any shape, in its own colours
        see = e.special_opacity / 100            # as see-through as the player says
        for item in special_border(border, kind, (fx, fy, fw, fh, angle), corner_radius(kind), e):
            if see < 1:
                item.opacity = item.opacity * see
            add(item)
    replaced = ({i for i, _pts, _closed in sticking_out(kind, (fx, fy, fw, fh, angle), lay.frame_points(p.id))}
                if border in SPECIAL_BORDERS else set())
    for i, line in enumerate(decor(kind)):      # drawn like the border (a stamen, an antenna, the wave)
        if i not in replaced:                   # unless the special border is on it
            add(Line(placed(line), colour, max(1.6, BORDER_WIDTHS[border] * 0.8)))
    if e.detail_lines and e.detail_opacity > 0:   # light, under the face and the words
        lines_inside = details(kind)
        for i, line in enumerate(lines_inside):
            add(Line(placed(line), lay.entry(p).get("detail")
                     or scheme_colour(e, "details", i / max(1, len(lines_inside)), i) or e.detail_colour or colour,
                     e.detail_width, opacity=e.detail_opacity / 100))
    # The face and words grow or shrink with a frame the player resized, about its middle, and
    # never turn (the owner: "shrink/grow with the frame, stay upright").
    # Measured against the shape's own natural size, never the group's: a villager sized on their own
    # kept a giant face when their group was made tiny (the owner, 2026-10-09: 8-pixel males, faces 4x).
    w0, h0 = natural_width(base_kind(kind)), NODE_H
    scale = max(0.2, min(4.0, fw / w0, fh / h0)) if (round(fw, 3), round(fh, 3)) != (round(w0, 3), round(h0, 3)) else 1.0
    middle = (x + NODE_W / 2, y + NODE_H / 2)

    flip_h, flip_v = lay.entry(p).get("flip_h", False), lay.entry(p).get("flip_v", False)

    def put(item) -> None:
        if scale != 1.0:
            item.x = middle[0] + (item.x - middle[0]) * scale
            item.y = middle[1] + (item.y - middle[1]) * scale
            if isinstance(item, Head):
                item.scale *= scale
            elif isinstance(item, Text):
                item.size *= scale
            else:
                item.w, item.h = item.w * scale, item.h * scale
        words = isinstance(item, Text) and item.role in ("names", "portraits")
        if words and lay.edits.flip_words and (flip_h or flip_v):
            # Mirrored with the flipped portrait, about its middle (the owner, 2026-10-09).
            if flip_h:
                item.x, item.mirror_h = 2 * middle[0] - item.x, True
            if flip_v:
                item.y, item.mirror_v = 2 * middle[1] - item.y + item.size * 0.7, True
        if angle and lay.edits.turn_words and words:
            # The words turn with the portrait, about its middle (the owner, 2026-10-09); the face does not.
            dx, dy = turn(item.x - middle[0], item.y - middle[1], angle)
            item.x, item.y, item.angle = middle[0] + dx, middle[1] + dy, angle
        add(item)

    pic, own = inner_sizes(lay, p)          # the face's and the words' sizes inside the shape
    if p.upcoming:
        for k, text in enumerate(node_text(lay, p)):
            put(Text(x + NODE_W / 2, y + NODE_H / 2 + 4 + k * 15 * own, text, (12 if k == 0 else 11) * own, ink,
                     bold=k == 0, centre=True, pid=p.id, role="names" if k == 0 else "portraits",
                     edit=f"person:{p.id}"))
        return
    sheet = sheet_name(lay.village.game, p)
    head = look_of(lay.edits, lay.village, p)[0]
    box = face_box(present, sheet, head)
    head_left, head_top, text_top, lines = placement(lay, p, box)
    if sheet in present and head is not None and head >= 0:
        put(Head(x + head_left, y + head_top, sheet, head, pid=p.id, scale=pic))
    else:
        mid = y + head_top + FACE_H * HEAD_SCALE * pic / 2
        r = 26 * pic
        put(Shape("ellipse", x + NODE_W / 2 - r, mid - r, 2 * r, 2 * r, colour, width=1, fill=colour, pid=p.id,
                  target=("person", p.id)))
        put(Text(x + NODE_W / 2, mid + 10 * pic, p.name[:1], 28 * pic, "#ffffff", bold=True, centre=True, pid=p.id))
    # Every line inside its shape (Codex, #575; the owner, 2026-10-08: "text should fit within the shape as
    # much as possible"): each line is measured against the shape's own width where it is drawn -- a
    # circle or a heart is narrower towards its edges -- and this portrait's words made only as much
    # smaller as the tightest line needs.  Then the player's own text size for this villager.
    points = text_room_points(lay.edits.text_room, kind, lay.frame_points(p.id), (fx, fy, fw, fh, angle))
    fit = 1.0
    for k, (text, bold, _r) in enumerate(lines):
        if not text:
            continue
        size = (11.5 if bold else 10) * scale
        baseline = middle[1] + (y + text_top + k * LINE_H * own - middle[1]) * scale
        # The narrowest the shape is across the whole line, from the tops of its letters to below them.
        chord = min(_chord(points, baseline - size * 0.75), _chord(points, baseline + size * 0.2))
        # Half the frame at least, unless the player keeps the words inside the shape (a cross's arm).
        room = max(chord - 8, 12.0) if lay.edits.text_inside else max(chord, fw * 0.5) - 8
        needed = len(text) * size * (0.58 if bold else 0.55)
        if room > 0 and needed > room:
            fit = min(fit, room / needed)
    # Left or right: every line from (or to) one edge, the narrowest the shape is across the words,
    # so no line leaves a round or pointed portrait (Edits.text_align).
    align = lay.edits.text_align
    half = NODE_W / 2 - 8
    if align != "centre":
        for k, (text, bold, _r) in enumerate(lines):
            if text:
                size = (11.5 if bold else 10) * scale
                baseline = middle[1] + (y + text_top + k * LINE_H * own - middle[1]) * scale
                chord = min(_chord(points, baseline - size * 0.75), _chord(points, baseline + size * 0.2))
                wide = max(chord - 4, 16.0) if lay.edits.text_inside else max(chord, fw * 0.5)
                half = min(half, (wide - 12) / 2 / scale)
    at = x + NODE_W / 2 + (-half if align == "left" else half if align == "right" else 0)
    for k, (text, bold, runs) in enumerate(lines):
        put(Text(at, y + text_top + k * LINE_H * own, text, (11.5 if bold else 10) * fit * own, ink,
                 bold=bold, centre=align == "centre", end=align == "right", pid=p.id,
                 role="names" if bold else "portraits", edit=f"person:{p.id}", runs=runs))


def text_room_points(room: str, kind: str, outline_points: list, frame: tuple) -> list:
    """The outline a portrait's words are fitted in: the shape's own, or a rectangle or an oval in its
    middle (Edits.text_room; "auto", for every shape -- the owner, 2026-10-09 --: the oval filling a
    circle or an oval, else the rectangle filling the frame)."""
    if room == "auto":
        room = "oval" if kind in ("circle", "ellipse") else "rect"
    if room == "shape":
        return outline_points
    x, y, w, h, angle = frame
    cx, cy = x + w / 2, y + h / 2
    if room == "rect":
        # The words may pass the drawn outline but stay within the shape's own width and height (the
        # owner, 2026-10-09): the frame's rectangle, a little in from its sides, or the oval filling it.
        pts = [(cx - 0.47 * w, cy - 0.47 * h), (cx + 0.47 * w, cy - 0.47 * h), (cx + 0.47 * w, cy + 0.47 * h),
               (cx - 0.47 * w, cy + 0.47 * h)]
    else:
        pts = [(cx + 0.5 * w * math.cos(a), cy + 0.5 * h * math.sin(a)) for a in (2 * math.pi * k / 48 for k in range(48))]
    if angle:
        pts = [(cx + dx, cy + dy) for dx, dy in (turn(px - cx, py - cy, angle) for px, py in pts)]
    return pts


def _chord(points: list[tuple[float, float]], y: float) -> float:
    """How wide the shape these corners outline is at height `y` (0 above or below it)."""
    xs = []
    for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
        if (ay > y) != (by > y):
            xs.append(ax + (y - ay) * (bx - ax) / (by - ay))
    return max(xs) - min(xs) if len(xs) >= 2 else 0.0


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


def _svg_runs(item: Text) -> str:
    """A formatted Text's runs as tspans, one after another: each its own weight, style, lines,
    colour and size, a superscript or subscript raised or lowered (dy) and the next put back."""
    out, at = [], 0.0
    for text, style in item.runs:
        look = run_look(item, style)
        decor = " ".join(d for d, on in (("underline", look["underline"]), ("line-through", look["strike"])) if on)
        attrs = (f' font-weight="{"bold" if look["bold"] else "normal"}"'
                 f' font-style="{"italic" if look["italic"] else "normal"}"'
                 f' text-decoration="{decor or "none"}" fill="{look["colour"]}" font-size="{look["size"]:g}"')
        if look["dy"] != at:
            attrs += f' dy="{look["dy"] - at:g}"'
            at = look["dy"]
        out.append(f"<tspan{attrs}>{html.escape(text)}</tspan>")
    return "".join(out)


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
        elif isinstance(item, Poly):
            pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in item.points)
            stroke = f'stroke="{item.stroke}" stroke-width="{item.width}"' if item.width else 'stroke="none"'
            out.append(f'<polygon points="{pts}" fill="{item.fill or "none"}" fill-rule="evenodd" {stroke}'
                       f' stroke-linejoin="round"{_svg_opacity(item)}/>')
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
            anchor = ' text-anchor="middle"' if item.centre else ' text-anchor="end"' if item.end else ""
            words = _svg_runs(item) if item.runs else e(item.text)
            moves = []
            if item.angle:
                moves.append(f"rotate({item.angle:g} {item.x:.1f} {item.y:.1f})")
            if item.mirror_h or item.mirror_v:
                my = item.y - item.size * 0.35
                moves.append(f"translate({item.x:.1f} {my:.1f}) scale({-1 if item.mirror_h else 1} "
                             f"{-1 if item.mirror_v else 1}) translate({-item.x:.1f} {-my:.1f})")
            if moves:
                anchor += f' transform="{" ".join(moves)}"'
            keep = ' xml:space="preserve"' if item.runs else ""     # the spaces between runs
            out.append(f'<text x="{item.x:.1f}" y="{item.y:.1f}" font-size="{item.size}"{weight}{anchor} '
                       f'fill="{item.colour}"{_svg_opacity(item)}{keep}>{words}</text>')
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
    edits = full_name_edits(edits, village)
    arrange(village, edits)
    return village, edits, layout(village, edits)


def write(folder: Path, game: int, slot: int, images: Path | None, game_title: str,
          out: Path | None = None, edits: Edits | None = None, library: dict | None = None) -> Written:
    """The genealogy report, the tree's page and (on Windows) its picture, in the save folder's
    Virtual Villagers Fun Patcher Family Trees\\Reports (or `out`) -- each run replaces the slot's last
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
    import vv_save_layout as save_layout             # "Family Trees\Reports"; "Logs\Genealogy" in older builds
    out = Path(out) if out is not None else save_layout.find(folder, f"{TREES}\\{save_layout.TREE_REPORTS}")
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
    edits = full_name_edits(Edits.load(Edits.path(folder, game, slot)), village)
    arrange(village, edits)
    # Names as Number Duplicate Names gives them (the owner, 2026-10-08: a Roman number only for the
    # same first and last name -- "Hawa Awanata should not be called I or II unless there's literally
    # a second Hawa Awanata"), here before Repair Saves & Logs puts them in the save; in the order the
    # tree numbers them, so the report and the tree agree.
    for pid, name in gen.duplicate_names(village, edits.number_order).items():
        village.people[pid].name = name
    text = gen.pair_report(village, rules, game_title)
    out = Path(out) if out is not None else folder / TREES
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"Virtual Villagers {game} Village Matchmaker - Save {slot}.txt"
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    return path, text
