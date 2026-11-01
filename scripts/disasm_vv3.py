"""Research helper for src/vv_assets_vv3.py: disassemble The Secret City's stock exe.

    python scripts/disasm_vv3.py fn 0x42E750 [count]      disassemble from an address
    python scripts/disasm_vv3.py calls 0x42E750           every call to an address, with the 6 instructions before
    python scripts/disasm_vv3.py refs 0x482954            every instruction whose operand holds the value
"""
from __future__ import annotations

import sys
from pathlib import Path

import capstone
import pefile

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"

_pe = pefile.PE(str(EXE))
IMAGE = _pe.get_memory_mapped_image()
BASE = _pe.OPTIONAL_HEADER.ImageBase
TEXT = next(s for s in _pe.sections if s.Name.startswith(b".text"))
T0 = BASE + TEXT.VirtualAddress
T1 = T0 + TEXT.Misc_VirtualSize
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
_ALL = None


def code(start: int, count: int = 80):
    return list(MD.disasm(IMAGE[start - BASE:start - BASE + count * 16], start))[:count]


def all_insns():
    """A linear sweep of .text (good enough for finding calls)."""
    global _ALL
    if _ALL is None:
        out = []
        pos = T0
        while pos < T1:
            got = False
            for ins in MD.disasm(IMAGE[pos - BASE:min(T1, pos + 0x4000) - BASE], pos):
                out.append(ins)
                pos = ins.address + ins.size
                got = True
            if not got or (out and pos == out[-1].address + out[-1].size and pos < T1 and
                           not list(MD.disasm(IMAGE[pos - BASE:pos - BASE + 16], pos))):
                pos += 1
        _ALL = out
    return _ALL


def calls_to(target: int):
    insns = all_insns()
    for i, ins in enumerate(insns):
        if ins.mnemonic in ("call", "jmp") and ins.op_str == hex(target):
            yield i, insns


RESOURCE_GETTERS = {0x42E750: "atlas", 0x42E8A0: "atlas*", 0x42E920: "strip", 0x42EA70: "strip*",
                    0x42EA80: "any", 0x42EB80: "any*", 0x42EB90: "b90", 0x42ECA0: "ca0", 0x42E8B0: "release"}


def pushed_before(insns, i, back=12):
    """The immediates pushed in the instructions before insns[i] (nearest first)."""
    out = []
    for ins in reversed(insns[max(0, i - back):i]):
        if ins.mnemonic == "push" and ins.op_str.startswith("0x") or ins.mnemonic == "push" and ins.op_str.isdigit():
            out.append(int(ins.op_str, 0))
        elif ins.mnemonic == "push":
            out.append(ins.op_str)
        if ins.mnemonic in ("call", "ret") or ins.mnemonic.startswith("j"):
            break
    return out


def resource_uses():
    insns = all_insns()
    for i, ins in enumerate(insns):
        if ins.mnemonic in ("call", "jmp") and ins.op_str.startswith("0x"):
            t = int(ins.op_str, 16)
            if t in RESOURCE_GETTERS:
                yield ins.address, RESOURCE_GETTERS[t], pushed_before(insns, i)


def main() -> None:
    what = sys.argv[1]
    if what == "ctors":
        targets = [int(a, 16) for a in sys.argv[2:]] or [0x40AD80, 0x401150, 0x40AF10, 0x40AF90, 0x40B3D0]
        insns = all_insns()
        for i, ins in enumerate(insns):
            if ins.mnemonic in ("call", "jmp") and ins.op_str.startswith("0x") and int(ins.op_str, 16) in targets:
                pushes = pushed_before(insns, i, 16)
                named = []
                for p in pushes[:4]:
                    if isinstance(p, int) and BASE <= p < BASE + len(IMAGE):
                        named.append(IMAGE[p - BASE:p - BASE + 40].split(b"\0", 1)[0].decode("latin-1"))
                    else:
                        named.append(p)
                print(f"{ins.address:#x} -> {ins.op_str} {named}")
        return
    if what == "dword":                     # where a dword value sits in the image (vtables ...)
        import struct as st
        v = st.pack("<I", int(sys.argv[2], 16))
        at = IMAGE.find(v)
        while at >= 0:
            print(hex(BASE + at), [hex(x) for x in st.unpack_from("<12I", IMAGE, (at & ~3) - 16)])
            at = IMAGE.find(v, at + 1)
        return
    if what == "vt":                        # a vtable's entries
        import struct as st
        a = int(sys.argv[2], 16)
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 24
        for k, x in enumerate(st.unpack_from(f"<{n}I", IMAGE, a - BASE)):
            print(k, hex(k * 4), hex(x))
        return
    if what == "uses":
        for a, kind, pushes in resource_uses():
            print(f"{a:#x} {kind} {pushes[:3]}")
        return
    addr = int(sys.argv[2], 16)
    if what == "fn":
        for ins in code(addr, int(sys.argv[3]) if len(sys.argv) > 3 else 80):
            print(f"{ins.address:#x}: {ins.mnemonic} {ins.op_str}")
    elif what == "calls":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 6
        for i, insns in calls_to(addr):
            print("----")
            for ins in insns[max(0, i - n):i + 1]:
                print(f"{ins.address:#x}: {ins.mnemonic} {ins.op_str}")
    elif what == "refs":
        h = hex(addr)
        for ins in all_insns():
            if h in ins.op_str:
                print(f"{ins.address:#x}: {ins.mnemonic} {ins.op_str}")


if __name__ == "__main__":
    main()
