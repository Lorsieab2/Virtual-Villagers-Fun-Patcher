"""Write The Tree of Life's "Up to 99 Cutting Tools/Soap/Cloth" row (data/vv4_up_to_99_supplies_feature.json).

The owner (2026-11-17): storage for cutting tools, soap and cloth bolts goes from the stock cap of 6 up to 99, and the
stacked pictures look exactly as with 6 when more are stored.  Off by default, on in Owner's Defaults.

"VVFP VV4 Supply Cap.dll" (native/vvfp_vv4_supply_cap) does it at run time, started by VVFP More
Companions.dll from the third word; its source lists every site and why.  tests/test_vv4_supply_cap.py proves it by emulation.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_vv4_supply_cap.ps1) and pins
it by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = "vv4_up_to_99_supplies"
NAME = "Up to 99 Cutting Tools/Soap/Cloth"
DLL_NAME = "VVFP VV4 Supply Cap.dll"
DLL = ROOT / "assets" / "supply_cap" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"

# (VA, stock bytes, written bytes or None for a jump, the routine)
SITES = (
    (0x43142F, "B8060000003946047E03894604", "B8630000003946047E03894604",
     "the cutting tools' produce 0x431400 (count += 3 at 0x43140F), its cap: mov eax, 6 -> 99"),
    (0x4368E2, "B8060000003946047E2D894604", "B8630000003946047E2D894604",
     "the cloth's produce 0x436890 (count += 3 at 0x4368C2), its cap: mov eax, 6 -> 99"),
    (0x436A09, "83F8067E0AC7410406000000", "83F8637E0AC7410463000000",
     "the tools' and cloth's use-up 0x4369F0 (count -= n), its clamp to 6 after each use -> 99"),
    (0x4314C8, "83C7013B7D047CC7", None,
     "the cutting tools' stack draw 0x431480 (one sprite 0x18 per tool): the loop goes on while i < count and i < 6"),
    (0x430CA6, "33DB85ED7E3A8D642400", None,
     "the Clothing Hut's draw 0x430C80 (one cloth_bolt sprite per bolt, bound ebp = the count): bounded by "
     "min(count, 6)"),
)


def description() -> str:
    return (
        "Cutting tools and cloth bolts can be stored up to 99 instead of 6. They are still made 3 at a time (a "
        "villager at the fish skeleton makes 3 cutting tools, a villager storing finished cloth adds 3 bolts), and "
        "every use takes one as before; the count never goes above 99. The stock game also put the count back to 6 "
        "whenever one was used: no longer. Soap was never limited to 6 in the stock game, so it needs no change. "
        "The stacked pictures look exactly as with 6 when more are stored: the row of cutting tools shows at most "
        "6, the Clothing Hut at most 6 bolts, and the soap at most 3 bars, as in the normal game. Pointing at the "
        "cutting tools or the Clothing Hut still shows how many there are (\"Cutting tools left: 23\"). The count "
        "is the game's own, saved in the save as before (a whole number, so 99 saves and loads as it is). **Needs "
        "no other patch.** **Off by default; Owner's Defaults ticks it.** Without the patch, a save holding more "
        "than 6 keeps its count until the next use puts it back to 6, as the normal game does. **Unverified in "
        f"play: the effect has not been tested live.** The companion is \"{DLL_NAME}\", started by VVFP "
        "More Companions.dll; if the DLL cannot be loaded, the stock game runs."
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
        "output_tag": "Up to 99 Supplies",
        "dependencies": [],
        "behavior_changes": [
            "Cutting tools (object 0x4D8614, count 0x4D8618) and cloth bolts (0x4D8AC8, count 0x4D8ACC): their "
            "produce routines (0x431400, 0x436890: += 3) cap at 99 instead of 6 (0x43142F, 0x4368E2), and the "
            "shared use-up 0x4369F0 clamps at 99 instead of 6 after each use (0x436A09).",
            "The cutting tools' stack (0x431480, sprite 0x18, three to a row) and the Clothing Hut's bolts "
            "(0x430C80, cloth_bolt) draw min(count, 6) pictures.",
        ],
        "explicit_non_changes": [
            "Soap (object 0x4D8D90, count 0x4D8D98) is not changed: the stock game never caps it (0x43A2DF += 3, "
            "use-up 0x43A410 with no upper clamp) and draws at most 3 bars (0x43A347).",
            "Production stays 3 at a time; every use (the cutting-tool harvest, job events 53 and 54, the tree "
            "decoration, the pruning puzzle) takes one as before; the achievements count what was made, never the "
            "store; the tooltips print the real count.",
            "The counts are saved and loaded as one dword each by the game's own save (0x436870 / 0x4313E0), with "
            "no clamp; nothing else is written.",
            "No executable byte is patched: the companion writes its 3 byte changes and 2 jumps at run time, only "
            "after verifying every stock byte, all or none.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; emulated (produce to 99 and never 100, a "
                            "use keeps 98, the stacks as with 6, the stock game without the patch) in "
                            "tests/test_vv4_supply_cap.py; runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/supply_cap/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [{
            "va": f"0x{va:X}",
            "stock_bytes": stock,
            "written_bytes": written if written else "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
            "routine": routine,
            "installed_by": INSTALLED_BY,
        } for va, stock, written, routine in SITES],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_vv4_supply_cap.ps1")], check=True)
    path = ROOT / "data" / f"{ID}_feature.json"
    path.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
