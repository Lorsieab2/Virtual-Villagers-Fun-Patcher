"""The owner, 2026-10-08: the Family Tree Maker must follow the naming and numbering changes ("my
family tree is falsely reporting people 'left the village'", "the family tree still carries the old
names"), and the Village Matchmaker gets "Prioritize previous partners", on by default."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402

YEARS = gen.UNITS_PER_YEAR


class UnrecordedLooksTests(unittest.TestCase):
    """Papu Tamikai: born with his twin Paco's head 16 (the Birth record), head 5 in the save now,
    with no Appearance changed record."""

    def registry(self, living_father=7, record_father=7, together=False, own_birth=False):
        reg = gen._Registry()
        father, mother = reg.get("Yahto Alosaka", 18, 10), reg.get("Amaci Awanata", 11, 18)
        father.alive = mother.alive = True
        living = reg.get("Papu Tamikai", 5, 14)
        living.alive, living.sex = True, "Male"
        living.father = father.id if living_father else None
        living.mother = mother.id
        living.birth_record = 4 if own_birth else None
        record = reg.get("Papu Tamikai", 16, 14)
        record.sex, record.father, record.mother, record.birth_record, record.litter = "Male", father.id, mother.id, 3, 9
        if not record_father:
            record.father = record.mother = None
        if together:
            reg.snapshots["2026-10-08 12:00"] = {living.id, record.id}
        child = reg.get("Kid Tamikai", 1, 1)
        child.father = record.id
        return reg, living, record, child

    def test_the_record_is_the_living_villager_before_a_change_of_looks(self) -> None:
        reg, living, record, child = self.registry()
        gen._unrecorded_looks(reg)
        self.assertNotIn(record.id, reg.people)
        self.assertEqual((living.birth_record, living.litter), (3, 9))
        self.assertEqual(child.father, living.id)
        self.assertEqual(reg.relooked[("Papu Tamikai", 16, 14)], ("Papu Tamikai", 5, 14))
        self.assertEqual(reg.get("Papu Tamikai", 16, 14).id, living.id)
        self.assertGreater(reg.get("Someone New", 2, 2).id, max(p for p in reg.people if p != reg.by_key[("Someone New", 2, 2)]))

    def test_never_without_the_same_recorded_parents(self) -> None:
        reg, _living, record, _child = self.registry(record_father=0)    # a pool name, no parents
        gen._unrecorded_looks(reg)
        self.assertIn(record.id, reg.people)

    def test_never_two_villagers_listed_together_or_two_births(self) -> None:
        for kwargs in ({"together": True}, {"own_birth": True}):
            reg, _living, record, _child = self.registry(**kwargs)
            gen._unrecorded_looks(reg)
            self.assertIn(record.id, reg.people, kwargs)


class TreeNamesTests(unittest.TestCase):
    def test_a_rename_puts_the_name_right_in_the_players_own_words(self) -> None:
        data = {"format": 1, "entries": {
            "Iruwa Bahati I|13|19": {"lines": ["7. Iruwa Bahati I", "Iruwa Bahati II's sister"],
                                     "runs": [[["7. ", {}], ["Iruwa Bahati I", {"bold": True}]],
                                              [["Iruwa Bahati II's sister", {}]]]},
            "Iruwa Bahati II|2|2": {"lines": ["8. Iruwa Bahati II"]}}}
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        out = json.loads(ft.renamed_keys(text, {("Iruwa Bahati I", 13, 19): "Iruwa Jafari"}))
        entry = out["entries"]["Iruwa Jafari|13|19"]
        self.assertEqual(entry["lines"], ["7. Iruwa Jafari", "Iruwa Bahati II's sister"])
        self.assertEqual(entry["runs"][0], [["7. ", {}], ["Iruwa Jafari", {"bold": True}]])
        self.assertEqual(out["entries"]["Iruwa Bahati II|2|2"]["lines"], ["8. Iruwa Bahati II"])

    def test_a_tree_file_is_written_back_in_its_own_shape(self) -> None:
        data = {"format": "x", "edits": {"entries": {"Hawa Awanata II|19|12": {"lines": ["Hawa Awanata II"]}}}}
        text = json.dumps(data, indent=1)
        out = ft.renamed_keys(text, {("Hawa Awanata II", 19, 12): "Hawa Awanata"})
        self.assertTrue(out.startswith('{\n "'))
        self.assertEqual(json.loads(out)["edits"]["entries"]["Hawa Awanata|19|12"]["lines"], ["Hawa Awanata"])
        self.assertEqual(ft.renamed_keys("not json", {("A", 1, 1): "B"}), "not json")

    def test_the_name_pattern(self) -> None:
        plain = ft._name_pattern("Iruwa Bahati I")
        self.assertIsNone(plain.search("Iruwa Bahati II"))
        self.assertIsNotNone(plain.search("35. Iruwa Bahati I"))
        self.assertIsNone(plain.search("XIruwa Bahati I"))
        any_number = ft._name_pattern("Iruwa Bandele", numbered=True)
        self.assertEqual(any_number.sub("Iruwa Bandele", "35. Iruwa Bandele II / Natural"), "35. Iruwa Bandele / Natural")


def person(pid, name, sex, years, father=None, mother=None, alive=True):
    p = gen.Person(pid, name, pid, pid, sex=sex, age=years * YEARS, alive=alive, father=father, mother=mother)
    p.first_seen = "2026-10-01 00:00"
    return p


class PreviousPartnersTests(unittest.TestCase):
    def village(self) -> gen.Village:
        people = {1: person(1, "Hoani Chuchip", "Male", 30), 2: person(2, "Kaula Akikai", "Female", 25),
                  3: person(3, "Lulu Chuchip", "Female", 1, father=1, mother=2),
                  4: person(4, "Tomi Wanjiko", "Male", 25)}
        return gen.Village(1, 1, "T", people)

    def test_an_established_couple_comes_first_and_the_rule_is_on_by_default(self) -> None:
        self.assertTrue(gen.Rules().prefer_previous_partners)
        self.assertIn("Previous partners first", gen.Rules().describe())
        pairs, _per_woman, _fallback = gen.suggest(self.village(), gen.Rules())
        self.assertEqual([(p.man.name, p.woman.name) for p in pairs], [("Hoani Chuchip", "Kaula Akikai")])

    def test_age_units_can_be_turned_off(self) -> None:
        """The owner, 2026-10-08: "a toggle to turn Age Units on and off in the village matchmaker"."""
        self.assertTrue(gen.Rules().show_age_units)
        on = gen.pair_report(self.village(), gen.Rules(), "A New Home")
        off = gen.pair_report(self.village(), gen.Rules(show_age_units=False), "A New Home")
        self.assertIn("600 game units (30 years old)", on)
        self.assertNotIn("game units", off)
        self.assertIn("Hoani Chuchip, 30 years old", off)
        self.assertNotIn("units", " ".join(gen.Rules(show_age_units=False).describe()))

    def test_off_the_closer_age_wins(self) -> None:
        pairs, _per_woman, _fallback = gen.suggest(self.village(), gen.Rules(prefer_previous_partners=False))
        self.assertEqual([(p.man.name, p.woman.name) for p in pairs], [("Tomi Wanjiko", "Kaula Akikai")])


if __name__ == "__main__":
    unittest.main()
