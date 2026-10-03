"""The Origins menus' command dispatch, executed, agrees with the analysis.

tests/test_origins_dead_code_removed.py and
tests/test_vv5_origins_dead_code_removed.py decide by reading the code which
paths can run; that is what proves code dead and lets it be removed. This is
the second, independent witness Codex's #506 review called for: both Tech and
Villager Details menus of all five games are executed under emulation
(tests/origins_dispatch_emulation.py) from the dialog's answer, for every row
the dialog can return and every combination of what the routines they call
answer, whether the balance covers the price and whether the doublers are
owned. Patcher code runs as written, callees included.

Every instruction that runs must be one the analysis calls live, and no
conditional jump may go the way the analysis says it cannot -- otherwise the
analysis is unsound and a proof of dead code means nothing.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import origins_dispatch_emulation as emulation  # noqa: E402
import origins_reachability as reach  # noqa: E402
import test_origins_dead_code_removed as early  # noqa: E402
import test_vv5_origins_dead_code_removed as vv5  # noqa: E402

disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

# Where each game keeps the tech balance and the doubler-ownership bits: an
# offset into the village object, or an absolute global.
FIELDS = {
    "vv1": ((0xA2FC,), (0x9E90, 0x9E94)),
    "vv2": ((0x2EADC,), (0x2EAE8,)),
    "vv3": ((0x582644,), (0x5824D0,)),
    "vv4": ((0x4D6F88,), (0x4D6E10,)),
    "vv5": ((0x51D5F8,), (0x51D388,)),
}


def subject(game: str):
    """(rendered bytes, owned ranges, static live set, static branch sides)."""
    if game == "vv5":
        if not vv5.STOCK.exists():
            raise unittest.SkipTest(f"stock executable missing: {vv5.STOCK}")
        data = vv5.render("full", "stock")
        builder = vv5.task9_builder()
        objects = {vv5.PAGE[0] + builder.OFF["bighead_offsets"]: builder.SIZES["bighead_offsets"]}
        edges: dict = {}
        _, _, live = reach.reach(data, vv5.REGIONS, objects, vv5.CODE_RANGES, edges=edges)
        return data, vv5.REGIONS, live, edges
    data, caves, _, _, live, edges = early.analysed(game, "full", "stock")
    return data, caves, live, edges


class OriginsDispatchExecutesOnlyLiveCode(unittest.TestCase):
    def test_every_executed_instruction_and_branch_is_one_the_analysis_allows(self) -> None:
        for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            with self.subTest(game=game):
                data, ranges, live, edges = subject(game)
                starts, ran, entered, steps = emulation.explore(data, ranges, *FIELDS[game])
                # Both menus were found and run, and they ran a good deal.
                self.assertEqual(len(starts), 2)
                self.assertGreater(len(ran), 300)
                self.assertEqual(sorted(hex(va) for va in ran if va not in live), [])
                image, base, _, _ = reach._load(data)
                for frm, to in steps:
                    if frm not in edges:
                        continue
                    insn = next(disassembler.disasm(bytes(image[frm - base: frm - base + 16]), frm))
                    went = "fall-through" if to == frm + insn.size else "taken"
                    allowed = edges[frm][1] if went == "fall-through" else edges[frm][0]
                    self.assertTrue(
                        allowed, f"{frm:#x} {insn.mnemonic}: ran {went}, which the analysis rules out"
                    )


if __name__ == "__main__":
    unittest.main()
