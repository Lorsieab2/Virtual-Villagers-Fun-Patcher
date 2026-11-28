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
FOG_LISTENING = "vv5_fog_of_doom_every_heathen_listens"
FOG_NO_LIMIT = "vv5_fog_of_doom_no_restrictions"
DEVOTION_FAITH = "vv5_devotion_builds_faith"
STATUE_HONORING = "vv5_unfinished_statue_drops_honor"
FORMER_AGE = "vv5_former_villagers_keep_aging"
FORMER_BONES = "vv5_former_villager_heathens_leave_skeletons"
# Heathen Tribe Expansion and Evolution (v1.35.101; it folds Heathen Tribe Ages, Dies and Has Children, All Heathens
# Leave Skeletons and Heathens can be selected in Island Events/Heathen-Exclusive Events).
EVOLUTION = "vv5_heathen_tribe_evolution"


def _setting_text(village, file_name: str) -> str | None:
    """A file the patcher wrote beside the Heathen companions (the patcher's folder next to the game's exe), or None."""
    exe = getattr(village, "exe", None)
    if exe is None:
        return None
    try:
        from pathlib import Path
        import patcher_files
        return (Path(exe).parent / patcher_files.PATCHER_FILES_FOLDER / file_name).read_bytes()[:4096].decode(
            "ascii", "replace")
    except (OSError, ImportError):
        return None


def _rate(village, file_name: str, zero_allowed: bool):
    """The births or arrivals slider's number as the companion reads it (heathen_evo.h): 0.1 to 10 (0 allowed for the
    arrivals), the default when there is no file; None when the game's folder is not known."""
    text = _setting_text(village, file_name)
    if text is None:
        return None if getattr(village, "exe", None) is None else (0 if zero_allowed else 1)
    if zero_allowed and text.strip() in ("0", "0.0"):
        return 0
    return gm.slider_number(village, file_name)


def _option(village, key: str, fallback: int) -> int:
    """A key of "VVFP Heathen Options.txt" (heathen_evo.h he_option), else `fallback`."""
    text = _setting_text(village, "VVFP Heathen Options.txt") or ""
    for line in text.splitlines():
        name, eq, value = line.partition("=")
        if eq and name.strip() == key and value.strip().lstrip("-").isdigit():
            return int(value.strip())
    return fallback


def _times(n) -> str:
    return "N times" if n is None else ("" if n == 1 else f"{n} times ")


def _shrine_facts(add) -> None:
    """The Shrine to the Ancestors ("VVFP Heathen Mausoleum.dll", native/vvfp_heathen_mausoleum)."""
    # The burial write 0x473FA9 by the faction at death; the Heathen AI 0x46E9E0 (half the times asked); the
    # believers' finder 0x46F146 (120 units, or no able Heathen); the carry walk 0x45B650; hotspot 0x0B.
    add("The Shrine to the Ancestors: a Heathen's grave (decided by the faction at death) goes to the Heathens' own "
        "table at the mud hut, 500 graves, never the Mausoleum's. An able adult Heathen (no puzzle role, not sick or "
        "expecting) carries a Heathen's body to the mud hut and buries it, half the times it is asked; believers do "
        "it, still to the mud hut, when no Heathen is able or the body has lain 120 age units (12 real-life hours on "
        "Normal), once The Buried Mausoleum is solved. A full shrine: no grave, the body is gone. Clicking the mud "
        "hut, or dropping a villager on it, opens the game's own Mausoleum screen titled \"Shrine to the Ancestors\" "
        "once it holds a grave. Day of Honor, the Remembrance Ceremony and the everyday Honoring the dead count its "
        "graves; the Village Statistics never do. Heathen graves already in the Mausoleum stay there.", sub=True)


def _heathen_evolution_facts(add, village, where: str) -> None:
    """Heathen Tribe Expansion and Evolution's rules (native/vvfp_heathen_aging, native/vvfp_heathen_life,
    native/vvfp_heathen_mausoleum; native/shared/heathen_evo.h), with the village's own slider numbers when the
    game's folder is known."""
    births = _rate(village, "VVFP Heathen Tribe Births.txt", False)
    arrivals = _rate(village, "VVFP Heathen Arrivals.txt", True)
    show = _option(village, "show_percent", 25) if getattr(village, "exe", None) is not None else None
    blue = (_option(village, "mask_orange_percent", 7) == 0 and _option(village, "mask_red_percent", 3) == 0)
    name = gm.feature_name(EVOLUTION)
    add(f"With \"{name}\" ({where}) the Heathen camp lives as a tribe of its own. Every Heathen ages as believers do "
        "and can die of old age by the believers' own rule (each whole year past 1,100 age units, 55 years, or later "
        "with Medicine: 10% for each year over), the puzzle Heathens too; a puzzle Heathen whose puzzle is unsolved "
        "is replaced at once in the same role. Every Heathen who dies leaves a skeleton. A growing camp makes The "
        "Last Heathen harder to reach, or impossible.", sub=True)
    # Births: 1 in 2,400 x W / t a unit (heathen_evo.h HE_BIRTH_ROLL); the litter HE_TWINS/HE_TRIPLETS_IN_10000.
    births_words = ("set by its slider" if births is None else f"at {births}x")
    add(f"Births ({births_words}): each Heathen woman 14 to 45, not expecting and not the Heathen Mommy, in a couple "
        "with a living adult Heathen man, has a chance each age unit of 1 in 2,400 x the number of such women / the "
        "slider in tenths -- about one baby for the whole tribe every 240 age units (24 real-life hours on Normal, 12 "
        f"on Fast, 40 on Slow) {_times(births)}as often. Twins 5.25%, triplets 1.75% (any Medicine level). Births go "
        "on after The Last Heathen while a Heathen woman and man are alive. A Heathen is only made while 10 villager "
        "records stay free.", sub=True)
    # Arrivals: 1 in 4,800 / t a unit of the village's clock (HE_ARRIVAL_ROLL); groups 40/30/20/10%.
    if arrivals == 0:
        add("New arrivals: none (the arrivals slider is at 0).", sub=True)
    else:
        arrivals_words = "set by its slider" if arrivals is None else f"at {arrivals}x"
        add(f"New arrivals ({arrivals_words}): a chance each age unit of 1 in 4,800 / the slider in tenths -- about one "
            f"arrival every 480 age units (48 real-life hours on Normal) {_times(arrivals)}as often, before and after "
            "The Last Heathen. An arrival is 1, 2, 3 or 4 Heathens (40%, 30%, 20%, 10%); half of the groups of two or "
            "more are a couple with 0 to 2 children aged 2 to 12; the adults are 18 to 40.", sub=True)
    add("Masks of arrivals and Heathen babies: " + ("all blue (\"Keep every new Heathen blue\")." if blue else
        "90% blue, 7% orange, 3% red. The puzzle Heathens keep their own masks."), sub=True)
    add("Couples: two living adult Heathens of either sex who are not kin (never parent and child, full or half "
        "siblings) pair for life, at most one new couple at a time; a couple ends when one dies or joins the tribe. "
        "A natural conception is a woman's and a man's; an island event may give any couple a baby.", sub=True)
    add("A new Chief or Master: when the Heathen Chief or a Heathen Master dies after their puzzle is solved, the "
        "eldest adult Heathen takes the role -- for show until The Last Heathen is solved (the role's skills, mask "
        "and title), the real role after it; a regrown camp of 6 adults gets a real Chief and Masters. Any sex after "
        "the first. A show Chief who joins the tribe becomes a real Retired Chief.", sub=True)
    # vvfp_heathen_aging.c grew_up / replace_child (the Rascal: the Details title 0x4430AE, the stock camp 0x424D23).
    add("Children who grow up: when one of the camp's own children (no recorded parents, never one who left the "
        "tribe) reaches 280 age units (14 years), a new child takes their place at once in the same camp role and "
        "mask: the Rascal -- the camp's orange-masked child, whom the Details screen calls \"Rascal\" and who chases "
        "believers it meets as every orange Heathen does -- by a new Rascal of 140 units, a blue child by one of 120 "
        "or 240, as the game's own camp has them. Couples' babies and arrivals' children are not replaced. Only "
        "while 10 villager records stay free (else it waits), and after The Last Heathen only while New Heathen "
        "Arrivals is above 0.", sub=True)
    # retire_elders: the elder test 0x46F790; the walk 0x4659C5 / 0x465A06.
    add("Elders retire: at the game's elder age (1,000 age units at Medicine 1, 160 more for each further level; the "
        "game's own test) a Heathen with a camp role or a puzzle role -- the Heathen Doctor, a Heathen Master, the "
        "Heathen Mommy -- gives it to the eldest adult Heathen who is not an elder and holds none, with the role's "
        "own skill, Faith and (the Mommy) infant, and lives at the encampment. The Heathen Chief never retires. With "
        "nobody younger the elder keeps the role. Elder Heathens walk at their normal pace; elder believers walk at "
        "the slow pace (40) as in the game.", sub=True)
    # Heathen Life's unit (vvfp_heathen_life.c): onset 0x465F50; damage 60 in 100, floor 21; recovery +1 (elders 20%);
    # doctors by the skill check 0x46B270's rule; no healer: 1 in 240 a unit.
    add("Sickness: an ordinary Heathen falls sick by the believers' own rule (Medicine 1: 4 in 1,440 a unit; "
        "Medicine 2: 4 in 2,460; Medicine 3: 3 in 5,400; elders a further 15 in 1,000; on the easiest difficulty "
        "half the units never roll). A sick Heathen loses 1 health on 61 rolls in 100, never below 21, so never dies "
        "of it; one who is not sick gains 1 a unit (an elder on 1 roll in 5). The camp's doctor is the ordinary adult "
        "Heathen with the best Healing (never the puzzle's Heathen Doctor): they walk to the patient and the "
        "believers' Healing check decides (a roll of 0 to 99 at or under Healing + 33); with nobody able, a sick "
        "Heathen gets well on their own on 1 unit in 240. Heathen cures never count in People Cured. Heathens never "
        "eat from the food store and never starve.", sub=True)
    show_words = "a share set in the row's Settings window" if show is None else f"{show}%"
    add(f"Show actions ({show_words} of an idle ordinary adult Heathen's choices, when it is not raining; the rest "
        "are the game's own Heathen life): harvesting noni once the Fence is built, crops once the Hydroponic Farm is "
        "restored and fish once The Lake is solved -- taking nothing, carried to the encampment, not the granary; "
        "visiting the pools, the Believer Idol once carved, the science lab, and the Love Shack and Clothing Hut doors "
        "once built (no embrace, no clothes); a show meal; praying at the mud hut. Only what believers of their age "
        "do: every show action is an adult's (14 or older; elders do them all), the Love Shack only at the couples' "
        "ages (18 to 49); a Heathen child plays in the nursery only while someone teaches at the nursery school. A "
        "sick Heathen rests at the encampment.", sub=True)
    add("Skills: the skill of the show action just done (Devotion at the statue and the mud hut, Research at the lab), "
        "or on 1 unit in 20 the skill of the Heathen's camp role, is practised by the believers' own check (a roll of "
        "0 to 99 at or under the skill + 33, + 66 for one who likes learning, + 16 for one who dislikes it) and gain "
        "((70 - skill) / 18, doubled for a liker, halved for a disliker), with "
        "no technology bonus and no mastery trophies. A Heathen keeps their skills on joining the tribe.", sub=True)
    _shrine_facts(add)
    add("Heathens can be chosen for island events (the new ones and the game's own) and the Heathen-Exclusive Events "
        "can happen, with Story / Cheat Upgrades. Every Heathen's conception, birth, couple, arrival, new role, death "
        "and grave goes in the logs, marked as a Heathen. None of this has been seen in a running game yet.",
        sub=True)
# No game exe and no patch log was found for the save, so whether a patch is in the game cannot be read; the player
# can name the game with the window's Browse... button.
UNTOLD = gm.UNTOLD
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
        where = "in this game" if faith_loss else UNTOLD
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
                # The roll is rand(N) < 1, N per cause (native/vvfp_faith_loss FL_ODDS_*: the owner, 2026-11-22); the
                # patch's hook at 0x4681DB, its cave 0x494F14; the four loss sites 0x46805E, 0x46807E, 0x4680BB,
                # 0x468184 (scripts/build_apprentice_faith_puddles_features.py).
                f"Believers in a crisis mostly stay and die rather than leave, decided once per villager for each "
                f"crisis. There are four: starvation (food under 10), hunger (food 10 to 250), sickness, and too few "
                f"believers (fewer than 12). The first time one of them would take a believer's last Faith, they "
                f"become a Heathen 1 time in 20 for starvation ({pct(below(20, 1))}), 1 in 25 for sickness "
                f"({pct(below(25, 1))}), 1 in 50 for hunger ({pct(below(50, 1))}) and 1 in 50 for too few believers "
                f"({pct(below(50, 1))}). Otherwise they are marked for that crisis, which "
                "never takes them below Faith 1 again, so they go on eating, starving and falling ill like any "
                "believer (a Heathen does none of that). Each crisis ends on its own: starvation and hunger when food "
                "is above 250, sickness when the villager is cured, too few believers at 12 or more believers; a later "
                "crisis of that kind is decided afresh. The marks are kept by villager in the patcher's file in the "
                "save's folder (\"Faith Loss\\Believers Kept - Save <S>.dat\").",
                "A thriving village (8,000 food or more, Spirituality, the Tribute Statue, 12 or more believers, "
                "nobody sick) still rises towards 100: only the chances change, and no loss roll fires there."):
            add(text, sub=True)
    new_heathens = village.has(NEW_HEATHENS)
    if new_heathens is not False:
        where = "in this game" if new_heathens else UNTOLD
        # The patch's hook at 0x467FDF, its cave 0x494F80: the orange and red mask bytes cleared (the role is
        # already 0), Faith -38 - rand(30).
        add(f"With \"{gm.feature_name(NEW_HEATHENS)}\" ({where}): a believer the Faith drift turns Heathen becomes "
            "an ordinary blue-mask Heathen with Faith -38 to -67, drawn as the game draws a new village's ordinary "
            "Heathens (normally they keep the Faith that took them there, 0 to -3). So it takes as much preaching as "
            "any blue Heathen to win them back. The Spa, The Cracked Mask and the Custom Island Event keep their -10.")
    notice = village.has(HEATHEN_NOTICE)
    if notice is not False:
        where = "in this game" if notice else UNTOLD
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
            # The wait is the Heathen's own +0x1CF4 (saved at entry +0x114): set to the clock + 7,200 at 0x468F2A, tested
            # at the sermon's end 0x468E19 (src/vv_game_mechanics_villagers.py has the clock and the save's field).
            "Preaching to a Heathen (after the preacher's Devotion check): +3, +4 at Devotion 50 or more, +5 at 88 or "
            "more. That Heathen then cannot be preached to for 2 real-life hours (real time, the same at every "
            "speed), paused or closed: a sermon before then ends with the game's \"tired of listening\" message and no Faith. "
            "Each Heathen keeps their own wait in the save (Villagers shows how long is left). The Heathen Doctor, "
            "the Chief, the three Masters and the Mommy cannot be preached to.",
            # The listeners are those in behaviour 0xE4; the +30 and the wait at 0x46D2A8, 0x46D2D8.
            "Spreading the Word (the Retired Chief's sermon): +30 to one listener picked at random, who then cannot "
            "be preached to for 2 real-life hours (real time) either.",
            # 0x41F78F skips roles 12 to 17; each Heathen's wait is set to the clock + 7,200 at 0x41F7B8 / 0x41F7BD.
            "The Earthquake God Power: +2 to +8 to every villager but the six special roles: the Heathen Doctor, "
            "Heathen Chief, Heathen Master Scientist, Heathen Master Builder, Heathen Master Farmer and Heathen "
            "Mommy, and the Retired Chief, who keeps the Heathen Chief's role (see God powers). Every Heathen it "
            "reaches then cannot be preached to for 2 real-life hours (real time) as well.",
            # The cure 0x468CFB; The Heathen Chief 0x4360EE; the Hydroponic Farm 0x439E35.
            "Curing the Heathen Doctor: Faith set to 25 to 59, each equally likely. Solving The Heathen Chief: the "
            "Chief's Faith set to 100. Solving the Hydroponic Farm: the Heathen Master Farmer +80.",
            "Island events: their own amounts (see Island events)."):
        add(text, sub=True)
    # Practising Devotion is the skill check 0x46B270 with skill 5: Honoring (behaviour 0xA0, 0x45CB70) goes to the
    # statue's spot on rand(100) < 50 and there queues the check on rand(100) < 25 (0x45CC92); the sermon end checks the
    # preacher (0x468E9A).  The check passes on rand(100) <= Devotion + 33 (0x46BB7D; 66 likes learning, 16 dislikes,
    # +15 / +30 at Learning 2 / 3) and gains (70 - Devotion) / 18 + the Spirituality level (0x46BC82).
    add(f"Practising Devotion is the game's Devotion skill check. It comes on 1 Honoring in 8 (half of all Honorings "
        f"go to the statue, and {_p(25)} of those end in the check) and on every sermon to a Heathen, while catching up "
        f"too. The check passes on a roll of 0 to 99 at or under Devotion + 33 (+66 for a villager who likes learning, "
        f"+16 for one who dislikes it; Learning 2 or 3 adds 15 or 30); a pass raises Devotion by (70 - Devotion) / 18 "
        f"plus the Spirituality level.")
    statue_honoring = village.has(STATUE_HONORING)
    if statue_honoring is not False:
        # native/vvfp_statue_honoring: the statue handler 0x479560's Confused dispatch 0x479726 (the stage +8 of
        # 0x51D950 at 1 or 2, the job dispatcher's own Honoring test 0x46CDC6), the companion's own 1-in-2 draw.
        where = "in this game" if statue_honoring else UNTOLD
        add(f"With \"{gm.feature_name(STATUE_HONORING)}\" ({where}): an adult believer dropped on the statue while "
            f"it is carved but its next stage waits for technology, who is \"Confused\" in the normal game, Honors "
            f"instead 1 time in 2 (50%, the patcher's own roll): the game's own Honoring, so its Devotion check comes as above (1 such "
            f"Honoring in 8).", sub=True)
    devotion_faith = village.has(DEVOTION_FAITH)
    if devotion_faith is not False:
        where = "in this game" if devotion_faith else UNTOLD
        # native/vvfp_devotion_faith: the check's entry spliced; two separate rand(10) < 1 rolls (0x403660), the Faith
        # one rand(20) < 1 when Faith Loss is Doubled/Gains Halved's byte 0x46809B is in the game (the owner,
        # 2026-11-21).
        if faith_loss is True:
            chance = (f"a 1 in 20 chance ({pct(below(20, 1))}) of Faith +1 (halved by "
                      f"\"{gm.feature_name(FAITH_LOSS)}\", in this game)")
            halved = ""
        else:
            chance = f"a 1 in 10 chance ({pct(below(10, 1))}) of Faith +1"
            halved = (f" With \"{gm.feature_name(FAITH_LOSS)}\" also ticked, the Faith chance is 1 in 20 "
                      f"({pct(below(20, 1))}); the Divine Energy chance stays 1 in 10.")
        add(f"With \"{gm.feature_name(DEVOTION_FAITH)}\" ({where}): each Devotion check of a believer, passed or "
            f"failed, gives {chance}, never above 100, and a separate 1 in "
            f"10 chance of Divine Energy +1 through the game's own adder, never above the village's cap. Heathens and "
            f"the six special roles (the Heathen Doctor, the Heathen Chief and the Retired Chief, the three Masters, the "
            f"Heathen Mommy) never get these rolls.{halved}", sub=True)
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
        where = "in this game" if keep_masks else UNTOLD
        # The join 0x4668B0, or The Defector's direct call 0x41699F; the mask the game drew is 0x4728C6's.
        add(f"With \"{gm.feature_name(KEEP_MASKS)}\" ({where}) a Heathen who joins the tribe (The Defector's "
            "included) keeps the mask the game drew on them (purple for the Heathen Doctor and the three Masters, the "
            "Chief's for the Heathen Chief, else orange, red or blue) as their Change Appearance mask, kept by the "
            "Origins upgrades. Change Appearance can change it or take it off, and Reset to original gives it back "
            "(their original look is the one they had as a Heathen, mask and all). Heathens who joined before the "
            "patch are not given one. One who later goes back to the Heathens wears the mask they wore as a Heathen "
            "before (blue, orange, red, purple or the Chief's) but is treated as an ordinary Heathen in the blue "
            "mask: a believer dropped on them preaches, they can be converted again, and they are never a Master or "
            "the Chief again.", sub=True)
    # The Heathen aging rows (native/vvfp_heathen_aging): the age credit's Heathen test 0x470077 and the life tick's
    # skip 0x472CB7, the believers' old-age rule 0x472FC6..0x47304A.
    evolution = village.has(EVOLUTION)
    if evolution is not False:
        _heathen_evolution_facts(add, village, "in this game" if evolution else UNTOLD)
    if evolution is not True:
        has = village.has(FORMER_AGE)
        if has is not False:
            where = "in this game" if has else UNTOLD
            add(f"With \"{gm.feature_name(FORMER_AGE)}\" ({where}) a villager who left the tribe for the Heathens "
                "ages as believers do and can die of old age by the believers' own rule (each whole year past 1,100 "
                "age units, 55 years, or later with Medicine: 10% for each year over); they still never eat, starve "
                "or fall sick, and are never replaced.", sub=True)
    bones = village.has(FORMER_BONES)
    if bones is not False and evolution is not True:
        add(f"With \"{gm.feature_name(FORMER_BONES)}\" ({'in this game' if bones else UNTOLD}) a villager who left "
            "the tribe and dies a Heathen leaves a skeleton, buried at the mud hut in the Shrine to the Ancestors "
            "(below); one who rejoined the tribe goes to the Mausoleum as always.", sub=True)
        _shrine_facts(add)
    # The drop handler 0x443BF0's mask test 0x443D4D (orange +0x1CED, red +0x1CEE turned away at 0x44402D; the rest
    # get Heathen action 6 and believer action 0x27); the sermon's end, the work event 0x468DA0.
    add("Dropping a believer of 14 or more on a Heathen in the blue mask starts preaching: the believer is "
        "\"Explaining the truth\", then (after the Devotion check) the Heathen is \"Listening\" and gains the Faith "
        "below. A drop on a Heathen in the orange or red mask does nothing.")
    # Fog of Doom Lets Red and Orange Heathens Listen (native/vvfp_fog_listening): the mask test spliced; the game's thick-fog
    # test 0x476260 on the weather 0x710948 (only the Fog of Doom sets thickness 4, 0x41FB60); Faith +0x1CF0 < -10.
    fog_listen = village.has(FOG_LISTENING)
    if fog_listen is not False:
        where = "in this game" if fog_listen else UNTOLD
        free = village.has(FOG_NO_LIMIT)
        add(f"With \"{gm.feature_name(FOG_LISTENING)}\" ({where}): while the Fog of Doom God Power's thick fog "
            "lasts, a drop on a Heathen in the orange or red mask whose Faith is below -10 starts the same preaching, "
            "with the same Faith; from -10 up only the Earthquake God Power raises their Faith, and the first such "
            "drop in a village says so in a popup (with Story / Cheat Upgrades), once per village (Start Over resets "
            "it). Natural fog and "
            "other weather never count. The Chief, purple-masked Heathens and the Heathen Mommy are puzzle Heathens and never listen this way.", sub=True)
        if free is not False:
            add(f"With \"{gm.feature_name(FOG_NO_LIMIT)}\" ({'in this game' if free else UNTOLD}) as well: in the "
                "Fog of Doom they listen whatever their Faith.", sub=True)
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
