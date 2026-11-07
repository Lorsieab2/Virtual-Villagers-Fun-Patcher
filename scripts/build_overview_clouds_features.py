"""Write the overview map's cloud rows (the owner, 2026-11-06: "Disable clouds on village overview map: ... makes those
graphics transparent ONLY on the overview map. Push clouds away on overview map with cursor: works exactly like how
VV4 handles it in games that do not have it. Default on").

Which games have clouds on the overview map (the Map button), read from the stock executables:

  * A New Home (0x42A5A0) and The Lost Children: no clouds on the overview map -- no rows.
  * The Secret City: five clouds (map_cloud01.png, sprite 0x27) drawn by the loop 0x46C3BD..0x46C3E1 of the overview
    screen's draw slot 0x46C2F0, always at alpha 1.0; they drift left and wrap (0x46C29F) but ignore the mouse.
  * The Tree of Life: five clouds (sprites 0xAE..0xB1) drawn by the loop 0x4454A1..0x4454D7 of the draw slot
    0x4453C0, each at its own alpha; its event slot 0x444B70 pushes them away from the mouse.
  * New Believers: the same five clouds and push (sprites 0x99..0x9C; loop 0x448623..0x448659 of 0x448510, push
    0x447CC0).

"Disable Clouds on the Overview Map" (vv3, vv4, vv5): the cloud loop's first instruction becomes a jump past the loop,
so no cloud is drawn on the overview map; nothing else of the screen, and nothing of any other screen, changes.
"Push Clouds Away on the Overview Map" (vv3 only: the others already push): "VVFP Push Clouds.dll"
(native/vvfp_push_clouds), started by VVFP Startup.dll from its second word, gives The Secret City The Tree of Life's
push from its own numbers.  tests/test_overview_clouds.py proves both by emulation.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_push_clouds.ps1) and pins it
by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_NAME = "VVFP Push Clouds.dll"
DLL = ROOT / "assets" / "push_clouds" / DLL_NAME
DISABLE = "Disable Clouds on the Overview Map"
PUSH = "Push Clouds Away on the Overview Map"
TEXT_BASE = 0x400000              # .text: file offset = VA - 0x400000 in every game

# game -> (loop start VA, stock bytes, patched bytes, loop end VA, draw slot, the cloud sprites, alpha, register note)
LOOPS = {
    3: (0x46C3BD, "8D7E08", "EB2490", 0x46C3E3, 0x46C2F0, "map_cloud01.png (sprite 0x27)", "always 1.0",
        "lea edi, [esi+8] becomes jmp 0x46C3E3; the code after the loop reads only the screen's own fields"),
    4: (0x4454A1, "8D9EAC000000", "EB3690909090", 0x4454D9, 0x4453C0,
        "map_cloud01.png and cloud variations1-3.png (sprites 0xAE..0xB1)", "each cloud's own",
        "lea ebx, [esi+0xAC] becomes jmp 0x4454D9 (four nops after it, never reached); the code after the loop "
        "compares with an immediate 0"),
    5: (0x448623, "8DAEAC000000", "31DBEB349090", 0x44865B, 0x448510,
        "map_cloud01.png and cloud variations1-3.png (sprites 0x99..0x9C)", "each cloud's own",
        "lea ebp, [esi+0xAC] becomes xor ebx, ebx / jmp 0x44865B (two nops after it, never reached): the code "
        "after the loop compares the screen's two leaving bytes with bl, which the stock loop leaves at 0"),
}
OWN_PUSH = {4: 0x444B70, 5: 0x447CC0}

# The Secret City's overview screen class (vtable 0x49EA04): slot -> (stock routine, what it is).
VTABLE = 0x49EA04
SLOTS = ((1, 0x46B980, "event slot (mouse moves and clicks)"), (8, 0x46C070, "update"),
         (9, 0x46B930, "activate (the screen is shown)"))
DRAW_CALL, SPRITE_DRAW = 0x46C3D8, 0x42EB90

NOT_SEEN = "**Not yet seen in a running game** (checked by emulation of the stock executable)."


def disable_description(game: int) -> str:
    if game == 3:
        hidden = (f"**With this on, the clouds are hidden, so {PUSH} has no visible effect until this is "
                  "unticked.**")
    else:
        hidden = ("**With this on, the clouds are hidden, so the game's own push (the clouds moving away from the "
                  "cursor) has no visible effect until this is unticked.**")
    return (
        "Hides the clouds that drift over the island on the overview map (the Map button): they are not drawn at "
        "all, so the whole island shows. Only the overview map changes: the village, its weather and every other "
        "screen look exactly as before, and the map's markers, buttons and its fade when you leave it are "
        f"unchanged. **On by default.** **Needs no other patch.** {hidden} {NOT_SEEN}"
    )


def push_description() -> str:
    return (
        "The clouds that drift over the island on the overview map (the Map button) move away from the mouse, "
        "exactly as in The Tree of Life: bring the cursor within about 80 pixels of a cloud's middle and it is "
        "pushed away from the cursor, sideways and up or down, faster the closer the cursor is (up to 5 pixels "
        "a frame, 10 when it is pushed the way the clouds drift), and it fades a little each time the mouse moves "
        "near it. It keeps going until the mouse moves again, and every cloud is back at full strength the next "
        "time the map is opened. The drift, and where a cloud comes back after leaving the map, are the game's "
        f"own. **On by default.** **Needs no other patch.** **While {DISABLE} is ticked the clouds are hidden, "
        f"so this has no visible effect until {DISABLE} is unticked.** {NOT_SEEN} The companion is "
        f"\"{DLL_NAME}\", started by VVFP Startup.dll; saves are never written by it."
    )


def disable_row(game: int) -> dict:
    start, before, after, end, draw, sprites, alpha, note = LOOPS[game]
    push = (f"The game's own push of the clouds away from the cursor (0x{OWN_PUSH[game]:X}) still moves them; "
            "with nothing drawn it cannot be seen." if game in OWN_PUSH else
            f"{PUSH} (its companion) still moves and fades the clouds; with nothing drawn it cannot be seen.")
    return {
        "id": f"vv{game}_disable_overview_clouds",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": DISABLE,
        "description": disable_description(game),
        "output_tag": "No Overview Clouds",
        "behavior_changes": [
            f"The overview screen's draw slot 0x{draw:X} draws its five clouds ({sprites}, alpha {alpha}) in the "
            f"loop 0x{start:X}..0x{end:X}; the loop is skipped: {note}. No cloud is drawn on the overview map.",
        ],
        "explicit_non_changes": [
            "Only the overview screen's own draw routine changes; the sprite draw routine, the cloud pictures and "
            "every other screen (the village view, its fog and weather, the title screen) are the game's own.",
            "The clouds' positions, drift and wrap are still updated every frame as before; nothing is written to "
            "a save, a villager record or a file. " + push,
        ],
        "companion_files": [],
        "patches": [{
            "offset": f"0x{start - TEXT_BASE:X}",
            "before": before,
            "after": after,
            "purpose": f"the overview map's cloud loop 0x{start:X}: {note}",
        }],
    }


def push_row(dll_sha: str) -> dict:
    detours = [{
        "va": f"0x{VTABLE + 4 * slot:X}",
        "stock_bytes": struct.pack("<I", stock).hex().upper(),
        "routine": f"the overview screen's vtable 0x{VTABLE:X}, slot {slot} ({what}, stock 0x{stock:X})",
        "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)",
    } for slot, stock, what in SLOTS]
    rel = (SPRITE_DRAW - (DRAW_CALL + 5)) & 0xFFFFFFFF
    detours.append({
        "va": f"0x{DRAW_CALL:X}",
        "stock_bytes": "E8" + struct.pack("<I", rel).hex().upper(),
        "written_bytes": "E8XXXXXXXX",
        "routine": f"the overview map's cloud loop: the call of the sprite draw 0x{SPRITE_DRAW:X} goes to the "
                   "companion, which puts the cloud's fade in the alpha argument and runs the stock draw",
        "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)",
    })
    return {
        "id": "vv3_push_overview_clouds",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv3",
        "name": PUSH,
        "description": push_description(),
        "output_tag": "Push Overview Clouds",
        "behavior_changes": [
            "Every mouse move (message 1 to the overview screen's event slot), for each of the five clouds at "
            "(x, y) (screen +8 + 12*i): dx = x - mouse x + 90, dy = y - mouse y + 50, distance = the float square "
            "root of dx*dx + dy*dy truncated, push = (100 - distance) / 20; push above 0: fade -= 0.01, vertical = "
            "push (dy >= 0) or -push, horizontal = -push (dx >= 0) or 2*push; otherwise both 0 -- The Tree of "
            "Life's event slot 0x444B70, number for number.",
            "Every frame the stock update moves the clouds (unless that frame ends the screen's leave, "
            "0x46C0BC..0x46C0FB): x -= horizontal and y += vertical first, then the stock drift and wrap -- The "
            "Tree of Life's x -= horizontal + drift, y += vertical (0x444AE0).",
            "Each cloud is drawn at its fade instead of the stock 1.0 (the call 0x46C3D8 of the sprite draw "
            "0x42EB90), as The Tree of Life draws each at its own alpha (0x4454B0); showing the screen (the "
            "activate slot) sets every fade back to 1.0, as The Tree of Life's activate 0x4447A0 does.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion replaces three vtable slots of the overview screen and "
            "one call in its cloud loop at run time, only after verifying every stock value, all or none.",
            "The stock event slot runs for every message (it ignores mouse moves), and the stock update and "
            "activate run as before: the clouds' drift (1 or 2 a frame), their wrap at the left edge and where "
            "they come back are The Secret City's own; clicks, buttons and the map's markers are unchanged.",
            "Nothing is written to a save, a villager record or a file; no text is shown.",
        ],
        "companion_files": [
            {"source": f"assets/push_clouds/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": detours,
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def write(name: str, row: dict) -> None:
    out = ROOT / "data" / name
    out.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", out.relative_to(ROOT))


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_push_clouds.ps1")], check=True)
    for game in LOOPS:
        write(f"vv{game}_disable_overview_clouds_feature.json", disable_row(game))
    write("vv3_push_overview_clouds_feature.json", push_row(sha(DLL)))


if __name__ == "__main__":
    main()
