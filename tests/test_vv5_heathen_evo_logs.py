"""Heathen Tribe Expansion and Evolution (New Believers, v1.35.101), W-D: the log exports the workstreams left owed,
and the readers of the new records.

* "VVFP Cause of Death.dll" VvfpCauseHeathenRole(game, index, role): a "Took the role" record (Births and
  Conceptions log) for a Heathen who became the camp's Chief or a Master -- emulated on the stock executable with
  the companion's TEST build (the record handed to the Parentage Export stand-in, as every Cause of Death record).
* "VVFP Parentage Export.dll" WriteParentageHeathenCouple: "Couple formed" -- run for real by
  native/parentage_export/parentage_export_harness.c (scripts/build_parentage_export_harness.ps1, which
  tests/test_harnesses_leave_ldw_as_found.py runs); here its export, kind and heading are pinned.
* "VVFP Story Upgrades.dll" VvfpStorySetCustomTitle: run by native/vvfp_story_upgrades/custom_titles_harness.c
  (tests/test_custom_titles_persistence.py); here its export and its one writer are pinned.
* A Death record backfilled from a grave at the Shrine to the Ancestors carries "Faction: Heathen": run by
  native/vvfp_cause_of_death/grave_backfill_harness.c part 9 (tests/test_grave_backfill.py).
* The readers: the new Arrived words in both wordings, the two new headings, a Heathen's arrival or birth never
  "came as a believer", and a grave at the Shrine to the Ancestors never a village burial.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_isolan_words as words  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_reconcile  # noqa: E402

try:
    from test_cause_of_death import STOCK, TEST_DLL, later
    from test_vv5_mud_hut_graves_logged import guardians
    HAVE = STOCK["vv5"].is_file() and TEST_DLL.is_file()
except Exception:  # pragma: no cover - environment dependent
    HAVE = False

ROLE = 12            # Parentage Export's KIND_ROLE (and Cause of Death's LOG_ROLE)
FACTION = 0x1CEC


@unittest.skipIf(not HAVE, "the stock executable or the Cause of Death test build is missing")
class TookTheRole(unittest.TestCase):
    def took(self, *, heathen: bool = True, role: int = 13, isolan: bool = False) -> list[dict]:
        g, w = later("vv5")
        # The game image for GetModuleHandleA(NULL), as in a game (heathen_word.h reads the string table at the
        # executable's own base); no other companion is loaded.
        g.p.api_handlers["GetModuleHandleA"] = lambda proc: ((0x400000 if proc.arg(0) == 0 else 0), 4)
        if isolan:
            guardians(g.p)
        r = w.villager(3, "Makoa", 900, 80)
        g.p.write(r + FACTION, b"\x01" if heathen else b"\x00")
        g.tick()
        g.p.export("VvfpCauseHeathenRole", 5, 3, role)
        return [e for e in g.of_kind(ROLE) if e["record"] == r]

    def test_a_heathen_who_takes_a_role_gets_a_took_the_role_record(self):
        for role, title in ((13, "Heathen Chief"), (14, "Heathen Master Scientist"), (15, "Heathen Master Builder"),
                            (16, "Heathen Master Farmer")):
            with self.subTest(role=role):
                records = self.took(role=role)
                self.assertEqual(len(records), 1)
                e = records[0]
                self.assertEqual((e["check"], e["detail"]), (1, 1), "the live record, its identity lines")
                self.assertEqual((e["Age"], e["Role"]), ("900", title))
                self.assertIn(e["Sex"], ("Male", "Female"))

    def test_with_guardians_of_isola_the_role_is_named_as_the_rewrite_names_it(self):
        self.assertEqual(self.took(role=13, isolan=True)[0]["Role"], "Chief of the Native Isola Tribe")
        self.assertEqual(self.took(role=16, isolan=True)[0]["Role"], "Esteemed Isolan Farmer")

    def test_a_believer_or_another_role_writes_nothing(self):
        self.assertEqual(self.took(heathen=False), [])
        for role in (0, 12, 17):
            self.assertEqual(self.took(role=role), [], role)


class ExportsPinned(unittest.TestCase):
    def test_the_three_exports_are_in_the_def_files(self):
        for path, line in (
                ("native/vvfp_cause_of_death/vvfp_cause_of_death.def", "VvfpCauseHeathenRole=_VvfpCauseHeathenRole@12"),
                ("native/vvfp_cause_of_death/vvfp_cause_of_death_test.def",
                 "VvfpCauseHeathenRole=_VvfpCauseHeathenRole@12"),
                ("native/parentage_export/parentage_export.def",
                 "WriteParentageHeathenCouple=_WriteParentageHeathenCouple@16"),
                ("native/vvfp_story_upgrades/vvfp_story_upgrades.def",
                 "VvfpStorySetCustomTitle=_VvfpStorySetCustomTitle@12"),
                ("native/vvfp_story_upgrades/vvfp_story_upgrades_test.def",
                 "VvfpStorySetCustomTitle=_VvfpStorySetCustomTitle@12")):
            self.assertIn(line, (ROOT / path).read_text(encoding="utf-8"), path)

    def test_the_names_match_the_shared_header(self):
        header = (ROOT / "native" / "shared" / "heathen_evo.h").read_text(encoding="utf-8")
        for name in ("WriteParentageHeathenCouple", "VvfpCauseHeathenRole", "VvfpStorySetCustomTitle"):
            self.assertIn(f'"{name}"', header)

    def test_the_couple_and_role_records_are_births_log_records_of_their_own(self):
        source = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn("KIND_COUPLE = 11, KIND_ROLE = 12", source)
        self.assertIn('heading = "Took the role\\n";', source)
        couple = source[source.index("WriteParentageHeathenCouple("):]
        couple = couple[:couple.index("\n}\n")]
        self.assertIn('"Couple formed\\n"', couple)
        self.assertIn("return emit_record(game_id, KIND_COUPLE, records, text);", couple)
        self.assertIn("who[k][VV5_FACTION] == 0", couple, "never a believer's")
        # Neither is numbered (a file is counted by its Conception markers) nor held for a save.
        numbered = source[source.index("static int kind_is_numbered(int kind) {"):]
        self.assertNotIn("KIND_COUPLE", numbered[:numbered.index("\n}\n")])
        self.assertNotIn("KIND_ROLE", numbered[:numbered.index("\n}\n")])

    def test_the_title_setter_is_the_files_own_writer(self):
        source = (ROOT / "native" / "vvfp_story_upgrades" / "story_titles.inc").read_text(encoding="utf-8")
        body = source[source.index("VvfpStorySetCustomTitle(int game, int index, const char *title) {"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("titles_set(game, index, title != NULL && title[0] != '\\0' ? title : NULL)", body)

    def test_the_heathens_row_reads_the_new_row_too(self):
        source = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph.inc").read_text(encoding="utf-8")
        self.assertIn('#define CG_HEATHEN_EVOLUTION_ROW "heathen_tribe_evolution"', source)
        row = source[source.index("static int cg_heathens_row(int game) {"):]
        row = row[:row.index("\n}\n")]
        self.assertIn("cg_installed_has(game, CG_HEATHENS_ROW) || cg_installed_has(game, CG_HEATHEN_EVOLUTION_ROW)",
                      row)

    def test_a_shrine_graves_backfilled_record_is_marked_a_heathens(self):
        source = (ROOT / "native" / "parentage_export" / "grave_backfill.inc").read_text(encoding="utf-8")
        self.assertIn("if (game_id == GAME_VV5 && f->place >= VV_GRAVE_SHRINE_FIRST) {", source)
        self.assertIn('"  Faction: %s\\n", vv5_heathen_word()', source)
        self.assertIn("#define VV_GRAVE_SHRINE_FIRST 500",
                      (ROOT / "native" / "shared" / "grave_backfill.h").read_text(encoding="utf-8"))


class ArrivedWords(unittest.TestCase):
    def test_every_arrival_word_in_either_wording_is_a_heathens(self):
        for how in ("Arrived at the Heathen camp", "Arrived at the Isolan camp",
                    "Arrived at the Heathen camp with 1 other", "Arrived at the Heathen camp with 3 others",
                    "Arrived at the Isolan camp with 2 others", "Replaced a Heathen who died of old age",
                    "Replaced an Isolan lost in an island event"):
            self.assertTrue(words.is_heathen_arrival(how), how)
        for how in ("unknown", "Converted from the Heathens", "Converted from the Isolans", "", None,
                    "Arrived at the Heathen camp with 0 others"):
            self.assertFalse(words.is_heathen_arrival(how), how)

    def test_the_isolan_forms_read_as_the_heathen_ones(self):
        self.assertEqual(words.heathen_form("Arrived at the Isolan camp"), "Arrived at the Heathen camp")
        self.assertEqual(words.heathen_form("Arrived at the Isolan camp with 2 others"),
                         "Arrived at the Heathen camp with 2 others")
        self.assertEqual(words.isolan_form("Arrived at the Heathen camp"), "Arrived at the Isolan camp")

    def test_the_words_are_the_companions_own(self):
        header = (ROOT / "native" / "shared" / "heathen_evo.h").read_text(encoding="utf-8")
        for text in ("Arrived at the Heathen camp", "Arrived at the Isolan camp",
                     "Arrived at the Heathen camp with %d other%s", "Arrived at the Isolan camp with %d other%s"):
            self.assertIn(f'"{text}"', header)


def block(text: str) -> additions.Block:
    return additions.Block(Path("x.txt"), 0, text.split("\n"), 1, None, 5, "Village: T (Save 1)")


class NewRecordsRead(unittest.TestCase):
    def test_the_new_headings_are_records(self):
        for heading in ("Couple formed", "Took the role"):
            self.assertTrue(vv_reconcile.RECORD_HEAD.match(heading), heading)

    def test_a_heathens_arrival_never_came_as_a_believer(self):
        heathen = block("Arrived 4\n  Name: Pua\n  Age at arrival: 400\n  Sex: Female\n  Faction: Heathen\n"
                        "  Head: 2\n  Body: 2\n  How: Arrived at the Heathen camp with 1 other")
        self.assertTrue(additions._came_as_heathen(heathen))
        words_only = block("Arrived 5\n  Name: Pua\n  Head: 2\n  Body: 2\n  How: Arrived at the Isolan camp")
        self.assertTrue(additions._came_as_heathen(words_only), "the words alone say so")
        believer = block("Arrived 6\n  Name: Ana\n  Head: 3\n  Body: 3\n  How: unknown")
        converted = block("Arrived 7\n  Name: Ana\n  Head: 3\n  Body: 3\n  How: Converted from the Heathens")
        self.assertFalse(additions._came_as_heathen(believer))
        self.assertFalse(additions._came_as_heathen(converted))

    def test_couple_and_role_records_name_no_villager_as_a_village_record(self):
        couple = block("Couple formed\n  First: Kalani\n    Age: 500\n    Sex: Female\n  Second: Noelani\n"
                       "    Age: 540\n    Sex: Female\n  Faction: Heathen")
        self.assertEqual(couple.identity, (None, None, None))
        self.assertTrue(additions.is_heathen_record(couple))
        role = block("Took the role\n  Name: Makoa\n  Faction: Heathen\n  Age: 900\n  Sex: Male\n"
                     "  Role: Heathen Chief\n  Head: 1\n  Body: 1")
        self.assertTrue(additions.is_heathen_record(role))
        self.assertFalse(additions.ARRIVED_HEADING.match(role.heading))
        self.assertFalse(additions.DISAPPEARED_HEADING.match(role.heading))


spec = importlib.util.spec_from_file_location("vvfp_consistency_check", ROOT / "scripts" / "vvfp_consistency_check.py")
checker = sys.modules.get("vvfp_consistency_check")
if checker is None:
    checker = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = checker
    spec.loader.exec_module(checker)


class ShrineGravesNeverCount(unittest.TestCase):
    """The consistency checker's bound for Villagers Buried counts the village's graves only: a grave at the Shrine
    to the Ancestors is a Heathen's, even in a record with no Faction line."""

    def test_a_shrine_grave_is_not_a_village_burial(self):
        records = [
            "Death 1\n  Name: Mia\n  Age at death: 1000\n  Cause of death: Old age\n  Grave: Master Builder\n",
            "Death 2\n  Name: Hea\n  Age at death: 900\n  Cause of death: Old age\n"
            "  Grave: the Shrine to the Ancestors (Untrained)\n",
            "Death 3\n  Name: Late\n  Age at death: 950\n  Cause of death: Old age\n"
            "  Grave: no grave (the Shrine to the Ancestors was full)\n",
            "Death 4\n  Name: Pua\n  Faction: Heathen\n  Age at death: 800\n  Cause of death: Old age\n"
            "  Grave: the Shrine to the Ancestors (Untrained)\n",
        ]
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "g"
        path = game / "Virtual Villagers Fun Patcher Logs" / "Deaths and Disappearances" / "Virtual Villagers 5 Deaths Log 1.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(("Village: Tribe (Save 1)\r\n" + "".join(r.replace("\n", "\r\n") + "\r\n" for r in records))
                         .encode("latin-1"))
        deaths = checker.check_unaccounted(game, 1, 5, checker.Report())
        self.assertEqual((deaths, checker.LAST_GRAVES), (4, 1), "only Mia's grave is the village's")


if __name__ == "__main__":
    unittest.main()
