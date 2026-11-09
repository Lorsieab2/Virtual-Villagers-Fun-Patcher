"""Generate data/vv5_hovel_memorial_actions_feature.json: "Memorial Actions Can Also Occur at the Heathen Hovel"
(New Believers; off by default and in Select All, on in Owner's Defaults).

THE OWNER (2026-11-08).  Only two actions may use the hovel: "Reflecting" and the everyday "Honoring the dead" --
no other action.  The hovel counts as a memorial only once all Heathens have converted, and from the first time
there are none left it stays one, even if Heathens appear again.  Once it is a memorial, those actions may choose
the hovel as their place: a random choice alongside their usual place, not always; the walk target is walkable
ground at the hovel.

THE MEMORIAL MOMENT: the game's own flag.  After a conversion (0x466982) and in the village update (0x4425ED) the
game asks whether The Last Heathen (project 25, CConvertLastHeathenPuzzle) is done (0x43AE80 on the project table
0x51E008: progress >= threshold); while it is not and no Heathen is left (0x471870 counts none), 0x437120 sends the
villagers "Fixing up the mud hut" (behaviour 0xD8, 0x459ED0), whose completion advances project 25 (0x46D487, the
only advance of it) and so solves it; from then on 0x4370E0 draws the hovel's flower cover.  Project progress is
saved with the village and never goes back (a new village, Start Over included, starts it at 0), so "project 25
done" is exactly "the first time no Heathens were left, and the hovel was covered" -- once and for good.  No sidecar
is needed.  (The moment is when the mud hut is fixed and the cover appears, a little after the last conversion.)

THE TWO ACTIONS.
  "Reflecting" is behaviour 29 (0x1D), routine 0x457E90 (say-event 0x4C5), registered at 0x46409E: five go-tos
  (0x4745A0 at 0x457EE2, 0x457F13, 0x457F6E, 0x457FC9, 0x458024) to random points of 1530..1803 by 1606..1805.
  No stock code starts behaviour 29 (no push of 0x1D reaches the starter 0x465580, no direct call or table
  entry but the registration; a 150,000-frame emulated village never started it): only the Custom Island Event's
  "Reflecting" does.  Its registration is re-aimed at a wrapper, so every start of it is covered.
  The everyday "Honoring the dead" is behaviour 17 (0x11), routine 0x4595B0 (say-event 0x4D1): one walk to area
  0x7A for the flowers (0x4744C0 at 0x4595FA, skipped when expecting) and three walks to the graves, area 0x7B
  (0x4744C0 at 0x459630, 0x45966D, 0x4596BA).  The game's everyday chooser 0x46B0F0 (from the adults' leisure
  pick 0x46F387, with food 8,000 or more: rand(100) > 70, rand(3) = 0, a grave exists (0x464E90), rand(100) < 50)
  starts it at 0x46B145.  The Day of Honor island event starts the same behaviour for everyone (0x414DDA ->
  0x470C60), and the Custom Island Event's "Honoring the dead [Day of Honor]" is that behaviour too; the owner
  excluded the Day of Honor one, so only the chooser's start at 0x46B145 can go to the hovel.  Behaviour 46
  ("Honoring the dead (another way)", 0x4567C0) is never started by the game either and is not changed.

HOW.  A wrapper decides once per action: the memorial (project 25 done) and rand(100) < 50.  On "yes" it starts the
action from its own call, whose return address marks the action's stack; the re-aimed walk calls inside the
routine look for that mark at a fixed depth ([esp+0x1C] for Reflecting's go-tos; [esp+0x2C] for Honoring's area
walks, through 0x465580 and the dispatcher 0x452BD0) and then walk to a random point in front of the hovel, with
the routine's own speed and flag.  Anything else walks exactly as stock.  Nothing is written to the save or to a
villager record.

THE HOVEL POINT: x = 2176 + rand(97), y = 1576 + rand(25) (world pixels, the feet's point: 2176..2272 by
1576..1600), the walkable ground just south of the hovel's rocks (lcmap.dat cells blocked at 2176..2279 by
1464..1559); every point's cell and its eight neighbours are walkable and joined to the village
(tests/test_vv5_hovel_memorial_actions.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
OUT = ROOT / "data" / "vv5_hovel_memorial_actions_feature.json"
KS = Ks(KS_ARCH_X86, KS_MODE_32)

ID = "vv5_hovel_memorial_actions"
NAME = "Memorial Actions Can Also Occur at the Heathen Hovel"

RAND = 0x403660
WALK_TO = 0x4745A0                  # queue a go-to (x, y, speed, flag); ecx the villager; ret 0x10
WALK_AREA = 0x4744C0                # queue a walk to a map area (area, speed, flag); ret 0xC
STARTER = 0x465580                  # start behaviour (id, &flag); ecx the villager; ret 8
PROJECT_DONE, PROJECTS, LAST_HEATHEN = 0x43AE80, 0x51E008, 25
CHANCE = 50                         # rand(100) < 50: the hovel half of the time

REFLECTING, REFLECTING_ROUTINE, REFLECTING_REGISTRATION = 29, 0x457E90, 0x46409E
REFLECTING_WALKS = (0x457EE2, 0x457F13, 0x457F6E, 0x457FC9, 0x458024)
HONORING, HONORING_ROUTINE, HONORING_CHOOSER_START = 17, 0x4595B0, 0x46B145
HONORING_GRAVE_WALKS = (0x459630, 0x45966D, 0x4596BA)       # area 0x7B; the flowers' walk 0x4595FA stays
DAY_OF_HONOR_START = 0x414DDA

HOVEL_X, HOVEL_X_SPAN, HOVEL_Y, HOVEL_Y_SPAN = 2176, 97, 1576, 25
REFLECT_MARK_DEPTH = 0x1C           # go-to: ret, 4 args, edi, esi, then the wrapper's return
HONOR_MARK_DEPTH = 0x2C             # area walk: ret, 3 args, esi, 0x452BD0's ret + arg, 0x465580's ret + 3 args

# Two pieces of the .text tail freed by the Origins clean-up (tests/test_vv5_origins_dead_code_removed.py): every
# byte must be reached, and nothing else claims them.
CAVE_A = (0x494B40, 0x494BC0)
CAVE_B = (0x494DA0, 0x494E00)


def asm(src: str, va: int) -> bytes:
    return bytes(KS.asm(src, va)[0])


_stock: tuple | None = None


def stock(va: int, n: int) -> bytes:
    global _stock
    if _stock is None:
        _stock = (pefile.PE(str(STOCK), fast_load=True), STOCK.read_bytes())
    pe, data = _stock
    off = pe.get_offset_from_rva(va - 0x400000)
    return data[off:off + n]


def hovel_point(rx: int, ry: int) -> tuple[int, int]:
    return HOVEL_X + rx, HOVEL_Y + ry


def _pieces(at: dict[str, int]) -> list[tuple[str, str, str, int]]:
    """(cave, name, source, mark) in order; each source is assembled at at[name].  A wrapper's mark is the
    return address of its own call of the action (its last `mark` bytes: pop ecx / ret, or ret 8)."""
    return [
        # decide: al = 1 when the hovel is a memorial (The Last Heathen done) and rand(100) < 50; keeps ecx.
        ("A", "decide", f"""
            push ecx
            push {LAST_HEATHEN}
            mov ecx,{PROJECTS:#x}
            call {PROJECT_DONE:#x}
            test al,al
            je no
            push 100
            call {RAND:#x}
            pop ecx
            cmp eax,{CHANCE}
            setl al
        no:
            pop ecx
            ret
        """, 0),
        # Reflecting's registered routine (cdecl, the villager): on "yes", run the stock routine from this call.
        ("A", "reflect", f"""
            call {at['decide']:#x}
            test al,al
            jne hovel
            jmp {REFLECTING_ROUTINE:#x}
        hovel:
            push dword ptr [esp+4]
            call {REFLECTING_ROUTINE:#x}
            pop ecx
            ret
        """, 2),
        # The everyday chooser's start of Honoring the dead (ecx the villager; the id and &flag on the stack).
        ("A", "honor", f"""
            call {at['decide']:#x}
            test al,al
            jne hovel
            jmp {STARTER:#x}
        hovel:
            push dword ptr [esp+8]
            push dword ptr [esp+8]
            call {STARTER:#x}
            ret 8
        """, 3),
        # Honoring's walks to the graves (area 0x7B): marked -> a go-to the hovel point, else as stock.
        ("A", "honor_walk", f"""
            cmp dword ptr [esp+{HONOR_MARK_DEPTH:#x}],{at['honor_mark']:#x}
            jne {WALK_AREA:#x}
            call {at['point']:#x}
            push dword ptr [esp+0xc]
            push dword ptr [esp+0xc]
            push edx
            push eax
            call {WALK_TO:#x}
            ret 0xc
        """, 0),
        # point: eax = x, edx = y, a random point in front of the hovel; keeps ecx.
        ("B", "point", f"""
            push ecx
            push {HOVEL_X_SPAN}
            call {RAND:#x}
            mov dword ptr [esp],eax
            push {HOVEL_Y_SPAN}
            call {RAND:#x}
            pop edx
            lea edx,[eax+{HOVEL_Y}]
            pop eax
            add eax,{HOVEL_X}
            pop ecx
            ret
        """, 0),
        # Reflecting's go-tos: marked -> the hovel point, else as stock.
        ("B", "reflect_walk", f"""
            cmp dword ptr [esp+{REFLECT_MARK_DEPTH:#x}],{at['reflect_mark']:#x}
            jne {WALK_TO:#x}
            call {at['point']:#x}
            mov dword ptr [esp+4],eax
            mov dword ptr [esp+8],edx
            jmp {WALK_TO:#x}
        """, 0),
    ]


def _assemble(at: dict[str, int]) -> tuple[bytes, bytes, dict[str, int]]:
    caves = {"A": [CAVE_A[0], b""], "B": [CAVE_B[0], b""]}
    new = dict(at)
    for cave, name, src, mark in _pieces(at):
        va = caves[cave][0] + len(caves[cave][1])
        code = asm(src, va)
        new[name] = va
        if mark:
            new[name + "_mark"] = va + len(code) - mark
        caves[cave][1] += code
    return caves["A"][1], caves["B"][1], new


def caves() -> tuple[bytes, bytes, dict[str, int]]:
    """Both caves and every piece's address (assembled until the forward references settle)."""
    at = {name: 0x494000 for name in ("decide", "reflect", "reflect_mark", "honor", "honor_mark", "honor_walk",
                                      "point", "reflect_walk")}
    for _ in range(4):
        code_a, code_b, new = _assemble(at)
        if new == at:
            break
        at = new
    code_a, code_b, again = _assemble(at)
    assert again == at, "the layout settled"
    assert CAVE_A[0] + len(code_a) <= CAVE_A[1], len(code_a)
    assert CAVE_B[0] + len(code_b) <= CAVE_B[1], len(code_b)
    return code_a, code_b, at


def patch(va: int, after: bytes, purpose: str, before: bytes | None = None) -> dict:
    before = stock(va, len(after)) if before is None else before
    assert len(before) == len(after)
    return {"offset": "0x%X" % (va - 0x400000), "before": before.hex().upper(), "after": after.hex().upper(),
            "purpose": purpose}


DESCRIPTION = (
    "Best paired with \"More Respectful Flower Hovel Cover\". Villagers will sometimes come here to pay their "
    "respects to those that passed on, and others that guide their fate. **Needs no other patch.** Once every "
    "Heathen has been converted and the villagers have fixed up the old Heathen hovel (the game's own moment: The "
    "Last Heathen is solved and the hovel's flower cover appears), the hovel becomes a memorial for good, even if "
    "Heathens come back later. From then on, a villager who goes \"Honoring the dead\" on an ordinary day honors at "
    "the hovel half of the time: they still go for their flowers first, then lay them in front of the hovel instead "
    "of at the graves. A villager \"Reflecting\" also reflects in front of the hovel half of the time instead of in "
    "the usual spot. Each walk goes to a random point of the open ground just in front of the hovel. The Day of "
    "Honor island event's honoring, every other action and every other place are unchanged, and before the "
    "memorial nothing changes. Nothing is saved: the game's own puzzle progress decides it. **New Believers never "
    "sends villagers \"Reflecting\" by itself: only a Custom Island Event (Story / Cheat Upgrades) does, so the "
    "Reflecting part shows only then.**")


def feature() -> dict:
    code_a, code_b, at = caves()
    call = lambda site, target: asm(f"call {target:#x}", site)          # noqa: E731
    patches = [
        patch(REFLECTING_REGISTRATION, b"\x68" + at["reflect"].to_bytes(4, "little"),
              f"\"Reflecting\" (behaviour 29) registration: push 0x457E90 -> push the wrapper 0x{at['reflect']:X}"),
        patch(HONORING_CHOOSER_START, call(HONORING_CHOOSER_START, at["honor"]),
              f"the everyday \"Honoring the dead\" chooser 0x46B0F0's start of behaviour 17: call 0x465580 -> call "
              f"the wrapper 0x{at['honor']:X}"),
    ]
    for site in REFLECTING_WALKS:
        patches.append(patch(site, call(site, at["reflect_walk"]),
                             f"\"Reflecting\" (0x457E90)'s go-to: call 0x4745A0 -> call 0x{at['reflect_walk']:X}"))
    for site in HONORING_GRAVE_WALKS:
        patches.append(patch(site, call(site, at["honor_walk"]),
                             f"\"Honoring the dead\" (0x4595B0)'s walk to the graves (area 0x7B): call 0x4744C0 -> "
                             f"call 0x{at['honor_walk']:X}"))
    patches.append(patch(CAVE_A[0], code_a,
                         f"cave: the memorial-and-chance check 0x{at['decide']:X} (The Last Heathen, project 25, done "
                         f"(0x43AE80) and rand(100) < 50), the Reflecting wrapper 0x{at['reflect']:X} (mark "
                         f"0x{at['reflect_mark']:X}), the Honoring start wrapper 0x{at['honor']:X} (mark "
                         f"0x{at['honor_mark']:X}) and the marked graves walk 0x{at['honor_walk']:X}",
                         bytes(len(code_a))))
    patches.append(patch(CAVE_B[0], code_b,
                         f"cave: the hovel point 0x{at['point']:X} (2176 + rand(97), 1576 + rand(25)) and the marked "
                         f"Reflecting go-to 0x{at['reflect_walk']:X}", bytes(len(code_b))))
    return {
        "id": ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": NAME,
        "description": DESCRIPTION,
        "output_tag": "Hovel Memorial Actions",
        "behavior_changes": [
            "The hovel is a memorial once The Last Heathen (project 25) is done (0x43AE80 on 0x51E008): the game solves "
            "it when no Heathen is left and the villagers have fixed up the mud hut (0x437120, behaviour 0xD8, "
            "0x46D487), and draws the hovel's flower cover from then on (0x4370E0). Project progress is saved and "
            "never goes back, so the hovel stays a memorial even when Heathens appear again.",
            "The everyday \"Honoring the dead\" (behaviour 17, 0x4595B0) started by its chooser 0x46B0F0 (0x46B145): "
            "with the memorial, rand(100) < 50 sends its three walks to the graves (area 0x7B) to random points in "
            "front of the hovel instead, x = 2176 + rand(97), y = 1576 + rand(25) (the feet's point; 2176..2272 by "
            "1576..1600); its walk for the flowers (area 0x7A) is unchanged.",
            "\"Reflecting\" (behaviour 29, 0x457E90; registered at 0x46409E, so every start of it): with the "
            "memorial, rand(100) < 50 sends its five go-tos to random points in front of the hovel instead of "
            "1530..1803 by 1606..1805.",
        ],
        "explicit_non_changes": [
            "The Day of Honor island event's honoring (behaviour 17 for everyone, 0x414DDA -> 0x470C60) and the Custom "
            "Island Event's \"Honoring the dead [Day of Honor]\" are as stock; so are \"Honoring the dead (another "
            "way)\" (behaviour 46, 0x4567C0) and every other action.",
            "Before The Last Heathen is solved everything is as stock. The actions' text, gestures, speeds, flags and "
            "length are their own. No save, sidecar or villager-record byte is written.",
        ],
        "companion_files": [],
        "patches": patches,
    }


def main() -> None:
    record = feature()
    for p in record["patches"]:
        va = int(p["offset"], 16) + 0x400000
        assert stock(va, len(p["before"]) // 2).hex().upper() == p["before"], p["offset"]
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    sys.exit(main())
