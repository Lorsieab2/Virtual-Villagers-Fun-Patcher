"""Convert reviewed experimental-expansion logs into release patch data."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAMES = ("vv3", "vv4", "vv5")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    builds = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8-sig"))
    by_id = {game["id"]: game for game in builds["games"]}
    payload = {"format": 1, "games": {}}
    for game_id in GAMES:
        source = ROOT / "research" / "stock-executables" / by_id[game_id]["input_name"]
        prototype = ROOT / "research" / f"{game_id}-expanded-prototype.exe"
        edits = json.loads(
            (ROOT / "research" / f"{game_id}-expanded-prototype.json").read_text(
                encoding="utf-8"
            )
        )
        checksum_offset = struct.unpack_from("<I", source.read_bytes(), 0x3C)[0] + 24 + 64
        patches = []
        for edit in edits:
            if edit["offset"] == checksum_offset:
                continue
            patches.append(
                {
                    "offset": f"0x{edit['offset']:X}",
                    "before": struct.pack("<I", edit["old"]).hex().upper(),
                    "after": struct.pack("<I", edit["new"]).hex().upper(),
                    "purpose": edit["label"],
                }
            )
        payload["games"][game_id] = {
            "source_sha256": sha256(source),
            "prototype_sha256": sha256(prototype),
            "patch_count": len(patches),
            "patches": patches,
        }
    destination = ROOT / "data" / "expanded_256.json"
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
