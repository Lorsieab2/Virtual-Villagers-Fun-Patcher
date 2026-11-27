"""Pin "VVFP Exact Pickups.dll" and "VVFP Window Restore.dll" (which starts it) in the Fix Vanilla Bugs rows.

Run after scripts/build_vvfp_exact_pickups.ps1 or scripts/build_vvfp_window_restore.ps1:
  * every <game>_fix_vanilla_bugs row's Window Restore entry gets the built DLL's SHA-256;
  * The Secret City's, The Tree of Life's and New Believers' rows ship "VVFP Exact Pickups.dll" right after
    "VVFP Fullscreen Mouse.dll" (added when missing, re-pinned when present); A New Home and The Lost Children
    never ship it (their pick test is in the executable, tests/test_duplicate_pickups.py).
data/builds.json is edited as text, so nothing else in it changes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / "data" / "builds.json"
RESTORE = "assets/window_restore/VVFP Window Restore.dll"
PICKUPS = "assets/exact_pickups/VVFP Exact Pickups.dll"
MOUSE = "assets/fullscreen_mouse/VVFP Fullscreen Mouse.dll"
SHIPS_PICKUPS = ("vv3", "vv4", "vv5")


def digest(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest().upper()


def entry(source: str) -> str:
    return ("        {\n"
            f'          "source": "{source}",\n'
            f'          "destination": "{Path(source).name}",\n'
            f'          "sha256": "{digest(source)}"\n'
            "        }")


def pin(row: str, source: str) -> str:
    pattern = re.compile(r'("source": "' + re.escape(source) + r'",\s*"destination": "[^"]+",\s*"sha256": ")'
                         r'[0-9A-F]{64}"')
    assert len(pattern.findall(row)) == 1, source
    return pattern.sub(lambda m: m.group(1) + digest(source) + '"', row)


def main() -> None:
    text = BUILDS.read_text(encoding="utf-8")
    for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
        start = text.index(f'"id": "{game}_fix_vanilla_bugs",')
        end = text.index("\n    },\n", start)
        row = pin(text[start:end], RESTORE)
        if game in SHIPS_PICKUPS:
            if f'"source": "{PICKUPS}"' in row:
                row = pin(row, PICKUPS)
            else:
                at = row.index(f'"source": "{MOUSE}"')
                close = row.index("\n        }", at) + len("\n        }")
                row = row[:close] + ",\n" + entry(PICKUPS) + row[close:]
        else:
            assert f'"source": "{PICKUPS}"' not in row, game
        text = text[:start] + row + text[end:]
    json.loads(text)
    BUILDS.write_text(text, encoding="utf-8", newline="\n")
    print("pinned", digest(RESTORE), digest(PICKUPS))


if __name__ == "__main__":
    main()
