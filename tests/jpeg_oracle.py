"""The games' own JPEG decoder, run in Unicorn: libjpeg-9.dll (IJG libjpeg 9, 13-Jan-2013) as SDL2_image's
IMG_LoadJPG_RW drives it (SDL2_image.dll 0x10003510): jpeg_CreateDecompress(cinfo, 90, 0x1C8), the source,
jpeg_read_header(cinfo, TRUE), quantize_colors (+0x4A) = FALSE, out_color_space (+0x2C) = JCS_RGB,
jpeg_calc_output_dimensions, jpeg_start_decompress, one jpeg_read_scanlines per row, jpeg_finish_decompress.

The DLL is a 32-bit PE mapped at its own base; its C library imports are answered in Python (malloc, free,
memcpy, memset ... the rest return 0).  The JPEG is given through libjpeg's own jpeg_mem_src.  Used by
tests/test_vv_jpeg.py only (never shipped).
"""
from __future__ import annotations

import struct
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP

STUBS = 0x0E000000
HEAP = 0x20000000
HEAP_SIZE = 0x08000000
STACK = 0x0F000000
STACK_SIZE = 0x00100000
DATA = 0x0E100000
END = 0x0E0FFFF0                 # the return address of a call from Python


class LibJpeg:
    def __init__(self, dll: Path) -> None:
        pe = pefile.PE(str(dll))
        self.base = base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        mu = self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(base, size)
        mu.mem_write(base, pe.get_memory_mapped_image()[:size])
        mu.mem_map(STUBS, 0x200000)
        mu.mem_map(HEAP, HEAP_SIZE)
        mu.mem_map(STACK, STACK_SIZE)
        self.heap = HEAP
        self.handlers: dict[int, tuple[str, object]] = {}
        slot = 0
        data_slot = DATA
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                name = imp.name.decode() if imp.name else f"#{imp.ordinal}"
                if name in ("_iob", "__mb_cur_max"):
                    mu.mem_write(imp.address, struct.pack("<I", data_slot))
                    data_slot += 0x400
                    continue
                stub = STUBS + slot * 16
                slot += 1
                mu.mem_write(stub, b"\xC3")
                mu.mem_write(imp.address, struct.pack("<I", stub))
                self.handlers[stub] = (name, getattr(self, "_" + name, None))
        mu.mem_write(END, b"\xF4")
        mu.hook_add(UC_HOOK_CODE, self._hook, begin=STUBS, end=STUBS + 0x1FFFFF)
        self.exports = {s.name.decode(): base + s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}

    # ---- memory
    def alloc(self, n: int) -> int:
        at = self.heap
        self.heap = (self.heap + max(n, 4) + 15) & ~15
        if self.heap > HEAP + HEAP_SIZE:
            raise MemoryError("the emulated heap is full")
        return at

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.mu.mem_read(va, 4))[0]

    def arg(self, i: int) -> int:
        return self.u32(self.mu.reg_read(UC_X86_REG_ESP) + 4 + 4 * i)

    # ---- the C library
    def _hook(self, mu, address, size, user) -> None:
        entry = self.handlers.get(address)
        if entry is None:
            return
        name, fn = entry
        if name in ("abort", "exit", "_amsg_exit"):
            raise RuntimeError(f"libjpeg called {name}")
        result = fn() if fn is not None else 0
        mu.reg_write(UC_X86_REG_EAX, result & 0xFFFFFFFF)

    def _malloc(self) -> int:
        return self.alloc(self.arg(0))

    def _calloc(self) -> int:
        n = self.arg(0) * self.arg(1)
        at = self.alloc(n)
        self.mu.mem_write(at, bytes(n))
        return at

    def _free(self) -> int:
        return 0

    def _memcpy(self) -> int:
        dst, src, n = self.arg(0), self.arg(1), self.arg(2)
        if n:
            self.mu.mem_write(dst, bytes(self.mu.mem_read(src, n)))
        return dst

    def _memset(self) -> int:
        dst, value, n = self.arg(0), self.arg(1), self.arg(2)
        if n:
            self.mu.mem_write(dst, bytes([value & 0xFF]) * n)
        return dst

    def _strlen(self) -> int:
        at, n = self.arg(0), 0
        while self.mu.mem_read(at + n, 1)[0]:
            n += 1
        return n

    # ---- calling the DLL
    def call(self, name: str, *args: int) -> int:
        esp = STACK + STACK_SIZE - 0x1000
        frame = struct.pack("<I", END) + b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        esp -= len(frame)
        self.mu.mem_write(esp, frame)
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.emu_start(self.exports[name], END)
        return self.mu.reg_read(UC_X86_REG_EAX)

    def decode(self, data: bytes) -> tuple[int, int, bytes]:
        """(width, height, RGB rows) exactly as libjpeg 9 gives them to SDL2_image."""
        self.heap = HEAP
        err = self.alloc(0x100)
        cinfo = self.alloc(0x1C8)
        self.mu.mem_write(cinfo, bytes(0x1C8))
        self.mu.mem_write(cinfo, struct.pack("<I", self.call("jpeg_std_error", err)))
        self.call("jpeg_CreateDecompress", cinfo, 90, 0x1C8)
        buf = self.alloc(len(data))
        self.mu.mem_write(buf, bytes(data))
        self.call("jpeg_mem_src", cinfo, buf, len(data))
        self.call("jpeg_read_header", cinfo, 1)
        self.mu.mem_write(cinfo + 0x4A, b"\0")
        self.mu.mem_write(cinfo + 0x2C, struct.pack("<I", 2))
        self.call("jpeg_calc_output_dimensions", cinfo)
        self.call("jpeg_start_decompress", cinfo)
        width, height = self.u32(cinfo + 0x5C), self.u32(cinfo + 0x60)
        row = self.alloc(width * 3)
        rows = self.alloc(4)
        self.mu.mem_write(rows, struct.pack("<I", row))
        out = bytearray()
        while self.u32(cinfo + 0x78) < height:
            self.call("jpeg_read_scanlines", cinfo, rows, 1)
            out += self.mu.mem_read(row, width * 3)
        self.call("jpeg_finish_decompress", cinfo)
        return width, height, bytes(out)
