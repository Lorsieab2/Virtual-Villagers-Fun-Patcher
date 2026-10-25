"""Write data/vv1_genetics_feature.json: Genetics for A New Home (the owner, 2026-10-25).

The behaviour lives in one companion, "VVFP VV1 Genetics.dll" (native/vv1_genetics), started by VVFP
Startup.dll from its second word of companions (native/shared/startup_companions_2.h).  Build the DLL
first (scripts/build_vv1_genetics.ps1); this pins it by SHA-256.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP VV1 Genetics.dll"
DLL = ROOT / "assets" / "genetics" / DLL_NAME
OUT = ROOT / "data" / "vv1_genetics_feature.json"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"

DESCRIPTION = (
    "Gives A New Home the head genetics of the later games. In the original game a baby's head is "
    "picked at random and neither parent's looks count; with this patch a baby's head comes from its "
    "parents, by The Lost Children, The Secret City, The Tree of Life and New Believers' own rule: "
    "the father's head and the mother's head added and halved (rounded down), then one row lower, the "
    "same or one row higher, one chance in three each; on 5 births in 100 any head instead, as the "
    "game rolls it. A boy's head stays within the boys' heads (0 to 18), so no boy is ever given head 19, "
    "which stays the Golden Child's; a girl's within 0 to 19. When the father is not known -- "
    "\"Unknown\", or a birth whose conception was not recorded -- the mother's head alone is used, with "
    "the same one-row step and the same 5 in 100. Twins and triplets share the first baby's head, as "
    "in every game. Bodies stay random, as in every game, and the Golden Child, new villages and island "
    "events' villagers are the game's own. **Needs Show Parents in Details Screen to know each baby's "
    "father; without it every baby takes after its mother.** **Works the same with every other patch and "
    "in every population mode.** **Not yet tested in a running game.** The companion is \""
    + DLL_NAME + "\", started by VVFP Startup.dll; if the DLL cannot be loaded, the game is stock."
)


def row(sha: str) -> dict:
    return {
        "id": "vv1_genetics",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": "Genetics: Babies Take After Their Parents",
        "description": DESCRIPTION,
        "output_tag": "Genetics",
        "dependencies": [],
        "behavior_changes": [
            "The villager creator 0x43C350, when the pregnancy tick calls it for the first child of a "
            "birth (0x42EFD0, returning to 0x42EFD5), stores at 0x43C647 a head from the parents instead of "
            "the head it rolled: rand(100) < 5 keeps the rolled head (rand(19) for a boy, rand(20) for a "
            "girl, as stock); otherwise base + rand(3) - 1, made 0 below 0 and 18 (a boy) or 19 (a girl) "
            "above, from the game's own rand 0x402F10.",
            "base is (father's head + mother's head) / 2, rounded down, with the father VVFP VV1 "
            "Parentage.dll stashed against the mother at the conception (Vv1ParentageQueryExpectedFather); "
            "the mother's head alone when that DLL is not there, knows no father, or gives a head outside "
            "0..19.",
            "Twins and triplets (0x43C840 at 0x42F021 and 0x42F06D) copy the first child's head, so they "
            "share the inherited head.",
        ],
        "explicit_non_changes": [
            "This row changes no executable bytes: the DLL verifies the creator's head and body rolls "
            "(0x43C616..0x43C64C, but for the rand calls' targets and the name roll's bound) and the game's "
            "rand, and writes its one detour at run time through the shared all-or-none writer; a "
            "different build installs nothing.",
            "Bodies, sexes, names, likes and dislikes are rolled as in the stock game.",
            "The Golden Child (family 199: head and body 19 from the creator's own branch), the first "
            "villagers of a new village, and every villager an island event or Story / Cheat Upgrades "
            "makes are the game's own; only births from a pregnancy change.",
            "No save byte or file is written: the head is the record's own field, saved by the game.",
        ],
        "companion_files": [
            {"source": f"assets/genetics/{DLL_NAME}", "destination": DLL_NAME, "sha256": sha},
        ],
        "patches": [],
        "runtime_detours": [
            {
                "va": "0x43C647",
                "stock_bytes": "898660030000",
                "written_bytes": "E9XXXXXXXX90",
                "routine": "the villager creator 0x43C350's head store (mov [esi+0x360], eax): the head "
                           "from the parents for a birth's first child, then on at 0x43C64D",
                "installed_by": INSTALLED_BY,
            },
        ],
    }


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    OUT.write_text(json.dumps(row(sha), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
