"""Add VV2's birth hook to its existing parentage feature.

WHY THIS EXISTS

The owner's requirement is that all five games ship the same log format. VV1
writes a `Birth` record for every child; VV2 writes none, so its Births and
Conceptions log carries only half of what its name promises. The owner's own
logs show it: VV1 with 3 conceptions and 3 correctly parented births, VV2 with
3 conceptions and none.

WHY IT EXTENDS THE PARENTAGE FEATURE RATHER THAN ADDING A NEW ONE

Births and conceptions are one log, written by one companion, produced by one
patch the player ticks. A separate manifest would also have to be registered
in PARENTAGE_FEATURES_PATHS -- and the comment there warns exactly what
happens if it is not: "the patcher discovers a feature only by reading its
manifest, so an unregistered one is not rejected, it is simply absent, and a
feature-composition test then passes without ever having seen it."

The patches are COMPOSITION patches keyed on Origins, like the conception
hook's, because the appended page they live in does not exist unless Origins
applies.

WHERE THE HOOKS GO

VV2 creates children at three call sites in one routine, guarded by the litter
count, which is 1, 2 or 3 in every game:

    call 0x44F5C0 @0x43BE8E  ->  splice 0x43BE93   the first child
    call 0x44CEC0 @0x43BEDF  ->  splice 0x43BEE4   the twin
    cmp [ecx+edi+0x544], 3                         the litter field
    call 0x44CEC0 @0x43BF2B  ->  splice 0x43BF30   the triplet

Each splice is the instruction AFTER the creating call, which is where VV1's
shipped birth hook splices: EAX holds the new child's record index there.

Those addresses were found by tracking the returned index through register
copies to its `imul <reg>,<reg>,0xE48C`, with VV1's four known splices as a
control -- the method had to rediscover them before its VV2 output was
believed -- and re-verified straight from the file bytes: the call opcode is
0xE8, its hand-decoded rel32 reproduces the target, and the splice is call+5.

THE REGISTER CONTRACT, identical at all three splices:

    ESI = the village object; [ESI+4] is the villager record array
    EDI = the mother's byte offset into that array
    EAX = the new child's record INDEX

corroborated by the game reading [edi+ebp+0x530] (age), [ecx+edi+0x544]
(litter) and [ecx+edi+0x540] (age at conception) right after these splices.

WHAT THE STUB PASSES: the game id and the child's record, nothing else. The
companion reads the child's own name, head, body, likes, dislikes and skills
from that record, and both parents from it too -- VV2 keeps them at +0x57D and
+0x596 for life. Extracting all that here would be forty-odd instructions of
hand-written assembly inside a byte budget.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables"
MANIFEST = ROOT / "data" / "vv2_parentage_feature.json"

EXE = "Virtual Villagers - The Lost Children.exe"
FEATURE_ID = "vv2_write_parentage_log"
ORIGINS_ID = "vv2_enable_origins_exclusive_features"
GAME_ID = 2
STRIDE = 0xE48C

APPEND_BASE_FILE = 0xB1000
APPEND_BASE_VA = 0x4B3000

# THE CAVE. The parentage cave ends at 0xB24D8 and the save-reset cave reserves
# 0x80 from there, so this starts at the reset's DECLARED end -- not at the
# first zero byte, which is earlier because the reset writes 98 of its 128
# reserved bytes and a later change may use the rest.
#
# Measured on an image rendered with every vv2 patch selected: 0xB2558..0xB3000
# is 2728 bytes, entirely zero.
CAVE_FILE = 0xB2558
CAVE_VA = APPEND_BASE_VA + (CAVE_FILE - APPEND_BASE_FILE)
CAVE_SIZE = 0x120

BODY_OFFSET = 0x00
DLL_NAME_OFFSET = 0x80
EXPORT_NAME_OFFSET = 0xB0
SITE_STUBS_OFFSET = 0xE0
SITE_STUB_SIZE = 0x11

DLL_NAME = b"VVFP Parentage Export.dll\0"
EXPORT_NAME = b"WriteParentageBirth\0"

LOAD_LIBRARY_IAT = 0x00474010
GET_MODULE_HANDLE_IAT = 0x004740D0
GET_PROC_ADDRESS_IAT = 0x004740D4

# The seven displaced bytes are identical at all three sites and were READ FROM
# THE STOCK FILE, not assumed: an earlier draft of this script had the first
# site as 8b5e04 and the file said otherwise.
#     8B 0E        mov ecx,[esi]
#     8B 6E 04     mov ebp,[esi+4]
#     8B D8        mov ebx,eax
DISPLACED = bytes.fromhex("8b0e8b6e048bd8")
SITES = (
    (0x0043BE93, "the first child of every birth"),
    (0x0043BEE4, "the twin"),
    (0x0043BF30, "the triplet"),
)


def assemble(source: str, address: int) -> bytes:
    from keystone import KS_ARCH_X86, KS_MODE_32, Ks

    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def rel32_call(source_va: int, target_va: int) -> bytes:
    return b"\xE8" + int(target_va - (source_va + 5)).to_bytes(4, "little", signed=True)


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - (source_va + 5)).to_bytes(4, "little", signed=True)


def _preimage() -> bytes:
    """The bytes this overlay replaces, from Origins' emitted page.

    Read from the page Origins emits rather than from the stock executable,
    because this address does not exist until Origins appends.

    THE MANIFEST'S FILLER IS NOT WHAT THE PATCHER SEES. Origins' append_bytes
    carry a repeating 0xD34D34 at the free offsets, but that is build-time
    scaffolding: by the time this overlay's byte guard runs, the region is
    ZEROS. Emitting the filler as `before` fails the guard at apply time with
    "expected 4D34D3..., found 000000...", which is exactly what happened on
    the first attempt here.

    So the region is checked against the filler -- confirming Origins still
    leaves it unclaimed -- and the emitted preimage is zeros, which is what
    the patcher will actually find.
    """
    origins = json.loads(
        (ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8")
    )
    layout = origins["pe_append_transaction"]["layouts"]["collection_progression"]
    append_offset = int(str(layout["append_offset"]), 0)
    page = base64.b64decode(layout["append_bytes"])

    start = CAVE_FILE - append_offset
    if start < 0 or start + CAVE_SIZE > len(page):
        raise RuntimeError(f"the birth cave {CAVE_FILE:#x} is outside Origins' page")
    region = page[start : start + CAVE_SIZE]

    filler = bytes.fromhex("4D34D3")
    expected = bytes(filler[i % len(filler)] for i in range(CAVE_SIZE))
    if region not in (bytes(CAVE_SIZE), expected):
        raise RuntimeError(
            f"the birth cave at {CAVE_FILE:#x} is neither zero nor the "
            f"build-time filler: something has claimed it"
        )
    return bytes(CAVE_SIZE)


def _payload() -> bytes:
    """One shared body, two strings, three site stubs."""
    body_va = CAVE_VA + BODY_OFFSET
    dll_va = CAVE_VA + DLL_NAME_OFFSET
    export_va = CAVE_VA + EXPORT_NAME_OFFSET

    # WriteParentageBirth(game_id, child_name, child_head, child_body,
    #                     mother_name, mother_head, mother_body,
    #                     father_name, father_head, father_body, child_record)
    #
    # Eleven stdcall arguments, right to left. Everything but the game id and
    # the record is NULL or -1; the companion reads the rest from the record.
    #
    # pushad stores edi, esi, ebp, esp, ebx, edx, ecx, eax from the low address
    # up, so saved esi is at [esp+0x04] and saved eax at [esp+0x1C]. Both are
    # read from the frame rather than live, because the three loader calls may
    # clobber caller-saved registers.
    body = assemble(
        f"""
            pushad
            push 0x{dll_va:X}
            call dword ptr [0x{GET_MODULE_HANDLE_IAT:X}]
            test eax, eax
            jne resolve_export
            push 0x{dll_va:X}
            call dword ptr [0x{LOAD_LIBRARY_IAT:X}]
            test eax, eax
            jz done
        resolve_export:
            push 0x{export_va:X}
            push eax
            call dword ptr [0x{GET_PROC_ADDRESS_IAT:X}]
            test eax, eax
            jz done
            mov esi, dword ptr [esp + 0x04]
            mov esi, dword ptr [esi + 4]
            mov ecx, dword ptr [esp + 0x1C]
            imul ecx, ecx, 0x{STRIDE:X}
            add ecx, esi
            push ecx
            push -1
            push -1
            push 0
            push -1
            push -1
            push 0
            push -1
            push -1
            push 0
            push {GAME_ID}
            call eax
        done:
            popad
            ret
        """,
        body_va,
    )
    if len(body) > DLL_NAME_OFFSET:
        raise RuntimeError(
            f"the birth body is {len(body):#x} bytes and runs into the DLL name"
        )

    payload = bytearray(CAVE_SIZE)
    payload[BODY_OFFSET : BODY_OFFSET + len(body)] = body
    payload[DLL_NAME_OFFSET : DLL_NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    payload[EXPORT_NAME_OFFSET : EXPORT_NAME_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME

    for index, (site_va, _what) in enumerate(SITES):
        offset = SITE_STUBS_OFFSET + index * SITE_STUB_SIZE
        stub_va = CAVE_VA + offset
        stub = (
            rel32_call(stub_va, body_va)
            + DISPLACED
            + rel32_jump(stub_va + 5 + len(DISPLACED), site_va + len(DISPLACED))
        )
        if len(stub) != SITE_STUB_SIZE:
            raise RuntimeError(f"stub {index} is {len(stub):#x} bytes")
        payload[offset : offset + len(stub)] = stub

    end = SITE_STUBS_OFFSET + len(SITES) * SITE_STUB_SIZE
    if end > CAVE_SIZE:
        raise RuntimeError(f"the cave needs {end:#x}, reserved {CAVE_SIZE:#x}")
    return bytes(payload)


def _patches(source: bytes) -> list[dict]:
    """The cave payload, then one rewrite per site."""
    entries = [
        {
            "offset": f"{CAVE_FILE:#x}",
            "before": _preimage().hex(),
            "after": _payload().hex(),
            "purpose": (
                "The birth hook: a shared body that resolves "
                "WriteParentageBirth once and hands it the game id and the "
                "new child's record, the companion and export name strings, "
                "and one stub per child-creation site"
            ),
        }
    ]
    for index, (site_va, what) in enumerate(SITES):
        file_offset = site_va - 0x400000
        actual = source[file_offset : file_offset + len(DISPLACED)]
        if actual != DISPLACED:
            raise RuntimeError(
                f"{what} at {site_va:#x}: stock bytes are {actual.hex()}, "
                f"expected {DISPLACED.hex()}"
            )
        stub_va = CAVE_VA + SITE_STUBS_OFFSET + index * SITE_STUB_SIZE
        # A five-byte jump leaves two of the seven displaced bytes behind,
        # which would execute as whatever they decode to; 0x90 makes the tail
        # an explicit no-op rather than a fragment.
        patched = rel32_jump(site_va, stub_va)
        patched += b"\x90" * (len(DISPLACED) - len(patched))
        entries.append(
            {
                "offset": f"{file_offset:#x}",
                "before": actual.hex(),
                "after": patched.hex(),
                "purpose": (
                    f"Divert {what} into its birth stub, which calls the "
                    f"companion, replays these seven bytes and returns to "
                    f"{site_va + len(DISPLACED):#x}"
                ),
            }
        )
    return entries


def main() -> None:
    source = (STOCK / EXE).read_bytes()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    feature = next(f for f in manifest["features"] if f["id"] == FEATURE_ID)
    composition = feature["composition_patches"][ORIGINS_ID]

    # Idempotent: drop any birth entries from a previous run before adding
    # this one's, so re-running does not stack duplicates.
    birth_offsets = {f"{CAVE_FILE:#x}"} | {
        f"{va - 0x400000:#x}" for va, _ in SITES
    }
    kept = [e for e in composition if e["offset"] not in birth_offsets]
    removed = len(composition) - len(kept)

    feature["composition_patches"][ORIGINS_ID] = kept + _patches(source)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"updated {MANIFEST.relative_to(ROOT)}")
    if removed:
        print(f"  replaced {removed} entries from a previous run")
    print(f"  cave {CAVE_FILE:#x} (VA {CAVE_VA:#x}), {CAVE_SIZE:#x} bytes")
    print(f"  {len(SITES)} site rewrites")
    print(f"  {len(feature['composition_patches'][ORIGINS_ID])} composition patches total")


if __name__ == "__main__":
    main()
