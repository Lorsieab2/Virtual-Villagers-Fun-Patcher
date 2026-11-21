"""Write New Believers' "Practicing Devotion Builds Faith and Divine Energy" row (the owner, 2026-11-21: "practicing
Devotion skill should give a 1-point increase in Faith. like a small chance which adds up over time."; "people
practicing devotion should also give 1 point in Divine Energy too. same mechanics").

The companion "VVFP Devotion Faith.dll" (native/vvfp_devotion_faith) splices the skill check's entry at run time.
tests/test_vv5_devotion_faith.py proves it by emulation of the stock executable.

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_devotion_faith.ps1) and pins it
by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW_ID = "vv5_devotion_builds_faith"
NAME = "Practicing Devotion Builds Faith and Divine Energy"
DLL_NAME = "VVFP Devotion Faith.dll"
DLL = ROOT / "assets" / "devotion_faith" / DLL_NAME
OUT = ROOT / "data" / f"{ROW_ID}_feature.json"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP More Companions.dll, third word)"

SITE = (0x46B270, "83EC0C5355",
        "the skill check 0x46B270's entry (`sub esp, 0Ch / push ebx / push ebp`; thiscall on the villager, the skill "
        "at [esp+4]). For skill 5 (Devotion), a believer (+0x1CEC 0) outside roles 12-17 (+0x1CFC) gets two "
        "separate rand(10) < 1 rolls (the game's rand 0x403660): Faith (+0x1CF0) +1 below 100; Divine Energy +1 "
        "through the village manager's (the word 0x4DACE0) adder 0x424F80 (kept at most the cap). Then the five bytes re-run and the "
        "stock check goes on at 0x46B275")


def description() -> str:
    return (
        "Each time a believer practises Devotion, there is a 1 in 10 chance their Faith rises by 1, and a separate "
        "1 in 10 chance the village gains 1 Divine Energy: small amounts that add up over time. Practising "
        "Devotion is the game's Devotion skill check. It comes on 1 Honoring in 8 (half go to the statue, and "
        "1 in 4 of those end in the check) and on every sermon to a Heathen, while playing and while catching up. "
        "The rolls come whether the check passes or fails; the Devotion skill, its odds and its gain stay the "
        "normal game's. **Honoring as a job needs the statue at its first stage or The Tribute Statue solved, as "
        "in the normal game.** **Faith never goes above 100 and Divine Energy never above the village's cap** "
        "(the game's own limits). **Believers only:** Heathens never practise Devotion, and the Heathen Doctor, the "
        "Heathen Chief (and the Retired Chief), the three Masters and the Heathen Mommy never get these rolls. "
        "**\"Faith Loss is Doubled/Gains Halved\" does not change these chances; Spirituality and Learning change "
        "how often the Devotion check passes, not these rolls.** **Works the same with every other patch and in "
        "every population mode.** **Not yet seen in a running game** (checked by emulation of the stock "
        f"executable). The companion is \"{DLL_NAME}\"; it never writes a save or a file."
    )


def row(dll_sha: str) -> dict:
    va, stock, what = SITE
    return {
        "id": ROW_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": NAME,
        "description": description(),
        "output_tag": "Devotion Faith",
        "dependencies": [],
        "behavior_changes": [
            "The skill check 0x46B270 with skill 5 (Devotion) -- Honoring's step-10 check (0x45CC9B queues it on "
            "rand(100) < 25 in the statue-spot half of behaviour 0xA0, 0x45CB70; run by 0x473B30 at 0x473C69 live and "
            "by the catch-up runner 0x46E020) and the sermon end's preacher check (0x468E9A) -- first makes two "
            "separate rolls for a believer (+0x1CEC 0) outside roles 12-17 (+0x1CFC): rand(10) < 1 adds 1 to Faith "
            "(+0x1CF0) when it is below 100 (a plain write; +1 from 1..99 never crosses the setter 0x467F90's "
            "conversion bounds); rand(10) < 1 adds 1 Divine Energy through the village manager's (read from the word "
            "0x4DACE0 the getter 0x425950 keeps it in, never the getter) adder "
            "0x424F80, which keeps it from 0 to the cap (+0x17D60). rand(10) is the game's 0x403660 (rand() % 10): "
            "3,277 values in 32,768, 10.00% (the owner, 2026-11-21: \"1 in 10 for both is good\").",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion splices the one site at run time, only after verifying its "
            "stock bytes; registers and flags are as they were, and the stock check runs unchanged afterwards.",
            "Every other skill's check, Heathens and roles 12-17 make no roll at all (the game's random numbers are "
            "drawn only for a believer's Devotion check).",
            "The Devotion check's odds and gain, Spirituality, Learning, the Faith drift, Faith Loss is Doubled/Gains "
            "Halved, preaching's own Faith for the Heathen, and the Divine Energy income and cap are the game's own.",
            "Nothing is written but the villager's Faith and the village's Divine Energy; no file.",
        ],
        "companion_files": [
            {"source": f"assets/devotion_faith/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": "E9XXXXXXXX",
             "routine": what, "installed_by": INSTALLED_BY},
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_devotion_faith.ps1")], check=True)
    OUT.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
