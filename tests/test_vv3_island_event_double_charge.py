"""A second Island Event purchase must be refused while one is still queued.

VV3's Island Event is queued a few seconds out rather than fired immediately.
The charge guard originally tested the village's next-event field against
**zero**, documented as "queued by zeroing its countdown" -- true of an older
mechanism that the timestamp replaced. Because a pending event leaves that
field NON-zero, the guard let the purchase through: buying Island Event again
inside the window deducted another 30,000 tech points and merely overwrote the
same timer, still producing exactly one event.

The first repair replaced the zero test with a timestamp comparison, which
Codex found defective in three ways (PR #249):

  1. **Every purchase was refused.** Both the pending and not-pending branches
     jumped to the refusal, so the deduction and queueing code was unreachable
     for the Island Event row.
  2. **The stamp did not survive the clock call.** It was held in ``edx``,
     which is caller-saved; VV3's clock at 0x403330 writes ``eax``, ``ecx`` and
     ``edx`` (``mov edx, [esp+4]`` at 0x403341), so ``sub edx, eax`` consumed
     callee scratch rather than the loaded stamp.
  3. **An elapsed deadline was treated as consumption.** If the delay passed
     before the handler consumed the queue -- the player reopens the paused
     Tech menu during the window and leaves it open -- ``stamp - now``
     underflowed as unsigned and the still-queued event read as not pending.

Pending is therefore tracked by a dedicated flag, set when the event is armed
and cleared only where the event is actually presented, exactly as the barrel's
pending flag already worked.

These tests assert the OUTCOME -- a queued event reaches the refusal, an
unqueued one reaches the deduction, and the flag is both set and cleared --
rather than which helper computes it. The previous revision of this file pinned
the timestamp encoding, and pinning a mechanism is how a guard ends up passing
while the bug it names is present.
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
# Dedicated "a purchased island event is queued and not yet consumed" flag.
ISLAND_PENDING_FLAG = 0x4B3C76
# The tech-point pool the purchase deducts from.
TECH_POINT_POOL = 0x582644
# The DLL result code the refusal path shows.
ALREADY_QUEUED_RESULT = 10


def _blobs():
    """Every emitted patch body and appended layout, as (name, bytes)."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = []
    for i, patch in enumerate(manifest.get("patches", [])):
        after = patch.get("after")
        if after:
            out.append(("patches/%d" % i, bytes.fromhex(after)))
    layouts = manifest.get("pe_append_transaction", {}).get("layouts", {})
    for name, layout in layouts.items():
        payload = layout.get("append_bytes")
        if payload:
            out.append(("layout/%s" % name, bytes.fromhex(payload)))
    return out


def _purchase_guard_sites(blob):
    """Yield only the PURCHASE guard's flag test, not the handler's.

    The pending flag is read in two places and they must not be conflated:

      * the purchase guard, which refuses a second buy and sits immediately
        before the tech-point deduction, and
      * the island-event handler hook, which clears the flag once the event has
        been presented and has no deduction anywhere near it.

    A test that treats every flag test as the purchase guard fails on the
    handler for the wrong reason. The deduction is what distinguishes them, so
    a site only counts as the purchase guard when the deduction follows it.
    """
    deduct = bytes.fromhex("2905") + TECH_POINT_POOL.to_bytes(4, "little")
    for start, ins in _decode_at(blob, ISLAND_PENDING_FLAG):
        if ins.mnemonic != "cmp":
            continue
        if blob.find(deduct, start, start + 0x40) < 0:
            continue
        yield start, ins


def _decode_at(blob, addr):
    """Decode each instruction that REFERENCES addr, aligned to its start.

    The address bytes sit in the middle of the encoding, so disassembling from
    the match offset yields garbage. Back up until an instruction decodes that
    actually names the address.
    """
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    needle = addr.to_bytes(4, "little")
    pos = 0
    while True:
        m = blob.find(needle, pos)
        if m < 0:
            return
        pos = m + 1
        for back in range(2, 10):
            start = m - back
            if start < 0:
                continue
            ins = next(md.disasm(blob[start:start + 16], start), None)
            if ins is not None and ("0x%x" % addr) in ins.op_str:
                yield start, ins
                break


class VV3IslandEventDoubleChargeTests(unittest.TestCase):
    def setUp(self):
        self.blobs = _blobs()
        self.assertTrue(self.blobs, "no VV3 patch bodies found")
        self.payload = b"".join(b for _, b in self.blobs)

    def test_the_old_zero_test_is_gone(self):
        """The original regression, pinned by encoding.

        ``cmp dword ptr [edi + ebp + 0x12EF4], 0`` is the old test. Its
        presence means a pending event -- which leaves that field non-zero --
        would once again pass the charge through.
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

    def test_no_stamp_arithmetic_survives_a_call(self):
        """Codex finding 2: a caller-saved register cannot hold a value across
        a call.

        VV3's clock at 0x403330 writes eax, ecx and edx, so subtracting into
        edx immediately after any call consumes callee scratch. This scans
        EVERY blob rather than only ones mentioning the guard: a build with the
        defect has no pending flag at all, so gating the scan on the flag would
        make this check vacuously pass exactly where it must fail.
        """
        if capstone is None:
            self.skipTest("requires capstone")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        offenders = []
        for name, blob in self.blobs:
            last_call = None
            for ins in md.disasm(blob, 0):
                if ins.mnemonic == "call":
                    last_call = ins.address
                if (
                    ins.mnemonic == "sub"
                    and ins.op_str.replace(" ", "") == "edx,eax"
                    and last_call is not None
                    and 0 <= ins.address - last_call < 32
                ):
                    offenders.append(
                        "%s+%#x (call at +%#x)" % (name, ins.address, last_call)
                    )
        self.assertFalse(
            offenders,
            "a queue value is computed into edx right after a call, but the "
            "clock clobbers eax/ecx/edx, so the comparison uses callee "
            "scratch: %s" % (offenders,),
        )

    def test_the_pending_flag_is_both_set_and_cleared(self):
        """Codex finding 3: pending must mean queued AND not yet consumed.

        A flag that is set but never cleared blocks every future purchase; a
        flag that is never set never refuses anything. Both sites must exist.
        """
        if capstone is None:
            self.skipTest("requires capstone")
        sets, clears = [], []
        for name, blob in self.blobs:
            for _, ins in _decode_at(blob, ISLAND_PENDING_FLAG):
                text = "%s %s" % (ins.mnemonic, ins.op_str)
                if ins.mnemonic == "mov" and text.rstrip().endswith(", 1"):
                    sets.append(name)
                elif ins.mnemonic == "mov" and text.rstrip().endswith(", 0"):
                    clears.append(name)
        self.assertTrue(
            sets,
            "nothing ever sets the island pending flag, so a queued event is "
            "never recognised and the second purchase is charged again",
        )
        self.assertTrue(
            clears,
            "nothing ever clears the island pending flag, so once one event "
            "is bought every later Island Event purchase is refused forever",
        )

    def test_the_unqueued_path_reaches_the_deduction(self):
        """Codex finding 1: the not-pending branch must not refuse.

        The defect made both branches jump to the refusal, so no purchase could
        ever be charged or queued. Require that the guard's not-taken edge
        reaches the tech-point deduction rather than the result code.
        """
        if capstone is None:
            self.skipTest("requires capstone")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        checked = 0
        for name, blob in self.blobs:
            for start, ins in _purchase_guard_sites(blob):
                window = list(md.disasm(blob[start:start + 0x40], start))
                text = " ; ".join(
                    "%s %s" % (i.mnemonic, i.op_str) for i in window
                )
                branch = next(
                    (i for i in window if i.mnemonic in ("je", "jz")), None
                )
                self.assertIsNotNone(
                    branch,
                    "the pending test in %s has no conditional branch: %s"
                    % (name, text),
                )
                target = int(branch.op_str, 16)
                tail = list(md.disasm(blob[target:target + 0x20], target))
                tail_text = " ; ".join(
                    "%s %s" % (i.mnemonic, i.op_str) for i in tail
                )
                self.assertIn(
                    "0x%x" % TECH_POINT_POOL,
                    tail_text,
                    "the not-pending branch does not reach the tech-point "
                    "deduction, so every Island Event purchase is refused and "
                    "the queueing code is unreachable: %s" % tail_text,
                )
                checked += 1
        self.assertGreater(
            checked, 0, "no island pending-flag test found in any patch body"
        )

    def test_the_refusal_precedes_the_deduction(self):
        """Refusing after charging would still take the player's points."""
        if capstone is None:
            self.skipTest("requires capstone")
        deduct = bytes.fromhex("2905") + TECH_POINT_POOL.to_bytes(4, "little")
        checked = 0
        for name, blob in self.blobs:
            for start, ins in _purchase_guard_sites(blob):
                charge = blob.find(deduct, start)
                self.assertGreater(
                    charge,
                    start,
                    "the tech-point deduction does not follow the guard in "
                    "%s, so a refused second purchase could still be charged"
                    % name,
                )
                checked += 1
        self.assertGreater(checked, 0, "no island pending-flag test found")

    def test_the_refusal_uses_the_already_queued_result(self):
        """The pending path must surface the refusal, not fail silently."""
        if capstone is None:
            self.skipTest("requires capstone")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        seen = False
        for name, blob in self.blobs:
            for start, ins in _purchase_guard_sites(blob):
                window = list(md.disasm(blob[start:start + 0x40], start))
                if any(
                    i.mnemonic == "mov"
                    and i.op_str.startswith("eax, ")
                    and i.op_str.endswith("0x%x" % ALREADY_QUEUED_RESULT)
                    for i in window
                ):
                    seen = True
        self.assertTrue(
            seen,
            "the pending path never sets the already-queued result code, so "
            "the refusal is never shown to the player",
        )


if __name__ == "__main__":
    unittest.main()
