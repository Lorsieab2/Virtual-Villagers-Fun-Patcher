"""Write the rows of the 0.1x-10x sliders: five (the owner, 2026-11-17) in all five games each, and two more (the
owner, 2026-11-25, for v1.35.101) only in the games that have what they change (SLIDER_GAMES):

  Collectible and Mushroom Frequency  "VVFP Collectible Frequency.dll"  native/vvfp_collectible_frequency
  Food Gained per Food Source         "VVFP Food Gain.dll"              native/vvfp_food_gain
  Tech Point Gain Rate                "VVFP Tech Gain.dll"              native/vvfp_tech_gain
  Skill Practice Success Chance       "VVFP Skill Success.dll"          native/vvfp_skill_success
  Age and Nursing Timer Speed         "VVFP Age Speed.dll"              native/vvfp_age_speed
  0.1-10x Weather Changes        "VVFP Weather Frequency.dll"      native/vvfp_weather_frequency  (VV3-VV5)
  0.1-10x Divine Energy Gain             "VVFP Divine Energy Gain.dll"     native/vvfp_divine_energy_gain (VV5)

Each slider goes 0.1 to 10 in tenths, 1 (the normal game) unless moved; its number is written beside the companion
(src/vv_fun_patcher.py RUNTIME_SLIDERS) and read at start (native/shared/slider_scale.h); at 1x the companion
installs nothing.  Each companion is a third-word companion started by "VVFP More Companions.dll".  The sites (and
why each is the right one) are in each companion's source; every one was read from the stock executables
(research/stock-executables) and is checked again by tests/test_new_sliders.py.

One command after a companion's source changes: this script builds them all (scripts/build_vvfp_<name>.ps1) and pins
each by SHA-256 in all its rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAMES = (1, 2, 3, 4, 5)
GAME_NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
INSTALLED_BY = "{dll}, VvfpStartup (started by VVFP More Companions.dll, third word)"
RAND = {1: 0x402F10, 2: 0x4031A0, 3: 0x4032D0, 4: 0x4036D0, 5: 0x403660}
FOOD_WRITER = {1: 0x41D140, 2: 0x4262B0, 3: 0x4263F0, 4: 0x41D920, 5: 0x41EB40}
TECH_WRITER = {1: 0x41D120, 2: 0x426290, 3: 0x427130, 4: 0x41E300, 5: 0x4237B0}

# (va, what, optional) -- the same tables as the companions' sources.
COLLECT_SITES = {
    1: [(0x423516, "the mushroom roll, rand(120) > 117 every 2-second village step while none is out", False)],
    2: [(0x415FED, "the appearance roll, rand(100) < Exploration + 4 every 2 seconds", False)],
    3: [(0x42DD72, "the appearance roll, rand(6000) < 3", False),
        (0x42DD8D, "the second roll above weather strength 50, rand(6000) < 3", False)],
    4: [(0x4143AD, "the appearance roll, rand(6000) < 4 (in fog: Wind Flute pieces / 2 x 4)", False),
        (0x4143C7, "the second roll above weather strength 50, rand(6000) < 4", False)],
    5: [(0x41464B, "the appearance roll, rand(6000) < 3 (in fog < 6)", False),
        (0x414665, "the second roll above weather level 50, rand(6000) < 3", False)],
}
SKILL_NAMES = ("Farming", "Building", "Research", "Healing", "Parenting")
SKILL_SITES = {
    1: [0x43D470, 0x43D5D3, 0x43D71D, 0x43D7EB, 0x43D89F],
    2: [0x44E1D0, 0x44E36B, 0x44E4D2, 0x44E5D5, 0x44E6DA],
    3: [0x45A342, 0x45A4F1, 0x45A673, 0x45A78D, 0x45A897],
    4: [0x462B15, 0x462D93, 0x462F9E, 0x46312A, 0x4632A3],
    5: [0x46B305, 0x46B4D1, 0x46B6BB, 0x46B847, 0x46B9C0, 0x46BB73],
}
SKILL_ORDER = {1: SKILL_NAMES, 2: SKILL_NAMES, 3: ("Farming", "Parenting", "Healing", "Building", "Research"),
               4: SKILL_NAMES, 5: SKILL_NAMES + ("Devotion",)}
FOOD_SITES = {
    1: [(0x43AD8C, "berries", False), (0x43AECD, "crops", False), (0x43AF3C, "fish", False),
        (0x43AF8E, "crab", False), (0x43AFF7, "mushroom", False),
        (0x43B09B, "the Golden Child's +150 food", False)],
    2: [(0x463198, "coconuts", False), (0x463259, "crops", False), (0x463312, "fish", False),
        (0x463364, "the big catch", False),
        (0x4633CD, "mushroom (left alone while Super-Secret Golden Mushroom owns the call)", True)],
    3: [(0x434AEC, "fruit", False), (0x434B15, "the chief's fruit bonus", False), (0x431C2A, "honey", False),
        (0x431C4C, "the chief's honey bonus", False), (0x458EE5, "fish", False), (0x458FE1, "crab", False),
        (0x42E079, "mushroom", False),
        (0x434C06, "the rain lift's fruit (left alone while Fruit is Harvested at the Food Bin owns the call)", True),
        (0x434D7F, "the cliff top's fruit (likewise)", True),
        (0x434C77, "the rain lift's fruit delivered at the food bin (only with Fruit is Harvested at the Food Bin)",
         True),
        (0x459068, "the chief's food grant", False)],
    4: [(0x464492, "berries", False), (0x46450B, "the harvest", False),
        (0x464573, "yellow fruit (left alone while Yellow Fruit Trees are No Longer Unlimited owns the call)", True),
        (0x4645B0, "fish", False), (0x4645FB, "golden fish", False), (0x464A46, "crab", False),
        (0x436F15, "the Mossy Rocks crab", False),
        (0x468AB2, "the Cooking Pit's catch-up fruit (likewise)", True),
        (0x414660, "mushroom", False), (0x464433, "the fish event the game inherited", False)],
    5: [(0x46CFFB, "noni", False), (0x46D10E, "crops", False), (0x46D79C, "lake fish", False),
        (0x41496B, "mushroom", False), (0x46CF9C, "an inherited food event", False),
        (0x46D074, "an inherited food event", False), (0x46D75F, "an inherited food event", False),
        (0x46D7D9, "an inherited food event", False), (0x46DB20, "an inherited food event", False)],
}
TECH_SITES = {
    1: [(0x43B313, "research at Science 1"), (0x43B32E, "research at Science 2"), (0x43B34B, "research at Science 3")],
    2: [(0x463737, "research at Science 3"), (0x4637C0, "research at the other Science levels"),
        (0x463809, "the fire's extra point")],
    3: [(0x459232, "research at Science 0 or 4 and up"), (0x4593AA, "research at Science 1 to 3"),
        (0x4593D0, "the chief's quarter"), (0x4593ED, "Magic's extra point"),
        (0x45940B, "the chief's third or the potion's extra point"), (0x459435, "the fire's extra point")],
    4: [(0x464E58, "research"), (0x464E82, "the Lab Equipment bonus"), (0x464EAB, "the fire's extra point")],
    5: [(0x46DE48, "research"), (0x46DE77, "the second collectible set's bonus"),
        (0x46DEA0, "the fire's extra point")],
}
AGE_SITES = {
    1: (0x42EA62, "2B8140030000", "sub eax, [ecx + 0x340]"),
    2: (0x43B856, "2BC203C8898D24050000", "sub eax, edx; add ecx, eax; mov [ebp + 0x524], ecx"),
    3: (0x45F4F5, "2BC703D0B880510100", "sub eax, edi; add edx, eax; mov eax, 0x15180"),
    4: (0x46656C, "2BC701866DFFFFFF", "sub eax, edi; add [esi - 0x93], eax"),
    5: (0x46FFA3, "2BC70186341C0000", "sub eax, edi; add [esi + 0x1C34], eax"),
}
# The weather setter's four spell lengths (seconds on the game's clock): (va, opcode, stock seconds, what) -- clear's
# least and greatest, then any other kind's (native/vvfp_weather_frequency).
WEATHER_SETTER = {3: 0x41FB40, 4: 0x46BC30, 5: 0x477060}
WEATHER_SITES = {
    3: [(0x41FBF9, 0xBF, 900, "mov edi, 900: clear weather's least"), (0x41FBFE, 0xBB, 1800,
                                                                       "mov ebx, 1800: clear weather's greatest"),
        (0x41FC05, 0xBF, 180, "mov edi, 180: any other weather's least"),
        (0x41FC0A, 0xBB, 360, "mov ebx, 360: any other weather's greatest")],
    4: [(0x46BD1D, 0xBF, 480, "mov edi, 480: clear weather's least"), (0x46BD22, 0xB8, 1800,
                                                                       "mov eax, 1800: clear weather's greatest"),
        (0x46BD29, 0xBF, 180, "mov edi, 180: any other weather's least"),
        (0x46BD2E, 0xB8, 360, "mov eax, 360: any other weather's greatest")],
    5: [(0x4771AB, 0xBF, 480, "mov edi, 480: clear weather's least"), (0x4771B0, 0xB8, 1800,
                                                                       "mov eax, 1800: clear weather's greatest"),
        (0x4771B7, 0xBF, 180, "mov edi, 180: any other weather's least"),
        (0x4771BC, 0xB8, 360, "mov eax, 360: any other weather's greatest")],
}
# The setter's calls from the weather's own code (the natural changes, divided by N): (va, what).  Every other call
# (island events, God Powers, a queued kind) is left alone, so those spells last as in the normal game.
WEATHER_NATURAL = {
    3: [(0x41FD11, "the start of a village's weather"), (0x41FF9C, "the fruit trees' rain after clear"),
        (0x41FFAB, "back to clear when a spell ends"), (0x41FFC0, "clear -> another kind (shared with a queued kind)")],
    4: [(0x46BDF8, "the start of a village's weather"), (0x46C103, "clear -> another kind"),
        (0x46C113, "back to clear when a spell ends")],
    5: [(0x477298, "the start of a village's weather"), (0x477563, "clear -> another kind"),
        (0x477573, "back to clear when a spell ends")],
}
# The setter's other calls, never touched (an island event's, a God Power's, a queued kind's ...).
WEATHER_LEFT_ALONE = {
    3: [0x414E67, 0x414E9C, 0x4150D9, 0x415119, 0x4151E9, 0x4166BB, 0x4166CB, 0x4167AD, 0x433B76, 0x464739,
        0x464787, 0x4647D9],
    4: [0x414957, 0x4149BC, 0x414B99, 0x414BD9, 0x414C19, 0x41509C, 0x41FF3A, 0x432918, 0x46C129],
    5: [0x414C37, 0x414C9C, 0x414E29, 0x41F32C, 0x41FB1D, 0x4230C7, 0x425A1E, 0x439182, 0x477589],
}
# The Secret City's queued kind shares the 0x41FFC0 call: its path's first instruction jumps to the companion, which
# makes the same call unmarked and goes on at 0x41FFC5.
WEATHER_QUEUED = {3: (0x41FFB4, "C74604FFFFFFFF", 0x41FFC5)}
# New Believers' Divine Energy adder and the calls of it that pay the believers' earnings (native/vvfp_divine_energy_gain).
ENERGY_WRITER = {5: 0x424F80}
ENERGY_SITES = {
    5: [(0x472D25, "each believer's +1 every age unit"), (0x472D43, "+3 more at Devotion 50 or more"),
        (0x472D61, "+5 more at Devotion 88 or more"),
        (0x472DDB, "+1 more on Hard, or on Medium with 8,000 food or more"),
        (0x46D893, "Honoring's +3"), (0x46D8B3, "Honoring's +4 more at Devotion 50 or more"),
        (0x46D8D7, "Honoring's +5 more at Devotion 88 or more"),
        (0x46DA1F, "work event 40's +1 (the Tribute Statue's polishing with Fix Vanilla Bugs)")],
}
# The adder's other calls, never scaled: (va, what).
ENERGY_LEFT_ALONE = {
    5: [(0x44E65C, "the tutorial's top-up to 10"), (0x425DB4, "a new village's 50"), (0x4250F4, "the cap's clamp"),
        (0x41474D, "a relic found again: 10"), (0x41476E, "a relic found again: 50"),
        (0x41478F, "a relic found again: 150"), (0x4157C8, "an island event's +10"),
        (0x415DAB, "an island event's -20")],
}

SLIDERS = {
    # key: (row suffix, name, DLL, asset folder, output tag)
    "collectible_frequency": ("_collectible_frequency", "Collectible and Mushroom Frequency",
                              "VVFP Collectible Frequency.dll", "collectible_frequency", "Collectible Frequency"),
    "food_gain": ("_food_gain", "Food Gained per Food Source", "VVFP Food Gain.dll", "food_gain", "Food Gain"),
    "tech_gain": ("_tech_gain", "Tech Point Gain Rate", "VVFP Tech Gain.dll", "tech_gain", "Tech Gain"),
    "skill_success": ("_skill_success", "Skill Practice Success Chance", "VVFP Skill Success.dll", "skill_success",
                      "Skill Success"),
    "age_speed": ("_age_speed", "Age and Nursing Timer Speed", "VVFP Age Speed.dll", "age_speed", "Age Speed"),
    # The owner, 2026-11-25 (v1.35.101): "Frequency of weather changes in games that have them" and "frequency of
    # divine energy gain in vv5".
    "weather_frequency": ("_weather_frequency", "0.1-10x Weather Changes", "VVFP Weather Frequency.dll",
                          "weather_frequency", "Weather Frequency"),
    "divine_energy_gain": ("_divine_energy_gain", "0.1-10x Divine Energy Gain", "VVFP Divine Energy Gain.dll",
                           "divine_energy_gain", "Divine Energy Gain"),
}
# The games each slider has a row in (A New Home and The Lost Children have no weather; only New Believers has
# Divine Energy).
SLIDER_GAMES = {key: GAMES for key in SLIDERS}
SLIDER_GAMES["weather_frequency"] = (3, 4, 5)
SLIDER_GAMES["divine_energy_gain"] = (5,)

COMMON_TAIL = ("**Needs no other patch.** Off by default; Owner's Defaults ticks it, with the slider at 1. "
               "**Unverified in play** (checked by emulation of the game's own code). The companion is \"{dll}\", "
               "started by VVFP More Companions.dll, and the slider's number is written beside it in \"{choice}\"; "
               "nothing is written to a save.")
SLIDER_WORDS = ("the {name} slider in the patcher window (it reads -10 to 10: 10 is 10 times, -10 a tenth, -2 "
                "half, and 1, the middle, the normal game; 1 unless you move it; type it in the box beside the "
                "slider too)")


def call_bytes(va: int, target: int) -> str:
    return "E8" + (target - (va + 5) & 0xFFFFFFFF).to_bytes(4, "little").hex().upper()


def describe(key: str, game: int) -> str:
    suffix, name, dll, _asset, _tag = SLIDERS[key]
    choice = dll[:-4] + ".txt"
    words = SLIDER_WORDS.format(name=name)
    if key == "collectible_frequency":
        what = ("Mushrooms appear on their own" if game == 1 else "Mushrooms and collectibles appear on their own")
        rules = {
            1: "A New Home has mushrooms only (no collectibles). Normally one appears, while none is out, about every "
               "2 real-life minutes; at 2 about every minute, at 0.5 about every 4 minutes.",
            2: "The Exploration level still counts: Normally 5% of each 2-second check (6% at Exploration 2, 7% at 3); "
               "at 2 times 10% (14% at 3).",
            3: "The second roll in heavy weather is multiplied too.",
            4: "Fog's Wind Flute chance and the second roll in heavy weather are multiplied too, and so is \"Collectible "
               "Spawn Timing works like VV1-3\".",
            5: "Fog's doubling and the second roll in heavy weather are multiplied too.",
        }[game]
        body = (f"{what} more or less often: 0.1 to 10 times as often, as you choose with {words}. {rules} What "
                "appears, how many may lie out at once and for how long are the game's own. ")
    elif key == "food_gain":
        sources = ", ".join(sorted({w.split(" (")[0] for _va, w, _o in FOOD_SITES[game]
                                    if "inherited" not in w}, key=str.casefold))
        extra = {4: " Food Mastery still works on top.", 5: " Food Mastery still works on top."}.get(game, "")
        body = (f"Each food source gives more or less food each time: 0.1 to 10 times its normal food, as you choose "
                f"with {words}; the rest of a whole food is a chance, so on average it is exact. The sources: {sources}"
                ". What the source itself loses is the game's own, and so is every other food gain: island events, "
                "puzzles' and messages' rewards, purchases and cheats." + extra + " ")
    elif key == "tech_gain":
        body = (f"Research brings more or fewer tech points: 0.1 to 10 times the normal points, as you choose with "
                f"{words}; the rest of a whole point is a chance, so on average it is exact. The Science level, the "
                "speed and every research bonus still count. Island events, duplicate collectibles, puzzles' and "
                "messages' rewards and cheats are the game's own. Works with 0.1-10x Tech Cost (prices) and the "
                "Origins Tech Point Doubler. ")
    elif key == "skill_success":
        skills = ", ".join(SKILL_NAMES + (("Devotion",) if game == 5 else ()))
        body = (f"Each time a villager practises a skill at work ({skills}) the skill check passes more or less "
                f"often: 0.1 to 10 times as often (always, once that reaches it), as you choose with {words}. The "
                "villager's skill still counts, and what a pass gives is the game's own. \"Learning Skills Never "
                "Fails\" still makes every check pass. ")
    elif key == "weather_frequency":
        clear = "15 to 30" if game == 3 else "8 to 30"
        trees = (" When the game makes a spell its shortest length (The Secret City does so in one state of its "
                 "fruit trees), that is divided too." if game == 3 else "")
        others = ("an island event, a God Power (Sunshine, Tempest) or anything else" if game == 5
                  else "an island event or anything else")
        body = (f"The weather changes on its own more or less often: 0.1 to 10 times as often, as you choose with "
                f"{words}. Every natural spell of weather (the weather's own turns: the start of a village's weather, "
                "clear weather giving way to another kind, and back to clear) lasts its normal length divided by the "
                f"number: normally clear weather lasts {clear} minutes and any other kind 3 to 6, on the game's clock "
                "(real-life minutes on Normal speed; the clock runs twice as fast on Fast, 0.6 times on Slow, and "
                f"stops while paused). So at 2 clear weather lasts {'7.5 to 15' if game == 3 else '4 to 15'} minutes "
                f"and any other kind 1.5 to 3; never less than 1 second. Weather that {others} brings on, at once or "
                "next in line, lasts exactly as in the normal game. Which kind comes next is the game's own. A spell "
                "already under way when the game starts keeps its end." + trees + " Rain and storms build up their strength "
                "5 points every 6 seconds, so at high numbers spells are short and the strength rarely reaches 50, "
                "above which mushrooms and collectibles get a second chance to appear. ")
    elif key == "divine_energy_gain":
        body = (f"The believers earn Divine Energy faster or slower: 0.1 to 10 times their normal Divine Energy, as "
                f"you choose with {words}; the rest of a whole point is a chance, so on average it is exact. What it "
                "multiplies: each believer's 1 every age unit (4 at Devotion 50 or more, 9 at 88 or more, and 1 more "
                "on Hard, or on Medium with 8,000 food or more) and Honoring's 3, 7 or 12 (and, with Fix Vanilla "
                "Bugs, the Tribute Statue polishing's 1). The cap is the game's own, and so are the God Powers' costs "
                "and every other Divine Energy change: a new village's 50, the tutorial's top-up, a relic found "
                "again (10, 50 or 150), island events and \"Practicing Devotion Builds Faith and Divine Energy\". ")
    else:
        extra = {
            1: " The Golden Child stays 5.",
            2: " Esteemed Elders (the totems) are not aged by the game, as before.",
            3: "",
            4: " Ghosts are not aged by the game, as before.",
            5: " Heathens are not aged by the game, as before; faith and Divine Energy, counted per year of age, "
               "follow too.",
        }[game]
        body = (f"Villagers' age clock runs faster or slower: 0.1 to 10 times as fast, as you choose with {words}. "
                "Everything counted in years of age follows it together: growing up, becoming an elder, old age, "
                "pregnancy and nursing (a baby is born 2 years of the mother's age after it was conceived), and "
                "eating, health and sickness, which come once per age step. So at 2 villagers also eat twice as "
                "often per real hour. The ages at which things happen are the game's own; only how soon they come "
                "changes. A Time Warp's years are multiplied too." + extra + " Work, conception, food regrowth, "
                "island events and the Nursery School run at the normal speed. ")
    return body + COMMON_TAIL.format(dll=dll, choice=choice)


def detours(key: str, game: int) -> list[dict]:
    _suffix, name, dll, _asset, _tag = SLIDERS[key]
    by = INSTALLED_BY.format(dll=dll)
    if key == "collectible_frequency":
        return [{"va": f"0x{va:X}", "stock_bytes": call_bytes(va, RAND[game]), "written_bytes": "E8XXXXXXXX",
                 "routine": f"{what}: the game's rand is called once by the companion, which scales the roll "
                            f"({'from the top' if game == 1 else 'from the bottom'}) so the test passes N times as "
                            "often", "installed_by": by}
                for va, what, _o in COLLECT_SITES[game]]
    if key == "skill_success":
        return [{"va": f"0x{va:X}", "stock_bytes": call_bytes(va, RAND[game]), "written_bytes": "E8XXXXXXXX",
                 "routine": f"the {skill} skill check's rand(100): called once by the companion, which scales the roll "
                            "so the check passes N times as often", "installed_by": by}
                for va, skill in zip(SKILL_SITES[game], SKILL_ORDER[game])]
    if key in ("food_gain", "tech_gain"):
        table = FOOD_SITES if key == "food_gain" else {g: [(va, w, False) for va, w in s] for g, s in TECH_SITES.items()}
        writer = (FOOD_WRITER if key == "food_gain" else TECH_WRITER)[game]
        kind = "food" if key == "food_gain" else "tech point"
        return [{"va": f"0x{va:X}", "stock_bytes": call_bytes(va, writer), "written_bytes": "E8XXXXXXXX",
                 "routine": f"{what}: the call of the {kind} writer 0x{writer:X} goes through the companion, which "
                            "multiplies a positive amount by N (the rest a chance) and goes on into the writer"
                            + ("; optional" if optional else ""), "installed_by": by}
                for va, what, optional in table[game]]
    if key == "weather_frequency":
        setter = WEATHER_SETTER[game]
        out = [{"va": f"0x{va:X}", "stock_bytes": f"{op:02X}" + seconds.to_bytes(4, "little").hex().upper(),
                "written_bytes": "E8XXXXXXXX",
                "routine": f"the weather setter 0x{setter:X}'s {what} (seconds on the game's clock): a call of the "
                           "companion, which loads the same register with the stock seconds, or with the seconds "
                           "divided by N (rounded, at least 1; the greatest kept above the least) while a natural "
                           "change is being made; flags and every other register kept", "installed_by": by}
               for va, op, seconds, what in WEATHER_SITES[game]]
        out += [{"va": f"0x{va:X}", "stock_bytes": call_bytes(va, setter), "written_bytes": "E8XXXXXXXX",
                 "routine": f"the weather's own call of the setter 0x{setter:X}, {what}: goes through the companion, "
                            "which marks the change natural, calls the setter with the same arguments and clears the "
                            "mark", "installed_by": by}
                for va, what in WEATHER_NATURAL[game]]
        if game in WEATHER_QUEUED:
            va, stock, resume = WEATHER_QUEUED[game]
            out.append({"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": "E9XXXXXXXX9090",
                        "routine": f"a queued kind's path (mov dword ptr [esi + 4], -1, then the call it shares "
                                   f"with the natural change): a jump to the companion, which makes the same move "
                                   f"and the same call of the setter unmarked (stock lengths) and goes on at "
                                   f"0x{resume:X}", "installed_by": by})
        return out
    if key == "divine_energy_gain":
        writer = ENERGY_WRITER[game]
        return [{"va": f"0x{va:X}", "stock_bytes": call_bytes(va, writer), "written_bytes": "E8XXXXXXXX",
                 "routine": f"{what}: the call of the Divine Energy adder 0x{writer:X} goes through the companion, "
                            "which multiplies a positive amount by N (the rest a chance) and goes on into the adder",
                 "installed_by": by}
                for va, what in ENERGY_SITES[game]]
    va, stock, text = AGE_SITES[game]
    return [{"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": "E8XXXXXXXX" + "90" * (len(stock) // 2 - 5),
             "routine": f"the world tick's add of each villager's real seconds since its last look ({text}): the "
                        "companion does the same with the seconds multiplied by N (the rest a chance), before the "
                        "game's own cap", "installed_by": by}]


def behaviour(key: str, game: int) -> str:
    _suffix, name, dll, _asset, _tag = SLIDERS[key]
    sites = ", ".join(d["va"] for d in detours(key, game))
    return (f"{name}: the companion's sites {sites} (see runtime_detours), installed only when the slider is not 1; N "
            f"is read at start from \"{dll[:-4]}.txt\" beside the companion in tenths (0.1 to 10; none is 1).")


def row(key: str, game: int, dll_sha: str) -> dict:
    suffix, name, dll, asset, tag = SLIDERS[key]
    return {
        "id": f"vv{game}{suffix}",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": name,
        "description": describe(key, game),
        "output_tag": tag,
        "dependencies": [],
        "conflicts": [],
        "behavior_changes": [behaviour(key, game)],
        "explicit_non_changes": [
            "No executable byte is patched: the companion writes its sites at run time, only after verifying their "
            "stock bytes (all of them, or none; an optional site another patch owns is left alone).",
            "At 1x nothing is installed. The game's rand is never drawn more or less often: the companion's chances "
            "are its own numbers.",
            "Nothing is written to a save, a villager record or a file; no text is shown.",
        ],
        "evidence_status": ("implemented from exact-build disassembly of the stock executable; the companion's install "
                            "and its effect emulated on the rendered executable (tests/test_new_sliders.py); "
                            "runtime/player confirmation pending"),
        "companion_files": [{"source": f"assets/{asset}/{dll}", "destination": dll, "sha256": dll_sha}],
        "patches": [],
        "runtime_detours": detours(key, game),
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    for key, (_suffix, _name, dll, asset, _tag) in SLIDERS.items():
        if "--no-build" not in sys.argv[1:]:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(ROOT / "scripts" / f"build_vvfp_{asset}.ps1")], check=True)
        dll_sha = sha(ROOT / "assets" / asset / dll)
        for game in SLIDER_GAMES[key]:
            path = ROOT / "data" / f"vv{game}{SLIDERS[key][0]}_feature.json"
            path.write_text(json.dumps(row(key, game, dll_sha), indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")
            print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
