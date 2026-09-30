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

The routine is __thiscall and ends in `ret 0x10` at both return sites
(0x43BCB7 and 0x43BCC8), so it takes four stack arguments. With E its entry
esp (the return address), they are at E+0x04..E+0x10, and it reads ALL FOUR --
tracked through its own `push edi` (0x43BBC0) and `push esi` (0x43BBF0):

    0x43BBC1  mov  edi, ecx                ; ecx = the villager RECORD ARRAY
    0x43BBD0  mov  eax, [esp+0x10]         ; E+0x0C  arg3, a skill selector
    0x43BBE2  mov  ecx, [esp+0x14]         ; E+0x10  arg4 (when arg3 != 2)
    0x43BBE6  mov  edx, [esp+0x08]         ; E+0x04  arg1, the mother's index
    0x43BBEA  imul edx, edx, 0x3D8         ;         the record stride
    0x43BBF1  lea  esi, [edx + edi]        ; esi = the MOTHER's record
    0x43BC00  mov  edx, [esp+0x10]         ; E+0x08  arg2 (after push esi)
    0x43BC04  mov  [esi+0x394], edx        ; into the mother, read at delivery

and the call site corroborates the mapping:

    0x43DD19  push edi                     ; arg4
    0x43DD20  mov  edx, [esp+0x1C]         ; the father's record
    0x43DD24  mov  eax, [edx + 0x36C]      ; one field of his (not an id)
    0x43DD2A  push ecx                     ; arg3
    0x43DD2F  push eax                     ; arg2 = his +0x36C, a VALUE
    0x43DD30  push ecx                     ; arg1 = the mother's index
    0x43DD31  mov  ecx, esi                ; record array base
    0x43DD33  call sub_43BBC0

No argument is unread, so none can carry anything for the patcher; see the
father-capture notes below for where he is found instead.

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
# Three 0x20 trampolines, the shared log body at 0x60, and the two strings at
# 0x120/0x140. The tail of the span is unused; it is kept at 0x200 because the
# composed address below was measured against a 0x200 claim. The stock zero
# run at 0x56900 is 0x700 bytes, so this is well inside it; the check in
# _emit still asserts the whole span is zero.
CAVE_SIZE = 0x200
TRAMPOLINE_SLOT = 0x20
LOG_OFFSET = 0x60
# From the shared log body's entry esp to E, the conception routine's entry
# esp: its own return (4) + pushad (0x20) + the routine's two pushes (8).
LOG_ENTRY_TO_E = 0x04 + 0x20 + 0x08

# --- the father capture -----------------------------------------------------
#
# VV1 stores NOTHING about the father in the mother's record, so unlike VV2-VV5
# there is no field to read at the success tails. His record exists only in the
# CALLER's frame, where the game loads exactly one field off it (+0x36C) and
# passes that value on.
#
# sub_43BBC0 has six callers and no indirect references:
#
#     0x43DD33  0x43DD54  0x43DD7B  0x43DD94  0x447031  0x447238
#
# THE ROUTINE READS ALL FOUR OF ITS ARGUMENTS. There is no dead slot to carry
# him in, and an earlier version of this feature that assumed one corrupted
# the game. Undoing the routine's own pushes (push edi at 0x43BBC0, push esi at
# 0x43BBF0), with E the esp at entry (the return address) and arg1..arg4 at
# E+0x04..E+0x10:
#
#     0x43BBD0  mov eax,[esp+0x10]    esp=E-4   E+0x0C  arg3  skill selector
#     0x43BBE2  mov ecx,[esp+0x14]    esp=E-4   E+0x10  arg4  (when arg3 != 2)
#     0x43BBE6  mov edx,[esp+0x08]    esp=E-4   E+0x04  arg1  the mother's index
#     0x43BC00  mov edx,[esp+0x10]    esp=E-8   E+0x08  arg2  the father's +0x36C
#     0x43BC04  mov [esi+0x394],edx             stored into the MOTHER
#
# 0x43BBD0 and 0x43BC00 carry the same displacement but not the same argument:
# `push esi` sits between them. The earlier design missed that, overwrote arg2
# with the father's record pointer, and so wrote a pointer into the mother's
# +0x394. Delivery reads that field at 0x42EF39 and compares it with 0xC7 to
# choose a special child-creation path at 0x42EF5F, so the patch changed what
# the stock game did at birth. The same design also lost the father outright on
# three paths (the twins tail read a return address; site 0x447238 stored the
# mother's index; site 0x447031's fallthrough stored his record + 0x348).
#
# So NOTHING at the call sites is patched now. Every call runs exactly the
# stock bytes, every argument is the stock value, and the mother's +0x394 is
# whatever the stock game writes. The success-tail trampolines instead find the
# father in the caller's own frame, which is still intact above the routine's:
# they identify the caller by the RETURN ADDRESS at E and read him from where
# that caller keeps him. Re-derived from the stock disassembly for each site:
#
#   0x43DD33 / 0x43DD54 (return 0x43DD38 / 0x43DD59)
#       0x43DD19 push edi, so G = esp after it. The +0x36C is loaded off
#       [G+0x1C] (0x43DD20 mov edx,[esp+0x1C] / 0x43DD41 mov eax,[esp+0x1C]),
#       then three pushes and the call make E = G-0x10. He is [E+0x2C].
#
#   0x43DD7B / 0x43DD94 (return 0x43DD80 / 0x43DD99)
#       The +0x36C is loaded off EBP (0x43DD70 / 0x43DD89). EBP is not in
#       any stack slot, but nothing between there and the tails writes it:
#       sub_43BBC0 never names ebp, and its two callees (the capacity
#       predicate 0x43A1A0 and rand 0x402F10) preserve it as MSVC callee-saved
#       registers. The trampoline's pushad leaves it live. He is EBP.
#
#   0x447031 / 0x447238 (return 0x447036 / 0x44723D), the two pairing scans
#       Both are the same shape, with F the scan's frame (esp after the rand
#       argument is cleaned up) and E = F-0x14 (four pushes and the call):
#           [F+0x10] = A, a record pointer        = [E+0x24]
#           [F+0x18] = B's record + 0x348 (cursor) = [E+0x2C]
#       and the branch at 0x446FE6 / 0x4471EB, `cmp [A+0x350],2 ; jne`:
#           equal     -> A is the mother; father's +0x36C is read off the
#                        cursor as [cursor+0x24] (0x447004 / 0x4471FF), so
#                        he is [E+0x2C] - 0x348.
#           not equal -> B is the mother; father's +0x36C is read off A
#                        (0x447020 / 0x44721D), so he is [E+0x24].
#       The trampoline re-evaluates that same comparison. sub_43BBC0 writes
#       the mother's +0x358, +0x35C, +0x38C, +0x390 and +0x394 and never
#       +0x350, so the answer at the tail is the answer the caller acted on.
#
# An unknown return address yields no father, which the companion reports as
# "(not captured for this birth)" -- never a stranger.
CONCEPTION_VA = 0x0043BBC0
FATHER_FROM_FRAME_2C = "frame+0x2C"      # [E+0x2C] is his record
FATHER_FROM_EBP = "ebp"                  # EBP is his record
FATHER_FROM_SCAN = "scan"                # the pairing-scan branch, see above
FATHER_SOURCES = (
    # (call VA, return VA, how)
    (0x0043DD33, 0x0043DD38, FATHER_FROM_FRAME_2C),
    (0x0043DD54, 0x0043DD59, FATHER_FROM_FRAME_2C),
    (0x0043DD7B, 0x0043DD80, FATHER_FROM_EBP),
    (0x0043DD94, 0x0043DD99, FATHER_FROM_EBP),
    (0x00447031, 0x00447036, FATHER_FROM_SCAN),
    (0x00447238, 0x0044723D, FATHER_FROM_SCAN),
)
# In the scan frames: A at [E+0x24], the cursor at [E+0x2C], and the cursor
# points 0x348 into B's record (0x446E70/0x447055 start it at
# this+0x3D770 = record[255]+0x348 and step it by the 0x3D8 stride).
SCAN_A_AT = 0x24
SCAN_CURSOR_AT = 0x2C
SCAN_CURSOR_BIAS = 0x348
SCAN_GENDER = 0x350
FRAME_FATHER_AT = 0x2C

# The stock bytes those derivations rest on, from the first father load to the
# return address. The build refuses an executable where any of them differ, so
# a different build of the game cannot be read with this table.
FATHER_SOURCE_STOCK = (
    (0x0043DD19, (
        "577D218B4C24148B54241C8B826C030000518B4C242850518BCEE888"
        "DEFFFF"
    )),
    (0x0043DD3D, (
        "8B5424188B44241C8B886C030000528B54242851528BCEE867DEFFFF"
    )),
    (0x0043DD69, (
        "577D198B4424148B8D6C0300005051538BCEE840DEFFFF"
    )),
    (0x0043DD85, (
        "8B5424188B856C0300005250538BCEE827DEFFFF"
    )),
    (0x00446FE2, (
        "8B54241083BA50030000026A64751CE81ABFFBFF8B54242C83C40483"
        "F8328B4424188B4824577D2253EB20E8FEBEFBFF8B54241883C40483"
        "F8328B4424108B886C030000577D0353EB0155518BCE52E88A4BFFFF"
    )),
    (0x004471E7, (
        "8B44241083B850030000026A64751EE815BDFBFF8B4C241C8B512483"
        "C40483F8328B442428578BCE7D2453EB22E8F7BCFBFF8B4C24148B91"
        "6C03000083C40483F8328B442414578BCE7D0353EB01555250E88349"
        "FFFF"
    )),
)

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


def _father_resolver_asm() -> str:
    """The assembly that leaves the father's record pointer in ebx, or 0.

    Runs inside log_conception, whose entry esp is: return into the trampoline
    at +0x00, the trampoline's pushad frame at +0x04..+0x23, and the success
    tail's own esp at +0x24. Every tail is inside the routine's `push edi` /
    `push esi` pair (the twins tail 0x43BCBA is reached only by jumps from
    0x43BC71/0x43BC7B/0x43BC8A, before the pops -- it sits after the `ret 0x10`
    at 0x43BCB7, not after the pops at 0x43BCC6/0x43BCC7), so E, the routine's
    entry esp holding the return address into the caller, is +0x24+8 = +0x2C.
    """
    lines = [
        f"    lea edx, [esp + 0x{LOG_ENTRY_TO_E:X}]",
        "    mov ecx, dword ptr [edx]",
        "    xor ebx, ebx",
    ]
    labels = {
        FATHER_FROM_FRAME_2C: "father_in_frame",
        FATHER_FROM_EBP: "father_in_ebp",
        FATHER_FROM_SCAN: "father_in_scan",
    }
    for _call_va, return_va, how in FATHER_SOURCES:
        lines.append(f"    cmp ecx, 0x{return_va:X}")
        lines.append(f"    je {labels[how]}")
    lines += [
        "    jmp father_known",
        "father_in_scan:",
        f"    mov ebx, dword ptr [edx + 0x{SCAN_A_AT:X}]",
        f"    cmp dword ptr [ebx + 0x{SCAN_GENDER:X}], 2",
        "    jne father_known",
        f"    mov ebx, dword ptr [edx + 0x{SCAN_CURSOR_AT:X}]",
        f"    sub ebx, 0x{SCAN_CURSOR_BIAS:X}",
        "    jmp father_known",
        "father_in_frame:",
        f"    mov ebx, dword ptr [edx + 0x{FRAME_FATHER_AT:X}]",
        "    jmp father_known",
        "father_in_ebp:",
        "    mov ebx, ebp",
        "father_known:",
    ]
    return "\n".join(lines)


def _emit(source: bytes, cave_va: int, cave_file: int) -> tuple[list[dict], bytes]:
    """Assemble the trampolines and hook rewrites for one cave address."""

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
    # The father table is only valid for the exact caller code it was derived
    # from, so every window it rests on is checked, and so is every call.
    for window_va, expected_hex in FATHER_SOURCE_STOCK:
        expected = bytes.fromhex(expected_hex)
        at = window_va - 0x400000
        if source[at : at + len(expected)] != expected:
            raise RuntimeError(
                f"stock bytes at {window_va:#x} are not the caller code the "
                f"father table was derived from"
            )
    for call_va, return_va, _how in FATHER_SOURCES:
        stock_call = assemble(f"call 0x{CONCEPTION_VA:X}", call_va)
        if source[call_va - 0x400000 : call_va - 0x400000 + 5] != stock_call:
            raise RuntimeError(
                f"stock bytes at {call_va:#x} are not a call to the "
                f"conception routine"
            )
        if return_va != call_va + len(stock_call):
            raise RuntimeError(f"return address for {call_va:#x} is wrong")
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
    log_va = cave_va + LOG_OFFSET

    payload = bytearray(CAVE_SIZE)
    patches: list[dict[str, object]] = []

    # The shared body every trampoline calls: find the father in the caller's
    # frame, load the companion, and hand it (game, records, mother, father).
    #
    # It runs inside the trampoline's pushad/popad bracket, so it may clobber
    # any register. ebx carries the father across the loader calls because
    # GetModuleHandleA, LoadLibraryA and GetProcAddress preserve it (stdcall
    # callee-saved). The records and the mother are read from the pushad frame
    # -- saved edi at +0x04 and saved esi at +0x08 from this routine's entry
    # esp -- because esi and edi are what the routine holds at every tail:
    # edi = the record array (0x43BBC1 mov edi,ecx), esi = the mother's record
    # (0x43BBF1 lea esi,[edx+edi]); the stolen instruction that overwrites edi
    # is replayed only after popad.
    #
    # Every failure branch returns before any argument push, and the export is
    # __stdcall with four arguments, so every path returns with esp unchanged.
    log_code = assemble(
        f"""
            {_father_resolver_asm()}
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
                push ebx
                push dword ptr [esp + 0x0C]
                push dword ptr [esp + 0x0C]
                push {GAME_ID}
                call eax
            done:
                ret
        """,
        log_va,
    )
    if LOG_OFFSET + len(log_code) > DLL_NAME_OFFSET:
        raise RuntimeError(
            f"the shared log body is {len(log_code):#x} bytes and runs into "
            f"the strings at {DLL_NAME_OFFSET:#x}"
        )
    payload[LOG_OFFSET : LOG_OFFSET + len(log_code)] = log_code

    for index, (tail_va, tail_file) in enumerate(zip(TAIL_VAS, TAIL_FILES)):
        # A DISTINCT name, not a reassignment of cave_va: overwriting the base
        # here left the singleton trampoline below computing its own slot from
        # an already-advanced base, so its rejoin jumped short -- into the
        # middle of the routine rather than to the epilogue.
        slot_va = cave_va + index * TRAMPOLINE_SLOT
        code = assemble(
            f"""
                pushad
                call 0x{log_va:X}
                popad
                mov edi, dword ptr [edi + 0x3E010]
                jmp 0x{tail_va + len(TAIL_STOLEN):X}
            """,
            slot_va,
        )
        if len(code) > TRAMPOLINE_SLOT:
            raise RuntimeError(
                f"trampoline {index} is {len(code):#x} bytes, over "
                f"{TRAMPOLINE_SLOT:#x}"
            )
        payload[index * TRAMPOLINE_SLOT : index * TRAMPOLINE_SLOT + len(code)] = code

        # Divert the tail: a five-byte jmp plus one nop replaces the six-byte
        # stolen instruction exactly, so nothing downstream shifts.
        entry = assemble(f"jmp 0x{slot_va:X}", tail_va)
        entry = entry + b"\x90" * (len(TAIL_STOLEN) - len(entry))
        if len(entry) != len(TAIL_STOLEN):
            raise RuntimeError("tail entry does not match the stolen byte count")

        patches.append(
            {
                # The renderer parses `offset` with int(value, 0) and reads
                # `before`/`after`; data/statistics_features.json is the
                # schema to match.
                "offset": f"0x{tail_file:X}",
                "before": TAIL_STOLEN.hex().upper(),
                "after": entry.hex().upper(),
                "purpose": (
                    "Divert the "
                    + ("triplets" if index == 0 else "twins")
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
    # crash the rejection path. Both branches are inside the routine's two
    # pushes, like the tails, so the shared body finds the caller's frame at
    # the same place.
    single_cave_va = cave_va + 2 * TRAMPOLINE_SLOT
    single_code = assemble(
        f"""
            pushad
            call 0x{log_va:X}
            popad
            jmp 0x{EPILOGUE_VA:X}
        """,
        single_cave_va,
    )
    if len(single_code) > TRAMPOLINE_SLOT:
        raise RuntimeError("singleton trampoline overflows its slot")
    payload[2 * TRAMPOLINE_SLOT : 2 * TRAMPOLINE_SLOT + len(single_code)] = single_code

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

    # No call site is patched. The six calls into sub_43BBC0 run exactly the
    # stock bytes with exactly the stock arguments; see FATHER_SOURCES.

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
                "Three trampolines -- triplets, twins and singletons -- the "
                "shared body they call, which finds the father in the "
                "calling code's own frame and loads the companion, and the "
                "DLL and export names. All logging logic lives in the "
                "companion DLL; only the call into it is in the executable."
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
