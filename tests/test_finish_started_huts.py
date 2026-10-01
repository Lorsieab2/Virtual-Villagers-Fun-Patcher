"""Builders work on the second and third population hut only once the player
has started it, and then finish it whatever the population -- in live play
and in catch-up (A New Home, The Lost Children).

The owner: "Villagers will be capable of autonomously working on population
huts as soon as the scaffold appears. But they will not actually do it unless
the player has dropped someone on it first and it has a little bit of
progress. Once they have been enabled to work autonomously, they continue
construction even during catch-up."

The stock rule, read from the executables:

  A New Home  Building branch 0x447528: hut 9 whenever incomplete; hut 10 only
              with population > 22 (0x44754F), hut 11 only > 45 (0x447581) --
              progress never tested.  The village drawing routine shows hut
              10's scaffold at population >= 15 (0x414AE7) and hut 11's at
              >= 28 (0x414BCC), or whenever the hut has progress, and writes
              progress 1 when it first shows it (0x414B0C, 0x414BF1, ebx = 1).
              A worked hut gains 1 per work step (0x43A884).
  The Lost Children  0x4600DE: hut 25 only with population > 22 and progress
              >= 2, hut 26 only > 45 and progress >= 2.  The scaffold shows at
              >= 21 (0x4196ED) and >= 46 (0x419768), or with progress, and
              gets progress 1 (0x419702, 0x41977D).

The fix: hut 10/11 and hut 25/26 count as building work exactly while they
are not complete and their progress is 2 or more -- past the scaffold mark,
which only a villager's work does -- with no population test.  In the
executable for A New Home through Builder Action Fixes, and at run time
through the fix-huts companion in both games, whose build-first helpers make
the same judgement.

CATCH-UP: both games' catch-up step (A New Home 0x42E790, called five times
per villager from 0x42E900; The Lost Children 0x43B4D0, from 0x43BFDD..)
starts a villager's job by calling the same Building dispatcher (0x42E81C,
0x43B583) that the live scheduler calls, so the same new-hut test decides
there; CatchUpTests runs that step.

Every run is EMULATED FROM THE GAME'S OWN CODE with the harness of
tests/test_builders_decision_roll.py.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from test_builders_decision_roll import (
    FORCE_FAIL, FORCE_PASS, HALT, OBJ, ROWS, STOCK, STOCK_ABSENT, STOCK_PRESENT, TEST_BUILD_ABSENT,
    TEST_BUILDS_PRESENT, V1, V2, VILLAGE, INDEX, Leaf, Rolls, _low, effects, lost_children, new_home,
    v1_outcome, v2_outcome,
)
from unicorn.x86_const import UC_X86_REG_ECX

ROOT = Path(__file__).resolve().parents[1]
BAF = ("vv1_builder_action_fixes",)
GATE = {"vv1": 0x44754A, "vv2": 0x4600DE}


def _builds_row(row_id: str) -> dict:
    builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
    return next(f for f in builds["fun_patches"] if f["id"] == row_id)


def _stock(game: str, va: int, n: int) -> bytes:
    import pefile
    pe = pefile.PE(str(STOCK[game]), fast_load=True)
    return STOCK[game].read_bytes()[pe.get_offset_from_rva(va - 0x400000):][:n]


def _probe_gate(game_no: int):
    from test_builders_decision_roll import Machine
    m = Machine("vv1", STOCK["vv1"].read_bytes(), modules=("fix_huts",))
    buf = 0x0EF00000
    m.mu.mem_map(buf, 0x1000)
    n = m.call_export("fix_huts", "VvfpFixHutsProbeGate", game_no, buf, buf + 0x100, buf + 0x200)
    va = m.u32(buf)
    return va, bytes(m.mu.mem_read(buf + 0x100, n)), bytes(m.mu.mem_read(buf + 0x200, n))


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class TheStockRuleTests(unittest.TestCase):
    """The numbers and marks the fix relies on are the game's own."""

    def test_a_new_home(self):
        self.assertEqual(_stock("vv1", 0x44754A, 10), bytes.fromhex("E8415AFDFF83F8167E22"))
        self.assertEqual(_stock("vv1", 0x44757C, 10), bytes.fromhex("E80F5AFDFF83F82D7E4B"))
        self.assertEqual(_stock("vv1", 0x414AE2, 10), bytes.fromhex("E8A984000083F80F7D10"))
        self.assertEqual(_stock("vv1", 0x414BC7, 10), bytes.fromhex("E8C483000083F81C7D10"))
        self.assertEqual(_stock("vv1", 0x41491B, 5), bytes.fromhex("BB01000000"))
        self.assertEqual(_stock("vv1", 0x414B0C, 6), bytes.fromhex("8998EC9F0000"))
        self.assertEqual(_stock("vv1", 0x414BF1, 6), bytes.fromhex("8998F49F0000"))
        # A work step adds 1: mov ebx, [eax+0x9FEC]; inc ebx; ...; mov [eax+0x9FEC], ebx.
        self.assertEqual(_stock("vv1", 0x43A884, 7), bytes.fromhex("8B98EC9F000043"))
        # Catch-up: the step calls the Building dispatcher, five times per villager.
        self.assertEqual(_stock("vv1", 0x42E81C, 5), bytes.fromhex("E89F8A0100"))
        for va in (0x42F10A, 0x42F112, 0x42F11A, 0x42F122, 0x42F12A):
            self.assertEqual(_stock("vv1", va, 5)[0], 0xE8)

    def test_the_lost_children(self):
        self.assertEqual(_stock("vv2", 0x4600E3, 5), bytes.fromhex("83F8167E1A"))
        self.assertEqual(_stock("vv2", 0x4600F6, 6), bytes.fromhex("39A81CE80200"))
        self.assertEqual(_stock("vv2", 0x46010D, 5), bytes.fromhex("83F82D7E1A"))
        self.assertEqual(_stock("vv2", 0x4196E8, 10), bytes.fromhex("E873C1000083F8157C50"))
        self.assertEqual(_stock("vv2", 0x419763, 10), bytes.fromhex("E8F8C0000083F82E7C50"))
        self.assertEqual(_stock("vv2", 0x419702, 10), bytes.fromhex("C7801CE8020001000000"))
        self.assertEqual(_stock("vv2", 0x41977D, 10), bytes.fromhex("C78024E8020001000000"))
        self.assertEqual(_stock("vv2", 0x43B583, 5), bytes.fromhex("E868460200"))


@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class TheLiftedBytesTests(unittest.TestCase):
    def test_the_companion_writes_over_the_exact_stock_bytes(self):
        # A New Home: written at run time by the companion.
        va, stock, lifted = _probe_gate(1)
        self.assertEqual(va, GATE["vv1"])
        self.assertEqual(_stock("vv1", va, len(stock)), stock)
        manifest = json.loads((ROOT / "data" / "vv1_builders_fix_huts_feature.json").read_text("utf-8"))
        entry = next(d for d in manifest["runtime_detours"] if int(d["va"], 16) == va)
        self.assertEqual(bytes.fromhex(entry["stock_bytes"]), stock)
        self.assertEqual(manifest["patches"], [], "A New Home's row changes no executable byte")
        from test_builders_decision_roll import Machine
        for no in (2, 3, 4, 5):
            m = Machine("vv1", STOCK["vv1"].read_bytes(), modules=("fix_huts",))
            m.mu.mem_map(0x0EF00000, 0x1000)
            self.assertEqual(m.call_export("fix_huts", "VvfpFixHutsProbeGate", no, 0x0EF00000, 0x0EF00100,
                                           0x0EF00200), 0, "no such gate in the later games")

    def test_the_lost_children_row_writes_its_test_into_the_executable(self):
        # The Lost Children's companion is installed only once the village is
        # drawn, after a session's load-time catch-up, so the row writes it.
        manifest = json.loads((ROOT / "data" / "vv2_builders_fix_huts_feature.json").read_text("utf-8"))
        (record,) = manifest["patches"]
        self.assertEqual(int(record["offset"], 16) + 0x400000, GATE["vv2"])
        before, after = bytes.fromhex(record["before"]), bytes.fromhex(record["after"])
        self.assertEqual(_stock("vv2", GATE["vv2"], len(before)), before)
        self.assertNotIn(GATE["vv2"], [int(d["va"], 16) for d in manifest["runtime_detours"]])
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv2")
        rendered, _ = vfp.render_patched_bytes(STOCK["vv2"], build, "stock", list(ROWS["vv2"]))
        self.assertEqual(bytes(rendered[0x600DE:0x600DE + len(after)]), after)

    def test_builder_action_fixes_writes_the_companions_bytes(self):
        va, stock, lifted = _probe_gate(1)
        row = next(p for p in _builds_row("vv1_builder_action_fixes")["patches"] if p["offset"] == "0x4754A")
        self.assertEqual(bytes.fromhex(row["before"]), stock)
        self.assertEqual(bytes.fromhex(row["after"]), lifted, "one change, written by either patch")
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv1")
        rendered, _ = vfp.render_patched_bytes(STOCK["vv1"], build, "stock", list(BAF))
        self.assertEqual(bytes(rendered[0x4754A:0x4754A + len(lifted)]), lifted)
        stock_exe = STOCK["vv1"].read_bytes()
        self.assertEqual(bytes(rendered[0x47528:0x4754A]), stock_exe[0x47528:0x4754A])
        self.assertEqual(bytes(rendered[0x47594:0x475A8]), stock_exe[0x47594:0x475A8])


def _vv1(config: str, **kw):
    if config == "stock":
        return new_home(rows=(), runtime=False, **kw)
    if config == "baf":
        return new_home(rows=BAF, runtime=False, **kw)
    return new_home(rows=ROWS["vv1"], force=FORCE_PASS if config.endswith("passes") else FORCE_FAIL, **kw)


def _vv2(config: str, **kw):
    if config == "stock":
        return lost_children(rows=(), runtime=False, **kw)
    return lost_children(rows=ROWS["vv2"], force=FORCE_PASS if config.endswith("passes") else FORCE_FAIL, **kw)


V1_PATCHED = ("baf", "fix huts, roll passes", "fix huts, roll fails")
V2_PATCHED = ("fix huts, roll passes", "fix huts, roll fails")


def _label(kw):
    return {k: str(v) for k, v in kw.items()}


@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class NewHomeFromTheRealCallerTests(unittest.TestCase):
    """A builder, Building level 3 or 2, food 100, hut 9 built; the game's
    rand answers high, so the stock branch walks into its new-hut section."""

    def _built(self, m) -> list:
        return [o for o in v1_outcome(m) if o[0] == "build hut"]

    def test_the_owners_village_a_started_hut_below_its_number_is_built(self):
        for level in (3, 2):
            kw = dict(level=level, huts=(1, 0, 0), projects={10: (12, 0)}, population=17)
            self.assertEqual(self._built(_vv1("stock", **kw)), [], "the stock game abandons it")
            for config in V1_PATCHED:
                with self.subTest(level=level, config=config):
                    self.assertEqual(self._built(_vv1(config, **kw)), [("build hut", 10)])

    def test_a_player_started_hut_is_built_at_any_population(self):
        for kw, hut in ((dict(huts=(1, 0, 0), projects={10: (2, 0)}, population=0), 10),
                        (dict(huts=(1, 0, 0), projects={10: (2, 0)}, population=60), 10),
                        (dict(huts=(1, 1, 0), projects={11: (2, 0)}, population=5), 11),
                        (dict(huts=(1, 1, 0), projects={11: (40, 0)}, population=30), 11),
                        (dict(huts=(1, 1, 0), projects={11: (40, 0)}, population=60), 11)):
            for config in V1_PATCHED:
                with self.subTest(config=config, **_label(kw)):
                    self.assertEqual(self._built(_vv1(config, **kw)), [("build hut", hut)])

    def test_an_untouched_hut_is_never_started_even_above_the_old_numbers(self):
        # Progress 0, or the drawing routine's scaffold mark 1.  Above 22/45
        # the stock game starts it; the patches never do.
        for progress in (0, 1):
            for hut, huts, population in ((10, (1, 0, 0), 23), (10, (1, 0, 0), 60), (11, (1, 1, 0), 46),
                                          (10, (1, 0, 0), 15), (11, (1, 1, 0), 30)):
                kw = dict(huts=huts, projects={hut: (progress, 0)}, population=population)
                stock = self._built(_vv1("stock", **kw))
                self.assertEqual(stock, [("build hut", hut)] if population > (22 if hut == 10 else 45) else [])
                for config in V1_PATCHED:
                    with self.subTest(config=config, **_label(kw)):
                        self.assertEqual(self._built(_vv1(config, **kw)), [])

    def test_below_the_old_numbers_an_untouched_hut_is_exactly_stock(self):
        for kw in (dict(huts=(1, 0, 0), population=14), dict(huts=(1, 0, 0), projects={10: (1, 0)}, population=20),
                   dict(huts=(1, 1, 0), projects={11: (1, 0)}, population=40)):
            with self.subTest(**_label(kw)):
                stock = _vv1("stock", **kw)
                for config in ("baf", "fix huts, roll fails"):
                    self.assertEqual(effects(_vv1(config, **kw)), effects(stock), config)
                passed = _vv1("fix huts, roll passes", **kw)
                self.assertEqual(self._built(passed), [])
                self.assertTrue([o for o in v1_outcome(passed) if o[0] == "examine"], v1_outcome(passed))

    def test_hut_9_and_a_complete_hut_are_unchanged(self):
        for kw in (dict(huts=(0, 0, 0), population=3), dict(huts=(1, 1, 0), projects={10: (400, 1)}, population=10)):
            with self.subTest(**_label(kw)):
                stock = _vv1("stock", **kw)
                for config in ("baf", "fix huts, roll fails"):
                    self.assertEqual(effects(_vv1(config, **kw)), effects(stock), config)
                self.assertEqual([o for o in v1_outcome(_vv1("fix huts, roll passes", **kw)) if o[0] == "build hut"],
                                 [o for o in v1_outcome(stock) if o[0] == "build hut"])

    def test_option_a_builds_a_started_hut_the_stock_roll_skipped(self):
        for level, site in ((3, V1["hut_site"]), (2, V1["level_site"])):
            with self.subTest(level=level):
                kw = dict(level=level, huts=(1, 0, 0), projects={10: (12, 0)}, population=17)
                rolls = lambda: Rolls({V1["gate_roll"]: 99, V1["first_roll"]: 0}, default=lambda n: 0)
                passed = _vv1("fix huts, roll passes", rolls=rolls(), **kw)
                self.assertEqual(v1_outcome(passed), [("build hut", 10)])
                self.assertIn(site, passed.seen)
                failed, stock = _vv1("fix huts, roll fails", rolls=rolls(), **kw), _vv1("stock", rolls=rolls(), **kw)
                self.assertEqual(effects(failed), effects(stock))
                kw["projects"] = {10: (1, 0)}
                kw["population"] = 40
                self.assertEqual(v1_outcome(_vv1("fix huts, roll passes", rolls=rolls(), **kw)), [("examine", 9)],
                                 "the untouched scaffold is not construction: a fix")

    def test_the_new_hut_test_runs_in_the_live_dispatcher(self):
        for config in V1_PATCHED:
            with self.subTest(config=config):
                m = _vv1(config, huts=(1, 0, 0), projects={10: (12, 0)}, population=17)
                self.assertIn(V1["disp"], m.seen)
                self.assertEqual(bytes(m.mu.mem_read(GATE["vv1"], 8)), bytes.fromhex("3899F09F0000742B"))


@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class LostChildrenFromTheRealCallerTests(unittest.TestCase):
    def _built(self, m) -> list:
        return [o for o in v2_outcome(m) if o[0] == "build"]

    def test_a_player_started_hut_is_built_at_any_population(self):
        for level in (3, 1):
            for huts, hut, population in ((((24, 1), (12, 0), (0, 0)), 25, 17), (((24, 1), (2, 0), (0, 0)), 25, 0),
                                          (((24, 1), (700, 1), (3, 0)), 26, 17),
                                          (((24, 1), (700, 1), (2, 0)), 26, 60)):
                kw = dict(level=level, huts=huts, population=population)
                for config in V2_PATCHED:
                    with self.subTest(config=config, **_label(kw)):
                        self.assertEqual(self._built(_vv2(config, **kw)), [("build", hut)])
            self.assertEqual(self._built(_vv2("stock", level=level, huts=((24, 1), (12, 0), (0, 0)), population=17)),
                             [], "the stock game abandons it below 23")

    def test_an_untouched_hut_is_never_started(self):
        for progress in (0, 1):
            for huts, population in ((((24, 1), (progress, 0), (0, 0)), 21), (((24, 1), (progress, 0), (0, 0)), 60),
                                     (((24, 1), (700, 1), (progress, 0)), 46),
                                     (((24, 1), (700, 1), (progress, 0)), 60)):
                kw = dict(huts=huts, population=population)
                with self.subTest(**_label(kw)):
                    stock = _vv2("stock", **kw)
                    self.assertEqual(self._built(stock), [])
                    self.assertEqual(effects(_vv2("fix huts, roll fails", **kw)), effects(stock))
                    passed = _vv2("fix huts, roll passes", **kw)
                    self.assertEqual(self._built(passed), [])
                    self.assertTrue([o for o in v2_outcome(passed) if o[0] == "examine"], v2_outcome(passed))

    def test_above_the_old_numbers_nothing_changes(self):
        for kw in (dict(huts=((24, 1), (2, 0), (0, 0)), population=30),
                   dict(huts=((24, 1), (700, 1), (5, 0)), population=50),
                   dict(huts=((24, 0), (0, 0), (0, 0)), population=3)):
            with self.subTest(**_label(kw)):
                stock = _vv2("stock", **kw)
                self.assertTrue(self._built(stock))
                for config in V2_PATCHED:
                    self.assertEqual(effects(_vv2(config, **kw)), effects(stock), config)

    def test_option_a_builds_a_started_hut_the_stock_rolls_skipped(self):
        for level, site in ((3, V2["hut_site"]), (1, V2["level_site"])):
            for huts, hut in ((((24, 1), (12, 0), (0, 0)), 25), (((24, 1), (700, 1), (2, 0)), 26)):
                with self.subTest(level=level, hut=hut):
                    kw = dict(level=level, huts=huts, population=17)
                    passed = _vv2("fix huts, roll passes", rolls=_low("vv2"), **kw)
                    self.assertEqual(v2_outcome(passed), [("build", hut)])
                    self.assertIn(site, passed.seen)
                    failed, stock = (_vv2("fix huts, roll fails", rolls=_low("vv2"), **kw),
                                     _vv2("stock", rolls=_low("vv2"), **kw))
                    self.assertEqual(effects(failed), effects(stock))

    def test_the_new_hut_test_runs_in_the_live_dispatcher(self):
        for config in V2_PATCHED:
            with self.subTest(config=config):
                m = _vv2(config, huts=((24, 1), (12, 0), (0, 0)), population=17)
                self.assertIn(V2["disp"], m.seen)
                self.assertEqual(bytes(m.mu.mem_read(GATE["vv2"], 8)), bytes.fromhex("389920E80200740D"))


# ---- Catch-up -----------------------------------------------------------------
V1_CATCH_UP = 0x42E790          # one catch-up job step for villager `index`, thiscall, ret 4
V2_CATCH_UP = 0x43B4D0


def _catch_up(game: str, config: str, **kw):
    if config == "fix huts, not yet installed":
        # The rendered executable, before the companion has installed anything
        # (The Lost Children's first load-time catch-up of a session).
        m = lost_children(rows=ROWS["vv2"], runtime=False, **kw)
        return _catch_up_run(game, m)
    m = (_vv1 if game == "vv1" else _vv2)(config, **kw)
    return _catch_up_run(game, m)


def _catch_up_run(game, m):
    """One catch-up step for villager INDEX, run from the step's own entry in
    the same emulated process the live tests use (rows, companions installed,
    village state laid out), with the step's own leaves scripted: the job
    reset, the preferred-job picker (Building) and the job simulation."""
    m.w32(OBJ + 4, VILLAGE)
    if game == "vv1":
        rec = VILLAGE + INDEX * 0x3D8
        m.w32(rec + 0x344, 0x40)                 # the age/skill test 0x42E7C5 (>= 0x14)
        m.leaves.update({
            0x439470: Leaf(1, lambda m, a, c, r: 0, name="reset"),
            0x439AE0: Leaf(2, lambda m, a, c, r: 4, name="picker"),
            0x446C70: Leaf(1, lambda m, a, c, r: 0, name="simulate"),
        })
        start = V1_CATCH_UP
    else:
        rec = VILLAGE + INDEX * 0xE48C
        m.w32(rec + 0x52C, 0x40)
        m.leaves.update({
            0x4492A0: Leaf(1, lambda m, a, c, r: 0, name="reset"),
            0x449C60: Leaf(2, lambda m, a, c, r: 5, name="picker"),
            0x464680: Leaf(1, lambda m, a, c, r: 0, name="simulate"),
        })
        start = V2_CATCH_UP
    m.calls, m.seen = [], []
    m.run(start, HALT, {UC_X86_REG_ECX: OBJ}, stack=(HALT, INDEX))
    assert ("simulate" in [c[0] for c in m.calls]), "the step ran the job simulation"
    return m


@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class CatchUpTests(unittest.TestCase):
    """While the game was closed, or during a Time Warp, each villager's job
    steps run through the same Building dispatcher: an enabled hut keeps being
    built whatever the population, an untouched scaffold is not started."""

    def test_a_new_home(self):
        cases = (
            (dict(huts=(1, 0, 0), projects={10: (12, 0)}, population=17), [("build hut", 10)], []),
            (dict(huts=(1, 1, 0), projects={11: (2, 0)}, population=5), [("build hut", 11)], []),
            (dict(huts=(1, 0, 0), projects={10: (1, 0)}, population=10), [], []),
            (dict(huts=(1, 0, 0), projects={10: (1, 0)}, population=40), [], [("build hut", 10)]),
        )
        for kw, patched, stock in cases:
            with self.subTest(config="stock", **_label(kw)):
                m = _catch_up("vv1", "stock", **kw)
                self.assertIn(V1["disp"], m.seen if V1["disp"] in m.watch else [V1["disp"]])
                self.assertEqual([o for o in v1_outcome(m) if o[0] == "build hut"], stock)
            for config in V1_PATCHED:
                with self.subTest(config=config, **_label(kw)):
                    m = _catch_up("vv1", config, **kw)
                    self.assertEqual([o for o in v1_outcome(m) if o[0] == "build hut"], patched)

    def test_the_lost_children(self):
        cases = (
            (dict(huts=((24, 1), (12, 0), (0, 0)), population=17), [("build", 25)], []),
            (dict(huts=((24, 1), (700, 1), (2, 0)), population=5), [("build", 26)], []),
            (dict(huts=((24, 1), (1, 0), (0, 0)), population=10), [], []),
            (dict(huts=((24, 1), (1, 0), (0, 0)), population=60), [], []),
        )
        for kw, patched, stock in cases:
            with self.subTest(config="stock", **_label(kw)):
                m = _catch_up("vv2", "stock", **kw)
                self.assertEqual([o for o in v2_outcome(m) if o[0] == "build"], stock)
            for config in V2_PATCHED + ("fix huts, not yet installed",):
                with self.subTest(config=config, **_label(kw)):
                    m = _catch_up("vv2", config, **kw)
                    self.assertEqual([o for o in v2_outcome(m) if o[0] == "build"], patched)
                    self.assertIn(V2["disp"], m.seen)


class DescriptionTests(unittest.TestCase):
    def test_builder_action_fixes(self):
        text = _builds_row("vv1_builder_action_fixes")["description"]
        for phrase in ("hidden rule", "15 villagers", "at 28", "more than 22", "more than 45",
                       "only after you have dropped a villager on it at least once",
                       "finish it whatever the population"):
            self.assertIn(phrase, text)

    def test_builders_fix_huts_when_idle(self):
        numbers = {"vv1": ("15 villagers", "at 28"), "vv2": ("21 villagers", "at 46")}
        for game, (first, second) in numbers.items():
            with self.subTest(game=game):
                row = json.loads((ROOT / "data" / f"{game}_builders_fix_huts_feature.json").read_text("utf-8"))
                for phrase in ("hidden rule", first, second, "more than 22", "more than 45",
                               "only after you have dropped a villager on it at least once",
                               "**Runs on the Origins-exclusive base"):
                    self.assertIn(phrase, row["description"])


if __name__ == "__main__":
    unittest.main()
