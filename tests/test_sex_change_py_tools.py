"""Every patcher tool that matches villagers by name and sex follows a villager whose sex changed
(native/shared/sex_change.h; src/vv_sex_changes.py's one rule: the same sex, or a name the save's "Sex
Changes" log -- or an Appearance changed record's Old sex / New sex -- names).  Without the log the old
behaviour holds."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_genealogy as gen  # noqa: E402
import vv_history_revision as hr  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_log_contradictions as contradictions  # noqa: E402
import vv_lost_titles as lt  # noqa: E402
import vv_misfiled_records as misfiled  # noqa: E402
import vv_reconcile as rc  # noqa: E402
import vv_save_layout as layout  # noqa: E402
import vv_titles_file as titles_file  # noqa: E402
import vv_vv2_totems as totems  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"


def sex_log(folder: Path, slot: int, text: str) -> None:
    path = folder / layout.save_root(slot) / layout.SAVE_DATA / "Sex Changes" / f"Sex Changes - Save {slot}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("cp1252"))


class Temp(unittest.TestCase):
    def folder(self) -> Path:
        return Path(self.enterContext(tempfile.TemporaryDirectory(prefix="vvsex")))


class FalseUnaccounted(Temp):
    """A villager who moved to another record AND whose sex changed between the two checks: the Left and
    Arrived records are the same villager once the log names them (vv_log_contradictions)."""

    def make(self, folder: Path) -> None:
        import test_false_unaccounted as fu
        unaccounted = (fu.VILLAGE + "\n" + fu.unacc(1, "Mover", "Left", 300, "Male", 1, 1)
                       + fu.unacc(2, "Mover", "Arrived", 301, "Female", 1, 1))
        fu.make(folder, 2, unaccounted=unaccounted, history=fu.VILLAGE + "\n")

    def test_the_pair_is_false_only_with_the_log(self):
        folder = self.folder()
        self.make(folder)
        verdicts = {v.block.heading: v for v in contradictions.false_unaccounted(folder, 2, 1)}
        self.assertFalse(verdicts["Unaccounted 1"].false)
        sex_log(folder, 1, "M\tF\tMover\r\n")
        verdicts = {v.block.heading: v for v in contradictions.false_unaccounted(folder, 2, 1)}
        self.assertTrue(verdicts["Unaccounted 1"].false)
        self.assertTrue(verdicts["Unaccounted 2"].false)

    def test_a_birth_record_of_the_old_sex_fits(self):
        class R:
            heading = "Arrived 1"
            identity = ("Ann", 3, 4)

            @staticmethod
            def value(label):
                return "Male" if label == "Sex" else None
        self.assertFalse(contradictions._record_fits(R, {"Ann"}, "Female", 3, 4))
        self.assertTrue(contradictions._record_fits(R, {"Ann"}, "Female", 3, 4, {"Ann"}))
        self.assertTrue(contradictions._record_fits(R, {"Ann"}, "Male", 3, 4))


class HistoryRevision(Temp):
    def test_the_sex_check_follows_the_log(self):
        p = hr.Person("Ann", 3, 4, sexes={"Male"})
        self.assertFalse(hr._sex_ok(p, "Female"))
        self.assertTrue(hr._sex_ok(p, "Female", {"Ann"}))
        self.assertTrue(hr._sex_ok(p, "Male"))


class Titles(unittest.TestCase):
    def test_could_be_accepts_the_other_sex_only_after_a_change(self):
        e = titles_file.Entry(0, 1, "Chief", known=True, age=10, head=3, body=4, sex=1)
        looks = dict(age=20, head=3, body=4, sex=0, skills=(0,) * titles_file.SKILLS)
        self.assertFalse(titles_file.could_be(3, e, looks))
        self.assertTrue(titles_file.could_be(3, e, looks, True))
        younger = dict(looks, age=5)
        self.assertFalse(titles_file.could_be(3, e, younger, True))      # the other checks still hold

    def test_a_title_held_for_them_stays_held(self):
        e = titles_file.Entry(0, 7, "Chief", known=True, age=10, head=3, body=4, sex=1)
        looks = dict(age=20, head=3, body=4, sex=0, skills=(0,) * titles_file.SKILLS)
        self.assertFalse(lt._held_for(3, [e], 7, looks))
        self.assertTrue(lt._held_for(3, [e], 7, looks, sex_changed=True))


class LastNames(Temp):
    def test_a_parent_s_own_rule_follows_a_change_of_sex(self):
        rules = {("Ann", 3, 4, "Female"): "mother"}
        self.assertIsNone(ln._parent_rule(rules, ("Ann", 3, 4), "Male", set()))
        self.assertEqual(ln._parent_rule(rules, ("Ann", 3, 4), "Male", set(), {"Ann"}), "mother")

    def test_a_line_under_the_old_sex_is_the_villager_s_now(self):
        folder = self.folder()
        path = ln.record_path(folder, 3, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(ln.RECORD_HEADER.format(game=3) + "\n" + ln.own_line(("Ann", 3, 4, "Male"), "random") + "\n",
                        encoding="utf-8")
        people = [ln.Living(0, "Ann", "Female", 3, 4, 1, "")]
        self.assertEqual(ln.read_own(folder, 3, 1), {("Ann", 3, 4, "Male"): "random"})   # the file's format kept
        self.assertEqual(ln.own_rules_now(folder, 3, 1, people), {("Ann", 3, 4, "Male"): "random"})
        sex_log(folder, 1, "M\tF\tAnn\r\n")
        self.assertEqual(ln.own_rules_now(folder, 3, 1, people), {("Ann", 3, 4, "Female"): "random"})


class Genealogy(Temp):
    def reg(self, changed: set[str]) -> tuple[gen._Registry, gen.Person]:
        reg = gen._Registry()
        reg.sex_changed = set(changed)
        ann = gen.Person(1, "Ann", 3, 4, "Female", 900, alive=True)
        twin = gen.Person(2, "Ann", 3, 4, "Female", 150, alive=True)
        child = gen.Person(3, "Kid", 5, 5, "Male", 100, alive=True)
        for p in (ann, twin, child):
            reg.people[p.id] = p
        reg.by_key[ann.key] = 1
        reg.living_dups[ann.key] = [1, 2]
        child.father = 1
        return reg, child

    def test_a_father_whose_sex_changed_stays_the_father(self):
        reg, child = self.reg(set())
        notes: list[str] = []
        gen._parents_by_age(reg, {}, notes)
        self.assertIsNone(child.father)                 # no record of a change: no father, as before
        reg, child = self.reg({"Ann"})
        gen._parents_by_age(reg, {}, [])
        self.assertEqual(child.father, 1)               # the one old enough

    def test_the_vv1_sidecar_roster_follows_a_change_of_sex(self):
        who = ("Ann", 1, 7, 3, 4)
        living = (1, "Ann", 2, 7, 3, 4)
        self.assertFalse(gen._vv1_fits(who, living))
        self.assertTrue(gen._vv1_fits(who, living, {"Ann"}))

    def test_the_records_old_sex_and_new_name_one_villager(self):
        reg = gen._Registry()
        p = gen.Person(1, "Ann", 3, 4, "Male", 100, gone="died")
        q = gen.Person(2, "Ann", 3, 4, "Female", 200, alive=True)
        reg.people = {1: p, 2: q}
        self.assertFalse(gen._could_be_same(reg, p, q, {}, {}))
        reg.sex_changed = {"Ann"}
        self.assertTrue(gen._could_be_same(reg, p, q, {}, {}))

    def test_the_log_s_names_reach_the_registry(self):
        from test_reconcile import Village, fixture
        v = Village(self.folder(), 2, fixture("vv2-huttest-1"))
        v.births("Appearance changed\n  Name: Ann\n  Old head: 3\n  Old body: 4\n  New head: 3\n  New body: 4\n"
                 "  Old sex: Male\n  New sex: Female\n\n")
        reg = gen._Registry()
        gen._appearance_changes(reg, v.folder, 2, 1)
        self.assertEqual(reg.sex_changed, {"Ann"})
        self.assertEqual(reg.relooked, {})              # the look did not change


class Totems(unittest.TestCase):
    def test_the_statue_keeps_the_sex_it_was_made_with(self):
        e = totems.Elder("Ann", totems.FEMALE, 3, 4, True, lineage=2, father="Pa", mother="Ma")
        t = totems.Totem(0, 5, "Ann", totems.MALE, 3, 4, 2, "Pa", "Ma", 0, 1, 0, 0)
        self.assertFalse(totems._exact(e, t))
        self.assertTrue(totems._exact(e, t, {"Ann"}))
        dead = totems.Elder("Ann", totems.FEMALE, 3, 4, False)
        self.assertFalse(totems._exact(dead, t))
        self.assertTrue(totems._exact(dead, t, {"Ann"}))
        self.assertIsNone(totems._maybe(dead, t))
        self.assertIsNotNone(totems._maybe(dead, t, {"Ann"}))
        renamed = totems.Totem(0, 5, "Annie", totems.MALE, 3, 4, 2, "Pa", "Ma", 0, 1, 0, 0)
        self.assertFalse(totems._renamed(dead, renamed, {("Annie", "Ann", 3, 4)}))
        self.assertTrue(totems._renamed(dead, renamed, {("Annie", "Ann", 3, 4)}, {"Ann"}))


class MisfiledRecords(unittest.TestCase):
    def test_a_roster_of_the_new_sex_is_the_same_villager(self):
        p = rc.Seen("Ann", 3, 4, "Male", 10, frozenset(), frozenset())
        r = rc.Seen("Ann", 3, 4, "Female", 20, frozenset(), frozenset())
        self.assertFalse(misfiled._same(p, r, True))
        self.assertTrue(misfiled._same(p, r, True, {"Ann"}))


class OriginalLook(Temp):
    def test_a_change_of_sex_is_no_change_of_look(self):
        import vv_original_look as ol
        from test_reconcile import Village, fixture
        v = Village(self.folder(), 2, fixture("vv2-huttest-1"))
        v.births("Appearance changed\n  Name: Ann\n  Old head: 3\n  Old body: 4\n  New head: 3\n  New body: 4\n"
                 "  Old sex: Male\n  New sex: Female\n\n")
        ev = ol.evidence(v.folder, 2, 1)
        self.assertEqual(ev.changes, [])
        self.assertEqual(ev.sex_changed, {"Ann"})


class RepairLogsKeepsTheRecord(Temp):
    def test_nothing_offers_to_remove_or_change_the_sex_lines(self):
        """Repair Logs' every kind (vv_log_additions.plan) leaves the Appearance changed record with its Old sex
        / New sex lines as it is: nothing removes it, puts a line of it right, or asks about the sex."""
        import struct
        import vv_log_additions as additions
        from test_reconcile import Village, fixture
        v = Village(self.folder(), 3, fixture("vv3-huttest-1"))
        data = bytearray(v.save_path(1).read_bytes())
        at = v.entries(bytes(data))[0]
        was = struct.unpack_from("<i", data, at + v.f.sex)[0]
        struct.pack_into("<i", data, at + v.f.sex, 1 if was == 0 else 0)
        v.write_save(1, bytes(data))
        s = v.people(bytes(data))[0]
        old, new = ("Male", "Female") if was == 0 else ("Female", "Male")
        log = v.births(f"Appearance changed\n  Name: {s.name}\n  Old head: {s.head}\n  Old body: {s.body}\n"
                       f"  New head: {s.head}\n  New body: {s.body}\n  Old sex: {old}\n  New sex: {new}\n\n")
        sex_log(v.folder, 1, f"{old[0]}\t{new[0]}\t{s.name}\r\n")
        lines = additions.read_lines(log)
        record = next(k for k, line in enumerate(lines) if line.strip() == "Appearance changed")
        span = range(record, record + 9)
        for kind in additions.plan(v.folder, 3, 1):
            for r in kind.removes:
                self.assertFalse(r.path == log and r.start in span, kind.id)
            for rep in kind.replaces:
                self.assertFalse(rep[0] == log and rep[1] in span, kind.id)
            for q in kind.questions.values():
                self.assertNotIn(f"sex|{s.name}|", q.key, kind.id)
        self.assertEqual([f for f in rc.reconcile(v.folder, 3, 1).questions if f.topic == "sex"], [])


if __name__ == "__main__":
    unittest.main()
