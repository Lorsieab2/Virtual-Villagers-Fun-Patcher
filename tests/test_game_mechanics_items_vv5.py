"""New Believers' "Technologies, items and buildings" group (src/vv_game_mechanics_items_vv5.py): every entry and its
label is pinned, and the entries name every technology, God power, puzzle and building the stock exe's own tables
hold (the tech cost table and labels, the God powers' cost table, and every project the game registers)."""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_items_vv5 as items  # noqa: E402
import vv_game_mechanics_powers_vv5 as powers  # noqa: E402

STOCK = ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe"
BASE = 0x400000
REGISTER = 0x43ABB0                     # the projects' registration: (this, id, points needed)
E, C, U = "VERIFIED-E", "VERIFIED-C", "UNCONFIRMED"

# Every entry, in order: (kind, name, cost, label).
PINNED = (
    ("technology", "The Tech screen", "tech points", C),
    ("technology", "Science level 1", "every village starts at it", E),
    ("technology", "Science level 2", "8,000 tech points", E),
    ("technology", "Science level 3", "70,000 tech points", E),
    ("technology", "Medicine level 1", "every village starts at it", E),
    ("technology", "Medicine level 2", "5,000 tech points", E),
    ("technology", "Medicine level 3", "50,000 tech points", E),
    ("technology", "Learning level 1", "every village starts at it", E),
    ("technology", "Learning level 2", "4,000 tech points", E),
    ("technology", "Learning level 3", "35,000 tech points", E),
    ("technology", "Construction level 1", "every village starts at it", C),
    ("technology", "Construction level 2", "5,000 tech points", C),
    ("technology", "Construction level 3", "65,000 tech points", C),
    ("technology", "Food Mastery level 1", "every village starts at it", E),
    ("technology", "Food Mastery level 2", "3,000 tech points", E),
    ("technology", "Food Mastery level 3", "40,000 tech points", E),
    ("technology", "Spirituality level 1", "every village starts at it", E),
    ("technology", "Spirituality level 2", "8,000 tech points", E),
    ("technology", "Spirituality level 3", "80,000 tech points", E),
    ("power", "Divine Energy", "how it is earned", E),
    ("power", "Spawn Butterflies", "10 Divine Energy", E),
    ("power", "Swarm of Bees", "25 Divine Energy", E),
    ("power", "Sunshine", "50 Divine Energy", E),
    ("power", "Lightning Strike", "100 Divine Energy", E),
    ("power", "Hand of Bloom", "150 Divine Energy", E),
    ("power", "Tempest", "300 Divine Energy", E),
    ("power", "Fog of Doom", "400 Divine Energy", E),
    ("power", "Time Warp", "500 Divine Energy", E),
    ("power", "Revive", "600 Divine Energy", E),
    ("power", "Grant Youth", "700 Divine Energy", E),
    ("power", "Earthquake", "800 Divine Energy", E),
    ("puzzle", "The Sick Heathen", "cure the sick Heathen Doctor", E),
    ("puzzle", "The Prison Break", "30 successful \"Making a granary out of the fence\" building actions", C),
    ("puzzle", "The Hungry Totem", "villagers dismantle it (\"Dismantling the Hungry Totem\")", C),
    ("puzzle", "The Knowing Totem", "villagers dismantle it (\"Dismantling the Knowing Totem\")", C),
    ("puzzle", "The Hydroponic Farm", "30 points, from the aqueduct repair", E),
    ("puzzle", "The Buried Mausoleum", "villagers restore it (\"Restoring the mausoleum\")", C),
    ("puzzle", "The Blocking Totem", "villagers dismantle it (\"Dismantling the Blocking Totem\")", U),
    ("puzzle", "The Hollow Totem", "village children break it (\"Squeezing into the Hollow Totem\")", U),
    ("puzzle", "The Heathen Builder", "a build-off with the Heathen Master Builder", U),
    ("puzzle", "The Lake", "2 points", E),
    ("puzzle", "The Pain Totem", "a Lightning Strike on it, then villagers take it down", E),
    ("puzzle", "The Rainbow Totem", "villagers put three dyes in the pools and dismantle it", U),
    ("puzzle", "The Heathen Scientist", "a proof the Heathen Master Scientist examines", U),
    ("puzzle", "The Tribute Statue", "three building stages", E),
    ("puzzle", "The Blind Totem", "villagers make and install a golden eye (panning, smelting, installing)", E),
    ("puzzle", "The Heathen Chief", "four necklace pieces brought to the Chief", E),
    ("puzzle", "The Heathen Parent", "convert the Heathen Mommy", E),
    ("building", "Hut 1", "2,000 points, 12 a successful build action (167 actions)", C),
    ("building", "Hut 2", "2,000 points, 4 a successful build action (500 actions)", C),
    ("building", "Hut 3", "2,000 points, 1 a successful build action (2,000 actions)", C),
    ("building", "The Clothing Hut", "2,000 points, 12 a successful build action (167 actions)", C),
    ("building", "The Love Shack", "2,000 points, 400 a successful build action (5 actions)", C),
    ("building", "The Nursery School", "2,000 points, 50 a successful build action (40 actions)", C),
    ("building", "The fire pit", "3 points, from \"Gathering dry grass\", \"Gathering firewood\" and \"Starting a "
                                 "fire\"", E),
    ("building", "Fixing a hut (the repair)", "free; a builder's own job", C),
    ("item", "Brown mushroom", "appears on the island at random, see Mushrooms", E),
    ("item", "Red (rare) mushroom", "appears on the island at random, see Mushrooms", E),
    ("item", "Relics (the first collectible set, 24 pieces)", "appear on the island at random, 82% common, 13% "
                                                              "uncommon, 5% rare; see Collectibles", E),
    ("item", "Lab gear (the second collectible set, 24 pieces)", "appear at random only once the Knowing Totem is "
                                                                 "down", E),
    ("item", "A change of clothes", "5,000 tech points, at the built Clothing Hut", C),
    ("item", "Tech points", "how they are earned", E),
    ("patcher", "Time Warp", "50,000 tech points", C),
    ("patcher", "Island Event", "30,000 tech points", C),
    ("patcher", "Barrel of Babies", "75,000 tech points", C),
    ("patcher", "Tech Point Doubler", "500,000 tech points", C),
    ("patcher", "Food Point Doubler", "500,000 tech points", C),
    ("patcher", "Full Heal / Cure All", "30,000 tech points", C),
    ("patcher", "Complete All Collections", "1,000,000 tech points", C),
    ("patcher", "Reset All Collections", "1,000,000 tech points", C),
    ("patcher", "Grant Running to All Villagers", "1,000,000 tech points", C),
    ("patcher", "Grant Full Mastery to All Villagers", "1,000,000 tech points", C),
    ("patcher", "All Villagers are Exactly 18", "1,000,000 tech points", C),
    ("patcher", "Equal Division of Labor (Includes Parenting)", "1,000,000 tech points", C),
    ("patcher", "Equal Division of Labor (No Parenting)", "1,000,000 tech points", C),
    ("patcher", "Change Appearance for All", "450,000 tech points", C),
    ("patcher", "Clear All Skill Preferences", "500,000 tech points", C),
    ("patcher", "Check Highest Skill (Includes Parenting)", "1,000,000 tech points", C),
    ("patcher", "Check Highest Skill (No Parenting)", "1,000,000 tech points", C),
    ("patcher", "Grant Youth", "50,000 tech points", C),
    ("patcher", "Grant Full Mastery", "100,000 tech points", C),
    ("patcher", "Grant Running", "40,000 tech points", C),
    ("patcher", "Set Age to 18", "50,000 tech points", C),
    ("patcher", "Change Appearance", "5,000 tech points", C),
    ("patcher", "Story / Cheat Upgrades", "0 tech points", C),
)

# Every sub-line's label, by the entry it is under (the entries not named have none).
PINNED_SUBS = {
    "Science level 2": (C, E), "Medicine level 2": (U,), "Learning level 1": (C,), "Learning level 3": (C,),
    "Divine Energy": (U,), "The Hungry Totem": (U,), "The Knowing Totem": (U,), "The Hydroponic Farm": (U,),
    "The Tribute Statue": (U, C), "The Heathen Chief": (U,), "The Nursery School": (C,), "The fire pit": (U,),
    "Fixing a hut (the repair)": (C, C), "Red (rare) mushroom": (E, U), "Barrel of Babies": (U,),
    "Story / Cheat Upgrades": (C,),
}


def _image():
    try:
        import pefile
    except ImportError:
        return None
    if not STOCK.exists():
        return None
    return bytes(pefile.PE(str(STOCK)).get_memory_mapped_image())


def _u32(img: bytes, va: int) -> int:
    return struct.unpack_from("<I", img, va - BASE)[0]


def _class(img: bytes, vtable: int) -> str:
    """A vtable's class name from its RTTI (complete object locator -> type descriptor -> ".?AV<name>@@")."""
    locator = _u32(img, vtable - 4)
    descriptor = _u32(img, locator + 12)
    end = img.index(b"\0", descriptor + 8 - BASE)
    name = img[descriptor + 8 - BASE:end].decode("latin1")
    return name[4:-2] if name.startswith(".?AV") else name


def registered_projects(img: bytes) -> dict[int, tuple[str, int, int | None]]:
    """Every project the game registers: {id: (class, points needed, points a build action adds or None)}, found
    from each direct call of 0x43ABB0 and the pushes and vtable store right before it."""
    out: dict[int, tuple[str, int, int | None]] = {}
    text_start, text_end = 0x401000 - BASE, 0x48F000 - BASE
    for at in range(text_start, text_end - 5):
        if img[at] != 0xE8 or at + 5 + struct.unpack_from("<i", img, at + 1)[0] != REGISTER - BASE:
            continue
        c = at
        if img[c - 6:c - 4] == b"\xC7\x06" and img[c - 9] == 0x6A and img[c - 7] == 0x56:
            pid, vtable = img[c - 8], _u32(img, c - 4 + BASE)
            if img[c - 14] == 0x68:
                points = struct.unpack_from("<I", img, c - 13)[0]
            elif img[c - 13] == 0x6A and img[c - 11:c - 9] == b"\x8B\xF1":
                points = img[c - 12]
            else:
                continue
        elif img[c - 5] == 0x6A and img[c - 3] == 0x6A and img[c - 1] == 0x56:     # push points; push id; push esi
            pid, points = img[c - 2], img[c - 4]
            store = img.rfind(b"\xC7\x06", c - 48, c)
            if store < 0:
                continue
            vtable = _u32(img, store + 2 + BASE)
        else:
            continue
        # A building's points per action: its constructor's "mov dword ptr [esi+0x24], imm32" after the call.
        tail = img[c + 5:c + 0x60]
        found = tail.find(b"\xC7\x46\x24")
        per = struct.unpack_from("<I", tail, found + 3)[0] if found >= 0 else None
        out[pid] = (_class(img, vtable), points, per)
    return out


class Pinned(unittest.TestCase):
    def test_every_entry_and_its_label(self) -> None:
        got = tuple((e.kind, e.name, e.cost, items.LABELS.get(e.verified, U)) for e in items.entries())
        self.assertEqual(got, PINNED)

    def test_every_sub_line_and_its_label(self) -> None:
        got = {e.name: tuple(items.LABELS.get(v, U) for _, v in e.subs) for e in items.entries() if e.subs}
        self.assertEqual(got, PINNED_SUBS)

    def test_the_facts_carry_the_labels(self) -> None:
        facts = items.item_facts()
        self.assertTrue(all(f.group == items.ITEMS_GROUP for f in facts))
        self.assertEqual(len([f for f in facts if not f.sub]), len(PINNED))
        rendered = gm.render(facts)
        for fact in facts:
            self.assertIn(items.label(fact), (E, C, U))
            self.assertEqual(items.label(fact) == U, not fact.confirmed)
        self.assertEqual(rendered.count(gm.UNCONFIRMED), sum(1 for f in facts if items.label(f) == U))
        self.assertIn(items.ITEMS_GROUP, items.GROUPS)

    def test_the_words(self) -> None:
        text = gm.render(items.item_facts())
        lower = text.lower()
        for banned in ("belief", "etc.", "some effect", "various"):
            self.assertNotIn(banned, lower)
        # Real-life units, the stock value first, then the patched one.
        self.assertIn("3, 6 or 10 real-life minutes on Fast, Normal or Slow", text)
        self.assertIn("With the patcher (\"Learning Skills Never Fails\", off by default)", text)
        self.assertIn("With the patcher (\"Enable Origins-Exclusive Features\", on by default)", text)
        self.assertIn("With the patcher (\"Story / Cheat Upgrades\", off by default)", text)
        # The settled rules: Grant Youth delays a pregnant villager's birth (described, not fixed).
        self.assertIn("the birth comes that much later (0x41FEB0)", text)

    def test_key_numbers(self) -> None:
        text = gm.render(items.item_facts())
        for words in ("÷ 11", "÷ 9", "÷ 7 (catching up ÷ 5)", "5.25%", "1.75%", "a brown mushroom 6 becomes 9",
                      "a red one 70", "0.281% (1 in 356)", "0.171% (1 in 585)", "0.0641% (1 in 1,560)",
                      "34.03% at skill 0", "takes 5,000 tech points (0x46CEC7)", "0 to 28, 0x419CE0",
                      "fixes it 70% of the time (0x463F47)", "every mushroom picked up"):
            self.assertIn(words, text)

    def test_default_off_matches_the_patcher(self) -> None:
        try:
            import vv_fun_patcher_gui as gui
        except Exception as exc:  # noqa: BLE001 -- no display or Tk: the GUI module cannot be imported here
            self.skipTest(f"vv_fun_patcher_gui could not be imported: {exc}")
        for feature in items.PATCHES:
            self.assertEqual(feature in items.DEFAULT_OFF, not gui.default_fun_patch_selection(feature), feature)
            self.assertNotEqual(gm.feature_name(feature), feature, f"{feature} has no name in the catalog")


class FromTheGamesOwnTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.img = _image()

    def setUp(self) -> None:
        if self.img is None:
            self.skipTest("the stock VV5 exe (inputs/vv5-stock-copy) or pefile is missing")

    def names(self, kind: str) -> list[str]:
        return [e.name for e in items.entries() if e.kind == kind]

    def test_every_technology(self) -> None:
        labels = re.findall(rb"([A-Za-z ]+)\0+eTech(\w+)Label\0", self.img[0xA7C00:0xA7D00])
        self.assertEqual(len(labels), len(items.TECHS))
        self.assertEqual({name.decode() for name, _ in labels}, {name for _, name, _, _ in items.TECHS})
        table = struct.unpack_from("<19i", self.img, items.TECH_TABLE - BASE)
        for tid, name, two, three in items.TECHS:
            # 0x4236D0: table[3 x id + level + 1] is the price of the next level.
            self.assertEqual((table[3 * tid + 2], table[3 * tid + 3]), (two, three), name)
            for level in (1, 2, 3):
                self.assertIn(f"{name} level {level}", self.names("technology"))

    def test_every_god_power(self) -> None:
        costs = struct.unpack_from("<11i", self.img, 0x498840 - BASE)
        self.assertEqual(costs, tuple(cost for _, cost, _ in powers.TABLE))
        entries = {e.name: e.cost for e in items.entries() if e.kind == "power"}
        for (name, _, hint), cost in zip(powers.TABLE, costs):
            self.assertIn(hint.encode("latin1"), self.img)
            self.assertEqual(entries[name], f"{cost:,} Divine Energy")
        self.assertEqual(len(entries), 1 + len(costs))      # and Divine Energy itself

    def test_every_puzzle_and_building(self) -> None:
        projects = registered_projects(self.img)
        # The 16 puzzles of the Puzzles screen (ids 1 to 16), the Heathen Mommy's (17, the patcher's restored puzzle),
        # the fire pit and the buildings, the Nursery School's lessons milestone (0) and The Last Heathen (25, no
        # writer traced: not listed).
        self.assertEqual(set(projects), set(range(0, 26)))
        for pid, (name, cls) in items.PUZZLE_CLASSES.items():
            self.assertEqual(projects[pid][0], cls, pid)
            self.assertIn(name, self.names("puzzle"))
            self.assertIn(f"{name}\n\n".encode("latin1"), self.img)      # the game's own completion tip
        self.assertEqual(projects[17][0], "CHeathenMommyPuzzle")
        self.assertIn("The Heathen Parent", self.names("puzzle"))
        for pid, (name, cls, points, per) in items.BUILDING_CLASSES.items():
            self.assertEqual(projects[pid][:2], (cls, points), pid)
            if per is not None:
                self.assertEqual(projects[pid][2], per, pid)
            self.assertIn(name, self.names("building"))
        self.assertEqual(projects[5][:2], ("CHydroFarm", 30))
        self.assertEqual(projects[10][:2], ("CRestoreLake", 2))
        accounted = set(items.PUZZLE_CLASSES) | set(items.BUILDING_CLASSES) | {0, 17, 25}
        self.assertEqual(accounted, set(projects))

    def test_the_clothes(self) -> None:
        img = self.img
        self.assertEqual(img[0x46CE93 - BASE:0x46CE9D - BASE], bytes.fromhex("813DF8D5510088130000"))
        self.assertEqual(img[0x46CEC7 - BASE:0x46CECC - BASE], bytes.fromhex("6878ECFFFF"))      # push -5000
        self.assertEqual(img[0x419E94 - BASE:0x419E99 - BASE], bytes.fromhex("6888130000"))      # push 5000
        self.assertEqual(img[0x419D06 - BASE:0x419D0D - BASE], bytes.fromhex("83BEA45000001C"))  # wraps past 28
        self.assertIn(b"Do you want to spend 5000 tech points to change this villager's clothes?", img)


if __name__ == "__main__":
    unittest.main()
