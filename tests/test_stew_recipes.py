"""Stew Recipes (src/vv_stew_recipes.py, src/vv_stew_recipes_window.py): a window of its own on the Tools tab with a
tab for The Lost Children, The Secret City and The Tree of Life only (Game Mechanics is not changed), every recipe
with its herbs, its water and what happens, and every table pinned to the stock executables' own bytes -- The Lost
Children's cook routine RUN in the emulator for every herb mix, the other games' recipe registers, effect switches,
herb names, water, food and puzzles read from their code."""
from __future__ import annotations

import itertools
import re
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import island_event_exe as exe  # noqa: E402
import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_counts as counts  # noqa: E402
import vv_stew_recipes as stews  # noqa: E402
import vv_stew_recipes_window as window  # noqa: E402

try:
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_ESP
    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - optional analysis tool
    HAVE_UNICORN = False

NO_TK = 3


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


def recipe(game: int, start: str) -> tuple[gm.Fact, list[gm.Fact]]:
    return next(r for r in recipes(game) if r[0].text.startswith(start))


TK_CHILD = r"""
import sys, tkinter
sys.path.insert(0, sys.argv[1])
import vv_stew_recipes_window as w
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
root.withdraw()
window = w.open_stew_recipes(root, 3)
window.update()
notebook = window.stew_notebook
print(window.resizable() == (True, True), notebook.index("end"), notebook.index(notebook.select()))
print("|".join(notebook.tab(i, "text") for i in range(notebook.index("end"))))
for number, box in window.stew_tabs.items():
    text = box.get("1.0", "end")
    print(number, bool(box.cget("yscrollcommand")), box.cget("state"), len(box.tag_ranges("unconfirmed")) > 0,
          text.startswith(w.page_text(number)[:40]))
root.destroy()
"""


class Window(unittest.TestCase):
    """The owner, 2026-11-10: "Separate window" -- Stew Recipes is its own tool, not part of Game Mechanics."""

    def test_only_the_lost_children_secret_city_and_tree_of_life_have_it(self) -> None:
        self.assertEqual(stews.GAMES, (2, 3, 4))
        self.assertEqual([n for n, _name in window.GAMES], [2, 3, 4])
        for game in (1, 5):
            self.assertEqual(stews.facts(game), [])
        for game in stews.GAMES:
            facts = stews.facts(game)
            self.assertTrue(facts)
            self.assertEqual({fact.group for fact in facts}, {stews.GROUP})
            text = window.page_text(game)
            self.assertFalse(text.startswith(stews.GROUP))
            self.assertTrue(text.startswith(gm.BULLET))

    def test_game_mechanics_is_not_changed(self) -> None:
        import vv_game_mechanics_window as mechanics
        source = (ROOT / "src" / "vv_game_mechanics_window.py").read_text(encoding="utf-8")
        self.assertNotIn("stew", source.lower().replace("stew pot", ""))
        self.assertNotIn(stews.GROUP, gm.GROUPS)
        for game in (2, 3, 4):
            self.assertNotIn("\n" + stews.GROUP + "\n", mechanics.general_text(game))

    def test_a_button_on_the_tools_tab_with_its_guide(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn('text="Stew Recipes...",', source)
        self.assertIn("vv_stew_recipes_window.open_stew_recipes(self, None)", source)
        # On a row of its own (Codex, #758): the genealogy row is full at the 820-pixel minimum width.
        self.assertIn('self._help_button(stew_tools, "stew_recipes")', source)
        self.assertNotIn('self._help_button(genealogy_tools, "stew_recipes")', source)
        self.assertIn("stew_tools = ttk.Frame(box)", source)
        import json
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))["controls"]
        self.assertEqual(guide["stew_recipes"]["title"], "Stew Recipes")

    def test_the_window_opens_with_three_tabs(self) -> None:
        run = subprocess.run([sys.executable, "-c", TK_CHILD, str(ROOT / "src")], capture_output=True, text=True,
                             timeout=120)
        if run.returncode == NO_TK:
            self.skipTest(f"no Tk display: {run.stderr.strip()}")
        self.assertEqual(run.returncode, 0, run.stderr)
        lines = run.stdout.strip().splitlines()
        self.assertEqual(lines[0], "True 3 1")                               # opened at The Secret City
        self.assertEqual(lines[1], "The Lost Children|The Secret City|The Tree of Life")
        for row in lines[2:]:
            number, scrolls, state, red, same = row.split()
            self.assertEqual((scrolls, state, red, same), ("True", "disabled", "True", "True"), row)


class Page(unittest.TestCase):
    def test_every_recipe_has_its_herbs_water_and_effect(self) -> None:
        for game, expected in ((2, 18), (3, len({p for *_, p in counts.VV3_COMBOS}) + 7), (4, 14)):
            found = recipes(game)
            self.assertEqual(len(found), expected, game)
            for title, subs in found:
                with self.subTest(game=game, recipe=title.text):
                    self.assertEqual([s.text.split(": ", 1)[0] + ": " for s in subs[:3]],
                                     [stews.HERBS_LINE, stews.WATER_LINE, stews.DOES_LINE])
                    self.assertTrue(all(len(s.text.split(": ", 1)[1]) > 3 for s in subs[:3]))
                    self.assertTrue(all(s.text.startswith((stews.KILL_LINE, stews.PUZZLE_LINE, stews.REHEAT_LINE))
                                        for s in subs[3:]))
                    self.assertTrue(all(s.confirmed for s in subs[:3]))

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
            self.assertFalse(re.search(r"what it (is|was) doing", text))           # villagers are never "it"

    def test_food_is_said_on_every_page(self) -> None:
        self.assertIn("every stew takes 10 food", gm.render(stews.facts(2)))
        self.assertIn("potions take no food", gm.render(stews.facts(3)))
        vv4 = gm.render(stews.facts(4))
        self.assertIn("takes 10 food from the store", vv4)
        self.assertIn("(the Grand Feast 20)", vv4)
        self.assertFalse(re.search(r"heat", vv4))              # the food count is not heat (re-traced)

    def test_what_kills_and_what_is_unconfirmed(self) -> None:
        """Making a villager sick can kill (the code); the health floors stay UNCONFIRMED (the owner, 2026-11-10:
        "I could swear I killed villagers with just the stews")."""
        for game, sick, floored in ((2, "Makes the eater sick", ("Nasty", "Burns")),
                                    (3, "\"That potion was awful.\"", ("\"Oh, it burns!\"",
                                                                       "\"He or she has a stomachache.\"",
                                                                       "\"Yikes!\""))):
            _t, subs = recipe(game, sick)
            kill = [s for s in subs if s.text.startswith(stews.KILL_LINE)]
            self.assertEqual(len(kill), 1)
            self.assertTrue(kill[0].confirmed)
            self.assertIn("can kill a villager who is not cured", kill[0].text)
            for start in floored:
                _t, subs = recipe(game, start)
                kill = [s for s in subs if s.text.startswith(stews.KILL_LINE)]
                self.assertEqual(len(kill), 1, start)
                self.assertFalse(kill[0].confirmed, start)                       # shown UNCONFIRMED
                self.assertIn("players have seen villagers die", kill[0].text)
                self.assertNotIn("never below", subs[2].text)
            self.assertIn("UNCONFIRMED  " + stews.KILL_LINE, gm.render(stews.facts(game)))
        self.assertIn("None of these stews takes away health or makes anyone sick.", gm.render(stews.facts(4)))

    def test_children_play(self) -> None:
        title, subs = recipe(2, "Sweet smell")
        self.assertEqual(title.text, "Sweet smell: makes children play")
        self.assertIn("plays (dancing, jumping or running away, equally likely)", subs[2].text)

    def test_stews_for_puzzles(self) -> None:
        for game, names in ((2, ("The Stew", "The Sunken Gong Piece")), (3, ("The Sharks",)),
                            (4, ("The Grand Feast", "Honoring the Tree", "Soap Invented", "Cloth Invented"))):
            summary = next(f.text for f in stews.facts(game) if f.text.startswith("Stews for puzzles:"))
            for name in names:
                self.assertIn(name, summary)
        self.assertTrue(recipe(2, "Puzzle: The Sunken Gong Piece")[0].confirmed)
        for start in ("Puzzle: The Sharks", "Puzzle: The Grand Feast", "Puzzle: Honoring the Tree"):
            game = 3 if "Sharks" in start else 4
            for _t, subs in [r for r in recipes(game) if r[0].text.startswith(start)]:
                self.assertTrue(any(s.text.startswith(stews.PUZZLE_LINE) and s.confirmed for s in subs), start)
        _t, feast = recipe(4, "Puzzle: The Grand Feast")
        words = " ".join(s.text for s in feast)
        for need in ("one hot rock", "20 food", "blackberries", "a fish", "fruit", "a mushroom",
                     "nobody has to eat it"):
            self.assertIn(need, words)
        # The owner chose the code's recipe (2026-11-10): no open question is left on the feast, and the spicy +
        # sweet + sweet stew says it does not solve it.
        self.assertTrue(all(s.confirmed for s in feast))
        _t, yummy = recipe(4, "Calls the whole village to the pot")
        self.assertIn("only spicy + sweet + soapy", " ".join(s.text for s in yummy))
        # Reheating is said once, for every stew (the owner: "All stews"), not under each recipe.
        vv4 = [f.text for f in stews.facts(4)]
        self.assertEqual(sum("Not every stew can: some just evaporate instead" in t for t in vv4), 1)
        self.assertFalse(any(t.startswith(stews.REHEAT_LINE) for t in vv4))
        # Food: fresh water always; salt water only for the failed "Too salty" mix (0x42DC80).
        food = next(t for t in vv4 if t.startswith("Food:"))
        for need in ("every fresh-water stew needs 10 food", "Grand Feast 20", "no food for soap or cloth pulp",
                     "\"Too salty\") asks for 10 food"):
            self.assertIn(need, food)
        _t, honor = recipe(4, "Puzzle: Honoring the Tree")
        self.assertIn("20 villagers", " ".join(s.text for s in honor))

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

    def test_the_vv2_herbs_are_named_by_colour(self) -> None:
        """The owner, 2026-11-10: each strange plant by its colour, the same name in the list and every recipe."""
        names = {herb: name for herb, (name, *_rest) in stews.VV2_HERBS.items()}
        self.assertEqual(names, {0x30: "Dark blue flower", 0x31: "Purple-black flower", 0x32: "Brown pitcher plant",
                                 0x33: "Orange flower", 0x34: "Light blue flower", 0x35: "Red flower"})
        page = gm.render(stews.facts(2))
        self.assertIn("the patcher's own", page)
        self.assertIn("the game calls every one \"the strange plant\"", page)
        for name in names.values():
            self.assertIn(f"{name}: ", page)
        for _title, subs in recipes(2):
            for mix in subs[0].text.removeprefix(stews.HERBS_LINE).split("; "):
                self.assertEqual(len(mix.split(" + ")), 3)
                self.assertTrue(set(mix.split(" + ")) <= set(names.values()), mix)

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


class WhatTheCodeDoes(unittest.TestCase):
    """The instructions behind the kill, food, boiling and puzzle lines (the owner's play outranks the floors, which
    the page therefore shows UNCONFIRMED: these pin only what the code does)."""

    def check(self, game: int, pins) -> None:
        if not exe.available(game):
            self.skipTest("the stock exe or capstone is missing")
        image = exe.exe(game)
        for address, instruction in pins:
            self.assertEqual(image.instruction(address), instruction, (game, hex(address)))

    def test_the_lost_children(self) -> None:
        self.check(2, (
            (0x4610AF, "mov dword ptr [edx + edi + 0x53c], 1"),       # stew 2: the eater falls sick
            (0x461174, "cmp ecx, 3"), (0x46117B, "mov dword ptr [eax], 3"),   # stew 4: stopped at 3
            (0x4614F4, "cmp eax, 3"), (0x4614FB, "mov dword ptr [esi], 3"),   # stew 18: stopped at 3
            (0x42602B, "cmp eax, 4"), (0x426034, "cmp eax, 2"), (0x42603D, "cmp eax, 0x12"),   # not The Stew
            (0x426056, "mov byte ptr [esi + 0x2e7a8], 1"),              # The Stew solved
            (0x45ADB1, "cmp eax, 0xa"), (0x462372, "add dword ptr [eax + 0x2eaa4], -0xa"),   # 10 food
            (0x46114E, "mov dword ptr [ecx + 0x3045c], edx"),           # stew 5 keeps its eater
            (0x430029, "cmp dword ptr [esi + 0x3045c], edi"),           # ... whom the pond lets dive
        ))

    def test_the_secret_city(self) -> None:
        self.check(3, ((0x426CB9, "cmp ebx, 2"), (0x426CBE, "mov ebx, 2")))   # a potion's loss stopped at 2

    def test_feels_smarter_is_skill_plus_67_percent(self) -> None:
        """Potion 3: the skill test passes on rand(100) <= skill + 66 instead of + 33, so the chance is the skill +
        67% instead of + 34% (rand() % 100 over 32,768 values)."""
        self.check(3, ((0x45A2F7, "push 3"), (0x45A314, "add eax, 0x21"), (0x45A31B, "mov edi, 0x42"),
                       (0x45A340, "push 0x64"), (0x45A34C, "cmp eax, ebp")))
        passes = lambda offset, skill: sum(1 for v in range(32768) if v % 100 <= skill + offset)  # noqa: E731
        self.assertEqual((f"{passes(66, 0) / 32768:.2%}", f"{passes(33, 0) / 32768:.2%}"), ("67.07%", "34.03%"))
        self.assertEqual(min(s for s in range(101) if passes(66, s) == 32768), 33)
        _t, subs = recipe(3, "\"He or she feels smarter.\"")
        text = " ".join(s.text for s in subs)
        self.assertIn("every skill test passes at the skill + 67% instead of + 34% (+ 17% for a villager who "
                      "dislikes learning; one who likes learning already has + 67%): 67.07% instead of 34.03% at "
                      "skill 0, and every time from skill 33.", text)
        self.assertNotIn("+ 66%", gm.render(stews.facts(3)))

    def test_the_tree_of_life(self) -> None:
        self.check(4, (
            (0x46ED53, "cmp eax, 0xa"), (0x46ED66, "push -0xa"),        # the food bin: 10 or more, takes 10
            (0x42E0CE, "push 6"),                                       # ... carried into the stew as item 6
            (0x42EAA2, "cmp ecx, 6"), (0x42EAA7, "add dword ptr [esi + 0xb18], 0xa"),   # +10 to the stew's count
            (0x42DC9E, "cmp eax, 0xa"), (0x42DCA8, "cmp eax, 0x14"),    # ready at 10, the feast at 20
            (0x42F981, "push 0x34"),                                    # the hot rock (item 0x34) ...
            (0x42F4A0, "push 2"), (0x42F4AC, "push 0x18"),              # ... boils the pot (Boiling Water)
            (0x42EEDC, "push 0xa"),                                     # the feast made: The Grand Feast
            (0x4366EC, "cmp dword ptr [esp], 0x14"), (0x4366F2, "push 0xd"),   # 20 honoring: Honoring the Tree
            (0x46F8AC, "call 0x42dde0"), (0x43332C, "call 0x42dd80"),   # blackberries, a fish ...
            (0x4349A8, "call 0x42dda0"), (0x413233, "call 0x42dd60"),   # ... fruit, a mushroom for the feast
        ))
        image = exe.exe(4)
        # Which item sets which feast flag: the pot's drop switch 0x42EABE (byte table 0x42EB4C -> 0x42EB38).
        flags = {}
        for item in range(0x79):
            case = image.raw[image.off(0x42EB4C + item)]
            target = image.u32(0x42EB38 + 4 * case)[0]
            if target != 0x42EB2E:
                flags[item] = image.instruction(target)
        self.assertEqual(flags, {0x00: "mov byte ptr [esi + 0xb1d], 1", 0x37: "mov byte ptr [esi + 0xb1f], 1",
                                 0x38: "mov byte ptr [esi + 0xb1e], 1", 0x76: "mov byte ptr [esi + 0xb1c], 1",
                                 0x77: "mov byte ptr [esi + 0xb1c], 1", 0x78: "mov byte ptr [esi + 0xb1c], 1"})
        self.assertEqual(exe.text(4, 0x197), "Adding to the stew")
        self.assertEqual(exe.text(4, 0x196), "Taking a hot rock to the pot")


if __name__ == "__main__":
    unittest.main()
