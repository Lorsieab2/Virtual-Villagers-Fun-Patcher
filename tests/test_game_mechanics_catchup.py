"""The Game Mechanics window's "Time away (catch-up)" group (src/vv_game_mechanics_catchup.py): every game has it,
right after Sources, and its save lines count each villager's time away from that villager's own stamp."""
from __future__ import annotations

import gzip
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_tribe_rename  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
LAST = {1: (0xA308, "<I", 4), 2: (0x2EAE8, "<I", 4), 3: (0x12F08, "<I", 4), 4: (0x17100, "<q", 8),
        5: (0x17D60, "<q", 8)}


def _page(test: unittest.TestCase, game: int, data: bytes, now: float) -> list[gm.Fact]:
    base = next(item.base for item in vv_tribe_rename.GAMES if item.number == game)
    root = Path(tempfile.mkdtemp(prefix="gmcu"))
    test.addCleanup(shutil.rmtree, root, True)
    (root / base).mkdir()
    (root / base / f"{base}1.ldw").write_bytes(data)
    return gm.read(root / base, game, 1, [], now=now)


def _last(game: int, data: bytes) -> float:
    at, fmt, base_at = LAST[game]
    return struct.unpack_from(fmt, data, base_at)[0] + struct.unpack_from("<i", data, at)[0]


class TimeAway(unittest.TestCase):
    def test_every_game_has_the_group_after_sources(self) -> None:
        self.assertEqual(gm.GROUPS.index(gm.TIME_AWAY), gm.GROUPS.index(gm.SOURCES) + 1)
        for game in range(1, 6):
            path = sorted(FIXTURES.glob(f"vv{game}-*-[1-5].ldw.gz"))[0]
            data = gzip.decompress(path.read_bytes())
            with self.subTest(game=game):
                facts = [f for f in _page(self, game, data, _last(game, data) + 3600) if f.group == gm.TIME_AWAY]
                self.assertTrue(any(f.text.startswith("How it is stepped through:") for f in facts))
                self.assertTrue(all(f.confirmed or f.verified is False for f in facts))

    def test_villagers_crossing_the_limit_at_different_moments(self) -> None:
        """A New Home's fixture keeps 8 to 92 seconds per villager: 38,120 s after its save (Fast) one villager still
        counts in full, the others are already cut to 8 h 36 min 40 s -- the page says so per villager, and its
        countdown is to the last one's crossing, not to a moment already past."""
        data = gzip.decompress((FIXTURES / "vv1-huttest-1.ldw.gz").read_bytes())
        now = _last(1, data) + 38_120
        facts = [f for f in _page(self, 1, data, now) if f.group == gm.TIME_AWAY]
        texts = [f.text for f in facts]
        self.assertIn("If it were played now each villager would age by at most 211 age units (10.55 villager years) "
                      "at once, all worked through in the first update after it loads. " + gm.AGES, texts)
        counted = next(t for t in texts if t.startswith("Counted now,"))
        self.assertRegex(counted, r"^Counted now, villager by villager: [1-9]\d* in full, [1-9]\d* cut to 8 hours 36 "
                                  r"minutes 40 seconds of real time, 0 cut to 24 hours of real time\.$")
        nxt = next(f for f in facts if f.text.startswith("The next villager's time away crosses a limit"))
        self.assertIsNotNone(nxt.due)
        self.assertGreater(nxt.due, now)
        self.assertLessEqual(nxt.due, now + 92)

    def test_a_paused_save_gets_none(self) -> None:
        data = bytearray(gzip.decompress((FIXTURES / "vv1-huttest-1.ldw.gz").read_bytes()))
        import vv_save_backup
        at, value = vv_save_backup.save_speed(1, bytes(data))
        struct.pack_into("<i", data, at, gm.speed_base(value) + gm.PAUSED)
        texts = [f.text for f in _page(self, 1, bytes(data), _last(1, bytes(data)) + 3600) if f.group == gm.TIME_AWAY]
        self.assertTrue(any(t.startswith("Saved paused: none of the time") for t in texts))
        self.assertFalse(any(t.startswith(("Counted now,", "If it were played now each")) for t in texts))


if __name__ == "__main__":
    unittest.main()
