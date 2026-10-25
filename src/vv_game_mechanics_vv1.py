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
    (0x43B2AB); every technology starts at level 1 (0x41C43E).
  * The skill check 0x43D440: success at rand(100) <= skill + 30; the gain (50 - skill) x 2 / 10, / 9 for
    Healing.
  * The Game Mechanics audit (2026-10-25) read every line of this page against the stock exe; each table below
    names its addresses.
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
import vv_game_mechanics_events as events
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

# Chance and timers (audited 2026-10-25 against the stock exe): (line, what stands behind it -- gm.RUNNING, gm.CODE,
# or False for UNCONFIRMED).  Each roll's odds are in its own group; this group points to them.
# The sparkles: the village update 0x423390 rolls rand(1000) < 50 at 0x423D47 (three groups, a fourth with The
# Lagoon [0x9FB0], two more with The Treasure [0x9FC8]), rand(20) < 3 at 0x423E30 while The Idol [0x9FD8] is not
# done, rand(25000) < 3 at 0x423ED9 while the cave [0x9FA8] is shut; each calls 0x41AFA0 -> 0x41A960, which only
# fills the 256-entry list of on-screen effects (0x34 bytes each) with a picture.  The new village's first event:
# 0x41C4A9 (now + 900 s); the tutorial mushroom: 0x4234C4 (now + 100 s); the village step every 2 real seconds
# (0x42345D), the idle sweep 40 real seconds after the last (0x4233F9 -> 0x448450).
# The autosave (the owner, 2026-10-25: the games autosave): 0x41BFC0, at the end of the screen switch 0x41B350
# (0x41B8BD, every path of its switch on the screen [0xACB4]), when the real clock time() (0x401E10) has reached
# [0xADEC] sets [0xADEC] = now + 600 and runs the save writer 0x41BF70 -- the slot list (0), the slot ([0xABE4]) and
# its slot + 20 copy -- with a village started ([0x9E1C]) and a slot chosen; the program start sets the first one 600
# seconds on (0x41D484).  No pause test.  0x41BF70 is the routine the menus' quit paths call (0x413635, 0x41418D).
AUTOSAVE = ("Autosave: each time the game switches from one of its screens to another, it "
            "saves the village if 10 real-life minutes have passed since the program started or since its last "
            "autosave: the slot's save, its second copy (\"Virtual Villagers2<slot>.ldw\") and the slot list. The "
            "10 minutes are real-life time, so they count while the game is paused too; with no screen switch "
            "there is no autosave, and quitting normally saves as well.")
CHANCE_LINES = (
    (AUTOSAVE, gm.OWNER),
    ("Every roll that changes play is in its own group, with its exact odds: the mushroom roll (Mushrooms, Chances); "
     "the island event's kind, its time and every outcome, crates and vials (Island events); eating, starving, "
     "health, sickness and old age (Chances); the 66% of picks that do nothing, the job and food-source choices "
     "(Hidden villager stats, Food sources); the skill check and its gain (Tech points and effects); conception, "
     "twins and the baby's sex (Births and gender); work injuries (Death and graves); eating on the food store "
     "(Food earned); the Golden Child's own picks (Golden Child).", gm.CODE),
    ("Each update of the village screen (every frame it draws, so how often depends on the computer) the game also "
     "rolls for sparkle pictures: 50 in 1,000 for three groups (a fourth once The Lagoon is done, two more once The "
     "Treasure is done), 3 in 20 for one near the idol until The Idol is done, and 3 in 25,000 for one at the "
     "boulder while the cave is shut. They are pictures only: they change nothing in the village.", gm.CODE),
    ("The game's other random rolls, in 64 more functions (where villagers walk, which animation and speech they "
     "show, and a new villager's name), were counted but not each traced, so it is not proven that none of them "
     "changes food, health, skills, births or deaths.", False),
    ("Timers: an age unit is 3, 6 or 10 real-life minutes on Fast, Normal or Slow (ageing, eating, sickness, health, "
     "pregnancy, birthdays); regrowth every 2 hours, 4 hours or 6 hours 40 minutes of real-life play, every missed "
     "one added when the game is next played; island events 12 to 23 real-life hours apart at any speed (Island "
     "events); the village step every 2 real-life seconds; the idle sweep every 40 real-life seconds; a mushroom "
     "lies 1 real-life minute.", gm.CODE),
    ("A new village's first island event comes 15 real-life minutes after it is made, and its tutorial mushroom "
     "lies 1 minute 40 real-life seconds.", gm.CODE),
    # The Golden Child's timer (0x447A14..0x447A57): the full rule is in GOLDEN_CHILD_LINES.
    ("The Golden Child's cave timer: 36 real-life hours after his birth, at any speed; see Golden Child.", gm.RUNNING),
)
# Conception, births, health, sickness and the skill check's odds are under Chances and Births and gender; the
# Other group keeps only what those groups do not give.
LIFE_LINES = (
    "Building trips: huts 250, 400 and 600; the beach 75 (each counts 2); the blockage 350; the field 200; digging "
    "800; the ruins 1,000; chiseling 1,350 (the last two half as many at Building 90 or more). Each trip injures 2% "
    "of the time (see Death and graves); an examined hut is repaired 70% of the time.",
)

# Hidden villager stats (the coordinator's specs hidden_vv1\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
HIDDEN_LINES = (
    ('A villager has no hidden fertility, learning rate, lifespan, aging rate, mood, hunger or energy value: '
     'the save keeps 39 numbers and the name for each villager, and none of them is such a value.', gm.RUNNING),
    # The villager maker 0x43C350: the name number rand(100) + 1 (0x43C64D); the family number the one passed in, or
    # rand(50) + 1 when none is (0x43C652..0x43C669).  Catch-up healing 0x446D23..0x446D37 skips a patient with the
    # healer's own name number and family number; live healing finds its patient by record (0x439350), never the
    # healer's own.
    ("Each villager's name number (1 to 100, rolled when it is made) picks the name; its family number is its "
     "mother's at birth, 1 for the Barrel O` Babies' toddlers and The Mysterious Face's stranger, 199 for the "
     "Golden Child, and 1 to 50 at random for a villager the game makes with none. While catching up a healer "
     "never cures a patient whose name number and family number are both its own (the healer and a brother or "
     "sister with the same name); live healing passes over only the healer.", gm.CODE),
    ("A baby takes its mother's family number and starts with one skill at 5 to 7: a parent's highest, never "
     'Breeding (Farming 0 instead).', gm.RUNNING),
    # The owner (2026-10-24): the Golden Child can die from certain outcomes of certain island events.  The code
    # agrees: no island event tests his flag, and the event picker 0x43BCD0(0) takes any living villager.  His
    # health comes back only by eating on the food store (0x4243F3) and The Black Pearl's share (0x41A050) (the
    # owner, 2026-10-25: follow the code).
    ('The Golden Child can die or be lost in island events: The Strange Berries ("Taste": 49% death), the old '
     'fruit crate (strength 3 always kills; any strength hurts), The Mysterious Face ("Get a closer look": '
     '51% never seen again) and The Book ("Read the book": never seen again); The Suspicious Monkey, The Wild '
     'Mushroom and the rotting crate take health that comes back only when he eats on the food store or from The '
     'Black Pearl. See Island events and Golden Child.', gm.OWNER),
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
    # The like test 0x437310 (likes +0x398..+0x3A4) is made once, for running (word 38, 0x43CD33); the dislike test
    # 0x4372E0 (+0x3A8..+0x3B4) at 34 places, for 19 words: 1 2 3 4 5 6 7 10 11 12 15 17 25 30 33 37 38 39 42.  The
    # walking speed 0x43CCF0: running (300) for a child unless running is disliked (0x43CD20), for an adult only when
    # it is liked; past the elderly age (42 + 8 x Medicine years) always 40 (0x43CD43..0x43CD5F).
    ("Every other like does nothing: the game tests a like only for running. The dislikes it never tests do "
     "nothing either: ants, bees, the dark, snakes, wind, rough wood, playing, exploring, blue, green, red, yellow, "
     "drums, bananas, coconuts, sand, sunlight, crab meat, whale meat, fruit, papaya, flies, monkeys, birds, "
     "lifting, surprises, jokes and sleeping (28 of the 47 words). An elderly villager (past 50, 58 or 66 years at "
     "Medicine 1, 2, 3) never runs: the game gives them its slow walk, liked running or not.", gm.CODE),
    # The skill check 0x43D440: no like or dislike is read (the gains are under Tech points and effects).
    ("Learning: liking or disliking it changes nothing in A New Home: the skill check reads only the skill (see "
     "Tech points and effects).", gm.CODE),
    ('A New Home has no fire.', gm.RUNNING),
    # Breeding age 18 (the owner): the embrace checks both ages >= 360 (0x43DB35..0x43DB46), the catch-up embrace
    # too (0x446E96, 0x446EA6).  The two 280 checks just before it in the catch-up code (0x446D39, 0x446E28) are
    # the catch-up healers' patient test, not a breeding gate (Time away has it).
    ("Breeding age: every embrace, the catch-up embrace included, needs both villagers 18 or older.", gm.RUNNING),
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
    # 0x42EB70..0x42EC74 (tests/test_vv1_golden_child_skips_the_age_unit.py): the age lock sets his age and
    # processed age to 100 each tick, and the age-unit body runs only while the processed age is below the age.
    # The sickness roll 0x42E590 also returns "not sick" for family 199 (0x42E5A4).
    ("The game skips him in its age-unit step, so he never has a meal, never starves, never falls sick on his own, "
     "never loses health to sickness, never dies of old age and never regains health there.", gm.RUNNING),
    # 0x4243F3 (drop area 11, food above 0) -> "Eating" 0x43FAD0 -> effect 41 (0x43A26D): below 100 health,
    # rand(100) < 50 gives +1, and 1 food is taken; The Black Pearl's share 0x41A050..0x41A09B adds rand(5) + 5 to
    # every record's health, up to 100.  Neither tests family 199.
    ("Health does come back two ways: dropped on the food store he goes \"Eating\" like anyone (1 food, and below "
     "100 health +1 health 50.05% of the time), and The Black Pearl's \"Share the treasure with the tribe.\" gives "
     "him 5 to 9 like everyone.", gm.CODE),
    # Sick: The Measles Epidemic (0x427DB5: every living villager under 280 age units, so always him), The Visitor's
    # "Tell the stranger to leave.", the red vial's vapour, the weathered and rotting crates, The Wild Mushroom's
    # poison and The Troubled Child's farming (its child picker 0x43BE70 takes any child under 280).  The pick
    # 0x448220 sends a sick villager to the sick routine 0x446420 (0x44826F) before the child routine 0x4479B0.
    ("Island events can make him sick: The Measles Epidemic always does (he is under 14), and so can every event "
     "that makes villagers sick (see Island events). Sickness costs him no health, but while he is sick each pick "
     "goes to a sick villager's things to do, so he does none of his own acts and does not open the cave until a "
     "healer cures him.", gm.CODE),
    # 0x44828A, 0x447B56 ("Meditating" for "Nature is calling!"), 0x447C62 (no "Curious about the cactus"),
    # 0x41FBDC (text 0x5F), parents from 18 (LIFE_LINES).  The drop handler 0x424150 tests no age, so a job drop
    # works for a child too (the School's needs only Research 90, 0x424438); its injuries (Death and graves) have
    # no family-199 test.
    ("As a child under 14 he never takes up work on his own and never has children; he picks a child's things to "
     "do, except that he goes \"Meditating\" where another child goes \"Nature is calling!\" and is never "
     "\"Curious about the cactus\". His villager panel shows \"Golden Child\" where others show their skill rank. "
     "He can be picked up and dropped like anyone, and dropped on a job he does it like anyone, with its injuries "
     "(2% of trips).", gm.CODE),
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
     "created berries!\"); at Farming level 2 or more the crop field +400 (\"The Golden Child restored the "
     "crops!\"), which the game cuts back to 800 within 2 real-life seconds (0x42F2C5); +150 food, counted in Food "
     "Gathered (\"The Golden Child magically created food!\"); every living "
     "villager stops to dance (one who dislikes dancing only stops) and every sick villager is cured at once, each "
     "counted in People Cured; and, while the cave is shut, opening the cave with every living villager "
     "\"Observing\". So the cave can open before the 36 hours. Two in seven of these picks do nothing, one more "
     "below Farming level 2 and one more once the cave is open.", gm.RUNNING),
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
    ("How he can leave: at 0 health he dies, and health he loses comes back only by eating on the food store or "
     "The Black Pearl (above). In the original game island events can pick him like any villager: Strange Berries "
     "(49% death), a large fruit crate (110 health lost, fatal from his 100) and the other events' health losses, "
     "which add up; Mysterious Face and The Book make the villager they pick vanish.", gm.RUNNING),
    # The new-village set-up 0x41C38A..0x41C39E clears every puzzle flag (0x9F9C + 8k, 99 of them, the Golden
    # Child's 0xA008 and the cave's 0x9FA8 among them) and 0x41C403 the hour stamps.
    ("A new village (Start Over) begins with every puzzle unsolved, The Golden Child's included, so he can be made "
     "again there.", gm.CODE),
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

    # -- Food sources (the food in storage is under Vital statistics) ---------------------------
    bush = _i32(data, BUSH)
    # A pick (effect 14, 0x43AD62): the bush / 130 (0x7E07E07F >> 38), at least 2, taken from the bush; a harvest
    # (effect 15, 0x43AEC5) 7, taken from the field (0x43AF0E); a catch (effect 16, 0x43AF34) 9.
    add("Food sources", f"Berry bush: {bush:,}; a pick brings {max(2, bush // 130):,} food now and takes as much from "
                        "the bush (the bush ÷ 130, at least 2).", gm.RUNNING)
    add("Food sources", f"Crop field: {_i32(data, FIELD):,} of {FIELD_CAP}; a harvest brings 7 food and takes 7 from "
                        "the field.", gm.RUNNING)
    # The big catch is a crab (the owner, 2026-10-23; the code does not name it): fishing 0x43F450 -- a villager who
    # dislikes fish runs away (0x43F45B); Farming skill 90 or more (0x43F4B0) and rand(100) <= 20 (0x43F4C3) is the
    # 55-food catch (effect 17, 0x43AF86), otherwise 9.
    add("Food sources", "Fishing: 9 food a catch; a fisher with Farming skill 90 or more instead catches a crab worth "
                        "55 food 21.02% of the time. Fishing needs Farming level 3 and the beach cleaned (Farming is "
                        f"level {farming}).", gm.CODE)
    add("Food sources", ("Where a farmer goes: at Farming level 1 the bush; at level 2 half the time the bush and "
                         "half the crops (the crops when the bush is under 100); at level 3 with the beach clean fish "
                         "50%, berries 16.5%, crops 16.75%, nothing 16.75% (with a dirty beach berries 33%, crops "
                         f"33.5%, nothing 33.5%). Farming is level {farming}."), gm.RUNNING)

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE, gm.RUNNING)
    # The regrowth loop 0x42EBF0: next += 2,400 x the speed real seconds, the bush +30, the field +800 at Farming 2
    # or more; the world tick's tail cuts the field to 800 (0x42F2C5).  Pausing pushes the timer on (0x42E936).
    add("Refills", f"The berry bush grows 30 every {gm.duration(gm.real_seconds(REGROW_UNITS * UNIT, speed))} of "
                   f"real-life play on {on} speed" + (" once unpaused" if paused else "")
                   + (f"; the crop field grows 800, up to {FIELD_CAP}, at the same time." if farming >= 2
                      else "; the crop field does not refill below Farming level 2."), gm.RUNNING)
    add("Refills", f"Next regrowth: {due(REGROW)}.", gm.SAVE)
    # 0x42E830: on a change of speed the time left becomes (time left) x new ÷ old, a paused speed counting as Normal.
    add("Refills", "Changing the speed changes the time left to the next regrowth in proportion: from Normal to Fast "
                   "it halves, from Normal to Slow it grows by two-thirds.", gm.CODE)

    # -- Mushrooms / Collectibles --------------------------------------------------------
    # 0x423505..0x42354B: with none out ([0xACAC] = 0) rand(120) > 117 every 2-second village step, paused or not;
    # it lies 60 real seconds at one of 9 spots; brown 8 / red 45 (effects 32 and 33, 0x43AFEF / 0x43B04C, each
    # +1 Mushrooms Found).  [0xACAC] lies past the save's last byte (state 0xABE4), so a mushroom is never saved.
    add("Mushrooms", "While none is out, a mushroom appears after about 2 real-life minutes on average, at any speed "
                     "(even while paused), at one of 9 places, and stays 1 real-life minute; it is picked only when you "
                     "drop a villager on it. It is a brown mushroom worth 8 food, or 1 in 20 a red (rare) mushroom "
                     "worth 45. How many have been found is under Village counts.", gm.RUNNING)
    add("Mushrooms", "Mushrooms are not kept in the save: one lying out when the game is closed is gone when it is "
                     "next played.", gm.CODE)
    if village.has(GOLDEN):
        out.extend(gm.golden_lines(GOLDEN, 30.0, speed_value, "one appears about every 2 real-life minutes while none "
                                   "is out, at every speed, so at most about 30 an hour when each is picked at once",
                                   even_paused=True))
    add("Collectibles", "A New Home has no collectibles: mushrooms are its only random pickup.", gm.RUNNING)

    # -- Tech points (how many there are is under Vital statistics) -----------------------------
    # Research, effect 18 (0x43B2AB): rand(100) < 2 takes rand(10) health (no floor); then the Research skill
    # (+0x3CC) ÷ 7 at Science 1 (and any level not 2 or 3), ÷ 5 at 2, ÷ 3 at 3, rounded down (0x43B2E9..0x43B33A).
    # A new village starts every technology at level 1 (0x41C43E..0x41C45C), so Science is never 0.
    science = level[SCIENCE]
    divisor = {2: 5, 3: 3}.get(science, 7)
    if 1 <= science <= 3:
        add("Tech points and effects", (
            f"Research gives the researcher's Research skill ÷ {divisor}, rounded down (Science is level {science}; "
            "÷ 7, ÷ 5 or ÷ 3 at level 1, 2 or 3), when the skill check passes; 2% of tries injure (0 to 9 "
            "health)."), gm.RUNNING)
    else:
        add("Tech points and effects", (
            "Research gives the researcher's Research skill ÷ 7, ÷ 5 or ÷ 3 at Science level 1, 2 or 3, rounded "
            "down, when the skill check passes; 2% of tries injure (0 to 9 health). Every technology starts at "
            "level 1."), gm.RUNNING)
    # The skill check 0x43D440 (one case per skill, table 0x43DA10): success when rand(100) <= skill + 30
    # (0x43D47B); the gain (50 - skill) x 2 ÷ 10 for Farming, Building, Research and Breeding (0x66666667 >> 34) and
    # ÷ 9 for Healing (0x38E38E39 >> 33, 0x43D814), rounded toward 0; at 0 or less rand(100) <= 25 and
    # rand(100) >= skill give 1 (0x43D558..0x43D579); the skill stops at 100.
    add("Tech points and effects", "Every job's skill check succeeds at (skill + 31) in 100 (no like or dislike "
                                   "changes it). A success raises the skill by (50 - skill) x 2 ÷ 10, rounded down, "
                                   "for Farming, Building, Research and Breeding, and by (50 - skill) x 2 ÷ 9 for "
                                   "Healing: 10 at skill 0 (Healing 11), 8 at 10, 1 at 45. From 46 up that is 0, and "
                                   "instead the skill rises by 1 on 26% x (100 - skill)% of successes (14% at 46, "
                                   "2.6% at 90), up to 100.", gm.CODE)
    # The patch turns the five failure branches of 0x43D440 into jumps to the gain (0x43D483, 0x43D5E0, 0x43D72A,
    # 0x43D7F8, 0x43D8AC; data/builds.json).
    if village.has(LEARNING) is not False:
        add("Tech points and effects", gm.patch_words(village, LEARNING, "the skill check always passes"), gm.CODE)

    # -- Food earned: the eating odds are under Chances ------------------------------------
    # The age-unit meal 0x42EC94..0x42ED46: at 200 food or less rand(100) >= 50 skips it and costs 1 health; then
    # 2 more (Medium above 2,000, any amount on Hard, never Easy: 76%); with the food at 0 after that, 1 health more
    # 76% of the time (every age unit on Hard).  The food store drop 0x4243F3 -> 0x43FAD0 -> effect 41 (0x43A26D).
    add("Food earned", (f"Each villager eats 2 food every age unit ({gm.duration(60 * speed)} of real-life play on {on} "
                        f"speed, {2 * 3600 / (60 * speed):g} food per real-life hour), and more on Medium and Hard; "
                        "when the meal is skipped and what going without costs are under Chances (Eating, "
                        "Starving)."), gm.RUNNING)
    add("Food earned", "A villager dropped on the food store goes \"Eating\": it costs 1 food, and below 100 health it "
                       "gives 1 health 50.05% of the time. Adults also go \"Eating\" on their own: when the game sends "
                       "an adult to its free-time choices, 10.66% of them are a meal while there is food (0x446030, "
                       "case 5).", gm.CODE)
    add("Food earned", "The Golden Child has no age-unit meal and never starves (that step skips him); dropped on the "
                       "food store he eats like anyone.", gm.CODE)

    # -- Time away (catch-up): src/vv_game_mechanics_catchup.py, added by vv_game_mechanics.read -----

    # -- Island events (how many have been seen is under Village counts) -----------------------
    add("Island events", f"Next island event: {due(EVENT)}.", gm.SAVE)
    out.extend(events.facts(village))

    # -- Other ---------------------------------------------------------------------------
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    for line, ok in CHANCE_LINES:
        add("Chance and timers", line, ok)
    for line in LIFE_LINES:
        add("Other", line, gm.RUNNING)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)",
                               "The Golden Child does not age. " + gm.patch_words(
                                   village, MAGIC_FRUIT, "with its puzzle done, the rolls start 7 years later")))
    add("Other", (f"An age unit is {gm.duration(60 * speed)} and a villager year (20 age units) "
                  f"{gm.duration(20 * 60 * speed)} of real-life play on {on} speed: ages, pregnancies and regrowth "
                  "follow the speed; work, mushrooms and island events do not."), gm.RUNNING)
    add("Other", f"The village was started at {gm.when(real(CREATED))}.", gm.SAVE)
    # The completion stamp (clock - [state+0x9E1C]) / 3600 (0x91A2B3C5 >> 43), 1 for 0: The Cemetery 0x4245A0..
    # 0x4245D2, The Cave 0x43ABE7..0x43AC1E, the Golden Child 0x4242AD; the clock 0x402F70 counts real seconds.
    out.extend(gm.hours_puzzle_lines([name for name, _flag, _hours in PUZZLES],
                                     lambda n: data[PUZZLES[n][1] + 4] != 0,
                                     lambda n: _i32(data, PUZZLES[n][2] + 4), real(CREATED), verified=gm.CODE))
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
        tech=_i32(data, TECH), tech_words="Research brings them (the skill ÷ 7, ÷ 5 or ÷ 3 at Science 1 to 3, "
                                          "rounded down).",
        brown=8, red=45, red_share=0.05, mushrooms_an_hour=30.0, golden=golden,
        mushroom_words="While none is out one appears about every 2 real-life minutes at any speed and stays 1 "
                       "real-life minute; it is picked only when you drop a villager on it, so at most about 30 per "
                       "real-life hour.",
        event_next=event_at,
        event_paused_left=max(0, _i32(data, EVENT) - _i32(data, SAVED)) if paused else None,
        # The timer world+0xA300 is a moment on the game clock 0x402F70; the pause pushes it on (0x42E930).  The
        # Origins Time Warp moves that clock on by moving its epoch back (native/vv1_origins_icons, the years' real
        # seconds: 12 hours on Fast and Normal, 10 on Slow), so the event comes that much sooner.
        event_rule="It comes 12 to 23 whole real-life hours after the last, at any speed; how the kind and the event "
                   "are drawn is under Island events.",
        event_running="Each Origins Time Warp brings it 12 real-life hours nearer on Fast or Normal and 10 on Slow: "
                      "the warp moves the game's clock on, and the timer is a moment on that clock (read from the "
                      "patcher's Time Warp code and the game's timer, not yet seen in a game).",
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
