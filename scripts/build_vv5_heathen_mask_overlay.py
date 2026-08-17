"""VV5 Heathen-mask cosmetic overlay — SHIPPING render hook (per-villager).

Draws the chosen Heathen mask on a Believer with zero persistent state change and,
critically, without turning the believer's white selection ring red. The mask is
painted by the villager's own heathen render path; we only borrow it transiently.

The per-villager render fn ``0x4720E0`` draws, in order: the faction aura
(``0x472169``), the **selection ring** (``0x47244B`` — believer ``0x44f320`` vs
heathen ``0x44f3f0``, gated by the "is selected" test ``0x4653d0`` at
``0x472442``), then the head (gate ``0x472729``: believer head ``0x44f5e0`` /
heathen head ``0x44f4e0``), then the **mask overlay** (``0x472880``–``0x472903``,
which reads the colour fields ``+0x1CFC`` / ``+0x1CED`` / ``+0x1CEE``). It exits
through two identical epilogues (``0x472B0F`` and ``0x472B57``:
``add esp,0xA8 ; ret 8``).

So we bracket a transient faction flip to the window **after the ring, through the
end of the function**:

  * flip cave (hook at ``0x472481``, just past the ring block): for a Believer
    whose persistent choice byte ``+0x1BC0`` is 1..5, save the colour fields + the
    villager pointer, set the chosen colour, set faction ``+0x1CEC`` = 1, mark a
    guard. The aura and ring already drew with the real Believer faction, so the
    ring stays white; the head + mask now draw heathen.
  * restore cave (hook at both epilogues): if the guard is set, revert faction +
    colours, then run the displaced ``add esp,0xA8 ; ret 8``. NOTE ``esi`` is
    popped before the epilogue, so the villager pointer is taken from the saved
    slot, not ``esi``.

Choice byte written by the Change-Appearance mask picker:
    0 = none, 1 = Blue, 2 = Orange, 3 = Red, 4 = Purple, 5 = Tribal Chief
Colour fields (raw record offsets; ``esi`` = villager pointer in the render fn):
    blue -> all 0 ; orange -> +0x1CED=1 ; red -> +0x1CEE=1 ;
    purple -> +0x1CFC=12 ; chief -> +0x1CFC=13

Standalone overlay (not the Origins payload, which owns all of .shr and relocates
it via a committed IDA ledger): caves live in the .text slice
``0x4949B0..0x494B37`` (clear of the Clickable Tips + Origins caves); guard/save
slots live in free .data BSS ``0x7B1D00`` (verified stock-zero), never touching
.shr. build()'s free-check re-verifies the cave span is zero on the parent exe.

Note: this covers the in-village render. The Details-screen portrait draws the
villager through a different path and is handled separately.

Usage::

    python scripts/build_vv5_heathen_mask_overlay.py --input <patched.exe> --output <out.exe>
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

# flip site: just after the selection-ring block (esi = villager pointer here)
FLIP_SITE = 0x472481
FLIP_PREIMAGE = bytes.fromhex("8b8c24bc000000")   # mov ecx, [esp+0xbc] (7 bytes)
FLIP_RETURN = 0x472488

# the two identical epilogues (esi already popped): add esp,0xA8 ; ret 8
EPILOGUES = (0x472B0F, 0x472B57)
EPILOGUE_PREIMAGE = bytes.fromhex("81c4a8000000")  # add esp, 0xA8 (6 bytes)

# caves in the free .text slice 0x4949B0..0x494B37
CAVE_FLIP = 0x4949B0
CAVE_RESTORE = 0x494A70

# free .data BSS scratch (NOT .shr — that belongs to Origins). Verified stock-zero.
SLOT_ACTIVE = 0x7B1D00       # guard
SLOT_SCED = 0x7B1D04         # saved +0x1CED (orange)
SLOT_SCEE = 0x7B1D08         # saved +0x1CEE (red)
SLOT_SCFC = 0x7B1D0C         # saved +0x1CFC (colorfield)
SLOT_REC = 0x7B1D10          # saved villager pointer (esi at flip time)

# raw record field offsets from the villager pointer
CHOICE = 0x1BC0
FACTION = 0x1CEC
ORANGE = 0x1CED
RED = 0x1CEE
COLORFIELD = 0x1CFC


def _flip_asm() -> str:
    return f"""
        push eax
        push edx
        movzx eax, byte ptr [esi+{CHOICE}]
        test eax, eax
        je flip_done
        cmp eax, 5
        ja flip_done
        cmp byte ptr [esi+{FACTION}], 0
        jne flip_done
        mov byte ptr [{SLOT_ACTIVE}], 1
        mov [{SLOT_REC}], esi
        movzx edx, byte ptr [esi+{ORANGE}]
        mov [{SLOT_SCED}], edx
        movzx edx, byte ptr [esi+{RED}]
        mov [{SLOT_SCEE}], edx
        movzx edx, byte ptr [esi+{COLORFIELD}]
        mov [{SLOT_SCFC}], edx
        mov byte ptr [esi+{ORANGE}], 0
        mov byte ptr [esi+{RED}], 0
        mov byte ptr [esi+{COLORFIELD}], 0
        cmp eax, 2
        je flip_orange
        cmp eax, 3
        je flip_red
        cmp eax, 4
        je flip_purple
        cmp eax, 5
        je flip_chief
        jmp flip_setf
    flip_orange:
        mov byte ptr [esi+{ORANGE}], 1
        jmp flip_setf
    flip_red:
        mov byte ptr [esi+{RED}], 1
        jmp flip_setf
    flip_purple:
        mov byte ptr [esi+{COLORFIELD}], 12
        jmp flip_setf
    flip_chief:
        mov byte ptr [esi+{COLORFIELD}], 13
    flip_setf:
        mov byte ptr [esi+{FACTION}], 1
    flip_done:
        pop edx
        pop eax
        mov ecx, [esp+0xbc]
        jmp {FLIP_RETURN}
    """


def _restore_asm() -> str:
    return f"""
        cmp byte ptr [{SLOT_ACTIVE}], 0
        je restore_done
        push eax
        push edx
        mov eax, [{SLOT_REC}]
        mov byte ptr [eax+{FACTION}], 0
        mov edx, [{SLOT_SCED}]
        mov byte ptr [eax+{ORANGE}], dl
        mov edx, [{SLOT_SCEE}]
        mov byte ptr [eax+{RED}], dl
        mov edx, [{SLOT_SCFC}]
        mov byte ptr [eax+{COLORFIELD}], dl
        mov byte ptr [{SLOT_ACTIVE}], 0
        pop edx
        pop eax
    restore_done:
        add esp, 0xA8
        ret 8
    """


def build(patched: bytes) -> bytes:
    raw = bytearray(patched)
    pe = pefile.PE(data=bytes(raw), fast_load=True)
    ib = pe.OPTIONAL_HEADER.ImageBase

    def sect(name: bytes):
        return next(s for s in pe.sections if s.Name.rstrip(b"\x00") == name)

    text = sect(b".text")

    def v2f(va: int) -> int:
        return text.PointerToRawData + (va - (ib + text.VirtualAddress))

    if raw[v2f(FLIP_SITE):v2f(FLIP_SITE) + len(FLIP_PREIMAGE)] != FLIP_PREIMAGE:
        raise ValueError("flip-site preimage mismatch at 0x472481 — not a stock-derived VV5 render fn")
    for ep in EPILOGUES:
        if raw[v2f(ep):v2f(ep) + len(EPILOGUE_PREIMAGE)] != EPILOGUE_PREIMAGE:
            raise ValueError(f"epilogue preimage mismatch at 0x{ep:X}")

    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    flip = bytes(ks.asm(_flip_asm(), CAVE_FLIP)[0])
    restore = bytes(ks.asm(_restore_asm(), CAVE_RESTORE)[0])
    if CAVE_FLIP + len(flip) > CAVE_RESTORE:
        raise ValueError(f"flip cave ({len(flip)}B) overflows into restore cave at 0x{CAVE_RESTORE:X}")
    cave_end = CAVE_RESTORE + len(restore)
    if cave_end > 0x494B37:
        raise ValueError(f"restore cave ends 0x{cave_end:X}, past the free slice end 0x494B37")
    if any(raw[v2f(CAVE_FLIP) + i] for i in range(cave_end - CAVE_FLIP)):
        raise ValueError(f"cave 0x{CAVE_FLIP:X}..0x{cave_end:X} is not free padding")

    raw[v2f(CAVE_FLIP):v2f(CAVE_FLIP) + len(flip)] = flip
    raw[v2f(CAVE_RESTORE):v2f(CAVE_RESTORE) + len(restore)] = restore

    # flip hook: 5-byte jmp over the first 5 bytes of the 7-byte mov, nop the 2 leftovers
    raw[v2f(FLIP_SITE):v2f(FLIP_SITE) + 5] = b"\xE9" + struct.pack("<i", CAVE_FLIP - (FLIP_SITE + 5))
    raw[v2f(FLIP_SITE) + 5] = 0x90
    raw[v2f(FLIP_SITE) + 6] = 0x90
    # epilogue hooks: 5-byte jmp over the first 5 bytes of the 6-byte add, nop the leftover
    for ep in EPILOGUES:
        raw[v2f(ep):v2f(ep) + 5] = b"\xE9" + struct.pack("<i", CAVE_RESTORE - (ep + 5))
        raw[v2f(ep) + 5] = 0x90

    out = pefile.PE(data=bytes(raw))
    out.OPTIONAL_HEADER.CheckSum = out.generate_checksum()
    return out.write()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the VV5 Heathen-mask render overlay (per-villager, +0x1BC0-gated).")
    ap.add_argument("--input", type=Path, required=True, help="already-patched VV5 exe to layer onto")
    ap.add_argument("--output", type=Path, required=True, help="output exe path")
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build(args.input.read_bytes()))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
