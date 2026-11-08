"""Generate data/vv4_clothmaking_at_science_3_feature.json: "Clothmaking Unlocks at Science Level 3" (The Tree of Life).

The owner (2026-11-08): "the clothing hut itself unlocks as normal in Science Level 2, but the player can't make cloth
until Science Level 3. Dropping villagers on the pulpy vines used to make cloth give the standard "Don't know what to
do with these tough vines!" refusal." -- "mutually exclusive with the "clothing hut at science level 3" patch" (No
Fishing at Science Level 2: ticking one unticks the other), "Default ON in Owner's Defaults", and it replaces that
patch in Classic VV Difficulty; cloth already made stays usable.

THE STOCK DROP (research/stock-executables, capstone, 2026-11-08).  Cloth Invented (puzzle 7, CClothmaking vtable
0x48E908, constructor 0x436DC0) registers the vines' drop handler 0x436D40.  Its first case (0x436D74) asks whether
project 22 (the Clothing Hut) is finished (0x438960 on the project manager 0x4D8BF8): no -> the villager says "Don't
know what to do with these tough vines!" (string 0x249, 0x436D88..0x436D9E); yes (0x436D86 jne) -> 0x436D9F starts
action 0x7A, cutting the pulpy vines, the cloth chain.  Nothing else starts action 0x7A (its other mentions: its
registration 0x436DE4, an animation table 0x43AADB, a map-area count 0x455822), so no autonomous job or catch-up turn
makes cloth: the drop is the only way.

THE CHANGE: the finished test's jne (0x436D86, "75 17") goes to a check in the int3 padding after the handler
(0x436DB4..0x436DBF, 12 bytes, between the handler's ret and the constructor 0x436DC0): Science (tech 0, the levels
0x4D6F5C) below 3 -> the stock refusal at 0x436D88; else the stock cloth start 0x436D9F.  ecx (the villager) is loaded
at 0x436D82 before the jne, as both paths need.  Cloth bolts already in the store, the nets' use of them (0x464879),
the Clothing Hut and its site are unchanged.  Run after any change and re-run tests/test_vv4_clothmaking_at_science_3.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
OUT = ROOT / "data" / "vv4_clothmaking_at_science_3_feature.json"
JNE, REFUSE, START, CAVE, CAVE_END = 0x436D86, 0x436D88, 0x436D9F, 0x436DB4, 0x436DC0
SCIENCE = 0x4D6F5C

NAME = "Clothmaking Unlocks at Science Level 3"
DESCRIPTION = (
    "**Cannot be ticked with No Fishing at Science Level 2: ticking one unticks the other.** Makes cloth, and so the "
    "fishing nets, come later; off by default. The Clothing Hut appears at Science level 2 as normal, but until "
    "Science level 3 (70,000 tech points) a villager dropped on the vines says \"Don't know what to do with these "
    "tough vines!\" and makes no cloth. Cloth the village already has can still be used: the fishing nets are "
    "mended with it and the Clothing Hut gives clothes as before. Nothing else changes.")


def main() -> None:
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    cave = bytes(ks.asm(f"cmp dword ptr [{SCIENCE:#x}],3\njl {REFUSE:#x}\njmp {START:#x}", CAVE)[0])
    assert len(cave) <= CAVE_END - CAVE, len(cave)
    jne = bytes(ks.asm(f"jne {CAVE:#x}", JNE)[0])
    assert len(jne) == 2, jne.hex()
    pe = pefile.PE(str(EXE), fast_load=True)
    data = EXE.read_bytes()

    def off(va: int) -> int:
        return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)

    assert data[off(JNE):off(JNE) + 2] == bytes.fromhex("7517")
    pad = data[off(CAVE):off(CAVE) + len(cave)]
    assert pad == b"\xCC" * len(cave), pad.hex()
    feature = {
        "id": "vv4_clothmaking_at_science_3",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": NAME,
        "description": DESCRIPTION,
        "output_tag": "Clothmaking at Science 3",
        "behavior_changes": [
            "The vines' drop handler 0x436D40: with the Clothing Hut finished and Science below 3, the stock refusal "
            "\"Don't know what to do with these tough vines!\" (0x249) instead of the cloth start (action 0x7A); at "
            "Science 3 the stock cloth start.",
        ],
        "explicit_non_changes": [
            "The Clothing Hut's site (Science 2), its building, cloth bolts already in the store, the fishing nets' "
            "use of them, clothes and every other drop are unchanged; nothing but this drop starts cloth-making.",
            "Two guarded in-place edits: one jump and int3 padding after the handler; no executable tail space.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; the drop at Science 1, 2 and 3 with the "
                            "Clothing Hut finished and unfinished is emulated stock and patched in "
                            "tests/test_vv4_clothmaking_at_science_3.py; runtime/player confirmation pending"),
        "companion_files": [],
        "patches": [
            {"offset": "0x%X" % off(JNE), "before": "7517", "after": jne.hex().upper(),
             "purpose": "the Clothing Hut finished test's jump (0x436D86): to the Science check 0x436DB4"},
            {"offset": "0x%X" % off(CAVE), "before": pad.hex().upper(), "after": cave.hex().upper(),
             "purpose": "the Science check in the padding (0x436DB4): below 3 the stock refusal 0x436D88, else the "
                        "stock cloth start 0x436D9F"},
        ],
    }
    OUT.write_text(json.dumps(feature, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
