"""Emit the VV4 Parentage Tracker feature manifest.

The hook records both parents at CONCEPTION, for the same reason VV1's does:
parentage is stored nowhere in a villager record.  VV4 keeps two name buffers
at record+0x1BC0 and record+0x1BD9, but those are written as a PAIR in one
block at 0x45F3B3 from two incoming string arguments -- they are the parents'
names copied ONTO a villager, not the villager's own name, and they are written
by the constructor rather than by conception.  The villager's own name is
record+0x1B9C.  So the parents' identities exist only while the conception
routine is running, and must be captured there.

WHERE THE HOOK GOES

sub_45E7B0 (VA 0x0045E7B0) is VV4's conception routine.  It was located from
the litter-size writes and the statistics increments it performs, which are
independently proven by the shipping statistics companion:

    record + 0x1C50   litter    1 at 0x45E87D, 3 at 0x45E8C0, 2 at 0x45E8D3
    dword_4D6E0C      triplets  add ,1 at 0x45E8CA
    dword_4D6E08      twins     add ,1 at 0x45E8DD

Exactly one function writes all of those.  That is the birth site by
construction rather than by resemblance.

The hook is NOT placed at that routine's head.  It is placed on the CALL to it
inside the role resolver sub_460990, at 0x00460A2E:

    0x460A09  mov edx,[esi+0x1BBC]     father BODY
    0x460A10  mov ecx,[esi+0x1BB8]     father HEAD
    0x460A1D  lea edx,[esi+0x1B9C]     father NAME
    0x460A2B  mov ecx, ebp             MOTHER record  (thiscall)
    0x460A2E  call sub_45E7B0          <-- the five bytes this feature steals

At the routine's head the father exists only as decomposed scalars pushed by
the caller, so his AGE is unreachable.  At the resolver's call site both
parents are live RECORD pointers -- ebp is the mother, esi is the father --
which is what makes every logged field readable from one place.

That site was validated before any byte was taken.  Using IDA's cross-reference
database rather than a linear sweep (a linear sweep desynchronises on embedded
data and reported zero incoming branches at an address that has three):

    every byte of 0x460A2E..0x460A32   0 non-flow code refs, 0 data refs
    resume 0x460A33                    0 non-flow code refs
    the call decodes as E8 7DDDFFFF -> 0x45E7B0, exactly 5 bytes

so nothing jumps into the stolen span or the resume, and no stored pointer or
jump-table entry aims at either.  The hook is also the last instruction before
the resolver's epilogue (pop edi/esi/ebp; retn 8), so register state at the
resume point is consumed only by that epilogue.

THE SUPPRESSION FLAG, WHICH IS NOT OPTIONAL

sub_45E7B0's last stack argument gates its statistics block.  Village seeding
calls it with that argument SET and a hardcoded father "Joey":

    sub_467B00 @ 0x467C15    seeding, suppression on

Every genuine conception passes it clear.  Without filtering on it, starting a
new village writes one bogus "Joey" record per starting villager -- permanently,
into a log whose whole premise is that parentage cannot be recovered afterwards,
and invisibly until someone starts a new game.  The trampoline therefore reads
that argument from the caller's frame and returns without logging when it is
set.

WHERE THE PAYLOAD LIVES

An appended section, not cave space.  Every executable zero run in VV4 large
enough to hold this payload is already claimed by another feature -- the claim
enumeration over load_fun_patches() finds no unclaimed run at any size -- and
the largest runs that LOOK free (.shr 0xCC511, .rdata 0xB7442) are inside
vv4_origins_village_wide_upgrades' 0xCC220 +1312 span or are non-executable.

Measuring the bytes is not enough to see this: a zero byte only means nothing
in THAT composition wrote there.  Only the declared-claim enumeration answers
it, and it says VV4 has nothing spare.

No VV4 feature declares pe_append_transaction, so the append slot is free and
this feature takes it.  Nothing else appends, so there is no composition to
declare either.

The geometry is derived from VV4's own headers rather than copied from another
game -- VV4 keeps NumberOfSections at file 0x106 and SizeOfImage at 0x150,
where VV5 keeps them at 0xFE and 0x148.  Copying VV5's offsets into VV4 would
write the section count over unrelated header bytes.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "inputs" / "vv4-stock-copy"
EXE = "Virtual Villagers - The Tree of Life.exe"
COMPANION = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"
# The tribe-delete stub resolves this at runtime; it ships alongside.
RESET_COMPANION = ROOT / "assets" / "save_reset" / "VVFP Save Reset.dll"
OUTPUT = ROOT / "data" / "vv4_parentage_feature.json"

GAME_ID = 4

# The conception call inside the role resolver, and the five bytes it occupies.
HOOK_VA = 0x00460A2E
HOOK_FILE = 0x00060A2E
HOOK_STOLEN = bytes.fromhex("e87dddffff")
CONCEPTION_VA = 0x0045E7B0

# The appended page.  VV4's stock file ends at 0xE3000 and its last section
# (.rsrc) ends at VA 0x329000 + 0x15DE0, so 0x73F000 is the next 0x1000-aligned
# virtual address that is free.
STOCK_FILE_SIZE = 0x000E3000
APPEND_LENGTH = 0x1000
PAGE_VA = 0x0073F000
SECTION_NAME = ".vv4pl"

# PE header fields this append has to move, at VV4's own offsets.
# The new section's own header, written into the zero slot that follows the
# stock section table.  Bumping NumberOfSections without writing this header
# leaves a zero-filled entry: the loader maps a zero-length section at the
# image base, the appended page is never mapped, and the hook's first call
# jumps to unmapped memory.  The slot is verified zero in the stock file, so
# the preimage below is exact.
SECTION_HEADER_FILE = 0x2C0
IMAGE_BASE = 0x400000
NUMBER_OF_SECTIONS_FILE = 0x106
NUMBER_OF_SECTIONS_BEFORE = 5
SIZE_OF_IMAGE_FILE = 0x150
SIZE_OF_IMAGE_BEFORE = 0x0033F000

# Imports, from the per-game table the shipping statistics companion already
# uses.  Verified against VV4's import directory rather than trusted: each slot
# resolves to the ASCII-variant name, which matters because the DLL name below
# is an ASCII string.
GET_MODULE_HANDLE_IAT = 0x0048A1D8
GET_PROC_ADDRESS_IAT = 0x0048A1DC
LOAD_LIBRARY_IAT = 0x0048A1E0

DLL_NAME = b"VVFP Parentage Export.dll\0"
# The four-argument entry point.  The three-argument
# WriteParentageRecord still exists in the companion and still behaves as
# it did, but these two games can do better than it allows: the conception
# routine holds BOTH parent records in registers, so the father's record
# can be handed over and his age, head and body reported for real instead
# of as "not recorded by this game".
EXPORT_NAME = b"WriteParentageRecordWithFather\0"

# Where the two strings sit inside the page, clear of the trampoline.
DLL_NAME_OFFSET = 0xF0
EXPORT_NAME_OFFSET = 0x110

# THE TRIBE-DELETE HOOK, sharing this page.
#
# The save-slot menu deletes a tribe by calling deleteSave through a `jmp`
# thunk with the RAW slot in edi. The game's OTHER caller of deleteSave is a
# save routine rotating backup generations, which passes slot + 0x14 -- so
# hooking the menu handler's own call reaches the reset and never ordinary
# play. See docs/start-over-reset-hook.md.
#
# Without this the patcher's per-slot state outlives the village: a new tribe
# started in a reused slot inherits the old one's masks, which is the bleed
# the owner reported. vv_reset_slot_state has always been correct and never
# ran, because save_reset.c was not compiled into any shipped companion until
# VVFP Save Reset.dll.
RESET_DLL_NAME = b"VVFP Save Reset.dll\0"
RESET_EXPORT_NAME = b"ResetDeletedTribe\0"
RESET_DLL_NAME_OFFSET = 0x130
RESET_EXPORT_NAME_OFFSET = 0x150
RESET_CODE_OFFSET = 0x170

RESET_HOOK_VA = 0x00418CD5
RESET_HOOK_FILE = 0x00018CD5
RESET_HOOK_STOLEN = bytes.fromhex("e8f6640000")
RESET_THUNK_VA = 0x0041F1D0


# The villager record array's container, and the header the game's own accessor
# adds to reach record zero.  sub_466040 does:
#     cmp eax,0x95 ; imul eax,eax,0x2E3C ; lea eax,[eax+ecx+0x44] ; ret 4
# so the array begins at container+0x44 and the companion is told the container
# unbiased -- its layout row carries record_base 0x44 and applies it itself.
# All 55 callers of that accessor load the container as a literal, so it costs
# one instruction here and no register pressure.
RECORDS_CONTAINER_VA = 0x0050E568

# The suppression argument.  sub_45E7B0 is __thiscall with seven stack dwords
# and cleans them itself (retn 1Ch), so they are GONE by the time the stolen
# call returns.  The flag therefore has to be read BEFORE that call, while the
# caller's pushes are still on the stack.
#
# The trampoline is entered by CALL, so at its first instruction:
#     [esp+0x00]  the trampoline's own return address (0x460A33)
#     [esp+0x04]  the first of the seven arguments
#     [esp+0x1C]  the seventh -- the suppression flag
#
# An earlier draft read it after the call, at a displacement into the pushad
# frame.  That address holds whatever the caller had above its arguments, not
# the flag, so seeding would not have been filtered and every new village would
# have written a record per starting villager.  Disassembling the emitted page
# is what exposed it; the source read plausibly.
SUPPRESSION_ARG_DISPLACEMENT = 0x1C


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoding, _ = engine.asm(source, address)
    return bytes(encoding)


def _emit(source: bytes) -> tuple[list[dict], bytes]:
    """Assemble the trampoline page and the hook rewrite."""

    if source[HOOK_FILE : HOOK_FILE + len(HOOK_STOLEN)] != HOOK_STOLEN:
        raise RuntimeError(
            f"stock bytes at {HOOK_FILE:#x} are not the expected conception call"
        )
    if len(source) != STOCK_FILE_SIZE:
        raise RuntimeError(
            f"stock file is {len(source):#x} bytes, expected {STOCK_FILE_SIZE:#x}"
        )

    dll_name_va = PAGE_VA + DLL_NAME_OFFSET
    export_name_va = PAGE_VA + EXPORT_NAME_OFFSET

    page = bytearray(APPEND_LENGTH)

    # The trampoline replaces the call, so it must perform that call itself and
    # then return to the instruction after it.  Both parents are live records
    # on entry: ebp is the mother, esi is the father.  They are read from the
    # pushad frame rather than live, because the three loader calls are free to
    # clobber caller-saved registers.
    #
    # pushad stores edi, esi, ebp, esp, ebx, edx, ecx, eax from low address up,
    # so inside the handler saved esi is at esp+0x14 and saved ebp at esp+0x10.
    code = assemble(
        f"""
            # THE TRAMPOLINE MUST IMPERSONATE sub_45E7B0, NOT WRAP IT.
            #
            # The hook replaces `call 0x45E7B0` at 0x460A2E, so the game's own
            # `call` has already pushed its return address by the time this
            # page runs.  An inner `call 0x45E7B0` pushes a SECOND one, and the
            # callee then starts with two return addresses below its arguments
            # and reads every one of them a dword high.
            #
            # VV4 crashed on startup exactly as VV5 did.  Its WER reports give
            # faults at RVA 0x7250C and 0x72594 -- the same two instructions in
            # the same MSVC string copy that VV5 faults in, 0x88 apart in both
            # games.  VV5's crash dump is what established the mechanism: the
            # frame showed the callee's "arg1" holding the game's own return
            # address, and strncpy faulting on a source pointer of 0x1, a
            # save-slot index read where a name pointer belongs.
            #
            # VV4's callee is the same shape as VV5's -- `push ebx`, then
            # `mov bl, [esp+0x20]`, ending `ret 0x1C` -- so the same defect
            # and the same correction apply.  This routine also builds the
            # save-slot name list, which is why a parentage patch produced a
            # startup crash rather than a conception-time one.
            #
            # sub_45E7B0 is __thiscall and ends in `ret 0x1C`: it cleans its
            # own seven arguments.  So this page has to honour the same
            # contract -- give the callee a frame of its own, and clean the
            # game's seven arguments itself on the way out.
            #
            # The seven arguments are re-pushed right to left.  Each push
            # lowers esp by four, which moves the next argument down into the
            # same displacement, so seven identical reads at +0x1C copy the
            # whole list in order.  +0x1C is also where the seventh argument
            # sits before any push, which is why the suppression flag is read
            # at the same displacement first.
            push dword ptr [esp + 0x{SUPPRESSION_ARG_DISPLACEMENT:X}]
            push dword ptr [esp + 0x{SUPPRESSION_ARG_DISPLACEMENT:X}]
            push dword ptr [esp + 0x{SUPPRESSION_ARG_DISPLACEMENT:X}]
            push dword ptr [esp + 0x{SUPPRESSION_ARG_DISPLACEMENT:X}]
            push dword ptr [esp + 0x{SUPPRESSION_ARG_DISPLACEMENT:X}]
            push dword ptr [esp + 0x{SUPPRESSION_ARG_DISPLACEMENT:X}]
            push dword ptr [esp + 0x{SUPPRESSION_ARG_DISPLACEMENT:X}]

            # ecx is the __thiscall `this` pointer.  The call site loads it at
            # the call site immediately before the hook, and the
            # seven pushes above do not touch it, so it arrives intact.
            call 0x{CONCEPTION_VA:X}

            # Save the caller's ebx, then read the suppression flag into it.
            #
            # BOTH happen after the callee returns, and that is deliberate.
            #
            # ebx is not dead across this call, which an earlier version of
            # this page assumed after looking only at the instructions
            # immediately following the hook.  The routine the hook sits in is
            # entered from a caller that keeps a live ebx across it and then
            # dereferences it -- `mov eax, [ebx+0x18]` -- before popping its
            # own saved copy.  Leaving the flag in ebx makes that a null
            # dereference whenever the flag is zero.  Codex caught this.
            #
            # Reading the flag afterwards is possible because this page cleans
            # the GAME's seven arguments itself: the callee popped only the
            # copies pushed above, so the originals are still in place here,
            # and the flag sits at the same displacement plus the four bytes
            # this push adds.  Nothing touches ebx or the stack across the
            # call, which is what the callee's esp-relative argument reads
            # require.
            push ebx
            mov ebx, dword ptr [esp + 0x{SUPPRESSION_ARG_DISPLACEMENT + 4:X}]

            pushad
            # Village seeding passes the suppression flag set, with a hardcoded
            # father.  Logging those would write one bogus record per starting
            # villager on every new game.
            test ebx, ebx
            jnz done

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

            # WriteParentageRecordWithFather(game_id, records, mother,
            # father).  stdcall, so the callee cleans its own 16 bytes and
            # the frame stays balanced.  Pushed right to left: the father
            # first, then the mother, then the container, then the game id.
            # The container is passed UNBIASED -- the companion's layout
            # row carries record_base 0x44 and applies it itself, and a
            # pre-biased pointer would be rejected at slot zero.
            #
            # pushad stores eax first and edi last, so from esp the frame
            # reads edi +0x00, esi +0x04, ebp +0x08, esp +0x0C, ebx +0x10,
            # edx +0x14, ecx +0x18, eax +0x1C.  An earlier draft used
            # +0x10 for the mother and would have passed ebx -- a
            # plausible-looking pointer that is not the mother, which the
            # companion's boundary guard would have rejected silently on
            # every birth.
            #
            # Both parents are live here.  The routine picks the roles at
            # its head: it tests [ecx + 0x1B90] and either sets ebp = ecx
            # with esi the partner, or ebp = esi and esi = ecx.  ebp is
            # the record carrying the litter count and the father's NAME,
            # which is what makes ebp the mother and esi the father.
            #
            # esi is passed as a hint, not as a trusted pointer.  The
            # companion validates it against the record array exactly as
            # it does the mother, rejects it if it is the mother herself
            # or an inactive slot, and falls back to the name-only text if
            # any of that fails -- so a wrong guess costs three fields,
            # never a wrong record.
            #
            # The father is read before the mother is pushed, so it uses
            # the raw frame offset; the mother is read one push later and
            # so needs 0x08 + 0x04.
            push dword ptr [esp + 0x04]
            push dword ptr [esp + 0x0C]
            push 0x{RECORDS_CONTAINER_VA:X}
            push {GAME_ID}
            call eax
        done:
            popad
            # Restore the caller's ebx.  This must follow popad, which would
            # otherwise put the suppression flag back into it.
            pop ebx

            # Clean the GAME's seven arguments, exactly as the routine this
            # page impersonates would have.  Returning with a bare `ret` would
            # leave 0x1C bytes of the caller's frame stranded.
            ret 0x{SUPPRESSION_ARG_DISPLACEMENT:X}
        """,
        PAGE_VA,
    )
    if len(code) > DLL_NAME_OFFSET:
        raise RuntimeError(
            f"trampoline is {len(code):#x} bytes and runs into the strings "
            f"at {DLL_NAME_OFFSET:#x}"
        )
    page[: len(code)] = code
    page[DLL_NAME_OFFSET : DLL_NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    page[EXPORT_NAME_OFFSET : EXPORT_NAME_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME

    # Divert the call: a five-byte call to the page replaces the five-byte call
    # to the conception routine exactly, so nothing downstream shifts.
    entry = assemble(f"call 0x{PAGE_VA:X}", HOOK_VA)
    if len(entry) != len(HOOK_STOLEN):
        raise RuntimeError("hook entry does not match the stolen byte count")

    # Origins owns the tribe-delete stub and hook now; see
    # scripts/build_vv4_origins_feature.py. Claiming the same bytes here too
    # would make uninstalling the parentage log strip a stub Origins still
    # needs, and Origins is what writes the per-slot mask files the reset
    # exists to sweep.

    patches = [
        {
            "offset": f"0x{HOOK_FILE:X}",
            "before": HOOK_STOLEN.hex(),
            "after": entry.hex(),
            "purpose": (
                "route the conception call through the parentage trampoline, "
                "which performs the original call and then records both parents"
            ),
        }
    ]
    return patches, bytes(page)


def _section_header() -> bytes:
    """Build the IMAGE_SECTION_HEADER for the appended parentage page.

    Code, executable and readable, sized to the single page that is appended.
    VirtualSize is kept equal to SizeOfRawData so the section describes exactly
    the bytes that exist and cannot overrun what is mapped after it.
    """
    name = SECTION_NAME.encode("ascii")
    if len(name) > 8:
        raise SystemExit(f"section name {SECTION_NAME!r} exceeds 8 bytes")
    header = struct.pack(
        "<8sIIIIIIHHI",
        name.ljust(8, bytes(1)),
        APPEND_LENGTH,            # VirtualSize
        PAGE_VA - IMAGE_BASE,     # VirtualAddress (RVA)
        APPEND_LENGTH,            # SizeOfRawData
        STOCK_FILE_SIZE,          # PointerToRawData
        0,                        # PointerToRelocations
        0,                        # PointerToLinenumbers
        0,                        # NumberOfRelocations
        0,                        # NumberOfLinenumbers
        0x60000020,               # CODE | EXECUTE | READ
    )
    if len(header) != 0x28:
        raise SystemExit("section header must be 0x28 bytes")
    return header


def build() -> dict:
    source = (STOCK / EXE).read_bytes()
    patches, page = _emit(source)

    companion_hash = hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper()

    reset_hash = hashlib.sha256(RESET_COMPANION.read_bytes()).hexdigest().upper()
    page_hash = hashlib.sha256(page).hexdigest().upper()

    layout = {
        "original_file_size": f"0x{STOCK_FILE_SIZE:X}",
        "append_offset": f"0x{STOCK_FILE_SIZE:X}",
        "append_length": APPEND_LENGTH,
        "append_bytes": page.hex(),
        "page_virtual_address": f"0x{PAGE_VA:X}",
        "page_sha256": page_hash,
        "purpose": "append the owned VV4 parentage trampoline page",
        "header_patches": [
            {
                "offset": f"0x{NUMBER_OF_SECTIONS_FILE:X}",
                "before": NUMBER_OF_SECTIONS_BEFORE.to_bytes(2, "little").hex(),
                "after": (NUMBER_OF_SECTIONS_BEFORE + 1)
                .to_bytes(2, "little")
                .hex(),
                "purpose": "count the appended parentage section",
            },
            {
                "offset": f"0x{SECTION_HEADER_FILE:X}",
                "before": "00" * 0x28,
                "after": _section_header().hex(),
                "purpose": "describe the appended parentage section",
            },
            {
                "offset": f"0x{SIZE_OF_IMAGE_FILE:X}",
                "before": SIZE_OF_IMAGE_BEFORE.to_bytes(4, "little").hex(),
                "after": (SIZE_OF_IMAGE_BEFORE + APPEND_LENGTH)
                .to_bytes(4, "little")
                .hex(),
                "purpose": "extend SizeOfImage for the appended parentage page",
            },
        ],
    }

    return {
        "schema_version": 1,
        "companion_sha256": companion_hash,
        "features": [
            {
                "id": "vv4_write_parentage_log",
                "game_id": "vv4",
                "name": "Write Births and Conceptions Log to Text File",
                "output_tag": "Births and Conceptions Log Text Export",
                "description": (
                    "On each new pregnancy, appends the mother's and father's "
                    "names, both parents' ages at conception, both head and "
                    "body values, both parents' likes and dislikes, and the "
                    "number of babies to "
                    "'Virtual Villagers 4 Births and Conceptions Log N.txt' beside the game "
                    "executable. Parentage is not stored in any villager "
                    "record, so both parents are captured at conception; they "
                    "cannot be recovered from the child afterwards. Village "
                    "seeding is excluded, so a new village does not write a "
                    "record for every starting villager. Rolls to a new "
                    "numbered file every 256 records. The game keeps only "
                    "the father's name on the mother's record. His HEAD and "
                    "BODY are copied onto her at conception, so the log "
                    "reads them from her record and they stay correct "
                    "even after he dies or another villager takes his "
                    "name. His AGE, which has no copy on her, is read from "
                    "his own record at conception -- the moment the engine "
                    "hands both parents to the hook -- so a normal birth "
                    "records his real age."
                ),
                "needs_on": [
                    {
                        "id": "vv4_write_village_statistics",
                        "for": (
                            "the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled)"
                        ),
                    },
                ],
                "companion_files": [
                    {
                        "source": "assets/parentage/VVFP Parentage Export.dll",
                        "destination": "VVFP Parentage Export.dll",
                        "sha256": companion_hash,
                    },
                    {
                        "source": "assets/save_reset/VVFP Save Reset.dll",
                        "destination": "VVFP Save Reset.dll",
                        "sha256": reset_hash,
                    },
                ],
                "pe_append_transaction": {
                    "section": SECTION_NAME,
                    "layouts": {
                        "stock": layout,
                        "collection_progression": layout,
                        "immediate_fixed": layout,
                    },
                },
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
