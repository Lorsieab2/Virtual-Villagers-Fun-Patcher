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

WHERE THE PAYLOAD LIVES, AND WHY TWO EARLIER ANSWERS WERE WRONG

The payload appends its own executable section rather than taking a cave,
because VV3's .text has no room -- and establishing that took two corrections
worth recording, since both are easy to repeat.

The first address, 0x7B664, was chosen by scanning the STOCK executable for a
run of zero bytes. It is zero there, and it is also inside 0x7B664..0x7B7F7,
which vv3_enable_origins_exclusive_features claims. Composing the two raised

    Patch overlap between feature:vv3_enable_origins_exclusive_features
                     and feature:vv3_write_parentage_log at 0x7B664

The stock file cannot answer "is this space free": a patcher's output is the
stock input plus every selected feature's bytes, so availability is a property
of a composition, not of the input.

The second address, 0x7BB8E, was chosen by scanning the COMPOSED output -- an
improvement that was still wrong, because a zero byte in a composed image only
means no feature in THAT composition wrote there. vv3_origins_village_wide_
upgrades claims 0x7B820..0x7BD40 and swallows it.

The reliable method is neither scan: enumerate every claim from the loaded
catalog, handling `after`, `bytes`, and `after_base64` with an explicit
`length` -- because computing a claim's size as len(after)//2 reads a
base64-encoded claim as zero width and reports an occupied region as free.
Doing that leaves exactly one unclaimed .text gap above the slack:

    0x7B2E0  0x60 bytes

against a 0xA0 payload. .text is VV3's only executable section (.rdata, .data,
.shr and .rsrc are all non-exec, .shr included despite being writable), so
there is nowhere else in the image to put code.

There is also a second occupant that appears in no manifest. The
executable-name crash-immunity reserve is allocated at PUBLISH time by
_nci_find_cave, which scans the composed bytes for the first zero run in an
executable section of at least need+4 bytes -- 0xB0 for VV3 -- and takes it. A
payload landing in that run does not crowd the reserve, it evicts it, and the
failure is silent: the finder returns None, publish records status "skipped",
reason "no code cave", and the build still ships without the crash immunity.
Appending sidesteps that contention entirely.

The page carries its bytes inline via `append_bytes`, so it needs no generated
page builder and no entry in the owner-bound generated-source allowlist.

CO-SELECTION WITH ORIGINS IS NOT YET SUPPORTED.

vv3_enable_origins_exclusive_features also appends, at the same stock EOF, and
the append guard permits exactly one appending feature per build. The only
mechanism that suppresses an append on co-selection is composition_overlays,
whose dispatch is hardcoded to VV1 Birth Control. VV3 additionally carries a
tail digest -- the only one in the project -- which asserts both that the file
ends at Origins' append and that the appended bytes hash to a certified value,
so writing into that page is refused as well.
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

# The appended page. Stock VV3 is five sections ending at file 0xCB000, with
# SizeOfImage 0x2DF000 and a free section header slot at 0x2C8.
STOCK_FILE_SIZE = 0x000CB000
PAGE_FILE = 0x000CB000
PAGE_VA = 0x006DF000
PAGE_SIZE = 0x1000
SECTION_NAME = b".vv3pl\0\0"

SECTION_COUNT_OFFSET = 0x10E
SECTION_COUNT_BEFORE = bytes.fromhex("0500")
SECTION_COUNT_AFTER = bytes.fromhex("0600")

SIZE_OF_IMAGE_OFFSET = 0x158
SIZE_OF_IMAGE_BEFORE = bytes.fromhex("00F02D00")  # 0x2DF000
SIZE_OF_IMAGE_AFTER = bytes.fromhex("00002E00")  # 0x2E0000

SECTION_HEADER_OFFSET = 0x2C8

IMAGE_BASE = 0x00400000

# Kept for the payload-size checks below; the page is 0x1000 but the code and
# strings must still fit where the offsets say they do.
CAVE_SIZE = 0xA0

# Where the payload lives when Origins is ALSO selected.
#
# vv3_enable_origins_exclusive_features appends 0x2000 bytes at the same stock
# EOF and installs two sections there:
#
#     .vv3mc  VA 0x6DF000  file 0xCB000  executable
#     .vv3md  VA 0x6E0000  file 0xCC000  writable data
#
# The append guard permits exactly one appending feature per build, so the two
# cannot both bring a page. Origins' own content ends at page-relative 0x3A0,
# leaving a reserved zero run; the applier requires a 0x400-aligned start,
# which puts the payload at file 0xCB400 / VA 0x6DF400.
OVERLAY_FILE = 0x000CB400
OVERLAY_VA = 0x006DF400
OVERLAY_LENGTH = 0x400
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


def _build_page(base_va: int = PAGE_VA) -> bytes:
    """Assemble the trampoline and the two strings for one base address.

    `base_va` is a parameter because the payload has two homes and is
    RE-EMITTED for the second rather than copied: the hook rewrite carries a
    rel32 into this page and the trampoline ends in a rel32 back into the
    conception routine, so relocating the bytes without reassembling would
    leave both jumps short by the distance between the homes.
    """
    cave_va = base_va
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

    page = bytearray(PAGE_SIZE)
    page[: len(code)] = code
    page[DLL_NAME_OFFSET : DLL_NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    page[EXPORT_NAME_OFFSET : EXPORT_NAME_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME
    return bytes(page)


def _hook_patches(page_va: int) -> list[dict[str, object]]:
    """The hook rewrite, emitted for whichever page holds the payload."""
    # Divert the hook: a five-byte jmp plus one nop replaces the six stolen
    # bytes exactly, so nothing downstream shifts.
    entry = assemble(f"jmp 0x{page_va:X}", HOOK_VA)
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
    ]


def _emit(
    source: bytes,
) -> tuple[list[dict[str, object]], dict[str, object], list[dict[str, object]]]:
    """Assemble both payload homes, the header changes, and the hook rewrites."""
    if len(source) != STOCK_FILE_SIZE:
        raise RuntimeError(
            f"stock file is {len(source):#x} bytes, expected {STOCK_FILE_SIZE:#x}"
        )
    if source[HOOK_FILE : HOOK_FILE + len(HOOK_STOLEN)] != HOOK_STOLEN:
        raise RuntimeError(f"stock bytes at {HOOK_FILE:#x} are not the expected hook")
    if source[SECTION_COUNT_OFFSET : SECTION_COUNT_OFFSET + 2] != SECTION_COUNT_BEFORE:
        raise RuntimeError("stock NumberOfSections is not 5")
    if source[SIZE_OF_IMAGE_OFFSET : SIZE_OF_IMAGE_OFFSET + 4] != SIZE_OF_IMAGE_BEFORE:
        raise RuntimeError("stock SizeOfImage is not 0x2DF000")
    if set(source[SECTION_HEADER_OFFSET : SECTION_HEADER_OFFSET + 40]) != {0}:
        raise RuntimeError("the sixth section header slot is not free")

    page = _build_page()
    patches = _hook_patches(PAGE_VA)

    overlay_page = _build_page(OVERLAY_VA)
    overlay_patches = _hook_patches(OVERLAY_VA)

    layout = {
        "original_file_size": f"0x{STOCK_FILE_SIZE:X}",
        "append_offset": f"0x{PAGE_FILE:X}",
        "append_length": PAGE_SIZE,
        "append_bytes": bytes(page).hex().upper(),
        "page_virtual_address": f"0x{PAGE_VA:X}",
        "page_sha256": hashlib.sha256(bytes(page)).hexdigest().upper(),
        "purpose": (
            "append the owned VV3 parentage trampoline page, because VV3's "
            ".text has one unclaimed 0x60 gap against a 0xA0 payload and is "
            "the game's only executable section"
        ),
        "header_patches": [
            {
                "offset": f"0x{SECTION_COUNT_OFFSET:X}",
                "before": SECTION_COUNT_BEFORE.hex().upper(),
                "after": SECTION_COUNT_AFTER.hex().upper(),
                "purpose": "add the owned .vv3pl executable section",
            },
            {
                "offset": f"0x{SIZE_OF_IMAGE_OFFSET:X}",
                "before": SIZE_OF_IMAGE_BEFORE.hex().upper(),
                "after": SIZE_OF_IMAGE_AFTER.hex().upper(),
                "purpose": "extend SizeOfImage for the owned .vv3pl section",
            },
            {
                "offset": f"0x{SECTION_HEADER_OFFSET:X}",
                "before": ("00" * 40).upper(),
                "after": _section_header().hex().upper(),
                "purpose": "write the owned .vv3pl section header",
            },
        ],
    }

    # When Origins is co-selected it takes the single append slot, so parentage
    # overlays into the reserved zeros of Origins' own executable section
    # instead of appending. The page is re-emitted for that address rather than
    # copied, and the hook travels with it.
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
            "place the VV3 parentage trampoline in the reserved zero range of "
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
                "pe_append_transaction": transaction,
                "patches": patches,
                # The hook aims at whichever page holds the payload, so the
                # co-selected form swaps it alongside the overlay above.
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
