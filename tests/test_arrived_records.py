""""Arrived" records in the Births and Conceptions log (all five games).

The owner (2026-10-04): every grown villager who joins a village -- an island
event's newcomer, the Custom Island Event's new villagers, the Barrel O'
Babies, ... -- gets an "Arrived" record in the Births and Conceptions log, in
all five games and in one format; villagers already in a village who arrived
before the record existed get one backfilled, but only after the first-load
prompt's Repair, exactly once.

"VVFP Cause of Death.dll" sees the arrivals (cod_arrivals.inc) and "VVFP
Parentage Export.dll" files the records (KIND_ARRIVED, arrival_backfill.inc);
native/shared/arrival_backfill.h has the format.
native/vvfp_cause_of_death/arrival_harness.c drives the shipped parentage and
Save Reset DLLs and the TEST build of the Cause of Death DLL in all five
games' geometry; see its header for the cases.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CL = Path(
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
    r"\14.51.36231\bin\Hostx64\x86\cl.exe"
)
BUILD = ROOT / "scripts" / "build_arrival_harness.ps1"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Cause of Death.test.dll"
COD = ROOT / "native" / "vvfp_cause_of_death"
PARENTAGE = ROOT / "native" / "parentage_export"
SHARED = ROOT / "native" / "shared"
# 33 in every game (one: a live arrival in the backfill's session gets exactly
# one record), one more in A New Home (no Show Parents), two more in New
# Believers (the Heathens); then the Birth records' backfill: 3 in A New Home
# (nothing to ask about, nothing written), 16 in each later game.
# 34 in every game since the owner's v1.35.58 live pass (never a founder a
# load put over the startup scan's seeding, nor one with parents), and two
# more where a Story / Cheat Upgrades scope call holds an event's own call
# (A New Home, The Secret City).
CHECKS = 34 * 5 + 1 + 2 + 2 + 3 + 16 * 4 + 9 * 5   # + 9 per game: the quit-time repairs and Start Over's approval
# + 2 in New Believers: another village's believer in a record a Heathen held is no conversion
CHECKS += 2
# + 2 per game with Birth records (The Lost Children on): a born villager's record is never his
# arrived look-alike's (Codex, #536)
CHECKS += 2 * 4
# + 2 per game: the marker names its village, and does not count for another village copied into
# the slot (Codex, #531)
CHECKS += 2 * 5
# New Believers' converted Heathen Master: the Former Heathens file and the Arrived record's title.
CHECKS += 2
# 8 per game: founders seeded before the village has its slot, with and without an empty creation
# save before them (the stale slot; The Tree of Life's and New Believers' early save).
CHECKS += 8 * 5
# + 1 per game: a villager whose Birth record names him by his first name alone (born before Last
# Names, the owner's Cheop Bahati) gets no Arrived record
CHECKS += 5
# + 7 per game: records that keep the name and looks of their day (a last name given since, a look
# changed since; the owner's Cheop Bahati and Hoani Chuchip), arrival_harness.c renamed_cases
CHECKS += 7 * 5
STOCK = ROOT / "research" / "stock-executables"
TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
          5: "New Believers"}
TABLES = {1: "MARKERS_VV1", 2: "MARKERS_VV2", 3: "MARKERS_VV3", 4: "MARKERS_VV4", 5: "MARKERS_VV5"}


def body(source: str, head: str) -> str:
    text = source[source.index(head):]
    return text[:text.index("\n}\n")]


class ArrivedRecordSource(unittest.TestCase):
    def test_the_dlls_export_the_calls(self):
        self.assertIn("RecordArrivalsMissingFromLog=_RecordArrivalsMissingFromLog@24",
                      (PARENTAGE / "parentage_export.def").read_text(encoding="utf-8"))
        for name in ("vvfp_cause_of_death.def", "vvfp_cause_of_death_test.def"):
            text = (COD / name).read_text(encoding="utf-8")
            self.assertIn("VvfpCauseScanArrivals=_VvfpCauseScanArrivals@8", text)
            self.assertIn("VvfpCauseRepairArrivals=_VvfpCauseRepairArrivals@12", text)
            self.assertIn("VvfpCauseArrivedBy=_VvfpCauseArrivedBy@12", text)

    def test_the_record_is_numbered_on_its_own_and_never_rolls(self):
        source = (PARENTAGE / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn("KIND_EPITAPH = 4, KIND_UNACCOUNTED = 5, KIND_ARRIVED = 6", source)
        self.assertIn('fprintf(file, "Arrived %d\\n%s", arrived_before + 1, text)', source)
        numbered = body(source, "static int kind_is_numbered(int kind) {")
        self.assertNotIn("KIND_ARRIVED", numbered)
        self.assertIn('strncmp(line, "Arrived ", 8) == 0', body(source, "static int read_log_header("))

    def test_nothing_is_backfilled_without_repair(self):
        source = (COD / "cod_arrivals.inc").read_text(encoding="utf-8")
        save = body(source, "static void arrival_backfill_at_save(")
        self.assertIn("!arrivals_repair[slot]", save)
        self.assertIn("vv_arrival_marker_present(g_game, slot, cod_marker_village(slot))", save)
        scan = body(source, "VvfpCauseScanArrivals(int game, int slot)")
        self.assertIn("record_arrivals(g_game, NULL, slot, arrival_facts, count, VV_ARRIVAL_COUNT)", scan)
        self.assertNotIn("marker_write", scan)

    def test_the_backfill_runs_at_the_save_before_the_reconciliation(self):
        roster = (COD / "cod_roster.inc").read_text(encoding="utf-8")
        done = body(roster, "static void cod_save_done(")
        self.assertLess(done.index("backfill_at_save(slot, save_buffer);"),
                        done.index("arrival_backfill_at_save(slot, save_buffer);"))
        self.assertLess(done.index("arrival_backfill_at_save(slot, save_buffer);"),
                        done.index("roster_reconcile(slot);"))
        reconcile = body(roster, "static void roster_reconcile(int slot)")
        self.assertLess(reconcile.index("arrival_save(slot, have_previous && kept_count > 0);"),
                        reconcile.index("Arrived with no Birth record or known arrival"))

    def test_a_birth_is_never_an_arrival(self):
        roster = (COD / "cod_roster.inc").read_text(encoding="utf-8")
        self.assertIn("arrival_noted_birth(cod_index_of((const unsigned char *)record));",
                      body(roster, "VvfpCauseNoteArrival(int game, const void *record)"))
        sites = (COD / "cod_arrival_sites.inc").read_text(encoding="utf-8")
        for site in ("0x42EF64u", "0x42EFD5u", "0x42F026u", "0x42F072u", "0x4242FDu", "0x44F602u",
                     "0x45FFD2u", "0x45F2ABu", "0x467D92u", "0x471EA2u", "0x46FDCEu"):
            self.assertIn(f"{site}, ", sites)
        arrivals = (COD / "cod_arrivals.inc").read_text(encoding="utf-8")
        self.assertIn("m->kind == MARK_BIRTH || m->kind == MARK_TEMPORARY", arrivals)
        # Read at fixed places, never searched for (stale locals) -- through
        # the Story / Cheat Upgrades companion where its scope call holds the
        # slot (tests/test_arrival_paths_emulated.py).
        self.assertIn("arrival_slot(regs, m->offset, caller) != m->value", arrivals)
        self.assertIn("caller(regs[R_ESP] + offset)", arrivals)

    def test_founders_only_at_a_first_save(self):
        arrivals = (COD / "cod_arrivals.inc").read_text(encoding="utf-8")
        self.assertIn("(!arrivals[i].founder || !same_village)", body(arrivals, "static void arrival_save("))

    def test_the_custom_island_event_names_its_villagers(self):
        source = (ROOT / "native" / "vvfp_story_upgrades" / "story_custom.inc").read_text(encoding="utf-8")
        self.assertIn('arrived(game, index, "Custom Island Event");', source)
        spawn = source[source.index("int index = a->spawn(s);"):]
        self.assertLess(spawn.index("ce_tell_arrival(e->game, index);"), spawn.index("titles_set"))

    def test_start_over_deletes_the_marker(self):
        source = (SHARED / "save_reset.c").read_text(encoding="utf-8")
        self.assertIn('"%s\\\\Virtual Villagers Fun Patcher Data\\\\Arrivals\\\\Virtual Villagers " n '
                      '" Arrivals Recorded - Save %d.dat"', source)
        for game in "12345":
            self.assertIn(f'ARRIVALS_FORMAT("{game}")', source)
        cod = (COD / "vvfp_cause_of_death.c").read_text(encoding="utf-8")
        self.assertIn("arrival_reset(slot);", body(cod, "VvfpCauseVillageReset(int game, int slot)"))

    def test_the_marker_is_never_written_over_a_file_it_did_not_write(self):
        source = (SHARED / "arrival_backfill.h").read_text(encoding="utf-8")
        write = body(source, "static int vv_backfill_marker_write(int which, int game, int slot, unsigned int village)")
        self.assertIn("GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES", write)
        # Only a marker of ours, for another village, is ever replaced (Codex, #531).
        self.assertIn("if (state == 1) {\n        move |= MOVEFILE_REPLACE_EXISTING;", write.replace("\r\n", "\n"))


def marker_values(game: int) -> list[int]:
    """Every return address in that game's marker table (value and need_value)."""
    source = (COD / "cod_arrival_sites.inc").read_text(encoding="utf-8")
    defines = dict(re.findall(r"#define (VV\d_\w+) (0x[0-9A-F]+u, 0x[0-9A-F]+u)", source))
    table = source[source.index(f"static const struct arrival_marker {TABLES[game]}[] = {{"):]
    table = table[:table.index("};")]
    for name, value in defines.items():
        table = table.replace(name, value)
    values = []
    for row in re.findall(r"\{ (0x[0-9A-F]+u), (0x[0-9A-F]+u), (0x[0-9A-F]+u), (\w+), (\w+),", table):
        values.append(int(row[2].rstrip("u"), 16))
        if row[4] != "0":
            values.append(int(row[4].rstrip("u"), 16))
    seeds = re.findall(rf"VV{game}_SEED\((0x[0-9A-F]+)u\)", table)
    if seeds:
        block = source[source.index(f"#define VV{game}_SEED(l2)"):]
        block = block[:block.index("static const")]
        values += [int(v, 16) for v in re.findall(r"(0x[0-9A-F]+)u, 0x[0-9A-F]+u, \(l2\)", block)]
        values += [int(v, 16) for v in seeds]
    return values


class BirthRecordBackfillSource(unittest.TestCase):
    """The Birth records a village's villagers born before the Births log
    existed are missing, written from each one's own save record after Repair
    (The Lost Children to New Believers; native/shared/arrival_backfill.h)."""

    def test_the_dlls_export_the_calls(self):
        self.assertIn("RecordBirthsMissingFromLog=_RecordBirthsMissingFromLog@24",
                      (PARENTAGE / "parentage_export.def").read_text(encoding="utf-8"))
        for name in ("vvfp_cause_of_death.def", "vvfp_cause_of_death_test.def"):
            text = (COD / name).read_text(encoding="utf-8")
            self.assertIn("VvfpCauseScanBirths=_VvfpCauseScanBirths@8", text)
            self.assertIn("VvfpCauseRepairBirths=_VvfpCauseRepairBirths@12", text)

    def test_nothing_is_written_without_repair_and_only_once(self):
        source = (COD / "cod_arrivals.inc").read_text(encoding="utf-8")
        save = body(source, "static void births_backfill_at_save(")
        self.assertIn("!births_repair[slot]", save)
        self.assertIn("vv_backfill_marker_present(VV_BACKFILL_BIRTHS, g_game, slot, cod_marker_village(slot))", save)
        scan = body(source, "VvfpCauseScanBirths(int game, int slot)")
        self.assertIn("record_births(g_game, NULL, slot, arrival_facts, count, VV_ARRIVAL_COUNT)", scan)
        self.assertNotIn("marker_write", scan)
        roster = (COD / "cod_roster.inc").read_text(encoding="utf-8")
        done = body(roster, "static void cod_save_done(")
        self.assertLess(done.index("births_backfill_at_save(slot, save_buffer);"), done.index("roster_reconcile(slot);"))

    def test_the_record_is_the_birth_record_with_its_note(self):
        source = (PARENTAGE / "arrival_backfill.inc").read_text(encoding="utf-8")
        self.assertIn('"  Note: Recorded afterwards (born before this log existed)\\n"', source)
        self.assertIn("if (births && game_id == GAME_VV1) {", source)
        export = (PARENTAGE / "parentage_export.c").read_text(encoding="utf-8")
        self.assertIn("static int compose_birth(", export)

    def test_start_over_deletes_the_marker(self):
        source = (SHARED / "save_reset.c").read_text(encoding="utf-8")
        self.assertIn('"%s\\\\Virtual Villagers Fun Patcher Data\\\\Births\\\\Virtual Villagers " n '
                      '" Births Recorded - Save %d.dat"', source)
        for game in "2345":
            self.assertIn(f'BIRTHS_FORMAT("{game}")', source)


class ArrivalMarkersAreReturnAddresses(unittest.TestCase):
    """Each marker is read at a fixed place on the stack and must be the
    address right after a call in the stock executable (cod_arrival_sites.inc):
    a `call rel32` (E8) or the event dispatcher's `call [edx+0x2C]` (FF 52 2C)."""

    def test_every_marker_follows_a_call(self):
        import pefile
        for game in range(1, 6):
            exe = STOCK / f"Virtual Villagers - {TITLES[game]}.exe"
            pe = pefile.PE(str(exe))
            values = marker_values(game)
            self.assertGreater(len(values), 5, game)
            for value in values:
                rva = value - pe.OPTIONAL_HEADER.ImageBase
                before = pe.get_data(rva - 5, 5)
                self.assertTrue(before[0] == 0xE8 or before[2:] == bytes([0xFF, 0x52, 0x2C]),
                                f"VV{game} {value:#x} does not follow a call: {before.hex()}")


class ArrivalMarkersHoldInEveryRenderedBuild(unittest.TestCase):
    """...and in the executable the patcher RENDERS, every population mode (and
    The Secret City to New Believers' 256 Villagers builds): a guard that
    called the creator from its own cave left the cave's return address
    there, so A New Home's birth markers (0x42EF64, 0x42EFD5) never matched in
    a patched build and its births were told apart only by the Births log's
    note (the owner's v1.35.58 preview).  Each marker must still follow a call
    there; tests/test_slot_guards_count_records.py runs the guards and checks
    the creator sees exactly that address."""

    def test_every_marker_follows_a_call_in_every_render(self):
        import sys
        import pefile
        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher as vfp
        builds = {b.id: b for b in vfp.load_builds()}
        for game in range(1, 6):
            exe = STOCK / f"Virtual Villagers - {TITLES[game]}.exe"
            if not exe.is_file():
                self.skipTest("no stock executables")
            renders = [(mode, []) for mode in ("stock", "collection_progression", "immediate_fixed")]
            if game >= 3:
                renders.append(("immediate_fixed", [f"vv{game}_population_256"]))
            for mode, features in renders:
                try:
                    data, _ = vfp.render_patched_bytes(exe, builds[f"vv{game}"], mode, features)
                except vfp.PatcherError as error:
                    self.fail(f"VV{game} {mode} {features}: {error}")
                pe = pefile.PE(data=bytes(data))
                for value in marker_values(game):
                    before = pe.get_data(value - pe.OPTIONAL_HEADER.ImageBase - 6, 6)
                    with self.subTest(game=game, mode=mode, features=features, marker=hex(value)):
                        # A call; or a slot guard called from a six-byte
                        # `push ebx; call <copy>` site, which hands the copy
                        # creator the address past its nop -- this one.
                        self.assertTrue(before[1] == 0xE8 or before[3:] == bytes([0xFF, 0x52, 0x2C])
                                        or (before[0] == 0xE8 and before[5] == 0x90),
                                        f"{value:#x} does not follow a call: {before.hex()}")


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
@unittest.skipUnless(TEST_DLL.is_file(), "test builds are not in the release source archive (tests/test_dlls)")
class ArrivedRecordHarness(unittest.TestCase):
    def test_the_harness_passes_in_all_five_games(self):
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
            capture_output=True, text=True, timeout=600,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("== 0 failure(s) ==", result.stdout)
        for game in range(1, 6):
            self.assertIn(f"Virtual Villagers {game}\n", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), CHECKS, result.stdout)


if __name__ == "__main__":
    unittest.main()
