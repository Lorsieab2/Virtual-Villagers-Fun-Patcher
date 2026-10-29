"""The Family Tree's people are never tied by name and looks alone (the identity audit).

A Birth record names its child by name, head and body, and the Family Tree Maker's registry keyed
every person by exactly that: a villager born with the name and looks of one who had died (heads are
inherited in The Lost Children to New Believers, names come from fixed pools) became the SAME
person -- the dead villager's parents on the living one, one person where there were two, and the
Death record on nobody.  Each Birth record is its own villager; the living one is the Birth whose
parents are the ones the save keeps on her record, and the Death record is the other one's.  Where
that cannot be told, nothing is guessed: both stay apart, unattached, and the notes say so.

Fixtures are built here (tests/test_last_names_rename.py's save layout); nothing outside is read.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_genealogy as gen  # noqa: E402
from test_last_names_rename import DATA, LOGS, TABLE, entry  # noqa: E402

VILLAGE = "Village: Tribe (Save 1)\n"


def birth(child: str, head: int, body: int, mother: tuple, father: tuple) -> str:
    return (f"Birth\n  Child: {child}\n    Head: {head}\n    Body: {body}\n"
            f"  Mother: {mother[0]}\n    Head: {mother[1]}\n    Body: {mother[2]}\n"
            f"  Father: {father[0]}\n    Head: {father[1]}\n    Body: {father[2]}\n\n")


class DeadNamesakeAndNewborn(unittest.TestCase):
    def build(self, living_parents: tuple, second_parents: tuple) -> Path:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        people = [
            entry("Ma2", 1, 7, 4, 4), entry("Pa2", 0, 7, 2, 2),
            entry("Gata", 1, 7, 3, 5, father=living_parents[1], mother=living_parents[0]),
        ]
        (folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            bytes(bytearray(b"ldwg" + bytes(TABLE - 4)) + b"".join(people) + bytes(64)))
        (folder / DATA).mkdir(parents=True)
        births = folder / LOGS / "Births and Conceptions" / "Virtual Villagers 3 Births and Conceptions Log 1.txt"
        births.parent.mkdir(parents=True)
        births.write_bytes((VILLAGE + birth("Gata", 3, 5, ("Ma1", 4, 6), ("Pa1", 1, 1))
                            + birth("Gata", 3, 5, *second_parents)).replace("\n", "\r\n").encode("latin-1"))
        deaths = folder / LOGS / "Deaths" / "Virtual Villagers 3 Deaths Log 1.txt"
        deaths.parent.mkdir(parents=True)
        deaths.write_bytes((VILLAGE + "Death 1\n  Name: Gata\n  Age at death: 900\n  Sex: Female\n"
                            "  Head: 3\n  Body: 5\n\n").replace("\n", "\r\n").encode("latin-1"))
        return folder

    def gatas(self, village: gen.Village) -> list:
        return [p for p in village.people.values() if p.name == "Gata"]

    def name_of(self, village: gen.Village, pid) -> str | None:
        return village.people[pid].name if pid is not None else None

    def test_a_newborn_with_a_dead_namesakes_name_and_looks_is_another_villager(self):
        folder = self.build((("Ma2", 4, 4), ("Pa2", 2, 2)), (("Ma2", 4, 4), ("Pa2", 2, 2)))
        village = gen.load_village(folder, 3, 1)
        gatas = self.gatas(village)
        self.assertEqual(len(gatas), 2, "two villagers named Gata with one look: two people")
        living = [p for p in gatas if p.alive]
        dead = [p for p in gatas if not p.alive]
        self.assertEqual(len(living), 1)
        self.assertEqual((self.name_of(village, living[0].mother), self.name_of(village, living[0].father)),
                         ("Ma2", "Pa2"), "the living Gata is the Birth whose parents her record keeps")
        self.assertEqual(dead[0].gone, "died", "the Death record is the dead namesake's")
        self.assertEqual((self.name_of(village, dead[0].mother), self.name_of(village, dead[0].father)),
                         ("Ma1", "Pa1"), "the dead Gata keeps her own parents")

    def test_two_births_her_record_cannot_tell_apart_are_never_guessed(self):
        # The save's own parents match neither Birth: which Birth is hers is not known.
        folder = self.build((("Ma3", 8, 8), ("Pa3", 9, 9)), (("Ma2", 4, 4), ("Pa2", 2, 2)))
        village = gen.load_village(folder, 3, 1)
        gatas = self.gatas(village)
        self.assertEqual(len(gatas), 2, "still two people, never merged")
        living = next(p for p in gatas if p.alive)
        dead = next(p for p in gatas if not p.alive)
        self.assertEqual((self.name_of(village, living.mother), self.name_of(village, living.father)),
                         ("Ma3", "Pa3"), "the living Gata keeps the parents her record keeps, no Birth's")
        self.assertIsNone(living.birth_record, "no Birth record is guessed to be hers")
        self.assertEqual((dead.gone, dead.mother, dead.father, dead.birth_record), ("died", None, None, None),
                         "the dead Gata has her Death record, and no Birth's parents are guessed to be hers")
        self.assertTrue(any("Gata" in n and "Birth" in n for n in village.notes), "and the notes say so")


class LivingNamesakesAndTheirBirths(unittest.TestCase):
    """Codex, PR #653: two living "Tomil Kalama" (one name and look) and Births of that name and look no living
    one is told by (the save keeps other parents): each living one stands for one of those Births, so only the
    Births beyond them are villagers of their own -- 2 living and 3 Births make 3 people, never 5."""

    def tomils(self, births: int) -> list:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        people = [entry("Ma2", 1, 7, 4, 4), entry("Pa2", 0, 7, 2, 2),
                  entry("Tomil Kalama", 0, 7, 3, 5, father=("Pa9", 9, 9), mother=("Ma9", 8, 8)),
                  entry("Tomil Kalama", 0, 8, 3, 5, father=("Pa9", 9, 9), mother=("Ma9", 8, 8))]
        (folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            bytes(bytearray(b"ldwg" + bytes(TABLE - 4)) + b"".join(people) + bytes(64)))
        (folder / DATA).mkdir(parents=True)
        log = folder / LOGS / "Births and Conceptions" / "Virtual Villagers 3 Births and Conceptions Log 1.txt"
        log.parent.mkdir(parents=True)
        log.write_bytes((VILLAGE + "".join(birth("Tomil Kalama", 3, 5, ("Ma2", 4, 4), ("Pa2", 2, 2))
                                           for _ in range(births))).replace("\n", "\r\n").encode("latin-1"))
        village = gen.load_village(folder, 3, 1)
        return [p for p in village.people.values() if p.name == "Tomil Kalama"]

    def test_three_births_two_living_make_three(self):
        tomils = self.tomils(3)
        self.assertEqual(len(tomils), 3)
        self.assertEqual(sum(p.alive for p in tomils), 2)

    def test_two_births_two_living_make_two(self):
        self.assertEqual(len(self.tomils(2)), 2)

    def test_four_births_two_living_make_four(self):
        tomils = self.tomils(4)
        self.assertEqual(len(tomils), 4)
        self.assertEqual(sum(not p.alive for p in tomils), 2)


if __name__ == "__main__":
    unittest.main()
