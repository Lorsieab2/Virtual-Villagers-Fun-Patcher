"""New Believers (VV5): what one farmer brings in, live and while catching up -- measured from the stock exe.

Every number below was measured by running the stock executable's own code in unicorn
(tests/farmers_emulation_vv5.py; re-measured by tests/test_game_mechanics_farmers_vv5.py).

WHO FARMS, AND ON WHICH SOURCE.  A believer's job preference (record +0x1C74) 0 is Farming; the job chooser 0x46A3C0
picks the job (FARMING_CHOSEN) and the work dispatcher 0x46C540, job 0, then takes one of the sources open now at
random (rand(count), 0x46C622): the noni bushes, the Hydroponic Farm's crops, the lake.  Nothing is remembered from
one trip to the next, except the job the player gives by dropping a believer on a source (record +0x1C54: 3 the noni
bushes, 5 the crops, 28 the lake; 0x46BCF0's table 0x46C4B8), which the scheduler keeps asking for first
(PLAYER_KEPT, SOURCE_RULES).  Heathens never reach the chooser (0x46F0BA -> the Heathen routine 0x46E9E0; catch-up
skips them at 0x472CB7).

ONE TRIP.  The dispatcher starts the behaviour (0x465580: 0x6C noni 0x457910, 0x6D crops 0x457C80, 0xE9 fish
0x463B20), which queues its steps (0x473380) and starts the first (0x473590); the villagers' per-frame update
0x471EB0 -> 0x4671E0 -> 0x46F4A0 runs them (0x473B30).  Noni: walk to a point of the noni bushes' area (0x1A), a
1 s gesture, wait 3 s, a 1 s gesture, the Farming check, wait 3 s, walk to the food bin (area 5), 3 s at the bin,
wait 3 s, then the noni are credited (event 12 at 0x46CFCD: max(2, noni / 100), taken off the bushes).  Crops: walk
to a point of the farm (area 0x52), 3 s, wait 3 s, 3 s, the Farming check, wait 3 s, walk to the food bin, 3 s, wait
3 s, then the crops (event 14 at 0x46D0D0: 10, 7 or 4 food on Fast, Normal or Slow, 7 while catching up, taken off
the crops).  Fish: walk to a point of the lake's shore (area 0x69), wait 3 s, the Farming check, walk to the food
bin, wait 3 s, then 4 food (event 16, 0x46D790).  Every payoff goes through the food writer 0x41EB40 (Food Mastery
x1.5 / x2 there).  The Farming check is the skill check 0x46B270 (step 10): it passes when rand(100) <= Farming + 33
(0x46B30A..0x46B311), i.e. (Farming + 34) times in 100 (+15 / +30 at Learning 2 / 3, 0x46B2BE..0x46B2D9; 66 instead
of 33 for a villager who likes learning, 16 for one who dislikes it); a failure clears the queue (0x46B362) and
the villager shakes its head (behaviour 0x25), so the trip ends at the source with nothing.

LIVE TRIP TIME (real-life seconds, the same at Fast, Normal and Slow).  Measured by running the villagers' per-frame
update 0x471EB0 frame by frame with the game's own frame time: the frame limiter 0x40965B..0x409688 holds each frame
to 1000 // 30 = 33 ms (30 frames a second, the settings' slot 0x402FB0; the setter 0x4080E0 from 0x402C48).  The
walk 0x468FF0 moves the villager by its speed / 100 pixels a frame, split between x and y in proportion (0x465D40;
re-aimed every 10 frames, 0x4690BE..0x4690DE) along the path 0x47AE30 finds on the walk map (lcmap.dat, 320 x 320
cells, loaded by 0x4775B0).  A believer walks at 100 (1 pixel a frame, 30.3 pixels a real-life second); 300 for an
adult who likes running or a child who does not dislike it (not while sick, 0x465983..0x4659BF); 40 for an elder
(age 840 + 160 x Medicine level units or more: 50, 58 or 66 years, 0x46F790) or for one who dislikes running
(0x4659D4..0x465A06).  Health, skills and Faith do not change the walk.  Every wait ends on the game's real clock
0x4036E0 (whole real-life seconds, time() minus the save's base): a step of n seconds ends on the first frame its
start + n is passed (0x475460), so it lasts n to n + 1 s.  Nothing in the update, the walk or the waits reads the
speed value except to stop while paused (0x442AD5: speed 999 skips 0x471EB0); the emulation gave identical trips,
frame for frame, at speed 3, 6 and 10.  The Time Warp God Power runs the update its rate times a frame
(0x471EF9..0x471F11) and divides each wait by it (0x4735A3).  A trip is timed from the frame it starts (the villager
standing at the food bin where its last trip ended) to the frame its food is credited; TRIP_SAMPLES says what was
measured.

Stubbed in the emulation: RNG(n) 0x403660 (a seeded uniform value), the real clock (the emulated real time), the C
runtime's locks, heap and files, and drawing and sound only (every SDL2, SDL2_image and FMOD import; an image is a
stand-in of a fixed size -- with each image's real size the trips are frame for frame the same).  Not emulated: the
framework's own frame timing outside the exe (SDL_Delay's accuracy), so a frame is taken as exactly 33 ms; a
computer that cannot draw 30 frames a second walks the villagers more slowly in real time (the waits are
unchanged).  The 2-second village update (ageing, eating, weather) is not run, so no rain sends a farmer to shelter.

CATCH-UP.  For each counted age unit the life pass 0x472C90 (repeated, 0x47336A -> 0x472CA0, until no believer is
behind) charges each believer's meal once (0x472D66..0x472DF6: 2 food above 500; at 500 or less 2 food on
rand(100) < 50, otherwise 1 health on rand(100) < 30; 2 more on rand(100) <= 75 on Medium with 8,000 food or more
left after that meal and on Hard, never on Easy; children eat too, Heathens never) and, for every unit but the last
2 (0x4732EB), gives each adult (age shown >= 280 units, not sick, not pregnant or nursing) 4 job turns 0x46E8E0
(0x473311..0x473326) with the catch-up flag manager+0x17E10 set (0x47330A).  A job turn needs 20 health (0x46E90B), asks the same chooser 0x46A3C0, then the player's job 0x46BCF0
(if one is set), then at 250 food or less Farming 20+ farms (0x46E985), otherwise the dispatcher 0x46C540 with the
chooser's job; the instant runner 0x46E020 then plays the queued steps with every walk an instant move (0x466300) and
every wait skipped: the Farming check (step 10 -> 0x46B270) and the payoff (step 20 -> 0x46CE60) run as live, so one
farming turn is one trip.  Crops pay 7 at every speed (0x46D0D7); noni and fish pay as live.  The dispatcher offers
noni while catching up only once The Hungry Totem is solved (0x46C5B5..0x46C5D0), but a believer the player dropped
on the noni bushes keeps picking them without it (0x46BE86 checks only that more than 3 noni are left).
"""
from __future__ import annotations

from vv_game_mechanics_farmers import Trip

TURNS_PER_UNIT = 4          # job turns a counted age unit (0x473311..0x473326), for all but the last 2 units

# The job chooser 0x46A3C0 for a villager whose preference is Farming (+0x1C74 = 0): 15 in 100 nothing (rand(100)
# < 15, 0x46A3D4; not for a villager who likes work); a villager who dislikes work: nothing on rand(100) < 70 more
# (0x46A415); otherwise each skill is considered on rand(100) > 15 (Farming first, 0x46A428) and the highest wins
# (Parenting only for a Children-preference villager); a choice other than Farming switches to the preference on
# rand(100) <= 85 (0x46A575); then the job happens only when the chosen skill is more than 5 and rand(100) <
# skill + 40 (0x46A594..0x46A5A6).  With Farming the villager's highest skill: 0.85 x (0.84 + 0.16 x 0.86) = 0.83096
# of choices are Farming, times min(1, (Farming + 40) / 100) -- as in A New Home.
FARMING_CHOSEN = 0.83096
# The player's job 0x46BCF0 (a believer dropped on a source, Farming 6 or more, the granary made): kept unless
# rand(100) < 20 (0x46BD1F), or rand(100) < 40 (0x46BD2E) with 8,000 food or more or a dislike of work; always for
# a believer who likes work (0x46BD04).  Neither liking nor disliking work: 80 in 100 below 8,000 food, 48 above.
PLAYER_KEPT = 0.8
PLAYER_KEPT_RICH = 0.48
SOURCES = 3                 # noni, crops and the lake, each open (the dispatcher picks one at random, 0x46C622)


def farming_chosen(farming: int) -> float:
    """Share of the chooser's picks (live: of the scheduler's tries that look for work; catch-up: of job turns)
    that choose Farming, for a villager whose preference is Farming and whose highest skill is Farming."""
    if farming <= 5:
        return 0.0
    return FARMING_CHOSEN * min(1.0, (farming + 40) / 100.0)


def catch_up_trips(farming: int, food: int = 1000, sources: int = SOURCES) -> float:
    """Trips on its own source a catch-up job turn runs for a believer the player dropped on that source: the
    player's job first (0x46E97A), the chooser's Farming on the rest, of which 1 in `sources` lands on it."""
    if farming < 6:
        return 0.0
    kept = PLAYER_KEPT if food < 8000 else PLAYER_KEPT_RICH
    return kept + (1 - kept) * farming_chosen(farming) / sources


CATCH_UP_TRIPS = catch_up_trips(100)        # 0.8553973... (Farming 60 or more, food under 8,000, all 3 open)

# The dispatcher 0x46C540, job 0, and the player's job 0x46BCF0, as emulated:
SOURCE_RULES = (
    "Nobody farms until the fence is made into a granary (project 2: the dispatcher 0x46C583; the player's job "
    "0x46BD9B, which also drops the job below Farming 6).",
    "Each Farming choice takes one of the sources open now at random (0x46C622): the noni bushes (more than 3 noni, "
    "0x46C5AC; while catching up only once The Hungry Totem is solved, 0x46C5B5..0x46C5D0), the crops (15 or more "
    "and the Hydroponic Farm restored, 0x46C5DD / 0x46C5E6), the lake (restored, project 10, 0x46C600).  A villager "
    "who dislikes berries refuses noni 60 in 100 (0x46C6F3..0x46C717); one who dislikes fish, the ocean or swimming "
    "refuses the lake 60 in 100 (0x46C647..0x46C699).",
    "A believer the player dropped on a source keeps to it (PLAYER_KEPT: 80 in 100 below 8,000 food, live and while "
    "catching up) before the chooser is asked; that job ends when the noni are down to 3 (0x46BE86, 0x46D012) or the "
    "crops below 15 (0x46BED3).  The dislike refusals above do not apply to it, nor does The Hungry Totem.",
    "At 250 food or less a villager with Farming 20 or more farms first (live 0x46F25E, catch-up 0x46E985); live, "
    "the others whose job is not Farming or Healing only worry about food half the time (0x46F299..0x46F2BC).",
)

# Trip lengths measured (real-life seconds; trips that paid, starting at the food bin), over the stock walk map
# (lcmap.dat) of a new village with the granary, The Hungry Totem, the Hydroponic Farm and the lake done: 400
# back-to-back trips of an adult believer with Farming 89 (every check passes) for each source, seed 11.
TRIP_SAMPLES = {"noni picks": (400, 94.36, 90.88, 98.90), "crop harvests": (400, 88.12, 82.90, 93.92),
                "fish": (400, 106.39, 89.89, 134.90)}
SPEEDS = (3, 6, 10)

# A believer left to the game's own scheduler (0x46F070, run from the empty-queue wait 0x46F4A0: one try at each new
# whole real-life second, 66 in 100 doing nothing at 0x46F0D9), dropped on the source (+0x1C54 3, 5 or 28), preference
# Farming, all other skills 10, food kept at 1,000, noni at 1,000 and crops at 800: real-life seconds per trip that
# brought food from that source, by Farming skill, over 32 emulated hours (4 runs of 8, seeds 31-34: 1,005, 962 and
# 795 noni picks; 1,060, 1,004 and 853 harvests; 924, 882 and 724 catches).  It includes the failed checks, the
# rests, and the trips the chooser sends to the other sources instead (about 1 in 8; their food is not counted
# here).  One 8-hour run differs from another by up to 7% (noni at Farming 100: 229 to 264 picks), so the 32-hour
# figures are good to about 3%, not 1%.  A believer not dropped anywhere (Farming 100, seed 31, 8 hours) made 263
# paying trips, 101 noni, 76 crops and 86 fish: 109.5 s per paying trip of any source.
LIVE_CYCLE = {"noni picks": {100: 114.6, 50: 119.8, 20: 144.9},
              "crop harvests": {100: 108.7, 50: 114.7, 20: 135.1},
              "fish": {100: 124.7, 50: 130.6, 20: 159.1}}

CROP_LIVE_FOOD = {3: 10, 6: 7, 10: 4}       # 0x46D0E7..0x46D103: Fast 10, Slow 4, any other speed 7


def _live(mean: float) -> dict[int, float]:
    return {speed: mean for speed in SPEEDS}


def _span(low: float, high: float) -> dict[int, tuple[float, float]]:
    return {speed: (low, high) for speed in SPEEDS}


_CLOCK = ("Real-life time, the same at Fast, Normal and Slow (nothing in the walk or the waits reads the speed); "
          "while paused the villagers stand still (0x442AD5), and a wait whose moment passes during the pause ends on "
          "the first frame after it. A trip in progress is not saved (the step queue, the record's first 0x1B80 "
          "bytes, is not among the fields the save loader 0x466B60 restores), so closing the game loses it.")


def _cycle_words(key: str) -> str:
    c = LIVE_CYCLE[key]
    return (f"Live, with the game's own scheduler: {c[100]:g} s per paying trip at Farming 100, {c[50]:g} at 50, "
            f"{c[20]:g} at 20 (LIVE_CYCLE).")


TRIPS: tuple[Trip, ...] = (
    Trip(
        key="noni picks",
        job="Farming preference (the noni bushes are one of the sources), or dropped on the noni bushes",
        live_seconds=_live(TRIP_SAMPLES["noni picks"][1]),
        live_span=_span(*TRIP_SAMPLES["noni picks"][2:]),
        catch_up_trips_per_turn=CATCH_UP_TRIPS,
        success_offset=34,
        live_words=("From the food bin: walk to the noni bushes, a 1 s gesture, wait 3 s, a 1 s gesture, the Farming "
                    "check, wait 3 s, walk back to the food bin, 3 s there and wait 3 s, then the noni are credited "
                    "(each wait lasts its seconds to one more). " + _CLOCK),
        catch_up_words=("Each job turn that farms the noni runs one pick at once (0x46E8E0 -> 0x46C540 or 0x46BCF0 -> "
                        "0x457910 -> 0x46E020): the Farming check, then max(2, noni / 100) food (0x46CFCD), as live. "
                        "The dispatcher offers noni only once The Hungry Totem is solved; a believer dropped on the "
                        "bushes picks them without it."),
        verified="code",
        extra=("An elder (walking at 40) takes 209.28 s (200.90-217.90); a believer who likes running (300) 44.20 s "
               "(43.89-45.90).",
               "A failed Farming check ends the trip at the bushes with nothing: 49.33 s on average from the bin.",
               "A villager who dislikes berries refuses 60 in 100 when the dispatcher picks the noni (0x46C717).",
               _cycle_words("noni picks")),
    ),
    Trip(
        key="crop harvests",
        job="Farming preference (the crops are one of the sources once the Hydroponic Farm is restored), or dropped "
            "on the crops",
        live_seconds=_live(TRIP_SAMPLES["crop harvests"][1]),
        live_span=_span(*TRIP_SAMPLES["crop harvests"][2:]),
        live_food=dict(CROP_LIVE_FOOD),
        catch_up_food=7,
        catch_up_trips_per_turn=CATCH_UP_TRIPS,
        success_offset=34,
        live_words=("From the food bin: walk to the Hydroponic Farm, 3 s, wait 3 s, 3 s, the Farming check, wait 3 s, "
                    "walk back to the food bin, 3 s there and wait 3 s, then the crops are credited: 10, 7 or 4 food "
                    "on Fast, Normal or Slow (the speed when it is credited). " + _CLOCK),
        catch_up_words=("Each job turn that farms the crops runs one harvest at once: the Farming check, then 7 food "
                        "at every speed (0x46D0D7..0x46D0E0), taken off the crops."),
        verified="code",
        extra=("An elder takes 188.22 s (176.88-197.90); a believer who likes running 44.87 s (43.89-45.90).",
               "A failed Farming check ends the trip at the farm with nothing: 48.39 s on average from the bin.",
               _cycle_words("crop harvests")),
    ),
    Trip(
        key="fish",
        job="Farming preference (the lake is one of the sources once it is restored), or dropped on the lake",
        live_seconds=_live(TRIP_SAMPLES["fish"][1]),
        live_span=_span(*TRIP_SAMPLES["fish"][2:]),
        catch_up_trips_per_turn=CATCH_UP_TRIPS,
        success_offset=34,
        live_words=("From the food bin: walk to a point of the lake's shore (area 0x69), wait 3 s, the "
                    "Farming check, walk back to the food bin, wait 3 s, then 4 food is credited. " + _CLOCK),
        catch_up_words=("Each job turn that farms the lake runs one catch at once: the Farming check, then 4 food "
                        "(0x46D790), as live."),
        verified="code",
        extra=("An elder takes 262.13 s (219.88-330.92); a believer who likes running 41.65 s (33.89-49.90).",
               "A failed Farming check ends the trip at the lake with nothing: 55.84 s on average from the bin.",
               "A villager who dislikes fish, the ocean or swimming refuses 60 in 100 when the dispatcher picks the "
               "lake (0x46C699).",
               _cycle_words("fish")),
    ),
)
