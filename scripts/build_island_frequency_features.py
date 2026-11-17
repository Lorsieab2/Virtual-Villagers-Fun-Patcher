"""Write the five "More Frequent Island Events" rows (the owner, 2026-11-15: a new patch in all five games with a
slider like the other multiplier sliders, 2x to 100x: at N x the game's own island events come N times as often;
the opening events' timing and the rescue rule stay as in the stock game; off by default, on in Owner's Defaults,
the slider 2 unless moved).

THE STOCK GAMES (inputs\\vvN-stock-copy, capstone, 2026-11-15): each game's island event trigger, once its timer is
due, sets the timer to now and adds the next wait, drawn as `push K; call rand; ...; add eax, K; imul eax, eax,
0xE10` -- rand(K) + K whole real-life hours, in seconds:

  A New Home         K 12 (12 to 23 hours)  0x423883 0x42390A 0x423A61   (the trigger 0x4237BD)
  The Lost Children  K 10 (10 to 19 hours)  0x42EF93 0x42F01A 0x42F171   (0x42EECD)
  The Secret City    K 8  (8 to 15 hours)   0x4687FB 0x468832 0x4688C6   (0x468732)
  The Tree of Life   K 8                    0x43FAF7 0x43FB35 0x43FBC4   (0x43FA3D)
  New Believers      K 8                    0x4427C1 0x442828            (0x4426EA)

These are every `add eax, K; imul eax, eax, 0xE10` in each executable (the only other `imul ..., 0xE10` is the C
runtime's).  The first event's 15 minutes (a new village's timer, The Tree of Life 0x41F31B: + 0x384) and the 30
minutes while the village has seen no event (the trigger's `add [timer], 0x708`) are other instructions, left alone.

THE CHANGE: "VVFP Island Frequency.dll" (native/vvfp_island_frequency) makes each of those nine bytes a call of its
stub, which puts (rand + K) x 3600 / N in eax, N read at start from "VVFP Island Frequency.txt" (written by the
patcher beside the DLL, the slider's number).  The Origins companions' island timer keeper
(native/shared/island_timer_keep.h) keeps whatever the timer held when an event was bought, so it keeps and puts
back the shortened time with no change; none of its sites shares a byte with these.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_island_frequency.ps1) and
pins it by SHA-256 in all five rows.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "More Frequent Island Events"
DLL_NAME = "VVFP Island Frequency.dll"
DLL = ROOT / "assets" / "island_frequency" / DLL_NAME
CHOICE = "VVFP Island Frequency.txt"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
GAMES = (1, 2, 3, 4, 5)
HOURS = {1: 12, 2: 10, 3: 8, 4: 8, 5: 8}
SITES = {1: (0x423883, 0x42390A, 0x423A61), 2: (0x42EF93, 0x42F01A, 0x42F171), 3: (0x4687FB, 0x468832, 0x4688C6),
         4: (0x43FAF7, 0x43FB35, 0x43FBC4), 5: (0x4427C1, 0x442828)}
TRIGGER = {1: 0x4237BD, 2: 0x42EECD, 3: 0x468732, 4: 0x43FA3D, 5: 0x4426EA}


def row_id(game: int) -> str:
    return f"vv{game}_more_frequent_island_events"


def stock_bytes(game: int) -> str:
    return f"83C0{HOURS[game]:02X}69C0100E0000"


def description(game: int) -> str:
    k = HOURS[game]
    first = (" The first event's 15 minutes after a village is made and the 30 minutes before the next while the "
             "village has seen no event are as in the normal game." if game in (4, 5) else
             " The 30 minutes before the next event while the village has seen no event are as in the normal game.")
    return (
        "The game's own island events come more or less often: 0.1 to 100 times as often, as you choose with the "
        "More Frequent Island Events slider in the patcher window (in steps of 0.1, 2 unless you move it; 1 is the "
        "normal game, below 1 they come less often; type it in the "
        f"box beside the slider too). Normally the next event comes {k} to {2 * k - 1} whole real-life hours after "
        f"the last; at 2 times it comes {k // 2} to {(2 * k - 1) / 2:g} hours after it, at 10 times every "
        f"{k * 6} to {(2 * k - 1) * 6} minutes, at 0.5 times {2 * k} to {2 * (2 * k - 1)} hours." + first + " Which event comes, and every rule for it, is the "
        "game's own. A bought or picked island event (Origins, Story / Cheat Upgrades) still leaves the next "
        "natural event's time as it was, now the shorter time. **Needs no other patch.** Off by default; Owner's "
        "Defaults ticks it. **Unverified in play** (checked by emulation of the game's own trigger). The companion "
        f"is \"{DLL_NAME}\", started by VVFP Startup.dll, and the slider's number is written beside it in "
        f"\"{CHOICE}\"; nothing is written to a save."
    )


def row(game: int, dll_sha: str) -> dict:
    k = HOURS[game]
    return {
        "id": row_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game),
        "output_tag": "More Frequent Island Events",
        "dependencies": [],
        "conflicts": [],
        "behavior_changes": [
            f"Each of the island event trigger's ({TRIGGER[game]:#X}) draws of the next wait, `add eax, {k}; imul "
            "eax, eax, 0xE10` (rand(" + str(k) + f") + {k} whole hours in seconds) at "
            + ", ".join(f"0x{va:X}" for va in SITES[game])
            + ", becomes a call of the companion's stub, which puts (rand + " + str(k) + ") x 3600 / N in eax, N "
            f"the slider (0.1 to 100 in tenths, 2 by default; x 10 / tenths) read at start from \"{CHOICE}\" beside the companion (above 100 is "
            "100, below 0.1 is 0.1, none is 2). Every other register is the game's; the instruction after each site sets "
            "the flags anew or does not read them.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion writes its sites at run time, only after verifying their "
            "stock bytes (all of them, or none).",
            "The first event's 15 minutes, the 30 minutes while the village has seen no event, which event comes "
            "and its rules, pauses and time away are the game's own; the Origins companions' island timer keeper "
            "keeps and restores the shortened natural time after a bought or picked event.",
            "Nothing is written to a save, a villager record or a file; no text is shown.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; the companion's install and the shortened "
                            "wait emulated on the rendered executable's own trigger code in each public mode "
                            "(tests/test_island_frequency.py); runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/island_frequency/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock_bytes(game), "written_bytes": "E8XXXXXXXX90909090",
             "routine": f"the island event trigger's draw of the next wait (rand({k}) + {k} hours) goes to the "
                        "companion, which puts the wait divided by the slider's N in eax",
             "installed_by": INSTALLED_BY}
            for va in SITES[game]
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
                        str(ROOT / "scripts" / "build_vvfp_island_frequency.ps1")], check=True)
    dll_sha = sha(DLL)
    for game in GAMES:
        write(ROOT / "data" / f"{row_id(game)}_feature.json", row(game, dll_sha))


if __name__ == "__main__":
    main()
