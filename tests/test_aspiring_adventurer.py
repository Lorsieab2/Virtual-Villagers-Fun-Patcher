"""The Aspiring Adventurer (vvN_more_island_events): the owner's island event (2026-11-12), all five games.

Static (always run):
  * the words: the companion's table (native/vvfp_more_island_events/adv_text.inc) is what
    scripts/build_more_island_events.py makes of src/vv_aspiring_adventurer.py, every piece in both forms is a
    translation row of its own (route "key") with the same English, and the owner's wording is intact;
  * the odds: the per-outcome chances are the owner's table (A: 50/25/25, then 50/50, A1/A5/A8 8.33%, A7/A9 12.5%,
    A2/A3/A4/A6 12.5%; B: 90% home, 1 in 6 lost endings, 1 in 3 healers);
  * the rows: off by default, on in Owner's Defaults, members of Classic VV Difficulty (The Tree of Life, New
    Believers), the DLL pinned, every site's stock bytes in the row and in the companion's source;
  * Game Mechanics: the event is listed only with the patch, with every outcome's chance and its condition.

EMULATED (unicorn, the stock executables, the shipped DLL; tests/story_emulator.py), in each game:
  * WHO: the event's own test refuses the special villagers (A New Home's Golden Child, The Lost Children's
    Esteemed Elder statue, The Secret City's Tribal Chief, The Tree of Life's ghosts and bodies, New Believers'
    Heathens, roles 12-17 and Reanimated spirits), anyone under 14, anyone carrying a baby, the dead and the absent;
    the condition needs two who may go (1 -> never; 2 -> yes; 3 adults of whom 2 nurse -> never), and with exactly
    two the friend of A8 is the other one;
  * THE DRAW: the game's own selection with the companion -- The Secret City, The Tree of Life, New Believers: the
    selector's loop lists slot 0 after the stock slots only when the condition holds; A New Home: the encounter
    setup takes the draw m of rand(m + 1); The Lost Children: family A's draw 21 is kept;
  * THE POPUP through the game's own click handler, OK and constructor sites: the question's pages with OK, then the
    two buttons, the answer, the result's pages with OK, the close on the last;
  * EVERY EFFECT: A1 / A5 / A8 the reward through the game's writer (once), A2 / A4 / H1 / L4 / L5 the game's own
    death (health 0; cause -1 in the later three), A3 / A6 / L6 the removal (no body) told to the Cause of Death
    companion as a disappearance, H3 health 10..50 and running disliked, L3 +20..30 in one skill, at most 100, L2
    New Believers' conversion to a Heathen (else the removal), and the words: pronouns, both names, the stranger's
    sex, "Isolans'" with Guardians of Isola's wording and "heathens'" without;
  * THE PAGES: every page of every outcome, with the longest names each game holds, fits the game's page (and
    together the pages hold the owner's whole text, no word lost);
  * EVERY BUILD: the companion installs beside every other public patch of the game in all three population modes.

The live game is NOT exercised here.
"""
from __future__ import annotations

import hashlib
import importlib.util
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
import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402
import vv_translations as vt  # noqa: E402

try:
    import pefile
    from story_emulator import STACK_TOP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

GAMES = (1, 2, 3, 4, 5)
DLL = ROOT / "assets" / "more_island_events" / "VVFP More Island Events.dll"
EXES = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
        3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
        5: "Virtual Villagers - New Believers.exe"}
STOCK = {g: ROOT / "research" / "stock-executables" / name for g, name in EXES.items()}
HAVE_STOCK = all(p.is_file() for p in STOCK.values())
MODES = ("stock", "collection_progression", "immediate_fixed")


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = _module("adv_builder", ROOT / "scripts" / "build_more_island_events.py")
ROWS = _module("adv_rows", ROOT / "scripts" / "build_more_island_events_rows.py")

# Each game's page (characters a line, lines a page: the companion's adv_game) and longest name.
PAGE = {1: (46, 9), 2: (46, 12), 3: (46, 11), 4: (46, 11), 5: (46, 17)}
LONGEST = {1: 27, 2: 23, 3: 24, 4: 24, 5: 24}


def feature_id(game: int) -> str:
    return f"vv{game}_more_island_events"


def wrap_lines(text: str, width: int) -> int:
    """The companion's own count (adv_wrap): greedy between words, a word longer than a line breaks."""
    lines = 0
    for paragraph in text.split("\n"):
        lines += 1
        used, first = 0, True
        for word in [w for w in paragraph.split(" ") if w]:
            n = len(word)
            if not first and used + 1 + n > width:
                lines += 1
                used, first = 0, True
            if not first:
                used += 1
            while n > width:
                lines += 1
                n -= width
            used += n
            first = False
    return lines


# ---- Static ----------------------------------------------------------------------------------------------------

class TheWords(unittest.TestCase):
    def test_the_companions_table_is_generated_from_the_one_source(self) -> None:
        self.assertEqual((ROOT / "native" / "vvfp_more_island_events" / "adv_text.inc").read_text(encoding="utf-8"),
                         BUILDER.text_inc())

    def test_every_piece_is_a_key_row_with_its_english(self) -> None:
        rows = {r["stem"]: r for r in vt.load_patcher_strings()}
        for stem, key, english, _names in adv.rows():
            with self.subTest(stem=stem):
                self.assertIn(stem, rows)
                self.assertEqual(rows[stem]["english"], english)
                self.assertEqual(rows[stem].get("route"), "key")

    def test_the_owners_wording(self) -> None:
        self.assertEqual(adv.english("A9", "f"), "%s laughs at the pitiable sight and walks back to the village with a "
                                                 "smile. She will definitely have a funny story to tell over dinner.")
        self.assertEqual(adv.english("L2_OTHER", "m"), "...until a scout spots %s walking about. %s seems to have joined "
                         "another tribe. He seems no worse for the wear, so the scout goes back to report their "
                         "findings to the tribe.")
        self.assertIn("joined the Isolans' tribe", adv.english("L2_ISOLANS", "m"))
        self.assertIn("joined the heathens' tribe", adv.english("L2_HEATHENS", "f"))
        self.assertEqual(adv.english("STRANGER", "f"), "The last thing %s sees is a strange woman brandishing a knife "
                                                       "with a wide grin on her face...")
        self.assertEqual(adv.english("L6", "f"), "...and she is never seen again. In the end, the villagers can only "
                         "speculate about what happened to poor %s, and forbid anyone from ever going out in the jungle "
                         "alone again.")
        self.assertEqual(adv.names_in("A8_END"), ("n", "n", "f", "n", "f"))
        for key, template in adv.TEXTS:            # no bracketed game effect is ever shown
            with self.subTest(key=key):
                self.assertNotIn("[", template)
                self.assertNotIn("health", template)


class TheOdds(unittest.TestCase):
    def test_the_owners_table(self) -> None:
        c = adv.outcome_chances()
        a, b = c["A"], c["B"]
        for end in ("A1", "A5", "A8"):
            self.assertAlmostEqual(a[end], 100 / 12)
        for end in ("A7", "A9", "A2", "A3", "A4", "A6"):
            self.assertAlmostEqual(a[end], 12.5)
        self.assertAlmostEqual(sum(a.values()), 100)
        self.assertAlmostEqual(b["HOME"], 90)
        for end in ("L2", "L3", "L4", "L5", "L6"):
            self.assertAlmostEqual(b[end], 10 / 6)
        for end in ("H1", "H2", "H3"):
            self.assertAlmostEqual(b[end], 10 / 18)
        self.assertAlmostEqual(sum(b.values()), 100)
        # Only the Custom Island Events path could lack a friend; there A8 becomes A5.
        self.assertAlmostEqual(adv.outcome_chances(friend=False)["A"]["A5"], 100 / 6)

    def test_the_companion_rolls_the_same_odds(self) -> None:
        core = (ROOT / "native" / "vvfp_more_island_events" / "adv_core.inc").read_text(encoding="utf-8")
        for needle in ("roll < 50 ? ADV_FIND_NOTHING : (roll < 75 ? ADV_FIND_MEAT : ADV_FIND_CHEST)",
                       "adv_percent(g, 50)", "g->rand_below(2) == 0 ? 7 : 9", "SURVIVE_FIND[g->rand_below(3)]",
                       "DEADLY[g->rand_below(4)]", "adv.lost = adv_percent(g, 10)", "1 + g->rand_below(6)",
                       "1 + g->rand_below(3)", "20 + g->rand_below(11)", "10 + g->rand_below(41)",
                       "adv_eligible_count(g, -1) >= 2", "adv.award = adv_award_roll(g, adv.award_kind, 1);",
                       "int base = lo + (hi > lo ? g->rand_below(hi - lo + 1) : 0);",
                       "return g->award_amount(kind, base * times);"):
            self.assertIn(needle, core)


class TheRows(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = {p.id: p.raw for p in patcher.load_fun_patches()}

    def test_five_rows_off_by_default_on_in_owners_defaults(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                self.assertIn(feature_id(game), self.rows)
                self.assertIn(feature_id(game), gui.DEFAULT_OFF_FUN_PATCH_IDS)
                self.assertNotIn(feature_id(game), gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)

    def test_classic_vv_difficulty_ticks_it(self) -> None:
        for game in (4, 5):
            row = json.loads((ROOT / "data" / f"vv{game}_classic_vv_difficulty_feature.json").read_text(encoding="utf-8"))
            self.assertIn(feature_id(game), row["dependencies"])

    def test_the_dll_is_pinned_and_started_by_the_loader(self) -> None:
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for game in GAMES:
            row = self.rows[feature_id(game)]
            self.assertEqual(row["companion_files"][0]["sha256"], sha)
        self.assertIn("VVFP More Island Events.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        self.assertIn('"VVFP More Island Events.dll"',
                      (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8"))

    def test_every_site_is_in_the_row_and_the_source(self) -> None:
        source = "".join(p.read_text(encoding="utf-8")
                         for p in (ROOT / "native" / "vvfp_more_island_events").glob("adv_vv*.inc"))
        for game in GAMES:
            row = self.rows[feature_id(game)]
            self.assertEqual([d["va"] for d in row["runtime_detours"]], [f"0x{s[0]:X}" for s in ROWS.SITES[game]])
            for va, stock, *_ in ROWS.SITES[game]:
                with self.subTest(game=game, va=hex(va)):
                    self.assertIn(f"0x{va:X}", source)
                    pairs = ", ".join(f"0x{stock[i:i + 2]}" for i in range(0, len(stock), 2))
                    self.assertIn(pairs.upper().replace("0X", "0x"), source)


class TheMechanicsPage(unittest.TestCase):
    def test_listed_only_with_the_patch(self) -> None:
        import vv_game_mechanics_events as gme
        for game in GAMES:
            catalog = importlib.import_module(f"vv_game_mechanics_events_vv{game}")
            event = next(e for e in catalog.EVENTS if e.title == adv.TITLE)
            self.assertEqual(event.only_with, feature_id(game))
            text = event.text + " " + " ".join(s if isinstance(s, str) else s.text for s in event.subs)
            with self.subTest(game=game):
                self.assertIn("needs at least two villagers", text)
                self.assertIn("not nursing a baby", text)
                for words in ("pile of dirt 50%", "meat 25%", "golden chest of artifacts 25%", "A1 8.33%",
                              "A5 8.33%", "A8 8.33%", "A7 12.5%", "A9 12.5%", "A2 (the beast, dies, a grave) 12.5%",
                              "home safe 90%", "1 in 6", "1 in 3", "0.56%", "1.67%", "20 to 30", "10 to 50",
                              "the friend always exists"):
                    self.assertIn(words, text)
            self.assertTrue(gme)


import importlib  # noqa: E402  (used above)


# ---- Emulated -----------------------------------------------------------------------------------------------------

# Each game's villager fields: name, its bytes, sex (value of a woman), age, health, present, carrying, likes,
# dislikes, slots, the skills (Farming, Building, Research, Healing) and whether they are floats.
LAYOUT = {
    1: dict(name=0x370, name_bytes=0x1C, sex=0x350, woman=2, age=0x348, health=0x344, present=0x28, carrying=0x358,
            likes=0x398, dislikes=0x3A8, slots=4, skills=(0x3C4, 0x3C0, 0x3CC, 0x3C8), floats=False),
    2: dict(name=0x564, name_bytes=0x18, sex=0x538, woman=2, age=0x530, health=0x52C, present=0x30, carrying=0x540,
            likes=0x5F0, dislikes=0x6E8, slots=62, skills=(0x7EC, 0x7E8, 0x7F4, 0x7F0), floats=False),
    3: dict(name=0xDD4, name_bytes=0x19, sex=0xDC8, woman=1, age=0xDC4, health=0xE78, present=0xF10, carrying=0xE8C,
            likes=0xFB4, dislikes=0xFC0, slots=3, skills=(0xEAC, 0xEBC, 0xEB8, 0xEB4), floats=False),
    4: dict(name=0x1B9C, name_bytes=0x19, sex=0x1B90, woman=1, age=0x1B8C, health=0x1C40, present=0x1CC4,
            carrying=0x1C4C, likes=0x1E60, dislikes=0x1E6C, slots=3, skills=(0x1C5C, 0x1C6C, 0x1C68, 0x1C64),
            floats=True),
    5: dict(name=0x1B9C, name_bytes=0x19, sex=0x1B90, woman=1, age=0x1B8C, health=0x1C40, present=0x1CD4,
            carrying=0x1C4C, likes=0x1F5C, dislikes=0x1F68, slots=3, skills=(0x1C5C, 0x1C6C, 0x1C68, 0x1C64),
            floats=True),
}
SPECIAL = {1: ((0x36C, 4, 0xC7),), 2: ((0x558, 1, 1),), 3: ((0xE80, 1, 1), (0xE94, 1, 1)), 4: ((0x1CC7, 1, 1),),
           5: ((0x1CEC, 1, 1), (0x1CFC, 4, 12), (0x1CFC, 4, 13), (0x1CFC, 4, 17), (0x1CE1, 1, 1))}
TABLES = {3: dict(manager=0x59E110, first=0x14, stride=0x1F8C, table=0x4B3C78, strings=0x592730,
                  loop=(0x419B54, 0x419B73), offset=8, settext=0x4185A0, hide=0x40C230, show=0x40C1F0,
                  close=0x40E020, ctor=0x4192F0, site=(0x419BEA, 0x419BEF), click=0x419A00, rand=0x4032D0,
                  food=0x582490, tech=0x582644),
          4: dict(manager=0x50E568, first=0x44, stride=0x2E3C, table=0x4CCA28, strings=0x4DEA20,
                  loop=(0x418050, 0x418075), offset=0x10, settext=0x416F60, hide=0x40C210, show=0x40C190,
                  close=0x40E090, ctor=0x417790, site=(0x418106, 0x41810B), click=0x417EA0, rand=0x4036D0,
                  food=0x4D6DD0, tech=0x4D6F88),
          5: dict(manager=0x554148, first=0x48, stride=0x2F44, table=0x4DC850, strings=0x5240A8,
                  loop=(0x4188C0, 0x4188E5), offset=0x10, settext=0x417700, hide=0x40C700, show=0x40C680,
                  close=0x40E580, ctor=0x418020, site=(0x41896A, 0x41896F), click=0x418720, rand=0x403660,
                  food=0x51D34C, tech=0x51D5F8)}
# Achievement counters the later games' writers call (their object is not built here): stood in for.
COUNTERS = {4: {0x412F90: 8}, 5: {0x413450: 8, 0x423600: 4}}
TOP = 99999                                    # a scripted roll meaning "the last value" (n - 1)
TITLE_LINE = "The Aspiring Adventurer\n"       # A New Home's and The Lost Children's title line
FAKE_COD = 0x0E800000


class Village:
    """One game with the companion started, villagers in the game's own records, the popup driven through the
    game's own click handler."""

    def __init__(self, game: int, exe: bytes | None = None):
        self.game = game
        self.p = Process(exe if exe is not None else STOCK[game].read_bytes(), DLL)
        self.rolls: list[int] = []
        self.ui: list[tuple] = []
        self.vanished: list[tuple] = []
        self.calls: list[tuple] = []
        self._cod()
        self.p.export("VvfpStartup", game, 0)
        self.installed = self.p.export("VvfpMoreIslandEventsInstalled")
        self.L = LAYOUT[game]
        p = self.p
        if game == 1:
            self.world = p.alloc(0x10000)
            self.base = p.alloc(0x3D8 * 256)
            p.put32(0x48AEDC, self.world)
            p.put32(0x48B614, self.base)
            p.put32(self.world + 0x9E40, 5)
            p.put32(self.world + 0xAD34, 0xFFFFFFFF)
            self.stride, self.first = 0x3D8, 0
            self.rand = 0x402F10
            p.stub(0x43A160, self._log("select"))
            p.stub(0x40AB80, self._log("add"))
            p.stub(0x40ABC0, self._log("remove"))
            p.stub(0x40C9B0, self._log("close", 0))
        elif game == 2:
            self.world = p.alloc(0x40000)
            self.base = p.alloc(0x30 + 0xE48C * 256)
            p.put32(0x4997BC, self.world)
            p.put32(0x499F24, self.base)
            p.put32(self.world + 0x305A4, self.base)          # the pool the game's population count reads
            p.put32(self.world + 0x2E51C, 5)
            self.stride, self.first = 0xE48C, 0x30
            self.rand = 0x4031A0
            p.stub(0x44B2D0, self._log("select"))
            p.stub(0x40B560, self._log("add"))
            p.stub(0x40B5A0, self._log("remove"))
            p.stub(0x40D390, self._log("close", 0))
            p.stub(0x4491F0, lambda pr: (self.calls.append(("deselect",)) or 0, 0))   # The Voices' selection drop
        else:
            t = self.t = TABLES[game]
            self.base, self.stride, self.first = t["manager"], t["stride"], t["first"]
            self.rand = t["rand"]
            p.stub(t["settext"], self._settext)
            p.stub(t["hide"], self._log("hide"))
            p.stub(t["show"], self._log("show"))
            p.stub(t["close"], self._log("close", 0))
            for va, pop in COUNTERS.get(game, {}).items():
                p.stub(va, lambda pr, pop=pop: (0, pop))
            if game in (4, 5):
                # The game's own stop and health setter (thiscall on the record's health block +0x1C34: value,
                # cause) reach the game's world, which is not built here: stood in for, and every call kept, so a
                # test sees the companion ask for the game's own death (0, cause -1).
                stop, setter = (0x468C60, 0x46AF00) if game == 4 else (0x473440, 0x4758B0)
                p.stub(stop, lambda pr: (self.calls.append(("stop", pr.reg("ecx"))) or 0, 0))

                def set_health(pr):
                    block = pr.reg("ecx")
                    pr.put32(block + 0xC, pr.arg(0))
                    self.calls.append(("health", block - 0x1C34, pr.arg(0), pr.arg(1) - (1 << 32) if pr.arg(1) >> 31
                                       else pr.arg(1)))
                    return 0, 8
                p.stub(setter, set_health)
            if game == 5:
                p.stub(0x4653D0, lambda pr: (0, 0))                            # not the one selected

                def convert(pr):
                    pr.write(pr.reg("ecx") + 0x1CEC, b"\x01")
                    self.calls.append(("heathen", pr.reg("ecx")))
                    return 0, 0
                p.stub(0x4669E0, convert)
            for k in range(1, 60):
                p.put32(t["table"] + 4 * k, 0)
        p.stub(self.rand, self._rand)

    # -- stand-ins -------------------------------------------------------------------------------------------
    def _cod(self) -> None:
        p = self.p
        stub = p.alloc(16)
        p.write(stub, b"\xC3")

        def module(pr):
            name = pr.cstring(pr.arg(0)) if pr.arg(0) else ""
            return (FAKE_COD if name == "VVFP Cause of Death.dll" else 0), 4

        def proc(pr):
            return (stub if pr.arg(0) == FAKE_COD and pr.cstring(pr.arg(1)) == "VvfpCauseVanishedBy" else 0), 8

        def told(pr):
            self.vanished.append((pr.arg(0), pr.arg(1), pr.cstring(pr.arg(2))))
            return 0, 12
        p.api_handlers["GetModuleHandleA"] = module
        p.api_handlers["GetProcAddress"] = proc
        p.stub(stub, told)

    def _rand(self, pr):
        n = pr.arg(0)
        v = self.rolls.pop(0) if self.rolls else 0
        return (n - 1 if v == TOP else v % max(1, n)), 0

    def _log(self, what: str, pop: int = 4):
        def fn(pr):
            self.ui.append((what, pr.arg(0)) if pop else (what,))
            return 0, pop
        return fn

    def _settext(self, pr):
        slot = pr.u32(self.t["strings"] + 4 * pr.arg(0))
        self.ui.append(("text", pr.cstring(pr.u32(slot + 8), 4000)))
        return 0, 4

    # -- villagers -----------------------------------------------------------------------------------------------
    def rec(self, i: int) -> int:
        return self.base + self.first + i * self.stride

    def villager(self, i: int, name: str, woman: bool = False, years: int = 20, health: int = 100,
                 carrying: int = 0, special=None) -> None:
        r, L, p = self.rec(i), self.L, self.p
        p.write(r + L["name"], name.encode()[:L["name_bytes"] - 1] + b"\0")
        p.put32(r + L["sex"], L["woman"] if woman else (1 if self.game <= 2 else 0))
        p.put32(r + L["age"], years * 20)
        p.put32(r + L["health"], health)
        p.write(r + L["present"], b"\x01")
        p.put32(r + L["carrying"], carrying)
        for k in range(L["slots"]):
            p.put32(r + L["likes"] + 4 * k, 0xFFFFFFFF)
            p.put32(r + L["dislikes"] + 4 * k, 0xFFFFFFFF)
        for off in L["skills"]:
            p.write(r + off, struct.pack("<f", 50.0) if L["floats"] else struct.pack("<i", 50))
        if special is not None:
            off, size, value = special
            p.write(r + off, value.to_bytes(size, "little"))

    def eligible(self, i: int) -> int:
        return self.p.export("VvfpAdventurerEligible", self.rec(i))

    def possible(self) -> int:
        return self.p.export("VvfpAdventurerPossible")

    def health(self, i: int) -> int:
        return struct.unpack("<i", self.p.read(self.rec(i) + self.L["health"], 4))[0]

    def present(self, i: int) -> int:
        return self.p.read(self.rec(i) + self.L["present"], 1)[0]

    def skill(self, i: int, which: int) -> float:
        raw = self.p.read(self.rec(i) + self.L["skills"][which], 4)
        return struct.unpack("<f" if self.L["floats"] else "<i", raw)[0]

    def dislikes(self, i: int) -> list[int]:
        r = self.rec(i) + self.L["dislikes"]
        return [struct.unpack("<i", self.p.read(r + 4 * k, 4))[0] for k in range(self.L["slots"])]

    def stores(self) -> tuple[int, int]:
        if self.game == 1:
            return self.p.u32(self.world + 0xA2EC), self.p.u32(self.world + 0xA2FC)
        if self.game == 2:
            return self.p.u32(self.world + 0x2EAA4), self.p.u32(self.world + 0x2EADC)
        return self.p.u32(self.t["food"]), self.p.u32(self.t["tech"])

    def state(self) -> list[int]:
        out = self.p.alloc(19 * 4)
        self.p.export("VvfpAdventurerState", out)
        return [struct.unpack("<i", self.p.read(out + 4 * k, 4))[0] for k in range(19)]

    def pages(self, which: int) -> list[str]:
        out, k = [], 0
        while True:
            at = self.p.export("VvfpAdventurerPage", which, k)
            if not at:
                return out
            out.append(self.p.cstring(at, 4000))
            k += 1

    # -- the draw ------------------------------------------------------------------------------------------------
    def listed(self) -> bool:
        """The Secret City, The Tree of Life, New Believers: every stock slot empty, the selector's loop run; True
        when slot 0 (the event) was listed."""
        p, t = self.p, self.t
        esp = STACK_TOP - 0x2000
        p.set_reg("esp", esp)
        p.set_reg("esi", 1)
        p.set_reg("edi", 0)
        p.run(*t["loop"])
        self.obj = p.u32(t["table"])
        return p.reg("edi") == 1 and p.u32(esp + t["offset"]) == 0

    # -- the popup -----------------------------------------------------------------------------------------------
    def begin(self, rolls: list[int]) -> bool:
        """The event drawn and its popup built; False when the game's own code went another way."""
        p = self.p
        self.ui.clear()
        if self.game == 1:
            self.dlg = p.alloc(0x6000)
            p.put32(self.dlg + 0x50A4, self.world)
            p.put32(self.dlg + 0x50A8, self.base)
            for o, v in ((0x54, 2), (0x58, 3), (0x5C, 4), (0x50BC, 0x111), (0x50C0, 0x222), (0x50C4, 0x333)):
                p.put32(self.dlg + o, v)
            self.rolls = [TOP] + list(rolls)
            p.call(0x4189E0, [], ecx=self.dlg)
            if p.u32(self.dlg + 0x5094) != 0x7F4B1A2E:
                return False
            esp = STACK_TOP - 0x3000 - 4
            p.put32(esp, 0x222)
            p.set_reg("esp", esp)
            p.set_reg("ecx", self.dlg)
            p.run(0x41A87C, 0x41A881)
            return True
        if self.game == 2:
            self.dlg = p.alloc(0x6000)
            p.put32(self.dlg + 0x50AC, self.world)
            p.put32(self.dlg + 0x50B0, self.base)
            for o, v in ((0x54, 2), (0x58, 3), (0x5C, 4), (0x50C8, 0x111), (0x50CC, 0x222), (0x50D0, 0x333)):
                p.put32(self.dlg + o, v)
            self.rolls = [TOP] + list(rolls)
            if p.call(0x41F780, [], ecx=self.dlg) & 0xFF == 0 or p.u32(self.dlg + 0x509C) != 21:
                return False
            p.stub(0x422380, lambda pr: (pr.reg("ecx"), 0))
            p.set_reg("esp", STACK_TOP - 0x3000)
            p.set_reg("ecx", self.dlg)
            p.run(0x42F1A3, 0x42F1A8)
            return True
        t = self.t
        if not self.listed():
            return False
        self.dlg = p.alloc(0x1000)
        for o, v in ((0x85C, 0x111), (0x860, 0x222), (0x864, 0x333)):
            p.put32(self.dlg + o, v)
        self.rolls = list(rolls)
        p.call(p.u32(p.u32(self.obj) + 8), ecx=self.obj)          # the title, as the constructor asks it first

        def ctor(pr):
            pr.put32(pr.reg("ecx") + 0x50, pr.arg(0))
            return pr.reg("ecx"), 4
        p.stub(t["ctor"], ctor)
        esp = STACK_TOP - 0x3000 - 4
        p.put32(esp, self.obj)
        p.set_reg("esp", esp)
        p.set_reg("ecx", self.dlg)
        p.run(*t["site"])
        if not any(u[0] == "text" for u in self.ui):     # one page: the question the constructor set
            self.ui.append(("text", self.pages(0)[-1]))
        return True

    def click(self, button: int) -> None:
        """OK (0), the first answer (1) or the second (2), through the game's own click handler."""
        handler = {1: 0x41A3D0, 2: 0x4222F0}.get(self.game) or self.t["click"]
        ident = {0: 4, 1: 2, 2: 3}[button] if self.game <= 2 else {0: 1, 1: 2, 2: 3}[button]
        self.p.call(handler, [8, ident], ecx=self.dlg)

    def shown(self) -> str:
        """The text the popup shows now."""
        if self.game == 1:
            return self.p.cstring(self.dlg + (0x2783 if self.p.read(self.dlg + 0x50, 1)[0] else 0x74), 6000)
        if self.game == 2:
            return self.p.cstring(self.dlg + (0x278B if self.p.read(self.dlg + 0x50, 1)[0] else 0x7C), 6000)
        texts = [u[1] for u in self.ui if u[0] == "text"]
        return texts[-1] if texts else ""

    def closed(self) -> bool:
        return ("close",) in self.ui

    def play(self, rolls: list[int], answer: int) -> list[str]:
        """The whole event: each page shown, in order (the question's pages, then the result's), until the close --
        each as one line of words (A New Home's and The Lost Children's own line breaks and title taken out)."""
        return [re.sub(r"\s+", " ", page.replace(TITLE_LINE, "")).strip() for page in self._play(rolls, answer)]

    def _play(self, rolls: list[int], answer: int) -> list[str]:
        self.assertion = []
        if not self.begin(rolls):
            raise AssertionError("the event was not drawn")
        state = self.state()
        seen = [self.shown()]
        for _ in range(state[15] - 1):              # the question's pages, with OK
            self.click(0)
            seen.append(self.shown())
        self.click(answer)
        seen.append(self.shown())
        result = self.state()[16 if answer == 1 else 17]
        for _ in range(result - 1):
            self.click(0)
            seen.append(self.shown())
        self.ui.clear()
        self.click(0)
        self.closed_at_end = self.closed()
        return seen


def rolls(*, hero=0, friend=None, find=0, survive=True, end=0, stranger=0, award=0, lost=False, lost_end=1, healer=1,
          skill=0, amount=0, injured=0, game=4) -> list[int]:
    """The rolls adv_begin draws, in its order.  find: 0 dirt, 1 meat, 2 chest; end: the index within the half;
    award: the reward's draw within the game's range (adv.award_range; TOP the largest), drawn only when the range
    has more than one amount (The Tree of Life's food is always 300).  The game's rand is asked only when there is a
    choice: with one possible friend (two who may go), none is drawn for the friend (friend=None)."""
    lo, hi = adv.award_range(game, "tech" if find == 2 else "food")
    out = [hero] + ([] if friend is None else [friend]) + [(0, 60, 80)[find], 0 if survive else 99, end, stranger]
    out += [award] if hi > lo else []
    if game == 3:
        out.append(0)                   # The Secret City's own count for its multiplier (0x45D460) draws one
    out += [0 if lost else 99, lost_end - 1, healer - 1, skill, amount, injured]
    return out


NAMES = {1: "Abcdefghijklmnopqrstuvwxyz1", 2: "Abcdefghijklmnopqrstuvw", 3: "Abcdefghijklmnopqrstuvwx",
         4: "Abcdefghijklmnopqrstuvwx", 5: "Abcdefghijklmnopqrstuvwx"}


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Who(unittest.TestCase):
    def test_installed_in_every_game(self) -> None:
        for game in GAMES:
            self.assertEqual(Village(game).installed, game)

    def test_the_special_the_young_the_nursing_the_dead_and_the_absent_never_go(self) -> None:
        for game in GAMES:
            v = Village(game)
            v.villager(0, "Ana", True)
            self.assertEqual(v.eligible(0), 1)
            cases = [("13 years", dict(years=13)), ("nursing", dict(carrying=500)), ("dead", dict(health=0))]
            cases += [(f"special {s}", dict(special=s)) for s in SPECIAL[game]]
            for what, kw in cases:
                with self.subTest(game=game, what=what):
                    v.villager(1, "Ben", **kw)
                    self.assertEqual(v.eligible(1), 0)
            v.villager(1, "Ben")
            v.p.write(v.rec(1) + v.L["present"], b"\x00")
            self.assertEqual(v.eligible(1), 0)

    def test_two_who_may_go_are_needed(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v = Village(game)
                v.villager(0, "Ana", True)
                self.assertEqual(v.possible(), 0)               # 1 -> never
                v.villager(1, "Ben", carrying=500)
                v.villager(2, "Cal", carrying=500)
                self.assertEqual(v.possible(), 0)               # 3 adults, 2 nursing -> never
                v.villager(2, "Cal")
                self.assertEqual(v.possible(), 1)               # 2 -> possible
                if game >= 3:
                    self.assertTrue(v.listed())
                    v.villager(2, "Cal", years=10)
                    self.assertFalse(v.listed())                # the selector does not list it

    def test_with_two_the_friend_is_the_other(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v = Village(game)
                v.villager(0, "Ana", True)
                v.villager(1, "Ben", years=10)                  # a child never goes
                v.villager(2, "Cal")
                seen = v.play(rolls(hero=0, find=1, end=2, game=game), 1)      # A8
                state = v.state()
                self.assertEqual((state[0], state[1], state[4]), (0, 2, 8))
                self.assertIn("Together Ana and Cal return", " ".join(seen))


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Effects(unittest.TestCase):
    def village(self, game: int, woman: bool = True) -> Village:
        v = Village(game)
        v.villager(0, "Ana", woman)
        v.villager(1, "Ben")
        return v

    def test_the_rewards(self) -> None:
        """A normal award (the owner, 2026-11-12): the game's stock island-event range, each amount equally likely --
        the draw's lowest, a middle one and the highest (TOP) give lo, lo + 7 and hi (a small village: no scaling)."""
        for game in GAMES:
            for find, end, a_end, draw in ((1, 0, 1, 0), (2, 1, 5, 7), (1, 2, 8, TOP), (2, 0, 1, TOP)):
                with self.subTest(game=game, find=find, end=a_end, draw=draw):
                    v = self.village(game)
                    before = v.stores()
                    seen = v.play(rolls(find=find, end=end, award=draw, game=game), 1)
                    state = v.state()
                    self.assertEqual(state[4], a_end)
                    after = v.stores()
                    gained = (after[0] - before[0], after[1] - before[1])
                    self.assertEqual(gained, (state[11], 0) if find == 1 else (0, state[11]))
                    lo, hi = adv.award_range(game, "food" if find == 1 else "tech")
                    expected = hi if draw == TOP else min(hi, lo + draw)
                    self.assertEqual(state[11], expected)
                    kind = "food" if find == 1 else "tech points"
                    self.assertIn(f"Your villagers gain {state[11]} {kind}.", " ".join(seen))
                    self.assertEqual(v.health(0), 100)
                    self.assertTrue(v.closed_at_end)

    def test_the_ranges_are_the_companions(self) -> None:
        """The companion's adv_game ranges are src/vv_aspiring_adventurer.py's AWARD_RANGES."""
        source = "".join(p.read_text(encoding="utf-8")
                         for p in (ROOT / "native" / "vvfp_more_island_events").glob("adv_vv*.inc"))
        for game in GAMES:
            r = adv.AWARD_RANGES[game]
            line = f"{r['food'][0]}, {r['food'][1]}, {r['tech'][0]}, {r['tech'][1]}, "
            with self.subTest(game=game):
                self.assertIn(line, source)

    def test_the_reward_scales_as_island_events_scale_scales(self) -> None:
        """With "VVFP Island Events Scale.dll" loaded (stood in for: its VvfpIslandEventsScaleMode export), the reward
        is scaled by its rule -- the population by the game's own count (stood in for) or a tenth of the store."""
        counts = {1: 0x41CF90, 4: 0x467610, 5: 0x4713F0}
        for game in (1, 4, 5):
            lo = adv.award_range(game, "food")[0]            # the draw 0: the range's lowest
            for mode, people, expected in ((1, 30, 2 * lo), (1, 51, 3 * lo), (2, 0, lo + 4000 // 10)):
                with self.subTest(game=game, mode=mode, people=people):
                    v = self.village(game)
                    p = v.p
                    fake = 0x0E900000
                    mode_stub = p.alloc(16)
                    p.write(mode_stub, b"\xC3")
                    p.stub(mode_stub, lambda pr, mode=mode: (mode, 0))
                    p.stub(counts[game], lambda pr, people=people: (people, 0))
                    cod_module, cod_proc = p.api_handlers["GetModuleHandleA"], p.api_handlers["GetProcAddress"]
                    p.api_handlers["GetModuleHandleA"] = lambda pr, m=cod_module: (
                        (fake, 4) if pr.cstring(pr.arg(0)) == "VVFP Island Events Scale.dll" else m(pr))
                    p.api_handlers["GetProcAddress"] = lambda pr, c=cod_proc: (
                        (mode_stub, 8) if pr.arg(0) == fake else c(pr))
                    if game == 1:
                        p.put32(v.world + 0xA2EC, 4000)
                    else:
                        p.put32(v.t["food"], 4000)
                    before = v.stores()[0]
                    seen = " ".join(v.play(rolls(find=1, end=0, game=game), 1))
                    self.assertEqual(v.state()[11], expected)
                    self.assertEqual(v.stores()[0] - before, expected)
                    self.assertIn(f"Your villagers gain {expected} food.", seen)

    def test_deaths_and_disappearances(self) -> None:
        for game in GAMES:
            for answer, kw, dies in ((1, dict(survive=False, end=0), True), (1, dict(survive=False, end=2), True),
                                     (1, dict(survive=False, end=1), False), (1, dict(survive=False, end=3), False),
                                     (2, dict(lost=True, lost_end=1, healer=1), True),
                                     (2, dict(lost=True, lost_end=4), True), (2, dict(lost=True, lost_end=5), True),
                                     (2, dict(lost=True, lost_end=6), False)):
                with self.subTest(game=game, answer=answer, kw=kw):
                    v = self.village(game)
                    before = v.stores()
                    v.play(rolls(game=game, **kw), answer)
                    self.assertEqual(v.stores(), before)         # never a reward
                    if dies:
                        self.assertEqual(v.health(0), 0)
                        if game in (4, 5):                       # the game's own setter, cause -1 "Unknown causes"
                            self.assertIn(("health", v.rec(0), 0, -1), v.calls)
                        self.assertEqual(v.present(0), 1)        # the body lies: a grave comes
                        self.assertEqual(v.vanished, [])
                    else:
                        self.assertEqual(v.present(0), 0)        # gone, no body
                        self.assertEqual(len(v.vanished), 1)
                        self.assertEqual(v.vanished[0][:2], (game, 0))
                        self.assertTrue(v.vanished[0][2].startswith("Disappeared in The Aspiring Adventurer"))
                    self.assertEqual(v.health(1), 100)
                    self.assertEqual(v.present(1), 1)

    def test_the_healers_the_survivalist_and_the_safe_path(self) -> None:
        for game in GAMES:
            with self.subTest(game=game, what="disabled"):
                v = self.village(game)
                v.play(rolls(game=game, lost=True, lost_end=1, healer=3, injured=40), 2)
                self.assertEqual(v.health(0), 50)
                self.assertIn(38, v.dislikes(0))                 # running
            with self.subTest(game=game, what="full recovery"):
                v = self.village(game)
                v.play(rolls(game=game, lost=True, lost_end=1, healer=2), 2)
                self.assertEqual((v.health(0), v.present(0)), (100, 1))
            for which in range(4):
                with self.subTest(game=game, what="survivalist", skill=which):
                    v = self.village(game)
                    v.play(rolls(game=game, lost=True, lost_end=3, skill=which, amount=10), 2)
                    self.assertEqual(v.skill(0, which), 80)
                    for other in range(4):
                        if other != which:
                            self.assertEqual(v.skill(0, other), 50)
            with self.subTest(game=game, what="capped"):
                v = self.village(game)
                v.p.write(v.rec(0) + v.L["skills"][2], struct.pack("<f", 95.0) if v.L["floats"] else
                          struct.pack("<i", 95))
                v.play(rolls(game=game, lost=True, lost_end=3, skill=2, amount=10), 2)
                self.assertEqual(v.skill(0, 2), 100)
            with self.subTest(game=game, what="home safe"):
                v = self.village(game)
                before = v.stores()
                seen = v.play(rolls(game=game, lost=False), 2)
                self.assertEqual((v.health(0), v.present(0), v.stores()), (100, 1, before))
                self.assertIn("And manages to make it home safely.", seen[-1])

    def test_joining_another_tribe(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v = self.village(game)
                seen = " ".join(v.play(rolls(game=game, lost=True, lost_end=2), 2))
                if game == 5:
                    self.assertEqual(v.p.read(v.rec(0) + 0x1CEC, 1)[0], 1)      # a Heathen now
                    self.assertEqual(v.present(0), 1)
                    self.assertIn("is seen wearing a mask and seems to have joined the heathens' tribe", seen)
                else:
                    self.assertEqual(v.present(0), 0)
                    self.assertEqual(v.vanished[0][2], "Disappeared in The Aspiring Adventurer (joined another tribe)")
                    self.assertIn("Ana seems to have joined another tribe. She seems no worse", seen)

    def test_isolans_with_guardians_of_isola(self) -> None:
        v = self.village(5)
        entry = v.p.alloc(32)
        text = v.p.alloc(64)
        v.p.write(text, b"A villager has left the tribe!\0")
        v.p.write(entry, struct.pack("<IIII", 0x48, 0, text, 0))
        v.p.put32(0x5240A8 + 4 * 0x48, entry)
        seen = " ".join(v.play(rolls(game=5, lost=True, lost_end=2), 2))
        self.assertIn("joined the Isolans' tribe", seen)

    def test_pronouns_and_the_stranger(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v = self.village(game, woman=False)
                seen = " ".join(v.play(rolls(game=game, survive=False, end=2, stranger=1), 1))      # A4
                self.assertIn("Ana is an aspiring adventurer. Every morning he goes off", seen)
                self.assertIn("a strange woman brandishing a knife with a wide grin on her face", seen)
                self.assertIn("lay him to rest", seen)
                v = self.village(game, woman=True)
                seen = " ".join(v.play(rolls(game=game, survive=False, end=2, stranger=0), 1))
                self.assertIn("a strange man brandishing a knife with a wide grin on his face", seen)
                self.assertIn("lay her to rest", seen)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class Pages(unittest.TestCase):
    OUTCOMES = ([("A", dict(find=f, survive=True, end=e)) for f in (1, 2) for e in range(3)]
                + [("A", dict(find=0, survive=True, end=e)) for e in range(2)]
                + [("A", dict(find=f, survive=False, end=e)) for f in range(3) for e in range(4)]
                + [("B", dict(lost=False))]
                + [("B", dict(lost=True, lost_end=k, healer=h)) for k in range(1, 7) for h in ((1, 2, 3) if k == 1 else (1,))])

    def test_every_page_fits_with_the_longest_names(self) -> None:
        for game in GAMES:
            width, lines = PAGE[game]
            for answer, kw in self.OUTCOMES:
                with self.subTest(game=game, answer=answer, kw=kw):
                    v = Village(game)
                    v.villager(0, NAMES[game], True)
                    v.villager(1, NAMES[game][::-1], False)
                    v.begin(rolls(game=game, **kw))
                    for which in (0, 1, 2):
                        for page in v.pages(which):
                            self.assertLessEqual(wrap_lines(page, width), lines, page)
                    # The words are whole: every piece, filled, is in the pages, in order.
                    joined = " ".join(" ".join(v.pages(w)) for w in (0, 1, 2)).replace("\n", " ")
                    self.assertIn(adv.fill("INTRO_1", "f", NAMES[game][:LONGEST[game]]), joined)

    def test_shown_pages_carry_the_title_and_room_for_the_picture(self) -> None:
        for game in (1, 2):
            v = Village(game)
            v.villager(0, "Ana", True)
            v.villager(1, "Ben")
            v.begin(rolls(game=game, find=1, end=0))
            shown = v.shown()
            self.assertTrue(shown.startswith("The Aspiring Adventurer\n\n\n\n\n\n"), shown[:60])
            width, lines = PAGE[game]
            for line in shown.split("\n"):
                self.assertLessEqual(len(line), width)
            self.assertLessEqual(len(shown.split("\n")), 1 + 5 + lines)


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class EveryBuild(unittest.TestCase):
    def others(self, game: int) -> list[str]:
        return [p.id for p in patcher.load_public_fun_patches()
                if p.game_id == f"vv{game}" and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS
                and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS and p.id != feature_id(game)]

    def render(self, game: int, mode: str, ids) -> bytes:
        build = next(b for b in patcher.load_builds() if b.id == f"vv{game}")
        data, _ = patcher.render_patched_bytes(STOCK[game], build, mode, list(ids))
        return bytes(data)

    def test_with_every_other_patch_in_every_mode(self) -> None:
        for game in GAMES:
            ids = patcher.resolve_fun_patch_ids(self.others(game) + [feature_id(game)], game_id=f"vv{game}")
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    exe = self.render(game, mode, ids)
                    pe = pefile.PE(data=exe, fast_load=True)
                    image = pe.get_memory_mapped_image()
                    for va, stock, *_ in ROWS.SITES[game]:
                        self.assertEqual(image[va - 0x400000:va - 0x400000 + len(stock) // 2].hex().upper(), stock,
                                         hex(va))
                    self.assertEqual(Village(game, exe=exe).installed, game)

    def test_a_site_that_is_not_stock_installs_nothing(self) -> None:
        for game in GAMES:
            data = bytearray(STOCK[game].read_bytes())
            pe = pefile.PE(data=bytes(data), fast_load=True)
            va = ROWS.SITES[game][-1][0]
            data[pe.get_offset_from_rva(va - 0x400000)] ^= 0xFF
            v = Village(game, exe=bytes(data))
            self.assertEqual(v.installed, 0)
            for other_va, stock, *_ in ROWS.SITES[game][:-1]:
                self.assertEqual(v.p.read(other_va, len(stock) // 2).hex().upper(), stock)


if __name__ == "__main__":
    unittest.main()
