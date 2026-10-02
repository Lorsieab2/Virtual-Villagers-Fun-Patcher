"""A small x86 emulator for the Story / Cheat Upgrades tests.

Maps a rendered game executable and "VVFP Story Upgrades.test.dll" into one
unicorn address space, the way the game process holds them, and lets a test
call the DLL's exports and run the executable's own code.

* The DLL's imports are bound to stubs: the memory APIs its installer uses
  (VirtualQuery, VirtualProtect, FlushInstructionCache, GetCurrentProcess)
  answer from the emulated memory; GetTickCount and MessageBoxA are scripted;
  anything else stops the run with an error, so a test can never pass through
  an API it did not expect.
* Game routines a test does not want to run (the random generator, a clock)
  are replaced by Python stubs registered with `stub`.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Callable

import pefile
from unicorn import (
    UC_ARCH_X86,
    UC_HOOK_CODE,
    UC_MODE_32,
    UC_PROT_ALL,
    Uc,
)
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EDI,
    UC_X86_REG_EDX,
    UC_X86_REG_EFLAGS,
    UC_X86_REG_EIP,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

STACK_TOP = 0x0FF00000
STACK_SIZE = 0x00100000
API_STUBS = 0x0E000000
HEAP = 0x20000000
HEAP_SIZE = 0x04000000
RETURN = 0x0D000000       # a `hlt`-free landing address the runs stop at

REGS = {
    "eax": UC_X86_REG_EAX, "ebx": UC_X86_REG_EBX, "ecx": UC_X86_REG_ECX,
    "edx": UC_X86_REG_EDX, "esi": UC_X86_REG_ESI, "edi": UC_X86_REG_EDI,
    "ebp": UC_X86_REG_EBP, "esp": UC_X86_REG_ESP, "eip": UC_X86_REG_EIP,
    "eflags": UC_X86_REG_EFLAGS,
}


class EmulationError(AssertionError):
    pass


def _page(n: int) -> int:
    return (n + 0xFFF) & ~0xFFF


class Process:
    def __init__(self, exe: bytes, dll: Path | None = None):
        self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        self.messages: list[str] = []
        self.message_answer = 1           # IDOK
        self.tick = 0
        self.stubs: dict[int, Callable[["Process"], tuple[int, int]]] = {}
        self.calls: list[tuple[int, list[int]]] = []
        # A test can answer an API itself: name -> fn(proc) -> (eax, popped).
        self.api_handlers: dict[str, Callable[["Process"], tuple[int, int]]] = {}
        self.api_calls: list[str] = []
        self.exe_path = b"C:\\Games\\Village\\Game.exe"
        self.loaded = []
        self._exe_pe = pefile.PE(data=exe)
        self._map_pe(self._exe_pe)
        self.mu.mem_map(STACK_TOP - STACK_SIZE, STACK_SIZE)
        self.mu.mem_map(HEAP, HEAP_SIZE)
        self.mu.mem_map(RETURN, 0x1000)
        self.mu.mem_write(RETURN, b"\xC3" * 0x10)
        # FS has base 0 here: the games' SEH prologues (`mov eax, fs:[0]`)
        # read and write page 0, which stands in for the thread's TIB.
        self.mu.mem_map(0, 0x1000)
        self._heap_next = HEAP
        self.exports: dict[str, int] = {}
        if dll is not None:
            self._load_dll(dll)
        self.mu.hook_add(UC_HOOK_CODE, self._on_code)

    # ---- mapping -------------------------------------------------------
    def _map_pe(self, pe: pefile.PE) -> None:
        base = pe.OPTIONAL_HEADER.ImageBase
        size = _page(pe.OPTIONAL_HEADER.SizeOfImage)
        self.mu.mem_map(base, size, UC_PROT_ALL)
        self.mu.mem_write(base, pe.get_memory_mapped_image()[:size])
        self.image_base = base

    def _load_dll(self, path: Path) -> None:
        pe = pefile.PE(str(path))
        base = pe.OPTIONAL_HEADER.ImageBase
        size = _page(pe.OPTIONAL_HEADER.SizeOfImage)
        self.mu.mem_map(base, size, UC_PROT_ALL)
        self.mu.mem_write(base, pe.get_memory_mapped_image()[:size])
        self.dll_base = base
        self.dll_size = size
        self.mu.mem_map(API_STUBS, 0x10000)
        self.api_names: dict[int, str] = {}
        slot = 0
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                stub = API_STUBS + slot * 16
                slot += 1
                self.mu.mem_write(stub, b"\xC3")
                self.api_names[stub] = imp.name.decode()
                self.mu.mem_write(imp.address, struct.pack("<I", stub))
        # The game's own imports too, so game code a test runs that calls
        # one (a hook's GetModuleHandleA) reaches a stub, never garbage.
        for entry in getattr(self._exe_pe, "DIRECTORY_ENTRY_IMPORT", []):
            for imp in entry.imports:
                if not imp.name:
                    continue
                stub = API_STUBS + slot * 16
                slot += 1
                self.mu.mem_write(stub, b"\xC3")
                self.api_names[stub] = imp.name.decode()
                self.mu.mem_write(imp.address, struct.pack("<I", stub))
        for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if symbol.name:
                self.exports[symbol.name.decode()] = base + symbol.address

    # ---- memory helpers ------------------------------------------------
    def read(self, va: int, n: int) -> bytes:
        return bytes(self.mu.mem_read(va, n))

    def write(self, va: int, data: bytes) -> None:
        self.mu.mem_write(va, data)

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.read(va, 4))[0]

    def put32(self, va: int, value: int) -> None:
        self.write(va, struct.pack("<I", value & 0xFFFFFFFF))

    def alloc(self, n: int) -> int:
        at = self._heap_next
        self._heap_next = _page(at + n + 0x10)
        self.write(at, bytes(n))
        return at

    def reg(self, name: str) -> int:
        return self.mu.reg_read(REGS[name])

    def set_reg(self, name: str, value: int) -> None:
        self.mu.reg_write(REGS[name], value & 0xFFFFFFFF)

    def mapped(self, va: int, n: int) -> bool:
        for begin, end, _ in self.mu.mem_regions():
            if begin <= va and va + n - 1 <= end:
                return True
        return False

    # ---- stubs ---------------------------------------------------------
    def stub(self, va: int, fn: Callable[["Process"], tuple[int, int]]) -> None:
        """Replace the routine at `va`: fn returns (eax, bytes of arguments
        the callee pops -- 0 for cdecl)."""
        self.stubs[va] = fn

    def arg(self, i: int) -> int:
        """Argument i (0-based) of the routine just entered."""
        return self.u32(self.reg("esp") + 4 + 4 * i)

    def _return(self, value: int, pop: int) -> None:
        esp = self.reg("esp")
        ret = self.u32(esp)
        self.set_reg("eax", value)
        self.set_reg("esp", esp + 4 + pop)
        self.set_reg("eip", ret)

    def _on_code(self, mu, address, size, user_data):
        if address in self.stubs:
            value, pop = self.stubs[address](self)
            self._return(value, pop)
            return
        name = getattr(self, "api_names", {}).get(address)
        if name is None:
            return
        self.api_calls.append(name)
        if name in self.api_handlers:
            value, pop = self.api_handlers[name](self)
            self._return(value, pop)
            return
        handler = getattr(self, "_api_" + name, None)
        if handler is None:
            mu.emu_stop()
            raise EmulationError(f"unexpected API call: {name}")
        value, pop = handler()
        self._return(value, pop)

    # The APIs the installer and the probes reach.
    def _api_VirtualQuery(self):
        address, buffer, length = self.arg(0), self.arg(1), self.arg(2)
        region = None
        for begin, end, _ in self.mu.mem_regions():
            if begin <= address <= end:
                region = (begin, end)
        if region is None:
            return 0, 12
        info = struct.pack("<7I", address & ~0xFFF, region[0], 0x40,
                           region[1] + 1 - (address & ~0xFFF), 0x1000, 0x40, 0x1000000)
        self.write(buffer, info[:length])
        return min(length, 28), 12

    def _api_VirtualProtect(self):
        self.put32(self.arg(3), 0x20)
        return 1, 16

    def _api_FlushInstructionCache(self):
        return 1, 12

    def _api_GetCurrentProcess(self):
        return 0xFFFFFFFF, 0

    def _api_GetTickCount(self):
        return self.tick, 0

    def _api_MessageBoxA(self):
        self.messages.append(self.cstring(self.arg(1)))
        return self.message_answer, 16

    # The companion resolves the game's own folder and the optional
    # companions beside it; by default nothing else is shipped.
    def _api_GetModuleFileNameA(self):
        buffer, size = self.arg(1), self.arg(2)
        path = self.exe_path[: size - 1]
        self.write(buffer, path + b"\0")
        return len(path), 12

    def _api_LoadLibraryA(self):
        self.loaded.append(self.cstring(self.arg(0)))
        return 0, 4

    def _api_GetLastError(self):
        return 2, 0                     # ERROR_FILE_NOT_FOUND

    # The user32/kernel32 string helpers the companion formats text with.
    def _api_wsprintfA(self):
        out, fmt = self.arg(0), self.cstring(self.arg(1))
        index = 2
        text = ""
        i = 0
        while i < len(fmt):
            c = fmt[i]
            if c != "%":
                text += c
                i += 1
                continue
            spec = fmt[i + 1]
            i += 2
            if spec == "%":
                text += "%"
                continue
            value = self.arg(index)
            index += 1
            if spec in "di":
                text += str(value - (1 << 32) if value & 0x80000000 else value)
            elif spec == "u":
                text += str(value)
            elif spec == "s":
                text += self.cstring(value)
            elif spec == "c":
                text += chr(value & 0xFF)
            else:
                raise EmulationError(f"wsprintfA: unsupported %{spec}")
        raw = text.encode("latin-1")
        self.write(out, raw + b"\0")
        return len(raw), 0

    def _api_lstrcpynA(self):
        out, source, size = self.arg(0), self.arg(1), self.arg(2)
        raw = self.cstring(source).encode("latin-1")[: max(size - 1, 0)]
        if size > 0:
            self.write(out, raw + b"\0")
        return out, 12

    def _api_lstrcpyA(self):
        self.write(self.arg(0), self.cstring(self.arg(1)).encode("latin-1") + b"\0")
        return self.arg(0), 8

    def _api_lstrcatA(self):
        joined = self.cstring(self.arg(0)) + self.cstring(self.arg(1))
        self.write(self.arg(0), joined.encode("latin-1") + b"\0")
        return self.arg(0), 8

    def _api_lstrlenA(self):
        return len(self.cstring(self.arg(0))), 4

    def _api_lstrcmpiA(self):
        a, b = self.cstring(self.arg(0)).lower(), self.cstring(self.arg(1)).lower()
        return (0 if a == b else (1 if a > b else 0xFFFFFFFF)), 8

    def _api_lstrcmpA(self):
        a, b = self.cstring(self.arg(0)), self.cstring(self.arg(1))
        return (0 if a == b else (1 if a > b else 0xFFFFFFFF)), 8

    def _api_GetModuleHandleA(self):
        return 0, 4                     # no optional companion is loaded

    loaded: list = []

    def cstring(self, va: int, limit: int = 2048) -> str:
        out = bytearray()
        while len(out) < limit and self.mapped(va + len(out), 1):
            byte = self.read(va + len(out), 1)
            if byte == b"\0":
                break
            out += byte
        return out.decode("latin-1")

    # ---- running -------------------------------------------------------
    def call(self, address: int, args: list[int] = (), *, ecx: int | None = None,
             regs: dict[str, int] | None = None, until: int = RETURN,
             limit: int = 2_000_000) -> int:
        """Call `address` with stdcall/cdecl stack `args` (and ECX for
        thiscall); run until it returns to RETURN (or reaches `until`)."""
        esp = STACK_TOP - 0x1000
        for value in reversed(list(args)):
            esp -= 4
            self.put32(esp, value)
        esp -= 4
        self.put32(esp, RETURN)
        self.set_reg("esp", esp)
        if ecx is not None:
            self.set_reg("ecx", ecx)
        for name, value in (regs or {}).items():
            self.set_reg(name, value)
        self.mu.emu_start(address, until, count=limit)
        if self.reg("eip") != until:
            raise EmulationError(f"stopped at 0x{self.reg('eip'):X}, not 0x{until:X}")
        return self.reg("eax")

    def run(self, start: int, until: int, *, limit: int = 2_000_000) -> None:
        """Run from `start` (registers and stack as the test left them)."""
        self.mu.emu_start(start, until, count=limit)
        if self.reg("eip") != until:
            raise EmulationError(f"stopped at 0x{self.reg('eip'):X}, not 0x{until:X}")

    def export(self, name: str, *args: int) -> int:
        return self.call(self.exports[name], list(args))
