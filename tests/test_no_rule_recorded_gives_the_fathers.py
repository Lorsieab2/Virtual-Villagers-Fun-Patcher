"""A village with no last-names rule recorded gives its babies the father's last name, in all five
games (the owner, 2026-10-14: "vv3-5 and the other games still have the last-names bug when new
children are born, and when villagers are generated in the village").

The owner's Secret City test village had no Last Names record (Repair's last-names window had never
been opened for it), so VVFP Last Names.dll's VvfpRuleLastName2 found no rule and every baby kept its
mother's family's name: Watu Wanjiko and Omawa Wanjiko, children of Keiau Chinaka; Tufi Sirikit,
daughter of Keiau Chinaka and Kitika Awanata.  The last-names window shows "From the father" for such
a village, so the DLL now uses that rule (DEFAULT_RULE) when none is recorded -- or when the village
cannot be told yet -- and Check Saves & Logs reads the same rule, so the two never disagree.  The DLL's
side runs in native/vvfp_last_names/last_names_harness.c section 8 (tests/test_last_names_own_rules.py).
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_last_names as ln  # noqa: E402
from vv_last_names import Living  # noqa: E402


def village():
    father = Living(0, "Keiau Chinaka", "Male", 9, 8, 7, "Chinaka", alive=True, arrived=False, age=854)
    mother = Living(1, "Zucca Wanjiko", "Female", 13, 25, 43, "Wanjiko", alive=True, arrived=False, age=857)
    # A child's family is her mother's: the DLL gave Watu his mother's family's name.
    child = Living(8, "Watu Wanjiko", "Male", 10, 23, 43, "Wanjiko", alive=True, arrived=False, age=382)
    return [father, mother, child], {child.identity: (father.identity, mother.identity)}, child


class NoRuleRecorded(unittest.TestCase):
    def test_the_default_is_from_the_father(self):
        self.assertEqual(ln.DEFAULT_RULE, "father")
        self.assertIn(ln.DEFAULT_RULE, ln.INHERIT)

    def check(self, game: int):
        people, parents, child = village()
        with mock.patch.object(ln, "read_record", return_value=(None, {})), \
                mock.patch.object(ln, "known_names", return_value=set()), \
                mock.patch.object(ln, "everyone", return_value=(people, parents)), \
                mock.patch.object(ln, "own_rules_now", return_value={}):
            return ln.wrong_last_names_explained(Path("unused"), game, 1), child

    def test_the_check_reads_a_village_with_no_record_by_the_fathers(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                (rule, wrong), child = self.check(game)
                self.assertEqual(rule, "father")
                self.assertEqual([(v.identity, now, should) for v, now, should, _used, _either in wrong],
                                 [(child.identity, "Wanjiko", "Chinaka")])

    def test_the_dll_uses_the_same_default(self):
        source = (ROOT / "native" / "vvfp_last_names" / "vvfp_last_names.c").read_text(encoding="utf-8")
        self.assertIn("#define DEFAULT_RULE 'f'", source)
        rule = source[source.index("int __stdcall VvfpRuleLastName2("):source.index("int __stdcall VvfpRelookLastName(")]
        self.assertRegex(rule, r"if \(rule\[0\] == '\\0' && !names_a_rule\(\)\) \{\s+rule\[0\] = DEFAULT_RULE;")
        # A missing record is no longer the end of it.
        self.assertIsNone(re.search(r"if \(!read_record\(slot, rule, sizeof rule\)\) \{\s+return 0;", rule))

    def test_no_python_reader_falls_back_to_the_mother(self):
        source = (ROOT / "src" / "vv_last_names.py").read_text(encoding="utf-8")
        self.assertNotIn('rule or "mother"', source)
        self.assertEqual(source.count("rule or DEFAULT_RULE"), 3)


if __name__ == "__main__":
    unittest.main()
