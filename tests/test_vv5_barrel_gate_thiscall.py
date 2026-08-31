"""VV5 Barrel of Babies crashed the game the moment it was purchased.

The barrel's capacity gate is the game's own `0x472BD0`. That function is
__thiscall and never loads ECX itself: it forwards its own `this` straight to
`0x4713F0`, which does

    lea esi, [ecx + 0x1D34]
    mov ebx, 0x96
    lea ecx, [esi - 0x1CEC]      ; == original ecx + 0x48
    call 0x466170

The barrel cave called `0x472BD0` with whatever ECX happened to be left in the
register, so `0x466170` was entered on a wild `this + 0x48` and the game
access-violated on purchase.

Both crash dumps match that reading exactly: ECX was garbage and *different on
each run*, EBX was 150 (`0x96`, the constant above), and ESI - ECX was exactly
0x1CEC. The fix is the single instruction every stock caller already emits.

This is deliberately guarded in two independent places:

  * against the stock executable, so the calling convention is derived from the
    binary rather than asserted here; and
  * against the emitted page, which is what actually ships.
"""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
MANIFEST = ROOT / "data" / "vv5_task9_native_actions.json"

CAP_GATE = 0x472BD0
VILLAGE_MANAGER = 0x554148
# mov ecx, imm32
MOV_ECX_MANAGER = b"\xb9" + struct.pack("<I", VILLAGE_MANAGER)


def _sections(image: bytes):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    opt = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 24 + 28)[0]
    out = []
    for i in range(count):
        off = pe + 24 + opt + i * 40
        name = image[off : off + 8].rstrip(b"\0").decode()
        vsize, va, rsize, ptr = struct.unpack_from("<IIII", image, off + 8)
        out.append((name, va, vsize, ptr, rsize))
    return base, out


def _call_sites(blob: bytes, blob_va: int, target: int) -> list[int]:
    """Offsets of every direct `call target` in blob."""
    found = []
    for i in range(len(blob) - 5):
        if blob[i] != 0xE8:
            continue
        rel = struct.unpack_from("<i", blob, i + 1)[0]
        if blob_va + i + 5 + rel == target:
            found.append(i)
    return found


def _page():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    layout = manifest["pe_append_transaction"]["layouts"]["collection_progression"]
    return bytes.fromhex(layout["append_bytes"]), int(layout["page_virtual_address"], 16)


class BarrelGateThiscallTests(unittest.TestCase):
    @unittest.skipUnless(STOCK.is_file(), "stock VV5 executable is not present")
    def test_every_stock_caller_sets_ecx(self) -> None:
        """Establishes the contract from the binary instead of asserting it."""
        image = STOCK.read_bytes()
        base, sections = _sections(image)
        text = next(s for s in sections if s[0] == ".text")
        _name, va, _vsize, ptr, rsize = text
        blob = image[ptr : ptr + rsize]
        sites = _call_sites(blob, base + va, CAP_GATE)

        # Decoding every byte offset finds a few misaligned false positives, so
        # judge on the ratio rather than demanding all of them.
        setters = [i for i in sites if blob[i - 5 : i] == MOV_ECX_MANAGER]
        self.assertGreaterEqual(len(sites), 10, "expected the gate to be widely called")
        self.assertGreaterEqual(
            len(setters),
            len(sites) - 1,
            f"only {len(setters)} of {len(sites)} stock call sites load "
            f"ECX = 0x{VILLAGE_MANAGER:X}; the premise of this test is that "
            f"loading it is the required calling convention",
        )

    def test_the_barrel_gate_calls_load_ecx(self) -> None:
        """The shipping page. This is the regression itself."""
        page, page_va = _page()
        sites = _call_sites(page, page_va, CAP_GATE)

        # Barrel of Babies checks capacity twice: once before showing the
        # confirmation and once after, so a village that filled up while the
        # prompt was open cannot slip through. If that ever drops to one, the
        # re-check is gone and this test should be revisited, not relaxed.
        self.assertEqual(
            len(sites), 2, "expected exactly the two barrel capacity checks"
        )
        for offset in sites:
            with self.subTest(va=hex(page_va + offset)):
                self.assertEqual(
                    page[offset - 5 : offset],
                    MOV_ECX_MANAGER,
                    f"the capacity gate at 0x{page_va + offset:X} is called "
                    f"without loading ECX = 0x{VILLAGE_MANAGER:X}; 0x472BD0 is "
                    f"__thiscall and forwards ECX to 0x4713F0, which "
                    f"dereferences it -- this crashed the game on purchase",
                )

    def test_the_generator_says_why(self) -> None:
        """A bare `mov ecx` invites a later reader to delete it as redundant."""
        source = (ROOT / "scripts" / "build_vv5_task9_native_actions.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("__thiscall", source)
        self.assertIn("0x4713F0", source)


if __name__ == "__main__":
    unittest.main()
