"""Stale villager entries after the last one a save loads are nobody (v1.35.80, all five games).

The owner's Kalahuna Tribe 2 (The Lost Children, Save 1, 2026-10-20): the game's save writer does NOT
zero the entries after its last villager.  After deaths at a full table the game closes its list up
and leaves frozen copies in the tail -- entries 252-255 held Goby, Malo, Tomil and Hoya Kalama, copies
of four living children, so the patcher's readers saw two records of each.  The first of them is
flagged 0 at entry +0x2DC (record +0x800) and the game loads nothing from there on; every entry it
loads carries the save's clock as its write stamp (record +0x528), the copies an older one.

Every reader goes through scripts/vvfp_consistency_check.py villager_offsets (src/vv_last_names.py
living, the reconciliation, Check and Repair), which now stops at that flag in The Lost Children as it
does at the other games' (PRESENT).  A live villager is never dropped.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_tools as tools  # noqa: E402

checker = tools.load_checker()

VV2_SIZE = 197500
VV2_TABLE = 540                 # entry 0; the name is entry +0x40
VV2_ENTRY = 0x2E0
VV2_CLOCK = 191208
NAMES = ["Goby Kalama", "Malo Kalama", "Tomil Kalama", "Hoya Kalama", "Aba Makawee", "Daku Kenobi",
         "Napuka Kenobi", "Noa Alosaka"]


def vv2_save(live: list[str], ghosts: list[tuple[str, int]], clock: int = 1083658,
             statue_at: int | None = None) -> bytes:
    """A The Lost Children save: `live` entries flagged 1 with the clock as their stamp, then each
    ghost (name, flag) with an older stamp."""
    data = bytearray(VV2_SIZE)
    struct.pack_into("<i", data, VV2_CLOCK, clock)
    rows = [(n, 1, clock) for n in live] + [(n, flag, clock - 13452) for n, flag in ghosts]
    for i, (name, flag, stamp) in enumerate(rows):
        e = VV2_TABLE + i * VV2_ENTRY
        p = e + 0x40
        data[p:p + len(name)] = name.encode()
        struct.pack_into("<i", data, e + 4, stamp)            # record +0x528: the write stamp
        struct.pack_into("<i", data, p - 0x38, 100)           # health
        struct.pack_into("<i", data, p - 0x34, 200 + 7 * i)   # age
        struct.pack_into("<i", data, p - 0x2C, 1 + i % 2)     # sex
        struct.pack_into("<i", data, p - 0x1C, i % 20)        # head
        struct.pack_into("<i", data, p - 0x18, (3 * i) % 20)  # body
        data[e + 0x2DC] = flag                                # the entry's in-use flag
        if statue_at == i:
            data[p - 0x0C] = 1                                # an Esteemed Elder statue
    return bytes(data)


def names_at(data: bytes, offsets: list[int]) -> list[str]:
    return [checker.cstr(data, p, 0x18) for p in offsets]


class TheLostChildrenTail(unittest.TestCase):
    def test_the_frozen_copies_after_the_last_villager_are_nobody(self):
        live = NAMES[4:] + NAMES[:4]          # the children alive, in their own entries
        data = vv2_save(live, [(NAMES[0], 0), (NAMES[1], 1), (NAMES[2], 1), (NAMES[3], 1)])
        offsets = checker.villager_offsets(2, data, [])
        self.assertEqual(names_at(data, offsets), live)
        roster = checker.vv25_roster(2, data, [])
        self.assertEqual(len(roster), len(live))
        self.assertEqual(sorted(v.name for v in roster), sorted(live), "one record of each child")

    def test_a_live_villager_is_never_dropped(self):
        live = [f"Villager{chr(65 + i // 26)}{chr(97 + i % 26)}" for i in range(256)]
        data = vv2_save(live, [])
        self.assertEqual(len(checker.villager_offsets(2, data, [])), 256, "a full table: all 256")
        data = vv2_save(NAMES, [], statue_at=2)
        self.assertEqual(names_at(data, checker.villager_offsets(2, data, [])), NAMES,
                         "a statue keeps its record; nobody after it is dropped")
        self.assertEqual(len(checker.vv25_roster(2, data, [])), len(NAMES) - 1, "the statue is no villager")

    def test_the_flag_is_the_games_own_and_agrees_with_the_write_stamp(self):
        data = vv2_save(NAMES[:5], [("Ghost Kalama", 0), ("Other Ghost", 1)])
        for p in checker.villager_offsets(2, data, []):
            self.assertEqual(struct.unpack_from("<i", data, p - 0x3C)[0], 1083658)
        self.assertEqual(checker.PRESENT[2], (0x29C, 1))

    def test_the_last_names_reader_sees_one_record_per_child(self):
        import tempfile
        import vv_last_names as ln
        with tempfile.TemporaryDirectory(prefix="vvg") as d:
            folder = Path(d)
            live = NAMES[4:] + NAMES[:4]
            (folder / f"{checker.SAVE_STEMS[2]}1.ldw").write_bytes(
                vv2_save(live, [(NAMES[0], 0), (NAMES[3], 1)]))
            self.assertEqual(sorted(v.name for v in ln.living(folder, 2, 1)), sorted(live))


class TheOtherGamesStopAtTheirFlag(unittest.TestCase):
    """The same end-of-list rule in every game: a stale copy after the flag is nobody."""

    def test_the_secret_city_to_new_believers(self):
        for game in (3, 4, 5):
            off, width = checker.PRESENT[game]
            data = bytearray(0x400)
            p = 0x200
            data[p + off:p + off + width] = (1).to_bytes(width, "little")
            self.assertTrue(checker.present(bytes(data), p, game), game)
            data[p + off:p + off + width] = bytes(width)
            self.assertFalse(checker.present(bytes(data), p, game), game)

    def test_a_new_home_stops_at_its_present_byte(self):
        source = (ROOT / "src" / "vv_last_names.py").read_text(encoding="utf-8")
        self.assertIn("if data[rel(0x3D4)] != 1:", source)
        self.assertIn("break", source[source.index("if data[rel(0x3D4)] != 1:"):][:160])


if __name__ == "__main__":
    unittest.main()
