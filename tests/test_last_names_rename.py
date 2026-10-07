"""Repair Saves & Logs' "Give villagers last names": the save, the patcher's files and the logs together
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
          father: tuple = ("", 0, 0), mother: tuple = ("", 0, 0), expecting: tuple = ("", 0, 0),
          health: int = 90) -> bytes:
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
    struct.pack_into("<i", e, n + 0xA4, health)          # record +0xE78; 0 or less is a body
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

    def test_a_body_is_never_offered_a_last_name(self):
        # An audit, 2026-10-06: A New Home already skipped bodies (a body keeps the name it died
        # with); the later games offered them.
        body = entry("Kaimi", 1, 2, 4, 4, health=0)
        data = self.save.read_bytes()[:TABLE + 4 * STRIDE] + body + bytes(64)
        self.save.write_bytes(data)
        self.assertNotIn("Kaimi", [v.name for v in ln.living(self.folder, 3, 1)])

    def test_stale_records_after_the_end_of_list_flag_are_nobody(self):
        # Live, 2026-10-06: a save keeps stale copies after the villagers; the game stops at the
        # first entry whose flag is 0 and never loads them, so they are never offered or renamed.
        ended = bytearray(entry("Gone", 0, 3, 1, 1))
        ended[0:4] = bytes(4)                                   # the writer's end-of-list flag
        ghost = entry("Ago", 0, 1, 5, 6)                        # a stale copy, still flagged 1
        data = self.save.read_bytes()[:TABLE + 4 * STRIDE] + bytes(ended) + ghost + bytes(64)
        self.save.write_bytes(data)
        self.assertEqual([v.name for v in ln.living(self.folder, 3, 1)], ["Ago", "Aipi", "Kid", "Orphan"])
        work = ln.plan(self.folder, 3, 1, self.chosen())
        save = next(c for c in work.changes if c.path == self.save)
        at = TABLE + 5 * STRIDE + 0x14
        self.assertEqual(save.updated[at:at + 4], b"Ago\0", "the stale copy is left as it is")

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

    def test_a_name_alone_is_renamed_only_when_every_namesake_is(self):
        # Codex (#553): a record with only a name (no looks) follows a rename only when every
        # living villager of that name takes the same new name.
        namesake = entry("Ago", 0, 2, 1, 2, likes=(7, 8, 9), dislikes=(10, 11, 12))
        data = self.save.read_bytes()[:TABLE + 4 * STRIDE] + namesake + bytes(64)
        self.save.write_bytes(data)
        bare = self._log("Tribe History/Village History 3.txt",
                         "=== Virtual Villagers 3 -- 2026-10-02 ===\nVillage: Tribe (Save 1)\n"
                         "Villager 1\n  Name: Ago\n\n")
        ago = next(v for v in ln.living(self.folder, 3, 1) if v.name == "Ago" and v.identity[1] == 5)
        work = ln.plan(self.folder, 3, 1, {ago.identity: "Akikai"})
        self.assertFalse(any(c.path == bare for c in work.changes), "the other Ago keeps his name")
        others = [v for v in ln.living(self.folder, 3, 1) if v.name == "Ago"]
        work = ln.plan(self.folder, 3, 1, {v.identity: "Akikai" for v in others})
        change = next(c for c in work.changes if c.path == bare)
        self.assertIn(b"  Name: Ago Akikai\r\n", change.updated)

    def test_another_games_titles_and_elders_are_left_alone(self):
        # Codex (#553): games sharing a folder share these files' names; each names its game.
        data = bytearray(self.titles.read_bytes())
        data[8] = 4
        self.titles.write_bytes(bytes(data))
        elders = self.folder / DATA / "Village Elders" / "Village Elders - Save 1.dat"
        elders.parent.mkdir(parents=True)
        line = b"E\t0\tAgo\t\t\t1\t0\r\n"
        for game, changed in ((4, False), (3, True)):
            with self.subTest(game=game):
                elders.write_bytes(b"VVFP VILLAGE ELDERS v2 game=%d\r\n" % game + line)
                work = ln.plan(self.folder, 3, 1, self.chosen())
                self.assertFalse(any(c.path == self.titles for c in work.changes))
                self.assertEqual(any(c.path == elders for c in work.changes), changed)
        roster = self.folder / DATA / "Village Statistics" / "Village Roster - Save 1.dat"
        roster.parent.mkdir(parents=True)
        roster.write_bytes(b"VVFP VILLAGE ROSTER v1\r\n0\tAgo\t-\r\n")
        work = ln.plan(self.folder, 3, 1, self.chosen())
        self.assertFalse(any(c.path == roster for c in work.changes), "no Village Statistics file names game 3")
        (roster.parent / "Village Statistics - Save 1.dat").write_bytes(b"VVFP VILLAGE STATISTICS v1 game=3\n")
        work = ln.plan(self.folder, 3, 1, self.chosen())
        self.assertTrue(any(c.path == roster for c in work.changes))

    def test_a_parent_reference_from_before_a_change_of_looks_is_asked(self):
        # Codex (#553): a child's father field keeps the looks he had when she was born.
        child = entry("Tama", 1, 1, 4, 4, father=("Ago", 3, 3), mother=("Aipi", 7, 8))
        data = self.save.read_bytes()[:TABLE + 4 * STRIDE] + child + bytes(64)
        self.save.write_bytes(data)
        work = ln.plan(self.folder, 3, 1, self.chosen())
        [question] = [q for q in work.questions if q.who == ("Ago", 3, 3)]
        yes = next(a for a in question.options if a.startswith("Yes"))
        tama = TABLE + 4 * STRIDE + 0x14
        save = next(c for c in work.changes if c.path == self.save)
        self.assertEqual(save.updated[tama + 0x24:tama + 0x28], b"Ago\0", "not answered: left alone")
        work = ln.plan(self.folder, 3, 1, self.chosen(), {question.key: yes})
        save = next(c for c in work.changes if c.path == self.save)
        self.assertEqual(save.updated[tama + 0x24:tama + 0x24 + 11], b"Ago Akikai\0")

    def test_a_damaged_titles_file_is_left_alone(self):
        self.titles.write_bytes(self.titles.read_bytes()[:30])      # count says 1, the entry is cut
        work = ln.plan(self.folder, 3, 1, self.chosen())
        self.assertFalse(any(c.path == self.titles for c in work.changes))
        self.assertTrue(any("damaged" in n for n in work.notes))
        ln.give_last_names(self.folder, 3, 1, self.chosen(), NoGame(), NOW)
        self.assertEqual(len(self.titles.read_bytes()), 30)


class NewHomeParentage(unittest.TestCase):
    """A New Home's Parentage Records roster (Codex, #553): an entry with recorded looks is matched
    by them alone; gender, family and name decide only an entry without looks, and only when every
    living holder of them takes one new name."""

    def test_a_namesake_with_other_looks_keeps_his_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            people = [ln.Living(0, "Ago", "Male", 5, 6, 1, "Akikai"), ln.Living(0, "Ago", "Male", 1, 2, 1, "Akikai")]
            renames = {("Ago", 5, 6): "Ago Akikai"}
            buf = bytearray(b"VP02" + bytes(8 + 256 * 36 + 256 * 92))

            def occupant(i, head, body):
                occ = 12 + i * 36
                buf[occ] = 1
                buf[occ + 2], buf[occ + 3] = head + 1 if head is not None else 0, body + 1 if body is not None else 0
                struct.pack_into("<i", buf, occ + 4, 1)
                buf[occ + 8:occ + 11] = b"Ago"

            occupant(0, 5, 6)
            occupant(1, 1, 2)
            occupant(2, None, None)
            path = data_dir / "Parentage Records" / "Virtual Villagers 1 Parentage Records - Save 1.dat"
            path.parent.mkdir()
            path.write_bytes(bytes(buf))
            result = ln.Plan(renames)
            ln._plan_vv1_parentage(result, data_dir, data_dir, 1, people, renames, renames, {})
            [change] = result.changes
            names = [ln._cstr(change.updated, 12 + i * 36 + 8, 28) for i in range(3)]
            self.assertEqual(names, ["Ago Akikai", "Ago", "Ago"],
                             "his looks decide; a looks-less entry is ambiguous while the namesake keeps his name")


class EveryoneAndWrongNames(unittest.TestCase):
    """The owner, 2026-10-07: a check for "Wrong last names", last names that can be changed
    (another rule or custom names), and last names for the villagers no longer in the village."""
    _log = GiveLastNames._log
    tearDown = GiveLastNames.tearDown

    def setUp(self):
        GiveLastNames.setUp(self)
        from unittest import mock
        named = mock.patch("vv_log_additions.current_villages", return_value={"Village: Tribe (Save 1)"})
        named.start()
        self.addCleanup(named.stop)

    def ids(self):
        people, _parents = ln.everyone(self.folder, 3, 1)
        return {(v.name, v.alive): v.identity for v in people}

    def test_the_gone_get_last_names_in_the_logs(self):
        ids = self.ids()
        self.assertIn(("Ago", False), ids, "the dead Ago of the Deaths log is listed")
        ln.give_last_names(self.folder, 3, 1, {ids[("Ago", False)]: "Moa"}, NoGame(), NOW)
        self.assertIn("  Name: Ago Moa\r\n", self.deaths.read_bytes().decode())
        self.assertEqual([v.name for v in ln.living(self.folder, 3, 1)][0], "Ago", "the living Ago is not him")

    def test_a_last_name_can_be_changed_and_the_rule_is_kept(self):
        ids = self.ids()
        ln.give_last_names(self.folder, 3, 1, {ids[("Ago", True)]: "Akikai"}, NoGame(), NOW, rule="father")
        ids = self.ids()
        ln.give_last_names(self.folder, 3, 1, {ids[("Ago Akikai", True)]: "Chapstick"}, NoGame(), NOW,
                           rule="father", mine={ids[("Ago Akikai", True)]: "Chapstick"})
        self.assertEqual([v.name for v in ln.living(self.folder, 3, 1)][0], "Ago Chapstick")
        rule, fixed = ln.read_record(self.folder, 3, 1)
        self.assertEqual((rule, fixed), ("father", {("Ago", 5, 6): "Chapstick"}))

    def test_wrong_last_names_are_found(self):
        ids = self.ids()
        # Kid's father is Ago: with "From the father", Kid Wikimak is wrong once Ago is a Chapstick.
        ln.give_last_names(self.folder, 3, 1, {ids[("Ago", True)]: "Chapstick", ids[("Kid", True)]: "Wikimak"},
                           NoGame(), NOW, rule="father", mine={ids[("Ago", True)]: "Chapstick"})
        rule, wrong = ln.wrong_last_names(self.folder, 3, 1)
        self.assertEqual(rule, "father")
        self.assertEqual([(v.name, now, should) for v, now, should in wrong if v.name.startswith("Kid")],
                         [("Kid Wikimak", "Wikimak", "Chapstick")])


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
        # Everyone -- the living and the gone -- with the last name they have now in the box.
        self.assertIn("people, parents = vv_last_names.everyone(folder, number, info.slot)", body)
        self.assertIn("start_value = names[\"chosen\"].get(v.identity, now[v.identity])", body)
        # Every one of the game's names is offered, the father's and the mother's first.
        self.assertIn("values=[none] + first + [n for n in pool if n not in first]", body)
        box = body[body.index("box = ttk.Combobox(inner,"):body.index("box.grid(")]
        self.assertNotIn('state="readonly"', box, "the player may type a last name")
        self.assertIn('vv_last_names.name_problem(number, "", last)', body)
        # The wrong ones are marked and can be put right.
        self.assertIn('ttk.Button(buttons, text="Fix wrong last names", command=by_rule)', body)


if __name__ == "__main__":
    unittest.main()
