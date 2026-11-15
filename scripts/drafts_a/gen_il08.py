"""Write the owner-approved draft "New Events - Inner Life Part VIII" (events 141-160, work, rest, boredom and pride
in small things) as collection events, then format and check them (scripts/drafts_a/da_common.py has the shape and
the defaults; this table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no sensitivity edit.  Looking back on a life
(154, 159, 160) asks for no verdict.  Effects as the draft's brackets: 149 A small tech (where the game has tech
points), 152 A (name1) celebrates.  No harm in any outcome (152's chicken is "fine but furious", story only).
Roles: 141 "a villager who is farming" -> Farming skill; 153 "a villager who is building" -> Building skill;
149 "a villager who is doing research" -> Research skill; its casting line says "VV2-VV5 or wherever the game has a
laboratory"; it stays in all five games (lead decision: narrative is not gameplay); 143 / 155 "or any adult" ->
any adult (the game records no job change or cook).
Casting (the owner's naming rule, 2026-11-15): 149 the villager who asks ("one of them") and the curious child,
159 B the child tying the knot are cast villagers named at the first mention.  Left uncast: 144's "somebody" /
"someone humming", 155's unknown "someone" (the text keeps them unknown), 159 A's child (a memory of the day).
Grammar: 154 "(his/hers)" has no placeholder -> "(his/her) own".

    python scripts/drafts_a/gen_il08.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il08"
TABLE: dict[int, dict] = {
    141: {"roles": {"subject": c.skilled(c.ADULT, "Farming"), "friend": c.ADULT},
          "desc": "A villager has planted the straightest row of seeds ever seen on Isola, and nobody is around to see it."},
    142: {"desc": "A villager resting in the shade leaps up to look busy, and so does the friend who comes along."},
    143: {"pron": {"setup": {3: "subject"}},
          "desc": "A villager who was a builder for years now helps in the gardens, and cannot stop measuring the bean poles."},
    144: {"desc": "Shelling nuts all morning, a villager starts making up a song: keep singing, or stop when someone looks."},
    145: {"pron": {"a": {1: "subject"}},
          "desc": "A villager's old digging stick, worn to the shape of their hands, snaps clean in two: mend it, or make a new one."},
    146: {"desc": "A job a villager has put off for weeks turns out to take about five minutes."},
    147: {"desc": "A villager finally fixes the creak in their hut that has been there for years."},
    148: {"pron": {"setup": {1: "subject"}, "a": {0: "subject"}},
          "desc": "A villager who sweeps the main path every morning before anyone is up is found at it by a friend."},
    149: {"roles": {"subject": c.skilled(c.ADULT, "Research"), "neighbor": c.ADULT, "child": c.CHILD},
          "cast": [(110, "One of them asks,", "One of them, (neighbor), asks,"),
                   (110, "A curious child stays to watch.", "(child), a curious child, stays to watch.")],
          "desc": "A villager's experiment fills the whole village with an enormous smell: own up, or quietly open the windows."},
    150: {"desc": "On a slow day, a villager sits on a rock and watches a snail cross the path."},
    151: {"desc": "A villager weaving and chatting forgot to stop, and the basket is now big enough to sleep in."},
    152: {"desc": "A villager has decided to learn to juggle with three coconuts: keep practicing, or switch to something softer."},
    153: {"roles": {"subject": c.skilled(c.ADULT, "Building")},
          "desc": "Nobody is racing, but a builder has privately decided to tie the frame of a wall faster than yesterday."},
    154: {"fixes": [(167, "This one is (his/hers), knots and all.", "This one is (his/her) own, knots and all.")],
          "desc": "Mending a fishing net, a villager wonders what life would be like if they had chosen different work."},
    155: {"desc": "A villager made the best stew of their life tonight, and nobody said a word about it."},
    156: {"pron": {"a": {0: "subject"}},
          "desc": "A villager has cut reeds all morning with the fish knife instead of the reed knife, and a friend just noticed."},
    157: {"pron": {"b_label": {0: "friend"}},
          "desc": "A villager has just stacked the perfect woodpile, and a friend pulls a piece out of the middle."},
    158: {"desc": "Pouring rain keeps a villager stuck in their hut with nothing left to do: visit a friend, or let the day be slow."},
    159: {"roles": {"subject": c.ADULT, "friend": c.ADULT, "pupil": c.CHILD},
          "cast": [(227, "finds a child proudly tying", "finds (pupil), a child, proudly tying")],
          "pron": {"setup": {1: "subject", 2: "subject"}, "b": "subject"},
          "desc": "At the end of the day, a villager feels they got nothing done at all, and a friend asks how the day was."},
    160: {"desc": "The work is finished, and a villager sits outside their hut at sunset thinking about the day."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
