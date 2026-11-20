"""Fix Vanilla Bugs: every herb study trains Healing (A New Home, The Lost
Children) -- "VVFP Herb Study.dll" -- and The Lost Children's briar thorns.

The owner (2026-11-17, skill practice items 15 and 40): every studyable plant
gives Healing practice when studied, first study and re-studies; a plant the
game never lets anyone re-study becomes re-studyable; the missing ones are
original-game bugs, under each game's Fix Vanilla Bugs.  The Magic Plant of
Life stays exactly stock.

Pinned here, with the companion's stubs RUN in an emulator over the stock
executable (the leaf routines scripted):

* A New Home: each herb case of the completion routine 0x43A230 first makes
  the Healing practice roll 0x43D440(index, 5) -- the re-study's own -- then
  runs the stock case (eax = the state, as its displaced instruction leaves
  it).  The stock cases never call it (read from the executable), and the
  Magic Plant of Life's study has no case there.
* The Lost Children: the study continuation's plant pick is rand(6): 0-3 the
  stock table, 4 and 5 herbs 3 and 4 (only when understood).
* The Lost Children's briar continuation tests the thorns' finished flag.
* The rows: both Fix Vanilla Bugs rows ship and pin the DLL, list its sites,
  and "VVFP Startup.dll" starts it (the second word).
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DLL = ROOT / "assets" / "herb_study" / "VVFP Herb Study.dll"
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Herb Study.test.dll"
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
STOCK = {"vv1": ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
         "vv2": ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"}
STOCK_ABSENT = "the stock executables are not in this checkout (research/stock-executables)"
STOCK_PRESENT = all(p.is_file() for p in STOCK.values())
STACK = 0x0F000000
VILLAGE = 0x20000000
STATE = 0x30000000
INDEX = 7
DLL_BASE = 0x11000000

VV1_CASES = {"medical cactus": (0x43A361, 0xA068), "rare rose": (0x43A451, 0xA060),
             "strange lily": (0x43A432, 0xA070), "strange plant": (0x43A473, 0xA078)}


def _stock(game, va, n):
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    return STOCK[game].read_bytes()[pe.get_offset_from_rva(va - 0x400000):][:n]


class Emu:
    """The stock executable and the test build mapped; `leaves` scripted
    (address -> (stack args, callee-cleaned, fn(args, ecx) -> eax))."""

    def __init__(self, game):
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        pe = pefile.PE(str(STOCK[game]))
        image = pe.get_memory_mapped_image()
        mu.mem_map(0x400000, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0x400000, image)
        dpe = pefile.PE(str(TEST_DLL))
        dpe.relocate_image(DLL_BASE)
        dimage = dpe.get_memory_mapped_image(ImageBase=DLL_BASE)
        mu.mem_map(DLL_BASE, (len(dimage) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(DLL_BASE, dimage)
        self.exports = {e.name.decode(): DLL_BASE + e.address for e in dpe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        mu.mem_map(STACK - 0x20000, 0x20000)
        mu.mem_map(VILLAGE, 0x1000000)
        mu.mem_map(STATE, 0x100000)
        self.leaves, self.calls, self.stops = {}, [], set()
        mu.hook_add(UC_HOOK_CODE, self._hook)

    def _hook(self, mu, address, size, user_data):
        if address in self.stops:
            self.stopped = address
            mu.emu_stop()
            return
        leaf = self.leaves.get(address)
        if leaf is None:
            return
        nargs, callee, fn = leaf
        sp = mu.reg_read(UC_X86_REG_ESP)
        ret, *args = struct.unpack(f"<{1 + nargs}I", mu.mem_read(sp, 4 * (1 + nargs)))
        ecx = mu.reg_read(UC_X86_REG_ECX)
        self.calls.append((address, tuple(args), ecx))
        mu.reg_write(UC_X86_REG_EAX, fn(args, ecx) & 0xFFFFFFFF)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + (4 * nargs if callee else 0))
        mu.reg_write(UC_X86_REG_EIP, ret)

    def site(self, game_no, which):
        buf, ret = STACK - 0x8000, STACK - 0x100
        self.mu.mem_write(ret, b"\xF4")
        self.mu.mem_write(STACK - 0x200, struct.pack("<5I", ret, game_no, which, buf, buf + 4))
        self.mu.reg_write(UC_X86_REG_ESP, STACK - 0x200)
        self.stops = {ret}
        self.mu.emu_start(self.exports["VvfpHerbStudyProbeSite"], 0, count=10000)
        n = self.mu.reg_read(UC_X86_REG_EAX)
        va, stub = struct.unpack("<2I", self.mu.mem_read(buf, 8))
        return n, va, stub

    def install(self, game_no, which):
        n, va, stub = self.site(game_no, which)
        rel = (stub - (va + 5)) & 0xFFFFFFFF
        self.mu.mem_write(va, b"\xE9" + struct.pack("<I", rel) + b"\x90" * (n - 5))
        return va

    def run(self, start, stops, regs, stack):
        esp = STACK - 0x1000
        self.mu.mem_write(esp, struct.pack(f"<{len(stack)}I", *stack))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        for reg, value in regs.items():
            self.mu.reg_write(reg, value)
        self.stops, self.stopped = set(stops), None
        self.mu.emu_start(start, 0, count=100000)
        return self.stopped


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class ANewHome(unittest.TestCase):
    def test_the_stock_first_study_has_no_healing_roll(self):
        """The bug: from each herb case's entry to its exit, no call of the
        practice roll 0x43D440 (the re-study path's step 6 makes it)."""
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        for name, (va, flag) in VV1_CASES.items():
            with self.subTest(herb=name):
                self.assertEqual(_stock("vv1", va, 6), bytes.fromhex("8B8610E00300"))
                self.assertEqual(_stock("vv1", va + 6, 2), b"\x8A\x88")
                self.assertEqual(struct.unpack("<I", _stock("vv1", va + 8, 4))[0], flag)
                calls = [i.op_str for i in md.disasm(_stock("vv1", va, 0x90), va) if i.mnemonic == "call"]
                self.assertNotIn("0x43d440", calls)

    def test_each_case_rolls_healing_practice_then_runs_unchanged(self):
        for which, (name, (va, _)) in enumerate(VV1_CASES.items()):
            with self.subTest(herb=name):
                emu = Emu("vv1")
                self.assertEqual(emu.install(1, which), va)
                emu.mu.mem_write(VILLAGE + 0x3E010, struct.pack("<I", STATE))
                emu.leaves[0x43D440] = (2, True, lambda a, c: 1)
                # The completion routine's frame at the case: edi, ebp, ebx,
                # esi, the return address, then (index, herb).
                stop = emu.run(va, {va + 6}, {UC_X86_REG_ESI: VILLAGE, UC_X86_REG_EBX: 0x1111},
                               (0xED1, 0xEB9, 0xEB8, 0xE51, 0x401000, INDEX, 0x19))
                self.assertEqual(stop, va + 6)
                self.assertEqual(emu.calls, [(0x43D440, (INDEX, 5), VILLAGE)])
                self.assertEqual(emu.mu.reg_read(UC_X86_REG_EAX), STATE, "the displaced mov eax, [esi+0x3E010]")
                self.assertEqual(emu.mu.reg_read(UC_X86_REG_ESP), STACK - 0x1000, "stack as at the entry")
                self.assertEqual(emu.mu.reg_read(UC_X86_REG_ESI), VILLAGE)

    def test_the_magic_plant_of_life_is_not_a_case(self):
        # "Studying fruitless plant" (0x443030) queues no completion step: no
        # site of the companion is in it, and no herb case is its.
        emu = Emu("vv1")
        sites = {emu.site(1, k)[1] for k in range(4)}
        self.assertEqual(sites, {va for va, _ in VV1_CASES.values()})
        self.assertEqual(emu.site(1, 4)[0], 0)
        self.assertFalse(any(0x443030 <= va < 0x443150 for va in sites))


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class TheLostChildren(unittest.TestCase):
    STARTERS = {4: (0x458B70, 0x2E870), 5: (0x458E30, 0x2E878)}

    def pick(self, roll, understood=()):
        emu = Emu("vv2")
        self.assertEqual(emu.install(2, 0), 0x4606A1)
        emu.mu.mem_write(VILLAGE + 0xE574D4, struct.pack("<I", STATE))
        for flag in understood:
            emu.mu.mem_write(STATE + flag, b"\x01")
        emu.leaves[0x4031A0] = (1, False, lambda a, c: roll)
        for starter, _ in self.STARTERS.values():
            emu.leaves[starter] = (1, True, lambda a, c: 0)
        stop = emu.run(0x4606A1, {0x4606AB, 0x4606D5, 0x460961},
                       {UC_X86_REG_ESI: VILLAGE, UC_X86_REG_EBP: INDEX, UC_X86_REG_EBX: 0}, (0,))
        return emu, stop

    def test_the_stock_pick_leaves_herbs_3_and_4_out(self):
        self.assertEqual(_stock("vv2", 0x4606A1, 7).hex().upper(), "6A04E8F82AFAFF")
        table = struct.unpack("<4I", _stock("vv2", 0x460AE4, 16))
        self.assertEqual(table, (0x4606BB, 0x4606E1, 0x460707, 0x46072D))
        starters = set()
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
        for case in table:
            for ins in Cs(CS_ARCH_X86, CS_MODE_32).disasm(_stock("vv2", case, 0x26), case):
                if ins.mnemonic == "call":
                    starters.add(int(ins.op_str, 16))
        self.assertEqual(starters, {0x458CD0, 0x4589A0, 0x458FD0, 0x459130})

    def test_rand_6_the_stock_table_for_0_to_3(self):
        for roll in range(4):
            with self.subTest(roll=roll):
                emu, stop = self.pick(roll)
                self.assertEqual(stop, 0x4606AB)
                self.assertEqual(emu.mu.reg_read(UC_X86_REG_EAX), roll)
                self.assertEqual(emu.calls, [(0x4031A0, (6,), emu.calls[0][2])])
                self.assertEqual(emu.mu.reg_read(UC_X86_REG_ESP), STACK - 0x1000)

    def test_herbs_3_and_4_are_studied_again_once_understood(self):
        for roll, (starter, flag) in self.STARTERS.items():
            with self.subTest(roll=roll):
                emu, stop = self.pick(roll, understood=(flag,))
                self.assertEqual(stop, 0x4606D5, "the continuation's own 'started' exit")
                self.assertEqual(emu.calls[1], (starter, (INDEX,), VILLAGE))
                emu, stop = self.pick(roll)
                self.assertEqual(stop, 0x460961, "not understood: the continuation's own fallback")
                self.assertEqual(len(emu.calls), 1)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class LostChildrenThorns(unittest.TestCase):
    def test_the_briar_continuation_tests_the_thorns(self):
        row = next(p for p in json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))["fun_patches"]
                   if p["id"] == "vv2_fix_vanilla_bugs")
        (patch,) = [p for p in row["patches"] if p["offset"] == "0x608FA"]
        self.assertEqual((patch["before"], patch["after"]), ("B0", "E0"))
        # cmp byte [ecx+0x2E7B0], bl -- the vine wall's flag -- in the stock game.
        self.assertEqual(_stock("vv2", 0x4608F8, 6).hex().upper(), "3899B0E70200")
        # The thorns' flag +0x2E7E0: set where the thorns counter reaches 3000,
        # and the one the briar drop tests (0x43076D).
        self.assertEqual(struct.unpack("<I", _stock("vv2", 0x43076D + 2, 4))[0], 0x2E7E0)


class Rows(unittest.TestCase):
    def test_both_fix_vanilla_bugs_rows_ship_and_pin_it(self):
        import vv_fun_patcher as vfp
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        rows = {p["id"]: p for p in json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))["fun_patches"]}
        expected = {"vv1": {"0x43A361", "0x43A451", "0x43A432", "0x43A473"}, "vv2": {"0x4606A1"}}
        for game, sites in expected.items():
            with self.subTest(game=game):
                row = rows[f"{game}_fix_vanilla_bugs"]
                files = [c for c in row["companion_files"] if c["destination"] == "VVFP Herb Study.dll"]
                self.assertEqual([c["sha256"] for c in files], [sha])
                listed = {d["va"] for d in row["runtime_detours"] if d["installed_by"].startswith("VVFP Herb Study.dll")}
                self.assertEqual(listed, sites)
                self.assertIn("VVFP Herb Study.dll", row["description"])
        # The second startup word filled at the v1.35.97 merge, so the herb study moved to the third word, which
        # "VVFP More Companions.dll" starts (vv_fun_patcher.STARTUP_LOADER_COMPANIONS_3, its comment says so).
        self.assertIn("VVFP Herb Study.dll", vfp.STARTUP_LOADER_COMPANIONS_3)
        self.assertNotIn("VVFP Herb Study.dll", vfp.STARTUP_LOADER_COMPANIONS_2)
        self.assertIn('"VVFP Herb Study.dll"', (ROOT / "native/shared/startup_companions_3.h").read_text(encoding="utf-8"))
        for game in expected:
            with self.subTest(game=game, starter="VVFP More Companions.dll"):
                # a third-word companion only starts when the build also ships its starter (attached at patch time)
                shipped = vfp._attach_more_companions([vfp.Record(rows[f"{game}_fix_vanilla_bugs"])])
                self.assertIn("VVFP More Companions.dll",
                              {c["destination"] for c in shipped[0].raw["companion_files"]})
                self.assertTrue(vfp._startup_loader_mask_3(shipped)
                                & (1 << vfp.STARTUP_LOADER_COMPANIONS_3.index("VVFP Herb Study.dll")))
        self.assertIn("assets/herb_study/VVFP Herb Study.dll",
                      (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
