"""Room for the parents of every villager who ever lived, in all five games (the owner, 2026-10-20:
"make room for their parents in all 5 games").

A New Home keeps its parents only in the Show Parents companion's file, "Virtual Villagers 1 Parentage
Records - Save <n>.dat": 256 records, one per villager record, and a departed villager's entry waited in a
record nobody held.  A village at the 256 cap has no such record -- every death is followed by a birth into
the freed one -- so the entry was dropped: the owner's Kalahuna Tribe 1 lost the parents of 45 villagers who
passed away, Etini, Fatai and Ginger Awanata among them, and Restore A New Home Parents could only list them
as "no room".  The file now has a departed list after its 256 records (native/vv1_parentage g_departed),
which grows with the village; a file with nobody on it is the earlier builds' file byte for byte.

The Lost Children to New Believers keep a villager's parents on the villager's own record, which the game
frees at the death and gives to the next villager.  The Death and Disappeared records now carry them, read
from the record before it is freed (native/parentage_export gone_parents_block), in the block the Village
History prints for the living, so the family tree and Villager Info keep them after the record is reused.
"""
from __future__ import annotations

import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv1_parents_restore as restore  # noqa: E402
import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_villager_info as info  # noqa: E402
from test_tree_renamed_villagers import build_save  # noqa: E402

SLOT = 1


def occupant(name: str, gender: int, scalar: int, head: int, body: int, departed: int = 0) -> bytes:
    return (bytes((gender, departed, head + 1, body + 1)) + struct.pack("<i", scalar)
            + name.encode("latin-1").ljust(28, b"\0"))


def entry(father: str = "", mother: str = "", fh: int = 2, fb: int = 3, mh: int = 4, mb: int = 5) -> bytes:
    looks = bytes((fh + 1 if father else 0, fb + 1 if father else 0, mh + 1 if mother else 0,
                   mb + 1 if mother else 0, 0, 0, 0, 0))
    return looks + father.encode("latin-1").ljust(28, b"\0") + mother.encode("latin-1").ljust(28, b"\0") + bytes(28)


def parents_file(records: list[tuple[bytes, bytes]], departed: list[tuple[bytes, bytes]] = ()) -> bytes:
    """A VP02 file: `records` (occupant, entry) for records 0.., the rest empty, then the departed list."""
    roster = b"".join(o for o, _e in records) + bytes(36 * (256 - len(records)))
    entries = b"".join(e for _o, e in records) + bytes(92 * (256 - len(records)))
    data = b"VP02" + struct.pack("<II", 0, SLOT) + roster + entries
    if departed:
        data += b"VPD1" + struct.pack("<I", len(departed)) + b"".join(o + e for o, e in departed)
    return data


def full_village() -> list[tuple[bytes, bytes]]:
    return [(occupant(f"Villager {k}", 1 + (k & 1), 1000 + k, k % 30, k % 25), entry()) for k in range(256)]


class TheDepartedList(unittest.TestCase):
    """A New Home's file, read by every reader of it."""

    def test_an_earlier_builds_file_has_no_list_and_reads_as_before(self):
        data = parents_file(full_village())
        self.assertEqual(len(data), restore.SIZE)
        self.assertEqual(restore.departed_list(data), [])
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        path = root / restore.file_name(SLOT)
        path.write_bytes(data)
        table = restore.read_table(path, SLOT)
        self.assertEqual(table.size(), 256)
        self.assertEqual(table.to_bytes(), data, "written back exactly as it was")

    def test_a_full_village_and_many_who_passed_away_keep_every_parent(self):
        dead = [(occupant(f"Gone {k}", 2, 3000 + k, 5, 6, departed=1), entry(f"Father {k}", f"Mother {k}"))
                for k in range(700)]
        data = parents_file(full_village(), dead)
        self.assertEqual(len(data), restore.SIZE + 8 + 700 * 128)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        path = root / restore.file_name(SLOT)
        path.write_bytes(data)
        table = restore.read_table(path, SLOT)
        self.assertEqual(table.size(), 256 + 700)
        self.assertEqual([table.names(256 + k) for k in range(700)],
                         [(f"Father {k}", f"Mother {k}") for k in range(700)])
        self.assertEqual(table.to_bytes(), data)

    def test_never_twice(self):
        table = restore.Table(bytearray(parents_file(full_village())))
        who = occupant("Etini Awanata", 2, 7, 4, 5)
        parents = entry("Tadao Awanata", "Lisha Akikai I")
        parents = parents[:4] + parents[8:8 + 56]
        first = table.add_departed(who, parents)
        self.assertEqual(table.add_departed(who, parents), first)
        self.assertEqual(len(table.departed), 1)
        self.assertEqual(table.occupant(first)[1], 1, "marked departed")
        with self.assertRaises(ValueError):
            table.put_parents(first, parents)              # an entry on the list is never changed

    def test_a_list_that_is_not_the_companions_is_not_read(self):
        data = parents_file(full_village(), [(occupant("Gone", 2, 1, 1, 1, 1), entry("F", "M"))])
        for bad in (data + b"x", data[:-1], data[:restore.SIZE] + b"VPDX" + data[restore.SIZE + 4:],
                    data[:restore.SIZE + 4] + struct.pack("<I", 2) + data[restore.SIZE + 8:]):
            with self.subTest(size=len(bad)):
                self.assertIsNone(restore.departed_list(bad))
                root = Path(tempfile.mkdtemp())
                self.addCleanup(shutil.rmtree, root, True)
                path = root / restore.file_name(SLOT)
                path.write_bytes(bad)
                self.assertIsNone(restore.read_table(path, SLOT), "never written over")
                self.assertEqual(restore.read_table(path, SLOT, strict=False).size(), 256,
                                 "a copy still gives its 256 records")

    def sidecar(self, data: bytes) -> list:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        import vv_save_layout as layout
        path = layout.route(root, f"{layout.DATA}\\{layout.PARENTS_VV1}\\{restore.file_name(SLOT)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return gen._vv1_sidecar(root, SLOT)

    def test_the_family_tree_reads_the_list(self):
        etini = (occupant("Etini Awanata", 2, 7, 4, 5, 1), entry("Tadao Awanata", "Lisha Akikai I", 2, 3, 4, 5))
        entries = self.sidecar(parents_file(full_village(), [etini, etini]))
        listed = [e for e in entries if e.who[0] == "Etini Awanata"]
        self.assertEqual(len(listed), 1, "the same villager with the same entry is one entry")
        self.assertTrue(listed[0].departed)
        self.assertEqual(listed[0].who, ("Etini Awanata", 2, 7, 4, 5))
        self.assertEqual(listed[0].father, ("Tadao Awanata", 2, 3))
        self.assertEqual(listed[0].mother, ("Lisha Akikai I", 4, 5))
        self.assertEqual(len(self.sidecar(parents_file(full_village()))), 256, "an earlier build's file")
        self.assertEqual(self.sidecar(parents_file(full_village(), [etini]) + b"junk"), [],
                         "a file the companion would set aside gives nothing")

    def test_a_renamed_parent_is_renamed_on_the_list_too(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        import vv_save_layout as layout
        path = layout.route(root, f"{layout.DATA}\\{layout.PARENTS_VV1}\\{restore.file_name(SLOT)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        etini = (occupant("Etini Awanata", 2, 7, 4, 5, 1), entry("Tadao", "Lisha Akikai I", 2, 3, 4, 5))
        path.write_bytes(parents_file(full_village(), [etini]))
        plan = ln.Plan({})
        ln._plan_vv1_parentage(plan, root, root / layout.DATA, SLOT, [], {}, {("Tadao", 2, 3): "Tadao Awanata"}, {})
        self.assertEqual(len(plan.changes), 1)
        updated = plan.changes[0].updated
        self.assertEqual(len(updated), restore.SIZE + 8 + 128)
        self.assertEqual(restore.departed_list(updated)[0][36 + 8:36 + 8 + 13], b"Tadao Awanata")


def block(heading: str, name: str, head: int, body: int, sex: str, lines: list[str] = (),
          date: str | None = None):
    values = {"Sex": sex, "Name": name, "Likes": "Fish", "Dislikes": "Rain"}
    return SimpleNamespace(identity=(name, head, body), heading=heading, date=date, lines=list(lines),
                           path=Path("x"), value=lambda key: values.get(key))


def gone_parents(father: tuple, mother: tuple) -> list[str]:
    """The block a Death or Disappeared record carries (native/parentage_export gone_parents_block)."""
    return ["  Parents:", f"    Father: {father[0]}", f"      Head: {father[1]}", f"      Body: {father[2]}",
            f"    Mother: {mother[0]}", f"      Head: {mother[1]}", f"      Body: {mother[2]}"]


class AfterTheRecordIsReused(unittest.TestCase):
    """All five games: a villager who passed away or disappeared keeps their parents in the family tree and
    Villager Info from the record the patcher wrote at the death, after the game has given their record to
    somebody else -- and a namesake parent is told apart by the looks the record carries."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # The living: two fathers named Tane (other looks), a mother, and the baby in the dead villager's record.
    LIVING = [("Tane", "Male", 11, 12, "running", 900), ("Tane", "Male", 14, 2, "running", 800),
              ("Rua", "Female", 13, 14, "running", 850), ("Baby", "Female", 5, 6, "running", 40)]

    def load(self, game, logged):
        data, offsets = build_save(game, self.LIVING)
        ln.save_path(self.folder, game, 1).write_bytes(data)
        with mock.patch("vv_last_names._entries", return_value=offsets), \
                mock.patch("vv_cut_names.find_cut", return_value=([], [])), \
                mock.patch("vv_log_additions.person_blocks", return_value=logged):
            return gen.load_village(self.folder, game, 1)

    def test_a_dead_villagers_parents_survive_the_record_being_reused(self):
        for game in (1, 2, 3, 4, 5):
            for heading in ("Death 7", "Disappeared"):
                with self.subTest(game=game, record=heading):
                    v = self.load(game, [block(heading, "Pita", 5, 6, "Female",
                                               gone_parents(("Tane", 14, 2), ("Rua", 13, 14)))])
                    pita = next(p for p in v.known() if p.name == "Pita")
                    self.assertFalse(pita.alive)
                    father, mother = v.people[pita.father], v.people[pita.mother]
                    self.assertEqual((father.name, father.head, father.body, father.alive), ("Tane", 14, 2, True),
                                     "the Tane with those looks, never the other")
                    self.assertEqual((mother.name, mother.head, mother.body, mother.alive), ("Rua", 13, 14, True))
                    baby = next(p for p in v.known() if p.name == "Baby")
                    self.assertIsNone(baby.father, "the villager now in the record inherits nothing")
                    shown = info.plain_text(info.info_lines(v, ft.Edits(), pita.id))
                    self.assertIn("Tane", shown)
                    self.assertIn("Rua", shown)

    def test_a_founder_has_none(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = self.load(game, [block("Death 1", "Elder", 7, 7, "Male")])
                elder = next(p for p in v.known() if p.name == "Elder")
                self.assertEqual((elder.father, elder.mother), (None, None))


if __name__ == "__main__":
    unittest.main()
