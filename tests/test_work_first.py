"""Builders and Healers Work First, upgraded to skill practice (all five games)
-- the addendum to Builders Fix Huts When Idle.

The owner's decisions (2026-11-17, "Skill Practice - Behaviors to Approve"):
villagers practise their selected job on their own -- Farming, Research,
Healing, Building and New Believers' Devotion -- about three times in four,
the roll shared with Builders Fix Huts When Idle; Parenting stays under the
Birth Control patches; builders never start a project nobody was dropped on;
puzzle work and tool jobs stay the game's; New Believers' Devotion is never
doubled up with Easier Devotee Training.  Plus the items that need sites of
their own: beginners (items 1, 2), the fruit trip and noni in catch-up (84,
101) and The Lost Children's sewing hut (30).

Pinned here, EMULATED in the executable the patcher renders for the rows with
the companions' test builds installed (tests/test_catch_up_work_first.world):

* every runtime site's stock bytes, and that the installer writes them all;
* the live scheduler's calls: the own job first, the caller's request when it
  starts nothing, the caller's request alone when the roll fails or for any
  other caller, Parenting never, Research never in place of Farming;
* New Believers' live Devotion only without Easier Devotee Training;
* the beginners' gate, the catch-up offers and the sewing hut, each stub run
  from its site with the game's registers;
* the five rows ship and pin the DLL and list every site.
Catch-up, the fallbacks (exercise, herb study), the builders' rule and the
untrained mark: tests/test_catch_up_work_first.py.  Every behaviour here
fails with the earlier DLL.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

from test_builders_decision_roll import (
    FORCE_FAIL, FORCE_PASS, HALT, OBJ, RECORD, STATE, STOCK_ABSENT, STOCK_PRESENT, TEST_BUILD_ABSENT,
    TEST_BUILDS_PRESENT, VILLAGE, INDEX, Leaf,
)
from test_catch_up_work_first import G, GAMES, _stock_bytes_at, world, _own_jobs, _other

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DLL = ROOT / "assets" / "work_first" / "VVFP Work First.dll"
WORK_FIRST_BASE = 0x11000000

# The adult scheduler's calls of the dispatcher (their return addresses).
LIVE = {
    "vv1": (0x448355, 0x448382),
    "vv2": (0x461A08, 0x461A35),
    "vv3": (0x45C23C, 0x45C27A, 0x45C28F),
    "vv4": (0x4659D2, 0x465A17, 0x465A2A),
    "vv5": (0x46F291, 0x46F2D6, 0x46F2EA),
}
OTHER_CALLER = {"vv1": 0x447D99, "vv2": 0x4605F9, "vv3": 0x45AA99, "vv4": 0x4634D9, "vv5": 0x46BCF9}


def live(m, game, ret, job):
    """The scheduler's `call dispatcher` returning to `ret`, asking `job`."""
    m.asked, m.marks, m.calls = [], [], []
    if game in ("vv1", "vv2"):
        m.run(G[game]["disp"], ret, {UC_X86_REG_ECX: VILLAGE}, stack=(ret, INDEX, job))
    elif game == "vv3":
        m.run(G[game]["disp"], ret, {UC_X86_REG_ECX: VILLAGE}, stack=(ret, RECORD, job))
    else:
        m.run(G[game]["disp"], ret, {UC_X86_REG_ECX: OBJ}, stack=(ret, job))
    return m


def jobs(m):
    return [job for _, job in m.asked]


def run_until(m, start, targets, regs, stack=()):
    """Run from `start` until one of `targets` is reached; returns it."""
    reached = []

    def hook(mu, address, size, user_data):
        reached.append(address)
        mu.emu_stop()
    handles = [m.mu.hook_add(UC_HOOK_CODE, hook, begin=t, end=t) for t in targets]
    try:
        m.stop_at = None
        m.mu.reg_write(UC_X86_REG_ESP, 0x0F000000 - 0x1000 - 4 * len(stack))
        if stack:
            m.mu.mem_write(0x0F000000 - 0x1000 - 4 * len(stack), struct.pack(f"<{len(stack)}I", *stack))
        for reg, value in regs.items():
            m.mu.reg_write(reg, value)
        m.error = None
        m.mu.emu_start(start, 0, count=200000)
        if m.error and not reached:
            raise AssertionError(m.error)
    finally:
        for h in handles:
            m.mu.hook_del(h)
    return reached[0] if reached else m.mu.reg_read(UC_X86_REG_EIP)


def _manifest(game):
    return json.loads((ROOT / "data" / f"{game}_work_first_feature.json").read_text(encoding="utf-8"))


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class SiteTests(unittest.TestCase):
    def test_every_runtime_site_is_stock_and_installed(self):
        for game in ("vv1", "vv2", "vv4", "vv5"):
            m = world(game)
            for site in _manifest(game)["runtime_detours"]:
                va = int(site["va"], 16)
                stock = bytes.fromhex(site["stock_bytes"])
                with self.subTest(game=game, va=hex(va)):
                    self.assertEqual(_stock_bytes_at(game, va, len(stock)), stock)
                    code = bytes(m.mu.mem_read(va, len(stock)))
                    self.assertEqual(code[0], 0xE9)
                    target = (va + 5 + struct.unpack("<i", code[1:5])[0]) & 0xFFFFFFFF
                    self.assertTrue(WORK_FIRST_BASE <= target < WORK_FIRST_BASE + 0x1000000, hex(target))
                    self.assertEqual(code[5:], b"\x90" * (len(stock) - 5))

    def test_the_scheduler_call_sites(self):
        for game, rets in LIVE.items():
            for ret in rets:
                with self.subTest(game=game, ret=hex(ret)):
                    code = _stock_bytes_at(game, ret - 5, 5)
                    self.assertEqual(code[0], 0xE8)
                    self.assertEqual((ret + struct.unpack("<i", code[1:])[0]) & 0xFFFFFFFF, G[game]["disp"])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class LiveScheduler(unittest.TestCase):
    def test_the_own_job_first_for_every_practised_job(self):
        for game in GAMES:
            for who, own in _own_jobs(game):
                other = _other(game, own)
                for ret in LIVE[game]:
                    with self.subTest(game=game, who=who, ret=hex(ret)):
                        m = live(world(game, selected=own, pick=other), game, ret, other)
                        self.assertEqual(jobs(m), [own])
                        self.assertEqual(m.mu.reg_read(UC_X86_REG_EAX) & 0xFF, 1)
                        # Nothing of theirs to do: the scheduler's own request.
                        m = live(world(game, selected=own, pick=other, food=200,
                                       starts=lambda j, o=own: j != o), game, ret, other)
                        self.assertEqual(jobs(m), [own, other])
                        self.assertEqual(m.asked[-1][0], ret, "the request with the scheduler's own frame")

    def test_a_failed_roll_or_another_caller_is_the_request_alone(self):
        for game in GAMES:
            g = G[game]
            own = g["healing"]
            other = g["building"]
            with self.subTest(game=game, case="roll"):
                m = live(world(game, selected=own, force=FORCE_FAIL), game, LIVE[game][0], other)
                self.assertEqual(m.asked, [(LIVE[game][0], other)])
            with self.subTest(game=game, case="caller"):
                m = live(world(game, selected=own), game, OTHER_CALLER[game], other)
                self.assertEqual(m.asked, [(OTHER_CALLER[game], other)])
                self.assertEqual(m.draws("fix_huts"), 0)

    def test_parenting_is_never_put_first(self):
        for game in GAMES:
            g = G[game]
            for ret in LIVE[game]:
                with self.subTest(game=game, ret=hex(ret)):
                    m = live(world(game, selected=g["parenting"]), game, ret, g["healing"])
                    self.assertEqual(m.asked, [(ret, g["healing"])])
                    self.assertEqual(m.draws("fix_huts"), 0)

    def test_research_never_takes_the_place_of_farming(self):
        # The later games' low-food scheduler asks for Farming first.
        for game in GAMES:
            g = G[game]
            with self.subTest(game=game):
                m = live(world(game, selected=g["research"]), game, LIVE[game][0], g["farming"])
                self.assertEqual(m.asked, [(LIVE[game][0], g["farming"])])
                m = live(world(game, selected=g["research"]), game, LIVE[game][0], g["healing"])
                self.assertEqual(jobs(m), [g["research"]])

    def test_a_new_home_farmer_only_where_the_farming_case_starts_something(self):
        # A New Home's Farming case reports "started" with nothing started
        # at level 1 with nothing to forage: no farmer is put first there.
        g = G["vv1"]
        for level, forage, first in ((1, 0, False), (1, 5, True), (2, 0, True), (3, 0, True)):
            with self.subTest(level=level, forage=forage):
                m = world("vv1", selected=g["farming"], farm_level=level)
                m.w32(STATE + 0xA2F4, forage)
                live(m, "vv1", LIVE["vv1"][0], g["healing"])
                self.assertEqual(jobs(m)[0] == g["farming"], first)


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class NewBelieversDevotion(unittest.TestCase):
    """Item 98: devotees practise Devotion while you play too -- but never on
    top of Easier Devotee Training, which already sends them Honoring."""

    def test_live_devotion_without_easier_devotee_training(self):
        for ret in LIVE["vv5"]:
            with self.subTest(ret=hex(ret)):
                m = live(world("vv5", selected=5), "vv5", ret, 3)
                self.assertEqual(jobs(m), [5])

    def test_with_easier_devotee_training_the_game_decides(self):
        for ret in LIVE["vv5"]:
            with self.subTest(ret=hex(ret)):
                m = world("vv5", selected=5, pick=3)
                # Easier Devotee Training's jmp in place of the stock test.
                m.mu.mem_write(0x46F1DD, bytes.fromhex("E91E520200") + b"\x90" * 4)
                live(m, "vv5", ret, 3)
                self.assertEqual(m.asked, [(ret, 3)])
                # ... while in catch-up the devotee is still put first.
                m.asked = []
                m.decide()
                self.assertEqual([j for _, j in m.asked][:1], [5])


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class Beginners(unittest.TestCase):
    """Items 1 and 2: the picker's `cmp esi, 5; jle fail` -- for the selected
    job (never Parenting), on the decision's roll, a skill of 5 or less goes
    on to the game's own roll."""

    SITES = {"vv4": (0x461E69, 0x461E6E, 0x461EB4, 0x1C70), "vv5": (0x46A594, 0x46A599, 0x46A5DF, 0x1C74)}

    def gate(self, game, skill, job, selected, force=FORCE_PASS):
        site, go, fail, field = self.SITES[game]
        m = world(game, selected=selected, force=force)
        where = run_until(m, site, (go, fail), {UC_X86_REG_ESI: skill, UC_X86_REG_EBX: job, UC_X86_REG_EDI: OBJ})
        self.assertEqual((m.mu.reg_read(UC_X86_REG_ESI), m.mu.reg_read(UC_X86_REG_EBX),
                          m.mu.reg_read(UC_X86_REG_EDI)), (skill, job, OBJ), "registers kept")
        return "go" if where == go else "fail" if where == fail else hex(where)

    def test_the_selected_job_at_skill_0_to_5_goes_on(self):
        for game in self.SITES:
            for job in (0, 2, 3, 4) + ((5,) if game == "vv5" else ()):
                for skill in (0, 5):
                    with self.subTest(game=game, job=job, skill=skill):
                        self.assertEqual(self.gate(game, skill, job, selected=job), "go")

    def test_everything_else_is_the_stock_gate(self):
        for game in self.SITES:
            with self.subTest(game=game, case="parenting"):
                self.assertEqual(self.gate(game, 3, 1, selected=1), "fail")
            with self.subTest(game=game, case="not the selected job"):
                self.assertEqual(self.gate(game, 3, 2, selected=4), "fail")
            with self.subTest(game=game, case="roll failed"):
                self.assertEqual(self.gate(game, 3, 2, selected=2, force=FORCE_FAIL), "fail")
            with self.subTest(game=game, case="above 5"):
                self.assertEqual(self.gate(game, 6, 2, selected=4), "go")


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class CatchUpOffers(unittest.TestCase):
    """Items 84 and 101: the Farming case's `cmp byte [game+flag], bl; jne
    skip` -- in catch-up a selected farmer is offered the fruit trip / noni on
    the decision's roll; while you play the stock offer."""

    SITES = {"vv4": (0x463A30, 0x463A38, 0x463A43, 0x171A4), "vv5": (0x46C5CA, 0x46C5D2, 0x46C5D8, 0x17E10)}
    GAME_OBJ = STATE

    def offer(self, game, catching_up, selected, force=FORCE_PASS):
        site, yes, no, flag = self.SITES[game]
        m = world(game, selected=selected, force=force)
        m.w8(self.GAME_OBJ + flag, 1 if catching_up else 0)
        m.leaves[0x425950] = Leaf(0, lambda m, a, c, r: self.GAME_OBJ, name="game")     # what follows the skip (VV5)
        where = run_until(m, site, (yes, no), {UC_X86_REG_EAX: self.GAME_OBJ, UC_X86_REG_EBX: 0,
                                                UC_X86_REG_ESI: OBJ})
        self.assertEqual(m.mu.reg_read(UC_X86_REG_ESI), OBJ)
        return "offer" if where == yes else "skip" if where == no else hex(where)

    def test_live_is_the_stock_offer(self):
        for game in self.SITES:
            for selected in (0, 2):
                with self.subTest(game=game, selected=selected):
                    self.assertEqual(self.offer(game, False, selected), "offer")

    def test_catch_up_offers_it_to_a_farmer_only(self):
        for game in self.SITES:
            with self.subTest(game=game, who="farmer"):
                self.assertEqual(self.offer(game, True, 0), "offer")
            with self.subTest(game=game, who="healer"):
                self.assertEqual(self.offer(game, True, 2), "skip")
            with self.subTest(game=game, who="farmer, roll failed"):
                self.assertEqual(self.offer(game, True, 0, force=FORCE_FAIL), "skip")


@unittest.skipUnless(STOCK_PRESENT, STOCK_ABSENT)
@unittest.skipUnless(TEST_BUILDS_PRESENT, TEST_BUILD_ABSENT)
class LostChildrenSewingHut(unittest.TestCase):
    """Item 30: once the sewing hut is finished, the Building case's examine
    pick sometimes examines it (0x45F7C0(index, 7)); otherwise the stock
    rand(4)."""

    def pick(self, finished, forced, force=FORCE_PASS):
        m = world("vv2", force=force)
        m.w8(STATE + 0x2E790, 1 if finished else 0)
        m.mu.mem_write(m.exports["work_first"]["VvfpWorkFirstStats"] + 16, struct.pack("<i", forced))
        m.leaves[0x45F7C0] = Leaf(2, lambda m, a, c, r: 0, name="examine")
        m.leaves[0x4031A0] = Leaf(1, lambda m, a, c, r: 2, cdecl=True, name="rand")
        m.calls = []
        where = run_until(m, 0x4602B0, (0x4602B7, 0x4602E5),
                          {UC_X86_REG_ESI: VILLAGE, UC_X86_REG_EDI: INDEX, UC_X86_REG_EBX: 1})
        return where, [c[:2] for c in m.calls if c[0] in ("examine", "rand")]

    def test_the_finished_sewing_hut_is_examined(self):
        where, calls = self.pick(True, 4)
        self.assertEqual(where, 0x4602E5)
        self.assertEqual(calls, [("examine", (INDEX, 7))])

    def test_otherwise_the_stock_pick(self):
        for finished, forced, force in ((False, 4, FORCE_PASS), (True, 3, FORCE_PASS), (True, 4, FORCE_FAIL)):
            with self.subTest(finished=finished, forced=forced, force=force):
                where, calls = self.pick(finished, forced, force)
                self.assertEqual(where, 0x4602B7)
                self.assertEqual(calls, [("rand", (4,))])


class RowTests(unittest.TestCase):
    def test_the_rows_are_an_addendum_that_ships_and_pins_the_dll(self):
        import vv_fun_patcher as vfp
        from vv_fun_patcher_gui import default_fun_patch_selection
        sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        ids = {p.id for p in vfp.load_public_fun_patches()}
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("assets/work_first/VVFP Work First.dll", release)
        for game in GAMES:
            with self.subTest(game=game):
                rid = f"{game}_builders_and_healers_work_first"
                m = _manifest(game)
                self.assertIn(rid, ids)
                self.assertTrue(default_fun_patch_selection(rid))
                self.assertEqual(m["dependencies"], [f"{game}_builders_fix_huts"])
                self.assertEqual(m["patches"], [])
                self.assertEqual([c["sha256"] for c in m["companion_files"]], [sha])
                self.assertIn("**Requires Builders Fix Huts When Idle**", m["description"])
                self.assertIn("Villagers practise their selected job", m["description"])
                self.assertIn("Parenting is left to the game and the Birth Control patches", m["description"])
                self.assertNotIn("research-pick", json.dumps(m))
                self.assertIn(f"data/{game}_work_first_feature.json", release)
                self.assertIn(f"`{rid}`", readme)
        source = (ROOT / "native/vvfp_fix_huts/vvfp_fix_huts.c").read_text(encoding="utf-8")
        self.assertIn('vvfp_load_patcher_dll("VVFP Work First.dll")', source)
        self.assertIn('GetProcAddress(work_first_module, "VvfpWorkFirstInstall")', source)

    def test_the_runtime_sites_match_the_dll(self):
        source = (ROOT / "native/vvfp_work_first/vvfp_work_first.c").read_text(encoding="utf-8")
        for game in ("vv1", "vv2", "vv4", "vv5"):
            for site in _manifest(game)["runtime_detours"]:
                with self.subTest(game=game, va=site["va"]):
                    self.assertIn(site["va"][2:].upper() + "U", source.upper().replace("0X", ""))


if __name__ == "__main__":
    unittest.main()
