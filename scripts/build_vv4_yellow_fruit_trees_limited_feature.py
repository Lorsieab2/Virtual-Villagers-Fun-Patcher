"""Write "Yellow Fruit Trees are No Longer Unlimited" (The Tree of Life) -- data/vv4_yellow_fruit_trees_limited_feature.json
-- and "Yellow Breadfruit Refills Partially Every Time", which needs it -- data/vv4_yellow_fruit_refills_partially_feature.json.

The owner (2026-11-08): the Cooking Pit's yellow fruit tree gets a limited supply -- at most 1,000 fruit, refilled to
full every 40 age units, like A New Home's and The Lost Children's crops; 3 fruit for each trip's food (and each
stomped fruit that goes into the stew), 5 for each catch-up Cooking Pit bonus; an empty tree refuses villagers and is
not offered by the farming dispatcher; the count kept in a sidecar .dat per save, never in the save; the remaining
fruit shown in the game when the tree is clicked.  Off by default; Owner's Defaults and Classic VV Difficulty tick it.

"VVFP VV4 Fruit Supply.dll" (native/vvfp_vv4_fruit_supply) does all of it at run time, started by VVFP Startup.dll
from its second word; tests/test_vv4_yellow_fruit_trees_limited.py proves it by emulation.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_vv4_fruit_supply.ps1) and pins
it by SHA-256.  --no-build pins what is already built.

THE PICTURES.  The DLL draws one 256 x 256 picture over the two trees by the fruit left: the stages are ONE table,
FS_STAGES in native/vvfp_vv4_fruit_supply/vvfp_vv4_fruit_supply.c, which this script reads for the row's words (change
the numbers there only).  New art (the owner's): replace assets/fruit_supply/vvfp_fruit_tree_5.png .. _0.png (8-bit RGBA,
256 x 256, top-left on world (0, 1664): the section (0, 128)-(256, 384) of MapX0Y3.jpg; the base to paint on is
assets/fruit_supply/yellow_fruit_trees_map_section.png), then run this script (--no-build); it checks and pins each
picture by SHA-256.  scripts/vv4_fruit_tree_mockups.py previews the six stages on the game's own map.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = "vv4_yellow_fruit_trees_limited"
NAME = "Yellow Fruit Trees are No Longer Unlimited"
DLL_NAME = "VVFP VV4 Fruit Supply.dll"
DLL = ROOT / "assets" / "fruit_supply" / DLL_NAME
SOURCE = ROOT / "native" / "vvfp_vv4_fruit_supply" / "vvfp_vv4_fruit_supply.c"
ART_SIZE, ART_X, ART_Y = 256, 0, 1664     # MapX0Y3.jpg is tile (0, 3) at (0, 1536); the trees' section is (0, 128)
SIDECAR = ("Virtual Villagers Fun Patcher\\Save <S>\\Data\\Fruit Trees\\"
           "Virtual Villagers 4 Yellow Fruit Tree - Save <S>.dat")
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"

# Yellow Breadfruit Refills Partially Every Time (the owner, 2026-11-11): with the limited tree, refill at The Secret
# City's pace -- every 30 age units (3 hours on Normal) the tree gains floor(units x 37 / 10), 111, up to 1,000 --
# instead of to full every 40.  The same companion does it (FS_PARTIAL_* in its source) while the row's one file, the
# flag below, is in the patcher's folder; the row needs the limited tree (its dependency) and ships no code.
PARTIAL_ID = "vv4_yellow_fruit_refills_partially"
PARTIAL_NAME = "Yellow Breadfruit Refills Partially Every Time"
PARTIAL_FLAG = "VVFP VV4 Fruit Partial Refill.txt"
PARTIAL_UNITS, PARTIAL_PER_10_UNITS = 30, 37
PARTIAL_GAIN = PARTIAL_UNITS * PARTIAL_PER_10_UNITS // 10        # 111

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
    (0x4400AD, "B920CB4C00",
     "the village draw 0x440050, after the map tiles (0x46FE10) and before the map's overlay list (mov ecx, "
     "0x4CCB20 / call 0x41C370): the fruit trees' picture at (0, 1664) minus the scroll, then the stock mov"),
    (0x445426, "B920CB4C00",
     "the Overview Map draw 0x4453C0, before the map's overlay list (mov ecx, 0x4CCB20 / call 0x41C5B0, its left, "
     "top and scale pushed): the fruit trees' picture where the list puts a picture of (0, 1664), then the stock mov"),
)
VTABLE = 0x48E890
EVENT_SLOT_VA = 0x4CCA74       # the island-event table 0x4CCA28's slot 19, NULL in the stock game
EVENT_GAIN = 350               # fruit the event adds (the berry event's +350, 0x414B38); the owner gave no amount
SLOTS = ((4, 0x433CB0, "save: the companion writes the tree's file, then the stock save"),
         (3, 0x433820, "load: the stock load, then the file is read again at the next use"))


FULL_FRUIT = 1000
STAGE_WORDS = ("5 fruits on each tree", "4 fruits on each tree", "3 fruits on each tree", "2 fruits on each tree",
               "1 fruit on each tree", "no fruit on either tree")


def stages() -> list[tuple[int, str | None]]:
    """FS_STAGES from the DLL's source: (from, picture or None), the most fruit first, the last from 0."""
    text = SOURCE.read_text(encoding="utf-8")
    body = re.search(r"static const fs_stage FS_STAGES\[\] = \{(.*?)\n\};", text, re.S).group(1)
    rows = [(int(a), None if b == "NULL" else b.strip('"'))
            for a, b in re.findall(r"\{\s*(\d+),\s*(NULL|\"[^\"]+\")\s*\}", body)]
    assert rows and rows[-1][0] == 0 and all(x[0] > y[0] for x, y in zip(rows, rows[1:])), rows
    return rows


def stage_ranges() -> list[tuple[int, int, str | None]]:
    """(lowest, highest, picture) of each stage."""
    rows = stages()
    tops = [FULL_FRUIT] + [r[0] - 1 for r in rows[:-1]]
    return [(low, top, name) for (low, name), top in zip(rows, tops)]


def pictures() -> list[str]:
    return [name for _, _, name in stage_ranges() if name is not None]


def art_file(name: str) -> dict:
    data = (ROOT / "assets" / "fruit_supply" / name).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", data[16:24]) != (ART_SIZE, ART_SIZE) \
            or (data[24], data[25]) != (8, 6):
        raise SystemExit(f"assets/fruit_supply/{name} must be an 8-bit RGBA PNG of {ART_SIZE} x {ART_SIZE}")
    return {"source": f"assets/fruit_supply/{name}", "destination": f"Images/{name}",
            "sha256": hashlib.sha256(data).hexdigest().upper()}


def shows(i: int, name: str | None) -> str:
    return STAGE_WORDS[i] if i < len(STAGE_WORDS) else str(name)


def ranges_text() -> str:
    def span(low: int, top: int) -> str:
        return f"{low:,}" if low == top else f"{low:,} to {top:,}"
    return "; ".join(f"{span(low, top)} fruit: {shows(i, name)}" for i, (low, top, name) in enumerate(stage_ranges()))


def description() -> str:
    return (
        "The yellow fruit tree of the Cooking Pit no longer gives fruit without end. It holds at most 1,000 fruit "
        "and is refilled to full every 40 age units (4 hours of play on Normal speed, 2 on Fast, 6 hours 40 "
        "minutes on Slow), counted as the game counts its villagers' ages, so time away (as far as the game "
        "counts it) and Time Warp count too -- like A New Home's and The Lost Children's crops. "
        f"**With \"{PARTIAL_NAME}\" ticked too, it is not refilled to full: it gains {PARTIAL_GAIN} fruit every "
        f"{PARTIAL_UNITS} age units (3 hours on Normal), up to 1,000, as The Secret City's fruit trees do.** "
        "Each fruit trip "
        "takes 3 fruit when its food is put in the food bin, and a stomped fruit that goes into the stew takes "
        "3 when it is put in the pot; a failed Farming check or an interrupted trip takes nothing. While catching "
        "up, each Cooking Pit bonus takes 5 fruit, and pays nothing when fewer than 5 are left. With fewer than 3 "
        "fruit left, a villager dropped on the tree refuses, as at an empty blackberry bush (\"Refusing\", and "
        "\"There is not enough to harvest.\" when it is the selected villager), and villagers deciding to farm are "
        "not sent there. Click the tree to see "
        "how much fruit is left (\"Fruit remaining: N\" on the game's own status line, as the blackberry bush "
        "shows its berries). The two trees are drawn with the fruit they have left (art by Lorsieab2), over the map's own picture of them (the map is never "
        f"changed): {ranges_text()}; the same picture on the Overview Map. A new village starts with a full tree. "
        "Technologies and effects: Food Mastery "
        "multiplies the food a trip or a bonus pays, never the fruit taken (3 and 5 are taken before it); "
        "Construction (the pit's debris) and Dendrology gate other steps and puzzles, not the fruit; the "
        "difficulty changes only meals; the stew takes fruit as above; the Purify Tree, the Tree of Life, the "
        "Nursery's \"Showing baby the cooking area\" and the island event that needs the restored pit take no "
        "fruit; Time Warp and Choose Time Skip Amount add age units, so the tree refills for them too. "
        "A Custom Island Event (Story / Cheat Upgrades) that refills the food sources fills the tree to 1,000 "
        "too; no island event of the game's own refills it. The patch also adds one island event, \"A Closer "
        f"Look\" about the breadfruit: a farmer finds leftover fruit and the tree gains {EVENT_GAIN} fruit (to at "
        "most 1,000). It can happen once the Cooking Pit is restored and someone lives in the village, with an "
        "equal chance among the island events that can happen then; without this patch it does not exist. In "
        "Pick Island Event the two are \"A Closer Look (Blackberries)\" and \"A Closer Look (Yellow "
        "Breadfruit)\". The count is kept beside the save, in "
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
    detours.append({
        "va": f"0x{EVENT_SLOT_VA:X}",
        "stock_bytes": "00000000",
        "routine": "the island-event table 0x4CCA28's slot 19 (empty in the stock game): the companion's "
                   "A Closer Look (Yellow Breadfruit) event object",
        "installed_by": INSTALLED_BY,
    })
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
            "processed, re-chosen when it is no longer alive -- health 0 or the death flag +0x1CC7, buried "
            "or not -- or its record changes) counts; at 40 the tree is set to 1,000 "
            "and the count starts again. This is live and catch-up alike, so time away as the game's aging "
            "counts it (it clamps a long absence) and Time Warp both count. With " + PARTIAL_ID + " (its file "
            f"\"{PARTIAL_FLAG}\" in the patcher's folder when the game starts) the count goes to {PARTIAL_UNITS} "
            f"instead and the tree gains floor(count x {PARTIAL_PER_10_UNITS} / 10) -- {PARTIAL_GAIN} -- up to "
            "1,000.",
            "A Custom Island Event's \"Refill the food sources\" (VVFP Story Upgrades.dll, c4_refill) calls this "
            "companion's export VvfpYellowFruitRefill (found with GetProcAddress; nothing when this companion is "
            "not loaded): the tree is set to 1,000 for the village on screen (read from its file first when the "
            "village was just loaded); the 40-unit count runs on; the file is written at the next save, with it.",
            "One more island event, A Closer Look (Yellow Breadfruit): the companion's own object in the event "
            "table's slot 19 (0x4CCA74, NULL in the stock game: the builder 0x416FF0 never writes it), which the "
            "selector 0x418000 collects like any other slot (1..49, NULL skipped at 0x418057; one of the possible "
            "ones by rand(n), 0x4180A6), so the 8-15 h timer, the Island Events Seen count and the rescue rule "
            "(slot 25) are unchanged. The object copies A Closer Look's vtable 0x48C84C (title id 0x342) with its "
            "own condition (the Cooking Pit restored, 0x438960(6), then the berry event's 0x415E00: a living "
            "villager of any age, 0x4679B0(-1,-1,-1,1,1,-1,0,0,0)), text id 0x2E7 (an id with no string entry "
            "that no code pushes; its index slot 0x4DEA20+4*id points at the companion's text, by key "
            "vvfp.fruit_supply/vvfp_vv4_fruit_supply.ev_text_id.s0 in the player's language), result "
            f"(+{EVENT_GAIN} fruit, at most 1,000; then, as the berry event moves its farmer to the bushes, the "
            "villager's queue is cleared (0x468C60) and they walk to the tree, map area 38, the first walk of every "
            "\"Shaking down some fruit!\" action 0x65..0x6A: 0x468FC0(38, 100, 0), 0x46A030) and "
            "a delete that frees nothing (the exit teardown 0x417760 calls it).",
            "Message 2 to the tree's area handler 0x435970 (the tree clicked; ignored by the stock game) shows "
            "\"Fruit remaining: N\" on the status line 0x4DB8E8 through 0x44C3A0, for 5 seconds, as the bush "
            "shows \"Berries remaining: \" (0x46F82A, text 0x115). The words go through VVFP Translations.dll "
            "(row vvfp.fruit_supply/vvfp_vv4_fruit_supply.on_click.s0).",
            f"The file {SIDECAR}: magic 'VV4F', version 1, game 4, slot, fruit, age units since the last refill, "
            "the number of living villagers and their 256 identities by record (FNV-1a of gender, name and "
            "parents' names, as the Origins companion's); written atomically when the game saves the puzzles "
            "(CFruitwells slot 4), read after the game loads them (slot 3) and used only while at least one of "
            "its villagers is alive in the village. An unreadable file is never replaced; an invalid one is set "
            "aside. A file that exists but cannot be read when the village is bound (locked, a read failed) is "
            "never bound over: until it is read -- retried at most every 2 seconds, the sidecar gate's throttle -- "
            "the tree is the stock game's (no refusal, nothing taken, no refill counted, the event and the Custom "
            "Island Event refill change nothing) and nothing is written; then the saved fruit and refill progress "
            "are restored.",
            "The pictures (FS_STAGES, the one table of the stages in the companion's source): "
            f"{ranges_text()}. Over the map tile MapX0Y3.jpg's section (0, 128)-(256, 384) (the tile is (0, 3) of "
            "the 4 x 4 grid of 512 x 512 tiles 0x46FCE0 builds at (512 x, 512 y)), world (0, 1664)-(256, 1920), "
            "the companion draws Images\\" + ", Images\\".join(pictures()) + " (256 x 256 RGBA, top-left at "
            "(0, 1664)); no village bound, or its file not read yet (pending): nothing, the map's own trees. "
            "Village (0x440050): after the map tiles (0x46FE10 at 0x4400A8), just before the map's overlay list "
            "(0x41C370, list 0x4CCB20) and as it draws, through 0x409960 at (0, 1664) minus the scroll "
            "([0x72563C], [0x725640]); everything after (the list, the queued sprites, the villagers) is drawn "
            "over it. Overview Map (0x4453C0): just before the list (0x41C5B0 at 0x44542B, origin (188, 61), "
            "scale 0.20703125), as the list draws: through 0x409AD0 at ftol(0 x scale) + 188, ftol(1664 x scale) + "
            "61 and the list's whole percent (20 cut by _ftol; 21 when Fix Vanilla Bugs rounds the list's at "
            "0x41C5CB). Each picture is built once by the game's own ldwImageGrid 0x40AB10 (name, 1, 1), the image "
            "kind the list draws, only after its PNG header says 8-bit RGBA 256 x 256; a missing or wrong file is "
            "never drawn.",
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
            "No executable byte is patched: the companion writes its 10 jumps, 2 vtable slots and the event "
            "table's empty slot 19 at run time, only "
            "after verifying every stock value, all or none; a different build installs nothing.",
            "The save is never written, so removing the patch leaves the tree unlimited as in the stock game; the "
            "file stays beside the save, unused (Start Over empties the save's folder).",
            "The trips, the Farming check and its practice, the stew, the bonus odds and amounts, Food Mastery "
            "and every other food source are the game's own.",
            "The map tiles (MapX0Y3.jpg included) and every other picture are never changed; the fruit trees' "
            "pictures are new files in Images, drawn only by the companion.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; emulated stock and patched (trips, refusal, "
                            "dispatcher, task gate, stew, catch-up bonus, refill, file, Start Over, the pictures' "
                            "draws in the village and on the Overview Map) in "
                            "tests/test_vv4_yellow_fruit_trees_limited.py; runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/fruit_supply/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ] + [art_file(name) for name in pictures()],
        "patches": [],
        "runtime_detours": detours,
        # The companion's one table of the stages (FS_STAGES), as written here for Game Mechanics to read.
        "fruit_tree_stages": [{"from": low, "to": top, "picture": name, "shows": shows(i, name)}
                              for i, (low, top, name) in enumerate(stage_ranges())],
    }


def partial_description() -> str:
    return (
        f"With \"{NAME}\", the Cooking Pit's yellow fruit tree is no longer refilled to full every 4 hours: it "
        f"refills at The Secret City's pace instead, gaining {PARTIAL_GAIN} fruit every 3 hours of play on Normal "
        "speed (1 hour 30 minutes on Fast, 5 hours on Slow), up to 1,000 -- 37 fruit an hour, as The Secret City's "
        "fruit trees gain. The time is counted as the game counts its villagers' ages, so time away (as far as the "
        "game counts it) and Time Warp count too, in proportion. No technology changes the amount. The "
        f"breadfruit island event (+{EVENT_GAIN}), a Custom Island Event's refill (to 1,000), the fruit each trip "
        "and bonus takes, the refusals at an empty tree and the trees' pictures of the fruit left are unchanged. "
        f"**Needs \"{NAME}\": ticking this patch ticks it too, and unticking that one unticks this one.** "
        "**Off by default, and off in Owner's Defaults.** **Unverified in play: the effect has not been tested "
        f"live.** The patch adds one small file, \"{PARTIAL_FLAG}\", to the patcher's folder, which tells "
        f"\"{DLL_NAME}\" to refill this way; the save and the tree's own file are kept as before."
    )


def partial_row() -> dict:
    return {
        "id": PARTIAL_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": PARTIAL_NAME,
        "description": partial_description(),
        "output_tag": "Breadfruit Refills Partially",
        "dependencies": [ID],
        "behavior_changes": [
            f"\"{DLL_NAME}\" (the {ID} row's companion) checks at start (VvfpStartup) whether \"{PARTIAL_FLAG}\" "
            "is in the patcher's folder (GetFileAttributesW, by full path from the executable's own; the contents "
            "are never read). When it is, the tree's refill count (one per age unit the life tick 0x468430 "
            f"processes for the reference villager, at 0x468AD6) refills at {PARTIAL_UNITS} instead of 40: the tree "
            f"gains floor(count x {PARTIAL_PER_10_UNITS} / 10) fruit -- {PARTIAL_GAIN} at {PARTIAL_UNITS} -- up "
            "to 1,000, and the count starts again. That is The Secret City's fruit-tree refill (0x434760 in its "
            "executable: floor(elapsed x 37 / 3600) once 10,800 game seconds have passed), an age unit being 360 "
            "game seconds (40 are 4 hours on Normal). A count of 30 to 39 kept by the refill to full (a file "
            "written without this row) is paid in proportion at the next unit.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched and no code is added: the row's only file is the flag; the companion and "
            f"its sites are the {ID} row's.",
            "The tree's file keeps its format (the count since the last refill is below 40 either way), so the "
            "patch can be ticked or unticked at any time; the save is never written.",
            "The fruit taken by trips, stews and catch-up bonuses, the refusals, the dispatcher, the island "
            "event's +350, a Custom Island Event's refill to 1,000, the pictures and the click readout are "
            f"unchanged. No technology changes the {PARTIAL_GAIN}: Food Mastery multiplies the food paid, never "
            "the fruit.",
        ],
        "evidence_status": ("implemented in the companion's source; the refill emulated with and without the flag "
                            "(on time, after a long absence, at the cap, a count carried over from the refill to "
                            "full) in tests/test_vv4_yellow_fruit_refills_partially.py; runtime/player confirmation "
                            "pending"),
        "companion_files": [
            {"source": f"assets/fruit_supply/{PARTIAL_FLAG}", "destination": PARTIAL_FLAG,
             "sha256": sha(ROOT / "assets" / "fruit_supply" / PARTIAL_FLAG)},
        ],
        "patches": [],
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
    out = ROOT / "data" / f"{PARTIAL_ID}_feature.json"
    out.write_text(json.dumps(partial_row(), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
