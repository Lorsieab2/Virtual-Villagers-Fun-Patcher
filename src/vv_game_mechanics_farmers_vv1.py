"""A New Home (VV1): what one farmer brings in, live and while catching up -- measured from the stock exe.

Every number below was measured by running the stock executable's own code in unicorn
(tests/farmers_emulation_vv1.py; re-measured by tests/test_game_mechanics_farmers_vv1.py).

WHO IS A FARMER, AND ON WHICH SOURCE.  A villager's job preference (record +0x3D0) is set on the Details screen
(0x4496E9..0x4497F3); 1 is Farming.  Dropping a villager on the berry bush, the crop field or the sea runs that
job at once and remembers the source in record +0x3B8: 3 the bush (0x424744 / 0x42479F -> 0x441E10), 5 the
field (0x424BE4 -> 0x4439F0, Farming level 2 or more), 6 the sea (0x4241E2 -> 0x43F450, Farming level 3 or
more, not a villager who dislikes swimming or the ocean, 0x4241BB / 0x4241CA).  Afterwards the job chooser 0x439AE0 decides each time whether
the villager farms, and the work dispatcher 0x4472C0 (job 1) picks the source from the Farming level, the
remembered source, the bush and the field (see SOURCE_RULES).  A berry pick that leaves the bush under 100
forgets the remembered source (0x43AE06).

ONE TRIP.  The job routine queues the trip's steps (0x4399F0) and the per-frame action runner 0x448600 plays
them.  Berries 0x441E10: walk to the bush, wait 5-7 s, wait 2 s, the Farming check, wait 5-9 s, walk back to the
food bin, wait 2 s, then the reward (14: the bush / 130, at least 2, 0x43AD62).  Crops 0x4439F0: four walks along
a field row with a 3 s wait at each, the Farming check, walk back, wait 1 s, the reward (15: 7 food, 0x43AEC5).
Fishing 0x43F450: two walks to a fishing spot with a 1 s wait at each, the Farming check, walk up the beach and
back (26% of trips by one more waypoint), wait 1 s, the reward (16: 9 food, 0x43AF34); a fisher with Farming 90 or more
instead makes the big catch on rand(100) <= 20 (0x43F4B0 / 0x43F4C6: 21 in 100, no Farming check, 55 food,
reward 17 at 0x43AF86, then a 10 s celebration).  The Farming check is the skill test 0x43D440: it passes when
rand(100) <= Farming + 30, i.e. (Farming + 31) times in 100; a failure clears the queue (0x43D4B4) and queues a
short reaction (0x43A040), so the trip ends with no food.  The reward runs at the end of the queue, at the food
bin, and adds the food with 0x41D140 (food and Food Gathered).

LIVE TRIP TIME (real-life seconds, the same at Fast, Normal and Slow).  Measured by running the action runner
0x448600 frame by frame with the game's own frame time: the frame limiter 0x409118..0x409142 holds each frame to
1000 // 30 = 33 ms (30 frames a second, the settings 0x402FC0).  The walk 0x445CB0 moves the villager by its
speed / 100 pixels a frame, split between x and y in proportion (0x439CC0; the direction is re-aimed every 10
frames), and steps around obstacles on the map's 10-pixel grid (0x414200, built by the stock map builder 0x414590;
detours 0x43DFC0, at most 15 a job: more and the walk gives up).  An adult walks at 100 (1 pixel a frame,
30.3 pixels a real-life second), a villager who likes running at 300, an elder past 840 + 160 x Medicine level
age units (50, 58 or 66 years) at 40 (0x43CD09..0x43CD5F).  The waits end on the game clock 0x402F70, whole
real-life seconds (time() minus the save's epoch).  Nothing in the runner, the walk or the waits reads the speed
value except to stop while paused (0x424030); the emulation gave identical trips, frame for frame, at speed 3, 6
and 10.  A trip is timed from the frame its job is queued (the villager standing at the food bin where its last
trip ended) to the frame the food is credited; TRIP_SAMPLES says what was measured.

Stubbed in the emulation: rand(N) 0x402F10 (a seeded uniform value), the clock and time() (the emulated real
time), and drawing, sound and text only (speech bubbles 0x417DF0 / 0x417C60, particles 0x41AFD0, tutorial
popups 0x41C960, the text table 0x433970, sprintf 0x44B23D, the draw-order sort 0x439FC0).  Not emulated: the
framework's own frame timing outside the exe (SDL_Delay's accuracy), so a frame is taken as exactly 33 ms; a
computer that cannot draw 30 frames a second walks the villagers more slowly in real time (the waits are
unchanged).

CATCH-UP.  For each counted age unit the life loop 0x42EC55..0x42F162 charges each villager's meal once
(0x42ECCC: 2 food; 2 more on rand(100) <= 75 at 0x42ECFC on Medium above 2,000 food or on Hard) and, for every
unit but the last 2, gives each adult (age shown >= 280 units, not sick, not pregnant) 5 job turns 0x42E790
(0x42F10A..0x42F12A; health >= 20 at 0x42E7C5).  A job turn asks the same chooser 0x439AE0; on Farming (1) the
dispatcher 0x4472C0 queues the same trip and the instant runner 0x446C70 plays it with every walk and wait
skipped: the Farming check (type 6 -> 0x43D440) and the reward (type 14 -> 0x43A230) run as live, so one farming
turn is one trip and pays what a live trip pays (A New Home has no catch-up rate).  A catch-up trip never gives up
on a walk (the walks are skipped).
"""
from __future__ import annotations

from vv_game_mechanics_farmers import Trip

TURNS_PER_UNIT = 5          # job turns a counted age unit (0x42F10A..0x42F12A), for all but the last 2 units

# The job chooser 0x439AE0 for a villager whose preference is Farming (+0x3D0 = 1): 15 in 100 nothing (0x439AF3);
# otherwise the best skill, each skill considered on rand(100) > 15 (Farming first, 0x439B35); a choice other than
# Farming switches to the preference on rand(100) <= 85 (0x439C40); then the job happens only when the chosen
# skill is more than 1 and rand(100) < skill + 40 (0x439C80..0x439C9A).  With Farming the villager's highest skill:
# 0.85 x (0.84 + 0.16 x 0.86) = 0.83096 of turns choose Farming, times min(1, (Farming + 40) / 100).  (A villager
# who dislikes work first refuses 70 in 100, 0x439B1D.)
FARMING_CHOSEN = 0.83096


def farming_chosen(farming: int) -> float:
    """Share of job turns (live: of the scheduler's job choices) that choose Farming, for a villager whose
    preference is Farming and whose highest skill is Farming."""
    if farming <= 1:
        return 0.0
    return FARMING_CHOSEN * min(1.0, (farming + 40) / 100.0)


# The dispatcher 0x4472C0, job 1, for a villager remembering a source (record +0x3B8), as emulated:
SOURCE_RULES = (
    "Farming level 1: the bush whenever it has berries (0x44745C); an empty bush: nothing, and the farmer is "
    "reported busy.",
    "Farming level 2: while the bush holds 100 or more and the field is not empty, a farmer set to the bush picks "
    "berries, one set to the field harvests, anyone else picks berries on rand(100) < 50 and otherwise harvests; a "
    "bush under 100: the field; an empty field: watering, for every farmer (0x4473E3..0x44744E).",
    "Farming level 3: with the beach cleaned, fishing on rand(100) < 50 (0x447321) and always for a farmer set to "
    "the sea. Otherwise (and always with a dirty beach) a farmer set to the bush picks berries while the bush holds "
    "100 or more; one set to the field harvests (an empty field: watering); one set to the sea picks berries on "
    "rand(100) < 33 while the bush holds 100 or more and otherwise does nothing; anyone else picks berries on "
    "rand(100) < 33 while the bush holds 100 or more, and failing that (as does a farmer set to the bush once it is "
    "under 100) harvests on rand(100) < 50, else does nothing (0x447349..0x4473D5).",
)

# Trip lengths measured (real-life seconds; trips that paid, starting at the food bin), over the map a new
# village's state builds (0x414590): 400 back-to-back trips of an adult with Farming 89 for each source (no
# big catch below 90), seed 11; the big catch: 400 trips with Farming 100, seed 13.  The same over the map of a
# grown village (the owner's A New Home slot 5 save, every hut built and the beach clean): berries 98.13
# (90.95-109.96), crops 84.91 (64.88-99.92), fish 90.75 (47.88-120.88), big catch 104.58 (94.12-119.89).
TRIP_SAMPLES = {"berry picks": (400, 98.50, 90.95, 108.97), "crop harvests": (400, 84.88, 62.90, 100.88),
                "catches": (260, 92.07, 47.88, 121.87), "big catches": (70, 104.05, 91.91, 117.91)}
SPEEDS = (3, 6, 10)

# A farmer left to the game's own scheduler (0x448220, run from the runner's empty-queue wait 0x448798: one try
# each whole real-life second, 66 in 100 doing nothing at 0x448266), 8 real-life hours each, preference Farming,
# all other skills 10, food kept at 1,000: real-life seconds per trip that brought food, by Farming skill.  It
# includes the failed checks, the walks that gave up, the rests and other jobs the chooser and scheduler pick.
# berries at Farming level 1, crops at level 2 with a bush under 100, fishing at level 3 set to the sea (at
# Farming 100 that is 190 catches and 51 big catches).
LIVE_CYCLE = {"berry picks": {100: 107.9, 50: 118.5, 20: 122.6},
              "crop harvests": {100: 98.6, 50: 115.2, 20: 118.0},
              "catches": {100: 119.5, 50: 142.6, 20: 170.4}}

# Live fishing trips that end at the map's right edge with nothing: the far spot (x 1308-1635, chosen on
# rand(100) > 50, 0x43F689) is walked to twice; a target x of 1563 or more (rand(110) at 0x43F7F9 of 85 or more)
# walks the villager into the edge clamp (record x >= 1540, 0x445F31) before it arrives, which clears its queue:
# 0.49 x (1 - (85/110)^2) = 19.74% of trips from the bin (measured 64 of 324).  Catch-up skips the walks.
# A catch-up job turn of a farmer set to a source runs FARMING_CHOSEN trips on average (catch_up_trips_per_turn):
# Farming the villager's highest skill and 60 or more; below 60 times (Farming + 40) / 100 (farming_chosen), and
# times the dispatcher's share for that source at the village's Farming level (SOURCE_RULES).
FISH_EDGE_LOSS = 0.49 * (1 - (85 / 110) ** 2)


def _live(mean: float) -> dict[int, float]:
    return {speed: mean for speed in SPEEDS}


def _span(low: float, high: float) -> dict[int, tuple[float, float]]:
    return {speed: (low, high) for speed in SPEEDS}


_CLOCK = ("Real-life time, the same at Fast, Normal and Slow (nothing in the walk or the waits reads the speed); "
          "while paused the villagers stand still, and a wait whose moment passes during the pause ends on the first "
          "frame after it. A trip in progress is not saved (the step queue is outside the saved part of the record), "
          "so closing the game loses it.")

TRIPS: tuple[Trip, ...] = (
    Trip(
        key="berry picks",
        job="Farming preference, dropped on the berry bush",
        live_seconds=_live(98.50),
        live_span=_span(90.95, 108.97),
        catch_up_trips_per_turn=FARMING_CHOSEN,
        success_offset=31,
        live_words=("From the food bin: walk to the bush (one of two spots), wait 5-7 s and 2 s, the Farming check, "
                    "wait 5-9 s, walk back to the food bin, wait 2 s, then the berries are credited. " + _CLOCK),
        catch_up_words=("Each job turn that chooses Farming runs one pick at once (0x42E790 -> 0x4472C0 -> 0x441E10 -> "
                        "0x446C70): the Farming check, then the bush / 130, at least 2 (0x43AD62), as live."),
        verified="code",
        extra=("An elder (walking at 40) takes 216.99 s (204.96-237.96); a villager who likes running (300) "
               "46.49 s (41.94-51.94).",
               "A failed Farming check ends the trip near the bush with nothing: 52.90 s on average from the bin.",
               "A villager who dislikes berries or bushes refuses 75 in 100 (0x441E3C).",
               "Live, with the game's own scheduler: 107.9 s per paying trip at Farming 100, 118.5 at 50, 122.6 at "
               "20 (LIVE_CYCLE)."),
    ),
    Trip(
        key="crop harvests",
        job="Farming preference, dropped on the crop field (Farming level 2 or more)",
        live_seconds=_live(84.88),
        live_span=_span(62.90, 100.88),
        catch_up_trips_per_turn=FARMING_CHOSEN,
        success_offset=31,
        live_words=("From the food bin: walk to one of the field's 4 rows (in one of 3 sections), 4 stops along it "
                    "with a 3 s wait at each, the Farming check, walk back to the food bin (26% of trips by a "
                    "waypoint), wait 1 s, then 7 food is credited. " + _CLOCK),
        catch_up_words=("Each job turn that chooses Farming runs one harvest at once: the Farming check, then 7 food "
                        "taken from the field (0x43AEC5), as live. An empty field: no reward (the job then only "
                        "waters, 0x443A43)."),
        verified="code",
        extra=("An elder takes 188.87 s (138.93-234.89); a villager who likes running 39.83 s (34.91-44.91), but 37 "
               "of its 110 trips from the bin used up their 15 detours and gave up (0x43DFE9 -> 0x43DFEE) with "
               "nothing.",
               "A villager who dislikes turnips refuses 75 in 100 (0x443A1E).",
               "Live, with the game's own scheduler: 98.6 s per paying trip at Farming 100, 115.2 at 50, 118.0 at 20 "
               "(LIVE_CYCLE)."),
    ),
    Trip(
        key="catches",
        job="Farming preference, dropped on the sea (Farming level 3, the beach cleaned)",
        live_seconds=_live(92.07),
        live_span=_span(47.88, 121.87),
        catch_up_trips_per_turn=FARMING_CHOSEN,
        success_offset=31,
        live_words=("From the food bin: two walks to a fishing spot (the near shore x 81-330 or the far one x "
                    "1308-1635) with a 1 s wait at each, the Farming check, walk up the beach and back to the food "
                    "bin (26% of trips by one more waypoint), wait 1 s, then 9 food is credited. A villager who "
                    "dislikes fish always refuses (0x43F45B). " + _CLOCK),
        catch_up_words=("Each job turn that chooses Farming and fishing runs one catch at once: the Farming check, "
                        "then 9 food (0x43AF34); with Farming 90 or more 21 in 100 are a crab, 55 food with no "
                        "check (0x43AF86). No walk, so no catch-up trip is lost at the map's edge."),
        verified="code",
        extra=("A crab (Farming 90 or more, 21 in 100, 55 food): 104.05 s (91.91-117.91), then a 10 s "
               "celebration before the next trip.",
               "19.74% of live trips from the bin walk into the map's right edge and bring nothing ("
               "measured 64 of 324), 26.87 s on average.",
               "An elder takes 224.06 s (109.89-295.91); a villager who likes running 33.99 s (18.88-41.91).",
               "Live, with the game's own scheduler: 119.5 s per paying trip at Farming 100 (crabs included), "
               "142.6 at 50, 170.4 at 20 (LIVE_CYCLE)."),
    ),
)
