"""Write New Believers' "Heathens Keep Their Masks When Converted" row (the owner, 2026-11-08: "Heathens keep their
masks when converted - when a heathen converts their mask stays on their head (as if the player manually set it
using Change Appearance)", "Oh and the player can always Change Appearance to change it or take it off if they want
to."; default on in Owner's Defaults only).

The companion "VVFP Heathens Keep Masks.dll" (native/vvfp_heathens_keep_masks) splices ten sites at run time, all
or none, and puts the mask a converting Heathen wears into the Origins companion's mask table -- the store Change
Appearance keeps a believer's mask in -- then has that companion write its Village Masks file.  And (the owner,
2026-11-22) a believer who goes back to the Heathens is drawn in the mask they wore as a Heathen before (blue,
orange, red, purple or the Chief's) but behaves as an ordinary Heathen in the blue mask.
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
    (0x4669F5, "C786FC1C000000000000",
     "0x4669E0's (to a Heathen) `mov dword [esi+0x1CFC], 0`, before its call of the setter with 1: a believer "
     "whose Heathen mask is known has it kept by the Origins companion and the kind bytes cleared, then the role "
     "is cleared as in the stock game and it goes on at 0x4669FF (the setter's stock call)"),
    (0x415D0C, "E86F0B0500",
     "The Spa's `call 0x466880` with 1 (after its SetFaith(-10)): the same, return address 0x415D11"),
    (0x416C5B, "E820FC0400",
     "The Cracked Mask's `call 0x466880` with 1 (after its SetFaith(-10)): the same, return address 0x416C60"),
    (0x472732, "80BEED1C000000",
     "the render's head kind test `cmp byte [esi+0x1CED], 0` (orange): set too for a Heathen who went back "
     "wearing orange; goes on at 0x472739"),
    (0x472758, "80BEEE1C000000",
     "the render's head kind test `cmp byte [esi+0x1CEE], 0` (red): set too for one who went back wearing red; "
     "goes on at 0x47275F"),
    (0x4728EB, "80BEED1C000000",
     "the render's mask kind test `cmp byte [esi+0x1CED], 0` (orange): as at 0x472732; goes on at 0x4728F2"),
    (0x472903, "80BEEE1C000000",
     "the render's mask kind test `cmp byte [esi+0x1CEE], 0` (red): as at 0x472758; goes on at 0x47290A"),
    (0x4728C6, "8B86FC1C0000",
     "the render's role read `mov eax, [esi+0x1CFC]` for the mask art (12 and 14-16 purple, 13 the Chief's, the "
     "table 0x472B60): a Master's role (14) or the Chief's (13) for one who went back wearing purple or the "
     "Chief's mask, for that draw only; goes on at 0x4728CC"),
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
        "If a villager who was once a Heathen later loses their faith and goes back to the Heathens, they wear "
        "their own mask again -- the one they wore as a Heathen before, blue, orange, red, purple or the Chief's "
        "-- but act exactly like an ordinary Heathen in a blue mask: you can talk to them, they listen, and they "
        "can be converted again like any blue one (never a Master or the Chief again). "
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
            "Going back to the Heathens (the owner, 2026-11-22: \"a villager who goes back to the Heathens gets back "
            "exactly the mask they wore as a Heathen before ... behaviour is always an ordinary blue Heathen\"): "
            "at the three ways a believer becomes a Heathen through the faction setter 0x466880 with 1 (0x4669E0 "
            "-- SetFaith 0x467F90 at Faith 0 or below: the Faith drift and The Breaking Point, island events, the "
            "Custom Island Event's and Story / Cheat Upgrades' \"Becomes a Heathen\" -- spliced at its role clear "
            "0x4669F5; The Spa's own call 0x415D0C and The Cracked Mask's 0x416C5B), while the record is still a "
            "believer: the mask they wore as a Heathen -- the Former Heathens file's entry for them (VVFP Cause of "
            "Death.dll's new VvfpCauseFormerKind, the newest queued filing first), else the Retired Chief's role "
            "13, else the orange (+0x1CED) or red (+0x1CEE) kind byte the conversion 0x4668B0 left -- is put in the "
            "Origins mask table (VvfpMaskKeep 1..5), then both kind bytes and the role (+0x1CFC) are cleared, so "
            "every behaviour the game reads from them is an ordinary blue Heathen's (the drop test 0x443D4D lets a "
            "believer preach to them, the chasers' and scary ones' AI leave them out, never a puzzle role). A "
            "believer whose Heathen mask is not known and whose Change Appearance mask is orange, red, purple or "
            "the Chief's has it set to blue (a believer's chosen mask is never one they wore). The stock game left "
            "the bytes (an orange or red Heathen again, in look and behaviour; \"New Heathens Get a Heathen's "
            "Faith\" clears them for the drift: blue), drew a former purple Heathen blue, and made the Retired "
            "Chief through The Spa's own call the Heathen Chief again.",
            "The render's four kind tests (0x472732 and 0x472758 for the head, 0x4728EB and 0x472903 for the mask; "
            "`cmp byte [esi+0x1CED/0x1CEE], 0`) and its role read for the mask art (0x4728C6) answer the game's own "
            "values, or, for an ordinary Heathen (no puzzle role 12-17) with neither byte whose Origins mask is orange, red, purple or the "
            "Chief's: set for the orange (red) test, a Master's role 14 (the Chief's 13) for that draw. Drawn in "
            "their own mask; the bytes and role the behaviour reads stay 0. Blue needs nothing: the game has one "
            "blue Heathen look.",
            "Such a Heathen joining the tribe again keeps that mask as the Change Appearance mask (not the blue the "
            "bytes say), an orange or red one's kind byte put back as the stock conversion leaves a convert's. The "
            "logs' Mask line and the Former Heathens file name the mask drawn (native/shared/former_heathens.h "
            "vv_former_drawn_kind, from the companion's VvfpHeathensKeepMasksLook): VVFP Cause of Death.dll, VVFP "
            "Parentage Export.dll, VVFP Population Export.dll and VVFP Island Events.dll read it. The Heathen "
            "Doctor (cured) and the Heathen Mommy (her puzzle) can join and go back too: the same, their own mask.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion splices the ten sites at run time, only after verifying "
            "their stock bytes, all or none; each conversion splice makes the very instruction it replaced, every "
            "register and flag as they were, the setter seeing its stock return address; each drawing splice keeps "
            "every register (eax at the role read is the value the game loads there) and sets the zero flag as the "
            "compare it replaced.",
            "Nothing is charged and no \"Appearance changed\" is logged. Faith, faction and every other part of "
            "either conversion are the game's own. Nothing is written to a save file; the villager-record writes "
            "are the kind bytes and role of a villager going back to the Heathens (cleared) and an orange or red "
            "kind byte put back when they join again, and only while the Origins companion keeps the mask.",
            "A Heathen the game makes, and the puzzle Heathens while they are Heathens, are never touched.",
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
