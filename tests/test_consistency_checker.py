"""scripts/vvfp_consistency_check.py: the read-only cross-check of a village's logs and data files
against its save, run on fixture saves built here (no file outside the repository is read).

The fixtures model the owner's A New Home case -- two founders died, the save was loaded, and the
pre-v1.35.57 parentage table stayed at its record indices -- and a clean village; and a Secret City
save, to show the later games' packed villager table is read.  Every run must leave every byte and
timestamp of the folder exactly as it found it.
"""
from __future__ import annotations

import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("vvfp_consistency_check", ROOT / "scripts" / "vvfp_consistency_check.py")
checker = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = checker
spec.loader.exec_module(checker)

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"

# name, male, scalar, head, body, couple (1 Kito+Chika, 2 Ghali+Onawa, 0 none)
OWNER = [
    ("Ghali", 1, 45, 6, 1, 0), ("Kito", 1, 19, 0, 18, 0), ("Chika", 0, 39, 19, 17, 0),
    ("Onawa", 0, 50, 16, 2, 0), ("Huata", 0, 36, 11, 9, 0), ("Nishi", 0, 39, 7, 3, 1),
    ("Penyo", 0, 50, 8, 15, 2), ("Goro", 1, 39, 17, 7, 1), ("Hawa", 0, 50, 2, 19, 2),
    ("Lisha", 0, 50, 13, 10, 2), ("Kaimi", 0, 39, 5, 16, 1),
]
SILKO = ("Silko", 1, 77, 22, 5, 0)
BY_NAME = {v[0]: v for v in OWNER + [SILKO]}
PARENTS = {1: ("Kito", "Chika"), 2: ("Ghali", "Onawa")}


def vv1_save(villagers) -> bytes:
    data = bytearray(0x184 + 256 * 0x9C)
    for i, (name, male, scalar, head, body, _) in enumerate(villagers):
        base = 0x184 + i * 0x9C - 0x33C
        struct.pack_into("<i", data, base + 0x350, 1 if male else 2)
        struct.pack_into("<i", data, base + 0x348, 500)
        struct.pack_into("<i", data, base + 0x360, head)
        struct.pack_into("<i", data, base + 0x364, body)
        struct.pack_into("<i", data, base + 0x36C, scalar)
        struct.pack_into("<i", data, base + 0x3D4, 1)
        data[base + 0x370:base + 0x370 + len(name)] = name.encode()
    return bytes(data)


def births_log(villagers) -> str:
    out = ["Village: Kalahuna Tribe 1 (Save 1)"]
    for name, _, _, head, body, couple in villagers:
        if not couple:
            continue
        f, m = (BY_NAME[n] for n in PARENTS[couple])
        out += ["Birth", f"  Child: {name}", f"    Head: {head}", f"    Body: {body}",
                f"  Mother: {m[0]}", f"    Head: {m[3]}", f"    Body: {m[4]}",
                f"  Father: {f[0]}", f"    Head: {f[3]}", f"    Body: {f[4]}", ""]
    return "\n".join(out) + "\n"


def entry_for(couple) -> bytes:
    e = bytearray(92)
    if couple:
        f, m = (BY_NAME[n] for n in PARENTS[couple])
        e[0], e[1], e[2], e[3] = f[3] + 1, f[4] + 1, m[3] + 1, m[4] + 1
        e[8:8 + len(f[0])] = f[0].encode()
        e[36:36 + len(m[0])] = m[0].encode()
    return bytes(e)


def parentage(roster, couples) -> bytes:
    """A VP02 file: `roster` names who holds each record, `couples[i]` the parents at record i."""
    out = bytearray(struct.pack("<III", 0x32305056, 0, 1))
    for i in range(256):
        rec = bytearray(36)
        if i < len(roster):
            name, male, scalar = roster[i][0], roster[i][1], roster[i][2]
            struct.pack_into("<BBxxi", rec, 0, 1 if male else 2, 0, scalar)
            rec[8:8 + len(name)] = name.encode()
        out += rec
    for i in range(256):
        out += entry_for(couples[i] if i < len(couples) else 0)
    return bytes(out)


def snapshot(folder: Path) -> dict:
    return {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.rglob("*") if p.is_file()}


class Vv1Fixture(unittest.TestCase):
    def build(self, drifted: bool) -> Path:
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "Virtual Villagers - A New Home - Modded"
        (game / LOGS / "Births and Conceptions").mkdir(parents=True)
        (game / DATA).mkdir(parents=True)
        before = OWNER
        after = [v for v in OWNER if v[0] not in ("Kito", "Chika")] + [SILKO]
        (game / "Virtual Villagers1.ldw").write_bytes(vv1_save(after))
        (game / LOGS / "Births and Conceptions" / "Virtual Villagers 1 Births and Conceptions Log 1.txt").write_text(
            births_log(OWNER), encoding="latin-1")
        # Drifted: the entries stayed at the indices of the village BEFORE the load, the roster was
        # rebound to the village after it.  In step: each entry is its own villager's.
        couples = [v[5] for v in (before if drifted else after)]
        (game / DATA / "Virtual Villagers 1 Parentage Records - Save 1.dat").write_bytes(parentage(after, couples))
        return game

    def test_the_drifted_table_is_confirmed_wrong_villager_by_villager(self):
        game = self.build(drifted=True)
        files = snapshot(game)
        rep = checker.check(game, 1)
        wrong = [t for _, v, t in rep.lines if v == "WRONG"]
        self.assertTrue(any(t.startswith("Lisha: recorded father Kito, mother Chika; the Births log says father Ghali")
                            for t in wrong), rep.render())
        self.assertTrue(any(t.startswith("Silko: recorded father") and "no Birth record" in t for t in wrong), rep.render())
        self.assertFalse(any(t.startswith("Goro") for t in wrong), "Goro's parents were right before and after")
        self.assertEqual(checker.main([str(game), "1"]), 1)
        self.assertEqual(snapshot(game), files, "the checker changed a file")

    def test_a_table_in_step_with_the_log_is_clean(self):
        game = self.build(drifted=False)
        files = snapshot(game)
        rep = checker.check(game, 1)
        self.assertEqual(rep.wrong, 0, rep.render())
        self.assertIn("every living villager's recorded parents agree with the Births log", rep.render())
        self.assertEqual(snapshot(game), files)


class Vv3Fixture(unittest.TestCase):
    def test_the_secret_citys_packed_villager_table_is_read(self):
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "Virtual Villagers - The Secret City - Modded"
        game.mkdir(parents=True)
        data = bytearray(77608)
        people = [("Vinapu", 1, 503, 27, 27), ("Manaka", 0, 601, 22, 16), ("Aloha", 1, 501, 24, 6)]
        for i, (name, male, age, head, body) in enumerate(people):
            e = 30832 + i * 0x11C
            struct.pack_into("<I", data, e, 1)
            n = e + 20
            data[n:n + len(name)] = name.encode()
            struct.pack_into("<i", data, n - 12, 1 if male else 0)
            struct.pack_into("<i", data, n - 16, age)
            struct.pack_into("<i", data, n + 28, head)
            struct.pack_into("<i", data, n + 32, body)
            for k in range(5):
                struct.pack_into("<i", data, n + 0xD8 + 4 * k, 90 if i == 0 else 10)
        (game / "Virtual Villagers - The Secret City1.ldw").write_bytes(bytes(data))
        rep = checker.check(game, 1)
        self.assertIn("The Secret City, Save 1: 3 living villagers read from the save", rep.render())
        roster = checker.vv25_roster(3, bytes(data), [])
        self.assertEqual([(v.name, v.head, v.body, v.age) for v in roster],
                         [(p[0], p[3], p[4], p[2]) for p in people])
        self.assertTrue(checker.is_elder(3, roster[0]) and not checker.is_elder(3, roster[1]))
        self.assertEqual(rep.wrong, 0)

    def test_the_256_villager_extension_is_read_after_the_150(self):
        data = bytearray(77608 + 20 + 2 * 0x11C)
        for k, (base, names) in enumerate(((30832, ("Vinapu", "Manaka")), (77608, ("Fill150", "Fill151")))):
            for i, name in enumerate(names):
                e = base + i * 0x11C
                struct.pack_into("<I", data, e, 1)
                data[e + 20:e + 20 + len(name)] = name.encode()
                struct.pack_into("<i", data, e + 20 + 28, 3)
        roster = checker.vv25_roster(3, bytes(data), [])
        self.assertEqual([(v.rank, v.name) for v in roster],
                         [(0, "Vinapu"), (1, "Manaka"), (2, "Fill150"), (3, "Fill151")])


    def test_a_single_villager_in_the_256_extension_is_read(self):
        data = bytearray(77608 + 20 + 0x11C)
        for base, name in ((30832, "Vinapu"), (77608, "Fill150")):
            struct.pack_into("<I", data, base, 1)
            data[base + 20:base + 20 + len(name)] = name.encode()
            struct.pack_into("<i", data, base + 20 + 28, 3)
        self.assertEqual([v.name for v in checker.vv25_roster(3, bytes(data), [])], ["Vinapu", "Fill150"])


class ParsingFixtures(unittest.TestCase):
    def test_unknown_parents_are_no_parents_and_disagreement_is_any_field(self):
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "g"
        (game / LOGS / "Births and Conceptions").mkdir(parents=True)
        (game / LOGS / "Births and Conceptions" / "Virtual Villagers 1 Births and Conceptions Log 1.txt").write_text(
            "Village: T (Save 1)\nBirth\n  Child: Ama\n    Head: 1\n    Body: 2\n  Mother: Chika\n    Head: 19\n"
            "    Body: 17\n  Father: (unknown)\n    Head: -1\n    Body: -1\n\n", encoding="latin-1")
        births, _ = checker.births_log(game, 1, 1)
        self.assertIsNone(births[0].father)
        self.assertEqual(births[0].mother.name, "Chika")

    def test_a_truncated_elders_file_is_unchecked_not_a_crash(self):
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "g"
        (game / DATA / "Village Elders").mkdir(parents=True)
        (game / DATA / "Village Elders" / "Village Elders - Save 1.dat").write_text("VVFP VILLAGE ELDERS v2 game=3")
        rep = checker.Report()
        self.assertIsNone(checker.check_elders(game, 1, 3, [], rep))
        self.assertEqual(rep.lines[0][1], "UNCHECKED")


if __name__ == "__main__":
    unittest.main()
