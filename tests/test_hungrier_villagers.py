"""Hungrier Villagers (0.1-10x Meals) (all five games) and Classic VV Difficulty (The Tree of Life, New Believers).
The traces are in scripts/build_hungrier_villagers_features.py and scripts/build_classic_vv_difficulty_features.py.

  * Each game's two meal sites decode, patched at every N, to the same instruction taking 2 x N food.
  * The Secret City, The Tree of Life and New Believers: the game's own food-add routine run in unicorn with the
    multiplied meal never leaves food below 0, and takes exactly 2 x N above it.
  * A New Home and The Lost Children: the meal routine's own clamp after the two sites sets food to 0 when it is
    0 or less.
  * A published build writes x N at every site and its records say so; the slider, Owner's Defaults and Classic VV
    Difficulty's red title and dependencies.
  * The owner (2026-11-17): every slider goes less as well as more, 0.1 to 10 in tenths.  A multiplier whose 2 x N
    is whole food (0.5, 1.5 ...) is written in the bytes; any other (0.1, 0.3, 1.7 ...) leaves them at the normal -2
    and "VVFP Meal Scale.dll", emulated on the published executable, takes 2 x N food on average at both sites, with
    every register as the game left it and the game's own clamp after.
Tests that need the stock executables skip when they are absent.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402
from vv_fun_patcher_gui import (CLASSIC_DIFFICULTY_FUN_PATCH_IDS, OWNERS_DEFAULT_SLIDER, TITLE_COLOURS,  # noqa: E402
                                default_fun_patch_selection, owners_default_fun_patch_selection,
                                saved_meal_multiplier, select_all_fun_patch_selection)

try:
    import capstone
    import pefile
    from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE_TOOLS = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_TOOLS = False

STOCK_DIR = ROOT / "research" / "stock-executables"
NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
# The meal sites (instruction VA, length); VV3-VV5: the food-add routine and the food global; VV1/VV2: the clamp.
SITES = {1: [(0x42ECCC, 7), (0x42ED03, 7)], 2: [(0x43BAF9, 7), (0x43BB30, 7)], 3: [(0x460080, 2), (0x4600C4, 2)],
         4: [(0x4684C8, 2), (0x46850B, 2)], 5: [(0x472D9E, 2), (0x472DEF, 2)]}
FOOD_ADD = {3: (0x4263F0, 0x582490), 4: (0x41D920, 0x4D6DD0), 5: (0x41EB40, 0x51D34C)}
# The stock "plenty of food" notice the food-add routine calls when food is above 2,000 (three arguments, thiscall),
# for every meal with or without the patch: stubbed.
NOTICE = {3: 0x436E60, 4: 0x44B890, 5: 0x44E730}
CLAMP = {1: 0x42ED0C, 2: 0x43BB39}


def stock_path(game: int) -> Path:
    return STOCK_DIR / f"Virtual Villagers - {NAMES[game]}.exe"


def manifest(game: int) -> dict:
    return json.loads((ROOT / "data" / f"vv{game}_hungrier_villagers_feature.json").read_text("utf-8"))


def with_n(game: int, n: int) -> bytes:
    data = bytearray(stock_path(game).read_bytes())
    for p in manifest(game)["patches"]:
        at = int(p["offset"], 16)
        assert data[at] == int(p["before"], 16)
        data[at] = (-2 * n) & 0xFF
    return bytes(data)


def have_stock() -> bool:
    return all(stock_path(g).is_file() for g in NAMES)


@unittest.skipUnless(HAVE_TOOLS, "capstone / unicorn / pefile not installed")
class Meals(unittest.TestCase):
    def setUp(self) -> None:
        if not have_stock():
            self.skipTest("stock executables not present")

    def test_every_site_takes_two_times_n(self) -> None:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for game, sites in SITES.items():
            pe = pefile.PE(str(stock_path(game)), fast_load=True)
            for n in (*range(1, 11), 63, 64):
                data = stock_path(game).read_bytes() if n == 1 else with_n(game, n)
                for va, length in sites:
                    at = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
                    ins = next(md.disasm(data[at:at + length], va))
                    with self.subTest(game=game, n=n, va=hex(va)):
                        self.assertEqual(ins.size, length)
                        self.assertEqual(ins.mnemonic, "add" if game <= 2 else "push")
                        self.assertTrue(ins.op_str.endswith((f"-{2 * n}", f"-{2 * n:#x}")), ins.op_str)

    def test_the_food_add_routine_never_leaves_food_below_zero(self) -> None:
        for game, (routine, food) in FOOD_ADD.items():
            data = stock_path(game).read_bytes()
            pe = pefile.PE(data=data, fast_load=True)
            base = pe.OPTIONAL_HEADER.ImageBase
            uc = Uc(UC_ARCH_X86, UC_MODE_32)
            text = next(s for s in pe.sections if s.Name.startswith(b".text"))
            start = (base + text.VirtualAddress) & ~0xFFF
            uc.mem_map(start, ((base + text.VirtualAddress + text.Misc_VirtualSize + 0xFFF) & ~0xFFF) - start)
            uc.mem_write(base + text.VirtualAddress,
                         data[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData][:text.Misc_VirtualSize])
            page = food & ~0xFFF
            uc.mem_map(page, 0x1000)
            uc.mem_map(0x0100_0000, 0x10000)

            def notice(uc, address, size, _):
                esp = uc.reg_read(UC_X86_REG_ESP)
                uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(esp, 4))[0])
                uc.reg_write(UC_X86_REG_ESP, esp + 16)

            uc.hook_add(UC_HOOK_CODE, notice, begin=NOTICE[game], end=NOTICE[game])
            for n in (*range(2, 11), 64):
                for before in (0, 1, 2 * n - 1, 2 * n, 2 * n + 1, 500, 8_000):
                    uc.mem_write(food, struct.pack("<i", before))
                    esp = 0x0100_8000
                    uc.mem_write(esp, struct.pack("<II", 0x0100_F000, (-2 * n) & 0xFFFFFFFF))
                    uc.reg_write(UC_X86_REG_ESP, esp)
                    uc.reg_write(UC_X86_REG_ECX, food)
                    uc.emu_start(routine, 0x0100_F000, count=200)
                    after = struct.unpack("<i", uc.mem_read(food, 4))[0]
                    with self.subTest(game=game, n=n, before=before):
                        self.assertEqual(after, max(0, before - 2 * n))

    def test_a_new_home_and_the_lost_children_clamp_after_both_meals(self) -> None:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for game, clamp in CLAMP.items():
            pe = pefile.PE(str(stock_path(game)), fast_load=True)
            data = stock_path(game).read_bytes()
            at = pe.get_offset_from_rva(clamp - pe.OPTIONAL_HEADER.ImageBase)
            code = list(md.disasm(data[at:at + 0x20], clamp))[:4]
            field = SITES[game][0]
            meal = next(md.disasm(data[pe.get_offset_from_rva(field[0] - pe.OPTIONAL_HEADER.ImageBase):][:7], field[0]))
            slot = meal.op_str.split("[")[1].split("]")[0]
            with self.subTest(game=game):
                self.assertEqual((code[0].mnemonic, code[1].mnemonic), ("cmp", "jg"))
                self.assertIn(slot, code[0].op_str)
                self.assertEqual(code[3].mnemonic, "mov")
                self.assertIn(slot, code[3].op_str)        # food = ebx (0) when it is 0 or less
                # Both meal sites fall through (or jump) to the clamp: the second ends right before it.
                self.assertEqual(SITES[game][1][0] + 7 + 2, clamp)


@unittest.skipUnless(HAVE_TOOLS, "capstone / unicorn / pefile not installed")
class Publish(unittest.TestCase):
    def setUp(self) -> None:
        if not have_stock():
            self.skipTest("stock executables not present")

    def test_every_site_becomes_minus_two_n_and_its_record_says_so(self) -> None:
        builds = {b.id: b for b in patcher.load_builds()}
        for game in NAMES:
            ids = [f"vv{game}_hungrier_villagers"]
            # The slider's top is 10 (the owner, 2026-11-17): -20, far inside the meal's signed byte.
            for n, written in ((2, 2), (5, 5), (10, 10)):
                data, applied = patcher.render_patched_bytes(stock_path(game), builds[f"vv{game}"], "stock", ids)
                patcher.apply_meal_multiplier(data, f"vv{game}", n, applied)
                with self.subTest(game=game, n=n):
                    for p in manifest(game)["patches"]:
                        self.assertEqual(data[int(p["offset"], 16)], (-2 * written) & 0xFF)
                        self.assertGreaterEqual(-2 * written, -128)
                    self.assertEqual(patcher.meal_multiplier_applied(applied), written)

    def test_halves_are_written_in_the_bytes_and_other_tenths_leave_the_normal_meal(self) -> None:
        builds = {b.id: b for b in patcher.load_builds()}
        for game in NAMES:
            ids = [f"vv{game}_hungrier_villagers"]
            for n, food in ((0.5, 1), (1, 2), (1.5, 3), (0.1, 2), (0.3, 2), (1.7, 2), (9.5, 19), (9.9, 2)):
                data, applied = patcher.render_patched_bytes(stock_path(game), builds[f"vv{game}"], "stock", ids)
                patcher.apply_meal_multiplier(data, f"vv{game}", n, applied)
                with self.subTest(game=game, n=n):
                    for p in manifest(game)["patches"]:
                        self.assertEqual(data[int(p["offset"], 16)], (-food) & 0xFF)
                    self.assertEqual(patcher.meal_in_bytes(n), n in (0.5, 1, 1.5, 9.5))
                    self.assertEqual(patcher.meal_multiplier_applied(applied), min(n, 64))

    def test_out_of_range_is_refused(self) -> None:
        for bad in (0, 10.1, 100, 101, True, 0.05, "3"):
            with self.assertRaises(patcher.PatcherError):
                patcher.validate_meal_multiplier(bad)
        for good in (2, 10, 1, 0.1, 0.5, 2.0):
            self.assertEqual(patcher.validate_meal_multiplier(good), good)
        self.assertEqual(patcher.MEAL_MULTIPLIER_SAFE_MAXIMUM, 64)

    def test_the_companion_number_is_written_beside_it(self) -> None:
        import tempfile
        row = next(p for p in patcher.load_public_fun_patches() if p.id == "vv3_hungrier_villagers")
        self.assertEqual([c["destination"] for c in row.raw["companion_files"]], ["VVFP Meal Scale.dll"])
        for n in (0.3, 2, 0.5):
            with tempfile.TemporaryDirectory() as out, self.subTest(n=n):
                patcher._write_meal_scale_choice(Path(out), [row], n)
                beside = Path(out) / Path(*patcher.patcher_files.installed_relative_path(
                    "VVFP Meal Scale.dll").parts).parent / "VVFP Meal Scale.txt"
                self.assertEqual(beside.read_bytes(), f"{n}\n".encode())


class Registration(unittest.TestCase):
    def test_off_by_default_on_in_owners_defaults(self) -> None:
        public = {p.id for p in patcher.load_public_fun_patches()}
        for game in NAMES:
            patch_id = f"vv{game}_hungrier_villagers"
            self.assertIn(patch_id, public)
            self.assertFalse(default_fun_patch_selection(patch_id))
            self.assertTrue(owners_default_fun_patch_selection(patch_id))
            self.assertTrue(select_all_fun_patch_selection(patch_id))

    def test_the_slider_is_a_tenth_to_10_default_1(self) -> None:
        r = patcher.MEAL_MULTIPLIER_RANGE
        self.assertEqual((r[0], r[-1], len(r)), (0.1, 10, 100))
        self.assertEqual(patcher.MEAL_MULTIPLIER_DEFAULT, 1)   # the stock meals for players (the owner, 2026-11-27)
        self.assertEqual(saved_meal_multiplier({"meal_multiplier": 7}), 7)
        self.assertEqual(saved_meal_multiplier({"meal_multiplier": 100}), 10)      # an old 100 loads as 10
        self.assertEqual(saved_meal_multiplier({"meal_multiplier": 0.3}), 0.3)
        self.assertEqual(saved_meal_multiplier({"meal_multiplier": 101}), 10)
        for bad in ({}, {"meal_multiplier": True}, None):
            self.assertEqual(saved_meal_multiplier(bad), 1)

    def test_classic_ticks_the_harder_patches_and_owners_defaults_sets_sliders_to_2(self) -> None:
        """The owner (2026-11-07): "have the classic vv difficulty on default for owner's defaults! (set the
        sliders to 2x." -- and "make the text colored red for the classic vv difficulty patch titles"."""
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        # Island Events Scale With Population (the owner, 2026-11-12) is a member in both games.
        pieces = {"vv4": {"vv4_harder_fishing_unlock", "vv4_collectible_spawn_like_vv3", "vv4_sickness_like_vv3",
                          "vv4_yellow_fruit_trees_limited", "vv4_difficulty_settings",
                          "vv4_island_events_scale_with_population", "vv4_more_island_events",
                          # the owner (2026-11-16): the whole "More Island Events and Creator" row
                          "vv4_isola_grand_event_collection", "vv4_scrolling_popups"},
                  "vv5": {"vv5_faith_loss_doubled_gains_halved", "vv5_sickness_like_vv3", "vv5_difficulty_settings",
                          "vv5_island_events_scale_with_population", "vv5_more_island_events",
                          "vv5_isola_grand_event_collection", "vv5_scrolling_popups"}}
        for patch_id in CLASSIC_DIFFICULTY_FUN_PATCH_IDS:
            game = patch_id[:3]
            row = public[patch_id]
            self.assertEqual(row.name, "Classic VV Difficulty")
            self.assertEqual(set(row.raw["dependencies"]),
                             {f"{game}_food_pays_like_earlier_games", f"{game}_hungrier_villagers",
                              f"{game}_tech_cost_multiplier", f"{game}_science_collectibles_complete"}
                             | pieces[game])
            self.assertTrue(set(row.raw["dependencies"]) <= set(public))
            self.assertEqual(row.raw["patches"], [])
            self.assertFalse(default_fun_patch_selection(patch_id))
            self.assertTrue(owners_default_fun_patch_selection(patch_id))
            self.assertFalse(select_all_fun_patch_selection(patch_id))
        self.assertEqual(OWNERS_DEFAULT_SLIDER, 2)
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        body = source[source.index("def _owners_default_fun_patches("):]
        body = body[:body.index("\n    def ")]
        self.assertIn('("tech_cost_var", "meal_var", "sickness_var")', body)
        self.assertIn("OWNERS_DEFAULT_SLIDER", body)
        # The title colour rule: a map of patch id -> (style, colour); Classic's rows are red.
        for patch_id in CLASSIC_DIFFICULTY_FUN_PATCH_IDS:
            self.assertEqual(TITLE_COLOURS[patch_id], ("ClassicDifficulty.TCheckbutton", "#c00000"))
        self.assertIn("button.configure(style=title_style)", source)


if __name__ == "__main__":
    unittest.main()


try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, with_requirements
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

MEAL_DLL = ROOT / "assets" / "meal_scale" / "VVFP Meal Scale.dll"
MEAL_CHOICE = "VVFP Meal Scale.txt"
FAKE_FILE = 0x0000F00D
# Where each game keeps its food (VV1/VV2: [eax + offset], eax the game object; VV3-VV5: the store ecx points at).
FOOD_AT = {1: 0xA2EC, 2: 0x2EAA4, 3: 0x582490, 4: 0x4D6DD0, 5: 0x51D34C}


@unittest.skipUnless(HAVE_TOOLS and HAVE_EMULATOR, "pefile/unicorn not installed")
class MealCompanion(unittest.TestCase):
    """"VVFP Meal Scale.dll" started as VVFP More Companions.dll starts it, on the executable a build at that number
    publishes, with the number in "VVFP Meal Scale.txt"; each meal site is run and the food it takes counted."""

    def setUp(self) -> None:
        if not have_stock():
            self.skipTest("stock executables not present")
        if not MEAL_DLL.is_file():
            self.skipTest("companion not built")

    def machine(self, game: int, setting: bytes | None) -> "Machine":
        sys.path.insert(0, str(ROOT / "tests"))
        # As a build publishes a number that is not whole food: the meal bytes at the normal -2 (apply_meal_multiplier).
        data = bytearray(render(game, with_requirements(game, [f"vv{game}_hungrier_villagers"]), "stock"))
        for p in manifest(game)["patches"]:
            data[int(p["offset"], 16)] = 0xFE
        m = Machine(bytes(data), MEAL_DLL)

        def open_(p):
            path = p.wstring(p.arg(0))
            ok = setting is not None and path.endswith("\\Virtual Villagers Fun Patcher Files\\" + MEAL_CHOICE)
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
        return m

    def meal(self, m: "Machine", game: int, va: int) -> int:
        """One meal at the site: the food it takes (VV1/VV2 from the object, VV3-VV5 the pushed amount)."""
        values = {"ebx": 0x11111111, "esi": 0x44444444, "edi": 0x55555555, "ebp": 0x66666666}
        for name, value in values.items():
            m.set_reg(name, value)
        esp = m.reg("esp")
        if game <= 2:
            obj = m.alloc(0x30000)
            m.put32(obj + FOOD_AT[game], 10_000)
            m.set_reg("eax", obj)
            m.set_reg("ecx", 0x22222222)
            m.set_reg("edx", 0x33333333)
            m.run(va, va + 7)
            self.assertEqual(m.reg("esp"), esp)
            self.assertEqual((m.reg("eax"), m.reg("ecx"), m.reg("edx")), (obj, 0x22222222, 0x33333333))
            taken = 10_000 - m.u32(obj + FOOD_AT[game])
        else:
            m.set_reg("eax", 0x77777777)
            m.set_reg("edx", 0x33333333)
            m.run(va, va + 7)
            self.assertEqual(m.reg("esp"), esp - 4, "one argument pushed, as `push -2`")
            self.assertEqual(m.reg("ecx"), FOOD_AT[game], "ecx the food store, as `mov ecx, store`")
            self.assertEqual((m.reg("eax"), m.reg("edx")), (0x77777777, 0x33333333))
            taken = -struct.unpack("<i", struct.pack("<I", m.u32(m.reg("esp"))))[0]
            m.set_reg("esp", esp)
        self.assertEqual({name: m.reg(name) for name in values}, values)
        return taken

    def test_the_meal_takes_two_times_n_on_average(self) -> None:
        for game in NAMES:
            for n, low, high in ((0.3, 0, 1), (0.1, 0, 1), (1.7, 3, 4), (0.9, 1, 2)):
                with self.subTest(game=game, n=n):
                    m = self.machine(game, f"{n}\n".encode())
                    m.export("VvfpStartup", game, 0)
                    self.assertEqual(m.export("VvfpMealScaleInstalled"), 1)
                    self.assertEqual(m.export("VvfpMealScaleTenths"), round(n * 10))
                    for va, _ in SITES[game]:
                        draws = [self.meal(m, game, va) for _ in range(150)]
                        self.assertTrue(all(low <= d <= high for d in draws), set(draws))
                        self.assertIn(low, draws)
                        self.assertIn(high, draws)
                    many = [m.export("VvfpMealScaleNextMeal") for _ in range(4000)]
                    self.assertAlmostEqual(sum(many) / len(many), 2 * n, delta=0.06)

    def test_a_whole_food_number_installs_nothing(self) -> None:
        for game in (1, 4):
            for setting in (b"2", b"0.5", b"1.5", b"", None, b"abc"):
                with self.subTest(game=game, setting=setting):
                    m = self.machine(game, setting)
                    before = [m.read(va, 7) for va, _ in SITES[game]]
                    m.export("VvfpStartup", game, 0)
                    self.assertEqual(m.export("VvfpMealScaleInstalled"), 0)
                    self.assertEqual([m.read(va, 7) for va, _ in SITES[game]], before)

    def test_nothing_in_another_game_or_when_a_site_is_not_stock(self) -> None:
        m = self.machine(3, b"0.3")
        m.export("VvfpStartup", 6, 0)
        self.assertEqual(m.export("VvfpMealScaleInstalled"), 0)
        m = self.machine(3, b"0.3")
        m.write(SITES[3][1][0] + 1, b"\xFC")        # the extra meal at x 2: whole food in the bytes
        before = m.read(SITES[3][0][0], 7)
        m.export("VvfpStartup", 3, 0)
        self.assertEqual(m.export("VvfpMealScaleInstalled"), 0)
        self.assertEqual(m.read(SITES[3][0][0], 7), before)

    def test_the_third_word_starts_it(self) -> None:
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_3[0], "VVFP Meal Scale.dll")
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text("utf-8")
        self.assertIn('"VVFP Meal Scale.dll",', header)
