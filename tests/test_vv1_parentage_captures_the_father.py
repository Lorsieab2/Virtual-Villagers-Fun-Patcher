"""VV1 finds the father in the conception routine's caller.

VV1 stores nothing about the father in the mother's record, so unlike VV2-VV5
there is nothing to read at the success tails. His record exists only in the
frame of whichever of the six callers of sub_43BBC0 is conceiving, where the
game loads one field off it (+0x36C) and passes that value on.

The success-tail trampolines therefore call one shared body that identifies
the caller by the return address at the routine's entry esp and reads him from
where that caller keeps him -- a stack slot, EBP, or (in the two pairing scans)
whichever of the scan's two villagers the caller's own gender branch did not
make the mother. Nothing at the call sites is patched: an earlier design that
carried him in an argument it thought unread wrote a pointer into the mother's
+0x394 and lost him on three paths. See test_vv1_father_argument_slot.py for
why no argument is free, and test_vv1_parentage_conception_emulation.py for
every path executed end to end.

These guards pin what would fail silently: a caller missing from the table, a
table naming the wrong return address, or a trampoline that stops calling the
body or stops replaying what it displaced.
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
CAVES = {"standalone": (0x00456900, 0x00056900), "composed": (0x00490E00, 0x0008EE00)}
SLOT = 0x20
LOG_OFFSET = 0x60
TAIL_REJOINS = {0: 0x43BCA8, 1: 0x43BCC0}
EPILOGUE = 0x43BCC6
REPLAY = bytes.fromhex("8bbf10e00300")  # mov edi,[edi+0x3E010]


def _feature():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["features"][0]


def _payloads():
    feature = _feature()
    for label, patches in (
        ("standalone", feature["patches"]),
        ("composed", feature["composition_patches"]["vv1_enable_origins_exclusive_features"]),
    ):
        cave_va, cave_file = CAVES[label]
        for patch in patches:
            if int(patch["offset"], 16) == cave_file:
                yield label, cave_va, bytes.fromhex(patch["after"])
                break
        else:
            raise AssertionError("the %s cave patch is missing" % label)


def _stock_callers():
    """Every direct call into sub_43BBC0 in the stock executable."""
    blob = STOCK.read_bytes()
    found = []
    for at in range(0x1000, 0x57000 - 5):
        if blob[at] == 0xE8:
            va = at + 0x400000
            if va + 5 + struct.unpack_from("<i", blob, at + 1)[0] == CONCEPTION_VA:
                found.append(va)
    return found


class VV1FindsTheFatherInTheCallerTests(unittest.TestCase):
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
        """Its else branch returns 0, which would refuse every VV1 record."""
        source = EXPORTER.read_text(encoding="utf-8")
        self.assertIn(
            "|| g->father_kind == FATHER_BY_CAPTURE",
            source,
            "the layout validator must accept FATHER_BY_CAPTURE",
        )

    def test_the_body_knows_exactly_the_stock_callers(self) -> None:
        """Derived from the executable, not from the build script's table.

        A caller missing from the body's comparisons logs every conception it
        makes as "(not captured for this birth)"; a comparison against an
        address that is not a return from sub_43BBC0 never matches anything.
        """
        if not STOCK.is_file():
            self.skipTest("the exact-build VV1 executable is not available")
        import capstone

        callers = _stock_callers()
        self.assertEqual(len(callers), 6, [hex(c) for c in callers])
        returns = {va + 5 for va in callers}
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for label, cave_va, payload in _payloads():
            body = payload[LOG_OFFSET:0x120]
            compared = set()
            for insn in md.disasm(body, cave_va + LOG_OFFSET):
                if insn.mnemonic == "ret":
                    break
                if insn.mnemonic == "cmp" and insn.op_str.startswith("ecx, 0x"):
                    compared.add(int(insn.op_str.split(", ")[1], 16))
            with self.subTest(layout=label):
                self.assertEqual(compared, returns)

    def test_every_trampoline_calls_the_body_inside_pushad(self) -> None:
        """pushad; call body; popad; then replay-and-rejoin, or the epilogue."""
        for label, cave_va, payload in _payloads():
            body_va = cave_va + LOG_OFFSET
            for index in range(3):
                code = payload[index * SLOT : (index + 1) * SLOT]
                slot_va = cave_va + index * SLOT
                with self.subTest(layout=label, trampoline=index):
                    self.assertEqual(code[0], 0x60, "no pushad")
                    self.assertEqual(code[1], 0xE8, "no call to the body")
                    rel = struct.unpack_from("<i", code, 2)[0]
                    self.assertEqual(slot_va + 6 + rel, body_va)
                    self.assertEqual(code[6], 0x61, "no popad after the call")
                    if index in TAIL_REJOINS:
                        self.assertEqual(code[7:13], REPLAY,
                                         "the displaced instruction is not replayed")
                        jmp_at = 13
                        want = TAIL_REJOINS[index]
                    else:
                        jmp_at = 7
                        want = EPILOGUE
                    self.assertEqual(code[jmp_at], 0xE9)
                    rel = struct.unpack_from("<i", code, jmp_at + 1)[0]
                    self.assertEqual(slot_va + jmp_at + 5 + rel, want)

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
