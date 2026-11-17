"""The five 0.1x-10x sliders (the owner, 2026-11-17; all five games, 1 the normal game, 1 unless moved):
Collectible and Mushroom Frequency, Food Gained per Food Source, Tech Point Gain Rate, Skill Practice Success Chance
and Age and Nursing Timer Speed.

STOCK.  Every site each companion writes is read from the stock executables: the rand calls of the appearance and
skill rolls, the food and tech point writers' calls, the age clock's add (and nothing else of the repo's patches or
companions writes a byte of them, apart from the optional sites another row owns).

EMULATED, on the executable the patcher renders for the row: each companion is started as VVFP More Companions.dll
starts it, with the slider's number in its .txt in the patcher's folder; then every site is run with the game's own
routine behind it (rand, the writer) replaced by a stand-in that reports what it was handed:
  * a roll comes back (10 r + u) / tenths for some u of 0..9 (from the top in A New Home's mushroom roll), the game's
    rand drawn exactly once, ecx and edx as rand left them; over every roll of rand(100) the skill check passes N
    times as often;
  * a positive food or tech amount reaches the writer as A x N (the rest a chance; on average exact), a negative or
    zero one as it was, ecx (the store) and the return address the game's own;
  * the age clock gets the seconds x N (on average), the rest of the add as the game's own.
At 1x, with no file, in another game, or with a required site not stock, nothing is installed.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path, with_requirements
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

import build_new_slider_features as gen  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402

GAMES = (1, 2, 3, 4, 5)
FAKE_FILE = 0x0000F00D
DLLS = {key: ROOT / "assets" / asset / dll for key, (_s, _n, dll, asset, _t) in gen.SLIDERS.items()}


def row_id(key: str, game: int) -> str:
    return f"vv{game}{gen.SLIDERS[key][0]}"


def have_stock() -> bool:
    return HAVE_EMULATOR and all(stock_path(g).is_file() for g in GAMES)


def signed(value: int) -> int:
    return struct.unpack("<i", struct.pack("<I", value & 0xFFFFFFFF))[0]


class Stock(unittest.TestCase):
    def setUp(self) -> None:
        if not have_stock():
            self.skipTest("stock executables or the emulator not present")

    def call_target(self, data: bytes, va: int) -> int | None:
        o = va - 0x400000
        if data[o] != 0xE8:
            return None
        return va + 5 + struct.unpack_from("<i", data, o + 1)[0]

    def test_every_call_site_calls_what_the_companion_expects(self) -> None:
        for game in GAMES:
            data = stock_path(game).read_bytes()
            with self.subTest(game=game):
                for va, _w, _o in gen.COLLECT_SITES[game]:
                    self.assertEqual(self.call_target(data, va), gen.RAND[game])
                for va in gen.SKILL_SITES[game]:
                    self.assertEqual(self.call_target(data, va), gen.RAND[game])
                    # push 100 just before.
                    self.assertIn(b"\x6A\x64", data[va - 0x400000 - 12:va - 0x400000])
                for va, _w, _o in gen.FOOD_SITES[game]:
                    if va != 0x434C77:      # only a call with Fruit is Harvested at the Food Bin
                        self.assertEqual(self.call_target(data, va), gen.FOOD_WRITER[game], hex(va))
                for va, _w in gen.TECH_SITES[game]:
                    self.assertEqual(self.call_target(data, va), gen.TECH_WRITER[game], hex(va))
                va, stock, _text = gen.AGE_SITES[game]
                self.assertEqual(data[va - 0x400000:va - 0x400000 + len(stock) // 2].hex().upper(), stock)

    def test_the_tables_are_the_companions_own(self) -> None:
        sources = {key: (ROOT / "native" / f"vvfp_{asset}" / f"vvfp_{asset}.c").read_text("utf-8")
                   for key, (_s, _n, _d, asset, _t) in gen.SLIDERS.items()}
        for game in GAMES:
            with self.subTest(game=game):
                for va, _w, optional in gen.COLLECT_SITES[game]:
                    self.assertIn(f"{{ 0x{va:X}u, {int(optional)} }}", sources["collectible_frequency"])
                for va in gen.SKILL_SITES[game]:
                    self.assertIn(f"{{ 0x{va:X}u, 0 }}", sources["skill_success"])
                for va, _w, optional in gen.FOOD_SITES[game]:
                    self.assertIn(f"{{ 0x{va:X}u, {int(optional)} }}", sources["food_gain"])
                for va, _w in gen.TECH_SITES[game]:
                    self.assertIn(f"{{ 0x{va:X}u, 0 }}", sources["tech_gain"])
                self.assertIn(f"{{ {game}, 0x{gen.AGE_SITES[game][0]:X}u,", sources["age_speed"])

    def test_no_other_patch_writes_a_required_site(self) -> None:
        sites = []
        for game in GAMES:
            sites += [(game, va, 5) for va, _w, _o in gen.COLLECT_SITES[game]]
            sites += [(game, va, 5) for va in gen.SKILL_SITES[game]]
            sites += [(game, va, 5) for va, _w, optional in gen.FOOD_SITES[game] if not optional]
            sites += [(game, va, 5) for va, _w in gen.TECH_SITES[game]]
            va, stock, _t = gen.AGE_SITES[game]
            sites.append((game, va, len(stock) // 2))
        for feature in patcher.load_fun_patches():
            game = int(feature.id[2]) if re.match(r"vv[1-5]_", feature.id) else None
            for p in feature.raw.get("patches", []):
                start = int(p["offset"], 16) + 0x400000
                end = start + len(p["after"]) // 2
                for g, va, n in sites:
                    if g == game:
                        with self.subTest(row=feature.id, site=hex(va)):
                            self.assertTrue(end <= va or va + n <= start)
            for d in feature.raw.get("runtime_detours", []):
                if feature.id.endswith(tuple(s[0] for s in gen.SLIDERS.values())):
                    continue
                start = int(d["va"], 16)
                end = start + len(d.get("stock_bytes", "")) // 2
                for g, va, n in sites:
                    if g == game:
                        with self.subTest(row=feature.id, site=hex(va)):
                            self.assertTrue(end <= va or va + n <= start)


class _Emulated:
    KEY = ""

    def setUp(self) -> None:
        if not have_stock():
            self.skipTest("stock executables or the emulator not present")
        if not DLLS[self.KEY].is_file():
            self.skipTest("companion not built")

    def machine(self, game: int, setting: bytes | None, rows: list[str] | None = None) -> "Machine":
        choice = gen.SLIDERS[self.KEY][2][:-4] + ".txt"
        m = Machine(render(game, with_requirements(game, rows or [row_id(self.KEY, game)]), "stock"), DLLS[self.KEY])
        opened: list[str] = []

        def open_(p):
            path = p.wstring(p.arg(0))
            opened.append(path)
            ok = setting is not None and path.endswith("\\Virtual Villagers Fun Patcher Files\\" + choice)
            return (FAKE_FILE if ok else 0xFFFFFFFF), 28

        def read(p):
            if p.arg(0) != FAKE_FILE:
                return 0, 20
            data = (setting or b"")[:p.arg(2)]
            p.write(p.arg(1), data)
            p.put32(p.arg(3), len(data))
            return 1, 20

        m.api_handlers["CreateFileW"] = open_
        m.api_handlers["ReadFile"] = read
        m.api_handlers["CloseHandle"] = lambda p: (1, 4)
        m.api_handlers["GetCurrentProcessId"] = lambda p: (0x1234, 0)
        m.opened = opened
        return m

    def start(self, m: "Machine", game: int) -> int:
        m.export("VvfpStartup", game, 0)
        prefix = "Vvfp" + "".join(w.capitalize() for w in self.KEY.split("_"))
        return m.export(prefix + "Installed")

    def sites(self, game: int) -> list[tuple[int, int]]:
        raise NotImplementedError

    def test_nothing_at_1x_without_a_file_in_another_game_or_off_stock(self) -> None:
        for game in GAMES:
            for setting in (b"1", b"1.0\n", None, b"", b"abc"):
                with self.subTest(game=game, setting=setting):
                    m = self.machine(game, setting)
                    before = [m.read(va, n) for va, n in self.sites(game)]
                    self.assertEqual(self.start(m, game), 0)
                    self.assertEqual([m.read(va, n) for va, n in self.sites(game)], before)
        m = self.machine(3, b"2")
        self.assertEqual(self.start(m, 6), 0)
        m = self.machine(3, b"2")
        first = self.sites(3)[0][0]
        m.write(first, b"\x90")
        before = [m.read(va, n) for va, n in self.sites(3)]
        self.assertEqual(self.start(m, 3), 0)
        self.assertEqual([m.read(va, n) for va, n in self.sites(3)], before)

    def test_the_setting_file(self) -> None:
        prefix = "Vvfp" + "".join(w.capitalize() for w in self.KEY.split("_"))
        for setting, tenths in ((b"2", 20), (b"0.5\n", 5), (b"10", 100), (b"11", 100), (b"0", 1), (b"0.05", 1),
                                (b"2.5", 25), (b" 3 ", 30)):
            with self.subTest(setting=setting):
                m = self.machine(4, setting)
                self.assertEqual(self.start(m, 4), 1)
                self.assertEqual(m.export(prefix + "Tenths"), tenths)


class RollCompanions:
    """Shared by the two roll companions."""

    def roll_sites(self, game: int) -> list[int]:
        raise NotImplementedError

    def sites(self, game: int) -> list[tuple[int, int]]:
        return [(va, 5) for va in self.roll_sites(game)]

    def roll(self, m: "Machine", game: int, va: int, r: int) -> int:
        calls = []

        def rand(p):
            calls.append(p.arg(0))
            p.set_reg("ecx", 0x2C2C2C2C)
            p.set_reg("edx", 0x2D2D2D2D)
            return r, 0

        m.stubs[gen.RAND[game]] = rand
        for name, value in (("ebx", 0x11111111), ("esi", 0x44444444), ("edi", 0x55555555), ("ebp", 0x66666666)):
            m.set_reg(name, value)
        m.set_reg("ecx", 0x22222222)
        m.set_reg("edx", 0x33333333)
        esp = m.reg("esp") - 0x40
        m.set_reg("esp", esp)
        modulus = 100 if va in gen.SKILL_SITES[game] else (120 if game == 1 else 100 if game == 2 else 6000)
        m.put32(esp, modulus)              # the game's `push M` (the caller pops it after the call)
        m.run(va, va + 5)
        self.assertEqual(calls, [modulus], "the game's rand drawn exactly once, with its own M")
        self.assertEqual(m.reg("esp"), esp)
        self.assertEqual((m.reg("ecx"), m.reg("edx")), (0x2C2C2C2C, 0x2D2D2D2D))
        self.assertEqual([m.reg(n) for n in ("ebx", "esi", "edi", "ebp")],
                         [0x11111111, 0x44444444, 0x55555555, 0x66666666])
        return signed(m.reg("eax"))


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class CollectibleFrequency(RollCompanions, _Emulated, unittest.TestCase):
    KEY = "collectible_frequency"

    def roll_sites(self, game: int) -> list[int]:
        return [va for va, _w, _o in gen.COLLECT_SITES[game]]

    def test_the_roll_is_scaled(self) -> None:
        for game in GAMES:
            modulus = {1: 120, 2: 100}.get(game, 6000)
            for n in ("2", "0.5", "10", "0.1", "3.7"):
                tenths = round(float(n) * 10)
                with self.subTest(game=game, n=n):
                    m = self.machine(game, n.encode())
                    self.assertEqual(self.start(m, game), 1)
                    for va in self.roll_sites(game):
                        for r in (0, 1, 2, 3, 57, modulus - 2, modulus - 1):
                            got = self.roll(m, game, va, r)
                            if game == 1:
                                d = modulus - 1 - r
                                self.assertIn(got, {modulus - 1 - (10 * d + u) // tenths for u in range(10)})
                            else:
                                self.assertIn(got, {(10 * r + u) // tenths for u in range(10)})

    def test_a_new_home_passes_n_times_as_often(self) -> None:
        # rand(120) > 117: 2 of 120 normally; at 2, 4 of 120 on average over every roll.
        m = self.machine(1, b"2")
        self.assertEqual(self.start(m, 1), 1)
        passed = sum(self.roll(m, 1, 0x423516, r) > 117 for r in range(120) for _ in range(5))
        self.assertEqual(passed, 20)


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class SkillSuccess(RollCompanions, _Emulated, unittest.TestCase):
    KEY = "skill_success"

    def roll_sites(self, game: int) -> list[int]:
        return gen.SKILL_SITES[game]

    def test_the_check_passes_n_times_as_often(self) -> None:
        # Over every roll of rand(100), a check passing at r <= T passes (T + 1) x N times in 100 (all at most).
        for game in GAMES:
            for n, threshold in (("2", 30), ("0.5", 59), ("0.1", 99), ("3", 40)):
                tenths = round(float(n) * 10)
                with self.subTest(game=game, n=n):
                    m = self.machine(game, n.encode())
                    self.assertEqual(self.start(m, game), 1)
                    va = gen.SKILL_SITES[game][0]
                    rolls = [self.roll(m, game, va, r) for r in range(100) for _ in range(10)]
                    passed = sum(r <= threshold for r in rolls)
                    self.assertEqual(passed, min(1000, (threshold + 1) * tenths))
                    for other in gen.SKILL_SITES[game][1:]:
                        self.assertIn(self.roll(m, game, other, 50), {(500 + u) // tenths for u in range(10)})


class GainCompanions:
    SITES: dict = {}
    WRITER: dict = {}

    def sites(self, game: int) -> list[tuple[int, int]]:
        return [(va, 5) for va, *rest in self.SITES[game] if not (rest[1:] and rest[1])]

    def gain(self, m: "Machine", game: int, va: int, amount: int) -> tuple[int, int, int]:
        seen = []

        def writer(p):
            seen.append((signed(p.arg(0)), p.reg("ecx"), p.u32(p.reg("esp"))))
            return 0, 4

        m.stubs[self.WRITER[game]] = writer
        m.set_reg("ecx", 0x5A5A5A5A)
        esp = m.reg("esp") - 0x40
        m.set_reg("esp", esp)
        m.put32(esp, amount)
        m.run(va, va + 5)
        self.assertEqual(len(seen), 1)
        self.assertEqual(m.reg("esp"), esp + 4, "the writer popped its argument (ret 4)")
        return seen[0]

    def test_gains_are_scaled_and_go_on_into_the_writer(self) -> None:
        for game in GAMES:
            for n in ("2", "0.5", "0.1", "10", "1.5"):
                tenths = round(float(n) * 10)
                with self.subTest(game=game, n=n):
                    m = self.machine(game, n.encode())
                    self.assertEqual(self.start(m, game), 1)
                    for va, _n in self.sites(game):
                        for amount in (7, 55, 1):
                            got, ecx, ret = self.gain(m, game, va, amount)
                            low = amount * tenths // 10
                            self.assertIn(got, {low, low + (1 if amount * tenths % 10 else 0)})
                            self.assertEqual((ecx, ret), (0x5A5A5A5A, va + 5))
                        for amount in (0, -5):
                            self.assertEqual(self.gain(m, game, va, amount)[0], amount)

    def test_on_average_it_is_exact(self) -> None:
        m = self.machine(4, b"0.3")
        self.assertEqual(self.start(m, 4), 1)
        va = self.sites(4)[0][0]
        total = sum(self.gain(m, 4, va, 7)[0] for _ in range(1000))
        self.assertAlmostEqual(total / 1000, 2.1, delta=0.12)


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class FoodGain(GainCompanions, _Emulated, unittest.TestCase):
    KEY = "food_gain"
    SITES = {g: [(va, w, o) for va, w, o in s] for g, s in gen.FOOD_SITES.items()}
    WRITER = gen.FOOD_WRITER

    def sites(self, game: int) -> list[tuple[int, int]]:
        return [(va, 5) for va, _w, optional in self.SITES[game] if not optional]

    def test_optional_sites_follow_the_rows_that_own_them(self) -> None:
        # Stock: every optional site that holds the call is written too; The Secret City's food-bin call is not a
        # call of the writer there, so it is left.
        m = self.machine(4, b"2")
        self.assertEqual(self.start(m, 4), 1)
        chosen = [m.export("VvfpFoodGainSite", i) for i in range(len(gen.FOOD_SITES[4]))]
        self.assertEqual(chosen, [1] * len(gen.FOOD_SITES[4]))
        m = self.machine(3, b"2")
        self.assertEqual(self.start(m, 3), 1)
        chosen = [m.export("VvfpFoodGainSite", i) for i in range(len(gen.FOOD_SITES[3]))]
        self.assertEqual(chosen, [0 if va == 0x434C77 else 1 for va, _w, _o in gen.FOOD_SITES[3]])
        # Another row owns an optional site: it is left alone and the rest still go in.
        m = self.machine(2, b"2")
        m.write(0x4633CD, bytes.fromhex("E8330A0100"))     # Super-Secret Golden Mushroom's call
        self.assertEqual(self.start(m, 2), 1)
        self.assertEqual(m.read(0x4633CD, 5), bytes.fromhex("E8330A0100"))
        self.assertEqual([m.export("VvfpFoodGainSite", i) for i in range(5)], [1, 1, 1, 1, 0])


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class TechGain(GainCompanions, _Emulated, unittest.TestCase):
    KEY = "tech_gain"
    SITES = {g: [(va, w, False) for va, w in s] for g, s in gen.TECH_SITES.items()}
    WRITER = gen.TECH_WRITER

    def sites(self, game: int) -> list[tuple[int, int]]:
        return [(va, 5) for va, _w, _o in self.SITES[game]]


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class AgeSpeed(_Emulated, unittest.TestCase):
    KEY = "age_speed"

    def sites(self, game: int) -> list[tuple[int, int]]:
        va, stock, _t = gen.AGE_SITES[game]
        return [(va, len(stock) // 2)]

    def tick(self, m: "Machine", game: int, now: int, stamp: int, uncounted: int) -> int:
        """The site run once: the villager's uncounted seconds after it."""
        va, n = self.sites(game)[0]
        rec = m.alloc(0x4000) + 0x2000
        m.set_reg("eax", now)
        m.set_reg("ebx", 0x11111111)
        if game == 1:
            m.set_reg("ecx", rec)
            m.put32(rec + 0x340, stamp)
            m.set_reg("ebx", uncounted)
            m.run(va, va + n)
            self.assertEqual(m.reg("ecx"), rec)
            return (m.reg("ebx") + m.reg("eax")) & 0xFFFFFFFF   # the stock `add ebx, eax` that follows
        if game == 2:
            m.set_reg("ebp", rec)
            m.set_reg("edx", stamp)
            m.set_reg("ecx", uncounted)
            m.run(va, va + n)
            self.assertEqual(m.reg("ecx"), m.u32(rec + 0x524))
            self.assertEqual(m.reg("edx"), stamp)
            return m.u32(rec + 0x524)
        m.set_reg("edi", stamp)
        if game == 3:
            m.set_reg("edx", uncounted)
            m.set_reg("ecx", 0x22222222)
            m.run(va, va + n)
            self.assertEqual((m.reg("eax"), m.reg("ecx")), (0x15180, 0x22222222))
            return m.reg("edx")
        m.set_reg("esi", rec)
        field = rec - 0x93 if game == 4 else rec + 0x1C34
        m.put32(field, uncounted)
        m.run(va, va + n)
        self.assertEqual((m.reg("esi"), m.reg("edi")), (rec, stamp))
        return m.u32(field)

    def test_the_seconds_are_scaled(self) -> None:
        for game in GAMES:
            for n in ("2", "0.5", "10", "0.1", "1.5"):
                tenths = round(float(n) * 10)
                with self.subTest(game=game, n=n):
                    m = self.machine(game, n.encode())
                    self.assertEqual(self.start(m, game), 1)
                    for seconds in (0, 1, 7, 3600, 100_000):
                        got = self.tick(m, game, 2_000_000_000, 2_000_000_000 - seconds, 500) - 500
                        low = seconds * tenths // 10
                        self.assertIn(got, {low, low + (1 if seconds * tenths % 10 else 0)})

    def test_on_average_it_is_exact(self) -> None:
        m = self.machine(5, b"0.3")
        self.assertEqual(self.start(m, 5), 1)
        total = sum(self.tick(m, 5, 1000, 999, 0) for _ in range(1000))
        self.assertAlmostEqual(total / 1000, 0.3, delta=0.06)


class Rows(unittest.TestCase):
    def test_each_row_is_what_the_generator_writes(self) -> None:
        for key, (_s, _n, dll, asset, _t) in gen.SLIDERS.items():
            path = ROOT / "assets" / asset / dll
            if not path.is_file():
                self.skipTest("companion not built")
            for game in GAMES:
                with self.subTest(key=key, game=game):
                    record = json.loads((ROOT / "data" / f"{row_id(key, game)}_feature.json").read_text("utf-8"))
                    self.assertEqual(record, gen.row(key, game, gen.sha(path)))

    def test_rows_off_by_default_on_in_owners_defaults(self) -> None:
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        for slider in patcher.RUNTIME_SLIDERS:
            for game in GAMES:
                with self.subTest(slider=slider.key, game=game):
                    row = public[f"vv{game}{slider.row_suffix}"]
                    self.assertEqual(row.name, slider.name)
                    self.assertEqual([c["destination"] for c in row.raw["companion_files"]], [slider.dll])
                    self.assertEqual(row.raw["patches"], [])
                    self.assertIn("**Needs no other patch.**", row.raw["description"])
                    self.assertFalse(default_fun_patch_selection(row.id))
                    self.assertTrue(owners_default_fun_patch_selection(row.id))
                    self.assertFalse(select_all_fun_patch_selection(row.id))

    def test_the_tables_agree(self) -> None:
        import transparency
        self.assertEqual([(s.key, s.row_suffix, s.name, s.dll) for s in patcher.RUNTIME_SLIDERS],
                         [(k, v[0], v[1], v[2]) for k, v in gen.SLIDERS.items()])
        self.assertEqual({s.row_suffix: (s.key, s.name, s.meaning) for s in patcher.RUNTIME_SLIDERS},
                         transparency.RUNTIME_SLIDER_LINES)
        self.assertEqual(list(patcher.STARTUP_LOADER_COMPANIONS_3[1:6]), [s.dll for s in patcher.RUNTIME_SLIDERS])
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text("utf-8")
        self.assertEqual(re.findall(r'^    "(VVFP [^"]+\.dll)",', header, re.M), list(patcher.STARTUP_LOADER_COMPANIONS_3))
        for s in patcher.RUNTIME_SLIDERS:
            self.assertEqual(s.choice_file, s.dll[:-4] + ".txt")
            self.assertIn(f'"{s.choice_file}"', (ROOT / "native" / f"vvfp_{s.key}" / f"vvfp_{s.key}.c").read_text("utf-8"))
            release = (ROOT / "scripts" / "build_release.py").read_text("utf-8")
            self.assertIn(f'"assets/{s.key}/{s.dll}"', release)
            for game in GAMES:
                self.assertIn(f'"data/vv{game}{s.row_suffix}_feature.json"', release)


class Setting(unittest.TestCase):
    def setUp(self) -> None:
        for s in patcher.RUNTIME_SLIDERS:
            self.addCleanup(patcher.set_runtime_slider_multiplier, s.key, patcher.runtime_slider_multiplier(s.key))

    def test_a_tenth_to_10_default_1(self) -> None:
        r = patcher.RUNTIME_SLIDER_RANGE
        self.assertEqual((r[0], r[-1], len(r), patcher.RUNTIME_SLIDER_DEFAULT), (0.1, 10, 100, 1))
        for s in patcher.RUNTIME_SLIDERS:
            for good in (0.1, 1, 2.5, 10):
                self.assertEqual(patcher.set_runtime_slider_multiplier(s.key, good), good)
            for bad in (0, 10.1, 11, 0.05, "2", True, None):
                with self.subTest(key=s.key, bad=bad), self.assertRaises(patcher.PatcherError):
                    patcher.set_runtime_slider_multiplier(s.key, bad)

    def test_written_beside_the_companion_only_with_the_row(self) -> None:
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        for s in patcher.RUNTIME_SLIDERS:
            for n in (2, 0.5, 10, 1):
                with tempfile.TemporaryDirectory() as out, self.subTest(key=s.key, n=n):
                    patcher.set_runtime_slider_multiplier(s.key, n)
                    patcher._write_runtime_slider_choices(Path(out), [public["vv3_children_play"]])
                    self.assertEqual(list(Path(out).rglob(s.choice_file)), [])
                    patcher._write_runtime_slider_choices(Path(out), [public[f"vv3{s.row_suffix}"]])
                    beside = Path(out) / Path(*patcher.patcher_files.installed_relative_path(s.dll).parts).parent \
                        / s.choice_file
                    self.assertEqual(list(Path(out).rglob(s.choice_file)), [beside])
                    self.assertEqual(beside.read_bytes(), f"{n}\n".encode())
                    self.assertEqual(patcher._runtime_sliders_in([public[f"vv3{s.row_suffix}"]]),
                                     {f"{s.key}_multiplier": n})

    def test_the_command_line(self) -> None:
        import argparse
        parser = argparse.ArgumentParser()
        patcher._add_check_logs_arg(parser)
        for s in patcher.RUNTIME_SLIDERS:
            flag = f"--{s.key.replace('_', '-')}-multiplier"
            self.assertIsNone(getattr(parser.parse_args([]), f"{s.key}_multiplier"))
            self.assertEqual(getattr(parser.parse_args([flag, "0.5"]), f"{s.key}_multiplier"), 0.5)
            for bad in ("0", "11", "0.05"):
                with self.subTest(flag=flag, bad=bad), self.assertRaises(SystemExit):
                    parser.parse_args([flag, bad])

    def test_the_gui_restores_and_clamps(self) -> None:
        import vv_fun_patcher_gui as gui
        for s in patcher.RUNTIME_SLIDERS:
            key = f"{s.key}_multiplier"
            for saved, restored in ((2, 2), (0.5, 0.5), (50, 10), (0, 0.1), ("x", 1), (None, 1)):
                self.assertEqual(gui.saved_runtime_slider_multiplier({key: saved}, s.key), restored)
            self.assertEqual(gui.saved_runtime_slider_multiplier({}, s.key), 1)


if __name__ == "__main__":
    unittest.main()
