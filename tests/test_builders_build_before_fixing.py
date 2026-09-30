"""Builders Fix Huts When Idle -- build first, fix last (The Lost Children,
The Secret City, The Tree of Life, New Believers).

The owner: "The builders will prioritize fixing huts OVER building the new
huts or other projects, when in fact they should build new stuff first, then
fix huts."  A builder builds any new hut or project the stock game would let
it build or continue first; only when there is no such construction does it
examine / fix a hut.

These tests RUN each game's real Building dispatcher -- the executable's own
code, from its entry with job Building -- in an emulator, with the fix-huts
companion's test build mapped and its detours written exactly where
VvfpFixHutsInstall writes them (The Secret City: the rendered executable with
the row's own page stub, resolving the companion's VvfpFixHutsFilter).  Only
the leaves are scripted: the random roll, the project/hut state and
completion tests, the dislike test and the job-start routines, which record
what the dispatcher asked for.  The random rolls are driven through every
outcome (seeded sweeps plus the all-low and all-high extremes).

  * a new hut available and a complete hut standing -> the new hut is built,
    never a hut fixed;
  * a started project (or, with every hut built, any project) -> it is
    continued, never a hut fixed;
  * the stock rolls that skip construction (VV2's 80% rolls, VV4/VV5's
    dislike roll) -> "nothing", never a hut fix;
  * nothing to build -> a built hut is fixed (the companion's pick, or the
    stock fix-a-hut option once every hut is built).
"""
from __future__ import annotations

import random
import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Fix Huts.test.dll"
WORK_FIRST_TEST_DLL = ROOT / "tests" / "test_dlls" / "VVFP Work First.test.dll"
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
STOCK = {g: ROOT / "research" / "stock-executables" / n for g, n in (
    ("vv2", "Virtual Villagers - The Lost Children.exe"), ("vv3", "Virtual Villagers - The Secret City.exe"),
    ("vv4", "Virtual Villagers - The Tree of Life.exe"), ("vv5", "Virtual Villagers - New Believers.exe"))}
GAME_NO = {"vv2": 2, "vv3": 3, "vv4": 4, "vv5": 5}

STACK_TOP = 0x0F000000
RETURN = 0x0E000000          # a hlt the dispatcher returns to
VILLAGE = 0x20000000         # VV2 village object / VV3 record / VV4-VV5 villager object
STATE = 0x30000000           # VV2 state / VV4-VV5 record
WORK_FIRST_BASE = 0x11000000
INDEX = 7


_IMAGES: dict[tuple[str, int], tuple[bytes, dict[str, int]]] = {}


def _image(key: str, base: int, load) -> tuple[bytes, dict[str, int]]:
    """A PE mapped at `base` (relocated if need be), parsed once per run."""
    if (key, base) not in _IMAGES:
        pe = load()
        if pe.OPTIONAL_HEADER.ImageBase != base:
            pe.relocate_image(base)
        image = pe.get_memory_mapped_image(ImageBase=base)
        exports = {}
        if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
            exports = {e.name.decode(): base + e.address for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        _IMAGES[(key, base)] = (image, exports)
    return _IMAGES[(key, base)]


def _map_pe(mu, key: str, base: int, load) -> dict[str, int]:
    image, exports = _image(key, base, load)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFFF)
    mu.mem_write(base, image)
    return exports


def _probe_stub(mu, exports, export: str, game_no: int) -> tuple[int, bytes]:
    buf, esp = STACK_TOP - 0x8000, STACK_TOP - 0x9000
    mu.mem_write(RETURN, b"\xF4")
    mu.mem_write(esp, struct.pack("<6I", RETURN, game_no, buf, buf + 0x20, buf + 0x40, buf + 0x60))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.emu_start(exports[export], RETURN, count=10000)
    n = mu.reg_read(UC_X86_REG_EAX)
    va, = struct.unpack("<I", mu.mem_read(buf, 4))
    return va, bytes(mu.mem_read(buf + 0x40, n))


def _rendered_vv3() -> bytes:
    import vv_fun_patcher as vfp
    build = next(b for b in vfp.load_builds() if b.id == "vv3")
    rendered, _ = vfp.render_patched_bytes(
        STOCK["vv3"], build, "stock",
        ["vv3_enable_origins_exclusive_features", "vv3_builders_fix_huts"])
    return bytes(rendered)


class Leaf:
    """A scripted game routine: pops `args` dwords (callee-cleaned unless
    `cdecl`), answers `fn(mu, args, ecx)` in eax."""

    def __init__(self, nargs: int, fn, cdecl: bool = False):
        self.nargs, self.fn, self.cdecl = nargs, fn, cdecl


class Dispatcher:
    """Run one game's real Building dispatcher once."""

    def __init__(self, game: str, leaves: dict[int, Leaf], entry: int, args: tuple[int, ...],
                 ecx: int, setup, work_first: bool = False, companion_missing: bool = False):
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        if game == "vv3":
            _map_pe(mu, game, 0x400000, lambda: pefile.PE(data=_rendered_vv3()))
        else:
            _map_pe(mu, game, 0x400000, lambda: pefile.PE(str(STOCK[game])))
        self.ex = _map_pe(mu, "fix_huts", 0x10000000, lambda: pefile.PE(str(TEST_DLL)))
        mu.mem_map(STACK_TOP - 0x20000, 0x20000)
        mu.mem_map(RETURN, 0x1000)
        mu.mem_map(VILLAGE, 0x1000000)
        mu.mem_map(STATE, 0x100000)
        if game == "vv3":
            # The row's page stub resolves the companion once and caches the
            # export at 0x6E0FF8; the Work First cache at 0x6E0FF0 = 1 (absent).
            # companion_missing: the cache says the resolution failed (1).
            mu.mem_write(0x6E0FF8, struct.pack("<I", 1 if companion_missing else self.ex["VvfpFixHutsFilter"]))
            mu.mem_write(0x6E0FF0, struct.pack("<I", 1))
        else:
            # Where VvfpFixHutsInstall writes its detours.
            for probe in ("VvfpFixHutsProbeSite", "VvfpFixHutsProbeLevelSite"):
                if probe == "VvfpFixHutsProbeLevelSite" and game != "vv2":
                    continue
                va, patched = _probe_stub(mu, self.ex, probe, GAME_NO[game])
                mu.mem_write(va, patched)
        if work_first:
            wex = _map_pe(mu, "work_first", WORK_FIRST_BASE, lambda: pefile.PE(str(WORK_FIRST_TEST_DLL)))
            va, patched = _probe_stub(mu, wex, "VvfpWorkFirstProbeSite", GAME_NO[game])
            mu.mem_write(va, patched)
        setup(mu)
        self.leaves, self.calls = leaves, []
        self.ret = args[0]
        esp = STACK_TOP - 0x1000
        mu.mem_write(esp, b"".join(struct.pack("<I", a) for a in args))
        mu.mem_write(RETURN, b"\xF4")
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, ecx)
        self.esp0 = esp
        mu.hook_add(UC_HOOK_CODE, self._hook)
        mu.emu_start(entry, 0, count=2_000_000)
        self.al = mu.reg_read(UC_X86_REG_EAX) & 0xFF
        self.esp_after = mu.reg_read(UC_X86_REG_ESP)

    def _hook(self, mu, address, size, user_data):
        if address == self.ret:
            mu.emu_stop()
            return
        leaf = self.leaves.get(address)
        if leaf is None:
            return
        sp = mu.reg_read(UC_X86_REG_ESP)
        ret, *args = struct.unpack(f"<{1 + leaf.nargs}I", mu.mem_read(sp, 4 * (1 + leaf.nargs)))
        value = leaf.fn(mu, args, mu.reg_read(UC_X86_REG_ECX))
        self.calls.append((address, tuple(args), mu.reg_read(UC_X86_REG_ECX)))
        mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        mu.reg_write(UC_X86_REG_ESP, sp + 4 + (0 if leaf.cdecl else 4 * leaf.nargs))
        mu.reg_write(UC_X86_REG_EIP, ret)



def _rolls(seed):
    """A roll source: None -> all high (every roll passes), 'low' -> every
    roll fails, an int -> a seeded sweep over every outcome."""
    rng = random.Random(seed) if isinstance(seed, int) else None

    def roll(mu, args, ecx):
        n = max(1, args[0])
        if seed == "low":
            return 0
        if seed is None:
            return n - 1
        return rng.randrange(n)
    return roll


SWEEP = [None, "low"] + list(range(60))


# ---- The Lost Children --------------------------------------------------------
V2_BUILD, V2_EXAMINE = 0x457130, 0x45F7C0
V2_CONTINUE = {0x44AB90: 1, 0x45FBE0: 17, 0x45BA20: 8, 0x45A000: 12, 0x45F410: 11}


def run_vv2(seed, level=3, huts=((24, 1), (0, 0), (0, 0)), projects=None, population=10, task=0,
            ea74=3, ea8c=3):
    """huts: (progress, complete) for 24/25/26; projects: {id: (progress,
    complete)}, every other project complete."""
    projects = projects or {}

    def setup(mu):
        mu.mem_write(VILLAGE + 0xE574D4, struct.pack("<I", STATE))
        mu.mem_write(VILLAGE + INDEX * 0xE48C + 0x7E0, struct.pack("<i", task))
        for pid in range(1, 32):
            prog, done = projects.get(pid, (0, 1))
            if pid in (24, 25, 26):
                prog, done = huts[pid - 24]
            mu.mem_write(STATE + 0x2E754 + pid * 8, struct.pack("<iB", prog, done))
        mu.mem_write(STATE + 0x2EA84, struct.pack("<i", level))
        mu.mem_write(STATE + 0x2EA74, struct.pack("<i", ea74))
        mu.mem_write(STATE + 0x2EA8C, struct.pack("<i", ea8c))

    leaves = {
        0x4031A0: Leaf(1, _rolls(seed), cdecl=True),
        0x425860: Leaf(0, lambda mu, a, c: population),
        V2_BUILD: Leaf(3, lambda mu, a, c: 1),
        V2_EXAMINE: Leaf(2, lambda mu, a, c: 1),
    }
    for va in V2_CONTINUE:
        leaves[va] = Leaf(1, lambda mu, a, c: 1)
    return Dispatcher("vv2", leaves, 0x45FBF0, (RETURN, INDEX, 5), VILLAGE, setup)


def vv2_outcome(d: Dispatcher):
    starts = [c for c in d.calls if c[0] in (V2_BUILD, V2_EXAMINE) or c[0] in V2_CONTINUE]
    assert len(starts) <= 1, starts
    assert d.esp_after == d.esp0 + 12, "ret 8"
    if not starts:
        assert d.al == 0, "nothing started reports al = 0"
        return ("nothing",)
    va, args, _ = starts[0]
    assert d.al == 1
    if va == V2_EXAMINE:
        return ("fix", args[1])
    if va == V2_BUILD:
        return ("build", args[1])
    return ("continue", V2_CONTINUE[va])


@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class LostChildrenTests(unittest.TestCase):
    def outcomes(self, **kw):
        return {vv2_outcome(run_vv2(seed, **kw)) for seed in SWEEP}

    def test_a_new_hut_is_built_never_a_hut_fixed(self):
        # Hut 24 built, hut 25 open to build (population > 22, progress >= 2).
        for level in (3, 2, 1):
            with self.subTest(level=level):
                seen = self.outcomes(level=level, huts=((24, 1), (2, 0), (0, 0)), population=30)
                self.assertIn(("build", 25), seen)
                self.assertTrue(seen <= {("build", 25), ("nothing",)}, seen)

    def test_hut_24_under_construction_is_built_first(self):
        # The owner's own save: hut 24 at progress 383, not complete, level 1.
        seen = self.outcomes(level=1, huts=((383, 0), (0, 0), (0, 0)))
        self.assertTrue(seen <= {("build", 24), ("nothing",)}, seen)
        self.assertIn(("build", 24), seen)

    def test_a_started_project_is_continued_never_a_hut_fixed(self):
        for level, huts in ((3, ((24, 1), (700, 1), (11, 1))), (3, ((24, 1), (0, 0), (0, 0))),
                            (2, ((24, 1), (0, 0), (0, 0)))):
            with self.subTest(level=level, huts=huts):
                seen = self.outcomes(level=level, huts=huts, projects={8: (5, 0)})
                self.assertIn(("continue", 8), seen)
                self.assertTrue(seen <= {("continue", 8), ("nothing",)}, seen)

    def test_level_3_projects_are_continued_never_a_hut_fixed(self):
        seen = self.outcomes(level=3, huts=((24, 1), (700, 1), (11, 1)), projects={12: (1, 0)})
        self.assertIn(("continue", 12), seen)
        self.assertTrue(seen <= {("continue", 12), ("nothing",)}, seen)

    def test_the_villagers_own_build_task_comes_before_a_fix(self):
        # [record+0x7E0] = 15: project 7, not complete.
        seen = self.outcomes(level=3, huts=((24, 1), (700, 1), (11, 1)), projects={7: (40, 0)}, task=15)
        self.assertTrue(seen <= {("build", 7), ("nothing",)}, seen)
        self.assertIn(("build", 7), seen)

    def test_every_roll_failing_gives_nothing_not_a_fix(self):
        for kw in (dict(level=3, huts=((24, 1), (2, 0), (0, 0)), population=30),
                   dict(level=2, huts=((24, 1), (0, 0), (0, 0)), projects={8: (5, 0)}),
                   dict(level=3, huts=((24, 1), (700, 1), (11, 1)), projects={5: (2, 0)})):
            with self.subTest(**{k: str(v) for k, v in kw.items()}):
                self.assertEqual(vv2_outcome(run_vv2("low", **kw)), ("nothing",))

    def test_nothing_to_build_a_built_hut_is_fixed(self):
        # Hut 25 not yet open (progress 0 / population 10): nothing to build.
        for level in (3, 2, 1):
            with self.subTest(level=level):
                self.assertEqual(self.outcomes(level=level, huts=((24, 1), (0, 0), (0, 0))), {("fix", 24)})
        # Hut 25 would be open but the population is not above 22 yet.
        self.assertEqual(self.outcomes(level=3, huts=((24, 1), (2, 0), (0, 0)), population=22), {("fix", 24)})

    def test_every_hut_built_nothing_to_build_keeps_the_stock_fix(self):
        seen = self.outcomes(level=3, huts=((24, 1), (700, 1), (11, 1)))
        # the stock rand(4): hut 24/25/26 or building 5, examined
        self.assertTrue(seen <= {("fix", 24), ("fix", 25), ("fix", 26), ("fix", 5), ("nothing",)}, seen)
        self.assertTrue(any(o[0] == "fix" for o in seen), seen)


# ---- The Tree of Life / New Believers ---------------------------------------
LATER = {
    "vv4": dict(entry=0x4639B0, state=0x438980, done=0x438960, obj=0x4D8BF8, dislike=0x45D1F0, rand=0x4036D0,
                start=0x45DEC0, rec_dislikes=0x1E6C, fix_job=0x2E, build_job=8, open_at=1,
                counts={0x430FD0: 0, 0x4396D0: 5, 0x421570: 500}),
    "vv5": dict(entry=0x46C540, state=0x43AEA0, done=0x43AE80, obj=0x51E008, dislike=0x464F90, rand=0x403660,
                start=0x465580, rec_dislikes=0x1F68, fix_job=0x35, build_job=0x10, open_at=2,
                counts={0x4388D0: 0, 0x4322E0: 0}),
}
# Option -> the argument the build job gets (hut / project slot).
BUILD_ARG = {"vv4": {19: 0, 20: 1, 21: 2, 23: 4, 22: 3, 25: 6, 24: 5},
             "vv5": {19: 0, 20: 1, 21: 2, 23: 4, 22: 3, 24: 5}}


def run_later(game, seed, built=(19,), open_=(), dislikes=False, work_first=False):
    """built: complete projects (huts 19-22 and others); open_: projects the
    game offers to build (state test passes, not complete)."""
    g = LATER[game]

    def state(mu, a, c):
        return g["open_at"] if a[0] in open_ else 0

    def done(mu, a, c):
        if game == "vv5" and a[0] == 14:
            return 1                   # VV5 option 7 (project 14) off
        return 1 if a[0] in built else 0

    def setup(mu):
        mu.mem_write(VILLAGE + 0x1B88, struct.pack("<I", STATE))
        mu.mem_write(STATE + 0x1C54, struct.pack("<i", 0))
        mu.mem_write(STATE + (0x1C70 if game == "vv4" else 0x1C74), struct.pack("<i", 4))

    leaves = {
        g["state"]: Leaf(1, state),
        g["done"]: Leaf(1, done),
        g["dislike"]: Leaf(1, lambda mu, a, c: 1 if dislikes and a[0] in (0x1E, 0x35) else 0),
        g["rand"]: Leaf(1, _rolls(seed), cdecl=True),
        g["start"]: Leaf(2, lambda mu, a, c: 1),
    }
    for va, value in g["counts"].items():
        leaves[va] = Leaf(0, lambda mu, a, c, value=value: value)
    if game == "vv4":
        # Option 7: 0x4396D0(0x4D8720) == 0 would offer it; 1 keeps it off.
        leaves[0x4396D0] = Leaf(0, lambda mu, a, c: 5 if c == 0x4D86A8 else 1)
    if work_first:
        # Called from the adult scheduler's farming attempt (job 1) for a
        # villager whose selected job is Building.
        call_site_return = 0x4659D2
        return Dispatcher(game, leaves, g["entry"], (call_site_return, 1), VILLAGE, setup, work_first=True)
    return Dispatcher(game, leaves, g["entry"], (RETURN, 4), VILLAGE, setup)


def later_outcome(game, d: Dispatcher):
    g = LATER[game]
    starts = [c for c in d.calls if c[0] == g["start"]]
    if not starts:
        assert d.al == 0
        return ("nothing",)
    job, arg = starts[0][1][0], starts[0][1][1]
    value = struct.unpack("<i", d.mu.mem_read(arg, 4))[0]
    assert d.al == 1
    if job == g["fix_job"]:
        return ("fix", value)
    if job == g["build_job"]:
        return ("build", value)
    return ("job", job)


@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class TreeOfLifeNewBelieversTests(unittest.TestCase):
    def outcomes(self, game, **kw):
        return {later_outcome(game, run_later(game, seed, **kw)) for seed in SWEEP}

    def test_a_new_hut_is_built_never_a_hut_fixed(self):
        for game in LATER:
            for dislikes in (False, True):
                with self.subTest(game=game, dislikes=dislikes):
                    seen = self.outcomes(game, built=(19,), open_=(20,), dislikes=dislikes)
                    self.assertIn(("build", 1), seen)
                    allowed = {("build", 1)} | ({("nothing",)} if dislikes else set())
                    self.assertTrue(seen <= allowed, seen)

    def test_with_every_hut_built_a_project_comes_before_the_stock_fix(self):
        for game in LATER:
            for project in (23, 24):
                for dislikes in (False, True):
                    with self.subTest(game=game, project=project, dislikes=dislikes):
                        seen = self.outcomes(game, built=(19, 20, 21, 22), open_=(project,), dislikes=dislikes)
                        want = ("build", BUILD_ARG[game][project])
                        self.assertIn(want, seen)
                        self.assertTrue(seen <= {want, ("nothing",)}, seen)
                        if not dislikes:
                            self.assertEqual(seen, {want})

    def test_nothing_to_build_a_built_hut_is_fixed(self):
        for game in LATER:
            for dislikes in (False, True):
                with self.subTest(game=game, dislikes=dislikes):
                    self.assertEqual(self.outcomes(game, built=(19,), dislikes=dislikes), {("fix", 0)})
                    seen = self.outcomes(game, built=(19, 21), dislikes=dislikes)
                    self.assertTrue(seen <= {("fix", 0), ("fix", 2)}, seen)

    def test_every_hut_built_nothing_to_build_keeps_the_stock_fix(self):
        for game in LATER:
            with self.subTest(game=game):
                seen = self.outcomes(game, built=(19, 20, 21, 22))
                self.assertTrue(seen and all(o[0] == "fix" for o in seen), seen)

    @unittest.skipUnless(WORK_FIRST_TEST_DLL.is_file(), TEST_BUILD_ABSENT)
    def test_work_first_asks_for_building_and_gets_the_new_hut(self):
        # Builders and Healers Work First: the scheduler's farming request
        # for a builder first asks the dispatcher for Building.
        for seed in SWEEP[:12]:
            d = run_later("vv4", seed, built=(19,), open_=(20,), work_first=True)
            jobs = [c[1][0] for c in d.calls if c[0] == LATER["vv4"]["start"]]
            self.assertEqual(later_outcome("vv4", d), ("build", 1))
            self.assertEqual(jobs, [8])


# ---- The Secret City ----------------------------------------------------------
V3 = dict(state=0x432210, done=0x4321F0, pstate=0x4358F0, pdone=0x4358D0, rand=0x4032D0, start=0x455570,
          likes=0x4547B0, other=0x45EF30)


def run_vv3(seed, huts_built=(0,), huts_open=(), projects_open=(), companion_missing=False):
    def setup(mu):
        pass

    leaves = {
        V3["state"]: Leaf(1, lambda mu, a, c: 2 if a[0] in huts_open else 0),
        V3["done"]: Leaf(1, lambda mu, a, c: 1 if a[0] in huts_built else 0),
        V3["pstate"]: Leaf(1, lambda mu, a, c: 2 if a[0] in projects_open else 0),
        V3["pdone"]: Leaf(1, lambda mu, a, c: 0),
        V3["rand"]: Leaf(1, _rolls(seed), cdecl=True),
        V3["start"]: Leaf(2, lambda mu, a, c: 1),
        V3["likes"]: Leaf(1, lambda mu, a, c: 0),
        V3["other"]: Leaf(0, lambda mu, a, c: 0),
    }
    return Dispatcher("vv3", leaves, 0x45AF00, (RETURN, VILLAGE, 4), 0x12345678, setup,
                      companion_missing=companion_missing)


def vv3_outcome(d: Dispatcher):
    starts = [c for c in d.calls if c[0] == V3["start"]]
    assert d.esp_after == d.esp0 + 12, "ret 8"
    if not starts:
        assert d.al == 0
        return ("nothing",)
    job, arg = starts[0][1]
    value = struct.unpack("<i", d.mu.mem_read(arg, 4))[0]
    assert d.al == 1
    if job == 0x56:
        return ("fix", value)
    if job == 9:
        return ("build", value)
    return ("job", job)


@unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)
class SecretCityTests(unittest.TestCase):
    def outcomes(self, **kw):
        return {vv3_outcome(run_vv3(seed, **kw)) for seed in SWEEP[:24]}

    def test_a_new_hut_is_built_never_a_hut_fixed(self):
        self.assertEqual(self.outcomes(huts_built=(0,), huts_open=(1,)), {("build", 1)})

    def test_with_every_hut_built_a_project_comes_before_the_stock_fix(self):
        # Project 6 is option 5 (job 0x7F, or the stock 60% idle job 7 for a
        # villager with those likes -- the scripted likes test says no).
        seen = self.outcomes(huts_built=(0, 1, 2, 3), projects_open=(6,))
        self.assertEqual(seen, {("job", 0x7F)})

    def test_nothing_to_build_a_built_hut_is_fixed(self):
        self.assertEqual(self.outcomes(huts_built=(0,)), {("fix", 0)})
        seen = self.outcomes(huts_built=(0, 1, 2, 3))
        self.assertTrue(seen and all(o[0] == "fix" for o in seen), seen)

    def test_without_the_companion_the_page_stub_runs_the_stock_test(self):
        # The stock mix (option 9 beside the project) and the stock
        # "nothing" on an empty list.
        seen = self.outcomes(huts_built=(0, 1, 2, 3), projects_open=(6,), companion_missing=True)
        self.assertIn(("job", 0x7F), seen)
        self.assertTrue(any(o[0] == "fix" for o in seen), seen)
        self.assertEqual(self.outcomes(huts_built=(0,), companion_missing=True), {("nothing",)})


if __name__ == "__main__":
    unittest.main()
