"""A second Island Event purchase must be refused; a first must go through.

VV3's purchased Island Event is queued a few seconds out so its popup does not
fire inside the paused, modal Tech menu. That delay opens a window in which the
player can buy the row again: the original guard tested the village's
next-event field against **zero**, documented as "queued by zeroing its
countdown" -- true of an older mechanism that had been replaced by a TIMESTAMP.
A pending event leaves that field non-zero, so the guard passed the second
purchase through, deducting another 30,000 tech points and merely overwriting
the same timer, still producing exactly one event.

The first repair inferred pending-ness from that timestamp: load
`[world + 0x12EF4]`, subtract `clock()`, and treat "inside the delay window" as
pending. Codex found three P1 defects in it on #249, all from the same mistake
of *inferring* state instead of *recording* it:

  * the not-pending branch fell straight into the refusal, so EVERY Island
    Event purchase was refused and no path could reach the deduction at all;
  * the stamp was held in `edx` across a call to `0x403330`, which clobbers
    `eax/ecx/edx`, so the subtraction read scratch;
  * an overdue-but-unconsumed event -- the player reopens the paused Tech menu
    during the delay and leaves it open, so the handler never runs -- underflows
    the unsigned compare and reads as not pending, re-opening the double charge.

The guard now uses a DEDICATED flag, mirroring the Barrel's long-standing
`BARREL_PENDING_FLAG_VA`: set when the purchase arms the queue, cleared by the
island-event handler once it has actually consumed it.

Codex then found a FOURTH P1 in that repair. The handler cleared the flag with
an unconditional store, and the handler runs every gameplay frame -- so the very
first frame after the purchase menu closed retired the flag while the event was
still queued for `QUEUE_DELAY_SECONDS`, and a second purchase inside that window
was charged again. Reaching the hook proves the *menu has closed*; it does not
prove the *event has been consumed*, which is what the flag has to mean. The
release is therefore gated on a due stamp recorded when the queue is armed.

These tests assert OUTCOMES against the emitted bytes -- which branch reaches
the deduction and which reaches the refusal -- because the previous suite here
asserted the mechanism (`cmp edx, 5`, a `ja` exists) and passed green while the
guard refused every purchase in the game.
"""

import json
import re
import unittest
from pathlib import Path

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"
BUILDER = ROOT / "scripts" / "build_vv3_origins_feature.py"

# The tech-point balance the purchase deducts from.
TECH_BALANCE_VA = 0x582644
# The DLL result code the refusal path shows.
ALREADY_QUEUED_RESULT = 10


def _constant(name: str) -> int:
    """A hex constant from the builder, so the test cannot drift from it."""
    text = BUILDER.read_text(encoding="utf-8")
    match = re.search(rf"^{name} = (0x[0-9A-Fa-f]+)", text, re.M)
    if not match:
        raise AssertionError(f"{name} not found in the builder")
    return int(match.group(1), 16)


FLAG_VA = _constant("SECTION_DATA_VA") + 0x50
# The epoch second at which the queued event becomes due. The release compares
# the clock against this before retiring the flag.
DUE_VA = _constant("SECTION_DATA_VA") + 0x54

# Byte-sized absolute forms, which is how the assembler encodes these.
GUARD_TEST = bytes([0x80, 0x3D]) + FLAG_VA.to_bytes(4, "little") + bytes([0x00])
FLAG_ARM = bytes([0xC6, 0x05]) + FLAG_VA.to_bytes(4, "little") + bytes([0x01])
FLAG_CLEAR = bytes([0xC6, 0x05]) + FLAG_VA.to_bytes(4, "little") + bytes([0x00])
DEDUCT = bytes([0x29, 0x05]) + TECH_BALANCE_VA.to_bytes(4, "little")
# `cmp eax, dword ptr [DUE_VA]` -- the release gate.
DUE_COMPARE = bytes([0x3B, 0x05]) + DUE_VA.to_bytes(4, "little")
# `mov dword ptr [DUE_VA], eax` -- recorded when the queue is armed.
DUE_RECORD = bytes([0xA3]) + DUE_VA.to_bytes(4, "little")

# The old timestamp reads, both of which are defects if they come back.
OLD_ZERO_TEST = bytes.fromhex("83BC2FF42E010000")
OLD_STAMP_LOAD = bytes.fromhex("8B942FF42E0100")


def _payload_variants() -> dict[str, bytes]:
    """The emitted bytes, keyed by BUILD VARIANT.

    VV3 emits one appended layout per patch mode, and each carries its own
    complete copy of the menu code. Concatenating them and counting sites
    across the whole blob double-counts every instruction -- the first version
    of this file did exactly that and reported two arm sites for what is one
    site per build. Each variant has to satisfy the invariants on its own.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    shared = []
    for patch in manifest.get("patches", []):
        after = patch.get("after")
        if after:
            shared.append(bytes.fromhex(after))
    common = b"".join(shared)

    variants = {}
    layouts = manifest.get("pe_append_transaction", {}).get("layouts", {})
    for name, layout in layouts.items():
        payload = layout.get("append_bytes")
        if payload:
            variants[name] = common + bytes.fromhex(payload)
    return variants


def _payload_bytes() -> bytes:
    """One representative variant, for the ordering assertions."""
    variants = _payload_variants()
    return next(iter(variants.values())) if variants else b""


class VV3IslandEventDoubleChargeTests(unittest.TestCase):
    def setUp(self):
        self.payload = _payload_bytes()
        self.assertTrue(self.payload, "no VV3 patch bodies found")

    def test_the_old_zero_test_is_gone(self):
        """The original regression, pinned by encoding.

        `cmp dword ptr [edi + ebp + 0x12EF4], 0`. Its presence means a pending
        event -- which leaves that field non-zero -- would once again pass the
        charge through.
        """
        self.assertNotIn(
            OLD_ZERO_TEST,
            self.payload,
            "the Island Event charge guard tests its queue field against zero "
            "again. A pending event stores a FUTURE TIMESTAMP there, so that "
            "test passes while an event is queued and a second purchase is "
            "charged in full for no extra event",
        )

    def test_the_guard_does_not_infer_pending_from_the_timestamp(self):
        """The second regression: inferring state instead of recording it.

        All three P1s came from reading `[world + 0x12EF4]` in the guard.
        Reading it there at all is the defect, so the absence of that load is
        what this pins.
        """
        self.assertNotIn(
            OLD_STAMP_LOAD,
            self.payload,
            "the charge guard loads the next-island-event timestamp again. "
            "That field is written by natural events too, and being past it "
            "does not mean the event was CONSUMED -- the handler only runs "
            "during village gameplay, so an event armed and then left overdue "
            "in the paused Tech menu is still outstanding. Use the dedicated "
            "pending flag instead",
        )

    def test_the_flag_is_tested_set_and_cleared_the_expected_number_of_times(self):
        """A flag nothing sets, or nothing clears, is worse than no flag.

        Without the arm the guard never fires and the double charge returns.
        Without the clear the flag latches on the first purchase and refuses
        Island Event for the rest of the save.

        The arm and the clear are each unique: exactly one place records that an
        event is outstanding, and exactly one place retires it.

        The flag is TESTED twice, and both are load-bearing:

          * the purchase guard, which refuses a second buy, and
          * the release helper, which early-outs when nothing is queued so the
            every-frame path costs one compare instead of a clock call.

        Pinning the test count at one would forbid that early-out, so the counts
        are asserted per site rather than as one number for all three.
        """
        variants = _payload_variants()
        self.assertTrue(variants, "no VV3 build variants found")
        for variant, payload in sorted(variants.items()):
            for name, encoding, expected in (
                ("guard test", GUARD_TEST, 2),
                ("arm (set to 1)", FLAG_ARM, 1),
                ("consume (clear to 0)", FLAG_CLEAR, 1),
            ):
                with self.subTest(variant=variant, site=name):
                    self.assertEqual(
                        payload.count(encoding),
                        expected,
                        f"the {variant} build has "
                        f"{payload.count(encoding)} {name} sites for the "
                        f"island pending flag at 0x{FLAG_VA:X}, "
                        f"expected {expected}",
                    )

    def test_the_release_is_gated_on_the_due_time(self):
        """Codex's fourth P1: closing the menu is not consuming the event.

        The release runs in the island-event handler, which fires every
        gameplay frame. An unconditional store there retires the flag on the
        FIRST frame after the purchase menu closes -- while the event is still
        queued for the delay -- so a second purchase inside that window is
        charged again, which is the original double charge.

        Arming must record the due stamp, and the release must compare against
        it. Both sites are required in every build variant.
        """
        variants = _payload_variants()
        self.assertTrue(variants, "no VV3 build variants found")
        for variant, payload in sorted(variants.items()):
            with self.subTest(variant=variant, site="record due stamp"):
                self.assertIn(
                    DUE_RECORD,
                    payload,
                    f"the {variant} build never records the island event's due "
                    f"time at 0x{DUE_VA:X}, so the release has nothing to "
                    "compare against and can only clear unconditionally",
                )
            with self.subTest(variant=variant, site="compare due stamp"):
                self.assertIn(
                    DUE_COMPARE,
                    payload,
                    f"the {variant} build clears the island pending flag "
                    "without comparing the clock against the due time, so the "
                    "first frame after the menu closes retires a still-queued "
                    "event and the second purchase is charged again",
                )

    @unittest.skipIf(capstone is None, "requires capstone")
    def test_the_clear_is_dominated_by_the_due_compare(self):
        """The gate must actually precede the clear on the path that reaches it.

        Both instructions existing somewhere is not enough -- a compare that
        sits after the store, or in an unrelated routine, would satisfy a
        presence check while leaving the defect in place. This walks backwards
        from each clear and requires the compare, with a conditional branch,
        in the instructions immediately before it.
        """
        variants = _payload_variants()
        self.assertTrue(variants, "no VV3 build variants found")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for variant, payload in sorted(variants.items()):
            with self.subTest(variant=variant):
                site = payload.find(FLAG_CLEAR)
                self.assertGreater(
                    site, 0, "no island pending-flag clear in this build"
                )
                start = max(0, site - 48)
                window = list(md.disasm(payload[start:site], start))
                text = " ; ".join(
                    f"{i.mnemonic} {i.op_str}" for i in window
                )
                self.assertTrue(
                    any(
                        i.mnemonic == "cmp"
                        and f"0x{DUE_VA:x}" in i.op_str
                        for i in window
                    ),
                    "the clear is not preceded by a comparison against the due "
                    f"time at 0x{DUE_VA:X}: {text}",
                )
                self.assertTrue(
                    any(
                        i.mnemonic in ("jb", "jbe", "jae", "ja")
                        for i in window
                    ),
                    "the due comparison has no unsigned branch, so its result "
                    f"cannot skip the clear: {text}",
                )

    @unittest.skipIf(capstone is None, "requires capstone")
    def test_a_non_pending_purchase_reaches_the_deduction(self):
        """The defect that would have shipped: every purchase refused.

        The first repair's not-pending branch fell straight into
        `mov eax, 10; jmp show_result`, identical to the pending path, so no
        Island Event purchase could ever succeed. The whole previous test file
        passed against that build, because it never asked where the
        not-pending path GOES.
        """
        index = self.payload.find(GUARD_TEST)
        self.assertGreater(index, 0, "guard not found")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        decoded = list(md.disasm(self.payload[index : index + 0x40], 0))
        self.assertGreaterEqual(len(decoded), 2, "guard did not decode")

        branch = decoded[1]
        self.assertEqual(
            branch.mnemonic,
            "je",
            "the guard's test is not followed by an equal-branch, so the "
            f"not-pending case has no path of its own: {branch.mnemonic}",
        )
        target = int(branch.op_str, 16)
        landing = self.payload[index + target : index + target + len(DEDUCT)]
        self.assertEqual(
            landing,
            DEDUCT,
            "the not-pending branch does not land on the tech-point "
            f"deduction at 0x{TECH_BALANCE_VA:X}. Every Island Event purchase "
            "is refused, which is exactly the defect this guard shipped once "
            "already",
        )

    @unittest.skipIf(capstone is None, "requires capstone")
    def test_a_pending_purchase_reaches_the_refusal(self):
        """The other half: while one is outstanding, refuse."""
        index = self.payload.find(GUARD_TEST)
        self.assertGreater(index, 0, "guard not found")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        decoded = list(md.disasm(self.payload[index : index + 0x40], 0))
        fallthrough = decoded[2]
        self.assertEqual(
            (fallthrough.mnemonic, fallthrough.op_str),
            ("mov", f"eax, 0x{ALREADY_QUEUED_RESULT:x}"),
            "the pending path does not load the already-queued result code, "
            f"so no refusal is shown: {fallthrough.mnemonic} "
            f"{fallthrough.op_str}",
        )

    def test_the_refusal_precedes_the_deduction(self):
        """Refusing after charging would still take the player's points."""
        guard = self.payload.find(GUARD_TEST)
        self.assertGreater(guard, 0, "guard not found")
        charge = self.payload.find(DEDUCT, guard)
        self.assertGreater(
            charge,
            guard,
            "the tech-point deduction does not follow the guard, so a refused "
            "second purchase could still be charged",
        )

    def test_the_guard_needs_no_clock_call(self):
        """Register-clobber safety, structurally.

        The second P1 was a stamp held in caller-saved `edx` across
        `0x403330`, which clobbers `eax/ecx/edx`. A guard that makes no call
        cannot have that class of bug, so assert the absence of the call rather
        than trying to prove a save/restore is correct.
        """
        index = self.payload.find(GUARD_TEST)
        self.assertGreater(index, 0, "guard not found")
        window = self.payload[index : index + 0x10]
        self.assertNotIn(
            bytes([0xE8]),
            window,
            "the charge guard makes a call again. The queue clock clobbers "
            "eax/ecx/edx, which silently corrupted the previous version's "
            "comparison",
        )


if __name__ == "__main__":
    unittest.main()
