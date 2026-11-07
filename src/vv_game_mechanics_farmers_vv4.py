"""The Tree of Life (VV4): what one farmer brings in, live and while catching up -- measured from the stock exe.

Every number below was measured by running the stock executable's own code in unicorn over the game's own map
(tests/farmers_emulation_vv4.py; re-measured by tests/test_game_mechanics_farmers_vv4.py).

WHO FARMS, AND WHERE.  Dropping a villager on the blackberry bush starts "Harvesting blackberries" (action 99,
0x451C30) and gives it the task 3 (record +0x1C54, 0x46F8DC); dropping one on the fishing nets (once Fishing Nets is
solved) starts "Retrieving a fish" (action 129, 0x4331D0) with the task 0x1C (0x433553); dropping one on the fruit
(once the Cooking Pit is restored, puzzle 6) starts "Attempting to retrieve fruit" (action 100, 0x4343A0 -> 101..104,
0x435970) and sets no task.  Nothing in the stock game sets the task 2 (the fruit task the player-task code 0x46364E
and the Cooking Pit bonus test); it can only be written into a save.  A villager with a task asks for it again each
time it is idle, through the player-task gate 0x4634D0 (see TASK_GATE); a villager whose own choice is Farming
(the chooser 0x461CC0) goes to the dispatcher 0x4639B0, which offers the bush (more than 3 berries), the fruit
(the Cooking Pit restored, and never while catching up, 0x463A30) and the nets (Fishing Nets) equally (rand(n),
0x463A62).  When the dispatcher sends a villager who dislikes berries, fruit, or fish / the ocean / swimming to
that source it runs away 60 times in 100 (0x463BA8, 0x463B3D, 0x463ACF) and loses its task; the task path
(0x4634D0) has no such check.

ONE TRIP.  Each action queues its steps (the builders 0x468EE0..0x469F30 append 0x58-byte steps at record + 0) and
the villager's per-frame update 0x465BD0 plays them.  The Farming check is the skill check 0x462A80 (step 9): it
passes when rand(100) <= Farming + 33 (Farming + 48 / + 63 at Learning level 2 / 3, 0x462AD5; liking learning makes
the base 66, disliking it 16), i.e. (Farming + 34) times in 100 at Learning 1; a failure clears the queue and starts
"Shaking head" (action 32), so the trip ends with nothing.  The food is credited by a job event (0x4642F0) at the
food bin, through the food writer 0x41D920 (Food Mastery: x1.5 rounded down at level 2, x2 at level 3).  See each
Trip's live_words.  During the tutorial, until its "Great job!" tip (0x2B2) has been shown, a failed Farming check
passes once the "Darn!" tip (0x2D2) has been shown (0x462B27..0x462B5E); the figures here are for a village past it.

LIVE TRIP TIME (real-life seconds, the same at Fast, Normal and Slow).  Measured by running 0x465BD0 frame by frame
with the game's own frame time: the frame limiter 0x40942B..0x409455 holds each frame to 1000 // 30 = 33 ms (30
frames a second: the settings' virtual 0x403020 passed to 0x408150 at 0x402CB8).  A walk (step 3, 0x45E2C0 /
0x461120) moves the villager its speed / 100 pixels a frame, split between x and y in proportion (0x45E6F0; re-aimed
every 10 frames), and on entering each 8-pixel map cell asks the path search 0x4706B0 / 0x4705D0 (on the map grid
0x6C4658 loaded from cmap.dat by 0x46C150) for waypoints (step 6); a walk whose target cell is blocked, or that finds
no path, clears the queue.  An adult walks at 100 (1 pixel a frame, 30.3 pixels a real-life second); one who likes
running at 300 (0x45E2EE), and so does every child who does not dislike it; one who dislikes running, or an elder
(age units >= 840 + 160 x Medicine level: 50, 58 or 66 years, 0x465EB0), at 40 (0x45E325).  The waits (steps 2,
10, 14) end on the game clock 0x403750: whole real-life seconds (time() minus an epoch), a wait of d seconds ending
on the first frame after the clock passes its start + d (0x46A000).  Nothing in the update, the walk or the waits
reads the speed value: the scene update 0x43F750 only stops calling the villagers (0x466420, at 0x43FF8A) while it
is 999 (paused).  The emulation gave identical trips, frame for frame, at speed 3, 6 and 10.  A trip is timed from
the frame its action starts (the villager standing at the food bin where its last trip ended) to the frame the food
is credited; TRIP_SAMPLES says what was measured.

Stubbed in the emulation: rand(N) 0x4036D0, the clock 0x403750, the singleton getters 0x41FE70 / 0x44DA20 and the
scene's mouse hotspot rebuild 0x41CA50 (tests/farmers_emulation_vv4.py says why each is safe).  Not emulated: the
framework's own frame timing outside the exe (SDL_Delay's accuracy), so a frame is taken as exactly 33 ms; a
computer that cannot draw 30 frames a second walks the villagers more slowly in real time (the waits are unchanged).

CATCH-UP.  For each counted age unit the life tick 0x468430 (repeated until no one is behind, 0x468B09 -> 0x468440)
charges each villager's meal (0x46848B..0x468512: 2 food above 500; at 500 or less on rand(100) < 50 only, else
none and on rand(100) < 30 1 health lost; 2 more on rand(100) <= 75 at 8,000 food or more or on Hard, never on
Easy) and, for every unit but the last 2, gives each villager aged 14 or more (280 age units, by the age shown),
not sick and not pregnant, 4 job turns 0x465750 (0x468A24..0x468A75, the catch-up flag game + 0x171A4 set).  A job
turn (health 20 or more, 0x46577B) asks the chooser 0x461CC0, then a player task through the gate 0x4634D0, then
(at 250 food or less, Farming 20 or more) farming, else the chooser's job through the dispatcher 0x4639B0; the
step resolver 0x464FA0 runs the queue at once: walks become instant moves (step 3 -> 0x45ECB0), the skill check
(step 9) and the carry and reward steps (17, 18, 19 -> 0x46A4D0) run as live, every wait and pose is skipped.  So a
farming turn is one trip and pays what a live trip pays.  Then the Cooking Pit bonus (FRUITWELLS).
"""
from __future__ import annotations

from vv_game_mechanics_farmers import Trip

TURNS_PER_UNIT = 4          # job turns a counted age unit (0x468A60..0x468A75), for all but the last 2 units

# The job chooser 0x461CC0 for a villager whose preference is Farming (+0x1C70 = 0): 15 in 100 nothing (0x461CD4;
# a villager who likes work skips this, one who dislikes it refuses 70 in 100 more, 0x461D15); then the best skill,
# each considered on rand(100) > 15 (Farming first, 0x461D28; Parenting only for a Parenting preference); a choice
# other than Farming switches to the preference on rand(100) <= 85 (0x461E4A); then the job happens only when the
# chosen skill is more than 5 and rand(100) < skill + 40 (0x461E69..0x461E7B).  With Farming the villager's highest
# skill: 0.85 x (0.84 + 0.16 x 0.86) = 0.83096 of choices are Farming, times min(1, (Farming + 40) / 100).
FARMING_CHOSEN = 0.83096


def farming_chosen(farming: int) -> float:
    """Share of job choices (live: the scheduler's; catch-up: the job turns') that choose Farming, for a villager
    whose preference is Farming and whose highest skill is Farming."""
    if farming <= 5:
        return 0.0
    return FARMING_CHOSEN * min(1.0, (farming + 40) / 100.0)


# The player-task gate 0x4634D0 (live and catch-up): a villager who likes work always does its task; otherwise it
# refuses on rand(100) < 20 (0x4634F7), or on rand(100) < 40 (0x463506) when the store holds 8,000 food or more or
# it dislikes work.  A refused task falls back to the chooser's job (0x4657E3 / 0x46599D).
TASK_GATE = {"likes work": 1.0, "neutral": 0.8, "neutral, 8,000 food or more": 0.48, "dislikes work": 0.48}


def task_trips_per_turn(farming: int, *, nets: bool = True, food: int = 1000, work: str = "neutral") -> float:
    """Trips at its own source a catch-up job turn gives a Farming-preference farmer dropped on the bush or the
    nets: the gate, or else the chooser's Farming and the dispatcher's pick of that source (the bush and the nets,
    1 in 2 while both are offered; the fruit never)."""
    gate = TASK_GATE["likes work"] if work == "likes" else (
        0.48 if work == "dislikes" or food >= 8000 else 0.8)
    return gate + (1 - gate) * farming_chosen(farming) * (0.5 if nets else 1.0)


# The Cooking Pit bonus, catch-up only (0x468A7A..0x468AC5): once the Cooking Pit is restored (puzzle 6, 0x468A81),
# after a counted unit's 4 job turns each villager who had them (aged 14 or more, not sick, not pregnant, all units
# but the last 2; its health is not checked here) adds 5 food x Food Mastery (0x468AB2) if its task is 2 (never set
# by the stock game), else on rand(100) < Farming - 25 (0x468A90..0x468AA9: (Farming - 25) times in 100, never at 25
# or less, 75 at Farming 100); then a Farming skill check 0x462A80 (practice only: the food is already added).
FRUITWELLS = {"food": {1: 5, 2: 7, 3: 10},          # by Food Mastery level (0x41D92C..0x41D94D)
              "chance_offset": -25,                  # pays on rand(100) < Farming - 25
              "task_always": 2,                      # the task that always pays (not set by the stock game)
              "per": "counted age unit, all but the last 2, per villager aged 14+ not sick or pregnant"}


def fruitwells_food_unit(farming: int, mastery: int = 1) -> float:
    """Food the Cooking Pit bonus adds for one villager each counted age unit (no task 2)."""
    return FRUITWELLS["food"][mastery] * max(0, min(100, farming - 25)) / 100.0


# The dispatcher 0x4639B0, job 0 (Farming), as emulated:
SOURCE_RULES = (
    "Live: the bush while it holds more than 3 berries, the fruit once the Cooking Pit is restored, the nets once "
    "Fishing Nets is solved, each equally likely (0x4639F0..0x463A68).",
    "Catch-up: the same without the fruit (0x463A30): the bush and the nets, 1 in 2 each.",
    "A farmer dropped on the bush (task 3) or the nets (task 0x1C) asks for that source each time it is idle, "
    "through the gate; the bush task ends once the bush holds 3 or less (0x463609 / 0x4644A9). The "
    "fruit drop sets no task.",
)

# Trip lengths measured (real-life seconds; trips that paid, starting at the food bin), over the game's map with
# the Cooking Pit restored and Fishing Nets solved: 400 back-to-back trips of an adult with Farming 89 (no failed
# check) for each source, seed 11 (the bush kept at 1,000; no fish scale found, so no Golden Fish).
TRIP_SAMPLES = {"blackberry picks": (400, 94.76, 91.87, 97.91), "fish in the net": (400, 66.49, 52.90, 79.93),
                "fruit stomps": (400, 162.24, 157.94, 167.97)}
SPEEDS = (3, 6, 10)

# A farmer left to the game's own scheduler (0x465840, run from the update's empty-queue wait 0x465C53..0x465CC8:
# one try each whole real-life second, 66 in 100 doing nothing at 0x465889), 4 x 24 real-life hours (seeds 1-4)
# each, preference Farming, all other skills 10, food kept at 1,000: real-life seconds per trip that brought food
# from that source, by Farming skill.  It includes the failed checks, the refused tasks and the other sources and
# jobs the chooser and dispatcher pick.  Blackberries: dropped on the bush (task 3), the bush kept at 1,000, the
# the Cooking Pit and Fishing Nets done; fish: dropped on the nets (task 0x1C), the same village; fruit: no task (the
# fruit drop sets none), the bush empty and Fishing Nets unsolved, so the fruit is the only farming offered.
CYCLE_SETUP = {"blackberry picks": (3, 1000, (6, 0xB)), "fish in the net": (0x1C, 1000, (6, 0xB)),
               "fruit stomps": (0, 0, (6,))}
CYCLE_HOURS, CYCLE_SEEDS = 24, (1, 2, 3, 4)
LIVE_CYCLE_COUNTS = {       # paying trips from that source in each 24-hour run, seeds 1..4
    "blackberry picks": {100: (770, 767, 762, 777), 50: (744, 741, 743, 736), 20: (671, 702, 681, 675)},
    "fish in the net": {100: (1013, 997, 991, 1017), 50: (901, 938, 913, 896), 20: (736, 774, 743, 788)},
    "fruit stomps": {100: (513, 516, 515, 511), 50: (490, 496, 488, 492), 20: (449, 450, 450, 445)},
}
_RUN_SECONDS = 2_618_181 * 0.033   # the frames of 24 real-life hours at 33 ms (int(24 x 3600 / 0.033)), seconds
LIVE_CYCLE = {key: {farming: round(len(counts) * _RUN_SECONDS / sum(counts), 1)
                    for farming, counts in by_skill.items()}
              for key, by_skill in LIVE_CYCLE_COUNTS.items()}
# = {"blackberry picks": {100: 112.4, 50: 116.6, 20: 126.6}, "fish in the net": {100: 86.0, 50: 94.7, 20: 113.6},
#    "fruit stomps": {100: 168.2, 50: 175.8, 20: 192.6}}; the two halves of each (seeds 1-2, 3-4) agree within 1.7%.


def _live(mean: float) -> dict[int, float]:
    return {speed: mean for speed in SPEEDS}


def _span(low: float, high: float) -> dict[int, tuple[float, float]]:
    return {speed: (low, high) for speed in SPEEDS}


_CLOCK = ("Real-life time, the same at Fast, Normal and Slow (nothing in the walk or the waits reads the speed); "
          "while paused the villagers stand still, and a wait whose moment passes during the pause ends on the first "
          "frame after it. A trip in progress is not saved (the step queue, record + 0, is outside the saved part of "
          "the record); the task is (+0x1C54), so a farmer dropped on a source goes back to it after loading.")

_TASK_TURN = task_trips_per_turn(100)      # 0.8 + 0.2 x 0.83096 / 2 = 0.883096 (Farming 60 or more)


def _cycle(key: str) -> str:
    c = LIVE_CYCLE[key]
    return f"{c[100]} s per paying trip at Farming 100, {c[50]} at 50, {c[20]} at 20 (LIVE_CYCLE)"


TRIPS: tuple[Trip, ...] = (
    Trip(
        key="blackberry picks",
        job="dropped on the blackberry bush (task 3), or a Farming choice the dispatcher sends to the bush",
        live_seconds=_live(94.76),
        live_span=_span(91.87, 97.91),
        catch_up_trips_per_turn=_TASK_TURN,
        success_offset=34,
        live_words=("From the food bin: walk to a random point of the bush (map area 0x20, x 120-199, y 1408-1423), "
                    "a 1 s pose, a 3 s wait, a 1 s pose, the Farming check, a 3 s wait, walk back to a random point "
                    "of the food bin (area 8), two 3 s waits, then the bush / 100 (at least 2) is credited and taken "
                    "off the bush (job event 13, 0x464464). " + _CLOCK),
        catch_up_words=("A farmer dropped on the bush: each job turn whose task passes the gate (8 in 10), or whose "
                        "own Farming choice the dispatcher sends to the bush (1 in 2 with the nets), runs one pick at "
                        "once (0x465750 -> 0x4634D0 / 0x4639B0 -> 0x451C30 -> 0x464FA0): the Farming check, then "
                        "the bush / 100, at least 2, as live. The task ends when the bush holds 3 or less."),
        verified="code",
        extra=("An elder (walking at 40) takes 210.67 s (203.91-218.89); a villager who likes running (300) "
               "44.30 s (43.89-45.90).",
               "A failed Farming check ends the trip at the bush with nothing: 49.58 s on average from the bin "
               "(45 of 200 trips at Farming 0).",
               "Catch-up trips a job turn: " + f"{_TASK_TURN:.6f}" + " at Farming 60 or more "
               "(the task 8 turns in 10, else the Farming choice x 1/2 for the bush; with 8,000 food or more the task "
               "only 48 turns in 100).",
               "Live, with the game's own scheduler: " + _cycle("blackberry picks") + "."),
    ),
    Trip(
        key="fish in the net",
        job="dropped on the fishing nets (Fishing Nets solved; task 0x1C), or a Farming choice sent to the nets",
        live_seconds=_live(66.49),
        live_span=_span(52.90, 79.93),
        catch_up_trips_per_turn=_TASK_TURN,
        success_offset=34,
        live_words=("From the food bin: on rand(100) < 50 two walks to the pier of map area 0x60 (x 1638-1665 "
                    "y 1259-1282, then x 1771-1800 y 1221-1242), else three to the pier of area 0x61 (x 1618-1647 "
                    "y 1527-1544, x 1694-1725 y 1503-1516, x 1799-1847 y 1486-1501) (0x43320E), a 3 s wait, the Farming check, take a fish, "
                    "walk back to a new point by that side's first one, walk to the food-bin point chosen when the "
                    "trip began, a 3 s wait, then 4 food is credited (job event 16, 0x4645A4). The piers are walkable "
                    "only with Fishing Nets solved (0x46D0A4: areas 0x60 / 0x61). " + _CLOCK),
        catch_up_words=("A farmer dropped on the nets: each job turn whose task passes the gate (8 in 10), or whose "
                        "own Farming choice the dispatcher sends to the nets (1 in 2 with the bush), runs one catch at "
                        "once (0x465750 -> 0x4634D0 / 0x4639B0 -> 0x4331D0 -> 0x464FA0): the Farming check, then 4 "
                        "food, or the Golden Fish's 8, as live."),
        verified="code",
        extra=("The Golden Fish: with s fish scales found (s >= 1), rand(100) < 2s + 1 (0x433360..0x433387) takes it "
               "straight to the bin: 8 food (job event 17, 0x4645E1).",
               "An elder takes 150.02 s (124.87-188.89); a villager who likes running 28.00 s (21.91-31.91).",
               "A failed Farming check ends the trip on the pier with nothing: 38.41 s on average from the bin "
               "(42 of 200 trips at Farming 0).",
               "Live, with the game's own scheduler: " + _cycle("fish in the net") + "."),
    ),
    Trip(
        key="fruit stomps",
        job="dropped on the fruit (the Cooking Pit restored; no task is set), or a Farming choice sent to the fruit",
        live_seconds=_live(162.24),
        live_span=_span(157.94, 167.97),
        catch_up_trips_per_turn=0.0,
        success_offset=34,
        live_words=("From the food bin: one of the four fruit spots not in use (actions 101-104, 0x4343A0), walk "
                    "to the fruit tree (map area 0x26, x 64-159 y 1880-1919), shake it down (short steps and 1 s "
                    "poses), the Farming check, take the fruit, walk to the Cooking Pit (area 0x22, x 368-383 "
                    "y 1848-1863), a 5 s wait, stomp it (hops), take the stomped fruit, walk to a random point of "
                    "the food bin, a 1 s wait, then 3 food is credited (job event 15, 0x464567). " + _CLOCK),
        catch_up_words=("None: the dispatcher never offers the fruit while catching up (0x463A30) and no stock drop "
                        "sets the fruit task 2 (0x46364E); the Cooking Pit bonus adds 5 food x Food "
                        "Mastery per villager and counted unit on rand(100) < Farming - 25 instead."),
        verified="code",
        extra=("When the stew pot waits for ingredients as the trip is queued (0x4349A3: 0x42DDA0 on the pot "
               "0x4D76D8), the stomped fruit goes into the stew (action 0x90) and no food is credited.",
               "An elder takes 331.65 s (320.96-341.98); a villager who likes running 88.77 s (86.95-89.99).",
               "A failed Farming check ends the trip at the tree with nothing: 71.79 s on average from the bin "
               "(42 of 200 trips at Farming 0).",
               "A task 2 written into a save would bring the fruit even while catching up (the gate path skips "
               "the catch-up refusal): 3 food a turn the gate passes.",
               "The Cooking Pit bonus (catch-up only, 0x468A7A-0x468AC5): after each counted unit's job turns, 5 food "
               "x Food Mastery (7 at level 2, 10 at 3) for each villager who had them, on rand(100) < Farming - 25: "
               "3.75 food a unit at Farming 100, 1.75 at 60, none at 25 or less; its health "
               "is not checked.",
               "Live, with the game's own scheduler (no other farming offered): " + _cycle("fruit stomps") + "."),
    ),
)
