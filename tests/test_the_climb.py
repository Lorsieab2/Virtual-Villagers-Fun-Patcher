"""The Climb (vv2_more_island_events): the owner's island event for The Lost Children (2026-11-12).

Static (always run):
  * the words: the companion's table (native/vvfp_more_island_events/climb_text.inc) is what
    scripts/build_more_island_events.py makes of src/vv_the_climb.py, every piece in every form is a translation row
    of its own (route "key", The Lost Children only), and the owner's wording is intact, word for word;
  * the odds and the numbers: "Go with the plan" 50% the fall / 50% the summit, a large (2x) tech award, +10 to 20
    Research for the advice, the Trainee level 20, the cap 100, 18 years -- and the companion rolls the same;
  * Game Mechanics: the event is listed only with the patch, in The Lost Children only, with who may go, who never
    does, every branch with its chance and the rewards.

EMULATED (unicorn, the stock The Lost Children executable, the shipped DLL; tests/story_emulator.py):
  * WHO: Research 19 never, 20 yes; 17 years never, 18 yes; never the nursing, an Esteemed Elder's statue, the dead or
    the absent; one villager is enough; the villager drawn among those who may go;
  * THE DRAW: family A's draw 21 is kept for The Climb when only it can happen, and, when The Aspiring Adventurer can
    too, the game's rand(2) picks (0 the Adventurer, 1 The Climb); none: never kept;
  * THE POPUP through the game's own click handler, OK and constructor sites: the question's pages with OK, the two
    answers, the result's pages with OK, the close;
  * EVERY EFFECT, made in the answer's click (the click the Island Events log watches): the fall -- the game's own
    death (health 0: the body lies and gets a grave); the summit -- Research 100, the award through the game's tech
    writer within the large range and scaled by the game's own factor, the game's own village celebration called
    once (Old Friends' place); the advice -- +10 to 20 Research, at most 100; nothing else changes;
  * THE PAGES: every page with the longest name The Lost Children holds fits the popup's page, and the pages together
    hold the owner's whole text.

The live game is NOT exercised here.
"""
from __future__ import annotations

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
import vv_the_climb as climb  # noqa: E402
import vv_translations as vt  # noqa: E402
from test_aspiring_adventurer import (BUILDER, DLL, HAVE_EMULATOR, HAVE_STOCK, NAMES, TOP, Village,  # noqa: E402
                                      wrap_lines)

if HAVE_EMULATOR:
    from story_emulator import STACK_TOP

NATIVE = ROOT / "native" / "vvfp_more_island_events"
WIDTH, LINES = 46, 12                      # The Lost Children's page (ADV_VV2)
TITLE_LINE = "The Climb\n"
RESEARCH = 0x7F4
FALL, SUMMIT = 0, 99                       # rand(100) < 50 is the fall

# The owner's words (2026-11-12), typed from the owner's text: the curly apostrophe as ', the ellipsis as ..., the
# notes left out, the approved edits made, a sentence's first pronoun capitalised.  Ana is a woman.
OWNER = {
    "INTRO": "Ana is known for her crazy, spontaneous, yet sometimes genius ideas. She is an avid researcher and has "
             "been studying the tribe's history for a long time. She believes that two of the tribe's founders fell "
             "down the Great Falls, but nothing definitive is known about their origins. Ana proposes trying to "
             "retrace their steps by climbing the waterfall and offers to devise a plan. The others are skeptical "
             "about her claims and warn her not to take matters into her own hands without further proof. Ana knows "
             "that the plan could be dangerous, but what if she is right? Should she go through with her plan, or "
             "follow the other researchers' advice?",
    "PLAN": "Ana revises her plan until she believes it is practically foolproof. At dawn the next morning, she sneaks "
            "out of the hut before anyone else has woken up and makes her way toward the waterfall. Setting up her "
            "climbing gear, she makes the perilous ascent up the falls.",
    "FALL": "For several hours, she carefully scales the jagged rocks until she can almost see over the edge of the "
            "falls. Just a little further... Oops! Ana's hand loses its grip and she falls many dozens of meters to "
            "the hard, unforgiving ground. When the villagers wake up, they discover Ana's body and weep bitterly for "
            "their fallen colleague. She will be remembered as a passionate dreamer that dared to do the impossible.",
    "SUMMIT": "For several hours, she carefully scales the jagged rocks until she can almost see over the edge of the "
              "falls. Just a little further... With one last stretch, Ana climbs onto the final rock and stands in "
              "victory. From this height, she can see over the entire village and jungle canopy. She thinks she can "
              "even see other settlements from up here! Behind her, she hears the rushing of the falls echoing "
              "through a large cave mouth leading to somewhere unknown. Checking her notes and doing some quick "
              "calculations, she is almost certain the cave tunnel must lead somewhere close to the Southern Shore of "
              "Isola. Ana fervently writes down her deductions and makes a detailed sketch of the area before making "
              "the careful descent back home. That day, she presents her findings to the others, who work together to "
              "perfect her plan. Over several months they send an expedition team to the perilous peak, and confirm "
              "that Ana was right about everything. They name Ana a Distinguished Scientist, and recognize her "
              "achievements in a grand ceremony. Ana is certainly setting a name for herself throughout the entire "
              "scientific community! Your village gains 1234 tech points.",
    "ADVICE": "Ana admits that her plan still needs some refining. She goes back to the drawing board to double-check "
              "it. After scrutinizing it thoroughly, even she sees glaring flaws in its execution, and writes a report "
              "detailing all her mistakes. The next day she consults her senior colleagues to help her work out the "
              "kinks in her plan, and over time Ana learns many things from their strict guidance. It turns out she "
              "had much to learn, but was too blinded by ambition to notice her shortcomings. Ana promises to be "
              "more humble and learn from her elders before stubbornly taking matters into her own hands.",
}


def owner_text(key: str, form: str = "f", name: str = "Ana", award: int = 1234) -> str:
    """A whole ending as the companion composes it (the fall and the summit open with CLIMB)."""
    if key in ("FALL", "SUMMIT"):
        return climb.fill("CLIMB", form, name) + climb.CLIMB_JOIN + climb.fill(key, form, name, award)
    return climb.fill(key, form, name, award)


# ---- Static ----------------------------------------------------------------------------------------------------

class TheWords(unittest.TestCase):
    def test_the_companions_table_is_generated_from_the_one_source(self) -> None:
        self.assertEqual((NATIVE / "climb_text.inc").read_text(encoding="utf-8"), BUILDER.climb_text_inc())

    def test_every_piece_is_a_key_row_with_its_english(self) -> None:
        rows = {r["stem"]: r for r in vt.load_patcher_strings()}
        for stem, _key, english, _names in climb.rows():
            with self.subTest(stem=stem):
                self.assertIn(stem, rows)
                self.assertEqual(rows[stem]["english"], english)
                self.assertEqual(rows[stem].get("route"), "key")
                self.assertEqual(rows[stem]["games"], ["vv2"])

    def test_only_letters_the_lost_childrens_font_draws(self) -> None:
        import vv_font_glyphs as fonts
        missing = set(fonts.missing("vv2", "ldwBurweed27"))
        for key, template in climb.TEXTS:
            with self.subTest(key=key):
                self.assertTrue(template.isascii())
                self.assertFalse(set(re.sub(r"\{[^}]*\}|%d", "", template)) & missing)     # %d: the amount's digits
                self.assertNotIn("  ", template)
                self.assertNotIn("(", re.sub(r"\{[^}]*\}", "", template))      # no owner's note is shown

    def test_the_owners_wording(self) -> None:
        for key, text in OWNER.items():
            with self.subTest(key=key):
                self.assertEqual(owner_text(key), text)
        self.assertEqual(climb.TITLE, "The Climb")
        self.assertEqual((climb.english("LABEL_PLAN", ""), climb.english("LABEL_ADVICE", "")),
                         ("Go with the plan", "Follow the scientists' advice"))
        male = owner_text("SUMMIT", "m", "Ben")
        self.assertIn("Ben is certainly setting a name for himself throughout", male)
        self.assertIn("Behind him, he hears the rushing", male)
        self.assertTrue(owner_text("INTRO", "m", "Ben").startswith("Ben is known for his crazy, spontaneous, yet "
                                                                   "sometimes genius ideas. He is an avid researcher"))
        self.assertIn("He will be remembered as a passionate dreamer", owner_text("FALL", "m", "Ben"))
        self.assertIn("to help him work out the kinks in his plan", owner_text("ADVICE", "m", "Ben"))


class TheOdds(unittest.TestCase):
    def test_the_owners_numbers(self) -> None:
        self.assertEqual(climb.outcome_chances(), {"PLAN": {"FALL": 50.0, "SUMMIT": 50.0}, "ADVICE": {"ADVICE": 100.0}})
        self.assertEqual((climb.ADULT_YEARS, climb.RESEARCH_TRAINEE, climb.RESEARCH_MAX), (18, 20, 100))
        self.assertEqual(climb.ADVICE_GAIN, (10, 20))
        self.assertEqual(climb.SUMMIT_AWARD, ("tech", "large"))
        self.assertEqual(adv.award_range(2, "tech", "large"), (1000, 6000))

    def test_the_companion_rolls_the_same(self) -> None:
        core = (NATIVE / "climb_core.inc").read_text(encoding="utf-8")
        for needle in ("#define CLIMB_ADULT_UNITS 360", "#define CLIMB_TRAINEE 20", "#define CLIMB_RESEARCH_MAX 100",
                       "climb.falls = adv_percent(g, 50);", "climb.award = adv_award_roll(g, ADV_KIND_TECH, 2);",
                       "climb.gain = 10 + g->rand_below(11);", "g->celebrate();"):
            self.assertIn(needle, core)
        vv2 = (NATIVE / "adv_vv2.inc").read_text(encoding="utf-8")
        self.assertIn("#define VV2_CELEBRATION_PLACE 0x18", vv2)
        self.assertEqual(climb.CELEBRATION_PLACE, 0x18)


@unittest.skipUnless(HAVE_STOCK, "needs the stock executables")
class TheGamesOwnNumbers(unittest.TestCase):
    """The thresholds are the stock executable's own (read from its bytes)."""

    def setUp(self) -> None:
        import pefile
        from test_aspiring_adventurer import STOCK
        self.pe = pefile.PE(data=STOCK[2].read_bytes())

    def at(self, va: int, n: int) -> bytes:
        return self.pe.get_data(va - 0x400000, n)

    def test_trainee_is_20(self) -> None:
        # The Details panel: Research +0x7F4 (0x429C08), then `cmp eax, 0x14; jl` -> "Untrained" (string 0x81) at
        # 0x429DBD; an adult's 20..49 "Trainee" (0x84) at 0x429C8D.
        self.assertEqual(self.at(0x429C08, 7), bytes.fromhex("8B8410F4070000"))
        self.assertEqual(self.at(0x429C3D, 3), bytes.fromhex("83F814"))
        self.assertEqual(self.at(0x429DC0, 5), bytes.fromhex("6881000000"))
        self.assertEqual(self.at(0x429C8D, 5), bytes.fromhex("6884000000"))

    def test_the_cap_is_100(self) -> None:
        # The family-A Research gain: `cmp dword [eax], 0x64; jle; mov dword [eax], 0x64` (0x4212F4).
        self.assertEqual(self.at(0x4212F4, 11), bytes.fromhex("8338647E06C70064000000"))

    def test_old_friends_celebrates_with_place_0x18(self) -> None:
        # mov ecx, [ebp+0x50A8] (the pool); push 0x18; call 0x45D7D0.
        self.assertEqual(self.at(0x4344A8, 13), bytes.fromhex("8B8DA8500000" + "6A18" + "E81B930200"))


class TheMechanicsPage(unittest.TestCase):
    def test_listed_only_with_the_patch_in_the_lost_children(self) -> None:
        import vv_game_mechanics_events_vv2 as vv2
        event = next(e for e in vv2.EVENTS if e.title == climb.TITLE)
        self.assertEqual(event.only_with, "vv2_more_island_events")
        text = event.text + " " + " ".join(s if isinstance(s, str) else s.text for s in event.subs)
        for words in ("18 villager years", "Research of 20 or more", "\"Trainee\"", "not nursing a baby",
                      "not an Esteemed Elder's totem statue", "one such villager is enough", "Go with the plan",
                      "Follow the scientists' advice", "the fall 50%", "the summit 50%", "1,000 to 6,000 tech points",
                      "Research becomes 100", "celebrat", "+10 to 20 Research", "a grave", "Distinguished Scientist",
                      "1 in 44"):
            with self.subTest(words=words):
                self.assertIn(words, text)
        for game in (1, 3, 4, 5):
            catalog = __import__(f"vv_game_mechanics_events_vv{game}")
            self.assertFalse(any(e.title == climb.TITLE for e in catalog.EVENTS), game)


# ---- Emulated -----------------------------------------------------------------------------------------------------

class ClimbVillage(Village):
    """The Lost Children with the companion started; the game's own celebration stood in for (recorded)."""

    def __init__(self) -> None:
        super().__init__(2)
        self.celebrations: list[tuple[int, int]] = []
        self.people: int | None = None

        def celebrate(pr):
            self.celebrations.append((pr.reg("ecx"), pr.arg(0)))
            return 0, 4
        self.p.stub(0x45D7D0, celebrate)

    def scientist(self, i: int, name: str, woman: bool = False, research: int = 50, **kw) -> None:
        self.villager(i, name, woman, **kw)
        self.p.put32(self.rec(i) + RESEARCH, research)

    def research(self, i: int) -> int:
        return struct.unpack("<i", self.p.read(self.rec(i) + RESEARCH, 4))[0]

    def climb_possible(self) -> int:
        return self.p.export("VvfpClimbPossible")

    def climb_state(self) -> list[int]:
        out = self.p.alloc(12 * 4)
        self.p.export("VvfpClimbState", out)
        return [struct.unpack("<i", self.p.read(out + 4 * k, 4))[0] for k in range(12)]

    def climb_pages(self, which: int) -> list[str]:
        out, k = [], 0
        while True:
            at = self.p.export("VvfpClimbPage", which, k)
            if not at:
                return out
            out.append(self.p.cstring(at, 4000))
            k += 1

    def begin_climb(self, rolls: list[int], share: int | None = None) -> bool:
        """Family A's setup with the draw 21 (and, when both events can happen, `share` for the rand(2)); True when the
        dialog is The Climb's."""
        p = self.p
        self.ui.clear()
        self.dlg = p.alloc(0x6000)
        p.put32(self.dlg + 0x50AC, self.world)
        p.put32(self.dlg + 0x50B0, self.base)
        for o, v in ((0x54, 2), (0x58, 3), (0x5C, 4), (0x50C8, 0x111), (0x50CC, 0x222), (0x50D0, 0x333)):
            p.put32(self.dlg + o, v)
        self.rolls = [TOP] + ([] if share is None else [share]) + list(rolls)
        if p.call(0x41F780, [], ecx=self.dlg) & 0xFF == 0 or p.u32(self.dlg + 0x509C) != 21:
            return False
        p.stub(0x422380, lambda pr: (pr.reg("ecx"), 0))
        p.set_reg("esp", STACK_TOP - 0x3000)
        p.set_reg("ecx", self.dlg)
        p.run(0x42F1A3, 0x42F1A8)
        return self.shown().startswith(TITLE_LINE)

    def play_climb(self, rolls: list[int], answer: int, share: int | None = None) -> list[str]:
        """The whole event: every page shown, in order, until the close (each as one line of words, the title and the
        dialog's own line breaks taken out).  `answer` 1 is "Go with the plan", 2 the advice."""
        if not self.begin_climb(rolls, share):
            raise AssertionError("The Climb was not drawn")
        seen = [self.shown()]
        for _ in range(self.climb_state()[8] - 1):
            self.click(0)
            seen.append(self.shown())
        self.click(answer)
        self.after_answer = (self.health(self.hero), self.research(self.hero), self.stores(), len(self.celebrations))
        seen.append(self.shown())
        for _ in range(20):
            self.ui.clear()
            self.click(0)
            if self.closed():
                break
            seen.append(self.shown())
        self.closed_at_end = self.closed()
        return [re.sub(r"\s+", " ", page.replace(TITLE_LINE, "")).strip() for page in seen]

    hero = 0


def climb_rolls(*, hero: int | None = None, falls: bool = True, award: int = 0, gain: int = 0) -> list[int]:
    """The rolls climb_begin draws, in its order (the villager only when more than one may climb)."""
    return ([] if hero is None else [hero]) + [FALL if falls else SUMMIT, award, gain]


def joined(pages: list[str]) -> str:
    out: list[str] = []
    for page in pages:
        if not out or out[-1] != page:
            out.append(page)
    return " ".join(out)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Who(unittest.TestCase):
    def test_research_and_age(self) -> None:
        cases = (
            ("Research 19", dict(research=19), 0),
            ("Research 20 (Trainee)", dict(research=20), 1),
            ("Research 100", dict(research=100), 1),
            ("17 years", dict(years=17), 0),
            ("18 years", dict(years=18), 1),
            ("13 years", dict(years=13), 0),
            ("nursing", dict(carrying=500), 0),
            ("an Esteemed Elder's statue", dict(special=(0x558, 1, 1)), 0),
            ("dead", dict(health=0), 0),
        )
        for what, kw, possible in cases:
            with self.subTest(what=what):
                v = ClimbVillage()
                v.scientist(0, "Ana", True, **kw)                 # one villager: enough
                self.assertEqual(v.climb_possible(), possible)
                self.assertEqual(v.possible(), 0)                 # the Adventurer needs two
                drawn = v.begin_climb(climb_rolls())
                self.assertEqual(drawn, bool(possible))
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        v.p.write(v.rec(0) + 0x30, b"\x00")
        self.assertEqual(v.climb_possible(), 0)                   # the absent never go
        self.assertFalse(v.begin_climb(climb_rolls()))

    def test_the_villager_is_drawn_among_those_who_may_go(self) -> None:
        v = ClimbVillage()
        v.scientist(0, "Ana", True, research=19)                  # never
        v.scientist(1, "Ben", research=20)
        v.scientist(2, "Cal", research=60)
        self.assertEqual(v.possible(), 1)                         # the Adventurer can happen too
        v.play_climb(climb_rolls(hero=1, falls=False), 2, share=1)
        self.assertEqual(v.climb_state()[0], 2)                   # the second of Ben and Cal
        v = ClimbVillage()
        v.scientist(0, "Ana", True, research=19)
        v.scientist(1, "Ben", research=20)
        v.scientist(2, "Cal", research=60)
        v.play_climb(climb_rolls(hero=0, falls=False), 2, share=1)
        self.assertEqual(v.climb_state()[0], 1)

    def test_the_draw_21_is_shared_with_the_adventurer(self) -> None:
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        v.scientist(1, "Ben")
        self.assertEqual((v.possible(), v.climb_possible()), (1, 1))
        self.assertTrue(v.begin_climb(climb_rolls(hero=0), share=1))      # rand(2) = 1: The Climb
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        v.scientist(1, "Ben")
        self.assertFalse(v.begin_climb([0] * 20, share=0))                # rand(2) = 0: the Adventurer
        self.assertTrue(v.shown().startswith("The Aspiring Adventurer\n"))
        # Never the village's first island event.
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        v.p.put32(v.world + 0x2E51C, 1)
        self.assertFalse(v.begin_climb(climb_rolls()))


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Effects(unittest.TestCase):
    def village(self, research: int = 50, woman: bool = True) -> ClimbVillage:
        v = ClimbVillage()
        v.scientist(0, "Ana", woman, research=research)
        v.villager(1, "Kid", years=10)                            # a child: never climbs, never touched
        return v

    def test_the_fall(self) -> None:
        v = self.village()
        before = v.stores()
        text = joined(v.play_climb(climb_rolls(falls=True), 1))
        self.assertTrue(v.closed_at_end)
        self.assertEqual(v.after_answer, (0, 50, before, 0))      # made in the answer's click
        self.assertEqual((v.health(0), v.present(0)), (0, 1))     # the game's own death: the body lies, a grave comes
        self.assertEqual(v.research(0), 50)
        self.assertEqual(v.stores(), before)
        self.assertEqual(v.celebrations, [])
        self.assertEqual(v.vanished, [])
        self.assertEqual((v.health(1), v.present(1)), (100, 1))
        self.assertEqual(v.climb_state()[7], 0)
        self.assertIn(OWNER["PLAN"] + " " + OWNER["FALL"], text)

    def test_the_summit(self) -> None:
        for draw, research in ((0, 50), (7, 20), (TOP, 99)):
            with self.subTest(draw=draw):
                v = self.village(research)
                before = v.stores()
                text = joined(v.play_climb(climb_rolls(falls=False, award=draw), 1))
                award = v.climb_state()[3]
                lo, hi = adv.award_range(2, "tech")
                self.assertEqual(award, 2 * (hi if draw == TOP else lo + draw))
                self.assertTrue(1000 <= award <= 6000)
                after = v.stores()
                self.assertEqual((after[0] - before[0], after[1] - before[1]), (0, award))
                self.assertEqual(v.research(0), 100)              # the game's maximum
                self.assertEqual(v.celebrations, [(v.base, 0x18)])   # once, on the pool, Old Friends' place
                self.assertEqual(v.after_answer, (100, 100, after, 1))
                self.assertEqual((v.health(0), v.present(0)), (100, 1))
                self.assertIn(OWNER["PLAN"], text)
                self.assertIn(owner_text("SUMMIT", award=award), text)
                self.assertIn(f"Your village gains {award} tech points.", text)

    def test_the_award_scales_by_the_games_own_factor(self) -> None:
        for people, factor in ((25, 1), (26, 2), (50, 2), (51, 3)):
            with self.subTest(people=people):
                v = self.village()
                v.p.stub(0x425860, lambda pr, n=people: (n, 0))   # the game's own population count
                before = v.stores()
                v.play_climb(climb_rolls(falls=False, award=0), 1)
                self.assertEqual(v.climb_state()[3], factor * 2 * 500)
                self.assertEqual(v.stores()[1] - before[1], factor * 1000)

    def test_the_advice(self) -> None:
        for research, draw, expected in ((20, 0, 30), (50, 5, 65), (40, TOP, 60), (95, TOP, 100), (100, 0, 100)):
            with self.subTest(research=research, draw=draw):
                v = self.village(research)
                before = v.stores()
                text = joined(v.play_climb(climb_rolls(gain=draw), 2))
                gain = v.climb_state()[4]
                self.assertEqual(gain, 20 if draw == TOP else 10 + draw)
                self.assertEqual(v.research(0), expected)
                self.assertEqual(v.after_answer[1], expected)
                self.assertEqual(v.stores(), before)
                self.assertEqual(v.celebrations, [])
                self.assertEqual((v.health(0), v.present(0)), (100, 1))
                self.assertIn(OWNER["ADVICE"], text)
                self.assertNotIn("For several hours", text)

    def test_both_answers_and_both_climbs_are_reached(self) -> None:
        reached = set()
        for answer, falls in ((1, True), (1, False), (2, True), (2, False)):
            v = self.village()
            v.play_climb(climb_rolls(falls=falls), answer)
            state = v.climb_state()
            self.assertEqual((state[5], state[6]), (1, answer - 1))
            reached.add(state[7])
        self.assertEqual(reached, {0, 1, 2})

    def test_the_question_and_the_labels(self) -> None:
        v = self.village()
        v.begin_climb(climb_rolls())
        self.assertEqual((v.p.cstring(v.dlg + 0x4E9A, 300), v.p.cstring(v.dlg + 0x4F9A, 300)),
                         ("Go with the plan", "Follow the scientists' advice"))
        self.assertEqual(v.p.u32(v.dlg + 0x50A0), 0)              # the villager in the picture
        self.assertIn(("select", 0), v.ui)

    def test_a_man(self) -> None:
        v = self.village(woman=False)
        text = joined(v.play_climb(climb_rolls(falls=False, award=0), 1))
        self.assertIn(owner_text("SUMMIT", "m", "Ana", 1000), text)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Pages(unittest.TestCase):
    def test_every_page_fits_with_the_longest_name(self) -> None:
        name = NAMES[2]
        for woman in (False, True):
            for falls in (True, False):
                v = ClimbVillage()
                v.scientist(0, name, woman)
                v.p.stub(0x425860, lambda pr: (99, 0))            # the largest factor: the widest number
                self.assertTrue(v.begin_climb(climb_rolls(falls=falls, award=TOP)))
                for which in range(4):
                    for page in v.climb_pages(which):
                        with self.subTest(woman=woman, falls=falls, which=which):
                            self.assertLessEqual(wrap_lines(page, WIDTH), LINES, page)
                for line in v.shown().split("\n"):
                    self.assertLessEqual(len(line), WIDTH)

    def test_the_pages_hold_the_whole_text(self) -> None:
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        v.begin_climb(climb_rolls(falls=False))
        award = v.climb_state()[3]
        sets = {k: " ".join(v.climb_pages(k)).replace("\n", " ") for k in range(4)}
        self.assertEqual(sets[0], OWNER["INTRO"])
        self.assertEqual(sets[1], OWNER["PLAN"] + " " + OWNER["FALL"])
        self.assertEqual(sets[2], OWNER["PLAN"] + " " + owner_text("SUMMIT", award=award))
        self.assertEqual(sets[3], OWNER["ADVICE"])
        self.assertGreater(len(v.climb_pages(2)), 2)              # the plan's popup, then the climb's


if __name__ == "__main__":
    unittest.main()
