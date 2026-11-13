"""The Cave Explorers (vv1_more_island_events): the owner's island event for A New Home (2026-11-12).

Static (always run):
  * the words: the companion's table (native/vvfp_more_island_events/cave_text.inc) is what
    scripts/build_more_island_events.py makes of src/vv_cave_explorers.py, every piece in every form is a translation
    row of its own (route "key", A New Home only), and the owner's wording is intact (the broken placeholders fixed);
  * the odds: the owner's table (Proceed: 50% A / 50% B; A: 10% argument, 80% make up, 10% chasm; B: 10% map, 30%
    coins, 30% treasure map, 30% food; return: 50/50 food or tech; keep: 50% researchers, 25% both die, 25% name2 dies),
    and the companion rolls the same numbers;
  * Game Mechanics: the event is listed only with the patch, with every branch's chance and its condition.

EMULATED (unicorn, the stock A New Home executable, the shipped DLL; tests/story_emulator.py):
  * WHO: never before The Cave puzzle is done; never without two villagers of 18 or more at most 5 years apart who
    may go (alive, present, not carrying a baby, not the Golden Child); the pair drawn among the ordered pairs;
  * THE DRAW: the encounter setup's rand(m + k) takes this event at m + 1 when both events can happen, at m when only
    it can;
  * THE POPUP through the game's own click handler, OK and constructor sites: each question's pages with OK, then its
    two answers (relabelled and centred as the constructor places them), every path to every ending, the close;
  * EVERY EFFECT: the awards (normal, large 2x, huge 3x, within the game's range), the deaths (health 0: a body and a
    grave) and the disappearances (no body, told to the Cause of Death companion), nothing in the endings where
    nothing happens;
  * THE PAGES: every page of every path, with the longest names A New Home holds, fits the popup's page, and the pages
    together hold the owner's whole text.

The live game is NOT exercised here.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_aspiring_adventurer as adv  # noqa: E402
import vv_cave_explorers as cave  # noqa: E402
import vv_translations as vt  # noqa: E402
from test_aspiring_adventurer import (BUILDER, DLL, HAVE_EMULATOR, HAVE_STOCK, NAMES, TOP, Village,  # noqa: E402
                                      wrap_lines)

if HAVE_EMULATOR:
    from story_emulator import STACK_TOP

NATIVE = ROOT / "native" / "vvfp_more_island_events"
WIDTH, LINES = 46, 9                       # A New Home's page (ADV_VV1)
TITLE_LINE = "The Cave Explorers\n"

# The rolls' values: the run's ending, the find, the kept ending (rand(100) thresholds 10/90, 10/40/70, 50/75).
A_END = {"ARGUE": 0, "MAKEUP": 50, "CHASM": 95}
FIND = {"FIND_MAP": 0, "FIND_COINS": 20, "FIND_TREASURE": 50, "FIND_FOOD": 80}
KEEP = {"KEEP_RESEARCH": 0, "KEEP_BOTH": 60, "KEEP_ONE": 80}


def cave_rolls(*, pair=0, scream=True, screamer=0, wrong=0, end="MAKEUP", faller=0, finder=0, find="FIND_COINS",
               find_award=0, return_food=True, return_award=0, keep="KEEP_RESEARCH", keep_award=0) -> list[int]:
    """The rolls cave_begin draws, in its order (A New Home's ranges always hold more than one amount)."""
    out = [pair, 0 if scream else 99, screamer, wrong, A_END[end], faller, finder, FIND[find]]
    out += [] if find == "FIND_MAP" else [find_award]
    out += [0 if return_food else 1, return_award, KEEP[keep], keep_award]
    return out


# ---- Static ----------------------------------------------------------------------------------------------------

class TheWords(unittest.TestCase):
    def test_the_companions_table_is_generated_from_the_one_source(self) -> None:
        self.assertEqual((NATIVE / "cave_text.inc").read_text(encoding="utf-8"), BUILDER.cave_text_inc())

    def test_every_piece_is_a_key_row_with_its_english(self) -> None:
        rows = {r["stem"]: r for r in vt.load_patcher_strings()}
        for stem, _key, english, _names in cave.rows():
            with self.subTest(stem=stem):
                self.assertIn(stem, rows)
                self.assertEqual(rows[stem]["english"], english)
                self.assertEqual(rows[stem].get("route"), "key")
                self.assertEqual(rows[stem]["games"], ["vv1"])

    def test_only_letters_a_new_homes_font_draws(self) -> None:
        for key, template in cave.TEXTS:
            with self.subTest(key=key):
                self.assertTrue(template.isascii())
                self.assertNotIn("  ", template)
                self.assertNotIn("(", re.sub(r"\{[^}]*\}", "", template))      # no owner's note is shown

    def test_the_owners_wording(self) -> None:
        names = {"a": "Ana", "b": "Ben"}
        sexes = {"a": "f", "b": "m"}
        self.assertEqual(cave.fill("KEEP_BOTH", names, sexes),
                         "Ben suddenly feels a strange pain in their chest. Over the next few days he develops a high "
                         "fever and convulsions. No matter what the healers do, Ben becomes weaker and weaker, until he "
                         "passes away in agony. Ana, in her guilt, stops eating until she too, quietly passes away. The "
                         "villagers mourn for them both, and upon discovering the stolen artifacts, perform a "
                         "complicated ritual to appease any angered spirits. Hopefully, this will put them, and poor "
                         "Ana and Ben, to rest in peace.")
        self.assertTrue(cave.fill("KEEP_ONE", names, sexes).endswith("angered spirits. Hopefully, this will put them, "
                                                                     "and poor Ben, to rest in peace."))
        self.assertIn("The villagers mourn for him, and upon", cave.fill("KEEP_ONE", names, sexes))
        self.assertIn("Ben informs the researchers about the objects Ana and Ben found.",
                      cave.fill("KEEP_RESEARCH", names, sexes))
        self.assertTrue(cave.fill("FIND_FOOD", names, award=7).startswith("a sack of preserved food! Ana and Ben haul "
                                                                         "the large sack back to the village"))
        self.assertIn("Your villagers gain 9 of tech points.", cave.fill("FIND_TREASURE", names, award=9))
        self.assertIn("Your village gains 9 tech points.", cave.fill("FIND_COINS", names, award=9))
        self.assertIn("After much reflection, she thanks him for setting their mind straight.",
                      cave.fill("DONT", names, sexes))
        self.assertIn("And neither should you,\" he says.", cave.fill("DONT", names, sexes))
        self.assertEqual(cave.fill("CHASM", {"c": "Ben", "d": "Ana"}, {"c": "m", "d": "f"}),
                         "As they burst out of the cave, they flop onto what seems to be solid ground. However, Ben's "
                         "foot slips and he falls down a slippery chasm. Horrified, Ana has no time to react before "
                         "she, too tumbles down the winding waterfall. All that's left of them is their fading screams "
                         "and a bowl of fresh berries.")
        self.assertIn("whatever Ben encountered seems to be coming closer", cave.fill("RUN", {"s": "Ben"}, {"s": "m"}))
        self.assertTrue(cave.fill("RUN", {"s": "Ana"}, {"s": "f"}).startswith(
            "\"Quick, run! Something's chasing us!\" she cries."))
        self.assertIn("\"This was YOUR idea!", cave.fill("ARGUE", names))
        self.assertTrue(cave.fill("ARGUE", names).endswith("I should have never agreed to come along!\" Ben shouts."))
        self.assertIn("Ben, frightened, starts crying.", cave.fill("ARGUE", names))
        self.assertIn("'You'll love it here. - Ana and Ben'", cave.fill("FIND_MAP", names))
        self.assertIn("a bundle of strange devices at their doorsteps. Your villagers gain 5 tech points.",
                      cave.fill("RETURN_TECH", names, award=5))
        self.assertIn("a bundle of food at their doorsteps. Your villagers gain 5 food.",
                      cave.fill("RETURN_FOOD", names, award=5))
        self.assertEqual([cave.english(k, "") for k in ("LABEL_EXPLORE", "LABEL_DONT", "LABEL_PROCEED", "LABEL_STAY",
                                                         "LABEL_LEFT", "LABEL_RIGHT", "LABEL_RETURN", "LABEL_KEEP")],
                         ["Explore the Cave", "Don't explore", "Proceed Further", "Stay Here",
                          "Run towards the left path", "Run towards the right path", "You're right, I'll return them.",
                          "Curses schmurses. I'm keeping them."])


class TheOdds(unittest.TestCase):
    def test_the_owners_table(self) -> None:
        c = cave.outcome_chances()
        self.assertEqual(c["PROCEED"], {"A": 50.0, "FIND_MAP": 5.0, "FIND_COINS": 15.0, "FIND_TREASURE": 15.0,
                                        "FIND_FOOD": 15.0})
        self.assertEqual(c["RUN"], {"ARGUE": 10.0, "MAKEUP": 80.0, "CHASM": 10.0})
        self.assertEqual(c["RETURN"], {"RETURN_FOOD": 50.0, "RETURN_TECH": 50.0})
        self.assertEqual(c["KEEP"], {"KEEP_RESEARCH": 50.0, "KEEP_BOTH": 25.0, "KEEP_ONE": 25.0})
        self.assertEqual(cave.AWARDS["FIND_TREASURE"], ("tech", "huge"))
        self.assertEqual(cave.AWARDS["FIND_FOOD"], ("food", "large"))
        self.assertEqual(adv.award_range(1, "tech", "huge"), (1500, 14997))
        self.assertEqual(adv.award_range(1, "food", "large"), (400, 3000))

    def test_the_companion_rolls_the_same_odds(self) -> None:
        core = (NATIVE / "cave_core.inc").read_text(encoding="utf-8")
        for needle in ("cave.scream_a = adv_percent(g, 50);", "cave.screamer = g->rand_below(2);",
                       "cave.wrong = g->rand_below(4);",
                       "roll < 10 ? CAVE_END_ARGUE : (roll < 90 ? CAVE_END_MAKEUP : CAVE_END_CHASM)",
                       "cave.faller = g->rand_below(2);", "cave.finder = g->rand_below(2);",
                       "roll < 10 ? CAVE_MAP : (roll < 40 ? CAVE_COINS : (roll < 70 ? CAVE_TREASURE : CAVE_FOOD))",
                       "adv_award_roll(g, ADV_KIND_TECH, 1)", "adv_award_roll(g, ADV_KIND_TECH, 3)",
                       "adv_award_roll(g, ADV_KIND_FOOD, 2)", "cave.return_food = g->rand_below(2) == 0;",
                       "roll < 50 ? CAVE_RESEARCH : (roll < 75 ? CAVE_BOTH_DIE : CAVE_ONE_DIES)",
                       "#define CAVE_ADULT_UNITS 360", "#define CAVE_GAP_UNITS 100"):
            self.assertIn(needle, core)


class TheMechanicsPage(unittest.TestCase):
    def test_listed_only_with_the_patch_in_a_new_home(self) -> None:
        import vv_game_mechanics_events_vv1 as vv1
        event = next(e for e in vv1.EVENTS if e.title == cave.TITLE)
        self.assertEqual(event.only_with, "vv1_more_island_events")
        text = event.text + " " + " ".join(s if isinstance(s, str) else s.text for s in event.subs)
        for words in ("The Cave puzzle", "18 villager years", "5 villager years", "not the Golden Child",
                      "not nursing a baby", "Proceed Further", "50%", "argue 10%", "make up 80%",
                      "the chasm 10%", "a map 10%", "gold coins 30%", "a treasure map 30%", "preserved food 30%",
                      "200 to 1,500 food", "500 to 4,999 tech points", "1,500 to 14,997 tech points",
                      "400 to 3,000 food", "the researchers 50%", "both die 25%", "dies 25%", "no grave"):
            with self.subTest(words=words):
                self.assertIn(words, text)
        for game in (2, 3, 4, 5):
            catalog = __import__(f"vv_game_mechanics_events_vv{game}")
            self.assertFalse(any(e.title == cave.TITLE for e in catalog.EVENTS), game)


# ---- Emulated -----------------------------------------------------------------------------------------------------

class CaveVillage(Village):
    """A New Home with the companion started, The Cave puzzle done (or not), real-looking answer buttons whose
    relabel and move are recorded."""

    RECT = (100, 50, 550, 450)            # the dialog's left, top, right, bottom (+0x14 .. +0x20)

    def __init__(self, cave_open: bool = True):
        super().__init__(1)
        p = self.p
        p.write(self.world + 0x9FA8, b"\x01" if cave_open else b"\x00")
        code = p.alloc(64)
        p.write(code, b"\xC3" * 64)
        self.labels: list[tuple[int, str]] = []
        self.moves: list[tuple[int, int, int]] = []
        p.stub(0x4015A0, self._label)
        p.stub(code, lambda pr: (100 + 2 * len(self._text.get(pr.reg("ecx"), "")), 0))     # width
        p.stub(code + 8, lambda pr: (20, 0))                                                  # height
        p.stub(code + 16, self._move)
        self._text: dict[int, str] = {}
        self.buttons = []
        for _ in range(3):
            vtable = p.alloc(0x20)
            obj = p.alloc(0x40)
            p.put32(obj, vtable)
            p.put32(vtable + 4, code + 16)
            p.put32(vtable + 12, code)
            p.put32(vtable + 16, code + 8)
            self.buttons.append(obj)

    def _label(self, pr):
        text = pr.cstring(pr.arg(0))
        self._text[pr.reg("ecx")] = text
        self.labels.append((pr.reg("ecx"), text))
        return 0, 8

    def _move(self, pr):
        self.moves.append((pr.reg("ecx"), pr.arg(0) - (1 << 32) if pr.arg(0) >> 31 else pr.arg(0), pr.arg(1)))
        return 0, 8

    def begin(self, rolls: list[int], draw: int = TOP) -> bool:
        p = self.p
        self.ui.clear()
        self.dlg = p.alloc(0x6000)
        p.put32(self.dlg + 0x50A4, self.world)
        p.put32(self.dlg + 0x50A8, self.base)
        a, b, ok = self.buttons
        for o, v in ((0x54, 2), (0x58, 3), (0x5C, 4), (0x50BC, a), (0x50C0, b), (0x50C4, ok)):
            p.put32(self.dlg + o, v)
        for k, v in enumerate(self.RECT):
            p.put32(self.dlg + 0x14 + 4 * k, v)
        self.rolls = [draw] + list(rolls)
        # Every popup laid out with the longest names: more than the emulator's default cap of instructions.
        p.call(0x4189E0, [], ecx=self.dlg, limit=8_000_000)
        if p.u32(self.dlg + 0x5094) != 0x7F4B1A2E:
            return False
        esp = STACK_TOP - 0x3000 - 4
        p.put32(esp, b)
        p.set_reg("esp", esp)
        p.set_reg("ecx", self.dlg)
        p.run(0x41A87C, 0x41A881)
        return True

    def attached(self) -> set[int]:
        a, b, ok = self.buttons
        up = {a}                               # the constructor attached the first answer before the site
        for event in self.ui:
            if event[0] == "add":
                up.add(event[1])
            elif event[0] == "remove":
                up.discard(event[1])
        return up

    def answers_up(self) -> bool:
        a, b, ok = self.buttons
        up = self.attached()
        return a in up and b in up and ok not in up

    def cave_state(self) -> list[int]:
        out = self.p.alloc(20 * 4)
        self.p.export("VvfpCaveExplorersState", out)
        return [struct.unpack("<i", self.p.read(out + 4 * k, 4))[0] for k in range(20)]

    def cave_possible(self) -> int:
        return self.p.export("VvfpCaveExplorersPossible")

    def cave_pages(self, which: int) -> list[str]:
        out, k = [], 0
        while True:
            at = self.p.export("VvfpCaveExplorersPage", which, k)
            if not at:
                return out
            out.append(self.p.cstring(at, 4000))
            k += 1

    def labels_shown(self) -> tuple[str, str]:
        return (self.p.cstring(self.dlg + 0x4E92, 300), self.p.cstring(self.dlg + 0x4F92, 300))

    def play_cave(self, rolls: list[int], answers: list[int]) -> list[str]:
        """The whole event: every page shown, in order, until the close (each as one line of words, the title and A
        New Home's own line breaks taken out); the answers clicked in turn whenever the two answers are up."""
        if not self.begin(rolls):
            raise AssertionError("the event was not drawn")
        self.asked: list[tuple[str, str]] = []
        seen = [self.shown()]
        answers = list(answers)
        for _ in range(60):
            if self.answers_up():
                self.asked.append(self.labels_shown())
                self.click(answers.pop(0) + 1)          # 0 the first answer: the click handler's button 1
            else:
                self.click(0)
                if self.closed():
                    break
            seen.append(self.shown())
        self.closed_at_end = self.closed()
        self.left_over = answers
        return [re.sub(r"\s+", " ", page.replace(TITLE_LINE, "")).strip() for page in seen]


def joined(pages: list[str]) -> str:
    """The pages as one text (a page the dialog shows twice -- with OK, then with the answers -- once)."""
    out: list[str] = []
    for page in pages:
        if not out or out[-1] != page:
            out.append(page)
    return " ".join(out)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Who(unittest.TestCase):
    def village(self, cave_open: bool = True) -> CaveVillage:
        v = CaveVillage(cave_open)
        v.villager(0, "Ana", True, years=20)
        v.villager(1, "Ben", False, years=24)
        return v

    def test_never_before_the_cave_puzzle(self) -> None:
        v = self.village(cave_open=False)
        self.assertEqual(v.cave_possible(), 0)
        self.assertTrue(v.begin([0] * 20))                 # the draw goes to the only event that can happen
        self.assertTrue(v.shown().startswith("The Aspiring Adventurer\n"))
        v = self.village(cave_open=True)
        self.assertEqual(v.cave_possible(), 1)

    def test_two_who_may_go_close_in_age(self) -> None:
        cases = (
            ("both 20", dict(years=20), 1),
            ("5 years apart", dict(years=25), 1),
            ("6 years apart", dict(years=26), 0),
            ("17 years old", dict(years=17), 0),
            ("nursing", dict(years=20, carrying=500), 0),
            ("the Golden Child", dict(years=20, special=(0x36C, 4, 0xC7)), 0),
            ("dead", dict(years=20, health=0), 0),
        )
        for what, kw, possible in cases:
            with self.subTest(what=what):
                v = CaveVillage()
                v.villager(0, "Ana", True, years=20)
                v.villager(1, "Ben", **kw)
                self.assertEqual(v.cave_possible(), possible)
        v = CaveVillage()
        v.villager(0, "Ana", True, years=20)
        self.assertEqual(v.cave_possible(), 0)                # one alone: never
        v.villager(1, "Ben", years=20)
        v.p.write(v.rec(1) + 0x28, b"\x00")
        self.assertEqual(v.cave_possible(), 0)                # the absent never go

    def test_the_pair_and_the_draw(self) -> None:
        v = self.village()
        v.villager(2, "Cal", False, years=40)                 # too far from both: never in a pair
        v.play_cave(cave_rolls(pair=1), [1])
        state = v.cave_state()
        self.assertEqual(state[:4], [1, 0, 0, 1])             # name1 Ben, name2 Ana
        self.assertEqual(v.asked[0], ("Explore the Cave", "Don't explore"))
        # With both events possible, the draw m is The Aspiring Adventurer, m + 1 The Cave Explorers.
        v = self.village()
        v.villager(2, "Cal", False, years=40)
        self.assertTrue(v.begin([0] * 20, draw=TOP))
        self.assertTrue(v.shown().startswith(TITLE_LINE))


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class EveryPath(unittest.TestCase):
    def village(self) -> CaveVillage:
        v = CaveVillage()
        v.villager(0, "Ana", True, years=20)
        v.villager(1, "Ben", False, years=24)
        return v

    def assert_untouched(self, v: CaveVillage, before) -> None:
        self.assertEqual(v.stores(), before)
        for i in (0, 1):
            self.assertEqual((v.health(i), v.present(i)), (100, 1))
        self.assertEqual(v.vanished, [])

    def test_dont_explore(self) -> None:
        v = self.village()
        before = v.stores()
        text = joined(v.play_cave(cave_rolls(), [1]))
        self.assertEqual(v.asked, [("Explore the Cave", "Don't explore")])
        self.assertTrue(v.closed_at_end)
        self.assert_untouched(v, before)
        self.assertIn(cave.fill("INTRO", {"a": "Ana", "b": "Ben"}, {"a": "f", "b": "m"}), text)
        self.assertIn(cave.fill("DONT", {"a": "Ana", "b": "Ben"}, {"a": "f", "b": "m"}), text)
        self.assertEqual(v.cave_state()[17], 0)

    def test_the_find(self) -> None:
        names, sexes = {"a": "Ana", "b": "Ben", "r": "Ben"}, {"a": "f", "b": "m"}
        for find, draw, kind, size in (("FIND_COINS", 0, "tech", "normal"), ("FIND_COINS", TOP, "tech", "normal"),
                                       ("FIND_TREASURE", 11, "tech", "huge"), ("FIND_TREASURE", TOP, "tech", "huge"),
                                       ("FIND_FOOD", 0, "food", "large"), ("FIND_FOOD", TOP, "food", "large")):
            with self.subTest(find=find, draw=draw):
                v = self.village()
                before = v.stores()
                text = joined(v.play_cave(cave_rolls(scream=False, finder=1, find=find, find_award=draw), [0, 0]))
                self.assertEqual(v.asked, [("Explore the Cave", "Don't explore"), ("Proceed Further", "Stay Here")])
                self.assertTrue(v.closed_at_end)
                state = v.cave_state()
                award = state[11]
                lo, hi = adv.award_range(1, kind)
                times = adv.AWARD_SIZES[size]
                self.assertEqual(award, times * (hi if draw == TOP else lo + draw))
                lo2, hi2 = adv.award_range(1, kind, size)
                self.assertTrue(lo2 <= award <= hi2)
                after = v.stores()
                self.assertEqual((after[0] - before[0], after[1] - before[1]),
                                 (award, 0) if kind == "food" else (0, award))
                self.assertIn(cave.fill("DEEPER", names), text)
                self.assertIn(cave.fill("B_SEARCH", names) + " " + cave.fill(find, names, sexes, award), text)
                for i in (0, 1):
                    self.assertEqual((v.health(i), v.present(i)), (100, 1))

    def test_the_map_takes_both_away(self) -> None:
        v = self.village()
        before = v.stores()
        v.play_cave(cave_rolls(scream=False, find="FIND_MAP"), [0, 0])
        self.assertEqual(v.stores(), before)                    # no award
        self.assertEqual((v.present(0), v.present(1)), (0, 0))  # gone, no bodies: no graves
        self.assertEqual(sorted(v.vanished), [(1, 0, cave.VANISHED["FIND_MAP"]), (1, 1, cave.VANISHED["FIND_MAP"])])

    def test_the_scream_and_the_run(self) -> None:
        for end in ("ARGUE", "MAKEUP", "CHASM"):
            for side, label in ((0, "left"), (1, "right")):
                for screamer, wrong in ((0, 0), (1, 3)):
                    with self.subTest(end=end, side=side, screamer=screamer):
                        v = self.village()
                        before = v.stores()
                        text = joined(v.play_cave(cave_rolls(screamer=screamer, wrong=wrong, end=end, faller=1),
                                                  [0, 0, side]))
                        self.assertEqual(v.asked[2], ("Run towards the left path", "Run towards the right path"))
                        self.assertTrue(v.closed_at_end)
                        s = "Ana" if screamer == 0 else "Ben"
                        o = "Ben" if screamer == 0 else "Ana"
                        names = {"a": "Ana", "b": "Ben", "s": s, "o": o, "c": "Ben", "d": "Ana"}
                        sexes = {"a": "f", "b": "m", "s": "f" if s == "Ana" else "m", "c": "m", "d": "f"}
                        self.assertIn(cave.fill("A_SCREAM", names, sexes) + " "
                                      + cave.fill(cave.WRONG[wrong], names), text)
                        self.assertIn(cave.fill("RUN", names, sexes), text)
                        self.assertIn(f"Ana and Ben run down the {label} path screaming like little children.", text)
                        self.assertIn(cave.fill(end, names, sexes), text)
                        self.assertEqual(v.stores(), before)               # never food from the berries
                        if end == "CHASM":
                            self.assertEqual((v.present(0), v.present(1)), (0, 0))
                            self.assertEqual(sorted(v.vanished), [(1, 0, cave.VANISHED["CHASM"]),
                                                                  (1, 1, cave.VANISHED["CHASM"])])
                        else:
                            self.assert_untouched(v, before)

    def test_stay_and_return(self) -> None:
        for food, draw in ((True, 0), (False, TOP)):
            with self.subTest(food=food):
                v = self.village()
                before = v.stores()
                text = joined(v.play_cave(cave_rolls(return_food=food, return_award=draw), [0, 1, 0]))
                self.assertEqual(v.asked[2], ("You're right, I'll return them.", "Curses schmurses. I'm keeping them."))
                kind = "food" if food else "tech"
                lo, hi = adv.award_range(1, kind)
                award = v.cave_state()[13]
                self.assertEqual(award, hi if draw == TOP else lo)
                after = v.stores()
                self.assertEqual((after[0] - before[0], after[1] - before[1]), (award, 0) if food else (0, award))
                self.assertIn(cave.fill("STAY", {"a": "Ana", "b": "Ben"}, {"b": "m"}), text)
                self.assertIn(cave.fill("RETURN_FOOD" if food else "RETURN_TECH", {"b": "Ben"}, {"b": "m"}, award), text)

    def test_stay_and_keep(self) -> None:
        for keep in ("KEEP_RESEARCH", "KEEP_BOTH", "KEEP_ONE"):
            with self.subTest(keep=keep):
                v = self.village()
                before = v.stores()
                text = joined(v.play_cave(cave_rolls(keep=keep, keep_award=5), [0, 1, 1]))
                self.assertTrue(v.closed_at_end)
                award = v.cave_state()[15]
                self.assertEqual(award, adv.award_range(1, "tech")[0] + 5)
                names, sexes = {"a": "Ana", "b": "Ben"}, {"a": "f", "b": "m"}
                self.assertIn(cave.fill("KEEP", names) + ", " + cave.fill(keep, names, sexes, award), text)
                after = v.stores()
                if keep == "KEEP_RESEARCH":
                    self.assertEqual((after[0] - before[0], after[1] - before[1]), (0, award))
                    self.assert_untouched(v, after)
                    continue
                self.assertEqual(v.stores(), before)
                self.assertEqual(v.health(1), 0)                    # name2 dies: the body lies, a grave comes
                self.assertEqual(v.present(1), 1)
                self.assertEqual(v.health(0), 0 if keep == "KEEP_BOTH" else 100)
                self.assertEqual(v.present(0), 1)
                self.assertEqual(v.vanished, [])

    def test_the_answers_are_relabelled_and_centred(self) -> None:
        v = self.village()
        v.play_cave(cave_rolls(), [0, 1, 1])
        a, b, _ok = v.buttons
        self.assertEqual([t for _, t in v.labels], ["Proceed Further", "Stay Here", "You're right, I'll return them.",
                                                    "Curses schmurses. I'm keeping them."])
        left, top, right, bottom = CaveVillage.RECT
        width, height = right - left, bottom - top
        w = 100 + 2 * len("Curses schmurses. I'm keeping them.")
        self.assertIn((b, width // 2 - w // 2, height - 2 * 20), v.moves)
        w = 100 + 2 * len("You're right, I'll return them.")
        self.assertIn((a, width // 2 - w // 2, height - 20 // 2 - 3 * 20), v.moves)

    def test_one_answer_a_click(self) -> None:
        """Every answer is made once: the third question's answer ends it, and a further click changes nothing."""
        v = self.village()
        v.play_cave(cave_rolls(keep="KEEP_ONE"), [0, 1, 1])
        self.assertEqual(v.cave_state()[16], 3)
        self.assertEqual(v.left_over, [])


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Pages(unittest.TestCase):
    def test_every_page_fits_with_the_longest_names(self) -> None:
        name = NAMES[1]
        cases = [dict(scream=s, screamer=k, wrong=w, end=e, find=f)
                 for s in (True, False) for k in (0, 1) for w in range(4) for e in A_END for f in FIND]
        cases += [dict(return_food=r, keep=k) for r in (True, False) for k in KEEP]
        for kw in cases:
            v = CaveVillage()
            v.villager(0, name, True, years=20)
            v.villager(1, name[::-1], False, years=20)
            self.assertTrue(v.begin(cave_rolls(find_award=TOP, return_award=TOP, keep_award=TOP, **kw)))
            for which in range(10):
                for page in v.cave_pages(which):
                    with self.subTest(kw=kw, which=which):
                        self.assertLessEqual(wrap_lines(page, WIDTH), LINES, page)
            shown = v.shown()
            for line in shown.split("\n"):
                self.assertLessEqual(len(line), WIDTH)

    def test_the_pages_hold_the_whole_text(self) -> None:
        v = CaveVillage()
        v.villager(0, "Ana", True, years=20)
        v.villager(1, "Ben", False, years=20)
        v.begin(cave_rolls(scream=True, end="ARGUE"))
        names, sexes = {"a": "Ana", "b": "Ben", "s": "Ana", "o": "Ben"}, {"a": "f", "b": "m", "s": "f"}
        sets = {k: " ".join(v.cave_pages(k)).replace("\n", " ") for k in range(10)}
        self.assertEqual(sets[0], cave.fill("INTRO", names, sexes))
        self.assertEqual(sets[1], cave.fill("EXPLORE_1", names) + " " + cave.fill("EXPLORE_2", names, sexes))
        self.assertEqual(sets[2], cave.fill("DEEPER", names) + " " + cave.fill("A_SCREAM", names, sexes) + " "
                         + cave.fill("WRONG_1", names) + " " + cave.fill("RUN", names, sexes))
        self.assertEqual(sets[6], cave.fill("RUN_LEFT", names) + " " + cave.fill("ARGUE", names) + " "
                         + cave.fill("ARGUE_2", names))


if __name__ == "__main__":
    unittest.main()
