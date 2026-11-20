"""Game Mechanics' "Jobs and training" group (src/vv_game_mechanics_training.py; the owner, 2026-11-18): the job
picker's skill rule in all five games, and The Tree of Life's and New Believers' hidden "untrained" mark with each
villager's state read from the save.

  * The stock exes: the 86-in-100 preference override, the skill floor (A New Home above 1, the others above 5) and
    the (skill + 40) roll, byte for byte; the dispatcher's refusal while the mark is 1 and the villager set-up's
    write of 1 in The Tree of Life and New Believers.
  * The page and the general page: the rule lines in every game, the mark lines only in VV4 and VV5.
  * The save: "Untrained now" names exactly the villagers whose saved task field is 1 (believers only in VV5).
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_training as training  # noqa: E402
import vv_last_names as ln  # noqa: E402
import test_game_mechanics_life as t  # noqa: E402
from test_game_mechanics_carried import STOCK, STOCK_ABSENT, image  # noqa: E402

# (va, bytes) in each stock exe.
SITES = {
    1: ((0x439C40, "83f855 7f3b"), (0x439C80, "83fe01 0f8e99feffff 6a64 e88092fcff 83c404 83c628")),
    2: ((0x449DCD, "83f855"), (0x449E0F, "83fe05 7e41 6a64 e88593fbff 83c628")),
    3: ((0x45985B, "83f855 7f0d"), (0x45986D, "83fe05 7e46 6a64 e8579afaff 83c628")),
    4: ((0x461E4A, "83f855 7f1a"), (0x461E69, "83fe05 7e46 6a64 e85b18faff 83c628"),
        (0x45F534, "c786541c000001000000")),
    5: ((0x46A575, "83f855 7f1a"), (0x46A594, "83fe05 7e46 6a64 e8c090f9ff 83c628"),
        (0x4687D3, "c786541c000001000000")),
}
# The dispatcher's refusal: cmp [reg+0x1C54], ebp (ebp = 1 there) at VV4 0x4639D2 and VV5 0x46C565.
REFUSAL = {4: (0x4639D2, "39a9541c0000"), 5: (0x46C565, "39a8541c0000")}


def at(game: int, va: int, n: int) -> bytes:
    data, base, sections = image(game)
    rva = va - base
    raw = next(r + rva - s for s, size, r, _ in sections if s <= rva < s + size)
    return data[raw:raw + n]


@unittest.skipUnless(all(p.is_file() for p in STOCK.values()), STOCK_ABSENT)
class StockCode(unittest.TestCase):
    def test_the_picker_rule(self) -> None:
        for game, sites in SITES.items():
            for va, hexes in sites:
                with self.subTest(game=game, va=hex(va)):
                    want = bytes.fromhex(hexes.replace(" ", ""))
                    self.assertEqual(at(game, va, len(want)), want)

    def test_the_dispatcher_refuses_an_untrained_villager(self) -> None:
        for game, (va, hexes) in REFUSAL.items():
            with self.subTest(game=game):
                want = bytes.fromhex(hexes)
                self.assertEqual(at(game, va, len(want)), want)


def lines(game: int, data=None) -> list[gm.Fact]:
    case = unittest.TestCase()
    try:
        return [f for f in t.page(case, game, t.fixture(game) if data is None else data) if f.group == gm.TRAINING]
    finally:
        case.doCleanups()


class Page(unittest.TestCase):
    def test_rule_in_every_game_and_the_mark_in_vv4_vv5(self) -> None:
        for game in range(1, 6):
            for where, facts in (("page", lines(game)),
                                 ("general", [f for f in gm.general(game, now=t.NOW) if f.group == gm.TRAINING])):
                with self.subTest(game=game, where=where):
                    text = "\n".join(f.text for f in facts)
                    self.assertIn("replaces the game's own pick 86 times in 100", text)
                    self.assertIn(f"skill is above {1 if game == 1 else 5}", text)
                    self.assertIn("(skill + 40) times in 100", text)
                    self.assertEqual("untrained\" mark" in text, game in (4, 5))
                    self.assertEqual("will not seek a mate on their own unless they are trained" in text, game == 5)
                    self.assertTrue(all(f.confirmed for f in facts))
                    self.assertNotIn("0x", text)

    def test_work_first_line_follows_the_patch(self) -> None:
        for has, shown in ((frozenset(), False), (frozenset({"vv4_work_first"}), True), (None, False),
                           (frozenset({"vv4_builders_and_healers_work_first"}), False)):
            village = gm.Village(Path("."), 4, 1, Path("4.ldw"), b"", has, t.NOW, general=True)
            text = "\n".join(f.text for f in training.facts(village))
            self.assertEqual("the mark no longer blocks the villager's preferred job" in text, shown)


class Save(unittest.TestCase):
    def test_untrained_now_names_the_marked_villagers(self) -> None:
        for game in (4, 5):
            with self.subTest(game=game):
                data = t.fixture(game)
                entries = ln._entries(game, bytes(data))
                believers = [a for a in entries if game == 4 or data[a - 0x1F] == 0]
                for a in believers:
                    struct.pack_into("<i", data, a + training.MARK, 0)
                for a in believers[:2]:
                    struct.pack_into("<i", data, a + training.MARK, 1)
                struct.pack_into("<i", data, believers[2] + training.MARK, 3)      # a task the player gave: trained
                names = [ln._cstr(data, a, 0x18) for a in believers[:2]]
                who = "believers" if game == 5 else "villagers"
                line = next(f for f in lines(game, data) if f.text.startswith("Untrained now:"))
                self.assertEqual(line.text, f"Untrained now: 2 of the {len(believers)} {who}: {', '.join(names)}.")
                self.assertEqual(line.verified, gm.SAVE)
                import vv_game_mechanics_life as life
                self.assertEqual(life.claim_template(line.text),
                                 f"Untrained now: 2 of the {len(believers)} {who}: <villagers>.")
                for a in believers[:2]:
                    struct.pack_into("<i", data, a + training.MARK, 0)
                line = next(f for f in lines(game, data) if f.text.startswith("Untrained now:"))
                self.assertIn("every one is trained", line.text)

    def test_no_status_line_in_vv1_to_vv3(self) -> None:
        for game in (1, 2, 3):
            with self.subTest(game=game):
                self.assertFalse(any(f.text.startswith("Untrained now:") for f in lines(game)))


if __name__ == "__main__":
    unittest.main()
