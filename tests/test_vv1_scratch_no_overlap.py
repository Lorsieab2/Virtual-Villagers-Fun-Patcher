"""No two things may share a byte of VV1's .vv1md scratch.

The owner's crash of 2026-09-19 23:31 (full dump: eax = DLL+0x2000, ebx = 1,
write to address 1, return address inside the doubler save stub) came from
the cached Vv1DoublerSave address at scratch+0x1FC sharing its low byte with
MASK_BIRTH_DIRTY, a byte flag at the same address: the birth hook's
`mov byte ptr [..], 1` and the companion's clear turned DLL+0x2050 into
DLL+0x2001 and then DLL+0x2000, and the next autosave called into the middle
of an instruction.  These guards make that class of layout error a test
failure, and check the rendered patch bytes rather than only the constants.
"""
from __future__ import annotations

import importlib.util
import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_vv1_origins_feature.py"
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"


def _builder():
    spec = importlib.util.spec_from_file_location("vv1_origins_builder_for_scratch_test", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScratchLayoutTest(unittest.TestCase):
    def test_builder_declares_every_scratch_slot_and_they_do_not_overlap(self) -> None:
        b = _builder()
        slots = b.SCRATCH_SLOTS
        names = {name for name, _, _ in slots}
        for required in ("MASK_BIRTH_DIRTY", "DOUBLER_SAVE_DLL_FN", "DOUBLER_RESTORE_DLL_FN", "MASK_TICK_DLL_FN", "MASK_SAVE_SLOT", "MASK_TABLE"):
            self.assertIn(required, names)
        # every *_VA constant that lives in the scratch section is listed
        base, end = b.DATA_SCRATCH_BASE_VA, b.DATA_SCRATCH_BASE_VA + 0x1000
        listed = {va for _, va, _ in slots}
        for name in dir(b):
            if name.endswith("_VA") and isinstance(getattr(b, name), int) and base <= getattr(b, name) < end:
                self.assertIn(getattr(b, name), listed, "%s is in .vv1md but not in SCRATCH_SLOTS" % name)
        b._check_scratch_slots()  # raises on overlap
        # and the check really detects overlap
        with self.assertRaises(AssertionError):
            b._check_scratch_slots((("a", base, 4), ("b", base + 3, 1)))

    def test_the_birth_dirty_byte_shares_no_dword_with_a_cached_pointer(self) -> None:
        b = _builder()
        for cache in (b.DOUBLER_SAVE_DLL_FN_VA, b.DOUBLER_RESTORE_DLL_FN_VA, b.MASK_TICK_DLL_FN_VA, b.PORTRAIT_DLL_FN_VA, b.VILLAGE_MASK_DLL_FN_VA):
            self.assertFalse(cache <= b.MASK_BIRTH_DIRTY_VA < cache + 4, "%#x" % cache)
        self.assertEqual(b.MASK_BIRTH_DIRTY_VA, b.DATA_SCRATCH_BASE_VA + 0x1FC, "the companion hardcodes the flag at +0x1FC")
        self.assertNotEqual(b.DOUBLER_SAVE_DLL_FN_VA, b.DATA_SCRATCH_BASE_VA + 0x1FC)

    def test_rendered_patches_never_byte_store_into_a_cached_pointer(self) -> None:
        """Scan every patch's bytes for `mov byte ptr [abs32], imm8` (C6 05 disp32 imm8)
        and `mov byte ptr [abs32], reg` (88 05/0D/15/1D/25/2D/35/3D disp32) whose
        target falls inside a cached-pointer dword."""
        b = _builder()
        record = json.loads(MANIFEST.read_text(encoding="utf-8"))
        caches = {b.DOUBLER_SAVE_DLL_FN_VA, b.DOUBLER_RESTORE_DLL_FN_VA, b.MASK_TICK_DLL_FN_VA, b.PORTRAIT_DLL_FN_VA, b.VILLAGE_MASK_DLL_FN_VA}
        hits = []
        byte_stores = re.compile(rb"\xc6\x05(.{4})|\x88[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](.{4})", re.S)
        for patch in record["patches"]:
            after = bytes.fromhex(patch["after"])
            for m in byte_stores.finditer(after):
                target = struct.unpack("<I", m.group(1) or m.group(2))[0]
                for cache in caches:
                    if cache <= target < cache + 4:
                        hits.append((patch["offset"], hex(target), hex(cache)))
        self.assertEqual(hits, [], "a byte store lands inside a cached export address")
        # positive control: the birth hook's byte store IS present, at the flag
        flag = struct.pack("<I", b.MASK_BIRTH_DIRTY_VA)
        self.assertTrue(any(b"\xc6\x05" + flag + b"\x01" in bytes.fromhex(p["after"]) for p in record["patches"]),
                        "the birth hook still sets MASK_BIRTH_DIRTY")
        # and the save stub caches at the new dword
        save_cache = struct.pack("<I", b.DOUBLER_SAVE_DLL_FN_VA)
        self.assertTrue(any(b"\xa3" + save_cache in bytes.fromhex(p["after"]) for p in record["patches"]),
                        "the save stub stores its resolved export at DOUBLER_SAVE_DLL_FN_VA")


if __name__ == "__main__":
    unittest.main()
