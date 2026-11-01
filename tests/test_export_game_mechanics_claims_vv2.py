"""scripts/export_game_mechanics_claims.py, The Lost Children (VV2): every line the Game Mechanics window renders
from the fixtures and from the fish's states is in the claims file, and the file is written under its name with
its statuses.  The shared checks are in tests/game_mechanics_claims_cases.py."""
from __future__ import annotations

import gzip
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import game_mechanics_claims_cases as cases  # noqa: E402
import test_game_mechanics as t  # noqa: E402


class Coverage(cases.ClaimsCases, unittest.TestCase):
    GAME = 2

    def test_the_lost_childrens_fish(self) -> None:
        import vv_game_mechanics_vv2 as vv2
        data = gzip.decompress((t.FIXTURES / "vv2-huttest-1.ldw.gz").read_bytes())
        for fish, solved, farming in ((700, 0, 3), (0, 0, 3), (-40, 1, 1), (-1_162_256, 1, 3), (5, 1, 2)):
            buf = bytearray(data)
            struct.pack_into("<i", buf, vv2.FISH + vv2.S, fish)
            struct.pack_into("<i", buf, vv2.LEVELS + 8 * vv2.FARMING_LEVEL + vv2.S, farming)
            buf[vv2.SUSTAINABLE_FISHING + vv2.S] = solved
            with self.subTest(fish=fish, solved=solved, farming=farming):
                self.assert_covered(2, self.page(2, bytes(buf), 1_791_000_000.0))


if __name__ == "__main__":
    unittest.main()
