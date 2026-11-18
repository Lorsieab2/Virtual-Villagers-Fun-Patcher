"""Catch-up: villagers practise their selected job (Builders and Healers Work
First, upgraded to skill practice), and The Lost Children's healers keep
studying plants -- run from each game's own catch-up worker.

Time passing while the game was closed, and the patcher's Time Warp, never
run the idle scheduler.  Each game has a catch-up worker (A New Home 0x42E790,
The Lost Children 0x43B4D0, The Secret City 0x45BF00, The Tree of Life
0x465750, New Believers 0x46E8E0), called a few times per age unit for each
adult, which takes the stock picker's job and dispatches it itself.  The
owner's decisions:

1. In each catch-up decision, a villager whose selected job is Farming,
   Research, Healing or Building -- and in New Believers Devotion -- does that
   job about 3 times in 4, one 75% roll per decision, never always; otherwise
   the stock pick runs (the owner, 2026-11-17: the skill-practice upgrade
   "works in catch-up too").  Research never displaces a Farming pick.
2. Parenting stays under the Birth Control patches: a villager checked on
   Parenting is never put first, and the worker's Parenting pick -- its 5%
   catch-up conception attempt, which an earlier version hooked as
   "research" -- is never touched.
3. The low-food safety net wins: at 250 food or less with Farming 20 or more,
   The Secret City, The Tree of Life and New Believers dispatch Farming and
   Work First never overrides it.
4. Builders never start a project nobody was dropped on: The Tree of Life
   never while its Building case offers puzzle work it can start by itself
   (the stream only until The Stream is solved, the owner's item 73); A New
   Home's / The Lost Children's hut starts: tests/test_work_first.py.
5. The fallback: a healer whose Healing work started nothing studies an
   understood plant once Herb Mastery is solved (A New Home -- never the
   Magic Plant of Life -- and The Lost Children).  "Doing exercise" stays the
   game's own leisure: a builder with nothing to build is never sent to it.
6. The "untrained" mark (The Tree of Life, New Believers) is lifted for one
   dispatch of the villager's selected job, and put back.
7. Only above skill 5 (the owner, 2026-11-18): nobody is put first while
   their skill in that job is 5 or less.
8. The Lost Children's healers continue plant study (state 9, the scheduler's
   own continuation 0x460590(index, 40)) during catch-up; A New Home's the same
   way (0x447CD0(index, 60), tests/test_easier_healing_mastery.py).

Everything here is EMULATED FROM THE WORKER'S ENTRY in the executable the
patcher renders for the rows (Origins base + Builders Fix Huts When Idle +
Villagers Work Their Own Job First, + Healers Study Plants Regardless of Food in
A New Home / The Lost Children), with the test builds of the companions
mapped and installed as their per-frame callers install them
(tests/test_builders_decision_roll.Machine).  The worker, every patched site
and every companion stub run as machine code; the leaf game routines (the
picker, the RNG, the task-state continuation, the queue processor, the hut
tests, the Parenting step, the plant starters, the do-action routine) and the
work dispatcher's BODY (after its displaced entry bytes) are scripted, the
last recording which job it was asked for.  Any call into the executable that
is not scripted stops the run.  Each behaviour here fails with the earlier
DLL (no Farming/Research/Devotion first, the Parenting pick hooked, no guard,
no fallback).
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
# worker's Parenting pick test (never hooked), the jobs.
G = {
    "vv1": dict(worker=0x42E790, disp=0x4472C0, body=0x4472C6, shift=0, argbytes=8,
                parent_site=0x42E7E0, parent_stock="83F8027532", pick_ret=0x42E821,
                farming=1, parenting=2, research=3, building=4, healing=5),
    "vv2": dict(worker=0x43B4D0, disp=0x45FBF0, body=0x45FBF6, shift=0, argbytes=8,
                parent_site=0x43B52D, parent_stock="83FD027534", pick_ret=0x43B588,
                farming=1, parenting=2, healing=3, research=4, building=5),
    "vv3": dict(worker=0x45BF00, disp=0x45AF00, body=0x45AF0A, shift=0xA0, argbytes=8,
                parent_site=0x45BF52, parent_stock="83FB017524", pick_ret=0x45BFC5,
                farming=0, parenting=1, healing=2, research=3, building=4,
                food=0x582490, farm_ret=0x45BFB0, do_action=0x455570),
    "vv4": dict(worker=0x465750, disp=0x4639B0, body=0x4639BA, shift=0x98, argbytes=4,
                parent_site=0x46579F, parent_stock="83FF01751F", pick_ret=0x46582C,
                farming=0, parenting=1, healing=2, research=3, building=4,
                food=0x4D6DD0, farm_ret=0x46580F, do_action=0x45DEC0),
    "vv5": dict(worker=0x46E8E0, disp=0x46C540, body=0x46C546, shift=0x94, argbytes=4,
                parent_site=0x46E92F, parent_stock="83FF017531", pick_ret=0x46E9CE,
                farming=0, parenting=1, healing=2, research=3, building=4, devotion=5,
                food=0x51D34C, farm_ret=0x46E9B1, do_action=0x465580),
}
GAMES = tuple(G)
FARMING = 0
SEED = 0x9E3779B9                  # the roll generator's state for the share measurements
LATER = ("vv3", "vv4", "vv5")
# A New Home's herbs (starter, understood flag, trait-tested), The Lost Children's six.
VV1_HERBS = ((0x443270, 0xA068, False), (0x4435B0, 0xA060, True), (0x443440, 0xA070, True),
             (0x443720, 0xA078, True))
VV2_HERBS = tuple((s, f, True) for s, f in ((0x458CD0, 0x2E860), (0x4589A0, 0x2E868), (0x458B70, 0x2E870),
                                             (0x458E30, 0x2E878), (0x458FD0, 0x2E880), (0x459130, 0x2E888)))
MAGIC_PLANT = 0x443030


class Worker(Machine):
    """A Machine whose work dispatcher body is scripted: it records (return
    address of the dispatcher call, job) and answers starts(job)."""

    # Where a scripted Building dispatch returns from asking the fix-huts
    # companion's roll (inside the HALT page, which holds a hlt at +0).
    ASKED = HALT + 0x10

    def __init__(self, game, exe, starts, modules, loaded=None):
        super().__init__(game, exe, modules=modules, loaded=loaded)
        self.g = G[game]
        self.starts = starts
        self.asked: list[tuple[int, int]] = []
        self.marks: list[int] = []        # New Believers' untrained mark at each dispatch
        # When set, a Building dispatch asks VvfpFixHutsRoll first, as the
        # companion's own sites inside the Building dispatcher do; the answers
        # are recorded in building_rolls.
        self.building_asks = False
        self.building_rolls: list[int] = []
        self._pending = None

    def _answer(self, mu, frame, job):
        ret, = struct.unpack("<I", mu.mem_read(frame, 4))
        mu.reg_write(UC_X86_REG_EAX, 1 if self.starts(job) else 0)
        mu.reg_write(UC_X86_REG_ESP, frame + 4 + self.g["argbytes"])
        mu.reg_write(UC_X86_REG_EIP, ret)

    def _hook(self, mu, address, size, user_data):
        if address == self.ASKED and self._pending is not None:
            frame, job = self._pending
            self._pending = None
            self.building_rolls.append(mu.reg_read(UC_X86_REG_EAX) & 0xFF)
            self._answer(mu, frame, job)
            return
        if address == self.g["body"] and address != self.stop_at:
            sp = mu.reg_read(UC_X86_REG_ESP)
            frame = sp + self.g["shift"]
            ret, = struct.unpack("<I", mu.mem_read(frame, 4))
            job, = struct.unpack("<i", mu.mem_read(frame + self.g["argbytes"], 4))
            self.asked.append((ret, job))
            self.calls.append(("dispatch", (job,), 0))
            if self.game in ("vv4", "vv5"):
                self.marks.append(self.u32(RECORD + 0x1C54))
            if self.building_asks and job == self.g["building"] and "fix_huts" in self.exports:
                self._pending = (frame, job)
                mu.mem_write(sp - 4, struct.pack("<I", self.ASKED))
                mu.reg_write(UC_X86_REG_ESP, sp - 4)
                mu.reg_write(UC_X86_REG_EIP, self.exports["fix_huts"]["VvfpFixHutsRoll"])
                return
            self._answer(mu, frame, job)
            return
        super()._hook(mu, address, size, user_data)


def _rows(game):
    return ROWS[game]


def world(game, *, rows=None, runtime=True, force=FORCE_PASS, selected=4, pick=1, starts=None,
          food=1000, farming=10, huts_done=False, task=0, task_done=0, cont=0, rolls=None,
          modules=None, install=True, exe=None, herb_mastery=False, herbs=(), trait=False,
          stream=0, stream_solved=False, piers_stage=5, rubble_stage=1, population=10,
          hut_progress=5, farm_level=2, skill=30) -> Worker:
    """A machine ready to run `game`'s catch-up worker for one adult.
    starts: job -> whether the dispatcher starts something (default: every
    job but 0... except that the picker's 0 is 'nothing' in A New Home).
    herbs: indexes of understood herbs (VV1 / VV2 tables above); stream,
    piers_stage, rubble_stage: The Tree of Life's puzzle tests (the defaults
    offer no puzzle work); hut_progress: A New Home's hut 10 / The Lost
    Children's hut 24 progress (2 or more: a player worked on it); skill:
    every job's skill (above 5: the game's own pickers' rule)."""
    g = G[game]
    rows = _rows(game) if rows is None else rows
    if modules is None:
        modules = ("fix_huts", "work_first", "healers") if game in ("vv1", "vv2") else ("fix_huts", "work_first")
    if starts is None:
        # A New Home / The Lost Children have no job 0; the later games' job 0 is Farming.
        starts = (lambda job: job != 0) if game in ("vv1", "vv2") else (lambda job: True)
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
        for off in (0x3BC, 0x3C0, 0x3C4, 0x3C8, 0x3CC):
            m.w32(rec + off, skill)
        m.w32(STATE + 0xA2CC, 3)
        m.w32(STATE + 0xA2E4, farm_level)
        for off in (0x9FE8, 0x9FF0, 0x9FF8):
            m.w8(STATE + off, 1)
        if not huts_done:
            m.w8(STATE + 0x9FF0, 0)
            m.w32(STATE + 0x9FEC, hut_progress)
        m.w8(STATE + 0xA080, 1 if herb_mastery else 0)
        for i in herbs:
            m.w8(STATE + VV1_HERBS[i][1], 1)
        m.leaves.update({
            0x439470: Leaf(1, lambda m, a, c, r: 0, name="prepare"),
            0x439AE0: Leaf(2, lambda m, a, c, r: pick, name="picker"),
            0x402F10: Leaf(1, rolls, cdecl=True, name="rand"),
            0x4399F0: Leaf(7, lambda m, a, c, r: 1, name="parenting step"),
            0x446C70: Leaf(1, lambda m, a, c, r: 0, name="processor"),
            0x41CF90: Leaf(0, lambda m, a, c, r: population, name="population"),
            0x4372E0: Leaf(2, lambda m, a, c, r: 1 if trait else 0, name="trait"),
            MAGIC_PLANT: Leaf(1, lambda m, a, c, r: 0, name="magic plant"),
        })
        for k, (starter, _, _) in enumerate(VV1_HERBS):
            m.leaves[starter] = Leaf(1, lambda m, a, c, r: 0, name=f"herb {k}")
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
        for off in (0x7E4, 0x7E8, 0x7EC, 0x7F0, 0x7F4):
            m.w32(rec + off, skill)
        m.w32(STATE + 0x2EA84, 3)
        for off in (0x2E818, 0x2E820, 0x2E828):
            m.w8(STATE + off, 1)
        if not huts_done:
            m.w8(STATE + 0x2E828, 0)
        m.w32(STATE + 0x2E814, hut_progress)
        m.w8(STATE + 0x2E788, 1 if herb_mastery else 0)
        for i in herbs:
            m.w8(STATE + VV2_HERBS[i][1], 1)
        m.leaves.update({
            0x4492A0: Leaf(1, lambda m, a, c, r: 0, name="prepare"),
            0x449C60: Leaf(2, lambda m, a, c, r: pick, name="picker"),
            0x4031A0: Leaf(1, rolls, cdecl=True, name="rand"),
            0x449B70: Leaf(7, lambda m, a, c, r: 1, name="parenting step"),
            0x461580: Leaf(1, lambda m, a, c, r: task_done, name="task state"),
            0x460590: Leaf(2, lambda m, a, c, r: cont, name="continue"),
            0x464680: Leaf(1, lambda m, a, c, r: 0, name="processor"),
            0x4454E0: Leaf(2, lambda m, a, c, r: 1 if trait else 0, name="trait"),
        })
        for k, (starter, _, _) in enumerate(VV2_HERBS):
            m.leaves[starter] = Leaf(1, lambda m, a, c, r: 0, name=f"herb {k}")
        m.w32(rec + 0x7E0, task)
        m.plan(g["worker"], HALT, {UC_X86_REG_ECX: OBJ}, stack=(HALT, INDEX))
    elif game == "vv3":
        m.w8(RECORD + 0xE89, 0)
        m.w32(RECORD + 0xDC4, 0x200)
        m.w32(RECORD + 0xE78, 100)
        m.w32(RECORD + 0xE8C, 0)
        m.w32(RECORD + 0xEA0, task)
        for job in range(5):
            m.w32(RECORD + 0xEAC + 4 * job, skill)
        m.w32(RECORD + 0xEAC, farming)
        m.w32(RECORD + 0xEC0, selected)
        m.w32(g["food"], food)
        m.leaves.update({
            0x460F70: Leaf(1, lambda m, a, c, r: 0, name="prepare"),
            0x459730: Leaf(1, lambda m, a, c, r: pick, name="picker"),
            0x4032D0: Leaf(1, rolls, cdecl=True, name="rand"),
            0x4616B0: Leaf(0, lambda m, a, c, r: 1, name="parenting step"),
            0x45AA90: Leaf(1, lambda m, a, c, r: task_done, name="task state"),
            0x45B790: Leaf(1, lambda m, a, c, r: 0, name="processor"),
            0x4321F0: Leaf(1, lambda m, a, c, r: 1 if huts_done or a[0] != 2 else 0, name="done"),
            g["do_action"]: Leaf(2, lambda m, a, c, r: 1, name="do-action"),
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
        for job in range(5 if game == "vv4" else 6):
            m.mu.mem_write(RECORD + 0x1C5C + 4 * job, struct.pack("<f", float(skill)))
        m.w32(RECORD + (0x1C70 if game == "vv4" else 0x1C74), selected)
        m.w32(g["food"], food)
        hut = 0x438960 if game == "vv4" else 0x43AE80
        names = {"vv4": dict(prepare=0x468C60, picker=0x461CC0, rand=0x4036D0, parenting=0x469720,
                             task=0x4634D0, farm=0x4618F0, processor=0x464FA0),
                 "vv5": dict(prepare=0x473440, picker=0x46A3C0, rand=0x403660, parenting=0x474CE0,
                             task=0x46BCF0, farm=0x469D70, processor=0x46E020)}[game]

        def done(m, a, c, r):
            if game == "vv4" and a[0] == 1:
                return 1 if stream_solved else 0            # The Stream
            return 1 if huts_done or a[0] != 21 else 0

        m.leaves.update({
            names["prepare"]: Leaf(0, lambda m, a, c, r: 0, name="prepare"),
            names["picker"]: Leaf(0, lambda m, a, c, r: pick, name="picker"),
            names["rand"]: Leaf(1, rolls, cdecl=True, name="rand"),
            names["parenting"]: Leaf(0, lambda m, a, c, r: 1, name="parenting step"),
            names["task"]: Leaf(0, lambda m, a, c, r: task_done, name="task state"),
            names["farm"]: Leaf(1, lambda m, a, c, r: 1 if farming >= 20 else 0, name="farm test"),
            names["processor"]: Leaf(0, lambda m, a, c, r: 0, name="processor"),
            hut: Leaf(1, done, name="done"),
            g["do_action"]: Leaf(2, lambda m, a, c, r: 1, name="do-action"),
        })
        if game == "vv4":
            m.leaves.update({
                0x430FD0: Leaf(0, lambda m, a, c, r: stream, name="stream"),
                0x4396D0: Leaf(0, lambda m, a, c, r: piers_stage if c == 0x4D86A8 else rubble_stage, name="stage"),
                0x421570: Leaf(0, lambda m, a, c, r: 0, name="piers"),
            })
            m.w32(0x4D8A8C, 0)
        if game == "vv5":
            m.leaves[0x472BD0] = Leaf(0, lambda m, a, c, r: 1, name="housing")
        m.plan(g["worker"], HALT, {UC_X86_REG_ECX: OBJ}, stack=(HALT,))
    if runtime and install:
        m.install_runtime()
    if runtime:
        m.roll_force(force)
    return m


def decide(m: Worker) -> Worker:
    m.asked = []
    m.marks = []
    m.decide()
    return m


def effects(m: Worker):
    return [c[:2] for c in m.calls if c[0] not in ("done", "GetModuleHandleA", "LoadLibraryA",
                                                    "LoadLibraryExW", "GetFileAttributesW",
                                                    "GetProcAddress", "VirtualQuery", "population",
                                                    "stream", "stage", "piers")]


def jobs(m: Worker):
    return [job for _, job in m.asked]


def names(m: Worker):
    return [c[0] for c in m.calls]


def _own_jobs(game):
    """Every job the upgrade puts first."""
    g = G[game]
    out = [("farmer", g["farming"]), ("researcher", g["research"]), ("healer", g["healing"]),
           ("builder", g["building"])]
    if "devotion" in g:
        out.append(("devotee", g["devotion"]))
    return out


def _other(game, own):
    """A pick that is not the villager's own job, nor Parenting (whose pick
    never reaches the dispatcher), nor Farming for a researcher."""
    g = G[game]
    for job in (g["healing"], g["building"], g["farming"]):
        if job != own:
            return job
    raise AssertionError


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class CatchUpSites(unittest.TestCase):
    """The worker bytes the hook assumes, read from the stock executables."""

    def test_the_worker_code_the_hook_assumes(self):
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
        for game, g in G.items():
            with self.subTest(game=game):
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
                # The worker's other branch tests the Parenting pick.
                self.assertEqual(_stock_bytes_at(game, g["parent_site"], 5).hex().upper(), g["parent_stock"])
                ins = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(_stock_bytes_at(game, g["parent_site"], 5),
                                                               g["parent_site"]))
                self.assertEqual(ins[0].op_str.split(", ")[1], str(g["parenting"]))

    def test_the_parenting_pick_is_never_hooked(self):
        """Birth Control owns the catch-up conception attempt: the worker's
        Parenting test keeps its stock bytes once everything is installed (an
        earlier version diverted it, calling it the research pick)."""
        for game, g in G.items():
            with self.subTest(game=game):
                m = world(game)
                self.assertEqual(bytes(m.mu.mem_read(g["parent_site"], 5)).hex().upper(), g["parent_stock"])
                # The dispatcher hook is installed (A New Home, The Lost
                # Children, The Tree of Life, New Believers) or in the page.
                self.assertEqual(m.mu.mem_read(g["disp"], 1)[0], 0xE9)

    def test_the_lost_children_healers_site(self):
        self.assertEqual(_stock_bytes_at("vv2", 0x43B581, 7).hex().upper(), "5557E868460200")
        m = world("vv2")
        code = bytes(m.mu.mem_read(0x43B581, 7))
        self.assertEqual(code[0], 0xE9)
        target = (0x43B581 + 5 + struct.unpack("<i", code[1:5])[0]) & 0xFFFFFFFF
        self.assertTrue(0x12000000 <= target < 0x13000000)  # into "VVFP Healers Study.dll"
        self.assertEqual(code[5:], b"\x90\x90")


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class OwnJobFirst(unittest.TestCase):
    """Decision 1, forced rolls: the own job first through the pick dispatch."""

    def test_pick_dispatch_own_job_first(self):
        for game in GAMES:
            g = G[game]
            for who, own in _own_jobs(game):
                other = _other(game, own)
                with self.subTest(game=game, who=who):
                    m = decide(world(game, selected=own, pick=other))
                    self.assertEqual(jobs(m), [own])
                    # Asked by the hook (a stub outside the executable's code),
                    # in place of the worker's own call.
                    self.assertNotEqual(m.asked[0][0], g["pick_ret"])
                    self.assertIn("processor", names(m))
                    # Nothing of theirs to do: the pick runs, as the stock call.
                    m = decide(world(game, selected=own, pick=other, starts=lambda j, o=own: j != o))
                    self.assertEqual(jobs(m)[0], own)
                    self.assertEqual(m.asked[-1], (g["pick_ret"], other))

    def test_forced_fail_is_the_stock_worker(self):
        for game in GAMES:
            g = G[game]
            for who, own in _own_jobs(game):
                for pick in (_other(game, own), g["parenting"]):
                    with self.subTest(game=game, who=who, pick=pick):
                        kw = dict(selected=own, pick=pick, rolls=Rolls(default=lambda n: 0))
                        patched = decide(world(game, force=FORCE_FAIL, **kw))
                        stock = decide(world(game, rows=(), runtime=False, **kw))
                        self.assertEqual(effects(patched), effects(stock))

    def test_the_parenting_pick_is_the_stock_worker(self):
        """Decision 2: whatever the villager's job, the Parenting pick runs
        the stock 5% step (here forced on by rand 0), never their own job --
        the earlier version dispatched builders' and healers' own job here."""
        for game in GAMES:
            g = G[game]
            for who, own in _own_jobs(game) + [("parent", g["parenting"])]:
                with self.subTest(game=game, who=who):
                    kw = dict(selected=own, pick=g["parenting"], rolls=Rolls(default=lambda n: 0))
                    patched = decide(world(game, **kw))
                    stock = decide(world(game, rows=(), runtime=False, **kw))
                    self.assertEqual(effects(patched), effects(stock))
                    self.assertIn("parenting step", names(patched))
                    self.assertEqual(jobs(patched), [])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class ThreeTimesInFour(unittest.TestCase):
    """Decision 1 with the real generator: the share of catch-up decisions in
    which a villager whose pick was something else is put to their own job is
    about 75%, one roll per decision."""

    N = 600

    def _share(self, game, own, pick):
        m = world(game, selected=own, pick=pick, force=FORCE_REAL)
        m.seed(SEED)                      # the companion's real generator, from a fixed state
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
            for who, own in _own_jobs(game):
                with self.subTest(game=game, who=who):
                    share = self._share(game, own, _other(game, own))
                    print(f"catch-up share {game} {who}: {share:.3f}")
                    self.assertGreater(share, 0.68)
                    self.assertLess(share, 0.82)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class OneRollPerCatchUpDecision(unittest.TestCase):
    """Codex on #494: every hook the worker's choice reaches -- Work First's
    pick route, the companion's own sites in the Building dispatcher
    (modelled here by the scripted Building dispatch asking VvfpFixHutsRoll,
    as they do), and The Lost Children's plant study -- shares exactly one
    roll."""

    N = 600

    def _measure(self, m, intervened):
        hits = 0
        for _ in range(self.N):
            draws = m.draws("fix_huts")
            m.building_rolls = []
            decide(m)
            self.assertEqual(m.draws("fix_huts") - draws, 1, "one roll per catch-up decision")
            self.assertEqual(m.call_export("fix_huts", "VvfpFixHutsProbeDepth"), 0, "the decision is closed")
            hits += bool(intervened(m))
        return hits / self.N

    def test_builders_share_the_roll_with_the_building_dispatcher(self):
        for game in GAMES:
            g = G[game]
            for route, pick in (("pick", g["healing"]), ("own", g["building"])):
                with self.subTest(game=game, route=route):
                    m = world(game, selected=g["building"], pick=pick, force=FORCE_REAL)
                    m.building_asks = True
                    m.seed(SEED)

                    def intervened(m):
                        rolls = set(m.building_rolls)
                        self.assertLessEqual(len(rolls), 1, "the Building dispatch saw two rolls")
                        if jobs(m)[:1] == [g["building"]] and pick != g["building"]:
                            # Work First stepped in: the dispatcher sees the same pass.
                            self.assertEqual(rolls, {1})
                        return rolls == {1} or (jobs(m)[:1] == [g["building"]] and pick != g["building"])
                    share = self._measure(m, intervened)
                    print(f"catch-up combined {game} builder {route}: {share:.3f}")
                    self.assertGreater(share, 0.68)
                    self.assertLess(share, 0.82)

    def test_the_lost_children_studying_healer_rolls_once(self):
        # The healer's plant study starts nothing, so the pick is dispatched
        # through Work First's hook: the same roll.
        m = world("vv2", selected=G["vv2"]["healing"], pick=1, task=9, cont=0, force=FORCE_REAL)
        m.seed(SEED)

        def intervened(m):
            studied = any(c[0] == "continue" for c in m.calls)
            first = jobs(m)[:1] == [G["vv2"]["healing"]]
            if studied:
                self.assertTrue(first, "plant study without the shared roll")
            return first
        share = self._measure(m, intervened)
        print(f"catch-up combined vv2 studying healer: {share:.3f}")
        self.assertGreater(share, 0.68)
        self.assertLess(share, 0.82)

    def test_the_workers_are_wrapped(self):
        entries = {"vv1": 0x42E790, "vv2": 0x43B4D0, "vv3": 0x45BF00, "vv4": 0x465750, "vv5": 0x46E8E0}
        for game, va in entries.items():
            with self.subTest(game=game):
                m = world(game)
                self.assertEqual(m.mu.mem_read(va, 1)[0], 0xE9)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class LowFoodFarmingWins(unittest.TestCase):
    """Decision 3: at 250 food or less with Farming 20+, the worker's Farming
    dispatch is all that runs, with the roll forced to pass."""

    def test_farming_still_wins(self):
        for game in LATER:
            g = G[game]
            for who, own in _own_jobs(game):
                for pick in (_other(game, own), own):
                    with self.subTest(game=game, who=who, pick=pick):
                        m = decide(world(game, selected=own, pick=pick, food=250, farming=20))
                        self.assertEqual(m.asked, [(g["farm_ret"], FARMING)])
                        self.assertEqual(m.draws("fix_huts"), 0)
                        stock = decide(world(game, rows=(), runtime=False, selected=own, pick=pick,
                                             food=250, farming=20))
                        self.assertEqual(effects(m), effects(stock))

    def test_the_net_is_the_only_reason(self):
        for game in LATER:
            g = G[game]
            with self.subTest(game=game):
                m = decide(world(game, selected=g["healing"], pick=g["building"], food=251, farming=20))
                self.assertEqual(jobs(m), [g["healing"]])
                m = decide(world(game, selected=g["healing"], pick=g["building"], food=250, farming=19))
                self.assertEqual(jobs(m), [g["healing"]])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class UntouchedCases(unittest.TestCase):
    """Parenting, no selected job, a pick that already is the own job, a
    researcher picked for Farming, and a builder who would start a project
    nobody was dropped on are the stock worker (no fallback started)."""

    def _same_as_stock(self, game, **kw):
        kw.setdefault("rolls", Rolls(default=lambda n: 0))
        m = decide(world(game, **kw))
        stock = decide(world(game, rows=(), runtime=False, **kw))
        self.assertEqual(effects(m), effects(stock))
        return m

    def test_parenting_and_no_job_are_never_put_first(self):
        for game in GAMES:
            g = G[game]
            none = 0 if game in ("vv1", "vv2") else -1
            for selected in (g["parenting"], none):
                for pick in (g["healing"], g["building"], g["farming"]):
                    with self.subTest(game=game, selected=selected, pick=pick):
                        self._same_as_stock(game, selected=selected, pick=pick)

    def test_research_never_displaces_farming(self):
        for game in GAMES:
            g = G[game]
            with self.subTest(game=game):
                m = self._same_as_stock(game, selected=g["research"], pick=g["farming"])
                self.assertEqual(jobs(m), [g["farming"]])

    def test_the_pick_already_the_own_job(self):
        for game in GAMES:
            for who, own in _own_jobs(game):
                with self.subTest(game=game, who=who):
                    m = decide(world(game, selected=own, pick=own))
                    self.assertEqual(jobs(m), [own])
                    # A job with a fallback (A New Home's and The Lost Children's Healing) is dispatched
                    # by the companion so its fallback can follow; every other one is the stock call.
                    fallback = G[game]["healing"] if game in ("vv1", "vv2") else None
                    self.assertEqual(m.asked[0][0] == G[game]["pick_ret"], own != fallback)

    def test_a_builder_without_hut_work(self):
        for game in ("vv1", "vv2"):
            g = G[game]
            with self.subTest(game=game):
                self._same_as_stock(game, selected=g["building"], pick=g["healing"], huts_done=True)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class BuildersNeverStartAnUndroppedProject(unittest.TestCase):
    """Decision 4: the owner's rule -- builders never START a project nobody
    was dropped on; they may continue one in progress."""

    def test_the_tree_of_life_puzzle_work(self):
        g = G["vv4"]
        cases = [
            (dict(), True),                                     # no puzzle work on offer
            (dict(stream=50), False),                           # the stream before The Stream
            (dict(stream=50, stream_solved=True), True),        # keeping it clear once cleared (item 73)
            (dict(stream=0x62), True),                          # not offered
            (dict(piers_stage=1), False),                       # the piers before Fishing Nets
            (dict(rubble_stage=0), False),                      # the rubble before the Cooking Pit
        ]
        for kw, first in cases:
            with self.subTest(**kw):
                m = decide(world("vv4", selected=g["building"], pick=g["healing"], **kw))
                self.assertEqual(jobs(m)[0] == g["building"], first)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class Fallbacks(unittest.TestCase):
    """Decision 5."""

    def test_exercise_stays_stock(self):
        # The owner (2026-11-18): "Villagers' exercising frequency should stay stock".  A builder whose Building
        # work starts nothing is never sent to "Doing exercise"; the decision is the stock worker's.
        for game in LATER:
            g = G[game]
            for pick in (g["healing"], g["building"]):
                with self.subTest(game=game, pick=pick):
                    kw = dict(selected=g["building"], pick=pick, starts=lambda j, b=g["building"]: j != b,
                              rolls=Rolls(default=lambda n: 0))
                    m = decide(world(game, **kw))
                    self.assertEqual([c for c in m.calls if c[0] == "do-action"], [])
                    if pick == g["building"]:
                        stock = decide(world(game, rows=(), runtime=False, **kw))
                        self.assertEqual(effects(m), effects(stock))

    def _studied(self, m):
        return [c[0] for c in m.calls if c[0].startswith("herb ") or c[0] == "magic plant"]

    def test_healers_study_once_herb_mastery_is_solved(self):
        for game, herbs in (("vv1", VV1_HERBS), ("vv2", VV2_HERBS)):
            g = G[game]
            for k in range(len(herbs)):
                with self.subTest(game=game, herb=k):
                    m = decide(world(game, selected=g["healing"], pick=g["building"], herb_mastery=True,
                                     herbs=(k,), starts=lambda j, h=g["healing"]: j != h))
                    self.assertEqual(self._studied(m), [f"herb {k}"])
                    self.assertEqual(jobs(m), [g["healing"]])           # started: the pick is not run

    def test_a_healer_already_given_healing_studies_too(self):
        # Codex on #807: the picker's usual answer for a healer is Healing itself.
        for game, herbs in (("vv1", VV1_HERBS), ("vv2", VV2_HERBS)):
            g = G[game]
            with self.subTest(game=game):
                m = decide(world(game, selected=g["healing"], pick=g["healing"], herb_mastery=True, herbs=(0,),
                                 starts=lambda j, h=g["healing"]: j != h))
                self.assertEqual(self._studied(m), ["herb 0"])
                self.assertEqual(jobs(m), [g["healing"]], "the request ran once")
                m = decide(world(game, selected=g["healing"], pick=g["healing"], herb_mastery=True, herbs=(0,),
                                 force=FORCE_FAIL, starts=lambda j, h=g["healing"]: j != h))
                self.assertEqual(self._studied(m), [])
                self.assertEqual(m.asked, [(g["pick_ret"], g["healing"])])

    def test_no_study_before_herb_mastery_or_for_others(self):
        for game, herbs in (("vv1", VV1_HERBS), ("vv2", VV2_HERBS)):
            g = G[game]
            every = tuple(range(len(herbs)))
            cases = [
                ("unsolved", dict(selected=g["healing"], herb_mastery=False, herbs=every)),
                ("healing started", dict(selected=g["healing"], herb_mastery=True, herbs=every,
                                         starts=lambda j: True)),
                ("roll failed", dict(selected=g["healing"], herb_mastery=True, herbs=every, force=FORCE_FAIL)),
                ("not a healer", dict(selected=g["research"], herb_mastery=True, herbs=every)),
            ]
            for case, kw in cases:
                with self.subTest(game=game, case=case):
                    kw.setdefault("starts", lambda j, h=g["healing"]: j != h)
                    m = decide(world(game, pick=g["building"], **kw))
                    self.assertEqual(self._studied(m), [])

    def test_the_drop_refusal_trait_is_honoured(self):
        # A New Home: a villager with trait 0xB runs away from the rose, lily
        # and strange plant but not the cactus; The Lost Children: from all.
        for game, expected in (("vv1", ["herb 0"]), ("vv2", [])):
            g = G[game]
            with self.subTest(game=game):
                m = decide(world(game, selected=g["healing"], pick=g["building"], herb_mastery=True,
                                 herbs=tuple(range(len(VV1_HERBS if game == "vv1" else VV2_HERBS))),
                                 trait=True, starts=lambda j, h=g["healing"]: j != h))
                self.assertEqual(self._studied(m), expected)

    def test_never_the_magic_plant_of_life(self):
        g = G["vv1"]
        for seed in range(8):
            m = world("vv1", selected=g["healing"], pick=g["building"], herb_mastery=True, herbs=(0, 1, 2, 3),
                      starts=lambda j: j != g["healing"])
            m.mu.mem_write(m.exports["work_first"]["VvfpWorkFirstStats"] + 12, struct.pack("<i", seed))
            decide(m)
            self.assertNotIn("magic plant", names(m))
            self.assertEqual(len(self._studied(m)), 1)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class Untrained(unittest.TestCase):
    """Decision 6: the untrained mark (record+0x1C54 = 1; The Tree of Life
    and New Believers) is lifted for one dispatch of the selected job (never
    Parenting, skill above 5) and put back."""

    def test_the_selected_job_is_dispatched_trained_and_the_mark_put_back(self):
        for game in ("vv4", "vv5"):
            g = G[game]
            for own in (g["farming"], g["healing"], g["building"]):
                for pick in (own, g["research"]):
                    with self.subTest(game=game, selected=own, pick=pick):
                        m = decide(world(game, selected=own, pick=pick, task=1))
                        self.assertEqual(jobs(m)[0], own)
                        self.assertEqual(m.marks[0], 0, "lifted for the dispatch")
                        self.assertEqual(m.u32(RECORD + 0x1C54), 1, "put back")

    def test_not_at_skill_5_or_less(self):
        for game in ("vv4", "vv5"):
            g = G[game]
            with self.subTest(game=game):
                m = decide(world(game, selected=g["healing"], pick=g["healing"], task=1, skill=5))
                self.assertEqual(m.marks, [1])

    def test_any_other_request_still_sees_the_mark(self):
        g = G["vv5"]
        m = decide(world("vv5", selected=g["healing"], pick=g["building"], task=1, force=FORCE_FAIL))
        self.assertEqual(m.marks, [1])
        m = decide(world("vv5", selected=g["parenting"], pick=g["building"], task=1))
        self.assertEqual(m.marks, [1])

    def test_heathens_get_nothing_new(self):
        # A Heathen (u8 record+0x1CEC) never gets job work in the game: no own job first, no lifted mark.
        g = G["vv5"]
        for task in (0, 1):
            with self.subTest(task=task):
                m = world("vv5", selected=g["healing"], pick=g["building"], task=task)
                m.w8(RECORD + 0x1CEC, 1)
                decide(m)
                self.assertEqual(m.asked, [(g["pick_ret"], g["building"])])
                self.assertEqual(m.marks, [task])
                m = world("vv5", selected=g["healing"], pick=g["healing"], task=1)
                m.w8(RECORD + 0x1CEC, 1)
                decide(m)
                self.assertEqual(m.marks, [1])

    def test_a_trained_villager_is_unchanged(self):
        g = G["vv5"]
        m = decide(world("vv5", selected=g["healing"], pick=g["healing"], task=0))
        self.assertEqual(m.marks, [0])
        self.assertEqual(m.asked, [(g["pick_ret"], g["healing"])])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class OnlyAboveSkill5(unittest.TestCase):
    """Decision 7: at skill 5 or less in their job, nobody is put first -- the
    decision is the stock worker's."""

    def test_skill_5_or_less_is_never_put_first(self):
        for game in GAMES:
            for who, own in _own_jobs(game):
                other = _other(game, own)
                for skill in (0, 5):
                    with self.subTest(game=game, who=who, skill=skill):
                        kw = dict(selected=own, pick=other, skill=skill, rolls=Rolls(default=lambda n: 0))
                        if game == "vv3" and own == G[game]["farming"]:
                            kw["farming"] = skill
                        m = decide(world(game, **kw))
                        self.assertNotEqual(jobs(m)[:1], [own])
                        self.assertEqual(effects(m), effects(decide(world(game, rows=(), runtime=False, **kw))))

    def test_skill_6_is(self):
        for game in GAMES:
            g = G[game]
            with self.subTest(game=game):
                m = decide(world(game, selected=g["healing"], pick=g["building"], skill=6))
                self.assertEqual(jobs(m)[:1], [g["healing"]])

    def test_no_herb_study_at_skill_5_or_less(self):
        for game in ("vv1", "vv2"):
            g = G[game]
            with self.subTest(game=game):
                m = decide(world(game, selected=g["healing"], pick=g["healing"], skill=5, herb_mastery=True,
                                 herbs=(0,), starts=lambda j, h=g["healing"]: j != h))
                self.assertEqual([c for c in m.calls if c[0].startswith("herb ")], [])


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
                for who, own in (("healer", g["healing"]), ("farmer", g["farming"])):
                    with self.subTest(mode=mode, game=game, who=who):
                        m = decide(world(game, exe=exe, selected=own, pick=_other(game, own)))
                        self.assertEqual(jobs(m), [own])
                if game in LATER:
                    with self.subTest(mode=mode, game=game, farming=True):
                        m = decide(world(game, exe=exe, selected=g["healing"], pick=g["building"],
                                         food=250, farming=20))
                        self.assertEqual(m.asked, [(g["farm_ret"], FARMING)])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class LostChildrenHealersStudyInCatchUp(unittest.TestCase):
    """Decision 7: a villager in plant-study state 9 gets the continuation
    0x460590(index, 40) in catch-up, after the task-state step and before the
    pick, on the decision's roll."""

    def _continues(self, m):
        return [c for c in m.calls if c[0] == "continue"]

    def test_state_nine_continues_plant_study(self):
        # The worker reads no food total: this holds at any food level.
        m = decide(world("vv2", selected=2, pick=1, task=9, cont=1))
        self.assertEqual([c[1] for c in self._continues(m)], [(INDEX, 40)])
        self.assertEqual(m.asked, [])                     # started: no dispatch
        found = names(m)
        self.assertLess(found.index("task state"), found.index("continue"))
        self.assertIn("processor", found)

    def test_nothing_to_study_dispatches_the_pick_as_the_stock_call(self):
        m = decide(world("vv2", selected=2, pick=1, task=9, cont=0))
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
                kw = dict(selected=2, pick=1, cont=1, rolls=Rolls(default=lambda n: 0))
                kw.update(case)
                force = kw.pop("force", FORCE_PASS)
                m = decide(world("vv2", force=force, **kw))
                stock = decide(world("vv2", rows=(), runtime=False, **kw))
                self.assertEqual(effects(m), effects(stock))
                self.assertEqual(self._continues(m), [])

    def test_the_share_is_about_one_in_two(self):
        # A villager checked on Healing: half the time.  Anyone else (here
        # checked on Parenting): 14% of that (the owner, 2026-10-20).
        for selected, low, high in ((G["vv2"]["healing"], 0.45, 0.55), (2, 0.045, 0.10)):
            with self.subTest(selected=selected):
                m = world("vv2", selected=selected, pick=1, task=9, cont=1, force=FORCE_REAL)
                m.seed(SEED)
                n, hits = 1500, 0
                for _ in range(n):
                    decide(m)
                    hits += bool(self._continues(m))
                share = hits / n
                print(f"catch-up share vv2 plant study, checkmark {selected}: {share:.3f}")
                self.assertGreater(share, low)
                self.assertLess(share, high)

    def test_a_new_home_has_the_same_site(self):
        # A New Home's dispatcher continues plant study (0x4478EF, activity 9
        # -> 0x443270) only when catch-up picks Healing and no one is sick,
        # so it gets the same catch-up site at its pick dispatch (0x42E817);
        # tests/test_easier_healing_mastery.py runs it.
        self.assertEqual(_stock_bytes_at("vv1", 0x42E817, 10).hex().upper(), "8B4F045056E89F8A0100")
        m = world("vv1")
        code = bytes(m.mu.mem_read(0x42E817, 10))
        self.assertEqual(code[0], 0xE9)
        target = (0x42E817 + 5 + struct.unpack("<i", code[1:5])[0]) & 0xFFFFFFFF
        self.assertTrue(0x12000000 <= target < 0x13000000)  # into "VVFP Healers Study.dll"


if __name__ == "__main__":
    unittest.main()
