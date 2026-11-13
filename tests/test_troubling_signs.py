"""The Troubling Signs: the owner's island event for The Secret City (2026-11-13), in "More Island Events".

EMULATED (unicorn, the stock The Secret City executable, the built "VVFP More Island Events.dll"; tests/story_emulator.py,
the villagers in the game's own records as tests/test_aspiring_adventurer.py puts them):
  * who: a robed Tribal Chief, nine different villagers of 18 or more who are not protected (four advisors, five
    travellers), a population of 61 or more (babies being carried count), the tribe's name; else it never happens;
  * the selector: each event its own share of the draw (two entries when The Aspiring Adventurer can happen too);
  * the four answers by mouse (the game's own click handler for its two, this dialog's own for ours) and by keyboard;
  * the five travellers leave only as the decree's last page is shown, never the chief or an advisor; the award in
    The Secret City's scaled range; a loss never below 0;
  * the Island Events log's one entry ("VVFP Island Events.dll" stood in for), and nothing at a save or quit before the
    last page;
  * the owner's words, exactly; the four buttons' layout and their labels on the screen.

The game's own dialog constructor is stood in for by a few instructions that do what it does for this event (the
event, the measure of the tallest page, ready); the button and label routines are stood in for and record their
calls.  The live game is NOT exercised here.
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

import vv_troubling_signs as ts  # noqa: E402
from test_aspiring_adventurer import DLL, HAVE_EMULATOR, HAVE_STOCK, STOCK, TABLES, Village  # noqa: E402
from test_more_island_events_pages import fake_log  # noqa: E402

try:
    from story_emulator import STACK_TOP  # noqa: E402
except ImportError:                       # pragma: no cover
    STACK_TOP = 0

TOP = 99999
APP = 0x4B309C
TRIBE = 0x12ED4
BUTTON_W, BUTTON_H = 401, 42             # The Secret City's choice button picture (id 4), measured in the game's art
LINE = 20                                # the island-event font's line, as the game's paragraph measures it
PANEL = (144, 20, 656, 580)              # the dialog's rectangle (left, top, right, bottom)
GROUPS = ts.GROUPS
LABELS = {g: dict(ts.TEXTS)["LABEL_" + g] for g in GROUPS}
# The stand-in constructor: the event at +0x50, the measure of the tallest page (+0x28(0)), ready (+0x4C).
CTOR = bytes.fromhex("56" "8BF1" "8B442408" "894650" "8BC8" "8B10" "6A00" "FF5228" "C6464C01" "8BC6" "5E" "C20400")


class Signs(Village):
    """The Secret City with a village for The Troubling Signs and its popup driven through the dialog."""

    def __init__(self, tribe: str = "Kalahuna"):
        super().__init__(3)
        p = self.p
        self.buttons: dict[int, int] = {}            # id -> button
        self.labels: dict[int, str] = {}
        self.deleted: list[int] = []
        self.measured: list[str] = []
        self.app = p.alloc(0x13000)
        p.put32(APP, self.app)
        p.write(self.app + TRIBE, tribe.encode("latin-1") + b"\0")
        # The button class stood in for: its methods.
        code = p.alloc(64)
        p.write(code, b"\xC3" * 64)
        self.vt = p.alloc(32)
        for k, va in enumerate((code, code + 8, code + 16, code + 24, code + 32)):
            p.put32(self.vt + 4 * k, va)
        p.stub(code, lambda pr: (self.deleted.append(pr.reg("ecx")) or 0, 4))
        p.stub(code + 8, self._place)
        p.stub(code + 16, lambda pr: (0, 0))
        p.stub(code + 24, lambda pr: (BUTTON_W, 0))
        p.stub(code + 32, lambda pr: (BUTTON_H, 0))
        p.stub(0x42E9D0, lambda pr: (0x7777, 0))                         # the image manager
        p.stub(0x46EC93, lambda pr: (p.alloc(0x40), 0))                  # operator new
        p.stub(0x42E8A0, lambda pr: (0x5555, 4))                         # the picture
        p.stub(0x4019F0, self._button)
        p.stub(0x401620, self._label)
        p.stub(0x408940, lambda pr: (0x6666, 0))                         # the draw holder
        p.stub(0x40A0C0, self._measure)
        p.stub(0x436E60, lambda pr: (0, 12))                             # the food trophy's notice
        p.stub(0x412CD0, lambda pr: (0, 4))
        p.write(TABLES[3]["ctor"], CTOR)
        p.mu.ctl_flush_tb()

    # -- stand-ins ----------------------------------------------------------------------------------------------
    def _place(self, pr):
        pr.put32(pr.reg("ecx") + 0x20, pr.arg(0))
        pr.put32(pr.reg("ecx") + 0x24, pr.arg(1))
        return 0, 8

    def _button(self, pr):
        b = pr.reg("ecx")
        pr.put32(b, self.vt)
        self.buttons[pr.arg(0)] = b
        return b, 0x18

    def _label(self, pr):
        texts = [u[1] for u in self.ui if u[0] == "text"]
        ident = next((i for i, b in self.buttons.items() if b == pr.reg("ecx")), 0)
        self.labels[ident] = texts[-1] if texts else ""
        return 0, 0x14

    def _measure(self, pr):
        text = pr.cstring(pr.arg(0), 4000)
        self.measured.append(text)
        return LINE * (text.count("\n") + 1), 0x1C

    # -- the village ---------------------------------------------------------------------------------------------
    def chief(self, i: int = 0, name: str = "Ana", woman: bool = True, robed: bool = True) -> None:
        self.villager(i, name, woman, years=40, special=(0xE80, 1, 1))
        self.p.put32(self.rec(i) + 0xDF4, ts.CHIEF_ROBE_BODY if robed else 3)

    def village(self, others: int = 60, first: int = 1, years: int = 30) -> None:
        for k in range(others):
            self.villager(first + k, f"V{first + k:03d}", k % 2 == 1, years=years)

    def set_stores(self, food: int, tech: int) -> None:
        self.p.put32(self.t["food"], food)
        self.p.put32(self.t["tech"], tech)

    def possible(self) -> int:
        return self.p.export("VvfpTroublingSignsPossible")

    def ts_state(self) -> list[int]:
        out = self.p.alloc(27 * 4)
        self.p.export("VvfpTroublingSignsState", out)
        return [struct.unpack("<i", self.p.read(out + 4 * k, 4))[0] for k in range(27)]

    def ts_pages(self, which: int) -> list[str]:
        out, k = [], 0
        while True:
            at = self.p.export("VvfpTroublingSignsPage", which, k)
            if not at:
                return out
            out.append(self.p.cstring(at, 4000))
            k += 1

    # -- the draw and the popup ----------------------------------------------------------------------------------
    def list_draw(self, coin: int) -> tuple[int, int]:
        """The selector's loop with every stock slot empty: (entries added, the object in slot 0)."""
        p, t = self.p, self.t
        self.rolls = [coin]
        esp = STACK_TOP - 0x2000
        p.set_reg("esp", esp)
        p.set_reg("esi", 1)
        p.set_reg("edi", 0)
        p.run(*t["loop"])
        self.obj = p.u32(t["table"])
        return p.reg("edi"), self.obj

    def open(self, picks=None, awards=(0, 0, 0, 0)) -> bool:
        """The Troubling Signs drawn (the Adventurer's share lost to the coin) and its popup built."""
        p, t = self.p, self.t
        entries, obj = self.list_draw(1)
        if not entries:
            return False
        rolls = list(picks if picks is not None else [0] * 9)
        for a in awards:
            rolls += [a, 0]                       # the award's draw, then the game's own count's draw (0x45D460)
        self.rolls = rolls
        self.ui.clear()
        p.call(p.u32(p.u32(obj) + 8), ecx=obj)    # the title, as the constructor asks it first
        if self.ts_state()[0] < 0:
            return False
        self.dlg = d = p.alloc(0x1000)
        p.put32(d, 0x47F28C)
        p.write(d + 0x14, struct.pack("<4i", *PANEL))
        p.put32(d + 0x858, 0x1B0)
        for ident, field in ((2, 0x85C), (3, 0x860), (1, 0x864)):
            b = p.alloc(0x40)
            p.put32(b, self.vt)
            self.buttons[ident] = b
            p.put32(d + field, b)
        esp = STACK_TOP - 0x3000 - 4
        p.put32(esp, obj)
        p.set_reg("esp", esp)
        p.set_reg("ecx", d)
        p.run(*t["site"])
        return True

    def click(self, ident: int) -> None:
        """A click on button `ident` (1 OK, 2..5 the answers top to bottom), through this dialog's click handler."""
        self.p.call(self.p.u32(self.p.u32(self.dlg) + 0x0C), [8, ident], ecx=self.dlg)

    def key(self, kind: int, code: int) -> int:
        return self.p.call(self.p.u32(self.p.u32(self.dlg) + 0x08), [kind, code, 0], ecx=self.dlg) & 0xFF

    def answer_ids(self) -> list[int]:
        """The answers' buttons as shown now (the dialog's add-child / hide calls)."""
        shown: set[int] = set()
        for what, arg in [u for u in self.ui if u[0] in ("show", "hide")]:
            ident = next((i for i, b in self.buttons.items() if b == arg), None)
            if ident is not None and ident >= 2:
                (shown.add if what == "show" else shown.discard)(ident)
        return sorted(shown)

    def shown_text(self) -> str:
        texts = [u[1] for u in self.ui if u[0] == "text"]
        return texts[-1] if texts else ""

    def snapshot(self, records=range(0, 12)) -> tuple:
        return (self.stores(),) + tuple(self.present(i) for i in records)

    def play(self, group: int, by_key: bool = False) -> list[tuple]:
        """The whole event, answering `group` (0..3): (what was clicked, the village after it) for each click."""
        steps = []
        for _ in range(self.ts_state()[18] - 1):
            self.click(1)
            steps.append(("ok", self.snapshot()))
        self.ui.append(("mark", 0))
        if by_key:
            self.key(5, ord("1") + group)
        else:
            self.click(2 + group)
        steps.append(("answer", self.snapshot()))
        for _ in range(self.ts_state()[19 + group] - 1):
            if by_key:
                self.key(6, 0x3EB)
            else:
                self.click(1)
            steps.append(("ok", self.snapshot()))
        self.ui.clear()
        self.click(1)
        steps.append(("close", self.snapshot()))
        return steps


def standard(population: int = 61, **chief) -> Signs:
    v = Signs()
    v.chief(**chief)
    v.village(population - 1)
    v.set_stores(1000, 5000)
    return v


def words(text: str) -> list[str]:
    return re.sub(r"\s+", " ", text).strip().split(" ")


NEEDS = unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(),
                            "needs unicorn, pefile, the stock executables and the built DLL")


# ---- The words (no emulator) -------------------------------------------------------------------------------------

OWNER_TEXT = ROOT / "tests" / "data" / "troubling_signs_owner_text.txt"


class TheWords(unittest.TestCase):
    def test_every_piece_is_a_key_row_with_its_english(self) -> None:
        rows = {r["stem"]: r for r in json.loads((ROOT / "data" / "translations" / "patcher_strings.json")
                                                 .read_text(encoding="utf-8"))["strings"]}
        for stem, key, english, _ in ts.rows():
            with self.subTest(stem=stem):
                self.assertIn(stem, rows)
                self.assertEqual(rows[stem]["english"], english)
                self.assertEqual(rows[stem]["games"], ["vv3"])

    def test_the_companions_table_is_generated_from_the_one_source(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_more_island_events as builder
        self.assertEqual((ROOT / "native" / "vvfp_more_island_events" / "troubling_text.inc")
                         .read_text(encoding="utf-8"), builder.troubling_text_inc())

    def test_only_letters_the_games_font_draws(self) -> None:
        import vv_font_glyphs as glyphs
        missing = set(glyphs.missing("vv3", "ldwBurweed27"))
        for _, key, english, _ in ts.rows():
            self.assertFalse(set(english) & missing, key)
            self.assertTrue(all(32 <= ord(c) < 127 for c in english), key)

    def test_the_owners_wording(self) -> None:
        """Every shown line of the owner's text (the approved fixes applied; the curly quotes as the font's straight
        ones) is one of ours, exactly; the instructions in parentheses are never shown; nothing of ours is extra."""
        owner = OWNER_TEXT.read_text(encoding="utf-8")
        owner = owner.replace("“", '"').replace("”", '"').replace("’", "'")
        title, body = owner.split("\n", 1)
        self.assertEqual(title.split(" (")[0], ts.TITLE + ".")
        filled = {key: ts.fill(key, "f", "Ana", "Ben", "Kalahuna", 300) for key, _ in ts.TEXTS}
        ours = " ".join(" ".join(words(t)) for t in filled.values())
        used = set()
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("then") or (line.startswith("(") and not line.startswith("(Name)")):
                continue
            if line.endswith(":") and line[:-1] in LABELS.values():
                used.add(line[:-1])
                continue
            shown = (line.replace("(Name)", "Ana").replace("(name)", "Ana").replace("(he/she)", "she")
                     .replace("(his/her)", "her").replace("(random name)", "Ben").replace("(tribe name)", "Kalahuna")
                     .replace("(award)", "300"))
            self.assertNotIn("(", shown)
            self.assertIn(" ".join(words(shown)), ours, line)
            used.add(shown)
        joined = " ".join(" ".join(words(u)) for u in used)
        for key, text in filled.items():
            if key != "TITLE":
                self.assertIn(" ".join(words(text)), joined, key)

    def test_the_labels_fit_the_screen_whole(self) -> None:
        table = json.loads((ROOT / "data" / "cie_label_widths.json").read_text(encoding="utf-8"))["games"]["3"]
        for group, label in LABELS.items():
            width = sum(table["widths"][ord(c) - 32] + table["spacing"] for c in label)
            self.assertLessEqual(width, table["max_px"], label)
            self.assertGreater(width, 0)


# ---- Who (emulated) ----------------------------------------------------------------------------------------------

@NEEDS
class Who(unittest.TestCase):
    def test_possible_with_everything(self) -> None:
        v = standard()
        self.assertEqual(v.possible(), 1)
        self.assertEqual(v.ts_state()[25], 61)

    def test_no_chief_or_no_robe_never(self) -> None:
        v = Signs()
        v.village(70)
        self.assertEqual(v.possible(), 0)
        v = standard(robed=False)
        self.assertEqual(v.possible(), 0)
        entries, _ = v.list_draw(1)
        self.assertEqual(entries, 2)                       # the Adventurer and Diving for Treasure only

    def test_population_60_never_61_yes_babies_count(self) -> None:
        v = standard(population=60)
        self.assertEqual(v.possible(), 0)
        v.villager(60, "Mum", True, years=30, carrying=1)   # one more villager (and her baby)
        self.assertEqual(v.possible(), 1)
        v = standard(population=60)
        v.p.put32(v.rec(5) + 0xE8C, 100)                    # carrying one: the population is 61
        v.p.put32(v.rec(5) + 0xE90, 1)
        self.assertEqual(v.possible(), 1)

    def test_nine_unprotected_others_needed(self) -> None:
        v = Signs()
        v.chief()
        v.village(8, first=1)                               # eight who may be picked
        for k in range(9, 61):
            v.villager(k, f"C{k}", years=17)                # too young: the population only
        self.assertEqual(v.possible(), 0)
        v.villager(9, "Nine", years=18)
        self.assertEqual(v.possible(), 1)
        for off, size, value in ((0xE8C, 4, 50), (0xE94, 1, 1), (0xE80, 1, 1)):
            with self.subTest(off=hex(off)):
                v.p.write(v.rec(9) + off, value.to_bytes(size, "little"))
                self.assertEqual(v.possible(), 0)
                v.p.write(v.rec(9) + off, (0).to_bytes(size, "little"))
                self.assertEqual(v.possible(), 1)

    def test_no_tribe_name_never(self) -> None:
        v = standard()
        v.p.write(v.app + TRIBE, b"\0")
        self.assertEqual(v.possible(), 0)


# ---- The draw ------------------------------------------------------------------------------------------------------

@NEEDS
class TheDraw(unittest.TestCase):
    def test_each_its_own_share(self) -> None:
        v = standard()
        entries, first = v.list_draw(0)
        self.assertEqual(entries, 3)                         # with the Adventurer and Diving for Treasure: three
        entries, second = v.list_draw(1)                     # entries for slot 0 (tests/test_diving_for_treasure.py)
        self.assertEqual(entries, 3)
        self.assertNotEqual(first, second)                   # the draw puts any event's object in the slot
        v = Signs()
        v.chief()
        v.village(1)                                        # the Adventurer cannot happen (one who may go)
        self.assertEqual(v.list_draw(0)[0], 0)


# ---- The pages, the answers, the effects ---------------------------------------------------------------------------

@NEEDS
class Answers(unittest.TestCase):
    def test_nine_different_never_the_chief_never_protected(self) -> None:
        v = standard()
        v.villager(3, "Mum", True, years=30, carrying=40)        # protected: carrying
        v.villager(4, "Look", years=30, special=(0xE94, 1, 1))   # protected: a look-alike
        v.villager(6, "Kid", years=17)
        for k in range(61, 70):
            v.villager(k, f"E{k}", years=60)
            for off in (0xEAC, 0xEB0, 0xEB4):
                v.p.put32(v.rec(k) + off, 95)               # Esteemed Elders: fair game
        seen = set()
        for picks in ([0] * 9, [TOP] * 9, [5, 3, 0, 7, 1, 2, 9, 4, 6]):
            with self.subTest(picks=picks):
                self.assertTrue(v.open(picks))
                s = v.ts_state()
                nine = s[2:11]
                self.assertEqual(s[0], 0)
                self.assertEqual(len(set(nine)), 9)
                self.assertNotIn(0, nine)
                for bad in (3, 4, 6):
                    self.assertNotIn(bad, nine)
                seen |= set(nine)
        self.assertTrue(seen & set(range(61, 70)))           # an elder was picked

    def test_every_answer_by_mouse_and_by_key(self) -> None:
        for by_key in (False, True):
            for g, group in enumerate(GROUPS):
                with self.subTest(group=group, by_key=by_key):
                    v = standard()
                    self.assertTrue(v.open())
                    v.play(g, by_key)
                    s = v.ts_state()
                    self.assertEqual((s[15], s[16], s[17]), (1, g, 1))

    def test_the_effects_on_the_last_page_only(self) -> None:
        for g, group in enumerate(GROUPS):
            with self.subTest(group=group):
                v = standard()
                calls = fake_log(v)
                self.assertTrue(v.open(awards=(TOP, TOP, TOP, TOP)))
                s = v.ts_state()
                travellers, advisors = s[6:11], s[2:6]
                before = v.snapshot(range(0, 61))
                steps = []
                for _ in range(s[18] - 1):
                    v.click(1)
                    steps.append(v.snapshot(range(0, 61)))
                v.click(2 + g)
                steps.append(v.snapshot(range(0, 61)))
                pages = s[19 + g]
                self.assertGreaterEqual(pages, 3)            # the advice, "Hear me", the decree
                for _ in range(pages - 1):
                    v.click(1)
                    steps.append(v.snapshot(range(0, 61)))
                for state in steps[:-1]:
                    self.assertEqual(state, before)          # nothing before the decree's last page
                after = steps[-1]
                for i in range(61):
                    self.assertEqual(after[1 + i], 0 if i in travellers else 1, i)
                for i in advisors + [0]:
                    self.assertEqual(v.present(i), 1)        # the chief and the advisors stay
                self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
                self.assertEqual(calls[-1][2].splitlines()[:2],
                                 ["  Event: The Troubling Signs", f"  Choice: {LABELS[group]}"])
                v.ui.clear()
                v.click(1)
                self.assertIn(("close",), v.ui)
                self.assertEqual(v.snapshot(range(0, 61)), after)
                self.assertEqual(len(v.vanished), 5)
                self.assertTrue(all(w[2].startswith("Disappeared in The Troubling Signs") for w in v.vanished))

    def test_awards_in_the_scaled_range_and_losses_floored(self) -> None:
        lows = standard()
        self.assertTrue(lows.open(awards=(0, 0, 0, 0)))
        low = lows.ts_state()[11:15]
        m = low[1] // 1000                                   # the game's own factor: 1,000 tech at the bottom
        self.assertGreaterEqual(m, 1)
        self.assertEqual(low, [200 * m, 1000 * m, 200 * m, 1000 * m])
        highs = standard()
        highs.set_stores(100000, 100000)                      # a loss is never more than what is stored
        self.assertTrue(highs.open(awards=(TOP, TOP, TOP, TOP)))
        self.assertEqual(highs.ts_state()[11:15], [600 * m, 2000 * m, 600 * m, 2000 * m])
        # Each answer's store change.
        expect = {0: (-1, 0), 1: (0, +1), 2: (+1, 0), 3: (0, -1)}
        for g in range(4):
            v = standard()
            v.set_stores(1000, 50000)
            self.assertTrue(v.open(awards=(TOP, TOP, TOP, TOP)))
            food, tech = v.stores()
            v.play(g)
            amount = v.ts_state()[11 + g]
            df, dt = expect[g]
            self.assertEqual(v.stores(), (food + df * amount, tech + dt * amount), g)
        # A loss never below 0: what is stored is what is taken, and the page says so.
        for g, stores in ((0, (150, 5000)), (3, (1000, 700))):
            v = standard()
            v.set_stores(*stores)
            self.assertTrue(v.open(awards=(TOP, TOP, TOP, TOP)))
            self.assertEqual(v.ts_state()[11 + g], stores[0] if g == 0 else stores[1])
            v.play(g)
            self.assertEqual(v.stores()[0 if g == 0 else 1], 0)
            self.assertIn(f"loses {stores[0] if g == 0 else stores[1]} ", " ".join(v.ts_pages(1 + g)))

    def test_one_entry_and_nothing_at_a_save_before_the_last_page(self) -> None:
        v = standard()
        calls = fake_log(v)
        before = v.snapshot(range(0, 61))
        self.assertTrue(v.open())
        for _ in range(v.ts_state()[18] - 1):
            v.click(1)
        v.click(3)                                           # the magicians: their first page only
        v.click(1)                                           # "Hear me"
        self.assertEqual(calls, [])                          # a save or a quit now: no effects and no entry
        self.assertEqual(v.snapshot(range(0, 61)), before)
        self.assertEqual(v.p.export("VvfpMoreIslandEventsLogged", 3, 0), 1)
        # The game reloaded: a new draw, the left event never comes back.
        self.assertTrue(v.open())
        self.assertEqual(v.snapshot(range(0, 61)), before)
        v.play(2)
        self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
        self.assertEqual(calls[-1][2].count("  Choice: "), 1)
        self.assertIn(f"  Choice: {LABELS['NATURALISTS']}", calls[-1][2])
        self.assertEqual(calls[-1][3], 1)

    def test_the_words_as_shown(self) -> None:
        v = standard()
        v.p.write(v.rec(0) + 0xDD4, b"Chiefy Rex\0")
        v.p.put32(v.rec(0) + 0xDC8, 0)                       # a man
        self.assertTrue(v.open())
        s = v.ts_state()
        name = lambda i: v.p.cstring(v.rec(i) + 0xDD4)  # noqa: E731
        intro = " ".join(v.ts_pages(0))
        self.assertEqual(words(intro), words(ts.fill("INTRO_1", "m", "Chiefy Rex") + " "
                                             + ts.fill("INTRO_2", "m", "Chiefy Rex")))
        for g, group in enumerate(GROUPS):
            shown = " ".join(v.ts_pages(1 + g))
            keys = [k for page in ts.pages_of(group) for k in page]
            expected = " ".join(ts.fill(k, "m", "Chiefy Rex", name(s[2 + g]), "Kalahuna", s[11 + g]) for k in keys)
            self.assertEqual(words(shown), words(expected), group)
            for page in v.ts_pages(1 + g):
                self.assertLessEqual(len(page), 1990)
        self.assertIn("Hear me, O Kalahuna! Your Chief speaks!", " ".join(v.ts_pages(1)))


# ---- The four buttons ----------------------------------------------------------------------------------------------

@NEEDS
class TheFourButtons(unittest.TestCase):
    def test_made_labelled_laid_out_and_deleted(self) -> None:
        v = standard()
        self.assertTrue(v.open())
        self.assertEqual(sorted(i for i in v.buttons if i >= 4), [4, 5])
        self.assertEqual((v.labels[4], v.labels[5]), (LABELS["NATURALISTS"], LABELS["SCIENTISTS"]))
        out = v.p.alloc(16)
        self.assertEqual(v.p.export("VvfpTroublingSignsButtons", out), 4)
        order = [v.p.u32(out + 4 * k) for k in range(4)]
        self.assertEqual(order, [v.buttons[2], v.buttons[3], v.buttons[4], v.buttons[5]])
        width, height = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
        ys = []
        for b in order:
            x, y = struct.unpack("<2i", v.p.read(b + 0x20, 8))
            self.assertEqual(x, (width - BUTTON_W) // 2)    # centred: a wider label is centred too
            ys.append(y)
        self.assertEqual(ys, [height - 2 * BUTTON_H - k * (BUTTON_H + BUTTON_H // 2) for k in (3, 2, 1, 0)])
        self.assertTrue(all(b - a >= BUTTON_H for a, b in zip(ys, ys[1:])))   # never overlapping
        self.assertGreaterEqual(ys[0], 0)
        self.assertLessEqual(ys[-1] + BUTTON_H, height)

    def test_room_for_them_above_the_text(self) -> None:
        v = standard()
        self.assertTrue(v.open())
        room = v.ts_state()[26]
        self.assertEqual(room, 3 * BUTTON_H)
        self.assertEqual(v.p.export("VvfpMoreIslandEventsButtonRoom", v.dlg), room)
        self.assertEqual(v.p.export("VvfpMoreIslandEventsButtonRoom", v.dlg + 8), 0)
        sized = v.measured[-1]                                # the tallest page as the constructor measured it
        self.assertGreaterEqual(LINE * (sized.count("\n") + 1) - LINE * (sized.rstrip("\n ").count("\n") + 1), room)

    def test_shown_and_hidden_with_the_pages(self) -> None:
        v = standard()
        self.assertTrue(v.open())
        if v.ts_state()[18] > 1:
            self.assertEqual(v.answer_ids(), [])
            for _ in range(v.ts_state()[18] - 1):
                v.click(1)
        self.assertTrue({4, 5} <= set(v.answer_ids()))           # (the game's two were shown by its constructor)
        self.assertEqual(v.key(6, 0x3EB), 0)                       # Enter takes no answer
        v.click(5)
        self.assertNotIn(4, v.answer_ids())
        self.assertNotIn(5, v.answer_ids())
        v.click(1)
        self.assertIn(v.buttons[4], v.deleted)
        self.assertIn(v.buttons[5], v.deleted)


if __name__ == "__main__":
    unittest.main()
