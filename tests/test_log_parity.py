"""Five-game log parity (docs/log-parity-matrix.md).

The owner (2026-10-09): "VV1-5 will have at a minimum the same information in all of its logs UNLESS
A SPECIFIC GAME LACKS THAT FEATURE."  The gaps closed here, each proven by a native harness that fails
against the build before the fix:

* A New Home's Unaccounted and Arrived records name the villager's own parents, as The Lost Children
  to New Believers print them from the record (native/vvfp_cause_of_death/arrival_harness.c
  parents_cases; the roster file keeps A New Home's parents' names, version 3);
* the Deaths log's numbering when an older build's "Deaths" folder sits beside "Deaths and
  Disappearances" (native/parentage_export/death_log_harness.c case 9b);
* the Repairs log's numbering after an older build's "Repairs" folder, in every game's repairs
  (native/shared/repairs_log.h, as A New Home's parentage repair already did).
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_last_names as ln  # noqa: E402
import vv_save_layout as layout  # noqa: E402

COD = ROOT / "native" / "vvfp_cause_of_death"


class Vv1RosterParents(unittest.TestCase):
    def roster(self, version: int, father: str, mother: str) -> bytes:
        lo, hi = 0x000, 0x3D8                       # A New Home's snapshot (cod REC[1])
        record = bytearray(hi - lo)
        record[0x370:0x370 + 3] = b"Kid"
        record[0x360:0x368] = struct.pack("<ii", 4, 4)
        entry = struct.pack("<HHBBHQ", 0, 0, 0, 0, 0, 0) + bytes(record)
        if version == 3:
            entry += father.encode().ljust(32, b"\0") + mother.encode().ljust(32, b"\0")
        return struct.pack("<4sIIIIIII", b"VCR1", version, 1, 1, lo, hi, 0, 0) + entry

    def plan(self, data: bytes, renames: dict) -> ln.Plan:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            sub = folder / layout.DATA / "Unaccounted Villagers"
            sub.mkdir(parents=True)
            (sub / "Virtual Villagers 1 Villagers at Last Save - Save 1.dat").write_bytes(data)
            plan = ln.Plan(renames=renames)
            ln._plan_unaccounted(plan, 1, 1, folder / layout.DATA, renames, {})
            return plan

    def test_a_given_last_name_reaches_the_parents_kept_in_the_roster(self):
        plan = self.plan(self.roster(3, "Goro", "Aisha"), {("Goro", 7, 2): "Goro Bahati"})
        self.assertEqual(len(plan.changes), 1, plan.notes)
        updated = plan.changes[0].updated
        tail = updated[-64:]
        self.assertEqual(tail[:32].split(b"\0")[0], b"Goro Bahati")
        self.assertEqual(tail[32:].split(b"\0")[0], b"Aisha")

    def test_a_version_2_roster_is_still_read(self):
        plan = self.plan(self.roster(2, "", ""), {("Kid", 4, 4): "Kid Bahati"})
        self.assertEqual(len(plan.changes), 1, plan.notes)

    def test_the_companion_writes_version_3_only_for_a_new_home(self):
        source = (COD / "cod_roster.inc").read_text(encoding="utf-8")
        self.assertIn("return g_game == 1 ? ROSTER_VERSION_VV1 : ROSTER_VERSION;", source)
        self.assertIn('wsprintfA(out, "  Parents:\\n    Father: %.31s\\n    Mother: %.31s\\n",', source)
        arrivals = (COD / "cod_arrivals.inc").read_text(encoding="utf-8")
        self.assertIn('wsprintfA(after, "%s  How: %s\\n%s", own, arrivals[index].how, arrivals[index].parents);',
                      arrivals)


if __name__ == "__main__":
    unittest.main()
