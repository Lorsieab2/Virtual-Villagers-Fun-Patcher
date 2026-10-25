"""A New Home (VV1): every island event the game fires, its odds and outcomes (src/vv_game_mechanics_events.py).

Read from the stock executable (research/stock-executables, inputs/vv1-stock-copy); state offsets are the world's
(a save's file offset is 4 more).  The popup words are the game's own strings (the table the getter 0x433880 walks,
0x275 entries of 20 bytes at 0x487208; English first), quoted by id below.

THE SCHEDULER (0x4237BD; the conditions report docs/reports/island-event-conditions.txt, A New Home):
  * The next event time is world+0xA300 on the game clock 0x402F70, which counts real seconds at every speed.
    A new village sets it 15 minutes after its start (0x41C4A9: +0x384); the village's first event sets the
    next 30 minutes later (+0x708); every later one (rand(12) + 12) x 3600 seconds later: 12 to 23 whole
    hours, each 1 in 12.  The Island Events Seen counter world+0x9E40 counts them.
  * When due, an event is tried only with a living villager of 14 or more (0x43BCD0(1)) whose age +0x348
    equals its processed age +0x34C; otherwise nothing is rescheduled and the trigger tries again.
  * Family (0x423818, 0x42383A): with Seen = 0 always an Encounter; otherwise rand(100) < 20 an Encounter
    (20%), else rand(100) < 50 an Island event (40%), else a Crate or vial (40%).
  * Island family: rand(15) at 0x4284DB, re-rolled until the case's check passes (table 0x4286A0 -> 0x428688);
    case 1 (A Mighty Storm) maps to the re-roll itself, so 14 can happen, each equally likely among those whose
    condition holds.  Strength n = the population (living plus babies carried, 0x41CF90) / 3, from 1 to 10
    (0x4239AD).  Bodies: the jump table 0x428430, cases at 0x427CCD .. 0x4283DF.
  * Encounter family: rand(16) at 0x418932, re-rolled until the class check passes (0x418948, table 0x418990);
    variant 5 (The Furry Food) has class 4, the re-roll itself, so 15 can happen.  Subject: 0x43BCD0(0), any
    living villager (present +0x28, health +0x344 > 0) -- the Golden Child included: the picker has no test of
    his flag (+0x36C == 0xC7, tested only at 0x41FBDC, 0x42242D, 0x424B56, 0x42E5A4, 0x438982, 0x43C7AF).
    The Troubled Child's subject is a living child under 280 age units (0x43BE70).  Results: the resolve
    0x419380, table 0x41A384 (cases 0x4193AC .. 0x41A291); the button pressed is [this+0x509C] (1 the first).
  * Crate family (0x42D0E0 -> setup 0x42AFF0): strength rand(100) at 0x42B00C, 0-32 level 1 (33%), 33-66
    level 2 (34%), 67-99 level 3 (33%); then one rand(9) at 0x42B03E, no re-roll.  Results: 0x42B775, table
    0x42D014.  Subject 0x43BCD0(0) as above.
  * A body: health 0 or less makes the villager a body at the villager update (0x438921); burial (0x448F65)
    and the removal of an unburied body after 240 age units (0x42E9A2 -> 0x42E9C3) clear only the present
    byte +0x28.  "Never seen again" (The Mysterious Face, The Book) clears +0x28 at once: no body, no grave.
  * The Golden Child never regains health (his age-unit step is skipped, 0x42EC74 with the age lock
    0x42EB70), so an event's health losses on him add up; at 0 he dies like anyone.
"""
from __future__ import annotations

from vv_game_mechanics_events import Event, Line, share

RESTORE = "vv1_restore_missing_island_events"
FIX = "vv1_fix_vanilla_bugs"
STORY = "vv1_story_cheat_upgrades"

ISLAND, ENCOUNTER, CRATE = 14, 15, 9            # the events each family can fire (stock)
GOLDEN = " Golden Child: can be this villager, and dies or is lost by this result."

RULES = (
    Line("Timing: an event comes 12 to 23 whole real-life hours after the last event, each of the 12 hour counts 1 in 12, at any "
         "speed; in a new village the first comes 15 real-life minutes after it is started and the second 30 "
         "real-life minutes after the first. Paused, the timer waits; after time away at most one event happens."),
    Line("An event happens only when there is a living villager of 14 villager years or more whose shown age "
         "has caught up with the processed age; otherwise the game waits and tries again."),
    Line("Which kind: the village's first event is always an encounter (a choice for one villager). After that "
         "20% are encounters, 40% island events (no choice) and 40% crates or vials found on the beach."),
    Line(f"Within a kind every event whose condition holds is equally likely: with every condition met each "
         f"island event is {share(40, ISLAND)}, each encounter {share(20, ENCOUNTER)} (1 in {ENCOUNTER} of the "
         f"first event), each crate or vial {share(40, CRATE)}. Island events: 14 can happen; encounters: 15; "
         "crates and vials: 9."),
    Line("With the patcher's \"Restore Missing Island Events\" (in this game): A Mighty Storm and The Furry Food "
         f"can happen too while there is stored food, so each island event is then {share(40, ISLAND + 1)} and "
         f"each encounter {share(20, ENCOUNTER + 1)} with every condition met.", only_with=RESTORE),
    Line("Strength n (the island events): the population -- living villagers plus babies being carried -- "
         "divided by 3, from 1 to 10. Crates and vials have their own strength: 1 (33%), 2 (34%) or 3 (33%)."),
    Line("Who: an encounter's or a crate's villager is any living villager, each equally likely, the Golden Child "
         "included (the picker does not test for him); The Troubled Child picks a living child under 14 "
         "villager years. Choosing a button applies the result at once. Every \"N%\" is the game's test "
         "rand(100) < N: the C runtime's random number (0 to 32,767) modulo 100, which makes it N% to within 0.07 "
         "percentage points."),
    Line("The Golden Child and these events: see the Golden Child group, which lists every event that can pick him "
         "and what it does to him (he never regains health, so a loss stays)."),
    Line("With the patcher's \"Fix Vanilla Bugs\" (in this game): no natural island event with a result that kills "
         "or removes its villager can pick the Golden Child (the picker 0x43BCD0 passes over him for those events); "
         "a Pick Island Event or Custom Island Event may still pick him, by design (the owner).", only_with=FIX),
    Line("With the patcher's \"Story / Cheat Upgrades\" (in this game): Pick Island Event chooses the next event "
         "and its rolls instead of the chances above.", only_with=STORY),
)

EVENTS = (
    # -- Island events (no choice; strength n) ------------------------------------------------------------
    Event("The Bad Little Monkey", "an island event, always possible", (
        "The tribe loses 900 x n tech points, down to 0 at least (0x427CCD).",)),
    Event("The Plague of Parrots", "an island event, always possible", (
        "The berry bush loses 200 x n, down to 0 at least (0x427EEA).",)),
    Event("A Plague of Locusts", "an island event; needs Farming technology level 2 or more", (
        "The crop field is emptied to 0 (0x427F4A).",)),
    Event("The Measles Epidemic", "an island event; needs a living child under 14 villager years", (
        "Every living villager under 280 age units (14 villager years) falls sick (0x427D6B); no health is "
        "lost by the event itself.",)),
    Event("The South Wind", "an island event, always possible", (
        "The berry bush, the crop field and the stored food each lose 80 x n, each down to 0 at least "
        "(0x427F83).",)),
    Event("The Heat Wave", "an island event, always possible", (
        "Each villager, 50% each: goes swimming or relaxes (0x428023); nothing else changes.",)),
    Event("Isola Day Celebration", "an island event, always possible", (
        "The stored food loses 10 for every villager (babies being carried counted), down to 0 at least, and "
        "the village celebrates (0x42808A).",)),
    Event("Blessings Day Celebration", "an island event, always possible", (
        "As Isola Day, the stored food loses 10 for every villager, down to 0 at least, and the village celebrates (0x4280F2).",)),
    Event("The Big Wave", "an island event; needs the beach cleaned up", (
        "The beach is covered with debris again: its cleaned flag and its clean-up progress go back to 0 "
        "(0x428116).",)),
    Event("The Good Little Monkey", "an island event, always possible", (
        "The tribe gains 900 x n tech points (0x42815B).",)),
    Event("The Greedy Little Monkey", "an island event, always possible", (
        "The stored food gains 200 x n (0x4281A1).",)),
    Event("The Barrel O` Babies", "an island event; needs room for new villagers when it is picked", (
        "1 toddler for n of 1 to 4, 2 for 5 to 7, 3 for 8 to 10 (0x4281E7); room is checked only when the "
        "event is picked, and every toddler is then made.",
        "Each toddler (the game's villager maker 0x43C350): 70 to 89 age units old (3.5 to 4.45 villager "
        "years, each 1 in 20), a boy or a girl 50% each, 90 health, family number 1, every skill 0 -- with The "
        "School solved Research, Building, Healing and Farming each gain 0 to 6 (each 1 in 7) -- a head and a "
        "body each one of 0 to 18 for a boy, 0 to 19 for a girl, and likes and dislikes as at a birth (none "
        "70%, one 21%, two 9%).")),
    Event("The North Wind", "an island event, always possible", (
        "The berry bush and the crop field each gain 100 x n (0x428388).",)),
    Event("The Helpful Honeybees", "an island event, always possible", (
        "The berry bush gains 300 x n (0x4283DF).",)),
    Event("A Mighty Storm", "an island event added by the patch, while there is stored food", (
        "All the stored food is washed away: food 0 (0x427D32).",), only_with=RESTORE),
    # -- Encounters (a villager, two buttons) -------------------------------------------------------------
    Event("The Trapped Whale", "an encounter; needs Spirituality technology below level 3", (
        "\"Help free the whale.\": Spirituality technology goes up 1 level (0x4193AC).",
        "\"Harvest the whale for food.\": +1,000 stored food.")),
    Event("The Strange Berries", "an encounter, always possible", (
        Line("\"Taste the strange berries.\": 51% the villager feels young again -- age and processed age set to "
             "250 age units (12.5 villager years; a pregnancy is kept) -- and 49% the villager dies (health set "
             "to 0) (rand(100) at 0x4194B6)." + GOLDEN.replace("dies or is lost", "dies")),
        "\"Ignore the seductive plant.\": nothing changes.")),
    Event("The Old Drum", "an encounter, always possible", (
        "\"Cut open the drum.\": the villager's Healing skill becomes 100 (0x4195CC).",
        "\"Keep the drum to make music.\": the berry bush gains 500.")),
    Event("The Mysterious Face", "an encounter, always possible", (
        Line("\"Get a closer look.\": 51% the villager is never seen again (taken from the village: no body, no "
             "grave); 49% a stranger joins -- 281 age units (14.05 villager years), a man or a woman 50% each, "
             "90 health, Farming 100 and the other skills 0, family number 1, made as the Barrel O` Babies' "
             "toddlers are (with The School solved, Farming can reach 106) -- if there is room for a villager, and without room the villager "
             "is never seen again instead (rand(100) at 0x4196ED)." + GOLDEN.replace("dies or is lost",
                                                                                     "is lost")),
        "\"Cautiously back away.\": nothing changes.")),
    Event("The Visitor", "an encounter; needs Medicine technology below level 3", (
        "\"Allow him to gather samples.\": Medicine technology goes up 1 level (0x4197CF).",
        "\"Tell the stranger to leave.\": the villager falls sick, and every living villager falls sick at "
        "75% each (0x4188B0); no health is lost by the event itself.")),
    Event("A Mysterious Vial (red liquid)", "an encounter, always possible. Item: a vial of an oily, red liquid", (
        "\"Drink the liquid.\": 50% a red vapour makes every other villager sick (the drinker is not); 50% the "
        "drinker's Healing becomes 100 (rand(100) at 0x419953).",
        "\"Pour it out.\": nothing changes.")),
    Event("The Troubled Child", "an encounter; needs a living child under 14 villager years, who is the one", (
        "\"Let him (her) try farming.\": the child falls sick and gains 50 Farming, up to 100 (0x419B29).",
        "\"Let him (her) try research.\": the child's Research becomes 100 and the tribe gains 3,000 tech "
        "points.")),
    Event("A Mysterious Vial (blue liquid)", "an encounter, always possible. Item: a vial of an oily, blue liquid", (
        "\"Drink the liquid.\": 50% the drinker turns back into a toddler -- age and processed age 80 age units "
        "(4 villager years) and any pregnancy ended -- and 50% the drinker dances, with no lasting change "
        "(rand(100) at 0x419C50). The Golden Child is set back to 100 age units at the next game tick.",
        "\"Pour it out.\": nothing changes."),
        patched=((FIX, "the drinker's pregnancy ends completely, the number of babies she carried included; in "
                       "the normal game that number is kept, so her next single pregnancy brings that many "
                       "babies"),)),
    Event("The Suspicious Monkey", "an encounter; needs a living child under 14 villager years (the villager "
                                   "itself can be anyone)", (
        Line("\"Try to scare the monkey away.\": the villager loses 50 health, down to 0 at least (0x419D51); "
             "at 0 the villager dies. Golden Child: can be this villager, and the losses add up."),
        "\"Wait and see what it does.\": the villager gains 60 Healing, up to 100.")),
    Event("The Wild Mushroom", "an encounter, always possible", (
        Line("\"Taste the mushroom.\": 50% delicious -- Farming +65 up to 100, and +300 to 499 stored food (each "
             "amount 1 in 200) -- and 50% poisoned -- sick, and 25 to 49 health lost (each 1 in 25), down to 0 "
             "at least (rand(100) at 0x419E74); at 0 the villager dies. Golden Child: can be this villager, "
             "and the losses add up."),
        "\"Discard the mushroom.\": nothing changes.")),
    Event("The Black Pearl", "an encounter, always possible", (
        "\"Share the treasure with the tribe.\": every villager gains 5 to 9 health (each rolled 1 in 5 for "
        "each villager), up to 100, and the village celebrates (0x41A000).",
        "\"Keep the pearl hidden.\": the villager's first two dislikes become crowds and work (dislike slots 1 "
        "and 2 overwritten: 1 and 42 in the game's list, string 0xD6) (0x41A0B5).")),
    Event("The Dream", "an encounter, always possible", (
        "\"Enter the right cave.\": the villager's first two dislikes become fish and the ocean (33 and 17 in "
        "the list) (0x41A130).",
        "\"Enter the left cave.\": nothing changes.")),
    Event("The Moth", "an encounter, always possible", (
        "\"Help the moth.\": nothing changes (0x41A1C1).",
        "\"Leave the moth alone.\": the villager's Healing becomes 100.")),
    Event("The Book", "an encounter, always possible", (
        Line("\"Read the book.\": the villager is never seen again (taken from the village: no body, no grave) "
             "(0x41A221)." + GOLDEN.replace("dies or is lost", "is lost")),
        "\"Bring it to the researchers.\": nothing changes.")),
    Event("The Brass Compass", "an encounter, always possible", (
        "\"Use it to mash berries.\": every villager gains 10 to 19 Farming (each rolled 1 in 10 for each "
        "villager), up to 100 (0x41A291).",
        "\"Let the researchers have it.\": the tribe gains 2,000 to 4,999 tech points (each 1 in 3,000).")),
    Event("The Furry Food", "an encounter added by the patch, while there is stored food", (
        "\"Remove the moldy pieces.\": every living villager falls sick at 50% each (0x41989D).",
        "\"Throw out all the food.\": the stored food becomes 0."), only_with=RESTORE),
    # -- Crates and vials (strength 1, 2, 3 at 33%, 34%, 33%; "Leave it alone." / "Pour it out." change nothing)
    Event("A Mysterious Crate (wooden)", "a crate, 1 in 9 of crates and vials. Item: a wooden crate", (
        "\"Open it.\": +500, +1,000 or +1,500 stored food at strength 1, 2, 3 (coconuts, golden ripe bananas, "
        "juicy steaks) (0x42B77C).",)),
    Event("A Mysterious Crate (carefully sealed)", "a crate. Item: a carefully sealed crate", (
        "\"Open it.\": +1,000, +2,000 or +3,000 tech points at strength 1, 2, 3 (0x42BA10).",)),
    Event("A Mysterious Crate (badly weathered)", "a crate. Item: a badly weathered crate", (
        "\"Open it.\": +500, +1,000 or +1,500 tech points, and every living villager falls sick at 15%, 20% or "
        "25% each, at strength 1, 2, 3; no health is lost (0x42BCE0).",)),
    Event("A Mysterious Crate (rotting)", "a crate. Item: a rotting, wooden crate", (
        Line("\"Open it.\": every living villager is bitten at 20%, 30% or 45% each -- sick, and 10, 15 or 20 "
             "health lost, down to 0 at least -- at strength 1, 2, 3; then the opener falls sick and loses 15 "
             "more health with no floor (0x42C127). At 0 health a villager dies. Golden Child: can be the opener "
             "or bitten, and the losses add up."),)),
    Event("A Mysterious Crate (watertight)", "a crate. Item: a painstakingly well prepared, watertight crate", (
        "\"Open it.\": with room for villagers when it is opened (0x42C358), 1, 2 or 3 infants at strength 1, 2, "
        "3, each 70 to 89 age units old (3.5 to 4.45 villager years), made as the Barrel O` Babies makes them; "
        "without room nothing (0x42C343).",)),
    Event("A Mysterious Crate (old fruit)", "a crate. Item: a rotten and half-eaten, old fruit crate", (
        Line("\"Open it.\": giant spiders bite the opener, who loses 40, 70 or 110 health at strength 1, 2, 3, with "
             "no floor (0x42C5BA); at 0 or less the opener dies, so strength 3 always kills. Golden Child: can be "
             "the opener; strength 3 kills him, and the other losses add up."),)),
    Event("A Mysterious Vial (red, from the sea)", "a vial. Item: a watery or oily red vial (the word changes "
                                                   "nothing)", (
        "\"Drink the liquid.\": the drinker's head is re-rolled: a man gets one of heads 0 to 18, a woman one of "
        "0 to 19, each equally likely (the old head can come again) (0x42C894); the strength changes only the "
        "words.",)),
    Event("A Mysterious Vial (blue, from the sea)", "a vial. Item: a watery or oily blue vial", (
        "\"Drink the liquid.\": one skill, each 20% -- Farming, Breeding, Building, Research or Healing -- gains "
        "50, 75 or 100 at strength 1, 2, 3, up to 100 (rand(5) at 0x42CA61; 0x437230).",)),
    Event("A Mysterious Vial (fizzy, from the sea)", "a vial. Item: a watery or oily fizzy vial", (
        "\"Drink the liquid.\": all five skills lose 30, 50 or 70 at strength 1, 2, 3, down to 0 at least "
        "(0x42CCDB).",)),
)
