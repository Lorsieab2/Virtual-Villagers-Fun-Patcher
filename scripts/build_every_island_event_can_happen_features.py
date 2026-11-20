"""Generate data/vv{1,2,3,5}_every_island_event_can_happen_feature.json: "Every Island Event Can Happen".

The owner's decisions (2026-11-17, final; docs/every-island-event-can-happen-requirements.txt):
  1. The ONLY requirements dropped are the technology-level gates: every event that needs a technology level can
     happen at any level, everything researched included.
  2. Every event that raises a technology raises it by 1, up to that technology's top level (3 in all five games),
     instead of setting it to a number.  At the top level the event still happens and shows its own text; the level
     stays where it is.
  3. Everything else stays stock: the timer, the family weights and re-rolls, every villager, puzzle, building, food,
     grave and room requirement, the rescue rule and the first-event rules.  VV1's A Plague of Locusts (Farming 2: its
     crops) and VV3's Ghostly Dreams (Nature 1 / Magic 1) keep their technology needs by the owner's word.

What the stock executables do (research/stock-executables; .text raw offset == VA - 0x400000 in all four games):

  A NEW HOME (VV1).  Encounter chooser 0x418920: rand(16), class byte table 0x4189A4, handlers 0x418990.
    The Trapped Whale (variant 0, class 0, 0x41894F): cmp [world+0xA2BC], ebx(3) / jge re-roll at 0x41895B -- Spirituality
      below 3.  Its "Help free the whale" (0x4193EE) adds 1 only while below 3: already +1 up to 3.
    The Visitor (variant 4, class 2, 0x418963): cmp [world+0xA2D4], ebx(3) / jge re-roll at 0x41896F -- Medicine below 3.
      "Allow him to gather samples" (0x419815): already +1 up to 3.
    Both jge become nops.  Kept: A Plague of Locusts' Farming 2 (0x42861D) by the owner's word.
  THE LOST CHILDREN (VV2).  Two-choice chooser 0x41F570: rand(22), up to 10 draws, condition table 0x41F6C8, ebp=2.
    The Ancient Gold Coin (case 0): cmp [world+0x2EA74], ebp / setl bl at 0x41F5C5 -- Culture below 2.
    The Spyglass (case 18): cmp [world+0x2EA94], ebp / setl bl at 0x41F659 -- Exploration below 2.
    Both setl bl become mov bl, 1.
    "Use it to adorn clothing" (0x42051E): Culture + 1 only while below 2 -> cmp eax, 2 becomes cmp eax, 3.
    "Keep it" (0x421E7D): mov [world+0x2EA94], 2 -- SETS Exploration to 2, lowering a level-3 village.  The
      result's tail 0x421E74..0x421E8E becomes: mov ecx, world; cmp [ecx+0x2EA94], 3; adc [ecx+0x2EA94], 0 (the
      carry is set only below 3, so +1 up to 3); jmp 0x422256, the resolve's own shared exit (pop edi, esi, ebp,
      ebx; add esp, 0x2C2C; ret -- exactly the pops and return the stock tail made).
  THE SECRET CITY (VV3).  Conditions are the event objects' vtable [1]; levels are 0x426FC0(id) on 0x582618 (0
    Science, 1 Medicine, 2 Alchemy); the raise 0x426FD0 already stops at 3.
    The Bitter Brown Beans (taste or dye) and The Ancient Tablet (laundry or decoration), shared condition 0x4157E0:
      Science below 2.  Its level test 0x415800..0x415816 is shared: No Safeguards for Island Events rewrites
      0x415800..0x41580B at run time, so it may not be touched (0x41580C..0x415816 keeps the stock bytes: these
      events make no villager, so no record guard sits there since 536d34f42).  Instead the picker's branch 0x4157FB
      (jne 0x415800; xor al, al; ret) becomes jne +1; ret (eax is 0 there, so al is 0 as before); jmp 0x415817, and
      the alignment nops 0x415817 become xor eax, eax; jmp 0x41580C: the level read is skipped and level 0 goes into
      the same stock test.
    The Bitter Brown Beans (brew or fertilizer) 0x4159B0: cmp eax, 1 / setg at 0x4159DC -- Science 2 or more.
    The Ancient Tablet (research or display) 0x415C40: cmp eax, 3 / jl at 0x415C69 -- Alchemy below 3; cmp eax, 2 /
      setge at 0x415C7F -- Science 2 or more.  "Focus research on tablet" (0x415D30 -> 0x426FD0): +1 up to 3.
    The Medical Emergency 0x4171D0: cmp eax, 2 / setge at 0x417215 -- Medicine 2 or more.
    Each compare's immediate becomes -128 (">= / >" always true) or 127 ("<" always true): the instruction and its
    length stay, and the setcc/jcc No Safeguards rewrites right after it (0x4159DF, 0x415C82, 0x417218) is not
    touched, so both patches apply together in either order.
    Kept by the owner's word: The Ghostly Dreams' Nature 1 / Magic 1 (0x415517, 0x415657).
  THE TREE OF LIFE (VV4): no event condition reads a technology (the only getter call in the event code, 0x415303,
    is in a result: Food Mastery + 1 while below 3), and every raise (0x415314, 0x41591D,
    0x416DB2, 0x416DBF) goes through 0x41E1D0, which stops at 3.  Nothing to change, so there is no row.
  NEW BELIEVERS (VV5).  Levels are 0x423600(id) on 0x51D5CC (0 Science, 4 Food Mastery); the raise 0x423610 stops at 3.
    You're Doing It Wrong! 0x415F60: cmp eax, 2 / jge at 0x415FD8 -- Science below 2.  "Teach them" (0x416081)
      raises Science only while below 2: cmp eax, 2 at 0x41608D becomes cmp eax, 3.
    The Advanced Artifacts 0x416430: cmp eax, 2 / jge at 0x41643F -- Science 2 or more (No Safeguards rewrites the
      jge at 0x416442); cmp eax, 3 / setl at 0x416496 -- Science below 3.  Its raise (0x416518): +1 up to 3.
    The Migrating Fruit Bats 0x4166F0: cmp eax, 2 / setl at 0x416733 -- Food Mastery below 2.  Its raise
      (0x416778): +1 up to 3.

Every write is guarded by its stock bytes; nothing is written to a save; no companion.
tests/test_every_island_event_can_happen.py renders each row in the three patch modes and runs the changed
conditions and raises in an emulator at every level.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x400000
STOCK = {
    1: "Virtual Villagers - A New Home.exe",
    2: "Virtual Villagers - The Lost Children.exe",
    3: "Virtual Villagers - The Secret City.exe",
    5: "Virtual Villagers - New Believers.exe",
}
GAMES = tuple(STOCK)
NAME = "Every Island Event Can Happen"
TAG = "Every Island Event"
NEEDS = "**Needs no other patch.**"


def feature_id(game: int) -> str:
    return f"vv{game}_every_island_event_can_happen"


def out_path(game: int) -> Path:
    return ROOT / "data" / f"{feature_id(game)}_feature.json"


def _rel(next_va: int, target: int) -> bytes:
    return struct.pack("<i", target - next_va)


def _vv2_spyglass() -> bytes:
    """0x421E74..0x421E8E: mov ecx, [esi+0x50AC]; cmp [ecx+0x2EA94], 3; adc [ecx+0x2EA94], 0; jmp 0x422256; nops."""
    code = (bytes.fromhex("8B8EAC500000")                 # mov ecx, [esi+0x50AC]  (the world, as stock)
            + bytes.fromhex("83B994EA020003")             # cmp dword [ecx+0x2EA94], 3
            + bytes.fromhex("839194EA020000"))            # adc dword [ecx+0x2EA94], 0
    jmp_at = 0x421E74 + len(code)
    code += b"\xE9" + _rel(jmp_at + 5, 0x422256)          # the resolve's shared exit
    return code + b"\x90" * (27 - len(code))


# game -> [(va, stock bytes, new bytes, purpose)]
SITES: dict[int, list[tuple[int, bytes, bytes, str]]] = {
    1: [
        (0x41895B, bytes.fromhex("7DD3"), bytes.fromhex("9090"),
         "The Trapped Whale (encounter variant 0): the re-roll when Spirituality (world+0xA2BC) is 3 or more "
         "(jge 0x418930) -> nops; \"Help free the whale\" still adds 1 only below 3 (0x4193F4)"),
        (0x41896F, bytes.fromhex("7DBF"), bytes.fromhex("9090"),
         "The Visitor (encounter variant 4): the re-roll when Medicine (world+0xA2D4) is 3 or more (jge 0x418930) "
         "-> nops; \"Allow him to gather samples\" still adds 1 only below 3 (0x41981B)"),
    ],
    2: [
        (0x41F5C5, bytes.fromhex("0F9CC3"), bytes.fromhex("B30190"),
         "The Ancient Gold Coin (two-choice case 0): Culture (world+0x2EA74) below 2 (setl bl) -> mov bl, 1"),
        (0x41F659, bytes.fromhex("0F9CC3"), bytes.fromhex("B30190"),
         "The Spyglass (two-choice case 18): Exploration (world+0x2EA94) below 2 (setl bl) -> mov bl, 1"),
        (0x420524, bytes.fromhex("83F802"), bytes.fromhex("83F803"),
         "The Ancient Gold Coin, \"Use it to adorn clothing\": Culture + 1 only below 2 -> only below 3 (the top)"),
        (0x421E74, bytes.fromhex("8B8EAC5000005F5E5DC78194EA0200020000005B81C42C2C0000C3"), _vv2_spyglass(),
         "The Spyglass, \"Keep it\": Exploration = 2 (mov at 0x421E7D) -> Exploration + 1 below 3 (cmp 3 / adc 0), "
         "then the resolve's shared exit 0x422256 (the same pops and return)"),
    ],
    3: [
        (0x4157FB, bytes.fromhex("750332C0C3"), bytes.fromhex("7501C3EB17"),
         "The Bitter Brown Beans (taste or dye) / The Ancient Tablet (laundry or decoration), condition 0x4157E0: "
         "no villager -> ret (eax 0, as stock); a villager -> 0x415817 instead of the Science read at 0x415800"),
        (0x415817, bytes.fromhex("90909090"), bytes.fromhex("33C0EBF1"),
         "the same condition: alignment nops -> xor eax, eax; jmp 0x41580C -- level 0 into the shared level test "
         "(the stock test there, which no record guard touches): Science below 2 dropped"),
        (0x4159DC, bytes.fromhex("83F801"), bytes.fromhex("83F880"),
         "The Bitter Brown Beans (brew or fertilizer), condition 0x4159B0: Science > 1 (cmp eax, 1 / setg) -> "
         "cmp eax, -128: any level"),
        (0x415C69, bytes.fromhex("83F803"), bytes.fromhex("83F87F"),
         "The Ancient Tablet (research or display), condition 0x415C40: Alchemy below 3 (cmp eax, 3 / jl) -> "
         "cmp eax, 127: any level (\"Focus research on tablet\" still adds 1 only below 3, 0x426FDD)"),
        (0x415C7F, bytes.fromhex("83F802"), bytes.fromhex("83F880"),
         "The Ancient Tablet (research or display): Science 2 or more (cmp eax, 2 / setge) -> cmp eax, -128"),
        (0x417215, bytes.fromhex("83F802"), bytes.fromhex("83F880"),
         "The Medical Emergency, condition 0x4171D0: Medicine 2 or more (cmp eax, 2 / setge) -> cmp eax, -128"),
    ],
    5: [
        (0x415FD8, bytes.fromhex("83F802"), bytes.fromhex("83F87F"),
         "You're Doing It Wrong!, condition 0x415F60: Science below 2 (cmp eax, 2 / jge no) -> cmp eax, 127"),
        (0x41608D, bytes.fromhex("83F802"), bytes.fromhex("83F803"),
         "You're Doing It Wrong!, \"Teach them\": Science + 1 only below 2 -> only below 3 (the top; 0x423610 "
         "stops at 3 too)"),
        (0x41643F, bytes.fromhex("83F802"), bytes.fromhex("83F880"),
         "The Advanced Artifacts, condition 0x416430: Science 2 or more (cmp eax, 2 / jge) -> cmp eax, -128"),
        (0x416496, bytes.fromhex("83F803"), bytes.fromhex("83F87F"),
         "The Advanced Artifacts: Science below 3 (cmp eax, 3 / setl) -> cmp eax, 127 (its raise 0x423610 "
         "stops at 3)"),
        (0x416733, bytes.fromhex("83F802"), bytes.fromhex("83F87F"),
         "The Migrating Fruit Bats, condition 0x4166F0: Food Mastery below 2 (cmp eax, 2 / setl) -> cmp eax, 127 "
         "(its raise 0x423610 stops at 3)"),
    ],
}

DESCRIPTIONS = {
    1: ("The Trapped Whale (it needed Spirituality below level 3) and The Visitor (Medicine below level 3) can now "
        "happen at any technology level, even with everything researched. \"Help free the whale\" and \"Allow him to "
        "gather samples\" still raise that technology by 1 level, up to 3; at level 3 the event still happens, shows "
        "its own text, and the level stays at 3."),
    2: ("The Ancient Gold Coin (it needed Culture below level 2) and The Spyglass (Exploration below level 2) can "
        "now happen at any technology level, even with everything researched. \"Use it to adorn clothing\" raises "
        "Culture by 1 level up to 3 (it stopped at 2), and \"Keep it\" raises Exploration by 1 level up to 3 instead "
        "of setting it to 2 (which lowered a village at level 3); at level 3 the event still happens, shows its own "
        "text, and the level stays at 3."),
    3: ("The Bitter Brown Beans (both versions: Science below level 2, or 2 or more), The Ancient Tablet (both "
        "versions: Science below 2; Science 2 or more and Alchemy below 3) and The Medical Emergency (Medicine 2 or "
        "more) can now happen at any technology level, even with everything researched. \"Focus research on "
        "tablet\" still raises Alchemy by 1 level, up to 3; at level 3 the event still happens, shows its own text, "
        "and the level stays at 3. The Ghostly Dreams keep their Nature / Magic need."),
    5: ("You're Doing It Wrong! (it needed Science below level 2), The Advanced Artifacts (Science exactly 2) and "
        "The Migrating Fruit Bats (Food Mastery below level 2) can now happen at any technology level, even with "
        "everything researched. \"Teach them\" raises Science by 1 level up to 3 (it stopped at 2); the other two "
        "raise theirs by 1 level up to 3 as before; at level 3 the event still happens, shows its own text, and the "
        "level stays at 3."),
}
COMMON = (" Every other requirement (the villagers an event needs, puzzles, buildings, food, graves, room), how often "
          "events come and how one is chosen stay as in the normal game. ")

BEHAVIOR = {
    1: ["The Trapped Whale can be chosen by the encounter roll at every Spirituality level, 3 included.",
        "The Visitor can be chosen by the encounter roll at every Medicine level, 3 included.",
        "Their raises are the game's own: +1 level, never past 3."],
    2: ["The Ancient Gold Coin can be chosen by the two-choice roll at every Culture level.",
        "The Spyglass can be chosen by the two-choice roll at every Exploration level.",
        "\"Use it to adorn clothing\": Culture + 1 level, up to 3 (was: only below 2).",
        "\"Keep it\": Exploration + 1 level, up to 3 (was: Exploration set to 2)."],
    3: ["The Bitter Brown Beans (taste or dye) and The Ancient Tablet (laundry or decoration) qualify at every "
        "Science level; the always-applied record check of their shared condition still runs.",
        "The Bitter Brown Beans (brew or fertilizer) qualifies at every Science level.",
        "The Ancient Tablet (research or display) qualifies at every Science and Alchemy level.",
        "The Medical Emergency qualifies at every Medicine level.",
        "\"Focus research on tablet\" is the game's own raise: +1 level, never past 3."],
    5: ["You're Doing It Wrong! qualifies at every Science level; \"Teach them\": Science + 1 level, up to 3 (was: only "
        "below 2).",
        "The Advanced Artifacts qualifies at every Science level; its raise is the game's own (+1, never past 3).",
        "The Migrating Fruit Bats qualifies at every Food Mastery level; its raise is the game's own (+1, never past "
        "3)."],
}
NON_CHANGES = {
    1: ["A Plague of Locusts still needs Farming level 2 (its crops)."],
    2: [],
    3: ["The Ghostly Dreams still need Nature level 1 / Magic level 1."],
    5: [],
}


def build(game: int) -> dict:
    data = (ROOT / "research" / "stock-executables" / STOCK[game]).read_bytes()
    patches = []
    for va, before, after, purpose in SITES[game]:
        if len(before) != len(after):
            raise SystemExit(f"vv{game} 0x{va:X}: length changed")
        if data[va - BASE:va - BASE + len(before)] != before:
            raise SystemExit(f"vv{game} 0x{va:X}: not the stock bytes")
        patches.append({"offset": f"0x{va - BASE:X}", "before": before.hex().upper(),
                        "after": after.hex().upper(), "purpose": purpose})
    return {
        "id": feature_id(game),
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": DESCRIPTIONS[game] + COMMON + NEEDS,
        "output_tag": TAG,
        "behavior_changes": BEHAVIOR[game],
        "explicit_non_changes": [
            "Only technology-level requirements are dropped; every other requirement of every event is the game's "
            "own.",
            "The time between island events, the family weights, the re-rolls and every event's text are unchanged.",
            *NON_CHANGES[game],
            "No save data changes.",
        ],
        "evidence_status": ("static exact-build evidence (every write guarded by its stock bytes) and emulated "
                            "conditions and raises at every technology level in all three patch modes; not yet "
                            "seen in a running game"),
        "companion_files": [],
        "patches": patches,
    }


def main() -> None:
    for game in GAMES:
        out_path(game).write_text(json.dumps(build(game), indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {out_path(game).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
