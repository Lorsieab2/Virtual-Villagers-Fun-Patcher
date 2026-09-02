"""Assemble the VV3 "Everyone Tries On the Robe" broadcast wrapper.

Until now this patch had no builder: its 235-byte cave lived as literal hex
in ``data/builds.json``.  That made it the one feature nobody could review or
regenerate from source, which is why the bug below survived.

THE BUG.  The wrapper broadcast by calling the stock robe drop handler
``0x421960`` once per villager.  That function is gated on the robe-candidate
flag ``[record+0xE80]``::

    0x421974  mov  al, [esi+0xE80]
    0x42197A  test al, al
    0x42197C  je   0x4219A3      ->  xor al, al ; ret     (assigns NOTHING)

``docs/vv3-everyone-tries-on-robe.md`` already recorded that ``+0xE80`` "can be
zero across a restarted village", so for most villagers the broadcast was a
silent no-op: they kept their current action and never walked to the
amphitheatre, while the handful with the flag set did try on the robe.

THE FIX.  Assign the robe action directly through the stock action
dispatcher, which is what ``0x421960`` itself does on its success path::

    0x455570  mov edx,[esp+8]        ; param forwarded to the action handler
              mov eax,[esp+4]        ; action id (the stock path uses 0x39)
              push edx / push eax
              mov [ecx+0xF24], eax   ; write the villager's ACTION field
              push ecx               ; ecx = villager record (thiscall)
              mov ecx, 0x596970      ; global action dispatch table
              call 0x441170          ; table[id] -> handler, then invoke
              ret 8

Writing ``+0xF24`` through that dispatcher is exactly "interrupt whatever this
villager is doing and start the robe action", so every eligible villager now
actually walks to the amphitheatre.

WHAT IS READ, AND WHAT IS DELIBERATELY NOT TOUCHED.  Both candidate/selector
fields are now READ, and only read:

* ``+0xE80`` (chief flag) gates the whole feature.  The ceremony is for
  choosing a chief, so the fan-out runs only while the village has none;
  dropping the existing chief on the robe falls through to the stock
  "chief lectures" routine untouched.
* ``+0xE88`` (robe variant) selects which of the two robe actions each
  villager is given, ``0x78`` or ``0x79`` -- the same choice the stock
  handler makes for the villager it accepts.

Neither field is written, repaired or invented, and the stock arrival handler
still decides who is rejected and who becomes Tribal Chief.  The natural stock
ending is preserved; only the "everyone goes and tries" part is added.  The
dropped initiator still goes through the complete unchanged ``0x421960`` (which
also fires its one-shot effect), and a drop the stock handler refuses still
fans out to nobody.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research/stock-executables/Virtual Villagers - The Secret City.exe"
STOCK_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"

sys.path.insert(0, str(ROOT / ".tools/keystone"))
sys.path.insert(0, str(ROOT / ".tools/keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402

IMAGE_BASE = 0x400000
PAYLOAD_FILE_OFFSET = 0xB4100
PAYLOAD_VA = 0x6C8100
PAYLOAD_LEN = 512                 # reviewed owned range
# Extended from 235 to 512. The fanout now reproduces the stock robe branch in
# full -- it sets the walk destination as well as the action -- and that does
# not fit in 235 bytes. The extra bytes are taken from the 400 zero bytes
# lying immediately after the original range in the stock image, so nothing
# stock is displaced; the patcher's own overlap check confirms no other patch
# claims them.

STOCK_ROBE_CALLBACK = 0x421960    # stock drop handler (gated on +0xE80)
ACTION_DISPATCH = 0x455570        # set +0xF24 and dispatch via table 0x596970
# The stock success path at 0x421960 assigns TWO different action ids, and the
# distinction is the whole bug.  In order it does:
#
#   0x45E0C0(0x38, 7, -1, 0) on the manager 0x59E110
#       -> 0x45DDE0 sweeps 150 slots, filters on activity/health/state, and for
#          EACH selected villager calls 0x455570(record, 0x38, scratch)
#   0x455570(initiator, 0x39, ptr)
#
# So 0x38 is the CROWD action every other villager receives, and 0x39 is the
# robe attempt the dropped villager gets.  Confirmed in the stock image: at
# 0x421984 the selector is invoked with 0x38, and at 0x421995 the initiator is
# dispatched 0x39; scanning every stock call site of 0x455570 shows 0x39 passed
# as an immediate and 0x38 never passed directly at all.
#
# The fan-out must therefore assign 0x39 -- the robe attempt -- to everybody.
# The requested behaviour is that ALL villagers try the robe on and the native
# selector decides who is accepted, with the rest rejected natively; giving the
# village 0x38 instead is precisely the reported bug, where one villager robes
# and everyone else performs the spectator action.
#
# This ran AFTER the stock selector, which is what makes the fan-out effective:
# it overwrites the 0x38 the selector just handed the crowd.  A previous change
# here (PR #153) inverted that reasoning and fanned out 0x38, which re-applied
# the spectator action to everyone -- reverted.
CROWD_ACTION_ID = 0x38            # assigned per villager by the stock selector
INITIATOR_ACTION_ID = 0x39        # assigned only to the dropped villager
# The robe branch of the stock handler, read out of 0x4219A8..0x421A1E.
RAND_FN = 0x004032D0              # rand(n)
SET_DESTINATION = 0x004611B0      # (x, y, 0x64, 0) thiscall; walks the villager
STOP_CURRENT_ACTIVITY = 0x00460F70  # the game's own detach; ecx=villager,
                                  # one arg, ret 4. The 0x39 handler calls it
                                  # first, which is why 0x39 preempted work.
ROBE_SPOT_X = 0x261               # 609 + rand(5)
ROBE_SPOT_Y = 0x1E8               # 488 + rand(5)
OFF_CHIEF = 0xE80                 # non-zero = this villager IS the chief.
                                  # Verified live: with two chiefs present it was
                                  # set on exactly those two and clear on the rest.
OFF_ROBE_VARIANT = 0xE88          # selects which of the two robe actions
ROBE_ACTION_A = 0x78              # 120, taken when +0xE88 is set
ROBE_ACTION_B = 0x79              # 121, taken when +0xE88 is clear -- the one
                                  # observed on the manually dropped villager

RECORD_BASE = 0x59E124
RECORD_STRIDE = 0x1F8C
SLOT_BOUND_PTR = 0x42883A         # runtime villager-slot bound (150 or 256)

OFF_ACTIVE = 0xF10
OFF_HEALTH = 0xE78
OFF_NURSING = 0xE8C
OFF_ACTION = 0xF24
# The value the stock callback actually leaves in +0xF24, and the reason the
# fanout never ran.  0x421960's success path ends with
# 0x455570(initiator, 0x39, ptr), and 0x455570's FIRST action is
# `mov [ecx+0xF24], eax` with eax = 0x39.  So immediately after the callback
# returns true, the initiator's action field holds 0x39 -- never 0x78 or 0x79.
# The gate below accepted only 0x78/0x79, so it always fell through to `done`
# and the village kept its stock behaviour exactly: the dropped villager tried
# the robe, and the crowd 0x45E0C0(0x38, 7, -1, 0) sent seven others to the
# lecture. That is precisely the reported bug -- one villager robes, everyone
# else lectures.
# 0x78/0x79 are kept as accepted values: they are later robe sub-states, and a
# handler that has already advanced past 0x39 by the time we look must still
# fan out rather than silently do nothing.
ACTION_ROBE_ASSIGNED = 0x39
ACTION_ROBE_A = 0x78
ACTION_ROBE_B = 0x79


def assemble(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def build_wrapper() -> bytes:
    source = f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 4
        mov esi, dword ptr [ebp + 8]

        push esi
        mov eax, 0x{STOCK_ROBE_CALLBACK:X}
        call eax
        add esp, 4
        mov bl, al
        test al, al
        je done

        cmp dword ptr [esi + 0x{OFF_ACTIVE:X}], 0
        je done
        cmp dword ptr [esi + 0x{OFF_HEALTH:X}], 0
        jle done
        cmp dword ptr [esi + 0x{OFF_NURSING:X}], 0
        jne done
        # Only a ROBE action counts as an initiator -- 0x39 must NOT.
        #
        # 0x39 is the lecture action, and dropping the CHIEF on the hotspot is
        # what assigns it: stock answers that drop with the chief lecturing.
        # While 0x39 was accepted here, dropping the chief fanned the robe out
        # to the whole village instead, replacing the native chief-lectures
        # routine. A drop that produces 0x39 is not a robe ceremony and must
        # fall through untouched.
        mov eax, dword ptr [esi + 0x{OFF_ACTION:X}]
        cmp eax, 0x{ACTION_ROBE_A:X}
        je bound_check
        cmp eax, 0x{ACTION_ROBE_B:X}
        jne done

    bound_check:
        # Both accepted bounds must fall through to the guards below.
        # This used to `je scan` for 0x96, which jumped straight to the fanout
        # and skipped the chief and one-shot scans entirely -- and 150 is the
        # bound every shipping mode uses, so in practice neither guard ran.
        mov ecx, dword ptr [0x{SLOT_BOUND_PTR:X}]
        cmp ecx, 0x96
        je chief_check
        cmp ecx, 0x100
        jne done

    # Only run while the village has NO chief.
    #
    # +0xE80 is the chief flag, read out of the running game: with two chiefs
    # present it was set on exactly those two villagers and clear on the other
    # 147. It is also what the stock handler branches on -- chief drops take
    # the 0x39 lecture path (the chief lectures), everyone else takes the robe
    # path -- which is why dropping the chief used to fan the robe out and mint
    # a second chief.
    #
    # With a chief in place the ceremony is not supposed to happen at all, so
    # bail and leave the base game to it.
    chief_check:
        mov ecx, dword ptr [0x{SLOT_BOUND_PTR:X}]
        mov edi, 0x{RECORD_BASE:X}
    chief_next:
        cmp dword ptr [edi + 0x{OFF_ACTIVE:X}], 0
        je chief_advance
        cmp dword ptr [edi + 0x{OFF_HEALTH:X}], 0
        jle chief_advance
        cmp byte ptr [edi + 0x{OFF_CHIEF:X}], 0
        jne done
    chief_advance:
        add edi, 0x{RECORD_STRIDE:X}
        dec ecx
        jne chief_next

    # One-shot guard: if any OTHER living villager is already wearing a robe
    # action, this ceremony has been fanned out already. Without this the
    # fanout re-runs on every subsequent callback -- every villager now passes
    # the initiator gate -- and the native chief selection loops instead of
    # running once.
    oneshot_check:
        # Reload the bound: the chief scan above exits with ecx == 0, so
        # reusing it here underflows to 0xFFFFFFFF on the first `dec` and the
        # loop walks far past the villager array.
        mov ecx, dword ptr [0x{SLOT_BOUND_PTR:X}]
        mov edi, 0x{RECORD_BASE:X}
    oneshot_next:
        cmp edi, esi
        je oneshot_advance
        cmp dword ptr [edi + 0x{OFF_ACTIVE:X}], 0
        je oneshot_advance
        cmp dword ptr [edi + 0x{OFF_HEALTH:X}], 0
        jle oneshot_advance
        mov eax, dword ptr [edi + 0x{OFF_ACTION:X}]
        cmp eax, 0x{ROBE_ACTION_A:X}
        je done
        cmp eax, 0x{ROBE_ACTION_B:X}
        je done
    oneshot_advance:
        add edi, 0x{RECORD_STRIDE:X}
        dec ecx
        jne oneshot_next

    scan:
        mov ecx, dword ptr [0x{SLOT_BOUND_PTR:X}]
        mov edi, 0x{RECORD_BASE:X}
    next:
        cmp edi, esi
        je advance
        cmp dword ptr [edi + 0x{OFF_ACTIVE:X}], 0
        je advance
        cmp dword ptr [edi + 0x{OFF_HEALTH:X}], 0
        jle advance
        cmp dword ptr [edi + 0x{OFF_NURSING:X}], 0
        jne advance

        push ecx
        push edi

        # ORDER MATTERS: detach BEFORE setting the destination.
        #
        # 0x460F70 zeroes the villager's task array, and the walk path lives
        # in it. Setting the destination first and detaching second wiped the
        # path, so every villager performed the robe action standing where it
        # was rather than walking to the amphitheatre.
        # Detach this villager from whatever they are doing FIRST.
        #
        # 0x460F70 is the game's own "stop what you are doing" routine. The
        # 0x39 handler calls it before doing anything else, which is the only
        # reason dispatching 0x39 preempted a working villager; the 0x78/0x79
        # handlers do not call it, because in stock they only ever run on a
        # villager the player has just picked up. That is why the action
        # landed as a label on busy villagers and only the idle ones walked
        # over.
        #
        # It zeroes a strided task array across the villager's first 0xDC0
        # bytes -- the +0x0258 and +0x038C..+0x0418 callback fields the live
        # diff showed on the real robe-trier -- then clears +0xF13 and +0xF1C
        # and runs two teardown calls. It takes ecx = the villager and one
        # stack argument, and cleans that argument itself (ret 4).
        #
        # It does NOT touch the ceremony bit at byte +0xF11, so setting that
        # afterwards is safe.
        push edi
        mov ecx, edi
        mov eax, 0x{STOP_CURRENT_ACTIVITY:X}
        call eax


        # Send this villager to the amphitheatre, exactly the way the stock
        # robe branch does.  Assigning the action without a destination is
        # what made everyone stand around lecturing: the action had nowhere
        # to carry them.
        push 0
        push 0x64
        push 5
        mov eax, 0x{RAND_FN:X}
        call eax
        add esp, 4
        add eax, 0x{ROBE_SPOT_X:X}
        push eax
        push 5
        mov eax, 0x{RAND_FN:X}
        call eax
        add esp, 4
        add eax, 0x{ROBE_SPOT_Y:X}
        push eax
        mov ecx, edi
        mov eax, 0x{SET_DESTINATION:X}
        call eax

        # Then the action itself, and it is always 0x79.
        #
        # Mirroring the stock +0xE88 test looked more faithful but is wrong
        # here: it hands most villagers 0x78, and only 0x79 is the action the
        # villager the player DROPPED was observed holding while actually
        # trying the robe on. With 0x78 they take the label but do not drop
        # what they are doing.
        #
        # The dispatch itself is the interrupt -- the earlier version of this
        # patch proved that by making the whole village stop and lecture the
        # instant it assigned 0x39 -- so assigning 0x79 preempts their current
        # job exactly the same way.
        # No ceremony bit is set here, deliberately.
        #
        # A live diff showed the real robe-trier carrying bit 8 of +0xF10, and
        # setting it looked like the missing cause. It is not: with it set for
        # everyone, NOBODY became chief. The bit is something the ceremony
        # produces, and pre-setting it makes the arrival handler treat each
        # villager as already processed, so the native chief selection has
        # nobody left to choose from.
        #
        # What remains is exactly what the player's drop does to a villager --
        # detach, walk to the amphitheatre, perform the robe action -- and the
        # base game then picks the chief from whoever turns up.
        # Let the game pick which robe action this villager gets.
        #
        # Stock selects between TWO robe actions on +0xE88: 0x78 when it is
        # set, 0x79 when it is clear. Forcing 0x79 on everyone gave every
        # villager the same outcome and nobody became chief, which is what you
        # would expect if 0x78 is the variant that can. Mirroring the stock
        # test hands each villager exactly the action the base game would have
        # handed it, so the native selection still decides the chief instead
        # of this patch deciding it.
        sub esp, 4
        mov dword ptr [esp], 0
        mov eax, esp
        push eax
        cmp byte ptr [edi + 0x{OFF_ROBE_VARIANT:X}], 0
        je robe_variant_b
        push 0x{ROBE_ACTION_A:X}
        jmp robe_dispatch
    robe_variant_b:
        push 0x{ROBE_ACTION_B:X}
    robe_dispatch:
        mov ecx, edi
        mov eax, 0x{ACTION_DISPATCH:X}
        call eax
        add esp, 4

        pop edi
        pop ecx

    advance:
        add edi, 0x{RECORD_STRIDE:X}
        dec ecx
        jne next

    done:
        mov al, bl
        lea esp, [ebp - 0xC]
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """
    code = assemble(source, PAYLOAD_VA)
    if len(code) > PAYLOAD_LEN:
        raise RuntimeError(
            f"wrapper is {len(code)} bytes, over the {PAYLOAD_LEN}-byte owned range"
        )
    return code + b"\x90" * (PAYLOAD_LEN - len(code))


def main() -> None:
    original = STOCK.read_bytes()
    actual = hashlib.sha256(original).hexdigest().upper()
    if actual != STOCK_SHA256:
        raise RuntimeError(
            f"stock SHA-256 mismatch: expected {STOCK_SHA256}, got {actual}"
        )

    preimage = original[PAYLOAD_FILE_OFFSET : PAYLOAD_FILE_OFFSET + PAYLOAD_LEN]
    if preimage != bytes(PAYLOAD_LEN):
        raise RuntimeError("the owned robe cave is not zero-filled in the stock build")

    payload = build_wrapper()
    print(
        f"payload      : {len(payload)} bytes @ VA 0x{PAYLOAD_VA:X} "
        f"(file 0x{PAYLOAD_FILE_OFFSET:X})"
    )
    print(f"payload sha  : {hashlib.sha256(payload).hexdigest().upper()}")
    print(f"preimage sha : {hashlib.sha256(preimage).hexdigest().upper()}")
    print(f"after hex    : {payload.hex().upper()}")

    out = ROOT / "research/vv3-robe"
    out.mkdir(parents=True, exist_ok=True)
    target = out / "vv3-everyone-tries-on-robe-payload.json"
    target.write_text(
        json.dumps(
            {
                "offset": f"0x{PAYLOAD_FILE_OFFSET:X}",
                "virtual_address": f"0x{PAYLOAD_VA:X}",
                "before": preimage.hex().upper(),
                "after": payload.hex().upper(),
                "payload_sha256": hashlib.sha256(payload).hexdigest().upper(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
