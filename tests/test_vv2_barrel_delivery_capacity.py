"""VV2's cued Barrel of Babies must recheck capacity when it is delivered.

Capacity is gated when the row is bought, but the event is only dispatched
`BARREL_CUE_FRAMES` later.  A pregnancy or another event taking a slot inside
that window left the stock per-child allocation stopping after one or two
children while the player had paid the full 75,000.

The player object needs no pointer captured at purchase: the splice at
0x42E9EE is immediately preceded by `mov edi, dword ptr [esi + 0x10]`, and EDI
is untouched until the helper's own resume.

`GateVV2Barrel` cannot be reused directly -- it shows the "close to maximum"
notice when it refuses, and a held barrel retries every cue period -- so the
companion DLL exports `GateVV2BarrelSilent`, the same arithmetic without the
dialog.  Both call one shared `vv2_barrel_has_room`.
"""

import json
import unittest
from pathlib import Path

try:
    import capstone
except ImportError:  # pragma: no cover
    capstone = None

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv2_origins_feature.json"
COMPANION = ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c"
EXPORTS = ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.def"

SHR_VA, SHR_RAW = 0x49C000, 0x9A000
SILENT_GATE = 0x9A4A0
DELIVERY_GATE = 0x9A745
MAIN_HELPER = 0x9A780
CUE_COUNTER_VA = 0x49C708
PENDING_VA = 0x49C700
BARREL_CUE_FRAMES = 90
# Free runs verified zero in the stock image and unclaimed by every vv2
# manifest.  Each ends where the next owned cave begins.
SILENT_GATE_ROOM = 0x50
DELIVERY_GATE_ROOM = 0x3B
MAIN_HELPER_ROOM = 0x80


def _rows():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {int(row["offset"], 0): row for row in manifest["patches"]}


def _disasm(blob, va):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    return list(md.disasm(bytes.fromhex(blob), va))


def _va(offset):
    return SHR_VA + (offset - SHR_RAW)


@unittest.skipIf(capstone is None, "requires capstone")
class VV2BarrelDeliveryCapacityTests(unittest.TestCase):
    def setUp(self):
        self.rows = _rows()
        for offset in (SILENT_GATE, DELIVERY_GATE, MAIN_HELPER):
            self.assertIn(offset, self.rows, f"{offset:#x} is not emitted")
        self.gate = _disasm(self.rows[DELIVERY_GATE]["after"], _va(DELIVERY_GATE))
        self.main = _disasm(self.rows[MAIN_HELPER]["after"], _va(MAIN_HELPER))

    # -- placement ---------------------------------------------------------

    def test_every_cave_fits_the_free_run_it_was_placed_in(self):
        for offset, room in (
            (SILENT_GATE, SILENT_GATE_ROOM),
            (DELIVERY_GATE, DELIVERY_GATE_ROOM),
            (MAIN_HELPER, MAIN_HELPER_ROOM),
        ):
            with self.subTest(offset=hex(offset)):
                self.assertLessEqual(
                    len(self.rows[offset]["after"]) // 2,
                    room,
                    "this cave would run into the next owned block",
                )

    def test_new_caves_do_not_enter_the_village_wide_range(self):
        """0x9A800..0x9AD20 belongs to the co-selectable Village-Wide patch."""
        for offset in (SILENT_GATE, DELIVERY_GATE):
            end = offset + len(self.rows[offset]["after"]) // 2
            self.assertTrue(
                end <= 0x9A800 or offset >= 0x9AD20,
                f"{offset:#x} overlaps vv2_origins_village_wide_upgrades",
            )

    # -- the silent export -------------------------------------------------

    def test_companion_exports_the_silent_gate(self):
        self.assertIn(
            "GateVV2BarrelSilent=_GateVV2BarrelSilent@4",
            EXPORTS.read_text(encoding="utf-8"),
        )

    def test_stub_asks_for_the_silent_export_by_name(self):
        blob = bytes.fromhex(self.rows[SILENT_GATE]["after"])
        self.assertIn(b"GateVV2BarrelSilent\x00", blob)

    def test_both_gates_share_one_capacity_rule(self):
        """Two copies of the arithmetic is how purchase and delivery drift."""
        source = COMPANION.read_text(encoding="utf-8")
        self.assertIn("static int vv2_barrel_has_room(void *pool)", source)
        for entry in ("GateVV2Barrel", "GateVV2BarrelSilent"):
            body = source[source.index(f"__stdcall {entry}(void *pool)") :]
            body = body[: body.index("\n}")]
            self.assertIn("vv2_barrel_has_room(pool)", body, entry)
        silent = source[source.index("__stdcall GateVV2BarrelSilent(void *pool)") :]
        silent = silent[: silent.index("\n}")]
        self.assertNotIn(
            "ShowVV2UpgradeResult",
            silent,
            "the delivery probe must stay silent; it retries every cue period",
        )

    # -- the glue ----------------------------------------------------------

    def test_delivery_gate_calls_the_silent_stub_and_rearms_on_refusal(self):
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self.gate)
        self.assertIn("push edi", text)
        self.assertIn(f"call {hex(_va(SILENT_GATE))}", text)
        rearm = [
            i
            for i in self.gate
            if i.mnemonic == "mov" and hex(CUE_COUNTER_VA) in i.op_str.lower()
        ]
        self.assertEqual(len(rearm), 1, "refusal must re-arm the cue counter")
        self.assertTrue(rearm[0].op_str.rstrip().endswith(hex(BARREL_CUE_FRAMES)))

    def _recheck_call(self):
        """The helper's call into the delivery gate, or a clear failure.

        Written as an explicit assertion rather than a bare `next(...)`: with
        the recheck removed -- the defect these tests exist to catch -- a
        generator expression raises StopIteration, which reads as a broken test
        rather than as the bug being present.
        """
        calls = [
            i
            for i in self.main
            if i.mnemonic == "call" and i.op_str == hex(_va(DELIVERY_GATE))
        ]
        self.assertEqual(
            len(calls),
            1,
            "the main helper does not call the delivery-time capacity recheck",
        )
        return calls[0]

    def test_main_helper_rechecks_before_it_consumes_the_token(self):
        call = self._recheck_call()
        consume = next(
            i
            for i in self.main
            if i.mnemonic == "mov"
            and hex(PENDING_VA) in i.op_str.lower()
            and i.op_str.rstrip().endswith(", 0")
        )
        self.assertLess(
            call.address,
            consume.address,
            "capacity is rechecked after the token was already spent",
        )

    def test_refusal_falls_through_to_the_stock_resume_with_the_token_intact(self):
        call = self._recheck_call()
        branch = next(
            i
            for i in self.main
            if i.address > call.address and i.mnemonic in {"je", "jz"}
        )
        target = int(branch.op_str, 16)
        tail = [i for i in self.main if i.address >= target]
        self.assertTrue(tail, "the refusal branch leaves the helper")
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in tail)
        self.assertTrue(
            text.startswith("mov ecx, edi ; call 0x403200"),
            f"refusal must land on the displaced stock pair, got {text[:60]}",
        )
        self.assertIn("jmp 0x42e9f5", text)
        cleared = [
            i for i in tail if i.mnemonic == "mov" and hex(PENDING_VA) in i.op_str.lower()
        ]
        self.assertEqual(cleared, [], "the refusal path must not spend the token")


if __name__ == "__main__":
    unittest.main()
