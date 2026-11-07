"""Repair Saves & Logs: graves and their Deaths log lines as the exe draws them, with Children's Graves Say
Apprentice and Checked Skill Preferences are listed as Jobs on Graves (src/vv_log_additions.py plan_apprentice,
src/vv_graves.py plan_preferred).  One test per game and combination of the two rows.

Each village has four graves, all made by a game without the preference row (the highest skill, Building 95):
  Anna, adult, died with Farming (60) checked     -> rewritten with the preference row
  Ben, child (200), died with Farming checked     -> rewritten; "Apprentice" where the game draws it
  Cara, adult, no preference                      -> left
  Dan, adult, record no longer in the save        -> left, and said so
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_graves  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import preferred_repair_fixtures as fx  # noqa: E402

OLD_EPITAPH, NEW_EPITAPH = "Strong Arms, Big Heart", "Nature's Friend"


def village(game: int, rows: list[str]) -> fx.Village:
    v = fx.Village(game)
    graves = [("Anna", 900, OLD_EPITAPH), ("Ben", 200, "Curious and Playful"), ("Cara", 900, OLD_EPITAPH),
              ("Dan", 900, OLD_EPITAPH)]
    for place, (name, age, epitaph) in enumerate(graves):
        fx.write_grave(v.buf, game, place, name, age, fx.BUILDER[game], 95, epitaph)
        v.death(place + 1, name, age, "Master Builder", epitaph)
    fx.write_entry(v.buf, game, 0, "Eve", 500, 80, fx.NONE[game], True)        # the one living villager
    fx.write_entry(v.buf, game, 1, "Anna", 900, 0, fx.FARMING[game], False)
    fx.write_entry(v.buf, game, 2, "Ben", 200, 0, fx.FARMING[game], False)
    fx.write_entry(v.buf, game, 3, "Cara", 900, 0, fx.NONE[game], False)
    v.save()
    v.log()
    if game == 1:
        fx.sidecar_vv1(v, 0, "Anna", 900, OLD_EPITAPH)
    v.rows(rows)
    return v


def rows_for(game: int, apprentice: bool, preferred: bool) -> list[str]:
    rows = [f"vv{game}_cause_of_death"]
    if apprentice and game != 4:
        rows.append(f"vv{game}_apprentice_graves")
    if preferred:
        rows.append(f"vv{game}_preferred_job_graves")
    return rows


def expected(game: int, apprentice: bool, preferred: bool) -> list[str]:
    """The lines rewritten, in log order."""
    apprentice = apprentice or game == 4
    out = []
    if preferred:
        out.append("  Grave: Adept Farmer")
        if game != 3:                           # The Secret City: these graves have no gravestone, no epitaph
            out.append(f"  Epitaph: {NEW_EPITAPH}")
        out.append("  Grave: Apprentice Farmer" if apprentice else "  Grave: Adept Farmer")
    elif apprentice:
        out.append("  Grave: Apprentice Builder")
    return out


class Combination(unittest.TestCase):
    def check(self, game: int, apprentice: bool, preferred: bool):
        v = village(game, rows_for(game, apprentice, preferred))
        try:
            kind = additions.plan_apprentice(v.folder, game, 1, v.game_folders)
            self.assertEqual([text for _p, _i, text in kind.replaces], expected(game, apprentice, preferred))
            planned = kind.context.get("graves")
            if preferred:
                self.assertEqual([p.grave.name for p in planned.graves], ["Anna", "Ben"])
                self.assertEqual([p.new for p in planned.graves], [(fx.FARMING[game], 60)] * 2)
                self.assertEqual(planned.unknown, 1)
                self.assertTrue(any("no longer in the save" in n for n in kind.notes))
            else:
                self.assertIsNone(planned)
        finally:
            v.close()


for _game in range(1, 6):
    for _a, _p, _label in ((False, False, "neither"), (True, False, "apprentice_only"),
                           (False, True, "preference_only"), (True, True, "both")):
        def _test(self, game=_game, a=_a, p=_p):
            self.check(game, a, p)
        setattr(Combination, f"test_vv{_game}_{_label}", _test)


class Apply(unittest.TestCase):
    """The save, the Graves file and the log as written, both rows in."""

    def apply(self, game: int):
        v = village(game, rows_for(game, True, True))
        try:
            kind = additions.plan_apprentice(v.folder, game, 1, v.game_folders)
            n = additions.write_preferred_graves(v.folder, game, 1, [kind], {"apprentice"})
            additions.apply(v.folder, [kind], {"apprentice"}, {})
            self.assertEqual(n, 2)
            data = (v.folder / f"{tools.load_checker().SAVE_STEMS[game]}1.ldw").read_bytes()
            graves = {g.name: g for g in vv_graves.read_graves(game, data)}
            lay = vv_graves.LAYOUTS[game]
            for name in ("Anna", "Ben"):
                at = graves[name].at
                self.assertEqual(struct.unpack_from("<i", data, at + lay.job)[0], fx.FARMING[game])
                self.assertEqual(struct.unpack_from("<i", data, at + lay.value)[0], 60)
            for name in ("Cara", "Dan"):
                self.assertEqual(struct.unpack_from("<i", data, graves[name].at + lay.job)[0], fx.BUILDER[game])
            if lay.epitaph:
                self.assertEqual(graves["Anna"].values["epitaph"], NEW_EPITAPH)
                self.assertEqual(graves["Cara"].values["epitaph"], OLD_EPITAPH)
            if game == 1:
                entries = vv_graves._vcd1_entries(vv_graves.graves_file(v.folder, 1, 1).read_bytes(), 1)
                self.assertEqual(vv_graves.EPITAPHS[entries[0][9]], NEW_EPITAPH)
            log = v.folder.joinpath(fx.LOGS, "Deaths and Disappearances",
                                    f"Virtual Villagers {game} Deaths Log 1.txt").read_text(encoding="cp1252")
            self.assertEqual(log.count("Grave: Master Builder"), 2)
            self.assertIn("Grave: Apprentice Farmer", log)
            self.assertEqual(additions.plan_apprentice(v.folder, game, 1, v.game_folders).replaces, [])
            copies = [p for p in v.folder.rglob("*before-grave-job-repair*")]
            self.assertTrue(copies, "the save is copied before it is changed")
        finally:
            v.close()

    def test_vv1(self):
        self.apply(1)

    def test_vv2(self):
        self.apply(2)

    def test_vv3(self):
        self.apply(3)

    def test_vv4(self):
        self.apply(4)

    def test_vv5(self):
        self.apply(5)

    def test_a_changed_save_is_refused(self):
        v = village(5, rows_for(5, True, True))
        try:
            kind = additions.plan_apprentice(v.folder, 5, 1, v.game_folders)
            save = v.folder / f"{tools.load_checker().SAVE_STEMS[5]}1.ldw"
            save.write_bytes(save.read_bytes() + b"\0")
            with self.assertRaises(tools.LogToolError):
                additions.write_preferred_graves(v.folder, 5, 1, [kind], {"apprentice"})
        finally:
            v.close()

    def test_check_saves_and_logs_counts_each_kind(self):
        v = village(2, rows_for(2, True, True))
        try:
            text = tools.check_logs(v.folder, 1, 2, v.game_folders).text
            self.assertIn("2 grave(s) show the villager's highest skill", text)
            self.assertIn("no longer in the save", text)
        finally:
            v.close()


def deaths_log(v: fx.Village, game: int) -> str:
    return v.folder.joinpath(fx.LOGS, "Deaths and Disappearances",
                             f"Virtual Villagers {game} Deaths Log 1.txt").read_text(encoding="cp1252")


def save_of(v: fx.Village, game: int) -> Path:
    return v.folder / f"{tools.load_checker().SAVE_STEMS[game]}1.ldw"


class SameNameAndAge(unittest.TestCase):
    """Codex, #725: two graves "Anna", both 900.  The first (Building 96) had no preference; the second (Building
    95) had Farming checked.  Only the second's Death record follows."""

    def test_each_grave_keeps_its_own_death_record(self):
        for game in (2, 5):
            v = fx.Village(game)
            try:
                first = list(fx.SKILLS[game])
                first[fx.BUILDING[game]] = 96.0 if game >= 4 else 96
                fx.write_grave(v.buf, game, 0, "Anna", 900, fx.BUILDER[game], 96, "Inspired Architect")
                fx.write_grave(v.buf, game, 1, "Anna", 900, fx.BUILDER[game], 95, OLD_EPITAPH)
                v.death(1, "Anna", 900, "Master Builder", "Inspired Architect")
                v.death(2, "Anna", 900, "Master Builder", OLD_EPITAPH)
                fx.write_entry(v.buf, game, 0, "Eve", 500, 80, fx.NONE[game], True)
                fx.write_entry(v.buf, game, 1, "Anna", 900, 0, fx.NONE[game], False, first)
                fx.write_entry(v.buf, game, 2, "Anna", 900, 0, fx.FARMING[game], False)
                v.save()
                path = v.log()
                v.rows(rows_for(game, True, True))
                kind = additions.plan_apprentice(v.folder, game, 1, v.game_folders)
                lines = path.read_text(encoding="cp1252").split("\n")
                second = lines.index("Death 2")
                self.assertTrue(all(i > second for _p, i, _t in kind.replaces), (game, kind.replaces))
                self.assertEqual([t for _p, _i, t in kind.replaces],
                                 ["  Grave: Adept Farmer", f"  Epitaph: {NEW_EPITAPH}"], game)
            finally:
                v.close()


class HalfDone(unittest.TestCase):
    """Codex, #725: the save holds the preference but the logs do not (a repair that stopped half way, or the
    row's own burial with an older log): the next plan finds the lines and nothing else."""

    def test_the_logs_follow_a_grave_already_rewritten(self):
        for game in range(1, 6):
            v = village(game, rows_for(game, True, True))
            try:
                kind = additions.plan_apprentice(v.folder, game, 1, v.game_folders)
                self.assertEqual(additions.write_preferred_graves(v.folder, game, 1, [kind], {"apprentice"}), 2)
                again = additions.plan_apprentice(v.folder, game, 1, v.game_folders)
                self.assertIsNone(again.context.get("graves"), game)
                self.assertEqual([t for _p, _i, t in again.replaces], expected(game, True, True), game)
                additions.apply(v.folder, [again], {"apprentice"}, {})
                self.assertIn("Grave: Apprentice Farmer", deaths_log(v, game))
                last = additions.plan_apprentice(v.folder, game, 1, v.game_folders)
                self.assertEqual((last.replaces, last.context.get("graves")), ([], None), game)
            finally:
                v.close()


class LogWriteFails(unittest.TestCase):
    """Codex, #725: a Deaths log that cannot be written stops Repair before the save is touched; the next Repair
    does all of it."""

    def test_the_save_is_left_until_the_logs_are_in_then_a_retry_finishes(self):
        from unittest import mock
        from test_log_tools import FakeProcesses
        game = 5
        v = village(game, rows_for(game, True, True))
        try:
            before = save_of(v, game).read_bytes()
            kinds = [additions.plan_apprentice(v.folder, game, 1, v.game_folders)]
            with mock.patch.object(additions, "apply", side_effect=OSError("the Deaths log is locked")):
                with self.assertRaises((OSError, tools.LogToolError)):
                    tools.approve_repair(v.folder, game, 1, FakeProcesses(), chosen={"apprentice"}, kinds=kinds,
                                         rearm=False)
            self.assertEqual(save_of(v, game).read_bytes(), before, "the save is untouched")
            self.assertNotIn("Adept Farmer", deaths_log(v, game))
            kinds = [additions.plan_apprentice(v.folder, game, 1, v.game_folders)]
            tools.approve_repair(v.folder, game, 1, FakeProcesses(), chosen={"apprentice"}, kinds=kinds,
                                 rearm=False)
            data = save_of(v, game).read_bytes()
            anna = next(g for g in vv_graves.read_graves(game, data) if g.name == "Anna")
            self.assertEqual(struct.unpack_from("<i", data, anna.at + vv_graves.LAYOUTS[game].job)[0], 0)
            self.assertIn("Grave: Adept Farmer", deaths_log(v, game))
            final = additions.plan_apprentice(v.folder, game, 1, v.game_folders)
            self.assertEqual((final.replaces, final.context.get("graves")), ([], None))
        finally:
            v.close()

    def test_without_kinds_the_repair_plans_with_the_game_folders(self):
        from test_log_tools import FakeProcesses
        game = 3
        v = village(game, rows_for(game, True, True))
        try:
            tools.approve_repair(v.folder, game, 1, FakeProcesses(), chosen={"apprentice"}, rearm=False,
                                 game_folders=v.game_folders)
            self.assertIn("Grave: Adept Farmer", deaths_log(v, game))
        finally:
            v.close()


class RetypedEpitaph(unittest.TestCase):
    """The audit, #725: a grave whose epitaph the player changed keeps it; its job is still rewritten."""

    def test_an_epitaph_changed_record_keeps_the_epitaph(self):
        game = 4
        v = village(game, rows_for(game, True, True))
        try:
            v.log_text += (f"Epitaph changed\n  Name: Anna\n  Age at death: 900\n  Grave: Master Builder\n"
                           f"  Old epitaph: Inspired Architect\n  New epitaph: {OLD_EPITAPH}\n\n")
            v.log()
            kind = additions.plan_apprentice(v.folder, game, 1, v.game_folders)
            anna = next(p for p in kind.context["graves"].graves if p.grave.name == "Anna")
            self.assertIsNone(anna.epitaph)
            self.assertNotIn(f"  Epitaph: {NEW_EPITAPH}", [t for _p, _i, t in kind.replaces])
            self.assertEqual([t for _p, _i, t in kind.replaces].count("  Grave: Adept Farmer"), 2)
        finally:
            v.close()


class TranslatedEpitaph(unittest.TestCase):
    def test_an_epitaph_in_another_language_is_left_and_said_so(self):
        game = 5
        v = village(game, rows_for(game, True, True))
        try:
            fx.write_grave(v.buf, game, 0, "Anna", 900, fx.BUILDER[game], 95, "Bras forts, grand coeur")
            v.save()
            kind = additions.plan_apprentice(v.folder, game, 1, v.game_folders)
            anna = next(p for p in kind.context["graves"].graves if p.grave.name == "Anna")
            self.assertIsNone(anna.epitaph)
            self.assertTrue(any("translated game" in n for n in kind.notes))
        finally:
            v.close()


if __name__ == "__main__":
    unittest.main()
