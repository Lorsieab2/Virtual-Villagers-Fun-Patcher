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

and the call site corroborates both mappings:

    0x43DD19  push edi
    0x43DD24  mov  eax, [edx + 0x36C]      ; the father's villager ID
    0x43DD2A  push ecx                     ; mother index
    0x43DD2F  push eax                     ; father id  (a VALUE, not an index)
    0x43DD30  push ecx
    0x43DD31  mov  ecx, esi                ; record array base
    0x43DD33  call sub_43BBC0

The routine takes FOUR stack arguments, not three: both its return sites are
`ret 0x10` (0x43BCB7 and 0x43BCC8) and it reads a fourth slot at 0x43BBE2.
Only the first two are read here, but anyone extending this trampoline to
reach the third or fourth needs the real frame size rather than a guess.

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

# The companion takes a game id so one DLL serves all five games, matching
# how the statistics companion is structured. VV1 is 1.
GAME_ID = 1

# The SUCCESS exits of the conception routine sub_43BBC0.
#
# Hooking the routine's HEAD was wrong twice over, and Codex caught both:
#
#   * The litter size is not known there. The engine writes record+0x35C on
#     branches that run later -- 2 at 0x43BC4E, 3 at 0x43BC8C -- so a head hook
#     can only report a singleton, and every twin and triplet birth would be
#     recorded permanently wrong. Permanently, because the whole premise of this
#     feature is that parentage cannot be recovered from the child afterwards:
#     there is no second source to correct the record from.
#
#   * Conception can be REJECTED. 0x43BBC8 tests the result of the capacity
#     predicate 0x43A1A0 and jumps to 0x43BCC7 when it fails, creating no
#     pregnancy at all. A head hook logs those phantom conceptions too.
#
# Moving to the tails fixed both -- and then dropped every SINGLE birth, which
# is the common case. The tail at 0x43BCBA looks like a "twins/single" join but
# is not: its only three predecessors (0x43BC71, 0x43BC7B, 0x43BC8A) all sit
# downstream of `mov [esi+0x35C], 2`, so it is twins-only. Singletons leave via
# 0x43BC39 and 0x43BC4C, which both target 0x43BCC6 and bypass both tails.
#
# So there are three success exits, and all three are covered:
#
#     0x43BCA2  triplets   mov edi,[edi+0x3E010]   -- steal 6, replay, rejoin
#     0x43BCBA  twins      mov edi,[edi+0x3E010]   -- steal 6, replay, rejoin
#     singles   RETARGET the two branches rather than stealing anything
#
# The singleton case cannot be hooked the same way. Its natural site 0x43BCC6
# is `pop esi; pop edi; ret 0x10`, six bytes -- but the REJECTION path enters at
# 0x43BCC7, one byte in. Stealing six bytes there would leave the rejection jump
# landing in the middle of the inserted jmp, which crashes the game. The bytes
# at 0x43BCC6 are therefore left completely untouched.
#
# Instead the two singleton branches are retargeted, so nothing is stolen and
# nothing shifts:
#
#     0x43BC39  je  0x43BCC6   is already a six-byte near jcc -> retarget it
#                              straight at the trampoline.
#     0x43BC4C  jge 0x43BCC6   is a TWO-byte short jcc; a rel8 cannot reach the
#                              cave. It is retargeted to 0x43BCCB instead, which
#                              is +0x7D from the next instruction and so still
#                              in rel8 range, and 0x43BCCB..0x43BCCF is the
#                              routine's own five-byte NOP padding -- exactly
#                              the width of one jmp rel32 to the cave.
#
# Both singleton routes therefore reach the trampoline, which logs and then
# jumps to 0x43BCC6 to rejoin the stock epilogue.
TAIL_VAS = (0x0043BCA2, 0x0043BCBA)
TAIL_FILES = (0x0003BCA2, 0x0003BCBA)

# The singleton wiring.
SINGLE_NEAR_JE_VA = 0x0043BC39      # je 0x43BCC6, six bytes, retargeted
SINGLE_NEAR_JE_FILE = 0x0003BC39
SINGLE_NEAR_JE_STOCK = bytes.fromhex("0f8487000000")

SINGLE_SHORT_JGE_VA = 0x0043BC4C    # jge 0x43BCC6, two bytes, aimed at the pad
SINGLE_SHORT_JGE_FILE = 0x0003BC4C
SINGLE_SHORT_JGE_STOCK = bytes.fromhex("7d78")

PAD_VA = 0x0043BCCB                 # five nops after the routine
PAD_FILE = 0x0003BCCB
PAD_STOCK = bytes.fromhex("9090909090")

EPILOGUE_VA = 0x0043BCC6            # pop esi; pop edi; ret 0x10 -- NEVER patched

TAIL_STOLEN = bytes.fromhex("8bbf10e00300")

# The cave.
#
# 0x456580..0x456FFF is the only usable zero run in .text, and most of it is
# already spoken for. Being zero in the STOCK executable is NOT evidence that a
# range is free: the safety patches and several fun patches write into this run
# at apply time, and the renderer rejects cross-owner overlaps. An earlier draft
# of this file claimed 0x456800 on the strength of a stock zero-scan alone;
# data/builds.json shows fun_patches[9]/patches[2] owns exactly that address,
# so the feature could not have composed in any mode. Codex caught it.
#
# Ownership across the run, from data/builds.json plus the statistics feature:
#     0x56580 0x565B0 0x565E0  safety_patches[6] [8] [1]
#     0x56600                  fun_patches[8]/patches[2]
#     0x56680                  safety_patches[9]
#     0x566A0 0x566E0          fun_patches[6]/patches[1] [3]
#     0x56730                  statistics feature (emitted, not in builds.json)
#     0x56800                  fun_patches[9]/patches[2]   <-- the collision
#     0x56840 0x56860          safety_patches[3] [4]
#     0x56880                  fun_patches[9]/patches[4]
#     0x568A0 0x568D0          fun_patches[10]/patches[1] [5]
#
# The highest claimed byte is 0x56900, so this takes the block above it. That
# leaves 0x56900+0x100 .. 0x56FFF free for whatever comes next.
CAVE_VA = 0x00456900
CAVE_FILE = 0x00056900
CAVE_SIZE = 0x140

# Where the payload lives when Origins is ALSO selected.
#
# Origins claims the whole of 0x56900..0x57000, so the two features cannot both
# use the cave. It also appends an 8 KB block as .vv1mc (R-X code) and .vv1md
# (R/W data) at VA 0x490000, and the code page has an unclaimed run at file
# 0x8E435 / VA 0x490435 -- 0x18B bytes, against the 0x140 this needs.
#
# The payload is re-emitted for that address rather than copied, because every
# trampoline ends in a rel32 back into the conception routine and a byte copy
# would leave all three aimed 0x39B35 bytes short of their targets.
CO_SELECTED_CAVE_VA = 0x00490435
CO_SELECTED_CAVE_FILE = 0x0008E435
ORIGINS_FEATURE_ID = "vv1_enable_origins_exclusive_features"

# Imports, reused from the statistics feature's own verified table entries.
# Resolved from the stock import table rather than assumed, because the ANSI
# vs wide pairing matters: the DLL name below is an ASCII string, so these must
# be the A variants. They are --
#     0x457010 -> KERNEL32.dll!LoadLibraryA
#     0x4570D0 -> KERNEL32.dll!GetModuleHandleA
#     0x4570D4 -> KERNEL32.dll!GetProcAddress
LOAD_LIBRARY_IAT = 0x00457010
GET_MODULE_HANDLE_IAT = 0x004570D0
GET_PROC_ADDRESS_IAT = 0x004570D4

DLL_NAME = b"VVFP Parentage Export.dll\0"
EXPORT_NAME = b"WriteParentageRecord\0"

# Where the two strings sit inside the cave block, clear of BOTH trampolines.
#
# Two 0x50 slots occupy 0x00..0x9F, so the strings start at 0xA0. An earlier
# layout left them at 0x80 and the second trampoline ran straight into the DLL
# name -- the emitted disassembly decoded the string as instructions, which is
# exactly what that looks like when it happens.
DLL_NAME_OFFSET = 0xF0
EXPORT_NAME_OFFSET = 0x110

# The five stock bytes the trampoline replaces, restored before returning.
STOLEN_BYTES = bytes.fromhex("578bf9e8d8e5ffff")


def assemble(source: str, address: int) -> bytes:
    engine = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    encoding, _ = engine.asm(source, address)
    return bytes(encoding)


def _emit(source: bytes, cave_va: int, cave_file: int) -> tuple[list[dict], bytes]:
    """Assemble the trampolines and hook rewrites for one cave address."""

    # Three trampolines -- triplets, twins, singles -- each in its own slot.
    # Each assembles to about 0x45 bytes, so 0x50 apiece. The checks below are
    # what actually enforce the layout: an earlier 0x40 was too small, and an
    # earlier string offset let a trampoline run into the DLL name.
    slot_size = 0x50

    for tail_file in TAIL_FILES:
        if source[tail_file : tail_file + len(TAIL_STOLEN)] != TAIL_STOLEN:
            raise RuntimeError(
                f"stock bytes at {tail_file:#x} are not the expected tail"
            )
    for label, offset, expected in (
        ("singleton near je", SINGLE_NEAR_JE_FILE, SINGLE_NEAR_JE_STOCK),
        ("singleton short jge", SINGLE_SHORT_JGE_FILE, SINGLE_SHORT_JGE_STOCK),
        ("trailing pad", PAD_FILE, PAD_STOCK),
    ):
        if source[offset : offset + len(expected)] != expected:
            raise RuntimeError(
                f"stock bytes at {offset:#x} are not the expected {label}"
            )
    if cave_file + CAVE_SIZE <= len(source):
        if set(source[cave_file : cave_file + CAVE_SIZE]) != {0}:
            raise RuntimeError(f"cave at {cave_file:#x} is not free")
    elif cave_file < len(source):
        # A cave that straddles the stock end-of-file is a mistake, not an
        # appended page: appended space starts exactly at EOF.
        raise RuntimeError(
            f"cave at {cave_file:#x} straddles the stock end of file"
        )
    else:
        # Past the stock EOF the bytes do not exist yet -- this address lives in
        # a page Origins appends, and the patcher checks that page's zero
        # preimage when it applies the composition. Asserting against the stock
        # file here would only assert that the file is short.
        pass

    dll_name_va = cave_va + DLL_NAME_OFFSET
    export_name_va = cave_va + EXPORT_NAME_OFFSET

    payload = bytearray(CAVE_SIZE)
    patches: list[dict[str, object]] = []

    for index, (tail_va, tail_file) in enumerate(zip(TAIL_VAS, TAIL_FILES)):
        # A DISTINCT name, not a reassignment of cave_va: overwriting the base
        # here left the singleton trampoline below computing its own slot from
        # an already-advanced base, so its rejoin jumped 0x50 short -- into the
        # middle of the routine rather than to the epilogue. The emitted bytes
        # looked plausible and the two tail trampolines were unaffected, which
        # is exactly why it survived a check that only looked at those two.
        slot_va = cave_va + index * slot_size

        # The trampoline.
        #
        # Both tails are entered with the two pointers already in registers:
        #     esi = the mother's record   (lea esi,[edx+edi] at 0x43BBF1, never
        #                                  reassigned before either tail)
        #     edi = the record array base (about to be overwritten by the stolen
        #                                  instruction, which is why the copy is
        #                                  taken before it runs)
        #
        # So there is no stack-offset arithmetic at all. An earlier draft hooked
        # the routine's head and had to fish arguments out of the pushad frame
        # at hand-computed displacements; passing registers the game already
        # holds is simpler and immune to that whole class of mistake.
        #
        # pushad stores edi, esi, ebp, esp, ebx, edx, ecx, eax from low address
        # up, so inside the handler saved edi is at esp+0x00 and saved esi at
        # esp+0x04. They are read from the frame rather than live because the
        # three loader calls are free to clobber caller-saved registers, and
        # reading the frame stays correct if the payload later touches more.
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
                # WriteParentageRecord(records, mother). stdcall, so the callee
                # cleans its own 8 bytes and the frame stays balanced. Pushed
                # right to left: mother (saved esi) first, then records (edi).
                # WriteParentageRecord(game_id, records, mother). stdcall, so
                # the callee cleans its own 12 bytes and the frame stays
                # balanced. Pushed right to left, and each push moves esp,
                # which is why the two frame reads use the same displacement
                # and still fetch different values: saved esi (the mother)
                # then saved edi (the record array).
                push dword ptr [esp + 0x04]
                push dword ptr [esp + 0x04]
                push {GAME_ID}
                call eax
            done:
                popad
                # Replay the stolen manager fetch, then rejoin after it.
                mov edi, dword ptr [edi + 0x3E010]
                jmp 0x{tail_va + len(TAIL_STOLEN):X}
            """,
            slot_va,
        )
        if slot_va + len(code) > cave_va + DLL_NAME_OFFSET:
            raise RuntimeError(
                f"trampoline {index} runs into the strings at {DLL_NAME_OFFSET:#x}"
            )
        if len(code) > slot_size:
            raise RuntimeError(
                f"trampoline {index} is {len(code):#x} bytes, over {slot_size:#x}"
            )
        payload[index * slot_size : index * slot_size + len(code)] = code

        # Divert the tail: a five-byte jmp plus one nop replaces the six-byte
        # stolen instruction exactly, so nothing downstream shifts.
        entry = assemble(f"jmp 0x{slot_va:X}", tail_va)
        entry = entry + b"\x90" * (len(TAIL_STOLEN) - len(entry))
        if len(entry) != len(TAIL_STOLEN):
            raise RuntimeError("tail entry does not match the stolen byte count")

        patches.append(
            {
                # The renderer parses `offset` with int(value, 0) and reads
                # `before`/`after`. An integer offset raises a TypeError there,
                # and `original`/`bytes` leaves it with no `before` at all -- so
                # an earlier draft aborted every dry run and every apply that
                # selected this feature. data/statistics_features.json is the
                # schema to match.
                "offset": f"0x{tail_file:X}",
                "before": TAIL_STOLEN.hex().upper(),
                "after": entry.hex().upper(),
                "purpose": (
                    "Divert the "
                    + ("triplets" if index == 0 else "twins/single")
                    + " success tail of the conception routine sub_43BBC0 to "
                    "its trampoline, which logs the pregnancy with the litter "
                    "size the engine has already committed, then replays this "
                    "instruction."
                ),
            }
        )

    # The singleton trampoline, in the third slot.
    #
    # Reached from the two retargeted branches rather than from stolen bytes.
    # It logs and then jumps to the stock epilogue at 0x43BCC6, which is left
    # completely untouched -- see the note above on why stealing there would
    # crash the rejection path.
    #
    # esi and edi hold the mother's record and the record array here for the
    # same reason they do at the tails: esi is written once at 0x43BBF1 and
    # never reassigned before any exit, and edi is written at 0x43BBC1 and left
    # alone, with the intervening manager fetches all targeting eax.
    single_cave_va = cave_va + 2 * slot_size
    single_code = assemble(
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
            push dword ptr [esp + 0x04]
            push dword ptr [esp + 0x04]
            push {GAME_ID}
            call eax
        done:
            popad
            jmp 0x{EPILOGUE_VA:X}
        """,
        single_cave_va,
    )
    if single_cave_va + len(single_code) > cave_va + DLL_NAME_OFFSET:
        raise RuntimeError("singleton trampoline runs into the strings")
    payload[2 * slot_size : 2 * slot_size + len(single_code)] = single_code

    # Retarget the six-byte near je straight at the trampoline.
    near_je = assemble(f"je 0x{single_cave_va:X}", SINGLE_NEAR_JE_VA)
    if len(near_je) != len(SINGLE_NEAR_JE_STOCK):
        raise RuntimeError("retargeted near je changed width")
    patches.append(
        {
            "offset": f"0x{SINGLE_NEAR_JE_FILE:X}",
            "before": SINGLE_NEAR_JE_STOCK.hex().upper(),
            "after": near_je.hex().upper(),
            "purpose": (
                "Retarget the singleton branch that skips the twins roll so it "
                "reaches the parentage trampoline instead of the epilogue. "
                "Same width, so nothing shifts."
            ),
        }
    )

    # The two-byte short jge cannot reach the cave with a rel8, so aim it at the
    # routine's own trailing pad and put the long jump there.
    short_jge = assemble(f"jge 0x{PAD_VA:X}", SINGLE_SHORT_JGE_VA)
    if len(short_jge) != len(SINGLE_SHORT_JGE_STOCK):
        raise RuntimeError(
            "retargeted short jge changed width; it would shift the code after it"
        )
    patches.append(
        {
            "offset": f"0x{SINGLE_SHORT_JGE_FILE:X}",
            "before": SINGLE_SHORT_JGE_STOCK.hex().upper(),
            "after": short_jge.hex().upper(),
            "purpose": (
                "Retarget the singleton branch whose twins roll failed to the "
                "five-byte pad after the routine. It stays a two-byte short "
                "jump, so nothing shifts; a rel8 cannot reach the cave."
            ),
        }
    )

    pad_jump = assemble(f"jmp 0x{single_cave_va:X}", PAD_VA)
    if len(pad_jump) != len(PAD_STOCK):
        raise RuntimeError("pad jump does not fit the five nop bytes exactly")
    patches.append(
        {
            "offset": f"0x{PAD_FILE:X}",
            "before": PAD_STOCK.hex().upper(),
            "after": pad_jump.hex().upper(),
            "purpose": (
                "Fill the routine's five-byte nop pad with the long jump to the "
                "singleton trampoline, which the short branch above can reach."
            ),
        }
    )

    payload[DLL_NAME_OFFSET : DLL_NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    payload[EXPORT_NAME_OFFSET : EXPORT_NAME_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME
    patches.append(
        {
            "offset": f"0x{cave_file:X}",
            "before": ("00" * CAVE_SIZE).upper(),
            "after": bytes(payload).hex().upper(),
            "purpose": (
                "Two loader trampolines, one per success tail, plus the shared "
                "DLL and export names. All logging logic lives in the companion "
                "DLL; only the call into it is in the executable."
            ),
        }
    )

    return patches, bytes(payload)


def build() -> dict:
    source = (STOCK / EXE).read_bytes()
    patches, _ = _emit(source, CAVE_VA, CAVE_FILE)
    co_patches, _ = _emit(source, CO_SELECTED_CAVE_VA, CO_SELECTED_CAVE_FILE)

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
                "patches": patches,
                # The same feature, re-emitted for the address it must use when
                # Origins is also selected. The patcher swaps to these rather
                # than refusing the composition; see CO_SELECTED_CAVE_VA above
                # for why a byte copy would not work.
                "composition_patches": {
                    ORIGINS_FEATURE_ID: co_patches,
                },
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
