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


class NamesTypedBeforeTheRecord(unittest.TestCase):
    """A last name typed in v1.35.62, before the village kept a record, is still a last name: it is
    replaced, never given a second one (regression audit, 2026-10-07)."""

    def test_any_later_word_is_a_last_name(self):
        self.assertEqual(ln.split_name(1, "Chapa Chapstick"), ("Chapa", "Chapstick", ""))
        self.assertEqual(ln.split_name(3, "Chapa Chapstick II"), ("Chapa", "Chapstick", "II"))
        self.assertEqual(ln.with_last(1, "Chapa Chapstick", "Akikai"), "Chapa Akikai")
        self.assertEqual(ln.with_last(1, "Chapa Chapstick II", ""), "Chapa II")
        self.assertEqual(ln.split_name(1, "Soda II"), ("Soda", "", "II"))
        self.assertEqual(ln.split_name(1, "Soda"), ("Soda", "", ""))

    def test_the_matchmaker_reads_last_names_the_same_way(self):
        import vv_genealogy as gen
        self.assertEqual(gen._last_name("Soda Akikai II"), "Akikai")
        self.assertEqual(gen._last_name("Soda II"), "")
        self.assertEqual(gen._last_name("Mia Akikai"), "Akikai")
        self.assertEqual(gen._last_name("Mia"), "")


class TwoWordNamesAreAsked(unittest.TestCase):
    """The owner, 2026-10-07, on a two-word name whose second word is no known last name: "Ask per
    villager" -- ticked (a last name) by default, unticked keeps the words as one first name."""

    def test_the_player_says_which_names_are_one_first_name(self):
        self.assertEqual(ln.guessed_last_name(1, "Big Bob"), "Bob")
        self.assertEqual(ln.guessed_last_name(1, "Soda Akikai II"), "", "one of the game's own: nothing to ask")
        self.assertEqual(ln.guessed_last_name(1, "Chapa Chapstick", {"Chapstick"}), "", "on record: nothing to ask")
        whole = {ln.WHOLE + "Big Bob"}
        self.assertEqual(ln.split_name(1, "Big Bob II", whole), ("Big Bob", "", "II"))
        self.assertEqual(ln.with_last(1, "Big Bob", "Akikai", whole), "Big Bob Akikai")
        self.assertEqual(ln.with_last(1, "Big Bob", "Akikai"), "Big Akikai")
        self.assertEqual(ln.guessed_last_name(1, "Big Bob", whole), "Bob", "still asked, answered unticked")

    def test_the_answer_is_kept_with_the_village(self):
        with tempfile.TemporaryDirectory() as tmp:
            ln.write_record(Path(tmp), 1, 2, "father", {("Chapa", 1, 1): "Chapstick"}, {"Big Bob"})
            self.assertEqual(ln.read_record(Path(tmp), 1, 2), ("father", {("Chapa", 1, 1): "Chapstick"}))
            self.assertEqual(ln.read_whole(Path(tmp), 1, 2), {"Big Bob"})
            self.assertEqual(ln.known_names(Path(tmp), 1, 2), {"Chapstick", ln.WHOLE + "Big Bob"})
            # A later write without the answers keeps them.
            ln.write_record(Path(tmp), 1, 2, "mother", {})
            self.assertEqual(ln.read_whole(Path(tmp), 1, 2), {"Big Bob"})


class TheRepairsLogFollowsARename(unittest.TestCase):
    """The Repairs log (left out of the checker's log list) names villagers in its own words; a rename
    reaches it where the name is one villager's alone, as a whole name (2026-10-07: "(no last name)
    should completely remove the last name")."""

    def test_unique_whole_names_are_renamed_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            log = folder / LOGS / "Repairs" / "Virtual Villagers 1 Repairs Log 1.txt"
            log.parent.mkdir(parents=True)
            text = ("Village: Kalahuna Tribe 1 (Save 1)\r\n"
                    "Pregnancy: Chapa Wanjiko -- father Usutu Bahati (was unknown)\r\n"
                    "Pregnancy: Iruwa Bahati I -- father Silko Akikai (was unknown)\r\n"
                    "Also: Chapa Wanjikoa and Kaula Bahati II\r\n"
                    "Set to unknown: Kaula Bahati -- (was father Iruwa Bahati I, mother Chapa Wanjiko)\r\n"
                    # native/vv1_parentage/vv1_crosscheck.inc's own sentence
                    "Pregnancy over: Chapa Wanjiko -- expected father Iruwa Bahati I cleared (not expecting)\r\n\r\n"
                    "Village: Other Tribe (Save 2)\r\n"
                    "Pregnancy: Chapa Wanjiko -- father Ago (was unknown)\r\n")
            log.write_bytes(text.encode("latin-1"))
            result = ln.Plan({})
            ln._plan_repairs_logs(result, folder, 1, 1, {"Chapa Wanjiko": {"Chapa"}, "Iruwa Bahati I": {"Iruwa I"},
                                                         "Kaula": {"Kaula Wanjiko"}, "": {"Wanjiko"}}, None)
            self.assertEqual(len(result.changes), 1)
            after = result.changes[0].updated.decode("latin-1")
            self.assertIn("Pregnancy: Chapa -- father Usutu Bahati (was unknown)\r\n", after)
            self.assertIn("Pregnancy: Iruwa I -- father Silko Akikai", after)
            # Not a whole name (Chapa Wanjikoa), a numbered namesake (Kaula Bahati II), another slot;
            # renaming "Kaula" never touches "Kaula Bahati", and an empty name renames nothing.
            self.assertIn("Also: Chapa Wanjikoa and Kaula Bahati II\r\n", after)
            self.assertIn("Set to unknown: Kaula Bahati -- (was father Iruwa I, mother Chapa)\r\n", after)
            self.assertNotIn("Wanjiko Bahati", after)
            self.assertIn("Pregnancy over: Chapa -- expected father Iruwa I cleared (not expecting)", after)
            self.assertIn("Pregnancy: Chapa Wanjiko -- father Ago", after)
            self.assertEqual(log.read_bytes().decode("latin-1"), text, "planning writes nothing")

    def test_a_namesake_the_logs_know_keeps_every_line(self):
        # Codex, #566: a living Ago renamed while a buried Ago keeps the name -- "Ago" is not one
        # villager's alone, so no name-only line changes.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            log = folder / LOGS / "Repairs" / "Virtual Villagers 1 Repairs Log 1.txt"
            log.parent.mkdir(parents=True)
            log.write_bytes(b"Village: Tribe (Save 1)\r\nPregnancy: Ago -- father Tomi (was unknown)\r\n")
            deaths = folder / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt"
            deaths.parent.mkdir(parents=True)
            deaths.write_bytes(b"Village: Tribe (Save 1)\r\nDeath 1\r\n  Name: Ago\r\n  Head: 9\r\n  Body: 9\r\n\r\n")
            result = ln.Plan({})
            ln._plan_repairs_logs(result, folder, 1, 1, {"Ago": {"Ago Akikai"}}, None,
                                  renames={("Ago", 1, 1): "Ago Akikai"})
            self.assertEqual(result.changes, [])
            # A gone Ago whose older record has no looks may be a namesake: not unique either (Codex, #566).
            older = folder / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 2.txt"
            older.write_bytes(b"Village: Tribe (Save 1)\r\nDeath 1\r\n  Name: Tomi\r\n\r\n")
            result = ln.Plan({})
            ln._plan_repairs_logs(result, folder, 1, 1, {"Tomi": {"Tomi Akikai"}}, None,
                                  renames={("Tomi", 1, 1): "Tomi Akikai"})
            self.assertEqual(result.changes, [])
            older.unlink()
            # The buried Ago renamed too (Number Duplicate Names numbers the dead): every Ago is renamed.
            result = ln.Plan({})
            ln._plan_repairs_logs(result, folder, 1, 1, {"Ago": {"Ago Akikai"}}, None,
                                  renames={("Ago", 1, 1): "Ago Akikai", ("Ago", 9, 9): "Ago Akikai"})
            self.assertEqual(len(result.changes), 1)


class EveryRenameIsHeldToTheGamesRoom(unittest.TestCase):
    """The owner: a character limit "IN EVERY SINGLE PLACE A RENAME (OUTSIDE OF THE GAME) CAN
    HAPPEN" -- plan_renames refuses, before reading anything, a name the game cannot hold."""

    def test_too_long_empty_or_unprintable_names_are_refused(self):
        for game in range(1, 6):
            for bad in ("x" * (ln.ROOM[game] + 1), "", "Soda\x01", "Soda\x7f"):
                with self.subTest(game=game, bad=bad):
                    with self.assertRaises(ln.LastNamesError):
                        ln.plan_renames(Path("no such folder"), game, 1, {("Soda", 1, 1): bad})


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
    e[n:n + len(name)] = name.encode("latin-1")           # as the games keep names
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
            folder = Path(tmp)
            data_dir = folder / ln.tools.DATA
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
            # In "Parentage Records", where an older build kept it ("Parents (A New Home)" now,
            # src/vv_save_layout.py): found there while it has not moved.
            path = data_dir / "Parentage Records" / "Virtual Villagers 1 Parentage Records - Save 1.dat"
            path.parent.mkdir(parents=True)
            path.write_bytes(bytes(buf))
            result = ln.Plan(renames)
            ln._plan_vv1_parentage(result, folder, data_dir, 1, people, renames, renames, {})
            self.assertEqual(result.changes[0].path, path)
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
        self.assertIn("values=[none, custom] + first + [n for n in pool if n not in first]", body)
        box = body[body.index("box = ttk.Combobox(inner,"):body.index("box.grid(")]
        self.assertNotIn('state="readonly"', box, "the player may type a last name")
        self.assertIn("vv_last_names.name_problem(number, split(v.name)[0], last)", body)
        # The wrong ones are marked and can be put right.
        self.assertIn('ttk.Button(buttons, text="Fix wrong last names", command=fix_wrong)', body)


def grave_buffer(game: int, graves: dict[int, tuple]) -> bytearray:
    """A save holding only `game`'s grave table: place -> (name, age, head, body).  Every byte of a
    used place outside its name, age (and looks) is 0xAA, so what a rename leaves alone shows."""
    base, slots, stride, cap, age_at, looks = ln.GRAVES[game]
    buf = bytearray(base + slots * stride)
    for place, (name, age, head, body) in graves.items():
        at = base + place * stride
        buf[at:at + stride] = b"\xaa" * stride
        buf[at:at + cap] = name.encode() + bytes(cap - len(name))
        struct.pack_into("<i", buf, at + age_at, age)
        if looks:
            struct.pack_into("<ii", buf, at + looks[0], head, body)
    return buf


class RenameGraves(unittest.TestCase):
    """The graves of renamed dead villagers (Number Duplicate Names, last names for the gone)."""

    def test_each_game_renames_the_grave_matched_by_name_and_age(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                base, _slots, stride, cap, _age_at, looks = ln.GRAVES[game]
                # The Tree of Life and New Believers keep looks on the grave: a namesake of the same
                # age with other looks is someone else.
                buf = grave_buffer(game, {3: ("Bob", 300, 7, 8), 5: ("Bob", 300, 1, 1) if looks else ("Al", 9, 0, 0)})
                before = bytes(buf)
                result = ln.Plan({})
                done = ln._rename_graves(buf, game, {("Bob", 7, 8): "Bob Stone"}, {("Bob", 7, 8): 300}, result)
                at = base + 3 * stride
                self.assertEqual(done, [(3, before[at:at + cap], b"Bob Stone", 300)])
                # NUL-terminated and zero-filled within the field; the bytes past it are untouched.
                self.assertEqual(bytes(buf[at:at + cap]), b"Bob Stone" + bytes(cap - 9))
                self.assertEqual(bytes(buf[at + cap:at + stride]), before[at + cap:at + stride])
                other = base + 5 * stride
                self.assertEqual(bytes(buf[other:other + stride]), before[other:other + stride])
                self.assertEqual(result.notes, [])

    def test_vv4_and_vv5_skip_a_grave_whose_looks_differ(self):
        for game in (4, 5):
            with self.subTest(game=game):
                buf = grave_buffer(game, {0: ("Bob", 300, 1, 1)})
                before = bytes(buf)
                done = ln._rename_graves(buf, game, {("Bob", 7, 8): "Bob Stone"}, {("Bob", 7, 8): 300}, ln.Plan({}))
                self.assertEqual(done, [])
                self.assertEqual(bytes(buf), before)

    def test_a_grave_that_could_be_two_villagers_keeps_its_name(self):
        # The Secret City keeps no looks on a grave: two dead Anns of age 400 cannot be told apart.
        buf = grave_buffer(3, {2: ("Ann", 400, 0, 0)})
        before = bytes(buf)
        result = ln.Plan({})
        ages = {("Ann", 1, 2): 400, ("Ann", 3, 4): 400}
        self.assertEqual(ln._rename_graves(buf, 3, {("Ann", 1, 2): "Ann 1"}, ages, result), [])
        self.assertEqual(bytes(buf), before)
        self.assertEqual(result.notes,
                         ["The grave of Ann (age 400) could be more than one villager's, so it keeps its name."])
        # Two graves of the same name and age are just as unclear.
        buf = grave_buffer(1, {0: ("Ann", 400, 0, 0), 1: ("Ann", 400, 0, 0)})
        before = bytes(buf)
        result = ln.Plan({})
        self.assertEqual(ln._rename_graves(buf, 1, {("Ann", 1, 2): "Ann 1"}, {("Ann", 1, 2): 400}, result), [])
        self.assertEqual(bytes(buf), before)
        self.assertEqual(len(result.notes), 1)

    def test_a_grave_dug_before_last_names_is_found_by_the_first_name(self):
        # An earlier build gave the logs a last name the grave never got: the grave still says "Soda".
        self.assertIn("Akikai", tools.load_checker().LAST_NAMES[1])
        base, _slots, stride, cap, _age_at, _looks = ln.GRAVES[1]
        buf = grave_buffer(1, {4: ("Soda", 30, 0, 0)})
        before = bytes(buf)
        result = ln.Plan({})
        key = ("Soda Akikai", 1, 2)
        done = ln._rename_graves(buf, 1, {key: "Soda Akikai II"}, {key: 30}, result)
        at = base + 4 * stride
        self.assertEqual(done, [(4, before[at:at + cap], b"Soda Akikai II", 30)])
        self.assertEqual(bytes(buf[at:at + cap]), b"Soda Akikai II" + bytes(cap - 14))
        self.assertEqual(result.notes, [])
        # Two dead whose first names are both Poro, of the same age: the grave "Poro" is either.
        buf = grave_buffer(1, {4: ("Poro", 41, 0, 0)})
        before = bytes(buf)
        result = ln.Plan({})
        ages = {("Poro Akikai", 1, 2): 41, ("Poro Wikimak", 3, 4): 41}
        self.assertEqual(ln._rename_graves(buf, 1, {("Poro Akikai", 1, 2): "Poro Akikai II"}, ages, result), [])
        self.assertEqual(bytes(buf), before)
        self.assertEqual(result.notes,
                         ["The grave of Poro Akikai (age 41) could be more than one villager's, so it keeps its name."])

    def test_a_baby_who_died_at_age_0_has_a_grave_too(self):
        buf = grave_buffer(3, {2: ("Baby", 0, 0, 0)})
        done = ln._rename_graves(buf, 3, {("Baby", 1, 2): "Baby II"}, {("Baby", 1, 2): 0}, ln.Plan({}))
        self.assertEqual([(place, new) for place, _old, new, _age in done], [(2, b"Baby II")])

    def test_a_name_too_long_for_the_grave_keeps_the_old_one(self):
        buf = grave_buffer(3, {0: ("Ann", 400, 0, 0)})
        before = bytes(buf)
        result = ln.Plan({})
        long_name = "Ann " + "x" * 21                     # 25 bytes: no room for the NUL in 0x19
        self.assertEqual(ln._rename_graves(buf, 3, {("Ann", 1, 2): long_name}, {("Ann", 1, 2): 400}, result), [])
        self.assertEqual(bytes(buf), before)
        self.assertEqual(result.notes, [f"{long_name} is too long for Ann's grave, which keeps its name."])

    def test_grave_fingerprint_is_cod_fingerprint(self):
        # FNV-1a, worked by hand: "Bob", 0xFF, then 300 as four little-endian bytes.
        self.assertEqual(ln.grave_fingerprint(b"Bob\0junk", 0x1C, 300), 0x024ABD82)
        # The name stops at `cap` when it has no NUL sooner (The Lost Children's 0x18), and a negative
        # age is its two's-complement bytes.
        self.assertEqual(ln.grave_fingerprint(b"Abcdefghijklmnopqrstuvwxyz", 0x18, -5), 0xF980257E)
        from unittest import mock
        with mock.patch.object(ln, "_fnv", return_value=0):
            self.assertEqual(ln.grave_fingerprint(b"Bob", 0x1C, 300), 1, "a fingerprint is never 0")


class GraveFiles(unittest.TestCase):
    """The cause-of-death files that know a grave by its fingerprint follow the new name."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / tools.DATA
        (self.data / "Graves").mkdir(parents=True)
        (self.data / "Deaths").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def vcd1(game: int, entries) -> bytes:
        out = struct.pack("<4sIII", b"VCD1", 1, game, len(entries))
        for kind, index, fp in entries:
            out += struct.pack("<HHIbBBB", kind, index, fp, 2, 5, 1, 0) + b"Rest in peace".ljust(32, b"\0")
        return out

    @staticmethod
    def vcg1(game: int, entries) -> bytes:
        out = struct.pack("<4sIII", b"VCG1", 1, game, len(entries))
        for place, fp in entries:
            out += struct.pack("<HHI", place, 0, fp)
        return out

    def test_the_graves_file_and_graves_logged_move_to_the_new_fingerprint(self):
        game, slot, cap = 1, 2, ln.GRAVE_PRINT_CAP[1]
        old, new = ln.grave_fingerprint(b"Bob", cap, 300), ln.grave_fingerprint(b"Bob Stone", cap, 300)
        other = ln.grave_fingerprint(b"Al", cap, 9)
        graves = self.data / "Graves" / f"Virtual Villagers {game} Graves - Save {slot}.dat"
        logged = self.data / "Deaths" / f"Virtual Villagers {game} Graves Logged - Save {slot}.dat"
        # The grave at place 3; a lying body (kind 1) with the same index and print, the same print at
        # another place, and another print at place 3 are all someone else.
        graves.write_bytes(self.vcd1(game, [(0, 3, old), (1, 3, old), (0, 4, old), (0, 3, other)]))
        logged.write_bytes(self.vcg1(game, [(1, old), (3, old), (4, other)]))
        before = {graves: graves.read_bytes(), logged: logged.read_bytes()}
        result = ln.Plan({})
        ln._plan_grave_files(result, Path(self.tmp.name), game, slot, [(3, b"Bob\0\0", b"Bob Stone", 300)])
        changes = {c.path: c for c in result.changes}
        self.assertEqual(set(changes), {graves, logged})
        self.assertEqual(changes[graves].updated,
                         self.vcd1(game, [(0, 3, new), (1, 3, old), (0, 4, old), (0, 3, other)]))
        self.assertEqual(changes[logged].updated, self.vcg1(game, [(1, old), (3, new), (4, other)]))
        for path, original in before.items():
            self.assertEqual(changes[path].original, original)
            self.assertEqual(path.read_bytes(), original, "planning writes nothing")

    def test_the_loose_graves_file_of_the_lost_children_is_found_too(self):
        game, slot, cap = 2, 1, ln.GRAVE_PRINT_CAP[2]
        old, new = ln.grave_fingerprint(b"Bob", cap, 300), ln.grave_fingerprint(b"Bob Stone", cap, 300)
        loose = self.data / f"Virtual Villagers {game} Graves - Save {slot}.dat"
        loose.write_bytes(self.vcd1(game, [(0, 7, old)]))
        result = ln.Plan({})
        ln._plan_grave_files(result, Path(self.tmp.name), game, slot, [(7, b"Bob", b"Bob Stone", 300)])
        self.assertEqual([(c.path, c.updated) for c in result.changes], [(loose, self.vcd1(game, [(0, 7, new)]))])

    def test_the_later_games_have_only_graves_logged(self):
        game, slot, cap = 3, 1, ln.GRAVE_PRINT_CAP[3]
        old, new = ln.grave_fingerprint(b"Bob", cap, 300), ln.grave_fingerprint(b"Bob Stone", cap, 300)
        # A VCD1 file is A New Home's and The Lost Children's only; one here is left alone.
        stray = self.data / "Graves" / f"Virtual Villagers {game} Graves - Save {slot}.dat"
        stray.write_bytes(self.vcd1(game, [(0, 7, old)]))
        logged = self.data / "Deaths" / f"Virtual Villagers {game} Graves Logged - Save {slot}.dat"
        logged.write_bytes(self.vcg1(game, [(7, old), (8, old)]))
        result = ln.Plan({})
        ln._plan_grave_files(result, Path(self.tmp.name), game, slot, [(7, b"Bob", b"Bob Stone", 300)])
        self.assertEqual([(c.path, c.updated) for c in result.changes],
                         [(logged, self.vcg1(game, [(7, new), (8, old)]))])

    def test_a_file_of_another_game_or_the_wrong_size_is_left_alone(self):
        game, slot, cap = 1, 1, ln.GRAVE_PRINT_CAP[1]
        old = ln.grave_fingerprint(b"Bob", cap, 300)
        logged = self.data / "Deaths" / f"Virtual Villagers {game} Graves Logged - Save {slot}.dat"
        graves = self.data / "Graves" / f"Virtual Villagers {game} Graves - Save {slot}.dat"
        logged.write_bytes(self.vcg1(2, [(3, old)]))                   # says it is The Lost Children's
        graves.write_bytes(self.vcd1(game, [(0, 3, old)]) + b"\0")     # one byte too long
        result = ln.Plan({})
        ln._plan_grave_files(result, Path(self.tmp.name), game, slot, [(3, b"Bob", b"Bob Stone", 300)])
        self.assertEqual(result.changes, [])


if __name__ == "__main__":
    unittest.main()
