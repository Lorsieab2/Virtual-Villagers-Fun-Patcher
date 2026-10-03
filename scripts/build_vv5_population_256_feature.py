"""Generate data/vv5_population_256_feature.json: "256 Villagers (Experimental)" for New Believers.

WHAT IT DOES

New Believers keeps its villagers -- believers, Heathens and Reanimate stand-ins
alike -- in one static object, the villager manager at 0x554148: a 0x48-byte
header, 150 records of 0x2F44 bytes from 0x554190, and a tail (the selected
index, the pending list and its count, the pending mask, a float).  The object
fills the zero part of .data up to unrelated globals (0x70F670 onwards), so it
cannot grow where it is.  This feature MOVES it:

  * a new section at the fixed address 0x7F0000 holds a page of code (the
    detours below) and, as zero-fill, the Villager Details list, the Origins
    companion's 256-villager mask table, the relocated manager at 0x800000
    (header, 256 records, and the tail re-laid for 256: the pending list and
    mask hold 256), the compact save table and a save scratch buffer.  A
    filler section (no file bytes) pads the image up to 0x7F0000, so the
    address never depends on which other patches appended pages before it;
  * every `mov ecx, 0x554148` (445 of them, the way the manager pointer
    enters the code), the 15 absolute loads of manager header fields and the
    2 absolute record-field loads are pointed at the relocated manager --
    every operand of .text that falls inside the stock object is one of
    these, which the generator re-verifies with a full disassembly;
  * the 24 references to the manager's tail (relative to the manager) follow
    the re-laid tail;
  * every slot bound (61 loop counts 150 -> 256, the pending list's capacity
    150 -> 256, the getter, the selection and pending validators, the
    reverse scans and the static constructor 149 -> 255, the reverse scans'
    start pointers moved to record 255) is widened, and the 150-dword index
    arrays of the twelve pickers are widened to 256 by growing each picker's
    stack frame (the pickers make the very same rand(count) call, so the
    random stream is used exactly as before); 0x471EB0's second array, a
    count per villager INDEX, is widened the same way with its memset;
  * the sex tally 0x4714A0, unrolled six records at a time (25 x 6 = 150;
    256 is no multiple of 6), runs as a plain 256-record loop with the same
    tests;
  * the Villager Details screen's believer list (a static int[150] at
    0x51E220, followed by Details state and its own count at 0x51E480) moves
    to a 256-entry buffer, so more than 150 believers never overwrite them;
  * the save keeps the stock payload byte for byte and appends villagers
    150..255 after it (see SAVE FORMAT);
  * the population modes reach 256 (Collection Progression: base 241 + 0..15
    collection bonus; Immediate Fixed: 256 at once; stock mode keeps the
    stock cap of 105) and the automatic slot-safety rows guard 256 slots.

Every byte this writes is guarded by the stock bytes it replaces; the patcher
applies the whole feature after every other patch, and rewrites the manager
references inside other patches' own code through the per-feature
`compositions` table, each with an exact expected count.

SAVE FORMAT

A stock save is a 0x18-byte header (`ldwg`, ..., the payload size at +0x10)
and a payload of 0x17D78 bytes: the game state from +8.  Villagers are saved
as a compact table of 0x118-byte entries at GameState+0xC90C (150 entries),
written by 0x46F9B0 (an end flag after the last villager when fewer than 150
were saved) and read back by 0x46FA20 until an entry whose first byte is 0.

This feature keeps the compact table for ALL 257 entries (256 + an end-flag
slot) in the new section (`compact_table`); the writer and reader use it
directly.  On save, the payload is assembled in a scratch buffer: the stock
0x17D78 bytes, with the saved villagers 0..149 (and the end flag when fewer
than 150 were saved) put in their stock place exactly as the stock writer
would, then villagers 150..255 appended (0x73F0 bytes, zero after the last
villager) -- payload 0x1F168.  On load the reader tries the 256 size first
and then the stock size, so an old 150-slot save loads (its extension reads
as empty) and is written back in the 256 format at its next save.  The
header's size field tells the two apart; a 256-format save is never offered
to a stock build, because the 256 build uses its own save folder ("... -
Modded 256"), and a stock build refuses it.

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
STOCK_VV5 = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
OUT = ROOT / "data" / "vv5_population_256_feature.json"

FEATURE_ID = "vv5_population_256"
IMAGE_BASE = 0x400000

# ---- geometry -----------------------------------------------------------
STOCK_MANAGER = 0x554148
STRIDE = 0x2F44
RECORD_BASE_OFFSET = 0x48
STOCK_SLOTS = 150
SLOTS = 256
STOCK_TAIL = RECORD_BASE_OFFSET + STOCK_SLOTS * STRIDE          # 0x1BB220
STOCK_MANAGER_SIZE = STOCK_TAIL + 0x2FC                          # up to the float at +0x1BB518
TAIL = RECORD_BASE_OFFSET + SLOTS * STRIDE                       # 0x2F4448
# The tail, re-laid for 256: (stock offset, new offset, what it is)
TAIL_FIELDS = [
    (STOCK_TAIL + 0x000, TAIL + 0x000, "selected villager index"),
    (STOCK_TAIL + 0x004, TAIL + 0x004, "pending-list count"),
    (STOCK_TAIL + 0x008, TAIL + 0x008, "pending list (256 dwords)"),
    (STOCK_TAIL + 0x260, TAIL + 0x408, "pending mask (256 bytes)"),
    (STOCK_TAIL + 0x2F8, TAIL + 0x508, "float"),
]
TAIL_MAP = {old: new for old, new, _ in TAIL_FIELDS}
MANAGER_SIZE = TAIL + 0x50C                                      # 0x2F4954

SECTION_VA = 0x7F0000              # .vv256: one page of code, then zero-fill
CODE_VA = SECTION_VA
DETAILS_LIST = 0x7F1000            # 256 dwords
MASK_TABLE = 0x7F1400              # the Origins companion's mask nibbles, 256 villagers (128 bytes)
MANAGER = 0x800000
COMPACT_ENTRY = 0x118
COMPACT_TABLE = 0xAF5000           # 257 entries (256 + end-flag slot)
COMPACT_TABLE_SIZE = (SLOTS + 1) * COMPACT_ENTRY
SCRATCH = 0xB07000                 # one complete 256-format payload
STOCK_PAYLOAD = 0x17D78
EXTENSION = (SLOTS - STOCK_SLOTS) * COMPACT_ENTRY           # 0x73F0
PAYLOAD = STOCK_PAYLOAD + EXTENSION                         # 0x1F168
SECTION_END = 0xB27000
STOCK_COMPACT_IN_PAYLOAD = 0xC90C - 8                       # GameState+0xC90C

assert DETAILS_LIST + SLOTS * 4 <= MASK_TABLE
assert MASK_TABLE + SLOTS // 2 <= MANAGER
assert MANAGER + MANAGER_SIZE <= COMPACT_TABLE
assert COMPACT_TABLE + COMPACT_TABLE_SIZE <= SCRATCH
assert SCRATCH + PAYLOAD <= SECTION_END
assert TAIL + 0x408 == TAIL + 8 + SLOTS * 4 and TAIL + 0x508 == TAIL + 0x408 + SLOTS
assert STOCK_PAYLOAD % 4 == 0 and EXTENSION % 4 == 0 and COMPACT_ENTRY % 4 == 0

# ---- site tables (stock VV5, traced; every one is re-verified below) ------
# (VA, stock immediate, new immediate, what the loop is)
BOUNDS = [
    (0x41F1E4, 150, 256, "every index through the getter (0x41F170); the slot count Origins, Time Warp and the companions read at 0x41F1E6"),
    (0x41F7C6, 150, 256, "every record (0x41F6E0)"),
    (0x420BB3, 150, 256, "every record (0x4209B0)"),
    (0x42164C, 150, 256, "every record (0x421330)"),
    (0x421A19, 150, 256, "every record (0x421710)"),
    (0x421D49, 150, 256, "every record (0x421AC0)"),
    (0x422C94, 150, 256, "every record (0x422C60)"),
    (0x425AFD, 150, 256, "load / elapsed-time scan, first loop (0x4259D0)"),
    (0x425D82, 150, 256, "load / elapsed-time scan, second loop (0x4259D0)"),
    (0x42609E, 150, 256, "catch-up learning over every record (0x425E30)"),
    (0x43E5A8, 150, 256, "every record (0x43E560)"),
    (0x44B8EC, 150, 256, "Villager Details believer-list builder (0x44B890)"),
    (0x467ABD, 150, 256, "nearest-villager search (0x467A40)"),
    (0x46F83E, 150, 256, "reset: every record learns its own index, the pending mask is cleared (0x46F800)"),
    (0x46F954, 149, 255, "index -> record getter: 0 <= i <= 255 (0x46F950)"),
    (0x46F994, 150, 256, "first active record (0x46F970)"),
    (0x46F9BB, 150, 256, "SAVE: pack every active villager into the compact table (0x46F9B0)"),
    (0x46F9FC, 150, 256, "SAVE: end flag after the last villager when fewer than 256 (0x46F9B0)"),
    (0x46FA28, 150, 256, "LOAD: reset every record before reading the compact table (0x46FA20)"),
    (0x46FAA5, 150, 256, "reset every record (0x46FAA0)"),
    (0x46FAF6, 150, 256, "ALLOCATOR: first free slot (0x46FAD0)"),
    (0x46FB07, 150, 256, "ALLOCATOR: no free slot (0x46FAD0)"),
    (0x46FBA6, 150, 256, "HEATHEN ALLOCATOR: first free slot (0x46FB80)"),
    (0x46FBBA, 150, 256, "HEATHEN ALLOCATOR: no free slot (0x46FB80)"),
    (0x46FD96, 150, 256, "CHILD ALLOCATOR: first free slot (0x46FD70)"),
    (0x46FDA7, 150, 256, "CHILD ALLOCATOR: no free slot (0x46FD70)"),
    (0x46FE06, 150, 256, "REANIMATE STAND-IN ALLOCATOR: first free slot (0x46FDE0)"),
    (0x46FE17, 150, 256, "REANIMATE STAND-IN ALLOCATOR: no free slot (0x46FDE0)"),
    (0x46FE98, 150, 256, "per-tick update of every record, counter on the stack (0x46FE90)"),
    (0x4701A5, 150, 256, "draw-order sort (0x470100)"),
    (0x47028D, 149, 255, "world-point picker reverse scan 255..0, first pass (0x470270)"),
    (0x47037D, 149, 255, "world-point picker reverse scan 255..0, second pass (0x470270)"),
    (0x4704F4, 150, 256, "spatial pick, first pass (0x470450)"),
    (0x47058A, 150, 256, "spatial pick, second pass (0x470450)"),
    (0x4705DB, 149, 255, "reverse picker 255..0 (0x4705D0)"),
    (0x4706C6, 150, 256, "first record with a field value (0x470690)"),
    (0x4706FF, 149, 255, "reverse picker 255..0 (0x4706F0)"),
    (0x4707E4, 150, 256, "any villager near a point (0x4707A0)"),
    (0x4708B1, 150, 256, "village-wide action (0x470810)"),
    (0x4708FA, 149, 255, "select a villager: -1 or 0..255 (0x4708F0)"),
    (0x470966, 150, 256, "first idle index (0x470940)"),
    (0x47098A, 150, 256, "every record (0x470980)"),
    (0x4709D5, 150, 256, "every record (0x4709D0)"),
    (0x470AFA, 150, 256, "mate picker (0x470A10)"),
    (0x470BB4, 150, 256, "picker (0x470B40)"),
    (0x470C02, 150, 256, "every record (0x470BF0)"),
    (0x470CE4, 150, 256, "Island Event group picker (0x470C60)"),
    (0x470DE4, 150, 256, "Island Event group picker (0x470D60)"),
    (0x470ED1, 150, 256, "Island Event picker (0x470E60)"),
    (0x47112D, 150, 256, "Island Event group picker (0x4710B0)"),
    (0x47127D, 150, 256, "Island Event scatter (0x471200)"),
    (0x471352, 150, 256, "every record (0x471340)"),
    (0x4713FB, 150, 256, "BELIEVER COUNTER for the cap check (0x4713F0)"),
    (0x47145B, 150, 256, "every record (0x471450)"),
    (0x47159B, 150, 256, "adults (0x471590)"),
    (0x4715EE, 150, 256, "every record, counter on the stack (0x4715E0)"),
    (0x4716AE, 150, 256, "any villager with a field value (0x471680)"),
    (0x4716DA, 150, 256, "Island Event group action (0x4716D0)"),
    (0x47178B, 150, 256, "any Heathen with a job (0x471750)"),
    (0x4717EC, 150, 256, "random villager with a job (0x4717A0)"),
    (0x4719F8, 150, 256, "filtered random villager (0x471870)"),
    (0x471B0B, 150, 256, "filtered random villager (0x471A50)"),
    (0x471C02, 150, 256, "random villager (0x471BB0)"),
    (0x471C6E, 150, 256, "Heathens near a villager (0x471C50)"),
    (0x471D34, 149, 255, "pending list: add only 0..255 (0x471D30)"),
    (0x471D4B, 150, 256, "pending list capacity: 256 (0x471D30)"),
    (0x471D75, 149, 255, "pending list: remove only 0..255 (0x471D70)"),
    (0x471DFE, 149, 255, "static constructor: construct every record (0x471DF0)"),
    (0x472092, 150, 256, "pending-list walk over every record (0x471EB0)"),
    (0x472CAF, 150, 256, "ageing / birth tick, counter on the stack (0x472C90)"),
]
# The reverse scans start at record 149; they must start at record 255.
# (VA, the field the start pointer is at)
ENDPOINTS = [
    (0x47027E, 0x0000, "world-point picker reverse scan start: record 255"),
    (0x4705E3, 0x0000, "reverse picker start: record 255"),
    (0x470704, 0x0000, "reverse picker start: record 255"),
]
# The pickers that collect candidate indices into 150-dword arrays on the
# stack: (start, end, the stack arrays' stock displacements as the indexed
# accesses name them, the frame size).  0x4710B0 has two lists; 0x471EB0 a
# count per villager index and a list (and an ebp frame, nothing above it
# read through esp).
PICKERS = [
    (0x470A10, 0x470B34, (0x10,), 0x258), (0x470B40, 0x470BEA, (0x10,), 0x258),
    (0x470C60, 0x470D5F, (0x18,), 0x260), (0x470D60, 0x470E5F, (0x18,), 0x260),
    (0x470E60, 0x4710B0, (0x10,), 0x258), (0x4710B0, 0x4711F9, (0x18, 0x270), 0x4B8),
    (0x471200, 0x471335, (0x18,), 0x260), (0x4717A0, 0x471838, (0x10,), 0x25C),
    (0x471870, 0x471A4C, (0x14,), 0x25C), (0x471A50, 0x471BA8, (0x14,), 0x25C),
    (0x471BB0, 0x471C4E, (0x10,), 0x258), (0x471EB0, 0x4720DC, (0x38, 0x290), 0x4D8),
]
STOCK_ARRAY = STOCK_SLOTS * 4
GROWTH = (SLOTS - STOCK_SLOTS) * 4                           # 0x1A8
MEMSET_COUNTS = 0x471EC2                                     # push 0x258: 0x471EB0 clears its per-index counts
# Villager Details list (static int[150] at 0x51E220): every reference.
DETAILS_REFS = [0x44B8DA, 0x44B9D0, 0x44BA23, 0x44BA2E, 0x44BA5D, 0x44BAA2, 0x44BAE0, 0x44BAE8, 0x44BBC8]
STOCK_DETAILS = 0x51E220
# Absolute operands inside the stock manager object other than `mov ecx`.
HEADER_REFS = [0x46541D, 0x46543E, 0x46545F, 0x465475, 0x46549A, 0x4654B5, 0x4654CF, 0x4654E0,
               0x466E50, 0x466E8F, 0x466EB8, 0x466FAE, 0x46716F, 0x46718C, 0x4671B1]
RECORD_FIELD_REFS = [0x442B0B, 0x442B11]
MANAGER_IMMEDIATES = 445
TAIL_REFS = 24
# Stock `mov ecx, 0x554148` that another patch replaces with a jump to its own
# code (which repeats the instruction there): the row stands aside when that
# patch is selected, and the composition below rewrites the moved copy.
YIELDS = {
    # Heathen Mommy Puzzle Restoration: the end of new-game Heathen creation
    # (0x424F69 -> 0x494620).
    0x424F69: "vv5_heathen_mommy_puzzle",
}


# ---- other patches' own code that names the table ------------------------
# Applied after every other patch, each only when its owner is selected.  A
# pattern must match EXACTLY `count` times inside the bytes that owner wrote
# (its rows and its appended or overlaid code), so a drifted owner fails the
# build instead of half-composing.
def _hex32(value: int) -> str:
    return struct.pack("<I", value).hex().upper()


def record_va(index: int, field: int = 0) -> int:
    return MANAGER + RECORD_BASE_OFFSET + index * STRIDE + field


STOCK_RECORDS = STOCK_MANAGER + RECORD_BASE_OFFSET
STOCK_MASK_TABLE = 0x7B1D20
SLOT_GATE_OLD = "813DE6F1410096000000"     # cmp dword ptr [0x41F1E6], 150
SLOT_GATE_NEW = "813DE6F14100" + _hex32(SLOTS)

COMPOSITIONS: dict[str, list[dict]] = {
    "vv5_enable_origins_exclusive_features": [
        # Since v1.35.52 the only Origins code naming the manager is the Task9
        # page's selected-villager getter; the .shr get_record helpers and the
        # page's resolve_manager were unreachable and are gone.
        {"find": "B9" + _hex32(STOCK_MANAGER), "replace": "B9" + _hex32(MANAGER), "count": 1,
         "purpose": "Origins code: the relocated villager manager (the Task9 page's selected-villager getter)"},
        {"find": "BE" + _hex32(STOCK_RECORDS) + "BB96000000",
         "replace": "BE" + _hex32(record_va(0)) + "BB" + _hex32(SLOTS), "count": 5,
         "purpose": "Origins village-wide actions: walk the 256 records of the relocated table"},
        {"find": "68" + _hex32(STOCK_RECORDS), "replace": "68" + _hex32(record_va(0)), "count": 2,
         "purpose": "Origins companion calls: hand over the relocated table's first record"},
        # The dispatch helper 0x494EA0 (village-wide first record, the inline
        # Cure All loop and its `inc [0x55490C]`) and the legacy .shr Tech
        # bodies were unreachable and are removed since v1.35.52; nothing of
        # theirs is composed here.
        {"find": "81FB96000000", "replace": "81FB" + _hex32(SLOTS), "count": 2,
         "purpose": "Origins selected-villager gates: any index of the 256 slots"},
        {"find": SLOT_GATE_OLD, "replace": SLOT_GATE_NEW, "count": 4,
         "purpose": "Origins Task9 Food Doubler rows: the slot count 0x41F1E6 holds is this build's own 256"},
        {"find": "2D" + _hex32(STOCK_RECORDS), "replace": "2D" + _hex32(record_va(0)), "count": 2,
         "purpose": "Origins mask helpers: a record's index in the relocated table"},
        {"find": "3D96000000", "replace": "3D" + _hex32(SLOTS), "count": 2,
         "purpose": "Origins mask helpers: indices 0..255"},
        # (mask_load_once, the sixth reference, and the page header with its
        # 150 bound were unreachable and are zeroed since v1.35.52.)
        {"find": _hex32(STOCK_MASK_TABLE), "replace": _hex32(MASK_TABLE), "count": 5,
         "purpose": "Origins mask helpers: the 256-villager mask table in the 256 section"},
    ],
    "vv5_heathen_mommy_puzzle": [
        {"find": "B9" + _hex32(STOCK_MANAGER), "replace": "B9" + _hex32(MANAGER), "count": 3,
         "purpose": "Heathen Mommy sequence: the relocated villager manager (the moved stock "
                    "`mov ecx` and two Heathen creations)"},
    ],
    "vv5_write_parentage_log": [
        {"find": "68" + _hex32(STOCK_MANAGER), "replace": "68" + _hex32(MANAGER), "count": 1,
         "purpose": "parentage stub: pass the relocated villager manager"},
        {"find": "81C1" + _hex32(STOCK_RECORDS), "replace": "81C1" + _hex32(record_va(0)), "count": 1,
         "purpose": "parentage stub: first record of the relocated table"},
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

    def text(self) -> tuple[int, int, int]:
        for name, rva, vsize, rptr, rsize in self.sections:
            if name == ".text":
                return IMAGE_BASE + rva, rptr, vsize
        raise ValueError(".text missing")

    def sweep(self):
        """Linear sweep of .text (an undecodable byte is stepped over)."""
        va0, raw, size = self.text()
        code = self.data[raw:raw + size]
        pos = 0
        while pos < len(code):
            last = None
            for i in self.md.disasm(code[pos:], va0 + pos):
                yield i
                last = i
            pos = pos + 1 if last is None else last.address - va0 + last.size


def row(img: Image, va: int, after: bytes, purpose: str) -> dict:
    o = img.off(va)
    before = img.data[o:o + len(after)]
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
    assert size == 4, (hex(va), size)
    struct.pack_into("<I", raw, pos, new & 0xFFFFFFFF)
    return row(img, va, bytes(raw), purpose)


def replace_disp(img: Image, va: int, old: int, new: int, purpose: str) -> dict:
    i = img.insn(va)
    mems = [op for op in i.operands if op.type == CS_OP_MEM]
    assert len(mems) == 1 and (mems[0].mem.disp & 0xFFFFFFFF) == old, (hex(va), i.op_str)
    pos = i.disp_offset
    raw = bytearray(i.bytes)
    assert struct.unpack_from("<I", raw, pos)[0] == old, (hex(va), i.op_str)
    struct.pack_into("<I", raw, pos, new & 0xFFFFFFFF)
    return row(img, va, bytes(raw), purpose)


def rel32(src: int, dst: int) -> bytes:
    return struct.pack("<i", dst - (src + 5))


def build_code_page() -> tuple[bytes, dict[str, int]]:
    """The detours, assembled at their fixed addresses in the .vv256 page."""
    T = COMPACT_TABLE
    S = SCRATCH
    E = COMPACT_ENTRY
    blocks: list[tuple[str, str]] = [
        # 0x4714A0's body: (male count, female count) over every record whose
        # +0x1C40 is positive, by +0x1B90 (0 male, 1 female; any other value
        # is not counted) -- the stock tests, one record at a time.
        # In: ecx = manager, edx = &males, esi = &females.  Back at 0x471585.
        ("tally", f"""
            lea eax, [ecx + 0x1bd8]
            mov edi, {SLOTS}
        tally_next:
            cmp dword ptr [eax + 0xb0], 0
            jle tally_skip
            mov ecx, dword ptr [eax]
            test ecx, ecx
            jne tally_female
            add dword ptr [edx], 1
            jmp tally_skip
        tally_female:
            cmp ecx, 1
            jne tally_skip
            add dword ptr [esi], ecx
        tally_skip:
            add eax, 0x{STRIDE:x}
            sub edi, 1
            jne tally_next
            jmp 0x471585
        """),
        # 0x4245EE: the stock save call is (payload, size, slot) with the
        # payload at GameState+8 (esi = GameState).  Assemble the 256-format
        # payload in the scratch buffer: the stock 0x17D78 bytes; the saved
        # villagers 0..min(n,150)-1 in the stock table, with the stock end
        # flag at entry n when n < 150 (exactly the stock writer's bytes);
        # villagers 150..n-1 in the extension, zero after them.  n is the
        # first entry of the compact table whose flag is 0.
        # Returns eax = payload, ecx = GameState.
        ("save_prep", f"""
            push esi
            push edi
            push ebx
            lea esi, [esi + 8]
            mov edi, 0x{S:X}
            mov ecx, 0x{STOCK_PAYLOAD // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            xor ebx, ebx
        count_next:
            imul eax, ebx, 0x{E:X}
            cmp byte ptr [eax + 0x{T:X}], 0
            je counted
            add ebx, 1
            cmp ebx, {SLOTS}
            jb count_next
        counted:
            mov ecx, ebx
            cmp ecx, {STOCK_SLOTS}
            jbe stock_part
            mov ecx, {STOCK_SLOTS}
        stock_part:
            imul ecx, ecx, 0x{E // 4:X}
            mov esi, 0x{T:X}
            mov edi, 0x{S + STOCK_COMPACT_IN_PAYLOAD:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            cmp ebx, {STOCK_SLOTS}
            jae no_stock_flag
            mov byte ptr [edi], 0
        no_stock_flag:
            mov edi, 0x{S + STOCK_PAYLOAD:X}
            mov esi, 0x{T + STOCK_SLOTS * E:X}
            xor ecx, ecx
            sub ebx, {STOCK_SLOTS}
            jbe ext_copied
            imul ecx, ebx, 0x{E // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
        ext_copied:
            mov ecx, 0x{S + PAYLOAD:X}
            sub ecx, edi
            shr ecx, 2
            xor eax, eax
            rep stosd dword ptr es:[edi], eax
            pop ebx
            pop edi
            pop esi
            mov ecx, esi
            mov eax, 0x{S:X}
            ret
        """),
        # 0x4256F9 (ebx = GameState, esi = slot, the load temporary at
        # [esp+0x90]): read the slot's payload -- the 256 size first, then the
        # stock size (an old save: its extension reads as empty) -- copy the
        # stock part into the temporary the stock code copies into the game
        # state, and rebuild entries 0..255 of the compact table from both
        # parts.  Entry 256 is never written and stays zero, so the reader
        # stops at 256 villagers at most.
        # Back at 0x425716 (the stock copy), or 0x42567F (load failed).
        ("load_cave", f"""
            push esi
            push 0x{PAYLOAD:X}
            push 0x{S:X}
            mov ecx, ebx
            call 0x403770
            test al, al
            jnz load_new
            push esi
            push 0x{STOCK_PAYLOAD:X}
            push 0x{S:X}
            mov ecx, ebx
            call 0x403770
            test al, al
            jz load_fail
            push edi
            xor eax, eax
            mov edi, 0x{S + STOCK_PAYLOAD:X}
            mov ecx, 0x{EXTENSION // 4:X}
            rep stosd dword ptr es:[edi], eax
            pop edi
        load_new:
            push esi
            push edi
            mov esi, 0x{S:X}
            lea edi, [esp + 0x98]
            mov ecx, 0x{STOCK_PAYLOAD // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            mov esi, 0x{S + STOCK_COMPACT_IN_PAYLOAD:X}
            mov edi, 0x{T:X}
            mov ecx, 0x{STOCK_SLOTS * E // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            mov esi, 0x{S + STOCK_PAYLOAD:X}
            mov ecx, 0x{EXTENSION // 4:X}
            rep movsd dword ptr es:[edi], dword ptr [esi]
            pop edi
            pop esi
            jmp 0x425716
        load_fail:
            jmp 0x42567f
        """),
    ]
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


def picker_rows(img: Image) -> list[dict]:
    """Grow each picker's frame so each of its index arrays holds 256 entries.

    The arrays sit at the bottom of the frame (above a few small locals), one
    after another.  An esp-relative operand moves up by GROWTH for every
    array that ends at or below it: an array's own indexed accesses move by
    the growth of the arrays below it, and the arguments and the return
    address above the last array move by the growth of all of them.  The
    frame's `sub esp` / `add esp` grow by the same total; nothing below the
    first array moves.  (Pushes inside the function add up to 0x10 to every
    displacement, which is far less than an array.)"""
    out = []
    for start, end, arrays, frame in PICKERS:
        o0 = img.off(start)
        frames = []
        total = GROWTH * len(arrays)
        ends = [base + STOCK_ARRAY for base in arrays]

        def shift(disp: int, indexed: bool) -> int:
            if indexed:
                (k,) = [j for j, base in enumerate(arrays) if base <= disp < base + 0x10]
                return GROWTH * k
            below = [base for base in arrays if base - 0x10 <= disp < base + 0x10]
            if below:
                return GROWTH * arrays.index(below[0])
            assert all(not (base + 0x10 <= disp < e - 0x10) for base, e in zip(arrays, ends)), (hex(start), hex(disp))
            assert disp < arrays[0] or disp >= ends[-1] - 0x10, (hex(start), hex(disp))
            return total if disp >= ends[-1] - 0x10 else 0

        for i in img.md.disasm(img.data[o0:img.off(end)], start):
            if i.mnemonic in ("sub", "add") and i.op_str == f"esp, 0x{frame:x}":
                frames.append(i.address)
                out.append(replace_imm(img, i.address, frame, frame + total,
                                       f"widen the picker's index arrays to {SLOTS} entries (0x{start:X})"))
                continue
            if i.address == MEMSET_COUNTS:
                out.append(replace_imm(img, i.address, STOCK_ARRAY, SLOTS * 4,
                                       "clear all 256 per-villager counts (0x471EB0)"))
                continue
            for op in i.operands:
                if op.type != CS_OP_MEM or i.reg_name(op.mem.base) != "esp":
                    continue
                disp = op.mem.disp
                if disp == 0 and not op.mem.index:
                    continue                       # lea esp, [esp]: alignment padding
                if op.mem.index:
                    assert op.mem.scale == 4, (hex(i.address), i.op_str)
                move = shift(disp, bool(op.mem.index))
                if move:
                    # replace_disp checks the operand is a 4-byte displacement
                    out.append(replace_disp(img, i.address, disp, disp + move,
                                            f"{'index array' if op.mem.index else 'argument or array'} above the "
                                            f"widened index arrays (0x{start:X})"))
        assert len(frames) >= 1, (hex(start), frames)
    return out


def scan_object_operands(img: Image) -> dict[int, tuple[str, int]]:
    """Every .text instruction with an operand inside the stock manager
    object: address -> (kind, value)."""
    found: dict[int, tuple[str, int]] = {}
    lo, hi = STOCK_MANAGER, STOCK_MANAGER + STOCK_MANAGER_SIZE
    for i in img.sweep():
        for op in i.operands:
            if op.type == CS_OP_IMM:
                v = op.imm & 0xFFFFFFFF
                if lo <= v < hi:
                    found[i.address] = ("imm", v)
            elif op.type == CS_OP_MEM:
                v = op.mem.disp & 0xFFFFFFFF
                if lo <= v < hi:
                    found[i.address] = ("disp", v)
    return found


def scan_values(img: Image, values) -> dict[int, tuple[str, int]]:
    """Every .text instruction with an immediate or displacement in `values`."""
    found: dict[int, tuple[str, int]] = {}
    for i in img.sweep():
        for op in i.operands:
            if op.type == CS_OP_IMM and (op.imm & 0xFFFFFFFF) in values:
                found[i.address] = ("imm", op.imm & 0xFFFFFFFF)
            elif op.type == CS_OP_MEM and (op.mem.disp & 0xFFFFFFFF) in values:
                found[i.address] = ("disp", op.mem.disp & 0xFFFFFFFF)
    return found


def _builds_json() -> dict:
    return json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8-sig"))


def build() -> dict:
    data = STOCK_VV5.read_bytes()
    if hashlib.sha256(data).hexdigest().upper() != STOCK_SHA256:
        raise SystemExit("stock New Believers executable SHA-256 mismatch")
    img = Image(data)
    manifest = _builds_json()
    rows: list[dict] = []

    # 1. every operand inside the stock manager object
    operands = scan_object_operands(img)
    movs = sorted(va for va, (k, v) in operands.items() if k == "imm" and v == STOCK_MANAGER)
    assert len(movs) == MANAGER_IMMEDIATES, len(movs)
    assert data.count(b"\xB9" + struct.pack("<I", STOCK_MANAGER)) == MANAGER_IMMEDIATES
    assert sorted(set(operands) - set(movs)) == sorted(HEADER_REFS + RECORD_FIELD_REFS), \
        sorted(hex(a) for a in set(operands) - set(movs))
    fun_rows = {p["id"]: p for p in manifest["fun_patches"]}
    for va in movs:
        i = img.insn(va)
        assert i.mnemonic == "mov" and i.op_str == "ecx, 0x554148", (hex(va), i.op_str)
        r = row(img, va, b"\xB9" + struct.pack("<I", MANAGER),
                "point this villager-manager call at the relocated manager")
        if va in YIELDS:
            feature_id = YIELDS[va]
            (theirs,) = [p for p in fun_rows[feature_id]["patches"] if p["offset"] == r["offset"]]
            assert theirs["before"] == r["before"], (hex(va), theirs)
            r["yield_to"] = {"feature": feature_id, "after": theirs["after"]}
        rows.append(r)
    assert set(YIELDS) <= set(movs)
    for va in HEADER_REFS:
        old = operands[va][1]
        assert STOCK_MANAGER < old < STOCK_MANAGER + RECORD_BASE_OFFSET, hex(va)
        rows.append(replace_disp(img, va, old, MANAGER + (old - STOCK_MANAGER),
                                 "villager-manager header field: the relocated manager"))
    for va in RECORD_FIELD_REFS:
        old = operands[va][1]
        field = old - STOCK_RECORDS
        assert field in (0x1C98, 0x1C9C), (hex(va), hex(old))
        rows.append(replace_disp(img, va, old, record_va(0, field),
                                 "villager position by index: the relocated record table"))

    # 2. the manager's tail, re-laid for 256
    tail = scan_values(img, set(TAIL_MAP))
    assert len(tail) == TAIL_REFS, sorted(hex(a) for a in tail)
    names = {old: what for old, _, what in TAIL_FIELDS}
    for va, (kind, old) in sorted(tail.items()):
        purpose = f"villager-manager tail: the {names[old]} of the relocated manager"
        if kind == "imm":
            rows.append(replace_imm(img, va, old, TAIL_MAP[old], purpose))
        else:
            rows.append(replace_disp(img, va, old, TAIL_MAP[old], purpose))

    # 3. slot bounds and the reverse-scan start points
    for va, old, new, what in BOUNDS:
        rows.append(replace_imm(img, va, old, new, f"{SLOTS} slots: {what}"))
    for va, field, what in ENDPOINTS:
        old149 = RECORD_BASE_OFFSET + (STOCK_SLOTS - 1) * STRIDE + field
        new255 = RECORD_BASE_OFFSET + (SLOTS - 1) * STRIDE + field
        i = img.insn(va)
        if any(op.type == CS_OP_IMM for op in i.operands):
            rows.append(replace_imm(img, va, old149, new255, what))
        else:
            rows.append(replace_disp(img, va, old149, new255, what))

    # 4. the pickers' index arrays
    rows.extend(picker_rows(img))

    # 5. Villager Details list: every operand naming it is one of DETAILS_REFS
    details = scan_values(img, set(range(STOCK_DETAILS - 4, STOCK_DETAILS + STOCK_SLOTS * 4)))
    assert sorted(details) == sorted(DETAILS_REFS), sorted(hex(a) for a in details)
    for va in DETAILS_REFS:
        i = img.insn(va)
        (m,) = [op for op in i.operands if op.type == CS_OP_MEM]
        old = m.mem.disp & 0xFFFFFFFF
        assert old in (STOCK_DETAILS, STOCK_DETAILS - 4) and m.mem.scale == 4, (hex(va), i.op_str)
        rows.append(replace_disp(img, va, old, DETAILS_LIST + (old - STOCK_DETAILS),
                                 f"Villager Details: the {SLOTS}-entry believer list"))

    page, L = build_code_page()

    # 6. the unrolled sex tally
    rows.append(row(img, 0x4714B6, b"\xE9" + rel32(0x4714B6, L["tally"]) + b"\x90" * 6,
                    "male/female tally: one 256-record loop instead of 25 x 6 unrolled records (0x4714A0)"))

    # 7. save: compact table, payload assembly, load
    T = COMPACT_TABLE
    rows.append(row(img, 0x46F9D4, b"\x8D\x87" + struct.pack("<I", T) + b"\x90" * 6,
                    "save writer: pack villagers into the 257-entry compact table"))
    rows.append(row(img, 0x46FA04, b"\x90" * 5 + bytes.fromhex("69DB18010000") + b"\xC6\x83"
                    + struct.pack("<I", T) + b"\x00\x90",
                    "save writer: end the 257-entry compact table after the last villager"))
    rows.append(row(img, 0x46FA44, b"\x80\xBE" + struct.pack("<I", T) + b"\x00" + b"\x90" * 6,
                    "save reader: read the compact entry's flag from the 257-entry table"))
    rows.append(row(img, 0x46FA53, b"\x8D\x86" + struct.pack("<I", T) + b"\x90" * 6,
                    "save reader: read villagers from the 257-entry compact table"))
    rows.append(replace_imm(img, 0x46FA73, STOCK_SLOTS * COMPACT_ENTRY, SLOTS * COMPACT_ENTRY,
                            "save reader: stop after 256 compact entries"))
    rows.append(row(img, 0x4245EE,
                    b"\x57\xE8" + rel32(0x4245EF, L["save_prep"]) + b"\x68" + struct.pack("<I", PAYLOAD) + b"\x50",
                    "save: write the stock payload followed by villagers 150..255"))
    rows.append(row(img, 0x4256F9, b"\xE9" + rel32(0x4256F9, L["load_cave"]) + b"\x90" * 0x18,
                    "load: accept a 256-format save, or an old 150-slot save with no extension"))

    # every row is unique and non-overlapping
    spans = sorted((int(r["offset"], 16), len(r["after"]) // 2) for r in rows)
    for (a, n), (b, _) in zip(spans, spans[1:]):
        assert a + n <= b, (hex(a), hex(b))

    # 8. population modes and the slot-safety layer
    (vv5,) = [g for g in manifest["games"] if g["id"] == "vv5"]
    mode_rows = {"stock": []}
    for mode, edits, purposes in (
        ("collection_progression",
         {"0x94500": ("81C687000000", "81C6F1000000")},
         {"0x72C49": "route the cap comparison through the base-241 calculation that counts every occupied "
                     "or reserved slot",
          "0x94500": "add base 241 with a 32-bit immediate, keep the 0-15 collection bonus (256 at most), "
                     "compare total slot demand"}),
        ("immediate_fixed",
         {"0x72C04": ("BE3C000000", "BEA6000000")},
         {"0x72C04": "Immediate Fixed: 166 + 90 = 256 at every collection state",
          "0x72C49": "route the fixed cap comparison through the total occupied-or-reserved slot counter",
          "0x94500": "complete the fixed 256 calculation, compare total slot demand, and resume the stock "
                     "housing checks"}),
    ):
        out = []
        for src in vv5["variants"][mode]["patches"]:
            after = src["after"]
            if src["offset"] in edits:
                old, new = edits[src["offset"]]
                assert after.count(old) == 1, (mode, src["offset"])
                after = after.replace(old, new)
            out.append({"offset": src["offset"], "before": src["before"], "after": after,
                        "purpose": purposes[src["offset"]]})
        assert set(edits) <= {r["offset"] for r in out} and set(purposes) == {r["offset"] for r in out}
        mode_rows[mode] = out
    safety_rows = build_safety_rows(vv5)

    def page_entry() -> dict:
        return {"hex": page.hex().upper(), "sha256": hashlib.sha256(page).hexdigest().upper()}

    return {
        "rows": rows,
        "mode_rows": mode_rows,
        "safety_rows": safety_rows,
        "code_pages": {mode: page_entry() for mode in ("stock", "collection_progression", "immediate_fixed")},
        "compositions": COMPOSITIONS,
        "layout": {
            "stock_manager": f"0x{STOCK_MANAGER:X}",
            "manager": f"0x{MANAGER:X}",
            "record_stride": f"0x{STRIDE:X}",
            "record_base_offset": f"0x{RECORD_BASE_OFFSET:X}",
            "slots": SLOTS,
            "physical_records": SLOTS,
            "section_va": f"0x{SECTION_VA:X}",
            "section_end": f"0x{SECTION_END:X}",
            "code_page_va": f"0x{CODE_VA:X}",
            "details_list": f"0x{DETAILS_LIST:X}",
            "mask_table": f"0x{MASK_TABLE:X}",
            "manager_tail": f"0x{TAIL:X}",
            "compact_table": f"0x{COMPACT_TABLE:X}",
            "scratch_payload": f"0x{SCRATCH:X}",
            "stock_payload_size": f"0x{STOCK_PAYLOAD:X}",
            "payload_size": f"0x{PAYLOAD:X}",
            "section_name": ".vv256",
            "filler_section_name": ".vv256z",
        },
        "labels": {k: f"0x{v:X}" for k, v in L.items()},
    }


def build_safety_rows(vv5: dict) -> list[dict]:
    """The automatic slot-safety rows of data/builds.json, for 256 slots.

    Same code at the same addresses; only the slot arithmetic changes:
    triplets and twins need 3 / 2 free slots of 256 (<= 253 / <= 254
    demanded), Barrel O' Babies, Barrel O' Heathen Babies and Chutes Without
    Ladders need one, Abandoned Infants are clamped to the slots left of 256
    and picked by the relocated manager, and the demand counter walks the
    relocated table."""
    stock_rows = {r["offset"]: r for r in vv5["safety_patches"]}
    out = []
    edits = {
        "0x94340": [("3D93000000", "3DFD000000")],
        "0x94360": [("3D94000000", "3DFE000000")],
        "0x944C0": [("B9" + _hex32(STOCK_RECORDS), "B9" + _hex32(record_va(0))),
                    ("BA96000000", "BA" + _hex32(SLOTS))],
        "0x94560": [("3D96000000", "3D" + _hex32(SLOTS))],
        "0x94580": [("3D96000000", "3D" + _hex32(SLOTS))],
        "0x945A0": [("3D96000000", "3D" + _hex32(SLOTS))],
        "0x945E0": [("0596000000", "05" + _hex32(SLOTS)),
                    ("B9" + _hex32(STOCK_MANAGER), "B9" + _hex32(MANAGER))],
    }
    purposes = {
        "0x65F10": "route triplet selection through the 256-slot saturation guard",
        "0x94340": "keep triplets only when three of the 256 villager slots remain after active Heathens, "
                   "corpses and reservations",
        "0x65F23": "route twin selection through the 256-slot saturation guard",
        "0x94360": "keep twins only when two of the 256 villager slots remain after active Heathens, "
                   "corpses and reservations",
        "0x944C0": "count all active records of the relocated 256-record table plus nursing babies that "
                   "still require future records",
        "0x151D0": "recheck all occupied and reserved slots of 256 before Barrel O' Babies creates its first believer",
        "0x94560": "skip the first believer child at 256 physical slots and otherwise resume the stock outcome",
        "0x152B0": "recheck all occupied and reserved slots of 256 before Barrel O' Heathen Babies creates "
                   "its first Heathen",
        "0x94580": "skip the first Heathen child at 256 physical slots and otherwise resume the stock outcome",
        "0x15410": "recheck all occupied and reserved slots of 256 before Chutes Without Ladders creates its first child",
        "0x945A0": "skip the first Chutes child at 256 physical slots and otherwise resume the stock outcome",
        "0x155E0": "route Abandoned Infants through a remaining-slot clamp",
        "0x945E0": "reserve no more than the lesser of six abandoned infants or the slots left of 256, "
                   "picked by the relocated manager",
    }
    for offset, src in stock_rows.items():
        after = src["after"]
        for old, new in edits.get(offset, []):
            assert after.count(old) == 1, (offset, old)
            after = after.replace(old, new)
        out.append({"offset": offset, "before": src["before"], "after": after,
                    "purpose": purposes[offset]})
    assert set(edits) <= set(stock_rows) and set(purposes) == set(stock_rows)
    return out


DESCRIPTION = (
    "EXPERIMENTAL. Gives New Believers 256 villager slots instead of 150 (believers, Heathens and "
    "Reanimate stand-ins share them, as in the stock game). The game's villager table is moved to a "
    "new, larger place in memory and every part of the game that walks it -- births, Heathens, island "
    "events, the Villager Details screen, saving and loading -- is widened to match. With Collection "
    "Progression Max Pop the cap becomes 241 plus the collection bonus (256 with everything); with "
    "Immediate Fixed Max Pop it is 256 at once; with No Population Increase the stock cap of 105 is "
    "unchanged, only the table is larger. The patched game is named \"... - Modded 256\" and keeps its "
    "saves in their own \"Virtual Villagers - New Believers - Modded 256\" folder, so they never mix "
    "with 150-slot saves: a 256 save cannot be opened by a 150-slot game. Copy an old save into that "
    "folder and it loads, then is saved in the 256 format from then on. Off by default."
)


def main() -> int:
    body = build()
    record = {
        "id": FEATURE_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv5",
        "name": "256 Villagers (Experimental)",
        "description": DESCRIPTION,
        "output_tag": "256 Villagers",
        "behavior_changes": [
            "The villager table has 256 slots; the population modes that raise the cap reach 256.",
            "Saves hold up to 256 villagers in a longer save file that only this build reads.",
        ],
        "explicit_non_changes": [
            "No Population Increase keeps the stock cap of 105.",
            "Nothing changes for a build that does not tick this patch.",
        ],
        "evidence_status": "static exact-build implementation with emulation of the replaced routines; live confirmation pending",
        "patches": [],
        "population_256": body,
    }
    OUT.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(body['rows'])} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
