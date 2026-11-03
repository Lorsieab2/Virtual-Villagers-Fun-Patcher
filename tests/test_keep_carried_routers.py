"""The Secret City, The Tree of Life and New Believers, Fix Vanilla Bugs, "VVFP Keep Carried.dll": when the game's
router says "no route" to the goal of a walk a villager makes while holding something, the villager walks to the
nearest point the router CAN route to (rings of 8 to 64 pixels round the goal) and the job's release step follows.

Runs each stock exe in unicorn on the game's real map (research/game-data/vvN, never committed: the tests skip
without it) with the companion's TEST build mapped and its router-call site written where VvfpStartup writes it
(tests/keep_carried_native.py).  Villager 0 holds a mushroom, starts at a free point, walks to a goal the router
cannot route to, and the release step (the game's own item step, item -1) is queued behind the walk.

  * stock: the router fails, the clear 0x460F70 / 0x468C60 / 0x473440 empties the queue and releases the item where
    the villager stands -- it is dropped (and nothing is credited);
  * with the companion: the villager walks to the alternate point, the release step runs there (VV3: in the food
    area, and the food is credited; VV4: inside the food bin);
  * everything else is stock: a routable goal gives the same trace frame for frame (the companion's only act is the
    game's own router call), a villager holding nothing or the baby, or a walk with no step behind it, give up as
    before.
"""
import math
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
pytest.importorskip("unicorn")
pytest.importorskip("pefile")

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
DATA = ROOT / "research" / "game-data"
NEEDS = {
    3: [STOCK / "Virtual Villagers - The Secret City.exe", DATA / "vv3" / "cmap.dat", DATA / "vv3" / "wpts.dat"],
    4: [STOCK / "Virtual Villagers - The Tree of Life.exe", DATA / "vv4" / "cmap.dat"],
    5: [STOCK / "Virtual Villagers - New Believers.exe"] + [DATA / "vv5" / n for n in
                                                           ("lcmap.dat", "wpts.dat", "anims.dat", "animpts.dat")],
}
from keep_carried_native import KEEP_DLL, Vv3Run, Vv4Run, Vv5Run, stats  # noqa: E402

if not KEEP_DLL.is_file():
    pytest.skip("test builds are not in the release source archive (tests/test_dlls)", allow_module_level=True)

# game: (runner, item, start, goal the router cannot route to, a routable goal, how far the alternate may be)
CASES = {
    3: (Vv3Run, 0x64, (1300, 1300), (1120, 1248), (1200, 1264), 40),
    4: (Vv4Run, 0x76, (1300, 1300), (1124, 1248), (1116, 1260), 40),
    5: (Vv5Run, 0x80, (1411, 1175), (1110, 1170), (1380, 1175), 70),
}


def case(game):
    if not all(p.is_file() for p in NEEDS[game]):
        pytest.skip("needs the stock exe and the game's map data (research/, not committed)")
    return CASES[game]


@pytest.mark.parametrize("game", [3, 4, 5])
def test_stock_drops_the_item_where_the_router_gave_up(game):
    run_cls, item, start, goal, _, reach = case(game)
    run = run_cls(start, goal, item=item, keep=False)
    assert run.go() is not None
    assert run.item() == -1 and len(run.released) == 1
    assert math.dist(run.feet(), goal) > reach           # released short of the goal, where the walk gave up


@pytest.mark.parametrize("game", [3, 4, 5])
def test_with_the_companion_the_villager_walks_to_the_alternate_point_and_releases_there(game):
    run_cls, item, start, goal, _, reach = case(game)
    run = run_cls(start, goal, item=item)
    assert run.go() is not None
    assert math.dist(run.feet(), goal) <= reach
    assert run.item() == -1 and len(run.released) == 1
    assert run.released[0][1] is not None and math.dist(run.released[0][1], goal) <= reach   # released THERE
    s = stats(run.v, run.ex)
    assert s["kept"] == 1 and s["give_ups"] == 0


def test_vv3_the_mushroom_is_credited_in_the_food_area():
    run_cls, item, start, goal, _, _ = case(3)
    stock = run_cls(start, goal, item=item, keep=False)
    stock.go()
    assert not stock.v.credits
    run = run_cls(start, goal, item=item)
    run.go()
    assert [amount for _, amount, _ in run.v.credits] == [6]
    assert run.v.region(*run.feet()) == 0xE            # the food area


def test_vv4_the_release_happens_inside_the_food_bin():
    run_cls, item, start, goal, _, _ = case(4)
    run = run_cls(start, goal, item=item)
    run.go()
    x, y = run.released[0][1]
    assert 1096 <= x <= 1127 and 1248 <= y <= 1271     # the bin: map area 8


@pytest.mark.parametrize("game", [3, 4, 5])
def test_a_routable_goal_is_identical_frame_for_frame(game):
    run_cls, item, start, _, ordinary, _ = case(game)
    stock = run_cls(start, ordinary, item=item, keep=False)
    fixed = run_cls(start, ordinary, item=item)
    assert stock.go() == fixed.go() is not None
    assert stock.trace == fixed.trace and stock.released == fixed.released
    assert stats(fixed.v, fixed.ex)["alternates"] == 0


@pytest.mark.parametrize("game", [3, 4, 5])
def test_nothing_held_or_the_baby_or_no_step_behind_is_the_stock_give_up(game):
    run_cls, item, start, goal, _, _ = case(game)
    for kw in (dict(item=-1), dict(item=3), dict(item=item, tail=False)):
        stock = run_cls(start, goal, keep=False, **kw)
        fixed = run_cls(start, goal, **kw)
        assert stock.go() == fixed.go() is not None
        assert stock.trace == fixed.trace
        assert stats(fixed.v, fixed.ex)["alternates"] == 0


@pytest.mark.parametrize("game", [3, 4, 5])
def test_the_site_is_the_routers_call_and_jumps_to_the_companion(game):
    run_cls, item, start, goal, _, _ = case(game)
    run = run_cls(start, goal, item=item)
    code = bytes(run.v.uc.mem_read(run.SITE, 5))
    assert code[0] == 0xE8
    target = (run.SITE + 5 + struct.unpack("<i", code[1:])[0]) & 0xFFFFFFFF
    assert run.BASE <= target < run.BASE + 0x100000
