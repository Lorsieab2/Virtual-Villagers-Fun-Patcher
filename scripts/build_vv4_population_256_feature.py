"""Generate data/vv4_population_256_feature.json: "256 Villagers (Experimental)" for The Tree of Life.

WHAT IT DOES

The Tree of Life keeps its villagers in one static object, the population
manager at 0x50E568: a 0x44-byte header, 150 records of 0x2E3C bytes from
0x50E5AC, and a 0xC-byte tail nothing reads.  The object fills the zero part
of .data up to unrelated globals (0x6BFCE0 onwards), so it cannot grow where
it is.  This feature MOVES it:

  * a new section at the fixed address 0x7F0000 holds a page of code (the
    detours below) and, as zero-fill, the Villager Details list, the
    relocated manager at 0x800000 (header plus 256 records), the compact save
    table and a save scratch buffer.  A filler section (no file bytes) pads
    the image up to 0x7F0000, so the address never depends on which other
    patches appended pages before it;
  * every `mov ecx, 0x50E568` (280 of them, the way the manager pointer
    enters the code), the 15 absolute loads of manager header fields and the
    4 absolute record-field loads are pointed at the relocated manager --
    every operand of .text that falls inside the stock object is one of
    these, which the generator re-verifies with a full disassembly;
  * every slot bound (57 sites: loop counts 150 -> 256, the getter, the
    selection setter and the static constructor 149 -> 255, the reverse scans
    149 -> 255 with their start pointers moved to record 255) is widened, and
    the 150-dword index array of the ten random pickers is widened to 256 by
    growing each picker's stack frame (the pickers make the very same
    rand(count) call, so the random stream is used exactly as before);
  * the sex tally 0x467650, unrolled six records at a time (25 x 6 = 150;
    256 is no multiple of 6), runs as a plain 256-record loop with the same
    tests;
  * the Villager Details screen's living list (a static int[150] at
    0x4D8E00, followed by its own count at 0x4D9060) moves to a 256-entry
    buffer, so more than 150 living villagers never overwrite its count;
  * the save keeps the stock payload byte for byte and appends villagers
    150..255 after it (see SAVE FORMAT);
  * the population modes reach 256 (Collection Progression: base 231 + 0..25
    collection points; Immediate Fixed: 256 at once; stock mode keeps the
    stock cap of 115) and the automatic slot-safety rows guard 256 slots.

Every byte this writes is guarded by the stock bytes it replaces; the patcher
applies the whole feature after every other patch, and rewrites the manager
references inside other patches' own code through the per-feature
`compositions` table, each with an exact expected count.

SAVE FORMAT

A stock save is a 0x18-byte header (`ldwg`, ..., the payload size at +0x10)
and a payload of 0x1710C bytes: the game state from +8.  Villagers are saved
as a compact table of 0x104-byte entries at GameState+0xC868 (150 entries,
ending at +0x160C0 where the 0x4D8BF8 progress block's size dword starts),
written by 0x4660A0 and read back by 0x466110 until an entry whose first byte
is 0.

This feature keeps the compact table for ALL 257 entries (256 + an end-flag
slot) in the new section (`compact_table`); the writer and reader use it
directly, so the end flag can never land on the progress block (the stock
game's exactly-150 defect cannot happen in this build).  On save, the payload
is assembled in a scratch buffer: the stock 0x1710C bytes, with the saved
villagers 0..149 (and the end flag when fewer than 150 were saved) put in
their stock place exactly as the stock writer would, then villagers 150..255
appended (0x6BA8 bytes, zero after the last villager) -- payload 0x1DCB4.  On
load the reader tries the 256 size first and then the stock size, so an old
150-slot save loads (its extension reads as empty) and is written back in the
256 format at its next save.  The header's size field tells the two apart; a
256-format save is never offered to a stock build, because the 256 build uses
its own save folder ("... - Modded 256"), and a stock build refuses it.

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
STOCK_VV4 = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
STOCK_SHA256 = "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"
OUT = ROOT / "data" / "vv4_population_256_feature.json"

FEATURE_ID = "vv4_population_256"
IMAGE_BASE = 0x400000

# ---- geometry -----------------------------------------------------------
STOCK_MANAGER = 0x50E568
STRIDE = 0x2E3C
RECORD_BASE_OFFSET = 0x44
STOCK_SLOTS = 150
SLOTS = 256
TAIL = 0xC                          # after the last record; nothing reads it
STOCK_MANAGER_SIZE = RECORD_BASE_OFFSET + STOCK_SLOTS * STRIDE + TAIL   # 0x1B1778

SECTION_VA = 0x7F0000              # .vv256: one page of code, then zero-fill
CODE_VA = SECTION_VA
DETAILS_LIST = 0x7F1000            # 256 dwords
MANAGER = 0x800000
MANAGER_SIZE = RECORD_BASE_OFFSET + SLOTS * STRIDE + TAIL                # 0x2E3C50
COMPACT_ENTRY = 0x104
COMPACT_TABLE = 0xAE4000           # 257 entries (256 + end-flag slot)
COMPACT_TABLE_SIZE = (SLOTS + 1) * COMPACT_ENTRY
SCRATCH = 0xAF5000                 # one complete 256-format payload
STOCK_PAYLOAD = 0x1710C
EXTENSION = (SLOTS - STOCK_SLOTS) * COMPACT_ENTRY           # 0x6BA8
PAYLOAD = STOCK_PAYLOAD + EXTENSION                         # 0x1DCB4
SECTION_END = 0xB13000
STOCK_COMPACT_IN_PAYLOAD = 0xC868 - 8                       # GameState+0xC868

assert MANAGER + MANAGER_SIZE <= COMPACT_TABLE
assert COMPACT_TABLE + COMPACT_TABLE_SIZE <= SCRATCH
assert SCRATCH + PAYLOAD <= SECTION_END
assert DETAILS_LIST + SLOTS * 4 <= MANAGER
assert STOCK_PAYLOAD % 4 == 0 and EXTENSION % 4 == 0 and COMPACT_ENTRY % 4 == 0

# ---- site tables (stock VV4, traced; every one is re-verified below) ------
# (VA, stock immediate, new immediate, what the loop is)
BOUNDS = [
    (0x42001A, 150, 256, "load/elapsed-time scan over every record (0x41FEF0); the slot count Origins and Time Warp read at 0x42001C"),
    (0x4202A6, 150, 256, "second scan over every record (0x41FEF0)"),
    (0x420515, 150, 256, "periodic world update over every record (0x420330)"),
    (0x43360E, 150, 256, "every index through the getter (0x4335D0)"),
    (0x43696A, 150, 256, "records with job 0x79 (0x436920)"),
    (0x43BBA8, 150, 256, "village reset: clear every record's alive flag (0x43BB60)"),
    (0x4482DD, 150, 256, "Villager Details living-list builder (0x448290)"),
    (0x4603F2, 150, 256, "nearest-villager search (0x460370)"),
    (0x465F56, 150, 256, "init: every record learns its own index (0x465F20)"),
    (0x466044, 149, 255, "index -> record getter: 0 <= i <= 255 (0x466040)"),
    (0x466084, 150, 256, "first record matching 0x45DD10 (0x466060)"),
    (0x4660AB, 150, 256, "SAVE: pack every living villager into the compact table (0x4660A0)"),
    (0x466118, 150, 256, "LOAD: reset every record before reading the compact table (0x466110)"),
    (0x466245, 150, 256, "reset every record (0x466240)"),
    (0x46628D, 150, 256, "ALLOCATOR: first free slot (0x466270)"),
    (0x46629C, 150, 256, "ALLOCATOR: no free slot (0x466270)"),
    (0x46632D, 150, 256, "ALLOCATOR from a template: first free slot (0x466310)"),
    (0x46633C, 150, 256, "ALLOCATOR from a template: no free slot (0x466310)"),
    (0x46638D, 150, 256, "GHOST ALLOCATOR: first free slot (0x466370)"),
    (0x46639C, 150, 256, "GHOST ALLOCATOR: no free slot (0x466370)"),
    (0x466425, 150, 256, "per-record update of living records (0x466420)"),
    (0x46645B, 150, 256, "ageing / day tick, counter on the stack (0x466450)"),
    (0x46674E, 150, 256, "per-record scan (0x4666B0)"),
    (0x46683B, 149, 255, "world-point picker reverse scan 255..0 (0x466820)"),
    (0x4669CB, 150, 256, "villager at a point (0x466940)"),
    (0x466A0B, 149, 255, "villager-at-a-point reverse scan 255..0 (0x466A00)"),
    (0x466ADF, 149, 255, "nearby sick-villager reverse scan 255..0 (0x466AD0)"),
    (0x466BBF, 150, 256, "any villager within the radius (0x466B80)"),
    (0x466C77, 150, 256, "per-record scan (0x466BF0)"),
    (0x466C9A, 149, 255, "select a villager: -1 or 0..255 (0x466C90)"),
    (0x466D0D, 150, 256, "per-record scan (0x466CE0)"),
    (0x466D28, 150, 256, "every record (0x466D20)"),
    (0x466D68, 150, 256, "every record (0x466D60)"),
    (0x466E6D, 150, 256, "picker (0x466DA0)"),
    (0x466F0F, 150, 256, "picker (0x466EB0)"),
    (0x466F52, 150, 256, "every record (0x466F40)"),
    (0x466FB6, 150, 256, "every record (0x466FB0)"),
    (0x466FE8, 150, 256, "every record (0x466FE0)"),
    (0x467052, 150, 256, "every record (0x467040)"),
    (0x4670BD, 150, 256, "every record (0x4670B0)"),
    (0x467127, 150, 256, "every record, counter on the stack (0x467110)"),
    (0x46721A, 150, 256, "Island Event group picker (0x4671A0)"),
    (0x467302, 150, 256, "Island Event picker (0x467290)"),
    (0x4673FA, 150, 256, "Island Event picker (0x467380)"),
    (0x467498, 150, 256, "every record (0x467490); the slot count Origins reads at 0x467499"),
    (0x46755A, 150, 256, "Island Event picker (0x4674E0)"),
    (0x467618, 150, 256, "POPULATION COUNTER for the cap check (0x467610)"),
    (0x467748, 150, 256, "adults with a condition (0x467740)"),
    (0x46779E, 150, 256, "village-wide action, counter on the stack (0x467790)"),
    (0x467848, 150, 256, "any villager with a job (0x467820)"),
    (0x46786A, 150, 256, "every villager with a job (0x467860)"),
    (0x467930, 150, 256, "random villager with a job (0x4678F0)"),
    (0x467AA7, 150, 256, "filtered random villager (0x4679B0)"),
    (0x467BB0, 150, 256, "filtered random adults, Abandoned Infants too (0x467B00)"),
    (0x467C98, 150, 256, "random villager with a field value (0x467C50)"),
    (0x467CEE, 149, 255, "static constructor: construct every record (0x467CE0)"),
    (0x46844B, 150, 256, "pregnancy/birth/ageing tick, counter on the stack (0x468430)"),
]
# The reverse scans start at record 149; they must start at record 255.
# (VA, the field the start pointer is at)
ENDPOINTS = [
    (0x466843, 0x1CC7, "world-point picker reverse scan start: record 255 +0x1CC7"),
    (0x466A13, 0x1C94, "villager-at-a-point reverse scan start: record 255 +0x1C94"),
    (0x466AE4, 0x0000, "nearby sick-villager reverse scan start: record 255"),
]
# The ten pickers that collect candidate indices into a 150-dword array on
# the stack, with the address their code ends at.
PICKERS = [
    (0x466DA0, 0x466EB0), (0x466EB0, 0x466F40), (0x4671A0, 0x467290),
    (0x467290, 0x467380), (0x467380, 0x467490), (0x4674E0, 0x467610),
    (0x4678F0, 0x467980), (0x4679B0, 0x467B00), (0x467B00, 0x467C50),
    (0x467C50, 0x467CE0),
]
STOCK_ARRAY = STOCK_SLOTS * 4
GROWTH = (SLOTS - STOCK_SLOTS) * 4                           # 0x1A8
# Villager Details list (static int[150] at 0x4D8E00): every reference.
DETAILS_REFS = [0x4482CB, 0x4483C0, 0x448413, 0x44841E, 0x44844D, 0x448492, 0x4484D0, 0x4484D8, 0x4485B8]
STOCK_DETAILS = 0x4D8E00
# Absolute operands inside the stock manager object other than `mov ecx`.
HEADER_REFS = [0x45DD61, 0x45DD82, 0x45DDA1, 0x45DDBA, 0x45DDE0, 0x45DDFB, 0x45DE19, 0x45DE2A,
               0x45F748, 0x45F76C, 0x45F795, 0x45F87E, 0x45FA3F, 0x45FA5C, 0x45FA81]
RECORD_FIELD_REFS = [0x43FFB9, 0x43FFBF, 0x442BB9, 0x442BBF]
MANAGER_IMMEDIATES = 280
# Stock `mov ecx, 0x50E568` that another patch replaces with a jump to its own
# code (which repeats the instruction there): the row stands aside when that
# patch is selected, and the composition below rewrites the moved copy.
YIELDS = {
    # Origins' Barrel of Babies admission detour (0x414D50 -> 0x4894F3).
    0x414D50: ("vv4_enable_origins_exclusive_features", "vv4_origins_feature.json"),
}

# ---- other patches' own code that names the table ------------------------
# Applied after every other patch, each only when its owner is selected.  A
# pattern must match EXACTLY `count` times inside the bytes that owner wrote
# (its rows and its appended or overlaid code), so a drifted owner fails the
# build instead of half-composing.
def _hex32(value: int) -> str:
    return struct.pack("<I", value).hex().upper()


COMPOSITIONS: dict[str, list[dict]] = {
    "vv4_enable_origins_exclusive_features": [
        {"find": "B968E55000", "replace": "B9" + _hex32(MANAGER), "count": 4,
         "purpose": "Origins code: the relocated population manager (Barrel admission detour, "
                    "two Villager-menu getters, Barrel purchase gate)"},
        {"find": "B9ACE55000", "replace": "B9" + _hex32(MANAGER + RECORD_BASE_OFFSET), "count": 1,
         "purpose": "Origins village-wide upgrades: first record of the relocated table"},
        {"find": "BAACE55000", "replace": "BA" + _hex32(MANAGER + RECORD_BASE_OFFSET), "count": 1,
         "purpose": "Origins village-wide upgrades: first record of the relocated table"},
        {"find": "3D960000007D03B001C3", "replace": "3D000100007D03B001C3", "count": 2,
         "purpose": "Origins purchased-barrel room checks: room up to the 256-record table"},
        {"find": "83C0033D960000007E04", "replace": "83C0033D000100007E04", "count": 1,
         "purpose": "Origins Barrel purchase gate: refuse only when population + 3 would exceed 256 records"},
        # The Tech menu's "no room for the barrel" bit counts free records:
        # since v1.35.54 its walk starts at the stock manager's record 0
        # active byte (`mov ecx, 0x510270` = 0x50E568 + 0x44 + 0x1CC4) and
        # covers 150 records; here it starts at the relocated manager's
        # record 0 active byte and covers 256.
        {"find": "B97002510031F6BB96000000",
         "replace": "B9" + _hex32(MANAGER + RECORD_BASE_OFFSET + 0x1CC4) + "31F6BB00010000",
         "count": 1,
         "purpose": "Origins Tech menu: count free records of the relocated 256-record table "
                    "(manager + 0x44 + 0x1CC4 is record 0's active byte)"},
    ],
    "vv4_write_parentage_log": [
        {"find": "6868E55000", "replace": "68" + _hex32(MANAGER), "count": 1,
         "purpose": "parentage stub: pass the relocated population manager"},
        {"find": "81C1ACE55000", "replace": "81C1" + _hex32(MANAGER + RECORD_BASE_OFFSET), "count": 1,
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


def record_va(index: int, field: int = 0) -> int:
    return MANAGER + RECORD_BASE_OFFSET + index * STRIDE + field


def rel32(src: int, dst: int) -> bytes:
    return struct.pack("<i", dst - (src + 5))


def build_code_page(mode: str) -> tuple[bytes, dict[str, int]]:
    """The detours, assembled at their fixed addresses in the .vv256 page."""
    T = COMPACT_TABLE
    S = SCRATCH
    E = COMPACT_ENTRY
    blocks: list[tuple[str, str]] = [
        # 0x467650's body: (male count, female count) over every record whose
        # +0x1C84 is positive, by +0x1BD4 (0 male, 1 female; any other value
        # is not counted) -- the stock tests, one record at a time.
        # In: ecx = manager, edx = &males, esi = &females.  Back at 0x467735.
        ("tally", f"""
            lea eax, [ecx + 0x1bd4]
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
            jmp 0x467735
        """),
        # 0x41F12E: the stock save call is (payload, size, slot) with the
        # payload at GameState+8 (esi = GameState).  Assemble the 256-format
        # payload in the scratch buffer: the stock 0x1710C bytes; the saved
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
        # 0x41FC09 (ebx = GameState, esi = slot, the load temporary at
        # [esp+0x90]): read the slot's payload -- the 256 size first, then the
        # stock size (an old save: its extension reads as empty) -- copy the
        # stock part into the temporary the stock code copies into the game
        # state, and rebuild entries 0..255 of the compact table from both
        # parts.  Entry 256 is written only by the writer's end flag (0) and is
        # zero-fill before that, so the reader stops at 256 villagers at most.
        # Back at 0x41FC26 (the stock copy), or 0x41FB8F (load failed).
        ("load_cave", f"""
            push esi
            push 0x{PAYLOAD:X}
            push 0x{S:X}
            mov ecx, ebx
            call 0x4037e0
            test al, al
            jnz load_new
            push esi
            push 0x{STOCK_PAYLOAD:X}
            push 0x{S:X}
            mov ecx, ebx
            call 0x4037e0
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
            jmp 0x41fc26
        load_fail:
            jmp 0x41fb8f
        """),
    ]
    if mode == "collection_progression":
        # Collection Progression: base 231 + 0..25 collection points = 256.
        # 231 does not fit the stock sign-extended byte immediate.
        blocks.append(("cp_add", """
            add esi, 0xE7
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


def picker_rows(img: Image) -> list[dict]:
    """Grow each picker's frame by GROWTH so its index array holds 256
    entries.  The array sits at the bottom of the frame (above at most three
    small locals), so every esp-relative operand at or above 0x258 -- the
    arguments, the return address -- moves up by GROWTH, and the frame's
    `sub esp` / `add esp` grow by GROWTH; nothing below moves."""
    out = []
    for start, end in PICKERS:
        o0 = img.off(start)
        frames = []
        for i in img.md.disasm(img.data[o0:img.off(end)], start):
            if i.mnemonic in ("sub", "add") and i.op_str.startswith("esp, 0x2"):
                imm = i.operands[1].imm
                assert imm in (0x258, 0x25C, 0x260, 0x264), (hex(i.address), i.op_str)
                frames.append(imm)
                out.append(replace_imm(img, i.address, imm, imm + GROWTH,
                                       f"widen the picker's index array to {SLOTS} entries (0x{start:X})"))
                continue
            for op in i.operands:
                if op.type != CS_OP_MEM or i.reg_name(op.mem.base) != "esp":
                    continue
                disp = op.mem.disp
                if op.mem.index:
                    # the array itself: indexed from its bottom, never moved
                    assert disp < 0x20, (hex(i.address), i.op_str)
                    continue
                if disp >= STOCK_ARRAY:
                    # replace_disp checks the operand is a 4-byte displacement
                    out.append(replace_disp(img, i.address, disp, disp + GROWTH,
                                            f"argument above the widened index array (0x{start:X})"))
                else:
                    assert disp < 0x20, (hex(i.address), i.op_str)
        assert len(set(frames)) == 1 and len(frames) >= 2, (hex(start), frames)
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


def build() -> dict:
    data = STOCK_VV4.read_bytes()
    if hashlib.sha256(data).hexdigest().upper() != STOCK_SHA256:
        raise SystemExit("stock The Tree of Life executable SHA-256 mismatch")
    img = Image(data)
    rows: list[dict] = []

    # 1. every operand inside the stock manager object
    operands = scan_object_operands(img)
    movs = sorted(va for va, (k, v) in operands.items() if k == "imm" and v == STOCK_MANAGER)
    assert len(movs) == MANAGER_IMMEDIATES, len(movs)
    assert data.count(b"\xB9" + struct.pack("<I", STOCK_MANAGER)) == MANAGER_IMMEDIATES
    assert sorted(set(operands) - set(movs)) == sorted(HEADER_REFS + RECORD_FIELD_REFS), \
        sorted(hex(a) for a in set(operands) - set(movs))
    for va in movs:
        i = img.insn(va)
        assert i.mnemonic == "mov" and i.op_str == "ecx, 0x50e568", (hex(va), i.op_str)
        r = row(img, va, b"\xB9" + struct.pack("<I", MANAGER),
                "point this population-manager call at the relocated manager")
        if va in YIELDS:
            feature_id, path = YIELDS[va]
            manifest = json.loads((ROOT / "data" / path).read_text(encoding="utf-8"))
            (theirs,) = [p for p in manifest["patches"] if p["offset"] == r["offset"]]
            assert theirs["before"] == r["before"], (hex(va), theirs)
            r["yield_to"] = {"feature": feature_id, "after": theirs["after"]}
        rows.append(r)
    assert set(YIELDS) <= set(movs)
    for va in HEADER_REFS:
        old = operands[va][1]
        assert STOCK_MANAGER < old < STOCK_MANAGER + RECORD_BASE_OFFSET, hex(va)
        rows.append(replace_disp(img, va, old, MANAGER + (old - STOCK_MANAGER),
                                 "population-manager header field: the relocated manager"))
    for va in RECORD_FIELD_REFS:
        old = operands[va][1]
        field = old - (STOCK_MANAGER + RECORD_BASE_OFFSET)
        assert field in (0x1C94, 0x1C98), (hex(va), hex(old))
        rows.append(replace_disp(img, va, old, record_va(0, field),
                                 "villager position by index: the relocated record table"))

    # 2. slot bounds and the reverse-scan start points
    for va, old, new, what in BOUNDS:
        rows.append(replace_imm(img, va, old, new, f"{SLOTS} slots: {what}"))
    for va, field, what in ENDPOINTS:
        old149 = RECORD_BASE_OFFSET + (STOCK_SLOTS - 1) * STRIDE + field
        new255 = RECORD_BASE_OFFSET + (SLOTS - 1) * STRIDE + field
        rows.append(replace_disp(img, va, old149, new255, what))

    # 3. the pickers' index arrays
    rows.extend(picker_rows(img))

    # 4. Villager Details list
    for va in DETAILS_REFS:
        i = img.insn(va)
        (m,) = [op for op in i.operands if op.type == CS_OP_MEM]
        old = m.mem.disp & 0xFFFFFFFF
        assert old in (STOCK_DETAILS, STOCK_DETAILS - 4) and m.mem.scale == 4, (hex(va), i.op_str)
        rows.append(replace_disp(img, va, old, DETAILS_LIST + (old - STOCK_DETAILS),
                                 f"Villager Details: the {SLOTS}-entry living list"))

    pages = {}
    labels_by_mode = {}
    for mode in ("stock", "collection_progression", "immediate_fixed"):
        pages[mode], labels_by_mode[mode] = build_code_page(mode)
    L = labels_by_mode["collection_progression"]
    for mode in ("stock", "immediate_fixed"):
        for k, v in labels_by_mode[mode].items():
            assert L[k] == v

    # 5. the unrolled sex tally
    rows.append(row(img, 0x467666, b"\xE9" + rel32(0x467666, L["tally"]) + b"\x90" * 6,
                    "male/female tally: one 256-record loop instead of 25 x 6 unrolled records (0x467650)"))

    # 6. save: compact table, payload assembly, load
    T = COMPACT_TABLE
    rows.append(row(img, 0x4660C9, b"\x8D\x87" + struct.pack("<I", T) + b"\x90" * 6,
                    "save writer: pack villagers into the 257-entry compact table"))
    rows.append(row(img, 0x4660F1, b"\x90" * 5,
                    "save writer: the end flag goes into the 257-entry compact table (no game-state lookup)"))
    rows.append(row(img, 0x4660FE, b"\xC6\x83" + struct.pack("<I", T) + b"\x00\x90",
                    "save writer: end the compact table after the last villager"))
    rows.append(row(img, 0x466132, b"\x38\x1D" + struct.pack("<I", T) + b"\x90" * 5,
                    "save reader: read the first compact entry from the 257-entry table"))
    rows.append(row(img, 0x466141, b"\x8D\x86" + struct.pack("<I", T) + b"\x90" * 6,
                    "save reader: read villagers from the 257-entry compact table"))
    rows.append(row(img, 0x466166, b"\x80\xBE" + struct.pack("<I", T) + b"\x00" + b"\x90" * 6,
                    "save reader: stop at the end of the 257-entry compact table"))
    rows.append(row(img, 0x41F12E,
                    b"\x57\xE8" + rel32(0x41F12F, L["save_prep"]) + b"\x68" + struct.pack("<I", PAYLOAD) + b"\x50",
                    "save: write the stock payload followed by villagers 150..255"))
    rows.append(row(img, 0x41FC09, b"\xE9" + rel32(0x41FC09, L["load_cave"]) + b"\x90" * 0x18,
                    "load: accept a 256-format save, or an old 150-slot save with no extension"))

    # every row is unique and non-overlapping
    spans = sorted((int(r["offset"], 16), len(r["after"]) // 2) for r in rows)
    for (a, n), (b, _) in zip(spans, spans[1:]):
        assert a + n <= b, (hex(a), hex(b))

    # 7. population modes and the slot-safety layer
    mode_rows = {
        "stock": [],
        "collection_progression": [
            row(img, 0x4683EF, b"\xE8" + rel32(0x4683EF, L["cp_add"]),
                "Collection Progression: base 231 plus 0-25 collection points, 256 at most"),
        ],
        "immediate_fixed": [
            row(img, 0x4683AA, bytes.fromhex("BEA60000009090909090"),
                "Immediate Fixed: 166 + 90 = 256 at every collection state"),
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
            "physical_records": SLOTS,
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

    Same code at the same addresses; only the slot arithmetic changes:
    triplets and twins need 3 / 2 free slots of 256 (<= 253 / <= 254
    demanded), the Island Event newcomer and the Daredevil Barrel child need
    one, Abandoned Infants are clamped to the slots left of 256 and picked by
    the relocated manager, and the demand counter walks the relocated table."""
    manifest = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8-sig"))
    (vv4,) = [g for g in manifest["games"] if g["id"] == "vv4"]
    stock_rows = {r["offset"]: r for r in vv4["safety_patches"]}
    out = []
    edits = {
        "0x89020": [("3D93000000", "3DFD000000")],
        "0x89040": [("3D94000000", "3DFE000000")],
        "0x89060": [("3D96000000", "3D00010000")],
        "0x89080": [("3D96000000", "3D00010000")],
        "0x890C0": [("0596000000", "0500010000"),
                    ("B968E55000", "B9" + struct.pack("<I", MANAGER).hex().upper())],
        "0x890F0": [("BAACE55000", "BA" + struct.pack("<I", record_va(0)).hex().upper()),
                    ("B996000000", "B900010000")],
    }
    purposes = {
        "0x5E8C0": "route triplet selection through the 256-slot saturation guard",
        "0x89020": "keep triplets only when three of the 256 villager slots remain",
        "0x5E8D3": "route twin selection through the 256-slot saturation guard",
        "0x89040": "keep twins only when two of the 256 villager slots remain",
        "0x148B0": "recheck the 256-slot physical limit before an Island Event creates its first adult",
        "0x89060": "skip the event newcomer when all 256 slots are in demand or resume the complete stock outcome below",
        "0x14D90": "recheck the 256-slot physical limit before the Daredevil Barrel creates its first child",
        "0x89080": "skip the first barrel child when all 256 slots are in demand while retaining the stock later-child cap",
        "0x14FC0": "route Abandoned Infants through a remaining-slot clamp",
        "0x890C0": "reserve no more than the lesser of six abandoned infants or the slots left of 256, picked by the relocated manager",
        "0x890F0": "count VV4 physical villager demand for the 256-slot saturation guards: every occupied record of the relocated table plus the babies each pregnant mother still owes a record",
    }
    for offset, src in stock_rows.items():
        after = src["after"]
        for old, new in edits.get(offset, []):
            assert after.count(old) == 1, (offset, old)
            after = after.replace(old, new)
        out.append({"offset": offset, "before": src["before"], "after": after,
                    "purpose": purposes.get(offset, src["purpose"])})
    assert set(edits) <= set(stock_rows)
    return out


DESCRIPTION = (
    "EXPERIMENTAL. Gives The Tree of Life 256 villager slots instead of 150. The game's villager "
    "table is moved to a new, larger place in memory and every part of the game that walks it "
    "-- births, island events, the Villager Details screen, saving and loading -- is widened to "
    "match. With Collection Progression Max Pop the cap becomes 231 plus the collection bonus "
    "(256 with everything); with Immediate Fixed Max Pop it is 256 at once; with No Population "
    "Increase the stock cap of 115 is unchanged, only the table is larger. The patched game is "
    "named \"... - Modded 256\" and keeps its saves in their own \"Virtual Villagers - The Tree "
    "of Life - Modded 256\" folder, so they never mix with 150-slot saves: a 256 save cannot be "
    "opened by a 150-slot game. Copy an old save into that folder and it loads, then is saved in "
    "the 256 format from then on. Off by default."
)


def main() -> int:
    body = build()
    record = {
        "id": FEATURE_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": "256 Villagers (Experimental)",
        "description": DESCRIPTION,
        "output_tag": "256 Villagers",
        "behavior_changes": [
            "The villager table has 256 slots; the population modes that raise the cap reach 256.",
            "Saves hold up to 256 villagers in a longer save file that only this build reads.",
        ],
        "explicit_non_changes": [
            "No Population Increase keeps the stock cap of 115.",
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
