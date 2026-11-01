"""The Lost Children (VV2): what one farmer brings in, live and while catching up -- measured from the stock exe.

Every number below was measured by running the stock executable's own code in unicorn
(tests/farmers_emulation_vv2.py; re-measured by tests/test_game_mechanics_farmers_vv2.py).

WHO IS A FARMER, AND ON WHICH SOURCE.  A villager's job preference (record +0x7F8) is set on the Details screen; 1
is Farming.  Dropping a villager on the coconut tree, the field or the sea runs that job at once and stores an
assignment in record +0x7E0: 3 coconuts (0x430181 -> 0x456F70), 5 the field (0x43073D -> 0x4593D0), 6 fishing
(0x42FBF3 -> 0x4507A0).  The assignment does not keep the source: when it is kept (0x461580) it runs the work
dispatcher 0x45FBF0 with job 1 (Farming, 0x4617AC) like any farmer, and the dispatcher picks the source from the
Farming technology level (state +0x2EA9C), the fish, the coconuts, the field and the dam (see SOURCE_RULES).  Only
two late branches of the AI decision run the stored source itself (0x460590): below 300 food when the chosen job
did not start (0x461A15), and when it did not start for a villager whose best skill is under 50 and whose five
skills add up to under 70 (0x461A5E).

ONE TRIP.  The job routine queues the trip's steps (0x449B70: record +0x4C, 49 steps of 24 bytes) and the
per-frame villager update 0x464CD0 plays them.  Coconuts 0x456F70: walk to the tree's foot (407, 356), walk to one
of 3 picking spots, the Farming check (step 6), two animation steps (8 and 15), walk back to the food bin (x
1130-1141, y 970-974), wait 3 s, then the payoff (callback 27, 0x463160).  Crops 0x4593D0: walk to one of the
field's 4 rows (x 1100, 1175, 1250 or 1325), 4 stops down it with a 3 s wait at each, the Farming check, walk back
to the food bin (26 in 100 by a waypoint, rand(100) <= 25 at 0x45961A), the payoff (callback 28, 0x46321E).
Fishing 0x4507A0: three walks to
spots along the shore (x 37-166, y 330-543) with a 1 s wait at each, the Farming check, walk up the beach
(0x167, 0x1F3) and to the food bin (0x47E, 0x3E0), wait 1 s, the payoff (callback 29, 0x4632CB); a fisher with
Farming 88 or more makes the big catch on rand(100) < 10 (0x450BE3 / 0x450BFA, 10 in 100, chosen when the trip is
queued; still after the Farming check): 55 food at any speed (callback 30, 0x46335C).  The Farming check is the
skill step 0x44E170: it passes when rand(100) <= Farming + 33 (+ 66 for a villager who likes learning, + 16 for one
who dislikes it), i.e. (Farming + 34) times in 100; a failure clears the queue (0x44E227) and queues a short
reaction (0x44B1B0), so the trip ends with no food.  The payoff runs at the end of the queue, at the food bin, and
adds the food with 0x4262B0 (food, state +0x2EAA4, and a running total, state +0x2E504).

FOOD A TRIP BRINGS.  The payoffs read the speed value (state +0x2EB08) live and the catch-up flag (state +0x3046C):
coconuts 8 / 4 / 2 on Fast / Normal / Slow, 4 while catching up (0x463160..0x463197); crops 10 / 7 / 4, 7 catching
up (0x46321E..0x463258); fish 11 / 8 / 5, 8 catching up (0x4632CB..0x463305); the big catch 55 always (0x463362).
A speed value other than 3 or 10 pays the Normal amount.  Coconuts are taken off the tree (never below 0; under 10
left the assignment is cleared, 0x4631F8); crops off the field and the birds' allowance; fish off the water.

LIVE TRIP TIME (real-life seconds, the same at Fast, Normal and Slow).  Measured by running the villager update
0x464CD0 frame by frame with the game's own frame time: the frame limiter 0x409318..0x409342 holds each frame to
1000 // 30 = 33 ms (30 frames a second: 0x403250 through the app's vtable, 0x40299B, set at 0x408340).  The walk
0x45E880 moves the villager by its speed / 100 pixels a frame, split between x and y (0x449F00 / 0x449E80; the
direction is re-aimed every 11 frames), over the map's 10-pixel grid (170 x 170 cells, dword x // 10 * 170 +
y // 10, read by 0x4181D0, built by the stock map builder 0x418660 from the village's state): a blocked cell (1-23;
24 for a child) sends it round by the grid path finder 0x41A700 (a detour walk, step 26, put first in the queue); no
path clears the queue; cells 76-79 put a fixed waypoint first (0x44FCB0).  An adult walks at 100 (1 pixel
a frame, 30.3 pixels a real-life second); a child under 280 age units (14 years) who does not dislike running, and
anyone who likes running, at 300; an elder past 840 + 160 x Medicine level age units (50, 58 or 66 years) and
anyone who dislikes running at 40 (0x44D848..0x44D899).  Health, sickness and skill do not change the walk.  The
waits end on the game clock 0x403200, whole real-life seconds (time() minus the save's base): a step's timer
(record +0x58) is the clock + its seconds and it ends on the first frame the clock passes it (0x464E1F..0x464E2D).
The speed value is read by nothing in the update, the walk or the waits; only the village scene's frame stops
calling the update while paused (speed + 999, 0x42F9F0).  The emulation gave identical trips, frame for frame,
at speed 3, 6 and 10 (only the food differed).  A trip is timed from the frame its job is queued (the villager
standing where its last trip ended, at the food bin) to the frame the food is credited; TRIP_SAMPLES says what was
measured.

Stubbed in the emulation: rand(N) 0x4031A0 (a seeded uniform value), the clock 0x403200 (the emulated real time),
and drawing, sound and text only (the text table 0x441680, the effects 0x41EA60 / 0x41EA30 / 0x41E8A0, the
particles 0x4239D0, the draw-order sort 0x44B0E0, the item getter 0x416060 with no item lying).  Not emulated: the
framework's own frame timing outside the exe (SDL_Delay's accuracy), so a frame is taken as exactly 33 ms; a
computer that cannot draw 30 frames a second walks the villagers more slowly in real time (the waits are
unchanged).

CATCH-UP.  For each counted age unit the life loop 0x43BA70..0x43C0BB charges each villager's meal once (0x43BAF9:
2 food above 150 food; at 150 or less the meal is eaten on rand(100) < 50 and skipped otherwise; 2 more on
rand(100) <= 75 at 0x43BB21 on Medium above 4,000 food or on Hard, never on Easy) and, for every unit but the last
2, gives each villager aged 280 units or more by the age shown (14 years), not sick, not nursing, not a totem, 4
job turns 0x43B4D0 (0x43BF94..0x43BFF5, with the flag state +0x3046C set; health >= 20 at 0x43B50D).  A job turn
asks the same chooser 0x449C60; on Farming (1) the dispatcher 0x45FBF0 queues the same trip and the step simulator
0x464680 plays it with every walk and wait skipped: the Farming check (step 6 -> 0x44E170) and the payoff (step 17
-> 0x461B10) run as live, so one farming turn is one trip and pays the catch-up amount (coconuts 4, crops 7, fish 8,
the big catch 55).  A catch-up trip is never lost on a walk (the walks are skipped).
"""
from __future__ import annotations

from vv_game_mechanics_farmers import Trip

TURNS_PER_UNIT = 4          # job turns a counted age unit (0x43BFDD..0x43BFF5), for all but the last 2 units

# The job chooser 0x449C60 for a villager whose preference is Farming (+0x7F8 = 1): 15 in 100 nothing unless the
# villager likes work (0x449C6E); otherwise the best skill, each skill weighed on rand(100) > 15 (Farming first,
# 0x449CB4); a choice other than Farming switches to the preference on rand(100) <= 85 (0x449DC5); then the job
# happens only when the chosen skill is more than 5 and rand(100) < skill + 40 (0x449E0F..0x449E23).  With Farming
# the villager's highest skill: 0.85 x (0.84 + 0.16 x 0.86) = 0.83096 of turns choose Farming, times
# min(1, (Farming + 40) / 100).  (A villager who dislikes work first refuses 70 in 100, 0x449CA1.)
FARMING_CHOSEN = 0.83096
SUCCESS_OFFSET = 34         # the Farming check passes (Farming + 34) times in 100 (0x44E1D0; likes learning +66)


def farming_chosen(farming: int) -> float:
    """Share of job turns (live: of the scheduler's job choices) that choose Farming, for a villager whose
    preference is Farming and whose highest skill is Farming."""
    if farming <= 5:
        return 0.0
    return FARMING_CHOSEN * min(1.0, (farming + 40) / 100.0)


# The dispatcher 0x45FBF0, job 1, as emulated.  "Fished out" is 0x425B00: no fish left (+0x2EAD0 <= 0) and
# Sustainable Fishing not solved (+0x2E7E8 = 0).
SOURCE_RULES = (
    "Farming level 1: while fish remain (the count above 0, Sustainable Fishing not looked at), fishing on "
    "rand(100) > 50 (0x45FE00), and always without the dam; otherwise, with the dam built, the field (an empty field: "
    "the empty-field job 0x45D280, no food); with no fish and no dam, nothing (0x45FDF4..0x45FE5C).",
    "Farming level 2: unless fished out, fishing on rand(100) <= 80 (0x45FD26). Otherwise, with more than 10 "
    "coconuts and no dislike of heights or coconuts, coconuts on rand(100) > 50 (0x45FD79), and also on "
    "rand(100) < 50 (0x45FD98) when the field is empty, and always without the dam; failing that the field with the "
    "dam built (empty: the empty-field job), else nothing (0x45FD1B..0x45FDF1).",
    "Farming level 3: unless fished out, fishing on rand(100) < 40 with crops on the field (0x45FC60), and on "
    "rand(100) < 80 (0x45FC51) or failing it < 40 with the field empty. Otherwise, with 10 coconuts or more, coconuts "
    "on rand(100) < 25 with crops on the field (0x45FCAC), and on rand(100) < 75 (0x45FC9D) or failing it < 25 with "
    "the field empty; failing that the field with the dam built (empty: the empty-field job), else nothing "
    "(0x45FC36..0x45FD18).",
    "A villager who dislikes coconuts or heights refuses a coconut trip on rand(100) < 75 (0x456F94), one who "
    "dislikes turnips or vegetables a crop trip on rand(100) < 75 (0x459400), one who dislikes fish every fishing "
    "trip (0x4507AB); a fishing trip when fished out walks to the shore and brings nothing (0x4507F9).",
)

# Trip lengths measured (real-life seconds; trips that paid, each starting where the last one ended, at the food
# bin), over the map the stock map builder 0x418660 makes from the owner's grown village (its slot 5 save: every
# technology at level 3, the dam built, Sustainable Fishing solved): 400 back-to-back trips of an adult with Farming
# 87 for each source (every check passes; no big catch below 88), seed 11; the big catch: 400 fishing trips with
# Farming 100, seed 13 (38 big catches).  Over the map built from a fresh state (no buildings, no dam; crops with
# the dam): coconuts 126.48 (122.96-135.96), crops 40.85 (31.91-57.91), fish 122.58 (110.88-133.91).
TRIP_SAMPLES = {"coconut trips": (400, 127.73, 122.96, 135.99), "crop trips": (400, 40.95, 31.91, 57.91),
                "fishing trips": (400, 121.10, 103.92, 136.92), "big catches": (38, 122.06, 109.89, 133.91)}
SPEEDS = (3, 6, 10)
LIVE_FOOD = {"coconut trips": {3: 8, 6: 4, 10: 2}, "crop trips": {3: 10, 6: 7, 10: 4},
             "fishing trips": {3: 11, 6: 8, 10: 5}}
CATCH_UP_FOOD = {"coconut trips": 4, "crop trips": 7, "fishing trips": 8}
BIG_CATCH_FOOD = 55

# A farmer left to the game's own scheduler (the empty-queue wait 0x464E72: one AI decision 0x461850 each whole
# real-life second, 66 in 100 doing nothing at 0x46188E), 24 real-life hours for each of 4 seeds (pooled: total time
# over total paying trips; a run whose villager stalled on the leisure walk 0x457AA0 counts only up to the stall;
# seed-to-seed spread: within 1.5% at Farming 100, 3% at 50, up to 14% at 20), preference
# Farming, all other skills 10, health 100, food kept at 1,000, over the grown village's map, the Farming skill held
# fixed: real-life seconds per trip that brought food, by Farming skill.  It includes the failed checks, the rests
# and the other jobs the chooser and the AI pick.  The dispatcher's source roll is pinned to the named source (the
# level 3 rolls at 0x45FC60 and 0x45FCAC; everything else runs as in the game); fishing includes the big catches.
LIVE_CYCLE = {"coconut trips": {100: 139.8, 50: 153.2, 20: 216.4},
              "crop trips": {100: 55.8, 50: 74.4, 20: 166.5},
              "fishing trips": {100: 132.4, 50: 147.6, 20: 266.5}}


def _live(mean: float) -> dict[int, float]:
    return {speed: mean for speed in SPEEDS}


def _span(low: float, high: float) -> dict[int, tuple[float, float]]:
    return {speed: (low, high) for speed in SPEEDS}


def _cycle(key: str) -> str:
    c = LIVE_CYCLE[key]
    return (f"Live, with the game's own scheduler: {c[100]:g} s per paying trip at Farming 100, {c[50]:g} at 50, "
            f"{c[20]:g} at 20 (LIVE_CYCLE).")


_CLOCK = ("Real-life time, the same at Fast, Normal and Slow (nothing in the walk or the waits reads the speed); "
          "while paused the villagers stand still, and a wait whose moment passes during the pause ends on the first "
          "frame after it. A trip in progress is not saved (the step queue, record +0x4C, is outside the part of the "
          "record a save keeps, 0x44B640: +0x524..+0x7FF and the name), so closing the game loses it.")

TRIPS: tuple[Trip, ...] = (
    Trip(
        key="coconut trips",
        job="Farming preference, picking coconuts (Farming level 2 or more, more than 10 coconuts on the tree)",
        live_seconds=_live(127.73),
        live_span=_span(122.96, 135.99),
        live_food=dict(LIVE_FOOD["coconut trips"]),
        catch_up_food=CATCH_UP_FOOD["coconut trips"],
        catch_up_trips_per_turn=FARMING_CHOSEN,
        success_offset=SUCCESS_OFFSET,
        live_words=("From the food bin: walk to the coconut tree and to one of its 3 picking spots, the Farming "
                    "check, climb and pick, walk back to the food bin, wait 3 s, then the coconuts are credited "
                    "(8, 4 or 2 on Fast, Normal or Slow). " + _CLOCK),
        catch_up_words=("Each job turn that chooses Farming and coconuts runs one trip at once (0x43B4D0 -> 0x45FBF0 "
                        "-> 0x456F70 -> 0x464680): the Farming check, then 4 food at any speed (0x463170)."),
        verified="code",
        extra=("A villager who likes running (300) takes 63.37 s (60.95-65.97); an elder or a villager who dislikes "
               "running (40) 271.42 s (261.95-294.99).",
               "A villager who dislikes coconuts or heights refuses 75 in 100 (0x456F94).",
               _cycle("coconut trips")),
    ),
    Trip(
        key="crop trips",
        job="Farming preference, harvesting the field (the dam built, crops on the field)",
        live_seconds=_live(40.95),
        live_span=_span(31.91, 57.91),
        live_food=dict(LIVE_FOOD["crop trips"]),
        catch_up_food=CATCH_UP_FOOD["crop trips"],
        catch_up_trips_per_turn=FARMING_CHOSEN,
        success_offset=SUCCESS_OFFSET,
        live_words=("From the food bin: walk to one of the field's 4 rows, 4 stops along it with a 3 s wait at "
                    "each, the Farming check, walk back to the food bin (26 in 100 by a waypoint), then the crops "
                    "are credited (10, 7 or 4 on Fast, Normal or Slow). " + _CLOCK),
        catch_up_words=("Each job turn that chooses Farming and the field runs one harvest at once: the Farming "
                        "check, then 7 food at any speed taken from the field (0x46322E). An empty field: the "
                        "empty-field job instead (0x45D280), no food."),
        verified="code",
        extra=("A villager who likes running takes 24.75 s (21.88-29.90); an elder or a villager who dislikes "
               "running 76.85 s (60.88-117.91).",
               "A villager who dislikes turnips or vegetables refuses 75 in 100 (0x459400).",
               _cycle("crop trips")),
    ),
    Trip(
        key="fishing trips",
        job="Farming preference, fishing (fish left, or Sustainable Fishing solved)",
        live_seconds=_live(121.10),
        live_span=_span(103.92, 136.92),
        live_food=dict(LIVE_FOOD["fishing trips"]),
        catch_up_food=CATCH_UP_FOOD["fishing trips"],
        catch_up_trips_per_turn=FARMING_CHOSEN,
        success_offset=SUCCESS_OFFSET,
        live_words=("From the food bin: three walks to spots along the shore with a 1 s wait at each, the Farming "
                    "check, walk up the beach and back to the food bin, wait 1 s, then the fish are credited (11, 8 "
                    "or 5 on Fast, Normal or Slow). A villager who dislikes fish always refuses (0x4507AB). "
                    + _CLOCK),
        catch_up_words=("Each job turn that chooses Farming and fishing runs one catch at once: the Farming check, "
                        "then 8 food at any speed (0x4632DB); with Farming 88 or more 10 in 100 are the big catch, "
                        "55 food (0x463362)."),
        verified="code",
        extra=("Big catch (Farming 88 or more, 10 in 100, after the Farming check): 55 food at any speed, live and "
               "catching up; 122.06 s (109.89-133.91).",
               "A villager who likes running takes 45.70 s (43.89-52.90); an elder or a villager who dislikes "
               "running 295.90 s (263.90-321.88).",
               "Fished out (no fish and Sustainable Fishing not solved): the trip walks to the shore and brings "
               "nothing (0x4507F9).",
               _cycle("fishing trips")),
    ),
)
