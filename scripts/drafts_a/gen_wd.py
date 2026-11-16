"""Write the owner-approved draft "New Events - What's That Doing Here" (WD-01..50) as collection events, then format
and check them (scripts/drafts_a/da_common.py has the shape and the defaults; this table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no sensitivity edit.  Every animal is real, none
is harmed, each goes home or is left in peace; theories (a bird, a prank, a spirit, the sea once over the hill) stay
theories; no legendary creature is named.  The chicken (WD-20), pig (WD-18) and other animals are kept exactly as
written (narrative is not gameplay).  Effects as the draft's brackets: WD-07 A, WD-33 B, WD-37 A small food gain.
One grammar fix: WD-27 "(his/hers)" has no placeholder -> "(his/her) bowl".
The owner's naming rule (2026-11-15), "cast" edits: a single person present in the scene, named only by role, is a
cast villager named at the first mention ("(child), a child,"): WD-04 child and elder, WD-06 child, WD-09 child,
WD-22 child, WD-25 elder, WD-26 child, WD-27 visitor, WD-29 drummer, WD-30 child, WD-32 elder, WD-40 old fisher
(cast an elder).  Left alone: groups (the children, the elders, a crowd), WD-24's three elders ("One says..." of the
elders asked), WD-40's "One of them" (of the elders), WD-26 A's guess "it was a child", WD-50's "the next person" and
"someone" (the circle; a deliberate unknown), WD-22's unknown prankster.
WD-14 and WD-40 titles: the owner's renames (owner-title-changes.md).

    python scripts/drafts_a/gen_wd.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_wd"
TABLE: dict[int, dict] = {
    1: {"desc": "A villager finds a small upright black-and-white bird on the beach at dawn: fetch a friend, or keep a distance."},
    2: {"desc": "A seal has come up the stream for a nap in the best water-filling spot: wait for it, or fill up elsewhere."},
    3: {"desc": "A villager lifts the lid of the cooking pot and finds a crab inside, looking as if the villager is the intruder."},
    4: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "child": c.CHILD, "elder": c.ELDER},
        "cast": [(53, "A child suggests", "(child), a child, suggests"),
                 (53, "An elder suggests", "(elder), an elder, suggests")],
        "desc": "A coconut is balanced on top of a villager's roof, and nobody knows how it got there."},
    5: {"desc": "A small silver fish is swimming in the big water jar: keep it as a guest for the day, or take it back at once."},
    6: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "child": c.CHILD},
        "cast": [(77, "A child admits", "(child), a child, admits")],
        "desc": "A villager finds a bright orange starfish clinging to the doorpost, a long way from the sea."},
    7: {"desc": "A villager goes to the canoe to fish and finds a pelican already sitting in it: take it fishing, or shoo it out."},
    8: {"desc": "A small green frog is sitting in the fruit bowl, and a villager only notices when a mango blinks."},
    9: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "child": c.CHILD},
        "cast": [(110, "a child starts", "(child), a child, starts")],
        "desc": "A single sandal hangs in the tree outside a villager's hut, and nobody is missing one: get it down, or leave it."},
    10: {"desc": "A yellow flower is growing out of the top of a villager's roof: let it grow, or move it to the ground."},
    11: {"desc": "A hermit crab walks past wearing a small clay cup instead of a shell: find it a shell, or find the cup's owner."},
    12: {"desc": "A small brown bat is asleep on the roof beam of a villager's hut in the middle of the day."},
    13: {"desc": "A villager opens the storehouse and an owl stares back from the top shelf with solemn disapproval."},
    14: {"desc": "A melon vine is growing in the middle of the busiest path in the village: protect it, or move it."},
    15: {"desc": "A heron on the far bank of the stream has been staring at a villager, not at the fish, for some time."},
    16: {"desc": "The bathing pool is full of small birds having a wonderful bath: wait your turn, or join them."},
    17: {"desc": "A nest blown down by the wind holds all the small shiny things that have gone missing from a villager's hut."},
    18: {"desc": "A villager comes to rest in the hammock and finds a young pig asleep in it: wake it, or share the shade."},
    19: {"desc": "A villager wakes up nose to nose with a lizard sitting on the pillow: lie very still, or say good morning."},
    20: {"desc": "A chicken is crowing at dawn on the roof of a villager's hut: climb up and get it down, or give up and get up."},
    21: {"desc": "Wet webbed footprints lead into a villager's hut and under the sleeping mat, where a duck looks up."},
    22: {"roles": {"subject": c.ADULT, "child": c.CHILD},
         "cast": [(269, "A child giggles", "(child), a child, giggles")],
         "desc": "Overnight someone has put seaweed on the big carved post like a wig: take it off, or wait for someone to own up."},
    23: {"desc": "After a storm, a single enormous leaf blocks a villager's doorway, and nobody knows what tree it came from."},
    24: {"desc": "A perfect ring of small white mushrooms appears overnight in a villager's garden: step inside, or leave it alone."},
    25: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "elder": c.ELDER},
         "cast": [(305, "takes it to an elder", "takes it to (elder), an elder")],
         "desc": "A villager reaches into the fruit basket and pulls out a large, warm, speckled egg."},
    26: {"roles": {"subject": c.ADULT, "child": c.CHILD},
         "cast": [(317, "A small child at the back", "(child), a small child at the back")],
         "desc": "Someone has written a greeting in huge letters on the beach overnight: write back, or ask around."},
    27: {"roles": {"subject": c.ADULT, "visitor": c.ADULT},
         "cast": [(329, "A visitor from another village", "(visitor), a visitor from another village,")],
         "fixes": [(326, "(his/hers)", "(his/her) bowl")],
         "desc": "A neat bowl of fresh fruit sits on a rock at the far end of the beach, with nobody around."},
    28: {"desc": "A villager's fishing net, left on the beach to dry, is draped across the top of a tall tree."},
    29: {"roles": {"subject": c.ADULT, "drummer": c.ADULT},
         "cast": [(347, "the drummer starts", "(drummer), the drummer, starts")],
         "desc": "At the evening gathering the drum makes strange scrabbling noises: look inside, or play around it."},
    30: {"roles": {"subject": c.ADULT, "child": c.CHILD},
         "cast": [(365, "a small child opens", "(child), a small child, opens")],
         "pron": {"b": {0: "child"}},
         "desc": "Every hut in the village wakes to a single smooth pebble on its doorstep: keep it, or investigate."},
    31: {"desc": "A beautifully made kite is stuck at the top of the tallest tree, and nobody in the village made it."},
    32: {"roles": {"subject": c.ADULT, "elder": c.ELDER},
         "cast": [(383, "An elder says", "(elder), an elder, says")],
         "desc": "On a hot afternoon, small cold white stones fall from the sky and melt in a villager's hand."},
    33: {"desc": "A fresh fish lies on a villager's roof while a seabird circles above: give it back to the bird, or keep it."},
    34: {"desc": "A villager sits down with a cup of tea and finds a tiny shrimp swimming around in it."},
    35: {"desc": "A villager tips over the old feast pot to clean it and finds a bird's nest with three tiny eggs underneath."},
    36: {"desc": "A pale green moth the size of a hand sits on a villager's doorframe: admire it, or go in very carefully."},
    37: {"desc": "A forgotten basket of seeds has sprouted into a little jungle: plant them all, or keep it as it is."},
    38: {"desc": "Something has walked on a villager's roof every night for a week: go out with a torch, or decide not to know."},
    39: {"desc": "At the very top of the highest hill, far from the sea, a villager finds a seashell set in the rock."},
    40: {"roles": {"subject": c.ADULT, "fisher": c.ELDER},
         "cast": [(473, "it belongs to an old fisher", "it belongs to (fisher), an old fisher")],
         "pron": {"b": {0: "fisher", 1: "fisher"}},
         "desc": "A carved walking stick stands upright in the sand with no footprints near it: leave it, or take it to the elders."},
    41: {"desc": "A single coconut is floating and spinning in the middle of the drinking pool: fish it out, or wait for the wind."},
    42: {"desc": "A large blue butterfly lands on the end of a villager's nose: stay perfectly still, or ask a friend for help."},
    43: {"desc": "A villager wakes up to small grey feathers everywhere in the hut: clean up, or find the bird."},
    44: {"desc": "A low, humming music drifts across the village every windy evening, and nobody is playing anything."},
    45: {"desc": "Sheltering from the rain, a villager sees a crab walk past holding a leaf over its head like an umbrella."},
    46: {"pron": {"b": {0: "subject"}},
         "desc": "After a stormy night, a child finds a bright reef fish swimming in a puddle near the beach."},
    47: {"desc": "A villager pulls in the fishing net and finds a tiny seahorse curled around a strand."},
    48: {"desc": "Something in a villager's hut chirps all night and stops whenever anyone comes near: hunt it down, or sleep."},
    49: {"desc": "A line of ants marches through a villager's hut carrying a whole red flower like a festival float."},
    50: {"desc": "A large seabird walks up and sits down in the circle at dinner: share some fish, or ignore it."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
