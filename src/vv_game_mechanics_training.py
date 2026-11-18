"""Game Mechanics: "Jobs and training" -- the job picker's skill rule (all five games) and The Tree of Life's and New
Believers' hidden "untrained" mark (the owner, 2026-11-18).

THE PICKER'S RULE (stock exes, research/stock-executables; tests/test_game_mechanics_training.py pins the bytes):
  the preferred job (the Details screen's tick) replaces the game's pick when rand(100) <= 85 (cmp eax,0x55; jg skip):
  VV1 0x439C40 (preference [rec+0x3D0]), VV2 0x449DCD (+0x7F8), VV3 0x45985B (+0xEC0), VV4 0x461E4A (+0x1C70), VV5
  0x46A575 (+0x1C74).  Then the score must be above the floor (VV1 0x439C80 cmp esi,1; VV2 0x449E0F, VV3 0x45986D,
  VV4 0x461E69, VV5 0x46A594 cmp esi,5) and rand(100) < score + 40 (add esi,0x28; cmp eax,esi).
  docs/hidden-gates-all-five-games.md has the rest of each chooser.

THE UNTRAINED MARK: record +0x1C54 (the task the player gave), 1 = untrained.  In the save it is the villager
entry (vv_last_names._entries) + 0xB8 -- the same saved block as the pregnancy (+0xB0) and litter (+0xB4);
the fixture saves hold 0, 1 and task numbers there.
  * Set to 1 only by the villager set-up, last thing: VV4 0x45EF10 at 0x45F534 (from the makers 0x466270 /
    0x466370), VV5 0x4681F0 at 0x4687D3 (from 0x46FAD0, 0x46FB80, 0x46FDE0).  No other write of 1 (an IDA scan of
    every [reg+0x1C54] operand).
  * Read: the work dispatcher refuses every job while it is 1 (VV4 0x4639B0 at 0x4639D2, VV5 0x46C540 at
    0x46C565: cmp [rec+0x1C54], 1 -> return 0), Parenting (job 1: the partner search and embrace) included; the
    scheduler (VV4 0x465840 at 0x46597F, VV5 0x46F070 at 0x46F240) and the catch-up worker (VV4 0x465750 at
    0x4657C9, VV5 0x46E8E0 at 0x46E96B) only continue a given task when it is 2 or more, else they ask the
    dispatcher; the "keep it unless 1" resets (VV4 0x45E6A0; VV5 0x452D10, 0x455230, 0x465CF0) keep it.  The
    catch-up worker's Parenting pick (VV4 0x465750: rand(100) <= 5 -> 0x469720; VV5 0x46E8E0 -> 0x474CE0) comes
    before the mark is read.
  * Cleared: a drop that gives the villager work writes its task over it (VV4 e.g. 0x46F8DC 3, 0x440CEC 9;
    VV5 0x47A4F3 3, 0x443DE8 9 ...), and the task's own end writes 0 (VV4 0x4634D0, VV5 0x46BCF0 when the skill is
    below 6, and the work objects' handlers VV4 0x430210 / VV5 0x434D20).
  * New Believers' tip 701 (eTTipInstruct39): "A villager will not seek a mate on their own unless they are trained
    and Parenting is set as their preferred skill."
  * Villagers Work Their Own Job First (native/vvfp_work_first, PR #807): untrained_dispatch lifts the mark for one
    dispatch of the villager's selected job (never Parenting) and puts it back; the beginners' gate (VV4 0x461E69,
    VV5 0x46A594) lets the selected job through to the rand(100) < skill + 40 roll.
Nothing here writes anything.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm

GROUP = "Jobs and training"
C = gm.CODE
FLOOR = {1: 1, 2: 5, 3: 5, 4: 5, 5: 5}
MARK = 0xB8                                 # the task field in the saved villager entry (record +0x1C54)
UNTRAINED = 1
WORK_FIRST = "vv{}_work_first"
WORK_FIRST_NAME = "Villagers Work Their Own Job First"


def rule_lines(game: int) -> list[tuple[str, bool | str, bool]]:
    floor = FLOOR[game]
    out = [
        ("How a villager picks a job on their own (each time the game chooses what an idle villager does):", C, False),
        ("The preferred job (the one ticked on the Villager Details screen) replaces the game's own pick 86 times in "
         "100.", C, True),
        (f"The villager then goes only if that job's skill is above {floor}"
         + (" (A New Home's floor; the other four games use above 5)" if game == 1 else "")
         + ", and then (skill + 40) times in 100: skill 20 goes 60 times in 100, skill 60 or more always. "
         f"A villager whose skills are all {floor} or lower never picks a job on their own.", C, True),
    ]
    return out


def mark_lines(village: gm.Village) -> list[tuple[str, bool | str, bool]]:
    game = village.game
    if game not in (4, 5):
        return []
    out = [
        ("The hidden \"untrained\" mark: every new villager starts untrained -- born, arriving, or in a new "
         "village. While the mark is set the game starts no job for them at all, whatever their skill and whatever "
         "their preferred job, Parenting included, so they never go to work or seek a mate on their own.", C, False),
    ]
    if game == 5:
        out.append(("The game's own tip says so: \"A villager will not seek a mate on their own unless they are trained "
                    "and Parenting is set as their preferred skill.\"", C, True))
    out += [
        ("How it is cleared: drop the villager once where the drop gives them work (a job spot, a food source, a "
         "building site, another villager to embrace). That task replaces the mark, and when the task ends the "
         "villager is trained for good. Nothing else in the game sets the mark again.", C, True),
        ("While the game is closed (catch-up), the 6-in-100 mating try of a villager whose pick is Parenting comes "
         "before the mark is looked at, so an untrained villager can conceive in time away.", C, True),
        ("The mark is kept in the save, so an untrained villager is still untrained after loading.", gm.SAVE, True),
    ]
    has = village.has(WORK_FIRST.format(game))
    if has is not False:
        where = "" if has else " (whether the game has it could not be told)"
        out.append((f"With the patcher's \"{WORK_FIRST_NAME}\"{where}: the mark no longer blocks the villager's "
                    "preferred job (never Parenting): when the patch puts that job first, the game is asked for it "
                    "with the mark lifted for that one request. Every other job stays blocked until a drop clears "
                    "the mark. The preferred job also gets past the skill-5 floor to the (skill + 40) roll.", C, True))
    return out


def status_lines(village: gm.Village) -> list[gm.Fact]:
    """Each villager's trained / untrained state from the save (The Tree of Life, New Believers' believers)."""
    if village.game not in (4, 5) or village.general:
        return []
    try:
        import vv_last_names as ln
        entries = ln._entries(village.game, village.data)
    except Exception:  # noqa: BLE001 -- an unreadable table gives one line saying so
        return [gm.Fact(GROUP, "Untrained now: the villager table could not be read.", gm.SAVE)]
    names, total = [], 0
    for at in entries:
        if village.game == 5 and village.data[at - 0x1F] != 0:      # a Heathen (vv_game_mechanics_life.VV5_FACTION)
            continue
        total += 1
        if struct.unpack_from("<i", village.data, at + MARK)[0] == UNTRAINED:
            names.append(ln._cstr(village.data, at, 0x18))
    who = "believers" if village.game == 5 else "villagers"
    if not names:
        return [gm.Fact(GROUP, f"Untrained now: none of the {total} {who}; every one is trained.", gm.SAVE)]
    return [gm.Fact(GROUP, f"Untrained now: {len(names)} of the {total} {who}: {', '.join(names)}.", gm.SAVE)]


def facts(village: gm.Village) -> list[gm.Fact]:
    out = [gm.Fact(GROUP, text, ok, sub) for text, ok, sub in rule_lines(village.game) + mark_lines(village)]
    return out + status_lines(village)
