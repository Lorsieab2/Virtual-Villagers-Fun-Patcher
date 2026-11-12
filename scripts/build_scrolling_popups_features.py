"""Write the rows of "Scrolling Popups" (all five games) -- the owner, 2026-11-12: vertical and horizontal scrollbars
on popups so the player can read practically unlimited text ("Let the patcher handle it"; "any popup!!!"), with the
game's own scrollbar pictures, in a companion DLL started by VVFP Startup.dll.

v1.35.97: the island-event dialog of The Secret City, The Tree of Life and New Believers (stage 1), and the message
box of all five games (stage 2).  A New Home and The Lost Children have no vertical scrollbar pictures of their own:
they borrow The Secret City's (assets/scrolling_popups/vvfp_scroll_*.png, byte-identical copies, shipped to Images\\
as new files; no game file is replaced).  The sites and every address the companion uses are in
native/shared/scroll_popup.h (read from the stock executables with capstone; tests/test_scrolling_popups.py pins the
two together and runs the companion on the real popup code in emulation).

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_scrolling_popups.ps1) and
pins it by SHA-256 in the five rows.  --no-build pins what is already built.
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
GAMES = (1, 2, 3, 4, 5)
TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
SCREEN = {1: (800, 600), 2: (800, 600), 3: (800, 600), 4: (800, 600), 5: (1024, 768)}

# The event pump's call of the mouse dispatcher: (site, its stock target).
MOUSE = {1: (0x403C6E, 0x401FE0), 2: (0x403EFE, 0x402070), 3: (0x40451E, 0x4020A0), 4: (0x404B02, 0x402320),
         5: (0x404A92, 0x4022D0)}
# The island-event dialog (The Secret City, The Tree of Life, New Believers): (dialog ctor, draw site, justify),
# (size site, sizer).
SITES = {
    3: (0x4192F0, 0x418591, 0x40A0C0, 0x41983F, 0x40DDD0),
    4: (0x417790, 0x416F4C, 0x409C30, 0x417CEF, 0x40DE20),
    5: (0x418020, 0x4176E9, 0x409F00, 0x418573, 0x40E310),
}
# The island-event constructor's measures of its texts (`call justify`, measure only).
MEASURES = {
    3: (0x419611, 0x419648, 0x419681, 0x4197F7),
    4: (0x417AC7, 0x417B00, 0x417B3B, 0x417CA4),
    5: (0x41834E, 0x418387, 0x4183C2, 0x41852B),
}
# The message box: (its vtable, its init, size site, sizer), and the text control draw's call of the text draw
# (site, text draw).
MSGBOX = {
    1: (0x459AB0, 0x427120, 0x427378, 0x40C760),
    2: (0x476DC4, 0x432C90, 0x432EE8, 0x40D140),
    3: (0x47F3AC, 0x41C3A0, 0x41C53F, 0x40DDD0),
    4: (0x48D3C4, 0x419A30, 0x419BE0, 0x40DE20),
    5: (0x4985D4, 0x41A2D0, 0x41A47B, 0x40E310),
}
CONTROL = {1: (0x40C197, 0x4094B0), 2: (0x40CB77, 0x4096A0), 3: (0x40D807, 0x40A060), 4: (0x40CFC9, 0x409BD0),
           5: (0x40D4B9, 0x409EA0)}
# The tip (theTipDialog): (its vtable, size site, sizer).
TIPS = {
    1: (0x481AD0, 0x436006, 0x40C760),
    2: (0x48FAC8, 0x443D86, 0x40D140),
    3: (0x47F454, 0x41DFF1, 0x40DDD0),
    4: (0x48D47C, 0x41B4B9, 0x40DE20),
    5: (0x49868C, 0x41BD13, 0x40E310),
}
# The frame draw's tail (`mov edx, [esi]` .. the `jmp` to the dialog's body draw): (site, stock bytes).
TAIL = {
    1: (0x40C9A3, "8B165F8BCE5E5B83C404FF6230"),
    2: (0x40D383, "8B165F8BCE5E5B83C404FF6230"),
    3: (0x40E013, "8B165F8BCE5E5B83C404FF6230"),
    4: (0x40E07C, "8B168B42305F8BCE5E83C404FFE0"),
    5: (0x40E56C, "8B168B42305F8BCE5E83C404FFE0"),
}
# A New Home's and The Lost Children's island-event dialogs: (name, vtable, size site, sizer).
EVENTS = {
    1: (("plain", 0x459AE4, 0x428830, 0x40C760), ("encounter / two choices", 0x459578, 0x41A634, 0x40C760),
        ("Mysterious Crate / visitor", 0x459BF8, 0x42D2B4, 0x40C760)),
    2: (("plain", 0x476DF8, 0x434A6B, 0x40D140), ("two choices", 0x476714, 0x42255F, 0x40D140),
        ("sacks and vials / two choices", 0x476F30, 0x439FA4, 0x40D140)),
}
# The tombstone (the grave's readout): its vtable (all five games).  A New Home and The Lost Children draw its lines
# in its body draw with the centred-block draw, whose one call of the core draw is a site: (site, core draw).
TOMBS = {1: 0x481B58, 2: 0x48FB48, 3: 0x47F498, 4: 0x48D4EC, 5: 0x4986E8}
CENTRE = {1: (0x409501, 0x409160), 2: (0x4096F1, 0x409360)}
# The tip's per-line `call justify` (The Secret City, The Tree of Life, New Believers).
TIP_JUSTIFY = {3: 0x41E433, 4: 0x41B9B0, 5: 0x41C200}
ART = {1: "WideSlider2.png and sliderhandle.png (its own) and Images\\vvfp_scroll_up/down/track/knob.png (The Secret "
          "City's UpArrowButton, DownArrowButton, VerticalScrollTrack and VerticalScrollKnob, borrowed)",
       3: "image ids 0x1B-0x1E, 0x19, 0x1A", 4: "image ids 0xA3-0xA6, 0xA1, 0xA2", 5: "image ids 0x81-0x84, 0x7F, 0x80"}
ART[2] = ART[1]
BORROWED = ("vvfp_scroll_up.png", "vvfp_scroll_down.png", "vvfp_scroll_track.png", "vvfp_scroll_knob.png")


def row_id(game: int) -> str:
    return f"vv{game}_scrolling_popups"


def call_bytes(site: int, target: int) -> str:
    rel = (target - (site + 5)) & 0xFFFFFFFF
    return "E8" + rel.to_bytes(4, "little").hex().upper()


def covered(game: int) -> str:
    """The popups the patch covers in `game`, in words."""
    parts = []
    if game in EVENTS:
        parts.append("island-event popups (plain, two-choice and visitor events, and Custom Island Events from Story "
                     "/ Cheat Upgrades; also when the result replaces the question in a popup sized for the "
                     "question)")
    if game in SITES:
        parts.append("island-event popups (and Custom Island Events from Story / Cheat Upgrades, which use them)")
    parts.append("message boxes (tech and puzzle results, confirmations)")
    parts.append("tips (the tutorial and notices)")
    parts.append("the tombstone (a long name or cause of death scrolls sideways)")
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def description(game: int) -> str:
    borrowed = (" A New Home and The Lost Children have no up/down scrollbar pictures of their own, so they borrow "
                "The Secret City's (shipped as new picture files; no game file is replaced)." if game in (1, 2) else "")
    return (
        "Popups get scrollbars when their text does not fit: a popup is never taller or wider than the screen (its "
        "buttons stay at its bottom, where they always are), and when its text is taller than the room left, or "
        "wider than the box (a long line, or one very long word), a vertical and/or a horizontal scrollbar appears, "
        "drawn with the game's own scrollbar pictures." + borrowed + " Scroll with the mouse wheel over the popup, "
        "the arrows, by dragging the knob or by clicking the bar; the text starts at the top and starts over when "
        "it changes. A popup whose text fits looks and works exactly as before. This covers the " + covered(game)
        + "; more popups follow. There is no keyboard scrolling. Nothing is saved, so the patch can be ticked or "
        "unticked at any time. **Needs no other patch.** Off by default; Owner's Defaults ticks it. **Unverified in "
        "play: the effect has not been tested live.** The companion is \"" + DLL_NAME + "\", started by VVFP "
        "Startup.dll; if it cannot be loaded, the popups are as the game draws them."
    )


def detours(game: int) -> list[dict]:
    """Every site the companion writes in `game`: va, stock bytes, what it does."""
    mouse, dispatch = MOUSE[game]
    out = [(mouse, dispatch, "the event pump's call of the mouse dispatcher: scrollbar events are the companion's, "
                             "every other event is passed on to the stock dispatcher")]
    if game in SITES:
        _ctor, draw, justify, size, sizer = SITES[game]
        out.append((draw, justify, "the island-event dialog's body text: the stock call when it fits, else clipped, "
                                   "scrolled and given scrollbars"))
        out.append((size, sizer, "the island-event dialog's panel size: the height capped to the screen, then the "
                                 "stock sizer"))
        out += [(va, justify, "the island-event dialog constructor's measure of a text: at the widest word's width "
                              "when that is wider than the box (never stuck), else the stock call")
                for va in MEASURES[game]]
    _vt, _init, bsize, bsizer = MSGBOX[game]
    ctl, text_draw = CONTROL[game]
    out.append((bsize, bsizer, "the message box's panel size: the width and the height capped to the screen, then "
                               "the stock sizer"))
    out.append((ctl, text_draw, "the text control draw's call of the text draw: the message box's text, when it does "
                                "not fit, clipped, scrolled and given scrollbars; every other text as the game draws "
                                "it"))
    for name, _vt, esize, esizer in EVENTS.get(game, ()):
        out.append((esize, esizer, f"the island-event dialog's ({name}) panel size: capped to the screen, the room it "
                                   "asks below its text kept, then the stock sizer"))
    _tvt, tsize, tsizer = TIPS[game]
    out.append((tsize, tsizer, "the tip's panel size: the width and the height capped to the screen, then the stock "
                               "sizer"))
    if game in TIP_JUSTIFY:
        out.append((TIP_JUSTIFY[game], SITES[game][2], "the tip's per-line justified paragraph: at the widest word's "
                                                       "width when that is wider than the box (never stuck)"))
    if game in CENTRE:
        out.append((CENTRE[game][0], CENTRE[game][1], "the centred-block draw's call of the core draw: while the "
                                                      "companion measures the tombstone's lines, each line's extent "
                                                      "is recorded and nothing is drawn; otherwise the stock call"))
    rows = [{"va": f"0x{va:X}", "stock_bytes": call_bytes(va, target), "written_bytes": "E8XXXXXXXX",
             "routine": routine, "installed_by": INSTALLED_BY} for va, target, routine in out]
    tail, stock = TAIL[game]
    rows.append({"va": f"0x{tail:X}", "stock_bytes": stock,
                 "written_bytes": "E9XXXXXXXX" + "90" * (len(stock) // 2 - 5),
                 "routine": "the frame draw's tail calling the dialog's body draw: a tip that asked for more than the "
                            "screen holds is drawn with its panel moved by the scroll position under a clip, with "
                            "the scrollbars; every other dialog's body is called as before",
                 "installed_by": INSTALLED_BY})
    return rows


def sites(game: int) -> list[tuple[int, str]]:
    return [(int(d["va"], 16), d["stock_bytes"]) for d in detours(game)]


def call_sites(game: int) -> list[tuple[int, str]]:
    """The sites that are 5-byte calls (all but the frame draw's tail)."""
    return [(va, stock) for va, stock in sites(game) if stock.startswith("E8") and len(stock) == 10]


def behavior_changes(game: int) -> list[str]:
    mouse, dispatch = MOUSE[game]
    w, h = SCREEN[game]
    out = []
    if game in SITES:
        ctor, draw, justify, size, sizer = SITES[game]
        out += [
            f"The island-event dialog (constructor 0x{ctor:X}): its `call 0x{sizer:X}` sizing the panel (0x{size:X}) "
            f"calls {DLL_NAME}, which caps the height to the screen's ({h} px, read from the drawing context) "
            "less 16 px above and below; the game then centres the panel and places its buttons from the bottom.",
            f"Its draw's `call 0x{justify:X}` drawing the body text (0x{draw:X}) calls the companion, which measures "
            "the text with that same routine (measure only) and its words with the game's counted draw; when the "
            "text fits the box (the panel's bottom less the room the dialog keeps for its buttons: 4 x a choice "
            "button's height with two choices, else 5/2 x the OK button's) it makes the stock call unchanged; "
            "otherwise it sets the drawing context's clip rectangle (+0x60) to the box, draws the text moved by the "
            "scroll position, restores the clip, and draws the scrollbars with the game's own pictures.",
            "A word wider than the text box (a long unbroken word) hangs the stock game: its justified paragraph "
            "backs off to an empty line and tries the same word again, for ever. The constructor's four measures of "
            "the dialog's texts (" + ", ".join(f"0x{va:X}" for va in MEASURES[game]) + f", `call 0x{justify:X}`, "
            "measure only) call the companion, which gives the paragraph the width of the text's widest word when "
            "that is wider than the box (the words measured with the game's counted draw, cut where the paragraph "
            "cuts them); the draw wraps at that same width and the box scrolls sideways.",
        ]
    vt, init, bsize, bsizer = MSGBOX[game]
    ctl, text_draw = CONTROL[game]
    out += [
        f"The message box (vtable 0x{vt:X}, laid out by 0x{init:X}): its `call 0x{bsizer:X}` sizing the panel "
        f"(0x{bsize:X}) calls the companion, which keeps the size asked for and caps the width and the height to the "
        f"screen's ({w} x {h}, read from the drawing context) less 16 px on each side; the game then centres the "
        "panel and places its text and buttons as always.",
        f"The text control draw's `call 0x{text_draw:X}` drawing a control's text (0x{ctl:X}) calls the companion: "
        "the text of a message box whose panel was capped (the control's parent has the message box's vtable and "
        "asked for more than the screen holds) is drawn under a clip rectangle set to the room the box keeps for it "
        "(0x14 below the panel's top, 0x1E from its sides, above its buttons), moved by the scroll position, with "
        "the scrollbars beside it; every other text, and a message box's text that fits, is the stock call "
        "unchanged.",
        f"The tip (vtable 0x{TIPS[game][0]:X}): its `call 0x{TIPS[game][2]:X}` sizing the panel "
        f"(0x{TIPS[game][1]:X}) is capped the same way. The frame draw's tail (0x{TAIL[game][0]:X}, `mov edx, [esi]` "
        "to the `jmp` into the dialog's body draw) jumps to the companion, which makes the same pops and calls the "
        "body draw: a tip that asked for more than the screen holds has its body drawn with its panel rectangle "
        "(+0x14..+0x20, which the body draw places everything by) moved by the scroll position and by what the "
        "capped panel moved its centred contents, under a clip set to the box (0x24 from the sides, 0x0A below the "
        "top, above twice the OK button's height), the rectangle put back after, with the scrollbars; every other "
        "dialog's body is called exactly as before."
        + (f" The tip's per-line `call 0x{SITES[game][2]:X}` (0x{TIP_JUSTIFY[game]:X}) is given the widest word's "
           "width when that is wider than the box, so the stock hang on a long word cannot happen there."
           if game in TIP_JUSTIFY else "")
        + "".join(
            f" The island-event dialog ({name}, vtable 0x{vt:X}): its `call 0x{esizer:X}` (0x{esize:X}) is capped the "
            "same way, and the room it asks for below its text is kept."
            for name, vt, esize, esizer in EVENTS.get(game, ()))
        + (" Through the frame draw's tail, an island-event dialog whose text shown now (measured with the game's own "
           "text height and width; the result when it has replaced the question) does not fit above that room, or "
           "is wider than the panel, has its body drawn with the y its constructor keeps (+0x64 / +0x6C) and, for a "
           "wide text, the panel's sides moved by the scroll position, under a clip, with the scrollbars."
           if game in EVENTS else ""),
        (f"The tombstone (vtable 0x{TOMBS[game]:X}, a fixed panel): its body draw draws every line with the "
         f"centred-block draw, whose call of the core draw (0x{CENTRE[game][0]:X}) calls the companion. Through the "
         "frame draw's tail the body is drawn once measuring (each line's extent recorded, nothing drawn, the clip "
         "empty), and when a line runs past the panel's sides (a long name, Cause of Death's cause line, a "
         "translation) the body is drawn with the panel rectangle (which the body draw and Cause of Death's line "
         "place everything by) moved by the scroll position, under a clip 16 px in from the sides and above the OK "
         "button, with a horizontal bar below the lines; otherwise exactly as before."
         if game in CENTRE else
         f"The tombstone (vtable 0x{TOMBS[game]:X}, a fixed panel): each line is a text control. At the text control "
         f"draw's call (0x{CONTROL[game][0]:X}) a line whose window is the tombstone is measured with all the "
         "tombstone's other lines (its window's text controls, as the text control draw places them); when one runs "
         "past the panel's sides (a long name, a long cause, a translation), each line is drawn moved by the scroll "
         "position under a clip 16 px in from the sides and above the Done button, with a horizontal bar below the "
         "lines; the editable epitaph and every tombstone that fits are drawn exactly as before."),
        f"The event pump's `call 0x{dispatch:X}` handing a mouse event to the game (0x{mouse:X}) calls the "
        "companion first: a press on a scrollbar of the popup drawn this moment, a knob drag and its release are "
        "used by the companion and not passed on; every other event goes to the game unchanged. The wheel is read "
        "by an SDL event watch (SDL_AddEventWatch, SDL_MOUSEWHEEL).",
        f"The scrollbars are the game's own pictures ({ART[game]}): Up/DownArrowButton, VerticalScrollTrack fitted "
        "to the bar's height, VerticalScrollKnob; the horizontal bar is WideSlider2 fitted to the vertical track's "
        "width (18 px) with sliderhandle fitted to the knob's size turned sideways.",
    ]
    return out


def row(game: int, dll_sha: str) -> dict:
    files = [{"source": f"assets/scrolling_popups/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha}]
    if game in (1, 2):
        files += [{"source": f"assets/scrolling_popups/{name}", "destination": f"Images/{name}",
                   "sha256": sha(ROOT / "assets" / "scrolling_popups" / name)} for name in BORROWED]
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
        "behavior_changes": behavior_changes(game),
        "explicit_non_changes": [
            "No executable byte is patched: the companion writes its sites at run time, only after verifying their "
            "stock bytes and the instructions before them (all of them, or none).",
            "A popup whose text fits is drawn by the very same call as in the stock game; the popups' text fields "
            "keep their sizes; keys, the buttons, the events and the save are unchanged."
            + (" No game picture is replaced: the borrowed pictures are new files." if game in (1, 2) else ""),
        ],
        "evidence_status": ("implemented from exact-build disassembly; the companion emulated on the published "
                            "executable's own popup code with the game's own fonts and pictures "
                            "(tests/test_scrolling_popups.py: the panel capped, the clip set and restored, wheel, "
                            "arrows, knob drag and track clicks moving the drawn lines, the buttons at the panel's "
                            "bottom, a fitting text drawn exactly as the stock game draws it); runtime/player "
                            "confirmation pending"),
        "companion_files": files,
        "patches": [],
        "runtime_detours": detours(game),
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
