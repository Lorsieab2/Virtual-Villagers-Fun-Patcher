"""Builders Fix Huts When Idle -- the Building-level gate and A New Home's
false "started" (v1.35.37).

The owner, v1.35.36 installed: "how come vv1 builders stay idle doing
nothing still?" and "In VV1 right now I only have 1 hut built. The builders
should be fixing huts."  Read live from the owner's running village: Building
level ([state+0xA2CC]) 2, hut 9 built and huts 10/11 not, every project flag
complete, both builders (Ghali, Penyo) on "Nothing" for a full minute, and
this companion's check counter still 0 -- the hut site was never reached.

Root causes, both in the stock Building branch:

* Below Building level 3 it gives up at `cmp [state+0xA2CC], 3; jl` (VV1
  0x44765E) -- before the hut fix.  The Lost Children has the same gate
  (0x4601F2).
* A New Home reports "started" (al = bl = 1) on every way it gives up, so a
  builder with nothing to do stands idle and the scheduler never looks
  further.  (The Lost Children and the later games report "nothing".)

Pinned here, running the DLL's stubs in an emulator:

* The level sites' stock bytes are the gates, read from the executables.
* Level 3 or more: the stock code continues.  Below 3: the hut fix runs --
  a complete hut is examined while another is unbuilt.
* A New Home's hut stub: no hut standing -> "nothing" (al = 0) with the
  dispatcher's own pops; every hut complete -> the stock 20% skip now says
  "nothing", otherwise the stock random hut.

All of that is what the stubs do when the decision's 75% roll passes (the
companion's test-build roll is forced to pass here); with it forced to fail
each stub runs exactly the stock code (RollFailedTests).  The roll, and these
stubs reached from the games' own callers, are pinned in
tests/test_builders_decision_roll.py.
"""
from __future__ import annotations

import struct
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX,
    UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "fix_huts" / "VVFP Fix Huts.dll"
# The probes and counters the emulator drives exist only in the TEST build
# (VVFP_TEST, same source; tests/test_shipped_dlls_have_no_test_hooks.py).
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Fix Huts.test.dll"
# tests/test_dlls/ is export-ignore: the release source archive carries no test
# build, so there the tests that drive one skip instead of failing.
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
STOCK = {"vv1": ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
         "vv2": ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"}
STACK = 0x70000000
VILLAGE = 0x20000000
STATE = 0x30000000
INDEX = 7


def _stock(game: str, va: int, n: int) -> bytes:
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    return STOCK[game].read_bytes()[pe.get_offset_from_rva(va - 0x400000):][:n]


def _emulator():
    pe = pefile.PE(str(TEST_DLL))
    base = pe.OPTIONAL_HEADER.ImageBase
    exports = {e.name.decode(): base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    image = pe.get_memory_mapped_image()
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(base, image)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(VILLAGE, 0x1000000)
    mu.mem_map(STATE, 0x100000)
    return mu, exports


def _probe(export: str, game_no: int):
    mu, ex = _emulator()
    buf, ret, esp = STACK - 0x8000, STACK - 0x100, STACK - 0x200
    mu.mem_write(ret, b"\xF4")
    mu.mem_write(esp, struct.pack("<6I", ret, game_no, buf, buf + 0x20, buf + 0x40, buf + 0x60))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(ex[export], ret, count=10000)
    n = mu.reg_read(UC_X86_REG_EAX)
    va, = struct.unpack("<I", mu.mem_read(buf, 4))
    stub, = struct.unpack("<I", mu.mem_read(buf + 0x60, 4))
    return n, va, bytes(mu.mem_read(buf + 0x20, n)), bytes(mu.mem_read(buf + 0x40, n)), stub


G = {
    "vv1": dict(no=1, state_ptr=0x3E010, level=0xA2CC, huts=(0x9FE8, 0x9FF0, 0x9FF8), first_hut=9,
                resume=0x447671, examine=0x446600, started=0x4477A6, rand=0x402F10, hut_pick=0x447737,
                hut_resume=0x44772E, level_stock=0x447664),
    "vv2": dict(no=2, state_ptr=0xE574D4, level=0x2EA84, huts=(0x2E818, 0x2E820, 0x2E828), first_hut=24,
                resume=0x4601FF, examine=0x45F7C0, started=0x4602E5, rand=0x4031A0, hut_resume=0x4602A7,
                nothing=0x46004C),
}


# A New Home's stock construction entries, the "build first" targets: the new-hut
# section (huts 9/10/11), then each started project's check block after its
# random roll.  The construction check enters one of these instead of a fix.
VV1_HUT_SECTION = 0x447528
VV1_PROJECT_BLOCKS = {3: 0x4475A8, 2: 0x4475F8, 4: 0x447635, 8: 0x447685, 7: 0x4476C2, 5: 0x4476FB}
VV1_CONSTRUCTION = {VV1_HUT_SECTION, *VV1_PROJECT_BLOCKS.values()}
VV1_POPULATION = 0x41CF90
VV2_POPULATION = 0x425860
# The hut section's build tail (push ebp; mov ecx, esi; call 0x442090): huts
# 10 and 11 are entered here with the hut pushed (tests/test_finish_started_huts.py).
VV1_HUT_TAIL = 0x447539
VV1_HUT9_CALL = 0x44753C
# The stock bytes there: call 0x442090, the hut gate.  A constant rather than
# a read of the exe, so these emulator tests also run where the stock
# executables are absent (CI); test_patcher.py pins them against the exe.
VV1_HUT9_CALL_STOCK = bytes.fromhex("E84FABFFFF")
# The Lost Children's construction entries (option A): each handler just after
# its own test in the Building branch -- huts 24/25/26, projects 1, 17, 8, 5,
# 12, 11, and the own-task handlers of jump table 0x460550.
VV2_CONSTRUCTION = {0x45FF0B, 0x45FF38, 0x45FF65, 0x4600A7, 0x460171, 0x4601A9, 0x45FF92, 0x46023D, 0x46028C,
                    0x45FEF2, 0x45FF1F, 0x45FF4C, 0x45FF79, 0x45FFA6, 0x460036, 0x45FECD, 0x45FFD3, 0x45FFF4,
                    0x460015}
ROLL_PASS, ROLL_FAIL = 1, 2


class Run:
    """Enter a stub with the dispatcher's saves (esi, ebx, ebp, edi pushed by
    its prologue) under the return address, as the game has them."""

    def __init__(self, game: str, stub: int, level: int, huts: tuple[int, int, int], roll: int = 50,
                 population: int = 10, projects: dict[int, tuple[int, int]] | None = None,
                 hut_call: bytes | None = None, force: int = ROLL_PASS):
        g = G[game]
        mu, ex = _emulator()
        # The decision's roll (VvfpFixHutsRollTest: force, draws), forced.
        mu.mem_write(ex["VvfpFixHutsRollTest"], struct.pack("<ii", force, 0))
        self.draws_at = ex["VvfpFixHutsRollTest"] + 4
        mu.mem_write(VILLAGE + g["state_ptr"], struct.pack("<I", STATE))
        mu.mem_write(STATE + g["level"], struct.pack("<i", level))
        for off, done in zip(g["huts"], huts):
            mu.mem_write(STATE + off, bytes([done]))
        self.population = population
        if game == "vv1":
            # Project record i: (signed progress dword, complete flag byte) at
            # state + 0x9F9C + 8*i.  The new huts start at zero progress.
            for pid, (progress, done) in (projects or {}).items():
                mu.mem_write(STATE + 0x9F9C + 8 * pid, struct.pack("<iB", progress, done))
            for pid, done in zip((9, 10, 11), huts):
                if pid not in (projects or {}):
                    mu.mem_write(STATE + 0x9F9C + 8 * pid, struct.pack("<iB", 0, done))
            # The stock new-hut call the construction check reads (or a caller's
            # substitute), and the game's population counter it calls.
            try:
                mu.mem_map(VV1_HUT9_CALL & ~0xFFF, 0x1000)
            except Exception:
                pass
            mu.mem_write(VV1_HUT9_CALL, hut_call if hut_call is not None else VV1_HUT9_CALL_STOCK)
        exits = [g["resume"], g["examine"], g["started"], g["rand"]] + [g[k] for k in ("hut_pick", "hut_resume", "nothing", "level_stock") if k in g]
        if game == "vv1":
            exits += [VV1_POPULATION, VV1_HUT_TAIL] + list(VV1_CONSTRUCTION)
        else:
            exits += [VV2_POPULATION] + list(VV2_CONSTRUCTION)
        for va in exits:
            try:
                mu.mem_map(va & ~0xFFF, 0x1000)
            except Exception:
                pass
            mu.mem_write(va, b"\xC3")
        self.ret = 0x6FFFF000
        mu.mem_write(self.ret, b"\xF4")
        esp = STACK - 0x400
        # [edi][ebp][ebx][esi][ret][index][job]: the dispatcher's saves
        mu.mem_write(esp, struct.pack("<7I", 0xE0E0E0E0, 0xB0B0B0B0, 0xB1B1B1B1, 0x51515151, self.ret, INDEX, 4))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ESI, VILLAGE)
        mu.reg_write(UC_X86_REG_EBP, INDEX)
        mu.reg_write(UC_X86_REG_EBX, 0 if game == "vv2" else 1)
        mu.reg_write(UC_X86_REG_EDI, INDEX)
        mu.reg_write(UC_X86_REG_EDX, STATE)
        self.g, self.roll, self.exit, self.examined, self.rolled = g, roll, None, None, []
        self.built = None             # the hut pushed at the hut section's build tail
        mu.hook_add(UC_HOOK_CODE, self._hook)
        mu.emu_start(stub, 0, count=100000)
        self.mu, self.esp_before = mu, esp

    def _hook(self, mu, address, size, user_data):
        g = self.g
        if address == VV1_HUT_TAIL and self.g["no"] == 1:
            sp = mu.reg_read(UC_X86_REG_ESP)
            hut, flag = struct.unpack("<2I", mu.mem_read(sp, 8))
            self.built = (hut, flag, sp)
            self.exit = address
            mu.emu_stop()
            return
        if (address == VV1_POPULATION and self.g["no"] == 1) or (address == VV2_POPULATION and self.g["no"] == 2):
            sp = mu.reg_read(UC_X86_REG_ESP)
            ret, = struct.unpack("<I", mu.mem_read(sp, 4))
            self.population_asked = mu.reg_read(UC_X86_REG_ECX)
            mu.reg_write(UC_X86_REG_EAX, self.population)
            mu.reg_write(UC_X86_REG_ESP, sp + 4)
            mu.reg_write(UC_X86_REG_EIP, ret)
            return
        if (self.g["no"] == 1 and address in VV1_CONSTRUCTION) or (self.g["no"] == 2 and address in VV2_CONSTRUCTION):
            self.exit = address
            mu.emu_stop()
            return
        if address == g["rand"]:
            sp = mu.reg_read(UC_X86_REG_ESP)
            self.rolled.append(struct.unpack("<I", mu.mem_read(sp + 4, 4))[0])
            mu.reg_write(UC_X86_REG_EAX, self.roll)
            ret, = struct.unpack("<I", mu.mem_read(sp, 4))
            mu.reg_write(UC_X86_REG_ESP, sp + 4)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address == g["examine"]:
            sp = mu.reg_read(UC_X86_REG_ESP)
            ret, a, b = struct.unpack("<3I", mu.mem_read(sp, 12))
            self.examined = (a, b)
            mu.reg_write(UC_X86_REG_ESP, sp + 12)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address in (g["resume"], g["started"], self.ret) or address in [g.get("hut_pick"), g.get("hut_resume"), g.get("nothing"), g.get("level_stock")]:
            self.exit = address
            mu.emu_stop()

    def reg(self, r):
        return self.mu.reg_read(r)

    def draws(self) -> int:
        return struct.unpack("<i", self.mu.mem_read(self.draws_at, 4))[0]


class LevelGateTests(unittest.TestCase):
    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_sites_are_the_stock_level_gates(self):
        for game, g in G.items():
            with self.subTest(game=game):
                n, va, stock, patched, stub = _probe("VvfpFixHutsProbeLevelSite", g["no"])
                self.assertEqual(_stock(game, va, n), stock)
                rel, = struct.unpack("<i", patched[1:5])
                self.assertEqual(va + 5 + rel, stub)
        # VV1: mov edx, [esi+0x3E010] then cmp [edx+0xA2CC], 3; jl 0x4474A1
        self.assertEqual(_stock("vv1", 0x447664, 7), bytes.fromhex("83BACCA2000003"))
        self.assertEqual(_stock("vv1", 0x44766B, 2), bytes.fromhex("0F8C"))
        # VV2: cmp [edx+0x2EA84], 3; jl 0x46004C, and 0x46004C returns al = 0
        self.assertEqual(_stock("vv2", 0x46004C, 6), bytes.fromhex("5F5D5B32C05E"))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_level_3_or_more_continues_the_stock_branch(self):
        for game, g in G.items():
            with self.subTest(game=game):
                stub = _probe("VvfpFixHutsProbeLevelSite", g["no"])[4]
                r = Run(game, stub, level=3, huts=(1, 0, 0))
                self.assertEqual(r.exit, g["resume"])
                self.assertIsNone(r.examined)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_below_level_3_a_standing_hut_is_fixed(self):
        # The owner's village: level 2, hut 9 built, huts 10/11 not.
        for game, g in G.items():
            with self.subTest(game=game):
                stub = _probe("VvfpFixHutsProbeLevelSite", g["no"])[4]
                r = Run(game, stub, level=2, huts=(1, 0, 0))
                self.assertEqual(r.examined, (INDEX, g["first_hut"]) if game == "vv1" else (INDEX, g["first_hut"]))
                self.assertEqual(r.exit, g["started"])
                self.assertEqual(r.reg(UC_X86_REG_EBX) & 0xFF, 1, "the started epilogue returns bl")
                self.assertEqual(r.rolled, [], "the chooser's hut, never the stock random pick")


class BelowLevelOnlyAHutTests(unittest.TestCase):
    """The owner: "below level 3, at all food levels, villagers will fix huts
    if at least one is built and there are no other building projects
    available".  Every hut built: a built population hut is fixed.  No hut
    built: "nothing".  Codex on #463: never the stock random pick the gate
    used to skip (VV2's fourth option is building 5, not a hut)."""

    HUTS = {"vv1": (9, 10, 11), "vv2": (24, 25, 26)}

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_every_hut_built_a_built_hut_is_fixed(self):
        for game, g in G.items():
            stub = _probe("VvfpFixHutsProbeLevelSite", g["no"])[4]
            with self.subTest(game=game):
                r = Run(game, stub, level=2, huts=(1, 1, 1))
                self.assertIsNotNone(r.examined)
                self.assertIn(r.examined[1], self.HUTS[game], "a population hut, never building 5")
                self.assertEqual(r.exit, g["started"])
                self.assertEqual(r.rolled, [], "the stock random pick is never reached")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_only_built_huts_are_chosen(self):
        # A New Home: hut 9 unbuilt is construction (built first, never passed
        # over for a fix), so its cases keep hut 9 built; population 10 leaves
        # huts 10 and 11 locked.
        # The Lost Children builds hut 24 whenever it is unbuilt, as A New Home
        # builds hut 9, so each game keeps its first hut built here.
        cases = {"vv1": (((1, 1, 0), {0, 1}), ((1, 0, 1), {0, 2})),
                 "vv2": (((1, 1, 0), {0, 1}), ((1, 0, 1), {0, 2}))}
        for game, g in G.items():
            stub = _probe("VvfpFixHutsProbeLevelSite", g["no"])[4]
            for huts, allowed in cases[game]:
                with self.subTest(game=game, huts=huts):
                    seen = {Run(game, stub, level=2, huts=huts).examined[1] - self.HUTS[game][0]
                            for _ in range(6)}
                    self.assertTrue(seen <= allowed, seen)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_lost_children_hut_24_unbuilt_is_built_first_never_a_fix(self):
        # Build first, fix last (tests/test_builders_build_before_fixing.py
        # runs the whole dispatcher): hut 24 unbuilt is construction the
        # stock branch always offers, so the level gate goes straight into
        # the branch's own hut-24 code (option A), with what it expects.
        stub = _probe("VvfpFixHutsProbeLevelSite", 2)[4]
        r = Run("vv2", stub, level=2, huts=(0, 1, 0))
        self.assertIsNone(r.examined)
        self.assertEqual(r.exit, 0x45FF0B, "push ebx; push 0x18: build hut 24")
        self.assertEqual(r.reg(UC_X86_REG_EBX), 0, "this harness's ebx (the game's is 1 here), untouched")
        self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before, "the dispatcher's frame, untouched")
        self.assertEqual(r.reg(UC_X86_REG_EAX), VILLAGE + INDEX * 0xE48C + 0x7E0, "&record+0x7E0")
        self.assertEqual((r.reg(UC_X86_REG_ESI), r.reg(UC_X86_REG_EDI)), (VILLAGE, INDEX))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_no_hut_built_builds_hut_24(self):
        # Nothing stands to fix, but hut 24 is there to build (at any
        # progress), which the stock rolls skipped this time: straight into it
        # (option A), as A New Home builds hut 9.
        stub = _probe("VvfpFixHutsProbeLevelSite", G["vv2"]["no"])[4]
        r = Run("vv2", stub, level=2, huts=(0, 0, 0))
        self.assertIsNone(r.examined, "nothing examined")
        self.assertEqual(r.rolled, [], "the stock random pick is never reached")
        self.assertEqual(r.exit, 0x45FF0B, "the branch's own hut-24 code")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_new_home_no_hut_built_builds_hut_9(self):
        # Hut 9 has no population gate: with none built, a builder builds it.
        stub = _probe("VvfpFixHutsProbeLevelSite", G["vv1"]["no"])[4]
        r = Run("vv1", stub, level=2, huts=(0, 0, 0))
        self.assertIsNone(r.examined, "nothing examined")
        self.assertEqual(r.exit, VV1_HUT_SECTION)
        self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before, "the dispatcher's frame, untouched")
        self.assertEqual((r.reg(UC_X86_REG_ESI), r.reg(UC_X86_REG_EBP), r.reg(UC_X86_REG_EBX) & 0xFF),
                         (VILLAGE, INDEX, 1), "what the stock hut section expects")


class NewHomeBuildFirstTests(unittest.TestCase):
    """The owner: "The builders will prioritize fixing huts OVER building the
    new huts or other projects, when in fact they should build new stuff first,
    then fix huts."  Both A New Home fix sites -- the 20% skip roll and the
    level-below-3 gate -- first enter the stock construction code whenever
    there is construction to do, exactly as the stock branch judges it."""

    def setUp(self):
        self.sites = {"skip roll": _probe("VvfpFixHutsProbeSite", 1)[4],
                      "level gate": _probe("VvfpFixHutsProbeLevelSite", 1)[4]}

    def _sites(self, level_for_skip=3, level_for_gate=2):
        return [(name, stub, level_for_skip if name == "skip roll" else level_for_gate)
                for name, stub in self.sites.items()]

    def _assert_builds(self, r, hut):
        self.assertIsNone(r.examined, "no hut fix while a new hut can be built")
        self.assertEqual(r.exit, VV1_HUT_TAIL, "the hut section's own build tail")
        self.assertEqual(r.built[:2], (hut, 1), "push ebx (1); push the hut")
        self.assertEqual(r.built[2], r.esp_before - 8, "the dispatcher's frame, two pushes deep")
        self.assertEqual((r.reg(UC_X86_REG_ESI), r.reg(UC_X86_REG_EBP)), (VILLAGE, INDEX),
                         "what the build tail expects")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_an_unlocked_new_hut_is_built_not_a_fix(self):
        # Hut 9 built, hut 10 unbuilt and worked on by the player (progress 5).
        for site, stub, level in self._sites():
          with self.subTest(site=site):
            r = Run("vv1", stub, level=level, huts=(1, 0, 0), population=23, projects={10: (5, 0)})
            self._assert_builds(r, 10)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_an_untouched_hut_is_started_only_above_the_stock_numbers(self):
        # Progress 0, or the drawing routine's scaffold mark 1: construction
        # only above 22 (hut 10) / 45 (hut 11), as in the stock game.
        for site, stub, level in self._sites():
          with self.subTest(site=site):
            for progress in (0, 1):
                for population in (10, 15, 22):
                    self.assertIsNotNone(Run("vv1", stub, level=level, huts=(1, 0, 1), population=population,
                                             projects={10: (progress, 0)}).examined)
                for population in (10, 28, 45):
                    self.assertIsNotNone(Run("vv1", stub, level=level, huts=(1, 1, 0), population=population,
                                             projects={11: (progress, 0)}).examined)
                # Above 22 / 45 an untouched hut is construction, as in the stock game.
                self._assert_builds(Run("vv1", stub, level=level, huts=(1, 0, 1), population=23,
                                        projects={10: (progress, 0)}), 10)
                self._assert_builds(Run("vv1", stub, level=level, huts=(1, 1, 0), population=46,
                                        projects={11: (progress, 0)}), 11)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_started_hut_is_built_whatever_the_population(self):
        # The owner's village (v1.35.42): population 17, hut 10 at progress
        # 12.  Progress 1 is the mark the drawing routine leaves on a shown
        # scaffold.  A complete hut is never built again.
        for site, stub, level in self._sites():
          with self.subTest(site=site):
            for progress in (12, 2):
                self._assert_builds(Run("vv1", stub, level=level, huts=(1, 0, 1), population=5,
                                        projects={10: (progress, 0)}), 10)
                self._assert_builds(Run("vv1", stub, level=level, huts=(1, 1, 0), population=5,
                                        projects={11: (progress, 0)}), 11)
            r = Run("vv1", stub, level=level, huts=(1, 1, 0), population=5, projects={10: (12, 1)})
            self.assertIsNotNone(r.examined, "hut 10 complete, hut 11 unstarted below 28: a fix")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_a_started_project_is_continued_not_a_fix(self):
        # Every hut built; one project under way.  Level 3 opens projects 8/7/5,
        # level 2 only 3/2/4 -- the stock branch's own level gates.
        for pid, block in VV1_PROJECT_BLOCKS.items():
            for site, stub, level in self._sites(level_for_skip=3, level_for_gate=2):
              with self.subTest(site=site):
                with self.subTest(project=pid, level=level):
                    r = Run("vv1", stub, level=level, huts=(1, 1, 1), projects={pid: (5, 0)})
                    if pid in (8, 7, 5) and level < 3:
                        self.assertIsNotNone(r.examined, "not open below level 3: the fix")
                    else:
                        self.assertIsNone(r.examined)
                        self.assertEqual(r.exit, block)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_unstarted_or_finished_projects_are_not_construction(self):
        for site, stub, level in self._sites():
          with self.subTest(site=site):
            for record in ((0, 0), (-3, 0), (5, 1)):
                with self.subTest(record=record):
                    r = Run("vv1", stub, level=level, huts=(1, 1, 1), projects={3: record, 2: record})
                    self.assertNotIn(r.exit, VV1_CONSTRUCTION, "nothing to build: no construction entered")
                    # Every hut built: the level gate fixes one itself; the skip
                    # roll hands it to the stock random-hut pick.
                    self.assertTrue(r.examined is not None or r.exit == G["vv1"]["hut_pick"], r.exit)

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_an_older_progress_gate_is_mirrored(self):
        # If a progress gate still owns the new-hut calls, a zero-progress hut
        # is not something the hut section would build, so it is not claimed.
        gated = b"\xE8" + struct.pack("<i", 0x4568D0 - (VV1_HUT9_CALL + 5))
        for site, stub, level in self._sites():
          with self.subTest(site=site):
            r = Run("vv1", stub, level=level, huts=(1, 0, 1), population=30, hut_call=gated)
            self.assertIsNotNone(r.examined, "the gate would skip it: the fix, not a loop")
            r = Run("vv1", stub, level=level, huts=(1, 0, 1), population=30, hut_call=gated,
                    projects={10: (4, 0)})  # worked on by the player
            self._assert_builds(r, 10)


class NewHomeNothingTests(unittest.TestCase):
    def setUp(self):
        self.stub = _probe("VvfpFixHutsProbeSite", 1)[4]

    def _assert_nothing(self, r):
        self.assertEqual(r.exit, r.ret, "returned to the dispatcher's caller")
        self.assertEqual(r.reg(UC_X86_REG_EAX) & 0xFF, 0, "nothing started")
        self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before + 7 * 4, "the saves popped and ret 8")
        self.assertEqual((r.reg(UC_X86_REG_EDI), r.reg(UC_X86_REG_EBP), r.reg(UC_X86_REG_EBX), r.reg(UC_X86_REG_ESI)),
                         (0xE0E0E0E0, 0xB0B0B0B0, 0xB1B1B1B1, 0x51515151), "the dispatcher's own pops, in order")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_no_hut_standing_builds_hut_9(self):
        # No hut stands, so there is nothing to fix -- but hut 9 is there to
        # build, and building comes first.
        r = Run("vv1", self.stub, level=3, huts=(0, 0, 0))
        self.assertIsNone(r.examined)
        self.assertEqual(r.exit, VV1_HUT_SECTION)
        self.assertEqual(r.rolled, [])

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_nothing_to_build_and_nothing_standing_is_nothing(self):
        # Only reachable with a progress gate holding hut 9 at zero progress.
        gated = b"\xE8" + struct.pack("<i", 0x4568D0 - (VV1_HUT9_CALL + 5))
        r = Run("vv1", self.stub, level=3, huts=(0, 0, 0), hut_call=gated)
        self._assert_nothing(r)
        self.assertEqual(r.rolled, [])

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_every_hut_complete_the_skip_roll_is_nothing_else_the_stock_hut(self):
        r = Run("vv1", self.stub, level=3, huts=(1, 1, 1), roll=20)
        self._assert_nothing(r)
        self.assertEqual(r.rolled, [100])
        r = Run("vv1", self.stub, level=3, huts=(1, 1, 1), roll=21)
        self.assertEqual(r.exit, G["vv1"]["hut_pick"], "the stock rand(3) hut pick")


class RollFailedTests(unittest.TestCase):
    """The decision's roll failed (a quarter of the decisions): each stub runs
    the stock code, exactly -- the displaced instructions, then the stock
    continuation with the registers and stack the stock code has there."""

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_below_level_3_the_stock_gate_gives_up(self):
        for game, g in G.items():
            stub = _probe("VvfpFixHutsProbeLevelSite", g["no"])[4]
            for huts in ((1, 0, 0), (1, 1, 1), (0, 1, 0)):
                with self.subTest(game=game, huts=huts):
                    r = Run(game, stub, level=2, huts=huts, population=30, force=ROLL_FAIL)
                    self.assertIsNone(r.examined)
                    self.assertEqual(r.rolled, [])
                    self.assertEqual(r.draws(), 1)
                    self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before)
                    if game == "vv1":
                        # mov edx, [esi+0x3E010] done; on to the stock cmp / jl.
                        self.assertEqual(r.exit, g["level_stock"])
                        self.assertEqual(r.reg(UC_X86_REG_EDX), STATE)
                    else:
                        self.assertEqual(r.exit, g["nothing"], "the stock jl's own target")
                    self.assertEqual((r.reg(UC_X86_REG_ESI), r.reg(UC_X86_REG_EDI), r.reg(UC_X86_REG_EBP)),
                                     (VILLAGE, INDEX, INDEX))

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_level_3_asks_no_roll(self):
        for game, g in G.items():
            stub = _probe("VvfpFixHutsProbeLevelSite", g["no"])[4]
            with self.subTest(game=game):
                r = Run(game, stub, level=3, huts=(1, 0, 0), force=ROLL_FAIL)
                self.assertEqual(r.exit, g["resume"])
                self.assertEqual(r.draws(), 0, "the stock code: nothing to decide")

    @unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_the_hut_site_runs_the_displaced_skip_roll(self):
        for game, g in G.items():
            stub = _probe("VvfpFixHutsProbeSite", g["no"])[4]
            for huts, population in (((1, 0, 0), 10), ((1, 0, 0), 30), ((1, 1, 1), 10), ((0, 0, 0), 10)):
                with self.subTest(game=game, huts=huts, population=population):
                    r = Run(game, stub, level=3, huts=huts, population=population, roll=37, force=ROLL_FAIL)
                    self.assertEqual(r.rolled, [100], "push 0x64; call rand -- the displaced bytes")
                    self.assertEqual(r.exit, g["hut_resume"], "then the stock cmp eax, 0x14")
                    self.assertEqual(r.reg(UC_X86_REG_EAX), 37, "the roll's result in eax")
                    self.assertEqual(r.reg(UC_X86_REG_ESP), r.esp_before, "add esp, 4 done")
                    self.assertIsNone(r.examined)
                    self.assertEqual(r.draws(), 1)


if __name__ == "__main__":
    unittest.main()
