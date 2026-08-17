"""VV5 Heathen-mask cosmetic overlay — SHIPPING render hook (per-villager).

Applies the transient faction-flip render technique as a standalone overlay that
can be layered on top of any already-patched VV5 exe (stock, or the Origins /
Task9 build). It wraps the per-villager render function ``0x4720E0`` and, for the
duration of one believer's render only, flips faction ``+0x1CEC`` to heathen and
sets the mask-colour fields so the game draws its own heathen head + mask (correct
position / blink / layering, via ``0x451DA0`` on atlas ``0x5258B8``). Every field
is restored via a return-address trampoline BEFORE the render function returns, so
the update loop never observes the flip — the villager stays a full believer in
every game system (population, faith, no deactivation). A re-entrancy guard keeps
a nested render from ever leaving the flip stuck.

Unlike the Step-1 prototype (which masked every believer), this reads the
persistent per-villager choice byte ``+0x1BC0`` written by the Change-Appearance
picker:

    0 = none, 1 = Blue, 2 = Orange, 3 = Red, 4 = Purple, 5 = Tribal Chief

Colour mapping (all transient, restored same-frame — proven live 2026-08-16):
    blue   -> orange=0, red=0, colorfield=0   (default heathen colour)
    orange -> +0x1CED (orange flag) = 1
    red    -> +0x1CEE (red flag)    = 1
    purple -> +0x1CFC (colorfield)  = 12
    chief  -> +0x1CFC (colorfield)  = 13

Why a standalone overlay and NOT the Origins payload: the Origins feature owns the
entire ``.shr`` section (PAYLOAD_VA 0x7B2000, size 0x1000) and relocates it in
expanded mode via a committed IDA relocation ledger that can't be extended with
fabricated entries. So this hook lives in a ``.text`` cave (0x494900, clear of the
Origins caves) and keeps its scratch in free ``.data`` BSS (0x7B1D00, verified
stock-zero and unused), never touching ``.shr``.

Registers at ``0x4720E0`` entry: ``ecx`` = manager base (must be preserved — the
render fn needs it), villager index at ``[esp+4]``. Only ``eax``/``edx`` are free
(``ebx``/``esi``/``edi``/``ebp`` are callee-saved and the render fn saves the
caller's values in its own prologue, so clobbering them here would corrupt the
caller). Record base ``= index*0x2F44 + ecx``; field ``F`` at ``[base + 0x48 + F]``.

Usage::

    python scripts/build_vv5_heathen_mask_overlay.py --input <patched.exe> --output <out.exe>
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

HOOK = 0x4720E0
HOOK_PREIMAGE = bytes.fromhex("81ECA8000000")  # sub esp, 0xA8
# The single large .text cave (0x494339..0x495000) is shared: Clickable Tips owns
# 0x494610..0x4949B0 and the Origins feature owns 0x4944C0 / 0x494B37 / 0x494EA0 /
# 0x494FBE. The free slice clear of BOTH is 0x4949B0..0x494B37 (391 bytes). The
# build() free-check re-verifies the whole span is zero on whatever parent exe is
# supplied, so any future collision fails loudly instead of corrupting a neighbour.
CAVE = 0x4949B0
RESTORE = 0x494AA0

# free .data BSS scratch (NOT .shr — that belongs to Origins). Verified stock-zero.
SLOT_ACTIVE = 0x7B1D00  # re-entrancy guard
SLOT_REC = 0x7B1D04     # saved record base (eax)
SLOT_RET = 0x7B1D08     # saved real return address
SLOT_SCED = 0x7B1D0C    # saved +0x1CED (orange flag)
SLOT_SCEE = 0x7B1D10    # saved +0x1CEE (red flag)
SLOT_SCFC = 0x7B1D14    # saved +0x1CFC (colorfield)

# field displacements from the record base eax (= index*0x2F44 + ecx); +0x48 esi bias
CHOICE_DISP = 0x48 + 0x1BC0   # 0x1C08 persistent mask choice
FACTION_DISP = 0x48 + 0x1CEC  # 0x1D34 "is heathen" faction byte
ORANGE_DISP = 0x48 + 0x1CED   # 0x1D35
RED_DISP = 0x48 + 0x1CEE      # 0x1D36
COLORFIELD_DISP = 0x48 + 0x1CFC  # 0x1D44 mask-variant / colour field


def _wrap_asm() -> str:
    return f"""
        cmp byte ptr [{SLOT_ACTIVE}], 0
        jne wrap_orig
        mov eax, [esp+4]
        imul eax, eax, 0x2F44
        add eax, ecx
        cmp byte ptr [eax+{FACTION_DISP}], 0
        jne wrap_orig
        movzx edx, byte ptr [eax+{CHOICE_DISP}]
        test edx, edx
        je wrap_orig
        cmp edx, 5
        ja wrap_orig
        mov byte ptr [{SLOT_ACTIVE}], 1
        mov [{SLOT_REC}], eax
        movzx edx, byte ptr [eax+{ORANGE_DISP}]
        mov [{SLOT_SCED}], edx
        movzx edx, byte ptr [eax+{RED_DISP}]
        mov [{SLOT_SCEE}], edx
        movzx edx, byte ptr [eax+{COLORFIELD_DISP}]
        mov [{SLOT_SCFC}], edx
        mov byte ptr [eax+{FACTION_DISP}], 1
        mov byte ptr [eax+{ORANGE_DISP}], 0
        mov byte ptr [eax+{RED_DISP}], 0
        mov byte ptr [eax+{COLORFIELD_DISP}], 0
        movzx edx, byte ptr [eax+{CHOICE_DISP}]
        cmp edx, 2
        je set_orange
        cmp edx, 3
        je set_red
        cmp edx, 4
        je set_purple
        cmp edx, 5
        je set_chief
        jmp colour_done
    set_orange:
        mov byte ptr [eax+{ORANGE_DISP}], 1
        jmp colour_done
    set_red:
        mov byte ptr [eax+{RED_DISP}], 1
        jmp colour_done
    set_purple:
        mov byte ptr [eax+{COLORFIELD_DISP}], 12
        jmp colour_done
    set_chief:
        mov byte ptr [eax+{COLORFIELD_DISP}], 13
    colour_done:
        mov eax, [esp]
        mov [{SLOT_RET}], eax
        mov dword ptr [esp], {RESTORE}
    wrap_orig:
        sub esp, 0xA8
        jmp {HOOK + 6}
    """


def _restore_asm() -> str:
    return f"""
        mov eax, [{SLOT_REC}]
        mov byte ptr [eax+{FACTION_DISP}], 0
        mov edx, [{SLOT_SCED}]
        mov byte ptr [eax+{ORANGE_DISP}], dl
        mov edx, [{SLOT_SCEE}]
        mov byte ptr [eax+{RED_DISP}], dl
        mov edx, [{SLOT_SCFC}]
        mov byte ptr [eax+{COLORFIELD_DISP}], dl
        mov byte ptr [{SLOT_ACTIVE}], 0
        mov eax, [{SLOT_RET}]
        jmp eax
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

    if raw[v2f(HOOK):v2f(HOOK) + 6] != HOOK_PREIMAGE:
        raise ValueError("hook preimage mismatch at 0x4720E0 — not a stock-derived VV5 render fn")

    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    wrap = bytes(ks.asm(_wrap_asm(), CAVE)[0])
    restore = bytes(ks.asm(_restore_asm(), RESTORE)[0])
    if CAVE + len(wrap) > RESTORE:
        raise ValueError(f"wrap ({len(wrap)}B) overflows into restore stub at 0x{RESTORE:X}")
    cave_span = (RESTORE - CAVE) + len(restore)
    if any(raw[v2f(CAVE) + i] for i in range(cave_span)):
        raise ValueError(f"cave 0x{CAVE:X}..0x{CAVE + cave_span:X} is not free padding")

    raw[v2f(CAVE):v2f(CAVE) + len(wrap)] = wrap
    raw[v2f(RESTORE):v2f(RESTORE) + len(restore)] = restore
    raw[v2f(HOOK):v2f(HOOK) + 5] = b"\xE9" + struct.pack("<i", CAVE - (HOOK + 5))
    raw[v2f(HOOK) + 5] = 0x90  # nop the displaced 6th byte

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
