"""The carrier is the carrying parent whatever their sex (the owner, 2026-11-15): the Family Tree's genealogy.

A villager can carry as a man -- their sex changed mid-pregnancy (the sex change is offered while carrying and
nursing, keeping the pregnancy), or an island event made a man carry.  The Births and Conceptions log puts the
carrier in its Mother slot ("Mother" = the carrying parent), so:

  * a living carrier is "expecting" whatever their sex now (src/vv_genealogy.py _save_people: the pregnancy
    field alone, as A New Home already did), so the tree still shows the Upcoming child;
  * the Mother slot's sex is only a guess for a parent nothing else describes: a dead or gone carrier's own
    record (the Death record's "Sex: Male") gives their sex, not the slot (_slot_sex, _log_people).
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
from test_lost_before_birth import BIRTHS, DEATHS, write  # noqa: E402


def conception(mother: str, sex: str, babies: int) -> str:
    return (f"Conception 1\n  Mother: {mother}\n    Age at conception: 600\n    Sex: {sex}\n"
            f"    Head: 2\n    Body: 3\n    Likes: (none)\n    Dislikes: (none)\n"
            f"  Father: Pa\n    Age at conception: 700\n    Sex: Male\n    Head: 0\n"
            f"    Body: 2\n    Likes: (none)\n    Dislikes: (none)\n  Babies in pregnancy: {babies}\n\n")


def birth(child: str, mother: str) -> str:
    return (f"Birth\n  Child: {child}\n    Head: 3\n    Body: 3\n  Mother: {mother}\n    Head: 2\n"
            f"    Body: 3\n  Father: Pa\n    Head: 0\n    Body: 2\n\n")


def death(name: str, sex: str) -> str:
    return (f"Death 1\n  Name: {name}\n  Age at death: 900\n  Sex: {sex}\n  Cause of death: Old age\n"
            f"  Grave: Untrained\n  Epitaph: (none)\n  Head: 2\n  Body: 3\n  Likes: (none)\n"
            f"  Dislikes: (none)\n\n")


class AMaleCarrier(unittest.TestCase):
    def test_a_dead_male_carrier_keeps_his_own_sex(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, BIRTHS.format(g=3), "Village: Tribe (Save 1)\n" + conception("Ro", "Male", 1)
                  + birth("Kid", "Ro"))
            write(folder, DEATHS.format(g=3), "Village: Tribe (Save 1)\n" + death("Ro", "Male"))
            reg = gen._Registry()
            gen._births(reg, folder, 3, 1)
            ro = reg.get("Ro", 2, 3)
            kid = reg.get("Kid", 3, 3)
            self.assertEqual(kid.mother, ro.id, "the carrier is the carrying parent")
            self.assertEqual(ro.sex, "Female", "the slot's guess, before any record of his own")
            self.assertTrue(ro.sex_from_slot)
            gen._log_people(reg, folder, 3, 1)
            self.assertEqual(ro.sex, "Male", "his own Death record's sex, not the Mother slot's")
            self.assertFalse(ro.sex_from_slot)
            self.assertEqual(kid.mother, ro.id, "and still the carrying parent")

    def test_a_record_s_sex_is_never_replaced_by_a_slot(self):
        p = gen.Person(1, "Ro", 2, 3, "Male")
        gen._slot_sex(p, "Female")
        self.assertEqual((p.sex, p.sex_from_slot), ("Male", False))

    def test_a_living_male_carrier_is_expecting(self):
        # _save_people's rule in every game: the pregnancy field alone (no "and female").
        source = (ROOT / "src" / "vv_genealogy.py").read_text(encoding="utf-8")
        self.assertIn("p.expecting = ln.carrying(game, data, at)         # whoever carries", source)
        self.assertNotIn('p.sex == "Female" and ln.carrying', source)


if __name__ == "__main__":
    unittest.main()
