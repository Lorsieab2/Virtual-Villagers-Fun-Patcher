"""Repair Saves & Logs: Reset corrupted skill values (src/vv_corrupt_skills.py), all five games.

The owner (v1.35.70): "Can you reset obviously-corrupted skill values?"  Only a value no game can
hold counts: NaN, +-infinity, below 0, above 100 (the stock skill writers 0x437230, 0x445430,
0x455740 clamp a signed int to 0..100; 0x46AD80, 0x475730 a float to 0.0..100.0).

Each test builds a save folder of one game by hand (in a temporary folder), with the villager table
where the game keeps it -- never the owner's saves.
"""
from __future__ import annotations

import math
import os
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

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
NOW = datetime(2026, 10, 11, 12, 0, 0)
STRIDE = {2: 0x2E0, 3: 0x11C, 4: 0x104, 5: 0x118}
FIRST = 0x2000
NAN = struct.unpack("<f", struct.pack("<I", 0x7FC00000))[0]
INF = float("inf")


def cs():
    import vv_corrupt_skills
    return vv_corrupt_skills


class NoGame:
    def find(self, exe_name):
        return []


class Running:
    def find(self, exe_name):
        return [1]


# Where each game's save keeps the skills, from the villager's name (independent of the module):
# A New Home record +0x3BC with the name at +0x370; The Lost Children record +0x7E4, name +0x564;
# The Secret City record +0xEAC, name +0xDD4; The Tree of Life and New Believers record +0x1C5C,
# name +0x1B9C.
SKILL_AT = {1: 0x3BC - 0x370, 2: 0x7E4 - 0x564, 3: 0xEAC - 0xDD4, 4: 0x1C5C - 0x1B9C, 5: 0x1C5C - 0x1B9C}
IS_FLOAT = {1: False, 2: False, 3: False, 4: True, 5: True}
COUNT = {1: 5, 2: 5, 3: 5, 4: 5, 5: 6}


def save_for(game: int, people: list[dict]) -> bytes:
    """A save the checker and Last Names read as the game loads it."""
    checker = tools.load_checker()
    f = ln.FIELDS[game]
    fmt = "<f" if IS_FLOAT[game] else "<i"
    if game == 1:
        data = bytearray(0x184 + 256 * 0x9C)
        for i, p in enumerate(people):
            base = 0x184 + i * 0x9C - 0x33C
            struct.pack_into("<i", data, base + 0x350, 2)
            struct.pack_into("<i", data, base + 0x348, 500)
            struct.pack_into("<i", data, base + 0x344, p.get("health", 100))
            struct.pack_into("<ii", data, base + 0x360, p["head"], p["body"])
            data[base + 0x3D4] = 1
            at = base + 0x370
            data[at:at + len(p["name"])] = p["name"].encode()
            for k, v in enumerate(p["skills"]):
                struct.pack_into(fmt, data, at + SKILL_AT[game] + 4 * k, v)
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
        struct.pack_into("<i", data, at + f.sex, 2 if game == 2 else 1)
        struct.pack_into("<i", data, at + checker.HEALTH[game], p.get("health", 100))
        if game == 5 and p.get("heathen"):
            data[at - 0x1F] = 1
        for k, v in enumerate(p["skills"]):
            struct.pack_into(fmt, data, at + SKILL_AT[game] + 4 * k, v)
    return bytes(data)


def skills_of(game: int, data: bytes, k: int) -> list:
    at = ln._entries(game, data, bodies=True)[k]
    fmt = "<f" if IS_FLOAT[game] else "<i"
    return [struct.unpack_from(fmt, data, at + SKILL_AT[game] + 4 * j)[0] for j in range(COUNT[game])]


def raw_skills_of(game: int, data: bytes, k: int) -> list:
    at = ln._entries(game, data, bodies=True)[k]
    return [struct.unpack_from("<I", data, at + SKILL_AT[game] + 4 * j)[0] for j in range(COUNT[game])]


class Village:
    def __init__(self, case: unittest.TestCase, game: int, people: list[dict]):
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.game = game
        self.save = ln.save_path(self.folder, game, 1)
        self.save.write_bytes(save_for(game, people))

    def repairs(self) -> str:
        found = sorted((self.folder / LOGS).rglob("Virtual Villagers * Repairs Log *.txt"))
        return found[0].read_bytes().decode("latin-1") if found else ""

    def backups(self) -> list[Path]:
        root = self.folder / "Backups"
        return sorted(p for p in root.iterdir()) if root.is_dir() else []


def int_people() -> list[dict]:
    return [
        {"name": "Alapai", "head": 3, "body": 2, "skills": [-5, 101, 0, 100, 50]},
        {"name": "Kai", "head": 4, "body": 4, "skills": [0, 100, 37, 1, 99]},          # all valid
        {"name": "Moana", "head": 5, "body": 1, "skills": [-2147483648, 2147483647, 7, 100, 0]},
    ]


def float_people(game: int) -> list[dict]:
    extra = [12.5] if game == 5 else []
    return [
        {"name": "Alapai", "head": 3, "body": 2, "skills": [NAN, INF, -INF, -0.5, 100.5] + extra},
        {"name": "Kai", "head": 4, "body": 4, "skills": [0.0, 100.0, -0.0, 37.25, 99.999] + extra},   # all valid
        {"name": "Moana", "head": 5, "body": 1, "skills": [1e30, 7.0, -1e-30, 100.0, 0.0] + ([-3.0] if game == 5 else [])},
    ]


class TheSkillFields(unittest.TestCase):
    def test_each_games_save_layout(self):
        mod = cs()
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertEqual(mod.SKILLS[game], (SKILL_AT[game], IS_FLOAT[game]))
                self.assertEqual(len(mod.SKILL_NAMES[game]), COUNT[game])
        self.assertEqual(cs().SKILL_NAMES[1], ("Parenting", "Building", "Farming", "Healing", "Research"))
        self.assertEqual(cs().SKILL_NAMES[2], cs().SKILL_NAMES[1])
        self.assertEqual(cs().SKILL_NAMES[3], ("Farming", "Parenting", "Healing", "Research", "Building"))
        self.assertEqual(cs().SKILL_NAMES[4], cs().SKILL_NAMES[3])
        self.assertEqual(cs().SKILL_NAMES[5], cs().SKILL_NAMES[3] + ("Devotion",))

    def test_the_checkers_reading_agrees(self):
        """The skills sit where Check Saves & Logs itself reads them (scripts/vvfp_consistency_check.py)."""
        checker = tools.load_checker()
        for game in range(2, 6):
            lay = checker.LAYOUTS[game]
            self.assertEqual((lay.skills, lay.skill_count, lay.skills_float),
                             (SKILL_AT[game], COUNT[game], IS_FLOAT[game]))

    def test_only_impossible_values_count(self):
        fix = cs().fixed_value
        for v in (0, 1, 50, 100):
            self.assertIsNone(fix(v, False))
        self.assertEqual(fix(-1, False), 0)
        self.assertEqual(fix(101, False), 100)
        for v in (0.0, -0.0, 0.5, 100.0, 99.99999):
            self.assertIsNone(fix(v, True), v)
        for v, want in ((NAN, 0.0), (INF, 0.0), (-INF, 0.0), (-0.001, 0.0), (100.001, 100.0), (1e38, 100.0)):
            self.assertEqual(fix(v, True), want, v)


class TheSurvey(unittest.TestCase):
    def test_int_games_find_and_name_each_value(self):
        for game in (1, 2, 3):
            with self.subTest(game=game):
                v = Village(self, game, int_people())
                found = cs().survey(v.folder, game, 1)
                names = cs().SKILL_NAMES[game]
                self.assertEqual([r.describe() for r in found], [
                    f"Alapai (head 3, body 2): {names[0]} -5 -> 0",
                    f"Alapai (head 3, body 2): {names[1]} 101 -> 100",
                    f"Moana (head 5, body 1): {names[0]} -2147483648 -> 0",
                    f"Moana (head 5, body 1): {names[1]} 2147483647 -> 100",
                ])

    def test_float_games_find_and_name_each_value(self):
        for game in (4, 5):
            with self.subTest(game=game):
                v = Village(self, game, float_people(game))
                found = cs().survey(v.folder, game, 1)
                n = cs().SKILL_NAMES[game]
                want = [
                    f"Alapai (head 3, body 2): {n[0]} NaN (0x7FC00000) -> 0",
                    f"Alapai (head 3, body 2): {n[1]} infinity -> 0",
                    f"Alapai (head 3, body 2): {n[2]} -infinity -> 0",
                    f"Alapai (head 3, body 2): {n[3]} -0.5 -> 0",
                    f"Alapai (head 3, body 2): {n[4]} 100.5 -> 100",
                    f"Moana (head 5, body 1): {n[0]} 1.00000002e+30 -> 100",
                    f"Moana (head 5, body 1): {n[2]} -1e-30 -> 0",
                ]
                if game == 5:
                    want.append("Moana (head 5, body 1): Devotion -3 -> 0")
                self.assertEqual([r.describe() for r in found], want)

    def test_nothing_valid_is_found(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                people = int_people()[1:2] if game <= 3 else float_people(game)[1:2]
                v = Village(self, game, people)
                self.assertEqual(cs().survey(v.folder, game, 1), [])

    def test_heathens_and_bodies_are_included_and_named(self):
        v = Village(self, 5, [
            {"name": "Ula", "head": 1, "body": 1, "skills": [0.0, 0.0, 0.0, 0.0, 0.0, NAN], "heathen": True},
            {"name": "Rua", "head": 2, "body": 2, "skills": [200.0, 0.0, 0.0, 0.0, 0.0, 0.0], "health": 0},
        ])
        self.assertEqual([r.describe() for r in cs().survey(v.folder, 5, 1)], [
            "Ula (head 1, body 1), a Heathen: Devotion NaN (0x7FC00000) -> 0",
            "Rua (head 2, body 2), a body not yet buried: Farming 200 -> 100",
        ])


class TheReset(unittest.TestCase):
    def _village(self, game: int) -> Village:
        return Village(self, game, int_people() if game <= 3 else float_people(game))

    def test_reset_writes_only_the_corrupted_dwords(self):
        for game in range(1, 6):
            with self.subTest(game=game):
                v = self._village(game)
                before = v.save.read_bytes()
                found = cs().survey(v.folder, game, 1)
                result = cs().reset(v.folder, game, 1, processes=NoGame(), now=NOW)
                after = v.save.read_bytes()
                self.assertEqual(len(after), len(before))
                changed = {i for i in range(len(before)) if before[i] != after[i]}
                allowed = {r.offset + b for r in found for b in range(4)}
                self.assertTrue(changed <= allowed, sorted(changed - allowed))
                self.assertEqual(len(result.reset), len(found))
                if game <= 3:
                    self.assertEqual(skills_of(game, after, 0), [0, 100, 0, 100, 50])
                    self.assertEqual(skills_of(game, after, 1), [0, 100, 37, 1, 99])
                    self.assertEqual(skills_of(game, after, 2), [0, 100, 7, 100, 0])
                else:
                    extra = [12.5] if game == 5 else []
                    self.assertEqual(skills_of(game, after, 0), [0.0, 0.0, 0.0, 0.0, 100.0] + extra)
                    # The valid ones, -0.0 too, keep their exact bits.
                    self.assertEqual(raw_skills_of(game, after, 1), raw_skills_of(game, before, 1))
                    self.assertEqual(raw_skills_of(game, before, 1)[2], 0x80000000)
                    moana = skills_of(game, after, 2)
                    self.assertEqual(moana[:5], [100.0, 7.0, 0.0, 100.0, 0.0])
                    if game == 5:
                        self.assertEqual(moana[5], 0.0)
                self.assertEqual(cs().survey(v.folder, game, 1), [])

    def test_backed_up_first_with_a_copy_and_one_repair_record(self):
        for game in (1, 4, 5):
            with self.subTest(game=game):
                v = self._village(game)
                original = v.save.read_bytes()
                found = cs().survey(v.folder, game, 1)
                result = cs().reset(v.folder, game, 1, processes=NoGame(), now=NOW)
                backup = Path(result.backup.backup_folder)
                self.assertIn(cs().BACKUP_LABEL, backup.name)
                self.assertEqual((backup / v.save.name).read_bytes(), original)
                copy = v.folder / DATA / "Copies Made Before Repairs" / (v.save.name + cs().COPY_SUFFIX)
                self.assertEqual(copy.read_bytes(), original)
                text = v.repairs()
                self.assertIn("Repair 1\r\n  Date: 2026-10-11 12:00:00\r\n", text)
                self.assertIn("  Checked: every villager's skills in the save, for values no game can hold "
                              "(NaN, infinite, below 0 or above 100)\r\n", text)
                for r in found:
                    self.assertIn(f"  Reset: {r.describe()}\r\n", text)
                self.assertIn(f"  File: {v.save.name} -- copy kept: {copy.name}\r\n", text)
                self.assertIn(f"  Backup: {backup.name}\r\n", text)
                self.assertEqual(text.count("Repair "), 1)
                # In the slot's own Repairs Made folder.
                logged = sorted((v.folder / LOGS).rglob("Virtual Villagers * Repairs Log *.txt"))
                self.assertIn("Save 1", str(logged[0]))

    def test_the_record_wording_for_an_int_game(self):
        v = self._village(2)
        cs().reset(v.folder, 2, 1, processes=NoGame(), now=NOW)
        text = v.repairs()
        self.assertIn("  Reset: Alapai (head 3, body 2): Parenting -5 -> 0\r\n", text)
        self.assertIn("  Reset: Alapai (head 3, body 2): Building 101 -> 100\r\n", text)
        self.assertNotIn("Kai", text)

    def test_refused_while_the_game_runs(self):
        v = self._village(4)
        before = v.save.read_bytes()
        with self.assertRaises(tools.GameRunning):
            cs().reset(v.folder, 4, 1, processes=Running(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)
        self.assertEqual(v.backups(), [])
        self.assertEqual(v.repairs(), "")

    def test_nothing_found_changes_nothing(self):
        v = Village(self, 3, int_people()[1:2])
        before = v.save.read_bytes()
        with self.assertRaises(cs().SkillResetError):
            cs().reset(v.folder, 3, 1, processes=NoGame(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)
        self.assertEqual(v.backups(), [])

    def test_written_through_a_temporary_file_and_read_back(self):
        v = self._village(5)
        with mock.patch.object(ln, "_write", wraps=ln._write) as spy:
            cs().reset(v.folder, 5, 1, processes=NoGame(), now=NOW)
        self.assertEqual(spy.call_args_list[0].args[0], v.save)
        self.assertEqual(list(v.folder.glob("*.lastnames-tmp")), [])

    def test_a_failed_swap_leaves_the_save_as_it_was(self):
        v = self._village(1)
        before = v.save.read_bytes()
        with mock.patch("vv_last_names.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(cs().SkillResetError) as caught:
                cs().reset(v.folder, 1, 1, processes=NoGame(), now=NOW)
        self.assertIn("put back as it was", str(caught.exception))
        self.assertEqual(v.save.read_bytes(), before)
        self.assertEqual(list(v.folder.glob("*.lastnames-tmp")), [])
        self.assertEqual(v.repairs(), "")

    def test_a_bad_read_back_puts_the_save_back(self):
        v = self._village(4)
        before = v.save.read_bytes()
        real = Path.read_bytes
        calls = {"n": 0}

        def flaky(path):
            data = real(path)
            if path == v.save and data != before:
                calls["n"] += 1
                if calls["n"] == 1:                 # the read-back inside ln._write
                    return data[:-1] + bytes([data[-1] ^ 0xFF])
            return data
        with mock.patch.object(Path, "read_bytes", flaky):
            with self.assertRaises(cs().SkillResetError):
                cs().reset(v.folder, 4, 1, processes=NoGame(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)


class TheCheckAndTheChecklist(unittest.TestCase):
    def test_check_saves_and_logs_lists_them_as_a_note(self):
        for game in (1, 3, 5):
            with self.subTest(game=game):
                v = Village(self, game, int_people() if game <= 3 else float_people(game))
                result = tools.check_logs(v.folder, 1, game)
                lines = [line for line in result.text.splitlines() if "skill value(s) no game can hold" in line]
                self.assertEqual(len(lines), 1, result.text)
                self.assertTrue(lines[0].lstrip().startswith("NOTE"), lines[0])
                self.assertIn("Alapai (head 3, body 2):", lines[0])
                self.assertIn("Reset corrupted skill values", lines[0])
                self.assertEqual(v.save.read_bytes(), save_for(game, int_people() if game <= 3 else float_people(game)))

    def test_no_note_when_every_value_is_valid(self):
        v = Village(self, 4, float_people(4)[1:2])
        self.assertNotIn("no game can hold", tools.check_logs(v.folder, 1, 4).text)

    def test_the_checklist_row_is_ticked_only_when_something_is_found(self):
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        checklist = gui[gui.index("    def _repair_checklist("):gui.index("    def _last_names_dialog(")]
        self.assertIn('skills_var = tk.BooleanVar(value=bool(skills["found"]))', checklist)
        self.assertIn("Reset corrupted skill values:", checklist)
        self.assertIn('skills["reset"] = bool(skills["found"]) and skills_var.get()', checklist)
        repair = gui[gui.index("    def _repair_logs("):gui.index("    def _repair_checklist(")]
        self.assertIn('skills["found"] = vv_corrupt_skills.survey(folder, number, info.slot)', repair)
        self.assertIn('if skills["reset"]:', repair)
        # After the game's repair is approved, before any rename (the record names the save's names).
        self.assertLess(repair.index("vv_log_tools.approve_repair("), repair.index("self._reset_corrupt_skills("))
        self.assertLess(repair.index("self._reset_corrupt_skills("), repair.index("vv_cut_names.restore("))
        method = gui[gui.index("    def _reset_corrupt_skills("):]
        self.assertIn("vv_corrupt_skills.reset(folder, number, info.slot)", method[:1200])

    def test_the_guide_and_readme_say_it(self):
        import json
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        text = json.dumps(guide)
        self.assertIn("Reset corrupted skill values", text)
        self.assertIn("**Reset corrupted skill values**", (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
