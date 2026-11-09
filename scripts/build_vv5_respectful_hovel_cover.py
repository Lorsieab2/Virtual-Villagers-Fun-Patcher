"""Generate New Believers' "More Respectful Flower Hovel Cover" row in data/builds.json.

THE OWNER (2026-11-08): "a patch that overrides the normal one: "More Respectful Flower Hovel Cover" - overrides the
normal graphics and fix vanilla bugs vv5 graphic with the one I'm going to give you", then: "can you overlay this
respectful hovel cover over the original one? its bottom and left edges should be aligned to the bottom and left
edges of the original completed hovel."

THE ART.  The owner's picture (assets/vv5_respectful_hovel_cover/vvfp_respectful_hovel.png, the owner's file byte
for byte; the owner, after the first mockup: "I'll change the art", so this first one is a placeholder) is 800 x 500
RGBA, flattened from a GIMP file whose bottom layers are the completed hovel cover at
(0, 214): 634 x 286, flush with the canvas's bottom and left edges.  Graves, grave flowers, heathen heads and flowers
are painted on top, some above the old picture (up to y 44) and right of it (up to x 711).  The base is already in
the picture, so it is shipped as it is: compositing it over the hovel again would only thicken the hovel's faded
edges.  It goes to Images as vvfp_respectful_hovel.png; the game's own hovel_cover.png and Fix Vanilla Bugs'
vvfp_hovel.png are never changed.

THE DRAW.  0x4370E0 is the only drawer of image 0x1B (the image table entry 0x4CF768); once project 25
(CConvertLastHeathenPuzzle) is done it calls 0x44F320(sprite, x, y, 1.0f), which draws at once from the top-left
corner (the village at 100%, the Overview Map at 0.2125 through the same routine).  The stock top-left is
(1705, 1459); Fix Vanilla Bugs moves it to (1702, 1465), where the redrawn 634 x 286 picture meets the map's tiles,
so the completed hovel's bottom-left corner is (1702, 1751).  The new picture's bottom-left is put there:

    x = 1702                                (left edges)
    y = 1465 + 286 - height = 1751 - 500 = 1251   (bottom edges; the height is read from the PNG)

NEW ART: replace the PNG (8-bit RGBA, its own bottom and left edges on the completed hovel's), then run
    python scripts/build_vv5_respectful_hovel_cover.py
    python scripts/generate_transparency_docs.py
and the tests (tests/test_vv5_respectful_hovel_cover.py); the row's size, SHA-256 and draw y follow the file.

This row writes only bytes Fix Vanilla Bugs leaves alone, so the two build together and the result is the same with
Fix Vanilla Bugs on or off: the draw's tail (0x437104..0x43711E, its own code and the int3 padding after it) is
recoded to overwrite the pushed y with the new y, push 1702 and the sprite, and call 0x44F320; the "not solved" branch
(0x4370F1) is re-aimed at the moved pop esi / ret.  Fix Vanilla Bugs' x and y immediates (0x4370F5, 0x4370FF) still
load ecx and eax and are then unused.  The image table's name pointer (0x4CF76C, read only by the getter) is pointed
at a new "vvfp_respectful_hovel.png" in the zero tail of .rdata's last page (0x4C5FD0, before Fix Vanilla Bugs'
"eTipDemo" at 0x4C5FF0).

Run after any change: python scripts/build_vv5_respectful_hovel_cover.py
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURE = "vv5_respectful_hovel_cover"
AFTER = "vv5_fix_vanilla_bugs"
ART_SOURCE = "assets/vv5_respectful_hovel_cover/vvfp_respectful_hovel.png"
ART_NAME = "vvfp_respectful_hovel.png"
ART_DESTINATION = "Images/" + ART_NAME

# The completed hovel (Fix Vanilla Bugs' picture and place) and the new picture.  The picture's size is read from
# its PNG header, so new art is the one file plus a re-run of this script (and scripts/generate_transparency_docs.py).
HOVEL_LEFT, HOVEL_TOP, HOVEL_HEIGHT = 1702, 1465, 286
HOVEL_BOTTOM = HOVEL_TOP + HOVEL_HEIGHT                 # 1751


def art_size() -> tuple[int, int]:
    data = (ROOT / ART_SOURCE).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR" or (data[24], data[25]) != (8, 6):
        raise SystemExit(f"{ART_SOURCE} must be an 8-bit RGBA PNG")
    return struct.unpack(">II", data[16:24])


ART_WIDTH, ART_HEIGHT = art_size()
DRAW_X = HOVEL_LEFT
DRAW_Y = HOVEL_BOTTOM - ART_HEIGHT                      # 1251 for the 800 x 500 picture

BASE = 0x400000
DRAW_TAIL_VA = 0x437104
CALL_VA = 0x437118
POP_VA = 0x43711D
JE_VA = 0x4370F1
DRAW_QUEUE = 0x44F320
NAME_POINTER_VA = 0x4CF76C
NAME_VA = 0x4C5FD0
STOCK_NAME_VA = 0x49D5E0
RDATA_VA, RDATA_RAW = 0x495000, 0x95000
DATA_VA, DATA_RAW = 0x4C6000, 0xC6000
TEXT_VA, TEXT_RAW = 0x401000, 0x1000


def _file(va: int) -> int:
    if va >= DATA_VA:
        return va - DATA_VA + DATA_RAW
    if va >= RDATA_VA:
        return va - RDATA_VA + RDATA_RAW
    return va - TEXT_VA + TEXT_RAW


def draw_tail() -> bytes:
    """mov dword [esp], y / push x / push [esi+0x10] / mov ecx, 0x521078 / call 0x44F320 / pop esi / ret."""
    code = (b"\xC7\x04\x24" + struct.pack("<I", DRAW_Y)
            + b"\x68" + struct.pack("<I", DRAW_X)
            + b"\xFF\x76\x10"
            + b"\xB9" + struct.pack("<I", 0x521078)
            + b"\xE8" + struct.pack("<i", DRAW_QUEUE - (CALL_VA + 5))
            + b"\x5E\xC3")
    assert DRAW_TAIL_VA + len(code) == POP_VA + 2 and code[CALL_VA - DRAW_TAIL_VA] == 0xE8
    return code


STOCK_TAIL = bytes.fromhex("508B461050B978105200E80D8201005EC3") + b"\xCC" * 10


def patches() -> list[dict[str, str]]:
    name = ART_NAME.encode("ascii") + b"\0"
    tail = draw_tail()
    return [
        {"offset": f"0x{_file(JE_VA):X}", "before": "7420",
         "after": "74" + f"{POP_VA - (JE_VA + 2):02X}",
         "purpose": "The hovel cover's draw 0x4370E0: The Last Heathen not yet converted (je at 0x4370F1) jumps to "
                    "the moved pop esi / ret (0x43711D) instead of 0x437113"},
        {"offset": f"0x{_file(DRAW_TAIL_VA):X}", "before": STOCK_TAIL[:len(tail)].hex().upper(),
         "after": tail.hex().upper(),
         "purpose": f"The hovel cover's draw 0x4370E0 (only drawer of image 0x1B): the y already pushed becomes "
                    f"{DRAW_Y} and the x pushed is {DRAW_X} (mov dword [esp], {DRAW_Y} / push {DRAW_X} / push "
                    f"[esi+0x10] / mov ecx, 0x521078 / call 0x44F320 / pop esi / ret, into the int3 padding "
                    f"after it), so the {ART_WIDTH} x {ART_HEIGHT} picture's bottom-left corner is the completed "
                    f"hovel's ({HOVEL_LEFT}, {HOVEL_TOP + HOVEL_HEIGHT}), with or without Fix Vanilla Bugs"},
        {"offset": f"0x{_file(NAME_VA):X}", "before": "00" * len(name), "after": name.hex().upper(),
         "purpose": f"\"{ART_NAME}\" in the zero tail of .rdata's last page (0x{NAME_VA:X}), the name the image "
                    f"table's entry 0x1B is pointed at"},
        {"offset": f"0x{_file(NAME_POINTER_VA):X}", "before": struct.pack("<I", STOCK_NAME_VA).hex().upper(),
         "after": struct.pack("<I", NAME_VA).hex().upper(),
         "purpose": f"The image table entry 0x1B (0x4CF768): its name pointer 0x{STOCK_NAME_VA:X} "
                    f"(\"hovel_cover.png\", or Fix Vanilla Bugs' \"vvfp_hovel.png\") becomes 0x{NAME_VA:X} "
                    f"(\"{ART_NAME}\"), the owner's picture the row installs in Images"},
    ]


# The owner's opening sentence (2026-11-08), verbatim.
OPENING = "Turns the restored hovel into a memorial for the fallen. A symbol of everlasting peace throughout Isola."
DESCRIPTION = (
    OPENING + " Best paired with \"Memorial Actions Can Also Occur at the Heathen Hovel\". Once The Last Heathen is "
    "converted, the game covers the old Heathen camp with a picture of the empty hovel among flowers. With this patch "
    "that picture is the owner's more respectful one (art by Lorsieab2): the same hovel, with graves and flowers "
    "round the camp. Its bottom and left edges sit on the old picture's, so it rises above and reaches right of where "
    "the old one ended. It is drawn wherever the game draws the cover, the village and the Overview Map alike, and replaces "
    "both the game's own picture and Fix Vanilla Bugs' redrawn one; it sits where Fix Vanilla Bugs puts the hovel "
    "(on the map's own tiles), with Fix Vanilla Bugs on or off. The patcher puts it in the game's Images folder as "
    "vvfp_respectful_hovel.png; the game's own hovel_cover.png is never changed. When the cover appears and every "
    "other picture are the base game's own. On by default. **Needs no other patch.**")


def row() -> dict:
    art = (ROOT / ART_SOURCE).read_bytes()
    assert struct.unpack(">II", art[16:24]) == (ART_WIDTH, ART_HEIGHT) and art[25] == 6
    return {
        "id": FEATURE,
        "game_id": "vv5",
        "name": "More Respectful Flower Hovel Cover",
        "description": DESCRIPTION,
        "output_tag": "Respectful Hovel Cover",
        "behavior_changes": [
            f"The Last Heathen's hovel cover (0x4370E0, drawn once project 25 CConvertLastHeathenPuzzle is done; the "
            f"only drawer of image 0x1B) is the owner's {ART_WIDTH} x {ART_HEIGHT} picture {ART_NAME}, drawn with its "
            f"top-left at ({DRAW_X}, {DRAW_Y}): its bottom-left corner ({DRAW_X}, {DRAW_Y + ART_HEIGHT}) is the "
            f"completed hovel's ({HOVEL_LEFT}, {HOVEL_TOP} + {HOVEL_HEIGHT}), Fix Vanilla Bugs' place for the "
            f"634 x 286 picture. The draw's tail is recoded (0x437104..0x43711E, into the int3 padding after it): "
            f"the y pushed becomes {DRAW_Y}, the x pushed is {DRAW_X}, then the sprite, 0x44F320 and pop esi / ret "
            f"as before; the 'not converted' branch (0x4370F1) is re-aimed at the moved pop esi.",
            f"The image table entry 0x1B (0x4CF768) names \"{ART_NAME}\" (a new string at 0x{NAME_VA:X}, in the "
            f"zero tail of .rdata's last page) instead of 0x{STOCK_NAME_VA:X}.",
            "With Fix Vanilla Bugs too: its hovel bytes (the name at 0x49D5E0, the x and y immediates at 0x4370F5 and "
            "0x4370FF) are still written but no longer used for the cover; this row writes none of its bytes.",
        ],
        "explicit_non_changes": [
            "The game's own Images\\hovel_cover.png and Fix Vanilla Bugs' Images\\vvfp_hovel.png are never changed "
            "or removed. When the cover appears (The Last Heathen converted), the order it is drawn in, its scale "
            "(100% in the village, the Overview Map's own) and every other picture are the base game's own.",
            "No save data or villager record byte is written.",
        ],
        "evidence_status": (
            "static exact-build evidence (the cover's one load, one drawer, the immediate top-left blit through "
            "0x44F320 and the name pointer's one reader); emulation of the stock and rendered draw routine, alone and "
            "with Fix Vanilla Bugs (tests/test_vv5_respectful_hovel_cover.py): the cover is drawn once, with the "
            f"sprite, ({DRAW_X}, {DRAW_Y}) and 1.0, and not at all before the puzzle is solved; a mockup on the "
            "game's own map tiles; no live test yet"),
        "patches": patches(),
        "companion_files": [
            {"source": ART_SOURCE, "destination": ART_DESTINATION, "size": len(art),
             "sha256": hashlib.sha256(art).hexdigest().upper()},
        ],
    }


def main() -> None:
    path = ROOT / "data" / "builds.json"
    builds = json.loads(path.read_text(encoding="utf-8"))
    rows = [p for p in builds["fun_patches"] if p["id"] != FEATURE]
    at = next(i for i, p in enumerate(rows) if p["id"] == AFTER) + 1
    rows.insert(at, row())
    builds["fun_patches"] = rows
    path.write_text(json.dumps(builds, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"updated data/builds.json ({FEATURE})")


if __name__ == "__main__":
    main()
