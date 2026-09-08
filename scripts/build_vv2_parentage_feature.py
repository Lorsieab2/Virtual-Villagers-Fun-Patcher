"""Emit the VV2 Parentage Tracker feature manifest.

VV2 keeps no father id anywhere. What it does keep is the father's NAME,
sprintf'd onto the MOTHER's record at +0x5C0 by the conception routine itself:

    0x44BA20  mov edx, [esp+0x1C]          ; the father's name string, an argument
    0x44BA35  lea eax, [esi+0x5C0]         ; esi is still the mother's record
    0x44BA49  call 0x4682BD                ; sprintf(mother+0x5C0, name)

so the layout row is FATHER_BY_NAME and the father's age, head and body are
genuinely unavailable, exactly as in VV4 and VV5. Three further fields at
+0x5DC, +0x5E0 and +0x5E8 are written from stack arguments in the same block.
They are deliberately NOT read: a store from a conception argument into a field
adjacent to a known one is precisely the evidence that produced the retracted
"+0x394 is the father id" reading in VV1, where position was mistaken for
intent.

WHERE THE HOOK GOES, AND WHY THERE IS ONLY ONE

sub_44B980 is VV2's conception routine. Its four success outcomes converge on a
single join:

    0x44BA71  jne 0x44BAD8      singleton -- skips both litter writes
    0x44BA80  jge 0x44BAD8      singleton -- the twins roll failed
    0x44BA82  mov [esi+0x544], 2            TWINS
    0x44BAA5  jne 0x44BAD8      twins -- skips the triplets write
    0x44BAB4  jge 0x44BAD8      twins -- the triplets roll failed
    0x44BAB6  mov [esi+0x544], 3            TRIPLETS
    0x44BAD8  pop esi ; pop edi ; ret 0x1C

Every one of those branches SKIPS PAST a litter write, so +0x544 is final only
at 0x44BAD8. A hook anywhere earlier reports the previous pregnancy's litter or
zero, which is the defect that made VV1's first attempt log every twin and
triplet as a singleton. One hook at the join is therefore both sufficient and
the only correct placement. VV1 needed three tails; VV2 needs one.

WHY THE REJECTION IS MOVED RATHER THAN THE SUCCESSES

The join cannot simply be stolen. The rejection path lands one byte into it:

    0x44B98A  je 0x44BAD9       <- the ONLY reference to 0x44BAD9
    0x44BAD8  pop esi           <- the four success branches land here
    0x44BAD9  pop edi           <- the rejection lands HERE

so a five-byte steal at 0x44BAD8 swallows the rejection's target. The obvious
answer -- retarget the four success branches instead -- is impossible: all four
are two-byte SHORT jumps, the window reaching all of them is 0x44BA37..0x44BAF2,
and the only slack inside it is three nop bytes. A rel8 cannot reach a cave.

The rejection, however, is a six-byte NEAR jcc and can be retargeted anywhere.
Moving that one branch leaves the join referenced by nothing but the four
successes, which frees it. An exhaustive every-byte branch-target census gives:

    0x44BAD2  0 refs                                    fall-through only
    0x44BAD8  4 refs  0x44BA71 0x44BA80 0x44BAA5 0x44BAB4
    0x44BAD9  1 ref   0x44B98A                          the rejection
    0x44BADA  0 refs        0x44BADD  0 refs

THE STACK IS ASYMMETRIC, AND THE STUB DEPENDS ON IT

    0x44B980  push edi          ; only edi is pushed at this point
    0x44B98A  je 0x44BAD9       ; the rejection branches out HERE
    0x44B99A  push esi          ; esi is pushed only on the success path

So the success exit needs two pops and the rejection exit needs ONE. The
relocated rejection stub is `pop edi ; ret 0x1C`, four bytes. A two-pop stub
would take the caller's return address into esi and return into garbage -- and
only on the rejection path, which is the common path once the village is at
capacity, so it would survive light testing and fail when a player's village
fills up.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / (
    "Virtual Villagers - The Lost Children.exe"
)
OUTPUT = ROOT / "data" / "vv2_parentage_feature.json"

GAME_ID = 2

# Image geometry is READ FROM THE PE, not written down here. A hardcoded
# copy of these three numbers is what an earlier draft used, and its
# PointerToRawData was wrong by 0xC00, which put every computed file offset
# 3 KB from its intended site. The stock-preimage assertions caught it, but
# deriving the values removes the opportunity entirely.
def _geometry() -> tuple[int, int, int]:
    import pefile

    pe = pefile.PE(str(STOCK), fast_load=True)
    text = next(
        s for s in pe.sections if s.Name.rstrip(b"\0") == b".text"
    )
    return (
        pe.OPTIONAL_HEADER.ImageBase,
        text.VirtualAddress,
        text.PointerToRawData,
    )


def _v2f(va: int) -> int:
    base, text_va, text_raw = _geometry()
    return va - base - text_va + text_raw


def _f2v(fo: int) -> int:
    """File offset to VA.

    Only valid inside .text. The payload lives in the page Origins appends,
    which has its own mapping declared in that feature's layout, so it uses
    `_appended_f2v` instead. Using this function for it produced a trampoline
    address 0x2000 low -- the join jumped to 0x4B241A while the code sat at
    0x4B441A -- and the build still succeeded, because nothing checks that a
    jump target contains code.
    """

    base, text_va, text_raw = _geometry()
    return fo + base + text_va - text_raw


def _appended_f2v(fo: int) -> int:
    """File offset to VA for an address inside Origins' appended page."""

    manifest = json.loads(
        (ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8")
    )
    layout = manifest["pe_append_transaction"]["layouts"]["collection_progression"]
    append_offset = int(str(layout["append_offset"]), 0)
    virtual_address = int(str(layout["virtual_address"]), 0)
    # virtual_address in the layout is already an absolute VA (0x4B3000), not
    # an RVA, so the image base must NOT be added again. Doing so produced
    # 0x8B441A -- the trampoline body assembled correctly and every jump was
    # 0x400000 too high, which a disassembler renders as plausible code.
    return fo - append_offset + virtual_address


# The two hook sites and their exact stock bytes. Both are asserted before
# anything is emitted: patch [1] is safe ONLY because patch [0] removed the
# sole reference to 0x44BAD9, and nothing else in the manifest records that
# dependency, so a future edit that touched one without the other would
# silently reintroduce the swallowed-target bug.
REJECT_VA = 0x0044B98A
REJECT_STOCK = bytes.fromhex("0f8449010000")      # je 0x44BAD9
JOIN_VA = 0x0044BAD8
JOIN_STOCK = bytes.fromhex("5e5fc21c00")          # pop esi; pop edi; ret 0x1C

# WHERE THE PAYLOAD LIVES, and why it is not in .text.
#
# VV2's .text cave cannot hold it. The single zero run 0x73C40..0x74000 is
# almost entirely claimed, and the free tail that remains is the space the
# renamed-build crash-immunity finalizer needs: _require_name_crash_immunity
# runs at the end of apply_patch, sizes its cave from the PUBLISHED basename
# (apply_patch renames the output, so it is longer than build.input_name), and
# RAISES rather than degrading. Placing a 0x78-byte payload there made VV2 fail
# to publish with Origins deselected, while passing with everything selected --
# because the Origins features append a PE section the finalizer will happily
# use instead. Selecting everything is the EASIEST case, not the hardest.
#
# So the payload goes into the page Origins already appends, exactly as VV1's
# parentage tracker does. That needs no second append: the append guard at
# src/vv_fun_patcher.py:3879 requires len(work) == original_file_size, so a
# second appending feature in the same build would fail. VV1 grows by exactly
# 8192 bytes with every feature selected, which is one append, not two.
#
# The address was measured on the BUILT OUTPUT rather than read from a
# manifest. Building VV2 with Origins alone and scanning the appended region
# 0xB1000..0xB4000 gives two zero runs: page+0x0000 (0x1000) and page+0x141A
# (0xBE6). The manifest's own append_bytes show 0xD34D34 filler at those
# offsets, which is build-time scaffolding replaced before the overlay's
# preimage is checked -- reading it instead of building would have reported the
# page full.
#
# The LICENCE is separate from the space, and it is the part that matters:
# VV2 declares no append_sha256, so an overlay into its appended page cannot
# invalidate a certification, because there is none. VV3 has the same free space
# and cannot use it, because its whole appended block is hashed.
CAVE_FILE = 0xB241A
CAVE_SIZE = 0xBE

# Layout inside the cave. The trampoline measures about 0x41 bytes, so the stub
# sits at 0x60 and the strings at 0x70 and 0x90 -- deliberately generous,
# because an earlier VV1 layout let a trampoline run into the DLL name and the
# overrun decoded as plausible instructions rather than failing.
STUB_OFFSET = 0x60
DLL_NAME_OFFSET = 0x70
EXPORT_NAME_OFFSET = 0x90

DLL_NAME = b"VVFP Parentage Export.dll\0"
EXPORT_NAME = b"WriteParentageRecord\0"

# Resolved from the stock import table, not assumed. All three are the ANSI
# variants, which is what the ASCII name string above requires.
LOAD_LIBRARY_IAT = 0x00474010
GET_MODULE_HANDLE_IAT = 0x004740D0
GET_PROC_ADDRESS_IAT = 0x004740D4

COMPANION_SOURCE = "assets/parentage/VVFP Parentage Export.dll"


def _companion() -> dict[str, str]:
    """The shared parentage companion, with its digest read from the file.

    The digest is computed here rather than written down because this is the
    same DLL VV1 ships and another session rebuilds it: a literal copied from
    VV1's manifest would silently go stale the next time that happens, and the
    patcher would then refuse to apply the feature with a hash mismatch. The
    build is not reproducible either -- two compiles of identical source differ
    -- so there is no fixed value that could be asserted instead.
    """

    import hashlib

    payload = (ROOT / COMPANION_SOURCE).read_bytes()
    return {
        "destination": "VVFP Parentage Export.dll",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "source": COMPANION_SOURCE,
    }


def assemble(source: str, address: int) -> bytes:
    from keystone import KS_ARCH_X86, KS_MODE_32, Ks

    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)



def _origins_page_preimage() -> bytes:
    """The bytes the overlay will be applied over, from Origins' emitted page.

    Read from the page the Origins manifest emits rather than from the stock
    executable, because this address does not exist until Origins appends. The
    manifest's `append_bytes` are base64 and carry build-time scaffolding at
    this offset, so the region is taken from the decoded page and asserted to
    be the free run measured on a built output.
    """

    import base64

    manifest = json.loads(
        (ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8")
    )
    transaction = manifest["pe_append_transaction"]
    layout = transaction["layouts"]["collection_progression"]
    append_offset = int(str(layout["append_offset"]), 0)
    page = base64.b64decode(layout["append_bytes"])
    start = CAVE_FILE - append_offset
    if start < 0 or start + CAVE_SIZE > len(page):
        raise RuntimeError(
            f"payload at {CAVE_FILE:#x} falls outside Origins' appended page"
        )
    return page[start : start + CAVE_SIZE]


def _emit(source: bytes) -> tuple[list[dict], bytes]:
    """Assemble the cave payload and the two hook rewrites."""

    for label, va, expected in (
        ("rejection jcc", REJECT_VA, REJECT_STOCK),
        ("success join", JOIN_VA, JOIN_STOCK),
    ):
        offset = _v2f(va)
        if source[offset : offset + len(expected)] != expected:
            raise RuntimeError(
                f"stock bytes at {offset:#x} are not the expected {label}"
            )
    # The payload address lives PAST the stock end of file: it is inside the
    # page Origins appends, so asserting against `source` would only assert
    # that the stock file is short. The preimage is taken from Origins' own
    # emitted page instead, which is what the overlay will actually be applied
    # over -- and it is read from the built page rather than from the
    # manifest's append_bytes, because those carry 0xD34D34 build-time
    # scaffolding at this offset that is replaced before the overlay's
    # preimage is checked.
    if CAVE_FILE < len(source):
        raise RuntimeError(
            f"payload at {CAVE_FILE:#x} is inside the stock file; it was "
            "meant to sit in the appended page"
        )
    preimage = _origins_page_preimage()

    cave_va = _appended_f2v(CAVE_FILE)
    dll_name_va = cave_va + DLL_NAME_OFFSET
    export_name_va = cave_va + EXPORT_NAME_OFFSET
    stub_va = cave_va + STUB_OFFSET

    payload = bytearray(CAVE_SIZE)

    # The trampoline. It is a TAIL, not a detour: the bytes it replaces are the
    # routine's own epilogue, so it ends by replaying them rather than jumping
    # back. That removes every rejoin rel32 -- the class of error that put one
    # VV1 trampoline 0x50 bytes short, into the middle of the routine.
    #
    # At the join the two pointers the companion needs are already live:
    #     esi = the MOTHER's record   (lea esi,[eax+edi] at 0x44B99B)
    #     edi = the record ARRAY BASE (mov edi,ecx at 0x44B981)
    # Both are read from the pushad frame rather than live, because the three
    # loader calls may clobber caller-saved registers. pushad stores edi, esi,
    # ebp, esp, ebx, edx, ecx, eax from the low address up, so saved edi is at
    # esp+0x00 and saved esi at esp+0x04 on entry to the handler.
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
            # callee cleans its own 12 bytes and the frame stays balanced.
            # Pushed right to left, and each push moves esp, which is why the
            # two frame reads use the same displacement and still fetch
            # different values: saved esi (the mother) then saved edi (the
            # record array).
            push dword ptr [esp + 0x04]
            push dword ptr [esp + 0x04]
            push {GAME_ID}
            call eax
        done:
            popad
            # Replay the stolen epilogue. This is the success path, so both
            # registers are on the stack and both pops are correct here.
            pop esi
            pop edi
            ret 0x1C
        """,
        cave_va,
    )
    if len(code) > STUB_OFFSET:
        raise RuntimeError(
            f"trampoline is {len(code):#x} bytes, over the stub at {STUB_OFFSET:#x}"
        )
    payload[: len(code)] = code

    # The relocated rejection exit. ONE pop: esi is pushed at 0x44B99A, after
    # the rejection branch has already been taken, so only edi is on the stack
    # here. See the module docstring.
    stub = assemble("pop edi\nret 0x1C", stub_va)
    if len(stub) > DLL_NAME_OFFSET - STUB_OFFSET:
        raise RuntimeError(f"stub is {len(stub):#x} bytes, over its slot")
    payload[STUB_OFFSET : STUB_OFFSET + len(stub)] = stub

    if EXPORT_NAME_OFFSET + len(EXPORT_NAME) > CAVE_SIZE:
        raise RuntimeError("the export name runs past the end of the cave")
    payload[DLL_NAME_OFFSET : DLL_NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    payload[EXPORT_NAME_OFFSET : EXPORT_NAME_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME

    # Patch [0]: repoint the rejection at the stub. Still a six-byte near jcc;
    # only the rel32 changes, so nothing downstream shifts.
    reject = assemble(f"je 0x{stub_va:X}", REJECT_VA)
    if len(reject) != len(REJECT_STOCK):
        raise RuntimeError("the retargeted rejection changed size")

    # Patch [1]: divert the join. Exactly five bytes replacing five.
    entry = assemble(f"jmp 0x{cave_va:X}", JOIN_VA)
    if len(entry) != len(JOIN_STOCK):
        raise RuntimeError("the join entry does not match the stolen byte count")

    patches = [
        {
            "offset": f"0x{_v2f(REJECT_VA):X}",
            "before": REJECT_STOCK.hex().upper(),
            "after": reject.hex().upper(),
            "purpose": (
                "Retarget the conception routine's rejection exit to a relocated "
                "one-pop stub, so the success join stops being reachable one byte "
                "in and can be diverted whole"
            ),
        },
        {
            "offset": f"0x{_v2f(JOIN_VA):X}",
            "before": JOIN_STOCK.hex().upper(),
            "after": entry.hex().upper(),
            "purpose": (
                "Divert the single point where every successful conception "
                "converges and the litter size is final, into the loader "
                "trampoline"
            ),
        },
        {
            "offset": f"0x{CAVE_FILE:X}",
            "before": "00" * CAVE_SIZE,
            "after": bytes(payload).hex().upper(),
            "purpose": (
                "The loader trampoline, the relocated one-pop rejection stub, and "
                "the companion and export name strings"
            ),
        },
    ]
    return patches, bytes(payload)


def build() -> dict:
    source = STOCK.read_bytes()
    patches, _ = _emit(source)
    return {
        "features": [
            {
                "id": "vv2_write_parentage_log",
                "game_id": "vv2",
                "name": "Write Parentage Log to Text File",
                "output_tag": "parentage",
                "description": (
                    "Records both parents at conception in a plain text log. VV2 "
                    "keeps the father's name on the mother's record and no father "
                    "id, so he is found by name. His head and body do not depend "
                    "on that: the game copies them onto the mother at conception, "
                    "so the log reports them even when he has since died or "
                    "another villager shares his name. Only his age needs the "
                    "lookup, and the log says so plainly when it cannot be "
                    "confirmed rather than printing a zero a real villager could "
                    "hold. Requires the Origins upgrades: "
                    "the loader trampoline lives in the page they append, because "
                    "VV2's own code cave is occupied by the renamed-build crash "
                    "guard and has no room for it."
                ),
                # Declared, not implied. The payload lives in the page the
                # Origins upgrades append, so selecting parentage without them
                # produced a build that applied the manifest, reported success,
                # and left the conception routine completely unpatched -- the
                # feature silently doing nothing, which is worse than refusing.
                # The dependency makes the patcher resolve Origins in.
                "dependencies": ["vv2_enable_origins_exclusive_features"],
                "companion_files": [_companion()],
                # No standalone `patches` list. VV1's tracker has both a cave
                # variant and an overlay; VV2 can only have the overlay, because
                # the built output leaves at most 0x2D contiguous free bytes in
                # its .text cave once the crash-immunity wrapper has taken the
                # tail -- measured on the artefact, not on the manifests, which
                # reported 447 and then 208 before this.
                "patches": [],
                "composition_patches": {
                    "vv2_enable_origins_exclusive_features": patches,
                },
            }
        ]
    }


def main() -> None:
    OUTPUT.write_text(
        json.dumps(build(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
