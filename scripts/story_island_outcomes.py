"""Pick Island Event: the settings each offered event can carry, per game.

The owner: "In general I want all possible outcomes for events that have them
to be possible."  Every setting was traced in that game's own executable; the
per-game tables (scripts/story_outcomes_vv1.py ... _vv5.py) cite the code for
each one in its "evidence".  This module gathers them for the generator
(scripts/build_story_cheat_upgrades_features.py) and the tests.

A control is one row of the Pick Island Event dialog's settings:

* "enum": one of the event's own results (each option forces one or more of
  the game's own rolls);
* "amount": the value of one amount roll -- every value the game can roll;
* "loop": a roll the game makes for each villager in turn -- nobody,
  everyone, or the villagers the player chooses;
* "victim": which villager the event is about, when the game picks one with
  a roll among candidates.

Each roll is a SITE: the VA of a `call rand` (E8 rel32) in the game.
"branch" is the choice of a two-choice event the control belongs to (0 = the
first button, 1 = the second); "phase" is where the roll runs ("select":
before the event is shown, "build": the popup, "apply": the OK);
"scope_call" (and "scope_call_alt") is the call in the event's own code that a
shared routine's roll is answered under (story_outcomes.inc).
"""
from __future__ import annotations

import re

import story_outcomes_vv1
import story_outcomes_vv2
import story_outcomes_vv3
import story_outcomes_vv4
import story_outcomes_vv5
import story_outcomes_gong

_MODULES = {
    "vv1": story_outcomes_vv1, "vv2": story_outcomes_vv2, "vv3": story_outcomes_vv3,
    "vv4": story_outcomes_vv4, "vv5": story_outcomes_vv5,
}

# Conditions an option can need, checked when the dialog opens and again when
# the pick is bought (story_outcomes_ui.inc oc_condition_holds).
CONDITION_IDS = {None: 0, "room": 1, "vv2_gong_tiers": 2, "vv2_breeding_mastered": 3}

# Options whose condition is checked (game, slot, control id, option label
# prefix) -> condition.  Every other condition in the tables depends on the
# villager the game picks or on an earlier roll, and is stated in the label.
_OPTION_CONDITIONS = {
    ("vv1", 67, "result", "A lost stranger joins"): "room",
    ("vv3", 39, "result", "Two copies of the villager appear"): "room",
}


def _normalise(game: str, slot: int, c: dict) -> dict:
    c = dict(c)
    # A loop whose villager can not be told from the registers offers only
    # nobody / everyone (A New Home's Heat Wave: the swimmers).
    c.pop("record_index", None)
    if c["kind"] == "enum":
        options = []
        notes = []
        for o in c["options"]:
            o = dict(o)
            cond = o.get("cond")
            for (g, s, cid, prefix), name in _OPTION_CONDITIONS.items():
                if (g, s, cid) == (game, slot, c["id"]) and o["label"].startswith(prefix):
                    cond = name
            if cond is not None:
                o["cond"] = cond
            elif o.get("condition") and o["condition"] not in notes:
                notes.append(o["condition"])
            options.append(o)
        c["options"] = options
        if notes and not c.get("note"):
            c["note"] = "Only " + "; ".join(notes) if len(notes) == 1 else "; ".join(notes)
    return c


# The calls that create each new villager of a barrel, a crate or a couple
# belong to the Origins rows (they patch them to count the births), so the
# rolls inside the shared creator are told apart by their order in the
# event's apply instead: the n-th baby is the n-th call of the creator's roll.
# Each event's per-baby settings are therefore one per baby, whatever the
# strength or contents level that decides how many babies come.
CREATOR_CALLS = {
    "vv1": {0x428263, 0x4282C6, 0x4282E3, 0x42833C, 0x428359, 0x428376,
            0x42C3EF, 0x42C410, 0x42C431, 0x42C4AF, 0x42C4D0, 0x42C54E},
    "vv2": {0x434102, 0x4341A2, 0x4341C3, 0x434262, 0x434283, 0x4342A4, 0x434467, 0x4344A3},
}
_BABY_ID = {
    "vv1": re.compile(r"^[sl]\d_baby(\d)_(.+)$"),
    "vv2": re.compile(r"^t\d(\d)_(.+)$"),
}
_BABY_LABEL = {
    12: "Baby {k}: {field}",
    132: "If you open it, infant {k}: {field}",
    21: "Toddler {k}: {field}",
}
_FIELD_NAMES = {"age": "age", "sex": "boy or girl", "head": "head", "body": "body",
                "research_bonus": "research bonus", "building_bonus": "building bonus",
                "healing_bonus": "healing bonus", "farming_bonus": "farming bonus"}


def _regroup_babies(game: str, slot: int, controls: list[dict]) -> list[dict]:
    """One control per baby and field: the brackets' own sites (ages) become
    one control's sites; the creator's rolls become that baby's call."""
    pattern = _BABY_ID.get(game)
    if pattern is None or slot not in _BABY_LABEL:
        return controls
    out: list[dict] = []
    merged: dict[tuple[int, str], dict] = {}
    for c in controls:
        m = pattern.match(c["id"])
        if not m:
            out.append(c)
            continue
        k, field = int(m.group(1)), m.group(2)
        key = (k, field)
        inside_creator = c.get("scope_call") in CREATOR_CALLS[game]
        if key not in merged:
            new = dict(c)
            new["id"] = f"baby{k}_{field}"
            new["label"] = _BABY_LABEL[slot].format(k=k, field=_FIELD_NAMES.get(field, field))
            new["note"] = (f"Only if at least {k} {'baby comes' if k == 1 else 'babies come'} "
                           "(the game's own count).")
            new.pop("condition", None)
            if inside_creator:
                new["scope_call"] = None
                new["occurrence"] = k
                new["evidence"] = (c["evidence"] + f" Told apart as the {k}th call of the roll in "
                                   "the event's apply (the creator calls are the Origins rows').")
            elif c["kind"] != "enum":
                new["sites"] = [c["site"]]
            merged[key] = new
            out.append(new)
        else:
            have = merged[key]
            if inside_creator:
                if c["kind"] == "enum":
                    assert [o["force"] for o in c["options"]] == [o["force"] for o in have["options"]], c["id"]
                else:
                    assert c["site"] == have["site"] and c["bound"] == have["bound"], c["id"]
            else:
                assert c["kind"] == "amount" and c["bound"] == have["bound"] \
                    and c["base"] == have["base"], c["id"]
                have["sites"].append(c["site"])
    for c in out:
        if c["kind"] == "enum" and c.get("scope_call") in CREATOR_CALLS[game]:
            raise AssertionError(c["id"])
    return out


# The Lost Children's Old Friends: the man is the creator's first call, the
# woman its second.
def _old_friends(controls: list[dict]) -> list[dict]:
    out = []
    for c in controls:
        c = dict(c)
        if c.get("scope_call") in CREATOR_CALLS["vv2"]:
            c["occurrence"] = 1 if c["id"].startswith("man_") else 2
            c["scope_call"] = None
        out.append(c)
    return out


def _controls(game: str, slot: int, cs: list[dict]) -> list[dict]:
    cs = [_normalise(game, slot, c) for c in cs]
    cs = _regroup_babies(game, slot, cs)
    if (game, slot) == ("vv2", 25):
        cs = _old_friends(cs)
    for c in cs:
        if c.get("scope_call") in CREATOR_CALLS.get(game, ()):
            raise AssertionError(f"{game} {slot} {c['id']}: scoped by an Origins-owned call")
    return cs


CONTROLS: dict[str, dict[int, list[dict]]] = {
    game: {slot: _controls(game, slot, cs) for slot, cs in m.CONTROLS.items()}
    for game, m in _MODULES.items()
}
OMITTED = {game: m.OMITTED for game, m in _MODULES.items()}
COSMETIC = {game: m.COSMETIC for game, m in _MODULES.items()}
NO_OUTCOME = {game: m.NO_OUTCOME for game, m in _MODULES.items()}

# A New Home / The Lost Children: the calls that run a delivered event's
# resolve after the player's OK: (call VA, stack argument holding the
# clicked choice (-1 none, -2 a dword of the object in ECX), value added to
# it to give 0 / 1, that dword's offset, stack argument holding the strength
# (magnitude) the body receives or -1).
APPLY_SCOPES: dict[str, list[tuple[int, int, int, int, int]]] = {
    # 0x41A444 encounter resolve 0x418A80, 0x42D0C4 crate / vial resolve
    # 0x42B740: [this+0x509C] = 1 (first button) / 2, stored just before.
    # The single-result island events run inside the island chooser call
    # 0x428777 (story_c1.inc c1_choose opens and closes them).
    "vv1": [(0x41A444, -2, -1, 0x509C, -1), (0x42D0C4, -2, -1, 0x509C, -1)],
    # 0x422364 family A resolve 0x4204B0 ([this+0x50A4] = 1 / 2); 0x439DB4
    # sack / vial resolve 0x438160 ([this+0x509C] = 1 / 2); 0x43483D family C
    # body 0x433600 (case, magnitude) after the case roll.
    "vv2": [(0x422364, -2, -1, 0x50A4, -1), (0x439DB4, -2, -1, 0x509C, -1),
            (0x43483D, -1, 0, 0, 1)],
}

# A New Home / The Lost Children island events whose strength (magnitude,
# normally clamp(population / 3, 1, 10)) the player can set: slot ->
# "linear" (every value 1-10 differs) or "barrel" (1-4 / 5-7 / 8-10: one,
# two or three babies).  Events that ignore the magnitude get no setting.
STRENGTH: dict[str, dict[int, str]] = {
    "vv1": {0: "linear", 2: "linear", 5: "linear", 10: "linear", 11: "linear", 12: "barrel",
            13: "linear", 14: "linear"},
    "vv2": {5: "linear", 21: "barrel", 22: "linear"},
}

# The Lost Children's Gong of Wonder: the call that runs one use, and its
# settings (scripts/story_outcomes_gong.py).
GONG_USE_CALLS: dict[str, list[int]] = {"vv2": list(story_outcomes_gong.USE_CALLS)}
GONG_CONTROLS: dict[str, list[dict]] = {
    "vv2": [_normalise("vv2", 1000, c) for c in story_outcomes_gong.CONTROLS]}

# Events whose own condition a pick may pass because it is a timing or story
# condition the event's code does not need -- each proven by running the
# event's own popup and apply in emulation with the condition false (the
# state absent): complete, no invalid access, a coherent result.  "needs":
# what the event's own condition method must still have picked (The Secret
# City, The Tree of Life, New Believers: object fields +0x4 the villager the
# event is about, +0xC a second villager), else it stays locked.  Conditions
# the code does need (a villager of some kind, crops, room for new villagers
# -- room is never overridden) keep the event locked, with its reason.
# A New Home / The Lost Children pass the check right after the event roll,
# once (story_vv1.inc / story_vv2.inc).
UNLOCKED: dict[str, dict[int, dict]] = {
    "vv1": {
        9: {"why": "the beach not yet cleaned up: the wave resets the cleaning done so far"},
        (1 << 6) | 9: {"why": "no child: the game already lets any villager meet the monkey"},
        1: {"why": "developer-dead (never runs in the original game)"},
        (1 << 6) | 5: {"why": "developer-dead (never runs in the original game)"},
    },
    "vv2": {
        8: {"why": "nobody has died yet: the honoring never reads the graves"},
        11: {"why": "the village's later progress not reached"},
        14: {"why": "the village's later progress not reached"},
        17: {"why": "the village's later progress not reached"},
        (1 << 6) | 14: {"why": "a lone villager: the copy still needs room in the village"},
        18: {"why": "developer-dead (never runs in the original game)"},
        20: {"why": "developer-dead (never runs in the original game)"},
        26: {"why": "developer-dead (never runs in the original game)"},
    },
    "vv3": {
        1: {"needs": []}, 3: {"needs": []}, 6: {"needs": []}, 13: {"needs": []},
        15: {"needs": [4]}, 16: {"needs": [4]}, 17: {"needs": [4]}, 19: {"needs": [4]},
        20: {"needs": [4]}, 21: {"needs": [4]}, 22: {"needs": [4]}, 23: {"needs": [4]},
        26: {"needs": [4]}, 36: {"needs": [4, 0xC]}, 41: {"needs": [4]}, 44: {"needs": [4]},
        49: {"needs": []}, 54: {"needs": []},
    },
    "vv4": {
        5: {"needs": []}, 22: {"needs": []}, 25: {"needs": ["room"]}, 26: {"needs": []},
        27: {"needs": []}, 28: {"needs": [4, "room"]}, 32: {"needs": [4]}, 46: {"needs": [4]},
        48: {"needs": [4]},
        6: {"needs": ["room"]},                     # developer-dead, works
    },
    "vv5": {
        4: {"needs": []}, 21: {"needs": []}, 23: {"needs": []}, 40: {"needs": [4]}, 42: {"needs": [4]},
        25: {"needs": []}, 33: {"needs": ["room"]},  # developer-dead, work
    },
}
DEAD_NOTES: dict[str, dict[int, str]] = {
    "vv1": {1: "Never happens in the original game (its condition always fails); its code and "
               "text are complete and it works.",
            (1 << 6) | 5: "Never happens in the original game (its condition always fails); its "
                          "code and text are complete and it works."},
    "vv2": {s: "Never happens in the original game (its condition always fails); its code and "
               "text are complete and it works." for s in (18, 20, 26)},
    "vv4": {6: "Never happens in the original game (its condition always fails); its code and text "
               "are complete and it works. It needs room in the village for the new villager."},
    "vv5": {25: "Never happens in the original game (its condition always fails); its code and text "
                "are complete and it works.",
            33: "Never happens in the original game (its condition always fails); its code and text "
                "are complete and it works. It needs room in the village for the babies."},
}
