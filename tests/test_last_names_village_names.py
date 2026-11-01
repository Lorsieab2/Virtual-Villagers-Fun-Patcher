"""The owner's last-name rules of 2026-10-31 (all five games).

1. A villager's own rule ALWAYS beats the village-wide rule.  When both parents have own rules that
   disagree, a fair coin for each child picks whose own rule is used: in the game a fresh draw at each
   birth (VVFP Last Names' random_below), in Repair Saves & Logs the same each time for the same child
   (own_coin), and Repair keeps the last name a child carries when either parent's rule gives it.
2. "Random from the existing Village Names" (record keyword "village"), both as the village's rule and as
   a villager's own: each child a last name drawn at random among the last names the village has EVER used
   -- any villager, living or dead, the save's and the logs' -- every eligible name equally likely, only
   names that fit the name field.  Repair keeps the record's "used" lines (cumulative, never shrinking) so
   the DLL knows them; with none, the game's list.  An earlier build's readers skip the new lines.

The DLL side runs in native/vvfp_last_names/last_names_harness.c (tests/test_last_names_own_rules.py,
sections 1, 10 and 13).
"""
from __future__ import annotations

import collections
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_last_names_own_rules import save  # noqa: E402
from test_last_names_rename import NoGame, entry  # noqa: E402

LABEL = "Random from the existing Village Names"
POOL = [f"Ln{n:02d}" for n in range(50)]


def person(name: str, sex: str, head: int = 1, body: int = 1, alive: bool = True, arrived: bool = False) -> ln.Living:
    return ln.Living(0, name, sex, head, body, 1, "Akikai", alive=alive, arrived=arrived)


def carried(name: str) -> str:
    return ln.split_name(3, name)[1]


class TheRuleAndItsLabel(unittest.TestCase):
    def test_both_dropdowns_offer_it(self):
        self.assertEqual(ln.INHERIT["village"], LABEL)
        self.assertEqual(ln.OWN_RULES["village"], LABEL)
        self.assertEqual(ln.VILLAGE_NAMES, "village")
        self.assertIn("village", ln.RANDOM_RULES)

    def test_the_window_lists_them_and_says_how_rules_combine(self):
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        main = source[source.index("    def _last_names_dialog("):source.index("    def _own_rules_dialog(")]
        own = source[source.index("    def _own_rules_dialog("):source.index("    def _repair_questions(")]
        # The dropdowns are the module's own tables, so the new entry shows in both.
        self.assertIn("values=list(vv_last_names.INHERIT.values())", main)
        self.assertIn("words = vv_last_names.OWN_RULES", own)
        self.assertIn("values=list(words.values())", own)
        # The window's check reads the village's ever-used names, and skips the drawn rules.
        self.assertIn("village_used = vv_last_names.village_names(folder, number, info.slot, people, parents, known)",
                      main)
        self.assertIn("vv_last_names.check_rules(recorded_own, own_state, living_keys), village_used,", main)
        self.assertIn("rule_key() not in vv_last_names.RANDOM_RULES", main)
        self.assertIn("Random from the existing Village Names", main)
        self.assertIn("a coin toss for each", own)
        self.assertIn("A villager's own rule always beats the village rule", own)
        self.assertNotIn("when they disagree, or neither has one, the village rule", own)


class VillageNamesInRepair(unittest.TestCase):
    def setUp(self):
        self.dad = person("Ago Bahati", "Male", 5, 6)
        self.mum = person("Aipi Wanjiko", "Female", 7, 8)
        self.other = person("Tiki Okelani", "Female", 3, 3)

    def kids(self, n: int, name: str = "Kid") -> list[ln.Living]:
        return [person(name, "Male", 9, 100 + k) for k in range(n)]

    def given(self, kids, rule="village", own=None, used=None, fits=None, pool=POOL, people=None):
        everyone = people if people is not None else [self.dad, self.mum, self.other, *kids]
        parents = {kid.identity: (self.dad.identity, self.mum.identity) for kid in kids}
        return ln.inherited(everyone, parents, rule, pool, None, carried, own, used, fits)

    def test_a_child_with_none_draws_one_the_village_has_used_evenly(self):
        kids = self.kids(1500)
        got = self.given(kids)
        counts = collections.Counter(got[k.identity] for k in kids)
        self.assertEqual(set(counts), {"Bahati", "Wanjiko", "Okelani"}, "only names the village has used")
        for name, n in counts.items():
            self.assertTrue(400 < n < 600, (name, n))
        self.assertEqual(got, self.given(kids), "the same each time for the same child")

    def test_a_carried_used_name_is_kept_the_games_draw(self):
        for have in ("Okelani", "Bahati", "Wanjiko"):
            [kid] = self.kids(1, f"Kid {have}")
            self.assertEqual(self.given([kid])[kid.identity], have)

    def test_the_record_and_the_dead_count(self):
        dead = person("Old Powaka", "Male", 1, 2, alive=False)
        kids = self.kids(300)
        got = self.given(kids, used={"Alpha"}, people=[self.dad, self.mum, dead, *kids])
        self.assertEqual({got[k.identity] for k in kids}, {"Alpha"},
                         "an explicit set is the whole set (village_names gathers the dead and the record)")
        got = self.given(kids, people=[self.dad, self.mum, dead, *kids])
        self.assertIn("Powaka", {got[k.identity] for k in kids}, "a dead villager's last name counts")

    def test_only_names_that_fit(self):
        kids = self.kids(200)
        fits = lambda v, last: len(last) <= 6  # noqa: E731
        got = self.given(kids, fits=fits)
        self.assertEqual({got[k.identity] for k in kids}, {"Bahati"})

    def test_the_lists_fallback_only_draws_names_that_fit(self):
        # Codex, PR #658: no used name fits, so the fallback drew from the whole list -- "Tasunke" for a
        # 16-letter first name, past The Secret City's 23 characters, though "Akikai" fits.
        pool = list(tools.load_checker().LAST_NAMES[3])
        dad, mum = person("Ago", "Male", 5, 6), person("Aipi", "Female", 7, 8)
        fits = ln.fitter(3)
        kids = [person("Longfirstnameabc", "Male", 9, n) for n in range(60)]
        parents = {kid.identity: (dad.identity, mum.identity) for kid in kids}
        got = ln.inherited([dad, mum, *kids], parents, "village", pool, None, carried, None, {"Reallylongname"}, fits)
        self.assertEqual(got[kids[0].identity], "Akikai", "Codex's example")
        for kid in kids:
            self.assertTrue(fits(kid, got[kid.identity]), got[kid.identity])
        # Nothing fits at all: the name is left as it is (the DLL leaves it too).
        tight = lambda v, last: False  # noqa: E731
        got = ln.inherited([dad, mum, *kids], parents, "village", pool, None, carried, None, {"Bahati"}, tight)
        self.assertEqual({got[k.identity] for k in kids}, {""})
        own = {ln.own_key(dad): "list"}
        got = ln.inherited([dad, mum, *kids], parents, "father", pool, None, carried, own, None, tight)
        self.assertEqual({got[k.identity] for k in kids}, {""}, "a parent's own list rule likewise")

    def test_none_ever_used_draws_from_the_list(self):
        dad, mum = person("Ago", "Male", 5, 6), person("Aipi", "Female", 7, 8)
        kids = self.kids(50)
        parents = {kid.identity: (dad.identity, mum.identity) for kid in kids}
        got = ln.inherited([dad, mum, *kids], parents, "village", POOL, None, carried, None, None)
        self.assertTrue(all(got[k.identity] in POOL for k in kids))

    def test_a_villager_with_no_recorded_parent_keeps_their_own(self):
        founder = person("Kito", "Male", 4, 4)
        got = ln.inherited([self.dad, founder], {}, "village", POOL, None, carried)
        self.assertEqual(got[self.dad.identity], "Bahati")
        self.assertNotIn(got[founder.identity], ("", "Bahati"), "a founder gets their own (separate)")

    def test_an_arrival_keeps_theirs(self):
        arrival = person("Ana", "Female", 2, 2, arrived=True)
        parents = {arrival.identity: (self.dad.identity, self.mum.identity)}
        got = ln.inherited([self.dad, self.mum, arrival], parents, "village", POOL, None, carried)
        self.assertEqual(got[arrival.identity], "")

    def test_a_parents_own_village_rule_beats_the_villages_from_the_father(self):
        kids = self.kids(300)
        got = self.given(kids, rule="father", own={ln.own_key(self.mum): "village"})
        self.assertEqual({got[k.identity] for k in kids}, {"Bahati", "Wanjiko", "Okelani"})

    def test_the_lasts_in_use(self):
        people = [self.dad, person("Kid Wanjiko II", "Male"), person("Solo", "Female"),
                  person("Odd Two%", "Female")]
        parents = {people[1].identity: (("Gone Powaka", 1, 1), None)}
        self.assertEqual(ln.lasts_in_use(people, parents, carried), {"Bahati", "Wanjiko", "Powaka"},
                         "a numeral passed over, no one-word name, nothing the games cannot store")


class DisagreeingOwnRules(unittest.TestCase):
    """Every combination of two different own rules: the child's carried name is kept when either rule
    gives it; a child whose name neither gives gets the one own_coin picks -- never the village's."""

    def setUp(self):
        self.dad = person("Ago Bahati", "Male", 5, 6)
        self.mum = person("Aipi Wanjiko", "Female", 7, 8)

    def outcome(self, kid, father_rule, mother_rule, village="each"):
        own = {ln.own_key(self.dad): father_rule, ln.own_key(self.mum): mother_rule}
        parents = {kid.identity: (self.dad.identity, self.mum.identity)}
        return ln.inherited([self.dad, self.mum, kid], parents, village, POOL, None, carried, own,
                            {"Bahati", "Wanjiko", "Okelani"})[kid.identity]

    def test_every_pair(self):
        rules = ("father", "mother", "random", "list", "village")
        gives = {"father": {"Bahati"}, "mother": {"Wanjiko"}, "random": {"Bahati", "Wanjiko"},
                 "list": set(POOL), "village": {"Bahati", "Wanjiko", "Okelani"}}
        for f in rules:
            for m in rules:
                if f == m:
                    continue
                with self.subTest(father=f, mother=m):
                    allowed = gives[f] | gives[m]
                    for have in ("Bahati", "Wanjiko", "Okelani", "Ln07"):
                        kid = person(f"Kid {have}", "Male", 9, 9)
                        got = self.outcome(kid, f, m)
                        self.assertEqual(got, have) if have in allowed else self.assertIn(got, allowed)
                    reached = set()
                    for k in range(80):
                        kid = person("Kid", "Male", 9, 200 + k)
                        got = self.outcome(kid, f, m)
                        self.assertIn(got, allowed)
                        reached.add("father" if got in gives[f] and got not in gives[m] else
                                    "mother" if got in gives[m] and got not in gives[f] else "both")
                    self.assertTrue({"father", "mother"} <= reached or "both" in reached, reached)

    def test_the_check_takes_either_parents_name_as_right(self):
        own = {ln.own_key(self.dad): "father", ln.own_key(self.mum): "mother"}
        kid = person("Kid Wanjiko", "Male", 9, 9)
        parents = {kid.identity: (self.dad.identity, self.mum.identity)}
        should, used, either = ln.expected_last_names([self.dad, self.mum, kid], parents, "father", POOL, {},
                                                      carried, own)[kid.identity]
        self.assertEqual(should, "Wanjiko")
        self.assertIn(used, ("father", "mother"))
        self.assertEqual(either, ("Bahati", "Wanjiko"))
        self.assertFalse(ln.wrong_last_name("Bahati", should, either))
        self.assertTrue(ln.wrong_last_name("Okelani", should, either))


class TheRecord(unittest.TestCase):
    def test_used_lines_round_trip_and_never_shrink(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            own = {("Ago Bahati", 5, 6, "Male"): "village"}
            ln.write_record(folder, 3, 1, "village", {("Chapa", 1, 1): "Chapstick"}, {"Big Bob"}, own,
                            used={"Bahati", "Élan", "Two Words", "Bad%", ""})
            text = ln.record_path(folder, 3, 1).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("VVFP LAST NAMES v1 game=3\nrule\tvillage\n"))
            self.assertIn("villager\tAgo Bahati\t5\t6\tM\tvillage\n", text)
            self.assertIn("used\tBahati\n", text)
            self.assertIn("used\tÉlan\n", text)
            self.assertNotIn("Two Words", text)
            self.assertNotIn("Bad%", text)
            self.assertEqual(ln.read_record(folder, 3, 1), ("village", {("Chapa", 1, 1): "Chapstick"}))
            self.assertEqual(ln.read_own(folder, 3, 1), own)
            self.assertEqual(ln.read_used(folder, 3, 1), {"Bahati", "Élan"})
            ln.write_record(folder, 3, 1, "father", {}, used={"Okelani"})
            self.assertEqual(ln.read_used(folder, 3, 1), {"Bahati", "Élan", "Okelani"}, "only ever added to")
            ln.save_arrivals(folder, 3, 1, False, NoGame())
            self.assertEqual(ln.read_used(folder, 3, 1), {"Bahati", "Élan", "Okelani"})

    def test_repair_reads_the_lines_the_game_adds_back_unchanged(self):
        # VVFP Last Names.dll appends "used" lines at a birth (persist_used; Codex, PR #661): the record as
        # it was, byte for byte, then "used\t<last name>" in UTF-8 -- as the harness's section 14 checks.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = ln.record_path(folder, 3, 1)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"VVFP LAST NAMES v1 game=3\nrule\tvillage\nwhole\tBig Bob\n"
                             b"used\tZephyr\nused\t\xc3\x89lan\n")
            self.assertEqual(ln.read_used(folder, 3, 1), {"Zephyr", "\u00c9lan"})
            self.assertEqual(ln.read_record(folder, 3, 1)[0], "village")
            self.assertEqual(ln.read_whole(folder, 3, 1), {"Big Bob"})
            ln.write_record(folder, 3, 1, "village", {}, used={"Bahati"})
            text = path.read_bytes()
            for line in (b"used\tZephyr\n", b"used\t\xc3\x89lan\n", b"used\tBahati\n", b"whole\tBig Bob\n"):
                self.assertIn(line, text, "Repair keeps the game's lines as they are")

    def test_an_earlier_builds_reader_skips_the_new_lines(self):
        """v1.35.85's readers, as they were: the rule must be one of its INHERIT, an own line's rule one of
        its OWN_RULES; any other line is skipped.  They read "village" as no rule ("From the father") and
        keep reading everything else."""
        old_inherit = {"mother", "father", "random", "list", "each"}
        old_own = {"father", "mother", "random", "list"}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            ln.write_record(folder, 2, 1, "village", {("Chapa", 1, 1): "Chapstick"}, {"Big Bob"},
                            {("Ago", 5, 6, "Male"): "village", ("Aipi", 7, 8, "Female"): "mother"},
                            used={"Bahati"})
            lines = ln.record_path(folder, 2, 1).read_text(encoding="utf-8").splitlines()
        rule, fixed, own = None, {}, {}
        for line in lines[1:]:
            parts = line.split("\t")
            if parts[0] == "rule" and len(parts) == 2 and parts[1] in old_inherit:
                rule = parts[1]
            elif parts[0] == "set" and len(parts) == 5:
                fixed[(parts[1], int(parts[2]), int(parts[3]))] = parts[4]
            elif parts[0] == "villager" and len(parts) == 6 and parts[5] in old_own:
                own[parts[1]] = parts[5]
        self.assertIsNone(rule, "no rule: the village shows and gives From the father")
        self.assertEqual(fixed, {("Chapa", 1, 1): "Chapstick"})
        self.assertEqual(own, {"Aipi": "mother"}, "a villager's own 'village' is no own rule there")
        # And the DLL of v1.35.85: its village rule wants six letters and its own_line_of four or six.
        self.assertEqual(len("village"), 7)

    def test_a_renamed_last_bearers_surname_stays_used(self):
        # Codex, PR #658: the used names were read only after the renames, so renaming the last bearer of a
        # surname (rules unchanged: the window then skips save_own_rules) lost it from the record.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            save(folder, [entry("Ago Bahati", 0, 1, 5, 6), entry("Aipi Wanjiko", 1, 50, 7, 8)])
            ln.write_record(folder, 3, 1, "father", {})
            self.assertEqual(ln.read_used(folder, 3, 1), set(), "no used lines yet")
            ago = {v.name: v for v in ln.living(folder, 3, 1)}["Ago Bahati"]
            ln.give_last_names(folder, 3, 1, {ago.identity: "Okelani"}, NoGame(), rule="father")
            self.assertEqual([v.name for v in ln.living(folder, 3, 1)], ["Ago Okelani", "Aipi Wanjiko"])
            self.assertEqual(ln.read_used(folder, 3, 1), {"Bahati", "Okelani", "Wanjiko"},
                             "the surname before the rename, and the ones after")

    def test_repair_keeps_the_villages_names_when_it_keeps_the_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            save(folder, [entry("Ago Bahati", 0, 1, 5, 6), entry("Aipi Wanjiko", 1, 50, 7, 8),
                          entry("Tiki Okelani II", 1, 3, 3, 3)])
            ln.write_record(folder, 3, 1, "father", {}, used={"Powaka"})
            ln.save_own_rules(folder, 3, 1, "village", {("Ago Bahati", 5, 6, "Male"): "village"}, NoGame())
            self.assertEqual(ln.read_record(folder, 3, 1)[0], "village")
            self.assertEqual(ln.read_used(folder, 3, 1), {"Bahati", "Wanjiko", "Okelani", "Powaka"})
            self.assertEqual(ln.village_names(folder, 3, 1), {"Bahati", "Wanjiko", "Okelani", "Powaka"})


if __name__ == "__main__":
    unittest.main()
