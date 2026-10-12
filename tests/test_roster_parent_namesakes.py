"""A New Home's Villagers at Last Save roster (VCR1 version 3) keeps each villager's father and mother
by NAME alone.  A rename that reaches only one of two living namesakes must leave that name alone: the
parent could be either.  (_plan_vv1_parentage and the logs already hold to this through `by_name`.)"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import unittest  # noqa: E402

import vv_last_names as ln  # noqa: E402
import vv_save_layout as layout  # noqa: E402
from test_lost_titles import DATA, Village, person  # noqa: E402


def roster(father: str, mother: str) -> bytes:
    lo, hi = 0x000, 0x3D8
    record = bytearray(hi - lo)
    record[0x370:0x373] = b"Kid"
    record[0x360:0x368] = struct.pack("<ii", 4, 4)
    entry = struct.pack("<HHBBHQ", 0, 0, 0, 0, 0, 0) + bytes(record)
    entry += father.encode().ljust(32, b"\0") + mother.encode().ljust(32, b"\0")
    return struct.pack("<4sIIIIIII", b"VCR1", 3, 1, 1, lo, hi, 0, 0) + entry


class RosterParentsKeptByName(unittest.TestCase):
    def father_after(self, people, renames, deaths: str = ""):
        v = Village(self, 1, people, "")
        if deaths:
            v.log("Deaths/Virtual Villagers 1 Deaths Log 1.txt", f"Village: Tribe (Save 1)\n{deaths}")
        path = v.folder / DATA / "Unaccounted Villagers" / "Virtual Villagers 1 Villagers at Last Save - Save 1.dat"
        path.parent.mkdir(parents=True)
        path.write_bytes(roster("Goro", "Aisha"))
        plan = ln.plan_renames(v.folder, 1, 1, renames)
        changed = [c for c in plan.changes if c.path == path]
        data = changed[0].updated if changed else path.read_bytes()
        return data[-64:-32].split(b"\0")[0]

    def test_a_namesake_the_rename_does_not_reach_keeps_the_parent_name(self):
        father = self.father_after([person("Goro", 7, 2, male=True), person("Goro", 8, 8, male=True)],
                                   {("Goro", 7, 2): "Goro 2"})
        self.assertEqual(father, b"Goro", "two living Goros: the parent could be either, so it is left")

    def test_a_dead_namesake_keeps_the_parent_name(self):
        father = self.father_after([person("Goro", 7, 2, male=True)], {("Goro", 7, 2): "Goro Bahati"},
                                   "Death 1\n  Name: Goro\n  Age at death: 1400\n  Head: 1\n  Body: 1\n\n")
        self.assertEqual(father, b"Goro", "a dead Goro may be the parent: it is left")

    def test_the_only_goro_takes_the_new_name(self):
        father = self.father_after([person("Goro", 7, 2, male=True)], {("Goro", 7, 2): "Goro Bahati"})
        self.assertEqual(father, b"Goro Bahati")


if __name__ == "__main__":
    unittest.main()
