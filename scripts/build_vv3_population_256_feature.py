"""Generate data/vv3_population_256_feature.json: "256 Villagers (Experimental)" for The Secret City.

WHAT IT DOES

The Secret City keeps its villagers in one static object, the population
manager at 0x59E110: a 0x14-byte header, 150 records of 0x1F8C bytes from
0x59E124, and fourteen sprite handles after the last record (0x6C5D2C..). The
object fills the zero part of .data up to unrelated globals, so it cannot grow
where it is. This feature MOVES it:

  * a new section at the fixed address 0x7F0000 holds a page of code (the
    detours below) and, as zero-fill, the relocated manager at 0x800000 --
    header plus 260 records: 256 usable slots and four zero records that the
    game's unrolled x5/x10 scans read past slot 255 (256 is a multiple of
    neither 5 nor 10).  A filler section (no file bytes) pads the image up to
    0x7F0000, so the address never depends on which other patches appended
    pages before it;
  * every `mov ecx, 0x59E110` (380 of them, the only way the manager pointer
    enters the code) is pointed at 0x800000, and the six absolute record
    operands at the selected-villager code follow it;
  * the 32 accesses that reach the sprite handles through the manager
    pointer become absolute accesses to the handles' STOCK addresses, so the
    handles stay where 31 other absolute accesses already expect them;
  * every slot bound (65 sites: loop counts 150 -> 256, the three 15 x 10
    unrolled loops -> 26, the reverse scans 149 -> 255 and their start
    pointers -> record 255, the static constructor 150 -> 260) and every
    picker's 150-dword stack array (12 functions, frames grown) is widened;
  * the Villager Details screen's index list (150 dwords inside a heap
    object) moves to a 256-entry buffer in the new section;
  * the save keeps the stock payload byte for byte and appends the
    villagers 150..255 after it (see SAVE FORMAT);
  * the population modes reach 256 (Collection Progression: base 221;
    Immediate Fixed: 256 at once; stock mode keeps the stock cap of 125) and
    the automatic slot-safety rows guard 256 slots instead of 150.

Every byte this writes is guarded by the stock bytes it replaces; the patcher
applies the whole feature after every other patch, and rewrites the manager
references inside other patches' own code through the per-feature
`compositions` table, each with an exact expected count.

SAVE FORMAT

A stock save is a 12-byte header (`ldwg`, a dword, the payload size) and a
payload of 0x12F1C bytes: the game object from +8.  Villagers are saved as a
compact table of 0x11C-byte entries at game+0x786C (150 entries, ending at
game+0x11ED4), written by 0x45EF80 and read back by 0x45C860 until an entry
whose first byte is 0.

This feature keeps the compact table for ALL 257 entries (256 + a 0
terminator slot) in the new section (`compact_table`).  The writer and reader
use it directly.  On save, the payload is assembled in a scratch buffer: the
stock 0x12F1C bytes, with entries 0..149 copied into their stock place, then
entries 150..255 appended (0x7598 bytes) -- payload 0x1A4B4.  On load the
reader tries the 256 size first and then the stock size, so an old 150-slot
save loads (the extension reads as empty) and is written back in the 256
format at its next save.  The header's size field tells the two apart; a
256-format save is never offered to a stock build, because the 256 build uses
its own save folder ("... - Modded 256").

Re-run after changing anything here; the patcher pins nothing else.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, CS_OP_IMM, CS_OP_MEM, Cs
from keystone import KS_ARCH_X86, KS_MODE_32, Ks

ROOT = Path(__file__).resolve().parents[1]
STOCK_VV3 = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
STOCK_SHA256 = "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
OUT = ROOT / "data" / "vv3_population_256_feature.json"

FEATURE_ID = "vv3_population_256"
IMAGE_BASE = 0x400000

# ---- geometry -----------------------------------------------------------
STOCK_MANAGER = 0x59E110
STRIDE = 0x1F8C
RECORD_BASE_OFFSET = 0x14
STOCK_SLOTS = 150
SLOTS = 256
RECORDS = 260                      # 256 usable + 4 zero records for the unrolled scans
STOCK_TAIL = 0x127C1C              # sprite handles: manager + 0x127C1C .. + 0x127C54
STOCK_MANAGER_SIZE = 0x127C54

SECTION_VA = 0x7F0000              # .vv256: one page of code, then zero-fill
CODE_VA = SECTION_VA
DETAILS_LIST = 0x7F1000            # 256 dwords
MANAGER = 0x800000
MANAGER_SIZE = RECORD_BASE_OFFSET + RECORDS * STRIDE      # 0x200A44
COMPACT_ENTRY = 0x11C
COMPACT_TABLE = 0xA01000           # 257 entries (256 + terminator slot)
COMPACT_TABLE_SIZE = (SLOTS + 1) * COMPACT_ENTRY
SCRATCH = 0xA13000                 # one complete 256-format payload
STOCK_PAYLOAD = 0x12F1C
EXTENSION = (SLOTS - STOCK_SLOTS) * COMPACT_ENTRY           # 0x7598
PAYLOAD = STOCK_PAYLOAD + EXTENSION                         # 0x1A4B4
SECTION_END = 0xA2E000
STOCK_COMPACT_IN_PAYLOAD = 0x786C - 8                       # game+0x786C at payload offset

assert MANAGER + MANAGER_SIZE <= COMPACT_TABLE
assert COMPACT_TABLE + COMPACT_TABLE_SIZE <= SCRATCH
assert SCRATCH + PAYLOAD <= SECTION_END
assert DETAILS_LIST + SLOTS * 4 <= MANAGER

# ---- site tables (stock VV3, traced; every one is re-verified below) ------
# (VA, stock immediate, new immediate, what the loop is)
BOUNDS = [
    (0x45C868, 150, 256, "load: reset every record before reading the compact table (0x45C860)"),
    (0x45C8D5, 150, 256, "reset every record (0x45C8D0)"),
    (0x45C934, 150, 256, "select villager: mark the chosen record, clear the rest (0x45C900)"),
    (0x45C97B, 150, 256, "first active dead record waiting for burial (0x45C950)"),
    (0x45C995, 150, 256, "per-record update of active records (0x45C990)"),
    (0x45CB85, 150, 256, "picker, unrolled x10 (0x45C9D0)"),
    (0x45CDCA, 150, 256, "picker, unrolled x10 (0x45CBC0)"),
    (0x45D1FA, 150, 256, "mate picker, unrolled x5 (0x45CE00)"),
    (0x45D28A, 150, 256, "find record by condition (0x45D240)"),
    (0x45D427, 150, 256, "picker, unrolled x5 (0x45D2C0)"),
    (0x45D70A, 150, 256, "Island Event subject picker, unrolled x5 (0x45D460)"),
    (0x45D772, 150, 256, "sickness roll for every villager (0x45D760)"),
    (0x45D7D6, 15, 26, "cure-all Island Event outcome, 15 x 10 unrolled -> 26 x 10 (0x45D7D0)"),
    (0x45D8D8, 150, 256, "every villager (0x45D8D0)"),
    (0x45D932, 150, 256, "health-hit roll for every villager (0x45D920)"),
    (0x45D9A2, 150, 256, "swept-away roll (0x45D990)"),
    (0x45DA02, 150, 256, "dislike roll (0x45D9F0)"),
    (0x45DC57, 150, 256, "skill-gain roll, counter on the stack (0x45DC40)"),
    (0x45DD75, 150, 256, "collect and act (0x45DCE0)"),
    (0x45E042, 150, 256, "collect and act, unrolled x5 (0x45DDE0)"),
    (0x45E2F2, 150, 256, "picker, unrolled x5 (0x45E0F0)"),
    (0x45E572, 150, 256, "picker, unrolled x5 (0x45E370)"),
    (0x45E895, 150, 256, "skill picker, unrolled x5 (0x45E610)"),
    (0x45E8F8, 15, 26, "POPULATION COUNTER, 15 x 10 unrolled -> 26 x 10 (0x45E8F0)"),
    (0x45EA9C, 15, 26, "male/female counter, 15 x 10 unrolled -> 26 x 10 (0x45EA80)"),
    (0x45EC11, 150, 256, "is any active record linked to the argument (0x45EBF0)"),
    (0x45EC3F, 150, 256, "every villager (0x45EC30)"),
    (0x45ECEA, 150, 256, "first pass of 0x45ECB0"),
    (0x45EE25, 150, 256, "second pass of 0x45ECB0, unrolled x10"),
    (0x45EE68, 150, 256, "index validator 0 <= i < slots and active (0x45EE60)"),
    (0x45EE9E, 150, 260, "static constructor: construct every physical record (0x45EE90)"),
    (0x45EEF4, 150, 256, "init: every record learns its own index (0x45EEC0)"),
    (0x45EF14, 150, 256, "first selected record (0x45EF00)"),
    (0x45EF5C, 150, 256, "first alive active record with +0xE94 set (0x45EF30)"),
    (0x45EF8B, 150, 256, "SAVE: pack every active record into the compact table (0x45EF80)"),
    (0x45F12B, 150, 256, "ALLOCATOR, unrolled x10 (0x45F0B0)"),
    (0x45F163, 150, 256, "ALLOCATOR final range check: never a zero padding record (0x45F0B0)"),
    (0x45F24B, 150, 256, "allocator, unrolled x10 (0x45F1D0)"),
    (0x45F283, 150, 256, "allocator final range check (0x45F1D0)"),
    (0x45F34B, 150, 256, "allocator, unrolled x10 (0x45F2D0)"),
    (0x45F383, 150, 256, "allocator final range check (0x45F2D0)"),
    (0x45F3B5, 150, 256, "every villager (0x45F3B0)"),
    (0x45F3EB, 150, 256, "aging / day tick, counter on the stack (0x45F3E0)"),
    (0x45F7C6, 150, 256, "every villager (0x45F640)"),
    (0x45F91D, 150, 256, "search returning a record (0x45F890)"),
    (0x45F96B, 149, 255, "mating reverse scan 255..0 (0x45F960)"),
    (0x45FA3F, 149, 255, "nearby-villager reverse scan 255..0 (0x45FA30)"),
    (0x45FB08, 150, 256, "every villager (0x45FAD0)"),
    (0x45FB78, 150, 256, "weighted picker (0x45FB20)"),
    (0x45FC3F, 150, 256, "first alive active record with +0xE94 (0x45FC10)"),
    (0x45FCD8, 150, 256, "clear selection on every record (0x45FCC0)"),
    (0x45FD8D, 150, 256, "every villager (0x45FCF0)"),
    (0x45FFFB, 150, 256, "per-villager tick, counter on the stack (0x45FFE0)"),
    (0x460D42, 149, 255, "world hit-test reverse scan 255..0 (0x460D20)"),
    (0x428839, 150, 256, "the slot count the companions read at 0x42883A; the save-state constructor still builds its 150 in-object entries (0x428810, see ctor_tail)"),
    (0x4330BF, 150, 256, "every villager (0x433070)"),
    (0x435A58, 150, 256, "saved event state: villager index -1..slots-1 (0x435A30)"),
    (0x436BFC, 150, 256, "count adults with activity 0x84 (0x436BC0)"),
    (0x436D3D, 150, 256, "per-villager scan (0x436CC0)"),
    (0x44B260, 150, 256, "count villagers with activity 0x6C (0x44B230)"),
    (0x4622B4, 150, 256, "every villager (0x461FB0)"),
    (0x46E2C0, 150, 256, "Villager Details list builder (0x46E280)"),
]
# The reverse scans start at record 149; they must start at record 255.
ENDPOINTS = [
    (0x45F973, 0xEE4, "mating reverse scan start: record 255 +0xEE4"),
    (0x45FA44, 0x000, "nearby-villager reverse scan start: record 255"),
    (0x460D4A, 0xEE0, "world hit-test reverse scan start: record 255 +0xEE0"),
]
# (function, frame growth, every instruction whose esp displacement or frame size moves)
STACK_ARRAYS = [
    (0x45C9D0, 0x1A8, [0x45C9D0, 0x45C9DF, 0x45CB9B, 0x45CBB1]),
    (0x45CBC0, 0x1A8, [0x45CBC0, 0x45CBCA, 0x45CBD7, 0x45CDE1, 0x45CDF7]),
    (0x45CE00, 0x1A8, [0x45CE00, 0x45CE0F, 0x45D211, 0x45D229]),
    (0x45D2C0, 0x1A8, [0x45D2C0, 0x45D2CE, 0x45D43D, 0x45D454]),
    (0x45D460, 0x1A8, [0x45D460, 0x45D466, 0x45D46E, 0x45D477, 0x45D716, 0x45D72D, 0x45D755]),
    (0x45DCE0, 0x1A8, [0x45DCE0, 0x45DCE7, 0x45DD14, 0x45DD5B, 0x45DD87, 0x45DDC8]),
    (0x45DDE0, 0x1A8, [0x45DDE0, 0x45DDE6, 0x45DDF3, 0x45E04E, 0x45E065, 0x45E0A8]),
    (0x45E0F0, 0x1A8, [0x45E0F0, 0x45E0F6, 0x45E105, 0x45E2FE, 0x45E319, 0x45E320, 0x45E363]),
    (0x45E370, 0x1A8, [0x45E370, 0x45E377, 0x45E385, 0x45E57E, 0x45E599, 0x45E5A0, 0x45E5CA, 0x45E5D7, 0x45E602]),
    (0x45E610, 0x1A8, [0x45E610, 0x45E616, 0x45E621, 0x45E62F, 0x45E660, 0x45E6C0, 0x45E738, 0x45E7A4, 0x45E819, 0x45E8A1, 0x45E8B8, 0x45E8E0]),
    (0x45ECB0, 0x1A8, [0x45ECB4, 0x45ECC5, 0x45ECF1, 0x45ED03, 0x45ED0C, 0x45EE31, 0x45EE54]),
    (0x45FB20, 0x4F8, [0x45FB20, 0x45FBA2, 0x45FBAD]),
]
TAIL_THIS_RELATIVE = [
    0x45C74E, 0x45C760, 0x45C772, 0x45C784, 0x45C796, 0x45C7A8, 0x45C7BA, 0x45C7CC,
    0x45C7DB, 0x45C7EA, 0x45C7F9, 0x45C80B, 0x45C81D, 0x45C829, 0x45F80B, 0x45F81A,
    0x45F83B, 0x45F867, 0x46080C, 0x460878, 0x46087E, 0x460884, 0x460894, 0x4608A0,
    0x4608A6, 0x4608B9, 0x4608C9, 0x4608D5, 0x4608DB, 0x460A54, 0x460A7D, 0x460BD3,
]
ABSOLUTE_RECORD_OPERANDS = [0x468BBF, 0x468BC5, 0x4690EF, 0x4690F5, 0x469219, 0x46921F]
MANAGER_IMMEDIATES = 380

# ---- other patches' own code that names the table ------------------------
# Applied after every other patch, each only when its owner is selected.  A
# pattern must match EXACTLY `count` times inside the bytes that owner wrote
# (its rows and its appended or overlaid code), so a drifted owner fails the
# build instead of half-composing.
COMPOSITIONS = {
    "vv3_enable_origins_exclusive_features": [
        {"find": "B924E15900", "replace": "B914008000", "count": 1,
         "purpose": "Origins cure-all cave: first record of the relocated table"},
        {"find": "BA24E15900", "replace": "BA14008000", "count": 1,
         "purpose": "Origins cure-all cave: first record of the relocated table"},
        {"find": "B910E15900", "replace": "B900008000", "count": 3,
         "purpose": "Origins code: the relocated population manager"},
        # The Origins payload still carries a probe for the withdrawn
        # experimental 256 layout, which grew the game object in the middle
        # and moved its tail fields by 0x7598: "if the slot count at 0x42883A
        # is 256, read the selected villager 0x7598 further on".  This build
        # moves no game-object field, and its slot count IS 256, so the probe
        # would read the wrong field; the 17 bytes of the probe go.
        {"find": "813D3A884200000100007505B998750000", "replace": "90" * 17, "count": 1,
         "purpose": "Origins selected-villager lookup: the game object's fields do not move in this build"},
        {"find": "813D3A884200000100007505BD98750000", "replace": "90" * 17, "count": 1,
         "purpose": "Origins Tech menu: the game object's fields do not move in this build"},
    ],
    "vv3_write_parentage_log": [
        {"find": "6810E15900", "replace": "6800008000", "count": 1,
         "purpose": "parentage stub: pass the relocated population manager"},
        {"find": "81C124E15900", "replace": "81C114008000", "count": 1,
         "purpose": "parentage stub: first record of the relocated table"},
    ],
    "vv3_everyone_tries_on_robe": [
        {"find": "BF24E15900", "replace": "BF14008000", "count": 3,
         "purpose": "robe wrapper: first record of the relocated table"},
    ],
}


def ks_asm(code: str, va: int) -> bytes:
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    encoding, _ = ks.asm(code, va)
    return bytes(encoding)


class Image:
    def __init__(self, data: bytes) -> None:
        self.data = data
        (pe,) = struct.unpack_from("<I", data, 0x3C)
        nsec = struct.unpack_from("<H", data, pe + 6)[0]
        opt = struct.unpack_from("<H", data, pe + 20)[0]
        table = pe + 24 + opt
        self.sections = []
        for i in range(nsec):
            off = table + 40 * i
            name = data[off:off + 8].rstrip(b"\0").decode()
            vsize, rva, rsize, rptr = struct.unpack_from("<IIII", data, off + 8)
            self.sections.append((name, rva, vsize, rptr, rsize))
        self.md = Cs(CS_ARCH_X86, CS_MODE_32)
        self.md.detail = True

    def off(self, va: int) -> int:
        rva = va - IMAGE_BASE
        for _, s_rva, vsize, rptr, rsize in self.sections:
            if s_rva <= rva < s_rva + min(vsize, rsize):
                return rptr + rva - s_rva
        raise ValueError(f"VA 0x{va:X} has no file bytes")

    def insn(self, va: int):
        o = self.off(va)
        return next(self.md.disasm(self.data[o:o + 16], va, 1))

    def text_range(self) -> tuple[int, int]:
        for name, rva, vsize, rptr, rsize in self.sections:
            if name == ".text":
                return rptr, rptr + rsize
        raise ValueError(".text missing")


def row(img: Image, va: int, after: bytes, purpose: str, *, length: int | None = None) -> dict:
    n = len(after) if length is None else length
    o = img.off(va)
    before = img.data[o:o + n]
    assert len(before) == len(after), (hex(va), before.hex(), after.hex())
    assert before != after, hex(va)
    return {
        "offset": f"0x{o:X}",
        "before": before.hex().upper(),
        "after": after.hex().upper(),
        "purpose": purpose,
    }


def replace_imm(img: Image, va: int, old: int, new: int, purpose: str) -> dict:
    i = img.insn(va)
    imms = [op for op in i.operands if op.type == CS_OP_IMM]
    assert len(imms) == 1 and (imms[0].imm & 0xFFFFFFFF) == old, (hex(va), i.mnemonic, i.op_str)
    pos = i.imm_offset
    size = i.size - pos
    raw = bytearray(i.bytes)
    if size == 4:
        struct.pack_into("<I", raw, pos, new & 0xFFFFFFFF)
    elif size == 1:
        assert -128 <= new <= 127, (hex(va), new)
        raw[pos] = new & 0xFF
    else:
        raise AssertionError((hex(va), size))
    return row(img, va, bytes(raw), purpose)


def replace_disp(img: Image, va: int, old: int, new: int, purpose: str) -> dict:
    i = img.insn(va)
    mems = [op for op in i.operands if op.type == CS_OP_MEM]
    assert len(mems) == 1 and (mems[0].mem.disp & 0xFFFFFFFF) == old, (hex(va), i.op_str)
    pos = i.disp_offset
    raw = bytearray(i.bytes)
    assert struct.unpack_from("<I", raw, pos)[0] == old
    struct.pack_into("<I", raw, pos, new & 0xFFFFFFFF)
    return row(img, va, bytes(raw), purpose)


def record_va(index: int, field: int = 0) -> int:
    return MANAGER + RECORD_BASE_OFFSET + index * STRIDE + field


def build_code_page(mode: str) -> tuple[bytes, dict[str, int]]:
    """The detours, assembled at their fixed addresses in the .vv256 page."""
    T = COMPACT_TABLE
    S = SCRATCH
    blocks: list[tuple[str, str]] = [
        # 0x428810 builds the 150 compact entries inside the game object (or a
        # load buffer).  Its count register now starts at the slot count the
        # companions read at 0x42883A (256), so the loop stops at 256-150.
        ("ctor_tail", """
            add esi, 0x11c
            dec edi
            cmp edi, %d
            jne 0x428840
            jmp 0x428873
        """ % (SLOTS - STOCK_SLOTS)),
        # 0x427D60: the stock writer is called with (payload, size, slot).
        # Assemble the 256-format payload in the scratch buffer: the stock
        # object bytes, the first 150 compact entries in their stock place,
        # then entries 150..255.  Returns eax = payload, ecx = game object.
        ("save_prep", f"""
            push esi
            push edi
            lea esi, [esi + 8]
            mov edi, 0x{S:X}
            mov ecx, 0x{STOCK_PAYLOAD // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            mov esi, 0x{T:X}
            mov edi, 0x{S + STOCK_COMPACT_IN_PAYLOAD:X}
            mov ecx, 0x{STOCK_SLOTS * COMPACT_ENTRY // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            mov edi, 0x{S + STOCK_PAYLOAD:X}
            mov ecx, 0x{EXTENSION // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            pop edi
            pop esi
            mov ecx, esi
            mov eax, 0x{S:X}
            ret
        """),
        # 0x428939: read the slot's payload -- the 256 size first, then the
        # stock size (an old save: its extension reads as empty) -- copy the
        # stock part where the stock code expects it, and rebuild the compact
        # table from both parts.  The terminator slot 256 is always empty.
        ("load_cave", f"""
            push esi
            push 0x{PAYLOAD:X}
            push 0x{S:X}
            mov ecx, ebx
            call 0x4033A0
            test al, al
            jnz load_new
            push esi
            push 0x{STOCK_PAYLOAD:X}
            push 0x{S:X}
            mov ecx, ebx
            call 0x4033A0
            test al, al
            jz load_fail
            push edi
            xor eax, eax
            mov edi, 0x{S + STOCK_PAYLOAD:X}
            mov ecx, 0x{EXTENSION // 4:X}
            rep stosd
            pop edi
        load_new:
            push esi
            push edi
            mov esi, 0x{S:X}
            lea edi, [esp + 0x9C]
            mov ecx, 0x{STOCK_PAYLOAD // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            mov esi, 0x{S + STOCK_COMPACT_IN_PAYLOAD:X}
            mov edi, 0x{T:X}
            mov ecx, 0x{STOCK_SLOTS * COMPACT_ENTRY // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            mov esi, 0x{S + STOCK_PAYLOAD:X}
            mov ecx, 0x{EXTENSION // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            mov byte ptr [0x{T + SLOTS * COMPACT_ENTRY:X}], 0
            pop edi
            pop esi
            jmp 0x428956
        load_fail:
            jmp 0x428A74
        """),
        # Villager Details list: the 256-entry buffer replaces the 150 dwords
        # at screen+8; the count at screen+0x260 stays where it is.
        ("details_store", f"""
            mov dword ptr [eax*4 + 0x{DETAILS_LIST:X}], esi
            inc dword ptr [edi + 0x260]
            ret
        """),
        ("details_sort_init", f"""
            mov esi, 0x{DETAILS_LIST:X}
            mov dword ptr [esp + 0x18], esi
            ret
        """),
        ("details_sort_store", f"""
            mov ecx, dword ptr [esp + 0x14]
            mov dword ptr [edi*4 + 0x{DETAILS_LIST:X}], ecx
            ret
        """),
        ("details_read", f"""
            mov ecx, dword ptr [esp + 0x20]
            mov edx, dword ptr [ecx*4 + 0x{DETAILS_LIST:X}]
            ret
        """),
        ("details_find", f"""
            mov esi, dword ptr [esp + 0xC]
            mov ecx, 0x{DETAILS_LIST:X}
            ret
        """),
    ]
    if mode == "collection_progression":
        # Collection Progression: base 221 + 0..25 collections + 10 magic = 256.
        # 221 does not fit the stock sign-extended byte immediate.
        blocks.append(("cp_add", """
            add esi, 0xDD
            cmp ebx, esi
            ret
        """))
    page = bytearray()
    labels: dict[str, int] = {}
    for name, code in blocks:
        while len(page) % 16:
            page.append(0xCC)
        va = CODE_VA + len(page)
        labels[name] = va
        page += ks_asm(code, va)
    assert len(page) <= 0x1000
    page += bytes(0x1000 - len(page))
    # The fill between blocks is int3 (never executed); the tail is zero.
    return bytes(page), labels


def rel32(src: int, dst: int) -> bytes:
    return struct.pack("<i", dst - (src + 5))


def build() -> dict:
    data = STOCK_VV3.read_bytes()
    if hashlib.sha256(data).hexdigest().upper() != STOCK_SHA256:
        raise SystemExit("stock The Secret City executable SHA-256 mismatch")
    img = Image(data)
    rows: list[dict] = []

    # 1. the manager pointer: every `mov ecx, 0x59E110`
    t0, t1 = img.text_range()
    pat = b"\xB9" + struct.pack("<I", STOCK_MANAGER)
    hits = []
    pos = t0
    while True:
        k = data.find(pat, pos, t1)
        if k < 0:
            break
        hits.append(k)
        pos = k + 1
    assert len(hits) == MANAGER_IMMEDIATES, len(hits)
    # The pattern occurs nowhere else in the image.
    assert data.count(struct.pack("<I", STOCK_MANAGER)) == MANAGER_IMMEDIATES
    for k in hits:
        va = IMAGE_BASE + 0x1000 + (k - 0x1000)  # .text: RVA == file offset
        i = img.insn(va)
        assert i.mnemonic == "mov" and i.op_str == "ecx, 0x59e110", (hex(va), i.op_str)
        rows.append(row(img, va, b"\xB9" + struct.pack("<I", MANAGER),
                        "point this population-manager call at the relocated manager"))

    # 2. absolute record operands of the selected villager
    for va in ABSOLUTE_RECORD_OPERANDS:
        i = img.insn(va)
        (m,) = [op for op in i.operands if op.type == CS_OP_MEM]
        old = m.mem.disp & 0xFFFFFFFF
        field = old - (STOCK_MANAGER + RECORD_BASE_OFFSET)
        assert field in (0xEE0, 0xEE4), (hex(va), hex(old))
        rows.append(replace_disp(img, va, old, record_va(0, field),
                                 "selected villager's position: the relocated record table"))

    # 3. sprite handles: manager-relative -> absolute stock address
    for va in TAIL_THIS_RELATIVE:
        i = img.insn(va)
        raw = bytearray(i.bytes)
        modrm = raw[1]
        assert raw[0] in (0x89, 0x8B) and (modrm >> 6) == 2 and (modrm & 7) != 4, (hex(va), i.op_str)
        disp = struct.unpack_from("<I", raw, 2)[0]
        assert STOCK_TAIL <= disp < STOCK_MANAGER_SIZE and i.size == 6, (hex(va), hex(disp))
        raw[1] = (modrm & 0x38) | 0x05
        struct.pack_into("<I", raw, 2, STOCK_MANAGER + disp)
        rows.append(row(img, va, bytes(raw),
                        "keep this sprite handle at its stock address after the manager moves"))

    # 4. slot bounds
    for va, old, new, what in BOUNDS:
        rows.append(replace_imm(img, va, old, new, f"{SLOTS} slots: {what}"))
    for va, field, what in ENDPOINTS:
        i = img.insn(va)
        old149 = RECORD_BASE_OFFSET + (STOCK_SLOTS - 1) * STRIDE + field
        new255 = RECORD_BASE_OFFSET + (SLOTS - 1) * STRIDE + field
        if i.mnemonic == "lea":
            rows.append(replace_disp(img, va, old149, new255, what))
        else:
            rows.append(replace_imm(img, va, old149, new255, what))

    # 5. stack arrays
    for fn, delta, sites in STACK_ARRAYS:
        for va in sites:
            i = img.insn(va)
            if i.mnemonic in ("sub", "add") and i.op_str.startswith("esp, "):
                old = i.operands[1].imm
                rows.append(replace_imm(img, va, old, old + delta,
                                        f"widen the picker's index array to {SLOTS} entries (0x{fn:X})"))
            else:
                (m,) = [op for op in i.operands if op.type == CS_OP_MEM]
                assert i.reg_name(m.mem.base) == "esp" and m.mem.index == 0, (hex(va), i.op_str)
                old = m.mem.disp
                assert old >= 0x200, (hex(va), i.op_str)
                rows.append(replace_disp(img, va, old, old + delta,
                                         f"argument/local above the widened index array (0x{fn:X})"))

    pages = {}
    labels_by_mode = {}
    for mode in ("stock", "collection_progression", "immediate_fixed"):
        pages[mode], labels_by_mode[mode] = build_code_page(mode)
    L = labels_by_mode["collection_progression"]
    for mode in ("stock", "immediate_fixed"):
        for k, v in labels_by_mode[mode].items():
            assert L[k] == v

    # 6. save: compact table, payload assembly, load
    T = COMPACT_TABLE
    rows.append(row(img, 0x42886A, b"\xE9" + rel32(0x42886A, L["ctor_tail"]) + b"\x90" * 4,
                    "save-state constructor: build only its 150 in-object compact entries"))
    rows.append(row(img, 0x45EFA6, b"\x8D\x87" + struct.pack("<I", T) + b"\x90",
                    "save writer: pack villagers into the 257-entry compact table"))
    rows.append(row(img, 0x45EFD2, b"\xC6\x83" + struct.pack("<I", T) + b"\x00\x90",
                    "save writer: end the compact table after the last villager"))
    rows.append(row(img, 0x45C885, b"\x8A\x0D" + struct.pack("<I", T),
                    "save reader: read the first compact entry from the 257-entry table"))
    rows.append(row(img, 0x45C896, b"\x8D\x86" + struct.pack("<I", T) + b"\x90",
                    "save reader: read villagers from the 257-entry compact table"))
    rows.append(row(img, 0x45C8B6, b"\x8A\x8E" + struct.pack("<I", T) + b"\x90",
                    "save reader: stop at the end of the 257-entry compact table"))
    rows.append(row(img, 0x427D60,
                    b"\x57\xE8" + rel32(0x427D61, L["save_prep"]) + b"\x68" + struct.pack("<I", PAYLOAD) + b"\x50",
                    "save: write the stock payload followed by villagers 150..255"))
    rows.append(row(img, 0x428939, b"\xE9" + rel32(0x428939, L["load_cave"]) + b"\x90" * 0x18,
                    "load: accept a 256-format save, or an old 150-slot save with no extension"))

    # 7. Villager Details list
    rows.append(row(img, 0x46E2B5, b"\xE8" + rel32(0x46E2B5, L["details_store"]) + b"\x90" * 5,
                    "Villager Details: store the living villager in the 256-entry list"))
    rows.append(row(img, 0x46E3A6, b"\x56\x57\xE8" + rel32(0x46E3A8, L["details_sort_init"]) + b"\x90" * 3,
                    "Villager Details: sort the 256-entry list"))
    rows.append(row(img, 0x46E3E4, b"\xE8" + rel32(0x46E3E4, L["details_sort_store"]) + b"\x90" * 3,
                    "Villager Details: sort the 256-entry list"))
    rows.append(row(img, 0x46E4DF, b"\xE8" + rel32(0x46E4DF, L["details_read"]) + b"\x90" * 3,
                    "Villager Details: show the villager at a list position"))
    rows.append(row(img, 0x46CB2D, b"\xE8" + rel32(0x46CB2D, L["details_find"]) + b"\x90" * 2,
                    "Villager Details: find a villager's list position (previous/next)"))

    # every row is unique and non-overlapping
    spans = sorted((int(r["offset"], 16), len(r["after"]) // 2) for r in rows)
    for (a, n), (b, _) in zip(spans, spans[1:]):
        assert a + n <= b, (hex(a), hex(b))

    # 8. population modes and the slot-safety layer
    mode_rows = {
        "stock": [],
        "collection_progression": [
            row(img, 0x45FEE1, b"\xE8" + rel32(0x45FEE1, L["cp_add"]),
                "Collection Progression: base 221 plus 0-25 collection points and 10 from Magic Level 3, 256 at most"),
        ],
        "immediate_fixed": [
            row(img, 0x45FEA2, bytes.fromhex("BEA6000000909090"),
                "Immediate Fixed: 166 + 90 = 256 at every collection and magic state"),
        ],
    }
    safety_rows = build_safety_rows(img)

    def page_entry(mode: str) -> dict:
        return {"hex": pages[mode].hex().upper(),
                "sha256": hashlib.sha256(pages[mode]).hexdigest().upper()}

    return {
        "rows": rows,
        "mode_rows": mode_rows,
        "safety_rows": safety_rows,
        "code_pages": {mode: page_entry(mode) for mode in pages},
        "compositions": COMPOSITIONS,
        "layout": {
            "stock_manager": f"0x{STOCK_MANAGER:X}",
            "manager": f"0x{MANAGER:X}",
            "record_stride": f"0x{STRIDE:X}",
            "record_base_offset": f"0x{RECORD_BASE_OFFSET:X}",
            "slots": SLOTS,
            "physical_records": RECORDS,
            "section_va": f"0x{SECTION_VA:X}",
            "section_end": f"0x{SECTION_END:X}",
            "code_page_va": f"0x{CODE_VA:X}",
            "details_list": f"0x{DETAILS_LIST:X}",
            "compact_table": f"0x{COMPACT_TABLE:X}",
            "scratch_payload": f"0x{SCRATCH:X}",
            "stock_payload_size": f"0x{STOCK_PAYLOAD:X}",
            "payload_size": f"0x{PAYLOAD:X}",
            "section_name": ".vv256",
            "filler_section_name": ".vv256z",
        },
        "labels": {k: f"0x{v:X}" for k, v in labels_by_mode["collection_progression"].items()},
    }


def build_safety_rows(img: Image) -> list[dict]:
    """The automatic slot-safety rows of data/builds.json, for 256 slots.

    Same code at the same addresses; only the slot arithmetic changes: twins
    and triplets need 2 / 3 free slots of 256 (<= 254 / <= 253 occupied), the
    Island Event newcomer and barrel child need one, and the slot counter
    walks the relocated table.  The counter tests the active BYTE (+0xF10),
    as the 150-slot row does since v1.35.52."""
    manifest = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8-sig"))
    (vv3,) = [g for g in manifest["games"] if g["id"] == "vv3"]
    stock_rows = {r["offset"]: r for r in vv3["safety_patches"]}
    out = []
    edits = {
        "0x7B260": [("3D93000000", "3DFD000000")],
        "0x7B280": [("3D94000000", "3DFE000000")],
        "0x7B2E0": [("3D96000000", "3D00010000")],
        "0x7B300": [("3D96000000", "3D00010000")],
        "0x7B318": [("BA24E15900", "BA" + struct.pack("<I", record_va(0)).hex().upper()),
                    ("B996000000", "B900010000")],
    }
    purposes = {
        "0x55BBF": "route triplet selection through the 256-slot saturation guard",
        "0x7B260": "keep triplets only when three of the 256 villager slots remain",
        "0x55BDD": "route twin selection through the 256-slot saturation guard",
        "0x7B280": "keep twins only when two of the 256 villager slots remain",
        "0x14D90": "recheck the 256-slot physical limit before an Island Event creates its first adult",
        "0x7B2E0": "skip the event newcomer when all 256 slots are occupied or resume the complete stock outcome",
        "0x15320": "recheck the 256-slot physical limit before the barrel event creates its first child",
        "0x7B300": "skip the first barrel child when all 256 slots are occupied while retaining the stock later-child cap checks",
        "0x7B318": "count occupied villager record slots (active byte) of the relocated 256-slot table",
    }
    for offset, src in stock_rows.items():
        after = src["after"]
        for old, new in edits.get(offset, []):
            assert after.count(old) == 1, (offset, old)
            after = after.replace(old, new)
        out.append({"offset": offset, "before": src["before"], "after": after,
                    "purpose": purposes[offset]})
    assert set(edits) <= set(stock_rows)
    return out


DESCRIPTION = (
    "EXPERIMENTAL. Gives The Secret City 256 villager slots (0 to 255) instead of 150. The "
    "game's villager table is moved to a new, larger place in memory and every part of the "
    "game that walks it -- births, island events, the Villager Details screen, saving and "
    "loading -- is widened to match. With Collection Progression Max Pop the cap becomes 221 "
    "plus the collection and Magic Level 3 bonuses (256 with everything); with Immediate "
    "Fixed Max Pop it is 256 at once; with No Population Increase the stock cap of 125 is "
    "unchanged, only the table is larger. The patched game is named \"... - Modded 256\" and "
    "keeps its saves, and the patcher's logs, in their own \"Virtual Villagers - The Secret "
    "City - Modded 256\" folder, so they never mix with 150-slot saves. The patcher does not "
    "copy saves into it: copy your save files from the \"... - Modded\" save folder yourself. "
    "An old save loads with all its villagers; the first time the game saves it, it is "
    "written in the longer 256 format, which only a 256 build can open, so keep the originals "
    "as a backup. **Needs Fix Vanilla Bugs on (it is on by default) to load a village that "
    "the base game's exactly-150-villager save bug has already damaged.** Off by default."
)


def main() -> int:
    body = build()
    record = {
        "id": FEATURE_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv3",
        "name": "256 Villagers (Experimental)",
        "description": DESCRIPTION,
        "output_tag": "256 Villagers",
        # A soft prerequisite (Codex, #509 review): 256 still applies and works
        # without Fix Vanilla Bugs, but a village the base game's
        # exactly-150-villager save bug already damaged then cannot load. Stated
        # through the prerequisite UI -- the sentence under the description and
        # the confirmation before patching -- never by ticking anything.
        "needs_on": [{"id": "vv3_fix_vanilla_bugs",
                      "for": "loading a village that the base game's exactly-150-villager save bug has already damaged (without it such a village does not load)",
                      # Not a patch that merely does less (#512 review): the
                      # confirmation must say plainly what will not work.
                      "without": "a village the base game's exactly-150-villager save bug has already damaged will NOT load in the 256 build. Every other village loads and plays normally."}],
        "behavior_changes": [
            "The villager table has 256 slots; the population modes that raise the cap reach 256.",
            "Saves hold up to 256 villagers in a longer save file that only this build reads.",
        ],
        "explicit_non_changes": [
            "No Population Increase keeps the stock cap of 125.",
            "Nothing changes for a build that does not tick this patch.",
        ],
        "evidence_status": "static exact-build implementation with emulation of the replaced routines; live-tested with the game driven through its memory (an old save upgraded, filled to 256, triplets born into slots 200, 253 and 254 and a baby into slot 255, saved and reloaded); a hands-on live pass is pending",
        "patches": [],
        "population_256": body,
    }
    OUT.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(body['rows'])} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
