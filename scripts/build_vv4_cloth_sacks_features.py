"""Write The Tree of Life's "Cloth Sacks for Yellow Fruit" row (data/vv4_cloth_sacks_for_yellow_fruit_feature.json).

The owner (2026-11-17): the Clothing Hut's extra cloth bolts get a use -- an adult dropped on the left side of the
Clothing Hut, under its awning, makes a sack from one bolt, gathers the yellow fruit in it and brings 30 fruit to
the food bin, working "like the cutting tool on the blackberries in every respect".  Then: "farmers should never use cutting
tools or sacks on their own" (only a villager the player drops makes a sack) and "if the cutting tools allow
harvesting with less than 3 fruit, so should the sacks" (no fruit check at the drop).  On by default (the owner,
2026-11-18) and in Owner's Defaults.

"VVFP VV4 Cloth Sacks.dll" (native/vvfp_vv4_cloth_sacks) does it at run time, started by VVFP Startup.dll from its
second word; its source says what it changes and why.  tests/test_vv4_cloth_sacks.py proves it by emulation.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_vv4_cloth_sacks.ps1)
and pins it and the sack pictures by SHA-256.  --no-build pins what is already built.

THE PICTURES.  The owner's art is assets/cloth_sacks/sack_empty.png, sack_yellow_fruit_raw.png (the shaken fruit,
carried from the trees to the Cooking Pit) and
sack_yellow_fruit.png (the cooked fruit, carried to the food bin).  The game draws carried items at 1:1 from
carrying.png's 40 x 40 cells (the world draw's last argument is the picture's alpha, not a scale), so the shipped
pictures, assets/cloth_sacks/vvfp_sack_*.png, are the owner's art at 45 % (premultiplied Lanczos), carried-item
size; one scale for all three, so the sack body is the same size in every state.  New art: replace the owner's file, run this script with --art (it remakes the shipped pictures; each must
come out at most 40 x 40) and then as usual; the companion centres each picture on the cell by its own size.
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
# (the shipped picture, the owner's art it is made from)
PICTURES = (("vvfp_sack_empty.png", "sack_empty.png"),
            ("vvfp_sack_yellow_fruit_raw.png", "sack_yellow_fruit_raw.png"),
            ("vvfp_sack_yellow_fruit.png", "sack_yellow_fruit.png"))
ART_SCALE = 0.45
CELL = 40
LIMITED = "vv4_yellow_fruit_trees_limited"
LIMITED_NAME = "Yellow Fruit Trees are No Longer Unlimited"
SACK_FRUIT = 30

SITES = (
    (0x46E460, "83EC08568B742410",
     "the drop dispatcher 0x46E460 (a villager dropped: its place 0x45ED00, the map's area there 0x46C410, that "
     "area's handler): an adult (+0x1B8C >= 0x118), not expecting (+0x1C4C), under the finished Clothing Hut's "
     "awning (puzzle 0x16; the hut's place, its object 0x4D82D8 +0x28/+0x2C, plus x -26..70, and y 40..134 or any point the game itself hands to the hut there: its own drop area under the drop point, 0x46C410 = 0x12, built from the hut picture by 0x42FD20 -> 0x46CC50) with the "
     "Cooking Pit restored (puzzle 6) starts the sack trip, or gets a refusal; anything else goes on to the stock "
     "dispatcher"),
    (0x4642F0, "8B44240483EC18",
     "the job events 0x4642F0: events 0x75, 0x76 and 0x77 (the sack made, the sack full, the sack's food at the "
     "bin; above 74, which the game's own table sends to its end 0x464EB2) are the companion's; every other event "
     "goes on to the stock code"),
    (0x4667B4, "E8875EFEFF",
     "the carried item's draw 0x466770, its call of the world draw 0x44C640: for a villager on a sack trip that "
     "carries the sack, the sack's picture (carried-item size, alpha 1.0 as passed) instead of carrying.png's "
     "cell, then the same call"),
)

def make_pictures() -> None:
    """The shipped pictures from the owner's art, at ART_SCALE (only with --art: Pillow's output is pinned)."""
    from PIL import Image
    for shipped, art in PICTURES:
        im = Image.open(ROOT / "assets" / "cloth_sacks" / art).convert("RGBA")
        size = (round(im.width * ART_SCALE), round(im.height * ART_SCALE))
        im.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA").save(ROOT / "assets" / "cloth_sacks" / shipped)


def picture_size(name: str) -> tuple[int, int]:
    data = (ROOT / "assets" / "cloth_sacks" / name).read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    if data[:8] != b"\x89PNG\r\n\x1a\n" or not (0 < width <= CELL and 0 < height <= CELL) \
            or (data[24], data[25]) != (8, 6):
        raise SystemExit(f"assets/cloth_sacks/{name} must be an 8-bit RGBA PNG of at most {CELL} x {CELL}")
    return width, height


def picture(name: str, art: str) -> dict:
    picture_size(name)
    data = (ROOT / "assets" / "cloth_sacks" / name).read_bytes()
    return {"source": f"assets/cloth_sacks/{name}", "destination": f"Images/{name}", "sha256": sha_bytes(data)}


def description() -> str:
    return (
        "The Clothing Hut's extra cloth bolts get a use: sacks for the yellow fruit (the breadfruit of the Cooking "
        "Pit; nothing else). Drop an adult on the LEFT side of the finished Clothing Hut, under its awning, once the "
        "Cooking Pit is restored: the villager takes one cloth bolt, stands at the hut \"Making a sack out of "
        "cloth\" (the research look, without its sounds), carries the empty sack to the yellow fruit trees (\"Gathering food in cloth "
        "sack\"), shakes the fruit down into the sack, carries it to the Cooking Pit and cooks it as on any fruit trip, and "
        "carries the full sack to the food bin "
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
        "the villager refuses as at the tree (\"There is no more room in the cooking pit!\") and no cloth is used; "
        "the villager's place at the pit is kept from the drop, so the pit cannot fill up while the sack is made. Only a villager you drop at the hut makes a sack: farmers who "
        "decide to farm by themselves never do, as they never harvest with a cutting tool. The sacks are drawn with Lorsieab2's art, the size of the game's other carried items: the empty sack, the sack of shaken fruit carried to the Cooking Pit and the sack of cooked fruit carried to the food bin, all three at one scale and standing on one line, so the sack itself is the same size in every state. Nothing is written to the save or anywhere else. "
        "**Needs no other patch.** **On by default (and in Owner's Defaults).** **Unverified in play: the effect "
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
            "used (0x4369F0(1) on 0x4D8AC8, the cutting tools' own routine) and the sack trip is queued. With Fix Vanilla Bugs (vv4_fix_vanilla_bugs, its \"VVFP VV4 Empty Sources.dll\" loaded) and the limited tree at 0 fruit, after the cloth check: action 0x3F with text 0xA7, no cloth used.",
            "The sack trip, with the game's own step builders: the fruit trip's pit-spot claim (its first step, type "
            "0x2E, lock 5..8) copied to the front and run at once, so the spot is the villager's from the drop, as "
            "a stock trip claims its spot at once; a caption step (0x468CF0) \"Making a sack out of "
            "cloth\", the cloth carried (item 0x35), the Researching action's working-pose waits (0x469280(6) twice, "
            "step type 0x0A), not its sound steps (0x469CD0, step type 0x19, a sound at the villager), job event 0x75 (the "
            "empty sack shows), a caption step \"Gathering food in cloth sack\", then the game's own fruit trip "
            "(do-action 0x64, 0x4343A0: a free spot picked by rand and that spot's trip 0x65..0x68 built: the walk "
            "to the trees, the shaking, the Farming check, the fruit, the walk to the pit, the cooking). From that "
            "trip's last caption step (\"Carrying fruit to the food bin\", or \"Adding to the stew\" when the stew "
            "wanted the fruit, 0x4349A3) its steps are replaced by: the caption 0x240 (\"Carrying fruit to the food "
            "bin\"), job event 0x76 (the cooked sack shows), item 0x36 carried, the walk to the food bin (area 8), the "
            "trip's own 1-second wait and put-down, and job event 0x77: the sack's food. The trip's own job event 15 "
            "(3 food) is therefore never queued, and the stew is never given the sack.",
            f"Job event 0x77 (as event 14): n = {SACK_FRUIT}; with {LIMITED}, n = the fruit left, at most "
            f"{SACK_FRUIT}, taken from the tree (VvfpYellowFruitTake of \"VVFP VV4 Fruit Supply.dll\", found with "
            "GetProcAddress); 0x41D920(n); with the limited tree and fewer than 3 fruit left, the villager's task "
            "cleared; over 2,000 food, tip 0x2E5.",
            "The pictures: the carried item's draw (0x466770, its call of 0x44C640 at 0x4667B4; the fifth argument "
            "is the picture's alpha, 1.0, and the size the map's zoom) draws, for a villager whose queue still holds "
            "event 0x77: after event 0x75, item 0x35 -> Images\\vvfp_sack_empty.png and item 0x36 (trees to pit) -> "
            "Images\\vvfp_sack_yellow_fruit_raw.png; after event 0x76, item 0x36 (pit to bin) -> "
            "Images\\vvfp_sack_yellow_fruit.png; with the same alpha, centred on carrying.png's 40-pixel cell and "
            "standing 31 pixels down, where its fruit and berries end; built once by ldwImageGrid 0x40AB10 (name, 1, "
            "1) after the PNG header says 8-bit RGBA of at most 40 x 40; a missing or wrong file: the game's own "
            "picture (the cloth, the yellow fruit).",
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


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def main() -> None:
    if "--art" in sys.argv[1:]:
        make_pictures()
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_vv4_cloth_sacks.ps1")], check=True)
    path = ROOT / "data" / f"{ID}_feature.json"
    path.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
