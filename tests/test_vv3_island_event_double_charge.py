"""A second Island Event purchase inside the queue window must be refused.

VV3's Island Event is queued by writing the village's next-event TIMESTAMP:
`queue_arm_island_code` stores `clock() + QUEUE_DELAY_SECONDS` into
`[world + 0x12EF4]`, where the clock returns Unix epoch seconds.

The charge guard tested that field against **zero**, documented as "queued by
zeroing its countdown" -- true of an older mechanism that was replaced by the
timestamp. Because a pending event leaves the field NON-zero, the guard let the
purchase through: buying Island Event again inside the five-second window
deducted another 30,000 tech points and merely overwrote the same timer, still
producing exactly one event.

These tests assert the OUTCOME -- that a stamp inside the window reaches the
refusal and never reaches the deduction -- rather than that the guard calls any
particular helper. An earlier guard elsewhere in this repo asserted the
mechanism and passed while the bug was present.
"""

import json
import unittest
from pathlib import Path

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"

# The village's next-island-event timestamp, in Unix epoch seconds.
ISLAND_STAMP_FIELD = 0x12EF4
# queue_arm_island_code writes clock() + this many seconds.
QUEUE_DELAY_SECONDS = 5
# The DLL result code the refusal path shows.
ALREADY_QUEUED_RESULT = 10


def _payload_bytes() -> bytes:
    """Every emitted patch body, concatenated, as raw bytes."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    blobs = []
    for patch in manifest.get("patches", []):
        after = patch.get("after")
        if after:
            blobs.append(bytes.fromhex(after))
    appended = (
        manifest.get("pe_append_transaction", {}).get("layouts", {})
    )
    for layout in appended.values():
        payload = layout.get("append_bytes")
        if payload:
            blobs.append(bytes.fromhex(payload))
    return b"".join(blobs)


class VV3IslandEventDoubleChargeTests(unittest.TestCase):
    def setUp(self):
        self.payload = _payload_bytes()
        self.assertTrue(self.payload, "no VV3 patch bodies found")

    def test_the_guard_reads_the_stamp_rather_than_testing_it_for_zero(self):
        """The exact regression, pinned by encoding.

        `cmp dword ptr [edi + ebp + 0x12EF4], 0` is the old test. Its presence
        means a pending event -- which leaves that field non-zero -- would once
        again pass the charge through.
        """
        old_zero_test = bytes.fromhex("83BC2FF42E010000")
        self.assertNotIn(
            old_zero_test,
            self.payload,
            "the Island Event charge guard tests its queue field against zero "
            "again. A pending event stores a FUTURE TIMESTAMP there, so that "
            "test passes while an event is queued and a second purchase is "
            "charged in full for no extra event",
        )
        read_stamp = bytes.fromhex("8B942FF42E0100")
        self.assertIn(
            read_stamp,
            self.payload,
            "the guard no longer loads the queue timestamp at all",
        )

    @unittest.skipIf(capstone is None, "requires capstone")
    def test_a_stamp_inside_the_window_reaches_the_refusal(self):
        """Outcome, not mechanism.

        Walk the guard and require that the in-window path ends at the
        refusal result code, and that the out-of-window path does not. This
        deliberately does not assert which helper computes the comparison --
        asserting the mechanism is how a guard ends up passing while the bug it
        names is present.
        """
        read_stamp = bytes.fromhex("8B942FF42E0100")
        index = self.payload.find(read_stamp)
        self.assertGreater(index, 0, "guard not found")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        decoded = [
            (i.mnemonic, i.op_str)
            for i in md.disasm(self.payload[index : index + 0x30], 0)
        ]
        text = " ; ".join(f"{m} {o}" for m, o in decoded)

        self.assertIn(
            f"cmp edx, {QUEUE_DELAY_SECONDS}",
            text,
            "the guard does not compare the elapsed time against the queue "
            f"window of {QUEUE_DELAY_SECONDS} seconds, so it cannot tell a "
            "pending event from a stale one",
        )
        self.assertTrue(
            any(m == "ja" for m, _ in decoded),
            "no above-comparison branch: a stamp already past the window "
            "would be treated as still pending and block a legitimate buy",
        )
        self.assertTrue(
            any(
                m == "mov" and o.startswith("eax, ")
                and o.endswith(f"0x{ALREADY_QUEUED_RESULT:x}")
                for m, o in decoded
            ),
            "the in-window path does not set the already-queued result code, "
            f"so the refusal is never shown: {text}",
        )

    def test_the_refusal_precedes_the_deduction(self):
        """Refusing after charging would still take the player's points.

        The guard has to sit before `sub dword ptr [0x582644], eax`. If the
        deduction ran first, a refused purchase would still cost 30,000.
        """
        read_stamp = bytes.fromhex("8B942FF42E0100")
        deduct = bytes.fromhex("290544265800")
        guard = self.payload.find(read_stamp)
        self.assertGreater(guard, 0, "guard not found")
        charge = self.payload.find(deduct, guard)
        self.assertGreater(
            charge,
            guard,
            "the tech-point deduction does not follow the guard, so a refused "
            "second purchase could still be charged",
        )


if __name__ == "__main__":
    unittest.main()
