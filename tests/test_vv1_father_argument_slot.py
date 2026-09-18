"""The VV1 father must be read from the argument slot the stub writes.

The owner's parentage log showed every VV1 conception reporting "(not captured
for this birth)". Nothing static caught it: the trampolines disassembled
correctly, every byte guard passed, and the companion behaved exactly as
designed -- it validated the pointer it was handed, found it was not a villager
record, and said so.

The fault was one constant. The stub writes the father into the dead SECOND
argument, but the trampolines computed their displacement from arg1's position,
so they read arg3 -- a skill selector -- and passed that instead.

These guards close the loop by deriving the displacement from the emitted bytes
rather than restating the constant, so the two halves of the mechanism cannot
disagree again.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURE = ROOT / "data" / "vv1_parentage_feature.json"

# Where the father sits relative to the esp the routine is entered with, i.e.
# at the moment `call 0x43BBC0` transfers control and esp points at the return
# address. arg1..arg4 follow at +0x04, +0x08, +0x0C, +0x10, and the dead slot
# the stub commandeers is arg2.
FATHER_AT_ENTRY_ESP = 0x08

# What each tail has pushed before the trampoline runs. sub_43BBC0 opens with
# `push edi` then `push esi`; the twins tail at 0x43BCBA is past both pops and
# so is back at the entry esp, while the other two are eight bytes deeper.
TAIL_ADJUSTMENTS = (0, 8)

PUSHAL = 0x20


def emitted_payloads():
    record = json.loads(FEATURE.read_text(encoding="utf-8"))
    out = []
    stack = [record]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            after = node.get("after")
            offset = node.get("offset")
            if isinstance(after, str) and len(after) >= 40 and offset:
                try:
                    out.append((bytes.fromhex(after), int(offset, 16)))
                except ValueError:
                    pass
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return out


class VV1FatherArgumentSlotTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import capstone  # noqa: F401
        except ImportError:  # pragma: no cover - optional dependency
            self.skipTest("capstone is not installed")
        self.assertTrue(
            FEATURE.is_file(), "the VV1 parentage feature must be rendered")

    def father_pushes(self):
        """Every `push [esp+disp]` in the emitted payloads, disp > pushal."""
        import capstone

        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        found = set()
        for code, offset in emitted_payloads():
            address = offset + 0x400000 if offset < 0x400000 else offset
            for instruction in md.disasm(code, address):
                if instruction.mnemonic != "push":
                    continue
                match = re.fullmatch(
                    r"dword ptr \[esp \+ (0x[0-9a-f]+)\]",
                    instruction.op_str)
                if match:
                    displacement = int(match.group(1), 16)
                    # The three small pushes are the companion's own
                    # arguments, re-pushed from its stack frame.
                    if displacement > PUSHAL:
                        found.add(displacement)
        return sorted(found)

    def test_every_trampoline_reads_the_dead_second_argument(self) -> None:
        """Derived from the bytes, not restated from the constant.

        A displacement one dword out reads arg3 and passes a skill selector
        as the father. That is exactly what shipped, and it produced a log
        that said the father was not captured on every single birth.
        """
        pushes = self.father_pushes()
        self.assertTrue(
            pushes, "no father push found in the emitted payloads")
        for displacement in pushes:
            with self.subTest(displacement=hex(displacement)):
                tail_relative = displacement - PUSHAL
                candidates = {
                    tail_relative - adjustment
                    for adjustment in TAIL_ADJUSTMENTS
                }
                self.assertIn(
                    FATHER_AT_ENTRY_ESP, candidates,
                    "push [esp+%#x] resolves to entry+%s, and the father is "
                    "at entry+%#x"
                    % (displacement,
                       "/".join(hex(c) for c in sorted(candidates)),
                       FATHER_AT_ENTRY_ESP))

    def test_the_stub_and_the_trampoline_agree(self) -> None:
        """Both halves must name the same slot.

        The stub writes at the call site, where esp is one dword lower than
        the routine's entry esp because the call has pushed a return address
        -- so its displacement is the entry-relative one exactly. They were
        consistent before this fix on the stub side and wrong on the read
        side, which is why only one of the two was corrected.
        """
        source = (ROOT / "scripts"
                  / "build_vv1_parentage_feature.py").read_text(
                      encoding="utf-8")
        match = re.search(r"FATHER_ARG_AT_STUB = (0x[0-9A-Fa-f]+)", source)
        self.assertIsNotNone(match, "the stub displacement must be declared")
        self.assertEqual(
            int(match.group(1), 16), FATHER_AT_ENTRY_ESP,
            "the stub must write the dead second argument")

        for name in ("TRIPLETS", "TWINS", "SINGLE"):
            with self.subTest(tail=name):
                tail = re.search(
                    r"FATHER_ARG_AT_%s = (0x[0-9A-Fa-f]+) \+ (\d+)"
                    % name, source)
                self.assertIsNotNone(
                    tail, "FATHER_ARG_AT_%s must be declared" % name)
                base, adjustment = int(tail.group(1), 16), int(tail.group(2))
                self.assertEqual(
                    base, FATHER_AT_ENTRY_ESP,
                    "%s must be measured from the father's own slot" % name)
                self.assertIn(adjustment, TAIL_ADJUSTMENTS)

    def test_the_reentry_audit_records_the_same_displacement(self) -> None:
        """The audit prose must not contradict the emitted bytes.

        Codex raised this: the fingerprints were updated but the register
        contract recorded alongside them still described the defective
        offsets. An audit that records the wrong contract is worse than no
        audit, because it is what a later reviewer consults -- it would have
        justified restoring the exact bug being fixed here.

        So the prose is checked against the same constant the trampolines are
        built from, rather than left to be re-read by eye.
        """
        audit = (ROOT / "tests"
                 / "test_vv1_hook_foreign_reentry_audit.py").read_text(
                     encoding="utf-8")
        self.assertIn(
            "0x20+0x08", audit,
            "the audit must record the twins tail's real displacement")
        self.assertIn(
            "0x20+0x08+8", audit,
            "the audit must show how the deeper tails are derived")
        # The defective values must not survive anywhere in the prose.
        self.assertNotIn(
            "0x20+0x14", audit,
            "the audit still records arg3's displacement")
        self.assertNotIn(
            "0x20+0x0C", audit,
            "the audit still records arg1's displacement")
        # Case-insensitive: the prose capitalises SECOND for emphasis, so a
        # revert to "third" could arrive in any casing.
        # Case-insensitive, and tolerant of the comment wrapping: the prose
        # capitalises SECOND for emphasis and the phrase spans a line break,
        # so a revert to "third" could arrive in any casing or layout.
        self.assertNotRegex(
            audit,
            r"(?i)third\s+stack\s*(?:\n\s*#)?\s*argument",
            "the dead slot is the second argument, not the third")
        self.assertRegex(
            audit,
            r"(?i)second\s+stack\s*(?:\n\s*#)?\s*argument",
            "the audit must name the second argument as the dead slot")

    def test_no_site_passes_the_mothers_register(self) -> None:
        """esi is the `this` pointer -- the mother -- at every call site.

        0x447238 chose ecx, which 0x44722E overwrites with esi before the
        call, so that site handed the companion the mother. The companion
        rejects a father equal to the mother, so it could never have captured
        even once the displacement was right.
        """
        source = (ROOT / "scripts"
                  / "build_vv1_parentage_feature.py").read_text(
                      encoding="utf-8")
        table = source[source.index("FATHER_CALL_SITES = ("):]
        table = table[:table.index("\n)")]
        registers = re.findall(r'"(e[a-z]{2})"', table)
        self.assertEqual(
            len(registers), 6, "all six call sites must name a register")
        self.assertNotIn(
            "esi", registers, "esi is the mother, never the father")
        # 0x447238 specifically: ecx is clobbered there.
        site = re.search(
            r"\(0x00447238,[^)]*?\"(e[a-z]{2})\"", table, re.S)
        self.assertIsNotNone(site, "site 0x447238 must be present")
        self.assertEqual(
            site.group(1), "eax",
            "0x447238 must pass eax; ecx is overwritten with the mother")


if __name__ == "__main__":
    unittest.main()
