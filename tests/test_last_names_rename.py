"""Repair Logs' "Give villagers last names": the save, the patcher's files and the logs together
(src/vv_last_names.py).

The owner (2026-10-06): with the game closed, existing villagers get the last name the player
picks (the family's by default) in the save AND every log, so the logs keep matching the save.
These tests build a small The Secret City save and log folder by hand.
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
NOW = datetime(2026, 10, 6, 12, 0, 0)
STRIDE = 0x11C
TABLE = 0x40                       # where the made-up table starts in the file
FNV_BASIS, FNV_PRIME = 2166136261, 16777619


class NoGame:
    def find(self, exe_name):
        return []


class Running:
    def find(self, exe_name):
        return [1]


def _fnv(h: int, data: bytes) -> int:
    for b in data:
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFF
    return h


def entry(name: str, sex: int, family: int, head: int, body: int, likes=(1, 2, 3), dislikes=(4, 5, 6),
          father: tuple = ("", 0, 0), mother: tuple = ("", 0, 0), expecting: tuple = ("", 0, 0)) -> bytes:
    """One saved villager of The Secret City (name at entry +0x14)."""
    e = bytearray(STRIDE)
    struct.pack_into("<I", e, 0, 1)
    n = 0x14
    e[n:n + len(name)] = name.encode()
    struct.pack_into("<i", e, n - 4, family)
    struct.pack_into("<i", e, n - 0x0C, sex)
    struct.pack_into("<i", e, n - 0x10, 600)              # age
    struct.pack_into("<i", e, n + 0x1C, head)
    struct.pack_into("<i", e, n + 0x20, body)
    for (pname, phead, pbody), at, looks in ((father, 0x24, 0x58), (mother, 0x3D, 0x60)):
        e[n + at:n + at + len(pname)] = pname.encode()
        struct.pack_into("<ii", e, n + looks, phead, pbody)
    e[n + 0x74:n + 0x74 + len(expecting[0])] = expecting[0].encode()
    struct.pack_into("<ii", e, n + 0x90, expecting[2], expecting[1])
    struct.pack_into("<3i", e, n + 0xF0, *likes)
    struct.pack_into("<3i", e, n + 0xFC, *dislikes)
    return bytes(e)


def title_identity(name: str, likes, dislikes) -> int:
    h = _fnv(_fnv(FNV_BASIS, name.encode()), b"\xff")
    h = _fnv(h, struct.pack("<3i", *likes))
    return _fnv(h, struct.pack("<3i", *dislikes)) or 1


class GiveLastNames(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        people = [
            entry("Ago", 0, 1, 5, 6),                                          # Akikai
            entry("Aipi", 1, 50, 7, 8, expecting=("Ago", 5, 6)),               # Wikimak, expecting Ago's
            entry("Kid", 0, 50, 9, 9, father=("Ago", 5, 6), mother=("Aipi", 7, 8)),
            entry("Orphan", 1, 2, 3, 3, father=("Ago", 1, 1)),                 # a dead Ago, other looks
        ]
        save = bytearray(b"ldwg" + bytes(TABLE - 4)) + b"".join(people) + bytes(64)
        self.save = self.folder / "Virtual Villagers - The Secret City1.ldw"
        self.save.write_bytes(bytes(save))
        titles = self.folder / DATA / "Custom Titles" / "Custom Titles - Save 1.dat"
        titles.parent.mkdir(parents=True)
        self.old_fp = title_identity("Ago", (1, 2, 3), (4, 5, 6))
        titles.write_bytes(struct.pack("<4I", 0x31544356, 2, 3, 1) + struct.pack("<II", 0, self.old_fp)
                           + b"Seer".ljust(32, b"\0"))
        self.titles = titles
        self.history = self._log("Tribe History/Village History 1.txt",
                                 "=== Virtual Villagers 3 -- 2026-10-01 ===\nVillage: Tribe (Save 1)\n"
                                 "Villager 1\n  Name: Ago\n  Head: 5\n  Body: 6\n\n"
                                 "Villager 2\n  Name: Kid\n  Head: 9\n  Body: 9\n  Parents:\n"
                                 "    Father: Ago\n      Head: 5\n      Body: 6\n"
                                 "    Mother: Aipi\n      Head: 7\n      Body: 8\n\n")
        self.births = self._log("Births and Conceptions/Virtual Villagers 3 Births and Conceptions Log 1.txt",
                                "Village: Tribe (Save 1)\n"
                                "Birth\n  Child: Kid\n    Head: 9\n    Body: 9\n  Mother: Aipi\n    Head: 7\n"
                                "    Body: 8\n  Father: Ago\n    Head: 5\n    Body: 6\n\n"
                                "Birth\n  Child: Aipi\n    Head: 2\n    Body: 2\n  Mother: Ma\n    Head: 1\n"
                                "    Body: 1\n  Father: Pa\n    Head: 1\n    Body: 1\n\n")
        self.deaths = self._log("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                                "Village: Tribe (Save 1)\nDeath 1\n  Name: Ago\n  Age at death: 1400\n"
                                "  Head: 1\n  Body: 1\n\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _log(self, relative: str, text: str) -> Path:
        path = self.folder / LOGS / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", "\r\n").encode())
        return path

    def chosen(self, **extra):
        people = {v.name: v for v in ln.living(self.folder, 3, 1)}
        choice = {people["Ago"].identity: people["Ago"].default, people["Aipi"].identity: people["Aipi"].default}
        choice.update(extra)
        return choice

    def test_the_family_last_names_are_the_defaults(self):
        people = {v.name: v for v in ln.living(self.folder, 3, 1)}
        self.assertEqual(people["Ago"].default, "Akikai")
        self.assertEqual(people["Aipi"].default, "Wikimak")

    def test_the_save_names_and_every_link_to_the_living_follow(self):
        ln.give_last_names(self.folder, 3, 1, self.chosen(), NoGame(), NOW)
        names = [v.name for v in ln.living(self.folder, 3, 1)]
        self.assertEqual(names, ["Ago Akikai", "Aipi Wikimak", "Kid", "Orphan"])
        data = self.save.read_bytes()
        kid = TABLE + 2 * STRIDE + 0x14
        self.assertEqual(data[kid + 0x24:kid + 0x24 + 11], b"Ago Akikai\0", "the child's father")
        self.assertEqual(data[kid + 0x3D:kid + 0x3D + 13], b"Aipi Wikimak\0", "...and mother")
        aipi = TABLE + STRIDE + 0x14
        self.assertEqual(data[aipi + 0x74:aipi + 0x74 + 11], b"Ago Akikai\0", "the father of her baby")
        orphan = TABLE + 3 * STRIDE + 0x14
        self.assertEqual(data[orphan + 0x24:orphan + 0x28], b"Ago\0", "a dead Ago (other looks) is not him")

    def test_the_custom_title_follows_its_villager(self):
        ln.give_last_names(self.folder, 3, 1, self.chosen(), NoGame(), NOW)
        fp = struct.unpack_from("<I", self.titles.read_bytes(), 20)[0]
        self.assertEqual(fp, title_identity("Ago Akikai", (1, 2, 3), (4, 5, 6)))

    def test_the_logs_follow_and_the_dead_keep_their_names(self):
        ln.give_last_names(self.folder, 3, 1, self.chosen(), NoGame(), NOW)
        history = self.history.read_bytes().decode()
        self.assertIn("  Name: Ago Akikai\r\n", history)
        self.assertIn("    Father: Ago Akikai\r\n      Head: 5", history)
        self.assertIn("    Mother: Aipi Wikimak\r\n", history)
        births = self.births.read_bytes().decode()
        self.assertIn("  Father: Ago Akikai\r\n", births)
        self.assertIn("  Child: Aipi\r\n    Head: 2", births, "her own Birth record had other looks: asked, not guessed")
        self.assertIn("  Name: Ago\r\n", self.deaths.read_bytes().decode(), "a Death record is never a living villager's")

    def test_records_with_other_looks_are_asked_about(self):
        work = ln.plan(self.folder, 3, 1, self.chosen())
        [question] = [q for q in work.questions if q.who == ("Aipi", 2, 2)]
        self.assertEqual(question.default, ln.NOT_THEM)
        yes = next(a for a in question.options if a.startswith("Yes"))
        work = ln.plan(self.folder, 3, 1, self.chosen(), {question.key: yes})
        logs = next(c for c in work.changes if c.path == self.births)
        self.assertIn(b"  Child: Aipi Wikimak\r\n    Head: 2", logs.updated)
        self.assertFalse(any(q.who[0] == "Ago" and q.who[1:] == (1, 1) for q in work.questions),
                         "the dead Ago's looks are a Death record's: never asked")

    def test_it_is_refused_while_the_game_runs_and_too_long_names(self):
        with self.assertRaises(tools.GameRunning):
            ln.give_last_names(self.folder, 3, 1, self.chosen(), Running(), NOW)
        self.assertIn(b"Ago\0", self.save.read_bytes())
        people = {v.name: v for v in ln.living(self.folder, 3, 1)}
        with self.assertRaises(ln.LastNamesError):
            ln.plan(self.folder, 3, 1, {people["Ago"].identity: "Abcdefghijklmnopqrstuvwxyz"})
        self.assertEqual(ln.name_problem(3, "Ago", "Two words"), "A last name is one word of printable "
                                                                 "letters, no spaces or accents.")

    def test_a_backup_comes_first(self):
        result = ln.give_last_names(self.folder, 3, 1, self.chosen(), NoGame(), NOW)
        backup = Path(result.backup.backup_folder)
        self.assertTrue((backup / self.save.name).is_file())
        self.assertIn(b"Ago\0", (backup / self.save.name).read_bytes())


class CodexReview(GiveLastNames):
    """PR #553's review of the last names."""

    def test_another_games_logs_in_the_same_folder_are_left_alone(self):
        other = self._log("Deaths/Virtual Villagers 4 Deaths Log 1.txt",
                          "Village: Tribe (Save 1)\nArrived 1\n  Name: Ago\n  Head: 5\n  Body: 6\n\n")
        shared = self._log("Tribe History/Village History 2.txt",
                           "=== Virtual Villagers 4 -- 2026-10-01 ===\nVillage: Tribe (Save 1)\n"
                           "Villager 1\n  Name: Ago\n  Head: 5\n  Body: 6\n\n")
        ln.give_last_names(self.folder, 3, 1, self.chosen(), NoGame(), NOW)
        self.assertIn("  Name: Ago\r\n", other.read_bytes().decode(), "The Tree of Life's own log")
        self.assertIn("  Name: Ago\r\n", shared.read_bytes().decode(), "The Tree of Life's History snapshot")
        self.assertIn("  Name: Ago Akikai\r\n", self.history.read_bytes().decode())

    def test_two_villagers_one_title_identity_must_share_the_last_name(self):
        twin = entry("Ago", 0, 2, 1, 2)                     # Ago's name and likes, other looks
        data = self.save.read_bytes()[:TABLE + 4 * STRIDE] + twin + bytes(64)
        self.save.write_bytes(data)
        people = [v for v in ln.living(self.folder, 3, 1) if v.name == "Ago"]
        self.assertEqual(len(people), 2)
        with self.assertRaises(ln.LastNamesError) as raised:
            ln.plan(self.folder, 3, 1, {people[0].identity: "Akikai", people[1].identity: "Alosaka"})
        self.assertIn("same last name", str(raised.exception))
        work = ln.plan(self.folder, 3, 1, {people[0].identity: "Akikai", people[1].identity: "Akikai"})
        self.assertEqual(len(work.renames), 2)
        # An identity no titles or mask file holds decides nothing: two villagers of one name in
        # different families take their own families' last names (the self-review, #553).
        self.titles.unlink()
        work = ln.plan(self.folder, 3, 1, {people[0].identity: "Akikai", people[1].identity: "Alosaka"})
        self.assertEqual(sorted(work.renames.values()), ["Ago Akikai", "Ago Alosaka"])

    def test_a_damaged_titles_file_is_left_alone(self):
        self.titles.write_bytes(self.titles.read_bytes()[:30])      # count says 1, the entry is cut
        work = ln.plan(self.folder, 3, 1, self.chosen())
        self.assertFalse(any(c.path == self.titles for c in work.changes))
        self.assertTrue(any("damaged" in n for n in work.notes))
        ln.give_last_names(self.folder, 3, 1, self.chosen(), NoGame(), NOW)
        self.assertEqual(len(self.titles.read_bytes()), 30)


class TheWindow(unittest.TestCase):
    SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def test_repair_logs_offers_it_unticked_and_runs_it_off_the_main_thread(self):
        body = self.SOURCE[self.SOURCE.index("    def _repair_checklist("):self.SOURCE.index("    def _repair_questions(")]
        self.assertIn('text="Give villagers last names, in the game and the logs"', body)
        self.assertIn("names_var = tk.BooleanVar(value=False)", body, "renaming is never ticked for the player")
        repair = self.SOURCE[self.SOURCE.index("    def _repair_logs("):self.SOURCE.index("    def _repair_checklist(")]
        self.assertIn("lambda: vv_last_names.give_last_names(folder, number, info.slot, names[\"chosen\"],", repair)

    def test_the_family_name_is_chosen_for_you_and_any_can_be_typed(self):
        body = self.SOURCE[self.SOURCE.index("    def _last_names_dialog("):self.SOURCE.index("    def _repair_questions(")]
        self.assertIn("v.default or none", body)
        self.assertIn("values=[none] + list(checker.LAST_NAMES[number])", body)
        self.assertNotIn('state="readonly"', body, "the player may type a last name")
        self.assertIn("vv_last_names.name_problem(number, v.name, last)", body)
        # A name with a space already has a last name: nothing is chosen for it (Codex, #553).
        self.assertIn('value=names["chosen"].get(v.identity) or (none if spaced else v.default or none)', body)
        self.assertIn('if " " not in v.name:\n                    value.set(choice(v))', body)


if __name__ == "__main__":
    unittest.main()
