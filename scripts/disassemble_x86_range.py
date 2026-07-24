"""Disassemble a virtual-address range from a 32-bit PE executable."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from find_x86_immediate import executable_text


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools" / "capstone"))

from capstone import CS_ARCH_X86, CS_MODE_32, Cs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("start", type=lambda value: int(value, 0))
    parser.add_argument("end", type=lambda value: int(value, 0))
    args = parser.parse_args()

    text_va, _, text = executable_text(args.executable.read_bytes())
    start_offset = args.start - text_va
    end_offset = args.end - text_va
    if start_offset < 0 or end_offset > len(text) or start_offset >= end_offset:
        raise ValueError("Requested range is outside .text")
    for instruction in Cs(CS_ARCH_X86, CS_MODE_32).disasm(
        text[start_offset:end_offset], args.start
    ):
        print(f"{instruction.address:08X}  {instruction.mnemonic:8} {instruction.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
