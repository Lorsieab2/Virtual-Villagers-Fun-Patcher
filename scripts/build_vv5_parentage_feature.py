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
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "inputs" / "vv5-stock-copy"
EXE = "Virtual Villagers - New Believers.exe"
COMPANION = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"
OUTPUT = ROOT / "data" / "vv5_parentage_feature.json"

GAME_ID = 5

# The conception call inside the role resolver, and the five bytes it occupies.
HOOK_VA = 0x00467DBE
HOOK_FILE = 0x00067DBE
HOOK_STOLEN = bytes.fromhex("e83de0ffff")
CONCEPTION_VA = 0x00465E00

# The appended page.  VV4's stock file ends at 0xE3000 and its last section
# (.rsrc) ends at VA 0x329000 + 0x15DE0, so 0x73F000 is the next 0x1000-aligned
# virtual address that is free.
STOCK_FILE_SIZE = 0x000F2000
APPEND_LENGTH = 0x1000
PAGE_VA = 0x007C9000
SECTION_NAME = ".vv5pl"

# Where the payload lives when Origins is ALSO selected.
#
# Only one feature may append per build: the append guard pins each layout to
# the file size it expects to start from, so a second appender fails whichever
# order they run in.  vv5_enable_origins_exclusive_features pulls in the
# .vv5t9 section (task 9 native actions), which appends 0x8000 bytes at the
# stock EOF, and the public vv5_origins_village_wide_upgrades depends on
# Origins, so a player selecting the village-wide upgrades reaches that append
# transitively.
#
# .vv5t9 is executable (characteristics 0x60000020) and uses 0x7A83 of its
# 0x8000, leaving a 0x57D zero tail.  The overlay therefore takes the
# 0x400-aligned window at file 0xF9C00 -- inside that tail, measured zero in
# every patch mode and with the village-wide upgrades also selected -- which
# maps to VA 0x7D0C00.  The payload's real footprint is 0x125 bytes: code to
# 0x4B, then the two loader strings.
#
# The destination is NOT page-aligned, and does not need to be: it is a tail
# inside a section that is already mapped executable, not a page of its own.
# The declared zero preimage is what proves the range was unclaimed, and the
# patcher re-checks it against the composed parent before writing.
#
# Re-emitted for that address rather than copied: the trampoline's rejoin and
# its call to the conception routine are both rel32, so moving the bytes
# without reassembling would leave each aimed at the wrong target.
OVERLAY_OFFSET = 0x000F9C00
OVERLAY_LENGTH = 0x400
OVERLAY_PAGE_VA = 0x007D0C00
ORIGINS_FEATURE_ID = "vv5_enable_origins_exclusive_features"

# PE header fields this append has to move, at VV4's own offsets.
NUMBER_OF_SECTIONS_FILE = 0xFE
NUMBER_OF_SECTIONS_BEFORE = 5
SIZE_OF_IMAGE_FILE = 0x148
SIZE_OF_IMAGE_BEFORE = 0x003C9000

# Imports, from the per-game table the shipping statistics companion already
# uses.  Verified against VV4's import directory rather than trusted: each slot
# resolves to the ASCII-variant name, which matters because the DLL name below
# is an ASCII string.
GET_MODULE_HANDLE_IAT = 0x004951D8
GET_PROC_ADDRESS_IAT = 0x004951DC
LOAD_LIBRARY_IAT = 0x004951E0

DLL_NAME = b"VVFP Parentage Export.dll\0"
EXPORT_NAME = b"WriteParentageRecord\0"

# Where the two strings sit inside the page, clear of the trampoline.
DLL_NAME_OFFSET = 0xF0
EXPORT_NAME_OFFSET = 0x110

# The villager record array's container, and the header the game's own accessor
# adds to reach record zero.  sub_466040 does:
#     cmp eax,0x95 ; imul eax,eax,0x2E3C ; lea eax,[eax+ecx+0x44] ; ret 4
# so the array begins at container+0x44 and the companion is told the container
# unbiased -- its layout row carries record_base 0x48 and applies it itself.
# All 55 callers of that accessor load the container as a literal, so it costs
# one instruction here and no register pressure.
RECORDS_CONTAINER_VA = 0x00554148

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


def _emit(source: bytes, page_va: int = PAGE_VA, page_len: int = APPEND_LENGTH) -> tuple[list[dict], bytes]:
    """Assemble the trampoline page and the hook rewrite."""

    if source[HOOK_FILE : HOOK_FILE + len(HOOK_STOLEN)] != HOOK_STOLEN:
        raise RuntimeError(
            f"stock bytes at {HOOK_FILE:#x} are not the expected conception call"
        )
    if len(source) != STOCK_FILE_SIZE:
        raise RuntimeError(
            f"stock file is {len(source):#x} bytes, expected {STOCK_FILE_SIZE:#x}"
        )

    dll_name_va = page_va + DLL_NAME_OFFSET
    export_name_va = page_va + EXPORT_NAME_OFFSET

    page = bytearray(page_len)

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
            # Read the suppression flag BEFORE the call: sub_45E7B0 cleans its
            # own seven arguments, so they do not exist afterwards.  ebx is
            # callee-saved and the resolver restores it in its epilogue, and
            # pushad/popad below preserves it across everything in between.
            mov ebx, dword ptr [esp + 0x{SUPPRESSION_ARG_DISPLACEMENT:X}]

            # The stolen call, performed first so the game's own behaviour is
            # unchanged whatever happens afterwards.
            call 0x{CONCEPTION_VA:X}

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

            # WriteParentageRecord(game_id, records, mother).  stdcall, so the
            # callee cleans its own 12 bytes and the frame stays balanced.
            # Pushed right to left: the mother first, then the container, then
            # the game id.  The container is passed UNBIASED -- the companion's
            # layout row carries record_base 0x48 and applies it itself, and a
            # pre-biased pointer would be rejected at slot zero.
            #
            # The mother is ebp.  pushad stores eax first and edi last, so from
            # esp the frame reads edi +0x00, esi +0x04, ebp +0x08, esp +0x0C,
            # ebx +0x10, edx +0x14, ecx +0x18, eax +0x1C.  An earlier draft
            # used +0x10 and would have passed ebx -- a plausible-looking
            # pointer that is not the mother, which the companion's boundary
            # guard would have rejected silently on every birth.
            push dword ptr [esp + 0x08]
            push 0x{RECORDS_CONTAINER_VA:X}
            push {GAME_ID}
            call eax
        done:
            popad
            ret
        """,
        page_va,
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
    entry = assemble(f"call 0x{page_va:X}", HOOK_VA)
    if len(entry) != len(HOOK_STOLEN):
        raise RuntimeError("hook entry does not match the stolen byte count")

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


def build() -> dict:
    source = (STOCK / EXE).read_bytes()
    patches, page = _emit(source)
    # The overlay page is generated a full 0x1000 long even though only the
    # first OVERLAY_LENGTH bytes are written.  _apply_composition_overlay
    # requires exactly that shape and checks the tail past OVERLAY_LENGTH is
    # zero, which is what proves nothing is written outside the reserved
    # window.  The payload is 0x125 bytes, so the tail is zero by construction.
    overlay_patches, overlay_page = _emit(
        source, OVERLAY_PAGE_VA, 0x1000
    )
    if len(overlay_page) != 0x1000 or any(overlay_page[OVERLAY_LENGTH:]):
        raise SystemExit(
            "overlay page must be 0x1000 bytes and zero past "
            f"0x{OVERLAY_LENGTH:X}"
        )

    companion_hash = hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper()
    page_hash = hashlib.sha256(page).hexdigest().upper()

    layout = {
        "original_file_size": f"0x{STOCK_FILE_SIZE:X}",
        "append_offset": f"0x{STOCK_FILE_SIZE:X}",
        "append_length": APPEND_LENGTH,
        "append_bytes": page.hex(),
        "page_virtual_address": f"0x{PAGE_VA:X}",
        "page_sha256": page_hash,
        "purpose": "append the owned VV5 parentage trampoline page",
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
                "id": "vv5_write_parentage_log",
                "game_id": "vv5",
                "name": "Write Parentage Log to Text File",
                "output_tag": "Parentage Log Text Export",
                "description": (
                    "On each new pregnancy, appends the mother's and father's "
                    "names, their ages at conception, their head and body "
                    "values, and the number of babies to "
                    "'Virtual Villagers 5 Parentage Log N.txt' beside the game "
                    "executable. Parentage is not stored in any villager "
                    "record, so both parents are captured at conception; they "
                    "cannot be recovered from the child afterwards. Village "
                    "seeding is excluded, so a new village does not write a "
                    "record for every starting villager. Rolls to a new "
                    "numbered file every 256 records."
                ),
                "companion_files": [
                    {
                        "source": "assets/parentage/VVFP Parentage Export.dll",
                        "destination": "VVFP Parentage Export.dll",
                        "sha256": companion_hash,
                    }
                ],
                "pe_append_transaction": {
                    "section": SECTION_NAME,
                    "composition_overlays": {
                        ORIGINS_FEATURE_ID: {
                            "base_feature": ORIGINS_FEATURE_ID,
                            "overlay_offset": f"0x{OVERLAY_OFFSET:X}",
                            "overlay_length": OVERLAY_LENGTH,
                            "page_virtual_address": f"0x{OVERLAY_PAGE_VA:X}",
                            "append_bytes": overlay_page.hex(),
                            "page_sha256": hashlib.sha256(overlay_page)
                            .hexdigest()
                            .upper(),
                            "overlay_preimage": {
                                "kind": "zero_fill",
                                "length": OVERLAY_LENGTH,
                                "sha256": hashlib.sha256(
                                    bytes(OVERLAY_LENGTH)
                                )
                                .hexdigest()
                                .upper(),
                            },
                            "hook_patches": overlay_patches,
                            "purpose": (
                                "place the parentage trampoline in the zero "
                                "window of the page Origins appends, so only "
                                "one feature appends in any build"
                            ),
                        }
                    },
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
