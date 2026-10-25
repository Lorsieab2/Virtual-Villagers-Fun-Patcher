"""Game Mechanics for A New Home (VV1): read-only lines from one save (src/vv_game_mechanics.py).

THE SAVE.  "<base><slot>.ldw" (0xABE8 bytes): "ldwg", the clock's epoch G (Unix seconds), the buffer's
length 0xABDC, then the game state from state+8 on -- so a state offset S is file offset S + 4.  Every
offset below is a FILE offset (little-endian int32).  A clock value v is the real moment G + v: A New
Home's clock counts real seconds, and the speed only sets how long an age unit takes.

  food 0xA2F0, tech points 0xA300, berry bush 0xA2F8, crop field 0xA2FC, speed 0xA31C (3 Fast, 6 Normal,
  10 Slow; + 999 while paused), tech levels Spirituality / Science / Construction / Medicine / Fertility /
  Farming at 0xA2C0 + 8k; the save moment 0xA308, the next regrowth 0xA2F4, the next island event
  0xA304, the village's creation 0x9E20; Mushrooms Found 0x9E34.

THE RULES (static reading of the stock executable; the research notes are in the coordinator's
scratchpad spec, mech_vv1\\spec.md, 2026-10-23):
  * An age unit is 60 x speed real seconds (3 / 6 / 10 minutes); 20 units are a year (the world tick
    0x42E900).
  * Eating: 2 food per villager per unit (0x42ECCC).
  * Regrowth every 40 units (0x42EC0D): the berry bush +30; at Farming level 2 or more the crop field
    +800 up to 800 (0x42F2C5).  Changing speed rescales the time left (0x42E830); pausing freezes the
    timer (0x42E90A).  On load every missed regrowth is applied, without a cap (the 0x42EBF0 loop).
  * A pick from the bush gives bush / 130, at least 2 (0x43AD62); a crop harvest 7 (0x43AEC5); a catch
    9, or at Farming skill 90+ a 21% chance of 55 (0x43F4A7) -- fishing needs Farming level 3 and the
    beach cleaned.
  * Research gives Research / 7, / 5 or / 3 at Science level 1, 2 or 3, after a (Research + 31)% roll
    (0x43B2AB).
  * Mushrooms: while none is out, a 2-in-120 roll every 2 real seconds (0x42351E), so about 2 real
    minutes' wait at any speed; one stays 60 real seconds (0x42352F) at one of 9 spots; 8 food, or 45
    for the 5% big kind (0x43AFEF / 0x43B04C).  Mushrooms are not saved.  A New Home has no collectibles.
  * Island events: after the first two, every 12 to 23 real hours at any speed (0x423886); the timer
    freezes while paused; after an absence at most one fires.
  * Time away (0x42EA62): how much counts is shown only from vv_game_mechanics.AWAY_LIMITS, the verified
    table.  A save left paused gets no catch-up (credit zeroed, 0x42EACE) -- a static reading, not yet
    confirmed in game.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm
import vv_game_mechanics_death as death
import vv_game_mechanics_life as life

GAME = 1
LENGTH = 0xABDC
FOOD, TECH, BUSH, FIELD, SPEED = 0xA2F0, 0xA300, 0xA2F8, 0xA2FC, 0xA31C
LEVELS = 0xA2C0
SCIENCE, FARMING = 1, 5                       # the level's index: Spirituality, Science, ... Farming
SAVED, REGROW, EVENT, CREATED = 0xA308, 0xA2F4, 0xA304, 0x9E20
MUSHROOMS_FOUND = 0x9E34
EVENTS_SEEN = 0x9E44                          # the Island Events statistic
UNIT = 360                                    # an age unit, in Normal-speed seconds (60 x 6)
REGROW_UNITS = 40
FIELD_CAP = 800
GOLDEN = "vv1_super_secret_golden_mushroom"
LEARNING = "vv1_learning_never_fails"
MAGIC_FRUIT = "vv1_magic_fruit_alters_mortality"

# The island events, each outcome and its odds, and life -- all verified by emulation (the coordinator's spec
# mech_vv1\spec.md v2, sections 5 and 7).
EVENT_LINES = (
    "Each event is a story event 20% of the time, a village event 40% and a crate or vial 40%; within each kind "
    "every event whose conditions hold is equally likely. The story events and their choices follow (what each "
    "choice does is not yet confirmed).",
    "Story events: Trapped Whale (Spirituality below 3): free it, Spirituality +1 level; harvest it, +1,000 food. "
    "Strange Berries (taste): 51% the villager becomes 12 and a half, 49% death. Old Drum: cut it, Healing 100; "
    "play it, bush +500. Mysterious Face (look): 51% the villager vanishes, 49% a stranger of 14 joins (or the "
    "villager vanishes if there is no room).",
    "Visitor (Medicine below 3): allow, Medicine +1 level; refuse, the villager falls sick and everyone else at "
    "75%. Mysterious Vial, red (drink): 50% everyone else sick, 50% Healing 100. Troubled Child (a child): "
    "farming, Farming +50 and sick; research, Research 100 and +3,000 tech points. Mysterious Vial, blue (drink): "
    "50% the villager becomes 4 years old, 50% nothing.",
    "Suspicious Monkey (a child): scare it, -50 health; wait, Healing +60. Wild Mushroom (taste): 50% Farming +65 "
    "and 300 to 499 food, 50% sick and -25 to -49 health. Black Pearl: share it, everyone +5 to 9 health; keep "
    "it, dislikes crowds and work. The Dream: the right cave, dislikes fish and the ocean; the left, nothing.",
    "The Moth: help it, nothing; leave it, Healing 100. The Book: read it, the villager vanishes; give it to the "
    "researchers, nothing. Brass Compass: mash it, everyone Farming +10 to 19; give it to the researchers, +2,000 "
    "to 4,999 tech points. Skills stop at 100.",
    "Village events (n is a third of the population, 1 to 10): Bad Little Monkey -900n tech points; Plague of "
    "Parrots bush -200n; Plague of Locusts (Farming 2 or more) the field emptied; Measles Epidemic (a child) every "
    "child sick; South Wind -80n from food, bush and field; Heat Wave sets each villager to one of two idle "
    "actions, nothing else; Isola Day and Blessings Day -10 food a villager and a gathering of the village.",
    "Big Wave (the beach cleaned) dirties the beach again; Good Little Monkey +900n tech points; Greedy Little "
    "Monkey +200n food; Barrel O' Babies (room) 1, 2 or 3 children of 3.5 to 4.45 years for n under 5, 5 to 7, 8 or more; North Wind "
    "bush and field +100n; Helpful Honeybees bush +300n.",
    "Crates and vials, 1 in 9 each; small 33%, medium 34%, large 33%: wooden +500/1,000/1,500 food; sealed "
    "+1,000/2,000/3,000 tech; weathered +500/1,000/1,500 tech and each villager sick at 15/20/25%; rotting the "
    "opener sick and -15 health, each villager sick at 20/30/45% with -10/-15/-20 health; watertight 1/2/3 "
    "children of 3.5 to 4.45 years if there is room.",
    "Fruit crate: the opener -40/70/110 health (a large one is fatal); red vial a new head; blue vial one skill "
    "+50/75/100; fizzy vial every skill -30/50/70. Leaving a crate or pouring a vial out changes nothing.",
)
# Chance and timers (the coordinator's spec mech_vv1\spec.md, "Chance and timers (complete index)"):
# (line, verified on a traced path).  The full index of every roll is in the claims export.
CHANCE_LINES = (
    ("Every roll that changes play: a mushroom 2 in 120 each 2 seconds with none out, big 5 in 100; the island "
     "event kind and its next time; the event choices; crates and vials; rationing 50%, waste 76%, starving 76%; "
     "health regained 50% (20% for the elderly); falling sick; old age; the scheduler's 66% of nothing; the job "
     "chooser; the food source; skill success and gain; the embrace below 400 food (26%) and conception; twins "
     "7%, triplets 25% of twins; injuries 2%; rest +1 health 50%; an examined hut repaired 70%.", True),
    ("Sick damage (71%, about 22% at 20 health or less), the catch-up embrace (6%) and healing, the crab catch "
     "(21%), dislike refusals and the story events' outcomes.", False),
    ("Every frame some map effects are rolled (1 in 20 of 1,000, 3 in 20, 3 in 25,000) depending on the puzzles; "
     "what they draw is not yet worked out, and their rate follows the frame rate.", False),
    ("64 more functions roll the dice (walking, animation, speech, villager creation and others): not individually "
     "worked out.", False),
    ("Timers: an age unit 3, 6 or 10 minutes (aging, eating, sickness, health, pregnancy, birthdays); regrowth 2 "
     "hours, 4 hours or 6 hours 40 minutes, every missed one added on load; island events 30 minutes after the "
     "first, then 12 to 23 hours, at any speed; the 2-second village step; the 40-second idle sweep; a mushroom "
     "lasts 1 minute.", True),
    ("A new village's first island event 15 minutes after it is made; the tutorial mushroom 1 minute 40 seconds; "
     "step and screen timers.", False),
    # The Golden Child's timer (0x447A14..0x447A57): the full rule is in GOLDEN_CHILD_LINES.
    ("The Golden Child's cave timer: 36 real hours after his birth, at any speed; see Golden Child.", True),
    ("The game may also save every 10 minutes while playing; this has not been seen in a game.", False),
)
LIFE_LINES = (
    "A baby is born 41 age units after conception. Conception: a roll of 300 at or under Parenting - 50 + 50 x "
    "Fertility level (1, 51 or 101 in 300 at Parenting 0, 50, 100 and Fertility 1); below 400 food only 26% of "
    "embraces get that far. Twins 7% with Fertility 3 or the strange fish; a quarter of twins are triplets, "
    "needing both.",
    "Babies need room: under 15 people always; 15 or more need the first hut, 25 the second, 50 the third; none "
    "at 90. Villagers work from 14 and have children from 18.",
    "Sickness each age unit (14 and older): 1 in 600, 1 in 1,200 or 3 in 10,000 at Medicine 1, 2, 3; past 50, 58 "
    "or 66 years 1.5% more. Children never fall sick on their own (only The Measles Epidemic makes them sick). "
    "With food and not sick, a villager regains 1 health half the "
    "age units (every one on Easy); past 50, 58 or 66 years 10% (20% on Easy).",
    "Building trips: huts 250, 400 and 600; the beach 75 (each counts 2); the blockage 350; the field 200; digging "
    "800; the ruins 1,000; chiseling 1,350 (the last two half as many at Building 90 or more). Each trip injures 2% "
    "of the time; an examined hut is repaired 70% of the time.",
)

# Hidden villager stats (the coordinator's specs hidden_vv1\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
HIDDEN_LINES = (
    ('A villager has no hidden fertility, learning rate, lifespan, aging rate, mood, hunger or energy value: '
     'the save keeps 39 numbers and the name for each villager, and none of them is such a value.', gm.RUNNING),
    ("Each villager's name number (1 to 100) picks the name, and with the family number (1 to 50) it is the "
     'game\'s "same villager" key; a healer never cures a villager whose two numbers equal the healer\'s own '
     '(brothers and sisters often do).', False),
    ("A baby takes its mother's family number and starts with one skill at 5 to 7: a parent's highest, never "
     'Breeding (Farming 0 instead).', gm.RUNNING),
    # The Golden Child (the owner, 2026-10-23: "I do not think the Golden Child can die of starvation"): the age lock
    # 0x42EB70..0x42EB8E sets his age and processed age to 100 each tick, and the age-unit body runs a villager
    # only while the processed age is below the age (0x42EC74), so he skips eating (0x42ECCC), both starvation
    # drains (0x42ECB7, 0x42ED37), sickness (0x42EDA3, and 0x42E5A4), regaining health and the old-age roll.
    # Emulated on the stock bytes: tests/test_vv1_golden_child_skips_the_age_unit.py.
    ('The Golden Child has family number 199 and is born beside a normal baby; he starts with every skill at '
     '100 and is set back to 5 years old at every age unit, so the game skips him in its age-unit step: he never '
     'eats, never starves, never falls sick, never dies of old age and never regains health.', gm.RUNNING),
    ('Work injuries and island-event health losses do not check for the Golden Child; since he never regains '
     'health, such losses last, and at 0 health he dies.', False),
    ('With 6 or fewer villagers, when one sex has 2 or fewer members, a baby is of the more numerous sex.', gm.RUNNING),
    ("Likes: at birth 70% none, 21% one, 9% two; dislikes the same; a like is never also a dislike.", gm.RUNNING),
    ("Running, liked: a villager of 14 or more runs, three times walking speed. Disliked: a child under 14 "
     "walks instead of running, and the dislike works for adults too.", gm.OWNER),
    ("Disliking work makes 70% of idle picks take no job; disliking medicine passes Healing over half the time. "
     "Fish, disliked: always refuses fishing (\"Running away\"); berries or bushes: refuses foraging 75% of the "
     "time; rocks: refuses clearing the blockage 75%; turnips: skips the crops 75%; drift wood: skips the beach "
     "clean-up 85%.", gm.RUNNING),
    ("Swimming or the ocean, disliked: keeps away from the lagoon and swimming, and dropped in the water, "
     "\"Leaving the water\". Dancing: no dancing, and no dance steps at celebrations and honouring. Flowers: no "
     "garden or flower gathering. Resting: no relaxing in a well-off village. Butterflies and laundry: skipped. "
     "Crowds: sits out village-wide celebrations. Caves: dropped on one cave spot, no action starts. Herbs: "
     "refuses plant-study drops.", gm.RUNNING),
    ("The other likes and dislikes: no effect has been found in the running game. Wandering may ignore running, "
     "and elders may never run.", False),
    ("A New Home's skill test reads only the skill: success at skill + 31%, with no like or dislike of "
     'learning.', gm.RUNNING),
    ('Sick: -1 health on 71% of age units above 20 health, 22% at 20 or below. Health comes back on half the '
     'age units with food and no sickness (every one on Easy), a fifth of that past 50, 58 or 66 years '
     '(Medicine 1, 2, 3). Injuries: 2% of trips, 0 to 14 health building, 0 to 9 researching.', gm.RUNNING),
    ('A New Home has no fire.', gm.RUNNING),
    # Breeding age 18 (the owner): the embrace checks both ages >= 360 (0x43DB35..0x43DB46), the catch-up embrace
    # too (0x446E96, 0x446EA6).  The two 280 checks just before it in the catch-up code (0x446D39, 0x446E28) are
    # the catch-up healers' patient test, not a breeding gate.  Under-14s never fall sick at random (0x42E590), but The
    # Measles Epidemic (handler 0x4284FA) makes every living child sick, and those checks leave them uncured.
    ("Breeding age: every embrace, the catch-up embrace included, needs both villagers 18 or older. The 14-year "
     "checks beside the catch-up embrace in the game's code belong to catch-up healing: there the healer cures "
     "only patients 14 or older. Children under 14 never fall sick at random, but The Measles Epidemic island "
     "event makes every child sick, and catch-up healing never cures them: drop a healer on each sick child.",
     gm.RUNNING),
)

# The Golden Child (the owner, 2026-10-24: "what is it -- the Cave Opening?").  Traced on the stock executable
# (inputs\vv1-stock-copy), state offsets (a file offset is 4 more); the owner's save and logs agree (Lulu Chuchip:
# born in hour 274, the cave opened in hour 275, male, head 19, body 19, every skill 100, age 100).
#
# The pick (0x448220, each time a villager picks what to do next): rand(100) <= 65 is "Nothing" (0x448266); the sick
# are seen to first (0x44826F; he is never sick); under 14 years the child routine 0x4479B0 runs (0x44828A).  There
# rand(100) <= 15 picks nothing (0x4479BD).  For family 199 (0x4479E5): rand(100) <= 20 runs his own routine
# 0x446920 (0x4479F3), otherwise, when the whole hours since the village was started ((clock - [0x9E1C]) / 3600)
# reach his birth hour [0x9E80] + 36 and the cave [0x9FA8] is shut, he is sent to open it (0x447A14..0x447A57).
# 0x446920: rand(100) <= 25 a show in place (one of three animations, no effect: 0x44692E); otherwise rand(7)
# (jump table 0x446C48): 0 berry bush +400 (effect 37, 0x43B050, message 0x39); 1 at Farming level 2+ the crop field
# +400, no cap (effect 38, 0x43B070, message 0x3A); 2 food +150 and Food Gathered (effect 39, 0x43B090 -> 0x41D140,
# message 0x3B); 3 and 4 nothing; 5 every living villager "Dancing" (0x4407D0; one who dislikes dancing, word 39,
# only stops) and every sick one cured at once, People Cured +1 each ([0x9E2C], 0x446B77); 6 with the cave shut,
# every living villager "Observing" (0x4408A0) and he opens it (0x446BE1).  Opening it (0x445910, "Unblocking the
# Cave"): a walk to the boulder, then effect 1 (0x43ABC4): [0x9FA8] = 1, the map changed (0x414590, 0x416380), the
# hour stamped at [0x9E50] and the message 0x13E.
P_CHILD = 0.34 * 0.84                     # the pick reaches his choices: 34% (0x448266) x 84% (0x4479BD)
P_TIMER = P_CHILD * 0.79                  # the 36-hour branch: 79% (0x4479F3)
P_SHOW = P_CHILD * 0.21 * 0.26            # his routine (21%), the show (26%)
P_ACT = P_CHILD * 0.21 * 0.74 / 7         # his routine, each of the seven acts
GC_FLAG, GC_HOUR, CAVE_FLAG, CAVE_HOUR = 0xA008 + 4, 0x9E80 + 4, 0x9FA8 + 4, 0x9E50 + 4    # file offsets
IDOL_FLAG, BUTTERFLIES_FLAG, GARDEN_FLAG = 0x9FD8 + 4, 0xA088 + 4, 0x9FC0 + 4
FERTILITY = 4                             # the level's index: Fertility ([state+0xA2DC])
CAVE_WAIT_HOURS = 36


def _pc(p: float) -> str:
    return f"{100 * p:.2g}%" if p < 0.1 else f"{100 * p:.1f}%"


GOLDEN_CHILD_LINES = (
    # 0x424150 case 13 (drop area 15, the water; 0x425065), y <= 900 (0x424186, the lagoon; below is the sea):
    # pregnant ([rec+0x358], 0x424242), no Golden Child yet ([0xA008], 0x42424D), The Idol ([0x9FD8], 0x42425B),
    # Fertility level 3 ([0xA2DC], 0x42426E).  0x424289 is the flag's only writer; 0x4242F8 makes him (family 199,
    # 0x4242F3); 0x42431C/0x424326 clear her due and twin count, so the pregnancy is never delivered.
    ("How he is born: drop a pregnant villager into the lagoon after The Idol is done, with Fertility at level 3. "
     "There is no chance roll: those conditions always make him, at once, and otherwise the drop is an ordinary one "
     "into the water. The pregnancy she carried ends there: its baby or babies are never born; the Golden Child takes "
     "their place. The game's message: \"A miracle! One of your villagers gave birth to a special, golden child! No "
     "one can doubt or deny his powers! Behold the Golden Child!\" The game makes only one Golden Child a village.",
     gm.RUNNING),
    # 0x43C7AF..0x43C80C (the creator for family 199); the owner's log (Lulu Chuchip); the owner's rule.
    ("He is born a boy of exactly 5 years (100 age units) and stays 5 for life, with 100 health, every skill at 100, "
     "head 19 and body 19; his likes and dislikes are rolled like anyone's. His family number is 199.", gm.OWNER),
    # 0x42EB70..0x42EC74 (tests/test_vv1_golden_child_skips_the_age_unit.py).
    ("He never eats, never starves, never falls sick, never dies of old age and never regains health: the game "
     "skips him in its age-unit step.", gm.RUNNING),
    # 0x44828A, 0x447B56 ("Meditating" for "Nature is calling!"), 0x447C62 (no "Curious about the cactus"),
    # 0x41FBDC (text 0x5F), parents from 18 (LIFE_LINES).
    ("As a child under 14 he never works and never has children; he picks a child's things to do, except that he "
     "goes \"Meditating\" where another child goes \"Nature is calling!\" and is never \"Curious about the cactus\". "
     "His villager panel shows \"Golden Child\" where others show their skill rank. He can be picked up and dropped "
     "like anyone.", gm.RUNNING),
    # 0x447A14..0x447A57; the clock 0x402F70 is the computer's time less the save's base (difftime, 0x44B6FE).
    (f"The 36-hour action is the Cave Opening. From {CAVE_WAIT_HOURS} real hours after his birth, while the cave is "
     f"still shut, each time he picks what to do there is a {_pc(P_TIMER)} chance (34% x 84% x 79%) that he walks to "
     "the giant boulder (\"Unblocking the Cave\") and opens the cave. Exactly: the whole hours since the village was "
     "started must reach his birth hour (the Puzzles screen's) plus 36, so it starts 35 to 36 real hours after his "
     "birth (36 to 37 if he was born in the village's first hour).", gm.RUNNING),
    ("The 36 hours are real hours on the computer's clock: 36 hours on Slow, Normal and Fast alike (10.8, 18 or 36 game "
     "years, though he never ages). They count while the game is paused or closed; the load-time catch-up does "
     "nothing for him; each Origins Time Warp moves the clock on 12 hours on Fast or Normal and 10 hours on Slow, which "
     "counts towards them.", gm.RUNNING),
    # 0x4479F3, 0x446920, 0x446C48 (see the comment above GOLDEN_CHILD_LINES).
    (f"His own acts, at any time from his birth: each time he picks what to do, {_pc(P_SHOW)} a short show where he "
     f"stands (nothing else happens), and {_pc(P_ACT)} each of: the berry bush +400 (\"The Golden Child magically "
     "created berries!\"); at Farming level 2 or more the crop field +400, even past 800 (\"The Golden Child restored "
     "the crops!\"); +150 food, counted in Food Gathered (\"The Golden Child magically created food!\"); every living "
     "villager stops to dance (one who dislikes dancing only stops) and every sick villager is cured at once, each "
     "counted in People Cured; and, while the cave is shut, opening the cave with every living villager "
     "\"Observing\". So the cave can open before the 36 hours. Two in seven of these picks do nothing (three in seven below "
     "Farming level 2).", gm.RUNNING),
    # 0x43ABC4 (effect 1), 0x424635 / 0x4245F1 (drop areas 2 and 18), word 10 "caves".
    ("Opening the cave: the boulder is gone, the Puzzles screen records the hour, and the game's message reads \"The "
     "magical Golden Child moved the giant boulder and opened the cave! Maybe more clues about Isola's mysteries are "
     "waiting to be found inside...\". It happens once: with the cave open he never tries again. From then dropping a "
     "villager on the cave takes the game to the cave's own screen (on one of its two spots a villager who "
     "dislikes caves starts nothing).", gm.RUNNING),
    # 0x424B3A (drop area 32 with The Garden [0x9FC0]), 0x43F380 ("Calling Butterflies!"), effect 29 (0x43A4F7).
    ("The Butterflies: once The Garden is done, drop him on the garden: he goes \"Calling Butterflies!\" and the "
     "puzzle is done (\"The Golden Child called forth a group of beautiful butterflies to grace the new garden!\"). "
     "Anyone else dropped there does the garden's ordinary action.", gm.RUNNING),
    # 0x4243CF: not pregnant, The Magic Fish not found, Farming level 3, skill 0x3C4 at 90 or more.
    ("With Farming skill 100 he can find The Magic Fish of Fertility when dropped into the lagoon at Farming level 3, "
     "like any villager with Farming skill 90 or more.", gm.RUNNING),
    # 0x445910's only callers 0x447A57 and 0x446C3D; effect 29 only from 0x43F380 (0x424B6E); 0x424289.
    ("Only he opens the cave and only he calls the butterflies. If he dies or vanishes first, that village never gets "
     "them: his puzzle cannot be done again.", gm.RUNNING),
    # 0x42EF39: the birth of a pregnancy whose father ([rec+0x394], stored at conception 0x43BC04) is family 199.
    ("A pregnancy fathered by a family-199 villager would bring a second Golden Child at its birth, beside her own "
     "baby; he is always 5 and parents must be 18, so the stock game never reaches it.", gm.RUNNING),
    # Health losses do not check family 199 (HIDDEN_LINES); the island events' villager picks take him like anyone
    # (no family-199 test in their pickers), with the outcomes EVENT_LINES gives.
    ("How he can leave: health he loses never comes back, and at 0 health he dies. In the original game island "
     "events can pick him like any villager: Strange Berries (49% death), a large fruit crate (110 health lost, "
     "fatal from his 100) and the other events' health losses, which add up; Mysterious Face and The Book make the "
     "villager they pick vanish.", gm.RUNNING),
    ("Start Over deletes the village's save: the new village has no Golden Child, and his puzzle can be done again.",
     False),
)


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def facts(village: gm.Village) -> list[gm.Fact]:
    data = village.data
    if len(data) != 12 + LENGTH or data[:4] != b"ldwg" or struct.unpack_from("<I", data, 8)[0] != LENGTH:
        return [gm.Fact("Other", f"{village.save.name} could not be read: it is not an A New Home save.")]
    epoch = struct.unpack_from("<I", data, 4)[0]
    speed_value = _i32(data, SPEED)
    if gm.speed_base(speed_value) not in gm.SPEED_NAMES:
        return [gm.Fact("Other", f"{village.save.name} could not be read: its game speed is not one the game "
                                 "writes.")]
    speed = gm.speed_base(speed_value)
    paused = speed_value >= gm.PAUSED
    on = gm.speed_name(speed)
    level = [_i32(data, LEVELS + 8 * k) for k in range(6)]
    saved = epoch + _i32(data, SAVED)

    def real(at: int) -> float:
        return epoch + _i32(data, at)

    def due(at: int) -> str:
        """A timer as a real date -- or, saved paused, how long after unpausing."""
        if paused:
            return f"{gm.duration(max(0, _i32(data, at) - _i32(data, SAVED)))} after it is unpaused"
        return gm.when(real(at)) if real(at) > village.now else f"{gm.when(real(at))} (when the village is next played)"

    out: list[gm.Fact] = []
    add = lambda group, text, ok=False: out.append(gm.Fact(group, text, ok))  # noqa: E731
    farming = level[FARMING]

    # -- Food sources --------------------------------------------------------------------
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.", gm.SAVE)
    bush = _i32(data, BUSH)
    add("Food sources", f"Berry bush: {bush:,}; a pick takes {max(2, bush // 130):,} from it now (the bush ÷ 130, at "
                        "least 2).", gm.RUNNING)
    add("Food sources", f"Crop field: {_i32(data, FIELD):,} of {FIELD_CAP}; a harvest gives 7.", gm.RUNNING)
    # The big catch is a crab (the owner, 2026-10-23; the code does not name it: 0x43F4A7).
    add("Food sources", "Fishing: 9 a catch, or a crab worth 55 food; it needs Farming level 3 and the beach cleaned "
                        f"(Farming is level {farming}).", gm.RUNNING)
    add("Food sources", "A villager with Farming skill 90 or more has a 21% chance of catching a crab, worth 55 food.")
    add("Food sources", ("Where a farmer goes: at Farming level 1 the bush; at level 2 half the time the bush and "
                         "half the crops (the crops when the bush is under 100); at level 3 with the beach clean fish "
                         "50%, berries 16.5%, crops 16.75%, nothing 16.75% (with a dirty beach berries 33%, crops "
                         f"33.5%, nothing 33.5%). Farming is level {farming}."), gm.RUNNING)

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE, gm.RUNNING)
    add("Refills", f"The berry bush grows 30 {gm.every(REGROW_UNITS * UNIT, speed_value)}"
                   + (f"; the crop field grows 800, up to {FIELD_CAP}, at the same time." if farming >= 2
                      else "; the crop field does not refill below Farming level 2."), gm.RUNNING)
    add("Refills", f"Next regrowth: {due(REGROW)}.", gm.SAVE)
    add("Refills", "Changing the speed rescales the time left.")

    # -- Mushrooms / Collectibles --------------------------------------------------------
    add("Mushrooms", "While none is out, a mushroom appears after about 2 minutes on average, at any speed (even "
                     "while paused), at one of 9 places, and stays 1 minute; it is picked only when you drop a villager on it. It is a brown mushroom worth "
                     "8 food, or 1 in 20 a red (rare) mushroom worth 45.", gm.RUNNING)
    add("Mushrooms", "Mushrooms are not kept in the save.")
    if village.has(GOLDEN):
        add("Mushrooms", gm.golden_line(GOLDEN, "about 4 years of play"), gm.RUNNING)
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.", gm.SAVE)
    add("Collectibles", "A New Home has no collectibles: mushrooms are its only random pickup.", gm.RUNNING)

    # -- Tech points ---------------------------------------------------------------------
    science = level[SCIENCE]
    divisor = {1: 7, 2: 5, 3: 3}.get(science)
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.", gm.SAVE)
    if divisor:
        add("Tech points and effects", (
            f"Research gives the researcher's Research skill ÷ {divisor} (Science is level {science}), after a "
            "(skill + 31)% roll; 2% of tries injure (0 to 9 health)."), gm.RUNNING)
    else:
        add("Tech points and effects", "Research gives no tech points before Science level 1.")
    add("Tech points and effects", "Every job succeeds at (skill + 31)%. A success raises the skill by 10 at 0, by 8 "
                                   "at 10, by 1 at 45; from 46 up by 1 at 26% x (100 - skill)% (14% at 46, 2.6% at "
                                   "90).", gm.RUNNING)
    if village.has(LEARNING) is not False:
        add("Tech points and effects", gm.patch_words(village, LEARNING, "the roll always passes"))

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", (f"Each villager eats 2 food every {gm.duration(60 * speed)} on {on} speed "
                        f"({2 * 3600 / (60 * speed):g} an hour); on Medium above 2,000 food, or on Hard, 2 more 76% of "
                        "the time; never on Easy. At 200 food or less a villager skips the meal half the time and "
                        "loses 1 health."), gm.RUNNING)
    add("Food earned", "With no food, a villager loses 1 health 76% of age units (every one on Hard).")
    add("Food earned", "The Golden Child neither eats nor starves: the age-unit step that feeds and starves the villagers "
                       "skips him.", gm.RUNNING)

    # -- Time away and Time Warp ---------------------------------------------------------
    out.extend(gm.time_away(village, saved, speed_value,
                            "Saved paused: the time away is not counted when it is next played, and the regrowth and "
                            "island event timers move on with the paused time.", unit_seconds=20 * 60 * speed))
    for n, fact in enumerate(out):
        if fact.text.startswith("Saved paused:"):
            out[n] = gm.Fact(fact.group, fact.text, gm.RUNNING)             # verified (spec v2, section 1 and 8)
    add("Time away and Time Warp", "While catching up, an adult more than 2 age units behind tries 5 jobs for every "
                                   "counted age unit.", gm.RUNNING)
    add("Time away and Time Warp", "Every regrowth missed while the game was closed is added when it is next played, "
                                   "with no limit on how many: the bush has no cap, the crop field stops at 800.", gm.RUNNING)
    out.append(gm.time_warp_line(speed_value))

    # -- Island events -------------------------------------------------------------------
    first = (" The first is always a story event, the second 30 minutes later;"
             if _i32(data, EVENTS_SEEN) < 2 else "")
    add("Island events", f"Next island event: {due(EVENT)}.", gm.SAVE)
    add("Island events", f"{first} Island events come every 12 to 23 whole hours, "
                         "each equally likely, at any speed. Paused, the timer waits; after time away at most one "
                         "happens.", gm.RUNNING)
    for n, line in enumerate(EVENT_LINES):
        # Which event is picked is V; the story events' choice outcomes (lines 1 to 4) are not (spec v3, section 7).
        add("Island events", line, False if 1 <= n <= 4 else gm.RUNNING)

    # -- Other ---------------------------------------------------------------------------
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    for line, ok in CHANCE_LINES:
        add("Chance and timers", line, gm.RUNNING if ok else False)
    for line in LIFE_LINES:
        add("Other", line, gm.RUNNING)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)",
                               "The Golden Child does not age. " + gm.patch_words(
                                   village, MAGIC_FRUIT, "with its puzzle done, the rolls start 7 years later")))
    add("Other", (f"An age unit is {gm.duration(60 * speed)} and a year {gm.duration(20 * 60 * speed)} on {on} speed: "
                  "ages, pregnancies and regrowth follow the speed; work, mushrooms and island events do not."), gm.RUNNING)
    add("Other", f"The village was started at {gm.when(real(CREATED))}.", gm.SAVE)
    out.extend(gm.hours_puzzle_lines([name for name, _flag, _hours in PUZZLES],
                                     lambda n: data[PUZZLES[n][1] + 4] != 0,
                                     lambda n: _i32(data, PUZZLES[n][2] + 4), real(CREATED)))
    out.extend(golden_child_facts(village, data, real(CREATED), level))

    # -- The countdowns, and the people and clocks (src/vv_game_mechanics_life.py) ------------
    regrow_at = None if paused else real(REGROW)
    event_at = None if paused else real(EVENT)
    gm.with_due(out, "Next regrowth:", regrow_at, "refill")
    gm.with_due(out, "Next island event:", event_at, "next")
    out.extend(life.sections(_context(village, data, epoch, speed_value, level, bush, saved, regrow_at, event_at)))
    magic = next(flag for name, flag, _hours in PUZZLES if name == "The Magic Plant of Life")
    out.extend(death.facts(village, medicine=level[3], speed_value=speed_value, base=epoch,
                           magic_fruit=data[magic + 4] != 0))
    return out


def _hours(n: int) -> str:
    return f"hour {n:,} of the village"


def golden_child_facts(village: gm.Village, data: bytes, created: float, level: list[int]) -> list[gm.Fact]:
    """The Golden Child subsection: the rules (GOLDEN_CHILD_LINES), then this save's Golden Child, his puzzle and
    the cave's 36-hour timer, with its real moment for the live countdown.  The hour stamps are whole hours since
    the village was started, 1 for 0 (0x4242AD, 0x43AC08); the clock is real time, so the timer runs on while the
    game is paused or closed and its moment is real even in a save left paused."""
    group = gm.GOLDEN_CHILD
    out: list[gm.Fact] = []
    add = lambda text, ok, due=None, kind=None: out.append(gm.Fact(group, text, ok, False, due, kind))  # noqa: E731
    born = data[GC_FLAG] != 0
    born_hour = _i32(data, GC_HOUR)
    cave_open = data[CAVE_FLAG] != 0
    if not born:
        idol = data[IDOL_FLAG] != 0
        fertility = _i32(data, LEVELS + 8 * FERTILITY)
        needs = []
        if not idol:
            needs.append("The Idol done")
        if fertility < 3:
            needs.append(f"Fertility at level 3 (it is level {fertility})")
        add("This village has no Golden Child yet. " + (
            "Everything he needs is in place: drop a pregnant villager into the lagoon." if not needs else
            "First it needs " + " and ".join(needs) + "; then drop a pregnant villager into the lagoon."), gm.SAVE)
    else:
        people = life.people(village) or []
        golden = [p for p in people if p.golden]
        when = gm.when(created + born_hour * 3600)
        if golden:
            for p in golden:
                add(f"{p.name} is this village's Golden Child, born in {_hours(born_hour)} (from about {when}); "
                    f"health {p.health}.", gm.SAVE)
        else:
            add(f"This village's Golden Child was born in {_hours(born_hour)} (from about {when}), but no Golden "
                "Child lives in it now; the game never makes another.", gm.SAVE)
        if cave_open:
            add(f"The cave was opened in {_hours(_i32(data, CAVE_HOUR))}: his 36-hour timer is spent.", gm.SAVE)
        elif not golden:
            add("The cave is still shut, and with no Golden Child it can never open.", gm.SAVE)
        else:
            due = created + (born_hour + CAVE_WAIT_HOURS) * 3600
            if due > village.now:
                add(f"The cave is still shut. His 36 hours are up at {gm.when(due)} (real time, at any speed, paused "
                    f"or not); until then only his {_pc(P_ACT)} act can open it.", gm.SAVE, due, "due")
            else:
                add(f"The cave is still shut and his 36 hours were up at {gm.when(due)}: each time he picks what to "
                    f"do, a {_pc(P_TIMER)} chance he opens it.", gm.SAVE)
        if data[GARDEN_FLAG] != 0 and data[BUTTERFLIES_FLAG] == 0 and golden:
            add("The Garden is done and The Butterflies is not: drop him on the garden.", gm.SAVE)
    out.extend(gm.Fact(group, line, ok) for line, ok in GOLDEN_CHILD_LINES)
    return out


def _context(village: gm.Village, data: bytes, epoch: int, speed_value: int, level: list[int], bush: int,
             saved: float, regrow_at: float | None, event_at: float | None) -> life.Context:
    farming = level[FARMING]
    every = life.every_real(REGROW_UNITS * UNIT, speed_value).removeprefix("every ")
    # The regrowth's own steps (0x42EC0D, 0x42F2C5): +30 to the bush (no limit), +800 up to 800 to the field.
    steps = dict(interval=gm.real_seconds(REGROW_UNITS * UNIT, speed_value), next_at=epoch + _i32(data, REGROW),
                 first_in=life.resumed(max(0, _i32(data, REGROW) - _i32(data, SAVED)), speed_value), rule=gm.RUNNING)
    sources = [life.Source("Berry bush", bush, None, 30 / REGROW_UNITS, regrow_at, f"+30 every {every}", verified=gm.SAVE,
                           step=30, **steps),
               life.Source("Crop field", _i32(data, FIELD), FIELD_CAP, FIELD_CAP / REGROW_UNITS if farming >= 2 else 0.0,
                           regrow_at if farming >= 2 else None,
                           f"refilled to {FIELD_CAP} every {every}" if farming >= 2 else "no refill below Farming level 2",
                           verified=gm.SAVE, step=FIELD_CAP if farming >= 2 else 0, **steps)]
    if farming >= 3:
        sources.append(life.Source("Fishing (Farming level 3, the beach cleaned)", None, unlimited=True,
                                   refill_words="the sea never runs out", verified=gm.RUNNING))
    paused = speed_value >= gm.PAUSED
    golden = village.has(GOLDEN) is True
    ctx = life.Context(
        village, speed_value, saved, _i32(data, FOOD), low_food=200, extra_from=2001, sources=sources,
        tech=_i32(data, TECH), tech_words="Research brings them (the skill ÷ 7, ÷ 5 or ÷ 3 at Science 1 to 3).",
        brown=8, red=45, red_share=0.05, mushrooms_an_hour=30.0, golden=golden,
        mushroom_words="While none is out one appears about every 2 real-life minutes at any speed and stays 1 "
                       "real-life minute; it is picked only when you drop a villager on it, so at most about 30 per "
                       "real-life hour.",
        event_next=event_at,
        event_paused_left=max(0, _i32(data, EVENT) - _i32(data, SAVED)) if paused else None,
        event_rule="It comes 12 to 23 whole real-life hours after the last, each hour equally likely, at any speed; which "
                   "event is drawn then (a story event 20%, a village event 40%, a crate or vial 40%).",
        event_running="Paused, its timer waits; with the game closed it runs on in real time, and after time away at "
                      "most one event happens; the catch-up adds none. A Time Warp does not move it: its only writers are the "
                      "game's own rescheduling (0x423891, 0x42391A, 0x423A37, 0x423A6F) and the Origins Island Event "
                      "(0x456B47; native/shared/island_timer_vv1.inc).",
        medicine=level[3], elderly_from={1: 50, 2: 58, 3: 66}, old_age_from={1: 55, 2: 63, 3: 71}, parents_from=18,
        sick_loss=(0.71, 0.22),
        collectibles=[("Collectibles: A New Home has none; mushrooms are its only random pickup.", gm.RUNNING)],
        limit=life.limit_words(village, None, "nothing for collections (A New Home has none)",
                               "; babies also need room: 15 people or more need the first hut, 25 the second, 50 "
                               "the third"),
        food_words="2 food a villager every age unit; on Medium above 2,000 food, or on Hard, 2 more 76% of the "
                   "time; never more on Easy.",
        trips=[("berry picks", max(2, bush // 130)), ("crop harvests", 7 if farming >= 2 else 0),
               ("catches", 9 if farming >= 3 else 0)])
    return ctx


# The puzzles: each a solved byte and the whole hours since the village was started that its completion writes
# ((clock - [state+0x9E1C]) / 3600, 1 for 0: 0x4245A0), the Puzzles screen's "Completed in N hours"; state
# offsets (a file offset is 4 more), as the patcher's Story Cheat Upgrades and the Village Statistics read them.
PUZZLES = (("The Well", 0xA058, 0x9EA8), ("The Hut", 0x9FE8, 0x9E70), ("The Beach", 0x9FB8, 0x9E58),
           ("The School", 0xA050, 0x9EA4), ("The Lagoon", 0x9FB0, 0x9E54),
           ("The Magic Fish of Fertility", 0xA090, 0x9EC4), ("The Cemetery", 0xA000, 0x9E7C),
           ("Herb Mastery", 0xA080, 0x9EBC), ("The Garden", 0x9FC0, 0x9E5C), ("The Magic Plant of Life", 0xA098, 0x9EC8),
           ("The Temple", 0x9FE0, 0x9E6C), ("The Idol", 0x9FD8, 0x9E68), ("The Butterflies", 0xA088, 0x9EC0),
           ("The Treasure", 0x9FC8, 0x9E60), ("The Cave", 0x9FA8, 0x9E50), ("The Golden Child", 0xA008, 0x9E80))
