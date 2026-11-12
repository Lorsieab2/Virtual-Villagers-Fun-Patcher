"""Write the rows of "Scrolling Popups" (The Secret City, The Tree of Life, New Believers) -- the owner, 2026-11-12:
vertical and horizontal scrollbars on popups so the player can read practically unlimited text ("Let the patcher
handle it"), with the game's own scrollbar pictures, in a companion DLL started by VVFP Startup.dll.

Stage 1 (v1.35.97): the island-event dialog of each of the three games.  The sites and every address the companion
uses are in native/shared/scroll_popup.h (read from the stock executables with capstone; tests/test_scrolling_popups.py
pins the two together and runs the shipped DLL on the real dialog code in emulation).

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_scrolling_popups.ps1) and
pins it by SHA-256 in the three rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Scrolling Popups.dll"
DLL = ROOT / "assets" / "scrolling_popups" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
NAME = "Scrolling Popups"
GAMES = (3, 4, 5)
TITLES = {3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}

# (mouse site, its stock call target), (dialog ctor, draw site, justify), (size site, sizer), screen height
SITES = {
    3: (0x40451E, 0x4020A0, 0x4192F0, 0x418591, 0x40A0C0, 0x41983F, 0x40DDD0, 600),
    4: (0x404B02, 0x402320, 0x417790, 0x416F4C, 0x409C30, 0x417CEF, 0x40DE20, 600),
    5: (0x404A92, 0x4022D0, 0x418020, 0x4176E9, 0x409F00, 0x418573, 0x40E310, 768),
}
# The constructor's measures of its texts (`call justify`, measure only).
MEASURES = {
    3: (0x419611, 0x419648, 0x419681, 0x4197F7),
    4: (0x417AC7, 0x417B00, 0x417B3B, 0x417CA4),
    5: (0x41834E, 0x418387, 0x4183C2, 0x41852B),
}
ART = {3: "0x1B-0x1E, 0x19, 0x1A", 4: "0xA3-0xA6, 0xA1, 0xA2", 5: "0x81-0x84, 0x7F, 0x80"}


def row_id(game: int) -> str:
    return f"vv{game}_scrolling_popups"


def call_bytes(site: int, target: int) -> str:
    rel = (target - (site + 5)) & 0xFFFFFFFF
    return "E8" + rel.to_bytes(4, "little").hex().upper()


def description(game: int) -> str:
    return (
        "Island-event popups get scrollbars when their text does not fit: a popup is never taller than the screen "
        "(its buttons stay at its bottom, where they always are), and when its text is taller than the room left, "
        "or has a line wider than the box (one very long word), a vertical and/or a horizontal scrollbar appears, "
        "drawn with the game's own scrollbar pictures. Scroll with the mouse wheel over the popup, the arrows, by "
        "dragging the knob or by clicking the bar; the text starts at the top and starts over when the result "
        "replaces the question. A popup whose text fits looks and works exactly as before. This first stage covers "
        "the island-event popups (and Custom Island Events from Story / Cheat Upgrades, which use them); the text a "
        "popup can hold is still the game's 2,000 characters. There is no keyboard scrolling. Nothing is saved, so "
        "the patch can be ticked or unticked at any time. **Needs no other patch.** Off by default; Owner's Defaults "
        "ticks it. **Unverified in play: the effect has not been tested live.** The companion is \"" + DLL_NAME
        + "\", started by VVFP Startup.dll; if it cannot be loaded, the popups are as the game draws them."
    )


def row(game: int, dll_sha: str) -> dict:
    mouse, dispatch, ctor, draw, justify, size, sizer, screen = SITES[game]
    return {
        "id": row_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game),
        "output_tag": "Scrolling Popups",
        "dependencies": [],
        "conflicts": [],
        "behavior_changes": [
            f"The island-event dialog (constructor 0x{ctor:X}): its `call 0x{sizer:X}` sizing the panel (0x{size:X}) "
            f"calls {DLL_NAME}, which caps the height to the screen's ({screen} px, read from the drawing context) "
            "less 16 px above and below; the game then centres the panel and places its buttons from the bottom.",
            f"Its draw's `call 0x{justify:X}` drawing the body text (0x{draw:X}) calls the companion, which measures "
            "the text with that same routine (measure only) and its words with the game's counted draw; when the "
            "text fits the box (the panel's bottom less the room the dialog keeps for its buttons: 4 x a choice "
            "button's height with two choices, else 5/2 x the OK button's) it makes the stock call unchanged; "
            "otherwise it sets the drawing context's clip rectangle (+0x60) to the box, draws the text moved by the "
            "scroll position, restores the clip, and draws the scrollbars with the game's own pictures (image ids "
            f"{ART[game]}: Up/DownArrowButton, VerticalScrollTrack tiled, VerticalScrollKnob, WideSlider2, "
            "sliderhandle).",
            f"The event pump's `call 0x{dispatch:X}` handing a mouse event to the game (0x{mouse:X}) calls the "
            "companion first: a press on a scrollbar of the dialog drawn this moment, a knob drag and its release "
            "are used by the companion and not passed on; every other event goes to the game unchanged. The wheel "
            "is read by an SDL event watch (SDL_AddEventWatch, SDL_MOUSEWHEEL).",
        ] + [
            "A word wider than the text box (a long unbroken word) hangs the stock game: its justified paragraph "
            "backs off to an empty line and tries the same word again, for ever. The constructor's four measures of "
            "the dialog's texts (" + ", ".join(f"0x{va:X}" for va in MEASURES[game]) + f", `call 0x{justify:X}`, "
            "measure only) call the companion, which gives the paragraph the width of the text's widest word when "
            "that is wider than the box (the words measured with the game's counted draw, cut where the paragraph "
            "cuts them); the draw wraps at that same width and the box scrolls sideways.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion writes the three sites at run time, only after verifying "
            "their stock bytes and the instructions before them (all of them, or none).",
            "A popup whose text fits is drawn by the very same call as in the stock game; the dialog's text field "
            "keeps its 2,000-byte size; keys, the buttons, the events and the save are unchanged.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; the shipped companion emulated on the "
                            "published executable's own dialog constructor and draw code with the game's own fonts "
                            "and pictures (tests/test_scrolling_popups.py: the panel capped, the clip set and "
                            "restored, wheel, arrows, knob drag and track clicks moving the drawn lines, the buttons "
                            "at the panel's bottom, a fitting text drawn exactly as the stock game draws it); "
                            "runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/scrolling_popups/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{mouse:X}", "stock_bytes": call_bytes(mouse, dispatch), "written_bytes": "E8XXXXXXXX",
             "routine": "the event pump's call of the mouse dispatcher: scrollbar events are the companion's, every "
                        "other event is passed on to the stock dispatcher",
             "installed_by": INSTALLED_BY},
            {"va": f"0x{draw:X}", "stock_bytes": call_bytes(draw, justify), "written_bytes": "E8XXXXXXXX",
             "routine": "the island-event dialog's body text: the stock call when it fits, else clipped, scrolled "
                        "and given scrollbars",
             "installed_by": INSTALLED_BY},
            {"va": f"0x{size:X}", "stock_bytes": call_bytes(size, sizer), "written_bytes": "E8XXXXXXXX",
             "routine": "the island-event dialog's panel size: the height capped to the screen, then the stock sizer",
             "installed_by": INSTALLED_BY},
        ] + [
            {"va": f"0x{va:X}", "stock_bytes": call_bytes(va, justify), "written_bytes": "E8XXXXXXXX",
             "routine": "the island-event dialog constructor's measure of a text: at the widest word's width when "
                        "that is wider than the box (never stuck), else the stock call",
             "installed_by": INSTALLED_BY}
            for va in MEASURES[game]
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", path.relative_to(ROOT))


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_scrolling_popups.ps1")], check=True)
    dll_sha = sha(DLL)
    for game in GAMES:
        write(ROOT / "data" / f"{row_id(game)}_feature.json", row(game, dll_sha))


if __name__ == "__main__":
    main()
