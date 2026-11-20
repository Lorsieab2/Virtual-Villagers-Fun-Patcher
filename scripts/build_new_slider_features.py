"""Write the rows of the five 0.1x-10x sliders (the owner, 2026-11-17), all five games each:

  Collectible and Mushroom Frequency  "VVFP Collectible Frequency.dll"  native/vvfp_collectible_frequency
  Food Gained per Food Source         "VVFP Food Gain.dll"              native/vvfp_food_gain
  Tech Point Gain Rate                "VVFP Tech Gain.dll"              native/vvfp_tech_gain
  Skill Practice Success Chance       "VVFP Skill Success.dll"          native/vvfp_skill_success
  Age and Nursing Timer Speed         "VVFP Age Speed.dll"              native/vvfp_age_speed

Each slider goes 0.1 to 10 in tenths, 1 (the normal game) unless moved; its number is written beside the companion
(src/vv_fun_patcher.py RUNTIME_SLIDERS) and read at start (native/shared/slider_scale.h); at 1x the companion
installs nothing.  Each companion is a third-word companion started by "VVFP More Companions.dll".  The sites (and
why each is the right one) are in each companion's source; every one was read from the stock executables
(research/stock-executables) and is checked again by tests/test_new_sliders.py.

One command after a companion's source changes: this script builds the five (scripts/build_vvfp_<name>.ps1) and pins
them by SHA-256 in all 25 rows.  --no-build pins what is already built.
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

SLIDERS = {
    # key: (row suffix, name, DLL, asset folder, output tag)
    "collectible_frequency": ("_collectible_frequency", "Collectible and Mushroom Frequency",
                              "VVFP Collectible Frequency.dll", "collectible_frequency", "Collectible Frequency"),
    "food_gain": ("_food_gain", "Food Gained per Food Source", "VVFP Food Gain.dll", "food_gain", "Food Gain"),
    "tech_gain": ("_tech_gain", "Tech Point Gain Rate", "VVFP Tech Gain.dll", "tech_gain", "Tech Gain"),
    "skill_success": ("_skill_success", "Skill Practice Success Chance", "VVFP Skill Success.dll", "skill_success",
                      "Skill Success"),
    "age_speed": ("_age_speed", "Age and Nursing Timer Speed", "VVFP Age Speed.dll", "age_speed", "Age Speed"),
}

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
        for game in GAMES:
            path = ROOT / "data" / f"vv{game}{SLIDERS[key][0]}_feature.json"
            path.write_text(json.dumps(row(key, game, dll_sha), indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")
            print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
