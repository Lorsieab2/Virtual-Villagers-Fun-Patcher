"""Repair Logs: adding what older records lack (src/vv_log_additions.py).

The owner (2026-10-06): Check Logs and Repair Logs offer to add, retroactively,
the Sex line, the Special villager title, the Custom title, the Mask and Twin /
Triplet to records an older patcher wrote -- from the save, the patcher's files
and the logs, and "IF EVER UNSURE, ASK THE PLAYER".  These tests build small
log folders by hand.
"""
from __future__ import annotations

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
NOW = datetime(2026, 10, 6, 12, 0, 0)


class FakeProcesses:
    def find(self, exe_name):
        return []


def write(folder: Path, relative: str, text: str) -> Path:
    path = folder / LOGS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
    return path


def villager(n: int, name: str, head: int, body: int, extra: str = "", skills=(10, 10, 10, 10, 10)) -> str:
    rows = "".join(f"    {w:<10} {v}\n" for w, v in zip(("Breeding", "Building", "Farming", "Healing", "Research"), skills))
    return (f"Villager {n}\n  Name: {name}\n{extra}  Age: 400\n  Sex: Female\n  Head: {head}\n  Body: {body}\n"
            f"  Likes: (none)\n  Dislikes: (none)\n  Skills:\n{rows}\n")


def snapshot(date: str, *people: str) -> str:
    return f"=== Virtual Villagers 3 -- {date} ===\nVillage: Tribe (Save 1)\n" + "".join(people)


class Planning(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def kinds(self, game=3):
        return {k.id: k for k in additions.plan(self.folder, game, 1)}

    def test_a_custom_title_is_added_from_the_date_the_player_picks(self):
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\n" + villager(1, "Hoani", 11, 2, "  Custom title: Helpful Spirit\n"))
        history = write(self.folder, "Tribe History/Village History 1.txt",
                        snapshot("2026-10-01 10:00", villager(1, "Hoani", 11, 2))
                        + snapshot("2026-10-02 10:00", villager(1, "Hoani", 11, 2))
                        + snapshot("2026-10-03 10:00", villager(1, "Hoani", 11, 2,
                                                                 "  Custom title: Helpful Spirit\n")))
        kind = self.kinds()["custom"]
        self.assertEqual(kind.decided, 0)
        [question] = kind.questions.values()
        self.assertEqual(question.options, ["From 2026-10-01 10:00", "From 2026-10-02 10:00", additions.FROM_NOW])
        self.assertEqual(question.default, additions.FROM_NOW)
        done = additions.apply(self.folder, [kind], {"custom"}, {question.key: "From 2026-10-02 10:00"})
        text = history.read_bytes().decode("latin-1")
        self.assertEqual(text.count("  Custom title: Helpful Spirit\r\n"), 2, "the 2nd snapshot gained it")
        first = text.index("2026-10-01")
        second = text.index("2026-10-02")
        self.assertNotIn("Custom title", text[first:second])
        self.assertIn("  Name: Hoani\r\n  Custom title: Helpful Spirit\r\n  Age: 400", text[second:])
        self.assertEqual([(f.name, f.count) for f in done["custom"]],
                         [(str(history.relative_to(self.folder)), 1)])
        backups = list(history.parent.glob("*.before-v1.35.61-repair*"))
        self.assertEqual(len(backups), 1)
        [again] = self.kinds()["custom"].questions.values()
        self.assertEqual(again.options, ["From 2026-10-01 10:00", additions.FROM_NOW],
                         "only the snapshot still without it is offered")

    def test_the_lines_under_a_name_keep_the_exporters_order(self):
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\n" + villager(1, "Mara", 3, 3, "  Custom title: Seer\n"
                                                      "  Special villager: Tribal Chief\n  Mask: Red Mask\n"))
        history = write(self.folder, "Tribe History/Village History 1.txt",
                        snapshot("2026-10-01 10:00", villager(1, "Mara", 3, 3)))
        kinds = list(self.kinds().values())
        answers = {q.key: q.options[0] for k in kinds for q in k.questions.values()}
        additions.apply(self.folder, kinds, {"custom", "special", "mask"}, answers)
        text = history.read_bytes().decode("latin-1")
        self.assertIn("  Name: Mara\r\n  Custom title: Seer\r\n  Special villager: Tribal Chief\r\n"
                      "  Mask: Red Mask\r\n  Age: 400", text)

    def test_special_titles_the_records_decide(self):
        history = write(self.folder, "Tribe History/Village History 1.txt",
                        snapshot("2026-10-01 10:00", villager(1, "Sage", 1, 1, skills=(88, 90, 88, 10, 0)),
                                 villager(2, "Kid", 2, 2, skills=(88, 88, 10, 10, 0))))
        deaths = write(self.folder, "Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                       "Village: Tribe (Save 1)\nDeath 1\n  Name: Old\n  Age at death: 1400\n"
                       "  Cause of death: Old age\n  Grave: Esteemed Elder\n  Epitaph: Wise\n  Head: 4\n"
                       "  Body: 4\n  Likes: (none)\n  Dislikes: (none)\n\n")
        kind = self.kinds(3)["special"]
        self.assertEqual(kind.decided, 2)
        self.assertEqual(kind.asked, 0)
        additions.apply(self.folder, [kind], {"special"}, {})
        self.assertIn("  Name: Sage\r\n  Special villager: Esteemed Elder\r\n", history.read_bytes().decode())
        self.assertNotIn("  Name: Kid\r\n  Special", history.read_bytes().decode())
        self.assertIn("  Name: Old\r\n  Special villager: Esteemed Elder\r\n", deaths.read_bytes().decode())

    def test_a_title_the_records_cannot_date_is_asked(self):
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\n" + villager(1, "Chief", 5, 5, "  Special villager: Tribal Chief\n"))
        write(self.folder, "Tribe History/Village History 1.txt",
              snapshot("2026-10-01 10:00", villager(1, "Chief", 5, 5, skills=(88, 88, 88, 0, 0))))
        kind = self.kinds(3)["special"]
        self.assertEqual(kind.decided, 0, "skills would say Esteemed Elder; the Chief's title wins and is asked")
        self.assertEqual(kind.asked, 1)

    def test_born_as_from_the_conception_or_asked(self):
        log = write(self.folder, "Births and Conceptions/Virtual Villagers 3 Births and Conceptions Log 1.txt",
                    "Village: Tribe (Save 1)\n"
                    "Conception 1\n  Mother: Ma\n    Head: 1\n    Body: 1\n  Father: Pa\n    Head: 2\n"
                    "    Body: 2\n  Babies in pregnancy: 2\n\n"
                    "Birth\n  Child: A\n    Head: 3\n    Body: 3\n  Mother: Ma\n    Head: 1\n    Body: 1\n"
                    "  Father: Pa\n    Head: 2\n    Body: 2\n\n"
                    "Birth\n  Child: B\n    Head: 3\n    Body: 3\n  Mother: Ma\n    Head: 1\n    Body: 1\n"
                    "  Father: Pa\n    Head: 2\n    Body: 2\n\n"
                    "Birth\n  Child: C\n    Head: 3\n    Body: 3\n  Mother: Lone\n    Head: 7\n    Body: 7\n"
                    "  Father: Pa\n    Head: 2\n    Body: 2\n\n")
        kind = self.kinds(3)["born_as"]
        self.assertEqual(kind.decided, 2, "the conception said 2 and two births follow")
        [question] = kind.questions.values()
        self.assertIn("Lone", question.text)
        additions.apply(self.folder, [kind], {"born_as"}, {question.key: "Triplet"})
        text = log.read_bytes().decode()
        self.assertEqual(text.count("  Born as: Twin\r\n"), 2)
        self.assertIn("  Mother: Lone\r\n    Head: 7\r\n    Body: 7\r\n  Father: Pa\r\n    Head: 2\r\n"
                      "    Body: 2\r\n  Born as: Triplet\r\n", text)

    def test_dont_know_adds_nothing(self):
        write(self.folder, "Births and Conceptions/Virtual Villagers 3 Births and Conceptions Log 1.txt",
              "Village: Tribe (Save 1)\nBirth\n  Child: C\n    Head: 3\n    Body: 3\n  Mother: Lone\n"
              "    Head: 7\n    Body: 7\n  Father: Pa\n    Head: 2\n    Body: 2\n\n")
        kind = self.kinds(3)["born_as"]
        self.assertEqual(additions.apply(self.folder, [kind], {"born_as"}, {}), {})
        [question] = kind.questions.values()
        self.assertEqual(additions.apply(self.folder, [kind], {"born_as"}, {question.key: additions.DONT_KNOW}), {})

    def test_another_slots_village_is_left_alone(self):
        write(self.folder, "Tribe History/Village History 1.txt",
              "=== Virtual Villagers 4 -- 2026-10-01 ===\nVillage: Other (Save 2)\n"
              + villager(1, "Sage", 1, 1, skills=(90, 90, 90, 90, 90)))
        self.assertEqual(self.kinds(4)["special"].decided, 0)

    def test_a_snapshot_from_before_a_change_of_looks_is_found(self):
        # Codex (#553): a Change Appearance alters Head and Body; name, likes and
        # dislikes still find the villager's older snapshots.
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\n" + villager(1, "Hoani", 11, 2, "  Custom title: Helpful Spirit\n"))
        write(self.folder, "Tribe History/Village History 1.txt",
              snapshot("2026-10-01 10:00", villager(1, "Hoani", 4, 7)))
        [question] = self.kinds()["custom"].questions.values()
        self.assertEqual(question.options, ["From 2026-10-01 10:00", additions.FROM_NOW])

    def test_two_current_villagers_alike_leave_old_looks_unmatched(self):
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\n" + villager(1, "Hoani", 11, 2, "  Custom title: Helpful Spirit\n")
              + villager(2, "Hoani", 12, 3))
        write(self.folder, "Tribe History/Village History 1.txt",
              snapshot("2026-10-01 10:00", villager(1, "Hoani", 4, 7)))
        self.assertEqual(self.kinds()["custom"].questions, {})

    def test_an_erased_village_in_the_same_slot_is_left_alone(self):
        # Codex (#553): after Start Over the slot's new village is another tribe; the
        # old one's snapshots keep their own "Village:" header and are not touched.
        save = self.folder / "Virtual Villagers - The Secret City1.ldw"
        save.write_bytes(b"ldwg" + bytes(12))
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\n" + villager(1, "Hoani", 11, 2, "  Custom title: Helpful Spirit\n"))
        write(self.folder, "Tribe History/Village History 1.txt",
              snapshot("2026-09-01 10:00", villager(1, "Hoani", 11, 2)).replace("Village: Tribe", "Village: Gone")
              + "Tribe renamed from Old to Tribe on 2026-09-20\n\n"
              + snapshot("2026-09-21 10:00", villager(1, "Hoani", 11, 2)).replace("Village: Tribe", "Village: Old")
              + snapshot("2026-10-01 10:00", villager(1, "Hoani", 11, 2)))
        import vv_tribe_rename
        from unittest import mock
        with mock.patch.object(vv_tribe_rename, "save_name", return_value="Tribe"):
            self.assertEqual(additions.current_villages(self.folder, 3, 1),
                             {"Village: Tribe (Save 1)", "Village: Old (Save 1)"})
            [question] = self.kinds()["custom"].questions.values()
        self.assertEqual(question.options, ["From 2026-09-21 10:00", "From 2026-10-01 10:00", additions.FROM_NOW])

    def test_repair_logs_applies_what_was_ticked_and_answered(self):
        game_folder = self.folder
        (game_folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(b"ldwg" + bytes(12))
        history = write(game_folder, "Tribe History/Village History 1.txt",
                        snapshot("2026-10-01 10:00", villager(1, "Sage", 1, 1, skills=(88, 90, 88, 10, 0))))
        kinds = additions.plan(game_folder, 3, 1)
        result = tools.approve_repair(game_folder, 3, 1, FakeProcesses(), NOW, chosen={"special"},
                                      answers={}, kinds=kinds, rearm=False)
        self.assertIsNone(result.approval)
        self.assertEqual(result.cleared, [])
        self.assertFalse(tools.approval_path(game_folder, 3, 1).exists(), "not re-armed: no approval")
        self.assertIn("Special villager: Esteemed Elder", history.read_bytes().decode())
        repairs = next((game_folder / LOGS / "Repairs").glob("*.txt")).read_bytes().decode()
        self.assertIn("Special villager added: " + LOGS + "\\Tribe History", repairs)


if __name__ == "__main__":
    unittest.main()
