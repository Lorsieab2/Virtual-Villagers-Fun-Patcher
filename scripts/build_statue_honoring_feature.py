"""Write New Believers' "Villagers Dropped on an Unfinished Statue May Honor" row (the owner, 2026-11-27: "villagers
when dropped on the statue when it can be improved, should have a chance of practicing devotion (honoring) instead of
being confused (roughly equal) so people can always get triggered to honor no matter what"; on by default: the owner's
own request).

The companion "VVFP Statue Honoring.dll" (native/vvfp_statue_honoring) splices the statue handler's Confused dispatch
at run time.  tests/test_vv5_statue_honoring.py proves it by emulation of the stock executable.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_statue_honoring.ps1) and pins it
by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW_ID = "vv5_unfinished_statue_drops_honor"
NAME = "Villagers Dropped on an Unfinished Statue May Honor"
DLL_NAME = "VVFP Statue Honoring.dll"
DLL = ROOT / "assets" / "statue_honoring" / DLL_NAME
OUT = ROOT / "data" / f"{ROW_ID}_feature.json"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"

SITE = (0x479726, "6A1FC744240C66000000",
        "the statue handler 0x479560's drop case 3 (the statue carved to its first or second stage, its next stage "
        "waiting for technology): `push 0x1F / mov dword [esp+0xC], 0x66` before the action setter call 0x465580 at "
        "0x479730. The call to the companion leaves 0x1F (Confused, its parameter 0x66) or 0xA0 (Honoring, its "
        "parameter byte 0) where the push would, every register and flag unchanged")


def description() -> str:
    return (
        "Dropping a villager on the Tribute Statue while it can still be improved but its next stage needs more "
        "technology (Construction and Spirituality) makes them \"Confused\" in the normal game. With this patch, "
        "about half of those drops (1 in 2) start the game's own Honoring instead, so you can always get a "
        "villager to Honor. **Only while the statue is carved to its first or second stage and its next stage "
        "waits for technology**: while a stage can be worked on a drop still builds the statue, and the finished "
        "statue still gives Polishing (or, with \"Statue Drops: Normal Action or Honoring\", Polishing or "
        "Honoring). The Honoring is the normal game's in every way: half the time the villager honors at the "
        "statue, where it earns Divine Energy and, 1 time in 4, practises Devotion through the game's own Devotion "
        "check (1 Honoring in 8 overall, as every Honoring); the rest of the time they honor at the game's other "
        "spot for it, so the statistics, logs and other patches count it like any other.**Adults only, as in the normal game**: children and nursing mothers "
        "still cannot be dropped on the statue. **Heathens cannot be picked up in the game, so they are never "
        "dropped on it.** **Needs no other patch; works the same with every other patch and in every population "
        "mode.** **Not yet seen in a running game** (checked by emulation of the stock executable). The companion is \"VVFP Statue Honoring.dll\"; it never writes a save or a file."
    )


def row(dll_sha: str) -> dict:
    va, stock, what = SITE
    return {
        "id": ROW_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": NAME,
        "description": description(),
        "output_tag": "Statue Honoring",
        "dependencies": [],
        "behavior_changes": [
            "The statue (area 0x18, handler 0x479560, permission 0: the drop dispatcher 0x4794A0 turns a child under "
            "280 age units and an expecting mother away first) drops in three cases (message 0, 0x47969C): the "
            "statue can be worked on (0x432350) -> 0x95 Building a statue; else solved (0x43AE80(14)) -> 0x9D "
            "Polishing; else -> 0x1F Confused (0x47971D..0x479730). In that third case a believer (+0x1CEC 0) of "
            "280 age units or more, while the statue object 0x51D950's stage (+8, 0x4271C0) is 1 or 2 -- the job "
            "dispatcher's own Honoring offer test 0x46CDC6..0x46CDE1 -- gets behaviour 0xA0 (Honoring, 0x45CB70, its "
            "parameter byte 0 as 0x46CDE8 sets it) on one draw in two of the companion's own xorshift (never the "
            "game's rand 0x403660); otherwise the stock 0x1F with 0x66.",
            "Honoring is the game's own, started by the stock call 0x465580: rand(100) < 50 to the statue's spot "
            "(0x45CBA5, area 0x45), there rand(100) < 25 queues the Devotion practice 0x474780(5) -> the skill check "
            "0x46B270 (0x45CC92) and the work event 0x5D (Divine Energy) is queued (0x45CCA0); else to area 0x6E "
            "with gestures and waits only (0x45CCC0..0x45CD6F).",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion splices the one site at run time, only after verifying its "
            "stock bytes; registers and flags are as the stock instructions leave them.",
            "The statue's other drop cases (Building a statue 0x4796AA, Polishing 0x4796E2 -- and that dispatch's "
            "vv5_statue_polishing_or_honoring selector), its hover and click cases, the job dispatcher, the "
            "Honoring script, the Devotion check and its odds are the game's own (and the other patches' own).",
            "Heathens cannot be picked up (0x445F32, \"You cannot touch heathens because they do not believe in "
            "you.\"), so none is ever dropped on the statue; a record with the faction byte set keeps the stock "
            "Confused.",
            "Nothing is written to a save, a villager record or a file; no text is shown.",
        ],
        "companion_files": [
            {"source": f"assets/statue_honoring/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": "E8XXXXXXXX" + "90" * (len(stock) // 2 - 5),
             "routine": what, "installed_by": INSTALLED_BY},
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_statue_honoring.ps1")], check=True)
    OUT.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
