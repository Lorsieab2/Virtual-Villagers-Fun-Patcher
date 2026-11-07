"""Game Mechanics: the farmers a village needs to bring in what it eats, live and while catching up.

Each game's module src/vv_game_mechanics_farmers_vvN.py holds what was measured from that game's own code: one
`Trip` for each way a farmer brings food in (the berry bush, the field, the sea, ...), with the real-life length
of one trip measured by emulating the stock game's own walking and action code over real map data, the food a
trip credits live and while catching up, the trips a catch-up job turn runs, and the Farming skill check.  The
Vital statistics' "Farmers needed" lines (src/vv_game_mechanics_life.py) are worked out from them here.

TIME AND UNITS.  An age unit is 60 x the speed value real-life seconds (3, 6 or 10 real-life minutes on Fast,
Normal or Slow).  A trip's length is real-life seconds at the named speed.  Catch-up has no trip length: each
counted age unit's job turns run at once (src/vv_game_mechanics_catchup.py).
"""
from __future__ import annotations

import importlib
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Trip:
    key: str                                   # the Context.trips name it pairs with ("berry picks")
    job: str                                   # how a villager is set to it, in the game's words
    live_seconds: dict[int, float]             # speed value -> real-life seconds of one steady trip
    live_span: dict[int, tuple[float, float]]  # speed value -> the shortest and longest trip measured
    live_food: dict[int, float] | None = None  # food a paying live trip credits (before Food Mastery); None: Context
    catch_up_food: float | None = None         # food a paying catch-up trip credits; None: as live (Context)
    catch_up_trips_per_turn: float = 1.0       # trips one catch-up job turn of a farmer set to it runs
    success_offset: int | None = None          # a trip pays (Farming + offset) times in 100; None: always
    live_words: str = ""                       # how the trip was measured: what it includes, its clock
    catch_up_words: str = ""                   # the catch-up rule, with addresses
    verified: str = "running"                  # gm.RUNNING or gm.CODE
    extra: tuple[str, ...] = field(default_factory=tuple)   # further measured facts, one line each


def game_module(game: int):
    """The game's measured module, or None."""
    try:
        return importlib.import_module(f"vv_game_mechanics_farmers_vv{game}")
    except ImportError:
        return None


def game_trips(game: int) -> tuple[int, tuple[Trip, ...]]:
    """(job turns an age unit while catching up, the game's trips); (0, ()) when none are measured."""
    module = game_module(game)
    if module is None:
        return 0, ()
    return int(module.TURNS_PER_UNIT), tuple(module.TRIPS)


def turn_trips(game: int, trip: Trip, farming: int, food: int) -> float:
    """Trips at `trip`'s source one catch-up job turn runs for a farmer set to it, at this Farming skill and food
    store, by the game's own rule (each module's measured helper)."""
    module = game_module(game)
    if module is None or not trip.catch_up_trips_per_turn:
        return 0.0
    if hasattr(module, "catch_up_trips"):              # The Secret City, New Believers: the kept site or task first
        return float(module.catch_up_trips(farming, food))
    if hasattr(module, "task_trips_per_turn"):         # The Tree of Life: the player-task gate first
        return float(module.task_trips_per_turn(farming, food=food))
    return float(module.farming_chosen(farming))       # A New Home, The Lost Children: the job chooser alone


def live_cycle(game: int, trip: Trip, farming: int) -> float | None:
    """Real-life seconds per paying trip for a farmer left to the game's own scheduler (measured), or None."""
    module = game_module(game)
    cycle = getattr(module, "LIVE_CYCLE", {}).get(trip.key, {}) if module is not None else {}
    return cycle.get(farming) or None


def delivered(game: int, trip: Trip) -> float:
    """The share of catch-up trips that pay once the Farming check passes (The Secret City's honey: 11 in 12)."""
    module = game_module(game)
    return float(getattr(module, "CATCH_UP_DELIVERED", {}).get(trip.key, 1.0)) if module is not None else 1.0


def pays(trip: Trip, farming: int) -> float:
    """The share of trips that bring food at this Farming skill."""
    if trip.success_offset is None:
        return 1.0
    return max(0.0, min(100, farming + trip.success_offset)) / 100.0


def live_food_unit(trip: Trip, food: float, speed: int, unit: float, farming: int) -> float | None:
    """Food one farmer brings an age unit of live play, on trips back to back."""
    seconds = trip.live_seconds.get(speed)
    if not seconds:
        return None
    return unit / seconds * pays(trip, farming) * food


def catch_up_food_unit(trip: Trip, food: float, turns: int, farming: int) -> float:
    """Food one farmer brings each counted age unit while catching up (the job turns' trips)."""
    return turns * trip.catch_up_trips_per_turn * pays(trip, farming) * food


def boosted(amount: float, mastery: float) -> float:
    """A food gain after Food Mastery, as the game rounds it (The Tree of Life 0x41D920, New Believers 0x41EB40):
    level 2 adds half, rounded down; level 3 doubles.  Only a single gain (an int) is rounded: a float is an
    average over several outcomes (The Tree of Life's net: fish or Golden Fish), each rounded by its caller."""
    if mastery == 1.5 and isinstance(amount, int):
        return amount + amount // 2
    return amount * mastery


def needed(eaten: float, brought: float | None) -> int | None:
    """Whole farmers to bring `eaten` when one brings `brought` (the same time span)."""
    if not brought or brought <= 0:
        return None
    return max(0, math.ceil(eaten / brought - 1e-9))


FARMING_SHOWN = 50                 # the Farming skill the page's figures are for
GROUP = "Food earned"


@dataclass(frozen=True)
class Supply:
    """What one farmer set to a source brings, live and while catching up, and the farmers needed."""
    trip: Trip
    live_food: float               # food a paying live trip credits at the save's speed (Food Mastery applied)
    cycle: float | None            # real-life seconds per paying live trip (the game's scheduler)
    live_hour: float | None        # food one farmer brings a real-life hour of live play
    live_needed: int | None
    catch_up_food: float           # food a paying catch-up trip credits (Food Mastery applied)
    turn_trips: float              # trips a job turn runs
    pays: float                    # the share of trips whose Farming check passes
    share: float                   # the share of those that pay (The Secret City's honey: 11 in 12)
    catch_up_unit: float           # food one farmer brings each counted age unit
    catch_up_needed: int | None


def supplies(game: int, trips_food: dict[str, float], speed: int, unit: float, mastery: float, food_store: int,
             eaten_unit: float, farming: int = FARMING_SHOWN) -> tuple[int, list[Supply]]:
    """(job turns an age unit, each source's Supply) for a village that eats `eaten_unit` food an age unit, with
    the page's food a trip (`trips_food`, Context.trips; a source at 0 is not open) at `speed`, an age unit of
    `unit` real-life seconds."""
    turns, trips = game_trips(game)
    out = []
    eaten_hour = eaten_unit * 3600.0 / unit
    for trip in trips:
        base = trips_food.get(trip.key)
        if not base or base <= 0:
            continue
        live = float(boosted((trip.live_food or {}).get(speed, base), mastery))
        cycle = live_cycle(game, trip, farming)
        hour = 3600.0 / cycle * live if cycle else None
        caught = float(boosted(trip.catch_up_food if trip.catch_up_food is not None else base, mastery))
        per_turn = turn_trips(game, trip, farming, food_store)
        share = delivered(game, trip)
        paying = pays(trip, farming)
        brought = turns * per_turn * paying * share * caught
        out.append(Supply(trip, live, cycle, hour, needed(eaten_hour, hour), caught, per_turn, paying, share,
                          brought, needed(eaten_unit, brought)))
    return turns, out


def _seconds(value: float) -> str:
    return f"{value:,.1f}".rstrip("0").rstrip(".")


def rule_facts(game: int, basis: str = "running") -> list[tuple[str, str, bool]]:
    """The measured trips as (text, status, sub-bullet), for the Food earned group: one line for each source, its
    steps and clock, the catch-up rule and the further facts under it."""
    turns, trips = game_trips(game)
    if not trips:
        return []
    out: list[tuple[str, str, bool]] = [(
        "Farming trips, measured by running the stock game's own villager update frame by frame (33 ms a frame, "
        "the game's 30 frames a second) over its real map: each trip's length is real-life time and the same at "
        "Fast, Normal and Slow; the food a trip brings is under each source. While catching up a farming job turn "
        f"runs a whole trip at once: {turns} job turns each counted age unit for each working adult.", basis, False)]
    for trip in trips:
        lo, hi = trip.live_span.get(6, (0.0, 0.0))
        cycle = live_cycle(game, trip, 100), live_cycle(game, trip, 50), live_cycle(game, trip, 20)
        text = (f"{trip.key[0].upper() + trip.key[1:]}: one whole trip, from the food bin and back to it, takes "
                f"{_seconds(trip.live_seconds.get(6, 0.0))} real-life seconds on average ({_seconds(lo)} to "
                f"{_seconds(hi)}; real time, the same at every speed) for an adult who passes the Farming check")
        if trip.success_offset is not None:
            text += f", which passes (Farming + {trip.success_offset}) times in 100"
        text += "."
        if all(cycle):
            text += (f" A farmer left to the game's own choices brings food once every {_seconds(cycle[0])} real-life "
                     f"seconds at Farming 100, {_seconds(cycle[1])} at 50 and {_seconds(cycle[2])} at 20 (failed "
                     "checks, rests and other jobs included).")
        text += f" Set to it: {trip.job[0].lower() + trip.job[1:]}."
        out.append((text, basis, False))          # measured by running the game's own code (gm.RUNNING)
        for words in (trip.live_words, trip.catch_up_words, *trip.extra):
            # The scheduler's figures are in the line above already.
            if words and not words.startswith("Live, with the game's own scheduler"):
                out.append((words, trip.verified, True))
    return out
