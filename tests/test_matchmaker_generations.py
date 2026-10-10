"""The owner, 2026-10-10: "for matchmaker can you show the generation numbers the villagers belong to, and
add a default on toggle for (prioritize latest generation) first"."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_genealogy as gen  # noqa: E402
import vv_genealogy_window as win  # noqa: E402

YEARS = gen.UNITS_PER_YEAR


def person(pid, name, sex, years, generation, father=None, mother=None):
    p = gen.Person(pid, name, pid, pid, sex=sex, age=years * YEARS, alive=True, father=father, mother=mother)
    p.first_seen = "2026-10-01 00:00"
    p.generation = generation
    return p


def village() -> gen.Village:
    """An older couple (generation I), a younger couple (generation II), and a generation I man who is also
    the best match by age for the generation II woman's older rival."""
    people = {
        1: person(1, "Aro Alosaka", "Male", 30, 1), 2: person(2, "Bela Wikimak", "Female", 30, 1),
        3: person(3, "Cato Chuchip", "Male", 22, 2), 4: person(4, "Dina Akikai", "Female", 22, 2),
        5: person(5, "Eko Wanjiko", "Male", 20, 0 + 3), 6: person(6, "Fia Tamikai", "Female", 20, 3),
    }
    return gen.Village(1, 1, "T", people)


def pairs(rules: gen.Rules):
    return [(p.man.id, p.woman.id) for p in gen.suggest(village(), rules)[0]]


class MatchmakerGenerationTests(unittest.TestCase):
    def test_the_toggle_is_on_by_default_and_remembered_like_the_other_rules(self) -> None:
        self.assertTrue(gen.Rules().prefer_latest_generation)
        self.assertIn("latest generation at the top", " ".join(gen.Rules().describe()))
        self.assertIn("Listed in the default order", " ".join(gen.Rules(list_by="default").describe()))
        self.assertEqual(gen.Rules().list_by, "generation")
        self.assertEqual(gen.Rules().list_direction, "descending")
        self.assertIn("list_by", [name for name, _w, _k in win.RULE_FIELDS])
        self.assertFalse(win.rules_from({"prefer_latest_generation": False}).prefer_latest_generation)   # Preview 21 settings
        self.assertTrue(win.rules_from({}).prefer_latest_generation)          # an old settings file: on
        self.assertTrue(win.rules_from({"prefer_latest_generation": True}).prefer_latest_generation)

    def test_newest_generation_pairs_first_and_off_is_the_previous_order(self) -> None:
        on = pairs(gen.Rules(close_in_age=False))
        gens = lambda prs: [max(v.people[m].generation, v.people[w].generation) for m, w in prs]
        v = village()
        self.assertEqual(on, [(5, 6), (3, 4), (1, 2)])
        self.assertEqual(gens(on), sorted(gens(on), reverse=True))        # newest generation first
        off = pairs(gen.Rules(close_in_age=False, list_by="default"))
        self.assertEqual(len(off), len(on))                                 # the same villagers are paired
        # Off: the previous order, which ignores generations (closest in age first: the oldest couple).
        self.assertEqual(off, [(1, 2), (3, 4), (5, 6)])
    def test_who_may_pair_is_untouched(self) -> None:
        for rules in (gen.Rules(), gen.Rules(plan_ahead=True)):
            a = gen.suggest(village(), rules)[1]
            b = gen.suggest(village(), gen.Rules(**{**rules.__dict__, "list_by": "default"}))[1]
            self.assertEqual({w: sorted(p.man.id for p in ps) for w, ps in a.items()},
                             {w: sorted(p.man.id for p in ps) for w, ps in b.items()})
        v = village()
        v.people[7] = person(7, "Gus Bahati", "Male", 21, 4, father=3, mother=4)
        v.people[8] = person(8, "Hana Bahati", "Female", 21, 4, father=3, mother=4)
        for on in (True, False):
            pr = gen.suggest(v, gen.Rules(list_by="generation" if on else "default", plan_ahead=True))[1]
            self.assertNotIn(7, [p.man.id for p in pr.get(8, [])])     # full siblings stay blocked

    def test_the_report_shows_each_villagers_generation(self) -> None:
        report = gen.pair_report(village(), gen.Rules(), "A New Home")
        self.assertIn("Eko Wanjiko, 400 game units (20 years old), Generation III", report)
        self.assertIn("Generation I", report)
        for line in report.splitlines():
            if line.strip().startswith("1.") and "#" in line:
                self.assertEqual(line.count("Generation"), 2)
        off = gen.pair_report(village(), gen.Rules(show_age_units=False), "A New Home")
        self.assertIn("Eko Wanjiko, 20 years old, Generation III", off)

    def test_zero_values_and_the_fallback_list(self) -> None:
        v = village()
        for p in v.people.values():
            p.head = p.body = 0
        self.assertIn("Generation III", gen.pair_report(v, gen.Rules(), "A New Home"))
        v = gen.Village(1, 1, "T", {1: person(1, "Aro Alosaka", "Male", 30, 1),
                                    2: person(2, "Bela Alosaka", "Female", 30, 2)})
        report = gen.pair_report(v, gen.Rules(), "A New Home")
        self.assertIn("Aro Alosaka (Generation I) and Bela Alosaka (Generation II):", report)
        match = next(m for m in win.MATCHMAKER_STYLE if "woman" in m[1] and len(m[1]) == 2 and m[0].pattern.startswith("^    "))
        found = match[0].search(next(l for l in report.splitlines() if "(Generation I)" in l))
        self.assertEqual((found.group(1), found.group(2)), ("Aro Alosaka", "Bela Alosaka"))

    def test_every_listing_option_and_direction(self) -> None:
        """List pairings by: generation, age, family tree number; ascending and descending."""
        v = village()
        for pid, number in zip(sorted(v.people), (6, 5, 4, 3, 2, 1)):      # numbers run opposite to ids
            v.people[pid].number = number
        v.people[1].age = 0                                                  # an age of 0 is a real age
        base = gen.suggest(v, gen.Rules(list_by="default", plan_ahead=True))[1]
        allowed = {w: sorted(p.man.id for p in ps) for w, ps in base.items()}
        keys = {"generation": lambda w, m: max(w.generation, m.generation),
                "age": lambda w, m: w.age, "number": lambda w, m: w.number}
        for by, key in keys.items():
            for direction in ("ascending", "descending"):
                rules = gen.Rules(list_by=by, list_direction=direction, plan_ahead=True)
                one, per_woman, _fallback = gen.suggest(v, rules)
                self.assertEqual({w: sorted(p.man.id for p in ps) for w, ps in per_woman.items()}, allowed, (by, direction))
                values = [key(v.people[w], v.people[ps[0].man.id]) for w, ps in per_woman.items()]
                if by == "generation":
                    values = [max(v.people[w].generation, v.people[ps[0].man.id].generation) for w, ps in per_woman.items()]
                self.assertEqual(values, sorted(values, reverse=direction == "descending"), (by, direction))
                pair_values = [key(p.woman, p.man) for p in one]
                self.assertEqual(pair_values, sorted(pair_values, reverse=direction == "descending"), (by, direction))
                self.assertIn(gen.LIST_BY[by][0], " ".join(rules.describe()))
                self.assertIn(gen.LIST_BY[by][1 if direction == "ascending" else 2], " ".join(rules.describe()))

    def test_listing_only_reorders_the_default_matching_for_age_and_number(self) -> None:
        v = village()
        default = {(p.man.id, p.woman.id) for p in gen.suggest(v, gen.Rules(list_by="default"))[0]}
        for by in ("age", "number"):
            got = {(p.man.id, p.woman.id) for p in gen.suggest(v, gen.Rules(list_by=by))[0]}
            self.assertEqual(got, default, by)           # the same suggested pairs, only listed differently

    def test_listing_choice_is_remembered_and_bad_values_are_ignored(self) -> None:
        rules = win.rules_from({"list_by": "age", "list_direction": "ascending"})
        self.assertEqual((rules.list_by, rules.list_direction), ("age", "ascending"))
        rules = win.rules_from({"list_by": "nonsense", "list_direction": "sideways"})
        self.assertEqual((rules.list_by, rules.list_direction), ("generation", "descending"))
        self.assertEqual(win.rules_from({"prefer_latest_generation": False}).list_by, "default")
        self.assertEqual(win.rules_from({"prefer_latest_generation": False, "list_by": "age"}).list_by, "age")
        gen.pair_report(village(), gen.Rules(list_by="nonsense"), "A New Home")      # never fails

if __name__ == "__main__":
    unittest.main()
