"""Diving for Treasure: the owner's island event for The Secret City (2026-11-13), in "More Island Events".

Static (always run): the words are the owner's (src/vv_diving_for_treasure.py, the companion's table generated from
it, a translation row for every piece), in letters the game's font draws; the odds are the owner's table.

EMULATED (unicorn, the stock The Secret City executable, the built "VVFP More Island Events.dll"; tests/story_emulator.py,
the villagers in the game's own records as tests/test_aspiring_adventurer.py puts them, the popup through the game's
own click handler, OK and constructor sites):
  * who: the diver and the head Doctor are villagers of 18 or more who are not protected, never the same one; under
    18, nursing (mother or father), the Tribal Chief and look-alike records never; two such villagers are needed;
  * every branch reachable, at its odds (the rolls' boundaries: 1 in 4 finds; 75 / 25; 17 / 17 / 66);
  * every effect: the tech and food awards in The Secret City's scaled range, "dislikes swimming" (preference 37),
    the death (a grave: health 0, the game's own death), the disappearance (no body, Cause of Death told), the
    Healing and Parenting gains capped at 100;
  * the effects on the ending's last page only; the Island Events log's one entry; nothing at a save or quit before
    the last page, and a left event never comes back;
  * the draw: one entry for each More Island Events event that can happen (1, 2 and 3), each event's object in slot 0
    as often as the others, and never an entry past the list's room.

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

import vv_diving_for_treasure as dt  # noqa: E402
from test_aspiring_adventurer import DLL, HAVE_EMULATOR, HAVE_STOCK, STOCK, TABLES, TOP, Village  # noqa: E402
from test_more_island_events_pages import fake_log  # noqa: E402

try:
    from story_emulator import STACK_TOP  # noqa: E402
except ImportError:                       # pragma: no cover
    STACK_TOP = 0

NATIVE = ROOT / "native" / "vvfp_more_island_events"
OWNER_TEXT = ROOT / "tests" / "data" / "diving_for_treasure_owner_text.txt"
LABELS = (dict(dt.TEXTS)["LABEL_DEEPER"], dict(dt.TEXTS)["LABEL_NOT"])
ENDINGS = dt.ENDINGS                                  # A, B, C, D1, D2A, D2B, D2C, NOT
T = TABLES[3]
LIKES, DISLIKES, PARENTING, HEALING = 0xFB4, 0xFC0, 0xEB0, 0xEB4
SWIMMING = 37
TITLE_ID = 0x3A7


def words(text: str) -> list[str]:
    return re.sub(r"\s+", " ", text).strip().split(" ")


def dive_rolls(*, diver=0, doctor=0, find=0, survive=True, sink="rescued", heal=0, parent=0, tech=0, food=0,
               candidates=3) -> list[int]:
    """The rolls dv_begin draws, in its order (the game's rand is asked only when there is a choice: with two
    candidates the head Doctor is the other one, no roll).  find 0..3 (A..D); sink "dies", "disappears", "rescued"
    (or the raw roll); heal / parent: the gain - 10; tech / food: the award's draw (TOP the largest), each followed
    by the game's own count's draw (0x45D460)."""
    sink_roll = {"dies": 0, "disappears": 20, "rescued": 50}.get(sink, sink)
    out = ([diver] if candidates > 1 else []) + ([doctor] if candidates > 2 else [])
    out += [find, 0 if survive is True else (99 if survive is False else survive), sink_roll, heal, parent]
    return out + [tech, 0, food, 0]


class Dive(Village):
    """The Secret City with the companion, its villagers and Diving for Treasure's popup."""

    def __init__(self):
        super().__init__(3)
        self.p.stub(0x436E60, lambda pr: (0, 12))           # the food trophy's notice
        self.p.stub(0x412CD0, lambda pr: (0, 4))

    def adults(self, n: int = 3, first: int = 0, years: int = 30) -> None:
        for k in range(n):
            self.villager(first + k, f"Diver{first + k}", k % 2 == 0, years=years)

    def dv_possible(self) -> int:
        return self.p.export("VvfpDivingPossible")

    def dv_state(self) -> list[int]:
        out = self.p.alloc(23 * 4)
        self.p.export("VvfpDivingState", out)
        return [struct.unpack("<i", self.p.read(out + 4 * k, 4))[0] for k in range(23)]

    def dv_pages(self, which: int) -> list[str]:
        out, k = [], 0
        while True:
            at = self.p.export("VvfpDivingPage", which, k)
            if not at:
                return out
            out.append(self.p.cstring(at, 4000))
            k += 1

    def i32(self, i: int, off: int) -> int:
        return struct.unpack("<i", self.p.read(self.rec(i) + off, 4))[0]

    def likes(self, i: int) -> list[int]:
        return [self.i32(i, LIKES + 4 * k) for k in range(3)]

    # -- the draw ------------------------------------------------------------------------------------------------
    def list_draw(self, coin: int, listed: int = 0, sentinel: bool = False) -> tuple[int, int]:
        """The selector's loop with every stock slot empty and `listed` entries already in the list: (entries the
        companion added, the object in slot 0)."""
        p = self.p
        esp = STACK_TOP - 0x2000
        if sentinel:
            for k in range(listed, 64):
                p.put32(esp + T["offset"] + 4 * k, 0xA5A5A5A5)
        self.rolls = [coin]
        p.set_reg("esp", esp)
        p.set_reg("esi", 1)
        p.set_reg("edi", listed)
        p.run(*T["loop"])
        self.rolls = []
        self.obj = p.u32(T["table"])
        self.list_esp = esp
        return p.reg("edi") - listed, self.obj

    def title_of(self, obj: int) -> str:
        """The title an event object gives (its +0x08, as the dialog asks it first)."""
        self.p.call(self.p.u32(self.p.u32(obj) + 8), ecx=obj)
        entry = self.p.u32(T["strings"] + 4 * TITLE_ID)
        return self.p.cstring(self.p.u32(entry + 8), 400)

    # -- the popup -----------------------------------------------------------------------------------------------
    def open(self, rolls: list[int], coin: int = 1) -> bool:
        """Diving for Treasure drawn (`coin` its index among the events that can happen: 1 after the Adventurer)
        and its popup built through the game's presenter site."""
        p = self.p
        entries, obj = self.list_draw(coin)
        if not entries:
            return False
        self.ui.clear()
        self.rolls = list(rolls)
        if self.title_of(obj) != dt.TITLE:
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
            out.append((self.present(i), self.health(i), self.i32(i, HEALING), self.i32(i, PARENTING),
                        tuple(self.dislikes(i)), tuple(self.likes(i))))
        return tuple(out)

    def play(self, answer: int) -> list[tuple]:
        """The whole event: (what was clicked, the village after it) for each click; answer 0 "Swim deeper", 1
        "Better not"."""
        s = self.dv_state()
        steps = []
        for _ in range(s[14] - 1):
            self.click(0)
            steps.append(("ok", self.snapshot()))
        self.click(1 + answer)
        steps.append(("answer", self.snapshot()))
        pages = self.dv_state()[15 + self.dv_state()[12]]
        for _ in range(pages - 1):
            self.click(0)
            steps.append(("ok", self.snapshot()))
        self.ui.clear()
        self.click(0)
        steps.append(("close", self.snapshot()))
        return steps


def three(**kw) -> Dive:
    v = Dive()
    v.adults(3, **kw)
    return v


NEEDS = unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(),
                            "needs unicorn, pefile, the stock executables and the built DLL")


# ---- The words and the odds (no emulator) ---------------------------------------------------------------------------

class TheWords(unittest.TestCase):
    def test_every_piece_is_a_key_row_with_its_english(self) -> None:
        rows = {r["stem"]: r for r in json.loads((ROOT / "data" / "translations" / "patcher_strings.json")
                                                 .read_text(encoding="utf-8"))["strings"]}
        for stem, key, english, _ in dt.rows():
            with self.subTest(stem=stem):
                self.assertIn(stem, rows)
                self.assertEqual(rows[stem]["english"], english)
                self.assertEqual(rows[stem]["games"], ["vv3"])
                self.assertEqual(rows[stem]["route"], "key")

    def test_the_companions_table_is_generated_from_the_one_source(self) -> None:
        import build_more_island_events as builder
        self.assertEqual((NATIVE / "dive_text.inc").read_text(encoding="utf-8"), builder.dive_text_inc())

    def test_only_letters_the_games_font_draws(self) -> None:
        import vv_font_glyphs as glyphs
        missing = set(glyphs.missing("vv3", "ldwBurweed27"))
        for _, key, english, _ in dt.rows():
            self.assertFalse(set(english) & missing, key)
            self.assertTrue(all(32 <= ord(c) < 127 for c in english), key)

    def test_the_owners_wording(self) -> None:
        """Every shown line of the owner's text (the approved fixes applied; curly quotes, apostrophes and the
        ellipsis in the font's letters) is one of ours, exactly, in both sexes; the instructions are never shown;
        nothing of ours is extra."""
        owner = OWNER_TEXT.read_text(encoding="utf-8")
        owner = owner.replace("“", '"').replace("”", '"').replace("’", "'").replace("…", "...")
        title, body = owner.split("\n", 1)
        self.assertEqual(title.split(" --")[0], dt.TITLE + ".")
        for form, sub in (("f", {"(he/she)": "she", "(He/she)": "She", "(his/her)": "her", "(His/her)": "Her",
                                 "(him/her)": "her", "(himself/herself)": "herself", "(father/mother)": "mother"}),
                          ("m", {"(he/she)": "he", "(He/she)": "He", "(his/her)": "his", "(His/her)": "His",
                                 "(him/her)": "him", "(himself/herself)": "himself", "(father/mother)": "father"})):
            with self.subTest(form=form):
                filled = {key: dt.fill(key, form, "Ana", "Ben", 300) for key, _ in dt.TEXTS}
                ours = " ".join(" ".join(words(t)) for t in filled.values())
                used = []
                for line in body.splitlines():
                    line = line.strip()
                    if not line or line.startswith("--"):
                        continue
                    if line.endswith(":") and line[:-1] in LABELS:
                        used.append(line[:-1])
                        continue
                    shown = line.replace("(Name)", "Ana").replace("(name)", "Ana").replace("(random name)", "Ben")
                    shown = shown.replace("(award)", "300")
                    for k, v in sub.items():
                        shown = shown.replace(k, v)
                    self.assertNotIn("(", shown)
                    self.assertIn(" ".join(words(shown)), ours, line)
                    used.append(shown)
                joined = " ".join(" ".join(words(u)) for u in used)
                for key, text in filled.items():
                    if key != "TITLE":
                        self.assertIn(" ".join(words(text)), joined, key)

    def test_the_labels_fit_the_screen_whole(self) -> None:
        table = json.loads((ROOT / "data" / "cie_label_widths.json").read_text(encoding="utf-8"))["games"]["3"]
        for label in LABELS:
            width = sum(table["widths"][ord(c) - 32] + table["spacing"] for c in label)
            self.assertLessEqual(width, table["max_px"], label)


class TheOdds(unittest.TestCase):
    def test_the_owners_table(self) -> None:
        c = dt.outcome_chances()
        deeper = c["DEEPER"]
        for e in ("A", "B", "C"):
            self.assertAlmostEqual(deeper[e], 25.0)
        self.assertAlmostEqual(deeper["D1"], 18.75)
        self.assertAlmostEqual(deeper["D2A"], 1.0625)
        self.assertAlmostEqual(deeper["D2B"], 1.0625)
        self.assertAlmostEqual(deeper["D2C"], 4.125)
        self.assertAlmostEqual(sum(deeper.values()), 100.0)
        self.assertEqual(c["NOT"], {"NOT": 100.0})

    def test_the_companion_rolls_the_same_odds(self) -> None:
        core = (NATIVE / "dive_core.inc").read_text(encoding="utf-8")
        for needle in ("dv.find = t->g->rand_below(4);", "dv.survives = adv_percent(t->g, 75);",
                       "dv.sink = roll < 17 ? 0 : (roll < 34 ? 1 : 2);", "dv.healing_gain = 10 + t->g->rand_below(11);",
                       "dv.parenting_gain = 10 + t->g->rand_below(11);",
                       "dv.tech_award = adv_award_roll(t->g, ADV_KIND_TECH, 1);",
                       "dv.food_award = adv_award_roll(t->g, ADV_KIND_FOOD, 1);",
                       "dv_count(t, -1) >= 2", "t->g->eligible(r) && t->age(r) >= DV_ADULT_UNITS"):
            self.assertIn(needle, core)
        vv3 = (NATIVE / "dive_vv3.inc").read_text(encoding="utf-8")
        self.assertIn("#define DV_VV3_SWIMMING 37", vv3)

    def test_the_game_mechanics_entry(self) -> None:
        import vv_game_mechanics_events_vv3 as catalog
        event = next(e for e in catalog.EVENTS if e.title == dt.TITLE)
        self.assertEqual(event.only_with, "vv3_more_island_events")
        text = event.text + " " + " ".join(s if isinstance(s, str) else s.text for s in event.subs)
        for needle in ("18 villager years or more", "not nursing a baby", "not the Tribal Chief", "never the diver",
                       "wall clock", "25%", "18.75%", "1.06%", "4.13%", "17%", "66%", "dislikes swimming",
                       "1,000 to 2,000 tech points", "200 to 600 food", "+10 to 20 Healing", "+10 to 20 Parenting",
                       "at most 100", "a grave", "no grave", "one entry"):
            self.assertIn(needle, text)
        self.assertNotIn("highest Healing", text)              # the head Doctor is a name only (the owner)

    def test_swimming_is_preference_37_in_the_games_own_list(self) -> None:
        exe = STOCK[3].read_bytes() if STOCK[3].is_file() else b""
        if not exe:
            self.skipTest("needs the stock executable")
        at = exe.index(b" ants, crowds")
        self.assertEqual(at, 0x97488)
        names = [s.strip() for s in exe[at:exe.index(b"\0", at)].decode().split(",")]
        self.assertEqual((names.index("swimming"), names.index("running")), (dt.SWIMMING, 38))


# ---- Who (emulated) --------------------------------------------------------------------------------------------------

@NEEDS
class Who(unittest.TestCase):
    def test_two_adults_needed_under_18_never(self) -> None:
        v = Dive()
        v.villager(0, "Ana", True, years=18)
        self.assertEqual(v.dv_possible(), 0)                 # one adult: nobody to name on the rescue page
        v.villager(1, "Kid", years=17)
        self.assertEqual(v.dv_possible(), 0)                 # 17: never
        v.villager(1, "Ben", years=18)
        self.assertEqual(v.dv_possible(), 1)

    def test_protected_never_picked(self) -> None:
        for what, kw in (("a nursing mother", dict(woman=True, carrying=500)),
                         ("a nursing father", dict(woman=False, carrying=500)),
                         ("the Tribal Chief", dict(special=(0xE80, 1, 1))),
                         ("a look-alike record", dict(special=(0xE94, 1, 1))),
                         ("seventeen", dict(years=17))):
            with self.subTest(what=what):
                v = Dive()
                v.villager(0, "Ana", True, years=30)
                v.villager(1, "Bad", **{"years": 30, **kw})
                self.assertEqual(v.dv_possible(), 0)
                v.villager(2, "Cal", years=30)
                self.assertEqual(v.dv_possible(), 1)
                for diver in (0, TOP):
                    for doctor in (0, TOP):
                        self.assertTrue(v.open(dive_rolls(diver=diver, doctor=doctor, candidates=2)))
                        s = v.dv_state()
                        self.assertNotIn(1, (s[0], s[1]))
                        self.assertEqual({s[0], s[1]}, {0, 2})

    def test_diver_and_doctor_any_adult_never_the_same(self) -> None:
        v = Dive()
        v.adults(5)
        v.villager(5, "Old", years=70)                       # an elder: fair game
        seen_divers, seen_doctors = set(), set()
        for diver in range(6):
            for doctor in range(5):
                self.assertTrue(v.open(dive_rolls(diver=diver, doctor=doctor)))
                s = v.dv_state()
                self.assertNotEqual(s[0], s[1])
                seen_divers.add(s[0])
                seen_doctors.add(s[1])
        self.assertEqual(seen_divers, set(range(6)))
        self.assertEqual(seen_doctors, set(range(6)))


# ---- The branches, their odds and their effects (emulated) ------------------------------------------------------------

@NEEDS
class Branches(unittest.TestCase):
    def ending(self, **kw) -> str:
        v = three()
        self.assertTrue(v.open(dive_rolls(**kw)))
        v.play(kw.pop("answer", 0))
        return ENDINGS[v.dv_state()[12]]

    def test_every_branch_at_its_odds(self) -> None:
        # rand(4): each find one value of four.
        for find, want in enumerate(("A", "B", "C")):
            self.assertEqual(self.ending(find=find), want)
        # D: rand(100) < 75 survives (75 values of 100), else sinks.
        self.assertEqual(self.ending(find=3, survive=74), "D1")
        self.assertEqual(self.ending(find=3, survive=0), "D1")
        self.assertEqual(self.ending(find=3, survive=75, sink=50), "D2C")
        # Sinking: rand(100) < 17 dies, < 34 disappears (17 values), else rescued (66 values).
        for roll, want in ((0, "D2A"), (16, "D2A"), (17, "D2B"), (33, "D2B"), (34, "D2C"), (99, "D2C")):
            with self.subTest(roll=roll):
                self.assertEqual(self.ending(find=3, survive=False, sink=roll), want)
        v = three()
        self.assertTrue(v.open(dive_rolls(find=0)))
        v.play(1)
        self.assertEqual(ENDINGS[v.dv_state()[12]], "NOT")    # "Better not": always

    def test_a_and_c_awards_in_range(self) -> None:
        for find, kind, (lo, hi) in ((0, 1, (1000, 2000)), (2, 0, (200, 600))):
            for draw in (0, TOP):
                with self.subTest(find=find, draw=draw):
                    v = three()
                    v.p.put32(T["food"], 5000)
                    v.p.put32(T["tech"], 5000)
                    self.assertTrue(v.open(dive_rolls(find=find, tech=draw, food=draw)))
                    s = v.dv_state()
                    amount = s[6] if kind == 1 else s[7]
                    m = s[6] // (1000 if draw == 0 else 2000)        # The Secret City's own factor
                    self.assertGreaterEqual(m, 1)
                    self.assertEqual(amount, (lo if draw == 0 else hi) * m)
                    before = v.stores()
                    v.play(0)
                    after = v.stores()
                    self.assertEqual(after[kind] - before[kind], amount)    # through the game's own writer
                    self.assertEqual(after[1 - kind], before[1 - kind])

    def test_b_nothing_happens(self) -> None:
        v = three()
        self.assertTrue(v.open(dive_rolls(find=1)))
        before = v.snapshot()
        v.play(0)
        self.assertEqual(v.snapshot(), before)

    def test_d1_dislikes_swimming(self) -> None:
        v = three()
        v.p.put32(v.rec(0) + LIKES, SWIMMING)                  # liked before: no longer
        self.assertTrue(v.open(dive_rolls(diver=0, find=3, survive=True)))
        v.play(0)
        self.assertIn(SWIMMING, v.dislikes(0))
        self.assertNotIn(SWIMMING, v.likes(0))
        self.assertEqual((v.present(0), v.health(0)), (1, 100))

    def test_d2a_dies_with_a_grave(self) -> None:
        v = three()
        calls = fake_log(v)
        self.assertTrue(v.open(dive_rolls(diver=1, find=3, survive=False, sink="dies")))
        v.play(0)
        self.assertEqual(v.health(1), 0)                       # the game's own death: a body and a grave
        self.assertEqual(v.vanished, [])
        self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
        self.assertEqual(calls[-1][2].splitlines()[:2], ["  Event: Diving for Treasure", "  Choice: Swim deeper"])

    def test_d2b_disappears_no_grave(self) -> None:
        v = three()
        self.assertTrue(v.open(dive_rolls(diver=2, find=3, survive=False, sink="disappears")))
        v.play(0)
        self.assertEqual(v.present(2), 0)
        self.assertEqual(v.health(2), 100)                     # no body
        self.assertEqual(v.vanished, [(3, 2, "Disappeared in Diving for Treasure (lost at sea)")])

    def test_d2c_and_better_not_gains_capped(self) -> None:
        for answer, field, start, gain, want in ((0, HEALING, 50, 0, 60), (0, HEALING, 50, TOP, 70),
                                                 (0, HEALING, 95, TOP, 100), (1, PARENTING, 50, 0, 60),
                                                 (1, PARENTING, 50, TOP, 70), (1, PARENTING, 92, 5, 100)):
            with self.subTest(answer=answer, field=hex(field), start=start, gain=gain):
                v = three()
                v.p.put32(v.rec(0) + HEALING, 50)
                v.p.put32(v.rec(0) + PARENTING, 50)
                v.p.put32(v.rec(0) + field, start)
                kw = dict(heal=gain) if answer == 0 else dict(parent=gain)
                self.assertTrue(v.open(dive_rolls(diver=0, find=3, survive=False, sink="rescued", **kw)))
                v.play(answer)
                self.assertEqual(v.i32(0, field), want)
                other = PARENTING if field == HEALING else HEALING
                self.assertEqual(v.i32(0, other), 50)
                self.assertEqual((v.present(0), v.health(0)), (1, 100))


# ---- The pages, the log, the save (emulated) ----------------------------------------------------------------------

@NEEDS
class Pages(unittest.TestCase):
    CASES = {"A": dict(find=0), "B": dict(find=1), "C": dict(find=2), "D1": dict(find=3),
             "D2A": dict(find=3, survive=False, sink="dies"), "D2B": dict(find=3, survive=False, sink="disappears"),
             "D2C": dict(find=3, survive=False, sink="rescued"), "NOT": dict(find=0)}

    def test_the_effects_on_the_last_page_only_and_one_entry(self) -> None:
        for name, kw in self.CASES.items():
            with self.subTest(ending=name):
                v = three()
                calls = fake_log(v)
                before = v.snapshot()
                self.assertTrue(v.open(dive_rolls(diver=0, **kw)))
                steps = v.play(1 if name == "NOT" else 0)
                last = len(steps) - 2                           # the click that showed the last page
                pages = v.dv_state()[15 + ENDINGS.index(name)]
                self.assertGreaterEqual(pages, len(dt.pages_of(name)))   # each of the owner's popups a page or more
                self.assertEqual(len(steps), v.dv_state()[14] - 1 + pages + 1)   # OKs, the answer, OKs, the close
                for kind, state in steps[:last]:
                    self.assertEqual(state, before, kind)       # nothing before the ending's last page
                self.assertEqual(steps[-1][1], steps[last][1])  # nothing more at the close
                if name != "B":
                    self.assertNotEqual(steps[last][1], before)
                self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
                entry = calls[-1][2]
                self.assertEqual(entry.count("  Event: "), 1)
                self.assertEqual(entry.count("  Choice: "), 1)
                self.assertTrue(entry.startswith(f"  Event: Diving for Treasure\n  Choice: "
                                                 f"{LABELS[1 if name == 'NOT' else 0]}\n"))
                self.assertEqual(calls[-1][3], 1)

    def test_more_pages_than_one_where_the_owner_has_popups(self) -> None:
        v = three()
        self.assertTrue(v.open(dive_rolls(find=3, survive=False, sink="rescued")))
        s = v.dv_state()
        for k, name in enumerate(ENDINGS):
            self.assertGreaterEqual(s[15 + k], len(dt.pages_of(name)), name)

    def test_nothing_at_a_save_or_quit_before_the_last_page(self) -> None:
        v = three()
        calls = fake_log(v)
        before = v.snapshot()
        self.assertTrue(v.open(dive_rolls(diver=0, find=3, survive=False, sink="dies")))
        for _ in range(v.dv_state()[14] - 1):
            v.click(0)
        v.click(1)                                              # "Swim deeper": its first page only
        v.click(0)                                              # the sinking's page
        self.assertEqual(calls, [])                             # a save or a quit now: no effects and no entry
        self.assertEqual(v.snapshot(), before)
        # The game reloaded: a new draw; the left event never comes back.
        self.assertTrue(v.open(dive_rolls(diver=1, find=1)))
        self.assertEqual(v.snapshot(), before)
        v.play(0)
        self.assertEqual(v.health(0), 100)
        self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
        self.assertEqual(calls[-1][2].count("  Choice: "), 1)
        v.click(0)                                              # OK again after the close: nothing twice
        self.assertEqual([c[0] for c in calls].count("write"), 1)

    def test_the_words_as_shown(self) -> None:
        v = three()
        v.p.write(v.rec(0) + 0xDD4, b"Diver Dan\0")
        v.p.put32(v.rec(0) + 0xDC8, 0)                          # a man
        v.p.write(v.rec(2) + 0xDD4, b"Doc Holly\0")
        self.assertTrue(v.open(dive_rolls(diver=0, doctor=1, tech=0, food=TOP)))
        s = v.dv_state()
        self.assertEqual(s[1], 2)
        self.assertEqual(words(" ".join(v.dv_pages(0))), words(dt.fill("INTRO", "m", "Diver Dan")))
        for k, name in enumerate(ENDINGS):
            award = s[6] if name == "A" else (s[7] if name == "C" else 0)
            keys = [key for popup in dt.pages_of(name) for key in popup]
            expected = " ".join(dt.fill(key, "m", "Diver Dan", "Doc Holly", award) for key in keys)
            shown = v.dv_pages(1 + k)
            self.assertEqual(words(" ".join(shown)), words(expected), name)
            for page in shown:
                self.assertLessEqual(len(page), 1990)
        self.assertIn("Doc Holly, the head Doctor, says,", " ".join(v.dv_pages(1 + ENDINGS.index("D2C"))))
        self.assertIn("to be a gentle father to his spouse", " ".join(v.dv_pages(1 + ENDINGS.index("NOT"))))

    def test_the_popup_shows_the_pages_in_order(self) -> None:
        v = three()
        self.assertTrue(v.open(dive_rolls(diver=0, find=3, survive=False, sink="rescued")))
        intro = v.dv_pages(0)
        shown = [v.shown() or intro[-1]]                       # one page: the question the constructor set
        for _ in range(len(intro) - 1):
            v.click(0)
            shown.append(v.shown())
        self.assertEqual(shown[-1], intro[-1])
        v.click(1)
        result = v.dv_pages(1 + ENDINGS.index("D2C"))
        seen = [v.shown()]
        for _ in range(len(result) - 1):
            v.click(0)
            seen.append(v.shown())
        self.assertEqual(seen, result)
        v.ui.clear()
        v.click(0)
        self.assertTrue(v.closed())


# ---- The draw: each event its own entry (emulated) -------------------------------------------------------------------

@NEEDS
class TheDraw(unittest.TestCase):
    def test_one_event_the_adventurer_alone(self) -> None:
        v = Dive()
        v.adults(2, years=15)                                   # 14 or more, under 18: the Adventurer only
        self.assertEqual(v.dv_possible(), 0)
        entries, obj = v.list_draw(0)
        self.assertEqual(entries, 1)
        self.assertEqual(v.title_of(obj), "The Aspiring Adventurer")

    def test_two_events_two_entries_each_its_own(self) -> None:
        titles = []
        for coin in (0, 1):
            v = three()
            entries, obj = v.list_draw(coin)
            self.assertEqual(entries, 2)
            for k in range(entries):
                self.assertEqual(v.p.u32(v.list_esp + T["offset"] + 4 * k), 0)   # slot 0's entries
            titles.append(v.title_of(obj))
        self.assertEqual(titles, ["The Aspiring Adventurer", dt.TITLE])

    def test_three_events_three_entries_each_its_own(self) -> None:
        from test_troubling_signs import standard
        titles = []
        for coin in (0, 1, 2):
            v = standard()
            entries, obj = v.list_draw(coin)
            self.assertEqual(entries, 3)
            v.rolls = []
            v.p.call(v.p.u32(v.p.u32(obj) + 8), ecx=obj)
            entry = v.p.u32(T["strings"] + 4 * TITLE_ID)
            titles.append(v.p.cstring(v.p.u32(entry + 8), 400))
        self.assertEqual(titles, ["The Aspiring Adventurer", "The Troubling Signs", dt.TITLE])

    def test_each_event_as_likely_as_one_stock_event(self) -> None:
        """With `listed` stock events and n of ours, the list holds listed + n entries, one per event of ours; the
        object in slot 0 is each of ours 1 in n -- so each of ours is drawn 1 in (listed + n), as a stock event."""
        v = three()
        objects = [v.list_draw(c, listed=10)[1] for c in (0, 1)]
        self.assertEqual(len(set(objects)), 2)
        self.assertEqual(v.list_draw(0, listed=10)[0], 2)

    def test_never_past_the_list(self) -> None:
        """The list holds the stock slots + 1 entries (57 + 1): with 56 stock events listed there is room for two,
        with 57 for one -- the rest are left out, nothing written past the list."""
        from test_troubling_signs import standard
        for listed, room in ((55, 3), (56, 2), (57, 1)):
            with self.subTest(listed=listed):
                v = standard()
                p = v.p
                esp = STACK_TOP - 0x2000
                for k in range(listed, 64):
                    p.put32(esp + T["offset"] + 4 * k, 0xA5A5A5A5)
                v.rolls = [0]
                p.set_reg("esp", esp)
                p.set_reg("esi", 1)
                p.set_reg("edi", listed)
                p.run(*T["loop"])
                added = p.reg("edi") - listed
                self.assertEqual(added, min(3, room))
                for k in range(listed, listed + added):
                    self.assertEqual(p.u32(esp + T["offset"] + 4 * k), 0)
                for k in range(listed + added, 64):
                    self.assertEqual(p.u32(esp + T["offset"] + 4 * k), 0xA5A5A5A5)
                self.assertLessEqual(listed + added, 58)


if __name__ == "__main__":
    unittest.main()
