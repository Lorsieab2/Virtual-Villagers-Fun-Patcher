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
  * THE DRAW: the event never takes a share of family A's draw (stock island event chances never change): with
    nothing due the chooser runs on the stock bytes, rand(22), a stock draw of 21 drawn again as in the stock game;
    only while it is due (Pick Island Event or the rare roll) is the draw's call pointed into the companion for that
    one run -- its first draw the event's own number, 22 (21 The Aspiring Adventurer), when it can happen -- chained
    onto whatever the call holds (the game's rand, or Story / Cheat Upgrades' own roll), and put back after; an
    unknown call is left alone;
  * THE POPUP through the game's own click handler, OK and constructor sites: the question's pages with OK, the two
    answers, the result's pages with OK, the close;
  * EVERY EFFECT, made when the page that ends its ending's text is shown (never on the plan's page): the fall -- the
    game's own
    death (health 0: the body lies and gets a grave); the summit -- Research 100, the award through the game's tech
    writer within the large range and scaled by the game's own factor, the game's own village celebration called
    once (Old Friends' place); the advice -- +10 to 20 Research, at most 100; nothing else changes;
  * THE LOG: one Island Events entry, held at the answer, the effects page bracketed by the log's own comparison and
    the entry closed there; the game's own brackets write nothing while the dialog is open;
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
                      "never takes a share of the game's own draw", "separate rare roll comes up 25%",
                      "Pick Island Event", "when the page"):
            with self.subTest(words=words):
                self.assertIn(words, text)
        # The stock draw is never widened (the owner, 2026-11-14): no "1 in 23", no slot of its own in it.
        for stale in ("1 in 23", "its own slot"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, text)
        for game in (1, 3, 4, 5):
            catalog = __import__(f"vv_game_mechanics_events_vv{game}")
            self.assertFalse(any(e.title == climb.TITLE for e in catalog.EVENTS), game)


# ---- Emulated -----------------------------------------------------------------------------------------------------

FAKE_ISLAND_EVENTS = 0x0EA00000                # "VVFP Island Events.dll", stood in for
CLIMB_DRAW, ADVENTURER_DRAW = 22, 21           # each event's own number in family A's draw (past the stock 0..20)
CLIMB_PICK, ADVENTURER_PICK = 2, 0             # their registry indexes (mie_pick.inc)


class ClimbVillage(Village):

    PICK = CLIMB_PICK
    """The Lost Children with the companion started; the game's own celebration stood in for (recorded), and -- with
    `log` -- the Island Events log's one-entry exports stood in for (each call recorded, with the village then)."""

    def __init__(self, log: bool = False) -> None:
        super().__init__(2)
        self.celebrations: list[tuple[int, int]] = []
        self.bounds: list[int] = []
        self.log_calls: list[tuple] = []
        p = self.p

        def celebrate(pr):
            self.celebrations.append((pr.reg("ecx"), pr.arg(0)))
            return 0, 4
        p.stub(0x45D7D0, celebrate)
        rand = p.stubs[self.rand]

        def counted(pr):
            self.bounds.append(pr.arg(0))
            return rand(pr)
        p.stub(self.rand, counted)
        if log:
            self._fake_log()

    def _fake_log(self) -> None:
        p = self.p
        code = p.alloc(32)
        p.write(code, b"\xC3" * 32)
        exports = {"VvfpIslandEventsGraphBegin": code, "VvfpIslandEventsGraphEnd": code + 8,
                   "VvfpIslandEventsGraphWrite": code + 16}

        def begin(pr):
            self.log_calls.append(("begin", self.village_now()))
            return 1, 4

        def end(pr):
            self.log_calls.append(("end", self.village_now()))
            pr.write(pr.arg(1), b"  Ana: Health 100 -> 0\n\0")
            return len("  Ana: Health 100 -> 0\n"), 12

        def write(pr):
            self.log_calls.append(("write", pr.arg(0), pr.arg(1), pr.cstring(pr.arg(2), 4000),
                                   pr.arg(3) - (1 << 32) if pr.arg(3) >> 31 else pr.arg(3), pr.arg(4)))
            return 1, 20
        p.stub(code, begin)
        p.stub(code + 8, end)
        p.stub(code + 16, write)
        module, proc = p.api_handlers["GetModuleHandleA"], p.api_handlers["GetProcAddress"]
        p.api_handlers["GetModuleHandleA"] = lambda pr, m=module: (
            (FAKE_ISLAND_EVENTS, 4) if pr.arg(0) and pr.cstring(pr.arg(0)) == "VVFP Island Events.dll" else m(pr))
        p.api_handlers["GetProcAddress"] = lambda pr, c=proc: (
            (exports.get(pr.cstring(pr.arg(1)), 0), 8) if pr.arg(0) == FAKE_ISLAND_EVENTS else c(pr))

    def village_now(self) -> tuple:
        return (self.health(0), self.research(0), self.stores(), len(self.celebrations))

    def scientist(self, i: int, name: str, woman: bool = False, research: int = 50, **kw) -> None:
        self.villager(i, name, woman, **kw)
        self.p.put32(self.rec(i) + RESEARCH, research)

    def research(self, i: int) -> int:
        return struct.unpack("<i", self.p.read(self.rec(i) + RESEARCH, 4))[0]

    def climb_possible(self) -> int:
        return self.p.export("VvfpClimbPossible")

    def logged(self) -> int:
        return self.p.export("VvfpMoreIslandEventsLogged", 2, 0)

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

    def begin_climb(self, rolls: list[int], pick: int | None = CLIMB_PICK) -> bool:
        """Family A's setup with registry entry `pick` due (None: nothing due, the stock draw); True when the dialog
        is The Climb's."""
        p = self.p
        self.ui.clear()
        self.bounds.clear()
        self.dlg = p.alloc(0x6000)
        p.put32(self.dlg + 0x50AC, self.world)
        p.put32(self.dlg + 0x50B0, self.base)
        for o, v in ((0x54, 2), (0x58, 3), (0x5C, 4), (0x50C8, 0x111), (0x50CC, 0x222), (0x50D0, 0x333)):
            p.put32(self.dlg + o, v)
        self.due = -1 if pick is None else pick
        self.rolls = list(rolls)
        if p.call(0x41F780, [], ecx=self.dlg) & 0xFF == 0 or p.u32(self.dlg + 0x509C) not in (21, 22):
            return False
        p.stub(0x422380, lambda pr: (pr.reg("ecx"), 0))
        p.set_reg("esp", STACK_TOP - 0x3000)
        p.set_reg("ecx", self.dlg)
        p.run(0x42F1A3, 0x42F1A8)
        return self.shown().startswith(TITLE_LINE)

    def play_climb(self, rolls: list[int], answer: int) -> list[str]:
        """The whole event: every page shown, in order, until the close (each as one line of words, the title and the
        dialog's own line breaks taken out); `self.states` the village as each result page is shown.  `answer` 1 is
        "Go with the plan", 2 the advice."""
        if not self.begin_climb(rolls):
            raise AssertionError("The Climb was not drawn")
        seen = [self.shown()]
        for _ in range(self.climb_state()[8] - 1):
            self.click(0)
            seen.append(self.shown())
        self.click(answer)
        self.states = [self.village_now()]
        self.logged_while_open = self.logged()
        seen.append(self.shown())
        for _ in range(20):
            self.ui.clear()
            self.click(0)
            if self.closed():
                break
            self.states.append(self.village_now())
            seen.append(self.shown())
        self.closed_at_end = self.closed()
        self.result_pages = [re.sub(r"\s+", " ", page.replace(TITLE_LINE, "")).strip() for page in seen[-len(self.states):]]
        return [re.sub(r"\s+", " ", page.replace(TITLE_LINE, "")).strip() for page in seen]


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
        for hero, expected in ((1, 2), (0, 1)):
            v = ClimbVillage()
            v.scientist(0, "Ana", True, research=19)              # never
            v.scientist(1, "Ben", research=20)
            v.scientist(2, "Cal", research=60)
            self.assertEqual(v.possible(), 1)                     # the Adventurer can happen too: no matter
            v.play_climb(climb_rolls(hero=hero, falls=False), 2)
            self.assertEqual(v.climb_state()[0], expected)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class TheDraw(unittest.TestCase):
    """Never a share of the draw (the owner's rule: stock island event chances never change): with nothing due family
    A's chooser runs on the stock bytes; a due event takes its own number, and the draw's call is put back."""

    def watch_draw_site(self, v: ClimbVillage) -> list[int]:
        """Every write to the draw's call 0x41F59D (5 bytes), kept."""
        from unicorn import UC_HOOK_MEM_WRITE
        writes: list[int] = []
        v.p.mu.hook_add(UC_HOOK_MEM_WRITE, lambda mu, access, address, size, value, data: writes.append(address),
                        begin=0x41F59D, end=0x41F5A1)
        return writes

    def test_nothing_due_the_stock_draw(self) -> None:
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        v.scientist(1, "Ben")
        self.assertEqual((v.possible(), v.climb_possible()), (1, 1))
        writes = self.watch_draw_site(v)
        # 21 (the value the stock draw never keeps) is drawn again; 5 is a stock event.
        self.assertFalse(v.begin_climb([ADVENTURER_DRAW, 5] + [0] * 20, pick=None))
        self.assertEqual(v.p.u32(v.dlg + 0x509C), 5)
        self.assertEqual(v.bounds[:2], [22, 22])                  # the stock bound, rand(22)
        self.assertEqual(writes, [])                              # the draw's call never written
        self.assertEqual(v.done, [])

    def test_a_due_event_takes_its_own_number(self) -> None:
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        v.scientist(1, "Ben")
        self.assertTrue(v.begin_climb(climb_rolls(hero=0)))
        self.assertNotIn(22, v.bounds)                            # no draw of the game's was taken for it
        self.assertNotIn(23, v.bounds)
        self.assertEqual(v.done, [(2, 1)])
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        v.scientist(1, "Ben")
        self.assertFalse(v.begin_climb([0] * 20, pick=ADVENTURER_PICK))
        self.assertEqual(v.p.u32(v.dlg + 0x509C), 21)
        self.assertTrue(v.shown().startswith("The Aspiring Adventurer\n"))
        self.assertEqual(v.done, [(2, 1)])

    def test_a_due_event_that_cannot_happen_is_refused(self) -> None:
        v = ClimbVillage()
        v.scientist(0, "Ana", True, research=0)                   # nobody may climb
        self.assertFalse(v.begin_climb([5] * 20))
        self.assertEqual(v.done, [(2, 0)])
        self.assertEqual(v.p.u32(v.dlg + 0x509C), 5)              # the stock draw ran ...
        self.assertEqual(set(v.bounds), {22})                     # ... with the stock bound
        # Never the village's first island event.
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        v.p.put32(v.world + 0x2E51C, 1)
        self.assertFalse(v.begin_climb(climb_rolls()))
        self.assertEqual(v.done, [(2, 0)])

    def test_the_draws_call_is_put_back(self) -> None:
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        stock = v.p.read(0x41F59D, 5)
        self.assertEqual(stock.hex().upper(), "E8FE3BFEFF")      # the game's rand, as at the start
        writes = self.watch_draw_site(v)
        self.assertTrue(v.begin_climb(climb_rolls()))
        self.assertEqual(v.p.read(0x41F59D, 5), stock)
        self.assertTrue(writes)                                   # pointed into the companion while due, put back

    def test_chained_onto_story_cheat_upgrades_roll(self) -> None:
        """With Story / Cheat Upgrades' roll at the draw's call (it installs later, from the Origins companion), the
        stock bound reaches that roll whenever the game draws, and its call is put back as it was."""
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        p = v.p
        story_fn = p.alloc(16)
        p.write(story_fn, b"\xC3")
        story_base = next(b for b, e, _ in p.mu.mem_regions() if b <= story_fn <= e)
        seen: list[int] = []

        def story_roll(pr):
            seen.append(pr.arg(0))
            return 5, 0                                           # The Voices In The Brush, always possible
        p.stub(story_fn, story_roll)
        v.story_handles.add(story_base)
        module = p.api_handlers["GetModuleHandleA"]
        p.api_handlers["GetModuleHandleA"] = lambda pr, m=module: (
            (story_base, 4) if pr.arg(0) and pr.cstring(pr.arg(0)) == "VVFP Story Upgrades.dll" else m(pr))
        story_call = b"\xE8" + struct.pack("<i", story_fn - (0x41F59D + 5))
        p.write(0x41F59D, story_call)
        p.mu.ctl_flush_tb()
        self.assertFalse(v.begin_climb([], pick=None))            # nothing due: Story's roll, the stock bound
        self.assertEqual(seen, [22])
        self.assertEqual(p.u32(v.dlg + 0x509C), 5)
        seen.clear()
        self.assertTrue(v.begin_climb(climb_rolls()))             # due: its own number, Story's roll not asked
        self.assertEqual(seen, [])
        self.assertEqual(p.read(0x41F59D, 5), story_call)
        self.assertEqual(p.u32(v.dlg + 0x509C), 22)

    def test_an_unknown_call_at_the_draw_is_left_alone(self) -> None:
        v = ClimbVillage()
        v.scientist(0, "Ana", True)
        p = v.p
        other = p.alloc(16)
        p.write(other, b"\xC3")
        seen: list[int] = []
        p.stub(other, lambda pr: (seen.append(pr.arg(0)) or 5, 0))   # 5: The Voices In The Brush, always possible
        call = b"\xE8" + struct.pack("<i", other - (0x41F59D + 5))
        p.write(0x41F59D, call)
        p.mu.ctl_flush_tb()
        self.assertFalse(v.begin_climb(climb_rolls()))
        self.assertEqual(p.read(0x41F59D, 5), call)
        self.assertEqual(seen, [22])                              # the stock bound: never widened, never ours


def one_scientist(research: int = 50, woman: bool = True, log: bool = False) -> ClimbVillage:
    v = ClimbVillage(log)
    v.scientist(0, "Ana", woman, research=research)
    v.villager(1, "Kid", years=10)                                # a child: never climbs, never touched
    return v


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Effects(unittest.TestCase):
    """The effects wait for their own page (the owner's standing rule): each ending's are made when the page that
    ends its text is shown -- never on the plan's page."""

    def village(self, research: int = 50, woman: bool = True, log: bool = False) -> ClimbVillage:
        return one_scientist(research, woman, log)

    def assert_only_on_the_last_page(self, v: ClimbVillage, before: tuple) -> None:
        self.assertGreater(len(v.states), 1)
        for state in v.states[:-1]:
            self.assertEqual(state, before)                       # nothing yet on the earlier pages
        self.assertNotEqual(v.states[-1], before)

    def test_the_fall(self) -> None:
        v = self.village()
        before = v.village_now()
        text = joined(v.play_climb(climb_rolls(falls=True), 1))
        self.assertTrue(v.closed_at_end)
        self.assert_only_on_the_last_page(v, before)
        self.assertEqual(v.result_pages[0], OWNER["PLAN"])        # the plan's page: still alive
        self.assertEqual(v.states[0][0], 100)
        self.assertTrue(v.result_pages[-1].endswith("dared to do the impossible."))
        self.assertEqual((v.health(0), v.present(0)), (0, 1))     # the game's own death: the body lies, a grave comes
        self.assertEqual(v.research(0), 50)
        self.assertEqual(v.stores(), before[2])
        self.assertEqual(v.celebrations, [])
        self.assertEqual(v.vanished, [])
        self.assertEqual((v.health(1), v.present(1)), (100, 1))
        self.assertEqual(v.climb_state()[7], 0)
        self.assertIn(OWNER["PLAN"] + " " + OWNER["FALL"], text)

    def test_the_summit(self) -> None:
        for draw, research in ((0, 50), (7, 20), (TOP, 99)):
            with self.subTest(draw=draw):
                v = self.village(research)
                before = v.village_now()
                text = joined(v.play_climb(climb_rolls(falls=False, award=draw), 1))
                award = v.climb_state()[3]
                lo, hi = adv.award_range(2, "tech")
                self.assertEqual(award, 2 * (hi if draw == TOP else lo + draw))
                self.assertTrue(1000 <= award <= 6000)
                self.assert_only_on_the_last_page(v, before)
                self.assertTrue(v.result_pages[-1].endswith(f"Your village gains {award} tech points."))
                after = v.stores()
                self.assertEqual((after[0] - before[2][0], after[1] - before[2][1]), (0, award))
                self.assertEqual(v.research(0), 100)              # the game's maximum
                self.assertEqual(v.celebrations, [(v.base, 0x18)])   # once, on the pool, Old Friends' place
                self.assertEqual(v.states[-1], (100, 100, after, 1))
                self.assertEqual((v.health(0), v.present(0)), (100, 1))
                self.assertIn(OWNER["PLAN"], text)
                self.assertIn(owner_text("SUMMIT", award=award), text)

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
                self.assertEqual(v.states[-1][1], expected)       # on the advice's own (last) page
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
class TheLog(unittest.TestCase):
    """The Island Events log's ONE entry for the event: nothing handed over before the effects page (a save before it
    holds neither), its effects' lines taken by the log's own comparison around that page, the entry handed over
    complete and final there; the game's own brackets write nothing for the dialog until the next draw."""

    def test_one_entry_with_the_effects_page_bracketed(self) -> None:
        v = one_scientist(log=True)
        before = v.village_now()
        v.play_climb(climb_rolls(falls=True), 1)
        kinds = [c[0] for c in v.log_calls]
        self.assertEqual(kinds, ["begin", "end", "write"])
        begin, end, last = v.log_calls
        self.assertEqual(begin[1], before)                         # the village before the effects ...
        self.assertEqual(end[1][0], 0)                             # ... and after them
        self.assertEqual((last[1], last[3], last[4], last[5]),
                         (2, "  Event: The Climb\n  Choice: Go with the plan\n  Ana: Health 100 -> 0\n", -1, 1))
        self.assertEqual(v.logged_while_open, 1)
        self.assertEqual(v.logged(), 1)                            # through the close's own bracket
        v.begin_climb([5] * 20, pick=None)                         # the game's next draw: not ours
        self.assertEqual(v.logged(), 0)

    def test_the_advice_is_logged_on_its_own_last_page(self) -> None:
        v = one_scientist(log=True)
        v.play_climb(climb_rolls(gain=0), 2)
        self.assertEqual(len(v.climb_pages(3)), 2)
        self.assertEqual([c[0] for c in v.log_calls], ["begin", "end", "write"])
        self.assertEqual(v.log_calls[0][1][1], 50)                  # Research before the advice's last page ...
        self.assertEqual(v.log_calls[1][1][1], 60)                  # ... and after it
        self.assertEqual(v.log_calls[-1][3],
                         "  Event: The Climb\n  Choice: Follow the scientists' advice\n  Ana: Health 100 -> 0\n")
        self.assertEqual(v.log_calls[-1][5], 1)

    def test_without_the_log_companion_nothing_is_asked(self) -> None:
        v = one_scientist()
        v.play_climb(climb_rolls(falls=True), 1)
        self.assertEqual(v.log_calls, [])
        self.assertEqual(v.health(0), 0)


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
