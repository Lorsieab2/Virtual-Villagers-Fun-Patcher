"""New Believers' "All Villagers are Exactly 18" moves the lived age with the shown age.

A New Believers villager keeps two ages: the shown age +0x1B8C and the age the villager tick has already lived,
+0x1C3C.  Every update the tick (0x472C90) steps each villager whose lived age is behind the shown age one unit at a
time until none is behind -- all inside that one update, with 4 job turns per unit (0x473311-0x473326) -- and a
pregnancy or nursing starts at the lived age (0x465E7A writes +0x1C3C to +0x1C4C; the birth at 0x4730BA is due 40
units later).

Until v1.35.97 the village-wide row moved the shown age only (0x46F7F0 is a plain add).  Live (R4, 2026-11-20, New
Believers slot 5, 90 villagers): every girl who was 2 to 11 years old replayed the missing years at once -- four to
seven Conception records and as many births each at shown age 360 -- so 93 babies were born before Equal Division
of Labor was bought next, and it rightly reported 183 villagers.  The per-villager Set Age to 18 already shifted
+0x1C3C and a running +0x1C4C by the same delta; the village-wide row now does too.

Emulated: the page's own age18_all routine and the real Origins companion, over the rendered executable, 150 and
256 slots."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_vv5_task9_native_actions as builder  # noqa: E402

DLL = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
PAGE = 0x7C9000
TECH = 0x51D5F8
CHARGE = 0x4237B0
STRIDE = 0x2F44
ACTIVE, MASK, FACTION, HEALTH = 0x1CD4, 0x1CE1, 0x1CEC, 0x1C40
AGE, LIVED, PREGNANT = 0x1B8C, 0x1C3C, 0x1C4C
OWNER = 0x1234
PID = 77


class SourceTests(unittest.TestCase):
    def test_the_row_shifts_the_lived_age_and_a_running_pregnancy(self) -> None:
        source = (ROOT / "scripts/build_vv5_task9_native_actions.py").read_text(encoding="utf-8")
        body = source[source.index("def build_age18_all"):source.index("def build_division")]
        self.assertIn("add dword ptr [esi+0x1C3C], edi", body)
        self.assertIn("add dword ptr [esi+0x1C4C], edi", body)


class EmulatedTests(unittest.TestCase):
    def _process(self, mode: str, with_256: bool):
        from story_emulator import Process
        from vv5_population_256_harness import render

        proc = Process(render(mode, with_256, True), DLL)
        proc.api_handlers["GetForegroundWindow"] = lambda p: (OWNER, 0)
        proc.api_handlers["IsWindow"] = lambda p: (1, 4)

        def thread_pid(p):
            if p.arg(1):
                p.put32(p.arg(1), PID)
            return 1, 8
        proc.api_handlers["GetWindowThreadProcessId"] = thread_pid
        proc.api_handlers["GetCurrentProcessId"] = lambda p: (PID, 0)

        def load(p):
            name = p.cstring(p.arg(0))
            return (proc.dll_base if name == "VVFP Origins Icons.dll" else 0), 4
        proc.api_handlers["LoadLibraryA"] = load
        proc.api_handlers["GetProcAddress"] = lambda p: (proc.exports.get(p.cstring(p.arg(1)), 0), 8)

        def charge(p):
            delta = struct.unpack("<i", struct.pack("<I", p.arg(0)))[0]
            balance = struct.unpack("<i", p.read(p.reg("ecx"), 4))[0]
            p.write(p.reg("ecx"), struct.pack("<i", balance + delta))
            return 0, 4
        proc.stub(CHARGE, charge)
        self.assertEqual(proc.export("BeginOriginsOwner"), 1)
        manager = struct.unpack("<I", proc.read(0x494051, 4))[0]
        proc.base = manager + 0x48
        proc.slots = struct.unpack("<I", proc.read(0x41F1E6, 4))[0]
        for i in range(proc.slots):
            proc.write(proc.base + i * STRIDE + ACTIVE, b"\0")
        proc.put32(TECH, 2_000_000)
        return proc

    def _villager(self, proc, slot, age, lived, pregnant=0, faction=0):
        r = proc.base + slot * STRIDE
        proc.write(r + ACTIVE, b"\x01")
        proc.write(r + MASK, b"\0")
        proc.write(r + FACTION, bytes([faction]))
        proc.put32(r + HEALTH, 50)
        proc.put32(r + AGE, age)
        proc.put32(r + LIVED, lived)
        proc.put32(r + PREGNANT, pregnant)
        return r

    def _ages(self, proc, r):
        return tuple(struct.unpack("<i", proc.read(r + off, 4))[0] for off in (AGE, LIVED, PREGNANT))

    def test_every_age_moves_by_the_same_delta(self):
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            for with_256 in (False, True):
                with self.subTest(mode=mode, with_256=with_256):
                    proc = self._process(mode, with_256)
                    girl = self._villager(proc, 0, 148, 148)                  # Pau, 7.4 years old
                    behind = self._villager(proc, 1, 150, 147)                # a tick not yet run
                    mother = self._villager(proc, 2, 500, 500, pregnant=480)  # 20 units into a pregnancy
                    elder = self._villager(proc, 3, 1302, 1302, pregnant=0)   # 65 years old
                    last = self._villager(proc, proc.slots - 1, 200, 200)
                    already = self._villager(proc, 4, 360, 355)               # left alone
                    heathen = self._villager(proc, 5, 100, 100, faction=1)    # never touched
                    proc.call(PAGE + builder.OFF["age18_all"])
                    self.assertEqual(self._ages(proc, girl), (360, 360, 0))
                    self.assertEqual(self._ages(proc, behind), (360, 357, 0))
                    # Still 20 units into the pregnancy: the birth stays 20 units away.
                    self.assertEqual(self._ages(proc, mother), (360, 360, 340))
                    self.assertEqual(self._ages(proc, elder), (360, 360, 0))
                    self.assertEqual(self._ages(proc, last), (360, 360, 0))
                    self.assertEqual(self._ages(proc, already), (360, 355, 0))
                    self.assertEqual(self._ages(proc, heathen), (100, 100, 0))
                    self.assertTrue(proc.messages[-1].startswith("Set 5 Villagers to Age 18."), proc.messages[-1])
                    self.assertEqual(proc.u32(TECH), 1_000_000)


if __name__ == "__main__":
    unittest.main()
