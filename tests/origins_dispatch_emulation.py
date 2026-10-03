"""Run the Origins Tech and Villager Details menus' command dispatch under
emulation, for every row the menu dialog can return.

The reachability analysis (tests/origins_reachability.py) decides by reading
the code which paths are possible. This executes them instead, as a second,
independent witness: each menu is entered right where it takes the dialog's
answer (`cmp eax, -1; je done; mov ebx, eax`), once for every value the
dialog can return and every combination of the environment the dispatch
looks at -- what each helper and game routine answers, whether the tech
balance covers the price, whether the doublers are owned -- and every
instruction that runs is recorded.

What it does not do is run the game. Patcher code is executed, callees
included; a call out of it -- a game routine, an import, a DLL export the
code resolved -- is not: its arguments are popped as its own `ret` would pop
them (an export, stdcall, pops the pushes just before the call), and EAX is
set to the answer chosen for that call. Memory the menu reads (the village object, the
executable's own globals) starts zero-filled, except the fields the run
sets. A run ends when the menu returns, loops back to its dialog, or reads
memory nothing mapped.
"""
from __future__ import annotations

import itertools
import re
import struct

import capstone
import pefile
from unicorn import (
    UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_32, UC_PROT_ALL, Uc, UcError,
)
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

# The menus take the dialog's answer with exactly this sequence.
DISPATCH = re.compile(rb"\x83\xF8\xFF(?:\x0F\x84....|\x74.)\x89\xC3", re.S)

OBJECT = 0x20000000          # the village object [esi+0x0C] / [esi+0x10]
OBJECT_SIZE = 0x04000000
RECORDS = OBJECT + 0x01000000  # what a routine returning a pointer hands back
FRAME = 0x30000000           # the menu's caller-side stack
FRAME_SIZE = 0x00100000
SENTINEL = 0x0BADF00C        # a return address that ends the run
# Every dialog answer that matters: each row, the rows past the end, and
# the far end of the unsigned range (-1 itself is the dialog's Cancel).
ANSWERS = tuple(range(0, 24)) + (0x7FFFFFFF, 0x80000000, 0xFFFFFFFE)
CALL_ANSWERS = (0, 1, 2, RECORDS)   # what each stubbed call returns
CALL_DEPTH = 3                 # calls per run whose answer varies
BALANCES = (0, 0x7FFFFFFF)
OWNED = (0, 0xFFFFFFFF)

# Arguments popped by the imports the menus call (stdcall).
IMPORT_POPS = {
    b"LoadLibraryA": 4, b"LoadLibraryW": 4, b"GetProcAddress": 8,
    b"GetModuleHandleA": 4, b"GetModuleHandleW": 4, b"MessageBoxA": 16,
}


class Image:
    def __init__(self, data: bytes):
        pe = pefile.PE(data=data, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        self.base = pe.OPTIONAL_HEADER.ImageBase
        self.size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        image = bytearray(self.size)
        image[: pe.OPTIONAL_HEADER.SizeOfHeaders] = data[: pe.OPTIONAL_HEADER.SizeOfHeaders]
        for section in pe.sections:
            raw = data[section.PointerToRawData: section.PointerToRawData + section.SizeOfRawData]
            start = section.VirtualAddress
            image[start: start + len(raw)] = raw[: self.size - start]
        self.bytes = bytes(image)
        self.imports: dict[int, int] = {}
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            for symbol in entry.imports:
                if symbol.name in IMPORT_POPS:
                    self.imports[symbol.address] = IMPORT_POPS[symbol.name]
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.md.detail = True
        self._pops: dict[int, int | None] = {}

    def dispatch_points(self, lo: int, hi: int) -> list[int]:
        """The `mov ebx, eax` of each menu in [lo, hi)."""
        found = []
        for match in DISPATCH.finditer(self.bytes, lo - self.base, hi - self.base):
            found.append(self.base + match.end() - 2)
        return found

    def callee_pops(self, target: int) -> int | None:
        """Bytes a routine's `ret` pops, from its first return; None if it
        cannot be found."""
        if target in self._pops:
            return self._pops[target]
        pops = None
        va = target
        for _ in range(4000):
            if not 0 <= va - self.base < self.size - 16:
                break
            insn = next(self.md.disasm(self.bytes[va - self.base: va - self.base + 16], va), None)
            if insn is None:
                break
            if insn.mnemonic == "ret":
                pops = insn.operands[0].imm if insn.operands else 0
                break
            va += insn.size
        self._pops[target] = pops
        return pops


class Machine:
    """One emulator, reused for every run: each run's memory writes are
    undone afterwards, so every run starts from the same image."""

    def __init__(self, image: Image, owned_ranges, balance_fields, owned_fields):
        self.image = image
        self.owned_ranges = tuple(owned_ranges)
        self.balance_fields = balance_fields
        self.owned_fields = owned_fields
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(image.base, image.size, UC_PROT_ALL)
        uc.mem_write(image.base, image.bytes)
        uc.mem_map(OBJECT, OBJECT_SIZE, UC_PROT_ALL)
        uc.mem_map(FRAME, FRAME_SIZE, UC_PROT_ALL)
        uc.mem_map(SENTINEL & ~0xFFF, 0x1000, UC_PROT_ALL)
        # The village object is reached through [esi+0x0C] and [esi+0x10];
        # the later games keep the balance and doubler flags in globals.
        uc.mem_write(OBJECT, struct.pack("<IIIII", 0, 0, 0, OBJECT + 0x1000, OBJECT + 0x1000))
        # The villager records a routine hands back: every byte 1, so each
        # record reads as present, alive, below full health and sick --
        # a village with something for every upgrade to do.
        uc.mem_write(RECORDS, b"" * (OBJECT + OBJECT_SIZE - RECORDS))
        uc.hook_add(UC_HOOK_CODE, self._on_code)
        uc.hook_add(UC_HOOK_MEM_WRITE, self._on_write)
        self.uc = uc
        self.undo: list[tuple[int, bytes]] = []
        self.ran: set[int] = set()
        self.steps: set[tuple[int, int]] = set()   # (from, to) as run
        self.previous = None
        self.calls: set = set()

    def owned(self, va: int) -> bool:
        return any(lo <= va < hi for lo, hi in self.owned_ranges)

    def _field(self, field: int) -> int:
        return field if field >= self.image.base else OBJECT + 0x1000 + field

    def _on_write(self, uc, access, address, size, value, _):
        self.undo.append((address, bytes(uc.mem_read(address, size))))

    def _on_code(self, uc, address, size, _):
        if address == SENTINEL or not self.owned(address):
            uc.emu_stop()
            return
        self.ran.add(address)
        if self.previous is not None:
            self.steps.add((self.previous, address))
        self.previous = address
        insn = next(self.image.md.disasm(bytes(uc.mem_read(address, size)), address), None)
        if insn is None:
            return
        if insn.mnemonic != "call":
            self.pushes = self.pushes + 1 if insn.mnemonic == "push" else 0
            return
        pushed, self.pushes = self.pushes, 0
        op = insn.operands[0]
        if op.type == capstone.x86.X86_OP_IMM:
            target = op.imm & 0xFFFFFFFF
            if target == self.dialog:
                uc.emu_stop()             # back at the dialog: the menu looped
                return
            if self.owned(target):
                # Patcher code is executed, not stubbed: what it does to
                # the registers is part of what decides the dispatch.
                self.calls.add((target, uc.reg_read(UC_X86_REG_EAX), uc.reg_read(UC_X86_REG_EBX)))
                return
            pops = self.image.callee_pops(target)
        elif op.type == capstone.x86.X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
            pops = self.image.imports.get(op.mem.disp & 0xFFFFFFFF)
        elif op.type == capstone.x86.X86_OP_REG:
            # A DLL export the code resolved: stdcall, popping the
            # arguments pushed for it -- the pushes run just before it.
            pops = 4 * pushed
        else:
            pops = None
        if pops is None:
            uc.emu_stop()
            return
        answer = self.answers[self.call_index] if self.call_index < len(self.answers) else 1
        self.call_index += 1
        uc.reg_write(UC_X86_REG_ESP, uc.reg_read(UC_X86_REG_ESP) + pops)
        uc.reg_write(UC_X86_REG_EAX, answer)
        uc.reg_write(UC_X86_REG_EIP, address + size)

    def run(self, start: int, eax: int, ebx: int, answers, balance: int, owned: int,
            dialog: int | None) -> None:
        uc = self.uc
        self.dialog = dialog
        self.answers = answers
        self.call_index = 0
        self.previous = None
        self.pushes = 0
        self.undo = []
        for field in self.balance_fields:
            uc.mem_write(self._field(field), struct.pack("<I", balance))
        for field in self.owned_fields:
            uc.mem_write(self._field(field), struct.pack("<I", owned))
        esp = FRAME + FRAME_SIZE // 2
        uc.mem_write(esp, struct.pack("<I", SENTINEL) * 64)
        uc.reg_write(UC_X86_REG_ESP, esp)
        uc.reg_write(UC_X86_REG_ESI, OBJECT)
        uc.reg_write(UC_X86_REG_EDI, OBJECT + 0x1000)
        uc.reg_write(UC_X86_REG_EBP, OBJECT + 0x1000)
        uc.reg_write(UC_X86_REG_ECX, OBJECT)
        uc.reg_write(UC_X86_REG_EDX, 0)
        uc.reg_write(UC_X86_REG_EAX, eax)
        uc.reg_write(UC_X86_REG_EBX, ebx)
        try:
            uc.emu_start(start, 0, count=20000)
        except UcError:
            pass
        for address, old in reversed(self.undo):
            uc.mem_write(address, old)


def explore(data: bytes, owned_ranges, balance_fields, owned_fields):
    """Run every menu dispatch over the whole grid, then every owned routine
    the runs call, with each (eax, ebx) it was called with, and so on down.

    Each call a run makes answers from `answers` in turn -- every sequence
    of the first CALL_DEPTH answers drawn from CALL_ANSWERS, then 1 -- so a
    path that needs one helper to say no and the next to say yes is run.
    Returns (dispatch points, owned addresses run, {callee: {(eax, ebx)}},
    {(address, next address) as run})."""
    image = Image(data)
    machine = Machine(image, owned_ranges, balance_fields, owned_fields)
    starts = [va for lo, hi in owned_ranges for va in image.dispatch_points(lo, hi)]
    sequences = list(itertools.product(CALL_ANSWERS, repeat=CALL_DEPTH))
    for start in starts:
        # The dialog call just before the dispatch: reaching it again means
        # the menu looped back to ask again.
        dialog = None
        for back in range(5, 40):
            if image.bytes[start - image.base - back] == 0xE8:
                target = (start - back + 5 + struct.unpack_from(
                    "<i", image.bytes, start - image.base - back + 1)[0]) & 0xFFFFFFFF
                if machine.owned(target):
                    dialog = target
                    break
        for answer in ANSWERS:
            for answers in sequences:
                for balance in BALANCES:
                    for owned in OWNED:
                        machine.run(start, answer, 0, answers, balance, owned, dialog)
    done: set = set()
    entered: dict[int, set] = {}
    while machine.calls - done:
        call = min(machine.calls - done)
        done.add(call)
        target, eax, ebx = call
        entered.setdefault(target, set()).add((eax, ebx))
        for answers in sequences:
            for balance in BALANCES:
                for owned in OWNED:
                    machine.run(target, eax, ebx, answers, balance, owned, None)
    return starts, machine.ran, entered, machine.steps
