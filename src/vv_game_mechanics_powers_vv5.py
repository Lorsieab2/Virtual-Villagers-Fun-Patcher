"""Game Mechanics for New Believers (VV5): the "God powers" group, with its Spirituality subsection.

Every line is read from the stock exe's own reachable code (SHA-256 92946781...C65D), at the addresses cited:
  * the God Power handler 0x422EB0 (called from the cast routine 0x4234A0, which the main scene's input 0x445A93
    calls), its jump table 0x423468, the powers' table 0x4CA000 (24 bytes each: +0x08 a range in pixels, +0x0D
    "needs a target villager") and the costs 0x498840 (10, 25, 50, 100, 150, 300, 400, 500, 600, 700, 800);
  * the spells' classes (RTTI): CSpawnButterfliesSpell 0x422990, CBeeSwarmSpell 0x421330, CSunshineSpell 0x41F240,
    CLightningSpell 0x421AC0, CHandOfBloomSpell 0x4209B0, CFogOfDoomSpell 0x41FAD0, CTimeWarpSpell 0x41FBF0,
    CGrantYouthSpell 0x41FCD0, CReanimateSpell 0x41FF10, CEarthQuakeSpell 0x41F6E0; Tempest is the handler's own
    weather call (0x4230C7);
  * the button refresh 0x422E50 (run every update of the village from 0x4425B8): a power is usable while Divine
    Energy (manager +0x17D64) is at least its cost;
  * Spirituality is tech 6 of 6 (index 5 at 0x51D5CC; the game's label "Spirituality"): its reads are 0x425071 /
    0x425085 (the Divine Energy cap 0x425020), 0x4323A4 / 0x4323CA (the Tribute Statue's upgrades 0x432350),
    0x468119 (the Faith drift 0x468040) and 0x46BC89 (the Devotion skill gain in the skill check 0x46B270).
The game's clocks: the real clock (0x4036E0, real seconds, runs on while paused), the millisecond ticks (0x4020E0,
real time, run on while paused) and the game clock (0x41ED40: 2x real time on Fast, 1x on Normal, 0.6x on Slow,
stopped while paused).  An age unit is 3, 6 or 10 real-life minutes on Fast, Normal or Slow; 20 make a year.
Read only: nothing here writes anything.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm

POWERS = "God powers"
ENERGY, ENERGY_CAP = 0x17D74, 0x17D70          # FILE offsets (manager +0x17D64 / +0x17D60)
# (name, cost, the game's own hint text) in the game's order (0x4CA000, 0x498840, the hint strings 0x4B7A94-0x4B7D88)
TABLE = (
    ("Spawn Butterflies", 10, "spawn a cluster of lovely, distracting butterflies!"),
    ("Swarm of Bees", 25, "spawn a bunch of stinging bees!"),
    ("Sunshine", 50, "make it sunny."),
    ("Lightning Strike", 100, "a bolt of lightning from above!"),
    ("Hand of Bloom", 150, "spontaneous vegetative growth."),
    ("Tempest", 300, "summon a grand storm!"),
    ("Fog of Doom", 400, "a fog so thick that visibility is crippled."),
    ("Time Warp", 500, "accelerate time for one islander."),
    ("Revive", 600, "bring a fallen believer back!"),
    ("Grant Youth", 700, "make someone (quite) young again."),
    ("Earthquake", 800, "shake the very island itself!"),
)
# A weather spell's length: the weather timer 0x4771B7.
WEATHER = ("lasts as long as any other weather: 1.5 to 3, 3 to 6 or 5 to 10 real-life minutes on Fast, Normal or Slow "
           "speed (paused time does not count)")

RULES = (
    # The buttons are refreshed every update of the village by 0x422E50.
    ("A power can be used whenever the Divine Energy is at least its cost; there is no cooldown and nothing else to "
     "unlock it. The Divine Energy cap decides which powers can ever be reached (Tech points and effects, and "
     "Spirituality below). The game's tip: \"You have a new power! As you increase the number of people who believe "
     "in you, new powers become available.\""),
    # The cost is taken at 0x423014; Spawn Butterflies replaces its own cluster at 0x4206F0.
    ("The cost is taken only when the cast works: a cast that is refused costs nothing. At most 10 powers can be at "
     "work at once; with 10 running, another cast does nothing and costs nothing, except Spawn Butterflies, which "
     "replaces its own earlier cluster."),
    # The target is the villager under the pointer (0x420660); the refusal 0x422F47.
    ("Time Warp, Revive and Grant Youth need a target: the villager under the pointer. Otherwise the game says \"You "
     "must select a target villager.\""),
    # The blocked corner is tested at 0x4234C8.
    ("Until The Blind Totem is solved, no power can be cast on the island's north-east corner (world x past 1,815 "
     "and y above 445): the game says \"Your vision and power are blocked here!\""),
)

# Stock vs patched (the owner, 2026-10-27: "say what god powers do"): every patch row of the patcher's catalog
# (data/builds.json and data/vv5_*_feature.json) that touches a God Power, searched by the powers' names, their
# handler (0x422EB0, 0x4234A0), their table (0x4CA000) and costs (0x498840) and the Divine Energy field: only Revive's
# record (the safety rows every patched New Believers gets, and Population 256's allocator rows at 0x46FDE0).
PATCHED = ("Stock or patched: no patch changes a power's cost, range, duration, odds or targets. Only Revive changes, "
           "and only when no villager record is free for the stand-in it makes: every game the patcher writes refuses "
           "that cast, nothing spent, where the normal game crashes; with the patcher's \"256 Villagers "
           "(Experimental)\" (off by default) the records are 256 instead of 150, so that refusal comes later (see "
           "Revive).")

# (power index, main line, sub-lines); every sub-line is from the code cited in it.
EFFECTS = (
    # Spawn Butterflies: the real clock 0x422A4F (126 s); the children are drawn by 0x41F170.
    (0, "lasts 2 minutes 6 seconds of real-life time (real time, the same at every speed), paused or not. Every 2 "
        "real-life seconds, until 6 seconds before the end, every living child under 14 who is not being carried and "
        "is not already at it stops what they are doing to go \"Playing with butterflies!\"; adults are not drawn. "
        "The game's tip: \"Butterflies are great for distracting children, both believers and heathens alike.\"", ()),
    # Swarm of Bees: the reactions 0x4214F0; +20 noni at 0x42146B, cut back by the noni growth at 0x425F7A.
    (1, "every living villager within 150 pixels of the spot reacts: near the water they go \"Hiding in the "
        "water\"; elsewhere \"Running from the bees\" (a villager in the red mask is \"Annoyed by the bees\" "
        "instead). Nobody loses health.",
     ("Cast on the noni bushes: +20 noni at once. Noni can then stand above 1,000 until the next +2 growth, which "
      "cuts it back to 1,000.",)),
    # Sunshine: the weather set at 0x41F32C; "Getting out of the rain" stopped at 0x41F343.
    (2, f"makes it sunny at once; the sunny weather {WEATHER}. Villagers \"Getting out of the rain\" stop. Sunshine "
        "ends a Tempest or any rain at once, and with it the rain's all-mushroom spawns.", ()),
    # Lightning Strike: the hiding 0x421C05; the fire pit 0x439090; the Pain Totem window 0x43A0C0, read by the job
    # choice at 0x46C2FF; the fixed spot near the water 0x421B7F.
    (3, "strikes the spot, and every living villager within 300 pixels of it goes \"Hiding from lightning\". Nobody "
        "loses health.",
     ("On the built fire pit: lights it, or relights it with a full fire, for 10, 20 or 33 hours 20 minutes of "
      "real-life play on Fast, Normal or Slow; paused time does not count.",
      "On the Pain Totem: villagers work on taking it down only during the 75 real-life seconds (real time) after a "
      "strike on it.",
      "Aimed within 300 pixels of the water, the bolt strikes one fixed spot instead (world point 520, 177), and "
      "nobody hides.")),
    # Hand of Bloom: the three uses by place, 0x42315F; the field 0x439EA0; the noni 0x420E5B; the food bin's area
    # refused at 0x422F69; the plants 0x420C18, the mushrooms 0x420D10, 0x420EC6; Heathens drawn within 402 pixels
    # (the distance squared below 15 x 104 squared, 0x420A40) go to the plants (0x420AC1).
    (4, "has three uses, by where it is cast:",
     ("On the field: with the Hydroponic Farm built, the crops are filled to 800 at once and the crop timer starts "
      "again from then; without it the game says \"The field is hopeless with the aqueduct in this condition.\" and "
      "nothing is spent.",
      "On the noni bushes: +1 noni every update of the village for 100 to 199 updates, +100 to +199 noni in all; "
      "above 1,000 it is cut back at the next +2 growth.",
      "Anywhere else (not the food bin's area, where it is refused): 17 to 22 plants grow within 104 pixels, as the "
      "ground allows. While 10 to 12 mushroom places are left, each plant is a mushroom half the time (a brown or a "
      "red one, equally likely), otherwise a flower. A grown mushroom is a normal one (brown 6 food, red 35, counted "
      "in Mushrooms Found when it reaches the food bin). Believers within 104 pixels dance; Heathens within 402 "
      "pixels go to the plants.")),
    # Tempest: the handler's own weather call 0x4230C7; rain makes every spawn a mushroom (0x477040); The Lake's
    # point 0x43C7E0, 0x43C460.
    (5, f"starts a storm at full strength (weather 5, rain); it {WEATHER}. While it rains every random spawn is a "
        "mushroom.",
     ("The Lake: when The Lake has no progress yet and the weather level is above 50 when Tempest is cast, The Lake "
      "gets 1 of its 2 points 120 real-life seconds (real time) later; once it has progress, a Tempest there gives "
      "none.",)),
    # Fog of Doom: weather 4 at 0x41FB1D for 120,000 ms (0x41FBAB); the season's weather 30 game-clock seconds later
    # (0x476F64); only weather 2, 3 and 5 is rain (0x477040); the doubled spawn 0x414633.
    (6, "covers the island in thick fog (weather 4) for 2 real-life minutes (real time), paused or not. Then, 30 "
        "seconds on the game's clock later (15, 30 or 50 real-life seconds on Fast, Normal or Slow), the weather goes "
        "back to the season's. It replaces the weather at once, so rain and a Tempest stop. In the fog the chance "
        "of a mushroom or collectible appearing doubles: 36 in 32,768 each update of the village instead of 18 in "
        "32,768.",
     # The Heathens' check 0x46E2E0 (from 0x471FE6) stops while the fog is 2 or more times as thick (0x476260); the
     # Fog of Doom draws it 4 times as thick (0x41FB60), ordinary fog and a Tempest's storm at 1 (0x475EDC).
     ("Heathens, while the thick fog lasts: they do not see believers. Every update of the village each Heathen "
      "checks for believers near them; that check stops while the fog is drawn at 2 or more times its usual "
      "thickness. The Fog of Doom draws it 4 times as thick; ordinary fog and a Tempest's storm stay at the usual "
      "thickness. So Heathens in orange masks do not chase believers away (\"Chasing the intruder\", the believer "
      "\"Running to safety\"), and believers do not run from Heathens in red masks (\"Running from the scary "
      "heathen\"): believers walk among the Heathens unchased. The code agrees with what the owner sees in play. "
      "Nothing else a Heathen does reads the fog: its thickness is read only there and by the fog's own drawing.",
      # The drawing value 0.6 at 0x41FB74, read only by the villager drawing 0x472186 (Heathens 1).
      "The tribe's villagers: what they do is unchanged. For the 2 real-life minutes (real time) they are drawn "
      "faded, at 0.6 of their usual visibility (Heathens are not faded; Revive raises the same value from 0 to 1 as "
      "the dead rise).",
      # Until the weather next changes (0x477073); the fog's own change 180 + rand(180) game-clock seconds after the
      # cast (0x4771B7), clear weather (0x47756D); 256 fog clouds instead of 64 (0x475F7A).
      "How long the thick fog lasts: until the weather next changes, 2 real-life minutes plus the 15, 30 or 50 "
      "real-life seconds above. The fog's own weather change comes 180 to 359 seconds on the game's clock after the "
      "cast: on Fast that is 90 to 179.5 real-life seconds, so 1 cast in 3 on Fast ends it before the 2 minutes, "
      "with clear weather; on Normal and Slow it never comes first. Sunshine or a Tempest cast during it ends it at "
      "once (each sets the weather). The 4 times thickness is 256 fog clouds instead of 64.")),
    # Time Warp: the time factor (villager +0x1CC8) set from 1 to 10 at 0x41FC4E for 300,000 ms (0x41FC9B), then back
    # to 1 (0x41FCB3).
    (7, "speeds the target up for 5 real-life minutes (real time, the same at every speed, paused or not): the "
        "target's time factor goes from 1 to 10, then back to 1. It speeds up the target's age, movement and "
        "actions; nothing else reads it:",
     # The age credit 0x470040 doubles the factor (0x470051) and pays at 0x47006C, emptying the count at 0x4700E2.
     ("Age: a villager's age clock counts real-life seconds toward the next age unit. While warped, each whole "
      "real-life minute on that clock pays 20 ÷ the speed value (3, 6 or 10) age units, rounded down, and the count starts again. That is 6, 3 "
      "or 2 age units each real-life minute on Fast, Normal or Slow, instead of 1 every 3, 6 or 10 real-life "
      "minutes: 18, 18 or 20 times as fast.",
      "Over the 5 real-life minutes (real time) that is 4 or 5 such minutes (the fifth falls on the last second): 24 "
      "to 30, 12 to 15 or 8 to 10 age units on Fast, Normal or Slow (1.2 to 1.5, 0.6 to 0.75 or 0.4 to 0.5 villager "
      "years of 20 age units). Whole minutes the target had already counted toward its next unit when the warp began "
      "are paid at the warp rate at once: up to 13, 16 or 18 more age units (2, 5 or 9 whole minutes at most). In "
      "all a warp gives 24 to 43, 12 to 31 or 8 to 28 age units (1.2 to 2.15, 0.6 to 1.55 or 0.4 to 1.4 villager "
      "years).",
      # The life tick 0x472C90; a pregnancy counts in the mother's age units (0x44B123).
      "Every age unit paid goes through the target's own age-unit update, one unit at a time: the Faith drift, the 2 "
      "food eaten, the Divine Energy added and the sickness roll each come once per unit, and a pregnancy comes that "
      "many units closer to the birth. Working from 14 (280 age units), having children from 18 (360) and old age "
      "come by age, so they come sooner.",
      # The step loop 0x471EF9; the action length divisor 0x4735AB.
      "Movement and actions: each update of the village runs the target's step 10 times instead of once, so the "
      "target walks 10 times as far. Each timed action started while warped lasts a tenth as long, in whole "
      "real-life seconds (real time), at least 1 (30 seconds become 3, 5 seconds become 1). Work (research's tech "
      "points, a hut's building points, a harvest's food, the skill checks that raise skills) gives the usual amount "
      "each time; it comes as much more often as the walking and the shorter actions allow, up to 10 times.",
      # A Heathen never ages (0x470077); the dead never age (0x46FF63); the achievement 0x41FC44.
      "The target can be any villager under the pointer: a Heathen moves and acts 10 times as fast but never ages; "
      "the dead never age. Cast on a villager under 14 (280 age units) it earns the \"Waaay Too Much Sugar\" "
      "achievement (\"You used time warp on a child\").",
      # Paused, the count is emptied (0x470022); quitting ends the warp (0x465207).
      "While the game is paused nobody ages and the age clock's count is emptied, so the paused part of the 5 "
      "real-life minutes (real time) gives no age. The warp is not saved: quitting ends it, so time away (catch-up) "
      "is never warped.",
      # Work event 54 is at 0x46D3F8.
      ("A work step of the game's also sets the factor back to 1; which action starts it was not "
       "traced.", False),
      # The trail 0x472101; the effect 0x467C70.
      ("While warped the target is drawn with a trail of its last positions, and an effect beside it on 2 in 100 of "
       "its steps in four of its actions; how these look was not checked in play.", False))),
    # Revive: the rise after 4,000 ms (0x41FF93, 0x420080); the dead test 0x423404.
    (8, "brings a dead villager (0 health or less) back with 100 health; they rise after 4 real-life seconds (real "
        "time). The game checks only that the target is dead: \"This villager is still full of life.\" otherwise.",
     ("Only a dead villager still lying on the island can be the target: a buried one cannot be picked.",
      # The second record 0x41FFF0, 0x420142; the patcher's safety fix at file offset 0x2341A.
      "The game also makes a second villager record for the dead one (same name, family, name number and age, 0 "
      "health), which is not shown on the island. With no free record (150 in use) the normal game crashes; in a "
      "game written by the patcher the cast is refused instead, nothing spent: \"There's no room in your village to "
      "revive this person.\" (the patcher's safety fix). With the patcher's \"256 Villagers (Experimental)\" the "
      "records are 256, so the refusal comes only with all 256 in use.",
      # The Lake's point 0x4233DD.
      "On the dry lake bed while The Lake is unsolved, no target is needed: with no progress yet The Lake gets 1 of "
      "its 2 points; once it has progress, a Revive there gives none.")),
    # Grant Youth: 0x41FDC0, 3 age units an update at 0x41FDDC; the refusals 0x42330D; the pregnancy 0x41FEB0.
    (9, "makes a living believer of 14 or more 5 years old (age 100 age units), counting the age down by 3 age units "
        "at every update of the village until it gets there. Refused, nothing spent: under 14 \"This villager is "
        "already full of youth.\", a Heathen \"You cannot grant youth to heathens.\", the dead \"You cannot grant "
        "youth to corpses.\"",
     ("A pregnant villager stays pregnant, but the time she had already carried is counted backwards, so the birth "
      "comes that much later than from a fresh pregnancy (the normal game's arithmetic). Skills, likes and Faith "
      "are kept.",)),
    # Earthquake: rand(7) + 2 at 0x41F78F, which skips roles 12 to 17; the preaching wait 0x41F7B8.
    (10, "every living villager's Faith goes up by 2 to 8 (each amount equally likely), except the six special roles "
         "below. A Heathen whose Faith rises above 0 joins the tribe; every Heathen it reaches cannot be preached to "
         "for 2 real-life hours (real time), paused or not.",
      # The role is the villager's +0x1CFC; the names the game shows 0x443102; the purple mask 0x4728C6.
      ("The six special roles (the role number, and the name the game shows on a Heathen in it): 12 \"Heathen "
       "Doctor\", 13 \"Heathen Chief\", 14 \"Heathen Master Scientist\", 15 \"Heathen Master Builder\", 16 \"Heathen "
       "Master Farmer\", 17 \"Heathen Mommy\". Each is the Heathen one puzzle is about: The Sick Heathen (curing the "
       "Doctor), The Heathen Chief (four necklace pieces), The Heathen Scientist, The Heathen Builder (a build-off), "
       "The Hydroponic Farm (+80 Faith to the Master Farmer) and The Heathen Parent (the Mommy; on the Puzzles "
       f"screen only with the patcher's \"{gm.feature_name('vv5_heathen_mommy_puzzle')}\"); see Puzzles. The Doctor "
       "and the three Masters wear the purple mask.",
       # The role is read in only from the save (0x466C0E); joining clears it (0x46696F) except the Chief's
       # (0x466966); becoming a Heathen clears any (0x4669F5); never drawn for island events (0x47199A).
       "No code in the game gives a villager one of these roles: the role is only ever read in from the villager's "
       "saved record, so only Heathens a village starts with hold them. Joining the tribe clears the role except the "
       "Chief's: the converted Heathen Chief keeps role 13 as the tribe's \"Retired Chief\", so the Earthquake skips "
       "the Retired Chief too. Becoming a Heathen clears any role. Villagers in these roles cannot be preached to and "
       "are never drawn for island events.",
       # The drop after 10,000 ms (0x41F832), the rarity 0x41F853.
       "10 real-life seconds (real time) after the cast: one collectible drops, 72% uncommon, 28% rare.",
       # The farm 0x439F00, a hut 0x434790, the statue 0x432C90, the mausoleum 0x43C9C0.
       "At the same moment, each unfinished project with progress loses part of it: the Hydroponic Farm 1 of its 30 "
       "points, each started hut 100 of its 2,000, the Tribute Statue 1 (5 at its last stage). The Buried Mausoleum "
       "gains 50 of the 1,000 it needs.")),
)

SPIRITUALITY = (
    ("Spirituality (the tech, levels 1 to 3; the game: \"Training your villagers in spirituality increases your "
     "maximum divine energy, allows statue upgrades and influences heathens to believe.\") does four things:"),
    # The Faith drift's roll 0x468112.
    "Faith: each age unit every believer gains 1 Faith 10%, 20% or 30% of the time at level 1, 2 or 3, one of the "
    "Faith drift's rolls (see Faith).",
    # The cap 0x425071, 0x425085.
    "The Divine Energy cap: +50 at level 2 and +50 more at level 3.",
    # The statue's upgrades 0x432350.
    "The Tribute Statue: its second stage can be worked on only with Construction and Spirituality both at level 2 or "
    "more, its third only with both at level 3.",
    # The Devotion gain in the skill check, 0x46BC89.
    "Devotion: every successful Devotion skill check adds the Spirituality level (1 to 3) to the Devotion gained, on "
    "top of the usual (70 - Devotion) / 18.",
)


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def lines(village: gm.Village) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    add = lambda text, ok=gm.RUNNING, sub=False: out.append(gm.Fact(POWERS, text, ok, sub))  # noqa: E731
    data = village.data
    if not village.general and len(data) >= ENERGY + 4:
        energy, cap = _i32(data, ENERGY), _i32(data, ENERGY_CAP)
        usable = [name for name, cost, _ in TABLE if energy >= cost]
        reach = [name for name, cost, _ in TABLE if cap >= cost]
        add(f"This village: {energy:,} Divine Energy of a {cap:,} cap. Usable now: "
            f"{', '.join(usable) if usable else 'none'}. Within the cap: {', '.join(reach) if reach else 'none'}.",
            gm.SAVE)
    # The costs are the table at 0x498840.
    add("The 11 God Powers and their Divine Energy costs, with the game's hints: " + "; ".join(
        f"{name} {cost} (\"{hint}\")" for name, cost, hint in TABLE) + ".")
    for text in RULES:
        add(text, sub=True)
    add(PATCHED, gm.CODE, True)
    for index, text, subs in EFFECTS:
        name, cost, _ = TABLE[index]
        add(f"{name} ({cost}): {text}")
        for sub in subs:
            sub, ok = sub if isinstance(sub, tuple) else (sub, gm.OWNER if sub.startswith("Only a dead") else gm.RUNNING)
            add(sub, ok, True)
    add(SPIRITUALITY[0])
    for text in SPIRITUALITY[1:]:
        add(text, sub=True)
    return out
