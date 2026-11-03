"""A New Home, Fix Vanilla Bugs, "VVFP Keep Carried.dll": a villager whose walk gives up keeps what it carries.

Runs the stock exe in unicorn with the companion's TEST build mapped and its three sites written where VvfpStartup
writes them (tests/keep_carried_native.py).  The scenario is the one the stock game loses: villager 0 carries fish
(record +0x3C = 8) from the north of the island towards a point south of the concave corner round (1430, 710); the
fish job's tail (wait, step 8, release 0xD, 0xE, 0x13, 5) is queued behind the walk, so a finished delivery pays.

  * stock: the walk gives up after fifteen nudges (or leaves the map), the queue is cleared, the fish is dropped and
    nothing is paid;
  * with the companion: the villager walks a route round the obstacle, delivers, and the food is paid;
  * everything else is stock: an ordinary walk is identical frame for frame (with and without Improved Pathfinding),
    a villager holding nothing gives up as before, and when no route exists the stock give-up runs.
"""
import math
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
pytest.importorskip("unicorn")
pytest.importorskip("pefile")
import farmers_emulation_vv1 as fe1  # noqa: E402

if not fe1.STOCK.is_file():
    pytest.skip("needs the stock VV1 exe (research/, not committed)", allow_module_level=True)
from keep_carried_native import KEEP_DLL, PATH_DLL, Vv1Run, stats  # noqa: E402

if not (KEEP_DLL.is_file() and PATH_DLL.is_file()):
    pytest.skip("test builds are not in the release source archive (tests/test_dlls)", allow_module_level=True)

CORNER = ((1335, 605), (1365, 1245))
# Starts and targets where the stock game loses the fish: the first four give up after fifteen nudges, the rest
# are driven off the east edge of the map by the nudges' waypoints (the walk's edge clear).
BLOCKED = [((1344, 604), (1371, 1297)), ((1433, 570), (1388, 1281)), ((1305, 516), (1497, 1223)),
           ((1346, 546), (1367, 1266)),
           ((1371, 551), (1413, 1077)), ((1363, 484), (1474, 1187)), ((1428, 533), (1496, 1277)),
           ((1330, 542), (1495, 1070)), ((1442, 619), (1441, 1265))]
ORDINARY = [((1335, 605), (1170, 1209)), ((900, 800), (1170, 1209)), ((1300, 1000), (1190, 1214))]


def test_stock_drops_the_fish_and_pays_nothing():
    run = Vv1Run(*CORNER, keep=False)
    assert run.go() is not None
    assert run.item() == 0x13 and not run.v.rewards and not run.v.food_log
    assert math.dist(run.v.feet(), CORNER[1]) > 300           # it gave up far from the bin


def test_with_the_companion_the_fish_is_delivered_and_paid():
    run = Vv1Run(*CORNER)
    assert run.go() is not None
    assert math.dist(run.v.feet(), CORNER[1]) <= 6
    assert [amount for _, amount in run.v.food_log] == [55] and len(run.v.rewards) == 1
    s = stats(run.v, run.ex)
    assert s["kept"] == 1 and s["give_ups"] == 0


@pytest.mark.parametrize("start,target", BLOCKED)
def test_every_blocked_start_loses_in_stock_and_delivers_with_the_companion(start, target):
    stock = Vv1Run(start, target, keep=False)
    stock.go(9000)
    assert not stock.v.rewards and stock.item() == 0x13
    run = Vv1Run(start, target)
    assert run.go(9000) is not None
    assert len(run.v.rewards) == 1 and run.v.food_log
    assert math.dist(run.v.feet(), target) <= 8
    assert stats(run.v, run.ex)["give_ups"] == 0


@pytest.mark.parametrize("pathfinding", [False, True])
@pytest.mark.parametrize("start,target", ORDINARY)
def test_ordinary_walks_are_identical_frame_for_frame(start, target, pathfinding):
    stock = Vv1Run(start, target, keep=False, pathfinding=pathfinding)
    fixed = Vv1Run(start, target, pathfinding=pathfinding)
    assert stock.go() == fixed.go() is not None
    assert stock.trace == fixed.trace
    assert stats(fixed.v, fixed.ex)["calls"] == 0 and len(fixed.v.rewards) == 1


def test_with_improved_pathfinding_installed_the_two_compose():
    alone = Vv1Run(*CORNER, keep=False, pathfinding=True)
    both = Vv1Run(*CORNER, pathfinding=True)
    assert alone.go() == both.go() is not None
    assert alone.trace == both.trace and len(both.v.rewards) == 1       # pathfinding routes it first
    assert stats(both.v, both.ex)["calls"] == 0


def test_a_villager_holding_nothing_gives_up_exactly_as_before():
    stock = Vv1Run(*CORNER, keep=False, item=0x13)
    fixed = Vv1Run(*CORNER, item=0x13)
    assert stock.go() == fixed.go() is not None
    assert stock.trace == fixed.trace and not fixed.v.rewards
    assert stats(fixed.v, fixed.ex)["alternates"] == 0


def test_the_baby_is_never_touched():
    stock = Vv1Run(*CORNER, keep=False, item=3)
    fixed = Vv1Run(*CORNER, item=3)
    assert stock.go() == fixed.go() is not None and stock.trace == fixed.trace


def test_no_route_gives_up_as_the_stock_game_does():
    # Every cell the companion reads answers "blocked" (only its own reads): no route, so the stock clear runs.
    stock = Vv1Run(*CORNER, keep=False)
    fixed = Vv1Run(*CORNER, block_alternates=True)
    assert stock.go() == fixed.go() is not None
    assert stock.trace == fixed.trace and fixed.item() == 0x13 and not fixed.v.rewards
    s = stats(fixed.v, fixed.ex)
    assert s["give_ups"] == 1 and s["alternates"] == 0


def test_the_three_sites_are_calls_to_the_companion():
    run = Vv1Run(*CORNER)
    for site, _ in Vv1Run.SITES:
        code = bytes(run.v.uc.mem_read(site, 5))
        assert code[0] == 0xE8
        target = (site + 5 + struct.unpack("<i", code[1:])[0]) & 0xFFFFFFFF
        assert 0x10000000 <= target < 0x10100000
