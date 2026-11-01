"""Dump The Secret City's sprite resource table (0x4A95A0) and every picture-name string the exe holds.

Research helper for src/vv_assets_vv3.py (read only; prints)."""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"


def main() -> None:
    pe = pefile.PE(str(EXE))
    image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase

    def text(va):
        if not va or not (base <= va < base + len(image)):
            return None
        return image[va - base:va - base + 80].split(b"\0", 1)[0].decode("latin-1")
    for i in range(0x100):
        f = struct.unpack_from("<12I", image, 0x4A95A0 + i * 0x30 - base)
        name = text(f[1])
        if name is None:
            print("end at", i)
            break
        print(f"{i:3d} id={f[0]:#x} {name!r} cols={f[2]} rows={f[3]} suffix={text(f[4])!r} sheets={f[5]},{f[6]} rest={[hex(v) for v in f[7:]]}")
    if "--strings" in sys.argv:
        for m in re.finditer(rb"[A-Za-z0-9_ .\-]{3,}\.(png|jpg|PNG|JPG)\0", image):
            print(hex(base + m.start()), m.group()[:-1].decode())
        for m in re.finditer(rb"[A-Za-z0-9_\-]{3,}\0", image):
            pass


if __name__ == "__main__":
    main()
