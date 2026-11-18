"""Generate the five "Builders Fix Huts When Idle" rows.

The owner: "When no building projects are present/available to be worked on
AND not all population huts are complete, then builders will fix huts to
increase their skill (just makes it able to be autonomously chosen; applies
during catch-up time and live playing)."

The behaviour lives in one companion, "VVFP Fix Huts.dll"
(native/vvfp_fix_huts), which detours each game's Building dispatcher at its
"nothing available" point -- see the source for the five sites.  How the
companion gets loaded differs:

  * A New Home, The Lost Children, The Tree of Life, New Believers: a
    companion that already runs every frame in that game (the Origins
    companion; New Believers' Task 9 companion) loads it by full path and
    calls VvfpFixHutsInstall(game), which verifies the stock bytes and writes
    the detour at run time.  Those rows patch no executable byte.
  * The Secret City has no such companion (its shared Origins DLL is not
    rebuilt from source), so its row carries a small executable-side stub:
    the dispatcher's empty-list test jumps to the stub, which resolves the
    companion's VvfpFixHutsDecide once (GetModuleHandleA / LoadLibraryA /
    GetProcAddress from the stock import table, the same shape the VV3
    parentage trampoline uses) and calls it; the stub lives in the reserved
    zero range of the page Origins appends (a composition overlay at
    0x6DF800, after the parentage overlay at 0x6DF400), with a standalone
    appended-section form that is never used because the row depends on
    Origins.

The DLL is pinned by SHA-256, so re-run this after every rebuild.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import keystone

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from origins_base_text import ORIGINS_BASE_SENTENCE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "fix_huts" / "VVFP Fix Huts.dll"
STOCK_VV3 = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"

DESCRIPTION = (
    "Builders fix huts when no building projects are present, and build first. "
    "This makes builders more likely to do their building work, not certain: "
    "each time the game chooses what a builder does, the patch steps in about "
    "three times in four, and the rest of the time the game chooses exactly as "
    "it always has. A villager whose job checkmark on the Villager Details "
    "screen is not Building (any other job, or none) but whom the game gives "
    "building work anyway gets all of this only on 14% of those choices; "
    "otherwise the game chooses exactly as it always has. When it steps in, construction always comes first -- a "
    "builder goes straight into a new hut or building project the game would "
    "let it build, even when the game's own random roll would have skipped it "
    "this time, and never fixes a hut while there is one. When no building "
    "project is available to be worked on and at least one population hut "
    "stands -- while another is unbuilt, and below Building level 3 even once "
    "every one is built -- a builder with nothing to do examines and fixes one "
    "of the huts that already stands, the game's own \"Examining hut\" / \"Fixing hut\" job, "
    "which trains Building. It only makes that job able to be chosen "
    "autonomously; the job itself, its chance of a repair and its skill roll are "
    "the game's own. Whenever there is hut work to do, a builder also does "
    "this regardless of the food supply: plentiful food no longer skips "
    "the builder's work attempt (A New Home, The Lost Children), and scarce "
    "food no longer sends the builder to farm or gather first (The Secret City, "
    "The Tree of Life, New Believers).{huts} {share} {catchup} "
    + ORIGINS_BASE_SENTENCE
    + " That base's companion loads this patch's DLL (in The Secret City, a "
    "small stub in the page the base appends does); if the DLL cannot be "
    "loaded, the stock scheduler runs unchanged."
)
# The other behaviour patches of each game that share the one roll per choice.
SHARE = {
    "vv1": "Builders and Healers Work First, Healers Study Plants Regardless of Food and Builder Action Fixes use the same roll when selected with it,",
    "vv2": "Builders and Healers Work First and Healers Study Plants Regardless of Food use the same roll when selected with it,",
    "vv3": "Builders and Healers Work First uses the same roll when selected with it,",
    "vv4": "Builders and Healers Work First uses the same roll when selected with it,",
    "vv5": "Builders and Healers Work First uses the same roll when selected with it,",
}


# Huts need a manual start (A New Home, The Lost Children): the stock
# Building branch lets builders work on the second and third population hut
# by population alone; see "Huts need a manual start" in
# native/vvfp_fix_huts/vvfp_fix_huts.c.
_MANUAL = (
    " With this patch builders start the second or third population hut only after you have dropped "
    "a villager on it at least once, and from then on they finish it whatever the population. This "
    "holds every time the game chooses, not only three times in four."
)
HUTS = {
    "vv1": (
        " The new population huts also change. The normal game has a hidden rule here: it shows the "
        "scaffold of the second population hut once the village has 15 villagers and of the third at 28, "
        "but its builders will not work on the second hut until there are more than 22 villagers, nor on "
        "the third until there are more than 45 -- and above those numbers they start one on their own, "
        "while a hut they have already started is abandoned whenever the population falls back to 22 (or "
        "45) or below. With this patch, at or below 22 (or 45) villagers builders only work on the "
        "second or third population hut once you have dropped a villager on it at least once, and from then "
        "on they finish it whatever the population; above that, as in the original game, they may start it "
        "themselves. This holds every time the game chooses, not only three times in four. Builder Action "
        "Fixes makes the same change in the executable."
    ),
    "vv2": (
        " The new population huts also change. The normal game has a hidden rule here: it shows the "
        "scaffold of the second population hut once the village has 21 villagers and of the third at 46, "
        "but its builders will not work on the second hut until there are more than 22 villagers, nor on "
        "the third until there are more than 45, and then only on a hut someone has already worked on -- "
        "and a hut they have already started is abandoned whenever the population falls back to 22 (or "
        "45) or below." + _MANUAL
    ),
}
HUT_GATE_BEHAVIOR = {
    "vv1": "The Building branch's new-hut test (0x44754A) is extended: hut 10 and hut 11 are built while they are not complete and either their progress is 2 or more, at any population, or the population is above 22 / 45 as in the stock game (stock: only the population, whatever the progress). The village drawing routine marks a shown scaffold with progress 1 (0x414B0C, 0x414BF1); a villager the player drops on it works it past that. So at or below 22 / 45 builders never start one of these huts by themselves and always finish one the player has started; above, they may start it as the stock game does. Hut 9, the rest of the branch and the build itself are the game's own. This holds on every choice, whether or not the roll below passes.",
    "vv2": "The Building branch's new-hut test (0x4600DE) is replaced: hut 25 and hut 26 are built while they are not complete and their progress is 2 or more, whatever the population (stock: also more than 22 / more than 45 villagers). The village drawing routine marks a shown scaffold with progress 1 (0x419702, 0x41977D); a villager the player drops on it works it past that. So builders never start one of these huts by themselves and always finish one the player has started. Hut 24, the rest of the branch and the build itself are the game's own. This holds on every choice, whether or not the roll below passes.",
}
GATE_RUNTIME = {
    "vv1": {"va": "0x44754A",
            "stock_bytes": "E8415AFDFF83F8167E228B9610E00300389AF09F00007414536A0A558BCEE823ABFFFF5F5D8AC35B5EC208008B8E10E00300E80F5AFDFF83F82D7E4B8B8610E003003898F89F0000743D",
            "routine": "the Building dispatcher's new-hut test for huts 10 and 11 (0x4472C0), replaced by not complete and (progress >= 2 or population above 22 / 45); Builder Action Fixes' identical bytes are accepted as already in place"},
}
# The Lost Children's companion is installed only once the village is first
# drawn, after the load-time catch-up of a session has already run, so its new-
# hut test is written into the executable by this row instead.
GATE_PATCHES = {
    "vv2": [{
        "offset": "0x600DE",
        "before": "E87D57FCFF83F8167E1A8B86D474E500389820E80200740C39A81CE802000F8D36FEFFFF8B8ED474E500E85357FCFF83F82D7E1A8B86D474E500389828E80200740C39A824E802000F8D39FEFFFF",
        "after": "389920E80200740D83B91CE80200010F8F45FEFFFF8B8ED474E500389928E80200742B83B924E80200010F8F57FEFFFFEB1CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
        "purpose": "the Building branch's new-hut test (0x4600DE): build hut 25 / hut 26 while it is not complete and its progress is 2 or more -- worked on past the drawing routine's progress-1 scaffold mark, which a player's drop does -- whatever the population, instead of only above 22 / 45 villagers; the int3 bytes after the jmp are never reached",
    }],
}
# Catch-up (time passing while the game was closed, and Time Warp) runs each
# game's own worker -- A New Home 0x42E790, The Lost Children 0x43B4D0, The
# Secret City 0x45BF00, The Tree of Life 0x465750, New Believers 0x46E8E0 --
# which picks the job with the stock picker and calls the Building dispatcher
# directly, never the idle scheduler.  Everything inside the dispatcher acts
# there; the food bypass, which lives in the scheduler, does not.
CATCHUP = (
    "The food bypass acts only while you play. During catch-up (time passing while the game was "
    "closed, and Time Warp) each villager does the job the stock game picks, and when that job is "
    "building, the same build-first and hut-fixing rules apply{huts}."
)


# Not checked on the job (the owner, 2026-10-20): "ALL villagers NOT checked on X
# skill perform actions that train that skill 14% of the time" -- patch
# behaviours only; see "Not checked on the job" in native/vvfp_fix_huts.
PREFERENCE_FIELD = {
    "vv1": "village + index*0x3D8 + 0x3D0, Building 4",
    "vv2": "village + index*0xE48C + 0x7F8, Building 5",
    "vv3": "record + 0xEC0, Building 4, Healing 2",
    "vv4": "[object + 0x1B88] + 0x1C70, Building 4, Healing 2",
    "vv5": "[object + 0x1B88] + 0x1C74, Building 4, Healing 2",
}
PREFERENCE_BEHAVIOR = (
    "Not checked on the job: everything this companion makes a villager do trains Building -- construction "
    "first and the hut fix inside the Building dispatcher{healer} -- and the dispatcher is reached for anyone "
    "the game gives that job. For a villager whose job preference ({field}; 0 or -1 is no checkmark) is not "
    "that job, the companion acts only when, after the decision's roll passes, one more roll of its own "
    "passes 14 times in 100 (NOT_PREFERRED_PERCENT, drawn once per decision like the decision's roll): about "
    "10.5% of such decisions instead of 75%. A failed roll is the stock game's choice. A villager checked on "
    "the job is unchanged. 14 is the later games' own figure: their job chooser keeps a villager's checked "
    "job 86 times in 100."
)
PREFERENCE_HEALER = {
    "vv3": "; and the low-food bypass, which sends a builder or (with Builders and Healers Work First) a healer "
           "straight to their pick, asks the same of the picked job, Building or Healing",
    "vv4": "; and the low-food bypass, which sends a builder or (with Builders and Healers Work First) a healer "
           "straight to their pick, asks the same of the picked job, Building or Healing",
    "vv5": "; and the low-food bypass, which sends a builder or (with Builders and Healers Work First) a healer "
           "straight to their pick, asks the same of the picked job, Building or Healing",
}


def describe(game: str) -> str:
    return (DESCRIPTION.replace("{huts}", HUTS.get(game, ""))
            .replace("{catchup}", CATCHUP.format(huts=", and so does the new-hut rule" if game in HUTS else ""))
            .replace("{share}", SHARE[game] + " so one choice is either all patched or all stock."
                     + HEALERS_EXTRA_ROLL.get(game, "")))


# Healers Study Plants Regardless of Food passes the shared roll and then makes its own
# two-in-three roll, so a studying healer continues half the time (the owner, v1.35.77).
HEALERS_EXTRA_ROLL = {
    "vv1": " Healers Study Plants Regardless of Food then adds its own two-in-three roll, so a studying healer carries on half the time.",
    "vv2": " Healers Study Plants Regardless of Food then adds its own two-in-three roll, so a studying healer carries on half the time.",
}


# The Building-level gates before the hut (A New Home, The Lost Children):
# below Building level 3 the stock Building branch gave up before the hut fix.
LEVEL_RUNTIME = {
    "vv1": {"va": "0x44765E", "stock_bytes": "8B9610E00300",
            "routine": "the Building dispatcher's level-3 gate before the hut (0x4472C0)"},
    "vv2": {"va": "0x4601F2", "stock_bytes": "83BA84EA0200030F8C4DFEFFFF",
            "routine": "the Building dispatcher's level-3 gate before the hut (0x45FBF0)"},
}

# The idle scheduler's food gates (see "Regardless of the food supply" in
# native/vvfp_fix_huts/vvfp_fix_huts.c).  VV3's is executable-side.
FOOD_RUNTIME = {
    "vv1": {"va": "0x448336", "stock_bytes": "81BDECA2000090010000" "7D2D",
            "routine": "the idle scheduler's 400-food gate (0x448220); with Builder Action Fixes, which owns the same bytes, selected too, its exact jmp E965E5000090909090909090 and cave at 0x4568A0 are verified and the jmp is pointed at the companion's equivalent of that cave, which asks the decision's roll"},
    "vv2": {"va": "0x4619E9", "stock_bytes": "81B9A4EA02002C010000" "7D2D",
            "routine": "the idle scheduler's 300-food gate (0x461850)"},
    "vv4": {"va": "0x4659B0", "stock_bytes": "8B8E881B0000",
            "routine": "the idle scheduler's low-food path, after the pick (0x465840)"},
    "vv5": {"va": "0x46F271", "stock_bytes": "8B8E881B0000",
            "routine": "the idle scheduler's low-food path, after the pick (0x46F070)"},
}
LEVEL_BEHAVIOR = {
    "vv1": "Below Building level 3 the stock Building branch gave up before the hut fix; now, at any food level, a builder fixes a built population hut whenever at least one is built and no other building project is available (every hut built included). And wherever A New Home's Building branch gives up (the 21% skip roll (rand(100) <= 20, 0x44772E), the level gate with no hut to fix, no hut standing) it reported 'started' with nothing started, leaving the builder on 'Nothing'; it now reports 'nothing started', so the villager goes on to other work.",
    "vv2": "Below Building level 3 the stock Building branch gave up before the hut fix; now, at any food level, a builder fixes a built population hut (never building 5) whenever at least one is built and no other building project is available (every hut built included).",
}
# Build first, fix last (the owner: builders "should build new stuff first,
# then fix huts"), and straight into it (the owner's option A: where a stock
# random roll says "not this time" but construction is available, the builder
# goes straight into that construction).  See "Build first, fix last" and
# "About three times in four" in the companion's source.
BUILD_FIRST_BEHAVIOR = {
    "vv1": "Construction always comes first: where the Building branch reaches the hut fix although it has a new hut to build (hut 9, or hut 10 or 11 once the player has worked on it or the population is above 22 / 45) or a started project open at this Building level -- after its 21% 'not this time' roll, or at the level-3 gate -- the builder goes straight into that construction through the branch's own code for it, and a hut is fixed only when there is nothing to build.",
    "vv2": "Construction always comes first: while the Building branch has a new hut to build or a project to start or continue -- the villager's own build task, project 1, hut 24, hut 25 or 26 once the player has worked on it, and the level-2 and level-3 projects -- with only its 79% rolls (rand(100) > 20) against it, a failed roll no longer leads to a hut fix (the companion's or the stock one): the builder goes straight into the first of them, in the branch's own order, through the branch's own code for it.",
    "vv3": "Construction always comes first: the stock 'fix a hut' option is taken out of any option list that also holds a hut to build or a project, so a builder fixes a hut only when there is no construction to choose. The Secret City's Building branch has no random roll that skips construction, so there is nothing to go straight into.",
    "vv4": "Construction always comes first: the stock 'fix a hut' option is taken out of any option list that also holds a hut to build or a project, and when the stock dislike roll takes a builder's construction options away (a builder with a certain dislike keeps each option only 16% of the time, rand(100) <= 15), the options it took are put back, by the branch's own tests and in its own order, and the stock pick goes straight into one of them; a hut is fixed only when there is no construction at all.",
    "vv5": "Construction always comes first: the stock 'fix a hut' option is taken out of any option list that also holds a hut to build or a project, and when the stock dislike roll takes a builder's construction options away (a builder with a certain dislike keeps each option only 16% of the time, rand(100) <= 15), the options it took are put back, by the branch's own tests and in its own order, and the stock pick goes straight into one of them; a hut is fixed only when there is no construction at all.",
}
# About three times in four, once per decision.
ROLL_BEHAVIOR = (
    "Every change above happens about three times in four, not always: each time the game's idle "
    "scheduler chooses what a villager does (one run of {sched}{loop}), one 75% roll from the "
    "companion's own generator -- never the game's random numbers -- decides whether the patches "
    "step in. If it passes, they act together; if it fails, every patched place runs the stock "
    "code for that choice, exactly as the unpatched game. The roll is drawn the first time a "
    "patched place asks and shared by every patch the choice reaches{share}."
)
ROLL_SCHED = {
    "vv1": ("0x448220", ""),
    "vv2": ("0x461850", ""),
    "vv3": ("0x45BFE0", ", including the choose-the-next-job routine's retries of it for the same villager (0x45C388, up to ten)"),
    "vv4": ("0x465840", ", including the choose-the-next-job routine's retries of it for the same villager (0x465B1A, up to ten)"),
    "vv5": ("0x46F070", ", including the choose-the-next-job routine's retries of it for the same villager (0x46F3DA, up to ten)"),
}
ROLL_SHARE = {
    "vv1": " -- Builders and Healers Work First, Healers Study Plants Regardless of Food and Builder Action Fixes included",
    "vv2": " -- Builders and Healers Work First and Healers Study Plants Regardless of Food included",
    "vv3": " -- Builders and Healers Work First included",
    "vv4": " -- Builders and Healers Work First included",
    "vv5": " -- Builders and Healers Work First included",
}
# The scheduler entries the companion wraps to open and close each decision.
SCHED_RUNTIME = {
    "vv1": {"va": "0x448220", "stock_bytes": "535556578B7C2414",
            "routine": "the idle scheduler's entry (0x448220): wrapped to open and close one decision"},
    "vv2": {"va": "0x461850", "stock_bytes": "535556578B7C2414",
            "routine": "the idle scheduler's entry (0x461850): wrapped to open and close one decision"},
    "vv4": {"va": "0x465840", "stock_bytes": "83EC08568BF1",
            "routine": "the idle scheduler's entry (0x465840): wrapped to open and close one decision"},
    "vv5": {"va": "0x46F070", "stock_bytes": "83EC085356",
            "routine": "the idle scheduler's entry (0x46F070): wrapped to open and close one decision"},
}
# The catch-up workers' entries, wrapped the same way: one worker call is one
# decision, so every patch the catch-up choice reaches shares one roll.
CU_RUNTIME = {
    "vv1": {"va": "0x42E790", "stock_bytes": "568B74240857",
            "routine": "the catch-up worker's entry (0x42E790): wrapped to open and close one decision"},
    "vv2": {"va": "0x43B4D0", "stock_bytes": "535657" "8B7C2410",
            "routine": "the catch-up worker's entry (0x43B4D0): wrapped to open and close one decision"},
    "vv4": {"va": "0x465750", "stock_bytes": "568BF1E808350000",
            "routine": "the catch-up worker's entry (0x465750): wrapped to open and close one decision"},
    "vv5": {"va": "0x46E8E0", "stock_bytes": "568BF1E8584B0000",
            "routine": "the catch-up worker's entry (0x46E8E0): wrapped to open and close one decision"},
}
CU_ROLL_BEHAVIOR = (
    "Catch-up -- time that passed while the game was closed, and Time Warp -- never runs the idle "
    "scheduler; its worker ({worker}) makes the choice instead, and one run of it is one decision "
    "too: the patches it reaches (this one's sites in the Building dispatcher, Builders and Healers "
    "Work First{healers}) share one 75% roll, never one each.{healers_extra}"
)
CU_WORKER = {"vv1": "0x42E790", "vv2": "0x43B4D0", "vv3": "0x45BF00", "vv4": "0x465750", "vv5": "0x46E8E0"}
FOOD_BEHAVIOR = (
    "Whenever a builder has hut work to do, its work attempt no longer depends "
    "on the food supply: {how}. Every other villager keeps the stock food "
    "behaviour."
)
FOOD_HOW = {
    "vv1": "at 400 food or more a villager whose selected job is Building still gets the preferred-job attempt the stock game gives below 400",
    "vv2": "at 300 food or more a villager whose selected job is Building still gets the preferred-job attempt the stock game gives below 300",
    "vv3": "at 250 food or less a picked Building job is dispatched at once instead of waiting behind a farming attempt and a 50% swap for a food action",
    "vv4": "at 250 food or less a picked Building job is dispatched at once instead of waiting behind a farming attempt and a 50% swap for a food action",
    "vv5": "at 250 food or less a picked Building job is dispatched at once instead of waiting behind a farming attempt and a 50% swap for a food action",
}

# ---- The addendum: Builders and Healers Work First (skill practice) --------
# The owner's skill-practice upgrade (v1.35.97, decisions of 2026-11-17 on
# "Skill Practice - Behaviors to Approve"): villagers practise their selected
# job on their own -- farmers, researchers, healers, builders and (New
# Believers) devotees; Parenting stays under the Birth Control patches.  See
# native/vvfp_work_first/vvfp_work_first.c.
WORK_FIRST_DLL = ROOT / "assets" / "work_first" / "VVFP Work First.dll"
WORK_FIRST_DESCRIPTION = (
    "Villagers practise their selected job on their own: about three times in four, each time the game "
    "chooses what a villager does, a villager whose selected job is Farming, Research, Healing or "
    "Building{devotion} first tries that job's own work, at any food level; the rest of the time, and "
    "whenever there is nothing of theirs to do, the game chooses exactly as it always has. The one roll is "
    "shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. What the "
    "work is -- which crop, project, patient or study -- is the game's own choice, with its own technology "
    "levels and buildings, so nothing starts that the game itself would not allow. Researchers never take "
    "the place of a farming attempt, and Parenting is left to the game and the Birth Control patches. "
    "**This patch never sends a builder to start a project nobody was ever dropped on; it only puts builders first to carry on work that was started**"
    "{builders} Healers{healers}{extra} This also applies during catch-up -- the time that passes while "
    "the game is closed, and Time Warp.{catch_up} An addendum to Builders Fix Huts When Idle. **Requires "
    "Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, a small stub in the page "
    "the Origins-exclusive base appends does); ticking this ticks it, and it brings with it the "
    "Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens."
)
WORK_FIRST_BUILDERS = {
    "vv1": (" (here a builder is put first only while there is hut work, and never while a population hut "
            "nobody has worked on could be started)."),
    "vv2": (" (here a builder is put first only while there is hut work, and never while the first population "
            "hut could be started by nobody's drop). A builder also sometimes examines the finished sewing hut, "
            "as they already examine the other huts (Building practice)."),
    "vv3": (". A builder with no building work to carry on does \"Doing exercise\" instead (Building "
            "practice), when the village has more than 250 food."),
    "vv4": (". A builder with no building work to carry on does \"Doing exercise\" instead (Building "
            "practice), when the village has more than 250 food. While the Building work could start puzzle "
            "work on its own -- the stream before The Stream is cleared, the piers before Fishing Nets, the "
            "rubble before the Cooking Pit -- builders are not put first; once The Stream is cleared, keeping "
            "it clear counts as building practice."),
    "vv5": (". A builder with no building work to carry on does \"Doing exercise\" instead (Building "
            "practice), when the village has more than 250 food."),
}
WORK_FIRST_HEALERS = {
    "vv1": (" heal the sick, or study plants: **before Herb Mastery is solved a healer with no patient studies "
            "the medical cactus only if you dropped them on it, unless Easier Healing Mastery is also selected**; "
            "once Herb Mastery is solved, a healer with nothing else to do studies any of the four herbs on their "
            "own (the Magic Plant of Life is never studied this way)."),
    "vv2": (" heal the sick, or study plants: **before Herb Mastery is solved a healer with no patient studies a "
            "plant only if you dropped them on one, unless Easier Healing Mastery is also selected**; once Herb "
            "Mastery is solved, a healer with nothing else to do studies any of the six plants on their own."),
    "vv3": " heal the sick, or study medicine once Medicine 2 has been researched.",
    "vv4": " heal the sick, or study medicine once the Hospital has been built.",
    "vv5": " heal the sick, or study medicine once the Pain Totem has been dismantled.",
}
WORK_FIRST_EXTRA = {
    "vv1": "",
    "vv2": "",
    "vv3": "",
    "vv4": (" Beginners practise too: the game never sent a villager to their selected job while that skill was 5 "
            "or less; now they go on the game's own terms (skill + 40 times in 100). In catch-up a farmer may also "
            "make the fruit trip, \"Attempting to retrieve fruit\", once the Cooking Pit is restored, as they do "
            "while you play."),
    "vv5": (" Beginners practise too: the game never sent a villager to their selected job while that skill was 5 "
            "or less; now they go on the game's own terms (skill + 40 times in 100). A new villager is no longer "
            "held back by the game's \"untrained\" mark for their selected job (only that job: mating and every "
            "other job still wait for training, as in the game). In catch-up a farmer may also harvest noni "
            "before the Hungry Totem is dismantled, as a farmer you dropped there already does."),
}
WORK_FIRST_CATCH_UP_FARMING = (
    " Catch-up's low-food rule still wins: at 250 food or less a villager with Farming 20 or more farms, "
    "whatever their job."
)
WORK_FIRST_DEVOTION = {
    "vv5": (", or Devotion (Devotion while you play only when Easier Devotee Training is not selected, so the two "
            "never double up)"),
}
# The catch-up worker per game: the worker, its pick dispatch (and the return
# the dispatcher hook recognises), and the low-food Farming call (VV3-VV5).
CATCH_UP = {
    "vv1": dict(worker="0x42E790", call="0x42E81C", ret="0x42E821"),
    "vv2": dict(worker="0x43B4D0", call="0x43B583", ret="0x43B588"),
    "vv3": dict(worker="0x45BF00", call="0x45BFC0", ret="0x45BFC5", farm="0x45BFAB"),
    "vv4": dict(worker="0x465750", call="0x465827", ret="0x46582C", farm="0x46580A"),
    "vv5": dict(worker="0x46E8E0", call="0x46E9C9", ret="0x46E9CE", farm="0x46E9AC"),
}
JOB_NUMBERS = {
    "vv1": dict(farming=1, parenting=2, research=3, building=4, healing=5),
    "vv2": dict(farming=1, parenting=2, healing=3, research=4, building=5),
    "vv3": dict(farming=0, parenting=1, healing=2, research=3, building=4),
    "vv4": dict(farming=0, parenting=1, healing=2, research=3, building=4),
    "vv5": dict(farming=0, parenting=1, healing=2, research=3, building=4, devotion=5),
}
PICKER_RUNTIME = {
    "vv1": [{"va": "0x4472C0", "stock_bytes": "8B44240885C0",
             "routine": "the work dispatcher's entry, acting only for the adult scheduler's calls (returns 0x448355, 0x448382) and the catch-up worker's pick dispatch (0x42E821)"}],
    "vv2": [{"va": "0x45FBF0", "stock_bytes": "8B44240885C0",
             "routine": "the work dispatcher's entry, acting only for the adult scheduler's calls (returns 0x461A08, 0x461A35) and the catch-up worker's pick dispatch (0x43B588)"},
            {"va": "0x4602B0", "stock_bytes": "6A04E8E92EFAFF",
             "routine": "the Building case's examine pick (push 4; call rand): once the sewing hut is finished, on the decision's roll, one time in five it examines the sewing hut (0x45F7C0(index, 7)); otherwise the stock rand(4) runs"}],
    "vv4": [{"va": "0x4639B0", "stock_bytes": "8B44240481EC98000000",
             "routine": "the work dispatcher's entry, acting only for the adult scheduler's calls (returns 0x4659D2, 0x465A17, 0x465A2A) and the catch-up worker's pick dispatch (0x46582C)"},
            {"va": "0x461E69", "stock_bytes": "83FE057E46",
             "routine": "the job picker's skill gate (cmp esi, 5; jle fail): at skill 5 or less the villager's selected job (never Parenting) goes on to the stock rand(100) < skill + 40 on the decision's roll"},
            {"va": "0x463A30", "stock_bytes": "3898A4710100750B",
             "routine": "the Farming case's catch-up test before the fruit trip (cmp byte [game+0x171A4], bl; jne): in catch-up a villager whose selected job is Farming is offered the fruit trip on the decision's roll"}],
    "vv5": [{"va": "0x46C540", "stock_bytes": "81EC94000000",
             "routine": "the work dispatcher's entry, acting only for the adult scheduler's calls (returns 0x46F291, 0x46F2D6, 0x46F2EA) and the catch-up worker's pick dispatch (0x46E9CE)"},
            {"va": "0x46A594", "stock_bytes": "83FE057E46",
             "routine": "the job picker's skill gate (cmp esi, 5; jle fail): at skill 5 or less the villager's selected job (never Parenting) goes on to the stock rand(100) < skill + 40 on the decision's roll"},
            {"va": "0x46C5CA", "stock_bytes": "3898107E01007506",
             "routine": "the Farming case's catch-up test before noni (cmp byte [game+0x17E10], bl; jne): in catch-up a villager whose selected job is Farming is offered noni on the decision's roll, before the Hungry Totem as a dropped farmer already is"}],
}


def work_first_description(game: str) -> str:
    catch_up = WORK_FIRST_CATCH_UP_FARMING if "farm" in CATCH_UP[game] else ""
    return (WORK_FIRST_DESCRIPTION
            .replace("{devotion}", WORK_FIRST_DEVOTION.get(game, ""))
            .replace("{builders}", WORK_FIRST_BUILDERS[game])
            .replace("{healers}", WORK_FIRST_HEALERS[game])
            .replace("{extra}", WORK_FIRST_EXTRA[game])
            .replace("{catch_up}", catch_up))


def work_first_row(game: str, sha: str) -> dict:
    jobs = JOB_NUMBERS[game]
    cu = CATCH_UP[game]
    jobs_text = ", ".join(f"{name.capitalize()} {number}" for name, number in jobs.items())
    behavior = [
        f"Whenever the adult scheduler (or the catch-up worker's pick dispatch, {cu['call']} returning to {cu['ret']}) asks the work dispatcher to start a job, for a villager whose selected job is Farming, Research, Healing or Building{' or Devotion' if game == 'vv5' else ''} ({jobs_text}), the dispatcher is first asked for that villager's own job; if that starts something the caller sees it started, and if there is nothing of theirs to do the caller's own request runs unchanged. Parenting is never put first. Research never displaces a Farming request.",
        "About three times in four, not always: the companion asks the decision's roll that Builders Fix Huts When Idle draws once per choice of the idle scheduler and once per run of the catch-up worker (VvfpFixHutsRoll, handed over through VvfpWorkFirstSetRoll, or looked up by module name in The Secret City); when it fails, the caller's own request runs alone, exactly as the stock game.",
        "Builders never start a project nobody was dropped on: " + {
            "vv1": "a builder is put first only while it has hut work (a population hut unbuilt, or below Building level 3 any hut built) and no hut the stock Building case could start on its own is still below progress 2 (hut 9 any time, huts 10 / 11 above 22 / 45 villagers; progress [state+0x9F9C+8*id], 1 is the drawing routine's scaffold mark).",
            "vv2": "a builder is put first only while it has hut work (a population hut unbuilt, or below Building level 3 any hut built) and hut 24, which the stock Building case starts on its own, is done or has progress 2 or more ([state+0x2E814]).",
            "vv3": "The Secret City's Building case only continues projects above 0%, so a builder is always put first.",
            "vv4": "a builder is put first only while the Building case offers no puzzle work it can start by itself: the stream (0x430FD0 on 0x4D8CF0 between 1 and 97) while The Stream (project 1) is unsolved, the piers (0x4396D0 on 0x4D86A8 below 2 and 0x421570 below 100), the rubble (0x4396D0 on 0x4D8720 at 0 and [0x4D8A8C] below 100). Its construction only continues projects above 0%.",
            "vv5": "New Believers' Building case only continues projects above 0%, so a builder is always put first.",
        }[game],
    ]
    if game in ("vv3", "vv4", "vv5"):
        ex = {"vv3": ("0x455570", "0x96", "0x582490", "record+0xF24"),
              "vv4": ("0x45DEC0", "0x47", "0x4D6DD0", "record+0x1CE0"),
              "vv5": ("0x465580", "0x4E", "0x51D34C", "record+0x1D10")}[game]
        behavior.append(f"Exercise: when a builder's Building work started nothing (including when Building was the caller's own request, which the companion then dispatches itself on the roll), the food total [{ex[2]}] is above 250 and the villager's current action ({ex[3]}) did not change, the companion starts the game's own \"Doing exercise\" (do-action {ex[0]}, action {ex[1]}), whose step raises Building through the standard practice roll.")
    if game in ("vv1", "vv2"):
        plants = ("medical cactus 0x443270, rare rose 0x4435B0, strange lily 0x443440, strange plant 0x443720 -- never the Magic Plant of Life (0x443030); solved flag [state+0xA080]; trait test 0x4372E0(index, 0xB) for the rose, lily and plant, as the drop makes; a villager whose last activity is 9 (the Healing case already started the cactus) is left alone"
                  if game == "vv1" else
                  "herbs 1-6, 0x458CD0, 0x4589A0, 0x458B70, 0x458E30, 0x458FD0, 0x459130; solved flag [state+0x2E788]; trait test 0x4454E0(index, 0xB), as the drop makes")
        behavior.append(f"Plants: once Herb Mastery is solved, a healer whose Healing work started nothing studies a random understood plant through the game's own starter ({plants}); a re-study's step is the stock Healing practice roll.")
    if game == "vv5":
        behavior.append("Devotion (job 5) is put first like Healing: in catch-up always; while you play only when Easier Devotee Training's bytes are not at 0x46F1DD (stock 83B9FC1C00000D7554), so the two never double up. The dispatcher's Devotion case (0x46CDB6) queues Honoring when project 14 is complete or 0x4271C0 answers 1 or 2, and otherwise starts nothing.")
        behavior.append("Untrained: every new villager starts with [record+0x1C54] = 1, which the dispatcher refuses (0x46C565). For the scheduler's and the catch-up worker's calls, a request for the villager's selected job (never Parenting) is dispatched with the mark set to 0 for that call and put back to 1 afterwards if it is still 0 (a refusal inside the call writes 0).")
    if game in ("vv3", "vv4", "vv5"):
        behavior.append("At 250 food or less a healer's pick is also dispatched at once instead of waiting behind a farming attempt, as Builders Fix Huts When Idle already does for builders.")
    non_changes_catch_up = (
        f"In catch-up, the worker's low-food Farming dispatch ({cu['farm']}: 250 food or less and Farming 20 or more) is not one of the calls the hook acts on, so Farming wins exactly as in the stock game."
        if "farm" in cu else
        "In catch-up, only the worker's own pick dispatch reaches the hook; nothing else in the worker changes.")
    row = {
        "id": f"{game}_builders_and_healers_work_first",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": "Builders and Healers Work First",
        "description": work_first_description(game),
        "output_tag": "Work First",
        "dependencies": [f"{game}_builders_fix_huts"],
        "behavior_changes": behavior,
        "explicit_non_changes": [
            "A villager with nothing of their own to do does whatever the stock scheduler chose; the younger villagers' routine, every other caller of the dispatcher and a villager with no selected job are untouched.",
            "Parenting (job %d) is never put first, and the catch-up worker's Parenting pick (its 5%% conception attempt) is not touched: births stay under the Birth Control patches." % jobs["parenting"],
            "What the work does -- which crop, project, hut, patient or study -- is the game's own dispatcher's choice, with its technology levels and buildings; the Farming cases start no tool or sack job (those stay drop-only) and no puzzle work.",
            non_changes_catch_up,
            "Nothing is written to the save or any file." + (" The only record write is New Believers' untrained mark, lifted for one dispatch and put back." if game == "vv5" else ""),
        ],
        "companion_files": [
            {"source": "assets/work_first/VVFP Work First.dll",
             "destination": "VVFP Work First.dll", "sha256": sha},
        ],
        "patches": [],
    }
    if game in PICKER_RUNTIME:
        row["explicit_non_changes"].insert(0,
            "This row changes no executable bytes: the fix-huts companion loads the DLL, which detours the sites below at run time, all of them or none, only after verifying the stock bytes; a different build of the game installs nothing.")
        row["runtime_detours"] = [
            {**site, "installed_by": "VVFP Work First.dll, VvfpWorkFirstInstall"} for site in PICKER_RUNTIME[game]
        ]
    else:
        row["explicit_non_changes"].insert(0,
            "This row changes no executable bytes: The Secret City's hook is the dispatcher stub that Builders Fix Huts When Idle places in the page Origins appends, which resolves this DLL's VvfpWorkFirstFirst itself; without this row the DLL is not shipped and the stub runs the stock code.")
    return row


RUNTIME = {
    "vv1": {"va": "0x447724", "stock_bytes": "6A64E8E5B7FBFF83C404",
            "routine": "the Building dispatcher's skip roll before the random hut (0x4472C0)"},
    "vv2": {"va": "0x46029D", "stock_bytes": "6A64E8FC2EFAFF83C404",
            "routine": "the Building dispatcher's skip roll before the random hut (0x45FBF0)"},
    "vv4": {"va": "0x463F8A", "stock_bytes": "3BFB0F8469010000",
            "routine": "the Building dispatcher's empty-option-list test (0x4639B0)"},
    "vv5": {"va": "0x46CADA", "stock_bytes": "3BFB0F8415030000",
            "routine": "the Building dispatcher's empty-option-list test (0x46C540)"},
}

# ---- The Secret City ------------------------------------------------------
VV3_SITE_VA = 0x45B39E
VV3_SITE_FILE = VV3_SITE_VA - 0x400000
VV3_SITE_STOCK = bytes.fromhex("3BFB0F849C030000")   # cmp edi, ebx; je 0x45B742
VV3_NOTHING = 0x45B742
VV3_RESUME = 0x45B3A6
VV3_STARTED = 0x45B5F0
VV3_LOAD_LIBRARY_IAT = 0x47C124
VV3_GET_MODULE_HANDLE_IAT = 0x47C074
VV3_GET_PROC_ADDRESS_IAT = 0x47C128
VV3_CACHE_SLOT = 0x6E0FF8          # .vv3md (R/W), unused by Origins and parentage
VV3_DLL_NAME = b"VVFP Fix Huts.dll\0"
VV3_EXPORT_NAME = b"VvfpFixHutsFilter\0"
VV3_LIST_OFFSET = 0x64             # the dispatcher's option list, [esp+0x64] at the site
VV3_NAME_OFFSET = 0x80
VV3_EXPORT_OFFSET = 0xA0

# "Regardless of the food supply": at 250 food or less The Secret City's idle
# scheduler makes the pick (ebx) wait behind a farming attempt and then,
# half the time, swaps it for a food action.  The farming test at 0x45C229
# (cmp [esi+0xEAC], 20; jl 0x45C244) jumps to a second stub, which asks the
# companion's VvfpFixHutsBuilderFirst(3, pick): a Building pick always (and a
# Healing pick while "VVFP Work First.dll" is shipped) goes straight to the
# stock dispatch-with-pick at 0x45C271 -- the companion makes no hut check,
# since a builder here always has hut work; anything else replays the test.  With the DLL missing the stock
# test runs.
VV3_FOOD_SITE_VA = 0x45C229
VV3_FOOD_SITE_FILE = VV3_FOOD_SITE_VA - 0x400000
VV3_FOOD_SITE_STOCK = bytes.fromhex("83BEAC0E0000147C12")   # cmp [esi+0xEAC], 0x14; jl 0x45C244
VV3_FOOD_FARM = 0x45C232          # the jl not taken: try farming
VV3_FOOD_SKIP = 0x45C244          # the jl taken: skill below 20
VV3_FOOD_DISPATCH = 0x45C271      # push ebx; push esi; mov ecx, edi; call dispatcher
VV3_FOOD_CACHE_SLOT = 0x6E0FFC    # .vv3md; fix-huts 0x6E0FF8, lesson-cap 0x6E0FF4
VV3_FOOD_EXPORT_NAME = b"VvfpFixHutsBuilderFirst\0"
VV3_FOOD_EXPORT_OFFSET = 0xC0
VV3_FOOD_CODE_OFFSET = 0x100

# The hook for the addendum row "Builders and Healers Work First": the work
# dispatcher's entry (0x45AF00: mov eax, [esp+8]; sub esp, 0xA0) jumps to a
# third stub, which resolves "VVFP Work First.dll"'s VvfpWorkFirstFirst(3,
# caller, record, job).  A job number back means: ask the stock dispatcher for
# that job first (the villager's own Building or Healing work); if it starts
# something, return "started" (ret 8); otherwise, and for -1, the stock
# request runs through the displaced bytes.  The addendum acts only for the
# adult scheduler's three call sites and only while a population hut is
# unbuilt.  The Secret City has no per-frame companion, so the hook lives in
# this row's page; with the addendum's DLL not shipped the resolution fails
# once, is remembered, and the stock dispatcher runs.
VV3_PICKER_VA = 0x45AF00
VV3_PICKER_FILE = VV3_PICKER_VA - 0x400000
VV3_PICKER_STOCK = bytes.fromhex("8B44240881ECA0000000")   # mov eax, [esp+8]; sub esp, 0xA0
VV3_PICKER_BODY = 0x45AF0A
VV3_PRIORITY_CACHE_SLOT = 0x6E0FF0
VV3_PRIORITY_EXPORT_NAME = b"VvfpWorkFirstFirst\0"
VV3_WORK_FIRST_DLL_NAME = b"VVFP Work First.dll\0"
VV3_WORK_FIRST_NAME_OFFSET = 0x1A0
VV3_PRIORITY_EXPORT_OFFSET = 0x1C0
VV3_PRIORITY_CODE_OFFSET = 0x200

# The catch-up worker's `cmp ebx, 1; jne` at 0x45BF52 is its Parenting pick
# (5% of the time a catch-up conception attempt), not research: an earlier
# version diverted it into a stub that gave builders and healers their own
# job instead.  Parenting stays under the Birth Control patches, so it is no
# longer touched (native/vvfp_work_first/vvfp_work_first.c, CATCH-UP).

# About three times in four, once per decision (see "About three times in
# four" in native/vvfp_fix_huts/vvfp_fix_huts.c): the companion wraps each
# game's idle scheduler so every patch in one decision shares one 75% roll.
# The Secret City's scheduler entry (0x45BFE0: push ecx; push esi; mov esi,
# [esp+0xC]) jumps to a fourth stub, which resolves the companion's
# VvfpFixHutsScheduler3 once and jumps to it with the stack and every
# register untouched; the companion runs the displaced bytes and the stock
# scheduler inside the decision.  With the DLL missing, the stub runs the
# displaced bytes and the stock scheduler.
VV3_SCHED_VA = 0x45BFE0
VV3_SCHED_FILE = VV3_SCHED_VA - 0x400000
VV3_SCHED_STOCK = bytes.fromhex("51568B74240C")   # push ecx; push esi; mov esi, [esp+0xC]
VV3_SCHED_BODY = 0x45BFE6
VV3_SCHED_CACHE_SLOT = 0x6E0FEC    # .vv3md; work-first 0x6E0FF0, lesson-cap 0x6E0FF4
VV3_SCHED_EXPORT_NAME = b"VvfpFixHutsScheduler3\0"
VV3_SCHED_CODE_OFFSET = 0x300
VV3_SCHED_EXPORT_OFFSET = 0x3C0

# One roll per catch-up decision too (see "The decision in catch-up" in
# native/vvfp_fix_huts/vvfp_fix_huts.c): the catch-up worker's entry
# (0x45BF00: push esi; mov esi, [esp+8]; push edi) jumps to a sixth stub,
# which resolves the companion's VvfpFixHutsCatchUp3 once and jumps to it with
# the stack and every register untouched; the companion opens a decision, runs
# the displaced bytes and the stock worker, and closes it.  Without the DLL
# the stub runs the displaced bytes and the stock worker.
VV3_CU_VA = 0x45BF00
VV3_CU_FILE = VV3_CU_VA - 0x400000
VV3_CU_STOCK = bytes.fromhex("568B74240857")   # push esi; mov esi, [esp+8]; push edi
VV3_CU_BODY = 0x45BF06
VV3_CU_CACHE_SLOT = 0x6E0FE8       # .vv3md; scheduler 0x6E0FEC, work-first 0x6E0FF0
VV3_CU_EXPORT_NAME = b"VvfpFixHutsCatchUp3\0"
VV3_CU_CODE_OFFSET = 0x360
VV3_CU_EXPORT_OFFSET = 0x3D8

# Origins' appended pages: .vv3mc (R-X) at 0x6DF000 / file 0xCB000, whose own
# content ends at 0x3A0; the parentage overlay takes 0x400..0x800; this one
# takes 0x800..0xC00.
VV3_OVERLAY_FILE = 0xCB800
VV3_OVERLAY_VA = 0x6DF800
VV3_OVERLAY_LENGTH = 0x400
VV3_ORIGINS_ID = "vv3_enable_origins_exclusive_features"

# The standalone form (never selected: the row depends on Origins), shaped like
# the parentage row's: an owned executable section at the stock EOF.
VV3_STOCK_FILE_SIZE = 0xCB000
VV3_PAGE_FILE = 0xCB000
VV3_PAGE_VA = 0x6DF000
VV3_PAGE_SIZE = 0x1000
VV3_SECTION_NAME = b".vv3fh\0\0"


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoding, _ = engine.asm(source, address)
    return bytes(encoding)


def vv3_build_page(base_va: int) -> bytes:
    """The stub, re-assembled for the address it will live at."""
    name_va = base_va + VV3_NAME_OFFSET
    export_va = base_va + VV3_EXPORT_OFFSET
    # Build first, fix last: the companion's VvfpFixHutsFilter(3, esi, list,
    # count) sees every option list, drops the stock "fix a hut" option 9
    # from a list that holds construction, and on an empty list may start a
    # hut fix (-1).  Its answer replaces edi before the stock test.
    code = assemble(
        f"""
        pushad
        mov eax, dword ptr [0x{VV3_CACHE_SLOT:X}]
        cmp eax, 1
        ja call_it
        je give_up
        push 0x{name_va:X}
        call dword ptr [0x{VV3_GET_MODULE_HANDLE_IAT:X}]
        test eax, eax
        jne have_module
        push 0x{name_va:X}
        call dword ptr [0x{VV3_LOAD_LIBRARY_IAT:X}]
        test eax, eax
        je mark_failed
    have_module:
        push 0x{export_va:X}
        push eax
        call dword ptr [0x{VV3_GET_PROC_ADDRESS_IAT:X}]
        test eax, eax
        je mark_failed
        mov dword ptr [0x{VV3_CACHE_SLOT:X}], eax
    call_it:
        lea ecx, [esp + 0x{0x20 + VV3_LIST_OFFSET:X}]
        push edi
        push ecx
        push esi
        push 3
        call eax
        add esp, 16
        cmp eax, -1
        je started
        mov dword ptr [esp], eax
        jmp give_up
    mark_failed:
        mov dword ptr [0x{VV3_CACHE_SLOT:X}], 1
    give_up:
        popad
        cmp edi, ebx
        je 0x{VV3_NOTHING:X}
        jmp 0x{VV3_RESUME:X}
    started:
        popad
        jmp 0x{VV3_STARTED:X}
        """,
        base_va,
    )
    if len(code) > VV3_NAME_OFFSET:
        raise RuntimeError(f"the VV3 stub is {len(code):#x} bytes, past its string at {VV3_NAME_OFFSET:#x}")
    page = bytearray(VV3_PAGE_SIZE)
    page[: len(code)] = code
    page[VV3_NAME_OFFSET : VV3_NAME_OFFSET + len(VV3_DLL_NAME)] = VV3_DLL_NAME
    page[VV3_EXPORT_OFFSET : VV3_EXPORT_OFFSET + len(VV3_EXPORT_NAME)] = VV3_EXPORT_NAME
    food_va = base_va + VV3_FOOD_CODE_OFFSET
    food = assemble(
        f"""
        pushad
        mov eax, dword ptr [0x{VV3_FOOD_CACHE_SLOT:X}]
        cmp eax, 1
        ja call_it
        je give_up
        push 0x{name_va:X}
        call dword ptr [0x{VV3_GET_MODULE_HANDLE_IAT:X}]
        test eax, eax
        jne have_module
        push 0x{name_va:X}
        call dword ptr [0x{VV3_LOAD_LIBRARY_IAT:X}]
        test eax, eax
        je mark_failed
    have_module:
        push 0x{base_va + VV3_FOOD_EXPORT_OFFSET:X}
        push eax
        call dword ptr [0x{VV3_GET_PROC_ADDRESS_IAT:X}]
        test eax, eax
        je mark_failed
        mov dword ptr [0x{VV3_FOOD_CACHE_SLOT:X}], eax
    call_it:
        push ebx
        push 3
        call eax
        add esp, 8
        test eax, eax
        popad
        jne 0x{VV3_FOOD_DISPATCH:X}
        jmp stock
    mark_failed:
        mov dword ptr [0x{VV3_FOOD_CACHE_SLOT:X}], 1
    give_up:
        popad
    stock:
        cmp dword ptr [esi + 0xEAC], 0x14
        jl 0x{VV3_FOOD_SKIP:X}
        jmp 0x{VV3_FOOD_FARM:X}
        """,
        food_va,
    )
    page[VV3_FOOD_EXPORT_OFFSET : VV3_FOOD_EXPORT_OFFSET + len(VV3_FOOD_EXPORT_NAME)] = VV3_FOOD_EXPORT_NAME
    if VV3_FOOD_EXPORT_OFFSET + len(VV3_FOOD_EXPORT_NAME) > VV3_FOOD_CODE_OFFSET:
        raise RuntimeError("the food export name runs into the food stub")
    page[VV3_FOOD_CODE_OFFSET : VV3_FOOD_CODE_OFFSET + len(food)] = food
    if VV3_FOOD_CODE_OFFSET + len(food) > VV3_WORK_FIRST_NAME_OFFSET:
        raise RuntimeError("the food stub runs into the Work First DLL name")
    priority_va = base_va + VV3_PRIORITY_CODE_OFFSET
    work_first_name_va = base_va + VV3_WORK_FIRST_NAME_OFFSET
    priority = assemble(
        f"""
        pushad
        mov eax, dword ptr [0x{VV3_PRIORITY_CACHE_SLOT:X}]
        cmp eax, 1
        ja call_it
        je give_up
        push 0x{work_first_name_va:X}
        call dword ptr [0x{VV3_GET_MODULE_HANDLE_IAT:X}]
        test eax, eax
        jne have_module
        push 0x{work_first_name_va:X}
        call dword ptr [0x{VV3_LOAD_LIBRARY_IAT:X}]
        test eax, eax
        je mark_failed
    have_module:
        push 0x{base_va + VV3_PRIORITY_EXPORT_OFFSET:X}
        push eax
        call dword ptr [0x{VV3_GET_PROC_ADDRESS_IAT:X}]
        test eax, eax
        je mark_failed
        mov dword ptr [0x{VV3_PRIORITY_CACHE_SLOT:X}], eax
    call_it:
        push dword ptr [esp + 0x18]
        push dword ptr [esp + 0x2C]
        push dword ptr [esp + 0x2C]
        push dword ptr [esp + 0x2C]
        push 3
        call eax
        add esp, 20
        cmp eax, -2
        je started
        cmp eax, -3
        je nothing
        popad
        jmp original
    started:
        popad
        mov al, 1
        ret 8
    nothing:
        popad
        xor al, al
        ret 8
    mark_failed:
        mov dword ptr [0x{VV3_PRIORITY_CACHE_SLOT:X}], 1
    give_up:
        popad
    original:
        mov eax, dword ptr [esp + 8]
        sub esp, 0xA0
        jmp 0x{VV3_PICKER_BODY:X}
        """,
        priority_va,
    )
    page[VV3_WORK_FIRST_NAME_OFFSET : VV3_WORK_FIRST_NAME_OFFSET + len(VV3_WORK_FIRST_DLL_NAME)] = VV3_WORK_FIRST_DLL_NAME
    if VV3_WORK_FIRST_NAME_OFFSET + len(VV3_WORK_FIRST_DLL_NAME) > VV3_PRIORITY_EXPORT_OFFSET:
        raise RuntimeError("the Work First DLL name runs into the export name")
    page[VV3_PRIORITY_EXPORT_OFFSET : VV3_PRIORITY_EXPORT_OFFSET + len(VV3_PRIORITY_EXPORT_NAME)] = VV3_PRIORITY_EXPORT_NAME
    page[VV3_PRIORITY_CODE_OFFSET : VV3_PRIORITY_CODE_OFFSET + len(priority)] = priority
    if VV3_PRIORITY_CODE_OFFSET + len(priority) > VV3_SCHED_CODE_OFFSET:
        raise RuntimeError("the work-first stub runs into the scheduler stub")
    sched = assemble(
        f"""
        cmp dword ptr [0x{VV3_SCHED_CACHE_SLOT:X}], 1
        ja go
        je stock
        pushad
        push 0x{name_va:X}
        call dword ptr [0x{VV3_GET_MODULE_HANDLE_IAT:X}]
        test eax, eax
        jne have_module
        push 0x{name_va:X}
        call dword ptr [0x{VV3_LOAD_LIBRARY_IAT:X}]
        test eax, eax
        je mark_failed
    have_module:
        push 0x{base_va + VV3_SCHED_EXPORT_OFFSET:X}
        push eax
        call dword ptr [0x{VV3_GET_PROC_ADDRESS_IAT:X}]
        test eax, eax
        je mark_failed
        mov dword ptr [0x{VV3_SCHED_CACHE_SLOT:X}], eax
        popad
    go:
        jmp dword ptr [0x{VV3_SCHED_CACHE_SLOT:X}]
    mark_failed:
        mov dword ptr [0x{VV3_SCHED_CACHE_SLOT:X}], 1
        popad
    stock:
        push ecx
        push esi
        mov esi, dword ptr [esp + 0xC]
        jmp 0x{VV3_SCHED_BODY:X}
        """,
        base_va + VV3_SCHED_CODE_OFFSET,
    )
    page[VV3_SCHED_CODE_OFFSET : VV3_SCHED_CODE_OFFSET + len(sched)] = sched
    if VV3_SCHED_CODE_OFFSET + len(sched) > VV3_CU_CODE_OFFSET:
        raise RuntimeError("the scheduler stub runs into the catch-up stub")
    catch_up = assemble(
        f"""
        cmp dword ptr [0x{VV3_CU_CACHE_SLOT:X}], 1
        ja go
        je stock
        pushad
        push 0x{name_va:X}
        call dword ptr [0x{VV3_LOAD_LIBRARY_IAT:X}]
        test eax, eax
        je mark_failed
        push 0x{base_va + VV3_CU_EXPORT_OFFSET:X}
        push eax
        call dword ptr [0x{VV3_GET_PROC_ADDRESS_IAT:X}]
        test eax, eax
        je mark_failed
        mov dword ptr [0x{VV3_CU_CACHE_SLOT:X}], eax
        popad
    go:
        jmp dword ptr [0x{VV3_CU_CACHE_SLOT:X}]
    mark_failed:
        mov dword ptr [0x{VV3_CU_CACHE_SLOT:X}], 1
        popad
    stock:
        push esi
        mov esi, dword ptr [esp + 8]
        push edi
        jmp 0x{VV3_CU_BODY:X}
        """,
        base_va + VV3_CU_CODE_OFFSET,
    )
    page[VV3_CU_CODE_OFFSET : VV3_CU_CODE_OFFSET + len(catch_up)] = catch_up
    if VV3_CU_CODE_OFFSET + len(catch_up) > VV3_SCHED_EXPORT_OFFSET:
        raise RuntimeError("the catch-up stub runs into the scheduler export name")
    page[VV3_SCHED_EXPORT_OFFSET : VV3_SCHED_EXPORT_OFFSET + len(VV3_SCHED_EXPORT_NAME)] = VV3_SCHED_EXPORT_NAME
    if VV3_SCHED_EXPORT_OFFSET + len(VV3_SCHED_EXPORT_NAME) > VV3_CU_EXPORT_OFFSET:
        raise RuntimeError("the scheduler export name runs into the catch-up export name")
    page[VV3_CU_EXPORT_OFFSET : VV3_CU_EXPORT_OFFSET + len(VV3_CU_EXPORT_NAME)] = VV3_CU_EXPORT_NAME
    if any(page[VV3_OVERLAY_LENGTH:]):
        raise RuntimeError("the VV3 stub must fit in the 0x400 overlay")
    return bytes(page)


def vv3_site_patch(page_va: int) -> dict:
    entry = b"\xE9" + int(page_va - (VV3_SITE_VA + 5)).to_bytes(4, "little", signed=True)
    entry += b"\x90" * (len(VV3_SITE_STOCK) - len(entry))
    return {
        "offset": f"0x{VV3_SITE_FILE:X}",
        "before": VV3_SITE_STOCK.hex().upper(),
        "after": entry.hex().upper(),
        "purpose": (
            "Divert the Building dispatcher's option-list test (cmp edi, ebx; "
            "je nothing at 0x45B39E) into the fix-huts stub, which hands the option "
            "list to the companion's VvfpFixHutsFilter -- the stock 'fix a hut' "
            "option is dropped from a list that holds construction, and an empty "
            "list may start a hut fix -- then replays the test on the answer and "
            "resumes at the stock pick, 'job started' or 'nothing' path."
        ),
    }


def vv3_food_site_patch(page_va: int) -> dict:
    target = page_va + VV3_FOOD_CODE_OFFSET
    entry = b"\xE9" + int(target - (VV3_FOOD_SITE_VA + 5)).to_bytes(4, "little", signed=True)
    entry += b"\x90" * (len(VV3_FOOD_SITE_STOCK) - len(entry))
    return {
        "offset": f"0x{VV3_FOOD_SITE_FILE:X}",
        "before": VV3_FOOD_SITE_STOCK.hex().upper(),
        "after": entry.hex().upper(),
        "purpose": (
            "Divert the idle scheduler's low-food farming test (cmp [esi+0xEAC], 20; "
            "jl at 0x45C229) into the food stub, which asks the companion's "
            "VvfpFixHutsBuilderFirst whether to send the pick straight to the stock "
            "dispatch-with-pick -- always for a Building pick, and for a Healing pick "
            "while \"VVFP Work First.dll\" is shipped; there is no hut check, because "
            "a builder always has hut work (fixing an unbuilt hut, or the stock "
            "fix-a-hut option once every one is built) -- and otherwise replays the "
            "test."
        ),
    }


def vv3_picker_site_patch(page_va: int) -> dict:
    target = page_va + VV3_PRIORITY_CODE_OFFSET
    entry = b"\xE9" + int(target - (VV3_PICKER_VA + 5)).to_bytes(4, "little", signed=True)
    entry += b"\x90" * (len(VV3_PICKER_STOCK) - len(entry))
    return {
        "offset": f"0x{VV3_PICKER_FILE:X}",
        "before": VV3_PICKER_STOCK.hex().upper(),
        "after": entry.hex().upper(),
        "purpose": (
            "Divert the work dispatcher's entry (mov eax, [esp+8]; sub esp, 0xA0 at "
            "0x45AF00) into the work-first stub for the Builders and Healers Work First "
            "addendum, which resolves \"VVFP Work First.dll\" and asks its "
            "VvfpWorkFirstFirst (the caller, record, job and ecx): -2 returns 'started', "
            "-3 'nothing started' (the companion ran the request itself), and otherwise "
            "-- or without that DLL -- the stock request runs through the displaced bytes."
        ),
    }


def vv3_cu_site_patch(page_va: int) -> dict:
    target = page_va + VV3_CU_CODE_OFFSET
    entry = b"\xE9" + int(target - (VV3_CU_VA + 5)).to_bytes(4, "little", signed=True)
    entry += b"\x90" * (len(VV3_CU_STOCK) - len(entry))
    return {
        "offset": f"0x{VV3_CU_FILE:X}",
        "before": VV3_CU_STOCK.hex().upper(),
        "after": entry.hex().upper(),
        "purpose": (
            "Divert the catch-up worker's entry (push esi; mov esi, [esp+8]; push edi at "
            "0x45BF00) into the catch-up decision stub, which resolves the companion's "
            "VvfpFixHutsCatchUp3 once and jumps to it with the stack and registers "
            "untouched: the companion opens one decision for the worker's choice (one 75% "
            "roll shared by every patch it reaches), runs the displaced bytes and the stock "
            "worker, and closes it. Without the DLL the stub runs the displaced bytes and "
            "the stock worker."
        ),
    }


def vv3_sched_site_patch(page_va: int) -> dict:
    target = page_va + VV3_SCHED_CODE_OFFSET
    entry = b"\xE9" + int(target - (VV3_SCHED_VA + 5)).to_bytes(4, "little", signed=True)
    entry += b"\x90" * (len(VV3_SCHED_STOCK) - len(entry))
    return {
        "offset": f"0x{VV3_SCHED_FILE:X}",
        "before": VV3_SCHED_STOCK.hex().upper(),
        "after": entry.hex().upper(),
        "purpose": (
            "Divert the idle scheduler's entry (push ecx; push esi; mov esi, [esp+0xC] at "
            "0x45BFE0) into the decision stub, which resolves the companion's "
            "VvfpFixHutsScheduler3 once and jumps to it with the stack and registers "
            "untouched: the companion opens one decision (one 75% roll shared by every "
            "patch in it, the whole retry loop of the game's choose-the-next-job routine), "
            "runs the displaced bytes and the stock scheduler, and closes it. Without the "
            "DLL the stub runs the displaced bytes and the stock scheduler."
        ),
    }


def vv3_section_header() -> bytes:
    header = bytearray(40)
    header[0:8] = VV3_SECTION_NAME
    header[8:12] = VV3_PAGE_SIZE.to_bytes(4, "little")
    header[12:16] = (VV3_PAGE_VA - 0x400000).to_bytes(4, "little")
    header[16:20] = VV3_PAGE_SIZE.to_bytes(4, "little")
    header[20:24] = VV3_PAGE_FILE.to_bytes(4, "little")
    header[36:40] = (0x60000020).to_bytes(4, "little")
    return bytes(header)


def vv3_transaction(stock: bytes) -> tuple[list[dict], dict, list[dict]]:
    if len(stock) != VV3_STOCK_FILE_SIZE:
        raise RuntimeError("stock VV3 size changed")
    if stock[VV3_SITE_FILE : VV3_SITE_FILE + len(VV3_SITE_STOCK)] != VV3_SITE_STOCK:
        raise RuntimeError("stock bytes at 0x45B39E are not the expected test")
    page = vv3_build_page(VV3_PAGE_VA)
    overlay_page = vv3_build_page(VV3_OVERLAY_VA)
    if stock[VV3_FOOD_SITE_FILE : VV3_FOOD_SITE_FILE + len(VV3_FOOD_SITE_STOCK)] != VV3_FOOD_SITE_STOCK:
        raise RuntimeError("stock bytes at 0x45C229 are not the expected farming test")
    if stock[VV3_PICKER_FILE : VV3_PICKER_FILE + len(VV3_PICKER_STOCK)] != VV3_PICKER_STOCK:
        raise RuntimeError("stock bytes at 0x45AF00 are not the expected dispatcher prologue")
    if stock[VV3_SCHED_FILE : VV3_SCHED_FILE + len(VV3_SCHED_STOCK)] != VV3_SCHED_STOCK:
        raise RuntimeError("stock bytes at 0x45BFE0 are not the expected scheduler prologue")
    if stock[VV3_CU_FILE : VV3_CU_FILE + len(VV3_CU_STOCK)] != VV3_CU_STOCK:
        raise RuntimeError("stock bytes at 0x45BF00 are not the expected catch-up worker prologue")
    patches = [vv3_site_patch(VV3_PAGE_VA), vv3_food_site_patch(VV3_PAGE_VA),
               vv3_picker_site_patch(VV3_PAGE_VA), vv3_sched_site_patch(VV3_PAGE_VA),
               vv3_cu_site_patch(VV3_PAGE_VA)]
    overlay_patches = [vv3_site_patch(VV3_OVERLAY_VA), vv3_food_site_patch(VV3_OVERLAY_VA),
                       vv3_picker_site_patch(VV3_OVERLAY_VA), vv3_sched_site_patch(VV3_OVERLAY_VA),
                       vv3_cu_site_patch(VV3_OVERLAY_VA)]
    layout = {
        "original_file_size": f"0x{VV3_STOCK_FILE_SIZE:X}",
        "append_offset": f"0x{VV3_PAGE_FILE:X}",
        "append_length": VV3_PAGE_SIZE,
        "append_bytes": page.hex().upper(),
        "page_virtual_address": f"0x{VV3_PAGE_VA:X}",
        "page_sha256": hashlib.sha256(page).hexdigest().upper(),
        "purpose": (
            "append the owned VV3 fix-huts stub page (the standalone form; the row "
            "depends on Origins, so in practice the stub overlays Origins' page)"
        ),
        "header_patches": [
            {"offset": "0x10E", "before": "0500", "after": "0600",
             "purpose": "add the owned .vv3fh executable section"},
            {"offset": "0x158", "before": "00F02D00", "after": "00002E00",
             "purpose": "extend SizeOfImage for the owned .vv3fh section"},
            {"offset": "0x2C8", "before": "00" * 40, "after": vv3_section_header().hex().upper(),
             "purpose": "write the owned .vv3fh section header"},
        ],
    }
    overlay = {
        "base_feature": VV3_ORIGINS_ID,
        "overlay_offset": f"0x{VV3_OVERLAY_FILE:X}",
        "overlay_length": VV3_OVERLAY_LENGTH,
        "page_virtual_address": f"0x{VV3_OVERLAY_VA:X}",
        "append_bytes": overlay_page.hex().upper(),
        "page_sha256": hashlib.sha256(overlay_page).hexdigest().upper(),
        "hook_patches": overlay_patches,
        "overlay_preimage": {
            "kind": "zero_fill",
            "length": VV3_OVERLAY_LENGTH,
            "sha256": hashlib.sha256(b"\x00" * VV3_OVERLAY_LENGTH).hexdigest().upper(),
        },
        "purpose": (
            "place the VV3 fix-huts stub in the reserved zero range of the executable "
            "section Origins appends, after the parentage overlay"
        ),
    }
    transaction = {
        "layouts": {mode: layout for mode in ("stock", "collection_progression", "immediate_fixed")},
        "composition_overlays": {VV3_ORIGINS_ID: overlay},
    }
    return patches, transaction, overlay_patches


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    common_non_changes = [
        "Nothing about the examine/fix job itself changes: its route, its 70% repair chance, its Building practice roll and its messages are the game's own.",
        "A builder with a project available still takes the project. With no population hut built there is nothing to fix. With every hut built and no construction available, at Building level 3 or above (and in The Secret City, The Tree of Life and New Believers at any level) the hut choice is the stock fix-a-hut option; below level 3 in A New Home and The Lost Children a built population hut is fixed directly (never The Lost Children's building 5).",
        "Nothing is written to a villager record, the save or any file.",
    ]
    for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
        manifest = {
            "id": f"{game}_builders_fix_huts",
            "enabled": True,
            "catalog_enabled": True,
            "catalog_hidden": False,
            "game_id": game,
            "name": "Builders Fix Huts When Idle",
            "description": describe(game),
            "output_tag": "Fix Huts",
            "dependencies": [f"{game}_enable_origins_exclusive_features"],
            "behavior_changes": [
                "When the Building dispatcher finds no project to work on (every project check has failed) and at least one population hut is complete while another is not, the companion picks a random complete hut and starts the game's own 'Examining hut' job for it, in live play and in catch-up alike.",
                FOOD_BEHAVIOR.format(how=FOOD_HOW[game]),
            ] + ([LEVEL_BEHAVIOR[game]] if game in LEVEL_BEHAVIOR else [])
              + ([HUT_GATE_BEHAVIOR[game]] if game in HUT_GATE_BEHAVIOR else [])
              + ([BUILD_FIRST_BEHAVIOR[game]] if game in BUILD_FIRST_BEHAVIOR else [])
              + [ROLL_BEHAVIOR.format(sched=ROLL_SCHED[game][0], loop=ROLL_SCHED[game][1],
                                      share=ROLL_SHARE[game])
                   + (" The new-hut test above is not part of the roll: it holds on every choice."
                      if game in HUT_GATE_BEHAVIOR else "")]
              + [CU_ROLL_BEHAVIOR.format(worker=CU_WORKER[game],
                                         healers=(" and Healers Study Plants Regardless of Food"
                                                  if game in ("vv1", "vv2") else ""),
                                         healers_extra=(" Healers Study Plants Regardless of Food then adds its "
                                                        "own two-in-three roll, so a studying healer carries on "
                                                        "half the time."
                                                        if game in ("vv1", "vv2") else ""))]
              + [PREFERENCE_BEHAVIOR.format(field=PREFERENCE_FIELD[game], healer=PREFERENCE_HEALER.get(game, ""))],
            "explicit_non_changes": list(common_non_changes),
            "companion_files": [
                {"source": "assets/fix_huts/VVFP Fix Huts.dll",
                 "destination": "VVFP Fix Huts.dll", "sha256": sha},
            ],
            "patches": [],
        }
        if game in RUNTIME:
            if game in GATE_PATCHES:
                manifest["patches"] = GATE_PATCHES[game]
                manifest["explicit_non_changes"].insert(0,
                    "This row changes one test in the executable, the Building branch's new-hut test, so it holds from the first catch-up of a session; everything else is detoured at run time by the DLL, which a companion that already runs every frame loads and which installs only after verifying the stock bytes; a different build of the game installs nothing.")
            else:
                manifest["explicit_non_changes"].insert(0,
                    "This row changes no executable bytes: a companion that already runs every frame loads the DLL, which detours the dispatcher at run time only after verifying the stock bytes; a different build of the game installs nothing.")
            manifest["runtime_detours"] = [
                {**RUNTIME[game], "installed_by": "VVFP Fix Huts.dll, VvfpFixHutsInstall"},
                {**FOOD_RUNTIME[game], "installed_by": "VVFP Fix Huts.dll, VvfpFixHutsInstall"},
            ] + ([{**LEVEL_RUNTIME[game], "installed_by": "VVFP Fix Huts.dll, VvfpFixHutsInstall"}]
                 if game in LEVEL_RUNTIME else []) + (
                [{**GATE_RUNTIME[game], "installed_by": "VVFP Fix Huts.dll, VvfpFixHutsInstall"}]
                 if game in GATE_RUNTIME else []) + [
                {**CU_RUNTIME[game], "installed_by": "VVFP Fix Huts.dll, VvfpFixHutsInstall (before Builders and Healers Work First)"},
                {**SCHED_RUNTIME[game], "installed_by": "VVFP Fix Huts.dll, VvfpFixHutsInstall (first; nothing else installs without it)"},
            ]
        else:
            patches, transaction, _overlay_patches = vv3_transaction(STOCK_VV3.read_bytes())
            manifest["explicit_non_changes"].insert(0,
                "The Secret City's row diverts one eight-byte test in the Building dispatcher, one nine-byte test in the idle scheduler's low-food path, the work dispatcher's ten-byte entry, the idle scheduler's six-byte entry, and the catch-up worker's six-byte entry into five stubs in the page Origins appends; each resolves its companion once and otherwise replays the stock bytes, so with the DLL missing the stock scheduler runs. The dispatcher stub serves the Builders and Healers Work First addendum and does nothing unless \"VVFP Work First.dll\" is shipped.")
            manifest["patches"] = patches
            manifest["pe_append_transaction"] = transaction
        out = ROOT / "data" / f"{game}_builders_fix_huts_feature.json"
        out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), sha)
        work_sha = hashlib.sha256(WORK_FIRST_DLL.read_bytes()).hexdigest().upper()
        out = ROOT / "data" / f"{game}_work_first_feature.json"
        out.write_text(json.dumps(work_first_row(game, work_sha), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), work_sha)


if __name__ == "__main__":
    main()
