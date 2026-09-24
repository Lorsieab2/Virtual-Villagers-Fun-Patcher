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
# 0x140 for the three trampolines and the two strings, plus the father-capture
# block below. The stock zero run at 0x56900 is 0x700 bytes, so this is well
# inside it; the check in _emit still asserts the whole span is zero.
CAVE_SIZE = 0x200

# --- the father capture -----------------------------------------------------
#
# VV1 stores NOTHING about the father in the mother's record, so unlike VV2-VV5
# there is no field to read at the success tails. His record pointer exists only
# at the CALL SITES of the conception routine, where the game loads exactly one
# field off it (+0x36C) and discards the rest.
#
# sub_43BBC0 has six callers and no indirect references:
#
#     0x43DD33  0x43DD54  0x43DD7B  0x43DD94  0x447031  0x447238
#
# A hook inside the routine cannot reach him. Its prologue forms exactly one
# record pointer -- imul 0x3D8 at 0x43BBEA, the mother's -- that is the only
# stride multiply in the function.
#
# HOW HE TRAVELS: an argument slot the routine never reads.
#
# sub_43BBC0 is __thiscall ending in `ret 0x10`, so it takes four stack
# arguments. After its `push edi` they sit at [esp+0x08], [esp+0x0C],
# [esp+0x10] and [esp+0x14]. Disassembling every esp-based memory operand in
# the whole routine finds accesses to exactly three of them:
#
#     [esp+0x08]  1 read   0x43BBE6  mov edx,[esp+8]      the mother's index
#     [esp+0x10]  2 reads  0x43BBD0, 0x43BC00             a skill selector
#     [esp+0x14]  1 read   0x43BBE2  mov ecx,[esp+0x14]
#     [esp+0x0C]  0 reads  -- the father's +0x36C, passed and ignored
#
# So the third argument is dead. Each call site is redirected through a stub
# that replaces the pushed +0x36C VALUE with the father's record POINTER, and
# the success-tail trampolines read the pointer back out of that slot.
#
# This is why there is no writable scratch slot. An earlier draft kept the
# pointer in a fixed cave address, which Codex correctly rejected: the cave is
# in .text (0x60000020, R-X) and the Origins-composed page is .vv1mc with the
# same characteristics, so the very first conception would have written to a
# read-only page and access-violated. Passing the pointer in a dead argument
# needs no writable storage at all, and it cannot go stale -- there is nothing
# that persists between births to go stale.
#
# The stubs are per-site because the father's pointer is in a different
# register at each one, and because the already-pushed value has to be
# overwritten in place:
#
#     site      the instruction that loads his +0x36C, giving the register
#     0x43DD33  0x43DD24  mov eax,[edx+0x36C]   -> edx
#     0x43DD54  0x43DD45  mov ecx,[eax+0x36C]   -> eax
#     0x43DD7B  0x43DD70  mov ecx,[ebp+0x36C]   -> ebp
#     0x43DD94  0x43DD89  mov eax,[ebp+0x36C]   -> ebp
#     0x447031  0x447020  mov ecx,[eax+0x36C]   -> eax
#     0x447238  0x44721D  mov edx,[ecx+0x36C]   -> ecx
#
# At the stub the return address is on top, so the four arguments are at
# [esp+0x04] .. [esp+0x10] and the dead one is at [esp+0x08].
CONCEPTION_VA = 0x0043BBC0
FATHER_ARG_AT_STUB = 0x08          # [esp+0x08] once the call pushed its return
FATHER_CALL_SITES = (
    (0x0043DD33, 0x0003DD33, "edx"),
    (0x0043DD54, 0x0003DD54, "eax"),
    (0x0043DD7B, 0x0003DD7B, "ebp"),
    (0x0043DD94, 0x0003DD94, "ebp"),
    (0x00447031, 0x00447031 - 0x400000, "eax"),
    # 0x447238 takes EAX, not ECX.
    #
    # Its father load is `mov ecx,[esp+0x14]` at 0x447219, but 0x44722E then
    # does `mov ecx,esi` -- esi is the `this` pointer, the mother -- so by the
    # time the stub runs ecx holds her. The companion rejects a father equal
    # to the mother, so this site could never have captured even with the
    # displacement right.
    #
    # eax is loaded at 0x447229 from [esp+0x14], the same slot the father came
    # from, and is not written again before the call; it is pushed as arg1 at
    # 0x447237. Verified by disassembling the aligned window rather than read
    # from the surrounding code, whose preceding bytes decode as garbage from
    # a mid-instruction start.
    #
    # Two branches converge on this call. The one above (reached by the jne at
    # 0x4471F4) is the one that loads the father; the fallthrough at 0x4471F6
    # never reads [reg+0x36C] at all and loads eax from a different slot,
    # [esp+0x28]. On that path eax is not the father, and the companion's
    # record validation rejects it, so that birth loses his three fields
    # exactly as today. This site therefore goes from never capturing to
    # capturing on one of its two paths.
    (0x00447238, 0x00447238 - 0x400000, "eax"),
)

# Where each trampoline finds that argument, as a displacement from the tail's
# own esp BEFORE its pushad. Measured from the routine's stack adjustments:
#
#     0x43BBC0  push edi        +4
#     0x43BBF0  push esi        +8
#     0x43BC3F  push 0x64 / 0x43BC46 add esp,4    (balanced)
#     0x43BC7D  push 0x64 / 0x43BC84 add esp,4    (balanced)
#     0x43BCAF  pop esi         +4
#     0x43BCB6  pop edi         +0
#
# So the triplets tail and both singleton branches sit at +8, while the twins
# tail at 0x43BCBA is past both pops and sits at +0. Getting this wrong reads
# a neighbouring argument, which is a plausible-looking wrong pointer rather
# than a crash -- the companion's record validation is what stops it becoming
# a wrong father in the log.
# The dead slot is the SECOND argument, so it is one dword above arg1.
#
# This was 0x0C, which is arg1's displacement, and the mistake was invisible
# in every static check: the emitted trampolines disassembled correctly, the
# byte guards passed, and the companion validated the pointer it was handed
# and correctly reported it as unusable. The owner's parentage log is what
# exposed it -- every VV1 conception read "(not captured for this birth)",
# because what was actually being passed was arg3, a skill selector, which
# is not a record slot.
#
# Derivation, anchored at the call rather than at the routine's reads.
#
# When `call 0x43bbc0` transfers control, esp points at the return address and
# the four arguments sit above it: arg1 at +0x04, arg2 at +0x08, arg3 at +0x0C,
# arg4 at +0x10. Call that esp E. The dead slot is arg2, so the father is at
# E+0x08.
#
# That cross-checks against the routine's own reads. After its `push edi` it
# reads [esp+0x08], [esp+0x10] and [esp+0x14] and never [esp+0x0C]; undoing the
# push those are E+0x04, E+0x0C, E+0x10 -- arg1, arg3, arg4 -- leaving E+0x08,
# arg2, as the one it never touches.
#
# The tails are two pushes deep (push edi, push esi), so their esp is E-8 and
# the father is at +0x08+8 there; the twins tail is past both pops, back at E,
# so it is at +0x08+0.
FATHER_ARG_AT_TRIPLETS = 0x08 + 8
FATHER_ARG_AT_TWINS = 0x08 + 0
FATHER_ARG_AT_SINGLE = 0x08 + 8

# Six stubs, each: overwrite the dead argument, then tail-call the routine.
FATHER_STUB_OFFSET = 0x170
FATHER_STUB_SIZE = 0x10

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
# Measured against real renders, not predicted from manifests.
#
# The previous address here was 0x8E435, chosen for a 0x18B gap between two
# Origins patches. That was correct for the 0x140 payload it was sized against
# and is not correct now: at 0x200 the payload would run 0x75 bytes into the
# Origins stub block at 0x8E5C0 and corrupt the mask renderer. The zero-preimage
# check in _emit cannot catch that, because past the stock end of file there are
# no bytes to compare.
#
# Manifest arithmetic then got it wrong a second time. Summing what Origins
# writes suggested everything above 0x8EB8C was free, so this moved to 0x8EC00
# -- and the patcher's own byte guard rejected it, because VV1 Birth Control
# claims the whole 0x490000 page and other patches compose into it at apply
# time. Neither manifest shows that.
#
# So the free runs were measured by rendering VV1 with every other fun patch
# selected, in all three build modes, and intersecting the result. Exactly two
# runs of 0x100 or more are zero in every mode:
#
#     0x8E435 .. 0x8E5C0   0x18B   (the old home, too small at 0x200)
#     0x8ED82 .. 0x90000   0x127E
#
# This takes 0x8EE00 in the second run, which leaves it ending exactly at
# 0x8F000. Re-measure with scripts against a render if this payload grows
# again; do not re-derive it from the manifests.
CO_SELECTED_CAVE_VA = 0x00490E00
CO_SELECTED_CAVE_FILE = 0x0008EE00
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
# The four-argument entry point. The three-argument WriteParentageRecord is
# still exported and still works, but VV1 now has a father to pass and the
# extra argument is the only way to hand it over.
EXPORT_NAME = b"WriteParentageRecordWithFather\0"

# Where the two strings sit inside the cave block, clear of BOTH trampolines.
#
# Two 0x50 slots occupy 0x00..0x9F, so the strings start at 0xA0. An earlier
# layout left them at 0x80 and the second trampoline ran straight into the DLL
# name -- the emitted disassembly decoded the string as instructions, which is
# exactly what that looks like when it happens.
DLL_NAME_OFFSET = 0x120
EXPORT_NAME_OFFSET = 0x140

# THE TRIBE-DELETE HOOK.
#
# The save-slot menu deletes a tribe by calling deleteSave through a `jmp`
# thunk with the RAW slot in edi. The game's OTHER caller of deleteSave is a
# save routine rotating backup generations, which passes slot + 0x14 -- so
# hooking the menu handler's own call reaches the reset and never ordinary
# play. See docs/start-over-reset-hook.md.
#
# WHERE ITS BYTES GO, and why not .text. VV1 rendered with every patch
# selected has NO free run of 96 bytes anywhere in .text -- the space is
# entirely claimed. The only executable room is inside .vv1mc, the page
# Origins appends, whose largest free run is 188 bytes at file 0x8E344.
# That was measured by rendering, not assumed.
#
# .vv1md, which follows at VA 0x491000, is NOT executable. Placing the stub
# past the end of .vv1mc would crash on tribe delete rather than fail to
# build, so the cave is bounded to the run that was measured.
# Inside the SAME cave _emit places, at a fixed offset past the parentage
# payload, so it relocates with it: 0x56900 standalone, 0x8EE00 composed.
# Writing it at a hardcoded appended-page address instead made the
# standalone pass claim bytes that only exist when Origins appends the
# page, and the patcher's overlap guard rejected it.
# ITS OWN CAVE, AND ONLY IN THE COMPOSED PASS.
#
# VV1 rendered with every patch selected has NO free run this size anywhere
# in .text -- the space is entirely claimed -- so the stub can only live in
# .vv1mc, the executable page Origins appends.
#
# ITS ADDRESS WAS MEASURED AGAINST EVERY MANIFEST, not against one render.
# Overlaying the claims of every vv1 manifest on 0x8E000..0x8F000 leaves
# exactly one unclaimed run of this size: 436 bytes at 0x8EB8C. Two earlier
# addresses looked free and were not. 0x8E344 read as zero in Origins' own
# page but the overlap guard rejected it, because Origins writes those bytes.
# 0x8ED40 passed a single-configuration build and then failed the byte guard
# the moment another feature was selected, because that feature's code lives
# there. A render with one set of patches is not a measurement.
#
# .vv1md, which follows .vv1mc at VA 0x491000, is NOT executable, so an
# address past the end of .vv1mc would crash on tribe delete rather than
# fail to build. This one is comfortably inside it.
#
# Two things that measurement caught. .vv1md, which follows .vv1mc at VA
# 0x491000, is NOT executable, so growing the parentage cave past 0x491000
# put the stub in a non-executable section -- a crash on tribe delete rather
# than a build failure. And this address exists only when Origins appends the
# page, so emitting it in the standalone pass made that pass claim bytes that
# are not there, which the patcher's overlap guard rejected.
#
# So the reset is emitted for the composed layout only. Every shipped build
# has Origins selected -- all patches ship enabled by default -- and a
# standalone parentage build simply keeps the pre-existing behaviour of not
# sweeping on tribe delete, rather than crashing.
RESET_CAVE_FILE = 0x0008EB8C
RESET_CAVE_VA = 0x00490B8C
RESET_CAVE_SIZE = 0x74
RESET_DLL_NAME = b"VVFP Save Reset.dll\0"
RESET_EXPORT_NAME = b"ResetDeletedTribe\0"
RESET_DLL_NAME_OFFSET = 0x00
RESET_EXPORT_NAME_OFFSET = 0x14
RESET_CODE_OFFSET = 0x28

RESET_HOOK_VA = 0x00413E07
RESET_HOOK_FILE = 0x00013E07
RESET_HOOK_STOLEN = bytes.fromhex("e8e4810000")
RESET_THUNK_VA = 0x0041BFF0
RESET_COMPANION_SOURCE = "assets/save_reset/VVFP Save Reset.dll"


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
    # 0x60, not 0x50: each trampoline gained a push of the captured father
    # and a clear of the slot, which took the largest from 0x45 to 0x57.
    slot_size = 0x60

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
        # Per-tail, NOT shared: the triplets tail is still inside the routine's
        # two pushes while the twins tail is past both pops, so the same
        # argument sits at different displacements. pushad then adds 0x20.
        father_arg_in_frame = 0x20 + (
            FATHER_ARG_AT_TRIPLETS if index == 0 else FATHER_ARG_AT_TWINS
        )
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
                # WriteParentageRecordWithFather(game_id, records, mother,
                # father). Pushed right to left, so the father goes first.
                #
                # The father arrives in the conception routine's third
                # stack argument, which the routine itself never reads. pushad
                # has just pushed 0x20 bytes, so the argument moves down by
                # that much; father_arg_in_frame already includes it.
                #
                # There is nothing to clear and nothing that can go stale: the
                # value lives in this call's own frame, so a pregnancy that
                # somehow reached here without a patched call site reads
                # whatever the stock caller pushed -- his +0x36C scalar, a
                # small integer that fails the companion's record validation
                # and logs "(not captured for this birth)".
                push dword ptr [esp + 0x{father_arg_in_frame:X}]
                push dword ptr [esp + 0x08]
                push dword ptr [esp + 0x08]
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
    # The singleton route is entered from branches at 0x43BC39 and 0x43BC4C,
    # both of which are still inside the routine's two pushes, so it uses the
    # same displacement as the triplets tail.
    father_arg_in_frame = 0x20 + FATHER_ARG_AT_SINGLE
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
            push dword ptr [esp + 0x{father_arg_in_frame:X}]
            push dword ptr [esp + 0x08]
            push dword ptr [esp + 0x08]
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

    # The six father-capture stubs, and the six call-site retargets.
    #
    # Each stub stashes the father's record pointer and then jumps to the real
    # conception routine, so the routine runs with its arguments and stack
    # exactly as the game built them -- the stub is transparent to it. The
    # stashed pointer is consumed and cleared by whichever success tail the
    # pregnancy reaches.
    #
    # Nothing here validates the pointer: that happens in the DLL, against the
    # record array, and is a stronger check than anything available here. A
    # site that somehow passed rubbish loses the father's three fields for that
    # birth and nothing else.
    for stub_index, (call_va, call_file, reg) in enumerate(FATHER_CALL_SITES):
        stub_offset = FATHER_STUB_OFFSET + stub_index * FATHER_STUB_SIZE
        stub_va = cave_va + stub_offset
        # Overwrite the dead third argument IN PLACE with the father's record
        # pointer, then tail-call the routine. The stub writes the caller's own
        # stack frame -- always writable -- rather than any part of the image,
        # which is the whole point of this design.
        #
        # The jmp, not a call: the routine must see exactly the frame the game
        # built, including the return address that sends it back to the real
        # caller. An extra frame here would leave `ret 0x10` unwinding the
        # wrong number of bytes.
        stub = assemble(
            f"""
                mov dword ptr [esp + 0x{FATHER_ARG_AT_STUB:X}], {reg}
                jmp 0x{CONCEPTION_VA:X}
            """,
            stub_va,
        )
        if len(stub) > FATHER_STUB_SIZE:
            raise RuntimeError(
                f"father stub {stub_index} is {len(stub):#x} bytes, over "
                f"{FATHER_STUB_SIZE:#x}"
            )
        if stub_offset + len(stub) > CAVE_SIZE:
            raise RuntimeError(f"father stub {stub_index} runs past the cave")
        payload[stub_offset : stub_offset + len(stub)] = stub

        # The stock five-byte E8 call, verified before it is replaced. All six
        # sites are direct near calls and sub_43BBC0 has no indirect
        # references, so redirecting them reaches every caller.
        stock_call = assemble(f"call 0x{CONCEPTION_VA:X}", call_va)
        if len(stock_call) != 5:
            raise RuntimeError("the stock conception call is not five bytes")
        if source[call_file : call_file + 5] != stock_call:
            raise RuntimeError(
                f"stock bytes at {call_file:#x} are not a call to the "
                f"conception routine"
            )
        new_call = assemble(f"call 0x{stub_va:X}", call_va)
        if len(new_call) != len(stock_call):
            raise RuntimeError("the retargeted call changed width")
        patches.append(
            {
                "offset": f"0x{call_file:X}",
                "before": stock_call.hex().upper(),
                "after": new_call.hex().upper(),
                "purpose": (
                    "Redirect one of the six conception call sites through a "
                    "stub that stashes the father's record pointer, which is "
                    "live in a register here and discarded by the stock code. "
                    "VV1 stores nothing about him in the mother's record, so "
                    "this is the only place his identity exists. Same width, "
                    "so nothing shifts."
                ),
            }
        )

    payload[DLL_NAME_OFFSET : DLL_NAME_OFFSET + len(DLL_NAME)] = DLL_NAME
    payload[EXPORT_NAME_OFFSET : EXPORT_NAME_OFFSET + len(EXPORT_NAME)] = EXPORT_NAME

    # THE TRIBE-DELETE PAYLOAD, in the measured free run inside .vv1mc.
    #
    # The stub preserves every register, because it runs inside the menu
    # handler's own frame, and falls through to the game's delete on EVERY
    # failure: a missing companion or an unresolved export costs the sweep,
    # never the player's save.
    reset_dll_va = RESET_CAVE_VA + RESET_DLL_NAME_OFFSET
    reset_export_va = RESET_CAVE_VA + RESET_EXPORT_NAME_OFFSET
    reset_code_va = RESET_CAVE_VA + RESET_CODE_OFFSET
    reset_payload = bytearray(RESET_CAVE_SIZE)
    reset_code = assemble(
        f"""
            pushad
            push 0x{reset_dll_va:X}
            call dword ptr [0x{GET_MODULE_HANDLE_IAT:X}]
            test eax, eax
            jnz reset_have_module
            push 0x{reset_dll_va:X}
            call dword ptr [0x{LOAD_LIBRARY_IAT:X}]
            test eax, eax
            jz reset_done
        reset_have_module:
            push 0x{reset_export_va:X}
            push eax
            call dword ptr [0x{GET_PROC_ADDRESS_IAT:X}]
            test eax, eax
            jz reset_done
            # ResetDeletedTribe(game, slot). EDI is the RAW slot the menu
            # handler loaded for the case the player chose -- not the
            # slot + 0x14 that the backup rotator passes.
            push edi
            push {GAME_ID}
            call eax
        reset_done:
            popad
            jmp 0x{RESET_THUNK_VA:X}
        """,
        reset_code_va,
    )
    if RESET_CODE_OFFSET + len(reset_code) > RESET_CAVE_SIZE:
        raise RuntimeError("the reset stub runs past its measured cave")
    reset_payload[RESET_CODE_OFFSET : RESET_CODE_OFFSET + len(reset_code)] = reset_code
    reset_payload[RESET_DLL_NAME_OFFSET : RESET_DLL_NAME_OFFSET + len(RESET_DLL_NAME)] = RESET_DLL_NAME
    reset_payload[RESET_EXPORT_NAME_OFFSET : RESET_EXPORT_NAME_OFFSET + len(RESET_EXPORT_NAME)] = RESET_EXPORT_NAME

    reset_entry = assemble(f"call 0x{reset_code_va:X}", RESET_HOOK_VA)
    if len(reset_entry) != len(RESET_HOOK_STOLEN):
        raise RuntimeError("the reset hook entry does not match the stolen bytes")

    patches.append(
        {
            "offset": f"0x{cave_file:X}",
            "before": ("00" * CAVE_SIZE).upper(),
            "after": bytes(payload).hex().upper(),
            "purpose": (
                "Three loader trampolines -- triplets, twins and singletons "
                "-- plus the shared DLL and export names, the father-capture "
                "slot, and the six stubs that fill it. All logging logic lives "
                "in the companion DLL; only the call into it is in the "
                "executable."
            ),
        }
    )

    # ORIGINS OWNS THE TRIBE-DELETE STUB AND HOOK.
    #
    # Origins is what writes the per-slot mask files, so it carries the reset
    # unconditionally -- a build with Origins and no parentage log still needs
    # its masks swept. Claiming the same bytes here too would break removal:
    # uninstalling the parentage log would zero a stub Origins still needs.
    #
    # The parentage log therefore contributes no reset patch of its own. It
    # gets the behaviour for free whenever Origins is selected, which every
    # shipped build is, and a standalone parentage build has no mask state to
    # sweep anyway.

    return patches, bytes(payload)


def build() -> dict:
    source = (STOCK / EXE).read_bytes()
    patches, _ = _emit(source, CAVE_VA, CAVE_FILE)
    co_patches, _ = _emit(source, CO_SELECTED_CAVE_VA, CO_SELECTED_CAVE_FILE)

    companion_hash = hashlib.sha256(COMPANION.read_bytes()).hexdigest()

    reset_hash = hashlib.sha256((ROOT / RESET_COMPANION_SOURCE).read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "companion_sha256": companion_hash,
        "features": [
            {
                "id": "vv1_write_parentage_log",
                "game_id": "vv1",
                "name": "Write Births and Conceptions Log to Text File",
                "output_tag": "Births and Conceptions Log Text Export",
                "description": (
                    "On each new pregnancy, appends both parents' names, "
                    "both parents' ages at conception, both head and body "
                    "values, both parents' likes and dislikes, and the number "
                    "of babies to 'Virtual "
                    "Villagers 1 Births and Conceptions Log N.txt' beside the game "
                    "executable. The mother's age determines the child's "
                    "age, and the father's age is recorded too. VV1 "
                    "stores nothing about the father in the mother's "
                    "record -- not his name, and no id that could find "
                    "him -- so his details, his age included, are "
                    "captured from his own record at the six conception "
                    "call sites, where the game holds it briefly. A birth "
                    "that reaches delivery without such a capture reports "
                    "the father as not captured for that birth, rather "
                    "than naming the wrong villager. "
                    "Parentage is not stored in any villager record, so "
                    "both parents are captured at conception; they cannot "
                    "be recovered from the child afterwards. Rolls to a "
                    "new numbered file every 256 records."
                ),
                # The "Birth" records come from Show Parents' companion, which
                # sees every birth; conceptions are logged without it.
                "needs_on": [
                    {
                        "id": "vv1_write_village_statistics",
                        "for": (
                            "the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled)"
                        ),
                    },
                    {
                        "id": "vv1_show_parents",
                        "for": "the \"Birth\" records (conceptions are logged without it)",
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
