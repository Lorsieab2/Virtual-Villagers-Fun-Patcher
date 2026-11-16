"""The Tree of Life, Fix Vanilla Bugs: saving no longer ends every villager's effects.

The owner (2026-11-16): "the meditation and clean body effect dont last as long [as] they should on villagers",
"even when they just came out of the pond or finished meditation".

What the effects are (stock executable, 929,792 bytes):
  * A villager carries up to 12 effects (+0x1D0C, 0x1C bytes each: the manager, an id, a kind, an offset, the end
    time, the start; count +0x1E5C), added by 0x460A90 with a length in seconds of the computer's clock 0x403750
    and removed by the effect list's update 0x45FC70 once that clock reaches the end.
  * Clean body: "Getting clean in soapy pond" (action 0x97, 0x438180) ends with step 0x469B90(0xE, 1) (0x438221),
    which calls the Purify Tree object's +0x30 (0x437EC0) with 1: five sparkles of kind 2 on the sparkle manager
    0x4CE1C0, each an effect of 240 seconds (0xF0, 0x437F23...).  The tree's drop handler 0x438370 starts
    "Purifying the tree" (action 0x98) only for a villager with a kind-2 sparkle (0x45EBE0, 0x43848A), else
    "Only those pure of body can purify the tree." (message 0x4A).
  * The glow (pure mind): "Meditating to purify the mind" (action 0x99, 0x438320) ends with step 0x469B90(0xE, 0)
    (0x43834E): three sparkles of kind 1, 240 seconds each (0x4380CF...).  Purifying works only with one
    (0x45EB90, 0x438278; else "Only those pure of mind can see the corruption.", message 0x4B), and research gives
    3 times the tech points with one (0x464E46 -> 0x464E4F).
  * Also: the sticky gunk (kind 5, 180 seconds, 0x438CA0 after cutting stalks, action 0x78; read by 0x438FA0)
    and a stew's wait (manager 0x4D6F50, 0x42E966; its add callback 0x41DEE0 sets 600 seconds for the healing and
    sick stews, 1 for the rest; read by 0x45EB40, "That villager can't eat more stew so soon.").

THE BUG.  The save writer 0x4660A0 calls 0x45EAA0 -- remove every effect, freeing its sparkle -- on each villager
(0x4660C4) before packing it (0x45DB30).  The writer runs at every save: quitting and the autosave every 10
real-life minutes (0x41F1A0 -> 0x41F160 -> slot save and its second copy, 0x41F030 -> 0x41F125).  The packed
entry never holds the effects (0x45DB30 copies +0x1B8C, +0x1C34, +0x1C5C and +0x1E60..+0x1E77 only), so the
call does nothing for the file; it only wipes the village in play.  An autosave lands inside a 240-second effect
4 times in 10 on average, at any moment of it, right after the bath or the meditation included.  The game's own
design keeps effects across everything else: each has its own end time, and the village view redraws every
villager's sparkles when it opens (0x43F620 -> 0x466D60 -> 0x45EAE0).

THE FIX.  The 5-byte call at 0x4660C4 becomes 5 NOPs.  Loading still starts every villager with none (the
record reset 0x45D8A0 zeroes the count; the game reset 0x41F1E0 clears every sparkle, 0x41F22A), and "Wiping
sticky gunk off on tree" still ends them all (step 0x4A -> 0x45EAA0 at 0x46431C).
"""
from __future__ import annotations

import dataclasses
import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
FEATURE_ID = "vv4_fix_vanilla_bugs"
MODES = ("stock", "collection_progression", "immediate_fixed")

CALL_OFFSET = 0x660C4                       # file offset of 0x4660C4
CALL_STOCK = bytes.fromhex("E8D789FFFF")    # call 0x45EAA0
CALL_FIXED = bytes.fromhex("9090909090")
EFFECTS_FIXES = ((CALL_OFFSET, CALL_STOCK, CALL_FIXED),)

REMOVE_ALL = 0x45EAA0
SPARKLES, SPARKLES_VTABLE = 0x4CE1C0, 0x48D54C        # the sparkle manager and its vtable (set at start-up)
STEWS, STEWS_VTABLE = 0x4D6F50, 0x48D5C4              # the stew-effect manager and its vtable
CLEAN_BODY, GLOW = 0x45EBE0, 0x45EB90                 # kind 2 / kind 1 sparkle on the villager
HAS_EFFECT = 0x45EB40                                 # (manager, id): the stew wait's check
EFFECTS, COUNT, ENTRY = 0x1D0C, 0x1E5C, 0x1C


def _sparkle(sid: int) -> int:
    """The kind dword of sparkle `sid` in the manager's 512 x 0x44 table (0x41D1C0 reads [ecx + sid*0x44 + 4])."""
    return SPARKLES + 4 + sid * 0x44


def _have_stock() -> bool:
    return STOCK.is_file()


def _render(mode: str, ids) -> bytes:
    from vv_fun_patcher import load_builds, render_patched_bytes
    build = next(b for b in load_builds() if b.id == "vv4")
    rendered, _ = render_patched_bytes(STOCK, build, mode, list(ids))
    return bytes(rendered)


@unittest.skipUnless(_have_stock(), "needs research/stock-executables (the stock VV4 exe)")
class StaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.pe = pefile.PE(str(STOCK), fast_load=True)

    def _listing(self, va: int, size: int) -> list[tuple[int, str, str]]:
        off = self.pe.get_offset_from_rva(va - 0x400000)
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        return [(i.address, i.mnemonic, i.op_str) for i in md.disasm(self.stock[off:off + size], va)]

    def test_the_writer_calls_remove_all_on_each_villager(self) -> None:
        self.assertEqual(self.pe.get_offset_from_rva(0x4660C4 - 0x400000), CALL_OFFSET)
        self.assertEqual(self.stock[CALL_OFFSET:CALL_OFFSET + 5], CALL_STOCK)
        listing = self._listing(0x4660A0, 0x51)
        self.assertIn((0x4660C2, "mov", "ecx, esi"), listing)
        self.assertIn((0x4660C4, "call", hex(REMOVE_ALL)), listing)
        self.assertIn((0x4660D8, "call", "0x45db30"), listing)          # then packs the villager

    def test_the_packed_entry_never_holds_the_effects(self) -> None:
        # 0x45DB30 (the per-villager packer) reads no field of the effect list (+0x1D0C .. +0x1E5F).
        listing = self._listing(0x45DB30, 0xA1)
        self.assertEqual(listing[-1][1], "ret")
        for _, _, ops in listing:
            for word in ops.replace("[", " ").replace("]", " ").replace(",", " ").split():
                if word.startswith("0x"):
                    self.assertFalse(EFFECTS <= int(word, 16) < COUNT + 4, ops)

    def test_remove_all_has_one_other_caller_left_alone(self) -> None:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        pe = pefile.PE(str(STOCK))
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        calls = [i.address for i in md.disasm(text.get_data(), 0x400000 + text.VirtualAddress)
                 if i.mnemonic == "call" and i.op_str == hex(REMOVE_ALL)]
        self.assertEqual(calls, [0x46431C, 0x4660C4])

    def test_rendered_in_every_mode(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, [])
                rendered = _render(mode, [FEATURE_ID])
                self.assertEqual(without[CALL_OFFSET:CALL_OFFSET + 5], CALL_STOCK)
                self.assertEqual(rendered[CALL_OFFSET:CALL_OFFSET + 5], CALL_FIXED)
                # 0x45EAA0 itself and the "Wiping sticky gunk" caller are untouched.
                for va in (REMOVE_ALL, 0x46431C):
                    off = va - 0x400000
                    self.assertEqual(rendered[off:off + 5], without[off:off + 5])

    def test_kept_with_256_villagers(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered = _render(mode, ["vv4_population_256", FEATURE_ID])
                self.assertEqual(rendered[CALL_OFFSET:CALL_OFFSET + 5], CALL_FIXED)


@unittest.skipUnless(_have_stock(), "needs research/stock-executables (the stock VV4 exe)")
class SaveEmulationTests(unittest.TestCase):
    """The REAL save writer 0x4660A0 (with the real 0x45EAA0, 0x45E9F0 and the managers' callbacks) on one villager
    carrying the clean body (5 kind-2 sparkles), the glow (3 kind-1 sparkles) and a stew's wait."""

    CLEAN_IDS = (7, 8, 9, 10, 11)
    GLOW_IDS = (12, 13, 14)
    STEW_ID = 8                       # the stew's number is the effect's id (0x42E960); 8 is the healing stew

    @classmethod
    def setUpClass(cls) -> None:
        cls.builds = {(mode, label): _render(mode, ids) for mode in MODES
                      for label, ids in (("stock", []), ("patched", [FEATURE_ID]))}

    def _machine(self, exe: bytes):
        from save_table_emulator import VV4, Machine
        layout = dataclasses.replace(VV4, pre_save=0xFFFFFFFF)     # the real 0x45EAA0 runs
        m = Machine(exe, layout)
        m.set_block_size(layout.block_size)
        m.populate(1)
        mu = m.mu
        mu.mem_write(SPARKLES, struct.pack("<I", SPARKLES_VTABLE))
        mu.mem_write(STEWS, struct.pack("<I", STEWS_VTABLE))
        for sid in range(512):
            mu.mem_write(_sparkle(sid), struct.pack("<i", -1))
        rec = m.record(0)
        entries = [(SPARKLES, sid, 2) for sid in self.CLEAN_IDS] + [(SPARKLES, sid, 1) for sid in self.GLOW_IDS]
        entries.append((STEWS, self.STEW_ID, -1))
        for n, (manager, sid, kind) in enumerate(entries):
            if manager == SPARKLES:
                mu.mem_write(_sparkle(sid), struct.pack("<i", kind))
            # manager, id, kind, offset x, offset y, end (computer's clock + 240), start
            mu.mem_write(rec + EFFECTS + n * ENTRY, struct.pack("<IiiiiIi", manager, sid, kind, 0, 0, 1_000_240, 0))
        mu.mem_write(rec + COUNT, struct.pack("<i", len(entries)))
        return m, rec, entries

    def _state(self, m, rec):
        count = struct.unpack("<i", m.mu.mem_read(rec + COUNT, 4))[0]
        return {
            "count": count,
            "clean": m.thiscall(CLEAN_BODY, rec) & 0xFF,
            "glow": m.thiscall(GLOW, rec) & 0xFF,
            "stew wait": m.thiscall(HAS_EFFECT, rec, STEWS, self.STEW_ID) & 0xFF,
            "sparkles": [struct.unpack("<i", m.mu.mem_read(_sparkle(s), 4))[0]
                         for s in self.CLEAN_IDS + self.GLOW_IDS],
        }

    def test_before_the_save_the_villager_is_clean_glowing_and_waiting(self) -> None:
        m, rec, entries = self._machine(self.builds[("stock", "stock")])
        self.assertEqual(self._state(m, rec), {"count": 9, "clean": 1, "glow": 1, "stew wait": 1,
                                               "sparkles": [2] * 5 + [1] * 3})

    def test_stock_save_ends_every_effect(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                m, rec, _ = self._machine(self.builds[(mode, "stock")])
                self.assertEqual(m.save(), 1)
                self.assertEqual(self._state(m, rec), {"count": 0, "clean": 0, "glow": 0, "stew wait": 0,
                                                       "sparkles": [-1] * 8})

    def test_fixed_save_keeps_every_effect(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                m, rec, entries = self._machine(self.builds[(mode, "patched")])
                before = bytes(m.mu.mem_read(rec + EFFECTS, COUNT + 4 - EFFECTS))
                self.assertEqual(m.save(), 1)
                self.assertEqual(self._state(m, rec), {"count": 9, "clean": 1, "glow": 1, "stew wait": 1,
                                                       "sparkles": [2] * 5 + [1] * 3})
                self.assertEqual(bytes(m.mu.mem_read(rec + EFFECTS, COUNT + 4 - EFFECTS)), before)

    def test_the_saved_bytes_are_the_same(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                tables = []
                for label in ("stock", "patched"):
                    m, rec, _ = self._machine(self.builds[(mode, label)])
                    m.save()
                    tables.append(m.table_bytes())
                self.assertEqual(tables[0], tables[1])
                self.assertEqual(tables[0][0], 1)          # the villager was saved


if __name__ == "__main__":
    unittest.main()
