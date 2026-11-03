"""VV2 Fix Vanilla Bugs, "VVFP Stuck Walks.dll": the villager stuck walking to the herb in the south-east sand.

Runs the stock The Lost Children exe in unicorn with the companion's TEST build mapped and its detour written
where VvfpStartup writes it (tests/vv2_stuck_walks_native.py); every instruction of the walk, the band handler,
the companion's handler and the scheduler is machine code.

  * stock: the herb study from the stalled starts never ends (the band waypoint is queued again forever);
  * with the companion: the same starts reach the herb, through an alternate standing point;
  * ordinary walks (starts the stock redirect gets past): identical to stock, frame for frame;
  * with Improved Pathfinding installed too (its flood and descent detours): the same, so the two compose;
  * no alternate left: the villager gives up -- the step queue is emptied and the scheduler runs again --
    and neither the companion nor the stock clear writes the record's +0x40 / +0x44 (+0x44 keeps its value).
"""
import math
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
pytest.importorskip("unicorn")
pytest.importorskip("pefile")
import farmers_emulation_vv2 as fe  # noqa: E402

if not (fe.STOCK.is_file() and fe.GROWN.is_file()):
    pytest.skip("needs the stock VV2 exe and the grown village save copy (research/, not committed)",
                allow_module_level=True)
from vv2_stuck_walks_native import PATH_DLL, STUCK_DLL, NativeRun  # noqa: E402
from vv2_stuck_villager_emulation import HERB6, queue  # noqa: E402

if not (STUCK_DLL.is_file() and PATH_DLL.is_file()):
    pytest.skip("test builds are not in the release source archive (tests/test_dlls)", allow_module_level=True)

STALLED = [(1500, 1000), (1350, 1050), (1540, 1280), (1420, 1280), (1480, 1280)]
ORDINARY = [(1140, 1037), (1300, 1100), (1500, 1100), (1450, 1200), (1540, 1210)]


def test_stock_loops_with_the_companion_absent():
    run = NativeRun(STALLED[0], stuck_walks=False)
    assert run.go(5000) is None
    assert math.dist(run.v.feet(), HERB6) > 100
    assert len(run.stock_hits) >= 40 and queue(run.v, 1)[0][0] == 3


@pytest.mark.parametrize("pathfinding", [False, True])
@pytest.mark.parametrize("start", STALLED)
def test_stalled_starts_reach_the_herb(start, pathfinding):
    run = NativeRun(start, pathfinding=pathfinding, carried=0x1A)
    assert run.go(5000) is not None                      # the scheduler runs again: the study ended
    assert math.dist(run.v.feet(), HERB6) <= 30
    stats = run.stats()
    assert stats["loops"] >= 1 and stats["alternates"] >= 1 and stats["give_ups"] == 0


@pytest.mark.parametrize("pathfinding", [False, True])
@pytest.mark.parametrize("start", ORDINARY)
def test_ordinary_walks_unchanged_frame_for_frame(start, pathfinding):
    stock = NativeRun(start, stuck_walks=False, pathfinding=pathfinding)
    fixed = NativeRun(start, pathfinding=pathfinding)
    assert stock.go(5000) == fixed.go(5000) is not None
    assert stock.trace == fixed.trace
    assert fixed.stats()["loops"] == 0 and fixed.stats()["alternates"] == 0


def test_no_alternate_gives_up_and_keeps_what_the_villager_holds():
    from unicorn import UC_HOOK_MEM_WRITE
    from unicorn.x86_const import UC_X86_REG_EIP
    run = NativeRun(STALLED[0], block_alternates=True)
    rec = run.v.rec(0)
    run.v.w32(rec + 0x44, 7)
    writers = []
    run.v.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc, *_: writers.append(uc.reg_read(UC_X86_REG_EIP)),
                      begin=rec + 0x40, end=rec + 0x47)
    assert run.go(6000) is not None                      # the scheduler picks a new job
    stats = run.stats()
    assert stats["give_ups"] == 1 and stats["alternates"] == 0
    assert run.v.r32(rec + 0x44) == 7
    # +0x40 is written by the walk's own step starter (0x44D833) as always; never by the give-up: neither
    # the companion nor the stock clear 0x4492A0 writes +0x40 / +0x44.
    assert not [w for w in writers if 0x10000000 <= w < 0x10100000 or 0x4492A0 <= w < 0x4492E9]


def test_a_finished_rescue_leaves_no_history_for_the_next_trip_to_the_same_herb():
    """Rescued, the study done, the villager is sent to the same herb again from a stalled start (twice more):
    each trip is a new walk and is rescued on its own, with no give-up (the first rescue's tried points and
    looping flag do not carry over)."""
    from vv2_stuck_villager_emulation import HERB6_JOB
    run = NativeRun(STALLED[0], carried=0x1A)
    assert run.go(5000) is not None
    assert math.dist(run.v.feet(), HERB6) <= 30
    v = run.v
    for start in (STALLED[1], STALLED[2]):
        before = run.stats()
        v.t += 120.0                                     # the study and the time before the next trip
        v.villager(skills={"healing": 30}, preference=0, health=100, feet=start)   # a fresh record, as at the start
        run.ai.clear()
        v.call(HERB6_JOB, fe.MGR, 0)
        assert run.go(5000) is not None
        assert math.dist(v.feet(), HERB6) <= 30
        after = run.stats()
        assert after["loops"] == before["loops"] + 1 and after["give_ups"] == 0
        assert after["alternates"] > before["alternates"]


def test_the_site_is_the_handlers_entry_and_jumps_to_the_companion():
    run = NativeRun(ORDINARY[0])
    site = bytes(run.v.uc.mem_read(0x44FCB0, 5))
    assert site[0] == 0xE9
    target = (0x44FCB5 + struct.unpack("<i", site[1:])[0]) & 0xFFFFFFFF
    assert 0x10000000 <= target < 0x10100000
