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


    # ---- Codex on #522, third round ------------------------------------------------------

    def births_file(self, game: Path, n: int = 1) -> Path:
        return game / LOGS / "Births and Conceptions" / f"Virtual Villagers 1 Births and Conceptions Log {n}.txt"

    def test_a_new_village_whose_header_is_all_its_log_holds_is_not_the_old_one(self):
        game = self.build(drifted=True)
        self.births_file(game, 2).write_text("Village: Another Tribe (Save 1)\n", encoding="latin-1")
        births, _ = checker.births_log(game, 1, 1)
        self.assertEqual(births.village, "Village: Another Tribe (Save 1)")
        self.assertEqual(len(births), 0, "the previous village's records are not this village's")
        rep = checker.check(game, 1)
        self.assertEqual(rep.wrong, 0, rep.render())

    def test_an_expecting_mothers_father_is_compared_by_body_too(self):
        game = self.build(drifted=False)
        save = bytearray((game / "Virtual Villagers1.ldw").read_bytes())
        after = [v for v in OWNER if v[0] not in ("Kito", "Chika")] + [SILKO]
        lisha = [v[0] for v in after].index("Lisha")
        struct.pack_into("<i", save, 0x184 + lisha * 0x9C - 0x33C + 0x358, 900)
        (game / "Virtual Villagers1.ldw").write_bytes(bytes(save))
        goro = BY_NAME["Goro"]
        with self.births_file(game).open("a", encoding="latin-1") as f:
            f.write(f"Conception 1\n  Mother: Lisha\n    Head: 13\n    Body: 10\n"
                    f"  Father: Goro\n    Head: {goro[3]}\n    Body: {goro[4]}\n  Babies in pregnancy: 1\n\n")
        dat = game / DATA / "Virtual Villagers 1 Parentage Records - Save 1.dat"
        data = bytearray(dat.read_bytes())
        e = 12 + 256 * 36 + lisha * 92
        data[e + 4] = goro[3] + 1
        data[e + 5] = goro[4] + 1
        data[e + 64:e + 64 + 4] = b"Goro"
        dat.write_bytes(bytes(data))
        self.assertEqual(checker.check(game, 1).wrong, 0)
        data[e + 5] = goro[4] + 2                      # the right name and head, the wrong body
        dat.write_bytes(bytes(data))
        rep = checker.check(game, 1)
        self.assertTrue(any(v == "WRONG" and t.startswith("Lisha is expecting") for _, v, t in rep.lines), rep.render())

    def test_a_stale_expected_father_on_a_villager_not_expecting_is_wrong(self):
        game = self.build(drifted=False)
        after = [v for v in OWNER if v[0] not in ("Kito", "Chika")] + [SILKO]
        hawa = [v[0] for v in after].index("Hawa")
        dat = game / DATA / "Virtual Villagers 1 Parentage Records - Save 1.dat"
        data = bytearray(dat.read_bytes())
        e = 12 + 256 * 36 + hawa * 92
        data[e + 4], data[e + 5] = 5, 6
        data[e + 64:e + 64 + 5] = b"Ponui"
        dat.write_bytes(bytes(data))
        rep = checker.check(game, 1)
        self.assertTrue(any(v == "WRONG" and t.startswith("Hawa is not expecting, but an expected father Ponui")
                            for _, v, t in rep.lines), rep.render())

    # ---- Codex on #522, fourth round ------------------------------------------------------

    def verdicts(self, game: Path, suffix: str):
        return [(v, t) for f, v, t in checker.check(game, 1).lines if f.endswith(suffix)]

    def test_a_graves_file_whose_count_lies_is_unchecked_without_walking_it(self):
        game = self.build(drifted=False)
        (game / DATA / "Graves").mkdir()
        (game / DATA / "Graves" / "Virtual Villagers 1 Graves - Save 1.dat").write_bytes(
            struct.pack("<4sIII", b"VCD1", 1, 1, 0xFFFFFFFF))
        self.assertEqual(self.verdicts(game, "Graves - Save 1.dat")[0][0], "UNCHECKED")

    def test_deaths_of_an_earlier_village_in_the_slot_are_not_this_ones(self):
        game = self.build(drifted=False)
        folder = game / LOGS / "Deaths"
        folder.mkdir()
        (folder / "Virtual Villagers 1 Deaths Log 1.txt").write_text(
            "Village: Old Tribe (Save 1)\nDeath 1\n  Name: Ghali\n\nDeath 2\n  Name: Lisha\n\n"
            "Village: Kalahuna Tribe 1 (Save 1)\nDeath 1\n  Name: Kito\n\n", encoding="latin-1")
        blocks, _ = checker.numbered_records(game, "Deaths", "Virtual Villagers 1 Deaths Log", "Death ", 1)
        self.assertEqual(len(blocks), 1)
        self.assertIn("Kito", blocks[0])

    def test_an_unreadable_births_log_is_unchecked_not_a_crash(self):
        game = self.build(drifted=True)
        original = checker.read_log_text

        def denied(path):
            if "Births and Conceptions" in path.name:
                raise checker.LogUnreadable(f"{path.name}: Permission denied")
            return original(path)
        checker.read_log_text = denied
        try:
            rep = checker.check(game, 1)
        finally:
            checker.read_log_text = original
        self.assertEqual(rep.wrong, 0, rep.render())
        self.assertIn("cannot be read", rep.render())

    def vcr1(self, game: Path, data: bytes) -> list:
        folder = game / DATA / "Unaccounted Villagers"
        folder.mkdir(exist_ok=True)
        (folder / "Virtual Villagers 1 Village Roster - Save 1.dat").write_bytes(data)
        return self.verdicts(game, "Village Roster - Save 1.dat")

    def test_a_roster_the_game_would_reject_is_not_ok(self):
        game = self.build(drifted=False)
        lo, hi = 0x33C, 0x3D8
        entry = lambda i, r: struct.pack("<HHIQ", i, r, 0, 0) + bytes(hi - lo)
        good = struct.pack("<4sIIIIIII", b"VCR1", 1, 1, 2, lo, hi, 0, 0) + entry(0, 0) + entry(1, 1)
        self.assertEqual(self.vcr1(game, good)[0][0], "OK")
        bad_order = struct.pack("<4sIIIIIII", b"VCR1", 1, 1, 2, lo, hi, 0, 0) + entry(1, 1) + entry(0, 0)
        self.assertEqual(self.vcr1(game, bad_order)[0][0], "UNCHECKED")
        bad_version = struct.pack("<4sIIIIIII", b"VCR1", 3, 1, 2, lo, hi, 0, 0) + entry(0, 0) + entry(1, 1)
        self.assertEqual(self.vcr1(game, bad_version)[0][0], "UNCHECKED")
        # Version 2 keeps each villager's mask (0..5) in the entry's byte 4 (Codex, #553).
        masked = lambda i, r, m: struct.pack("<HHBBHQ", i, r, m, 0, 0, 0) + bytes(hi - lo)
        v2 = struct.pack("<4sIIIIIII", b"VCR1", 2, 1, 2, lo, hi, 0, 0)
        self.assertEqual(self.vcr1(game, v2 + masked(0, 0, 4) + masked(1, 1, 0))[0][0], "OK")
        self.assertEqual(self.vcr1(game, v2 + masked(0, 0, 6) + masked(1, 1, 0))[0][0], "UNCHECKED")
        v1_masked = struct.pack("<4sIIIIIII", b"VCR1", 1, 1, 2, lo, hi, 0, 0) + masked(0, 0, 4) + masked(1, 1, 0)
        self.assertEqual(self.vcr1(game, v1_masked)[0][0], "UNCHECKED", "version 1 has no mask byte")
        short = good[:-1]
        self.assertEqual(self.vcr1(game, short)[0][0], "UNCHECKED")

    def test_a_statistics_roster_with_a_malformed_row_is_unchecked(self):
        game = self.build(drifted=False)
        after = [v for v in OWNER if v[0] not in ("Kito", "Chika")] + [SILKO]
        folder = game / DATA / "Village Statistics"
        folder.mkdir()
        rows = [f"{i}\t{v[0]}\t00000000" for i, v in enumerate(after)]
        path = folder / "Village Roster - Save 1.dat"
        path.write_text("VVFP VILLAGE ROSTER v1\n" + "\n".join(rows) + "\n", encoding="latin-1")
        self.assertEqual(self.verdicts(game, "Village Roster - Save 1.dat")[-1][0], "OK")
        path.write_text("VVFP VILLAGE ROSTER v1\n" + "\n".join(rows) + "\n99\tTrunc\n", encoding="latin-1")
        self.assertEqual(self.verdicts(game, "Village Roster - Save 1.dat")[-1][0], "UNCHECKED")

    def marker(self, game: Path, words) -> None:
        folder = game / DATA / "Cross-Check"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "Virtual Villagers 1 Cross-Check - Save 1.dat").write_bytes(struct.pack("<4s11I", b"VXC1", *words))

    def test_the_marker_counts_only_for_its_own_village_and_slot(self):
        game = self.build(drifted=False)
        here = checker.village_id("Village: Kalahuna Tribe 1 (Save 1)")

        def verdict():
            return [(v, t) for f, v, t in checker.check(game, 1).lines if f.endswith("Cross-Check")][0]
        self.marker(game, [1, 1, 1, 2, 0, 0, 0, 0, 0, 0, here])
        self.assertEqual(verdict(), ("OK", "the cross-check ran for this village: repaired"))
        self.marker(game, [1, 1, 1, 2, 0, 0, 0, 0, 0, 0, here ^ 1])
        self.assertEqual(verdict()[0], "NOTE")
        self.assertIn("another village's", verdict()[1])
        self.marker(game, [1, 1, 2, 2, 0, 0, 0, 0, 0, 0, here])        # another slot's
        self.assertEqual(verdict()[0], "UNCHECKED")
        self.marker(game, [1, 1, 1, 9, 0, 0, 0, 0, 0, 0, here])        # no such result
        self.assertEqual(verdict()[0], "UNCHECKED")

    def test_a_record_cut_short_makes_the_log_unchecked_as_the_game_does(self):
        game = self.build(drifted=True)
        with self.births_file(game).open("a", encoding="latin-1") as f:
            f.write("Birth\n  Child: Lisha\n")
        rep = checker.check(game, 1)
        self.assertEqual(rep.wrong, 0, rep.render())
        self.assertIn("cut short", rep.render())

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


class StaleRecords(unittest.TestCase):
    """A save keeps stale villager records after the living ones; the game loads the records in
    order and stops at the first not flagged present (live, 2026-10-06, all five games: the
    owner's saves read as 39 / 104 / 124 / 100 / 115 / 106 villagers where the game loaded
    37 / 90 / 123 / 86 / 5 / 90).  Nothing after that record is a villager."""

    def vv1(self, flags):
        data = bytearray(0x184 + 256 * 0x9C)
        for i, flag in enumerate(flags):
            base = 0x184 + i * 0x9C - 0x33C
            struct.pack_into("<i", data, base + 0x350, 1)
            struct.pack_into("<i", data, base + 0x344, 90)
            struct.pack_into("<i", data, base + 0x3D4, flag)
            name = f"Vil{i}".encode()
            data[base + 0x370:base + 0x370 + len(name)] = name
        return bytes(data)

    def vv25(self, game, flags, extension=()):
        lay = checker.LAYOUTS[game]
        first = 0x400
        data = bytearray(first + 150 * lay.stride + 0x40 + (len(extension) + 1) * lay.stride)
        spots = [(first + i * lay.stride, flag, f"Vil{i}") for i, flag in enumerate(flags)]
        ext = first + 150 * lay.stride + 0x40
        spots += [(ext + i * lay.stride, flag, f"Ext{i}") for i, flag in enumerate(extension)]
        for p, flag, name in spots:
            data[p:p + len(name)] = name.encode()
            struct.pack_into("<i", data, p + lay.age, 300)
            struct.pack_into("<i", data, p + lay.head, 3)
            struct.pack_into("<i", data, p + lay.body, 4)
            if game in checker.PRESENT:
                off, width = checker.PRESENT[game]
                data[p + off:p + off + width] = flag.to_bytes(width, "little")
                if game == 5:
                    data[p + off + 1] = 1           # the entry header's next byte (the faction)
        return bytes(data)

    def test_a_new_home_stops_at_the_first_record_not_present(self):
        self.assertEqual([v.name for v in checker.vv1_roster(self.vv1([1, 1, 0, 1, 1]))], ["Vil0", "Vil1"])

    def test_the_later_games_stop_at_the_end_of_list_flag(self):
        for game in (3, 4, 5):
            with self.subTest(game=game):
                roster = checker.vv25_roster(game, self.vv25(game, [1, 1, 1, 0, 1, 1]), [])
                self.assertEqual([v.name for v in roster], ["Vil0", "Vil1", "Vil2"])

    def test_nothing_after_the_flag_is_read_from_the_256_extension_either(self):
        for game in (3, 4, 5):
            with self.subTest(game=game):
                ended = checker.vv25_roster(game, self.vv25(game, [1, 0, 1], extension=[1]), [])
                self.assertEqual([v.name for v in ended], ["Vil0"])
                full = checker.vv25_roster(game, self.vv25(game, [1] * 150, extension=[1, 0, 1]), [])
                self.assertEqual([v.name for v in full][-2:], ["Vil149", "Ext0"])

    def test_the_lost_children_has_no_flag_and_ends_at_its_zeroed_tail(self):
        lay = checker.LAYOUTS[2]
        data = bytearray(0x400 + 4 * lay.stride)
        for i in range(2):
            p = 0x400 + i * lay.stride
            data[p:p + 4] = f"Vil{i}".encode()
            struct.pack_into("<i", data, p + lay.age, 300)
        self.assertEqual([v.name for v in checker.vv25_roster(2, bytes(data), [])], ["Vil0", "Vil1"])


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


def vv3_save(people) -> bytes:
    """A Secret City save: the packed villager table (see the test above), with each villager's
    own parents (name +0x24 / +0x3D) and skills."""
    data = bytearray(77608)
    for i, (name, father, mother, head, body, masters) in enumerate(people):
        e = 30832 + i * 0x11C
        struct.pack_into("<I", data, e, 1)
        n = e + 20
        data[n:n + len(name)] = name.encode()
        data[n + 0x24:n + 0x24 + len(father)] = father.encode()
        data[n + 0x3D:n + 0x3D + len(mother)] = mother.encode()
        struct.pack_into("<i", data, n - 16, 500)
        struct.pack_into("<i", data, n + 28, head)
        struct.pack_into("<i", data, n + 32, body)
        for k in range(5):
            struct.pack_into("<i", data, n + 0xD8 + 4 * k, 95 if k < masters else 10)
    return bytes(data)


class ReconcileFixtures(unittest.TestCase):
    """What v1.35.58's extended first-load repair changes, predicted read-only."""

    def folder(self) -> Path:
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "Virtual Villagers - The Secret City - Modded"
        (game / LOGS / "Births and Conceptions").mkdir(parents=True)
        (game / LOGS / "Deaths").mkdir(parents=True)
        (game / LOGS / "Tribe History").mkdir(parents=True)
        (game / DATA / "Village Elders").mkdir(parents=True)
        (game / DATA / "Village Statistics").mkdir(parents=True)
        (game / "Virtual Villagers - The Secret City1.ldw").write_bytes(vv3_save([
            ("Vinapu", "", "", 27, 27, 0), ("Kolea", "Vinapu", "Manaka", 4, 5, 0),
            ("Twin", "Vinapu", "Manaka", 6, 6, 0), ("Twin", "Vinapu", "Manaka", 6, 6, 0),
            ("Nishi", "Vinapu", "Manaka", 9, 3, 0),
        ]))
        (game / LOGS / "Births and Conceptions" / "Virtual Villagers 3 Births and Conceptions Log 1.txt").write_text(
            "Village: Recon (Save 1)\nBirth\n  Child: Twin\n    Head: 6\n    Body: 6\n  Mother: Manaka\n    Head: 1\n"
            "    Body: 1\n  Father: Vinapu\n    Head: 27\n    Body: 27\n\n"
            "Birth\n  Child: Nishi\n    Head: 7\n    Body: 3\n  Mother: Manaka\n    Head: 1\n    Body: 1\n"
            "  Father: Vinapu\n    Head: 27\n    Body: 27\n\n", encoding="latin-1")
        (game / LOGS / "Deaths" / "Virtual Villagers 3 Deaths Log 1.txt").write_text(
            "Village: Recon (Save 1)\nDeath 1\n  Name: Mia\n  Grave: Master Builder\n\n"
            "Death 2\n  Name: Lua\n  Grave: no grave (never buried: the game removed the body)\n\n"
            "Death 3\n  Name: Rex\n  Grave: Untrained\n\n", encoding="latin-1")
        (game / LOGS / "Tribe History" / "Village History 1.txt").write_text(
            "=== Virtual Villagers 3 -- 2026-09-01 10:00:00 ===\nVillage: Recon (Save 1)\n\n"
            "Villager 1\n  Name: Ghost\n  Age: 900\n  Head: 1\n  Body: 1\n  Skills:\n"
            "    Farming    88\n    Building   90\n    Healing    100\n    Science    3\n    Breeding   4\n\n"
            "Villager 2\n  Name: Near\n  Age: 900\n  Head: 1\n  Body: 1\n  Skills:\n"
            "    Farming    88\n    Building   87\n    Healing    100\n    Science    3\n    Breeding   4\n\n",
            encoding="latin-1")
        (game / DATA / "Village Elders" / "Village Elders - Save 1.dat").write_text(
            "VVFP VILLAGE ELDERS v2 game=3\ngraves_seen=0\n", encoding="latin-1")
        return game

    def counters(self, game: Path, buried: int) -> None:
        (game / DATA / "Village Statistics" / "Village Statistics - Save 1.dat").write_text(
            f"VVFP VILLAGE STATISTICS v1 game=3\nmigrated.villagers_buried=0\nvillagers_buried={buried}\n",
            encoding="latin-1")

    def test_what_the_repair_would_change_is_listed_and_nothing_is_written(self):
        game = self.folder()
        self.counters(game, 1)
        before = snapshot(game)
        rep = checker.check(game, 1)
        text = rep.render()
        self.assertEqual(snapshot(game), before)
        wrong = [t for _f, v, t in rep.lines if v == "WRONG"]
        self.assertEqual(sum("Kolea: born here" in w for w in wrong), 1, text)
        self.assertEqual(sum("Twin: born here" in w for w in wrong), 1, "two Twins, one Birth record: one is missing")
        self.assertFalse(any("Nishi" in w for w in wrong), "the only Nishi, looks changed: her record is hers")
        self.assertFalse(any("Vinapu: born here" in w for w in wrong), "no parents in the save: not born here")
        self.assertTrue(any(w.startswith("Ghost is a Village Elder in the Village History log") for w in wrong), text)
        self.assertFalse(any(w.startswith("Near ") for w in wrong), "two masteries is not an elder")
        self.assertIn("Villagers Buried is 1, below the 2 Death records with a grave in the Deaths log (repairable: "
                      "raised to 2)", text)
        self.assertEqual(rep.wrong, 4)

    def test_a_counter_above_its_bound_is_never_reported_and_the_backfill_marker_ends_it(self):
        game = self.folder()
        self.counters(game, 7)
        (game / DATA / "Births").mkdir(parents=True)
        (game / DATA / "Births" / "Virtual Villagers 3 Births Recorded - Save 1.dat").write_bytes(
            struct.pack("<4I", 0x31424356, 1, 3, 1))
        rep = checker.check(game, 1)
        self.assertIn("Villagers Buried 7 >= the 2 Death records with a grave", rep.render())
        self.assertFalse(any("born here" in t for _f, v, t in rep.lines if v == "WRONG"))
        self.assertEqual(rep.wrong, 1)      # Ghost

    def test_every_report_only_file_says_why(self):
        game = self.folder()
        self.counters(game, 2)
        text = checker.check(game, 1).render()
        for name, why in checker.REPORT_ONLY.items():
            if name in ("stews", "masks", "titles"):
                continue        # shown with their files, which this fixture has none of
            self.assertIn(why, text, name)


if __name__ == "__main__":
    unittest.main()
