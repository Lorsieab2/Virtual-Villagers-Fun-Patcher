"""The Secret City's Game Mechanics entries for every technology level, puzzle, building, item, potion and patcher
upgrade (src/vv_game_mechanics_items_vv3.py): each entry and its label pinned, and the entries checked against the
game's own tables -- the technologies and their prices, the puzzles and their thresholds, and the huts -- read from
the stock executable."""
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
import vv_game_mechanics_counts as counts  # noqa: E402
import vv_game_mechanics_items_vv3 as items  # noqa: E402
import vv_game_mechanics_vv3 as vv3  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
LABEL = {gm.RUNNING: "E", gm.CODE: "C", gm.OWNER: "O", gm.CLAMP: "K", False: "U"}

# (kind, name, the entry's label, its further facts' labels): E emulated (VERIFIED-E), C traced (VERIFIED-C),
# O the owner's word, K the verified Time Warp clamp, U UNCONFIRMED.
PINS = (
    ("technology", "The Tech screen", "C", ""),
    ("technology", "Science level 1", "C", ""), ("technology", "Science level 2", "C", ""),
    ("technology", "Science level 3", "C", ""),
    ("technology", "Medicine level 1", "C", ""), ("technology", "Medicine level 2", "C", ""),
    ("technology", "Medicine level 3", "C", ""),
    ("technology", "Alchemy level 1", "E", ""), ("technology", "Alchemy level 2", "E", ""),
    ("technology", "Alchemy level 3", "E", ""),
    ("technology", "Restoration level 1", "C", ""), ("technology", "Restoration level 2", "C", ""),
    ("technology", "Restoration level 3", "C", ""),
    ("technology", "Leadership level 1", "C", ""), ("technology", "Leadership level 2", "C", ""),
    ("technology", "Leadership level 3", "C", ""),
    ("technology", "Nature level 1", "C", "E"), ("technology", "Nature level 2", "C", ""),
    ("technology", "Nature level 3", "C", "U"),
    ("technology", "Magic level 1", "C", ""), ("technology", "Magic level 2", "C", ""),
    ("technology", "Magic level 3", "C", ""),
    ("technology", "Choosing a faction", "C", "E"),
    ("puzzle", "Puzzles in general", "C", ""),
    ("puzzle", "The First Chief", "C", "UU"),
    ("puzzle", "The Bee Hive", "C", ""),
    ("puzzle", "The Alchemy Lab", "C", ""),
    ("puzzle", "The Roster of the Dead", "U", ""),
    ("puzzle", "Weather Dancing", "U", ""),
    ("puzzle", "The Lift", "C", "U"),
    ("puzzle", "The Ruins", "C", ""),
    ("puzzle", "The Ancient Bath", "C", ""),
    ("puzzle", "The Statue", "C", ""),
    ("puzzle", "The Orchard", "C", ""),
    ("puzzle", "The Sharks", "C", ""),
    ("puzzle", "Aromatherapy", "C", ""),
    ("puzzle", "The Ash Key", "E", ""),
    ("puzzle", "The Cliff Key", "U", ""),
    ("puzzle", "The Clam Key", "U", ""),
    ("puzzle", "The Chief and the Princess", "U", ""),
    ("building", "Building in general", "C", "C"),
    ("building", "The first hut", "C", ""),
    ("building", "The second hut", "C", ""),
    ("building", "The third hut", "C", ""),
    ("building", "The fourth hut", "C", ""),
    ("building", "Fixing huts", "C", "U"),
    ("building", "The campfire", "C", "O"),
    ("building", "The medical area", "C", "U"),
    ("item", "The herbs", "C", "OC"),
    ("item", "Brewing a potion", "E", "COO"),   # the code's spoil time, then the owner's word (2026-10-27)
    ("item", "Drinking a potion", "E", "O"),
    ("item", "The recipe book", "C", ""),
) + tuple(("item", items._potion_name(p), "C", "") for p in range(41)) + (
    ("item", "Fruit", "C", "UUU"),
    ("item", "Honey", "C", ""),
    ("item", "Fish and the crab", "C", ""),
    ("item", "Mushrooms", "E", "EU"),
    ("item", "Collectibles", "C", ""),
    ("item", "Turtle Shell Collection", "C", "C"),
    ("item", "Coral Collection", "C", "C"),
    ("item", "Tablet Collection", "C", "C"),
    ("item", "Feather Collection", "C", "C"),
    ("item", "All four collections", "C", ""),
    ("item", "Grant Food (the chief's power)", "C", ""),
    ("item", "Educate the Children (the chief's power)", "C", "UU"),
    ("item", "Point Out a Rare Collectible (the chief's power)", "C", "E"),
    ("item", "New clothes", "C", "U"),
    ("item", "Wood for the campfire", "C", ""),
    ("item", "Water for the Ash Key", "E", ""),
    ("item", "A snack at the food bin", "C", ""),
    ("patcher", "Free Origins upgrades", "U", ""),
    ("patcher", "Time Warp", "K", ""),
) + tuple(("patcher", name, "U", "") for name in (
    "Island Event", "Barrel of Babies", "Tech Point Doubler", "Food Point Doubler", "Complete All Collections",
    "Reset All Collections", "Equal Division of Labor (Includes Parenting / No Parenting)",
    "Clear All Skill Preferences", "Check Highest Skill (Includes Parenting / No Parenting)",
    "All Villagers Like Running", "Grant Full Mastery to All Villagers", "Make Villagers Young Adults",
    "Grant Youth", "Grant Full Mastery", "Grant Running", "Set Age to 18", "Change Appearance",
    "Pick Island Event", "Custom Island Event", "Choose Time Skip Amount", "Recharge Chief Powers",
    "Learning Skills Never Fails"))

COUNTS = {"technology": 23, "puzzle": 17, "building": 8, "item": 62, "patcher": 24}


class Exe:
    """The stock executable's image, read only (pefile maps the sections to their addresses)."""

    def __init__(self, path: Path) -> None:
        import pefile
        pe = pefile.PE(str(path), fast_load=True)
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.image = pe.get_memory_mapped_image()
        self.raw = path.read_bytes()

    def i32(self, va: int) -> int:
        return struct.unpack_from("<i", self.image, va - self.base)[0]


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
        heads = [f.text for f in facts if not f.sub]
        self.assertEqual(heads, [f"{e.name}: {e.text}" for e in items.entries()])
        self.assertEqual(len({e.name for e in items.entries()}), len(items.entries()))
        # Only the groups listed are used, none of them an existing group of the page.
        self.assertFalse(set(items.ITEM_GROUPS) & set(gm.GROUPS))

    def test_unconfirmed_lines_carry_the_label(self) -> None:
        text = gm.render(items.item_facts())
        self.assertIn(f"{gm.UNCONFIRMED}  The Roster of the Dead: solved after 700 steps", text)
        self.assertIn("• Alchemy level 1: a new village's level, no price.", text)

    def test_the_general_rules_page_keeps_every_line(self) -> None:
        # gm.general drops a line that reads like an amount or a date from the empty save: none of these may.
        for fact in items.item_facts():
            self.assertIsNone(re.match(r"^[A-Z][A-Za-z' ]{0,30}: -?[\d,]+\b", fact.text), fact.text)
            self.assertIsNone(re.search(r"\b(19[67]\d|20\d\d)\b", fact.text), fact.text)
            self.assertNotIn("could not be read", fact.text)

    def test_no_vague_words(self) -> None:
        for fact in items.item_facts():
            for word in ("etc", "some effect", "various", "and so on"):
                self.assertNotIn(word, fact.text.lower().replace("etc.", "etc"), fact.text)


class TheGamesOwnTables(unittest.TestCase):
    def test_every_technology_and_its_prices(self) -> None:
        data = exe()
        names = {e.name for e in items.entries()}
        # The Tech screen's own info strings name the seven technologies.
        for words in (b"Science Technology", b"Medicine Technology", b"Alchemy Technology",
                      b"Restoration Technology", b"Leadership Technology", b"Faction of Nature",
                      b"Faction of Magic"):
            self.assertIn(words, data.raw)
        self.assertEqual(items.TECHS, ("Science", "Medicine", "Alchemy", "Restoration", "Leadership", "Nature",
                                       "Magic"))
        for tech_id, name in enumerate(items.TECHS):
            # 0x427020: the price of level L + 1 is dword [0x4A818C + 4 * (L + 1 + 3 * id)].
            table = tuple(data.i32(0x4A818C + 4 * (level + 3 * tech_id)) for level in (1, 2, 3))
            self.assertEqual(table, items.TECH_PRICES[name], name)
            for level in (1, 2, 3):
                self.assertIn(f"{name} level {level}", names)
                entry = next(e for e in items.entries() if e.name == f"{name} level {level}")
                if level > items.START_LEVEL[name]:
                    self.assertTrue(entry.text.startswith(f"{table[level - 1]:,} tech points."), entry.text)
                else:
                    self.assertTrue(entry.text.startswith("a new village's level, no price."), entry.text)
        # A new village: 1, 1, 1, 1, 1, 0, 0 (0x426F40).
        start = data.image[0x426F40 - data.base:0x426F40 - data.base + 0x1C]
        self.assertEqual(start, bytes.fromhex("b801000000890189410489410889410c89411033c0894114894118c3"))
        self.assertEqual([items.START_LEVEL[n] for n in items.TECHS], [1, 1, 1, 1, 1, 0, 0])

    def test_every_puzzle_and_its_threshold(self) -> None:
        data = exe()
        names = {e.name: e for e in items.entries() if e.kind == items.PUZZLE}
        for pid, name in vv3.PUZZLE_NAMES.items():
            threshold = data.i32(0x49D230 + 4 * pid)
            self.assertEqual(threshold, vv3.PUZZLE_THRESHOLDS[pid], name)
            self.assertIn(name, names)
            steps = f"{threshold:,} step" + ("s" if threshold > 1 else "")
            self.assertRegex(names[name].text, rf"\b(in|after) {re.escape(steps)}\b", name)
        self.assertEqual(len(names), len(vv3.PUZZLE_NAMES) + 1)          # and "Puzzles in general"

    def test_every_hut(self) -> None:
        data = exe()
        projects = tuple(data.i32(0x49D0D0 + 4 * i) for i in range(4))   # hut i -> its project (0x4321E0)
        self.assertEqual(projects, items.HUT_PROJECTS)
        for project in projects:
            self.assertEqual(data.i32(0x49D230 + 4 * project), items.HUT_TOTAL)
        # The huts' start (0x4322F0 -> 0x4322C0): hut i in state i + 1, short by the remainder 0x49D0E0[state].
        short = tuple(data.i32(0x49D0E0 + 4 * (i + 1)) for i in range(4))
        self.assertEqual(short, items.HUT_START_SHORT)
        huts = [e for e in items.entries() if e.kind == items.BUILDING and e.name.endswith(" hut")]
        self.assertEqual([e.name for e in huts], ["The first hut", "The second hut", "The third hut",
                                                  "The fourth hut"])
        for entry, gap in zip(huts, short):
            words = f"starts {gap:,} build units short" if gap < items.HUT_TOTAL else "starts at 0 of 2,000"
            self.assertIn(words, entry.text)

    def test_the_new_clothes_check(self) -> None:
        data = exe()
        # 0x422892: push 0x18 (the fourth hut's project 24) ... cmp [0x582644], 0x1388 (5,000 tech points).
        self.assertEqual(data.image[0x422892 - data.base:0x422894 - data.base], bytes.fromhex("6a18"))
        self.assertEqual(data.image[0x4228A2 - data.base:0x4228AC - data.base],
                         bytes.fromhex("813d4426580088130000"))
        self.assertEqual(items.CLOTHES_PRICE, 5_000)

    def test_the_first_paying_research_skill(self) -> None:
        """Science 1, 2, 3 divide the Research skill by 11, 9, 7 (0x45934D, 0x4592E2, 0x459274: the magic-number
        divides) and, outside catch-up, divide that by the clock's rate x float 1/6 (0x426580: fild [ecx + 0x20];
        fmul dword [0x4808A0]) and cut it to a whole number (0x46EF58).  So on Normal (rate 6) and Slow (10) nothing
        is paid below twice the divisor, on Fast (3) nothing below the divisor."""
        data = exe()
        code = lambda start, size: data.image[start - data.base:start - data.base + size]  # noqa: E731
        self.assertEqual(code(0x426580, 9), bytes.fromhex("db4120d80da0084800"))
        sixth = struct.unpack("<f", code(0x4808A0, 4))[0]
        for at, magic, d in ((0x45934D, 0x2E8BA2E9, 11), (0x4592E2, 0x38E38E39, 9), (0x459274, 0x92492493, 7)):
            self.assertEqual(code(at, 5), b"\xb8" + struct.pack("<I", magic))
        for at in (0x4592C4, 0x459332, 0x459399):                                  # fdivr dword [esp + 0xc]
            self.assertEqual(code(at, 4), bytes.fromhex("d87c240c"))
        names = {e.name: e.text for e in items.entries()}
        for level, d, c in ((1, 11, 7), (2, 9, 7), (3, 7, 5)):
            first = {rate: next(s for s in range(1, 200) if int((s // d) / (rate * sixth)) >= 1) for rate in (3, 6, 10)}
            self.assertEqual(first, {3: d, 6: 2 * d, 10: 2 * d})
            self.assertIn(f"a session pays nothing below Research {d} on Fast speed, below Research {2 * d} on Normal "
                          f"or Slow speed, and below Research {c} while catching up", names[f"Science level {level}"])
            self.assertNotIn("(nothing below", names[f"Science level {level}"])

    def test_the_fruit_trees_two_thresholds(self) -> None:
        """The dispatcher (0x45AF9A) and the remembered-site continuation (0x45ADEA) take a tree at 10 or more fruit;
        the drop handler 0x4224D0 (region 0x18, 0x422BC3) queues the pick (action 0x7D, 0x422585) with no count
        check; the pick 0x4348F0 refuses a tree under 5 (0x434982)."""
        data = exe()
        code = lambda start, size: data.image[start - data.base:start - data.base + size]  # noqa: E731
        for at in (0x45AF9A, 0x45ADEA):
            self.assertEqual(code(at, 5), bytes.fromhex("83f80a7c14"))             # cmp eax, 10; jl skip
        self.assertEqual(code(0x434982, 6), bytes.fromhex("833cc6057c3c"))         # cmp [esi + eax*8], 5; jl
        self.assertEqual(code(0x422BC3, 7), b"\x68" + struct.pack("<I", 0x4224D0) + b"\x6a\x18")
        self.assertEqual(code(0x422585, 2), bytes.fromhex("6a7d"))
        for at in range(0x4224D0, 0x4225C2 - 4):                                   # no call of the fruit count
            if code(at, 1) == b"\xe8":
                self.assertNotEqual(at + 5 + struct.unpack("<i", code(at + 1, 4))[0], 0x434100)
        fruit = {e.name: e.text for e in items.entries()}["Fruit"]
        self.assertIn("The game sends a farmer to a tree by itself only while the tree holds 10 or more fruit. A "
                      "villager the player drops on a tree that is ready to pick goes to pick it at any count. The "
                      "pick itself needs 5 or more: under 5 the villager reacts instead, picks nothing and forgets "
                      "the tree.", fruit)
        self.assertNotIn("is picked only with 10 or more", fruit)

    def test_each_collection_against_the_exe(self) -> None:
        """Each collection has its own entry: the pickup's completion message for each 12-kind range (tips 720 to 723,
        in the order Turtle Shell, Coral, Tablet, Feather), the rarity ranges, and the room check's 5 a collection
        with four made 25."""
        data = exe()
        code = lambda start, size: data.image[start - data.base:start - data.base + size]  # noqa: E731
        for at, first, tip in ((0x42DF9F, 0x34, 0x2D0), (0x42DFBD, 0x40, 0x2D1), (0x42DFDB, 0x4C, 0x2D2),
                               (0x42DFF9, 0x58, 0x2D3)):
            self.assertEqual(code(at, 2), bytes((0x6A, first)))                  # push <the collection's first kind>
            mov = {0x2D0: 0x42DFAC, 0x2D1: 0x42DFCA, 0x2D2: 0x42DFE8, 0x2D3: 0x42E006}[tip]
            self.assertEqual(code(mov, 5), b"\xb8" + struct.pack("<I", tip))     # mov eax, <its message>
        self.assertEqual(code(0x42DE50, 3), bytes.fromhex("83f80c"))              # complete at 12 found
        for at, lows in ((0x42D664, (0x34, 0x40, 0x4C, 0x58)), (0x42D6A4, (0x38, 0x44, 0x50, 0x5C)),
                         (0x42D6E4, (0x3C, 0x48, 0x54, 0x60))):
            self.assertEqual(code(at, 3), bytes((0x83, 0xF8, lows[0])))          # common, uncommon, rare: 4 each
        self.assertEqual(code(0x45FE8C, 3), bytes.fromhex("83fe14"))              # cmp esi, 20
        self.assertEqual(code(0x45FE91, 5), bytes.fromhex("be19000000"))          # mov esi, 25
        names = {e.name: e for e in items.entries()}
        for name in ("Turtle Shell", "Coral", "Tablet", "Feather"):
            entry = names[f"{name} Collection"]
            self.assertIn("12 pieces (4 common, 4 uncommon, 4 rare)", entry.text)
            self.assertIn(f"\"{name} Collection", entry.subs[0][0])
        self.assertIn("The Ruins", names["Tablet Collection"].text)


class Potions(unittest.TestCase):
    def test_every_recipe_is_listed_once(self) -> None:
        by_name = {e.name: e.text for e in items.entries()}
        listed = sum(int(n) for e in items.entries() if e.name.startswith("Potion ")
                     for n in re.findall(r"\((\d+) recipes?\)", e.text))
        self.assertEqual(listed, len(counts.VV3_COMBOS))
        self.assertEqual(len(counts.VV3_COMBOS), 77)
        for a, b, c, product in counts.VV3_COMBOS:
            recipe = " + ".join(counts.VV3_HERBS[h] for h in (a, b, c))
            self.assertIn(recipe, by_name[items._potion_name(product)].split(". The villager")[0])
        # Every potion the game can brew has its entry, and no other.
        self.assertEqual({e.name for e in items.entries() if e.name.startswith("Potion ")},
                         {items._potion_name(p) for *_, p in counts.VV3_COMBOS})

    def test_the_closer_traces(self) -> None:
        by_name = {e.name: e.text for e in items.entries()}
        self.assertIn("every living child under 14", by_name[items._potion_name(40)])
        self.assertIn("adults never go", by_name[items._potion_name(40)])
        self.assertIn("the sharks leave", by_name[items._potion_name(27)])
        self.assertIn("charmed", by_name[items._potion_name(26)])

    def test_feels_smarter_is_skill_plus_67_percent(self) -> None:
        """The skill test 0x45A2C0: push 3 / 0x455E10 (effect 3) at 0x45A2F7..0x45A300 picks mov edi, 0x42 (66,
        0x45A31B) over 0x21 or 0x10 (33 or 16, 0x45A311..0x45A314); then rand(100) at 0x45A342, cmp eax, ebp (skill +
        edi), jle passes.  rand(100) is the C library's rand() % 100 (0x4032E1..0x4032E7), rand() 15 bits."""
        data = exe()
        code = lambda start, size: data.image[start - data.base:start - data.base + size]  # noqa: E731
        self.assertEqual(code(0x45A2F7, 2), bytes.fromhex("6a03"))
        self.assertEqual(code(0x45A311, 6), bytes.fromhex("83e0ef83c021"))       # and eax, -17; add eax, 33
        self.assertEqual(code(0x45A31B, 5), bytes.fromhex("bf42000000"))         # mov edi, 66
        self.assertEqual(code(0x45A340, 2), bytes.fromhex("6a64"))               # push 100
        self.assertEqual(code(0x45A34C, 4), bytes.fromhex("3bc50f8e"))           # cmp eax, ebp; jle (pass)
        self.assertEqual(code(0x46F3F5, 5), bytes.fromhex("25ff7f0000"))         # rand(): and eax, 0x7FFF
        passes = lambda offset, skill: sum(1 for v in range(32768) if v % 100 <= skill + offset)  # noqa: E731
        self.assertEqual(f"{passes(66, 0) / 32768:.2%}", "67.07%")
        self.assertEqual(f"{passes(33, 0) / 32768:.2%}", "34.03%")
        self.assertEqual(min(s for s in range(101) if passes(66, s) == 32768), 33)
        does = counts.VV3_POTIONS[3][1]
        self.assertIn("every skill test passes at the skill + 67% instead of + 34% (+ 17% for a villager who "
                      "dislikes learning; one who likes learning already has + 67%): 67.07% instead of 34.03% at "
                      "skill 0, and every time from skill 33", does)
        self.assertNotIn("+ 66%", does)
        self.assertIn(does, {e.name: e.text for e in items.entries()}[items._potion_name(3)])


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
        off = {fid for fid in gui.DEFAULT_OFF_FUN_PATCH_IDS if fid.startswith("vv3_")}
        self.assertEqual(off, set(items.DEFAULT_OFF))

    def test_the_origins_prices(self) -> None:
        source = (ROOT / "scripts" / "build_vv3_origins_feature.py").read_text(encoding="utf-8")
        self.assertIn("for value in (50000, 30000, 75000, 500000, 500000, 30000):", source)
        self.assertIn("for value in (50000, 100000, 40000, 50000, 5000):", source)
        by_name = {e.name: e.text for e in items.entries() if e.kind == items.PATCHER}
        for name, price in items.ORIGINS_PRICES.items():
            self.assertIn(f"{price:,} tech points", by_name[name], name)


if __name__ == "__main__":
    unittest.main()
