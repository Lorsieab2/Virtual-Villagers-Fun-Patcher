"""New Believers: the Origins upgrades' Time Warp ages the Heathens the Heathen aging rows age (live check, #850:
an "Advanced 12 years" warp aged every believer by 240 units and the former villagers among the Heathens by none).

The warp writes the ages itself, past the age credit (native/vv5_task9_origins vv5_time_warp_apply; the Story /
Cheat Upgrades' time skip goes through the same routine, one Time Warp at a time), and credited only the faction the
game ages.  It now asks "VVFP Heathen Aging.dll" (VvfpHeathenAgingAges) for a Heathen's record and credits the ones
that companion ages; their old age then comes through the life tick, unit by unit (tests/test_vv5_heathen_aging.py).

EMULATED: the Origins companion's ShowVv5TimeWarp runs on the stock executable's memory (its confirmation answered
OK, the game's tech charge stood in for); the Heathen aging companion is a stand-in answering for one record, and its
real export is run by tests/test_vv5_heathen_aging.py.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from story_emulator import Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

DLL = ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
RECORDS, STRIDE = 0x554190, 0x2F44
AGE, HEALTH, LAST_SEEN, PRESENT, RATE, FACTION = 0x1B8C, 0x1C40, 0x1C38, 0x1CD4, 0x1CC8, 0x1CEC
WORLD_WORD, SPEED, TECH, CHARGE = 0x4DACE0, 0x17D7C, 0x51D5F8, 0x4237B0
AGING = 0x0B300000


class Warp(Process):
    def __init__(self, aging: bool):
        super().__init__(STOCK.read_bytes(), DLL)
        self.aging = aging
        self.asked: list[int] = []
        stubs = self.alloc(0x20)
        self.ages_stub = stubs
        self.stub(stubs, self._ages)
        self.stub(CHARGE, self._charge)
        self.api_handlers["GetModuleHandleA"] = self._module
        self.api_handlers["GetProcAddress"] = self._proc
        world = self.alloc(0x18000)
        self.put32(WORLD_WORD, world)
        self.put32(world + SPEED, 3)                     # fast: 12 years
        self.put32(TECH, 10_000)
        self.former = self._villager(1, heathen=True)
        self.camp = self._villager(2, heathen=True)
        self.believer = self._villager(0, heathen=False)

    def _villager(self, index: int, heathen: bool) -> int:
        r = RECORDS + index * STRIDE
        self.write(r, bytes(STRIDE))
        self.write(r + PRESENT, b"\x01")
        self.write(r + FACTION, b"\x01" if heathen else b"\x00")
        self.put32(r + AGE, 1400)
        self.put32(r + HEALTH, 90)
        self.put32(r + RATE, 1)
        return r

    def _module(self, p):
        name = p.cstring(p.arg(0)) if p.arg(0) else ""
        return (AGING if self.aging and name == "VVFP Heathen Aging.dll" else 0), 4

    def _proc(self, p):
        if p.arg(0) == AGING and p.cstring(p.arg(1)) == "VvfpHeathenAgingAges":
            return self.ages_stub, 8
        return 0, 8

    def _ages(self, p):
        self.asked.append(p.arg(0))
        return int(p.arg(0) == self.former), 4

    def _charge(self, p):
        balance = p.reg("ecx")
        p.put32(balance, (p.u32(balance) + p.arg(0)) & 0xFFFFFFFF)
        return 0, 4

    def age(self, record: int) -> int:
        return struct.unpack("<i", self.read(record + AGE, 4))[0]


def _skip() -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    if not STOCK.is_file() or not DLL.is_file():
        return "the stock executable or the Origins companion is not present"
    return None


@unittest.skipIf(_skip(), _skip() or "")
class TimeWarpAgesHeathens(unittest.TestCase):
    def test_a_warp_ages_a_former_villager_among_the_heathens(self):
        w = Warp(aging=True)
        w.export("ShowVv5TimeWarp", 1000)
        self.assertEqual(w.age(w.believer), 1640, "12 years: 240 units")
        self.assertEqual(w.age(w.former), 1640, "the Heathen the aging rows age: the same 240 units")
        self.assertEqual(w.age(w.camp), 1400, "a Heathen they do not age: none")
        self.assertIn(w.former, w.asked)
        self.assertNotIn(w.believer, w.asked, "a believer is never asked about")

    def test_without_the_heathen_aging_companion_no_heathen_ages(self):
        w = Warp(aging=False)
        w.export("ShowVv5TimeWarp", 1000)
        self.assertEqual((w.age(w.believer), w.age(w.former), w.age(w.camp)), (1640, 1400, 1400))


if __name__ == "__main__":
    unittest.main()
