"""Write the "Esteemed Elders in Every Game" rows: data/vv1_esteemed_elders_feature.json, vv2_..., vv4_... (the owner,
2026-11-22: "all 5 games should change a villager's title to 'Esteemed Elder' if they master 3 skills (EXCEPT SPECIAL
VILLAGERS LIKE THE GOLDEN CHILD, VV3 TRIBAL CHIEF ETC)").  The Secret City and New Believers already do it in the
stock game (0x462570, 0x475610), so they have no row: the rule is the game's own there.

The companion "VVFP Esteemed Elders.dll" (native/vvfp_esteemed_elders) splices the villager panel's title and the
burial's epitaph at run time; the rule is native/shared/esteemed_elder.h.  tests/test_esteemed_elders.py proves it
by emulation of the stock executables.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_esteemed_elders.ps1) and pins
it by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "Esteemed Elders in Every Game"
DLL_NAME = "VVFP Esteemed Elders.dll"
DLL = ROOT / "assets" / "esteemed_elders" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"
GAMES = (1, 2, 4)
CAUSE_ROW_VV1 = "Show Cause of Death and Epitaphs on Graves, and Log Every Death"
REPAIR = ("**Villagers and graves from before: Repair Saves & Logs > \"Give the Esteemed Elder title "
          "retroactively\".**")
COMMON_END = ("**Works the same with every other patch and in every population mode.** **Not yet seen in a running "
              f"game** (checked by emulation of the stock executable). The companion is \"{DLL_NAME}\"; it never "
              "writes a save or a file.")


def row_id(game: int) -> str:
    return f"vv{game}_esteemed_elders"


DESCRIPTIONS = {
    1: ("A villager who has mastered three or more skills (90 or more, the level the Villager Details screen calls "
        "\"Master\") gets the title \"Esteemed Elder\" on the Villager Details screen, as in The Secret City and New "
        "Believers. The Golden Child keeps his own title, and a custom title (Story / Cheat Upgrades) still shows "
        "in its place. The logs' \"Special villager\" line says it too. When such a villager dies, their grave's "
        f"epitaph is \"Esteemed Elder\". **The epitaph needs \"{CAUSE_ROW_VV1}\"** (A New Home's graves have an "
        f"epitaph only with it). {REPAIR} {COMMON_END}"),
    2: ("A villager who has mastered three or more skills (88 or more) gets the title \"Esteemed Elder\" on the "
        "Villager Details screen even when the game has not made them an Esteemed Elder (the normal game stops "
        "making new elders, and their totems, at 50 totems). The normal game's own Esteemed Elders, and their "
        "totems, are unchanged; this patch makes no totem. A totem statue never gets the title, and a custom title "
        "(Story / Cheat Upgrades) still shows in its place. The logs' \"Special villager\" line says it too, and "
        "when such a villager dies as an adult their grave gets the game's own \"Esteemed Elder\" epitaph. "
        f"{REPAIR} {COMMON_END}"),
    4: ("A villager who has mastered three or four skills (88 or more) gets the title \"Esteemed Elder\" on the "
        "Villager Details screen, as in The Secret City and New Believers. Mastering all five is still the game's "
        "own \"Scholar\", which wins. A ghost never gets the title, and a custom title (Story / Cheat Upgrades) "
        "still shows in its place. The logs' \"Special villager\" line says it too, and when such a villager dies "
        f"as an adult their grave's epitaph is \"Esteemed Elder\". {REPAIR} {COMMON_END}"),
}

SITES = {
    1: [(0x41FBDC, "81B96C030000C70000007515",
         "the villager panel 0x41F9B0's Golden Child test (`cmp dword [ecx+0x36C], 0xC7 / jne 0x41FBFD`, ecx the "
         "record): the Golden Child goes on to his string 0x5F (0x41FBE8) as before; otherwise a villager with three "
         "or more of the five skills +0x3BC..+0x3CC at 90 or more (the panel's own Master, 0x41FC16) gets \"Esteemed "
         "Elder\" (pushed and copied by 0x44B23D at 0x41FD6D, as the Golden Child's string is); anyone else goes on "
         "to the rank at 0x41FBFD with every register as it was")],
    2: [(0x429C1D, "3899FC0700007418",
         "the villager panel's elder flag test (`cmp byte [ecx+0x7FC], bl / je 0x429C3D`): the flag, or three or "
         "more of the five skills +0x7E4..+0x7F4 at 88 or more (never a totem, +0x558), takes the game's own "
         "\"Esteemed Elder\" (string 0x87, 0x429C25); otherwise the rank at 0x429C3D with every register as it was"),
        (0x46513C, "8A81FC07000084C0742C",
         "the burial's elder test for an adult's epitaph (`mov al, [ecx+0x7FC] / test al, al / je 0x465172`): the "
         "flag, or the same three-mastered rule, takes the game's own epitaph 0x1F0 (0x465146); otherwise the job's "
         "epitaph at 0x465172")],
    4: [(0x440314, "E857A9020084C07418",
         "the villager panel's Scholar test (`call 0x46AC70 / test al, al / je 0x440335`, ecx the record's skills, [esp+0x10] the record): the "
         "Scholar (all five) still takes string 0xDA (0x44031D); otherwise three or four of the five float skills "
         "+0x1C5C..+0x1C6C at 88.0 or more (never a ghost, +0x1CC7) gets \"Esteemed Elder\" (pushed and copied by "
         "0x4716DB at 0x4404D1, as the Scholar's string is); otherwise the rank at 0x440335"),
        (0x45D611, "8B4424148B4C2420",
         "the Roster of the Dead writer 0x45D470 right after its epitaph copy (0x45D60C): for a grave of age 360 or "
         "more whose Scholar byte +0x31 is 0, when the record (the writer's first argument) is an Esteemed Elder by "
         "the same rule, the epitaph +0x38 (char[0x20]) becomes \"Esteemed Elder\"; then the two loads re-run and "
         "the writer goes on at 0x45D619")],
}

BEHAVIOUR = {
    1: ["The Villager Details screen's title (0x41F9B0): \"Esteemed Elder\" for a villager, not the Golden Child, "
        "with three or more of the five skills at 90 or more, in place of the skill-and-job label; Story / Cheat "
        "Upgrades' custom title is applied after it (0x41FD75), so it still wins.",
        "The logs' \"Special villager: Esteemed Elder\" line (native/shared/special_title.h) while the companion is "
        "installed; the Cause of Death companion gives such a villager's new grave the epitaph \"Esteemed Elder\" "
        "(its Graves file, version 4)."],
    2: ["The Villager Details screen's title and an adult's grave epitaph: the game's own \"Esteemed Elder\" "
        "(strings 0x87 and 0x1F0) for a villager with the stock flag +0x7FC, as before, or with three or more of "
        "the five skills at 88 or more (never a totem statue, +0x558).",
        "The logs' \"Special villager: Esteemed Elder\" line follows the same rule while the companion is "
        "installed."],
    4: ["The Villager Details screen's title: \"Scholar\" for all five skills at 88.0 or more, as before; "
        "\"Esteemed Elder\" for three or four (never a ghost, +0x1CC7).",
        "The Roster of the Dead: an adult's grave (age 360 or more), not a Scholar's, whose villager is an Esteemed "
        "Elder gets the epitaph \"Esteemed Elder\" in place of the job's; the grave's job, value and Scholar byte "
        "are the game's own. The logs' \"Special villager: Esteemed Elder\" line follows the same rule while the "
        "companion is installed."],
}

NON_CHANGES = [
    "No executable byte is patched: the companion splices its sites at run time, all or none, only after verifying "
    "their stock bytes; the game goes on with the registers it reads afterwards as they were.",
    "No skill, flag, totem, job or save field is changed; the rule only reads the villager's record.",
    "The Secret City and New Believers are left as the stock game makes them (their own Esteemed Elder rule).",
]


def row(game: int, dll_sha: str) -> dict:
    out = {
        "id": row_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": DESCRIPTIONS[game],
        "output_tag": "Esteemed Elders",
        "dependencies": [],
        "behavior_changes": list(BEHAVIOUR[game]),
        "explicit_non_changes": list(NON_CHANGES)
        + (["The stock elder pass (0x44D4C0), its flag, its totems and the Village Elders counter are unchanged."]
           if game == 2 else []),
        "companion_files": [
            {"source": f"assets/esteemed_elders/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
             "routine": what, "installed_by": INSTALLED_BY}
            for va, stock, what in SITES[game]
        ],
    }
    return out


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_esteemed_elders.ps1")], check=True)
    digest = sha(DLL)
    for game in GAMES:
        out = ROOT / "data" / f"{row_id(game)}_feature.json"
        out.write_text(json.dumps(row(game, digest), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
