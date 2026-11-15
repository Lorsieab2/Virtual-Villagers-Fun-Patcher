"""Write the owner-approved draft "New Events - Inner Life Part V" (events 81-100) as collection events, then format
and check them (scripts/drafts_a/da_common.py has the shape and the defaults; this table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no sensitivity edit.  No effects (the draft: story
only).  90 and 100 are single popups.  Roles: 81 "two adults close in age" and 97 ("when we were twelve") are cast
at most 5 years apart; 85 (name2) is a small child (3-8; the draft's note: story only where no second villager);
91 a child 4-9 and an elder; 93 an adult 35+ and a young adult; 96 an adult 30-50; 99 an adult 25+.  83 and 100
"an adult or elder": 18+.  94 "(name1)'s parents" is a family story (the draft's note), no relation needed.
Casting edits (the owner's naming rule, 2026-11-15): 81 the elder and "another" at the fire, 88 the small child, 95
the child, 98 the two children who speak (the pronoun follows the one who answers; no grammar fix).

    python scripts/drafts_a/gen_il05.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il05"
CLOSE = dict(c.ADULT, max_age_gap={"role": "subject", "years": 5})
TABLE: dict[int, dict] = {
    81: {"roles": {"subject": c.ADULT, "friend": CLOSE, "elder": c.ELDER, "other": c.ADULT},
         "cast": [(14, "One elder remembers", "(elder), an elder, remembers"), (14, "Another says", "Another, (other), says")],
         "desc": "Two old friends remember the same childhood fall into the stream, but each remembers the other falling in."},
    82: {"pron": {"a": {0: "subject", 1: "subject", 2: "subject"}},
         "desc": "A villager is asked about the oldest thing they own, and fetches a small, chipped clay cup."},
    83: {"pron": {"a": "subject"},
         "roles": {"subject": c.ADULT, "friend": c.ADULT},
         "desc": "A villager stops where a great old tree once stood and finds a young sapling growing there now."},
    84: {"desc": "A villager has spent all morning trying to remember the name of a neighbor's noisy pet bird from long ago."},
    85: {"pron": {"a": {0: "subject"}},
         "roles": {"subject": c.ADULT, "friend": c.ages(3, 8)},
         "desc": "While repairing an old roof, a villager finds their favorite childhood toy tucked deep in the thatch."},
    86: {"pron": {"a_label": "friend"},
         "desc": "Someone tells the old family crab story wrong at a gathering: correct them, or let the new version live."},
    87: {"pron": {"setup": {0: "subject"}},
         "desc": "A villager fondly remembers the year it rained every day, though a friend remembers the complaining."},
    88: {"roles": {"subject": c.ADULT, "child": c.ages(3, 8)},
         "cast": [(101, "When a small child asks later", "When (child), a small child, asks later")],
         "pron": {"b": {1: "subject"}},
         "desc": "A villager passes the huge rock they were afraid to climb as a child, and finds it is about knee high."},
    89: {"desc": "A villager is asked about their first memory: a bright yellow bird on the edge of a bowl."},
    90: {"desc": "A villager finds a little fish they carved into a tree as a child, now at about the height of their waist."},
    91: {"pron": {"setup": "subject", "a": {1: "subject"}},
         "desc": "A child asks an elder to remember that they found a perfectly ordinary grey pebble today."},
    92: {"desc": "Two villagers discover that each of them remembers teaching the other one to swim."},
    93: {"desc": "A villager watching a loud, certain young adult argue on the beach sees their own younger self."},
    94: {"desc": "A villager leaning on an old hut post notices the notches that marked how tall they grew each year."},
    95: {"roles": {"subject": c.ADULT, "child": c.CHILD},
         "cast": [(173, "Today a child asks", "Today (child), a child, asks"), (176, "The child sits", "(child) sits"),
                  (176, "The child cheers", "(child) cheers"), (179, "The child takes", "(child) takes")],
         "pron": {"setup": "subject"},
         "desc": "A villager who once made a leaf whistle that scared the birds tries again for a child: a small wet noise."},
    96: {"pron": {"setup": {6: "subject"}, "b": "subject"},
         "desc": "At the end of an ordinary day, a villager realizes they are probably about halfway through their life."},
    97: {"roles": {"subject": c.ADULT, "friend": CLOSE},
         "desc": "A villager tells a favorite story about a lost pearl, and a friend goes quiet: it was their story."},
    98: {"roles": {"subject": c.ADULT, "asker": c.CHILD, "kid": c.CHILD},
         "cast": [(215, "When one of them asks", "When (asker), one of them, asks"), (215, "another says", "another, (kid), says")],
         "pron": {"b": {1: "kid"}},
         "desc": "A villager sees children on the beach playing a game they invented as a child, with new rules."},
    99: {"desc": "A villager tidying their hut finds a list written as a teenager of things to do when grown up."},
    100: {"roles": {"subject": c.ADULT},
          "desc": "From the top of the hill, a villager notices the little worn paths in the grass that nobody made on purpose."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
