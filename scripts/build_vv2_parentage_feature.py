"""Emit the VV2 Parentage Tracker feature manifest.

WHERE THE HOOK GOES

sub_44B980 is VV2's conception routine. Its shape matters, because VV1's and
VV2's look alike and are not:

    0x44B980  push edi
    0x44B981  mov  edi, ecx           edi = the record ARRAY base (thiscall)
    0x44B983  call sub_44B310
    0x44B988  test al, al
    0x44B98A  je   0x44BAD9           the REJECTION
    0x44B990  mov  eax, [esp+8]       the mother's INDEX
    0x44B994  imul eax, eax, 0xE48C   the stride
    0x44B99A  push esi                pushed AFTER the rejection branch
    0x44B99B  lea  esi, [eax+edi]     esi = the MOTHER's record

Both pointers the companion needs are therefore live in registers, and neither
has to be recovered from a global the way VV3's does.

ONE HOOK, NOT THREE

The litter size is written late -- 2 at 0x44BA82, 3 at 0x44BAB6 -- so a hook at
the routine head reports a singleton for every twin and triplet birth. VV1 had
the same problem and needed three hooks at three separate success tails.

VV2 does not, because it genuinely converges:

    0x44BAD8   <- 0x44BA71, 0x44BA80, 0x44BAA5, 0x44BAB4, and fallthrough
    0x44BAD9   <- 0x44B98A only (the rejection)
    0x44BADA   no incoming branches

Established by branch-target query over the decoded routine, not by reading.
The four jcc are easy to mistake for "the singleton path" -- they are not.
0x44BA71 and 0x44BA80 exit before the twins write, so they mean one baby;
0x44BAA5 and 0x44BAB4 exit after it, so they mean two. Twins and triplets fall
through to 0x44BAD8 as well. Hooking those branches as if they were a separate
singleton tail would log twins and triplets twice each.

So: one hook at the common exit, reading the committed litter off the record.

THE STACK IS ASYMMETRIC, AND THAT IS WHAT MAKES ROOM

0x44BAD8 is `pop esi ; pop edi ; ret 0x1C`, five bytes -- exactly a jmp rel32.
But 0x44BAD9 is the rejection's target, one byte in, so overwriting all five
would land that jump mid-instruction and crash the game.

The rejection at 0x44B98A is a six-byte NEAR jcc, so its rel32 can be pointed
anywhere. Retargeting it to a stub frees 0x44BAD9, and the five bytes become
contiguous.

The stub does ONE pop, not two: esi is pushed at 0x44B99A, which is after the
rejection branch, so on the rejection path esi was never pushed. A symmetric
`pop esi ; pop edi ; ret 0x1C` there would unbalance the stack and return to
garbage.

THE LITTER FIELD IS READ, NOT ASSUMED

+0x544 is never written for a single birth, so 0 has to mean one baby. That is
only safe if the field is cleared per pregnancy rather than retaining the last
one, and it is -- the delivery routine zeroes it:

    0x43BF6E  xor eax, eax
    0x43BF85  mov [ecx+edi+0x544], eax

with villager creation zeroing it as well (0x44CDC8, 0x44D150, 0x44D479). So a
singleton conceived after a twin birth reads 0 and not a stale 2.

WHY THIS ONE APPENDS ITS OWN SECTION INSTEAD OF USING A CAVE

VV1's payload lives in a .text cave. VV2's cannot, and the reason is a measured
budget rather than a preference.

.text is VV2's only executable section (characteristics 0x60000020; .rdata,
.data, .shr and .rsrc are all non-exec, so a trampoline cannot live in any of
them). Its trailing slack is 0x3C0 bytes at 0x73C40, and eleven existing
features already claim most of it. Computing the true free gaps -- which means
handling `after`, `bytes`, `after_base64` and an explicit `length`, because a
scan that measures every claim as len(after)//2 silently reads
vv2_write_village_statistics's 0xD0-byte base64 claim as zero width and reports
its region free -- leaves:

    0x73F42  0xBE
    0x73DF4  0x2C

Two things need contiguous room there:

    this trampoline                 0xB1, or 0x3B stripped to the bone
    executable-name crash immunity  0xB2, sized from the PUBLISHED basename
                                    'Virtual Villagers - The Lost Children -
                                    Modded.exe'

0x3B + 0xB2 = 0xED against a largest run of 0xBE. They do not both fit, and the
loser is silent: the immunity pass returns status 'skipped', reason 'no code
cave', and the build still publishes. VV1 had 0xA80 of slack and never met
this; VV2 has 0x3C0.

So the payload leaves .text entirely and brings its own page. The one-append
guard permits exactly one appending feature per build, and VV2's only other one
is vv2_enable_origins_exclusive_features -- which is playtest-disabled and
refused alongside any other selection, so the slot is free in every composition
this feature can appear in.

The page carries its bytes inline via `append_bytes`, so it needs no generated
page builder and no entry in the owner-bound generated-source allowlist.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
COMPANION = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"
OUTPUT = ROOT / "data" / "vv2_parentage_feature.json"

EXE = "Virtual Villagers - The Lost Children.exe"

# The companion's per-game id. VV2 is 2.
GAME_ID = 2

IMAGE_BASE = 0x00400000

# The rejection branch: a six-byte near jcc whose rel32 is retargeted so that
# nothing else has to move. Its stolen bytes are the whole instruction.
REJECT_VA = 0x0044B98A
REJECT_FILE = 0x0004B98A
REJECT_STOLEN = bytes.fromhex("0F8449010000")

# The common exit. Five bytes: pop esi / pop edi / ret 0x1C.
EXIT_VA = 0x0044BAD8
EXIT_FILE = 0x0004BAD8
EXIT_STOLEN = bytes.fromhex("5E5FC21C00")

# The appended page. Stock VV2 is five sections ending at file 0xB1000, with
# SizeOfImage 0xB3000 and a free section header slot at 0x2B0.
STOCK_FILE_SIZE = 0x000B1000
PAGE_FILE = 0x000B1000
PAGE_VA = 0x004B3000
PAGE_SIZE = 0x1000
SECTION_NAME = b".vv2pl\0\0"

SECTION_COUNT_OFFSET = 0xF6
SECTION_COUNT_BEFORE = bytes.fromhex("0500")
SECTION_COUNT_AFTER = bytes.fromhex("0600")

SIZE_OF_IMAGE_OFFSET = 0x140
SIZE_OF_IMAGE_BEFORE = bytes.fromhex("00300B00")  # 0xB3000
SIZE_OF_IMAGE_AFTER = bytes.fromhex("00400B00")  # 0xB4000

SECTION_HEADER_OFFSET = 0x2B0

# Where the payload lives when Origins is ALSO selected.
#
# vv2_enable_origins_exclusive_features appends 8192 bytes at the same stock
# EOF and the append guard permits exactly one appending feature per build, so
# the two cannot both bring a page. Origins' block installs two sections, and
# only one of them can hold code:
#
#     .mtab  VA 0x4B3000  file 0xB1000  writable, NOT executable
#     .vvmk  VA 0x4B4000  file 0xB2000  executable
#
# Origins' own content ends at file 0xB241A, so the composed page carries a
# reserved zero run after it. The overlay applier requires a 0x400-aligned
# start, which puts the payload at file 0xB2800 / VA 0x4B4800 with 0x800
# available -- measured on the composed output, not on a manifest.
OVERLAY_FILE = 0x000B2800
OVERLAY_VA = 0x004B4800
OVERLAY_LENGTH = 0x400
ORIGINS_FEATURE_ID = "vv2_enable_origins_exclusive_features"

# Resolved from the stock import table rather than assumed: the DLL name below
# is ASCII, so these must be the A variants.
#     0x474010 -> KERNEL32.dll!LoadLibraryA
#     0x4740D0 -> KERNEL32.dll!GetModuleHandleA
#     0x4740D4 -> KERNEL32.dll!GetProcAddress
LOAD_LIBRARY_IAT = 0x00474010
GET_MODULE_HANDLE_IAT = 0x004740D0
GET_PROC_ADDRESS_IAT = 0x004740D4

DLL_NAME = b"VVFP Parentage Export.dll\0"
EXPORT_NAME = b"WriteParentageRecord\0"

# Layout inside the owned page. There is a whole 0x1000 here rather than the
# 0xBE a cave would have given, so the offsets are generous -- and the checks
# below still enforce them, because an earlier VV1 build ran its trampoline
# into its own DLL name string twice, and that decodes as plausible
# instructions rather than faulting.
DLL_NAME_OFFSET = 0x100
EXPORT_NAME_OFFSET = 0x140


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoding, _ = engine.asm(source, address)
    return bytes(encoding)


def _section_header() -> bytes:
    """The 40-byte header for the owned executable page."""
    header = bytearray(40)
    header[0:8] = SECTION_NAME
    header[8:12] = PAGE_SIZE.to_bytes(4, "little")  # VirtualSize
    header[12:16] = (PAGE_VA - IMAGE_BASE).to_bytes(4, "little")  # VirtualAddress
    header[16:20] = PAGE_SIZE.to_bytes(4, "little")  # SizeOfRawData
    header[20:24] = PAGE_FILE.to_bytes(4, "little")  # PointerToRawData
    # Characteristics: CODE | EXECUTE | READ. Deliberately not writable; the
    # page holds code and read-only strings, and nothing writes into it.
    header[36:40] = (0x60000020).to_bytes(4, "little")
    return bytes(header)


def _build_page(base_va: int = PAGE_VA, size: int = PAGE_SIZE) -> tuple[bytes, int]:
    """Assemble the trampoline, the rejection stub, and the two strings.

    `base_va` is a parameter because the payload has two homes and is
    RE-EMITTED for the second rather than copied: both hooks carry rel32
    displacements into this page, so relocating the bytes without reassembling
    would leave each jump short by the distance between the homes.
    """
    dll_name_va = base_va + DLL_NAME_OFFSET
    export_name_va = base_va + EXPORT_NAME_OFFSET

    # The page holds two entry points.
    #
    # reject_stub replays the rejection epilogue. ONE pop: esi is pushed at
    # 0x44B99A, after the branch that reaches here, so it is not on the stack.
    #
    # log_tail runs on every accepted conception. edi is the record array and
    # esi the mother, both still live. pushad/popad brackets the whole thing so
    # the loader calls may clobber freely, and the two pointers are read back
    # out of the pushad frame rather than from the live registers, because
    # those calls destroy caller-saved ones. pushad stores edi, esi, ebp, esp,
    # ebx, edx, ecx, eax from the low address up, so inside the handler saved
    # edi is at esp+0x00 and saved esi at esp+0x04 -- and each push below moves
    # esp again, which is why the two reads use the same displacement for two
    # different values.
    code = assemble(
        f"""
        log_tail:
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
            # callee cleans its own twelve bytes. Pushed right to left: the
            # mother first, then the array, then the game id.
            push dword ptr [esp + 0x04]
            push dword ptr [esp + 0x04]
            push {GAME_ID}
            call eax
        done:
            popad
            # Replay the stolen epilogue.
            pop esi
            pop edi
            ret 0x1C
        reject_stub:
            # The rejection path. esi was never pushed, so one pop only.
            pop edi
            ret 0x1C
        """,
        base_va,
    )
    if len(code) > DLL_NAME_OFFSET:
        raise RuntimeError(
            f"page code is {len(code):#x} bytes, over the {DLL_NAME_OFFSET:#x} allowance"
        )
    if EXPORT_NAME_OFFSET + len(EXPORT_NAME) > size:
        raise RuntimeError("strings do not fit inside the owned page")

    page = bytearray(size)
    page[: len(code)] = code
    page[DLL_NAME_OFFSET : DLL_NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    page[EXPORT_NAME_OFFSET : EXPORT_NAME_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME

    # reject_stub's address is whatever the assembler placed it at rather than
    # a guess. Its encoding is `pop edi` (0x5F) then `ret 0x1C`.
    stub_index = bytes(code).rindex(bytes.fromhex("5FC21C00"))
    return bytes(page), base_va + stub_index


def _hook_patches(page_va: int, reject_stub_va: int) -> list[dict[str, object]]:
    """The two hook rewrites, emitted for whichever page holds the payload."""
    # Retarget the rejection. Same six-byte near jcc, new rel32.
    reject_after = assemble(f"je 0x{reject_stub_va:X}", REJECT_VA)
    if len(reject_after) != len(REJECT_STOLEN):
        raise RuntimeError("retargeted rejection changed width")

    # Divert the common exit. A five-byte jmp replaces the five stolen bytes
    # exactly, so nothing downstream shifts.
    exit_after = assemble(f"jmp 0x{page_va:X}", EXIT_VA)
    if len(exit_after) != len(EXIT_STOLEN):
        raise RuntimeError("exit diversion does not match the stolen byte count")

    return [
        {
            "offset": f"0x{REJECT_FILE:X}",
            "before": REJECT_STOLEN.hex().upper(),
            "after": reject_after.hex().upper(),
            "purpose": (
                "Retarget the conception rejection branch to an equivalent "
                "stub, so the routine's five-byte epilogue becomes contiguous "
                "and can carry the log diversion. The stub pops one register, "
                "not two, because esi is pushed after this branch."
            ),
        },
        {
            "offset": f"0x{EXIT_FILE:X}",
            "before": EXIT_STOLEN.hex().upper(),
            "after": exit_after.hex().upper(),
            "purpose": (
                "Divert the single point every accepted conception reaches, "
                "past both litter writes, so the log records the committed "
                "number of babies and never a rejected conception."
            ),
        },
    ]


def _emit(source: bytes) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Assemble the page, the header changes, and the two hook rewrites."""
    if len(source) != STOCK_FILE_SIZE:
        raise RuntimeError(
            f"stock file is {len(source):#x} bytes, expected {STOCK_FILE_SIZE:#x}"
        )
    if source[REJECT_FILE : REJECT_FILE + len(REJECT_STOLEN)] != REJECT_STOLEN:
        raise RuntimeError(f"stock bytes at {REJECT_FILE:#x} are not the rejection jcc")
    if source[EXIT_FILE : EXIT_FILE + len(EXIT_STOLEN)] != EXIT_STOLEN:
        raise RuntimeError(f"stock bytes at {EXIT_FILE:#x} are not the routine epilogue")
    if source[SECTION_COUNT_OFFSET : SECTION_COUNT_OFFSET + 2] != SECTION_COUNT_BEFORE:
        raise RuntimeError("stock NumberOfSections is not 5")
    if source[SIZE_OF_IMAGE_OFFSET : SIZE_OF_IMAGE_OFFSET + 4] != SIZE_OF_IMAGE_BEFORE:
        raise RuntimeError("stock SizeOfImage is not 0xB3000")
    if set(source[SECTION_HEADER_OFFSET : SECTION_HEADER_OFFSET + 40]) != {0}:
        raise RuntimeError("the sixth section header slot is not free")

    page, reject_stub_va = _build_page()
    patches = _hook_patches(PAGE_VA, reject_stub_va)

    # The applier requires a full 0x1000 page whose bytes past overlay_length
    # are zero; only the first OVERLAY_LENGTH of it is written into the parent.
    overlay_page, overlay_stub_va = _build_page(OVERLAY_VA, PAGE_SIZE)
    overlay_patches = _hook_patches(OVERLAY_VA, overlay_stub_va)

    layout = {
        "original_file_size": f"0x{STOCK_FILE_SIZE:X}",
        "append_offset": f"0x{PAGE_FILE:X}",
        "append_length": PAGE_SIZE,
        "append_bytes": page.hex().upper(),
        "page_virtual_address": f"0x{PAGE_VA:X}",
        "page_sha256": hashlib.sha256(page).hexdigest().upper(),
        "purpose": (
            "append the owned VV2 parentage trampoline page, because VV2's "
            ".text slack cannot hold both this payload and the "
            "executable-name crash immunity reserve"
        ),
        "header_patches": [
            {
                "offset": f"0x{SECTION_COUNT_OFFSET:X}",
                "before": SECTION_COUNT_BEFORE.hex().upper(),
                "after": SECTION_COUNT_AFTER.hex().upper(),
                "purpose": "add the owned .vv2pl executable section",
            },
            {
                "offset": f"0x{SIZE_OF_IMAGE_OFFSET:X}",
                "before": SIZE_OF_IMAGE_BEFORE.hex().upper(),
                "after": SIZE_OF_IMAGE_AFTER.hex().upper(),
                "purpose": "extend SizeOfImage for the owned .vv2pl section",
            },
            {
                "offset": f"0x{SECTION_HEADER_OFFSET:X}",
                "before": ("00" * 40).upper(),
                "after": _section_header().hex().upper(),
                "purpose": "write the owned .vv2pl section header",
            },
        ],
    }

    # When Origins is co-selected it takes the single append slot, so parentage
    # overlays into the reserved zeros of Origins' own executable section
    # instead of appending. The page is re-emitted for that address rather than
    # copied, and the hooks travel with it.
    overlay = {
        "base_feature": ORIGINS_FEATURE_ID,
        "overlay_offset": f"0x{OVERLAY_FILE:X}",
        "overlay_length": OVERLAY_LENGTH,
        "page_virtual_address": f"0x{OVERLAY_VA:X}",
        "append_bytes": overlay_page.hex().upper(),
        "page_sha256": hashlib.sha256(overlay_page).hexdigest().upper(),
        "overlay_preimage": {
            "kind": "zero_fill",
            "length": OVERLAY_LENGTH,
            "sha256": hashlib.sha256(b"\x00" * OVERLAY_LENGTH).hexdigest().upper(),
        },
        "purpose": (
            "place the VV2 parentage trampoline in the reserved zero range of "
            "the executable section Origins appends, so both features compose "
            "without either losing its payload"
        ),
    }

    transaction = {
        "layouts": {
            mode: layout
            for mode in ("stock", "collection_progression", "immediate_fixed")
        },
        "composition_overlays": {ORIGINS_FEATURE_ID: overlay},
    }
    return patches, transaction, overlay_patches


def build() -> dict:
    source = (STOCK / EXE).read_bytes()
    patches, transaction, overlay_patches = _emit(source)

    companion_hash = hashlib.sha256(COMPANION.read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "companion_sha256": companion_hash,
        "features": [
            {
                "id": "vv2_write_parentage_log",
                "game_id": "vv2",
                "name": "Write Parentage Log to Text File",
                "output_tag": "Parentage Log Text Export",
                "description": (
                    "On each new pregnancy, appends the mother's and father's "
                    "names, their ages at conception, their head and body "
                    "values, and the number of babies to "
                    "'Virtual Villagers 2 Parentage Log N.txt' beside the game "
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
                "pe_append_transaction": transaction,
                "patches": patches,
                # The hooks aim at whichever page holds the payload, so the
                # co-selected form swaps them alongside the overlay above.
                "composition_patches": {ORIGINS_FEATURE_ID: overlay_patches},
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
