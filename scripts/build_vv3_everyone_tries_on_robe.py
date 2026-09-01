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

WHAT IS DELIBERATELY NOT TOUCHED.  The candidate/selector state ``+0xE80`` and
``+0xE88`` is never read, written, repaired or invented, and the stock arrival
handler still decides who is rejected and who becomes Tribal Chief.  The
natural stock ending is preserved; only the "everyone goes and tries" part is
added.  The dropped initiator still goes through the complete unchanged
``0x421960`` (which also fires its one-shot effect), and a drop the stock
handler refuses still fans out to nobody.
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
PAYLOAD_LEN = 235                 # the reviewed owned range, kept byte-for-byte

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
        mov eax, dword ptr [esi + 0x{OFF_ACTION:X}]
        cmp eax, 0x{ACTION_ROBE_ASSIGNED:X}
        je bound_check
        cmp eax, 0x{ACTION_ROBE_A:X}
        je bound_check
        cmp eax, 0x{ACTION_ROBE_B:X}
        jne done

    bound_check:
        mov ecx, dword ptr [0x{SLOT_BOUND_PTR:X}]
        cmp ecx, 0x96
        je scan
        cmp ecx, 0x100
        jne done

    scan:
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
        sub esp, 4
        mov dword ptr [esp], 0
        mov eax, esp
        push eax
        push 0x{INITIATOR_ACTION_ID:X}
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
