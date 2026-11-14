"""The Playful Dolphins: the owner's island event for The Tree of Life (2026-11-13), in "More Island Events".

Static (always run): the words are the owner's (src/vv_playful_dolphins.py, the companion's table generated from it,
a translation row for every piece), in letters the game's font draws; the odds are the owner's table.

EMULATED (unicorn, the stock The Tree of Life executable, the built "VVFP More Island Events.dll";
tests/story_emulator.py, the villagers in the game's own records as tests/test_aspiring_adventurer.py puts them, the
popup through the game's own click handler, OK and constructor sites):
  * who: the swimmer is a villager of 14 or more who is not protected; 13, nursing (mother or father) and a body or
    ghost never; two such villagers are needed; the Fishing Nets (or any puzzle) are never needed;
  * both branches of "Swim towards the dolphins" at their odds (rand(100) < 50 the hunt), and "Hang back";
  * every effect: Farming set to 100 (the game's maximum), the large and the small food awards (and their scaling),
    the tail slap's 30 to 50 health lost, never below 1;
  * the effects on the ending's last page only; the Island Events log's one entry; nothing handed over before it;
  * the draw: never a share of the game's own draw (stock island event chances never change): the selector's
    list gains no entry; the event's object is in slot 0 only while it is due (Pick Island Event or the rare roll),
    for Story's pick to present.

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
import vv_playful_dolphins as dp  # noqa: E402
from test_aspiring_adventurer import DLL, HAVE_EMULATOR, HAVE_STOCK, STOCK, TABLES, TOP, Village  # noqa: E402
from test_more_island_events_pages import fake_log  # noqa: E402

try:
    from story_emulator import STACK_TOP  # noqa: E402
except ImportError:                       # pragma: no cover
    STACK_TOP = 0

NATIVE = ROOT / "native" / "vvfp_more_island_events"
OWNER_TEXT = ROOT / "tests" / "data" / "playful_dolphins_owner_text.txt"
LABELS = (dict(dp.TEXTS)["LABEL_SWIM"], dict(dp.TEXTS)["LABEL_BACK"])
ENDINGS = dp.ENDINGS                                  # HUNT, SLAP, BACK
T = TABLES[4]
FARMING = 0x1C5C                                      # float; Farming first (adv_vv345.inc t_skill)
TITLE_ID = 0x35F
FOOD_LO = adv.award_range(4, "food")[0]               # 300: The Tree of Life's only stock food gain
FISHING_NETS = 11                                     # the game's puzzle 11 (island_event_more.inc P4(11))
PUZZLE_PROGRESS, PUZZLE_DONE_AT = 0x4D8BF8 + 8 * FISHING_NETS, 0x4D8B20 + 4 * FISHING_NETS


def words(text: str) -> list[str]:
    return re.sub(r"\s+", " ", text).strip().split(" ")


def dp_rolls(*, swimmer=0, slap=False, loss=0, candidates=3) -> list[int]:
    """The rolls dp_begin draws, in its order: the swimmer (only with a choice), rand(100) < 50 the hunt (slap: 99),
    the slap's loss - 30 (TOP the largest).  The Tree of Life's food range is one amount: no award roll."""
    return ([swimmer] if candidates > 1 else []) + [99 if slap else 0, loss]


DOLPHINS_PICK = 5                                # The Playful Dolphins' registry index (mie_pick.inc)


class Dolphins(Village):
    """The Tree of Life with the companion, its villagers and The Playful Dolphins' popup."""

    def __init__(self):
        super().__init__(4)

    def adults(self, n: int = 3, first: int = 0, years: int = 30) -> None:
        for k in range(n):
            self.villager(first + k, f"Swimmer{first + k}", k % 2 == 0, years=years)

    def dp_possible(self) -> int:
        return self.p.export("VvfpDolphinsPossible")

    def dp_state(self) -> list[int]:
        out = self.p.alloc(16 * 4)
        self.p.export("VvfpDolphinsState", out)
        return [struct.unpack("<i", self.p.read(out + 4 * k, 4))[0] for k in range(16)]

    def dp_pages(self, which: int) -> list[str]:
        out, k = [], 0
        while True:
            at = self.p.export("VvfpDolphinsPage", which, k)
            if not at:
                return out
            out.append(self.p.cstring(at, 4000))
            k += 1

    def farming(self, i: int) -> float:
        return struct.unpack("<f", self.p.read(self.rec(i) + FARMING, 4))[0]

    def set_farming(self, i: int, value: float) -> None:
        self.p.write(self.rec(i) + FARMING, struct.pack("<f", value))

    def set_health(self, i: int, value: int) -> None:
        self.p.put32(self.rec(i) + self.L["health"], value)

    # -- the draw ------------------------------------------------------------------------------------------------
    def list_draw(self, pick: int = DOLPHINS_PICK, listed: int = 0) -> tuple[int, int]:
        """Registry entry `pick` due (-1: nothing due), the selector's loop with every stock slot empty and `listed`
        entries already in the list: (entries the companion added -- always 0 --, the object in slot 0)."""
        self.due = pick
        added = self.run_list(listed) - listed
        return added, self.obj

    def title_of(self, obj: int) -> str:
        """The title an event object gives (its +0x08, as the dialog asks it first)."""
        self.p.call(self.p.u32(self.p.u32(obj) + 8), ecx=obj)
        entry = self.p.u32(T["strings"] + 4 * TITLE_ID)
        return self.p.cstring(self.p.u32(entry + 8), 400)

    # -- the popup -----------------------------------------------------------------------------------------------
    def open(self, rolls: list[int]) -> bool:
        """The Playful Dolphins due, put in slot 0 and presented (its own condition holding, as Story's pick asks
        it), its popup built through the game's presenter site."""
        p = self.p
        added, obj = self.list_draw(DOLPHINS_PICK)
        if added or not self.can_fire(obj):
            return False
        self.ui.clear()
        self.rolls = list(rolls)
        if self.title_of(obj) != dp.TITLE:
            return False

        def ctor(pr):
            pr.put32(pr.reg("ecx") + 0x50, pr.arg(0))
            return pr.reg("ecx"), 4
        self.dlg = p.alloc(0x1000)
        for o, v in ((0x85C, 0x111), (0x860, 0x222), (0x864, 0x333)):
            p.put32(self.dlg + o, v)
        p.stub(T["ctor"], ctor)
        esp = STACK_TOP - 0x3000 - 4
        p.put32(esp, obj)
        p.set_reg("esp", esp)
        p.set_reg("ecx", self.dlg)
        p.run(*T["site"])
        return True

    def snapshot(self, records=range(0, 3)) -> tuple:
        out = [self.stores()]
        for i in records:
            out.append((self.present(i), self.health(i), self.farming(i)))
        return tuple(out)

    def play(self, answer: int, calls: list | None = None) -> list[tuple]:
        """The whole event: (what was clicked, the village after it, the log calls so far) for each click; answer 0
        "Swim towards the dolphins", 1 "Hang back"."""
        calls = calls if calls is not None else []
        steps = []
        for _ in range(self.dp_state()[10] - 1):
            self.click(0)
            steps.append(("ok", self.snapshot(), len(calls)))
        self.click(1 + answer)
        steps.append(("answer", self.snapshot(), len(calls)))
        pages = self.dp_state()[11 + self.dp_state()[8]]
        for _ in range(pages - 1):
            self.click(0)
            steps.append(("ok", self.snapshot(), len(calls)))
        self.ui.clear()
        self.click(0)
        steps.append(("close", self.snapshot(), len(calls)))
        return steps


def three(**kw) -> Dolphins:
    v = Dolphins()
    v.adults(3, **kw)
    return v


NEEDS = unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(),
                            "needs unicorn, pefile, the stock executables and the built DLL")


# ---- The words and the odds (no emulator) ---------------------------------------------------------------------------

class TheWords(unittest.TestCase):
    def test_every_piece_is_a_key_row_with_its_english(self) -> None:
        rows = {r["stem"]: r for r in json.loads((ROOT / "data" / "translations" / "patcher_strings.json")
                                                 .read_text(encoding="utf-8"))["strings"]}
        for stem, key, english, _ in dp.rows():
            with self.subTest(stem=stem):
                self.assertIn(stem, rows)
                self.assertEqual(rows[stem]["english"], english)
                self.assertEqual(rows[stem]["games"], ["vv4"])
                self.assertEqual(rows[stem]["route"], "key")

    def test_the_companions_table_is_generated_from_the_one_source(self) -> None:
        import build_more_island_events as builder
        self.assertEqual((NATIVE / "dolphin_text.inc").read_text(encoding="utf-8"), builder.dolphin_text_inc())

    def test_only_letters_the_games_font_draws(self) -> None:
        import vv_font_glyphs as glyphs
        missing = set(glyphs.missing("vv4", "ldwBurweed27"))
        for _, key, english, _ in dp.rows():
            self.assertFalse(set(english) & missing, key)
            self.assertTrue(all(32 <= ord(c) < 127 for c in english), key)

    def test_the_owners_wording(self) -> None:
        """Every shown line of the owner's text (the approved fixes applied; curly quotes, apostrophes and the
        ellipsis in the font's letters) is one of ours, exactly, in both sexes; the instructions are never shown;
        nothing of ours is extra."""
        owner = OWNER_TEXT.read_text(encoding="utf-8")
        owner = owner.replace("“", '"').replace("”", '"').replace("’", "'").replace("…", "...")
        title, body = owner.split("\n", 1)
        self.assertEqual(title.split(" --")[0], dp.TITLE + ".")
        for form, sub in (("f", {"(he/she)": "she", "(He/she)": "She", "(his/her)": "her", "(His/her)": "Her",
                                 "(fisherman/fisherwoman)": "fisherwoman"}),
                          ("m", {"(he/she)": "he", "(He/she)": "He", "(his/her)": "his", "(His/her)": "His",
                                 "(fisherman/fisherwoman)": "fisherman"})):
            with self.subTest(form=form):
                filled = {key: dp.fill(key, form, "Ana", 300) for key, _ in dp.TEXTS}
                ours = " ".join(" ".join(words(t)) for t in filled.values())
                used = []
                for line in body.splitlines():
                    line = line.strip()
                    if not line or line.startswith("--"):
                        continue
                    if line.endswith(":") and line[:-1] in LABELS:
                        used.append(line[:-1])
                        continue
                    shown = line.replace("(Name)", "Ana").replace("(name)", "Ana").replace("(award)", "300")
                    for k, v in sub.items():
                        shown = shown.replace(k, v)
                    self.assertNotIn("(", shown)
                    self.assertIn(" ".join(words(shown)), ours, line)
                    used.append(shown)
                joined = " ".join(" ".join(words(u)) for u in used)
                for key, text in filled.items():
                    if key != "TITLE":
                        self.assertIn(" ".join(words(text)), joined, key)

    def test_the_owners_fixes(self) -> None:
        text = " ".join(t for _, t in dp.TEXTS)
        for needle in ("accidentally gotten hit by their tail flipper.", "hold {his} breath", "shares {his} observations",
                       "doubts that it's a good idea", "\"What magnificent creatures!\" {he} thinks.",
                       "leaves the beach", "aquaculture"):
            self.assertIn(needle, text)
        for gone in ("accidentally got hit", "exits the beach", "hold their breath"):
            self.assertNotIn(gone, text)

    def test_the_labels_fit_the_screen_whole(self) -> None:
        table = json.loads((ROOT / "data" / "cie_label_widths.json").read_text(encoding="utf-8"))["games"]["4"]
        for label in LABELS:
            width = sum(table["widths"][ord(c) - 32] + table["spacing"] for c in label)
            self.assertLessEqual(width, table["max_px"], label)


class TheOdds(unittest.TestCase):
    def test_the_owners_table(self) -> None:
        c = dp.outcome_chances()
        self.assertEqual(c["SWIM"], {"HUNT": 50.0, "SLAP": 50.0})
        self.assertEqual(c["BACK"], {"BACK": 100.0})

    def test_the_companion_rolls_the_same_odds(self) -> None:
        core = (NATIVE / "dolphin_core.inc").read_text(encoding="utf-8")
        for needle in ("dp.slap = !adv_percent(t->g, 50);", "dp.loss = 30 + t->g->rand_below(21);",
                       "dp.hunt_award = adv_award_roll(t->g, ADV_KIND_FOOD, 2);",
                       "dp.back_award = adv_award_roll_part(t->g, ADV_KIND_FOOD, 1, 2);",
                       "adv_possible(t->g)", "#define DP_HEALTH_LEFT 1",
                       "g->skill(dp.swimmer, ADV_SKILL_FARMING, DP_MASTER_GAIN);"):
            self.assertIn(needle, core)

    def test_no_puzzle_is_asked(self) -> None:
        """The owner: it needs no Fishing Nets (nor any puzzle) -- the event's code reads no puzzle flag."""
        source = "".join((NATIVE / f).read_text(encoding="utf-8") for f in ("dolphin_core.inc", "dolphin_vv4.inc"))
        for needle in ("0x4D8B", "0x4D8C", "cave_open", "puzzle_done"):
            self.assertNotIn(needle, source)

    def test_the_game_mechanics_entry(self) -> None:
        import vv_game_mechanics_events_vv4 as catalog
        event = next(e for e in catalog.EVENTS if e.title == dp.TITLE)
        self.assertEqual(event.only_with, "vv4_more_island_events")
        text = event.text + " " + " ".join(s if isinstance(s, str) else s.text for s in event.subs)
        for needle in ("14 villager years or more", "not nursing a baby", "not a body or a ghost", "under 14",
                       "Needs no fishing nets or other puzzle.", "wall clock", "50%", "Farming becomes 100",
                       "600 food", "150 food", "30 to 50", "never below 1", "one entry", "Island Events Scale"):
            self.assertIn(needle, text)


# ---- Who (emulated) --------------------------------------------------------------------------------------------------

@NEEDS
class Who(unittest.TestCase):
    def test_13_never_14_yes(self) -> None:
        v = Dolphins()
        v.villager(0, "Ana", True, years=30)
        v.villager(1, "Kid", years=13)
        self.assertEqual(v.dp_possible(), 0)                 # 13: never
        v.villager(1, "Kid", years=14)
        self.assertEqual(v.dp_possible(), 1)                 # 14: yes
        for swimmer in (0, TOP):
            self.assertTrue(v.open(dp_rolls(swimmer=swimmer, candidates=2)))
            self.assertIn(v.dp_state()[0], (0, 1))
        v.villager(2, "Young", years=13)
        for swimmer in range(4):
            self.assertTrue(v.open(dp_rolls(swimmer=swimmer)))
            self.assertNotEqual(v.dp_state()[0], 2)

    def test_two_needed(self) -> None:
        v = Dolphins()
        v.villager(0, "Ana", True, years=30)
        self.assertEqual(v.dp_possible(), 0)
        v.villager(1, "Ben", years=30)
        self.assertEqual(v.dp_possible(), 1)

    def test_protected_never_picked(self) -> None:
        for what, kw in (("a nursing mother", dict(woman=True, carrying=500)),
                         ("a nursing father", dict(woman=False, carrying=500)),
                         ("a body or a ghost", dict(special=(0x1CC7, 1, 1))),
                         ("thirteen", dict(years=13))):
            with self.subTest(what=what):
                v = Dolphins()
                v.villager(0, "Ana", True, years=30)
                v.villager(1, "Bad", **{"years": 30, **kw})
                self.assertEqual(v.dp_possible(), 0)
                v.villager(2, "Cal", years=30)
                self.assertEqual(v.dp_possible(), 1)
                for swimmer in (0, TOP):
                    self.assertTrue(v.open(dp_rolls(swimmer=swimmer, candidates=2)))
                    self.assertIn(v.dp_state()[0], (0, 2))

    def test_the_fishing_nets_are_never_needed(self) -> None:
        """The owner: it can happen whether or not the Fishing Nets are mended (the game's puzzle 11)."""
        for progress, done_at in ((0, 5), (5, 5)):
            with self.subTest(progress=progress, done_at=done_at):
                v = three()
                v.p.put32(PUZZLE_PROGRESS, progress)
                v.p.put32(PUZZLE_DONE_AT, done_at)
                self.assertEqual(v.dp_possible(), 1)
                added, obj = v.list_draw(DOLPHINS_PICK)
                self.assertEqual(added, 0)
                self.assertTrue(v.can_fire(obj))
                self.assertTrue(v.open(dp_rolls()))
                v.play(0)
                self.assertEqual(ENDINGS[v.dp_state()[8]], "HUNT")


# ---- The branches, their odds and their effects (emulated) ------------------------------------------------------------

@NEEDS
class Branches(unittest.TestCase):
    def ending(self, answer: int = 0, **kw) -> str:
        v = three()
        self.assertTrue(v.open(dp_rolls(**kw)))
        v.play(answer)
        return ENDINGS[v.dp_state()[8]]

    def test_both_branches_at_their_odds(self) -> None:
        # rand(100) < 50 the hunt (50 values of 100), else the tail slap (50 values).
        v = three()
        for roll, want in ((0, "HUNT"), (49, "HUNT"), (50, "SLAP"), (99, "SLAP")):
            with self.subTest(roll=roll):
                v = three()
                self.assertTrue(v.open([0, roll, 0]))
                v.play(0)
                self.assertEqual(ENDINGS[v.dp_state()[8]], want)
        self.assertEqual(self.ending(answer=1), "BACK")
        self.assertEqual(self.ending(answer=1, slap=True), "BACK")      # "Hang back": always

    def test_the_hunt_farming_100_and_a_large_award(self) -> None:
        for start in (0.0, 50.0, 87.5, 100.0):
            with self.subTest(start=start):
                v = three()
                v.set_farming(0, start)
                v.set_farming(1, 50.0)
                before = v.stores()
                self.assertTrue(v.open(dp_rolls(swimmer=0)))
                s = v.dp_state()
                self.assertEqual(s[3], 2 * FOOD_LO)                 # twice a normal award: 600
                v.play(0)
                self.assertEqual(v.farming(0), 100.0)               # the game's maximum
                self.assertEqual(v.farming(1), 50.0)
                after = v.stores()
                self.assertEqual((after[0] - before[0], after[1] - before[1]), (2 * FOOD_LO, 0))
                self.assertEqual(v.health(0), 100)

    def test_hang_back_a_small_award(self) -> None:
        v = three()
        v.set_farming(0, 50.0)
        before = v.stores()
        self.assertTrue(v.open(dp_rolls(swimmer=0)))
        self.assertEqual(v.dp_state()[4], FOOD_LO // 2)              # half a normal award: 150
        v.play(1)
        after = v.stores()
        self.assertEqual((after[0] - before[0], after[1] - before[1]), (FOOD_LO // 2, 0))
        self.assertEqual((v.farming(0), v.health(0)), (50.0, 100))

    def test_the_awards_scale_as_island_events_scale_scales(self) -> None:
        """With "VVFP Island Events Scale.dll" (stood in for), both awards are scaled by its rule, as the other
        events of The Tree of Life are: the population (x2 over 25, x3 over 50) or a tenth of the store."""
        for mode, people, hunt, back in ((1, 30, 2 * 600, 2 * 150), (1, 51, 3 * 600, 3 * 150),
                                         (2, 0, 600 + 400, 150 + 400)):
            for answer in (0, 1):
                with self.subTest(mode=mode, people=people, answer=answer):
                    v = three()
                    p = v.p
                    fake = 0x0E900000
                    mode_stub = p.alloc(16)
                    p.write(mode_stub, b"\xC3")
                    p.stub(mode_stub, lambda pr, mode=mode: (mode, 0))
                    p.stub(0x467610, lambda pr, people=people: (people, 0))
                    module, proc = p.api_handlers["GetModuleHandleA"], p.api_handlers["GetProcAddress"]
                    p.api_handlers["GetModuleHandleA"] = lambda pr, m=module: (
                        (fake, 4) if pr.arg(0) and pr.cstring(pr.arg(0)) == "VVFP Island Events Scale.dll"
                        else m(pr))
                    p.api_handlers["GetProcAddress"] = lambda pr, c=proc: (
                        (mode_stub, 8) if pr.arg(0) == fake else c(pr))
                    p.put32(T["food"], 4000)
                    self.assertTrue(v.open(dp_rolls()))
                    s = v.dp_state()
                    self.assertEqual((s[3], s[4]), (hunt, back))
                    before = v.stores()[0]
                    v.play(answer)
                    self.assertEqual(v.stores()[0] - before, hunt if answer == 0 else back)
                    text = " ".join(v.dp_pages(1 if answer == 0 else 3))
                    self.assertIn(f" {hunt if answer == 0 else back} food.", text)

    def test_the_slap_30_to_50_health_never_dead(self) -> None:
        for start, loss, want in ((100, 0, 70), (100, TOP, 50), (100, 10, 60), (80, 0, 50), (40, TOP, 1),
                                  (31, 0, 1), (30, 0, 1), (1, TOP, 1)):
            with self.subTest(start=start, loss=loss):
                v = three()
                v.set_health(0, start)
                v.set_farming(0, 50.0)
                self.assertTrue(v.open(dp_rolls(swimmer=0, slap=True, loss=loss)))
                s = v.dp_state()
                self.assertEqual(s[5], 50 if loss == TOP else 30 + loss)
                before = v.stores()
                v.play(0)
                self.assertEqual(ENDINGS[v.dp_state()[8]], "SLAP")
                self.assertEqual(v.health(0), want)
                self.assertGreaterEqual(v.health(0), 1)
                self.assertEqual(v.present(0), 1)
                self.assertEqual(v.stores(), before)
                self.assertEqual(v.farming(0), 50.0)
                self.assertEqual(v.vanished, [])
                deaths = [c for c in v.calls if c[0] == "stop" or (c[0] == "health" and c[2] <= 0)]
                self.assertEqual(deaths, [])                          # never the game's death path
                setter = [c for c in v.calls if c[0] == "health"]
                self.assertEqual(setter, [] if start == 1 else [("health", v.rec(0), want, -1)])


# ---- The pages, the log, the save (emulated) ----------------------------------------------------------------------

@NEEDS
class Pages(unittest.TestCase):
    CASES = {"HUNT": (0, dict()), "SLAP": (0, dict(slap=True)), "BACK": (1, dict())}

    def test_the_effects_on_the_last_page_only_and_one_entry(self) -> None:
        for name, (answer, kw) in self.CASES.items():
            with self.subTest(ending=name):
                v = three()
                calls = fake_log(v)
                before = v.snapshot()
                self.assertTrue(v.open(dp_rolls(swimmer=0, **kw)))
                steps = v.play(answer, calls)
                last = len(steps) - 2                               # the click that showed the last page
                pages = v.dp_state()[11 + ENDINGS.index(name)]
                self.assertGreaterEqual(pages, len(dp.pages_of(name)))
                self.assertEqual(len(steps), v.dp_state()[10] - 1 + pages + 1)
                for kind, state, logged in steps[:last]:
                    self.assertEqual(state, before, kind)           # nothing before the ending's last page
                    self.assertEqual(logged, 0, kind)               # and nothing handed to the log
                self.assertEqual(steps[-1][1], steps[last][1])      # nothing more at the close
                self.assertNotEqual(steps[last][1], before)
                self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
                entry = calls[-1][2]
                self.assertEqual(entry.count("  Event: "), 1)
                self.assertEqual(entry.count("  Choice: "), 1)
                self.assertTrue(entry.startswith(f"  Event: {dp.TITLE}\n  Choice: {LABELS[answer]}\n"))
                self.assertEqual(calls[-1][3], 1)
                self.assertEqual(v.dp_state()[9], 1)

    def test_nothing_at_a_save_or_quit_before_the_last_page(self) -> None:
        """A long name makes the hunt two pages or more: a save between them holds neither the effects nor the
        entry; the left event never comes back, and the next one writes its own one entry."""
        v = three()
        v.p.write(v.rec(0) + 0x1B9C, b"Abcdefghijklmnopqrstuvwx\0")
        calls = fake_log(v)
        before = v.snapshot()
        self.assertTrue(v.open(dp_rolls(swimmer=0)))
        for _ in range(v.dp_state()[10] - 1):
            v.click(0)
        v.click(1)                                                  # "Swim towards the dolphins"
        pages = v.dp_state()[11]
        for _ in range(pages - 2):
            v.click(0)
        self.assertGreater(pages, 1)
        self.assertEqual(calls, [])                                 # a save or a quit now: nothing
        self.assertEqual(v.snapshot(), before)
        self.assertTrue(v.open(dp_rolls(swimmer=1)))                # reloaded: a new draw
        self.assertEqual(v.snapshot(), before)
        v.play(1)
        self.assertEqual(v.farming(0), 50.0)
        self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
        v.click(0)                                                  # OK again after the close: nothing twice
        self.assertEqual([c[0] for c in calls].count("write"), 1)

    def test_the_words_as_shown(self) -> None:
        for woman in (False, True):
            with self.subTest(woman=woman):
                v = three()
                v.p.write(v.rec(0) + 0x1B9C, b"Dolly Fin\0")
                v.p.put32(v.rec(0) + 0x1B90, 1 if woman else 0)
                self.assertTrue(v.open(dp_rolls(swimmer=0)))
                s = v.dp_state()
                form = "f" if woman else "m"
                self.assertEqual(words(" ".join(v.dp_pages(0))), words(dp.fill("INTRO", form, "Dolly Fin")))
                for k, name in enumerate(ENDINGS):
                    award = s[3] if name == "HUNT" else (s[4] if name == "BACK" else 0)
                    keys = [key for popup in dp.pages_of(name) for key in popup]
                    expected = " ".join(dp.fill(key, form, "Dolly Fin", award) for key in keys)
                    shown = v.dp_pages(1 + k)
                    self.assertEqual(words(" ".join(shown)), words(expected), name)
                    for page in shown:
                        self.assertLessEqual(len(page), 1990)
                hunt = " ".join(v.dp_pages(1))
                self.assertIn("becomes a skilled " + ("fisherwoman" if woman else "fisherman") + " and", hunt)
                slap = " ".join(v.dp_pages(2))
                self.assertIn("accidentally gotten hit by their tail flipper.", slap)
                self.assertIn("any deeper... " + ("she" if woman else "he") + " shudders", slap)

    def test_the_popup_shows_the_pages_in_order(self) -> None:
        v = three()
        self.assertTrue(v.open(dp_rolls(swimmer=0, slap=True)))
        intro = v.dp_pages(0)
        for _ in range(len(intro) - 1):
            v.click(0)
        v.click(1)
        result = v.dp_pages(2)
        seen = [v.shown()]
        for _ in range(len(result) - 1):
            v.click(0)
            seen.append(v.shown())
        self.assertEqual(seen, result)
        v.ui.clear()
        v.click(0)
        self.assertTrue(v.closed())


# ---- The draw: its own entry with the other events of The Tree of Life (emulated) -------------------------------------

@NEEDS
class TheDraw(unittest.TestCase):
    """Never a share of the draw (stock island event chances never change): the selector's list gains no entry; the
    due event's object is in slot 0, for Story's pick to present."""

    def test_the_due_event_in_slot_0_and_no_entry(self) -> None:
        titles = []
        for pick in (0, DOLPHINS_PICK):
            v = three()
            added, obj = v.list_draw(pick)
            self.assertEqual(added, 0)
            self.assertTrue(v.can_fire(obj))
            titles.append(v.title_of(obj))
        self.assertEqual(titles, ["The Aspiring Adventurer", dp.TITLE])

    def test_due_but_not_possible(self) -> None:
        v = Dolphins()
        v.villager(0, "Ana", True, years=30)
        added, obj = v.list_draw(DOLPHINS_PICK)
        self.assertEqual(added, 0)
        self.assertFalse(v.can_fire(obj))

    def test_nothing_due_nothing_listed(self) -> None:
        v = three()
        for listed in (0, 10, 49):
            with self.subTest(listed=listed):
                self.assertEqual(v.list_draw(-1, listed=listed)[0], 0)

    def test_never_writes_the_list(self) -> None:
        for listed in (0, 47, 49):
            with self.subTest(listed=listed):
                v = three()
                p = v.p
                esp = STACK_TOP - 0x2000
                for k in range(listed, 64):
                    p.put32(esp + T["offset"] + 4 * k, 0xA5A5A5A5)
                v.due = DOLPHINS_PICK
                self.assertEqual(v.run_list(listed), listed)
                for k in range(listed, 64):
                    self.assertEqual(p.u32(esp + T["offset"] + 4 * k), 0xA5A5A5A5)


@NEEDS
class TheGameData(unittest.TestCase):
    def test_the_games_own_caps(self) -> None:
        """The Tree of Life's own skill adder 0x46AD80 caps at the double 100.0 (0x48A7C0) with 100.0f (0x48CF04);
        its health setter 0x46AF00 stores the value at [block + 0xC] (record +0x1C40) and caps it at 0x64."""
        import pefile
        pe = pefile.PE(str(STOCK[4]))
        base = pe.OPTIONAL_HEADER.ImageBase

        def at(va: int, n: int) -> bytes:
            off = pe.get_offset_from_rva(va - base)
            return pe.__data__[off:off + n]
        self.assertEqual(struct.unpack("<d", at(0x48A7C0, 8))[0], 100.0)
        self.assertEqual(struct.unpack("<f", at(0x48CF04, 4))[0], 100.0)
        self.assertIn(b"\xDC\x15\xC0\xA7\x48\x00", at(0x46AD80, 0x40))       # fcom qword [0x48A7C0]
        self.assertEqual(at(0x46AF00, 9), bytes.fromhex("8B44240485C089410C"))   # mov [ecx+0xC], eax
        self.assertIn(b"\x83\xF8\x64", at(0x46AF00, 0x30))                   # cmp eax, 0x64


if __name__ == "__main__":
    unittest.main()
