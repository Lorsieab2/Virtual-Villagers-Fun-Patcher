"""Repair Saves & Logs' "Fix grave information" (src/vv_graves.py), all five games.

The owner (2026-10-10): "add an option in Repair logs/saves to fix grave information too: Name, age,
etc." and "account for mod-added stuff too".  Each test builds a save whose graves table sits where
the game keeps it, a Deaths log, and the patcher's grave files, by hand.
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

import vv_graves as vg  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_log_decisions  # noqa: E402
import vv_log_tools as tools  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
NOW = datetime(2026, 10, 10, 12, 0, 0)


class NoGame:
    def find(self, exe_name):
        return []


class Running:
    def find(self, exe_name):
        return [1]


def grave_bytes(game: int, name: str, age: int, job: int | None = None, value: int = 100, epitaph: str = "",
                cause: int = 2, head: int = 3, body: int = 4, male: bool = True, elder: bool = False,
                chief: bool = False) -> bytes:
    lay = vg.LAYOUTS[game]
    job = (1 if game <= 2 else 0) if job is None else job      # a Farmer in every game
    e = bytearray(lay.stride)
    e[:len(name)] = name.encode("latin-1")
    struct.pack_into("<i", e, lay.age, age)
    struct.pack_into("<i", e, lay.job, job)
    struct.pack_into("<i", e, lay.value, value)
    if lay.epitaph:
        e[lay.epitaph[0]:lay.epitaph[0] + len(epitaph)] = epitaph.encode("latin-1")
    if lay.cause is not None:
        struct.pack_into("<i", e, lay.cause, cause)
    if lay.head is not None:
        struct.pack_into("<ii", e, lay.head, head, body)
        e[lay.male] = int(male)
        e[lay.child] = int(age < 280)
    if lay.elder is not None:
        e[lay.elder] = int(elder)
    if lay.chief is not None:
        e[lay.chief] = int(chief)
    return bytes(e)


def death(n: int, name: str, age: int, cause: str = "Old age", grave: str = "Master Farmer",
          epitaph: str = "Inspired Architect", head: int = 3, body: int = 4, sex: str = "Male",
          extra: str = "") -> str:
    return (f"Death {n}\n  Name: {name}\n{extra}  Age at death: {age}\n  Sex: {sex}\n  Cause of death: {cause}\n"
            f"  Grave: {grave}\n  Epitaph: {epitaph or '(none)'}\n  Head: {head}\n  Body: {body}\n"
            "  Likes: (none)\n  Dislikes: (none)\n\n")


class Village:
    """A made-up save folder of one game: graves in the save, a Deaths log, and the patcher's files."""

    def __init__(self, game: int, graves: list[bytes], deaths: str, stones: list[tuple] = ()):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.game = game
        lay = vg.LAYOUTS[game]
        save = bytearray(lay.base + lay.places * lay.stride + 0x100)
        if game == 3:
            base, count, stride, off, _cap = vg.VV3_STONES
            for k in range(count):
                struct.pack_into("<i", save, base + k * stride, -1)
            for k, (place, text) in enumerate(stones):
                struct.pack_into("<ii", save, base + k * stride, place, 100)
                save[base + k * stride + off:base + k * stride + off + len(text)] = text.encode()
        for place, g in enumerate(graves):
            save[lay.base + place * lay.stride:lay.base + (place + 1) * lay.stride] = g
        self.save = ln.save_path(self.folder, game, 1)
        self.save.write_bytes(bytes(save))
        self.deaths = self.log(f"Deaths/Virtual Villagers {game} Deaths Log 1.txt",
                               "Village: Tribe (Save 1)\n" + deaths)

    def log(self, relative: str, text: str) -> Path:
        path = self.folder / LOGS / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
        return path

    def text(self, path: Path) -> str:
        return path.read_bytes().decode("latin-1").replace("\r\n", "\n")

    def close(self):
        self.tmp.cleanup()


def fingerprint(game: int, name: str, age: int) -> int:
    return ln.grave_fingerprint(name.encode("latin-1"), ln.GRAVE_PRINT_CAP[game], age)


def vcd1(game: int, entries: list[tuple]) -> bytes:
    out = struct.pack("<4sIII", b"VCD1", 1, game, len(entries))
    for place, fp, cause, epitaph, custom, text in entries:
        out += struct.pack("<HHIbBBB", 0, place, fp, cause, epitaph, custom, 0) + text.encode().ljust(32, b"\0")
    return out


def vcg1(game: int, entries: list[tuple]) -> bytes:
    return struct.pack("<4I", 0x31474356, 1, game, len(entries)) + b"".join(
        struct.pack("<HHI", place, 0, fp) for place, fp in entries)


class WhatEachGameKeeps(unittest.TestCase):
    """The per-game field table (from each game's burial writer and grave loader)."""

    def test_the_layouts(self):
        self.assertEqual(vg.LAYOUTS[1].base, ln.GRAVES[1][0])
        for game in range(1, 6):
            self.assertEqual((vg.LAYOUTS[game].base, vg.LAYOUTS[game].places, vg.LAYOUTS[game].stride),
                             ln.GRAVES[game][:3])
        self.assertIn("head", vg.editable(4))
        self.assertNotIn("head", vg.editable(3))
        self.assertIn("title", vg.editable(3))
        self.assertNotIn("title", vg.editable(1))

    def test_the_skill_line_is_the_games(self):
        self.assertEqual(vg.grave_line(1, 4, 95, 1000), "Master Builder")
        self.assertEqual(vg.grave_line(1, 4, 95, 200), "Apprentice Builder")
        self.assertEqual(vg.grave_line(2, 3, 60, 1000), "Adept Doctor")
        self.assertEqual(vg.grave_line(3, 0, 10, 1000), "Untrained")
        self.assertEqual(vg.grave_line(3, 0, 100, 200), "Master Farmer", "The Secret City has no apprentices")
        self.assertEqual(vg.grave_line(4, 1, 30, 200), "Apprentice Parent")
        self.assertEqual(vg.grave_line(5, 5, 100, 1000), "Master Devotee")
        self.assertEqual(vg.grave_line(4, 5, 100, 1000), "Untrained", "no Devotee before New Believers")

    def test_values_the_game_cannot_keep_are_refused(self):
        for game in range(1, 6):
            with self.assertRaises(vg.GraveError):
                vg.check_value(game, "age", 0)            # every burial reuses an age-0 grave
            with self.assertRaises(vg.GraveError):
                vg.check_value(game, "name", "x" * (ln.ROOM[game] + 1))
            with self.assertRaises(vg.GraveError):
                vg.check_value(game, "cause", "Boredom")
            with self.assertRaises(vg.GraveError):
                vg.check_value(game, "epitaph", "y" * (vg.EPITAPH_ROOM[game] + 1))
        self.assertEqual(vg.check_value(2, "epitaph", "z" * 64), "z" * 64)
        with self.assertRaises(vg.GraveError):
            vg.check_value(4, "head", 9, seen={"head": {0, 5}})
        self.assertEqual(vg.check_value(4, "head", 0, seen={"head": {5}}), 0, "head 0 is a real head")
        with self.assertRaises(vg.GraveError):
            vg.check_value(4, "title", "Tribal Chief")      # only The Secret City's grave keeps a chief


class EveryGameFindsAndFixesDifferences(unittest.TestCase):
    def village(self, game, graves, deaths, **kw):
        v = Village(game, graves, deaths, **kw)
        self.addCleanup(v.close)
        return v

    def test_a_matching_grave_has_no_difference(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                job = 1 if game <= 2 else 0
                epitaph = "Inspired Architect" if game in (2, 4, 5) else ""
                v = self.village(game, [grave_bytes(game, "Mia", 1000, job=job, epitaph=epitaph)],
                                 death(1, "Mia", 1000, epitaph=epitaph if game != 3 else "Inspired Architect"),
                                 stones=[(0, "Inspired Architect")] if game == 3 else ())
                found = vg.survey(v.folder, game, 1)
                self.assertEqual(len(found.graves), 1)
                self.assertEqual(found.differences, [], [d.text for d in found.differences])

    def test_name_and_age_differences_are_listed_in_plain_words(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                job = 1 if game <= 2 else 0
                v = self.village(game, [grave_bytes(game, "Mia", 1000, job=job), grave_bytes(game, "Rex", 900, job=job)],
                                 death(1, "Mia Akikai", 1000, epitaph="") + death(2, "Rex", 905, epitaph=""))
                found = vg.survey(v.folder, game, 1)
                fields = {(d.place, d.field) for d in found.differences}
                self.assertIn((0, "name"), fields)
                self.assertIn((1, "age"), fields)
                text = next(d.text for d in found.differences if d.field == "name")
                self.assertIn("the grave says Mia", text)
                self.assertIn("the Death record says Mia Akikai", text)
                self.assertEqual(next(d for d in found.differences if d.field == "name").choices,
                                 ["Mia", "Mia Akikai"])

    def test_choosing_the_record_fixes_the_save_and_the_grave_files_follow(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                job = 1 if game <= 2 else 0
                v = self.village(game, [grave_bytes(game, "Mia", 1000, job=job)],
                                 death(1, "Mia Akikai", 1000, epitaph=""))
                logged = v.folder / DATA / "Deaths" / f"Virtual Villagers {game} Graves Logged - Save 1.dat"
                logged.parent.mkdir(parents=True)
                logged.write_bytes(vcg1(game, [(0, fingerprint(game, "Mia", 1000))]))
                before = v.save.read_bytes()
                result = vg.fix_graves(v.folder, game, 1, [vg.Fix(0, "name", "Mia Akikai")], retro=True,
                                       processes=NoGame(), now=NOW)
                self.assertEqual(vg.read_graves(game, v.save.read_bytes())[0].name, "Mia Akikai")
                self.assertEqual(vg.survey(v.folder, game, 1).differences, [])
                self.assertEqual(struct.unpack_from("<I", logged.read_bytes(), 20)[0],
                                 fingerprint(game, "Mia Akikai", 1000), "Graves Logged follows the new name")
                copies = list((v.folder / DATA / "Copies Made Before Repairs").rglob("*.before-grave-repair"))
                self.assertTrue(any(c.read_bytes() == before for c in copies), "a copy of the save before")
                self.assertTrue(result.backup.backup_folder.is_dir())
                repairs = list((v.folder / LOGS / "Repairs Made").glob("*.txt"))
                self.assertTrue(repairs)
                self.assertIn("Village: Tribe (Save 1)", repairs[0].read_bytes().decode("latin-1"))
                self.assertIn("Grave information corrected", repairs[0].read_bytes().decode("latin-1"))
                self.assertIn("Name Mia -> Mia Akikai", repairs[0].read_bytes().decode("latin-1"))

    def test_choosing_the_grave_fixes_the_record_when_retroactive(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                job = 1 if game <= 2 else 0
                v = self.village(game, [grave_bytes(game, "Rex", 900, job=job)], death(1, "Rex", 905, epitaph=""))
                vg.fix_graves(v.folder, game, 1, [vg.Fix(0, "age", 900)], retro=True, processes=NoGame(), now=NOW)
                self.assertIn("  Age at death: 900\n", v.text(v.deaths))
                self.assertNotIn("905", v.text(v.deaths))
                self.assertIn("\r\n", v.deaths.read_bytes().decode("latin-1"), "line endings kept")

    def test_no_leaves_every_record_and_is_not_asked_again(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                job = 1 if game <= 2 else 0
                v = self.village(game, [grave_bytes(game, "Rex", 900, job=job)], death(1, "Rex", 905, epitaph=""))
                before = v.deaths.read_bytes()
                vg.fix_graves(v.folder, game, 1, [vg.Fix(0, "age", 900)], retro=False, processes=NoGame(), now=NOW)
                self.assertEqual(v.deaths.read_bytes(), before, "the record left as it is")
                self.assertTrue(vv_log_decisions.load(v.folder, game, 1))
                found = vg.survey(v.folder, game, 1)
                self.assertEqual([d for d in found.differences if d.field == "age"], [])
                self.assertTrue(any("as you chose to leave the records" in n for n in found.notes))

    def test_refused_while_the_game_runs(self):
        v = self.village(4, [grave_bytes(4, "Rex", 900)], death(1, "Rex", 905, epitaph=""))
        before = v.save.read_bytes()
        with self.assertRaises(tools.LogToolError):
            vg.fix_graves(v.folder, 4, 1, [vg.Fix(0, "age", 900)], retro=True, processes=Running(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)
        self.assertFalse((v.folder / "Backups").exists())

    def test_a_failure_puts_every_file_back(self):
        v = self.village(4, [grave_bytes(4, "Rex", 900)], death(1, "Rex", 905, epitaph=""))
        save_before, log_before = v.save.read_bytes(), v.deaths.read_bytes()
        real = ln._write
        calls = []

        def failing(path, data):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("disk full")
            real(path, data)
        ln._write = failing
        try:
            with self.assertRaises(vg.GraveError) as caught:
                vg.fix_graves(v.folder, 4, 1, [vg.Fix(0, "name", "Rexy")], retro=True, processes=NoGame(), now=NOW)
        finally:
            ln._write = real
        self.assertIn("every file was put back", str(caught.exception))
        self.assertEqual(v.save.read_bytes(), save_before)
        self.assertEqual(v.deaths.read_bytes(), log_before)


class ModAddedData(unittest.TestCase):
    def village(self, game, graves, deaths, **kw):
        v = Village(game, graves, deaths, **kw)
        self.addCleanup(v.close)
        return v

    def test_a_new_home_cause_and_epitaph_live_in_the_graves_file(self):
        v = self.village(1, [grave_bytes(1, "Mia", 1000)], death(1, "Mia", 1000, cause="Disease",
                                                                  epitaph="Child of the Earth"))
        graves = v.folder / DATA / "Graves" / "Virtual Villagers 1 Graves - Save 1.dat"
        graves.parent.mkdir(parents=True)
        graves.write_bytes(vcd1(1, [(0, fingerprint(1, "Mia", 1000), 2, 3, 0, "")]))   # Old age, Nature's Friend
        found = vg.survey(v.folder, 1, 1)
        fields = {d.field: d for d in found.differences}
        self.assertEqual(set(fields), {"cause", "epitaph"})
        self.assertIn("the patcher's Graves file says Old age", fields["cause"].text)
        vg.fix_graves(v.folder, 1, 1, [vg.Fix(0, "cause", "Disease"), vg.Fix(0, "epitaph", "Rest well")],
                      retro=True, processes=NoGame(), now=NOW)
        entry = graves.read_bytes()[16:60]
        self.assertEqual(struct.unpack_from("<b", entry, 8)[0], 0, "Disease")
        self.assertEqual((entry[9], entry[10]), (0, 1))
        self.assertEqual(entry[12:21], b"Rest well")
        self.assertIn("  Epitaph: Rest well\n", v.text(v.deaths))

    def test_a_grave_with_no_graves_file_entry_gets_one(self):
        v = self.village(2, [grave_bytes(2, "Mia", 1000)], death(1, "Mia", 1000, epitaph=""))
        vg.fix_graves(v.folder, 2, 1, [vg.Fix(0, "cause", "Starvation")], retro=False, processes=NoGame(), now=NOW)
        graves = v.folder / DATA / "Graves" / "Virtual Villagers 2 Graves - Save 1.dat"
        data = graves.read_bytes()
        self.assertEqual(struct.unpack_from("<4sIII", data, 0), (b"VCD1", 1, 2, 1))
        self.assertEqual(struct.unpack_from("<HHIb", data, 16), (0, 0, fingerprint(2, "Mia", 1000), 1))

    def test_a_rename_rekeys_the_graves_file(self):
        v = self.village(2, [grave_bytes(2, "Mia", 1000)], death(1, "Mia Akikai", 1000, epitaph=""))
        graves = v.folder / DATA / "Graves" / "Virtual Villagers 2 Graves - Save 1.dat"
        graves.parent.mkdir(parents=True)
        graves.write_bytes(vcd1(2, [(0, fingerprint(2, "Mia", 1000), 2, 0, 0, "")]))
        vg.fix_graves(v.folder, 2, 1, [vg.Fix(0, "name", "Mia Akikai")], retro=True, processes=NoGame(), now=NOW)
        self.assertEqual(struct.unpack_from("<I", graves.read_bytes(), 20)[0], fingerprint(2, "Mia Akikai", 1000))
        self.assertEqual(vg.survey(v.folder, 2, 1).graves[0].sidecar.get("cause"), "Old age")

    def test_the_newest_epitaph_changed_record_is_the_one_compared(self):
        v = self.village(4, [grave_bytes(4, "Mia", 1000, epitaph="Rest well")],
                         death(1, "Mia", 1000, grave="Master Farmer", epitaph="Child of the Earth"))
        v.log("Deaths/Virtual Villagers 4 Deaths Log 2.txt",
              "Village: Tribe (Save 1)\nEpitaph changed\n  Name: Mia\n  Age at death: 1000\n  Grave: Master Farmer\n"
              "  Old epitaph: Child of the Earth\n  New epitaph: Rest well\n\n")
        self.assertEqual(vg.survey(v.folder, 4, 1).differences, [])
        vg.fix_graves(v.folder, 4, 1, [vg.Fix(0, "epitaph", "Sleep well")], retro=True, processes=NoGame(), now=NOW)
        second = v.text(v.folder / LOGS / "Deaths" / "Virtual Villagers 4 Deaths Log 2.txt")
        self.assertIn("  New epitaph: Sleep well\n", second)
        self.assertIn("  Epitaph: Child of the Earth\n", v.text(v.deaths), "the Death record keeps the first one")

    def test_special_titles_against_the_grave(self):
        v = self.village(3, [grave_bytes(3, "Hope", 1400, job=0, elder=True), grave_bytes(3, "Chief", 1400, job=0, chief=True)],
                         death(1, "Hope", 1400, grave="Master Farmer", epitaph="")
                         + death(2, "Chief", 1400, grave="Master Farmer", epitaph="",
                                 extra="  Special villager: Tribal Chief\n"))
        found = vg.survey(v.folder, 3, 1)
        self.assertEqual([(d.place, d.field) for d in found.differences], [(0, "title")])
        vg.fix_graves(v.folder, 3, 1, [vg.Fix(0, "title", "Esteemed Elder")], retro=True, processes=NoGame(), now=NOW)
        self.assertIn("Death 1\n  Name: Hope\n  Special villager: Esteemed Elder\n", v.text(v.deaths))

    def test_a_later_games_chief_is_not_a_difference(self):
        # The Tree of Life and New Believers keep no chief on the grave; an elder Chief's record names
        # only the higher title.
        for game in (4, 5):
            v = self.village(game, [grave_bytes(game, "Chief", 1400), grave_bytes(game, "Old", 1400, elder=True)],
                             death(1, "Chief", 1400, grave="Master Farmer", epitaph="",
                                   extra="  Special villager: Tribal Chief\n")
                             + death(2, "Old", 1400, grave="Master Farmer", epitaph="",
                                     extra="  Special villager: Tribal Chief\n"))
            self.assertEqual(vg.survey(v.folder, game, 1).differences, [])

    def test_custom_title_and_mask_against_the_last_snapshot(self):
        v = self.village(5, [grave_bytes(5, "Mia", 1000)],
                         death(1, "Mia", 1000, grave="Master Farmer", epitaph="",
                               extra="  Custom title: Seer\n  Mask: Red Mask\n"))
        v.log("Tribe History/Virtual Villagers 5 Village History 1.txt",
              "=== Virtual Villagers 5 -- 2026-10-01 ===\nVillage: Tribe (Save 1)\nVillager 1\n  Name: Mia\n"
              "  Custom title: Oracle\n  Mask: Red Mask\n  Age: 990\n  Head: 3\n  Body: 4\n\n")
        found = vg.survey(v.folder, 5, 1)
        self.assertEqual([d.field for d in found.differences], ["custom"])
        self.assertEqual(found.differences[0].choices, ["Seer", "Oracle"])
        vg.fix_graves(v.folder, 5, 1, [vg.Fix(0, "custom", "Oracle")], retro=True, processes=NoGame(), now=NOW)
        self.assertIn("  Custom title: Oracle\n", v.text(v.deaths))

    def test_looks_and_sex_on_the_later_graves(self):
        v = self.village(4, [grave_bytes(4, "Mia", 1000, head=5, body=6, male=False)],
                         death(1, "Mia", 1000, epitaph="", head=5, body=7, sex="Male"))
        found = vg.survey(v.folder, 4, 1)
        self.assertEqual({d.field for d in found.differences}, {"body", "sex"})
        vg.fix_graves(v.folder, 4, 1, [vg.Fix(0, "sex", "Male"), vg.Fix(0, "body", 7)], retro=False,
                      processes=NoGame(), now=NOW)
        g = vg.read_graves(4, v.save.read_bytes())[0]
        self.assertEqual((g.values["sex"], g.values["body"]), ("Male", 7))

    def test_the_last_names_record_is_compared(self):
        v = self.village(4, [grave_bytes(4, "Mia", 1000)], death(1, "Mia", 1000, epitaph=""))
        ln.write_record(v.folder, 4, 1, "father", {("Mia", 3, 4): "Akikai"})
        found = vg.survey(v.folder, 4, 1)
        names = [d for d in found.differences if d.field == "name"]
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0].choices, ["Mia", "Mia Akikai"])

    def test_the_job_line_can_only_follow_the_grave(self):
        v = self.village(4, [grave_bytes(4, "Mia", 1000, job=0)], death(1, "Mia", 1000, grave="Master Builder",
                                                                         epitaph=""))
        diff = vg.survey(v.folder, 4, 1).differences[0]
        self.assertEqual((diff.field, diff.choices), ("grave", ["Master Farmer"]))
        with self.assertRaises(vg.GraveError):
            vg.fix_graves(v.folder, 4, 1, [vg.Fix(0, "grave", "Master Builder")], retro=True,
                          processes=NoGame(), now=NOW)
        vg.fix_graves(v.folder, 4, 1, [vg.Fix(0, "grave", "Master Farmer")], retro=True, processes=NoGame(), now=NOW)
        self.assertIn("  Grave: Master Farmer\n", v.text(v.deaths))


class TheGamesOwnRules(unittest.TestCase):
    def test_the_later_games_end_the_list_at_age_0(self):
        v = Village(4, [grave_bytes(4, "Mia", 1000), bytes(vg.LAYOUTS[4].stride), grave_bytes(4, "Rex", 900)], "")
        self.addCleanup(v.close)
        self.assertEqual([g.name for g in vg.read_graves(4, v.save.read_bytes())], ["Mia"])

    def test_the_first_games_skip_empty_places(self):
        v = Village(2, [grave_bytes(2, "Mia", 1000), bytes(vg.LAYOUTS[2].stride), grave_bytes(2, "Rex", 900)], "")
        self.addCleanup(v.close)
        self.assertEqual([g.place for g in vg.read_graves(2, v.save.read_bytes())], [0, 2])

    def test_a_secret_city_epitaph_is_on_its_gravestone(self):
        v = Village(3, [grave_bytes(3, "Mia", 1000, job=0)], death(1, "Mia", 1000, grave="Master Farmer",
                                                                    epitaph="Old"),
                    stones=[(0, "New")])
        self.addCleanup(v.close)
        found = vg.survey(v.folder, 3, 1)
        self.assertEqual([d.field for d in found.differences], ["epitaph"])
        vg.fix_graves(v.folder, 3, 1, [vg.Fix(0, "epitaph", "Old")], retro=True, processes=NoGame(), now=NOW)
        self.assertEqual(vg.read_graves(3, v.save.read_bytes())[0].values["epitaph"], "Old")

    def test_a_record_with_no_grave_is_a_note_never_a_difference(self):
        v = Village(5, [], death(1, "Mia", 1000, epitaph="")
                    + "Death 2\n  Name: Kai\n  Age at death: 800\n  Grave: no grave (never buried: the game "
                      "removed the body)\n  Epitaph: (none)\n\n")
        self.addCleanup(v.close)
        found = vg.survey(v.folder, 5, 1)
        self.assertEqual(found.differences, [])
        self.assertEqual(len(found.notes), 1)
        self.assertIn("Mia", found.notes[0])


class TheRepairWindow(unittest.TestCase):
    """The checklist's "Fix grave information" line and its questions (src/vv_fun_patcher_gui.py)."""
    SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def body(self, start: str, end: str) -> str:
        return self.SOURCE[self.SOURCE.index(start):self.SOURCE.index(end)]

    def test_the_checklist_offers_it_unticked(self):
        checklist = self.body("    def _repair_checklist(", "    def _last_names_dialog(")
        self.assertIn("Fix grave information", checklist)
        self.assertIn("graves_var = tk.BooleanVar(value=False)", checklist)
        self.assertIn("grave_state if graves_var.get() else None", checklist)

    def test_every_answer_starts_at_dont_know_and_edits_are_checked(self):
        dialog = self.body("    def _graves_dialog(", "    def _grave_editor(")
        self.assertIn("state[\"answers\"].get(diff.key, dont)", dialog)
        self.assertEqual(vg.DONT_KNOW, "Don't know / leave it")
        editor = self.body("    def _grave_editor(", "    def _fix_graves(")
        self.assertIn("vv_graves.check_value(number, key, value, surveyed)", editor)

    def test_retroactively_edit_records_is_asked_before_anything_is_written(self):
        fix = self.body("    def _fix_graves(", "    def _close(")
        self.assertLess(fix.index("Retroactively edit records?"), fix.index("vv_graves.fix_graves("))
        repair = self.body("    def _repair_logs(", "    def _repair_checklist(")
        self.assertIn("grave_fixes = picked", repair)
        self.assertLess(repair.index("self._fix_graves("), repair.index("vv_cut_names.restore("))


if __name__ == "__main__":
    unittest.main()
