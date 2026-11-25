"""Write The Tree of Life's and New Believers' "X Buttons to Remove Chosen Founders" rows (the owner, 2026-11-24:
"add patches to vv4 and vv5 when selecting villagers for the expedition. I want to add X buttons beside the 5 slots so
we can choose new candidates.").

The companion "VVFP Founder X Buttons.dll" (native/vvfp_founder_x_buttons) splices the "Select 5 villagers" screen's
candidate generator and replaces two slots of its vtable at run time.  native/vvfp_founder_x_buttons/
founder_x_harness.c drives its logic (scripts/build_founder_x_harness.ps1) and tests/test_founder_x_buttons.py runs it
on the stock executables by emulation.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_founder_x_buttons.ps1) and pins
it by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "X Buttons to Remove Chosen Founders"
DLL_NAME = "VVFP Founder X Buttons.dll"
DLL = ROOT / "assets" / "founder_x_buttons" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"

# game -> the screen's vtable, its stock command handler (slot 3) and draw (slot 6), the generator, its table
# `mov ecx`, the record getter, the present byte, the next-candidate routine, the X picture and the Select string.
GAMES = {
    4: {"vtable": 0x48EB38, "handler": 0x43BC00, "draw": 0x43B6A0, "generator": 0x43B830, "table_mov": 0x43B83B,
        "getter": 0x466040, "present": 0x1CC4, "next": 0x43BA80, "image": "0xEB tech_info_btn.png",
        "done": "0xE1", "select": "0x54", "flag": "+0x171C4", "start": "0x41FEF0", "sound": "0x64 (tap.ogg)",
        "slots": "97, 245, 398, 546, 698", "plank": 140},
    5: {"vtable": 0x49A074, "handler": 0x43E600, "draw": 0x43E030, "generator": 0x43E220, "table_mov": 0x43E22B,
        "getter": 0x46F950, "present": 0x1CD4, "next": 0x43E470, "image": "0xCD btn_tech_question.png",
        "done": "0xDA", "select": "0x49", "flag": "+0x17E38", "start": "0x4259D0", "sound": "0x66 (tap.ogg)",
        "slots": "202, 350, 503, 651, 803", "plank": 215},
}


def row_id(game: int) -> str:
    return f"vv{game}_founder_x_buttons"


def description() -> str:
    return (
        "On the \"Select 5 villagers\" screen at the start of a new village, an X beside each chosen villager sends "
        "them away so you can pick another. Each X stands at the right end of that villager's name plank. Clicking "
        "it removes that villager for good, just as Reject does; the villagers chosen after them move along to fill "
        "the gap, and the candidate on show stays. Keep choosing until five are chosen. After the fifth pick, while "
        "the button says Done, an X takes you back to choosing: Select and Reject come back and a new candidate is "
        "shown. **Once the island has started, the five chosen are your founders and there are no X buttons.** The "
        "X buttons are the game's own stone button with an X on it. **Works the same with every other patch and in "
        "every population mode.** **Not yet seen in a running game** (checked by emulation of the stock executable "
        f"and a test harness). The companion is \"{DLL_NAME}\"; it never writes a save or a file."
    )


def _slot(value: int) -> str:
    return struct.pack("<I", value).hex().upper()


def row(game: int, dll_sha: str) -> dict:
    g = GAMES[game]
    return {
        "id": row_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(),
        "output_tag": "Founder X Buttons",
        "dependencies": [],
        "behavior_changes": [
            f"The \"Select 5 villagers\" screen (vtable 0x{g['vtable']:X}; +8 the candidate's record, +0x18 the "
            f"number chosen, +0x1C..+0x2C the five chosen records, +0x30 Reject) gets five buttons, ids 0x5858..0x585C, "
            f"made as its Select and Reject are (the button constructor, the image manager's picture {g['image']}, "
            f"the label \"X\" in Select's colours), each at the right end of its slot's name plank, just above it (slot "
            f"x {g['slots']}, plank top y {g['plank']}). They are added to and removed from the screen (its own "
            f"add / remove child calls) only in its draw (slot 6): one for each filled slot while a pick can change, "
            f"none once five are chosen with Reject still on (the manager's flag {g['flag']} started the island).",
            f"Its command handler (slot 3, stock 0x{g['handler']:X}) takes an X click (8, 0x5858 + k): the chosen "
            f"villager k's present byte (+0x{g['present']:X}) is cleared, as a Reject clears a candidate's; the later "
            f"chosen move down one and +0x18 drops by one; the game's sound {g['sound']} plays. In the Done state "
            f"(five chosen, Reject off) Select's label goes back to string {g['select']} (as the screen's show sets "
            f"it; string {g['done']} is Done), Reject is added back in the next draw and 0x{g['next']:X} shows a new "
            f"candidate. Every other message goes on to the stock handler.",
            f"The candidate generator 0x{g['generator']:X} (its entry spliced): the candidate on show (+8) is freed "
            f"when it is not chosen, and while the stock code runs +0x18 reads as the lowest record whose present "
            f"byte is 0 -- where the game's allocator makes the candidate -- so the stock code frees, fills and "
            f"returns that record (the stock screen counts on the candidate's record being +0x18); the real count is "
            f"put back after. With no X used that record is +0x18 itself: the stock screen unchanged. The villager "
            f"table is read from the generator's own `mov ecx` (0x{g['table_mov']:X}) and records through the getter "
            f"0x{g['getter']:X} until it returns none: 150 or 256 records.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion writes its three sites at run time, only after verifying "
            "their stock bytes and every routine it calls.",
            f"Select, Reject, the Done state, the start of the island (0x{int(g['start'], 16):X}, which takes every "
            "present record as a founder) and the candidates themselves are the game's own.",
            "A removed villager is gone as a rejected candidate is: no log calls it a disappearance (saves while "
            "this screen is open are not the village).",
            "Nothing is written but the screen's chosen list and count and the removed villager's present byte; no "
            "file.",
        ],
        "companion_files": [
            {"source": f"assets/founder_x_buttons/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{g['generator']:X}", "stock_bytes": "83EC108B4118", "written_bytes": "E9XXXXXXXX90",
             "routine": "the candidate generator's entry (`sub esp, 10h / mov eax, [ecx+18h]`): the candidate on show "
                        "freed unless chosen, +0x18 read as the lowest free record while the stock code runs",
             "installed_by": INSTALLED_BY},
            {"va": f"0x{g['vtable'] + 0xC:X}", "stock_bytes": _slot(g["handler"]), "written_bytes": "XXXXXXXX",
             "routine": "the screen's vtable slot 3, its command handler: an X click removes that chosen villager",
             "installed_by": INSTALLED_BY},
            {"va": f"0x{g['vtable'] + 0x18:X}", "stock_bytes": _slot(g["draw"]), "written_bytes": "XXXXXXXX",
             "routine": "the screen's vtable slot 6, its draw: the X buttons put on and taken off the screen, "
                        "Reject back after an X in the Done state, then the stock draw",
             "installed_by": INSTALLED_BY},
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_founder_x_buttons.ps1")], check=True)
    dll_sha = sha(DLL)
    for game in GAMES:
        out = ROOT / "data" / f"{row_id(game)}_feature.json"
        out.write_text(json.dumps(row(game, dll_sha), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
