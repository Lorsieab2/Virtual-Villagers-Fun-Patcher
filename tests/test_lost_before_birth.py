"""Babies lost with their mother: never born, never left unexplained (all five games).

The owner (2026-10-09): "Nursing mothers who die will only produce a grave for the mother
(nursing child just disappears - child villager is never born as a full fledged villager)" and
"Only full fledged villagers produce skeletons and graves".  So:

* the mother's Death or Disappeared record says "Nursing: yes, N babies (never born: lost with
  their mother)" -- the games' own word for the state (the owner, 2026-10-10: "Each game's own word";
  every game's villager screen shows "Nursing"), and the Births and Conceptions log closes her open Conception with a "Lost before
  birth" record (native/vvfp_cause_of_death/cod_lost.inc, run by lost_birth_harness.c in every
  game's geometry; the Parentage Export side by death_log_harness.c);
* the Family Tree and the genealogy treat that Conception as closed (src/vv_genealogy.py);
* Repair Saves & Logs adds both to older records where it can prove the case, and asks the player
  where it cannot (src/vv_log_additions.py plan_lost).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_genealogy as gen  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_tools as tools  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
          r"\14.51.36231\bin\Hostx64\x86\cl.exe")
COD = ROOT / "native" / "vvfp_cause_of_death"


def write(folder: Path, relative: str, text: str) -> Path:
    path = folder / LOGS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
    return path


def conception(n: int, mother: str, head: int, body: int, age: int, babies: int,
               father: str = "Pa", fhead: int = 0, fbody: int = 2) -> str:
    return (f"Conception {n}\n  Mother: {mother}\n    Age at conception: {age}\n    Sex: Female\n"
            f"    Head: {head}\n    Body: {body}\n    Likes: (none)\n    Dislikes: (none)\n"
            f"  Father: {father}\n    Age at conception: 700\n    Sex: Male\n    Head: {fhead}\n"
            f"    Body: {fbody}\n    Likes: (none)\n    Dislikes: (none)\n  Babies in pregnancy: {babies}\n\n")


def birth(child: str, mother: str, head: int, body: int) -> str:
    return (f"Birth\n  Child: {child}\n    Head: 3\n    Body: 3\n  Mother: {mother}\n    Head: {head}\n"
            f"    Body: {body}\n  Father: Pa\n    Head: 0\n    Body: 2\n\n")


def death(n: int, name: str, head: int, body: int, age: int) -> str:
    return (f"Death {n}\n  Name: {name}\n  Age at death: {age}\n  Sex: Female\n  Cause of death: Disease\n"
            f"  Grave: Untrained\n  Epitaph: (none)\n  Head: {head}\n  Body: {body}\n  Likes: (none)\n"
            f"  Dislikes: (none)\n\n")


def disappeared(name: str, head: int, body: int, age: int) -> str:
    return (f"Disappeared\n  Name: {name}\n  Age: {age}\n  Sex: Female\n"
            f"  What happened: Disappeared in a custom island event\n  Head: {head}\n  Body: {body}\n"
            f"  Likes: (none)\n  Dislikes: (none)\n\n")


BIRTHS = "Births and Conceptions/Virtual Villagers {g} Births and Conceptions Log 1.txt"
DEATHS = "Deaths and Disappearances/Virtual Villagers {g} Deaths Log 1.txt"


class NativeHarness(unittest.TestCase):
    @unittest.skipUnless(CL.is_file(), "needs the 32-bit MSVC toolchain")
    def test_every_game_every_departure_path(self):
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(ROOT / "scripts" / "build_lost_birth_harness.ps1")],
            capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-2000:])
        self.assertIn("all passed", result.stdout)
        for game in range(1, 6):
            self.assertIn(f"game {game} death, 3 baby/babies: the Nursing line", result.stdout)
            self.assertIn(f"game {game} disappearance: an unknown father is (unknown)", result.stdout)

    def test_every_death_and_departure_path_goes_through_the_two_writers(self):
        # Every Death record is cod_log_death's and every Disappeared record cod_log_gone's, and both
        # say whether the babies were lost: no site writes either kind itself.  The one exception is
        # New Believers' "Left the tribe: became a Heathen" (cod_arrivals.inc
        # arrival_left_for_the_heathens): she is alive and keeps her pregnancy as a Heathen, so no
        # babies are lost and she must not be reported as departed from the roster.
        allowed = {("LOG_DISAPPEARED", "cod_gone.inc"), ("LOG_DISAPPEARED", "cod_arrivals.inc")}
        for path in COD.glob("cod_*.inc"):
            text = path.read_text(encoding="utf-8")
            for kind in ("LOG_DEATH", "LOG_DISAPPEARED"):
                uses = text.count(f"cod_write({kind}")
                self.assertEqual(uses, 1 if (kind, path.name) in allowed else 0,
                                 f"{path.name} writes {kind} itself")
        arrivals = (COD / "cod_arrivals.inc").read_text(encoding="utf-8")
        self.assertIn("Left the tribe: became a Heathen", arrivals)
        main = (COD / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        self.assertEqual(main.count("cod_write(LOG_DEATH"), 1)
        self.assertIn('lost_record(record, babies, "died")', main)
        self.assertIn('lost_record(record, babies, "disappeared")',
                      (COD / "cod_gone.inc").read_text(encoding="utf-8"))


class TheChecker(unittest.TestCase):
    def test_a_lost_record_is_read_and_closes_nothing_else(self):
        checker = tools.load_checker()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, BIRTHS.format(g=3), "Village: Tribe (Save 1)\n" + conception(1, "Ma", 0, 0, 600, 2)
                  + "Lost before birth\n  Mother: Ma\n    Head: 0\n    Body: 0\n  Father: Pa\n    Head: 0\n"
                    "    Body: 2\n  Babies nursing: 2\n"
                    "  What happened: the mother died while nursing; never born\n\n")
            records, _files = checker.births_log(folder, 3, 1)
            self.assertEqual([r.kind for r in records], ["conception", "lost"])
            lost = records[1]
            self.assertEqual((lost.mother.name, lost.mother.head, lost.mother.body), ("Ma", 0, 0))
            self.assertEqual((lost.father.name, lost.father.head, lost.father.body), ("Pa", 0, 2))
            self.assertEqual(lost.babies, 2)
            self.assertFalse(records.damaged)


class BothWords(unittest.TestCase):
    """The owner, 2026-10-10: "Babies nursing: N" from now on; old logs say "Babies in pregnancy: N",
    and every reader takes both."""

    def test_the_checker_and_repair_read_either_word(self):
        checker = tools.load_checker()
        for words in ("Babies nursing", "Babies in pregnancy"):
            with self.subTest(words=words), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                text = conception(1, "Ma", 0, 0, 600, 2).replace("Babies in pregnancy", words)
                write(folder, BIRTHS.format(g=3), "Village: Tribe (Save 1)\n" + text + birth("A", "Ma", 0, 0)
                      + birth("B", "Ma", 0, 0))
                records, _files = checker.births_log(folder, 3, 1)
                self.assertEqual(records[0].babies, 2)
                self.assertEqual((records[0].father.name, records[0].father.head, records[0].father.body), ("Pa", 0, 2))
                kind = {k.id: k for k in additions.plan(folder, 3, 1)}["born_as"]
                self.assertEqual((kind.decided, kind.asked), (2, 0), "Twin, from the Conception's babies")

    def test_every_writer_uses_the_new_words(self):
        for rel, want in (("native/population_export/population_export.c", '"  Nursing: yes\\n"'),
                          ("native/population_export/population_export.c", '"  Babies nursing: %d\\n"'),
                          ("native/parentage_export/parentage_export.c", '"  Babies nursing: %d\\n"'),
                          ("native/vvfp_cause_of_death/cod_lost.inc", '"  Babies nursing: %d\\n"'),
                          ("native/vvfp_cause_of_death/cod_roster.inc", '"  Nursing: yes, %d %s\\n"')):
            self.assertIn(want, (ROOT / rel).read_text(encoding="utf-8"), rel)
        table = (ROOT / "native/vvfp_island_events/island_event_games.inc").read_text(encoding="utf-8")
        self.assertEqual(table.count('{ "Nursing", '), 5)
        self.assertNotIn('"Pregnant"', table)
        self.assertNotIn('"Babies in pregnancy"', table)
        for rel, old in (("native/statistics_export/statistics_reconcile.inc", '"  Babies in pregnancy: 2"'),
                         ("native/vv1_parentage/vv1_crosscheck.inc", '"Babies in pregnancy"')):
            self.assertIn(old, (ROOT / rel).read_text(encoding="utf-8"), f"{rel} still reads old logs")


class TheGenealogy(unittest.TestCase):
    def registry(self, text: str) -> gen._Registry:
        reg = gen._Registry()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write(folder, BIRTHS.format(g=3), "Village: Tribe (Save 1)\n" + text)
            gen._births(reg, folder, 3, 1)
        return reg

    def test_the_conception_is_closed_and_noted(self):
        reg = self.registry(conception(1, "Ma", 0, 0, 600, 3)
                            + "Lost before birth\n  Mother: Ma\n    Head: 0\n    Body: 0\n  Father: Pa\n"
                              "    Head: 0\n    Body: 2\n  Babies nursing: 3\n\n")
        self.assertNotIn(("Ma", 0, 0), reg.conceptions)
        self.assertEqual(reg.lost, [(("Ma", 0, 0), 3)])
        gen._upcoming(reg)
        self.assertFalse(any(p.upcoming for p in reg.people.values()), "no Upcoming child for her")

    def test_an_open_conception_still_has_its_baby_on_the_way(self):
        reg = self.registry(conception(1, "Ma", 0, 0, 600, 1))
        mother = reg.get("Ma", 0, 0)
        mother.alive, mother.expecting = True, True
        gen._upcoming(reg)
        babies = [p for p in reg.people.values() if p.upcoming]
        self.assertEqual(len(babies), 1)
        self.assertEqual(reg.people[babies[0].father].name, "Pa")


class Repair(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def kind(self, game: int) -> additions.Kind:
        return {k.id: k for k in additions.plan(self.folder, game, 1)}["lost"]

    def test_a_proved_case_gets_both_records_and_is_done_once(self):
        births = write(self.folder, BIRTHS.format(g=3), "Village: Tribe (Save 1)\n"
                       + conception(1, "Ma", 0, 0, 600, 2) + conception(2, "Other", 5, 5, 620, 1)
                       + birth("Kid", "Other", 5, 5))
        deaths = write(self.folder, DEATHS.format(g=3), "Village: Tribe (Save 1)\n" + death(1, "Ma", 0, 0, 610))
        kind = self.kind(3)
        self.assertEqual((kind.decided, kind.asked), (2, 0))
        done = additions.apply(self.folder, [kind], {"lost"}, {})
        self.assertEqual(sorted(f.count for f in done["lost"]), [1, 1])
        dtext = deaths.read_bytes().decode("latin-1")
        self.assertIn("  Epitaph: (none)\r\n  Nursing: yes, 2 babies (never born: lost with their mother)\r\n"
                      "  Head: 0\r\n", dtext)
        btext = births.read_bytes().decode("latin-1")
        self.assertIn("  Babies in pregnancy: 2\r\n\r\nLost before birth\r\n  Mother: Ma\r\n    Head: 0\r\n"
                      "    Body: 0\r\n  Father: Pa\r\n    Head: 0\r\n    Body: 2\r\n  Babies nursing: 2\r\n"
                      "  What happened: the mother died while nursing; never born\r\n", btext)
        self.assertLess(btext.index("Lost before birth"), btext.index("Conception 2"),
                        "right after the Conception it closes")
        again = self.kind(3)
        self.assertEqual((again.decided, again.asked), (0, 0), "nothing is added twice")

    def test_a_disappeared_mother_of_twins_in_the_lost_children(self):
        write(self.folder, BIRTHS.format(g=2), "Village: Tribe (Save 1)\n" + conception(1, "Ma", 4, 0, 600, 2))
        deaths = write(self.folder, DEATHS.format(g=2), "Village: Tribe (Save 1)\n" + disappeared("Ma", 4, 0, 600))
        kind = self.kind(2)
        additions.apply(self.folder, [kind], {"lost"}, {})
        self.assertIn("  What happened: Disappeared in a custom island event\r\n"
                      "  Nursing: yes, 2 babies (never born: lost with their mother)\r\n",
                      deaths.read_bytes().decode("latin-1"))

    def test_nothing_when_a_birth_follows_or_she_is_alive_or_gone_before(self):
        write(self.folder, BIRTHS.format(g=4), "Village: Tribe (Save 1)\n"
              + conception(1, "Born", 1, 1, 600, 1) + birth("Kid", "Born", 1, 1)
              + conception(2, "Alive", 2, 2, 600, 1) + conception(3, "Early", 3, 3, 600, 1))
        write(self.folder, DEATHS.format(g=4), "Village: Tribe (Save 1)\n" + death(1, "Born", 1, 1, 620)
              + death(2, "Alive", 2, 2, 610) + death(3, "Early", 3, 3, 500))
        write(self.folder, "Tribe Population/Village Population 1.txt",
              "Village: Tribe (Save 1)\nVillager 1\n  Name: Alive\n  Age: 650\n  Sex: Female\n  Head: 2\n"
              "  Body: 2\n  Likes: (none)\n  Dislikes: (none)\n\n")
        kind = self.kind(4)
        self.assertEqual((kind.decided, kind.asked), (0, 0))

    def test_past_the_delivery_or_two_records_is_asked(self):
        write(self.folder, BIRTHS.format(g=5), "Village: Tribe (Save 1)\n"
              + conception(1, "Late", 1, 1, 600, 1) + conception(2, "Twice", 2, 2, 600, 3))
        deaths = write(self.folder, DEATHS.format(g=5), "Village: Tribe (Save 1)\n" + death(1, "Late", 1, 1, 700)
                       + death(2, "Twice", 2, 2, 610) + death(3, "Twice", 2, 2, 630))
        kind = self.kind(5)
        self.assertEqual((kind.decided, kind.asked), (0, 2))
        self.assertEqual(additions.apply(self.folder, [kind], {"lost"},
                                         {k: additions.DONT_KNOW for k in kind.questions}), {})
        late = next(q for q in kind.questions.values() if q.text.startswith("Late"))
        twice = next(q for q in kind.questions.values() if q.text.startswith("Twice"))
        self.assertIn("after the baby was due", late.text)
        self.assertEqual(len(twice.options), 3, "each of her two records, or don't know")
        additions.apply(self.folder, [kind], {"lost"}, {late.key: late.options[0], twice.key: twice.options[1]})
        text = deaths.read_bytes().decode("latin-1")
        self.assertIn("  Age at death: 700\r\n", text)
        self.assertEqual(text.count("Nursing: yes"), 2)
        self.assertIn("Death 3\r\n  Name: Twice\r\n  Age at death: 630\r\n  Sex: Female\r\n  Cause of death: Disease\r\n"
                      "  Grave: Untrained\r\n  Epitaph: (none)\r\n  Nursing: yes, 3 babies", text,
                      "the record the player chose")

    def test_a_new_home_golden_child_makes_it_a_question(self):
        write(self.folder, BIRTHS.format(g=1), "Village: Tribe (Save 1)\n" + conception(1, "Ma", 0, 0, 600, 1)
              + "Arrived 1\n  Name: Lulu\n  Special villager: Golden Child\n  Head: 1\n  Body: 1\n\n")
        write(self.folder, DEATHS.format(g=1), "Village: Tribe (Save 1)\n" + death(1, "Ma", 0, 0, 610))
        kind = self.kind(1)
        self.assertEqual((kind.decided, kind.asked), (0, 1))


if __name__ == "__main__":
    unittest.main()
