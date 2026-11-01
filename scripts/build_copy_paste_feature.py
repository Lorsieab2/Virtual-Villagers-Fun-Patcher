"""Write data/vv<N>_copy_paste_feature.json: "Copy and Paste in Text Boxes", all five games (the owner,
2026-11-01: "Can you add the ability to copy and paste into text fields in the games?").

The behaviour lives in one companion, "VVFP Copy and Paste.dll" (native/vvfp_copy_paste), started by VVFP
Startup.dll from its second word of companions (native/shared/startup_companions_2.h).  It patches no
executable byte: it detours each game's SDL_KEYDOWN case at run time, after checking its stock bytes
(native/vvfp_copy_paste/copy_paste_tables.h, proved by tests/test_copy_paste.py).

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_copy_paste.ps1) and
pins it by SHA-256 in all five rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Copy and Paste.dll"
DLL = ROOT / "assets" / "copy_paste" / DLL_NAME
GAMES = (1, 2, 3, 4, 5)
NAME = "Copy and Paste in Text Boxes"

# Each game's SDL_KEYDOWN case (its first two instructions, moved into the hook), the text box's keyboard
# handler and the event manager -- the same facts as native/vvfp_copy_paste/copy_paste_tables.h.
SITES = {
    1: ("0x4039D6", "8B4C243C81F941000040", "0x40BE30", "0x48AEC8"),
    2: ("0x403C66", "8B4C243C81F941000040", "0x40C810", "0x4997A8"),
    3: ("0x404286", "8B4C243C81F941000040", "0x40D4A0", "0x4B3088"),
    4: ("0x4048A6", "8B4C243881F93A000040", "0x40D750", "0x4CB508"),
    5: ("0x404836", "8B4C243881F93A000040", "0x40DC40", "0x4DACCC"),
}

BOXES = {
    1: "the tribe name when a new village starts and the villager names on the Details screen",
    2: "the tribe name when a new village starts and the villager names on the Details screen",
    3: "the tribe name when a new village starts and the villager names on the Details screen",
    4: "the tribe name when a new village starts and the villager names on the Details screen",
    5: "the tribe name when a new village starts and the villager names on the Details screen",
}


def description(game: int) -> str:
    return (
        "Lets you copy and paste in the game's text boxes (" + BOXES[game] + ", and every other box you type "
        "in). While a box has typing focus: Ctrl+V or Shift+Insert pastes the text on the Windows clipboard "
        "where you type (the boxes have no movable caret, so at the end of the text); Ctrl+C or Ctrl+Insert "
        "copies the box's whole text; Ctrl+X cuts it (copies it, then empties the box). Pasted text keeps "
        "the box's own rules: its own character filter (a numbers-only box takes only digits), and its own "
        "length limit, cut before the first character that does not fit, never inside a character. Line "
        "breaks and tabs become spaces; other control characters are dropped, and so is every character "
        "the game cannot show (never turned into '?'): **with Render Unicode with In-Game Fonts or Use Unicode "
        "Font on, every character those patches let you type is pasted (at least every Windows-1252 character: "
        "accented letters, curly quotes, €, ...); with neither, plain English letters, digits and signs "
        "only.** The keys never reach the game as letters or shortcuts. "
        "Ctrl+A does nothing: the game's boxes have no selection. When the clipboard is busy or holds no "
        "text, nothing happens. **On by default.** **Needs no other patch; works with or without Render "
        "Unicode with In-Game Fonts and Use Unicode Font.** **Not yet seen in a running game** (checked by emulation of each "
        "stock executable). The companion is \"" + DLL_NAME + "\", started by VVFP Startup.dll; saves are "
        "never written by it."
    )


def row(game: int, dll_sha: str) -> dict:
    site, stock, handler, manager = SITES[game]
    return {
        "id": f"vv{game}_copy_paste",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game),
        "output_tag": "Copy and Paste",
        "behavior_changes": [
            f"The event pump's SDL_KEYDOWN case ({site}) first asks the companion about the key: Ctrl+V, "
            "Shift+Insert, Ctrl+C, Ctrl+Insert and Ctrl+X (no Alt, no Windows key), while a text box has "
            "typing focus, are handled and the pump goes on with the next event; every other key, and these "
            "keys while no box has focus, go on to the stock case exactly as before.",
            f"The focused box is found the way the game types into it: the game's own keyboard listeners "
            f"(event manager {manager}), in the game's order, the first whose keyboard handler is the text "
            f"box's ({handler}) that has focus ([box+0x25]) on a screen that takes input.",
            "Paste: the clipboard's CF_UNICODETEXT, composed (NFC) and split into whole characters, CR/LF/Tab "
            "as spaces, other control characters and lone surrogates dropped, each character turned into the "
            "box's bytes (UTF-8 when the loaded Unicode companion -- VVFP Unicode Text.dll, else VVFP Unicode "
            "Font.dll -- answers VvfpGlyphsUtf8() == 1; every printable Windows-1252 character when it answers 0; "
            "printable ASCII when neither is loaded), a character the game cannot show dropped, a numbers-only "
            "box's filter applied, and the whole cut before the first character that does not fit the box's byte "
            "limit ([box+0x28]). UTF-8 text goes in through that companion's VvfpBoxInsertUtf8 (it inserts as "
            "typing does); otherwise the bytes are typed into the box through its own handler, one character "
            "message each.",
            "Copy: the box's text bytes, read back by the same rule, put on the clipboard as CF_UNICODETEXT; "
            "Cut: the same, then (only when the copy succeeded) the box's own Backspace for each byte.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion replaces the SDL_KEYDOWN case's first ten bytes at "
            "run time, only after verifying their stock bytes, and installs nothing on a different build.",
            "Nothing is written but a focused box's text, through the box's own handler and its own rules: "
            "opening and closing a box without these keys leaves its bytes exactly as they were. Saves, "
            "villager records and the patcher's files are never written.",
            "The clipboard is opened and closed on the game thread and never waited for; busy or empty means "
            "nothing happens. A fault is abandoned and the key goes on to the stock code.",
            "The SDL_TEXTINPUT case (detoured by Render Unicode with In-Game Fonts) is not touched; both "
            "patches work together or alone.",
        ],
        "companion_files": [
            {"source": f"assets/copy_paste/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": site, "stock_bytes": stock,
             "routine": "the event pump's SDL_KEYDOWN case (mov ecx, [esp + sym]; cmp ecx, imm32)",
             "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"},
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_copy_paste.ps1")], check=True)
    digest = sha(DLL)
    for game in GAMES:
        out = ROOT / "data" / f"vv{game}_copy_paste_feature.json"
        out.write_text(json.dumps(row(game, digest), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), digest)


if __name__ == "__main__":
    main()
