"""Check Saves & Logs on A New Home's parents: namesakes and villagers renamed since birth.

The owner's Kalahuna Tribe 1 (2026-10-11): two living Soda Bahatis, two Tuna Tokidokis, two Dulu
Sirikits, two Elki Awanatas and two Etini Akikais -- each pair sharing name, sex and family number --
were reported as "no entry follows this villager (a new occupant: unknown)", although the parentage
file held an entry for every one of them, told apart by the looks its roster records.  The companion
itself follows them by those looks (native/vv1_parentage/vv1_parentage.c vv1_follow_roster); the
checker did not.

And Tiki Alosaka (head 12, body 18), born Iruwa Okelani to Hoto Okelani and Taka Powaka and renamed in
the game to her half-sister's name, was UNCHECKED ("looks changed since birth").  Her own Birth record
-- her looks, the very parents the file holds, a name nobody carries now -- is found and agrees.  A
villager renamed to a name no Birth record has is never reported as needing a second Birth record or
cleared parents (vv1_crosscheck.inc does the same in the game: test_vv1_crosscheck.py).
"""
from __future__ import annotations

import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("vvfp_consistency_check", ROOT / "scripts" / "vvfp_consistency_check.py")
checker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"

HOTO = ("Hoto Okelani", 1, 42, 18, 5)
LIKO = ("Liko Tasunke", 1, 39, 4, 4)
TAKA = ("Taka Powaka", 0, 50, 7, 11)
LEIA = ("Leia Alosaka", 0, 7, 15, 8)
IRUWA = ("Iruwa Bahati II", 0, 35, 9, 0)


def save(villagers) -> bytes:
    data = bytearray(0x184 + 256 * 0x9C)
    for i, (name, male, scalar, head, body) in enumerate(villagers):
        base = 0x184 + i * 0x9C - 0x33C
        struct.pack_into("<i", data, base + 0x350, 1 if male else 2)
        struct.pack_into("<i", data, base + 0x348, 500)
        struct.pack_into("<i", data, base + 0x360, head)
        struct.pack_into("<i", data, base + 0x364, body)
        struct.pack_into("<i", data, base + 0x36C, scalar)
        struct.pack_into("<i", data, base + 0x3D4, 1)
        data[base + 0x370:base + 0x370 + len(name)] = name.encode()
    return bytes(data)


def birth(child, father, mother) -> list[str]:
    return ["Birth", f"  Child: {child[0]}", f"    Head: {child[3]}", f"    Body: {child[4]}",
            f"  Mother: {mother[0]}", f"    Head: {mother[3]}", f"    Body: {mother[4]}",
            f"  Father: {father[0]}", f"    Head: {father[3]}", f"    Body: {father[4]}", ""]


def parents_file(rows) -> bytes:
    """rows: (occupant, father, mother) in record order; the roster records each occupant's looks."""
    out = bytearray(struct.pack("<III", 0x32305056, 0, 1))
    for i in range(256):
        rec = bytearray(36)
        if i < len(rows):
            name, male, scalar, head, body = rows[i][0]
            struct.pack_into("<BBBBi", rec, 0, 1 if male else 2, 0, head + 1, body + 1, scalar)
            rec[8:8 + len(name)] = name.encode()
        out += rec
    for i in range(256):
        e = bytearray(92)
        if i < len(rows) and rows[i][1]:
            f, m = rows[i][1], rows[i][2]
            e[0], e[1], e[2], e[3] = f[3] + 1, f[4] + 1, m[3] + 1, m[4] + 1
            e[8:8 + len(f[0])] = f[0].encode()
            e[36:36 + len(m[0])] = m[0].encode()
        out += e
    return bytes(out)


class Fixture(unittest.TestCase):
    def village(self, living, births, rows) -> Path:
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "Virtual Villagers - A New Home - Modded"
        (game / LOGS / "Births and Conceptions").mkdir(parents=True)
        (game / DATA).mkdir(parents=True)
        (game / "Virtual Villagers1.ldw").write_bytes(save(living))
        lines = ["Village: Kalahuna Tribe 1 (Save 1)"]
        for b in births:
            lines += birth(*b)
        (game / LOGS / "Births and Conceptions" / "Virtual Villagers 1 Births and Conceptions Log 1.txt").write_text(
            "\n".join(lines) + "\n", encoding="latin-1")
        (game / DATA / "Virtual Villagers 1 Parentage Records - Save 1.dat").write_bytes(parents_file(rows))
        return game

    def lines(self, game: Path) -> list[tuple[str, str]]:
        rep = checker.check(game, 1)
        return [(v, t) for f, v, t in rep.lines if "Parentage Records" in f]


class Namesakes(Fixture):
    def test_two_namesakes_are_told_apart_by_the_looks_the_file_recorded(self):
        # The owner's two Soda Bahatis: same name, sex and family 35, head 12 body 19 and head 11 body 6,
        # and the file holds them in another order than the save (a load packed the array).
        soda_a = ("Soda Bahati", 0, 35, 12, 19)
        soda_b = ("Soda Bahati", 0, 35, 11, 6)
        living = [HOTO, LIKO, IRUWA, soda_b, soda_a]
        game = self.village(living, [(soda_a, HOTO, IRUWA), (soda_b, LIKO, IRUWA)],
                            [(HOTO, None, None), (soda_a, HOTO, IRUWA), (LIKO, None, None),
                             (IRUWA, None, None), (soda_b, LIKO, IRUWA)])
        got = self.lines(game)
        self.assertNotIn("no entry follows", " ".join(t for _, t in got))
        self.assertIn(("OK", "Soda Bahati: father Hoto Okelani, mother Iruwa Bahati II, as the Births log says"), got)
        self.assertIn(("OK", "Soda Bahati: father Liko Tasunke, mother Iruwa Bahati II, as the Births log says"), got)

    def test_namesakes_with_the_same_looks_are_never_guessed(self):
        twin = ("Ama Akikai", 0, 39, 7, 7)
        living = [HOTO, LIKO, IRUWA, twin, twin]
        game = self.village(living, [(twin, HOTO, IRUWA)],
                            [(twin, HOTO, IRUWA), (twin, LIKO, IRUWA), (HOTO, None, None), (LIKO, None, None),
                             (IRUWA, None, None)])   # never at their own records: nothing to fall back on
        got = self.lines(game)
        self.assertEqual(sum(t.startswith("Ama Akikai: no entry follows") for _, t in got), 2, got)

    def test_a_file_from_an_earlier_build_with_no_looks_still_leaves_them_unknown(self):
        soda_a = ("Soda Bahati", 0, 35, 12, 19)
        soda_b = ("Soda Bahati", 0, 35, 11, 6)
        living = [HOTO, LIKO, IRUWA, soda_b, soda_a]
        game = self.village(living, [(soda_a, HOTO, IRUWA), (soda_b, LIKO, IRUWA)],
                            [(soda_a, HOTO, IRUWA), (soda_b, LIKO, IRUWA), (HOTO, None, None),
                             (LIKO, None, None), (IRUWA, None, None)])
        path = game / DATA / "Virtual Villagers 1 Parentage Records - Save 1.dat"
        data = bytearray(path.read_bytes())
        for i in range(256):
            data[12 + i * 36 + 2] = data[12 + i * 36 + 3] = 0      # no looks recorded
        path.write_bytes(bytes(data))
        got = self.lines(game)
        self.assertEqual(sum(t.startswith("Soda Bahati: no entry follows") for _, t in got), 2, got)


class BirthUnderAnotherName(Fixture):
    """The owner (2026-10-11): "Iruwa Okelani" (Birth 252, head 12, body 18) became a second living
    "Tiki Alosaka" with no rename record, and she never renamed anyone.  A checker that took that as
    "renamed since birth: OK" hid real corruption.  It is a contradiction: ASKED, never accepted, never
    repaired without the player's answer."""

    def test_the_owners_tiki_and_iruwa_is_a_question_for_the_player(self):
        tiki = ("Tiki Alosaka", 0, 7, 3, 8)
        born = ("Iruwa Okelani", 0, 50, 12, 18)
        renamed = ("Tiki Alosaka", 0, 50, 12, 18)
        living = [HOTO, TAKA, LEIA, tiki, renamed]
        game = self.village(living, [(tiki, HOTO, LEIA), (born, HOTO, TAKA)],
                            [(HOTO, None, None), (TAKA, None, None), (LEIA, None, None), (tiki, HOTO, LEIA),
                             (renamed, HOTO, TAKA)])
        got = self.lines(game)
        self.assertIn(("OK", "Tiki Alosaka: father Hoto Okelani, mother Leia Alosaka, as the Births log says"), got)
        asked = [t for v, t in got if v == "ASK"]
        self.assertEqual(len(asked), 1, got)
        self.assertTrue(asked[0].startswith("Birth says Iruwa Okelani; the save says Tiki Alosaka (head 12, body 18); "
                                            "no log records a rename. Which is right?"), asked)
        self.assertIn("Nothing is changed until you answer", asked[0])
        # Never accepted: no OK line takes the Birth record of Iruwa as Tiki's.
        self.assertFalse(any(v == "OK" and "Iruwa" in t for v, t in got), got)

    def test_the_birth_number_is_named(self):
        born = ("Iruwa Okelani", 0, 50, 12, 18)
        renamed = ("Zuri Okelani", 0, 50, 12, 18)
        living = [HOTO, TAKA, renamed]
        game = self.village(living, [(born, HOTO, TAKA)],
                            [(HOTO, None, None), (TAKA, None, None), (renamed, HOTO, TAKA)])
        path = game / LOGS / "Births and Conceptions" / "Virtual Villagers 1 Births and Conceptions Log 1.txt"
        path.write_text(path.read_text(encoding="latin-1").replace("\nBirth\n", "\nBirth 252\n"), encoding="latin-1")
        got = self.lines(game)
        self.assertFalse(any(v in ("WRONG", "OK") and t.startswith("Zuri Okelani:") for v, t in got), got)
        self.assertTrue(any(v == "ASK" and t.startswith("Birth 252 says Iruwa Okelani; the save says Zuri Okelani")
                            for v, t in got), got)

    def test_a_birth_whose_child_still_lives_under_that_name_is_not_asked_about(self):
        born = ("Iruwa Okelani", 0, 50, 12, 18)
        other = ("Zuri Okelani", 0, 50, 12, 18)
        living = [HOTO, TAKA, born, other]
        game = self.village(living, [(born, HOTO, TAKA)],
                            [(HOTO, None, None), (TAKA, None, None), (born, HOTO, TAKA), (other, HOTO, TAKA)])
        got = self.lines(game)
        self.assertFalse(any(v == "ASK" for v, _ in got), got)
        self.assertTrue(any(v == "WRONG" and t.startswith("Zuri Okelani") for v, t in got), got)

    def test_parents_that_are_not_her_births_are_no_such_question(self):
        born = ("Iruwa Okelani", 0, 50, 12, 18)
        renamed = ("Zuri Okelani", 0, 50, 12, 18)
        living = [HOTO, LIKO, TAKA, renamed]
        game = self.village(living, [(born, HOTO, TAKA)],
                            [(HOTO, None, None), (LIKO, None, None), (TAKA, None, None), (renamed, LIKO, TAKA)])
        got = self.lines(game)
        self.assertFalse(any("Iruwa" in t for _, t in got), got)


class StaleTitleRecords(unittest.TestCase):
    """The owner's two "Helpful Spirit" titles (Hoto Okelani, Liko Tasunke) were kept at records 92 and
    150 from before a load packed the villagers to 78 and 136: each is its villager's (its identity is
    theirs alone), and is said so -- not "does not match the villager there"."""

    def titles(self, entries) -> bytes:
        out = bytearray(b"VCT1" + struct.pack("<III", 2, 1, len(entries)))
        for index, fp, title in entries:
            e = bytearray(40)
            struct.pack_into("<II", e, 0, index, fp)
            e[8:8 + len(title)] = title.encode()
            out += e
        return bytes(out)

    def run_check(self, living, entries):
        roster = checker.vv1_roster(save(living))
        game = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (game / DATA / "Custom Titles").mkdir(parents=True)
        (game / DATA / "Custom Titles" / "Custom Titles - Save 1.dat").write_bytes(
            self.titles([(i, checker.vv1_title_identity(roster[w]) if w is not None else 7, t)
                         for i, w, t in entries]))
        rep = checker.Report()
        checker.check_titles(game, 1, 1, roster, None, rep)
        return [(v, t) for _, v, t in rep.lines]

    def test_a_title_at_a_stale_record_is_its_villagers(self):
        # Slot reuse and packing are normal (the owner's village at the 256 cap): a NOTE, and the title
        # follows its villager's identity -- never the record number.
        got = self.run_check([TAKA, HOTO, LIKO], [(5, 1, "Helpful Spirit"), (0, 2, "Helpful Spirit")])
        for who, now, was in (("Hoto Okelani", 1, 5), ("Liko Tasunke", 2, 0)):
            self.assertIn(("NOTE", f"\"Helpful Spirit\" is {who}'s (record {now} now; the file still says record "
                                   f"{was}, from before a load packed the villagers or the slot was reused -- the "
                                   "title follows its villager's identity, and the game's load moves it to them)"),
                          got)

    def test_a_title_nobody_carries_is_still_a_note(self):
        got = self.run_check([TAKA, HOTO], [(5, None, "Moon Mother")])
        self.assertTrue(any(v == "NOTE" and "does not match the villager there" in t for v, t in got), got)

    def test_a_pending_title_is_named_with_who_could_be_them(self):
        """v1.35.70: a version 3 file's pending title (its villager could not be told apart after a load)
        is reported as waiting, with the villagers who carry its name and likes -- never as an error."""
        sys.path.insert(0, str(ROOT / "src"))
        import vv_titles_file as tf
        roster = checker.vv1_roster(save([TAKA, HOTO, LIKO]))
        game = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (game / DATA / "Custom Titles").mkdir(parents=True)
        (game / DATA / "Custom Titles" / "Custom Titles - Save 1.dat").write_bytes(tf.serialise(1, [
            tf.Entry(tf.PENDING, checker.vv1_title_identity(roster[1]), "Helpful Spirit", False)]))
        rep = checker.Report()
        checker.check_titles(game, 1, 1, roster, None, rep)
        got = [(v, t) for _, v, t in rep.lines]
        self.assertIn(("NOTE", "\"Helpful Spirit\" is PENDING: kept, shown on nobody until exactly one villager has "
                               "its whole identity (could be: Hoto Okelani, record 1) -- the reconciliation asks you "
                               "about it"), got)
        self.assertFalse(any(v in ("WRONG", "UNCHECKED") for v, _ in got), got)


class LastNameNoteSaysWhichRule(unittest.TestCase):
    """The owner's Tiki Alosaka was listed "should be Powaka" under the village's "From the father",
    while her father Hoto Okelani's own rule is 50:50 -- either parent's last name is right."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "src"))
        import vv_last_names
        self.ln = vv_last_names

    def test_a_parents_own_fifty_fifty_names_both(self):
        v = checker.Villager(rank=0, name="Tiki Alosaka", male=False, age=1, head=12, body=18, skills=[])
        self.assertEqual(self.ln.wrong_last_name_text(v, "Powaka", "random", "father", ("Okelani", "Powaka")),
                         "Tiki Alosaka (should be Okelani or Powaka: a parent's own rule, 50:50, applies)")

    def test_the_village_rule_reads_as_before(self):
        v = checker.Villager(rank=0, name="Kin Powaka", male=True, age=1, head=1, body=1, skills=[])
        self.assertEqual(self.ln.wrong_last_name_text(v, "Okelani", "father", "father"), "Kin Powaka (should be Okelani)")


class RestoreNamesakes(unittest.TestCase):
    """Restore A New Home Parents (src/vv1_parents_restore.py) tells two namesakes apart by the looks both
    rosters recorded, as the companion does; with no looks recorded they stay ambiguous, as before."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "src"))
        import vv1_parents_restore
        self.restore = vv1_parents_restore
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory())) / "Virtual Villagers - Test"
        records = self.folder / DATA / "Parentage Records"
        records.mkdir(parents=True)
        self.path = records / vv1_parents_restore.file_name(1)
        logs = self.folder / LOGS / "Births and Conceptions"
        logs.mkdir(parents=True)
        (logs / "Virtual Villagers 1 Births and Conceptions Log 1.txt").write_text("Village: T (Save 1)\n",
                                                                                  encoding="latin-1")

    def write(self, path, rows, looks=True):
        r = self.restore
        data = bytearray(r.SIZE)
        data[:4] = r.MAGIC
        struct.pack_into("<I", data, 8, 1)
        for index, (name, gender, scalar, head, body), father, mother in rows:
            o = r.HEADER + index * r.OCCUPANT
            data[o:o + 4] = bytes([gender, 0, head + 1 if looks else 0, body + 1 if looks else 0])
            struct.pack_into("<i", data, o + 4, scalar)
            data[o + 8:o + 8 + len(name)] = name.encode()
            e = r.HEADER + r.COUNT * r.OCCUPANT + index * r.ENTRY
            if father:
                data[e:e + 4] = bytes([1, 2, 3, 4])
                data[e + 8:e + 8 + len(father)] = father.encode()
                data[e + 36:e + 36 + len(mother)] = mother.encode()
        path.write_bytes(bytes(data))

    def rows(self, with_parents):
        soda_a = ("Soda Bahati", 2, 35, 12, 19)
        soda_b = ("Soda Bahati", 2, 35, 11, 6)
        hoto = ("Hoto Okelani", 1, 42, 18, 5)
        liko = ("Liko Tasunke", 1, 39, 4, 4)
        iruwa = ("Iruwa Bahati II", 2, 35, 9, 0)
        p = (lambda f, m: (f, m)) if with_parents else (lambda f, m: (None, None))
        return [(0, hoto, None, None), (1, liko, None, None), (2, iruwa, None, None),
                (3, soda_b, *p("Liko Tasunke", "Iruwa Bahati II")), (4, soda_a, *p("Hoto Okelani", "Iruwa Bahati II"))]

    def test_namesakes_get_their_own_parents_back(self):
        self.write(self.path, [(i if i < 3 else 7 - i, *rest) for i, *rest in self.rows(False)])
        self.write(self.path.with_name(self.path.name + ".before-v1.35.58-repair"), self.rows(True))
        work = self.restore.plan(self.folder, 1)
        got = {(r.name, r.father) for r in work.restored}
        self.assertEqual(got, {("Soda Bahati", "Hoto Okelani"), ("Soda Bahati", "Liko Tasunke")}, work.lines())
        t = work.table
        by_looks = {t.looks(i): t.names(i) for i in range(5) if t.identity(i) and t.identity(i)[0] == "Soda Bahati"}
        self.assertEqual(by_looks[(12, 19)], ("Hoto Okelani", "Iruwa Bahati II"))
        self.assertEqual(by_looks[(11, 6)], ("Liko Tasunke", "Iruwa Bahati II"))

    def test_namesakes_with_no_looks_recorded_stay_ambiguous(self):
        self.write(self.path, self.rows(False))
        self.write(self.path.with_name(self.path.name + ".before-v1.35.58-repair"), self.rows(True), looks=False)
        work = self.restore.plan(self.folder, 1)
        self.assertEqual(work.restored, [])
        self.assertIn("Soda Bahati", work.ambiguous)


class BirthUnderAnotherNameInTheLaterGames(unittest.TestCase):
    """The Lost Children to New Believers keep parents on the villager: a villager with the looks and the
    very parents of a Birth record under another name is never given a second Birth record "recorded
    afterwards" -- and is never taken as settled either: a question for the player
    (native/parentage_export/arrival_backfill.inc, the same rule)."""

    def villager(self, name, head, body, father, mother):
        return checker.Villager(rank=0, name=name, male=False, age=500, head=head, body=body, skills=[0] * 5,
                                father=father, mother=mother)

    def birth(self, child, head, body, father, mother):
        return checker.LogRecord("birth", "Village: X (Save 1)", checker.Person(child, head, body),
                                 checker.Person(mother, 1, 1), checker.Person(father, 2, 2), number="Birth 252")

    def test_no_second_birth_record_and_a_question(self):
        zuri = self.villager("Zuri", 12, 18, "Hoto", "Taka")
        births = [self.birth("Iruwa", 12, 18, "Hoto", "Taka")]
        asked: list = []
        self.assertEqual(checker.missing_births([zuri], births, asked), [])
        self.assertEqual(asked, [(zuri, births)])

    def test_the_report_asks_never_says_ok(self):
        zuri = self.villager("Zuri", 12, 18, "Hoto", "Taka")
        births = checker.BirthsLog([self.birth("Iruwa", 12, 18, "Hoto", "Taka")])
        births.village = "Village: X (Save 1)"
        rep = checker.Report()
        game = Path(self.enterContext(tempfile.TemporaryDirectory()))
        checker.vv25_parents_vs_births([zuri], births, rep, 3, game, 1)
        got = [(v, t) for _, v, t in rep.lines]
        self.assertTrue(any(v == "ASK" and t.startswith("Birth 252 says Iruwa; the save says Zuri (head 12, body 18); "
                                                       "no log records a rename. Which is right?") for v, t in got), got)
        self.assertFalse(any(v == "OK" and "Birth or Arrived record" in t for v, t in got), got)

    def test_other_parents_are_no_rename(self):
        zuri = self.villager("Zuri", 12, 18, "Liko", "Taka")
        births = [self.birth("Iruwa", 12, 18, "Hoto", "Taka")]
        self.assertEqual(checker.missing_births([zuri], births), [zuri])

    def test_a_birth_whose_child_still_lives_under_that_name_is_not_hers(self):
        iruwa = self.villager("Iruwa", 12, 18, "Hoto", "Taka")
        zuri = self.villager("Zuri", 12, 18, "Hoto", "Taka")
        births = [self.birth("Iruwa", 12, 18, "Hoto", "Taka")]
        self.assertEqual(checker.missing_births([iruwa, zuri], births), [zuri])

    def test_twins_are_never_told_apart(self):
        a = self.villager("Zuri", 12, 18, "Hoto", "Taka")
        b = self.villager("Mara", 12, 18, "Hoto", "Taka")
        births = [self.birth("Iruwa", 12, 18, "Hoto", "Taka")]
        self.assertEqual(checker.missing_births([a, b], births), [a, b])


if __name__ == "__main__":
    unittest.main()
