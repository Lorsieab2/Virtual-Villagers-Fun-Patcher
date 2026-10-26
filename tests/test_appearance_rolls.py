"""Fix Vanilla Bugs: every random head and body roll reaches the last row ("VVFP Appearance Rolls.dll",
native/vvfp_appearance_rolls).  The owner, 2026-10-25: "for all games except VV3 (both genders; the Tribal
Chief's body) and VV1 (male villagers only; the Golden Child's body), fix the body selector to accept that last
body", and every random head may spawn too, except the Golden Child's head in A New Home.

Every roll of a head or a body, per game (rand(n) = the game's rand() % n; 30 rows per sex, A New Home 20):

  A New Home   creator 0x43C350: a boy head and body rand(19) (0x43C61F), a girl rand(20) (0x43C62A) --
               a boy's row 19 is the Golden Child's (0x43C7EA), so it stays; twins copy (0x43C9C1); "A
               Mysterious Vial": a man rand(19) (0x42C92D, 0x42C9C9), a woman rand(20) (0x42C9F6, 0x42CA23);
               the roster reset 0x41C000 (rand(20) both, every slot then inactive, overwritten by the creator).
               Nothing changes.
  Lost Children creator 0x44C600: head inherited and clamped 0..29 or rand(30) (0x44CC25), body rand(30)
               (0x44CC35), a new village's fixed lists then an out-of-range re-roll rand(30) (0x44CCBB,
               0x44CCDA); the roster reset rand(30) (0x424F3F, 0x424F53); "A Mysterious Vial" (green): a
               man rand(29) (0x4395ED, 0x43968F) -- CHANGED to rand(30) -- a woman rand(30) (0x4396BC, 0x4396E9).
  Secret City  creator 0x456120: head inherited/clamped or rand(30) (0x4564FE), body rand(29) (0x456520):
               body 29 is the Tribal Chief's robe, so it stays; the obsidian vial's head rand(30) (0x417634).
               Nothing changes.
  Tree of Life creator 0x45EF10: head inherited/clamped or rand(30) (0x45F28C), body rand(29) (0x45F2AE) --
               CHANGED to rand(30); the fixed lists behind the 14th argument are never reached (every caller
               passes 0).
  New Believers creator 0x4681F0: head inherited/clamped or rand(30) (0x468591), body rand(29) (0x4685B3) --
               CHANGED to rand(30); fixed lists as The Tree of Life.

This file runs each changed roll in an emulator on the stock executable with the companion installed (every
bound the game passes, every answer the game's rand can give: each row 0 to 29 comes out, 29 included) and
without it (0 to 28), and the rolls that stay (The Secret City's body, A New Home's boys) with the companion
started for that game: unchanged.  tests/test_companion_installs_all_or_none.py runs its all-or-none install.
"""
from __future__ import annotations

import functools
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile  # noqa: F401
    from story_emulator import STACK_TOP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False
    STACK_TOP = 0

DLL_NAME = "VVFP Appearance Rolls.dll"
DLL = ROOT / "assets" / "appearance_rolls" / DLL_NAME
MODES = ("stock", "collection_progression", "immediate_fixed")
RAND = {1: 0x402F10, 2: 0x4031A0, 3: 0x4032D0, 4: 0x4036D0, 5: 0x403660}


@functools.lru_cache(maxsize=None)
def _builds():
    return {b.id: b for b in patcher.load_builds()}


def stock_path(game: int) -> Path:
    return ROOT / "inputs" / f"vv{game}-stock-copy" / _builds()[f"vv{game}"].input_name


@functools.lru_cache(maxsize=None)
def render(game: int, ids: tuple[str, ...], mode: str) -> bytes:
    data, _ = patcher.render_patched_bytes(stock_path(game), _builds()[f"vv{game}"], mode, list(ids))
    return bytes(data)


def have(*games: int) -> bool:
    return HAVE_EMULATOR and DLL.is_file() and all(stock_path(g).is_file() for g in games)


class Roll:
    """One roll site run in the emulator: from the push of the bound to just after the store."""

    def __init__(self, game: int, exe: bytes, *, dll: bool):
        self.game = game
        self.p = Process(exe, DLL if dll else None)
        self.installed = None
        if dll:
            self.p.export("VvfpStartup", game, 0)
            self.installed = self.p.export("VvfpAppearanceRollsInstalled")
        self.bounds: list[int] = []
        self.answer = 0
        self.p.stub(RAND[game], self._rand)
        self.records = self.p.alloc(0x10000)
        self.manager = self.p.alloc(0x10000)

    def _rand(self, p):
        bound = p.arg(0)
        self.bounds.append(bound)
        assert 0 <= self.answer < bound, (self.answer, bound)
        return self.answer, 0

    def outcomes(self, start: int, until: int, field: int, *, sex: int = 1) -> tuple[list[int], set[int]]:
        """Every value the store can get: the roll run once for each answer rand can give."""
        seen: set[int] = set()
        bounds: list[int] = []
        answer = 0
        while True:
            self.bounds = []
            self.answer = answer
            esp = STACK_TOP - 0x4000
            self.p.set_reg("esp", esp)
            self.p.set_reg("esi", self.records)
            self.p.set_reg("edi", self.records + 0x1B8C)
            self.p.set_reg("ebp", self.manager)
            self.p.put32(self.manager + 0x5098, 0)                 # the event's villager index
            self.p.put32(self.manager + 0x50AC, self.records)      # the villager array
            self.p.put32(self.records + 0x538, sex)
            self.p.run(start, until)
            bounds += self.bounds
            seen.add(self.p.u32(self.records + field))
            answer += 1
            if answer >= self.bounds[0]:
                return sorted(set(bounds)), seen


# The changed rolls: (game, start, until, field written).
CHANGED = {
    2: ((0x4395ED, 0x439612, 0x548), (0x43968F, 0x4396B4, 0x548)),   # the green vial, a man's new head
    4: ((0x45F2AE, 0x45F2C5, 0x1BBC),),                              # the creator's body
    5: ((0x4685B3, 0x4685CA, 0x1BBC),),
}


def _skip(*games):
    return unittest.skipUnless(have(*games), "unicorn/pefile, the stock executables or the DLL is missing")


class RowTests(unittest.TestCase):
    def rows(self):
        return {p.id: p.raw for p in patcher.load_fun_patches()}

    def test_the_three_rows_ship_the_companion_and_say_so(self):
        rows = self.rows()
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper() if DLL.is_file() else None
        for game in (2, 4, 5):
            row = rows[f"vv{game}_fix_vanilla_bugs"]
            with self.subTest(game=game):
                files = [f for f in row["companion_files"] if f["destination"] == DLL_NAME]
                self.assertEqual(len(files), 1)
                if sha:
                    self.assertEqual(files[0]["sha256"], sha)
                self.assertTrue(row["description"].endswith("**Needs no other patch.**"))
                self.assertIn("head 29" if game == 2 else "body 29", row["description"])
                sites = [d for d in row["runtime_detours"] if d["installed_by"].startswith(DLL_NAME)]
                self.assertEqual(len(sites), len(CHANGED[game]))
                for site in sites:
                    self.assertEqual(site["stock_bytes"][:-2], site["written_bytes"][:-2])
                    self.assertEqual((site["stock_bytes"][-4:], site["written_bytes"][-4:]), ("6A1D", "6A1E"))

    def test_a_new_home_and_the_secret_city_get_no_line(self):
        rows = self.rows()
        for game in (1, 3):
            raw = rows[f"vv{game}_fix_vanilla_bugs"]
            self.assertNotIn(DLL_NAME, str(raw.get("companion_files", [])), game)

    def test_the_startup_loader_starts_it_from_the_second_word(self):
        self.assertIn(DLL_NAME, patcher.STARTUP_LOADER_COMPANIONS_2)
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertLess(header.index("VVFP VV1 Genetics.dll"), header.index(DLL_NAME))   # append only


@_skip(2, 4, 5)
class ChangedRolls(unittest.TestCase):
    def test_with_the_fix_every_row_comes_out_the_last_included(self):
        for game, sites in CHANGED.items():
            for start, until, field in sites:
                with self.subTest(game=game, site=hex(start)):
                    roll = Roll(game, stock_path(game).read_bytes(), dll=True)
                    self.assertEqual(roll.installed, 1)
                    bounds, seen = roll.outcomes(start, until, field)
                    self.assertEqual(bounds, [30])
                    self.assertEqual(seen, set(range(30)))

    def test_without_it_the_last_row_never_comes_out(self):
        for game, sites in CHANGED.items():
            for start, until, field in sites:
                with self.subTest(game=game, site=hex(start)):
                    bounds, seen = Roll(game, stock_path(game).read_bytes(), dll=False).outcomes(start, until, field)
                    self.assertEqual(bounds, [29])
                    self.assertEqual(seen, set(range(29)))

    def test_a_woman_drinking_the_green_vial_is_unchanged(self):
        for dll in (False, True):
            roll = Roll(2, stock_path(2).read_bytes(), dll=dll)
            for start, until in ((0x4396BC, 0x4396E1), (0x4396E9, 0x43970E)):
                bounds, seen = roll.outcomes(start, until, 0x548, sex=2)
                self.assertEqual((bounds, seen), ([30], set(range(30))), (dll, hex(start)))

    def test_the_fix_row_renders_the_sites_stock_in_every_mode_and_installs(self):
        for game, sites in CHANGED.items():
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    exe = render(game, (f"vv{game}_fix_vanilla_bugs",), mode)
                    roll = Roll(game, exe, dll=True)
                    self.assertEqual(roll.installed, 1)
                    for start, until, field in sites:
                        self.assertEqual(roll.outcomes(start, until, field), ([30], set(range(30))))

    def test_a_changed_site_that_is_not_stock_installs_nothing(self):
        exe = bytearray(stock_path(2).read_bytes())
        self.assertEqual(exe[0x39690], 0x1D)
        exe[0x39690] = 0x1C                            # the second vial site only (file offset == RVA in VV2)
        roll = Roll(2, bytes(exe), dll=True)
        self.assertEqual(roll.installed, 0)
        self.assertEqual(roll.outcomes(0x4395ED, 0x439612, 0x548), ([29], set(range(29))))


@_skip(1, 3)
class RollsThatStay(unittest.TestCase):
    def test_the_secret_citys_body_stays_0_to_28(self):
        for dll in (False, True):
            roll = Roll(3, stock_path(3).read_bytes(), dll=dll)
            if dll:
                self.assertEqual(roll.installed, 0)
            self.assertEqual(roll.outcomes(0x456520, 0x45652D, 0xDF4), ([29], set(range(29))), dll)

    def test_a_new_home_boys_never_roll_row_19_and_girls_reach_it(self):
        for dll in (False, True):
            roll = Roll(1, stock_path(1).read_bytes(), dll=dll)
            if dll:
                self.assertEqual(roll.installed, 0)
            for sex, n in ((1, 19), (2, 20)):
                roll.p.put32(roll.records + 0x350, sex)
                heads, bodies = set(), set()
                for answer in range(n):
                    roll.answer = answer
                    roll.bounds = []
                    roll.p.set_reg("esp", STACK_TOP - 0x4000)
                    roll.p.set_reg("esi", roll.records)
                    roll.p.run(0x43C616, 0x43C64D)                   # sex test, body roll, head roll
                    self.assertEqual(roll.bounds, [n, n], (dll, sex))
                    heads.add(roll.p.u32(roll.records + 0x360))
                    bodies.add(roll.p.u32(roll.records + 0x364))
                self.assertEqual((heads, bodies), (set(range(n)), set(range(n))), (dll, sex))

    def test_a_new_home_vial_keeps_a_man_off_row_19(self):
        roll = Roll(1, stock_path(1).read_bytes(), dll=True)
        self.assertEqual(roll.installed, 0)
        for va in (0x42C92D, 0x42C9C9):                                  # a man: rand(19)
            self.assertEqual(roll.p.read(va, 7), b"\x6a\x13\xe8" + roll.p.read(va + 3, 4))
        for va in (0x42C9F6, 0x42CA23):                                  # a woman: rand(20)
            self.assertEqual(roll.p.read(va, 2), b"\x6a\x14")


if __name__ == "__main__":
    unittest.main()
