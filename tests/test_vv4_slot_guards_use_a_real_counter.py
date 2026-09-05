"""VV4's five slot guards must count live demand, not read a running total.

They originally compared against `0x4D6DE8`, which IS written -- by
`add dword ptr [0x4d6de8], ecx` at 0x45E91C, where ecx is the babies a
pregnancy still owes. Nothing decrements it, so it is a lifetime total of
babies ever conceived. Once it passes 150 the guards suppress twins, triplets
and event children permanently, however empty the village is. (An earlier
account called the address unwritten; that came from decoding one byte late,
which turns the writer into `or eax, 0x4d6de8`. See
tests/test_slot_guard_population_source.py.)

Two regressions are pinned here, because neither is visible in play:

* a guard reverting to a static compare -- indistinguishable from a guard with
  no reason to fire;
* the counter reverting to occupied-records-only -- which preserves the base,
  stride, active byte, slot count, return and every guard call, so geometry
  checks alone still pass while unborn babies stop being counted and events can
  over-reserve the 150 physical slots.

Asserted against a RENDERED executable rather than the generator source, since
what matters is the instruction the game executes.
"""

import struct
import unittest
from pathlib import Path
import sys

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.vv_fun_patcher import load_builds, render_patched_bytes  # noqa: E402

STOCK = ROOT / "inputs" / "vv4-stock-copy" / "Virtual Villagers - The Tree of Life.exe"

COUNTER_VA = 0x4890F0
GUARD_VAS = (0x489020, 0x489040, 0x489060, 0x489080, 0x4890C0)
# The running lifetime-conception total the guards used to read.
RUNNING_TOTAL_ADDRESS = 0x4D6DE8
# Record sweep the counter must perform.
RECORD_BASE = 0x50E5AC
RECORD_STRIDE = 0x2E3C
ACTIVE_BYTE = 0x1CC4
PREGNANT_FIELD = 0x1C4C
PENDING_BABIES = 0x1C50
SLOT_COUNT = 0x96
# Rendered-image landmarks inside the counter helper. Pinned so a branch
# that keeps its shape but flips its meaning cannot pass.
WRITER_VA = 0x45E91C          # the stock `add [0x4d6de8], ecx`
# Per-guard capacity thresholds and branch polarity, read from a
# rendered image. Pinned so a guard that still CALLS the counter but
# compares the wrong number cannot pass.
GUARD_EXPECTATIONS = {
    # va: (compared value, branch mnemonic, branch destination)
    0x489020: (0x93, "jg", 0x45E8D3),    # triplets: needs 3 free
    0x489040: (0x94, "jg", 0x45E8E4),    # twins: needs 2 free
    0x489060: (0x96, "jge", 0x489077),   # event newcomer: needs 1 free
    0x489080: (0x96, "jge", 0x489096),   # first barrel child: needs 1 free
}
# The fifth guard compares no threshold -- it converts occupancy into remaining
# capacity and clamps the brood to it, so it needs its own expectations.
CLAMP_GUARD_VA = 0x4890C0
CLAMP_MAX_CHILDREN = 6
CLAMP_NO_CAPACITY_VA = 0x4890ED   # `ret` -- refuse, create nothing
CLAMP_PROCEED_VA = 0x4890D8       # the reservation argument push
RESERVATION_CALL_VA = 0x467B00    # sub_467B00, the creation helper
CLAMP_BROOD_PUSH_VA = 0x4890E0    # the brood-count argument specifically
RESERVATION_CALL_ANCHOR = 0x4890E8  # the call site; the proceed path ends here
PENDING_FIELD = 0x1C50            # pending-baby count on a record
# Brood written on each multiple-birth guard's ALLOWED path. Pinned so a
# guard can keep its threshold and branch while writing a larger brood.
# Each multiple-birth guard writes a brood and then RESUMES the stock routine.
# Both halves are pinned: the brood, and the continuation it jumps back to.
# Retargeting the triplet continuation to the twin path leaves the `mov ..., 3`
# intact and then lets the twin path overwrite the pending count with 2.
GUARD_PAYLOADS = {
    0x489030: (3, 0x45E8CA),   # triplets
    0x489050: (2, 0x45E8DD),   # twins
}

# The two queued-event guards do not write a brood -- they push the stock
# routine's arguments and resume it. Pinned the same way: the exact argument
# sequence and the continuation, so a guard cannot resume the WRONG stock
# action (Island Event into the Barrel routine, or either with a changed
# delay) while every threshold and skip destination still matches.
EVENT_PAYLOADS = {
    0x48906C: (["esi", 0x258], 0x4148B6),   # Island Event
    0x48908C: ([0xC8], 0x414D95),           # Barrel of Babies
}
LOOP_HEAD_VA = 0x4890FE      # the per-record compare the loop returns to
NEXT_RECORD_VA = 0x489119    # `add edx, stride` -- the skip destination
PREGNANCY_FIELD = 0x1C4C     # non-zero when the record is expecting


def _sections(image):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    opt = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 24 + 28)[0]
    out = []
    for i in range(count):
        o = pe + 24 + opt + i * 40
        out.append(
            (
                base + struct.unpack_from("<I", image, o + 12)[0],
                struct.unpack_from("<I", image, o + 8)[0],
                struct.unpack_from("<I", image, o + 20)[0],
                struct.unpack_from("<I", image, o + 16)[0],
            )
        )
    return out


@unittest.skipIf(capstone is None, "requires capstone")
@unittest.skipUnless(STOCK.is_file(), "requires the VV4 stock executable")
class VV4SlotGuardCounterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        builds = {b.id: b for b in load_builds()}
        # No optional patches: these are automatic safety edits, always applied.
        cls.image, _ = render_patched_bytes(STOCK, builds["vv4"], "stock", [])
        cls.sections = _sections(cls.image)
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    def _offset(self, va):
        for start, vsize, raw, rsize in self.sections:
            if start <= va < start + max(vsize, rsize):
                return raw + (va - start)
        return None

    def _disasm(self, va, length):
        offset = self._offset(va)
        self.assertIsNotNone(offset, f"{va:#x} is not mapped")
        return list(self.md.disasm(self.image[offset : offset + length], va))

    def test_every_guard_calls_the_counter_first(self):
        for va in GUARD_VAS:
            with self.subTest(guard=hex(va)):
                first = self._disasm(va, 16)[0]
                self.assertEqual(first.mnemonic, "call", "guard does not start with a call")
                self.assertEqual(
                    int(first.op_str, 16),
                    COUNTER_VA,
                    "guard decides from something other than the record counter",
                )

    def test_every_guard_pins_its_threshold_and_branch(self):
        """Calling the counter is not enough; the comparison decides capacity.

        Operands are compared exactly, so neither `cmp eax, 0x930` nor
        `cmp ebx, 0x93` satisfies a 0x93 expectation, and the destination is
        pinned because a rel32 can be retargeted while mnemonic and threshold
        stay put.
        """
        for va, (threshold, jump, destination) in GUARD_EXPECTATIONS.items():
            with self.subTest(guard=hex(va)):
                insns = self._disasm(va, 24)
                cmps = [i for i in insns if i.mnemonic == "cmp"]
                self.assertTrue(cmps, f"guard at {va:#x} compares nothing")
                operands = self._ops(cmps[0])
                self.assertEqual(
                    operands[0], "eax",
                    f"guard at {va:#x} compares {operands[0]}, not the counter "
                    "result")
                self.assertTrue(
                    self._is_imm(operands[1], threshold),
                    f"guard at {va:#x} reserves against {operands[1]}, not "
                    f"{threshold:#x} free records")
                after = insns[insns.index(cmps[0]) + 1]
                self.assertEqual(
                    after.mnemonic, jump,
                    f"guard at {va:#x} branches with {after.mnemonic}, not "
                    f"{jump}; the polarity decides whether the event is allowed")
                self.assertEqual(
                    int(after.op_str, 16), destination,
                    f"guard at {va:#x} branches to {after.op_str}, not "
                    f"{destination:#x}; the destination decides what is skipped")

    def test_the_clamp_guard_converts_and_limits(self):
        """The fifth guard has no threshold -- it clamps the brood instead.

        Both decisions are pinned to their own comparison AND destination, and
        the clamped value is traced to the reservation call. Each of those can
        break alone: retargeting the zero-capacity `jle` from the `ret` to the
        argument push creates children with no slot remaining, and pushing a
        different register hands the helper an unrelated brood count.
        """
        insns = self._disasm(CLAMP_GUARD_VA, 48)
        decoded = [(i.mnemonic, self._ops(i)) for i in insns]

        self.assertIn(("neg", ["eax"]), decoded,
                      "the clamp guard does not negate the occupancy count")

        pool = [i for i in insns
                if i.mnemonic == "add" and self._ops(i)[0] == "eax"
                and self._is_imm(self._ops(i)[1], SLOT_COUNT)]
        self.assertTrue(
            pool, f"the clamp guard does not add the {SLOT_COUNT:#x}-slot pool")
        after_pool = insns[insns.index(pool[0]) + 1]
        self.assertEqual(
            (after_pool.mnemonic, int(after_pool.op_str, 16)),
            ("jle", CLAMP_NO_CAPACITY_VA),
            f"the zero-capacity branch is `{after_pool.mnemonic} "
            f"{after_pool.op_str}`, not `jle {CLAMP_NO_CAPACITY_VA:#x}`; "
            "retargeting it creates children with no slot remaining")

        cap = [i for i in insns
               if i.mnemonic == "cmp" and self._ops(i)[0] == "eax"
               and self._is_imm(self._ops(i)[1], CLAMP_MAX_CHILDREN)]
        self.assertTrue(cap, "the clamp guard no longer compares against "
                             f"{CLAMP_MAX_CHILDREN}")
        after_cap = insns[insns.index(cap[0]) + 1]
        self.assertEqual(
            (after_cap.mnemonic, int(after_cap.op_str, 16)),
            ("jle", CLAMP_PROCEED_VA),
            f"the brood clamp branches to `{after_cap.mnemonic} "
            f"{after_cap.op_str}`, not `jle {CLAMP_PROCEED_VA:#x}`")
        self.assertTrue(
            any(m == "mov" and o[0] == "eax"
                and self._is_imm(o[1], CLAMP_MAX_CHILDREN)
                for m, o in decoded if len(o) > 1),
            f"the clamp guard no longer caps the brood at {CLAMP_MAX_CHILDREN}")

        refusal = [i for i in insns if i.address == CLAMP_NO_CAPACITY_VA]
        self.assertTrue(
            refusal, f"nothing decodes at {CLAMP_NO_CAPACITY_VA:#x}")
        self.assertEqual(
            refusal[0].mnemonic, "ret",
            f"the zero-capacity destination is `{refusal[0].mnemonic}`, not "
            "`ret`; a fall-through there runs on into the counter instead of "
            "refusing the reservation")

        # The brood push is asserted at its exact address, not "somewhere before
        # the call" -- otherwise moving it to another register while a different
        # argument became `push eax` would still satisfy this.
        brood = [i for i in insns if i.address == CLAMP_BROOD_PUSH_VA]
        self.assertTrue(brood, f"nothing decodes at {CLAMP_BROOD_PUSH_VA:#x}")
        self.assertEqual(
            (brood[0].mnemonic, self._ops(brood[0])[0]), ("push", "eax"),
            f"{CLAMP_BROOD_PUSH_VA:#x} is `{brood[0].mnemonic} "
            f"{brood[0].op_str}`, not `push eax`; the reservation helper would "
            "receive an unrelated brood count")

        # And the proceed path must actually REACH the call: walk forward from
        # the clamp's proceed target and refuse any early return or jump away.
        walked = [i for i in insns
                  if CLAMP_PROCEED_VA <= i.address <= RESERVATION_CALL_ANCHOR]
        self.assertTrue(walked, "the proceed path decodes to nothing")
        for insn in walked:
            self.assertNotIn(
                insn.mnemonic, ("ret", "jmp"),
                f"`{insn.mnemonic} {insn.op_str}` at {insn.address:#x} leaves "
                "the proceed path before the reservation call, so a clamp "
                "result of 1..6 would create nothing")
        self.assertTrue(
            any(i.mnemonic == "call"
                and self._is_imm(i.op_str, RESERVATION_CALL_VA)
                for i in walked),
            f"the proceed path does not reach {RESERVATION_CALL_VA:#x}")

    def test_each_multiple_birth_writes_its_own_brood(self):
        """A threshold is only half the guard; the payload is the other half.

        Changing the triplet's `mov [esi+0x1c50], 3` to 4 keeps the counter
        call, the 0x93 comparison, the `jg` and both destinations intact -- and
        at a demand of 147 permits a fourth baby past the 150-record pool.
        """
        for va, (brood, resume) in GUARD_PAYLOADS.items():
            with self.subTest(payload=hex(va)):
                insns = self._disasm(va, 24)
                insn = insns[0]
                self.assertEqual(
                    insn.mnemonic, "mov",
                    f"{va:#x} is `{insn.mnemonic}`, not the brood write")
                destination, source = self._ops(insn)
                self.assertEqual(
                    destination, f"dword ptr [esi + {PENDING_FIELD:#x}]",
                    f"the brood at {va:#x} is written to {destination}, not the "
                    "pending-baby field")
                self.assertTrue(
                    self._is_imm(source, brood),
                    f"the guard at {va:#x} reserves {source} babies, not "
                    f"{brood}")
                # The continuation is the other half. Without it, retargeting
                # the triplet jump to the twin path keeps this brood write and
                # then lets the twin path overwrite the 3 with a 2.
                self.assertGreater(
                    len(insns), 1,
                    f"nothing follows the brood write at {va:#x}")
                # Mnemonic first, then the target. Parsing the operand inside
                # the tuple would raise on any non-rel32 continuation (`ret`,
                # `nop`, `jmp eax` all give an unparseable op_str), replacing
                # the message below with an unrelated ValueError.
                self.assertEqual(
                    insns[1].mnemonic, "jmp",
                    f"the guard at {va:#x} resumes with `{insns[1].mnemonic} "
                    f"{insns[1].op_str}`, not a `jmp`; a retargeted "
                    "continuation runs a different stock birth path and can "
                    "overwrite the brood this guard just reserved")
                # `_is_imm` rather than a bare `int(..., 16)`: an INDIRECT
                # continuation (`jmp eax`) keeps the mnemonic and so reaches
                # here, and parsing its operand would raise instead of
                # reporting the message below.
                self.assertTrue(
                    self._is_imm(insns[1].op_str, resume),
                    f"the guard at {va:#x} resumes at `{insns[1].op_str}`, not "
                    f"{resume:#x}; a retargeted continuation runs a different "
                    "stock birth path and can overwrite the brood this guard "
                    "just reserved")

    def test_each_event_guard_resumes_its_own_stock_action(self):
        """The queued-event guards push arguments and resume -- pin both.

        `GUARD_EXPECTATIONS` pins only each guard's taken SKIP destination, so
        the fall-through payload was unconstrained: Island Event could push the
        Barrel's argument, or either could resume the other's stock routine,
        with every existing assertion still green.
        """
        for va, (args, resume) in EVENT_PAYLOADS.items():
            with self.subTest(event=hex(va)):
                insns = self._disasm(va, 24)
                pushes = []
                index = 0
                while index < len(insns) and insns[index].mnemonic == "push":
                    pushes.append(self._ops(insns[index])[0])
                    index += 1
                self.assertEqual(
                    len(pushes), len(args),
                    f"the guard at {va:#x} pushes {len(pushes)} arguments, not "
                    f"{len(args)}; the stock routine would read the wrong stack")
                for position, (actual, expected) in enumerate(zip(pushes, args)):
                    if isinstance(expected, int):
                        self.assertTrue(
                            self._is_imm(actual, expected),
                            f"argument {position} at {va:#x} is `{actual}`, not "
                            f"{expected:#x}")
                    else:
                        self.assertEqual(
                            actual, expected,
                            f"argument {position} at {va:#x} is `{actual}`, not "
                            f"`{expected}`")
                self.assertLess(
                    index, len(insns),
                    f"nothing follows the pushes at {va:#x}")
                # Split for the same reason as the brood continuation above:
                # a non-rel32 resume has an op_str `int` cannot parse.
                self.assertEqual(
                    insns[index].mnemonic, "jmp",
                    f"the guard at {va:#x} resumes with "
                    f"`{insns[index].mnemonic} {insns[index].op_str}`, not a "
                    "`jmp`; it would run the wrong stock action")
                # `_is_imm` for the same reason as the brood continuation:
                # `jmp eax` keeps the mnemonic and would raise on parse.
                self.assertTrue(
                    self._is_imm(insns[index].op_str, resume),
                    f"the guard at {va:#x} resumes at "
                    f"`{insns[index].op_str}`, not {resume:#x}; it would run "
                    "the wrong stock action")

    def test_no_guard_reads_the_running_total(self):
        """The exact regression: back to the lifetime-conception total."""
        for va in GUARD_VAS:
            with self.subTest(guard=hex(va)):
                text = " ; ".join(
                    f"{i.mnemonic} {i.op_str}" for i in self._disasm(va, 32)
                )
                self.assertNotIn(hex(RUNNING_TOTAL_ADDRESS), text.lower())

    def test_running_total_is_still_written_but_no_longer_consulted(self):
        """The stock writer stays; only the guards' dependence on it is gone.

        Disassembled and compared operand by operand. Counting address bytes
        proves only that the number appears -- `add dword ptr [eax], 0x4d6de8`
        would satisfy a mnemonic check, contain the address, start with a
        memory destination, and still not write it. That is the same ambiguity
        that produced the documentation error this suite corrects.
        """
        needle = struct.pack("<I", RUNNING_TOTAL_ADDRESS)
        self.assertEqual(
            self.image.count(needle), 1,
            "expected exactly the stock `add [0x4d6de8], ecx` writer")
        insn = self._disasm(WRITER_VA, 8)[0]
        self.assertEqual(
            insn.mnemonic, "add",
            f"{WRITER_VA:#x} is not an add; the running total is no longer "
            "written where the documentation says it is")
        operands = self._ops(insn)
        self.assertEqual(len(operands), 2,
                         f"unexpected operand shape: {insn.op_str}")
        self.assertEqual(
            operands[0], f"dword ptr [{RUNNING_TOTAL_ADDRESS:#x}]",
            f"the running total is not the DESTINATION -- got {operands[0]}")
        self.assertEqual(
            operands[1], "ecx",
            f"the writer adds {operands[1]}, not ecx; that changes the "
            "documented lifetime-conception semantics")

    def test_counter_sweeps_the_record_array(self):
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self._disasm(COUNTER_VA, 64))
        self.assertIn(hex(RECORD_BASE), text.lower(), "counter does not start at the pool")
        self.assertIn(hex(RECORD_STRIDE), text.lower(), "counter does not use the record stride")
        self.assertIn(hex(ACTIVE_BYTE), text.lower(), "counter does not test the active byte")
        self.assertIn(hex(SLOT_COUNT), text.lower(), "counter does not bound at 150 slots")

    @staticmethod
    def _ops(insn):
        """Decoded operands, normalised. Substring matching is not enough:
        `cmp eax, 0x93` and `cmp eax, 0x930` both contain "0x93", and a changed
        left operand is invisible to it."""
        return [part.strip().lower() for part in insn.op_str.split(",")]

    @staticmethod
    def _is_imm(operand, value):
        try:
            return int(operand, 16) == value
        except ValueError:
            return False

    def _gate(self, displacement, width):
        """(compare, following branch) for a record-field test.

        `width` is asserted, not inferred: byte and dword reads are NOT
        interchangeable. Reading the active flag as a dword makes an
        inactive record with any nonzero adjacent byte count as occupied.

        The memory operand is parsed and compared exactly. Substring matching
        would let `0x1cc4` also match `0x1cc40`, i.e. a counter reading outside
        the intended field while every polarity assertion still passed.
        """
        want = f"{width} ptr [edx + {displacement:#x}]"
        insns = self._disasm(COUNTER_VA, 64)
        for index, insn in enumerate(insns):
            if insn.mnemonic != "cmp":
                continue
            operands = self._ops(insn)
            if operands[0] != want:
                continue
            if not self._is_imm(operands[1], 0) and operands[1] != "0":
                continue
            for follower in insns[index + 1:]:
                if follower.mnemonic.startswith("j"):
                    return insn, follower
        return None, None

    def test_the_active_byte_branch_skips_inactive_records(self):
        """Polarity matters: `jne` here would count the dead and skip the living.

        Presence of a jump is not enough -- flipping this one inverts the
        counter's meaning while leaving every other assertion satisfied.
        """
        compare, branch = self._gate(ACTIVE_BYTE, "byte")
        self.assertIsNotNone(
            compare,
            f"no `cmp [edx + {ACTIVE_BYTE:#x}], 0` in the counter; the active-byte\n"
            "test does not read the intended record field")
        mnemonic, target = branch.mnemonic, int(branch.op_str, 16)
        self.assertEqual(mnemonic, "je",
                         "the active-byte test must skip when the byte is zero; "
                         "any other polarity counts inactive records as live")
        self.assertEqual(target, NEXT_RECORD_VA,
                         "the inactive path must jump to the next-record step")

    def test_the_pregnancy_branch_skips_only_the_pending_add(self):
        """`jne` here would drop pending babies from the demand figure."""
        compare, branch = self._gate(PREGNANCY_FIELD, "dword")
        self.assertIsNotNone(
            compare,
            f"no `cmp [edx + {PREGNANCY_FIELD:#x}], 0` in the counter")
        mnemonic, target = branch.mnemonic, int(branch.op_str, 16)
        self.assertEqual(mnemonic, "je",
                         "a non-pregnant record must skip the pending-baby add")
        self.assertEqual(target, NEXT_RECORD_VA,
                         "the not-pregnant path must jump to the next-record step")

    def test_the_loop_actually_walks_every_record(self):
        """Every register the sweep depends on, pinned by name.

        Each of these breaks alone while the others still pass: the accumulator
        must be zeroed and incremented in EAX (otherwise the helper returns
        caller garbage, or counts only pending babies), the record pointer must
        be initialised into EDX and advanced by the stride (otherwise it walks
        arbitrary memory, or the same record 150 times), and the countdown must
        be initialised into ECX with a back-edge to the per-record compare.
        """
        insns = self._disasm(COUNTER_VA, 64)
        decoded = [(i.mnemonic, self._ops(i)) for i in insns]

        self.assertIn(
            ("xor", ["eax", "eax"]), decoded,
            "the accumulator is not zeroed in EAX; the helper would return "
            "whatever the caller left there")
        self.assertIn(
            ("add", ["eax", "1"]), decoded,
            "no `add eax, 1` for an occupied record; the count would omit "
            "living villagers")
        self.assertTrue(
            any(m == "mov" and o[0] == "edx" and self._is_imm(o[1], RECORD_BASE)
                for m, o in decoded if len(o) > 1),
            f"the record pointer is not initialised as "
            f"`mov edx, {RECORD_BASE:#x}`; the sweep would start from an "
            "uninitialised caller value")
        self.assertTrue(
            any(m == "mov" and o[0] == "ecx" and self._is_imm(o[1], SLOT_COUNT)
                for m, o in decoded if len(o) > 1),
            f"the countdown is not `mov ecx, {SLOT_COUNT:#x}`")
        self.assertIn(("sub", ["ecx", "1"]), decoded,
                      "the counter does not decrement its record countdown")

        step = [i for i in insns if i.address == NEXT_RECORD_VA]
        self.assertTrue(step, f"nothing decodes at {NEXT_RECORD_VA:#x}")
        operands = self._ops(step[0])
        self.assertEqual(
            (step[0].mnemonic, operands[0]), ("add", "edx"),
            f"the next-record step is `{step[0].mnemonic} {step[0].op_str}`; "
            "advancing anything but EDX walks the same record every iteration")
        self.assertTrue(
            self._is_imm(operands[1], RECORD_STRIDE),
            f"the next-record step advances by {operands[1]}, not the stride")

        self.assertTrue(
            [i for i in insns
             if i.mnemonic == "jne" and int(i.op_str, 16) == LOOP_HEAD_VA],
            f"no conditional back-edge to {LOOP_HEAD_VA:#x}")

    def test_counter_adds_pending_babies_behind_a_pregnancy_gate(self):
        """Geometry alone is not enough.

        Reverting the helper to an occupied-records-only sweep keeps the base,
        stride, active byte, slot count, return and every guard call intact --
        so every other test here still passes while unborn babies stop being
        counted and events can reserve past the 150 physical slots. That is the
        regression the document's "physical demand" claim rests on, so assert it
        directly: the pregnancy field must be TESTED, the pending count ADDED,
        and the add must sit behind the test.
        """
        instructions = self._disasm(COUNTER_VA, 64)
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in instructions).lower()
        self.assertIn(hex(PREGNANT_FIELD), text, "counter never tests the pregnancy field")
        self.assertIn(hex(PENDING_BABIES), text, "counter never adds the pending babies")

        gate = next(
            (i for i in instructions if hex(PREGNANT_FIELD) in i.op_str.lower()), None
        )
        add = next(
            (i for i in instructions if hex(PENDING_BABIES) in i.op_str.lower()), None
        )
        self.assertIsNotNone(gate)
        self.assertIsNotNone(add)
        self.assertEqual(gate.mnemonic, "cmp", "the pregnancy field is not tested")
        self.assertEqual(add.mnemonic, "add", "pending babies are not accumulated")
        self.assertLess(
            gate.address,
            add.address,
            "pending babies are added without first testing for a pregnancy",
        )
        between = [
            i
            for i in instructions
            if gate.address < i.address < add.address and i.mnemonic.startswith("j")
        ]
        self.assertTrue(
            between,
            "no branch between the pregnancy test and the add: the count would "
            "include babies for villagers who are not pregnant",
        )


    def test_the_pending_add_accumulates_into_eax(self):
        """The demand figure is EAX; adding elsewhere silently drops babies.

        The pregnancy-gate test accepts any `add` mentioning the field, so
        redirecting this one to another register left every assertion green
        while the returned demand omitted every unborn baby.
        """
        adds = [i for i in self._disasm(COUNTER_VA, 64)
                if i.mnemonic == "add"
                and self._ops(i)[1] == f"dword ptr [edx + {PENDING_FIELD:#x}]"]
        self.assertTrue(
            adds,
            f"no `add <reg>, [edx + {PENDING_FIELD:#x}]` in the counter")
        self.assertEqual(
            self._ops(adds[0])[0], "eax",
            f"pending babies are added into {self._ops(adds[0])[0]}, not eax; "
            "the returned demand would omit every unborn baby")

    def test_counter_skips_unoccupied_records(self):
        """The active-byte test must gate the increment, not merely appear."""
        instructions = self._disasm(COUNTER_VA, 64)
        gate = next(
            (i for i in instructions if hex(ACTIVE_BYTE) in i.op_str.lower()), None
        )
        self.assertIsNotNone(gate, "counter never tests the active byte")
        self.assertEqual(gate.mnemonic, "cmp")
        following = [i for i in instructions if i.address > gate.address][:1]
        self.assertTrue(
            following and following[0].mnemonic.startswith("j"),
            "the occupancy test is not followed by a branch, so every record "
            "would be counted whether occupied or not",
        )

    def test_counter_returns_rather_than_falling_through(self):
        """VV5's mirror bug was a guard returning from mid-function."""
        instructions = self._disasm(COUNTER_VA, 64)
        self.assertTrue(
            any(i.mnemonic == "ret" for i in instructions),
            "the counter never returns to its caller",
        )


class VV4SlotGuardDocTests(unittest.TestCase):
    """Deliberately OUTSIDE the binary-dependent class.

    Both skip decorators there (capstone, and the gitignored stock exe) would
    otherwise skip this too -- so in exactly the dependency-free runs that are
    most common, the title regression would have no coverage at all.
    """

    def test_doc_does_not_claim_the_guards_are_inert(self):
        doc = (ROOT / "docs" / "vv4-slot-guards-are-inert.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "# VV4's 150-slot safety guards never fire",
            doc,
            "the doc's title again asserts a defect the image disproves",
        )

    def test_doc_does_not_claim_nothing_writes_the_address(self):
        """The error this file has carried twice: 0x4D6DE8 IS written by
        `add dword ptr [0x4d6de8], ecx` at 0x45E91C. Decoding one byte late
        hides the writer."""
        doc = (ROOT / "docs" / "vv4-slot-guards-are-inert.md").read_text(encoding="utf-8")
        self.assertNotIn("**Nothing ever wrote `0x4D6DE8`.**", doc)
        self.assertIn("add dword ptr [0x4d6de8], ecx", doc.lower())

    def test_doc_does_not_claim_the_playtest_is_done(self):
        """Static disassembly is not runtime evidence."""
        doc = (ROOT / "docs" / "vv4-slot-guards-are-inert.md").read_text(encoding="utf-8")
        self.assertNotIn("All four were completed", doc)


if __name__ == "__main__":
    unittest.main()
