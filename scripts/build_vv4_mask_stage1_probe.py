"""VV4 Heathen-mask STAGE-1 PROOF (UNVERIFIED) — force Blue mask on every villager.

Proves the append-rows overlay end to end: the head atlases carry the 5 masks as
rows 30..34 (build_vv4_mask_atlas.py), the head-atlas row count is bumped 30->35,
and a render-hook cave re-draws head-atlas row 30 (Blue) on top of every
villager's head, at the same position/facing, reusing the native draw
`FUN_00409a70` (stdcall, ret 0x1c). No villager fields are written.

THIS IS A PROOF STUB, not the shipping feature: it masks EVERYONE (unconditional)
so alignment/scale can be eyeballed in-game. The real feature gates the draw on
the unused per-villager byte +0x1BC4 (0=none, 1..5=mask) and draws row 29+byte.

A render hook can only be proven in-game: build, deploy the exe + the four
modified head atlases over a COPY of the install, launch, open a villager's
Detail screen (that triggers the cached head re-composite), and LOOK.

Addresses (stock The Tree of Life.exe, IB 0x400000):
  head-draw call site 0x45F702 (call 0x409a70); cave 0x489019; .shr scratch
  0x728C40..; head-atlas row-count fields file 0xC3C24 (male_heads id0x117) /
  0xC3B94 (female_heads id0x114), value 30->35.
"""
from __future__ import annotations
import argparse, struct, shutil
from pathlib import Path
import pefile
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

STOCK_SHA = "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"
# Head-draw call sites in BOTH villager render twins:
#   0x45F702 = FUN_0045f550 (walking world villagers, called via pointer)
#   0x45F9CA = FUN_0045f7c0 (selection-panel portraits)
# One cave serves both: it returns via the saved dynamic return address.
CALL_SITES = (0x45F702, 0x45F9CA)
DRAW = 0x409A70
CAVE = 0x489019
# .shr scratch slots (clear of the barrel patch at 0x728B00..0x728C04)
S_ECX, S_A0, S_A1, S_A2, S_A4, S_A5, S_RET = (0x728C40, 0x728C44, 0x728C48,
                                              0x728C4C, 0x728C50, 0x728C54, 0x728C58)
ROW_FIELDS = {0xC3C24: (30, 35), 0xC3B94: (30, 35)}   # file offset: (old, new)
MASK_ROW = 30                        # Blue = atlas row 30 (proof forces this)


def _va2off(pe, va):
    rva = va - pe.OPTIONAL_HEADER.ImageBase
    for s in pe.sections:
        if s.VirtualAddress <= rva < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            return s.PointerToRawData + (rva - s.VirtualAddress)
    raise ValueError(f"VA {va:#x} not mapped")


def _cave_asm(post_head: int, force_row: int | None) -> str:
    """Cave body. ``force_row`` unconditionally draws that atlas row (proof mode);
    ``None`` gates on the unused per-villager byte +0x1BC4 (0=none, 1..5=mask ->
    atlas row 29+byte). ``esi`` = villager record is callee-saved across the
    native draw, so it is still the record at post_head."""
    prologue = f"""
        mov [{S_ECX}], ecx
        mov eax, [esp+4]
        mov [{S_A0}], eax
        mov eax, [esp+8]
        mov [{S_A1}], eax
        mov eax, [esp+0xC]
        mov [{S_A2}], eax
        mov eax, [esp+0x14]
        mov [{S_A4}], eax
        mov eax, [esp+0x18]
        mov [{S_A5}], eax
        mov eax, [esp]
        mov [{S_RET}], eax
        mov dword ptr [esp], {post_head}
        jmp {DRAW}
    post_head:
    """
    if force_row is not None:
        select = f"        mov eax, {force_row}\n"           # proof: always this row
    else:
        select = f"""        movzx eax, byte ptr [esi + 0x1BC4]
        test eax, eax
        jz mask_done
        add eax, 29
    """
    draw = f"""
        push 0
        push dword ptr [{S_A5}]
        push dword ptr [{S_A4}]
        push eax
        push dword ptr [{S_A2}]
        push dword ptr [{S_A1}]
        push dword ptr [{S_A0}]
        mov ecx, dword ptr [{S_ECX}]
        call {DRAW}
    mask_done:
        jmp dword ptr [{S_RET}]
    """
    return prologue + select + draw


def _assemble(code: str, base: int) -> bytes:
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    enc, _ = ks.asm(code, base)
    return bytes(enc)


def build(inp: Path, out: Path, force_row: int | None = None) -> None:
    raw = bytearray(inp.read_bytes())
    import hashlib
    got = hashlib.sha256(raw).hexdigest().upper()
    if got != STOCK_SHA:
        raise SystemExit(f"input is not stock (sha {got})")
    pe = pefile.PE(data=bytes(raw), fast_load=True)

    # two-pass assemble to resolve the post_head label address (prologue length is
    # immediate-independent, so assemble the prologue alone to find its offset)
    prologue = _cave_asm(0, force_row).split("post_head:")[0]
    post_head = CAVE + len(_assemble(prologue, CAVE))
    cave = _assemble(_cave_asm(post_head, force_row), CAVE)
    if len(cave) > (0x48A000 - CAVE):
        raise SystemExit("cave overflow")

    coff = _va2off(pe, CAVE)
    raw[coff:coff + len(cave)] = cave

    # patch BOTH head-draw call sites -> call CAVE (cave returns via saved ret addr)
    for cs in CALL_SITES:
        site = _va2off(pe, cs)
        assert raw[site] == 0xE8, f"call site {cs:#x} not E8"
        raw[site + 1:site + 5] = struct.pack("<i", CAVE - (cs + 5))

    # bump head-atlas row counts 30->35
    for off, (old, new) in ROW_FIELDS.items():
        assert raw[off] == old, f"row field {off:#x} = {raw[off]} != {old}"
        raw[off] = new

    # recompute PE checksum
    pe2 = pefile.PE(data=bytes(raw))
    pe2.OPTIONAL_HEADER.CheckSum = pe2.generate_checksum()
    out.write_bytes(pe2.write())
    mode = f"FORCED row {force_row}" if force_row is not None else "gated on +0x1BC4"
    print(f"exe -> {out}  ({mode}; cave {len(cave)}B, checksum {pe2.OPTIONAL_HEADER.CheckSum:#010x})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--force-row", type=int, default=None,
                    help="proof mode: draw this atlas row on EVERY villager "
                         "(30=Blue..34=Chief). Omit for the real +0x1BC4-gated draw.")
    a = ap.parse_args()
    build(Path(a.input), Path(a.output), force_row=a.force_row)


if __name__ == "__main__":
    main()
