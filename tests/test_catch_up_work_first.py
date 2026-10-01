"""Catch-up: builders, healers (and New Believers' devotees) work first, and
The Lost Children's healers keep studying plants -- run from each game's own
catch-up worker.

Time passing while the game was closed, and the patcher's Time Warp, never
run the idle scheduler.  Each game has a catch-up worker (A New Home 0x42E790,
The Lost Children 0x43B4D0, The Secret City 0x45BF00, The Tree of Life
0x465750, New Believers 0x46E8E0), called a few times per age unit for each
adult, which takes the stock picker's job and dispatches it itself.  The
owner's decisions:

1. In each catch-up decision, a villager whose selected job is Building or
   Healing -- and in New Believers Devotion ("the patch is only meant to boost
   skill gain and progress in jobs that kind of lack that natively") -- does
   that job about 3 times in 4, one 75% roll per decision, never always;
   otherwise the stock pick runs.  Other jobs are untouched.  New Believers'
   live play does NOT get the Devotion boost ("devotion will be okay").
2. The low-food safety net wins: at 250 food or less with Farming 20 or more,
   The Secret City, The Tree of Life and New Believers dispatch Farming and
   Work First never overrides it.
3. The Lost Children's healers continue plant study (state 9, the
   scheduler's own continuation 0x460590(index, 40)) during catch-up.

Everything here is EMULATED FROM THE WORKER'S ENTRY in the executable the
patcher renders for the rows (Origins base + Builders Fix Huts When Idle +
Builders and Healers Work First, + Healers Study Plants Regardless of Food in
A New Home / The Lost Children), with the test builds of the companions
mapped and installed as their per-frame callers install them
(tests/test_builders_decision_roll.Machine).  The worker, every patched site
and every companion stub run as machine code; the leaf game routines (the
picker, the RNG, the task-state continuation, the queue processor, the hut
tests, the research step) and the work dispatcher's BODY (after its displaced
entry bytes) are scripted, the last recording which job it was asked for.
Any call into the executable that is not scripted stops the run.
"""
from __future__ import annotations

import struct
import unittest

from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

import pefile

from test_builders_decision_roll import (
    FORCE_FAIL, FORCE_PASS, FORCE_REAL, HALT, OBJ, RECORD, ROWS, STATE, STOCK, STOCK_ABSENT, STOCK_PRESENT,
    TEST_BUILD_ABSENT, TEST_BUILDS_PRESENT, VILLAGE, INDEX, Leaf, Machine, Rolls, rendered,
)


def _stock_bytes_at(game: str, va: int, n: int) -> bytes:
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    return STOCK[game].read_bytes()[pe.get_offset_from_rva(va - 0x400000):][:n]

# Per game: the worker, the dispatcher (entry, body = entry + displaced
# bytes, the stack the displaced bytes took, the argument bytes it pops), the
# research job, the catch-up research site, Building / Healing (/ Devotion).
G = {
    "vv1": dict(worker=0x42E790, disp=0x4472C0, body=0x4472C6, shift=0, argbytes=8, research=2,
                cu_site=0x42E7E0, cu_stock="83F8027532", pick_ret=0x42E821, building=4, healing=5,
                other=1),
    "vv2": dict(worker=0x43B4D0, disp=0x45FBF0, body=0x45FBF6, shift=0, argbytes=8, research=2,
                cu_site=0x43B52D, cu_stock="83FD027534", pick_ret=0x43B588, building=5, healing=3,
                other=1),
    "vv3": dict(worker=0x45BF00, disp=0x45AF00, body=0x45AF0A, shift=0xA0, argbytes=8, research=1,
                cu_site=0x45BF52, cu_stock="83FB017524", pick_ret=0x45BFC5, building=4, healing=2,
                other=3, food=0x582490, farm_ret=0x45BFB0),
    "vv4": dict(worker=0x465750, disp=0x4639B0, body=0x4639BA, shift=0x98, argbytes=4, research=1,
                cu_site=0x46579F, cu_stock="83FF01751F", pick_ret=0x46582C, building=4, healing=2,
                other=3, food=0x4D6DD0, farm_ret=0x46580F),
    "vv5": dict(worker=0x46E8E0, disp=0x46C540, body=0x46C546, shift=0x94, argbytes=4, research=1,
                cu_site=0x46E92F, cu_stock="83FF017531", pick_ret=0x46E9CE, building=4, healing=2,
                devotion=5, other=3, food=0x51D34C, farm_ret=0x46E9B1),
}
GAMES = tuple(G)
FARMING = 0
LATER = ("vv3", "vv4", "vv5")


class Worker(Machine):
    """A Machine whose work dispatcher body is scripted: it records (return
    address of the dispatcher call, job) and answers starts(job)."""

    def __init__(self, game, exe, starts, modules, loaded=None):
        super().__init__(game, exe, modules=modules, loaded=loaded)
        self.g = G[game]
        self.starts = starts
        self.asked: list[tuple[int, int]] = []

    def _hook(self, mu, address, size, user_data):
        if address == self.g["body"] and address != self.stop_at:
            sp = mu.reg_read(UC_X86_REG_ESP)
            frame = sp + self.g["shift"]
            ret, = struct.unpack("<I", mu.mem_read(frame, 4))
            job, = struct.unpack("<i", mu.mem_read(frame + self.g["argbytes"], 4))
            self.asked.append((ret, job))
            self.calls.append(("dispatch", (job,), 0))
            mu.reg_write(UC_X86_REG_EAX, 1 if self.starts(job) else 0)
            mu.reg_write(UC_X86_REG_ESP, frame + 4 + self.g["argbytes"])
            mu.reg_write(UC_X86_REG_EIP, ret)
            return
        super()._hook(mu, address, size, user_data)


def _rows(game):
    return ROWS[game]


def world(game, *, rows=None, runtime=True, force=FORCE_PASS, selected=4, pick=1, starts=None,
          food=1000, farming=10, huts_done=False, task=0, task_done=0, cont=0, rolls=None,
          modules=None, install=True, exe=None) -> Worker:
    """A machine ready to run `game`'s catch-up worker for one adult.
    starts: job -> whether the dispatcher starts something (default: every
    job but 0... except that the picker's 0 is 'nothing' in A New Home)."""
    g = G[game]
    rows = _rows(game) if rows is None else rows
    if modules is None:
        modules = ("fix_huts", "work_first", "healers") if game in ("vv1", "vv2") else ("fix_huts", "work_first")
    starts = starts or (lambda job: job != 0)
    m = Worker(game, rendered(game, tuple(rows)) if exe is None else exe, starts, modules=modules if runtime else ())
    m.real.add(g["disp"])                 # its entry runs (stock or hooked); its body is scripted
    rolls = rolls or Rolls()
    m.rand = rolls
    m.counted = {"research": 0}
    if game == "vv1":
        rec = VILLAGE + INDEX * 0x3D8
        m.w32(OBJ + 4, VILLAGE)
        m.w32(VILLAGE + 0x3E010, STATE)
        m.w32(rec + 0x354, 0)
        m.w32(rec + 0x348, 0x200)
        m.w32(rec + 0x344, 100)
        m.w32(rec + 0x358, 0)
        m.w32(rec + 0x3D0, selected)
        m.w32(STATE + 0xA2CC, 3)
        for off in (0x9FE8, 0x9FF0, 0x9FF8):
            m.w8(STATE + off, 1)
        if not huts_done:
            m.w8(STATE + 0x9FF0, 0)
        m.leaves.update({
            0x439470: Leaf(1, lambda m, a, c, r: 0, name="prepare"),
            0x439AE0: Leaf(2, lambda m, a, c, r: pick, name="picker"),
            0x402F10: Leaf(1, rolls, cdecl=True, name="rand"),
            0x4399F0: Leaf(7, lambda m, a, c, r: 1, name="research step"),
            0x446C70: Leaf(1, lambda m, a, c, r: 0, name="processor"),
        })
        m.plan(g["worker"], HALT, {UC_X86_REG_ECX: OBJ}, stack=(HALT, INDEX))
    elif game == "vv2":
        rec = VILLAGE + INDEX * 0xE48C
        m.w32(OBJ + 4, VILLAGE)
        m.w32(VILLAGE + 0xE574D4, STATE)
        m.w32(rec + 0x53C, 0)
        m.w32(rec + 0x530, 0x200)
        m.w32(rec + 0x52C, 100)
        m.w32(rec + 0x540, 0)
        m.w32(rec + 0x7F8, selected)
        m.w32(STATE + 0x2EA84, 3)
        for off in (0x2E818, 0x2E820, 0x2E828):
            m.w8(STATE + off, 1)
        if not huts_done:
            m.w8(STATE + 0x2E828, 0)
        m.leaves.update({
            0x4492A0: Leaf(1, lambda m, a, c, r: 0, name="prepare"),
            0x449C60: Leaf(2, lambda m, a, c, r: pick, name="picker"),
            0x4031A0: Leaf(1, rolls, cdecl=True, name="rand"),
            0x449B70: Leaf(7, lambda m, a, c, r: 1, name="research step"),
            0x461580: Leaf(1, lambda m, a, c, r: task_done, name="task state"),
            0x460590: Leaf(2, lambda m, a, c, r: cont, name="continue"),
            0x464680: Leaf(1, lambda m, a, c, r: 0, name="processor"),
        })
        m.w32(rec + 0x7E0, task)
        m.plan(g["worker"], HALT, {UC_X86_REG_ECX: OBJ}, stack=(HALT, INDEX))
    elif game == "vv3":
        m.w8(RECORD + 0xE89, 0)
        m.w32(RECORD + 0xDC4, 0x200)
        m.w32(RECORD + 0xE78, 100)
        m.w32(RECORD + 0xE8C, 0)
        m.w32(RECORD + 0xEA0, task)
        m.w32(RECORD + 0xEAC, farming)
        m.w32(RECORD + 0xEC0, selected)
        m.w32(g["food"], food)
        m.leaves.update({
            0x460F70: Leaf(1, lambda m, a, c, r: 0, name="prepare"),
            0x459730: Leaf(1, lambda m, a, c, r: pick, name="picker"),
            0x4032D0: Leaf(1, rolls, cdecl=True, name="rand"),
            0x4616B0: Leaf(0, lambda m, a, c, r: 1, name="research step"),
            0x45AA90: Leaf(1, lambda m, a, c, r: task_done, name="task state"),
            0x45B790: Leaf(1, lambda m, a, c, r: 0, name="processor"),
            0x4321F0: Leaf(1, lambda m, a, c, r: 1 if huts_done or a[0] != 2 else 0, name="done"),
        })
        m.real_ranges.append((0x6DF000, 0x6E1000))     # the rows' stubs in the page Origins appends
        m.plan(g["worker"], HALT, {UC_X86_REG_ECX: VILLAGE}, stack=(HALT, RECORD))
    else:
        m.w32(OBJ + 0x1B88, RECORD)
        m.w8(RECORD + 0x1C48, 0)
        m.w32(RECORD + 0x1B8C, 0x200)
        m.w32(RECORD + 0x1C40, 100)
        m.w32(RECORD + 0x1C4C, 0)
        m.w32(RECORD + 0x1C54, task)
        m.w32(RECORD + (0x1C70 if game == "vv4" else 0x1C74), selected)
        m.w32(g["food"], food)
        hut = 0x438960 if game == "vv4" else 0x43AE80
        names = {"vv4": dict(prepare=0x468C60, picker=0x461CC0, rand=0x4036D0, research=0x469720,
                             task=0x4634D0, farm=0x4618F0, processor=0x464FA0),
                 "vv5": dict(prepare=0x473440, picker=0x46A3C0, rand=0x403660, research=0x474CE0,
                             task=0x46BCF0, farm=0x469D70, processor=0x46E020)}[game]
        m.leaves.update({
            names["prepare"]: Leaf(0, lambda m, a, c, r: 0, name="prepare"),
            names["picker"]: Leaf(0, lambda m, a, c, r: pick, name="picker"),
            names["rand"]: Leaf(1, rolls, cdecl=True, name="rand"),
            names["research"]: Leaf(0, lambda m, a, c, r: 1, name="research step"),
            names["task"]: Leaf(0, lambda m, a, c, r: task_done, name="task state"),
            names["farm"]: Leaf(1, lambda m, a, c, r: 1 if farming >= 20 else 0, name="farm test"),
            names["processor"]: Leaf(0, lambda m, a, c, r: 0, name="processor"),
            hut: Leaf(1, lambda m, a, c, r: 1 if huts_done or a[0] != 21 else 0, name="done"),
        })
        if game == "vv5":
            m.leaves[0x472BD0] = Leaf(0, lambda m, a, c, r: 1, name="research open")
        m.plan(g["worker"], HALT, {UC_X86_REG_ECX: OBJ}, stack=(HALT,))
    if runtime and install:
        m.install_runtime()
    if runtime:
        m.roll_force(force)
    return m


def decide(m: Worker) -> Worker:
    m.asked = []
    m.decide()
    return m


def effects(m: Worker):
    return [c[:2] for c in m.calls if c[0] not in ("done", "GetModuleHandleA", "LoadLibraryA",
                                                    "GetProcAddress")]


def jobs(m: Worker):
    return [job for _, job in m.asked]


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class CatchUpSites(unittest.TestCase):
    """The worker bytes every stub assumes, read from the stock executables,
    and where the installers write them."""

    def test_the_worker_code_the_stubs_assume(self):
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
        for game, g in G.items():
            with self.subTest(game=game):
                self.assertEqual(_stock_bytes_at(game, g["cu_site"], 5).hex().upper(), g["cu_stock"])
                # The pick dispatch returns to pick_ret: the 5 bytes before it
                # are `call dispatcher`.
                code = _stock_bytes_at(game, g["pick_ret"] - 5, 5)
                self.assertEqual(code[0], 0xE8)
                self.assertEqual((g["pick_ret"] + struct.unpack("<i", code[1:])[0]) & 0xFFFFFFFF, g["disp"])
                if "farm_ret" in g:
                    code = _stock_bytes_at(game, g["farm_ret"] - 5, 5)
                    self.assertEqual(code[0], 0xE8)
                    self.assertEqual((g["farm_ret"] + struct.unpack("<i", code[1:])[0]) & 0xFFFFFFFF,
                                     g["disp"])
                    # ... with `push 0` as its job: Farming (The Secret City
                    # also pushes the record).
                    back = 8 if game == "vv3" else 7
                    self.assertEqual(_stock_bytes_at(game, g["farm_ret"] - back, 2), b"\x6A\x00")
                # The research test and its two targets.
                ins = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(_stock_bytes_at(game, g["cu_site"], 5),
                                                               g["cu_site"]))
                self.assertEqual(ins[0].op_str.split(", ")[1], str(g["research"]))

    def test_the_installers_write_the_catch_up_sites(self):
        for game, g in G.items():
            with self.subTest(game=game):
                m = world(game)
                code = bytes(m.mu.mem_read(g["cu_site"], 5))
                self.assertEqual(code[0], 0xE9, f"{game}: catch-up site not installed")
                target = (g["cu_site"] + 5 + struct.unpack("<i", code[1:])[0]) & 0xFFFFFFFF
                if game == "vv3":
                    # The Secret City: the fix-huts row's research stub in the
                    # page Origins appends, in the executable from the start.
                    self.assertTrue(0x6DF800 <= target < 0x6DFC00, hex(target))
                else:
                    self.assertGreaterEqual(target, 0x11000000)    # into "VVFP Work First.dll"
                    self.assertLess(target, 0x12000000)

    def test_the_secret_city_acts_before_any_dispatch(self):
        """The research stub resolves "VVFP Work First.dll" itself: on a fresh
        machine, before any dispatcher call has loaded it, the very first
        catch-up decision -- a research pick -- already puts a healer first."""
        g = G["vv3"]
        m = world("vv3", selected=g["healing"], pick=g["research"])
        self.assertNotIn(("LoadLibraryA", "VVFP Work First.dll"), m.calls)
        decide(m)
        self.assertEqual(jobs(m), [g["healing"]])
        self.assertIn(("LoadLibraryA", "VVFP Work First.dll"), m.calls)
        self.assertNotIn("research step", [c[0] for c in m.calls])

    def test_the_lost_children_healers_site(self):
        self.assertEqual(_stock_bytes_at("vv2", 0x43B581, 7).hex().upper(), "5557E868460200")
        m = world("vv2")
        code = bytes(m.mu.mem_read(0x43B581, 7))
        self.assertEqual(code[0], 0xE9)
        target = (0x43B581 + 5 + struct.unpack("<i", code[1:5])[0]) & 0xFFFFFFFF
        self.assertTrue(0x12000000 <= target < 0x13000000)  # into "VVFP Healers Study.dll"
        self.assertEqual(code[5:], b"\x90\x90")


def _own_jobs(game):
    g = G[game]
    out = [("builder", g["building"]), ("healer", g["healing"])]
    if "devotion" in g:
        out.append(("devotee", g["devotion"]))
    return out


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class OwnJobFirst(unittest.TestCase):
    """Decision 1, forced rolls: the own job first on both routes."""

    def test_pick_dispatch_own_job_first(self):
        for game in GAMES:
            g = G[game]
            for who, own in _own_jobs(game):
                with self.subTest(game=game, who=who):
                    m = decide(world(game, selected=own, pick=g["other"]))
                    self.assertEqual(jobs(m), [own])
                    # Asked by the hook (a stub outside the executable's code),
                    # in place of the worker's own call.
                    self.assertNotEqual(m.asked[0][0], g["pick_ret"])
                    self.assertIn("processor", [c[0] for c in m.calls])
                    # Nothing of theirs to do: the pick runs, as the stock call.
                    m = decide(world(game, selected=own, pick=g["other"], starts=lambda j, o=own: j != o))
                    self.assertEqual(jobs(m), [own, g["other"]])
                    self.assertEqual(m.asked[1][0], g["pick_ret"])

    def test_research_pick_own_job_first(self):
        for game in GAMES:
            g = G[game]
            for who, own in _own_jobs(game):
                with self.subTest(game=game, who=who):
                    # The research step's 5% gate passes (rand 0), so a
                    # skipped research step is visible.
                    m = decide(world(game, selected=own, pick=g["research"], rolls=Rolls(default=lambda n: 0)))
                    self.assertEqual(jobs(m), [own])
                    names = [c[0] for c in m.calls]
                    self.assertNotIn("research step", names)
                    self.assertIn("processor", names)
                    # Nothing of theirs: the stock research step runs.
                    m = decide(world(game, selected=own, pick=g["research"], starts=lambda j: False,
                                     rolls=Rolls(default=lambda n: 0)))
                    self.assertEqual(jobs(m), [own])
                    self.assertIn("research step", [c[0] for c in m.calls])

    def test_forced_fail_is_the_stock_worker(self):
        for game in GAMES:
            g = G[game]
            for who, own in _own_jobs(game):
                for pick in (g["other"], g["research"]):
                    with self.subTest(game=game, who=who, pick=pick):
                        kw = dict(selected=own, pick=pick, rolls=Rolls(default=lambda n: 0))
                        patched = decide(world(game, force=FORCE_FAIL, **kw))
                        stock = decide(world(game, rows=(), runtime=False, **kw))
                        self.assertEqual(effects(patched), effects(stock))
                        self.assertEqual(patched.draws("fix_huts"), 1)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class ThreeTimesInFour(unittest.TestCase):
    """Decision 1 with the real generator: the share of catch-up decisions in
    which a builder / healer / devotee whose pick was something else is put
    to their own job is about 75%, one roll per decision."""

    N = 1000

    def _share(self, game, own, pick):
        m = world(game, selected=own, pick=pick, force=FORCE_REAL)
        own_first = 0
        for _ in range(self.N):
            draws = m.draws("fix_huts")
            decide(m)
            self.assertEqual(m.draws("fix_huts") - draws, 1, "one roll per decision")
            if jobs(m)[:1] == [own]:
                own_first += 1
        return own_first / self.N

    def test_the_share_is_about_three_in_four(self):
        for game in GAMES:
            g = G[game]
            for who, own in _own_jobs(game):
                for route, pick in (("pick", g["other"]), ("research", g["research"])):
                    with self.subTest(game=game, who=who, route=route):
                        share = self._share(game, own, pick)
                        print(f"catch-up share {game} {who} {route}: {share:.3f}")
                        self.assertGreater(share, 0.70)
                        self.assertLess(share, 0.80)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class LowFoodFarmingWins(unittest.TestCase):
    """Decision 2: at 250 food or less with Farming 20+, the worker's Farming
    dispatch is all that runs, with the roll forced to pass."""

    def test_farming_still_wins(self):
        for game in LATER:
            g = G[game]
            for who, own in _own_jobs(game):
                for pick in (g["other"], own):
                    with self.subTest(game=game, who=who, pick=pick):
                        m = decide(world(game, selected=own, pick=pick, food=250, farming=20))
                        self.assertEqual(m.asked, [(g["farm_ret"], FARMING)])
                        self.assertEqual(m.draws("fix_huts"), 0)
                        stock = decide(world(game, rows=(), runtime=False, selected=own, pick=pick,
                                             food=250, farming=20))
                        self.assertEqual(effects(m), effects(stock))

    def test_the_net_is_the_only_reason(self):
        # Not vacuous: one more food, or Farming below 20, and the own job
        # comes first again.
        for game in LATER:
            g = G[game]
            with self.subTest(game=game):
                m = decide(world(game, selected=g["healing"], pick=g["other"], food=251, farming=20))
                self.assertEqual(jobs(m), [g["healing"]])
                m = decide(world(game, selected=g["healing"], pick=g["other"], food=250, farming=19))
                self.assertEqual(jobs(m), [g["healing"]])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class OtherJobsUntouched(unittest.TestCase):
    """Decision 1: every other selected job, a pick that already is the own
    job, and a builder with no hut work are the stock worker, roll forced to
    pass, no roll drawn."""

    def _same_as_stock(self, game, **kw):
        kw.setdefault("rolls", Rolls(default=lambda n: 0))
        m = decide(world(game, **kw))
        stock = decide(world(game, rows=(), runtime=False, **kw))
        self.assertEqual(effects(m), effects(stock))
        self.assertEqual(m.draws("fix_huts"), 0)
        return m

    def test_other_selected_jobs(self):
        for game in GAMES:
            g = G[game]
            own = {g["building"], g["healing"], g.get("devotion")}
            for selected in range(0, 7):
                if selected in own:
                    continue
                for pick in (g["other"], g["research"], 0):
                    with self.subTest(game=game, selected=selected, pick=pick):
                        self._same_as_stock(game, selected=selected, pick=pick)

    def test_the_pick_already_the_own_job(self):
        for game in GAMES:
            for who, own in _own_jobs(game):
                with self.subTest(game=game, who=who):
                    m = self._same_as_stock(game, selected=own, pick=own)
                    self.assertEqual(jobs(m), [own])

    def test_a_builder_without_hut_work(self):
        for game in GAMES:
            g = G[game]
            with self.subTest(game=game):
                self._same_as_stock(game, selected=g["building"], pick=g["other"], huts_done=True)

    def test_new_believers_devotion_stays_live_only_stock(self):
        """The owner: no live-play Devotion boost.  The live scheduler's
        three dispatcher calls with a devotee: the stock request alone."""
        for ret in (0x46F291, 0x46F2D6, 0x46F2EA):
            with self.subTest(ret=ret):
                m = world("vv5", selected=5)
                m.asked = []
                m.run(G["vv5"]["disp"], ret, {UC_X86_REG_ECX: OBJ}, stack=(ret, 3))
                self.assertEqual(m.asked, [(ret, 3)])
                self.assertEqual(m.draws("fix_huts"), 0)
                # ... while a healer there is still put first (live Work First).
                m = world("vv5", selected=2)
                m.asked = []
                m.run(G["vv5"]["disp"], ret, {UC_X86_REG_ECX: OBJ}, stack=(ret, 3))
                self.assertEqual(jobs(m), [2])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class EveryPopulationMode(unittest.TestCase):
    """The tests above run the executable rendered in the "stock" population
    mode; the catch-up behaviour must hold in the other two as well (the
    owner: every patch works in all three modes)."""

    _EXE: dict = {}

    def exe(self, game, mode):
        if (game, mode) not in self._EXE:
            import vv_fun_patcher as vfp
            from test_builders_decision_roll import STOCK
            build = next(b for b in vfp.load_builds() if b.id == game)
            self._EXE[(game, mode)] = bytes(vfp.render_patched_bytes(STOCK[game], build, mode,
                                                                      list(_rows(game)))[0])
        return self._EXE[(game, mode)]

    def test_own_job_first_and_the_farming_net(self):
        for mode in ("collection_progression", "immediate_fixed"):
            for game in GAMES:
                g = G[game]
                exe = self.exe(game, mode)
                for pick in (g["other"], g["research"]):
                    with self.subTest(mode=mode, game=game, pick=pick):
                        m = decide(world(game, exe=exe, selected=g["healing"], pick=pick))
                        self.assertEqual(jobs(m), [g["healing"]])
                if game in LATER:
                    with self.subTest(mode=mode, game=game, farming=True):
                        m = decide(world(game, exe=exe, selected=g["healing"], pick=g["other"],
                                         food=250, farming=20))
                        self.assertEqual(m.asked, [(g["farm_ret"], FARMING)])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class LostChildrenHealersStudyInCatchUp(unittest.TestCase):
    """Decision 3: a villager in plant-study state 9 gets the continuation
    0x460590(index, 40) in catch-up, after the task-state step and before the
    pick, on the decision's roll."""

    def _continues(self, m):
        return [c for c in m.calls if c[0] == "continue"]

    def test_state_nine_continues_plant_study(self):
        # The worker reads no food total: this holds at any food level.
        m = decide(world("vv2", selected=1, pick=1, task=9, cont=1))
        self.assertEqual([c[1] for c in self._continues(m)], [(INDEX, 40)])
        self.assertEqual(m.asked, [])                     # started: no dispatch
        names = [c[0] for c in m.calls]
        self.assertLess(names.index("task state"), names.index("continue"))
        self.assertIn("processor", names)

    def test_nothing_to_study_dispatches_the_pick_as_the_stock_call(self):
        m = decide(world("vv2", selected=1, pick=1, task=9, cont=0))
        self.assertEqual(len(self._continues(m)), 1)
        self.assertEqual(m.asked, [(0x43B588, 1)])

    def test_with_work_first_the_healer_is_still_put_first_after_the_study(self):
        # The healers stub pushes the stock return address, so Work First's
        # dispatcher hook recognises the worker's call.
        m = decide(world("vv2", selected=3, pick=1, task=9, cont=0))
        self.assertEqual(len(self._continues(m)), 1)
        self.assertEqual(jobs(m), [3])

    def test_untouched_cases_are_the_stock_worker(self):
        cases = [dict(task=0), dict(task=8), dict(task=9, force=FORCE_FAIL), dict(task=9, task_done=1),
                 dict(task=9, pick=2)]
        for case in cases:
            with self.subTest(**case):
                kw = dict(selected=1, pick=1, cont=1, rolls=Rolls(default=lambda n: 0))
                kw.update(case)
                force = kw.pop("force", FORCE_PASS)
                m = decide(world("vv2", force=force, **kw))
                stock = decide(world("vv2", rows=(), runtime=False, **kw))
                self.assertEqual(effects(m), effects(stock))
                self.assertEqual(self._continues(m), [])

    def test_the_share_is_about_three_in_four(self):
        m = world("vv2", selected=1, pick=1, task=9, cont=1, force=FORCE_REAL)
        n, hits = 1000, 0
        for _ in range(n):
            decide(m)
            hits += bool(self._continues(m))
        share = hits / n
        print(f"catch-up share vv2 plant study: {share:.3f}")
        self.assertGreater(share, 0.70)
        self.assertLess(share, 0.80)

    def test_a_new_home_needs_no_site(self):
        # A New Home's catch-up already continues plant study through its
        # dispatcher's Healing case (job 5): activity 9 -> 0x443270.
        code = _stock_bytes_at("vv1", 0x4478EF, 13)
        self.assertEqual(code[:8], bytes.fromhex("83BC30B803000009"))     # cmp [rec+0x3B8], 9
        self.assertEqual(code[8:12], bytes.fromhex("7508558B"))            # jne; push ebp; mov ecx, esi
        target = (0x4478FC + 5 + struct.unpack("<i", _stock_bytes_at("vv1", 0x4478FD, 4))[0]) & 0xFFFFFFFF
        self.assertEqual(target, 0x443270)


if __name__ == "__main__":
    unittest.main()
