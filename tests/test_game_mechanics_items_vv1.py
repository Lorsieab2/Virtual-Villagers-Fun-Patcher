"""A New Home's technologies, puzzles, buildings, items and patcher upgrades on the Game Mechanics page
(src/vv_game_mechanics_items_vv1.py): every entry and its labels pinned, every technology and its prices against the
stock exe's own tech screen, every puzzle against the page's puzzle table, every building's size against the exe's own
completion callbacks, and every patcher line's default against the patcher's own defaults."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import island_event_exe as exe  # noqa: E402
import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_items_vv1 as items  # noqa: E402
import vv_game_mechanics_vv1 as page  # noqa: E402

GAME = 1
LETTER = {gm.CODE: "C", gm.RUNNING: "E", gm.CLAMP: "K", gm.OWNER: "O", False: "U"}

# Every entry, in order, with the label of each of its lines (C VERIFIED-C, E VERIFIED-E, K the verified clamp,
# U UNCONFIRMED).
PINNED = {
    "Every technology": "CC",
    "Farming level 1": "CCC",
    "Farming level 2": "CCCCCCC",
    "Farming level 3": "CCCC",
    "Fertility level 1": "CCC",
    "Fertility level 2": "CC",
    "Fertility level 3": "CCCCC",
    "Science level 1": "CCC",
    "Science level 2": "CCC",
    "Science level 3": "CCC",
    "Medicine level 1": "CCC",
    "Medicine level 2": "CCC",
    "Medicine level 3": "CCC",
    "Construction level 1": "CCC",
    "Construction level 2": "CCC",
    "Construction level 3": "CCC",
    "Spirituality level 1": "CCCC",
    "Spirituality level 2": "CCCCC",
    "Spirituality level 3": "CCCC",
    "The Well": "CC",
    "The Hut": "CC",
    "The Beach": "CC",
    "The School": "CCC",
    "The Lagoon": "CC",
    "The Magic Fish of Fertility": "CC",
    "The Cemetery": "CC",
    "Herb Mastery": "CCCC",
    "The Garden": "CCC",
    "The Magic Plant of Life": "UCC",
    "The Temple": "CC",
    "The Idol": "CC",
    "The Butterflies": "EC",
    "The Treasure": "CC",
    "The Cave": "EE",
    "The Golden Child": "EC",
    "Population huts": "CCCC",
    "Hut repair (Examining hut, Fixing hut)": "CC",
    "The beach clean-up": "C",
    "The blockage": "C",
    "The garden field": "C",
    "The temple ruins": "C",
    "The idol": "C",
    "The treasure dig": "C",
    "The well": "C",
    "The school": "C",
    "The cemetery": "C",
    "Mushrooms": "EE",
    "Collectibles": "E",
    "The food store": "C",
    "Research": "EC",
    "Clothing (F6)": "CC",
    "Origins: Time Warp": "K",
    "Origins: Island Event": "C",
    "Origins: Barrel of Babies": "C",
    "Origins: Tech Point Doubler and Food Point Doubler": "C",
    "Origins: Full Heal / Cure All": "U",
    "Origins: village-wide rows": "CCCCC",
    "Origins: Villager Details rows": "UCCCC",
    "Story / Cheat Upgrades": "CCCC",
}
COUNTS = {"technology": 19, "puzzle": 16, "building": 11, "item": 5, "patcher": 8}

# The tech screen's prices: (the level-3 "mov edx" address, the level-2 one) for each technology (0x435AF8..0x435D2E).
PRICE_SITES = {"Farming": (0x435B11, 0x435B18), "Fertility": (0x435BB5, 0x435BBC), "Science": (0x435C0D, 0x435C14),
               "Medicine": (0x435C65, 0x435C6C), "Construction": (0x435CB9, 0x435CC0),
               "Spirituality": (0x435D22, 0x435D29)}
# Each building's size, from its completion callback's compare: (address, the size, the entry that gives it).
SIZES = ((0x43A7B7, 250, "Population huts"), (0x43A8DE, 400, "Population huts"), (0x43AA05, 600, "Population huts"),
         (0x43B136, 350, "The blockage"), (0x43B3C3, 1000, "The temple ruins"), (0x43A5F9, 1350, "The idol"),
         (0x43AB11, 150, "The Beach"), (0x43B1FE, 200, "The garden field"), (0x43ACC5, 800, "The treasure dig"))


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
            self.assertIsNone(fact.due)
            self.assertNotIn(gm.UNCONFIRMED, fact.text)
        rendered = gm.render(facts, 0)
        self.assertTrue(rendered.startswith(items.ITEMS_GROUP + "\n"))
        self.assertEqual(rendered.count(gm.UNCONFIRMED), sum(1 for f in facts if not f.confirmed))

    def test_no_vague_words(self) -> None:
        for e in items.ENTRIES:
            for line, _ in e.lines:
                for vague in ("etc.", "some effect", "and so on", "various"):
                    self.assertNotIn(vague, line, f"{e.name}: {line}")

    def test_the_group_is_the_pages_items_group(self) -> None:
        # The page's own group for these entries (gm.ITEMS), once, and no other group shares its name.
        self.assertEqual(items.ITEMS_GROUP, gm.ITEMS)
        self.assertEqual(gm.GROUPS.count(items.ITEMS_GROUP), 1)

    def test_every_puzzle_of_the_game_has_one_entry(self) -> None:
        names = [name for name, _flag, _hours in page.PUZZLES]
        self.assertEqual(len(names), 16)
        self.assertEqual(sorted(e.name for e in items.ENTRIES if e.kind == items.PUZZLE), sorted(names))
        for name in names:
            head, _ = entry(name).lines[0]
            self.assertTrue(head.startswith("Solved "), name)
            self.assertTrue(any(line.startswith("Reward: ") for line, _ in entry(name).lines), name)

    def test_every_technology_has_both_levels(self) -> None:
        self.assertEqual(len(items.TECH_COSTS), 6)
        for tech, (two, three) in items.TECH_COSTS.items():
            self.assertIn(f"{two:,} tech points", text(f"{tech} level 2"))
            self.assertIn(f"{three:,} tech points", text(f"{tech} level 3"))
        self.assertEqual(sum(1 for e in items.ENTRIES if e.kind == items.TECH), 1 + 3 * 6)
        for tech in items.TECH_COSTS:                  # level 1 is its own entry, as on the later games' tabs
            self.assertEqual(entry(f"{tech} level 1").lines[0][0], items.LEVEL_ONE)

    def test_every_building_has_an_entry(self) -> None:
        for name in ("Population huts", "Hut repair (Examining hut, Fixing hut)", "The beach clean-up",
                     "The blockage", "The garden field", "The temple ruins", "The idol", "The treasure dig",
                     "The well", "The school", "The cemetery"):
            self.assertEqual(entry(name).kind, items.BUILDING)

    def test_patcher_lines_name_real_patches_and_their_defaults(self) -> None:
        names = _patch_names()
        try:
            import vv_fun_patcher_gui as gui
        except Exception as exc:  # noqa: BLE001 -- no GUI toolkit: the defaults cannot be read
            self.skipTest(f"the patcher's defaults cannot be read: {exc}")
        found = 0
        for e in items.ENTRIES:
            for line, _ in e.lines:
                for name, state in _named_patches(line):
                    self.assertIn(name, names, f"{e.name}: no patch is named {name!r}")
                    ids = names[name]
                    expected = {"on" if pid not in gui.DEFAULT_OFF_FUN_PATCH_IDS else "off" for pid in ids}
                    self.assertEqual(expected, {state}, f"{e.name}: {name}")
                    found += 1
        self.assertGreater(found, 10)


def _patch_names(game: int = GAME) -> dict[str, list[str]]:
    """Every patch of `game`: its display name -> its ids (data/builds.json and data/*.json)."""
    out: dict[str, list[str]] = {}
    data = ROOT / "data"
    entries = json.loads((data / "builds.json").read_text(encoding="utf-8")).get("fun_patches", [])
    for path in sorted(data.glob("*.json")):
        try:
            one = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(one, dict):
            entries.append(one)
    for one in entries:
        if isinstance(one, dict) and str(one.get("id", "")).startswith(f"vv{game}_") and "name" in one:
            out.setdefault(one["name"], [])
            if one["id"] not in out[one["name"]]:
                out[one["name"]].append(one["id"])
    return out


_WITH = re.compile(r"With the patcher \((.+?), (on|off) by default")
_ALSO = re.compile(r"[Ww]ith ([A-Z][^()]+?) (?:as well )?\((on|off) by default\)")


def _named_patches(line: str) -> list[tuple[str, str]]:
    return _WITH.findall(line) + _ALSO.findall(line)


@unittest.skipUnless(exe.available(GAME), "the stock A New Home exe or capstone/pefile is absent")
class TheExeSaysSo(unittest.TestCase):
    def setUp(self) -> None:
        self.exe = exe.exe(GAME)

    def test_the_tech_prices(self) -> None:
        for tech, (three_at, two_at) in PRICE_SITES.items():
            two, three = items.TECH_COSTS[tech]
            self.assertEqual(self.exe.instruction(two_at), f"mov edx, {hex(two)}", tech)
            self.assertEqual(self.exe.instruction(three_at), f"mov edx, {hex(three)}", tech)

    def test_the_technologies_are_the_games_own(self) -> None:
        raw = self.exe.raw
        for tech, title in items.TECH_TITLES.items():
            self.assertIn(f"{title}\n".encode(), raw, tech)
        # The six levels start at 1 and a new village has 99 tech points.
        for address in (0x41C43E, 0x41C444, 0x41C44A, 0x41C450, 0x41C456, 0x41C45C):
            self.assertTrue(self.exe.instruction(address).endswith(", esi"), hex(address))
        self.assertEqual(self.exe.instruction(0x41C422), "mov esi, 1")
        self.assertEqual(self.exe.instruction(0x41C410), "mov eax, 0x63")

    def test_the_building_sizes(self) -> None:
        for address, size, name in SIZES:
            self.assertTrue(self.exe.instruction(address).endswith(f", {hex(size)}"), hex(address))
            self.assertIn(f"{size:,}", text(name), name)

    def test_the_drop_gates(self) -> None:
        for address, instruction in (
                (0x4241D6, "cmp dword ptr [ecx + 0xa2e4], 2"),      # the sea: fishing at Farming 3
                (0x4243C6, "cmp dword ptr [esi + 0xa2e4], 3"),      # the Magic Fish at Farming 3
                (0x4243CF, "cmp dword ptr [ecx + edi + 0x3c4], 0x5a"),
                (0x42426E, "cmp dword ptr [eax + 0xa2dc], 3"),      # the Golden Child at Fertility 3
                (0x4244AC, "cmp dword ptr [eax + 0xa2cc], 2"),      # the blockage at Construction 2
                (0x424543, "cmp dword ptr [eax + 0xa2bc], 2"),      # the cemetery at Spirituality 2
                (0x42499C, "cmp dword ptr [eax + 0xa2bc], 3"),      # the idol at Spirituality 3
                (0x424C66, "cmp dword ptr [eax + 0xa2bc], 2"),      # the ruins at Spirituality 2 ...
                (0x424C73, "cmp dword ptr [eax + 0xa2cc], 3"),      # ... and Construction 3
                (0x424438, "cmp dword ptr [eax + ecx + 0x3cc], 0x5a"),  # the school at Research 90
                (0x424BCC, "cmp dword ptr [ecx + 0xa2e4], 2"),      # the field at Farming 2
                (0x4475D7, "cmp dword ptr [ecx + 0xa2cc], 2"),      # builders: Construction 2 ...
                (0x447664, "cmp dword ptr [edx + 0xa2cc], 3"),      # ... and 3
                (0x447481, "call 0x41cea0")):                        # research stops at the six levels' 18
            self.assertEqual(self.exe.instruction(address), instruction, hex(address))

    def test_buying_farming_2_moves_the_regrowth(self) -> None:
        self.assertEqual(self.exe.instruction(0x435B36), "cmp dword ptr [ecx + 0xa2e4], 1")
        self.assertEqual(self.exe.instruction(0x435B62), "imul eax, eax, 0x960")
        self.assertEqual(self.exe.instruction(0x435B74), "sar eax, 2")

    def test_the_devotion_roll(self) -> None:
        self.assertEqual(self.exe.instruction(0x4483F3), "call 0x41ced0")
        self.assertEqual(self.exe.instruction(0x41CEE1), "lea eax, [eax + eax*2]")
        self.assertEqual(self.exe.instruction(0x4462ED), "cmp eax, 0x32")
        self.assertEqual(self.exe.instruction(0x4462F9), "push 5")


if __name__ == "__main__":
    unittest.main()
