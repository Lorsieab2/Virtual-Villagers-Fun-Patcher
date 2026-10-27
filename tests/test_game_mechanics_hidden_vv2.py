"""The Lost Children's "Hidden keys, clicks and cheats" group (src/vv_game_mechanics_hidden_vv2.py): every entry and its
label pinned, every DEAD item pinned, every key the stock exe's input slots test and every tip in its string table
listed (tests/hidden_checks.py has the checks)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from hidden_checks import C, D, E, O, U, HiddenChecks  # noqa: E402,F401

import vv_game_mechanics_hidden_vv2 as hidden_vv2  # noqa: E402


class Hidden2(HiddenChecks, unittest.TestCase):
    MODULE = hidden_vv2
    GAME = 2
    TEXT_BOX = 0x40C810
    # (kind, name, label, the sub-lines' labels): C VERIFIED-C, E VERIFIED-E, O OWNER, U UNCONFIRMED, D DEAD.
    PINNED = (
        ('key', 'Which keys reach the game', C, ()),
        ('key', 'Space (village screen)', C, ()),
        ('key', '1 to 9 (village screen)', C, ()),
        ('key', 'C, D, M, P, T and Esc (village screen)', C, ()),
        ('key', 'F1 (Collections, the help pictures, the intro pages, Puzzles and Milestones, the splash, Tech)', C, ()),
        ('key', 'F3 (Collections, the help pictures, the intro page 0x429430, Puzzles and Milestones)', C, (U,)),
        ('key', 'Esc (Collections, Map, Puzzles and Milestones, Tech, Villager Detail)', C, ()),
        ('key', 'Any typed character (the splash pictures)', C, ()),
        ('key', 'Any typed character (the intro pages and the gamewin_bg.jpg screen)', C, (U,)),
        ('key', 'Enter and Esc (pop-up boxes)', C, ()),
        ('key', 'Typing in a name box', C, (D,)),
        ('key', 'Tab, the arrows, Page Up, Page Down, Home, End, Insert, Delete, F2, F4, F5 to F10', C, ()),
        ('key', 'Store screens: no redraw or reroll key', C, ()),
        ('code', 'Typed codes and name cheats', C, (U,)),
        ('click', 'The mask (village screen)', C, (C, U)),
        ('click', 'Places that show their state (village)', C, (C, C, C, C, C, C, C, C, C, C, C, C, U)),
        ('tip', 'Where the tips appear', C, (C, U)),
        ('patcher', 'Tip 786 (the mask)', C, (C,)),
        ('patcher', 'Upgrades buttons (Tech and Villager Detail screens)', C, (U,)),
        ('patcher', 'Story / Cheat menus (in the Origins Upgrades menu)', C, ()),
    )
    TIP_COUNTS = {
        'The 50 random tips (the loading screen draws from the first 30, the mask from all)': {C: 50},
        'The 89 tip pop-ups (tutorial and milestones)': {C: 66, U: 23},
    }
    DEAD = (
        "the box's own ending on a typed Enter or",
    )
    PICKERS = ((0x429530, 0x429c00, 30, 742), (0x4308d0, 0x431b10, 50, 742))
    SPOT = (0x42d2a0, 0x42d500, 0x218)


if __name__ == "__main__":
    unittest.main()
