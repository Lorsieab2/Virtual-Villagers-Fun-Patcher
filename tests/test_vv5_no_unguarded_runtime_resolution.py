"""Fail if patched VV5 code uses a runtime-resolved pointer without a NULL check.

A patched game can legitimately find itself without its companion files: the
executable gets renamed, copied somewhere on its own, or launched with a
different working directory. Then LoadLibraryA, GetProcAddress, GetModuleHandleA
and the asset loader all return NULL -- and an unguarded use of that NULL is an
immediate access violation, i.e. the game crashes on startup or the moment the
feature is touched, rather than simply doing nothing.

This is not hypothetical: the VV2 build hit exactly this -- 0xC0000005 at an
injected cave (VA ~0x473DA2) because a companion mask PNG failed to load on a
renamed exe and the render cave dereferenced the NULL atlas pointer. VV5 must
never regress into that shape.

Every such result must therefore be NULL-checked before it is called or
dereferenced. That is cheap (test/jz) and turns "crashes when the companion
DLL or PNG is missing" into "the feature is quietly inert", which is the only
acceptable behaviour for an optional cosmetic patch.

The check tracks the value as it moves between registers, because the real code
does `call ...; mov edx, eax; test edx, edx` -- a scan that only watches EAX
reports a false positive there.

Stock call sites are ignored: this is about what the patches add.

Ported from VV1's test_vv1_no_unguarded_runtime_resolution.py (thanks to that
chat). CAVEAT it inherits: this proves the guard AT THE RESOLUTION SITE only. A
pointer that is cached and re-read by a later draw path (as a future bighead
overlay would cache an SDL_Surface* across frames) must ALSO guard the cache
reader -- that is out of scope here and must be checked at the draw site.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

try:
    import capstone
    import pefile

    HAVE_DEPS = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_DEPS = False

STOCK = ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe"

# Imports whose result is NULL when the companion file / module is missing.
LOAD_LIBRARY = 0x4951E0
GET_PROC_ADDRESS = 0x4951DC
GET_MODULE_HANDLE = 0x4951D8  # GetModuleHandleA -> NULL when the module isn't loaded
IMG_LOAD_IAT = 0x495300       # SDL2_image IMG_Load IAT slot (FF15 form)
# IMG_Load's compiler jump-stub: a rel32 `call` lands here (E8 form).
IMG_LOAD_THUNK = 0x47BAAA

WATCHED_IAT = {
    LOAD_LIBRARY: "LoadLibraryA",
    GET_PROC_ADDRESS: "GetProcAddress",
    GET_MODULE_HANDLE: "GetModuleHandleA",
    IMG_LOAD_IAT: "IMG_Load",
}
LOOKAHEAD = 12


def _sections(pe):
    return [
        (s.PointerToRawData, s.SizeOfRawData, pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress)
        for s in pe.sections
    ]


def _file_to_va(pe, offset: int):
    for raw, size, va in _sections(pe):
        if raw <= offset < raw + size:
            return va + (offset - raw)
    return None


def _resolution_sites(data: bytes, stock: bytes, pe):
    """Every patched call whose return value may be NULL."""
    out = []
    for slot, name in WATCHED_IAT.items():
        pattern = b"\xFF\x15" + struct.pack("<I", slot)
        start = 0
        while True:
            start = data.find(pattern, start)
            if start < 0:
                break
            if start >= len(stock) or data[start : start + 6] != stock[start : start + 6]:
                out.append((_file_to_va(pe, start), start, name))
            start += 1
    # direct rel32 calls to the IMG_Load jump-stub
    for offset in range(len(data) - 5):
        if data[offset] != 0xE8:
            continue
        va = _file_to_va(pe, offset)
        if va is None:
            continue
        target = va + 5 + struct.unpack_from("<i", data, offset + 1)[0]
        if target != IMG_LOAD_THUNK:
            continue
        if offset >= len(stock) or data[offset : offset + 5] != stock[offset : offset + 5]:
            out.append((va, offset, "IMG_Load"))
    return out


def _is_guarded(md, data: bytes, offset: int, va: int) -> tuple[bool, str]:
    """True if the result is NULL-checked before being called or dereferenced."""
    tracked = {"eax"}
    body = list(md.disasm(data[offset : offset + 96], va))[1 : LOOKAHEAD + 1]
    for ins in body:
        text = f"{ins.mnemonic} {ins.op_str}"
        if ins.mnemonic in ("test", "cmp"):
            if any(reg in ins.op_str for reg in tracked):
                return True, text
        if ins.mnemonic == "mov" and "," in ins.op_str:
            dst, src = (part.strip() for part in ins.op_str.split(",", 1))
            if src in tracked and dst.isalpha():
                tracked.add(dst)
            elif dst in tracked and src not in tracked:
                tracked.discard(dst)
        if ins.mnemonic == "call" and ins.op_str in tracked:
            return False, f"called without a check: {text}"
        if "[" in ins.op_str and "]" in ins.op_str and ins.mnemonic != "lea":
            # Only what is BETWEEN the brackets is an address computation. The
            # source operand of a store sits outside them, so `mov [tbl], eax`
            # is caching the result, not dereferencing it.
            inside = ins.op_str[ins.op_str.index("[") + 1 : ins.op_str.index("]")]
            if any(reg in inside for reg in tracked):
                return False, f"dereferenced without a check: {text}"
    return False, "no NULL check within lookahead"


@unittest.skipUnless(HAVE_DEPS, "requires capstone and pefile")
@unittest.skipUnless(STOCK.exists(), "requires the exact-build VV5 stock executable")
class VV5NoUnguardedRuntimeResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import vv_fun_patcher as patcher

        builds = {b.id: b for b in patcher.load_builds()}
        ids = [f.id for f in patcher.load_fun_patches() if f.game_id == "vv5"]
        cls.stock = STOCK.read_bytes()
        cls.renders = {}
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            rendered, _ = patcher.render_patched_bytes(STOCK, builds["vv5"], mode, ids)
            cls.renders[mode] = bytes(rendered)

    def test_every_patched_resolution_is_null_checked(self) -> None:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for mode, data in self.renders.items():
            pe = pefile.PE(data=data, fast_load=True)
            sites = _resolution_sites(data, self.stock, pe)
            self.assertGreater(len(sites), 0, f"{mode}: found no patched sites to check")
            for va, offset, name in sites:
                with self.subTest(mode=mode, site=hex(va), api=name):
                    guarded, why = _is_guarded(md, data, offset, va)
                    self.assertTrue(
                        guarded,
                        f"{name} at {va:#x} ({mode}) is used without a NULL check "
                        f"-- {why}. A renamed/moved executable loses its companion "
                        "files, so this is an access violation rather than the "
                        "feature going quietly inert.",
                    )


if __name__ == "__main__":
    unittest.main()
