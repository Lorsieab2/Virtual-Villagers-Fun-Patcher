"""Write the owner-approved draft "New Events - Inner Life" (events 1-10) as collection events, then format and check
them (scripts/drafts_a/da_common.py has the shape and the defaults; this table is the authoring record).

Review (the rulebook's 15 checks, 2026-11-15): no hard-rule break, no edit.  Effects as the draft's brackets: 1 A
the child celebrates, 2 B small food, 7 A small Healing.  3 "The Quiet Hands": (name1) is mute in the story only
(the draft's note); TODO for the engine: a story trait "mute" (pending engine).

    python scripts/drafts_a/gen_il01.py [--review <folder>]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import da_common as c  # noqa: E402

SOURCE = "da_il01"
TABLE: dict[int, dict] = {
    1: {"pron": {"a": {0: "friend"}},
        "desc": "A child's invisible best friend, Mister Pebbles, comes to dinner: play along, ask about him, or let it be."},
    2: {"desc": "A villager chats away to the fish while fishing alone: join the conversation, or leave them to it."},
    3: {"roles": {"subject": c.ADULT, "friend": c.VILLAGER},
        "note": "TODO story trait mute: pending engine (the draft: in the story (name1) is mute; nothing about the "
                "villager changes in the game)",
        "desc": "A villager who does not speak meets a new apprentice who talks to them slowly and loudly."},
    4: {"desc": "A villager has an idea for the harvest feast but hesitates: say it anyway, or keep it to themselves."},
    5: {"roles": {"subject": c.VILLAGER, "friend": c.VILLAGER}, "pron": {"a": "subject"},
        "desc": "A villager sorting seeds drifts off into a daydream: snap back to work, or keep dreaming a little longer."},
    6: {"roles": {"subject": c.VILLAGER, "friend": c.VILLAGER}, "pron": {"setup": "subject", "a": "subject"},
        "desc": "A villager rehearses an apology for a broken bowl, and its owner is standing right behind them."},
    7: {"roles": {"subject": c.ages(14, 25), "friend": c.skilled(c.ELDER, "Healing")},
        "fx": {"a": [c.sk("subject", "Healing")]},
        "desc": "A young villager who wants to be a healer cannot sleep, and finds an old healer by the fire."},
    8: {"desc": "A villager has been worried for days and keeps turning a smooth stone: offer to listen, or find a match."},
    9: {"desc": "A villager lies awake thinking about everything at once, until the frogs start singing."},
    10: {"desc": "A child building a tall tower of shells hears a little voice that says it will fall."},
}

if __name__ == "__main__":
    sys.exit(c.main(SOURCE, TABLE))
