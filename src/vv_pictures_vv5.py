"""Picture Studio, New Believers (Virtual Villagers 5): a villager drawn exactly as the game's village draw
does it, from the game's own code (docs/picture-studio-vv5.md; proven by tests/test_pictures_vv5.py, which
runs that code in Unicorn on the stock executable).

THE DRAW.  0x4720E0 (thiscall on the villager manager 0x554148, records at +0x48, stride 0x2F44) draws one
villager.  Every place it uses comes from the game's animation table 0x5258B8, which the loader 0x451180
fills from the game's own Assets\\animpts.dat and then partly overwrites (0x4519BD..0x451AEE).  The renderer
reads the same file (read only, from the player's game) and applies the same overwrites (AnimTable).

  scale         s  = (age / 700 + 0.5) x [+0x1CCC] for a child (age < 280 units), else 1 x [+0x1CCC]
                     (0x466240; [+0x1CCC] is 1.0 from the record set-up 0x4651B0 and is never saved)
  head scale    hs = (age / 14 + 80) / 100 for a child, else 1.0 (0x4722F3)
  place         P  = (X + trunc(20 s), Y + trunc(55 s)) (0x466350, constants -20.0 / -55.0)
  feet          Yl = Y (+20 for the sitting and lying poses 40 and 41) (0x472263)
  pose          a  = pose + 8 x direction for the walking poses 0-7 (0x4722B9), else the pose itself
  head anchor   HA = heads[sex][head turn].anchor[head] x hs, each rounded trunc(v + 0.5) (0x451DA0)
  shadow        peep_shadow1.png at (P.x - trunc(34 s), P.y - trunc(32 s)), scale s (0x4723A5..0x472437)
  carried item  carrying.png / collectables_small.png at (X, Yl + trunc(18 s)), unscaled (0x4724ED,
                0x4701C0): before the body for directions 0, 3, 4, after the head otherwise; a mother's
                litter of 2 or 3 adds copies at (x - 5, y + 5) and (x, y + 9) (0x47020B..0x47025B)
  body          B  = (P.x, Yl + trunc(55 s)) - body anchor (anim a, sex, body row) x s (0x451D00); drawn
                cell (row body, column a's frame base) of the anim's sheet, scale s (0x47279C / 0x472774)
  head          H  = B + neck anchor (anim a, sex, body row) x s (0x451CA0) - HA; cell (row head, column
                head turn + 8 when old) of the head sheet, scale hs (0x4729C3 / 0x4728C1)
  heathen mask  (faction set) vv5_heathenheads.png row colour (Blue 0, Orange 1, Red 2, Purple 3 for ranks
                12/14/15/16, Chief 4 for rank 13; 0x4728C6), column head turn, at B + neck - mask anchor
                (0x451DA0 with 0x1E + colour), scale hs (0x47298F)
  swimming      ripple.png (frame rand & 3) at (P.x - 32, Yl + trunc(55 s) - 32), alpha 0.4, then the head
                only, at P - HA (0x472592..0x47264B, 0x4727CD)
  dead          (health 0 or less) skelly.png frame ([+0x1B94] mod 4) at (X, Y), scale s (0x472B18)

Every blit goes through the engine's cell draw (0x408DA0 / 0x408B70 / 0x408AC0 -> place 0x407F10 -> the
software blitter 0x404C40): the scale is the integer percentage trunc(100 x f) (the renderer's 100 at
+0x3010, 0x44F0F0, times the float) divided by 100.0, the cell never centred (the flag is 0).

PATCHER ART.  The Origins cosmetic mask of a Believer is drawn by flipping the villager to the heathen path
for its own draw (scripts/build_vv5_task9_native_actions.py mask_flip, entered at 0x472481): faction 1 and
Orange (+0x1CED = 1), Red (+0x1CEE = 1), Purple (rank 12), Chief (rank 13) or Blue (none); the renderer does
the same.  Change Appearance's head look (VVFP Head Look.dll) changes only the age compare at 0x4722A2.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, replace
from pathlib import Path

import vv_picture_image as pi
import vv_pictures_common as common

GAME = 5
ANIMPTS = "animpts.dat"

# ---------------------------------------------------------------------------------- the sprites

# The game's sprite descriptors (0x4D1A1C...: name, columns, rows, ".png", sheets across, down; the id is the
# dword before each), and the sprites the village manager keeps (0x46F870).
SPRITES = {
    0xF9: pi.Atlas("female_heads", 16, 30, (2, 1)),
    0xFA: pi.Atlas("female_bodies", 32, 30, (2, 3)),
    0xFB: pi.Atlas("female_actions", 17, 30, (1, 3)),
    0xFC: pi.Atlas("male_heads", 16, 30, (2, 1)),
    0xFD: pi.Atlas("male_bodies", 32, 30, (2, 3)),
    0xFE: pi.Atlas("male_actions", 17, 30, (1, 3)),
    0x101: pi.Atlas("vv5_heathenheads.png", 8, 5),
    0x103: pi.Atlas("skelly.png", 4, 1),
    0x104: pi.Atlas("ripple.png", 4, 1),
    0xE8: pi.Atlas("carrying.png", 13, 7),
    0xEC: pi.Atlas("collectables_small.png", 6, 9),
}
SHADOW = "peep_shadow1.png"          # id 0x102, a whole picture (0x44FC50)
SKELLY, RIPPLE, CARRYING, COLLECTABLES = 0x103, 0x104, 0xE8, 0xEC
MASKS = 0x101

# ---------------------------------------------------------------------------------- the table

BLOCK_A, BLOCK_B, BLOCK_C = 0x17E08, 0x29F0, 0x2C0      # animpts.dat's three blocks (0x451934, 0x451960, 0x451993)
RECORD = 0x1E8                                            # one anchor record
ANIM = 0x7A4                                              # one animation: 4 records + 4
ANIMS = 50
TURNS = 11                                                # head turns per sex (8 village + 3 Details)


@dataclass(frozen=True)
class Entry:
    sprite: int
    frame: int
    neck: tuple            # 30 (x, y): the head's place on each body row (+8)
    anchor: tuple          # 30 (x, y): each row's anchor (+0xF8)


def _entry(data: bytes, at: int) -> Entry:
    sprite, frame = struct.unpack_from("<ii", data, at)
    pairs = struct.unpack_from("<120i", data, at + 8)
    neck = tuple((pairs[2 * k], pairs[2 * k + 1]) for k in range(30))
    anchor = tuple((pairs[60 + 2 * k], pairs[61 + 2 * k]) for k in range(30))
    return Entry(sprite, frame, neck, anchor)


class AnimTable:
    """The animation table 0x5258B8 as the loader 0x451180 leaves it: animpts.dat's blocks A (at +0x7254, the
    animations from +0x7258), B (+0x1F05C, the heads) and C (+0x21A4C, the heathen masks), then the
    loader's own overwrites."""

    def __init__(self, data: bytes) -> None:
        if len(data) < 12 + BLOCK_A + BLOCK_B + BLOCK_C:
            raise pi.PictureError("The game's Assets\\animpts.dat is cut short.")
        size_a = struct.unpack_from("<I", data, 0)[0]
        if size_a != BLOCK_A:
            raise pi.PictureError("The game's Assets\\animpts.dat is not New Believers' own.")
        a = data[4:4 + BLOCK_A]
        at = 4 + BLOCK_A
        size_b = struct.unpack_from("<I", data, at)[0]
        b = data[at + 4:at + 4 + BLOCK_B]
        at += 4 + BLOCK_B
        size_c = struct.unpack_from("<I", data, at)[0]
        c = data[at + 4:at + 4 + BLOCK_C]
        if (size_b, size_c) != (BLOCK_B, BLOCK_C):
            raise pi.PictureError("The game's Assets\\animpts.dat is not New Believers' own.")
        # table +0x7254 is block A's start: animation n, record k at +0x7258 + n * 0x7A4 + k * 0x1E8
        self.anims = [[_entry(a, 4 + n * ANIM + k * RECORD) for k in range(4)] for n in range(ANIMS)]
        self.heads = [[_entry(b, (sex * TURNS + t) * RECORD) for t in range(TURNS)] for sex in range(2)]
        # masks: per head turn t, record at +0x21A4C + t * 0x58 (sprite, frame), offsets at
        # +0x21A7C + (t * 11 + colour) * 8 (0x451E16..0x451E73)
        self.masks = []
        for t in range(8):
            offsets = tuple(struct.unpack_from("<ii", c, 0x30 + (t * 11 + k) * 8) for k in range(5))
            self.masks.append(offsets)
        # the loader's overwrites (0x4519BD..0x451AEE)
        for sex in range(2):
            for t in range(8):
                e = self.heads[sex][t]
                self.heads[sex][t] = replace(e, sprite=0xFC if sex == 0 else 0xF9, frame=t)
            for t in range(8, 11):
                e = self.heads[sex][t]
                self.heads[sex][t] = replace(e, sprite=0xFF, frame=t - 8 + 3 * sex)
        for n in range(32, 49):
            for k, sprite in ((0, 0xFE), (2, 0xFB)):
                self.anims[n][k] = replace(self.anims[n][k], sprite=sprite, frame=n - 32)
        for k, frame in ((0, 0), (2, 1)):
            self.anims[49][k] = replace(self.anims[49][k], sprite=0x100, frame=frame)
        for n in range(32):
            for k, sprite in ((0, 0xFD), (2, 0xFA)):
                self.anims[n][k] = replace(self.anims[n][k], sprite=sprite, frame=n)


def _round(v: int, s: float) -> int:
    """trunc(v x s + 0.5), as 0x451CA0 / 0x451D00 / 0x451DA0 scale an anchor."""
    return int(v * s + 0.5)


# ---------------------------------------------------------------------------------- one villager


@dataclass
class Look:
    """What the draw reads from a villager record (fields as in docs/picture-studio-vv5.md)."""
    male: bool = True
    age: int = 600                  # age units (+0x1B8C)
    head: int = 0                   # +0x1BB8
    body: int = 0                   # +0x1BBC
    health: int = 100               # +0x1C40: 0 or less is a body (the skeleton)
    old: bool | None = None         # the old head; None: the game's own rule (age >= 1,100)
    faction: int = 0                # +0x1CEC: Heathen
    orange: int = 0                 # +0x1CED
    red: int = 0                    # +0x1CEE
    rank: int = 0                   # +0x1CFC: 12-16 purple, 13 chief
    cosmetic: int = 0               # the Origins cosmetic mask (1..5), drawn on a Believer only
    skeleton: int = 0               # +0x1B94: the skeleton's frame is this mod 4
    scale_factor: float = 1.0       # +0x1CCC


@dataclass
class Pose:
    pose: int = 0                   # +0x1CB4: 0-7 walking frames, 8-31 other columns, 32-48 actions
    direction: int = 0              # +0x1D00: 0-3 (the walking frames are offset by 8 per direction)
    turn: int = 5                   # +0x1D04: the head turn, 0-7
    shadow: bool = True
    swimming: bool = False
    ripple: int = 0                 # the swimming ripple's frame (the game picks rand & 3)
    item: int = -1                  # +0x1D0C: the carried item, -1 nothing, 0-79 carrying.png, 80+ collectables
    litter: int = 1                 # +0x1C50: copies of the carried item (a mother's 2 or 3 babies)
    x: int = 0
    y: int = 0


MASK_ROWS = {12: 3, 13: 4, 14: 3, 15: 3, 16: 3}          # the jump table at 0x472B60


def mask_row(look: Look) -> int:
    """The heathen mask's row (0x4728C6): ranks 12-16 Purple, 13 Chief; else Orange, Red, else Blue."""
    if look.rank in MASK_ROWS:
        return MASK_ROWS[look.rank]
    if look.orange:
        return 1
    if look.red:
        return 2
    return 0


def effective(look: Look) -> Look:
    """The patcher's cosmetic mask: a Believer with one is drawn as a Heathen of that colour (mask_flip)."""
    if look.faction or not 1 <= look.cosmetic <= 5:
        return look
    orange, red, rank = 0, 0, 0
    if look.cosmetic == 2:
        orange = 1
    elif look.cosmetic == 3:
        red = 1
    elif look.cosmetic == 4:
        rank = 12
    elif look.cosmetic == 5:
        rank = 13
    return replace(look, faction=1, orange=orange, red=red, rank=rank)


def child_scale(age: int, factor: float = 1.0) -> float:
    """0x466240."""
    if age < common.ADULT_AGE:
        return pi.f32((age / 700.0 + 0.5) * pi.f32(factor))
    return pi.f32(1.0 * pi.f32(factor))


def head_scale(age: int) -> float:
    """0x4722F3: (age / 14 + 80) / 100 for a child."""
    if age < common.ADULT_AGE:
        return pi.f32((age / 14.0 + 80.0) / 100.0)
    return 1.0


def _percent(f: float) -> float:
    """The blitter's scale for a draw at float scale f: trunc(100 x f) / 100.0 as a 32-bit float."""
    return pi.f32(int(100 * pi.f32(f)) / 100.0)


class Planner:
    def __init__(self, table: AnimTable, sheets: pi.Sheets) -> None:
        self.table = table
        self.sheets = sheets

    def _cell(self, sprite: int, row: int, col: int, x: int, y: int, f: float, what: str,
              alpha: float = 1.0) -> pi.Draw:
        atlas = SPRITES[sprite]
        # the linear frame row * columns + column, split again by C division (0x408DA0 -> 0x40AE90)
        down, across = pi._cdivmod(row * atlas.cols + col, atlas.cols)
        file, rect = self.sheets.cell(atlas, across, down)
        return pi.Draw(file, rect, x, y, _percent(f), alpha, what)

    def plan(self, look: Look, pose: Pose) -> list[pi.Draw]:
        t = self.table
        look = effective(look)
        X, Y = pose.x, pose.y
        s = child_scale(look.age, look.scale_factor)
        out: list[pi.Draw] = []
        if look.health <= 0:
            frame = pi._cdivmod(int(look.skeleton), 4)[1]            # [+0x1B94] & 0x80000003, C's remainder
            return [self._cell(SKELLY, 0, frame, X, Y, s, "skeleton")]
        sex = 0 if look.male else 1
        px, py = X - int(-20.0 * s), Y - int(-55.0 * s)
        yl = Y + (0x14 if pose.pose in (0x28, 0x29) else 0)
        anim = pose.pose + 8 * pose.direction if 0 <= pose.pose <= 7 else pose.pose
        if not 0 <= anim < ANIMS - 1:
            raise pi.PictureError(f"New Believers has no pose {anim}.")
        old = (look.age >= common.OLD_AGE) if look.old is None else look.old
        hs = head_scale(look.age)
        if not 0 <= look.head < 30 or not 0 <= look.body < 30:
            raise pi.PictureError("New Believers' heads and bodies are rows 0 to 29.")
        if not 0 <= pose.turn < 8:
            raise pi.PictureError("A head turn is 0 to 7.")
        head = t.heads[sex][pose.turn]
        ha = (_round(head.anchor[look.head][0], hs), _round(head.anchor[look.head][1], hs))
        swim = pose.swimming and pose.pose != 0x29
        water = pose.swimming                     # the tile test 0x47AD80 / 0x477820 (type 5): no shadow, nothing carried
        if pose.shadow and not water:
            out.append(self._whole(SHADOW, px - int(34 * s), py - int(32 * s), s, "shadow"))
        carry_first = pose.direction in (0, 3, 4)
        if carry_first and not water:
            out += self._carried(pose, X, yl + int(s * 18), "carried item")
        bx, by = px, yl + int(-(-55.0 * s))      # P.x and the lifted P.y (0x472551..0x472571)
        if swim:
            out.append(self._cell(RIPPLE, 0, pose.ripple & 3, bx - 0x20, by - 0x20, 1.0, "ripple", alpha=pi.f32(0.4)))
            hx, hy = bx - ha[0], by - ha[1]
        else:
            rec = t.anims[anim][2 * sex]
            ax, ay = rec.anchor[look.body]
            bx -= _round(ax, s)
            by -= _round(ay, s)
            out.append(self._cell(rec.sprite, look.body, rec.frame, bx, by, s, "body"))
            nx, ny = rec.neck[look.body]
            hx, hy = bx + _round(nx, s) - ha[0], by + _round(ny, s) - ha[1]
        out.append(self._cell(head.sprite, look.head, pose.turn + (8 if old else 0), hx, hy, hs, "head"))
        if look.faction:
            colour = mask_row(look)
            mx, my = t.masks[pose.turn][colour]
            ma = (_round(mx, hs), _round(my, hs))
            out.append(self._cell(MASKS, colour, pose.turn, hx + ha[0] - ma[0], hy + ha[1] - ma[1], hs, "mask"))
        if not carry_first and not water:
            out += self._carried(pose, X, yl + int(s * 18), "carried item")
        return out

    def _whole(self, name: str, x: int, y: int, f: float, what: str) -> pi.Draw:
        w, h = self.sheets.size(name)
        return pi.Draw(name, (0, 0, w, h), x, y, _percent(f), 1.0, what)

    def _carried(self, pose: Pose, x: int, y: int, what: str) -> list[pi.Draw]:
        if pose.item < 0:
            return []
        sprite, frame = (COLLECTABLES, pose.item - 0x50) if pose.item >= 0x50 else (CARRYING, pose.item)
        atlas = SPRITES[sprite]
        draws = [pi.Draw(*self.sheets.cell(atlas, frame % atlas.cols, frame // atlas.cols), x, y, 1.0, 1.0, what)]
        # the copies are always carrying.png at the item's own number (0x47021C, 0x470249: [manager + 0x24])
        copy = SPRITES[CARRYING]
        cell = self.sheets.cell(copy, pose.item % copy.cols, pose.item // copy.cols)
        if pose.litter > 1:
            draws.append(pi.Draw(*cell, x - 5, y + 5, 1.0, 1.0, what))
            if pose.litter == 3:
                draws.append(pi.Draw(*cell, x, y + 9, 1.0, 1.0, what))
        return draws


# ---------------------------------------------------------------------------------- the save

def save_look(v: common.SaveVillager) -> Look:
    """What a saved entry keeps (the writer 0x465270: entry +1 faction, +2 orange, +3 red, +0xC rank, then the
    record window +0x1B8C.. from +0x10; the name is at entry +0x20)."""
    return Look(male=v.male, age=v.age, head=v.head, body=v.body, health=v.health,
                faction=v.u8(-0x1F), orange=v.u8(-0x1E), red=v.u8(-0x1D), rank=v.i32(-0x14),
                cosmetic=v.mask, skeleton=v.i32(-8),
                old=None if v.look == common.LOOK_AUTO else v.look == common.LOOK_OLD)


def title_of(look: Look) -> str:
    """The owner's titles (special-titles-and-masks-in-logs): Heathens keep the game's; a converted one is
    told by the colour bytes the conversion 0x4668B0 leaves."""
    if look.faction:
        if look.rank == 13:
            return "Heathen Chief"
        colour = ("Blue", "Orange", "Red", "Purple", "Chief")[mask_row(look)]
        return f"Heathen ({colour.lower()} mask)"
    if look.rank == 13:
        return "Retired Heathen Chief"
    if look.orange:
        return "Former Heathen (orange mask)"
    if look.red:
        return "Former Heathen (red mask)"
    return ""


def stage_of(look: Look) -> str:
    if look.health <= 0:
        return "dead"
    if look.age < common.ADULT_AGE:
        return "child"
    return "elder" if look.age >= common.OLD_AGE else "adult"


# ---------------------------------------------------------------------------------- the renderer

DIRECTIONS = ("Front, facing left", "Back, facing left", "Front, facing right", "Back, facing right")
TURN_LABELS = ("Head turn 1", "Head turn 2", "Head turn 3", "Head turn 4 (back)", "Head turn 5 (right)",
               "Head turn 6 (front)", "Head turn 7 (left)", "Head turn 8")


def _pose_options() -> tuple:
    out = [pi.Option(("walk", f), f"Walking, frame {f + 1}") for f in range(8)]
    out += [pi.Option(("action", k), f"Action pose {k + 1}" + {8: " (sitting)", 9: " (lying down)"}.get(k, ""))
            for k in range(17)]
    return tuple(out)


def _pose_fields() -> tuple:
    return (
        pi.Field("pose", "Pose", _pose_options(), ("walk", 0)),
        pi.Field("direction", "Direction", tuple(pi.Option(k, d) for k, d in enumerate(DIRECTIONS)), 0),
        pi.Field("turn", "Head turn", tuple(pi.Option(k, t) for k, t in enumerate(TURN_LABELS)), 5),
        pi.Field("swimming", "Swimming", (pi.Option(False, "No"),) + tuple(
            pi.Option(k, f"Swimming, ripple {k + 1}") for k in range(4)), False),
        pi.Field("item", "Carrying", (pi.Option(-1, "Nothing"),) + tuple(
            pi.Option(k, f"Item {k + 1} (carrying.png)") for k in range(91)) + tuple(
            pi.Option(0x50 + k, f"Collectable {k + 1}") for k in range(54)), -1),
        pi.Field("litter", "Copies carried", (pi.Option(1, "One"), pi.Option(2, "Two (twins)"),
                                              pi.Option(3, "Three (triplets)")), 1),
        pi.Field("shadow", "Shadow", (pi.Option(True, "With shadow"), pi.Option(False, "No shadow")), True),
        pi.Field("skeleton", "Skeleton (the dead)", (pi.Option(None, "As the save has it"),) + tuple(
            pi.Option(k, f"Skeleton {k + 1}") for k in range(4)), None),
    )


def _pose_from(options: dict) -> Pose:
    kind = options.get("pose", ("walk", 0))
    if isinstance(kind, (list, tuple)):
        pose = kind[1] if kind[0] == "walk" else 32 + kind[1]
    else:
        pose = int(kind)
    swim = options.get("swimming", False)
    return Pose(pose=pose, direction=int(options.get("direction", 0) or 0), turn=int(options.get("turn", 5)),
                shadow=bool(options.get("shadow", True)), swimming=swim is not False and swim is not None,
                ripple=int(swim) if swim not in (False, None) else 0,
                item=int(options.get("item", -1)), litter=int(options.get("litter", 1) or 1))


def required_files() -> list[str]:
    files = []
    for sprite in (0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0x101, 0x103, 0x104, 0xE8, 0xEC):
        files += SPRITES[sprite].files()
    return files + [SHADOW]


def required_data_files() -> list[str]:
    """The game's own data the drawing reads (from Assets\\, not Images\\): the animation anchors."""
    return [ANIMPTS]


def patcher_art() -> dict[str, Path]:
    """New Believers needs none: its masks are the game's own (vv5_heathenheads.png), and the patcher's
    cosmetic masks are drawn with them."""
    return {}


def _read_data(source, name: str) -> bytes | None:
    data = source.read(name) if source is not None else None
    if data is not None:
        return data
    for holder in (source, getattr(source, "base", None)):
        copy = getattr(holder, "copy", None)
        if copy:
            path = Path(copy) / "Assets" / name
            try:
                return path.read_bytes()
            except OSError:
                continue
    return None


def load(source) -> "Renderer":
    return Renderer(source)


class Renderer:
    game = GAME

    def __init__(self, source) -> None:
        self.source = source
        self.sheets = pi.Sheets(source)
        self.problem = getattr(source, "problem", "") or ""
        self.table = None
        data = _read_data(source, ANIMPTS)
        if data is None:
            if not self.problem:
                self.problem = ("New Believers' Assets\\animpts.dat (where the game keeps where each head sits on "
                                "each body) was not found beside its Images folder.")
        else:
            try:
                self.table = AnimTable(data)
            except pi.PictureError as exc:
                self.problem = str(exc)
        self.planner = Planner(self.table, self.sheets) if self.table is not None else None

    def _need(self) -> Planner:
        if self.planner is None:
            raise pi.PictureError(self.problem or "The game's pictures were not found.")
        return self.planner

    # ---- From my save
    def saved_items(self, folder, slot) -> list[pi.SavedItem]:
        out = []
        for v in common.read_village(Path(folder), GAME, int(slot)):
            look = save_look(v)
            stage = stage_of(look)
            years = common.years(v.age)
            title = title_of(look)
            if look.health <= 0:
                where = "Bodies awaiting burial"
            elif look.faction:
                where = "Heathens"
            else:
                where = "Villagers"
            label = f"{v.name} ({stage}, {years} year{'s' if years != 1 else ''})"
            bits = [f"{'Male' if v.male else 'Female'}, {years} years ({v.age} age units)", f"head {v.head}",
                    f"body {v.body}"]
            if title:
                bits.append(title)
            if v.mask and not look.faction:
                bits.append(f"Origins mask: {common.MASK_NAMES[v.mask]} (patcher)")
            if v.look != common.LOOK_AUTO:
                bits.append(f"Head look: {common.LOOK_NAMES[v.look]} (patcher)")
            out.append(pi.SavedItem(f"{v.rank}", label, where, "heathen" if look.faction else stage,
                                    "; ".join(bits)))
        return out

    def saved_fields(self) -> tuple:
        return _pose_fields()

    def _saved(self, folder, slot, item_id) -> common.SaveVillager:
        for v in common.read_village(Path(folder), GAME, int(slot)):
            if str(v.rank) == str(item_id):
                return v
        raise pi.PictureError("That villager is no longer in the save.")

    def plan_saved(self, folder, slot, item_id, **options) -> list[pi.Draw]:
        look = save_look(self._saved(folder, slot, item_id))
        if options.get("skeleton") is not None:
            look = replace(look, skeleton=int(options["skeleton"]))
        return self._need().plan(look, _pose_from(options))

    def render_saved(self, folder, slot, item_id, **options) -> pi.Image:
        return pi.render_plan(self.sheets, self.plan_saved(folder, slot, item_id, **options))

    # ---- Make your own
    def custom_choices(self, *_args, **_kwargs) -> list[pi.Subject]:
        heads = tuple(pi.Option(k, f"Head {k}") for k in range(30))
        bodies = tuple(pi.Option(k, f"Body {k}") for k in range(30))
        stages = tuple(pi.Option(("child", y * 20), f"Child, {y} year{'s' if y != 1 else ''}") for y in range(14))
        stages += (pi.Option(("adult", 600), "Adult (30 years)"), pi.Option(("elder", 1200), "Elder (60 years)"),
                   pi.Option(("dead", 600), "Dead (skeleton)"))
        masks = (pi.Option(("none", 0), "No mask (Believer)"),
                 pi.Option(("heathen", 0), "Heathen: Blue mask"), pi.Option(("heathen", 1), "Heathen: Orange mask"),
                 pi.Option(("heathen", 2), "Heathen: Red mask"), pi.Option(("heathen", 3), "Heathen: Purple mask"),
                 pi.Option(("heathen", 4), "Heathen Chief: Chief mask"))
        masks += tuple(pi.Option(("cosmetic", k), f"Believer with the Origins {common.MASK_NAMES[k]}", patcher=True)
                       for k in range(1, 6))
        looks = (pi.Option(None, "Auto (old head from 55)"), pi.Option(False, "Young head", patcher=True),
                 pi.Option(True, "Old head", patcher=True))
        fields = (pi.Field("sex", "Sex", (pi.Option(True, "Male"), pi.Option(False, "Female")), True),
                  pi.Field("stage", "Life stage", stages, ("adult", 600)),
                  pi.Field("head", "Head", heads, 0), pi.Field("body", "Body", bodies, 0),
                  pi.Field("mask", "Mask", masks, ("none", 0)),
                  pi.Field("look", "Head look", looks, None)) + _pose_fields()
        note = ("Every head and body fits every age. The old head is drawn from 55 years (Auto), or always / never "
                "with Change Appearance's head look. Heathens wear the game's own masks; a Believer can wear the "
                "patcher's Origins mask. Children are drawn smaller, as the game does from birth to 14.")
        return [pi.Subject("villager", "Villager", fields, note)]

    def custom_look(self, spec: dict) -> Look:
        kind, age = spec.get("stage", ("adult", 600))
        look = Look(male=bool(spec.get("sex", True)), age=int(age), head=int(spec.get("head", 0)),
                    body=int(spec.get("body", 0)), health=0 if kind == "dead" else 100, old=spec.get("look"),
                    skeleton=int(spec.get("skeleton") or 0))
        mkind, value = spec.get("mask", ("none", 0))
        if mkind == "heathen":
            orange, red, rank = (value == 1), (value == 2), {3: 12, 4: 13}.get(value, 0)
            look = replace(look, faction=1, orange=int(orange), red=int(red), rank=rank)
        elif mkind == "cosmetic":
            look = replace(look, cosmetic=int(value))
        return look

    def plan_custom(self, spec: dict) -> list[pi.Draw]:
        return self._need().plan(self.custom_look(spec), _pose_from(spec))

    def render_custom(self, spec: dict) -> pi.Image:
        return pi.render_plan(self.sheets, self.plan_custom(spec))
