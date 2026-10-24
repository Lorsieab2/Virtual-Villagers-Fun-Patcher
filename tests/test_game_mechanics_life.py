"""Game Mechanics' Vital statistics, Nursing and pregnancy, Villager timers and Village timers, all five games
(src/vv_game_mechanics_life.py and each game's module).

Every case starts from a committed real save (tests/fixtures/rename_tribe) and writes the fields under test into a
copy at the offsets the module reads (pregnancy, babies, sickness, age, faction, difficulty), so each line is
checked against values the test chose.
"""
from __future__ import annotations

import gzip
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_life as life  # noqa: E402
import vv_last_names as ln  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
NOW = 1_790_000_000 + 3_000_000
SAVES = {1: "vv1-huttest-1", 2: "vv2-huttest-1", 3: "vv3-huttest-1", 4: "vv4-huttest-1", 5: "vv5-256-1"}


def fixture(game: int, name: str | None = None) -> bytearray:
    return bytearray(gzip.decompress((FIXTURES / f"{name or SAVES[game]}.ldw.gz").read_bytes()))


def entries(game: int, data: bytes) -> list[int]:
    return ln._entries(game, bytes(data))


def put(data: bytearray, at: int, value: int, byte: bool = False) -> None:
    if byte:
        data[at] = value
    else:
        struct.pack_into("<i", data, at, value)


def carry(game: int, data: bytearray, n: int, units_left: int, babies: int, lag: int = 0) -> str:
    """Make villager n (in the game's own order) a mother `units_left` age units from her babies' birth, the only
    one carrying."""
    lay = life.LAYOUTS[game]
    for other in entries(game, data):
        put(data, other + lay.conceived, 0)
    at = entries(game, data)[n]
    age = struct.unpack_from("<i", data, at + lay.age)[0]
    put(data, at + lay.processed, age - lag)
    put(data, at + lay.conceived, age - lag - life.BIRTH_UNITS + units_left)
    put(data, at + lay.babies, (0 if babies == 1 else babies) if lay.singles_unwritten else babies)
    put(data, at + {1: -0x20, 2: -0x2C}.get(game, -0x0C), 2 if game <= 2 else 1)      # a woman
    return ln._cstr(data, at, 0x18)


def page(test: unittest.TestCase, game: int, data: bytes, now: float = NOW, extra=None) -> list[gm.Fact]:
    import vv_tribe_rename
    base = next(item.base for item in vv_tribe_rename.GAMES if item.number == game)
    root = Path(tempfile.mkdtemp(prefix="gml"))
    test.addCleanup(shutil.rmtree, root, True)
    folder = root / base
    folder.mkdir()
    (folder / f"{base}1.ldw").write_bytes(bytes(data))
    if extra is not None:
        extra(folder)
    return gm.read(folder, game, 1, [], now=now)


def group(facts: list[gm.Fact], name: str) -> list[gm.Fact]:
    return [f for f in facts if f.group == name]


def texts(facts: list[gm.Fact], name: str) -> str:
    return "\n".join(f.text for f in group(facts, name))


class Order(unittest.TestCase):
    def test_vital_statistics_comes_first_in_every_game(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                facts = page(self, game, fixture(game))
                self.assertEqual(facts[0].group, life.VITALS)
                names = [f.group for f in facts]
                for g in (life.VITALS, gm.SOURCES, life.NURSING, life.VILLAGER_TIMERS, life.VILLAGE_TIMERS):
                    self.assertIn(g, names)
                self.assertLess(names.index(gm.SOURCES), names.index(life.NURSING))
                order = [gm.GROUPS.index(f.group) for f in facts]
                self.assertEqual(order, sorted(order))
                self.assertLessEqual(len([f for f in group(facts, life.VITALS) if not f.sub]), 15)

    def test_the_general_page_shows_none_of_it(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                groups = {f.group for f in gm.general(game, now=NOW)}
                self.assertFalse(groups & {life.VITALS, life.NURSING, life.VILLAGER_TIMERS, life.VILLAGE_TIMERS})

    def test_fact_due_is_optional(self) -> None:
        fact = gm.Fact("Other", "x")
        self.assertIsNone(fact.due)
        self.assertIsNone(fact.due_kind)


class Nursing(unittest.TestCase):
    def test_every_game_names_the_mother_and_her_babies(self) -> None:
        for game in range(1, 6):
            for babies, word in ((1, "1 baby"), (2, "twins"), (3, "triplets")):
                with self.subTest(game=game, babies=babies):
                    data = fixture(game)
                    _unpause(game, data)
                    name = carry(game, data, 0, 10, babies)
                    facts = page(self, game, data)
                    line = next(f for f in group(facts, life.NURSING) if f.text.startswith(name))
                    self.assertIn(f"{word}; 10 age units to go, born", line.text)
                    self.assertIsNotNone(line.due)
                    self.assertEqual(line.due_kind, "due")
                    soonest = next(f for f in group(facts, life.VITALS) if f.text.startswith("Soonest birth:"))
                    self.assertIn(name, soonest.text)

    def test_the_birth_moment_counts_from_the_last_save(self) -> None:
        """Unpaused, within the time away counted in full: the moment is the save's last moment plus the units."""
        import vv_game_mechanics_vv4 as vv4
        data = fixture(4)
        _unpause(4, data)
        struct.pack_into("<i", data, vv4.SPEED, 6)
        name = carry(4, data, 1, 20, 1)
        last = struct.unpack_from("<q", data, 8)[0] + struct.unpack_from("<i", data, vv4.LAST_TICK)[0]
        facts = page(self, 4, data, now=last + 60)
        line = next(f for f in group(facts, life.NURSING) if f.text.startswith(name))
        self.assertEqual(line.due, last + 20 * 360)

    def test_details_screen_minutes(self) -> None:
        for game, extra in ((1, 40), (3, 41), (4, 41), (5, 41)):
            with self.subTest(game=game):
                data = fixture(game)
                _unpause(game, data)
                carry(game, data, 0, 10, 1)
                speed = gm.speed_base(_speed(game, data))
                facts = page(self, game, data)
                shown = next(f for f in group(facts, life.NURSING) if "Nursing for:" in f.text)
                self.assertIn(f'"Nursing for: {(10 + extra - 41) * speed} min"', shown.text)
                self.assertTrue(shown.sub)

    def test_a_mother_counts_as_two_for_food_and_her_babies_in_the_population(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                data = fixture(game)
                _unpause(game, data)
                for other in entries(game, data):              # nobody carrying first
                    put(data, other + life.LAYOUTS[game].conceived, 0)
                before = page(self, game, bytes(data))
                carry(game, data, 0, 5, 3)
                after = page(self, game, data)
                count = lambda facts, start: next(f.text for f in group(facts, life.VITALS)  # noqa: E731
                                                  if f.text.startswith(start))
                pop_before = int(count(before, "Population for food: ").split()[3])
                pop_after = int(count(after, "Population for food: ").split()[3])
                self.assertEqual(pop_after, pop_before + 1)
                self.assertIn("3 babies on the way", count(after, "Population: "))

    def test_nobody_carrying(self) -> None:
        data = fixture(3)
        facts = page(self, 3, data)
        self.assertIn("Nobody is carrying a baby now.", texts(facts, life.NURSING))
        self.assertIn("Soonest birth: nobody is carrying a baby.", texts(facts, life.VITALS))


class Timers(unittest.TestCase):
    def test_children_grow_up(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                data = fixture(game)
                _unpause(game, data)
                at = entries(game, data)[0]
                lay = life.LAYOUTS[game]
                put(data, at + lay.age, 14 * 20 - 3)
                put(data, at + lay.processed, 14 * 20 - 3)
                name = ln._cstr(data, at, 0x18)
                facts = page(self, game, data)
                line = next(f for f in group(facts, life.VILLAGER_TIMERS) if f.text.startswith(name + ", 13"))
                self.assertIn("turns 14", line.text)
                self.assertTrue(line.sub)

    def test_the_sick_are_listed_with_their_health(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                data = fixture(game)
                at = entries(game, data)[0]
                lay = life.LAYOUTS[game]
                put(data, at + lay.sick, 1, lay.sick_byte)
                put(data, at + lay.health, 33)
                name = ln._cstr(data, at, 0x18)
                facts = page(self, game, data)
                line = next(f for f in group(facts, life.VILLAGER_TIMERS) if f.text.startswith(name + ": 33 health"))
                self.assertIn("(an estimate)", line.text)

    def test_the_golden_child(self) -> None:
        data = fixture(1)
        at = entries(1, data)[0]
        put(data, at + life.VV1_FAMILY, life.GOLDEN_FAMILY)
        name = ln._cstr(data, at, 0x18)
        facts = page(self, 1, data)
        self.assertIn(f"{name} is the Golden Child: always 5 years old", texts(facts, life.VILLAGER_TIMERS))
        self.assertIn("the Golden Child never eats", texts(facts, life.VITALS))

    def test_the_next_natural_island_event_has_a_countdown(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                data = fixture(game)
                _unpause(game, data)
                facts = page(self, game, data)
                line = next(f for f in group(facts, life.VILLAGE_TIMERS) if f.text.startswith("Next natural island event:"))
                self.assertEqual(line.due_kind, "next")
                rule = next(f for f in facts if f.text.startswith("Next island event:"))
                self.assertEqual(rule.due, line.due)

    def queued(self, *, same_village: bool, bought_after_save: bool) -> list[gm.Fact]:
        """The Secret City's page with a Pick Island Event in the patcher's queued purchases file, its roster
        this village's or another's, bought before or after the save was last written."""
        import os
        data = fixture(3)

        def queue(folder: Path) -> None:
            path = folder / "Virtual Villagers Fun Patcher Data" / "Paid Purchases"
            path.mkdir(parents=True)
            body = bytearray(life.STORY_WHEN + 64)
            struct.pack_into("<4I", body, 0, life.STORY_MAGIC, 1, 3, 1)
            roster = [life.title_identity(3, bytes(data), at) for at in ln._entries(3, bytes(data), bodies=True)]
            if not same_village:
                roster = [(v * 7 + 1) & 0xFFFFFFFF or 1 for v in roster]
            struct.pack_into(f"<{len(roster)}I", body, life.STORY_ROSTER, *roster)
            struct.pack_into("<I", body, life.STORY_HAVE, life.SQ_PICK)
            save = folder / next(p.name for p in folder.glob("*.ldw"))
            os.utime(save, (1_790_000_000, 1_790_000_000))
            bought = 1_790_000_000 + (600 if bought_after_save else -600)
            struct.pack_into("<Q", body, life.STORY_WHEN, (bought + life.FILETIME_UNIX) * 10_000_000)
            (path / "Virtual Villagers 3 Story Purchases - Save 1.dat").write_bytes(bytes(body))
        return page(self, 3, data, extra=queue)

    def test_a_valid_queued_purchased_event_only_delays_the_natural_one(self) -> None:
        facts = self.queued(same_village=True, bought_after_save=False)
        timers = texts(facts, life.VILLAGE_TIMERS)
        self.assertIn("A purchased island event is pending and delays the natural one", timers)
        self.assertNotIn("Next natural island event:", timers)
        self.assertNotIn("Pick", timers)                       # never listed
        self.assertIn("Next natural island event: after a pending purchased event", texts(facts, life.VITALS))

    def test_another_villages_or_an_unpaid_purchase_does_not_count(self) -> None:
        for same, after in ((False, False), (True, True)):
            with self.subTest(same_village=same, bought_after_save=after):
                facts = self.queued(same_village=same, bought_after_save=after)
                timers = texts(facts, life.VILLAGE_TIMERS)
                self.assertNotIn("purchased island event is pending", timers)
                line = next(f for f in group(facts, life.VILLAGE_TIMERS)
                            if f.text.startswith("Next natural island event:"))
                self.assertNotIn("purchased", line.text)

    def test_the_soonest_birth_counts_the_catch_up(self) -> None:
        """10 units left with no time away to work off comes after 15 left of which 20 are already counted (worked
        off in about 30 seconds of catch-up)."""
        import vv_game_mechanics_vv4 as vv4
        data = fixture(4)
        struct.pack_into("<i", data, vv4.SPEED, 6)
        lay = life.LAYOUTS[4]
        first, second = entries(4, data)[:2]
        for other in entries(4, data):
            put(data, other + lay.conceived, 0)
        for at, left, lag in ((first, 10, 0), (second, 15, 20)):
            age = struct.unpack_from("<i", data, at + lay.age)[0]
            put(data, at + lay.processed, age - lag)
            put(data, at + lay.conceived, age - lag - life.BIRTH_UNITS + left)
            put(data, at + lay.babies, 1)
            put(data, at - 0x0C, 1)
        last = struct.unpack_from("<q", data, 8)[0] + struct.unpack_from("<i", data, vv4.LAST_TICK)[0]
        facts = page(self, 4, data, now=last + 1)
        later = ln._cstr(data, second, 0x18)
        soonest = next(f for f in group(facts, life.VITALS) if f.text.startswith("Soonest birth:"))
        self.assertIn(later, soonest.text)
        self.assertIn("while the village catches up", soonest.text)
        mothers = [f.text for f in group(facts, life.NURSING) if " age units to go" in f.text]
        self.assertTrue(mothers[0].startswith(later))

    def test_puzzles_under_way(self) -> None:
        import vv_game_mechanics_vv3 as vv3
        data = fixture(3)
        struct.pack_into("<i", data, 12 + vv3.PUZZLES + 4 + 8 * 6, 900)          # The Ruins, 900 of 1800
        facts = page(self, 3, data)
        self.assertIn("The Ruins 900 of 1800", texts(facts, life.VILLAGE_TIMERS))


class Vitals(unittest.TestCase):
    def test_difficulty_is_read_and_used(self) -> None:
        for game in range(1, 6):
            for level, name, per_unit in ((0, "Easy", "2"), (2, "Hard", "3.52")):
                with self.subTest(game=game, level=level):
                    data = fixture(game)
                    struct.pack_into("<i", data, life.DIFFICULTY_AT[game], level)
                    facts = page(self, game, data)
                    vitals = texts(facts, life.VITALS)
                    self.assertIn(f"difficulty {name};", vitals)
                    self.assertIn(f"That is {per_unit} food a villager each age unit now", vitals)

    def test_medium_eats_more_only_above_its_threshold(self) -> None:
        import vv_game_mechanics_vv4 as vv4
        data = fixture(4)
        struct.pack_into("<i", data, life.DIFFICULTY_AT[4], 1)
        for food, per_unit in ((7_999, "2"), (8_000, "3.52")):
            with self.subTest(food=food):
                struct.pack_into("<i", data, vv4.FOOD, food)
                self.assertIn(f"That is {per_unit} food a villager", texts(page(self, 4, data), life.VITALS))

    def test_estimates_are_marked(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                facts = page(self, game, fixture(game))
                head = next(f for f in group(facts, life.VITALS) if f.text.startswith("Food estimates"))
                self.assertIn("estimates, not the game's own figures", head.text)
                self.assertFalse(head.confirmed)
                for start in ("Food eaten:", "Sustainable population", "Storage alone lasts",
                              "Food needed for 100% health over 8 hours", "Food needed for 100% health over 24 hours"):
                    line = next(f for f in group(facts, life.VITALS) if f.text.startswith(start))
                    self.assertTrue(line.sub)
                    self.assertFalse(line.confirmed, start)

    def test_speed_difficulty_and_time_away_are_named(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                first = page(self, game, fixture(game))[0]
                self.assertRegex(first.text, r"^Speed (Fast|Normal|Slow)")
                self.assertIn("difficulty", first.text)
                self.assertIn("would count if it were played now", first.text)

    def test_closed_game_estimates(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                data = fixture(game)
                _unpause(game, data)
                vitals = texts(page(self, game, data), life.VITALS)
                self.assertIn("Closed for 8 hours:", vitals)
                self.assertIn("Closed for 24 hours:", vitals)

    def test_the_tree_of_life_sets(self) -> None:
        data = fixture(4)
        at = life.COLLECTIBLES_AT[4]
        struct.pack_into("<48i", data, at, *([2] * 12 + [1] * 12 + [0] * 24))
        vitals = texts(page(self, 4, data), life.VITALS)
        self.assertIn("Collectibles: 24 of 48 pieces owned; 36 found in all, 12 of them duplicates", vitals)
        self.assertIn("Fish Scale 12 of 12 (12 duplicates); Lab Equipment 12 of 12 (0 duplicates); Mausoleum Mural 0 "
                      "of 12", vitals)
        self.assertIn("The limit is 100: 90 plus 10 for collections", vitals)

    def test_golden_mushroom_only_with_its_patch(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                vitals = texts(page(self, game, fixture(game)), life.VITALS).lower()
                self.assertNotIn("golden mushroom", vitals)
                self.assertNotIn("1,000,000", vitals)


class Heathens(unittest.TestCase):
    """New Believers: Heathens count only when they are in the tribe (faction byte 0)."""

    def test_heathens_outside_the_tribe_are_left_out_and_labelled(self) -> None:
        data = fixture(5, "vv5-huttest-1")
        everyone = life.people(gm.Village(Path("."), 5, 1, Path("x"), bytes(data), None, NOW))
        outside = [p for p in everyone if p.heathen]
        self.assertTrue(outside)
        facts = page(self, 5, data)
        vitals = texts(facts, life.VITALS)
        members = len(everyone) - len(outside)
        self.assertIn(f"Population: {members} villager", vitals)
        self.assertIn(f"Heathens outside the tribe: {len(outside)}, left out of every count", vitals)
        self.assertIn("Heathens outside the tribe never eat", vitals)

    def test_a_heathen_in_the_tribe_counts(self) -> None:
        data = fixture(5, "vv5-huttest-1")
        first = entries(5, data)[0]
        before = texts(page(self, 5, bytes(data)), life.VITALS)
        data[first + life.VV5_FACTION] = 0                      # converted: in the tribe
        after = texts(page(self, 5, data), life.VITALS)
        number = lambda text: int(text.split("Population: ")[1].split()[0])  # noqa: E731
        self.assertEqual(number(after), number(before) + 1)

    def test_an_outside_mother_is_not_counted(self) -> None:
        data = fixture(5, "vv5-huttest-1")
        _unpause(5, data)
        name = carry(5, data, 0, 5, 2)
        facts = page(self, 5, data)
        self.assertFalse(any(f.text.startswith(name) for f in group(facts, life.NURSING)))
        self.assertIn("Outside the tribe (Heathens, not counted): 1 carrying.", texts(facts, life.NURSING))
        self.assertNotIn("babies on the way", texts(facts, life.VITALS))


def _speed(game: int, data: bytes) -> int:
    import vv_save_backup
    return vv_save_backup.save_speed(game, bytes(data))[1]


def _unpause(game: int, data: bytearray) -> None:
    import vv_save_backup
    at, value = vv_save_backup.save_speed(game, bytes(data))
    if value >= gm.PAUSED:
        struct.pack_into("<i", data, at, value - gm.PAUSED)


if __name__ == "__main__":
    unittest.main()
