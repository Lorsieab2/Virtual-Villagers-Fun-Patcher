"""A New Home's "Hidden keys, clicks and cheats" group (src/vv_game_mechanics_hidden_vv1.py): every entry and its
label pinned, every DEAD item pinned, every key the stock exe's input slots test and every tip in its string table
listed (tests/hidden_checks.py has the checks)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from hidden_checks import C, D, E, O, U, HiddenChecks  # noqa: E402,F401

import vv_game_mechanics_hidden_vv1 as hidden_vv1  # noqa: E402


class Hidden1(HiddenChecks, unittest.TestCase):
    MODULE = hidden_vv1
    GAME = 1
    TEXT_BOX = 0x40BE30
    # (kind, name, label, the sub-lines' labels): C VERIFIED-C, E VERIFIED-E, O OWNER, U UNCONFIRMED, D DEAD.
    PINNED = (
        ('key', 'Which keys reach the game', C, ()),
        ('key', 'Space (village screen)', C, ()),
        ('key', 'D, M, P, T and Esc (village screen)', C, ()),
        ('key', 'F7 and F8 (village screen)', C, ()),
        ('key', 'F1 (the splash, the help pictures, the Start / "?" screen, Puzzles and Milestones, Tech)', C, (O,)),
        ('key', 'F3 (the help pictures, the Start / "?" screen, Puzzles and Milestones)', C, (U,)),
        ('key', 'Esc (Map, Puzzles and Milestones, Tech, Villager Detail)', C, ()),
        ('key', 'Enter and Esc (pop-up boxes)', C, ()),
        ('key', 'Typing in a name box', C, (D,)),
        ('key', 'Tab, the arrows, Page Up, Page Down, Home, End, Insert, Delete, F2, F4, F5, F6, F9 and F10', C, ()),
        ('key', 'Store screens: no redraw or reroll key', C, ()),
        ('code', 'Typed codes and name cheats', C, (U,)),
        ('click', 'The mask (village screen)', C, (U, C, C)),
        ('click', 'The school drum (village)', C, ()),
        ('click', 'Places that show their state (village)', C, (C, C, C, C, C, C, C, C, U)),
        ('click', 'The grid at the map spot 1,233 to 1,533 across and 200 to 350 down (village)', U, ()),
        ('tip', 'Where the tips appear', C, (U, C)),
        ('patcher', 'Number keys 1 to 9 (village screen)', C, (C,)),
        ('patcher', 'F6 (village screen)', C, ()),
        ('patcher', 'Sort By (Villager Detail screen)', C, ()),
        ('patcher', 'Upgrades buttons (Tech and Villager Detail screens)', C, (E,)),
        ('patcher', 'Story / Cheat menus (in the Origins Upgrades menu)', C, ()),
    )
    TIP_COUNTS = {
        'The 30 random tips (the mask)': {C: 30},
        'The 70 tip pop-ups (tutorial and milestones)': {C: 60, U: 10},
    }
    DEAD = (
        "the box's own ending on a typed Enter or",
    )
    PICKERS = ((0x424ef0, 0x425c00, 30, 519),)
    SPOT = (0x4224a0, 0x422700, 0x2c8)


if __name__ == "__main__":
    unittest.main()
