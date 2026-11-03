"""VV2 stuck villager (herb 6 study): the stock exe loops; the scratch fix finishes; ordinary walks unchanged."""
import math
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
from vv2_stuck_villager_emulation import HERB6, Run, queue  # noqa: E402

STALLED = [(1500, 1000), (1350, 1050), (1540, 1280)]
ORDINARY = [(1140, 1037), (1300, 1100), (1500, 1100), (1450, 1200), (1540, 1210)]


@pytest.mark.parametrize("start", STALLED[:1])
def test_stock_loops_on_the_band_waypoint(start):
    run = Run(start)
    run.go(5000, stop_on_ai=False)
    assert not run.ai
    assert math.dist(run.v.feet(), HERB6) > 100
    assert len(run.hits) >= 40 and {h[4] for h in run.hits} >= {"0x45eb1f"}
    assert queue(run.v, 1)[0][0] == 3


@pytest.mark.parametrize("start", STALLED)
def test_fix_finishes_the_study(start):
    run = Run(start, fix=True)
    assert run.go(5000) is not None
    assert math.dist(run.v.feet(), HERB6) <= 30


@pytest.mark.parametrize("start", ORDINARY)
def test_ordinary_walks_unchanged_step_for_step(start):
    a, b = Run(start), Run(start, fix=True)
    assert a.go(5000) == b.go(5000)
    assert a.trace == b.trace and not b.fixes


def test_no_route_gives_up_and_keeps_the_carried_value():
    run = Run((1500, 1000), fix=True, block_alternates=True)
    run.v.w32(run.v.rec(0) + 0x44, 7)
    run.go(6000)
    assert run.gave_up and run.v.r32(run.v.rec(0) + 0x44) == 7
    assert queue(run.v, 1)[0][0] == 0
    for _ in range(40):
        run.v.step_frame()
    assert run.ai                      # the scheduler runs again: the villager picks a new job
