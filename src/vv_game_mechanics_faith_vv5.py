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
FAITH_LOSS = "vv5_faith_loss_doubled_gains_halved"
NEW_HEATHENS = "vv5_new_heathens_get_heathen_faith"
HEATHEN_NOTICE = "vv5_heathen_conversion_notice"
KEEP_MASKS = "vv5_heathens_keep_masks_when_converted"
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
    # The clamp -100..100 0x467FE4; the Heathen turn 0x4669E0; the join 0x4668B0; a convert below 5 set to 55 at
    # 0x467FC7; only while the island runs (manager +0x17E39, tested at 0x467F99).
    add("Faith runs from -100 to 100. A believer whose Faith falls to 0 or less becomes a Heathen at once (\"A "
        "villager has stopped believing in you!\"). A Heathen whose Faith rises above 0 joins the tribe (\"There is a "
        "new believer!\"), and a convert left below 5 is set to 55. This happens only while the village is running: "
        "loading a save never converts anyone.")
    # rand(30) + 30 at 0x468508; a twin or triplet copies the first baby's Faith at 0x4688C8.
    add("Every villager the game makes (each baby, each newcomer) starts at Faith 30 to 59, each value equally "
        "likely. A twin or triplet gets the same Faith as the first baby.", sub=True)
    # The drift 0x468040, run by the life tick 0x472C90, which skips Heathens (0x472CB7).
    add("Each age unit (3, 6 or 10 real-life minutes on Fast, Normal or Slow), every believer's Faith moves by the sum "
        "of these rolls. Heathens get none of them, while catching up or otherwise:")
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
            # The skips at 0x4681A7.
            f"Then, when the sum is a fall and Faith is below 5, the fall is skipped {_p(50)} of the time; when it is a "
            f"rise and Faith is above 75, the rise is skipped {_p(70)} of the time. Each roll's exact odds are a hair "
            "above the round percentage, as the game's random numbers fall."):
        add(text, sub=True)
    faith_loss = village.has(FAITH_LOSS)
    if faith_loss is not False:
        # Stock first, then the patch (scripts/build_apprentice_faith_puddles_features.py, FAITH_EDITS).  Shown
        # too when whether the game has it cannot be told (no exe or patch log found), as every other patch is.
        doubled = 1 - (1 - below(100, 60) / DRAWS) * (1 - below(100, 20) / DRAWS)
        where = "in this game" if faith_loss else "whether the game has it could not be told"
        add(f"With \"{gm.feature_name(FAITH_LOSS)}\" ({where}) every loss roll's chance is doubled and every "
            "gain roll's halved (each roll: the normal chance -> the patched one):")
        for text in (
                f"Food under 10: -1 {pct(round(starving * DRAWS))} -> {pct(round(doubled * DRAWS))} ({_p(30)} -> "
                f"{_p(60)}, or else {_p(10)} -> {_p(20)}); 10 to 250: -1 {_p(10)} -> {_p(20)}; 8,000 or more: +1 "
                f"{_p(20)} -> {_p(10)}.",
                f"A sick believer loses 1 more {_p(15)} -> {_p(30)} of the time.",
                f"The Tribute Statue solved: +1 {_p(30)} -> {_p(15)}; its first stage {_p(10)} -> {_p(5)}, its second "
                f"{_p(20)} -> {_p(10)}.",
                f"Spirituality level 1, 2 or 3: +1 {_p(10)}, {_p(20)} or {_p(30)} -> {_p(5)}, {_p(10)} or {_p(15)}.",
                f"Fewer than 12 believers: -1 with a chance of (12 - believers) in 100 -> 2 x (12 - believers) in 100 "
                f"(11 believers {_p(1)} -> {_p(2)}; 1 believer {_p(11)} -> {_p(22)}); 12 or more: +1 with a chance of "
                f"(believers / 5) in 100 -> (believers / 10) in 100, rounded down (50 believers {_p(10)} -> {_p(5)}).",
                f"A fall with Faith below 5: skipped {_p(50)} of the time -> never skipped, so a falling believer can "
                f"reach 0 and become a Heathen; a rise above 75 is still skipped {_p(70)} of the time.",
                # The roll is rand(10) < 1; the patch's hook at 0x4681DB, its cave 0x494F14.
                f"Starving and sick believers mostly die rather than leave, decided once per villager per crisis. The "
                f"first time low food or sickness would take a believer's last Faith (the drift's other changes alone "
                f"leaving it above 0), 1 time in 10 ({pct(below(10, 1))}) they become a Heathen. Otherwise they are "
                "marked, and low food and sickness never take them below Faith 1, so they go on eating, starving and "
                "falling ill like any believer (a Heathen does none of that). The mark clears at the first age unit "
                "with food above 250 and the villager not sick; a later crisis is decided afresh. Too few believers "
                "takes Faith as in the normal game. The marks are kept by villager in the patcher's file in the save's "
                "folder (\"Faith Loss\\Believers Kept - Save <S>.dat\").",
                "A thriving village (8,000 food or more, Spirituality, the Tribute Statue, 12 or more believers, "
                "nobody sick) still rises towards 100: only the chances change, and no loss roll fires there."):
            add(text, sub=True)
    new_heathens = village.has(NEW_HEATHENS)
    if new_heathens is not False:
        where = "in this game" if new_heathens else "whether the game has it could not be told"
        # The patch's hook at 0x467FDF, its cave 0x494F80: the orange and red mask bytes cleared (the role is
        # already 0), Faith -38 - rand(30).
        add(f"With \"{gm.feature_name(NEW_HEATHENS)}\" ({where}): a believer the Faith drift turns Heathen becomes "
            "an ordinary blue-mask Heathen with Faith -38 to -67, drawn as the game draws a new village's ordinary "
            "Heathens (normally they keep the Faith that took them there, 0 to -3). So it takes as much preaching as "
            "any blue Heathen to win them back. The Spa, The Cracked Mask and the Custom Island Event keep their -10.")
    notice = village.has(HEATHEN_NOTICE)
    if notice is not False:
        where = "in this game" if notice else "whether the game has it could not be told"
        add(f"With \"{gm.feature_name(HEATHEN_NOTICE)}\" ({where}): a popup, \"The Breaking Point\", in the "
            "island-event window tells you when believers lose faith and leave. There is one popup for a whole "
            "catch-up, Time Warp or time skip. It is not an island event (the next one keeps its time; not counted, "
            "not logged), and a believer an island event makes a Heathen is not in it. It needs Story / Cheat "
            "Upgrades to show it, and a living adult, as every island event.")
        add("When and what it says: each believer the drift turns Heathen is counted under the loss roll that took "
            "their Faith (starvation: food under 10; hunger: food 10 to 250; sickness; too few believers). 3 real-life "
            "seconds after the last one (real time, the same at every speed), once no other island event is showing "
            "or on its way, the popup says \"Several of your villagers have lost faith due to the dire conditions "
            "amongst the tribe and have decided to join the heathens.\" and \"N villagers have left due to ...\" "
            "(with Guardians of Isola: they have lost trust in the village's ability to provide for their needs and "
            "join the Isolans, and a list such as \"Starvation: N villagers\").", sub=True)
    add("Other things that change Faith, exactly:")
    for text in (
            # The wait is set at 0x468F2A.
            "Preaching to a Heathen (after the preacher's Devotion check): +3, +4 at Devotion 50 or more, +5 at 88 or "
            "more. That Heathen then cannot be preached to for 2 real-life hours (real time, the same at every "
            "speed), paused or closed. The Heathen Doctor, the Chief, the three Masters and the Mommy cannot be "
            "preached to.",
            # The listeners are those in behaviour 0xE4; the +30 and the wait at 0x46D2A8, 0x46D2D8.
            "Spreading the Word (the Retired Chief's sermon): +30 to one listener picked at random, who then cannot "
            "be preached to for 2 real-life hours (real time) either.",
            # 0x41F78F skips roles 12 to 17.
            "The Earthquake God Power: +2 to +8 to every villager but the six special roles: the Heathen Doctor, "
            "Heathen Chief, Heathen Master Scientist, Heathen Master Builder, Heathen Master Farmer and Heathen "
            "Mommy, and the Retired Chief, who keeps the Heathen Chief's role (see God powers).",
            # The cure 0x468CFB; The Heathen Chief 0x4360EE; the Hydroponic Farm 0x439E35.
            "Curing the Heathen Doctor: Faith set to 25 to 59, each equally likely. Solving The Heathen Chief: the "
            "Chief's Faith set to 100. Solving the Hydroponic Farm: the Heathen Master Farmer +80.",
            "Island events: their own amounts (see Island events)."):
        add(text, sub=True)
    if village.has(HEATHEN_MOMMY) is True:
        # Her puzzle's Faith is set at 0x43979C.
        add(f"With \"{gm.feature_name(HEATHEN_MOMMY)}\" (in this game): a new village's Heathen Mommy starts "
            "carrying one baby whose father is \"Unknown\", a name with head 2 and body 2 and no villager behind it "
            "(see Genetics). Solving the Heathen Mommy's puzzle sets her Faith to 50 to 59, each equally likely, which "
            "brings her into the tribe.", sub=True)
    # The owner's words (2026-10-25: "Heathens never fall sick" is true in play): the life tick skips them, so a
    # sick mark an island event sets on one has no effect (The Missing Kids' own line says so).
    # The mask pick 0x4728C6: roles 12 and 14-16 purple, 13 the Chief's (the table 0x472B60), then the orange byte
    # +0x1CED (the chasers) and the red byte +0x1CEE (the scary ones), else blue.
    add("A Heathen's mask is chosen by its role and kind, never by Faith: the Heathen Doctor and the three Masters "
        "wear purple, the Heathen Chief the Chief's mask, the chasers orange and the scary ones red; every other "
        "Heathen wears the blue mask.")
    # Barrel O' Babies! (heathens) 0x4152B0; ordinary Heathens -38 - rand(30) at 0x471070, the five fixed ones
    # 0x470F1F..0x471037; the special Heathens by the creator calls of 0x424AC0.
    add("A Heathen's Faith is set once, when the game makes them, and never drifts: Barrel O' Babies! (heathens) "
        "-55; a new village's ordinary Heathens -38 to -67, each equally likely, except five set to -5, -9, -16, -23 "
        "and -30; the Heathen Doctor -14, the three Masters -74, the Heathen Chief -94.")
    # The life tick skips Heathens at 0x472CB7; The Missing Kids' sick mark 0x4161D1; becoming a Heathen clears the
    # role at 0x4669F5, joining clears it except the Retired Chief's at 0x466966.  The line's start is pinned by
    # tests/test_game_mechanics_code_vs_observation.py (the code side of "Heathens never fall sick").
    add("Heathens, in the game's code: they are skipped by the villagers' age-unit update, so while catching up or "
        "otherwise they never age, eat, gain Divine Energy or get the sickness roll, and a sick mark costs them no "
        "health. The Missing Kids can mark a Heathen child sick (see Island events). Their details can't be viewed "
        "(\"You cannot view details about heathens. They do not believe in you.\"). Becoming a Heathen clears a "
        "villager's role, even the Retired Chief's; joining the tribe clears it too, except the Retired Chief's.")
    # Heathens Keep Their Masks When Converted (native/vvfp_heathens_keep_masks): shown when the game has it, or when
    # whether it has it cannot be told, as every other patch is.
    keep_masks = village.has(KEEP_MASKS)
    if keep_masks is not False:
        where = "in this game" if keep_masks else "whether the game has it could not be told"
        # The join 0x4668B0, or The Defector's direct call 0x41699F; the mask the game drew is 0x4728C6's.
        add(f"With \"{gm.feature_name(KEEP_MASKS)}\" ({where}) a Heathen who joins the tribe (The Defector's "
            "included) keeps the mask the game drew on them (purple for the Heathen Doctor and the three Masters, the "
            "Chief's for the Heathen Chief, else orange, red or blue) as their Change Appearance mask, kept by the "
            "Origins upgrades. Change Appearance can change it or take it off, and Reset to original gives it back "
            "(their original look is the one they had as a Heathen, mask and all). Heathens who joined before the "
            "patch are not given one.", sub=True)
    add("The owner: Heathens never fall sick in play.", gm.OWNER, sub=True)
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
