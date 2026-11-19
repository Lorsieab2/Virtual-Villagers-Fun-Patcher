"""With Scrolling Popups installed, a popup is never split into pages (v1.35.97).

The owner: "the multiple popups for Aspiring Adventurer should be merged into single ones" -- with Scrolling Popups on,
every More Island Events question is one popup and every result one popup; a branching Custom Island Event's popup is
one page.  Without the patch, the pages still fit the screen as before.  "VVFP Scrolling Popups.dll" is asked
(VvfpScrollingPopupsInstalled) when the pages are laid out.

EMULATED (unicorn, the stock executables):
  * More Island Events (the shipped DLL, Scrolling Popups' export stood in for), all five games: The Aspiring
    Adventurer's question is one page and each answer's result one page, holding exactly the words the paged popups
    hold; the effects come with that one page (the answer's click) and the award is paid once (every event of the
    companion lays its pages out through the same adv_popup);
  * the Story / Cheat Upgrades companion (TEST build): a long popup of a branching event is several pages without
    the patch and one page with it, with the same words; its effect still made once, with that page.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_aspiring_adventurer as aa  # noqa: E402
import vv_cie_graph as cg  # noqa: E402
from test_story_cie_graph_runtime import Run, emulated, have_stock, norm, stores  # noqa: E402

FAKE_SP = 0x0EB00000
NEEDS_RUN = aa.HAVE_EMULATOR and aa.HAVE_STOCK and aa.DLL.is_file()


class ScrollingVillage(aa.Village):
    """A game with More Island Events started and "VVFP Scrolling Popups.dll" stood in for as installed."""

    def _cod(self) -> None:
        super()._cod()
        p = self.p
        module, proc = p.api_handlers["GetModuleHandleA"], p.api_handlers["GetProcAddress"]
        installed = p.alloc(16)

        def module2(pr):
            name = pr.cstring(pr.arg(0)) if pr.arg(0) else ""
            return (FAKE_SP, 4) if name == "VVFP Scrolling Popups.dll" else module(pr)

        def proc2(pr):
            if pr.arg(0) == FAKE_SP:
                return (installed if pr.cstring(pr.arg(1)) == "VvfpScrollingPopupsInstalled" else 0), 8
            return proc(pr)
        p.api_handlers["GetModuleHandleA"] = module2
        p.api_handlers["GetProcAddress"] = proc2
        p.stub(installed, lambda pr: (1, 0))


def words(pages) -> str:
    return re.sub(r"\s+", " ", " ".join(pages)).strip()


@unittest.skipUnless(NEEDS_RUN, "needs unicorn, pefile and the stock executables")
class MoreIslandEvents(unittest.TestCase):
    def pair(self, game: int):
        out = []
        for cls in (aa.Village, ScrollingVillage):
            v = cls(game)
            v.villager(0, "Ana", True)
            v.villager(1, "Ben")
            out.append(v)
        return out

    def test_the_aspiring_adventurer_one_popup_each(self) -> None:
        for game in aa.GAMES:
            for answer, roll in ((1, aa.rolls(hero=0, find=1, end=0, game=game)),
                                 (2, aa.rolls(hero=0, lost=True, lost_end=3, game=game))):
                with self.subTest(game=game, answer=answer):
                    paged, whole = self.pair(game)
                    paged_before, before = paged.stores(), whole.stores()
                    seen_paged = paged.play(roll, answer)
                    seen_whole = whole.play(roll, answer)
                    st = whole.state()
                    self.assertEqual((st[15], st[16 if answer == 1 else 17]), (1, 1), "one question, one result")
                    self.assertGreaterEqual(len(seen_paged), len(seen_whole))
                    self.assertEqual(len(seen_whole), 2)
                    self.assertEqual(words(seen_whole), words(seen_paged), "the same words, none lost")
                    self.assertTrue(whole.closed_at_end)
                    # The effects with that one page, once: the same changes as the paged popups made.
                    gained = tuple(a - b for a, b in zip(whole.stores(), before))
                    self.assertEqual(gained, tuple(a - b for a, b in zip(paged.stores(), paged_before)))
                    if answer == 1:
                        self.assertNotEqual(gained, (0, 0), "A1 pays the award")


@emulated
class CustomIslandEvents(unittest.TestCase):
    LONG = " ".join(f"(Name) walks past the {w} tree and keeps on walking for a long while, thinking about it."
                    for w in ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth",
                              "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth"))
    GRAPH = cg.load({
        "format": "vvfp-cie-graph", "version": 1, "title": "The Long Walk", "games": [1, 2, 3, 4, 5],
        "roles": {"subject": {"kind": "villager"}},
        "start": "s",
        "nodes": {"s": {"text": LONG + "\nAt the end (he/she) finds a basket of fruit.",
                        "effects": [{"do": "food", "amount": 100}]}},
    })

    def test_one_page_with_scrolling_popups(self) -> None:
        data = cg.compile_graph(self.GRAPH)
        # The Tree of Life's and New Believers' delivery of a popup this long reaches the game's own C runtime
        # (TlsGetValue), which this emulation does not run -- with or without the patch; their pager is the same code.
        for game in ("vv1", "vv2", "vv3"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                shown = {}
                for scroll in (0, 1):
                    run = Run(game)
                    run.p.export("VvfpStoryProbeGraphScroll", scroll)
                    run.force([])
                    food0, _tech0 = stores(run)
                    self.assertIsNone(run.queue(data))
                    shown[scroll] = run.play()
                    food1, _tech1 = stores(run)
                    self.assertEqual(food1 - food0, 100, "the effect once")
                    page = len(shown[scroll]) - 1
                    self.assertEqual(run.seen[page]["food"] - food0, 100, "made with the popup's last page")
                    if page > 0:
                        self.assertEqual(run.seen[page - 1]["food"] - food0, 0, "not before it")
                self.assertGreater(len(shown[0]), 1, "paged without the patch")
                self.assertEqual(len(shown[1]), 1, "one page with it")
                def text(pages):
                    return norm(" ".join(Run.strip(None, t, "The Long Walk") for _k, t, *_ in pages))
                self.assertEqual(text(shown[1]), text(shown[0]), "the same words, none lost")


if __name__ == "__main__":
    unittest.main()
