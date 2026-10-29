"""Generate the numeric-keys feature manifests.

Two rows come out of this:

  data/vv1_number_keys_feature.json
    A New Home: the companion DLL that makes the number keys glide the view
      exactly as The Lost Children's do, plus a new random tip announcing it.

  data/vv2_numeric_keys_tip_feature.json
      The Lost Children: the existing tip's wording changed from "keypad" to
      "numeric keys", for parity with A New Home.

Every `before` is read from the stock executable rather than typed in, and
each site is asserted to hold exactly what the design says before a manifest
is written, so a wrong address fails here instead of at apply time.

THE VV1 TIP.  The game picks the tip it shows when the mask is clicked as
string id 0x207 + rand(30) at 0x4256B0, inside the village screen's mouse
handler 0x424EF0 (vtable 0x4598B0 +4; the mask test is 0x425661..0x42567F).
That is A New Home's only random-tip picker: 0x4256BA is the code's only use
of 0x207, and the loading screen (built by 0x41F650) shows only "Loading..."
(string 79).  The game resolves ids through a first-match linear
scan of 629 twenty-byte {id, en, de, fr, es} records at 0x487208 (0x433880,
ids below 0x280 only).  Ids 0x205/0x206 and 0x225/0x226 are all taken, so the
range cannot simply grow.  What is free: the demo-version string record
(id 0x259, "Demo version has a max population of 9!", no code reference in
the full game) with 92 contiguous bytes of its own storage, and the ids
0x27D/0x27E.  So: "points." (id 0x225, one reference at 0x4346E7) is
renumbered to 0x27E, the demo record becomes id 0x225 with all four language
pointers at its own storage, the new tip is written over that storage, and
the picker draws from 31.  No executable space is claimed anywhere.

THE VV2 TIP.  0x312 is random tip 45 of 50 (0x2E6 + 44).  The loading
screen (0x429530) draws only 0x2E6 + rand(30) (0x42972A), so this tip comes
only from the mask click: 0x2E6 + rand(50) in the village screen's mouse
handler 0x4308D0 (0x431394).  Record 0x312 keeps its id; only its English pointer moves to
the demo record's storage (id 0x35C, also unreferenced), where the longer
wording fits with room to spare.  The German pointer is untouched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from origins_base_text import ORIGINS_BASE_SENTENCE  # noqa: E402

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
              "draw the tip shown when the mask is clicked from 31 ids instead of 30 (0x4256B0, in the village "
              "screen's mouse handler 0x424EF0: push 0x1e -> push 0x1f), "
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
            "The number keys glide the view to nine spots on the island, laid out like a numeric keypad "
            "(7 8 9 across the top, 4 5 6 in the middle, 1 2 3 along the bottom), exactly the way they do in "
            "The Lost Children: the same nine spots, the same glide (a tenth of the remaining distance each "
            "update), and the same controls -- another number key changes course, dragging the map pulls "
            "against the glide while the mouse button is held and releasing the button (or any click) ends it, "
            "and opening another screen ends it. The keys work on the village screen: the top-row digits, and "
            "the numeric keypad when Num Lock is on. "
            "Adds the tip \"You can zip around the island with your numeric keys.\" to the helpful tips "
            "shown at the bottom of the screen when you click the mask. "
            + ORIGINS_BASE_SENTENCE
            + " That base's companion loads this patch's DLL."
        ),
        "output_tag": "Numeric Keys",
        "dependencies": ["vv1_enable_origins_exclusive_features"],
        "behavior_changes": [
            "Typing 1-9 on the village screen (the game's own text-character handler 0x41FDF0, detoured at "
            "0x41FE04 as The Lost Children's 0x429E70 does it) sets the glide target to The Lost Children's "
            "nine spots 1=(-150,1200), 2=(300,1200), 3=(850,1200), 4=(-150,500), 5=(300,570), 6=(850,500), "
            "7=(-150,0), 8=(300,0), 9=(850,0); another digit retargets from where the view is.",
            "The glide is The Lost Children's 0x42F814, run from the Origins village-update hook (0x423F89): "
            "while a target is set it zeroes the edge velocities, moves each axis a tenth of the remaining "
            "distance (truncated, no minimum step, no snap), clamps with A New Home's own clamp (an axis that "
            "hits it has its target zeroed, as in The Lost Children), and ends once both remaining distances "
            "divided by ten are zero.",
            "The map drag is untouched and moves the view against the glide while the button is held; the "
            "mouse-up branch (0x424F12), the screen buttons that leave the village view (0x4208CC, 0x420932, "
            "0x420998) and the screen constructor (0x422555) now also clear the glide, where The Lost Children "
            "clears it. These six sites are detoured at run time by the companion after their stock bytes are "
            "checked; if any differs, nothing is installed.",
            "Clicking the mask can show one more tip: \"You can zip around the island with your numeric keys.\"",
        ],
        "explicit_non_changes": [
            "The companion writes only the camera pair and the screen's edge velocity pair (+0x2D8/+0x2DC); "
            "the native held-record carry routine refreshes a carried villager after each glide step. No "
            "save-format change is made, and with no glide the edge scrolling and map drag are stock.",
            "Characters other than 1-9 reach the stock handler unchanged; a digit typed on another screen goes "
            "to that screen, as in The Lost Children.",
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
            "Rewords the tip \"You can zip around the island with your keypad.\", one of the helpful tips "
            "shown at the bottom of the screen when you click the mask, to \"You can zip around the island "
            "with your numeric keys.\", matching A New Home's new tip. "
            "The keys themselves already work in The Lost Children; nothing else changes."
        ),
        "output_tag": "Numeric Keys Tip",
        "behavior_changes": [
            "One of the tips shown when you click the mask reads \"numeric keys\" instead of \"keypad\".",
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
