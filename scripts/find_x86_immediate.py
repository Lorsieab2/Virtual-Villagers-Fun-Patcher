"""Print x86 instructions that reference an immediate value, with context."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools" / "capstone"))

from capstone import CS_ARCH_X86, CS_MODE_32, CS_OP_IMM, CS_OP_MEM, Cs  # noqa: E402


def executable_text(data: bytes) -> tuple[int, int, bytes]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    section_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    image_base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    sections = pe + 24 + optional_size
    for index in range(section_count):
        header = sections + index * 40
        name = data[header : header + 8].rstrip(b"\0")
        virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<III", data, header + 12
        )
        if name == b".text":
            return image_base + virtual_address, raw_pointer, data[
                raw_pointer : raw_pointer + raw_size
            ]
    raise ValueError("Executable has no .text section")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("value", type=lambda value: int(value, 0))
    parser.add_argument("--context", type=int, default=5)
    parser.add_argument(
        "--memory-displacement",
        action="store_true",
        help="match memory-operand displacement instead of an immediate operand",
    )
    args = parser.parse_args()

    text_va, text_offset, text = executable_text(args.executable.read_bytes())
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    decoder.detail = True
    instructions = list(decoder.disasm(text, text_va))
    for index, instruction in enumerate(instructions):
        if args.memory_displacement:
            matches = any(
                operand.type == CS_OP_MEM and operand.mem.disp == args.value
                for operand in instruction.operands
            )
        else:
            matches = any(
                operand.type == CS_OP_IMM and operand.imm == args.value
                for operand in instruction.operands
            )
        if not matches:
            continue
        file_offset = instruction.address - text_va + text_offset
        print(
            f"\n--- VA 0x{instruction.address:X}; file 0x{file_offset:X}; "
            f"{instruction.mnemonic} {instruction.op_str}"
        )
        start = max(0, index - args.context)
        for nearby in instructions[start : index + args.context + 1]:
            print(f"{nearby.address:08X}  {nearby.mnemonic:8} {nearby.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
