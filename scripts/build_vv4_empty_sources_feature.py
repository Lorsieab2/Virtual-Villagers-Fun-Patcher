"""Write The Tree of Life's "No Tool Harvest from Empty Sources" row (data/vv4_no_tool_harvest_from_empty_sources_feature.json).

The owner (2026-11-18): a cutting tool is never used up on a blackberry bush with 0 berries, nor a cloth sack on a
yellow fruit tree with 0 fruit (the tree runs out only with "Yellow Fruit Trees are No Longer Unlimited"); the drop is
refused, nothing is used up.  At 1 or more everything works as before.  On by default and in Owner's Defaults.

"VVFP VV4 Empty Sources.dll" (native/vvfp_vv4_empty_sources) refuses the cutting-tool harvest at run time, started by
VVFP Startup.dll from its second word; "VVFP VV4 Cloth Sacks.dll" refuses the sack when this companion is loaded.
tests/test_vv4_empty_sources.py proves both by emulation.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_vv4_empty_sources.ps1) and pins
it by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = "vv4_no_tool_harvest_from_empty_sources"
NAME = "No Tool Harvest from Empty Sources"
DLL_NAME = "VVFP VV4 Empty Sources.dll"
DLL = ROOT / "assets" / "empty_sources" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
SACKS, SACKS_NAME = "vv4_cloth_sacks_for_yellow_fruit", "Cloth Sacks for Yellow Fruit"
LIMITED_NAME = "Yellow Fruit Trees are No Longer Unlimited"
SITE = (0x46E86F, "566A01E87981FCFF",
        "the cutting-tool harvest's drop 0x46E7E0, its tool use (push esi / push 1 / call 0x4369F0 on 0x4D8614): with "
        "0 berries ([game + 0x170F8]) the empty bush's own refusal (action 0x3F, text 0xA7) and the drop's end "
        "0x46E89B instead, no tool used; otherwise the stock instructions and on at 0x46E877")


def description() -> str:
    return (
        "A cutting tool is no longer used up on a blackberry bush that has no berries left: a villager dropped to "
        "harvest it with a cutting tool refuses, as at an empty bush (\"There is not enough to harvest.\", the "
        "game's own words), and keeps the tool. With 1 berry or more the harvest works exactly as before (it brings "
        f"what is left, at most 30). **With \"{SACKS_NAME}\" ticked too, the same goes for the cloth sacks: a sack "
        f"is not made for a yellow fruit tree with no fruit left (which happens only with \"{LIMITED_NAME}\"; "
        "otherwise the tree never runs out), and no cloth is used. Without Cloth Sacks this patch does the cutting "
        "tool alone.** **Needs no other patch.** **On by default.** **Unverified in play: the effect has not been "
        f"tested live.** The companion is \"{DLL_NAME}\", started by VVFP Startup.dll; if the DLL cannot be loaded, "
        "the stock game runs."
    )


def row(dll_sha: str) -> dict:
    va, stock, routine = SITE
    return {
        "id": ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": NAME,
        "description": description(),
        "output_tag": "No Empty Tool Harvest",
        "dependencies": [],
        "behavior_changes": [
            "The cutting-tool harvest's drop (0x46E7E0, map area 0x31): after its own 'no tool' check, with 0 "
            "berries the villager gets action 0x3F with text 0xA7 (\"There is not enough to harvest.\", the empty "
            "bush's refusal at 0x46F881) and no tool is used (0x4369F0 is not called); with 1 or more, unchanged.",
            f"{SACKS_NAME} (\"VVFP VV4 Cloth Sacks.dll\") asks whether \"{DLL_NAME}\" is loaded (GetModuleHandleW); "
            "when it is and the yellow fruit tree holds 0 fruit (VvfpYellowFruitLeft of \"VVFP VV4 Fruit "
            "Supply.dll\"), a drop at the hut gets the same refusal (action 0x3F, text 0xA7) after the 'no cloth' "
            "check and before any cloth is used.",
        ],
        "explicit_non_changes": [
            "At 1 or more berries or fruit the tool and the sack take what is left, as before (job event 14 and the "
            "sack's event: at most 30). Picking, the fruit trips and every other drop are the game's own.",
            "The pruning puzzle's use of a tool at the same spot (0x46E84C, puzzle 0xC) is not changed.",
            "No executable byte is patched: the companion writes one jump at run time after verifying the site and "
            "the code it returns to; nothing is written to the save.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; emulated (an empty bush refused with the tool "
                            "kept, 1 berry harvested as before, the stock game using the tool; an empty limited tree "
                            "refused at the hut with the cloth kept, with and without the companion) in "
                            "tests/test_vv4_empty_sources.py; runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/empty_sources/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [{
            "va": f"0x{va:X}",
            "stock_bytes": stock,
            "written_bytes": "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
            "routine": routine,
            "installed_by": INSTALLED_BY,
        }],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_vv4_empty_sources.ps1")], check=True)
    path = ROOT / "data" / f"{ID}_feature.json"
    path.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
