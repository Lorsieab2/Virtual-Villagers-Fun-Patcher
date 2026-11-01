"""The Secret City (VV3): what one farmer brings in, live and while catching up -- measured from the stock exe.

Every number below was measured by running the stock executable's own code in unicorn
(tests/farmers_emulation_vv3.py; re-measured by tests/test_game_mechanics_farmers_vv3.py), over the game's own map
(cmap.dat through the map loader 0x4201F0, wpts.dat at 0x560964) with the game objects built by the exe's own static
constructors (0x4A400C..0x4A411C).

WHO IS A FARMER, AND ON WHICH SOURCE.  The job chooser 0x459730 picks a skill (Farming is skill 0; the Details
screen's preference is record +0xEC0) and the work dispatcher 0x45AF00 (skill 0) lists the sources open now and
takes one at random (rand(count), 0x45AFF5): the honey when puzzle 1 is solved and the hive holds more than 10
(0x45AF46..0x45AF56), a fruit tree (itself picked at random) among those planted with 10 or more fruit
(0x45AF80..0x45AFCA), the sea when puzzle 10 is solved (0x45AFD3).  A farmer who dislikes the source runs off 60
times in 100 instead (rand(100) < 60: bees or honey 0x45B143, fruit 0x45B0BD, fish, the ocean or swimming
0x45B04A).  A villager remembers its work site (record +0xEA0): a fruit pick sets the tree's site 0x17-0x19
(0x4349B5), a honey take 0x15 (0x431D8F), dropping a villager on the sea 0x1C (0x4698E6; fishing itself never sets
it).  Before choosing, the scheduler 0x45BFE0 (0x45C1F9) and the catch-up turn 0x45BF00 (0x45BF7B) first try to
keep at the remembered site (0x45AA90): with Farming 6 or more it continues 80 times in 100 (rand(100) < 20 stops,
0x45AAB4; then rand(100) >= 40 goes on, and under 40 goes on too while food is under 8,000, 0x45AAC8: so 48 in
100 at 8,000 or more; always for a villager who likes work, item 0x2B), to a random tree with 10 or more fruit
(0x45ADB4), the honey (puzzle 1 and more than 10 honey, else the site is forgotten, 0x45ABA8) or the sea (0x45ABEB).

ONE TRIP.  The job routine queues the trip's steps (0x460E30, 44 bytes each at record +0) and the villager's
per-frame update 0x456E90 plays them through the step runner 0x45C440.  Fruit 0x44BF00: walk to a point of the
tree's area (0x16 / 0x17 / 0x18), wait 5 s, the Farming check, the pick (step 0x1B -> the trees' drop handler
0x4348F0: the tree must hold 5 or more) -- the food is credited here, at the tree, by the award 0x434A80 -- then
walk to a point of the food bin (area 0xE) and let go of the fruit.  Honey 0x446E40: walk to the hive (area 0x1E),
two short animations around a 3 s wait, the Farming check, take the honey (item 0x29, the hive's take listener
0x431D74: it needs 10 or more honey, 0x4317F0), wait 3 s, walk back by three set points and a fourth inside the
bin (x 0x45C + rand(0x34), y 0x4F5 + rand(12), 0x446F31), wait twice about 3 s (0x4613B0(3), 0x4612D0(3)), let go: the hive's release
listener 0x431A40 credits the honey only when the villager stands in the food bin (region 0xE, 0x431BE3); the
fourth point's last row, y 1280 (rand(12) = 11), is below the bin, so 1 trip in 12 brings nothing.  Fishing
0x453440: three walks to the shore (x 0x4A5 + rand(0x170), y 0x46 + rand(0x36)) each with a short cast, the
Farming check, walk to a point of the food bin, let go, then the catch (step 0x11 -> 0x458DB0): fish 0x458E81
(11, 8 or 5, credited at 0x458EE5) or, with Farming 88 or more on rand(100) < 10 (0x4535A2), the crab, 55 food
(0x458FDA, at any speed, no chief bonus).  The Farming check is the skill test 0x45A2C0: it passes when rand(100) <=
Farming + 33 (0x45A342..0x45A34E), i.e. (Farming + 34) times in 100 (+ 66 for a villager who likes learning or is
under the potion that makes them smarter, + 16 for one who dislikes learning); a failure clears the queue and
queues the reaction 0x31 (0x45A3B9..0x45A3CC), so the trip brings nothing.  (In a village that has never had a
Farming, Parenting or Research success, the try after a failure succeeds, 0x45A354..0x45A38B; the emulation is a
grown village.)

FOOD A TRIP CREDITS (the food writer 0x4263F0 adds to food and Food Gathered).  Fruit and honey: 4 / (speed value x
0.16666667f) truncated (0x434AD4 / 0x431C12), so 7, 3 or 2 on Fast, Normal or Slow; 4 while catching up (the flag
game+0x12FB4, 0x434AC5 / 0x431BF2).  Fish 11, 8 or 5 (0x458E97..0x458EBA); 8 while catching up (0x458E90).  The
tree loses what the award paid (0x434B1A), the hive what the release paid (0x431C51).  The Tribal Chief's
supervision 0x45FC60 adds a third to fruit (0x434AF1) and fish (0x458EC6), a half to honey (0x431C36) when the
chief (alive, not sick) has the same remembered site and rand(100) < 25 x Leadership (never at Leadership 0); the
fruit award asks for site 0x17 for every tree (0x434AF1), so it pays only with the chief remembering site 0x17.

LIVE TRIP TIME (real-life seconds, the same at Fast, Normal and Slow).  Measured by running the villager's update
0x456E90 frame by frame with the game's own frame time: the frame limiter 0x409A88..0x409AB2 holds each frame to
1000 // 30 = 33 ms (fps 30 from the settings 0x403380, set by 0x408960).  The walk 0x458760 moves the villager by
its speed / 100 pixels a frame, split between x and y in proportion (0x455A00; re-aimed every 10 frames by
0x459490), and goes round obstacles with the path object at record +0xFCC (0x4237C0; no path: the queue is cleared
and the trip ends, 0x458A8C); trigger cells on the way insert set walks (0x420610 -> the table 0x560958, e.g. the
waypoints 0x422CA0).  An adult walks at 100 (1 pixel a frame, 30.3 pixels a real-life second), at 300 one who likes
running (item 0x26; a child who does not dislike it, or under the potion 0x18), at 40 one who dislikes running or an
elder at 840 + 160 x Medicine level age units or more (0x457290..0x457308, 0x45C5E0).  The waits end on the clock
0x403330, whole real-life seconds of time() past an epoch (0x4A4210): a step ends on the first frame its end
second has passed (0x460EA0).  Nothing in the update, the walk or the waits reads the speed value except to stop
while paused (the manager's update 0x45F3B0 runs only while game+0x12F20 < 999, 0x468B59); the emulation gave
identical trips, frame for frame, at speed 3, 6 and 10.  A trip is timed from the frame its job is queued (the
villager standing where its last trip ended, at the food bin) to the frame its queue empties, back at the bin;
the fruit is credited at the tree, part-way (TRIP_SAMPLES, CREDIT_SAMPLES).

Stubbed in the emulation: rand(N) 0x4032D0 (a seeded uniform value), the clock 0x403330 (the emulated real time),
the game object 0x428B60 (a block holding the speed value, the difficulty and the catch-up flag), the text table
0x42F740 / 0x42F190, the settings object 0x402C90 and fopen 0x46F47B (the data files are put in place first),
atexit and operator new.  Not emulated: the framework's own frame timing outside the exe (SDL_Delay's accuracy), so
a frame is taken as exactly 33 ms; a computer that cannot draw 30 frames a second walks the villagers more slowly in
real time (the waits are unchanged).

CATCH-UP.  The aging loop 0x45FFE0 (from the 2-second tick 0x428C60) runs every villager's uncounted age units one
at a time until no one is behind (0x4605CE -> 0x45FFF0).  For each counted unit it charges the villager's meal once
(0x460040: 2 food while food is above 500; at 500 or less 2 food on rand(100) < 50 (0x46005B), else 1 health lost
on rand(100) < 30 (0x46006A); then 2 more on rand(100) <= 75 (0x4600BF) on Medium with 8,000 or more left, or on Hard; never on
Easy) and, for every unit but the last 2 (0x46051F), gives an adult (age shown 280 or more) who is not sick, not
nursing (+0xE8C) and not the Tribal Chief (+0xE80, 0x460555) 4 job turns 0x45BF00 (0x460568..0x460580) with the
catch-up flag set; a turn needs 20 health (0x45BF2C).  A turn asks the chooser, then the remembered site (as live),
then (food 250 or less and Farming 20 or more) Farming first, else the chooser's job; the instant runner 0x45B790
plays the queue with every walk a teleport (0x45B7D7 -> 0x455EB0) and only the Farming check (step 7), item steps
(0xF / 0x10), the special steps (0x11) and the pick (0x1B) run, so one farming turn is one trip and pays as live but
at the catch-up rate.  Fishing skips its walk to the bin while catching up (0x4535C2) and pays anyway; honey's
fourth point is a teleport to the same random spot, so 1 in 12 catch-up honey trips pays nothing too.
"""
from __future__ import annotations

from vv_game_mechanics_farmers import Trip

TURNS_PER_UNIT = 4          # job turns a counted age unit (0x460568..0x460580), for all but the last 2 units

# The job chooser 0x459730 for a villager whose preference is Farming (+0xEC0 = 0): 15 in 100 nothing (rand(100) <
# 15, 0x459746; not for a villager who likes work); a villager who dislikes work: nothing on rand(100) < 70 more
# (0x459783); otherwise each skill is considered on rand(100) > 15 (Farming first, 0x459796) and the highest wins
# (Parenting counts 15 lower); a choice other than Farming switches to the preference on rand(100) <= 85
# (0x45985B); then the job happens only when the chosen skill is more than 5 and rand(100) < skill + 40
# (0x45986D..0x45987F).  With Farming the villager's highest skill: 0.85 x (0.84 + 0.16 x 0.86) = 0.83096 of
# choices are Farming, times min(1, (Farming + 40) / 100) -- the same as A New Home.
FARMING_CHOSEN = 0.83096
# The remembered-site continuation 0x45AA90 (Farming 6 or more, food under 8,000, not liking work): 80 in 100.
SITE_KEPT = 0.8
SITE_KEPT_RICH = 0.48       # with 8,000 food or more (0x45AAC8)


def farming_chosen(farming: int) -> float:
    """Share of the chooser's picks (live: of the scheduler's tries that look for work; catch-up: of job turns)
    that choose Farming, for a villager whose preference is Farming and whose highest skill is Farming."""
    if farming <= 5:
        return 0.0
    return FARMING_CHOSEN * min(1.0, (farming + 40) / 100.0)


def catch_up_trips(farming: int, food: int = 1000) -> float:
    """Trips a catch-up job turn runs for that villager when it remembers its site (a tree, the hive, or the sea it
    was dropped on): the continuation first, the chooser on the rest (0x45BF47..0x45BFC0)."""
    if farming < 6:
        return farming_chosen(farming)
    kept = SITE_KEPT if food < 8000 else SITE_KEPT_RICH
    return kept + (1 - kept) * farming_chosen(farming)


CATCH_UP_TRIPS = catch_up_trips(100)        # 0.966192 (Farming 60 or more, food under 8,000)

# The dispatcher 0x45AF00, Farming, as emulated:
SOURCE_RULES = (
    "Each Farming choice takes one of the sources open now at random: the honey (puzzle 1 solved and more than 10 "
    "honey in the hive), the fruit trees (any planted tree with 10 or more fruit; the tree itself is picked at "
    "random), the sea (puzzle 10 solved).",
    "A villager keeps at its remembered site 80 times in 100 (48 with 8,000 food or more; always if it likes work) "
    "before the chooser is asked again: a fruit pick remembers its tree, a honey take the hive, and dropping the "
    "villager on the sea remembers the sea (fishing itself does not).",
    "At 250 food or less a villager with Farming 20 or more farms first (live 0x45C229, catch-up 0x45BF9F).",
)

# Trip lengths measured (real-life seconds; trips that paid, each starting where the last ended, at the food bin),
# over the stock map: 400 back-to-back trips of an adult with Farming 87 for each source (no crab below 88), seed
# 11, the 3 trees in turn; the crab: Farming 100, seed 13 (52 crabs and 348 fish in 400 trips).  Honey: 369 of 400
# paid, the other 31 ended at y 1280 below the bin (91.68 s, nothing credited).
TRIP_SAMPLES = {"fruit picks": (400, 37.11, 24.35, 49.6), "honey picks": (369, 91.59, 89.0, 94.02),
                "fishing trips": (400, 114.92, 99.99, 139.99), "crabs": (52, 115.06, 100.98, 133.98)}
FRUIT_TREES = {0: (134, 27.59, 24.35, 31.52), 1: (133, 37.1, 34.29, 40.66), 2: (133, 46.71, 44.19, 49.6)}
# From the food bin to the moment the food is credited: fruit at the tree, honey and fish at the bin.
CREDIT_SAMPLES = {"fruit picks": (400, 21.3, 14.26, 27.65), "honey picks": (369, 91.56, 88.97, 93.98),
                  "fishing trips": (400, 114.82, 99.89, 139.89)}
HONEY_DELIVERED = 11 / 12   # honey trips that end inside the food bin (the rest pay nothing), live and catch-up
# The share of catch-up trips that pay once the check passes (the honey dropped below the bin pays nothing); live,
# LIVE_CYCLE already counts only the trips that paid.
CATCH_UP_DELIVERED = {"honey picks": HONEY_DELIVERED}
SPEEDS = (3, 6, 10)

# A farmer left to the game's own scheduler (the runner's empty-queue wait 0x45C49C: one try each whole real-life
# second, 66 in 100 doing nothing at 0x45C0C4), preference Farming, the site remembered, all other skills 10, food
# kept at 1,000, only that source open (fruit: 3 trees full, no honey, puzzle 10 unsolved; honey: the hive full, no
# fruit, puzzle 10 unsolved; the sea: no fruit, no honey), 2 x 40 real-life hours (seeds 1 and 2, within 2.1% of each
# other; their pooled mean below): real-life seconds per trip that brought food, by Farming skill.  It includes the
# failed checks, honey dropped outside the bin, the idle seconds and the other jobs the chooser picks.  At Farming 100
# fishing that is 2,143 fish and 251 crabs.
LIVE_CYCLE = {"fruit picks": {100: 42.3, 50: 48.5, 20: 57.0},
              "honey picks": {100: 105.5, 50: 110.0, 20: 117.8},
              "fishing trips": {100: 120.3, 50: 127.4, 20: 141.2}}
# The paying trips of each 40-hour run (4,363,636 frames of 33 ms), seeds 1 and 2.
LIVE_CYCLE_HOURS = 40
LIVE_CYCLE_RUNS = {("fruit picks", 100): (3413, 3399), ("fruit picks", 50): (2967, 2972),
                   ("fruit picks", 20): (2542, 2509), ("honey picks", 100): (1351, 1379),
                   ("honey picks", 50): (1307, 1312), ("honey picks", 20): (1210, 1235),
                   ("fishing trips", 100): (1201, 1193), ("fishing trips", 50): (1138, 1123),
                   ("fishing trips", 20): (1026, 1014)}
LIVE_CYCLE_CRABS = (141, 110)               # of the Farming 100 fishing runs' paying trips

FRUIT_LIVE_FOOD = {3: 7, 6: 3, 10: 2}       # 4 / (speed x 0.16666667f), truncated (0x434AD4 / 0x431C12)
FISH_LIVE_FOOD = {3: 11, 6: 8, 10: 5}       # 0x458E97..0x458EBA


def _live(mean: float) -> dict[int, float]:
    return {speed: mean for speed in SPEEDS}


def _span(low: float, high: float) -> dict[int, tuple[float, float]]:
    return {speed: (low, high) for speed in SPEEDS}


_CLOCK = ("Real-life time, the same at Fast, Normal and Slow (nothing in the walk or the waits reads the speed). While "
          "paused the villagers stand still (their update stops at speed value 999 or more), and a wait whose second "
          "passes during the pause ends on the first frame after it. Loading the village clears every villager's "
          "queue (0x428A5A -> 0x45C990 -> 0x45C360: a new job is chosen, its first 0 to 4 steps are applied at once, "
          "then the queue is cleared again), so a trip in progress when the game closes is lost.")

_FRUIT = Trip(
    key="fruit picks",
    job="Farming preference, dropped on a fruit tree (3 trees planted)",
    live_seconds=_live(37.11),
    live_span=_span(24.35, 49.6),
    live_food=FRUIT_LIVE_FOOD,
    catch_up_food=4,
    catch_up_trips_per_turn=CATCH_UP_TRIPS,
    success_offset=34,
    live_words=("From the food bin: walk to the tree, wait 5 s, the Farming check, pick: the fruit is credited at the "
                "tree (21.30 s on average from the bin, 14.26 to 27.65); then walk back to the food bin and let go. "
                "The nearest tree takes 27.59 s, the middle one 37.10, the far one 46.71. " + _CLOCK),
    catch_up_words=("Each job turn that farms runs one pick at once (0x45BF00 -> 0x44BF00 -> 0x45B790): the Farming "
                    "check, then 4 food taken from the tree (0x434ABB). A farmer remembering a tree keeps at it 80 "
                    "turns in 100 and the chooser gives Farming on the rest: 0.966192 trips a turn."),
    verified="code",
    extra=("A villager who likes running (300) takes 16.33 s (12.84-20.59); an elder or a villager who dislikes "
           "running (40) 83.82 s (56.46-111.01).",
           "A tree under 5 fruit is not picked (0x434982: the reaction 0x72 instead, and the site is forgotten); the "
           "dispatcher only sends farmers to trees with 10 or more.",
           "Live, with the game's own scheduler: 42.3 s per paying pick at Farming 100, 48.5 at 50, 57.0 at 20 "
           "(LIVE_CYCLE)."),
)

TRIPS: tuple[Trip, ...] = (
    _FRUIT,
    Trip(
        key="honey picks",
        job="Farming preference, dropped on the hive (puzzle 1 solved)",
        live_seconds=_live(91.59),
        live_span=_span(89.0, 94.02),
        live_food=FRUIT_LIVE_FOOD,
        catch_up_food=4,
        catch_up_trips_per_turn=CATCH_UP_TRIPS,
        success_offset=34,
        live_words=("From the food bin: walk up to the hive, two short animations and a 3 s wait, the Farming check, "
                    "take the honey, wait 3 s, walk back down by three set points to a fourth in the bin, wait 3 s, "
                    "let go: the honey is credited then, at the bin. 1 trip in 12 ends just below the bin and brings "
                    "nothing. " + _CLOCK),
        catch_up_words=("Each job turn that farms runs one honey trip at once: the Farming check, then 4 food taken "
                        "from the hive (0x431BE8) when the villager is teleported into the bin (11 turns in 12)."),
        verified="code",
        extra=("Only 11 trips in 12 pay, live and while catching up (the last point's y is 0x4F5 + rand(12); y 1280 "
               "is outside the bin): multiply the food by 11/12.",
               "The hive gives honey only while it holds 10 or more (0x4317F0); the dispatcher sends farmers only "
               "above 10.",
               "A villager who likes running takes 43.52 s (43.0-44.02); an elder or one who dislikes running 201.74 "
               "s (197.01-207.01).",
               "Live, with the game's own scheduler: 105.5 s per paying trip at Farming 100, 110.0 at 50, 117.8 at "
               "20 (LIVE_CYCLE)."),
    ),
    Trip(
        key="fishing trips",
        job="Farming preference, dropped on the sea (puzzle 10 solved)",
        live_seconds=_live(114.92),
        live_span=_span(99.99, 139.99),
        live_food=FISH_LIVE_FOOD,
        catch_up_food=8,
        catch_up_trips_per_turn=CATCH_UP_TRIPS,
        success_offset=34,
        live_words=("From the food bin: three walks along the shore with a short cast at each, the Farming check, walk "
                    "back to the food bin, let go: the catch is credited then, at the bin. A fisher with Farming 88 "
                    "or more lands a crab, 55 food, on 10 catches in 100 (the same trip, 115.06 s). " + _CLOCK),
        catch_up_words=("Each job turn that farms runs one fishing trip at once: the Farming check, then 8 food "
                        "(0x458E90), or the crab's 55 with Farming 88 or more on rand(100) < 10; the walk to the bin "
                        "is left out (0x4535C2)."),
        verified="code",
        extra=("A villager who likes running takes 42.70 s (39.01-48.97); an elder or one who dislikes running "
               "276.80 s (252.98-314.99).",
               "A villager who dislikes fish, the ocean or swimming runs off 60 times in 100 (0x45B04A).",
               "Live, with the game's own scheduler: 120.3 s per paying trip at Farming 100 (crabs included), 127.4 "
               "at 50, 141.2 at 20 (LIVE_CYCLE)."),
    ),
)
