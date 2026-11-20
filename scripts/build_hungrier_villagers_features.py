"""Generate data/vv<N>_hungrier_villagers_feature.json (all five games): "Hungrier Villagers (0.1-10x Meals)".

The owner (2026-11-07), on making the games harder: "I like the hungrier villagers mod for all 5 games in addition to
the tech point cost slider thing" -- a slider like 0.1-10x Tech Cost (vv_fun_patcher.MEAL_MULTIPLIER_RANGE), off by
default; "have the classic vv difficulty on default for owner's defaults! (set the sliders to 2x."

THE MEAL (research/stock-executables, read with capstone, 2026-11-07).  Once per age unit each villager eats in one
routine, live and while catching up alike (every caller of it runs the same code; there is no separate catch-up
meal): first the meal, 2 food; then, by the difficulty, 2 more three times in four (rand(100) <= 75): above 2,000 food
(VV1) / 4,000 (VV2) / at 8,000 or more (VV3-VV5) on Normal (Medium), at any food level on Hard, never on Easy.
Both amounts are a signed byte immediate:
  * A New Home (0x42E900) and The Lost Children (0x43B690): `add dword [eax + food], -2`, then the routine's own
    clamp sets food to 0 when it is 0 or less (VV1 0x42ED0C, VV2 0x43BB39) before anything else reads it but the
    extra's threshold test; at x64 food dips at most to -256 there, nowhere near an overflow.
  * The Secret City, The Tree of Life and New Believers: `push -2` to the food-add routine (VV3 0x4263F0, VV4
    0x41D920, VV5 0x41EB40), which for a negative amount skips Food Mastery and the Food Gathered statistic, adds,
    and clamps a negative result to 0 at once (VV3 0x42643D, VV4 0x41D98B, VV5 0x41EBAB).
Children eat the same meal; nursing babies are not villagers and never eat; VV1's Golden Child and VV5's Heathens
are skipped by the stock code and stay so.

THE CHANGE: each of the two immediates becomes -2 x N, a signed byte for every N from 2 to 64 (-4 .. -128), in place;
the slider goes to 100 (the owner, 2026-11-15) and 65 to 100 are written as 64, the most the byte holds (never wrapped
round to a gain).  The owner (2026-11-17): every slider goes less as well as more, 0.1 to 10 in tenths, 1 the normal
game.  A meal is whole food, so an N whose 2 x N is whole (0.5, 1, 1.5, 2 ...) is written in the bytes as before (x 0.5:
-1); any other N (0.1, 0.3, 1.7 ...) leaves the bytes at the normal -2 and "VVFP Meal Scale.dll"
(native/vvfp_meal_scale, a third-word companion started by "VVFP More Companions.dll") makes each meal take 2 x N food
on average, the whole part every time and one more with the chance of the rest, reading N from "VVFP Meal Scale.txt"
beside it.  Every row ships the companion; with whole food its sites' stock bytes are not there, so it installs
nothing.
The manifest's own bytes are x 2, the slider's default; vv_fun_patcher.apply_meal_multiplier writes x N when a build
is published, checking that each site still holds the x 2 byte.

NOT CHANGED: the low-food skip of a meal, starvation, the snack at the food bin (1 food for a chance of 1 health),
the starting food, every event or puzzle that takes food, the stew, and everything that brings food in.

One command after the companion's source changes: this script builds it (scripts/build_vvfp_meal_scale.ps1) and
pins it by SHA-256 in all five rows.  --no-build pins what is already built.

Run after any change and re-run tests/test_hungrier_villagers.py.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
NAME = "Hungrier Villagers (0.1-10x Meals)"
DLL_NAME = "VVFP Meal Scale.dll"
DLL = ROOT / "assets" / "meal_scale" / DLL_NAME
CHOICE = "VVFP Meal Scale.txt"
FACTOR = 2                      # the manifest's own bytes: the slider's default
STOCK_MEAL = 2

# game: (exe, meal routine, [(instruction VA, its length, "meal" | "extra")], the extra's Normal threshold words)
GAMES = {
    1: ("A New Home", 0x42E900, [(0x42ECCC, 7, "meal"), (0x42ED03, 7, "extra")], "above 2,000 food"),
    2: ("The Lost Children", 0x43B690, [(0x43BAF9, 7, "meal"), (0x43BB30, 7, "extra")], "above 4,000 food"),
    3: ("The Secret City", 0x460080, [(0x460080, 2, "meal"), (0x4600C4, 2, "extra")], "at 8,000 food or more"),
    4: ("The Tree of Life", 0x4684C8, [(0x4684C8, 2, "meal"), (0x46850B, 2, "extra")], "at 8,000 food or more"),
    5: ("New Believers", 0x472D9E, [(0x472D9E, 2, "meal"), (0x472DEF, 2, "extra")], "at 8,000 food or more"),
}


def imm(n: int) -> int:
    return (-STOCK_MEAL * n) & 0xFF


def description(game: int) -> str:
    threshold = GAMES[game][3]
    return (
        "**Needs no other patch.** Off by default. Every villager's meal takes 0.1 to 10 times the normal food "
        "(a saved number above 10 is 10, the slider's top): you choose how many "
        f"times with the Hungrier Villagers slider in the patcher window (in steps of 0.1, {FACTOR} unless you move "
        "it; type it in the box beside the slider too; the slider reads -10 to 10: 10 is 10 times, -10 a tenth, -2 half, 1 in the middle the normal game; a number saved above 10 is 10). 1 is the normal game; above 1 the game is harder, below 1 "
        f"easier. Normally a villager's meal takes 2 food, and 2 more three times in four {threshold} on Normal "
        f"difficulty, at any food level on Hard, never on Easy; at x {FACTOR} that is 4 and 4 more, at x 0.5 1 and 1 "
        "more. A meal is whole food, so a number like 0.3 or 1.7 takes 2 x that ON AVERAGE: at x 0.3 a meal takes 1 "
        "food six times in ten and nothing otherwise (the companion \"" + DLL_NAME + "\" does that, reading the "
        "number from \"" + CHOICE + "\" beside it). Food never goes below 0: when it runs out the game's own starvation rules take over, as without the "
        "patch. Skipped meals when food is low, the snack at the food bin, events that take food and everything that "
        "brings food in are unchanged."
    )


def stock_site(game: int, va: int) -> str:
    """The meal instruction's seven stock bytes (the companion's site)."""
    name = GAMES[game][0]
    exe = STOCK / f"Virtual Villagers - {name}.exe"
    pe = pefile.PE(str(exe), fast_load=True)
    at = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
    return exe.read_bytes()[at:at + 7].hex().upper()


def feature(game: int, dll_sha: str) -> dict:
    name, _, sites, _ = GAMES[game]
    exe = STOCK / f"Virtual Villagers - {name}.exe"
    pe = pefile.PE(str(exe), fast_load=True)
    data = exe.read_bytes()
    patches = []
    for va, length, kind in sites:
        at = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase) + length - 1
        assert data[at] == imm(1), (game, hex(va), hex(data[at]))
        patches.append({
            "offset": "0x%X" % at,
            "before": "%02X" % imm(1),
            "after": "%02X" % imm(FACTOR),
            "purpose": (f"the {'meal' if kind == 'meal' else 'difficulty extra meal'} at 0x{va:X}: -2 food "
                        f"-> -{STOCK_MEAL * FACTOR} at x {FACTOR}"),
        })
    return {
        "id": f"vv{game}_hungrier_villagers",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game),
        "output_tag": "Hungrier Villagers",
        "behavior_changes": [
            f"The meal routine's two food amounts ({', '.join('0x%X' % va for va, _, _ in sites)}), each -2, become "
            "-2 x N when that is whole food (the slider, 0.1 to 10 in tenths; 2 by default; at x 10 a "
            "meal is -20); the stock clamp keeps food at 0 or more.",
            "Any other N leaves both at -2, and the companion makes each of the two instructions (all of them or "
            "none, after their stock bytes are checked) a call of its stub, which takes 2 x N food on average: the "
            "whole part every time and one more with the chance of the rest, drawn from the companion's own numbers "
            "(the game's rand is never drawn). The stock clamp keeps food at 0 or more, as before.",
        ],
        "explicit_non_changes": [
            "When a villager eats, the low-food skip, starvation, the snack at the food bin, starting food, events "
            "and everything that brings food in are unchanged.",
            "Two one-byte edits in place; no code is added and no executable space is claimed. The companion writes "
            "its sites at run time only, and only when the bytes are the stock ones.",
            "Nothing is written to a save, a villager record or a file; no text is shown.",
        ],
        "evidence_status": (
            "implemented from exact-build disassembly; the meal at every multiplier and the zero clamp are emulated "
            "in tests/test_hungrier_villagers.py; runtime/player confirmation pending"),
        "meal_multiplier": {"default": FACTOR, "minimum": 0.1, "maximum": 10, "stock_meal": STOCK_MEAL},
        "companion_files": [
            {"source": f"assets/meal_scale/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": patches,
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock_site(game, va), "written_bytes": "E8XXXXXXXX9090",
             "routine": f"the {'meal' if kind == 'meal' else 'difficulty extra meal'} goes to the companion, which "
                        "takes 2 x N food on average (only when 2 x N is not whole food)",
             "installed_by": f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"}
            for va, _, kind in sites
        ],
    }


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_meal_scale.ps1")], check=True)
    dll_sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game in GAMES:
        out = ROOT / "data" / f"vv{game}_hungrier_villagers_feature.json"
        out.write_text(json.dumps(feature(game, dll_sha), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                       newline="\n")
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
