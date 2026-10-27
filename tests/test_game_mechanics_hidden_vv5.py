"""New Believers's "Hidden keys, clicks and cheats" group (src/vv_game_mechanics_hidden_vv5.py): every entry and its
label pinned, every DEAD item pinned, every key the stock exe's input slots test and every tip in its string table
listed (tests/hidden_checks.py has the checks)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from hidden_checks import C, D, E, O, U, HiddenChecks  # noqa: E402,F401

import vv_game_mechanics_hidden_vv5 as hidden_vv5  # noqa: E402


class Hidden5(HiddenChecks, unittest.TestCase):
    MODULE = hidden_vv5
    GAME = 5
    TEXT_BOX = 0x40DC40
    # (kind, name, label, the sub-lines' labels): C VERIFIED-C, E VERIFIED-E, O OWNER, U UNCONFIRMED, D DEAD.
    PINNED = (
        ('key', 'Which keys reach the game', C, ()),
        ('key', 'Space (village screen)', C, ()),
        ('key', '1 to 9 (village screen)', C, ()),
        ('key', 'C, D, M, P and T (village screen)', C, ()),
        ('key', 'Esc (village screen)', C, (U,)),
        ('key', 'F8 (village screen)', C, ()),
        ('key', 'C then D (village screen)', D, ()),
        ('key', "E, F, W, g, B, ' ; [ and ] (village screen)", C, ()),
        ('key', 'F1 (help, splash, Puzzles and Milestones, Collections, the Mausoleum, Tech)', C, ()),
        ('key', 'F3 (Puzzles and Milestones)', C, (U,)),
        ('key', 'Esc (Collections, the Mausoleum, Tech, Puzzles, the Map, Villager Detail, Trophies, Adoption)', C, ()),
        ('key', 'Any typed character (the splash pictures)', C, ()),
        ('key', 'Enter and Esc (pop-up boxes)', C, ()),
        ('key', 'Typing in a name box', C, (D,)),
        ('key', 'Tab, the arrows, Page Up, Page Down, Home, End, Insert, Delete, F2, F4 to F7, F9 and F10', C, ()),
        ('key', 'Event type 7 (village screen)', D, ()),
        ('code', 'Typed codes and name cheats', C, (U,)),
        ('click', 'No tip spot in the stock game', C, ()),
        ('click', 'Clicking villagers in the tutorial (village)', C, ()),
        ('click', 'Places that show their state (village)', U, ()),
        ('tip', 'Where the tips appear', C, (C, U, U)),
        ('patcher', 'The tip vine (village screen)', C, (U,)),
        ('patcher', 'Difficulty (Options dialog)', C, ()),
        ('patcher', 'Upgrades buttons (Tech and Villager Detail screens)', C, (U,)),
        ('patcher', 'Story / Cheat menus (in the Origins Upgrades menu)', C, ()),
    )
    TIP_COUNTS = {
        'The 50 random tips (eRandomTip1 to 50; the loading screen draws from the first 30)': {C: 30, U: 20},
        'The 98 tip pop-ups (eTTip tutorial, eTip milestones)': {C: 63, U: 35},
    }
    DEAD = (
        'C then D (village screen)',
        'Event type 7 (village screen)',
        "the box's own ending on a typed Enter or",
    )
    PICKERS = ((0x441d30, 0x441ed0, 30, 1121),)
    SPOT = None


if __name__ == "__main__":
    unittest.main()
