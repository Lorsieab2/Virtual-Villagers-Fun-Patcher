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

    def call(self, target: int | str) -> None:
        start = self.cursor
        self.emit(b"\xE8\x00\x00\x00\x00")
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
    #
    # BUG FIX (crash on manual drag-pair): the "actor is not category 2"
    # branch used to read [edi+0x348] for the candidate's age. EDI does hold
    # the candidate record pointer earlier in FUN_0043dad0 (set at 0x43db32),
    # but it gets reassigned twice before this splice point is ever reached
    # -- first to the game-state singleton (*(esi+0x3e010), at 0x43dc51),
    # then to a small RNG(3)+5 duration value (5..7, at 0x43dcd8/0x43dcfb) --
    # confirmed via disassembly of the stock function, and Ghidra's own
    # decompile independently confirms that value is a plain int local
    # (iVar4), never a pointer. Reading [edi+0x348] with edi==5..7 dereferences
    # an address in the unmapped low-memory page and crashes essentially every
    # time the dragged/actor villager is the non-carrier participant (roughly
    # half of all manual pairings) -- this is exactly the reported "game
    # crashes when I drop a person on another person" bug.
    #
    # Fix: recompute the candidate record pointer fresh from EBX (the
    # candidate's *index*, iVar3, set once at 0x43db18 and never
    # touched again before this point -- confirmed via the same disassembly)
    # and ESI (the function's own "this", also never reassigned): candidate
    # = esi + ebx*0x3D8, identical to the stock computation at 0x43db23-
    # 0x43db32 that originally produced the now-stale EDI copy.
    asm.seek(0x000)
    asm.emit(bytes.fromhex("83BD5003000002"))
    asm.jcc(0x85, "manual_candidate")  # jne: actor is not category 2
    asm.emit(bytes.fromhex("81BD48030000E8030000"))
    asm.jcc(0x8D, "manual_reject")  # jge: actor/carrier is age 50+
    asm.jmp("manual_accept")
    asm.label("manual_candidate")
    asm.emit(bytes.fromhex("8BC3"))  # mov eax, ebx (candidate index, still live)
    asm.emit(bytes.fromhex("69C0D8030000"))  # imul eax, eax, 0x3D8
    asm.emit(bytes.fromhex("03C6"))  # add eax, esi -> eax = candidate record
    asm.emit(bytes.fromhex("81B848030000E8030000"))  # cmp dword ptr [eax+0x348], 0x3E8
    asm.jcc(0x8D, "manual_reject")  # jge: candidate/carrier is age 50+
    # fall through to the shared accept path
    #
    # STACK-BALANCE FIX (crash confirmed from a full-heap dump: FUN_0043DAD0
    # `ret`ed into the villager-index arg 0x22). Stock code from 0x43DD03 is:
    #     0x43DD03  cmp [ebp+0x350], 2
    #     0x43DD0A  push 0x64            <- argument for the call at 0x43DD0E/0x43DD5E
    #     0x43DD0C  jne  0x43DD5E
    # Every stock path reaches 0x43DD5E only *after* that `push 0x64`, and the
    # code there does `call 0x402F10; add esp,4`, cleaning it. The old cave's
    # candidate accept path jumped straight to 0x43DD5E, so the `push 0x64` was
    # skipped but the `add esp,4` still ran -> esp 4 bytes too high for the rest
    # of FUN_0043DAD0 -> its later `ret` popped the wrong slot and jumped to the
    # index arg (0x22). Both accept paths now re-run the stock compare and rejoin
    # at 0x43DD0A, so the stock `push 0x64; jne 0x43DD5E` supplies both the flags
    # (correct accept branch) and the stack push (balanced) exactly as stock.
    asm.label("manual_accept")
    asm.emit(bytes.fromhex("83BD5003000002"))  # cmp dword ptr [ebp+0x350], 2
    asm.jmp(0x43DD0A)  # stock: push 0x64; jne 0x43DD5E
    asm.label("manual_reject")
    # SECOND HALF OF THE SAME BUG (crash at 0x43DDE1, confirmed from a live
    # Windows Application-log 0xC0000005 record with fault offset 0x3DDE1).
    # The stock reject block at 0x43DD9E reads the *candidate record* out of
    # EDI six times (0x43DDE1, 0x43DDF4, 0x43DE06, 0x43DE1A, 0x43DE2E) --
    # which is correct for the stock code paths that reach it, since they all
    # branch there from the eligibility checks near the top of the function,
    # while EDI still holds the candidate pointer set at 0x43DB32.
    #
    # This hook is spliced much later (0x43DD03), and by that point EDI has
    # been reassigned to the RNG(3)+5 duration value -- the exact same stale-
    # EDI fact that caused the first crash at page offset 0x22. Jumping
    # straight to 0x43DD9E therefore crashed on the first of those six reads.
    # Fixing only the age-compare left this second dereference live, which is
    # why the crash "came back" at a new address after the first fix.
    #
    # EBX (candidate index), ESI (this), and EBP (actor record) are all still
    # valid here, so rebuild EDI exactly the way stock does at 0x43DB23-
    # 0x43DB32 before entering the block. Only the reject path restores EDI:
    # both accept paths (0x43DD0A / 0x43DD5E) fall into the conception
    # dispatch, which passes EDI to FUN_0043BBC0 *as* the duration and must
    # keep the RNG value untouched.
    asm.emit(bytes.fromhex("8BFB"))  # mov edi, ebx
    asm.emit(bytes.fromhex("69FFD8030000"))  # imul edi, edi, 0x3D8
    asm.emit(bytes.fromhex("01F7"))  # add edi, esi -> edi = candidate record
    asm.jmp(0x43DD9E)

    # The two ordinary action-9 writer-reaching scans retain the stock lower
    # age bound and add only the candidate upper bound.
    asm.seek(0x080)
    asm.emit(bytes.fromhex("813868010000"))
    asm.jcc(0x8C, "action1_reject")
    asm.emit(bytes.fromhex("8138E8030000"))
    asm.jcc(0x8D, "action1_reject")
    asm.jmp(0x446EA2)
    asm.label("action1_reject")
    asm.jmp(0x447036)

    asm.seek(0x0C0)
    asm.emit(bytes.fromhex("813968010000"))
    asm.jcc(0x8C, "action2_reject")
    asm.emit(bytes.fromhex("8139E8030000"))
    asm.jcc(0x8D, "action2_reject")
    asm.jmp(0x447090)
    asm.label("action2_reject")
    asm.jmp(0x44723D)

    # Planner scan: preserve the initiator's stock >=360 check while requiring
    # the scanned candidate to remain in the ordinary 360..999 range.
    asm.seek(0x100)
    asm.emit(bytes.fromhex("8178F468010000"))
    asm.jcc(0x8C, "planner_reject")
    asm.emit(bytes.fromhex("8178F4E8030000"))
    asm.jcc(0x8D, "planner_reject")
    asm.jmp(0x4477FF)
    asm.label("planner_reject")
    asm.jmp(0x447829)

    # VV1's chooser is the one early-game implementation whose native tail
    # predates the VV4 score floor and preference fallback.  Keep its native
    # skill/category mapping, but route the final score decision through the
    # owned page so it matches the VV4/VV2/VV3 chooser contract: score > 5,
    # then the 25% non-preference fallback for the embracing category (2).
    asm.seek(0x140)
    asm.jcc(0x8E, "chooser_reject")  # signed <= after cmp esi, 5
    asm.emit(bytes.fromhex("83C628"))  # add esi, 40
    asm.emit(bytes.fromhex("6A64"))
    asm.call(0x402F10)
    asm.emit(bytes.fromhex("83C404"))
    asm.emit(bytes.fromhex("3BC6"))  # cmp eax, esi
    asm.jcc(0x8D, "chooser_reject")  # signed >= rejects the action
    asm.emit(bytes.fromhex("83FD02"))  # cmp ebp, 2
    asm.jcc(0x85, "chooser_return")  # non-embracing category returns
    asm.emit(bytes.fromhex("817FD003000002"))  # pref != 2 is not guaranteed
    asm.jcc(0x84, "chooser_return")  # checked embracing preference returns
    asm.emit(bytes.fromhex("6A64"))
    asm.call(0x402F10)
    asm.emit(bytes.fromhex("83C404"))
    asm.emit(bytes.fromhex("83F84B"))  # cmp eax, 75
    asm.jcc(0x8D, "chooser_return")  # 25% fallback
    asm.label("chooser_reject")
    asm.emit(bytes.fromhex("B901000000"))  # ECX=1 -> original zero result
    asm.jmp(0x439C9D)
    asm.label("chooser_return")
    asm.emit(bytes.fromhex("33C9"))  # ECX=0 -> original EBP result
    asm.jmp(0x439C9D)

    page = asm.finish()
    details = {
        "page_sha256": hashlib.sha256(page).hexdigest().upper(),
        "page_virtual_address": hex(PAGE_VA),
        "hooks": {
            "manual": {"raw": "0x3DD03", "page_offset": "0x0", "length": 7},
            "action_9_scan_1": {"raw": "0x46E96", "page_offset": "0x80", "length": 6},
            "action_9_scan_2": {"raw": "0x47084", "page_offset": "0xC0", "length": 6},
            "planner": {"raw": "0x477FA", "page_offset": "0x100", "length": 5},
            "chooser_score_floor": {"raw": "0x39C83", "page_offset": "0x140", "length": 6},
        },
    }
    return page, details


if __name__ == "__main__":
    page, details = build_page()
    print(details)
    print(page.hex().upper())
