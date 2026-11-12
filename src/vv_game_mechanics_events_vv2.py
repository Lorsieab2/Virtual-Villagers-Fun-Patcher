"""The Lost Children (VV2): every island event the game fires and the Gong of Wonder, their odds and outcomes
(src/vv_game_mechanics_events.py).

Read from the stock executable (research/stock-executables, inputs/vv2-stock-copy); state offsets are the world's
(a save's file offset is 4 more).  Button words are the game's own strings (12-byte entries: id, English, German).
rand(n) is 0x4031A0: the C runtime's rand() % n.

THE SCHEDULER (0x42EECD; docs/reports/island-event-conditions.txt, The Lost Children):
  * The next event time is world+0x2EAE0 on the clock 0x403200 (real seconds at any speed).  A new village sets it
    15 minutes after its start (0x42529B); the first event sets the next 30 minutes later (+0x708), every later
    one (rand(10) + 10) x 3600 s later.  Seen counter world+0x2E51C.
  * Tried only with a living villager of 14 or more (0x44BAE0(1)) whose age +0x530 equals its processed age
    +0x534.  Family (0x42EF28, 0x42EF4A): Seen = 0 -> two-choice; else rand(100) < 20 two-choice, else rand(100)
    < 50 single-result, else a sack or vial.
  * Single-result chooser 0x434607: rand(28), up to 10 draws, each draw's condition from table 0x434868 (cases
    4, 18, 20, 26 map to the never-valid 0x434824); if none passes, Blessings Day (first version, case 10).
    Bodies 0x433600, table 0x4344F4.  Strength n (0x42F09E): population / 3, 1 to 10.  Amounts "x k" use
    0x4335A0: x3 above 50 people, otherwise x1 (its second test repeats 50, so x2 never happens).
  * Two-choice chooser 0x41F59D: rand(22), 21 always rejected, up to 10 draws, condition table 0x41F6C8; if none
    passes, The Voices In The Brush.  Setup 0x41F7A6 (table 0x420454), resolve 0x4204C0 (table 0x422264),
    button [this+0x50A4] (1 the first).  Amounts "x k" use 0x41F720: x3 above 50 people, x2 above 25, else x1.
  * Sacks and vials (0x437AC0): strength rand(100) at 0x437ADC (0-32 1, 33-66 2, 67-99 3), then rand(8) at
    0x437B0E, no re-roll.  Resolve 0x43819D (table 0x439D0C).
  * Population (0x425860): living villagers that are not Esteemed Elder statues (+0x558) plus babies carried.
    Pickers: 0x44BAE0(0) any record present (+0x30) with health +0x52C > 0; a statue is made with health 0
    (0x44D467), so no picker or per-villager roll ever takes one.  Room (0x44B310): population below 90 plus 5 for
    each complete children's collection, and 15-24 people need 1 hut, 25-49 two, 50 or more three.
  * Per-villager rolls: 0x4332F0 (single-result), 0x41F500 (two-choice), 0x437570 (sacks): every present living
    record, rand(100) < the chance.

THE GONG OF WONDER (story research scripts/story_outcomes_gong.py): a villager finishing action 66 "Ringing the
Gong of Wonder" (0x461B10, case 0x461B32) once the rest world+0x2EAC8 has passed runs 0x44E8A0 (from 0x461B8E):
rand(100) < 5 tier A, else rand(100) < 25 tier B, else tier C -- A and B only once world byte +0x2E910 is set,
which the first tier-C result does (0x44EFDB; never cleared).  Tier A rand(6) (0x44E8CF, table 0x44F450), tier B
rand(9) (0x44EBE3), tier C rand(9) (0x44EFE2; entries 7 and 8 are the same).  The ringer (0x44B440): the first
record in index order that is present, alive, older than 280 age units and doing "Ringing the Gong of Wonder".
"""
from __future__ import annotations

from vv_game_mechanics_events import Event, Line, share

RESTORE = "vv2_restore_missing_island_events"
FIX = "vv2_fix_vanilla_bugs"
STORY = "vv2_story_cheat_upgrades"
GONG_FIX = "vv2_gong_of_wonder_coconuts_fix"

SINGLE, TWO, SACK = 24, 21, 8                    # the events each family can fire (stock)
DRAWS = 10

K1 = ("k is 1, or 3 with more than 50 people (the game's x2 step is never reached)")
K2 = "k is 1 up to 25 people, 2 up to 50, 3 above"


def each(total: int, eligible: int, percent: float) -> str:
    """The share of one eligible event of a family drawn `total` ways up to 10 times."""
    miss = (1 - eligible / total) ** DRAWS
    return f"{percent * (1 - miss) / eligible:.2f}%"


RULES = (
    Line("Timing: an event comes 10 to 19 whole real-life hours after the last (each of those 10 hour counts "
         "equally likely), at any speed; in a new village the first comes 15 real-life minutes after it is started "
         "and the second 30 real-life minutes after the first. Paused, the timer waits; after time away at most one "
         "event happens. The Gong's \"luck\" result brings the next one 1 real-life minute later."),
    # "no age units still waiting": the villager's age +0x530 equals its processed age +0x534.
    Line("An event happens only when there is a living villager of 14 villager years or more with no age units "
         "still waiting to be worked through (from time away); otherwise the game waits and tries again."),
    Line("Which kind: the village's first event is always a two-choice event. After that 20% are two-choice "
         "events, 40% single-result events and 40% sacks or vials."),
    Line("Single-result events: up to 10 draws of 1 in 28 (4 of the 28 never pass), the first whose condition "
         "holds happens, else Blessings Day (first version). Two-choice: up to 10 draws of 1 in 22 (1 never "
         "passes), else The Voices In The Brush. Sacks and vials: 1 in 8, no condition."),
    Line(f"So with every condition met each single-result event is {each(28, SINGLE, 40)}, each two-choice event "
         f"{each(22, TWO, 20)} ({each(22, TWO, 100)} of the first event), each sack or vial {share(40, SACK)}. How "
         "it is worked out: with E of them possible, each gets 1/E x (1 - (1 - E/28)^10) of the single-result 40% "
         "(22 in place of 28 for two-choice), and the fallback event gets the rest."),
    Line("With the patcher's \"Restore Missing Island Events\" (in this game): The Mosquito Swarm, The Dragonfly "
         "Migration and Science Awareness Day pass their draw like an unconditional event, and draw 4 shows one "
         "of three lore pages (The Tattered Diary, The Doctrine of Magicians, The Doctrine of Naturalists, a third "
         "each) that change nothing; with every condition met each single-result event is then "
         f"{each(28, SINGLE + 4, 40)}.", only_with=RESTORE),
    Line(f"Strength n (single-result events): the population divided by 3, from 1 to 10. Amounts \"x k\": in "
         f"single-result events {K1}; in two-choice events {K2}. Sacks and vials have their own strength: 1 "
         "(33%), 2 (34%), 3 (33%)."),
    Line("With the patcher's \"Fix Vanilla Bugs\" (in this game): single-result events use the two-choice factor "
         f"too -- {K2} -- as the game meant (0x4335C9 tests 25, not 50 again).", only_with="vv2_fix_vanilla_bugs"),
    # Every "N%" is the game's test rand(100) < N: the C runtime's rand() (0 to 32,767) modulo 100.
    Line("Who: an event's villager is any living villager, each equally likely (Esteemed Elder statues have 0 "
         "health and are never picked); For The Birds and The Child Prodigy pick a living child under 14 villager "
         "years. Every \"N%\" below is exact to within 0.07 percentage points (the game's random numbers run 0 to "
         "32,767, which 100 does not divide evenly)."),
    Line("With the patcher's \"Story / Cheat Upgrades\" (in this game): Pick Island Event and Pick Gong of Wonder "
         "Outcome choose the next event or Gong result and its rolls instead of the chances above.",
         only_with=STORY),
)

B = "every villager's ongoing work is cleared"           # the record's task +0x7E0

EVENTS = (
    # -- Single-result events --------------------------------------------------------------------------
    # The bodies, in order: 0x43361A, 0x433673, 0x4336B9, 0x433731, 0x4342FE, 0x434358, 0x433793, 0x4342B0,
    # 0x433F73, 0x433858, 0x433910, 0x433BC8 (the gathering 0x45D7D0), 0x433C87 ("Greeting the guiding hand"
    # 0x454350), 0x433B2C, 0x433A31 ("Honoring the Dead" 0x454890), 0x433AB3 (the animation 0x44AF20), 0x4344BC ->
    # 0x4333B0, 0x434040 (the toddlers: the villager maker 0x44F580 with no parents), 0x434413, 0x433DD3,
    # 0x433CEF, 0x433E07, 0x433D3A, 0x433E3E; the patch's 0x433EB5, 0x433FCD, 0x43439D.
    Event("The Obnoxious Parrot", "single-result, always possible", (
        "The tribe loses a quarter of its tech points, rounded down.",)),
    Event("The Flash Flood", "single-result, always possible", (
        "Stored food above 750 is cut to 750.",)),
    Event("The Dense Fog (food lost)", "single-result, always possible", (
        "The stored food loses 200 x k, down to 0 at least.",)),
    Event("The Dense Fog (tech lost)", "single-result, always possible", (
        "The tribe loses 1,000 x k tech points, with no floor.",)),
    Event("The Dense Fog (tech gained)", "single-result, always possible", (
        "The tribe gains 800 x k tech points.",)),
    Event("The Dense Fog (food gained)", "single-result, always possible", (
        "The stored food gains 150 x k.",)),
    Event("The East Wind", "single-result, always possible", (
        f"The coconuts, the crops and the stored food each lose 80 x n, each down to 0 at least, and {B}.",)),
    Event("The West Wind", "single-result, always possible", (
        "The coconuts and the crops each gain 100 x n, with no cap in the event itself.",)),
    Event("The Friendly Parrot", "single-result, always possible", (
        "The stored food gains 400 x k.",)),
    Event("The Heat Wave", "single-result, always possible", (
        "Every living villager not already busy stops: an adult (over 280 age units) goes \"Enjoying the pond\" "
        "(one of two ways, 50% each), a child goes \"Cooling feet in stream\"; nothing else changes.",)),
    Event("Isola Day Celebration", "single-result, always possible", (
        f"The villagers celebrate as in the Heat Wave, {B}, and the stored food loses 10 for every villager "
        "(babies being carried counted), down to 0 at least.",)),
    Event("Blessings Day Celebration (first version)", "single-result, always possible; also the fallback when "
                                                       "10 draws find no event", (
        "A gathering, every free living villager goes \"Relaxing at the beach\", and the stored food loses 10 "
        "for every villager, down to 0 at least.",)),
    Event("Blessings Day Celebration (second version)", "single-result, always possible", (
        "\"Greeting the guiding hand\", and the stored food loses 10 for every villager, down to 0 at least.",)),
    Event("Day of Elders", "single-result, always possible", (
        "The gathering Blessings Day (first version) also starts, when the first villager record is a living, "
        "free villager; no amount changes.",)),
    Event("Day of Honor", "single-result; needs a grave in the memorial (someone buried)", (
        "Every free living villager goes \"Honoring the Dead\"; no amount changes.",)),
    Event("The Spring Allergies", "single-result, always possible", (
        f"Every living villager stops what it is doing and plays a short animation, and {B}; no health or "
        "amount changes.",)),
    Event("The Mother Parrot", "single-result, always possible", (
        "Each living child under 280 age units (14 villager years), 35% each: +7 to 17 Parenting (each 1 in 11), "
        "up to 100.",)),
    Event("The Barrel O` Babies", "single-result; needs room for new villagers when it is picked", (
        "1 toddler for n of 1 to 4, 2 for 5 to 7, 3 for 8 to 10; room is checked only when the event is "
        "picked.",
        "Each toddler is 70 to 89 age units old (3.5 to 4.45 villager years, each 1 in 20), a boy or a girl 50% "
        "each, 90 health, every skill 0, a head and a body each one of 0 to 29, likes and dislikes as at a "
        "birth.")),
    Event("Old Friends", "single-result; needs room for new villagers when it is picked", (
        "A man and a woman join, each 400 to 599 age units (20 to 29.95 villager years, each 1 in 200) "
        "with one skill -- Farming, Parenting, Healing, Research or Building, 20% each -- at 30 to 49 (each 1 in "
        "20), 90 health, the other skills 0; then the village celebrates.",)),
    Event("The Epidemic", "single-result; needs all 16 puzzles solved", (
        "Every living villager falls sick at 80% each; no health is lost by the event itself.",)),
    Event("Rats!", "single-result; needs all 16 puzzles solved", (
        "Every living villager is bitten at 40% each -- sick, and 60 health lost, down to 0 at least (at 0 the "
        "villager dies) -- and then the stored food is halved, rounded down.",)),
    Event("The Foul Passing", "single-result; needs all 16 puzzles solved", (
        "All the stored food is lost: food 0; the crops and coconuts are not touched.",)),
    Event("Where Are The Infants?", "single-result; needs all 16 puzzles solved and a living pregnant or nursing "
                                    "villager of 18 villager years or more", (
        f"Every living pregnant or nursing villager loses her babies (her pregnancy is ended), and {B}.",)),
    Event("A Dangerous Mission", "single-result; needs a population of 61 or more", (
        "The first 8 living villagers in record order aged 281 to 499 age units (14.05 to 24.95 villager years) "
        "leave the village for good: no body, no grave.",)),
    Event("The Mosquito Swarm", "single-result added by the patch, always possible", (
        "Every living villager falls sick at 20% each; every living adult who is not pregnant or nursing goes to "
        f"the pond, and {B}.",), only_with=RESTORE),
    Event("The Dragonfly Migration", "single-result added by the patch, always possible", (
        "Every living villager is cured and set to 100 health.",), only_with=RESTORE),
    Event("Science Awareness Day", "single-result added by the patch, always possible", (
        "Every living child under 280 age units gains 3 to 7 Research (each 1 in 5), up to 100.",),
        only_with=RESTORE),
    # -- Two-choice events ----------------------------------------------------------------------------
    # The results (the resolve 0x4204C0, table 0x422264): the coin 0x4204DC, the idol 0x4205B7, the girl 0x420763
    # and 0x4206C4, Biggles made at 0x41F944 and leaving at 0x420806, the savage child 0x42090B (made by 0x44F580),
    # the voices' roll rand(100) at 0x420A78, the fish 0x420B43, the runner 0x420C08, the nightmare 0x420D83, the
    # bump's roll rand(100) at 0x420E5F, the prodigy 0x421206, the dragonflies 0x421309, the seeds 0x421369, the
    # crystal ball 0x421401, the mirror 0x42178A (the copy made by 0x44CEC0), the coconut 0x421839, the star
    # 0x421900 and its roll rand(100) at 0x421B08, the hole's roll rand(6) at 0x421B97, the spyglass 0x421E38, the
    # love note 0x421F0E (the woman picked by 0x44BE70, the room check 0x44B980), the pearl 0x422016.
    Event("The Ancient Gold Coin", "two-choice; needs Culture technology below level 2", (
        "\"Use it to adorn clothing\": Culture technology goes up 1 level.",
        "\"Give it to the scientists\": +2,000 x k tech points.")),
    Event("The Cursed Idol", "two-choice; needs 250 stored food or more", (
        "\"Destroy the idol\": the villager's first two dislikes become crowds and work.",
        "\"Make an offering of food\": the stored food loses 250 x k, down to 0 at least.")),
    Event("The Prettiest Tribe Girl", "two-choice; needs a living woman of 14 villager years or more (the girl "
                                      "named can be any living female)", (
        "\"All agree she is the prettiest\": her first two dislikes become work and learning, and she goes off to "
        "enjoy the pond.",
        "\"Looks aren't everything\": she gains 20 to 39 Parenting (each 1 in 20), up to 100.")),
    Event("The Strange Request", "two-choice, always possible; the game makes a man named Biggles, 580 age units "
                                 "(29 villager years), for it", (
        "\"Allow the request\": the tribe loses 3,000 x k tech points, with no floor, and Biggles leaves.",
        "\"Refuse the request\": Biggles leaves; nothing else changes.")),
    Event("The Savage Child", "two-choice; needs room for new villagers", (
        "\"Lure him away with food\": the stored food loses 500 x k, down to 0 at least, and a boy of 260 age units "
        "(13 villager years) joins, 90 health, every skill 0, a random head and body.",
        "\"Chase him away\": the tribe loses 1,000 x k tech points; if fewer than 1,000 are left they become 0.")),
    Event("The Voices In The Brush", "two-choice, always possible; also the fallback when 10 draws find no event", (
        "\"Investigate the voices\": 50% harmless, +700 x k stored food; 50% the villager is never seen again (no "
        "body, no grave).",
        "\"Head back to the village\": nothing changes.")),
    Event("For The Birds", "two-choice; needs a living child under 14 villager years, who is the one", (
        "\"Taste the fish\": +100 x k stored food.",
        "\"Leave the fish alone\": the child gains 30 Farming, with no cap.")),
    Event("The Fastest Runner", "two-choice, always possible", (
        "\"Let him (her) race everyone\": the villager now dislikes running (in the first empty of two dislike "
        "slots, else the second) and no longer likes it.",
        "\"Agree he (she) is the fastest\": the villager now likes running and no longer dislikes it.")),
    Event("The Nightmare", "two-choice, always possible", (
        "\"Wake him (her) up\": nothing changes.",
        "\"Let him (her) sleep\": the villager loses 20 health, down to 0 at least; at 0 the villager dies.")),
    Event("A Bump On The Head", "two-choice, always possible", (
        "\"Bonk him (her) on the head\": 50% every skill +30, up to 100; 50% every skill -30, down to 0; either way "
        "10 health lost, down to 0 at least.",
        "\"Let him (her) rest\": nothing changes.")),
    Event("The Child Prodigy", "two-choice; needs a living child under 14 villager years, who is the one", (
        "\"Let him (her) play\": the child gains 50 Building, up to 100.",
        "\"Let him (her) apprentice\": the child gains 10 Research, up to 100, and the tribe +1,000 x k tech "
        "points.")),
    Event("The Swarm Of Dragonflies", "two-choice, always possible", (
        "\"Chase them away\": every living villager falls sick at 20% each.",
        "\"Ignore them\": nothing changes.")),
    Event("The Black Seeds", "two-choice, always possible", (
        "\"Eat them\": nothing changes.",
        "\"Plant them\": the crop field is emptied to 0.")),
    Event("The Crystal Ball", "two-choice; needs a living villager of 14 villager years or more (the keeper can be "
                              "anyone)", (
        "\"Keep it\": the keeper trades places with another living villager, each equally likely: their names, "
        "all five skills and their first two likes and dislikes are swapped.",
        "\"Give it to the children\": nothing changes."),
        patched=((FIX, "it is offered only when another living villager is there to trade places with, and "
                       "\"Keep it\" with nobody else does nothing; in the normal game it is offered with nobody "
                       "else and \"Keep it\" then closes the game"),)),
    Event("The Silver Mirror", "two-choice; needs a population of 2 or more", (
        "\"Speak the word Geminus\": nothing changes.",
        "\"Speak the word Sunimeg\": with room for a villager, a copy of the villager joins -- the same name, sex, "
        "head, body, age and skills, 90 health; without room nothing.")),
    Event("The Huge Coconut", "two-choice, always possible", (
        "\"Soften it in the pond\": nothing changes.",
        "\"Hurl it from the diving rock\": +250 x k stored food, and every living villager is cured and set to 100 "
        "health.")),
    Event("The Falling Star", "two-choice, always possible", (
        "\"Wish for himself (herself)\": one skill, 20% each -- Parenting, Building, Farming, Research or Healing "
        "-- gains 10 to 20 (each 1 in 11), up to 100.",
        "\"Wish for the village\": 50% +(100 to 299) x k stored food, 50% +(1,000 to 2,999) x k tech "
        "points.")),
    Event("The Hole In The Sand", "two-choice, always possible", (
        "\"Investigate the hole\": 1 in 6 each: brass tools, +1,000 x k tech points; a "
        "cache of nuts, +300 x k stored food; baby snakes, the villager falls sick and every living villager at "
        "40%; putrid slime, the villager falls sick; a golden pocket watch, +1,000 x k tech points; ants raid the "
        "food bin, -150 x k stored food, down to 0 at least.",
        "\"Fill in the hole\": nothing changes.")),
    Event("The Spyglass", "two-choice; needs Exploration technology below level 2", (
        "\"Keep it\": Exploration technology becomes level 2.",
        "\"Give it to the scientists\": +3,000 tech points (not x k).")),
    Event("The Love Note", "two-choice; needs a living man and a living woman, each 18 villager years or more (the "
                           "man is the one)", (
        "\"Write his own poem\": he gains 30 Parenting, up to 100.",
        "\"Hide to catch the poet\": a living woman of 18 villager years or more, each equally likely, "
        "conceives his child, if there is room; at Medicine level 3 the conception's twin and triplet "
        "rolls are made (7%, then 25% of those triplets).")),
    Event("The White Pearl", "two-choice, always possible", (
        "\"Keep it for himself (herself)\": all five skills each gain 10 to 29 (each 1 in 20), up to 100.",
        "\"Show it to the tribe\": the tribe loses 200 x k tech points, with no floor.")),
    # -- Sacks and vials ("Leave it alone" / "Pour it out" change nothing) --------------------------------
    # The results (0x43819D, table 0x439D0C): 0x4381A4, 0x438454, 0x4388B0, 0x438E77, 0x43919E, the green vial
    # 0x43954E, the orange vial rand(5) at 0x439727, the fragrant vial 0x4399B9.
    Event("A Mysterious Sack (thick, plastic)", "a sack, 1 in 8 of sacks and vials. Item: a thick, plastic sack", (
        "\"Open it\": +500, +1,000 or +1,500 stored food at strength 1, 2, 3 (coconuts, golden ripe bananas, "
        "preserved meat).",)),
    Event("A Mysterious Sack (carefully sealed)", "a sack. Item: a carefully sealed sack", (
        "\"Open it\": +1,000, +2,000 or +3,000 tech points at strength 1, 2, 3.",)),
    Event("A Mysterious Sack (somewhat compromised)", "a sack. Item: a somewhat compromised sack", (
        "\"Open it\": +500, +1,000 or +1,500 tech points, and every living villager falls sick at 15%, 20% or 25% "
        "each, at strength 1, 2, 3.",)),
    Event("A Mysterious Sack (thick, canvas)", "a sack. Item: a thick, canvas sack", (
        "\"Open it\": starving mice bite every living villager at 20%, 30% or 45% each -- sick, and 10, 15 or 20 "
        "health lost, down to 0 at least -- at strength 1, 2, 3; then the opener falls sick and loses 15 more "
        "health with no floor. At 0 health a villager dies.",)),
    Event("A Mysterious Sack (stained, heavy burlap)", "a sack. Item: a stained, heavy burlap sack", (
        "\"Open it\": fire ants sting the opener, who loses 40, 70 or 110 health at strength 1, 2, 3, with no floor; "
        "at 0 or less the opener dies, so strength 3 always kills.",)),
    Event("A Mysterious Vial (green)", "a vial. Item: a thin or viscous green vial (the word changes nothing)", (
        "\"Drink the liquid\": the drinker's head is re-rolled: a man gets one of heads 0 to 28, a woman one of 0 "
        "to 29, each equally likely; the strength changes only the words.",),
        patched=((FIX, "a man gets one of heads 0 to 29 too, each equally likely, as a woman does; in the normal "
                       "game a man never gets head 29 from the drink"),)),
    Event("A Mysterious Vial (orange)", "a vial. Item: a thin or viscous orange vial", (
        "\"Drink the liquid\": one skill, 20% each -- Farming, Building, Parenting, Healing or Research -- gains "
        "50, 75 or 100 at strength 1, 2, 3, up to 100.",)),
    Event("A Mysterious Vial (fragrant)", "a vial. Item: a thin or viscous fragrant vial", (
        "\"Drink the liquid\": all five skills lose 30, 50 or 70 at strength 1, 2, 3, down to 0 at least.",)),
)

RINGER = "the ringer (the first adult, in record order, who is ringing the Gong)"
# The rest: 86,400 seconds of the real-seconds clock 0x403200, set at 0x461B58.  "Grants vision": the glow timer
# 0x44E907 (30 seconds of that clock), drawn by 0x445B50.
EXTRA = (
    Event("Gong of Wonder", "when a villager finishes \"Ringing the Gong of Wonder\" "
                            "once its rest has passed, one result follows and a new rest of 24 real-life hours "
                            "(real time, at any speed) starts; rung during the rest, nothing happens", (
        "Tiers -- 5% A, 23.75% B (25% of the rest), 71.25% C -- but A and B only once a C result has happened in "
        "this village, so the village's first ring is always C (100%). Each tier's results are equally likely.",
        "Tier A, each 1 in 6 (0.83% of rings): \"Grants vision\" -- only two pictures drawn by the Gong for 30 "
        "real-life seconds (real time); no amount and no villager changes; +1,000 stored food with the crops set "
        "to 800 and the coconut trees to 30; +20,000 to 59,999 tech points; the stored food, the crops and the "
        "coconuts all set to 0; every woman of 18 to 49 villager years who is not pregnant is cured, set to 100 "
        "health and becomes pregnant (father unknown), each if there is room; the ringer dies (health 0).",
        "Tier B, each 1 in 9 (2.64% of rings): every living villager falls sick at 30% each; \"luck\" -- 20 sparkles "
        "by the Gong and the next island event 1 real-life minute later (real time); +10,000 to 29,999 tech points; +1,000 to "
        "2,999 stored food; the ringer loses 90 health, down to 0; the crops set to 0; the coconuts set to 0; "
        "\"Takes youth\" -- whoever is in villager record 6 gets age 1,001 age units (50.05 villager years); "
        "\"Grants youth\" -- whoever is in record 15 gets age 100 age units (5 villager years). The two youth "
        "results act on those fixed records, not on the ringer (a stock bug), and need a ringer to exist.",
        "Tier C, each 1 in 9 (7.92% of rings; \"Grants wisdom\" is two of the nine, 15.83%): every living villager "
        "cured and set to 100 health; +200 to 999 stored food; the crops set to 800; the coconuts set to 30; +3,000 "
        "to 12,999 tech points; -3,000 to -12,999 tech points with no floor; every living villager falls sick at "
        "15% each; \"Grants wisdom\" -- one of the ringer's five skills (20% each) set to 100.",
        "Every amount is each value equally likely. A result for the ringer does nothing when no adult is ringing "
        "(a child rang it): the message still shows.",
        Line("Normal game: the coconut results set the trees to 30, whatever they held.", only_with=GONG_FIX),
        Line("With the patcher's \"Gong of Wonder Coconuts Fix\" (in this game): they add 30 to the coconut trees "
             "instead.", only_with=GONG_FIX),
    )),
)

# The Aspiring Adventurer (the owner, 2026-11-12): "VVFP Aspiring Adventurer.dll" adds it (src/vv_game_mechanics_adventurer.py).
from vv_game_mechanics_adventurer import adventurer_event  # noqa: E402

EVENTS = EVENTS + (adventurer_event(2),)
