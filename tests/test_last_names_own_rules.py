"""Each villager's own last-name rule (the owner, 2026-10-09).

"Can you add a feature to set inheritance settings per-villager in addition to the existing Global
Settings? (so certain villagers can pass their last name with different rules from the rest of the
village, ie so that half the village doesn't inherit a single person's last name)".

A living villager may have a rule of their own for their children's last name -- From the father, From
the mother or 50:50 -- or use the village's.  At a birth one parent's own rule is used, both parents'
when they agree, and the village's when they disagree or neither has one.  The rules are kept in the
village's Last Names record as "villager" lines, keyed by the whole name, head, body and sex
(src/vv_last_names.py); VVFP Last Names.dll's VvfpRuleLastName2 reads them at each birth
(native/vvfp_last_names/last_names_harness.c runs it over every combination).
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_last_names_rename import NoGame, Running, TABLE, entry  # noqa: E402

NATIVE = ROOT / "native" / "vvfp_last_names"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
HARNESS_CHECKS = 4 * 4 * 5 + 8 + 1 + 2 + 3 + 10
NOW = datetime(2026, 10, 9, 12, 0, 0)
RULES = (None, "father", "mother", "random")


def person(name: str, sex: str, head: int = 1, body: int = 1, alive: bool = True) -> ln.Living:
    return ln.Living(0, name, sex, head, body, 1, "Akikai", alive=alive)


class TheBirthsRule(unittest.TestCase):
    def test_every_combination_of_the_parents_and_the_village(self):
        for father in RULES:
            for mother in RULES:
                for village in (*RULES, "list", "each"):
                    with self.subTest(father=father, mother=mother, village=village):
                        if father and mother:
                            want = father if father == mother else village
                        else:
                            want = father or mother or village
                        self.assertEqual(ln.decide(father, mother, village), want)

    def test_the_owners_four_cases(self):
        self.assertEqual(ln.decide("mother", None, "father"), "mother", "only one parent has one: theirs")
        self.assertEqual(ln.decide(None, "random", "father"), "random")
        self.assertEqual(ln.decide("mother", "mother", "father"), "mother", "both, the same: that one")
        self.assertEqual(ln.decide("mother", "random", "father"), "father", "both, disagreeing: the village's")
        self.assertEqual(ln.decide(None, None, "father"), "father", "neither: the village's")


class InheritedFollowsTheOwnRules(unittest.TestCase):
    """What the last-names list marks as right (and Fix wrong last names gives) follows the same rule."""

    def setUp(self):
        self.dad = person("Ago Bahati", "Male", 5, 6)
        self.mum = person("Aipi Wanjiko", "Female", 7, 8)
        self.kid = person("Kid", "Male", 9, 9)
        self.people = [self.dad, self.mum, self.kid]
        self.parents = {self.kid.identity: (self.dad.identity, self.mum.identity)}

    def given(self, rule: str, own: dict) -> str:
        carried = lambda name: ln.split_name(3, name)[1]  # noqa: E731
        return ln.inherited(self.people, self.parents, rule, None, None, carried, own)[self.kid.identity]

    def test_a_fathers_own_from_the_mother_beats_the_village_from_the_father(self):
        self.assertEqual(self.given("father", {}), "Bahati")
        self.assertEqual(self.given("father", {ln.own_key(self.dad): "mother"}), "Wanjiko")

    def test_disagreeing_parents_use_the_village_rule(self):
        own = {ln.own_key(self.dad): "mother", ln.own_key(self.mum): "father"}
        self.assertEqual(self.given("father", own), "Bahati")
        self.assertEqual(self.given("mother", own), "Wanjiko")

    def test_agreeing_parents_use_theirs(self):
        own = {ln.own_key(self.dad): "mother", ln.own_key(self.mum): "mother"}
        self.assertEqual(self.given("father", own), "Wanjiko")

    def test_an_own_rule_decides_even_under_a_player_chosen_village_rule(self):
        self.assertEqual(self.given("each", {ln.own_key(self.dad): "mother"}), "Wanjiko")
        self.assertEqual(self.given("each", {}), "")

    def test_a_namesake_with_other_looks_or_sex_is_not_them(self):
        self.people.append(person("Ago Bahati", "Male", 5, 7))         # a living namesake with those looks
        self.assertEqual(self.given("father", {("Ago Bahati", 5, 7, "Male"): "mother"}), "Bahati")
        self.assertEqual(self.given("father", {("Ago Bahati", 5, 6, "Female"): "mother"}), "Bahati")
        self.people.pop()
        # With no living villager of those looks, the one line of his name and sex is his after a change
        # of looks no record told of.
        self.assertEqual(self.given("father", {("Ago Bahati", 5, 7, "Male"): "mother"}), "Wanjiko")


class TheRecordFile(unittest.TestCase):
    def test_lines_round_trip_beside_everything_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            own = {("Ago Bahati", 5, 6, "Male"): "mother", ("\u00c9lodie", 7, 8, "Female"): "random"}
            ln.write_record(folder, 2, 1, "father", {("Chapa", 1, 1): "Chapstick"}, {"Big Bob"}, own)
            text = ln.record_path(folder, 2, 1).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("VVFP LAST NAMES v1 game=2\nrule\tfather\n"), "the v1 header kept")
            self.assertIn("villager\tAgo Bahati\t5\t6\tM\tmother\n", text)
            self.assertIn("villager\t\u00c9lodie\t7\t8\tF\trandom\n", text)
            self.assertEqual(ln.read_own(folder, 2, 1), own)
            # The readers that do not know the lines skip them.
            self.assertEqual(ln.read_record(folder, 2, 1), ("father", {("Chapa", 1, 1): "Chapstick"}))
            self.assertEqual(ln.read_whole(folder, 2, 1), {"Big Bob"})
            # A later write that does not name them keeps them (Give last names writes the rule).
            ln.write_record(folder, 2, 1, "mother", {})
            self.assertEqual(ln.read_own(folder, 2, 1), own)
            ln.write_record(folder, 2, 1, "mother", {}, own={})
            self.assertEqual(ln.read_own(folder, 2, 1), {})

    def test_malformed_or_clashing_lines_give_no_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = ln.record_path(folder, 3, 1)
            path.parent.mkdir(parents=True)
            path.write_text("VVFP LAST NAMES v1 game=3\nrule\tfather\n"
                            "villager\tAgo\t5\t6\tM\tmother\nvillager\tAgo\t5\t6\tM\tfather\n"
                            "villager\tKito\tx\t6\tM\tmother\nvillager\tKito\t1\t6\tQ\tmother\n"
                            "villager\tKito\t1\t6\tM\tlist\nvillager\tAipi\t7\t8\tF\tmother\n", encoding="utf-8")
            self.assertEqual(ln.read_own(folder, 3, 1), {("Aipi", 7, 8, "Female"): "mother"})
            path.write_text("VVFP LAST NAMES v1 game=2\nvillager\tAipi\t7\t8\tF\tmother\n", encoding="utf-8")
            self.assertEqual(ln.read_own(folder, 3, 1), {}, "another game's record")

    def test_indistinguishable_villagers_are_found(self):
        a, b = person("Soda", "Female", 3, 3), person("Soda", "Female", 3, 3)
        c, d = person("Soda", "Female", 3, 4), person("Soda", "Male", 3, 3)
        gone = person("Kito", "Male", alive=False)
        self.assertEqual(ln.indistinguishable([a, b, c, d, gone, person("Kito", "Male")]),
                         {("Soda", 3, 3, "Female"): [a, b]})


def save(folder: Path, people: list[bytes]) -> Path:
    path = folder / "Virtual Villagers - The Secret City1.ldw"
    path.write_bytes(bytes(bytearray(b"ldwg" + bytes(TABLE - 4)) + b"".join(people) + bytes(64)))
    return path


class SavingTheRules(unittest.TestCase):
    """Repair Saves & Logs keeps the rules with the game closed, for the living only."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        save(self.folder, [
            entry("Ago Bahati", 0, 1, 5, 6),
            entry("Aipi Wanjiko", 1, 50, 7, 8, expecting=("Dead Dad", 2, 2)),
            entry("Soda", 1, 2, 3, 3),
            entry("Soda", 1, 2, 3, 3),
        ])
        self.people = {(v.name, v.head): v for v in ln.living(self.folder, 3, 1)}

    def tearDown(self):
        self.tmp.cleanup()

    def test_kept_with_the_village_rule(self):
        ago = ln.own_key(self.people[("Ago Bahati", 5)])
        kept = ln.save_own_rules(self.folder, 3, 1, "father", {ago: "mother"}, NoGame())
        self.assertEqual(kept, {ago: "mother"})
        self.assertEqual(ln.read_record(self.folder, 3, 1)[0], "father")
        self.assertEqual(ln.read_own(self.folder, 3, 1), {ago: "mother"})
        # "Use the village rule" takes it away.
        ln.save_own_rules(self.folder, 3, 1, "father", {ago: ""}, NoGame())
        self.assertEqual(ln.read_own(self.folder, 3, 1), {})

    def test_refused_while_the_game_runs(self):
        ago = ln.own_key(self.people[("Ago Bahati", 5)])
        with self.assertRaises((ln.LastNamesError, tools.LogToolError)):
            ln.save_own_rules(self.folder, 3, 1, "father", {ago: "mother"}, Running())
        self.assertFalse(ln.record_path(self.folder, 3, 1).exists())

    def test_namesakes_no_birth_could_tell_apart_are_refused(self):
        soda = ln.own_key(self.people[("Soda", 3)])
        with self.assertRaisesRegex(ln.LastNamesError, "same name, looks and sex"):
            ln.save_own_rules(self.folder, 3, 1, "father", {soda: "mother"}, NoGame())
        self.assertFalse(ln.record_path(self.folder, 3, 1).exists(), "nothing written")

    def test_only_a_living_villager(self):
        with self.assertRaisesRegex(ln.LastNamesError, "not a living villager"):
            ln.save_own_rules(self.folder, 3, 1, "father", {("Nobody", 1, 1, "Male"): "mother"}, NoGame())

    def test_the_dead_keep_none_but_an_expected_father_keeps_his(self):
        ln.write_record(self.folder, 3, 1, "father", {}, own={
            ("Dead Dad", 2, 2, "Male"): "mother",           # Aipi is expecting his baby
            ("Gone Guy", 4, 4, "Male"): "mother"})          # nobody is
        kept = ln.save_own_rules(self.folder, 3, 1, "mother", {}, NoGame())
        self.assertEqual(kept, {("Dead Dad", 2, 2, "Male"): "mother"})
        self.assertEqual(ln.read_own(self.folder, 3, 1), kept)

    def test_a_delivered_mothers_stale_expected_father_keeps_nothing(self):
        # The game leaves the expected father's name on her after the birth; her pregnancy field
        # (0 once delivered) decides, as the Population log's "Nursing" does (v1.35.66 live).
        save(self.folder, [entry("Aipi Wanjiko", 1, 50, 7, 8, expecting=("Dead Dad", 2, 2), pregnant=0)])
        ln.write_record(self.folder, 3, 1, "father", {}, own={("Dead Dad", 2, 2, "Male"): "mother"})
        self.assertEqual(ln.save_own_rules(self.folder, 3, 1, "mother", {}, NoGame()), {})


class RenamesCarryTheRule(unittest.TestCase):
    """Give last names, Number Duplicate Names and restoring cut names all rename through plan_renames;
    the villager's line follows them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        save(self.folder, [entry("Ago", 0, 1, 5, 6), entry("Aipi", 1, 50, 7, 8)])
        ln.write_record(self.folder, 3, 1, "father", {}, own={
            ("Ago", 5, 6, "Male"): "mother", ("Ago", 1, 1, "Male"): "random", ("Aipi", 7, 8, "Female"): "father"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_give_last_names(self):
        people = {v.name: v for v in ln.living(self.folder, 3, 1)}
        ln.give_last_names(self.folder, 3, 1, {people["Ago"].identity: "Akikai"}, NoGame(), NOW, rule="father")
        own = ln.read_own(self.folder, 3, 1)
        self.assertEqual(own[("Ago Akikai", 5, 6, "Male")], "mother")
        self.assertEqual(own[("Ago", 1, 1, "Male")], "random", "another Ago (other looks) is not him")
        self.assertEqual(own[("Aipi", 7, 8, "Female")], "father")
        self.assertNotIn(("Ago", 5, 6, "Male"), own)

    def test_number_duplicate_names_and_the_dead(self):
        work = ln.plan_renames(self.folder, 3, 1, {("Ago", 5, 6): "Ago I", ("Ago", 1, 1): "Ago II"}, dead=True)
        [change] = [c for c in work.changes if c.path == ln.record_path(self.folder, 3, 1)]
        text = change.updated.decode("utf-8")
        self.assertIn("villager\tAgo I\t5\t6\tM\tmother\n", text)
        self.assertIn("villager\tAgo II\t1\t1\tM\trandom\n", text)
        self.assertIn("villager\tAipi\t7\t8\tF\tfather\n", text)


class TheCompanionsPassTheLooks(unittest.TestCase):
    def test_both_parentage_companions_call_the_rule_with_names_and_looks(self):
        export = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn('GetProcAddress(dll, "VvfpRuleLastName2")', export)
        self.assertIn("father, *(const int *)(rec + g->parent_father_head), *(const int *)(rec + g->parent_father_body),",
                      export)
        self.assertIn("mother, *(const int *)(rec + g->parent_mother_head), *(const int *)(rec + g->parent_mother_body),",
                      export)
        vv1 = (ROOT / "native" / "vv1_parentage" / "vv1_parentage.c").read_text(encoding="utf-8")
        self.assertIn('GetProcAddress(dll, "VvfpRuleLastName2")', vv1)
        # A New Home's entry keeps each look + 1: a real head or body 0 is 1 there, and 0 is "not recorded"
        # (an earlier build's entry) -- then the one living villager of that name and sex, if only one.
        self.assertIn("fh = e->father_head && e->father_body ? e->father_head - 1 : -1;", vv1)
        self.assertIn("mb = e->mother_head && e->mother_body ? e->mother_body - 1 : -1;", vv1)
        self.assertIn("vv1_only_looks(e->father_name, 1, &fh, &fb);", vv1)
        self.assertIn("rule(name, VV1_NAME_CAPACITY, e->father_name, fh, fb, e->mother_name, mh, mb, slot)", vv1)
        self.assertIn("unsigned char father_head, father_body;   /* +1; 0 = unknown */", vv1)
        only = vv1[vv1.index("static void vv1_only_looks("):]
        self.assertIn("if (found == 1 && h >= 0 && b >= 0) {", only[:1200])
        definition = (NATIVE / "vvfp_last_names.def").read_text(encoding="utf-8")
        self.assertIn("VvfpRuleLastName2=_VvfpRuleLastName2@36", definition)
        self.assertNotIn("VvfpRuleLastName=", definition)


class HeadAndBodyZeroAreRealLooks(unittest.TestCase):
    """Head 0 / body 0 is a villager's real look (the first of each list), never "unknown"."""

    def test_a_parent_with_head_0_and_body_0_keeps_their_rule(self):
        dad, mum, kid = person("Ago Bahati", "Male", 0, 0), person("Aipi Wanjiko", "Female", 0, 0), person("Kid", "Male")
        carried = lambda name: ln.split_name(2, name)[1]  # noqa: E731
        parents = {kid.identity: (dad.identity, mum.identity)}
        for own, want in (({ln.own_key(dad): "mother"}, "Wanjiko"), ({ln.own_key(mum): "mother"}, "Wanjiko"),
                          ({}, "Bahati")):
            with self.subTest(own=own):
                self.assertEqual(ln.inherited([dad, mum, kid], parents, "father", None, None, carried, own)[kid.identity],
                                 want)

    def test_kept_and_read_back_with_head_0_and_body_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            save(folder, [entry("Ago Bahati", 0, 1, 0, 0), entry("Aipi", 1, 50, 7, 8)])
            ago = ("Ago Bahati", 0, 0, "Male")
            self.assertEqual(ln.save_own_rules(folder, 3, 1, "father", {ago: "mother"}, NoGame()), {ago: "mother"})
            self.assertIn("villager\tAgo Bahati\t0\t0\tM\tmother\n", ln.record_path(folder, 3, 1).read_text("utf-8"))
            self.assertEqual(ln.read_own(folder, 3, 1), {ago: "mother"})

    def test_the_lost_children_to_new_believers_pass_the_childs_record_looks_as_they_are(self):
        export = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        rule = export[export.index("static void rule_last_name("):]
        rule = rule[:rule.index("\n}\n")]
        self.assertNotIn("? -1", rule, "no value of a look is taken for unknown")
        native = (NATIVE / "vvfp_last_names.c").read_text(encoding="utf-8")
        self.assertIn("if (name == NULL || name[0] == '\\0' || head < 0 || body < 0) {", native)


class ARuleFollowsAChangeOfLooks(unittest.TestCase):
    """The coordinator, 2026-10-09: a look change (an island event changed Papu's head in the owner's A
    New Home) must not leave the villager's rule behind."""

    def test_every_appearance_record_re_keys_the_line_in_the_game(self):
        export = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn('    } else if (kind == KIND_APPEARANCE) {\n        heading = "Appearance changed\\n";\n'
                      '        relook_last_name(g, record, before);\n', export)
        self.assertIn('GetProcAddress(dll, "VvfpRelookLastName")', export)
        self.assertIn('"  Old head: %d\\n  Old body: %d\\n  New head: %d\\n  New body: %d"', export)
        self.assertIn("VvfpRelookLastName=_VvfpRelookLastName@28",
                      (NATIVE / "vvfp_last_names.def").read_text(encoding="utf-8"))
        # Every writer of an "Appearance changed" record hands over those four lines first.
        for path in (ROOT / "native" / "shared" / "appearance_log.h",
                     ROOT / "native" / "vvfp_island_events" / "vvfp_island_events.c"):
            with self.subTest(writer=path.name):
                self.assertIn('"  Old head: %d\\n  Old body: %d\\n  New head: %d\\n  New body: %d\\n"',
                              path.read_text(encoding="utf-8"))

    def test_repair_re_keys_a_line_whose_looks_changed_with_no_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            save(folder, [entry("Papu", 0, 1, 9, 6), entry("Papu", 1, 2, 9, 6), entry("Aipi", 1, 50, 7, 8)])
            ln.write_record(folder, 3, 1, "father", {}, own={("Papu", 3, 6, "Male"): "mother",
                                                            ("Aipi", 1, 1, "Female"): "random"})
            people = ln.living(folder, 3, 1)
            now = ln.own_rules_now(folder, 3, 1, people)
            self.assertEqual(now[("Papu", 9, 6, "Male")], "mother", "the one Papu (male) with no line of his own")
            self.assertEqual(now[("Aipi", 7, 8, "Female")], "random")
            kept = ln.save_own_rules(folder, 3, 1, "father", now, NoGame())
            self.assertEqual(ln.read_own(folder, 3, 1), kept)
            self.assertIn(("Papu", 9, 6, "Male"), kept, "re-keyed at the save")

    def test_not_when_it_could_be_two_villagers(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            save(folder, [entry("Papu", 0, 1, 9, 6), entry("Papu", 0, 2, 4, 4)])
            ln.write_record(folder, 3, 1, "father", {}, own={("Papu", 3, 6, "Male"): "mother"})
            self.assertEqual(ln.own_rules_now(folder, 3, 1, ln.living(folder, 3, 1)),
                             {("Papu", 3, 6, "Male"): "mother"}, "two Papus with no line: neither")
            # A living villager who still has the line's looks keeps it.
            ln.write_record(folder, 3, 1, "father", {}, own={("Papu", 9, 6, "Male"): "mother"})
            self.assertEqual(ln.own_rules_now(folder, 3, 1, ln.living(folder, 3, 1)),
                             {("Papu", 9, 6, "Male"): "mother"})

    def test_a_birth_finds_the_parent_after_a_change_of_looks(self):
        mum, kid = person("Aipi Wanjiko", "Female", 7, 8), person("Kid", "Male")
        dad = person("Papu Bahati", "Male", 9, 6)        # his looks now: 9 / 6, changed with no record
        carried = lambda name: ln.split_name(3, name)[1]  # noqa: E731
        parents = {kid.identity: (dad.identity, mum.identity)}
        own = {("Papu Bahati", 3, 6, "Male"): "mother"}   # set while he looked 3 / 6
        self.assertEqual(ln.inherited([dad, mum, kid], parents, "father", None, None, carried, own)[kid.identity],
                         "Wanjiko", "the one line of his name and sex, whose looks nobody living has")
        twin = person("Papu Bahati", "Male", 3, 6)        # a living namesake has those looks: not him
        self.assertEqual(ln.inherited([dad, twin, mum, kid], parents, "father", None, None, carried, own)
                         [kid.identity], "Bahati")
        # A child conceived before the change keeps his old looks on its record: the in-game re-key keeps
        # the old line beside the new one (VvfpRelookLastName), so both are found.
        both = {("Papu Bahati", 3, 6, "Male"): "mother", ("Papu Bahati", 9, 6, "Male"): "mother"}
        for looks in ((3, 6), (9, 6)):
            parents = {kid.identity: (("Papu Bahati", *looks), mum.identity)}
            self.assertEqual(ln.inherited([dad, mum, kid], parents, "father", None, None, carried, both)
                             [kid.identity], "Wanjiko")


class TheRowsReadAsTheLastNamesWindow(unittest.TestCase):
    """The owner (Preview 11): the own-rule window's rows read as the last-names window's -- name, sex,
    parents, "arrived" -- and never show a head or body value ("and no body/head value"); rows that would
    read alike are told apart by age, then by "1 of 2"."""

    def rows(self, people, parents):
        import vv_fun_patcher_gui as gui
        return gui.last_name_rows(people, parents)

    def test_the_main_windows_format(self):
        goro = ln.Living(0, "Goro Wanjiko", "Male", 3, 4, 1, "", age=400)
        iruwa = ln.Living(0, "Iruwa Bandele", "Female", 0, 0, 1, "", arrived=True, age=500)
        copy = ln.Living(0, "Kito", "Male", 5, 5, 1, "", arrived=True, age=500)
        gone = ln.Living(-1, "Chika", "Female", 6, 6, 0, "", alive=False, age=900)
        parents = {goro.identity: (("Kito Wanjiko", 1, 1), ("Chika Helaku", 2, 2)),
                   copy.identity: (("Ago", 1, 1), None)}
        self.assertEqual(self.rows([goro, iruwa, copy, gone], parents), [
            "Goro Wanjiko (Male) -- father Kito Wanjiko, mother Chika Helaku",
            "Iruwa Bandele (Female) -- arrived",
            "Kito (Male) -- father Ago, mother unknown -- arrived",
            "Chika (Female, no longer in the village)",
        ])

    def test_namesakes_by_age_then_by_number_never_by_looks(self):
        pa = (("Kito", 1, 1), ("Chika", 2, 2))
        twin1 = ln.Living(0, "Soda", "Female", 0, 0, 1, "", age=40)
        twin2 = ln.Living(0, "Soda", "Female", 0, 1, 1, "", age=40)      # same-named twins
        older = ln.Living(0, "Soda", "Female", 7, 7, 1, "", age=0)       # age 0 is a real age
        lone = ln.Living(0, "Ago", "Male", 0, 0, 1, "", age=0)
        parents = {twin1.identity: pa, twin2.identity: pa, older.identity: pa}
        rows = self.rows([twin1, older, twin2, lone], parents)
        self.assertEqual(rows, [
            "Soda (Female) -- father Kito, mother Chika -- aged 2 -- 1 of 2",
            "Soda (Female) -- father Kito, mother Chika -- aged 0",
            "Soda (Female) -- father Kito, mother Chika -- aged 2 -- 2 of 2",
            "Ago (Male)",
        ])
        for row in rows:
            self.assertNotRegex(row, r"head|body")

    def test_both_windows_use_it_and_scroll(self):
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        main = source[source.index("    def _last_names_dialog("):source.index("    def _own_rules_dialog(")]
        own = source[source.index("    def _own_rules_dialog("):source.index("    def _repair_questions(")]
        self.assertIn("for row, (v, who) in enumerate(zip(people, last_name_rows(people, parents))):", main)
        self.assertIn("shown = [v for v in people if v.alive]", own)
        self.assertIn("for row, (v, who) in enumerate(zip(shown, last_name_rows(shown, parents))):", own)
        self.assertIn("window.resizable(True, True)", own)
        self.assertIn('bar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)', own)
        self.assertIn("canvas.configure(yscrollcommand=bar.set)", own)
        for text in (main, own):
            self.assertNotRegex(text, r"head \{|body \{|v\.head\}|v\.body\}")

@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class OwnRulesHarness(unittest.TestCase):
    def test_every_combination_in_the_shipped_code(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_last_names_harness_") as out:
            exe = Path(out) / "last_names_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 str(NATIVE / "last_names_harness.c"),
                 "/link",
                 f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
                 f"/OUT:{exe}", "kernel32.lib", "shell32.lib"],
                capture_output=True, text=True, cwd=out, timeout=600,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(exe), str(Path(out) / "documents")], capture_output=True, text=True,
                                    cwd=out, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"== {HARNESS_CHECKS} check(s), 0 failure(s) ==", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), HARNESS_CHECKS, result.stdout)


if __name__ == "__main__":
    unittest.main()
