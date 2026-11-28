"""Write the "Sharp Full Screen Picture (4K Filter)" row (the owner, 2026-11-26: "I prefer a filter made by you. 4k
please"; 2026-11-27: filter E with the automatic step-down, bars or stretch, New Believers' window size for every
game, off by default).  PROTOTYPE STAGE: New Believers only until the owner has seen it.

The companion "VVFP Sharp Picture.dll" (native/vvfp_sharp_picture) changes the game's SDL imports at run time, all or
none; native/vvfp_sharp_picture/sharp_picture_harness.c runs the game's own frame routine with it.  Design and
measurements: docs/4k-filter-design.md.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_sharp_picture.ps1) and pins it
by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAMES = (5,)   # the prototype: New Believers first (the owner, 2026-11-27)
NAME = "Sharp Full Screen Picture (4K Filter)"
DLL_NAME = "VVFP Sharp Picture.dll"
DLL = ROOT / "assets" / "sharp_picture" / DLL_NAME
FRAME = {1: 0x403830, 2: 0x403AC0, 3: 0x4040E0, 4: 0x4046F0, 5: 0x404680}
SIZE = {1: "800x600", 2: "800x600", 3: "800x600", 4: "800x600", 5: "1024x768"}


def row_id(game: int) -> str:
    return f"vv{game}_sharp_picture"


def description(game: int) -> str:
    return (
        "Draws the game's picture sharp at your screen's own size -- up to 4K -- with a filter made for these games "
        "(not an AI upscale; no art is replaced): edges and text come out smooth and crisp instead of blocky or "
        "blurred. The game's window opens at New Believers' size, 1024x768 times your Windows scaling, and full "
        "screen uses every pixel of the screen. The picture keeps its shape with black bars at the sides (a click "
        "on a bar does nothing), or fills the whole screen if you choose stretch. When the computer's graphics "
        "cannot keep up, it switches to a lighter version of the filter by itself. **Use it with Fix Vanilla Bugs** (its "
        "full screen mouse fix puts the mouse on the right spot of the sharp picture). **If the graphics card "
        "cannot run it, the game draws its picture as before.** **Not yet seen in a running game** (checked with "
        f"the game's own drawing code and the games' own SDL2.dll). The companion is \"{DLL_NAME}\"; it never writes "
        "a save or a game file."
    )


def row(game: int, dll_sha: str) -> dict:
    frame = FRAME[game]
    return {
        "id": row_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game),
        "output_tag": "Sharp Picture",
        # Not a prerequisite (the patcher would refuse every build without Fix Vanilla Bugs): said in bold instead.
        "dependencies": [],
        "behavior_changes": [
            "The process is made system DPI aware before WinMain (SetProcessDpiAwarenessContext, else "
            "SetProcessDPIAware), so the window and full screen are the screen's real pixels; the game's "
            "SDL_CreateWindow import opens the window at 1024x768 times the system DPI / 96.",
            f"The frame routine 0x{frame:X} hands SDL its {SIZE[game]} picture with SDL_UpdateTexture, then "
            "SDL_RenderClear, SDL_RenderCopy and SDL_RenderPresent through the game's imports. The companion's "
            "SDL_UpdateTexture also copies the picture into a texture of its own Direct3D 9Ex device on the game's "
            "window (SDL's texture is still updated); SDL_RenderClear and SDL_RenderCopy return at once; "
            "SDL_RenderPresent draws the edge-directed 2x scaler (twice, 4x, when the picture is shown more than "
            "twice its size), a Catmull-Rom fit to the window (black bars, or stretched with \"stretch\" in VVFP "
            "Sharp Picture.txt) and presents. The GPU time is measured (timestamp queries); over 20 ms on average "
            "over 60 frames the filter steps down to 2x for the session.",
            "SDL's event filter (SDL_SetEventFilter) drops a left/right/middle press on a black bar and its release. "
            "VVFP Fullscreen Mouse.dll (Fix Vanilla Bugs) asks VvfpSharpPictureRect for the picture's rectangle while "
            "the filter draws, so SDL_GetMouseState and the pointer warp map to the picture in bars and stretch.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched and no byte of SDL2.dll: the companion changes six entries of the game's "
            "import table (SDL_CreateWindow and the four frame calls), only when SDL2.dll reports 2.0.3, the frame "
            "routine calls those imports in that order, they still hold SDL2.dll's own addresses and Direct3D 9Ex is "
            "there (d3d9.dll from the system folder).",
            "Any Direct3D failure stops the filter for the session and SDL draws the picture as before.",
            "Game files, art and saves are untouched; nothing is written.",
        ],
        "companion_files": [
            {"source": f"assets/sharp_picture/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
    }


def main() -> int:
    if "--no-build" not in sys.argv:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_sharp_picture.ps1")], check=True)
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game in GAMES:
        out = ROOT / "data" / f"{row_id(game)}_feature.json"
        out.write_text(json.dumps(row(game, sha), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                       newline="\n")
        print(out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
