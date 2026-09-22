"""Generate the numeric-keys feature manifests.

Two rows come out of this:

  data/vv1_number_keys_feature.json
      A New Home: the companion DLL that makes the number keys glide the view
      to a section of the island, plus a new random tip announcing it.

  data/vv2_numeric_keys_tip_feature.json
      The Lost Children: the existing tip's wording changed from "keypad" to
      "numeric keys", for parity with A New Home.

Every `before` is read from the stock executable rather than typed in, and
each site is asserted to hold exactly what the design says before a manifest
is written, so a wrong address fails here instead of at apply time.

THE VV1 TIP.  The game picks a loading-screen tip as string id
0x207 + rand(30) at 0x4256B0 and resolves ids through a first-match linear
scan of 629 twenty-byte {id, en, de, fr, es} records at 0x487208 (0x433880,
ids below 0x280 only).  Ids 0x205/0x206 and 0x225/0x226 are all taken, so the
range cannot simply grow.  What is free: the demo-version string record
(id 0x259, "Demo version has a max population of 9!", no code reference in
the full game) with 92 contiguous bytes of its own storage, and the ids
0x27D/0x27E.  So: "points." (id 0x225, one reference at 0x4346E7) is
renumbered to 0x27E, the demo record becomes id 0x225 with all four language
pointers at its own storage, the new tip is written over that storage, and
the picker draws from 31.  No executable space is claimed anywhere.

THE VV2 TIP.  Record 0x312 keeps its id; only its English pointer moves to
the demo record's storage (id 0x35C, also unreferenced), where the longer
wording fits with room to spare.  The German pointer is untouched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
VV1 = STOCK / "Virtual Villagers - A New Home.exe"
VV2 = STOCK / "Virtual Villagers - The Lost Children.exe"
DLL = ROOT / "assets" / "number_keys" / "VVFP VV1 Number Keys.dll"

TIP = b"You can zip around the island with your numeric keys.\0"

# VV1 sites (file offsets; sections .text/.text/.data/.data/.rdata)
VV1_PICKER = 0x256B0           # push 0x1e  -> push 0x1f
VV1_POINTS_PUSH = 0x346E7      # push 0x225 -> push 0x27e
VV1_POINTS_RECORD = 0x87244    # record id 0x225 -> 0x27e
VV1_DEMO_RECORD = 0x8744C      # record id 0x259 -> 0x225, pointers -> 0x481240
VV1_DEMO_STRINGS = 0x81240     # 92 bytes of the demo record's own strings
VV1_DEMO_STRINGS_VA = 0x481240
VV1_STORAGE = 92

# VV2 sites
VV2_TIP_RECORD_EN = 0x98038    # record 0x312's English pointer 0x4836F0 -> 0x48F4DC
VV2_DEMO_STRINGS = 0x8F4DC
VV2_DEMO_STRINGS_VA = 0x48F4DC


def le(value: int) -> bytes:
    return value.to_bytes(4, "little")


def patch(source: bytes, offset: int, before: bytes, after: bytes, purpose: str) -> dict:
    actual = source[offset:offset + len(before)]
    if actual != before:
        raise SystemExit(f"stock bytes at {offset:#x} are {actual.hex()}, expected {before.hex()}")
    if len(after) != len(before):
        raise SystemExit(f"patch at {offset:#x} changes length")
    return {"offset": f"{offset:#X}", "before": before.hex().upper(), "after": after.hex().upper(), "purpose": purpose}


def storage(new: bytes, size: int) -> bytes:
    if len(new) > size:
        raise SystemExit("tip does not fit the dead storage")
    return new + b"\0" * (size - len(new))


def vv1() -> dict:
    src = VV1.read_bytes()
    demo = src[VV1_DEMO_STRINGS:VV1_DEMO_STRINGS + VV1_STORAGE]
    if not demo.startswith(b"In der Demoversion sind maximal 9 Bewohner m") or b"Demo version has a max population of 9!\0" not in demo:
        raise SystemExit("VV1 demo storage is not what the design says")
    patches = [
        patch(src, VV1_PICKER, b"\x6a\x1e", b"\x6a\x1f",
              "draw the loading-screen tip from 31 ids instead of 30 (0x4256B0: push 0x1e -> push 0x1f), "
              "so id 0x225 -- the new tip -- can come up; the picker is 0x207 + rand(n)"),
        patch(src, VV1_POINTS_PUSH, b"\x68\x25\x02\x00\x00", b"\x68\x7e\x02\x00\x00",
              "the one reader of string id 0x225 (\"points.\", 0x4346E7) asks for 0x27E instead, a free id, "
              "freeing 0x225 for the tip; the string itself is unchanged"),
        patch(src, VV1_POINTS_RECORD, le(0x225), le(0x27E),
              "renumber the \"points.\" string record (0x487244) from 0x225 to 0x27E to match its reader"),
        patch(src, VV1_DEMO_RECORD,
              le(0x259) + le(0x481274) + le(0x481240) + le(0x481214) + le(0x4811E0),
              le(0x225) + le(VV1_DEMO_STRINGS_VA) * 4,
              "repurpose the demo-version string record (0x48744C, id 0x259, unreferenced in the full game) as "
              "tip id 0x225, all four language pointers at its own storage"),
        patch(src, VV1_DEMO_STRINGS, demo, storage(TIP, VV1_STORAGE),
              "the new tip text, written over the demo record's own 92 bytes of German+English storage"),
    ]
    return {
        "id": "vv1_number_keys",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": "Numeric Keys: Zip Around the Island",
        "description": (
            "The number keys move the view to one of nine sections of the island, laid out like a numeric "
            "keypad (7 8 9 across the top, 4 5 6 in the middle, 1 2 3 along the bottom), gliding there the way "
            "The Lost Children and the later games do. Top-row digits and keypad digits both work; holding a key "
            "does not repeat; a glide keeps going even if the view is scrolled or a villager is dragged "
            "mid-glide -- press another number key to change course. Adds the loading-screen tip \"You can zip "
            "around the island with your numeric keys.\" Requires Enable Origins-Exclusive Features, whose "
            "companion loads this one."
        ),
        "output_tag": "Numeric Keys",
        "dependencies": ["vv1_enable_origins_exclusive_features"],
        "behavior_changes": [
            "Pressing 1-9 (top row or numeric keypad) glides the view to the matching ninth of the island, "
            "reaching the same corners the game's own map clicks are clamped to (x -205..885, y -5..1205).",
            "One more loading-screen tip can appear: \"You can zip around the island with your numeric keys.\"",
        ],
        "explicit_non_changes": [
            "No villager, save, or village-state field other than the scroll position is written.",
            "Ctrl+digit and Alt+digit are ignored; key auto-repeat is ignored; a digit typed before any village "
            "exists does nothing.",
            "The \"points.\" string is unchanged in wording; only its internal id moves (0x225 -> 0x27E).",
            "No executable space is claimed: every changed byte replaces bytes of the unreferenced demo-version "
            "string record or a single immediate.",
        ],
        "companion_files": [
            {
                "source": "assets/number_keys/VVFP VV1 Number Keys.dll",
                "destination": "VVFP VV1 Number Keys.dll",
                "sha256": hashlib.sha256(DLL.read_bytes()).hexdigest().upper(),
            }
        ],
        "patches": patches,
    }


def vv2() -> dict:
    src = VV2.read_bytes()
    demo = src[VV2_DEMO_STRINGS:VV2_DEMO_STRINGS + VV1_STORAGE]
    if not demo.startswith(b"In der Demoversion sind maximal 9 Bewohner m") or b"Demo version has a max population of 9!\0" not in demo:
        raise SystemExit("VV2 demo storage is not what the design says")
    record = src[VV2_TIP_RECORD_EN - 4:VV2_TIP_RECORD_EN + 8]
    if record != le(0x312) + le(0x4836F0) + le(0x483970):
        raise SystemExit("VV2 tip record 0x312 is not what the design says")
    patches = [
        patch(src, VV2_TIP_RECORD_EN, le(0x4836F0), le(VV2_DEMO_STRINGS_VA),
              "point tip 0x312's English text (0x498038) at the reworded copy; the German pointer is untouched"),
        patch(src, VV2_DEMO_STRINGS, demo, storage(TIP, VV1_STORAGE),
              "the reworded tip, written over the demo-version record's own 92 bytes of storage "
              "(id 0x35C, unreferenced in the full game)"),
    ]
    return {
        "id": "vv2_numeric_keys_tip_wording",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv2",
        "name": "Tip Wording: Numeric Keys",
        "description": (
            "Rewords the loading-screen tip \"You can zip around the island with your keypad.\" to "
            "\"You can zip around the island with your numeric keys.\", matching A New Home's new tip. "
            "The keys themselves already work in The Lost Children; nothing else changes."
        ),
        "output_tag": "Numeric Keys Tip",
        "behavior_changes": [
            "One loading-screen tip reads \"numeric keys\" instead of \"keypad\".",
        ],
        "explicit_non_changes": [
            "No code, save, or village-state byte changes; the German text is untouched.",
            "No executable space is claimed: the new text replaces the unreferenced demo-version strings.",
        ],
        "companion_files": [],
        "patches": patches,
    }


def main() -> None:
    for name, record in (("vv1_number_keys_feature.json", vv1()), ("vv2_numeric_keys_tip_feature.json", vv2())):
        out = ROOT / "data" / name
        out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
        print(out, hashlib.sha256(out.read_bytes()).hexdigest().upper())


if __name__ == "__main__":
    main()
