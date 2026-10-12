"""Generate the five "Keep the Game's Own Log (ldwLog.txt)" rows.

Every Virtual Villagers game carries the LDW engine's log writer, which writes
Documents\\LDW\\<executable name>\\ldwLog.txt.  It has no on/off switch and every
call to it is live in all five executables, but the base game opens the file
with "wt" (each run erases the last), buffers it until a clean exit, and only
writes when something goes wrong -- so the owner had a file only from New
Believers.  "VVFP Game Log.dll" (native/vvfp_game_log) replaces the writer's
first instruction at run time with its own writer: the same lines, kept
across runs, written at once, repeats and bursts held down, rolled at 4 MiB.

Companion only: "VVFP Startup.dll" loads it as the game opens.  No executable
byte is patched.  The DLL is pinned by SHA-256, so re-run this after every
rebuild (scripts/build_vvfp_game_log.ps1).  tests/test_game_log.py checks the
call sites and lines below against the stock executables.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "game_log" / "VVFP Game Log.dll"
STOCK = ROOT / "research" / "stock-executables"
EXE = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
# The writer (its first 16 bytes, which the companion verifies) and every call to it:
# (call address, the format the call passes, what the line means).
WRITER = {
    "vv1": 0x40A970, "vv2": 0x40AB70, "vv3": 0x40B800, "vv4": 0x40B6C0, "vv5": 0x40BBB0,
}
FONT = ("Font Image not found: %s\n", "a font picture is missing (the game then closes)")
GRAPHIC = (" Missing Graphic -> %s", "a picture file is missing")
SOUND = ("ldwSoundFx Missing File ->%s", "a sound file is missing")
TIMER = ("Seconds Timer out of bounds!", "the game's one-second timer is more than 3 seconds ahead of the computer's clock, as when the clock is set back (checked every frame)")
TIP = ("Displaying Tip (%d) message!", "a tutorial tip is shown")
SM_NEAR = ("String Table (sm.xml) malformed near %s", "a text id the game asks for is not in Assets\\sm.xml")
SM_END = ("String Table (sm.xml) malformed looking for </Text> after %s", "a text in Assets\\sm.xml has no </Text>")
HEAL = ("%s could not find someone to heal.", "a healer found nobody to heal")
STUCK = ("%s is stuck!", "a villager's next step is blocked")
NO_WAY = ("%s cannot get from %d, %d (isBlocking=%s) to %d, %d (isBlocking=%s)", "a villager found no way to where it was going")
SHACK = ("%s is going to the love shack door at %d, %d (isBlocking=%s)", "a villager walks to the love shack door")
CALLS = {
    "vv1": [(0x4022E7, *FONT), (0x40A715, *GRAPHIC), (0x40AF57, *SOUND)],
    "vv2": [(0x402577, *FONT), (0x40A915, *GRAPHIC), (0x40B937, *SOUND), (0x42F1F1, *TIMER), (0x42F37B, *TIP)],
    "vv3": [(0x4025B7, *FONT), (0x40B5B5, *GRAPHIC), (0x40C5C7, *SOUND), (0x42F635, *SM_NEAR),
            (0x42F68E, *SM_END), (0x45B940, *HEAL), (0x4688F9, *TIMER)],
    "vv4": [(0x402875, *FONT), (0x40B248, *GRAPHIC), (0x40C4F8, *SOUND), (0x43FC28, *TIMER),
            (0x44D8B7, *SM_NEAR), (0x44D90E, *SM_END), (0x465149, *HEAL)],
    "vv5": [(0x402805, *FONT), (0x40B748, *GRAPHIC), (0x40C9E8, *SOUND), (0x442879, *TIMER),
            (0x450BC7, *SM_NEAR), (0x450C1E, *SM_END), (0x46930B, *STUCK), (0x469502, *NO_WAY),
            (0x46E1C9, *HEAL), (0x474536, *SHACK)],
}
# What the game writes, in words, for the description.
WORDS = {
    FONT[0]: "a missing font picture",
    GRAPHIC[0]: "a missing picture",
    SOUND[0]: "a missing sound",
    TIMER[0]: "\"Seconds Timer out of bounds!\" (the computer's clock was set back, so the game's one-second timer is ahead of it)",
    TIP[0]: "each tutorial tip shown",
    SM_NEAR[0]: "a text the game asks for that is missing from its text file (sm.xml)",
    SM_END[0]: "a text in sm.xml with no end",
    HEAL[0]: "a healer who could not find anyone to heal",
    STUCK[0]: "a villager who is stuck",
    NO_WAY[0]: "a villager who cannot find a way to where it is going",
    SHACK[0]: "each villager walking to the love shack door",
}
# What the other games log that this game's code does not contain.
CANNOT = {
    "vv1": "A New Home's code contains no other log line (no clock, text-file, healer, tip or path-finding line), so nothing else can be logged.",
    "vv2": "The Lost Children's code contains no text-file, healer or path-finding line, so those cannot be logged.",
    "vv3": "The Secret City's code contains no tip or path-finding line, so those cannot be logged (its villagers keep a pointer to the log, but no code writes through it).",
    "vv4": "The Tree of Life's code contains no tip or path-finding line, so those cannot be logged (its villagers keep a pointer to the log, but no code writes through it).",
    "vv5": "New Believers' code contains no tip line, so tips cannot be logged.",
}


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def row(game: str, sha: str) -> dict:
    pe = pefile.PE(str(STOCK / EXE[game]))
    image = pe.get_memory_mapped_image()
    writer = WRITER[game]
    stock = image[writer - 0x400000: writer - 0x400000 + 16].hex().upper()
    assert stock.startswith("56578B7C240C8B37833E0075"), (game, stock)
    seen: list[str] = []
    for _va, fmt, _what in CALLS[game]:
        if WORDS[fmt] not in seen:
            seen.append(WORDS[fmt])
    description = (
        "Keeps the game's own log, 'ldwLog.txt' in the game's save folder (Documents\\LDW\\<game "
        "executable name>\\). Every Virtual Villagers game has always had this log, but the base game "
        "starts the file afresh the first time it writes in each run (erasing the earlier runs' lines), "
        "holds what it writes in memory until the game closes (a crash loses it), and writes only when "
        "something goes wrong -- so most players never see the file. Now each time the game opens it adds "
        "a \"---- Game started ----\" line, and every line the game writes is added to the file at once "
        "and kept: " + _join(seen) + ". " + CANNOT[game] + " A line repeated without a break "
        "is written once a minute with how many times it repeated, at most 1,000 lines are written a "
        "minute, and when the file reaches 4 MB it is renamed 'ldwLog 1.txt' (then 2, 3, ...) and a new "
        "one is started, so no file grows without limit; nothing is ever deleted. **Needs no other patch.**"
    )
    behavior = [
        f"The game's log writer ({writer:#x}) is replaced at run time by the companion's: the same "
        "\"<date and time>: <line>\" text with CR-LF line ends, to the same file, "
        "Documents\\LDW\\<executable name up to its first dot>\\ldwLog.txt.",
        "The file is appended to (the base game opens it with \"wt\", which erases the earlier runs' lines), "
        "and each line is written to the file at once (the base game buffers until a clean exit).",
        "Each run starts with one \"---- Game started ----\" line, which also creates the file.",
        "A line that exactly repeats the one before it is written again only after a minute, preceded by "
        "\"(the line above was repeated <n> more times)\".",
        "At most 1,000 lines are written in a minute; the next line written says how many were left out.",
        "When ldwLog.txt would pass 4 MiB it is renamed \"ldwLog <n>.txt\" (n one more than the highest "
        "already there) and a new ldwLog.txt is started.",
    ] + [
        f"Call at {va:#x} writes \"{fmt.rstrip(chr(10))}\": {what}." for va, fmt, what in CALLS[game]
    ]
    return {
        "id": f"{game}_game_log",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": "Keep the Game's Own Log (ldwLog.txt)",
        "description": description,
        "output_tag": "Game Log",
        "behavior_changes": behavior,
        "explicit_non_changes": [
            "No executable byte is patched: the companion replaces the writer's first instruction at run "
            "time, only after verifying its first 16 bytes, and installs nothing on a different build.",
            "Which lines the game writes, and when, is the game's own: every call site is unchanged, and no "
            "line the game's code does not contain is ever written (only the \"Game started\" line and the "
            "repeat and left-out counts are the companion's).",
            "No save, village or villager data is read or written; nothing else in the game changes.",
            "Older 'ldwLog <n>.txt' files and any other file in the folder are never changed or deleted.",
        ],
        "evidence_status": ("static exact-build verification of the writer and every call to it in each "
                            "executable (tests/test_game_log.py); the companion's writer is run by "
                            "native/vvfp_game_log/game_log_harness.c"),
        "companion_files": [
            {"source": "assets/game_log/VVFP Game Log.dll", "destination": "VVFP Game Log.dll",
             "sha256": sha},
        ],
        "runtime_detours": [{
            "va": f"{writer:#x}",
            "stock_bytes": stock,
            "routine": "the LDW engine's log writer (cdecl: the log object, a format and its values)",
            "installed_by": "VVFP Game Log.dll, VvfpStartup",
        }],
        "patches": [],
    }


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game in EXE:
        path = ROOT / "data" / f"{game}_game_log_feature.json"
        path.write_text(json.dumps(row(game, sha), indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
                        newline="\n")
        print(path.name, sha)


if __name__ == "__main__":
    main()
