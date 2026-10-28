"""The Lost Children's technologies, puzzles, buildings, items and patcher upgrades on the Game Mechanics page
(src/vv_game_mechanics_items_vv2.py): every entry and its labels pinned, every technology and its prices against the
stock exe's own tech screen, every puzzle against the page's puzzle table, every building's size against the exe's own
completion callbacks, the stews against the exe's stew routine, and every patcher line's default against the patcher's
own defaults."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import island_event_exe as exe  # noqa: E402
import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_items_vv2 as items  # noqa: E402
import vv_game_mechanics_vv2 as page  # noqa: E402
from test_game_mechanics_items_vv1 import LETTER, _named_patches, _patch_names  # noqa: E402

GAME = 2

PINNED = {
    "Every technology": "CC",
    "Farming level 1": "CCC",
    "Farming level 2": "CCCE",
    "Farming level 3": "CCC",
    "Exploration level 1": "CC",
    "Exploration level 2": "CCU",
    "Exploration level 3": "CC",
    "Science level 1": "CC",
    "Science level 2": "CCC",
    "Science level 3": "CCC",
    "Medicine level 1": "CC",
    "Medicine level 2": "CC",
    "Medicine level 3": "CCCC",
    "Engineering level 1": "CC",
    "Engineering level 2": "CCC",
    "Engineering level 3": "CCCC",
    "Culture level 1": "CCC",
    "Culture level 2": "CCCUU",
    "Culture level 3": "CCCC",
    "Fire": "UEE",
    "The Scarecrow": "CE",
    "The Elder Totem": "EEC",
    "The Hospital": "CECC",
    "Herb Mastery": "CEC",
    "The Sewing Hut": "CU",
    "The Dam": "CC",
    "The Cutting Tool": "UC",
    "The Stew": "CC",
    "The Vine Wall": "CU",
    "The Ancient Mosaic": "CC",
    "The Boxed Gong Piece": "UC",
    "The Sunken Gong Piece": "UC",
    "The Inlaid Gong Piece": "UC",
    "The Overgrown Gong Piece": "CC",
    "Sustainable Fishing": "CE",
    "The broken starting hut": "C",
    "Population huts": "CCCC",
    "Hut repair (Examining hut, Fixing hut)": "CC",
    "The hospital": "C",
    "The dam": "C",
    "The sewing hut": "C",
    "The vine wall": "C",
    "The ancient ruins": "C",
    "The briar thorns": "C",
    "The scarecrow": "C",
    "The fire pit": "EC",
    "Mushrooms": "EEC",
    "Collectibles": "EE",
    "Butterfly Collection": "EC",
    "Shell Collection": "EC",
    "Beetle Collection": "EC",
    "Pebble Collection": "EC",
    "All four collections": "CC",
    "Stews": "ECCU",
    "A snack (the food store)": "E",
    "Teaching children": "CC",
    "The Gong of Wonder": "EC",
    "Research": "E",
    "Origins: Time Warp": "K",
    "Origins: Island Event": "C",
    "Origins: Barrel of Babies": "C",
    "Origins: Tech Point Doubler and Food Point Doubler": "C",
    "Origins: Full Heal / Cure All": "U",
    "Origins: village-wide rows": "UUCCCC",
    "Origins: Villager Details rows": "UUUUC",
    "Story / Cheat Upgrades": "CCCCC",
}
COUNTS = {"technology": 19, "puzzle": 16, "building": 11, "item": 12, "patcher": 8}

# The tech screen's prices: (the level-3 "mov edx" address, the level-2 one) for each technology (0x4437F0..0x443A2C).
PRICE_SITES = {"Farming": (0x44381D, 0x443824), "Exploration": (0x443875, 0x44387C), "Science": (0x4438CD, 0x4438D4),
               "Medicine": (0x443925, 0x44392C), "Engineering": (0x443979, 0x443980), "Culture": (0x4439E2, 0x4439E9)}
# Each building's size, from its completion callback: (address, the size, the entry that gives it).
SIZES = ((0x462AFD, 400, "The broken starting hut"), (0x462C35, 450, "Population huts"),
         (0x462D72, 700, "Population huts"), (0x462EAE, 900, "Population huts"), (0x462FC0, 1200, "The hospital"),
         (0x4630C3, 400, "The sewing hut"), (0x4641EB, 425, "The dam"), (0x46407C, 1000, "The vine wall"),
         (0x4629E8, 5000, "The ancient ruins"), (0x463920, 3000, "The briar thorns"))


def entry(name: str) -> items.Entry:
    return next(e for e in items.ENTRIES if e.name == name)


def text(name: str) -> str:
    return " ".join(line for line, _ in entry(name).lines)


class TheEntries(unittest.TestCase):
    def test_every_entry_and_its_labels_are_pinned(self) -> None:
        got = {e.name: "".join(LETTER[label] for _, label in e.lines) for e in items.ENTRIES}
        self.assertEqual(got, PINNED)
        self.assertEqual(list(got), list(PINNED), "the order changed")

    def test_the_counts_by_kind(self) -> None:
        self.assertEqual(items.counts(), COUNTS)
        self.assertEqual(sum(COUNTS.values()), len(items.ENTRIES))

    def test_the_facts(self) -> None:
        facts = items.item_facts()
        self.assertEqual(len(facts), sum(len(e.lines) for e in items.ENTRIES))
        heads = [f for f in facts if not f.sub]
        self.assertEqual(len(heads), len(items.ENTRIES))
        for fact, one in zip(heads, items.ENTRIES):
            self.assertEqual(fact.text, f"{one.name}: {one.lines[0][0]}")
        for fact in facts:
            self.assertEqual(fact.group, items.ITEMS_GROUP)
            self.assertTrue(fact.verified in gm.TRUSTED or fact.verified is False, fact.text)
            self.assertNotIn(gm.UNCONFIRMED, fact.text)
        rendered = gm.render(facts, 0)
        self.assertEqual(rendered.count(gm.UNCONFIRMED), sum(1 for f in facts if not f.confirmed))

    def test_no_vague_words(self) -> None:
        for e in items.ENTRIES:
            for line, _ in e.lines:
                for vague in ("etc.", "some effect", "and so on", "various"):
                    self.assertNotIn(vague, line, f"{e.name}: {line}")

    def test_every_puzzle_of_the_game_has_one_entry(self) -> None:
        names = [name for name, _flag, _hours in page.PUZZLES]
        self.assertEqual(len(names), 16)
        self.assertEqual(sorted(e.name for e in items.ENTRIES if e.kind == items.PUZZLE), sorted(names))
        for name in names:
            self.assertTrue(entry(name).lines[0][0].startswith("Solved "), name)
            self.assertTrue(any(line.startswith("Reward: ") for line, _ in entry(name).lines), name)

    def test_every_technology_has_both_levels(self) -> None:
        self.assertEqual(len(items.TECH_COSTS), 6)
        for tech, (two, three) in items.TECH_COSTS.items():
            self.assertIn(f"{two:,} tech points", text(f"{tech} level 2"))
            self.assertIn(f"{three:,} tech points", text(f"{tech} level 3"))
            self.assertEqual(entry(f"{tech} level 1").lines[0][0], items.LEVEL_ONE)     # level 1, its own entry
        self.assertEqual(sum(1 for e in items.ENTRIES if e.kind == items.TECH), 1 + 3 * 6)

    @unittest.skipUnless(exe.available(GAME), "the stock exe is not here")
    def test_each_collection_and_the_room_it_gives_against_the_exe(self) -> None:
        """Each collection has its own entry; the room check gives 5 for each complete one and makes four 25, and
        the completion messages are the game's own, shown at the addresses cited."""
        game = exe.exe(GAME)
        for at, first in ((0x44B32B, 0), (0x44B342, 0xC), (0x44B356, 0x18), (0x44B36A, 0x24)):
            self.assertEqual(game.instruction(at), "push " + (hex(first) if first else "edi"))
        self.assertEqual(game.instruction(0x44B378), "cmp edi, 0x14")
        self.assertEqual(game.instruction(0x44B37D), "mov edi, 0x19")
        self.assertEqual(game.instruction(0x44B3AD), "add edi, 0x5a")
        for at, string_id, name in ((0x4634DB, 0x1DE, "Butterfly"), (0x463515, 0x1DF, "Shell"),
                                    (0x46354F, 0x1E0, "Beetle"), (0x463589, 0x1E1, "Pebble"),
                                    (0x463609, 0x1E2, None)):
            self.assertEqual(game.instruction(at), f"push {hex(string_id)}")
            words = exe.text(GAME, string_id)
            if name:
                self.assertTrue(words.startswith(f"{name} Collection"), words)
                self.assertTrue(words.endswith("increased by 5."), words)
                self.assertIn(f"{name} Collection", text(f"{name} Collection"))
            else:
                self.assertTrue(words.endswith("increased by 10!"), words)
        self.assertIn("90 + 25 = 115", text("All four collections"))

    def test_the_eighteen_stews(self) -> None:
        self.assertEqual(len(items.STEW_EFFECTS), 18)
        self.assertEqual([s.split(":", 1)[0] for s in items.STEW_EFFECTS], [str(n) for n in range(1, 19)])

    def test_patcher_lines_name_real_patches_and_their_defaults(self) -> None:
        names = _patch_names(GAME)
        try:
            import vv_fun_patcher_gui as gui
        except Exception as exc:  # noqa: BLE001 -- no GUI toolkit: the defaults cannot be read
            self.skipTest(f"the patcher's defaults cannot be read: {exc}")
        found = 0
        for e in items.ENTRIES:
            for line, _ in e.lines:
                for name, state in _named_patches(line):
                    self.assertIn(name, names, f"{e.name}: no patch is named {name!r}")
                    expected = {"on" if pid not in gui.DEFAULT_OFF_FUN_PATCH_IDS else "off" for pid in names[name]}
                    self.assertEqual(expected, {state}, f"{e.name}: {name}")
                    found += 1
        self.assertGreater(found, 10)


@unittest.skipUnless(exe.available(GAME), "the stock Lost Children exe or capstone/pefile is absent")
class TheExeSaysSo(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(GAME)

    def test_the_tech_prices(self) -> None:
        for tech, (three_at, two_at) in PRICE_SITES.items():
            two, three = items.TECH_COSTS[tech]
            self.assertEqual(self.exe.instruction(two_at), f"mov edx, {hex(two)}", tech)
            self.assertEqual(self.exe.instruction(three_at), f"mov edx, {hex(three)}", tech)

    def test_the_technologies_are_the_games_own(self) -> None:
        for tech, title in items.TECH_TITLES.items():
            self.assertIn(f"{title}\n".encode(), self.exe.raw, tech)
        for address in (0x425229, 0x42522F, 0x425235, 0x42523B, 0x425241, 0x425247):
            self.assertTrue(self.exe.instruction(address).endswith(", esi"), hex(address))

    def test_the_building_sizes(self) -> None:
        for address, size, name in SIZES:
            self.assertTrue(self.exe.instruction(address).endswith(f", {hex(size)}"), hex(address))
            self.assertIn(f"{size:,}", text(name), name)
        self.assertEqual(self.exe.instruction(0x462408), "cmp dword ptr [eax + 0x2e76c], 2")    # the scarecrow
        self.assertEqual(self.exe.instruction(0x462710), "cmp dword ptr [eax + 0x2e7e4], 0xa")  # the fish

    def test_the_drop_and_builder_gates(self) -> None:
        for address, instruction in (
                (0x430174, "cmp dword ptr [eax + 0x2ea9c], 2"),     # coconuts at Farming 2
                (0x42FC4F, "cmp dword ptr [esi + 0x2ea9c], 3"),     # algae-eating fish at Farming 3 ...
                (0x42FC5F, "mov eax, 0x58"),                        # ... and Farming or Research 88
                (0x4307B0, "cmp dword ptr [eax + 0x2ea84], 2"),     # the dam at Engineering 2
                (0x430422, "mov edx, 3"),                           # the ruins at Engineering 3 and Culture 3
                (0x43042F, "cmp dword ptr [eax + 0x2ea74], edx"),
                (0x4601DF, "cmp dword ptr [eax + 0x2ea8c], 3"),     # builders: the hospital at Medicine 3
                (0x4601F2, "cmp dword ptr [edx + 0x2ea84], 3"),     # builders: Engineering 3
                (0x461AA6, "call 0x425850"),                        # the culture roll ...
                (0x425856, "lea eax, [eax + eax*2]")):              # ... 3 x Culture
            self.assertEqual(self.exe.instruction(address), instruction, hex(address))

    def test_the_dam_restarts_the_regrowth(self) -> None:
        self.assertEqual(self.exe.instruction(0x464213), "mov dword ptr [edx + 0x2ead8], 0")
        self.assertEqual(self.exe.instruction(0x4642D2), "imul eax, eax, 0x960")
        self.assertEqual(self.exe.instruction(0x4642DE), "sar eax, 2")

    def test_the_stew_routine_has_eighteen_cases(self) -> None:
        self.assertEqual(self.exe.instruction(0x461051), "cmp eax, 0x11")
        targets = self.exe.u32(0x461510, 18)
        self.assertEqual(targets[0], 0x46106A)
        self.assertEqual(self.exe.instruction(0x4610AF), "mov dword ptr [edx + edi + 0x53c], 1")   # 2: sick
        self.assertEqual(self.exe.instruction(0x4610D3), "mov dword ptr [eax + edi + 0x53c], 0")   # 3: cured
        self.assertEqual(self.exe.instruction(0x461486), "push 0x32")                              # 17: 50 + 0..49
        self.assertEqual(self.exe.instruction(0x4614D8), "push 0x19")                              # 18: 15 + 0..24


if __name__ == "__main__":
    unittest.main()
