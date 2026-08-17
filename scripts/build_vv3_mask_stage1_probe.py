"""VV3 Heathen-mask overlay — STAGE 1 render-hook proof (UNVERIFIED).

Proves the render hook + extra head-draw fires in-game, before any mask
atlas / unused-byte / UI work.  It redirects VV3's villager head-draw call
(0x456B24) into a code cave that FIRST re-draws the head shifted up by 0x30px
(a floating second head on EVERY villager), then performs the original head
draw.  If floating heads appear over the villagers, the hook + draw primitive
are proven and we can swap the shifted head for a real mask atlas gated by a
per-villager byte.

No villager state is changed; this only adds a draw call.  Output is a
checksum-fixed test exe for live playtest ONLY.

Reverse-engineering anchors (stock VV3 "Virtual Villagers - The Secret City.exe",
IB 0x400000, sha 8BC5DB38...):
  - Head/body render FUN_004568e0; HEAD DRAW at 0x456B24:
      mov ecx,[esi+0x1F7C] ; call 0x409FB0   (7 stack args, callee ret 0x1C)
      args on stack at [esp+0..0x18] = atlas, 0x78(x), 0xF2(layer), headRow,
      facing(DAT_004b162c), headY, 1
  - esi = villager record; the draw primitive preserves esi.
  - Code cave: VA 0x47B254 (.text tail padding, 0xDAC free).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import keystone

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
IMAGE_BASE = 0x400000
HOOK_VA = 0x456B24          # head-draw call site (11 bytes replaced)
HOOK_LEN = 0x456B2F - 0x456B24  # = 0xB (11)
RETURN_VA = 0x456B2F
CAVE_VA = 0x47B254
DRAW_FN = 0x409FB0
SPRITE_OBJ_OFF = 0x1F7C
Y_LIFT = 0x30               # px to lift the proof head so it's visibly separate


def _pe_checksum(buf: bytearray) -> int:
    off = struct.unpack_from("<I", buf, 0x3C)[0]
    csum_off = off + 24 + 64
    struct.pack_into("<I", buf, csum_off, 0)
    total = 0
    padded = bytes(buf) + (b"\0" if len(buf) % 2 else b"")
    for i in range(0, len(padded), 2):
        total += padded[i] | (padded[i + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return ((total & 0xFFFF) + len(buf)) & 0xFFFFFFFF, csum_off


def build(out_path: Path) -> None:
    data = bytearray(STOCK.read_bytes())
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)

    cave_asm = f"""
        /* floating second head: copy the 7 on-stack draw args down, lift Y */
        sub  esp, 0x1C
        mov  eax, [esp+0x1C]      /* atlas   */
        mov  [esp+0x00], eax
        mov  eax, [esp+0x20]      /* x=0x78  */
        mov  [esp+0x04], eax
        mov  eax, [esp+0x24]      /* layer 0xF2 */
        mov  [esp+0x08], eax
        mov  eax, [esp+0x28]      /* head row */
        mov  [esp+0x0C], eax
        mov  eax, [esp+0x2C]      /* facing  */
        mov  [esp+0x10], eax
        mov  eax, [esp+0x30]      /* headY   */
        sub  eax, {Y_LIFT}
        mov  [esp+0x14], eax
        mov  eax, [esp+0x34]      /* trailing 1 */
        mov  [esp+0x18], eax
        mov  ecx, [esi+0x{SPRITE_OBJ_OFF:X}]
        call 0x{DRAW_FN:X}        /* draws lifted head (ret 0x1C restores esp) */
        /* original head draw: args still intact at [esp..+0x18] */
        mov  ecx, [esi+0x{SPRITE_OBJ_OFF:X}]
        call 0x{DRAW_FN:X}
        jmp  0x{RETURN_VA:X}
    """
    cave_bytes, _ = ks.asm(cave_asm, addr=CAVE_VA)
    cave_bytes = bytes(cave_bytes)
    assert len(cave_bytes) <= 0xDAC, f"cave too big: {len(cave_bytes)}"

    # hook: jmp CAVE at HOOK_VA, pad to HOOK_LEN with NOPs
    hook_bytes, _ = ks.asm(f"jmp 0x{CAVE_VA:X}", addr=HOOK_VA)
    hook_bytes = bytes(hook_bytes) + b"\x90" * (HOOK_LEN - len(hook_bytes))
    assert len(hook_bytes) == HOOK_LEN

    # .text raw==va==0x1000, so file offset == RVA
    def foff(va: int) -> int:
        return va - IMAGE_BASE

    data[foff(CAVE_VA):foff(CAVE_VA) + len(cave_bytes)] = cave_bytes
    data[foff(HOOK_VA):foff(HOOK_VA) + HOOK_LEN] = hook_bytes

    csum, csum_off = _pe_checksum(data)
    struct.pack_into("<I", data, csum_off, csum)

    out_path.write_bytes(data)
    print(f"cave {len(cave_bytes)} bytes @ 0x{CAVE_VA:X}; hook {HOOK_LEN} bytes @ 0x{HOOK_VA:X}")
    print(f"PE checksum = 0x{csum:08X}")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "scratchpad_vv3_mask_stage1.exe"
    build(out)
