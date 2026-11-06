"""Fix Vanilla Bugs: the Overview Map's water lines up with its riverbeds (The Secret City, The Tree of Life).

The owner (The Tree of Life, with a screenshot): the waterfall and river water on the Overview Map
"floats above the riverbed"; and "the map water fix should keep in mind the water animations too".

The Overview Map (The Tree of Life 0x4453C0, The Secret City 0x46C2xx) draws its picture
(overview_bg.jpg, the island shrunk to the 424 x 424 box at (188, 61)) and then every picture of the
village on top of it at the scale 424/2048 = 0.20703125: the overlay list (0x41C5B0 / 0x428EF0) and
the draw queue (origin routine 0x44C3E0 / 0x42E250, then each queued sprite, static 0x44C5E0 / 0x42E4B0
and animated 0x44C640 / 0x42E510).  A sprite's position is world * 0.20703125 + the origin, but its
size goes to the blitter as a whole percent, which both routines cut with _ftol: 20.703 -> 20.  So
every river section, waterfall and every frame of their animations is drawn 20% of its size from its
top left corner while the riverbed under it is 20.70%: the water ends short of its bed's bottom and
right edges (by up to 7 map pixels on the largest river picture) -- it "floats above".

The fix rounds the percent (push eax; fistp dword [esp]; pop eax, the FPU's round-to-nearest, which
pops the value as _ftol does): 21, 0.30 points from 20.70 instead of 0.70.  The village view's scale
1.0 still gives 100.  New Believers' map scale is 0.2125 (21.25%): cut or rounded it is 21, so it has
no such bug and is not changed.  A New Home and The Lost Children draw no scaled water on their maps.

Everything here RUNS the stock and the patcher's rendered bytes in unicorn.
"""
from __future__ import annotations

import functools
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import load_builds, load_fun_patches, render_patched_bytes  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP
except ImportError:  # pragma: no cover
    pefile = None

STOCK_DIR = ROOT / "research" / "stock-executables"
NAMES = {"vv3": "The Secret City", "vv4": "The Tree of Life", "vv5": "New Believers"}
MODES = ("stock", "collection_progression", "immediate_fixed")
BASE = 0x400000
HEAP, STK = 0x10000000, 0x20000000
RETURN = 0x0BAD0000
MAP_SCALE = 424 / 2048                      # 0.20703125, exact in a float
ORIGIN = (188, 61)                          # the map box's top left corner
ROUND = bytes.fromhex("50DB1C2458")         # push eax; fistp dword [esp]; pop eax
FIXES = {
    "vv3": ((0x2E285, bytes.fromhex("E8CE0C0400898610300000"), ROUND + bytes.fromhex("898610300000")),
            (0x28F01, bytes.fromhex("E8526004008BE8"), ROUND + bytes.fromhex("8BE8"))),
    "vv4": ((0x4C411, bytes.fromhex("E81A520200898610300000"), ROUND + bytes.fromhex("898610300000")),
            (0x1C5CB, bytes.fromhex("E860500500803B008BE8"), ROUND + bytes.fromhex("803B008BE8"))),
}
SITES = {"vv3": (0x42E285, 0x428F01), "vv4": (0x44C411, 0x41C5CB)}   # the two _ftol calls, as addresses
# origin routine, the queue object, static and animated queued sprite, their blitter calls,
# the overlay list routine and its blitter call
ROUTINES = {
    "vv3": dict(origin=0x42E250, queue=0x58F6F8, static=0x42E4B0, anim=0x42E510,
                static_blit=0x409FA0, anim_blit=0x409FD0, overlays=0x428EF0, overlay_blit=0x409FC0),
    "vv4": dict(origin=0x44C3E0, queue=0x4DB9F8, static=0x44C5E0, anim=0x44C640,
                static_blit=0x409A40, anim_blit=0x409AE0, overlays=0x41C5B0, overlay_blit=0x409AD0),
    "vv5": dict(origin=0x44F0F0, queue=0x521078),
}
MAP_SCALES = {"vv3": MAP_SCALE, "vv4": MAP_SCALE, "vv5": struct.unpack("<f", struct.pack("<f", 0.2125))[0]}
# The Tree of Life's water on the map: (picture, frame width, frame height, frames, world x, world y).
# The river sections (0x439BA0, the river puzzle's object, its strongest state) are single pictures;
# the waterfalls are the ambient animations 0x24..0x2A (0x46DB.., not centred, their table's frame counts).
VV4_WATER = (
    ("stream_section-1.png", 353, 386, 1, 1426, 3),
    ("stream_section-1-waterfall.png", 345, 563, 1, 1520, 310),
    ("stream_section-2-strong.png", 910, 387, 1, 639, 295),
    ("stream_section-3-strong.png", 288, 237, 1, 420, 554),
    ("stream_section-4-strong.png", 998, 1008, 1, 0, 620),
    ("waterfall1Strip.png", 153, 163, 30, 697, 1113),
    ("waterfall2Strip.png", 162, 222, 35, 684, 830),
    ("waterfall3Strip.png", 90, 134, 33, 421, 634),
    ("waterfall4Strip.png", 366, 247, 30, 1215, 304),
    ("waterfalls567Strip.png", 187, 248, 30, 1504, 85),
    ("waterfall8Strip.png", 136, 393, 32, 1744, 481),
    ("waterfall9Strip.png", 94, 106, 30, 1560, 338),
)
NO_STOCK = "stock executables are not available"


def overview_map_water_fixes(game: str) -> tuple:
    """The (file offset, stock bytes, fixed bytes) this fix adds to <game>_fix_vanilla_bugs."""
    return FIXES.get(game, ())


def _stock_path(game: str) -> Path:
    return STOCK_DIR / f"Virtual Villagers - {NAMES[game]}.exe"


def _have(game: str) -> bool:
    return pefile is not None and _stock_path(game).is_file()


@functools.lru_cache(maxsize=None)
def _build(game: str):
    return next(b for b in load_builds() if b.id == game)


@functools.lru_cache(maxsize=None)
def _render(game: str, mode: str) -> bytes:
    data, _ = render_patched_bytes(_stock_path(game), _build(game), mode, [f"{game}_fix_vanilla_bugs"])
    return bytes(data)


@functools.lru_cache(maxsize=None)
def _stock(game: str) -> bytes:
    return _stock_path(game).read_bytes()


@functools.lru_cache(maxsize=None)
def _image(data: bytes) -> bytes:
    return pefile.PE(data=data).get_memory_mapped_image()


def _f32(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


class _Machine:
    """The mapped executable; a call to <stop> is recorded (its stack arguments) and ends the run."""

    def __init__(self, data: bytes, stop: int | None = None) -> None:
        image = _image(data)
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, image)
        for area in (HEAP, STK):
            mu.mem_map(area, 0x400000)
        mu.mem_map(RETURN, 0x1000)
        self.mu, self.stop, self.args = mu, stop, None
        self.hook = mu.hook_add(UC_HOOK_CODE, self._code)

    def _code(self, uc, address, _size, _user) -> None:
        if address == self.stop:
            esp = uc.reg_read(UC_X86_REG_ESP)
            self.args = struct.unpack("<7i", bytes(uc.mem_read(esp + 4, 28)))
            uc.emu_stop()

    def call(self, entry: int, ecx: int, args: tuple[int, ...]) -> None:
        esp = STK + 0x200000
        self.mu.mem_write(esp, struct.pack("<I", RETURN) + b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.reg_write(UC_X86_REG_ECX, ecx)
        self.mu.emu_start(entry, RETURN, count=200_000)

    def read(self, va: int) -> int:
        return struct.unpack("<i", bytes(self.mu.mem_read(va, 4)))[0]

    def close(self) -> None:
        self.mu.hook_del(self.hook)
        self.mu = None


def queue_percent(game: str, data: bytes, scale: float) -> int:
    """The whole percent the real origin routine leaves for every queued sprite (queue +0x3010)."""
    r = ROUTINES[game]
    m = _Machine(data)
    try:
        m.call(r["origin"], r["queue"], (ORIGIN[0], ORIGIN[1], _f32(scale)))
        return m.read(r["queue"] + 0x3010)
    finally:
        m.close()


def queued_sprite(game: str, data: bytes, x: int, y: int, frame: int | None) -> tuple[int, int, int]:
    """(map x, map y, percent) the real queue hands the blitter for a sprite at world (x, y): the origin
    routine with the map's scale, then the static (frame None) or animated queued sprite routine."""
    r = ROUTINES[game]
    kind = "static" if frame is None else "anim"
    m = _Machine(data, r[f"{kind}_blit"])
    try:
        m.call(r["origin"], r["queue"], (ORIGIN[0], ORIGIN[1], _f32(MAP_SCALES[game])))
        sprite = HEAP + 0x100
        if frame is None:   # (sprite, x, y, alpha) -> blit(sprite, x, y, alpha, percent, 0)
            m.call(r["static"], r["queue"], (sprite, x, y, _f32(1.0)))
            got = m.args
            assert got[0] == sprite and got[3] == _f32(1.0) and got[5] == 0, got
            return got[1], got[2], got[4]
        # (anim, x, y, frame, alpha) -> blit(anim, x, y, frame, alpha, percent, 0)
        m.call(r["anim"], r["queue"], (sprite, x, y, frame, _f32(1.0)))
        got = m.args
        assert got[0] == sprite and got[3] == frame and got[4] == _f32(1.0) and got[6] == 0, got
        return got[1], got[2], got[5]
    finally:
        m.close()


def overlay(game: str, data: bytes, x: int, y: int, frame: int) -> tuple[int, int, int]:
    """(map x, map y, percent) the real overlay list hands the blitter for its one entry at world (x, y)."""
    r = ROUTINES[game]
    m = _Machine(data, r["overlay_blit"])
    try:
        entries = HEAP + 0x10000                     # {active byte, x, y, sprite, frame} x 0x14, then 0
        for k, value in enumerate((1, x, y, HEAP + 0x100, frame)):
            m.mu.mem_write(entries + 4 * k, struct.pack("<i", value))
        m.mu.mem_write(entries + 0x14, b"\0")
        m.mu.mem_write(entries + 0x1680, struct.pack("<I", HEAP + 0x200))     # its graphics
        m.call(r["overlays"], entries, (ORIGIN[0], ORIGIN[1], _f32(MAP_SCALE)))
        got = m.args
        return got[1], got[2], got[4]
    finally:
        m.close()


def drawn(length: int, percent: int) -> int:
    """The blitter's drawn length: the frame length times percent / 100 as a float, cut (The Tree of Life 0x404CB0)."""
    return int(length * struct.unpack("<f", struct.pack("<f", percent / 100.0))[0])


class RowTests(unittest.TestCase):
    def test_each_row_carries_its_fix_and_says_so(self) -> None:
        rows = {p.raw["game_id"]: p.raw for p in load_fun_patches() if p.raw["id"].endswith("_fix_vanilla_bugs")}
        for game, fixes in FIXES.items():
            with self.subTest(game=game):
                row = rows[game]
                pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"]))
                          for p in row["patches"]]
                for fix in fixes:
                    self.assertIn(fix, pinned)
                self.assertIn("Overview Map's water lines up with its riverbeds", row["description"])
                self.assertIn("every frame of their animations", row["description"])
                self.assertTrue(row["description"].endswith("**Needs no other patch.**"))
                self.assertTrue(any("Overview Map scale" in text for text in row["behavior_changes"]))
        for game in ("vv1", "vv2", "vv5"):
            self.assertNotIn("Overview Map's water", rows[game]["description"])


@unittest.skipUnless(all(_have(g) for g in NAMES), NO_STOCK)
class StockBytesTests(unittest.TestCase):
    def test_the_sites_hold_the_stock_bytes(self) -> None:
        for game, fixes in FIXES.items():
            pe = pefile.PE(data=_stock(game), fast_load=True)
            for va, (offset, before, after) in zip(SITES[game], fixes):
                with self.subTest(game=game, offset=hex(offset)):
                    self.assertEqual(pe.get_offset_from_rva(va - BASE), offset)
                    self.assertEqual(_stock(game)[offset:offset + len(before)], before)
                    self.assertEqual(len(before), len(after))
                    # the replaced call is the game's _ftol
                    rel = struct.unpack("<i", before[1:5])[0]
                    target = va + 5 + rel
                    self.assertEqual(target, {"vv3": 0x46EF58, "vv4": 0x471630}[game])

    def test_every_mode_writes_the_fix(self) -> None:
        for game, fixes in FIXES.items():
            for mode in MODES:
                data = _render(game, mode)
                for offset, _, after in fixes:
                    with self.subTest(game=game, mode=mode, offset=hex(offset)):
                        self.assertEqual(data[offset:offset + len(after)], after)


class CloudsRowTests(unittest.TestCase):
    """The Overview Map's cloud rows (<game>_disable_overview_clouds, PR #708) jump over the map's cloud
    loop inside the same draw routine (The Tree of Life 0x4454A1, The Secret City 0x46C3BD, New Believers
    0x448623); this fix's bytes are elsewhere, and the two rows install together."""
    CLOUD_SITES = {"vv3": 0x46C3BD, "vv4": 0x4454A1, "vv5": 0x448623}

    def test_the_fix_is_clear_of_the_cloud_jumps(self) -> None:
        for game, fixes in FIXES.items():
            cloud = self.CLOUD_SITES[game] - BASE
            for offset, before, _ in fixes:
                with self.subTest(game=game, offset=hex(offset)):
                    self.assertFalse(offset - 16 <= cloud < offset + len(before) + 16)

    @unittest.skipUnless(all(_have(g) for g in NAMES), NO_STOCK)
    def test_installs_together_with_the_cloud_row(self) -> None:
        ids = {p.id for p in load_fun_patches()}
        for game, fixes in FIXES.items():
            cloud_id = f"{game}_disable_overview_clouds"
            if cloud_id not in ids:
                continue        # the cloud row is not on this branch yet
            with self.subTest(game=game):
                cloud_row = next(p for p in load_fun_patches() if p.id == cloud_id)
                for mode in MODES:
                    data, _ = render_patched_bytes(_stock_path(game), _build(game), mode,
                                                   [f"{game}_fix_vanilla_bugs", cloud_id])
                    data = bytes(data)
                    for offset, _, after in fixes:
                        self.assertEqual(data[offset:offset + len(after)], after, mode)
                    for p in cloud_row.raw.get("patches", []):
                        off, after = int(p["offset"], 16), bytes.fromhex(p["after"])
                        self.assertEqual(data[off:off + len(after)], after, mode)


@unittest.skipUnless(all(_have(g) for g in NAMES), NO_STOCK)
class EmulationTests(unittest.TestCase):
    def test_the_map_percent_is_cut_in_stock_and_rounded_when_fixed(self) -> None:
        for game in FIXES:
            with self.subTest(game=game):
                self.assertEqual(queue_percent(game, _stock(game), MAP_SCALE), 20)
                self.assertEqual(queue_percent(game, _stock(game), 1.0), 100)
                for mode in MODES:
                    self.assertEqual(queue_percent(game, _render(game, mode), MAP_SCALE), 21, mode)
                    self.assertEqual(queue_percent(game, _render(game, mode), 1.0), 100, mode)   # village view

    def test_new_believers_already_draws_its_map_at_the_rounded_percent(self) -> None:
        # 0.2125 x 100 = 21.25: cut or rounded it is 21, so New Believers needs no change.
        self.assertEqual(queue_percent("vv5", _stock("vv5"), MAP_SCALES["vv5"]), 21)
        self.assertEqual(round(MAP_SCALES["vv5"] * 100), 21)

    def test_the_overlay_list_matches_the_queue(self) -> None:
        for game in FIXES:
            for x, y in ((0, 0), (1426, 3), (1084, 1137), (2047, 2047)):
                with self.subTest(game=game, point=(x, y)):
                    sx, sy, pct = overlay(game, _stock(game), x, y, 0)
                    self.assertEqual((sx, sy), (int(x * MAP_SCALE) + ORIGIN[0], int(y * MAP_SCALE) + ORIGIN[1]))
                    self.assertEqual(pct, 20)
                    for mode in MODES:
                        self.assertEqual(overlay(game, _render(game, mode), x, y, 0), (sx, sy, 21), mode)

    def test_every_frame_of_the_tree_of_life_water_fills_its_riverbed(self) -> None:
        fixed = {mode: _render("vv4", mode) for mode in MODES}
        for name, fw, fh, frames, x, y in VV4_WATER:
            for frame in range(frames):
                with self.subTest(picture=name, frame=frame):
                    kind = None if frames == 1 else frame
                    sx, sy, pct = queued_sprite("vv4", _stock("vv4"), x, y, kind)
                    # where the map puts it: the same in both, exactly the world point shrunk
                    self.assertEqual((sx, sy), (int(x * MAP_SCALE) + ORIGIN[0], int(y * MAP_SCALE) + ORIGIN[1]))
                    self.assertEqual(pct, 20)
                    for mode, data in fixed.items():
                        self.assertEqual(queued_sprite("vv4", data, x, y, kind), (sx, sy, 21), mode)
                    # the riverbed under it ends at (x + fw, y + fh) shrunk; how far the drawn picture misses it
                    for length, start in ((fw, x), (fh, y)):
                        bed = (start + length) * MAP_SCALE
                        before = int(start * MAP_SCALE) + drawn(length, 20) - bed
                        after = int(start * MAP_SCALE) + drawn(length, 21) - bed
                        self.assertLess(before, 0)                       # stock: short of the bed
                        self.assertLessEqual(abs(after), abs(before))
                        # the percent's 0.30 points, plus the cut position and cut size (under a pixel each)
                        self.assertLessEqual(abs(after), length * (0.21 - MAP_SCALE) + 2.0)
        # the largest river picture: stock ends 7 map pixels short of its bed, fixed within 3
        bed = (620 + 1008) * MAP_SCALE
        self.assertGreater(bed - (int(620 * MAP_SCALE) + drawn(1008, 20)), 7)
        self.assertLess(abs(int(620 * MAP_SCALE) + drawn(1008, 21) - bed), 3.5)


if __name__ == "__main__":
    unittest.main()
