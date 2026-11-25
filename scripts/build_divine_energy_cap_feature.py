"""Write New Believers' "Max Divine Energy Continues to Increase" row (the owner, 2026-11-25: "removes the hardcoded
1000 max energy to allow it to increase with population and collectibles").

The companion "VVFP Divine Energy Cap.dll" (native/vvfp_divine_energy_cap) writes its three sites at run time, all or
none.  tests/test_vv5_divine_energy_cap.py proves it by emulation of the stock executable.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_divine_energy_cap.ps1) and pins
it by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW_ID = "vv5_max_divine_energy_increases"
NAME = "Max Divine Energy Continues to Increase"
DLL_NAME = "VVFP Divine Energy Cap.dll"
DLL = ROOT / "assets" / "divine_energy_cap" / DLL_NAME
OUT = ROOT / "data" / f"{ROW_ID}_feature.json"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"

SITES = (
    (0x4250B4, "81FEE80300007E07BEE8030000", "81FEE8030000EB07BEE8030000",
     "the cap routine 0x425020's \"at most 1,000\" (`cmp esi, 1000 / jle 0x4250C3 / mov esi, 1000`): the jle "
     "becomes a jmp, so the cap is the routine's own formula, never held at 1,000 (still at least 0)"),
    (0x4250D8, "C787607D0100E8030000", "E9XXXXXXXX9090909090",
     "the cap routine's +0x17E11 path (`mov dword ptr [edi+0x17D60], 1000`; the byte is only ever cleared, by the "
     "village reset 0x4246A0 at 0x424807, and is not in the save): the companion stores max(the formula, 1,000) and "
     "goes on at 0x4250E2"),
    (0x44321E, "E85DD10000", "E8XXXXXXXX",
     "the HUD's call of the Divine Energy bar 0x450380 (x 0x269, y 0xC, cap, current, the chosen power's cost; the bar "
     "clamps the cap to 10..1,000 and divides by the clamped cap): above a 1,000 cap the companion passes 1,000, "
     "current x 1,000 / cap and cost x 1,000 / cap (at least 1), then calls 0x450380"),
)


def description() -> str:
    return (
        "Removes the hardcoded 1,000 maximum Divine Energy, so the cap keeps growing with the number of believers "
        "and collectibles. The cap is worked out as in the normal game: 5 for each believer and each baby they "
        "carry, plus 10; +50 and +50 more for the Tribute Statue's first two stages; +100 once The Tribute Statue "
        "is solved; +50 and +50 more for Spirituality 2 and 3; +3 for each piece of the first collectible set (+90 "
        "once all 24 are owned). The normal game stops it at 1,000 (120 believers with every bonus); with this "
        "patch it goes on: 1,150 with 150 believers and every bonus, 1,680 with 256 (\"256 Villagers "
        "(Experimental)\"). The Divine "
        "Energy bar at the top of the screen shows the energy as a share of the cap, so a full bar is still full "
        "and fits its frame. **The cap still falls when believers die or leave, as in the normal game, and the "
        "Divine Energy never goes above the cap.** **Below 1,000 nothing changes.** **A save made with a cap above "
        "1,000 still loads without the patch: the game then brings the cap and the Divine Energy back down to "
        "1,000.** **Works the same with every other patch and in every population mode.** **Not yet seen in a "
        f"running game** (checked by emulation of the stock executable). The companion is \"{DLL_NAME}\"; it never "
        "writes a save or a file."
    )


def row(dll_sha: str) -> dict:
    return {
        "id": ROW_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": NAME,
        "description": description(),
        "output_tag": "Divine Energy Cap",
        "dependencies": [],
        "behavior_changes": [
            "The cap routine 0x425020 (every update of the village, 0x4425A3) computes 5 x (0x4713F0 + 2: the living "
            "believers and the babies they carry), +50 at the Tribute Statue's stage 1 (0x4271C0), +50 more at stage 2, "
            "+100 once puzzle 14 is solved (0x43AE80), +50 at Spirituality (tech 5, 0x423600) 2, +50 more at 3, and "
            "the first collectible set (0x413F50, ids from 0x68): 3 per piece, 90 with all 24; the stock "
            "\"at most 1,000\" (0x4250B4..0x4250C1) is skipped, so the cap (+0x17D60) is that sum, at least 0: 1,150 "
            "with 150 believers and every bonus, 1,680 with 256 (256 Villagers); 1,000 is reached at 120.",
            "The +0x17E11 path (0x4250D8) stores max(the sum, 1,000) instead of exactly 1,000. The byte is never set by "
            "the game (its only write is the clear at 0x424807 in the village reset 0x4246A0, run on every new village "
            "and every load; it lies past the saved part of the manager, +8..+0x17D80), so in play the path is not "
            "taken; with the patch it can never bring the cap back down to 1,000.",
            "The HUD's Divine Energy bar (0x450380, called only at 0x44321E) clamps the cap to 10..1,000 for its frame "
            "(cap x 372 / 1,000 pixels) but divides the fill by the clamped cap; with a cap above 1,000 the companion "
            "gives it a cap of 1,000, the Divine Energy x 1,000 / cap (the Divine Energy kept 0..cap first) and the "
            "chosen power's cost x 1,000 / cap (at least 1 while a power is chosen), so a full village fills the "
            "whole 372-pixel frame and nothing is drawn past it.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion writes its three sites at run time, all or none, only after "
            "verifying their stock bytes.",
            "The cap's formula and every bonus, the Divine Energy income, the powers' costs and unlocks (cap at least "
            "10..800, 0x440E71 / 0x441107 / 0x44147E / 0x441569), the power buttons (0x422E60), Blessings Day's "
            "fill to the cap (0x414B58), the adder and subtractor (0x424F80 / 0x424FD0, kept 0..cap) and the HUD's "
            "numbers (\"%i\", 0x442398 / 0x4423CA) are the game's own; they read the whole 32-bit numbers.",
            "With a cap of 1,000 or less the bar's call passes its arguments unchanged.",
            "The cap and Divine Energy are whole 32-bit numbers in the save (offsets 0x17D70 / 0x17D74); nothing is "
            "written but the cap the game itself stores; no file.",
        ],
        "companion_files": [
            {"source": f"assets/divine_energy_cap/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": written, "routine": what,
             "installed_by": INSTALLED_BY}
            for va, stock, written, what in SITES
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_divine_energy_cap.ps1")], check=True)
    OUT.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
