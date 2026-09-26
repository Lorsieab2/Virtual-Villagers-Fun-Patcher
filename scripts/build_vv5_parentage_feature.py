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
STOCK = ROOT / "inputs" / "vv5-stock-copy"
EXE = "Virtual Villagers - New Believers.exe"
COMPANION = ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"
# The tribe-delete stub resolves this at runtime; it ships alongside.
RESET_COMPANION = ROOT / "assets" / "save_reset" / "VVFP Save Reset.dll"
OUTPUT = ROOT / "data" / "vv5_parentage_feature.json"

GAME_ID = 5

# The conception call inside the role resolver, and the five bytes it occupies.
# THE HOOK SITS AT THE CONCEPTION ROUTINE'S SUCCESS EXIT, NOT AT ONE CALL SITE.
#
# It used to replace one `call` to the routine -- the role resolver's -- so
# only that path was logged. The routine has four callers:
#     0x467DBE (the player's drop and the role resolver), 0x46E16B and 0x46E19B (the two gender branches of autonomous embracing), and 0x471B6D (village seeding, suppression set).
# The owner's requirement is that every way a villager conceives is logged:
# autonomous embracing, the player dropping one villager on another, time
# catch-up, and island events. Every one of them starts the pregnancy in this
# routine: it is the only code in the executable that writes the pregnancy
# fields (due, father name, the father's head/body copies, litter) -- verified
# by enumerating every writer of those offsets in the stock image. So the
# routine is the one place that sees them all.
#
# 0x465F34 is reached only after the litter size is final (all three
# litter outcomes converge there) and never by the capacity rejection, which
# jumps straight to 0x465F44. No branch or stored pointer targets
# any byte of the ten stolen here (checked over the whole .text and image).
# The stolen bytes are `test bl,bl / jne 0x465F44 / mov ecx,[esi+0x1C50]`,
# replayed verbatim before resuming at 0x465F3E.
HOOK_VA = 0x00465F34
HOOK_FILE = 0x00065F34
HOOK_STOLEN = bytes.fromhex("84db750c8b8e501c0000")
HOOK_REJECT_VA = 0x00465F44
HOOK_RESUME_VA = 0x00465F3E
# The routine's father-NAME argument. Every caller that has the father's record
# passes `lea reg, [father + 0x1B9C]` -- the name inside his record, which the
# routine copies onto the mother -- so his record is this argument minus 0x1B9C.
# At the exit the routine's own `push ebx; push esi` are the only things above
# its return address, so the argument is at [esp+0x18] there, the same slot the
# routine reads it from when it copies the name.
FATHER_NAME_ARG_AT_TAIL = 0x18
FATHER_NAME_OFFSET = 0x1B9C
CONCEPTION_VA = 0x00465E00
# sub_465E00 adds the accepted litter size here at 0x465F3E. Its early
# capacity-check exit at 0x465E18 does not touch this counter.
CONCEPTION_TOTAL_VA = 0x0051D360

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
# The new section's own header, written into the zero slot that follows the
# stock section table.  Bumping NumberOfSections without writing this header
# leaves a zero-filled entry: the loader maps a zero-length section at the
# image base, the appended page is never mapped, and the hook's first call
# jumps to unmapped memory.  The slot is verified zero in the stock file, so
# the preimage below is exact.
SECTION_HEADER_FILE = 0x2B8
IMAGE_BASE = 0x400000
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
# thunk, with the RAW slot in edi. The game's OTHER caller of deleteSave is a
# save routine rotating backup generations, which passes slot + 0x14 -- so
# hooking the menu handler's own call reaches the reset and never ordinary
# play. See docs/start-over-reset-hook.md.
#
# Without this the patcher's per-slot state outlives the village: a new tribe
# started in a reused slot inherits the old one's masks, which is the bleed
# the owner reported. vv_reset_slot_state has always been correct and has
# never run, because save_reset.c was not compiled into any shipped
# companion until VVFP Save Reset.dll.
RESET_DLL_NAME = b"VVFP Save Reset.dll\0"
RESET_EXPORT_NAME = b"ResetDeletedTribe\0"
RESET_DLL_NAME_OFFSET = 0x130
RESET_EXPORT_NAME_OFFSET = 0x150
RESET_CODE_OFFSET = 0x170

RESET_HOOK_VA = 0x004193F5
RESET_HOOK_FILE = 0x000193F5
RESET_HOOK_STOLEN = bytes.fromhex("e896b20000")
RESET_THUNK_VA = 0x00424690

# The villager record array's container, and the header the game's own accessor
# adds to reach record zero.  sub_466040 does:
#     cmp eax,0x95 ; imul eax,eax,0x2E3C ; lea eax,[eax+ecx+0x44] ; ret 4
# so the array begins at container+0x44 and the companion is told the container
# unbiased -- its layout row carries record_base 0x48 and applies it itself.
# All 55 callers of that accessor load the container as a literal, so it costs
# one instruction here and no register pressure.
RECORDS_CONTAINER_VA = 0x00554148

# The suppression argument. sub_465E00 is __thiscall with seven stack dwords
# and cleans them itself (retn 1Ch). The trampoline passes COPIES of the
# caller's arguments to that call; the originals remain above its return
# address, so the flag can be read after the game routine returns.
#
# The trampoline is entered by CALL, so at its first instruction:
#     [esp+0x00]  the trampoline's own return address (0x467DC3)
#     [esp+0x04]  the first of the seven arguments
#     [esp+0x1C]  the seventh -- the suppression flag
#
# An earlier draft read it from the wrong pushad-frame displacement. That
# address holds whatever the caller had above its arguments, not the flag, so
# seeding would not have been filtered. The current code reads the original
# seventh argument after saving ebx; its displacement is +0x20 at that point.
SUPPRESSION_ARG_DISPLACEMENT = 0x1C



# THE BIRTH HOOK.
#
# The conception hook above records the parents when a pregnancy
# starts. This records the CHILD when it is born, so the Births and
# Conceptions log carries both halves of what its name promises --
# the owner's requirement that all five games ship the same log
# format, which VV1 already meets and this game did not.
#
# One stub per child-creation site, all calling a shared body. The
# splices are the instruction AFTER each creating call, which is
# where VV1's shipped birth hook splices too: the new child's record
# INDEX is in EAX there.
#
# The addresses were found by tracking that index through register
# copies to its `imul <reg>,<reg>,<stride>`, with VV1's four known
# splices used as a control -- the method had to rediscover them
# before this game's output was believed -- and then re-verified from
# the file bytes: 0xE8 opcode, hand-decoded rel32 reproducing the
# target, splice at call+5.
#
# THE DISPLACED BYTES ARE NOT UNIFORM. The destination register
# varies, and the triplet site needs eight bytes rather than five
# because a five-byte jump would land inside an imul. They are read
# from the stock file and checked against it at build time.
BIRTH_SITES = (
    (0x00473125, bytes.fromhex("8bf883ffff"), "the first child of every birth"),
    (0x004731C4, bytes.fromhex("8be883fdff"), "the twin"),
    (0x0047325F, bytes.fromhex("8bf869c0442f0000"), "the triplet"),
)
BIRTH_EXPORT_NAME = b"WriteParentageBirth\0"
# The child's record, for a game whose ESI points into the MOTHER's
# record rather than at a village object, so [ESI+4] is meaningless:
#     records container + record base + index * stride
BIRTH_RECORD_BASE = 0x48
BIRTH_STRIDE = 0x2F44
BIRTH_RECORDS_VA = 0x00554148
# Placed after the reset block, in the filler tail this page already
# carries. Measured on the emitted page rather than assumed.
BIRTH_BODY_OFFSET = 0x201
BIRTH_EXPORT_NAME_OFFSET = 0x261
BIRTH_STUBS_OFFSET = 0x275
# Sized for the LONGEST site. The triplet replays eight displaced
# bytes rather than five, so 5 (call) + 8 (replay) + 5 (jump) = 0x12.
BIRTH_STUB_SIZE = 0x12

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
    # The trampoline is entered by a JMP from the routine's success exit, so it
    # runs inside the routine's own frame: esi is the mother (`mov esi, ecx`
    # at the routine's head, and the record the father's name was copied onto),
    # bl is the suppression flag the routine loaded from its seventh argument,
    # and the father's name argument is at [esp+FATHER_NAME_ARG_AT_TAIL].
    # pushad adds 0x20 to that. It ends by replaying the stolen bytes and
    # jumping back, so the routine finishes exactly as it would have.
    code = assemble(
        f"""
            pushad
            # Village seeding passes the suppression flag set, with a hardcoded
            # father; logging it would write one bogus record per starting
            # villager on every new game.
            test bl, bl
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

            # The father: his name argument minus the name's offset inside
            # his record. A name that is not inside a record -- a literal
            # string -- is refused by the companion's slot check, and so is
            # the mother herself; either way nothing is scanned for.
            mov edx, dword ptr [esp + 0x{0x20 + FATHER_NAME_ARG_AT_TAIL:X}]
            test edx, edx
            jz have_father
            sub edx, 0x{FATHER_NAME_OFFSET:X}
        have_father:
            # WriteParentageRecordWithFather(game_id, container, mother,
            # father), stdcall. The mother is the pushad copy of esi, read
            # one push later (+0x04 + 0x04). The container is passed
            # unbiased; the companion's layout row applies record_base.
            push edx
            push dword ptr [esp + 0x08]
            push 0x{RECORDS_CONTAINER_VA:X}
            push {GAME_ID}
            call eax
        done:
            popad
            # The stolen bytes, replayed.
            test bl, bl
            jne 0x{HOOK_REJECT_VA:X}
            mov ecx, dword ptr [esi + 0x1C50]
            jmp 0x{HOOK_RESUME_VA:X}
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
    # A five-byte jump into the page, padded with NOPs to the ten stolen bytes
    # so the whole span decodes cleanly.
    entry = assemble(f"jmp 0x{page_va:X}", HOOK_VA)
    entry += b"\x90" * (len(HOOK_STOLEN) - len(entry))
    if len(entry) != len(HOOK_STOLEN):
        raise RuntimeError("hook entry does not match the stolen byte count")

    # Origins owns the tribe-delete stub and hook now; see
    # scripts/build_vv5_origins_feature.py. Claiming the same bytes here too
    # would make uninstalling the parentage log strip a stub Origins still
    # needs, and Origins is what writes the per-slot mask files the reset
    # exists to sweep.

    patches = [
        {
            "offset": f"0x{HOOK_FILE:X}",
            "before": HOOK_STOLEN.hex(),
            "after": entry.hex(),
            "purpose": (
                "divert the conception routine's success exit -- reached by every accepted "
                "conception on every path, and never by the capacity rejection -- into "
                "the parentage trampoline, which records both parents and resumes"
            ),
        },
    ]

    # ---- THE BIRTH HOOK -------------------------------------------------
    #
    # A shared body plus one stub per child-creation site. The body hands
    # the companion the game id and the new child's record; the companion
    # reads the child's own name, head, body, likes, dislikes and skills
    # from that record, and both parents from it too, so there is nothing
    # for this stub to extract.
    # page_va, NOT the PAGE_VA constant: _emit is called twice, once for the
    # plain page and once for the overlay at OVERLAY_PAGE_VA. Using the
    # constant emitted overlay stubs pointing at the plain page, so the
    # shipped artifact's stubs called into zeros.
    birth_body_va = page_va + BIRTH_BODY_OFFSET
    birth_export_va = page_va + BIRTH_EXPORT_NAME_OFFSET
    birth_body = assemble(
        f"""
            pushad
            push 0x{dll_name_va:X}
            call dword ptr [0x{GET_MODULE_HANDLE_IAT:X}]
            test eax, eax
            jne birth_resolve
            push 0x{dll_name_va:X}
            call dword ptr [0x{LOAD_LIBRARY_IAT:X}]
            test eax, eax
            jz birth_done
        birth_resolve:
            push 0x{birth_export_va:X}
            push eax
            call dword ptr [0x{GET_PROC_ADDRESS_IAT:X}]
            test eax, eax
            jz birth_done
            mov ecx, dword ptr [esp + 0x1C]
            # THE CHILD MAY NEVER HAVE BEEN ALLOCATED.
            #
            # The game's own handling of that is the `cmp <reg>,-1` this
            # stub displaces, and the stub calls here BEFORE replaying it.
            # Without this test the scale below turns -1 into a pointer
            # before record zero, which the companion then reads as a
            # villager. Found in review.
            cmp ecx, -1
            je birth_done
            imul ecx, ecx, 0x{BIRTH_STRIDE:X}
            add ecx, 0x{BIRTH_RECORDS_VA + BIRTH_RECORD_BASE:X}
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
        birth_done:
            popad
            ret
        """,
        birth_body_va,
    )
    if len(birth_body) > BIRTH_EXPORT_NAME_OFFSET - BIRTH_BODY_OFFSET:
        raise RuntimeError(
            f"the birth body is {len(birth_body):#x} bytes and runs into "
            f"the export name"
        )

    # DO NOT PLACE THE BIRTH BLOCK ON TOP OF ANYTHING.
    #
    # Codex found that VV3's block had landed on the conception
    # trampoline, the DLL name and the export name: the emitted page no
    # longer contained either loader string, so the conception hook could
    # not resolve its exports. The offsets had been chosen by scanning a
    # BUILT ARTIFACT for zero runs, which measures the composed page --
    # where a run is free only because the generator has not written it
    # yet. These slice assignments run last, so they overwrote it.
    #
    # This reads the page in hand instead, which write order cannot fool.
    for _lo, _hi, _what in (
        (BIRTH_BODY_OFFSET, BIRTH_BODY_OFFSET + len(birth_body), "body"),
        (
            BIRTH_EXPORT_NAME_OFFSET,
            BIRTH_EXPORT_NAME_OFFSET + len(BIRTH_EXPORT_NAME),
            "export name",
        ),
        (
            BIRTH_STUBS_OFFSET,
            BIRTH_STUBS_OFFSET + len(BIRTH_SITES) * BIRTH_STUB_SIZE,
            "stubs",
        ),
    ):
        _clash = [_i for _i in range(_lo, _hi) if page[_i]]
        if _clash:
            raise RuntimeError(
                f"the birth {_what} at {_lo:#x}..{_hi:#x} would overwrite "
                f"{len(_clash)} occupied byte(s), first at "
                f"{_clash[0]:#x}"
            )
    page[BIRTH_BODY_OFFSET : BIRTH_BODY_OFFSET + len(birth_body)] = birth_body
    page[
        BIRTH_EXPORT_NAME_OFFSET : BIRTH_EXPORT_NAME_OFFSET
        + len(BIRTH_EXPORT_NAME)
    ] = BIRTH_EXPORT_NAME

    for _index, (_site_va, _displaced, _what) in enumerate(BIRTH_SITES):
        # Each site replays its OWN displaced bytes: five at most sites,
        # eight at the triplet, where a five-byte jump would land inside
        # an imul. Checked against the stock file below.
        _actual = source[
            _site_va - IMAGE_BASE : _site_va - IMAGE_BASE + len(_displaced)
        ]
        if _actual != _displaced:
            raise RuntimeError(
                f"{_what} at {_site_va:#x}: stock bytes are "
                f"{_actual.hex()}, expected {_displaced.hex()}"
            )
        _stub_off = BIRTH_STUBS_OFFSET + _index * BIRTH_STUB_SIZE
        _stub_va = page_va + _stub_off
        _stub = (
            b"\xE8"
            + int(birth_body_va - (_stub_va + 5)).to_bytes(4, "little", signed=True)
            + _displaced
            + b"\xE9"
            + int(
                (_site_va + len(_displaced))
                - (_stub_va + 5 + len(_displaced) + 5)
            ).to_bytes(4, "little", signed=True)
        )
        if len(_stub) > BIRTH_STUB_SIZE:
            raise RuntimeError(
                f"birth stub {_index} is {len(_stub):#x} bytes, reserved "
                f"{BIRTH_STUB_SIZE:#x}"
            )
        page[_stub_off : _stub_off + len(_stub)] = _stub

        # A five-byte jump leaves the rest of the displaced bytes behind,
        # which would execute as whatever they decode to; 0x90 makes the
        # tail an explicit no-op rather than a fragment.
        _entry = b"\xE9" + int(_stub_va - (_site_va + 5)).to_bytes(
            4, "little", signed=True
        )
        _entry += b"\x90" * (len(_displaced) - len(_entry))
        patches.append(
            {
                "offset": f"0x{_site_va - IMAGE_BASE:X}",
                "before": _actual.hex(),
                "after": _entry.hex(),
                "purpose": (
                    f"divert {_what} into its birth stub, which calls the "
                    f"companion, replays these bytes and returns to "
                    f"{_site_va + len(_displaced):#x}"
                ),
            }
        )
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
    reset_hash = hashlib.sha256(RESET_COMPANION.read_bytes()).hexdigest().upper()
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
                "id": "vv5_write_parentage_log",
                "game_id": "vv5",
                "name": "Write Births and Conceptions Log to Text File",
                "output_tag": "Births and Conceptions Log Text Export",
                "description": (
                    "On each new pregnancy, appends the mother's and father's "
                    "names, both parents' ages at conception, both head and "
                    "body values, both parents' likes and dislikes, and the "
                    "number of babies to "
                    "'Virtual Villagers 5 Births and Conceptions Log N.txt' beside the game "
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
                        "id": "vv5_write_village_statistics",
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
