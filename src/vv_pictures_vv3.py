"""Picture Studio, The Secret City (Virtual Villagers 3): a villager drawn exactly as the game draws it.

Every rule here is the stock executable's own (docs/picture-studio-vv3.md), proven by
tests/test_pictures_vv3.py, which runs the game's own villager draw 0x4605F0 in Unicorn on the vanilla
executable -- with the game's own resource table, atlas constructors and camera -- and compares every
blit it makes with the plan below.

THE ATLASES (resource table 0x4A95A0, loaded by 0x45C730 into the village object 0x59E110):
    0x88 male_heads.png 8x30   0x89 male_heads_old.png   0x8A male_bodies 2x3 sheets 32x30
    0x8B male_actions 1x3 sheets 17x30, and 0x84-0x87 the same for women (sex +0xDC8 non-zero);
    0x8D peep_shadow1.png (whole), 0x71 carrying.png 13x4, 0x75 collectables_small.png 6x9,
    0x8E skelly.png 4x1, 0x8F ripple.png 4x1.

THE DRAW (0x4605F0, one villager record, ESI):
  * frame +0xEFC: 17..24 are the walking frames, drawn from the bodies atlas at column
    (frame - 17) + 8 x direction (+0xF14, 0..3); 0..16 are the actions atlas' columns, the frame itself.
    Frames 8 and 9 (sitting, lying) sit 20 pixels lower (0x4607A5).
  * size: under 280 age units (14 years) the body is drawn at age x 1/700 + 0.5 (0x455E50) and the head
    at (age / 14 + 80) / 100 (0x46091E); full size from 280.  Each goes through the camera 0x42E5E0 as
    trunc(100 x scale) percent (0x42E605), then 0x4093A0 as percent x 0.01f.
  * the head: old sheet from 1,100 units (0x46086D / 0x4608AE; Change Appearance's head look moves only
    this compare), row = head +0xDF0, column = head facing +0xF18, placed at
    x + trunc(dx x body scale) - trunc(head scale x 20), y + trunc(dy x body scale) - trunc(head scale x 27),
    (dx, dy) from the walking table 0x59E018 by direction or the action table 0x59E038 by frame (both
    filled by 0x4605F0 itself on its first call).
  * order: shadow (unless +0xF1C is 6 or the height +0xF04 is below 0), the carried item when the
    direction is 0, 3 or 4, the body (unless swimming), the head, the carried item when the direction is
    1, 2, 5, 6 or 7.  Swimming (the cmap's kind 5 under the feet, not held, frame not 9): no body, a
    ripple (alpha 0.4) and the head moved to the feet.
  * dead (health +0xE78 at or below 0): only skelly.png, column +0xDCC mod 4, at the body's scale.

The Origins cosmetic mask (patcher): the companion's VV3WorldMaskDrawAt
(native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c), called by the cave at 0x460C7F right
after the head, draws heathen_masks.png (8 x 5, the patcher's assets/vv3_heathen_masks/heathen_masks.png)
through the same 0x42E5E0 with the head's own x, y and scale: row = mask - 1, column = head facing & 7,
x + round(( -10 + (-4 for facings 0 and 1) ) x head scale), y + round(-33 x head scale).
"""
from __future__ import annotations

from pathlib import Path

import vv_picture_image as pi
import vv_pictures_common as common

GAME = 3
ROOT = Path(__file__).resolve().parents[1]
MASK_ART = ROOT / "assets" / "vv3_heathen_masks" / "heathen_masks.png"

ATLASES = {
    ("male", "heads"): pi.Atlas("male_heads.png", 8, 30),
    ("male", "heads_old"): pi.Atlas("male_heads_old.png", 8, 30),
    ("male", "bodies"): pi.Atlas("male_bodies", 32, 30, (2, 3)),
    ("male", "actions"): pi.Atlas("male_actions", 17, 30, (1, 3)),
    ("female", "heads"): pi.Atlas("female_heads.png", 8, 30),
    ("female", "heads_old"): pi.Atlas("female_heads_old.png", 8, 30),
    ("female", "bodies"): pi.Atlas("female_bodies", 32, 30, (2, 3)),
    ("female", "actions"): pi.Atlas("female_actions", 17, 30, (1, 3)),
}
SHADOW = "peep_shadow1.png"
CARRYING = pi.Atlas("carrying.png", 13, 4)
COLLECTABLES = pi.Atlas("collectables_small.png", 6, 9)
SKELLY = pi.Atlas("skelly.png", 4, 1)
RIPPLE = pi.Atlas("ripple.png", 4, 1)
MASKS = pi.Atlas("heathen_masks.png", 8, 5)

# The sheets' sizes in the stock game (used only when a plan is checked without the art).
SIZES = {"carrying.png": (520, 160), "collectables_small.png": (240, 360), "peep_shadow1.png": (68, 64),
         "skelly.png": (240, 65), "ripple.png": (260, 65), "heathen_masks.png": (520, 725)}
for _sex in ("male", "female"):
    SIZES[f"{_sex}_heads.png"] = SIZES[f"{_sex}_heads_old.png"] = (320, 1950)
    for _x in range(2):
        for _y in range(3):
            SIZES[f"{_sex}_bodies{_x}{_y}.png"] = (640, 650)
    for _y in range(3):
        SIZES[f"{_sex}_actions0{_y}.png"] = (680, 650)

HEAD_BY_DIRECTION = ((20, 16), (19, 16), (20, 15), (20, 17))                  # 0x59E018
HEAD_BY_FRAME = ((20, 24), (18, 26), (16, 28), (14, 30), (21, 18), (21, 18), (21, 18), (21, 18), (21, 14),
                 (2, 29), (20, 16), (24, 19), (22, 17), (18, 17), (20, 16), (20, 16), (20, 17))   # 0x59E038
WALK_FIRST, WALK_LAST = 17, 24
LOW_FRAMES = (8, 9)                     # sitting, lying: 20 pixels lower (0x4607A5)
NO_SHADOW_JOB = 6                       # +0xF1C 6: no shadow (0x4609D1)
NO_ITEM = -1
COLLECTABLE_FIRST = 0x34                # items from here are collectables_small.png (0x45F7F7)
SWIM_ITEM = 0x2A                        # the one item still drawn while swimming (0x460ADF)
CHIEF_ROBE = 29                         # the Tribal Chief's robe, the body 0x45FBDE gives the chief
MASK_X, MASK_Y = -10, -33               # VV3_WORLD_MASK_X/Y_NUDGE_PX
MASK_X_BY_FACING = (-4, -4, 0, 0, 0, 0, 0, 0)

F_BODY_RATE = pi.f32(1 / 700)           # 0x49DF28 (0.0014285714)
F_HALF = pi.f32(0.5)                    # 0x47C5F4
F_HEAD_RATE = pi.f32(1 / 14)            # 0x49E78C
F_HUNDREDTH = pi.f32(0.01)              # 0x47C614


# ---------------------------------------------------------------------------------- the game's numbers

def body_scale(age: int) -> float:
    """0x455E50: age x 1/700 + 0.5 under 280 units, else 1.0 (a 32-bit float)."""
    if age >= common.ADULT_AGE:
        return 1.0
    return pi.f32(age * F_BODY_RATE + F_HALF)


def body_scale_raw(age: int) -> float:
    """0x455E50's value as the x87 holds it (not stored to a float): age x 1/700 + 0.5, or 1.0."""
    if age >= common.ADULT_AGE:
        return 1.0
    return age * F_BODY_RATE + F_HALF


def head_scale(age: int) -> float:
    """0x46091E: (age x 1/14 + 80) x 0.01 under 280 units, else 1.0 (a 32-bit float)."""
    if age >= common.ADULT_AGE:
        return 1.0
    return pi.f32((age * F_HEAD_RATE + 80.0) * F_HUNDREDTH)


def camera_scale(scale: float) -> float:
    """0x42E5E0 / 0x42E570: trunc(100 x scale) percent, which 0x4093A0 / 0x4091A0 make percent x 0.01f."""
    return pi.percent_scale(int(100 * scale))


def mask_nudge(px: int, scale: float) -> int:
    """vv3_scaled_nudge: (float)px x scale, rounded half away from zero (in 32-bit floats)."""
    value = pi.f32(px * scale)
    return int(pi.f32(value + 0.5)) if value >= 0.0 else int(pi.f32(value - 0.5))


def _trunc(value: float) -> int:
    return int(value)


# ---------------------------------------------------------------------------------- a villager's state

class Look:
    """What a villager's picture depends on: the record's fields the draw reads."""

    def __init__(self, *, male: bool = True, age: int = 600, head: int = 0, body: int = 0, dead: bool = False,
                 dead_frame: int = 0, look: int = common.LOOK_AUTO, mask: int = 0, frame: int = WALK_FIRST,
                 direction: int = 1, facing: int | None = None, shadow: str = "on", item: int = NO_ITEM,
                 litter: int = 1, swimming: bool = False, ripple: int = 0, height: int = 0) -> None:
        self.male, self.age, self.head, self.body = male, age, head, body
        self.dead, self.dead_frame, self.look, self.mask = dead, dead_frame, look, mask
        self.frame, self.direction = frame, direction
        self.facing = direction if facing is None else facing
        self.shadow, self.item, self.litter = shadow, item, litter
        self.swimming, self.ripple, self.height = swimming, ripple, height

    @property
    def held(self) -> bool:
        return self.shadow == "held"


def _cell(sheets, atlas: pi.Atlas, col: int, row: int):
    return atlas.cell(sheets.size, col, row)


def _linear(sheets, atlas: pi.Atlas, frame: int):
    """0x409510 / 0x4090F0: a frame number as column frame % cols, row frame / cols."""
    row, col = pi._cdivmod(frame, atlas.cols)
    return _cell(sheets, atlas, col, row)


class _Sizes:
    """The stock sheets' sizes, for planning without the art (tests)."""

    @staticmethod
    def size(name: str):
        return SIZES[name]


def plan(look: Look, x: int = 0, y: int = 0, sheets=None, mask_art: bool = True) -> list[pi.Draw]:
    """The blits 0x4605F0 makes for a villager whose record holds (+0xEE0, +0xEE4) = (x, y), with the
    camera at no scroll and zoom 1.0 (0x42E250(0, 0, 1.0)), in the game's order, plus the patcher's
    cosmetic mask right after the head when `mask_art`."""
    sheets = sheets if sheets is not None else _Sizes
    sex = "male" if look.male else "female"
    s = body_scale(look.age)
    out: list[pi.Draw] = []
    low = 20 if look.frame in LOW_FRAMES else 0
    y_adj = y + low
    if look.dead:
        col = pi._cdivmod(look.dead_frame, 4)[1]
        file, rect = _cell(sheets, SKELLY, col, 0)
        return [pi.Draw(file, rect, x, y_adj, camera_scale(s), what="skeleton")]
    big_y = y_adj - look.height
    walking = WALK_FIRST <= look.frame <= WALK_LAST
    if walking:
        body_atlas = ATLASES[(sex, "bodies")]
        body_col = (look.frame - WALK_FIRST) + look.direction * 8
        hdx, hdy = HEAD_BY_DIRECTION[look.direction]
    else:
        if not 0 <= look.frame < len(HEAD_BY_FRAME):
            raise pi.PictureError(f"The Secret City has no pose {look.frame}.")
        body_atlas = ATLASES[(sex, "actions")]
        body_col = look.frame
        hdx, hdy = HEAD_BY_FRAME[look.frame]
    hs = head_scale(look.age)
    hx = _trunc(hdx * s) - _trunc(hs * 20.0) + x
    hy = _trunc(hdy * s) - _trunc(hs * 27.0) + big_y
    # the feet (0x455EF0): x - trunc(-20 s), y - trunc(-55 s), from the record's own y
    raw = body_scale_raw(look.age)
    ax = x - _trunc(raw * -20.0)
    ay = y - _trunc(raw * -55.0)
    if look.shadow != "off" and look.height >= 0:
        ss = pi.f32(s * F_HALF) if look.held else s
        sx = ax - _trunc(ss * 34.0)
        sy = ay - _trunc(ss * 32.0) + (20 if look.held else 0)
        w, h = sheets.size(SHADOW)
        out.append(pi.Draw(SHADOW, (0, 0, w, h), sx, sy, camera_scale(ss), what="shadow"))
    swimming = look.swimming
    item_shown = look.item != NO_ITEM and (not swimming or look.item == SWIM_ITEM)
    item_x = x + _trunc(_trunc(0.0) * raw)
    item_y = big_y + _trunc(_trunc(18.0) * raw)
    if item_shown and look.direction in (0, 3, 4):
        out += _items(sheets, look, item_x, item_y)
    if look.held or not swimming or look.frame == 9:
        file, rect = _cell(sheets, body_atlas, body_col, look.body)
        out.append(pi.Draw(file, rect, x, big_y, camera_scale(s), what="body"))
    else:
        # 0x460B74: the head moves to the feet; the ripple (0x409F80, no camera) under it
        hx = hx + ax - x - hdx
        hy = hy + ay - big_y - hdy
        file, rect = _linear(sheets, RIPPLE, look.ripple & 3)
        out.append(pi.Draw(file, rect, ax - 0x20, ay - 0x20, 1.0, pi.f32(0.4), what="ripple"))
    old = common.old_head(look.age, look.look)
    head_atlas = ATLASES[(sex, "heads_old" if old else "heads")]
    file, rect = _cell(sheets, head_atlas, look.facing, look.head)
    out.append(pi.Draw(file, rect, hx, hy, camera_scale(hs), what="head"))
    if mask_art and look.mask:
        facing = look.facing & 7
        mx = hx + mask_nudge(MASK_X + MASK_X_BY_FACING[facing], hs)
        my = hy + mask_nudge(MASK_Y, hs)
        file, rect = _cell(sheets, MASKS, facing, look.mask - 1)
        out.append(pi.Draw(file, rect, mx, my, camera_scale(hs), what="mask"))
    if item_shown and look.direction in (1, 2, 5, 6, 7):
        out += _items(sheets, look, item_x, item_y)
    return out


def _items(sheets, look: Look, x: int, y: int) -> list[pi.Draw]:
    """0x45F7E0: the carried item, and again for twins (-5, +5) and triplets (0, +9) -- those always from
    carrying.png with the item's own number, as the game does."""
    item = look.item
    if item >= COLLECTABLE_FIRST:
        file, rect = _linear(sheets, COLLECTABLES, item - COLLECTABLE_FIRST)
    else:
        file, rect = _linear(sheets, CARRYING, item)
    out = [pi.Draw(file, rect, x, y, what="item")]
    if look.litter > 1:
        file, rect = _linear(sheets, CARRYING, item)
        out.append(pi.Draw(file, rect, x - 5, y + 5, what="item"))
        if look.litter == 3:
            out.append(pi.Draw(file, rect, x, y + 9, what="item"))
    return out


# ---------------------------------------------------------------------------------- the choices

POSES = ([pi.Option(f"walk", "Walking")]
         + [pi.Option(k, f"{label}") for k, label in (
             (0, "Kneeling at work, 1"), (1, "Kneeling at work, 2"), (2, "Kneeling at work, 3"),
             (3, "Kneeling at work, 4"), (4, "Standing at work, 1"), (5, "Standing at work, 2"),
             (6, "Standing at work, 3"), (7, "Standing at work, 4"), (8, "Sitting"), (9, "Lying down"),
             (10, "Busy, 1"), (11, "Busy, 2"), (12, "Busy, 3"), (13, "Busy, 4"), (14, "Arms raised, 1"),
             (15, "Arms raised, 2"), (16, "Standing, facing you"))]
         + [pi.Option("swim", "Swimming")])
DIRECTIONS = (pi.Option(0, "Walking up and right"), pi.Option(1, "Walking down and right"),
              pi.Option(2, "Walking down and left"), pi.Option(3, "Walking up and left"))     # 0x455500
FRAMES = tuple(pi.Option(k, f"Frame {k + 1}") for k in range(8))
FACINGS = (pi.Option("auto", "As the walk (the game's own)"),) + tuple(
    pi.Option(k, f"Head picture {k + 1}") for k in range(8))
SHADOWS = (pi.Option("on", "Shadow"), pi.Option("held", "Shadow while held by the hand"),
           pi.Option("off", "No shadow"))


def pose_fields() -> tuple:
    return (pi.Field("pose", "Pose", tuple(POSES), "walk"),
            pi.Field("direction", "Direction", DIRECTIONS, 1),
            pi.Field("frame", "Frame", FRAMES, 0),
            pi.Field("facing", "Head turned", FACINGS, "auto"),
            pi.Field("shadow", "Shadow", SHADOWS, "on"))


def apply_pose(look: Look, pose: dict) -> Look:
    p = pose.get("pose", "walk")
    direction = int(pose.get("direction", 1) or 0) & 3
    frame = int(pose.get("frame", 0) or 0)
    look.direction = direction
    look.swimming = p == "swim"
    if p in ("walk", "swim", None):
        look.frame = WALK_FIRST + (frame & 7)
        look.ripple = frame & 3
    else:
        look.frame = int(p)
    facing = pose.get("facing", "auto")
    look.facing = direction if facing in (None, "auto") else int(facing)
    look.shadow = pose.get("shadow", "on") or "on"
    if look.dead:
        look.dead_frame = frame & 3
    return look


# ---------------------------------------------------------------------------------- the renderer

def required_files() -> list[str]:
    out = []
    for atlas in ATLASES.values():
        out += atlas.files()
    return out + [SHADOW, CARRYING.name, COLLECTABLES.name, SKELLY.name, RIPPLE.name]


# The release ships the same atlas inside the Origins companion (RCDATA 5000, native/vv3_full_mastery_candidate/
# vv3_full_mastery_candidate.rc), byte for byte the assets\ file (tests/test_pictures_vv3.py): it is read from there
# when the loose file is not beside the patcher (the release zip carries the DLL, not the loose file).
SHIPPED_DLL = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
MASK_RESOURCE = (10, 5000)                              # RT_RCDATA, id 5000


def patcher_art() -> dict:
    return {MASKS.name: MASK_ART} if MASK_ART.is_file() else {}


def mask_atlas_bytes() -> bytes | None:
    """heathen_masks.png as the patcher ships it: the assets\\ file, else the Origins companion's own copy."""
    try:
        return MASK_ART.read_bytes()
    except OSError:
        pass
    try:
        return pi.pe_resource(SHIPPED_DLL.read_bytes(), *MASK_RESOURCE)
    except OSError:
        return None


class _WithMasks:
    """The picture source, with the patcher's mask atlas behind it."""

    def __init__(self, source) -> None:
        self.source = source
        self.problem = getattr(source, "problem", "") or ""
        self.copy = getattr(source, "copy", None)

    def read(self, name: str):
        data = self.source.read(name) if self.source is not None else None
        if data is None and name.casefold() == MASKS.name.casefold():
            data = mask_atlas_bytes()
        return data


def load(source) -> "Renderer":
    return Renderer(_WithMasks(source))


# Saved-entry offsets from the name (the save keeps record +0xDC4..+0xEC4 in one run, the name at +0xDD4).
SAVE_DEAD_FRAME = 0xDCC - 0xDD4
SAVE_CHIEF = 0xE80 - 0xDD4
SAVE_LITTER = 0xE90 - 0xDD4
SAVE_SKILLS = 0xEAC - 0xDD4


class Renderer:
    game = GAME

    def __init__(self, source) -> None:
        self.source = source
        self.sheets = pi.Sheets(source)
        self.problem = getattr(source, "problem", "") or ""
        self._people: dict = {}

    # ---- From my save
    def _village(self, folder, slot):
        key = (str(folder), slot)
        people = common.read_village(Path(folder), GAME, slot)
        self._people[key] = {str(v.rank): v for v in people}
        return people

    @staticmethod
    def title_of(v: common.SaveVillager) -> str:
        if v.u8(SAVE_CHIEF):
            return "Tribal Chief"
        skills = [v.i32(SAVE_SKILLS + 4 * k) for k in range(5)]
        if sum(1 for s in skills if s >= 88) >= 3:
            return "Esteemed Elder"
        return ""

    def saved_items(self, folder, slot) -> list:
        items = []
        for v in self._village(folder, slot):
            stage = "dead" if v.dead else ("child" if v.age < common.ADULT_AGE else
                                           "elder" if v.age >= common.OLD_AGE else "adult")
            label = f"{v.name} ({stage}, {common.age_label(v.age)})"
            parts = ["Male" if v.male else "Female", common.age_label(v.age), f"head {v.head}", f"body {v.body}"]
            title = self.title_of(v)
            if title:
                parts.append(title)
            if v.mask:
                parts.append(f"{common.MASK_NAMES[v.mask]} (patcher)")
            if v.look:
                parts.append(f"head look {common.LOOK_NAMES[v.look]} (patcher)")
            where = "Bodies awaiting burial" if v.dead else "Villagers"
            items.append(pi.SavedItem(str(v.rank), label, where, "body" if v.dead else "villager", ", ".join(parts)))
        return items

    def saved_fields(self) -> tuple:
        return pose_fields()

    def saved_look(self, folder, slot, item_id) -> Look:
        people = self._people.get((str(folder), slot)) or {str(v.rank): v for v in self._village(folder, slot)}
        v = people.get(str(item_id))
        if v is None:
            raise pi.PictureError("That villager is not in the save any more.")
        return Look(male=v.male, age=v.age, head=v.head, body=v.body, dead=v.dead,
                    dead_frame=v.i32(SAVE_DEAD_FRAME), look=v.look, mask=v.mask)

    def plan_saved(self, folder, slot, item_id, **pose) -> list:
        look = self.saved_look(folder, slot, item_id)
        if pose:
            apply_pose(look, pose)
        return plan(look, sheets=self.sheets)

    def render_saved(self, folder, slot, item_id, **pose):
        return pi.render_plan(self.sheets, self.plan_saved(folder, slot, item_id, **pose))

    # ---- Make your own
    def custom_choices(self, *_args, **_kwargs) -> list:
        heads = tuple(pi.Option(k, f"Head {k}") for k in range(30))
        bodies = tuple(pi.Option(k, f"Body {k}" + (" (the Tribal Chief's robe)" if k == CHIEF_ROBE else ""))
                       for k in range(30))
        stages = (common.option_years(0, 13, "Child")
                  + [pi.Option(30 * common.UNITS_PER_YEAR, "Adult (14 to 54 years)"),
                     pi.Option(60 * common.UNITS_PER_YEAR, "Elder (55 years and over)"),
                     pi.Option("dead", "Dead (skeleton)")])
        masks = tuple(pi.Option(k, name, patcher=k > 0) for k, name in enumerate(common.MASK_NAMES))
        looks = (pi.Option(common.LOOK_AUTO, "Auto (old from 55)"), pi.Option(common.LOOK_YOUNG, "Young", True),
                 pi.Option(common.LOOK_OLD, "Old", True))
        items = ((pi.Option(NO_ITEM, "Nothing"),)
                 + tuple(pi.Option(k, f"carrying.png item {k + 1}") for k in range(52))
                 + tuple(pi.Option(COLLECTABLE_FIRST + k, f"collectables_small.png item {k + 1}") for k in range(54)))
        litters = (pi.Option(1, "One"), pi.Option(2, "Twins (drawn twice)"), pi.Option(3, "Triplets (drawn three times)"))
        fields = (pi.Field("sex", "Sex", (pi.Option("male", "Male"), pi.Option("female", "Female")), "male"),
                  pi.Field("stage", "Life stage", tuple(stages), 30 * common.UNITS_PER_YEAR),
                  pi.Field("head", "Head", heads, 0),
                  pi.Field("body", "Body", bodies, 0),
                  pi.Field("look", "Head look", looks, common.LOOK_AUTO),
                  pi.Field("mask", "Mask", masks, 0)) + pose_fields() + (
                  pi.Field("item", "Carrying", items, NO_ITEM),
                  pi.Field("litter", "Babies carried", litters, 1))
        note = ("Children grow from half size at birth to full size at 14, the head from 80%; from 55 the old head "
                "is drawn (or as the head look says). A Tribal Chief wears body 29. Dead villagers lie as a "
                "skeleton (frame 1-4). Masks and head looks are the patcher's.")
        return [pi.Subject("villager", "Villager", fields, note)]

    def custom_look(self, spec: dict) -> Look:
        stage = spec.get("stage", 600)
        dead = stage == "dead"
        look = Look(male=spec.get("sex", "male") != "female", age=600 if dead else int(stage),
                    head=int(spec.get("head", 0) or 0), body=int(spec.get("body", 0) or 0), dead=dead,
                    look=int(spec.get("look", 0) or 0), mask=int(spec.get("mask", 0) or 0),
                    item=int(spec.get("item", NO_ITEM) if spec.get("item") is not None else NO_ITEM),
                    litter=int(spec.get("litter", 1) or 1))
        return apply_pose(look, spec)

    def plan_custom(self, spec: dict) -> list:
        return plan(self.custom_look(spec), sheets=self.sheets)

    def render_custom(self, spec: dict):
        return pi.render_plan(self.sheets, self.plan_custom(spec))
