"""The Lost Children's own drawing code, run in Unicorn, for Picture Studio's Everything tab (src/vv_assets_vv2.py,
tests/test_assets_vv2.py, docs/picture-studio-assets-vv2.md).

Every picture is a fake surface the size of the real file (only the picture loader 0x40A730 is replaced); every
sprite is built by the game's own constructors (0x40A270 one sheet, 0x40A0D0 whole); the game's draw code then
runs and each blit it makes -- the plain 0x403F90, the scaled / faded 0x404000 and SDL's own SDL_UpperBlit
(0x467A2C) -- is recorded as (file, rect, x, y, scale, alpha byte), the key vv_picture_image.Draw.key() gives.

RECIPES: each sets up one of the game's draw routines on the state a picture shows and returns its blits.  Run as a
script (python scripts/emulate_vv2_assets.py) it rewrites the GENERATED block of src/vv_assets_vv2.py from them;
tests/test_assets_vv2.py runs every recipe again and requires each plan of the module to be the game's blits.
Needs the stock executable (research/stock-executables) and the game's pictures (research/game-images), for sizes.
"""
from __future__ import annotations

import pprint
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_picture_image as pi  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
IMAGES = ROOT / "research" / "game-images" / "Virtual Villagers - The Lost Children" / "Images"
MODULE = ROOT / "src" / "vv_assets_vv2.py"

NEW, DELETE = 0x467F83, 0x467F2E
PICTURE = 0x40A730
ONE_SHEET, WHOLE = 0x40A270, 0x40A0D0
PLAIN_BLIT, SCALED_BLIT, SDL_BLIT = 0x403F90, 0x404000, 0x467A2C
RAND, CLOCK, GRAPHICS, EXISTS = 0x4031A0, 0x403200, 0x408320, 0x40A690
CELL_CUT = 0x40A190


def _s(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def _f(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


def file_size(name: str) -> tuple[int, int]:
    """A picture's (width, height) from its header (PNG or JPEG), the file found as Windows finds it (any case)."""
    import vv_pictures_assets as pa
    path = IMAGES / name
    if not path.is_file():
        path = next((p for p in IMAGES.iterdir() if p.name.casefold() == name.casefold()), None)
        if path is None:
            raise FileNotFoundError(name)
    return pa.picture_size(path.read_bytes())


class Emu:
    """The stock executable in Unicorn with the picture loader and the blitters recorded."""

    def __init__(self, exe: bytes | None = None, sizes=file_size) -> None:
        from story_emulator import API_STUBS, Process
        from unicorn import UC_HOOK_CODE
        self.UC_HOOK_CODE = UC_HOOK_CODE
        self.p = p = Process(exe if exe is not None else STOCK.read_bytes())
        p.mu.mem_map(API_STUBS, 0x10000)
        p.api_names = {}
        slot = 0
        for entry in p._exe_pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if not imp.name:
                    continue
                stub = API_STUBS + slot * 16
                slot += 1
                p.mu.mem_write(stub, b"\xC3")
                p.api_names[stub] = imp.name.decode()
                p.mu.mem_write(imp.address, struct.pack("<I", stub))
                p.api_handlers[imp.name.decode()] = lambda q: (0, 0)
        self.sizes = sizes
        self.names: dict[int, str] = {}
        self.blits: list[tuple] = []
        self.alphas: list[float] = []
        self.timer = 0
        self.rand = lambda n: max(0, n - 1)
        self.gfx = self.renderer()
        self.holder = p.alloc(4)                 # the game keeps the graphics object behind one pointer
        p.put32(self.holder, self.gfx)
        p.stub(NEW, lambda q: (q.alloc(max(4, q.arg(0))), 0))
        p.stub(DELETE, lambda q: (0, 0))
        p.stub(PICTURE, self._picture)
        p.stub(RAND, lambda q: (self.rand(_s(q.arg(0))) & 0xFFFFFFFF, 0))
        p.stub(CLOCK, lambda q: (self.timer & 0xFFFFFFFF, 0))
        p.stub(GRAPHICS, lambda q: (self.holder, 0))
        p.stub(EXISTS, lambda q: (1, 0))
        p.stub(PLAIN_BLIT, self._plain)
        p.stub(SCALED_BLIT, self._scaled)
        p.stub(SDL_BLIT, self._sdl)

    # ---- pictures and sprites
    def _picture(self, q):
        name = q.cstring(q.arg(0))
        this = q.reg("ecx")
        w, h = self.sizes(name)
        surface = q.alloc(0x40)
        q.put32(surface + 8, w)
        q.put32(surface + 12, h)
        self.names[surface] = name
        q.put32(this, surface)
        q.write(this + 4, b"\x01")
        return this, 4

    def text(self, value: str) -> int:
        at = self.p.alloc(len(value) + 1)
        self.p.write(at, value.encode() + b"\0")
        return at

    def sprite(self, name: str, cols: int = 1, rows: int = 1) -> int:
        """A sprite built by the game's one-sheet constructor 0x40A270."""
        obj = self.p.alloc(0x34)
        self.p.call(ONE_SHEET, [self.text(name), cols, rows], ecx=obj, limit=2_000_000)
        return obj

    def whole(self, name: str) -> int:
        """A sprite built by the game's whole-picture constructor 0x40A0D0."""
        obj = self.p.alloc(0x34)
        self.p.call(WHOLE, [self.text(name)], ecx=obj, limit=2_000_000)
        return obj

    def cell(self, sprite: int, col: int, row: int) -> tuple[int, int, int, int]:
        """The game's own cell cut 0x40A190."""
        rect = self.p.alloc(16)
        self.p.call(CELL_CUT, [col, row, rect], ecx=sprite, limit=100_000)
        return tuple(_s(v) for v in struct.unpack("<iiii", self.p.read(rect, 16)))

    def renderer(self) -> int:
        """A graphics object whose clip rectangle (+0x60 .. +0x6C) holds everything."""
        g = self.p.alloc(0x200)
        self.p.write(g + 0x60, struct.pack("<iiii", -100000, -100000, 100000, 100000))
        self.p.put32(g + 8, 800)
        self.p.put32(g + 0xC, 600)
        return g

    # ---- the blits: (file as the game named it, rect, x, y, scale, alpha byte); the alpha float beside them
    def _name(self, surface: int) -> str:
        return self.names.get(surface, f"?{surface:X}")

    def _plain(self, q):
        surface, x, y, l, t, r, b = (q.arg(i) for i in range(7))
        self.blits.append((self._name(surface), tuple(_s(v) for v in (l, t, r, b)), _s(x), _s(y), 1.0, 255))
        self.alphas.append(1.0)
        return 0, 0x1C

    def _scaled(self, q):
        surface, x, y, l, t, r, b, alpha, scale, _flag = (q.arg(i) for i in range(10))
        self.blits.append((self._name(surface), tuple(_s(v) for v in (l, t, r, b)), _s(x), _s(y), round(_f(scale), 6),
                           pi.surface_alpha(_f(alpha))))
        self.alphas.append(_f(alpha))
        return 0, 0x28

    def _sdl(self, q):
        """SDL_UpperBlit(src, srcrect {x, y, w, h}, dst, dstrect {x, y, w, h}), cdecl."""
        src, srect, _dst, drect = (q.arg(i) for i in range(4))
        sx, sy, sw, sh = struct.unpack("<iiii", q.read(srect, 16)) if srect else (0, 0, 0, 0)
        dx, dy = struct.unpack("<ii", q.read(drect, 8)) if drect else (0, 0)
        self.blits.append((self._name(src), (sx, sy, sx + sw, sy + sh), dx, dy, 1.0, 255))
        self.alphas.append(1.0)
        return 0, 0

    def run(self, address: int, args=(), ecx: int | None = None, limit: int = 5_000_000,
            until: int | None = None) -> list[tuple]:
        """The blits `address` makes (to its return, or up to `until`)."""
        from story_emulator import RETURN
        from unicorn.x86_const import UC_X86_REG_FPCW
        self.blits, self.alphas = [], []
        self.p.mu.reg_write(UC_X86_REG_FPCW, 0x027F)
        self.p.call(address, list(args), ecx=ecx, limit=limit, until=RETURN if until is None else until)
        return self.blits

    def watch(self, address: int, fn) -> None:
        """fn(process) at `address`, the routine itself left to run."""
        self.p.mu.hook_add(self.UC_HOOK_CODE, lambda mu, a, s, u: fn(self.p), begin=address, end=address)


def keys(blits) -> list[tuple]:
    """The blits as Draw.key() gives them (file case folded)."""
    return [(b[0].casefold(), tuple(b[1]), b[2], b[3], round(b[4], 6), b[5]) for b in blits]


# ------------------------------------------------------------------ what the module keeps of a blit

def entry(blit, alpha: float, grids: dict, sizes) -> tuple:
    """(file, col, row, x, y, scale, alpha) of a blit: the cell of the sprite grid it was cut from."""
    name, rect, x, y, scale, _byte = blit
    cols, rows = grids.get(name.casefold(), (1, 1))
    w, h = sizes(name)
    cw, ch = w // cols, h // rows
    col, row = rect[0] // cw, rect[1] // ch
    if tuple(rect) != (cw * col, ch * row, cw * col + cw, ch * row + ch):
        raise ValueError(f"{name}: {rect} is not a cell of {cols} x {rows}")
    return (name, col, row, x, y, scale, round(alpha, 7))


# ------------------------------------------------------------------ the recipes
# Each recipe(emu) returns [(key, category, group, label, note, proof, [(frame label, blits, alphas), ...]), ...].

SCENE_FIELDS = (
    (0x15E0, "scaffolding.png", 1, 1), (0x15E8, "carrying.png", 13, 2), (0x15E4, "stoolfood.png", 1, 1),
    (0x15EC, "graves.png", 4, 1), (0x15F0, "graveflowers.png", 3, 1), (0x15F8, "leafCover.png", 1, 1),
    (0x1674, "firestrip.png", 4, 2), (0x1638, "shore01.png", 1, 1), (0x163C, "shore02.png", 1, 1),
    (0x1640, "bigwave01.png", 1, 1), (0x1644, "medwaves01.png", 1, 1), (0x1648, "smallwaves01.png", 1, 1),
    (0x162C, "collectables_images.png", 6, 9), (0x1630, "bird_shadow.png", 1, 1), (0x15F4, "woodpile.png", 1, 1),
    (0x15FC, "small_huts.png", 2, 2), (0x1600, "hospital.png", 1, 1), (0x1604, "foodStates.png", 3, 1),
    (0x1608, "veggies.png", 3, 2), (0x160C, "dam.jpg", 1, 1), (0x1610, "wetFarm.jpg", 1, 1),
    (0x1614, "flood.jpg", 1, 1), (0x1618, "mosaicCovers1.png", 3, 3), (0x161C, "mosaicCovers2.png", 3, 3),
    (0x1620, "briars.png", 2, 1), (0x1624, "sunkenGong.jpg", 1, 1), (0x1628, "scarecrow.png", 2, 1),
    (0x164C, "vines1.png", 1, 1), (0x1650, "vines2.png", 1, 1), (0x1654, "vines3.png", 1, 1),
    (0x1658, "vines4.png", 1, 1), (0x165C, "gongsmall.png", 2, 2), (0x1660, "tinyflowers.png", 2, 2),
    (0x1634, "researchstates.png", 2, 1), (0x1670, "crate.png", 2, 1), (0x1664, "leaningspears.png", 1, 1),
    (0x1668, "speartips.png", 1, 1), (0x166C, "coveredpot.png", 1, 1), (0x1678, "clothinghut.png", 1, 1),
)
SCENE_MANAGER, WORLD_SIZE = 0x1700, 0x31000
BUILD_LIST, DRAW_LIST = 0x41C1D0, 0x41B630
ADD_WHOLE, ADD_FRAME = 0x41B580, 0x41B5D0


class Scene:
    """The village's object list: 0x41C1D0 fills it from the world's state, 0x41B630 draws it (each entry a whole
    sprite through 0x408820 or a frame through 0x4089B0, at (x - camera x, y - camera y)).  The sprites are built
    with the game's constructor and the arguments its scene constructor 0x41DAF0 gives (SCENE_FIELDS)."""

    def __init__(self, emu: Emu) -> None:
        self.e = e = emu
        p = e.p
        self.m = p.alloc(SCENE_MANAGER)
        self.world = p.alloc(WORLD_SIZE)
        self.drag = p.alloc(0x40)
        p.put32(self.m + 0x1680, self.world)
        p.put32(self.m + 0x167C, e.holder)
        p.put32(self.m + 0x1684, self.drag)
        for off, name, cols, rows in SCENE_FIELDS:
            p.put32(self.m + off, e.sprite(name, cols, rows))
        self.adds: list[int] = []
        e.watch(ADD_WHOLE, lambda q: self.adds.append(q.u32(q.reg("esp"))))
        e.watch(ADD_FRAME, lambda q: self.adds.append(q.u32(q.reg("esp"))))

    def draw(self, state: dict, sites) -> tuple[list, list]:
        """(blits, alphas) of the entries the builder adds from call sites inside `sites` ((start, end) ranges),
        for a world state {offset: int or bytes}.  Each entry makes exactly one blit (the clip holds everything),
        so entry k is blit k."""
        p = self.e.p
        p.write(self.world, bytes(WORLD_SIZE))
        for off, value in state.items():
            p.write(self.world + off, value if isinstance(value, bytes) else struct.pack("<i", value))
        self.adds = []
        self.e.run(BUILD_LIST, ecx=self.m)
        blits = self.e.run(DRAW_LIST, ecx=self.m)
        alphas = self.e.alphas
        if len(blits) != len(self.adds):
            raise AssertionError("an entry was not drawn")
        pick = [k for k, ret in enumerate(self.adds) if any(a <= ret - 5 < b for a, b in sites)]
        return [blits[k] for k in pick], [alphas[k] for k in pick]


B, P, PL, V = "Buildings and objects", "Puzzles", "Plants and food", "Villagers"

# (key, category, group, label, sites, states).  states: ("sweep", world offset, first, last, unit, other fields)
# for every value in turn (each run of values that draws the same is one picture), or [(label, {offset: value})].
SCENE_DEFS = (
    ("hut1", B, "Huts", "The Hut (first new hut)", ((0x41C1DE, 0x41C292),),
     ("sweep", 0x2E814, 0, 450, "build points", {}), [("finished", {0x2E818: 1})]),
    ("hut2", B, "Huts", "The Hut (second new hut)", ((0x41C292, 0x41C347),),
     ("sweep", 0x2E81C, 0, 700, "build points", {}), [("finished", {0x2E820: 1})]),
    ("hut3", B, "Huts", "The Hut (third new hut)", ((0x41C347, 0x41C3FC),),
     ("sweep", 0x2E824, 0, 900, "build points", {}), [("finished", {0x2E828: 1})]),
    ("lovely_hut", P, "Puzzles in the village", "The Lovely Hut (the broken starting hut)", ((0x41C6A1, 0x41C719),),
     ("sweep", 0x2E75C, 0, 400, "build points", {}), []),
    ("hospital", B, "Buildings", "The Hospital", ((0x41C3FC, 0x41C4DC),),
     ("sweep", 0x2E77C, 0, 1200, "build points", {}), [("finished", {0x2E780: 1})]),
    ("sewing_hut", B, "Buildings", "The Sewing Hut", ((0x41C520, 0x41C5B8),),
     ("sweep", 0x2E78C, 0, 400, "build points", {}), [("finished", {0x2E790: 1})]),
    ("research_table", B, "Buildings", "The research table (Science level)", ((0x41C4DC, 0x41C520),),
     None, [("Science level 2", {0x2EA7C: 2}), ("Science level 3", {0x2EA7C: 3})]),
    ("firepit", B, "Objects", "The fire pit's dry grass and firewood", ((0x41C5EA, 0x41C63A),),
     None, [("dry grass", {0x30458: b"\x01"}), ("firewood", {0x30459: b"\x01"}),
            ("dry grass and firewood", {0x30458: b"\x01\x01"})]),
    ("exploration_find", B, "Objects", "The Exploration find (carrying.png frames 19 and 20)", ((0x41C63A, 0x41C6A1),),
     None, [("placed (flag +0x2E8A8)", {0x2E8A8: b"\x01"}),
            ("with +0x3044C set", {0x2E8A8: b"\x01", 0x3044C: 1}),
            ("with +0x30448 set", {0x2E8A8: b"\x01", 0x30448: b"\x01"})]),
    ("exploration_pot", B, "Objects", "The covered pot and the spear tips (Exploration level 2)",
     ((0x41C7CE, 0x41C81D),), None,
     [("Exploration level 2", {0x2EA94: 2}), ("Exploration level 2, the find placed", {0x2EA94: 2, 0x2E8A8: b"\x01"})]),
    ("cutting_tool", P, "Puzzles in the village", "The Cutting Tool (leaning spears)", ((0x41C719, 0x41C741),),
     None, [("solved", {0x2E7A0: b"\x01"})]),
    ("food_store", PL, "Food", "The food store", ((0x41C81D, 0x41C87F),),
     ("sweep", 0x2EAA4, 0, 4100, "food", {}), []),
    ("crops", PL, "Crops", "The crops on the farm (the Dam solved)", ((0x41D1C1, 0x41D403),),
     ("sweep", 0x2EAD8, 0, 800, "crops", {0x2E798: b"\x01"}), []),
    ("coconuts", PL, "Coconut trees", "The coconut trees", ((0x41D4B3, 0x41D7B8),),
     ("sweep", 0x2EACC, 0, 1500, "coconuts", {}), []),
    ("dam", P, "Puzzles in the village", "The Dam and the farm", ((0x41CE20, 0x41CE63), (0x41D403, 0x41D46B)),
     ("sweep", 0x2E794, 0, 425, "build points", {}), [("solved (the farm)", {0x2E798: b"\x01"})]),
    ("vine_wall", P, "Puzzles in the village", "The Vine Wall", ((0x41CD75, 0x41CE20),),
     ("sweep", 0x2E7AC, 0, 1000, "build points", {}), []),
    ("mosaic", P, "Puzzles in the village", "The Ancient Mosaic (in the drained flats: drawn once the Dam is solved)",
     ((0x41CE63, 0x41D1C1),),
     ("sweep", 0x2E7B4, 0, 5000, "points", {0x2E798: b"\x01"}), [("solved", {0x2E798: b"\x01", 0x2E7B8: b"\x01"})]),
    ("inlaid_piece", P, "Puzzles in the village", "The Inlaid Gong Piece (on the mosaic)", ((0x41C7A5, 0x41C7CE),),
     None, [("progress 1 of 2", {0x2E7D4: 1})]),
    ("sunken_piece", P, "Puzzles in the village", "The Sunken Gong Piece", ((0x41C5B8, 0x41C5EA),),
     None, [("not yet found", {})]),
    ("boxed_piece", P, "Puzzles in the village", "The Boxed Gong Piece (the crate)", ((0x41C741, 0x41C7A5),),
     None, [("the sealed crate", {}), ("the crate open, the piece inside", {0x2E7D0: b"\x01"}),
            ("the crate open, the piece taken", {0x2E7D0: b"\x01", 0x2E7BC: 1})]),
    ("overgrown_piece", P, "Puzzles in the village", "The Overgrown Gong Piece (the briars)", ((0x41C92A, 0x41CBB3),),
     ("sweep", 0x2E7DC, 0, 3000, "points", {}), []),
    ("gong", P, "Puzzles in the village", "The Gong of Wonder and the flowers (the briars cleared)",
     ((0x41CB97, 0x41CD75),), None,
     [("the base", {0x2E7E0: b"\x01"}),
      ("with the Sunken Gong Piece", {0x2E7E0: b"\x01", 0x2E7C8: b"\x01"}),
      ("with the Inlaid Gong Piece", {0x2E7E0: b"\x01", 0x2E7D8: b"\x01"}),
      ("with the Boxed Gong Piece", {0x2E7E0: b"\x01", 0x2E7C0: b"\x01"}),
      ("whole: every piece", {0x2E7E0: b"\x01", 0x2E7C0: b"\x01", 0x2E7C8: b"\x01", 0x2E7D8: b"\x01"})]),
    ("scarecrow", P, "Puzzles in the village", "The Scarecrow", ((0x41D46B, 0x41D4B3),),
     None, [("being made (+0x2E76C = 1)", {0x2E76C: 1}), ("solved", {0x2E770: b"\x01"})]),
    ("collections_shown", B, "Objects", "Complete collections shown in the village", ((0x41C87F, 0x41C92A),),
     None, [("Butterflies complete", {0x2E720: b"\x01" * 12}),
            ("Shells complete", {0x2E72C: b"\x01" * 12}),
            ("Beetles complete", {0x2E738: b"\x01" * 12}),
            ("Pebbles complete", {0x2E744: b"\x01" * 12}),
            ("all four", {0x2E720: b"\x01" * 48})]),
    ("grave_flowers", V, "Graves", "The grave flowers (+0x2E858)", ((0x41D7FD, 0x41D875),),
     None, [("shown", {0x2E858: b"\x01"})]),
    ("graveyard", V, "Graves", "The graveyard", ((0x41D875, 0x41DAA5),),
     None, [("one grave (slot 1)", {0x2EB80: 1}),
            ("the graveyard full (50 graves)", {0x2EB80 + 0x7C * k: 1 for k in range(50)}),
            ("50 graves, other stones", {0x2EB80 + 0x7C * k: 2 for k in range(50)})]),
)


def _sweep_label(a: int, b: int, last: int, unit: str) -> str:
    if a == b:
        return f"{a:,} {unit[:-1] if a == 1 and unit.endswith('s') else unit}"
    if b == last:
        return f"{a:,} or more {unit}"
    return f"{a:,} to {b:,} {unit}"


def scene_assets(emu: Emu, defs=SCENE_DEFS):
    sc = Scene(emu)
    out = []
    for key, category, group, label, sites, sweep, extras in defs:
        frames = []
        if sweep is not None:
            _kind, field, first, last, unit, other = sweep
            run = None
            for v in range(first, last + 1):
                st = dict(other)
                st[field] = v
                blits, alphas = sc.draw(st, sites)
                k = keys(blits)
                if run is not None and run[3] == k:
                    run[1] = v
                    continue
                if run is not None and run[3]:
                    frames.append(run)
                run = [v, v, (blits, alphas, st), k]
            if run is not None and run[3]:
                frames.append(run)
            frames = [(_sweep_label(a, b, last, unit), data[0], data[1], data[2], (field, a, b, first, last))
                      for a, b, data, _k in frames]
        for flabel, st in extras:
            blits, alphas = sc.draw(st, sites)
            if blits:
                frames.append((flabel, blits, alphas, st, None))
        out.append((key, category, group, label, "", "emulated 0x41C1D0 + 0x41B630", frames))
    return out


# ---- the island: 16 tiles MapX<x>Y<y>.jpg, loaded by 0x411FF0 and drawn by 0x411F80

def island_assets(emu: Emu):
    p = emu.p
    m = p.alloc(0x200)
    emu.run(0x411FF0, ecx=m)
    frames = [("the whole island (camera at 0, 0)", emu.run(0x411F80, [0, 0], ecx=m), list(emu.alphas), None)]
    return [("island", "Scene", "The island", "The island (16 map tiles)",
             "the game draws the tiles the camera sees; here the camera is at (0, 0) and the clip holds the whole "
             "island", "emulated 0x411FF0 + 0x411F80", frames)]


# ---- the collections screen 0x416180

COLLECTION_FIELDS = ((0xF8, "butterflies_big.png", 4, 3), (0xFC, "beetles_big.png", 4, 3),
                     (0x100, "pebbles_big.png", 4, 3), (0x104, "shells_big.png", 4, 3),
                     (0x108, "wheel_pieces.png", 2, 2))
# the found bytes 0x2E720 + piece: 12 a collection, Butterflies, Shells, Beetles, Pebbles (vv_game_mechanics_vv2)
COLLECTIONS = ("Butterflies", "Shells", "Beetles", "Pebbles")
RARITY = ("common", "common", "common", "common", "uncommon", "uncommon", "uncommon", "uncommon",
          "rare", "rare", "rare", "rare")
GONG_PIECES = (("The Sunken Gong Piece", 0x2E7C8), ("The Inlaid Gong Piece", 0x2E7D8),
               ("The Boxed Gong Piece", 0x2E7C0), ("The Overgrown Gong Piece", 0x2E7E0))


def collections_assets(emu: Emu):
    p = emu.p
    o = p.alloc(0x200)
    world = p.alloc(WORLD_SIZE)
    p.put32(o + 8, emu.holder)
    p.put32(o + 0xC, world)
    p.put32(o + 0xF4, emu.whole("collections_bg.jpg"))
    for off, name, cols, rows in COLLECTION_FIELDS:
        p.put32(o + off, emu.sprite(name, cols, rows))

    def draw(state):
        p.write(world, bytes(WORLD_SIZE))
        for off, value in state.items():
            p.write(world + off, value)
        blits = emu.run(0x416180, ecx=o)
        return blits[1:], emu.alphas[1:]                # the background is the screen's own asset
    out = []
    for c, name in enumerate(COLLECTIONS):
        frames = []
        for k in range(12):
            blits, alphas = draw({0x2E720 + 12 * c + k: b"\x01"})
            frames.append((f"piece {k + 1} ({RARITY[k]})", blits, alphas, None))
        blits, alphas = draw({0x2E720 + 12 * c: b"\x01" * 12})
        frames.append(("complete", blits, alphas, None))
        out.append((f"collection:{name}", "Collectibles", "The collections screen", f"{name} collection",
                    "each piece where the collections screen puts it once found", "emulated 0x416180", frames))
    frames = []
    for name, off in GONG_PIECES:
        blits, alphas = draw({off: b"\x01"})
        frames.append((name, blits, alphas, None))
    blits, alphas = draw({off: b"\x01" for _n, off in GONG_PIECES})
    frames.append(("every piece", blits, alphas, None))
    out.append(("collection:gong", "Collectibles", "The collections screen", "The Gong of Wonder's pieces",
                "each piece where the collections screen puts it once found", "emulated 0x416180", frames))
    every = {0x2E720: b"\x01" * 48}
    every.update({off: b"\x01" for _n, off in GONG_PIECES})
    p.write(world, bytes(WORLD_SIZE))
    empty = emu.run(0x416180, ecx=o)
    e_alpha = list(emu.alphas)
    p.write(world, bytes(WORLD_SIZE))
    for off, value in every.items():
        p.write(world + off, value)
    full = emu.run(0x416180, ecx=o)
    out.append(("screen:collections", "Screens", "", "The collections screen",
                "its counts are SDL text, not drawn here", "emulated 0x416180",
                [("nothing found", empty, e_alpha, None), ("everything found", full, list(emu.alphas), None)]))
    return out


# ---- the Tech screen 0x441830: tech_bg.jpg, then each technology's picture, frame 0 always, 1 from level 2, 2 at 3

TECH_FIELDS = ((0x44, "culture.jpg"), (0x48, "farming.jpg"), (0x4C, "science.jpg"), (0x50, "medicine.jpg"),
               (0x54, "building.jpg"), (0x58, "exploration.jpg"))
TECHS = (("Farming", 0x2EA9C, "farming.jpg"), ("Medicine", 0x2EA8C, "medicine.jpg"),
         ("Exploration", 0x2EA94, "exploration.jpg"), ("Engineering", 0x2EA84, "building.jpg"),
         ("Science", 0x2EA7C, "science.jpg"), ("Culture", 0x2EA74, "culture.jpg"))


def tech_assets(emu: Emu):
    p = emu.p
    o = p.alloc(0x200)
    world = p.alloc(WORLD_SIZE)
    p.put32(o + 8, emu.holder)
    p.put32(o + 0xC, world)
    p.put32(o + 0x40, emu.whole("tech_bg.jpg"))
    for off, name in TECH_FIELDS:
        p.put32(o + off, emu.sprite(name, 3, 1))
    p.put32(o + 0x1C, 4)                                   # the screen settled (no fade in progress)
    p.put32(o + 0x20, struct.unpack("<I", struct.pack("<f", 1.0))[0])

    def draw(levels):
        p.write(world, bytes(WORLD_SIZE))
        for _n, off, _f in TECHS:
            p.put32(world + off, levels.get(off, 1))
        # up to 0x441D2B, where the screen's buttons and text are drawn (each through its own widget)
        return emu.run(0x441830, ecx=o, until=0x441D2B), list(emu.alphas)
    out = []
    for name, off, file in TECHS:
        frames = []
        for level in (1, 2, 3):
            blits, alphas = draw({off: level})
            pick = [k for k, b in enumerate(blits) if b[0].casefold() == file]
            frames.append((f"level {level}", [blits[k] for k in pick], [alphas[k] for k in pick], None))
        out.append((f"tech:{name}", "UI: Tech screen", "Technologies", f"{name} (its picture at each level)",
                    "frame 0 (uncoloured) is always drawn, frame 1 over it from level 2, frame 2 over both at level 3",
                    "emulated 0x441830", frames))
    frames = []
    for level in (1, 2, 3):
        blits, alphas = draw({off: level for _n, off, _f in TECHS})
        frames.append((f"every technology at level {level}", blits, alphas, None))
    out.append(("screen:tech", "UI: Tech screen", "The screen", "The Tech screen",
                "its buttons, text and tooltips are drawn by other code (the buttons under UI: Panels and buttons)",
                "emulated 0x441830", frames))
    return out


# ---- the Villager Details bars 0x43C470 (value 0..100, which 3..8)

BARS = ((3, "first skill bar"), (4, "second skill bar"), (5, "third skill bar"), (6, "fourth skill bar"),
        (7, "fifth skill bar"), (8, "health bar"))
BAR_VALUES = (0, 6, 7, 25, 50, 75, 99, 100)


def bar_assets(emu: Emu):
    # the bars' object as its constructor 0x43C2B0 leaves it: the graphics holder, then the four whole pictures
    p = emu.p
    o = p.alloc(0x40)
    p.put32(o, emu.holder)
    for off, name in ((8, "BambooMeterFrame1.png"), (0xC, "StatusBarSliceB.png"), (0x10, "StatusBarSliceR.png"),
                      (0x14, "healthBarbulb.png")):
        p.put32(o + off, emu.whole(name))
    out = []
    for which, name in BARS:
        frames = []
        for value in BAR_VALUES:
            blits = emu.run(0x43C470, [which, value], ecx=o)        # thiscall (which, value)
            if blits:
                frames.append((f"{value} of 100", blits, list(emu.alphas), None))
        out.append((f"bar:{which}", "UI: Meters", "Villager Details bars", f"The Villager Details {name}",
                    "one 16-pixel slice for each full 6.25 of 100 (value x 256 / 100 / 16); its place on the "
                    "Villager Details screen", "emulated 0x43C2B0 + 0x43C470", frames))
    return out


# ---- the bamboo meter 0x4451B0 (x, y, value, mode); mode 3 is the LoadColor.png bar

def bamboo_assets(emu: Emu):
    # the meter's object as its constructor 0x445080 leaves it: the graphics holder, the frame, the fill slice
    p = emu.p
    o = p.alloc(0x40)
    p.put32(o, emu.holder)
    p.put32(o + 8, emu.whole("BambooMeterFrame1.png"))
    p.put32(o + 0xC, emu.whole("LoadColor.png"))
    frames = []
    for value in (1, 25, 50, 75, 100):
        blits = emu.run(0x4451B0, [3, 0, 0, value], ecx=o)        # (mode, x, y, value)
        frames.append((f"{value} of 100", blits, list(emu.alphas), None))
    return [("meter:bamboo", "UI: Meters", "Bamboo meter", "The bamboo meter (LoadColor.png fill)",
             "modes 0 to 2 fill the bar with a colour (a rectangle fill, not a picture) and are left out; the "
             "frame is drawn again after every slice, as the game does", "emulated 0x445080 + 0x4451B0", frames)]


# ---- the dialog panels: 0x40D050 (sprite, w, h) and the nine-tile draw 0x40CEB0 (x, y, alpha)

PANEL_SIZES = ((200, 120), (400, 300), (560, 420))


def panel_assets(emu: Emu):
    out = []
    for name in ("GreenDlgTileGrid.png", "OrangeDlgTileGrid.png"):
        sprite = emu.sprite(name, 9, 1)
        frames = []
        for w, h in PANEL_SIZES:
            o = emu.p.alloc(0x40)
            emu.run(0x40D050, [sprite, w, h], ecx=o)
            blits = emu.run(0x40CEB0, [0, 0, struct.unpack("<I", struct.pack("<f", 1.0))[0]], ecx=o)
            frames.append((f"{w} x {h}", blits, list(emu.alphas), None))
        colour = name[:-len("DlgTileGrid.png")]
        out.append((f"panel:{colour}", "UI: Panels and buttons", "Dialog panels", f"{colour} dialog panel",
                    "built from the nine tiles at a sample size", "emulated 0x40D050 + 0x40CEB0", frames))
    return out


# ---- the buttons: a 3 x 1 sprite (0x401732); the draw dispatch 0x4010B0 picks frame = state +0x30 (0 the mouse
# away, 1 over it, 2 over it and pressed: the mouse handler 0x401780), the draw 0x401360 blits it at the button

BUTTON_FILES = ("popup_button1.png", "main_wide_button2.png", "ultra_wide_button.png", "leftarrow.png",
                "rightarrow.png", "empty1.png", "main_detail_button.png", "MS_Button_01.png", "MS_Button_02.png",
                "MS_Button_03.png", "MS_Button_04.png", "info_button.png", "research_button.png")
BUTTON_STATES = ("normal", "mouse over", "pressed")


def button_assets(emu: Emu):
    p = emu.p
    out = []
    for name in BUTTON_FILES:
        sprite = emu.sprite(name, 3, 1)
        w, h = emu.sizes(name)
        button = p.alloc(0x80)
        p.write(button + 0x10, struct.pack("<iiii", 0, 0, w // 3, h))
        p.write(button + 0x28, b"\x01\x01")
        p.put32(button + 0x3C, sprite)
        widget = p.alloc(0x20)
        p.put32(widget, 0x474280)
        p.write(widget + 8, b"\x01")
        p.put32(widget + 0x10, button)
        frames = []
        for state, label in enumerate(BUTTON_STATES):
            p.put32(button + 0x30, state)
            frames.append((label, emu.run(0x4010B0, ecx=widget), list(emu.alphas), None))
        out.append((f"button:{name}", "UI: Panels and buttons", "Buttons", name[:-4].replace("_", " "),
                    "drawn at the button's own place; a disabled button goes through the game's tint loop 0x408E60 "
                    "(pixels blended toward a colour) and is not drawn here", "emulated 0x4010B0 + 0x401360",
                    frames))
    return out


# ---- the birds 0x4135C0: nine birds (+0x2C, 0x30 each); bird.png 12 x 1 and its shadow, scaled through 0x409610

def bird_assets(emu: Emu):
    p = emu.p
    o = p.alloc(0x200)
    world = p.alloc(0x40)
    p.put32(o + 0x1BC, emu.holder)
    p.put32(o + 0x1C0, world)
    p.put32(o + 0x1CC, emu.sprite("bird.png", 12, 1))
    p.put32(o + 0x1D0, emu.sprite("bird_shadow.png", 1, 1))
    frames = []
    for state, what in ((1, "flying"), (3, "landed")):
        for facing in (0, 3):
            for frame in (0, 1):
                p.write(o, bytes(0x30 * 9))
                b = o + 0x2C
                p.put32(b, state)
                p.put32(b - 0x2C, 100)
                p.put32(b - 0x28, 100)
                p.put32(b - 0x10, facing)
                p.put32(b - 8, frame)
                p.put32(b - 4, 100)
                blits = emu.run(0x4135C0, [1 if state != 3 else 0], ecx=o)
                frames.append((f"{what}, {'facing 3' if facing == 3 else 'facing 0'}, frame {frame}", blits,
                               list(emu.alphas), None))
    return [("bird", "Creatures", "Birds", "A bird and its shadow",
             "a bird at (100, 100), unscaled; the birds' flight and the frame order are the game's update code, "
             "not traced (the shadow and the frame offsets are the draw's)", "emulated 0x4135C0", frames)]


# ---- the fonts: 0x402110 (name, glyph table, flag) makes the glyph rectangles; 0x4026C0 gives one

FONTS = (("ldwBurweed27", 0x4952C0, 0), ("ldwarialbold", 0x4958A8, 1))


def font_glyphs(emu: Emu):
    """{font file: [(character code, (left, top, right, bottom)), ...]} as the game's font object holds them."""
    p = emu.p
    out = {}
    for name, table, flag in FONTS:
        o = p.alloc(0x20)
        emu.run(0x402110, [emu.text(name), table, flag], ecx=o)
        glyphs = p.u32(o + 4)
        codes = []
        for k in range(0x100):
            code = struct.unpack("<i", p.read(table + 0x14 * k, 4))[0]
            if code == 0:
                break
            codes.append(code & 0xFF if code < 0 else code)
        rect = p.alloc(16)
        rows = []
        for code in codes:
            emu.run(0x4026C0, [code, rect], ecx=glyphs)
            rows.append((code, tuple(_s(v) for v in struct.unpack("<iiii", p.read(rect, 16)))))
        out[name + ".png"] = rows
    return out


RECIPES = (scene_assets, island_assets, collections_assets, tech_assets, bar_assets, bamboo_assets, panel_assets,
           button_assets, bird_assets)


# ------------------------------------------------------------------ writing the module's GENERATED block

BEGIN, END = "# ---- BEGIN GENERATED (scripts/emulate_vv2_assets.py) ----", "# ---- END GENERATED ----"


def generate(emu: Emu | None = None) -> str:
    import vv_assets_vv2 as m
    emu = emu or Emu()
    grids = m.grids()
    assets = []
    for recipe in RECIPES:
        for key, category, group, label, note, proof, frames in recipe(emu):
            rows = []
            for frame in frames:
                flabel, blits, alphas = frame[:3]
                if not blits:
                    continue                      # the routine draws nothing in this state
                state = frame[3] if len(frame) > 3 else None
                span = frame[4] if len(frame) > 4 else None
                plan = tuple(entry(b, a, grids, emu.sizes) for b, a in zip(blits, alphas))
                rows.append((flabel, plan, state, span))
            assets.append((key, category, group, label, note, proof, tuple(rows)))
    glyphs = font_glyphs(emu)
    body = ("GENERATED = " + pprint.pformat(tuple(assets), width=118, compact=True) + "\n\n"
            "GLYPHS = " + pprint.pformat(glyphs, width=118, compact=True) + "\n")
    return body


def write_module() -> None:
    text = MODULE.read_text(encoding="utf-8")
    start, stop = text.index(BEGIN) + len(BEGIN), text.index(END)
    MODULE.write_text(text[:start] + "\n" + generate() + text[stop:], encoding="utf-8")


if __name__ == "__main__":
    write_module()
    print("wrote", MODULE)
