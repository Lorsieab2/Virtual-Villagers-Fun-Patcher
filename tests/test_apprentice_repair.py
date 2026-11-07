"""Repair Saves & Logs: children's Grave (Job) lines as "Apprentice <job>" (all four games that need it).

The owner (2026-11-07): "put the "apprentice" in graves as a new Repair Saves/Logs fix" -- in the grave's "Job"
part only.  A grave in the save keeps job, best skill and age, never the words, so with Children's Graves Say
Apprentice in the exe (or in The Tree of Life, stock) every child's grave is already drawn "Apprentice <job>".
What still names the rank is the patcher's own Deaths log: the Grave line of Death and Epitaph changed records
written before.  src/vv_log_additions.py plan_apprentice finds those lines (age at death under 280, a rank and a
job word), Check Saves & Logs says how many, and Repair rewrites exactly them, in place, the file copied first.

Fixtures are built here; no file outside the repository is read.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_tools as tools  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
SAVE_FOLDER = {1: "Virtual Villagers - A New Home - Modded", 2: "Virtual Villagers - The Lost Children - Modded",
               3: "Virtual Villagers - The Secret City - Modded", 4: "Virtual Villagers - The Tree of Life - Modded",
               5: "Virtual Villagers - New Believers - Modded"}
JOB = {1: "Farmer", 2: "Doctor", 3: "Builder", 4: "Parent", 5: "Devotee"}
VILLAGE = "Village: Test Tribe (Save 1)"


def deaths_log(game: int) -> str:
    job = JOB[game]
    return (f"{VILLAGE}\n"
            # A child, rank named: rewritten.
            f"Death 1\n  Name: Kiki\n  Age at death: 200\n  Sex: Female\n  Cause of death: Disease\n"
            f"  Grave: Adept {job}\n  Epitaph: Curious and Playful\n\n"
            # A child, Untrained: left.
            f"Death 2\n  Name: Lulu\n  Age at death: 100\n  Sex: Female\n  Cause of death: Disease\n"
            f"  Grave: Untrained\n  Epitaph: Loving and Special\n\n"
            # An adult (280 is 14 years): left.
            f"Death 3\n  Name: Moko\n  Age at death: 280\n  Sex: Male\n  Cause of death: Old age\n"
            f"  Grave: Master {job}\n  Epitaph: Respected Citizen\n\n"
            # The last unit before 14, Trainee: rewritten.
            f"Death 4\n  Name: Pua\n  Age at death: 279\n  Sex: Female\n  Cause of death: Starvation\n"
            f"  Grave: Trainee {job}\n  Epitaph: Curious and Playful\n\n"
            # A child with no grave: left.
            f"Death 5\n  Name: Nui\n  Age at death: 60\n  Sex: Male\n  Cause of death: Disease\n"
            f"  Grave: no grave\n  Epitaph: (none)\n\n"
            # The Epitaph changed record of Kiki's grave: its Grave line too.
            f"Epitaph changed\n  Name: Kiki\n  Age at death: 200\n  Grave: Adept {job}\n"
            f"  Old epitaph: Curious and Playful\n  New epitaph: Our little one\n\n"
            # Already "Apprentice": left.
            f"Death 6\n  Name: Tau\n  Age at death: 150\n  Sex: Male\n  Cause of death: Disease\n"
            f"  Grave: Apprentice {job}\n  Epitaph: Curious and Playful\n\n")


class Fixture:
    def __init__(self, game: int, rows: list[str] | None, *, log_matches: bool = True):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.folder = root / "LDW" / SAVE_FOLDER[game]
        logs = self.folder / LOGS / "Deaths and Disappearances"
        logs.mkdir(parents=True)
        self.log = logs / f"Virtual Villagers {game} Deaths Log 1.txt"
        self.log.write_bytes(deaths_log(game).encode("cp1252"))
        # A save the checker can open (an empty village): Check Saves & Logs needs the slot's save.
        stem = tools.load_checker().SAVE_STEMS[game]
        (self.folder / f"{stem}1.ldw").write_bytes(bytes(0x40000))
        self.game_folders = []
        if rows is not None:
            built = root / "Games" / SAVE_FOLDER[game]
            files = built / "Virtual Villagers Fun Patcher Files"
            files.mkdir(parents=True)
            exe = built / f"{SAVE_FOLDER[game]}.exe"
            exe.write_bytes(b"MZ not a real game" + bytes([game]))
            digest = hashlib.sha256(exe.read_bytes()).hexdigest()
            (files / (exe.stem + gm.PATCH_LOG_SUFFIX)).write_text(json.dumps({
                "patcher": gm.PATCHER_SIGNATURE, "output_sha256": digest if log_matches else "0" * 64,
                "fun_patches": rows, "created_utc": "2026-11-07T00:00:00"}), encoding="utf-8")
            self.game_folders = [built]

    def close(self):
        self.tmp.cleanup()


class ApprenticeRepairTests(unittest.TestCase):
    def plan(self, f: Fixture, game: int):
        return next(k for k in additions.plan(f.folder, game, 1, f.game_folders) if k.id == "apprentice")

    def test_with_the_row_each_childs_rank_line_and_nothing_else_is_rewritten(self):
        for game in (1, 2, 3, 5):
            f = Fixture(game, [f"vv{game}_apprentice_graves", f"vv{game}_cause_of_death"])
            try:
                kind = self.plan(f, game)
                job = JOB[game]
                lines = f.log.read_text(encoding="cp1252").split("\n")
                self.assertEqual([(lines[i], new) for _p, i, new in kind.replaces],
                                 [(f"  Grave: Adept {job}", f"  Grave: Apprentice {job}"),
                                  (f"  Grave: Trainee {job}", f"  Grave: Apprentice {job}"),
                                  (f"  Grave: Adept {job}", f"  Grave: Apprentice {job}")], game)
                checked = tools.check_logs(f.folder, 1, game, f.game_folders)
                self.assertIn("3 record(s) of children's graves name the rank", checked.text, game)
                before = f.log.read_bytes()
                done = additions.apply(f.folder, [kind], {"apprentice"}, {})
                after = f.log.read_bytes()
                self.assertEqual(after, before.replace(f"  Grave: Adept {job}\n".encode(),
                                                       f"  Grave: Apprentice {job}\n".encode())
                                 .replace(f"  Grave: Trainee {job}\n".encode(),
                                          f"  Grave: Apprentice {job}\n".encode()), game)
                self.assertEqual(sum(fix.count for fix in done["apprentice"]), 3)
                copies = [p for p in f.folder.rglob("*") if p.is_file() and p.read_bytes() == before]
                self.assertTrue(copies, "the log is copied before it is changed")
                # Planned again: nothing left.
                self.assertEqual(self.plan(f, game).replaces, [])
            finally:
                f.close()

    def test_without_the_row_nothing_changes(self):
        for game in (1, 2, 3, 5):
            f = Fixture(game, [f"vv{game}_cause_of_death"])
            try:
                kind = self.plan(f, game)
                self.assertEqual((kind.replaces, kind.notes), ([], []), game)
            finally:
                f.close()

    def test_when_the_game_cannot_be_told_nothing_changes_and_it_says_so(self):
        for game in (1, 2, 3, 5):
            for f in (Fixture(game, None), Fixture(game, [f"vv{game}_apprentice_graves"], log_matches=False)):
                try:
                    kind = self.plan(f, game)
                    self.assertEqual(kind.replaces, [], game)
                    self.assertTrue(any("could not be told" in n for n in kind.notes), game)
                finally:
                    f.close()

    def test_the_tree_of_life_has_it_in_the_stock_game(self):
        f = Fixture(4, None)
        try:
            kind = self.plan(f, 4)
            self.assertEqual(len(kind.replaces), 3)
        finally:
            f.close()

    def test_registered_for_the_repairs_log_and_the_guide(self):
        self.assertIn("apprentice", additions.CHECKED)
        self.assertIn("apprentice", additions.ADDED)
        howto = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        self.assertTrue(any("Apprentice" in line for line in howto["controls"]["repair_logs"]["guide"]))


if __name__ == "__main__":
    unittest.main()
