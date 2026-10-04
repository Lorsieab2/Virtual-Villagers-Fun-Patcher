"""Generate data/vv2_restore_missing_island_events_feature.json.

Restore Missing Island Events (The Lost Children).

The single-result island events (family C) are chosen by 0x434570: it draws
the case with rand(28) at 0x434607 and checks it through the condition jump
table at 0x434868 (28 entries).  The target 0x434822 (`mov bl, 1`) accepts the
draw; 0x434824 leaves bl at 0 and the chooser draws again (up to 10 times,
then runs case 10).  Cases 4, 18, 20 and 26 are mapped to 0x434824, so the
original game never runs them:

* 18 The Mosquito Swarm (string 0x2C2), 20 The Dragonfly Migration (0x2AD)
  and 26 Science Awareness Day (0x2B7) have complete bodies in the case
  runner 0x433600 (jump table 0x4344F4).  The chooser's own switch still holds
  two stray labels, `cmp ebp, 0x2AD` / `cmp ebp, 0x2B7` -> accept
  (0x434617-0x434820): the STRING ids of The Dragonfly Migration and Science
  Awareness Day, written where their case numbers belonged, so the two events
  the developer meant to accept could never be drawn.  The Mosquito Swarm has
  no label at all.  Pointing the three table entries at the table's own
  accept target 0x434822 puts them in the stock roll with exactly the chance
  of every unconditional case (1 in 28 per draw).  Their bodies have no
  condition of their own; nothing links the Swarm and the Migration (no flag
  is written or read, and the Migration's text stands alone).

* Case 4 has no body (0x4344F4[4] is the runner's shared epilogue 0x4344ED)
  and no text.  It becomes the host of three no-choice events whose English
  text the game ships (string ids 698-700) but no code reads: The Tattered
  Diary, The Doctrine of Magicians, The Doctrine of Naturalists.  The owner
  (2026-10-04): lore only -- the popup, no game effect -- and rarer than a
  typical event.  Case 4 is drawn 1 time in 28 like any unconditional case
  and then rand(3) picks the page, so each page is a third as likely as a
  typical single-result event.

The case-4 body (48 bytes) is written over stock code that can never run:
the trigger's single-result branch for a positive "kind" (0x42F032-0x42F066).
The kind is edi = 0x426110(), whose whole body is `xor eax, eax; ret`, and
edi is not written again before `cmp edi, ebx` (ebx = 0) at 0x42F028, so the
`jle 0x42F067` at 0x42F030 is always taken.  No branch, call or pointer in
the image reaches 0x42F032-0x42F09D (tests/test_vv2_restore_missing_island_events.py
pins all of this).  The 5 bytes after the body are int3.

Every patch is guarded by its exact stock bytes.  Run from the repository
root:

    python scripts/build_vv2_restore_missing_island_events_feature.py
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
OUT = ROOT / "data" / "vv2_restore_missing_island_events_feature.json"

IMAGE_BASE = 0x400000
CONDITION_TABLE = 0x434868
RUNNER_TABLE = 0x4344F4
ACCEPT = 0x434822
REJECT = 0x434824
EPILOGUE = 0x4344ED
RAND = 0x4031A0
STRING_OF = 0x441680
SPRINTF = 0x4682BD
CAVE = 0x42F032
CAVE_ROOM = 0x42F067 - CAVE          # 53 bytes up to the jge at 0x42F067
PAGE_ROLL = CAVE + 2                 # the rand(3) call: Pick Island Event's page site
FIRST_PAGE = 0x2BA                   # 698 The Tattered Diary, 699 Magicians, 700 Naturalists

RESTORED = {18: "The Mosquito Swarm", 20: "The Dragonfly Migration", 26: "Science Awareness Day"}
PAGES = ("The Tattered Diary", "The Doctrine of Magicians", "The Doctrine of Naturalists")


def file_offset(va: int) -> int:
    # .text is mapped 1:1 (raw 0x1000 at RVA 0x1000).
    return va - IMAGE_BASE


def rel32(at: int, target: int) -> bytes:
    return struct.pack("<i", target - (at + 5))


def case4_body() -> bytes:
    code = bytearray()

    def here() -> int:
        return CAVE + len(code)

    code += b"\x6A\x03"                                       # push 3
    code += b"\xE8" + rel32(here(), RAND)                     # call rand  -> page 0..2
    code += b"\x83\xC4\x04"                                   # add esp, 4
    code += b"\x05" + struct.pack("<I", FIRST_PAGE)           # add eax, 698
    code += b"\x8B\x8D\xAC\x50\x00\x00"                       # mov ecx, [ebp+0x50AC] (strings)
    code += b"\x50"                                           # push eax
    code += b"\xE8" + rel32(here(), STRING_OF)                # call 0x441680 (text of id)
    code += b"\x50"                                           # push eax
    code += b"\x8D\x8D\x7F\x27\x00\x00"                       # lea ecx, [ebp+0x277F] (popup text)
    code += b"\x51"                                           # push ecx
    code += b"\xE8" + rel32(here(), SPRINTF)                  # call 0x4682BD (copy, as every case)
    code += b"\x83\xC4\x08"                                   # add esp, 8
    code += b"\xE9" + rel32(here(), EPILOGUE)                 # jmp 0x4344ED (pop edi..ebp; ret 8)
    return bytes(code)


def main() -> None:
    data = STOCK.read_bytes()

    def read(va: int, n: int) -> bytes:
        return data[file_offset(va):file_offset(va) + n]

    def u32(va: int) -> int:
        return struct.unpack("<I", read(va, 4))[0]

    patches = []
    for case, title in RESTORED.items():
        va = CONDITION_TABLE + 4 * case
        if u32(va) != REJECT:
            raise SystemExit(f"condition table [{case}] is not the stock reject target")
        patches.append({
            "offset": f"0x{file_offset(va):X}",
            "before": read(va, 4).hex().upper(),
            "after": struct.pack("<I", ACCEPT).hex().upper(),
            "purpose": f"{title} (single-result case {case}): the chooser's condition table entry "
                       f"0x{va:X} now accepts the draw (0x{ACCEPT:X}, as every unconditional case) "
                       f"instead of always rejecting it (0x{REJECT:X})",
        })
    va = CONDITION_TABLE + 4 * 4
    if u32(va) != REJECT:
        raise SystemExit("condition table [4] is not the stock reject target")
    patches.append({
        "offset": f"0x{file_offset(va):X}",
        "before": read(va, 4).hex().upper(),
        "after": struct.pack("<I", ACCEPT).hex().upper(),
        "purpose": f"case 4 (the three lore pages): condition table entry 0x{va:X} accepts the "
                   f"draw (0x{ACCEPT:X}) instead of always rejecting it",
    })
    va = RUNNER_TABLE + 4 * 4
    if u32(va) != EPILOGUE:
        raise SystemExit("runner table [4] is not the stock epilogue")
    patches.append({
        "offset": f"0x{file_offset(va):X}",
        "before": read(va, 4).hex().upper(),
        "after": struct.pack("<I", CAVE).hex().upper(),
        "purpose": f"case 4: the case runner's jump table entry 0x{va:X} now runs the lore-page "
                   f"body at 0x{CAVE:X} instead of going straight to the epilogue 0x{EPILOGUE:X}",
    })
    body = case4_body()
    if len(body) > CAVE_ROOM:
        raise SystemExit(f"case-4 body is {len(body)} bytes; only {CAVE_ROOM} are dead")
    # The dead branch: 0x426110 is `xor eax, eax; ret`, so `jle 0x42F067` is always taken.
    if read(0x426110, 3) != bytes.fromhex("33C0C3"):
        raise SystemExit("0x426110 is no longer `xor eax, eax; ret`")
    if read(0x42F028, 10) != bytes.fromhex("3BFB898DE0EA02007E35"):
        raise SystemExit("0x42F028 is not `cmp edi, ebx; mov [ebp+0x2EAE0], ecx; jle 0x42F067`")
    after = body + b"\xCC" * (CAVE_ROOM - len(body))
    patches.append({
        "offset": f"0x{file_offset(CAVE):X}",
        "before": read(CAVE, CAVE_ROOM).hex().upper(),
        "after": after.hex().upper(),
        "purpose": f"case 4 body, over the trigger's never-taken positive-kind branch "
                   f"(0x{CAVE:X}-0x{CAVE + CAVE_ROOM - 1:X}; 0x426110 always returns 0): rand(3) at "
                   f"0x{PAGE_ROLL:X} picks string 698, 699 or 700 (The Tattered Diary, The Doctrine "
                   f"of Magicians, The Doctrine of Naturalists), copied into the popup text exactly as "
                   f"every other case does; nothing else changes; {CAVE_ROOM - len(body)} int3 bytes "
                   f"follow",
    })

    manifest = {
        "id": "vv2_restore_missing_island_events",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv2",
        "name": "Restore Missing Island Events",
        "description": (
            "Lets the island events the original game contains but never runs happen. "
            "The Mosquito Swarm (some villagers fall ill and the adults take refuge in the water), "
            "The Dragonfly Migration (every villager is restored to full health and cured) and "
            "Science Awareness Day (the children gain research skill) join the game's own random "
            "island-event roll with the same chance as a typical event. Three events whose text "
            "the game ships but never shows are added as rarer no-choice events, each a third as "
            "likely as a typical event: The Tattered Diary, The Doctrine of Magicians and The "
            "Doctrine of Naturalists, pages of Isola's lore a villager finds; they change nothing "
            "else. **Needs no other patch.** With Story / Cheat Upgrades, Pick Island Event also "
            "offers the three new events."
        ),
        "output_tag": "Missing Island Events",
        "behavior_changes": [
            "The single-result island-event chooser (0x434570) accepts cases 18, 20 and 26 like every "
            "unconditional case: each is drawn 1 time in 28, as The Heat Wave or The West Wind are.",
            "The Mosquito Swarm runs the game's own case 18: each living villager has a 20% chance "
            "to fall sick, and every adult who is not pregnant stops what they are doing and goes "
            "to the pond (\"Enjoying the pond\", the game's swim).",
            "The Dragonfly Migration runs the game's own case 20: every living villager's health "
            "becomes 100 and their sickness is cured.",
            "Science Awareness Day runs the game's own case 26: every living child gains 3 to 7 "
            "Research skill points (capped at 100).",
            "Case 4 (no body or text in the original game) is drawn 1 time in 28 and shows one of "
            "The Tattered Diary, The Doctrine of Magicians or The Doctrine of Naturalists (rand(3)), "
            "the game's own English texts 698-700, in the ordinary single-result popup.",
        ],
        "explicit_non_changes": [
            "The lore pages change nothing but the popup: no food, tech, villager, skill or save value.",
            "The Mosquito Swarm and The Dragonfly Migration stay independent, as in the game's own "
            "code: neither sets or reads anything the other uses.",
            "Every other island event, the family weights, the 10-draw retry, the event timer and the "
            "Island Events Seen counter are the base game's own.",
            "No executable space is claimed: the lore-page body replaces stock code that can never "
            "run, and the five other edits are entries of the game's own jump tables.",
        ],
        "evidence_status": (
            "static exact-build evidence; emulation of the real chooser, runner and trigger code "
            "proving each event's odds and effects; and a live test (v1.35.58 test build, "
            "2026-10-04, every public VV2 patch): all six events picked through Pick Island Event and "
            "clicked through, each popup showing the game's own text, with the Swarm's sickness and "
            "pond, the Migration's heal and cure and Science Day's child Research read back from "
            "memory, and the three pages changing nothing but the Island Events Seen counter"
        ),
        "companion_files": [],
        "patches": patches,
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.name, len(patches), "patches; case-4 body", len(body), "bytes")


if __name__ == "__main__":
    main()
