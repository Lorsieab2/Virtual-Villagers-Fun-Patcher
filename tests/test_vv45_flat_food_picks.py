"""Food Gains are Flat, like VV1-3 (Harder Games): The Tree of Life and New Believers (off by default).

The owner: "Food and Tech Point Gains work like VV1-3: instead of scaling, they pay the same flat amount (but the
food mastery, collection bonuses, and any other effects work to change that as normal)" -- decided with the owner:
food only, default off (on in Owner's Defaults), and the flat amount is The Secret City's: a fruit or honey pick
pays 4 / (speed value x 0.16666667f) truncated -- 7, 3 or 2 on Fast, Normal or Slow -- and 4 while catching up
(The Secret City 0x434ABB..0x434AE4).

What scales in the stock games, read from the executables:

* The Tree of Life, the blackberry pick (job event 13, 0x464464): max(2, berries / 100) through the food writer
  0x41D920 (Food Mastery), then as many berries off the bush (clamped at 0; the task ends below 3).
* New Believers, the noni pick (job step 12, 0x46CFCD): max(2, noni / 100) through 0x41EB40, as many noni taken.

The row replaces only the 33 bytes that compute the amount: 4 while the catch-up flag is set (VV4 game+0x171A4,
VV5 game+0x17E10), else 7 at the speed value 3, 2 at 10, 3 otherwise (VV4 game+0x17110, VV5 game+0x17D7C; the
same flag and speed the stock fish step 0x4643F4 / 0x46CF5D reads).  The food writer, the subtraction and the
task end are the stock code that follows.

Pinned here: the stock and rendered bytes in every population mode, and the pick step RUN in an emulator over the
stock and the rendered executables at each speed and while catching up, with Food Mastery 1, 2 and 3.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402
from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,  # noqa: E402
                                select_all_fun_patch_selection)

STOCK = ROOT / "research" / "stock-executables"
EXE = {"vv4": "Virtual Villagers - The Tree of Life.exe", "vv5": "Virtual Villagers - New Believers.exe"}
NAME = "Food Gains are Flat, like VV1-3 (Harder Games)"
SITE = {   # game: (step entry, patched site VA, stock bytes, rendered bytes)
    "vv4": (0x464464, 0x46446B, "8B8BF8700100B81F85EB51F7E9C1FA058BFAC1EF1F03FA83FF027D05BF02000000",
            "80BBA4710100006A045F75158B83107101006A075F3C0374086A035F3C0A75014F"),
    "vv5": (0x46CFCD, 0x46CFD4, "8B8B587D0100B81F85EB51F7E9C1FA058BF2C1EE1F03F283FE027D05BE02000000",
            "80BB107E0100006A045E75158B837C7D01006A075E3C0374086A035E3C0A75014E"),
}
# game: (game getter, statistics call (ret 8), food store, tech levels (Food Mastery is index 4), the source's
# field, the speed field, the catch-up flag field, where the step has finished (after the task-end check))
GAME = {
    "vv4": (0x41FE70, 0x412F90, 0x4D6DD0, 0x4D6F5C, 0x170F8, 0x17110, 0x171A4, 0x4644C2),
    "vv5": (0x425950, 0x413450, 0x51D34C, 0x51D5CC, 0x17D58, 0x17D7C, 0x17E10, 0x46D02B),
}
SECRET_CITY = {3: 7, 6: 3, 10: 2}     # The Secret City's fruit and honey pick (src/vv_game_mechanics_farmers_vv3.py)
SECRET_CITY_CATCH_UP = 4


def _row(game: str) -> str:
    return f"{game}_food_pays_like_earlier_games"


def _render(game: str, mode: str = "immediate_fixed", with_row: bool = True) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == game)
    rows = [_row(game)] if with_row else []
    rendered, applied = vfp.render_patched_bytes(STOCK / EXE[game], build, mode, rows)
    owners = {r["owner"] for r in applied}
    assert (f"feature:{_row(game)}" in owners) == with_row, owners
    return bytes(rendered)


def _off(game: str, va: int) -> int:
    pe = pefile.PE(str(STOCK / EXE[game]), fast_load=True)
    return pe.get_offset_from_rva(va - 0x400000)


def _mastery(level: int, amount: int) -> int:
    return amount * 2 if level >= 3 else (amount + amount // 2 if level == 2 else amount)


def _pick(game: str, image: bytes, *, source: int, speed: int, catching_up: bool, mastery: int = 1,
          food: int = 500) -> tuple[int, int]:
    """Run the pick step from its entry over the executable's own sections: (food gained, source left)."""
    getter, stats, store, levels, field, speed_at, flag_at, done = GAME[game]
    entry = SITE[game][0]
    pe = pefile.PE(data=image, fast_load=True)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    top = max(s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData) for s in pe.sections)
    mu.mem_map(0x400000, (top + 0xFFFF) & ~0xFFFF)
    for s in pe.sections:
        raw = image[s.PointerToRawData:s.PointerToRawData + s.SizeOfRawData]
        mu.mem_write(0x400000 + s.VirtualAddress, raw[:max(s.Misc_VirtualSize, s.SizeOfRawData)])
    game_obj, villager, rec, stack = 0x20000000, 0x21000000, 0x22000000, 0x70000000
    for a in (game_obj, villager, rec):
        mu.mem_map(a, 0x20000)
    mu.mem_map(stack - 0x10000, 0x20000)
    mu.mem_write(game_obj + field, struct.pack("<i", source))
    mu.mem_write(game_obj + speed_at, struct.pack("<i", speed))
    mu.mem_write(game_obj + flag_at, bytes([1 if catching_up else 0]))
    mu.mem_write(villager + 0x1B88, struct.pack("<I", rec))
    mu.mem_write(store, struct.pack("<i", food))
    mu.mem_write(levels + 4 * 4, struct.pack("<i", mastery))
    mu.reg_write(UC_X86_REG_ESP, stack - 0x100)
    mu.reg_write(UC_X86_REG_ESI if game == "vv4" else UC_X86_REG_EDI, villager)

    def hook(mu, address, size, user_data):
        if address in (getter, stats):
            esp = mu.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", mu.mem_read(esp, 4))[0]
            if address == getter:
                mu.reg_write(UC_X86_REG_EAX, game_obj)
                mu.reg_write(UC_X86_REG_ESP, esp + 4)
            else:
                mu.reg_write(UC_X86_REG_ESP, esp + 12)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address == done:
            mu.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    mu.emu_start(entry, 0, count=2000)
    assert mu.reg_read(UC_X86_REG_EIP) == done, hex(mu.reg_read(UC_X86_REG_EIP))
    gained = struct.unpack("<i", mu.mem_read(store, 4))[0] - food
    left = struct.unpack("<i", mu.mem_read(game_obj + field, 4))[0]
    return gained, left


class FlatFoodPicksTests(unittest.TestCase):
    def test_stock_and_rendered_bytes_in_every_population_mode(self):
        for game, (_, site, stock, after) in SITE.items():
            o = _off(game, site)
            stock_image = (STOCK / EXE[game]).read_bytes()
            self.assertEqual(stock_image[o:o + 33], bytes.fromhex(stock))
            for mode in ("stock", "collection_progression", "immediate_fixed"):
                with self.subTest(game=game, mode=mode):
                    patched = _render(game, mode)
                    self.assertEqual(patched[o:o + 33], bytes.fromhex(after))
                    without = _render(game, mode, with_row=False)
                    diff = [i for i in range(len(patched)) if patched[i] != without[i]]
                    # The 33 bytes and the PE checksum, nothing else.
                    self.assertTrue(all(o <= i < o + 33 or 0x100 <= i < 0x200 for i in diff), diff[:8])

    def test_stock_pick_scales_with_the_source(self):
        for game in SITE:
            image = (STOCK / EXE[game]).read_bytes()
            for source in (3, 150, 250, 399, 400, 1000):
                for speed in (3, 6, 10):
                    for catching_up in (False, True):
                        with self.subTest(game=game, source=source, speed=speed, catching_up=catching_up):
                            pay = max(2, source // 100)
                            self.assertEqual(_pick(game, image, source=source, speed=speed,
                                                   catching_up=catching_up), (pay, max(0, source - pay)))

    def test_patched_pick_pays_the_secret_citys_flat_amount(self):
        for game in SITE:
            image = _render(game)
            for source in (4, 150, 1000):
                for speed, pay in SECRET_CITY.items():
                    with self.subTest(game=game, source=source, speed=speed):
                        self.assertEqual(_pick(game, image, source=source, speed=speed, catching_up=False),
                                         (pay, max(0, source - pay)))
                    with self.subTest(game=game, source=source, speed=speed, catching_up=True):
                        self.assertEqual(_pick(game, image, source=source, speed=speed, catching_up=True),
                                         (SECRET_CITY_CATCH_UP, max(0, source - SECRET_CITY_CATCH_UP)))
                # Paused (the speed + 999): the villagers are not updated then; the pick would pay Normal's 3.
                with self.subTest(game=game, source=source, speed="paused"):
                    self.assertEqual(_pick(game, image, source=source, speed=6 + 999, catching_up=False)[0], 3)

    def test_food_mastery_still_multiplies_the_flat_amount(self):
        for game in SITE:
            image = _render(game)
            for level in (1, 2, 3):
                for speed, pay in SECRET_CITY.items():
                    with self.subTest(game=game, level=level, speed=speed):
                        gained, left = _pick(game, image, source=1000, speed=speed, catching_up=False, mastery=level)
                        self.assertEqual(gained, _mastery(level, pay))
                        self.assertEqual(left, 1000 - pay, "the source loses the amount before Food Mastery")
                with self.subTest(game=game, level=level, catching_up=True):
                    self.assertEqual(_pick(game, image, source=1000, speed=6, catching_up=True, mastery=level)[0],
                                     _mastery(level, SECRET_CITY_CATCH_UP))

    def test_the_secret_city_values_are_the_pages_own(self):
        import vv_game_mechanics_farmers_vv3 as vv3
        self.assertEqual(vv3.FRUIT_LIVE_FOOD, SECRET_CITY)
        self.assertEqual(vv3.TRIPS[0].catch_up_food, SECRET_CITY_CATCH_UP)

    def test_the_row_name_and_its_defaults(self):
        rows = {p.id: p for p in vfp.load_public_fun_patches()}
        for game in SITE:
            with self.subTest(game=game):
                row = rows[_row(game)]
                self.assertEqual(row.name, NAME)
                self.assertTrue(row.raw["description"].startswith(
                    "Changes the food sources that scale to a flat gain."))
                self.assertFalse(default_fun_patch_selection(row.id))
                self.assertTrue(owners_default_fun_patch_selection(row.id))
                self.assertTrue(select_all_fun_patch_selection(row.id))
        self.assertNotIn("vv3_food_pays_like_earlier_games", rows)


class GameMechanicsPageTests(unittest.TestCase):
    """The Food sources line (stock first, then the patch) and the Farmers needed figures, from a real save."""

    def _facts(self, game: int, with_row: bool):
        sys.path.insert(0, str(ROOT / "tests"))
        import test_game_mechanics_counts as pages
        page = pages.Page(self, game)
        page.save(pages.fixture(pages.SAVES[game]))
        return page.facts([_row(f"vv{game}")] if with_row else [])

    def test_the_page_says_stock_then_patched_and_farmers_use_the_flat_amount(self):
        for game, name, unchanged in (
                (4, "Blackberries alone", "the harvest, Cooking Pit fruit (3), fish from the net (4) and the Golden "
                                          "Fish (8) already pay a fixed amount and are unchanged"),
                (5, "Noni bushes alone", "the Hydroponic Farm crops (10, 7 or 4 by speed) and the lake fish (4) "
                                         "already pay a fixed amount and are unchanged")):
            with self.subTest(game=game):
                stock = self._facts(game, False)
                patched = self._facts(game, True)
                food = [f.text for f in stock if f.group == "Food sources"]
                self.assertFalse(any(NAME in t for t in food))
                self.assertTrue(any("10 food now" in t for t in food), food)   # the save's full bush: 1,000 / 100
                lines = [f.text for f in patched if f.group == "Food sources"]
                at = next(i for i, t in enumerate(lines) if NAME in t)
                self.assertTrue(any("10 food now" in t for t in lines[:at]), "the stock line comes first")
                self.assertIn("3 food on Normal speed instead (7, 3 or 2 on Fast, Normal or Slow and 4 while "
                              "catching up", lines[at])
                self.assertIn(unchanged, lines[at])
                farm = lambda facts: next(f.text for f in facts if f.text.startswith(name))  # noqa: E731
                self.assertIn("x 10 food)", farm(stock))
                self.assertIn("10 each)", farm(stock))
                self.assertIn("x 4 food)", farm(patched))          # catch-up: The Secret City's 4
                self.assertIn("3 each)", farm(patched))            # live on Normal: 3
                catch_up = "pick gives 4 food while catching up, at any speed (live: 7, 3 or 2"
                self.assertFalse(any(catch_up in f.text for f in stock))
                self.assertTrue(any(catch_up in f.text for f in patched))


if __name__ == "__main__":
    unittest.main()
