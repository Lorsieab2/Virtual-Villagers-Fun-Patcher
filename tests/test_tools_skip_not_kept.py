"""Every patcher tool that reads Conception and Birth records skips the ones the saved village never held
(v1.35.97, src/vv_not_kept.py).

Before a village's first save the game can play the same time twice (the start-up catch-up, then the
village loaded again from its save and the same time played over).  The Parentage Export companion
writes the first run's records all the same and closes each with "Note: Not in the village as it was
saved" (native/parentage_export/parentage_export.c NOT_KEPT_NOTE / BIRTH_NOT_KEPT_NOTE).  Logs must match
the save: such a Conception is nobody's pregnancy and such a Birth nobody's child, so no family tree,
parents repair, backfill, reconcile, statistics count or history revision may take them as real -- and
the record itself is never removed or rewritten for it.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv1_parents_restore as restore  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_contradictions as contradictions  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_original_look as original_look  # noqa: E402
import vv_reconcile as rc  # noqa: E402
from vv_not_kept import NOT_KEPT_LINE, is_not_kept, is_not_kept_line  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
HEADER = "Village: Tribe (Save 1)"

# The two notes exactly as the companion writes them (parentage_export.c).
CONCEPTION_NOTE = ("  Note: Not in the village as it was saved: the game played this time, then\n"
                   "    loaded the village again from its save and played the same time over, so\n"
                   "    this pregnancy was not kept.\n")
BIRTH_NOTE = ("  Note: Not in the village as it was saved: the game played this time, then\n"
              "    loaded the village again from its save and played the same time over, so\n"
              "    this birth was not kept.\n")


def conception(n: int, mother: tuple, father: tuple, babies: int = 1, not_kept: bool = False) -> str:
    (mn, mh, mb), (fn, fh, fb) = mother, father
    return (f"Conception {n}\n  Mother: {mn}\n    Age at conception: 600\n    Sex: Female\n    Head: {mh}\n"
            f"    Body: {mb}\n  Father: {fn}\n    Age at conception: 600\n    Sex: Male\n    Head: {fh}\n"
            f"    Body: {fb}\n  Babies nursing: {babies}\n" + (CONCEPTION_NOTE if not_kept else "") + "\n")


def birth(heading: str, child: tuple, mother: tuple, father: tuple, not_kept: bool = False,
          born_as: str | None = None) -> str:
    (cn, ch, cb), (mn, mh, mb), (fn, fh, fb) = child, mother, father
    return (f"{heading}\n  Child: {cn}\n    Sex: Female\n    Head: {ch}\n    Body: {cb}\n    Likes: (none)\n"
            f"    Dislikes: (none)\n  Mother: {mn}\n    Head: {mh}\n    Body: {mb}\n  Father: {fn}\n    Head: {fh}\n"
            f"    Body: {fb}\n" + (f"  Born as: {born_as}\n" if born_as else "")
            + (BIRTH_NOTE if not_kept else "") + "\n")


def write_births(folder: Path, game: int, text: str) -> Path:
    path = folder / LOGS / "Births and Conceptions" / f"Virtual Villagers {game} Births and Conceptions Log 1.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((HEADER + "\n" + text).replace("\n", "\r\n").encode("latin-1"))
    return path


MA, PA, WRONG = ("Ma", 1, 1), ("Pa", 2, 2), ("Wrong", 11, 12)


class TheNote(unittest.TestCase):
    """One helper, matched on the exact words the companion writes."""

    def test_both_notes_and_only_them(self):
        self.assertEqual(NOT_KEPT_LINE, CONCEPTION_NOTE.split("\n")[0])
        self.assertEqual(NOT_KEPT_LINE, BIRTH_NOTE.split("\n")[0])
        source = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="latin-1")
        self.assertEqual(source.count(f'"{NOT_KEPT_LINE}\\n"'), 2, "the DLL's own words, in both notes")
        for text in (conception(1, MA, PA, not_kept=True), birth("Birth 1", ("Kid", 3, 4), MA, PA, not_kept=True),
                     conception(1, MA, PA, not_kept=True).replace("\n", "\r\n")):
            self.assertTrue(is_not_kept(text))
            self.assertTrue(is_not_kept(text.splitlines()))
        self.assertTrue(is_not_kept_line(NOT_KEPT_LINE.strip()), "a reader that strips its lines")
        for line in ("  Note: Recorded before this village was saved, among villagers who were",
                     "  Note: Not in the village as it was saved",
                     "  Note: Not in the village",
                     "  Child: Note: Not in the village as it was saved: the game played this time, then",
                     "  Note: Recorded afterwards (her Conception had no Birth, and her Death record follows it)"):
            self.assertFalse(is_not_kept_line(line), line)
        self.assertFalse(is_not_kept(conception(1, MA, PA)))


class ConsistencyChecker(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.checker = tools.load_checker()

    def test_the_births_log_leaves_them_out_and_counts_nothing_of_them(self):
        write_births(self.folder, 2,
                     conception(1, MA, WRONG, babies=2, not_kept=True) + conception(2, MA, PA, babies=2)
                     + birth("Birth 1", ("Ghost", 13, 14), MA, WRONG, not_kept=True)
                     + birth("Birth 2", ("Kid", 3, 4), MA, PA) + birth("Birth 3", ("Kid2", 5, 6), MA, PA))
        records, _files = self.checker.births_log(self.folder, 2, 1)
        self.assertEqual([(r.kind, (r.child or r.mother).name, r.father.name) for r in records],
                         [("conception", "Ma", "Pa"), ("birth", "Kid", "Pa"), ("birth", "Kid2", "Pa")])
        every, _files = self.checker.births_log(self.folder, 2, 1, keep_not_kept=True)
        self.assertEqual(sum(r.not_kept for r in every), 2, "still read, marked, when asked for")
        # Village Statistics: Babies Made and Twins Birthed are bounded by the kept records only.
        stats = self.folder / LOGS / "Save 1" / "Village Statistics" / "Village Statistics v2 - Save 1.txt"
        stats.parent.mkdir(parents=True)
        stats.write_text("Babies Made: 2\nTwins Birthed: 1\n", encoding="latin-1")
        rep = self.checker.Report()
        self.checker.check_statistics(self.folder, 1, 2, [], records, 0, None, rep)
        lines = [(state, text) for _label, state, text in rep.lines]
        self.assertIn(("OK", "Babies Made 2 >= the 2 Birth records in the log (the log is a lower bound: births "
                             "before it began are not in it)"), lines)
        self.assertIn(("OK", "Twins Birthed 1 >= the 1 twin conceptions in the log"), lines)


class FamilyTree(unittest.TestCase):
    """The Family Tree Maker (vv_genealogy, and so Last Names, the Matchmaker and Village Info)."""

    def test_no_phantom_child_and_no_wrong_father(self):
        from test_last_names_rename import TABLE, entry
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        people = [entry("Pa", 0, 1, 2, 2), entry("Ma", 1, 50, 1, 1),
                  entry("Kid", 0, 50, 3, 4, father=("Pa", 2, 2), mother=("Ma", 1, 1))]
        (folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            b"ldwg" + bytes(TABLE - 4) + b"".join(people) + bytes(64))
        write_births(folder, 3,
                     conception(1, MA, WRONG, not_kept=True) + conception(2, MA, PA)
                     + birth("Birth 1", ("Ghost", 13, 14), MA, WRONG, not_kept=True)
                     + birth("Birth 2", ("Kid", 3, 4), MA, PA))
        village = gen.load_village(folder, 3, 1)
        names = {p.name for p in village.people.values()}
        self.assertNotIn("Ghost", names, "the first run's child never lived in the saved village")
        self.assertNotIn("Wrong", names, "nor did its father father anybody")
        kid = next(p for p in village.people.values() if p.name == "Kid")
        self.assertEqual(village.people[kid.father].name, "Pa")
        self.assertIsNone(kid.litter, "the phantom is no twin of the real child")


class ParentsRepairVV1(unittest.TestCase):
    """A New Home's parents restore (vv1_parents_restore): the Birth records' parents."""

    def test_a_not_kept_birth_gives_nobody_parents(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_births(folder, 1, birth("Birth 1", ("Kid", 3, 4), MA, WRONG, not_kept=True)
                     + birth("Birth 2", ("Kid", 3, 4), MA, PA) + birth("Birth 3", ("Ghost", 9, 9), MA, WRONG,
                                                                       not_kept=True))
        self.assertEqual(restore._births_log_parents(folder, 1), {("Kid", 3, 4): {("Pa", "Ma")}})


class RepairBackfills(unittest.TestCase):
    """Repair Saves & Logs' backfills (vv_log_additions)."""

    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_born_as_never_groups_a_phantom_with_the_real_child(self):
        # The replay's two deliveries of one pregnancy, written one after the other with the same mother.
        log = write_births(self.folder, 3, conception(1, MA, PA, babies=1)
                           + birth("Birth 1", ("Ghost", 13, 14), MA, PA, not_kept=True)
                           + birth("Birth 2", ("Kid", 3, 4), MA, PA))
        kind = additions.plan_born_as(self.folder, 3, 1)
        self.assertEqual(kind.questions, {}, "not asked as a pair of twins")
        self.assertEqual([i.line for i in kind.inserts], ["  Born as: Single birth"])
        lines = log.read_bytes().decode("latin-1").split("\r\n")
        self.assertGreater(kind.inserts[0].after, lines.index("Birth 2"), "on the real child's record only")

    def test_a_not_kept_pregnancy_is_never_offered_to_the_golden_child(self):
        arrived = ("Arrived 1\n  Name: Lulu\n  Special villager: Golden Child\n  Age: 100\n  Sex: Female\n"
                   "  Head: 5\n  Body: 5\n  Likes: (none)\n  Dislikes: (none)\n\n")
        write_births(self.folder, 1, conception(1, MA, WRONG, not_kept=True) + arrived)
        kind = additions.plan_golden(self.folder, 1, 1)
        self.assertEqual(kind.questions, {})
        self.assertEqual(kind.notes, ["Lulu, the Golden Child: no pregnancy in the logs could be theirs; nothing added."])

    def test_a_not_kept_pregnancy_leaves_no_baby_to_lose(self):
        write_births(self.folder, 2, conception(1, MA, PA) + birth("Birth 1", ("Kid", 3, 4), MA, PA)
                     + conception(2, MA, WRONG, not_kept=True))
        deaths = self.folder / LOGS / "Deaths and Disappearances" / "Virtual Villagers 2 Deaths Log 1.txt"
        deaths.parent.mkdir(parents=True)
        deaths.write_bytes((HEADER + "\nDeath 1\n  Name: Ma\n  Age at death: 610\n  Sex: Female\n  Head: 1\n"
                            "  Body: 1\n\n").replace("\n", "\r\n").encode("latin-1"))
        kind = additions.plan_lost(self.folder, 2, 1)
        self.assertEqual((kind.inserts, kind.questions), ([], {}))
        # The same log with that Conception kept: her babies were lost with her (the rule still works).
        write_births(self.folder, 2, conception(1, MA, PA) + birth("Birth 1", ("Kid", 3, 4), MA, PA)
                     + conception(2, MA, WRONG))
        kind = additions.plan_lost(self.folder, 2, 1)
        self.assertTrue(kind.inserts or kind.questions)

    def test_a_not_kept_birth_records_nobody(self):
        write_births(self.folder, 4, birth("Birth 1", ("Kid", 3, 4), MA, PA, not_kept=True)
                     + "Arrived 1\n  Name: Kid\n  Age when recorded: 100\n  Sex: Female\n  Head: 3\n  Body: 4\n"
                       "  How: unknown\n  Note: Recorded afterwards (arrived before this log existed)\n\n")
        kind = additions.plan_backfilled_arrivals(self.folder, 4, 1, {}, None)
        self.assertEqual((kind.questions, kind.removes), ({}, []), "the backfilled record is the only one")
        self.assertEqual(additions._side_counts(self.folder, 4, 1, None), {("Kid", 3, 4): [1, 0, 0, 0]},
                         "only the Arrived record came as a believer")
        self.assertEqual(additions._faction_events(self.folder, 4, 1)[2], {("Kid", 3, 4)})

    def test_the_record_itself_is_never_changed(self):
        log = write_births(self.folder, 3, conception(1, MA, PA, babies=2, not_kept=True)
                           + birth("Birth 1", ("Ghost", 13, 14), MA, PA, not_kept=True))
        before = log.read_bytes()
        kinds = additions.plan(self.folder, 3, 1)
        additions.apply(self.folder, kinds, {k.id for k in kinds}, {})
        self.assertEqual(log.read_bytes(), before)


class Contradictions(unittest.TestCase):
    def test_a_not_kept_birth_is_no_second_record_of_a_villager(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_births(folder, 2, birth("Birth 1", ("Kid", 3, 4), MA, PA, not_kept=True)
                     + "Arrived 1\n  Name: Kid\n  Age at arrival: 100\n  Sex: Female\n  Head: 3\n  Body: 4\n"
                       "  How: Barrel of Babies\n  Note: Recorded afterwards (arrived before this log existed)\n\n")
        self.assertEqual(contradictions._born_and_arrived(folder, 2, 1), [])
        # ...where a kept Birth would make it one.
        write_births(folder, 2, birth("Birth 1", ("Kid", 3, 4), MA, PA)
                     + "Arrived 1\n  Name: Kid\n  Age at arrival: 100\n  Sex: Female\n  Head: 3\n  Body: 4\n"
                       "  How: Barrel of Babies\n  Note: Recorded afterwards (arrived before this log existed)\n\n")
        self.assertEqual([f.kind for f in contradictions._born_and_arrived(folder, 2, 1)], ["born_and_arrived"])


class ReconcileAndLooks(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        write_births(self.folder, 5, birth("Birth 1", ("Ghost", 13, 14), MA, WRONG, not_kept=True)
                     + birth("Birth 2", ("Kid", 3, 4), MA, PA))

    def test_the_reconciliation_reads_only_kept_births(self):
        logs = rc.read_logs(self.folder, 5, 1, None)
        self.assertEqual([(r.who.name, r.who.father) for r in logs.births], [("Kid", "Pa")])

    def test_original_looks_never_take_a_phantom_as_a_villager(self):
        evidence = original_look.evidence(self.folder, 5, 1)
        self.assertEqual([own[0] for own in evidence.own], ["Kid"])
        self.assertNotIn("Ghost", evidence.names)


class HistoryRevision(unittest.TestCase):
    """Remove a restarted tribe's villagers (vv_history_revision): a not-kept record ties nobody to this
    tribe and names no villager."""

    def test_a_not_kept_conception_joins_nobody_to_this_tribe(self):
        from test_history_revision import Scene
        s = Scene(Path(self.enterContext(tempfile.TemporaryDirectory())), 3)
        # tests/test_history_revision.py test_a_parent_of_this_tribe_is_never_proven_gone, not kept: the link
        # it made is gone, so Gonea Testa is proven gone after all -- and the phantom child is nobody.
        s.v.births("Conception 1\n  Mother: Lupa Tangaroa\n    Age at conception: 2\n    Head: 24\n    Body: 28\n"
                   "  Father: Gonea Testa\n    Head: 99\n    Body: 98\n" + CONCEPTION_NOTE + "\n"
                   "Birth 1\n  Child: Phantom Kid\n    Sex: Male\n    Head: 77\n    Body: 76\n"
                   "  Mother: Lupa Tangaroa\n    Head: 24\n    Body: 28\n  Father: Gonea Testa\n    Head: 99\n"
                   "    Body: 98\n" + BIRTH_NOTE + "\n")
        plan = s.plan()
        self.assertEqual([v.person.name for v in plan.gone], ["Gonea Testa"])
        listed = {v.person.name for v in plan.gone + plan.kept + plan.unsure}
        self.assertNotIn("Phantom Kid", listed)
        births = next((s.v.folder / LOGS).rglob("Virtual Villagers 3 Births and Conceptions Log 1.txt"))
        self.assertFalse(any(c.path == births for c in plan.cuts), "the record is left exactly as it is")


if __name__ == "__main__":
    unittest.main()
