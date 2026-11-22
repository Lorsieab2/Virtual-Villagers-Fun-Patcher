"""Write the owner-approved draft "New Events - Inner Life Part III" (events 41-60) as collection events, then format
and check them (scripts/drafts_a/da_common.py has the shape and the defaults; this table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no sensitivity edit.  Effects as the draft's
brackets: 47 A small Building skill ("small Building or craft skill"), 53 A (name1) now likes "fruit" (every game's
own word; the draft: "likes fruit").  49 and 56 are single popups.  Roles: 52 the child who overhears is cast as a
child of (name2) (the draft's note; PREFER drops the relation where the village has none), 54 (name2) "an actual
elder", 60 (name2) the teen's "older friend" (18+).  57's visitor is another Isolan village (the draft's note).
Casting edits (the owner's naming rule, 2026-11-15): 46 the six-year-old and the little one who trips (one role, age
6), 47 the carver, 52 the child of (name2), 57 the visitor; their pronouns follow them (no grammar fix).  Flag for the owner (left as written): 58 "From Tuesday?" names a
weekday.

    python scripts/drafts_a/gen_il03.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il03"
TABLE: dict[int, dict] = {
    41: {"desc": "A villager who always takes thirty-seven steps to the well counts thirty-nine today: walk it again, or let it be."},
    42: {"desc": "A shell collector finds a nearly perfect pink shell with one tiny chip: keep it anyway, or put it back."},
    43: {"desc": "A villager handing over a bowl of fruit is suddenly certain this exact moment has happened before."},
    44: {"pron": {"setup": "subject"},
         "desc": "An elder's story of getting lost as a child has grown with every telling: keep telling it, or tell the plain version."},
    45: {"pron": {"setup": "friend"},
         "desc": "A villager wonders what a quiet friend is thinking about all through the meal: ask, or let them be quiet."},
    46: {"roles": {"subject": c.YOUNG_ADULT, "little": c.ages(6, 6)},
         "cast": [(74, "loses spectacularly to a six-year-old,", "loses spectacularly to (little), a six-year-old,"),
                  (77, "When one of the little ones trips,", "When (little), one of the little ones, trips,"),
                  (77, "the child says", "(little) says")],
         "pron": {"a": {2: "subject"}, "b": {0: "little"}},
         "desc": "A young adult is invited to race the children along the beach: race anyway, or watch and cheer."},
    47: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "carver": c.ADULT},
         "cast": [(83, "Today a carver leaves", "Today (carver), a carver, leaves")],
         "fx": {"a": [c.sk("subject", "Building")]},
         "desc": "A villager who has never carved anything whittles a very good little turtle: show someone, or keep it a secret."},
    48: {"desc": "A villager sure that today would be terrible finds that nothing bad has happened by late afternoon."},
    49: {"desc": "A villager resting under a palm tree wonders what a coconut would think about, if it could think."},
    50: {"desc": "A villager is locked in a noisy argument with a rude bird on the roof: keep going, or make peace."},
    51: {"desc": "A villager walks to a favorite thinking rock at the end of the beach and finds someone already sitting on it."},
    52: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "child": c.related(c.CHILD, "child_of", "friend")},
         "cast": [(137, "It's (name2)'s child, who", "It's (child), (name2)'s child, who"),
                  (140, "The child hums", "(child) hums"), (140, "the child knows", "(child) knows"),
                  (140, "Then the child says", "Then (child) says"), (143, "The child giggles", "(child) giggles")],
         "desc": "A villager's private sunrise song is overheard by a child who could not sleep: sing it again, or keep it."},
    53: {"roles": {"subject": c.VILLAGER, "friend": c.ADULT},
         "fx": {"a": [{"do": "preference", "role": "subject", "list": "likes", "preference": "fruit"}]},
         "desc": "A villager who has always hated mangoes bites one and likes it, and someone saw: admit it, or deny everything."},
    54: {"roles": {"subject": c.ages(8, 12), "friend": c.ELDER},
         "desc": "A child who has decided to feel about forty starts sitting with the elders and nodding wisely."},
    55: {"desc": "A villager has written a letter to someone they have not spoken to in a long time: give it to them, or keep it."},
    56: {"desc": "A villager spends the afternoon by the shore turning over a question that will not quite fit into words."},
    57: {"roles": {"subject": c.ages(6), "visitor": c.VILLAGER},
         "cast": [(191, "Today, a visitor from another village notices",
                   "Today, (visitor), a visitor from another village, notices"),
                  (194, "The visitor nods", "(visitor) nods"), (197, "The visitor thinks", "(visitor) thinks")],
         "desc": "A visitor asks why a villager taps their bowl three times before every meal: make something up, or tell the truth."},
    58: {"desc": "A villager finally thinks of the perfect comeback, two days too late: use it anyway, or save it for next time."},
    59: {"desc": "The smell of rain on dry ground brings back an elder's memories of a hut that no longer stands."},
    60: {"pron": {"setup": {2: "subject"}},
         "desc": "A teen has decided to be mysterious this week, with a flower behind one ear and a thoughtful stare."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
