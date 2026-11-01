"""Picture Studio, A New Home (Virtual Villagers 1): a villager drawn exactly as the village draws it.

THE GAME'S OWN DRAW (docs/picture-studio-vv1.md has every rule and how each was proven).  The village
compositor 0x437790 (called from the frame at 0x4240FE) draws each record of the draw order
gameobj+0x3DBDC, in this order:

  1. the shadow block (0x4377BE-0x43795B): the ground test 0x414200 at (x + 0x14, y + 0x41) says water
     (0xF) -> a swimmer: no shadow, the selection circle focus_circle.png at (x - 13, y + 0x16) when
     selected (+0x29); else peep_shadow1.png at (x - 13, y + 0x13) (and the circle there when selected),
     or, while held by the hand (+0x2A, set by the pick-up 0x41DCCE / 0x41E14A, cleared by the drop
     0x439450), the shadow at (x - 13, y + 0x27) at surface alpha 0.5 (0x409400).  The Golden Child
     (+0x36C == 0xC7) never counts as swimming.  Nothing for a dead villager.
  2. the villager (0x43795B on):
     * dead (health +0x344 <= 0): skelly.png frame (+0x368 % 4) at (x, y), nothing else;
     * a child (age +0x348 < 0x118), drawn through the scaled cell draw 0x409410 at body scale
       age/7 + 50 % and head scale age/14 + 80 %, centred on the unscaled cell:
         - the Golden Child: always the MALE sheets; +0x58 6 or 7: male_actions column +0x20;
           state +0x38 == 2: male_actions column 8; else male_bodies column +0x20 + 8 * +0x30; the
           head (column +0x34) -- all at (x + 5, y + 13);
         - state 1 (bent over): the carried item (carrying.png, +0x3C unless 0x13) at (x - 5, y + 0x21);
           <sex>_actions column +0x20 at (x, y + 13); the head column 3 at (x - 2f - 2, y + 2f + 0x11)
           (f = +0x20);
         - any other state: the carried item at (x + 5, y + 0x24) behind the body when facing
           +0x30 is 0 or 3; <sex>_bodies column +0x20 + 8 * +0x30 at (x + 5, y + 13); the head column
           +0x34 at (x + 5, y + 13); the carried item in front when +0x30 is 1 or 2;
     * an adult, unscaled (0x4093C0):
         - in water (not held): ripple.png frame (random 0-3) at (x - 12, y + 0x1C) at surface alpha
           0.4 (0x4093E0; the 0.4 the random call 0x402F70 was given, still on the stack); the head
           column +0x34 at (x, y + 0x27); nothing else;
         - state 0 or 5 (walking): the carried item behind at (x, y + 0x10) for +0x30 0 or 3 (and
           again at (x - 5, y + 10) with a litter +0x35C, and (x, y + 5) with three); <sex>_bodies
           column +0x20 + 8 * +0x30 at (x, y + 3); the head column +0x34 at (x, y - 1); the carried
           item in front at (x, y + 0x19) for +0x30 1 or 2 (litter: (x - 5, y + 0x12), three: (x, y + 13));
         - state 1 (bent over): the item at (x - 5, y + 0x21); <sex>_actions column +0x20 at
           (x, y + 3); the head column 3 at (x - 2f - 2, y + 2f + 7);
         - state 2 (sitting): <sex>_actions column 8 at (x, y + 3); the head column +0x34 at
           (x, y + 7); the item for +0x30 1 or 2 at (x, y + 0x14) (litter (x - 5, y + 0x19), three
           (x, y + 0x1D));
         - state 3 (standing at work): the item at (x, y + 0x15); <sex>_actions column +0x20 + 4 at
           (x, y + 3); the head column 3 at (x, y - 2);
         - any other state: nothing (state 4 is skipped before the shadow).
  The row of every body and action cell is the body value (+0x364), of every head the head value
  (+0x360): a value is a sheet row (the owner's rule).

THE PATCHER'S OWN ART.
  * Origins masks (assets/origins/mask_atlas.png, 7 facings x 5 colours of 40 x 160, built by the
    companion's Vv1GetMaskSprite with the game's own constructor): the village hooks on 0x409410 and
    0x4093C0 (scripts/build_vv1_origins_feature.py, "Village all-pose mask") draw the head, then the mask
    with the head's own arguments but the mask atlas, row mask - 1, and y lifted: a child's by
    (scale * 15) >> 5 (its scaled draw), an adult's by 48.
  * Grey Hair at 55 (assets/vv1_grey_hair/vvfp_grey_<sex>_heads.png, the stock 7 x 20 layout): every
    village head draw takes the grey sheet when the villager is drawn grey -- age >= 1,100 under Auto,
    always under the head look Old, never under Young (native/vv1_grey_hair/vv1_grey_hair.c drawn_grey).
    The masks still see the young sheet, so a grey head keeps its mask.
  * Change Appearance's head look: the save's "Head Looks - Save <S>.dat" (vv_pictures_common).
  * The Golden Mushroom (Super-Secret Golden Mushroom, carried as item 15): "VVFP Golden Mushroom.dll"
    draws golden_mushroom.png in place of carrying.png frame 15, 6 right and 2 down (vv_pictures_carried).

WHAT A VILLAGER CARRIES: every item the game (or the patcher) puts in +0x3C is named in
vv_pictures_carried.VV1, with the ones nothing stores marked unused.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import vv_picture_image as pi
import vv_pictures_carried as carried
import vv_pictures_common as common

GAME = 1
ROOT = Path(__file__).resolve().parents[1]
GOLDEN = 0xC7
NO_ITEM = 0x13
ADULT = 0x118
WATER = 0xF
MASK_FILE = "mask_atlas.png"
GREY = {True: "vvfp_grey_male_heads.png", False: "vvfp_grey_female_heads.png"}

# gameobj offset -> the atlas the game builds there (0x43C08E-0x43C2EB): name, columns, rows, sheets.
ATLASES = {
    0x3DFF4: pi.Atlas("female_heads.png", 7, 20),
    0x3DFF8: pi.Atlas("male_heads.png", 7, 20),
    0x3DFE4: pi.Atlas("female_bodies", 32, 20, (2, 2)),
    0x3DFEC: pi.Atlas("female_actions", 9, 20, (1, 2)),
    0x3DFE8: pi.Atlas("male_bodies", 32, 20, (2, 2)),
    0x3DFF0: pi.Atlas("male_actions", 9, 20, (1, 2)),
    0x3E000: pi.Atlas("carrying.png", 15, 1),
    0x3E004: pi.Atlas("skelly.png", 4, 1),
    0x3E008: pi.Atlas("ripple.png", 4, 1),
}
# Whole-picture sprites (0x409ED0): drawn whole.
IMAGES = {0x3DFE0: "peep_shadow1.png", 0x3DFFC: "focus_circle.png"}
HEADS = {True: 0x3DFF8, False: 0x3DFF4}
BODIES = {True: 0x3DFE8, False: 0x3DFE4}
ACTIONS = {True: 0x3DFF0, False: 0x3DFEC}
CARRYING, SKELLY, RIPPLE, SHADOW, FOCUS = 0x3E000, 0x3E004, 0x3E008, 0x3DFE0, 0x3DFFC
MASK_ATLAS = pi.Atlas(MASK_FILE, 7, 5)
GREY_ATLAS = {True: pi.Atlas(GREY[True], 7, 20), False: pi.Atlas(GREY[False], 7, 20)}

HEAD_ROWS = 20
BODY_ROWS = 20
RIPPLE_ALPHA = pi.f32(0.4)
SAVE_EXPECTING = 0x358 - 0x370      # the conception stamp, from the name: non-zero = carrying the baby
SAVE_LITTER = 0x35C - 0x370         # the litter (2 twins, 3 triplets)
SHADOW_HELD_ALPHA = 0.5


def required_files() -> list[str]:
    files = []
    for atlas in ATLASES.values():
        files += atlas.files()
    return files + list(IMAGES.values())


def patcher_art() -> dict[str, Path]:
    return {
        carried.GOLDEN_FILE: carried.GOLDEN_ART,
        MASK_FILE: ROOT / "assets" / "origins" / "mask_atlas.png",
        GREY[True]: ROOT / "assets" / "vv1_grey_hair" / "vvfp_grey_male_heads.png",
        GREY[False]: ROOT / "assets" / "vv1_grey_hair" / "vvfp_grey_female_heads.png",
    }


@dataclass(frozen=True)
class Villager:
    """The record fields the village draw reads (A New Home record offsets in the comments)."""
    male: bool = True               # +0x350 == 1
    age: int = 600                  # +0x348, age units
    head: int = 0                   # +0x360
    body: int = 0                   # +0x364
    health: int = 100               # +0x344
    golden: bool = False            # +0x36C == 0xC7
    state: int = 0                  # +0x38
    direction: int = 0              # +0x30
    frame: int = 0                  # +0x20
    head_col: int = 5               # +0x34
    item: int = NO_ITEM             # +0x3C
    litter: int = 0                 # +0x35C
    act: int = 0                    # +0x58
    bones: int = 0                  # +0x368 (the skeleton's frame, % 4)
    selected: bool = False          # +0x29 == 1
    held: bool = False              # +0x2A != 0
    water: bool = False             # the ground test 0x414200 says 0xF
    ripple: int = 0                 # the random ripple frame (0x402F70 & 3)
    mask: int = 0                   # the Origins cosmetic mask 1..5 (patcher)
    grey: bool = False              # drawn from Grey Hair's sheet (patcher)
    expecting: bool = False         # +0x358 non-zero: carries the baby (item 3) after loading


def _cdiv(a: int, b: int) -> int:
    return pi._cdivmod(a, b)[0]


class Planner:
    """Turns the game's wrapper calls into blits (pi.Draw), as each wrapper does."""

    def __init__(self, sheets: pi.Sheets, x: int, y: int) -> None:
        self.sheets, self.x0, self.y0 = sheets, x, y
        self.out: list[pi.Draw] = []

    def _atlas(self, slot) -> pi.Atlas:
        return slot if isinstance(slot, pi.Atlas) else ATLASES[slot]

    def image(self, slot: int, x: int, y: int, what: str) -> None:
        """0x4093A0 -> 0x408590: the whole picture at (x, y)."""
        name = IMAGES[slot]
        w, h = self.sheets.size(name)
        self.out.append(pi.Draw(name, (0, 0, w, h), self.x0 + x, self.y0 + y, what=what))

    def image_faded(self, slot: int, x: int, y: int, alpha: float, what: str) -> None:
        """0x409400 -> 0x408A40 (atlas, x, y, alpha, scale 100, centre): the whole picture at a surface alpha."""
        name = IMAGES[slot]
        w, h = self.sheets.size(name)
        self.out.append(pi.Draw(name, (0, 0, w, h), self.x0 + x, self.y0 + y, 1.0, pi.f32(alpha), what=what))

    def cell(self, slot, x: int, y: int, row: int, col: int, what: str) -> None:
        """0x4093C0 -> 0x408740: cell (col, row), unscaled."""
        name, rect = self.sheets.cell(self._atlas(slot), col, row)
        self.out.append(pi.Draw(name, rect, self.x0 + x, self.y0 + y, what=what))

    def frame(self, slot, x: int, y: int, frame: int, what: str, alpha: float = 1.0) -> None:
        """0x4093D0 -> 0x4087B0 (and 0x4093E0 -> 0x408840 with a surface alpha): frame n is column
        n % columns, row n / columns."""
        atlas = self._atlas(slot)
        name, rect = self.sheets.cell(atlas, frame - _cdiv(frame, atlas.cols) * atlas.cols, _cdiv(frame, atlas.cols))
        self.out.append(pi.Draw(name, rect, self.x0 + x, self.y0 + y, 1.0, alpha, what=what))

    def scaled(self, slot, x: int, y: int, row: int, col: int, percent: int, what: str) -> None:
        """0x409410 -> 0x408AF0 (centred): the cell at percent / 100, moved by place-scaled 0x407ED0 so
        it stays centred on the unscaled cell."""
        name, rect = self.sheets.cell(self._atlas(slot), col, row)
        dx, dy = pi.centre_offset(rect[2] - rect[0], rect[3] - rect[1], percent)
        self.out.append(pi.Draw(name, rect, self.x0 + x + dx, self.y0 + y + dy, pi.percent_scale(percent), what=what))


def plan(v: Villager, sheets: pi.Sheets, x: int = 0, y: int = 0, shadow: bool = True,
         golden_art: bool = True) -> list[pi.Draw]:
    """The blits 0x437790 makes for one record at (x, y) (camera at 0), with the patcher's masks and
    grey heads.  `shadow` False leaves out the shadow and selection circle (a picture of the villager
    alone; the game always draws them).  `golden_art` False leaves the Golden Mushroom (item 15) to the
    stock frame draw, as the game draws it without the "VVFP Golden Mushroom.dll" companion."""
    p = Planner(sheets, x, y)
    if v.state == 4:                    # 0x4377BE: a record in state 4 is not drawn at all
        return p.out
    swimming =v.water and not v.held and not v.golden
    if shadow and v.health > 0:
        if swimming:
            if v.selected:
                p.image(FOCUS, -13, 0x16, "selection circle")
        elif v.selected and not v.held:
            p.image(SHADOW, -13, 0x13, "shadow")
            p.image(FOCUS, -13, 0x13, "selection circle")
        elif not v.held:
            p.image(SHADOW, -13, 0x13, "shadow")
        else:
            p.image_faded(SHADOW, -13, 0x27, SHADOW_HELD_ALPHA, "shadow (held)")

    def head_scaled(hx: int, hy: int, col: int, percent: int) -> None:
        sheet = GREY_ATLAS[True] if v.golden and v.grey else (GREY_ATLAS[v.male] if v.grey else None)
        slot = HEADS[True] if v.golden else HEADS[v.male]
        p.scaled(sheet or slot, hx, hy, v.head, col, percent, "head")
        if v.mask and v.age < ADULT:
            p.scaled(MASK_ATLAS, hx, hy - ((percent * 15) >> 5), v.mask - 1, col, percent, "mask")

    def head_cell(hx: int, hy: int, col: int) -> None:
        p.cell(GREY_ATLAS[v.male] if v.grey else HEADS[v.male], hx, hy, v.head, col, "head")
        if v.mask:
            p.cell(MASK_ATLAS, hx, hy - 48, v.mask - 1, col, "mask")

    def item(ix: int, iy: int) -> None:
        if golden_art and v.item == carried.GOLDEN_ITEM[GAME]:
            # VVFP Golden Mushroom.dll at the frame-draw thunk 0x4093D0: carrying.png frame 15 becomes
            # golden_mushroom.png (frame 0 of a 1 x 1 sprite) moved by (6, 2)
            p.out.append(carried.golden_draw(GAME, p.x0 + ix, p.y0 + iy, sheets=sheets))
            return
        p.frame(CARRYING, ix, iy, v.item, "carried")

    if v.health <= 0:
        p.frame(SKELLY, 0, 0, v.bones - _cdiv(v.bones, 4) * 4, "skeleton")
        return p.out
    if v.age < ADULT:
        body_pct = _cdiv(v.age, 7) + 50
        head_pct = _cdiv(v.age, 14) + 80
        if v.golden:
            if v.act in (6, 7):
                p.scaled(ACTIONS[True], 5, 13, v.body, v.frame, body_pct, "body")
            elif v.state == 2:
                p.scaled(ACTIONS[True], 5, 13, v.body, 8, body_pct, "body")
            else:
                p.scaled(BODIES[True], 5, 13, v.body, v.frame + v.direction * 8, body_pct, "body")
            head_scaled(5, 13, v.head_col, head_pct)
            return p.out
        if v.state == 1:
            if v.item != NO_ITEM:
                item(-5, 0x21)
            p.scaled(ACTIONS[v.male], 0, 13, v.body, v.frame, body_pct, "body")
            head_scaled(-2 * v.frame - 2, 2 * v.frame + 0x11, 3, head_pct)
            return p.out
        if v.direction in (0, 3) and v.item != NO_ITEM:
            item(5, 0x24)
        p.scaled(BODIES[v.male], 5, 13, v.body, v.frame + v.direction * 8, body_pct, "body")
        head_scaled(5, 13, v.head_col, head_pct)
        if v.direction in (1, 2) and v.item != NO_ITEM:
            item(5, 0x24)
        return p.out
    if swimming:
        p.frame(RIPPLE, -12, 0x1C, v.ripple & 3, "ripple", RIPPLE_ALPHA)
        head_cell(0, 0x27, v.head_col)
        return p.out
    if v.state in (0, 5):
        if v.direction in (0, 3) and v.item != NO_ITEM:
            item(0, 0x10)
            if v.litter:
                item(-5, 0xA)
                if v.litter == 3:
                    item(0, 5)
        p.cell(BODIES[v.male], 0, 3, v.body, v.frame + v.direction * 8, "body")
        head_cell(0, -1, v.head_col)
        if v.direction in (1, 2) and v.item != NO_ITEM:
            item(0, 0x19)
            if v.litter:
                item(-5, 0x12)
                if v.litter == 3:
                    item(0, 0xD)
    elif v.state == 1:
        if v.item != NO_ITEM:
            item(-5, 0x21)
        p.cell(ACTIONS[v.male], 0, 3, v.body, v.frame, "body")
        head_cell(-2 * v.frame - 2, 2 * v.frame + 7, 3)
    elif v.state == 2:
        p.cell(ACTIONS[v.male], 0, 3, v.body, 8, "body")
        head_cell(0, 7, v.head_col)
        if v.direction in (1, 2) and v.item != NO_ITEM:
            item(0, 0x14)
            if v.litter:
                item(-5, 0x19)
                if v.litter == 3:
                    item(0, 0x1D)
    elif v.state == 3:
        if v.item != NO_ITEM:
            item(0, 0x15)
        p.cell(ACTIONS[v.male], 0, 3, v.body, v.frame + 4, "body")
        head_cell(0, -2, 3)
    return p.out


# ---------------------------------------------------------------------------------------- poses

DIRECTIONS = ((0, "Direction 1"), (1, "Direction 2"), (2, "Direction 3"), (3, "Direction 4"))
HEAD_FACINGS = tuple((c, f"Head facing {c + 1}") for c in range(7))
POSES = (
    ("walk", "Walking / standing (state 0)"),
    ("bend", "Bent over at work (state 1)"),
    ("sit", "Sitting (state 2)"),
    ("reach", "Standing at work (state 3)"),
    ("swim", "Swimming (adults; children and the Golden Child are drawn as on land, without a shadow)"),
    ("golden_act", "The Golden Child's own action (+0x58 = 6)"),
)
POSE_STATE = {"walk": 0, "bend": 1, "sit": 2, "reach": 3, "swim": 0, "golden_act": 0}
FRAMES = {"walk": 8, "bend": 4, "sit": 1, "reach": 4, "swim": 1, "golden_act": 9}


def _options(pairs) -> tuple:
    return tuple(pi.Option(k, label) for k, label in pairs)


def pose_fields() -> tuple:
    return (
        pi.Field("pose", "Pose", _options(POSES), "walk"),
        pi.Field("direction", "Body direction", _options(DIRECTIONS), 2),
        pi.Field("frame", "Frame", tuple(pi.Option(f, f"Frame {f + 1}") for f in range(9)), 0),
        pi.Field("head_col", "Head facing", _options(HEAD_FACINGS), 5),
        pi.Field("item", "Carrying", carried.options(GAME), NO_ITEM),
        pi.Field("litter", "Babies carried (litter +0x35C)",
                 _options(((0, "One"), (2, "Twins (the item drawn twice)"), (3, "Triplets (the item drawn three times)"),
                           (1, "Two (litter 1: never set by the game)"))), 0),
        pi.Field("shadow", "Shadow", _options(((True, "Shadow (as the game draws it)"), (False, "No shadow"))), True),
        pi.Field("selected", "Selected", _options(((False, "Not selected"), (True, "Selected (circle)"))), False),
        pi.Field("held", "Held by the hand", _options(((False, "On the ground"), (True, "Picked up"))), False),
        pi.Field("ripple", "Ripple frame (swimming)", tuple(pi.Option(r, f"Ripple {r + 1}") for r in range(4)), 0),
        pi.Field("bones", "Skeleton frame (dead)", tuple(pi.Option(b, f"Skeleton {b + 1}") for b in range(4)), 0),
    )


def saved_pose_fields() -> tuple:
    """From my save: the pose pickers, and whether the save's game has Grey Hair at 55 (the window may
    set the default from the game copy; the patch is on by default).  The save does not keep the carried
    item (+0x3C is outside the saved +0x33C..+0x3D8): after loading, the reset 0x439470 gives a villager
    expecting (+0x358 non-zero) the baby, item 3, and everyone else nothing -- the "As the game shows it"
    choice; the litter +0x35C is saved."""
    fields = []
    for f in pose_fields():
        if f.key == "item":
            f = pi.Field("item", f.label, carried.options(GAME, saved=True), carried.SAVED)
        elif f.key == "litter":
            f = pi.Field("litter", f.label, (pi.Option(carried.SAVED, "As in the save"),) + f.options, carried.SAVED)
        fields.append(f)
    return tuple(fields) + (
        pi.Field("grey_hair", "Grey Hair at 55",
                 (pi.Option(True, "On (grey from 55, or as the head look says)", patcher=True),
                  pi.Option(False, "Off (the stock game: never grey)")), True),
    )


def _apply_pose(v: Villager, pose: dict) -> tuple[Villager, bool]:
    name = pose.get("pose", "walk")
    if name not in POSE_STATE:
        raise pi.PictureError(f"A New Home has no pose called {name!r}.")
    frame = int(pose.get("frame", 0))
    if not 0 <= frame < FRAMES[name]:
        frame = min(max(frame, 0), FRAMES[name] - 1)
    v = replace(v, state=POSE_STATE[name], frame=frame,
                direction=int(pose.get("direction", v.direction)) & 3,
                head_col=int(pose.get("head_col", v.head_col)),
                item=carried.resolve(pose.get("item", v.item), v.expecting, NO_ITEM),
                litter=v.litter if pose.get("litter") in (None, carried.SAVED) else int(pose["litter"]),
                selected=bool(pose.get("selected", False)), held=bool(pose.get("held", False)),
                water=name == "swim", ripple=int(pose.get("ripple", 0)) & 3,
                act=6 if name == "golden_act" else 0)
    if "bones" in pose:
        v = replace(v, bones=int(pose["bones"]))
    return v, bool(pose.get("shadow", True))


# ---------------------------------------------------------------------------------------- renderer

def stage_word(age: int, golden: bool = False) -> str:
    if golden:
        return "the Golden Child"
    if age < ADULT:
        return "child"
    return "elder" if age >= common.OLD_AGE else "adult"


def _babies(litter: int) -> str:
    return {2: "twins", 3: "triplets"}.get(litter, "a baby")


class Renderer:
    game = GAME

    def __init__(self, source) -> None:
        self.source = source
        self.sheets = pi.Sheets(source)
        self.problem = getattr(source, "problem", "") or ""
        self._cache: dict = {}

    # ---- From my save
    def _village(self, folder, slot: int) -> list[common.SaveVillager]:
        key = (str(folder), slot)
        if key not in self._cache:
            self._cache = {key: common.read_village(Path(folder), GAME, slot)}
        return self._cache[key]

    def villager_of(self, s: common.SaveVillager) -> Villager:
        """The record as the save keeps it (+0x33C..+0x3D8 of each record; offsets from the name +0x370)."""
        golden = s.i32(0x36C - 0x370) == GOLDEN
        return Villager(male=s.male, age=s.age, head=s.head, body=s.body, health=s.health, golden=golden,
                        bones=s.i32(0x368 - 0x370), mask=s.mask, expecting=s.i32(SAVE_EXPECTING) != 0,
                        litter=s.i32(SAVE_LITTER),
                        grey=common.old_head(s.age, s.look))

    def saved_items(self, folder, slot: int) -> list[pi.SavedItem]:
        out = []
        for s in self._village(folder, slot):
            v = self.villager_of(s)
            if s.dead:
                where, kind, stage = "Bodies awaiting burial", "body", "dead"
            else:
                where, kind, stage = "Villagers", "villager", stage_word(s.age, v.golden)
            label = f"{s.name} ({stage}, {common.age_label(s.age)})"
            detail = (f"{'Male' if s.male else 'Female'}, {common.age_label(s.age)}; head {s.head}, body {s.body}; "
                      f"mask: {common.MASK_NAMES[s.mask] if 0 <= s.mask < len(common.MASK_NAMES) else s.mask}; "
                      f"head look: {common.LOOK_NAMES.get(s.look, s.look)}"
                      + ("; grey (Grey Hair at 55)" if v.grey and not s.dead else "")
                      + (f"; expecting: carries {_babies(v.litter)}" if v.expecting and not s.dead else ""))
            out.append(pi.SavedItem(str(s.rank), label, where, kind, detail))
        return out

    def saved_fields(self) -> tuple:
        return saved_pose_fields()

    def _saved(self, folder, slot: int, item_id: str) -> common.SaveVillager:
        for s in self._village(folder, slot):
            if str(s.rank) == str(item_id):
                return s
        raise pi.PictureError("That villager is no longer in the save.")

    def plan_saved(self, folder, slot: int, item_id: str, **pose) -> list[pi.Draw]:
        s = self._saved(folder, slot, item_id)
        base = self.villager_of(s)
        if not pose.pop("grey_hair", True):
            base = replace(base, grey=False)
        if "bones" not in pose:
            pose = dict(pose, bones=base.bones)
        v, shadow = _apply_pose(base, pose)
        return plan(v, self.sheets, shadow=shadow)

    def render_saved(self, folder, slot: int, item_id: str, **pose) -> pi.Image:
        return pi.render_plan(self.sheets, self.plan_saved(folder, slot, item_id, **pose))

    # ---- Make your own
    def custom_choices(self, *_args, **_kwargs) -> list[pi.Subject]:
        stages = [pi.Option(("child", y * common.UNITS_PER_YEAR), f"Child, {y} year{'s' if y != 1 else ''}")
                  for y in range(2, 14)]
        stages += [pi.Option(("adult", 14 * common.UNITS_PER_YEAR), "Adult, 14 years (full size)"),
                   pi.Option(("adult", 30 * common.UNITS_PER_YEAR), "Adult, 30 years"),
                   pi.Option(("elder", common.OLD_AGE), "Elder, 55 years (grey with Grey Hair at 55)", patcher=False),
                   pi.Option(("dead", 0), "Dead (skeleton)"),
                   pi.Option(("golden", 100), "The Golden Child (5 years)")]
        fields = (
            pi.Field("sex", "Sex", _options(((True, "Male"), (False, "Female"))), True),
            pi.Field("stage", "Life stage", tuple(stages), ("adult", 30 * common.UNITS_PER_YEAR)),
            pi.Field("head", "Head", tuple(pi.Option(r, f"Head {r}") for r in range(HEAD_ROWS)), 0),
            pi.Field("body", "Body", tuple(pi.Option(r, f"Body {r}") for r in range(BODY_ROWS)), 0),
            pi.Field("mask", "Mask (Origins)", tuple(pi.Option(m, common.MASK_NAMES[m], patcher=m > 0)
                                                      for m in range(6)), 0),
            pi.Field("look", "Head look (Grey Hair at 55)",
                     (pi.Option(common.LOOK_AUTO, "Auto (grey from 55)", patcher=True),
                      pi.Option(common.LOOK_YOUNG, "Young (never grey)", patcher=True),
                      pi.Option(common.LOOK_OLD, "Old (grey)", patcher=True),
                      pi.Option(-1, "Stock game (no Grey Hair patch)")), -1),
        ) + pose_fields()
        note = ("Children are drawn smaller every year until 14 (body age/7 + 50 %, head age/14 + 80 %). The "
                "Golden Child is always drawn with the boys' pictures. Grey heads and masks are the patcher's "
                "own art (Grey Hair at 55, Origins).")
        return [pi.Subject("villager", "Villager", fields, note)]

    def villager_from_spec(self, spec: dict) -> tuple[Villager, bool]:
        kind, age = spec.get("stage") or ("adult", 600)
        male = bool(spec.get("sex", True))
        look = spec.get("look", -1)
        look = -1 if look is None else int(look)
        golden = kind == "golden"
        v = Villager(male=True if golden else male, age=int(age), head=int(spec.get("head") or 0),
                     body=int(spec.get("body") or 0), health=0 if kind == "dead" else 100, golden=golden,
                     mask=int(spec.get("mask") or 0),
                     grey=look >= 0 and common.old_head(int(age), look) and kind != "dead")
        pose = {k: spec[k] for k in ("pose", "direction", "frame", "head_col", "item", "litter", "shadow",
                                     "selected", "held", "ripple", "bones") if k in spec and spec[k] is not None}
        if kind != "golden" and pose.get("pose") == "golden_act":
            raise pi.PictureError("Only the Golden Child has that action.")
        return _apply_pose(v, pose)

    def plan_custom(self, spec: dict) -> list[pi.Draw]:
        v, shadow = self.villager_from_spec(spec)
        return plan(v, self.sheets, shadow=shadow)

    def render_custom(self, spec: dict) -> pi.Image:
        return pi.render_plan(self.sheets, self.plan_custom(spec))


def load(source) -> Renderer:
    if isinstance(source, (str, Path)):
        source = pi.FolderSource(Path(source))
    if not hasattr(source, "patcher"):
        source = _WithPatcherArt(source)
    return Renderer(source)


class _WithPatcherArt:
    """A source that also reads the patcher's own art from assets\\ (when given a plain game folder)."""

    def __init__(self, base) -> None:
        self.base = base
        self.problem = getattr(base, "problem", "")
        self.copy = getattr(base, "copy", None)
        self.art = {k.casefold(): v for k, v in patcher_art().items()}

    def read(self, name: str) -> bytes | None:
        path = self.art.get(name.casefold())
        if path is not None:
            try:
                return path.read_bytes()
            except OSError:
                return None
        return self.base.read(name)
