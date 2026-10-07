"""Repair Saves & Logs' last names: where each villager's comes from.

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
    def test_fathers_names_flow_down_the_generations(self) -> None:
        given = ln.inherited(PEOPLE, PARENTS, "father")
        self.assertEqual(given[GORO.identity], "Lasso")         # his father's own
        self.assertEqual(given[SEKAI.identity], "Lasso")        # her father's, given him now
        self.assertEqual(given[CHIKA.identity], "Moa")          # a dead father's own
        self.assertEqual(given[HUATA.identity], "Ruku")         # no parents: the family's

    def test_a_name_the_player_gives_is_inherited_by_the_rule(self) -> None:
        # The owner, 2026-10-07: type "Chapstick" in a villager's own box, and with "From the
        # mother" her descendants inherit it; a name set further down is kept.
        given = ln.inherited(PEOPLE, PARENTS, "mother", fixed={HUATA.identity: "Chapstick"})
        self.assertEqual(given[HUATA.identity], "Chapstick")
        self.assertEqual(given[GORO.identity], "Chapstick")      # her son
        self.assertEqual(given[SEKAI.identity], "Moa")           # Goro's daughter: her mother Chika's
        father_rule = ln.inherited(PEOPLE, PARENTS, "father", fixed={GORO.identity: "Chapstick"})
        self.assertEqual(father_rule[SEKAI.identity], "Chapstick")   # her father Goro's
        kept = ln.inherited(PEOPLE, PARENTS, "father", fixed={GORO.identity: "Chapstick",
                                                               SEKAI.identity: ""})
        self.assertEqual(kept[SEKAI.identity], "", "a villager set to no last name keeps none")
        self.assertEqual(ln.inherited(PEOPLE, PARENTS, "each", fixed={GORO.identity: "Chapstick"}),
                         {HUATA.identity: "", GORO.identity: "Chapstick", CHIKA.identity: "", SEKAI.identity: ""})

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
        # Choose from list and Type custom name: every villager keeps the last name they carry
        # until the player gives another -- choosing the rule never wipes a name.
        for rule in ln.PLAYER_RULES:
            with self.subTest(rule=rule):
                self.assertEqual(set(ln.inherited(PEOPLE, PARENTS, rule).values()), {""})
                named = living("Dee Moa", 1, "Ruku", 4)
                self.assertEqual(ln.inherited([named, HUATA], {}, rule, fixed={HUATA.identity: "Chapstick"}),
                                 {named.identity: "Moa", HUATA.identity: "Chapstick"})

    def test_a_loop_in_the_records_ends_at_the_family(self) -> None:
        a, b = living("Ana", 1, "Ruku", 1), living("Bo", 2, "Tano", 2)
        looped = {a.identity: (b.identity, None), b.identity: (a.identity, None)}
        given = ln.inherited([a, b], looped, "father")
        self.assertEqual(set(given.values()) <= {"Ruku", "Tano"}, True)

    def test_villagers_without_parents_get_last_names_of_their_own(self) -> None:
        # The owner: "unrelated and single individuals have no family yet and should get separate
        # last names"; a couple's children take the father's.
        pool = ["Ruku", "Tano", "Mele", "Pao"]
        dad = living("Ari", 1, "Ruku", 1)
        mum = living("Bea", 1, "Ruku", 2)            # the same family number, by chance
        lone = living("Cal", 2, "Tano", 3)
        named = living("Dee Moa", 1, "Ruku", 4)       # already carries one
        kid = living("Eve", 1, "Ruku", 5)
        people = [dad, mum, lone, named, kid]
        parents = {kid.identity: (dad.identity, mum.identity)}
        given = ln.inherited(people, parents, "father", pool)
        self.assertEqual(given[dad.identity], "Ruku")
        self.assertEqual(given[mum.identity], "Mele")        # Ruku is Ari's; Tano is Cal's: the next free
        self.assertEqual(given[lone.identity], "Tano")
        self.assertEqual(given[kid.identity], "Ruku")        # the father's
        self.assertEqual(len({given[v.identity] for v in (dad, mum, lone)}), 3)
        listed = ln.inherited(people, parents, "list", pool)
        self.assertTrue(set(listed.values()) <= set(pool))
        self.assertEqual(listed, ln.inherited(people, parents, "list", pool))      # the same each time
        self.assertEqual(set(ln.inherited(people, parents, "each", pool).values()), {"", "Moa"})

    def test_every_rule_is_offered(self) -> None:
        # A typed name goes in the villager's own box, whose list offers "(custom last name - type
        # here...)" (the owner, 2026-10-07); it is not a rule.
        self.assertEqual(list(ln.INHERIT), ["mother", "father", "random", "list", "each"])
        self.assertEqual(ln.CUSTOM, "(custom last name - type here...)")
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("vv_last_names.with_siblings(fixed(), parents), carried)", gui)
        self.assertIn("values=[none, custom] + first", gui)
        self.assertIn('if value.get() == custom:\n                value.set("")', gui)
        # The whole new name is held to the game's room, and a box past it is marked.
        self.assertIn("len(vv_last_names.with_last(number, v.name, last, known)) > room", gui)
        self.assertIn('mark.set(f"too long: {room} characters at most")', gui)
        set_by = gui[gui.index("        def set_by_player(v) -> None:"):]
        self.assertIn("mine.add(v.identity)\n            by_rule()", set_by[:120], "the family follows at once")
        # Any change to a villager's box -- typed, pasted or picked -- is the player's; the
        # window's own filling in is not.
        self.assertIn('value.trace_add("write", lambda *_a, v=v: None if filling[0] else set_by_player(v))', gui)
        # The box takes typed names: it is never read-only.
        start = gui.index("box = ttk.Combobox(inner, textvariable=value, width=30,")
        self.assertNotIn("readonly", gui[start:gui.index("\n", start + 200)])

    def test_brothers_and_sisters_follow_a_name_the_player_gives(self) -> None:
        # The owner: "if one villager's last name is filled, the other members of their family
        # should probably auto-adjust": Goro's sister takes his typed name, and her daughter follows.
        sister = living("Mai", 2, "Tano", 8)
        niece = living("Lani", 2, "Tano", 9)
        people = PEOPLE + [sister, niece]
        parents = dict(PARENTS)
        parents[sister.identity] = PARENTS[GORO.identity]
        parents[niece.identity] = (("Pod", 1, 1), sister.identity)
        given = ln.inherited(people, parents, "mother", fixed=ln.with_siblings({GORO.identity: "Chapstick"}, parents))
        self.assertEqual(given[sister.identity], "Chapstick")
        self.assertEqual(given[niece.identity], "Chapstick")
        self.assertEqual(ln.with_siblings({GORO.identity: "A", sister.identity: "B"}, parents)[sister.identity], "B",
                         "a sibling the player set keeps theirs")

    def test_a_name_splits_into_first_last_and_numeral(self) -> None:
        # Every last name may be changed, a numeral (Number Duplicate Names) kept after it.
        self.assertEqual(ln.split_name(3, "Soda Akikai II"), ("Soda", "Akikai", "II"))
        self.assertEqual(ln.split_name(3, "Soda II"), ("Soda", "", "II"))
        self.assertEqual(ln.split_name(3, "Chapa Chapstick", {"Chapstick"}), ("Chapa", "Chapstick", ""))
        self.assertEqual(ln.split_name(3, "Akikai"), ("Akikai", "", ""), "a first word is never a last name")
        self.assertEqual(ln.with_last(3, "Soda Akikai II", "Wikimak"), "Soda Wikimak II")
        self.assertEqual(ln.with_last(3, "Soda Akikai II", ""), "Soda II")
        self.assertEqual(ln.with_last(3, "Soda II", "Akikai"), "Soda Akikai II")

    def test_a_change_of_rule_re_derives_the_family(self) -> None:
        # Goro already carries "Lasso"; under "From the mother" he is Huata's son: Ruku.
        goro = living("Goro Lasso", 2, "Tano", 5)
        people = [HUATA, goro]
        parents = {goro.identity: (KITO, HUATA.identity)}
        carried = lambda name: ln.split_name(3, name, {"Lasso", "Ruku"})[1]  # noqa: E731
        self.assertEqual(ln.inherited(people, parents, "mother", carried=carried)[goro.identity], "Ruku")
        self.assertEqual(ln.inherited(people, parents, "father", carried=carried)[goro.identity], "Lasso")


if __name__ == "__main__":
    unittest.main()
