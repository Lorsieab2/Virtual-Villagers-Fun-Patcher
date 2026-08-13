"""Build the immutable VV1 Birth Control hook page."""
from __future__ import annotations

import hashlib
import struct

PAGE_SIZE = 0x1000
PAGE_VA = 0x490000


class _Assembler:
    def __init__(self) -> None:
        self.data = bytearray(PAGE_SIZE)
        self.cursor = 0
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[int, int, int | str]] = []

    def seek(self, offset: int) -> None:
        if not 0 <= offset < PAGE_SIZE:
            raise ValueError(f"page offset out of range: 0x{offset:X}")
        self.cursor = offset

    def emit(self, payload: bytes) -> None:
        end = self.cursor + len(payload)
        if end > PAGE_SIZE:
            raise ValueError("VV1 Birth Control page overflow")
        self.data[self.cursor:end] = payload
        self.cursor = end

    def label(self, name: str) -> None:
        self.labels[name] = self.cursor

    def jmp(self, target: int | str) -> None:
        start = self.cursor
        self.emit(b"\xE9\x00\x00\x00\x00")
        self.fixups.append((start + 1, start + 5, target))

    def jcc(self, opcode: int, target: int | str) -> None:
        start = self.cursor
        self.emit(bytes((0x0F, opcode, 0, 0, 0, 0)))
        self.fixups.append((start + 2, start + 6, target))

    def finish(self) -> bytes:
        for immediate_start, instruction_end, target in self.fixups:
            if isinstance(target, str):
                if target not in self.labels:
                    raise ValueError(f"unresolved label: {target}")
                target_va = PAGE_VA + self.labels[target]
            else:
                target_va = target
            instruction_end_va = PAGE_VA + instruction_end
            struct.pack_into(
                "<i",
                self.data,
                immediate_start,
                target_va - instruction_end_va,
            )
        return bytes(self.data)


def build_page() -> tuple[bytes, dict[str, object]]:
    asm = _Assembler()

    # VV1 manual pairing: only a category-2 carrier at internal age >=1000
    # is rejected.  The male participant keeps the stock no-upper-bound path.
    asm.seek(0x000)
    asm.emit(bytes.fromhex("83BD5003000002"))
    asm.jcc(0x85, "manual_candidate")  # jne: actor is not category 2
    asm.emit(bytes.fromhex("81BD48030000E8030000"))
    asm.jcc(0x8D, "manual_reject")  # jge: actor/carrier is age 50+
    asm.jmp(0x43DD0A)
    asm.label("manual_candidate")
    asm.emit(bytes.fromhex("81BF48030000E8030000"))
    asm.jcc(0x8D, "manual_reject")  # jge: candidate/carrier is age 50+
    asm.jmp(0x43DD5E)
    asm.label("manual_reject")
    asm.jmp(0x43DD9E)

    # The two ordinary action-9 writer-reaching scans retain the stock lower
    # age bound and add only the candidate upper bound.
    asm.seek(0x040)
    asm.emit(bytes.fromhex("813868010000"))
    asm.jcc(0x8C, "action1_reject")
    asm.emit(bytes.fromhex("8138E8030000"))
    asm.jcc(0x8D, "action1_reject")
    asm.jmp(0x446EA2)
    asm.label("action1_reject")
    asm.jmp(0x447036)

    asm.seek(0x080)
    asm.emit(bytes.fromhex("813968010000"))
    asm.jcc(0x8C, "action2_reject")
    asm.emit(bytes.fromhex("8139E8030000"))
    asm.jcc(0x8D, "action2_reject")
    asm.jmp(0x447090)
    asm.label("action2_reject")
    asm.jmp(0x44723D)

    # Planner scan: preserve the initiator's stock >=360 check while requiring
    # the scanned candidate to remain in the ordinary 360..999 range.
    asm.seek(0x0C0)
    asm.emit(bytes.fromhex("8178F468010000"))
    asm.jcc(0x8C, "planner_reject")
    asm.emit(bytes.fromhex("8178F4E8030000"))
    asm.jcc(0x8D, "planner_reject")
    asm.jmp(0x4477FF)
    asm.label("planner_reject")
    asm.jmp(0x447829)

    page = asm.finish()
    details = {
        "page_sha256": hashlib.sha256(page).hexdigest().upper(),
        "page_virtual_address": hex(PAGE_VA),
        "hooks": {
            "manual": {"raw": "0x3DD03", "page_offset": "0x0", "length": 7},
            "action_9_scan_1": {"raw": "0x46E96", "page_offset": "0x40", "length": 6},
            "action_9_scan_2": {"raw": "0x47084", "page_offset": "0x80", "length": 6},
            "planner": {"raw": "0x477FA", "page_offset": "0xC0", "length": 5},
        },
    }
    return page, details


if __name__ == "__main__":
    page, details = build_page()
    print(details)
    print(page.hex().upper())
