"""Repair Saves & Logs: Catch up Heathen ages (src/vv5_heathen_ages.py), New Believers.

The owner (2026-11-22): stock New Believers never ages a Heathen (the age credit 0x46FE90 skips them at 0x470077,
the life tick 0x472C90 at 0x472CB7), so a Repair Saves & Logs row adds the time each villager spent frozen among the
Heathens to their age -- former villagers, villagers who rejoined, the camp's Heathens (time since the village
started) and the puzzle Heathens -- the full time even past old age, warned in the preview; unknown time is listed
and left alone.

Each test builds a save folder by hand (a temporary folder): a New Believers save with its villager table where the
game keeps it, and the Fun Patcher's logs (Founder records, Village History snapshots) -- never the owner's saves.
"""
from __future__ import annotations

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
import vv5_heathen_ages as ha  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
NOW = datetime(2026, 11, 22, 12, 0, 0)
STRIDE = 0x118
FIRST = 0xC000                              # after the technology levels (file 0xBC1C)
VILLAGE = "Village: Test Tribe (Save 1)"

# Independent of the module: the saved entry, from the villager's name (entry +0x20; the writer 0x465270 packs
# record +0x1B8C.. from entry +0x10 and +0x1C34.. from entry +0xB8; entry +1 the faction, +0xC the role).
AGE, PROCESSED, PREGNANCY, HEALTH = -0x10, 0xA0, 0xB0, 0xA4
FACTION, ROLE, PRESENT, HEAD, BODY, SEX = -0x1F, -0x14, -0x20, 0x1C, 0x20, -0x0C
MEDICINE_AT = 0xBC0C + 0x10 + 4


class NoGame:
    def find(self, exe_name):
        return []


class Running:
    def find(self, exe_name):
        return [1]


# Every villager: (name, head, body, faction now, role, pregnancy, ages by moment).  The moments: the village's start
# (S0 is a snapshot at the start itself), S1, S2, S3 a day apart (+100 age units each), then NOW (+20).  None: not
# listed then; "H" after an age: a Heathen then.
PEOPLE = [
    # The steady believers the time is measured by (founders).
    ("Fa Alpha", 1, 1, 0, 0, 0, [400, 400, 500, 600, 700, 720]),
    ("Fb Bravo", 2, 2, 0, 0, 0, [420, 420, 520, 620, 720, 740]),
    ("Fd Delta", 3, 3, 0, 0, 0, [440, 440, 540, 640, 740, 760]),
    # A founder who became a Heathen 30 units after S1: frozen 100 - 30 + 100 + 20 = 190.
    ("Fc Charlie", 4, 4, 1, 0, 0, [400, 400, 500, "530H", "530H", 530]),
    # A camp Heathen from the start: frozen 320 (the time since the village started).
    ("Ca Camp", 5, 5, 1, 0, 0, [None, "400H", "400H", "400H", "400H", 400]),
    # The Heathen Mommy (role 17), expecting: +320, her conception stamp too.
    ("Pm Mommy", 6, 6, 1, 17, 590, [None, "600H", "600H", "600H", "600H", 600]),
    # An old camp Heathen: 1200 + 320 = 1520, past old age (Medicine 2: 1260).
    ("Oc Old", 7, 7, 1, 0, 0, [None, "1200H", "1200H", "1200H", "1200H", 1200]),
    # Born after the start, a Heathen from S1 + 50 until 10 before now: 220 - 60 = 160.
    ("Rv Rejoined", 8, 8, 0, 0, 0, [None, None, 100, "150H", "150H", 160]),
    # First listed as a Heathen after the start: when they became one is not known.
    ("Uh Unknown", 9, 9, 1, 0, 0, [None, None, None, "300H", "300H", 300]),
    # Younger at S2 than at S1 (Grant Youth): not certain.
    ("Gy Granted", 10, 10, 1, 0, 0, [None, None, 600, 100, "100H", 100]),
    # Never a Heathen: never listed.
    ("Nb Newborn", 11, 11, 0, 0, 0, [None, None, None, 50, 150, 170]),
]
DATES = ["2026-01-01 10:00:00", "2026-01-02 10:00:00", "2026-01-03 10:00:00", "2026-01-04 10:00:00"]
FOUNDERS = ("Fa Alpha", "Fb Bravo", "Fd Delta", "Fc Charlie")


def save_bytes(people=PEOPLE, medicine: int = 2) -> bytes:
    data = bytearray(FIRST + 150 * STRIDE + 64)
    struct.pack_into("<i", data, MEDICINE_AT, medicine)
    for i, (name, head, body, heathen, role, stamp, ages) in enumerate(people):
        at = FIRST + i * STRIDE + 0x40
        data[at:at + len(name)] = name.encode()
        data[at + PRESENT] = 1
        age = ages[-1]
        struct.pack_into("<i", data, at + AGE, age)
        struct.pack_into("<i", data, at + PROCESSED, age)
        struct.pack_into("<i", data, at + HEAD, head)
        struct.pack_into("<i", data, at + BODY, body)
        struct.pack_into("<i", data, at + SEX, i % 2)
        struct.pack_into("<i", data, at + HEALTH, 100)
        struct.pack_into("<i", data, at + ROLE, role)
        struct.pack_into("<i", data, at + PREGNANCY, stamp)
        data[at + FACTION] = heathen
    return bytes(data)


def _record(heading: str, lines: list[str]) -> str:
    return "\n".join([heading] + [f"  {line}" for line in lines]) + "\n\n"


def logs(people=PEOPLE) -> dict[str, str]:
    births = VILLAGE + "\n"
    deaths = VILLAGE + "\n"
    k = 0
    for name, head, body, _h, _r, _s, ages in people:
        if name in FOUNDERS:
            k += 1
            births += _record(f"Arrived {k}", [f"Name: {name}", f"Age at arrival: {ages[0]}", "Sex: Male",
                                               "How: Founder", f"Head: {head}", f"Body: {body}"])
    deaths += _record("Disappeared", ["Name: Fc Charlie", "Age: 530", "Sex: Male", f"What happened: {ha.LEFT}",
                                      "Head: 4", "Body: 4"])
    births += _record("Arrived 9", ["Name: Rv Rejoined", "Age at arrival: 150", "Sex: Male",
                                    f"How: {ha.CONVERTED}", "Head: 8", "Body: 8"])
    history = ""
    for m, date in enumerate(DATES):
        history += f"=== Virtual Villagers 5 -- {date} ===\n{VILLAGE}\n\n"
        n = 0
        for name, head, body, _h, _r, _s, ages in people:
            age = ages[m + 1]
            if age is None:
                continue
            n += 1
            heathen = isinstance(age, str)
            history += _record(f"Villager {n}", [f"Name: {name}", f"Age: {int(str(age).rstrip('H'))}", "Sex: Male",
                                                 f"Faction: {'Heathen' if heathen else 'Believer'}",
                                                 f"Head: {head}", f"Body: {body}"])
    return {"Births and Conceptions/Virtual Villagers 5 Births and Conceptions Log 1.txt": births,
            "Deaths and Disappearances/Virtual Villagers 5 Deaths Log 1.txt": deaths,
            "Tribe History/Village History 1.txt": history}


class Village:
    def __init__(self, case: unittest.TestCase, people=PEOPLE, medicine: int = 2):
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.save = ln.save_path(self.folder, 5, 1)
        self.save.write_bytes(save_bytes(people, medicine))
        for rel, text in logs(people).items():
            path = self.folder / LOGS / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.replace("\n", "\r\n").encode("cp1252"))

    def repairs(self) -> str:
        found = sorted(p for root in (self.folder / LOGS, self.folder / "Virtual Villagers Fun Patcher")
                       for p in root.rglob("Virtual Villagers * Repairs Log *.txt"))
        return found[0].read_bytes().decode("cp1252") if found else ""

    def backups(self) -> list[Path]:
        root = self.folder / "Backups"
        return sorted(root.iterdir()) if root.is_dir() else []


def at_of(data: bytes, name: str) -> int:
    i = [p[0] for p in PEOPLE].index(name)
    return FIRST + i * STRIDE + 0x40


def field(data: bytes, name: str, off: int) -> int:
    return struct.unpack_from("<i", data, at_of(data, name) + off)[0]


class TheFields(unittest.TestCase):
    def test_the_saved_entry_offsets(self):
        self.assertEqual((ha.AGE, ha.PROCESSED, ha.PREGNANCY, ha.FACTION, ha.ROLE),
                         (AGE, PROCESSED, PREGNANCY, FACTION, ROLE))
        checker = tools.load_checker()
        self.assertEqual(checker.LAYOUTS[5].age, AGE)          # the checker reads the age there too
        self.assertEqual(checker.HEALTH[5], HEALTH)
        self.assertEqual(ha.old_age_threshold(1), 1100)
        self.assertEqual(ha.old_age_threshold(3), 1420)


class TheSurvey(unittest.TestCase):
    def setUp(self):
        self.v = Village(self)
        self.found = ha.survey(self.v.folder, 1)
        self.by = {c.name: c for c in self.found.changes}

    def test_each_kind_gets_the_time_it_spent_frozen(self):
        self.assertEqual({n: c.add for n, c in self.by.items()},
                         {"Fc Charlie": 190, "Ca Camp": 320, "Pm Mommy": 320, "Oc Old": 320, "Rv Rejoined": 160})
        self.assertIn("a Heathen since leaving the tribe", self.by["Fc Charlie"].kind)
        self.assertEqual(self.by["Ca Camp"].kind, "a Heathen of the camp")
        self.assertEqual(self.by["Ca Camp"].since, "frozen since the village started")
        self.assertIn("Heathen Mommy", self.by["Pm Mommy"].kind)
        self.assertIn("puzzle Heathen", self.by["Pm Mommy"].kind)
        self.assertIn("back in the tribe", self.by["Rv Rejoined"].kind)

    def test_unknown_time_is_listed_and_never_a_believer_who_was_never_a_heathen(self):
        unknown = {u.who.split(" (")[0]: u.reason for u in self.found.unknown}
        self.assertEqual(set(unknown), {"Uh Unknown", "Gy Granted"})
        self.assertIn("first listed as a Heathen", unknown["Uh Unknown"])
        self.assertIn("cannot explain", unknown["Gy Granted"])
        for steady in ("Fa Alpha", "Fb Bravo", "Fd Delta", "Nb Newborn"):
            self.assertNotIn(steady, self.by)
            self.assertNotIn(steady, unknown)

    def test_the_preview_shows_old_to_new_and_warns_past_old_age(self):
        text = self.found.describe()
        self.assertIn("Fc Charlie (head 4, body 4), a Heathen since leaving the tribe: age 530 -> 720 (26.5 -> 36 "
                      "years), +190 (9.5 years)", text)
        self.assertIn("Ca Camp (head 5, body 5), a Heathen of the camp: age 400 -> 720 (20 -> 36 years)", text)
        self.assertIn("Medicine level 2", text)
        self.assertIn("PAST OLD AGE AFTER THE CATCH-UP", text)
        self.assertIn("Oc Old (head 7, body 7): past old age at 76 years (old age starts at 63): 100% chance of "
                      "dying at their next birthday (77 years)", text)
        self.assertEqual([c.name for c in self.found.past_old_age], ["Oc Old"])
        self.assertIn("expecting: the time left before the birth is kept", self.by["Pm Mommy"].describe())
        self.assertIn("Not known, left as they are (2):", text)
        self.assertIn("Uh Unknown (head 9, body 9): first listed as a Heathen", text)

    def test_a_lower_medicine_level_moves_old_age(self):
        v = Village(self, medicine=3)               # 1420 (71 years): the next birthday, 77, is six years past it
        old = {c.name: c for c in ha.survey(v.folder, 1).changes}["Oc Old"]
        self.assertIn("old age starts at 71): 60% chance", old.warning)

    def test_the_survey_reads_only(self):
        self.assertEqual(self.v.save.read_bytes(), save_bytes())
        self.assertEqual(self.v.backups(), [])
        self.assertEqual(self.v.repairs(), "")

    def test_no_founder_records_means_camp_heathens_are_unknown(self):
        v = Village(self)
        births = v.folder / LOGS / "Births and Conceptions" / "Virtual Villagers 5 Births and Conceptions Log 1.txt"
        births.write_bytes(f"{VILLAGE}\r\n".encode())
        found = ha.survey(v.folder, 1)
        names = {c.name for c in found.changes}
        self.assertNotIn("Ca Camp", names)
        self.assertNotIn("Pm Mommy", names)
        self.assertIn("Ca Camp", " ".join(u.who for u in found.unknown))
        self.assertIn("Rv Rejoined", names)          # measured from the snapshots alone


class TheCatchUp(unittest.TestCase):
    def test_age_and_processed_age_gain_the_same_time_and_only_those_bytes_change(self):
        v = Village(self)
        before = v.save.read_bytes()
        result = ha.catch_up(v.folder, 1, processes=NoGame(), now=NOW)
        after = v.save.read_bytes()
        want = {"Fc Charlie": 190, "Ca Camp": 320, "Pm Mommy": 320, "Oc Old": 320, "Rv Rejoined": 160}
        self.assertEqual({c.name: c.add for c in result.survey.changes}, want)
        allowed = set()
        for name, add in want.items():
            for off in (AGE, PROCESSED):
                self.assertEqual(field(after, name, off), field(before, name, off) + add, (name, off))
                allowed |= {at_of(before, name) + off + b for b in range(4)}
        # The Heathen Mommy's infant keeps its time left: the conception stamp gains the same time.
        self.assertEqual(field(after, "Pm Mommy", PREGNANCY), 590 + 320)
        allowed |= {at_of(before, "Pm Mommy") + PREGNANCY + b for b in range(4)}
        changed = {i for i in range(len(before)) if before[i] != after[i]}
        self.assertTrue(changed <= allowed, sorted(changed - allowed))
        for name in ("Uh Unknown", "Gy Granted", "Fa Alpha", "Nb Newborn"):
            self.assertEqual(field(after, name, AGE), field(before, name, AGE), name)

    def test_a_second_run_finds_nothing(self):
        v = Village(self)
        ha.catch_up(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual(ha.survey(v.folder, 1).changes, [])
        with self.assertRaises(ha.HeathenAgesError):
            ha.catch_up(v.folder, 1, processes=NoGame(), now=NOW)

    def test_backup_copy_and_one_repairs_made_record(self):
        v = Village(self)
        original = v.save.read_bytes()
        result = ha.catch_up(v.folder, 1, processes=NoGame(), now=NOW)
        backup = Path(result.backup.backup_folder)
        self.assertIn(ha.BACKUP_LABEL, ha.vv_save_backup.backup_label(backup))
        self.assertEqual((backup / v.save.name).read_bytes(), original)
        [copy] = ha.tools.copies.kept_copies(v.folder, v.save, ha.COPY_SUFFIX)
        self.assertEqual(copy.read_bytes(), original)
        text = v.repairs()
        self.assertIn("Repair 1\r\n  Date: 2026-11-22 12:00:00\r\n", text)
        self.assertIn(f"  Checked: {ha.LABEL}:", text)
        for c in result.survey.changes:
            self.assertIn(f"  Aged: {c.describe()}\r\n", text)
        self.assertIn("  Past old age: Oc Old (head 7, body 7): past old age at 76 years", text)
        self.assertIn("  Not known, left as they are: Uh Unknown (head 9, body 9): first listed", text)
        self.assertIn(f"  File: {v.save.name} -- copy kept: {copy.name}\r\n", text)
        self.assertIn(f"  Backup: {backup.name}\r\n", text)
        self.assertEqual(text.count("Repair "), 1)

    def test_the_save_is_written_last(self):
        v = Village(self)
        order = []
        real_note, real_write = ha.note, ln._write
        with mock.patch.object(ha, "note", side_effect=lambda *a, **k: (order.append("log"), real_note(*a, **k))), \
                mock.patch.object(ln, "_write", side_effect=lambda *a: (order.append("save"), real_write(*a))):
            ha.catch_up(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual(order, ["log", "save"])
        self.assertTrue(v.backups())

    def test_no_repairs_record_no_save_change(self):
        v = Village(self)
        before = v.save.read_bytes()
        with mock.patch.object(ha, "note", side_effect=OSError("disk full")):
            with self.assertRaises(ha.HeathenAgesError) as caught:
                ha.catch_up(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertIn("Repairs Made log could not be written", str(caught.exception))
        self.assertEqual(v.save.read_bytes(), before)

    def test_a_failed_save_write_is_put_back_and_said_so(self):
        v = Village(self)
        before = v.save.read_bytes()
        with mock.patch("vv_last_names.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(ha.HeathenAgesError) as caught:
                ha.catch_up(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertIn("put back as it was", str(caught.exception))
        self.assertEqual(v.save.read_bytes(), before)
        text = v.repairs()
        self.assertIn("Repair 1\r\n", text)
        self.assertIn("Repair 2\r\n", text)
        self.assertIn(f"  Not done: the {ha.LABEL} in the record before this one:", text)

    def test_refused_while_the_game_runs(self):
        v = Village(self)
        before = v.save.read_bytes()
        with self.assertRaises(tools.GameRunning):
            ha.catch_up(v.folder, 1, processes=Running(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)
        self.assertEqual(v.backups(), [])
        self.assertEqual(v.repairs(), "")

    def test_a_preview_that_no_longer_holds_changes_nothing(self):
        v = Village(self)
        shown = ha.survey(v.folder, 1)
        shown.changes[0].add += 1
        before = v.save.read_bytes()
        with self.assertRaises(ha.HeathenAgesError):
            ha.catch_up(v.folder, 1, processes=NoGame(), now=NOW, expected=shown)
        self.assertEqual(v.save.read_bytes(), before)
        self.assertEqual(v.backups(), [])


class TheChecklistAndTheDocs(unittest.TestCase):
    def test_the_checklist_row_is_never_ticked_and_repair_confirms_the_list(self):
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        checklist = gui[gui.index("    def _repair_checklist("):gui.index("    def _history_list_dialog(")]
        self.assertIn("heathen_var = tk.BooleanVar(value=False)", checklist)
        self.assertIn("vv5_heathen_ages.LABEL", checklist)
        self.assertIn('skills["catch_up_heathens"] = bool(heathen_ages is not None and heathen_ages.changes) '
                      "and heathen_var.get()", checklist)
        repair = gui[gui.index("    def _repair_logs("):gui.index("    def _repair_checklist(")]
        self.assertIn('skills["heathen_ages"] = vv5_heathen_ages.survey(folder, info.slot)', repair)
        self.assertLess(repair.index("vv_log_tools.approve_repair("), repair.index("self._catch_up_heathen_ages("))
        self.assertLess(repair.index("self._catch_up_heathen_ages("), repair.index("vv_cut_names.restore("))
        method = gui[gui.index("    def _catch_up_heathen_ages("):gui.index("    def _reset_corrupt_skills(")]
        self.assertIn("self._heathen_ages_dialog(parent, found, ask=True)", method)
        self.assertIn("vv5_heathen_ages.catch_up(folder, info.slot, expected=found)", method)
        self.assertLess(method.index("_heathen_ages_dialog(parent"), method.index("vv5_heathen_ages.catch_up("))

    def test_the_guide_readme_and_how_to_use_say_it(self):
        import json
        guide = json.dumps(json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8")))
        self.assertIn("Catch up Heathen ages", guide)
        self.assertIn("**Catch up Heathen ages**", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("CATCH UP HEATHEN AGES", (ROOT / "How to Use.txt").read_text(encoding="utf-8"))

    def test_it_ships(self):
        self.assertIn('"src/vv5_heathen_ages.py"', (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
