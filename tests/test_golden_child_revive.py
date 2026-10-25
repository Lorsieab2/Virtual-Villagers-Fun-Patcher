"""Repair Saves & Logs: bring A New Home's Golden Child back (src/vv_golden_child_revive.py).

The owner (2026-10-24): health above 0, still five, his grave removed, a "returned" record added (the
logs are append-only), and only while his record slot has not been reused.  Each test works on a copy
of the committed fixture save in a temporary folder -- never the owner's saves.
"""
from __future__ import annotations

import gzip
import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_golden_child_revive as gcr  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "rename_tribe" / "vv1-huttest-1.ldw.gz"
NOW = datetime(2026, 10, 25, 12, 0, 0)


class NoGame:
    def find(self, exe_name):
        return []


class Running:
    def find(self, exe_name):
        return [1]


def rel(i: int, offset: int) -> int:
    return 0x184 + i * 0x9C + offset - 0x33C


def i32(data, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def base() -> bytearray:
    return bytearray(gzip.decompress(FIXTURE.read_bytes()))


def loaded(data) -> int:
    n = 0
    while data[rel(n, 0x3D4)] == 1:
        n += 1
    return n


def golden(data: bytearray, i: int, health: int, name: bytes = b"Lulu") -> bytearray:
    data[gcr.GOLDEN_BYTE] = 1
    struct.pack_into("<i", data, rel(i, 0x36C), 199)
    struct.pack_into("<i", data, rel(i, 0x344), health)
    struct.pack_into("<i", data, rel(i, 0x350), 1)
    struct.pack_into("<ii", data, rel(i, 0x360), 19, 19)
    data[rel(i, 0x370):rel(i, 0x370) + 0x1C] = name.ljust(0x1C, b"\0")
    return data


def grave(data: bytearray, place: int, name: bytes, age: int, skill: int = 100) -> int:
    at = gcr.GRAVES + place * gcr.GRAVE_STRIDE
    data[at:at + 0x1C] = name.ljust(0x1C, b"\0")
    struct.pack_into("<i", data, at + 0x1C, skill)
    struct.pack_into("<i", data, at + 0x24, age)
    return at


class Survey(unittest.TestCase):
    def test_the_fixture_has_none(self):
        self.assertEqual(gcr.survey_bytes(bytes(base())).state, "none")

    def test_alive_body_gone_and_reused(self):
        data = golden(base(), 1, 100)
        found = gcr.survey_bytes(bytes(data))
        self.assertEqual((found.state, found.index, found.name, found.revivable), ("alive", 1, "Lulu", False))
        data = golden(base(), 1, 0)
        self.assertEqual(gcr.survey_bytes(bytes(data)).state, "body")
        data = golden(base(), 1, -12)
        self.assertEqual(gcr.survey_bytes(bytes(data)).state, "body")
        # Gone: his record left as the stale copy at the gap, nothing written over it.
        data = base()
        n = loaded(data)
        data = golden(data, n, 0)
        found = gcr.survey_bytes(bytes(data))
        self.assertEqual((found.state, found.index), ("gone", n))
        # Reused: the village had him, but no record of his is where the game would load it.
        data = base()
        data[gcr.GOLDEN_BYTE] = 1
        self.assertEqual(gcr.survey_bytes(bytes(data)).state, "reused")
        data = golden(base(), loaded(base()) + 3, 0)       # a deeper stale copy: never loaded, not his slot
        self.assertEqual(gcr.survey_bytes(bytes(data)).state, "reused")

    def gone(self) -> bytearray:
        data = base()
        return golden(data, loaded(data), 0)

    def test_his_grave_is_his_name_at_age_five_with_skill_100(self):
        data = self.gone()
        grave(data, 0, b"Lulu", 400)                     # a namesake adult
        grave(data, 1, b"Lulu", 100, skill=6)            # a namesake child of five (Codex, #625)
        his = grave(data, 2, b"Lulu", 100)
        grave(data, 3, b"Kai", 100)
        self.assertEqual(gcr.survey_bytes(bytes(data)).graves, (his,))

    def test_a_namesake_grave_alone_or_two_candidates_are_never_touched(self):
        data = self.gone()                               # vanished: no grave of his own
        grave(data, 1, b"Lulu", 100, skill=6)
        self.assertEqual(gcr.survey_bytes(bytes(data)).graves, ())
        grave(data, 2, b"Lulu", 100)
        grave(data, 3, b"Lulu", 100)                     # two that could be his: neither is chosen
        self.assertEqual(gcr.survey_bytes(bytes(data)).graves, ())

    def test_a_body_has_no_grave(self):
        data = golden(base(), 1, 0)
        grave(data, 2, b"Lulu", 100)
        self.assertEqual(gcr.survey_bytes(bytes(data)).graves, ())


class Revive(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.save = self.folder / "Virtual Villagers1.ldw"

    def logs(self, word: str) -> str:
        found = sorted(p for p in self.folder.rglob(f"*{word}*.txt"))
        return "".join(p.read_text(encoding="latin-1") for p in found)

    def test_a_body_is_brought_back_with_the_record_added(self):
        data = golden(base(), 1, 0)
        struct.pack_into("<i", data, rel(1, 0x354), 1)    # sick
        namesake = grave(data, 4, b"Lulu", 100)          # not his: a body is not buried
        self.save.write_bytes(bytes(data))
        before = bytes(data)
        result = gcr.revive(self.folder, 1, processes=NoGame(), now=NOW)
        after = self.save.read_bytes()
        self.assertEqual(result.survey.state, "body")
        self.assertEqual(i32(after, rel(1, 0x344)), 100)
        self.assertEqual((i32(after, rel(1, 0x348)), i32(after, rel(1, 0x34C))), (100, 100))
        self.assertEqual(i32(after, rel(1, 0x354)), 0)
        self.assertEqual(after[namesake:namesake + gcr.GRAVE_STRIDE], before[namesake:namesake + gcr.GRAVE_STRIDE])
        changed = {k for k in range(len(after)) if after[k] != before[k]}
        allowed = set(range(rel(1, 0x344), rel(1, 0x350))) | set(range(rel(1, 0x354), rel(1, 0x358)))
        self.assertLessEqual(changed, allowed)
        self.assertEqual(gcr.survey_bytes(after).state, "alive")
        deaths = self.logs("Deaths Log")
        self.assertIn("Returned to life\n  Name: Lulu\n  Special villager: Golden Child\n  Age: 100 (5 years)\n"
                      "  Sex: Male\n", deaths.replace("\r\n", "\n"))
        self.assertNotIn("his grave was removed", deaths)
        self.assertIn("Revived: Lulu, the Golden Child", self.logs("Repairs Log"))
        copies = list(self.folder.rglob("*" + gcr.COPY_SUFFIX))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), before)

    def test_gone_is_made_present_again(self):
        data = base()
        n = loaded(data)
        data = golden(data, n, 0)
        data[rel(n + 1, 0x3D4)] = 1                     # a stale copy after him still flagged present
        his = grave(data, 5, b"Lulu", 100)               # buried: his grave (his name, five, skill 100)
        self.save.write_bytes(bytes(data))
        gcr.revive(self.folder, 1, processes=NoGame(), now=NOW)
        after = self.save.read_bytes()
        self.assertEqual(after[rel(n, 0x3D4)], 1)
        self.assertEqual(loaded(after), n + 1)           # only he comes back, no stale copy with him
        self.assertEqual(after[his:his + gcr.GRAVE_STRIDE], bytes(gcr.GRAVE_STRIDE))
        self.assertIn("his grave was removed", self.logs("Deaths Log"))
        self.assertEqual(i32(after, rel(n, 0x344)), 100)

    def test_refused_while_running_alive_or_reused(self):
        data = golden(base(), 1, 0)
        self.save.write_bytes(bytes(data))
        with self.assertRaises(Exception):
            gcr.revive(self.folder, 1, processes=Running(), now=NOW)
        self.assertEqual(self.save.read_bytes(), bytes(data))
        for data in (golden(base(), 1, 50), bytearray(base())):
            if data is not None and gcr.survey_bytes(bytes(data)).state == "none":
                data[gcr.GOLDEN_BYTE] = 1                  # reused
            self.save.write_bytes(bytes(data))
            with self.assertRaises(gcr.ReviveError):
                gcr.revive(self.folder, 1, processes=NoGame(), now=NOW)
            self.assertEqual(self.save.read_bytes(), bytes(data))


if __name__ == "__main__":
    unittest.main()
