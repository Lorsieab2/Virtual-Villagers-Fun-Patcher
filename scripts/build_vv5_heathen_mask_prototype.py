"""VV5 Heathen-mask cosmetic overlay — Step-1 PROTOTYPE (UNVERIFIED).

Proves the "transient faction-flip" render approach for a cosmetic Heathen mask
that touches NO persistent villager state. It wraps the per-villager render
function so that, for the duration of one believer's render only, the faction
byte ``+0x1CEC`` is set to 1 (heathen) and then restored to 0 before the render
function returns. The game therefore draws its own heathen head + mask (correct
position / blink / layers, via ``0x451DA0`` on atlas ``0x5258B8``, mask frames
``0x1E+variant``), while the update loop never observes the flip — so the
villager stays a full believer in every game system (population, faith, no
deactivation). A re-entrancy guard prevents a nested render from ever leaving
the flip stuck (that stuck-flag state is what deactivated villagers in the
earlier failed attempt).

**THIS IS A TEST STUB, NOT THE SHIPPING FEATURE.** For the Step-1 proof it masks
*every* believer (gate: faction byte == 0). The real Change-Appearance feature
will gate on a self-owned side-table of chosen villagers + a chosen mask colour
(transiently setting the mask-type fields ``+0x1CFC``/``+0x1CED``/``+0x1CEE`` the
same restore-safe way).

**UNVERIFIED:** a render hook can only be proven in-game. Build this, deploy over
a VV5 copy, launch, and confirm (a) believers show masks and (b) the believer
population does NOT drop (no deactivation). Expect to iterate.

Addresses (stock ``Virtual Villagers - New Believers.exe``, image base 0x400000):
  * render fn entry ``0x4720E0`` (first insn ``sub esp,0xA8``); villager index at
    ``[esp+4]`` on entry, manager base in ``ecx``; villager field base
    ``esi = index*0x2F44 + ecx + 0x48`` so faction ``+0x1CEC`` is at
    ``index*0x2F44 + ecx + 0x1D34``.
  * cave ``0x494900`` (wrap) + ``0x494980`` (restore stub).
  * writable ``.shr`` slots: active-guard ``0x7B2FE0``, saved-record ``0x7B2FE4``,
    saved-return ``0x7B2FE8``.

Usage::

    python scripts/build_vv5_heathen_mask_prototype.py --input <stock.exe> --output <patched.exe>
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

import pefile
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

HOOK = 0x4720E0
HOOK_PREIMAGE = bytes.fromhex("81ECA8000000")  # sub esp, 0xA8
CAVE = 0x494900
RESTORE = 0x494980
ACTIVE, REC, RET = 0x7B2FE0, 0x7B2FE4, 0x7B2FE8
FACTION_DISP = 0x1D34  # 0x48 (esi bias) + 0x1CEC (faction byte)


def _wrap_asm() -> str:
    return f"""
        cmp byte ptr [{ACTIVE}], 0
        jne wrap_orig
        mov eax, [esp+4]
        imul eax, eax, 0x2F44
        add eax, ecx
        cmp byte ptr [eax+{FACTION_DISP}], 0
        jne wrap_orig
        mov byte ptr [eax+{FACTION_DISP}], 1
        mov byte ptr [{ACTIVE}], 1
        mov [{REC}], eax
        mov eax, [esp]
        mov [{RET}], eax
        mov dword ptr [esp], {RESTORE}
    wrap_orig:
        sub esp, 0xA8
        jmp {HOOK + 6}
    """


def _restore_asm() -> str:
    return f"""
        mov eax, [{REC}]
        mov byte ptr [eax+{FACTION_DISP}], 0
        mov byte ptr [{ACTIVE}], 0
        mov eax, [{RET}]
        jmp eax
    """


def build(stock: bytes) -> bytes:
    raw = bytearray(stock)
    pe = pefile.PE(data=bytes(raw), fast_load=True)
    ib = pe.OPTIONAL_HEADER.ImageBase

    def sect(name: bytes):
        return next(s for s in pe.sections if s.Name.rstrip(b"\x00") == name)

    text = sect(b".text")

    def v2f(va: int) -> int:
        return text.PointerToRawData + (va - (ib + text.VirtualAddress))

    if raw[v2f(HOOK):v2f(HOOK) + 6] != HOOK_PREIMAGE:
        raise ValueError("hook preimage mismatch at 0x4720E0 — not stock VV5")
    if any(raw[v2f(CAVE) + i] for i in range(0x120)):
        raise ValueError("cave 0x494900 not free")

    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    wrap = bytes(ks.asm(_wrap_asm(), CAVE)[0])
    if len(wrap) > (RESTORE - CAVE):
        raise ValueError("wrap cave overflows into restore stub")
    restore = bytes(ks.asm(_restore_asm(), RESTORE)[0])

    raw[v2f(CAVE):v2f(CAVE) + len(wrap)] = wrap
    raw[v2f(RESTORE):v2f(RESTORE) + len(restore)] = restore
    raw[v2f(HOOK):v2f(HOOK) + 5] = b"\xE9" + struct.pack("<i", CAVE - (HOOK + 5))
    raw[v2f(HOOK) + 5] = 0x90  # nop the 6th displaced byte

    out = pefile.PE(data=bytes(raw))
    out.OPTIONAL_HEADER.CheckSum = out.generate_checksum()
    return out.write()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the VV5 Heathen-mask Step-1 prototype (UNVERIFIED).")
    ap.add_argument("--input", type=Path, required=True, help="stock VV5 exe")
    ap.add_argument("--output", type=Path, required=True, help="patched exe path")
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build(args.input.read_bytes()))
    print(f"wrote {args.output}  (UNVERIFIED render hook — test in-game before trusting)")


if __name__ == "__main__":
    main()
