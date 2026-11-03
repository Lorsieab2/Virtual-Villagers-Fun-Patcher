"""Write data/vv<N>_skip_all_intro_feature.json: "Skip All on the Intro Story", A New Home and The Lost Children
(the owner, 2026-11-03: The Secret City's stone "Skip All" button on the intro story of VV1 and VV2).

The behaviour lives in one companion, "VVFP Skip Intro.dll" (native/vvfp_skip_intro), started by VVFP
Startup.dll from its second word of companions (native/shared/startup_companions_2.h).  It patches no
executable byte: it replaces vtable slots of the story page classes at run time, after checking their stock
pointers (docs/reports/vv12-skip-all/design.md, proved by tests/test_skip_intro.py).

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_skip_intro.ps1) and
pins it by SHA-256 in both rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Skip Intro.dll"
DLL = ROOT / "assets" / "skip_intro" / DLL_NAME
GAMES = (1, 2)
NAME = "Skip All on the Intro Story"

SLOT_NAMES = {0: "destructor", 3: "button slot", 8: "update", 9: "activate"}
# Each game's story pages: (page, vtable, {slot: stock pointer}) -- the same facts as
# native/vvfp_skip_intro/vvfp_skip_intro.c SK_GAMES.
PAGES = {
    1: (("page 1 (state 0x15)", 0x4597F4, {0: 0x41EA00, 3: 0x41F640, 9: 0x41E5C0}),
        ("page 2, the help question (state 0x16)", 0x45982C, {8: 0x41F310})),
    2: (("page 1 (state 0x16)", 0x476AC4, {0: 0x428220, 3: 0x401190, 8: 0x428240, 9: 0x427DB0}),
        ("page 2 (state 0x17)", 0x476AFC, {0: 0x4288F0, 3: 0x401190, 9: 0x43A2B0}),
        ("page 3, the help question (state 0x18)", 0x476B34, {8: 0x4292C0})),
}
QUESTION = {
    1: "\"Would you like HELP the first time?\"",
    2: "\"Would you like tutorial tips turned on?\"",
}
STORY = {
    1: "two pages (the second asks the help question)",
    2: "three pages (the third asks the help question)",
}
DETAIL = {
    1: ("the Yes/No row (640, 560), drawn with main_wide_button2.png, the art of the help question's own Yes "
        "and No"),
    2: ("the Yes/No row (640, 550), drawn with popup_button1.png, the art of the help question's own Yes and "
        "No"),
}
YES_NO = {
    1: ("Yes: [game+0x9E1C] = the clock, sound 0x44. No: the tip flags [game+0x31+0x105..0x137] cleared, "
        "[game+0x151] = 1, [game+0x9E1C] = the clock, sound 0x43 (the last page's button slot 0x41EC40)."),
    2: ("Yes: the tutorial-tip flags [game+0x31+i] cleared and set from 0x186, the help flags +0x1F4..+0x1F7, "
        "+0x1FA, +0x1FB set, [game+0x2E4F8] = the clock, sound 0x4A. No: the same, then tips 0x186..0x1BE "
        "cleared, [game+0x1D8] = 1, sound 0x49 (the last page's button slot 0x428B30)."),
}


def description(game: int) -> str:
    return (
        "Adds a \"Skip All\" button to the story shown when a new village starts, as The Secret City has. "
        f"The story is {STORY[game]}; on every page before the question, a Skip All button sits at the bottom "
        "right, in the game's own button style and font. Clicking it ends the story at once: the page fades out "
        f"as it always does and you land straight on the help question, {QUESTION[game]}, with its Yes and No "
        "buttons already showing. Yes and No are the game's own and do exactly what they do at the end of the "
        "story read to the end. Without a click on Skip All the story is unchanged (a click anywhere else still "
        "turns the page). The button's word is translatable. **On by default.** **Needs no other patch.** "
        "**Not yet seen in a running game** (checked by emulation of the stock executable). The companion is "
        "\"" + DLL_NAME + "\", started by VVFP Startup.dll; saves are never written by it."
    )


def stock_hex(value: int) -> str:
    return struct.pack("<I", value).hex().upper()


def row(game: int, dll_sha: str) -> dict:
    detours = []
    for page, vtable, slots in PAGES[game]:
        for slot, stock in sorted(slots.items()):
            detours.append({
                "va": f"0x{vtable + 4 * slot:X}",
                "stock_bytes": stock_hex(stock),
                "routine": f"the story {page}'s vtable, slot {slot} ({SLOT_NAMES[slot]}, stock 0x{stock:X})",
                "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)",
            })
    last_page = PAGES[game][-1][0].split(",")[0]
    return {
        "id": f"vv{game}_skip_all_intro",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game),
        "output_tag": "Skip All",
        "behavior_changes": [
            "When a story page before the last is activated, a button is built once for it as the last page "
            "builds its Yes button -- the game's allocator, button constructor and label call, with the art "
            f"name pointer the Yes button uses -- at {DETAIL[game]}, labelled \"Skip All\" (asked of VVFP "
            "Translations.dll by key), id 0x5C1A, and added to the page as a child: the page draws it and the "
            "game's event manager hands it the mouse.",
            "Its click (message 8, id 0x5C1A, to the page's button slot) sets skip pending and calls the page's "
            "own event slot with event 2 -- the stock code a click anywhere runs -- so the page fades out and "
            "moves on as it always does." + (
                " When the first page's stock update has just moved the game to page 2's state (0x17) while skip "
                "is pending, the game goes to page 3's state (0x18) instead; page 3 was built with page 1."
                if game == 2 else ""),
            f"On the first frame of the {last_page} (the help question) while skip is pending, its frame count "
            "is put past its 50-frame (25 fast) wait before the stock update runs, so the stock update adds its "
            "Yes and No buttons on that frame; skip pending is then cleared (and is cleared whenever page 1 is "
            "activated).",
            "The answer is the stock last page's own: " + YES_NO[game],
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion replaces vtable slots of the story page classes at run "
            "time, only after verifying every stock pointer, and installs nothing on a different build.",
            "Without a click on Skip All every replaced slot runs the stock one with the same arguments; only "
            "the button is added. The pages' text, timing, the help question, its Yes and No buttons and what "
            "they set are the game's own.",
            "The F1 key and the typed-character page turn are untouched.",
            "No game art or font ships: the game draws its own button image with its own font. Nothing is "
            "written to a save, a villager record or a file.",
        ],
        "companion_files": [
            {"source": f"assets/skip_intro/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": detours,
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_skip_intro.ps1")], check=True)
    digest = sha(DLL)
    for game in GAMES:
        out = ROOT / "data" / f"vv{game}_skip_all_intro_feature.json"
        out.write_text(json.dumps(row(game, digest), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), digest)


if __name__ == "__main__":
    main()
