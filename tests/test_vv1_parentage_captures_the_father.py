"""VV1 captures the father at the conception call sites.

VV1 stores nothing about the father in the mother's record: its conception
routine receives a partner value and never stores it, and the field that once
looked like a father id turned out to be a skill value. So unlike VV2-VV5 there
is nothing to read at the success tails.

His record IS live at the call sites. sub_43BBC0 has six callers and no
indirect references, and each loads exactly one field off his record (+0x36C)
before discarding the pointer. So each call is routed through a stub that
stashes the pointer, and the success-tail trampolines pass it to the companion.

These guards pin the parts that would fail silently rather than loudly: a stub
aimed at the wrong place still assembles, and a capture that is never cleared
still logs -- with the previous birth's father.
"""

from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MANIFEST = ROOT / "data/vv1_parentage_feature.json"
EXPORTER = ROOT / "native/parentage_export/parentage_export.c"
STOCK = ROOT / "research/stock-executables/Virtual Villagers - A New Home.exe"

CONCEPTION_VA = 0x0043BBC0
CALL_SITES = (0x43DD33, 0x43DD54, 0x43DD7B, 0x43DD94, 0x447031, 0x447238)
CAVE_VA = 0x00456900
CAVE_FILE = 0x00056900
STUB_OFFSET = 0x170
STUB_SIZE = 0x10
SLOT_OFFSET = 0x160


def _feature():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["features"][0]


def _cave_payload():
    for patch in _feature()["patches"]:
        if int(patch["offset"], 16) == CAVE_FILE:
            return bytes.fromhex(patch["after"])
    raise AssertionError("the cave patch is missing")


class VV1CapturesTheFatherAtTheCallSitesTests(unittest.TestCase):
    def test_the_exporter_uses_the_capture_kind(self) -> None:
        """FATHER_NOT_RECORDED would short-circuit before the pointer is read."""
        source = EXPORTER.read_text(encoding="utf-8")
        self.assertIn("FATHER_BY_CAPTURE", source)
        self.assertIn(
            "FATHER_BY_CAPTURE, 0, 0, 0x35C,",
            source,
            "VV1's layout row must declare the capture kind",
        )

    def test_the_validator_accepts_the_capture_kind(self) -> None:
        """Its else branch returns 0, which would refuse every VV1 record.

        A layout the validator rejects does not fail loudly -- the feature
        simply never writes a line, which looks exactly like a village with no
        births.
        """
        source = EXPORTER.read_text(encoding="utf-8")
        self.assertIn(
            "|| g->father_kind == FATHER_BY_CAPTURE",
            source,
            "the layout validator must accept FATHER_BY_CAPTURE",
        )

    def test_every_call_site_is_redirected(self) -> None:
        """All six, or some births silently lose their father."""
        if not STOCK.is_file():
            self.skipTest("the exact-build VV1 executable is not available")
        blob = STOCK.read_bytes()
        patches = {int(p["offset"], 16): p for p in _feature()["patches"]}
        for va in CALL_SITES:
            file_off = va - 0x400000
            with self.subTest(site=hex(va)):
                self.assertIn(
                    file_off, patches, "call site is not redirected"
                )
                patch = patches[file_off]
                before = bytes.fromhex(patch["before"])
                self.assertEqual(
                    blob[file_off : file_off + len(before)],
                    before,
                    "the guard does not match the stock bytes",
                )
                self.assertEqual(
                    len(bytes.fromhex(patch["after"])),
                    len(before),
                    "the redirect changed width, so code after it shifts",
                )

    def test_each_redirect_lands_on_its_own_stub(self) -> None:
        """An off-by-one here still assembles and still runs."""
        patches = {int(p["offset"], 16): p for p in _feature()["patches"]}
        for index, va in enumerate(CALL_SITES):
            after = bytes.fromhex(patches[va - 0x400000]["after"])
            with self.subTest(site=hex(va)):
                self.assertEqual(after[0], 0xE8, "not a near call")
                rel = struct.unpack_from("<i", after, 1)[0]
                self.assertEqual(
                    va + 5 + rel,
                    CAVE_VA + STUB_OFFSET + index * STUB_SIZE,
                    "the redirect does not land on this site's stub",
                )

    def test_each_stub_returns_to_the_conception_routine(self) -> None:
        """A stub that does not reach sub_43BBC0 breaks conception itself."""
        payload = _cave_payload()
        for index in range(len(CALL_SITES)):
            start = STUB_OFFSET + index * STUB_SIZE
            stub = payload[start : start + STUB_SIZE]
            with self.subTest(stub=index):
                self.assertIn(0xE9, stub, "no jump back")
                j = stub.index(0xE9)
                rel = struct.unpack_from("<i", stub, j + 1)[0]
                site = CAVE_VA + start + j
                self.assertEqual(
                    site + 5 + rel,
                    CONCEPTION_VA,
                    "the stub does not tail-call the conception routine",
                )

    def test_every_stub_writes_the_same_slot(self) -> None:
        """Six stubs, one slot -- a stray address would capture nothing."""
        payload = _cave_payload()
        slot_va = CAVE_VA + SLOT_OFFSET
        packed = struct.pack("<I", slot_va)
        for index in range(len(CALL_SITES)):
            start = STUB_OFFSET + index * STUB_SIZE
            stub = payload[start : start + STUB_SIZE]
            with self.subTest(stub=index):
                self.assertIn(
                    packed, stub, "this stub does not write the capture slot"
                )

    def test_each_stub_captures_the_register_its_site_uses(self) -> None:
        """Derived from the executable, not from the build script's own table.

        This is the mutation that survives every other guard: a stub naming the
        wrong register still assembles, still lands correctly, still tail-calls
        the routine, and still writes the slot. It just stores something that
        is not the father, and the log fills with a stranger's name.

        The father's register at each site is whatever the stock code loads
        +0x36C from, because that load is the game reading his appearance
        variant off his own record. So the check reads the nearest such load
        before each call and requires the stub to capture the same register.
        """
        if not STOCK.is_file():
            self.skipTest("the exact-build VV1 executable is not available")
        blob = STOCK.read_bytes()
        payload = _cave_payload()
        slot_va = CAVE_VA + SLOT_OFFSET

        # mov r32,[r32+disp32] is 8B /r with mod=10; rm is the base register.
        # The short forms that store eax use opcode A3 and encode no register.
        store_modrm = {
            0: 0xA3,   # eax -- special-cased below
            1: 0x0D,   # ecx
            2: 0x15,   # edx
            3: 0x1D,   # ebx
            5: 0x2D,   # ebp
            6: 0x35,   # esi
            7: 0x3D,   # edi
        }

        for index, va in enumerate(CALL_SITES):
            with self.subTest(site=hex(va)):
                call_off = va - 0x400000
                window = blob[call_off - 96 : call_off]
                base = None
                for i in range(len(window) - 6):
                    if (
                        window[i] == 0x8B
                        and (window[i + 1] >> 6) == 2
                        and (window[i + 1] & 7) != 4
                        and window[i + 2 : i + 6] == b"\x6c\x03\x00\x00"
                    ):
                        base = window[i + 1] & 7
                self.assertIsNotNone(
                    base, "no +0x36C load before this call site"
                )

                start = STUB_OFFSET + index * STUB_SIZE
                stub = payload[start : start + STUB_SIZE]
                if base == 0:
                    expected = b"\xa3" + struct.pack("<I", slot_va)
                else:
                    expected = (
                        b"\x89"
                        + bytes([store_modrm[base]])
                        + struct.pack("<I", slot_va)
                    )
                self.assertTrue(
                    stub.startswith(expected),
                    "stub %d captures the wrong register: the site loads the "
                    "father from register %d, so the stub must store that one"
                    % (index, base),
                )

    def test_the_slot_is_cleared_after_it_is_read(self) -> None:
        """Otherwise a birth with no capture inherits the last father.

        That is the failure mode worth a guard of its own: it does not crash
        and it does not look wrong, it just attributes a child to whoever
        conceived previously. A wrong parent cannot be corrected later, because
        parentage is not recoverable from the child.
        """
        payload = _cave_payload()
        slot_va = CAVE_VA + SLOT_OFFSET
        # mov dword ptr [slot], 0  ==  C7 05 <slot> 00000000
        clear = b"\xc7\x05" + struct.pack("<I", slot_va) + b"\x00\x00\x00\x00"
        self.assertEqual(
            payload.count(clear),
            3,
            "each of the three trampolines must clear the slot after reading it",
        )

    def test_the_slot_starts_empty(self) -> None:
        """A non-zero initial value would be a father before any conception."""
        payload = _cave_payload()
        self.assertEqual(
            payload[SLOT_OFFSET : SLOT_OFFSET + 4],
            b"\x00\x00\x00\x00",
            "the capture slot must start empty",
        )

    def test_the_composed_payload_does_not_overlap_origins(self) -> None:
        """The composed cave moved twice; both earlier addresses were occupied.

        This compares against the Origins manifest, which is the overlap the
        renderer itself would reject. It is NOT a substitute for measuring free
        space against a real render -- Birth Control reserves the whole page
        through a generated payload that no manifest shows.
        """
        origins = ROOT / "data/vv1_origins_feature.json"
        if not origins.is_file():
            self.skipTest("the Origins manifest is not available")
        spans = []

        def walk(node):
            if isinstance(node, dict):
                off, after = node.get("offset"), node.get("after")
                if isinstance(off, str) and isinstance(after, str):
                    try:
                        spans.append((int(off, 16), len(after) // 2))
                    except ValueError:
                        pass
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(json.loads(origins.read_text(encoding="utf-8")))
        composed = _feature()["composition_patches"][
            "vv1_enable_origins_exclusive_features"
        ]
        for patch in composed:
            start = int(patch["offset"], 16)
            length = len(bytes.fromhex(patch["after"]))
            for other_start, other_length in spans:
                overlaps = (
                    start < other_start + other_length
                    and other_start < start + length
                )
                self.assertFalse(
                    overlaps,
                    "composed parentage at %#x+%#x overlaps Origins at %#x+%#x"
                    % (start, length, other_start, other_length),
                )


if __name__ == "__main__":
    unittest.main()
