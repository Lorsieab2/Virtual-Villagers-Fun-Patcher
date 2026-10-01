"""Builders build a population hut as soon as its scaffold shows, and always
finish a hut they have started (A New Home, The Lost Children).

The owner's report (v1.35.42, read live from the running A New Home village):
Building level 2, population 17, hut 10 at progress 12 and not complete; its
four builders spent most of their time "Fixing hut" and hut 10 never
progressed.  Then: the game shows the second hut's scaffold well below 22
villagers, yet builders will not work on it until the population passes 22.
The owner's decision: a population hut is built as soon as the game shows its
scaffold, and a started hut is always finished, whatever the population.

The stock rule, read from the executables:

  A New Home  Building branch 0x447528: hut 9 whenever incomplete; hut 10 only
              with population > 22 (0x44754F), hut 11 only > 45 (0x447581) --
              progress is never looked at.  The village drawing routine shows
              hut 10's scaffold at population >= 15 (0x414AE7) and hut 11's at
              >= 28 (0x414BCC), or whenever the hut has progress, and writes
              progress 1 when it first shows it (0x414B0C, 0x414BF1, ebx = 1).
  The Lost Children  0x4600DE: hut 25 only with population > 22 and progress
              >= 2, hut 26 only > 45 and progress >= 2.  The scaffold shows at
              >= 21 (0x4196ED) and >= 46 (0x419768), or with progress, and
              gets progress 1 (0x419702, 0x41977D) -- so the stock test never
              let a builder start either hut.

The fix replaces each test with the scaffold's (incomplete, and progress > 0
or the population at the scaffold's number): in the executable for A New Home
through Builder Action Fixes, and at run time through the fix-huts companion
in both games, whose build-first helpers make the same judgement.  The Secret
City, The Tree of Life and New Believers have no population test in their
Building dispatcher (their hut options test only the hut's own state and
completion), so nothing changes there.

Every run here is EMULATED FROM THE GAME'S OWN CALLER with the harness of
tests/test_builders_decision_roll.py: the executable the patcher renders, the
companions' test builds installed as their per-frame callers install them,
the scheduler and the Building dispatcher running as machine code.
"""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from test_builders_decision_roll import (
    FORCE_FAIL, FORCE_PASS, ROWS, STOCK, STOCK_ABSENT, STOCK_PRESENT, TEST_BUILD_ABSENT, TEST_BUILDS_PRESENT,
    V1, V2, Rolls, _low, effects, lost_children, new_home, v1_outcome, v2_outcome,
)

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
    """The numbers the fix uses are the game's own."""

    def test_a_new_home_builder_and_scaffold_numbers(self):
        # Builders: cmp eax, 22; jle / cmp eax, 45; jle after the population call.
        self.assertEqual(_stock("vv1", 0x44754A, 10), bytes.fromhex("E8415AFDFF83F8167E22"))
        self.assertEqual(_stock("vv1", 0x44757C, 10), bytes.fromhex("E80F5AFDFF83F82D7E4B"))
        # Scaffold: population >= 15 (hut 10) / >= 28 (hut 11), else any progress.
        self.assertEqual(_stock("vv1", 0x414AE2, 10), bytes.fromhex("E8A984000083F80F7D10"))
        self.assertEqual(_stock("vv1", 0x414BC7, 10), bytes.fromhex("E8C483000083F81C7D10"))
        # ... and the scaffold's first showing writes progress 1 (ebx = 1).
        self.assertEqual(_stock("vv1", 0x41491B, 5), bytes.fromhex("BB01000000"))
        self.assertEqual(_stock("vv1", 0x414B0C, 6), bytes.fromhex("8998EC9F0000"))
        self.assertEqual(_stock("vv1", 0x414BF1, 6), bytes.fromhex("8998F49F0000"))

    def test_the_lost_children_builder_and_scaffold_numbers(self):
        # Builders: population > 22 and progress >= 2 (ebp = 2) / > 45 and >= 2.
        self.assertEqual(_stock("vv2", 0x4600E3, 5), bytes.fromhex("83F8167E1A"))
        self.assertEqual(_stock("vv2", 0x4600F6, 6), bytes.fromhex("39A81CE80200"))
        self.assertEqual(_stock("vv2", 0x46010D, 5), bytes.fromhex("83F82D7E1A"))
        self.assertEqual(_stock("vv2", 0x4600C5, 5), bytes.fromhex("BD02000000"))
        # Scaffold: population >= 21 / >= 46, else any progress, and progress 1.
        self.assertEqual(_stock("vv2", 0x4196E8, 10), bytes.fromhex("E873C1000083F8157C50"))
        self.assertEqual(_stock("vv2", 0x419763, 10), bytes.fromhex("E8F8C0000083F82E7C50"))
        self.assertEqual(_stock("vv2", 0x419702, 10), bytes.fromhex("C7801CE8020001000000"))
        self.assertEqual(_stock("vv2", 0x41977D, 10), bytes.fromhex("C78024E8020001000000"))


@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class TheLiftedBytesTests(unittest.TestCase):
    def test_the_companion_writes_over_the_exact_stock_bytes(self):
        for game, no in (("vv1", 1), ("vv2", 2)):
            with self.subTest(game=game):
                va, stock, lifted = _probe_gate(no)
                self.assertEqual(va, GATE[game])
                self.assertEqual(_stock(game, va, len(stock)), stock)
                manifest = json.loads((ROOT / "data" / f"{game}_builders_fix_huts_feature.json").read_text("utf-8"))
                entry = next(d for d in manifest["runtime_detours"] if int(d["va"], 16) == va)
                self.assertEqual(bytes.fromhex(entry["stock_bytes"]), stock)
        for no in (3, 4, 5):
            from test_builders_decision_roll import Machine
            m = Machine("vv1", STOCK["vv1"].read_bytes(), modules=("fix_huts",))
            m.mu.mem_map(0x0EF00000, 0x1000)
            self.assertEqual(m.call_export("fix_huts", "VvfpFixHutsProbeGate", no, 0x0EF00000, 0x0EF00100,
                                           0x0EF00200), 0, "no such gate in the later games")

    def test_builder_action_fixes_writes_the_companions_bytes(self):
        va, stock, lifted = _probe_gate(1)
        row = next(p for p in _builds_row("vv1_builder_action_fixes")["patches"] if p["offset"] == "0x4754A")
        self.assertEqual(va - 0x400000, 0x4754A)
        self.assertEqual(bytes.fromhex(row["before"]), stock)
        self.assertEqual(bytes.fromhex(row["after"]), lifted, "one change, written by either patch")
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv1")
        rendered, _ = vfp.render_patched_bytes(STOCK["vv1"], build, "stock", list(BAF))
        self.assertEqual(bytes(rendered[0x4754A:0x4754A + len(lifted)]), lifted)

    def test_the_hut_section_around_the_lifted_bytes_is_untouched(self):
        # The hut-9 build tail both patches jump to (push ebp; mov ecx, esi;
        # call 0x442090; the epilogue) and hut 11's build block after the bytes.
        import vv_fun_patcher as vfp
        build = next(b for b in vfp.load_builds() if b.id == "vv1")
        rendered, _ = vfp.render_patched_bytes(STOCK["vv1"], build, "stock", list(BAF))
        stock = STOCK["vv1"].read_bytes()
        self.assertEqual(bytes(rendered[0x47528:0x4754A]), stock[0x47528:0x4754A])
        self.assertEqual(bytes(rendered[0x47594:0x475A8]), stock[0x47594:0x475A8])
        self.assertEqual(stock[0x47539:0x47541], bytes.fromhex("558BCEE84FABFFFF"))
        self.assertEqual(stock[0x47594:0x4759A], bytes.fromhex("536A0B558BCE"))


def _vv1(config: str, **kw):
    if config == "stock":
        return new_home(rows=(), runtime=False, **kw)
    if config == "baf":
        return new_home(rows=BAF, runtime=False, **kw)
    if config == "fix huts, roll passes":
        return new_home(rows=ROWS["vv1"], force=FORCE_PASS, **kw)
    if config == "fix huts, roll fails":
        return new_home(rows=ROWS["vv1"], force=FORCE_FAIL, **kw)
    raise ValueError(config)


def _vv2(config: str, **kw):
    if config == "stock":
        return lost_children(rows=(), runtime=False, **kw)
    if config == "fix huts, roll passes":
        return lost_children(rows=ROWS["vv2"], force=FORCE_PASS, **kw)
    if config == "fix huts, roll fails":
        return lost_children(rows=ROWS["vv2"], force=FORCE_FAIL, **kw)
    raise ValueError(config)


V1_PATCHED = ("baf", "fix huts, roll passes", "fix huts, roll fails")
V2_PATCHED = ("fix huts, roll passes", "fix huts, roll fails")


@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class NewHomeFromTheRealCallerTests(unittest.TestCase):
    """A builder (selected job Building), Building level 3 and 2, food 100,
    hut 9 built; the game's rand answers high, so the stock branch walks into
    its new-hut section."""

    def _built(self, m) -> list:
        return [o for o in v1_outcome(m) if o[0] == "build hut"]

    def test_the_owners_village_a_started_hut_below_its_number_is_built(self):
        # Population 17, hut 10 at progress 12.
        for level in (3, 2):
            kw = dict(level=level, huts=(1, 0, 0), projects={10: (12, 0)}, population=17)
            with self.subTest(level=level, config="stock"):
                self.assertEqual(self._built(_vv1("stock", **kw)), [], "the stock game abandons it")
            for config in V1_PATCHED:
                with self.subTest(level=level, config=config):
                    self.assertEqual(self._built(_vv1(config, **kw)), [("build hut", 10)])

    def test_a_shown_scaffold_is_built_from_its_number(self):
        cases = (
            (dict(huts=(1, 0, 0), population=15), 10),                       # scaffold shown at 15
            (dict(huts=(1, 0, 0), projects={10: (1, 0)}, population=5), 10),  # its progress-1 mark
            (dict(huts=(1, 1, 0), population=28), 11),
            (dict(huts=(1, 1, 0), projects={11: (1, 0)}, population=5), 11),
            (dict(huts=(1, 1, 0), projects={11: (40, 0)}, population=30), 11),
        )
        for kw, hut in cases:
            with self.subTest(config="stock", **{k: str(v) for k, v in kw.items()}):
                self.assertEqual(self._built(_vv1("stock", **kw)), [])
            for config in V1_PATCHED:
                with self.subTest(config=config, **{k: str(v) for k, v in kw.items()}):
                    self.assertEqual(self._built(_vv1(config, **kw)), [("build hut", hut)])

    def test_an_unshown_scaffold_waits_exactly_as_the_stock_game(self):
        # Unstarted and below the scaffold's number: not construction.  The
        # executable-only patch and the companion whose roll failed do exactly
        # what the stock executable does; with the roll passing, a built hut is
        # fixed rather than anything built.
        for kw in (dict(huts=(1, 0, 0), population=14), dict(huts=(1, 0, 0), population=0),
                   dict(huts=(1, 1, 0), population=27), dict(huts=(1, 1, 0), population=14)):
            with self.subTest(**{k: str(v) for k, v in kw.items()}):
                stock = _vv1("stock", **kw)
                self.assertEqual(self._built(stock), [])
                for config in ("baf", "fix huts, roll fails"):
                    m = _vv1(config, **kw)
                    self.assertEqual(effects(m), effects(stock), config)
                passed = _vv1("fix huts, roll passes", **kw)
                self.assertEqual(self._built(passed), [])
                self.assertTrue([o for o in v1_outcome(passed) if o[0] == "examine"], v1_outcome(passed))

    def test_above_the_old_numbers_nothing_changes(self):
        for kw in (dict(huts=(1, 0, 0), population=23), dict(huts=(1, 0, 0), projects={10: (50, 0)}, population=40),
                   dict(huts=(1, 1, 0), population=46), dict(huts=(0, 0, 0), population=3)):
            with self.subTest(**{k: str(v) for k, v in kw.items()}):
                stock = _vv1("stock", **kw)
                self.assertTrue(self._built(stock), "the stock game builds here")
                for config in V1_PATCHED:
                    self.assertEqual(effects(_vv1(config, **kw)), effects(stock), config)

    def test_a_complete_hut_is_never_built_again(self):
        kw = dict(huts=(1, 1, 0), projects={10: (400, 1)}, population=10)
        for config in ("stock",) + V1_PATCHED:
            with self.subTest(config=config):
                self.assertNotIn(("build hut", 10), self._built(_vv1(config, **kw)))

    def test_option_a_builds_a_started_hut_the_stock_roll_skipped(self):
        # The stock branch's first roll says "not this time", so it never
        # reaches its new-hut section; with the decision's roll passing the
        # companion's build-first check goes straight into hut 10 (its own
        # entry into the section's build tail) instead of a fix -- at the
        # skip-roll site (level 3) and at the level gate (level 2).
        for level, site in ((3, V1["hut_site"]), (2, V1["level_site"])):
            with self.subTest(level=level):
                kw = dict(level=level, huts=(1, 0, 0), projects={10: (12, 0)}, population=17)
                rolls = lambda: Rolls({V1["gate_roll"]: 99, V1["first_roll"]: 0}, default=lambda n: 0)
                passed = _vv1("fix huts, roll passes", rolls=rolls(), **kw)
                self.assertEqual(v1_outcome(passed), [("build hut", 10)])
                self.assertIn(site, passed.seen)
                failed, stock = _vv1("fix huts, roll fails", rolls=rolls(), **kw), _vv1("stock", rolls=rolls(), **kw)
                self.assertEqual(effects(failed), effects(stock), "the roll failed: the stock skip")
                self.assertNotIn(("build hut", 10), v1_outcome(stock))
                # Unstarted, population 17: the scaffold stands -- built.
                # Unstarted below 15: still not construction -- a hut fix.
                kw["projects"] = {}
                self.assertEqual(v1_outcome(_vv1("fix huts, roll passes", rolls=rolls(), **kw)), [("build hut", 10)])
                kw["population"] = 14
                self.assertEqual(v1_outcome(_vv1("fix huts, roll passes", rolls=rolls(), **kw)), [("examine", 9)])

    def test_the_new_hut_test_runs_in_the_live_dispatcher(self):
        # Liveness: the lifted bytes are executed on this path.
        for config in V1_PATCHED:
            with self.subTest(config=config):
                m = _vv1(config, huts=(1, 0, 0), projects={10: (12, 0)}, population=17)
                self.assertIn(V1["disp"], m.seen)
                code = bytes(m.mu.mem_read(GATE["vv1"], 8))
                self.assertEqual(code, bytes.fromhex("3899F09F00007421"), "the lifted test is in place")


@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
class LostChildrenFromTheRealCallerTests(unittest.TestCase):
    """A builder (selected job Building), Building level 3 and 1, food 100,
    hut 24 built; the game's rand answers high."""

    def _built(self, m) -> list:
        return [o for o in v2_outcome(m) if o[0] == "build"]

    def test_a_started_hut_below_its_number_is_built(self):
        for level in (3, 1):
            for huts, hut in ((((24, 1), (12, 0), (0, 0)), 25), (((24, 1), (2, 0), (0, 0)), 25),
                              (((24, 1), (700, 1), (3, 0)), 26)):
                kw = dict(level=level, huts=huts, population=17)
                with self.subTest(level=level, huts=huts, config="stock"):
                    self.assertEqual(self._built(_vv2("stock", **kw)), [])
                for config in V2_PATCHED:
                    with self.subTest(level=level, huts=huts, config=config):
                        self.assertEqual(self._built(_vv2(config, **kw)), [("build", hut)])

    def test_a_shown_scaffold_is_built_from_its_number(self):
        cases = (
            (dict(huts=((24, 1), (0, 0), (0, 0)), population=21), 25),
            (dict(huts=((24, 1), (1, 0), (0, 0)), population=5), 25),      # the progress-1 mark
            (dict(huts=((24, 1), (1, 0), (0, 0)), population=30), 25),     # stock: progress below 2
            (dict(huts=((24, 1), (700, 1), (0, 0)), population=46), 26),
            (dict(huts=((24, 1), (700, 1), (1, 0)), population=50), 26),
        )
        for kw, hut in cases:
            with self.subTest(config="stock", **{k: str(v) for k, v in kw.items()}):
                self.assertEqual(self._built(_vv2("stock", **kw)), [])
            for config in V2_PATCHED:
                with self.subTest(config=config, **{k: str(v) for k, v in kw.items()}):
                    self.assertEqual(self._built(_vv2(config, **kw)), [("build", hut)])

    def test_an_unshown_scaffold_waits_exactly_as_the_stock_game(self):
        for kw in (dict(huts=((24, 1), (0, 0), (0, 0)), population=20),
                   dict(huts=((24, 1), (700, 1), (0, 0)), population=45)):
            with self.subTest(**{k: str(v) for k, v in kw.items()}):
                stock = _vv2("stock", **kw)
                self.assertEqual(self._built(stock), [])
                failed = _vv2("fix huts, roll fails", **kw)
                self.assertEqual(effects(failed), effects(stock))
                passed = _vv2("fix huts, roll passes", **kw)
                self.assertEqual(self._built(passed), [])
                self.assertTrue([o for o in v2_outcome(passed) if o[0] == "examine"], v2_outcome(passed))

    def test_above_the_old_numbers_nothing_changes(self):
        for kw in (dict(huts=((24, 1), (2, 0), (0, 0)), population=30),
                   dict(huts=((24, 1), (700, 1), (5, 0)), population=50),
                   dict(huts=((24, 0), (0, 0), (0, 0)), population=3)):
            with self.subTest(**{k: str(v) for k, v in kw.items()}):
                stock = _vv2("stock", **kw)
                self.assertTrue(self._built(stock), "the stock game builds here")
                for config in V2_PATCHED:
                    self.assertEqual(effects(_vv2(config, **kw)), effects(stock), config)

    def test_a_complete_hut_is_never_built_again(self):
        kw = dict(huts=((24, 1), (700, 1), (0, 0)), population=10)
        for config in ("stock",) + V2_PATCHED:
            with self.subTest(config=config):
                self.assertNotIn(("build", 25), self._built(_vv2(config, **kw)))

    def test_option_a_builds_a_started_hut_the_stock_rolls_skipped(self):
        for level, site in ((3, V2["hut_site"]), (1, V2["level_site"])):
            for huts, hut in ((((24, 1), (12, 0), (0, 0)), 25), (((24, 1), (700, 1), (1, 0)), 26)):
                with self.subTest(level=level, hut=hut):
                    kw = dict(level=level, huts=huts, population=17)
                    passed = _vv2("fix huts, roll passes", rolls=_low("vv2"), **kw)
                    self.assertEqual(v2_outcome(passed), [("build", hut)])
                    self.assertIn(site, passed.seen)
                    failed, stock = (_vv2("fix huts, roll fails", rolls=_low("vv2"), **kw),
                                     _vv2("stock", rolls=_low("vv2"), **kw))
                    self.assertEqual(effects(failed), effects(stock))
                    self.assertNotIn(("build", hut), v2_outcome(stock))

    def test_the_new_hut_test_runs_in_the_live_dispatcher(self):
        for config in V2_PATCHED:
            with self.subTest(config=config):
                m = _vv2(config, huts=((24, 1), (12, 0), (0, 0)), population=17)
                self.assertIn(V2["disp"], m.seen)
                self.assertEqual(bytes(m.mu.mem_read(GATE["vv2"], 8)), bytes.fromhex("389920E80200741B"))


class DescriptionTests(unittest.TestCase):
    """The owner never knew the rule: each affected game's description spells
    it out with that game's numbers."""

    def test_builder_action_fixes(self):
        text = _builds_row("vv1_builder_action_fixes")["description"]
        for phrase in ("hidden rule", "15 villagers", "at 28", "more than 22", "more than 45",
                       "already been started is finished even if the population drops back"):
            self.assertIn(phrase, text)

    def test_builders_fix_huts_when_idle(self):
        numbers = {"vv1": ("15 villagers", "at 28"), "vv2": ("21 villagers", "at 46")}
        for game, (first, second) in numbers.items():
            with self.subTest(game=game):
                row = json.loads((ROOT / "data" / f"{game}_builders_fix_huts_feature.json").read_text("utf-8"))
                for phrase in ("hidden rule", first, second, "more than 22", "more than 45",
                               "already been started is finished even if the population drops back",
                               "**Runs on the Origins-exclusive base"):
                    self.assertIn(phrase, row["description"])
        for game in ("vv3", "vv4", "vv5"):
            with self.subTest(game=game):
                row = json.loads((ROOT / "data" / f"{game}_builders_fix_huts_feature.json").read_text("utf-8"))
                self.assertNotIn("hidden rule", row["description"], "no such rule in this game")


if __name__ == "__main__":
    unittest.main()
