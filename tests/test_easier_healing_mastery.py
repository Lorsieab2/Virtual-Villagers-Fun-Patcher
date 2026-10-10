"""Easier Healing Mastery: a healer with no one to treat studies, in live play
and in catch-up -- A New Home (new row) and The Lost Children (existing row).

The owner (2026-10-10): doctors in A New Home stuck at Trainee/Adept on Time
Warp.  Stock A New Home studies the Medical Cactus from the work dispatcher's
Healing case (0x447894) only for a villager in plant-study state 9, which only
the player's drop sets: with no one sick, every other healer the dispatcher is
asked to put to work does nothing (0x4478EF cmp [rec+0x3B8],9; jne).  The
Lost Children's Healing case does nothing at all with no one sick (0x4604AD).

Easier Healing Mastery is where "every healer with no patient studies" lives:
- The Lost Children (existing row): its cave sets state 9 and calls the
  task-state continuation 0x460590(index, 100), whose case 9 studies a plant.
- A New Home (new row): the no-patient exit itself (0x4478E7..0x447900) calls
  the stock study 0x443270(index) -- what the stock code does for state 9 --
  for any villager, writes no record field, and returns al=1 ("started") so
  the live scheduler does not go on to queue something else too.
Both act through the dispatcher, which live play and the catch-up worker
share, so both act in both.

Everything is EMULATED: the catch-up worker from its entry (A New Home
0x42E790, The Lost Children 0x43B4D0) and the WHOLE work dispatcher run as
machine code in the executable the patcher renders; only leaf routines (the
picker, the RNG, the queue processor, the study routines, the task-state
step) are scripted.  Any call into the executable that is not scripted stops
the run.  Then the same with every healer patch ticked (Builders Fix Huts When
Idle, Builders and Healers Work First, Healers Study Plants Regardless of
Food), their test builds installed as the per-frame companions install them,
to show the patches work together and queue one thing per decision.
"""
from __future__ import annotations

import struct
import unittest

from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX

from test_builders_decision_roll import (
    FORCE_FAIL, FORCE_PASS, FORCE_REAL, HALT, INDEX, ROWS, STATE, STOCK, STOCK_ABSENT, STOCK_PRESENT,
    TEST_BUILD_ABSENT, TEST_BUILDS_PRESENT, VILLAGE, Leaf, Machine, Rolls,
)

EHM = {"vv1": "vv1_easier_healing_mastery", "vv2": "vv2_easier_healing_mastery"}
MODES = ("stock", "collection_progression", "immediate_fixed")
HEALING = {"vv1": 5, "vv2": 3}
WORKER = {"vv1": 0x42E790, "vv2": 0x43B4D0}
DISPATCHER = {"vv1": 0x4472C0, "vv2": 0x45FBF0}
CU_RET = {"vv1": 0x42E821, "vv2": 0x43B588}          # the worker's pick dispatch returns here
LIVE_RETS = {"vv1": (0x448355, 0x448382), "vv2": (0x461A08, 0x461A35)}
STATE_FIELD = {"vv1": 0x3B8, "vv2": 0x7E0}
STRIDE = {"vv1": 0x3D8, "vv2": 0xE48C}
VV1_STUDY = 0x443270
VV2_PLANTS = {0x458CD0: "plant 0", 0x4589A0: "plant 1", 0x458FD0: "plant 2", 0x459130: "plant 3"}
STUDIES = {"study cactus", *VV2_PLANTS.values()}
OTHER = 1                                               # a job that is neither Healing nor research

_RENDERED: dict = {}


def render(game: str, rows: tuple[str, ...], mode: str = "stock") -> bytes:
    key = (game, rows, mode)
    if key not in _RENDERED:
        if not rows:
            _RENDERED[key] = STOCK[game].read_bytes()
        else:
            import vv_fun_patcher as vfp
            build = next(b for b in vfp.load_builds() if b.id == game)
            data, _ = vfp.render_patched_bytes(STOCK[game], build, mode, list(rows))
            _RENDERED[key] = bytes(data)
    return _RENDERED[key]


def machine(game, *, rows, runtime=False, force=FORCE_PASS, pick=None, selected=None, task=0, healing=5,
            mode="stock", cont=None, rolls=None) -> Machine:
    """One adult at INDEX, no one sick, ready to run `game`'s catch-up worker
    with the real dispatcher.  cont: script the scheduler's continuation
    (A New Home 0x447CD0) to return this; None leaves The Lost Children's
    0x460590 real."""
    pick = HEALING[game] if pick is None else pick
    selected = HEALING[game] if selected is None else selected
    modules = ("fix_huts", "work_first", "healers") if runtime else ()
    m = Machine(game, render(game, tuple(rows), mode), modules=modules)
    m.real.add(DISPATCHER[game])
    rolls = rolls or Rolls()
    rec = VILLAGE + INDEX * STRIDE[game]
    obj = 0x38000000
    m.w32(obj + 4, VILLAGE)
    if game == "vv1":
        m.w32(VILLAGE + 0x3E010, STATE)
        m.w32(rec + 0x348, 0x200)                     # an adult
        m.w32(rec + 0x344, 100)
        m.w32(rec + 0x3C8, healing)
        m.w32(rec + 0x3D0, selected)
        m.w32(STATE + 0xA2CC, 3)
        m.leaves.update({
            0x439470: Leaf(1, lambda m, a, c, r: 0, name="prepare"),
            0x439AE0: Leaf(2, lambda m, a, c, r: pick, name="picker"),
            0x402F10: Leaf(1, rolls, cdecl=True, name="rand"),
            0x4399F0: Leaf(7, lambda m, a, c, r: 1, name="research step"),
            0x446C70: Leaf(1, lambda m, a, c, r: 0, name="processor"),
            VV1_STUDY: Leaf(1, lambda m, a, c, r: 0, name="study cactus"),
        })
        if cont is not None:
            m.leaves[0x447CD0] = Leaf(2, lambda m, a, c, r: cont, name="continue")
    else:
        m.w32(VILLAGE + 0xE574D4, STATE)
        m.w32(rec + 0x530, 0x200)
        m.w32(rec + 0x52C, 100)
        m.w32(rec + 0x7F0, healing)
        m.w32(rec + 0x7F8, selected)
        m.w32(STATE + 0x2EA84, 3)
        for off in (0x2E860, 0x2E868, 0x2E880, 0x2E888):  # the four plants are there
            m.w8(STATE + off, 1)
        m.leaves.update({
            0x4492A0: Leaf(1, lambda m, a, c, r: 0, name="prepare"),
            0x449C60: Leaf(2, lambda m, a, c, r: pick, name="picker"),
            0x4031A0: Leaf(1, rolls, cdecl=True, name="rand"),
            0x449B70: Leaf(7, lambda m, a, c, r: 1, name="research step"),
            0x461580: Leaf(1, lambda m, a, c, r: 0, name="task state"),
            0x464680: Leaf(1, lambda m, a, c, r: 0, name="processor"),
        })
        for va, name in VV2_PLANTS.items():
            m.leaves[va] = Leaf(1, lambda m, a, c, r: 1, name=name)
        if cont is None:
            m.real.add(0x460590)
            m.real_ranges.append((0x473CA0, 0x473CC4))   # Easier Healing Mastery's cave
        else:
            m.leaves[0x460590] = Leaf(2, lambda m, a, c, r: cont, name="continue")
            m.real_ranges.append((0x473CA0, 0x473CC4))
    m.w32(rec + STATE_FIELD[game], task)
    m.plan(WORKER[game], HALT, {UC_X86_REG_ECX: obj}, stack=(HALT, INDEX))
    if runtime:
        m.install_runtime()
        m.roll_force(force)
    return m


def names(m: Machine) -> list[str]:
    return [c[0] for c in m.calls if c[0] not in ("GetModuleHandleA", "LoadLibraryA", "LoadLibraryExW",
                                                  "GetFileAttributesW", "GetProcAddress", "done")]


def studies(m: Machine) -> list[tuple]:
    return [c for c in m.calls if c[0] in STUDIES]


def state(m: Machine, game: str) -> int:
    return m.u32(VILLAGE + INDEX * STRIDE[game] + STATE_FIELD[game])


def live(m: Machine, game: str, ret: int) -> int:
    """The live scheduler's dispatcher call (return address `ret`) with the
    Healing job; returns al."""
    m.calls = []
    m.run(DISPATCHER[game], ret, {UC_X86_REG_ECX: VILLAGE}, stack=(ret, INDEX, HEALING[game]))
    return m.mu.reg_read(UC_X86_REG_EAX) & 0xFF


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class StockGap(unittest.TestCase):
    """What the owner saw: with no one sick, a healer whom catch-up gives the
    Healing job studies only in A New Home, and only in state 9."""

    def test_a_new_home_studies_only_in_state_nine(self):
        m = machine("vv1", rows=()).decide()
        self.assertEqual(studies(m), [])
        self.assertEqual(names(m), ["prepare", "picker", "processor"])
        m = machine("vv1", rows=(), task=9).decide()
        self.assertEqual(studies(m), [("study cactus", (INDEX,), VILLAGE)])

    def test_the_lost_children_never_studies(self):
        for task in (0, 9):
            with self.subTest(task=task):
                m = machine("vv2", rows=(), task=task).decide()
                self.assertEqual(studies(m), [])

    def test_the_stock_exit_the_new_row_replaces(self):
        data = STOCK["vv1"].read_bytes()
        self.assertEqual(data[0x478E7:0x47901].hex().upper(),
                         "8BC569C0D803000083BC30B8030000097508558BCEE86FB9FFFF")
        self.assertEqual(data[0x47901:0x47908].hex().upper(), "5F5D5B32C05EC2")   # 0x447901 stays


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class EasierHealingMasteryAlone(unittest.TestCase):
    """The row alone, every population mode, from the worker's entry and from
    the live scheduler's two dispatcher calls."""

    def test_catch_up_healer_with_no_patient_studies(self):
        for mode in MODES:
            for game in ("vv1", "vv2"):
                for task in (0, 9):
                    with self.subTest(mode=mode, game=game, task=task):
                        m = machine(game, rows=(EHM[game],), mode=mode, task=task).decide()
                        got = studies(m)
                        self.assertEqual(len(got), 1, names(m))
                        self.assertEqual(got[0][1], (INDEX,))
                        self.assertEqual(names(m)[-1], "processor")

    def test_record_fields(self):
        # A New Home writes no record field; The Lost Children's row (as it
        # always has) puts the villager in plant-study state 9.
        m = machine("vv1", rows=(EHM["vv1"],), task=0).decide()
        self.assertEqual(state(m, "vv1"), 0)
        m = machine("vv2", rows=(EHM["vv2"],), task=0).decide()
        self.assertEqual(state(m, "vv2"), 9)

    def test_live_play_studies_and_reports_started(self):
        for game in ("vv1", "vv2"):
            for ret in LIVE_RETS[game]:
                with self.subTest(game=game, ret=hex(ret)):
                    m = machine(game, rows=(EHM[game],))
                    self.assertEqual(live(m, game, ret), 1)      # the scheduler stops: nothing else queued
                    self.assertEqual(len(studies(m)), 1)
                    stock = machine(game, rows=())
                    self.assertEqual(live(stock, game, ret), 0)
                    self.assertEqual(studies(stock), [])

    def test_other_jobs_are_untouched(self):
        for game, picks in (("vv1", (OTHER, 4)), ("vv2", (OTHER,))):
            for pick in picks:
                with self.subTest(game=game, pick=pick):
                    kw = dict(pick=pick, rolls=Rolls(default=lambda n: 0))
                    m = machine(game, rows=(EHM[game],), **kw).decide()
                    stock = machine(game, rows=(), **kw).decide()
                    self.assertEqual(m.calls, stock.calls)
                    self.assertEqual(studies(m), [])

    def test_the_lost_children_healing_gate_is_the_games(self):
        # Case 9 of 0x460590 studies only with Healing 1 or more (or the
        # village flag clear); otherwise it falls to the game's idle choice
        # (0x460961 -> 0x44FE10 here): unchanged by the row.
        m = machine("vv2", rows=(EHM["vv2"],), healing=0)
        m.w32(STATE + 0x2EAEC, 1)
        m.leaves[0x44FE10] = Leaf(1, lambda m, a, c, r: 1, name="idle")
        m.decide()
        self.assertEqual(studies(m), [])
        self.assertIn("idle", names(m))


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class WithEveryHealerPatch(unittest.TestCase):
    """Easier Healing Mastery with Builders Fix Huts When Idle, Builders and
    Healers Work First and Healers Study Plants Regardless of Food: each still
    does its own job, and a decision queues one thing."""

    def rows(self, game):
        return tuple(ROWS[game]) + (EHM[game],)

    def test_work_first_puts_a_healer_to_healing_and_the_healing_studies(self):
        for game in ("vv1", "vv2"):
            with self.subTest(game=game):
                m = machine(game, rows=self.rows(game), runtime=True, pick=OTHER).decide()
                self.assertEqual(len(studies(m)), 1, names(m))
                self.assertNotIn("research step", names(m))

    def test_a_studying_healer_continues_once(self):
        # State 9: Healers Study's catch-up site continues the study first;
        # when that starts it, nothing is dispatched.
        for game in ("vv1", "vv2"):
            with self.subTest(game=game):
                m = machine(game, rows=self.rows(game), runtime=True, pick=OTHER, task=9, cont=1).decide()
                conts = [c for c in m.calls if c[0] == "continue"]
                self.assertEqual(len(conts), 1)
                self.assertEqual(conts[0][1], (INDEX, 60 if game == "vv1" else 40))
                self.assertEqual(studies(m), [])               # the scripted continuation did it
                # ... and when the continuation starts nothing, Work First and
                # Easier Healing Mastery still give exactly one study.
                m = machine(game, rows=self.rows(game), runtime=True, pick=OTHER, task=9, cont=0).decide()
                if game == "vv1":
                    self.assertEqual(len(studies(m)), 1, names(m))
                else:
                    # The Lost Children's row studies through the (here
                    # scripted) continuation itself, with 100.
                    self.assertEqual([c[1] for c in m.calls if c[0] == "continue"], [(INDEX, 40), (INDEX, 100)])

    def test_roll_failed_is_easier_healing_mastery_alone(self):
        for game in ("vv1", "vv2"):
            with self.subTest(game=game):
                m = machine(game, rows=self.rows(game), runtime=True, force=FORCE_FAIL).decide()
                self.assertEqual(len(studies(m)), 1)
                alone = machine(game, rows=(EHM[game],)).decide()
                self.assertEqual(studies(m), studies(alone))


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class NewHomeHealersStudyCatchUp(unittest.TestCase):
    """Healers Study Plants Regardless of Food's new A New Home catch-up site
    (0x42E817): a villager in plant-study state 9 continues studying whatever
    catch-up picks, on the decision's 75% roll -- as The Lost Children's
    (0x43B581) always has.  Without Easier Healing Mastery."""

    def rows(self):
        return tuple(ROWS["vv1"])

    def test_the_site(self):
        self.assertEqual(STOCK["vv1"].read_bytes()[0x2E817:0x2E821].hex().upper(), "8B4F045056E89F8A0100")
        m = machine("vv1", rows=self.rows(), runtime=True)
        code = bytes(m.mu.mem_read(0x42E817, 10))
        self.assertEqual(code[0], 0xE9)
        target = (0x42E817 + 5 + struct.unpack("<i", code[1:5])[0]) & 0xFFFFFFFF
        self.assertTrue(0x12000000 <= target < 0x13000000)      # into "VVFP Healers Study.dll"
        self.assertEqual(code[5:], b"\x90" * 5)

    def test_state_nine_continues_whatever_the_pick(self):
        for pick in (OTHER, 4, 0):
            with self.subTest(pick=pick):
                m = machine("vv1", rows=self.rows(), runtime=True, pick=pick, selected=OTHER, task=9,
                            cont=1).decide()
                self.assertEqual([c[1] for c in m.calls if c[0] == "continue"], [(INDEX, 60)])
                self.assertEqual(names(m)[-1], "processor")
                self.assertNotIn("study cactus", names(m))

    def test_nothing_started_dispatches_the_pick_as_the_stock_call(self):
        # The pick is dispatched with the stock return address: Healing with
        # no patient and state 9 is then the stock study.
        m = machine("vv1", rows=self.rows(), runtime=True, task=9, cont=0, selected=OTHER).decide()
        self.assertEqual(len([c for c in m.calls if c[0] == "continue"]), 1)
        self.assertEqual(studies(m), [("study cactus", (INDEX,), VILLAGE)])

    def test_untouched_cases_are_the_stock_worker(self):
        for case in (dict(task=0), dict(task=8), dict(task=9, force=FORCE_FAIL), dict(task=9, pick=2)):
            with self.subTest(**case):
                kw = dict(pick=OTHER, selected=OTHER, cont=1, rolls=Rolls(default=lambda n: 0))
                kw.update(case)
                force = kw.pop("force", FORCE_PASS)
                m = machine("vv1", rows=self.rows(), runtime=True, force=force, **kw).decide()
                stock = machine("vv1", rows=(), **kw).decide()
                self.assertEqual(names(m), names(stock))
                self.assertEqual([c for c in m.calls if c[0] == "continue"], [])

    def test_the_share_is_about_three_in_four(self):
        m = machine("vv1", rows=self.rows(), runtime=True, force=FORCE_REAL, pick=OTHER, selected=OTHER,
                    task=9, cont=1)
        m.seed(0x9E3779B9)
        n, hits = 1000, 0
        for _ in range(n):
            draws = m.draws("fix_huts")
            m.decide()
            self.assertEqual(m.draws("fix_huts") - draws, 1, "one roll per decision")
            hits += any(c[0] == "continue" for c in m.calls)
        share = hits / n
        print(f"catch-up share vv1 plant study: {share:.3f}")
        self.assertGreater(share, 0.70)
        self.assertLess(share, 0.80)

    def test_every_population_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                m = machine("vv1", rows=self.rows(), runtime=True, mode=mode, pick=OTHER, selected=OTHER,
                            task=9, cont=1).decide()
                self.assertEqual([c[1] for c in m.calls if c[0] == "continue"], [(INDEX, 60)])


if __name__ == "__main__":
    unittest.main()
