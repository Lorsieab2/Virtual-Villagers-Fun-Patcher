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
DUE_VA = _constant("SECTION_DATA_VA") + 0x54

# Byte-sized absolute forms, which is how the assembler encodes these.
GUARD_TEST = bytes([0x80, 0x3D]) + FLAG_VA.to_bytes(4, "little") + bytes([0x00])
FLAG_ARM = bytes([0xC6, 0x05]) + FLAG_VA.to_bytes(4, "little") + bytes([0x01])
FLAG_CLEAR = bytes([0xC6, 0x05]) + FLAG_VA.to_bytes(4, "little") + bytes([0x00])
DEDUCT = bytes([0x29, 0x05]) + TECH_BALANCE_VA.to_bytes(4, "little")

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

    def _purchase_guard(self):
        """Offset of the PURCHASE guard, not the handler's pre-check.

        Both read the same flag byte, so find() alone picks whichever the
        assembler happened to place first. The purchase guard is the one
        immediately protecting the tech-point deduction, so walk back from
        that.
        """
        deduct = self.payload.find(DEDUCT)
        self.assertGreater(deduct, 0, "deduction not found")
        index = self.payload.rfind(GUARD_TEST, 0, deduct)
        self.assertGreater(index, 0, "purchase guard not found")
        return index

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

    def test_the_flag_is_tested_set_and_cleared_exactly_once_each(self):
        """A flag nothing sets, or nothing clears, is worse than no flag.

        Without the arm the guard never fires and the double charge returns.
        Without the clear the flag latches on the first purchase and refuses
        Island Event for the rest of the save.
        """
        variants = _payload_variants()
        self.assertTrue(variants, "no VV3 build variants found")
        for variant, payload in sorted(variants.items()):
            # Two reads of the flag are correct: the purchase guard in the
            # Tech menu, and the handler's cheap pre-check before it spends a
            # clock call on the due comparison. Only the WRITES are unique.
            for name, encoding, want in (
                ("guard test", GUARD_TEST, 2),
                ("arm (set to 1)", FLAG_ARM, 1),
                ("consume (clear to 0)", FLAG_CLEAR, 2),
            ):
                with self.subTest(variant=variant, site=name):
                    self.assertEqual(
                        payload.count(encoding),
                        want,
                        f"the {variant} build has "
                        f"{payload.count(encoding)} {name} sites for the "
                        f"island pending flag at 0x{FLAG_VA:X}, expected {want}",
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
        index = self._purchase_guard()
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
        index = self._purchase_guard()
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
        guard = self._purchase_guard()
        charge = self.payload.find(DEDUCT, guard)
        self.assertGreater(
            charge,
            guard,
            "the tech-point deduction does not follow the guard, so a refused "
            "second purchase could still be charged",
        )

    @unittest.skipIf(capstone is None, "requires capstone")
    def test_the_flag_is_not_cleared_before_the_event_is_due(self):
        """The handler runs EVERY frame, so entry is not consumption.

        The first repair cleared the flag on handler entry, reasoning that
        reaching the island-event handler proved gameplay had resumed. True,
        but not sufficient -- Codex caught it on #249: the hook runs every
        gameplay frame, so the very first frame after the Tech menu closed
        cleared the flag while the event was still QUEUE_DELAY_SECONDS away.
        Reopening the menu inside that window then saw a clear flag and allowed
        a second 30,000-point purchase for the same event.

        The clear must therefore be guarded by a due-time comparison, the same
        shape the Barrel has always used. This asserts the guard is REACHED
        before the clear, rather than asserting any particular instruction
        sequence.
        """
        # The RELEASE clear, not the save-slot reset. Both zero the same byte,
        # so a bare find() picks whichever the assembler placed first; the
        # release is the one preceded by the due comparison.
        index = -1
        probe = self.payload.find(FLAG_CLEAR)
        while probe > 0:
            window = self.payload[max(0, probe - 0x18) : probe]
            if bytes([0x3B, 0x05]) + DUE_VA.to_bytes(4, "little") in window:
                index = probe
                break
            probe = self.payload.find(FLAG_CLEAR, probe + 1)
        self.assertGreater(
            index,
            0,
            "no flag clear is preceded by a comparison against the due time, "
            "so the pending flag is released without checking whether the "
            "event has actually come due",
        )
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        window = self.payload[max(0, index - 0x18) : index]
        decoded = list(md.disasm(window, 0))
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in decoded)
        self.assertIn(
            f"cmp eax, dword ptr [0x{DUE_VA:x}]",
            text,
            "the pending flag is cleared without first comparing the clock "
            "against the recorded due time, so it clears on the first "
            f"gameplay frame and a second purchase is allowed: {text}",
        )
        self.assertTrue(
            any(i.mnemonic == "jb" for i in decoded),
            "no below-branch guarding the clear, so an event that is not yet "
            f"due would still be released: {text}",
        )

    def test_the_purchase_records_a_due_time_for_that_guard(self):
        """A guard reading a slot nothing writes would never fire."""
        arm_due = bytes([0xA3]) + DUE_VA.to_bytes(4, "little")
        alt = bytes([0x89, 0x05]) + DUE_VA.to_bytes(4, "little")
        self.assertTrue(
            arm_due in self.payload or alt in self.payload,
            "nothing writes the island due time, so the clear guard compares "
            f"the clock against an uninitialised slot at 0x{DUE_VA:X}",
        )

    def test_a_save_slot_change_clears_the_island_state(self):
        """The flag is process-global; the event it describes is per-save.

        Codex found this on #249: buy an Island Event in village A, switch to
        village B inside the five-second window, and B's first Island Event was
        refused for an event A had paid for. The Barrel already cleared its own
        flag here and the comment beside it spells out exactly this hazard --
        the island flag was simply added later and missed the reset.

        The due stamp is cleared too. A stale FUTURE stamp left behind would
        stop the release helper retiring a flag armed afterwards, turning a
        transient leak into a permanent one.
        """
        clear_flag = FLAG_CLEAR
        clear_due = bytes([0xC7, 0x05]) + DUE_VA.to_bytes(4, "little") + bytes(4)
        for variant, payload in sorted(_payload_variants().items()):
            with self.subTest(variant=variant):
                self.assertGreaterEqual(
                    payload.count(clear_flag),
                    2,
                    "the island pending flag is cleared in only one place. The "
                    "save-slot capture hook must clear it too, or a purchase "
                    "in one village blocks the next village's first event",
                )
                self.assertIn(
                    clear_due,
                    payload,
                    "the island due stamp is not zeroed on a slot change, so a "
                    "stale future stamp can stop the release helper retiring a "
                    "flag armed in the new village",
                )

    def test_the_guard_needs_no_clock_call(self):
        """Register-clobber safety, structurally.

        The second P1 was a stamp held in caller-saved `edx` across
        `0x403330`, which clobbers `eax/ecx/edx`. A guard that makes no call
        cannot have that class of bug, so assert the absence of the call rather
        than trying to prove a save/restore is correct.
        """
        index = self.payload.find(DEDUCT)
        self.assertGreater(index, 0, "deduction not found")
        # The PURCHASE guard, which is the one that carried the clobber bug --
        # scoped by walking back from the deduction it protects. The handler's
        # clear site legitimately calls the clock, under pushad/popad.
        start = self.payload.rfind(GUARD_TEST, 0, index)
        self.assertGreater(start, 0, "purchase guard not found")
        window = self.payload[start:index]
        self.assertNotIn(
            bytes([0xE8]),
            window,
            "the charge guard makes a call again. The queue clock clobbers "
            "eax/ecx/edx, which silently corrupted the previous version's "
            "comparison",
        )


if __name__ == "__main__":
    unittest.main()
