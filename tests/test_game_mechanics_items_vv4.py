"""The Tree of Life's Game Mechanics entries for every technology level, puzzle, building, item, stew and patcher
upgrade (src/vv_game_mechanics_items_vv4.py): each entry and its label pinned, and the entries checked against the
game's own tables -- the technologies (the game's own text) and their prices, the puzzles, and the seven buildings'
build rates read from the stock executable."""
from __future__ import annotations

import re
import struct
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_items_vv4 as items  # noqa: E402
import vv_game_mechanics_vv4 as vv4  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
TEXT = ROOT / "assets" / "text-changes" / "vv4-sm-base.xml"          # the game's own sm.xml
LABEL = {gm.RUNNING: "E", gm.CODE: "C", gm.OWNER: "O", gm.CLAMP: "K", False: "U"}

PINS = (
    ("technology", "The Tech screen", "C", ""),
    ("technology", "Science level 1", "E", ""), ("technology", "Science level 2", "E", "U"),
    ("technology", "Science level 3", "E", ""),
    ("technology", "Medicine level 1", "C", ""), ("technology", "Medicine level 2", "C", ""),
    ("technology", "Medicine level 3", "C", "U"),
    ("technology", "Learning level 1", "C", ""), ("technology", "Learning level 2", "C", ""),
    ("technology", "Learning level 3", "C", "U"),
    ("technology", "Construction level 1", "U", ""), ("technology", "Construction level 2", "U", "U"),
    ("technology", "Construction level 3", "U", "U"),
    ("technology", "Food Mastery level 1", "E", ""), ("technology", "Food Mastery level 2", "E", ""),
    ("technology", "Food Mastery level 3", "E", ""),
    ("technology", "Dendrology level 1", "U", ""), ("technology", "Dendrology level 2", "U", ""),
    ("technology", "Dendrology level 3", "U", ""),
    ("puzzle", "The Cutting Tool", "U", ""),
    ("puzzle", "The Stream", "E", ""),
    ("puzzle", "Boiling Water", "U", ""),
    ("puzzle", "Soap Invented", "U", ""),
    ("puzzle", "The Butterflies", "U", ""),
    ("puzzle", "The Frog Rescue", "U", ""),
    ("puzzle", "The Cooking Pit", "C", ""),
    ("puzzle", "Cloth Invented", "U", ""),
    ("puzzle", "The Nursery School", "U", ""),
    ("puzzle", "The Mossy Rocks", "E", ""),
    ("puzzle", "The Grand Feast", "E", ""),
    ("puzzle", "Fishing Nets", "E", "U"),
    ("puzzle", "Pruning the Tree", "E", "U"),
    ("puzzle", "Honoring the Tree", "E", ""),
    ("puzzle", "Purify Tree", "E", "U"),
    ("puzzle", "Decorating the Tree", "E", "U"),     # the hummingbird's clock, not traced (2026-10-27)
    ("building", "Building in general", "E", "UC"),
    ("building", "Hut 1", "C", ""),
    ("building", "Hut 2", "E", "U"),
    ("building", "Hut 3", "E", "U"),
    ("building", "The Clothing Hut", "E", "U"),
    ("building", "The Love Shack", "C", ""),
    ("building", "The Nursery School (the building)", "E", "U"),
    ("building", "The Hospital", "C", "U"),
    ("building", "Fixing huts", "C", "U"),
    ("building", "The Fire Pit", "E", "O"),
    ("item", "The herbs", "E", ""),
    ("item", "Hot rocks", "E", "OE"),
    ("item", "A ready stew", "E", ""),
    ("item", "The grate", "O", ""),
    ("item", "Eating a stew", "E", ""),
    ("item", "Spicy stew", "E", ""),
    ("item", "Spicy, spicy, sweet stew", "E", ""),
    ("item", "Spicy, spicy, soapy stew", "E", ""),
    ("item", "Spicy, sweet, sweet stew", "E", ""),
    ("item", "The Grand Feast stew", "E", ""),
    ("item", "Spicy, soapy, soapy stew", "E", ""),
    ("item", "Sweet stew", "E", ""),
    ("item", "Sweet, sweet, soapy stew", "E", ""),
    ("item", "Healing stew", "E", ""),
    ("item", "Soapy stew", "E", ""),
    ("item", "Soap", "E", ""),
    ("item", "Soapy herbs in salt water", "U", ""),
    ("item", "A failed stew", "E", ""),
    ("item", "Blackberries", "E", ""),
    ("item", "Fruit", "E", ""),
    ("item", "Fish and the Golden Fish", "E", ""),
    ("item", "Crabs", "E", "O"),
    ("item", "Mushrooms", "E", "EU"),
    ("item", "The Fish Scale collection", "E", ""),
    ("item", "The Lab Equipment collection", "E", ""),
    ("item", "The Mausoleum Mural collection", "E", ""),
    ("item", "The Wind Flute collection", "E", "O"),
    ("item", "Collectibles", "E", ""),
    ("item", "New clothes", "C", "U"),
    ("item", "A snack at the food bin", "E", ""),
    ("patcher", "Free Origins upgrades", "U", ""),
    ("patcher", "Time Warp", "K", ""),
) + tuple(("patcher", name, "U", "") for name in (
    "Island Event", "Barrel of Babies", "Tech Point Doubler", "Food Point Doubler", "Full Heal / Cure All",
    "Complete All Collections", "Reset All Collections",
    "Equal Division of Labor (Includes Parenting / No Parenting)", "Clear All Skill Preferences",
    "Check Highest Skill (Includes Parenting / No Parenting)", "All Villagers Like Running",
    "Grant Full Mastery to All Villagers", "All Villagers are Exactly 18", "Change Appearance for All",
    "Grant Youth", "Grant Full Mastery", "Grant Running", "Set Age to 18", "Change Appearance",
    "Pick Island Event", "Custom Island Event", "Choose Time Skip Amount", "Difficulty Settings"))

COUNTS = {"technology": 19, "puzzle": 16, "building": 10, "item": 30, "patcher": 25}


class Exe:
    def __init__(self, path: Path) -> None:
        import pefile
        pe = pefile.PE(str(path), fast_load=True)
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.image = pe.get_memory_mapped_image()

    def i32(self, va: int) -> int:
        return struct.unpack_from("<i", self.image, va - self.base)[0]

    def at(self, start: int, end: int) -> bytes:
        return self.image[start - self.base:end - self.base]


def exe() -> Exe:
    if not EXE.is_file():
        raise unittest.SkipTest(f"{EXE} is not here (copy research\\stock-executables)")
    try:
        return Exe(EXE)
    except ImportError:
        raise unittest.SkipTest("pefile is not installed")


class Entries(unittest.TestCase):
    def test_every_entry_and_its_label_is_pinned(self) -> None:
        got = tuple((e.kind, e.name, LABEL[e.verified], "".join(LABEL[ok] for _, ok in e.subs))
                    for e in items.entries())
        self.assertEqual(got, PINS)
        self.assertEqual(Counter(e.kind for e in items.entries()), Counter(COUNTS))

    def test_facts_are_the_entries_in_their_groups(self) -> None:
        facts = items.item_facts()
        self.assertEqual(len(facts), sum(1 + len(e.subs) for e in items.entries()))
        for fact in facts:
            self.assertIn(fact.group, items.ITEM_GROUPS)
            self.assertIn(fact.verified, (gm.RUNNING, gm.CODE, gm.OWNER, gm.CLAMP, False))
            self.assertIsNone(fact.due)
        self.assertEqual([f.text for f in facts if not f.sub], [f"{e.name}: {e.text}" for e in items.entries()])
        self.assertEqual(len({e.name for e in items.entries()}), len(items.entries()))
        self.assertFalse(set(items.ITEM_GROUPS) & set(gm.GROUPS))
        import vv_game_mechanics_items_vv3 as vv3_items
        self.assertEqual(items.ITEM_GROUPS, vv3_items.ITEM_GROUPS)       # one set of groups for both games

    def test_the_general_rules_page_keeps_every_line(self) -> None:
        for fact in items.item_facts():
            self.assertIsNone(re.match(r"^[A-Z][A-Za-z' ]{0,30}: -?[\d,]+\b", fact.text), fact.text)
            self.assertIsNone(re.search(r"\b(19[67]\d|20\d\d)\b", fact.text), fact.text)
            self.assertNotIn("could not be read", fact.text)

    def test_the_owners_settled_facts(self) -> None:
        text = gm.render(items.item_facts())
        self.assertIn("• The grate: the pot can be emptied by dropping a villager on the grate.", text)
        self.assertIn("Some stews can be reheated by putting another hot rock in the pot.", text)
        self.assertNotIn("UNCONFIRMED  The grate", text)
        # Anything from the cauldron is a stew: soap and the failed mixes are entries among the stews.
        names = [e.name for e in items.entries()]
        self.assertLess(names.index("Spicy stew"), names.index("Soap"))
        self.assertLess(names.index("Soap"), names.index("A failed stew"))


class TheGamesOwnTables(unittest.TestCase):
    def test_every_technology_and_its_prices(self) -> None:
        text = TEXT.read_text(encoding="utf-8")
        labels = re.findall(r'<Text id="eTech(\w+)Label">\s*([^<\n]+?)\s*\n', text)
        self.assertEqual(tuple(name for _, name in labels), items.TECHS)
        data = exe()
        names = {e.name: e for e in items.entries()}
        for tech_id, name in enumerate(items.TECHS):
            # 0x41E220: the price of level L + 1 is dword [0x4BC18C + 4 * (L + 1 + 3 * id)].
            table = (data.i32(0x4BC18C + 4 * (2 + 3 * tech_id)), data.i32(0x4BC18C + 4 * (3 + 3 * tech_id)))
            self.assertEqual(table, items.TECH_PRICES[name], name)
            self.assertEqual(data.i32(0x4BC18C + 4 * (1 + 3 * tech_id)), 0, name)      # level 1 is never bought
            self.assertTrue(names[f"{name} level 1"].text.startswith("a new village's level, no price."))
            for level, price in zip((2, 3), table):
                self.assertTrue(names[f"{name} level {level}"].text.startswith(f"{price:,} tech points."), name)
        # Every technology starts at 1 (0x41E150) and stops at 3 (0x41E1D0: cmp eax, 3; jge).
        self.assertEqual(data.at(0x41E1D8, 0x41E1E1), bytes.fromhex("8b44b50083f8037d34"))

    def test_every_puzzle(self) -> None:
        names = {e.name: e for e in items.entries() if e.kind == items.PUZZLE}
        self.assertEqual(list(names), list(vv4.PUZZLE_NAMES.values()))
        for pid, name in vv4.PUZZLE_NAMES.items():
            threshold = vv4.PUZZLE_THRESHOLDS[pid]
            steps = f"{threshold:,} step" + ("s" if threshold > 1 else "")
            self.assertRegex(names[name].text, rf"\b(in|after) {re.escape(steps)}\b", name)

    def test_every_building_and_its_build_rate(self) -> None:
        data = exe()
        code = data.at(0x431000, 0x431400)
        # mov dword ptr [esi + 0x24], imm32: each building's build points a step, projects 19..25 in order.
        rates = [struct.unpack_from("<i", code, m.start() + 3)[0] for m in re.finditer(rb"\xc7\x46\x24", code)]
        self.assertEqual(rates, list(items.BUILDINGS.values()))
        by_name = {e.name: e.text for e in items.entries() if e.kind == items.BUILDING}
        for name, rate in items.BUILDINGS.items():
            key = name if name in by_name else f"{name} (the building)"
            self.assertIn(f"adds {rate} build point", by_name[key], name)
            self.assertIn(f"({-(-items.BUILD_TOTAL // rate):,} steps)", by_name[key], name)

    def test_the_new_clothes_check(self) -> None:
        data = exe()
        # 0x46F75B: push 0x16 (project 22, the Clothing Hut) ... cmp [0x4D6F88], 0x1388 (5,000 tech points).
        self.assertEqual(data.at(0x46F75B, 0x46F75D), bytes.fromhex("6a16"))
        self.assertEqual(data.at(0x46F76B, 0x46F775), bytes.fromhex("813d886f4d0088130000"))


class Patcher(unittest.TestCase):
    def test_every_setting_is_a_patch_the_patcher_knows(self) -> None:
        for fact in items.item_facts():
            for name in re.findall(r'With the patcher \("([^"]+)"', fact.text):
                self.assertNotRegex(name, r"^vv\d_", fact.text)

    def test_the_defaults_mirror_the_patchers(self) -> None:
        try:
            import vv_fun_patcher_gui as gui
        except Exception as exc:  # noqa: BLE001 -- no Tk: the mirror cannot be compared here
            raise unittest.SkipTest(f"the patcher's window could not be imported ({exc})")
        off = {fid for fid in gui.DEFAULT_OFF_FUN_PATCH_IDS if fid.startswith("vv4_")}
        self.assertEqual(off, set(items.DEFAULT_OFF))

    def test_the_origins_prices(self) -> None:
        source = (ROOT / "scripts" / "build_vv4_origins_feature.py").read_text(encoding="utf-8")
        self.assertIn("for value in (50000, 30000, 75000, 500000, 500000, 30000):", source)
        self.assertIn("for value in (50000, 100000, 40000, 50000, 5000):", source)
        icons = (ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c").read_text(encoding="utf-8")
        self.assertIn("Change Appearance for All for 450,000 tech", icons)
        self.assertIn("All Villagers are Exactly 18 for 1,000,000 tech", icons)
        by_name = {e.name: e.text for e in items.entries() if e.kind == items.PATCHER}
        for name, price in (("Time Warp", 50_000), ("Island Event", 30_000), ("Barrel of Babies", 75_000),
                            ("Tech Point Doubler", 500_000), ("Food Point Doubler", 500_000),
                            ("Full Heal / Cure All", 30_000), ("Grant Youth", 50_000),
                            ("Grant Full Mastery", 100_000), ("Grant Running", 40_000), ("Set Age to 18", 50_000),
                            ("Change Appearance", 5_000), ("Change Appearance for All", 450_000),
                            ("All Villagers are Exactly 18", 1_000_000)):
            self.assertIn(f"{price:,} tech points", by_name[name], name)


if __name__ == "__main__":
    unittest.main()
