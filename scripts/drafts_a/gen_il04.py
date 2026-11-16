"""Write the owner-approved draft "New Events - Inner Life Part IV" (events 61-80) as collection events, then format
and check them (scripts/drafts_a/da_common.py has the shape and the defaults; this table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no edit, no grammar fix.  Effects as the draft's
brackets: 70 A (name1) celebrates, 77 A small food gain.  64, 73 and 76 cast an adult with a child (the draft's
note: any child, no relation needed); 66 "an adult or elder": 18+.  78 is a single popup.  Casting edits (the owner's naming rule): 73 the surprised builder, 77 the fisher who speaks.  Near-duplicate (the draft's own note): 80 "The Lucky
Side of the Bed" overlaps in spirit with 41 "Thirty-Seven Steps" (both "the routine went wrong"); built, with a
ledger note, for the owner to keep or drop.

    python scripts/drafts_a/gen_il04.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il04"
TABLE: dict[int, dict] = {
    61: {"desc": "A villager has named every one of their tools, and is confused when someone asks to borrow just a basket."},
    62: {"pron": {"setup": {0: "subject"}},
         "desc": "A villager who eats exactly the same breakfast every day is offered a warm, sticky little cake."},
    63: {"pron": {"setup": {3: "subject"}},
         "desc": "A villager hums the same tune while working without knowing it, and the high bit is getting to a neighbor."},
    64: {"desc": "A villager says goodnight to the trees on the way home, and tonight a child is following and watching."},
    65: {"desc": "A villager has added one stone a day to a pile on the beach for years, and someone finally asks why."},
    66: {"roles": {"subject": c.ADULT, "friend": c.ADULT},
         "desc": "A villager ties a knot in a long string after every really good day, and a friend finds it while tidying."},
    67: {"pron": {"b": "subject"},
         "desc": "A villager guesses the weather out loud every morning, and today a friend says the guess is wrong."},
    68: {"desc": "On a bad day, a villager reaches for the emergency snack hidden in the thatch and finds a very full lizard."},
    69: {"pron": {"b_label": "friend"},
         "desc": "A villager setting off on the yearly first cold swim finds a friend waiting on the sand, asking to come."},
    70: {"desc": "A villager picks a word every morning and uses it as often as possible, and today's word is magnificent."},
    71: {"desc": "A villager scratches their nose before every decision, and a rumor says it is a secret signal."},
    72: {"desc": "A villager's favorite carved spoon has gone missing at dinner, and no other spoon is right."},
    73: {"roles": {"subject": c.ADULT, "friend": c.ages(4, 10), "builder": c.ADULT},
         "cast": [(161, "and a very surprised builder", "and (builder), a very surprised builder")],
         "pron": {"setup": "subject"},
         "desc": "A child asks a villager who thanks the water whenever they fill a jar whether the water can hear."},
    74: {"desc": "A villager who cuts their hair once a year asks a friend who has never cut hair to do it this time."},
    75: {"desc": "A villager always leaves the last piece of fruit for whoever comes next, and today someone reaches for it."},
    76: {"pron": {"a": "subject"},
         "desc": "A child who knows every word of the same bedtime story asks for a new one tonight."},
    77: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "fisher": c.ADULT},
         "cast": [(206, "and one of them says,", "and (fisher), one of them, says,")],
         "pron": {"setup": "subject"},
         "desc": "A villager waves at every canoe out on the water, even far-off specks that might be logs."},
    78: {"desc": "A villager always sneezes exactly three times, and tonight the whole village counts along at dinner."},
    79: {"pron": {"a": {1: "subject"}},
         "desc": "A villager who stacks the baskets by size every evening finds them already stacked by color."},
    80: {"note": "near-duplicate in spirit of il041 Thirty-Seven Steps (the draft's own note: both are the routine went "
                 "wrong; 80 is the easier one to drop); built for the owner to keep or drop",
         "desc": "A villager who always gets up on the left side of the sleeping mat rolls off on the right today."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
