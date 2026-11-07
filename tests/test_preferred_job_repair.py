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


if __name__ == "__main__":
    unittest.main()
