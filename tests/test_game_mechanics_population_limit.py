"""The Game Mechanics page's population limit (src/vv_game_mechanics_life.py): which population mode a game's exe
has, read from its own bytes -- including the 256 Villagers (Experimental) builds, whose cap code is the feature's
own mode_rows and not data/builds.json's -- and the Population limit and Room for new villagers lines for each mode
and collection state.

The owner's Tree of Life save with Immediate Fixed Max Pop and 256 Villagers was shown "up to 256" after a "normal
game" sentence, because the 256 build's exe was read as stock (its Immediate Fixed writes 166 at 0x683AA, not
builds.json's 60, and its Collection Progression calls cp_add instead of changing 0x683F1)."""
from __future__ import annotations

import gzip
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402

NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe" for g, n in NAMES.items()}
STOCK_ABSENT = "stock executables are not in the release source archive"
MODES = ("stock", "collection_progression", "immediate_fixed")
NOW = 1_790_000_000 + 3_000_000

_RENDERS: dict = {}


def rendered(game: int, mode: str, which: str) -> bytes:
    """The game's exe in `mode` with: "none" (only the population mode), "all" (every public patch but the
    experimental ones), "256" (256 Villagers alone) or "all256" (every public patch with 256 Villagers)."""
    key = (game, mode, which)
    if key not in _RENDERS:
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == f"vv{game}")
        public = [p.id for p in vfp.load_public_fun_patches()
                  if p.game_id == f"vv{game}" and p.id not in vfp.ALTERNATIVE_FUN_PATCH_IDS]
        ids = {"none": [], "all": [p for p in public if p not in vfp.EXPERIMENTAL_FUN_PATCH_IDS],
               "256": [f"vv{game}_population_256"], "all256": public}[which]
        data, _ = vfp.render_patched_bytes(STOCK[game], build, mode, ids)
        _RENDERS[key] = bytes(data)
    return _RENDERS[key]


def village(game: int, exe: Path | None = None, general: bool = False) -> gm.Village:
    return gm.Village(Path("."), game, 1, Path(f"{game}.ldw"), b"", None, NOW, exe=exe, general=general)


def words(game: int, mode, big, sets, magic=None, extra="") -> str:
    with mock.patch.object(life, "population_mode", return_value=(mode, big)):
        text, ok = life.limit_words(village(game, Path("x.exe")), sets, magic, extra)
    return text + "."                                 # the page adds the full stop


@unittest.skipUnless(all(p.is_file() for p in STOCK.values()), STOCK_ABSENT)
class ModeFromTheExe(unittest.TestCase):
    def test_the_stock_exes_are_stock(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertEqual(life.exe_population_mode(STOCK[game].read_bytes(), game), ("stock", False))

    def test_every_mode_of_the_150_villager_builds(self):
        for game in range(1, 6):
            for mode in MODES:
                for which in ("none", "all"):
                    with self.subTest(game=game, mode=mode, which=which):
                        want = life.EITHER if game == 1 and mode != "stock" else mode
                        self.assertEqual(life.exe_population_mode(rendered(game, mode, which), game), (want, False))

    def test_every_mode_of_the_256_villager_builds(self):
        for game in (3, 4, 5):
            for mode in MODES:
                for which in ("256", "all256"):
                    with self.subTest(game=game, mode=mode, which=which):
                        self.assertEqual(life.exe_population_mode(rendered(game, mode, which), game), (mode, True))

    def test_the_150_villager_rows_would_read_a_256_build_as_stock(self):
        # The bug: builds.json's Immediate Fixed bytes are not in the 256 build, and its Collection Progression
        # byte is still the stock 0x5A, so the old check said "stock".
        import json
        variants = next(g for g in json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))["games"]
                        if g["id"] == "vv4")["variants"]
        exe = rendered(4, "immediate_fixed", "256")
        self.assertFalse(life._matches(exe, variants["immediate_fixed"]["patches"], "after"))
        self.assertTrue(life._matches(exe, variants["collection_progression"]["patches"], "before"))

    def test_unknown_bytes_are_not_known(self):
        exe = bytearray(rendered(4, "immediate_fixed", "256"))
        exe[0x683AA] ^= 0xFF
        self.assertEqual(life.exe_population_mode(bytes(exe), 4), (None, True))
        exe = bytearray(rendered(2, "collection_progression", "none"))
        exe[0x4B3F2] ^= 0xFF
        self.assertEqual(life.exe_population_mode(bytes(exe), 2), (None, False))


class TheNumbersAreTheBytes(unittest.TestCase):
    """Each mode's base and fixed bonus as the rows write them."""

    def rows(self, game: int, mode: str) -> list[dict]:
        import json
        games = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))["games"]
        return next(g for g in games if g["id"] == f"vv{game}")["variants"][mode]["patches"]

    def spec(self, game: int) -> dict:
        import json
        return json.loads((ROOT / "data" / f"vv{game}_population_256_feature.json").read_text(encoding="utf-8"))

    def test_collection_progression_bases(self):
        after = {p["offset"]: bytes.fromhex(p["after"]) for g in (2, 3, 4, 5)
                 for p in self.rows(g, "collection_progression")}
        self.assertEqual(int.from_bytes(after["0x4B3F2"][2:6], "little"), life.PROGRESSION_BASE[2])
        self.assertEqual(after["0x5FEE3"][0], life.PROGRESSION_BASE[3])
        self.assertEqual(after["0x683F1"][0], life.PROGRESSION_BASE[4])
        self.assertEqual(int.from_bytes(after["0x94500"][2:6], "little"), life.PROGRESSION_BASE[5])
        for game in (3, 4):
            pages = self.spec(game)["population_256"]["code_pages"]
            page = bytes.fromhex(pages["collection_progression"]["hex"])
            stock = bytes.fromhex(pages["stock"]["hex"])
            at = next(n for n in range(len(page)) if page[n] != stock[n])
            add = page.index(b"\x81\xC6", at - 2)            # add esi, imm32 in cp_add
            self.assertEqual(int.from_bytes(page[add + 2:add + 6], "little"), life.PROGRESSION_BASE_256[game])
        row = next(r for r in self.spec(5)["population_256"]["mode_rows"]["collection_progression"]
                   if r["offset"] == "0x94500")
        self.assertEqual(int.from_bytes(bytes.fromhex(row["after"])[2:6], "little"), life.PROGRESSION_BASE_256[5])

    def test_immediate_fixed_is_150_or_256(self):
        fixed = {2: ("0x4B378", 1), 3: ("0x5FEA2", 1), 4: ("0x683AA", 1), 5: ("0x72C04", 1)}
        for game, (offset, at) in fixed.items():
            with self.subTest(game=game):
                row = next(p for p in self.rows(game, "immediate_fixed") if p["offset"] == offset)
                self.assertEqual(bytes.fromhex(row["after"])[at] + life.STOCK_BASE, 256 if game == 2 else 150)
                if game >= 3:
                    row = next(p for p in self.spec(game)["population_256"]["mode_rows"]["immediate_fixed"]
                               if p["offset"] == offset)
                    self.assertEqual(bytes.fromhex(row["after"])[at] + life.STOCK_BASE, 256)

    def test_the_256_descriptions_say_the_same(self):
        for game in (3, 4, 5):
            with self.subTest(game=game):
                text = self.spec(game)["description"]
                self.assertIn(f"cap becomes {life.PROGRESSION_BASE_256[game]} plus the collection", text)
                self.assertIn("with Immediate Fixed Max Pop it is 256 at once", text)
                stock = {3: 125, 4: 115, 5: 105}[game]
                self.assertIn(f"No Population Increase the stock cap of {stock} is unchanged", text)
                full = [(None, 12, 12)] * 4 if game != 5 else [(None, 24, 24)] * 2
                top = life.STOCK_BASE + life.collection_bonus(4 if game != 5 else 2, len(full)) + (10 if game == 3 else 0)
                self.assertEqual(top, stock)


class LimitWords(unittest.TestCase):
    VV4_NONE = [("Fish Scale", 8, 12), ("Lab Equipment", 9, 12), ("Mausoleum Mural", 8, 12), ("Wind Flute", 9, 12)]
    VV4_TWO = [("Fish Scale", 12, 12), ("Lab Equipment", 12, 12), ("Mausoleum Mural", 0, 12), ("Wind Flute", 3, 12)]
    VV4_ALL = [(name, 12, 12) for name, _, _ in VV4_NONE]

    def test_the_owners_save(self):
        self.assertEqual(words(4, "immediate_fixed", True, self.VV4_NONE),
                         "Population limit: 256 (Immediate Fixed Max Pop with 256 Villagers). In the normal game it "
                         "would be 90, plus 5 for each complete collection, 25 with all four; this village has none "
                         "complete (Fish Scale 8, Lab Equipment 9, Mausoleum Mural 8, Wind Flute 9 of 12), so 90.")

    def test_every_mode_of_the_tree_of_life(self):
        normal = "In the normal game it would be 90, plus 5 for each complete collection, 25 with all four; "
        two = "this village has 2 complete (Fish Scale 12, Lab Equipment 12, Mausoleum Mural 0, Wind Flute 3 of 12), so 100."
        self.assertEqual(words(4, "immediate_fixed", False, self.VV4_TWO),
                         f"Population limit: 150 (Immediate Fixed Max Pop). {normal}{two}")
        self.assertEqual(words(4, "collection_progression", False, self.VV4_TWO),
                         "Population limit: 135 (Collection Progression Max Pop: 125 plus the collection bonus, 150 at "
                         f"most). {normal}{two}")
        self.assertEqual(words(4, "collection_progression", True, self.VV4_TWO),
                         "Population limit: 241 (Collection Progression Max Pop with 256 Villagers: 231 plus the "
                         f"collection bonus, 256 at most). {normal}{two}")
        self.assertTrue(words(4, "collection_progression", True, self.VV4_ALL).startswith("Population limit: 256 ("))
        self.assertIn("this village has all four complete", words(4, "collection_progression", True, self.VV4_ALL))
        self.assertEqual(words(4, "stock", True, self.VV4_TWO),
                         "Population limit: 100 (No Population Increase with 256 Villagers, which keeps the normal "
                         "game's limit and only makes the villager table larger). The rule: 90, plus 5 for each "
                         f"complete collection, 25 with all four; {two}")
        self.assertEqual(words(4, "stock", False, self.VV4_ALL)[:23], "Population limit: 115 (")
        self.assertEqual(words(4, "collection_progression", True, None),
                         "Population limit: 231 plus the collection bonus, 256 at most (Collection Progression Max Pop "
                         "with 256 Villagers). In the normal game it would be 90, plus 5 for each complete collection, "
                         "25 with all four.")
        self.assertEqual(words(4, None, None, self.VV4_TWO)[:31], "Population limit: not known (wh")

    def test_the_secret_city_counts_magic(self):
        four = [(None, 12, 12), (None, 5, 12), (None, 0, 12), (None, 3, 12)]
        self.assertIn("this village has 1 complete (12, 5, 0 and 3 of 12 pieces) and Magic at level 3, so 105.",
                      words(3, "stock", False, four, 3))
        self.assertTrue(words(3, "stock", False, four, 2).startswith("Population limit: 95 ("))
        self.assertTrue(words(3, "collection_progression", False, four, 3).startswith(
            "Population limit: 130 (Collection Progression Max Pop: 115 plus the collection and Magic bonus, 150 at most)"))
        self.assertTrue(words(3, "collection_progression", True, [(None, 12, 12)] * 4, 3).startswith(
            "Population limit: 256 (Collection Progression Max Pop with 256 Villagers: 221 plus"))
        self.assertTrue(words(3, "immediate_fixed", True, four, 0).startswith("Population limit: 256 (Immediate"))
        self.assertNotIn(", so ", words(3, "stock", False, four, None))

    def test_new_believers_two_sets(self):
        sets = [("the first set", 24, 24), ("the second set", 3, 24)]
        text = words(5, "collection_progression", True, sets)
        self.assertTrue(text.startswith("Population limit: 246 (Collection Progression Max Pop with 256 Villagers: 241 "
                                        "plus the collection bonus, 256 at most). In this mode the check counts every "
                                        "villager record in use, Heathens and bodies not yet buried included"))
        self.assertIn("90, plus 5 for each complete collectible set, 15 with both; this village has 1 complete (the "
                      "first set 24, the second set 3 of 24), so 95.", text)
        self.assertIn("this village has both complete", words(5, "stock", False, [("a", 24, 24), ("b", 24, 24)]))
        self.assertTrue(words(5, "stock", False, [("a", 24, 24), ("b", 24, 24)]).startswith("Population limit: 105 ("))
        self.assertTrue(words(5, "immediate_fixed", False, sets).startswith("Population limit: 150 (Immediate"))

    def test_the_lost_children_and_a_new_home(self):
        sets = [("Butterflies", 12, 12), ("Shells", 12, 12), ("Beetles", 12, 12), ("Pebbles", 11, 12)]
        self.assertTrue(words(2, "collection_progression", False, sets).startswith(
            "Population limit: 246 (Collection Progression Max Pop: 231 plus the collection bonus, 256 at most)"))
        self.assertTrue(words(2, "immediate_fixed", False, sets).startswith("Population limit: 256 (Immediate"))
        self.assertIn("this village has 3 complete (Butterflies 12, Shells 12, Beetles 12, Pebbles 11 of 12), so 105.",
                      words(2, "stock", False, sets))
        huts = "In every mode babies also need room in the huts."
        self.assertEqual(words(1, life.EITHER, False, [], extra=huts),
                         "Population limit: 256 (Collection Progression or Immediate Fixed Max Pop, which are the same "
                         "in A New Home). In the normal game it would be 90 (A New Home has no collections). " + huts)
        self.assertEqual(words(1, "stock", False, []),
                         "Population limit: 90 (the normal game's; this game's exe does not change it; A New Home has "
                         "no collections).")

    def test_the_general_page_gives_the_rule(self):
        text, ok = life.limit_words(village(4, general=True), None)
        self.assertEqual(text, "Population limit: in the normal game 90, plus 5 for each complete collection, 25 with "
                               "all four")
        self.assertEqual(ok, gm.CODE)

    def test_room_words(self):
        with mock.patch.object(life, "population_mode", return_value=("immediate_fixed", True)):
            self.assertEqual(life.room_words(village(4)), "In this game's exe (Immediate Fixed Max Pop with 256 "
                             "Villagers) the limit is instead 256; the huts are the same as in the normal game.")
        with mock.patch.object(life, "population_mode", return_value=("collection_progression", False)):
            self.assertIn("the limit is instead 135 plus the same collection bonus, 150 at most; the check then counts "
                          "every villager record in use", life.room_words(village(5)))
        for mode in ("stock", None):
            with mock.patch.object(life, "population_mode", return_value=(mode, True)):
                self.assertIsNone(life.room_words(village(4)))


@unittest.skipUnless(STOCK[4].is_file(), STOCK_ABSENT)
class ThePage(unittest.TestCase):
    """A Tree of Life save read with a rendered 256 Villagers exe in Immediate Fixed: the page says 256."""

    def test_vital_statistics_and_island_events(self):
        root = Path(tempfile.mkdtemp(prefix="gpl"))
        self.addCleanup(shutil.rmtree, root, True)
        name = "Virtual Villagers - The Tree of Life - Modded 256"
        folder, game = root / "saves" / name, root / "game"
        folder.mkdir(parents=True)
        game.mkdir()
        save = ROOT / "tests" / "fixtures" / "rename_tribe" / "vv4-huttest-1.ldw.gz"
        data = bytearray(gzip.decompress(save.read_bytes()))
        import struct
        struct.pack_into("<48i", data, life.COLLECTIBLES_AT[4], *([1] * 8 + [0] * 4 + [1] * 12 + [0] * 24))
        (folder / "Virtual Villagers - The Tree of Life1.ldw").write_bytes(bytes(data))
        exe = game / f"{name}.exe"
        exe.write_bytes(rendered(4, "immediate_fixed", "256"))
        facts = gm.read(folder, 4, 1, game_folders=[game], now=NOW, exe=exe)
        limit = next(f for f in facts if f.text.startswith("Population limit:"))
        self.assertEqual(limit.text, "Population limit: 256 (Immediate Fixed Max Pop with 256 Villagers). In the normal "
                                     "game it would be 90, plus 5 for each complete collection, 25 with all four; this "
                                     "village has 1 complete (Fish Scale 8, Lab Equipment 12, Mausoleum Mural 0, Wind "
                                     "Flute 0 of 12), so 95.")
        self.assertTrue(limit.confirmed)
        room = [f.text for f in facts if f.group == "Island events"]
        at = next(n for n, t in enumerate(room) if t.startswith("Room for new villagers"))
        self.assertEqual(room[at + 1], "In this game's exe (Immediate Fixed Max Pop with 256 Villagers) the limit is "
                                       "instead 256; the huts are the same as in the normal game.")


if __name__ == "__main__":
    unittest.main()
