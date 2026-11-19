"""Fix Vanilla Bugs (The Tree of Life): no tool harvest from an empty bush, "VVFP VV4 Empty Sources.dll", and Cloth Sacks
asking for it.

The shipped DLLs run beside The Tree of Life's own code in unicorn (tests/farmers_emulation_vv4.py; the companion
mapped through tests/story_emulator.py's Process).  The cutting-tool harvest's drop 0x46E7E0, its harvest (action
0xBE) and job event 14 are the game's own.  "Stock" is the same village without the companion.  The live effect is
NOT verified here.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import hashlib  # noqa: E402

DLL = ROOT / "assets" / "empty_sources" / "VVFP VV4 Empty Sources.dll"
FVB = "vv4_fix_vanilla_bugs"

try:
    import farmers_emulation_vv4 as fe
    import test_vv4_cloth_sacks as sacks

    HAVE_EMULATOR = fe.STOCK.is_file() and fe.CMAP.is_file()
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

HARVEST_DROP, TOOLS = 0x46E7E0, 0x4D8618
REC_ACTION = 0x1CE0
SKILL_ROLL = 0x462B1A


def harvest(patched: bool, berries: int) -> tuple[int, int, list[int]]:
    """A villager dropped to harvest with a cutting tool: (tools left, its action, food credited)."""
    v = fe.Village(berries=berries, dll=DLL if patched else None)
    if patched:
        v.process.export("VvfpStartup", 4, 0)
        assert v.process.export("VvfpEmptySourcesInstalled") == 1
    v.w32(TOOLS, 3)
    v.by_caller[SKILL_ROLL] = 0
    r = v.villager(at=(1568, 1124), skills={"farming": 100})
    v.call(HARVEST_DROP, 0, 0, r)
    action = v.r32(r + REC_ACTION)
    for _ in range(20_000):
        v.step_frame()
        if v.queue_type() == 0:
            break
    return v.r32(TOOLS), action, [a for _, a in v.food_log]


@unittest.skipUnless(HAVE_EMULATOR, "the stock executable, its map and unicorn are needed")
class EmptyBushTests(unittest.TestCase):
    def test_an_empty_bush_refuses_and_keeps_the_tool(self) -> None:
        self.assertEqual(harvest(True, 0)[:2], (3, 0x3F))         # the empty bush's own refusal, tool kept
        self.assertEqual(harvest(False, 0)[0], 2)                  # the stock game spends the tool on nothing

    def test_one_berry_or_more_works_as_before(self) -> None:
        for berries, food in ((1, [1]), (1000, [30])):
            with self.subTest(berries=berries):
                tools, action, credits = harvest(True, berries)
                self.assertEqual(tools, 2)
                self.assertEqual(credits, food)


@unittest.skipUnless(HAVE_EMULATOR, "the stock executable, its map and unicorn are needed")
class EmptyTreeTests(unittest.TestCase):
    def sack(self, loaded: bool, tree: int) -> tuple[int, int, bool]:
        h = sacks.Hut(tree=tree)
        if loaded:
            p = h.v.process
            module = p.api_handlers["GetModuleHandleW"]

            def with_companion(pp):
                if pp.arg(0) and pp.wstring(pp.arg(0)) == "VVFP VV4 Empty Sources.dll":
                    return 0x7100000, 4
                return module(pp)
            p.api_handlers["GetModuleHandleW"] = with_companion
        r = h.villager()
        h.drop(r)
        return h.v.r32(sacks.CLOTH), h.v.r32(r + REC_ACTION), (0x13, sacks.EV_CREDIT) in h.queue(r)

    def test_an_empty_tree_refuses_the_sack_only_with_the_patch(self) -> None:
        self.assertEqual(self.sack(True, 0), (3, 0x3F, False))     # refused, no cloth used
        self.assertEqual(self.sack(False, 0)[::2], (2, True))      # Cloth Sacks alone: as the tool, it goes
        self.assertEqual(self.sack(True, 1)[::2], (2, True))       # 1 fruit: a sack as before


class RowTests(unittest.TestCase):
    def test_fix_vanilla_bugs_ships_and_pins_the_companion(self) -> None:
        # The owner (2026-11-18): a Fix Vanilla Bugs fix, not a patch of its own (Fix Vanilla Bugs is on by default).
        builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        row = next(p for p in builds["fun_patches"] if p["id"] == FVB)
        files = {f["destination"]: f["sha256"] for f in row["companion_files"]}
        self.assertEqual(files["VVFP VV4 Empty Sources.dll"], hashlib.sha256(DLL.read_bytes()).hexdigest().upper())
        self.assertIn("0x46E86F", [d["va"] for d in row["runtime_detours"]])
        self.assertIn("Cloth Sacks for Yellow Fruit", row["description"])
        self.assertFalse((ROOT / "data" / "vv4_no_tool_harvest_from_empty_sources_feature.json").exists())


if __name__ == "__main__":
    unittest.main()
