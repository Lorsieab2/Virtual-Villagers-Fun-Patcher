"""Picture Studio, The Lost Children (Virtual Villagers 2): its villagers drawn exactly as the game's own
village compositor draws them (docs/picture-studio-vv2.md).

THE DRAW CODE, ported.  The village compositor 0x445B50 (one loop over the 256 record slots, 0x445C1C ..
0x4478DE) draws each villager from its record (the record at game + 0xE57090 index x 0xE48C):

  * a shadow (peep_shadow1.png) and, when selected, the focus circle -- or, while the villager is held up
    by the hand (+0x32, cleared by the drop 0x42CE30), a faded shadow lower down;
  * an Esteemed Elder statue (+0x558): its own shadow and totems.png frame (+0x550 mod 8);
  * a body awaiting burial (health +0x52C <= 0): skelly.png frame (+0x550 mod 4);
  * a child (age +0x530 below 0x118, 14 years): body and head scaled down by age (body age/7 + 50 per
    cent, head age/14 + 80), in the pose of its state (+0x40): walking, bending, sitting, in the air;
  * an adult: body and head full size, the old head sheets from age 1,100 (55 years); its state:
    walking / standing (0, 5, 9), bending (1), sitting (2), arms up (3), in the air (8, 10), resting
    (9 with an odd +0x550) -- or swimming in deep water (terrain 0x18 at its feet: the ripple and the head);
  * what it carries (+0x44: carrying.png, collectables_images.png) and, for a litter (+0x544), the
    copies the game draws of it.

Every one of those branches is in `plan()` below in the game's own order, with the game's own offsets,
cells and scales; tests/test_pictures_vv2.py runs the compositor itself in Unicorn on the stock
executable for thousands of records and requires the same blits (sheet, cell, place, scale, alpha).

THE ENGINE'S PRIMITIVES are A New Home's, byte for byte (the atlas constructors 0x40A270 / 0x40A2F0, the
cell cut 0x40A190, place-scaled 0x408160, the blitter 0x404000): src/vv_picture_image.py's Atlas, centring
and blit rules hold here too (also proven in the tests).

THE PATCHER'S OWN ART AND CHANGES:
  * the Origins heathen masks (the "Enable Origins-Exclusive Features and Heathen Masks" patch,
    scripts/build_vv2_mask_stage2.py, shipped as the .vvmk section): the adult head thunk 0x4095B0 and
    the child head thunk 0x409600 draw the head, then the mask atlas heathen_masks.png (8 x 5 cells of
    65 x 145; row = the mask - 1, column = the head's own column) -- adults unscaled at (x, y - 42),
    children at the head's scale and (x, y - (scale x 54 >> 7)).  The atlas is the one the patch ships
    inside "VVFP VV2 Origins Icons.dll" (RCDATA 5000), read from assets\\origins.  The stubs' gate is
    the patch's own: any draw through those thunks from the village whose sheet is one of the five
    "head" sheets the patch lists (which include female_actions) -- so a woman's action body whose
    value equals her head value, and a girl's action body, get a mask too, as in the game;
  * Change Appearance's head look ("VVFP Head Look.dll"): in the village it changes only the compare at
    0x4469BA, the swimming head; every other village head keeps the game's own age rule (0x44C);
  * the Elder Totems patch ("VVFP VV2 Totems.dll"): statues kept in its own ElderTotems.dat instead of
    villager records, drawn exactly as a statue record (its draw_one); From my save lists them too.

Nothing here writes anything.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, replace
from pathlib import Path

import vv_picture_image as pi
import vv_pictures_common as common

GAME = 2
ROOT = Path(__file__).resolve().parents[1]
ORIGINS_DLL = ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll"
MASK_FILE = "heathen_masks.png"
MASK_RESOURCE = (10, 5000)          # RT_RCDATA, id 5000 (native/vv2_origins_icons/vv2_origins_icons.rc)

COMPOSITOR_START, COMPOSITOR_END = 0x445B50, 0x4478DE   # the village compositor
HEADS = 30
BODIES = 30
CHILD_AGE = 0x118                   # 280 units: full size from here (0x445E4F)
OLD_AGE = 0x44C                     # 1,100 units: the old head sheets (0x445C32, 0x4469BA)
NO_ITEM = 0x1A                      # +0x44: carrying nothing
DEEP_WATER = 0x18                   # terrain 0x4181D0 at the feet: swimming (0x4468CA)
MASK_ADULT_LIFT = 0x2A              # build_vv2_mask_stage2.py ADULT_MASK_DY
MASK_CHILD_MUL, MASK_CHILD_SHIFT = 54, 7

# The atlases as the asset loader builds them (0x44C232 .. 0x44C599), by the game object's slot.
ATLAS = {
    "f_heads": pi.Atlas("female_heads.png", 7, 30),            # +0xE574A8
    "f_heads_old": pi.Atlas("female_heads_old.png", 7, 30),    # +0xE574B0
    "f_bodies": pi.Atlas("female_bodies", 32, 30, (2, 3)),     # +0xE57498
    "f_actions": pi.Atlas("female_actions", 9, 30, (1, 3)),    # +0xE574A0
    "m_heads": pi.Atlas("male_heads.png", 7, 30),              # +0xE574AC
    "m_heads_old": pi.Atlas("male_heads_old.png", 7, 30),      # +0xE574B4
    "m_bodies": pi.Atlas("male_bodies", 32, 30, (2, 3)),       # +0xE5749C
    "m_actions": pi.Atlas("male_actions", 9, 30, (1, 3)),      # +0xE574A4
    "totems": pi.Atlas("totems.png", 8, 1),                    # +0xE574CC
    "shadow": pi.Atlas("peep_shadow1.png", 1, 1),              # +0xE57494 (a whole picture)
    "focus": pi.Atlas("focus_circle.png", 1, 1),               # +0xE574B8 (a whole picture)
    "carrying": pi.Atlas("carrying.png", 13, 2),               # +0xE574BC
    "collectables": pi.Atlas("collectables_images.png", 6, 9),  # +0xE574C0
    "skelly": pi.Atlas("skelly.png", 4, 1),                    # +0xE574C4
    "ripple": pi.Atlas("ripple.png", 4, 1),                    # +0xE574C8
}
MASK_ATLAS = pi.Atlas(MASK_FILE, 8, 5)
# The sheets the mask stubs treat as heads (build_vv2_mask_stage2.py HEAD_ATLASES 0xE574A0..0xE574B4).
MASKED_SHEETS = ("f_actions", "f_heads", "m_heads", "f_heads_old", "m_heads_old")


def required_files() -> list[str]:
    out = []
    for atlas in ATLAS.values():
        out += atlas.files()
    return out


def patcher_art() -> dict[str, Path]:
    """The patcher's own art this renderer uses.  The masks live inside the Origins DLL (RCDATA 5000), so
    they are read by `load` itself; nothing here is a loose picture."""
    return {}


# ------------------------------------------------------------------------------------------ the masks

def _pe_resource(data: bytes, kind: int, ident: int) -> bytes | None:
    """One resource of a PE file (the first language), pure Python."""
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


def mask_atlas_bytes(dll: Path = ORIGINS_DLL) -> bytes | None:
    """heathen_masks.png as the Origins patch ships it (inside its DLL, which extracts it at startup)."""
    try:
        return _pe_resource(dll.read_bytes(), *MASK_RESOURCE)
    except OSError:
        return None


class _WithMasks:
    """The picture source, plus the patch's mask atlas from its DLL."""

    def __init__(self, source, dll: Path = ORIGINS_DLL) -> None:
        self.source = source
        self.dll = dll
        self.problem = getattr(source, "problem", "")
        self._mask: bytes | None | bool = False

    def read(self, name: str) -> bytes | None:
        if name.casefold() == MASK_FILE:
            if self._mask is False:
                self._mask = mask_atlas_bytes(self.dll)
            if self._mask is not None:
                return self._mask
        return self.source.read(name) if self.source is not None else None


# ------------------------------------------------------------------------------------------ the record

@dataclass(frozen=True)
class State:
    """The record fields the village compositor reads, and the world it asks about."""
    male: bool = True
    age: int = 600                  # +0x530, age units
    head: int = 0                   # +0x548
    body: int = 0                   # +0x54C
    health: int = 100               # +0x52C
    state: int = 0                  # +0x40
    direction: int = 0              # +0x38 (0..3)
    frame: int = 0                  # +0x20
    facing: int = 5                 # +0x3C, the head's column (0..6)
    height: int = 0                 # +0x24, how high in the air (states 8 and 10)
    item: int = NO_ITEM             # +0x44
    litter: int = 0                 # +0x544
    variant: int = 0                # +0x550 (statue kind, skeleton and resting frames)
    statue: bool = False            # +0x558
    selected: bool = False          # +0x31
    held: bool = False              # +0x32, held up by the hand
    hidden: bool = False            # state 4 (not drawn)
    terrain: int = 0                # 0x4181D0 at (x + 0x14, y + 0x41)
    timer: int = 0                  # 0x403200: the ripple's frame is its low two bits
    mask: int = 0                   # the Origins patch's mask, 1..5 (0: none)
    masks_patch: bool = True        # the mask stubs are in the game
    look: int = common.LOOK_AUTO    # Change Appearance's head look


def _cdiv(a: int, b: int) -> int:
    return pi._cdivmod(a, b)[0]


def _crem(a: int, b: int) -> int:
    return pi._cdivmod(a, b)[1]


def _sar(a: int, n: int) -> int:
    return a >> n


def child_body_scale(age: int) -> int:
    """age / 7 + 50 (the magic-number division at 0x445F7D)."""
    return _cdiv(age, 7) + 50


def child_head_scale(age: int) -> int:
    """age / 14 + 80 (0x445FE3)."""
    return _cdiv(age, 14) + 80


class _Planner:
    """Builds one villager's blits in the compositor's order."""

    def __init__(self, sheets: pi.Sheets, st: State, x: int, y: int) -> None:
        self.sheets, self.st, self.x, self.y = sheets, st, x, y
        self.out: list[pi.Draw] = []

    # the game's draw wrappers -------------------------------------------------------------------
    def whole(self, key: str, x: int, y: int, what: str) -> None:              # 0x4095A0 -> 0x408820
        file, rect = self.sheets.cell(ATLAS[key], 0, 0)
        self.out.append(pi.Draw(file, rect, x, y, what=what))

    def whole_faded(self, key: str, x: int, y: int, alpha: float, percent: int, what: str) -> None:
        # 0x4095F0 -> 0x408C40: a whole picture at a surface alpha and scale, centred
        file, rect = self.sheets.cell(ATLAS[key], 0, 0)
        dx, dy = pi.centre_offset(rect[2] - rect[0], rect[3] - rect[1], percent)
        self.out.append(pi.Draw(file, rect, x + dx, y + dy, pi.percent_scale(percent), pi.f32(alpha), what=what))

    def frame(self, key: str, x: int, y: int, n: int, what: str, alpha: float | None = None) -> None:
        # 0x4095C0 -> 0x4089B0 (and, with an alpha, 0x4095D0 -> 0x408A40): a cell by its number
        atlas = ATLAS[key]
        file, rect = self.sheets.cell(atlas, _crem(n, atlas.cols), _cdiv(n, atlas.cols))
        if alpha is None:
            self.out.append(pi.Draw(file, rect, x, y, what=what))
        else:
            self.out.append(pi.Draw(file, rect, x, y, 1.0, pi.f32(alpha), what=what))

    def cell(self, key: str, x: int, y: int, row: int, col: int, what: str) -> None:
        # 0x4095B0 -> 0x408940; the Origins adult mask stub when it is in the game
        self._cell(ATLAS[key], x, y, row, col, what)
        st = self.st
        if (st.masks_patch and key in MASKED_SHEETS and row == st.head and 1 <= st.mask <= 5):
            self._cell(MASK_ATLAS, x, y - MASK_ADULT_LIFT, st.mask - 1, col, "mask")

    def _cell(self, atlas: pi.Atlas, x: int, y: int, row: int, col: int, what: str) -> None:
        file, rect = self.sheets.cell(atlas, col, row)
        self.out.append(pi.Draw(file, rect, x, y, what=what))

    def scaled(self, key: str, x: int, y: int, row: int, col: int, percent: int, what: str) -> None:
        # 0x409600 -> 0x408CF0 (centred); the Origins child mask stub when it is in the game
        self._scaled(ATLAS[key], x, y, row, col, percent, what)
        st = self.st
        if st.masks_patch and key in MASKED_SHEETS and 1 <= st.mask <= 5:
            lift = _sar(percent * MASK_CHILD_MUL, MASK_CHILD_SHIFT)
            self._scaled(MASK_ATLAS, x, y - lift, st.mask - 1, col, percent, "mask")

    def _scaled(self, atlas: pi.Atlas, x: int, y: int, row: int, col: int, percent: int, what: str) -> None:
        file, rect = self.sheets.cell(atlas, col, row)
        dx, dy = pi.centre_offset(rect[2] - rect[0], rect[3] - rect[1], percent)
        self.out.append(pi.Draw(file, rect, x + dx, y + dy, pi.percent_scale(percent), what=what))

    # the compositor -----------------------------------------------------------------------------
    def plan(self) -> list[pi.Draw]:
        st, x, y = self.st, self.x, self.y
        state = 4 if st.hidden else st.state
        if state == 4:
            return self.out
        alive = st.health > 0
        # 0x445C75: the shadow, the focus circle
        if st.selected and not st.held and state not in (4, 8) and alive:
            self.whole("shadow", x - 0xD, y + 0x13, "shadow")
            self.whole("focus", x - 0xD, y + 0x13, "selection circle")
        elif state != 4 and alive and state != 8:
            if not st.held:
                self.whole("shadow", x - 0xD, y + 0x13, "shadow")
            else:
                self.whole_faded("shadow", x - 0xD, y + 0x27, 0.5, 100, "shadow")
        # 0x445D88: an Esteemed Elder statue
        if st.statue:
            self.whole("shadow", x - 0x11, y + 0x3B, "statue shadow")
            self.frame("totems", x, y, _crem(st.variant, 8), "statue")
            return self.out
        # 0x445E14: a body awaiting burial
        if not alive:
            self.frame("skelly", x, y, _crem(st.variant, 4), "skeleton")
            return self.out
        if st.age < CHILD_AGE:
            self._child(state)
        else:
            self._adult(state)
        return self.out

    def _item(self, x: int, y: int, minus: int | None) -> None:
        """A carried item: carrying.png below NO_ITEM, else collectables_images.png at item - `minus`
        (None: the branch draws carrying.png whatever the value)."""
        item = self.st.item
        if item == NO_ITEM:
            return
        if minus is None or item < NO_ITEM:
            self.frame("carrying", x, y, item, "carried")
        else:
            self.frame("collectables", x, y, item - minus, "carried")

    def _child(self, state: int) -> None:
        st, x, y = self.st, self.x, self.y
        sex = "m" if st.male else "f"
        bs, hs = child_body_scale(st.age), child_head_scale(st.age)
        f = st.frame
        if state == 1:                                                      # 0x445EEF
            self._item(x - 5, y + 0x21, 0x1A)
            self.scaled(f"{sex}_actions", x, y + 0xD, st.body, f, bs, "body")
            self.scaled(f"{sex}_heads", x - 2 * f - 2, y + 2 * f + 0xA, st.head, 3, hs, "head")
        elif state == 2:                                                    # 0x4460EF
            self.scaled(f"{sex}_actions", x, y + 0xA, st.body, 8, bs, "body")
            self.scaled(f"{sex}_heads", x, y + 9, st.head, st.facing, hs, "head")
            if st.direction in (1, 2) and st.item != NO_ITEM:
                self.frame("carrying", x, y + 0x14, st.item, "carried")
        elif state == 10:                                                   # 0x446295
            h = st.height
            if st.item != NO_ITEM:
                self.frame("carrying", x, y - h + 0x15, st.item, "carried")
            if f == 3:
                self.scaled(f"{sex}_bodies", x, y - h + 0xD, st.body, 7, bs, "body")
                self.scaled(f"{sex}_heads", x, y - h + 5, st.head, 1, hs, "head")
            else:
                self.scaled(f"{sex}_bodies", x, y - h + 0xD, st.body, f + 4, bs, "body")
                self.scaled(f"{sex}_heads", x, y - h + 5, st.head, 3, hs, "head")
        else:                                                               # 0x4465E7
            if st.direction in (0, 3):
                self._item(x + 5, y + 0x24, 0x1E)
            self.scaled(f"{sex}_bodies", x + 5, y + 0xD, st.body, f + st.direction * 8, bs, "body")
            self.scaled(f"{sex}_heads", x + 5, y + 6, st.head, st.facing, hs, "head")
            if st.direction in (1, 2):
                self._item(x + 5, y + 0x24, 0x1E)

    def _adult(self, state: int) -> None:
        st, x, y = self.st, self.x, self.y
        sex = "m" if st.male else "f"
        old = st.age >= OLD_AGE
        heads = f"{sex}_heads_old" if old else f"{sex}_heads"
        f = st.frame
        if not st.held and st.terrain == DEEP_WATER and state != 9:         # 0x4468A6: swimming
            self.frame("ripple", x - 0xC, y + 0x1C, st.timer & 3, "ripple", alpha=0.4)
            shown = {common.LOOK_YOUNG: 0, common.LOOK_OLD: OLD_AGE}.get(st.look, st.age)
            swim_heads = f"{sex}_heads_old" if shown >= OLD_AGE else f"{sex}_heads"
            self.cell(swim_heads, x, y + 0x1F, st.head, st.facing, "head")
            return
        if state in (0, 5, 9):                                              # 0x4473AD
            if st.direction in (0, 3) and st.item != NO_ITEM:
                self.frame("carrying", x, y + 0x10, st.item, "carried")
                if st.litter:
                    self.frame("carrying", x - 5, y + 0xA, st.item, "carried")
                    if st.litter == 3:
                        self.frame("carrying", x, y + 5, st.item, "carried")
            if state == 9 and _crem(st.variant, 2) == 1:
                self.cell(f"{sex}_actions", x, y + 3, st.body, 8, "body")
                self.cell(heads, x, y - 1, st.head, st.facing, "head")
            else:
                self.cell(f"{sex}_bodies", x, y + 3, st.body, f + st.direction * 8, "body")
                self.cell(heads, x, y - 9, st.head, st.facing, "head")
            if st.direction in (1, 2) and st.item != NO_ITEM:
                self.frame("carrying", x, y + 0x19, st.item, "carried")
                if st.litter:
                    self.frame("carrying", x - 5, y + 0x12, st.item, "carried")
                    if st.litter == 3:
                        self.frame("carrying", x, y + 0xD, st.item, "carried")
        elif state == 1:                                                    # 0x446A7B
            if st.item != NO_ITEM:
                self.frame("carrying", x - 5, y + 0x21, st.item, "carried")
            self.cell(f"{sex}_actions", x, y + 3, st.body, f, "body")
            self.cell(heads, x - 2 * f - 2, y + 2 * f - 1, st.head, 3, "head")
        elif state == 2:                                                    # 0x446C38
            self.cell(f"{sex}_actions", x, y + 3, st.body, 8, "body")
            self.cell(heads, x, y - 1, st.head, st.facing, "head")
            if st.direction in (1, 2) and st.item != NO_ITEM:
                self.frame("carrying", x, y + 0x14, st.item, "carried")
                if st.litter:
                    self.frame("carrying", x - 5, y + 0x19, st.item, "carried")
                    if st.litter == 3:
                        self.frame("carrying", x, y + 0x1D, st.item, "carried")
        elif state == 3:                                                    # 0x446E3C
            if st.item != NO_ITEM:
                self.frame("carrying", x, y + 0x15, st.item, "carried")
            self.cell(f"{sex}_actions", x, y + 3, st.body, f + 4, "body")
            self.cell(heads, x, y - 0xA, st.head, 3, "head")
        elif state in (8, 10):                                              # 0x446F32, 0x4470CC
            h = st.height
            if st.item != NO_ITEM:
                self.frame("carrying", x, y - h + 0x15, st.item, "carried")
            sheet = f"{sex}_actions" if state == 8 else f"{sex}_bodies"
            if f == 3:
                self.cell(sheet, x, y - h + 3, st.body, 7, "body")
                self.cell(heads, x, y - h - 0xA, st.head, 1, "head")
            else:
                self.cell(sheet, x, y - h + 3, st.body, f + 4, "body")
                self.cell(heads, x, y - h - 0xA, st.head, 3, "head")
        # any other state draws nothing but the shadow (0x4470CF)


def plan(sheets: pi.Sheets, st: State, x: int = 0, y: int = 0) -> list[pi.Draw]:
    """The blits the village compositor makes for this record, its top-left at (x, y) on screen."""
    return _Planner(sheets, st, x, y).plan()


# ------------------------------------------------------------------------------------------ the poses

POSES = (
    ("walk", "Walking or standing"),
    ("bend", "Bending over (working)"),
    ("sit", "Sitting"),
    ("arms", "Standing, arms out"),
    ("air_actions", "In the air (action frames)"),
    ("air_walk", "In the air (walking frames)"),
    ("rest", "Resting"),
    ("swim", "Swimming (adults)"),
)
POSE_STATE = {"walk": 0, "bend": 1, "sit": 2, "arms": 3, "air_actions": 8, "air_walk": 10, "rest": 9, "swim": 0}
DIRECTIONS = ((0, "Direction 1"), (1, "Direction 2"), (2, "Direction 3"), (3, "Direction 4"))
FACINGS = tuple((k, f"Head column {k + 1}") for k in range(7))
SHADOWS = (("shadow", "Shadow"), ("none", "No shadow"), ("selected", "Shadow and selection circle"),
           ("held", "Held up by the hand (faded shadow below)"))
MASK_OPTIONS = tuple(pi.Option(k, common.MASK_NAMES[k], patcher=k > 0) for k in range(6))


def _carry_options() -> tuple:
    out = [pi.Option(NO_ITEM, "Nothing")]
    out += [pi.Option(k, f"carrying.png picture {k + 1}") for k in range(26)]
    out += [pi.Option(k, f"collectables_images.png picture {k - 0x1A + 1}") for k in range(0x1B, 0x1B + 54)]
    return tuple(out)


def pose_fields() -> tuple:
    return (
        pi.Field("pose", "Pose", tuple(pi.Option(k, t) for k, t in POSES), "walk"),
        pi.Field("direction", "Direction", tuple(pi.Option(k, t) for k, t in DIRECTIONS), 0),
        pi.Field("frame", "Frame", tuple(pi.Option(k, f"Frame {k + 1}") for k in range(8)), 0),
        pi.Field("facing", "Head turned", tuple(pi.Option(k, t) for k, t in FACINGS), 5),
        pi.Field("height", "Height in the air", tuple(pi.Option(k, f"{k} pixels") for k in (0, 4, 8, 12, 16, 20)), 8),
        pi.Field("ripple", "Ripple frame", tuple(pi.Option(k, f"Frame {k + 1}") for k in range(4)), 0),
        pi.Field("carrying", "Carrying", _carry_options(), NO_ITEM),
        pi.Field("shadow", "Shadow", tuple(pi.Option(k, t) for k, t in SHADOWS), "shadow"),
    )


def _apply_pose(st: State, pose: dict) -> State:
    name = pose.get("pose", "walk")
    if name not in POSE_STATE:
        raise pi.PictureError(f"There is no pose {name!r} in The Lost Children.")
    shadow = pose.get("shadow", "shadow")
    frame = int(pose.get("frame", 0) or 0)
    if name in ("bend", "arms", "air_actions", "air_walk"):
        frame = min(frame, 3)
    st = replace(st, state=POSE_STATE[name], direction=int(pose.get("direction", 0) or 0), frame=frame,
                 facing=int(pose.get("facing", 5) if pose.get("facing") is not None else 5),
                 height=int(pose.get("height", 8) or 0), item=int(pose.get("carrying", NO_ITEM)),
                 timer=int(pose.get("ripple", 0) or 0),
                 selected=shadow == "selected", held=shadow == "held")
    if name == "swim":
        st = replace(st, terrain=DEEP_WATER)
    if name == "rest":
        st = replace(st, variant=st.variant | 1 if st.variant >= 0 else 1)
    plan_shadow = shadow != "none"
    return replace(st, hidden=False), plan_shadow


def _drop_shadows(plan_list: list[pi.Draw]) -> list[pi.Draw]:
    return [d for d in plan_list if d.what not in ("shadow", "selection circle", "statue shadow")]


# ------------------------------------------------------------------------------------------ the renderer

def stage_label(v_age: int, dead: bool = False, statue: bool = False) -> str:
    if statue:
        return "statue"
    if dead:
        return "body"
    if v_age < CHILD_AGE:
        return "child"
    return "elder" if v_age >= OLD_AGE else "adult"


@dataclass
class _Saved:
    v: common.SaveVillager | None
    state: State
    name: str = ""


# The Elder Totems patch ("VVFP VV2 Totems.dll", native/vvfp_vv2_totems): the statues it keeps out of the
# villager records, in the save's own data folder, drawn with the game's own calls exactly as a statue
# record is (draw_one: the shadow at (x - 0x11, y + 0x3B), totems.png frame Totem Type % 8).
TOTEMS_MAGIC = b"VVFP VV2 TOTEMS\0"
TOTEM_ENTRY = 0x2E0
TOTEM_NAME, TOTEM_TYPE, TOTEM_AGE, TOTEM_SEX, TOTEM_HEAD, TOTEM_BODY = 0x40, 0x2C, 0x0C, 0x14, 0x24, 0x28


def totems_file(folder: Path, slot: int) -> Path:
    return (Path(folder) / "Virtual Villagers Fun Patcher" / f"Save {int(slot)}" / "Data" / "Elder Totems"
            / "ElderTotems.dat")


def read_totems(folder: Path, slot: int) -> list[dict]:
    """The Elder Totems patch's statues for a save slot (its own file, checked as the DLL checks it:
    magic, version 1 or 2, game 2, entry size, exact length, FNV-1a hash), read only; [] when none."""
    try:
        d = totems_file(folder, slot).read_bytes()
    except OSError:
        return []
    if len(d) < 44 or d[:16] != TOTEMS_MAGIC:
        return []
    version, game, _slot, entry, rows, count = struct.unpack_from("<iiiiII", d, 16)
    header = 40 if version == 1 else 72
    if version not in (1, 2) or game != GAME or entry != TOTEM_ENTRY or rows > 256 or count > 100000:
        return []
    if header + rows * 36 + count * TOTEM_ENTRY + 4 != len(d):
        return []
    h = common.FNV_BASIS
    for b in d[:-4]:
        h = ((h ^ b) * common.FNV_PRIME) & 0xFFFFFFFF
    if h != struct.unpack_from("<I", d, len(d) - 4)[0]:
        return []
    out = []
    start = header + rows * 36
    for k in range(count):
        e = d[start + k * TOTEM_ENTRY:start + (k + 1) * TOTEM_ENTRY]
        i = lambda off: struct.unpack_from("<i", e, off)[0]   # noqa: E731
        out.append({"name": e[TOTEM_NAME:TOTEM_NAME + 0x18].split(b"\0", 1)[0].decode("latin-1"),
                    "type": i(TOTEM_TYPE), "age": i(TOTEM_AGE), "male": i(TOTEM_SEX) == 1,
                    "head": i(TOTEM_HEAD), "body": i(TOTEM_BODY)})
    return out


class Renderer:
    game = GAME

    def __init__(self, source) -> None:
        self.source = _WithMasks(source)
        self.sheets = pi.Sheets(self.source)
        self.problem = getattr(source, "problem", "") or ""
        self._cache: dict = {}

    # ---- From my save
    def _read(self, folder, slot: int) -> dict[str, _Saved]:
        key = (str(folder), int(slot))
        found = self._cache.get(key)
        if found is None:
            people = common.read_village(Path(folder), GAME, int(slot))
            found = {}
            for v in people:
                st = State(male=v.male, age=v.age, head=v.head, body=v.body, health=v.health,
                           litter=v.i32(0x544 - 0x564), variant=v.i32(0x550 - 0x564), statue=v.statue,
                           mask=v.mask, look=v.look)
                found[f"r{v.rank}"] = _Saved(v, st, v.name)
            for k, t in enumerate(read_totems(Path(folder), int(slot))):
                st = State(male=t["male"], age=t["age"], head=t["head"], body=t["body"], health=0,
                           variant=t["type"], statue=True)
                found[f"t{k}"] = _Saved(None, st, t["name"])
            self._cache = {key: found}
        return found

    def saved_items(self, save_folder, slot: int) -> list[pi.SavedItem]:
        out = []
        for item_id, saved in self._read(save_folder, slot).items():
            v, st = saved.v, saved.state
            if v is None:
                out.append(pi.SavedItem(item_id, f"{saved.name}'s totem (statue)", "Esteemed Elder statues", "statue",
                                        f"{saved.name}'s totem: statue {_crem(st.variant, 8) + 1}, kept by the Elder "
                                        "Totems patch"))
                continue
            stage = stage_label(v.age, v.dead, v.statue)
            if v.statue:
                location, kind = "Esteemed Elder statues", "statue"
                label = f"{v.name} (statue)"
            elif v.dead:
                location, kind = "Bodies awaiting burial", "body"
                label = f"{v.name} (body, {common.age_label(v.age)})"
            else:
                location, kind = "Villagers", "villager"
                label = f"{v.name} ({stage}, {common.age_label(v.age)})"
            look = common.LOOK_NAMES.get(v.look, "Auto")
            detail = (f"{v.name}: {'male' if v.male else 'female'}, {common.age_label(v.age)} ({v.age} age units), "
                      f"{stage}; head {v.head}, body {v.body}; mask: {common.MASK_NAMES[v.mask] if v.mask < 6 else v.mask}; "
                      f"head look: {look}" + (f"; statue {_crem(st.variant, 8) + 1}" if v.statue else ""))
            out.append(pi.SavedItem(item_id, label, location, kind, detail))
        order = {"Villagers": 0, "Bodies awaiting burial": 1, "Esteemed Elder statues": 2}
        return sorted(out, key=lambda i: order[i.location])

    def saved_fields(self) -> tuple:
        return pose_fields()

    def plan_saved(self, save_folder, slot: int, item_id: str, **pose) -> list[pi.Draw]:
        saved = self._read(save_folder, slot).get(item_id)
        if saved is None:
            raise pi.PictureError("That villager is no longer in the save.")
        st = saved.state
        if st.statue or st.health <= 0:
            plan_list = plan(self.sheets, replace(st, selected=pose.get("shadow") == "selected"))
            return plan_list if pose.get("shadow", "shadow") != "none" else _drop_shadows(plan_list)
        st, with_shadow = _apply_pose(st, pose)
        plan_list = plan(self.sheets, st)
        return plan_list if with_shadow else _drop_shadows(plan_list)

    def render_saved(self, save_folder, slot: int, item_id: str, **pose) -> pi.Image:
        return self._render(self.plan_saved(save_folder, slot, item_id, **pose))

    def _render(self, plan_list: list[pi.Draw]) -> pi.Image:
        if not plan_list:
            raise pi.PictureError("The game draws nothing for this.")
        return pi.render_plan(self.sheets, plan_list)

    # ---- Make your own
    def custom_choices(self, *_args, **_kwargs) -> list[pi.Subject]:
        stages = [pi.Option(("child", y * common.UNITS_PER_YEAR), f"Child, {y} years") for y in range(2, 14)]
        stages += [pi.Option(("adult", 30 * common.UNITS_PER_YEAR), "Adult (14 to 54 years)"),
                   pi.Option(("elder", 60 * common.UNITS_PER_YEAR), "Elder (55 years and over: grey head)"),
                   pi.Option(("dead", 600), "Body awaiting burial (skeleton)")]
        villager = pi.Subject("villager", "Villager", (
            pi.Field("sex", "Sex", (pi.Option(True, "Male"), pi.Option(False, "Female")), True),
            pi.Field("stage", "Life stage", tuple(stages), ("adult", 600)),
            pi.Field("head", "Head", tuple(pi.Option(k, f"Head {k}") for k in range(HEADS)), 0),
            pi.Field("body", "Body", tuple(pi.Option(k, f"Body {k}") for k in range(BODIES)), 0),
            pi.Field("mask", "Mask", MASK_OPTIONS, 0),
            pi.Field("look", "Head look", tuple(pi.Option(k, t, patcher=k != 0) for k, t in common.LOOK_NAMES.items()),
                     common.LOOK_AUTO),
            *pose_fields(),
            pi.Field("skeleton", "Skeleton frame", tuple(pi.Option(k, f"Frame {k + 1}") for k in range(4)), 0),
        ), note="The pictures are cut from your own copy of the game. Children are drawn smaller by age, as the "
                "game draws them; the old (grey) head is the game's own from 55 years. In the village the head look "
                "changes only a swimming villager's head (the rest follow the age): that is how the game draws it. "
                "Masks are the Origins patch's heathen masks.")
        statue = pi.Subject("statue", "Esteemed Elder statue", (
            pi.Field("kind", "Statue", tuple(pi.Option(k, f"Statue {k + 1}") for k in range(8)), 0),
            pi.Field("shadow", "Shadow", (pi.Option("shadow", "Shadow"), pi.Option("none", "No shadow")), "shadow"),
        ), note="An Esteemed Elder statue, as the village draws it (totems.png and its shadow).")
        return [villager, statue]

    def plan_custom(self, spec: dict) -> list[pi.Draw]:
        subject = spec.get("subject", "villager")
        if subject == "statue":
            # a statue record's health is 0 (the totem maker 0x44D467), so only its own shadow is drawn
            st = State(statue=True, health=0, variant=int(spec.get("kind", 0) or 0))
            plan_list = plan(self.sheets, st)
            return plan_list if spec.get("shadow", "shadow") != "none" else _drop_shadows(plan_list)
        if subject != "villager":
            raise pi.PictureError(f"The Lost Children has no {subject!r} to draw.")
        kind, age = spec.get("stage", ("adult", 600))
        st = State(male=bool(spec.get("sex", True)), age=int(age), head=int(spec.get("head", 0)),
                   body=int(spec.get("body", 0)), mask=int(spec.get("mask", 0) or 0),
                   look=int(spec.get("look", common.LOOK_AUTO) or 0))
        if kind == "dead":
            st = replace(st, health=0, variant=int(spec.get("skeleton", 0) or 0))
            plan_list = plan(self.sheets, st)
            return plan_list
        st, with_shadow = _apply_pose(st, spec)
        plan_list = plan(self.sheets, st)
        return plan_list if with_shadow else _drop_shadows(plan_list)

    def render_custom(self, spec: dict) -> pi.Image:
        return self._render(self.plan_custom(spec))


def load(source) -> Renderer:
    """`source`: an object with .read(name) (picture_source's Pictures), or a game folder."""
    if isinstance(source, (str, Path)):
        source = pi.FolderSource(Path(source))
    return Renderer(source)
