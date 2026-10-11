"""Repair Saves & Logs: titles a change of likes or dislikes took away (src/vv_lost_titles.py).

Seen live in The Tree of Life (v1.35.67): the island event "Faces in the Night" gave Alapai new
dislikes, the Story Upgrades companion took the change for a departed villager and dropped her
custom title, and the Island Events log record says "  Custom title: Moon Mother -> none".  New
Believers' Former Heathens file was left with the entry under her old identity.

Each test builds a save folder of one game by hand (in a temporary folder): the villager table where
the game keeps it, the Island Events log, and the patcher's titles / Former Heathens files.
"""
from __future__ import annotations

import importlib.util
import re
import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_lost_titles as lt  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
NOW = datetime(2026, 10, 10, 12, 0, 0)
VILLAGE = "Village: Tribe (Save 1)"
STRIDE = {2: 0x2E0, 3: 0x11C, 4: 0x104, 5: 0x118}
FIRST = 0x2000
EVENT = "Faces in the Night"


class NoGame:
    def find(self, exe_name):
        return []


class Running:
    def find(self, exe_name):
        return [1]


def word(game: int, w: str) -> int:
    return lt.PREFERENCES[game].index(w)


def person(name: str, head: int, body: int, likes=("ants",), dislikes=("bees",), male: bool = False) -> dict:
    return {"name": name, "head": head, "body": body, "likes": likes, "dislikes": dislikes, "male": male}


def _array(game: int, values) -> list[int]:
    f = ln.FIELDS[game]
    out = [v if isinstance(v, int) else word(game, v) for v in values]
    return out + [-1] * (f.slots - len(out))


def save_for(game: int, people: list[dict]) -> bytes:
    """A save the checker and Last Names read as the game loads it: each villager living."""
    checker = tools.load_checker()
    f = ln.FIELDS[game]
    if game == 1:
        data = bytearray(0x184 + 256 * 0x9C)
        for i, p in enumerate(people):
            base = 0x184 + i * 0x9C - 0x33C
            struct.pack_into("<i", data, base + 0x350, 1 if p["male"] else 2)
            struct.pack_into("<i", data, base + 0x348, 500)
            struct.pack_into("<i", data, base + 0x344, 100)
            struct.pack_into("<ii", data, base + 0x360, p["head"], p["body"])
            data[base + 0x3D4] = 1
            at = base + 0x370
            data[at:at + len(p["name"])] = p["name"].encode()
            struct.pack_into(f"<{f.slots}i", data, at + f.likes, *_array(game, p["likes"]))
            struct.pack_into(f"<{f.slots}i", data, at + f.dislikes, *_array(game, p["dislikes"]))
        return bytes(data)
    lay = checker.LAYOUTS[game]
    data = bytearray(FIRST + 150 * STRIDE[game] + 64)
    for i, p in enumerate(people):
        at = FIRST + i * STRIDE[game] + 0x40
        data[at:at + len(p["name"])] = p["name"].encode()
        if game in checker.PRESENT:
            off, width = checker.PRESENT[game]
            data[at + off:at + off + width] = (1).to_bytes(width, "little")
        struct.pack_into("<i", data, at + lay.age, 500)
        struct.pack_into("<i", data, at + lay.head, p["head"])
        struct.pack_into("<i", data, at + lay.body, p["body"])
        struct.pack_into("<i", data, at + f.sex, f.male if p["male"] else (2 if game == 2 else 1))
        struct.pack_into("<i", data, at + checker.HEALTH[game], 100)
        struct.pack_into(f"<{f.slots}i", data, at + f.likes, *_array(game, p["likes"]))
        struct.pack_into(f"<{f.slots}i", data, at + f.dislikes, *_array(game, p["dislikes"]))
    return bytes(data)


def island_event(n: int, name: str, head: int, body: int, likes: str, dislikes: str, changes: str,
                 event: str = EVENT, custom: str | None = None) -> str:
    title = f"  Custom title: {custom}\n" if custom else ""
    return (f"Island event {n}\n  Name: {name}\n{title}  Event: {event}\n  Head: {head}\n  Body: {body}\n"
            f"  Likes: {likes}\n  Dislikes: {dislikes}\n{changes}\n")


def titles_file(game: int, entries: list[tuple]) -> bytes:
    return b"VCT1" + struct.pack("<III", 2, game, len(entries)) + b"".join(
        struct.pack("<II", i, fp) + t.encode().ljust(32, b"\0") for i, fp, t in entries)


def former_file(entries: list[tuple]) -> bytes:
    return b"VFH1" + struct.pack("<III", 1, 5, len(entries)) + b"".join(struct.pack("<II", *e) for e in entries)


class Village:
    """A made-up save folder of one game, slot 1."""

    def __init__(self, case: unittest.TestCase, game: int, people: list[dict], events: str):
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        named = mock.patch("vv_log_additions.current_villages", return_value={VILLAGE})
        named.start()
        case.addCleanup(named.stop)
        self.folder = Path(tmp.name)
        self.game = game
        self.save = ln.save_path(self.folder, game, 1)
        self.save.write_bytes(save_for(game, people))
        self.events = self.log(f"Island Events/Virtual Villagers {game} Island Events Log 1.txt",
                               f"{VILLAGE}\n" + events)
        self.titles = self.folder / DATA / "Custom Titles" / "Custom Titles - Save 1.dat"
        self.former = self.folder / DATA / "Former Heathens" / "Former Heathens - Save 1.dat"

    def log(self, relative: str, text: str) -> Path:
        path = self.folder / LOGS / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
        return path

    def identity(self, k: int) -> int:
        """The title identity of the save's k-th living villager."""
        data = self.save.read_bytes()
        return ln._title_identity(data, ln.living(self.folder, self.game, 1)[k].at, ln.FIELDS[self.game])

    def entries(self) -> list[tuple]:
        data = self.titles.read_bytes()
        count = struct.unpack_from("<I", data, 12)[0]
        return [(*struct.unpack_from("<II", data, 16 + 40 * k), data[24 + 40 * k:56 + 40 * k].rstrip(b"\0").decode())
                for k in range(count)]

    def repairs(self) -> str:
        found = sorted((self.folder / LOGS).rglob("Virtual Villagers * Repairs Log *.txt"))
        return found[0].read_bytes().decode("latin-1") if found else ""


def alapai_events(game: int) -> str:
    """Faces in the Night gave Alapai a second dislike and took her title."""
    return island_event(3, "Alapai", 3, 2, "ants", "bees",
                        "  Dislikes: bees -> bees, the dark\n  Custom title: Moon Mother -> none\n")


ALAPAI = person("Alapai", 3, 2, ("ants",), ("bees", "the dark"))
KAI = person("Kai", 4, 4, ("crowds",), ("caves",), male=True)


class TheWordLists(unittest.TestCase):
    def test_the_word_lists_are_the_ones_the_logs_print(self):
        source = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="latin-1")

        def c_list(name: str) -> tuple:
            m = re.search(rf"static const char {name}\[\] =\s*((?:\"[^\"]*\"\s*)+);", source)
            return tuple("".join(re.findall(r'"([^"]*)"', m.group(1))).split(","))
        self.assertEqual(lt.PREFERENCES[1], c_list("PREFERENCES_47"))
        self.assertEqual(lt.PREFERENCES[2], c_list("PREFERENCES_62"))
        self.assertEqual(lt.PREFERENCES[3], c_list("PREFERENCES_79_VV3"))
        self.assertEqual(lt.PREFERENCES[4], c_list("PREFERENCES_79"))
        self.assertEqual(lt.PREFERENCES[5], c_list("PREFERENCES_79"))

    def test_list_text_is_every_filled_slot(self):
        self.assertEqual(lt.list_text(5, [1, -1, 9]), "crowds, the dark")
        self.assertEqual(lt.list_text(5, [-1, -1, 500]), "(none)")
        self.assertEqual(lt.list_text(5, [-1, 9, 1]), "the dark, crowds")

    def test_a_long_list_stops_where_the_companions_buffer_does(self):
        """VillagePreferenceListText into the Island Events companion's char[512]: a word is kept when
        used + ", " + word + NUL still fits (parentage_export.c preference_list_text)."""
        import random
        rng = random.Random(1)
        words = lt.PREFERENCES[2]

        def c_text(values):
            out = ""
            for v in values:
                if 0 <= v < len(words):
                    if len(out) + (2 if out else 0) + len(words[v]) + 1 > 512:
                        break
                    out += (", " if out else "") + words[v]
            return out or "(none)"
        for _ in range(3000):
            values = [rng.randrange(-1, 62) for _ in range(62)]
            self.assertEqual(lt.list_text(2, values), c_text(values), values)

    def test_undo_a_change(self):
        self.assertEqual(lt.undo(5, [8, 9, -1], "bees", "bees, the dark"), [(8, -1, -1)])
        self.assertEqual(lt.undo(5, [8, -1, -1], "bees", "bees, the dark"), None)      # changed again since
        self.assertEqual(sorted(lt.undo(5, [8, 8, -1], "bees", "bees, bees")), [(-1, 8, -1), (8, -1, -1)])
        self.assertEqual(lt.undo(5, [8, -1, -1], "(changed)", "bees"), None)


class TheAlapaiCase(unittest.TestCase):
    """All five games: the title comes back under the identity she has now."""

    def test_the_title_comes_back_with_her_identity_now(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                v = Village(self, game, [ALAPAI, KAI], alapai_events(game))
                found = lt.survey(v.folder, game, 1)
                self.assertEqual([r.title for r in found.certain], ["Moon Mother"], found.notes)
                self.assertEqual(found.questions, [])
                save = v.save.read_bytes()
                result = lt.restore(v.folder, game, 1, processes=NoGame(), now=NOW)
                self.assertEqual(v.save.read_bytes(), save)                 # the save is never written
                self.assertEqual(v.entries(), [(0, v.identity(0), "Moon Mother")])
                self.assertEqual(v.titles.read_bytes()[:16], b"VCT1" + struct.pack("<III", 2, game, 1))
                # The patcher's own reader now gives it to her.
                import vv_villager_info as info
                self.assertEqual(info.file_titles(v.folder, game, 1)[("Alapai", 3, 2)], "Moon Mother")
                # Backed up first, and one Repair record.
                backup = Path(result.backup.backup_folder)
                self.assertIn(lt.BACKUP_LABEL, backup.name)
                self.assertTrue((backup / v.save.name).is_file())
                self.assertFalse((backup / DATA / "Custom Titles").exists())       # it was not there yet
                text = v.repairs()
                self.assertIn(f"{VILLAGE}\r\nRepair 1\r\n  Date: 2026-10-10 12:00:00\r\n", text)
                self.assertIn('  Restored: Alapai (head 3, body 2): Custom title "Moon Mother" (lost in Island '
                              f'event 3 ({EVENT}))', text)
                self.assertIn(f"  Backup: {backup.name}", text)
                # Done once: nothing is found again.
                self.assertFalse(lt.survey(v.folder, game, 1).found)

    def test_other_titles_stay_byte_for_byte(self):
        for game in (1, 4):
            with self.subTest(game=game):
                v = Village(self, game, [ALAPAI, KAI], alapai_events(game))
                v.titles.parent.mkdir(parents=True)
                original = titles_file(game, [(1, v.identity(1), "Chief Cook")])
                v.titles.write_bytes(original)
                lt.restore(v.folder, game, 1, processes=NoGame(), now=NOW)
                data = v.titles.read_bytes()
                self.assertEqual(data[16:56], original[16:56])
                self.assertEqual(v.entries()[1], (0, v.identity(0), "Moon Mother"))
                copy = v.folder / DATA / "Copies Made Before Repairs" / DATA / "Custom Titles" / (
                    "Custom Titles - Save 1.dat" + lt.COPY_SUFFIX)
                self.assertEqual(copy.read_bytes(), original)

    def test_the_repair_number_follows_every_repairs_file_of_the_game(self):
        # "Repair <n>" is numbered per GAME and written in the village's own slot folder
        # (src/vv_log_tools.py repair_record_start), as every other repair does.
        v = Village(self, 4, [ALAPAI, KAI], alapai_events(4))
        v.log("Save 1/Repairs Made/Virtual Villagers 4 Repairs Log 1.txt",
              f"{VILLAGE}\nRepair 1\n  Date: x\n\nRepair 2\n  Date: x\n\nRepair 3\n  Date: x\n\n")
        lt.restore(v.folder, 4, 1, processes=NoGame(), now=NOW)
        written = v.folder / LOGS / "Save 1" / "Repairs Made" / "Virtual Villagers 4 Repairs Log 1.txt"
        text = written.read_bytes().decode("latin-1")
        self.assertIn("Repair 4\r\n  Date: 2026-10-10 12:00:00\r\n", text)
        self.assertNotIn("Repair 1\r\n  Date: 2026-10-10", v.repairs())
        self.assertFalse((v.folder / LOGS / "Repairs Made").exists(), "not in the shared folder")

    def test_refused_while_the_game_runs(self):
        v = Village(self, 4, [ALAPAI, KAI], alapai_events(4))
        with self.assertRaises(tools.GameRunning):
            lt.restore(v.folder, 4, 1, processes=Running(), now=NOW)
        self.assertFalse(v.titles.exists())
        self.assertFalse((v.folder / "Backups").exists())


class WhatIsLeftAlone(unittest.TestCase):
    def test_a_later_retitle_or_removal_is_not_undone(self):
        for later in ("  Custom title: none -> Sun Child\n", "  Custom title: Moon Mother -> none\n"):
            with self.subTest(later=later):
                events = alapai_events(4) + island_event(9, "Alapai", 3, 2, "ants", "bees", later, "Story")
                v = Village(self, 4, [ALAPAI, KAI], events)
                found = lt.survey(v.folder, 4, 1)
                self.assertFalse(found.certain or found.questions)
                self.assertTrue(any("changed again" in n for n in found.notes), found.notes)

    def test_a_title_the_file_already_gives_her_is_kept(self):
        v = Village(self, 4, [ALAPAI, KAI], alapai_events(4))
        v.titles.parent.mkdir(parents=True)
        original = titles_file(4, [(0, v.identity(0), "Sun Child")])
        v.titles.write_bytes(original)
        found = lt.survey(v.folder, 4, 1)
        self.assertFalse(found.found)
        with self.assertRaises(lt.LostTitlesError):
            lt.restore(v.folder, 4, 1, processes=NoGame(), now=NOW)
        self.assertEqual(v.titles.read_bytes(), original)

    def test_a_departed_villager_or_an_event_that_took_them_is_not_restored(self):
        v = Village(self, 3, [KAI], alapai_events(3))
        found = lt.survey(v.folder, 3, 1)
        self.assertFalse(found.found)
        self.assertTrue(any("no living villager" in n for n in found.notes))
        gone = island_event(3, "Alapai", 3, 2, "ants", "bees",
                            "  Gone: yes\n  Dislikes: bees -> bees, the dark\n  Custom title: Moon Mother -> none\n")
        v = Village(self, 3, [ALAPAI, KAI], gone)
        self.assertFalse(lt.survey(v.folder, 3, 1).found)

    def test_a_title_removed_without_a_likes_change_is_not_the_bug(self):
        v = Village(self, 2, [ALAPAI, KAI], island_event(3, "Alapai", 3, 2, "ants", "bees",
                                                         "  Custom title: Moon Mother -> none\n"))
        self.assertFalse(lt.survey(v.folder, 2, 1).found)


class WhatIsAsked(unittest.TestCase):
    def test_two_look_alikes_are_asked_about_and_nothing_is_written(self):
        twin = person("Alapai", 3, 2, ("crowds",), ("bees", "the dark"))
        v = Village(self, 4, [ALAPAI, twin, KAI], alapai_events(4))
        found = lt.survey(v.folder, 4, 1)
        self.assertEqual(found.certain, [])
        self.assertEqual(len(found.questions), 2)
        self.assertIn("Was Alapai (head 3, body 2; likes ants; dislikes bees, the dark) the villager the Island "
                      f"Events log says lost the title \"Moon Mother\" in Island event 3 ({EVENT})? Restore it?",
                      found.questions[0].question)
        with self.assertRaises(lt.LostTitlesError):
            lt.restore(v.folder, 4, 1, processes=NoGame(), now=NOW)
        self.assertFalse(v.titles.exists())
        self.assertFalse((v.folder / "Backups").exists())
        # One title is never given to two villagers, even if both are answered yes.
        lt.restore(v.folder, 4, 1, {found.questions[1].key, found.questions[0].key}, NoGame(), NOW)
        self.assertEqual([e[2] for e in v.entries()], ["Moon Mother"])
        self.assertEqual(len(v.entries()), 1)

    def test_likes_changed_again_since_is_asked(self):
        since = person("Alapai", 3, 2, ("ants",), ("bees", "caves"))
        v = Village(self, 5, [since, KAI], alapai_events(5))
        found = lt.survey(v.folder, 5, 1)
        self.assertEqual(found.certain, [])
        self.assertEqual(len(found.questions), 1)
        self.assertIn("changed again since", found.questions[0].question)

    def test_new_looks_are_asked(self):
        relooked = person("Alapai", 7, 2, ("ants",), ("bees", "the dark"))
        v = Village(self, 1, [relooked, KAI], alapai_events(1))
        found = lt.survey(v.folder, 1, 1)
        self.assertEqual(found.certain, [])
        self.assertEqual(len(found.questions), 1)
        self.assertIn("the record names head 3, body 2", found.questions[0].question)
        lt.restore(v.folder, 1, 1, {found.questions[0].key}, NoGame(), NOW)
        self.assertEqual(v.entries(), [(0, v.identity(0), "Moon Mother")])


class FormerHeathens(unittest.TestCase):
    """New Believers: the former-Heathen entry left under her old identity follows her."""

    def old_identity(self, v: Village, dislikes) -> int:
        f = ln.FIELDS[5]
        data = bytearray(v.save.read_bytes())
        at = ln.living(v.folder, 5, 1)[0].at
        struct.pack_into(f"<{f.slots}i", data, at + f.dislikes, *_array(5, dislikes))
        return ln._title_identity(data, at, f)

    def test_the_entry_is_rekeyed(self):
        v = Village(self, 5, [ALAPAI, KAI], alapai_events(5))
        old = self.old_identity(v, ("bees",))
        v.former.parent.mkdir(parents=True)
        original = former_file([(0x1234, 0), (old, 2)])
        v.former.write_bytes(original)
        found = lt.survey(v.folder, 5, 1)
        self.assertEqual(sorted(r.kind for r in found.certain), ["former", "title"], found.notes)
        lt.restore(v.folder, 5, 1, processes=NoGame(), now=NOW)
        data = v.former.read_bytes()
        self.assertEqual(data[:24], original[:24])                       # the header and the other entry
        self.assertEqual(struct.unpack_from("<II", data, 24), (v.identity(0), 2))
        self.assertEqual(len(data), len(original))
        self.assertIn("Former Heathen mark (red mask)", v.repairs())

    def test_an_ambiguous_rebuild_is_asked(self):
        doubled = person("Alapai", 3, 2, ("ants",), ("bees", "bees"))
        events = island_event(3, "Alapai", 3, 2, "ants", "bees", "  Dislikes: bees -> bees, bees\n")
        v = Village(self, 5, [doubled, KAI], events)
        old = self.old_identity(v, ("bees",))                            # one of the two rebuilds
        v.former.parent.mkdir(parents=True)
        original = former_file([(old, 1)])
        v.former.write_bytes(original)
        found = lt.survey(v.folder, 5, 1)
        self.assertEqual(found.certain, [])
        self.assertEqual(len(found.questions), 1)
        self.assertIn("Was it theirs?", found.questions[0].question)
        with self.assertRaises(lt.LostTitlesError):
            lt.restore(v.folder, 5, 1, processes=NoGame(), now=NOW)
        self.assertEqual(v.former.read_bytes(), original)
        lt.restore(v.folder, 5, 1, {found.questions[0].key}, NoGame(), NOW)
        self.assertEqual(struct.unpack_from("<II", v.former.read_bytes(), 16), (v.identity(0), 1))

    def test_a_change_that_cannot_be_undone_is_said(self):
        events = island_event(3, "Alapai", 3, 2, "ants", "bees", "  Dislikes: crowds -> caves\n")
        v = Village(self, 5, [ALAPAI, KAI], events)
        v.former.parent.mkdir(parents=True)
        v.former.write_bytes(former_file([(0x1234, 0)]))
        found = lt.survey(v.folder, 5, 1)
        self.assertFalse(found.found)
        self.assertTrue(any("could not be rebuilt" in n for n in found.notes), found.notes)


class TheRepairWindow(unittest.TestCase):
    """Repair Saves & Logs surveys it and asks before restoring (src/vv_fun_patcher_gui.py)."""
    SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def body(self, start: str, end: str) -> str:
        return self.SOURCE[self.SOURCE.index(start):self.SOURCE.index(end, self.SOURCE.index(start))]

    def test_surveyed_with_the_rest_and_restored_before_any_rename(self):
        repair = self.body("    def _repair_logs(", "    def _repair_checklist(")
        self.assertIn("lost = vv_lost_titles.survey(folder, number, info.slot)", repair)
        self.assertIn("graves, lost) = self._run_with_wait(", repair)
        self.assertLess(repair.index("self._restore_lost_titles("), repair.index("vv_cut_names.restore("))
        self.assertLess(repair.index("vv_log_tools.approve_repair("), repair.index("self._restore_lost_titles("))

    def test_each_doubt_is_asked_and_the_certain_ones_listed_first(self):
        method = self.body("    def _restore_lost_titles(", "    def _close(")
        self.assertIn("messagebox.askyesno(\"Repair Saves & Logs\", question.question, parent=parent)", method)
        self.assertLess(method.index("lost.certain"), method.index("for question in lost.questions"))
        self.assertIn("vv_lost_titles.restore(folder, number, info.slot, chosen)", method)


if __name__ == "__main__":
    unittest.main()
