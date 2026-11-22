"""Write the owner-approved draft "New Events - Inner Life Part IX" (events 161-180, children and teens) as
collection events, then format and check them (scripts/drafts_a/da_common.py has the shape and the defaults; this
table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no sensitivity edit.  162 is the batch's one
teen romance (two teens within two years: max_age_gap 2), a dance or sitting and talking, nothing more (the
draft's note).  168: the dare is optional and saying no is fine.  Supervision stays in the picture (161, 166, 169).
Effect as the draft's bracket: 167 A small Building skill (where the game has one).  No harm in any outcome.
Roles: 162 / 174 two teens; 171 two children 7-13; 176 two children 6-12; 167 (name2) an adult builder -> Building
skill; 179 a child aged 13 -> 13 only; 164 "from the same household where the game records it, or any adult" ->
any adult (no game records a household).
Casting (the owner's naming rule, 2026-11-15): 166 the little one who speaks, 168 the child who teases and the
child who agrees, 176 the adult are cast villagers named at the first mention (176's later mentions by name).
Left uncast: groups ("the little ones", "the teens", "the grown-ups"), 177's grandmother (in a story), 178's and
179's "somebody" / "someone".
Grammar: 170 "(his/hers)" -> "(his/her) own"; 174 "(his/hers)" -> "(his/her) canoe".

    python scripts/drafts_a/gen_il09.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il09"
TABLE: dict[int, dict] = {
    161: {"pron": {"a": {0: "subject", 1: "subject", 4: "subject"}},
          "desc": "A child announces they are old enough to fetch the water alone with the big jar: let them go, or offer the small one."},
    162: {"roles": {"subject": c.TEEN, "friend": dict(c.TEEN, max_age_gap={"role": "subject", "years": 2})},
          "pron": {"setup": "subject", "a": {0: "subject"}},
          "desc": "There is music at the fire, and two teens looking for each other to ask for a dance keep missing each other."},
    163: {"desc": "A child and friends have opened a mud bakery on the beach, and a passing villager is called over to buy a cake."},
    164: {"pron": {"a": {0: "friend"}},
          "desc": "A teen announces they are cooking dinner tonight, all of it, alone: stay out of the way, or offer one piece of advice."},
    165: {"pron": {"setup": "subject"},
          "desc": "It is long past dark, and a small child is not tired, not tired at all."},
    166: {"roles": {"subject": c.ages(10, 13), "little": c.ages(3, 9)},
          "cast": [(74, "One of the little ones says,", "One of the little ones, (little), says,")],
          "desc": "An older child minding the little ones has made them sit in a row, and has no idea what comes next."},
    167: {"roles": {"subject": c.TEEN, "friend": c.skilled(c.ADULT, "Building")},
          "fx": {"a": [c.sk("subject", "Building")]},
          "pron": {"setup": "subject", "a": {0: "subject"}},
          "desc": "A teen's first day helping the builders is not going well: ask for one simple job, or keep trying everything."},
    168: {"roles": {"subject": c.ages(7, 12), "teaser": c.ages(7, 12), "ally": c.ages(7, 12)},
          "cast": [(101, "One of the others starts to tease, but another child says,",
                    "One of the others, (teaser), starts to tease, but (ally), another child, says,")],
          "desc": "The children dare each other to touch the scary old tree at the edge of the jungle, and it is one child's turn."},
    169: {"pron": {"setup": "subject", "b": {1: "friend"}},
          "desc": "The baby turtles might hatch on the beach tonight, and a teen asks to stay up and watch."},
    170: {"fixes": [(125, "It's (his/hers).", "It's (his/her) own.")],
          "desc": "A child has found a shortcut to the beach that takes much longer and is very muddy, and is extremely proud of it."},
    171: {"roles": {"subject": c.ages(7, 13), "friend": c.ages(7, 13)},
          "desc": "One child hates sweeping and another hates fetching water, and a very serious negotiation begins."},
    172: {"pron": {"a": {0: "friend"}},
          "desc": "Everyone keeps asking a teen what they want to be, and the teen does not know."},
    173: {"desc": "A child lays out empty shells on the sand as a hotel for hermit crabs who need a bigger room."},
    174: {"roles": {"subject": c.TEEN, "friend": c.TEEN},
          "fixes": [(170, "falls out of (his/hers) too", "falls out of (his/her) canoe too")],
          "desc": "Two teens finally settle who is the faster paddler with a canoe race to the big rock and back."},
    175: {"desc": "A child buried a treasure shell and drew a map of it, and now has no idea where it is."},
    176: {"roles": {"subject": c.ages(6, 12), "friend": c.ages(6, 12), "grownup": c.ADULT},
          "cast": [(191, "An adult has just asked", "(grownup), an adult, has just asked"),
                   (194, "The adult nods seriously", "(grownup) nods seriously"),
                   (197, "The adult never finds out", "(grownup) never finds out")],
          "desc": "Two children have invented their own secret language, and an adult politely asks what one word means."},
    177: {"pron": {"a": {0: "subject", 3: "subject"}, "b": {2: "subject", 3: "subject"}},
          "desc": "A teen secretly loves an elder's very long stories, and today the other teens drift off and leave them there."},
    178: {"desc": "The children are building the tallest sandcastle in the history of Isola, and the tide is coming in."},
    179: {"roles": {"subject": c.ages(13, 13)},
          "desc": "A child who is nearly fourteen goes to bed early, sure they will wake up feeling completely different."},
    180: {"pron": {"b": {0: "friend"}},
          "desc": "A child has planted a seed and wants it to grow right now: explain that seeds take time, or plant something faster."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
