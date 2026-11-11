"""The Stew Recipes page (src/vv_game_mechanics_stews.py): a page of its own on The Lost Children's, The Secret
City's and The Tree of Life's tabs only, every recipe with its herbs, its water and what happens, and every table
pinned to the stock executables' own bytes -- The Lost Children's cook routine RUN in the emulator for every herb
mix, the other games' recipe registers, effect switches, herb names and water read from their code."""
from __future__ import annotations

import itertools
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import island_event_exe as exe  # noqa: E402
import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_counts as counts  # noqa: E402
import vv_game_mechanics_stews as stews  # noqa: E402
import vv_game_mechanics_window as window  # noqa: E402

try:
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_ESP
    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - optional analysis tool
    HAVE_UNICORN = False


def recipes(game: int) -> list[tuple[gm.Fact, list[gm.Fact]]]:
    """Each recipe on a game's page: its title line and the sub-lines under it."""
    out: list[tuple[gm.Fact, list[gm.Fact]]] = []
    for fact in stews.facts(game):
        if fact.sub and out:
            out[-1][1].append(fact)
        elif not fact.sub:
            out.append((fact, []))
    return [(title, subs) for title, subs in out if subs and subs[0].text.startswith(stews.HERBS_LINE)]


def quoted(text: str) -> list[str]:
    return re.findall(r"\"([^\"]+)\"", text)


class Page(unittest.TestCase):
    def test_only_the_lost_children_secret_city_and_tree_of_life_have_it(self) -> None:
        self.assertEqual(stews.GAMES, (2, 3, 4))
        for game in (1, 5):
            self.assertEqual(stews.facts(game), [])
            facts = [gm.Fact(gm.ITEMS, "x", gm.CODE)]
            self.assertIs(stews.with_recipes(facts, game), facts)
        for game in stews.GAMES:
            facts = stews.facts(game)
            self.assertTrue(facts)
            self.assertEqual({fact.group for fact in facts}, {stews.GROUP})
            self.assertTrue(all(fact.confirmed for fact in facts), game)

    def test_it_is_a_page_of_its_own_after_the_items(self) -> None:
        self.assertNotIn(stews.GROUP, gm.GROUPS)
        page = [gm.Fact("Refills", "a"), gm.Fact(gm.ITEMS, "b"), gm.Fact(gm.ITEMS, "c"), gm.Fact("Other", "d")]
        out = stews.with_recipes(page, 4)
        n = len(stews.facts(4))
        self.assertEqual(out[:3], page[:3])
        self.assertEqual({f.group for f in out[3:3 + n]}, {stews.GROUP})
        self.assertEqual(out[3 + n:], page[3:])
        self.assertEqual(stews.with_recipes([gm.Fact("Other", "d")], 2)[1].group, stews.GROUP)

    def test_the_window_shows_it_with_a_link(self) -> None:
        for game in (1, 2, 3, 4, 5):
            text = window.general_text(game)
            lines = text.split("\n")
            self.assertEqual(stews.GROUP in lines, game in stews.GAMES, game)
            if game in stews.GAMES:
                self.assertLess(lines.index(gm.ITEMS), lines.index(stews.GROUP))
        source = (ROOT / "src" / "vv_game_mechanics_window.py").read_text(encoding="utf-8")
        self.assertIn("if line in gm.GROUPS or line == stews.GROUP:", source)   # the heading gets its link

    def test_every_recipe_has_its_herbs_water_and_effect(self) -> None:
        for game, expected in ((2, 18), (3, len({p for *_, p in counts.VV3_COMBOS}) + 7), (4, 14)):
            found = recipes(game)
            self.assertEqual(len(found), expected, game)
            for title, subs in found:
                with self.subTest(game=game, recipe=title.text):
                    self.assertEqual([s.text.split(": ", 1)[0] + ": " for s in subs],
                                     [stews.HERBS_LINE, stews.WATER_LINE, stews.DOES_LINE])
                    self.assertTrue(all(len(s.text.split(": ", 1)[1]) > 3 for s in subs))
                    self.assertTrue(title.text)

    def test_the_water_is_said_for_every_recipe(self) -> None:
        for title, subs in recipes(2):
            self.assertEqual(subs[1].text, stews.WATER_LINE + stews.VV2_WATER)
        for title, subs in recipes(3):
            self.assertEqual(subs[1].text, stews.WATER_LINE + stews.VV3_WATER)
        waters = [subs[1].text.removeprefix(stews.WATER_LINE) for _t, subs in recipes(4)]
        self.assertEqual(set(waters), {"fresh water", "salt water"})
        self.assertEqual(waters.count("salt water"), 3)              # soap, cloth pulp, too salty

    def test_plain_words_for_a_player(self) -> None:
        for game in stews.GAMES:
            text = gm.render(stews.facts(game))
            self.assertNotIn("0x", text)
            self.assertNotIn("{He/She}", text)
            self.assertFalse(re.search(r"\b[0-9A-F]{6}\b", text), game)
            self.assertLessEqual(max(len(word) for word in text.split()), 40)     # word-wraps in the window

    def test_every_mix_is_listed_once(self) -> None:
        mixes = [m for ms in stews.VV2_RECIPES.values() for m in ms]
        self.assertEqual(sorted(mixes), list(itertools.combinations_with_replacement(range(0x30, 0x36), 3)))
        self.assertEqual(sorted(stews.VV2_RECIPES), list(range(1, 19)))
        self.assertEqual(sorted(n for n, *_ in stews.VV2_STEWS), list(range(1, 19)))
        page = gm.render(stews.facts(3))
        for a, b, c, product in counts.VV3_COMBOS:
            self.assertIn(" + ".join(counts.VV3_HERBS[h] for h in sorted((a, b, c))), page)
        keys = [(herbs, water) for herbs, _p, water in stews.VV4_RECIPES]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(sorted(stews.VV4_ORDER), sorted(stews.VV4_STEWS))
        self.assertEqual(set(stews.VV4_STEWS),
                         {p for _h, p, _w in stews.VV4_RECIPES} | {stews.FAILED_FRESH, stews.FAILED_SALT})

    def test_the_vv3_both_faction_recipes_are_the_companions(self) -> None:
        source = (ROOT / "native" / "vvfp_vv3_both_factions" / "vvfp_vv3_both_factions.c")
        if not source.exists():
            source = next((ROOT / "native" / "vvfp_vv3_both_factions").glob("*.c"))
        text = source.read_text(encoding="utf-8", errors="replace")
        table = text[text.index("RECIPES[7] = {"):]
        table = table[:table.index("};")]
        pairs = tuple((int(a, 16), int(b, 16)) for a, b in re.findall(r"\{\s*(0x[0-9A-F]+),\s*(0x[0-9A-F]+)\s*\}",
                                                                          table))
        self.assertEqual(pairs, stews.VV3_BOTH)


@unittest.skipUnless(exe.available(2), "the stock Lost Children exe or capstone is missing")
class LostChildren(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(2)

    @unittest.skipUnless(HAVE_UNICORN, "unicorn is missing")
    def test_the_cook_routine_makes_each_mix_its_stew(self) -> None:
        """Run the stock cook routine 0x425B90 for every mix, in two orders, and read the stew it sets."""
        pe, raw = self.exe.pe, self.exe.raw
        image = pe.get_memory_mapped_image()
        manager = 0x10000000

        def cook(herbs) -> int:
            mu = Uc(UC_ARCH_X86, UC_MODE_32)
            mu.mem_map(0x400000, (len(image) + 0xFFF) & ~0xFFF)
            mu.mem_write(0x400000, image)
            mu.mem_map(manager, 0x40000)
            mu.mem_map(0x20000000, 0x10000)
            mu.reg_write(UC_X86_REG_ESP, 0x20008000)
            mu.mem_write(manager + 0x3043C, struct.pack("<3I", *herbs))
            for reg in (UC_X86_REG_ESI, UC_X86_REG_ECX):
                mu.reg_write(reg, manager)
            mu.reg_write(UC_X86_REG_EDI, 0)
            got: list[int] = []

            def write(uc, _access, address, _size, value, _data):
                if address == manager + 0x3044C:
                    got.append(value)
                    uc.emu_stop()

            def code(uc, address, _size, _data):
                if address == 0x426017:                      # the routine's join: no stew was written on the way
                    got.append(-1)
                    uc.emu_stop()

            mu.hook_add(UC_HOOK_MEM_WRITE, write)
            mu.hook_add(UC_HOOK_CODE, code)
            # From just after the clock call (0x425B9D): the stew field was cleared, the pot's end set.
            mu.emu_start(0x425BA7, 0x42610C, count=5000)
            return got[0]

        del raw
        self.assertEqual(self.exe.instruction(0x425B97), "mov dword ptr [esi + 0x3044c], edi")
        for stew, mixes in stews.VV2_RECIPES.items():
            for mix in mixes:
                for order in {mix, tuple(reversed(mix)), (mix[1], mix[2], mix[0])}:
                    with self.subTest(stew=stew, herbs=[hex(h) for h in order]):
                        self.assertEqual(cook(order), stew)

    def test_the_herbs_have_no_names_in_the_game(self) -> None:
        self.assertEqual(exe.text(2, 176), "sees the strange plant.")
        self.assertEqual(exe.text(2, 263), "Studying strange plant")
        self.assertEqual(self.exe.instruction(0x42BDDF), "push 0xb0")
        for herb, (_name, _where, place, _spot) in stews.VV2_HERBS.items():
            # The hover: place - 3 in the byte table 0x42C1E8, its case in 0x42C184 -> the strange plant.
            case = self.exe.raw[self.exe.off(0x42C1E8 + place - 3)]
            self.assertEqual(self.exe.u32(0x42C184 + 4 * case)[0], 0x42BD6D, hex(place))

    def test_each_plant_gives_its_herb_and_grows_where_the_page_says(self) -> None:
        studies = {}
        for herb, (_name, _where, place, spot) in stews.VV2_HERBS.items():
            with self.subTest(herb=hex(herb)):
                # The drop: place - 3 in 0x430888, its case in 0x4307EC.
                case = self.exe.raw[self.exe.off(0x430888 + place - 3)]
                handler = self.exe.u32(0x4307EC + 4 * case)[0]
                body = self.exe.disasm(handler, handler + 0xA0)
                calls = [n for n, (_a, m, o) in enumerate(body) if m == "call" and o in ("0x45a5c0",)]
                self.assertTrue(calls)
                trip_arg = int(body[calls[0] - 2][2], 16)               # push <arg> / push edi / call
                study = next(int(o, 16) for _a, m, o in body[calls[0]:] if m == "call" and o != "0x45a5c0")
                studies[herb] = study
                # The herb trip 0x45A5C0: arg - 0x21 in its table 0x45AD58; the trip ends with its action.
                trip = self.exe.u32(0x45AD58 + 4 * (trip_arg - 0x21))[0]
                steps = self.exe.disasm(trip, trip + 0x200)
                end = next(n for n, (a, m, o) in enumerate(steps)
                           if (m == "jmp" and o == "0x45ad38") or a == 0x45AD38)      # the last trip runs into it
                action = int(steps[end - 1][2], 16)
                # The action's completion (0x461B10: action - 1 in 0x4642F4) puts that herb in the pot.
                done = self.exe.u32(0x4642F4 + 4 * (action - 1))[0]
                writes = [o for _a, m, o in self.exe.disasm(done, done + 0x50) if m == "mov" and "0x3043c]" in o]
                self.assertTrue(writes[0].endswith(hex(herb)), (hex(done), writes))
                # Where it grows: the study's first walk (step 3 to x, y).
                walk = self.exe.disasm(study, study + 0x80)
                pushes = [o for _a, m, o in walk if m == "push"]
                at = pushes.index("3")
                x, y = pushes[at - 1], pushes[at - 2]
                if x == "eax":                                          # the south plant: x = 875 + rand(29)
                    self.assertEqual(herb, 0x33)
                    self.assertEqual(pushes[at - 2], "0x1d")            # rand(29)'s argument, pushed between
                    self.assertIn("add eax, 0x36b", [f"{m} {o}" for _a, m, o in walk])
                    self.assertEqual(spot[1], int(pushes[at - 3], 16))
                    self.assertTrue(875 <= spot[0] <= 875 + 28)
                else:
                    self.assertEqual(spot, (int(x, 16), int(y, 16)))
                self.assertEqual(self.exe.instruction(study + 0x21), "push 0x107")   # "Studying strange plant"
        self.assertEqual(len(set(studies.values())), 6)

    def test_the_water_is_fetched_at_the_pond(self) -> None:
        self.assertEqual(exe.text(2, 293), "Adding water to the stew")
        self.assertEqual(self.exe.instruction(0x45AF51), "push 0x125")
        self.assertEqual(self.exe.instruction(0x45AF6B), "push 0x35b")
        self.assertEqual(self.exe.instruction(0x45AF70), "push 0x3ee")
        self.assertEqual(self.exe.instruction(0x45AF85), "push 0x337")
        self.assertEqual(self.exe.instruction(0x45AF8A), "push 0x57d")
        self.assertEqual(self.exe.instruction(0x45B0AF), "push 0x2f")              # action 47 when it is back
        self.assertEqual(self.exe.u32(0x4642F4 + 4 * 46)[0], 0x4623C7)
        self.assertEqual(self.exe.instruction(0x4623CD), "mov byte ptr [eax + 0x30455], 1")
        self.assertEqual(self.exe.instruction(0x42FEE4), "call 0x45af30")         # the pot asks for the water

    def test_each_stew_shows_its_message(self) -> None:
        self.assertEqual(self.exe.instruction(0x461051), "cmp eax, 0x11")
        targets = self.exe.u32(0x461510, 18)
        for stew, _title, does in stews.VV2_STEWS:
            with self.subTest(stew=stew):
                body = self.exe.disasm(targets[stew - 1], targets[stew - 1] + 0x200)
                end = next(n for n, (_a, m, _o) in enumerate(body) if m == "ret")
                said = {int(next(o2 for _a2, m2, o2 in reversed(body[:n]) if m2 == "push"), 16)
                        for n, (_a, m, o) in enumerate(body[:end]) if m == "call" and o == "0x44b2a0"}
                if not said:
                    self.assertTrue(does.startswith("No message."))
                    continue
                self.assertEqual(len(said), 1)
                self.assertEqual(quoted(does)[0], exe.text(2, said.pop()))

    def test_the_cook_time_calls(self) -> None:
        self.assertEqual(self.exe.instruction(0x425EFA), "mov dword ptr [esi + 0x3044c], 1")
        self.assertEqual(self.exe.instruction(0x425F31), "cmp dword ptr [eax + 0x44], 0x32")
        self.assertEqual(self.exe.instruction(0x425F41), "cmp eax, 0x14")                  # 1 in 5
        self.assertEqual(self.exe.instruction(0x425F94), "mov dword ptr [esi + 0x3044c], 0xe")
        self.assertEqual(self.exe.instruction(0x425FCD), "cmp dword ptr [eax + 0x44], 0x32")
        self.assertEqual(self.exe.instruction(0x425FDD), "cmp eax, 0x5a")                  # 9 in 10


@unittest.skipUnless(exe.available(3), "the stock Secret City exe or capstone is missing")
class SecretCity(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(3)

    def test_the_herb_names_are_the_games(self) -> None:
        for k, herb in enumerate(range(0x1F, 0x26)):
            name = counts.VV3_HERBS[herb]
            self.assertEqual(exe.text(3, 0x204 + k), f"Curious about the {name}")
            self.assertIn(name.lower(), exe.text(3, 0xB0 + k).lower())

    def test_each_spot_shows_its_name_and_gives_its_herb(self) -> None:
        handlers = {}                                   # the drop handlers' registration: push 6 / handler / region
        body = self.exe.disasm(0x422AC5, 0x422B27)
        for n, (_a, m, o) in enumerate(body):
            if m == "call" and o == "0x4212a0":
                handlers[int(body[n - 1][2], 16)] = int(body[n - 2][2], 16)
        for k, region in enumerate((8, 9, 10, 11, 12, 30, 31)):
            herb = 0x1F + k
            with self.subTest(region=region):
                # The hover 0x466A40: region - 1 in 0x46767C, its case in 0x467610, says eSaySeesHerb<k+1>.
                case = self.exe.raw[self.exe.off(0x46767C + region - 1)]
                hover = self.exe.u32(0x467610 + 4 * case)[0]
                self.assertIn(f"push {hex(0xB0 + k)}", [f"{m} {o}" for _a, m, o in self.exe.disasm(hover, hover + 0x20)])
                # The drop: "Gathering herbs" (task 0x73) carrying the herb.
                drop = self.exe.disasm(handlers[region], handlers[region] + 0x90)
                self.assertIn(f"mov dword ptr [esp + 8], {hex(herb)}", [f"{m} {o}" for _a, m, o in drop])

    def test_a_recipe_takes_no_water(self) -> None:
        body = self.exe.disasm(0x430480, 0x430510)
        self.assertEqual(next(f"{m} {o}" for _a, m, o in body if m == "ret"), "ret 0x10")   # 3 herbs and a potion


@unittest.skipUnless(exe.available(4), "the stock Tree of Life exe or capstone is missing")
class TreeOfLife(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(4)

    def test_the_recipes_are_the_games(self) -> None:
        body = self.exe.disasm(0x42ED00, 0x42EDD4)
        rows, pushes = [], []
        for _a, m, o in body:
            if m == "push":
                pushes.append(int(o, 0))
            elif m == "call" and o == "0x42ebd0":
                water, product, c, b, a = pushes[-5:]
                rows.append(((a, b, c), product, water))
                pushes = []
        self.assertEqual(tuple(rows), stews.VV4_RECIPES)
        # No recipe: 12 with salt water (flag 0xA), else 13.
        self.assertEqual(self.exe.instruction(0x42ECBE), "push 0xa")
        self.assertEqual(self.exe.instruction(0x42ECCF), "add eax, 0xd")

    def test_the_herb_names_are_the_games(self) -> None:
        for k, (hover, item) in enumerate(((0x46EFC3, 0x46F012), (0x46F053, 0x46F0A2), (0x46F0E3, 0x46F132),
                                           (0x46F173, 0x46F1C2))):
            herb = 0x1F + k
            self.assertEqual(self.exe.instruction(hover), f"push {hex(0x137 + k)}")
            self.assertTrue(exe.text(4, 0x137 + k).endswith(stews.VV4_HERBS[herb] + "."))
            self.assertEqual(self.exe.instruction(item), f"mov dword ptr [esp + 0x14], {hex(herb)}")

    def test_fresh_and_salt_water(self) -> None:
        self.assertEqual(exe.text(4, 0x193), "Filling a pot with fresh water")
        self.assertEqual(exe.text(4, 0x194), "Filling a pot with salt water")
        self.assertEqual(self.exe.instruction(0x42F633), "push 0x193")
        self.assertEqual(self.exe.instruction(0x42F75C), "push 9")                  # fresh: flag 9 set
        self.assertEqual(self.exe.instruction(0x42F773), "push 0x194")
        self.assertEqual(self.exe.instruction(0x42F85B), "push 0xa")                # salt: flag 0xA set
        self.assertEqual(self.exe.instruction(0x42F85F), "call 0x4698d0")

    def test_each_stew_says_its_line(self) -> None:
        self.assertEqual(self.exe.instruction(0x41DEFB), "cmp eax, 0xd")
        targets = self.exe.u32(0x41E108, 14)
        for product, (_title, does) in stews.VV4_STEWS.items():
            with self.subTest(product=product):
                start = targets[product]
                said = []
                for address, m, o in self.exe.disasm(start, start + 0x80):
                    if address == 0x41DF7A or (m == "jmp" and o in ("0x41df7a", "0x41dfc2")) or m == "ret":
                        break
                    if m == "mov" and o.startswith("esi, 0x"):
                        said.append(int(o.split(", ")[1], 16))
                if product in (10, 11):
                    self.assertEqual(start, 0x41DFC2)                  # never eaten: nothing happens there
                if not said:
                    self.assertFalse(does.startswith("\""), "nothing is said")
                for string_id in said:
                    self.assertIn(exe.text(4, string_id).replace("{He/She}", "He or she"), quoted(does))

    def test_soap_and_cloth_pulp(self) -> None:
        for address, instruction in ((0x42E585, "cmp eax, 0xa"), (0x42E58C, "push 0x244"),
                                     (0x42E5A0, "cmp eax, 0xb"), (0x42E5A7, "push 0x24d"),
                                     (0x42E74D, "cmp eax, 0xa"), (0x42E75B, "push 0x77"),
                                     (0x42E762, "cmp eax, 0xb"), (0x42E770, "push 0x7b"),
                                     (0x42DC8E, "cmp edx, 0xa"), (0x42DC93, "cmp edx, 0xb"),
                                     (0x42DC9E, "cmp eax, 0xa"), (0x42DCA8, "cmp eax, 0x14")):
            self.assertEqual(self.exe.instruction(address), instruction, hex(address))
        self.assertEqual(exe.text(4, 0x244), "Soap is ready to stack.")
        self.assertEqual(exe.text(4, 0x24D), "Pulp for cloth is ready.")
        self.assertIn("Soap is ready to stack.", stews.VV4_STEWS[10][1])
        self.assertIn("Pulp for cloth is ready.", stews.VV4_STEWS[11][1])
        recipe = {product: herbs for herbs, product, _w in stews.VV4_RECIPES}
        self.assertEqual(recipe[10], (0x21,) * 3)                           # soapy-smelling plants
        self.assertEqual(recipe[11], (0x22,) * 3)                           # pulpy vines
        # Each hot rock adds 10 heat.
        self.assertEqual(self.exe.instruction(0x42EAA7), "add dword ptr [esi + 0xb18], 0xa")


if __name__ == "__main__":
    unittest.main()
