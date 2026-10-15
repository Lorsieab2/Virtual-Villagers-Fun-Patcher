"""A child takes the last name of the parent the village rule names, never the other parent's
(the owner, 2026-10-14: "FROM THE FATHER" is the village rule, yet Tatoa, daughter of Hokou Helaku
and Alana Tawonga, was born Tatoa Tawonga).

Two causes, both covered here:
- The last-names window showed "From the father" for a village with no Last Names record yet but
  kept it only when the player touched the rule box, so no rule reached the births and VVFP Last
  Names.dll left the family's name -- the mother's family (Tatoa: family 43, Tawonga).
- "From the father" fell back to the mother's name (and to the family's, the mother's family) when
  the father had none.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_last_names as ln  # noqa: E402
from vv_last_names import Living  # noqa: E402


def carried(name: str) -> str:
    return name.rpartition(" ")[2] if " " in name else ""


def village(father_name: str = "Hokou Helaku", mother_name: str = "Alana Tawonga"):
    father = Living(0, father_name, "Male", 0, 15, 10, "Helaku", alive=True, arrived=False, age=519)
    mother = Living(100, mother_name, "Female", 29, 15, 43, "Tawonga", alive=True, arrived=False, age=596)
    # A child's family is her mother's (the owner's save: Tatoa is family 43, Tawonga).
    child = Living(200, "Tatoa Tawonga", "Female", 13, 7, 43, "Tawonga", alive=True, arrived=False, age=52)
    return [father, mother, child], {child.identity: (father.identity, mother.identity)}, child


class ChildTakesNamedParent(unittest.TestCase):
    def test_from_the_father_gives_the_fathers(self):
        people, parents, child = village()
        self.assertEqual(ln.inherited(people, parents, "father", None, None, carried, {})[child.identity], "Helaku")

    def test_from_the_mother_gives_the_mothers(self):
        people, parents, child = village()
        self.assertEqual(ln.inherited(people, parents, "mother", None, None, carried, {})[child.identity], "Tawonga")

    def test_a_father_with_no_last_name_never_gives_the_mothers(self):
        people, parents, child = village(father_name="Hokou")
        people[0] = Living(0, "Hokou", "Male", 0, 15, 10, "", alive=True, arrived=True, age=519)
        got = ln.inherited(people, parents, "father", None, None, carried, {})[child.identity]
        self.assertNotEqual(got, "Tawonga")
        self.assertEqual(got, "")

    def test_a_mother_with_no_last_name_never_gives_the_fathers(self):
        people, parents, child = village(mother_name="Alana")
        people[1] = Living(100, "Alana", "Female", 29, 15, 43, "", alive=True, arrived=True, age=596)
        got = ln.inherited(people, parents, "mother", None, None, carried, {})[child.identity]
        self.assertNotEqual(got, "Helaku")
        self.assertEqual(got, "")

    def test_random_still_takes_the_one_parent_with_a_name(self):
        people, parents, child = village(father_name="Hokou")
        people[0] = Living(0, "Hokou", "Male", 0, 15, 10, "", alive=True, arrived=True, age=519)
        self.assertEqual(ln.inherited(people, parents, "random", None, None, carried, {})[child.identity],
                         "Tawonga")

    def test_the_rule_shown_is_kept_for_a_village_with_no_record(self):
        # The window shows "From the father" for a village with no record yet; OK must keep it, or the
        # births follow no rule (VVFP Last Names.dll reads only the record) and keep the family's name.
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        dialog = source[source.index("    def _last_names_dialog("):source.index("    def _own_rules_dialog(")]
        self.assertIn('saved_rule = names.get("rule") or recorded_rule or "father"', dialog)
        self.assertIn('names["rules_changed"] = names["own"] != written_own or rule_key() != recorded_rule', dialog)
        self.assertNotIn("rule_touched", dialog)


if __name__ == "__main__":
    unittest.main()
