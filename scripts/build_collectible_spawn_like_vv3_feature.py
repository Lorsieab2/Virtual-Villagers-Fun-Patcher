"""Generate data/vv4_collectible_spawn_like_vv3_feature.json: "Collectible Spawn Timing works like VV1-3" (The Tree of
Life).

The owner (2026-11-08): "Collectible Spawn Timing works like VV1-3 - part of the VV Classic Difficulty, they cause
natural collectible spawn timing to match the earlier 3 games. (does not affect collectible spawn alterations caused
by rain, wind flutes, fog, island events, god powers, or anything else)"; asked, the owner chose The Secret City's
timing (the same engine), no New Believers row (its timing already is The Secret City's), fog left alone, and the
heavy-weather second roll at The Secret City's 3 too ("fine do a for vv4").

THE STOCK ROLLS (research/stock-executables, capstone, 2026-11-08), once per update of the village, not while paused:
  * The Secret City 0x42DD6D..0x42DD98: rand(6000) < 3; above weather strength 50 a second rand(6000) < 3.
  * New Believers 0x414633..0x414670: rand(6000) < 3 (< 6 in fog, weather 4); above 50 a second < 3.  Already VV3's.
  * The Tree of Life 0x41437E..0x4143D2: rand(6000) < 4; in fog (weather 4) < (Wind Flute pieces / 2) x 4 instead
    (0x413B90 on set 0x6A); above 50 a second rand(6000) < 4.
All three place the item with the same routine shape (at most 2 random items out at once; each gone after 90 real-life
seconds), so only the thresholds differ.

THE CHANGE (The Tree of Life only):
  * 0x41437E..0x4143A7 (42 bytes), rewritten in place: the fog test first (cmp [0x6C461C], 4), then esi = 3 (stock
    4, which the stock code also used as the fog number), and in fog the Wind Flute threshold exactly as stock
    ((pieces / 2) x 4, with shl 2 for the two adds).  So fair weather and rain: 3; fog: unchanged.
  * 0x4143CF: the heavy-weather second roll's cmp eax, 4 -> 3.
What spawns (mushroom or collectible, rarity), the item limit, its lifetime, island events, the ghost and every other
spawn are unchanged.  Run after any change and re-run tests/test_collectible_spawn_like_vv3.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
OUT = ROOT / "data" / "vv4_collectible_spawn_like_vv3_feature.json"
BLOCK, BLOCK_END, SECOND = 0x41437E, 0x4143A8, 0x4143CF

CODE = f"""cmp dword ptr [0x6c461c],4
mov esi,3
jne {BLOCK_END:#x}
push 1
push 1
push 1
push 0x6a
mov ecx,0x4cc838
call 0x413b90
cdq
sub eax,edx
mov esi,eax
sar esi,1
shl esi,2"""

NAME = "Collectible Spawn Timing works like VV1-3"
DESCRIPTION = (
    "**Needs no other patch.** Makes collectibles come less often, as in The Secret City; off by default. A "
    "mushroom or collectible appears on its own with a chance of 4 in 6,000 each update of the village in The Tree "
    "of Life, against 3 in 6,000 in The Secret City (the same game engine), so about a quarter more often. With this "
    "patch the chance is The Secret City's 3 in 6,000, and in heavy rain (weather strength above 50) its second roll "
    "is 3 in 6,000 too. Fog's Wind Flute chance, rain making everything a mushroom, island events, the ghost and "
    "every other spawn are unchanged. New Believers needs no such patch: its timing already is The Secret City's.")


def main() -> None:
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    code = bytes(ks.asm(CODE, BLOCK)[0])
    assert len(code) == BLOCK_END - BLOCK, len(code)
    pe = pefile.PE(str(EXE), fast_load=True)
    data = EXE.read_bytes()

    def off(va: int) -> int:
        return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)

    before = data[off(BLOCK):off(BLOCK) + len(code)]
    assert before.hex().upper().startswith("BE04000000"), before.hex()
    second = data[off(SECOND):off(SECOND) + 3]
    assert second == bytes.fromhex("83F804"), second.hex()
    feature = {
        "id": "vv4_collectible_spawn_like_vv3",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": NAME,
        "description": DESCRIPTION,
        "output_tag": "Collectible Spawn like VV3",
        "behavior_changes": [
            "The random spawn roll 0x4143A8 compares rand(6000) with 3 (stock 4) outside fog; in fog (weather 4) the "
            "stock Wind Flute threshold (pieces / 2) x 4 is kept. The second roll above weather strength 50 "
            "(0x4143CF) compares with 3 (stock 4).",
        ],
        "explicit_non_changes": [
            "What appears (mushroom or collectible, its rarity), at most 2 random items out, their 90-second lifetime, "
            "fog's Wind Flute chance, rain's all-mushroom spawns, island events, the ghost and every other spawn are "
            "unchanged.",
            "Two guarded in-place edits (the 42-byte roll block, rewritten to the same length, and one immediate); no "
            "code is added and no executable space is claimed.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; the thresholds in fair weather, rain, fog with "
                            "0 to 12 Wind Flute pieces and heavy weather are emulated stock and patched in "
                            "tests/test_collectible_spawn_like_vv3.py; runtime/player confirmation pending"),
        "companion_files": [],
        "patches": [
            {"offset": "0x%X" % off(BLOCK), "before": before.hex().upper(), "after": code.hex().upper(),
             "purpose": "the random spawn roll's threshold (0x41437E): 3 outside fog (stock 4); fog's Wind Flute "
                        "threshold kept"},
            {"offset": "0x%X" % (off(SECOND) + 2), "before": "04", "after": "03",
             "purpose": "the second roll above weather strength 50 (0x4143CF): rand(6000) < 3 (stock 4)"},
        ],
    }
    OUT.write_text(json.dumps(feature, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
