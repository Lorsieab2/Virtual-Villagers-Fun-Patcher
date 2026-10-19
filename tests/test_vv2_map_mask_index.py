"""Clicking Map must not crash a VV2 village that has the Heathen-mask overlay.

The child head-draw stub (scripts/build_vv2_mask_stage2.py, hooked on the
0x409600 thunk) finds the villager from the caller's registers.  Its village
gate covers 0x445B50..0x449060, but two functions live there: the village
compositor 0x445B50..0x4478DF (villager loop index in EDI) and the Map
overview 0x4478E0..0x4490BF (loop index in EBP, EDI is scratch holding
[record+0x530]).  Reading [esi+edi*4+0xE57090] from the Map crashed the game
(owner's crash dump of 2026-10-18: return 0x44904E, EDI=0x445, EBP=6).

These tests run the shipped stub bytes from data/vv2_origins_feature.json
under Unicorn, with the register that is NOT the index pointed at unmapped
memory, so a wrong-register read faults exactly as the game did.
"""

import json
import struct
from pathlib import Path

import pytest

unicorn = pytest.importorskip("unicorn")
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UcError  # noqa: E402
from unicorn.x86_const import (  # noqa: E402
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8"))

CHILD_THUNK_OFFSET = 0x9600
CHILD_REAL_DRAW = 0x408CF0
MASK_TABLE_VA = 0x4B3000
MASK_ATLAS_PTR = 0x4B3F08
GAME_CTX = 0x10000000
INDEX_TABLE = 0xE57090
HEAD_ATLAS_OFF = 0xE574A8
DRAWOBJ_OFF = 0xE574D0
STACK = 0x00200000

MAP_RETURN = 0x44904E          # the crashing call: 0x449049 call 0x409600
COMPOSITOR_RETURN = 0x4467C8   # 0x4467C3 call 0x409600 in the village compositor
PORTRAIT_RETURN = 0x445650     # 0x44564B call 0x409600 in the Details portrait
WILD = 0x445                   # the EDI the Map renderer held at the crash


def _child_stub_entry(layout: dict) -> int:
    patch = next(p for p in MANIFEST["patches"] if p["offset"] == f"0x{CHILD_THUNK_OFFSET:X}")
    after = bytes.fromhex(patch["after"])
    assert after[0] == 0xE9
    return 0x400000 + CHILD_THUNK_OFFSET + 5 + int.from_bytes(after[1:5], "little", signed=True)


def _run(return_address: int, edi: int, ebp: int, record_index: int, mask_byte: int):
    layout = MANIFEST["pe_append_transaction"]["layouts"]["collection_progression"]
    page = bytes.fromhex(layout["append_bytes"])
    page_va = int(layout["virtual_address"], 0)
    assert page_va == MASK_TABLE_VA

    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(page_va, len(page))
    uc.mem_write(page_va, page)
    # Only the pages the stub may legitimately touch are mapped; any read
    # through the wrong index register lands in unmapped memory and faults.
    uc.mem_map(0x408000, 0x1000)
    uc.mem_write(CHILD_REAL_DRAW, b"\xC2\x1C\x00")          # ret 0x1c
    uc.mem_map(return_address & ~0xFFF, 0x1000)
    ctx_page = (GAME_CTX + INDEX_TABLE) & ~0xFFF
    uc.mem_map(ctx_page, 0x1000)
    uc.mem_map(STACK, 0x10000)

    head_atlas, mask_atlas, drawobj = 0x11110000, 0x22220000, STACK + 0x8000
    uc.mem_write(GAME_CTX + HEAD_ATLAS_OFF, struct.pack("<I", head_atlas))
    uc.mem_write(GAME_CTX + DRAWOBJ_OFF, struct.pack("<I", drawobj))
    uc.mem_write(drawobj, struct.pack("<I", drawobj))
    uc.mem_write(MASK_ATLAS_PTR, struct.pack("<I", mask_atlas))
    uc.mem_write(MASK_TABLE_VA + record_index, bytes([mask_byte]))
    loop_index = ebp if return_address >= 0x4478E0 else edi
    if return_address >= 0x445B50:
        uc.mem_write(GAME_CTX + INDEX_TABLE + loop_index * 4, struct.pack("<I", record_index))

    esp = STACK + 0x4000
    args = (head_atlas, 0x1EB, 0x29, 0x13, 3, 0x19, 1)
    uc.mem_write(esp, struct.pack("<8I", return_address, *args))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ESI, GAME_CTX)
    uc.reg_write(UC_X86_REG_EDI, edi)
    uc.reg_write(UC_X86_REG_EBP, ebp)
    uc.reg_write(UC_X86_REG_ECX, drawobj)
    uc.reg_write(UC_X86_REG_EAX, 0)

    draws = []

    def on_draw(emu, address, size, user):
        sp = emu.reg_read(UC_X86_REG_ESP)
        draws.append(struct.unpack("<7I", emu.mem_read(sp + 4, 28)))

    uc.hook_add(unicorn.UC_HOOK_CODE, on_draw, begin=CHILD_REAL_DRAW, end=CHILD_REAL_DRAW)
    uc.emu_start(_child_stub_entry(layout), return_address, count=2000)
    assert uc.reg_read(UC_X86_REG_ESP) == esp + 4 + 7 * 4, "stub did not clean its 7 args"
    return draws, head_atlas, mask_atlas


def test_map_overview_reads_the_index_from_ebp_not_edi() -> None:
    """The exact crash: Map caller, EDI = 0x445, EBP = loop index 6."""
    draws, head_atlas, mask_atlas = _run(MAP_RETURN, edi=WILD, ebp=6, record_index=9, mask_byte=3)
    assert len(draws) == 2, "a masked villager draws its head and then the mask"
    assert draws[0][0] == head_atlas
    assert draws[1][0] == mask_atlas
    assert draws[1][3] == 2, "mask row is the table byte minus one"


def test_map_overview_draws_unmasked_heads_once() -> None:
    draws, head_atlas, _ = _run(MAP_RETURN, edi=WILD, ebp=200, record_index=40, mask_byte=0)
    assert len(draws) == 1 and draws[0][0] == head_atlas


def test_village_compositor_still_reads_the_index_from_edi() -> None:
    """EBP is pointed at nothing valid; the compositor must keep using EDI."""
    draws, _, mask_atlas = _run(COMPOSITOR_RETURN, edi=6, ebp=0x40000000, record_index=9, mask_byte=5)
    assert len(draws) == 2 and draws[1][0] == mask_atlas
    assert draws[1][3] == 4


def test_details_portrait_still_derives_the_index_from_the_record_pointer() -> None:
    record = GAME_CTX + 12 * 0xE48C
    draws, _, mask_atlas = _run(PORTRAIT_RETURN, edi=record, ebp=0x40000000, record_index=12, mask_byte=1)
    assert len(draws) == 2 and draws[1][0] == mask_atlas
    assert draws[1][3] == 0


def test_the_unfixed_lookup_would_fault_on_the_map() -> None:
    """Guard the harness itself: an EDI-indexed read from the Map faults here."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(0x1000, 0x1000)
    uc.mem_write(0x1000, bytes.fromhex("8B84BE9070E500"))  # mov eax,[esi+edi*4+0xe57090]
    uc.mem_map((GAME_CTX + INDEX_TABLE) & ~0xFFF, 0x1000)
    uc.reg_write(UC_X86_REG_ESI, GAME_CTX)
    uc.reg_write(UC_X86_REG_EDI, WILD)
    with pytest.raises(UcError):
        uc.emu_start(0x1000, 0x1007)
