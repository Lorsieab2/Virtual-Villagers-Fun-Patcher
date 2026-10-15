"""Every villager a creator makes is labelled with the path that made it.

The owner (2026-10-11, live): in The Tree of Life the F7 developer command
spawns villagers, and their Arrived records said "How: unknown".  The stock
executable shows what F7 does: key event 1024 (F7; F1-F10 are commands
1018-1027, F6 1023 and F8 1025 as the VV1 key map has them) dispatches to case 3
at 0x44089D, which calls the event creator 0x467D10 six times, from the return
addresses 0x4408CA ... 0x440979.  Those were not in the marker table, so the
creator's hook fell back to the unknown label.

The check here is the one that matters: every direct call of a villager creator
in each stock executable must be a marker row (its own return address, or the
return address one wrapper up), so no creator path is left to the fallback.  A
path the table does not list is written as "added outside a recorded event",
never as "unknown" (the backfill keeps "unknown" for villagers it finds with no
record at all).
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_arrival_paths_emulated as emu  # noqa: E402  (the marker table reader)

try:
    import pefile
    HAVE_PEFILE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_PEFILE = False

STOCK = ROOT / "research" / "stock-executables"
SITES = ROOT / "native" / "vvfp_cause_of_death" / "cod_arrivals.inc"
F7_EVENT = 1024
F7_DISPATCH = 0x44089D
F7_CALLS = [0x4408CA, 0x4408ED, 0x440910, 0x440933, 0x440956, 0x440979]
EVENT_CREATOR = 0x467D10

# Villager creators, by game: the fresh and copy initialisers, and the wrappers
# a marker routes through (a direct call of any of these must be labelled).
TARGETS = {
    1: [0x43C350, 0x43C840],
    2: [0x44C600, 0x44CEC0],
    3: [0x456120, 0x4566E0, 0x45F0B0],
    4: [0x45EF10, 0x466270, EVENT_CREATOR],
    5: [0x4681F0, 0x4687F0],
}
# Direct calls that need no marker, and why.
ALLOWED = {
    4: {0x45D9B0: "the copy init's call inside the twin wrapper 0x466310 (0x466361): its callers "
                  "0x4688F3 and 0x468996 are the labelled marker rows"},
    5: {0x46FC28: "the Heathen allocator (0x46FB80): a Heathen is never a villager"},
}
EXE_TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
              5: "New Believers"}


def _exe(game: int):
    return STOCK / f"Virtual Villagers - {EXE_TITLES[game]}.exe"


def _pe(game: int):
    pe = pefile.PE(str(_exe(game)), fast_load=True)
    return pe, pe.OPTIONAL_HEADER.ImageBase


def _va_offset(pe, va: int) -> int:
    rva = va - pe.OPTIONAL_HEADER.ImageBase
    for s in pe.sections:
        if s.VirtualAddress <= rva < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            return s.PointerToRawData + (rva - s.VirtualAddress)
    raise ValueError(hex(va))


def _call_sites(game: int, target: int) -> list[int]:
    """The return address of every `call rel32` in .text that calls `target`."""
    pe, base = _pe(game)
    text = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".text")
    code = pe.__data__[text.PointerToRawData: text.PointerToRawData + text.SizeOfRawData]
    t0 = base + text.VirtualAddress
    sites = []
    for i in range(len(code) - 5):
        if code[i] == 0xE8:
            rel = struct.unpack_from("<i", code, i + 1)[0]
            if (t0 + i + 5 + rel) & 0xFFFFFFFF == target:
                sites.append(t0 + i + 5)
    return sites


@unittest.skipUnless(HAVE_PEFILE, "pefile not installed")
@unittest.skipUnless(all(_exe(g).is_file() for g in EXE_TITLES), "the stock executables are not in this checkout")
class EveryCreatorCallIsLabelled(unittest.TestCase):
    def check(self, game: int):
        rows = emu.markers(game)
        accepted = {r["value"] for r in rows} | {r["need_value"] for r in rows if r["need_value"]}
        for target in TARGETS[game]:
            sites = _call_sites(game, target)
            self.assertTrue(sites, f"VV{game}: no direct call of {target:#x} found")
            for site in sites:
                with self.subTest(game=game, creator=hex(target), return_address=hex(site)):
                    self.assertTrue(
                        site in accepted or site in ALLOWED.get(game, {}),
                        f"VV{game}: the call of {target:#x} returning to {site:#x} has no marker row, "
                        f"so its villager would be written as an unlisted path")

    def test_a_new_home(self):
        self.check(1)

    def test_the_lost_children(self):
        self.check(2)

    def test_the_secret_city(self):
        self.check(3)

    def test_the_tree_of_life(self):
        self.check(4)

    def test_new_believers(self):
        self.check(5)


@unittest.skipUnless(HAVE_PEFILE, "pefile not installed")
@unittest.skipUnless(_exe(4).is_file(), "the stock executables are not in this checkout")
class TheTreeOfLifeF7IsTheDeveloperCommand(unittest.TestCase):
    """Key event 1024 is F7 (the VV1 key map: F1-F10 are 1018-1027); in The Tree
    of Life it dispatches to 0x44089D, which makes six event villagers through
    0x467D10 from the six return addresses the marker rows name."""

    def test_event_1024_dispatches_to_the_f7_block(self):
        pe, _ = _pe(4)
        byte_table = _va_offset(pe, 0x4409B0)
        jump_table = _va_offset(pe, 0x440998)
        case = pe.__data__[byte_table + (F7_EVENT - 1000)]
        target = struct.unpack_from("<I", pe.__data__, jump_table + case * 4)[0]
        self.assertEqual(target, F7_DISPATCH)

    def test_the_block_makes_six_event_villagers(self):
        self.assertEqual(_call_sites(4, EVENT_CREATOR)[-6:], F7_CALLS)

    def test_the_marker_rows_name_the_developer_command(self):
        rows = {r["value"]: r for r in emu.markers(4)}
        for site in F7_CALLS:
            with self.subTest(site=hex(site)):
                self.assertIn(site, rows)
                self.assertEqual(rows[site]["label"], "Developer command (F7)")


class AnUnlistedPathIsNotUnknown(unittest.TestCase):
    """cod_arrivals.inc is compiled into the one Cause of Death DLL that all
    five games load, so the fallback is one line for every game."""

    def test_the_fallback_label(self):
        source = SITES.parent.joinpath("cod_arrivals.inc").read_text(encoding="utf-8")
        self.assertIn('lstrcpynA(arrivals[index].how, "added outside a recorded event", ARRIVAL_HOW);', source)
        self.assertNotIn('lstrcpynA(arrivals[index].how, "unknown"', source)


if __name__ == "__main__":
    unittest.main()
