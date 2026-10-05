"""Generate the five "Cause of Death" rows.

The owner, in turn: "for the games that don't write a cause of death like
VV1-VV2, can you add them please?" -- shown in the game, the way The Secret
City, The Tree of Life and New Believers show it; "mention it for all 5 games
in the logs, age of death too" (the age in the game's own units); "can you
also put the epitaphs for VV1-VV2 too?" (pregenerated, and editable by the
player as in the later games); one Death record per death that leaves a
skeleton, written when the death is final, with the grave's skill line and
epitaph; "Disappeared" records for villagers taken with no skeleton; and
"No villager gets unaccounted for!" -- a separate Unaccounted Villagers log.

One companion, "VVFP Cause of Death.dll" (native/vvfp_cause_of_death), loaded
by each game's Origins companion (native/shared/cause_bridge.h), which
verifies every site's stock bytes (all or nothing) and writes its detours at
run time.  The rows patch no executable byte.  The logs are filed by "VVFP
Parentage Export.dll" (WriteVillageRecord).

The site tables below are the DLL's own (cod_vv12.inc, cod_vv345.inc,
cod_gone*.inc, cod_roster*.inc, cod_epitaph_edit.inc); the tests install
the DLL into every render and check each listed site was written.

The DLL is pinned by SHA-256, so re-run this after every rebuild.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from origins_base_text import ORIGINS_BASE_SENTENCE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "cause_of_death" / "VVFP Cause of Death.dll"
INSTALLED_BY = "VVFP Cause of Death.dll, VvfpCauseInstall"

CAUSE_WORDS = "Old age, Disease, Starvation, Work accident, or Unknown causes"

INJURY15 = "a job's 2% injury, rand(15) (Work accident)"
INJURY10 = "a job's 2% injury, rand(10) (Work accident)"
SAVED = "right after the game's own save call (al = saved, edi = slot): the Unaccounted Villagers reconciliation"

# (va, stock bytes, what the site is), in the order the DLL adds them.
SITES = {
    "vv1": [
        ("0x42EF05", "C78344030000" "00000000", "the aging step's old-age store (Old age)"),
        ("0x42ECB7", "8B8C0744030000", "the aging step's hunger drain at 200 food or less (Starvation)"),
        ("0x42ED37", "8B8C1744030000", "the aging step's no-food drain (Starvation)"),
        ("0x42EDA3", "8B8C1744030000", "the aging step's sickness drain (Disease)"),
        ("0x43A5B4", "29038B8610E00300", INJURY15),
        ("0x43A793", "29078B8610E00300", INJURY15),
        ("0x43A8BA", "29078B9610E00300", INJURY15),
        ("0x43A9E1", "29078B9610E00300", INJURY15),
        ("0x43AAE7", "29078B8E10E00300", INJURY15),
        ("0x43AC9B", "29078B8610E00300", INJURY15),
        ("0x43B112", "29078B8E10E00300", INJURY15),
        ("0x43B2D4", "8B0B83C404", INJURY10),
        ("0x43B393", "8B0B83C404", INJURY10),
        ("0x449008", "8B5C2410" "C7860CFDFFFF01000000", "after the burial's grave loop: the Death record, the grave's cause and epitaph"),
        ("0x42E9C3", "C644072800", "an unburied body's removal: the Death record (no grave)"),
        ("0x436700", "5F5E5D5B81C4CC000000", "the grave popup's Draw epilogue: the cause and the epitaph's quotes"),
        ("0x436E5C", "C7465C22010000", "the grave popup's constructor end: the editable epitaph box"),
        ("0x436407", "8B442408" "3B4164", "the grave popup's onEvent: Done keeps an edited epitaph"),
        ("0x41979D", "885C0228" "8B8EA4500000", "The Mysterious Face takes a villager: the Disappeared record"),
        ("0x41A272", "885C1128" "5B", "The Book takes a villager: the Disappeared record"),
        ("0x43C39B", "C6462A00" "896E40", "the villager creator (0x43C350): an arrival"),
        ("0x43C888", "885E2A" "895E40", "the copy creator (0x43C840, twins and triplets): an arrival"),
        ("0x40322A", "5F5E" "8AC3" "5B", "the save file writer's success epilogue (bl = written; the village is its 0xABDC-byte write): the Unaccounted Villagers reconciliation"),
    ],
    "vv2": [
        ("0x43BDEE", "C7832C050000" "00000000", "the aging step's old-age store (Old age)"),
        ("0x43BAEB", "8D84382C050000", "the aging step's hunger drain at 150 food or less (Starvation)"),
        ("0x43BB7E", "8D843A2C050000", "the aging step's no-food drain (Starvation)"),
        ("0x43BC43", "8D843A2C050000", "the aging step's sickness drain (Disease)"),
        ("0x46299C", "2945008B86D474E500", "the Ancient Mosaic's injury, rand(15) (Work accident)"),
        ("0x462AD9", "29078B8ED474E500", "the Lovely Hut's injury, rand(15) (Work accident)"),
        ("0x462C11", "29078B86D474E500", "a hut's injury, rand(15) (Work accident)"),
        ("0x462D48", "29078B96D474E500", "a hut's injury, rand(15) (Work accident)"),
        ("0x462E84", "29078B96D474E500", "a hut's injury, rand(15) (Work accident)"),
        ("0x462F96", "29078B96D474E500", "the Hospital's injury, rand(15) (Work accident)"),
        ("0x463099", "29078B96D474E500", "the Sewing Hut's injury, rand(15) (Work accident)"),
        ("0x463644", "8B4D0083C404", "research's injury, rand(10) (Work accident)"),
        ("0x4638E6", "8B0F83C404", "the Gong restoration's injury, rand(10) (Work accident)"),
        ("0x46404A", "8B0F83C404", "the Vine Wall's injury, rand(10) (Work accident)"),
        ("0x4641B3", "8B4D0083C404", "the Dam's injury, rand(10) (Work accident)"),
        ("0x465334", "C7475801000000", "after the burial's grave loop: the Death record, the grave's cause"),
        ("0x43B78D", "C644383000", "an unburied body's removal: the Death record (no grave)"),
        ("0x444790", "8B8D84000000", "the grave panel's Draw, after its Age line: the cause"),
        ("0x444433", "8B4E60" "8B5678", "the grave panel's Done, before it keeps the epitaph: the old text"),
        ("0x44445C", "B001" "5E" "C20800", "the grave panel's Done, after: the Epitaph changed record"),
        ("0x433E9B", "46" "C6403000", "A Dangerous Mission takes a villager: the Disappeared record"),
        ("0x4208FF", "885C1130" "5B", "The Voices In The Brush takes a villager: the Disappeared record"),
        ("0x44C84F", "C6865805000000", "the villager creator (0x44C600): an arrival"),
        ("0x44CF04", "885E31" "885E32", "the copy creator (0x44CEC0, twins, triplets, the Mirror): an arrival"),
        ("0x41F963", "8B8EB0500000", "The Strange Request's stranger (not one of the tribe)"),
        ("0x424BF8", "5F5E" "C20400", SAVED),
    ],
    "vv3": [
        ("0x4551D7", "5D5B5FB001", "the Roster of the Dead writer's exit: the entry it wrote"),
        ("0x4622C8", "5F5E5D" "C7432801000000", "after the burial's roster write: the Death record"),
        ("0x45F437", "F7B1202F0100", "an unburied body's removal (its minutes): the Death record (no grave)"),
        ("0x41E6A3", "8B4E4C" "83C108", "the grave dialog's Done, before it keeps the epitaph: the old text"),
        ("0x41E6BB", "B001" "5E" "C20800", "the grave dialog's Done, after: the Epitaph changed record"),
        ("0x45D990", "5355" "8B6C240C" "5657", "the wave sweep's entry (The Tsunami, The Low Tide)"),
        ("0x45D9DD", "5F5E5D5B" "C20800", "the wave sweep's exit: the Disappeared records"),
        ("0x456326", "889E110F0000" "889E120F0000", "the villager init (0x456120): an arrival"),
        ("0x4566EF", "889E110F0000" "889E120F0000", "the copy init (0x4566E0, twins, triplets, clones): an arrival"),
        ("0x427D71", "5F5E" "C20400", SAVED),
    ],
    "vv4": [
        ("0x45D62E", "5EB0015D59", "the Roster of the Dead writer's exit: the entry it wrote"),
        ("0x46A996", "5E" "C7435401000000", "after the burial's roster write: the Death record"),
        ("0x4664B4", "8DBE39E3FFFF", "an unburied body's removal: the Death record (no grave)"),
        ("0x41C2D3", "8B4E4C" "83C138", "the grave dialog's Done, before it keeps the epitaph: the old text"),
        ("0x41C2EB", "B001" "5E" "C20800", "the grave dialog's Done, after: the Epitaph changed record"),
        ("0x415DA6", "C681C41C000000", "The Sealed Box's wave takes a villager: the Disappeared record"),
        ("0x45F175", "889EC51C0000" "889EC61C0000", "the villager init (0x45EF10): an arrival"),
        ("0x45D9BB", "C686C51C000000", "the copy init (0x45D9B0, twins, triplets): an arrival"),
        ("0x41F13F", "5F5E" "C20400", SAVED),
    ],
    "vv5": [
        ("0x464E51", "5EB0015D59", "the Roster of the Dead writer's exit: the entry it wrote"),
        ("0x473FAE", "5E" "C7435401000000", "after the burial's roster write: the Death record"),
        ("0x46FF12", "889ED41C0000", "an unburied body's removal: the Death record (no grave)"),
        ("0x41CB33", "8B4E4C" "83C138", "the grave dialog's Done, before it keeps the epitaph: the old text"),
        ("0x41CB4B", "B001" "5E" "C20800", "the grave dialog's Done, after: the Epitaph changed record"),
        ("0x468411", "8BCE" "89842490000000", "the villager init (0x4681F0): an arrival"),
        ("0x4687FE", "889ED51C0000", "the copy init (0x4687F0, twins, triplets): an arrival"),
        ("0x46FDE0", "5356" "8BD9" "57", "Reanimate's stand-in maker (not one of the tribe)"),
        ("0x4245FF", "5F5E" "C20400", SAVED),
    ],
}

GAME_NAMES = {"vv1": "A New Home", "vv2": "The Lost Children", "vv3": "The Secret City",
              "vv4": "The Tree of Life", "vv5": "New Believers"}

NAMES = {
    "vv1": "Show Cause of Death and Epitaphs on Graves, and Log Every Death",
    "vv2": "Show Cause of Death on Graves, and Log Every Death",
    "vv3": "Log Every Death, Disappearance and Unaccounted Villager",
    "vv4": "Log Every Death, Disappearance and Unaccounted Villager",
    "vv5": "Log Every Death, Disappearance and Unaccounted Villager",
}

DISAPPEARANCES = {
    "vv1": "The Mysterious Face and The Book",
    "vv2": "A Dangerous Mission and The Voices In The Brush",
    "vv3": "The Tsunami and The Low Tide",
    "vv4": "The Sealed Box",
    "vv5": None,
}


def logs_text(n: str, game: str) -> str:
    gone = DISAPPEARANCES[game]
    gone_text = (f"a villager taken with no skeleton ({gone}, or the Custom Island Event's "
                 "\"Disappears\") gets a \"Disappeared\" record saying what took them"
                 if gone else
                 "a villager taken by the Custom Island Event's \"Disappears\" gets a "
                 "\"Disappeared\" record (the game itself has no such event)")
    return (
        f"Every death that leaves a body is written to the Deaths log ('Virtual Villagers {n} "
        "Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\\Deaths' folder beside the "
        "game's saves) when it is final: when the body is buried, with the skill line and epitaph "
        "the grave was given, or when the game removes a body nobody buried (\"no grave\"). Each "
        "Death record gives the villager's name, head, body, likes and dislikes, their age at death "
        "in the game's own units (20 per year, as the Village Population log prints Age), the cause, "
        f"the grave and the epitaph. A villager brought back to life gets no Death record. {gone_text[0].upper()}{gone_text[1:]}, "
        "and editing a grave's epitaph adds an \"Epitaph changed\" record with the old and new text. "
        "A grave the Deaths log has no record for -- dug before the log was kept, or while the game "
        "was catching up on time away -- is given a Death record only when the player says so -- Repair "
        "Logs in the patcher window, or Repair when the game asks as it closes (with \"Check logs "
        "automatically\" on, and only if something is wrong); nothing is ever asked while the village "
        "is played. The record is made from "
        "the grave (name, age at death, skill line, epitaph, and the cause where the game or this "
        "patch knows it) with the head, body, likes and dislikes of the villager's last Village "
        "History snapshot (\"(unknown)\" when that does not settle who it was), and marked "
        "\"Recorded from the grave\". Which graves have their record is kept in 'Virtual Villagers "
        f"Fun Patcher Data\\Deaths\\Virtual Villagers {n} Graves Logged - Save <n>.dat', so no grave is recorded twice; "
        "Start Over deletes it. "
        "Every villager who joins the village without being born into it -- a new village's "
        "founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers" + (
            ", a Heathen converted to a believer (a Heathen is never a villager)" if game == "vv5" else "") + " -- "
        f"gets an \"Arrived\" record in the Births and Conceptions log ('Virtual Villagers {n} Births and "
        "Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, "
        "head, body, likes, dislikes, skills, and how they came (\"Founder\", the island event's title, "
        "\"Barrel of Babies\", \"Custom Island Event\""
        + (", \"Converted from the Heathens\"" if game == "vv5" else "") + ", or \"unknown\"). "
        "A birth is never an arrival. Villagers already in a village who arrived before this record "
        "existed (no Birth or Arrived record with their name, head and body) each get one the same "
        "way, only when the player says so, marked \"Recorded afterwards (arrived before this log "
        "existed)\", as \"Founder\" when the village's first Village History snapshot lists them and "
        "otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher "
        f"Data\\Arrivals\\Virtual Villagers {n} Arrivals Recorded - Save <n>.dat' then says it is done; "
        "Start Over deletes it. "
        + ("In A New Home a villager born here is told by their Birth record, which Show Parents in "
           "Details Screen writes: **without that patch no Arrived record is backfilled.** "
           if game == "vv1" else
           "A villager the save says was born here (their record keeps their parents) who has no Birth "
           "or Arrived record -- born before the log existed -- gets, the same way and only when the "
           "player says so, a Birth record written from the save, with their parents as the "
           "save keeps them, marked \"Recorded afterwards (born before this log existed)\" -- exactly "
           f"once: 'Virtual Villagers Fun Patcher Data\\Births\\Virtual Villagers {n} Births Recorded - "
           "Save <n>.dat' then says it is done; Start Over deletes it. ") +
        "At every save, the village is checked against the one saved before: a villager who left "
        "with no Death or Disappeared record, or arrived with no birth or known arrival, is written "
        f"with everything known about them to the Unaccounted Villagers log ('Virtual Villagers {n} "
        "Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\\Unaccounted "
        "Villagers'). Both logs are headed with the village and its save slot, are created when a "
        "village is started and again after Start Over (which deletes them with the village), only "
        "ever grow, and start a new numbered file after every 256 records. The village as it was at "
        f"each save is kept in 'Virtual Villagers Fun Patcher Data\\Unaccounted Villagers\\Virtual "
        f"Villagers {n} Village Roster - Save <n>.dat'; Start Over deletes it."
    )


CAVEATS = (
    "**The first save after this patch is installed only starts the check: nothing is reported "
    "about anything that happened before it.** "
    "**The patch's DLL is loaded and its hooks installed as soon as the game is opened, before "
    "any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up "
    "on time away (and of a Time Warp) are recorded as they happen, like any others.** "
    "**The logs are written by Write Births and Conceptions Log to Text File's DLL: with that "
    "patch off, none of them is written.**"
)


def description(game: str) -> str:
    n = game[-1]
    tail = (f"{CAVEATS} {ORIGINS_BASE_SENTENCE} That base's companion loads this patch's DLL; "
            "if the DLL cannot be loaded, the game runs unchanged.")
    if game == "vv1":
        return (
            "Shows each dead villager's cause of death and an epitaph on their grave, the way The "
            "Secret City, The Tree of Life and New Believers do. Clicking a gravestone shows the "
            "epitaph in quotes under the name, in a box you can type in (up to 31 characters; "
            "Done keeps it), and the cause under the age, in those games' own words ("
            f"{CAUSE_WORDS}). The cause is the one that killed them -- old age, sickness, hunger "
            "or an empty food bin, an injury at work -- and \"Unknown causes\" for an island event "
            "and anything else, which is how those games word an island-event death. The epitaph "
            "is chosen by the rule those games use at a burial: a child's is \"Curious and "
            "Playful\" or \"Loving and Special\"; an adult's comes from the skill the grave shows "
            "(for example \"Strong Arms, Big Heart\" or \"Inspired Architect\" for a builder); a "
            "villager with no skill is a \"Respected Citizen\". Those games' Chief, Esteemed Elder "
            "and Scholar epitaphs have no counterpart here and are not used. A New Home keeps "
            "neither, so both are kept for each save slot in a file beside the saves ('Virtual "
            "Villagers Fun Patcher Data\\Graves\\Virtual Villagers 1 Graves - Save <n>.dat'); Start Over "
            "deletes it. **Graves dug before this patch was installed get an epitaph the first "
            "time they are opened, but no cause: how they died was never recorded.** "
            f"{logs_text(n, game)} {tail}"
        )
    if game == "vv2":
        return (
            "Shows each dead villager's cause of death on their grave, the way The Secret City, The "
            "Tree of Life and New Believers do: clicking a gravestone shows the cause under the "
            f"age, in those games' own words ({CAUSE_WORDS}). The cause is the one that killed "
            "them -- old age, sickness, hunger or an empty food bin, an injury at work -- and "
            "\"Unknown causes\" for an island event and anything else, which is how those games "
            "word an island-event death. The Lost Children keeps no cause, so it is kept for each "
            "save slot in a file beside the saves ('Virtual Villagers Fun Patcher Data\\Graves\\"
            "Virtual Villagers 2 Graves - Save <n>.dat'); Start Over deletes it. The game's own epitaphs "
            "are unchanged. **Graves dug before this patch was installed, and bodies that were "
            "already lying when it was, show no cause: how they died was never recorded.** "
            f"{logs_text(n, game)} {tail}"
        )
    return f"{logs_text(n, game)} The cause is the one {GAME_NAMES[game]} itself records and shows on the grave. {tail}"


def manifest(game: str, sha: str) -> dict:
    n = game[-1]
    detours = [{"va": va, "stock_bytes": stock, "routine": what, "installed_by": INSTALLED_BY}
               for va, stock, what in SITES[game]]
    changes = []
    if game in ("vv1", "vv2"):
        changes += [
            "At each site that can kill (the aging step's old-age store and its sickness, hunger and no-food drains; every work injury), a check made before the site's own instructions records the cause when that change takes a living villager's health to 0 or below; the site's instructions then run unchanged.",
            "Every frame, a villager seen alive on an earlier frame who is now a body, with no site having reported the death, is recorded with \"Unknown causes\" (island events, the Gong of Wonder, the Custom Island Event's \"dies\", an edited save).",
            "After the burial's grave loop, the cause recorded for that body is carried to the grave it was given" + (" with an epitaph chosen by the later games' rule" if game == "vv1" else "") + ", and the Death record is written.",
            "The grave popup draws the cause at the later games' height (+0xD7)" + ("; its constructor adds the game's own editable text box for the epitaph (as The Lost Children's panel and the Villager Detail name box are made), drawn between quotes, and Done keeps an edited epitaph in the .dat file." if game == "vv1" else "."),
            f"Kept per save slot in 'Virtual Villagers Fun Patcher Data\\Graves\\Virtual Villagers {n} Graves - Save <n>.dat' (written atomically; an unreadable file is set aside, never overwritten; deleted by Start Over).",
        ]
    else:
        changes += [
            "After the burial's Roster of the Dead write, the Death record is written with the cause, skill line and epitaph the game gave the grave; a body the game removes unburied gets \"no grave\".",
        ]
    changes += [
        "The listed removals of a living villager write a Disappeared record before the game takes them; the Custom Island Event's \"Disappears\" is reported by the Story / Cheat Upgrades DLL.",
        f"Graves with no Death record: VvfpCauseScanGraves counts, writing nothing, the graves the village's Deaths log has no record for (the first-load check lists them for the player); VvfpCauseRepairGraves records the player's answer. Only after Repair, at each save of that village in the session, each such grave gets a Death record from the grave, filed by RecordGravesMissingFromLog in \"VVFP Parentage Export.dll\" (which counts the log's own and held records first, and takes the head, body, likes and dislikes from the Village History log); a villager the previous save held who was buried unseen is then not an Unaccounted record. The graves whose record is in the log are kept in 'Virtual Villagers Fun Patcher Data\\Deaths\\Virtual Villagers {n} Graves Logged - Save <n>.dat' (written atomically; deleted by Start Over).",
        "The grave's Done writes an Epitaph changed record when the epitaph's text changed.",
        "Every villager the game's own creators make is noted as an arrival; after each save the village is compared with the roster kept at the save before, and any departure with no Death or Disappeared record, or arrival with no known arrival, is written to the Unaccounted Villagers log.",
        f"The roster is kept in 'Virtual Villagers Fun Patcher Data\\Unaccounted Villagers\\Virtual Villagers {n} Village Roster - Save <n>.dat' (written atomically; deleted by Start Over).",
        "Arrivals: a villager a creator made that is neither a birth (the path's own return addresses, read at fixed places on the stack, or the Births and Conceptions log's note) nor a record the game takes away again is decided at the next tick, named by its path (Founder, the island event, Barrel of Babies), and gets an Arrived record at the next save of that village (at its departure if it leaves first); the Story / Cheat Upgrades DLL names the Custom Island Event's (VvfpCauseArrivedBy)" + ("; a Heathen made by a creator is not one, and a Heathen whose faction byte +0x1CEC the tick sees cleared is (\"Converted from the Heathens\")" if game == "vv5" else "") + ". A founder is written only at a save with no village saved in the slot before.",
        f"Arrivals before this record existed: VvfpCauseScanArrivals counts, writing nothing, the villagers (believers{', with no parents on their record' if game != 'vv1' else ''}) the village's Births and Conceptions log has no Birth or Arrived record for (name, head and body), for the first-load check; VvfpCauseRepairArrivals records the answer. Only after Repair, at the next save, each gets an Arrived record filed by RecordArrivalsMissingFromLog in \"VVFP Parentage Export.dll\", and none is an Unaccounted record; once all are on disk 'Virtual Villagers Fun Patcher Data\\Arrivals\\Virtual Villagers {n} Arrivals Recorded - Save <n>.dat' (deleted by Start Over) ends the backfill for good.",
        "All records are written through WriteVillageRecord in \"VVFP Parentage Export.dll\".",
    ]
    non_changes = [
        "This row changes no executable bytes: the Origins companion loads the DLL, which detours the listed sites at run time only after verifying every site's stock bytes; any other build installs nothing.",
        "No game value is changed: health, age, the graves, the Roster of the Dead and the save are only read; each detoured site's own instructions run unchanged after the check.",
    ]
    if game == "vv1":
        non_changes.append("Nothing is written into the game's grave table or a villager record; the cause and epitaph live only in the patcher's .dat file. The epitaph's two-way choices use the companion's own random numbers, never the game's.")
    elif game == "vv2":
        non_changes.append("Nothing is written into the game's grave table or a villager record; the cause lives only in the patcher's .dat file.")
    record = {
        "id": f"{game}_cause_of_death",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": NAMES[game],
        "description": description(game),
        "output_tag": "Cause of Death",
        "dependencies": [f"{game}_enable_origins_exclusive_features"],
        "needs_on": [{"id": f"{game}_write_parentage_log",
                      "for": "the Deaths and Unaccounted Villagers logs, which that patch's DLL writes (without it neither is written)"}],
        "behavior_changes": changes,
        "explicit_non_changes": non_changes,
        "companion_files": [
            {"source": "assets/cause_of_death/VVFP Cause of Death.dll",
             "destination": "VVFP Cause of Death.dll", "sha256": sha},
        ],
        "patches": [],
        "runtime_detours": detours,
    }
    return record


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
        out = ROOT / "data" / f"{game}_cause_of_death_feature.json"
        out.write_text(json.dumps(manifest(game, sha), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
