"""Write New Believers' "Heathens Keep Their Masks When Converted" row (the owner, 2026-11-08: "Heathens keep their
masks when converted - when a heathen converts their mask stays on their head (as if the player manually set it
using Change Appearance)", "Oh and the player can always Change Appearance to change it or take it off if they want
to."; default on in Owner's Defaults only).

The companion "VVFP Heathens Keep Masks.dll" (native/vvfp_heathens_keep_masks) splices two sites at run time, all or
none, and puts the mask a converting Heathen wears into the Origins companion's mask table -- the store Change
Appearance keeps a believer's mask in -- then has that companion write its Village Masks file.
tests/test_vv5_heathens_keep_masks.py proves it by emulation of the stock executable.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_heathens_keep_masks.ps1) and
pins it by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from origins_base_text import ORIGINS_BASE_SENTENCE  # noqa: E402
ROW_ID = "vv5_heathens_keep_masks_when_converted"
NAME = "Heathens Keep Their Masks When Converted"
DLL_NAME = "VVFP Heathens Keep Masks.dll"
DLL = ROOT / "assets" / "heathens_keep_masks" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
ORIGINS = "vv5_enable_origins_exclusive_features"

# (site VA, stock bytes, what the site is)
SITES = (
    (0x466966, "83BEFC1C00000D",
     "the conversion 0x4668B0's role test `cmp dword [esi+0x1CFC], 0xD` (before it clears every role but the "
     "Heathen Chief's at 0x46696F and the faction byte at 0x46697D): the companion keeps the Heathen's mask, then "
     "makes the same compare and goes on at the je 0x46696D"),
    (0x41699F, "E8DCFE0400",
     "The Defector's `call 0x466880` with 0 (after its SetFaith(+20)), which makes a Heathen whose Faith stayed at "
     "0 or below a believer without the conversion: the companion keeps the mask while the record is still a "
     "Heathen, then calls the setter with the stock return address 0x4169A4"),
)


def description() -> str:
    return (
        ORIGINS_BASE_SENTENCE + " "
        "\"Heathen\" masks are culturally important to them. Their choices must be "
        "honored. When a Heathen joins the tribe -- preached to, Spreading the Word, a "
        "God Power, a puzzle solved, an island event, a Custom Island Event, any way at all -- the mask they wore "
        "stays on their head: blue, orange, red, purple (the Heathen Doctor and the Heathen Masters) or the Tribal "
        "Chief's (the Heathen Chief, who becomes the Retired Chief). It is kept exactly as if you had chosen it "
        "with Change Appearance, so Change Appearance shows it as their mask and you can change it or take it off "
        "whenever you like; nothing is charged. **Reset to original gives it back**: a convert's original look "
        "is the head and body they had with the mask they wore (Original Looks for Reset to Original keeps it). "
        "**Heathens who "
        "joined the tribe before this patch keep the look they have now.** **Works the same with every other "
        "patch and in every population mode.** **Not yet seen in a running game** (checked by emulation of the "
        "stock executable). The companion is \"VVFP Heathens Keep Masks.dll\", started by VVFP Startup.dll; it "
        "writes only the Origins upgrades' own Village Masks file, never a save. If the Origins companion is not "
        "loaded, a convert loses the mask as in the stock game."
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
        "output_tag": "Heathens Keep Masks",
        "dependencies": [ORIGINS],
        "behavior_changes": [
            "When a Heathen joins the tribe through the conversion 0x4668B0 (SetFaith 0x467F90 above 0: preaching, "
            "Spreading the Word, a God Power's Faith, the puzzle rewards, island events; the Custom Island Event's "
            "\"Becomes a believer\") or The Defector's direct faction setter call 0x41699F, the mask the game draws "
            "on them (0x4728C6, native/shared/former_heathens.h vv_former_kind_of: purple for roles 12 and 14-16, "
            "the Chief's for role 13, else orange +0x1CED, red +0x1CEE or blue) is written into their nibble of the "
            "Origins companion's mask table (1 Blue, 2 Orange, 3 Red, 4 Purple, 5 the Tribal Chief's; 0x7B1D20, or "
            "0x7F1400 with 256 Villagers), the store Change Appearance keeps a believer's mask in, while the record "
            "is still a Heathen; then the Origins companion's WriteMaskSidecar writes its Village Masks file.",
            "The Origins render (the mask table at 0x472481) then draws that mask on the believer; Change "
            "Appearance shows it as the villager's mask, and changing it or choosing No Mask works as for any "
            "other mask.",
            "The Original Look companion is told (VvfpOriginalLookConverted): the original it kept while they were "
            "a Heathen, with no mask, takes the mask they wore, so Reset to original gives it back; an original "
            "kept while they were a believer (one who left for the Heathens and came back) or one with a mask of "
            "its own stays. With no original kept yet, its first sight records them with the kept mask.",
            "While the slot's Village Masks file has not loaded yet (held by another program a moment), the "
            "Origins companion's VvfpMaskKeep keeps the mask waiting, by the villager's identity, and puts it on "
            "them as soon as the load settles, then writes the file.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion splices the two sites at run time, only after verifying "
            "their stock bytes, all or none; each splice makes the very instruction it replaced, every register "
            "and flag as they were.",
            "Nothing is charged and no \"Appearance changed\" is logged. The role, Faith, faction, the Former "
            "Heathens file and every other part of the conversion are the game's own. Nothing is written to a save "
            "or a villager record.",
            "Without the Origins companion loaded (or one that is not New Believers'), or when its VvfpMaskOf does "
            "not answer the mask just written, nothing is kept: the convert loses the mask as in the stock game.",
            "Heathens converted before the row was installed are not given a mask.",
        ],
        "companion_files": [
            {"source": f"assets/heathens_keep_masks/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
             "routine": what, "installed_by": INSTALLED_BY}
            for va, stock, what in SITES
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_heathens_keep_masks.ps1")], check=True)
    out = ROOT / "data" / f"{ROW_ID.replace('_when_converted', '')}_feature.json"
    out.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
