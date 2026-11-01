"""Picture Studio's carried items (src/vv_pictures_carried.py), in all five games.

* The catalogue: every number the games' carry draws turn into a picture of the item sheets is listed once,
  named, marked as the game's, the patcher's (only the Golden Mushroom), unused or blank, and offered on
  both tabs; From my save adds "As the game shows it after loading" (a baby while expecting).
* The game's own evidence, read from the stock executables (skipped without them, as on CI): the values the
  docs call refused are refused, and the reachability corrections the docs rest on hold.
* The Golden Mushroom: the companion's offsets are the ones in its source, and each renderer draws the
  patcher's picture there.

Each renderer's own test file (tests/test_pictures_vv1.py ... vv5.py, test_every_carried_item) runs the
game's draw in Unicorn for every item here, in every direction and every carrying pose.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import carried_golden  # noqa: E402
import vv_picture_image as pi  # noqa: E402
import vv_pictures_carried as carried  # noqa: E402
import vv_pictures_vv1 as v1  # noqa: E402
import vv_pictures_vv2 as v2  # noqa: E402
import vv_pictures_vv3 as v3  # noqa: E402
import vv_pictures_vv4 as v4  # noqa: E402
import vv_pictures_vv5 as v5  # noqa: E402

EXES = ROOT / "research" / "stock-executables"
TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}

# Every number each game's carry draw makes a picture of: carrying.png's cells below the first collectable
# number, then the collectables sheet's 54 cells.
RANGES = {1: list(range(15)) + [15],
          2: list(range(26)) + list(range(0x1E, 0x1E + 54)),
          3: list(range(52)) + list(range(0x34, 0x34 + 54)),
          4: list(range(0x46)) + list(range(0x46, 0x46 + 54)),
          5: list(range(0x50)) + list(range(0x50, 0x50 + 54))}


class Catalogue(unittest.TestCase):
    def test_every_picture_is_listed_once(self) -> None:
        for game, values in RANGES.items():
            listed = [i.value for i in carried.items(game)]
            self.assertEqual(sorted(listed), sorted(set(values)), game)
            self.assertEqual(len(listed), len(set(listed)), game)

    def test_statuses_and_labels(self) -> None:
        for game in RANGES:
            for i in carried.items(game):
                self.assertIn(i.status, (carried.GAME, carried.UNUSED, carried.BLANK, carried.PATCHER))
                self.assertTrue(i.name and i.doing, (game, i))
                label = carried.label(i)
                self.assertEqual(label.endswith(carried.UNUSED_MARK), i.status == carried.UNUSED, label)
                self.assertEqual(label.endswith(carried.BLANK_MARK), i.status == carried.BLANK, label)
            patcher = [i.value for i in carried.items(game) if i.status == carried.PATCHER]
            self.assertEqual(patcher, [carried.GOLDEN_ITEM[game]], game)
            self.assertEqual(carried.item(game, carried.BABY).name, "Baby")
            self.assertEqual(carried.item(game, carried.BABY).status, carried.GAME)

    def test_options_offer_everything(self) -> None:
        for game in RANGES:
            opts = carried.options(game)
            self.assertEqual(opts[0].key, carried.NOTHING[game])
            self.assertEqual(sorted(o.key for o in opts[1:]), sorted(RANGES[game]))
            marked = [o for o in opts if o.patcher]
            self.assertEqual([o.key for o in marked], [carried.GOLDEN_ITEM[game]])
            # the game's items first, then the patcher's, then the unused and blank pictures
            order = [carried.item(game, o.key).status for o in opts[1:]]
            rank = {carried.GAME: 0, carried.PATCHER: 1, carried.UNUSED: 2, carried.BLANK: 3}
            self.assertEqual(order, sorted(order, key=rank.get))
            saved = carried.options(game, saved=True)
            self.assertEqual(saved[0].key, carried.SAVED)
            self.assertEqual([o.key for o in saved[1:]], [o.key for o in opts])

    def test_saved_choice_is_what_loading_gives(self) -> None:
        for game, nothing in carried.NOTHING.items():
            self.assertEqual(carried.resolve(carried.SAVED, True, nothing), carried.BABY)
            self.assertEqual(carried.resolve(carried.SAVED, False, nothing), nothing)
            self.assertEqual(carried.resolve(None, True, nothing), nothing)
            self.assertEqual(carried.resolve(7, False, nothing), 7)

    def test_renderers_offer_the_catalogue(self) -> None:
        def keys(fields, key):
            return [o.key for o in {f.key: f for f in fields}[key].options]
        self.assertEqual(keys(v1.pose_fields(), "item"), [o.key for o in carried.options(1)])
        self.assertEqual(keys(v1.saved_pose_fields(), "item"), [o.key for o in carried.options(1, True)])
        self.assertEqual(keys(v2.pose_fields(), "carrying"), [o.key for o in carried.options(2)])
        self.assertEqual(keys(v2.pose_fields(saved=True), "carrying"), [o.key for o in carried.options(2, True)])
        self.assertEqual(keys(v2.pose_fields(), "litter"), [0, 2, 3])
        self.assertEqual(keys(v3.carry_fields(), "item"), [o.key for o in carried.options(3)])
        self.assertEqual(keys(v4.pose_fields(), "item"), [o.key for o in carried.options(4)])
        self.assertEqual(keys(v4.pose_fields(saved=True), "item"), [o.key for o in carried.options(4, True)])
        self.assertEqual(keys(v5._pose_fields(), "item"), [o.key for o in carried.options(5)])
        self.assertEqual(keys(v5._pose_fields(saved=True), "litter"), [carried.SAVED, 1, 2, 3])
        # New Believers no longer offers carrying.png's 80-90 twice (those numbers are collectables)
        self.assertEqual(len(keys(v5._pose_fields(), "item")), 1 + 80 + 54)


class GoldenMushroom(unittest.TestCase):
    def test_offsets_are_the_companions(self) -> None:
        shifts = carried_golden.source_shifts()
        if shifts is None:
            self.skipTest("the Golden Mushroom companion's source is not in this checkout")
        self.assertEqual(shifts, carried.GOLDEN_SHIFT)

    def test_the_picture_ships_with_the_patcher(self) -> None:
        self.assertTrue(carried.GOLDEN_ART.is_file())
        data = carried.GOLDEN_ART.read_bytes()
        self.assertEqual((int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")), carried.GOLDEN_SIZE)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"assets/golden_mushroom/golden_mushroom.png"', release)
        for module in (v1, v3, v4, v5):
            self.assertEqual(module.patcher_art().get(carried.GOLDEN_FILE), carried.GOLDEN_ART, module.__name__)

    def test_each_renderer_draws_it_where_the_companion_does(self) -> None:
        # A New Home: carrying.png frame 15 (clamped to cell 0 by the 15 x 1 sheet) -> golden at (+6, +2)
        sheets = pi.Sheets(_Sized({"carrying.png": (600, 25), "peep_shadow1.png": (68, 64),
                                   "male_bodies00.png": (640, 650), "male_bodies10.png": (640, 650),
                                   "male_bodies01.png": (640, 650), "male_bodies11.png": (640, 650),
                                   "male_heads.png": (280, 1300), carried.GOLDEN_FILE: carried.GOLDEN_SIZE}))
        v = v1.Villager(age=600, item=15, direction=1)
        stock = [d for d in v1.plan(v, sheets, golden_art=False) if d.what == "carried"]
        gold = [d for d in v1.plan(v, sheets) if d.what == "carried"]
        self.assertEqual([(d.file, d.x - 6, d.y - 2) for d in gold], [(carried.GOLDEN_FILE, s.x, s.y) for s in stock])
        # The Secret City: collectables frame 50 -> golden at (+7, 0); the twins' copy stays carrying.png's
        look = v3.Look(age=600, item=0x66, litter=2, direction=1, frame=19)
        stock = [d for d in v3.plan(look, golden_art=False) if d.what == "item"]
        gold = [d for d in v3.plan(look) if d.what == "item"]
        self.assertEqual((gold[0].file, gold[0].x - 7, gold[0].y), (carried.GOLDEN_FILE, stock[0].x, stock[0].y))
        self.assertEqual(gold[1:], stock[1:])
        self.assertEqual(stock[1].file, "carrying.png")


class _Sized:
    """A picture source that knows only sizes (blank pixels)."""

    def __init__(self, sizes: dict) -> None:
        self.sizes = sizes
        self.problem = ""
        self.copy = None

    def read(self, name: str):
        import struct
        import zlib
        size = self.sizes.get(name)
        if size is None:
            return None
        w, h = size
        raw = b"".join(b"\0" + b"\0\0\0\0" * w for _ in range(h))

        def chunk(kind, body):
            return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _exe(game: int):
    path = EXES / f"Virtual Villagers - {TITLES[game]}.exe"
    if not path.is_file():
        return None
    try:
        import pefile
    except ImportError:
        return None
    pe = pefile.PE(str(path), fast_load=True)
    return pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase


class TheGamesOwnEvidence(unittest.TestCase):
    """Facts the docs rest on, read from the stock executables (skipped without them)."""

    def code(self, game: int, va: int, n: int) -> bytes:
        found = _exe(game)
        if found is None:
            self.skipTest(f"the stock {TITLES[game]} executable and pefile are needed")
        image, base = found
        return image[va - base:va - base + n]

    def test_the_setters_refuse_numbers_past_the_golden_mushroom(self) -> None:
        # The Tree of Life 0x4132B5 `cmp ebp, 0x78; ja`; New Believers 0x413755 `cmp ebp, 0x82; ja`
        self.assertEqual(self.code(4, 0x4132B5, 3), bytes.fromhex("83fd78"))
        self.assertEqual(self.code(4, 0x4132B8, 1), b"\x77")
        self.assertEqual(self.code(5, 0x413755, 6), bytes.fromhex("81fd82000000"))
        self.assertEqual(self.code(5, 0x41375B, 1), b"\x77")

    def test_new_believers_installs_the_golden_eye(self) -> None:
        """0x479C19 `push 0xB7` (Installing the golden eye, the action that carries item 79) jumps to the
        shared tail 0x479CFF, which starts the action (call 0x465580): item 79 is in the game."""
        self.assertEqual(self.code(5, 0x479C19, 5), bytes.fromhex("68b7000000"))
        self.assertEqual(self.code(5, 0x479C1E, 1), b"\xe9")
        self.assertEqual(self.code(5, 0x479D01, 1), b"\xe8")
        tail = int.from_bytes(self.code(5, 0x479D02, 4), "little", signed=True) + 0x479D06
        self.assertEqual(tail, 0x465580)

    def test_the_secret_city_carries_the_unlit_torch(self) -> None:
        """0x44BFB1 `push 0x32; mov ecx, esi; call 0x461730` (Trying an idea: carry item 50)."""
        self.assertEqual(self.code(3, 0x44BFB1, 2), bytes.fromhex("6a32"))
        call = int.from_bytes(self.code(3, 0x44BFB6, 4), "little", signed=True) + 0x44BFBA
        self.assertEqual(call, 0x461730)


class SavedChoice(unittest.TestCase):
    """From my save's "As the game shows it after loading": the baby for an expecting villager."""

    def test_the_secret_city(self) -> None:
        look = v3.Look(age=600, expecting=True)
        v3.apply_pose(look, {"item": carried.SAVED, "litter": carried.SAVED})
        self.assertEqual(look.item, carried.BABY)
        look = v3.Look(age=600)
        v3.apply_pose(look, {"item": carried.SAVED})
        self.assertEqual(look.item, v3.NO_ITEM)

    def test_new_believers_pose(self) -> None:
        look = v5.Look(expecting=True, litter=3)
        pose = v5._pose_from({"item": carried.SAVED, "litter": carried.SAVED}, look)
        self.assertEqual((pose.item, pose.litter), (carried.BABY, 3))
        pose = v5._pose_from({"item": carried.SAVED, "litter": carried.SAVED}, v5.Look())
        self.assertEqual((pose.item, pose.litter), (-1, 1))

    def test_a_new_home_and_the_lost_children(self) -> None:
        v, _ = v1._apply_pose(v1.Villager(expecting=True, litter=2), {"item": carried.SAVED, "litter": carried.SAVED})
        self.assertEqual((v.item, v.litter), (carried.BABY, 2))
        st, _ = v2._apply_pose(v2.State(expecting=True, litter=3), {"carrying": carried.SAVED, "litter": carried.SAVED})
        self.assertEqual((st.item, st.litter), (carried.BABY, 3))
        st, _ = v2._apply_pose(v2.State(), {"carrying": carried.SAVED})
        self.assertEqual(st.item, v2.NO_ITEM)


if __name__ == "__main__":
    unittest.main()
