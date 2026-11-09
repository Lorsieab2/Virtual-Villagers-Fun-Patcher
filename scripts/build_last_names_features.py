"""Generate the five "Villagers Have Last Names" rows.

Every Virtual Villagers game carries a third list of 50 names beside the male
and female first names -- the list Virtual Villagers 6 and 7 later used for
villagers' last names -- which each game's naming routine copies and never
reads.  The owner: new villagers get their family's last name (the family
number 1-50 the game keeps on every villager, inherited from the mother);
villagers who already have names keep them.  And (2026-10-07): "All
newly-spawned villagers from events will default to no last name (because
otherwise everyone will have the wrong last name)" -- the companion names
only a delivery's children and a new village's founders (see the source for
how it tells).

Companion only ("VVFP Last Names.dll", native/vvfp_last_names): "VVFP
Startup.dll" loads it as the game opens and its VvfpStartup detours the
naming routine (see the source for the sites).  No executable byte is
patched.  The DLL is pinned by SHA-256, so re-run this after every rebuild
(scripts/build_vvfp_last_names.ps1).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "last_names" / "VVFP Last Names.dll"
STOCK = ROOT / "research" / "stock-executables"
EXE = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
# The naming routine, its first instruction, and the unused list it copies.
SITES = {
    "vv1": (0x43B950, 0x481BA0, "the villager name builder (thiscall array, index, out), called by the creator and the twin path"),
    "vv2": (0x44B710, 0x48FB98, "the villager name builder (thiscall array, index, out), called by the creator and the twin path"),
    "vv3": (0x45C670, 0x49DFF8, "the villager naming routine (thiscall villager, family)"),
    "vv4": (0x465DA0, 0x4AA930, "the villager naming routine (thiscall villager, family)"),
    "vv5": (0x46F680, 0x4B8450, "the villager naming routine (thiscall villager, family)"),
}
ROOM = {"vv1": 27, "vv2": 23, "vv3": 23, "vv4": 23, "vv5": 23}
# New Believers' Heathens (the owner, 2026-11-08: "in vv5, please give heathens random last names thanks!!!!";
# 2026-11-09: "among the entire heathen tribe they should have like... maybe 4-5 unique last names from the defaults
# list that don't overlap with the villagers' last names" -- always four); native/vvfp_last_names, HEATHENS.
LOAD_VV5 = 0x46FA20
HEATHENS_DESCRIPTION = (
    " Heathens get last names too: each village's Heathen tribe has four family names of its own, chosen once at "
    "random from the same list among the names none of the village's villagers have ever used, and the same after "
    "every reload. Each Heathen gets one of the four at random, kept roughly even so no family is empty or huge: a "
    "new Heathen as the game makes them, and a Heathen with none the first time the patched game loads the village. "
    "Heathens who share a family name are not related. A Heathen who converts keeps their last name. While they "
    "are Heathens their last names are not counted among the village's existing names (Random from the existing "
    "Village Names); once converted, theirs counts like any other. Start Over gives the new village four of its own."
)
HEATHENS_BEHAVIOR = [
    "Each village's Heathens have FOUR family names: chosen once, the first time one of its Heathens is named, at "
    "random from the game's list among the names no believer in the game (converts included) and no \"used\" line "
    "of the village's Last Names record has (every last name the tribe has ever had, living or dead); with fewer "
    "than four such names the rest are any others of the list. Kept as four \"family\" lines of the record, so a "
    "reload gives the same four; Start Over deletes the record with the village.",
    "A Heathen (the Heathen allocator 0x46FB80, every Heathen the game makes: a new village's 28, Barrel O' Babies' "
    "Heathen babies, the Story / Cheat Upgrades' and the Custom Island Event's Heathens, the Heathen Mommy) is "
    "called \"<first name> <family name>\": one of the four that fits, at random, each weighted by how far it is "
    "behind the most-carried one among the living Heathens (1, and 4 more for each Heathen behind), so the four "
    "stay roughly even. Sharing one never makes Heathens related: the name is drawn, never inherited.",
    "Right after the villager table's load (0x46FA20), each living Heathen whose name carries no last name gets one "
    "the same way (a numeral is kept after it), and a \"Name changed\" record (Old name, Age) goes to the Births and "
    "Conceptions log at the next save, so the logs, the Family Tree Maker and Check Saves & Logs follow them as one "
    "villager. Each is kept as a \"heathen\" line with the name, head and body they had, so a session that ends "
    "without a save gives them the same name again; never written for a slot that cannot be told (a village whose "
    "slot is not known yet keeps its four in memory, and writes them once it is).",
    "Whatever the patcher keeps for a Heathen by their name -- a custom title, a mask, a head look, an original "
    "look, a Former Heathens entry -- stays theirs: right after the load the renamed are handed, as one batch, to "
    "each of those companions that is loaded (its export VvfpVillagersRenamed), which carries its own records to "
    "the new name and writes its own file; a name two renamed Heathens shared, or one a villager outside the "
    "batch still has, is carried to nobody (a custom title is then told apart by the looks it was kept with), "
    "and the batch is handed over again at later loads for a file a session never rewrote.",
    "A Heathen's own rule for their children's last names (a \"villager\" line of the Last Names record, keyed by "
    "the whole name, head, body and sex) is carried to the new name the same moment -- never a line a villager "
    "outside the batch still is, or two of the batch were -- and Repair's editor follows the \"Name changed\" "
    "record to it.",
    "\"Random from the existing Village Names\" never counts a current Heathen's last name (the villagers in the "
    "game at a birth, and Repair's names of the village); a converted Heathen keeps their name and it counts from "
    "then on.",
]


def names(image: bytes, va: int) -> list[str]:
    at = va - 0x400000
    return [n.decode("ascii") for n in image[at:image.index(b"\0", at)].split(b",") if n]


def row(game: str, sha: str) -> dict:
    routine, last_list, what = SITES[game]
    pe = pefile.PE(str(STOCK / EXE[game]))
    image = pe.get_memory_mapped_image()
    last = names(image, last_list)
    assert len(last) == 50, (game, len(last))
    stock = image[routine - 0x400000: routine - 0x400000 + 6]
    assert stock[:2] == b"\x81\xEC", (game, stock.hex())
    load_stock = image[LOAD_VV5 - 0x400000: LOAD_VV5 - 0x400000 + 6]
    assert game != "vv5" or load_stock == bytes.fromhex("5356578D7948"), load_stock.hex()
    examples = ", ".join(last[:3])
    description = (
        "Babies born in the village and the village's founders get a last name after their first name, from "
        f"the game's own list of 50 last names ({examples} ... {last[-1]}) -- a list the game has always "
        "carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. "
        "A baby takes its father's or its mother's last name by the rule chosen in Repair Saves & Logs (Last "
        "names come from: from the father, from the mother, 50:50, or a random one of the last names the village "
        "has ever used); without a rule recorded, a baby takes its "
        "father's last name (the village's default is from the father). A villager can also have a rule of "
        "their own for their children (Each villager's own rule): from the father, from the mother, 50:50, "
        "a random last name from the list, which gives each child -- twins and triplets too -- its own random "
        "draw from the game's list, every name equally likely, or a random one of the village's existing last "
        "names. A villager's own rule always beats the village's; when both parents have one and they "
        "disagree, a coin toss for each child picks whose. "
        "Villagers who arrive "
        "through an island event get no last name, because theirs would not be their family's. Only "
        "villagers named from now on get one: villagers who already have names keep them. The last "
        "name is part of the name the game stores, so it shows wherever the name does and stays in the save "
        "even if this patch is later removed."
        + (" The Golden Child, whose family is not one of the 50, gets no last name." if game == "vv1" else "")
        + (HEATHENS_DESCRIPTION if game == "vv5" else "")
        + " **Needs no other patch.**"
    )
    heathens = game == "vv5"
    return {
        "id": f"{game}_last_names",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": "Villagers Have Last Names",
        "description": description,
        "output_tag": "Last Names",
        "behavior_changes": [
            "A baby born in the village from now on (a mother's delivery: the first child, a twin or a "
            "triplet) and a new village's founders are called \"<first name> <last name>\": the first name is "
            "the game's own pick, and the last name is name number <family - 1> of the game's unused third "
            f"list ({last_list:#X}), read from the running executable.",
            "A villager the game creates any other way -- brought by an island event, a cheat or the Origins "
            "page -- keeps the game's own first name only: the companion tells a birth or a founder by the "
            "callers' return addresses on the stack, at fixed places.",
            "A villager whose family is outside 1-50 gets no last name.",
            "At a birth, the rule recorded by Repair Saves & Logs decides the last name (VvfpRuleLastName2): the "
            "father's, the mother's, either at random (50:50), or -- a parent's own rule \"Random last name from "
            "the list\" -- a name drawn at random from the game's list, or -- \"Random from the existing Village "
            "Names\", the village's rule or a parent's own -- one of the last names the village has ever used (the "
            "record's \"used\" lines, the villagers in the game at the birth, VvfpRuleLastName3, and the parents'; "
            "the game's list when there are none); every random draw is a fresh, unbiased one for each child. "
            "Each such birth adds the names it saw that the record lacks as \"used\" lines (only adding, through "
            "a temporary file, never for a slot it cannot tell), so a name stays ever used after its last bearer "
            "is gone.",
            "A parent's own rule always beats the village's; parents whose own rules disagree: a fresh coin toss "
            "for each child picks the father's or the mother's.",
            f"The whole name always fits the game's own name field: the longest pairing is far below its {ROOM[game]} "
            "characters.",
            *(HEATHENS_BEHAVIOR if heathens else []),
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion detours the naming routine's first instruction at "
            "run time" + (" (and the villager table's load, 0x46FA20)" if heathens else "") + ", after verifying "
            "it, the routine's push of the list and the creators' calls to it, and changes nothing if any differs.",
            "Villagers who already have names keep them; " + (
                "when a village is loaded, only a Heathen whose name carries no last name is given one."
                if heathens else "nothing is renamed when a village is loaded."),
            "The first names, sexes, looks and families are the game's own; the save format is unchanged.",
            *(["Heathens still never count in the statistics, and a Heathen's last name never makes them anyone's "
               "relative: it is drawn, never inherited, and no parent is recorded for it."] if heathens else []),
        ],
        "evidence_status": ("static exact-build verification of the naming routines, their callers and the "
                            "unused list in each executable; runtime/player confirmation pending"),
        "companion_files": [
            {"source": "assets/last_names/VVFP Last Names.dll", "destination": "VVFP Last Names.dll", "sha256": sha},
        ],
        "runtime_detours": [
            {
                "va": f"{routine:#X}".replace("0X", "0x"),
                "stock_bytes": stock.hex().upper(),
                "routine": what,
                "installed_by": "VVFP Last Names.dll, VvfpStartup",
            },
            *([{
                "va": "0x46FA20",
                "stock_bytes": load_stock.hex().upper(),
                "routine": "the villager table's load (thiscall manager, saved table): Heathens with no last name "
                           "get one right after it",
                "installed_by": "VVFP Last Names.dll, VvfpStartup",
            }] if heathens else []),
        ],
        "patches": [],
    }


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game in SITES:
        path = ROOT / "data" / f"{game}_last_names_feature.json"
        path.write_text(json.dumps(row(game, sha), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                        newline="\n")
        print(path.name)


if __name__ == "__main__":
    main()
