"""Write the rows of "Island Events Scale With Population (like The Lost Children)" and its alternative "Island Events
Scale With Stored Food and Tech Points" (A New Home, The Tree of Life, New Believers) -- the owner, 2026-11-12:

  1. island-event food and tech-point gains AND losses are multiplied by k = 1 up to 25 living villagers, 2 for 26
     to 50, 3 above 50 (The Lost Children's two-choice rule 0x41F720), the population as each game's own routine
     counts it.  A New Home: only its 4 fixed encounters (its island events already scale by n).  Off by default,
     on in Owner's Defaults, and a member of each game's Classic VV Difficulty (The Tree of Life, New Believers;
     A New Home has no Classic VV Difficulty row).
  2. the alternative: each gain or loss = the stock amount + 10% of the food (for food) or tech points (for tech)
     stored, never less than the stock amount.  Off by default and in Owner's Defaults; the two cannot both be
     ticked.

THE SITES (research/stock-executables, capstone, 2026-11-12) are the instruction that puts each stock amount in
place; native/vvfp_island_events_scale/vvfp_island_events_scale.c has the same table (tests pin the two together):

  A New Home (the encounters' resolve 0x419380; the world [esi+0x50A4]; food world+0xA2EC through 0x41D140, tech
  world+0xA2FC through 0x41D120; the population 0x41CF90, living villagers plus babies carried):
    0x41944F push 0x3E8 (The Trapped Whale), 0x419C35 push 0xBB8 (The Troubled Child, then jmp 0x41A36D),
    0x419F09 add eax, 0x12C after rand(200) (The Wild Mushroom), 0x41A367 add eax, 0x7D0 after rand(3000) (The
    Brass Compass).
  The Tree of Life (food 0x4D6DD0 through 0x41D920, tech 0x4D6F88 through 0x41E300, which stop at 0; the
  population 0x467610 on the villager manager): the single-result setters (vtable [14], `mov [ecx+8], imm`; the
  amount is printed as {award}; a loss setter then clamps it to what is stored, but tests the store against the
  STOCK immediate -- `cmp eax, imm / jge` -- so the companion clamps a scaled loss itself, by the same rule, and the
  {award} shown is what is taken) and the two-choice results' `mov [esp+4], imm` /
  `push imm` before the food or tech writer.  The Tree of Life Origins' tail jumps (0x41520E, 0x415862, 0x41586F,
  0x415A81, 0x415B46, 0x415D8C, 0x416722, 0x416735) follow the movs and are never touched.  CEventTheReturnOfBiggles
  (0x4156EB, its amount from [esi+8]) is never fired by the game and is left alone.
  New Believers (food 0x51D34C through 0x41EB40, tech 0x51D5F8 through 0x4237B0; the population 0x4713F0, believers
  and the babies they carry -- the record test 0x466170 with 0 refuses a Heathen): as The Tree of Life, plus the
  rolled amounts (0x414EFD add eax, 0x7D0; 0x41507A / 0x415128 mov ecx, -500 / sub ecx, eax; 0x415110 add eax, 0x32
  / push eax / mov ecx, food) and the short pushes (0x4163CA push -25, 0x41666B push -100, each with the following
  mov ecx, food).  The Smelly Vial's rand(100) + 20 food (0x416CF3) is never fired (its condition 0x415B10 is
  always false) and is left alone.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_island_events_scale.ps1) and
pins it by SHA-256 in all six rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Island Events Scale.dll"
DLL = ROOT / "assets" / "island_events_scale" / DLL_NAME
FLAG_NAME = "VVFP Island Events Scale Stored.txt"
FLAG = ROOT / "assets" / "island_events_scale" / FLAG_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
POPULATION_NAME = "Island Events Scale With Population (like The Lost Children)"
STORED_NAME = "Island Events Scale With Stored Food and Tech Points"
GAMES = (1, 4, 5)
TITLES = {1: "A New Home", 4: "The Tree of Life", 5: "New Believers"}


def population_id(game: int) -> str:
    return f"vv{game}_island_events_scale_with_population"


def stored_id(game: int) -> str:
    return f"vv{game}_island_events_scale_with_stored_amounts"


# (va, stock bytes, form, food or tech, stock amount, the event and its result).  The amount is the instruction's own:
# for a single-result setter the size of the loss (the setter's caller subtracts it), else the signed change.
SITES = {
    1: (
        (0x41944F, "68E8030000", "push", "food", 1000, "The Trapped Whale, \"Harvest the whale for food.\": +1,000 food"),
        (0x419C35, "68B80B0000", "push", "tech", 3000, "The Troubled Child, \"Let him (her) try research.\": +3,000 tech points"),
        (0x419F09, "052C010000", "add eax", "food", 300, "The Wild Mushroom, delicious: +300 to 499 food (rand(200) + 300)"),
        (0x41A367, "05D0070000", "add eax", "tech", 2000, "The Brass Compass, \"Let the researchers have it.\": +2,000 to 4,999 tech points (rand(3000) + 2000)"),
    ),
    4: (
        (0x414730, "C7410864000000", "setter", "food", 100, "The Creeping Mold: -100 food"),
        (0x414930, "C741082C010000", "setter", "food", 300, "The Mysterious Footprints (food gained): +300 food"),
        (0x414980, "C741082C010000", "setter", "food", 300, "The Mysterious Footprints (food lost): -300 food"),
        (0x414A00, "C74108D0070000", "setter", "tech", 2000, "The Mysterious Footprints (tech gained): +2,000 tech points"),
        (0x414A50, "C74108D0070000", "setter", "tech", 2000, "The Mysterious Footprints (tech lost): -2,000 tech points"),
        (0x415201, "C74424042C010000", "esp", "food", 300, "The Arc of Brilliant Colors, \"Run to the right side\" (rare mushrooms): +300 food"),
        (0x41585A, "C7442404B80B0000", "esp", "tech", 3000, "The Calabash Instrument, \"Fill it up to the first notch\": +3,000 tech points"),
        (0x415867, "C744240430F8FFFF", "esp", "tech", -2000, "The Calabash Instrument, \"Fill it to the top\": -2,000 tech points"),
        (0x415942, "680CFEFFFF", "push", "tech", -500, "The Climber, \"Start yelling for help\": -500 tech points"),
        (0x415A74, "C7442404F4010000", "esp", "tech", 500, "The Mosquito Larvae, \"Pour oil in the pond\": +500 tech points"),
        (0x415B39, "C7442404E8030000", "esp", "tech", 1000, "Faces in the Night, \"Inform the tribe\": +1,000 tech points"),
        (0x415D7F, "C744240488130000", "esp", "tech", 5000, "The Sealed Box, \"Swim back with the box\": +5,000 tech points"),
        (0x416715, "C7442404D0070000", "esp", "tech", 2000, "The Aspiring Scientist, \"Try the salts\": +2,000 tech points"),
        (0x416728, "C744240418FCFFFF", "esp", "tech", -1000, "The Aspiring Scientist, \"Use algae\": -1,000 tech points"),
    ),
    5: (
        (0x414A00, "C7410864000000", "setter", "food", 100, "The Creeping Mold: -100 food"),
        (0x414C10, "C741082C010000", "setter", "food", 300, "The Mysterious Footprints (food gained): +300 food"),
        (0x414C60, "C741082C010000", "setter", "food", 300, "The Mysterious Footprints (food lost): -300 food"),
        (0x414CE0, "C74108D0070000", "setter", "tech", 2000, "The Mysterious Footprints (tech gained): +2,000 tech points"),
        (0x414D30, "C74108D0070000", "setter", "tech", 2000, "The Mysterious Footprints (tech lost): -2,000 tech points"),
        (0x414EFD, "05D0070000", "add eax", "tech", 2000, "The Strange Crystals: +2,000 to 2,999 tech points (rand(1000) + 2000)"),
        (0x41507A, "B90CFEFFFF2BC8", "sub ecx", "tech", -500, "The Pesky Critter: -500 to -2,999 tech points (-500 - rand(2500))"),
        (0x415110, "83C03250B94CD35100", "add push", "food", 50, "Mushroom Day!: +50 to 99 food (rand(50) + 50)"),
        (0x415128, "B90CFEFFFF2BC8", "sub ecx", "tech", -500, "Mushroom Day!: -500 to -1,499 tech points (-500 - rand(1000))"),
        (0x4155B0, "68D0070000", "push", "tech", 2000, "News From Another Tribe (a message): +2,000 tech points"),
        (0x415F01, "C7442404D8FFFFFF", "esp", "food", -40, "Spying on the Heathens, \"Talk to the heathen\": -40 food"),
        (0x4160A5, "C7442404F4010000", "esp", "tech", 500, "You're Doing It Wrong!, \"There are a lot of them; better not!\": +500 tech points"),
        (0x4163CA, "6AE7B94CD35100", "push ecx", "food", -25, "Outreach?, \"Offer a tour\": -25 food"),
        (0x4163D7, "C7442404E0FCFFFF", "esp", "tech", -800, "Outreach?, \"Offer a tour\": -800 tech points"),
        (0x41655A, "68D0070000", "push", "tech", 2000, "The Advanced Artifacts, \"Collaborate with the other researchers\": +2,000 tech points"),
        (0x416548, "C74424049CFFFFFF", "esp", "tech", -100, "The Advanced Artifacts, the other button: -100 tech points"),
        (0x416648, "68DC050000", "push", "tech", 1500, "Trick Or Trade, \"Employ a clever ruse\": +1,500 tech points"),
        (0x41666B, "6A9CB94CD35100", "push ecx", "food", -100, "Trick Or Trade, \"Trade some food for the scrolls\": -100 food"),
        (0x416692, "C7442404B80B0000", "esp", "tech", 3000, "Trick Or Trade, \"Trade some food for the scrolls\": +3,000 tech points"),
        (0x416891, "C7442404DC050000", "esp", "tech", 1500, "The Aphids in the Noni Bush, \"Research bugs that eat aphids\": +1,500 tech points"),
        (0x4169A9, "C744240430F8FFFF", "esp", "tech", -2000, "The Defector, \"Accept the heathen\" (a spy): -2,000 tech points"),
        (0x416A57, "C7442404C8000000", "esp", "food", 200, "The Straw Hat, \"Use it as a cooking strainer\": +200 food"),
        (0x416B3A, "C7442404D0070000", "esp", "tech", 2000, "The Strange Nectar, \"Bring it to the lab\": +2,000 tech points"),
    ),
}

POPULATION_WORDS = {
    1: "living villagers plus the babies being carried, as the game counts its population",
    4: "living villagers plus the babies being carried, as the game counts its population",
    5: "believers plus the babies they carry, as the game counts its population for room; Heathens are not counted",
}
WHICH = {
    1: ("A New Home's island events already grow with the village (strength n); this patch scales the four "
        "encounters that give a fixed or rolled amount: The Trapped Whale (+1,000 food), The Troubled Child "
        "(+3,000 tech points), The Wild Mushroom (+300 to 499 food) and The Brass Compass (+2,000 to 4,999 tech "
        "points)."),
    4: ("The 14 amounts of 9 events are scaled: The Creeping Mold, The Mysterious Footprints (all four), The Arc of "
        "Brilliant Colors, The Calabash Instrument, The Climber, The Mosquito Larvae, Faces in the Night, The Sealed "
        "Box and The Aspiring Scientist."),
    5: ("The 23 amounts of 16 events are scaled: The Creeping Mold, The Mysterious Footprints (all four), The "
        "Strange Crystals, The Pesky Critter, Mushroom Day!, News From Another Tribe (a message), Spying on the "
        "Heathens, You're Doing It Wrong!, Outreach?, The Advanced Artifacts, Trick Or Trade, The Aphids in the "
        "Noni Bush, The Defector, The Straw Hat and The Strange Nectar."),
}
TEXTS = {
    1: ("The encounters' own result texts are fixed (for example the whale's \"1000-point food bonus!\"), so they "
        "still name the game's own amount while the scaled amount is what is given."),
    4: ("A single-result event's popup shows the scaled amount (it prints the amount the game set); a two-choice "
        "event's result text is fixed (for example \"Your tribe gains 5000 tech points.\"), so it still names the "
        "game's own amount while the scaled amount is what is given."),
    5: ("The Creeping Mold's and The Mysterious Footprints' popups show the scaled amount (they print the amount "
        "the game set); the other events' result texts are fixed (for example \"Your tribe gains 3000 tech "
        "points.\"), so they still name the game's own amount while the scaled amount is what is given."),
}
ROLLED = {
    1: "The Wild Mushroom's and The Brass Compass's amounts are scaled after the game's roll",
    4: None,
    5: "The Strange Crystals', The Pesky Critter's and Mushroom Day!'s amounts are scaled after the game's roll",
}


CLAMP_WORDS = (
    "A single-result loss (The Creeping Mold, The Mysterious Footprints' food and tech lost) is then clamped to what "
    "is stored by the companion, by the setter's own rule (stored below the amount: the amount is what is stored), "
    "because the setter itself tests the store against its stock amount (cmp eax, imm / jge); the setter's test then "
    "runs as in the stock game, and the {award} its popup shows is what is taken. The two-choice food and tech "
    "writers' floor at 0 runs after it, as in the stock game.")


def clamp_words(game: int) -> str:
    """What happens to a loss: A New Home's four encounters only ever give."""
    if game == 1:
        return "The four amounts are gains; the game's food and tech writers add them as before."
    return CLAMP_WORDS


def common_tail(game: int) -> str:
    rolled = ROLLED[game]
    words = (" " if game == 1 else
             " A loss still takes no more than there is, and Food Mastery still raises a food gain as the game does. ")
    words += TEXTS[game] + " "
    if rolled:
        words += (rolled + ", so Pick Island Event's amount settings (Story / Cheat Upgrades) choose the roll, "
                  "before the scaling. ")
    words += ("Custom Island Events (Story / Cheat Upgrades) keep their own amounts. Nothing is saved, so the patch "
              "can be ticked or unticked at any time.")
    return words


def population_description(game: int) -> str:
    classic = ("Off by default; part of Classic VV Difficulty; Owner's Defaults ticks it."
               if game in (4, 5) else "Off by default; Owner's Defaults ticks it.")
    return (
        "Island events' food and tech-point gains and losses grow with the village, as in The Lost Children: each "
        "amount is multiplied by 1 with up to 25 villagers, by 2 with 26 to 50 and by 3 with more than 50 ("
        + POPULATION_WORDS[game] + "). " + WHICH[game] + common_tail(game)
        + f" **Needs no other patch.** **Cannot be ticked together with \"{STORED_NAME}\": the two scale the same "
        "amounts in different ways, so tick only one; with both ticked the patcher builds nothing.** " + classic
        + " **Unverified in play: the effect has not been tested live.** The companion is \"" + DLL_NAME
        + "\", started by VVFP Startup.dll; if it cannot be loaded, the stock amounts are given."
    )


def stored_description(game: int) -> str:
    classic = (" Classic VV Difficulty scales by the population instead, so it cannot be ticked with this one either."
               if game in (4, 5) else "")
    return (
        "Island events' food and tech-point gains and losses grow with what the village has stored: each amount "
        "becomes the game's own amount plus a tenth of the food (for a food amount) or of the tech points (for a "
        "tech amount) stored at that moment, rounded down, and never less than the game's own amount. For example, "
        "with 5,000 food stored a gain of 300 food becomes 800"
        + (". " if game == 1 else ", and a loss of 300 food becomes a loss of 800. ")
        + WHICH[game] + common_tail(game)
        + f" **Needs no other patch.** **Cannot be ticked together with \"{POPULATION_NAME}\": the two scale the "
        "same amounts in different ways, so tick only one; with both ticked the patcher builds nothing.**" + classic
        + " Off by default, and off in Owner's Defaults and Select All (it is the alternative). **Unverified in play: "
        "the effect has not been tested live.** The patch adds one small file, \"" + FLAG_NAME + "\", to the "
        "patcher's folder, which tells \"" + DLL_NAME + "\" (started by VVFP Startup.dll) to scale this way."
    )


def detours(game: int, stored: bool) -> list[dict]:
    out = []
    for va, stock, form, kind, amount, what in SITES[game]:
        length = len(bytes.fromhex(stock))
        if stored:
            how = (f"the stock amount {amount:+d} plus a tenth of the stored {'food' if kind == 'food' else 'tech points'}"
                   f" (never less than {abs(amount)})")
        else:
            how = f"the stock amount {amount:+d} x k (1 up to 25, 2 up to 50, 3 above)"
        if form == "setter":
            how = how.replace(f"{amount:+d}", f"{amount}")
        out.append({
            "va": f"0x{va:X}",
            "stock_bytes": stock,
            "written_bytes": "E8XXXXXXXX" + "90" * (length - 5),
            "routine": f"{what}: the instruction putting it in place ({form}) calls the companion, which puts "
                       f"{how} in its place",
            "installed_by": INSTALLED_BY,
        })
    return out


def population_row(game: int, dll_sha: str) -> dict:
    count = {1: "the population routine 0x41CF90 on the world ([esi+0x50A4] at each encounter)",
             4: "the population routine 0x467610 on the villager manager (0x50E568, or where 256 Villagers moves it: "
                "the manager's static initialiser's own `mov ecx`, 0x488D70)",
             5: "the believer count 0x4713F0 on the villager manager (0x554148, or where 256 Villagers moves it: "
                "0x494050's `mov ecx`); its record test 0x466170(0) refuses a Heathen"}[game]
    return {
        "id": population_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": POPULATION_NAME,
        "description": population_description(game),
        "output_tag": "Events Scale With Population",
        "dependencies": [],
        "conflicts": [stored_id(game)],
        "behavior_changes": [
            f"Each site below calls {DLL_NAME}, which counts the population with {count} and puts the stock amount "
            "x k in place of the stock amount, k = 3 above 50, 2 above 25, else 1 (The Lost Children's 0x41F720: "
            "cmp 0x32 / jle, cmp 0x19 / jle). A gain stays a gain and a loss a loss. " + clamp_words(game),
        ] + [f"{what} (0x{va:X})." for va, _s, _f, _k, _a, what in SITES[game]],
        "explicit_non_changes": [
            "No executable byte is patched: the companion writes each site at run time, only after verifying every "
            "site's stock bytes (all of them, or none).",
            "The game's rolls, its food and tech writers (Food Mastery's raise included), the clamps, every other "
            "event, the popups' and buttons' texts, Custom Island Events and the save are unchanged.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; every site emulated on the stock executable "
                            "with the shipped companion (k = 1, 2, 3 at 25, 26, 50 and 51 villagers, gains, losses "
                            "and the loss clamp, the 256 Villagers manager) in tests/test_island_events_scale.py; "
                            "runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/island_events_scale/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": detours(game, stored=False),
    }


def stored_row(game: int, dll_sha: str, flag_sha: str) -> dict:
    store = {1: "the world's food (+0xA2EC) or tech points (+0xA2FC)",
             4: "the food (0x4D6DD0) or tech points (0x4D6F88)",
             5: "the food (0x51D34C) or tech points (0x51D5F8)"}[game]
    conflicts = [population_id(game)] + ([f"vv{game}_classic_vv_difficulty"] if game in (4, 5) else [])
    return {
        "id": stored_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": STORED_NAME,
        "description": stored_description(game),
        "output_tag": "Events Scale With Stores",
        "dependencies": [],
        "conflicts": conflicts,
        "behavior_changes": [
            f"\"{DLL_NAME}\" checks at start (VvfpStartup) whether \"{FLAG_NAME}\" is in the patcher's folder "
            "(GetFileAttributesW, by full path from the executable's own; the contents are never read). When it "
            f"is, each site below puts the stock amount plus floor(stored / 10) -- {store}, read at that moment, "
            "0 when below 0 -- with the amount's own sign in place of the stock amount (a loss grows by the same "
            "tenth). " + clamp_words(game),
        ] + [f"{what} (0x{va:X})." for va, _s, _f, _k, _a, what in SITES[game]],
        "explicit_non_changes": [
            "No executable byte is patched: the row's own file is the flag; the companion writes each site at run "
            "time, only after verifying every site's stock bytes (all of them, or none).",
            "The game's rolls, its food and tech writers (Food Mastery's raise included), the clamps, every other "
            "event, the popups' and buttons' texts, Custom Island Events and the save are unchanged.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; every site emulated on the stock executable "
                            "with the shipped companion and the flag (stock + a tenth of the stored food or tech "
                            "points, gains and losses, the loss clamp) in tests/test_island_events_scale.py; "
                            "runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/island_events_scale/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
            {"source": f"assets/island_events_scale/{FLAG_NAME}", "destination": FLAG_NAME, "sha256": flag_sha},
        ],
        "patches": [],
        "runtime_detours": detours(game, stored=True),
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_island_events_scale.ps1")], check=True)
    dll_sha, flag_sha = sha(DLL), sha(FLAG)
    for game in GAMES:
        write(ROOT / "data" / f"{population_id(game)}_feature.json", population_row(game, dll_sha))
        write(ROOT / "data" / f"{stored_id(game)}_feature.json", stored_row(game, dll_sha, flag_sha))


if __name__ == "__main__":
    main()
