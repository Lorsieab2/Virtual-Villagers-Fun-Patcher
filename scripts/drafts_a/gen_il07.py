"""Write the owner-approved draft "New Events - Inner Life Part VII" (events 121-140, friendship and small social
moments) as collection events, then format and check them (scripts/drafts_a/da_common.py has the shape and the
defaults; this table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no sensitivity edit.  130 "The Laugh That
Wasn't Welcome" names the act (an unthinking laugh), never shames the person, and neither choice forces forgiveness
(the draft's note).  Effect as the draft's bracket: 138 A small food.  No harm in any outcome.  "chief" does not
appear (140's "elders" are story elders).
Casting (the owner's naming rule, 2026-11-15): 121 the third villager, 123 the visitor, 126 the watching child,
136 the villager who squints, 140 the elder who sighs and the elder who laughs are cast villagers, named at the
first mention (later mentions by name); their pronouns follow them as the draft wrote them.
Grammar: 135 and 138 "(his/hers)" has no placeholder -> the noun it stands for.

    python scripts/drafts_a/gen_il07.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il07"
TABLE: dict[int, dict] = {
    121: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "third": c.ADULT},
          "cast": [(11, "a third villager sitting with them puts", "(third), a third villager sitting with them, puts"),
                   (14, "The third villager is not laughing", "(third) is not laughing")],
          "pron": {"a": "subject"},
          "desc": "Two friends collapse laughing at the words the coconut, and a third villager asks what it means."},
    122: {"desc": "A villager's one free afternoon meets a friend who needs help moving baskets: say no kindly, or offer one hour."},
    123: {"roles": {"subject": c.ADULT, "visitor": c.ADULT},
          "cast": [(35, "A visitor from another village walks", "(visitor), a visitor from another village, walks"),
                   (38, "The visitor laughs.", "(visitor) laughs."),
                   (41, "The visitor talks happily", "(visitor) talks happily"),
                   (41, "Just as the visitor leaves", "Just as (visitor) leaves"),
                   (41, "The visitor is already gone.", "(visitor) is already gone.")],
          "desc": "A visitor from another village hugs a villager like an old friend, and the villager has no idea who they are."},
    124: {"pron": {"setup": {0: "friend", 1: "subject"}, "a_label": {0: "friend"}},
          "desc": "A friend proudly gives a villager a lumpy carved bowl with a turtle on it that is not much like a turtle."},
    125: {"desc": "Two friends have said goodbye nine times and the sun is setting: really go this time, or sit back down."},
    126: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "child": c.CHILD},
          "cast": [(77, "A child who happens to be watching applauds",
                    "(child), a child who happens to be watching, applauds")],
          "desc": "Two villagers meet on a narrow path and keep stepping the same way: stand still, or make it a dance."},
    127: {"pron": {"b": {0: "friend"}},
          "desc": "A shy villager sits by the fire next to someone they hardly know, both trying to think of something to say."},
    128: {"pron": {"setup": {0: "friend", 1: "subject"}},
          "desc": "A friend is telling a villager a funny story that the villager already heard this morning."},
    129: {"pron": {"setup": "subject", "b": "subject"},
          "desc": "A friend has talked about almost nothing but knots for days: change the subject kindly, or ask a question."},
    130: {"pron": {"setup": {1: "subject"}, "a": {0: "subject"}, "b": {0: "subject", 3: "subject"}},
          "desc": "A villager laughs without thinking when a quiet friend says they would like to learn to drum."},
    131: {"desc": "Everybody has already seen the old heron come back, except one villager who rushes to share the news."},
    132: {"pron": {"setup": {0: "friend", 1: "friend"}},
          "desc": "A villager has planned a surprise meal for a friend, and on the morning of it the friend says they cannot wait."},
    133: {"desc": "A sudden shower sends two villagers who hardly know each other under the same big leaf."},
    134: {"pron": {"a_label": {0: "subject"}},
          "desc": "A villager wants to fix their own roof alone, and a very kind friend keeps coming over to help."},
    135: {"fixes": [(185, "moves (his/hers)", "moves (his/her) flower")],
          "desc": "A villager with a red flower behind one ear meets a friend wearing exactly the same flower."},
    136: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "doubter": c.ADULT},
          "cast": [(194, "One of them squints", "One of them, (doubter), squints"),
                   (194, "the same villager catches", "(doubter) catches")],
          "pron": {"setup": {0: "friend", 1: "friend"}, "a": {0: "friend"}},
          "desc": "A villager is trusted with a friend's secret, and a group by the well asks them about it."},
    137: {"pron": {"a": {1: "subject"}},
          "desc": "Two friends who used to meet every day now live on opposite sides of the village: walk over, or wave."},
    138: {"fixes": [(218, "drops all of (his/hers) too", "drops all of (his/her) coconuts too")],
          "desc": "Two villagers hold a contest to see who can carry more coconuts: add one more, or call it a draw."},
    139: {"pron": {"setup": {0: "friend", 1: "friend"}, "a_label": {0: "friend"}, "a": "friend",
                   "b": {1: "subject"}},
          "desc": "A villager's friend is good at everything, and today they discover the friend cannot whistle."},
    140: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "sigher": c.ELDER, "laugher": c.ELDER},
          "cast": [(242, "One elder sighs.", "One elder, (sigher), sighs."),
                   (242, "Another elder, to everyone's surprise,", "Another elder, (laugher), to everyone's surprise,")],
          "desc": "The elders are counting the harvest baskets very seriously, and two villagers catch the giggles."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
