"""The author's cause words on The Secret City's, The Tree of Life's and New Believers' graves (v1.35.97).

The owner: a branching Custom Island Event's death that names its cause shows those words on the grave in the later
three games too, not "Unknown causes".  "VVFP Cause of Death.dll" points each game's grave cause lookup at itself at
run time (VV3 0x41EC65 and The Secret City's Roster of the Dead 0x41A07F, VV4 0x41C18A, VV5 0x41C9DA:
cod_cie_words.inc CW_GRAVE_SITES): the game's own lookup runs, and only a grave whose cause is -1 and whose
fingerprint has the author's words (VvfpCauseKilledBy) gets them; every other grave keeps the game's own words.

EMULATED (unicorn, the stock executables, the TEST build; tests/test_cause_of_death.py's harness): in each game a
villager killed with words and one killed by a stock island event are buried; the grave dialog's call (and The
Secret City's Roster of the Dead's) is run with each Roster of the Dead entry: the words for the first, the game's
own text for the other; the sites are the companion's after the install, and the game's own call before it.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_cause_of_death as tc  # noqa: E402

SITES = {"vv3": [(0x41EC65, 0x42F190, "eax"), (0x41A07F, 0x42F190, "ebp")],
         "vv4": [(0x41C18A, 0x44D3D0, "ebx")],
         "vv5": [(0x41C9DA, 0x4506D0, "eax")]}
BASE = {"vv3": 0x2E6, "vv4": 0x317, "vv5": 0x314}
WORDS = "Fell from the Great Falls"


@unittest.skipUnless(tc.TEST_DLL.is_file(), tc.TEST_BUILD_ABSENT)
class LaterGravesSayTheWords(unittest.TestCase):
    def lookup(self, g: tc.Game, site: int, va: int, reg: str, entry: int, unknown: int) -> str:
        """The site's call as the dialog makes it: the id pushed, ecx the table, the entry in its register."""
        p = g.p
        seen = []

        def game_lookup(proc):
            seen.append(proc.arg(0))
            return unknown, 4
        p.stub(va, game_lookup)
        cause = struct.unpack("<i", p.read(entry + (0x2C if g.game == "vv3" else 0x34), 4))[0]
        p.put32(tc.STACK - 4, cause + BASE[g.game])
        g.run(site, site + 5, **{reg: entry, "ecx": 0x1000, "esp": tc.STACK - 4})
        self.assertEqual(seen, [cause + BASE[g.game]], "the game's own lookup ran, with its own id")
        self.assertEqual(p.reg("esp"), tc.STACK, "the id popped as the game's lookup pops it")
        return p.cstring(p.reg("eax"))

    def test_the_words_on_the_grave_and_the_roster_only_for_that_death(self):
        for game in ("vv3", "vv4", "vv5"):
            if not tc.STOCK[game].is_file():
                continue
            with self.subTest(game=game):
                g, w = tc.later(game)
                p = g.p
                words = p.alloc(64)
                p.write(words, WORDS.encode() + b"\0")
                unknown = p.alloc(32)
                p.write(unknown, b"Unknown causes\0")
                w.villager(3, "Killed", 640, 0, -1)
                p.export("VvfpCauseKilledBy", g.no, 3, words)
                w.villager(4, "Event", 650, 0, -1)                  # a stock island event's death
                g.tick()
                w.bury(3)
                w.bury(4)
                for site, va, reg in SITES[game]:
                    self.assertEqual(p.read(site, 1), b"\xE8")
                    self.assertNotEqual(site + 5 + struct.unpack("<i", p.read(site + 1, 4))[0], va,
                                        "the site is the companion's")
                    self.assertEqual(self.lookup(g, site, va, reg, w.entry(0), unknown), WORDS, (game, hex(site)))
                    self.assertEqual(self.lookup(g, site, va, reg, w.entry(1), unknown), "Unknown causes",
                                     (game, hex(site)))

    def test_not_installed_the_games_own_call(self):
        for game in ("vv3", "vv4", "vv5"):
            if not tc.STOCK[game].is_file():
                continue
            g = tc.Game(game, tc.rendered(game, "stock", True))
            for site, va, _reg in SITES[game]:
                self.assertEqual(site + 5 + struct.unpack("<i", g.p.read(site + 1, 4))[0], va, (game, hex(site)))


if __name__ == "__main__":
    unittest.main()
