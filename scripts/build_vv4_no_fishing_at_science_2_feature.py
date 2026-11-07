"""Generate data/vv4_no_fishing_at_science_2_feature.json: "No Fishing at Science Level 2" (The Tree of Life).

The owner: "I'm thinking that VV4 fishing is too easy! How about a new patch: No Fishing at Science Level 2:
Instead of villagers being able to create the clothing hut at science level 2, it locks it behind science level 3!
(if the clothing hut is already spawned but unbuilt the game relocks it until science level 3 is done)" -- then
"DEFAULT ON IN OWNER's DEFAULTS" (off in the normal defaults: a difficulty change).

Guarded exe edits only, assembled here (keystone) from the stock bytes (research/stock-executables).  Run after
any change and re-run tests/test_vv4_no_fishing_at_science_2.py.

WHY FISHING COMES EARLY (stock).  Science is tech 0 of the tech levels at 0x4D6F5C (0x41E1C0 reads
[0x4D6F5C + 4 * tech]).  Level 2 costs 8,000 tech points, level 3 70,000 (0x4BC18C).  The Clothing Hut is project
22 of the project manager 0x4D8BF8 (progress dword [0x4D8BF8 + 8 * 22] = 0x4D8CA8, done at the threshold
[0x4D8B20 + 4 * 22] = 0x4D8B78, 2,000 points, registered by its constructor 0x431190); its building object is the
static 0x4D82D8 (vtable 0x48E54C).
  * Cloth Invented (puzzle 7, drop handler 0x436D40): dropped on the tough vines, a villager says "Don't know what
    to do with these tough vines!" (0x249) while project 22 is unfinished (0x436D74); with the Clothing Hut built
    it starts cutting the pulpy vines (action 122), the cloth chain whose bolts the hut counts ("Cloth bolts
    available:", 0x7D, its hover 0x46F62F on [0x4D8ACC]).
  * Fishing Nets (puzzle 11, drop handler 0x433440): with the piers fixed (stage [0x4D86AC] >= 2) a villager
    dropped on the nets fixes them (action 127) only with project 22 finished (0x4334FC); otherwise "They need
    cloth for this!" (0x136).  The nets' work takes a cloth bolt (0x464879: [0x4D8ACC] > 0 -> 0x4369F0 on the
    store 0x4D8AC8, else "They need cloth for this!").
So the Clothing Hut gates both the cloth and the nets, and its site appears at Science 2.

THE SITE (stock).  Every building object's update 0x4300E0 (vtable +0x24, run for each building by 0x438910)
first asks its reveal predicate (vtable +0x64); the Clothing Hut's is 0x430CF0: state (vtable +0x3C, 0x4303E0) is
4 (an unrevealed site) and Science > 1.  When it answers yes the reveal 0x430810 picks the site's place, calls
SetState(3) (0x430430: progress = 2000 - 2000 = 0) and paints the site into the map (vtable +0x70, 0x430A20).
Then, at 0x430156, a second path: object 22 in state 4 with Science exactly 3 is set to state 3 without
SetState.  The state [obj+0x34] and the place are saved with the object (its 0x1C-byte record [obj+0x28..0x43],
0x42FE80 / 0x42FE30); the progress is saved separately in the project manager's table (0x4387A0).  The load paints
the site (0x42FE30 -> vtable +0x70) unless its state is 4, and the tech levels load after the buildings
(0x41FCD0 then 0x41FCE9), so the place to re-check Science is the update, not the load.  A state-4 object draws
nothing (the update's stage is -1, 0x430110 / 0x4301FA; the draw 0x42FEB0 skips stage -1) and is not painted
(0x430A26), so no villager can be dropped on it, walk into it or build in it (the build step 0x430210 adds points
only for a villager standing in the object's own map area, 0x43023B).
Builders reach the site three ways:
  * the Building dispatcher's option 8 (0x463E49): project 22's percent (0x438980) >= 1 and not finished; the
    Builders Fix Huts companion re-adds the same option on the same test (native/vvfp_fix_huts, VV4 options);
  * a villager whose task is 15 (set by the drop, 0x46F736) keeps building it while project 22 is unfinished
    (task switch 0x463940[12] -> 0x463786, the finished test 0x438960 at 0x46378D);
  * catch-up runs the same dispatcher and task code with the walks made instant.

THE PATCH.  Locked = Science below 3 and project 22 unfinished.
  1. The reveal predicate 0x430CF0 answers yes only at Science 3, and only for a site never built on (state 4,
     progress 0) -- so SetState(3) never resets points a relocked site already has.  Stock: Science 2.
  2. The update's second path 0x430156 (every building passes it; only object 22 is acted on), rewritten:
       Science 3:  state 4 -> state 3 (the stock path, now for every progress): the site comes back where it was,
                   with its points; the next update repaints it (its paint flag +0x61 is still set).
       Locked and the site showing (state not 4): relock -- state 4, and the site's map area is erased with the
       game's own erase 0x430490 (the routine that lifts a building off the map), then its drag flag +0x54 is
       cleared and its paint flag +0x61 set (as the paint left them unset).  The progress table is never written.
  3. The Clothing Hut's percent helper (its vtable +0x34, read by 0x438980) answers threshold - 1 while locked, so
     project 22's percent is never 1 or more there: no builder, Fix Huts' list included, is sent to it.  A
     finished hut still reads 100 (0x438980 with nothing left).
  4. The task-15 continuation's finished test (0x46378D) answers "finished" while Science is below 3, so a villager
     saved mid-build drops the task.
A finished Clothing Hut is never relocked (2) and its percent is unchanged (3).  Uninstalled later, the stock game
shows a relocked site again at Science 3 (its own 0x430156 path) with its points; below Science 3 it stays hidden
when its points are 400 or more, and a site under 400 points is revealed by the stock predicate with its points
reset (stock SetState(3)), the stock game's own behaviour for any state-4 site.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
OUT = ROOT / "data" / "vv4_no_fishing_at_science_2_feature.json"
KS = Ks(KS_ARCH_X86, KS_MODE_32)

FEATURE_ID = "vv4_no_fishing_at_science_2"
NAME = "No Fishing at Science Level 2"

SCIENCE = 0x4D6F5C          # tech levels, Science = tech 0
PROGRESS = 0x4D8CA8         # project 22's progress (0x4D8BF8 + 8 * 22)
THRESHOLD = 0x4D8B78        # project 22's threshold (0x4D8B20 + 4 * 22)
BUILD_TOTAL = 2000          # the threshold the constructor registers (0x431198 push 0x7D0)
PREDICATE = 0x430CF0        # the Clothing Hut's reveal predicate, vtable +0x64; 0x30 bytes to 0x430D20
SECOND_PATH = 0x430156      # the update's object-22 path, 0x30 bytes to 0x430186
AFTER_PATH = 0x430186
ERASE = 0x430490            # lift a building off the map (vtable +0x48)
PERCENT_BASE = 0x4303C0     # the shared vtable +0x34
VTABLE_PERCENT = 0x48E54C + 0x34
FINISHED = 0x438960         # project manager: finished(id)
CONTINUATION_CALL = 0x46378D
# int3 padding between the building class's small routines and after 0x432380 / 0x4323F3, claimed by nothing.
GAPS = (0x430F92, 0x430FA6, 0x430FC2, 0x430FD4)
FINISHED_GATE = 0x432381
FINISHED_GATE_TAIL = 0x4323F6
PERCENT_GATE = 0x430D0B     # in the predicate's own space, after the rewritten predicate


def asm(src: str, va: int) -> bytes:
    return bytes(KS.asm(src, va)[0])


_PE = pefile.PE(str(EXE), fast_load=True)
_DATA = EXE.read_bytes()


def offset(va: int) -> int:
    return _PE.get_offset_from_rva(va - _PE.OPTIONAL_HEADER.ImageBase)


def stock(va: int, n: int) -> bytes:
    return _DATA[offset(va):offset(va) + n]


def patch(va: int, after: bytes, purpose: str) -> dict:
    before = stock(va, len(after))
    return {"offset": "0x%X" % offset(va), "before": before.hex().upper(), "after": after.hex().upper(),
            "purpose": purpose}


def fill(code: bytes, size: int) -> bytes:
    assert len(code) <= size, (len(code), size)
    return code + b"\xCC" * (size - len(code))


def predicate_and_percent() -> bytes:
    predicate = asm(f"""
        xor eax,eax
        cmp byte ptr [ecx+0x34],4
        jne r
        cmp dword ptr [{PROGRESS:#x}],eax
        jne r
        cmp dword ptr [{SCIENCE:#x}],3
        setge al
    r:
        ret
        """, PREDICATE)
    assert PREDICATE + len(predicate) == PERCENT_GATE, hex(PREDICATE + len(predicate))
    percent = asm(f"""
        cmp dword ptr [{SCIENCE:#x}],3
        jge {PERCENT_BASE:#x}
        mov eax,{BUILD_TOTAL - 1}
        ret
        """, PERCENT_GATE)
    return fill(predicate + percent, 0x30)


def second_path() -> bytes:
    code = asm(f"""
        cmp dword ptr [esi+8],0x16
        jne {AFTER_PATH:#x}
        cmp dword ptr [{SCIENCE:#x}],3
        jge up
        mov eax,dword ptr [{PROGRESS:#x}]
        cmp eax,dword ptr [{THRESHOLD:#x}]
        jge {AFTER_PATH:#x}
        jmp {GAPS[0]:#x}
    up:
        cmp byte ptr [esi+0x34],4
        jne {AFTER_PATH:#x}
        mov byte ptr [esi+0x34],3
        jmp {AFTER_PATH:#x}
        """, SECOND_PATH)
    return fill(code, AFTER_PATH - SECOND_PATH)


def relock() -> list[bytes]:
    back = GAPS[3] + 4                       # the jmp back in the last gap
    one = asm(f"""
        cmp byte ptr [esi+0x34],4
        je {back:#x}
        mov byte ptr [esi+0x34],4
        jmp {GAPS[1]:#x}
        """, GAPS[0])
    two = asm(f"""
        cmp byte ptr [esi+0x61],0
        jne {back:#x}
        mov ecx,esi
        jmp {GAPS[2]:#x}
        """, GAPS[1])
    three = asm(f"""
        call {ERASE:#x}
        mov byte ptr [esi+0x54],0
        jmp {GAPS[3]:#x}
        """, GAPS[2])
    four = asm(f"""
        mov byte ptr [esi+0x61],1
        jmp {AFTER_PATH:#x}
        """, GAPS[3])
    assert len(asm("mov byte ptr [esi+0x61],1", GAPS[3])) == 4
    sizes = (14, 10, 14, 12)
    return [fill(code, size) for code, size in zip((one, two, three, four), sizes)]


def finished_gate() -> tuple[bytes, bytes]:
    head = asm(f"""
        cmp dword ptr [{SCIENCE:#x}],3
        jge {FINISHED:#x}
        jmp {FINISHED_GATE_TAIL:#x}
        """, FINISHED_GATE)
    tail = asm("mov al,1\nret 4", FINISHED_GATE_TAIL)
    return fill(head, 15), fill(tail, 10)


DESCRIPTION = (
    "**Needs no other patch.** Makes fishing come later, so the game is harder; off by default. In the base game "
    "buying Science level 2 (8,000 tech points) makes the Clothing Hut's building site appear, and the Clothing Hut "
    "is what lets your villagers make cloth (Cloth Invented) and mend the fishing nets with it (Fishing Nets) -- so "
    "fish come early. With this patch the Clothing Hut's site appears only at Science level 3 (70,000 tech points). "
    "A village whose Clothing Hut site is already showing, with or without some building done, while Science is "
    "below 3 gets the site locked again: it disappears and nobody builds it until Science reaches 3; then it comes "
    "back in the same place with all the building it already had. Nothing is reset or lost. A Clothing Hut that is "
    "already finished is never affected."
)


def feature() -> dict:
    a, b = finished_gate()
    gaps = relock()
    patches = [
        patch(SECOND_PATH, second_path(),
              "the update's object-22 path 0x430156 (every building passes it; only the Clothing Hut, project 22, is "
              "acted on): at Science 3 a hidden site (state 4) becomes state 3 with its progress and place kept, as "
              "the stock path did; below Science 3 an unfinished site that is showing is relocked (0x430F92)"),
        patch(PREDICATE, predicate_and_percent(),
              "the Clothing Hut's reveal predicate 0x430CF0 (vtable +0x64): reveal at Science 3 (stock: 2), and only "
              "a site never built on (state 4, progress 0), so the reveal's SetState(3) never resets progress; then "
              "its percent helper 0x430D0B: threshold - 1 below Science 3 (project 22's percent never reaches 1, so "
              "no builder is offered the site), else the shared 0x4303C0"),
        patch(VTABLE_PERCENT, (PERCENT_GATE).to_bytes(4, "little"),
              "the Clothing Hut's vtable +0x34 (0x48E580): 0x4303C0 -> its own percent helper 0x430D0B"),
        patch(GAPS[0], gaps[0], "relock, 1 of 4 (0x430F92): a site already in state 4 is left alone; else state 4"),
        patch(GAPS[1], gaps[1], "relock, 2 of 4 (0x430FA6): a site not painted (+0x61 set) needs no erase"),
        patch(GAPS[2], gaps[2],
              "relock, 3 of 4 (0x430FC2): erase the site's map area with the game's own 0x430490; clear the drag "
              "flag +0x54 it sets"),
        patch(GAPS[3], gaps[3], "relock, 4 of 4 (0x430FD4): mark it unpainted (+0x61), so Science 3 repaints it; back"),
        patch(FINISHED_GATE, a,
              "project 22's finished test for the task-15 continuation (0x432381): below Science 3 answer finished"),
        patch(FINISHED_GATE_TAIL, b, "...its answer (0x4323F6): al = 1, ret 4"),
        patch(CONTINUATION_CALL, asm(f"call {FINISHED_GATE:#x}", CONTINUATION_CALL),
              "the task-15 continuation 0x463786 (a villager building the Clothing Hut): call 0x432381 instead of "
              "0x438960, so below Science 3 the villager drops the task"),
    ]
    return {
        "id": FEATURE_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": NAME,
        "description": DESCRIPTION,
        "output_tag": "No Fishing at Science 2",
        "behavior_changes": [
            "The Clothing Hut's site (project 22, object 0x4D82D8) is revealed by its predicate 0x430CF0 at Science 3 "
            "(stock: Science 2, i.e. above 1), and only while it was never built on.",
            "Below Science 3 an unfinished Clothing Hut site that shows (state not 4) is relocked by the update "
            "0x4300E0 (path 0x430156): state 4, its map area erased by the game's own 0x430490; at Science 3 it "
            "returns to state 3 in the same place and is repainted. Its progress (0x4D8CA8) is never written.",
            "Below Science 3 project 22's percent (0x438980) is below 1, so the Building dispatcher (0x463E49) and "
            "Builders Fix Huts When Idle never offer it, live or while catching up; a villager on task 15 (building "
            "it) drops the task (0x46378D).",
        ],
        "explicit_non_changes": [
            "A finished Clothing Hut, every other building, the tech prices, Cloth Invented and Fishing Nets "
            "themselves are unchanged; no save data is written by the patch beyond the site's own state.",
            "Guarded edits in place: two rewritten stock routines (0x430156, 0x430CF0), one vtable entry, one call, "
            "and int3 padding between routines; no executable tail space is claimed.",
        ],
        "evidence_status": (
            "implemented from exact-build disassembly; the reveal at Science 1/2/3, the relock of a showing site "
            "(0 to 1,999 points) and its return at Science 3, a finished hut, project 22's percent and the task-15 "
            "continuation are emulated stock and patched on the game's own Clothing Hut object and map in "
            "tests/test_vv4_no_fishing_at_science_2.py; runtime/player confirmation pending"),
        "companion_files": [],
        "patches": patches,
    }


def main() -> None:
    record = feature()
    for p in record["patches"]:
        assert len(p["before"]) == len(p["after"]), p["offset"]
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    sys.exit(main())
