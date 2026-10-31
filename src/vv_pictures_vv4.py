"""Picture Studio, The Tree of Life (Virtual Villagers 4): every villager drawn exactly as the game draws it.

The rules below are the game's own draw code, ported line for line and proven in tests/test_pictures_vv4.py by
running that code (Unicorn, on the vanilla executable) down to its blits and comparing every blit -- sheet,
cell, place, scale, surface alpha -- with this module's plan (docs/picture-studio-vv4.md has the addresses).

THE VILLAGE FIGURE (0x467DA0, the live renderer of a villager, run once per villager per frame from the draw
queue 0x44C420 with surface alpha 1.0):
  * a body awaiting burial (health <= 0): skelly.png cell (record +0x1B94 C-mod 4) at the villager's place,
    at the body scale, and nothing else;
  * else: the shadow peep_shadow1.png, a carried item behind (facing 0, 3, 4), the body, the head, a carried
    item in front (facing 1, 2, 5, 6, 7) -- or, standing in water, the ripple (ripple.png at 0.4 alpha) and the
    head only;
  * every place comes from the game's animation tables (0x4E00E0), built by 0x44DE60 from the game's own
    Assets\\animpts.dat (read from the player's game, like the art) and its fixed sprite and frame overrides:
    a body anchor per (pose, sex, body), a head anchor per (pose, sex, body) and a head offset per (head
    column, sex, head);
  * a child is drawn smaller: the body at age / 700 + 0.5 (0x45EC30) and the head at (age / 14 + 80) / 100,
    both full size from 280 age units (14 years); the old head (heads10, the head column + 8) from 1,100 units
    (55 years) -- or as Change Appearance's head look says;
  * a ghost (0x466370 makes them: record +0x1CC7 set) is drawn at its own surface alpha, 0.6.
THE VILLAGER DETAILS PORTRAIT (0x45F550): the big body (bigbodies.png, pose 49) and the big head (bigheads,
columns 8-10 of the head table: three portrait facings), and an expecting mother's babies (carrying.png cell 3
at 200%).
THE PATCHER'S ORIGINS MASKS (scripts/build_vv4_origins_feature.py mask_world_cave, spliced on the head draw
0x468263): the head's own draw again with vvfp_mask_atlas00.png (8 facings x 5 masks of 65 x 145), the column
the head column AND 7, the row mask - 1, lifted by rint(34 x head scale); in the Details portrait (mask_head_cave, spliced on 0x45F702) the
Details atlas vvfp_bighead_mask_atlas00.png (3 portrait facings x 5 masks) at the head's percentage x 3 >> 1, moved by its
per-facing x, per-mask y, a 50-pixel lift and a young villager's correction.
THE BLIT: each world draw (0x44C790, 0x44C720, 0x44C640) turns the float scale into a whole percentage,
trunc(100 x scale), and the blitter draws at that percentage / 100, from the given top-left (never centred).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, replace
from pathlib import Path

import vv_picture_image as pi
import vv_pictures_common as common

GAME = 4
ROOT = Path(__file__).resolve().parents[1]

# The game's sprite table (0x4C07CC, 0x30 bytes an entry: name, columns, rows, suffix, sheets across, down).
SPRITES = {
    256: pi.Atlas("carrying.png", 13, 6),
    260: pi.Atlas("collectables_small.png", 6, 9),
    276: pi.Atlas("female_heads", 16, 30, (2, 1)),
    277: pi.Atlas("female_bodies", 32, 30, (2, 3)),
    278: pi.Atlas("female_actions", 17, 30, (1, 3)),
    279: pi.Atlas("male_heads", 16, 30, (2, 1)),
    280: pi.Atlas("male_bodies", 32, 30, (2, 3)),
    281: pi.Atlas("male_actions", 17, 30, (1, 3)),
    282: pi.Atlas("bigheads", 12, 30, (2, 1)),
    283: pi.Atlas("bigbodies.png", 2, 30),
    284: pi.Atlas("peep_shadow1.png", 1, 1),
    285: pi.Atlas("skelly.png", 4, 1),
    286: pi.Atlas("ripple.png", 4, 1),
}
CARRYING, COLLECTABLES, SHADOW, SKELLY, RIPPLE = 256, 260, 284, 285, 286
MASK_FILE = "vvfp_mask_atlas00.png"
MASK_ATLAS = pi.Atlas(MASK_FILE, 8, 5)           # the companion's 0x40ABA0(name, ".png", 1, 1, 8, 5)
MASK_LIFT = 34                                    # MASK_DY_VALUES: the same for all five masks
BIG_MASK_FILE = "vvfp_bighead_mask_atlas00.png"
BIG_MASK_ATLAS = pi.Atlas(BIG_MASK_FILE, 3, 5)   # 0x40ABA0(name, ".png", 1, 1, 3, 5): the Details masks
# The Details mask cave's tables (scripts/build_vv4_origins_feature.py MASK_DETAILS_*): the portrait facing's
# column, each column's x, each mask's y, the base lift, the scale x 3 >> 1, and the young correction.
BIG_MASK_FACE = (0, 1, 2)
BIG_MASK_DX = (19, 3, -16)
BIG_MASK_DY = (0, 2, 0, 2, 0)
BIG_MASK_LIFT = 0x32
ANIMPTS = "animpts.dat"
BODY_BLOCKS = 50                                  # the table's poses (0x7A4 bytes each)
HEAD_ENTRIES = 22                                 # 2 sexes x 11 head columns (0x1E8 bytes each)
POSES_WALK = 32                                   # 0-31: male/female_bodies (4 directions x 8 steps)
POSE_ACTIONS = range(32, 49)                      # 32-48: the actions sheets' 17 columns
POSE_BIG = 49                                     # bigbodies.png: the Details portrait's body
CHILD_AGE = 0x118
ZOOM = 1.0                                        # the camera's zoom [0x4DB9F8+0x300C] (always 1 in the village)
GHOST_ALPHA = struct.unpack("<f", bytes.fromhex("9a99193f"))[0]   # 0x48E330: 0.6f
DIRECTIONS = ("Facing 1", "Facing 2", "Facing 3", "Facing 4")
HEAD_COLUMNS = 8
NO_ITEM = -1


def required_files() -> list[str]:
    files = []
    for atlas in SPRITES.values():
        files += atlas.files()
    return files


def required_data_files() -> list[str]:
    """The game's own data the drawing reads (from Assets\\, not Images\\): the animation anchors, which the
    Picture Studio's cache copies with the pictures (src/vv_picture_image.py data_name)."""
    return [ANIMPTS]


def patcher_art() -> dict[str, Path]:
    return {MASK_FILE: ROOT / "assets" / "vv4_masks" / "vvfp_mask_atlas.png",
            BIG_MASK_FILE: ROOT / "assets" / "vv4_masks" / "vvfp_bighead_mask_atlas.png"}


def load(source) -> "Renderer":
    return Renderer(_WithPatcherArt(source))


class _WithPatcherArt:
    """The source, with the patcher's own art (assets\\) behind it for the names it does not have."""

    def __init__(self, base) -> None:
        self.base = base
        self.problem = getattr(base, "problem", "") or ""
        self.copy = getattr(base, "copy", None)

    def read(self, name: str):
        data = self.base.read(name) if self.base is not None else None
        if data is None:
            path = patcher_art().get(name)
            if path is not None:
                try:
                    data = path.read_bytes()
                except OSError:
                    data = None
        return data


# ------------------------------------------------------------------------------------------------- numbers

f32 = pi.f32


def _trunc(value: float) -> int:
    """The game's _ftol (0x471630): toward zero."""
    return int(value)


def _rint(value: float) -> int:
    """fistp under the default rounding: to nearest, ties to even."""
    return round(value)


def body_scale(age: int) -> float:
    """0x45EC30: age / 700 + 0.5 as a 32-bit float below 280 age units, else 1."""
    if age >= CHILD_AGE:
        return 1.0
    return f32(age / 700.0 + 0.5)


def head_scale(age: int) -> float:
    """0x467EEC: (age / 14 + 80) / 100 as a 32-bit float below 280 age units, else 1."""
    if age >= CHILD_AGE:
        return 1.0
    return f32((age / 14.0 + 80.0) / 100.0)


def percent(scale: float) -> int:
    """0x44C790 / 0x44C720 / 0x44C640: fild [mgr+0x3010] (100 at zoom 1) x scale, ftol."""
    return _trunc(100 * scale)


def blit_scale(pct: int) -> float:
    """0x408DC0 / 0x408B90: the percentage / 100.0 as a 32-bit float."""
    return f32(pct / 100.0)


def anchor(offset: tuple[int, int], scale: float) -> tuple[int, int]:
    """0x44E900 / 0x44E960 / 0x44EA00: each offset x scale + 0.5, toward zero."""
    return _trunc(offset[0] * scale + 0.5), _trunc(offset[1] * scale + 0.5)


# ------------------------------------------------------------------------------------- the animation tables

@dataclass(frozen=True)
class Entry:
    sprite: int
    frame: int
    first: tuple            # 30 (x, y): the head anchor per body (body entries) / unused (head entries)
    second: tuple           # 30 (x, y): the body anchor per body / the head offset per head


def _pairs(raw: bytes, at: int) -> tuple:
    return tuple(struct.unpack_from("<2i", raw, at + 8 * k) for k in range(30))


class Tables:
    """The game's animation tables at 0x4E00E0 as 0x44DE60 leaves them: Assets\\animpts.dat (a dword length,
    50 poses of 4 x 0x1E8 bytes, a dword length, 22 head entries of 0x1E8) copied over the table at +0x7254
    and +0x1F05C, then the fixed sprites and frames written over it (0x44E636-0x44E750)."""

    def __init__(self, data: bytes) -> None:
        if len(data) < 4:
            raise pi.PictureError("The game's Assets\\animpts.dat is cut short.")
        n = struct.unpack_from("<I", data, 0)[0]
        if n != BODY_BLOCKS * 0x7A4 or len(data) < 8 + n:
            raise pi.PictureError("The game's Assets\\animpts.dat is not The Tree of Life's.")
        m = struct.unpack_from("<I", data, 4 + n)[0]
        if m != HEAD_ENTRIES * 0x1E8 or len(data) < 8 + n + m:
            raise pi.PictureError("The game's Assets\\animpts.dat is not The Tree of Life's.")
        body_blob = data[4:4 + n]           # at table +0x7254: pose k, part s is blob + 4 + k * 0x7A4 + s * 0x1E8
        head_blob = data[8 + n:8 + n + m]   # at table +0x1F05C: entry e is blob + e * 0x1E8
        self.body = {}
        for k in range(BODY_BLOCKS):
            for part in (0, 2):             # 0 male, 2 female (the renderers ask for 0 + 2 x sex)
                at = 4 + k * 0x7A4 + part * 0x1E8
                female = part == 2
                if k < 32:
                    sprite, frame = (277 if female else 280), k
                elif k < 49:
                    sprite, frame = (278 if female else 281), k - 32
                else:
                    sprite, frame = 283, (1 if female else 0)
                raw = body_blob[at:at + 0x1E8].ljust(0x1E8, b"\0")
                self.body[(k, female)] = Entry(sprite, frame, _pairs(raw, 8), _pairs(raw, 0xF8))
        self.head = {}
        for female in (False, True):
            for col in range(11):
                at = (int(female) * 11 + col) * 0x1E8
                raw = head_blob[at:at + 0x1E8]
                if col < 8:
                    sprite, frame = (276 if female else 279), col
                else:
                    sprite, frame = 282, (col + 3 - 8 if female else col - 8)
                self.head[(col, female)] = Entry(sprite, frame, _pairs(raw, 8), _pairs(raw, 0xF8))


# ------------------------------------------------------------------------------------------ what is drawn

@dataclass(frozen=True)
class Look:
    """Everything about one villager the draw reads."""
    female: bool = False
    age: int = 600                  # age units
    head: int = 0
    body: int = 0
    health: int = 100               # <= 0: a body awaiting burial
    dead_frame: int = 0             # record +0x1B94 (the skeleton's cell, C-mod 4)
    old: bool = False               # the old head (heads10)
    ghost: bool = False
    mask: int = 0                   # the patcher's Origins mask 1..5
    item: int = NO_ITEM             # record +0x1CDC: < 70 carrying.png, else collectables_small.png
    litter: int = 1                 # record +0x1C50 (copies of the item: 2 and 3)
    expecting: bool = False         # record +0x1C4C != 0 (the Details portrait's babies)


@dataclass(frozen=True)
class Pose:
    pose: int = 0                   # record +0x1CB0: 0-7 a step (with the direction), 8-49 the table's pose
    direction: int = 0              # record +0x1CD0
    head_column: int = 5            # record +0x1CD4 (0-7)
    shadow: bool = True             # (the game always draws it on land; off: left out of the picture)
    held: bool = False              # record +0x1CC5: picked up by the hand
    water: bool = False             # standing in water (terrain 5 at the feet, 0x46C3D0)
    ripple: int = 0                 # ripple.png's cell (the game picks it at random)
    view: str = "village"           # "village" or "details"
    portrait_facing: int = 0        # record +0x2E38 C-mod 3 (Details)


def _draw(sheets: pi.Sheets, sprite: int, x: int, y: int, col: int, row: int, scale: float, alpha: float,
          what: str, atlas: pi.Atlas | None = None) -> pi.Draw:
    """One world draw (0x44C790): cell (col, row) at (x, y), trunc(100 x scale) percent, uncentred.  0x409A80
    makes the cell a frame, row x columns + col, and 0x408DC0 cuts it back (C division) for 0x40A990."""
    atlas = atlas or SPRITES[sprite]
    row, col = _cdivmod(row * atlas.cols + col, atlas.cols)
    name, rect = sheets.cell(atlas, col, row)
    return pi.Draw(name, rect, x, y, blit_scale(percent(scale)), alpha, what)


def _draw_frame(sheets: pi.Sheets, sprite: int, x: int, y: int, frame: int, scale: float, alpha: float,
                what: str) -> pi.Draw:
    """A linear-frame draw (0x409A80 / 0x408DC0): frame -> (frame % columns, frame / columns) in C."""
    atlas = SPRITES[sprite]
    q, r = _cdivmod(frame, atlas.cols)
    return _draw(sheets, sprite, x, y, r, q, scale, alpha, what)


def _cdivmod(a: int, b: int) -> tuple[int, int]:
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return q, a - q * b


def plan_village(sheets: pi.Sheets, tables: Tables, look: Look, pose: Pose, x0: int = 400, y0: int = 300) -> list:
    """0x467DA0 for one villager at world (x0, y0), camera at rest (no scroll, zoom 1), record +0x1CB8 = 0
    (on the ground), +0x1CD8 != 6, and the carried item's bob [0x4DEA04] = 0."""
    out = []
    alpha = GHOST_ALPHA if look.ghost else 1.0
    bs = body_scale(look.age)
    if look.health <= 0:
        frame = _cdivmod(look.dead_frame, 4)[1]
        out.append(_draw(sheets, SKELLY, x0, y0, frame, 0, bs, 1.0, "skeleton"))
        return out
    sex = look.female
    X = x0 - _trunc(-20.0 * bs)                     # 0x45ED00
    Y = y0 - _trunc(-55.0 * bs)
    elev = 0
    col = pose.pose
    if 0 <= col <= 7:
        direction = pose.direction if 0 <= pose.direction < 8 else 2
        col = col + direction * 8
    hs = head_scale(look.age)
    old = 8 if look.old else 0
    head_entry = tables.head[(pose.head_column, sex)]
    hx, hy = anchor(head_entry.second[look.head], hs) if 0 <= look.head < 30 else (0, 0)
    water = pose.water
    if pose.shadow and elev >= 0:
        s = f32(bs * 0.5) if pose.held else bs
        a, b = _trunc(34.0 * s), _trunc(32.0 * s)
        sx, sy = X - a, Y - b
        if pose.held:
            sy += 0x14
        if not water:
            out.append(_draw(sheets, SHADOW, sx, sy, 0, 0, s, alpha, "shadow"))
    behind = pose.direction in (0, 3, 4)
    if behind and not water:
        out += _item(sheets, look, x0 + _trunc(0 * bs), y0 - elev + _trunc(bs * _trunc(18.0 * ZOOM)), bs)
    ex, ey = X, Y - elev
    if not pose.held and water and col != 0x29:
        out.append(pi.Draw(*sheets.cell(SPRITES[RIPPLE], pose.ripple & 3, 0), X - 0x20, Y - elev - 0x20,
                           1.0, f32(0.4), "ripple"))
    else:
        body = tables.body.get((col, sex))
        if body is None or not 0 <= look.body < 30:
            raise pi.PictureError("The game has no picture for this pose.")
        bx, by = anchor(body.second[look.body], bs)
        ex, ey = ex - bx, ey - by
        out.append(_draw(sheets, body.sprite, ex, ey, body.frame, look.body, bs, alpha, "body"))
        ax, ay = anchor(body.first[look.body], bs)
        ex, ey = ex + ax, ey + ay
    head_x, head_y = ex - hx, ey - hy
    head_col = pose.head_column + old
    out.append(_draw(sheets, head_entry.sprite, head_x, head_y, head_col, look.head, hs, alpha, "head"))
    if look.mask:
        lift = _rint(MASK_LIFT * hs)
        out.append(_draw(sheets, 0, head_x, head_y - lift, pose.head_column & 7, look.mask - 1, hs, alpha,
                         "mask", MASK_ATLAS))
    if pose.direction in (1, 2, 5, 6, 7) and not water:
        out += _item(sheets, look, x0 + _trunc(0 * bs), y0 - elev + _trunc(bs * _trunc(18.0 * ZOOM)), bs)
    return out


def _item(sheets: pi.Sheets, look: Look, x: int, y: int, bs: float) -> list:
    """0x466770: the carried item (record +0x1CDC, -1 none) at (x, y) plus the bob (0 here), and a second
    and third copy for a litter of 2 and 3 (+0x1C50)."""
    if look.item == NO_ITEM:
        return []
    if look.item >= 0x46:
        sprite, frame = COLLECTABLES, look.item - 0x46
    else:
        sprite, frame = CARRYING, look.item
    out = [_draw_frame(sheets, sprite, x, y, frame, 1.0, 1.0, "item")]
    # The copies are always carrying.png's, at the item's own number (0x4667C8 / 0x4667F3: [mgr+0x24] and ESI,
    # the record's value): a collectable's copies are another carrying.png cell.  As the game draws it.
    if look.litter > 1:
        out.append(_draw_frame(sheets, CARRYING, x - 5, y + 5, look.item, 1.0, 1.0, "item"))
        if look.litter == 3:
            out.append(_draw_frame(sheets, CARRYING, x, y + 9, look.item, 1.0, 1.0, "item"))
    return out


def plan_details(sheets: pi.Sheets, tables: Tables, look: Look, pose: Pose, px: int = 400, py: int = 300) -> list:
    """0x45F550, the Villager Details figure, drawn at (px, py) (its two arguments)."""
    out = []
    sex = look.female
    bs = body_scale(look.age)
    hs = head_scale(look.age)
    body_pct = _trunc(bs * 100.0)
    head_pct = _trunc(100.0 * hs)
    body = tables.body[(POSE_BIG, sex)]
    if not 0 <= look.body < 30 or not 0 <= look.head < 30:
        raise pi.PictureError("The game has no picture for this head or body.")
    bx, by = anchor(body.second[look.body], bs)
    x, y = px - bx, py - by
    name, rect = sheets.cell(SPRITES[body.sprite], body.frame, look.body)
    out.append(pi.Draw(name, rect, x, y, blit_scale(body_pct), 1.0, "body"))
    ax, ay = anchor(body.first[look.body], bs)
    x, y = x + ax, y + ay
    col = _cdivmod(pose.portrait_facing, 3)[1] + 8
    entry = tables.head[(col, sex)]
    hx, hy = anchor(entry.second[look.head], hs)
    x, y = x - hx, y - hy
    head_col = entry.frame + (SPRITES[entry.sprite].cols // 2 if look.old else 0)
    name, rect = sheets.cell(SPRITES[entry.sprite], head_col, look.head)
    out.append(pi.Draw(name, rect, x, y, blit_scale(head_pct), 1.0, "head"))
    if 1 <= look.mask <= 5:
        # The Origins Details mask cave (mask_head_cave), after the head's own draw 0x45F702.
        row = look.mask - 1
        mcol = BIG_MASK_FACE[_cdivmod(pose.portrait_facing, 3)[1] % 3]
        mx = x + BIG_MASK_DX[mcol]
        my = y + BIG_MASK_DY[row] - BIG_MASK_LIFT
        if look.age < CHILD_AGE and row in (1, 3, 4):
            mx, my = mx - 2, my + 3
        mpct = ((head_pct * 3) & 0xFFFFFFFF) >> 1
        name, rect = sheets.cell(BIG_MASK_ATLAS, mcol, row)
        out.append(pi.Draw(name, rect, mx, my, blit_scale(mpct), 1.0, "mask"))
    if look.expecting:
        dx, dy = _trunc(20.0 * bs), _trunc(55.0 * bs)
        bx0 = px - 2 * dx - 10
        by0 = py - 2 * dy + 0x24
        spots = [(bx0, by0)]
        if look.litter > 1:
            spots.append((bx0, by0 - 8))
            if look.litter == 3:
                spots.append((bx0, by0 - 13))
        for sx, sy in spots:
            name, rect = sheets.cell(SPRITES[CARRYING], 3, 0)
            out.append(pi.Draw(name, rect, sx, sy, blit_scale(200), 1.0, "baby"))
    return out


# ----------------------------------------------------------------------------------------------- choices

LIFE = "life"
STAGES = [pi.Option(("child", y * common.UNITS_PER_YEAR), f"Child, {y} year{'s' if y != 1 else ''}")
          for y in range(0, 14)]
STAGES += [pi.Option(("adult", 14 * 20), "Adult, 14 years (full size)"),
           pi.Option(("adult", 30 * 20), "Adult, 30 years"),
           pi.Option(("elder", 55 * 20), "Elder, 55 years (old head)"),
           pi.Option(("elder", 80 * 20), "Elder, 80 years (old head)"),
           pi.Option(("ghost", 30 * 20), "Ghost (drawn at 60% opacity)"),
           pi.Option(("dead", 30 * 20), "Dead (body awaiting burial: skeleton)")]


def _pose_options() -> tuple:
    out = [pi.Option(("walk", step), f"Walking, step {step + 1}") for step in range(8)]
    out += [pi.Option(("action", k), f"Action {k + 1} (actions sheet column {k + 1})") for k in range(17)]
    out += [pi.Option(("water", r), f"Standing in water (ripple {r + 1})") for r in range(4)]
    out += [pi.Option(("held", step), f"Picked up by the hand, step {step + 1}") for step in range(8)]
    return tuple(out)


ITEM_OPTIONS = ((pi.Option(NO_ITEM, "Nothing"),)
                + tuple(pi.Option(k, f"carrying.png item {k + 1}" + (" (a baby)" if k == 3 else ""))
                        for k in range(13 * 6))
                + tuple(pi.Option(0x46 + k, f"collectables_small.png item {k + 1}") for k in range(6 * 9)))
MASK_OPTIONS = (pi.Option(0, common.MASK_NAMES[0]),) + tuple(pi.Option(k, common.MASK_NAMES[k], patcher=True)
                                                              for k in range(1, 6))
LOOK_OPTIONS = (pi.Option(common.LOOK_AUTO, "Auto (old from 55)"), pi.Option(common.LOOK_YOUNG, "Young", True),
                pi.Option(common.LOOK_OLD, "Old", True))
VIEW_OPTIONS = (pi.Option("village", "In the village"), pi.Option("details", "Villager Details portrait"))


def pose_fields() -> tuple:
    return (
        pi.Field("view", "Picture", VIEW_OPTIONS, "village"),
        pi.Field("pose", "Pose", _pose_options(), ("walk", 0)),
        pi.Field("direction", "Direction", tuple(pi.Option(d, DIRECTIONS[d]) for d in range(4)), 0),
        pi.Field("head_column", "Head facing",
                 tuple(pi.Option(c, f"Head column {c + 1}") for c in range(HEAD_COLUMNS)), 5),
        pi.Field("portrait_facing", "Portrait facing",
                 tuple(pi.Option(c, f"Portrait head {c + 1}") for c in range(3)), 1),
        pi.Field("shadow", "Shadow", (pi.Option(True, "With its shadow"), pi.Option(False, "No shadow")), True),
        pi.Field("item", "Carrying", ITEM_OPTIONS, NO_ITEM),
        pi.Field("litter", "How many", (pi.Option(1, "One"), pi.Option(2, "Two (twins)"),
                                        pi.Option(3, "Three (triplets)")), 1),
    )


def make_pose(spec: dict) -> Pose:
    kind, value = spec.get("pose") or ("walk", 0)
    view = spec.get("view") or "village"
    pose = Pose(view=view, direction=int(spec.get("direction") or 0),
                head_column=int(spec.get("head_column", 5) if spec.get("head_column") is not None else 5),
                shadow=bool(spec.get("shadow", True)),
                portrait_facing=int(spec.get("portrait_facing") or 0))
    if kind == "walk":
        return replace(pose, pose=value)
    if kind == "action":
        return replace(pose, pose=32 + value)
    if kind == "water":
        return replace(pose, pose=0, water=True, ripple=value)
    if kind == "held":
        return replace(pose, pose=value, held=True)
    raise pi.PictureError("Unknown pose.")


def _age_text(age: int) -> str:
    return common.age_label(age)


class Renderer:
    def __init__(self, source) -> None:
        self.game = GAME
        self.source = source
        self.sheets = pi.Sheets(source)
        self.problem = getattr(source, "problem", "") or ""
        self._tables = None
        self._people: dict = {}

    # ---- the tables, from the player's own game
    def tables(self) -> Tables:
        if self._tables is None:
            self._tables = Tables(self._animpts())
        return self._tables

    def _animpts(self) -> bytes:
        data = None
        reader = getattr(self.source, "read", None)
        if reader is not None:
            for name in ("Assets/" + ANIMPTS, "Assets\\" + ANIMPTS):
                try:
                    data = reader(name)
                except (OSError, ValueError):
                    data = None
                if data:
                    break
        if not data:
            for base in (getattr(self.source, "copy", None), getattr(getattr(self.source, "base", None), "copy", None)):
                if base:
                    path = Path(base) / "Assets" / ANIMPTS
                    try:
                        data = path.read_bytes()
                        break
                    except OSError:
                        continue
        if not data:
            raise pi.PictureError("The Tree of Life's Assets\\animpts.dat (where the game keeps where each head "
                                  "and body sits) was not found: click \"Find game...\" and pick the game folder.")
        return data

    # ---- plans
    def plan(self, look: Look, pose: Pose) -> list:
        if pose.view == "details":
            if look.health <= 0:
                raise pi.PictureError("The Villager Details screen does not show a body awaiting burial.")
            return plan_details(self.sheets, self.tables(), look, pose)
        return plan_village(self.sheets, self.tables(), look, pose)

    def render(self, look: Look, pose: Pose) -> pi.Image:
        return pi.render_plan(self.sheets, self.plan(look, pose))

    # ---- From my save
    def saved_fields(self) -> tuple:
        return pose_fields()

    def _read(self, folder, slot):
        key = (str(folder), slot)
        people = common.read_village(Path(folder), GAME, slot)
        self._people[key] = {str(v.rank): v for v in people}
        return people

    def saved_items(self, folder, slot) -> list:
        out = []
        for v in self._read(folder, slot):
            stage = "child" if v.age < CHILD_AGE else ("elder" if v.age >= common.OLD_AGE else "adult")
            if v.dead:
                where, kind, stage = "Bodies awaiting burial", "body", "dead"
            else:
                where, kind = "Villagers", "villager"
            detail = [f"{'Male' if v.male else 'Female'}, {_age_text(v.age)} ({v.age} age units)",
                      f"Head {v.head}, body {v.body}" + (" (the Tribal Chief's outfit)" if v.body == 29 else "")]
            if v.mask:
                detail.append(f"Mask: {common.MASK_NAMES[v.mask]} (the patcher's Origins mask)")
            if v.look:
                detail.append(f"Head look: {common.LOOK_NAMES[v.look]} (Change Appearance)")
            out.append(pi.SavedItem(str(v.rank), f"{v.name} ({stage}, {_age_text(v.age)})", where, kind,
                                    "\n".join(detail)))
        return out

    def look_of(self, v: common.SaveVillager) -> Look:
        """What the save says: the saved entry is the record windows (0x1B8C, 0xA8) +4, ... with the name at
        entry +0x14 (record +0x1B9C): record +0x1B94 is name - 8; the pregnancy +0x1C4C and litter +0x1C50
        are name +0xB0 / +0xB4 (src/vv_last_names.py PREGNANCY)."""
        expecting = v.i32(0xB0) != 0
        litter = v.i32(0xB4)
        return Look(female=not v.male, age=v.age, head=v.head, body=v.body, health=v.health,
                    dead_frame=v.i32(-8), old=common.old_head(v.age, v.look), mask=v.mask,
                    expecting=expecting, litter=litter if litter in (1, 2, 3) else 1)

    def _person(self, folder, slot, item_id) -> common.SaveVillager:
        people = self._people.get((str(folder), slot))
        if people is None or item_id not in people:
            self._read(folder, slot)
            people = self._people[(str(folder), slot)]
        if item_id not in people:
            raise pi.PictureError("That villager is no longer in the save.")
        return people[item_id]

    def plan_saved(self, folder, slot, item_id, **options) -> list:
        v = self._person(folder, slot, item_id)
        look = self.look_of(v)
        spec = {f.key: f.default for f in pose_fields()}
        spec.update({k: val for k, val in options.items() if val is not None})
        look = replace(look, item=spec.get("item", NO_ITEM),
                       litter=spec.get("litter", 1) if spec.get("item", NO_ITEM) != NO_ITEM else look.litter)
        return self.plan(look, make_pose(spec))

    def render_saved(self, folder, slot, item_id, **options) -> pi.Image:
        return pi.render_plan(self.sheets, self.plan_saved(folder, slot, item_id, **options))

    # ---- Make your own
    def custom_choices(self, *_args, **_kwargs) -> list:
        fields = (
            pi.Field("sex", "Sex", (pi.Option(False, "Male"), pi.Option(True, "Female")), False),
            pi.Field(LIFE, "Life stage", tuple(STAGES), ("adult", 30 * 20)),
            pi.Field("head", "Head", tuple(pi.Option(h, f"Head {h}") for h in range(30)), 0),
            pi.Field("body", "Body", tuple(pi.Option(b, f"Body {b}" + (" (the Tribal Chief's outfit)" if b == 29
                                                                      else "")) for b in range(30)), 0),
            pi.Field("look", "Head look", LOOK_OPTIONS, common.LOOK_AUTO),
            pi.Field("mask", "Mask", MASK_OPTIONS, 0),
            pi.Field("expecting", "Expecting (Details: holds the babies)",
                     (pi.Option(False, "No"), pi.Option(True, "Yes")), False),
            pi.Field("dead_frame", "Skeleton", tuple(pi.Option(k, f"Skeleton {k + 1}") for k in range(4)), 0),
        ) + pose_fields()
        return [pi.Subject("villager", "Villager", fields,
                           "Every head and body fits every age. The old head is the game's own (heads10), drawn "
                           "from 55 or as the head look says. Masks are the patcher's Origins masks.")]

    def plan_custom(self, spec: dict) -> list:
        stage, age = spec.get(LIFE) or ("adult", 600)
        look_choice = spec.get("look", common.LOOK_AUTO)
        look = Look(female=bool(spec.get("sex")), age=int(age), head=int(spec.get("head") or 0),
                    body=int(spec.get("body") or 0), health=0 if stage == "dead" else 100,
                    dead_frame=int(spec.get("dead_frame") or 0), old=common.old_head(int(age), look_choice),
                    ghost=stage == "ghost", mask=int(spec.get("mask") or 0),
                    item=spec.get("item", NO_ITEM) if spec.get("item") is not None else NO_ITEM,
                    litter=int(spec.get("litter") or 1), expecting=bool(spec.get("expecting")))
        return self.plan(look, make_pose(spec))

    def render_custom(self, spec: dict) -> pi.Image:
        return pi.render_plan(self.sheets, self.plan_custom(spec))
