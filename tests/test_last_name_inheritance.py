"""Repair Logs' last names: where each villager's comes from.

The owner (2026-10-07): "an option to choose whether people inherit the Father or Mother's last
name, or random 50:50 or player choice for each villager", "I also want the player to be able to
hand-type in last names too!" (each villager's box takes typed names).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_last_names as ln  # noqa: E402


def living(name: str, family: int, default: str, head: int = 1) -> ln.Living:
    return ln.Living(0, name, "Female", head, head, family, default)


# Kito Lasso (already named) and Huata (living, family Ruku) are Goro's parents; Goro and Chika
# are Sekai's.  Ghali, long dead, is Chika's father; her mother is unknown.
KITO = ("Kito Lasso", 4, 4)
HUATA = living("Huata", 1, "Ruku", 3)
GORO = living("Goro", 2, "Tano", 5)
CHIKA = living("Chika", 3, "Mele", 6)
SEKAI = living("Sekai", 3, "Mele", 7)
PEOPLE = [HUATA, GORO, CHIKA, SEKAI]
PARENTS = {
    GORO.identity: (KITO, HUATA.identity),
    CHIKA.identity: (("Ghali Moa", 9, 9), None),
    SEKAI.identity: (GORO.identity, CHIKA.identity),
}


class InheritanceTests(unittest.TestCase):
    def test_the_family_rule_is_the_games_own(self) -> None:
        given = ln.inherited(PEOPLE, PARENTS, "family")
        self.assertEqual(given[GORO.identity], "Tano")
        self.assertEqual(given[SEKAI.identity], "Mele")

    def test_fathers_names_flow_down_the_generations(self) -> None:
        given = ln.inherited(PEOPLE, PARENTS, "father")
        self.assertEqual(given[GORO.identity], "Lasso")         # his father's own
        self.assertEqual(given[SEKAI.identity], "Lasso")        # her father's, given him now
        self.assertEqual(given[CHIKA.identity], "Moa")          # a dead father's own
        self.assertEqual(given[HUATA.identity], "Ruku")         # no parents: the family's

    def test_mothers_names_and_the_fallback_to_the_father(self) -> None:
        given = ln.inherited(PEOPLE, PARENTS, "mother")
        self.assertEqual(given[GORO.identity], "Ruku")          # Huata's, given her now
        self.assertEqual(given[CHIKA.identity], "Moa")          # no mother: the father's
        self.assertEqual(given[SEKAI.identity], "Moa")          # Chika's

    def test_random_picks_a_parent_and_the_same_one_every_time(self) -> None:
        first = ln.inherited(PEOPLE, PARENTS, "random")
        self.assertIn(first[SEKAI.identity], {"Lasso", "Ruku", "Moa"})
        for _ in range(5):
            self.assertEqual(ln.inherited(PEOPLE, PARENTS, "random"), first)
        # Across many villagers both parents are chosen.
        kids = [living(f"Kid{k}", 3, "Mele", 100 + k) for k in range(40)]
        parents = {k.identity: (("Dad Lasso", 1, 1), ("Mum Ruku", 2, 2)) for k in kids}
        picks = set(ln.inherited(kids, parents, "random").values())
        self.assertEqual(picks, {"Lasso", "Ruku"})

    def test_each_villager_left_to_the_player(self) -> None:
        self.assertEqual(set(ln.inherited(PEOPLE, PARENTS, "each").values()), {""})

    def test_a_loop_in_the_records_ends_at_the_family(self) -> None:
        a, b = living("Ana", 1, "Ruku", 1), living("Bo", 2, "Tano", 2)
        looped = {a.identity: (b.identity, None), b.identity: (a.identity, None)}
        given = ln.inherited([a, b], looped, "father")
        self.assertEqual(set(given.values()) <= {"Ruku", "Tano"}, True)

    def test_every_rule_is_offered(self) -> None:
        self.assertEqual(list(ln.INHERIT), ["family", "father", "mother", "random", "each"])
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("vv_last_names.inherited(people, parents, rule_key())", gui)
        # The box takes typed names: it is never read-only.
        start = gui.index("box = ttk.Combobox(inner, textvariable=value, width=24,")
        self.assertNotIn("readonly", gui[start:gui.index("\n", start + 200)])


if __name__ == "__main__":
    unittest.main()
