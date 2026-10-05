"""Emulate a patched game from the C runtime's call of WinMain to WinMain.

The executable the patcher publishes (render + the published-build
finalizers) is mapped at 0x400000 exactly as the loader maps it, with every
initialised section from the file and every byte beyond it zero: the state
the game is in when its C runtime calls WinMain, before the game has run a
single instruction of its own.  The run starts at that call and ends when
WinMain is entered.

Everything the startup loader does in between runs as machine code: the
appended stub, "VVFP Startup.dll", and every companion it loads, each mapped
from the very file the patcher ships when the stub or a companion loads it --
and only when it is loaded by its full path in the patcher's folder,
"<game folder>/Virtual Villagers Fun Patcher Files/".  kernel32 is
answered by name (Imports below), including the functions the stub looks up
in it with GetProcAddress; anything else they call stops the run with an
error.  The game folder may hold any Unicode characters: the wide API sees
them as they are, the ANSI API as the ANSI code page renders them ('?' for
what it cannot spell), as on Windows.  Every read, write and executed
instruction inside the executable image is recorded, so a test can require
that the startup touched nothing of the game but the code bytes its detours
verify and replace.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import pefile
from unicorn import (
    UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE, UC_MODE_32, Uc, UcError,
)
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX,
    UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP, UC_X86_REG_FS, UC_X86_REG_GDTR,
    UC_X86_REG_SS, UC_X86_REG_DS, UC_X86_REG_ES,
)

EXE_BASE = 0x400000
STUBS = 0x7C000000
STACK_TOP = 0x0F000000
HEAP = 0x60000000
MODULE_BASE = 0x10000000
GAME_DIR = "C:\\Games\\Virtual Villagers\\"
PATCHER_FILES = "Virtual Villagers Fun Patcher Files\\"
# The fake kernel32 module the stub finds with GetModuleHandleA.
KERNEL32_BASE = 0x7B000000
# The thread information block (fs) and the descriptor table that maps it.
TEB = 0x7FFDE000
GDT = 0x00030000
FS_INDEX = 4
DATA_INDEX = 2
# A sentinel the C runtime's frame holds: WinMain's own return address.
CRT_RETURN_SENTINEL = 0x0E000000

# kernel32 (and the few user32 / shell32 calls a companion may make) by the
# bytes each pops on return; None = cdecl.
STDCALL = {
    "GetModuleFileNameA": 12, "GetModuleFileNameW": 12, "LoadLibraryA": 4, "LoadLibraryW": 4,
    "LoadLibraryExW": 12, "LoadLibraryExA": 12,
    "GetModuleHandleA": 4, "GetModuleHandleW": 4, "GetProcAddress": 8, "VirtualProtect": 16,
    "VirtualQuery": 12, "VirtualAlloc": 16, "FlushInstructionCache": 12, "GetCurrentProcess": 0,
    "lstrcpyA": 8, "lstrlenA": 4, "lstrcmpiA": 8, "lstrcatA": 8, "lstrcpynA": 12, "GetTickCount": 0,
    "DisableThreadLibraryCalls": 4, "GetFileAttributesA": 4, "GetFileAttributesW": 4,
    "InitializeCriticalSection": 4, "EnterCriticalSection": 4, "LeaveCriticalSection": 4,
    "GetLastError": 0, "SetLastError": 4,
}


@dataclass
class Module:
    name: str
    base: int
    size: int
    exports: dict
    ordinals: dict
    path: str


@dataclass
class Access:
    kind: str          # "read", "write", "exec"
    va: int
    size: int
    pc: int


class StartupMachine:
    """One emulated process at the C runtime's call of WinMain."""

    def __init__(self, exe: bytes, exe_name: str, shipped: dict[str, Path], game_dir: str = GAME_DIR):
        """exe: the published executable's bytes; shipped: the companion files
        in the patcher's folder (destination name -> source file); game_dir:
        the folder GetModuleFileNameW reports, ending in a backslash."""
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        self.shipped = {name.lower(): path for name, path in shipped.items()}
        self.game_dir = game_dir
        self.files_dir = game_dir + PATCHER_FILES
        self.exe_path = game_dir + exe_name
        self.stub_names: dict[int, str] = {}
        self._next_stub = STUBS
        mu.mem_map(STUBS, 0x10000)
        mu.mem_map(KERNEL32_BASE, 0x1000)
        self.kernel32_stubs: dict[str, int] = {}
        self.modules: dict[str, Module] = {}
        self._next_base = MODULE_BASE
        self._next_heap = HEAP
        self.calls: list[tuple] = []
        self.accesses: list[Access] = []
        self.error: str | None = None
        self.stop_at: int | None = None

        pe = pefile.PE(data=exe)
        self.pe = pe
        image = bytearray(pe.get_memory_mapped_image(ImageBase=EXE_BASE))
        self._redirect(image, pe, EXE_BASE)
        self.exe_end = EXE_BASE + len(image)
        mu.mem_map(EXE_BASE, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(EXE_BASE, bytes(image))
        self.sections = [
            (s.Name.rstrip(b"\0").decode("latin-1"), EXE_BASE + s.VirtualAddress,
             EXE_BASE + s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData), s.Characteristics)
            for s in pe.sections
        ]
        self.iat = set()
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            for imp in entry.imports:
                self.iat.add(imp.address)
        mu.mem_map(STACK_TOP - 0x100000, 0x100000)
        self._map_thread_block()
        mu.mem_map(CRT_RETURN_SENTINEL, 0x1000)
        mu.mem_write(CRT_RETURN_SENTINEL, b"\xF4")
        mu.hook_add(UC_HOOK_CODE, self._code)
        mu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self._memory,
                    begin=EXE_BASE, end=self.exe_end - 1)

    # -- the thread ---------------------------------------------------------
    def _map_thread_block(self) -> None:
        """A thread information block at fs:0, as Windows gives every thread:
        an empty structured-exception chain (-1) and the stack bounds, so a
        companion's __try/__except frames link and unlink as they do in the
        game.  fs is loaded from a one-entry descriptor table."""
        mu = self.mu
        mu.mem_map(TEB, 0x1000)
        mu.mem_write(TEB, struct.pack("<7I", 0xFFFFFFFF, STACK_TOP, STACK_TOP - 0x100000, 0, 0, 0, TEB))
        mu.mem_map(GDT, 0x1000)
        limit, access, flags = 0xFFF, 0x92, 0x4          # present, data, read/write; 32-bit
        descriptor = ((limit & 0xFFFF) | ((TEB & 0xFFFFFF) << 16) | (access << 40)
                      | (((limit >> 16) & 0xF) << 48) | (flags << 52) | (((TEB >> 24) & 0xFF) << 56))
        mu.mem_write(GDT + 8 * FS_INDEX, struct.pack("<Q", descriptor))
        flat = (0xFFFF | (0x92 << 40) | (0xF << 48) | (0xC << 52))   # base 0, 4 GiB, data
        mu.mem_write(GDT + 8 * DATA_INDEX, struct.pack("<Q", flat))
        mu.reg_write(UC_X86_REG_GDTR, (0, GDT, 0x100, 0))
        # With a descriptor table in place every data segment is reloaded
        # from it: ss, ds and es flat, fs the thread block.
        for register in (UC_X86_REG_SS, UC_X86_REG_DS, UC_X86_REG_ES):
            mu.reg_write(register, DATA_INDEX << 3)
        mu.reg_write(UC_X86_REG_FS, FS_INDEX << 3)

    # -- the image --------------------------------------------------------------
    def section_of(self, va: int):
        for name, start, end, characteristics in self.sections:
            if start <= va < end:
                return name, characteristics
        return None, 0

    def _redirect(self, image: bytearray, pe: pefile.PE, base: int) -> None:
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            for imp in entry.imports:
                name = imp.name.decode() if imp.name else f"#{imp.ordinal}"
                stub = self._next_stub
                self._next_stub += 16
                self.stub_names[stub] = name
                struct.pack_into("<I", image, imp.address - base, stub)
                popped = STDCALL.get(name)
                self.mu.mem_write(stub, b"\xC2" + struct.pack("<H", popped) if popped is not None else b"\xF4")

    def _load(self, name: str) -> Module | None:
        key = name.lower()
        if key in self.modules:
            return self.modules[key]
        source = self.shipped.get(key)
        if source is None:
            return None
        pe = pefile.PE(str(source))
        base = self._next_base
        self._next_base += 0x01000000
        pe.relocate_image(base)
        image = bytearray(pe.get_memory_mapped_image(ImageBase=base))
        self._redirect(image, pe, base)
        size = (len(image) + 0xFFFF) & ~0xFFFF
        self.mu.mem_map(base, size)
        self.mu.mem_write(base, bytes(image))
        exports, ordinals = {}, {}
        if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
            for e in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                if e.name:
                    exports[e.name.decode()] = base + e.address
                ordinals[e.ordinal] = base + e.address
        module = Module(name, base, size, exports, ordinals, self.files_dir + name)
        self.modules[key] = module
        return module

    def module_at(self, base: int) -> Module | None:
        return next((m for m in self.modules.values() if m.base == base), None)

    # -- hooks ------------------------------------------------------------------
    def _memory(self, mu, access, address, size, value, user_data):
        kind = "write" if access == UC_MEM_WRITE else "read"
        self.accesses.append(Access(kind, address, size, mu.reg_read(UC_X86_REG_EIP)))

    def _code(self, mu, address, size, user_data):
        if address == self.stop_at:
            mu.emu_stop()
            return
        if EXE_BASE <= address < self.exe_end:
            self.accesses.append(Access("exec", address, size, address))
        name = self.stub_names.get(address)
        if name is not None:
            self._import(name)

    def _import(self, name: str) -> None:
        mu = self.mu
        sp = mu.reg_read(UC_X86_REG_ESP)
        arg = lambda k: struct.unpack("<I", mu.mem_read(sp + 4 + 4 * k, 4))[0]   # noqa: E731
        cstr = lambda va: bytes(mu.mem_read(va, 520)).split(b"\0")[0].decode("latin-1")   # noqa: E731

        def wstr(va: int) -> str:
            raw = bytes(mu.mem_read(va, 4096))
            end = next(i for i in range(0, len(raw), 2) if raw[i:i + 2] == b"\0\0")
            return raw[:end].decode("utf-16-le")

        ret = lambda v: mu.reg_write(UC_X86_REG_EAX, v & 0xFFFFFFFF)   # noqa: E731
        if name in ("GetModuleFileNameA", "GetModuleFileNameW"):
            module = self.module_at(arg(0)) if arg(0) else None
            path = module.path if module else self.exe_path
            wide = name.endswith("W")
            n = arg(2)
            # The ANSI API renders the path in the ANSI code page: a character
            # it cannot spell comes back as '?', as on Windows.
            text = path.encode("utf-16-le") if wide else path.encode("cp1252", errors="replace")
            unit = 2 if wide else 1
            length = len(text) // unit
            if length + 1 > n:
                mu.mem_write(arg(1), text[: (n - 1) * unit] + b"\0" * unit)
                ret(n)
            else:
                mu.mem_write(arg(1), text + b"\0" * unit)
                ret(length)
            self.calls.append((name,))
        elif name in ("LoadLibraryA", "LoadLibraryW", "LoadLibraryExA", "LoadLibraryExW",
                      "GetModuleHandleA", "GetModuleHandleW"):
            wide = name.endswith("W")
            text = wstr(arg(0)) if wide else (cstr(arg(0)) if arg(0) else "")
            if name.startswith("GetModuleHandle") and not arg(0):
                ret(EXE_BASE)
                return
            if name.startswith("GetModuleHandle") and text.lower() == "kernel32.dll":
                self.calls.append((name, text, False))
                ret(KERNEL32_BASE)
                return
            base_name = text.replace("/", "\\").split("\\")[-1]
            # A load counts only by its full path in the patcher's folder,
            # exactly as Windows would find the file there (the ANSI API's
            # '?' never matches a real folder name).
            full = text.lower() == (self.files_dir + base_name).lower()
            if name.startswith("LoadLibrary"):
                module = self._load(base_name) if full else None
            else:
                module = self.modules.get(base_name.lower()) if "\\" not in text else None
            self.calls.append((name, text, full))
            ret(module.base if module else 0)
        elif name == "GetProcAddress" and arg(0) == KERNEL32_BASE:
            proc = cstr(arg(1))
            self.calls.append((name, "KERNEL32.dll", proc))
            if proc not in STDCALL:
                ret(0)
                return
            stub = self.kernel32_stubs.get(proc)
            if stub is None:
                stub = self._next_stub
                self._next_stub += 16
                self.stub_names[stub] = proc
                self.mu.mem_write(stub, b"\xC2" + struct.pack("<H", STDCALL[proc]))
                self.kernel32_stubs[proc] = stub
            ret(stub)
        elif name == "GetProcAddress":
            module = self.module_at(arg(0))
            proc = arg(1)
            if proc < 0x10000:
                address = module.ordinals.get(proc, 0) if module else 0
                self.calls.append((name, module.name if module else None, proc))
            else:
                text = cstr(proc)
                address = module.exports.get(text, 0) if module else 0
                self.calls.append((name, module.name if module else None, text))
            ret(address)
        elif name == "VirtualProtect":
            mu.mem_write(arg(3), struct.pack("<I", 0x20))
            self.calls.append((name, arg(0), arg(1), arg(2)))
            ret(1)
        elif name == "VirtualQuery":
            address = arg(0)
            section, characteristics = self.section_of(address)
            protect = 0x20 if characteristics & 0x20000000 else 0x04
            mu.mem_write(arg(1), struct.pack("<7I", address & ~0xFFF, EXE_BASE, protect, 0x1000,
                                             0x1000, protect, 0x1000000))
            ret(28)
        elif name == "VirtualAlloc":
            size = (arg(1) + 0xFFFF) & ~0xFFFF
            base = self._next_heap
            self._next_heap += size
            mu.mem_map(base, size)
            self.calls.append((name, arg(1), arg(3)))
            ret(base)
        elif name == "FlushInstructionCache":
            ret(1)
        elif name == "GetCurrentProcess":
            ret(0xFFFFFFFF)
        elif name == "lstrcpyA":
            mu.mem_write(arg(0), cstr(arg(1)).encode("latin-1") + b"\0")
            ret(arg(0))
        elif name == "lstrcatA":
            mu.mem_write(arg(0), (cstr(arg(0)) + cstr(arg(1))).encode("latin-1") + b"\0")
            ret(arg(0))
        elif name == "lstrcpynA":
            text = cstr(arg(1))[: max(arg(2) - 1, 0)]
            mu.mem_write(arg(0), text.encode("latin-1") + b"\0")
            ret(arg(0))
        elif name == "lstrcmpiA":
            first, second = cstr(arg(0)).lower(), cstr(arg(1)).lower()
            ret((first > second) - (first < second))
        elif name == "lstrlenA":
            ret(len(cstr(arg(0))))
        elif name == "GetTickCount":
            ret(1000)
        elif name in ("DisableThreadLibraryCalls", "InitializeCriticalSection", "EnterCriticalSection",
                      "LeaveCriticalSection", "SetLastError"):
            ret(1)
        elif name == "GetLastError":
            ret(0)
        elif name in ("GetFileAttributesA", "GetFileAttributesW"):
            text = wstr(arg(0)) if name.endswith("W") else cstr(arg(0))
            base_name = text.split("\\")[-1].lower()
            there = base_name in self.shipped and text.lower() == (self.files_dir + base_name).lower()
            ret(0x20 if there else 0xFFFFFFFF)
        else:
            self.error = f"unexpected import {name}"
            mu.emu_stop()

    # -- running ----------------------------------------------------------------
    def run_to_winmain(self, call_va: int, winmain_va: int, count: int = 20_000_000) -> dict:
        """Execute the C runtime's `call WinMain` at `call_va` and stop as
        WinMain is entered.  Returns the registers and stack at both ends."""
        mu = self.mu
        esp = STACK_TOP - 0x8000
        args = (0x400000, 0, 0x7FFE0000, 10)                 # hInstance, 0, lpCmdLine, nShowCmd
        mu.mem_write(esp, struct.pack("<4I", *args))
        regs = {UC_X86_REG_EAX: 0x11111111, UC_X86_REG_EBX: 0x22222222, UC_X86_REG_ECX: 0x33333333,
                UC_X86_REG_EDX: 0x44444444, UC_X86_REG_ESI: 0x55555555, UC_X86_REG_EDI: 0x66666666,
                UC_X86_REG_EBP: STACK_TOP - 0x100}
        for reg, value in regs.items():
            mu.reg_write(reg, value)
        mu.reg_write(UC_X86_REG_ESP, esp)
        self.stop_at = winmain_va
        try:
            mu.emu_start(call_va, 0, count=count)
        except UcError as exc:
            raise AssertionError(f"emulation fault {exc} at {mu.reg_read(UC_X86_REG_EIP):#x}") from None
        if self.error:
            raise AssertionError(self.error)
        eip = mu.reg_read(UC_X86_REG_EIP)
        if eip != winmain_va:
            raise AssertionError(f"stopped at {eip:#x}, not at WinMain {winmain_va:#x}")
        at_entry = {reg: mu.reg_read(reg) for reg in regs}
        sp = mu.reg_read(UC_X86_REG_ESP)
        return {
            "registers_before": regs,
            "registers_at_winmain": at_entry,
            "esp_before_call": esp,
            "esp_at_winmain": sp,
            "return_address": struct.unpack("<I", mu.mem_read(sp, 4))[0],
            "arguments": struct.unpack("<4I", mu.mem_read(sp + 4, 16)),
            "expected_arguments": args,
        }

    def code(self, va: int, n: int) -> bytes:
        return bytes(self.mu.mem_read(va, n))

    def module_of(self, pc: int) -> str:
        for module in self.modules.values():
            if module.base <= pc < module.base + module.size:
                return module.name
        return f"{pc:#x}"

    def audit(self, stock_exe: bytes, winmain_va: int) -> dict[str, list]:
        """Sort every access the run made inside the executable image.

        game_data: any read or write of the stock game's own writable data
          (every stock section the loader maps writable, over its whole
          virtual extent -- .data with its zero-filled tail, .shr's word);
        game_code_run: any instruction of the executable run other than the
          appended stub (WinMain itself, where the run stops, excepted);
        unverified_writes: a write to a byte nothing read first -- every
          detour verifies the bytes it replaces before writing them;
        writable_data: a read or write of a writable section the patcher
          appends (its own data, not the game's);
        code / constants / iat: what the installs legitimately touch -- the
          executable's code and read-only image bytes they verify and
          replace, and the import slots the stub calls through.
        """
        stock = pefile.PE(data=stock_exe, fast_load=True)
        game_data = [
            (EXE_BASE + s.VirtualAddress, EXE_BASE + s.VirtualAddress + s.Misc_VirtualSize,
             s.Name.rstrip(b"\0").decode("latin-1"))
            for s in stock.sections if s.Characteristics & 0x80000000
        ]
        out: dict[str, list] = {k: [] for k in (
            "game_data", "game_code_run", "unverified_writes", "writable_data", "code", "constants", "iat")}
        verified: set[int] = set()
        for a in self.accesses:
            section, characteristics = self.section_of(a.va)
            where = (a.kind, f"{a.va:#x}", section, self.module_of(a.pc))
            if a.kind == "exec":
                if a.va != winmain_va and section != ".vvfpst":
                    out["game_code_run"].append(where)
                continue
            if any(lo <= a.va < hi for lo, hi, _ in game_data):
                out["game_data"].append(where)
            elif a.kind == "read" and a.va in self.iat:
                out["iat"].append(where)
            elif characteristics & 0x20000000:
                out["code"].append(where)
            elif characteristics & 0x80000000:
                out["writable_data"].append(where)
            else:
                out["constants"].append(where)
            span = range(a.va, a.va + a.size)
            if a.kind == "read":
                verified.update(span)
            elif not all(byte in verified for byte in span):
                out["unverified_writes"].append(where)
        return out
