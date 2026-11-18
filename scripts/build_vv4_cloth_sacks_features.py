"""Write The Tree of Life's "Cloth Sacks for Yellow Fruit" row (data/vv4_cloth_sacks_for_yellow_fruit_feature.json) and
"Cutting Tool Harvest Caption" (data/vv4_cutting_tool_harvest_caption_feature.json).

The owner (2026-11-17): the Clothing Hut's extra cloth bolts get a use -- an adult dropped on the left side of the
Clothing Hut, under its awning, makes a sack from one bolt, gathers the yellow fruit in it and brings 30 fruit to
the food bin, working "like the cutting tool on the blackberries in every respect".  Then: "farmers should never use cutting
tools or sacks on their own" (only a villager the player drops makes a sack) and "if the cutting tools allow
harvesting with less than 3 fruit, so should the sacks" (no fruit check at the drop).  Off by default, on in
Owner's Defaults.  And: a villager harvesting blackberries with a cutting tool says
so ("Harvesting berries with a cutting tool"), its own row, also off by default and on in Owner's Defaults.

"VVFP VV4 Cloth Sacks.dll" (native/vvfp_vv4_cloth_sacks) and "VVFP VV4 Harvest Caption.dll"
(native/vvfp_vv4_harvest_caption) do it at run time, started by VVFP Startup.dll from its second word; each source
says what it changes and why.  tests/test_vv4_cloth_sacks.py proves both by emulation.

One command after a DLL's source changes: this script builds both (scripts/build_vvfp_vv4_cloth_sacks.ps1,
scripts/build_vvfp_vv4_harvest_caption.ps1) and pins them and the sack pictures by SHA-256.  --no-build pins what is
already built.  The art (the owner's, 2026-11-17) is assets/cloth_sacks/vvfp_sack_empty.png (60 x 65) and
vvfp_sack_yellow_fruit.png (60 x 87), 8-bit RGBA.
"""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = "vv4_cloth_sacks_for_yellow_fruit"
NAME = "Cloth Sacks for Yellow Fruit"
DLL_NAME = "VVFP VV4 Cloth Sacks.dll"
DLL = ROOT / "assets" / "cloth_sacks" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
PICTURES = (("vvfp_sack_empty.png", 60, 65), ("vvfp_sack_yellow_fruit.png", 60, 87))
LIMITED = "vv4_yellow_fruit_trees_limited"
LIMITED_NAME = "Yellow Fruit Trees are No Longer Unlimited"
SACK_FRUIT = 30

CAPTION_ID = "vv4_cutting_tool_harvest_caption"
CAPTION_NAME = "Cutting Tool Harvest Caption"
CAPTION_DLL_NAME = "VVFP VV4 Harvest Caption.dll"
CAPTION_DLL = ROOT / "assets" / "harvest_caption" / CAPTION_DLL_NAME
CAPTION = "Harvesting berries with a cutting tool"
CAPTION_INSTALLED_BY = f"{CAPTION_DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"

SITES = (
    (0x46E460, "83EC08568B742410",
     "the drop dispatcher 0x46E460 (a villager dropped: its place 0x45ED00, the map's area there 0x46C410, that "
     "area's handler): an adult (+0x1B8C >= 0x118), not expecting (+0x1C4C), under the finished Clothing Hut's "
     "awning (puzzle 0x16; the hut's place, its object 0x4D82D8 +0x28/+0x2C, plus x -10..54, y 40..134) with the "
     "Cooking Pit restored (puzzle 6) starts the sack trip, or gets a refusal; anything else goes on to the stock "
     "dispatcher"),
    (0x4642F0, "8B44240483EC18",
     "the job events 0x4642F0: events 0x75, 0x76 and 0x77 (the sack made, the sack full, the sack's food at the "
     "bin; above 74, which the game's own table sends to its end 0x464EB2) are the companion's; every other event "
     "goes on to the stock code"),
    (0x4667B4, "E8875EFEFF",
     "the carried item's draw 0x466770, its call of the world draw 0x44C640: for a villager on a sack trip that "
     "carries the sack, the sack's picture at 45% instead of carrying.png's cell, then the same call"),
)
CAPTION_SITE = (0x451CF6, "6A27508D86E41C0000",
                "the cutting-tool harvest 0x451CE0 (action 0xBE), copying its caption (push 0x27 / push eax, the looked-up "
                "text 0x280 / lea eax, [esi+0x1CE4]; then push eax / call 0x4724E0 at 0x451CFF): the companion's "
                "caption is pushed instead")


def picture(name: str, width: int, height: int) -> dict:
    data = (ROOT / "assets" / "cloth_sacks" / name).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", data[16:24]) != (width, height) \
            or (data[24], data[25]) != (8, 6):
        raise SystemExit(f"assets/cloth_sacks/{name} must be an 8-bit RGBA PNG of {width} x {height}")
    return {"source": f"assets/cloth_sacks/{name}", "destination": f"Images/{name}", "sha256": sha_bytes(data)}


def description() -> str:
    return (
        "The Clothing Hut's extra cloth bolts get a use: sacks for the yellow fruit (the breadfruit of the Cooking "
        "Pit; nothing else). Drop an adult on the LEFT side of the finished Clothing Hut, under its awning, once the "
        "Cooking Pit is restored: the villager takes one cloth bolt, stands at the hut \"Making a sack out of "
        "cloth\" (the research look), carries the empty sack to the yellow fruit trees (\"Gathering food in cloth "
        "sack\"), shakes down and cooks the fruit as on any fruit trip, and carries the full sack to the food bin "
        f"(\"Carrying fruit to the food bin\"): {SACK_FRUIT} food, before Food Mastery. It works like the cutting "
        "tool on the blackberries: the cloth bolt is used when the villager starts, whatever happens later (a "
        "failed Farming check or an interrupted trip loses it, as a cutting tool is lost); with no cloth the "
        "villager refuses (\"They need cloth for this!\"); the food is 1 for each fruit, at most 30, paid at the "
        "food bin, and Food Mastery multiplies it exactly as it multiplies a blackberry harvest (level 2: half as "
        "much again, level 3: doubled) -- no other technology or setting changes it. Like a blackberry harvest, a "
        "sack never goes into the stew and does not count toward The Grand Feast (the cutting-tool harvest's "
        "blackberries do not either). "
        f"**With \"{LIMITED_NAME}\" ticked too, each sack takes its fruit from the tree when it reaches the food "
        f"bin: {SACK_FRUIT}, or what is left when fewer -- even none, as a cutting tool harvests a nearly bare bush "
        "(the cloth bolt is still used).** Without it the trees are the "
        f"game's own unlimited ones and every sack holds {SACK_FRUIT}. All four places at the Cooking Pit taken: "
        "the villager refuses as at the tree. Only a villager you drop at the hut makes a sack: farmers who "
        "decide to farm by themselves never do, as they never harvest with a cutting tool. The sacks are drawn with Lorsieab2's art. Nothing is written to the save or anywhere else. "
        "**Needs no other patch.** **Off by default; Owner's Defaults ticks it.** **Unverified in play: the effect "
        f"has not been tested live.** The companion is \"{DLL_NAME}\", started by VVFP Startup.dll; if the DLL "
        "cannot be loaded, the stock game runs."
    )


def row(dll_sha: str) -> dict:
    return {
        "id": ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": NAME,
        "description": description(),
        "output_tag": "Cloth Sacks",
        "dependencies": [],
        "behavior_changes": [
            "The model, the cutting tool on the blackberries (stock): the drop on map area 0x31 (0x46E7E0) refuses "
            "with action 0x1A and text 0x12F when no tool is on hand ([0x4D8618] = 0); otherwise one tool is used at "
            "once (0x4369F0(1) on 0x4D8614, 0x46E872) and the harvest starts (action 0xBE, 0x451CE0: the walk to the "
            "bushes, the cuts, the Farming check 0x469220(0), the berries carried, item 0x3E, the walk to the food "
            "bin, job event 14). Job event 14 (0x4644EE): n = the berries left, at most 30; the food writer "
            "0x41D920(n), Food Mastery inside it; the berries -= n; fewer than 3 left: the villager's task cleared "
            "(+0x1C54); over 2,000 food: tip 0x2E5. No farmer the game sends ever harvests with a tool, and the "
            "harvest's item 0x3E is not one of the Grand Feast's (the stew pot's listener 0x42EA30 counts items 0, "
            "0x37, 0x38 and 0x76..0x78 only, table 0x42EB4C).",
            "The drop (0x46E460, before the stock dispatcher): an adult, not expecting, under the finished Clothing "
            "Hut's awning, the Cooking Pit restored: no cloth ([0x4D8ACC] = 0): action 0x1A with text 0x136 (\"They "
            f"need cloth for this!\"); the fruit left is not checked (the tool does not check the berries); the pit's four spot locks (5..8 at 0x705148, 0x46D880) all taken: the task cleared and "
            "action 0x1A with text 0x13C (the tree's start 0x4343A0's own refusal); otherwise one cloth bolt is "
            "used (0x4369F0(1) on 0x4D8AC8, the cutting tools' own routine) and the sack trip is queued.",
            "The sack trip, with the game's own step builders: a caption step (0x468CF0) \"Making a sack out of "
            "cloth\", the cloth carried (item 0x35), the Researching action's two animations and waits (0x469CD0(1, "
            "1.0, 2), 0x469280(6), 0x469CD0(0x67, 0.5, 2), 0x469280(6); 0x4537A9..0x45380E), job event 0x75 (the "
            "empty sack shows), a caption step \"Gathering food in cloth sack\", then the game's own fruit trip "
            "(do-action 0x64, 0x4343A0: a free spot picked by rand and that spot's trip 0x65..0x68 built: the walk "
            "to the trees, the shaking, the Farming check, the fruit, the walk to the pit, the cooking). From that "
            "trip's last caption step (\"Carrying fruit to the food bin\", or \"Adding to the stew\" when the stew "
            "wanted the fruit, 0x4349A3) its steps are replaced by: the caption 0x240 (\"Carrying fruit to the food "
            "bin\"), job event 0x76 (the full sack shows), item 0x36 carried, the walk to the food bin (area 8), the "
            "trip's own 1-second wait and put-down, and job event 0x77: the sack's food. The trip's own job event 15 "
            "(3 food) is therefore never queued, and the stew is never given the sack.",
            f"Job event 0x77 (as event 14): n = {SACK_FRUIT}; with {LIMITED}, n = the fruit left, at most "
            f"{SACK_FRUIT}, taken from the tree (VvfpYellowFruitTake of \"VVFP VV4 Fruit Supply.dll\", found with "
            "GetProcAddress); 0x41D920(n); with the limited tree and fewer than 3 fruit left, the villager's task "
            "cleared; over 2,000 food, tip 0x2E5.",
            "The pictures: the carried item's draw (0x466770, its call of 0x44C640 at 0x4667B4) draws "
            "Images\\vvfp_sack_empty.png (carrying item 0x35 after event 0x75) or Images\\vvfp_sack_yellow_fruit.png "
            "(item 0x36 after event 0x76) for a villager whose queue still holds event 0x77, at scale 0.45, 6 "
            "pixels right and 1 down / 9 up, instead of carrying.png's cell; built once by ldwImageGrid 0x40AB10 "
            "(name, 1, 1) after the PNG header says 8-bit RGBA 60 x 65 / 60 x 87; a missing or wrong file: the "
            "game's own picture (the cloth, the yellow fruit).",
            "The captions go through VVFP Translations.dll (rows vvfp.cloth_sacks/vvfp_vv4_cloth_sacks."
            "caption_making.s0 and .caption_gathering.s0), at most 38 letters (the caption field takes 39).",
        ],
        "explicit_non_changes": [
            "The Farming dispatcher 0x4639B0 is not touched: farmers the game sends never make a sack, as they never "
            "harvest with a cutting tool (the owner, 2026-11-17).",
            "The cutting tool, the blackberries, picking, the fruit trips a player or the game starts at the tree, "
            "their 3 fruit and 3 food, the stew, the Cooking Pit bonus while catching up and the cloth's other uses "
            "(the fishing nets, new clothes on the rest of the hut) are the game's own.",
            "Food Mastery is the only technology that changes a sack's food, inside the game's own food writer, as "
            "for a blackberry harvest; the difficulty and every other setting do not.",
            "No executable byte is patched: the companion writes its 3 jumps and calls at run time, only after "
            "verifying every stock byte (and the stock code it relies on), all or none; a different build installs "
            "nothing.",
            "Nothing is written to a save, a villager record's saved fields or a file. A queue the game keeps holds "
            "only the game's own steps and the job events 0x75..0x77, which the stock game ignores.",
            "The game's pictures are never changed: the sacks are new files in Images, drawn only by the companion.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; emulated on the stock executable (the drop, "
                            "the refusals, a whole trip to the food bin, the food with Food Mastery beside the "
                            "stock cutting-tool harvest's, the limited tree's take, farmers never choosing it, "
                            "the pictures' draw) in tests/test_vv4_cloth_sacks.py; runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/cloth_sacks/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ] + [picture(*p) for p in PICTURES],
        "patches": [],
        "runtime_detours": [{
            "va": f"0x{va:X}",
            "stock_bytes": stock,
            "written_bytes": ("E8" if stock.startswith("E8") else "E9") + "XXXXXXXX" + "90" * (len(stock) // 2 - 5),
            "routine": routine,
            "installed_by": INSTALLED_BY,
        } for va, stock, routine in SITES],
    }


def caption_description() -> str:
    return (
        "A villager harvesting blackberries with a cutting tool (dropped where the tribe's cutting tools are "
        f"used on the blackberries) now says \"{CAPTION}\" instead of \"Harvesting blackberries\", so it can be "
        "told apart from picking. Picking blackberries and every other caption are unchanged. The words are "
        "shortened from \"Harvesting blackberries with a cutting tool\" because the game's caption holds at most "
        "39 letters. **Needs no other patch.** **Off by default; Owner's Defaults ticks it.** **Unverified in "
        f"play: the effect has not been tested live.** The companion is \"{CAPTION_DLL_NAME}\", started by VVFP "
        "Startup.dll; if the DLL cannot be loaded, the stock caption shows."
    )


def caption_row(dll_sha: str) -> dict:
    va, stock, routine = CAPTION_SITE
    return {
        "id": CAPTION_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": CAPTION_NAME,
        "description": caption_description(),
        "output_tag": "Cutting Tool Caption",
        "dependencies": [],
        "behavior_changes": [
            "Picking (action 99, 0x451C30) and the cutting-tool harvest (action 0xBE, 0x451CE0) both copy text 0x280 "
            "\"Harvesting blackberries\" into the villager's caption (+0x1CE4, 0x27 letters, 0x4724E0); the harvest's "
            f"copy (0x451CF6) now copies \"{CAPTION}\" (38 letters), translated through VVFP Translations.dll (row "
            "vvfp.harvest_caption/vvfp_vv4_harvest_caption.caption.s0).",
        ],
        "explicit_non_changes": [
            "Picking, the harvest itself (the tool used, the berries, the food) and every other caption are the "
            "game's own; the game's text table is not changed.",
            "No executable byte is patched: the companion writes one jump at run time after verifying the site and "
            "the code around it; a different build installs nothing. Nothing is written anywhere.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; the harvest's and the pick's captions "
                            "emulated in tests/test_vv4_cloth_sacks.py; runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/harvest_caption/{CAPTION_DLL_NAME}", "destination": CAPTION_DLL_NAME,
             "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [{
            "va": f"0x{va:X}",
            "stock_bytes": stock,
            "written_bytes": "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
            "routine": routine,
            "installed_by": CAPTION_INSTALLED_BY,
        }],
    }


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        for script in ("build_vvfp_vv4_cloth_sacks.ps1", "build_vvfp_vv4_harvest_caption.ps1"):
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(ROOT / "scripts" / script)], check=True)
    for path, data in ((ROOT / "data" / f"{ID}_feature.json", row(sha(DLL))),
                       (ROOT / "data" / f"{CAPTION_ID}_feature.json", caption_row(sha(CAPTION_DLL)))):
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
