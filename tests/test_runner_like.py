"""Family Tree Maker: "Runner" for villagers who like running (the owner, 2026-10-10).  The like id 38 is
"running" in all five games' preference lists; the living are read from their save, the dead from their logs."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import grant_running  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_last_names as ln  # noqa: E402
from test_last_names_rename import TABLE, entry  # noqa: E402


def preference_lists():
    text = (ROOT / "native" / "population_export" / "population_export.c").read_text(encoding="latin-1")
    out = {}
    for name in ("PREFERENCES_47", "PREFERENCES_62", "PREFERENCES_79_VV3", "PREFERENCES_79"):
        body = text.split(f"static const char {name}[] =", 1)[1].split(";", 1)[0]
        out[name] = "".join(part.strip().strip('"') for part in body.splitlines()).split(",")
    return out


class TheLikeIdTests(unittest.TestCase):
    def test_running_is_id_38_in_every_games_list(self):
        self.assertEqual(gen.RUNNING, grant_running.RUNNING)
        for name, words in preference_lists().items():
            self.assertEqual(words[gen.RUNNING], "running", name)


class ReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, *people):
        (self.folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            b"ldwg" + bytes(TABLE - 4) + b"".join(people) + bytes(64))

    def test_a_living_villager_who_likes_running_is_a_runner(self):
        self.save(entry("Ago", 0, 1, 7, 8, likes=(1, 38, 3)), entry("Aipi", 1, 1, 2, 2, likes=(1, 2, 3)),
                  entry("Kai", 0, 1, 4, 4, dislikes=(38, 5, 6)))      # disliking running is no like
        v = gen.load_village(self.folder, 3, 1)
        runners = {p.name: p.runner for p in v.known()}
        self.assertEqual(runners, {"Ago": True, "Aipi": False, "Kai": False})

    def test_a_dead_villagers_logs_say(self):
        self.save(entry("Aipi", 1, 1, 2, 2))
        block = SimpleNamespace(identity=("Ghali", 5, 6), heading="Death", date=None, lines=[], path=Path("x"),
                                value=lambda key: {"Likes": "ants, Running", "Sex": "Male"}.get(key))
        with mock.patch("vv_log_additions.person_blocks", return_value=[block]):
            v = gen.load_village(self.folder, 3, 1)
        ghali = next(p for p in v.known() if p.name == "Ghali")
        self.assertTrue(ghali.runner and not ghali.alive)
        self.assertFalse(next(p for p in v.known() if p.name == "Aipi").runner)


if __name__ == "__main__":
    unittest.main()
