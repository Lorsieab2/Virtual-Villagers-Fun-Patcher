"""New Believers' Fix Vanilla Bugs: The Defector is always a Heathen of 14 or more (the owner, 2026-11-16: "The
Defector should ideally pick someone 14 and older. And envoys. (Would not be logical to have Heathen children doing
the outreach.)").

The stock condition 0x416900 calls the villager picker 0x471870 with its minimum age -1 (none); Outreach?'s envoy pick
(0x4162D6) already passes 0x118 (280 age units, 14 years).  The row re-encodes 0x41690E..0x416934 so the same
fourteen arguments go to the picker in the same order with the minimum age 0x118, and the 50% roll still sets
[this+0x10].

EMULATED on the rendered executable in each public mode: the condition is run with the picker and the game's rand
stood in for, and the picker receives exactly the stock arguments but the minimum age, which is 280; the roll's flag is
set as before (rand 49 -> 0, rand 50 -> 1); with no Heathen found the condition fails, as stock.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    import capstone
    from test_companion_installs_all_or_none import HAVE_EMULATOR, render, stock_path
    from story_emulator import Process
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

ROW = "vv5_fix_vanilla_bugs"
CONDITION, PICKER, RAND = 0x416900, 0x471870, 0x403660
SITE, LENGTH = 0x41690E, 39
MODES = ("stock", "collection_progression", "immediate_fixed")
FOUND = 0x0C300000


def row() -> dict:
    data = json.loads((ROOT / "data" / "builds.json").read_text("utf-8"))
    return next(p for p in data["fun_patches"] if p["id"] == ROW)


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn/capstone not installed")
class DefectorAge(unittest.TestCase):
    def setUp(self) -> None:
        if not stock_path(5).is_file():
            self.skipTest("stock executable not present")

    def picks(self, exe: bytes, roll: int, found: int) -> tuple[list[int], int, int]:
        """The condition run once: the picker's fourteen arguments, its answer and [this+0x10]."""
        m = Process(exe)
        seen: list[list[int]] = []

        def picker(p):
            seen.append([p.arg(i) for i in range(14)])
            return found, 56                    # thiscall, fourteen arguments

        m.stub(PICKER, picker)
        m.stub(RAND, lambda p: (roll, 0))       # cdecl
        this = m.alloc(0x40)
        answer = m.call(CONDITION, ecx=this)
        self.assertEqual(len(seen), 1)
        return seen[0], answer & 0xFF, m.u32(this + 0x10)

    def test_the_heathen_is_14_or_more_in_every_mode(self) -> None:
        stock_args, _, _ = self.picks(stock_path(5).read_bytes(), 70, FOUND)
        self.assertEqual(stock_args[0], 0xFFFFFFFF)          # the stock game: no minimum age
        for mode in MODES:
            exe = render(5, (ROW,), mode)
            for roll, flag in ((49, 0), (50, 1), (99, 1), (0, 0)):
                with self.subTest(mode=mode, roll=roll):
                    args, answer, coin = self.picks(exe, roll, FOUND)
                    self.assertEqual(args[0], 0x118)          # 280 age units: 14 years
                    self.assertEqual(args[1:], stock_args[1:])
                    self.assertEqual(answer, 1)
                    self.assertEqual(coin, flag)
            _, answer, _ = self.picks(exe, 70, 0)
            self.assertEqual(answer, 0)                       # no Heathen found: the event cannot come

    def test_like_the_envoy(self) -> None:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        exe = stock_path(5).read_bytes()
        envoy = list(md.disasm(exe[0x4162D6 - 0x400000:0x4162DB - 0x400000], 0x4162D6))
        self.assertEqual((envoy[0].mnemonic, envoy[0].op_str), ("push", "0x118"))
        rendered = render(5, (ROW,), "stock")
        code = rendered[SITE - 0x400000:SITE - 0x400000 + LENGTH]
        self.assertEqual(sum(i.size for i in md.disasm(code, SITE)), LENGTH)
        self.assertIn(("push", "0x118"), [(i.mnemonic, i.op_str) for i in md.disasm(code, SITE)])

    def test_the_row_says_so(self) -> None:
        record = row()
        patch = next(p for p in record["patches"] if p["offset"] == "0x1690E")
        self.assertEqual(len(bytes.fromhex(patch["before"])), LENGTH)
        self.assertEqual(stock_path(5).read_bytes()[0x1690E:0x1690E + LENGTH], bytes.fromhex(patch["before"]))
        self.assertIn("The Defector is always a Heathen of 14 or more", record["description"])

    def test_game_mechanics(self) -> None:
        import vv_game_mechanics_events_vv5 as ev
        defector = next(e for e in ev.EVENTS if e.title == "The Defector")
        self.assertIn((ROW, "the Heathen is 14 or more, like the envoy in Outreach? (in the normal game any age, a "
                            "child too)"), defector.patched)


if __name__ == "__main__":
    unittest.main()
