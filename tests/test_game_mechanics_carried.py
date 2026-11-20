"""Game Mechanics' "Babies being carried" group, all five games (src/vv_game_mechanics_carried.py; the owner,
2026-11-18: what the babies a pregnant villager carries count toward).

  * The stock exes: every call to each game's population counter and room check is exactly the list the module
    documents (so no caller is left out), and each counter adds the carried babies -- emulated on a made-up table.
  * The page: the group is on every game's page and general page, with the facts pinned per game, each confirmed
    from the game's code except the lines marked UNCONFIRMED or DEAD.
  * The live line: "N villagers + M babies being carried = P on the population counter" and each mother with her
    babies, on real fixture saves with a pregnant villager (one baby, twins, triplets) and with nobody carrying.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_carried as carried  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import test_game_mechanics_life as t  # noqa: E402

NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
STOCK = {g: ROOT / "research" / "stock-executables" / f"Virtual Villagers - {n}.exe" for g, n in NAMES.items()}
STOCK_ABSENT = "stock executables are not in the release source archive"


def image(game: int) -> tuple[bytes, int, list[tuple[int, int, int, int]]]:
    """(exe bytes, image base, [(rva, size, raw, raw size)]) of the executable sections."""
    data = STOCK[game].read_bytes()
    base, sections = life._sections(data)
    return data, base, [(rva, vsize, raw, rsize) for name, rva, vsize, raw, rsize in sections]


def branches_to(game: int, target: int) -> set[int]:
    """Every E8 (call) / E9 (jmp) rel32 in the stock exe's code that lands on `target`."""
    data, base, sections = image(game)
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    table = pe + 24 + struct.unpack_from("<H", data, pe + 20)[0]
    out = set()
    for n in range(count):
        flags = struct.unpack_from("<I", data, table + 40 * n + 36)[0]
        if not flags & 0x20000000:                      # executable sections only
            continue
        rva, vsize, raw, rsize = sections[n]
        for at in range(raw, raw + min(vsize, rsize) - 4):
            if data[at] in (0xE8, 0xE9):
                va = base + rva + at - raw
                if va + 5 + struct.unpack_from("<i", data, at + 1)[0] == target:
                    out.add(va)
    return out


@unittest.skipUnless(all(p.is_file() for p in STOCK.values()), STOCK_ABSENT)
class StockCode(unittest.TestCase):
    def test_every_counter_caller_is_listed(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertEqual(branches_to(game, carried.COUNTER[game]), set(carried.COUNTER_SITES[game]))

    def test_every_room_check_caller_is_listed(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertEqual(branches_to(game, carried.ROOM_CHECK[game]), set(carried.ROOM_SITES[game]))

    def test_each_room_check_asks_the_counter_first(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                start = carried.ROOM_CHECK[game]
                first = min(s for s in carried.COUNTER_SITES[game] if s > start)
                self.assertLess(first - start, 0x20)

    # The first record's step of each counter: +1 for the living villager, then, while it carries (its conceived
    # field is not 0), its babies -- VV1/VV2 +1 and one more for a litter of 2 or two more for 3 (a 0 there is one
    # baby), VV3-VV5 the litter field added; VV5 skips a Heathen (cmp byte [esi], 0 on the faction +0x1CEC).
    LITTER = {
        1: ("8b5114 85d2 7414 8b5118 40 83fa02 7503 40 eb08 83fa03 7503 83c002",),
        2: ("8b9110050000 85d2 7417 8b9114050000 40 83fa02 7503 40 eb08 83fa03 7503 83c002",),
        3: ("40 85db 7403 034118",),
        4: ("83c001 83798500 7403 034189",),
        5: ("803e00 751b", "83c701 83be60ffffff00 7406 03be64ffffff"),
    }

    def test_the_counters_add_the_carried_babies(self) -> None:
        for game, needles in self.LITTER.items():
            with self.subTest(game=game):
                data, base, sections = image(game)
                rva = carried.COUNTER[game] - base
                raw = next(r + rva - s for s, size, r, _ in sections if s <= rva < s + size)
                body = data[raw:raw + 0x60]
                for needle in needles:
                    self.assertIn(bytes.fromhex(needle.replace(" ", "")), body)


def facts_of(game: int, data=None) -> list[gm.Fact]:
    case = unittest.TestCase()
    try:
        return [f for f in t.page(case, game, t.fixture(game) if data is None else data) if f.group == gm.CARRIED]
    finally:
        case.doCleanups()


def general(game: int) -> list[gm.Fact]:
    return [f for f in gm.general(game, now=t.NOW) if f.group == gm.CARRIED]


PINNED = {
    1: ("at 15, 25 and 50 the first, second and third hut", "second hut's site appears once the count reaches 15",
        "only above 22 and the third above 45", "strength n is the count divided by 3",
        "Isola Day Celebration: the stored food loses 10 for every person counted, carried babies included",
        "The Mysterious Face's newcomer"),
    2: ("90 plus 5 for each complete children's collection", "second hut's site appears once the count reaches 21",
        "The Silver Mirror needs a count of 2 or more, and A Dangerous Mission more than 60",
        "two-choice events x2 above 25 and x3 above 50", "both Blessings Day Celebrations",
        "The Barrel O' Babies, Old Friends and The Savage Child"),
    3: ("plus 10 at Magic level 3", "at 10, 17 and 35", "Rescue: when the count is below 3",
        "leave out pregnant women of 18 to 49 and everyone of 14 to 17",
        "counts no carried babies (as the game's own Blessings Day)"),
    4: ("at 10, 17 and 35", "\"A Grandiose Feast\"", "\"Crowd Control\" (100)", "Prolific Procreation",
        "Daredevil Barrel...of Babies!", "There isn't enough housing to support more population!"),
    5: ("believers and the babies they carry", "5 x (the count + 2)", "fewer than 12 counted",
        "neither are the babies a Heathen mother carries", "Chutes Without Ladders",
        "in New Believers those modes count every villager record in use"),
}
EVERY_GAME = ("In short: each baby being carried counts as 1 on the game's population counter",
              "The population number on the game's screen", "Eating: only villagers are fed",
              "Highest Population", "A newborn's sex: while the count is 6 or fewer",
              "The patcher's birth guard")


class Page(unittest.TestCase):
    def test_every_game_pins_its_facts_on_the_page_and_the_general_page(self) -> None:
        for game in range(1, 6):
            for where, lines in (("page", facts_of(game)), ("general", general(game))):
                with self.subTest(game=game, where=where):
                    text = "\n".join(f.text for f in lines)
                    for words in EVERY_GAME + PINNED[game]:
                        self.assertIn(words, text)

    def test_the_group_follows_nursing_and_pregnancy(self) -> None:
        self.assertEqual(gm.GROUPS.index(gm.CARRIED), gm.GROUPS.index(life.NURSING) + 1)

    def test_labels(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                lines = general(game)
                unconfirmed = [f.text for f in lines if not f.confirmed]
                dead = [f.text for f in lines if f.text.startswith(carried.DEAD)]
                if game == 3:
                    self.assertEqual(len(dead), 1)
                    self.assertIn("trial-version limit", dead[0])
                    self.assertTrue(all(f.confirmed for f in lines if f.text in dead))
                else:
                    self.assertEqual(dead, [])
                expected = {1: 1, 2: 1, 3: 0, 4: 2, 5: 1}[game]       # the trial limit, the pregnant newcomer
                self.assertEqual(len(unconfirmed), expected, unconfirmed)
                self.assertNotIn("0x", "\n".join(f.text for f in lines))  # no exe addresses visible

    def test_vv4_highest_population_is_the_owners_sighting(self) -> None:
        line = next(f for f in general(4) if f.text.startswith("Highest Population 6 with 5 villagers"))
        self.assertEqual(line.verified, gm.OWNER)

    def test_a_patch_known_out_of_the_game_is_left_out(self) -> None:
        village = gm.Village(Path("."), 1, 1, Path("1.ldw"), b"", frozenset(), t.NOW)
        text = "\n".join(line for line, _ in carried.patch_lines(village))
        self.assertNotIn("Builders Fix Huts", text)
        village = gm.Village(Path("."), 1, 1, Path("1.ldw"), b"", frozenset({"vv1_builders_fix_huts"}), t.NOW)
        text = "\n".join(line for line, _ in carried.patch_lines(village))
        self.assertIn("With the patcher's \"Builders Fix Huts When Idle\": idle builders start", text)


class Live(unittest.TestCase):
    def test_villagers_plus_carried_babies_equal_the_counter(self) -> None:
        for game in range(1, 6):
            for babies, word in ((1, "1 baby"), (2, "twins"), (3, "triplets")):
                with self.subTest(game=game, babies=babies):
                    data = t.fixture(game)
                    name = t.carry(game, data, 0, 10, babies)
                    members = life.tribe(life.people(_village(game, data)))
                    lines = facts_of(game, data)
                    who = "believers" if game == 5 else "villagers"
                    plural = "y" if babies == 1 else "ies"
                    head = (f"This village now: {len(members)} {who} + {babies} bab{plural} being carried = "
                            f"{len(members) + babies} on the population counter.")
                    line = next(f for f in lines if f.text.startswith("This village now:"))
                    self.assertEqual(line.text, head)
                    self.assertEqual(line.verified, gm.SAVE)
                    mother = next(f for f in lines if f.text == f"{name}: {word}.")
                    self.assertTrue(mother.sub)
                    self.assertEqual(life.claim_template(mother.text), f"<villager>: {word}.")

    def test_nobody_carrying(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                data = t.fixture(game)
                lay = life.LAYOUTS[game]
                for at in t.entries(game, data):
                    t.put(data, at + lay.conceived, 0)
                line = next(f.text for f in facts_of(game, data) if f.text.startswith("This village now:"))
                self.assertIn("+ 0 babies being carried", line)

    def test_a_heathen_mothers_babies_are_outside_the_count(self) -> None:
        data = t.fixture(5)
        name = t.carry(5, data, 0, 10, 2)
        at = t.entries(5, data)[0]
        data[at + life.VV5_FACTION] = 1
        lines = facts_of(5, data)
        line = next(f.text for f in lines if f.text.startswith("This village now:"))
        self.assertIn("+ 0 babies being carried", line)
        self.assertFalse(any(f.text == f"{name}: twins." for f in lines))
        self.assertIn("Heathen mothers outside the count: 1, carrying 2.", [f.text for f in lines])


def _village(game: int, data) -> gm.Village:
    return gm.Village(Path("."), game, 1, Path(f"{game}.ldw"), bytes(data), None, t.NOW)


if __name__ == "__main__":
    unittest.main()
