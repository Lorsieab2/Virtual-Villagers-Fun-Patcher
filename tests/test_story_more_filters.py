"""The content filters keep More Island Events' events out exactly as their content tag table says.

"VVFP Story Upgrades.dll" keeps a More Island Events entry out of the draw and Pick Island Event's list when a ticked
content filter is one its table SC_MORE_FILTERS names (story_collection.inc sc_more_filtered).  That table was written
by hand and drifted from the events' tag table (data/event_collection/content_tags/mie.json): The Mysterious Mask had
no filter (it has a child's disappearance: F01 F04 F18), The Climb none (F03 F05), The Playful Dolphins F22 (it has
F06 F25), and so on.  It is now GENERATED (scripts/build_story_more_filters.py, run by
scripts/build_vvfp_story_upgrades.ps1 before every compile).  Shown here:

  * for every game, every More Island Events entry in that game has, in the committed header, exactly the filters
    mie.json names for its event, by its registry index (mie_pick.inc MIE_PICKS);
  * the committed header is exactly what the generator writes now, the source includes it and keeps no table of its
    own;
  * the shipped DLL (and the test build) hold that very table;
  * the population gate's table SC_MORE_DEADLY is generated from the same tags (any of F01..F04), matches every
    event's real outcomes, and marks The Mysterious Mask deadly (owner, 2026-11-21).
"""
from __future__ import annotations

import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_story_more_filters as gen  # noqa: E402

TAGS = ROOT / "data" / "event_collection" / "content_tags" / "mie.json"
HEADER = ROOT / "native" / "vvfp_story_upgrades" / "story_more_filters.h"
COLLECTION = ROOT / "native" / "vvfp_story_upgrades" / "story_collection.inc"
DLL = ROOT / "assets" / "story_upgrades" / "VVFP Story Upgrades.dll"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Story Upgrades.test.dll"

# Independent of the generator: each registry entry's event in mie.json.
EVENT_OF = {
    "aspiring_adventurer": "mie_adventurer", "cave_explorers": "mie_cave_explorers", "the_climb": "mie_climb",
    "troubling_signs": "mie_troubling_signs", "diving_for_treasure": "mie_diving",
    "playful_dolphins": "mie_dolphins", "mysterious_mask": "mie_mysterious_mask",
    "remembrance_ceremony": "mie_remembrance", "remembrance_ceremony_nb": "mie_remembrance",
    "the_rumblings": "mie_rumblings",
}


def shipped_table() -> list[int]:
    text = HEADER.read_text(encoding="ascii")
    body = re.search(r"SC_MORE_FILTERS\[\] = \{(.*?)\};", text, re.S).group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return [int(v, 16) for v in re.findall(r"0x([0-9A-F]+)u", body)]


def wanted(filters: list[str]) -> int:
    return sum(1 << (int(code[1:]) - 1) for code in set(filters))


class TheTableMatchesTheTagTable(unittest.TestCase):
    def test_every_event_in_every_game(self) -> None:
        tags = json.loads(TAGS.read_text(encoding="utf-8"))["events"]
        table = shipped_table()
        picks = gen.picks()
        self.assertEqual(len(table), len(picks))
        self.assertEqual({e for e in EVENT_OF.values()}, set(tags))     # every tagged event is an entry
        checked = 0
        for game in (1, 2, 3, 4, 5):
            in_game = [(k, ident) for k, (ident, games) in enumerate(picks) if game in games]
            self.assertTrue(in_game, f"VV{game} has no More Island Events entry")
            for k, ident in in_game:
                with self.subTest(game=game, event=ident):
                    expected = wanted(tags[EVENT_OF[ident]]["filters"])
                    got = table[k]
                    self.assertEqual(
                        got, expected,
                        f"VV{game} {ident}: table has "
                        f"{sorted(f'F{n + 1:02d}' for n in range(28) if got >> n & 1)}, mie.json "
                        f"{sorted(tags[EVENT_OF[ident]]['filters'])}")
                    checked += 1
        self.assertGreaterEqual(checked, 20)

    def test_the_cases_that_drifted(self) -> None:
        table = shipped_table()
        idx = {ident: k for k, (ident, _g) in enumerate(gen.picks())}
        bit = lambda n: 1 << (n - 1)                                    # noqa: E731
        self.assertEqual(table[idx["mysterious_mask"]], bit(1) | bit(4) | bit(18))
        self.assertEqual(table[idx["playful_dolphins"]], bit(6) | bit(25))
        self.assertFalse(table[idx["playful_dolphins"]] & bit(22))
        self.assertEqual(table[idx["the_climb"]], bit(3) | bit(5))


def shipped_deadly() -> list[int]:
    text = HEADER.read_text(encoding="ascii")
    body = re.search(r"SC_MORE_DEADLY\[\] = \{(.*?)\};", text, re.S).group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return [int(v) for v in re.findall(r"\b([01])\b", body)]


# Independent of the generator: the events whose real outcomes kill or remove a villager for good (adv_game.kill /
# adv_game.vanish in native/vvfp_more_island_events: adv_core, cave_core, climb_core, troubling_core, dive_core,
# mask_core).  The Playful Dolphins (health floored at 1), The Rumblings (structures) and The Remembrance Ceremony
# remove no one.
REMOVES_VILLAGERS = {"aspiring_adventurer", "cave_explorers", "the_climb", "troubling_signs",
                     "diving_for_treasure", "mysterious_mask"}


class TheDeadlyTableMatchesTheTagTable(unittest.TestCase):
    """SC_MORE_DEADLY (the 61-villager population gate) is generated from the same tags: F01..F04.  It was written by
    hand and left The Mysterious Mask (five villagers taken for good) out of the gate."""

    def test_every_event_in_every_game(self) -> None:
        tags = json.loads(TAGS.read_text(encoding="utf-8"))["events"]
        deadly = shipped_deadly()
        picks = gen.picks()
        self.assertEqual(len(deadly), len(picks))
        checked = 0
        for game in (1, 2, 3, 4, 5):
            in_game = [(k, ident) for k, (ident, games) in enumerate(picks) if game in games]
            self.assertTrue(in_game, f"VV{game} has no More Island Events entry")
            for k, ident in in_game:
                with self.subTest(game=game, event=ident):
                    filters = tags[EVENT_OF[ident]]["filters"]
                    by_tags = int(any(c in ("F01", "F02", "F03", "F04") for c in filters))
                    self.assertEqual(deadly[k], by_tags, f"VV{game} {ident}: tags {sorted(filters)}")
                    self.assertEqual(deadly[k], gen.deadly(sorted(set(filters))))
                    self.assertEqual(deadly[k], int(ident in REMOVES_VILLAGERS),
                                     f"VV{game} {ident}: the deadly mark does not match its real outcomes")
                    checked += 1
        self.assertGreaterEqual(checked, 20)

    def test_the_mask_is_deadly(self) -> None:
        idx = {ident: k for k, (ident, _g) in enumerate(gen.picks())}
        self.assertEqual(shipped_deadly()[idx["mysterious_mask"]], 1)

    def test_source_keeps_no_deadly_table_of_its_own(self) -> None:
        text = COLLECTION.read_text(encoding="utf-8")
        self.assertNotIn("SC_MORE_DEADLY[] =", text)
        self.assertIn("SC_MORE_DEADLY[k_more]", text)

    def test_the_dlls_hold_this_table(self) -> None:
        blob = bytes(shipped_deadly())
        for dll in (DLL, TEST_DLL):
            with self.subTest(dll=dll.name):
                if not dll.is_file():
                    self.skipTest(f"{dll} not built")
                self.assertTrue(blob in dll.read_bytes(),
                                f"{dll.name} is not built from this table (run scripts/build_vvfp_story_upgrades.ps1)")


class TheTableIsGenerated(unittest.TestCase):
    def test_header_is_the_generators_output(self) -> None:
        self.assertEqual(HEADER.read_text(encoding="ascii"), gen.render(),
                         "run python scripts/build_story_more_filters.py")

    def test_source_includes_it_and_keeps_no_table_of_its_own(self) -> None:
        text = COLLECTION.read_text(encoding="utf-8")
        self.assertIn('#include "story_more_filters.h"', text)
        self.assertNotIn("SC_MORE_FILTERS[] =", text)
        builder = (ROOT / "scripts" / "build_vvfp_story_upgrades.ps1").read_text(encoding="utf-8")
        self.assertIn("build_story_more_filters.py", builder)

    def test_the_dlls_hold_this_table(self) -> None:
        blob = struct.pack(f"<{len(shipped_table())}I", *shipped_table())
        for dll in (DLL, TEST_DLL):
            with self.subTest(dll=dll.name):
                if not dll.is_file():
                    self.skipTest(f"{dll} not built")
                self.assertTrue(blob in dll.read_bytes(),
                                f"{dll.name} is not built from this table (run scripts/build_vvfp_story_upgrades.ps1)")


if __name__ == "__main__":
    unittest.main()
