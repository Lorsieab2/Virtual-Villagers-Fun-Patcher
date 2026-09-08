"""Emit the VV3 Parentage Tracker feature manifest.

VV3 is the simplest of the five to hook and the reason is worth stating,
because the other games are not like this and copying VV3's shape would be
wrong.

WHERE THE HOOK GOES

sub_455AB0 is VV3's conception routine, located the same way VV1's was: from
the counter offsets the shipping statistics companion already reads, by finding
what increments them. It ends:

    0x455BDD  mov  dword ptr [esi+0xE90], 2    twins
    0x455BE7  inc  dword_5824C8
    0x455BED  mov  ecx, [esi+0xE90]            <- all three outcomes converge
    0x455BF3  add  dword_5824A8, ecx           <- THE HOOK
    0x455BF9  pop  esi                         <- the REJECTION lands here
    0x455BFA  retn 0x1C

0x455BF3 is the only address in the routine that is both past every litter
write and reached on success only. Established by xref rather than by reading:

    0x455BED   3 incoming branches (0x455B8E, 0x455B9D, 0x455BDB)
    0x455BF9   1 incoming branch  (0x455ABF) -- the REJECTION
    0x455BF3   ZERO incoming branches

That distinction is not visible to a linear disassembly sweep. One reported
0x455BED as having no incoming branches when it has three, because the sweep
desynchronised on embedded data and never decoded the jumps. Stealing six bytes
there would have broken all three. The xref query is the only method that
answers this question.

Because all three outcomes converge before the hook, VV3 needs ONE hook where
VV1 needed three. VV1's twins tail looked like a twins/single join and was not:
its predecessors all sat downstream of the litter write, so singletons bypassed
it entirely. VV3 genuinely joins first.

WHAT IS LIVE AT THE HOOK

    esi = the mother's record. VV3 passes it directly in ecx and parks it with
          `mov esi, ecx` at 0x455AB1 -- there is no stride multiply anywhere in
          the routine, which is why a stride scan finds nothing in VV3 and why a
          hook ported from VV1 or VV2 would read the wrong object.
    ecx = the FINAL litter size, just loaded from [esi+0xE90].

The companion takes an array base and a record, so the array base is
materialised from the global the game itself uses.

WHERE THE PAYLOAD LIVES

VV3's single .text cave is 0x47B254 length 0xDAC, and 0x9D0 of it belongs to
the two Origins features. So the answer differs by selection, exactly as it did
for VV1:

    parentage alone       0x99C free at 0x47B664 -- what this file emits
    parentage + Origins   the cave is full, and unlike VV1 there is no second
                          home available yet. See below.

CO-SELECTION WITH ORIGINS IS NOT YET SUPPORTED, deliberately.

VV1 solved the same collision by putting a second copy of the payload in the
zero tail of the R-X page Origins appends. That does not transfer to VV3: its
appended block carries an append_sha256 covering the WHOLE block, and the
patcher refuses the output if a single byte differs. Writing a payload into
that tail would invalidate an integrity check whose purpose is to protect
Origins own page, so weakening it to make room here would be the wrong trade.

VV1 has no such certification, which is the entire reason its approach worked
and this one cannot borrow it.

The remaining options -- extending VV3 certification to cover a parentage
region, or giving parentage its own appended section -- both touch machinery
that currently works, so they are the owner decision rather than an
assumption made here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
COMPANION = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"
OUTPUT = ROOT / "data" / "vv3_parentage_feature.json"

EXE = "Virtual Villagers - The Secret City.exe"

# The companion's per-game id. VV3 is 3.
GAME_ID = 3

# The hook. `add dword_5824A8, ecx`, six bytes, zero incoming branches.
HOOK_VA = 0x00455BF3
HOOK_FILE = 0x00055BF3
HOOK_STOLEN = bytes.fromhex("010DA8245800")

# Where control resumes: the routine's own epilogue, one instruction later.
RESUME_VA = 0x00455BF9

# The villager array base. VV3 reaches records through this global; the
# conception routine receives the mother's record directly and never touches
# the array, so the trampoline materialises the base itself.
RECORD_ARRAY_VA = 0x0059E110  # the container; the layout subtracts its 0x14 header

# Home when parentage is selected alone.
CAVE_VA = 0x0047B664
CAVE_FILE = 0x0007B664
CAVE_SIZE = 0xA0

# Home when Origins is also selected: the zero tail of the R-X page Origins
# appends as .vv3mc at VA 0x6DF000 / file 0xCB000. Its own code ends at +0x3A0.
CO_SELECTED_CAVE_VA = 0x006DF3A0
CO_SELECTED_CAVE_FILE = 0x000CB3A0
ORIGINS_FEATURE_ID = "vv3_enable_origins_exclusive_features"

# Resolved from the stock import table rather than assumed: the DLL name below
# is ASCII, so these must be the A variants.
#     0x47C124 -> KERNEL32.dll!LoadLibraryA
#     0x47C074 -> KERNEL32.dll!GetModuleHandleA
#     0x47C128 -> KERNEL32.dll!GetProcAddress
LOAD_LIBRARY_IAT = 0x0047C124
GET_MODULE_HANDLE_IAT = 0x0047C074
GET_PROC_ADDRESS_IAT = 0x0047C128

DLL_NAME = b"VVFP Parentage Export.dll\0"
EXPORT_NAME = b"WriteParentageRecord\0"

# The trampoline assembles to 0x48 bytes, so the strings start at 0x50 with
# headroom. The size check below is what enforces this -- it caught an
# earlier 0x40 that was too small rather than letting the code run into the
# DLL name, which is a failure that decodes as plausible instructions.
DLL_NAME_OFFSET = 0x50
EXPORT_NAME_OFFSET = 0x70


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoding, _ = engine.asm(source, address)
    return bytes(encoding)


def _emit(source: bytes, cave_va: int, cave_file: int) -> list[dict[str, object]]:
    """Assemble the trampoline and hook rewrite for one cave address."""
    if source[HOOK_FILE : HOOK_FILE + len(HOOK_STOLEN)] != HOOK_STOLEN:
        raise RuntimeError(
            f"stock bytes at {HOOK_FILE:#x} are not the expected hook"
        )
    if cave_file + CAVE_SIZE <= len(source):
        if set(source[cave_file : cave_file + CAVE_SIZE]) != {0}:
            raise RuntimeError(f"cave at {cave_file:#x} is not free")
    elif cave_file < len(source):
        raise RuntimeError(f"cave at {cave_file:#x} straddles the stock EOF")
    # Past the stock EOF the bytes do not exist yet: that address lives in a
    # page Origins appends, and the patcher checks that page when it applies
    # the composition. Asserting here would only assert the file is short.

    dll_name_va = cave_va + DLL_NAME_OFFSET
    export_name_va = cave_va + EXPORT_NAME_OFFSET

    # The trampoline.
    #
    # esi holds the mother's record and ecx the final litter size. Only esi is
    # needed -- the companion reads the litter off the record itself -- but the
    # stolen instruction consumes ecx, so it is replayed rather than folded in.
    #
    # pushad/popad brackets everything, so the loader calls may clobber freely.
    # The two pointers are read from the pushad frame rather than live, because
    # the loader calls destroy caller-saved registers: pushad stores edi, esi,
    # ebp, esp, ebx, edx, ecx, eax from low address up, so saved esi is at
    # esp+0x04 inside the handler.
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
            # WriteParentageRecord(game_id, records, mother). stdcall, so the
            # callee cleans its own twelve bytes. Pushed right to left, and the
            # mother comes from the pushad frame; the array base is a constant
            # because VV3 reaches records through a global rather than passing
            # one to the conception routine.
            push dword ptr [esp + 0x04]
            push 0x{RECORD_ARRAY_VA:X}
            push {GAME_ID}
            call eax
        done:
            popad
            # Replay the stolen add, then rejoin at the epilogue.
            add dword ptr [0x{0x005824A8:X}], ecx
            jmp 0x{RESUME_VA:X}
        """,
        cave_va,
    )
    if len(code) > DLL_NAME_OFFSET:
        raise RuntimeError(
            f"trampoline is {len(code):#x} bytes, over the {DLL_NAME_OFFSET:#x} allowance"
        )

    payload = bytearray(CAVE_SIZE)
    payload[: len(code)] = code
    payload[DLL_NAME_OFFSET : DLL_NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    payload[EXPORT_NAME_OFFSET : EXPORT_NAME_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME

    # Divert the hook: a five-byte jmp plus one nop replaces the six stolen
    # bytes exactly, so nothing downstream shifts.
    entry = assemble(f"jmp 0x{cave_va:X}", HOOK_VA)
    entry = entry + b"\x90" * (len(HOOK_STOLEN) - len(entry))
    if len(entry) != len(HOOK_STOLEN):
        raise RuntimeError("hook entry does not match the stolen byte count")

    return [
        {
            "offset": f"0x{HOOK_FILE:X}",
            "before": HOOK_STOLEN.hex().upper(),
            "after": entry.hex().upper(),
            "purpose": (
                "Divert the conception routine sub_455AB0 at the one address "
                "past every litter write that is reached on success only, so "
                "the log records the committed litter size and never a "
                "rejected conception."
            ),
        },
        {
            "offset": f"0x{cave_file:X}",
            "before": ("00" * CAVE_SIZE).upper(),
            "after": bytes(payload).hex().upper(),
            "purpose": (
                "Loader trampoline plus the DLL and export names. All logging "
                "logic lives in the companion DLL; only the call into it is in "
                "the executable."
            ),
        },
    ]


def build() -> dict:
    source = (STOCK / EXE).read_bytes()
    patches = _emit(source, CAVE_VA, CAVE_FILE)

    companion_hash = hashlib.sha256(COMPANION.read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "companion_sha256": companion_hash,
        "features": [
            {
                "id": "vv3_write_parentage_log",
                "game_id": "vv3",
                "name": "Write Parentage Log to Text File",
                "output_tag": "Parentage Log Text Export",
                "description": (
                    "On each new pregnancy, appends the mother's and father's "
                    "names, their ages at conception, their head and body "
                    "values, and the number of babies to "
                    "'Virtual Villagers 3 Parentage Log N.txt' beside the game "
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
                "patches": patches,
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
