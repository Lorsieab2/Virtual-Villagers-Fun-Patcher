"""Generate data/vv4_harder_fishing_unlock_feature.json: "Harder Fishing Unlock in VV4" (The Tree of Life).

The owner (2026-11-08): "the clothing hut itself unlocks as normal in Science Level 2, but the player can't make cloth
until Science Level 3. Dropping villagers on the pulpy vines used to make cloth give the standard "Don't know what to
do with these tough vines!" refusal." -- "Default ON in Owner's Defaults", in Classic VV Difficulty; cloth already
made stays usable.  Then: "Remove the Clothing Hut unlocks at Level 3 Science patch (not needed). Add to the Cloth
Unlocks at Level 3 Science Patch - a patch that locks fixing the piers at Level 3 Construction. Combine those two and
retitle it as: "Harder Fishing Unlock in VV4"" (the patch was "Clothmaking Unlocks at Science Level 3", id
vv4_clothmaking_at_science_3, never released).

Guarded exe edits only, assembled here (keystone) from the stock bytes (research/stock-executables).  Run after any
change and re-run tests/test_vv4_harder_fishing_unlock.py.

THE TECH LEVELS.  The levels are dwords at 0x4D6F5C (0x41E1C0 reads [0x4D6F5C + 4 * tech]); Science is tech 0
(0x4D6F5C), Construction tech 3 (0x4D6F68: Hut 2's reveal 0x430B90 asks tech 3 > 1, Hut 3's 0x430C00 tech 3 > 2).
A level's price is 0x4BC18C[level + 1 + 3 * tech] (0x41E220): Science 8,000 / 70,000, Construction 5,000 / 65,000.
Levels only go up (the purchase, the loader, island events).

1. THE CLOTH (research/stock-executables, capstone, 2026-11-08).  Cloth Invented (puzzle 7, CClothmaking vtable
0x48E908, constructor 0x436DC0) registers the vines' drop handler 0x436D40.  Its first case (0x436D74) asks whether
project 22 (the Clothing Hut) is finished (0x438960 on the project manager 0x4D8BF8): no -> the villager says "Don't
know what to do with these tough vines!" (string 0x249, 0x436D88..0x436D9E); yes (0x436D86 jne) -> 0x436D9F starts
action 0x7A, cutting the pulpy vines, the cloth chain.  Nothing else starts action 0x7A (its other mentions: its
registration 0x436DE4, an animation table 0x43AADB, a map-area count 0x455822), so no autonomous job or catch-up turn
makes cloth: the drop is the only way.
THE CHANGE: the finished test's jne (0x436D86, "75 17") goes to a check in the int3 padding after the handler
(0x436DB4..0x436DBF, 12 bytes, between the handler's ret and the constructor 0x436DC0): Science below 3 -> the stock
refusal at 0x436D88; else the stock cloth start 0x436D9F.  ecx (the villager) is loaded at 0x436D82 before the jne,
as both paths need.  Cloth bolts already in the store, the nets' use of them (0x464879), the Clothing Hut and its
site are unchanged.

2. THE PIERS (same build, 2026-11-08).  Fishing Nets is project 11 (puzzle object 0x4D86A8, vtable 0x48E818,
constructor 0x433570 via 0x488BC0, reset 0x4329C0: stage +4 = 0, pier counter +8 = 100, nets counter +0xC = 0).  Its
actions: 0x7F (127) fix nets, 0x80 (128) fix piers (handler 0x433050), 0x81 (129) retrieving a fish.  The pier work:
action 0x80 queues a Building attempt and job event 0x33 (0x4330E6, the only place event 0x33 is queued); the event
(0x4642F0 -> 0x46484F) calls 0x432FA0(0), which takes 20 off the counter: stage 1 at 50 or less, stage 2 (piers
fixed) at 0.  0x432FA0 has two callers, events 0x33 (piers) and 0x34 (nets); the object's other readers are the
dispatcher and the continuation below (0x4D86A8 / 0x4D86AC are referenced nowhere else but the constructor).  Action
0x80 is started in three places only (every push 0x80 before a call to the action start 0x45DEC0):
  * the player's drop, the handler 0x433440, case 0 (0x4334BC): project 11 unfinished and stage < 2 (0x4334CC) ->
    action 0x80 with task 30 (0x1E, +0x1C54) at 0x4334D5;
  * the Building dispatcher: option 6 is listed only while the stage is < 2 and the counter < 100 (0x463DD8..0x463DF4;
    so only once the player has started the piers) and a dislike of 0x1E passes its 16% (0x463DF6); option 6 ->
    0x464085 starts action 0x80;
  * the task continuation: task 30 (0x463535 switch 0x463908 -> 0x4635C6, its time test, then 0x4635CE switch
    0x463940 index 28 -> 0x46384D): project 11 unfinished and stage < 2 -> action 0x80 again (0x463874), else the
    task is cleared (0x4636DD).
Catch-up runs the same dispatcher and continuation.  A pier fix under way is not saved: the step queue is the
record's first part, outside the saved part (src/vv_game_mechanics_farmers_vv4.py); the task is, so a villager saved
mid-fix comes back through the continuation.
THE REFUSAL: "Additional research may be necessary." (0x75), what the game itself says when a villager is dropped on
a building that needs more Construction: Hut 2 below Construction 2 (0x46F38A) and Hut 3 below Construction 3
(0x46F477), both action 0x1A with 0x75.
THE CHANGE (Construction 0x4D6F68 below 3; at 3 every path is stock):
  * the drop's case 0 tail 0x4334CC..0x433544 rewritten in place (121 bytes, same entry and the fish path 0x433545
    kept): piers unfixed -> below Construction 3 the refusal 0x75; else the stock pier start (action 0x80, task 30).
    The nets' branch (Clothing Hut finished -> action 0x7F; else "They need cloth for this!" 0x136) is the same code
    re-laid out to share the say;
  * the dispatcher's test 0x463DD8..0x463DF5 rewritten in place (30 bytes): option 6 also needs Construction 3; the
    stage and counter are read directly ([0x4D86AC], [0x4D86B0], as the getters 0x4396D0 / 0x421570 return them);
  * the continuation 0x46385B..0x463873 rewritten in place (25 bytes): below Construction 3 task 30 is cleared
    (0x4636DD) as for fixed piers.
Below Construction 3 no pier fix starts, so event 0x33 never fires and the counter is never written: piers already
fixed stay fixed, and a part-done counter is kept for Construction 3.  The nets, the fish and everything else are
unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
OUT = ROOT / "data" / "vv4_harder_fishing_unlock_feature.json"
KS = Ks(KS_ARCH_X86, KS_MODE_32)

FEATURE_ID = "vv4_harder_fishing_unlock"
NAME = "Harder Fishing Unlock in VV4"

SCIENCE = 0x4D6F5C          # tech 0
CONSTRUCTION = 0x4D6F68     # tech 3 (0x4D6F5C + 4 * 3)
PIER_STAGE = 0x4D86AC       # project 11's puzzle object 0x4D86A8, +4
PIER_COUNTER = 0x4D86B0     # +8
START_ACTION = 0x45DEC0
FINISHED = 0x438960
PROJECTS = 0x4D8BF8
NEED_RESEARCH = 0x75        # "Additional research may be necessary." (Hut 2 / Hut 3 below their Construction)
NEED_CLOTH = 0x136          # "They need cloth for this!"

# the cloth (unchanged from Clothmaking Unlocks at Science Level 3)
CLOTH_JNE, CLOTH_REFUSE, CLOTH_START, CLOTH_CAVE, CLOTH_CAVE_END = 0x436D86, 0x436D88, 0x436D9F, 0x436DB4, 0x436DC0
# the piers
DROP_TAIL, DROP_FISH = 0x4334CC, 0x433545
DISPATCH, DISPATCH_END, NOT_OFFERED = 0x463DD8, 0x463DF6, 0x463E27
CONTINUE, CONTINUE_END, CLEAR_TASK = 0x46385B, 0x463874, 0x4636DD

_PE = pefile.PE(str(EXE), fast_load=True)
_DATA = EXE.read_bytes()


def offset(va: int) -> int:
    return _PE.get_offset_from_rva(va - _PE.OPTIONAL_HEADER.ImageBase)


def stock(va: int, n: int) -> bytes:
    return _DATA[offset(va):offset(va) + n]


def asm(src: str, va: int) -> bytes:
    return bytes(KS.asm(src, va)[0])


def patch(va: int, after: bytes, purpose: str) -> dict:
    before = stock(va, len(after))
    return {"offset": "0x%X" % offset(va), "before": before.hex().upper(), "after": after.hex().upper(),
            "purpose": purpose}


def exact(code: bytes, size: int, pad: bytes) -> bytes:
    assert len(code) <= size, (len(code), size)
    return code + pad * (size - len(code))


def cloth() -> tuple[bytes, bytes]:
    cave = asm(f"cmp dword ptr [{SCIENCE:#x}],3\njl {CLOTH_REFUSE:#x}\njmp {CLOTH_START:#x}", CLOTH_CAVE)
    assert len(cave) <= CLOTH_CAVE_END - CLOTH_CAVE, len(cave)
    assert stock(CLOTH_CAVE, len(cave)) == b"\xCC" * len(cave)
    jne = asm(f"jne {CLOTH_CAVE:#x}", CLOTH_JNE)
    assert stock(CLOTH_JNE, 2) == bytes.fromhex("7517") and len(jne) == 2
    return jne, cave


def drop_tail() -> bytes:
    # Entered at 0x4334CC with project 11 unfinished (al = 0); [esp+0x10] is the villager, [esp+0xC] the case
    # argument the stock pier start uses for its data byte, [esp+2] / [esp+4] the handler's own locals (as stock).
    assert stock(DROP_TAIL, 9) == bytes.fromhex("833DAC864D00027D27")
    code = asm(f"""
        cmp dword ptr [{PIER_STAGE:#x}],2
        jge nets
        mov eax,{NEED_RESEARCH:#x}
        cmp dword ptr [{CONSTRUCTION:#x}],3
        jl say
        mov ecx,dword ptr [esp+0x10]
        lea eax,[esp+0xc]
        mov byte ptr [eax],0
        push eax
        push 0x80
        push 0x1e
        pop dword ptr [ecx+0x1c54]
        call {START_ACTION:#x}
        jmp tail
    nets:
        push 0x16
        mov ecx,{PROJECTS:#x}
        call {FINISHED:#x}
        test al,al
        mov eax,{NEED_CLOTH:#x}
        je say
        mov ecx,dword ptr [esp+0x10]
        lea eax,[esp+2]
        mov byte ptr [eax],0
        push eax
        push 0x7f
        call {START_ACTION:#x}
        jmp tail
    say:
        mov ecx,dword ptr [esp+0x10]
        lea edx,[esp+4]
        mov dword ptr [edx],eax
        push edx
        push 0x1a
        call {START_ACTION:#x}
    tail:
        mov al,1
        add esp,8
        ret
        """, DROP_TAIL)
    return exact(code, DROP_FISH - DROP_TAIL, b"\xCC")


def dispatch() -> bytes:
    assert stock(DISPATCH, 5) == bytes.fromhex("B9A8864D00")
    code = asm(f"""
        cmp dword ptr [{CONSTRUCTION:#x}],3
        jl {NOT_OFFERED:#x}
        cmp dword ptr [{PIER_STAGE:#x}],2
        jge {NOT_OFFERED:#x}
        cmp dword ptr [{PIER_COUNTER:#x}],0x64
        jge {NOT_OFFERED:#x}
        """, DISPATCH)
    return exact(code, DISPATCH_END - DISPATCH, b"\x90")


def continuation() -> bytes:
    assert stock(CONTINUE, 6) == bytes.fromhex("0F857CFEFFFF")
    clear = CONTINUE_END - 5
    code = asm(f"""
        jne {clear:#x}
        cmp dword ptr [{CONSTRUCTION:#x}],3
        jl {clear:#x}
        cmp dword ptr [{PIER_STAGE:#x}],2
        jl {CONTINUE_END:#x}
        jmp {CLEAR_TASK:#x}
        """, CONTINUE)
    assert len(code) == CONTINUE_END - CONTINUE, len(code)
    return code


DESCRIPTION = (
    "**Needs no other patch.** Makes fishing come later, so the game is harder; off by default. Fish need the "
    "fishing nets, and the nets need the piers fixed and cloth to mend them. With this patch cloth waits for Science "
    "level 3 (70,000 tech points) and fixing the piers waits for Construction level 3 (65,000 tech points). The "
    "Clothing Hut still appears at Science level 2 as normal, but until Science 3 a villager dropped on the vines "
    "says \"Don't know what to do with these tough vines!\" and makes no cloth. Until Construction 3 a villager "
    "dropped on the broken piers says \"Additional research may be necessary.\" (as on a hut that needs more "
    "Construction), builders do not go to fix them on their own, and a villager who was fixing them stops. Piers "
    "already fixed stay fixed, work already done on them is kept for Construction 3, and cloth the village already "
    "has can still be used: the nets are mended with it and the Clothing Hut gives clothes as before. Nothing else "
    "changes.")


def feature() -> dict:
    jne, cave = cloth()
    return {
        "id": FEATURE_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": NAME,
        "description": DESCRIPTION,
        "output_tag": "Harder Fishing Unlock",
        "behavior_changes": [
            "The vines' drop handler 0x436D40: with the Clothing Hut finished and Science below 3, the stock refusal "
            "\"Don't know what to do with these tough vines!\" (0x249) instead of the cloth start (action 0x7A); at "
            "Science 3 the stock cloth start.",
            "The Fishing Nets drop handler 0x433440 (case 0, project 11 unfinished): with the piers unfixed (stage "
            "[0x4D86AC] < 2) and Construction ([0x4D6F68], tech 3) below 3, the villager says \"Additional research "
            "may be necessary.\" (0x75, the game's refusal on Hut 2 / Hut 3 below their Construction level) instead "
            "of starting the pier fix (action 0x80, task 30); at Construction 3 the stock pier start. The nets' "
            "branch is unchanged.",
            "Below Construction 3 the Building dispatcher never lists \"Fixing the piers\" (option 6, 0x463DD8), live "
            "or while catching up, and a villager on task 30 (fixing the piers, saved mid-fix) has the task cleared "
            "(0x46385B) instead of resuming it; at Construction 3 both are stock.",
        ],
        "explicit_non_changes": [
            "The Clothing Hut's site (Science 2), its building, cloth bolts already in the store, the fishing nets' "
            "use of them, clothes and every other drop are unchanged; nothing but the vines' drop starts "
            "cloth-making.",
            "The piers' stage and counter are never written by the patch: fixed piers stay fixed and a part-done "
            "counter is kept; mending the nets, catching fish, the tech prices and every other building job are "
            "unchanged.",
            "Guarded in-place edits: one jump and int3 padding after the vines' handler, and three stock routines' "
            "own bytes rewritten to the same length (the nets' drop tail, the dispatcher's pier test, the task-30 "
            "continuation); no executable tail space is claimed.",
        ],
        "evidence_status": (
            "implemented from exact-build disassembly; the vines' drop at Science 1, 2 and 3, and the piers' drop, "
            "the dispatcher's pier offer and the task-30 continuation at Construction 1, 2 and 3 with the piers "
            "unfixed, part-done and fixed (and the nets' branch with the Clothing Hut finished and unfinished) are "
            "emulated stock and patched in tests/test_vv4_harder_fishing_unlock.py; runtime/player confirmation "
            "pending"),
        "companion_files": [],
        "patches": [
            patch(CLOTH_JNE, jne, "the Clothing Hut finished test's jump (0x436D86): to the Science check 0x436DB4"),
            patch(CLOTH_CAVE, cave, "the Science check in the padding (0x436DB4): below 3 the stock refusal "
                                    "0x436D88, else the stock cloth start 0x436D9F"),
            patch(DROP_TAIL, drop_tail(),
                  "the Fishing Nets drop, case 0 tail (0x4334CC..0x433544, same length): piers unfixed and "
                  "Construction below 3 -> say 0x75 \"Additional research may be necessary.\"; else the stock pier "
                  "start (action 0x80, task 30); piers fixed -> the stock nets branch (Clothing Hut finished -> "
                  "action 0x7F, else say 0x136), sharing one say"),
            patch(DISPATCH, dispatch(),
                  "the Building dispatcher's pier test (0x463DD8): option 6 only at Construction 3, with the stock "
                  "stage < 2 and counter < 100"),
            patch(CONTINUE, continuation(),
                  "the task-30 continuation (0x46385B): below Construction 3 the task is cleared (0x4636DD), as for "
                  "fixed piers; else the stock stage test"),
        ],
    }


def main() -> None:
    record = feature()
    for p in record["patches"]:
        assert len(p["before"]) == len(p["after"]), p["offset"]
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
