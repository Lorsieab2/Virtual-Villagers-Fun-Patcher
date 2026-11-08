"""Hungrier Villagers (2-10x Meals) (all five games) and Classic VV Difficulty (The Tree of Life, New Believers).
The traces are in scripts/build_hungrier_villagers_features.py and scripts/build_classic_vv_difficulty_features.py.

  * Each game's two meal sites decode, patched at every N, to the same instruction taking 2 x N food.
  * The Secret City, The Tree of Life and New Believers: the game's own food-add routine run in unicorn with the
    multiplied meal never leaves food below 0, and takes exactly 2 x N above it.
  * A New Home and The Lost Children: the meal routine's own clamp after the two sites sets food to 0 when it is
    0 or less.
  * A published build writes x N at every site and its records say so; the slider, Owner's Defaults and Classic VV
    Difficulty's red title and dependencies.
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
from vv_fun_patcher_gui import (CLASSIC_DIFFICULTY_FUN_PATCH_IDS, OWNERS_DEFAULT_SLIDER,  # noqa: E402
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
            for n in range(1, 11):
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
            for n in range(2, 11):
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
            for n in (2, 5, 10):
                data, applied = patcher.render_patched_bytes(stock_path(game), builds[f"vv{game}"], "stock", ids)
                patcher.apply_meal_multiplier(data, f"vv{game}", n, applied)
                with self.subTest(game=game, n=n):
                    for p in manifest(game)["patches"]:
                        self.assertEqual(data[int(p["offset"], 16)], (-2 * n) & 0xFF)
                    self.assertEqual(patcher.meal_multiplier_applied(applied), n)

    def test_out_of_range_is_refused(self) -> None:
        for bad in (1, 11, True, 2.0, "3"):
            with self.assertRaises(patcher.PatcherError):
                patcher.validate_meal_multiplier(bad)


class Registration(unittest.TestCase):
    def test_off_by_default_on_in_owners_defaults(self) -> None:
        public = {p.id for p in patcher.load_public_fun_patches()}
        for game in NAMES:
            patch_id = f"vv{game}_hungrier_villagers"
            self.assertIn(patch_id, public)
            self.assertFalse(default_fun_patch_selection(patch_id))
            self.assertTrue(owners_default_fun_patch_selection(patch_id))
            self.assertTrue(select_all_fun_patch_selection(patch_id))

    def test_the_slider_is_2_to_10_default_2(self) -> None:
        self.assertEqual(list(patcher.MEAL_MULTIPLIER_RANGE), list(range(2, 11)))
        self.assertEqual(patcher.MEAL_MULTIPLIER_DEFAULT, 2)
        self.assertEqual(saved_meal_multiplier({"meal_multiplier": 7}), 7)
        for bad in ({}, {"meal_multiplier": 11}, {"meal_multiplier": True}, None):
            self.assertEqual(saved_meal_multiplier(bad), 2)

    def test_classic_ticks_the_harder_patches_and_owners_defaults_sets_sliders_to_2(self) -> None:
        """The owner (2026-11-07): "have the classic vv difficulty on default for owner's defaults! (set the
        sliders to 2x." -- and "make the text colored red for the classic vv difficulty patch titles"."""
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        pieces = {"vv4": {"vv4_no_fishing_at_science_2"}, "vv5": {"vv5_faith_loss_doubled_gains_halved"}}
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
        self.assertIn('("tech_cost_var", "meal_var")', body)
        self.assertIn("OWNERS_DEFAULT_SLIDER", body)
        self.assertIn('configure(style="ClassicDifficulty.TCheckbutton")', source)


if __name__ == "__main__":
    unittest.main()
