"""Write data/vv1_grey_hair_feature.json: Grey Hair at 55 for A New Home (the owner, 2026-10-28).

The behaviour lives in one companion, "VVFP VV1 Grey Hair.dll" (native/vv1_grey_hair), started by VVFP
Startup.dll from its second word of companions (native/shared/startup_companions_2.h); the art is two new
sheets the DLL has the game load from its Images folder (assets/vv1_grey_hair/README.txt).

One command after the grey sheets change: this script checks them and writes the picker's preview strips
(scripts/build_vv1_grey_hair_art.py), builds the DLL (scripts/build_vv1_grey_hair.ps1), and pins the DLL
and both sheets by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_vv1_grey_hair_art as art  # noqa: E402

DLL_NAME = "VVFP VV1 Grey Hair.dll"
DLL = ROOT / "assets" / "vv1_grey_hair" / DLL_NAME
OUT = ROOT / "data" / "vv1_grey_hair_feature.json"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"

# The 29 reads of the two head sheets (native/vv1_grey_hair/vv1_grey_hair.c SITES): (va, stock bytes, where).
READS = (
    (0x437405, "8B8EF8DF0300", "the Details portrait 0x437340, a man's head"),
    (0x43748E, "8B8EF4DF0300", "the Details portrait 0x437340, a woman's head"),
    (0x4374E6, "8B86F8DF0300", "the Details portrait 0x437340, a man's head"),
    (0x437539, "8B96F4DF0300", "the Details portrait 0x437340, a woman's head"),
    (0x4376B0, "8B8EF8DF0300", "a dialog's villager figure 0x4375F0, a man's head"),
    (0x437735, "8B8EF8DF0300", "a dialog's villager figure 0x4375F0, a man's head"),
    (0x43775D, "8B8EF4DF0300", "a dialog's villager figure 0x4375F0, a woman's head"),
    (0x437B9D, "8B96F8DF0300", "the village 0x437790, a man's head"),
    (0x437D73, "8B96F4DF0300", "the village 0x437790, a woman's head"),
    (0x437E9B, "8B96F8DF0300", "the village 0x437790, a man's head"),
    (0x437FA1, "8B96F4DF0300", "the village 0x437790, a woman's head"),
    (0x43812F, "8B8EF8DF0300", "the village 0x437790, a man's head"),
    (0x438140, "8B8EF4DF0300", "the village 0x437790, a woman's head"),
    (0x438265, "8B8EF8DF0300", "the village 0x437790, a man's head"),
    (0x4382D7, "8B8EF4DF0300", "the village 0x437790, a woman's head"),
    (0x43836C, "8B8EF8DF0300", "the village 0x437790, a man's head"),
    (0x4383C2, "8B8EF4DF0300", "the village 0x437790, a woman's head"),
    (0x4385D9, "8B8EF4DF0300", "the village 0x437790, a woman's head"),
    (0x438766, "8B8EF8DF0300", "the village 0x437790, a man's head"),
    (0x4387BA, "8B8EF4DF0300", "the village 0x437790, a woman's head"),
    (0x438BF3, "8B8EF4DF0300", "the map 0x4388E0, a woman's head"),
    (0x438D23, "8B8EF8DF0300", "the map 0x4388E0, a man's head"),
    (0x438DDB, "8B86F4DF0300", "the map 0x4388E0, a woman's head"),
    (0x438E73, "8B8EF8DF0300", "the map 0x4388E0, a man's head"),
    (0x438EE0, "8B8EF4DF0300", "the map 0x4388E0, a woman's head"),
    (0x439052, "8B86F8DF0300", "the map 0x4388E0, a man's head"),
    (0x4390D7, "8B8EF4DF0300", "the map 0x4388E0, a woman's head"),
    (0x4391CF, "8B86F8DF0300", "the map 0x4388E0, a man's head"),
    (0x439249, "8B86F4DF0300", "the map 0x4388E0, a woman's head"),
)
ENGINES = (
    (0x408AF0, "the engine's scaled cell draw (reached through 0x409410)"),
    (0x408740, "the engine's row/column cell draw (reached through 0x4093C0)"),
)

DESCRIPTION = (
    "Gives A New Home the grey hair of the later games. In the original game a villager keeps the same "
    "head picture for life; The Lost Children, The Secret City, The Tree of Life and New Believers switch "
    "to an older-looking head at 55 years. With this patch an A New Home villager of 55 years or more is "
    "drawn with a grey-haired version of the same head everywhere the game draws one -- in the village, on "
    "the map and in the Villager Details portrait -- and Change Appearance previews it the same way. "
    "Villagers already grey or bald look the same. Every head follows the same rule, the Golden Child's head "
    "19 too: the Golden Child himself never grows old, so he never changes, but any other villager given his "
    "head shows its old version from 55. Only the picture changes: the head number in the save stays the same, so logs, the Family "
    "Tree, genetics and Change Appearance keep reading the same head. **On by default.** **Show Parents' "
    "small pictures of a child's parents and the Family Tree keep the usual heads.** **Works the same "
    "with every other patch and in every population mode.** **Not yet seen in a running game.** The "
    "companion is \"" + DLL_NAME + "\", started by VVFP Startup.dll; it adds two new pictures, "
    "Images\\vvfp_grey_male_heads.png and Images\\vvfp_grey_female_heads.png, and changes none of the "
    "game's own; if the DLL cannot be loaded, or a picture is missing, those villagers keep their usual heads."
)


def row(dll_sha: str, sheet_sha: dict[str, str]) -> dict:
    detours = [
        {
            "va": f"0x{va:06X}",
            "stock_bytes": stock,
            "written_bytes": "E9XXXXXXXX90",
            "routine": f"{where}: the read of the young head sheet (mov reg, [esi+disp]); the companion does the "
                       "read itself and remembers the villager, then on at the next instruction",
            "installed_by": INSTALLED_BY,
        }
        for va, stock, where in READS
    ] + [
        {
            "va": f"0x{va:06X}",
            "stock_bytes": "83EC108B542424",
            "written_bytes": "E9XXXXXXXX9090",
            "routine": f"{where}'s entry: a draw given the head sheet just read gets the grey sheet when that "
                       "villager is 55 or older, then the displaced entry and on",
            "installed_by": INSTALLED_BY,
        }
        for va, where in ENGINES
    ]
    return {
        "id": "vv1_grey_hair",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": "Grey Hair at 55",
        "description": DESCRIPTION,
        "output_tag": "Grey Hair",
        "dependencies": [],
        "behavior_changes": [
            "Every draw of a villager's head from male_heads.png or female_heads.png -- the 29 reads of "
            "gameobj+0x3DFF8 / +0x3DFF4 in the Details portrait 0x437340, a dialog's villager figure 0x4375F0, "
            "the village 0x437790 and the map 0x4388E0 -- uses Images\\vvfp_grey_male_heads.png or "
            "Images\\vvfp_grey_female_heads.png instead (same column, same row) when the villager's shown age "
            "(record +0x348) is 1,100 age units (55 years) or more, the age the later games switch to their "
            "old heads (VV2 0x4469BA, VV3 0x46086D, VV4 0x467E89, VV5 0x4722A2).",
            "Head 19 follows the same rule as every other head (the owner, 2026-10-28): the Golden Child never "
            "reaches 1,100 (the age tick puts family 199 back to 100 units, 0x42EB80..0x42EB8E), but any other "
            "villager given head 19 is drawn from row 19 of the grey sheet once 1,100 or older.",
            "The Origins Change Appearance picker previews a villager's head from this companion's grey "
            "strip when the village draws that villager grey (Vv1GreyHairWanted).",
            "Change Appearance's head look (\"VVFP Head Look.dll\", shipped by the Origins row): each draw asks "
            "it for the villager's look -- Auto keeps the 1,100 rule, Young is never drawn grey and Old is drawn "
            "grey at any age; the picker offers the look only when this companion is installed and previews it "
            "with Vv1GreyHairUsable.",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes: the DLL verifies the 29 reads, the two engine entries and "
            "the four routines' register set-ups, and writes its 31 detours at run time through the shared "
            "all-or-none writer; a different build installs nothing.",
            "The head value (record +0x360) and every other record field are never written: logs, the Family "
            "Tree, genetics and Change Appearance read the same head number as before.",
            "The game's own male_heads.png and female_heads.png are not changed; the grey sheets are new files. "
            "A missing grey sheet, or one that is not exactly 280 x 1300 pixels, is never used.",
            "The draws themselves are the game's own: the same sprite cell, position, scale and facing; the Origins "
            "masks still find the head draw by its young sheet and are drawn as before.",
            "Show Parents' small parent figures on the Details screen (drawn by VVFP VV1 Parentage.dll from the "
            "parents' stored heads, which carry no age) and the Family Tree Maker keep the young heads.",
        ],
        "companion_files": [
            {"source": f"assets/vv1_grey_hair/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
            {"source": "assets/vv1_grey_hair/vvfp_grey_male_heads.png",
             "destination": "Images/vvfp_grey_male_heads.png", "sha256": sheet_sha["male"]},
            {"source": "assets/vv1_grey_hair/vvfp_grey_female_heads.png",
             "destination": "Images/vvfp_grey_female_heads.png", "sha256": sheet_sha["female"]},
        ],
        "patches": [],
        "runtime_detours": detours,
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        art.main()
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vv1_grey_hair.ps1")], check=True)
    for path in art.SHEETS.values():
        art.load_sheet(path)                    # refuses a sheet that is not 280 x 1300
    sheets = {sex: sha(path) for sex, path in art.SHEETS.items()}
    OUT.write_text(json.dumps(row(sha(DLL), sheets), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT), sha(DLL))


if __name__ == "__main__":
    main()
