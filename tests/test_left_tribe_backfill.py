"""Repair Saves & Logs: "Left the tribe" records New Believers never wrote (src/vv_log_additions.py
plan_left_tribe).

Builds before v1.35.66 wrote a believer's "Disappeared ... Left the tribe: became a Heathen" record
only when the companion's tick saw the change, so a believer whose faith reached 0 while the game
caught up on time away (or a Time Warp) left with none (native/vvfp_cause_of_death/cod_arrivals.inc
vv5_faction_set now writes it as it happens).  Repair adds the missing record from the village's
own records: a Heathen on the latest Village Population page whom the logs show coming as a believer
(or converted back) more often than leaving.  When she left is not known, so the age is
"(unknown)"; anything the records cannot settle is asked, and "Don't know" adds nothing.
"""
from __future__ import annotations

import gzip
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_additions as additions  # noqa: E402
import vv_log_tools as tools  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
NOW = datetime(2026, 10, 10, 21, 0, 0)
PAGE = "Tribe Population/Village Population 1.txt"
BIRTHS = "Births and Conceptions/Virtual Villagers 5 Births and Conceptions Log 1.txt"
DEATHS = "Deaths and Disappearances/Virtual Villagers 5 Deaths Log 1.txt"
LEFT = "Left the tribe: became a Heathen"


class FakeProcesses:
    def find(self, exe_name):
        return []


def write(folder: Path, relative: str, text: str) -> Path:
    path = folder / LOGS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
    return path


def person(n: int, name: str, head: int, body: int, faction: str, sex: str = "Female") -> str:
    return (f"Villager {n}\n  Name: {name}\n  Age: 640\n  Sex: {sex}\n  Faction: {faction}\n  Head: {head}\n"
            f"  Body: {body}\n  Likes: Fish\n  Dislikes: Rain\n  Skills:\n    Breeding   10\n\n")


def arrived(n: int, name: str, head: int, body: int, how: str) -> str:
    return (f"Arrived {n}\n  Name: {name}\n  Age at arrival: 400\n  Sex: Female\n  Head: {head}\n  Body: {body}\n"
            f"  How: {how}\n\n")


def left(name: str, head: int, body: int) -> str:
    return (f"Disappeared\n  Name: {name}\n  Age: 700\n  Sex: Female\n  What happened: {LEFT}\n  Head: {head}\n"
            f"  Body: {body}\n  Likes: Fish\n  Dislikes: Rain\n\n")


def death(n: int, name: str, head: int, body: int) -> str:
    return (f"Death {n}\n  Name: {name}\n  Age at death: 900\n  Sex: Male\n  Cause of death: Old age\n"
            f"  Grave: Master Farmer\n  Epitaph: Child of the Earth\n  Head: {head}\n  Body: {body}\n"
            "  Likes: Fish\n  Dislikes: Rain\n\n")


def backfilled(name: str, head: int, body: int) -> str:
    """The record Repair adds, as the companion's own (WriteVillageRecord, detail 1) with its age
    unknown and the note."""
    return (f"Disappeared\r\n  Name: {name}\r\n  Age: (unknown)\r\n  Sex: Female\r\n  What happened: {LEFT}\r\n"
            f"  Head: {head}\r\n  Body: {body}\r\n  Likes: Fish\r\n  Dislikes: Rain\r\n{additions.LEFT_NOTE}\r\n")


class LeftTheTribe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        # A real New Believers save (the Rename Tribe fixtures): the readers Check Logs runs need one.
        checker = tools.load_checker()
        save = ROOT / "tests" / "fixtures" / "rename_tribe" / "vv5-huttest-1.ldw.gz"
        (self.folder / f"{checker.SAVE_STEMS[5]}1.ldw").write_bytes(gzip.decompress(save.read_bytes()))

    def tearDown(self):
        self.tmp.cleanup()

    def kind(self, game: int = 5) -> additions.Kind:
        return next(k for k in additions.plan(self.folder, game, 1) if k.id == "left_tribe")

    def village(self, page: str, births: str, deaths: str) -> Path:
        write(self.folder, PAGE, "Village: Kalahuna Tribe 5 (Save 1)\n" + page)
        write(self.folder, BIRTHS, "Village: Kalahuna Tribe 5 (Save 1)\n" + births)
        return write(self.folder, DEATHS, "Village: Kalahuna Tribe 5 (Save 1)\n" + deaths)

    def test_a_founder_who_left_unseen_gets_the_record_once_through_repair(self):
        deaths = self.village(person(1, "Leaf", 3, 4, "Heathen") + person(2, "Stay", 5, 6, "Believer")
                              + person(3, "Pagan", 7, 8, "Heathen"),
                              arrived(1, "Leaf", 3, 4, "Founder") + arrived(2, "Stay", 5, 6, "Founder"),
                              death(1, "Old", 9, 9))
        kind = self.kind()
        self.assertEqual((kind.decided, kind.asked), (1, 0), "Pagan never was a believer: nothing")
        self.assertIn("\"Left the tribe\" records", tools.check_logs(self.folder, 1, 5).text,
                      "Check Logs reports it as something Repair can add")
        raw = deaths.read_bytes()
        checker = tools.load_checker()
        words = self.folder / checker.LOG_WORDS.format(game=5)
        words.parent.mkdir(parents=True, exist_ok=True)
        key = checker.word_key(str(deaths.relative_to(self.folder)))
        # The whole file as an older build wrote it: its boundary is its end.
        words.write_bytes(f"{len(raw)}\t{key}\r\n".encode("utf-8"))
        result = tools.approve_repair(self.folder, 5, 1, FakeProcesses(), NOW, chosen={"left_tribe"}, answers={},
                                      kinds=additions.plan(self.folder, 5, 1), rearm=False)
        after = deaths.read_bytes()
        self.assertEqual(after, raw + backfilled("Leaf", 3, 4).encode("latin-1") + b"\r\n",
                         "appended after the last record's blank line, with a blank line of its own")
        fix = result.added["left_tribe"][0]
        self.assertEqual(fix.count, 1)
        copy = tools.copy_before_repair(self.folder, deaths, "").with_name(fix.backup)
        self.assertEqual(copy.read_bytes(), raw, "copied first, into Copies Made Before Repairs")
        self.assertEqual(checker.word_boundaries(self.folder, 5)[key.lower()], len(raw),
                         "every byte before it is old; the added record, in the game's own words, is after it")
        repairs = next((self.folder / LOGS).rglob("Virtual Villagers 5 Repairs Log 1.txt")).read_text("latin-1")
        self.assertIn("Left the tribe record added", repairs)
        again = self.kind()
        self.assertEqual((again.decided, again.asked), (0, 0), "done once")

    def test_each_time_back_as_a_believer_needs_its_leaving(self):
        deaths = self.village(person(1, "Twice", 3, 4, "Heathen"),
                              arrived(1, "Twice", 3, 4, "Founder")
                              + arrived(2, "Twice", 3, 4, additions.CONVERTED),
                              left("Twice", 3, 4))
        kind = self.kind()
        self.assertEqual((kind.decided, kind.asked), (1, 0), "came, left (recorded), converted, left (not)")
        additions.apply(self.folder, [kind], {"left_tribe"}, {})
        self.assertEqual(deaths.read_bytes().count(LEFT.encode()), 2)

    def test_a_heathen_born_one_and_one_already_recorded_need_nothing(self):
        self.village(person(1, "Born", 3, 4, "Heathen") + person(2, "Done", 5, 6, "Heathen"),
                     "Birth 1\n  Child: Born\n    Head: 3\n    Body: 4\n  Mother: Ma\n    Head: 1\n    Body: 1\n\n"
                     + arrived(1, "Done", 5, 6, "Founder"),
                     left("Done", 5, 6))
        kind = self.kind()
        self.assertEqual(len(kind.inserts), 1, "the child born a believer is decided")
        self.assertIn("Name: Born", kind.inserts[0].line)

    def test_two_missing_or_a_namesake_or_a_double_is_asked_and_dont_know_adds_nothing(self):
        deaths = self.village(person(1, "Many", 1, 1, "Heathen") + person(2, "Ghost", 2, 2, "Heathen")
                              + person(3, "Dup", 3, 3, "Heathen") + person(4, "Dup", 3, 3, "Believer"),
                              arrived(1, "Many", 1, 1, "Founder") + arrived(2, "Many", 1, 1, additions.CONVERTED)
                              + arrived(3, "Ghost", 2, 2, "Founder") + arrived(4, "Dup", 3, 3, "Founder"),
                              death(1, "Ghost", 2, 2))
        kind = self.kind()
        self.assertEqual((kind.decided, kind.asked), (0, 3))
        texts = {q.text.split(" (")[0]: q for q in kind.questions.values()}
        self.assertIn("the logs miss 2 leavings", texts["Many"].text)
        self.assertIn("a Death or Disappeared record has the same name", texts["Ghost"].text)
        self.assertIn("another villager now has the same name", texts["Dup"].text)
        for q in kind.questions.values():
            self.assertEqual((q.options, q.default), ([additions.LEFT_YES, additions.DONT_KNOW], additions.DONT_KNOW))
        raw = deaths.read_bytes()
        self.assertEqual(additions.apply(self.folder, [kind], {"left_tribe"}, {}), {})
        self.assertEqual(deaths.read_bytes(), raw, "Don't know adds nothing")
        additions.apply(self.folder, [kind], {"left_tribe"}, {texts["Many"].key: additions.LEFT_YES})
        self.assertEqual(deaths.read_bytes().count(b"  Name: Many\r\n  Age: (unknown)"), 2)

    def test_under_another_villages_last_record_it_names_its_village(self):
        write(self.folder, PAGE, "Village: Kalahuna Tribe 5 (Save 1)\n" + person(1, "Leaf", 3, 4, "Heathen"))
        write(self.folder, BIRTHS, "Village: Kalahuna Tribe 5 (Save 1)\n" + arrived(1, "Leaf", 3, 4, "Founder"))
        deaths = write(self.folder, DEATHS, "Village: Kalahuna Tribe 5 (Save 1)\n" + death(1, "Old", 9, 9)
                       + "Village: Other (Save 2)\n" + death(1, "Far", 8, 8))
        kind = self.kind()
        additions.apply(self.folder, [kind], {"left_tribe"}, {})
        text = deaths.read_bytes().decode("latin-1")
        self.assertTrue(text.endswith("\r\nVillage: Kalahuna Tribe 5 (Save 1)\r\n" + backfilled("Leaf", 3, 4) + "\r\n"))
        mine = [b for b in additions.blocks(deaths) if b.of(1, 5) and b.heading == "Disappeared"]
        self.assertEqual([b.value("Name") for b in mine], ["Leaf"], "read back under its own village")

    def test_only_new_believers_and_only_with_a_deaths_log(self):
        write(self.folder, PAGE, "Village: Kalahuna Tribe 5 (Save 1)\n" + person(1, "Leaf", 3, 4, "Heathen"))
        write(self.folder, BIRTHS, "Village: Kalahuna Tribe 5 (Save 1)\n" + arrived(1, "Leaf", 3, 4, "Founder"))
        self.assertEqual(self.kind().inserts, [], "no Deaths log yet: nothing to add to")
        self.assertEqual(self.kind(3).inserts, [])

    def test_the_readers_take_the_added_record(self):
        self.village(person(1, "Leaf", 3, 4, "Heathen"), arrived(1, "Leaf", 3, 4, "Founder"), death(1, "Old", 9, 9))
        before = tools.check_logs(self.folder, 1, 5).text
        additions.apply(self.folder, [self.kind()], {"left_tribe"}, {})
        after = tools.check_logs(self.folder, 1, 5).text
        self.assertNotIn("\"Left the tribe\" records", after)
        self.assertEqual([line for line in after.splitlines() if "Left the tribe" not in line and line not in before],
                         [], "nothing new is reported about the added record")
        import vv_genealogy as gen
        village = gen.load_village(self.folder, 5, 1)
        leaf = [p for p in village.people.values() if p.name == "Leaf"]
        # (Alive or gone the tree takes from the save, which here is another village's: Leaf is only
        # in the logs, so it reads her record as it reads one the companion writes.)
        self.assertTrue(leaf, "the family tree reads the village with the added record, its age unknown")


if __name__ == "__main__":
    unittest.main()
