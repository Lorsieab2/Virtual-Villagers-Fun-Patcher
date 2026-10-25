"""Game Mechanics for New Believers (VV5): the "Faith and Heathens" group.

Read from the stock exe's own reachable code (SHA-256 92946781...C65D), at the addresses cited:
  * Faith is the villager's +0x1CF0 (the save's entry -0x18 from the name); its setter 0x467F90 clamps it to -100..100,
    turns a believer at 0 or less into a Heathen (0x4669E0) and a Heathen above 0 into a believer (0x4668B0), raising a
    convert below 5 to 55 -- only while the island runs (manager +0x17E39, set as the main scene starts, 0x442206), so
    loading a save never converts anyone;
  * the drift 0x468040, run once per age unit for each believer by the life tick 0x472C90 (0x472D17), which skips
    Heathens (0x472CB7);
  * the starting Faith rand(30) + 30 of every new villager (0x468508, in the villager set-up 0x4681F0 every birth and
    newcomer goes through); a twin or triplet copies the first baby's (0x4688C8);
  * the other writers: preaching 0x468F2F, Spreading the Word 0x46D2C3, the Earthquake 0x41F79F, the Heathen
    Doctor's cure 0x468CFB / 0x46D43C, The Heathen Chief 0x4360EE, the Hydroponic Farm 0x439E35, the Heathen Mommy's
    puzzle 0x43979C, and the island events (their own group).
The game's random numbers: rand(n) 0x403660 is the C library's rand() % n, so "rand(100) < 30" comes 9,840 times in
32,768 (30.03%), not exactly 30%.  Read only: nothing here writes anything.
"""
from __future__ import annotations

import vv_game_mechanics as gm

FAITH = "Faith and Heathens"
HEATHEN_MOMMY = "vv5_heathen_mommy_puzzle"
DRAWS = 32768


def below(n: int, k: int) -> int:
    return sum(1 for v in range(DRAWS) if v % n < k)


def pct(count: int) -> str:
    return f"{100 * count / DRAWS:.2f}%"


def _p(k: int) -> str:
    """The exact chance of rand(100) < k."""
    return pct(below(100, k))


def lines(village: gm.Village) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    add = lambda text, ok=gm.RUNNING, sub=False: out.append(gm.Fact(FAITH, text, ok, sub))  # noqa: E731
    starving = 1 - (1 - below(100, 30) / DRAWS) * (1 - below(100, 10) / DRAWS)
    add("Faith runs from -100 to 100 (0x467FE4). A believer whose Faith falls to 0 or less becomes a Heathen at once "
        "(\"A villager has stopped believing in you!\", 0x4669E0); a Heathen whose Faith rises above 0 joins the tribe "
        "(\"There is a new believer!\", 0x4668B0), and a convert left below 5 is set to 55 (0x467FC7). This happens "
        "only while the island runs: loading a save never converts anyone (0x467F99).")
    add("Every villager the game makes (each baby, each newcomer) starts at Faith 30 to 59, each value equally likely "
        "(rand(30) + 30, 0x468508); a twin or triplet gets the same Faith as the first baby (0x4688C8).", sub=True)
    add("Each age unit (3, 6 or 10 real-life minutes on Fast, Normal or Slow), every believer's Faith moves by the sum "
        "of these rolls (0x468040); Heathens get none of them, while catching up or otherwise (0x472CB7):")
    for text in (
            f"Food in storage under 10: -1 {pct(round(starving * DRAWS))} of the time ({_p(30)}, or else {_p(10)}); 10 "
            f"to 250: -1 {_p(10)}; 8,000 or more: +1 {_p(20)}; anything between: nothing.",
            # Not "A believer who is sick: -1 ...": the general page drops a line shaped "<Name>: <number>" as a
            # save's amount (vv_game_mechanics.general).
            f"A sick believer loses 1 more {_p(15)} of the time.",
            f"The Tribute Statue solved: +1 {_p(30)}; before that, at the statue's first stage +1 {_p(10)}, at its "
            f"second +1 {_p(20)}.",
            f"Spirituality level 1, 2 or 3: +1 {_p(10)}, {_p(20)} or {_p(30)}.",
            # The count is 0x4713F0's: living believers plus the babies they carry (0x46815E).
            f"Fewer than 12 believers (the babies they carry counted): -1 with a chance of (12 - believers) in 100 "
            f"(11 believers {_p(1)}, 1 believer "
            f"{_p(11)}); 12 or more: +1 with a chance of (believers / 5, rounded down) in 100 (12 to 14: {_p(2)}; 50: "
            f"{_p(10)}; 150: {_p(30)}).",
            f"Then, when the sum is a fall and Faith is below 5, the fall is skipped {_p(50)} of the time; when it is a "
            f"rise and Faith is above 75, the rise is skipped {_p(70)} of the time (0x4681A7). Each roll's exact odds "
            "are a hair above the round percentage, as the game's random numbers fall."):
        add(text, sub=True)
    add("Other things that change Faith, exactly:")
    for text in (
            "Preaching to a Heathen (after the preacher's Devotion check): +3, +4 at Devotion 50 or more, +5 at 88 or "
            "more; that Heathen then cannot be preached to for 2 real-life hours, paused or closed (0x468F2A). The "
            "Heathen Doctor, the Chief, the three Masters and the Mommy cannot be preached to.",
            "Spreading the Word (the Retired Chief's): +30 to one villager picked at random among those listening to "
            "the sermon (behaviour 0xE4), who then cannot be preached to for 2 real-life hours either (0x46D2A8, "
            "0x46D2D8).",
            "The Earthquake God Power: +2 to +8 to every villager but the six special roles (see God powers).",
            "Curing the Heathen Doctor: Faith set to 25 to 59, each equally likely (0x468CFB). Solving The Heathen "
            "Chief: the Chief's Faith set to 100 (0x4360EE). Solving the Hydroponic Farm: the Heathen Master Farmer "
            "+80 (0x439E35).",
            "Island events: their own amounts (see Island events)."):
        add(text, sub=True)
    if village.has(HEATHEN_MOMMY) is True:
        add(f"With \"{gm.feature_name(HEATHEN_MOMMY)}\" (in this game): solving the Heathen Mommy's puzzle sets her "
            "Faith to 50 to 59, each equally likely, which brings her into the tribe (0x43979C).", sub=True)
    add("Heathens: they never age, eat, fall sick on their own or gain Divine Energy, while catching up or otherwise (the "
        "life tick skips them, 0x472CB7; The Missing Kids can mark a Heathen child sick, 0x4161D1, which then does "
        "nothing to it); their details can't be viewed (\"You cannot view details about heathens. They do not "
        "believe in you.\"). Becoming a Heathen clears a villager's role, even the Retired Chief's (0x4669F5); "
        "joining the tribe clears it too, except the Retired Chief's (0x466966).")
    add("Heathens never count in the tribe's population or in any statistics row (see Village counts).", gm.OWNER,
        sub=True)
    try:
        import vv_game_mechanics_life as life
        everyone = None if village.general else life.people(village)
    except Exception:  # noqa: BLE001 -- an unreadable villager table gives no village line
        everyone = None
    if everyone:
        believers = [p for p in everyone if not p.heathen]
        n = len(believers)
        crowd = (f"-1 {_p(12 - n)} each age unit (fewer than 12 believers)" if n < 12 else
                 f"+1 {_p(n // 5)} each age unit")
        add(f"This village: {n} believers, so the believers' roll is {crowd}; "
            f"{len(everyone) - n} Heathens outside the tribe.", gm.SAVE)
    return out
