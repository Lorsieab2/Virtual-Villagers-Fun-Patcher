"""Missing last names (the owner, v1.35.66): "if repair logs detects a missing last name, please prompt
the player to add one if auto check is enabled" -- "like for arrivals and stuff. and direct them how to
add last names" -- and "an optional toggle (default on) for automatically assigning unique last names
for arrived villagers" (src/vv_last_names.py missing_last_names, the request file, the arrivals toggle;
the patcher's prompt in src/vv_fun_patcher_gui.py; the game's quit check in
native/shared/crosscheck_bridge.h, tested by tests/test_first_load_prompt.py).

A small The Secret City save and log folder is built by hand (tests/test_last_names_rename.py's); the
other games' detection is the same reading of the same Living records, checked with each game's own
list of last names."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_last_names_rename import TABLE, NoGame, Running, entry  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
NOW = datetime(2026, 10, 10, 12, 0, 0)


class Village(unittest.TestCase):
    """Founders Ago (family 1) and Aipi (50), their child Kid; Kalea, who arrived by a Custom Island
    Event; Mele Ana, whose two words the player said are one first name; Big Bob (a second word is a
    last name); Zero, head 0 and body 0; and a dead Moa Akikai the logs know."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        people = [
            entry("Ago Akikai", 0, 1, 5, 6),
            entry("Aipi", 1, 50, 7, 8),
            entry("Kid", 0, 50, 9, 9, father=("Ago Akikai", 5, 6), mother=("Aipi", 7, 8)),
            entry("Kalea", 1, 3, 4, 4),
            entry("Mele Ana", 1, 4, 2, 2),
            entry("Big Bob", 0, 5, 3, 3),
            entry("Zero", 0, 6, 0, 0),
        ]
        self.save = self.folder / "Virtual Villagers - The Secret City1.ldw"
        self.save.write_bytes(bytes(b"ldwg" + bytes(TABLE - 4)) + b"".join(people) + bytes(64))
        self._log("Births and Conceptions/Virtual Villagers 3 Births and Conceptions Log 1.txt",
                  "Village: Tribe (Save 1)\n"
                  "Arrived 1\n  Name: Kalea\n  Sex: Female\n  Head: 4\n  Body: 4\n  How: Custom Island Event\n\n"
                  "Arrived 2\n  Name: Ago Akikai\n  Sex: Male\n  Head: 5\n  Body: 6\n  How: Founder\n\n")
        self._log("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                  "Village: Tribe (Save 1)\nDeath 1\n  Name: Moa Akikai\n  Age at death: 1400\n"
                  "  Head: 1\n  Body: 1\n\n")
        named = mock.patch("vv_log_additions.current_villages", return_value={"Village: Tribe (Save 1)"})
        named.start()
        self.addCleanup(named.stop)

    def _log(self, relative: str, text: str) -> Path:
        path = self.folder / LOGS / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", "\r\n").encode())
        return path

    def record(self, *lines: str) -> None:
        path = ln.record_path(self.folder, 3, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(["VVFP LAST NAMES v1 game=3", *lines]) + "\n", encoding="utf-8")

    def missing(self) -> dict[str, ln.Missing]:
        return {m.villager.name: m for m in ln.missing_last_names(self.folder, 3, 1)}


class Detection(Village):
    def test_a_village_that_does_not_use_last_names_is_never_flagged(self):
        self.save.write_bytes(self.save.read_bytes().replace(b"Ago Akikai", b"Ago\0\0\0\0\0\0\0"))
        self.assertFalse(ln.uses_last_names(self.folder, 3, 1))
        self.assertEqual(ln.missing_last_names(self.folder, 3, 1), [])

    def test_a_villager_with_one_of_the_games_last_names_means_the_village_uses_them(self):
        self.assertTrue(ln.uses_last_names(self.folder, 3, 1))

    def test_who_has_none(self):
        self.record("rule\tfather", "whole\tMele Ana")
        found = self.missing()
        self.assertEqual(sorted(found), ["Aipi", "Kalea", "Kid", "Mele Ana", "Zero"],
                         "one word, or words the player said are one first name; Big Bob's second word is a "
                         "last name; Ago has his")
        self.assertEqual((found["Zero"].villager.head, found["Zero"].villager.body), (0, 0),
                         "head 0 and body 0 are a real villager")

    def test_without_the_record_a_multi_word_first_name_is_not_taken_for_missing(self):
        self.assertNotIn("Mele Ana", self.missing())

    def test_an_arrival_is_named_with_how_they_came(self):
        found = self.missing()
        self.assertEqual(found["Kalea"].describe(), "Kalea arrived (Custom Island Event) with no last name")
        self.assertEqual(found["Aipi"].describe(), "Aipi has no last name")

    def test_the_suggestions_follow_the_rule_and_fit(self):
        self.record("rule\tfather")
        found = self.missing()
        self.assertEqual(found["Kid"].suggested, "Akikai", "the father's, by the village's rule")
        taken = {"Akikai"}
        for name, m in found.items():
            if name != "Kid":
                self.assertTrue(m.suggested and m.suggested not in taken, (name, m.suggested))
                self.assertLessEqual(len(ln.with_last(3, name, m.suggested)), ln.ROOM[3])
                taken.add(m.suggested)

    def test_check_logs_reports_them_as_a_note(self):
        report = mock.MagicMock()
        with mock.patch.object(tools, "load_checker", wraps=tools.load_checker):
            note = ln.missing_note(3, ln.missing_last_names(self.folder, 3, 1))
        self.assertIn("living villager(s) have no last name: ", note)
        self.assertIn("Kalea arrived (Custom Island Event) with no last name", note)
        source = (ROOT / "src" / "vv_log_tools.py").read_text(encoding="utf-8")
        self.assertIn('report.add(f"{LOGS} (missing last names)", "NOTE", vv_last_names.missing_note(game, missing))',
                      source)
        del report


class EveryGame(unittest.TestCase):
    """The same reading in all five games: each game's own list decides what a last name is, and the
    record's "whole" lines what is one first name."""

    def test_all_five_games(self):
        checker = tools.load_checker()
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                last = checker.LAST_NAMES[game][0]
                people = [ln.Living(0, "Soda", "Male", 0, 0, 1, last),
                          ln.Living(1, f"Pua {last}", "Female", 1, 1, 1, last),
                          ln.Living(2, "Soda II", "Male", 2, 2, 1, last),
                          ln.Living(3, f"Mele {last} III", "Female", 3, 3, 1, last),
                          ln.Living(4, "Mele Ana", "Female", 4, 4, 2, last)]
                village = mock.MagicMock()
                village.known.return_value = []
                with tempfile.TemporaryDirectory() as tmp, \
                        mock.patch.object(ln, "everyone", return_value=(people, {})), \
                        mock.patch.object(ln, "living", return_value=people), \
                        mock.patch("vv_genealogy.load_village", return_value=village):
                    found = [m.villager.name for m in ln.missing_last_names(Path(tmp), game, 1)]
                    self.assertEqual(found, ["Soda", "Soda II"])
                    path = ln.record_path(Path(tmp), game, 1)
                    path.parent.mkdir(parents=True)
                    path.write_text(f"VVFP LAST NAMES v1 game={game}\nwhole\tMele Ana\n", encoding="utf-8")
                    found = [m.villager.name for m in ln.missing_last_names(Path(tmp), game, 1)]
                    self.assertEqual(found, ["Soda", "Soda II", "Mele Ana"])

    def test_a_heathen_is_never_asked_about(self):
        people = [ln.Living(0, "Soda Akikai", "Male", 1, 1, 1, "Akikai"), ln.Living(1, "Kahu", "Male", 2, 2, 1, "")]
        heathen = mock.MagicMock(key=("Kahu", 2, 2), heathen=True, how="", arrived=False)
        village = mock.MagicMock()
        village.known.return_value = [heathen]
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(ln, "everyone", return_value=(people, {})), \
                mock.patch.object(ln, "living", return_value=people), \
                mock.patch("vv_genealogy.load_village", return_value=village):
            self.assertEqual(ln.missing_last_names(Path(tmp), 5, 1), [])


class NotNow(Village):
    def test_not_now_is_not_asked_again_until_another_villager_has_none(self):
        found = ln.missing_last_names(self.folder, 3, 1)
        self.assertTrue(ln.should_ask(self.folder, 3, 1, found))
        ln.write_missing(self.folder, 3, 1, ln.NOT_NOW, [m.villager.identity for m in found])
        self.assertFalse(ln.should_ask(self.folder, 3, 1, found))
        self.assertFalse(ln.should_ask(self.folder, 3, 1, found[:2]), "fewer of them: still not asked")
        newcomer = ln.Missing(ln.Living(0, "Noa", "Male", 9, 1, 1, ""))
        self.assertTrue(ln.should_ask(self.folder, 3, 1, found + [newcomer]), "someone new: asked")

    def test_the_games_request_is_read_and_a_reminder_is_asked(self):
        path = ln.missing_path(self.folder, 3, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"VVFP MISSING LAST NAMES v1 game=3\nasked\tremind\nvillager\tKalea\t4\t4\n")
        self.assertEqual(ln.read_missing(self.folder, 3, 1), (ln.REMIND, {("Kalea", 4, 4)}))
        self.assertEqual(ln.requests(self.folder, 3), [1])
        self.assertTrue(ln.should_ask(self.folder, 3, 1, ln.missing_last_names(self.folder, 3, 1)))
        self.assertTrue(ln.uses_last_names(self.folder, 3, 1), "the game asked: the village uses them")


class Giving(Village):
    def test_the_suggested_names_are_given_everywhere_and_the_request_goes(self):
        ln.write_missing(self.folder, 3, 1, ln.REMIND, [("Kalea", 4, 4)])
        found = ln.missing_last_names(self.folder, 3, 1)
        result = ln.give_missing(self.folder, 3, 1, found, NoGame(), NOW)
        self.assertTrue(Path(result.backup.backup_folder).is_dir(), "the save folder is backed up first")
        names = [v.name for v in ln.living(self.folder, 3, 1)]
        self.assertTrue(all(" " in n for n in names), names)
        births = (self.folder / LOGS / "Births and Conceptions"
                  / "Virtual Villagers 3 Births and Conceptions Log 1.txt").read_bytes().decode()
        kalea = next(n for n in names if n.startswith("Kalea "))
        self.assertIn(f"  Name: {kalea}\r\n", births, "the logs follow")
        self.assertEqual(ln.missing_last_names(self.folder, 3, 1), [])
        self.assertFalse(ln.missing_path(self.folder, 3, 1).exists(), "nobody left: the request goes")

    def test_refused_while_the_game_runs(self):
        found = ln.missing_last_names(self.folder, 3, 1)
        with self.assertRaises(tools.GameRunning):
            ln.give_missing(self.folder, 3, 1, found, Running(), NOW)
        self.assertIn(b"Kalea\0", self.save.read_bytes())


class ArrivalsToggle(Village):
    def test_on_by_default_and_kept_in_the_record_older_builds_read(self):
        self.assertTrue(ln.read_arrivals(self.folder, 3, 1))
        self.record("rule\tfather", "set\tAgo\t5\t6\tAkikai")
        ln.save_arrivals(self.folder, 3, 1, False, NoGame())
        text = ln.record_path(self.folder, 3, 1).read_text(encoding="utf-8")
        self.assertIn("arrivals\tnone\n", text)
        self.assertFalse(ln.read_arrivals(self.folder, 3, 1))
        self.assertEqual(ln.read_record(self.folder, 3, 1), ("father", {("Ago", 5, 6): "Akikai"}),
                         "the rest of the record is kept")
        ln.write_record(self.folder, 3, 1, "mother", {})
        self.assertFalse(ln.read_arrivals(self.folder, 3, 1), "another write keeps the toggle")
        ln.save_arrivals(self.folder, 3, 1, True, NoGame())
        self.assertNotIn("arrivals", ln.record_path(self.folder, 3, 1).read_text(encoding="utf-8"))

    def test_turning_it_off_with_no_record_sets_no_rule(self):
        ln.save_arrivals(self.folder, 3, 1, False, NoGame())
        self.assertEqual(ln.read_record(self.folder, 3, 1), (None, {}))
        self.assertFalse(ln.read_arrivals(self.folder, 3, 1))

    def test_on_an_arrival_gets_a_unique_name_no_one_living_or_dead_has(self):
        found = self.missing()
        kalea = found["Kalea"]
        self.assertTrue(kalea.auto)
        self.assertNotIn(kalea.suggested, {"Akikai", ""}, "Ago has Akikai, and the dead Moa too")
        self.assertEqual(kalea.suggested, self.missing()["Kalea"].suggested, "the same each time")
        self.assertFalse(found["Aipi"].auto, "a founder is not an arrival")
        self.assertFalse(found["Kid"].auto, "babies follow the rules")

    def test_off_nobody_is_named_automatically(self):
        ln.save_arrivals(self.folder, 3, 1, False, NoGame())
        self.assertFalse(any(m.auto for m in ln.missing_last_names(self.folder, 3, 1)))

    def test_the_unique_pick_avoids_the_dead_while_the_list_allows(self):
        checker = tools.load_checker()
        pool = list(checker.LAST_NAMES[3])
        v = ln.Living(0, "Kalea", "Female", 4, 4, 3, pool[2], arrived=True)
        living_lasts = set(pool[:-2])
        self.assertEqual(ln.unique_last_name(3, v, living_lasts, {pool[-1]}), pool[-2])
        self.assertIn(ln.unique_last_name(3, v, living_lasts, set(pool[-2:])), pool[-2:],
                      "every free one has a dead namesake: still none a living villager has")
        self.assertEqual(ln.unique_last_name(3, v, set(pool), set()), "")


class ThePrompt(unittest.TestCase):
    """The patcher's side (src/vv_fun_patcher_gui.py), read from the source."""
    SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def body(self, name: str) -> str:
        start = self.SOURCE.index(f"    def {name}(")
        return self.SOURCE[start:self.SOURCE.index("\n    def ", start + 10)]

    def test_the_three_answers_and_the_directions(self):
        body = self.body("_missing_last_names_prompt")
        for words in ('"Give the suggested names"', '"Choose each…"', '"Not now"', "self._LN_HOW"):
            self.assertIn(words, body)
        how = self.SOURCE[self.SOURCE.index("    _LN_HOW = "):self.SOURCE.index("    def _ask_about_missing_last_names(")]
        for words in ("close the game, choose Repair Saves & \"\n               \"Logs...", "press Repair Saves & Logs",
                      "Give villagers last names, in the game and the logs", "press Choose…", "highlighted",
                      "press OK, then Repair"):
            self.assertIn(words, how)
        self.assertIn("vv_last_names.write_missing(folder, number, slot, vv_last_names.NOT_NOW", body)
        self.assertIn("vv_last_names.give_missing(", body)

    def test_it_asks_only_with_the_automatic_check_on(self):
        self.assertIn("if not self.check_logs_var.get():", self.body("_ask_about_missing_last_names"))
        self.assertIn("self._missing_last_names_at_repair(", self.body("_repair_logs"))
        repair = self.body("_missing_last_names_at_repair")
        self.assertIn("self.check_logs_var.get()", repair)
        self.assertIn("vv_last_names.should_ask(", repair)
        self.assertIn("auto = [m for m in missing if m.auto]", repair, "arrivals are named whatever the setting")

    def test_the_patcher_looks_for_the_games_requests_when_it_opens(self):
        start = self.SOURCE.index("        self.protocol(\"WM_DELETE_WINDOW\", self._close)\n")
        self.assertIn("self.after(", self.SOURCE[start:start + 300])
        self.assertIn("vv_last_names.requests(", self.body("_ask_about_missing_last_names"))

    def test_the_window_highlights_them_and_has_the_arrivals_toggle(self):
        body = self.body("_last_names_dialog")
        self.assertIn('names.get("highlight"', body)
        self.assertIn("Give arriving villagers their own new last name automatically", body)


if __name__ == "__main__":
    unittest.main()
