"""The Mysterious Mask: the owner's island event for The Tree of Life (2026-11-13), in "More Island Events".

Static (always run): the words are the owner's (src/vv_mysterious_mask.py, the companion's table generated from it, a
translation row for every piece), in letters the game's font draws; the odds are the owner's table.

EMULATED (unicorn, the stock The Tree of Life executable, the built "VVFP More Island Events.dll";
tests/story_emulator.py, the villagers in the game's own records as tests/test_aspiring_adventurer.py puts them):
  * who: a population of 61 or more (60 never; babies carried count), 2 children under 14 (1 never), 5 villagers of
    18 or more (4 never), everyone unprotected; the group 4 children when there are more, else all of them;
  * the four answers by mouse (the game's own click handler for its two, the shared multi-answer popup's for ours)
    and by key (1 to 4), each to its ending, with the walks' odds (A 50%, then C 25% / D 75%);
  * each of the elders' five speeches; the five volunteers always gone (no body), and every child of the group too
    when captured -- each told to Cause of Death, counted right;
  * the effects on the last page only; the Island Events log's one entry, nothing handed over before it;
  * the owner's words, exactly; the four buttons made, stacked and centred, and the pages laid out shorter;
  * the draw: its own entry beside The Aspiring Adventurer's and The Playful Dolphins'.

The game's own dialog constructor is stood in for by a few instructions that do what it does (the event, the measure
of the tallest page, ready); the button and label routines are stood in for.  The live game is NOT exercised here.
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

import vv_mysterious_mask as mm  # noqa: E402
from test_aspiring_adventurer import DLL, HAVE_EMULATOR, HAVE_STOCK, TABLES, TOP, Village  # noqa: E402
from test_more_island_events_pages import fake_log  # noqa: E402

try:
    from story_emulator import STACK_TOP  # noqa: E402
except ImportError:                       # pragma: no cover
    STACK_TOP = 0

NATIVE = ROOT / "native" / "vvfp_more_island_events"
OWNER_TEXT = ROOT / "tests" / "data" / "mysterious_mask_owner_text.txt"
LABELS = [dict(mm.TEXTS)["LABEL_" + a] for a in mm.ANSWERS]
ENDINGS = mm.ENDINGS
T = TABLES[4]
TITLE_ID = 0x35F
BUTTON_W, BUTTON_H = 401, 42
LINE = 20
PANEL = (144, 20, 656, 580)
DIALOG_VTABLE = 0x48D2C8
COMPOSE_LIMIT = 20_000_000                    # instructions for composing the event (measured: under 5,000,000)
# The stand-in constructor: the event at +0x50, the measure of the tallest page (+0x28(0)), ready (+0x4C).
CTOR = bytes.fromhex("56" "8BF1" "8B442408" "894650" "8BC8" "8B10" "6A00" "FF5228" "C6464C01" "8BC6" "5E" "C20400")
F_OF = {"WAIT": "F_WAITED", "CRY": "F_CRIED", "HOME": "F_BACK", "CAPTURED": "F_CAPTURED", "RESCUED": "F_RESCUED"}


def words(text: str) -> list[str]:
    return re.sub(r"\s+", " ", text).strip().split(" ")


def what_happened(ending: str) -> str:
    return ending if ending in ("WAIT", "CRY") else ending.split("_")[1]


class Mask(Village):
    """The Tree of Life with a village for The Mysterious Mask and its popup driven through the dialog."""

    def __init__(self):
        super().__init__(4)
        p = self.p
        self.buttons: dict[int, int] = {}
        self.labels: dict[int, str] = {}
        self.deleted: list[int] = []
        self.measured: list[str] = []
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
        p.stub(0x44CCF0, lambda pr: (0x7777, 0))                         # the image manager
        p.stub(0x470C5C, lambda pr: (p.alloc(0x40), 0))                  # operator new
        p.stub(0x44CB60, lambda pr: (0x5555, 4))                         # the picture
        p.stub(0x401C20, self._button)
        p.stub(0x401600, self._label)
        p.stub(0x408130, lambda pr: (0x6666, 0))                         # the draw holder
        p.stub(0x409C30, self._measure)
        p.write(T["ctor"], CTOR)
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
    def build(self, children: int = 4, adults: int = 57, child_years: int = 8, adult_years: int = 30) -> None:
        for k in range(children):
            self.villager(k, f"Kid{k}", k % 2 == 0, years=child_years)
        for k in range(adults):
            self.villager(children + k, f"A{k:02d}", k % 2 == 1, years=adult_years)

    def possible(self) -> int:
        return self.p.export("VvfpMysteriousMaskPossible")

    def mk_state(self) -> list[int]:
        out = self.p.alloc(28 * 4)
        self.p.export("VvfpMysteriousMaskState", out)
        return [struct.unpack("<i", self.p.read(out + 4 * k, 4))[0] for k in range(28)]

    def mk_pages(self, which: int) -> list[str]:
        out, k = [], 0
        while True:
            at = self.p.export("VvfpMysteriousMaskPage", which, k)
            if not at:
                return out
            out.append(self.p.cstring(at, 4000))
            k += 1

    # -- the draw and the popup ----------------------------------------------------------------------------------
    def list_draw(self, coin: int) -> tuple[int, int]:
        p = self.p
        self.rolls = [coin]
        p.set_reg("esp", STACK_TOP - 0x2000)
        p.set_reg("esi", 1)
        p.set_reg("edi", 0)
        p.run(*T["loop"])
        self.rolls = []
        return p.reg("edi"), p.u32(T["table"])

    def title_of(self, obj: int) -> str:
        """The title an event object gives (its +0x08, as the dialog asks it first: the event is composed here --
        nine sets of pages laid out, more instructions than the emulator's usual limit)."""
        self.p.call(self.p.u32(self.p.u32(obj) + 8), ecx=obj, limit=COMPOSE_LIMIT)
        entry = self.p.u32(T["strings"] + 4 * TITLE_ID)
        return self.p.cstring(self.p.u32(entry + 8), 400)

    def open(self, rolls: list[int], coin: int = 2) -> bool:
        """The Mysterious Mask drawn (`coin` its index among the events that can happen: 2 after the Adventurer and
        The Playful Dolphins) and its popup built through the game's presenter site."""
        p = self.p
        entries, obj = self.list_draw(coin)
        if not entries:
            return False
        self.ui.clear()
        self.rolls = list(rolls)
        if self.title_of(obj) != mm.TITLE:
            return False
        self.dlg = d = p.alloc(0x1000)
        p.put32(d, DIALOG_VTABLE)
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
        p.run(*T["site"])
        return True

    def click(self, ident: int) -> None:
        """A click on button `ident` (1 OK, 2..5 the answers top to bottom), through this dialog's click handler."""
        self.p.call(self.p.u32(self.p.u32(self.dlg) + 0x0C), [8, ident], ecx=self.dlg)

    def key(self, kind: int, code: int) -> int:
        return self.p.call(self.p.u32(self.p.u32(self.dlg) + 0x08), [kind, code, 0], ecx=self.dlg) & 0xFF

    def answer_ids(self) -> list[int]:
        shown: set[int] = set()
        for what, arg in [u for u in self.ui if u[0] in ("show", "hide")]:
            ident = next((i for i, b in self.buttons.items() if b == arg), None)
            if ident is not None and ident >= 2:
                (shown.add if what == "show" else shown.discard)(ident)
        return sorted(shown)

    def snapshot(self) -> tuple:
        return (self.stores(),) + tuple(self.present(i) for i in range(64))

    def play(self, answer: int, by_key: bool = False, calls: list | None = None) -> list[tuple]:
        """The whole event, answering `answer` (0..3): (what was clicked, the village after it, the log calls so far)."""
        calls = calls if calls is not None else []
        steps = []
        for _ in range(self.mk_state()[18] - 1):
            if by_key:
                self.key(6, 0x3EB)
            else:
                self.click(1)
            steps.append(("ok", self.snapshot(), len(calls)))
        if by_key:
            self.key(5, ord("1") + answer)
        else:
            self.click(2 + answer)
        steps.append(("answer", self.snapshot(), len(calls)))
        for _ in range(self.mk_state()[19 + self.mk_state()[15]] - 1):
            if by_key:
                self.key(6, 0x3EB)
            else:
                self.click(1)
            steps.append(("ok", self.snapshot(), len(calls)))
        self.ui.clear()
        self.click(1)
        steps.append(("close", self.snapshot(), len(calls)))
        return steps


def standard(children: int = 4, adults: int = 57) -> Mask:
    v = Mask()
    v.build(children, adults)
    return v


def mask_rolls(*, children: int = 4, adults: int = 57, home: bool = True, captured: bool = False,
               picks: list[int] | None = None) -> list[int]:
    """The rolls mk_begin draws: each child of the group among those left (none when one is left), each volunteer
    likewise, then a walk's home roll (rand(100) < 50) and the lost's captured roll (rand(100) < 25)."""
    group = min(4, children)
    out = list(picks) if picks is not None else (
        [0 for k in range(group) if children - k > 1] + [0 for k in range(5) if adults - k > 1])
    return out + [0 if home else 99, 0 if captured else 99]


ENDING_ROLLS = {"WAIT": (0, {}), "CRY": (1, {}),
                "CLEARING_HOME": (2, dict(home=True)), "CLEARING_CAPTURED": (2, dict(home=False, captured=True)),
                "CLEARING_RESCUED": (2, dict(home=False, captured=False)),
                "FOREST_HOME": (3, dict(home=True)), "FOREST_CAPTURED": (3, dict(home=False, captured=True)),
                "FOREST_RESCUED": (3, dict(home=False, captured=False))}

NEEDS = unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(),
                            "needs unicorn, pefile, the stock executables and the built DLL")


# ---- The words and the odds (no emulator) ---------------------------------------------------------------------------

class TheWords(unittest.TestCase):
    def test_every_piece_is_a_key_row_with_its_english(self) -> None:
        rows = {r["stem"]: r for r in json.loads((ROOT / "data" / "translations" / "patcher_strings.json")
                                                 .read_text(encoding="utf-8"))["strings"]}
        for stem, key, english, _ in mm.rows():
            with self.subTest(stem=stem):
                self.assertIn(stem, rows)
                self.assertEqual(rows[stem]["english"], english)
                self.assertEqual(rows[stem]["games"], ["vv4"])
                self.assertEqual(rows[stem]["route"], "key")

    def test_the_companions_table_is_generated_from_the_one_source(self) -> None:
        import build_more_island_events as builder
        self.assertEqual((NATIVE / "mask_text.inc").read_text(encoding="utf-8"), builder.mask_text_inc())

    def test_only_letters_the_games_font_draws(self) -> None:
        import vv_font_glyphs as glyphs
        missing = set(glyphs.missing("vv4", "ldwBurweed27"))
        for _, key, english, _ in mm.rows():
            self.assertFalse(set(english) & missing, key)
            self.assertTrue(all(32 <= ord(c) < 127 for c in english), key)

    def test_the_owners_wording(self) -> None:
        """Every shown line of the owner's text (curly quotes and apostrophes in the font's letters) is one of ours,
        exactly, for a boy and a girl as name1; the instructions are never shown; nothing of ours is extra."""
        owner = OWNER_TEXT.read_text(encoding="utf-8")
        owner = owner.replace(chr(0x201C), '"').replace(chr(0x201D), '"').replace(chr(0x2019), "'")
        title, body = owner.split("\n", 1)
        self.assertEqual(title.split(" --")[0], mm.TITLE + ".")
        for form, sub in (("f", {"(he/she)": "she", "(He/she)": "She", "(his/her)": "her", "(His/her)": "Her",
                                 "(him/her)": "her"}),
                          ("m", {"(he/she)": "he", "(He/she)": "He", "(his/her)": "his", "(His/her)": "His",
                                 "(him/her)": "him"})):
            with self.subTest(form=form):
                filled = {key: mm.fill(key, form, "Ana", "Ben") for key, _ in mm.TEXTS}
                ours = [" ".join(words(t)) for t in filled.values()]
                used = []
                for line in body.splitlines():
                    line = line.strip()
                    if not line or line.startswith("--"):
                        continue
                    if line.endswith(":") and line[:-1] in LABELS:
                        used.append(line[:-1])
                        continue
                    shown = line.replace("(name1)", "Ana").replace("(name2)", "Ben")
                    for k, v in sub.items():
                        shown = shown.replace(k, v)
                    self.assertNotIn("(", shown)
                    self.assertIn(" ".join(words(shown)), ours, line)          # each line is one piece, exactly
                    used.append(shown)
                for key, text in filled.items():
                    if key != "TITLE":
                        self.assertIn(" ".join(words(text)), [" ".join(words(u)) for u in used], key)

    def test_the_labels_fit_the_screen_whole(self) -> None:
        table = json.loads((ROOT / "data" / "cie_label_widths.json").read_text(encoding="utf-8"))["games"]["4"]
        for label in LABELS:
            width = sum(table["widths"][ord(c) - 32] + table["spacing"] for c in label)
            self.assertLessEqual(width, table["max_px"], label)


class TheOdds(unittest.TestCase):
    def test_the_owners_table(self) -> None:
        c = mm.outcome_chances()
        self.assertEqual(c["WAIT"], {"WAIT": 100.0})
        self.assertEqual(c["CRY"], {"CRY": 100.0})
        for walk in ("CLEARING", "FOREST"):
            self.assertEqual(c[walk], {f"{walk}_HOME": 50.0, f"{walk}_CAPTURED": 12.5, f"{walk}_RESCUED": 37.5})

    def test_the_companion_rolls_the_same_odds(self) -> None:
        core = (NATIVE / "mask_core.inc").read_text(encoding="utf-8")
        for needle in ("mk.home = adv_percent(t->g, 50);", "mk.captured = adv_percent(t->g, 25);",
                       "#define MK_POPULATION 61", "#define MK_GROUP_MAX 4", "#define MK_GROUP_MIN 2",
                       "#define MK_EXPEDITION 5", "#define MK_CHILD_UNITS 280", "#define MK_ADULT_UNITS 360",
                       "!adv_is_protected(t->g->game, r)", "t->g->eligible(r) && t->age(r) >= MK_ADULT_UNITS",
                       "#define MK_LINES_LESS 3"):
            self.assertIn(needle, core)

    def test_the_game_mechanics_entry(self) -> None:
        import vv_game_mechanics_events_vv4 as catalog
        event = next(e for e in catalog.EVENTS if e.title == mm.TITLE)
        self.assertEqual(event.only_with, "vv4_more_island_events")
        text = event.text + " " + " ".join(s if isinstance(s, str) else s.text for s in event.subs)
        for needle in ("61 or more", "babies", "under 14", "18 villager years or more", "2 to 4", "five volunteers",
                       "not nursing a baby", "not a body or a ghost", "wall clock", "50%", "25%", "75%", "12.5%",
                       "37.5%", "no graves", "every child of the group", "one entry", "keys 1 to 4"):
            self.assertIn(needle, text)


# ---- Who (emulated) --------------------------------------------------------------------------------------------------

@NEEDS
class Who(unittest.TestCase):
    def test_population_60_never_61_yes_babies_count(self) -> None:
        v = standard(4, 56)                                   # 60
        self.assertEqual(v.possible(), 0)
        v = standard(4, 57)                                   # 61
        self.assertEqual(v.possible(), 1)
        v = standard(4, 56)
        v.p.put32(v.rec(10) + 0x1C4C, 300)                    # an adult carrying one baby: 61 people (the adult
        v.p.put32(v.rec(10) + 0x1C50, 1)                      # is protected now, 55 others remain)
        self.assertEqual(v.possible(), 1)
        v.p.put32(v.rec(10) + 0x1C50, 0)                      # carrying none counted: 60
        self.assertEqual(v.possible(), 0)

    def test_one_child_never_two_yes(self) -> None:
        v = standard(1, 60)
        self.assertEqual(v.possible(), 0)
        v = standard(2, 59)
        self.assertEqual(v.possible(), 1)

    def test_four_adults_never_five_yes(self) -> None:
        v = Mask()
        v.build(4, 0)
        for k in range(4):
            v.villager(4 + k, f"A{k}", years=30)
        for k in range(53):
            v.villager(8 + k, f"T{k}", years=16)               # 14 to 17: neither a child nor of the expedition
        self.assertEqual(v.possible(), 0)
        v.villager(61, "Fifth", years=18)
        self.assertEqual(v.possible(), 1)

    def test_thirteen_is_a_child_fourteen_is_not(self) -> None:
        v = Mask()
        v.villager(0, "Kid", years=13)
        v.villager(1, "Teen", years=14)
        for k in range(59):
            v.villager(2 + k, f"A{k}", years=30)
        self.assertEqual(v.possible(), 0)                     # one child
        v.villager(1, "Kid2", years=13)
        self.assertEqual(v.possible(), 1)

    def test_any_child_under_14_no_lower_limit(self) -> None:
        """The owner: any child villager under 14, however young; babies still carried are not villagers (they only
        count toward the population)."""
        v = Mask()
        v.villager(0, "Newborn", years=0)
        v.villager(1, "Toddler", years=1)
        for k in range(59):
            v.villager(2 + k, f"A{k}", years=30)
        self.assertEqual(v.possible(), 1)
        self.assertTrue(v.open(mask_rolls(children=2, adults=59)))
        self.assertEqual(sorted(v.mk_state()[0:2]), [0, 1])

    def test_protected_never_picked(self) -> None:
        for what, kw, at in (("a body or ghost child", dict(special=(0x1CC7, 1, 1)), 1),
                             ("a nursing adult", dict(carrying=500), 6)):
            with self.subTest(what=what):
                v = standard(3, 59)                           # 62 records: 61 people with the body
                v.villager(at, "Bad", years=8 if at == 1 else 30, **kw)
                self.assertTrue(v.open(mask_rolls(children=2, adults=57, picks=[0, 0, 0, 0, 0, 0])))
                s = v.mk_state()
                self.assertNotIn(at, s[0:4] + s[5:10])

    def test_the_group_is_four_when_more_else_all(self) -> None:
        for children, size in ((2, 2), (3, 3), (4, 4), (7, 4)):
            with self.subTest(children=children):
                v = standard(children, 61 - children)
                self.assertTrue(v.open(mask_rolls(children=children, adults=61 - children)))
                s = v.mk_state()
                self.assertEqual(s[4], size)
                group = s[0:size]
                self.assertEqual(len(set(group)), size)
                self.assertTrue(all(0 <= g < children for g in group))
                self.assertEqual(s[size:4], [-1] * (4 - size))
                volunteers = s[5:10]
                self.assertEqual(len(set(volunteers)), 5)
                self.assertTrue(all(children <= a for a in volunteers))

    def test_any_child_may_find_it(self) -> None:
        seen = set()
        for k in range(4):
            v = standard(4, 57)
            self.assertTrue(v.open(mask_rolls(picks=[k, 0, 0, 0, 0, 0, 0, 0])))
            seen.add(v.mk_state()[0])
        self.assertEqual(seen, {0, 1, 2, 3})

    def test_its_own_entry_in_the_draw(self) -> None:
        titles = []
        for coin in (0, 1, 2):
            v = standard()
            entries, obj = v.list_draw(coin)
            self.assertEqual(entries, 3)                      # the Adventurer, The Playful Dolphins, The Mysterious Mask
            v.rolls = []
            titles.append(v.title_of(obj))
        self.assertEqual(titles, ["The Aspiring Adventurer", "The Playful Dolphins", mm.TITLE])
        v = standard(4, 56)                                   # 60 people: the other two only
        self.assertEqual(v.list_draw(0)[0], 2)


# ---- The answers, the endings, the effects (emulated) ------------------------------------------------------------

@NEEDS
class Answers(unittest.TestCase):
    def test_every_answer_by_mouse_and_by_key(self) -> None:
        for ending, (answer, kw) in ENDING_ROLLS.items():
            for by_key in (False, True):
                with self.subTest(ending=ending, by_key=by_key):
                    v = standard()
                    self.assertTrue(v.open(mask_rolls(**kw)))
                    v.play(answer, by_key=by_key)
                    s = v.mk_state()
                    self.assertEqual((s[13], s[14], ENDINGS[s[15]]), (1, answer, ending))
                    self.assertEqual(s[16], 1)
                    self.assertTrue(("close",) in v.ui)

    def test_the_walks_odds(self) -> None:
        """A walk: rand(100) < 50 home safe; lost: rand(100) < 25 captured -- the clearing and the forest alike."""
        for answer, walk in ((2, "CLEARING"), (3, "FOREST")):
            for home, captured, want in ((0, 0, "HOME"), (49, 0, "HOME"), (50, 0, "CAPTURED"), (50, 24, "CAPTURED"),
                                         (50, 25, "RESCUED"), (99, 99, "RESCUED")):
                with self.subTest(walk=walk, home=home, captured=captured):
                    v = standard()
                    self.assertTrue(v.open(mask_rolls()[:-2] + [home, captured]))
                    v.play(answer)
                    self.assertEqual(ENDINGS[v.mk_state()[15]], f"{walk}_{want}")

    def test_the_disappearances_counted_right(self) -> None:
        for ending, (answer, kw) in ENDING_ROLLS.items():
            for children in (2, 4):
                with self.subTest(ending=ending, children=children):
                    v = standard(children, 61 - children)
                    self.assertTrue(v.open(mask_rolls(children=children, adults=61 - children, **kw)))
                    s = v.mk_state()
                    group, volunteers = s[0:s[4]], s[5:10]
                    v.play(answer)
                    captured = ending.endswith("CAPTURED")
                    gone = volunteers + (group if captured else [])
                    self.assertEqual(v.mk_state()[17], len(gone))
                    self.assertEqual(sorted(i for _, i, _ in v.vanished), sorted(gone))
                    self.assertTrue(all(g == 4 for g, _, _ in v.vanished))
                    for i in range(61):
                        self.assertEqual(v.present(i), 0 if i in gone else 1, i)
                    for _, i, why in v.vanished:
                        self.assertEqual(why, "Disappeared in The Mysterious Mask ("
                                         + ("taken by masked strangers)" if i in group
                                            else "left on the elders' expedition)"))
                    stops = [c for c in v.calls if c[0] == "stop"]
                    self.assertEqual(len(stops), len(gone))      # the game's own removal, no body (no grave)

    def test_each_of_the_elders_speeches(self) -> None:
        for ending, (answer, kw) in ENDING_ROLLS.items():
            with self.subTest(ending=ending):
                v = standard()
                self.assertTrue(v.open(mask_rolls(**kw)))
                elders = " ".join(" ".join(words(p)) for p in v.mk_pages(1 + ENDINGS.index(ending)))
                mine = F_OF[what_happened(ending)]
                for key in F_OF.values():
                    text = " ".join(words(mm.fill(key, "m")))
                    if key == mine:
                        self.assertIn(text, elders)
                    else:
                        self.assertNotIn(text, elders)


# ---- The pages, the log, the save (emulated) ----------------------------------------------------------------------

@NEEDS
class Pages(unittest.TestCase):
    def test_the_effects_on_the_last_page_only_and_one_entry(self) -> None:
        for ending, (answer, kw) in ENDING_ROLLS.items():
            with self.subTest(ending=ending):
                v = standard()
                calls = fake_log(v)
                before = v.snapshot()
                self.assertTrue(v.open(mask_rolls(**kw)))
                steps = v.play(answer, calls=calls)
                last = len(steps) - 2
                pages = v.mk_state()[19 + ENDINGS.index(ending)]
                self.assertGreaterEqual(pages, 2)                       # the story, then the elders' page F
                self.assertEqual(len(steps), v.mk_state()[18] - 1 + pages + 1)
                for kind, state, logged in steps[:last]:
                    self.assertEqual(state, before, kind)               # nothing before the last page
                    self.assertEqual(logged, 0, kind)                   # nothing handed to the log
                self.assertNotEqual(steps[last][1], before)
                self.assertEqual(steps[-1][1], steps[last][1])
                self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
                entry = calls[-1][2]
                self.assertEqual(entry.count("  Event: "), 1)
                self.assertEqual(entry.count("  Choice: "), 1)
                self.assertTrue(entry.startswith(f"  Event: {mm.TITLE}\n  Choice: {LABELS[answer]}\n"))

    def test_nothing_at_a_save_or_quit_before_the_last_page(self) -> None:
        v = standard()
        calls = fake_log(v)
        before = v.snapshot()
        self.assertTrue(v.open(mask_rolls(home=False, captured=True)))
        for _ in range(v.mk_state()[18] - 1):
            v.click(1)
        v.click(4)                                                      # "Walk towards the clearing"
        pages = v.mk_state()[19 + ENDINGS.index("CLEARING_CAPTURED")]
        for _ in range(pages - 2):
            v.click(1)
        self.assertEqual(calls, [])                                     # a save or a quit now: nothing
        self.assertEqual(v.snapshot(), before)
        self.assertTrue(v.open(mask_rolls()))                           # reloaded: a new draw
        v.play(0)
        self.assertEqual([c[0] for c in calls], ["begin", "end", "write"])
        self.assertEqual(len(v.vanished), 5)                            # the new event's volunteers only
        v.click(1)                                                      # OK again after the close: nothing twice
        self.assertEqual([c[0] for c in calls].count("write"), 1)

    def test_the_words_as_shown(self) -> None:
        for woman in (False, True):
            for ending, (answer, kw) in ENDING_ROLLS.items():
                with self.subTest(woman=woman, ending=ending):
                    v = standard()
                    v.p.write(v.rec(0) + 0x1B9C, b"Pip Finder\0")
                    v.p.put32(v.rec(0) + 0x1B90, 1 if woman else 0)
                    v.p.write(v.rec(1) + 0x1B9C, b"Bo Second\0")
                    self.assertTrue(v.open(mask_rolls(**kw)))
                    form = "f" if woman else "m"
                    self.assertEqual(words(" ".join(v.mk_pages(0))), words(mm.fill("INTRO", form, "Pip Finder",
                                                                                   "Bo Second")))
                    expected = " ".join(mm.fill(k, form, "Pip Finder", "Bo Second")
                                        for popup in mm.paragraphs_of(ending) for para in popup for k in para)
                    shown = v.mk_pages(1 + ENDINGS.index(ending))
                    self.assertEqual(words(" ".join(shown)), words(expected))
                    for page in shown:
                        self.assertLessEqual(len(page), 1990)

    def test_the_popup_shows_the_pages_in_order(self) -> None:
        v = standard()
        self.assertTrue(v.open(mask_rolls(home=False)))
        intro = v.mk_pages(0)
        shown = [[u[1] for u in v.ui if u[0] == "text"][-1]]
        for _ in range(len(intro) - 1):
            v.click(1)
            shown.append([u[1] for u in v.ui if u[0] == "text"][-1])
        self.assertEqual(shown, intro)
        v.click(5)                                                      # "Walk towards the forest"
        result = v.mk_pages(1 + ENDINGS.index("FOREST_RESCUED"))
        seen = [[u[1] for u in v.ui if u[0] == "text"][-1]]
        for _ in range(len(result) - 1):
            v.click(1)
            seen.append([u[1] for u in v.ui if u[0] == "text"][-1])
        self.assertEqual(seen, result)


# ---- The four buttons (emulated) ---------------------------------------------------------------------------------

@NEEDS
class TheFourButtons(unittest.TestCase):
    def test_made_labelled_laid_out_and_deleted(self) -> None:
        v = standard()
        self.assertTrue(v.open(mask_rolls()))
        self.assertEqual(sorted(i for i in v.buttons if i >= 4), [4, 5])
        self.assertEqual([v.labels[4], v.labels[5]], LABELS[2:])
        width, height = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
        step = BUTTON_H + BUTTON_H // 2
        places = [(v.p.u32(v.buttons[i] + 0x20), v.p.u32(v.buttons[i] + 0x24)) for i in (2, 3, 4, 5)]
        for k, (x, y) in enumerate(places):
            self.assertEqual(x, (width - BUTTON_W) // 2)                 # centred
            self.assertEqual(y, height - 2 * BUTTON_H - (3 - k) * step)  # one above the other, 1.5 heights apart
        out = v.p.alloc(16)
        self.assertEqual(v.p.export("VvfpMoreIslandEventsAnswerButtons", out), 4)
        self.assertEqual([v.p.u32(out + 4 * k) for k in range(4)], [v.buttons[i] for i in (2, 3, 4, 5)])
        self.assertEqual(v.p.export("VvfpMoreIslandEventsButtonRoom", v.dlg), 3 * BUTTON_H)
        v.play(2)
        self.assertEqual(sorted(v.deleted), sorted([v.buttons[4], v.buttons[5]]))

    def test_shown_only_with_the_question(self) -> None:
        v = standard()
        self.assertTrue(v.open(mask_rolls()))
        intro = v.mk_state()[18]
        self.assertGreater(intro, 1)
        self.assertEqual(v.answer_ids(), [])                            # the opening's first page: OK only
        for _ in range(intro - 1):
            v.click(1)
        self.assertEqual(v.answer_ids(), [2, 3, 4, 5])                  # its last page: the four answers
        v.click(3)
        self.assertEqual(v.answer_ids(), [])

    def test_the_pages_are_laid_out_shorter(self) -> None:
        """Six lines shorter than a two-answer popup's 11 (3 for each answer past two), and the tallest page measured
        with the extra buttons' room: no taller than a two-answer popup."""
        v = standard()
        self.assertTrue(v.open(mask_rolls()))
        self.assertEqual(v.mk_state()[27], 11 - 3 * 2)
        padded = [m for m in v.measured if m.endswith("\n ")]
        self.assertTrue(padded)
        self.assertGreaterEqual(LINE * padded[-1].count("\n "), 3 * BUTTON_H)   # blank lines worth the room


if __name__ == "__main__":
    unittest.main()
