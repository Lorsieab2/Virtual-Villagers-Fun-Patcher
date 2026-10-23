"""Game Mechanics for The Tree of Life (VV4): read-only lines from one save (src/vv_game_mechanics.py).

Nothing is researched for this game yet: facts() returns no lines, and the section says so.  Each
mechanic added here reads the save (village.data) and the patcher's per-save files, never writes, and
returns vv_game_mechanics.Fact(group, text) lines in real time only (vv_game_mechanics.every / when /
duration), with the rule at the save's speed, techs and the patches in the game (village.has(id)).
"""
from __future__ import annotations

import vv_game_mechanics as gm

GAME = 4


def facts(village: gm.Village) -> list[gm.Fact]:
    return []