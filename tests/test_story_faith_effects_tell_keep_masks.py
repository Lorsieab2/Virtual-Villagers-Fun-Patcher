"""The Custom Island Event's "Becomes a Heathen" (40) and "Becomes a believer" (39) tell "VVFP Heathens Keep
Masks.dll" before the faction setter 0x466880 they call themselves (native/vvfp_story_upgrades/story_graph.inc
cg_keep_masks_faction).

The owner (2026-11-22): every way a villager goes back to the Heathens follows the rule -- their own mask, an
ordinary blue Heathen's behaviour.  The game's own conversions are spliced by the companion; this effect calls the
setter directly when its SetFaith did not convert (the villager's Faith already past 0), so the companion is told
first.  The test build of the Story DLL runs in the emulator beside New Believers' rendered executable
(tests/test_story_cie_graph_runtime_v6.py's run); the companion is a stand-in that records what it is told.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime_v6 import V6

KEEP_BASE = 0x0B300000
SET_FAITH, FACTION_SETTER = 0x467F90, 0x466880
APOSTASY, JOIN = 40, 39


@emulated
class FaithEffectsTellKeepMasks(unittest.TestCase):
    def run_effect(self, code: int, *, heathen: bool, loaded: bool = True) -> list[tuple]:
        if not have_stock("vv5"):
            self.skipTest("no New Believers")
        r = V6("vv5", [(0, "m", 30, "Adam", 0, False)])
        p = r.p
        record = r.v.record(0)
        p.write(record + 0x1CEC, b"\1" if heathen else b"\0")
        seen: list[tuple] = []
        told = p.alloc(0x10)
        p.stub(told, lambda q: (seen.append(("told", q.arg(0), q.arg(1))), (1, 8))[1])
        p.api_handlers["GetModuleHandleA"] = lambda q: (
            KEEP_BASE if loaded and q.cstring(q.arg(0)) == "VVFP Heathens Keep Masks.dll" else 0, 4)
        p.api_handlers["GetProcAddress"] = lambda q: (
            told if q.arg(0) == KEEP_BASE and q.cstring(q.arg(1)) == "VvfpHeathensKeepMasksFaction" else 0, 8)
        # SetFaith leaves the Faith where it was (already past 0: no conversion); the setter writes the faction.
        p.stub(SET_FAITH, lambda q: (seen.append(("set_faith", q.reg("ecx"), q.arg(0))), (0, 8))[1])
        p.stub(FACTION_SETTER, lambda q: (seen.append(("setter", q.reg("ecx"), q.arg(0) & 0xFF)),
                                          q.write(q.reg("ecx") + 0x1CEC, bytes([q.arg(0) & 0xFF])), (0, 4))[2])
        from unicorn import UC_HOOK_CODE
        for va in (told, SET_FAITH, FACTION_SETTER):
            p.mu.hook_add(UC_HOOK_CODE, p._on_code, begin=va, end=va)
        self.refused = p.export("VvfpStoryProbeFaithEffect", record, code, 0)
        return [(what, at - record if what != "set_faith" else at - record, value) for what, at, value in seen]

    def test_becomes_a_heathen_tells_the_companion_before_the_setter(self):
        self.assertEqual(self.run_effect(APOSTASY, heathen=False),
                         [("set_faith", 0, 0xFFFFFFF6), ("told", 0, 1), ("setter", 0, 1)])

    def test_becomes_a_believer_tells_the_companion_before_the_setter(self):
        self.assertEqual(self.run_effect(JOIN, heathen=True),
                         [("set_faith", 0, 20), ("told", 0, 0), ("setter", 0, 0)])

    def test_without_the_companion_the_effect_is_as_before(self):
        self.assertEqual(self.run_effect(APOSTASY, heathen=False, loaded=False),
                         [("set_faith", 0, 0xFFFFFFF6), ("setter", 0, 1)])


if __name__ == "__main__":
    unittest.main()
