"""Reachability of patcher-owned bytes in a rendered executable.

Used by the "no unreachable Origins code" tests. Given a rendered image and
the VA ranges a feature owns, it finds every byte of those ranges that live
code can reach, so a test can require that nothing else is left there.

* Roots: every rel32 jmp/call/jcc target and every 32-bit value found
  anywhere OUTSIDE the owned ranges that lands inside them -- the hooks,
  pointers and tables through which the game enters patcher code. Being
  conservative (a coincidental value counts as a root) can only make more
  bytes live, never fewer.
* From the roots: recursive disassembly following fall-through, direct
  branch and call targets, jump/call tables (`[disp + reg*4]`, read until an
  entry leaves the owned ranges), `push imm; ret`, `mov reg, imm ...
  jmp/call reg`, and any immediate into a code range (a routine address
  handed to another routine).
* Any other immediate or displacement made by REACHED code is a data
  reference: it marks the C string it points at, the whole known data object
  it falls in (price tables and the like), or four bytes.

Only references made by reached code count, so code reachable solely from
other dead code is reported dead too.
"""
from __future__ import annotations

import struct

import capstone
from capstone import x86 as X
import pefile

TERMINATORS = {"ret", "retf", "jmp", "int3", "ud2", "hlt"}


def _load(data: bytes):
    pe = pefile.PE(data=data, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    size = pe.OPTIONAL_HEADER.SizeOfImage
    image = bytearray(size)
    image[: pe.OPTIONAL_HEADER.SizeOfHeaders] = data[: pe.OPTIONAL_HEADER.SizeOfHeaders]
    executable = []
    for section in pe.sections:
        raw = data[section.PointerToRawData: section.PointerToRawData + section.SizeOfRawData]
        image[section.VirtualAddress: section.VirtualAddress + len(raw)] = raw[: size - section.VirtualAddress]
        if section.Characteristics & 0x20000000:
            executable.append(
                (section.VirtualAddress, section.VirtualAddress + max(section.Misc_VirtualSize, len(raw)))
            )
    return image, base, size, executable


def reach(data: bytes, regions, data_objects=None, code_ranges=None):
    """Return (image, base, live VAs) for the owned `regions` of `data`.

    regions:      [(lo, hi)] owned VA ranges.
    data_objects: {va: length} data objects (tables) inside the regions.
    code_ranges:  [(lo, hi)] ranges where an immediate pointing in is code.
    """
    data_objects = dict(data_objects or {})
    code_ranges = list(code_ranges or [])

    def in_object(v):
        return next(((o, n) for o, n in data_objects.items() if o <= v < o + n), None)

    def in_code(v):
        return any(lo <= v < hi for lo, hi in code_ranges) and in_object(v) is None

    image, base, size, executable = _load(data)
    inside = bytearray(size)
    for lo, hi in regions:
        inside[lo - base: hi - base] = b"\1" * (hi - lo)

    def owned(va):
        return 0 <= va - base < size and inside[va - base]

    work: list[int] = []
    data_refs: set[int] = set()
    view = memoryview(image)
    for shift in range(4):
        words = struct.iter_unpack("<I", view[shift: shift + (size - shift) // 4 * 4])
        for index, (value,) in enumerate(words):
            if not inside[shift + index * 4] and owned(value):
                data_refs.add(value)
                if in_code(value):
                    work.append(value)
    for lo, hi in executable:
        for rva in range(lo, min(hi, size - 6)):
            if inside[rva]:
                continue
            op = image[rva]
            if op in (0xE8, 0xE9):
                target = (base + rva + 5 + struct.unpack_from("<i", image, rva + 1)[0]) & 0xFFFFFFFF
            elif op == 0x0F and 0x80 <= image[rva + 1] <= 0x8F:
                target = (base + rva + 6 + struct.unpack_from("<i", image, rva + 2)[0]) & 0xFFFFFFFF
            else:
                continue
            if owned(target):
                work.append(target)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True

    def decode(va):
        return next(md.disasm(bytes(image[va - base: va - base + 16]), va), None)

    live: set[int] = set()
    code_seen: set[int] = set()
    while work:
        va = work.pop()
        register_values: dict[int, int] = {}
        while owned(va) and va not in code_seen:
            insn = decode(va)
            if insn is None:
                break
            code_seen.add(va)
            live.update(range(va, va + insn.size))
            operands = insn.operands
            branch = insn.group(capstone.CS_GRP_JUMP) or insn.group(capstone.CS_GRP_CALL)
            for op in operands:
                if op.type == X.X86_OP_IMM:
                    value = op.imm & 0xFFFFFFFF
                    if not owned(value):
                        continue
                    if branch or in_code(value):
                        work.append(value)
                    elif insn.mnemonic == "push":
                        following = decode(va + insn.size)
                        if following is not None and following.mnemonic == "ret":
                            work.append(value)
                        else:
                            data_refs.add(value)
                    else:
                        if insn.mnemonic == "mov" and operands[0].type == X.X86_OP_REG:
                            register_values[operands[0].reg] = value
                        data_refs.add(value)
                elif op.type == X.X86_OP_MEM:
                    value = op.mem.disp & 0xFFFFFFFF
                    if not owned(value):
                        continue
                    if branch and op.mem.index != 0:
                        entry = value
                        while owned(entry):
                            target = struct.unpack_from("<I", image, entry - base)[0]
                            if not owned(target):
                                break
                            live.update(range(entry, entry + 4))
                            work.append(target)
                            entry += 4
                    else:
                        data_refs.add(value)
                elif op.type == X.X86_OP_REG and branch and op.reg in register_values:
                    work.append(register_values[op.reg])
            if insn.mnemonic in TERMINATORS:
                break
            va += insn.size
    for ref in data_refs:
        obj = in_object(ref)
        if obj:
            live.update(range(obj[0], obj[0] + obj[1]))
            continue
        if ref in code_seen:
            continue
        cursor = ref
        while owned(cursor) and image[cursor - base] and cursor - ref < 512:
            live.add(cursor)
            cursor += 1
        live.update(range(ref, ref + 4))
    return image, base, live


def unreached(image, base, live, lo, hi):
    """Non-zero bytes of [lo, hi) that nothing reaches, as merged runs."""
    runs: list[list[int]] = []
    for va in range(lo, hi):
        if image[va - base] and va not in live:
            if runs and va - runs[-1][1] <= 1:
                runs[-1][1] = va + 1
            else:
                runs.append([va, va + 1])
    return [f"{a:#x}-{b:#x}" for a, b in runs]


def owned_caves(applied, owners):
    """Merged VA ranges of the applied rows `owners` wrote into zero caves.

    Rows written over stock code (a non-zero preimage) are hooks, entered by
    the game's own fall-through rather than by any reference, so they are not
    caves and are left out.
    """
    rows = []
    for row in applied:
        if row.get("owner") not in owners or not row.get("virtual_address"):
            continue
        after = bytes.fromhex(row.get("after", ""))
        before = bytes.fromhex(row.get("before", "") or "")
        if len(after) < 8 or any(before):
            continue
        va = int(row["virtual_address"], 0)
        rows.append([va, va + len(after)])
    rows.sort()
    merged: list[list[int]] = []
    for lo, hi in rows:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [tuple(r) for r in merged]
