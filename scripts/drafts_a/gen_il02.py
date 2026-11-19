"""Write the owner-approved draft "New Events - Inner Life Part II" (events 11-40) as collection events, then format
and check them (scripts/drafts_a/da_common.py has the shape and the defaults; this table is the authoring record).

The file begins with a ChatGPT preamble and ends with ChatGPT's "directions for the next batch": notes rows, never
shown (the manifest's rows).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no edit, no grammar fix.  No effects (the draft
gives no brackets): every event is story only.  Roles from a trade the text names: 16 (name1) "an excellent farmer"
(Farming), 17 "Ask a Scientist" (name2) (Research), 18 the elder who "loved building things" (Building), 25 "an
adult scientist" (Research).  Casting edits (the owner's naming rule, 2026-11-15): 13 the neighbor, 18 the
apprentice, 32 the hummer is (name2) (as the answer reads).  16 B "A passing villager" left as a generic passer-by.  Flag for the owner (left as written): 25 "Are you going to publish this?" and 38 "a
scholarly monograph" are modern-sounding words in an Isola story.

    python scripts/drafts_a/gen_il02.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il02"
TABLE: dict[int, dict] = {
    11: {"desc": "A child has invented a machine of sticks, string, a coconut shell and a lot of mud that does everything."},
    12: {"pron": {"setup": "subject"},
         "desc": "A villager wakes from a vivid dream in which a friend sold their sandals to buy a purple chicken."},
    13: {"roles": {"subject": c.ADULT, "neighbor": c.VILLAGER},
         "cast": [(61, "helps a neighbor,", "helps (neighbor), a neighbor,")],
         "desc": "A villager has written a very long list of things to do today, and by midday has only written the list."},
    14: {"desc": "A child who wants to be the bravest in the village finds a large beetle beside the sleeping mat."},
    15: {"desc": "A villager's almost perfect day has one small hole in a sandal: repair it, or complain about it."},
    16: {"roles": {"subject": c.skilled(c.ADULT, "Farming"), "friend": c.ADULT}, "pron": {"a": "subject"},
         "desc": "A villager who is an excellent farmer has a secret: they want to learn to dance."},
    17: {"roles": {"subject": c.VILLAGER, "friend": c.skilled(c.ADULT, "Research")},
         "desc": "A villager has spent all morning wondering why the ocean is salty: ask a scientist, or invent an answer."},
    18: {"roles": {"subject": c.skilled(c.ELDER, "Building"), "friend": c.ADULT, "apprentice": c.ages(14, 25)},
         "cast": [(133, "watching a young apprentice at work", "watching (apprentice), a young apprentice, at work"),
                  (141, "watches the apprentice", "watches (apprentice)")],
         "pron": {"setup": "subject", "b": "subject"},
         "desc": "An elder watching a young apprentice remembers another path they might have taken long ago."},
    19: {"desc": "A villager having a slightly frustrating day is told they are very good at explaining things."},
    20: {"desc": "A villager crosses the village to fetch something important and forgets what it was."},
    21: {"pron": {"setup": "subject", "b": "subject"},
         "desc": "A villager is pleased a friend was recognized for a discovery, but wishes their own help had been mentioned."},
    22: {"desc": "A villager announces there is nothing to worry about, then demonstrates an elaborate way of stacking coconuts."},
    23: {"desc": "A young child is certain that something called the Midnight Scratcher lives under their sleeping mat."},
    24: {"desc": "A villager is so tired of making decisions all morning that even choosing lunch feels exhausting."},
    25: {"roles": {"subject": c.skilled(c.ADULT, "Research"), "friend": c.ADULT},
         "desc": "A scientist who has studied an unusual plant for weeks announces a discovery at last."},
    27: {"desc": "A villager has written a proud poem about the sea in which nearly every line ends with the word moon."},
    28: {"desc": "A villager is offered the project they always wanted, and feels an unexpected uneasiness about success."},
    29: {"desc": "A villager has accomplished something small but personally important: tell a friend, or keep it private."},
    30: {"desc": "A villager asked to speak at a gathering imagines every possible disaster, including a falling coconut."},
    31: {"desc": "A child is terribly, monumentally bored and has told every adult in the village at least twice."},
    32: {"cast": [(357, "hears someone humming", "hears (name2) humming")], "pron": {"setup": "subject"},
         "desc": "An elder hears someone humming a melody they have not heard in decades."},
    33: {"desc": "A villager still feels irritated about a tiny scratch a friend left on a borrowed basket three weeks ago."},
    34: {"desc": "A child asks whether a fish that could climb a tree would still be a fish."},
    35: {"desc": "A villager praised as a hero for helping repair a footbridge finds the attention deeply embarrassing."},
    37: {"desc": "A child who broke a small clay cup says a bird did it, though the hut door was closed."},
    38: {"desc": "A villager content with an ordinary life puzzles a friend who has several ambitious plans."},
    39: {"desc": "A villager preparing lunch remembers something from years ago and begins to cry without knowing why."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
