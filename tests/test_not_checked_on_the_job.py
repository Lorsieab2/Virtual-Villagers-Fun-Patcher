"""Not checked on the job: 14% of a patch's skill-training actions, the game's own choices only.

The owner (2026-10-20): a villager whose job checkmark (the skill preference on
the Villager Details screen) is not the skill an approved patch behaviour
trains does that behaviour only 14 times in 100 of the times the patch would
make it happen -- and only when the game chooses (live or in catch-up); what
the player does by hand or by dropping a villager is never gated.

Here, from A New Home's three companions that hold such a gate (RUN in an
emulator from their own stub, the game's routines replaced by stop points):

* "VVFP VV1 Easier Healing.dll"  -- Easier Healing Mastery's study at the
  Healing case's no-patient exit (0x4478E7): checked on Healing (5) or in
  plant-study state 9 (the player's drop) studies; anyone else on 14 in 100,
  else the stock exit 0x447901.
* "VVFP VV1 Research At Max.dll" -- Continue Research at Max Technologies
  (0x447486): at 18 technology levels, checked on Research (3) researches;
  anyone else on 14 in 100, else 0x447901; below 18 the stock research.
* "VVFP VV1 Watering Builds.dll" -- watering the field (0x447635): checked on
  Building (4) waters; anyone else on 14 in 100, else the Building branch's
  next choice 0x44765E.

And, for every game, that the places those gates and the others (Healers
Study, Builders Fix Huts When Idle, Easier Healing Mastery in The Lost
Children, Easier Devotee Training, the statue selector) sit in are reached
only from the game's own choosers -- the idle scheduler and the catch-up
worker -- while the player's drops call the actions directly.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import capstone
import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
TEST_DLLS = ROOT / "tests" / "test_dlls"
STOCK = ROOT / "research" / "stock-executables"
EXES = {"vv1": "Virtual Villagers - A New Home.exe", "vv2": "Virtual Villagers - The Lost Children.exe",
        "vv3": "Virtual Villagers - The Secret City.exe", "vv4": "Virtual Villagers - The Tree of Life.exe",
        "vv5": "Virtual Villagers - New Believers.exe"}
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
STOCK_ABSENT = "the stock executables (research/stock-executables) are gitignored and absent"
VILLAGE, STATE, STACK_TOP = 0x20000000, 0x30000000, 0x70000000
INDEX = 7
STRIDE = 0x3D8
IMPORT_PAGE = 0x7E000000
IMPORT_ARGS = {"GetModuleHandleA": 1, "GetProcAddress": 2}
# A stand-in "VVFP Fix Huts.dll": its handle, and its VvfpFixHutsRoll
# (cdecl, no arguments): mov eax, [ROLL_ANSWER]; ret.
FIX_HUTS_HANDLE, SHARED_ROLL, ROLL_ANSWER = 0x7D000000, 0x7D000100, 0x7D000200


class Stub:
    """A test build loaded into an emulator, its stub (found through `probe`)
    run with the game's addresses in `stops` mapped as stop points."""

    def __init__(self, dll: str, probe: str, roll: str, stops: dict[int, str], calls: dict[int, str] = None):
        pe = pefile.PE(str(TEST_DLLS / dll))
        base = pe.OPTIONAL_HEADER.ImageBase
        image = bytearray(pe.get_memory_mapped_image())
        self.exports = {e.name.decode(): base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(base, bytes(image))
        mu.mem_map(STACK_TOP - 0x10000, 0x20000)
        mu.mem_map(VILLAGE, 0x100000)
        mu.mem_map(STATE, 0x100000)
        self.stops, self.calls = dict(stops), dict(calls or {})
        for va in list(self.stops) + list(self.calls):
            try:
                mu.mem_map(va & ~0xFFF, 0x1000)
            except Exception:
                pass
            mu.mem_write(va, b"\xF4")
        mu.mem_map(0x7F000000, 0x1000)
        mu.mem_write(0x7F000000, b"\xF4")
        self.roll = self.exports[roll]
        # The probe: (site, stock/row bytes, patched bytes, stub) -> length.
        buf, esp = STACK_TOP - 0x8000, STACK_TOP - 0x200
        mu.mem_write(esp, struct.pack("<5I", 0x7F000000, buf, buf + 0x40, buf + 0x80, buf + 0xC0))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.emu_start(self.exports[probe], 0x7F000000, count=100000)
        self.length = mu.reg_read(UC_X86_REG_EAX)
        self.site, = struct.unpack("<I", mu.mem_read(buf, 4))
        self.row = bytes(mu.mem_read(buf + 0x40, self.length))
        self.stub, = struct.unpack("<I", mu.mem_read(buf + 0xC0, 4))
        # Imports: each IAT slot points at a hlt in IMPORT_PAGE, answered by
        # `imports[name](args) -> eax` (stdcall, IMPORT_ARGS dwords).  An
        # unanswered import stops the run with end "import <name>".
        self.imports: dict = {}
        self.import_at: dict[int, str] = {}
        mu.mem_map(IMPORT_PAGE, 0x1000)
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", ()):
            for imp in entry.imports:
                if imp.name:
                    at = IMPORT_PAGE + 16 * len(self.import_at)
                    mu.mem_write(at, b"\xF4")
                    self.import_at[at] = imp.name.decode()
                    mu.mem_write(imp.address, struct.pack("<I", at))
        mu.hook_add(UC_HOOK_CODE, self._hook)

    def _hook(self, mu, address, size, _):
        if address in self.import_at:
            name = self.import_at[address]
            handler = self.imports.get(name)
            if handler is None:
                self.end = f"import {name}"
                mu.emu_stop()
                return
            esp = mu.reg_read(UC_X86_REG_ESP)
            n = IMPORT_ARGS.get(name, 0)
            ret, *args = struct.unpack(f"<{1 + n}I", mu.mem_read(esp, 4 * (1 + n)))
            mu.reg_write(UC_X86_REG_EAX, handler(args) & 0xFFFFFFFF)
            mu.reg_write(UC_X86_REG_ESP, esp + 4 + 4 * n)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address in self.stops:
            self.end = self.stops[address]
            mu.emu_stop()
        elif address in self.calls:
            self.called.append(self.calls[address])
            esp = mu.reg_read(UC_X86_REG_ESP)
            ret, = struct.unpack("<I", mu.mem_read(esp, 4))
            mu.reg_write(UC_X86_REG_ESP, esp + 8)          # thiscall(index), ret 4
            mu.reg_write(UC_X86_REG_EIP, ret)

    def force(self, force: int) -> None:
        self.mu.mem_write(self.roll, struct.pack("<i", force))

    def draws(self) -> int:
        return struct.unpack("<ii", self.mu.mem_read(self.roll, 8))[1]

    def run(self, regs: dict, stack: tuple = ()) -> str:
        mu = self.mu
        esp = STACK_TOP - 0x400
        mu.mem_write(esp, struct.pack(f"<{len(stack) + 1}I", 0x7F000000, *stack) if stack else struct.pack("<I", 0))
        mu.reg_write(UC_X86_REG_ESP, esp)
        for reg, value in regs.items():
            mu.reg_write(reg, value)
        self.end, self.called = None, []
        mu.emu_start(self.stub, 0, count=100000)
        return self.end


def _share(stub: Stub, run, n: int = 3000) -> float:
    stub.force(0)
    hits = 0
    for _ in range(n):
        hits += run()
    return hits / n


@unittest.skipUnless((TEST_DLLS / "VVFP VV1 Easier Healing.test.dll").is_file(), TEST_BUILD_ABSENT)
class NewHomeEasierHealing(unittest.TestCase):
    """The owner (2026-11-15): villagers set to Healing still do other things
    too, as in the normal game, where a healer with no patient does nothing at
    this exit (al = 0) and the scheduler goes on to its next choice.  A
    healer studies when the decision's roll passes -- the fix-huts
    companion's shared VvfpFixHutsRoll when that DLL is loaded, else a 75%
    roll of this DLL's own -- so about three times in four, never always."""

    def setUp(self):
        self.s = Stub("VVFP VV1 Easier Healing.test.dll", "VvfpVv1EasierHealingProbe", "VvfpVv1EasierHealingRollTest",
                      {0x44788B: "started", 0x447901: "nothing", SHARED_ROLL: "shared roll"},
                      {0x443270: "study"})
        self.decision = self.s.exports["VvfpVv1EasierHealingDecisionRollTest"]
        self.lookups = []
        self.fix_huts_loaded(False)

    def fix_huts_loaded(self, loaded: bool, answer: int = 1) -> None:
        """Whether "VVFP Fix Huts.dll" is in the process, and what its shared
        roll answers.  The stand-in roll is real code (mov eax, [answer];
        ret), so it is not a stop point."""
        mu = self.s.mu
        self.s.stops.pop(SHARED_ROLL, None)
        mu.mem_write(SHARED_ROLL, b"\xA1" + struct.pack("<I", ROLL_ANSWER) + b"\xC3")
        mu.mem_write(ROLL_ANSWER, struct.pack("<I", answer))

        def module(args):
            name = bytes(mu.mem_read(args[0], 64)).split(b"\0")[0].decode()
            self.lookups.append(name)
            return FIX_HUTS_HANDLE if loaded and name == "VVFP Fix Huts.dll" else 0

        def proc(args):
            name = bytes(mu.mem_read(args[1], 64)).split(b"\0")[0].decode()
            return SHARED_ROLL if args[0] == FIX_HUTS_HANDLE and name == "VvfpFixHutsRoll" else 0

        self.s.imports = {"GetModuleHandleA": module, "GetProcAddress": proc}

    def decision_force(self, force: int) -> None:
        self.s.mu.mem_write(self.decision, struct.pack("<ii", force, 0))

    def decision_draws(self) -> int:
        return struct.unpack("<ii", self.s.mu.mem_read(self.decision, 8))[1]

    def villager(self, preference: int, activity: int = 0) -> None:
        rec = VILLAGE + INDEX * STRIDE
        self.s.mu.mem_write(rec + 0x3D0, struct.pack("<i", preference))
        self.s.mu.mem_write(rec + 0x3B8, struct.pack("<i", activity))

    def go(self) -> str:
        return self.s.run({UC_X86_REG_ESI: VILLAGE, UC_X86_REG_EBP: INDEX})

    def test_the_site_is_the_rows(self):
        self.assertEqual(self.s.site, 0x4478E7)
        self.assertEqual(self.s.row.hex().upper(), "558BCEE881B9FFFF5F5D5BB0015EC20800909090909090909090")

    def test_the_players_cactus_drop_always_studies(self):
        # State 9 is the stock game's own study: never rolled.
        for preference in (5, 1, 0):
            with self.subTest(preference=preference):
                self.villager(preference, 9)
                self.s.force(2)
                self.decision_force(2)
                self.assertEqual(self.go(), "started")
                self.assertEqual(self.s.called, ["study"])
                self.assertEqual((self.s.draws(), self.decision_draws()), (0, 0), "never rolled")

    def test_a_healer_studies_on_the_decision_roll_else_the_stock_exit(self):
        self.villager(5)
        self.s.force(2)                                   # the 14% roll is never asked
        for force, end, called in ((1, "started", ["study"]), (2, "nothing", [])):
            with self.subTest(force=force):
                self.decision_force(force)
                self.assertEqual(self.go(), end)
                self.assertEqual(self.s.called, called)
                self.assertEqual(self.s.draws(), 0)
                self.assertEqual(self.decision_draws(), 1)

    def test_with_fix_huts_a_healer_uses_its_shared_roll(self):
        self.villager(5)
        for answer, end in ((1, "started"), (0, "nothing")):
            with self.subTest(answer=answer):
                self.fix_huts_loaded(True, answer)
                self.decision_force(1)                    # would pass: must not be drawn
                self.assertEqual(self.go(), end)
                self.assertEqual(self.decision_draws(), 0, "the shared roll, not its own")
        self.assertIn("VVFP Fix Huts.dll", self.lookups)

    def test_anyone_else_studies_on_the_roll_else_the_stock_exit(self):
        for preference in (0, 1, 2, 3, 4):
            self.villager(preference)
            for force, end, called in ((1, "started", ["study"]), (2, "nothing", [])):
                with self.subTest(preference=preference, force=force):
                    self.s.force(force)
                    self.decision_force(2)                # not asked for a non-healer
                    self.assertEqual(self.go(), end)
                    self.assertEqual(self.s.called, called)
                    self.assertEqual(self.decision_draws(), 0)

    def test_measured_shares(self):
        # Stock: 0 at this exit for everyone but state 9 (it does nothing).
        # Healer: 75%, so a quarter of these choices go on to other things.
        self.decision_force(0)
        for preference, low, high in ((5, 0.72, 0.78), (1, 0.115, 0.165), (0, 0.115, 0.165)):
            with self.subTest(preference=preference):
                self.villager(preference)
                share = _share(self.s, lambda: self.go() == "started")
                print(f"vv1 Easier Healing Mastery, checkmark {preference}: studies {share:.3f}")
                self.assertTrue(low <= share <= high, share)


@unittest.skipUnless((TEST_DLLS / "VVFP VV1 Research At Max.test.dll").is_file(), TEST_BUILD_ABSENT)
class NewHomeResearchAtMax(unittest.TestCase):
    def setUp(self):
        self.s = Stub("VVFP VV1 Research At Max.test.dll", "VvfpVv1ResearchAtMaxProbe", "VvfpVv1ResearchAtMaxRollTest",
                      {0x44748F: "research", 0x447901: "nothing"})

    def go(self, levels: int, preference: int) -> str:
        self.s.mu.mem_write(VILLAGE + INDEX * STRIDE + 0x3D0, struct.pack("<i", preference))
        # At the site the dispatcher's index argument is [esp+0x14].
        return self.s.run({UC_X86_REG_EAX: levels, UC_X86_REG_ESI: VILLAGE}, stack=(0, 0, 0, 0, INDEX))

    def test_the_site_is_the_rows(self):
        self.assertEqual(self.s.site, 0x447486)
        self.assertEqual(self.s.row.hex().upper(), "83F8130F8D72040000")

    def test_below_the_maximum_the_stock_research_for_anyone(self):
        self.s.force(2)
        for levels in (0, 9, 17):
            with self.subTest(levels=levels):
                self.assertEqual(self.go(levels, 1), "research")
        self.assertEqual(self.s.draws(), 0)

    def test_at_the_maximum(self):
        self.s.force(2)
        self.assertEqual(self.go(18, 3), "research", "checked on Research")
        self.assertEqual(self.s.draws(), 0)
        for preference in (0, 1, 2, 4, 5):
            for force, end in ((1, "research"), (2, "nothing")):
                with self.subTest(preference=preference, force=force):
                    self.s.force(force)
                    self.assertEqual(self.go(18, preference), end)
        self.assertEqual(self.go(19, 3), "nothing", "the row's own bound")

    def test_measured_shares(self):
        for preference, low, high in ((3, 1.0, 1.0), (1, 0.115, 0.165), (0, 0.115, 0.165)):
            with self.subTest(preference=preference):
                share = _share(self.s, lambda: self.go(18, preference) == "research")
                print(f"vv1 Continue Research at Max, checkmark {preference}: researches {share:.3f}")
                self.assertTrue(low <= share <= high, share)


@unittest.skipUnless((TEST_DLLS / "VVFP VV1 Watering Builds.test.dll").is_file(), TEST_BUILD_ABSENT)
class NewHomeWatering(unittest.TestCase):
    def setUp(self):
        self.s = Stub("VVFP VV1 Watering Builds.test.dll", "VvfpVv1WateringGateProbe", "VvfpVv1WateringRollTest",
                      {0x44764D: "water", 0x44765E: "next"})
        self.s.mu.mem_write(VILLAGE + 0x3E010, struct.pack("<I", STATE))

    def go(self, preference: int, done: int = 0, progress: int = 5) -> str:
        self.s.mu.mem_write(VILLAGE + INDEX * STRIDE + 0x3D0, struct.pack("<i", preference))
        self.s.mu.mem_write(STATE + 0x9FC0, bytes([done]))
        self.s.mu.mem_write(STATE + 0x9FBC, struct.pack("<i", progress))
        return self.s.run({UC_X86_REG_ESI: VILLAGE, UC_X86_REG_EBP: INDEX, UC_X86_REG_EBX: 1})

    def test_the_site_is_the_stock_garden_block(self):
        self.assertEqual(self.s.site, 0x447635)
        self.assertEqual(self.s.row.hex().upper(), "8B8610E003003898C09F0000")

    def test_the_stock_tests_come_first(self):
        self.s.force(1)
        self.assertEqual(self.go(4, done=1), "next", "garden restored")
        self.assertEqual(self.go(4, progress=0), "next", "no progress yet")
        self.assertEqual(self.s.draws(), 0)

    def test_a_builder_waters_anyone_else_on_the_roll(self):
        self.s.force(2)
        self.assertEqual(self.go(4), "water")
        self.assertEqual(self.s.draws(), 0)
        for preference in (0, 1, 2, 3, 5):
            for force, end in ((1, "water"), (2, "next")):
                with self.subTest(preference=preference, force=force):
                    self.s.force(force)
                    self.assertEqual(self.go(preference), end)
                    self.assertEqual(self.s.mu.reg_read(UC_X86_REG_EAX), STATE, "eax as the stock block leaves it")

    def test_measured_shares(self):
        for preference, low, high in ((4, 1.0, 1.0), (1, 0.115, 0.165), (0, 0.115, 0.165)):
            with self.subTest(preference=preference):
                share = _share(self.s, lambda: self.go(preference) == "water")
                print(f"vv1 watering the field, checkmark {preference}: waters {share:.3f}")
                self.assertTrue(low <= share <= high, share)


# ---- Player actions are never gated (all five games) -------------------------------------------
# Each gate sits in the work dispatcher (the job the game chose), in the idle
# scheduler, in the catch-up worker, or (VV5 statue) behind the task
# continuation's own return address.  The dispatchers' callers, from the stock
# executables: every call that can carry a gated job (VV1 3 Research / 4
# Building / 5 Healing; VV2 3 Healing / 5 Building; VV3-VV5 2 Healing /
# 4 Building) is the scheduler's or the catch-up worker's; the others push a
# fixed job that no gate is in.  The player's drops reach the actions
# directly: VV1's cactus study 0x443270 from 0x424A6A and watering 0x43FC20
# from 0x4244A0 / 0x424BAE, never through a gated site.
DISPATCHERS = {
    "vv1": (0x4472C0, {0x42E81C, 0x448350, 0x44837D}, {0x447F07: 2}),
    "vv2": (0x45FBF0, {0x43B583, 0x461A03, 0x461A30}, {0x460773: 2, 0x461316: 2, 0x4617B1: 1}),
    "vv3": (0x45AF00, {0x45BFAB, 0x45BFC0, 0x45C237, 0x45C275, 0x45C28A}, {0x426A7A: 1}),
    "vv4": (0x4639B0, {0x46580A, 0x465827, 0x4659CD, 0x465A12, 0x465A25}, {}),
    "vv5": (0x46C540, {0x46E9AC, 0x46E9C9, 0x46F28C, 0x46F2D1, 0x46F2E5}, {}),
}
DIRECT_DROPS = {"vv1": {0x443270: {0x424A6A, 0x4478FC, 0x447ED6}, 0x43FC20: {0x4244A0, 0x424BAE, 0x447650}}}


def _calls_to(image: bytes, base: int, target: int) -> set[int]:
    pe = pefile.PE(data=image, fast_load=True)
    out = set()
    for s in pe.sections:
        if not s.Characteristics & 0x20000000:
            continue
        data = s.get_data()
        va0 = base + s.VirtualAddress
        for i in range(len(data) - 5):
            if data[i] == 0xE8 and (va0 + i + 5 + struct.unpack_from("<i", data, i + 1)[0]) & 0xFFFFFFFF == target:
                out.add(va0 + i)
    return out


@unittest.skipUnless(all((STOCK / e).is_file() for e in EXES.values()), STOCK_ABSENT)
class PlayerActionsAreNeverGated(unittest.TestCase):
    def test_every_gated_job_reaches_the_dispatcher_only_from_the_games_own_choices(self):
        cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for game, (dispatcher, choosers, fixed) in DISPATCHERS.items():
            with self.subTest(game=game):
                image = (STOCK / EXES[game]).read_bytes()
                pe = pefile.PE(data=image, fast_load=True)
                callers = _calls_to(image, 0x400000, dispatcher)
                self.assertEqual(callers, choosers | set(fixed), [hex(c) for c in sorted(callers)])
                for site, job in fixed.items():
                    # The job pushed for these calls is a constant no gate is in.
                    o = pe.get_offset_from_rva(site - 0x400000 - 5)
                    pushes = [i for i in cs.disasm(image[o:o + 5], site - 5) if i.mnemonic == "push"]
                    self.assertTrue(any(i.op_str == str(job) for i in pushes), (game, hex(site)))

    def test_new_homes_drops_call_the_actions_directly(self):
        image = (STOCK / EXES["vv1"]).read_bytes()
        for action, callers in DIRECT_DROPS["vv1"].items():
            with self.subTest(action=hex(action)):
                self.assertEqual(_calls_to(image, 0x400000, action), callers)


class StartupListPlacesTheTwoGates(unittest.TestCase):
    def test_the_two_new_companions_follow_the_totem_store(self):
        # APPEND ONLY: "VVFP VV2 Totems.dll" took entry 21 (bit 22) first, so
        # the two A New Home gates are entries 22 and 23 (bits 23 and 24).
        import re

        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher as vfp
        self.assertEqual(vfp.STARTUP_LOADER_COMPANIONS[21:24], (
            "VVFP VV2 Totems.dll", "VVFP VV1 Easier Healing.dll", "VVFP VV1 Research At Max.dll"))
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        body = header[header.index("VVFP_STARTUP_COMPANIONS[] = {"):]
        body = body[:body.index("};")]
        self.assertEqual(re.findall(r'"([^"]+)"', body), list(vfp.STARTUP_LOADER_COMPANIONS))


if __name__ == "__main__":
    unittest.main()
