"""Repair Saves' reconciliation follows a villager whose sex changed (native/shared/sex_change.h,
src/vv_sex_changes.py): the save's "Sex Changes" log -- or the Appearance changed record's Old sex / New sex
lines -- makes the two looks one villager: no lost villager, no new arrival, no question about the sex.
Without either, the old questions stand."""
from __future__ import annotations

import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_reconcile as rc  # noqa: E402
import vv_save_layout as layout  # noqa: E402
from test_reconcile import CASES, Village, fixture  # noqa: E402


def flipped(v: Village, data: bytes, rank: int) -> tuple[bytes, str, str]:
    """The save with villager `rank`'s sex field the other value; (save, old "M"/"F", new)."""
    buf = bytearray(data)
    at = v.entries(data)[rank]
    female = 2 if v.f.male == 1 else 1
    now = struct.unpack_from("<i", buf, at + v.f.sex)[0]
    struct.pack_into("<i", buf, at + v.f.sex, female if now == v.f.male else v.f.male)
    return bytes(buf), ("M" if now == v.f.male else "F"), ("F" if now == v.f.male else "M")


def sex_log(v: Village, name: str, old: str, new: str) -> None:
    path = v.folder / layout.save_root(1) / layout.SAVE_DATA / "Sex Changes" / "Sex Changes - Save 1.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"{old}\t{new}\t{name}\r\n".encode("cp1252"))


def history_record(name: str, head: int, body: int, old: str, new: str) -> str:
    words = {"M": "Male", "F": "Female"}
    return (f"Appearance changed\n  Name: {name}\n  Old head: {head}\n  Old body: {body}\n  New head: {head}\n"
            f"  New body: {body}\n  Old sex: {words[old]}\n  New sex: {words[new]}\n\n")


class SexChangeReconcile(unittest.TestCase):
    def village(self, tag: str, game: int) -> Village:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        return Village(root, game, fixture(f"vv{game}-{tag}-1"))

    def generations(self, v: Village, older: bytes, current: bytes) -> None:
        now = time.time()
        v.write_save(21, older, now - 600)
        v.write_save(1, current, now)

    def topics(self, v: Village, game: int) -> list[str]:
        return sorted(f.topic for f in rc.reconcile(v.folder, game, 1).questions)

    def test_save_copies_across_a_change_of_sex_are_one_villager(self):
        for tag, game in CASES[:5]:
            with self.subTest(game=game):
                v = self.village(tag, game)
                data = v.save_path(1).read_bytes()
                self.generations(v, data, data)
                before = self.topics(v, game)
                after, old, new = flipped(v, data, 0)
                name = v.people(after)[0].name
                self.generations(v, data, after)
                # No log: the change is a question (or a lost villager and a newcomer), as before.
                self.assertNotEqual(self.topics(v, game), before)
                sex_log(v, name, old, new)
                self.assertEqual(self.topics(v, game), before)

    def test_the_history_record_alone_is_enough(self):
        v = self.village("huttest", 3)
        data = v.save_path(1).read_bytes()
        after, old, new = flipped(v, data, 0)
        s = v.people(after)[0]
        self.generations(v, data, after)
        v.births(history_record(s.name, s.head, s.body, old, new))
        rec = rc.reconcile(v.folder, 3, 1)
        self.assertFalse([f for f in rec.questions if f.topic in ("sex", "lost", "new")], [f.text for f in rec.questions])

    def test_a_snapshot_of_the_old_sex_is_the_same_villager(self):
        for tag, game in CASES[:5]:
            with self.subTest(game=game):
                v = self.village(tag, game)
                data = v.save_path(1).read_bytes()
                people = v.people(data)
                after, old, new = flipped(v, data, 0)
                v.write_save(1, after)
                v.history([("2026-10-11 20:00:00", people)])
                asked = [f for f in rc.reconcile(v.folder, game, 1).questions]
                self.assertTrue(asked)                          # no record of the change: asked
                sex_log(v, people[0].name, old, new)
                asked = [f.text for f in rc.reconcile(v.folder, game, 1).questions
                         if people[0].name in f.text]
                self.assertEqual(asked, [])

    def test_a_death_of_the_other_sex_still_says_nothing_without_the_log(self):
        """A Death record of the other sex with the same name and looks says nothing of a villager -- unless
        the logs say the villager's sex changed (left())."""
        b = rc._Builder(Path("."), 3, 1, rc.Logs(), {})
        gone = rc.Seen("Ann", 3, 4, "Female")
        b.logs.departures.append(rc.Record("Death 1", rc.Seen("Ann", 3, 4, "Male"), Path("x")))
        b.departed = {("Ann", 3, 4)}
        self.assertIsNone(b.left(gone))
        b.logs.sex_changed = {"Ann"}
        self.assertEqual(b.left(gone), "Death 1")

    def test_pairing_rules(self):
        a = [rc.Seen("Ann", 3, 4, "Male", 100)]
        b = [rc.Seen("Ann", 3, 4, "Female", 120)]
        pairs, gone, new = rc._pair(a, b)
        self.assertEqual((len(pairs), len(gone), len(new)), (0, 1, 1))
        pairs, gone, new = rc._pair(a, b, {"Ann"})
        self.assertEqual((len(pairs), len(gone), len(new)), (1, 0, 0))
        self.assertFalse(rc._could_be(a[0], b[0], 3))
        self.assertTrue(rc._could_be(a[0], b[0], 3, changed={"Ann"}))
        # Two namesakes of the new sex: each still pairs with one; nothing is invented.
        pairs, gone, new = rc._pair(a + [rc.Seen("Ann", 3, 4, "Female", 50)],
                                    b + [rc.Seen("Ann", 3, 4, "Female", 60)], {"Ann"})
        self.assertEqual((len(pairs), len(gone), len(new)), (2, 0, 0))


if __name__ == "__main__":
    unittest.main()
