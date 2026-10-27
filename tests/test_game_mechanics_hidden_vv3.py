"""The Secret City's "Hidden keys, clicks and cheats" group (src/vv_game_mechanics_hidden_vv3.py): every entry and its
label pinned, every DEAD item pinned, every key the stock exe's input slots test and every tip in its string table
listed (tests/hidden_checks.py has the checks)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from hidden_checks import C, D, E, O, U, HiddenChecks  # noqa: E402,F401

import vv_game_mechanics_hidden_vv3 as hidden_vv3  # noqa: E402


class Hidden3(HiddenChecks, unittest.TestCase):
    MODULE = hidden_vv3
    GAME = 3
    TEXT_BOX = 0x40D4A0
    # (kind, name, label, the sub-lines' labels): C VERIFIED-C, E VERIFIED-E, O OWNER, U UNCONFIRMED, D DEAD.
    PINNED = (
        ('key', 'Which keys reach the game', C, ()),
        ('key', 'Space (village screen)', C, ()),
        ('key', '1 to 9 (village screen)', C, ()),
        ('key', 'C, D, M, P, T and Esc (village screen)', C, ()),
        ('key', 'F then W (village screen)', U, (O,)),
        ('key', "' ; [ and ] (village screen)", C, ()),
        ('key', 'F1 (the help pictures, the splash, the three screens of the shared slot)', C, ()),
        ('key', "Esc (the shared slot's three screens, Map, Villager Detail)", C, (U,)),
        ('key', 'Any typed character (the splash pictures)', C, ()),
        ('key', 'Enter and Esc (pop-up boxes)', C, ()),
        ('key', 'Typing in a name box', C, (D,)),
        ('key', 'F3 and the keys not listed', C, ()),
        ('key', "The developer's three editors (behaviour scripts, the content map, waypoints)", D, ()),
        ('key', 'Event type 7 (village screen)', D, ()),
        ('code', 'Typed codes and name cheats', C, (U,)),
        ('click', 'The tip spot (village screen)', C, (U,)),
        ('click', 'Places that show their state (village)', C, (C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, C, U, U)),
        ('tip', 'Where the tips appear', C, (U,)),
        ('patcher', 'The second faction (Tech screen)', C, ()),
        ('patcher', 'Upgrades buttons (Tech and Villager Detail screens)', C, (U,)),
        ('patcher', 'Story / Cheat menus (in the Origins Upgrades menu)', C, ()),
    )
    TIP_COUNTS = {
        'The 50 random tips (eRandomTip1 to 50; the loading screen draws from the first 30, the tip spot from all)': {C: 50},
        'The 88 tip pop-ups (eTTip tutorial, eTip milestones)': {C: 52, U: 36},
    }
    DEAD = (
        "The developer's three editors (behaviour scripts, the content map, waypoints)",
        'Event type 7 (village screen)',
        "the box's own ending on a typed Enter or",
    )
    PICKERS = ((0x465e30, 0x466000, 30, 1050), (0x46a3d0, 0x46a630, 50, 1050))
    SPOT = (0x4676f0, 0x467900, 0x7c)


if __name__ == "__main__":
    unittest.main()
