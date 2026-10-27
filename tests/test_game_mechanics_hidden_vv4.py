"""The Tree of Life's "Hidden keys, clicks and cheats" group (src/vv_game_mechanics_hidden_vv4.py): every entry and its
label pinned, every DEAD item pinned, every key the stock exe's input slots test and every tip in its string table
listed (tests/hidden_checks.py has the checks)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from hidden_checks import C, D, E, O, U, HiddenChecks  # noqa: E402,F401

import vv_game_mechanics_hidden_vv4 as hidden_vv4  # noqa: E402


class Hidden4(HiddenChecks, unittest.TestCase):
    MODULE = hidden_vv4
    GAME = 4
    TEXT_BOX = 0x40D750
    # (kind, name, label, the sub-lines' labels): C VERIFIED-C, E VERIFIED-E, O OWNER, U UNCONFIRMED, D DEAD.
    PINNED = (
        ('key', 'Which keys reach the game', C, ()),
        ('key', 'Space (village screen)', C, ()),
        ('key', '1 to 9 (village screen)', C, ()),
        ('key', 'C, D, M, P, T and Esc (village screen)', C, ()),
        ('key', "The developer's cheat: C then D (or F then D), then F6, F7 or F8 (village screen)", C, (O, O, O, U)),
        ('key', 'B (village screen)', U, ()),
        ('key', "W, ' ; [ and ] (village screen)", C, ()),
        ('key', 'F1 (help, splash, Puzzles and Milestones, Collections, the Mausoleum, Tech)', C, ()),
        ('key', 'F3 (Puzzles and Milestones)', C, (U,)),
        ('key', 'Esc (Collections, the Mausoleum, Tech, Puzzles, the Map, Villager Detail, Trophies, Adoption)', C, ()),
        ('key', 'Any typed character (the splash pictures)', C, ()),
        ('key', 'Enter and Esc (pop-up boxes)', C, ()),
        ('key', 'Typing in a name box', C, (D,)),
        ('key', 'Tab, the arrows, Page Up, Page Down, Home, End, Insert, Delete, F2, F4, F5, F9 and F10', C, ()),
        ('key', 'Event type 7 (village screen)', D, ()),
        ('key', 'Store screens: no redraw or reroll key', C, ()),
        ('code', 'Typed codes and name cheats', C, (U,)),
        ('click', 'The tip spot (village screen)', C, (U,)),
        ('click', 'The collection displays (village)', C, (U,)),
        ('click', 'Other places (village)', U, ()),
        ('tip', 'Where the tips appear', C, (U, C)),
        ('patcher', 'Difficulty (Options dialog)', C, ()),
        ('patcher', 'Upgrades buttons (Tech and Villager Detail screens)', C, (U,)),
        ('patcher', 'Story / Cheat menus (in the Origins Upgrades menu)', C, ()),
    )
    TIP_COUNTS = {
        'The 50 random tips (eRandomTip1 to 50)': {C: 50},
        'The 89 tip pop-ups (eTTip tutorial, eTip milestones)': {C: 54, U: 35},
    }
    DEAD = (
        'Event type 7 (village screen)',
        "the box's own ending on a typed Enter or",
    )
    PICKERS = ((0x43f180, 0x43f400, 50, 1025), (0x442650, 0x442900, 50, 1025))
    SPOT = (0x441450, 0x441680, 0x8c)


if __name__ == "__main__":
    unittest.main()
