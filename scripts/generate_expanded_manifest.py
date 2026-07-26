"""Convert reviewed experimental-expansion logs into release patch data."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAMES = ("vv3", "vv4", "vv5")
STOCK_SAVE_COMPATIBILITY = {
    "vv3": [
        {
            "offset": "0x28949",
            "before": "E852AAFDFF",
            "after": "E8632A0500",
            "purpose": "route expanded save loading through a stock-layout compatibility fallback",
        },
        {
            "offset": "0x28961",
            "before": "B9C74B0000",
            "after": "B92D690000",
            "purpose": "copy the complete expanded VV3 saved state after either load format succeeds",
        },
        {
            "offset": "0x7B3B1",
            "before": "00" * 102,
            "after": (
                "5589E551FF7510FF750CFF75088B4DFCE8DA7FF8FF84C07547"
                "FF7510681C2F0100FF75088B4DFCE8C37FF8FF84C0743056578B"
                "750881C6182F01008DBE98750000B914040000FDF3A4FC8B7D08"
                "81C7CC1E010031C0B9661D0000F3AB5F5EB00189EC5DC20C00"
            ),
            "purpose": "accept an exact stock VV3 save, move its saved-state tail, and zero the 106 inserted villager records",
        },
    ],
    "vv4": [
        {
            "offset": "0x1FC19",
            "before": "E8C23BFEFF",
            "after": "E8EF940600",
            "purpose": "route expanded save loading through a stock-layout compatibility fallback",
        },
        {
            "offset": "0x8910D",
            "before": "00" * 102,
            "after": (
                "5589E551FF7510FF750CFF75088B4DFCE8BEA6F7FF84C07547"
                "FF7510680C710100FF75088B4DFCE8A7A6F7FF84C0743056578B"
                "750881C6087101008DBEA86B0000B915040000FDF3A4FC8B7D08"
                "81C7B860010031C0B9EA1A0000F3AB5F5EB00189EC5DC20C00"
            ),
            "purpose": "accept an exact stock VV4 save, move its saved-state tail, and zero the 106 inserted villager records",
        },
    ],
    "vv5": [
        {
            "offset": "0x25709",
            "before": "E862E0FDFF",
            "after": "E85EEF0600",
            "purpose": "route expanded save loading through a stock-layout compatibility fallback",
        },
        {
            "offset": "0x9466C",
            "before": "00" * 102,
            "after": (
                "5589E551FF7510FF750CFF75088B4DFCE8EFF0F6FF84C07547"
                "FF751068787D0100FF75088B4DFCE8D8F0F6FF84C0743056578B"
                "750881C6747D01008DBEF0730000B919040000FDF3A4FC8B7D08"
                "81C7146D010031C0B9FC1C0000F3AB5F5EB00189EC5DC20C00"
            ),
            "purpose": "accept an exact stock VV5 save, move its saved-state tail, and zero the 106 inserted villager records",
        },
    ],
}
REVIEWED_RECORD_BOUNDS = {
    "vv3": [
        {
            "offset": "0x35A5A",
            "before": "96000000",
            "after": "00010000",
            "purpose": "expand the serialized villager-index validator from 150 to 256 records",
        },
        {
            "offset": "0x5EE69",
            "before": "96000000",
            "after": "00010000",
            "purpose": "expand the active-record lookup validator from 150 to 256 records",
        },
        {
            "offset": "0x60D46",
            "before": "95000000",
            "after": "FF000000",
            "purpose": "start reverse spatial villager selection at expanded record 255",
        },
    ],
    "vv4": [
        {
            "offset": "0x66045",
            "before": "95000000",
            "after": "FF000000",
            "purpose": "expand the first reverse villager-selection scan through record 255",
        },
        {
            "offset": "0x66C9C",
            "before": "95000000",
            "after": "FF000000",
            "purpose": "expand the second reverse villager-selection scan through record 255",
        },
        {
            "offset": "0x6683F",
            "before": "95000000",
            "after": "FF000000",
            "purpose": "expand the third reverse villager-selection scan through record 255",
        },
        {
            "offset": "0x66A0F",
            "before": "95000000",
            "after": "FF000000",
            "purpose": "expand the fourth reverse villager-selection scan through record 255",
        },
    ],
    "vv5": [
        {
            "offset": "0x6FA75",
            "before": "10A40000",
            "after": "00180100",
            "purpose": "expand the compact-save loader span from 150 to 256 villager records",
        },
        {
            "offset": "0x6F955",
            "before": "95000000",
            "after": "FF000000",
            "purpose": "expand the first reverse villager-selection scan through record 255",
        },
        {
            "offset": "0x708FC",
            "before": "95000000",
            "after": "FF000000",
            "purpose": "expand the second reverse villager-selection scan through record 255",
        },
        {
            "offset": "0x71D77",
            "before": "95000000",
            "after": "FF000000",
            "purpose": "expand the third reverse villager-selection scan through record 255",
        },
    ],
}


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
        patches.extend(STOCK_SAVE_COMPATIBILITY[game_id])
        patches.extend(REVIEWED_RECORD_BOUNDS[game_id])
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
