"""Repair Saves & Logs moves a record written into ANOTHER save's log to its own save's log.

The owner's Secret City, 2026-10-31: Save 1's Births and Conceptions log holds Conception 312 (Mother Kiwi
Jumapili, Father Motu Okelani) and Conception 316 (Mother Matate Jumapili, Father Motu Okelani) -- Save 2's
villagers only -- held by the parentage companion and written at Save 1's save.  The owner chose to move
them into Save 2's log (src/vv_misfiled_records.py).  These logs are fakes in that shape: no save, the
villages known from their Village History snapshots.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_additions as additions  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_misfiled_records as misfiled  # noqa: E402

SAVES = "Virtual Villagers Fun Patcher"
BIRTHS = "Virtual Villagers 3 Births and Conceptions Log 1.txt"
HELD = ("  Note: Recorded before this village was saved, among villagers who were\n"
        "    not in it when it was -- likely the game's pre-tribe simulation, or a\n"
        "    tribe left unsaved by Start Over.\n")


def conception(number: int, mother: tuple, father: tuple, held: bool) -> str:
    def person(label, p):
        name, age, sex, head, body, likes, dislikes = p
        return (f"  {label}: {name}\n    Age at conception: {age}\n    Sex: {sex}\n    Head: {head}\n"
                f"    Body: {body}\n    Likes: {likes}\n    Dislikes: {dislikes}\n")
    return (f"Conception {number}\n" + person("Mother", mother) + person("Father", father)
            + "  Babies nursing: 1\n" + (HELD if held else "") + "\n")


KIWI = ("Kiwi Jumapili", 931, "Female", 3, 16, "learning", "dreaming, snakes")
MATATE = ("Matate Jumapili", 890, "Female", 3, 7, "(none)", "resting")
MOTU = ("Motu Okelani", 750, "Male", 21, 2, "exploring, children", "(none)")
GINGER = ("Ginger Bandele", 861, "Female", 17, 12, "running", "alchemy")
PIO = ("Pio Bandele", 566, "Male", 19, 8, "thunder", "(none)")
BIKINI = ("Bikini", 397, "Female", 16, 5, "rocks", "children")
PIKO = ("Piko", 498, "Male", 0, 15, "(none)", "(none)")


def snapshot(header: str, people: list[tuple]) -> str:
    out = f"=== Virtual Villagers 3 -- 2026-10-31 15:10:35 ===\n{header}\n\n"
    for n, (name, age, sex, head, body, likes, dislikes) in enumerate(people, 1):
        out += (f"Villager {n}\n  Name: {name}\n  Age: {age}\n  Sex: {sex}\n  Head: {head}\n  Body: {body}\n"
                f"  Likes: {likes}\n  Dislikes: {dislikes}\n\n")
    return out


class Fixture:
    """A Secret City save folder with two villages, as text files only (CRLF, as the games write)."""

    def __init__(self, base: Path):
        self.folder = base
        self.h1 = "Village: Kalahuna Tribe 3: N (Save 1)"
        self.h2 = "Village: Kalahuna Tribe 3: M (Save 2)"

    def write(self, rel: str, text: str) -> Path:
        path = self.folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
        return path

    def births(self, slot: int) -> Path:
        return self.folder / SAVES / f"Save {slot}" / "Logs" / "Births and Conceptions" / BIRTHS

    def build(self, save1_extra: list[tuple] = (), save1_records: str | None = None) -> None:
        self.write(f"{SAVES}\\Save 1\\Logs\\Tribe History\\Village History 1.txt",
                   snapshot(self.h1, [GINGER, PIO, *save1_extra]))
        self.write(f"{SAVES}\\Save 2\\Logs\\Tribe History\\Village History 1.txt",
                   snapshot(self.h2, [KIWI, MATATE, MOTU]))
        self.write(f"{SAVES}\\Save 2\\Logs\\Births and Conceptions\\{BIRTHS}",
                   self.h2 + "\n" + conception(285, KIWI[:1] + (928,) + KIWI[2:], MOTU[:1] + (747,) + MOTU[2:],
                                               False))
        if save1_records is None:
            save1_records = (conception(310, GINGER, PIO, False)
                             + conception(311, BIKINI, PIKO, True)
                             + conception(312, KIWI, MOTU, True)
                             + conception(315, GINGER, PIO, False)
                             + conception(316, MATATE, MOTU, True))
        self.write(f"{SAVES}\\Save 1\\Logs\\Births and Conceptions\\{BIRTHS}", self.h1 + "\n" + save1_records)


class MisfiledRecordsTests(unittest.TestCase):
    def setUp(self) -> None:
        # A short base: the per-save paths are long (the CI's temp folder is deep).
        self.base = Path(tempfile.mkdtemp(prefix="vvmf"))
        self.fx = Fixture(self.base)

    def tearDown(self) -> None:
        shutil.rmtree(self.base, ignore_errors=True)

    def plan(self, slot: int = 1) -> additions.Kind:
        return misfiled.plan(self.base, 3, slot)

    def apply(self, kind: additions.Kind, answer: str = misfiled.MOVE_IT) -> dict:
        return additions.apply(self.base, [kind], {kind.id}, {k: answer for k in kind.questions})

    def test_the_other_saves_records_are_offered_and_nothing_else(self):
        self.fx.build()
        kind = self.plan()
        self.assertEqual(sorted(q.text.split(" (")[0] for q in kind.questions.values()),
                         ["Conception 312", "Conception 316"])
        for q in kind.questions.values():
            self.assertIn("its villagers are Save 2's only", q.text)
            self.assertEqual(q.options, [misfiled.MOVE_IT, misfiled.LEAVE_IT])
            self.assertEqual(q.default, misfiled.MOVE_IT)
        self.assertEqual({i.path for i in kind.inserts}, {self.fx.births(2)})
        self.assertEqual({r.path for r in kind.removes}, {self.fx.births(1)})
        # Save 2's log holds nothing of Save 1's.
        self.assertEqual(len(self.plan(2).questions), 0)

    def test_moving_puts_them_in_their_own_log_with_their_numbers(self):
        self.fx.build()
        before1 = self.fx.births(1).read_bytes()
        done = self.apply(self.plan())
        self.assertEqual(sorted(f.name for f in done["misfiled"]),
                         sorted(str(p.relative_to(self.base)) for p in (self.fx.births(1), self.fx.births(2))))
        one = self.fx.births(1).read_bytes().decode("latin-1")
        two = self.fx.births(2).read_bytes().decode("latin-1")
        self.assertNotIn("Kiwi Jumapili", one)
        self.assertNotIn("Matate Jumapili", one)
        # The pre-tribe simulation's record and Save 1's own stay exactly as they were.
        for kept in ("Conception 310\r\n", "Conception 311\r\n  Mother: Bikini", "Conception 315\r\n"):
            self.assertIn(kept, one)
        self.assertEqual(one.count("Recorded before this village was saved"), 1)
        # Appended after Save 2's own record, in order, numbers kept, text kept, one note added each.
        self.assertLess(two.index("Conception 285"), two.index("Conception 312"))
        self.assertLess(two.index("Conception 312"), two.index("Conception 316"))
        moved = conception(312, KIWI, MOTU, True).replace("\n", "\r\n")
        self.assertIn(moved[:-2] + misfiled.moved_note(1) + "\r\n\r\n", two)
        self.assertEqual(two.count(misfiled.moved_note(1)), 2)
        self.assertNotIn("\n\n", two.replace("\r\n", ""))           # CRLF throughout
        self.assertEqual(two.count("Village: "), 1)                 # under Save 2's own header
        # Save 1's file lost exactly the two records, blank lines included.
        removed = (conception(312, KIWI, MOTU, True) + conception(316, MATATE, MOTU, True)).replace("\n", "\r\n")
        self.assertEqual(len(before1) - len(one.encode("latin-1")), len(removed.encode("latin-1")))
        # A copy of each file was kept first.
        copies = list(self.base.rglob("*.before-*"))
        self.assertEqual(len(copies), 2, copies)
        # Nothing left to move.
        self.assertEqual(len(self.plan().questions), 0)

    def test_leave_it_changes_nothing(self):
        self.fx.build()
        one, two = self.fx.births(1).read_bytes(), self.fx.births(2).read_bytes()
        self.apply(self.plan(), misfiled.LEAVE_IT)
        self.assertEqual(self.fx.births(1).read_bytes(), one)
        self.assertEqual(self.fx.births(2).read_bytes(), two)

    def test_a_villager_in_two_saves_is_never_moved(self):
        # Kiwi Jumapili is in Save 1's village too (a copied village): which save the record is can not
        # be told, so it stays, with a note.
        self.fx.build(save1_extra=[KIWI])
        kind = self.plan()
        self.assertEqual([q.text.split(" (")[0] for q in kind.questions.values()], ["Conception 316"])
        self.assertEqual(kind.notes, [])          # in Save 1's own village: simply not moved

    def test_a_villager_in_two_other_saves_is_left_with_a_note(self):
        self.fx.build()
        self.fx.write(f"{SAVES}\\Save 3\\Logs\\Tribe History\\Village History 1.txt",
                      snapshot("Village: Copy (Save 3)", [KIWI]))
        kind = self.plan()
        self.assertEqual([q.text.split(" (")[0] for q in kind.questions.values()], ["Conception 316"])
        self.assertTrue(any("Conception 312" in n and "2 saves' villages" in n for n in kind.notes), kind.notes)

    def test_only_held_records_are_looked_at(self):
        # The same Save 2 conception WITHOUT the held note (written straight to the log) is left alone.
        self.fx.build(save1_records=conception(312, KIWI, MOTU, False))
        self.assertEqual(len(self.plan().questions), 0)

    def test_different_likes_are_another_villager(self):
        other = KIWI[:5] + ("rocks",) + KIWI[6:]
        self.fx.build(save1_records=conception(312, other, MOTU, True))
        self.assertEqual(len(self.plan().questions), 0)

    def test_a_parent_younger_than_the_other_village_ever_had_them_is_not_moved(self):
        young = KIWI[:1] + (100,) + KIWI[2:]
        self.fx.build(save1_records=conception(312, young, MOTU, True))
        self.assertEqual(len(self.plan().questions), 0)

    def test_the_wrong_log_is_untouched_when_the_new_one_cannot_be_written(self):
        self.fx.build()
        kind = self.plan()
        one, two = self.fx.births(1).read_bytes(), self.fx.births(2).read_bytes()
        real = os.replace

        def failing(src, dst, *a, **k):
            if Path(dst) == self.fx.births(2):
                raise OSError("locked")
            return real(src, dst, *a, **k)
        with mock.patch.object(additions.os, "replace", side_effect=failing):
            with self.assertRaises(tools.LogToolError):
                self.apply(kind)
        self.assertEqual(self.fx.births(1).read_bytes(), one)
        self.assertEqual(self.fx.births(2).read_bytes(), two)

    def test_a_move_half_done_is_finished_without_a_second_copy(self):
        # The new log was written and the old one was not (a failure between them): the next Repair only
        # takes the record out of the wrong log.
        self.fx.build()
        kind = self.plan()
        real = os.replace

        def failing(src, dst, *a, **k):
            if Path(dst) == self.fx.births(1):
                raise OSError("locked")
            return real(src, dst, *a, **k)
        with mock.patch.object(additions.os, "replace", side_effect=failing):
            with self.assertRaises(tools.LogToolError):
                self.apply(kind)
        self.assertIn("Kiwi Jumapili", self.fx.births(1).read_bytes().decode("latin-1"))
        again = self.plan()
        self.assertEqual(len(again.questions), 2)
        self.assertEqual(again.inserts, [])
        self.apply(again)
        two = self.fx.births(2).read_bytes().decode("latin-1")
        self.assertEqual(two.count("Conception 312\r\n"), 1)
        self.assertEqual(two.count("Conception 316\r\n"), 1)
        self.assertNotIn("Kiwi Jumapili", self.fx.births(1).read_bytes().decode("latin-1"))

    def test_repair_offers_it_with_every_other_step(self):
        source = (ROOT / "src" / "vv_log_additions.py").read_text(encoding="utf-8")
        self.assertIn("kinds.append(vv_misfiled_records.plan(folder, game, slot))", source)
        self.assertIn("misfiled", additions.CHECKED)
        self.assertIn("misfiled", additions.ADDED)
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn('if kind.id == "misfiled"', gui)


if __name__ == "__main__":
    unittest.main()
