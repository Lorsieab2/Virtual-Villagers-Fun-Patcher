"""Generate data/vv1_restore_missing_island_events_feature.json.

Restore Missing Island Events (A New Home): the two island events the
original game has complete code and text for but never runs.

Why they never run, read from the stock executable:

* A Mighty Storm is island case 1.  The island-event chooser (0x428470)
  rolls the case at 0x4284DB (rand(15): the trigger's 0x41D110 is
  `xor eax, eax; ret`, so only the type-2 call 0x423A06, cases 0..14, runs),
  looks up the case's condition class in the byte table at 0x4286A0 and
  jumps through the six-entry table at 0x428688 (0x4284F3).  Case 1's class
  byte (0x4286A1) is 5, and entry 5 (0x42869C) is 0x4284D6: the re-roll.
  No other case has class 5.
* The Furry Food is villager-encounter variant 5.  The encounter chooser
  (0x418920) rolls rand(16) at 0x418932, looks up the class in the byte
  table at 0x4189A4 and jumps through the five-entry table at 0x418990
  (0x418948).  Variant 5's class byte (0x4189A9) is 4, and entry 4
  (0x4189A0) is 0x418930: the re-roll.  No other variant has class 4.

The fix re-aims only those two dead table entries at a condition the
events' own text calls for -- stored food to wash away / go moldy
(world+0xA2EC > 0) -- and otherwise lets the stock code run: with food the
case is accepted exactly as an always-possible case is (0x428671 runs the
island case, 0x41895D accepts the variant), without food the stock re-roll
runs.  So each event gets the same 1-in-15 / 1-in-16 first roll as every
other event whose condition holds.

The condition is one shared helper and two four-instruction stubs in the
.text tail's free zero runs (0x4568E1 and 0x456670); every write is guarded
by its exact stock bytes.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
OUT = ROOT / "data" / "vv1_restore_missing_island_events_feature.json"
BASE = 0x400000                  # .text is file-aligned: file offset = VA - BASE

WORLD_GLOBAL = 0x48AEDC          # the village-state singleton (0x41D500)
FOOD = 0xA2EC                    # world+0xA2EC: stored food

ISLAND_ENTRY = 0x42869C          # 0x428688 + 5*4: class 5 (case 1 only)
ISLAND_REROLL = 0x4284D6
ISLAND_RUN = 0x428671            # push magnitude, push case, call 0x427CA0
ENCOUNTER_ENTRY = 0x4189A0       # 0x418990 + 4*4: class 4 (variant 5 only)
ENCOUNTER_REROLL = 0x418930
ENCOUNTER_ACCEPT = 0x41895D      # mov eax, edi; pop; pop; pop; ret

HELPER = 0x4568E1                # free run 0x4568E1..0x4568FF (31 bytes)
ENCOUNTER_STUB = 0x456670        # free run 0x456670..0x45667F (16 bytes)


def _rel(next_va: int, target: int) -> bytes:
    return struct.pack("<i", target - next_va)


def _stub(at: int, reroll: int, accept: int) -> bytes:
    return (
        b"\xE8" + _rel(at + 5, HELPER)              # call food test
        + b"\x0F\x8E" + _rel(at + 11, reroll)       # jle: no stored food -> stock re-roll
        + b"\xE9" + _rel(at + 16, accept)           # jmp: food -> accepted as stock
    )


def cave_bytes() -> tuple[bytes, int, bytes]:
    helper = (
        bytes.fromhex("8B0D") + struct.pack("<I", WORLD_GLOBAL)          # mov ecx, [world]
        + bytes.fromhex("83B9") + struct.pack("<I", FOOD) + b"\x00"      # cmp dword [ecx+0xA2EC], 0
        + b"\xC3"                                                        # ret
    )
    island_stub = HELPER + len(helper)
    tail = helper + _stub(island_stub, ISLAND_REROLL, ISLAND_RUN)
    return tail, island_stub, _stub(ENCOUNTER_STUB, ENCOUNTER_REROLL, ENCOUNTER_ACCEPT)


def build() -> dict:
    data = STOCK.read_bytes()

    def at(va: int, n: int) -> bytes:
        return data[va - BASE:va - BASE + n]

    # The class tables: case 1 / variant 5 are the only users of the entries.
    island_classes = at(0x4286A0, 15)
    encounter_classes = at(0x4189A4, 16)
    if [i for i, c in enumerate(island_classes) if c == 5] != [1]:
        raise SystemExit("island class 5 is not case 1's alone")
    if [i for i, c in enumerate(encounter_classes) if c == 4] != [5]:
        raise SystemExit("encounter class 4 is not variant 5's alone")
    if at(ISLAND_ENTRY, 4) != struct.pack("<I", ISLAND_REROLL):
        raise SystemExit("island table entry 5 is not the stock re-roll")
    if at(ENCOUNTER_ENTRY, 4) != struct.pack("<I", ENCOUNTER_REROLL):
        raise SystemExit("encounter table entry 4 is not the stock re-roll")

    tail, island_stub, encounter = cave_bytes()
    if len(tail) > 0x4568FF - HELPER or len(encounter) > 0x456680 - ENCOUNTER_STUB:
        raise SystemExit("cave does not fit its free run")
    for va, code in ((HELPER, tail), (ENCOUNTER_STUB, encounter)):
        if at(va, len(code)) != bytes(len(code)):
            raise SystemExit(f"cave 0x{va:X} is not zero in the stock executable")

    def patch(va: int, after: bytes, purpose: str) -> dict:
        return {
            "offset": f"0x{va - BASE:X}",
            "before": at(va, len(after)).hex().upper(),
            "after": after.hex().upper(),
            "purpose": purpose,
        }

    return {
        "id": "vv1_restore_missing_island_events",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv1",
        "name": "Restore Missing Island Events",
        "description": (
            "A New Home has two island events whose story and effects are complete in the game but "
            "which the original game never picks: A Mighty Storm (a typhoon washes away all of the "
            "stored food) and The Furry Food (the stored food goes moldy: remove the moldy pieces and "
            "some villagers get stomach trouble, or throw out all the food). This adds both to the "
            "game's normal random island events, with the same chance as any other event, whenever "
            "the village has stored food to lose. Their text and effects are the game's own. "
            "**Needs no other patch.**"
        ),
        "output_tag": "Missing Island Events",
        "behavior_changes": [
            "A Mighty Storm (island event 1) can be chosen by the game's own island-event roll when "
            "the village has stored food; it then runs exactly as the game wrote it (all stored food "
            "is lost).",
            "The Furry Food (villager encounter 5) can be chosen by the game's own encounter roll when "
            "the village has stored food; both of its choices run exactly as the game wrote them.",
            "Each is offered with the same first-roll chance as every other event whose condition "
            "holds (1 in 15 among the island events, 1 in 16 among the encounters); with no stored "
            "food the game rolls again, as it does for any event that cannot happen.",
        ],
        "explicit_non_changes": [
            "How often island events happen, the other events, their odds and conditions, and the "
            "events' own text and effects are unchanged.",
            "No save data changes.",
        ],
        "evidence_status": "static exact-build evidence, emulated choosers and handlers, and live in-game confirmation (both events, both Furry Food choices, with and without food)",
        "companion_files": [],
        "patches": [
            patch(ISLAND_ENTRY, struct.pack("<I", island_stub),
                  "island condition-class table entry 5 (A Mighty Storm, case 1, its only user): the "
                  "stock re-roll 0x4284D6 -> the stored-food test at 0x4568EF"),
            patch(ENCOUNTER_ENTRY, struct.pack("<I", ENCOUNTER_STUB),
                  "encounter condition-class table entry 4 (The Furry Food, variant 5, its only user): "
                  "the stock re-roll 0x418930 -> the stored-food test at 0x456670"),
            patch(HELPER, tail,
                  "shared test 0x4568E1 (stored food world+0xA2EC compared with 0) and A Mighty Storm's "
                  "stub 0x4568EF: no food -> stock re-roll 0x4284D6, food -> stock case run 0x428671"),
            patch(ENCOUNTER_STUB, encounter,
                  "The Furry Food's stub 0x456670: no food -> stock re-roll 0x418930, food -> stock "
                  "variant accept 0x41895D"),
        ],
    }


def main() -> None:
    OUT.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
