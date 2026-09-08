"""Emit the VV1 Parentage Tracker feature manifest.

The hook records both parents at CONCEPTION, because parentage is stored
nowhere in a villager record: an independent RE audit of all four exact builds
(data/mask_identity_adapters.json) found the inheritance path that writes a
child's own head and body, but no instruction that stores any parent's name,
head or body into the child. Inheritance computes the child's own appearance
and discards the parents' values, so the parents cannot be recovered from the
child afterwards by any means. They must be captured while both are still
identifiable, which is exactly what the owner's specification asks for.

WHERE THE HOOK GOES

sub_43BBC0 (VA 0x0043BBC0) is VV1's conception routine. It was not located by
searching for birth strings -- "Babies Made", "Twins Birthed" and "Triplets
Birthed" have ZERO code cross-references, because they live in a five-dword
localisation table at 0x4874DC (string id plus four languages). Searching for
them finds nothing and invites the conclusion that the path is absent.

Instead it was located from the counter offsets the shipping statistics
companion already reads and which are therefore independently proven:

    manager + 0x9E24  Babies Made       inc at 0x43BC1C / 0x43BC5E / 0x43BC9C
    manager + 0x9E44  Twins Birthed     inc at 0x43BCC0
    manager + 0x9E48  Triplets Birthed     at 0x43BCA8 / 0x43BCB0

Exactly one function increments all three. That is the birth site by
construction rather than by resemblance.

Note sub_41C000 is NOT this site and is easy to mistake for it: it initialises
every record and touches head, body and +0x29, but it ZEROES those counters
(`mov [ebp+9E24h], ebx`) rather than incrementing them. It is the initial
village generator.

THE ARGUMENTS, READ FROM THE STOCK BYTES

At the function head, before any push:

    0x43BBC0  push edi                     ; esp shifts by 4 from here on
    0x43BBC1  mov  edi, ecx                ; ecx = the villager RECORD ARRAY
    0x43BBEA  imul edx, edx, 0x3D8         ; from [esp+8] -- the record stride
    0x43BBF1  lea  esi, [edx + edi]        ; esi = the MOTHER's record
    0x43BC04  mov  [esi+0x394], edx        ; from [esp+0x10] -- the FATHER id

and the call site confirms the same three arguments:

    0x43DD24  mov  eax, [edx + 0x36C]      ; the father's villager ID
    0x43DD2A  push ecx                     ; mother index
    0x43DD2F  push eax                     ; father id  (a VALUE, not an index)
    0x43DD30  push ecx
    0x43DD31  mov  ecx, esi                ; record array base
    0x43DD33  call sub_43BBC0

`0x3D8` reproducing the proven record stride is what establishes that ecx is
the record array and that [esp+8] is the mother's index.

WHY THE CAVE FOOTPRINT IS ONLY A TRAMPOLINE

Cave space is the scarce resource here: VV1 has exactly ONE zero run in .text
big enough to use (VA 0x00456580, length 0xA80), and the statistics feature
already holds 0xD0 of it at 0x456730. So every byte of real work -- file I/O,
name reading, the father lookup, log rolling -- lives in the companion DLL.
What remains in the cave is the irreducible minimum: the loader trampoline,
because a patched call must land on bytes inside the executable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
COMPANION = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"
OUTPUT = ROOT / "data" / "vv1_parentage_feature.json"

EXE = "Virtual Villagers - A New Home.exe"

# The conception routine, and the byte at which the trampoline takes over.
HOOK_VA = 0x0043BBC0
HOOK_FILE = 0x0003BBC0

# The cave. 0x456580..0x456FFF is the only usable zero run in .text; the
# statistics feature owns 0x456730..0x4567FF, so this claims the block above
# it and leaves 0x456900..0x456FFF free for whatever comes next.
CAVE_VA = 0x00456800
CAVE_FILE = 0x00056800
CAVE_SIZE = 0x100

# Imports, reused from the statistics feature's own verified table entries.
LOAD_LIBRARY_IAT = 0x00457010
GET_MODULE_HANDLE_IAT = 0x004570D0
GET_PROC_ADDRESS_IAT = 0x004570D4

DLL_NAME = b"VVFP Parentage Export.dll\0"
EXPORT_NAME = b"WriteParentageRecord\0"

# Where the two strings sit inside the cave block, clear of the code.
DLL_NAME_OFFSET = 0x80
EXPORT_NAME_OFFSET = 0xA0

# The five stock bytes the trampoline replaces, restored before returning.
STOLEN_BYTES = bytes.fromhex("578bf9e8d8e5ffff")


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoding, _ = engine.asm(source, address)
    return bytes(encoding)


def build() -> dict:
    source = (STOCK / EXE).read_bytes()
    if source[HOOK_FILE : HOOK_FILE + 5] != STOLEN_BYTES[:5]:
        raise RuntimeError(
            f"stock bytes at {HOOK_FILE:#x} are not the expected hook site"
        )
    if set(source[CAVE_FILE : CAVE_FILE + CAVE_SIZE]) != {0}:
        raise RuntimeError(f"cave at {CAVE_FILE:#x} is not free")

    dll_name_va = CAVE_VA + DLL_NAME_OFFSET
    export_name_va = CAVE_VA + EXPORT_NAME_OFFSET

    # The trampoline. Every register the stock routine relies on is preserved
    # with pushad/popad rather than by hand: the logging call is not on any
    # hot path (one conception at a time), so the few extra cycles buy immunity
    # from the whole class of clobber bugs.
    #
    # STACK ARITHMETIC, because two things here look wrong and are not.
    #
    # At entry esp holds the return address, so the three stock arguments sit
    # at +4 (mother index), +8 (father id) and +0xC. pushad then moves esp down
    # by 0x20, putting them at +0x24, +0x28 and +0x2C.
    #
    # 1. Both argument reads below are written `[esp + 0x2C]` yet fetch
    #    DIFFERENT values, because each push moves esp another 4 bytes:
    #        after `push 1`            0x2C - 0x04 = 0x28  -> father id
    #        after that push           0x2C - 0x08 = 0x24  -> mother index
    #    They are correct as written. Rewriting them to "matching" constants
    #    would break them.
    #
    # 2. The record array arrives in ecx, but ecx is caller-saved and the three
    #    loader calls above are free to destroy it -- so by this point the live
    #    register holds whatever GetProcAddress left behind, and pushing it
    #    would hand the DLL a garbage base to index records from. The original
    #    is in the pushad frame instead. pushad stores, from low address up:
    #    edi, esi, ebp, esp, ebx, edx, ecx, eax -- so the saved ecx is at
    #    post-pushad esp+0x18, which after the three pushes above reads as
    #    esp+0x24.
    code = assemble(
        f"""
            pushad
            push 0x{dll_name_va:X}
            call dword ptr [0x{GET_MODULE_HANDLE_IAT:X}]
            test eax, eax
            jne resolve_export
            push 0x{dll_name_va:X}
            call dword ptr [0x{LOAD_LIBRARY_IAT:X}]
            test eax, eax
            jz done
        resolve_export:
            push 0x{export_name_va:X}
            push eax
            call dword ptr [0x{GET_PROC_ADDRESS_IAT:X}]
            test eax, eax
            jz done
            # WriteParentageRecord(records, mother_index, father_id, babies).
            #
            # `babies` is 1 here on purpose. The engine picks twins and
            # triplets on branches that run AFTER this point and only then
            # writes record+0x35C, so reading that field now would report the
            # PREVIOUS pregnancy's litter size, or zero on the first. Logging
            # the value the engine has actually committed at this instant is
            # correct; claiming one it has not yet chosen would not be.
            push 1
            push dword ptr [esp + 0x2C]
            push dword ptr [esp + 0x2C]
            push dword ptr [esp + 0x24]
            call eax
        done:
            popad
            # Replay the stolen prologue, then rejoin the routine after it.
            push edi
            mov edi, ecx
            call 0x{0x0043A1A0:X}
            jmp 0x{HOOK_VA + len(STOLEN_BYTES):X}
        """,
        CAVE_VA,
    )
    if len(code) > DLL_NAME_OFFSET:
        raise RuntimeError(
            f"trampoline is {len(code):#x} bytes, over the {DLL_NAME_OFFSET:#x} allowance"
        )

    payload = bytearray(CAVE_SIZE)
    payload[: len(code)] = code
    payload[DLL_NAME_OFFSET : DLL_NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    payload[EXPORT_NAME_OFFSET : EXPORT_NAME_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME

    # The hook itself: jump to the trampoline, then pad the remainder of the
    # stolen instructions with nops so the routine's own byte layout is
    # unchanged for anything that lands mid-sequence.
    entry = assemble(f"jmp 0x{CAVE_VA:X}", HOOK_VA)
    entry = entry + b"\x90" * (len(STOLEN_BYTES) - len(entry))
    if len(entry) != len(STOLEN_BYTES):
        raise RuntimeError("hook entry does not match the stolen byte count")

    companion_hash = hashlib.sha256(COMPANION.read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "companion_sha256": companion_hash,
        "features": [
            {
                "id": "vv1_write_parentage_log",
                "game_id": "vv1",
                "name": "Write Parentage Log to Text File",
                "output_tag": "Parentage Log Text Export",
                "description": (
                    "On each new pregnancy, appends the mother's and father's "
                    "names, their ages at conception, their head and body "
                    "values, and the number of babies to "
                    "'Virtual Villagers 1 Parentage Log N.txt' beside the game "
                    "executable. Parentage is not stored in any villager "
                    "record, so both parents are captured at conception; they "
                    "cannot be recovered from the child afterwards. Rolls to a "
                    "new numbered file every 256 records."
                ),
                "companion_files": [
                    {
                        "source": "assets/parentage/VVFP Parentage Export.dll",
                        "destination": "VVFP Parentage Export.dll",
                        "sha256": companion_hash,
                    }
                ],
                "patches": [
                    {
                        "offset": HOOK_FILE,
                        "original": STOLEN_BYTES.hex(),
                        "bytes": entry.hex(),
                        "purpose": (
                            "Divert the head of the conception routine "
                            "sub_43BBC0 to the trampoline, which logs the "
                            "pregnancy and then replays these bytes."
                        ),
                    },
                    {
                        "offset": CAVE_FILE,
                        "original": ("00" * CAVE_SIZE),
                        "bytes": bytes(payload).hex(),
                        "purpose": (
                            "Loader trampoline plus the DLL and export names. "
                            "All logging logic lives in the companion DLL; "
                            "only the call into it is in the executable."
                        ),
                    },
                ],
            }
        ],
    }


def main() -> None:
    OUTPUT.write_text(
        json.dumps(build(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
