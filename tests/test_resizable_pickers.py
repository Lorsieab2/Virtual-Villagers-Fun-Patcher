"""v1.35.80: the companions' own windows are resizable, nothing in them is cut
off, the Gong of Wonder picker lists all 23 results, and villager lists sort.

The owner: "make sure all these windows are expandable (max/minimizable)
and make sure all the gong of wonder options are clearly in the list";
"I like the format of the 'Pick Island Events' better. Use that for the
Gong of Wonder outcome picker"; and every villager list in the Upgrades
menus gets "Age (oldest at top)" and "Alphabetical (first name, then last
name)".

* Every dialog template of every companion DLL that makes dialogs carries a
  sizing frame and minimise / maximise boxes, and every dialog procedure
  calls the kit's hook (native/shared/vvfp_dialog_kit.h) first.
* The kit on real Windows controls (scripts/build_dialog_kit_harness.ps1):
  each shipped dialog created hidden, its smallest size the template's,
  laid out at the template's size, half as large again and maximised with
  every control inside and nothing overlapping; wrapping lists; sorting.
* The Gong picker's logic in the emulator (the test build): its left list
  is Random, then the tiers A, B and C with all 23 results in the game's own
  words; each result lists only its own settings; the "still random"
  warning; OK keeps only the chosen result's settings; and the whole
  purchase -- the picker answered as a player would, the confirmation, the
  Gong made ready -- followed by a ring that takes the chosen branch.
* Every description and note the Pick Island Event / Gong picker can show
  fits its box at the window's smallest size (measured with the dialog's own
  font, as Windows lays the dialog out).
* The sort orders: names word by word, case-insensitive, numerals in order
  (Kenobi I, II, III ...), oldest first with ties by name.
"""
from __future__ import annotations

import ctypes
import os
import re
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_story_outcomes as so  # noqa: E402
from story_outcome_tables import plain  # noqa: E402

NATIVE = ROOT / "native"
VS_CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231"
             r"\bin\Hostx64\x86\cl.exe")

# The companions that make dialogs of their own, and the DLLs built from them.
DIALOG_SOURCES = {
    "vvfp_story_upgrades": ["vvfp_story_upgrades.rc"],
    "vv1_origins_icons": ["vv1_origins_icons.rc"],
    "vv2_origins_icons": ["vv2_origins_icons.rc"],
    "vv4_origins_icons": ["vv4_origins_icons.rc"],
    "vv3_full_mastery_candidate": ["vv3_full_mastery_candidate.rc"],   # VV3 Safe Upgrades
    "vv5_task9_origins": ["vv5_task9_origins.rc"],                     # VV5 (and VV4 Expanded)
}
SHIPPED_DLLS = [
    ROOT / "assets" / "story_upgrades" / "VVFP Story Upgrades.dll",
    ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll",
    ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll",
    ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll",
    ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll",
    ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll",
]
FRAME = ("WS_THICKFRAME", "WS_MINIMIZEBOX", "WS_MAXIMIZEBOX")

SCRATCH = so.SCRATCH
GONG = 2


def _dialog_styles(text: str) -> list[tuple[str, str]]:
    found = []
    for m in re.finditer(r"^(\d+)\s+DIALOGEX[^\n]*\n\s*STYLE\s+([^\n]+)", text, re.M):
        found.append((m.group(1), m.group(2)))
    return found


class TemplatesAndProcedures(unittest.TestCase):
    def test_every_dialog_template_has_a_sizing_frame_and_both_boxes(self):
        for folder, files in DIALOG_SOURCES.items():
            for name in files:
                text = (NATIVE / folder / name).read_text(encoding="latin-1")
                styles = _dialog_styles(text)
                self.assertTrue(styles, name)
                for dialog, style in styles:
                    with self.subTest(file=name, dialog=dialog):
                        for flag in FRAME:
                            self.assertIn(flag, style)

    def test_every_dialog_procedure_calls_the_kit_first(self):
        proc = re.compile(r"static INT_PTR CALLBACK (\w+)\((?P<sig>[^);]*)\) \{\n(?P<body>(?:.*\n){1,4})")
        for folder in DIALOG_SOURCES:
            for path in sorted((NATIVE / folder).glob("*.[ci]*")):
                if path.suffix not in (".c", ".inc") or "harness" in path.name:
                    continue
                text = path.read_text(encoding="latin-1").replace("\r\n", "\n")
                for m in proc.finditer(text):
                    with self.subTest(file=path.name, procedure=m.group(1)):
                        self.assertIn("vk_dialog_hook(", m.group("body"))


@unittest.skipUnless(os.name == "nt" and VS_CL.is_file(), "needs Windows and the Visual Studio x86 compiler")
class RealWindows(unittest.TestCase):
    """Each shipped dialog for real, hidden, and the kit's lists."""

    def test_every_shipped_dialog_resizes_and_nothing_is_cut_off(self):
        dlls = [str(p) for p in SHIPPED_DLLS if p.is_file()]
        self.assertEqual(len(dlls), len(SHIPPED_DLLS))
        run = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(ROOT / "scripts" / "build_dialog_kit_harness.ps1"), *dlls],
            capture_output=True, text=True, timeout=600)
        out = run.stdout + run.stderr
        self.assertEqual(run.returncode, 0, out)
        self.assertNotIn("FAIL", out)
        total = re.search(r"dialogs (\d+), failures 0", out)
        self.assertIsNotNone(total, out)
        # 11 Story Upgrades dialogs, and the five Origins menus' own
        self.assertGreaterEqual(int(total.group(1)), 11 + 3 * 4 + 2 * 4, out)


def _cstr(proc, va):
    return proc.read(va, 1400).split(b"\0", 1)[0].decode("cp1252")


@so.emulated
class GongPickerLogic(unittest.TestCase):
    def setUp(self):
        if not so.have_stock("vv2"):
            self.skipTest("stock executables not present")
        self.g, n = so.ChooserTests._open(None, "vv2", gong=True)
        self.assertEqual(n, 1)
        self.p = self.g.proc
        self.controls = so.controls_of("vv2", so.GONG_SLOT)
        self.ids = {c["id"]: i for i, c in enumerate(self.controls)}

    def entries(self):
        out = []
        k = 0
        while self.p.export("VvfpStoryProbeGongEntry", k, SCRATCH + 0x3000, 1200, SCRATCH + 0x3800):
            data = struct.unpack("<i", self.p.read(SCRATCH + 0x3800, 4))[0]
            out.append((_cstr(self.p, SCRATCH + 0x3000), data))
            k += 1
        return out

    def test_the_list_holds_random_then_all_23_results_by_tier_in_the_games_words(self):
        entries = self.entries()
        options = [plain(o["label"]) or o["label"] for o in self.controls[0]["options"]]
        self.assertEqual(len(options), 23)
        self.assertEqual(entries[0], ("Random (original game)", -1))
        headings = [i for i, (_, data) in enumerate(entries) if data == -100]
        self.assertEqual(headings, [1, 8, 18], "Tier A, then 6 results, Tier B, 9, Tier C, 8")
        self.assertTrue(entries[1][0].startswith("Tier A"))
        self.assertTrue(entries[8][0].startswith("Tier B"))
        self.assertTrue(entries[18][0].startswith("Tier C"))
        results = [(text, data) for text, data in entries if data >= 0]
        self.assertEqual([d for _, d in results], list(range(23)), "every result once, in order")
        self.assertEqual([t for t, _ in results], options, "the game's own wording")
        self.assertEqual(len(entries), 1 + 3 + 23)

    # Each result's own settings (scripts/story_outcomes_gong.py): the amounts
    # of its tier, who falls sick, the skill, the babies, the ringer.
    RESULT_SETTINGS = {
        "Grants technology: +20000": ["tech_big"], "Grants technology: +10000": ["tech_medium"],
        "Grants technology: +3000": ["tech_small"], "Takes technology": ["tech_lost"],
        "Grants food: +1000..2999": ["food_big"], "Grants food: +200..999": ["food_small"],
        "may fall sick (30%": ["sick_b"], "may fall sick (15%": ["sick_c"],
        "Grants wisdom": ["skill", "ringer"], "Grants life": ["babies"], "Takes life": ["ringer"],
        "loses 90 health": ["ringer"], "Takes youth": ["ringer"], "Grants youth": ["ringer"],
    }

    def rows(self, result):
        n = self.p.export("VvfpStoryProbeGongRows", result & 0xFFFFFFFF, SCRATCH + 0x3000)
        return list(struct.unpack(f"<{n}i", self.p.read(SCRATCH + 0x3000, 4 * n))) if n else []

    def test_each_result_lists_only_its_own_settings_and_random_lists_them_all(self):
        self.assertEqual(self.rows(-1), list(range(1, 12)), "Random: every setting but the result")
        for k, o in enumerate(self.controls[0]["options"]):
            want = []
            for key, ids in self.RESULT_SETTINGS.items():
                if key in o["label"]:
                    want = sorted(self.ids[i] for i in ids)
            with self.subTest(result=o["label"]):
                self.assertEqual(self.rows(k), want)
        self.assertNotIn(0, self.rows(-1), "the result itself is the list on the left, never scrolled away")

    def _set(self, ci, value):
        self.p.write(SCRATCH + 0x4000, struct.pack("<i", 0))
        self.p.export("VvfpStoryProbeChooserSet", 0, ci, value & 0xFFFFFFFF, SCRATCH + 0x4000, 0)

    def test_a_setting_with_the_result_left_random_says_the_effect_is_still_random(self):
        self.assertEqual(self.p.export("VvfpStoryProbeGongWarning", 0), 0, "nothing set")
        self._set(self.ids["ringer"], 3)
        self.assertEqual(self.p.export("VvfpStoryProbeGongWarning", 0), 1, "only the ringer: still random")
        self._set(0, so._option("Grants wisdom"))
        self.assertEqual(self.p.export("VvfpStoryProbeGongWarning", 0), 0)

    def test_ok_keeps_only_the_chosen_results_own_settings(self):
        self._set(self.ids["ringer"], 3)
        self._set(self.ids["tech_big"], 5)
        self._set(0, so._option("Grants luck"))
        self.p.export("VvfpStoryProbeGongWarning", 1)
        self.p.export("VvfpStoryProbeChooserFields", SCRATCH + 0x5000)
        choices = struct.unpack("<I", self.p.read(SCRATCH + 0x5000, 4))[0]
        values = struct.unpack("<12i", self.p.read(choices, 48))
        self.assertEqual(values[0], so._option("Grants luck"))
        self.assertEqual(values[1:], (-1,) * 11, "luck has no settings: the others go back to Random")
        self._set(self.ids["ringer"], 3)
        self._set(self.ids["skill"], 2)
        self._set(0, so._option("Grants wisdom"))
        self.p.export("VvfpStoryProbeGongWarning", 1)
        values = struct.unpack("<12i", self.p.read(choices, 48))
        self.assertEqual(values[self.ids["ringer"]], 3)
        self.assertEqual(values[self.ids["skill"]], 2)


@so.emulated
class GongPurchaseEndToEnd(unittest.TestCase):
    """The owner's report (v1.35.80 preview): "When I ring the Gong it gives a
    random effect" -- with "What the Gong does" left on Random, as designed.
    Here the whole way: the purchase opens the picker (answered as the
    player would: a result chosen, OK), the confirmation, the charge, the
    Gong made ready, and a ring by the action's own completion takes the
    chosen branch; with only the ringer chosen the confirmation says the
    effect is still random and the ring is the game's own roll."""

    def setUp(self):
        if not so.have_stock("vv2"):
            self.skipTest("stock executables not present")

    def _buy(self, choices: dict[int, int]):
        r = so._Ring()
        p = r.g.proc
        p.put32(r.w + 0x2EAC8, so.GONG_NOW + 40000)          # resting: rung a few hours ago
        p.put32(r.w + 0x2EADC, 100000)                        # tech points
        p.export("VvfpStoryCharge", 2)
        p.export("VvfpStoryProbeChooserFields", SCRATCH + 0x6000)
        choice_va, chosen_va = struct.unpack("<2I", p.read(SCRATCH + 0x6000, 8))

        def picker(q):
            # the player's clicks: the chooser has filled itself (Random everywhere)
            for ci, value in choices.items():
                q.put32(choice_va + 4 * ci, value)
            q.put32(chosen_va, 0)
            return 1, 20                                       # IDOK; DialogBoxParamA pops 5 arguments
        p.api_handlers["DialogBoxParamA"] = picker
        bought = p.export("VvfpStoryPickGongOutcome", 2, 0)
        return r, bought

    def test_a_chosen_result_is_bought_and_the_next_ring_gives_it(self):
        k = so._option("Grants luck")
        r, bought = self._buy({0: k})
        self.assertEqual(bought, 1)
        self.assertIn("DialogBoxParamA", r.g.proc.api_calls)
        self.assertTrue(any("Do you want to buy Pick Gong of Wonder Outcome" in m for m in r.g.proc.messages))
        self.assertFalse(any("still random" in m for m in r.g.proc.messages))
        self.assertIn("What the Gong does: Grants luck", r.g.proc.messages[0], "the confirmation names it")
        self.assertEqual(r.rest(), 1, "the Gong is ready to ring")
        self.assertEqual(r.gong()[0], so.ARMED)
        self.assertEqual(r.strike(), [so._entry(k)], "the ring takes the chosen branch")
        self.assertEqual(r.gong()[0], so.IDLE, "one use")

    def test_every_result_bought_through_the_picker_is_the_branch_rung(self):
        for k, o in enumerate(so.controls_of("vv2", so.GONG_SLOT)[0]["options"]):
            with self.subTest(result=o["label"]):
                r, bought = self._buy({0: k})
                self.assertEqual(bought, 1)
                self.assertEqual(r.strike(), [so._entry(k)])

    def test_only_the_ringer_chosen_says_the_effect_is_still_random(self):
        ringer = [c["id"] for c in so.controls_of("vv2", so.GONG_SLOT)].index("ringer")
        r, bought = self._buy({ringer: 3})
        self.assertEqual(bought, 1)
        self.assertTrue(any("The effect itself is still random" in m for m in r.g.proc.messages))
        self.assertEqual(r.strike(), [(0x44EFE4, so.stock_value(9))], "the game's own roll")


@so.emulated
class TextsFit(unittest.TestCase):
    """Every description and note fits its box at the smallest window size
    (dialog 301: description 306 x 52, note 306 x 50 dialog units, Segoe UI
    9), measured the way Windows lays out a DS_SETFONT dialog."""

    BOXES = {0: (306, 52), 1: (306, 50)}

    @classmethod
    def setUpClass(cls):
        if os.name != "nt":
            raise unittest.SkipTest("measured with Windows' own text layout")
        gdi, user = ctypes.windll.gdi32, ctypes.windll.user32
        cls.dc = user.GetDC(None)
        dpi = gdi.GetDeviceCaps(cls.dc, 90)                     # LOGPIXELSY
        cls.font = gdi.CreateFontW(-((9 * dpi + 36) // 72), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, "Segoe UI")
        gdi.SelectObject(cls.dc, cls.font)

        class SIZE(ctypes.Structure):
            _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

        class TEXTMETRICW(ctypes.Structure):
            _fields_ = [("tmHeight", ctypes.c_long)] + [(f"f{i}", ctypes.c_long) for i in range(6)] + \
                       [("pad", ctypes.c_byte * 40)]
        size, tm = SIZE(), TEXTMETRICW()
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        gdi.GetTextExtentPoint32W(cls.dc, letters, 52, ctypes.byref(size))
        gdi.GetTextMetricsW(cls.dc, ctypes.byref(tm))
        cls.base_x = (size.cx // 26 + 1) // 2
        cls.base_y = tm.tmHeight

    @classmethod
    def tearDownClass(cls):
        ctypes.windll.gdi32.DeleteObject(cls.font)
        ctypes.windll.user32.ReleaseDC(None, cls.dc)

    def fits(self, text: str, box) -> bool:
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        width = (box[0] * self.base_x) // 4
        height = (box[1] * self.base_y) // 8
        r = RECT(0, 0, width, 0)
        # SS_LEFT: DT_WORDBREAK | DT_EXPANDTABS
        ctypes.windll.user32.DrawTextW(self.dc, text, -1, ctypes.byref(r), 0x400 | 0x10 | 0x40)
        return r.bottom <= height

    def test_every_description_and_note_fits(self):
        for game in so.GAMES:
            if not so.have_stock(game):
                continue
            for gong in ((False, True) if game == "vv2" else (False,)):
                g, n = so.ChooserTests._open(None, game, gong=gong)
                for index in range(n):
                    rows = len(so.controls_of(game, so.GONG_SLOT)) if gong else 48
                    for what, row in [(0, -1), (1, -1)] + [(1, r) for r in range(rows)]:
                        g.proc.export("VvfpStoryProbeChooserWords", index, what, row & 0xFFFFFFFF,
                                      SCRATCH + 0x3000, 1200)
                        text = _cstr(g.proc, SCRATCH + 0x3000)
                        if not text:
                            continue
                        with self.subTest(game=game, gong=gong, event=index, what=what, row=row):
                            self.assertTrue(self.fits(text, self.BOXES[what]), text)


@so.emulated
class SortOrders(unittest.TestCase):
    """The villager sort orders of every companion list."""

    @classmethod
    def setUpClass(cls):
        if not so.have_stock("vv2"):
            raise unittest.SkipTest("stock executables not present")
        cls.g = so.Game("vv2")
        cls.p = cls.g.proc

    def cmp(self, a: str, b: str) -> int:
        self.p.write(SCRATCH + 0x3000, a.encode("cp1252") + b"\0")
        self.p.write(SCRATCH + 0x3400, b.encode("cp1252") + b"\0")
        v = self.p.export("VvfpStoryProbeNameCompare", SCRATCH + 0x3000, SCRATCH + 0x3400)
        return v - (1 << 32) if v & 0x80000000 else v

    def order(self, mode: int, people: list[tuple[str, int]]) -> list[int]:
        ptrs = []
        for i, (name, _) in enumerate(people):
            va = SCRATCH + 0x3000 + 64 * i
            self.p.write(va, name.encode("cp1252") + b"\0")
            ptrs.append(va)
        n = len(people)
        self.p.write(SCRATCH + 0x5000, struct.pack(f"<{n}I", *ptrs))
        self.p.write(SCRATCH + 0x5400, struct.pack(f"<{n}i", *(age for _, age in people)))
        self.p.export("VvfpStoryProbeSortOrder", mode, n, SCRATCH + 0x5000, SCRATCH + 0x5400, SCRATCH + 0x5800)
        return list(struct.unpack(f"<{n}i", self.p.read(SCRATCH + 0x5800, 4 * n)))

    def test_names_compare_first_name_then_last_case_insensitively(self):
        self.assertLess(self.cmp("anna Zed", "Bob Abel"), 0, "the first name first")
        self.assertLess(self.cmp("Anna Abel", "anna zed"), 0, "then the last name")
        self.assertEqual(self.cmp("ANNA zed", "anna ZED"), 0, "case does not matter")
        self.assertLess(self.cmp("Kenobi", "Kenobi II"), 0, "a name before its numbered ones")

    def test_numbered_names_go_in_numeral_order(self):
        numerals = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XIV", "XIX", "XX", "XL", "L"]
        for a, b in zip(numerals, numerals[1:]):
            with self.subTest(a=a, b=b):
                self.assertLess(self.cmp(f"Kenobi {a}", f"Kenobi {b}"), 0)
                self.assertGreater(self.cmp(f"Kenobi {b}", f"Kenobi {a}"), 0)
        self.assertLess(self.cmp("Bo 2", "Bo 10"), 0, "numbers too")
        self.assertLess(self.cmp("Liv Dix", "Liv Mix"), 0, "a word that only looks like a numeral is a word")

    def test_age_puts_the_oldest_at_the_top_and_ties_by_name(self):
        people = [("Cleo", 300), ("bea", 900), ("Abe", 900), ("Dan", 20), ("Kenobi II", 900)]
        self.assertEqual(self.order(1, people), [2, 1, 4, 0, 3])

    def test_alphabetical_and_the_games_own_order(self):
        people = [("Kenobi III", 5), ("Kenobi I", 5), ("anna Young", 9), ("Anna Zed", 1), ("Kenobi II", 3)]
        self.assertEqual(self.order(2, people), [2, 3, 1, 4, 0])
        self.assertEqual(self.order(0, people), [0, 1, 2, 3, 4], "the game's order is kept as it was")
        same = [("Twin", 5), ("twin", 5)]
        self.assertEqual(self.order(2, same), [0, 1], "a full tie keeps the game's order")


if __name__ == "__main__":
    unittest.main()
