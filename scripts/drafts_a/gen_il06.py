"""Write the owner-approved draft "New Events - Inner Life Part VI" (events 101-120, curiosity and wondering) as
collection events, then format and check them (scripts/drafts_a/da_common.py has the shape and the defaults; this
table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no sensitivity edit.  Science is offered as
wondering (118 keeps the moon and the breathing sea side by side, as the draft's notes say).  Effects as the draft's
brackets: 103 A small tech (where the game has tech points), 108 A small Farming or Research skill (the draft:
"Farming or Science"; Research is the game's science skill; only where the game has one).  No harm in any outcome.
109 and 119 are single popups.  116's dog and 111's hat are story only (kept as written).
Naming rule (2026-11-15): nobody cast; 116's "a child" is one of a chain of yawners (with "someone else"), 118's
"another villager" and "my teacher" are not in the scene.  109 "any villager" kept (the text does not say the
villager is alone at night): an owner question.
Grammar: 119 "(his/hers)" has no placeholder -> "(his/her) own".

    python scripts/drafts_a/gen_il06.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il06"
TABLE: dict[int, dict] = {
    101: {"desc": "A villager watching the waves wonders where each one starts: ask a friend, or follow one wave all the way in."},
    102: {"desc": "A villager lies awake wondering whether fish sleep, and goes down to the tide pools before dawn to find out."},
    103: {"desc": "A villager by the fire wonders why it crackles: test different kinds of wood, or just listen."},
    104: {"desc": "A child is deeply suspicious about a puddle that has vanished in the afternoon sun."},
    105: {"desc": "A villager holds a big curly shell to one ear, far from the beach, and hears the sea."},
    106: {"desc": "Lying on the beach at night, a villager notices that the stars have moved: stay up and watch, or tell a friend."},
    107: {"desc": "The sea is blue, but water scooped up in the hands is perfectly clear. A villager wants to know why."},
    108: {"fx": {"a": [c.sk("subject", ["Farming", "Research"])]},
          "desc": "A villager plants three seeds upside down to see whether a seed knows which way is up."},
    109: {"roles": {"subject": c.ages(6)},     # the lead (2026-11-15): wading at night, an older child at least
          "desc": "Walking on the shore late at night, a villager finds that the water lights up with soft blue sparks."},
    110: {"desc": "A teen argues all day about the biggest living thing on Isola: a whale, a tree, or the reef?"},
    111: {"desc": "A child asks where the wind lives: go looking for its home together, or ask the child what they think."},
    112: {"desc": "A villager lying under a tree wonders exactly how many leaves are on it: start counting, or estimate."},
    113: {"desc": "Once a villager notices one spiral, they see spirals everywhere: show a friend, or draw them all."},
    114: {"desc": "A rainbow seems to come down just past the gardens. A villager wonders what is at the end of it."},
    115: {"desc": "A villager counts the gap between the lightning and the thunder as a storm rolls around out at sea."},
    116: {"desc": "A yawn goes all the way round the fire at dinner, and a villager wants to know why yawns are catching."},
    117: {"desc": "The long-winged birds leave the cliffs again, and this year a villager wonders where they go."},
    118: {"desc": "A villager keeping track of the tide asks an elder why it comes a little later every day."},
    119: {"fixes": [(221, "(name1) tips (his/hers) too", "(name1) tips (his/her) own too")],
          "desc": "A seabird tips its head at a villager, and the villager wonders what they look like to a bird."},
    120: {"desc": "A child wants to know what is inside an ordinary round stone: crack it open, or keep the mystery."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
