"""Write "Yellow Fruit Trees are No Longer Unlimited" (The Tree of Life) -- data/vv4_yellow_fruit_trees_limited_feature.json.

The owner (2026-11-08): the Cooking Pit's yellow fruit tree gets a limited supply -- at most 1,000 fruit, refilled to
full every 40 age units, like A New Home's and The Lost Children's crops; 3 fruit for each trip's food (and each
stomped fruit that goes into the stew), 5 for each catch-up Cooking Pit bonus; an empty tree refuses villagers and is
not offered by the farming dispatcher; the count kept in a sidecar .dat per save, never in the save; the remaining
fruit shown in the game when the tree is clicked.  Off by default; Owner's Defaults and Classic VV Difficulty tick it.

"VVFP VV4 Fruit Supply.dll" (native/vvfp_vv4_fruit_supply) does all of it at run time, started by VVFP Startup.dll
from its second word; tests/test_vv4_yellow_fruit_trees_limited.py proves it by emulation.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_vv4_fruit_supply.ps1) and pins
it by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = "vv4_yellow_fruit_trees_limited"
NAME = "Yellow Fruit Trees are No Longer Unlimited"
DLL_NAME = "VVFP VV4 Fruit Supply.dll"
DLL = ROOT / "assets" / "fruit_supply" / DLL_NAME
SIDECAR = ("Virtual Villagers Fun Patcher\\Save <S>\\Data\\Fruit Trees\\"
           "Virtual Villagers 4 Yellow Fruit Tree - Save <S>.dat")
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"

# (VA, stock bytes, the routine) -- each a jump to the companion's stub, nops after it.
SITES = (
    (0x46456C, "6A03B9D06D4D00E8A893FBFF",
     "job event 15, the fruit trip's food-bin credit (push 3 / mov ecx, 0x4D6DD0 / call 0x41D920): 3 fruit taken, "
     "or no food and the event's own end 0x464EB0 when fewer than 3 are left"),
    (0x463A38, "C744BC1C0200000083C701",
     "the farming dispatcher 0x4639B0's \"offer the fruit\" (the Cooking Pit restored, not catching up): only while "
     "the tree holds 3 fruit or more"),
    (0x46364E, "8D44240C506A64",
     "the player-task gate 0x4634D0's fruit start (task 2): with fewer than 3 fruit, the empty bush's way out "
     "0x463636 (the task cleared)"),
    (0x4359B8, "8D542408526A64",
     "the drop on the tree (0x435970, message 0, the Cooking Pit restored): with fewer than 3 fruit, action 0x3F with "
     "text 0xA7 (\"There is not enough to harvest.\") as the empty blackberry bush gives (0x46F881), then 0x4359C9"),
    (0x43597A, "83E801755F",
     "the tree's message test (0x435970): message 2 (the tree clicked, which the stock game ignores here) shows "
     "\"Fruit remaining: N\" on the status line 0x4DB8E8 (0x44C3A0); messages 0 and 1 are unchanged"),
    (0x468AAB, "6A05B9D06D4D00E8694EFBFF",
     "the catch-up Cooking Pit bonus's push 5 / call 0x41D920: 5 fruit taken, or with fewer than 5 no food and on "
     "past its Farming practice check to 0x468ACA"),
    (0x468AD6, "8D4E20E872220000",
     "the life tick 0x468430's processed age unit (lea ecx, [esi+0x20] / call 0x46AD50, which every processed unit "
     "reaches): the reference villager's units count toward the refill, then the stock instructions"),
    (0x42EAE7, "C6861F0B000001",
     "the stew's item listener 0x42EA30, item 0x37 (the stomped fruit put in the cauldron): 3 fruit taken (down to "
     "0), then the stock flag"),
)
VTABLE = 0x48E890
SLOTS = ((4, 0x433CB0, "save: the companion writes the tree's file, then the stock save"),
         (3, 0x433820, "load: the stock load, then the file is read again at the next use"))


def description() -> str:
    return (
        "The yellow fruit tree of the Cooking Pit no longer gives fruit without end. It holds at most 1,000 fruit "
        "and is refilled to full every 40 age units (4 hours of play on Normal speed, 2 on Fast, 6 hours 40 "
        "minutes on Slow), counted as the game counts its villagers' ages, so time away (as far as the game "
        "counts it) and Time Warp count too -- like A New Home's and The Lost Children's crops. Each fruit trip "
        "takes 3 fruit when its food is put in the food bin, and a stomped fruit that goes into the stew takes "
        "3 when it is put in the pot; a failed Farming check or an interrupted trip takes nothing. While catching "
        "up, each Cooking Pit bonus takes 5 fruit, and pays nothing when fewer than 5 are left. With fewer than 3 "
        "fruit left, a villager dropped on the tree refuses, as at an empty blackberry bush (\"Refusing\", and "
        "\"There is not enough to harvest.\" when it is the selected villager), and villagers deciding to farm are "
        "not sent there. Click the tree to see "
        "how much fruit is left (\"Fruit remaining: N\" on the game's own status line, as the blackberry bush "
        "shows its berries). A new village starts with a full tree. Technologies and effects: Food Mastery "
        "multiplies the food a trip or a bonus pays, never the fruit taken (3 and 5 are taken before it); "
        "Construction (the pit's debris) and Dendrology gate other steps and puzzles, not the fruit; the "
        "difficulty changes only meals; the stew takes fruit as above; the Purify Tree, the Tree of Life, the "
        "Nursery's \"Showing baby the cooking area\" and the island event that needs the restored pit take no "
        "fruit; Time Warp and Choose Time Skip Amount add age units, so the tree refills for them too. "
        "A Custom Island Event (Story / Cheat Upgrades) that refills the food sources fills the tree to 1,000 "
        "too; no island event of the game's own refills it. The count is kept beside the save, in "
        f"{SIDECAR}, written when the game saves; the save itself is never changed, so without this patch the "
        "tree is simply unlimited again. **Needs no other patch.** **Off by default; Owner's Defaults ticks it, "
        "and it is part of Classic VV Difficulty.** **Unverified in play: the effect has not been tested live.** "
        f"The companion is \"{DLL_NAME}\", started by VVFP Startup.dll; if the DLL cannot be loaded, the stock "
        "game runs."
    )


def row(dll_sha: str) -> dict:
    detours = [{
        "va": f"0x{va:X}",
        "stock_bytes": stock,
        "written_bytes": "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
        "routine": routine,
        "installed_by": INSTALLED_BY,
    } for va, stock, routine in SITES]
    detours += [{
        "va": f"0x{VTABLE + 4 * slot:X}",
        "stock_bytes": struct.pack("<I", stock).hex().upper(),
        "routine": f"the Cooking Pit's (CFruitwells) vtable 0x{VTABLE:X}, slot {slot} ({what}; stock 0x{stock:X}, "
                   "called by the puzzles' save 0x438810 and load 0x4387A0)",
        "installed_by": INSTALLED_BY,
    } for slot, stock, what in SLOTS]
    return {
        "id": ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": NAME,
        "description": description(),
        "output_tag": "Limited Fruit Tree",
        "dependencies": [],
        "behavior_changes": [
            "The tree's supply (0 to 1,000) is the companion's, per village; a new village (no file, or a file whose "
            "villagers are none of this village's: Start Over, another tribe in the slot) starts at 1,000.",
            "Food-bin credit of a fruit trip (job event 15, 0x46456C): 3 fruit taken and the stock 3 food (x Food "
            "Mastery) credited; with fewer than 3 fruit, no food and nothing taken. Nothing is taken at the shake, "
            "the Farming check or the falling-fruit events.",
            "Stew (the stomped fruit 0x37 dropped in the cauldron, the stew's listener 0x42EA30 -> 0x42EAE7): 3 "
            "fruit taken (down to 0) when the cauldron takes it, not when the trip decides to divert (0x4349A3).",
            "Catch-up Cooking Pit bonus (0x468AAB): 5 fruit taken when it pays (its rand(100) is drawn as before); "
            "with fewer than 5, no food and no Farming practice check (0x468AB7..0x468AC5).",
            "With fewer than 3 fruit: a villager dropped on the restored tree gets action 0x3F (\"Refusing\"; text "
            "0xA7, \"There is not enough to harvest.\", on the status line when it is the selected villager), the "
            "empty blackberry bush's refusal (0x46F881..0x46F89C); the "
            "farming dispatcher does not add the fruit to its options (so rand(n) picks among the others, or "
            "none); a task 2 takes the empty bush's way out of the task gate (task cleared).",
            "Refill: every age unit the life tick 0x468430 processes for one reference villager (the first "
            "processed, re-chosen when it dies or its record changes) counts; at 40 the tree is set to 1,000 "
            "and the count starts again. This is live and catch-up alike, so time away as the game's aging "
            "counts it (it clamps a long absence) and Time Warp both count.",
            "A Custom Island Event's \"Refill the food sources\" (VVFP Story Upgrades.dll, c4_refill) calls this "
            "companion's export VvfpYellowFruitRefill (found with GetProcAddress; nothing when this companion is "
            "not loaded): the tree is set to 1,000 for the village on screen (read from its file first when the "
            "village was just loaded); the 40-unit count runs on; the file is written at the next save, with it.",
            "Message 2 to the tree's area handler 0x435970 (the tree clicked; ignored by the stock game) shows "
            "\"Fruit remaining: N\" on the status line 0x4DB8E8 through 0x44C3A0, for 5 seconds, as the bush "
            "shows \"Berries remaining: \" (0x46F82A, text 0x115). The words go through VVFP Translations.dll "
            "(row vvfp.fruit_supply/vvfp_vv4_fruit_supply.on_click.s0).",
            f"The file {SIDECAR}: magic 'VV4F', version 1, game 4, slot, fruit, age units since the last refill, "
            "the number of living villagers and their 256 identities by record (FNV-1a of gender, name and "
            "parents' names, as the Origins companion's); written atomically when the game saves the puzzles "
            "(CFruitwells slot 4), read after the game loads them (slot 3) and used only while at least one of "
            "its villagers is alive in the village. An unreadable file is never replaced; an invalid one is set "
            "aside.",
        ],
        "explicit_non_changes": [
            "Technologies and effects, read from the code: Food Mastery (tech 4) multiplies inside the food writer "
            "0x41D920, after the companion took the base 3 or 5 fruit; Construction (tech 3) gates the pit's debris "
            "(0x433FAD) and Dendrology (tech 5) gates puzzles 12 and 14 (0x437B0B, 0x438477), none of them the "
            "fruit; the difficulty (game+0x170F4) is read by the meals, not the fruit code; the other tests of the "
            "restored pit (0x4168E4 an island event's condition that changes a villager's Farming or health, "
            "0x461B56 the Nursery's \"Showing baby the cooking area\", 0x445FCC / 0x44631F the puzzle screen) take "
            "no fruit; every food-bin credit of fruit, the four spot trips' and the resumed stomping actions' "
            "(0x0F..0x12), is job event 15 and takes 3; Time Warp and Choose Time Skip Amount add age units that "
            "the life tick processes, so they count toward the refill. No island event of the game's own "
            "touches the tree: of the 49 event classes' results (vtable slots 11 and 12) and the routines they "
            "call, only A Closer Look (0x414B38, the blackberries +350) refills a food source, and it stays "
            "berries only (the owner, 2026-11-08).",
            "No executable byte is patched: the companion writes its 8 jumps and 2 vtable slots at run time, only "
            "after verifying every stock value, all or none; a different build installs nothing.",
            "The save is never written, so removing the patch leaves the tree unlimited as in the stock game; the "
            "file stays beside the save, unused (Start Over empties the save's folder).",
            "The trips, the Farming check and its practice, the stew, the bonus odds and amounts, Food Mastery "
            "and every other food source are the game's own.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; emulated stock and patched (trips, refusal, "
                            "dispatcher, task gate, stew, catch-up bonus, refill, file, Start Over) in "
                            "tests/test_vv4_yellow_fruit_trees_limited.py; runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/fruit_supply/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": detours,
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_vv4_fruit_supply.ps1")], check=True)
    out = ROOT / "data" / f"{ID}_feature.json"
    out.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
